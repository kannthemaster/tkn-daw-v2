"""Offline tests for the deterministic Thai command parser (no SoundCraft required)."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("jarvis", Path(__file__).with_name("jarvis.py"))
jarvis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jarvis)


class ParserTests(unittest.TestCase):
    def test_inspection(self):
        self.assertEqual(jarvis.parse_thai("ตรวจสอบเซสชัน")["method"], "session.inspect")

    def test_absolute_volume(self):
        payload = jarvis.parse_thai("ตั้งเสียง Kick ติดลบ 6 dB")
        self.assertEqual(payload["params"]["command"], "mix.volume")
        self.assertEqual(payload["params"]["params"], {"track": "Kick", "db": -6.0})

    def test_positive_volume(self):
        payload = jarvis.parse_thai("ตั้งเสียง Bass 2 dB")
        self.assertEqual(payload["params"]["params"]["db"], 2.0)

    def test_relative_volume_rejected(self):
        with self.assertRaises(ValueError):
            jarvis.parse_thai("ลดเสียง Kick 6 dB")

    def test_unsafe_or_unsupported_command_rejected(self):
        for phrase in ("ลบแทร็ก Kick", "export out.wav", "ตั้งเสียง Kick 100 dB"):
            with self.subTest(phrase=phrase), self.assertRaises(ValueError):
                jarvis.parse_thai(phrase)


if __name__ == "__main__":
    unittest.main()
