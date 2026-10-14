//! Loopback JSON-lines control server: one request per line, one reply per line.
//! This is the transport the MCP server (`soundcraft-cli mcp --connect PORT`) wraps.

use serde_json::{Value, json};
use soundcraft_ui_egui::ControlRequest;
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::time::Duration;

pub fn start(port: u16, ctx: egui::Context) -> Receiver<ControlRequest> {
    let (tx, rx) = channel::<ControlRequest>();
    let listener = match TcpListener::bind(("127.0.0.1", port)) {
        Ok(l) => l,
        Err(e) => {
            log::error!("control server failed to bind 127.0.0.1:{port}: {e}");
            return rx;
        }
    };
    let actual = listener.local_addr().map(|a| a.port()).unwrap_or(port);
    log::info!("control server listening on 127.0.0.1:{actual}");
    println!("SOUNDCRAFT_CONTROL_PORT={actual}");
    let spawned = std::thread::Builder::new().name("soundcraft-control".into()).spawn(move || {
        for stream in listener.incoming().flatten() {
            let tx = tx.clone();
            let ctx = ctx.clone();
            let _ = std::thread::Builder::new().name("soundcraft-control-conn".into()).spawn(move || serve(stream, tx, ctx));
        }
    });
    if let Err(e) = spawned {
        log::error!("control thread failed: {e}");
    }
    rx
}

fn serve(stream: TcpStream, tx: Sender<ControlRequest>, ctx: egui::Context) {
    let Ok(read) = stream.try_clone() else { return };
    let mut out = stream;
    for line in BufReader::new(read).lines() {
        let Ok(line) = line else { break };
        if line.trim().is_empty() {
            continue;
        }
        let reply = match serde_json::from_str::<Value>(&line) {
            Ok(msg) => {
                let id = msg.get("id").cloned().unwrap_or(Value::Null);
                let method = msg.get("method").and_then(Value::as_str).unwrap_or("").to_string();
                let params = msg.get("params").cloned().unwrap_or(json!({}));
                let (req, rrx) = ControlRequest::new(method, params);
                if tx.send(req).is_err() {
                    break;
                }
                ctx.request_repaint();
                let mut r = rrx.recv_timeout(Duration::from_secs(90)).unwrap_or_else(|_| json!({"ok": false, "error": "timeout"}));
                if let Some(o) = r.as_object_mut() {
                    o.insert("id".into(), id);
                }
                r
            }
            Err(e) => json!({"ok": false, "error": format!("bad JSON: {e}")}),
        };
        if writeln!(out, "{reply}").is_err() {
            break;
        }
    }
}
/// Owned, temporary loopback endpoint for the JARVIS Sidecar only.
pub fn start_jarvis(ctx: egui::Context, tx: Sender<ControlRequest>, stop: std::sync::Arc<std::sync::atomic::AtomicBool>) -> Result<u16, String> {
    let listener = TcpListener::bind(("127.0.0.1", 0)).map_err(|error| error.to_string())?;
    listener.set_nonblocking(true).map_err(|error| error.to_string())?;
    let port = listener.local_addr().map_err(|error| error.to_string())?.port();
    std::thread::Builder::new()
        .name("jarvis-endpoint".into())
        .spawn(move || {
            use std::sync::atomic::Ordering;
            while !stop.load(Ordering::Acquire) {
                match listener.accept() {
                    Ok((stream, _)) => serve_jarvis(stream, &tx, &ctx, &stop),
                    Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => std::thread::sleep(Duration::from_millis(15)),
                    Err(error) => {
                        log::warn!("JARVIS endpoint stopped: {error}");
                        break;
                    }
                }
            }
        })
        .map_err(|error| error.to_string())?;
    Ok(port)
}

fn serve_jarvis(stream: TcpStream, tx: &Sender<ControlRequest>, ctx: &egui::Context, stop: &std::sync::atomic::AtomicBool) {
    use std::io::Read as _;
    use std::sync::atomic::Ordering;
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
    let Ok(read) = stream.try_clone() else {
        return;
    };
    let mut line = String::new();
    if BufReader::new(read).take(32769).read_line(&mut line).is_err() || line.len() > 32768 || !line.ends_with('\n') {
        return;
    }
    let Ok(msg) = serde_json::from_str::<Value>(&line) else {
        return;
    };
    let id = msg.get("id").cloned().unwrap_or(Value::Null);
    let method = msg.get("method").and_then(Value::as_str).unwrap_or("");
    let params = msg.get("params").cloned().unwrap_or(json!({}));
    let allowed = method == "session.inspect"
        || method == "engine.execute"
            && matches!(
                params.get("command").and_then(Value::as_str),
                Some("mix.volume" | "mix.mute" | "track.rename" | "mix.insert" | "mix.insert_param")
            );
    let mut reply = if !allowed || stop.load(Ordering::Acquire) {
        json!({"ok":false,"error":"JARVIS endpoint rejects this method/command"})
    } else {
        let (request, response) = ControlRequest::new(method, params);
        if tx.send(request).is_err() {
            return;
        }
        ctx.request_repaint();
        let deadline = std::time::Instant::now() + Duration::from_secs(90);
        loop {
            if stop.load(Ordering::Acquire) || std::time::Instant::now() >= deadline {
                break json!({"ok":false,"error":"JARVIS request stopped or timed out"});
            }
            match response.recv_timeout(Duration::from_millis(100)) {
                Ok(reply) => break reply,
                Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {}
                Err(_) => break json!({"ok":false,"error":"JARVIS document owner disconnected"}),
            }
        }
    };
    if let Some(fields) = reply.as_object_mut() {
        fields.insert("id".into(), id);
    }
    let mut out = stream;
    let _ = writeln!(out, "{reply}");
}

#[cfg(test)]
mod jarvis_endpoint_tests {
    use super::*;
    use std::sync::Arc;
    use std::sync::atomic::{AtomicBool, Ordering};

    #[test]
    fn private_endpoint_rejects_unbounded_commands_and_closes_on_stop() {
        let (tx, rx) = channel();
        let stop = Arc::new(AtomicBool::new(false));
        let port = start_jarvis(egui::Context::default(), tx, stop.clone()).unwrap();
        let mut stream = TcpStream::connect(("127.0.0.1", port)).unwrap();
        stream.set_read_timeout(Some(Duration::from_secs(3))).unwrap();
        writeln!(stream, "{}", json!({"id":1,"method":"engine.execute","params":{"command":"track.delete","params":{}}})).unwrap();
        let mut response = String::new();
        BufReader::new(stream).read_line(&mut response).unwrap();
        assert_eq!(serde_json::from_str::<Value>(&response).unwrap()["ok"], false);
        assert!(rx.try_recv().is_err());
        stop.store(true, Ordering::Release);
        let deadline = std::time::Instant::now() + Duration::from_secs(3);
        while TcpStream::connect(("127.0.0.1", port)).is_ok() && std::time::Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(30));
        }
        assert!(TcpStream::connect(("127.0.0.1", port)).is_err());
    }
}
