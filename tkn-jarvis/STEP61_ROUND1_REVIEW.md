# Step 6.1 round 1 review — 2026-10-14

Evidence directory (original files preserved):
`C:\Users\Workstation2\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\TKN-DAW-V2\acceptance\20261014-093710-9ad02ecf`

This review combines saved JSON with the human's pasted terminal output.
PowerShell 5.1's console.txt omitted Python output and input, so it is not a
complete console trace. The cases are hand-selected; do not report general STT
accuracy. Audio was not saved; EXACT is a human attestation, not an audio oracle.

| Case | Observation | Status |
|---|---|---|
| en-track | exit 0; no transcript JSON; spoken_attestation empty | Incomplete, unscorable |
| th-track | ลดแท็กเสียงร้องลง 3 dB; accepted without correcting แท็ก | STT spelling error retained; number/unit equivalent |
| multiword | Lead Vocal → ลีดโวโค้า; corrected to Lead Vocal, 1.5 dB | Raw name incorrect; human correction stored |
| negative | Voice → ไว้ส; raw ลบ 3 จุด 05; corrected to -3.05 dB | Raw name incorrect; negative/decimal reformatted by human |
| zero | แทร็ก Voice → Trackwise; corrected to Voice, 0 dB | Raw target incorrect; value correct |
| digit-name | Retract wise to ลงสอง ดีบี; corrected to หรี่แทร็ก Voice 2 ลงสองดีบี | Raw command/name/embedded digit not reliable |
| silence | exit 1, no JSON; human pasted empty-transcript error, EXACT | Consistent with intended silence rejection; native log incomplete |
| cancel | cancel.json exists; reviewed_transcript is CANCEL, exit 0 | Not a cancellation: CANCEL was accepted as edited text |

All cases except en-track have EXACT attestations. English names repeatedly
require correction. Do not change raw results or retroactively label cancel as
passed. This run does not establish Voice Control acceptance. The transcribe-only
entry point has no DAW dispatch path; no live DAW/Intent acceptance was performed.

## Fixes for future runs

- CANCEL in the edit field now cancels, as well as any non-REVIEW response at
  the acceptance prompt. The raw transcript is printed before cancellation.
- Per-case UTF-8 Python logs explicitly retain raw STT, reviewed text, typed
  acceptance/cancellation outcome and errors, independent of PowerShell transcript.
- Review prompt says it accepts text, instead of claiming transcribe creates a Preview.
- Windows PowerShell UTF-8 BOM retained in the runner.
- Python regression suite after these changes: 104/104 passed; runner syntax valid.

Run the full frozen set again and review its evidence. A further complete repeat
is needed because round 1 is incomplete and did not establish cancellation.
Keep source changes between rounds explicit; these are UI/logging fixes, not
model tuning. Demo Preview/confirmation/Apply/Verify gates remain pending.
