import argparse
import subprocess
from datetime import datetime
from pathlib import Path

from faster_whisper import WhisperModel


BASE_DIR = Path(__file__).parent
CAPTURE_DIR = BASE_DIR / "captures"
TRANSCRIPTION_DIR = BASE_DIR / "transcriptions"

CAPTURE_DIR.mkdir(exist_ok=True)
TRANSCRIPTION_DIR.mkdir(exist_ok=True)


def get_default_monitor_source() -> str:
    sink = subprocess.check_output(
        ["pactl", "get-default-sink"],
        text=True
    ).strip()

    return f"{sink}.monitor"


def record_audio(name: str, duration: int) -> Path:
    source = get_default_monitor_source()
    output_file = CAPTURE_DIR / f"{name}.wav"

    print(f"[INFO] Source audio utilisée : {source}")
    print(f"[INFO] Enregistrement : {output_file}")
    print(f"[INFO] Durée : {duration} secondes")

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "pulse",
        "-i", source,
        "-t", str(duration),
        "-ac", "1",
        "-ar", "16000",
        str(output_file)
    ]

    subprocess.run(cmd, check=True)

    return output_file


def transcribe_audio(audio_file: Path, name: str, model_size: str = "small") -> Path:
    output_file = TRANSCRIPTION_DIR / f"{name}.md"

    print("[INFO] Chargement du modèle Faster-Whisper...")

    try:
        model = WhisperModel(
            model_size,
            device="cuda",
            compute_type="int8_float16"
        )
        engine = "cuda/int8_float16"
    except Exception as error:
        print(f"[WARN] GPU indisponible, bascule CPU : {error}")
        model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8"
        )
        engine = "cpu/int8"

    print(f"[INFO] Moteur utilisé : {engine}")
    print("[INFO] Transcription en cours...")

    segments, info = model.transcribe(
        str(audio_file),
        language="fr",
        beam_size=5
    )

    with output_file.open("w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("type: transcription_video\n")
        f.write(f"date: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"source_audio: {audio_file.name}\n")
        f.write(f"moteur: faster-whisper\n")
        f.write(f"modele: {model_size}\n")
        f.write(f"engine: {engine}\n")
        f.write("---\n\n")

        f.write(f"# Transcription - {name}\n\n")
        f.write(f"Langue détectée : `{info.language}`\n\n")
        f.write("## Transcription horodatée\n\n")

        for segment in segments:
            line = f"[{segment.start:.2f} - {segment.end:.2f}] {segment.text.strip()}"
            print(line)
            f.write(line + "\n\n")

    print(f"[OK] Transcription générée : {output_file}")

    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Capture audio système puis transcription locale en Markdown."
    )

    parser.add_argument(
        "--name",
        default=datetime.now().strftime("capture_%Y%m%d_%H%M%S"),
        help="Nom de la capture/transcription"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Durée d'enregistrement en secondes"
    )

    parser.add_argument(
        "--model",
        default="small",
        help="Modèle Whisper à utiliser : tiny, base, small, medium"
    )

    args = parser.parse_args()

    audio_file = record_audio(args.name, args.duration)
    transcribe_audio(audio_file, args.name, args.model)


if __name__ == "__main__":
    main()
