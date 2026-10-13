# JARVIS V1 Foundation acceptance

Validated on 2026-10-13 (Asia/Bangkok) on native Windows x64 with Rust 1.99.0, MSVC and Python 3.10.11.

Development branch: `develop/tkn-daw-v2-integration`.
Parent checkpoint: `2416ae2a98c1109fd26c9778d9623eab9a79b5a1` (Step 3 closeout).

## Scope

Additive Python adapter, regression tests, Windows demo runner and documentation. The foundation supports bounded Thai commands for built-in EQ and compressor, track creation/rename/mute, existing faders and inspection, and Undo/Redo. Preview remains offline; Apply resolves and checks the current session before dispatch; Verify inspects the resulting state. No existing tracked source files are changed by this increment.

## Acceptance evidence

| Check | Result | Local evidence |
| --- | --- | --- |
| `cargo xtask ci` | Exit 0; fmt, clippy, test, assets, layers, wasm all pass | `work/full-ci-v1-foundation.log` |
| Python discovery `test_*.py` | Exit 0; 34 tests pass (22 V0/transport + 12 V1) | `work/python-v1-foundation.log` |
| `windows_v1_smoke.py` | Exit 0; PASS; 21 command checks | `work/v1-smoke/summary.json` and command logs |
| Demo restoration | Final tracks exactly equal initial tracks after Undo | `work/v1-smoke/initial.json`, `restored.json` |

The live runner exercises actual CLI subprocesses and the desktop TCP control endpoint on its own isolated demo. It verifies built-in effect values, rejected commands without mutation, track rename/mute, Undo/Redo and restoration. Audio is disabled. Generated logs and profiles remain local and are excluded from the checkpoint.

The WASM check emits the existing nonfatal `CaptureStates` dead-code warning in `crates/playback/src/lib.rs`; all required gates still pass.

## Coverage limits and next work

No LLM or speech provider is connected. Free-form Thai intent recognition, voice control, physical playback/recording, audio-interface latency and installed third-party VST3/CLAP acceptance have not been tested. Built-in effect control and repository plugin-fixture tests do not establish hardware or installed-plugin acceptance.

Apply is not an atomic transaction, does not prevent concurrent session edits and does not automatically roll back a failed verification. SoundCraft's existing group/history semantics apply.

Next: select an AI provider and constrain generated intent to the supported schema and command allowlist while retaining Preview → Apply → Verify. Plan voice and physical audio/plugin acceptance separately. Keep this foundation checkpoint available before those additions; do not merge into `main` as part of this closeout.
