"""Versioned stdin/stdout JSONL sidecar; no network listener, UI, or audio input."""
import argparse
import json
import secrets
import sys

import intent_engine as ai

VERSION = 1
MAX_REQUEST = 32768


class Bridge:
    def __init__(self, port, model="gemma3:4b", request=None, propose=None):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Invalid owned control port")
        self.port, self.model = port, model
        self.request = request or ai.jarvis.request
        self.propose = propose or ai.propose
        self.pending = None
        self.closed = False
        self.write_attempted = False

    def dispatch(self, port, payload):
        if port != self.port:
            raise ValueError("Foreign control endpoint rejected")
        if payload.get("method") == "engine.execute":
            self.write_attempted = True
        return self.request(port, payload)

    def handle(self, msg):
        raw_id = msg.get("id") if type(msg) is dict else None
        correlation = raw_id if type(raw_id) is int and 1 <= raw_id <= 2147483647 else None
        self.write_attempted = False
        try:
            if self.closed:
                raise ValueError("Bridge is closed")
            if type(msg) is not dict or type(msg.get("version")) is not int or msg["version"] != VERSION:
                raise ValueError("Unsupported protocol version")
            if correlation is None:
                raise ValueError("Invalid correlation ID")
            method = msg.get("method")
            extras = {"status": set(), "shutdown": set(), "cancel": {"context"},
                      "preview": {"context", "instruction"},
                      "apply": {"context", "instruction", "preview_id", "confirmation", "confirmed"}}
            if type(method) is not str or method not in extras or set(msg) != {"version", "id", "method"} | extras[method]:
                raise ValueError("Unknown method or request fields")
            if "context" in msg and (type(msg["context"]) is not str or not 1 <= len(msg["context"]) <= 128):
                raise ValueError("Invalid session/input context")
            if method == "status":
                result = {"state": "preview" if self.pending else "idle"}
            elif method in ("cancel", "shutdown"):
                self.pending = None
                self.closed = method == "shutdown"
                result = {"state": "closed" if self.closed else "idle", "cancelled": True}
            elif method == "preview":
                self.pending = None
                text = msg["instruction"]
                if type(text) is not str or not text.strip() or len(text) > 4000:
                    raise ValueError("Instruction must contain 1..4000 characters")
                before = self.dispatch(self.port, ai.INSPECT)["result"]
                intent = self.propose(text, before, self.model)
                if intent["clarification"].strip():
                    result = {"state": "clarification", "message": intent["clarification"]}
                else:
                    plan = ai.preview(intent, before, self.port)
                    preview_id = secrets.token_hex(16)
                    self.pending = {"id": preview_id, "context": msg["context"], "text": text, "plan": plan}
                    changes = []
                    for action, command in zip(plan["intent"]["actions"], plan["commands"]):
                        change = dict(action)
                        change["track_id"] = command["params"]["params"]["track"]
                        if action["op"] == "volume_delta":
                            change["absolute_fader_db"] = command["params"]["params"]["db"]
                        changes.append(change)
                    result = {"state": "preview", "preview_id": preview_id,
                              "confirmation": plan["confirmation"], "changes": changes,
                              "commands": [{key: value for key, value in command.items() if key != "expected_plugin"}
                                           for command in plan["commands"]],
                              "summary": plan["intent"]["summary"]}
            else:
                pending, self.pending = self.pending, None
                if not pending or msg["context"] != pending["context"] or msg["instruction"] != pending["text"]:
                    raise ValueError("Preview expired: session or instruction changed")
                if msg["preview_id"] != pending["id"] or msg["confirmed"] is not True:
                    raise ValueError("Explicit confirmation of displayed Preview required")
                applied = ai.apply_preview(pending["plan"], msg["confirmation"], request=self.dispatch)
                result = {"state": "verified", "verified": applied["verified"], "steps": applied["steps"]}
            return {"version": VERSION, "id": correlation, "ok": True, "result": result}
        except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
            self.pending = None
            return {"version": VERSION, "id": correlation, "ok": False,
                    "error": {"message": str(error)[:3000], "may_have_written": self.write_attempted,
                              "new_preview_required": True}}


def serve(bridge, source, sink):
    def emit(reply):
        sink.write(json.dumps(reply, ensure_ascii=False, allow_nan=False) + "\n")
        sink.flush()
    emit({"version": VERSION, "id": None, "ok": True, "result": {"state": "ready"}})
    while not bridge.closed:
        line = source.readline(MAX_REQUEST + 1)
        if not line:
            bridge.pending = None
            break
        try:
            if len(line) > MAX_REQUEST or not line.endswith(b"\n"):
                raise ValueError("Oversized or incomplete request; stream closed")
            reply = bridge.handle(ai.decode(line.decode("utf-8")))
        except (UnicodeError, ValueError) as error:
            bridge.pending = None
            reply = {"version": VERSION, "id": None, "ok": False,
                     "error": {"message": str(error)[:3000], "may_have_written": False,
                               "new_preview_required": True}}
        emit(reply)
        if len(line) > MAX_REQUEST or not line.endswith(b"\n"):
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--model", default="gemma3:4b")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    serve(Bridge(args.port, args.model), sys.stdin.buffer, sys.stdout)


if __name__ == "__main__":
    main()
