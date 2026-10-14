//! Native-owned Python Sidecar worker; all process and socket work is off the UI thread.
use serde_json::{Value, json};
use soundcraft_ui_egui::jarvis::Connection;
use std::io::{BufRead, BufReader, Read, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{Receiver, RecvTimeoutError, Sender, channel, sync_channel};
use std::sync::{Arc, Mutex, OnceLock, Weak};
use std::time::{Duration, Instant};

const MAX_REPLY: u64 = 2_000_000;

type OwnedWorker = (Weak<AtomicBool>, Receiver<()>);
static WORKERS: OnceLock<Mutex<Vec<OwnedWorker>>> = OnceLock::new();

/// Only called when the desktop event loop exits, never during active UI/audio work.
pub fn shutdown_all() {
    let Some(registry) = WORKERS.get() else { return };
    let Ok(mut registry) = registry.lock() else { return };
    let workers = std::mem::take(&mut *registry);
    drop(registry);
    for (stop, _) in &workers {
        if let Some(stop) = stop.upgrade() {
            stop.store(true, Ordering::Release);
        }
    }
    let deadline = Instant::now() + Duration::from_secs(3);
    for (_, finished) in workers {
        let _ = finished.recv_timeout(deadline.saturating_duration_since(Instant::now()));
    }
}

pub fn start(ctx: &egui::Context) -> Result<Connection, String> {
    let (requests, rx) = sync_channel(1);
    let (replies_tx, replies) = channel();
    let (control_tx, control) = channel();
    let stop = Arc::new(AtomicBool::new(false));
    let worker_stop = stop.clone();
    let ctx = ctx.clone();
    let (finished_tx, finished) = channel();
    let mut registry = WORKERS.get_or_init(|| Mutex::new(Vec::new())).lock().map_err(|error| error.to_string())?;
    registry.retain(|(_, finished)| matches!(finished.try_recv(), Err(std::sync::mpsc::TryRecvError::Empty)));
    if registry.len() >= 8 {
        return Err("Previous JARVIS workers are still stopping; retry shortly".into());
    }
    std::thread::Builder::new()
        .name("jarvis-sidecar".into())
        .spawn(move || {
            if let Err(error) = worker(&ctx, &rx, &replies_tx, control_tx, &worker_stop) {
                let _ = replies_tx.send(Err(error));
                ctx.request_repaint();
            }
            worker_stop.store(true, Ordering::Release);
            let _ = finished_tx.send(());
        })
        .map_err(|error| error.to_string())?;
    registry.push((Arc::downgrade(&stop), finished));
    Ok(Connection { requests, replies, control, stop })
}

fn script_path() -> Result<PathBuf, String> {
    let path = std::env::var_os("SOUNDCRAFT_JARVIS_BRIDGE")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../tkn-jarvis/jarvis_bridge.py"));
    if !path.is_file() {
        return Err("JARVIS Python bridge not found; set SOUNDCRAFT_JARVIS_BRIDGE".into());
    }
    path.canonicalize().map_err(|error| error.to_string())
}

fn spawn(port: u16) -> Result<Child, String> {
    let script = script_path()?;
    let mut command = Command::new(python_path()?);
    command.args(["-u", "-B"]).arg(script).args(["--port", &port.to_string()]);
    command.env("PYTHONIOENCODING", "utf-8").stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW: no console window or focus stealing.
    }
    command.spawn().map_err(|error| format!("Python runtime unavailable: {error}; set SOUNDCRAFT_JARVIS_PYTHON"))
}

fn python_path() -> Result<std::ffi::OsString, String> {
    if let Some(configured) = std::env::var_os("SOUNDCRAFT_JARVIS_PYTHON") {
        return Ok(configured);
    }
    if !cfg!(windows) {
        return Ok("python3".into());
    }
    // Resolve the launcher first, then own the actual interpreter process for cleanup.
    let mut probe = Command::new("py");
    probe.args(["-3", "-c", "import sys; print(sys.executable)"]);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        probe.creation_flags(0x08000000);
    }
    let result = probe.output().map_err(|error| format!("Python runtime unavailable: {error}; set SOUNDCRAFT_JARVIS_PYTHON"))?;
    let path = String::from_utf8(result.stdout).map_err(|error| error.to_string())?;
    if !result.status.success() || !std::path::Path::new(path.trim()).is_file() {
        return Err("Python runtime unavailable; set SOUNDCRAFT_JARVIS_PYTHON to python.exe".into());
    }
    Ok(path.trim().into())
}

