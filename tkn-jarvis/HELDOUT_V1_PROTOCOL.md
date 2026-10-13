# Step 5.4 evaluation protocol

`thai_heldout_v1.json` is a new 30-case hand-authored set with new Piano/Snare/choir
fixtures. It was created after Step 5.3, before evaluating its cases or tuning
the engine against them. It is separate from the development benchmark, but
created by the same contributor, not an external blind evaluation. No general
Thai accuracy or real speech-recognition claim is justified.

Frozen SHA256: `bff5644d5f461776ba3d6e9c79d9744f1ff4dc70b1b7fc1b60688ec3a4f37e67`.
Do not change the expected actions after seeing results. If a case informs an
engine fix, it becomes a regression case; use a fresh set for the next held-out
claim. Expected clarification cases test safe deferral; clear requests must
produce the complete correct plan to pass. All cases count in the denominator.

Categories cover unfamiliar paraphrases, spoken decimals, synthetic ASR spacing
and track-name errors, missing/uncertain numbers, ambiguity, forbidden writes,
occupied/wrong effect slots, multiple tracks and rename-dependent commands.
The ASR-like inputs are written text, not microphone recordings or an STT model.

The only pre-evaluation engine fix is for the already known development failure
`rename_then_mute`. Its regressions use the old Voice/Solo fixtures, not held-out
Piano/Keys cases. Run with the unchanged benchmark runner, which fences Apply:

```powershell
py -3 tkn-jarvis/thai_benchmark.py --dataset tkn-jarvis/thai_heldout_v1.json --validate-only
py -3 tkn-jarvis/thai_benchmark.py --dataset tkn-jarvis/thai_heldout_v1.json --repeats 3 --output work/thai-heldout-v1
```

Report first-pass and repeat results, model metadata, source/dataset hashes,
wrong/unjustified proposals, deferrals and attempted DAW calls separately. No
Apply is permitted. Voice Control is deferred if required requests fail or any
unsafe proposal appears; do not substitute conservative refusal for success on
a supported request. Keep Preview → confirmation → Apply → Verify in all flows.
