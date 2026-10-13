# Step 5: local AI Intent Engine

The additive `intent_engine.py` adapter lets an installed local Ollama model propose bounded Thai intents. Existing V0/V1 files and production Rust are unchanged. It never accepts free-form engine commands from the model.

Flow: **Thai request → local Ollama intent → independent schema/range checks → concrete Preview → human confirmation → SoundCraft → Verify**.

## Run on Windows

Start Ollama with the already-installed `gemma3:4b` model (override with `--model` to select another installed local model). Start SoundCraft on an isolated disposable demo with a local control port. Review the session before using this on real work.

```powershell
Set-Location 'C:\TKN DAW\work\tkn-daw-v2'
.\target\debug\soundcraft.exe --demo --no-audio --control 7801
```

In another shell:

```powershell
py -3 tkn-jarvis/intent_engine.py preview 'จาร์วิส ลดเสียงร้องลงหน่อย ใส่ EQ ตัดเสียงทุ้ม แล้วบีบเสียงให้เนียนขึ้น' --port 7801 --out work/vocal-preview.json
py -3 tkn-jarvis/intent_engine.py apply work/vocal-preview.json
```

Preview reads the live session and contacts only local Ollama. A vocal track must exist and be unambiguous; the model should ask a clarification question otherwise (exit 2, no preview generated). AI can propose numeric assumptions for vague wording, which are shown for review. It does not listen to audio or guarantee better sound.

Apply displays the proposed changes and waits for the human to paste the saved artifact's full `confirmation` hash. Relative faders show both the requested delta and the resolved absolute fader value. The full session baseline is retained in the file instead of filling the review display. Any other input, including `yes`, cancels before contacting SoundCraft. There is no automatic-yes flag. Apply does not invoke the AI model again. The hash binds the exact preview for confirmation and detects accidental changes; it is not a signature or access-control boundary against someone editing code/files with local access.

## Boundaries

- Fixed `127.0.0.1:11434` Ollama endpoint; proxies and HTTP redirects disabled. Reject cloud model names, remote-backed model metadata and missing local models; never download automatically. Session names, faders and effect metadata are shared with the local server, excluding clips/audio/file paths. This assumes a trusted local Ollama installation.
- Generated JSON is bounded and rejects duplicate keys, nonfinite numbers, extra properties, unknown operations, effects, slots and unsupported parameter ranges. The same independent checks run again when applying a saved artifact.
- A conservative local request guard asks for clarification when it sees deletion/removal or confirmation-bypass wording, before contacting the model. It can also block negated or quoted uses of these words. Schema validation cannot prove semantic fidelity: the model can misinterpret an instruction into an otherwise allowed edit, so the human must review concrete commands.
- Allowed intents: absolute/relative volume, built-in EQ/compressor insertion/parameters, mute and rename. Relative faders become absolute values in Preview. There is no delete/save/bounce, arbitrary command, external-plugin load, shell command or history operation in the AI allowlist.
- EQ high-pass is explicitly `type = 3`, with independently validated integer filter choices 0..6. Existing V1's parser is unchanged.
- All actions are preflighted against simulated track/effect changes before a preview is accepted. Apply rebuilds commands from validated intent; it refuses modified artifacts and stale tracks/history before the first write.
- Each ordered write is checked by an independent post-write inspection. Stop at the first failure and report prior verified steps. A failing current step may already have written; there is no automatic rollback or atomic batch.
- Staleness checks reduce accidental application to a changed session. They do not lock the session or prevent a concurrent edit between inspection and dispatch. SoundCraft's existing group semantics apply. Use a dedicated demo for acceptance testing.
- This layer cannot prevent a user from directly running the separate V0/V1 adapters. Its boundary applies to AI-generated proposals through this entry point.

## Tests and evidence

```powershell
py -3 -m unittest discover -s tkn-jarvis -p 'test_*.py' -v
py -3 tkn-jarvis/windows_intent_smoke.py
cargo xtask ci
```

The Windows smoke owns an isolated, hidden, audio-disabled demo process. It creates a test vocal track, calls real local Ollama, checks that the compound proposal includes a fader, actual high-pass filter and compressor, confirms CLI cancellation makes no change, then supplies confirmation **only in this disposable acceptance fixture**. It verifies each resulting write, undoes the test changes and restores the initial demo tracks. It never attaches to a user session. Logs are saved locally under `work/intent-smoke` and are not committed. Profiles are stored outside the repository in the sibling `intent-smoke-profiles` directory: long model inference can trigger autosave with generated demo WAVs, which must not enter the repository's asset scan.

Provider protocol references: [Ollama Chat API](https://docs.ollama.com/api/chat) (`format` JSON schema and `stream: false`) and [Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs). The schema is included in both the format field and prompt, with an example proposal. Enforcement is local even if the model ignores its prompt.

## Windows acceptance, 2026-10-13

- Python tests: 59/59 pass (34 existing + 25 intent boundary tests).
- Rust `cargo xtask ci`: all six gates pass, exit 0. The existing nonfatal WASM `CaptureStates` warning remains.
- Real local `gemma3:4b`: the compound Thai vocal request passes Windows demo acceptance. Cancelled CLI application leaves the session unchanged; confirmed CLI application verifies its steps; Undo restores all initial demo tracks. Audio is disabled.
- Initial experiments with `qwen2.5:7b` and `qwen3:4b-instruct` failed validation or timed out on this machine. No AI commands were dispatched from those failed proposals. Schema grounding and a proposal example were then added; the successful result uses Gemma. This is one composite language acceptance case, not a broad Thai-language benchmark.
- An additional read-only language check initially found that Gemma substituted mute for a request to delete without confirmation. No command was applied. The independent deletion/bypass request guard and its regression test were added in response; this does not establish that all unsupported requests or interpretation errors can be detected automatically.
- The alternative phrase `ช่วยเบาแทร็ก Voice ลงอีก 3 เดซิเบลนะ` produces a relative -3 dB intent. The deletion/bypass request is now intercepted by the local guard, not credited as correct model interpretation. Evidence: `work/step5-language-checks.json`.
- Local evidence: `work/python-step5.log`, `work/full-ci-step5.log`, `work/intent-smoke/summary.json`, `intent.json`, `model-response.json`, `preview.json`, `cancelled.log`, `confirmed.log`, `after.json`.
- This Step 5 checkpoint belongs to `develop/tkn-daw-v2-integration`; identify its revision with `git log -1 --oneline -- tkn-jarvis/intent_engine.py`. Only the four new Step 5 files are included; no existing tracked source files were modified.

Voice control, physical playback/recording, interface latency and installed third-party VST3/CLAP tests are separate follow-ups. This is a bounded proposal engine, not universal natural-language understanding.
