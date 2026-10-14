"""Local Thai speech -> human transcript review -> existing preview only.

Apply remains a separate intent_engine CLI operation with typed confirmation.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import intent_engine as ai


class ConsoleLog:
    """Mirror Python output explicitly; PowerShell 5 transcripts omit it."""
    def __init__(self, stream, log):
        self.stream = stream
        self.log = log

    def write(self, text):
        self.log.write(text)
        self.log.flush()
        return self.stream.write(text)

    def flush(self):
        self.stream.flush()
        self.log.flush()


def local_model_directory(model_dir):
    directory = Path(model_dir).resolve(strict=True)
    # faster-whisper falls back to a Hub tokenizer if tokenizer.json is absent.
    for name in ("model.bin", "config.json", "tokenizer.json"):
        if not directory.is_dir() or not (directory / name).is_file():
            raise ValueError(f"Local STT model missing {name}")
    return directory


def transcribe(audio, model_dir):
    directory = local_model_directory(model_dir)
    from faster_whisper import WhisperModel
    model = WhisperModel(str(directory), device="cpu", compute_type="int8",
                         local_files_only=True)
    if "th" not in model.supported_languages:
        raise ValueError("The installed model does not support Thai")
    segments, _ = model.transcribe(audio, language="th", beam_size=5,
                                  vad_filter=True, condition_on_previous_text=False)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    if not text or len(text) > 4000:
        raise ValueError("Empty or oversized transcript; record again")
    return text


def record(seconds, device):
    if not math.isfinite(seconds) or not 1 <= seconds <= 30:
        raise ValueError("Recording duration must be 1..30 seconds")
    import sounddevice as sd
    print(f"Recording microphone for {seconds:g} seconds...")
    try:
        sd.check_input_settings(device=device, channels=1, dtype="float32", samplerate=16000)
        audio = sd.rec(int(seconds * 16000), samplerate=16000, channels=1,
                       dtype="float32", device=device)
        sd.wait()
        if sd.get_status():
            raise RuntimeError("Microphone overflow; recording rejected")
        return audio[:, 0]
    except sd.PortAudioError as error:
        raise RuntimeError(f"Microphone unavailable: {error}") from error
    finally:
        sd.stop()


def reviewed_text(raw, read=input):
    print("ข้อความจาก STT (ยังไม่ส่งเข้า AI):", raw)
    print("ตรวจชื่อแทร็ก ตัวเลข และเครื่องหมายลบให้ตรงกับที่พูด")
    edited = read("พิมพ์ข้อความที่แก้ไข หรือ Enter เพื่อใช้ข้อความเดิม: ").strip()
    if edited.upper() == "CANCEL":
        print("Transcript review cancelled")
        return None
    text = edited or raw
    if not text.strip() or len(text) > 4000:
        raise ValueError("Invalid reviewed transcript")
    print("ข้อความที่จะส่งเข้า Intent Engine:", text)
    if read("พิมพ์ REVIEW เพื่อยืนยันข้อความเท่านั้น (อย่างอื่นยกเลิก): ").strip() != "REVIEW":
        print("Transcript review cancelled")
        return None
    print("Transcript review accepted by typed REVIEW")
    return text


def create_preview(text, port, model):
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid control port")
    snapshot = ai.jarvis.request(port, ai.INSPECT)["result"]
    intent = ai.propose(text, snapshot, model)
    if intent["clarification"].strip():
        raise ValueError(intent["clarification"])
    return ai.preview(intent, snapshot, port)


def save_new(path, value):
    # Never replace existing evidence or a preview.
    with Path(path).open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("devices")
    for mode in ("transcribe", "preview"):
        command = sub.add_parser(mode)
        command.add_argument("--stt-model-dir", type=Path, required=True)
        command.add_argument("--seconds", type=float, default=8)
        command.add_argument("--device", type=int)
        command.add_argument("--out", type=Path, required=True)
        command.add_argument("--log", type=Path, help="New UTF-8 console evidence file")
        if mode == "preview":
            command.add_argument("--port", type=int, default=7801)
            command.add_argument("--model", default="gemma3:4b")
    args = parser.parse_args(argv)
    log = None
    original_stdout, original_stderr = sys.stdout, sys.stderr
    try:
        if args.mode != "devices" and args.log is not None:
            log = args.log.open("x", encoding="utf-8")
            sys.stdout = ConsoleLog(original_stdout, log)
            sys.stderr = ConsoleLog(original_stderr, log)
        if args.mode == "devices":
            import sounddevice as sd
            try:
                print(sd.query_devices())
            except sd.PortAudioError as error:
                raise RuntimeError(f"Cannot enumerate microphones: {error}") from error
            return 0
        if args.out.exists():
            raise ValueError("Output already exists; choose a new path")
        directory = local_model_directory(args.stt_model_dir)
        input("กด Enter เพื่อเริ่มบันทึกเสียงจากไมโครโฟน: ")
        raw = transcribe(record(args.seconds, args.device), directory)
        text = reviewed_text(raw)
        if text is None:
            print("Cancelled; no DAW connection or proposal")
            return 0
        if args.mode == "transcribe":
            save_new(args.out, {"raw_transcript": raw, "reviewed_transcript": text,
                                "language": "th", "stt_model_dir": str(directory)})
            print("Transcript saved; no DAW connection")
        else:
            artifact = create_preview(text, args.port, args.model)
            ai.display_preview(artifact)
            save_new(args.out, artifact)
            print("Preview saved. No writes sent. Apply separately using intent_engine.py apply.")
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, ImportError, EOFError) as error:
        print(f"Voice error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled")
        return 1
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr
        if log is not None:
            log.close()


if __name__ == "__main__":
    sys.exit(main())
