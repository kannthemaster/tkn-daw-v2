"""Audit the unchanged Text Chat UI against an explicitly owned disposable demo.

The runtime directory must contain the manifest created for Step 7.1. This is
an acceptance wrapper, not the production launcher. No automatic confirmation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import threading
import tkinter as tk

import intent_engine as ai
import jarvis_v1 as v1
import text_chat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.runtime / "active-demo.json").read_text(encoding="utf-8-sig"))
    demo = Path(manifest["demo"])
    match = re.search(r"SOUNDCRAFT_CONTROL_PORT=(\d+)", (demo / "stdout.log").read_text())
    if not match or demo.parent.resolve() != args.runtime.resolve():
        raise ValueError("Owned Step 7.1 demo manifest/endpoint required")
    port = int(match[1])
    lock = threading.Lock()
    def save(name, data):
        with (args.output / name).open("x", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    def event(kind, **data):
        with lock, (args.output / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps({"event": kind, **data}, ensure_ascii=False) + "\n")
    original_request, original_api = ai.jarvis.request, ai.local_api
    def audited_request(call_port, payload, *a, **kw):
        if call_port != port:
            raise ValueError("Acceptance cannot contact another DAW endpoint")
        try:
            response = original_request(call_port, payload, *a, **kw)
            event("daw", request=payload, response=response)
            return response
        except Exception as error:
            event("daw_error", request=payload, error=str(error))
            raise
    def audited_api(path, *a, **kw):
        result = original_api(path, *a, **kw)
        event("ollama", path=path, response=result)
        return result
    ai.jarvis.request, ai.local_api = audited_request, audited_api
    initial = audited_request(port, ai.INSPECT)["result"]
    if initial["name"] != "Midnight Groove" or initial.get("path") is not None:
        raise ValueError("Expected disposable built-in demo, not a user project")
    save("initial.json", initial)
    save("provenance.json", {"manifest": manifest, "port": port,
        "soundcraft_sha256": hashlib.sha256(Path(manifest["executable"]).read_bytes()).hexdigest(),
        "native_release": "upstream v0.6.1; production source matches integration checkout",
        "model": "gemma3:4b", "audio_disabled": True, "ui_source": "text_chat.py unchanged"})
    v1.apply(v1.parse_instruction("สร้างแทร็ก stereo ชื่อ Voice"), port)
    save("fixture.json", audited_request(port, ai.INSPECT)["result"])

    class AuditedSession(text_chat.ChatSession):
        phase = "ui"
        def preview(self, text):
            self.phase = "preview"
            before = audited_request(port, ai.INSPECT)["result"]
            try:
                result = super().preview(text)
                after = audited_request(port, ai.INSPECT)["result"]
                event("preview", instruction=text, result=result,
                      session_unchanged=ai.state(before) == ai.state(after))
                return result
            except Exception as error:
                event("preview_error", instruction=text, error=str(error))
                raise
            finally:
                self.phase = "ui"
        def cancel(self):
            event("cancel", phase=self.phase, had_pending=self.pending is not None)
            return super().cancel()
        def apply(self, text, confirmation):
            self.phase = "apply"
            event("apply_confirmed", instruction=text, plan=self.pending)
            try:
                result = super().apply(text, confirmation)
                event("apply_result", instruction=text, result=result)
                return result
            except Exception as error:
                event("apply_error", instruction=text, error=str(error))
                raise
            finally:
                self.phase = "ui"

    root = tk.Tk()
    text_chat.TextChat(root, AuditedSession(port))
    try:
        root.mainloop()
    finally:
        event("restoration_start")
        for _ in range(80):
            current = audited_request(port, ai.INSPECT)["result"]
            if current["tracks"] == initial["tracks"]:
                save("restored.json", current)
                event("restoration", tracks_match_initial=True,
                      note="Undo history/redo metadata may differ; session tracks restored")
                break
            response = audited_request(port, {"method": "engine.execute",
                "params": {"command": "edit.undo", "params": {}}})
            if response.get("result", {}).get("undone") is not True:
                event("restoration", tracks_match_initial=False, error="Undo exhausted")
                break
        else:
            event("restoration", tracks_match_initial=False, error="Undo limit")
        ai.jarvis.request, ai.local_api = original_request, original_api


if __name__ == "__main__":
    main()
