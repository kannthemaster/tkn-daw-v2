"""Text UI controller boundaries; no live DAW or model writes."""
import copy
import unittest
from unittest.mock import patch

import text_chat as chat
from test_intent_engine import intent
from test_jarvis_v1 import snapshot


class ChatTests(unittest.TestCase):
    def make_preview(self, session):
        with patch.object(chat.ai.jarvis, "request", return_value={"result": snapshot()}) as request, \
                patch.object(chat.ai, "propose", return_value=intent()):
            plan = session.preview("ลด Voice ลง 2 dB")
            request.assert_called_once_with(7801, chat.ai.INSPECT)
            return plan

    def test_preview_only_inspects_and_shows_resolved_fader(self):
        session = chat.ChatSession()
        with patch.object(chat.ai, "apply_preview") as apply:
            plan = self.make_preview(session)
            self.assertIn("-5", chat.review_text(plan))
            apply.assert_not_called()

    def test_cancel_sends_no_requests(self):
        session = chat.ChatSession()
        self.make_preview(session)
        with patch.object(chat.ai.jarvis, "request") as request:
            session.cancel()
            with self.assertRaises(ValueError):
                session.apply("ลด Voice ลง 2 dB", "yes")
            request.assert_not_called()

    def test_apply_requires_matching_confirmation_before_requests(self):
        session = chat.ChatSession()
        self.make_preview(session)
        with patch.object(chat.ai.jarvis, "request") as request:
            with self.assertRaisesRegex(ValueError, "confirmation"):
                session.apply("ลด Voice ลง 2 dB", "yes")
            request.assert_not_called()
        self.assertIsNone(session.pending)

    def test_changed_text_invalidates_preview_before_apply(self):
        session = chat.ChatSession()
        plan = self.make_preview(session)
        with patch.object(chat.ai, "apply_preview") as apply:
            with self.assertRaises(ValueError):
                session.apply("เพิ่ม Voice ลง 2 dB", plan["confirmation"])
            apply.assert_not_called()

    def test_confirmed_apply_delegates_verify_and_consumes_plan(self):
        session = chat.ChatSession()
        plan = self.make_preview(session)
        result = {"verified": True, "steps": [{"verified": True}]}
        with patch.object(chat.ai, "apply_preview", return_value=result) as apply:
            self.assertEqual(session.apply("ลด Voice ลง 2 dB", plan["confirmation"]), result)
            apply.assert_called_once_with(plan, plan["confirmation"], request=chat.ai.jarvis.request)
            with self.assertRaises(ValueError):
                session.apply("ลด Voice ลง 2 dB", plan["confirmation"])

    def test_stale_plan_rejected_by_existing_engine_before_write(self):
        session = chat.ChatSession()
        plan = self.make_preview(session)
        changed = copy.deepcopy(snapshot())
        changed["tracks"][0]["volume_db"] = -9
        with patch.object(chat.ai.jarvis, "request", return_value={"result": changed}) as request:
            with self.assertRaisesRegex(RuntimeError, "Session changed"):
                session.apply("ลด Voice ลง 2 dB", plan["confirmation"])
            request.assert_called_once_with(7801, chat.ai.INSPECT)

    def test_failed_new_preview_removes_old_plan(self):
        session = chat.ChatSession()
        self.make_preview(session)
        with patch.object(chat.ai.jarvis, "request", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                session.preview("ใหม่")
        self.assertIsNone(session.pending)

    def test_clarification_never_creates_apply_plan(self):
        session = chat.ChatSession()
        self.make_preview(session)
        with patch.object(chat.ai.jarvis, "request", return_value={"result": snapshot()}), \
                patch.object(chat.ai, "propose", return_value={"summary": "", "clarification": "แทร็กไหน?", "actions": []}):
            self.assertEqual(session.preview("กำกวม"), {"clarification": "แทร็กไหน?"})
        self.assertIsNone(session.pending)

    def test_returned_artifact_cannot_mutate_pending_plan(self):
        session = chat.ChatSession()
        plan = self.make_preview(session)
        plan["commands"].clear()
        self.assertEqual(len(session.pending["commands"]), 1)


if __name__ == "__main__":
    unittest.main()
