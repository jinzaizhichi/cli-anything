"""Backend helpers for the official Nsight Graphics CLI tools."""

from __future__ import annotations

import glob
import ctypes
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

ENV_VAR = "NSIGHT_GRAPHICS_PATH"

_BINARY_CANDIDATES = {
    "ngfx": ("ngfx.exe", "ngfx"),
    "ngfx_ui": ("ngfx-ui.exe", "ngfx-ui"),
    "ngfx_capture": ("ngfx-capture.exe", "ngfx-capture"),
    "ngfx_replay": ("ngfx-replay.exe", "ngfx-replay"),
}

INSTALL_INSTRUCTIONS = (
    "Nsight Graphics CLI tools were not found.\n"
    "Install NVIDIA Nsight Graphics and make sure ngfx.exe is available, or set "
    f"{ENV_VAR} to the install directory or executable path.\n"
    "Typical Windows location:\n"
    "  C:\\Program Files\\NVIDIA Corporation\\Nsight Graphics <version>\\host\\windows-desktop-nomad-x64"
)


def _command_string(args: Sequence[str]) -> str:
    """Render a command for display."""
    if platform.system() == "Windows":
        return subprocess.list2cmdline(list(args))
    return " ".join(args)


def _dedupe(values: Iterable[str]) -> list[str]:
    """Deduplicate while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = os.path.normcase(os.path.normpath(value))
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
    return result


def _normalized_install_key(path: str) -> str:
    """Normalize a path for install-root comparisons across slash styles."""
    normalized = os.path.normcase(os.path.normpath(path))
    return re.sub(r"[\\/]+", "/", normalized).rstrip("/")


def _scan_directory(directory: str) -> dict[str, str]:
    """Scan a directory for known Nsight binaries."""
    found: dict[str, str] = {}
    base = Path(directory)
    if not base.is_dir():
        return found
    for key, candidates in _BINARY_CANDIDATES.items():
        for candidate in candidates:
            path = base / candidate
            if path.is_file():
                found[key] = str(path.resolve())
                break
    return found


def _candidate_dirs_from_env(path_value: str) -> list[str]:
    """Resolve environment override into candidate directories."""
    if not path_value:
        return []
    path = Path(path_value)
    candidates: list[str] = []
    if path.is_file():
        candidates.append(str(path.parent))
    else:
        candidates.append(str(path))
        candidates.append(str(path / "host" / "windows-desktop-nomad-x64"))
        candidates.append(str(path / "windows-desktop-nomad-x64"))
    return _dedupe([p for p in candidates if Path(p).exists()])


def _default_windows_install_dirs(
    glob_func: Callable[[str], list[str]],
) -> list[str]:
    """Return default Windows install directories for Nsight Graphics."""
    drive_roots = _fixed_windows_drive_roots()
    if not drive_roots:
        drive_roots = ["C:"]

    patterns: list[str] = []
    for drive in drive_roots:
        patterns.extend(
            [
                f"{drive}/Program Files/NVIDIA Corporation/Nsight Graphics */host/windows-desktop-nomad-x64",
                f"{drive}/Program Files (x86)/NVIDIA Corporation/Nsight Graphics */host/windows-desktop-nomad-x64",
            ]
        )
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(glob_func(pattern))
    return _dedupe(
        sorted(
            matches,
            key=lambda path: (_version_sort_key(_extract_version_from_path(path)), path),
            reverse=True,
        )
    )


def _fixed_windows_drive_roots() -> list[str]:
    """Return fixed-drive roots such as C: and D: on Windows."""
    if platform.system() != "Windows":
        return []
    try:
        drive_mask = ctypes.windll.kernel32.GetLogicalDrives()
        get_drive_type = ctypes.windll.kernel32.GetDriveTypeW
    except Exception:
        return []

    DRIVE_FIXED = 3
    drives: list[str] = []
    for index in range(26):
        if not (drive_mask & (1 << index)):
            continue
        letter = chr(ord("A") + index)
        root = f"{letter}:\\"
        try:
            if get_drive_type(root) == DRIVE_FIXED:
                drives.append(f"{letter}:")
        except Exception:
            continue
    return drives


def _read_registry_installations(
    platform_system: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Read Nsight Graphics install records from the Windows uninstall registry."""
    platform_system = platform.system() if platform_system is None else platform_system
    if platform_system != "Windows":
        return []

    try:
        import winreg
    except ImportError:
        return []

    uninstall_roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    def _query_value(key, name: str) -> Optional[str]:
        try:
            value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            return None
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    records: list[dict[str, Any]] = []
    for hive, root in uninstall_roots:
        try:
            with winreg.OpenKey(hive, root) as root_key:
                index = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(root_key, index)
                    except OSError:
                        break
                    index += 1
                    try:
                        with winreg.OpenKey(root_key, subkey_name) as subkey:
                            display_name = _query_value(subkey, "DisplayName")
                            if not display_name or "Nsight Graphics" not in display_name:
                                continue
                            records.append(
                                {
                                    "display_name": display_name,
                                    "display_version": _query_value(subkey, "DisplayVersion"),
                                    "install_location": _query_value(subkey, "InstallLocation"),
                                    "install_source": _query_value(subkey, "InstallSource"),
                                    "uninstall_string": _query_value(subkey, "UninstallString"),
                                    "publisher": _query_value(subkey, "Publisher"),
                                    "registry_key": f"HKLM\\{root}\\{subkey_name}",
                                }
                            )
                    except OSError:
                        continue
        except OSError:
            continue
    return records


