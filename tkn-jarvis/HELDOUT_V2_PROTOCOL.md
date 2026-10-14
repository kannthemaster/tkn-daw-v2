# Step 5.5 first new evaluation

Frozen 24-case SHA256: `9f16988c4f4a3a596e7ba5571daeb014b805ace3873971451d445495ac64f57d`.
Run one full first-pass evaluation with gemma3:4b after converter development.
Do not change engine, converter, data or oracle during this run. No Apply.
If failures inform fixes afterward, this set becomes regression data and a new
set is required for another held-out claim. Preserve this first result even if
a later revision passes. Same contributor authored cases; not external blind
evaluation. ASR errors are synthetic text, not recorded speech recognition.

```powershell
py -3 tkn-jarvis/thai_benchmark.py --dataset tkn-jarvis/thai_heldout_v2.json --output work/thai-heldout-v2
```
