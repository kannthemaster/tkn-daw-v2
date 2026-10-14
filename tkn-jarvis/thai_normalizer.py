"""Bounded Thai lexical conversion only; no target guessing or DAW dispatch."""
import re

DIGITS = {"ศูนย์": 0, "หนึ่ง": 1, "เอ็ด": 1, "สอง": 2, "สาม": 3,
          "สี่": 4, "ห้า": 5, "หก": 6, "เจ็ด": 7, "แปด": 8, "เก้า": 9}
TOKEN = "|".join((*DIGITS, "สิบ", "ยี่", "ร้อย", "พัน", "หมื่น", "แสน", "ล้าน"))
WORD_NUMBER = rf"(?:{TOKEN})(?:\s*(?:{TOKEN}))*"
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def integer(word):
    if word in DIGITS:
        return DIGITS[word]
    for scale, amount in (("แสน", 100000), ("หมื่น", 10000), ("พัน", 1000), ("ร้อย", 100)):
        if scale in word:
            if word.count(scale) != 1:
                raise ValueError("ตัวเลขคำไทยกำกวม กรุณาระบุเป็นตัวเลข")
            left, right = word.split(scale)
            count = 1 if not left else DIGITS.get(left)
            tail = 0 if not right else integer(right)
            if count is None or not 1 <= count <= 9 or not 0 <= tail < amount:
                raise ValueError("ลำดับตัวเลขคำไทยไม่ถูกต้อง")
            return count * amount + tail
    if word.count("สิบ") == 1:
        left, right = word.split("สิบ")
        tens = 1 if not left else 2 if left == "ยี่" else DIGITS.get(left)
        units = 0 if not right else DIGITS.get(right)
        if tens is not None and 1 <= tens <= 9 and units is not None:
            return tens * 10 + units
    raise ValueError("ตัวเลขคำไทยยังไม่รองรับ กรุณาระบุเป็นตัวเลข")


def fraction(word):
    tokens = re.findall("|".join(DIGITS), word)
    if not tokens or "".join(tokens) != word:
        raise ValueError("ทศนิยมคำไทยกำกวม กรุณาระบุเป็นตัวเลข")
    return "".join(str(DIGITS[token]) for token in tokens)


def normalize(text, track_names=()):
    if "__TKN_LITERAL_" in text:
        raise ValueError("ข้อความมีเครื่องหมายภายใน กรุณาระบุคำสั่งใหม่")
    # Preserve existing, explicitly mentioned and new names, including digits or
    # vocabulary that also appears in commands. Do not fuzzy-correct names.
    protected = {name for name in track_names if isinstance(name, str) and name}
    protected.update(re.findall(r"['\"]([^'\"]+)['\"]", text))
    protected.update(re.findall(r"แทร็ก\s*([^\s,]+)", text))
    protected.update(re.findall(r"(?:หรี่|ลด|เพิ่ม|เปิดเสียง|ปิดเสียง)\s+([A-Za-z0-9_ก-๙]+)", text))
    for name in re.findall(r"เปลี่ยน(?:ชื่อ)?\s*.+?\s+เป็น\s+(.+?)(?=\s*(?:แล้ว|และ|,)|$)", text):
        name = re.sub(r"\s*(?:ให้หน่อย|หน่อย|ครับ|ค่ะ|นะ|ด้วย)\s*$", "", name).strip(" '\"")
        if name:
            protected.add(name)
    literals = {}
    for name in sorted(protected, key=lambda item: (-len(item), item)):
        marker = f"__TKN_LITERAL_{len(literals)}__"
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])"
        if re.search(pattern, text):
            text = re.sub(pattern, lambda match: marker, text)
            literals[marker] = name
    text = text.translate(THAI_DIGITS)
    # Do not accept a known unit as a prefix of a misspelled/different unit.
    # Only known Thai courtesy suffixes may be attached without whitespace.
    for unit in re.finditer(r"(?:ดี\s*บี|เดซิเบล|dB)([A-Za-zก-๙\d]+)", text, re.I):
        if not re.fullmatch(r"(?:ครับ|ค่ะ|นะ|หน่อย|ด้วย|แล้ว|และ|เท่านั้น|อย่างเดียว)+", unit[1]):
            raise ValueError("หน่วยเสียงไม่ชัดเจน กรุณายืนยันว่าเป็น dB")
    if re.search(r"หรือ|ไม่แน่ใจ|ฟังไม่ชัด", text):
        raise ValueError("คำขอมีทางเลือกหรือข้อมูลที่ไม่แน่นอน กรุณายืนยันก่อน")
    text = text.replace("หรี่", "ลด")
    text = re.sub(r"ดี\s*บี|เดซิเบล", "dB", text)
    pattern = rf"(?:(?P<sign>ติดลบ|ลบ)\s*)?(?P<int>{WORD_NUMBER})(?:\s*จุด\s*(?P<frac>{WORD_NUMBER}))?(?=\s*(?:dB|Hz|เฮิรตซ์|ms|มิลลิวินาที))"
    def convert(match):
        whole = integer(re.sub(r"\s+", "", match['int']))
        decimal = "" if not match['frac'] else "." + fraction(re.sub(r"\s+", "", match['frac']))
        return ("-" if match['sign'] else "") + str(whole) + decimal
    text = re.sub(pattern, convert, text, flags=re.I)
    text = re.sub(r"(?:ติดลบ|ลบ)\s*([+]?\d+(?:\.\d+)?)(?=\s*(?:dB|Hz|เฮิรตซ์|ms|มิลลิวินาที))", r"-\1", text, flags=re.I)
    for marker, name in literals.items():
        text = text.replace(marker, name)
    return text.strip()
