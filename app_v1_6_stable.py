import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from faster_whisper import WhisperModel


BASE_DIR = Path(__file__).parent
CAPTURE_DIR = BASE_DIR / "captures"
TRANSCRIPTION_DIR = BASE_DIR / "transcriptions"
MARKDOWN_DIR = TRANSCRIPTION_DIR / "markdown"
TXT_DIR = TRANSCRIPTION_DIR / "txt"
JSON_DIR = TRANSCRIPTION_DIR / "json"
LOG_DIR = BASE_DIR / "logs"

CAPTURE_DIR.mkdir(exist_ok=True)
TRANSCRIPTION_DIR.mkdir(exist_ok=True)
MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
TXT_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
CONFIG_FILE = BASE_DIR / "config.json"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as error:
        print(f"[WARN] Impossible de lire config.json : {error}")
        return {}

def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_command(command: list[str], check: bool = True) -> str:
    result = subprocess.run(
        command,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return result.stdout.strip()


def print_status(name: str, ok: bool, detail: str = "") -> None:
    status = "OK" if ok else "ERREUR"
    if detail:
        print(f"[{status}] {name} : {detail}")
    else:
        print(f"[{status}] {name}")


def check_environment() -> None:
    print("\n=== Vérification environnement ===\n")

    print_status("Python", True, sys.version.split()[0])

    if command_exists("ffmpeg"):
        try:
            version = run_command(["ffmpeg", "-version"]).splitlines()[0]
            print_status("FFmpeg", True, version)
        except Exception as error:
            print_status("FFmpeg", False, str(error))
    else:
        print_status("FFmpeg", False, "commande introuvable")

    if command_exists("pactl"):
        print_status("pactl", True, "commande disponible")

        try:
            default_sink = run_command(["pactl", "get-default-sink"])
            print_status("Sortie audio par défaut", True, default_sink)

            sources = run_command(["pactl", "list", "short", "sources"])
            monitor = f"{default_sink}.monitor"

            if monitor in sources:
                print_status("Source monitor", True, monitor)
            else:
                print_status("Source monitor", False, f"{monitor} introuvable")

        except Exception as error:
            print_status("Audio PipeWire/Pulse", False, str(error))
    else:
        print_status("pactl", False, "installer pulseaudio-utils")

    if command_exists("nvidia-smi"):
        try:
            nvidia_output = run_command(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader"
                ]
            )
            print_status("NVIDIA", True, nvidia_output)
        except Exception as error:
            print_status("NVIDIA", False, str(error))
    else:
        print_status("NVIDIA", False, "nvidia-smi introuvable")

    try:
        import ctranslate2

        cuda_count = ctranslate2.get_cuda_device_count()
        if cuda_count > 0:
            print_status("CTranslate2 CUDA", True, f"{cuda_count} GPU détecté(s)")
        else:
            print_status("CTranslate2 CUDA", False, "aucun GPU CUDA détecté")

    except Exception as error:
        print_status("CTranslate2", False, str(error))

    print("\n=== Fin vérification ===\n")


def list_audio_sources() -> None:
    print("\n=== Sortie audio par défaut ===")
    try:
        default_sink = run_command(["pactl", "get-default-sink"])
        print(default_sink)
        print(f"\nSource monitor recommandée : {default_sink}.monitor")
    except Exception as error:
        print(f"[ERREUR] Impossible de lire la sortie par défaut : {error}")

    print("\n=== Sources disponibles ===")
    try:
        print(run_command(["pactl", "list", "short", "sources"]))
    except Exception as error:
        print(f"[ERREUR] Impossible de lister les sources : {error}")

    print("\n=== Sorties disponibles ===")
    try:
        print(run_command(["pactl", "list", "short", "sinks"]))
    except Exception as error:
        print(f"[ERREUR] Impossible de lister les sorties : {error}")


def get_default_monitor_source() -> str:
    sink = run_command(["pactl", "get-default-sink"])
    return f"{sink}.monitor"


def build_ffmpeg_command(
    source: str,
    output_file: Path,
    duration: int | None,
    verbose: bool = False
) -> list[str]:
    command = [
        "ffmpeg",
        "-hide_banner",
    ]

    if not verbose:
        command += ["-loglevel", "error", "-nostats"]

    command += [
        "-y",
        "-f", "pulse",
        "-i", source,
    ]

    if duration is not None:
        command += ["-t", str(duration)]

    command += [
        "-ac", "1",
        "-ar", "16000",
        str(output_file)
    ]

    return command


