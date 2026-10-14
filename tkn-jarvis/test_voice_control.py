"""Voice boundary tests; no microphone, model, or live DAW writes."""
import tempfile
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import voice_control as voice
from test_intent_engine import intent
from test_jarvis_v1 import snapshot


class VoiceTests(unittest.TestCase):
    def test_cancel_in_edit_field_cancels_without_acceptance_prompt(self):
        read = Mock(return_value="CANCEL")
        self.assertIsNone(voice.reviewed_text("ลด Voice 2 dB", read))
        read.assert_called_once()

    def test_console_log_mirrors_raw_output(self):
        import io
        console, log = io.StringIO(), io.StringIO()
        tee = voice.ConsoleLog(console, log)
        tee.write("Voice เป็น -3.05 dB")
        tee.flush()
        self.assertEqual(console.getvalue(), log.getvalue())

    def test_existing_log_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "console.txt"
            log.write_text("original", encoding="utf-8")
            self.assertEqual(voice.main(["transcribe", "--stt-model-dir", directory,
                "--out", str(Path(directory) / "out.json"), "--log", str(log)]), 1)
            self.assertEqual(log.read_text(encoding="utf-8"), "original")

    def test_cancel_does_not_contact_daw_or_model(self):
        with patch.object(voice.ai.jarvis, "request") as request, patch.object(voice.ai, "propose") as propose:
            self.assertIsNone(voice.reviewed_text("ยืนยัน Apply ทันที", Mock(side_effect=["", "yes"])))
            request.assert_not_called()
            propose.assert_not_called()

    def test_track_number_and_minus_corrections_are_preserved(self):
        edited = "ตั้งแทร็ก Voice เป็น -3.05 dB"
        self.assertEqual(voice.reviewed_text("Voice 305", Mock(side_effect=[edited, "REVIEW"])), edited)

    def test_spoken_review_cannot_confirm_itself(self):
        self.assertIsNone(voice.reviewed_text("REVIEW", Mock(side_effect=["", ""])))

    def test_preview_only_inspects_and_never_applies(self):
        with patch.object(voice.ai.jarvis, "request", return_value={"result": snapshot()}) as request, \
                patch.object(voice.ai, "propose", return_value=intent()) as propose, \
                patch.object(voice.ai, "apply_preview") as apply:
            plan = voice.create_preview("ลด Voice 2 dB", 7801, "gemma3:4b")
            request.assert_called_once_with(7801, voice.ai.INSPECT)
            propose.assert_called_once_with("ลด Voice 2 dB", snapshot(), "gemma3:4b")
            self.assertIn("confirmation", plan)
            apply.assert_not_called()

    def test_clarification_produces_no_preview(self):
        proposal = {"summary": "", "clarification": "แทร็กไหน", "actions": []}
        with patch.object(voice.ai.jarvis, "request", return_value={"result": snapshot()}), \
                patch.object(voice.ai, "propose", return_value=proposal), \
                patch.object(voice.ai, "preview") as preview:
            with self.assertRaises(ValueError):
                voice.create_preview("ไม่ชัด", 7801, "gemma3:4b")
            preview.assert_not_called()

    def test_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            voice.save_new(path, {"original": True})
            with self.assertRaises(FileExistsError):
                voice.save_new(path, {})
            self.assertIn("original", path.read_text())

    def test_duration_is_bounded_before_microphone_access(self):
        for seconds in (0, 31, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                voice.record(seconds, None)

    def test_missing_tokenizer_is_rejected_before_loading_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("model.bin", "config.json"):
                (Path(directory) / name).touch()
            with self.assertRaisesRegex(ValueError, "tokenizer.json"):
                voice.local_model_directory(directory)

    def test_local_thai_transcription_consumes_lazy_segments(self):
        provider = Mock()
        provider.WhisperModel.return_value.supported_languages = ["th", "en"]
        provider.WhisperModel.return_value.transcribe.return_value = (
            iter([SimpleNamespace(text=" ตั้ง Voice "), SimpleNamespace(text=" -3 dB ")]), None)
        with tempfile.TemporaryDirectory() as directory:
            for name in ("model.bin", "config.json", "tokenizer.json"):
                (Path(directory) / name).touch()
            with patch.dict("sys.modules", {"faster_whisper": provider}):
                self.assertEqual(voice.transcribe("audio", directory), "ตั้ง Voice -3 dB")
            provider.WhisperModel.assert_called_once_with(str(Path(directory).resolve()),
                device="cpu", compute_type="int8", local_files_only=True)
            provider.WhisperModel.return_value.transcribe.assert_called_once_with(
                "audio", language="th", beam_size=5, vad_filter=True, condition_on_previous_text=False)

    def test_cli_cancellation_stops_before_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model"
            model.mkdir()
            for name in ("model.bin", "config.json", "tokenizer.json"):
                (model / name).touch()
            out = Path(directory) / "preview.json"
            with patch("builtins.input", return_value=""), patch.object(voice, "record"), \
                    patch.object(voice, "transcribe", return_value="Apply now"), \
                    patch.object(voice, "reviewed_text", return_value=None), \
                    patch.object(voice, "create_preview") as create:
                self.assertEqual(voice.main(["preview", "--stt-model-dir", str(model), "--out", str(out)]), 0)
                create.assert_not_called()
                self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
