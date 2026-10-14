# Step 7.2 — JARVIS inside SoundCraft

Open **Window > JARVIS**. It is closed in a fresh profile. The existing docking
system supports a right-hand panel or a floating panel, with separate Edit/Mix
arrangements. Closing it preserves the layout and the current in-memory chat.
Chat text, proposals and confirmation tokens are never saved in session files or
UI preferences; history is bounded and lasts only for this app process.

## Development setup

Use installed Python 3 and local Ollama with `gemma3:4b` on `127.0.0.1:11434`.
There is no microphone or voice activation. Windows uses `py -3` to locate the
actual interpreter; a worker owns that interpreter directly so closing the
panel stops it. Python process startup, AI requests and sockets run off the UI
thread. The UI drains bounded channels without waiting for AI.

Ollama must already be running; the panel owns its Python worker, not the Ollama
server. With a normal Ollama installation, start `ollama serve` and check that
`ollama list` contains `gemma3:4b`. With the portable runtime used in Step 7.1,
run its `ollama.exe serve` with `OLLAMA_MODELS` pointing at that runtime's
existing `models` folder and `OLLAMA_NO_CLOUD=1`. Do not download another model
just to open the panel. Runtime and evidence paths are recorded in the closeout
report.

Optional settings for the SoundCraft process:

```powershell
$env:SOUNDCRAFT_JARVIS_PYTHON = 'C:\path\to\python.exe'
$env:SOUNDCRAFT_JARVIS_BRIDGE = 'D:\project\TKN DAW\tkn-daw-v2\tkn-jarvis\jarvis_bridge.py'
```

The default bridge path resolves to this development checkout. This is a
development build, not a packaged installer with bundled Python or Ollama.
No model is downloaded automatically by the panel. On Windows, Thai text uses
a runtime system-font fallback; fonts are not redistributed.

## Review and apply

1. Type an explicit supported command, for example `ลดแทร็ก Voice ลง 2 dB`.
2. Select **สร้าง Preview** and review every proposed change.
3. Select **ยืนยัน Apply…**. The confirmation dialog defaults to Cancel.
4. Deliberately select **ยืนยัน Apply** to run the displayed plan.
5. Wait for **Verify ผ่าน … ขั้นตอน**. An error does not mean changes were rolled
   back; some earlier steps may already have succeeded. Inspect the session
   before deciding what to do next.

Insert-slot numbers in Preview follow the engine: `0 = a`, `1 = b`, through
`9 = j`. Check both the effect and its target slot before confirming.

Volume, EQ/Compressor inserts and parameters, rename and mute use the existing
bounded Intent Engine. AI track creation and unrestricted DAW commands remain
unsupported. Missing information yields clarification without an Apply plan.

Editing the text, changing the document, or Cancel expires the preview. Each
write is checked again on the UI thread against the same document and the exact
ordered compiled plan; stable track IDs survive rename. Sidecar replies alone
cannot authorize an unconfirmed write. Confirmation is a trusted host/UI action,
not proof of a human encoded in JSON. See [BRIDGE_PROTOCOL.md](BRIDGE_PROTOCOL.md).

An ephemeral loopback endpoint starts only while JARVIS is enabled. It accepts
only inspection and the small command allowlist, with bounded requests. The
existing optional `--control` development endpoint retains its original powers;
it is separate from this confirmation-gated JARVIS endpoint.

Closing the panel during planning cancels it. Closing during Apply keeps the
worker until Apply/Verify reports a result; app close is also deferred while that
operation is active. Normal app exit signals and waits briefly for its owned
workers to stop. Retry after a runtime or model error creates a fresh preview.

While JARVIS is starting/planning/applying or its confirmation dialog is open,
background DAW keyboard shortcuts are suspended. This includes a hidden panel
waiting for Verify: Tab must not move the Edit insertion when panel focus is
lost. Normal shortcuts resume when that operation/dialog ends. Window/menu
controls remain available; an unrelated document edit still rejects the plan.
See [lifecycle follow-up](STEP72_LIFECYCLE_FOLLOWUP.md) for the reproduced cause,
Windows results and [repeatable acceptance](PANEL_LIFECYCLE_ACCEPTANCE.md).

## Disposable Demo acceptance

Build this checkout, then launch it with a separate profile:

```powershell
$env:SOUNDCRAFT_CONFIG_DIR = Join-Path $env:TEMP ('TKN-V2-demo-' + [guid]::NewGuid())
.\target\debug\soundcraft.exe --demo --no-audio --control 0
```

`--no-audio` intentionally disables audio output. For listening tests, launch
without that flag. Embedded-command acceptance does not establish physical
speaker, audio-interface, or microphone performance.

Test Preview/Cancel invariance, modal Cancel, confirmed Volume/EQ/Compressor,
Rename → Mute with overlapping track names, text/session invalidation, unavailable
Ollama/Python, closing the panel, floating/redocking, and reopening the saved
layout. Restore the disposable demo afterward. Voice Control remains preserved
and paused; there is no merge into `main` or TKN DAW V1 change in this work.
