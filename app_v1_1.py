import argparse
import subprocess
from datetime import datetime
from pathlib import Path

from faster_whisper import WhisperModel


BASE_DIR = Path(__file__).parent
CAPTURE_DIR = BASE_DIR / "captures"
TRANSCRIPTION_DIR = BASE_DIR / "transcriptions"
LOG_DIR = BASE_DIR / "logs"

CAPTURE_DIR.mkdir(exist_ok=True)
TRANSCRIPTION_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


def run_command(command: list[str]) -> str:
    result = subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return result.stdout.strip()


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


def record_audio(name: str, duration: int, source: str | None = None) -> Path:
    if duration <= 0:
        raise ValueError("La durée doit être supérieure à 0 seconde.")

    source = source or get_default_monitor_source()
    output_file = CAPTURE_DIR / f"{name}.wav"

    print(f"[INFO] Source audio utilisée : {source}")
    print(f"[INFO] Enregistrement : {output_file}")
    print(f"[INFO] Durée : {duration} secondes")

    command = [
        "ffmpeg",
        "-y",
        "-f", "pulse",
        "-i", source,
        "-t", str(duration),
        "-ac", "1",
        "-ar", "16000",
        str(output_file)
    ]

    subprocess.run(command, check=True)

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError("Le fichier audio généré est vide ou absent.")

    print(f"[OK] Audio généré : {output_file}")
    return output_file


def load_whisper_model(model_size: str, device: str):
    if device == "cuda":
        print("[INFO] Tentative d'utilisation GPU CUDA...")
        return WhisperModel(
            model_size,
            device="cuda",
            compute_type="int8_float16"
        ), "cuda/int8_float16"

    if device == "cpu":
        print("[INFO] Utilisation CPU...")
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


def transcribe_audio(
    audio_file: Path,
    name: str | None = None,
    model_size: str = "small",
    language: str = "fr",
    device: str = "auto"
) -> Path:
    if not audio_file.exists():
        raise FileNotFoundError(f"Fichier introuvable : {audio_file}")

    if name is None:
        name = audio_file.stem

    output_file = TRANSCRIPTION_DIR / f"{name}.md"

    print(f"[INFO] Fichier audio : {audio_file}")
    print(f"[INFO] Modèle : {model_size}")
    print("[INFO] Chargement du modèle Faster-Whisper...")

    model, engine = load_whisper_model(model_size, device)

    print(f"[INFO] Moteur utilisé : {engine}")
    print("[INFO] Transcription en cours...")

    segments, info = model.transcribe(
        str(audio_file),
        language=language,
        beam_size=5
    )

    with output_file.open("w", encoding="utf-8") as file:
        file.write("---\n")
        file.write("type: transcription_video\n")
        file.write(f"date: {datetime.now().isoformat(timespec='seconds')}\n")
        file.write(f"source_audio: {audio_file.name}\n")
        file.write("moteur: faster-whisper\n")
        file.write(f"modele: {model_size}\n")
        file.write(f"engine: {engine}\n")
        file.write(f"language: {language}\n")
        file.write("---\n\n")

        file.write(f"# Transcription - {name}\n\n")
        file.write(f"Langue détectée : `{info.language}`\n\n")
        file.write("## Transcription horodatée\n\n")

        for segment in segments:
            line = f"[{segment.start:.2f} - {segment.end:.2f}] {segment.text.strip()}"
            print(line)
            file.write(line + "\n\n")

    print(f"[OK] Transcription générée : {output_file}")
    return output_file


def command_sources(args) -> None:
    list_audio_sources()


def command_record(args) -> None:
    record_audio(
        name=args.name,
        duration=args.duration,
        source=args.source
    )


def command_transcribe(args) -> None:
    transcribe_audio(
        audio_file=Path(args.file),
        name=args.name,
        model_size=args.model,
        language=args.language,
        device=args.device
    )


def command_run(args) -> None:
    audio_file = record_audio(
        name=args.name,
        duration=args.duration,
        source=args.source
    )

    transcribe_audio(
        audio_file=audio_file,
        name=args.name,
        model_size=args.model,
        language=args.language,
        device=args.device
    )

    if args.delete_audio:
        audio_file.unlink()
        print(f"[INFO] Audio supprimé : {audio_file}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcripteur local : capture audio système puis transcription Markdown."
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    parser_sources = subparsers.add_parser(
        "sources",
        help="Lister les sources et sorties audio disponibles."
    )
    parser_sources.set_defaults(func=command_sources)

    parser_record = subparsers.add_parser(
        "record",
        help="Enregistrer uniquement l'audio système."
    )
    parser_record.add_argument("--name", required=True, help="Nom du fichier audio.")
    parser_record.add_argument("--duration", type=int, required=True, help="Durée en secondes.")
    parser_record.add_argument("--source", default=None, help="Source audio spécifique à utiliser.")
    parser_record.set_defaults(func=command_record)

    parser_transcribe = subparsers.add_parser(
        "transcribe",
        help="Transcrire un fichier audio existant."
    )
    parser_transcribe.add_argument("--file", required=True, help="Chemin du fichier audio.")
    parser_transcribe.add_argument("--name", default=None, help="Nom de sortie Markdown.")
    parser_transcribe.add_argument("--model", default="small", help="Modèle : tiny, base, small, medium.")
    parser_transcribe.add_argument("--language", default="fr", help="Langue de transcription.")
    parser_transcribe.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser_transcribe.set_defaults(func=command_transcribe)

    parser_run = subparsers.add_parser(
        "run",
        help="Enregistrer puis transcrire automatiquement."
    )
    parser_run.add_argument("--name", required=True, help="Nom de la capture/transcription.")
    parser_run.add_argument("--duration", type=int, required=True, help="Durée en secondes.")
    parser_run.add_argument("--source", default=None, help="Source audio spécifique à utiliser.")
    parser_run.add_argument("--model", default="small", help="Modèle : tiny, base, small, medium.")
    parser_run.add_argument("--language", default="fr", help="Langue de transcription.")
    parser_run.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser_run.add_argument(
        "--delete-audio",
        action="store_true",
        help="Supprimer le fichier audio après transcription."
    )
    parser_run.set_defaults(func=command_run)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
