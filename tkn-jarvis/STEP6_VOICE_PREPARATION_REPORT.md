# Step 6 voice preparation — 2026-10-14

## Checkpoint

Reviewed Step 5.5 normalization/policy diff. Local HEAD and remote integration
branch both identify `674c89c59d0ed7ea4e69f0538d0a120e3e99c918`.
Step 5.5 is already committed/pushed; no duplicate commit or main merge performed.
Step 6 additions remain uncommitted for review. Existing V2 tracked code, Rust,
and TKN DAW V1 files were not changed.

## Implemented

New voice adapter, optional dependencies, boundary tests, and usage/acceptance
protocol. Manual recording is bounded to 1–30 seconds; raw transcript must be
reviewed/edited and explicitly accepted by typing REVIEW. STT has no Apply path.
Preview delegates to the existing intent engine. Apply stays in the existing
separate CLI with the exact confirmation hash and per-command Verify.
The program rejects incomplete local models, including missing tokenizer files,
and models without Thai support. Output creation never overwrites an existing file.

## Local setup and checks

Installed a separate Python 3.12 environment under
`$env:LOCALAPPDATA\TKN-DAW-V2\voice-env` (outside the repositories).
Installed faster-whisper 1.2.1, CTranslate2 4.8.3, sounddevice 0.5.6.
Downloaded multilingual `Systran/faster-whisper-small` separately for setup,
revision `536b0662742c02347bc0e980a01041f333bce120`, to
`$env:LOCALAPPDATA\TKN-DAW-V2\models\faster-whisper-small`.
Codex's Windows application redirects LOCALAPPDATA into its LocalCache;
use the paths visible to the shell running the program.

- Python suite: 101/101 passed (91 existing, 10 new voice boundary tests).
- Real installed STT: model loaded with offline Hub settings; Thai supported.
- Synthetic one-second silence: no transcript segments. This is a provider smoke
  check, not real microphone or Thai speech accuracy evidence.
- Device enumeration found Speakerphone (Brio 300), default input index 1.
- PortAudio accepted 16 kHz mono float32 input settings; no capture performed.
- No live Ollama inference, DAW writes, or microphone speech test performed.
- Full Rust CI was not rerun; cargo is unavailable on this shell's PATH.

## Open acceptance

Real Thai speech requires the human to speak the frozen phrases in README_VOICE.md
into the selected microphone. Start in transcribe-only mode, score raw results
separately from human corrections, then test cancellation, staleness and confirmed
Apply/Verify on an isolated disposable demo. Do not claim Step 6 complete or STT
accuracy from the synthetic Step 5.5 dataset, mock tests, or silence smoke.
