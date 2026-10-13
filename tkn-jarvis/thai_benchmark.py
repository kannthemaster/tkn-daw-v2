"""Read-only Thai intent benchmark: synthetic fixtures, Ollama only, no DAW calls."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import time
from unittest.mock import patch

import intent_engine as ai

DATASET = Path(__file__).with_name("thai_benchmark.json")


def load_dataset(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("cases"), list) or not data["cases"]:
        raise ValueError("Invalid benchmark dataset")
    ids = set()
    for case in data["cases"]:
        if case["id"] in ids or case["profile"] not in data["profiles"]:
            raise ValueError("Duplicate case or missing fixture")
        ids.add(case["id"])
        ai.context(data["profiles"][case["profile"]])
        expected = case["expected"]
        if expected == {"clarify": True}:
            continue
        if set(expected) != {"actions"} or not expected["actions"]:
            raise ValueError("Expected clarification or nonempty actions")
        for action in expected["actions"]:
            fields = ai.FIELDS.get(action["op"])
            if fields is None or not {"op", "track"} <= set(action) or not set(action) <= {"op", *fields}:
                raise ValueError("Invalid action oracle")
    return data


def normalize(actions, snapshot):
    """Compare volume effects, not a model's choice of absolute/relative encoding."""
    simulated, result = copy.deepcopy(snapshot), []
    for original in actions:
        action = copy.deepcopy(original)
        target = ai.v1.find_track(simulated, action["track"])
        if action["op"] in ("volume", "volume_delta"):
            value = action["db"]
            if action["op"] == "volume_delta":
                value += target["volume_db"]
            action.update(op="volume", db=value)
            target["volume_db"] = value
        elif action["op"] == "rename":
            target["name"] = action["name"]
        result.append(action)
    return result


def matches(actual, expected):
    for key, wanted in expected.items():
        if key not in actual:
            return False
        value = actual[key]
        if isinstance(wanted, dict) and set(wanted) == {"min", "max"}:
            if type(value) not in (int, float) or not math.isfinite(value) or not wanted["min"] <= value <= wanted["max"]:
                return False
        elif type(wanted) in (int, float):
            if type(value) not in (int, float) or not math.isclose(value, wanted, abs_tol=1e-5, rel_tol=0):
                return False
        elif type(value) is not type(wanted) or value != wanted:
            return False
    return True


def complete_match(actual, expected):
    # Backtracking avoids greedy matching mistakes when acceptance ranges overlap.
    if len(actual) != len(expected):
        return False
    if not expected:
        return True
    for index, action in enumerate(actual):
        if matches(action, expected[0]) and complete_match(actual[:index] + actual[index + 1:], expected[1:]):
            return True
    return False


def evaluate(case, snapshot, intent):
    intent = ai.validate(intent)
    if intent["clarification"].strip():
        return {"status": "PASS" if case["expected"].get("clarify") else "FAIL",
                "outcome": "clarification", "schema_valid": True, "preflight_valid": None}
    try:
        ai.compile_actions(intent, snapshot)
    except (ValueError, RuntimeError, KeyError, TypeError) as error:
        return {"status": "FAIL", "outcome": "preflight_rejected", "error": str(error),
                "schema_valid": True, "preflight_valid": False}
    if case["expected"].get("clarify"):
        return {"status": "FAIL", "outcome": "unjustified_proposal",
                "schema_valid": True, "preflight_valid": True}
    actual = normalize(intent["actions"], snapshot)
    expected = normalize(case["expected"]["actions"], snapshot)
    correct = complete_match(actual, expected)
    return {"status": "PASS" if correct else "FAIL", "outcome": "correct_proposal" if correct else "wrong_proposal",
            "schema_valid": True, "preflight_valid": True, "normalized_actual": actual, "normalized_expected": expected}


def run_case(case, snapshot, model, proposer=None):
    start, calls, raw, model_info, daw_attempts = time.monotonic(), [], None, None, 0
    real_api = ai.local_api
    def audited_api(path, *args, **kwargs):
        nonlocal raw, model_info
        response = real_api(path, *args, **kwargs)
        calls.append(path)
        if path == "chat":
            raw = response
        if path == "tags":
            model_info = next(({key: item.get(key) for key in ("name", "digest", "size", "details")}
                               for item in response.get("models", []) if isinstance(item, dict) and item.get("name") == model), None)
        return response
    def forbidden(*args, **kwargs):
        nonlocal daw_attempts
        daw_attempts += 1
        raise RuntimeError("BENCHMARK VIOLATION: DAW inspection/application is forbidden")
    record = {"id": case["id"], "category": case["category"], "text": case["text"],
              "profile": case["profile"], "expected": case["expected"], "fixture_sha256": ai.digest(snapshot)}
    try:
        # Runtime fences cover accidental use of existing controller entry points.
        with patch.object(ai.jarvis, "request", forbidden), patch.object(ai, "apply_preview", forbidden), \
                patch.object(ai.v1, "apply", forbidden), patch.object(ai, "local_api", audited_api):
            proposal = (proposer or ai.propose)(case["text"], copy.deepcopy(snapshot), model)
            record["intent"] = proposal
            record.update(evaluate(case, snapshot, proposal))
    except ValueError as error:
        record.update(status="FAIL", outcome="validation_rejected", schema_valid=False, preflight_valid=None, error=str(error))
    except (OSError, RuntimeError, KeyError, TypeError, AttributeError) as error:
        record.update(status="ERROR", outcome="provider_or_runner_error", error=str(error))
    record.update(elapsed_seconds=round(time.monotonic() - start, 3), api_calls=calls,
                  daw_attempts=daw_attempts, model_info=model_info,
                  source="local_guard" if not calls and "intent" in record and proposer is None else "model" if "chat" in calls else "fixture" if proposer else "provider_error")
    if raw is not None:
        record["raw_model_response"] = raw
    return record


