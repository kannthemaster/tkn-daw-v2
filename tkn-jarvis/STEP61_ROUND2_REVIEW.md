# Step 6.1 round 2 review — 2026-10-14

Evidence (original files preserved):
`C:\Users\Workstation2\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\TKN-DAW-V2\acceptance\20261014-101641-a2a37653`

All eight cases have EXACT human attestations. Six speech cases have raw and
reviewed JSON plus explicit typed REVIEW logs. Silence and cancellation have
per-case logs and no transcript JSON, as expected. The frozen cases match the
previous round. Model revision remains 536b0662742c02347bc0e980a01041f333bce120;
faster-whisper 1.2.1 / CTranslate2 4.8.3 / sounddevice 0.5.6.

## Observations

| Case | Raw STT | Review |
|---|---|---|
| en-track | Retek Vice ลงสองดีบี | Corrected command and Voice |
| th-track | ลดแท็กเสียงร้องลง 3 dB | Corrected แท็ก; numeric/unit form equivalent |
| multiword | เพิ่มแทร์ค ลีทโวโค่ ขึ้น 1.5 dB | Corrected Lead Vocal and keyword; value equivalent |
| negative | ตั้ง แทรก ไว้ เป็น ลบ 3 จุด สูน แห่ ดี บี | Corrected Voice and decimal wording; raw fraction unreliable |
| zero | ตั้ง Trackwise เป็นสูญ DB | Corrected target and ศูนย์ wording |
| digit-name | ครีแท็ก ไว้สอง ลงสอง ดีบี | Corrected command and Voice 2; raw name/digit boundary unreliable |
| silence | Empty-transcript error, exit 1 | Rejected before review, no transcript file |
| cancel | ลดแทร์กไวส์ ลงสองดีบี | Cancelled in edit field, exit 0, no transcript file |

All six reviewed texts match the intended frozen phrases. This establishes
stored human corrections in these attempts, not raw STT accuracy. Every raw
speech transcript contains at least a wording/spelling/target problem; English
track names remain unreliable and the negative decimal was corrupted.
No aggregate population accuracy or confidence claim is justified.

## Gate status

- One complete real speech run with preserved raw/corrected text: observed.
- Explicit human REVIEW for all six accepted speech cases: observed.
- Real silence rejection: observed for this attempt.
- Cancellation without saving an accepted transcript: observed for this attempt.
- Second complete run under this protocol: pending (round 1 was incomplete).
- Demo Preview/confirmation/Apply/Verify and stale-session tests: pending.

This run used the transcribe-only path, which never dispatches to DAW or Ollama.
No live session write acceptance is claimed. Recording device was intended to be
Brio 300, but the current evidence does not persist the selected PortAudio index
or full device metadata. Audio was not saved; EXACT is human attestation.
UI/cancellation/logging fixes occurred between rounds; the STT model was not
tuned. Keep both rounds and their limitations visible.

Step 6.1 and Step 6 remain open. Repeat the frozen set once more before judging
repeatability; do not add continuous listening or voice Apply based on this run.
