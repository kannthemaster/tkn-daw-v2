# Step 5.5 fresh post-fix evaluation

V2 first-pass was 23/24 with one unjustified proposal for the misspelled unit
`ดีบี้`. Apply fences prevented writes. After the full run finished, a unit-suffix
guard was added, and V2 became regression data. Preserve its failed first result.

V3 is a fresh 20-case set, frozen after that fix and before live inference.
SHA256: `b2ac2485e75a8176fec8a370b4f922659ee0e4885233e755c8ede4779cdd91b2`.
Run two complete repeats without changing engine/converter/dataset/oracles.
The new wrapper records lexical dependency hashes before and after; the original
runner and scoring policy are unchanged. All 20 cases count; no Apply permitted.
Same contributor authored the set, not an external blind or population sample.
Synthetic ASR-like text is not real STT accuracy or audio hardware validation.

```powershell
py -3 tkn-jarvis/normalization_benchmark.py --dataset tkn-jarvis/thai_heldout_v3.json --repeats 2 --output work/thai-heldout-v3
```

Clear requests must produce all requested actions. Ambiguity/malformed units
must defer without actions. If V3 informs further fixes, it too becomes regression
data and another fresh set is needed before making a held-out claim.
