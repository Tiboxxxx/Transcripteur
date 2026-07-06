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
    TXT_DIR,
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


def _find_vault_note(note_name: str, config: dict) -> Path | None:
    obsidian_dir = config.get("obsidian_dir")
    if not obsidian_dir:
        return None

    base = Path(obsidian_dir).expanduser() / (config.get("obsidian_subdir") or "")

    flat = base / f"{note_name}.md"
    if flat.exists():
        return flat

    # Sous-dossiers mensuels (classement 2026-07, 2026-08, ...)
    for candidate in sorted(base.glob(f"[0-9][0-9][0-9][0-9]-[0-9][0-9]/{note_name}.md"), reverse=True):
        return candidate

    # N'importe où ailleurs dans le vault (note reclassée à la main)
    vault = Path(obsidian_dir).expanduser()
    for candidate in vault.rglob(f"{note_name}.md"):
        if ".obsidian" not in candidate.parts and ".trash" not in candidate.parts:
            return candidate

    return None


def _obsidian_url(note_name: str, config: dict) -> str | None:
    note_file = _find_vault_note(note_name, config)
    if note_file is None:
        return None

    vault = Path(config["obsidian_dir"]).expanduser()
    file_param = str(note_file.relative_to(vault).with_suffix(""))
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
            "note_name": Path(_job["note"]).stem if _job["note"] else None,
            "note_url": (
                _obsidian_url(Path(_job["note"]).stem, config)
                if _job["note"] else None
            ),
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


@app.post("/api/note/open")
def note_open():
    """Ouvre la note dans Obsidian via xdg-open, côté serveur.

    Indispensable quand le dashboard est affiché dans un navigateur qui ne
    gère pas le protocole obsidian:// (navigateur intégré VSCode, etc.).
    """
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")

    if not name or "/" in name or name.startswith("."):
        return jsonify({"error": "Nom de note invalide"}), 400

    config = load_config()
    note_file = _find_vault_note(name, config)

    if note_file is not None:
        vault = Path(config["obsidian_dir"]).expanduser()
        file_param = str(note_file.relative_to(vault).with_suffix(""))
        target = f"obsidian://open?vault={quote(vault.name)}&file={quote(file_param)}"
    elif (MARKDOWN_DIR / f"{name}.md").exists():
        # Pas dans le vault : ouvrir l'export local avec l'application par défaut
        target = str(MARKDOWN_DIR / f"{name}.md")
    else:
        return jsonify({"error": f"Note introuvable : {name}"}), 404

    subprocess.Popen(
        ["xdg-open", target],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return jsonify({"ok": True, "target": target})


@app.post("/api/note/delete")
def note_delete():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")

    if not name or "/" in name or name.startswith("."):
        return jsonify({"error": "Nom de note invalide"}), 400

    config = load_config()
    deleted = []

    targets = [
        MARKDOWN_DIR / f"{name}.md",
        TXT_DIR / f"{name}.txt",
        JSON_DIR / f"{name}.json",
    ]
    vault_note = _find_vault_note(name, config)
    if vault_note:
        targets.append(vault_note)

    for target in targets:
        if target.exists():
            target.unlink()
            deleted.append(str(target))

    if not deleted:
        return jsonify({"error": f"Note inconnue : {name}"}), 404
    return jsonify({"ok": True, "deleted": deleted})


@app.post("/api/capture/delete")
def capture_delete():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")

    if not name or "/" in name or name.startswith("."):
        return jsonify({"error": "Nom de capture invalide"}), 400

    wav_file = CAPTURE_DIR / f"{name}.wav"
    if not wav_file.exists():
        return jsonify({"error": f"Capture inconnue : {name}"}), 404

    wav_file.unlink()
    return jsonify({"ok": True, "deleted": [str(wav_file)]})


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
