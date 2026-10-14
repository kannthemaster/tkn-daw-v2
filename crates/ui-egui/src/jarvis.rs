//! JARVIS presentation state and bounded host channels, separate from session data.
use crate::ControlRequest;
use serde_json::{Value, json};
use soundcraft_model::Session;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{Receiver, SyncSender, TryRecvError};

pub type Start = dyn Fn(&egui::Context) -> Result<Connection, String>;

pub struct Connection {
    pub requests: SyncSender<Value>,
    pub replies: Receiver<Result<Value, String>>,
    pub control: Receiver<ControlRequest>,
    pub stop: Arc<AtomicBool>,
}

impl Drop for Connection {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Release);
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
enum Phase {
    #[default]
    Idle,
    Starting,
    Planning,
    Applying,
}

#[derive(Default)]
pub struct State {
    pub instruction: String,
    pub history: Vec<(String, String)>,
    pub status: String,
    pub preview: Option<Value>,
    confirmation_open: bool,
    confirmation_first: bool,
    connection: Option<Connection>,
    phase: Phase,
    attempted_start: bool,
    generation: u64,
    next_id: u32,
    awaiting: Option<(u32, u64)>,
    expected_session: Option<Arc<Session>>,
    last_session: Option<Arc<Session>>,
    preview_instruction: String,
    applying_commands: Vec<Value>,
    expected_steps: usize,
}

