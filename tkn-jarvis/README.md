# TKN JARVIS V0 — SoundCraft adapter

This additive prototype lives outside the existing Rust workspace. It does not modify any SoundCraft core files or TKN DAW V1.

## Verified upstream integration surface

- SoundCraft's desktop control server listens on 127.0.0.1 with newline-delimited JSON.
- `engine.execute` accepts `{"command":"mix.volume","params":{"track":"Kick","db":-6}}`.
- `session.inspect` provides a read-only session snapshot.
- SoundCraft also ships `soundcraft-cli mcp` and `crates/automation`. For a full agent, reuse these rather than creating another MCP server.

See upstream `docs/control-protocol.md` and `docs/mcp.md`.

## Local Windows trial

Start SoundCraft with its control endpoint enabled:

```powershell
soundcraft.exe --demo --control 7801
```

In a second PowerShell window:

```powershell
py tkn-jarvis/jarvis.py "ตรวจสอบเซสชัน"
py tkn-jarvis/jarvis.py "ตั้งเสียง Kick ติดลบ 6 dB"
```

Those are **dry runs** and do not touch SoundCraft. After reviewing the request:

```powershell
py tkn-jarvis/jarvis.py "ตรวจสอบเซสชัน" --apply
py tkn-jarvis/jarvis.py "ตั้งเสียง Kick ติดลบ 6 dB" --apply
```

Only localhost TCP is used. No voice input, external LLM, file deletion, export, plugin insertion, or track removal is implemented yet.

## Safety rules

- Modification requires explicit `--apply`; preview is the default.
- Only two allowlisted operations exist: read session summary and set a track's **absolute** fader volume.
- Do not interpret "ลดเสียง" as an absolute setting. Relative changes are rejected until the existing fader value can be safely read.
- After applying a write, request `session.inspect`. This is observational verification, not a transactional guarantee or an automatic undo.
- Existing undo remains owned by SoundCraft. Never silently merge into `main`.

## Next milestone

1. Run actual Windows CLI smoke tests against a disposable demo session.
2. Discover actual command metadata with `soundcraft-cli commands` and reconcile parameter schemas.
3. Add deterministic inspect-before/after assertions for volume commands and failing-case tests.
4. Add structured multi-command preview and one-by-one confirmation; then optional speech-to-text and AI intent extraction.
5. Integrate with TKN DAW V1 project metadata through explicit import/export rather than altering legacy project files.

**Status:** source committed, not yet compiled or tested with a running Windows SoundCraft instance.
