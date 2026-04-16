# TEST.md – Nsight Graphics CLI Test Plan & Results

## Test Inventory Plan

- `test_core.py`: 32 unit tests planned
- `test_full_e2e.py`: 4 E2E tests planned

## Unit Test Plan

### `utils/nsight_graphics_backend.py`

- executable discovery from env override and install directories
- compatibility mode detection
- CLI override precedence via `--nsight-path`
- `ngfx --help-all` parsing for activities and options
- installation listing and version reporting
- Windows registry discovery for registered-only installs
- fixed-drive discovery for non-`C:` installs
- unified and split command construction
- artifact diffing behavior
- exported GPU Trace summary parsing
- newest-complete GPU Trace export selection when multiple exports share an output root

### `core/*.py`

- frame capture command routing
- split-mode fallback restrictions
- GPU Trace validation for trigger/limit options
- GPU Trace one-step summary behavior
- launch attach/detached wrapping

### `nsight_graphics_cli.py`

- root help
- help for `doctor`, `launch`, `frame`, `gpu-trace`, and `cpp`
- subprocess smoke test via `python -m`

## E2E Test Plan

Environment prerequisites:

- Nsight Graphics installed and discoverable
- `NSIGHT_GRAPHICS_TEST_EXE`
- optional `NSIGHT_GRAPHICS_TEST_ARGS`
- optional `NSIGHT_GRAPHICS_TEST_WORKDIR`

Scenarios:

1. `doctor info` returns installation metadata
2. `frame capture` produces one or more non-empty artifacts
3. `gpu-trace capture --auto-export` produces one or more non-empty artifacts
4. `cpp capture` produces one or more non-empty artifacts

## Running Tests

```bash
cd nsight-graphics/agent-harness
python -m pip install -e .
python -m pytest cli_anything/nsight_graphics/tests -v --tb=no
```

## Test Results

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.0.3, pluggy-1.6.0 -- C:\Users\aimidi\AppData\Local\Programs\Python\Python311\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\aimidi\.codex\worktrees\da29\CLI-Anything\nsight-graphics\agent-harness
collecting ... collected 36 items

cli_anything/nsight_graphics/tests/test_core.py::TestOutputAndErrors::test_output_json PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestOutputAndErrors::test_handle_error_debug PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_default_windows_install_dirs_prefers_higher_version PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_discover_binaries_from_env_dir PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_discover_binaries_prefers_cli_override PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_detect_tool_mode PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_list_installations_reports_versions PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_list_installations_includes_registry_only_entries PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_list_installations_merges_registry_metadata_into_filesystem_entry PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_list_installations_promotes_newer_drive_install PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestHelpParsing::test_parse_unified_help_extracts_activities_and_options PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_build_unified_command_formats_args_and_env PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_build_split_capture_command_maps_wait_seconds PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_diff_snapshots_reports_new_nonempty_files PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_gpu_trace_summary_from_export_dir PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_gpu_trace_summary_prefers_newest_complete_export_dir PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_frame_capture_uses_unified_ngfx PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_frame_capture_split_mode_rejects_perf_exports PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_gpu_trace_requires_arch_for_metric_set PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_launch_attach_returns_unified_result PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_cpp_capture_sets_activity PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_gpu_trace_capture_with_summary PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_root_help PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_nsight_path_is_forwarded_to_doctor PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args0-info] PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args1-versions] PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args2-detached] PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args3-capture] PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args4-capture] PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args5-summarize] PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args6-capture] PASSED
cli_anything/nsight_graphics/tests/test_core.py::TestCLISubprocess::test_cli_help_subprocess PASSED
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestDoctorE2E::test_doctor_info PASSED
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestTargetedE2E::test_frame_capture SKIPPED
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestTargetedE2E::test_gpu_trace_capture SKIPPED
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestTargetedE2E::test_cpp_capture SKIPPED

======================== 33 passed, 3 skipped in 1.86s ========================
```

## Summary Statistics

- Total tests collected: 36
- Passed: 33
- Skipped: 3
- Pass rate for executed tests: 100%

## Coverage Notes

- `doctor info` E2E passed against the local Nsight Graphics installation.
- Target-dependent E2E scenarios are implemented but currently skipped until
  `NSIGHT_GRAPHICS_TEST_EXE` (and optional args/workdir) are provided.
- GPU Trace summary coverage now includes the case where an output root contains
  multiple export directories; the newest complete export is selected.
