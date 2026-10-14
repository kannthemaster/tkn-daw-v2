"""Additive local JARVIS desktop text chat; existing intent boundary unchanged."""
import argparse
import copy
import json
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import intent_engine as ai


class ChatSession:
    def __init__(self, port=7801, model="gemma3:4b"):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Invalid control port")
        self.port, self.model = port, model
        self.pending = None
        self.instruction = None

    def cancel(self):
        self.pending = self.instruction = None

    def preview(self, text):
        self.cancel()
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError("กรุณาพิมพ์คำสั่ง 1–4000 ตัวอักษร")
        snapshot = ai.jarvis.request(self.port, ai.INSPECT)["result"]
        intent = ai.propose(text, snapshot, self.model)
        if intent["clarification"].strip():
            return {"clarification": intent["clarification"]}
        plan = ai.preview(intent, snapshot, self.port)
        self.pending, self.instruction = copy.deepcopy(plan), text
        return copy.deepcopy(plan)

    def apply(self, text, confirmation):
        plan, original = self.pending, self.instruction
        # A consumed or failed plan cannot be retried without a fresh Preview.
        self.cancel()
        if plan is None:
            raise ValueError("ไม่มี Preview ที่รอยืนยัน")
        if text != original:
            raise ValueError("ข้อความเปลี่ยนแล้ว กรุณาสร้าง Preview ใหม่")
        return ai.apply_preview(plan, confirmation, request=ai.jarvis.request)


def review_text(plan):
    lines = ["PREVIEW — ยังไม่ได้เปลี่ยนเซสชัน", ""]
    for index, (action, command) in enumerate(zip(plan["intent"]["actions"], plan["commands"]), 1):
        lines.append(f"{index}. " + json.dumps(action, ensure_ascii=False))
        if action["op"] == "volume_delta":
            lines.append(f"   Fader หลังปรับ: {command['params']['params']['db']} dB")
        lines.append("   คำสั่งจริง: " + json.dumps(command, ensure_ascii=False))
    lines.extend(["", "AI summary (ข้อเสนอ): " + plan["intent"]["summary"],
                  "", "ตรวจแทร็ก ค่า และช่องเอฟเฟกต์ก่อนกดยืนยัน"])
    return "\n".join(lines)


