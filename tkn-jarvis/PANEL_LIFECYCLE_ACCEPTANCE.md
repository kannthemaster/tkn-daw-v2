# JARVIS close-during-Apply acceptance

Use an owned **disposable** demo, local installed Python/Ollama `gemma3:4b`,
and this checkout's Windows build. Never use an existing project/control port.
The fixture below pauses for 12 seconds **after the first real reviewed write**.
It does not mock AI, confirmation, document checks, engine dispatch or Verify.
Normal application startup never selects this fixture.

Keep generated profiles, screenshots and audio **outside the repository**;
`cargo xtask assets` intentionally scans untracked assets too. Preserve failed
attempts in separate evidence directories rather than overwriting them.

```powershell
$demoRoot = Join-Path $env:TEMP ('TKN-panel-lifecycle-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $demoRoot | Out-Null
$env:SOUNDCRAFT_CONFIG_DIR = Join-Path $demoRoot 'profile'
$env:SOUNDCRAFT_JARVIS_PYTHON = 'C:\path\to\python.exe'
$env:SOUNDCRAFT_JARVIS_BRIDGE = (Resolve-Path 'tkn-jarvis/tests/fixtures/delayed_panel_bridge.py').Path
$env:TKN_TEST_WRITE_MARKER = Join-Path $demoRoot 'written.json'
.\target\debug\soundcraft.exe --demo --no-audio --control 0
```

1. Keep Kick selected and record the initial stopped position `443072` and full
   session through the printed development control port (`session.inspect`).
2. Window > JARVIS; type `ลดแทร็ก Kick ลง 2 dB`. Create Preview and confirm
   the snapshot/tracks are unchanged; review the compiled target and -5 dB fader.
3. Open the confirmation dialog; its default remains Cancel. Deliberately
   confirm Apply. Only after a **fresh** `written.json` appears and UI inspection
   says Applying, close the panel, press Tab and request app close. Perform these
   within the 12-second pause. Never count a maneuver after Verify as this case.
4. Inspect while hidden: the worker remains present, position stays `443072`,
   and app close is deferred. Wait for Verify 1 step, unchanged position, correct
   -5 dB fader and sidecar=false. Reopen to see the retained verified history.
5. Undo only this demo's change and compare all initial tracks, then exit. Allow
   its owned interpreter/listener to stop; never kill unrelated Python/Ollama.
6. Repeat in a fresh process/profile with `เปลี่ยนชื่อ Kick เป็น Test Kick แล้วปิดเสียง Test Kick`.
   Float/close the panel after the first write; require Verify **2** steps, both
   reviewed commands using Kick's original stable ID, and unchanged other tracks.
   Undo both writes and compare the original tracks. Preserve floating layout.
7. Negative test in another fresh demo: after a confirmed write, close the panel
   and deliberately run `transport.locate {"at":443077}` through the separate
   development endpoint. Require a session-change rejection and possible-partial-
   write warning, never Verify success. Restore only the owned fixture.

The development endpoint is for inspection, fixture setup/restoration and UI
events; confirmed JARVIS writes use its separate gated private endpoint. Do not
send a bridge Apply directly or bypass the native confirmation dialog.

Regression: `cargo test -p soundcraft-ui-egui --test jarvis_workflow -- --test-threads=1`.
Before commit: `cargo xtask ci` with `RUST_TEST_THREADS=1` (the earlier closeout
records a process-wide palette test race), plus the Python suite. Physical
audio, mic/voice, interface latency and real plugin validation remain separate.
