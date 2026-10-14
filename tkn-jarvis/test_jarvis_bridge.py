"""Bridge lifecycle and command boundary tests, including actual JSONL process."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

import jarvis_bridge as bridge
from test_intent_engine import intent
from test_jarvis_v1 import snapshot


def message(method, **fields):
    return {"version": 1, "id": 1, "method": method, **fields}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.before = snapshot()
        self.request = Mock(return_value={"result": self.before})
        self.propose = Mock(return_value=intent())
        self.bridge = bridge.Bridge(7801, request=self.request, propose=self.propose)

    def preview(self):
        return self.bridge.handle(message("preview", context="session1/input1", instruction="ลด Voice ลง 2 dB"))["result"]

    def apply(self, plan, **overrides):
        fields = {"context": "session1/input1", "instruction": "ลด Voice ลง 2 dB",
                  "preview_id": plan["preview_id"], "confirmation": plan["confirmation"], "confirmed": True}
        fields.update(overrides)
        return self.bridge.handle(message("apply", **fields))

    def test_preview_only_inspects_and_exposes_concrete_id_and_fader(self):
        plan = self.preview()
        self.request.assert_called_once_with(7801, bridge.ai.INSPECT)
        self.assertEqual(plan["changes"][0]["track_id"], 7)
        self.assertEqual(plan["changes"][0]["absolute_fader_db"], -5)
        self.assertEqual(plan["commands"][0]["params"]["params"], {"track": 7, "db": -5})
        self.assertNotIn("baseline", plan)

    def test_cancel_and_shutdown_never_dispatch(self):
        self.preview()
        self.request.reset_mock()
        self.bridge.handle(message("cancel", context="changed"))
        self.bridge.handle(message("shutdown"))
        self.request.assert_not_called()
        self.assertTrue(self.bridge.closed)

    def test_context_text_token_and_confirmation_fail_before_requests(self):
        for fields in ({"context": "other"}, {"instruction": "เพิ่ม Voice"}, {"preview_id": "old"},
                       {"confirmation": "yes"}, {"confirmed": False}, {"confirmed": "true"}):
            with self.subTest(fields=fields):
                plan = self.preview()
                self.request.reset_mock()
                reply = self.apply(plan, **fields)
                self.assertFalse(reply["ok"])
                self.assertFalse(reply["error"]["may_have_written"])
                self.request.assert_not_called()
                self.assertIsNone(self.bridge.pending)

    def test_stale_session_refused_after_read_only_inspection(self):
        plan = self.preview()
        changed = copy.deepcopy(self.before)
        changed["tracks"][0]["volume_db"] = -9
        self.request.reset_mock()
        self.request.return_value = {"result": changed}
        reply = self.apply(plan)
        self.assertFalse(reply["ok"])
        self.assertFalse(reply["error"]["may_have_written"])
        self.request.assert_called_once_with(7801, bridge.ai.INSPECT)

    def test_confirmed_apply_uses_existing_verify_and_cannot_replay(self):
        plan = self.preview()
        after = copy.deepcopy(self.before)
        after["tracks"][0]["volume_db"] = -5
        self.request.side_effect = [{"result": self.before}, {"result": self.before},
                                    {"ok": True, "result": {}}, {"result": after}]
        reply = self.apply(plan)
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["result"]["state"], "verified")
        self.assertTrue(reply["result"]["steps"][0]["verified"])
        self.request.reset_mock()
        self.assertFalse(self.apply(plan)["ok"])
        self.request.assert_not_called()

    def test_failed_verify_reports_possible_write_and_consumes_plan(self):
        plan = self.preview()
        self.request.side_effect = [{"result": self.before}, {"result": self.before},
                                    {"ok": True, "result": {}}, {"result": self.before}]
        reply = self.apply(plan)
        self.assertFalse(reply["ok"])
        self.assertTrue(reply["error"]["may_have_written"])
        self.assertIsNone(self.bridge.pending)

    def test_extra_fields_arbitrary_commands_and_invalid_versions_rejected(self):
        for msg in (message("engine.execute", command="track.delete"), message("status", port=9999),
                    {**message("status"), "version": True}, {**message("status"), "id": True}):
            with self.subTest(msg=msg):
                self.assertFalse(self.bridge.handle(msg)["ok"])
        self.request.assert_not_called()

    def test_clarification_leaves_no_apply_plan(self):
        self.propose.return_value = {"summary": "", "clarification": "แทร็กไหน", "actions": []}
        self.assertEqual(self.preview()["state"], "clarification")
        self.assertIsNone(self.bridge.pending)

    def test_jsonl_rejects_duplicate_keys_and_survives_bad_json(self):
        source = io.BytesIO(b'{"version":1,"id":1,"method":"status","method":"apply"}\nno json\n' +
                            json.dumps(message("shutdown")).encode() + b'\n')
        sink = io.StringIO()
        bridge.serve(self.bridge, source, sink)
        replies = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual([reply["ok"] for reply in replies], [True, False, False, True])
        self.request.assert_not_called()

    def test_oversized_line_closes_without_processing_trailing_commands(self):
        sink = io.StringIO()
        bridge.serve(self.bridge, io.BytesIO(b'x' * (bridge.MAX_REQUEST + 1) + b'\n'), sink)
        self.assertEqual(len(sink.getvalue().splitlines()), 2)
        self.request.assert_not_called()

    def test_real_process_utf8_ready_status_shutdown_and_clean_stdout(self):
        command = [sys.executable, "-B", str(Path(bridge.__file__)), "--port", "7801"]
        wire = "\n".join(json.dumps(message(method)) for method in ("status", "shutdown")) + "\n"
        result = subprocess.run(command, input=wire, capture_output=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r["result"]["state"] for r in replies], ["ready", "idle", "closed"])


if __name__ == "__main__":
    unittest.main()
