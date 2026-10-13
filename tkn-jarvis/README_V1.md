# JARVIS V1: command foundation

Date: 2026-10-13 (Asia/Bangkok).

Step 3 was closed after native Windows smoke and full `cargo xtask ci` passed. Rollback commit: [`2416ae2a98c1109fd26c9778d9623eab9a79b5a1`](https://github.com/kannthemaster/tkn-daw-v2/commit/2416ae2a98c1109fd26c9778d9623eab9a79b5a1), pushed to `develop/tkn-daw-v2-integration`. See `STEP3_CLOSEOUT.md` for the authorized test compatibility fixes and coverage limits.

**V1 is an additive command foundation following that published checkpoint. No LLM or speech provider is connected.** `jarvis_v1.py` translates a bounded Thai grammar into existing SoundCraft commands. The V0 adapter remains available. No production Rust changes were needed for V1.

## Commands

| Example instruction | Operation |
| --- | --- |
| `ตรวจสอบเซสชัน` | Inspect session |
| `ตั้งเสียง Kick ติดลบ 6 dB` | Absolute fader value |
| `สร้างแทร็ก stereo ชื่อ Voice` | Create one stereo audio track (`mono` also supported) |
| `เปลี่ยนชื่อแทร็ก Voice เป็น Lead Vox` | Rename a uniquely resolved track |
| `ปิดเสียงแทร็ก Lead Vox` / `เปิดเสียงแทร็ก Lead Vox` | Set mute on/off |
| `เพิ่ม EQ แทร็ก Lead Vox ช่อง a` | Add built-in EQ 1-Band to an empty slot |
| `ตั้ง EQ แทร็ก Lead Vox ช่อง a gain -3` | Set EQ gain in dB |
| `ตั้ง EQ แทร็ก Lead Vox ช่อง a freq 1200` | Set EQ frequency in Hz |
| `เพิ่ม Compressor แทร็ก Lead Vox ช่อง b` | Add built-in Compressor/Limiter |
| `ตั้ง Compressor แทร็ก Lead Vox ช่อง b threshold -18` | Set compressor threshold in dB |
| `ตั้ง Compressor แทร็ก Lead Vox ช่อง b ratio 6` | Set compressor ratio |
| `ย้อนกลับ` / `ทำซ้ำ` | SoundCraft Undo / Redo |

Slots are `a` through `j`. EQ supports `freq`, `gain`, `q`, `output_gain`; compressor supports `threshold`, `ratio`, `attack`, `release`, `knee`, `makeup`, `mix`. The parser enforces the built-in parameter ranges from this SoundCraft source. Unsupported commands, out-of-range values, arbitrary engine commands and track deletion are rejected.

## Run

Start SoundCraft on a disposable demo, with an isolated settings directory if appropriate:

```powershell
Set-Location 'C:\TKN DAW\work\tkn-daw-v2'
.\target\debug\soundcraft.exe --demo --no-audio --control 7801
```

In a second shell, preview first:

```powershell
py -3 tkn-jarvis/jarvis_v1.py 'สร้างแทร็ก stereo ชื่อ Voice'
```

After reviewing the displayed intent, explicitly apply it:

```powershell
py -3 tkn-jarvis/jarvis_v1.py 'สร้างแทร็ก stereo ชื่อ Voice' --apply --port 7801
py -3 tkn-jarvis/jarvis_v1.py 'เพิ่ม EQ แทร็ก Voice ช่อง a' --apply --port 7801
py -3 tkn-jarvis/jarvis_v1.py 'ตั้ง EQ แทร็ก Voice ช่อง a gain -3' --apply --port 7801
py -3 tkn-jarvis/jarvis_v1.py 'ย้อนกลับ' --apply --port 7801
```

Dry-run is offline: it never connects and does not prove that the target track/slot currently exists. Apply first inspects the full session, resolves names to track IDs, rejects duplicate names and occupied insert slots, checks effect identity, and checks history availability. It then dispatches one command and inspects again. Track/effect/fader values are checked against the requested result; history operations require the engine's `undone`/`redone` confirmation and include the inspected outcome. A no-op history entry can legitimately retain the same document state.

This is not a transaction or automatic rollback. Concurrent session edits between inspection and execution are not prevented. Existing SoundCraft group semantics remain in effect. The before/after snapshots expose what happened; an error after a write does not imply that the write was reversed.

## Validation

- **34/34 Python tests pass**: 22 V0/transport tests plus 12 V1 tests.
- **Windows V1 live demo smoke passes, exit 0.** It runs the actual V1 CLI as subprocesses against the desktop control protocol with audio disabled.
- Live acceptance creates a new stereo track, proves offline preview does not insert an effect, adds EQ and compressor, asserts EQ gain -3 dB, threshold -18 dB and ratio 6, rejects occupied/wrong-effect slots without state changes, renames and mutes the track, asserts Undo/Redo mute states, and undoes all eight writes. The final demo tracks exactly match the original snapshot.
- **Full `cargo xtask ci` passes against this V1 foundation on Windows, exit 0**: fmt, clippy, workspace tests, assets, layers and WASM. The WASM check retains the existing nonfatal `CaptureStates` dead-code warning.
- Evidence from the 2026-10-13 rerun: local `work/python-v1-foundation.log`, `work/full-ci-v1-foundation.log`, `work/v1-smoke/summary.json`, command logs and `initial.json`, `modified.json`, `restored.json`. Generated evidence is not committed.
- This foundation is the next checkpoint on `develop/tkn-daw-v2-integration`; identify its revision with `git log -1 --oneline -- tkn-jarvis/jarvis_v1.py`. See `V1_FOUNDATION_CLOSEOUT.md` for scope and acceptance results.

Re-run the checks:

```powershell
py -3 -m unittest discover -s tkn-jarvis -p 'test_*.py' -v
py -3 tkn-jarvis/windows_v1_smoke.py
cargo xtask ci
```

The V1 smoke runner always launches its own isolated demo, discovers its free control port, and terminates only that process. It cannot attach to an existing user session.

## Next increment

Choose the model/provider and connect AI-generated intent through a constrained parser/schema with the same preview/apply boundary. This foundation demonstrates command execution and verification, not AI inference or audio processing quality. Physical playback, recording, latency and installed VST3/CLAP acceptance remain separate tests.
