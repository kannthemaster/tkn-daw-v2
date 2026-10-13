#!/usr/bin/env python3
"""TKN JARVIS V0: cautious Thai-language controller for SoundCraft.

Standard library only. Dry-run by default; --apply is required to change a live session.
This is a deterministic command prototype, NOT an LLM or speech recognizer.
"""
import argparse
import json
import re
import socket
import sys


def parse_thai(text: str) -> dict:
    text = text.strip()
    if text in ("ตรวจสอบเซสชัน", "ดูเซสชัน", "สถานะเซสชัน"):
        return {"method": "session.inspect", "params": {"detail": "summary"}}
    match = re.fullmatch(
        r"(?:ลด|เพิ่ม)เสียง(?:แทร็ก)?\s+(.+?)\s+(\d+(?:\.\d+)?)\s*(?:db|เดซิเบล)",
        text, flags=re.IGNORECASE,
    )
    if match:
        direction = -1 if text.startswith("ลด") else 1
        db = direction * float(match.group(2))
        if not 0 < abs(db) <= 24:
            raise ValueError("Only relative changes from 0 to 24 dB are supported")
        # A relative change needs the current value first. Never pretend an
        # absolute mix.volume setter implements a relative delta.
        raise ValueError("Relative fader changes require an inspect-and-calculate step; not yet implemented")
    match = re.fullmatch(
        r"ตั้งเสียง(?:แทร็ก)?\s+(.+?)\s+(ติดลบ\s*)?(\d+(?:\.\d+)?)\s*(?:db|เดซิเบล)",
        text, flags=re.IGNORECASE,
    )
    if match:
        track = match.group(1).strip()
        if not track or len(track) > 128:
            raise ValueError("Invalid track name")
        db = float(match.group(3)) * (-1 if match.group(2) else 1)
        if not -60 <= db <= 12:
            raise ValueError("Volume must be between -60 and +12 dB")
        return {"method": "engine.execute", "params": {
            "command": "mix.volume", "params": {"track": track, "db": db}
        }}
    raise ValueError("Unsupported command. Try: ตรวจสอบเซสชัน / ตั้งเสียง Kick ติดลบ 6 dB")


def request(port: int, payload: dict, timeout: float = 5.0) -> dict:
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as conn:
        conn.settimeout(timeout)
        conn.sendall((json.dumps({"id": 1, **payload}, ensure_ascii=False) + "\n").encode("utf-8"))
        data = bytearray()
        while len(data) < 2_000_000:
            chunk = conn.recv(8192)
            if not chunk:
                break
            data.extend(chunk)
            if b"\n" in data:
                break
        if b"\n" not in data:
            raise RuntimeError("Incomplete response from SoundCraft")
        result = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
        if result.get("id") != 1:
            raise RuntimeError("Unexpected response id")
        if not result.get("ok", False):
            raise RuntimeError(str(result.get("error", "SoundCraft command failed")))
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="TKN JARVIS SoundCraft controller")
    parser.add_argument("instruction", help="Thai-language command (quote if it contains spaces)")
    parser.add_argument("--port", type=int, default=7801, help="SoundCraft local control port")
    parser.add_argument("--apply", action="store_true", help="Actually send command to SoundCraft")
    args = parser.parse_args()
    if not (1 <= args.port <= 65535):
        parser.error("port must be between 1 and 65535")
    try:
        payload = parse_thai(args.instruction)
        print(json.dumps({"mode": "APPLY" if args.apply else "DRY_RUN", **payload},
                         ensure_ascii=False, indent=2))
        if args.apply:
            response = request(args.port, payload)
            print(json.dumps(response, ensure_ascii=False, indent=2))
            if payload["method"] == "engine.execute":
                verified = request(args.port, {"method": "session.inspect",
                                               "params": {"detail": "summary"}})
                print(json.dumps({"post_command_inspection": verified.get("result")},
                                 ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"JARVIS error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
