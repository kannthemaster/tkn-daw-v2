"""Windows-only V1 live demo acceptance; never attaches to a user's session."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time

import jarvis
import jarvis_v1 as v1

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soundcraft", type=Path, default=ROOT / "target/debug/soundcraft.exe")
    parser.add_argument("--output", type=Path, default=ROOT / "work/v1-smoke")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if platform.system() != "Windows" or not args.soundcraft.is_file():
        (output / "summary.json").write_text(json.dumps({"status": "BLOCKED", "reason": "Windows desktop executable required"}), encoding="utf-8")
        return 2
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
           "SOUNDCRAFT_CONFIG_DIR": tempfile.mkdtemp(prefix="demo-", dir=output)}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    process, checks, status = None, [], "FAIL"
    try:
        with (output / "desktop.stdout.log").open("w", encoding="utf-8") as stdout, \
                (output / "desktop.stderr.log").open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen([str(args.soundcraft.resolve()), "--demo", "--no-audio", "--control", "0"],
                cwd=ROOT, env=env, startupinfo=startup, stdout=stdout, stderr=stderr)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Desktop exited {process.returncode}")
                match = re.search(r"SOUNDCRAFT_CONTROL_PORT=(\d+)", (output / "desktop.stdout.log").read_text(encoding="utf-8", errors="replace"))
                if match:
                    port = int(match[1])
                    try:
                        initial = jarvis.request(port, {"method": "session.inspect", "params": {"detail": "full"}})["result"]
                        break
                    except (OSError, RuntimeError):
                        pass
                time.sleep(0.25)
            else:
                raise RuntimeError("Desktop endpoint not ready after 60 seconds")

            def inspect():
                return jarvis.request(port, {"method": "session.inspect", "params": {"detail": "full"}})["result"]

            def run(label, text, apply=True, expected=0):
                command = [sys.executable, str(ROOT / "tkn-jarvis/jarvis_v1.py"), text, "--port", str(port)]
                if apply:
                    command.append("--apply")
                result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, encoding="utf-8", timeout=30)
                (output / f"{label}.log").write_text(result.stdout + "\nSTDERR:\n" + result.stderr, encoding="utf-8")
                if result.returncode != expected:
                    raise RuntimeError(f"{label}: exit {result.returncode}, expected {expected}")
                checks.append(label)

            (output / "initial.json").write_text(json.dumps(initial, indent=2), encoding="utf-8")
            run("create", "สร้างแทร็ก stereo ชื่อ JARVIS Trial")
            run("preview", "เพิ่ม EQ แทร็ก JARVIS Trial ช่อง a", apply=False)
            if v1.slot_insert(v1.find_track(inspect(), "JARVIS Trial"), 0) is not None:
                raise RuntimeError("Preview inserted an effect")
            run("eq-insert", "เพิ่ม EQ แทร็ก JARVIS Trial ช่อง a")
            run("eq-gain", "ตั้ง EQ แทร็ก JARVIS Trial ช่อง a gain -3")
            run("compressor-insert", "เพิ่ม Compressor แทร็ก JARVIS Trial ช่อง b")
            run("compressor-threshold", "ตั้ง Compressor แทร็ก JARVIS Trial ช่อง b threshold -18")
            run("compressor-ratio", "ตั้ง Compressor แทร็ก JARVIS Trial ช่อง b ratio 6")
            modified = inspect()
            target = v1.find_track(modified, "JARVIS Trial")
            if v1.slot_insert(target, 0)["params"]["gain"] != -3 or v1.slot_insert(target, 1)["params"]["threshold"] != -18 or v1.slot_insert(target, 1)["params"]["ratio"] != 6:
                raise RuntimeError("Independent effect state assertions failed")
            run("occupied-slot-rejected", "เพิ่ม EQ แทร็ก JARVIS Trial ช่อง a", expected=1)
            run("wrong-plugin-rejected", "ตั้ง Compressor แทร็ก JARVIS Trial ช่อง a threshold -18", expected=1)
            if inspect()["tracks"] != modified["tracks"]:
                raise RuntimeError("Rejected commands changed tracks")
            run("rename", "เปลี่ยนชื่อแทร็ก JARVIS Trial เป็น JARVIS Voice")
            run("mute", "ปิดเสียงแทร็ก JARVIS Voice")
            if v1.find_track(inspect(), "JARVIS Voice")["mute"] is not True:
                raise RuntimeError("Mute did not apply")
            run("undo", "ย้อนกลับ")
            if v1.find_track(inspect(), "JARVIS Voice")["mute"] is not False:
                raise RuntimeError("Undo did not restore mute")
            run("redo", "ทำซ้ำ")
            if v1.find_track(inspect(), "JARVIS Voice")["mute"] is not True:
                raise RuntimeError("Redo did not restore mute")
            (output / "modified.json").write_text(json.dumps(inspect(), indent=2), encoding="utf-8")
            for index in range(8):
                run(f"restore-{index + 1}", "ย้อนกลับ")
            restored = inspect()
            (output / "restored.json").write_text(json.dumps(restored, indent=2), encoding="utf-8")
            if restored["tracks"] != initial["tracks"]:
                raise RuntimeError("Undo stack did not restore the initial demo tracks")
            status = "PASS"
            print("PASS: V1 built-in effects, track create/rename/mute, Undo/Redo and full demo track restoration")
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        checks.append({"error": str(error)})
        print(f"FAIL: {error}", file=sys.stderr)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        (output / "summary.json").write_text(json.dumps({"status": status, "checks": checks,
            "audio_playback_tested": False, "llm_connected": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
