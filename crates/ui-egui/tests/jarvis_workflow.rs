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
    preview_with_engine(soundcraft_engine::Engine::default())
}

fn preview_with_engine(engine: soundcraft_engine::Engine) -> Fixture {
    let (requests_tx, requests) = sync_channel(1);
    let (replies, replies_rx) = channel();
    let (control, control_rx) = channel();
    let stop = Arc::new(AtomicBool::new(false));
    let connection = Arc::new(Mutex::new(Some(Connection { requests: requests_tx, replies: replies_rx, control: control_rx, stop: stop.clone() })));
    let mut app = SoundApp::new(
        engine,
        None,
        Services {
            jarvis_start: Some(Box::new(move |_| connection.lock().unwrap().take().ok_or("Test connection consumed".into()))),
            ..Services::default()
        },
    );
    app.run("track.new", json!({"name":"Voice"})).unwrap();
    let id = app.engine.session().track_by_name("Voice").unwrap().id.0;
    if let Some(kick) = app.engine.session().track_by_name("Kick").map(|track| track.id.0) {
        app.run("edit.select", json!({"tracks":[kick],"start":443072,"end":443072,"exact":true})).unwrap();
    }
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

#[test]
fn closing_panel_during_apply_does_not_route_tab_to_edit() {
    let mut engine = soundcraft_engine::demo::demo_engine();
    engine.execute("transport.locate", &json!({"at":443072})).unwrap();
    let mut f = preview_with_engine(engine);
    f.h.get_by_label("ยืนยัน Apply…").click();
    f.h.run_steps(3);
    f.h.get_by_label("ยืนยัน Apply").click();
    f.h.run_steps(3);
    let apply = f.requests.try_recv().unwrap();
    let (write, response) = ControlRequest::new("engine.execute", f.command["params"].clone());
    f.control.send(write).unwrap();
    f.h.run_steps(3);
    assert_eq!(response.try_recv().unwrap()["ok"], true);
    f.h.state_mut().run("ui.dock", json!({"operation":"close","panel":"jarvis"})).unwrap();
    f.h.run_steps(3);
    assert!(f.h.state().jarvis.applying());
    assert!(!f.stop.load(Ordering::Acquire));
    // A native pointer/menu close can leave no text/button keyboard owner.
    // Accessibility clicks in this harness otherwise retain the old button focus.
    f.h.ctx.memory_mut(|memory| {
        if let Some(id) = memory.focused() {
            memory.surrender_focus(id);
        }
    });
    for _ in 0..3 {
        for pressed in [true, false] {
            f.h.event(egui::Event::Key { key: egui::Key::Tab, physical_key: None, pressed, repeat: false, modifiers: egui::Modifiers::NONE });
        }
        f.h.run_steps(3);
    }
    assert_eq!(f.h.state().position(), 443072, "Panel interaction leaked into the Edit shortcut");
    let (inspect, inspected) = ControlRequest::new("session.inspect", json!({"detail":"full"}));
    f.control.send(inspect).unwrap();
    f.h.run_steps(3);
    assert_eq!(inspected.try_recv().unwrap()["ok"], true);
    f.replies
        .send(Ok(json!({"version":1,"id":apply["id"],"ok":true,"result":{"state":"verified","verified":true,"steps":[{"verified":true}]}})))
        .unwrap();
    f.h.run_steps(3);
    assert_eq!(f.h.state().jarvis.status, "Verify ผ่าน 1 ขั้นตอน");
    assert!(f.stop.load(Ordering::Acquire));
    f.h.ctx.memory_mut(|memory| {
        if let Some(id) = memory.focused() {
            memory.surrender_focus(id);
        }
    });
    f.h.key_press(egui::Key::Tab);
    f.h.run_steps(3);
    assert_eq!(f.h.state().position(), 443077, "Normal Edit navigation must resume after Verify");
}

#[test]
fn confirmation_navigation_cannot_change_the_reviewed_session() {
    let mut f = preview_with_engine(soundcraft_engine::demo::demo_engine());
    let before = serde_json::to_value(f.h.state().engine.session()).unwrap();
    f.h.get_by_label("ยืนยัน Apply…").click();
    f.h.run_steps(3);
    f.h.ctx.memory_mut(|memory| {
        if let Some(id) = memory.focused() {
            memory.surrender_focus(id);
        }
    });
    f.h.key_press(egui::Key::Tab);
    f.h.run_steps(3);
    assert_eq!(serde_json::to_value(f.h.state().engine.session()).unwrap(), before);
    assert!(f.requests.try_recv().is_err());
    f.h.get_by_label("ไม่ — Cancel").click();
    f.h.run_steps(3);
    assert!(f.requests.try_recv().is_err());
    assert!(f.h.state().jarvis.preview.is_none());
}

#[test]
fn hidden_applying_panel_still_rejects_an_external_session_change() {
    let mut f = preview_with_engine(soundcraft_engine::demo::demo_engine());
    f.h.get_by_label("ยืนยัน Apply…").click();
    f.h.run_steps(3);
    f.h.get_by_label("ยืนยัน Apply").click();
    f.h.run_steps(3);
    let apply = f.requests.try_recv().unwrap();
    let (write, written) = ControlRequest::new("engine.execute", f.command["params"].clone());
    f.control.send(write).unwrap();
    f.h.run_steps(3);
    assert_eq!(written.try_recv().unwrap()["ok"], true);
    f.h.state_mut().run("ui.dock", json!({"operation":"close","panel":"jarvis"})).unwrap();
    f.h.state_mut().run("transport.locate", json!({"at":443077})).unwrap();
    let changed = serde_json::to_value(f.h.state().engine.session()).unwrap();
    let (inspect, inspected) = ControlRequest::new("session.inspect", json!({"detail":"full"}));
    f.control.send(inspect).unwrap();
    f.h.run_steps(3);
    assert_eq!(inspected.try_recv().unwrap()["ok"], false);
    assert_eq!(serde_json::to_value(f.h.state().engine.session()).unwrap(), changed);
    f.replies
        .send(Ok(json!({"version":1,"id":apply["id"],"ok":false,"error":{"message":"Session changed during Verify","may_have_written":true}})))
        .unwrap();
    f.h.run_steps(3);
    assert!(!f.h.state().jarvis.status.starts_with("Verify ผ่าน"));
    assert!(f.h.state().jarvis.status.contains("rollback"));
    assert!(f.stop.load(Ordering::Acquire));
}

#[test]
fn a_position_change_before_confirmation_expires_preview() {
    let mut f = preview_with_engine(soundcraft_engine::demo::demo_engine());
    f.h.state_mut().run("transport.locate", json!({"at":443077})).unwrap();
    f.h.run_steps(3);
    assert!(f.h.state().jarvis.preview.is_none());
    assert!(f.requests.try_recv().is_err());
    assert!(f.stop.load(Ordering::Acquire));
}

#[test]
fn closed_docked_or_floating_panel_finishes_in_edit_and_mix() {
    for mix in [false, true] {
        for floating in [false, true] {
            let mut f = preview();
            if mix {
                f.h.state_mut().run("window.toggle_mix_edit", json!({})).unwrap();
            }
            if floating {
                f.h.state_mut().run("ui.dock", json!({"operation":"float","panel":"jarvis","rect":[900,150,420,600]})).unwrap();
            }
            f.h.run_steps(3);
            f.h.get_by_label("ยืนยัน Apply…").click();
            f.h.run_steps(3);
            f.h.get_by_label("ยืนยัน Apply").click();
            f.h.run_steps(3);
            let apply = f.requests.try_recv().unwrap();
            f.h.state_mut().run("ui.dock", json!({"operation":"close","panel":"jarvis"})).unwrap();
            let (write, written) = ControlRequest::new("engine.execute", f.command["params"].clone());
            f.control.send(write).unwrap();
            f.h.run_steps(3);
            assert_eq!(written.try_recv().unwrap()["ok"], true, "mix={mix}, floating={floating}");
            assert!(!f.stop.load(Ordering::Acquire));
            f.replies
                .send(Ok(json!({"version":1,"id":apply["id"],"ok":true,"result":{"state":"verified","verified":true,"steps":[{"verified":true}]}})))
                .unwrap();
            f.h.run_steps(3);
            assert_eq!(f.h.state().jarvis.status, "Verify ผ่าน 1 ขั้นตอน");
            assert!(f.stop.load(Ordering::Acquire));
        }
    }
}
