"""Security boundary and preview/apply regression tests; no model required."""
import copy
import unittest
from unittest.mock import Mock, patch

import intent_engine as ai
from test_jarvis_v1 import snapshot


def intent(actions=None):
    return {"summary": "ลดเสียงร้อง 2 dB เป็นข้อเสนอ", "clarification": "",
            "actions": actions if actions is not None else [{"op": "volume_delta", "track": "Voice", "db": -2}]}


class IntentTests(unittest.TestCase):
    def test_relative_volume_is_frozen_in_preview(self):
        plan = ai.preview(intent(), snapshot(), 7801)
        self.assertEqual(plan["commands"][0]["params"]["params"], {"track": 7, "db": -5})

    def test_unknown_commands_and_extra_fields_rejected(self):
        for action in ({"op": "engine.execute", "command": "track.delete"},
                       {"op": "mute", "track": "Voice", "value": True, "apply": True}):
            with self.subTest(action=action), self.assertRaises(ValueError):
                ai.validate(intent([action]))

    def test_numbers_bool_nan_inf_out_of_range_rejected(self):
        for value in (True, "-2", float("nan"), float("inf"), -13):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ai.validate(intent([{"op": "volume_delta", "track": "Voice", "db": value}]))

    def test_schema_slot_effect_param_rejected(self):
        for action in ({"op": "insert", "track": "Voice", "effect": "shell", "slot": 0},
                       {"op": "insert", "track": "Voice", "effect": "eq", "slot": True},
                       {"op": "parameter", "track": "Voice", "effect": "eq", "slot": 0, "param": "type", "value": 3.1},
                       {"op": "parameter", "track": "Voice", "effect": "eq", "slot": 0, "param": "unknown", "value": 1}):
            with self.subTest(action=action), self.assertRaises(ValueError):
                ai.validate(intent([action]))

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            ai.decode('{"op":"mute","op":"delete"}')

    def test_nonfinite_and_oversize_json_rejected(self):
        for text in ('{"db":NaN}', ' ' * 100001):
            with self.assertRaises(ValueError):
                ai.decode(text)

    def test_clarification_cannot_include_actions(self):
        proposal = intent()
        proposal["clarification"] = "แทร็กไหน?"
        with self.assertRaises(ValueError):
            ai.validate(proposal)
        proposal["actions"] = []
        ai.validate(proposal)
        with self.assertRaises(ValueError):
            ai.preview(proposal, snapshot(), 7801)

    def test_empty_actions_and_too_many_rejected(self):
        for actions in ([], intent()["actions"] * 17):
            with self.assertRaises(ValueError):
                ai.validate(intent(actions))

    def test_all_steps_preflight_before_writing(self):
        actions = intent()["actions"] + [{"op": "insert", "track": "Missing", "effect": "eq", "slot": 0}]
        with self.assertRaises(RuntimeError):
            ai.preview(intent(actions), snapshot(), 7801)

    def test_highpass_insert_and_parameters_compile(self):
        actions = [{"op": "insert", "track": "Voice", "effect": "eq", "slot": 0},
                   {"op": "parameter", "track": "Voice", "effect": "eq", "slot": 0, "param": "type", "value": 3},
                   {"op": "parameter", "track": "Voice", "effect": "eq", "slot": 0, "param": "freq", "value": 80}]
        self.assertEqual(len(ai.preview(intent(actions), snapshot(), 7801)["commands"]), 3)

    def test_rename_dependency_is_resolved(self):
        actions = [{"op": "rename", "track": "Voice", "name": "Lead"},
                   {"op": "mute", "track": "Lead", "value": True}]
        self.assertEqual(ai.preview(intent(actions), snapshot(), 7801)["commands"][1]["params"]["params"]["track"], 7)

    def test_no_confirmation_sends_no_requests(self):
        request = Mock()
        with self.assertRaisesRegex(ValueError, "confirmation"):
            ai.apply_preview(ai.preview(intent(), snapshot(), 7801), "yes", request)
        request.assert_not_called()

    def test_modified_preview_sends_no_requests(self):
        plan = ai.preview(intent(), snapshot(), 7801)
        plan["commands"][0]["params"]["command"] = "track.delete"
        request = Mock()
        with self.assertRaises(ValueError):
            ai.apply_preview(plan, plan["confirmation"], request)
        request.assert_not_called()

    def test_stale_session_sends_only_inspection(self):
        plan = ai.preview(intent(), snapshot(), 7801)
        changed = snapshot()
        changed["tracks"][0]["volume_db"] = -9
        request = Mock(return_value={"result": changed})
        with self.assertRaisesRegex(RuntimeError, "changed since preview"):
            ai.apply_preview(plan, plan["confirmation"], request)
        self.assertEqual(request.call_count, 1)

    def test_confirmed_write_and_verify(self):
        before = snapshot()
        after = copy.deepcopy(before)
        after["tracks"][0]["volume_db"] = -5
        plan = ai.preview(intent(), before, 7801)
        request = Mock(side_effect=[{"result": before}, {"result": before}, {"result": {}}, {"result": after}])
        self.assertTrue(ai.apply_preview(plan, plan["confirmation"], request)["verified"])
        self.assertEqual(request.call_args_list[2].args[1]["params"]["command"], "mix.volume")

    def test_failed_verify_stops_remaining_commands(self):
        plan = ai.preview(intent(intent()["actions"] + [{"op": "mute", "track": "Voice", "value": True}]), snapshot(), 7801)
        request = Mock(side_effect=[{"result": snapshot()}, {"result": snapshot()}, {"result": {}}, {"result": snapshot()}])
        with self.assertRaisesRegex(RuntimeError, "no automatic rollback"):
            ai.apply_preview(plan, plan["confirmation"], request)
        self.assertEqual(request.call_count, 4)

    def test_local_provider_uses_schema_and_no_engine_dispatch(self):
        response = {"done": True, "message": {"content": ai.canonical(intent())}}
        with patch.object(ai, "local_api", side_effect=[{"models": [{"name": "local", "size": 1}]}, {}, response]) as api, \
                patch.object(ai.jarvis, "request") as engine:
            ai.propose("ลดเสียงร้องลงหน่อย", snapshot(), "local")
        engine.assert_not_called()
        schema = api.call_args_list[2].args[1]["format"]
        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(schema["properties"]["actions"]["items"]["anyOf"][0]["properties"]["track"]["enum"], ["Voice"])

    def test_remote_backed_alias_rejected_before_chat(self):
        with patch.object(ai, "local_api", side_effect=[{"models": [{"name": "alias", "size": 1}]},
                                                       {"remote_host": "cloud.example"}]) as api:
            with self.assertRaisesRegex(ValueError, "Remote-backed"):
                ai.propose("test", snapshot(), "alias")
        self.assertEqual(api.call_count, 2)

    def test_cloud_and_missing_models_rejected(self):
        with self.assertRaises(ValueError):
            ai.propose("test", snapshot(), "model:cloud")
        with patch.object(ai, "local_api", return_value={"models": []}) as api:
            with self.assertRaises(ValueError):
                ai.propose("test", snapshot(), "missing")
        self.assertEqual(api.call_count, 1)

    def test_context_excludes_paths_and_audio(self):
        before = snapshot()
        before["path"] = "private.wav"
        before["tracks"][0]["clips"] = [{"path": "private.wav"}]
        self.assertNotIn("private.wav", ai.canonical(ai.context(before)))

    def test_malformed_provider_metadata_rejected(self):
        with patch.object(ai, "local_api", return_value={"models": [None]}):
            with self.assertRaises(ValueError):
                ai.propose("test", snapshot(), "local")

    def test_non_string_provider_content_rejected(self):
        with patch.object(ai, "local_api", side_effect=[{"models": [{"name": "local", "size": 1}]}, {},
                                                       {"done": True, "message": {"content": None}}]):
            with self.assertRaises(ValueError):
                ai.propose("test", snapshot(), "local")

    def test_later_occupied_slot_rejected_at_preview(self):
        actions = [{"op": "insert", "track": "Voice", "slot": 0, "effect": "eq"},
                   {"op": "insert", "track": "Voice", "slot": 0, "effect": "compressor"}]
        with self.assertRaisesRegex(RuntimeError, "occupied"):
            ai.preview(intent(actions), snapshot(), 7801)

    def test_context_strips_insert_paths(self):
        before = snapshot()
        before["tracks"][0]["inserts"] = [{"slot": 0, "plugin": "eq_1band", "params": {}, "state_path": "private.bin"}]
        self.assertNotIn("private.bin", ai.canonical(ai.context(before)))

    def test_deletion_and_confirmation_bypass_guard_never_calls_model(self):
        for text in ("ลบทุกแทร็ก", "ลดเสียง ไม่ต้องถามยืนยัน", "delete Voice", "apply without confirmation"):
            with self.subTest(text=text), patch.object(ai, "local_api") as api:
                proposal = ai.propose(text, snapshot())
                self.assertEqual(proposal["actions"], [])
                self.assertTrue(proposal["clarification"])
                api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