def _override_value(
    env: dict[str, str],
    nsight_path: Optional[str] = None,
) -> str:
    """Resolve the effective override path from CLI or environment."""
    if nsight_path and nsight_path.strip():
        return nsight_path.strip()
    return env.get(ENV_VAR, "").strip()


def discover_binaries(
    env: Optional[dict[str, str]] = None,
    which: Optional[Callable[[str], Optional[str]]] = None,
    glob_func: Optional[Callable[[str], list[str]]] = None,
    platform_system: Optional[str] = None,
    nsight_path: Optional[str] = None,
) -> dict[str, Any]:
    """Discover available Nsight binaries."""
    env = os.environ if env is None else env
    which = shutil.which if which is None else which
    glob_func = glob.glob if glob_func is None else glob_func
    platform_system = platform.system() if platform_system is None else platform_system

    binaries: dict[str, Optional[str]] = {
        "ngfx": None,
        "ngfx_ui": None,
        "ngfx_capture": None,
        "ngfx_replay": None,
    }
    search_roots: list[str] = []
    override = _override_value(env, nsight_path=nsight_path)

    if override:
        override_path = Path(override)
        if override_path.is_file():
            for key, candidates in _BINARY_CANDIDATES.items():
                lowered = {name.lower() for name in candidates}
                if override_path.name.lower() in lowered:
                    binaries[key] = str(override_path.resolve())
                    break
        search_roots.extend(_candidate_dirs_from_env(override))

    for key, candidates in _BINARY_CANDIDATES.items():
        for candidate in candidates:
            resolved = which(candidate)
            if resolved:
                binaries[key] = binaries[key] or str(Path(resolved).resolve())
                search_roots.append(str(Path(resolved).resolve().parent))
                break

    if platform_system == "Windows":
        search_roots.extend(_default_windows_install_dirs(glob_func))

    for directory in _dedupe(search_roots):
        found = _scan_directory(directory)
        for key, value in found.items():
            binaries[key] = binaries[key] or value

    return {
        "binaries": binaries,
        "search_roots": _dedupe(search_roots),
        "env_override": env.get(ENV_VAR, "").strip() or None,
        "cli_override": nsight_path.strip() if nsight_path and nsight_path.strip() else None,
        "effective_override": override or None,
    }


