# Step 3 closeout: Windows validation and full CI

Date: 2026-10-13 (Asia/Bangkok). Branch: `develop/tkn-daw-v2-integration`.

**Full `cargo xtask ci` passed on native Windows with exit 0.** The final summary is `ok fmt`, `ok clippy`, `ok test`, `ok assets`, `ok layers`, `ok wasm`. The focused Python suite passes 22/22. The preceding Windows desktop/CLI demo smoke passes with exit 0, including a verified Kick change from -3 to -6 dB, unchanged other faders, and restoration of the initial state.

This closes the previously missing full-CI gate in `STEP3_WINDOWS_FOLLOWUP.md`; that file records the earlier smoke-validation snapshot. The Step 3 closeout commit is the rollback point before JARVIS V1 development. Local logs under `work/` and build products under `target/` are not committed.

## Reviewed changes

- `jarvis.py`: strict response-object, ID and boolean-success validation; verified fader state after an applied volume command. Failed verification returns an error rather than claiming success; it is not automatic rollback.
- `test_transport.py`: real localhost fixture transport, parser/CLI error handling and post-write regression checks. Fixtures are distinguished from live integration evidence.
- `windows_smoke.py`: reproducible Windows source build, metadata discovery, headless CLI checks and isolated live desktop demo control.
- Four pre-existing test compatibility issues were corrected with explicit user permission, without modifying production Rust behavior:
  1. The Unix symlink/system-library rejection test is compiled only on Unix.
  2. The session missing-file assertion compares paths rather than mixed slash/backslash spellings.
  3. Two fixture bus flags are converted to the binding's platform-specific field type.
  4. The process-shutdown fixture asserts the platform-specific result: MSVC Windows DLL callbacks produce exit 0; the Unix late-state reproduction retains exit 3 and its error-message assertion. The explicit-shutdown success assertion remains on every platform.

The final CI run exercised all repository gates without suppressing native warnings or skipping failed tests through runner flags. The WASM check emits an existing nonfatal `CaptureStates` dead-code warning; its gate succeeds. The initial CI failures and final successful log are retained locally as evidence.

## Limits

The Windows late-state fixture does **not** reproduce the Unix negative teardown-order scenario. This is a fixture coverage limitation, not proof that every Windows VST3 shutdown path is safe. Microsoft's [atexit documentation](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/atexit) describes DLL callbacks running during DLL detach; the fixture's observed platform behavior is consistent with that distinction.

No physical speaker playback, recording, interface latency, installed third-party VST3/CLAP acceptance, release packaging, or broad DAW readiness is established by these checks. Tests with synthetic plugin fixtures must not be described as real-plugin acceptance. No V1 tracked code or main branch was changed.

## Reproduce

Use Rust 1.95+ (tested: 1.99.0), MSVC C++ Build Tools, Windows SDK, and the `wasm32-unknown-unknown` Rust target. In Developer PowerShell for VS 2022:

```powershell
Set-Location 'C:\TKN DAW\work\tkn-daw-v2'
py -3 -m unittest discover -s tkn-jarvis -p 'test_*.py' -v
cargo xtask ci
py -3 tkn-jarvis/windows_smoke.py --build
```

Keep the closeout commit as the rollback point. The next increment is an additive V1 command layer for built-in EQ/compressor, track management, and Undo/Redo, with dry-run, preflight inspection and verified results. Connecting an AI model is a separate integration decision; a deterministic command layer alone must not be labeled an LLM.
