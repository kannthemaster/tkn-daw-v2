//! UI confirmation and document ownership with a simulated Sidecar, real engine dispatch.
use egui_kittest::{Harness, kittest::Queryable};
use serde_json::{Value, json};
use soundcraft_ui_egui::{ControlRequest, Services, SoundApp, jarvis::Connection};
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, Ordering},
    mpsc::{Receiver, Sender, channel, sync_channel},
};

#[test]
fn window_menu_exposes_the_jarvis_command() {
    let tree = soundcraft_ui_egui::menus::tree();
    let window = tree.iter().find(|node| node.label == "Window").unwrap();
    assert!(window.children.iter().any(|node| node.path == "Window > JARVIS"));
}

struct Fixture {
    h: Harness<'static, SoundApp>,
    requests: Receiver<Value>,
    replies: Sender<Result<Value, String>>,
    control: Sender<ControlRequest>,
    stop: Arc<AtomicBool>,
    preview_request: Value,
    command: Value,
}

fn preview() -> Fixture {
    let (requests_tx, requests) = sync_channel(1);
    let (replies, replies_rx) = channel();
    let (control, control_rx) = channel();
    let stop = Arc::new(AtomicBool::new(false));
    let connection = Arc::new(Mutex::new(Some(Connection { requests: requests_tx, replies: replies_rx, control: control_rx, stop: stop.clone() })));
    let mut app = SoundApp::new(
        soundcraft_engine::Engine::default(),
        None,
        Services {
            jarvis_start: Some(Box::new(move |_| connection.lock().unwrap().take().ok_or("Test connection consumed".into()))),
            ..Services::default()
        },
    );
    app.run("track.new", json!({"name":"Voice"})).unwrap();
    let id = app.engine.session().tracks[0].id.0;
    app.ui.show_jarvis = true;
    app.jarvis.instruction = "ลดแทร็ก Voice ลง 2 dB".into();
    replies.send(Ok(json!({"version":1,"id":null,"ok":true,"result":{"state":"ready"}}))).unwrap();
    let mut h = Harness::builder().with_size(egui::vec2(1400.0, 900.0)).build_ui_state(
        |ui, app: &mut SoundApp| {
            app.logic(&ui.ctx().clone());
            app.ui(ui);
        },
        app,
    );
    h.run_steps(5);
    h.get_by_label("สร้าง Preview").click();
    h.run_steps(3);
    let preview_request = requests.try_recv().unwrap();
    assert_eq!(preview_request["method"], "preview");
    let command = json!({"method":"engine.execute","params":{"command":"mix.volume","params":{"track":id,"db":-2.0}}});
    replies
        .send(Ok(json!({"version":1,"id":preview_request["id"],"ok":true,"result":{
            "state":"preview","preview_id":"a".repeat(32),"confirmation":"b".repeat(64),
            "changes":[{"op":"volume_delta","track":"Voice","db":-2.0,"absolute_fader_db":-2.0}],"commands":[command.clone()]
        }})))
        .unwrap();
    h.run_steps(3);
    assert!(h.state().jarvis.preview.is_some());
    Fixture { h, requests, replies, control, stop, preview_request, command }
}

#[test]
fn confirmation_defaults_to_cancel_and_sends_no_apply() {
    let mut f = preview();
    let before = serde_json::to_value(f.h.state().engine.session()).unwrap();
    f.h.get_by_label("ยืนยัน Apply…").click();
    f.h.run_steps(3);
    f.h.event(egui::Event::Key { key: egui::Key::Enter, physical_key: None, pressed: true, repeat: false, modifiers: egui::Modifiers::NONE });
    f.h.run_steps(3);
    assert!(f.requests.try_recv().is_err());
    assert!(f.stop.load(Ordering::Acquire));
    assert!(f.h.state().jarvis.preview.is_none());
    assert_eq!(serde_json::to_value(f.h.state().engine.session()).unwrap(), before);
}

#[test]
fn deliberate_confirmation_dispatches_exact_plan_then_reports_verified_result() {
    let mut f = preview();
    f.h.get_by_label("ยืนยัน Apply…").click();
    f.h.run_steps(3);
    f.h.get_by_label("ยืนยัน Apply").click();
    f.h.run_steps(3);
    let apply = f.requests.try_recv().unwrap();
    assert_eq!(apply["method"], "apply");
    assert_eq!(apply["confirmed"], true);
    assert_eq!(apply["context"], f.preview_request["context"]);
    let (request, response) = ControlRequest::new("engine.execute", f.command["params"].clone());
    f.control.send(request).unwrap();
    f.h.run_steps(3);
    assert_eq!(response.try_recv().unwrap()["ok"], true);
    assert!(f.h.state().jarvis.applying());
    f.replies
        .send(Ok(json!({"version":1,"id":apply["id"],"ok":true,"result":{"state":"verified","verified":true,"steps":[{"verified":true}]}})))
        .unwrap();
    f.h.run_steps(3);
    assert_eq!(f.h.state().jarvis.status, "Verify ผ่าน 1 ขั้นตอน");
    assert!(!f.h.state().jarvis.applying());
}

#[test]
fn session_change_after_confirmation_rejects_queued_write() {
    let mut f = preview();
    f.h.get_by_label("ยืนยัน Apply…").click();
    f.h.run_steps(3);
    f.h.get_by_label("ยืนยัน Apply").click();
    f.h.run_steps(3);
    f.h.state_mut().run("track.rename", json!({"track":"Voice","name":"Other"})).unwrap();
    let before = serde_json::to_value(f.h.state().engine.session()).unwrap();
    let (request, response) = ControlRequest::new("engine.execute", f.command["params"].clone());
    f.control.send(request).unwrap();
    f.h.run_steps(3);
    assert_eq!(response.try_recv().unwrap()["ok"], false);
    assert_eq!(serde_json::to_value(f.h.state().engine.session()).unwrap(), before);
}

#[test]
fn stopped_worker_cannot_dispatch_a_late_queued_command() {
    let mut f = preview();
    f.h.get_by_label("ยืนยัน Apply…").click();
    f.h.run_steps(3);
    f.h.get_by_label("ยืนยัน Apply").click();
    f.h.run_steps(3);
    let before = serde_json::to_value(f.h.state().engine.session()).unwrap();
    f.stop.store(true, Ordering::Release);
    let (request, response) = ControlRequest::new("engine.execute", f.command["params"].clone());
    f.control.send(request).unwrap();
    f.h.run_steps(3);
    assert_eq!(response.try_recv().unwrap()["ok"], false);
    assert_eq!(serde_json::to_value(f.h.state().engine.session()).unwrap(), before);
}

#[test]
fn verified_reply_without_all_planned_writes_is_not_success() {
    let mut f = preview();
    f.h.get_by_label("ยืนยัน Apply…").click();
    f.h.run_steps(3);
    f.h.get_by_label("ยืนยัน Apply").click();
    f.h.run_steps(3);
    let apply = f.requests.try_recv().unwrap();
    f.replies
        .send(Ok(json!({"version":1,"id":apply["id"],"ok":true,"result":{"state":"verified","verified":true,"steps":[{"verified":true}]}})))
        .unwrap();
    f.h.run_steps(3);
    assert!(!f.h.state().jarvis.status.starts_with("Verify ผ่าน"));
}
