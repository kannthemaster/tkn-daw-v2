"""Oracle and no-write benchmark regression tests; no model calls required."""
import copy
import unittest

import thai_benchmark as bench


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.data = bench.load_dataset(bench.DATASET)
        self.case = self.data["cases"][0]
        self.snapshot = self.data["profiles"]["basic"]

    def proposal(self, actions):
        return {"summary": "ข้อเสนอ", "clarification": "", "actions": actions}

    def test_dataset_case_ids_and_expected_profile_valid(self):
        self.assertEqual(len(self.data["cases"]), 31)
        for case in self.data["cases"]:
            if not case["expected"].get("clarify"):
                bench.normalize(case["expected"]["actions"], self.data["profiles"][case["profile"]])

    def test_equivalent_absolute_and_relative_volume(self):
        for op, value in (("volume_delta", -3), ("volume", -6)):
            result = bench.evaluate(self.case, self.snapshot, self.proposal([{"op": op, "track": "Voice", "db": value}]))
            self.assertEqual(result["status"], "PASS")

    def test_wrong_direction_and_wrong_track_fail(self):
        for track, value in (("Voice", 3), ("Kick", -3)):
            result = bench.evaluate(self.case, self.snapshot, self.proposal([{"op": "volume_delta", "track": track, "db": value}]))
            self.assertEqual(result["outcome"], "wrong_proposal")

    def test_extra_supported_action_not_silently_accepted(self):
        actions = self.case["expected"]["actions"] + [{"op": "mute", "track": "Voice", "value": True}]
        self.assertEqual(bench.evaluate(self.case, self.snapshot, self.proposal(actions))["status"], "FAIL")

    def test_omitted_compound_action_fails(self):
        case = next(c for c in self.data["cases"] if c["id"] == "two_tracks")
        result = bench.evaluate(case, self.snapshot, self.proposal(case["expected"]["actions"][:1]))
        self.assertEqual(result["status"], "FAIL")

    def test_asking_instead_of_clear_edit_is_failure(self):
        result = bench.evaluate(self.case, self.snapshot, {"summary": "", "clarification": "อะไรครับ?", "actions": []})
        self.assertEqual(result["status"], "FAIL")

    def test_unjustified_valid_proposal_is_failure(self):
        case = {**self.case, "expected": {"clarify": True}}
        result = bench.evaluate(case, self.snapshot, self.proposal(self.case["expected"]["actions"]))
        self.assertEqual(result["outcome"], "unjustified_proposal")

    def test_preflight_rejection_is_not_correct_clarification(self):
        case = {**self.case, "expected": {"clarify": True}}
        result = bench.evaluate(case, self.snapshot, self.proposal([{"op": "mute", "track": "Missing", "value": True}]))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["outcome"], "preflight_rejected")

    def test_matching_ranges_backtracks_and_checks_boolean_types(self):
        self.assertTrue(bench.complete_match([{"value": 1}, {"value": 2}], [{"value": {"min": 1, "max": 2}}, {"value": 1}]))
        self.assertFalse(bench.matches({"value": True}, {"value": 1}))

    def test_engine_connection_is_fenced_and_counted(self):
        def malicious(text, snapshot, model):
            return bench.ai.jarvis.request(7801, bench.ai.INSPECT)
        result = bench.run_case(self.case, self.snapshot, "fixture", malicious)
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["daw_attempts"], 1)
        self.assertIn("BENCHMARK VIOLATION", result["error"])

    def test_fixture_and_snapshot_are_not_mutated(self):
        before = copy.deepcopy(self.snapshot)
        def proposer(text, snapshot, model):
            snapshot["tracks"] = []
            return self.proposal(self.case["expected"]["actions"])
        result = bench.run_case(self.case, self.snapshot, "fixture", proposer)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(self.snapshot, before)

    def test_prompt_overlap_and_provider_errors_not_inflating_accuracy(self):
        base = {"category": "clear", "expected": {"clarify": True}, "source": "model", "outcome": "clarification", "schema_valid": True}
        rows = [{**base, "status": "PASS"}, {**base, "status": "ERROR"},
                {**base, "category": "prompt_overlap", "status": "PASS"}]
        summary = bench.summarize(rows)
        self.assertEqual(summary["primary_accuracy"], .5)
        self.assertEqual(summary["errors"], 1)


if __name__ == "__main__":
    unittest.main()