def list_installations(
    env: Optional[dict[str, str]] = None,
    which: Optional[Callable[[str], Optional[str]]] = None,
    glob_func: Optional[Callable[[str], list[str]]] = None,
    platform_system: Optional[str] = None,
    nsight_path: Optional[str] = None,
) -> dict[str, Any]:
    """List installed Nsight Graphics directories and versions."""
    env = os.environ if env is None else env
    which = shutil.which if which is None else which
    glob_func = glob.glob if glob_func is None else glob_func
    platform_system = platform.system() if platform_system is None else platform_system

    discovered = discover_binaries(
        env=env,
        which=which,
        glob_func=glob_func,
        platform_system=platform_system,
        nsight_path=nsight_path,
    )
    selected_path = _primary_executable(discovered["binaries"])

    candidates: list[str] = []
    for root in discovered["search_roots"]:
        candidates.append(root)
    if platform_system == "Windows":
        candidates.extend(_default_windows_install_dirs(glob_func))
    if nsight_path:
        candidates.extend(_candidate_dirs_from_env(nsight_path))
    if env.get(ENV_VAR, "").strip():
        candidates.extend(_candidate_dirs_from_env(env[ENV_VAR]))
    for key, names in _BINARY_CANDIDATES.items():
        for name in names:
            resolved = which(name)
            if resolved:
                candidates.append(str(Path(resolved).resolve().parent))
                break

    installations: list[dict[str, Any]] = []
    installation_keys: set[str] = set()
    for directory in _dedupe(candidates):
        found = _scan_directory(directory)
        if not found:
            continue
        primary = _primary_executable(found)
        key = f"fs::{os.path.normcase(os.path.normpath(directory))}"
        installation_keys.add(key)
        installations.append(
            {
                "install_root": directory,
                "version": _extract_version_from_path(directory) or _extract_version_from_path(primary or ""),
                "tool_mode": detect_tool_mode(found),
                "selected": bool(primary and selected_path and os.path.normcase(primary) == os.path.normcase(selected_path)),
                "discovery_sources": ["filesystem"],
                "registered_only": False,
                "registry_key": None,
                "display_name": None,
                "display_version": None,
                "install_source": None,
                "binaries": {
                    key: found.get(key) for key in ("ngfx", "ngfx_ui", "ngfx_capture", "ngfx_replay")
                },
            }
        )

    for record in _read_registry_installations(platform_system=platform_system):
        install_location = record.get("install_location")
        normalized_location = None
        if install_location:
            normalized_location = _normalized_install_key(install_location)
        guessed_version = (
            _extract_version_from_text(record.get("display_name") or "")
            or _extract_version_from_text(record.get("display_version") or "")
        )

        matched_entry = None
        if normalized_location:
            for item in installations:
                item_root = item.get("install_root")
                if not item_root:
                    continue
                normalized_root = _normalized_install_key(item_root)
                if (
                    normalized_root == normalized_location
                    or normalized_root.startswith(normalized_location + "/")
                    or normalized_location.startswith(normalized_root + "/")
                ):
                    matched_entry = item
                    break
        elif guessed_version:
            same_version = [
                item
                for item in installations
                if not item.get("registered_only") and item.get("version") == guessed_version
            ]
            if len(same_version) == 1:
                matched_entry = same_version[0]

        if matched_entry is not None:
            matched_entry["discovery_sources"] = _dedupe(
                list(matched_entry.get("discovery_sources", [])) + ["registry"]
            )
            matched_entry["display_name"] = record.get("display_name")
            matched_entry["display_version"] = record.get("display_version")
            matched_entry["registry_key"] = record.get("registry_key")
            matched_entry["install_source"] = record.get("install_source")
            if not matched_entry.get("version"):
                matched_entry["version"] = guessed_version
            continue

        registry_key = f"reg::{record['registry_key']}"
        if registry_key in installation_keys:
            continue
        installation_keys.add(registry_key)
        installations.append(
            {
                "install_root": install_location or None,
                "version": guessed_version,
                "tool_mode": "registered-only",
                "selected": False,
                "discovery_sources": ["registry"],
                "registered_only": True,
                "registry_key": record.get("registry_key"),
                "display_name": record.get("display_name"),
                "display_version": record.get("display_version"),
                "install_source": record.get("install_source"),
                "binaries": {
                    "ngfx": None,
                    "ngfx_ui": None,
                    "ngfx_capture": None,
                    "ngfx_replay": None,
                },
            }
        )

    installations.sort(
        key=lambda item: (
            not item["selected"],
            item.get("registered_only", False),
            item.get("version") or "",
            item.get("install_root") or item.get("display_name") or "",
        ),
        reverse=False,
    )
    return {
        "ok": bool(installations),
        "selected_executable": selected_path,
        "count": len(installations),
        "installations": installations,
        "cli_override": discovered.get("cli_override"),
        "env_override": discovered.get("env_override"),
        "registry_count": sum(1 for item in installations if "registry" in item.get("discovery_sources", [])),
    }


def detect_tool_mode(binaries: dict[str, Optional[str]]) -> str:
    """Return compatibility mode for the discovered binaries."""
    if binaries.get("ngfx_capture") or binaries.get("ngfx_replay"):
        return "split"
    if binaries.get("ngfx"):
        return "unified"
    return "missing"


def _extract_long_option(line: str) -> Optional[str]:
    """Extract the primary long option token from a help line."""
    match = re.search(r"(--[A-Za-z0-9-]+)", line)
    return match.group(1) if match else None


