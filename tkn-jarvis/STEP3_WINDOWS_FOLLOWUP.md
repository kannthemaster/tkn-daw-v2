# Step 3 Windows follow-up — TKN DAW V2 / JARVIS V0

Date: 2026-10-13, Asia/Bangkok.

**Result: Step 3 passed on native Windows. The final `windows_smoke.py --build` run returned exit 0 at approximately 19:23 Bangkok time.**

Repository: `kannthemaster/tkn-daw-v2`; branch: `develop/tkn-daw-v2-integration`.
Base source: `041bec36b1f0555237804d7f9140c83ea0f13ad1` plus the authorized Python adapter fix and additive test files.

## Environment prepared

- Native Windows 11 Home Single Language, version 10.0.26200, x64.
- Python 3.10.11.
- Installed Rustup 1.29.1, stable Rust 1.99.0 and Cargo 1.99.0, target `x86_64-pc-windows-msvc`.
- Installed Visual Studio 2022 Build Tools 17.14.41 with the C++ workload and recommended components, including MSVC 14.44.35207 and Windows SDK 10.0.26100.0.
- Installer completed successfully and Visual Studio reports no reboot required.
- Dependencies fetched with the existing Cargo.lock. No Rust source, Cargo manifest, or lockfile was changed.

## Authorized JARVIS fixes

Only existing `tkn-jarvis/jarvis.py` was edited:

1. Reject JSON responses that are not objects with a controlled RuntimeError.
2. Require an integer response ID, rejecting Python's boolean/integer equality corner case.
3. Require a boolean `ok` field; a string `"false"` or integer `1` cannot signal success.
4. After an applied absolute fader change, require exactly one matching track in the inspected session and a finite numeric `volume_db` equal to the requested value within 0.0001 dB. A missing/ambiguous track, invalid value, or mismatch returns exit 1. This detects a bad outcome but does not roll back writes or provide transaction guarantees.

The initial regression run against the old adapter failed with 12 failed subcases and 3 errors (19 tests total). After fixing the adapter and adding CLI/float checks, **22/22 Python tests pass**. Evidence: `work/regression-before.log` and `work/regression-after.log`.

Added checks exercise malformed responses through real localhost fixture sockets, reject non-boolean success flags and boolean IDs, validate the CLI error path without traceback, and detect incorrect post-command state. Additional tests cover missing tracks, malformed inspection data, duplicate names, NaN, boolean fader values, and Rust float precision. Fixture success is separate from live integration success.

## Windows build and integration

Final results are recorded in `work/windows-smoke/summary.json`; CLI and desktop evidence is in the same directory.

| Validation | Result | Evidence |
| --- | --- | --- |
| Python parser, TCP and regression tests | PASS, 22/22 | `python-tests.log` |
| Native MSVC debug build, both packages | PASS | `windows-build.log`; initial full build completed in 5m 37s |
| CLI command schema and headless demo | PASS | `command-metadata.log`, `cli-demo-before.log`, `cli-demo-after.log` |
| Live JARVIS session inspection | PASS | `jarvis-inspect.log` |
| Dry-run without mixer changes | PASS | `jarvis-preview.log` plus independent inspection assertion |
| Live absolute mixer write | PASS | `jarvis-apply.log`, `live-before.json`, `live-after.json` |
| Relative command rejected | PASS | `jarvis-relative-rejected.log` |
| Nonexistent track rejected | PASS | `jarvis-missing-track.log`; desktop warning is intentional |
| CLI control snapshot matches JARVIS | PASS | `cli-control-inspect.log` |
| Original demo fader restored | PASS | Independent post-restore inspection assertion before final PASS |

The live demo contains nine tracks. Kick changed from **-3 dB to -6 dB**, while Snare, Hats, Bass, Pad, Keys, Lead, Verb, and Master 1 retained their original values. The runner restored Kick to -3 dB and verified that all faders matched the original snapshot. Control port 52077 was assigned dynamically. This used real SoundCraft desktop and CLI binaries built from this checkout, rather than fixture peers.

Binary SHA-256:

- `soundcraft.exe`: `EED3A0F9659C492247CA826041F91910D3481A9EEE4C3DB7D41524C219EFB6AA`
- `soundcraft-cli.exe`: `7179A477295282E55689BC0922F440916532F8F70B8F4E01C09F2E77AB7A012A`

Audio output was disabled. These checks validate mixer document changes and the live control protocol; they do not validate audible output, hardware latency, or recording.

Two early build attempts occurred while installation was still in progress (missing linker, then missing SDK `kernel32.lib`). After the installer completed and the developer environment was initialized, the full build and final smoke run passed. These transient installation errors required no Rust source changes.

## Reproduce

After reopening PowerShell to refresh Rust's PATH:

```powershell
Set-Location 'C:\TKN DAW\work\tkn-daw-v2'
py -3 tkn-jarvis/windows_smoke.py --build
$LASTEXITCODE
```

If MSVC is not discovered from a plain shell, use Developer PowerShell for VS 2022, or initialize its environment in the current shell:

```powershell
Import-Module 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\Microsoft.VisualStudio.DevShell.dll'
Enter-VsDevShell -VsInstallPath 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools' -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
py -3 tkn-jarvis/windows_smoke.py --build
```

The smoke runner starts its own disposable demo with audio output disabled, a dynamically assigned localhost control port, and an isolated settings profile. It compares the demo's faders before/after JARVIS and CLI commands, rejects unsupported/missing-track operations, restores the original Kick fader, and terminates only its own process. No recording or input monitoring is enabled.

## Scope

No V1 tracked files changed. No merge into main, push, or PR. No commit was created: full repository `cargo xtask ci` is separate from these focused Step 3 checks and was not run. No JARVIS V1, speech, or LLM features were added. Audio playback, recording, plugin hosting, release installers, and broad DAW readiness are outside this smoke test.

## Next step

Step 3's Windows build, mixer-control, and adapter-regression gate is now satisfied. Review the local changes; run the repository's full CI gate before committing. JARVIS V1 can then be scoped separately around explicit command previews, verified state changes, and optional speech/AI interpretation.
