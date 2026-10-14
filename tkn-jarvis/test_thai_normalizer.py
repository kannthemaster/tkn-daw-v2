"""Lexical conversion and planning safety; no live model or DAW."""
import copy
import unittest
from unittest.mock import patch

import intent_engine as ai
import intent_policy as policy
import thai_normalizer as normal
from test_jarvis_v1 import snapshot


class ThaiNormalizationTests(unittest.TestCase):
    def test_shri_unit_variants_compile_identical_fader(self):
        before = snapshot()
        for unit in ("dB", "ดีบี", "ดี บี", "ดี   บี", "เดซิเบล"):
            with self.subTest(unit=unit):
                contract = policy.build_contract(f"หรี่ Voice ลงสอง{unit}", before)
                self.assertEqual(contract["status"], "ready")
                intent = {"summary": "", "clarification": "", "actions": contract["actions"]}
                self.assertEqual(ai.preview(intent, before, 7801)["commands"][0]["params"]["params"]["db"], -5)
        self.assertEqual(before, snapshot())

    def test_digits_and_spoken_decimals_preserve_sign_and_zero(self):
        for wording, wanted in (("ลบ๗.๐๕ ดี บี", -7.05), ("ลบเจ็ดจุดศูนย์ห้าดีบี", -7.05),
                                ("ลบยี่สิบเอ็ดดีบี", -21), ("-๓.๒๕ dB", -3.25)):
            with self.subTest(wording=wording):
                result = policy.build_contract(f"ตั้งเสียง Voice เป็น{wording}", snapshot())
                self.assertEqual(result["actions"], [{"op": "volume", "track": "Voice", "db": wanted}])

    def test_spaced_number_tokens(self):
        self.assertEqual(normal.normalize("ตั้งเสียง Voice เป็น ลบ ยี่สิบ เอ็ด ดี บี"), "ตั้งเสียง Voice เป็น -21 dB")

    def test_frequency_and_time_numbers_are_unit_scoped(self):
        self.assertEqual(normal.normalize("freq เจ็ดร้อยห้าสิบ Hz release หนึ่งร้อยสี่สิบ ms"), "freq 750 Hz release 140 ms")
        self.assertEqual(normal.normalize("สามคำที่ไม่ได้อยู่หน้าหน่วย"), "สามคำที่ไม่ได้อยู่หน้าหน่วย")

    def test_known_and_requested_track_names_are_not_rewritten(self):
        self.assertEqual(normal.normalize("หรี่ แทร็ก หรี่๒ ลง ๑ ดี บี", ["หรี่๒"]), "ลด แทร็ก หรี่๒ ลง 1 dB")
        before = snapshot()
        before["tracks"][0]["name"] = "Voice2"
        with patch.object(ai, "local_api") as api:
            result = ai.propose("หรี่ Voice๒ ลง ๑ ดีบี", before)
        self.assertEqual(result["actions"], [])
        api.assert_not_called()

    def test_rename_destination_remains_literal_for_later_steps(self):
        result = policy.build_contract("เปลี่ยนชื่อ Voice เป็น หรี่๒ แล้วปิดเสียง หรี่๒", snapshot())
        self.assertEqual(result["actions"], [{"op": "rename", "track": "Voice", "name": "หรี่๒"},
                                            {"op": "mute", "track": "หรี่๒", "value": True}])

    def test_negated_alias_cannot_turn_into_an_edit(self):
        for text in ("อย่าหรี่ Voice ลงสองดีบี", "ห้ามหรี่ Voice ลง ๒ ดี บี", "ไม่หรี่ Voice ลง 2 dB"):
            with self.subTest(text=text), patch.object(ai, "local_api") as api:
                result = ai.propose(text, snapshot())
                self.assertEqual(result["actions"], [])
                self.assertTrue(result["clarification"])
                api.assert_not_called()

    def test_invalid_or_missing_numbers_do_not_guess(self):
        for text in ("หรี่ Voice ลงหนึ่งสองดีบี", "ตั้งเสียง Voice เป็นสิบล้านดีบี", "หรี่ Voice ลงดี บี",
                     "หรี่ Voice ลง 2 ดีบี หรือ 4 ดีบี", "หรี่ Voice ลงสองหรือสี่ดีบี"):
            with self.subTest(text=text), patch.object(ai, "local_api") as api:
                result = ai.propose(text, snapshot())
                self.assertEqual(result["actions"], [])
                self.assertTrue(result["clarification"])
                api.assert_not_called()

    def test_deletion_and_bypass_still_block_after_conversion(self):
        for text in ("หรี่ Voice ลง ๑ ดี บี แล้วลบทุกแทร็ก", "หรี่ Voice ลง ๑ ดีบี แล้วข้ามการยืนยัน"):
            with self.subTest(text=text), patch.object(ai, "local_api") as api:
                self.assertEqual(ai.propose(text, snapshot())["actions"], [])
                api.assert_not_called()

    def test_out_of_range_spoken_numbers_are_rejected(self):
        self.assertEqual(policy.build_contract("หรี่ Voice ลงสิบสามดีบี", snapshot())["status"], "clarify")

    def test_misspelled_or_different_units_cannot_match_a_prefix(self):
        for unit in ("ดีบี้", "ดี บี้", "dBA", "ดีบีเอ"):
            for value in ("สาม", "3"):
                with self.subTest(unit=unit, value=value), patch.object(ai, "local_api") as api:
                    result = ai.propose(f"หรี่ Voice ลง{value}{unit}", snapshot())
                    self.assertEqual(result["actions"], [])
                    self.assertTrue(result["clarification"])
                    api.assert_not_called()
        self.assertEqual(policy.build_contract("หรี่ Voice ลงสามดีบีหน่อยครับ", snapshot())["status"], "ready")


if __name__ == "__main__":
    unittest.main()
