# Step 7.2 lifecycle follow-up — 2026-10-14

Base checkpoint: **2b6998f25b772279afcf91d2a9bad7a441086bb9** on
`develop/tkn-daw-v2-integration`. Rollback checkpoint
**9ef52bf04cab068b34cd84aa68e1c9b102adbec3** remains an ancestor.
This report is the pre-publication test record; its containing commit identifies
the new checkpoint. The original STEP72_PANEL_REPORT is preserved as history.

## Cause established before changing production code

The original native Windows build reproduced the reported **443072 → 443077**
change. Kick was selected in the disposable demo; its next clip boundary is
443077. After actual Preview and native UI confirmation, the acceptance bridge
paused 12 seconds after a real fader write. Closing JARVIS retained its worker,
but Tab with no text-field keyboard owner reached `shortcuts::handle`, whose
normal Edit action calls `transport.locate` at that next selected clip boundary.
The changed document identity then rejected the next private inspection. The
original UI correctly warned of a possible partial write and never said Verify
passed. The fader change was independently observed and the demo restored.

The same failure was reproduced by a real-engine UI regression before the fix:
expected 443072, actual 443077. Keeping a track with clip boundaries selected
matters: an empty newly created Voice track does not reproduce Tab navigation.
Closing alone already retains the worker; this was an input-ownership issue,
not evidence that Sidecar transport or Playback changed the position itself.

## Scoped change

- `jarvis::State::blocks_session_shortcuts` owns background shortcut dispatch
  while Starting/Planning/Applying or while the explicit confirmation is open.
- The native/UI integration checks this before dispatching DAW shortcuts, even
  with a hidden panel awaiting Verify. Normal dispatch resumes afterward.
- No changes to document identity checks, generation/preview invalidation,
  ordered command matching, confirmation tokens, Python planning/apply/verify,
  private endpoint allowlist, native worker or application-close ownership.
- Pointer/menu or development-control edits are still real external edits and
  are rejected by the existing document guard. This is not a session lock or a
  blanket allowance to ignore cursor changes.
- Edit/Mix rendering, Dock implementation, Rust Engine/DSP/Playback and Voice
  sources are unchanged. New acceptance-only delay fixture is opt-in, not the
  default application bridge.

## Windows results with real local Python and Ollama

Installed Python **3.10.11**, Rust **1.99.0**, local installed `gemma3:4b` were
checked on this machine, not inferred from the previous report. Exact model and
source hashes and outcome observations: [PANEL_LIFECYCLE_RESULTS.json](PANEL_LIFECYCLE_RESULTS.json).
Each process had its own profile, `--demo --no-audio`, private gated JARVIS
endpoint and separate opt-in development control port. No existing user app or
project was attached. Confirmation was a deliberate native modal UI action in
the acceptance automation; it did not forge a direct Bridge Apply.

| Case | Observation |
|---|---|
| Before patch | Actual Tab changed 443072 → 443077; Verify rejected, partial-write warning; restored |
| Volume after patch | Preview unchanged; real confirmed -3 → -5 dB; hidden Applying + three Tabs + app-close request retained 443072; close deferred; Verify 1 step; worker stopped; all tracks restored |
| Rename → Mute | Same stable track ID 3 for both reviewed commands; float and close after first real write while Applying; Tab retained 443072; Verify 2 steps; other tracks unchanged; floating layout identical on reopening; both writes undone |
| External mutation | After confirmed fader write and close, explicit development-control locate to 443077 still rejected subsequent Verify; possible-partial-write warning; worker stopped; restored |
| Cleanup | All five owned app/control endpoints closed; no owned test interpreter remained |

Closing after a result does not count as closing during Apply. The first rename
attempt reached its lifecycle maneuver after Verify and is excluded. Another
poll asserted worker cleanup immediately at Idle, before the following UI tick;
later inspection established the original verified outcome and stopped worker
without changing sources/session. Both attempts and their observations are
retained. The hidden connection is released on the next UI frame after the
result, not necessarily in the same inspection that first reports Idle.

## Checks and evidence

Python suite: **133 passed**. JARVIS real-engine UI workflow suite: **11 tests**,
including the five new regressions (close + Tab and shortcut resumption, modal
navigation/Cancel, hidden external mutation, preview expiration on position
change, docked/floating completion in both Edit and Mix). Full CI uses
`RUST_TEST_THREADS=1` to retain the prior closeout's process-wide palette-race
workaround. Final **fmt / Clippy / test / assets / layers / WASM passed**,
exit 0. The existing WASM CaptureStates dead-code warning remains nonfatal.

The first full CI passed fmt/Clippy/tests but rejected untracked demo screenshots
and synthesized Autosave WAVs at the assets gate. These owned artifacts were
preserved outside the checkout, not deleted or exempted; final CI was rerun.
No weakening of the assets gate or proprietary media was introduced.

Local raw evidence is outside the repository:
`C:\Users\kannt\AppData\Local\TKN-DAW-Dev\panel-lifecycle-evidence-20261014`.
Baseline, positive Volume, negative mutation, unsuccessful timing attempt and
completed rename run have separate snapshots/markers/screenshots and restored
tracks. Build/test/CI logs are retained in the checkout's local `work/` and
copied to the external evidence root. Screenshots were visually inspected.
Reproduction: [PANEL_LIFECYCLE_ACCEPTANCE.md](PANEL_LIFECYCLE_ACCEPTANCE.md).

The old `C:\TKN DAW\work\tkn-daw-v2` checkout stayed at 674c89c with its
untracked report/work preserved. A fresh checkout under AppData\Local was used;
Drive sync status is still unconfirmed. Local-only plan documents were absent.
The referenced craftrules repository was absent and its GitHub clone returned
Repository not found; this limitation does not establish that its standards
were available. The checked-out AGENTS.md and local quality gates were followed.

## Remaining scope

No physical speaker playback, recording, Audio Interface, latency, real
VST3/CLAP or microphone/STT validation is claimed. Voice/faster-whisper remains
paused and preserved. No merge into main, V1 edit, automatic rollback, or general
Thai-language accuracy claim. This bounded Windows acceptance is not an
exhaustive concurrency/lifecycle stress certification.
