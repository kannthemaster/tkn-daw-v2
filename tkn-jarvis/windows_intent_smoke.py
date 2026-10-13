"""Owned Windows demo: real local AI proposal, cancelled/confirmed CLI, restoration."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

import intent_engine as ai
import jarvis
import jarvis_v1 as v1

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gemma3:4b")
    args = parser.parse_args()
    output = ROOT / "work/intent-smoke"
    output.mkdir(parents=True, exist_ok=True)
    executable = ROOT / "target/debug/soundcraft.exe"
    if sys.platform != "win32" or not executable.is_file():
        print("BLOCKED: native Windows executable required")
        return 2
    # Long model inference can trigger autosave with generated WAVs. Keep profiles
    # outside the repo so asset attribution checks don't scan test-only audio.
    profiles = ROOT.parent / "intent-smoke-profiles"
    profiles.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
           "SOUNDCRAFT_CONFIG_DIR": tempfile.mkdtemp(prefix="demo-", dir=profiles)}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    process, checks, status = None, [], "FAIL"
    try:
        with (output / "desktop.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen([str(executable), "--demo", "--no-audio", "--control", "0"],
                                       cwd=ROOT, env=env, startupinfo=startup, stdout=log, stderr=log)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Desktop exited during startup")
                match = re.search(r"SOUNDCRAFT_CONTROL_PORT=(\d+)", (output / "desktop.log").read_text(encoding="utf-8", errors="replace"))
                if match:
                    port = int(match[1])
                    try:
                        initial = jarvis.request(port, ai.INSPECT)["result"]
                        break
                    except (RuntimeError, OSError):
                        pass
                time.sleep(.25)
            else:
                raise RuntimeError("Desktop endpoint timeout")
            v1.apply(v1.parse_instruction("สร้างแทร็ก stereo ชื่อ เสียงร้อง"), port)
            before = jarvis.request(port, ai.INSPECT)["result"]
            # Real installed Ollama model, no synthetic provider response.
            original_api = ai.local_api
            def audited_api(path, *api_args, **api_kwargs):
                response = original_api(path, *api_args, **api_kwargs)
                if path == "chat":
                    (output / "model-response.json").write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
                return response
            ai.local_api = audited_api
            try:
                proposal = ai.propose("จาร์วิส ลดเสียงร้องลงหน่อย ใส่ EQ ตัดเสียงทุ้ม แล้วบีบเสียงให้เนียนขึ้น", before, args.model)
            finally:
                ai.local_api = original_api
            (output / "intent.json").write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
            artifact = ai.preview(proposal, before, port)
            plan = output / "preview.json"
            plan.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
            commands = artifact["commands"]
            if not any(cmd["params"]["command"] == "mix.volume" for cmd in commands):
                raise RuntimeError("Model omitted requested fader operation")
            effect_params = [cmd["params"]["params"] for cmd in commands if cmd["params"]["command"] == "mix.insert_param"]
            if not any(p.get("param") == "type" and p.get("value") == 3 for p in effect_params):
                raise RuntimeError("Model did not propose an actual high-pass filter")
            if not any(cmd["params"]["params"].get("plugin") == "compressor" for cmd in commands):
                raise RuntimeError("Model omitted compressor")
            checks.append("real-local-model-composite-intent")
            def run(label, answer, expected):
                result = subprocess.run([sys.executable, str(ROOT / "tkn-jarvis/intent_engine.py"), "apply", str(plan)],
                                        cwd=ROOT, env=env, input=answer + "\n", capture_output=True,
                                        encoding="utf-8", timeout=60)
                (output / f"{label}.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
                if result.returncode != expected:
                    raise RuntimeError(f"{label} exit {result.returncode}, expected {expected}")
            run("cancelled", "no", 1)
            if ai.state(jarvis.request(port, ai.INSPECT)["result"]) != ai.state(before):
                raise RuntimeError("Cancelled preview changed session")
            checks.append("cancelled-cli-no-mutation")
            run("confirmed", artifact["confirmation"], 0)
            after = jarvis.request(port, ai.INSPECT)["result"]
            (output / "after.json").write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")
            checks.append("confirmed-cli-apply-verify")
            for _ in range(len(commands) + 1):
                v1.apply(v1.parse_instruction("ย้อนกลับ"), port)
            restored = jarvis.request(port, ai.INSPECT)["result"]
            if restored["tracks"] != initial["tracks"]:
                raise RuntimeError("Demo tracks not restored")
            checks.append("full-demo-track-restoration")
            status = "PASS"
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
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
        summary = {"status": status, "checks": checks, "model": args.model,
                   "audio_tested": False, "cloud_used": False,
                   "confirmation": "automated acceptance only, owned disposable demo"}
        (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
