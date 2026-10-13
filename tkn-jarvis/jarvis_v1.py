"""V1 command foundation: deterministic Thai intents, preflight and verified state.

No LLM/voice provider is connected. Dry-run is offline; --apply explicitly writes.
Uses built-in SoundCraft effects, not third-party VST3/CLAP plugins.
"""
import argparse
import copy
import json
import math
import re
import sys

import jarvis

PLUGINS = {"eq": "eq_1band", "compressor": "compressor"}
RANGES = {
    "eq": {"freq": (20, 20000), "gain": (-24, 24), "q": (0.1, 10), "output_gain": (-24, 24)},
    "compressor": {"threshold": (-60, 0), "ratio": (1, 100), "attack": (0.01, 300),
                   "release": (5, 3000), "knee": (0, 24), "makeup": (0, 40), "mix": (0, 100)},
}


def name(value):
    value = value.strip()
    if not value or len(value) > 128 or any(ord(char) < 32 for char in value):
        raise ValueError("Track names must contain 1..128 characters without control characters")
    return value


def execute(command, params):
    return {"method": "engine.execute", "params": {"command": command, "params": params}}


def parse_instruction(text):
    text = text.strip()
    if text in ("ย้อนกลับ", "ทำซ้ำ"):
        return execute("edit.undo" if text == "ย้อนกลับ" else "edit.redo", {})
    match = re.fullmatch(r"สร้างแทร็ก\s+(mono|stereo)\s+ชื่อ\s+(.+)", text, re.I)
    if match:
        return execute("track.new", {"count": 1, "kind": "audio", "format": match[1].lower(), "name": name(match[2])})
    match = re.fullmatch(r"เปลี่ยนชื่อแทร็ก\s+(.+?)\s+เป็น\s+(.+)", text)
    if match:
        return execute("track.rename", {"track": name(match[1]), "name": name(match[2])})
    match = re.fullmatch(r"(ปิด|เปิด)เสียงแทร็ก\s+(.+)", text)
    if match:
        return execute("mix.mute", {"track": name(match[2]), "value": match[1] == "ปิด"})
    match = re.fullmatch(r"เพิ่ม\s+(EQ|Compressor)\s+แทร็ก\s+(.+?)\s+ช่อง\s+([a-j])", text, re.I)
    if match:
        return execute("mix.insert", {"track": name(match[2]), "slot": ord(match[3].lower()) - ord("a"),
                                      "plugin": PLUGINS[match[1].lower()]})
    match = re.fullmatch(r"ตั้ง\s+(EQ|Compressor)\s+แทร็ก\s+(.+?)\s+ช่อง\s+([a-j])\s+(\w+)\s+(-?\d+(?:\.\d+)?)", text, re.I)
    if match:
        effect, param, value = match[1].lower(), match[4].lower(), float(match[5])
        limits = RANGES[effect].get(param)
        if not limits or not math.isfinite(value) or not limits[0] <= value <= limits[1]:
            raise ValueError("Unsupported effect parameter or value outside its supported range")
        payload = execute("mix.insert_param", {"track": name(match[2]), "slot": ord(match[3].lower()) - ord("a"),
                                              "param": param, "value": value})
        # Local preflight requirement; removed before sending the wire request.
        payload["expected_plugin"] = PLUGINS[effect]
        return payload
    return jarvis.parse_thai(text)


def tracks(snapshot):
    items = snapshot.get("tracks") if isinstance(snapshot, dict) else None
    if not isinstance(items, list) or any(not isinstance(item, dict) or type(item.get("id")) is not int for item in items):
        raise RuntimeError("Invalid session track snapshot")
    if len({item["id"] for item in items}) != len(items):
        raise RuntimeError("Ambiguous track IDs in session snapshot")
    return items


def find_track(snapshot, reference):
    key = "id" if type(reference) is int else "name"
    matches = [item for item in tracks(snapshot) if item.get(key) == reference]
    if len(matches) != 1:
        raise RuntimeError("Track missing or ambiguous; no command sent")
    return matches[0]


