"""Tableau de bord web local du Transcripteur.

Lance un petit serveur Flask sur http://localhost:8765 qui pilote app.py :
démarrage/arrêt d'enregistrement, suivi en direct, quota Gemini, notes récentes.

Utilisation : ./transcripteur-web  (ou venv/bin/python web_app.py)
"""

import json
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from urllib.parse import quote

from app import (
    CAPTURE_DIR,
    CONFIG_FILE,
    JSON_DIR,
    MARKDOWN_DIR,
    load_config,
    load_gemini_stats,
)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
PYTHON = sys.executable

HOST = "127.0.0.1"
PORT = 8765

app = Flask(__name__, static_folder=None)

_lock = threading.Lock()
_job = {
    "process": None,
    "phase": "idle",        # idle | recording | processing | done | error
    "started_at": None,
    "stopped_at": None,
    "log": deque(maxlen=60),
    "silence_warning": False,
    "note": None,           # chemin de la note finale
    "title": None,          # titre Gemini éventuel
}


def _reader_thread(process: subprocess.Popen) -> None:
    for raw_line in process.stdout:
        line = raw_line.rstrip("\n")
        # Les mises à jour du timer utilisent \r sur une même ligne
        line = line.split("\r")[-1]
        if not line.strip():
            continue

        with _lock:
            _job["log"].append(line)

            if "[OK] Audio généré" in line:
                _job["phase"] = "processing"
                _job["stopped_at"] = time.time()
            elif "[WARN] Aucun son détecté" in line:
                _job["silence_warning"] = True
            elif "Titre proposé par Gemini :" in line:
                _job["title"] = line.split(":", 1)[1].strip()
            elif "[OK] Export Obsidian :" in line:
                _job["note"] = line.split(":", 1)[1].strip()
            elif "[OK] Markdown enrichi :" in line and not _job["note"]:
                _job["note"] = line.split(":", 1)[1].strip()

    process.wait()
    with _lock:
        if _job["stopped_at"] is None:
            _job["stopped_at"] = time.time()
        _job["phase"] = "done" if process.returncode == 0 else "error"
        _job["process"] = None


def _obsidian_url(note_name: str, config: dict) -> str | None:
    obsidian_dir = config.get("obsidian_dir")
    if not obsidian_dir:
        return None

    vault = Path(obsidian_dir).expanduser()
    subdir = config.get("obsidian_subdir") or ""
    note_file = vault / subdir / f"{note_name}.md"
    if not note_file.exists():
        return None

    file_param = f"{subdir}/{note_name}" if subdir else note_name
    return f"obsidian://open?vault={quote(vault.name)}&file={quote(file_param)}"