fn read_reply(receiver: &Receiver<Result<Value, String>>, child: &mut Child, stop: &AtomicBool, timeout: Duration) -> Result<Value, String> {
    let deadline = Instant::now() + timeout;
    loop {
        if stop.load(Ordering::Acquire) {
            return Err("JARVIS operation cancelled".into());
        }
        match receiver.recv_timeout(Duration::from_millis(100)) {
            Ok(reply) => return reply,
            Err(RecvTimeoutError::Disconnected) => return Err("Python Sidecar ended before reporting a result".into()),
            Err(RecvTimeoutError::Timeout) => {}
        }
        if Instant::now() >= deadline {
            return Err("JARVIS Sidecar timeout; result not established".into());
        }
        if child.try_wait().map_err(|error| error.to_string())?.is_some() {
            return Err("Python Sidecar exited; check runtime and bridge path".into());
        }
    }
}

fn worker(
    ctx: &egui::Context,
    requests: &Receiver<Value>,
    replies: &Sender<Result<Value, String>>,
    control: Sender<soundcraft_ui_egui::ControlRequest>,
    stop: &Arc<AtomicBool>,
) -> Result<(), String> {
    let port = crate::control_server::start_jarvis(ctx.clone(), control, stop.clone())?;
    let mut child = match spawn(port) {
        Ok(child) => child,
        Err(error) => {
            stop.store(true, Ordering::Release);
            return Err(error);
        }
    };
    // All exit paths run this owned-child cleanup, never targeting another process.
    let result = run(ctx, requests, replies, stop, &mut child);
    stop.store(true, Ordering::Release);
    let _ = child.kill();
    let _ = child.wait();
    result
}

fn run(
    ctx: &egui::Context,
    requests: &Receiver<Value>,
    replies: &Sender<Result<Value, String>>,
    stop: &AtomicBool,
    child: &mut Child,
) -> Result<(), String> {
    let mut input = child.stdin.take().ok_or("Missing Python stdin pipe")?;
    let output = child.stdout.take().ok_or("Missing Python stdout pipe")?;
    let (reader_tx, reader_rx) = sync_channel(2);
    std::thread::Builder::new()
        .name("jarvis-jsonl-reader".into())
        .spawn(move || {
            let mut reader = BufReader::new(output);
            loop {
                let mut line = Vec::new();
                let reply = match Read::by_ref(&mut reader).take(MAX_REPLY + 1).read_until(b'\n', &mut line) {
                    Ok(0) => break,
                    Ok(_) if line.len() as u64 <= MAX_REPLY && line.last() == Some(&b'\n') => {
                        serde_json::from_slice::<Value>(&line).map_err(|error| format!("Invalid Sidecar JSON: {error}"))
                    }
                    Ok(_) => Err("Oversized or incomplete Sidecar reply".into()),
                    Err(error) => Err(error.to_string()),
                };
                let failed = reply.is_err();
                if reader_tx.send(reply).is_err() || failed {
                    break;
                }
            }
        })
        .map_err(|error| error.to_string())?;
    let ready = read_reply(&reader_rx, child, stop, Duration::from_secs(20))?;
    if ready.get("version").and_then(Value::as_u64) != Some(1)
        || ready.get("id") != Some(&Value::Null)
        || ready.pointer("/result/state").and_then(Value::as_str) != Some("ready")
    {
        return Err("Unsupported Python bridge handshake".into());
    }
    replies.send(Ok(ready)).map_err(|error| error.to_string())?;
    ctx.request_repaint();
    loop {
        if stop.load(Ordering::Acquire) {
            let shutdown = json!({"version":1,"id":2147483647,"method":"shutdown"});
            let _ = writeln!(input, "{shutdown}");
            let _ = input.flush();
            return Ok(());
        }
        let request = match requests.recv_timeout(Duration::from_millis(100)) {
            Ok(request) => request,
            Err(RecvTimeoutError::Timeout) => continue,
            Err(_) => return Ok(()),
        };
        let encoded = serde_json::to_vec(&request).map_err(|error| error.to_string())?;
        if encoded.len() >= 32768 {
            return Err("Bridge request exceeds byte limit".into());
        }
        input.write_all(&encoded).and_then(|()| input.write_all(b"\n")).and_then(|()| input.flush()).map_err(|error| error.to_string())?;
        let reply = read_reply(&reader_rx, child, stop, Duration::from_secs(600))?;
        if reply.get("version").and_then(Value::as_u64) != Some(1) || reply.get("id") != request.get("id") {
            return Err("Sidecar correlation/version mismatch".into());
        }
        replies.send(Ok(reply)).map_err(|error| error.to_string())?;
        ctx.request_repaint();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn developer_bridge_resolves_without_loading_any_session() {
        assert!(script_path().is_ok());
    }
}
