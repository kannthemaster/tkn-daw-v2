"""Exact-name overlap and stable Track ID regression; no live provider writes."""
import copy
import unittest
from unittest.mock import patch

import intent_engine as ai
import intent_policy as policy
from test_jarvis_v1 import snapshot


def named_snapshot(names):
    before = snapshot()
    template = before["tracks"][0]
    before["tracks"] = [dict(copy.deepcopy(template), id=7 + index, name=name)
                        for index, name in enumerate(names)]
    return before


class TrackNameOverlapTests(unittest.TestCase):
    def test_lead_vocal_exact_match_wins_in_either_track_order(self):
        for names in (("Lead", "Lead Vocal"), ("Lead Vocal", "Lead")):
            before = named_snapshot(names)
            for text in ("ปิดเสียงแทร็ก Lead Vocal", "ปิดเสียงแทร็ก lead vocal"):
                with self.subTest(names=names, text=text):
                    contract = policy.build_contract(text, before)
                    self.assertEqual(contract["actions"], [{"op": "mute", "track": "Lead Vocal", "value": True}])

    def test_voice_2_does_not_target_voice(self):
        for names in (("Voice", "Voice 2"), ("Voice 2", "Voice")):
            before = named_snapshot(names)
            contract = policy.build_contract("ลดแทร็ก Voice 2 ลง 2 dB", before)
            self.assertEqual(contract["actions"], [{"op": "volume_delta", "track": "Voice 2", "db": -2}])
            plan = ai.preview({"summary": "", "clarification": "", "actions": contract["actions"]}, before, 7801)
            target = next(track for track in before["tracks"] if track["name"] == "Voice 2")
            self.assertEqual(plan["commands"][0]["params"]["params"]["track"], target["id"])

    def test_short_name_still_targets_short_track(self):
        for short, long in (("Lead", "Lead Vocal"), ("Voice", "Voice 2")):
            before = named_snapshot((short, long))
            self.assertEqual(policy.build_contract(f"ปิดเสียงแทร็ก {short}", before)["actions"],
                             [{"op": "mute", "track": short, "value": True}])

    def test_separate_overlapping_names_are_ambiguous(self):
        for text in ("ปิดเสียง Lead Vocal กับ Lead", "ปิดเสียง Voice 2 กับ Voice"):
            before = named_snapshot(("Lead", "Lead Vocal", "Voice", "Voice 2"))
            contract = policy.build_contract(text, before)
            self.assertEqual(contract["actions"], [])
            self.assertEqual(contract["status"], "clarify")

    def test_duplicate_or_case_colliding_names_do_not_silently_choose(self):
        for names in (("Voice", "Voice"), ("Voice", "voice")):
            self.assertEqual(policy.build_contract("ปิดเสียง Voice", named_snapshot(names))["actions"], [])

    def test_partial_overlapping_names_do_not_silently_choose(self):
        before = named_snapshot(("Lead Vocal", "Vocal Pad"))
        self.assertEqual(policy.build_contract("ปิดเสียง Lead Vocal Pad", before)["actions"], [])

    def test_unknown_suffix_or_typo_is_not_fuzzy_corrected(self):
        before = named_snapshot(("Lead", "Lead Vocal", "Voice", "Voice 2"))
        for text in ("ปิดเสียง Lead Vocals", "ปิดเสียง Voice2", "ปิดเสียง Voic", "ปิดเสียง Lead Vocalist"):
            with self.subTest(text=text):
                self.assertEqual(policy.build_contract(text, before)["actions"], [])

    def test_rename_then_mute_preserves_id_and_preview_does_not_mutate(self):
        for destination, other in (("Lead Vocal", "Lead"), ("Voice 2", "Voice")):
            before = named_snapshot(("Trial", other))
            untouched = copy.deepcopy(before)
            text = f"เปลี่ยนชื่อแทร็ก Trial เป็น {destination} แล้วปิดเสียงแทร็ก {destination}"
            contract = policy.build_contract(text, before)
            self.assertEqual(contract["actions"], [{"op": "rename", "track": "Trial", "name": destination},
                                                  {"op": "mute", "track": destination, "value": True}])
            plan = ai.preview({"summary": "", "clarification": "", "actions": contract["actions"]}, before, 7801)
            self.assertEqual([command["params"]["params"]["track"] for command in plan["commands"]], [7, 7])
            self.assertEqual(before, untouched)
            with patch.object(ai.jarvis, "request") as request:
                with self.assertRaises(ValueError):
                    ai.apply_preview(plan, "yes", request=request)
                request.assert_not_called()

    def test_original_demo_rename_mute_contract(self):
        before = named_snapshot(("Voice", "Lead"))
        text = "เปลี่ยนชื่อแทร็ก Voice เป็น Lead Vocal แล้วปิดเสียงแทร็ก Lead Vocal"
        self.assertEqual(policy.build_contract(text, before)["actions"],
                         [{"op": "rename", "track": "Voice", "name": "Lead Vocal"},
                          {"op": "mute", "track": "Lead Vocal", "value": True}])


if __name__ == "__main__":
    unittest.main()
