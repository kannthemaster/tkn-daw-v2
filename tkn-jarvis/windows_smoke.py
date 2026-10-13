"""Step 3 smoke runner. Missing prerequisites are BLOCKED, never PASS.

Run on Windows: py -3 tkn-jarvis/windows_smoke.py --build
Exit codes: 0 all requested checks passed; 1 failure; 2 blocked prerequisite.
Only launches its own disposable demo; never connects to a user's running app.
"""
import argparse
import contextlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tkn-jarvis" / "jarvis.py"
spec = importlib.util.spec_from_file_location("jarvis_smoke", ADAPTER)
jarvis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jarvis)


def volumes(snapshot):
    return {track["name"]: track["volume_db"] for track in snapshot["tracks"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Build both Windows binaries with Cargo --locked")
    parser.add_argument("--soundcraft", type=Path, default=ROOT / "target/debug/soundcraft.exe")
    parser.add_argument("--cli", type=Path, default=ROOT / "target/debug/soundcraft-cli.exe")
    parser.add_argument("--output", type=Path, default=ROOT / "work/windows-smoke")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    checks = []
    def note(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})
        print(f"{status}: {name}: {detail}", flush=True)
    def run(name, command, expected=0, timeout=60):
        result = subprocess.run([str(item) for item in command], cwd=ROOT, env=env,
                                capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        (output / (name + ".log")).write_text(
            json.dumps([str(item) for item in command], ensure_ascii=False) + "\n" +
            result.stdout + "\nSTDERR:\n" + result.stderr, encoding="utf-8")
        if result.returncode != expected:
            raise RuntimeError(f"{name}: exit {result.returncode}, expected {expected}; see {name}.log")
        return result.stdout
    def inspect(port):
        return jarvis.request(port, {"method": "session.inspect", "params": {"detail": "summary"}})["result"]
    process = None
    try:
        note("host", "PASS" if platform.system() == "Windows" else "BLOCKED", platform.platform())
        run("python-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tkn-jarvis", "-p", "test_*.py", "-v"])
        note("python-tests", "PASS", "Parser and fixture TCP tests; fixture is not SoundCraft")
        cargo = shutil.which("cargo")
        rustc = shutil.which("rustc")
        if cargo and rustc:
            note("rust-toolchain", "PASS", run("rust-version", [rustc, "-Vv"]).strip())
            run("cargo-version", [cargo, "--version"])
            if args.build:
                run("windows-build", [cargo, "build", "--locked", "-p", "soundcraft-cli", "-p", "soundcraft"], timeout=1800)
                note("windows-build", "PASS", "Debug Windows desktop and CLI built from checked-out source")
            else:
                note("windows-build", "BLOCKED", "Not requested; rerun with --build to verify this source")
        else:
            note("rust-toolchain", "BLOCKED", "cargo/rustc not found in PATH")
            note("windows-build", "BLOCKED", "Rust toolchain missing; compilation not performed")
        if platform.system() != "Windows":
            note("live-soundcraft", "BLOCKED", "Windows execution required")
        elif not args.soundcraft.is_file() or not args.cli.is_file():
            note("live-soundcraft", "BLOCKED", f"Missing executable: {args.soundcraft} or {args.cli}")
        else:
            run("cli-version", [args.cli, "--version"])
            metadata = run("command-metadata", [args.cli, "describe", "mix.volume"])
            if "mix.volume" not in metadata or "db" not in metadata:
                raise RuntimeError("mix.volume metadata missing")
            baseline = json.loads(run("cli-demo-before", [args.cli, "run", "--demo", "--inspect"]))
            changed_text = run("cli-demo-after", [args.cli, "run", "--demo", "--cmd",
                'mix.volume={"track":"Kick","db":-6}', "--inspect"])
            # CLI prefixes each command result with '<command>: ', then emits inspection JSON.
            decoder = json.JSONDecoder()
            first_line, separator, remainder = changed_text.partition("\n")
            if not separator or not first_line.startswith("mix.volume: "):
                raise RuntimeError("Unexpected CLI command output; see cli-demo-after.log")
            json.loads(first_line.removeprefix("mix.volume: "))
            rest, objects = remainder.strip(), []
            while rest:
                value, end = decoder.raw_decode(rest)
                objects.append(value)
                rest = rest[end:].lstrip()
            changed = objects[-1]
            wanted = {**volumes(baseline), "Kick": -6.0}
            if volumes(changed) != wanted:
                raise RuntimeError("Headless command did not change only Kick to -6 dB")
            note("cli-demo", "PASS", "Metadata and before/after volume assertions")
            # Keep the isolated profile with evidence, including after an early desktop failure.
            with contextlib.nullcontext(tempfile.mkdtemp(prefix="soundcraft-demo-", dir=output)) as profile:
                env["SOUNDCRAFT_CONFIG_DIR"] = profile
                startup = subprocess.STARTUPINFO()
                startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup.wShowWindow = 0
                with (output / "desktop.stdout.log").open("w", encoding="utf-8") as stdout, \
                        (output / "desktop.stderr.log").open("w", encoding="utf-8") as stderr:
                    process = subprocess.Popen([str(args.soundcraft.resolve()), "--demo", "--no-audio", "--control", "0"],
                        cwd=ROOT, env=env, stdout=stdout, stderr=stderr, startupinfo=startup)
                    deadline, port = time.monotonic() + 60, None
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise RuntimeError(f"Desktop exited {process.returncode}; see desktop logs")
                        logs = "".join((output / name).read_text(encoding="utf-8", errors="replace")
                            for name in ("desktop.stdout.log", "desktop.stderr.log"))
                        match = re.search(r"SOUNDCRAFT_CONTROL_PORT=(\d+)", logs)
                        if match:
                            port = int(match.group(1))
                            try:
                                before = inspect(port)
                                break
                            except (OSError, RuntimeError):
                                pass
                        time.sleep(0.25)
                    else:
                        raise RuntimeError("Desktop control endpoint was not ready after 60 seconds")
                    (output / "live-before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
                    initial = volumes(before)
                    if "Kick" not in initial:
                        raise RuntimeError("Demo has no Kick track")
                    run("jarvis-inspect", [sys.executable, ADAPTER, "ตรวจสอบเซสชัน", "--apply", "--port", port])
                    run("jarvis-preview", [sys.executable, ADAPTER, "ตั้งเสียง Kick ติดลบ 6 dB", "--port", port])
                    if volumes(inspect(port)) != initial:
                        raise RuntimeError("Dry-run changed volume")
                    run("jarvis-apply", [sys.executable, ADAPTER, "ตั้งเสียง Kick ติดลบ 6 dB", "--apply", "--port", port])
                    after = inspect(port)
                    if not math.isclose(volumes(after)["Kick"], -6, abs_tol=1e-5) or volumes(after) != {**initial, "Kick": -6.0}:
                        raise RuntimeError("Live command did not change only Kick to -6 dB")
                    (output / "live-after.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
                    run("jarvis-relative-rejected", [sys.executable, ADAPTER, "ลดเสียง Kick 6 dB", "--apply", "--port", port], expected=1)
                    run("jarvis-missing-track", [sys.executable, ADAPTER, "ตั้งเสียง TKN_MISSING_TRACK ติดลบ 6 dB", "--apply", "--port", port], expected=1)
                    if volumes(inspect(port)) != volumes(after):
                        raise RuntimeError("Rejected commands changed volume")
                    remote = json.loads(run("cli-control-inspect", [args.cli, "app", "--port", port, "session.inspect"]))
                    # Remote CLI prints the result value, rather than the wire envelope.
                    if volumes(remote) != volumes(after):
                        raise RuntimeError("CLI control snapshot differs from JARVIS snapshot")
                    jarvis.request(port, {"method": "engine.execute", "params": {"command": "mix.volume", "params": {"track": "Kick", "db": initial["Kick"]}}})
                    if volumes(inspect(port)) != initial:
                        raise RuntimeError("Could not restore demo fader")
                    note("live-soundcraft", "PASS", "JARVIS inspect/preview/apply/error cases, CLI control, fader restoration; no audio")
                    process.terminate()
                    process.wait(timeout=10)
                    process = None
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as error:
        note("smoke", "FAIL", str(error))
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        report = {"platform": platform.platform(), "python": sys.version, "checks": checks,
                  "audio_playback_tested": False, "recording_tested": False}
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if any(c["status"] == "FAIL" for c in checks) else 2 if any(c["status"] == "BLOCKED" for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
