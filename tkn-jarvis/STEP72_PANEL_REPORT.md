# Step 7.2 — Embedded JARVIS Panel closeout, 2026-10-14

Implemented Steps 7.2.1–7.2.5 on `develop/tkn-daw-v2-integration`.
The four scoped real command workflows passed Preview → UI confirmation →
Apply → original per-step Verify. This is development acceptance on disposable
audio-disabled demos, not physical audio/interface or language-accuracy acceptance.

## Implementation and checkpoints

| Step | Checkpoint | Result |
|---|---|---|
| 7.2.1 | e938b7b | Versioned bounded UTF-8 JSONL bridge; immutable one-shot previews; 11 Python bridge tests |
| 7.2.2 | f25c6b5 | Optional docked/floating panel; fresh-profile default closed; Thai system-font fallback |
| 7.2.3 | f037c8f | Background owned interpreter, temporary localhost endpoint, shutdown and close deferral |
| 7.2.4 | aca167d | Window menu wiring, initial panel width, complete-plan Verify guard, six real-engine UI workflow tests |
| Transport | d9a952c, 84dd883 | Buffered response frames; accepted Windows sockets explicitly use timed blocking reads |
| 7.2.5 | this documentation checkpoint | Windows build, full CI, actual screenshots, layout reload and evidence closeout |

Rollback checkpoint **9ef52bf04cab068b34cd84aa68e1c9b102adbec3** remains an
ancestor. No main merge, TKN DAW V1 edits, Voice Control changes or Rust
Audio/DSP/Playback Engine edits were made. Voice remains preserved and paused.

## Real acceptance

Built this checkout's Windows executable with installed Python 3.14 and the
existing local Ollama `gemma3:4b` model. Production source hashes were unchanged
through the final run. Fixtures and restoration used the existing explicit
development control endpoint; JARVIS used its separate gated ephemeral endpoint.

| Case | Observed result |
|---|---|
| Volume | `ลดแทร็ก Voice ลง 2 dB`: unchanged Preview; confirmed UI Apply; Verify 1 step; independent read -2 dB |
| EQ | Insert EQ in a, gain -3: unchanged fresh Preview; confirmed Apply; Verify 2 steps; eq_1band slot 0/gain -3 |
| Compressor | Insert in b, threshold -18: unchanged Preview; confirmed Apply; Verify 2 steps; compressor slot 1/threshold -18 |
| Rename → Mute | Original Voice → Lead Vocal phrase: both commands ID 33; Verify 2 steps; name Lead Vocal/mute=true; existing Lead ID 24 unchanged |
| Modal Cancel | Actual Enter selected default Cancel; no writes and no retained plan; UI code unchanged by later transport fixes |
| Session/edit changes | Old plans were discarded; fresh same-phrase plans were required. Automated pointer attempts changed the edit position, so later confirmation used keyboard navigation |
| Ollama offline | Connection-refused message, no Preview/Apply, unchanged tracks; owned server/runner stopped for the test |
| Missing Python | Explicit unavailable-runtime message, no Preview/Apply or Python child; session unchanged |
| Normal close | Owned interpreter and ephemeral listener stopped; the separate opt-in development listener remained |
| Layout | Actual Edit/Mix docked and floating screenshots; independent Edit/Mix layouts survived process exit/reopen |
| History | In-memory history survived panel close, but new app history was 0; chat, instructions and tokens absent from saved preferences |
| Restoration | All initial tracks restored with bounded Undo; stopped position restored to 443072; redo metadata retains the test history |

The lifecycle stress case used an **acceptance-only 12-second transport delay
after a real write**, preserving original AI/confirmation/Verify. Closing the
panel and requesting app quit left the worker running while Applying. During
that interval the edit position changed from 443072 to 443077; the document
guard rejected the subsequent inspection. The UI reported a possible partial
write and **did not report Verify success**, then stopped its worker. The demo
was restored. This establishes close deferral and fail-closed handling; it does
**not** establish successful Verify while simultaneously closing the panel.
That narrow interaction should be revisited before production rollout.

## Validation and fixes

Python suite: **133 passed**. Full Rust CI passed all six gates: fmt, strict
workspace Clippy, tests, assets, layers, WASM. Final transport CI used
`RUST_TEST_THREADS=1`: one existing process-wide palette assertion failed in a
parallel run, passed in isolation, and passed in the serialized full suite.
No theme production changes were made. Existing WASM CaptureStates dead-code
warning remains nonfatal.

Live testing found and fixed the missing Window menu entry and an intermittent
`WinError 10053` in the new private endpoint. A delayed-send regression reproduced
the exact network error before the fix; it passed after explicitly clearing the
accepted socket's inherited nonblocking mode. Twelve sequential large UTF-8
responses, including a 100 ms delay before each send, passed. The same real
Volume plan subsequently completed successfully; errors and discarded plans
from earlier runs are retained rather than counted as successful acceptance.

The UI permits writes only while explicitly Applying, for the exact next
compiled command against the same document. Stopped-worker and foreign-document
queued writes are rejected. Successful Verify requires all planned writes and
the matching number of verified steps. Model work/process/socket I/O run off
the UI thread; no audio callback changes were introduced.

## Evidence and use

Evidence root under the local TKN runtime:
`TKN-DAW-V2/step72-runtime/embedded-1990e46311544dca92cb3f1bef6c8891`.

- Final main run: `main-08f34b99e8e842d7ad3df37baf96710d` — before/preview/after JSON, nine independent acceptance checks, source/binary hashes, normal-close checks, restored state and screenshots.
- Reload: `reopen-5d73e2e2b46d40e6b895d234b755d9a5` — saved/reloaded layouts equal by parsed JSON, history 0.
- Missing runtime: `missingpython-8ab8126a4b204ff1a784eef23847ce64`.
- Lifecycle stress: `lifecycle-84dca874160140dca3e441de691d6b92` — actual write marker, applying/closed-panel snapshot, failure outcome and restored demo.
- Earlier main/prototype directories retain failures; root cleanup records owned processes stopped. Binaries, models and evidence are preserved.
- Compiler/CI logs: local `TKN-DAW-V2/rust-tools/step72-*.log` and `step724-*.log`.

Executable: `target/debug/soundcraft.exe`. Setup: [README_PANEL.md](README_PANEL.md).
Open **Window > JARVIS** with local Ollama running. Launch without `--no-audio`
for future listening tests; the command demos intentionally used that flag.
AI Mastering, Stem Separation, MV Studio and packaged-runtime distribution
remain subsequent work.
