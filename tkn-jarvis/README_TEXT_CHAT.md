# Step 7 — JARVIS Text Chat UI

Thai typed commands are the primary JARVIS interface. Voice development is
paused at the user's request; existing voice files and real microphone evidence
are preserved. No wake word, listening, or STT is used by text_chat.py.

This additive Tk desktop window runs alongside SoundCraft. It is not embedded
inside the Rust/egui DAW window: that integration requires authorization to edit
existing files. Existing Intent Engine, normalization, command allowlist, local
Ollama restrictions and Rust production files remain unchanged.

## Start

Double-click `Start-Text-Chat.cmd`, or from the tkn-jarvis directory:

```powershell
py -3 -B .\text_chat.py
```

From the repository root:

```powershell
py -3 -B .\tkn-jarvis\text_chat.py --port 7801 --model gemma3:4b
```

Requires Python with Tk (tested here with Python 3.14 / Tk 9.0). No voice
environment, faster-whisper or extra packages are required.
Before generating a Preview, run an installed local Ollama with gemma3:4b and
SoundCraft with a control port matching --port. Start acceptance on an isolated,
disposable audio-disabled demo rather than a user session. See README_INTENT.md.
The checkout has no built SoundCraft executable and Ollama was not listening
when this UI was prepared; no automatic model download or engine launch occurs.

## Use

1. Type a Thai instruction using actual session track names, e.g.
   `ลดแทร็ก Voice ลง 2 dB แล้วใส่ Compressor`.
2. Click สร้าง Preview. Read the clarification or proposed track/action/value/
   effect slot. Relative faders show their resolved absolute value. Concrete
   commands are also displayed; the AI summary is a proposal, not verification.
3. Click ยืนยัน Apply… only after reviewing. A second modal confirmation defaults
   to No. Cancelling this confirmation discards the Preview without writes.
4. After confirmation, the exact displayed artifact's confirmation hash is passed
   to the original apply_preview, which checks staleness and verifies each write.
   Only verified completion is shown as success. Failure may mean earlier steps
   or the current step wrote; there is no automatic rollback.

Editing input invalidates the pending Preview. Plans are held in memory,
consumed on an Apply attempt, and cannot be applied twice. During inference or
Apply, editing and action buttons are disabled; the UI remains responsive and
waits for a result before permitting closure. There is no ongoing chat-context
interpretation: every submitted instruction is a standalone request with a live
session snapshot. It is a bounded DAW command UI, not a general chatbot or an
audio quality evaluator. The existing allowlist does not add mastering, stem
separation, export or arbitrary commands. Clarifications require a new submission.

## Validation and remaining acceptance

Controller boundary tests cover preview-only reads, explicit confirmation,
cancellation, changed text, stale sessions, consumed plans, clarification,
connection failure and artifact isolation. Existing engine tests still apply.
Native UI inspected: Thai typing, layout and disconnected engine handling.
Live Ollama + SoundCraft UI Preview/confirmed Apply/Verify remain untested here;
controller fixtures do not establish live desktop acceptance.

Checkpoint publication belongs to `develop/tkn-daw-v2-integration`; identify the
Step 7 revision with `git log -1 -- tkn-jarvis/text_chat.py`. No main merge or V1
code change is part of this work.
