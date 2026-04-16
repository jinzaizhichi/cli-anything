# cli-anything-nsight-graphics

Windows-first CLI harness for the official [NVIDIA Nsight Graphics](https://developer.nvidia.com/nsight-graphics) tools.

This package focuses on **orchestrating** Nsight Graphics activities from the
terminal:

- installation and capability probing
- detached launch and PID attach
- Frame Debugger capture
- GPU Trace capture, auto-export, and summary generation
- Generate C++ Capture

It does not provide RenderDoc-style offline inspection of shaders, pipeline
state, textures, or resources.

## Installation

```bash
cd nsight-graphics/agent-harness
pip install -e .
```

## Prerequisites

- Windows host recommended and verified for v1
- NVIDIA Nsight Graphics installed
- One of:
  - `ngfx.exe`
  - or newer split tools such as `ngfx-capture` / `ngfx-replay`

If Nsight Graphics is not on `PATH`, set:

```powershell
$env:NSIGHT_GRAPHICS_PATH = "C:\Program Files\NVIDIA Corporation\Nsight Graphics 2023.3.2\host\windows-desktop-nomad-x64"
```

You may also point `NSIGHT_GRAPHICS_PATH` directly at `ngfx.exe`.

## Quick Start

### Inspect the installation

```bash
cli-anything-nsight-graphics --json doctor info
cli-anything-nsight-graphics --json doctor versions
```

### Choose a specific installed version

```bash
cli-anything-nsight-graphics ^
  --nsight-path "C:\Program Files\NVIDIA Corporation\Nsight Graphics 2024.2\host\windows-desktop-nomad-x64" ^
  --json doctor info
```

### Launch a target detached

```bash
cli-anything-nsight-graphics launch detached ^
  --activity "Frame Debugger" ^
  --exe "C:\VulkanSDK\1.3.290.0\Bin\vkcube.exe"
```

### Attach to a running PID

```bash
cli-anything-nsight-graphics launch attach ^
  --activity "Frame Debugger" ^
  --pid 12345
```

### Capture a frame

```bash
cli-anything-nsight-graphics --output-dir D:\captures frame capture ^
  --exe "C:\VulkanSDK\1.3.290.0\Bin\vkcube.exe" ^
  --wait-frames 10
```

### Collect a GPU trace

```bash
cli-anything-nsight-graphics --output-dir D:\traces gpu-trace capture ^
  --exe "C:\VulkanSDK\1.3.290.0\Bin\vkcube.exe" ^
  --start-after-ms 1000 ^
  --limit-to-frames 1 ^
  --auto-export ^
  --summarize
```

### Summarize an existing GPU Trace export

```bash
cli-anything-nsight-graphics gpu-trace summarize ^
  --input-dir D:\traces
```

`--input-dir` may point either at a specific exported trace directory or at a
parent output root that contains multiple exports. When multiple complete GPU
Trace exports are present, the CLI summarizes the newest complete export
directory so stale tables are not mixed into the result.

### Generate a C++ capture

```bash
cli-anything-nsight-graphics --output-dir D:\cpp cpp capture ^
  --exe "C:\VulkanSDK\1.3.290.0\Bin\vkcube.exe" ^
  --wait-seconds 5
```

## Command Reference

### Global Options

| Option | Description |
|--------|-------------|
| `--json` | JSON output mode |
| `--debug` | Include traceback details in errors |
| `--nsight-path` | Explicit install directory or executable to use when multiple Nsight versions are installed |
| `--project` | Nsight Graphics project file |
| `--output-dir` | Output directory for captures or exported artifacts |
| `--hostname` | Remote host for Nsight launch/attach |
| `--platform` | Target platform string passed to Nsight |

### Command Groups

| Group | Command | Purpose |
|-------|---------|---------|
| `doctor` | `info` | Probe installed binaries, version, activities, compatibility mode |
| `doctor` | `versions` | List detected Nsight Graphics installs and show which one is selected |
| `launch` | `detached` | Launch a target under Nsight without blocking the CLI |
| `launch` | `attach` | Attach Nsight to a running PID |
| `frame` | `capture` | Trigger a Frame Debugger capture |
| `gpu-trace` | `capture` | Trigger a GPU Trace capture and optionally summarize the exported result |
| `gpu-trace` | `summarize` | Summarize an existing GPU Trace export directory |
| `cpp` | `capture` | Trigger Generate C++ Capture |

## JSON Output

All commands support `--json`. Results include normalized fields such as:

- `ok`
- `returncode`
- `command`
- `stdout`
- `stderr`
- `tool_mode`

Capture-producing commands also include:

- `activity`
- `output_dir`
- `artifacts`

When `gpu-trace capture --summarize` is used, the result also includes:

- `summary.output_dir`
- `summary.search_root`
- `summary.frame_time_ms`
- `summary.fps_estimate`
- `summary.metrics`
- `summary.top_events`
- `summary.highlights`

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `NSIGHT_GRAPHICS_PATH` | Override executable discovery |
| `NSIGHT_GRAPHICS_TEST_EXE` | E2E target executable |
| `NSIGHT_GRAPHICS_TEST_ARGS` | Optional E2E target arguments |
| `NSIGHT_GRAPHICS_TEST_WORKDIR` | Optional E2E working directory |

## E2E Test Prerequisites

The E2E suite assumes:

- Nsight Graphics is installed and discoverable
- `NSIGHT_GRAPHICS_TEST_EXE` points to a graphics workload that Nsight can
  launch or capture
- optional args/workdir are provided if the test target requires them

Typical examples include `vkcube.exe`, game samples, or internal engine demos.

## Multiple Installations

If you have several Nsight Graphics versions installed, the CLI chooses in this order:

1. `--nsight-path`
2. `NSIGHT_GRAPHICS_PATH`
3. `PATH`
4. default Windows install directories

Use `doctor versions` to inspect what is installed and which executable is currently selected.

Entries marked `registered-only` came from the Windows uninstall registry but do
not currently have a discovered Nsight executable path. They are useful for
diagnosis, but not enough by themselves to launch captures. The harness also
scans standard `Program Files` locations on all fixed Windows drives, so
non-`C:` installs can still be promoted to normal filesystem-backed entries.

## One-Step GPU Trace Triage

If you want the harness to behave like a single-shot performance assistant,
prefer this pattern:

```bash
cli-anything-nsight-graphics --output-dir D:\traces gpu-trace capture ^
  --exe "C:\Path\To\App.exe" ^
  --start-after-hotkey ^
  --limit-to-frames 1 ^
  --auto-export ^
  --summarize
```

That gives you:

- the `.ngfx-gputrace` artifact
- exported `FRAME.xls`, `GPUTRACE_FRAME.xls`, and `D3DPERF_EVENTS.xls`
- a parsed summary from the newest complete export directory, with frame time,
  estimated FPS, selected counters, and top GPU events

## Human + AI Workflow

When a human is directing an AI agent, the most effective requests usually specify:

1. which Nsight version to use
2. the target executable
3. the working directory
4. the target arguments
5. the activity to run
6. the trigger condition
7. the artifact or summary to return

Example:

```text
Use Nsight Graphics 2026.1.0 for this executable.
Wait for me to press F11.
After GPU Trace finishes, give me:
- frame time
- estimated FPS
- draw count and dispatch count
- top 10 GPU events
- short diagnosis of the likely bottleneck
Program: D:/path/to/App.exe
Working dir: D:/path/to
Args: "D:\path\project.uproject" -dx12 -log -newconsole
```