def _recent_notes(config: dict, limit: int = 8) -> list[dict]:
    notes = []
    for md_file in sorted(
        MARKDOWN_DIR.glob("*.md"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )[:limit]:
        duration = None
        json_file = JSON_DIR / f"{md_file.stem}.json"
        if json_file.exists():
            try:
                segments = json.loads(json_file.read_text()).get("segments", [])
                if segments:
                    duration = round(segments[-1]["end"])
            except (json.JSONDecodeError, OSError, KeyError):
                pass

        notes.append({
            "name": md_file.stem,
            "modified": md_file.stat().st_mtime,
            "duration_seconds": duration,
            "obsidian_url": _obsidian_url(md_file.stem, config),
        })
    return notes


def _captures(limit: int = 8) -> list[dict]:
    captures = []
    for wav_file in sorted(
        CAPTURE_DIR.glob("*.wav"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )[:limit]:
        size = wav_file.stat().st_size
        captures.append({
            "name": wav_file.stem,
            "modified": wav_file.stat().st_mtime,
            # WAV PCM 16 bits mono 16 kHz → 32 000 octets/seconde
            "duration_seconds": max((size - 44) // 32000, 0),
            "transcribed": (JSON_DIR / f"{wav_file.stem}.json").exists(),
        })
    return captures


def _quota() -> dict:
    stats = load_gemini_stats()

    used = stats.get("total_tokens", 0)
    limit = stats.get("monthly_limit_tokens", 2_000_000)
    return {
        "tokens_used": used,
        "tokens_limit": limit,
        "tokens_remaining": max(limit - used, 0),
        "percent_used": round(used / limit * 100, 1) if limit else 0,
        "cost_estimate": round(stats.get("total_cost", 0.0), 4),
        "transcriptions": stats.get("transcriptions", 0),
        "month": stats.get("month"),
    }


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/status")
def status():
    config = load_config()
    with _lock:
        elapsed = None
        if _job["started_at"]:
            end = _job["stopped_at"] or time.time()
            elapsed = int(end - _job["started_at"])

        payload = {
            "phase": _job["phase"],
            "elapsed_seconds": elapsed,
            "recording_seconds": (
                int((_job["stopped_at"] or time.time()) - _job["started_at"])
                if _job["started_at"] else None
            ),
            "silence_warning": _job["silence_warning"],
            "title": _job["title"],
            "note": _job["note"],
            "log": list(_job["log"])[-15:],
        }

    payload["quota"] = _quota()
    payload["notes"] = _recent_notes(config)
    payload["captures"] = _captures()
    payload["config"] = {
        "model": config.get("default_model", "small"),
        "language": config.get("default_language", "fr"),
        "device": config.get("default_device", "auto"),
        "enrichment": bool(config.get("enable_gemini_enrichment", False)),
        "obsidian_dir": config.get("obsidian_dir"),
    }
    return jsonify(payload)


def _spawn_job(command: list[str], phase: str):
    """Lance app.py en sous-processus si aucun travail n'est en cours."""
    with _lock:
        if _job["process"] is not None:
            return None

        process = subprocess.Popen(
            command,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        _job.update({
            "process": process,
            "phase": phase,
            "started_at": time.time(),
            "stopped_at": None if phase == "recording" else time.time(),
            "silence_warning": False,
            "note": None,
            "title": None,
        })
        _job["log"].clear()

    threading.Thread(target=_reader_thread, args=(process,), daemon=True).start()
    return process


@app.post("/api/record/start")
def record_start():
    data = request.get_json(silent=True) or {}

    command = [PYTHON, str(BASE_DIR / "app.py"), "run"]
    if data.get("name"):
        command += ["--name", data["name"]]
    if data.get("title"):
        command += ["--title", data["title"]]
    if data.get("domain"):
        command += ["--domain", data["domain"]]
    if data.get("delete_audio"):
        command += ["--delete-audio"]

    if _spawn_job(command, "recording") is None:
        return jsonify({"error": "Un travail est déjà en cours"}), 409
    return jsonify({"ok": True})


@app.post("/api/reenrich")
def reenrich():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")

    if not (JSON_DIR / f"{name}.json").exists() or "/" in name:
        return jsonify({"error": f"Note inconnue : {name}"}), 404

    command = [PYTHON, str(BASE_DIR / "app.py"), "reenrich", "--name", name]
    if _spawn_job(command, "processing") is None:
        return jsonify({"error": "Un travail est déjà en cours"}), 409
    return jsonify({"ok": True})


@app.post("/api/transcribe")
def transcribe():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")

    wav_file = CAPTURE_DIR / f"{name}.wav"
    if not wav_file.exists() or "/" in name:
        return jsonify({"error": f"Capture inconnue : {name}"}), 404

    command = [PYTHON, str(BASE_DIR / "app.py"), "transcribe", "--file", str(wav_file)]
    if _spawn_job(command, "processing") is None:
        return jsonify({"error": "Un travail est déjà en cours"}), 409
    return jsonify({"ok": True})


@app.post("/api/record/stop")
def record_stop():
    with _lock:
        process = _job["process"]
        if process is None or _job["phase"] != "recording":
            return jsonify({"error": "Aucun enregistrement en cours"}), 409
        # SIGINT = équivalent CTRL+C : arrêt propre puis transcription
        process.send_signal(signal.SIGINT)
    return jsonify({"ok": True})


@app.post("/api/config/enrichment")
def toggle_enrichment():
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled"))

    config = load_config()
    config["enable_gemini_enrichment"] = enabled
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )
    return jsonify({"ok": True, "enrichment": enabled})


if __name__ == "__main__":
    print(f"🎛️  Tableau de bord : http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)
