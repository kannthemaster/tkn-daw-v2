# Step 5.5 Thai lexical normalization

Step 5.4 is published at `9b550b0dbee09826f4be056309d2235ccf704266` on
`develop/tkn-daw-v2-integration`. The Step 5.4 report records its pre-commit state.
Step 5.5 adds `thai_normalizer.py`, called by `intent_policy.py` before contract
generation. It performs lexical conversion, not fuzzy track matching or STT.

- `หรี่` maps to `ลด`; `ดีบี`, `ดี บี`, `เดซิเบล` map to `dB`.
- Thai digits map to ASCII outside protected names/literals.
- Standard spoken integers (0..999999, excluding million expressions) and
  digit-by-digit decimals convert only before recognized units. DAW bounds remain.
- Existing/requested track names and rename destinations are preserved.
- Ambiguous choices and malformed unit suffixes require clarification. `ดีบี้`
  and `dBA` must not be accepted as a prefix match for dB.
- Preview, explicit confirmation, Apply and Verify are unchanged.

```powershell
py -3 -m unittest discover -s tkn-jarvis -p 'test_*.py'
py -3 tkn-jarvis/normalization_benchmark.py --dataset tkn-jarvis/thai_heldout_v3.json --repeats 2 --output work/thai-heldout-v3
py -3 tkn-jarvis/windows_normalization_smoke.py --model gemma3:4b
```

The wrapper adds before/after lexical dependency hashes to the unchanged runner.
Its output directory is overwritten, so use a new directory for each evaluation.
V2 first-pass failed on an unjustified proposal for `ดีบี้`; its original result
is preserved. The unit guard was added after that run, making V2 regression data.
V3 was authored afterward, frozen, and evaluated without tuning during the run.
See the protocols and `STEP55_NORMALIZATION_REPORT.md` for final evidence.

These hand-authored sets are not external blind evaluations or general Thai/STT
accuracy claims. No Apply is permitted in benchmarks. Windows smoke confirms
only its own disposable audio-disabled demo and restores it. The smoke runner
writes under `work/intent-smoke`; do not run it concurrently with another smoke.
No hardware playback, recording, interface latency or real plugins are tested.