def slot_insert(track, slot):
    inserts = track.get("inserts")
    if not isinstance(inserts, list) or any(not isinstance(item, dict) for item in inserts):
        raise RuntimeError("Invalid insert snapshot")
    matches = [item for item in inserts if item.get("slot") == slot]
    if len(matches) > 1:
        raise RuntimeError("Ambiguous insert slot")
    return matches[0] if matches else None


def prepare(payload, before):
    """Resolve track names to IDs and reject collisions before any write."""
    prepared = copy.deepcopy(payload)
    if prepared["method"] == "session.inspect":
        return prepared
    command, params = prepared["params"]["command"], prepared["params"]["params"]
    if command not in {"track.new", "track.rename", "mix.volume", "mix.mute", "mix.insert", "mix.insert_param", "edit.undo", "edit.redo"}:
        raise ValueError("Command is outside the V1 allowlist")
    if command in ("track.new", "track.rename"):
        if any(item.get("name") == params["name"] for item in tracks(before)):
            raise RuntimeError("Destination track name already exists; no command sent")
    if "track" in params:
        target = find_track(before, params["track"])
        params["track"] = target["id"]
        if command in ("mix.insert", "mix.insert_param"):
            insert = slot_insert(target, params["slot"])
            if command == "mix.insert" and insert is not None:
                raise RuntimeError("Insert slot is occupied; no command sent")
            if command == "mix.insert_param" and (insert is None or insert.get("plugin") != prepared.get("expected_plugin")):
                raise RuntimeError("Expected effect is not in this slot; no command sent")
    if command in ("edit.undo", "edit.redo") and not before.get("undo" if command == "edit.undo" else "redo"):
        raise RuntimeError("No history operation is available; no command sent")
    return prepared


def verify(prepared, before, after, response):
    command, params = prepared["params"]["command"], prepared["params"]["params"]
    if command == "track.new":
        created = find_track(after, params["name"])
        old_ids = {item["id"] for item in tracks(before)}
        if created["id"] in old_ids or len(tracks(after)) != len(old_ids) + 1 or created.get("kind") != "audio" or created.get("format", "").lower() != params["format"]:
            raise RuntimeError("New track verification failed")
        return
    if command in ("edit.undo", "edit.redo"):
        key = "undone" if command == "edit.undo" else "redone"
        result = response.get("result")
        tracks(after)
        if not isinstance(result, dict) or result.get(key) is not True:
            raise RuntimeError("History verification failed")
        return
    target = find_track(after, params["track"])
    if command == "track.rename":
        if target.get("name") != params["name"]:
            raise RuntimeError("Track rename verification failed")
    elif command == "mix.mute":
        if target.get("mute") is not params["value"]:
            raise RuntimeError("Mute verification failed")
    elif command == "mix.volume":
        jarvis.verify_volume(after, target["name"], params["db"])
    else:
        insert = slot_insert(target, params["slot"])
        expected = params.get("plugin", prepared.get("expected_plugin"))
        if not insert or insert.get("plugin") != expected:
            raise RuntimeError("Effect verification failed")
        if command == "mix.insert_param":
            values = insert.get("params")
            actual = values.get(params["param"]) if isinstance(values, dict) else None
            if type(actual) not in (int, float) or not math.isfinite(actual) or not math.isclose(actual, params["value"], rel_tol=1e-6, abs_tol=1e-4):
                raise RuntimeError("Effect parameter verification failed")


def apply(payload, port):
    inspect = {"method": "session.inspect", "params": {"detail": "full"}}
    if payload["method"] == "session.inspect":
        return {"inspection": jarvis.request(port, payload)["result"]}
    before = jarvis.request(port, inspect)["result"]
    prepared = prepare(payload, before)
    wire = {key: value for key, value in prepared.items() if key != "expected_plugin"}
    response = jarvis.request(port, wire)
    after = jarvis.request(port, inspect)["result"]
    verify(prepared, before, after, response)
    return {"verified": True, "request": wire, "response": response, "before": before, "after": after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instruction")
    parser.add_argument("--port", type=int, default=7801)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        payload = parse_instruction(args.instruction)
        print(json.dumps({"mode": "APPLY" if args.apply else "DRY_RUN", "intent": payload}, ensure_ascii=False, indent=2))
        if args.apply:
            print(json.dumps(apply(payload, args.port), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        print(f"JARVIS V1 error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