def parse_unified_help(text: str) -> dict[str, Any]:
    """Parse `ngfx --help-all` output into structured metadata."""
    activities: list[str] = []
    platforms: list[str] = []
    general_options: list[str] = []
    activity_options: dict[str, list[str]] = {}
    current_section: Optional[str] = None
    current_activity: Optional[str] = None
    collecting: Optional[str] = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        if stripped == "General Options:":
            current_section = "general"
            current_activity = None
            collecting = None
            continue

        if stripped.endswith("activity options:"):
            current_section = "activity"
            current_activity = stripped[: -len(" activity options:")]
            activity_options.setdefault(current_activity, [])
            collecting = None
            continue

        if stripped.startswith("--") or stripped.startswith("-"):
            option = _extract_long_option(stripped)
            if option and current_section == "general":
                general_options.append(option)
                if option == "--activity":
                    collecting = "activities"
                elif option == "--platform":
                    collecting = "platforms"
                else:
                    collecting = None
            elif option and current_section == "activity" and current_activity:
                activity_options.setdefault(current_activity, []).append(option)
                collecting = None
            else:
                collecting = None
            continue

        if collecting == "activities":
            lowered = stripped.lower()
            if "should be one of" not in lowered and lowered not in {"of:", "one of:"}:
                activities.append(stripped)
            continue

        if collecting == "platforms":
            lowered = stripped.lower()
            if "should be one of" not in lowered and lowered not in {"of:", "one of:"}:
                platforms.append(stripped)
            continue

    return {
        "activities": _dedupe(activities),
        "platforms": _dedupe(platforms),
        "general_options": _dedupe(general_options),
        "activity_options": {
            key: _dedupe(values) for key, values in activity_options.items()
        },
    }


def parse_option_help(text: str) -> list[str]:
    """Extract long options from arbitrary CLI help output."""
    options: list[str] = []
    for raw_line in text.splitlines():
        option = _extract_long_option(raw_line.strip())
        if option:
            options.append(option)
    return _dedupe(options)


def _combined_output(result: dict[str, Any]) -> str:
    """Combine stdout and stderr for parsing."""
    stdout = result.get("stdout", "") or ""
    stderr = result.get("stderr", "") or ""
    return "\n".join(part for part in (stdout, stderr) if part)


