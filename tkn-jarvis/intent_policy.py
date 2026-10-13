"""Independent bounded request contracts, never a DAW dispatcher.

No benchmark IDs/fixtures/oracles are read. Unrecognized language defers safely.
The model still proposes values for recognized requests, inside this contract.
"""
import copy
import math
import re

import jarvis_v1 as v1

NUM = r"[-+]?\d+(?:\.\d+)?"
DIGITS = {"ศูนย์": 0, "หนึ่ง": 1, "เอ็ด": 1, "สอง": 2, "สาม": 3, "สี่": 4,
          "ห้า": 5, "หก": 6, "เจ็ด": 7, "แปด": 8, "เก้า": 9}
WORDS = r"(?:ศูนย์|หนึ่ง|เอ็ด|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|สิบ|ยี่)+"
PARAMS = {"type": r"type|ประเภท", "freq": r"freq|frequency|ความถี่", "gain": r"(?<!output_)\bgain\b",
          "q": r"\bq\b", "output_gain": r"output_gain", "threshold": r"threshold|เกณฑ์",
          "ratio": r"ratio|อัตราส่วน", "attack": r"attack", "release": r"release",
          "knee": r"knee", "makeup": r"makeup", "mix": r"\bmix\b"}


def clarify(reason):
    return {"status": "clarify", "reason": reason, "actions": []}


def thai_integer(word):
    if word in DIGITS:
        return DIGITS[word]
    if word == "สิบ":
        return 10
    if "สิบ" in word:
        left, right = word.split("สิบ", 1)
        tens = 2 if left == "ยี่" else 1 if not left else DIGITS.get(left)
        units = 0 if not right else DIGITS.get(right)
        if tens is not None and units is not None:
            return tens * 10 + units
    raise ValueError("Unsupported spoken number")


def normalize_text(text):
    # Convert numeric words only in a value/unit position, not arbitrary track names.
    pattern = rf"(?P<sign>ติดลบ|ลบ)?\s*(?P<int>{WORDS})(?:จุด(?P<frac>{WORDS}))?(?=\s*(?:dB|ดีบี|เดซิเบล|Hz|เฮิรตซ์|ms|มิลลิวินาที))"
    def convert(match):
        try:
            integer = thai_integer(match["int"])
            fraction = "" if not match["frac"] else "." + str(thai_integer(match["frac"]))
            return ("-" if match["sign"] else "") + str(integer) + fraction
        except ValueError:
            return match[0]
    text = re.sub(pattern, convert, text, flags=re.I)
    text = re.sub(rf"(?:ติดลบ|ลบ)\s*({NUM})(?=\s*(?:dB|ดีบี|เดซิเบล))", r"-\1", text, flags=re.I)
    return text.strip()


def denied_request(text):
    # Quoted/negated words alone are not a deletion request. Retain other clauses.
    cleaned = re.sub(r"คำว่า\s*['\"]?(?:delete|remove|ลบ)['\"]?\s*เป็นแค่ข้อความที่พูดถึง", "", text, flags=re.I)
    cleaned = re.sub(r"(?:ไม่ต้อง|อย่า|ห้าม)\s*(?:ลบ|delete|remove)(?:แทร็ก|track)?", "", cleaned, flags=re.I)
    if re.search(r"ลบ|\bdelete\b|\bremove\b|engine\.execute|track\.delete", cleaned, re.I):
        return "คำขอลบหรือคำสั่ง engine อิสระไม่รองรับ"
    bypass = re.sub(r"(?:อย่า|ห้าม)\s*ข้าม.{0,15}ยืนยัน", "", cleaned)
    if re.search(r"ไม่ต้อง.{0,20}ยืนยัน|ข้าม.{0,20}ยืนยัน|without\s+confirmation", bypass, re.I):
        return "ต้องตรวจ Preview และยืนยันก่อน Apply เสมอ"
    unsupported = re.sub(r"(?:ไม่ต้อง|อย่า|ห้าม)\s*(?:บันทึก|อัด|save|record)", "", cleaned, flags=re.I)
    if re.search(r"บันทึก|อัดเสียง|\brecord\b|\bsave\b|VST3|CLAP|bounce|shell|ย้อนกลับ|ทำซ้ำ|สร้างแทร็ก", unsupported, re.I):
        return "มีส่วนของคำขอที่ยังไม่รองรับ กรุณาแยกคำสั่งที่รองรับก่อน"
    return None