def stop_ffmpeg_cleanly(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return

    print("\n[INFO] Arrêt demandé. Fermeture propre de FFmpeg...")

    try:
        if process.stdin:
            process.stdin.write("q\n")
            process.stdin.flush()

        process.wait(timeout=10)

    except Exception as error:
        print(f"[WARN] Arrêt propre impossible : {error}")
        print("[WARN] Tentative d'arrêt forcé...")

        process.terminate()

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("[WARN] FFmpeg ne répond pas, kill forcé.")
            process.kill()


def record_audio(
    name: str,
    duration: int | None = None,
    source: str | None = None,
    verbose: bool = False
) -> Path:
    if duration is not None and duration <= 0:
        raise ValueError("La durée doit être supérieure à 0 seconde.")

    source = source or get_default_monitor_source()
    output_file = CAPTURE_DIR / f"{name}.wav"

    print(f"[INFO] Source audio utilisée : {source}")
    print(f"[INFO] Enregistrement : {output_file}")

    if duration is None:
        print("[INFO] Durée : manuelle")
        print("[INFO] Appuie sur CTRL+C une seule fois pour arrêter proprement.")
    else:
        print(f"[INFO] Durée : {duration} secondes")

    command = build_ffmpeg_command(source, output_file, duration, verbose)

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        text=True,
        start_new_session=True
    )

    start_time = time.time()
    manual_stop = False

    try:
        process.wait()

    except KeyboardInterrupt:
        manual_stop = True
        stop_ffmpeg_cleanly(process)

    elapsed = int(time.time() - start_time)
    return_code = process.returncode

    if return_code not in (0, None):
        if not (manual_stop and return_code == 255):
            print(f"[WARN] FFmpeg a terminé avec le code : {return_code}")

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError("Le fichier audio généré est vide ou absent.")

    print(f"[OK] Audio généré : {output_file}")
    print(f"[INFO] Durée réelle approximative : {elapsed} secondes")

    return output_file


def load_whisper_model(model_size: str, device: str):
    if device == "cuda":
        print("[INFO] Utilisation GPU CUDA forcée...")
        return WhisperModel(
            model_size,
            device="cuda",
            compute_type="int8_float16"
        ), "cuda/int8_float16"

    if device == "cpu":
        print("[INFO] Utilisation CPU forcée...")
        return WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8"
        ), "cpu/int8"

    print("[INFO] Mode auto : tentative GPU puis fallback CPU...")

    try:
        return WhisperModel(
            model_size,
            device="cuda",
            compute_type="int8_float16"
        ), "cuda/int8_float16"
    except Exception as error:
        print(f"[WARN] GPU indisponible, bascule CPU : {error}")
        return WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8"
        ), "cpu/int8"


def export_markdown(
    output_file: Path,
    name: str,
    audio_file: Path,
    model_size: str,
    engine: str,
    language: str,
    detected_language: str,
    language_probability: float,
    segments: list[dict]
) -> None:
    with output_file.open("w", encoding="utf-8") as file:
        file.write("---\n")
        file.write("type: transcription_video\n")
        file.write(f"date: {datetime.now().isoformat(timespec='seconds')}\n")
        file.write(f"source_audio: {audio_file.name}\n")
        file.write("moteur: faster-whisper\n")
        file.write(f"modele: {model_size}\n")
        file.write(f"engine: {engine}\n")
        file.write(f"language: {language}\n")
        file.write(f"language_detected: {detected_language}\n")
        file.write(f"language_probability: {language_probability:.2f}\n")
        file.write(f"segments: {len(segments)}\n")
        file.write("---\n\n")

        file.write(f"# Transcription - {name}\n\n")
        file.write(f"Langue détectée : `{detected_language}`\n\n")
        file.write("## Transcription horodatée\n\n")

        for segment in segments:
            file.write(
                f"[{segment['start']:.2f} - {segment['end']:.2f}] "
                f"{segment['text']}\n\n"
            )


def export_txt(output_file: Path, name: str, segments: list[dict]) -> None:
    with output_file.open("w", encoding="utf-8") as file:
        file.write(f"Transcription - {name}\n")
        file.write("=" * (16 + len(name)) + "\n\n")

        for segment in segments:
            file.write(
                f"[{segment['start']:.2f} - {segment['end']:.2f}] "
                f"{segment['text']}\n"
            )