def run_command(
    args: Sequence[str],
    *,
    cwd: Optional[str] = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run a subprocess and normalize the result."""
    try:
        proc = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "command": _command_string(args),
        }
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "command": _command_string(args),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "command": _command_string(args),
        }


def _extract_version_from_text(text: str) -> Optional[str]:
    """Extract a version string from CLI output."""
    match = re.search(r"(\d{4}\.\d+(?:\.\d+)?)", text)
    if match:
        return match.group(1)
    return None


def _extract_version_from_path(path: str) -> Optional[str]:
    """Extract a version-like token from the installation path."""
    return _extract_version_from_text(path)


def _version_sort_key(version: Optional[str]) -> tuple[int, ...]:
    """Convert a dotted version string into a sortable tuple."""
    if not version:
        return tuple()
    parts: list[int] = []
    for token in version.split("."):
        try:
            parts.append(int(token))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def get_version(binaries: dict[str, Optional[str]]) -> Optional[str]:
    """Best-effort version detection from CLI output or path."""
    preferred = binaries.get("ngfx") or binaries.get("ngfx_capture") or binaries.get("ngfx_replay")
    if not preferred:
        return None
    result = run_command([preferred, "--version"], timeout=10)
    text = _combined_output(result)
    return _extract_version_from_text(text) or _extract_version_from_path(preferred)


def _primary_executable(binaries: dict[str, Optional[str]]) -> Optional[str]:
    """Choose the preferred executable path to display."""
    return binaries.get("ngfx") or binaries.get("ngfx_capture") or binaries.get("ngfx_replay")


def probe_installation(nsight_path: Optional[str] = None) -> dict[str, Any]:
    """Return an installation and capability report."""
    discovered = discover_binaries(nsight_path=nsight_path)
    binaries = discovered["binaries"]
    mode = detect_tool_mode(binaries)
    version = get_version(binaries)

    help_metadata = {
        "activities": [],
        "platforms": [],
        "general_options": [],
        "activity_options": {},
    }
    if binaries.get("ngfx"):
        help_result = run_command([binaries["ngfx"], "--help-all"], timeout=15)
        help_metadata.update(parse_unified_help(_combined_output(help_result)))

    capture_options: list[str] = []
    if binaries.get("ngfx_capture"):
        capture_help = run_command([binaries["ngfx_capture"], "--help"], timeout=15)
        capture_options = parse_option_help(_combined_output(capture_help))

    replay_options: list[str] = []
    if binaries.get("ngfx_replay"):
        replay_help = run_command([binaries["ngfx_replay"], "--help"], timeout=15)
        replay_options = parse_option_help(_combined_output(replay_help))

    warnings: list[str] = []
    host_platform = platform.system()
    if host_platform != "Windows":
        warnings.append(
            "V1 is only verified on Windows-hosted Nsight Graphics installations."
        )
    if mode == "missing":
        warnings.append(INSTALL_INSTRUCTIONS)
    if mode == "split" and not binaries.get("ngfx"):
        warnings.append(
            "Split capture/replay tools were found without ngfx.exe; launch, attach, "
            "GPU Trace, and C++ Capture helpers may be unavailable."
        )

    return {
        "ok": _primary_executable(binaries) is not None,
        "tool_mode": mode,
        "compatibility_mode": mode,
        "resolved_executable": _primary_executable(binaries),
        "version": version,
        "host_platform": host_platform,
        "verified_host": host_platform == "Windows",
        "supported_activities": help_metadata["activities"],
        "supported_platforms": help_metadata["platforms"],
        "general_options": help_metadata["general_options"],
        "activity_options": help_metadata["activity_options"],
        "split_binaries_present": {
            "ngfx_capture": bool(binaries.get("ngfx_capture")),
            "ngfx_replay": bool(binaries.get("ngfx_replay")),
        },
        "capture_options": capture_options,
        "replay_options": replay_options,
        "binaries": binaries,
        "search_roots": discovered["search_roots"],
        "env_override": discovered["env_override"],
        "cli_override": discovered.get("cli_override"),
        "effective_override": discovered.get("effective_override"),
        "warnings": warnings,
    }


def require_binary(binaries: dict[str, Optional[str]], key: str) -> str:
    """Require a specific executable to exist."""
    path = binaries.get(key)
    if not path:
        raise RuntimeError(INSTALL_INSTRUCTIONS)
    return path


def require_launch_target(*, project: Optional[str], exe: Optional[str]) -> None:
    """Require at least one launch target input."""
    if not project and not exe:
        raise ValueError("Specify --exe or set --project at the root level.")


def ensure_exactly_one(label: str, flags: dict[str, bool]) -> str:
    """Validate that exactly one flag in the set is selected."""
    selected = [name for name, enabled in flags.items() if enabled]
    if len(selected) != 1:
        choices = ", ".join(flags.keys())
        raise ValueError(f"{label}: choose exactly one of {choices}.")
    return selected[0]


def ensure_at_most_one(label: str, flags: dict[str, bool]) -> Optional[str]:
    """Validate that zero or one flags are selected."""
    selected = [name for name, enabled in flags.items() if enabled]
    if len(selected) > 1:
        choices = ", ".join(flags.keys())
        raise ValueError(f"{label}: choose at most one of {choices}.")
    return selected[0] if selected else None


def format_env_values(envs: Sequence[str]) -> Optional[str]:
    """Format KEY=VALUE entries for ngfx.exe."""
    cleaned = [entry.strip() for entry in envs if entry and entry.strip()]
    if not cleaned:
        return None
    joined = "; ".join(cleaned)
    if not joined.endswith(";"):
        joined += ";"
    return joined


def format_program_args(args: Sequence[str]) -> Optional[str]:
    """Format target executable arguments."""
    cleaned = [entry for entry in args if entry]
    if not cleaned:
        return None
    return subprocess.list2cmdline(cleaned)


def build_unified_command(
    binaries: dict[str, Optional[str]],
    *,
    activity: Optional[str] = None,
    project: Optional[str] = None,
    output_dir: Optional[str] = None,
    hostname: Optional[str] = None,
    platform_name: Optional[str] = None,
    exe: Optional[str] = None,
    working_dir: Optional[str] = None,
    args: Sequence[str] = (),
    envs: Sequence[str] = (),
    attach_pid: Optional[int] = None,
    launch_detached: bool = False,
    extra_args: Sequence[str] = (),
) -> list[str]:
    """Build a command line for the unified ngfx.exe CLI."""
    ngfx = require_binary(binaries, "ngfx")
    command: list[str] = [ngfx]
    if hostname:
        command.extend(["--hostname", hostname])
    if project:
        command.extend(["--project", project])
    if output_dir:
        command.extend(["--output-dir", output_dir])
    if activity:
        command.extend(["--activity", activity])
    if platform_name:
        command.extend(["--platform", platform_name])
    if launch_detached:
        command.append("--launch-detached")
    if attach_pid is not None:
        command.extend(["--attach-pid", str(attach_pid)])
    if exe:
        command.extend(["--exe", exe])
    if working_dir:
        command.extend(["--dir", working_dir])
    formatted_args = format_program_args(args)
    if formatted_args:
        command.extend(["--args", formatted_args])
    formatted_env = format_env_values(envs)
    if formatted_env:
        command.extend(["--env", formatted_env])
    command.extend(extra_args)
    return command


def build_split_capture_command(
    binaries: dict[str, Optional[str]],
    *,
    exe: str,
    output_dir: Optional[str] = None,
    working_dir: Optional[str] = None,
    args: Sequence[str] = (),
    envs: Sequence[str] = (),
    wait_seconds: Optional[int] = None,
    wait_frames: Optional[int] = None,
    wait_hotkey: bool = False,
    frame_count: int = 1,
) -> list[str]:
    """Build a command line for the split ngfx-capture tool."""
    capture = require_binary(binaries, "ngfx_capture")
    command: list[str] = [capture, "--exe", exe, "--frame-count", str(frame_count)]
    if output_dir:
        command.extend(["--output-dir", output_dir])
    if working_dir:
        command.extend(["--working-dir", working_dir])
    formatted_args = format_program_args(args)
    if formatted_args:
        command.extend(["--args", formatted_args])
    formatted_env = format_env_values(envs)
    if formatted_env:
        command.extend(["--env", formatted_env])

    ensure_exactly_one(
        "frame trigger",
        {
            "wait_seconds": wait_seconds is not None,
            "wait_frames": wait_frames is not None,
            "wait_hotkey": wait_hotkey,
        },
    )
    if wait_seconds is not None:
        command.extend(["--capture-countdown-timer", str(wait_seconds * 1000)])
    elif wait_frames is not None:
        command.extend(["--capture-frame", str(wait_frames)])
    else:
        command.append("--capture-hotkey")
    return command


def default_output_dir() -> str:
    """Best-effort default output root used by the harness."""
    return str((Path.home() / "Documents" / "NVIDIA Nsight Graphics").resolve())


def activity_artifact_roots(activity: str, output_dir: Optional[str]) -> list[str]:
    """Return directories to scan for generated artifacts."""
    if output_dir:
        return [str(Path(output_dir).resolve())]

    base = Path(default_output_dir())
    roots = [str(base)]
    normalized = activity.lower()
    if normalized == "frame debugger":
        roots.insert(0, str(base / "GraphicsCaptures"))
    elif normalized == "gpu trace profiler":
        roots.append(str(base / "GPUTrace"))
    elif normalized == "generate c++ capture":
        roots.append(str(base / "CppCaptures"))
    return _dedupe(roots)


def snapshot_files(roots: Sequence[str]) -> dict[str, tuple[int, int]]:
    """Snapshot file mtimes and sizes under the roots."""
    snapshot: dict[str, tuple[int, int]] = {}
    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot[str(path.resolve())] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def diff_snapshots(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> list[dict[str, Any]]:
    """Return non-empty files that were created or updated."""
    artifacts: list[dict[str, Any]] = []
    for path, (mtime_ns, size) in sorted(after.items()):
        previous = before.get(path)
        if size <= 0:
            continue
        if previous is None or previous != (mtime_ns, size):
            artifacts.append(
                {
                    "path": path,
                    "size": size,
                    "mtime_ns": mtime_ns,
                }
            )
    return artifacts


def run_with_artifacts(
    args: Sequence[str],
    *,
    output_roots: Sequence[str],
    cwd: Optional[str] = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Run a command and discover artifacts under the supplied roots."""
    before = snapshot_files(output_roots)
    result = run_command(args, cwd=cwd, timeout=timeout)
    after = snapshot_files(output_roots)
    result["artifacts"] = diff_snapshots(before, after)
    result["artifact_count"] = len(result["artifacts"])
    return result
