"""V1 command and preflight regression tests. Actual desktop tested separately."""
import copy
import sys
import unittest
from unittest.mock import patch

import jarvis_v1 as v1


def snapshot():
    return {"tracks": [{"id": 7, "name": "Voice", "kind": "audio", "format": "Stereo",
                        "volume_db": -3.0, "mute": False, "inserts": []}], "undo": "Set Volume", "redo": None}


class V1Tests(unittest.TestCase):
    def test_supported_intents(self):
        cases = {"เพิ่ม EQ แทร็ก Voice ช่อง a": "mix.insert",
                 "เพิ่ม Compressor แทร็ก Voice ช่อง b": "mix.insert",
                 "ตั้ง EQ แทร็ก Voice ช่อง a freq 1200": "mix.insert_param",
                 "ตั้ง Compressor แทร็ก Voice ช่อง b threshold -18": "mix.insert_param",
                 "สร้างแทร็ก stereo ชื่อ Voice 2": "track.new",
                 "เปลี่ยนชื่อแทร็ก Voice เป็น Lead Vox": "track.rename",
                 "ปิดเสียงแทร็ก Voice": "mix.mute", "ย้อนกลับ": "edit.undo", "ทำซ้ำ": "edit.redo"}
        for text, command in cases.items():
            with self.subTest(text=text):
                self.assertEqual(v1.parse_instruction(text)["params"]["command"], command)

    def test_unsafe_or_invalid_input_rejected(self):
        for text in ("ลบแทร็ก Voice", "ตั้ง EQ แทร็ก Voice ช่อง a freq 1",
                     "ตั้ง EQ แทร็ก Voice ช่อง a gain 25", "ตั้ง Compressor แทร็ก Voice ช่อง b ratio 0",
                     "เพิ่ม EQ แทร็ก Voice ช่อง k", "สร้างแทร็ก stereo ชื่อ bad\x01name",
                     "ตั้ง EQ แทร็ก Voice ช่อง a gain nan"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                v1.parse_instruction(text)

    def test_id_resolution_does_not_mutate_preview(self):
        payload = v1.parse_instruction("เพิ่ม EQ แทร็ก Voice ช่อง a")
        prepared = v1.prepare(payload, snapshot())
        self.assertEqual(prepared["params"]["params"]["track"], 7)
        self.assertEqual(payload["params"]["params"]["track"], "Voice")

    def test_occupied_slot_is_not_overwritten(self):
        before = snapshot()
        before["tracks"][0]["inserts"] = [{"slot": 0, "plugin": "compressor", "params": {}}]
        with self.assertRaisesRegex(RuntimeError, "occupied"):
            v1.prepare(v1.parse_instruction("เพิ่ม EQ แทร็ก Voice ช่อง a"), before)

    def test_wrong_plugin_rejected_before_parameter_write(self):
        before = snapshot()
        before["tracks"][0]["inserts"] = [{"slot": 0, "plugin": "compressor", "params": {}}]
        with self.assertRaisesRegex(RuntimeError, "Expected effect"):
            v1.prepare(v1.parse_instruction("ตั้ง EQ แทร็ก Voice ช่อง a gain -3"), before)

    def test_name_collisions_and_ambiguous_target_rejected(self):
        for text in ("สร้างแทร็ก mono ชื่อ Voice", "เปลี่ยนชื่อแทร็ก Voice เป็น Voice"):
            with self.subTest(text=text), self.assertRaisesRegex(RuntimeError, "already exists"):
                v1.prepare(v1.parse_instruction(text), snapshot())
        before = snapshot()
        before["tracks"].append({**before["tracks"][0], "id": 8})
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            v1.prepare(v1.parse_instruction("ปิดเสียงแทร็ก Voice"), before)

    def test_redo_without_history_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "history"):
            v1.prepare(v1.parse_instruction("ทำซ้ำ"), snapshot())

    def test_failed_preflight_sends_only_inspection(self):
        with patch.object(v1.jarvis, "request", return_value={"result": snapshot()}) as request:
            with self.assertRaises(RuntimeError):
                v1.apply(v1.parse_instruction("เพิ่ม EQ แทร็ก Missing ช่อง a"), 7801)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[1]["method"], "session.inspect")

    def test_parameter_write_is_verified_and_local_metadata_not_sent(self):
        before = snapshot()
        before["tracks"][0]["inserts"] = [{"slot": 0, "plugin": "eq_1band", "params": {"gain": 0}}]
        after = copy.deepcopy(before)
        after["tracks"][0]["inserts"][0]["params"]["gain"] = -3
        with patch.object(v1.jarvis, "request", side_effect=[{"result": before}, {"result": {}}, {"result": after}]) as request:
            result = v1.apply(v1.parse_instruction("ตั้ง EQ แทร็ก Voice ช่อง a gain -3"), 7801)
        self.assertTrue(result["verified"])
        self.assertNotIn("expected_plugin", request.call_args_list[1].args[1])
        self.assertEqual(request.call_args_list[1].args[1]["params"]["params"]["track"], 7)

    def test_parameter_mismatch_is_failure(self):
        before = snapshot()
        before["tracks"][0]["inserts"] = [{"slot": 0, "plugin": "eq_1band", "params": {"gain": 0}}]
        plan = v1.prepare(v1.parse_instruction("ตั้ง EQ แทร็ก Voice ช่อง a gain -3"), before)
        with self.assertRaisesRegex(RuntimeError, "parameter verification"):
            v1.verify(plan, before, before, {"result": {}})

    def test_undo_result_must_confirm_operation(self):
        plan = v1.prepare(v1.parse_instruction("ย้อนกลับ"), snapshot())
        with self.assertRaisesRegex(RuntimeError, "History"):
            v1.verify(plan, snapshot(), snapshot(), {"result": {"undone": False}})
        v1.verify(plan, snapshot(), snapshot(), {"result": {"undone": True}})

    def test_offline_preview_does_not_connect(self):
        with patch.object(sys, "argv", ["jarvis_v1.py", "เพิ่ม EQ แทร็ก Voice ช่อง a"]), \
                patch.object(v1.jarvis, "request") as request, patch("builtins.print"):
            self.assertEqual(v1.main(), 0)
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