def summarize(records):
    primary = [row for row in records if row["category"] != "prompt_overlap"]
    model = [row for row in records if row["source"] == "model"]
    negative = [row for row in primary if row["expected"].get("clarify")]
    categories = {}
    for row in records:
        counts = categories.setdefault(row["category"], {"total": 0, "passed": 0, "failed": 0, "errors": 0})
        counts["total"] += 1
        counts[{"PASS": "passed", "FAIL": "failed", "ERROR": "errors"}[row["status"]]] += 1
    passed = sum(row["status"] == "PASS" for row in primary)
    return {"total": len(records), "primary_total": len(primary), "primary_passed": passed,
            "daw_attempts": sum(row.get("daw_attempts", 0) for row in records),
            "primary_accuracy": passed / len(primary) if primary else None,
            "errors": sum(row["status"] == "ERROR" for row in records),
            "model_responses": len(model), "model_schema_valid": sum(row.get("schema_valid") is True for row in model),
            "local_guard_cases": sum(row["source"] == "local_guard" for row in records),
            "clarification_expected": len(negative), "clarification_correct": sum(row["status"] == "PASS" for row in negative),
            "unjustified_proposals": sum(row["outcome"] == "unjustified_proposal" for row in records),
            "wrong_proposals": sum(row["outcome"] == "wrong_proposal" for row in records), "categories": categories}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "work/thai-benchmark")
    parser.add_argument("--case", action="append", help="Run only specified IDs (repeatable)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--validate-only", action="store_true", help="Validate dataset; no model calls")
    args = parser.parse_args()
    data = load_dataset(args.dataset)
    if not 1 <= args.repeats <= 10:
        parser.error("repeats must be 1..10")
    cases = data["cases"]
    if args.case:
        if not set(args.case) <= {case["id"] for case in cases}:
            parser.error("Unknown case ID")
        cases = [case for case in cases if case["id"] in args.case]
    if args.validate_only:
        print(f"Dataset valid: {len(cases)} selected cases; no model or DAW calls")
        return 0
    args.output.mkdir(parents=True, exist_ok=True)
    def revision(command):
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else "unavailable"
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "model": args.model,
              "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
              "engine_sha256": hashlib.sha256(Path(ai.__file__).read_bytes()).hexdigest(),
              "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "git_revision": revision(["git", "rev-parse", "HEAD"]), "python": platform.python_version(),
              "platform": platform.platform(), "repeats": args.repeats, "synthetic_sessions": True,
              "daw_calls_allowed": False, "limitations": "Hand-authored acceptance set, not population accuracy; prompt-overlap case excluded from primary score.",
              "records": []}
    for repeat in range(args.repeats):
        for case in cases:
            record = run_case(case, data["profiles"][case["profile"]], args.model)
            record["repeat"] = repeat + 1
            report["records"].append(record)
            report["summary"] = summarize(report["records"])
            (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{len(report['records'])}/{len(cases) * args.repeats} {case['id']}: {record['status']} {record['outcome']} ({record['elapsed_seconds']}s)", flush=True)
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = report["summary"]
    lines = ["# Thai Intent Benchmark", "", f"Model: {args.model}; revision: {report['git_revision']}",
             f"Primary: {summary['primary_passed']}/{summary['primary_total']} (includes errors as non-passes).", "",
             "| Case | Category | Result | Outcome | Source | Seconds |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {r['id']} | {r['category']} | {r['status']} | {r['outcome']} | {r['source']} | {r['elapsed_seconds']} |" for r in report["records"])
    lines.extend(["", "No SoundCraft connection or Apply. Results measure a curated acceptance set only.",
                  "Clarification, local guards, schema rejection and preflight rejection are reported separately.",
                  "See results.json for expected/actual values, raw responses and reproducibility hashes."])
    (args.output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(r["status"] == "PASS" for r in report["records"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
