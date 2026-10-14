# Step 7.1 — real Text Chat acceptance, 2026-10-14

**Outcome: live integration demonstrated; full closeout remains open because the
planned rename/mute request using an overlapping track name was falsely deferred.**
Existing Text Chat, Intent Engine and Rust UI code were not changed. Voice remains
paused. No main merge, V1 change, commit or push accompanies this acceptance run.

## Environment and provenance

- Integration HEAD: `23fa6c0c8dc0ec2b3a3d0ffa17478d6639680a50`.
- Native SoundCraft: official upstream v0.6.1 Windows x64 portable. Compared
  tag `6cf896e76c0ec82a11bf2494f209cfe7c8507f74` with integration HEAD: apps,
  crates and Cargo files differ only in four Windows test-related files/sections;
  production source matches. This is a release binary, not a locally built binary.
- Release ZIP SHA256, checked against published SHA256SUMS:
  `cd5f8d98257f771191fa1c1b7c524501ebf381311ff3d13509fd83a1926e1f20`.
- Ollama standalone v0.40.4, ZIP SHA256 checked against published checksums:
  `7485a1172f8527db4342a63521b9342fc466185ff0855da378cc864ecf6354cf`.
- Local `gemma3:4b`, digest
  `68ceab7e468a31c988b44d5a4984a0e21f58c4f7158c6ce29c1804babac38df7`,
  Q4_K_M, CPU inference. Loopback only and cloud disabled for the owned server.
- Portable binaries and model installed outside repositories under
  `%LOCALAPPDATA%\TKN-DAW-V2\step71-runtime` (Codex Windows LocalCache redirect).
- Owned built-in Midnight Groove demo, `--demo --no-audio --control 0`, unique
  profile. A synthetic empty Voice track was added through deterministic fixture
  setup, not via the AI allowlist. No user session opened.
- Audited wrapper `step71_text_chat_acceptance.py` runs the existing TextChat
  class. Real mouse interaction and modal confirmation were used; no provider
  mock, monkeypatched confirmation, or automatic yes was used. The wrapper logs
  calls/results, without changing the proposed commands or Verify implementation.

Official sources:
[SoundCraft release](https://github.com/storytold/soundcraft/releases/tag/v0.6.1),
[Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.4),
[Ollama Windows standalone](https://docs.ollama.com/windows).

## Observed results

| Case | Real result |
|---|---|
| Volume | First run: ลดแทร็ก Voice ลง 2 dB → Preview 0 to -2 dB → modal confirmation → Apply/Verify, one verified write. Independent session inspection showed -2 dB. |
| Cancel | Resumed run: same relative-volume Preview, clicked ยกเลิก Preview. Full engine baseline (tracks, undo, redo) unchanged; Voice remained 0 dB; no Apply event. |
| EQ | Insert EQ in slot a, gain -3. Two real writes verified. Independent read showed eq_1band slot 0 and gain -3. |
| Compressor | Insert in slot b, threshold -18. Two real writes verified. Independent read showed compressor slot 1 and threshold -18. |
| Planned combined rename/mute | เปลี่ยนชื่อแทร็ก Voice เป็น Lead Vocal แล้วปิดเสียงแทร็ก Lead Vocal → false clarification, no actions, no writes, unchanged baseline. Kept as a failed success case. |
| Supplemental standalone rename | Voice → JARVIS Vocal through real Preview/modal/Apply/Verify; same track ID 33, one verified write. |
| Supplemental standalone mute | Mute JARVIS Vocal through real Preview/modal/Apply/Verify; independently read mute=true, one verified write. |
| Unsupported AI track creation | สร้างแทร็ก stereo ชื่อ New Voice → clarification, Apply disabled, no new track, unchanged engine baseline. Creation is fixture setup only, not AI functionality. |
| Restoration | Both owned demos restored their initial tracks. Resumed run's full inspected document matches initial except redo and transport; redo retains New... after Undo, and demo transport had progressed then stopped. These metadata differences are retained in evidence, not described as byte-identical state. |

All accepted/resolved Preview cases in the resumed run recorded an unchanged
engine baseline before any Apply. Every confirmed successful write was followed
by the original independent Verify inspection. Closing the acceptance UI restored
the fixture with bounded Undo and compared tracks to initial state. Both owned
SoundCraft and Ollama processes were then stopped. Downloads/models/evidence are
preserved. No external plugin or physical playback/recording acceptance claimed.

## Known failure and next decision

The demo already contains `Lead`. After virtual rename to `Lead Vocal`, the
existing `mentioned` / `target_for` matching sees the shorter overlapping name,
removes it from residual text first, and leaves `Vocal`, causing the unknown-track
clarification. This is a conservative false rejection, not an unjustified write.
Standalone commands against unique JARVIS Vocal work, but those supplemental
results do not turn the original failed case into a pass. Do not claim all track
management wording is supported.

Fixing overlap handling requires authorization to edit existing Intent policy
code and regression coverage before rerunning the failing case. Rust/egui UI
integration remains unstarted and separately requires authorization. Step 7.2
was not started as part of these tests.

## Evidence

Original interrupted run (Volume success and restored before interruption cleanup):
`step71-runtime\text-ui-acceptance-47184a703fe14176a0bc53a381263304`.
Its `cancel-modal-check.json` was captured before the confirmation outcome and
is only a pre-confirmation snapshot; do not count it as a completed Cancel test.

Resumed run:
`step71-runtime\text-ui-acceptance-f7185356e2724e2485d68b1b0728b036`.
Key files: events.jsonl (raw model responses, proposals, real DAW calls,
confirmation/Verify/restoration events), initial.json, fixture.json, restored.json,
planned-cases.json (original plan unchanged), supplemental-cases.json (new
standalone cases recorded before execution), provenance.json, source-receipt.json,
cancel-button-check.json, EQ/compressor/rename/mute independent checks,
unsupported-independent-check.json and restoration-independent-check.json.

These are limited, synthetic-demo functional acceptance cases with real local
inference, not a population language benchmark or audio quality test. Python's
existing 113-test suite was previously passed; production code was unchanged
during live acceptance. Full Rust CI remains unavailable without cargo.