impl State {
    pub fn applying(&self) -> bool {
        self.phase == Phase::Applying
    }
    pub fn busy(&self) -> bool {
        self.phase != Phase::Idle
    }
    fn say(&mut self, who: &str, text: &str) {
        if self.history.len() >= 50 {
            self.history.remove(0);
        }
        self.history.push((who.into(), text.chars().take(4000).collect()));
    }
    fn fail(&mut self, message: &str) {
        let may_write = self.applying();
        self.status = if may_write {
            format!("หยุด: {message} — บางขั้นอาจเปลี่ยนแล้ว ไม่มี rollback อัตโนมัติ")
        } else {
            format!("JARVIS ไม่พร้อม: {message}")
        };
        let status = self.status.clone();
        self.say("JARVIS", &status);
        self.connection = None;
        self.phase = Phase::Idle;
        self.preview = None;
        self.confirmation_open = false;
        self.awaiting = None;
        self.expected_session = None;
        self.applying_commands.clear();
    }
    pub fn invalidate(&mut self) {
        if self.applying() {
            return;
        }
        self.generation = self.generation.saturating_add(1);
        if self.preview.is_some() || self.busy() {
            self.connection = None;
            self.phase = Phase::Idle;
            self.attempted_start = false;
            self.awaiting = None;
            self.status = "Preview หมดอายุ — กรุณาสร้างใหม่".into();
        }
        self.preview = None;
        self.expected_session = None;
        self.confirmation_open = false;
    }
    pub fn cancel(&mut self) {
        if self.applying() {
            return;
        }
        self.invalidate();
        self.status = "ยกเลิก — ไม่ได้ส่งคำสั่งเปลี่ยนเซสชัน".into();
    }
    fn send(&mut self, method: &str, fields: Value, phase: Phase) -> Result<(), String> {
        let mut msg = fields.as_object().cloned().ok_or("Invalid bridge fields")?;
        self.next_id = self.next_id.checked_add(1).filter(|id| *id <= 2147483647).unwrap_or(1);
        msg.insert("version".into(), json!(1));
        msg.insert("id".into(), json!(self.next_id));
        msg.insert("method".into(), json!(method));
        self.connection.as_ref().ok_or("Python Sidecar ยังไม่พร้อม")?.requests.try_send(Value::Object(msg)).map_err(|error| error.to_string())?;
        self.awaiting = Some((self.next_id, self.generation));
        self.phase = phase;
        Ok(())
    }
    pub fn request_preview(&mut self, session: Arc<Session>) {
        if self.busy() {
            return;
        }
        let text = self.instruction.trim().to_string();
        if text.is_empty() || text.chars().count() > 4000 {
            self.status = "กรุณาพิมพ์คำสั่ง 1–4000 ตัวอักษร".into();
            return;
        }
        self.preview = None;
        self.confirmation_open = false;
        self.preview_instruction = text.clone();
        self.expected_session = Some(session);
        self.say("คุณ", &text);
        if let Err(error) = self.send("preview", json!({"context": self.generation.to_string(), "instruction": text}), Phase::Planning) {
            self.fail(&error);
        } else {
            self.status = "กำลังสร้าง Preview…".into();
        }
    }
    fn request_apply(&mut self) {
        if self.busy() {
            return;
        }
        let Some(plan) = self.preview.take() else {
            return;
        };
        self.confirmation_open = false;
        self.applying_commands = plan.get("commands").and_then(Value::as_array).cloned().unwrap_or_default();
        self.expected_steps = self.applying_commands.len();
        let fields = json!({"context": self.generation.to_string(), "instruction": self.preview_instruction,
            "preview_id": plan.get("preview_id"), "confirmation": plan.get("confirmation"), "confirmed": true});
        if let Err(error) = self.send("apply", fields, Phase::Applying) {
            self.fail(&error);
        } else {
            self.status = "กำลัง Apply และ Verify…".into();
        }
    }
    fn receive(&mut self, reply: Value) {
        if reply.get("version").and_then(Value::as_u64) != Some(1) {
            self.fail("Bridge protocol version ไม่ตรงกัน");
            return;
        }
        if self.phase == Phase::Starting {
            if reply.get("id").is_some_and(Value::is_null)
                && reply.get("ok").and_then(Value::as_bool) == Some(true)
                && reply.pointer("/result/state").and_then(Value::as_str) == Some("ready")
            {
                self.phase = Phase::Idle;
                self.status = "พร้อม — ทุกคำสั่งต้องสร้าง Preview ก่อน".into();
            } else {
                self.fail("Sidecar handshake ไม่ถูกต้อง");
            }
            return;
        }
        let Some((id, generation)) = self.awaiting.take() else {
            self.fail("Unexpected Sidecar response");
            return;
        };
        if reply.get("id").and_then(Value::as_u64) != Some(u64::from(id)) || generation != self.generation {
            self.fail("Preview context changed");
            return;
        }
        if reply.get("ok").and_then(Value::as_bool) != Some(true) {
            let message = reply.pointer("/error/message").and_then(Value::as_str).unwrap_or("Sidecar error");
            self.fail(message);
            return;
        }
        let result = reply.get("result").cloned().unwrap_or(Value::Null);
        match (self.phase, result.get("state").and_then(Value::as_str)) {
            (Phase::Planning, Some("preview"))
                if result.get("changes").and_then(Value::as_array).is_some_and(|a| !a.is_empty() && a.len() <= 16)
                    && result.get("commands").and_then(Value::as_array).is_some_and(|a| !a.is_empty() && a.len() <= 16)
                    && result.get("preview_id").and_then(Value::as_str).is_some_and(|s| s.len() == 32)
                    && result.get("confirmation").and_then(Value::as_str).is_some_and(|s| s.len() == 64) =>
            {
                self.preview = Some(result);
                self.phase = Phase::Idle;
                self.status = "Preview พร้อม — ยังไม่ได้เปลี่ยนเซสชัน".into();
            }
            (Phase::Planning, Some("clarification")) => {
                self.say("JARVIS", result.get("message").and_then(Value::as_str).unwrap_or("กรุณาระบุคำสั่งให้ชัดเจน"));
                self.phase = Phase::Idle;
                self.expected_session = None;
                self.status = "ต้องระบุข้อมูลเพิ่มเติม — ไม่มีแผน Apply".into();
            }
            (Phase::Applying, Some("verified"))
                if result.get("verified").and_then(Value::as_bool) == Some(true)
                    && self.applying_commands.is_empty()
                    && result.get("steps").and_then(Value::as_array).is_some_and(|steps| {
                        !steps.is_empty()
                            && steps.len() == self.expected_steps
                            && steps.len() <= 16
                            && steps.iter().all(|step| step.get("verified").and_then(Value::as_bool) == Some(true))
                    }) =>
            {
                let count = result.get("steps").and_then(Value::as_array).map_or(0, Vec::len);
                self.status = format!("Verify ผ่าน {count} ขั้นตอน");
                let status = self.status.clone();
                self.say("JARVIS", &status);
                self.phase = Phase::Idle;
                self.expected_session = None;
            }
            _ => self.fail("Invalid Sidecar result; success not established"),
        }
    }
    pub fn tick(&mut self, ctx: &egui::Context, session: Arc<Session>, visible: bool, start: Option<&Start>) {
        if !visible && !self.applying() {
            self.connection = None;
            self.phase = Phase::Idle;
            self.preview = None;
            self.awaiting = None;
            self.expected_session = None;
            self.confirmation_open = false;
            self.last_session = None;
            self.attempted_start = false;
            return;
        }
        if self.expected_session.as_ref().or(self.last_session.as_ref()).is_some_and(|old| !Arc::ptr_eq(old, &session)) && !self.applying() {
            self.invalidate();
        }
        self.last_session = Some(session);
        if self.connection.is_none() && visible && !self.attempted_start {
            self.attempted_start = true;
            match start.map_or_else(|| Err("JARVIS Sidecar ใช้ได้ใน Native Desktop เท่านั้น".into()), |start| start(ctx))
            {
                Ok(connection) => {
                    self.connection = Some(connection);
                    self.phase = Phase::Starting;
                    self.status = "กำลังเปิด Python Sidecar…".into();
                }
                Err(error) => self.fail(&error),
            }
        }
        for _ in 0..8 {
            let received = self.connection.as_ref().map(|connection| connection.replies.try_recv());
            match received {
                Some(Ok(Ok(reply))) => self.receive(reply),
                Some(Ok(Err(error))) => {
                    self.fail(&error);
                    break;
                }
                Some(Err(TryRecvError::Disconnected)) => {
                    self.fail("Python Sidecar disconnected");
                    break;
                }
                _ => break,
            }
        }
        if self.busy() {
            ctx.request_repaint_after(std::time::Duration::from_millis(100));
        }
    }
    pub(crate) fn controls(&self) -> Vec<ControlRequest> {
        self.connection.as_ref().map(|connection| connection.control.try_iter().take(16).collect()).unwrap_or_default()
    }
    pub(crate) fn authorize(&self, request: &ControlRequest, current: &Arc<Session>) -> bool {
        self.connection.as_ref().is_some_and(|connection| !connection.stop.load(Ordering::Acquire))
            && self.expected_session.as_ref().is_some_and(|expected| Arc::ptr_eq(expected, current))
            && match request.method.as_str() {
                "session.inspect" => matches!(self.phase, Phase::Planning | Phase::Applying),
                "engine.execute" => {
                    self.applying()
                        && self.applying_commands.first().is_some_and(|command| {
                            command.get("method").and_then(Value::as_str) == Some(request.method.as_str())
                                && command.get("params") == Some(&request.params)
                        })
                }
                _ => false,
            }
    }
    pub(crate) fn wrote(&mut self, session: Arc<Session>) {
        self.expected_session = Some(session);
        if !self.applying_commands.is_empty() {
            self.applying_commands.remove(0);
        }
    }
    pub fn inspect(&self) -> Value {
        json!({"status": self.status, "busy": self.busy(), "applying": self.applying(),
            "preview": self.preview, "history_count": self.history.len(), "sidecar": self.connection.is_some()})
    }
}

