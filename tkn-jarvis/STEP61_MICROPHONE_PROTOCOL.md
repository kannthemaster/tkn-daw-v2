# Step 6.1 — frozen real microphone protocol

Prepared 2026-10-14; not executed. Model: faster-whisper-small revision
536b0662742c02347bc0e980a01041f333bce120. Input: Brio 300, device 1
(verify the current device list before each run). No DAW or Ollama connection.

Run `run_microphone_acceptance.ps1` in PowerShell. Each case records 8 seconds
only after Enter. Speak the exact phrase displayed. If you misspeak, keep the
attempt and mark it invalid; never count it as an STT error or overwrite it.
Run the complete script twice, using its new timestamped evidence directory.

| ID | Intended spoken text | Human action |
|---|---|---|
| en-track | หรี่แทร็ก Voice ลงสองดีบี | Correct transcript if needed, then REVIEW |
| th-track | ลดแทร็กเสียงร้องลงสามดีบี | Correct transcript if needed, then REVIEW |
| multiword | เพิ่มแทร็ก Lead Vocal ขึ้นหนึ่งจุดห้าดีบี | Correct transcript if needed, then REVIEW |
| negative | ตั้งแทร็ก Voice เป็นลบสามจุดศูนย์ห้าดีบี | Correct transcript if needed, then REVIEW |
| zero | ตั้งแทร็ก Voice เป็นศูนย์ดีบี | Correct transcript if needed, then REVIEW |
| digit-name | หรี่แทร็ก Voice 2 ลงสองดีบี | Correct transcript if needed, then REVIEW |
| silence | Stay silent throughout the eight seconds | Empty/error expected; cancel hallucinated text |
| cancel | ลดแทร็ก Voice ลงสองดีบี | Enter at edit prompt, type CANCEL at review prompt |

Evidence includes frozen cases, model revision, installed package versions,
device listing, console transcript and successful raw/reviewed transcript JSON.
Per-case Python console logs retain cancellation/raw STT output and errors that
do not produce JSON. Windows PowerShell transcripts alone may omit native Python
output. Audio is not saved. Intended phrases are a protocol, not proof the
speaker actually said them: the human must confirm what was spoken per attempt.

After the run, record whether each phrase was spoken exactly, raw name/value/sign
errors, corrections, silence result and cancellation. Do not equate exact string
matches with semantic correctness. Keep raw STT scoring separate from corrected
text, and do not describe this hand-selected set as population accuracy.

Step 6.1 remains pending until both real speech runs are reviewed. Demo Preview,
human Apply confirmation, stale-session rejection, cancellation and Verify are
later acceptance gates required before closing Step 6.
