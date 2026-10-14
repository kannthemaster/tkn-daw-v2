"""Acceptance-only pause after the first real confirmed write.

Use only an owned disposable no-audio demo. Normal bridge parsing, local model,
confirmation, session checks and per-step Verify remain unchanged. This fixture
does not create a plan or authorize a write. It requires an explicit marker path
and is never selected by the application by default.
"""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import jarvis_bridge as bridge

original = bridge.ai.jarvis.request
paused = False


def delayed(port, payload):
    global paused
    response = original(port, payload)
    if payload.get("method") == "engine.execute" and not paused:
        paused = True
        Path(os.environ["TKN_TEST_WRITE_MARKER"]).write_text(
            json.dumps({"request": payload, "response": response}, ensure_ascii=False), encoding="utf-8")
        time.sleep(12)
    return response


if __name__ == "__main__":
    bridge.ai.jarvis.request = delayed
    bridge.main()