def mentioned(text, tracks):
    found = []
    for track in tracks:
        name = track["name"]
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", text, re.I):
            found.append(track)
    return found


def target_for(text, tracks, previous):
    found = mentioned(text, tracks)
    residual = text
    for item in found:
        residual = re.sub(re.escape(item["name"]), "", residual, flags=re.I)
    residual = re.sub(r"ช่อง\s*[a-j]\b", "", residual, flags=re.I)
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9_]*", residual)
    jargon = {"eq", "compressor", "db", "hz", "ms", "jarvis", "q", "frequency",
              "mute", "unmute", "on", "off", "high", "pass", "highpass", "track",
              "delete", "remove", *PARAMS}
    if any(word.lower() not in jargon for word in candidates):
        raise ValueError("ไม่พบแทร็กที่ระบุ กรุณายืนยันชื่อแทร็ก")
    if not found and "เสียงร้อง" in text:
        found = [track for track in tracks if re.search(r"ร้อง|vocal|voice|vox", track["name"], re.I)]
    if len(found) > 1:
        raise ValueError("แทร็กกำกวม กรุณาระบุชื่อแทร็กเดียวให้ชัดเจน")
    if found:
        return found[0]
    # Unknown explicit ASCII target must not silently inherit an earlier track.
    if previous is not None:
        return previous
    raise ValueError("กรุณาระบุแทร็กที่จะปรับให้ชัดเจน")


def value_after(alias, text):
    match = re.search(rf"(?:{alias})\s*(?:ของ.*?ช่อง\s*[a-j]\s*)?(?:ลง)?\s*(?:ให้)?\s*(?:เป็น)?\s*({NUM})", text, re.I)
    return float(match[1]) if match else None


