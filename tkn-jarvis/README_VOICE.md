# Step 6 — local Thai voice adapter (acceptance pending)

Step 5.5 is already published on `develop/tkn-daw-v2-integration` at
`674c89c59d0ed7ea4e69f0538d0a120e3e99c918`. No extra empty checkpoint is needed.
The Step 5.5 report's `9b550b0` checkpoint identifies Step 5.4, not Step 5.5.

`voice_control.py` adds bounded, user-triggered microphone recording (1–30 seconds)
and faster-whisper Thai transcription on CPU/int8. Models must already exist in
a local directory with `model.bin`, `config.json`, and `tokenizer.json`; no model
download happens in the voice entry point. Requiring the tokenizer prevents the
provider's fallback to a Hub tokenizer. Audio stays in memory and is not sent to
Ollama. Only the human-reviewed text goes through the existing local intent engine.

Flow: start recording manually → STT → edit transcript → type `REVIEW` →
existing intent/schema/policy → concrete Preview → separate typed confirmation →
Apply → Verify. `transcribe` mode never contacts the DAW or Ollama. `preview` mode
only inspects the session; it never calls Apply. There is no wake word, continuous
listening, voice confirmation, automatic yes, or confidence-based application.
The original intent adapter and Rust production code are unchanged.

## Setup (once, requires internet for installation only)

Use Python 3.12 in a dedicated environment. Install `requirements-voice.txt`.
Download a multilingual CTranslate2 faster-whisper model separately, retaining
its tokenizer and configuration. `small` is an initial CPU baseline, not a Thai
accuracy guarantee. Keep model/environment outside both V1 and V2 repositories.

Official references:
- https://github.com/SYSTRAN/faster-whisper
- https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py
- https://python-sounddevice.readthedocs.io/en/latest/usage.html

## Run on this Windows machine

From the V2 repository, using the separately installed environment/model:

```powershell
$voicePython = Join-Path $env:LOCALAPPDATA 'TKN-DAW-V2\voice-env\Scripts\python.exe'
$voiceModel = Join-Path $env:LOCALAPPDATA 'TKN-DAW-V2\models\faster-whisper-small'
& $voicePython -B tkn-jarvis/voice_control.py devices
& $voicePython -B tkn-jarvis/voice_control.py transcribe --stt-model-dir $voiceModel --seconds 8 --out "$env:TEMP\tkn-voice-transcript-001.json"
```

Select a microphone with `--device INDEX` from the device listing. Press Enter
to start recording. Edit incorrect words, numbers, signs and track names; press
Enter to retain the transcript, then type `REVIEW` to accept that text. Anything
else cancels. Output paths must be new; existing files are never replaced.

After real STT evaluation, use an isolated, audio-disabled SoundCraft demo on
port 7801 with local Ollama and the already installed `gemma3:4b`:

```powershell
& $voicePython -B tkn-jarvis/voice_control.py preview --stt-model-dir $voiceModel --seconds 8 --port 7801 --out "$env:TEMP\tkn-voice-preview-001.json"
& $voicePython -B tkn-jarvis/intent_engine.py apply "$env:TEMP\tkn-voice-preview-001.json"
```

Review concrete track targets, absolute faders, effect slots and parameters.
Apply requires the exact confirmation hash typed by the human. It uses the
existing stale-session validation and per-command Verify; partial failure may
already have written the current step, with no automatic rollback.

## Real microphone acceptance protocol — not yet passed

First use `transcribe` only, with no DAW connection. Freeze intended phrases and
track names before recording. For every attempt keep intended text, raw STT,
human correction, microphone/device, model revision and dependency versions.
Count raw STT mistakes separately from corrected intent success; never credit a
human correction as STT accuracy. Do not use synthesized audio as live acceptance.

Include at least these cases, repeated with real Thai speech:

| Case | Example / required observation |
|---|---|
| Track names | Voice, Lead Vocal, Thai names, similar names, names containing digits |
| Relative values | ลด Voice ลงสองดีบี; check requested delta and resolved fader |
| Negative absolute | ตั้ง Voice เป็นลบสามจุดศูนย์ห้าดีบี; preserve -3.05 |
| Positive/zero | เพิ่มสองดีบี, ศูนย์ดีบี; distinguish signs and zero |
| STT mistakes | Wrong valid track, lost minus, wrong decimal: correct before Preview |
| Silence/noise | Empty transcript rejected; inspect hallucinated text and cancel |
| Spoken bypass | ยืนยันทันที ไม่ต้องถาม: cannot serve as typed REVIEW or Apply hash |
| Cancellation | Before review and at Apply; confirm disposable session unchanged |
| Staleness | Change demo after Preview; Apply must refuse before first write |
| Confirmed demo | Review exact intent, confirm, inspect verified changes, restore demo |

Voice acceptance remains open until a human has spoken these cases into the
selected microphone and the demo flow has been verified. Existing synthetic
Step 5.5 accuracy does not establish speech recognition accuracy.