fn changes(ui: &mut egui::Ui, plan: &Value) {
    if let Some(actions) = plan.get("changes").and_then(Value::as_array) {
        for (index, action) in actions.iter().enumerate() {
            let text = |key| action.get(key).and_then(Value::as_str).unwrap_or("?");
            let value = |key| action.get(key).map_or_else(|| "?".into(), Value::to_string);
            let detail = match text("op") {
                "volume" => format!("ตั้ง Volume เป็น {} dB", value("db")),
                "volume_delta" => format!("ปรับ Volume {} dB · หลัง Apply {} dB", value("db"), value("absolute_fader_db")),
                "rename" => format!("เปลี่ยนชื่อเป็น {}", text("name")),
                "mute" => {
                    if action.get("value").and_then(Value::as_bool) == Some(true) {
                        "Mute".into()
                    } else {
                        "Unmute".into()
                    }
                }
                "insert" => format!("ใส่ {} ช่อง {}", text("effect"), value("slot")),
                "parameter" => format!("{} ช่อง {} · {} = {}", text("effect"), value("slot"), text("param"), value("value")),
                _ => "รายการไม่รู้จัก — กรุณายกเลิก".into(),
            };
            ui.strong(format!("{}. {}", index + 1, text("track")));
            ui.label(detail);
            ui.separator();
        }
    }
}

pub fn panel(app: &mut crate::SoundApp, ui: &mut egui::Ui) {
    let session = app.engine.session_arc();
    let state = &mut app.jarvis;
    ui.heading("JARVIS");
    ui.label("Local AI · พิมพ์คำสั่งภาษาไทย");
    ui.label(&state.status);
    ui.separator();
    let available = ui.available_height();
    egui::ScrollArea::vertical().id_salt("jarvis-history").max_height((available * 0.22).max(60.0)).stick_to_bottom(true).show(ui, |ui| {
        for (who, text) in &state.history {
            ui.label(format!("{who}: {text}"));
        }
    });
    if let Some(plan) = &state.preview {
        ui.strong("PREVIEW — ยังไม่ Apply");
        egui::ScrollArea::vertical().id_salt("jarvis-preview").max_height((available * 0.42).max(100.0)).show(ui, |ui| changes(ui, plan));
    }
    ui.add_space(8.0);
    ui.add_enabled_ui(!state.busy(), |ui| {
        let response = ui.add(
            egui::TextEdit::multiline(&mut state.instruction)
                .desired_rows(3)
                .desired_width(f32::INFINITY)
                .char_limit(4000)
                .hint_text("ลดแทร็ก Voice ลง 2 dB"),
        );
        if response.changed() {
            state.invalidate();
        }
    });
    ui.horizontal_wrapped(|ui| {
        if ui.add_enabled(!state.busy() && state.connection.is_some(), egui::Button::new("สร้าง Preview")).clicked() {
            state.request_preview(session);
        }
        if ui.add_enabled(!state.busy() && state.preview.is_some(), egui::Button::new("ยืนยัน Apply…")).clicked() {
            state.confirmation_open = true;
            state.confirmation_first = true;
        }
        if ui.add_enabled(!state.applying() && (state.preview.is_some() || state.busy()), egui::Button::new("Cancel")).clicked() {
            state.cancel();
        }
        if !state.busy() && state.connection.is_none() && ui.button("เชื่อมต่อใหม่").clicked() {
            state.attempted_start = false;
        }
    });
}

