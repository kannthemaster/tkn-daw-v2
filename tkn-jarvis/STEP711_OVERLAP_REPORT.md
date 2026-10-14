# Step 7.1.1 — Track Name Overlap closeout, 2026-10-14

**PASS for the scoped overlap fix and the original live Rename → Mute case.**
The Step 7.1 false-rejection blocker documented in STEP71_LIVE_REPORT.md is
resolved for its original phrase. Step 7.2 embedded UI work has not started.

## Change scope

Only existing `intent_policy.py` production code changed. Added
`test_track_name_overlap.py`; no Intent Engine, normalizer, voice, Rust engine or
existing UI edits. Publication belongs to `develop/tkn-daw-v2-integration`;
identify its checkpoint with `git log -1 -- tkn-jarvis/intent_policy.py`.
No main merge or TKN DAW V1 change is part of this step.

The matcher collects exact bounded name occurrences, considers longest names
first, and suppresses a shorter occurrence only when it is fully contained in a
longer exact name. Residual-text validation masks precisely those spans, avoiding
removal of `Lead` from `Lead Vocal` before the full name can be considered.
Separate mentions, duplicate/case-colliding names and partial overlaps remain
ambiguous. Unknown spellings are not fuzzy-corrected.

Prepared DAW commands already resolve Track IDs in the original compile_actions
implementation. That implementation is unchanged: tests and real evidence now
show Rename and the following Mute both reference the same stable ID. Human/AI
intent names remain readable while the internal command plan uses IDs.

## Regression validation

Python suite **122/122 passed**, including nine new regression test methods:
Lead/Lead Vocal in either registry order and mixed input case, Voice/Voice 2,
short names still selectable, separate mentions ambiguous, duplicate names,
partial overlaps, unknown suffixes/typos, Rename/Mute stable IDs, immutable
Preview snapshots, confirmation rejection before requests, and the original
demo phrase. Existing intent/normalization/confirmation/Verify tests still pass.
Full Rust CI was not run: cargo remains unavailable; no Rust changes were made.

## Real local acceptance

Unchanged TextChat UI and audit wrapper, local Ollama v0.40.4 / gemma3:4b, native
upstream SoundCraft v0.6.1 portable with production-source equivalence recorded
in Step 7.1. Owned audio-disabled Midnight Groove demo, unique profile, free
localhost control port 55737. Demo transport was stopped before initial snapshot.
Deterministic fixture setup added Voice; existing Lead remained in the demo.

The exact previously failed phrase was used, without rewording:

`เปลี่ยนชื่อแทร็ก Voice เป็น Lead Vocal แล้วปิดเสียงแทร็ก Lead Vocal`

| Gate | Observed result |
|---|---|
| Preview | Real local model proposed ordered Rename then Mute; engine baseline unchanged |
| ID binding | Both concrete commands target Track ID 33; existing Lead has a different ID |
| Modal cancellation | Default No selected in actual confirmation dialog; baseline unchanged, Voice still present, Lead Vocal absent |
| Fresh Preview | Same phrase proposed correctly again; baseline unchanged |
| Confirmed Apply | Deliberate Yes selected in actual dialog; no automatic-yes bypass |
| Verify | Two real writes independently verified by the original implementation |
| Independent read | ID 33 renamed Lead Vocal and mute=true; original Lead track object unchanged |
| Restoration | Tracks and all inspected session fields restored except redo, which retains New... after bounded Undo |
| Cleanup | Owned SoundCraft, Ollama server and model runner stopped; binaries/models/evidence preserved |

Sources were hashed before/after evaluation and unchanged. No tuning during the
evaluation. This is functional acceptance of a frozen reproduction on a
disposable demo, not a new held-out language accuracy claim or audio acceptance.

Resource note: two orphan model runners from prior acceptance sessions were
found and stopped during the first Preview. Current model/server were retained;
source/model/settings did not change. Their IDs and prior parents are recorded
in resource-cleanup.json. Later teardown also explicitly stopped the current
model runner, avoiding the same leak.

## Evidence

Outside the repositories, under the Codex LOCALAPPDATA redirect:
`C:\Users\Workstation2\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\TKN-DAW-V2\step71-runtime\step711-overlap-74937a3e5ffc4f18913f18b582ff4d07`

Key artifacts: planned-case.json, sources-before.json, events.jsonl (raw local
model replies, previews, exact DAW requests, Apply/Verify events), fixture.json,
cancel-modal-check.json, apply-independent-check.json, after-apply.json,
restored.json and closeout-check.json. Old failed Step 7.1 evidence is retained.

Next: Embedded JARVIS Panel is a separate step that
requires explicit authorization to edit the existing SoundCraft UI.
