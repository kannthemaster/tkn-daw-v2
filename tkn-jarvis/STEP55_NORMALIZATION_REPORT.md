# Step 5.5 — Thai normalization and fresh evaluation

Step 5.4 ถูก Commit/Push แล้วที่ **9b550b0dbee09826f4be056309d2235ccf704266** บน
develop/tkn-daw-v2-integration; ยืนยัน remote ด้วย git ls-remote
รายงาน Step 5.4 เดิมเป็น snapshot ก่อน Commit นี้ ข้อความยังไม่ Commit ในรายงานเก่าจึงไม่ใช่สถานะล่าสุด
รายงานนี้บันทึกผลทดสอบก่อนเผยแพร่ Step 5.5; ดู Commit ที่บรรจุรายงานนี้และ git log สำหรับสถานะเผยแพร่
ไม่แก้ main หรือไฟล์เดิมของ TKN DAW V1

## สิ่งที่เปลี่ยน

เพิ่ม thai_normalizer.py และเรียกผ่าน intent_policy.py ก่อนสร้าง contract
หรี่ → ลด, ดีบี/ดี บี/เดซิเบล → dB, เลขไทย → เลขอารบิก, ตัวเลขคำไทยตามตำแหน่งค่า/หน่วย
รองรับจำนวนเต็มแบบมาตรฐานถึง 999999 และทศนิยมที่อ่านทีละหลัก; ขอบเขตค่าของ DAW ยังคงเดิม
รักษาเครื่องหมายลบและเลขศูนย์ในทศนิยม ไม่แก้ชื่อแทร็กหรือชื่อใหม่โดย fuzzy matching
จำนวนที่กำกวม หน่วยสะกดผิด dBA คำปฏิเสธ และคำขอข้ามการยืนยันจะถามกลับโดยไม่มี actions
เพิ่ม Regression Tests ตรวจผล fader จริงจาก dry preview, การรักษาชื่อ และขอบเขตความปลอดภัย
แก้ไฟล์เดิมเฉพาะ intent_policy.py; engine/apply/verify และ Rust production ไม่เปลี่ยน

## ผลแรกที่ไม่ผ่าน — เก็บไว้ครบ

V2 เป็นชุดใหม่ 24 กรณีที่ตรึงก่อนประเมิน ได้ 23/24 (95.8%) แต่ **ไม่ผ่าน safety gate**
v219_bad_unit: หรี่ Cello ลงสามดีบี้ ถูกแปลงเป็น volume_delta -3 ทั้งที่ต้องถามกลับ
มี unjustified proposal 1; attempted DAW calls 0 เพราะ Benchmark กัน Apply ไว้
หลังจบทั้งรอบจึงเพิ่ม unit-suffix guard และ regression สำหรับคำสะกดผิด
V2 กลายเป็น regression data; ผลหลังแก้ V2 ไม่ถูกนำมาเรียก held-out accuracy
ไม่ได้แก้ข้อสอบหรือโค้ดระหว่างรอบแรก และไม่ซ่อนผลที่ผิดด้วยการรายงานเฉพาะรอบที่ผ่าน

## ชุดใหม่หลังแก้ — V3

สร้างข้อความ/fixtures ใหม่ 20 กรณี แล้วตรึงก่อนรันสองรอบ ไม่มีการปรับระบบระหว่างประเมิน
wrapper ใหม่บันทึก hashes ของ engine/policy/converter/dataset/runner ก่อนและหลัง ซึ่งตรงกัน

- รอบ 1: 20/20; รอบ 2: 20/20
- รวม 40/40 (100.0%)
- คำขอที่ต้องถามกลับ: 16/16
- wrong/unjustified proposals: 0/0
- errors: 0; attempted DAW calls: 0
- สถานะ: ผ่านทุกกรณีที่ประเมิน

ชุดนี้เขียนโดยผู้พัฒนาคนเดียวกัน ไม่ใช่ external blind/population sampling
ข้อความ ASR-like จำลองด้วยการเขียน ไม่ใช่ผลจาก STT หรือไมโครโฟนจริง
คะแนนจำกัดเฉพาะชุดนี้ ไม่รับรองการตีความเสียงพูดไทยทั่วไปหรือทุกชื่อแทร็ก/สำนวน

## การทดสอบประกอบ

| การตรวจ | ผล |
| --- | --- |
| original | 30/30 หลัก; 31/31 รวม |
| v1 | 30/30 หลัก; 30/30 รวม |
| v2 | 24/24 หลัก; 24/24 รวม |
| Python tests | 91 ผ่าน |
| Full CI | fmt/clippy/test/assets/layers/wasm ผ่าน; exit 0 |
| Real Windows local AI smoke | หรี่เสียงร้องลงสองดี บี → Preview; ยกเลิกไม่เปลี่ยน session; ยืนยัน Apply → Verify → คืนค่า demo ผ่าน |

Smoke ใช้ native SoundCraft ที่แยกไว้ ปิด audio ไม่เชื่อม session ผู้ใช้
การยืนยันอัตโนมัติจำกัดเฉพาะ disposable fixture นี้ โปรแกรมยังคง Preview → ยืนยัน → Apply → Verify
ไม่มี Apply ระหว่าง Benchmark; confirmed smoke ใช้เฉพาะแผนที่ตรวจว่ามี volume_delta -2 ตรงคำขอ
ยังไม่ได้ทดสอบ playback/recording/Audio Interface/latency หรือ VST3/CLAP จริง
Full CI มี warning เดิม CaptureStates ใน WASM โดยทุก gate ยังผ่าน

## หลักฐานและการย้อนกลับ

- Published checkpoint: 9b550b0dbee09826f4be056309d2235ccf704266
- V2 first dataset SHA256: 9f16988c4f4a3a596e7ba5571daeb014b805ace3873971451d445495ac64f57d
- V3 frozen dataset SHA256: b2ac2485e75a8176fec8a370b4f922659ee0e4885233e755c8ede4779cdd91b2
- Converter SHA256: f192345879460395ffa2bd6496cd90e2a0e6f3861eed8574beaab34eef7ebc12
- Policy SHA256: 6067a95d77e99f0e5f1a14da86dcf96dd1a277cfef4e26f27da26accd8f588ce
- ก่อน/หลังประเมิน: source_receipt.json; raw last model response + expected/actual + metadata: results JSON
- V2 เดิมใช้ runner ที่บันทึก engine/runner/dataset hash แต่ไม่บันทึก helper dependency hash;
  V3 และ regression รอบสุดท้ายเพิ่ม source receipt เพื่อระบุโค้ดตัวแปลงที่ใช้จริง
- ZIP เป็นไฟล์ใหม่และ intent_policy.py สำหรับใช้กับ repo ที่ checkpoint ข้างต้น
  แพตช์แสดงเฉพาะไฟล์เดิม ต้องมี thai_normalizer.py ด้วย

## ขั้นตอนถัดไป

ตรวจ Diff แล้วเก็บ Checkpoint Step 5.5 ก่อนเริ่ม Step 6 แยกต่างหาก
Voice Control ต้องให้ผู้ใช้ตรวจ transcript และ Preview พร้อมยืนยันก่อน Apply
เครื่องหมายลบหรือชื่อแทร็กที่ STT ถอดผิดอาจยังเป็นข้อความที่ถูก Schema จึงห้ามถือคะแนนชุดนี้เป็นหลักฐานความแม่นยำเสียงจริง