pub fn confirmation(app: &mut crate::SoundApp, ctx: &egui::Context) {
    let state = &mut app.jarvis;
    if !state.confirmation_open {
        return;
    }
    let Some(plan) = state.preview.clone() else {
        state.confirmation_open = false;
        return;
    };
    let mut decision = None;
    let modal = egui::Modal::new(egui::Id::new("jarvis-confirm")).show(ctx, |ui| {
        ui.set_max_width(480.0);
        ui.heading("ยืนยัน Apply รายการนี้?");
        egui::ScrollArea::vertical().max_height(300.0).show(ui, |ui| changes(ui, &plan));
        ui.label("ระบบจะ Verify ทุกขั้นตอน ไม่มี rollback อัตโนมัติ");
        ui.horizontal(|ui| {
            let no = ui.button("ไม่ — Cancel");
            if state.confirmation_first {
                no.request_focus();
            }
            if no.clicked() {
                decision = Some(false);
            }
            if ui.button("ยืนยัน Apply").clicked() {
                decision = Some(true);
            }
        });
    });
    state.confirmation_first = false;
    if modal.should_close() {
        decision = Some(false);
    }
    match decision {
        Some(true) => state.request_apply(),
        Some(false) => state.cancel(),
        None => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use soundcraft_engine::Engine;
    use std::sync::mpsc::{channel, sync_channel};

    type Fixture = (State, std::sync::mpsc::Sender<Result<Value, String>>, Receiver<Value>, Arc<AtomicBool>);

    fn connected() -> Fixture {
        let (tx, requests) = sync_channel(1);
        let (replies, rx) = channel();
        let (_, control) = channel();
        let stop = Arc::new(AtomicBool::new(false));
        let state = State { connection: Some(Connection { requests: tx, replies: rx, control, stop: stop.clone() }), ..State::default() };
        (state, replies, requests, stop)
    }
    #[test]
    fn default_state_has_no_process_or_pending_plan() {
        let state = State::default();
        assert!(!state.busy());
        assert!(state.preview.is_none());
        assert!(state.connection.is_none());
    }
    #[test]
    fn editing_invalidates_preview_and_stops_owned_sidecar() {
        let (mut state, _, _, stop) = connected();
        state.preview = Some(json!({}));
        state.invalidate();
        assert!(state.preview.is_none());
        assert!(stop.load(Ordering::Acquire));
    }
    #[test]
    fn changing_document_invalidates_plan_even_when_revision_or_names_match() {
        let (mut state, _, _, stop) = connected();
        let first = Engine::default().session_arc();
        state.last_session = Some(first);
        state.preview = Some(json!({}));
        state.tick(&egui::Context::default(), Engine::default().session_arc(), true, None);
        assert!(state.preview.is_none());
        assert!(stop.load(Ordering::Acquire));
    }
    #[test]
    fn closing_during_apply_keeps_sidecar_until_verification_returns() {
        let (mut state, _replies, _requests, stop) = connected();
        state.phase = Phase::Applying;
        state.tick(&egui::Context::default(), Engine::default().session_arc(), false, None);
        assert!(!stop.load(Ordering::Acquire));
        assert!(state.applying());
    }
    #[test]
    fn foreign_document_requests_cannot_write_even_during_apply() {
        let (mut state, _, _, _) = connected();
        state.phase = Phase::Applying;
        let first = Engine::default().session_arc();
        state.expected_session = Some(first.clone());
        state.applying_commands = vec![json!({"method":"engine.execute","params":{}})];
        let (request, _) = ControlRequest::new("engine.execute", json!({}));
        assert!(state.authorize(&request, &first));
        assert!(!state.authorize(&request, &Engine::default().session_arc()));
        state.phase = Phase::Planning;
        assert!(!state.authorize(&request, &first));
    }
    #[test]
    fn incomplete_verification_is_never_presented_as_success() {
        let (mut state, _, _, _) = connected();
        state.phase = Phase::Applying;
        state.awaiting = Some((1, 0));
        state.receive(json!({"version":1,"id":1,"ok":true,"result":{"state":"verified","verified":true,"steps":[{"verified":false}]}}));
        assert!(!state.status.starts_with("Verify ผ่าน"));
        assert!(state.status.contains("rollback"));
    }
}