def export_json(
    output_file: Path,
    name: str,
    audio_file: Path,
    model_size: str,
    engine: str,
    language: str,
    detected_language: str,
    language_probability: float,
    segments: list[dict]
) -> None:
    payload = {
        "type": "transcription_video",
        "name": name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_audio": str(audio_file),
        "engine": engine,
        "model": model_size,
        "language_requested": language,
        "language_detected": detected_language,
        "language_probability": language_probability,
        "segment_count": len(segments),
        "segments": segments,
    }

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def transcribe_audio(
    audio_file: Path,
    name: str | None = None,
    model_size: str = "small",
    language: str = "fr",
    device: str = "auto"
) -> dict[str, Path]:
    if not audio_file.exists():
        raise FileNotFoundError(f"Fichier introuvable : {audio_file}")

    if name is None:
        name = audio_file.stem

    markdown_file = MARKDOWN_DIR / f"{name}.md"
    txt_file = TXT_DIR / f"{name}.txt"
    json_file = JSON_DIR / f"{name}.json"

    print(f"[INFO] Fichier audio : {audio_file}")
    print(f"[INFO] Modèle : {model_size}")
    print("[INFO] Chargement du modèle Faster-Whisper...")

    model, engine = load_whisper_model(model_size, device)

    print(f"[INFO] Moteur utilisé : {engine}")
    print("[INFO] Transcription en cours...")

    raw_segments, info = model.transcribe(
        str(audio_file),
        language=language,
        beam_size=5
    )

    segments = []

    for segment in raw_segments:
        item = {
            "start": round(float(segment.start), 2),
            "end": round(float(segment.end), 2),
            "text": segment.text.strip()
        }

        segments.append(item)

        print(
            f"[{item['start']:.2f} - {item['end']:.2f}] "
            f"{item['text']}"
        )

    detected_language = info.language
    language_probability = float(info.language_probability)

    export_markdown(
        output_file=markdown_file,
        name=name,
        audio_file=audio_file,
        model_size=model_size,
        engine=engine,
        language=language,
        detected_language=detected_language,
        language_probability=language_probability,
        segments=segments
    )

    export_txt(
        output_file=txt_file,
        name=name,
        segments=segments
    )

    export_json(
        output_file=json_file,
        name=name,
        audio_file=audio_file,
        model_size=model_size,
        engine=engine,
        language=language,
        detected_language=detected_language,
        language_probability=language_probability,
        segments=segments
    )

    print(f"[OK] Markdown généré : {markdown_file}")
    print(f"[OK] TXT généré      : {txt_file}")
    print(f"[OK] JSON généré     : {json_file}")

    return {
        "markdown": markdown_file,
        "txt": txt_file,
        "json": json_file,
    }

def export_to_obsidian(
    markdown_file: Path,
    obsidian_dir: str,
    obsidian_subdir: str | None = None
) -> Path:
    vault_dir = Path(obsidian_dir).expanduser()

    if obsidian_subdir:
        destination_dir = vault_dir / obsidian_subdir
    else:
        destination_dir = vault_dir

    destination_dir.mkdir(parents=True, exist_ok=True)

    destination_file = destination_dir / markdown_file.name

    shutil.copy2(markdown_file, destination_file)

    print(f"[OK] Export Obsidian : {destination_file}")

    return destination_file

def command_check(args) -> None:
    check_environment()


def command_sources(args) -> None:
    list_audio_sources()


def command_record(args) -> None:
    record_audio(
        name=args.name,
        duration=args.duration,
        source=args.source,
        verbose=args.verbose
    )


def command_transcribe(args) -> None:
    config = load_config()

    model = args.model or config.get("default_model", "small")
    language = args.language or config.get("default_language", "fr")
    device = args.device or config.get("default_device", "auto")

    outputs = transcribe_audio(
        audio_file=Path(args.file),
        name=args.name,
        model_size=model,
        language=language,
        device=device
    )

    obsidian_dir = args.obsidian_dir or config.get("obsidian_dir")
    obsidian_subdir = args.obsidian_subdir or config.get("obsidian_subdir")

    if obsidian_dir:
        export_to_obsidian(
            markdown_file=outputs["markdown"],
            obsidian_dir=obsidian_dir,
            obsidian_subdir=obsidian_subdir
        )


