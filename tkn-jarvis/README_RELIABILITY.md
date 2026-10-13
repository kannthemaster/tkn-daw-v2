# Step 5.3 — bounded Thai intent reliability

`intent_policy.py` independently extracts a bounded request contract before local
Ollama inference. Supported requests constrain track, slot, operation order, action
count and parameter values. Unknown or ambiguous requests return clarification
without model inference or DAW dispatch. A model response must satisfy both the
existing schema and this contract; rejected responses are never silently repaired.

This changes the measured system, not the underlying `gemma3:4b` model. For explicit
requests, the model copies contract values; vague compression requests permit
values only within specified preset ranges. The bounded parser is deliberately
conservative and is not a general Thai language understanding model. The unchanged
hand-authored benchmark was used during development, so its final score measures
acceptance on that set, not held-out/general accuracy. Voice control still needs
separate held-out evaluation and explicit confirmation.

## Behavior

- Spoken negative dB values are distinguished from deletion requests.
- Unknown names, multiple vocal targets, occupied slots and unsupported mixed
  requests require clarification. Missing targets cannot inherit a previous track.
- Parameter-only requests permit only the requested parameters and slots.
- Sequential renames resolve subsequent actions against the new name in a copied
  snapshot. The actual session is unchanged while planning.
- Accepted summaries are rebuilt from approved actions rather than model claims.
- Preview → explicit confirmation → Apply → Verify remains unchanged.

## Checks on Windows

```powershell
py -3 -m unittest discover -s tkn-jarvis -p 'test_*.py'
py -3 tkn-jarvis/thai_benchmark.py --output work/thai-benchmark-step53-final
py -3 tkn-jarvis/windows_intent_smoke.py
py -3 tkn-jarvis/windows_smoke.py
cargo xtask ci
```

Benchmark uses synthetic snapshots and dispatch fences: no Apply is allowed.
The separate intent smoke runner confirms an actual CLI Apply only in its own
disposable audio-disabled Windows demo, verifies it and restores the initial
tracks. It does not test speakers, recording, interface latency or real plugins.

Only `intent_engine.py` and `test_intent_engine.py` are changed existing files.
The policy and this document are new files. Include `intent_policy.py` when
packaging the engine. Benchmark dataset and runner are unchanged from Step 5.2.

## Checkpoint evidence (2026-10-13)

Latest full original-set run: 29/30 primary (96.7%), 30/31 including prompt overlap.
14/14 required clarifications were safe; zero wrong/unjustified proposals and
zero attempted DAW calls. `rename_then_mute` received duplicated mute operations
from the model; the entire plan was rejected safely. The runner exited 1 because
one case failed, despite exceeding the proposed 90% Step 5.3 gate. An earlier
run passed 30/30; these results do not establish deterministic model behavior.

79 Python tests, all six Full CI gates, native Windows build/control smoke and
real local-model confirmation/restoration smoke passed. Audio hardware was not
tested. This checkpoint precedes the separate Step 5.4 held-out evaluation.
