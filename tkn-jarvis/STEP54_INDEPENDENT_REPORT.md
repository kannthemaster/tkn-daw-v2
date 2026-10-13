# Step 5.4 — Release Checkpoint & Independent Benchmark

## Checkpoint ที่เผยแพร่แล้ว

Commit `aaa5169ab49029276e808053e897d3117f65dec4` เก็บ Step 5.2–5.3 บน
`develop/tkn-daw-v2-integration` และ Push สำเร็จ ยืนยัน remote ด้วย git ls-remote
8 ไฟล์ใน Checkpoint; ไม่มี work/log/demo audio หรือรายงาน Step 3 เก่ารวมอยู่
Full CI ก่อน Commit ผ่านทุก gate, Python 79 tests ผ่าน ไม่มี merge เข้า main หรือแก้ไฟล์เดิมของ TKN DAW V1

## งาน Step 5.4 หลัง Checkpoint (ยังไม่ได้ Commit/Push)

แก้เฉพาะ intent_engine.py และ test_intent_engine.py เพื่อแก้ rename_then_mute
แผนที่มี rename ต่อด้วยคำสั่งอื่นให้โมเดลเสนอทีละขั้นภายใต้ Schema ของขั้นนั้น
จากนั้นตรวจคำสั่งรวมและ dry preflight ทั้งแผน ไม่มีการ Apply ระหว่างเสนอแผน
เมื่อขั้นถัดไปผิดหรือถามกลับจะไม่คืนแผนบางส่วน และไม่ซ่อมคำตอบผิดด้วยการเพิ่มคำสั่งเอง
Known rename regression บนชุดเดิมผ่านโมเดลจริง 5/5 รอบ
การวางแผนหลายขั้นที่มี rename เรียกโมเดลเพิ่มตามจำนวนคำสั่ง จึงใช้เวลามากขึ้น
เป็นเวลาในการเสนอแผน ไม่ใช่การวัด latency ของ Audio Interface

## ผลชุดใหม่

ชุดใหม่ 30 กรณี เก็บคำตอบที่คาดหวังก่อนรัน ไม่เปลี่ยน dataset/oracle หลังเห็นผล
แยกจากชุดพัฒนาเดิม แต่เขียนโดยผู้พัฒนาคนเดียวกัน ไม่ใช่ external blind evaluation
คำที่ถอดเสียงผิดเป็นข้อความจำลอง ไม่ได้ใช้ไมโครโฟนหรือ Speech-to-Text จริง
ใช้ gemma3:4b บน Ollama ในเครื่อง, synthetic sessions และ no-Apply fences

- รอบ 1: 28/30; รอบ 2: 28/30; รอบ 3: 28/30
- รวม 84/90 (93.3%)
- คำขอที่ต้องถามกลับ: 36/36
- ข้อเสนอสุดท้ายผิด/เกินขอบเขต: 0 / 0
- Provider/runner errors: 0; attempted DAW calls: 0
- Model-response cases: 48; local-guard cases: 42
- Benchmark exit 1: ยังไม่ผ่านทุกกรณี แม้การปฏิเสธจะปลอดภัย

### กรณีที่ยังไม่ผ่าน

- `h05_hrii` ไม่ผ่าน 3/3 รอบ: หรี่ Piano ลงอีก 1 dB — clarification; ข้อเสนอสุดท้าย: {"summary": "", "clarification": "ยังตรวจความหมายส่วนนี้ไม่ได้ กรุณาระบุคำขอให้ชัดเจน", "actions": []}
- `h17_asr_unit_spacing` ไม่ผ่าน 3/3 รอบ: ลด Piano ลง สอง ดี บี — clarification; ข้อเสนอสุดท้าย: {"summary": "", "clarification": "กรุณาระบุค่าระดับเสียงที่ต้องการ", "actions": []}

ไม่ได้ปรับ engine ตามข้อสอบใหม่ระหว่างสามรอบ จึงคง first-pass evaluation ไว้
หากนำกรณีเหล่านี้ไปใช้แก้ engine ในอนาคต ต้องเรียกชุดนี้ว่า regression และจัดชุด held-out ใหม่
คะแนนเป็นของระบบ parser + schema + model + validator ในชุดจำกัด ไม่ใช่ความแม่นยำภาษาไทยทั่วไป

## การทดสอบประกอบ

- ชุดเดิมหลังแก้: 30/30 หลัก;
  31/31 รวม prompt-overlap;
  wrong/unjustified 0/0, no Apply
- Python Regression Tests: 80 ผ่าน
- Full CI: fmt/clippy/test/assets/layers/wasm ผ่านทุก gate, exit 0
- Native Windows Build (--locked), CLI/control smoke: ผ่าน
- Real local AI + cancelled CLI: ไม่มีการเปลี่ยน session; confirmed Apply → Verify และคืนค่า demo: ผ่าน
- มี warning เดิม CaptureStates ใน WASM ซึ่งไม่ทำให้ CI ล้มเหลว
- ลำโพง Recording, Audio Interface, latency และปลั๊กอิน VST3/CLAP จริง: ยังไม่ได้ทดสอบ

## Reproducibility

- Published rollback checkpoint: aaa5169ab49029276e808053e897d3117f65dec4
- Evaluated engine working-copy SHA256: 39502e7bf3e979221270705cadabe988dae81b24fa9734fb446ca54092c8e22c
- Additional policy SHA256: 9840f3de4aa48999db0fa06bf00307569d358a0dcdb3166cb2fbedcc1ad2cf70
- Held-out dataset SHA256: bff5644d5f461776ba3d6e9c79d9744f1ff4dc70b1b7fc1b60688ec3a4f37e67
- Unchanged benchmark runner SHA256: d253766d1a5823b96aaa8c5450c1afcecbc95d8cbedbe60d428a3eec94330968
- Evaluation finished UTC: 2026-10-13T23:11:17.633313+00:00
- Model metadata/digest, raw last response, original transcript and expected/actual actions: results JSON
  สำหรับแผน rename หลายขั้น runner เก็บ raw response สุดท้ายเท่านั้น แต่บันทึก API paths และแผนรวมที่ตรวจแล้ว

## ขั้นตอนถัดไป

ยังไม่เริ่ม Step 6 เพราะชุดใหม่มีคำขอที่ควรสำเร็จแต่ยังถูกปฏิเสธ
ควรตรวจ Diff ของ rename fix และเก็บ Checkpoint Step 5.4 เพิ่ม จากนั้นแก้จุดที่รายงาน
ด้วย regression tests และประเมินกับชุดภาษาไทยใหม่ที่ยังไม่ใช้ปรับระบบ ก่อนเชื่อม Voice Control
คำสั่งที่ STT ทำคำสำคัญหรือเครื่องหมายลบหายอาจกลายเป็นคำสั่งที่ถูก Schema ได้
จึงต้องแสดงข้อความที่ถอดเสียงและ Preview ให้ผู้ใช้ตรวจ พร้อมการยืนยันก่อน Apply เสมอ