class TextChat:
    def __init__(self, root, session):
        self.root, self.session = root, session
        self.events = queue.Queue()
        self.busy = False
        root.title("TKN DAW V2 · JARVIS Text Chat")
        root.geometry("1000x760")
        root.minsize(760, 600)
        root.configure(bg="#111827")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#111827")
        style.configure("TLabel", background="#111827", foreground="#e5e7eb", font=("Segoe UI", 11))
        style.configure("TButton", font=("Segoe UI", 11), padding=8)
        outer = ttk.Frame(root, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="JARVIS · พิมพ์สั่งงานภาษาไทย", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(outer, text=f"Local Ollama · {session.model}   |   DAW 127.0.0.1:{session.port}   |   Voice พักไว้").pack(anchor="w", pady=(5, 12))
        self.history = scrolledtext.ScrolledText(outer, height=7, wrap="word", font=("Segoe UI", 11),
            bg="#1f2937", fg="#e5e7eb", insertbackground="white", relief="flat", state="disabled")
        self.history.pack(fill="both", expand=True)
        ttk.Label(outer, text="รายการปรับแต่งที่เสนอ").pack(anchor="w", pady=(12, 4))
        self.review = scrolledtext.ScrolledText(outer, height=13, wrap="word", font=("Segoe UI", 11),
            bg="#0f172a", fg="#a7f3d0", relief="flat", state="disabled")
        self.review.pack(fill="both", expand=True)
        ttk.Label(outer, text="คำสั่งของคุณ").pack(anchor="w", pady=(12, 4))
        self.entry = tk.Text(outer, height=3, wrap="word", font=("Segoe UI", 12),
            bg="#1f2937", fg="white", insertbackground="white", relief="flat")
        self.entry.pack(fill="x")
        self.entry.bind("<<Modified>>", self.edited)
        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(10, 0))
        self.send = ttk.Button(buttons, text="สร้าง Preview", command=self.preview)
        self.send.pack(side="left")
        self.confirm = ttk.Button(buttons, text="ยืนยัน Apply…", command=self.apply, state="disabled")
        self.confirm.pack(side="left", padx=8)
        self.cancel_button = ttk.Button(buttons, text="ยกเลิก Preview", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left")
        self.status = ttk.Label(outer, text="พร้อม · พิมพ์คำสั่งแล้วสร้าง Preview ก่อนทุกครั้ง")
        self.status.pack(anchor="w", pady=(10, 0))
        self.say("JARVIS", "พิมพ์คำสั่ง เช่น ลดแทร็ก Voice ลง 2 dB แล้วใส่ Compressor\nผมจะแสดง Preview ให้ตรวจและยืนยันก่อน Apply")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def text(self):
        return self.entry.get("1.0", "end-1c").strip()

    def say(self, who, text):
        self.history.configure(state="normal")
        self.history.insert("end", f"{who}: {text}\n\n")
        self.history.see("end")
        self.history.configure(state="disabled")

    def show_review(self, text):
        self.review.configure(state="normal")
        self.review.delete("1.0", "end")
        self.review.insert("1.0", text)
        self.review.configure(state="disabled")

    def edited(self, _event=None):
        if self.entry.edit_modified():
            if not self.busy and self.session.pending is not None:
                self.cancel()
                self.status.configure(text="ข้อความเปลี่ยน · ต้องสร้าง Preview ใหม่")
            self.entry.edit_modified(False)

    def cancel(self):
        if self.busy:
            return
        self.session.cancel()
        self.confirm.configure(state="disabled")
        self.cancel_button.configure(state="disabled")
        self.show_review("ไม่มี Preview ที่รอยืนยัน")
        self.status.configure(text="ยกเลิก Preview · ไม่ได้ส่งคำสั่งเปลี่ยนเซสชัน")

    def work(self, operation, fn):
        if self.busy:
            return
        self.busy = True
        self.send.configure(state="disabled")
        self.confirm.configure(state="disabled")
        self.cancel_button.configure(state="disabled")
        self.entry.configure(state="disabled")
        self.status.configure(text="กำลังสร้าง Preview…" if operation == "preview" else "กำลัง Apply และ Verify…")
        def worker():
            try:
                self.events.put((operation, fn(), None))
            except Exception as error:
                self.events.put((operation, None, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def preview(self):
        if self.busy:
            return
        text = self.text()
        self.show_review("กำลังตรวจคำสั่ง…")
        self.say("คุณ", text)
        self.work("preview", lambda: self.session.preview(text))

    def apply(self):
        if self.busy or self.session.pending is None:
            return
        text = self.text()
        plan = copy.deepcopy(self.session.pending)
        # The model cannot press this button or acknowledge this modal dialog.
        confirmation_text = (f"Apply {len(plan['commands'])} การปรับแต่งจาก Preview ที่แสดงอยู่?\n\n"
                             f"คำสั่งของคุณ: {text[:300]}\n\n"
                             "ตรวจรายการ แทร็ก ค่า และช่องเอฟเฟกต์ใน Preview แล้วจึงยืนยัน\n"
                             "ระบบจะ Verify ทุกขั้นตอน ไม่มี rollback อัตโนมัติ")
        if not messagebox.askyesno("ยืนยันการปรับเซสชัน", confirmation_text,
                                  parent=self.root, default="no"):
            self.cancel()
            return
        self.work("apply", lambda: self.session.apply(text, plan["confirmation"]))

    def poll(self):
        try:
            while True:
                operation, result, error = self.events.get_nowait()
                self.busy = False
                self.entry.configure(state="normal")
                self.send.configure(state="normal")
                if error:
                    self.session.cancel()
                    self.show_review("ไม่มี Preview ที่รอยืนยัน")
                    self.say("JARVIS", error)
                    self.status.configure(text="หยุด · หาก Apply ล้มเหลว บางขั้นอาจเปลี่ยนแล้ว ไม่มี rollback อัตโนมัติ" if operation == "apply" else "สร้าง Preview ไม่สำเร็จ · ยังไม่ Apply")
                elif operation == "preview" and "clarification" in result:
                    self.show_review("ต้องระบุข้อมูลเพิ่มเติม · ไม่มีคำสั่งที่รอยืนยัน")
                    self.say("JARVIS", result["clarification"])
                    self.status.configure(text="กรุณาปรับคำสั่งให้ชัดเจน")
                elif operation == "preview":
                    self.show_review(review_text(result))
                    self.confirm.configure(state="normal")
                    self.cancel_button.configure(state="normal")
                    self.status.configure(text="Preview พร้อม · ยังไม่ได้เปลี่ยนเซสชัน")
                else:
                    self.say("JARVIS", f"Verify ผ่าน {len(result['steps'])} ขั้นตอน")
                    self.show_review("Apply แล้วและ Verify ผ่าน · สร้าง Preview ใหม่สำหรับคำสั่งถัดไป")
                    self.status.configure(text="เสร็จสิ้น · ผลยืนยันจากสถานะ DAW")
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo("กำลังทำงาน", "รอผลก่อนปิด เพื่อให้ตรวจสถานะ Apply/Verify ได้", parent=self.root)
            return
        self.session.cancel()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=7801)
    parser.add_argument("--model", default="gemma3:4b")
    args = parser.parse_args()
    session = ChatSession(args.port, args.model)
    root = tk.Tk()
    TextChat(root, session)
    root.mainloop()


if __name__ == "__main__":
    main()