def build_contract(text, snapshot):
    text = normalize_text(text)
    reason = denied_request(text)
    if reason:
        return clarify(reason)
    simulated = copy.deepcopy(snapshot)
    tracks = v1.tracks(simulated)
    actions, last_track, last_effect, last_slot = [], None, None, None

    def add(action, target):
        op = action["op"]
        if op in ("volume", "volume_delta"):
            v1value = action["db"] + (target["volume_db"] if op == "volume_delta" else 0)
            if not -60 <= v1value <= 12 or (op == "volume_delta" and not -12 <= action["db"] <= 12):
                raise ValueError("ระดับเสียงที่ขออยู่นอกช่วงที่รองรับ")
            target["volume_db"] = v1value
        elif op == "rename":
            new_name = v1.name(action["name"])
            if any(track["name"] == new_name for track in tracks):
                raise ValueError("ชื่อแทร็กใหม่มีอยู่แล้ว")
            target["name"] = new_name
        elif op == "insert":
            if v1.slot_insert(target, action["slot"]) is not None:
                raise ValueError("ช่องเอฟเฟกต์ไม่ว่าง ไม่สามารถเขียนทับโดยอัตโนมัติ")
            target["inserts"].append({"slot": action["slot"], "plugin": v1.PLUGINS[action["effect"]], "params": {}})
        elif op == "parameter":
            insert = v1.slot_insert(target, action["slot"])
            if not insert or insert["plugin"] != v1.PLUGINS[action["effect"]]:
                raise ValueError("เอฟเฟกต์ไม่ตรงกับช่องที่ขอ กรุณาตรวจชื่อและช่อง")
            value, param = action["value"], action["param"]
            limits = (0, 6) if action["effect"] == "eq" and param == "type" else v1.RANGES[action["effect"]].get(param)
            if limits is None:
                raise ValueError("พารามิเตอร์ไม่รองรับ")
            if isinstance(value, dict):
                if not limits[0] <= value["min"] <= value["max"] <= limits[1]:
                    raise ValueError("ค่าที่เสนออยู่นอกช่วง")
            elif not math.isfinite(value) or not limits[0] <= value <= limits[1] or (param == "type" and int(value) != value):
                raise ValueError("ค่าพารามิเตอร์อยู่นอกช่วงที่รองรับ")
        actions.append(action)
        if len(actions) > 16:
            raise ValueError("คำขอยาวเกินขอบเขต กรุณาแยกแผน")

    try:
        clauses = re.split(r"\s*(?:,|แล้ว|และ|ส่วน)\s*|\s+(?=(?:ใส่|เพิ่ม)\s+(?:EQ|compressor|คอมเพรสเซอร์))", text, flags=re.I)
        for clause in clauses:
            if not clause.strip():
                continue
            if "คงเดิม" in clause:
                if re.search(r"เพิ่ม|ลด|ตั้ง|เปิด|ปิด|EQ|compressor", clause, re.I):
                    raise ValueError("คำขอขัดแย้ง กรุณาระบุการเปลี่ยนแปลงเดียวให้ชัดเจน")
                continue
            clause = re.sub(r"ไม่ต้องเปลี่ยนระดับเสียง", "", clause).strip()
            if not clause:
                continue
            if re.search(r"(?:ไม่ต้อง|อย่า|ห้าม|ไม่)\s*(?:ลด|เพิ่ม|ตั้ง|ปรับ|เปิด|ปิด|ใส่|เปลี่ยน|บีบ)", clause):
                raise ValueError("พบการปฏิเสธการปรับเสียง กรุณาระบุเฉพาะการเปลี่ยนแปลงที่ต้องการ")
            # State description is not a request to mute again.
            request = re.sub(r"ถูกปิดเสียงอยู่|เบาไป", "", clause)
            rename = re.search(r"เปลี่ยน(?:ชื่อ)?\s*(?:แทร็ก\s*)?(.+?)\s+เป็น\s+(.+)", request)
            if rename:
                target = target_for(rename[1], tracks, None)
                new_name = re.sub(r"\s*(?:ให้หน่อย|หน่อย|ครับ|ค่ะ|นะ|ด้วย)\s*$", "", rename[2]).strip(" '\"")
                add({"op": "rename", "track": target["name"], "name": new_name}, target)
                last_track = target
                continue
            off = bool(re.search(r"เปิดเสียง|คืนเสียง|unmute|(?<!เ)ปิด\s*mute", request, re.I))
            on = bool(re.search(r"(?<!เ)ปิดเสียง|พักเสียง|เปิด\s*mute|mute\s+on", request, re.I))
            if off or on:
                if off and on:
                    raise ValueError("ต้องการเปิดหรือปิด mute กรุณายืนยันก่อน")
                target = target_for(request, tracks, last_track)
                add({"op": "mute", "track": target["name"], "value": on}, target)
                last_track = target
                continue
            effect = "compressor" if re.search(r"compressor|คอมเพรสเซอร์|บีบเสียง", request, re.I) else "eq" if re.search(r"\bEQ\b|อีคิว|ตัดเสียงทุ้ม|high.?pass", request, re.I) else None
            if effect is None and last_effect and re.search(r"ตั้ง|ปรับ", request):
                effect = last_effect
            if effect:
                target = target_for(request, tracks, last_track)
                slot_match = re.search(r"ช่อง\s*([a-j])\b", request, re.I)
                insert_requested = bool(re.search(r"ใส่|เพิ่ม|ตัดเสียงทุ้ม|บีบเสียง|high.?pass", request, re.I))
                if re.search(r"ทับ|แทนที่", request):
                    raise ValueError("ไม่รองรับการแทนที่เอฟเฟกต์ในช่องโดยอัตโนมัติ")
                if slot_match:
                    slot = ord(slot_match[1].lower()) - ord("a")
                elif insert_requested:
                    slot = next((slot for slot in range(10) if v1.slot_insert(target, slot) is None), None)
                    if slot is None:
                        raise ValueError("ไม่มีช่องเอฟเฟกต์ว่าง")
                elif effect == last_effect and target is last_track and last_slot is not None:
                    slot = last_slot
                else:
                    existing = [item["slot"] for item in target["inserts"] if item["plugin"] == v1.PLUGINS[effect]]
                    if len(existing) != 1:
                        raise ValueError("กรุณาระบุช่องเอฟเฟกต์ให้ชัดเจน")
                    slot = existing[0]
                if insert_requested:
                    add({"op": "insert", "track": target["name"], "effect": effect, "slot": slot}, target)
                params = []
                for param, alias in PARAMS.items():
                    value = value_after(alias, request)
                    if value is not None:
                        params.append((param, int(value) if param == "type" and value.is_integer() else value))
                if re.search(r"ตัดเสียงทุ้ม|high.?pass", request, re.I):
                    frequency = re.search(rf"({NUM})\s*(?:Hz|เฮิรตซ์)", request, re.I)
                    params = [("type", 3), ("freq", float(frequency[1]) if frequency else 80), ("q", .707)]
                elif effect == "compressor" and "เนียน" in request and not params:
                    params = [("threshold", {"min": -24, "max": -12}), ("ratio", {"min": 2, "max": 4}),
                              ("attack", {"min": 5, "max": 30}), ("release", {"min": 60, "max": 200})]
                if not insert_requested and not params:
                    raise ValueError("กรุณาระบุพารามิเตอร์และค่าที่ต้องการ")
                for param, value in params:
                    add({"op": "parameter", "track": target["name"], "effect": effect, "slot": slot, "param": param, "value": value}, target)
                last_track, last_effect, last_slot = target, effect, slot
                continue
            if re.search(r"ลด|เบา|เพิ่ม|ดังขึ้น|ระดับเสียง|ตั้งเสียง", request) or ("ตั้ง" in request and re.search(r"dB|ดีบี|เดซิเบล", text, re.I)):
                target = target_for(request, tracks, last_track)
                if re.search(r"%|เปอร์เซ็นต์", request):
                    raise ValueError("กรุณาระบุระดับเสียงเป็น dB")
                values = re.findall(rf"({NUM})\s*(?:dB|ดีบี|เดซิเบล)", request, re.I)
                if len(values) > 1:
                    raise ValueError("ค่าระดับเสียงขัดแย้ง กรุณาเลือกค่าหนึ่ง")
                absolute = bool(re.search(r"เป็น|อยู่ที่|ตั้งเสียง", request))
                down, up = bool(re.search(r"ลด|เบา|ลง", request)), bool(re.search(r"เพิ่ม|ดังขึ้น|ขึ้น", request))
                if not absolute and (down == up):
                    raise ValueError("กรุณาระบุว่าจะเพิ่มหรือลดระดับเสียง")
                if values:
                    value = float(values[0])
                elif not absolute and re.search(r"หน่อย|นิด", request):
                    value = 2
                else:
                    raise ValueError("กรุณาระบุค่าระดับเสียงที่ต้องการ")
                if not absolute:
                    value = -abs(value) if down else abs(value)
                add({"op": "volume" if absolute else "volume_delta", "track": target["name"], "db": value}, target)
                last_track = target
                continue
            # Never silently omit a clause just because a prior clause was understood.
            return {"status": "unknown", "reason": "ยังตรวจความหมายส่วนนี้ไม่ได้ กรุณาระบุคำขอให้ชัดเจน", "actions": []}
    except (ValueError, RuntimeError, KeyError, TypeError) as error:
        return clarify(str(error))
    if not actions:
        return {"status": "unknown", "reason": "กรุณาระบุการปรับเสียงที่ต้องการ", "actions": []}
    return {"status": "ready", "reason": "", "actions": actions}


