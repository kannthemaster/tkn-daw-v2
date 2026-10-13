"""Real localhost TCP tests of JARVIS; the peer is a fixture, not SoundCraft."""
import contextlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("jarvis_transport", Path(__file__).with_name("jarvis.py"))
jarvis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jarvis)


@contextlib.contextmanager
def peer(reply):
    received, failures = [], []
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(3)
        def serve():
            try:
                with server.accept()[0] as connection:
                    connection.settimeout(3)
                    with connection.makefile("rb") as stream:
                        received.append(json.loads(stream.readline()))
                    connection.sendall(reply)
            except Exception as error:
                failures.append(error)
        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        try:
            yield server.getsockname()[1], received
        finally:
            worker.join(4)
            if worker.is_alive():
                raise AssertionError("fixture thread did not finish")
            if failures:
                raise failures[0]


class TransportTests(unittest.TestCase):
    def test_non_object_response_rejected(self):
        for response in (b'[]\n', b'null\n', b'42\n'):
            with self.subTest(response=response), peer(response) as (port, _):
                with self.assertRaisesRegex(RuntimeError, "object"):
                    jarvis.request(port, {"method": "session.inspect"})

    def test_non_boolean_success_rejected(self):
        for flag in ('"false"', '1', 'null'):
            with self.subTest(flag=flag), peer(('{"id":1,"ok":' + flag + '}\n').encode()) as (port, _):
                with self.assertRaisesRegex(RuntimeError, "success flag"):
                    jarvis.request(port, {"method": "session.inspect"})

    def test_boolean_response_id_rejected(self):
        with peer(b'{"id":true,"ok":true}\n') as (port, _):
            with self.assertRaisesRegex(RuntimeError, "response id"):
                jarvis.request(port, {"method": "session.inspect"})

    def test_malformed_response_cli_exits_cleanly(self):
        with peer(b'[]\n') as (port, _):
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("jarvis.py")),
                "ตรวจสอบเซสชัน", "--apply", "--port", str(port)], capture_output=True,
                encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("JARVIS error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_volume_verification_accepts_rust_float_precision(self):
        jarvis.verify_volume({"tracks": [{"name": "Kick", "volume_db": -6.099999904632568}]}, "Kick", -6.1)

    def test_volume_verification_rejects_boolean_value(self):
        with self.assertRaisesRegex(RuntimeError, "invalid fader"):
            jarvis.verify_volume({"tracks": [{"name": "Kick", "volume_db": False}]}, "Kick", 0)

    def test_post_inspection_mismatch_reports_failure(self):
        with patch.object(sys, "argv", ["jarvis.py", "ตั้งเสียง Kick ติดลบ 6 dB", "--apply"]), \
                patch.object(jarvis, "request", side_effect=[{"ok": True},
                    {"result": {"tracks": [{"name": "Kick", "volume_db": -3}]}}]), \
                patch("builtins.print") as output:
            self.assertEqual(jarvis.main(), 1)
            self.assertTrue(any("verification failed" in str(call) for call in output.call_args_list))

    def test_post_inspection_invalid_or_missing_track_reports_failure(self):
        for snapshot in (None, {}, {"tracks": []}, {"tracks": [None]},
                         {"tracks": [{"name": "Kick", "volume_db": "-6"}]},
                         {"tracks": [{"name": "Kick", "volume_db": float("nan")}]},
                         {"tracks": [{"name": "Kick", "volume_db": -6}] * 2}):
            with self.subTest(snapshot=snapshot), \
                    patch.object(sys, "argv", ["jarvis.py", "ตั้งเสียง Kick ติดลบ 6 dB", "--apply"]), \
                    patch.object(jarvis, "request", side_effect=[{"ok": True}, {"result": snapshot}]), \
                    patch("builtins.print"):
                self.assertEqual(jarvis.main(), 1)

    def test_utf8_request_and_reply(self):
        reply = {"id": 1, "ok": True, "result": {"name": "ทดสอบ"}}
        with peer((json.dumps(reply, ensure_ascii=False) + "\n").encode()) as (port, received):
            payload = jarvis.parse_thai("ตั้งเสียง กลอง ติดลบ 6 dB")
            self.assertEqual(jarvis.request(port, payload), reply)
        self.assertEqual(received, [{"id": 1, **payload}])

    def test_bad_id_rejected(self):
        with peer(b'{"id":2,"ok":true}\n') as (port, _):
            with self.assertRaisesRegex(RuntimeError, "response id"):
                jarvis.request(port, {"method": "session.inspect"})

    def test_server_error_rejected(self):
        with peer(b'{"id":1,"ok":false,"error":"missing track"}\n') as (port, _):
            with self.assertRaisesRegex(RuntimeError, "missing track"):
                jarvis.request(port, {"method": "session.inspect"})

    def test_incomplete_response_rejected(self):
        with peer(b'{"id":1,"ok":true}') as (port, _):
            with self.assertRaisesRegex(RuntimeError, "Incomplete"):
                jarvis.request(port, {"method": "session.inspect"})

    def test_malformed_json_rejected(self):
        with peer(b'not-json\n') as (port, _):
            with self.assertRaises(json.JSONDecodeError):
                jarvis.request(port, {"method": "session.inspect"})

    def test_only_first_json_line_consumed(self):
        with peer(b'{"id":1,"ok":true,"result":{}}\nignored\n') as (port, _):
            self.assertTrue(jarvis.request(port, {"method": "session.inspect"})["ok"])

    def test_dry_run_never_connects(self):
        with patch.object(sys, "argv", ["jarvis.py", "ตั้งเสียง Kick ติดลบ 6 dB"]), \
                patch.object(jarvis.socket, "create_connection") as connect, \
                patch("builtins.print"):
            self.assertEqual(jarvis.main(), 0)
            connect.assert_not_called()

    def test_apply_write_requests_post_inspection(self):
        with patch.object(sys, "argv", ["jarvis.py", "ตั้งเสียง Kick ติดลบ 6 dB", "--apply"]), \
                patch.object(jarvis, "request", return_value={"id": 1, "ok": True,
                    "result": {"tracks": [{"name": "Kick", "volume_db": -6.0}]}}) as request, \
                patch("builtins.print"):
            self.assertEqual(jarvis.main(), 0)
            self.assertEqual(request.call_count, 2)
            self.assertEqual(request.call_args.args[1]["method"], "session.inspect")

    def test_cli_port_validation(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("jarvis.py")),
                                 "ตรวจสอบเซสชัน", "--port", "0"], capture_output=True,
                                encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("port must be", result.stderr)


if __name__ == "__main__":
    unittest.main()
