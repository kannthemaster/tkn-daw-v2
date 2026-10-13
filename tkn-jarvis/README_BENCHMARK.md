# Step 5.2 — Thai Intent Benchmark

This additive, hand-authored acceptance set measures the existing Step 5 engine without changing its prompt, parser or guard. It does not connect to SoundCraft, create a session or Apply anything. All session metadata is synthetic. Ollama runs locally with the same provider restrictions as Step 5.

Files: `thai_benchmark.json`, `thai_benchmark.py`, `test_thai_benchmark.py`, this README.

## Run

```powershell
Set-Location 'C:\TKN DAW\work\tkn-daw-v2'
py -3 tkn-jarvis/thai_benchmark.py --validate-only
py -3 -m unittest discover -s tkn-jarvis -p 'test_*.py' -v
py -3 tkn-jarvis/thai_benchmark.py --model gemma3:4b
```

The live benchmark requires an already-installed local model and Ollama. It never downloads a model. Output defaults to `work/thai-benchmark/results.json` and `report.md`. Progress is saved after every case. Exit 0 means every selected case passed; exit 1 means at least one semantic failure, validation failure or provider/runner error. A completed benchmark with failures is useful evidence, not a claim that the engine passed acceptance.

Run selected cases or repeat for stability:

```powershell
py -3 tkn-jarvis/thai_benchmark.py --case ambiguous_vocal_role --case negated_delete_false_positive --output work/thai-selected
py -3 tkn-jarvis/thai_benchmark.py --repeats 3 --output work/thai-repeated
```

Use distinct output directories for separate runs; results are overwritten in the specified directory. Up to 10 repeats are allowed; a single run is not evidence of stability across model versions or paraphrases.

## Acceptance policy

There are 31 cases covering polite commands, spoken Thai numbers, absolute/relative levels, direction, target selection, mute/negation, rename, EQ/compressor parameters, compound dependencies, vague references, duplicate names, contradictory requests, occupied slots, wrong effects, numeric limits, unsupported operations, injection and known conservative-guard false positives.

- The 30-case **primary score** excludes the vocal-chain example that overlaps the deployed prompt (`prompt_overlap`). That case remains in the report, separately labeled. These cases are a curated local regression set, not a held-out evaluation or representative population sample; no general Thai-language accuracy claim follows from the percentage.
- Explicit numeric values and track names must match. Absolute and relative volume intents are compared by their resulting absolute fader value, so equivalent encodings pass.
- The action list must be complete, with no extra edits, duplicates or silently omitted compound requests. Unnecessary commands on tracks that should remain unchanged are not accepted, even if they might be no-ops in that fixture.
- Ordering of independent edits/parameters is ignored for matching. The real engine adapter's dry preflight validates insert/parameter and rename dependencies in the generated order. No command is sent. The set does not include sequences of repeated edits to the same property whose final state depends on order.
- For the prompt-overlap vague chain only, omitted slot constraints allow any legal empty slot; preset numeric ranges are explicit acceptance policy. They do not rate perceived audio quality. Every requested effect and parameter must still appear, with no extra actions.
- For ambiguous/unsupported cases, a nonempty clarification with no actions passes. This checks deferral, not the linguistic quality of the question. Schema or dry-preflight rejection is recorded as a failure to provide the expected clarification, not quietly counted as correct understanding.
- A schema-valid and preflight-valid edit for a request that should defer is `unjustified_proposal`: a significant finding even though the benchmark's Apply fences prevent any write.
- A valid but wrong/partial/extra edit is `wrong_proposal`. An unnecessary clarification on a supported request is also a semantic failure. Conservative keyword-guard denials are separate from model responses.
- Errors remain in the primary denominator as non-passes. The report also counts model schema validity, correct deferrals, wrong proposals, unjustified proposals, local-guard cases and provider errors separately.

## Safety and reproducibility

The runner exposes no control port or Apply option. Runtime fences reject any call to `jarvis.request`, `intent_engine.apply_preview` or `jarvis_v1.apply`; the result records attempted calls. The regression suite includes a deliberately misbehaving callback to verify this fence. These protections cover the current adapter's paths, not arbitrary malicious code running with the same user's permissions.

Each result records case text, expected and actual intents, dry-preflight result, raw model response, elapsed time, provider call paths and model digest/details when available. Report metadata includes the baseline Git revision, dataset/engine/runner SHA-256 hashes, Python/platform and repeats. The uncommitted runner and dataset are identified by their hashes, not implied to exist in the baseline commit. Raw responses contain synthetic benchmark data only.

The existing engine may fail these tests. Preserve the baseline results before proposing changes; don't loosen expectations to make it pass. Changes to already committed engine files require the user's authorization under this project's current scope. Voice Control should retain human Preview → confirmation → Apply → Verify regardless of future benchmark improvements.

Step 5.2 was measured locally before the Step 5.3 fixes. The original Step 5 baseline is `2d949b56abbbda95840eabc318c51bbbe591b74e` on `develop/tkn-daw-v2-integration`. This benchmark runner does not modify source files or `main`; later authorized engine changes are described separately in `README_RELIABILITY.md`.

## Baseline measured on Windows, 2026-10-13

One run with installed `gemma3:4b` (digest `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`):

- Primary: **12/30 pass (40% on this acceptance set)**; prompt-overlap example passes separately, so total is 13/31.
- 25 model responses all pass schema validation; this does not establish semantic correctness. Six other cases return via the local guard.
- Correct deferral: 4/14 expected clarification cases. Nine cases produce schema-valid, dry-preflight-valid proposals where the policy requires clarification.
- Four wrong/extra proposals and two dry-preflight rejections are recorded. Three otherwise supported requests are over-rejected by the local guard, including Thai spoken negative numbers.
- Provider/runner errors: 0; attempted DAW calls: 0. The live runner intentionally returns exit 1 because acceptance failed.
- Unit suite: 71/71 pass (59 existing + 12 benchmark regressions). A correct test harness can expose failures in the engine; these results are not contradictory.

Examples: the guard treats `ลบหก dB` as deletion; a Kick-only fader request gets an extra compressor; a missing Bass target is redirected to Voice; parameter-only requests receive extra parameter writes; ambiguous vocals are both selected without asking. Generated summaries sometimes name a different track/slot than the actual action. Review concrete changes, never rely on the summary alone.

Recommended next work before voice integration: refine deletion-vs-negative-number handling, require explicit target/slot consistency and no unrequested operations, improve deferral for ambiguity/unsupported compound requests, and make rename dependencies representable in the schema. Preserve this failing baseline and rerun exactly the same cases after any authorized engine change. No engine fix is included here.
