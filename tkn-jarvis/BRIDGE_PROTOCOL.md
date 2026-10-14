# Step 7.2.1 — Local Bridge Protocol v1

The native host starts an installed Python interpreter with jarvis_bridge.py
and its own loopback control port. Communication is UTF-8 JSONL over private
stdin/stdout pipes. No bridge HTTP server, audio input or direct engine-command
method. One operation at a time; model work belongs to the Sidecar, not the UI
or audio callback. Stdout is JSON only; each reply is flushed.

Requests have exactly version=1, id (positive integer <=2147483647), method, and
the fields below. Request lines are limited to 32768 bytes. Duplicate keys,
unknown methods/fields, nonfinite JSON and malformed UTF-8 are rejected. Oversized
or incomplete framing closes the stream. EOF discards the pending Preview.

| Method | Extra fields | Result |
|---|---|---|
| status | none | idle/preview, without DAW/model calls |
| preview | context, instruction | clarification or preview with changes, stable IDs, preview_id and confirmation |
| cancel | context | discard pending plan, no DAW calls |
| apply | context, instruction, preview_id, confirmation, confirmed=true | verified steps or structured error |
| shutdown | none | discard plan and exit |

context is an opaque host-generated session/input generation token (1–128 chars).
The Rust host changes it on text edits or document replacement/mutation and
invalidates displayed plans. The Bridge compares context/text/token before
Apply, then the existing apply_preview independently checks the live baseline
and verifies every write. Exactly one immutable plan is retained in memory;
new Preview, Cancel, malformed request or any Apply attempt consumes it.

Ready event: {version:1,id:null,ok:true,result:{state:"ready"}}.
Replies retain request id and contain ok plus result or error. Preview responses
exclude the full baseline but show exact changes, resolved faders and concrete
compiled commands. The native host binds each allowed write to that ordered
command list as well as its current document identity. The full
baseline stays in Sidecar memory. Errors include message, may_have_written and
new_preview_required. An attempted write is conservatively reported as possibly
written, even if Verify later fails; there is no automatic rollback.

The parent must require a real user confirmation before sending Apply. A token
or confirmed flag is not authentication against a caller controlling the local
pipes/code. Model output cannot invoke Bridge methods. Shutdown during planning
may terminate the owned process; close during Apply must wait for a final result
to avoid losing the Verify outcome. Host lifecycle integration is Step 7.2.3.

Python regression suite: 133/133 passed at this step, including 11 Bridge tests
and a real process ready/status/shutdown smoke. No Rust/UI integration claimed by
this protocol milestone.

## Step 7.2.3 native ownership

`apps/soundcraft/src/jarvis_host.rs` starts the interpreter in a background
worker. The UI uses a bounded request channel, polls responses, and repaints
without blocking on model/process/socket work. Runtime paths are configurable;
Windows resolves `py -3` to the actual interpreter before owning its process.
The parent kills/waits only for its own child on worker exit. Normal desktop
exit signals all owned workers and allows a bounded cleanup interval after
stopping its player.

`control_server::start_jarvis` binds `127.0.0.1:0` with a shared stop flag. It
allows inspection and the five command IDs compiled by the original Intent
Engine. `control::drain_jarvis` runs on the UI thread: planning allows inspection
only, applying allows the exact next reviewed command only, and both require
the same `Arc<Session>` identity. Every own write advances that identity and
consumes one command. An unrelated mutation/replacement or stopped worker
rejects queued writes, even if a baseline check had already passed. The general
opt-in `--control` endpoint is separate and unchanged.

Closing during planning stops the owned worker. Closing during Apply keeps it
until the result arrives, and desktop close is deferred during that operation.
Runtime/model/timeout/protocol errors discard plans and never trigger retries
of writes. Complete confirmed plans still use the original Python per-step
inspection and Verify implementation.