def command_run(args) -> None:
    config = load_config()

    model = args.model or config.get("default_model", "small")
    language = args.language or config.get("default_language", "fr")
    device = args.device or config.get("default_device", "auto")

    audio_file = record_audio(
        name=args.name,
        duration=args.duration,
        source=args.source,
        verbose=args.verbose
    )

    outputs = transcribe_audio(
        audio_file=audio_file,
        name=args.name,
        model_size=model,
        language=language,
        device=device
    )

    obsidian_dir = args.obsidian_dir or config.get("obsidian_dir")
    obsidian_subdir = args.obsidian_subdir or config.get("obsidian_subdir")

    if obsidian_dir:
        export_to_obsidian(
            markdown_file=outputs["markdown"],
            obsidian_dir=obsidian_dir,
            obsidian_subdir=obsidian_subdir
        )

    if args.delete_audio:
        audio_file.unlink()
        print(f"[INFO] Audio supprimé : {audio_file}")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcripteur local : capture audio système puis transcription multi-format."
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    parser_check = subparsers.add_parser(
        "check",
        help="Vérifier l'environnement technique."
    )
    parser_check.set_defaults(func=command_check)

    parser_sources = subparsers.add_parser(
        "sources",
        help="Lister les sources et sorties audio disponibles."
    )
    parser_sources.set_defaults(func=command_sources)

    parser_record = subparsers.add_parser(
        "record",
        help="Enregistrer uniquement l'audio système."
    )
    parser_record.add_argument(
        "--name",
        required=True,
        help="Nom du fichier audio."
    )
    parser_record.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Durée en secondes. Si absent, arrêt manuel avec CTRL+C."
    )
    parser_record.add_argument(
        "--source",
        default=None,
        help="Source audio spécifique à utiliser."
    )
    parser_record.add_argument(
        "--verbose",
        action="store_true",
        help="Afficher les logs détaillés FFmpeg."
    )
    parser_record.set_defaults(func=command_record)

    parser_transcribe = subparsers.add_parser(
        "transcribe",
        help="Transcrire un fichier audio existant."
    )
    parser_transcribe.add_argument(
        "--file",
        required=True,
        help="Chemin du fichier audio."
    )
    parser_transcribe.add_argument(
        "--name",
        default=None,
        help="Nom de sortie."
    )
    parser_transcribe.add_argument(
        "--model",
        default=None,
        help="Modèle : tiny, base, small, medium."
    )
    parser_transcribe.add_argument(
        "--language",
        default=None,
        help="Langue de transcription."
    )
    parser_transcribe.add_argument(
        "--device",
        choices=["auto", "cuda", "cpu"],
        default=None,
        help="Périphérique de calcul : auto, cuda ou cpu."
    )
    parser_transcribe.add_argument(
        "--obsidian-dir",
        default=None,
        help="Chemin vers le vault Obsidian ou un dossier d'export."
    )
    parser_transcribe.add_argument(
        "--obsidian-subdir",
        default=None,
        help="Sous-dossier dans le vault Obsidian, exemple : 00_INBOX."
    )
    parser_transcribe.set_defaults(func=command_transcribe)

    parser_run = subparsers.add_parser(
        "run",
        help="Enregistrer puis transcrire automatiquement."
    )
    parser_run.add_argument(
        "--name",
        required=True,
        help="Nom de la capture/transcription."
    )
    parser_run.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Durée en secondes. Si absent, arrêt manuel avec CTRL+C."
    )
    parser_run.add_argument(
        "--source",
        default=None,
        help="Source audio spécifique à utiliser."
    )
    parser_run.add_argument(
        "--model",
        default=None,
        help="Modèle : tiny, base, small, medium."
    )
    parser_run.add_argument(
        "--language",
        default=None,
        help="Langue de transcription."
    )
    parser_run.add_argument(
        "--device",
        choices=["auto", "cuda", "cpu"],
        default=None,
        help="Périphérique de calcul : auto, cuda ou cpu."
    )
    parser_run.add_argument(
        "--delete-audio",
        action="store_true",
        help="Supprimer le fichier audio après transcription."
    )
    parser_run.add_argument(
        "--verbose",
        action="store_true",
        help="Afficher les logs détaillés FFmpeg."
    )
    parser_run.add_argument(
        "--obsidian-dir",
        default=None,
        help="Chemin vers le vault Obsidian ou un dossier d'export."
    )
    parser_run.add_argument(
        "--obsidian-subdir",
        default=None,
        help="Sous-dossier dans le vault Obsidian, exemple : 00_INBOX."
    )
    parser_run.set_defaults(func=command_run)

    return parser

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n[INFO] Interruption utilisateur.")
        sys.exit(130)
    except Exception as error:
        print(f"[ERREUR] {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