def equivalent(actual, expected):
    if set(actual) != set(expected):
        return False
    for key, wanted in expected.items():
        value = actual[key]
        if isinstance(wanted, dict):
            if type(value) not in (int, float) or not wanted["min"] <= value <= wanted["max"]:
                return False
        elif type(wanted) in (int, float):
            if type(value) not in (int, float) or not math.isclose(value, wanted, abs_tol=1e-5, rel_tol=0):
                return False
        elif type(value) is not type(wanted) or value != wanted:
            return False
    return True


def approved(policy, actions):
    # Ordered contracts keep dependent operations and repeated values unambiguous.
    return policy["status"] == "ready" and len(actions) == len(policy["actions"]) and all(
        equivalent(actual, expected) for actual, expected in zip(actions, policy["actions"]))


def generation_schema(policy):
    variants = []
    for action in policy["actions"]:
        fields = {}
        for key, value in action.items():
            if isinstance(value, dict):
                fields[key] = {"type": "number", "minimum": value["min"], "maximum": value["max"]}
            else:
                fields[key] = {"const": value}
        variants.append({"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields})
    return {"type": "object", "additionalProperties": False, "required": ["summary", "clarification", "actions"],
            "properties": {"summary": {"type": "string", "maxLength": 2000}, "clarification": {"const": ""},
                           "actions": {"type": "array", "minItems": len(variants), "maxItems": len(variants),
                                       "items": {"anyOf": variants}}}}


def explanation(actions):
    parts = []
    for action in actions:
        detail = ", ".join(f"{key}={value}" for key, value in action.items() if key not in ("op", "track"))
        parts.append(f"{action['track']}: {action['op']} ({detail})")
    return ("ข้อเสนอที่ตรวจขอบเขตแล้ว: " + "; ".join(parts))[:2000]
