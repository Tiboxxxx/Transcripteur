import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from faster_whisper import WhisperModel

try:
    from google.genai import Client
except ImportError:
    Client = None


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

GEMINI_MODEL = "models/gemini-flash-latest"
GEMINI_FALLBACK_MODEL = "models/gemini-2.5-flash"

_gemini_client = None
_gemini_stats = {
    "month": None,
    "total_tokens": 0,
    "total_cost": 0.0,
    "transcriptions": 0,
    "monthly_limit_tokens": 2_000_000,
    "cost_per_million_tokens": 0.075
}

def reset_stats_if_new_month(stats: dict, month: str) -> dict:
    if stats.get("month") != month:
        stats = {
            **stats,
            "month": month,
            "total_tokens": 0,
            "total_cost": 0.0,
            "transcriptions": 0,
        }
    return stats

def load_gemini_stats() -> dict:
    stats_file = LOG_DIR / "gemini_stats.json"
    stats = _gemini_stats.copy()
    if stats_file.exists():
        try:
            stats = {**_gemini_stats, **json.loads(stats_file.read_text())}
        except (json.JSONDecodeError, OSError):
            pass
    return reset_stats_if_new_month(stats, datetime.now().strftime("%Y-%m"))

def save_gemini_stats(stats: dict) -> None:
    stats_file = LOG_DIR / "gemini_stats.json"
    stats_file.write_text(json.dumps(stats, indent=2))

def check_quota_warning(tokens_used: int) -> None:
    global _gemini_stats
    _gemini_stats["total_tokens"] += tokens_used
    _gemini_stats["transcriptions"] += 1
    _gemini_stats["total_cost"] = (_gemini_stats["total_tokens"] / 1_000_000) * _gemini_stats["cost_per_million_tokens"]

    save_gemini_stats(_gemini_stats)

    tokens_remaining = _gemini_stats["monthly_limit_tokens"] - _gemini_stats["total_tokens"]
    percentage = (_gemini_stats["total_tokens"] / _gemini_stats["monthly_limit_tokens"]) * 100

    print(f"\n[INFO] === QUOTA GEMINI ===")
    print(f"[INFO] Tokens utilisés: {_gemini_stats['total_tokens']:,} / {_gemini_stats['monthly_limit_tokens']:,}")
    print(f"[INFO] Pourcentage: {percentage:.1f}%")
    print(f"[INFO] Coût estimé: ${_gemini_stats['total_cost']:.4f}")
    print(f"[INFO] Tokens restants: {tokens_remaining:,}")

    if percentage > 90:
        print(f"\n⚠️  ALERTE: Vous avez dépassé 90% de votre quota gratuit!")
        print(f"⚠️  Vous approchez de la limite (2M tokens/mois)")
    elif percentage > 75:
        print(f"\n⚠️  ATTENTION: Vous avez utilisé {percentage:.1f}% du quota gratuit")
    elif percentage > 50:
        print(f"[INFO] Vous avez utilisé {percentage:.1f}% du quota gratuit")

    print(f"[INFO] ==================\n")

def init_gemini(config: dict | None = None) -> bool:
    global _gemini_client

    if Client is None:
        print("[WARN] Paquet google-genai non installé, enrichissement désactivé")
        return False

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key and config:
        api_key = config.get("gemini_api_key")

    if not api_key:
        print("[WARN] Aucune clé Gemini API trouvée (GEMINI_API_KEY env ou config.json)")
        return False

    try:
        _gemini_client = Client(api_key=api_key)
        print("[OK] Gemini API configurée")
        return True
    except Exception as error:
        print(f"[WARN] Erreur configuration Gemini : {error}")
        return False

def enrich_with_gemini(text: str, language: str = "fr") -> dict | None:
    global _gemini_client, _gemini_stats

    if not _gemini_client:
        return None

    _gemini_stats = load_gemini_stats()

    try:
        if language == "fr":
            prompt = f"""Analyse cette transcription vidéo et crée une STRUCTURE DE COURS DÉTAILLÉE et RÉUTILISABLE.

Fournis un JSON valide avec:
{{
  "title": "Titre du cours",
  "duration_minutes": estimation en minutes,
  "level": "débutant/intermédiaire/avancé",
  "course_structure": [
    {{
      "section_number": 1,
      "section_title": "Titre de la section",
      "duration": "temps estimé",
      "key_concepts": ["concept 1", "concept 2"],
      "subsections": [
        {{
          "title": "Sous-section",
          "points": ["point 1", "point 2"],
          "examples": ["exemple 1", "exemple 2"],
          "notes": "notes importantes"
        }}
      ]
    }}
  ],
  "learning_objectives": ["objectif 1", "objectif 2"],
  "key_takeaways": ["takeaway 1", "takeaway 2"],
  "resources": ["ressource 1", "ressource 2"]
}}

Règles importantes:
- Structure claire avec sections et sous-sections
- Chaque section doit être autonome et réutilisable
- Inclure des exemples concrets
- Identifier les prérequis
- Prévoir des exercices ou cas d'usage

Transcription:
{text}"""
        else:
            prompt = f"""Analyze this video transcript and create a DETAILED and REUSABLE COURSE STRUCTURE.

Provide valid JSON with:
{{
  "title": "Course Title",
  "duration_minutes": estimated minutes,
  "level": "beginner/intermediate/advanced",
  "course_structure": [
    {{
      "section_number": 1,
      "section_title": "Section Title",
      "duration": "estimated time",
      "key_concepts": ["concept 1", "concept 2"],
      "subsections": [
        {{
          "title": "Subsection",
          "points": ["point 1", "point 2"],
          "examples": ["example 1", "example 2"],
          "notes": "important notes"
        }}
      ]
    }}
  ],
  "learning_objectives": ["objective 1", "objective 2"],
  "key_takeaways": ["takeaway 1", "takeaway 2"],
  "resources": ["resource 1", "resource 2"]
}}

Important rules:
- Clear structure with sections and subsections
- Each section should be standalone and reusable
- Include concrete examples
- Identify prerequisites
- Plan for exercises or use cases

Transcript:
{text}"""

        response = None
        model_used = None
        last_error = None

        for model in (GEMINI_MODEL, GEMINI_FALLBACK_MODEL):
            for attempt in range(1, 3):
                try:
                    response = _gemini_client.models.generate_content(
                        model=model,
                        contents=prompt
                    )
                    model_used = model
                    break
                except Exception as error:
                    if "503" not in str(error) and "UNAVAILABLE" not in str(error):
                        raise
                    last_error = error
                    if attempt < 2:
                        print(f"[WARN] {model} surchargé (503), nouvel essai dans 15 s...")
                        time.sleep(15)
            if response is not None:
                break
            if model == GEMINI_MODEL:
                print(f"[WARN] Bascule sur le modèle de secours : {GEMINI_FALLBACK_MODEL}")

        if response is None:
            raise last_error

        try:
            json_str = response.text
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            enrichment = json.loads(json_str.strip())
            enrichment["_model_used"] = model_used.removeprefix("models/")

            usage = getattr(response, "usage_metadata", None)
            if usage and getattr(usage, "total_token_count", None):
                total_tokens_used = usage.total_token_count
            else:
                # Estimation de secours : ~1,3 token par mot
                total_tokens_used = int(
                    (len(prompt.split()) + len(json_str.split())) * 1.3
                )

            check_quota_warning(total_tokens_used)

            return enrichment
        except json.JSONDecodeError:
            print(f"[WARN] Impossible de parser la réponse Gemini JSON")
            return None

    except Exception as error:
        print(f"[WARN] Erreur enrichissement Gemini : {error}")
        return None

def default_capture_name() -> str:
    return datetime.now().strftime("capture_%Y-%m-%d_%Hh%M")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Impossible de trouver un nom libre pour : {path}")


def slugify_title(title: str, max_length: int = 60) -> str:
    slug = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    slug = re.sub(r"[\s-]+", "_", slug).strip("_")
    return slug[:max_length].rstrip("_")


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


def _is_probably_silent(wav_file: Path, threshold: int = 200) -> bool:
    # WAV PCM 16-bit little-endian produit par ffmpeg ; en-tête ~44 octets.
    try:
        data = wav_file.read_bytes()
    except OSError:
        return False

    samples = data[44:][-320_000:]
    if len(samples) < 2:
        return True

    for i in range(0, len(samples) - 1, 2):
        value = int.from_bytes(samples[i:i + 2], "little", signed=True)
        if abs(value) >= threshold:
            return False

    return True


def record_audio(
    name: str | None = None,
    duration: int | None = None,
    source: str | None = None,
    verbose: bool = False
) -> Path:
    if duration is not None and duration <= 0:
        raise ValueError("La durée doit être supérieure à 0 seconde.")

    if name is None:
        name = default_capture_name()

    source = source or get_default_monitor_source()
    output_file = unique_path(CAPTURE_DIR / f"{name}.wav")

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
    silence_checked = False

    try:
        while process.poll() is None:
            time.sleep(1)
            elapsed = int(time.time() - start_time)
            print(
                f"\r⏺ Enregistrement... {elapsed // 60:02d}:{elapsed % 60:02d}",
                end="",
                flush=True
            )

            if not silence_checked and elapsed >= 12:
                silence_checked = True
                if output_file.exists() and _is_probably_silent(output_file):
                    print(
                        "\n[WARN] Aucun son détecté depuis le début ! "
                        "Vérifie que la vidéo/le podcast joue bien et que "
                        "la bonne source audio est utilisée (app.py sources)."
                    )
        print()

    except KeyboardInterrupt:
        manual_stop = True
        print()
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


_START_FILLERS = {"euh", "hum", "hm", "ah", "bah", "ben", "beh"}
_END_FILLERS = {"hein", "voilà", "voila"}


def _strip_punctuation(word: str) -> str:
    return re.sub(r"[.,!?;:]+$", "", word).lower()


def clean_segment_text(text: str) -> str:
    words = text.split()
    if not words:
        return ""

    while words and _strip_punctuation(words[0]) in _START_FILLERS:
        words = words[1:]

    while words and _strip_punctuation(words[-1]) in _END_FILLERS:
        words = words[:-1]

    if not words:
        return ""

    deduped = [words[0]]
    for word in words[1:]:
        if _strip_punctuation(word) != _strip_punctuation(deduped[-1]):
            deduped.append(word)

    result = " ".join(deduped)
    return result[0].upper() + result[1:] if result else ""


def group_into_paragraphs(segments: list[dict], gap: float = 3.0) -> list[list[dict]]:
    if not segments:
        return []

    paragraphs = [[segments[0]]]

    for segment in segments[1:]:
        if segment["start"] - paragraphs[-1][-1]["end"] >= gap:
            paragraphs.append([segment])
        else:
            paragraphs[-1].append(segment)

    return paragraphs


def export_markdown(
    output_file: Path,
    name: str,
    audio_file: Path,
    model_size: str,
    engine: str,
    language: str,
    detected_language: str,
    language_probability: float,
    segments: list[dict],
    gemini_enrichment: dict | None = None
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

        if gemini_enrichment:
            if gemini_enrichment.get("summary"):
                file.write(f"summary: {json.dumps(gemini_enrichment['summary'], ensure_ascii=False)}\n")
            if gemini_enrichment.get("title"):
                file.write(f"course_title: {json.dumps(gemini_enrichment['title'], ensure_ascii=False)}\n")
            if gemini_enrichment.get("level"):
                file.write(f"level: {gemini_enrichment['level']}\n")
            if gemini_enrichment.get("keywords"):
                file.write(f"keywords: {', '.join(gemini_enrichment['keywords'])}\n")
            if gemini_enrichment.get("topics"):
                file.write(f"topics: {', '.join(gemini_enrichment['topics'])}\n")
            if gemini_enrichment.get("sentiment"):
                file.write(f"sentiment: {gemini_enrichment['sentiment']}\n")
            if gemini_enrichment.get("quality_score"):
                file.write(f"quality_score: {gemini_enrichment['quality_score']}\n")
            file.write(
                f"enriched_by: "
                f"{gemini_enrichment.get('_model_used', GEMINI_MODEL.removeprefix('models/'))}\n"
            )

        file.write("---\n\n")

        file.write(f"# Transcription - {name}\n\n")
        file.write(f"Langue détectée : `{detected_language}`\n\n")

        if gemini_enrichment:
            # Afficher la structure de cours si présente
            if gemini_enrichment.get("course_structure"):
                file.write("## Structure du Cours\n\n")

                # Objectifs d'apprentissage
                if gemini_enrichment.get("learning_objectives"):
                    file.write("### Objectifs d'apprentissage\n\n")
                    for obj in gemini_enrichment["learning_objectives"]:
                        file.write(f"- {obj}\n")
                    file.write("\n")

                # Sections du cours
                for section in gemini_enrichment["course_structure"]:
                    section_num = section.get("section_number", "")
                    section_title = section.get("section_title", "")
                    file.write(f"### Section {section_num}: {section_title}\n\n")

                    if section.get("duration"):
                        file.write(f"**Durée:** {section['duration']}\n\n")

                    # Concepts clés
                    if section.get("key_concepts"):
                        file.write("**Concepts clés:**\n")
                        for concept in section["key_concepts"]:
                            file.write(f"- {concept}\n")
                        file.write("\n")

                    # Sous-sections
                    if section.get("subsections"):
                        for subsection in section["subsections"]:
                            file.write(f"#### {subsection.get('title', 'Détails')}\n\n")

                            if subsection.get("points"):
                                for point in subsection["points"]:
                                    file.write(f"- {point}\n")
                                file.write("\n")

                            if subsection.get("examples"):
                                file.write("**Exemples:**\n")
                                for example in subsection["examples"]:
                                    file.write(f"- {example}\n")
                                file.write("\n")

                            if subsection.get("notes"):
                                file.write(f"**Notes:** {subsection['notes']}\n\n")

                # Takeaways
                if gemini_enrichment.get("key_takeaways"):
                    file.write("### Points clés à retenir\n\n")
                    for takeaway in gemini_enrichment["key_takeaways"]:
                        file.write(f"- {takeaway}\n")
                    file.write("\n")

                # Ressources
                if gemini_enrichment.get("resources"):
                    file.write("### Ressources\n\n")
                    for resource in gemini_enrichment["resources"]:
                        file.write(f"- {resource}\n")
                    file.write("\n")

        file.write("## Transcription nettoyée\n\n")

        for paragraph in group_into_paragraphs(segments):
            parts = [clean_segment_text(s["text"]) for s in paragraph]
            parts = [p for p in parts if p]
            if parts:
                file.write(" ".join(parts) + "\n\n")

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

        for paragraph in group_into_paragraphs(segments):
            parts = [clean_segment_text(s["text"]) for s in paragraph]
            parts = [p for p in parts if p]
            if parts:
                file.write(" ".join(parts) + "\n\n")


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
    device: str = "auto",
    config: dict | None = None
) -> dict[str, Path]:
    if not audio_file.exists():
        raise FileNotFoundError(f"Fichier introuvable : {audio_file}")

    if name is None:
        name = audio_file.stem

    # Nom unique commun aux trois formats pour ne rien écraser
    final_name = name
    index = 2
    while (
        (MARKDOWN_DIR / f"{final_name}.md").exists()
        or (TXT_DIR / f"{final_name}.txt").exists()
        or (JSON_DIR / f"{final_name}.json").exists()
    ):
        final_name = f"{name}_{index}"
        index += 1
    name = final_name

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

    gemini_enrichment = None

    if config and config.get("enable_gemini_enrichment", False):
        print("[INFO] Enrichissement Gemini en cours...")
        if init_gemini(config):
            full_text = " ".join([s["text"] for s in segments])
            gemini_enrichment = enrich_with_gemini(full_text, language=language)
            if gemini_enrichment:
                print(f"[OK] Enrichissement Gemini complété")
            else:
                print("[WARN] Enrichissement Gemini échoué, continuation sans")
        else:
            print("[WARN] Impossible d'initialiser Gemini")

    export_markdown(
        output_file=markdown_file,
        name=name,
        audio_file=audio_file,
        model_size=model_size,
        engine=engine,
        language=language,
        detected_language=detected_language,
        language_probability=language_probability,
        segments=segments,
        gemini_enrichment=gemini_enrichment
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
        "enrichment": gemini_enrichment,
    }


def rename_outputs(outputs: dict, new_name: str) -> dict:
    renamed = dict(outputs)

    for key in ("markdown", "txt", "json"):
        old_file = outputs[key]
        new_file = unique_path(old_file.with_stem(new_name))
        old_file.rename(new_file)
        renamed[key] = new_file

    print(f"[OK] Notes renommées : {new_name}")
    return renamed

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

def enrich_markdown_for_obsidian(
    markdown_file: Path,
    title: str | None = None,
    domain: str | None = None
) -> None:
    if not markdown_file.exists():
        print(f"[WARN] Markdown introuvable pour enrichissement : {markdown_file}")
        return

    content = markdown_file.read_text(encoding="utf-8")

    if not content.startswith("---\n"):
        print(f"[WARN] Aucun frontmatter YAML trouvé dans : {markdown_file}")
        return

    end_index = content.find("\n---", 4)

    if end_index == -1:
        print(f"[WARN] Frontmatter YAML mal formé dans : {markdown_file}")
        return

    frontmatter = content[4:end_index].strip()
    body = content[end_index + 4:]

    existing_keys = set()

    for line in frontmatter.splitlines():
        if ":" in line and not line.startswith(" "):
            key = line.split(":", 1)[0].strip()
            existing_keys.add(key)

    additions = []

    if title and "title" not in existing_keys:
        additions.append(f'title: "{title}"')

    if domain and "domain" not in existing_keys:
        additions.append(f"domain: {domain}")

    if "tags" not in existing_keys:
        tags = ["transcription"]
        if domain:
            tags.append(domain)
        additions.append("tags:")
        for tag in tags:
            additions.append(f"  - {tag}")

    if not additions:
        print(f"[INFO] Markdown déjà enrichi : {markdown_file}")
        return

    new_frontmatter = frontmatter + "\n" + "\n".join(additions)
    new_content = "---\n" + new_frontmatter + "\n---" + body

    markdown_file.write_text(new_content, encoding="utf-8")

    print(f"[OK] Markdown enrichi : {markdown_file}")

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
        device=device,
        config=config
    )

    obsidian_dir = args.obsidian_dir or config.get("obsidian_dir")
    obsidian_subdir = args.obsidian_subdir or config.get("obsidian_subdir")

    title = args.title
    enrichment = outputs.get("enrichment")
    if not title and enrichment and enrichment.get("title"):
        title = enrichment["title"]
        print(f"[OK] Titre proposé par Gemini : {title}")

    enrich_markdown_for_obsidian(
        markdown_file=outputs["markdown"],
        title=title,
        domain=args.domain
    )

    if obsidian_dir:
        export_to_obsidian(
            markdown_file=outputs["markdown"],
            obsidian_dir=obsidian_dir,
            obsidian_subdir=obsidian_subdir
        )


def command_reenrich(args) -> None:
    config = load_config()
    name = args.name

    json_file = JSON_DIR / f"{name}.json"
    if not json_file.exists():
        raise FileNotFoundError(f"Export JSON introuvable : {json_file}")

    payload = json.loads(json_file.read_text(encoding="utf-8"))
    segments = payload["segments"]
    language = payload.get("language_requested", "fr")

    if not init_gemini(config):
        raise RuntimeError("Gemini indisponible (clé API ou paquet manquant).")

    print(f"[INFO] Ré-enrichissement de « {name} » ({len(segments)} segments)...")
    full_text = " ".join(s["text"] for s in segments)
    enrichment = enrich_with_gemini(full_text, language=language)

    if not enrichment:
        raise RuntimeError("Échec de l'enrichissement Gemini.")

    markdown_file = MARKDOWN_DIR / f"{name}.md"
    export_markdown(
        output_file=markdown_file,
        name=name,
        audio_file=Path(payload.get("source_audio", f"{name}.wav")),
        model_size=payload.get("model", "small"),
        engine=payload.get("engine", ""),
        language=language,
        detected_language=payload.get("language_detected", language),
        language_probability=float(payload.get("language_probability", 0.0)),
        segments=segments,
        gemini_enrichment=enrichment
    )
    print(f"[OK] Markdown régénéré : {markdown_file}")

    title = args.title
    if not title and enrichment.get("title"):
        title = enrichment["title"]
        print(f"[OK] Titre proposé par Gemini : {title}")

    enrich_markdown_for_obsidian(
        markdown_file=markdown_file,
        title=title,
        domain=args.domain
    )

    obsidian_dir = args.obsidian_dir or config.get("obsidian_dir")
    obsidian_subdir = args.obsidian_subdir or config.get("obsidian_subdir")

    if obsidian_dir:
        export_to_obsidian(
            markdown_file=markdown_file,
            obsidian_dir=obsidian_dir,
            obsidian_subdir=obsidian_subdir
        )


def command_run(args) -> None:
    config = load_config()

    model = args.model or config.get("default_model", "small")
    language = args.language or config.get("default_language", "fr")
    device = args.device or config.get("default_device", "auto")

    auto_named = args.name is None

    audio_file = record_audio(
        name=args.name,
        duration=args.duration,
        source=args.source,
        verbose=args.verbose
    )

    outputs = transcribe_audio(
        audio_file=audio_file,
        name=audio_file.stem,
        model_size=model,
        language=language,
        device=device,
        config=config
    )

    title = args.title
    enrichment = outputs.get("enrichment")
    if not title and enrichment and enrichment.get("title"):
        title = enrichment["title"]
        print(f"[OK] Titre proposé par Gemini : {title}")

    # Si le nom était auto-généré, renommer les notes d'après le titre trouvé
    if auto_named and title:
        slug = slugify_title(title)
        if slug:
            outputs = rename_outputs(outputs, slug)

    enrich_markdown_for_obsidian(
        markdown_file=outputs["markdown"],
        title=title,
        domain=args.domain
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
        default=None,
        help="Nom du fichier audio. Si absent, nom horodaté automatique."
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
        "--title",
        default=None,
        help="Titre de la note (ex: 'Cours sur les LLM')."
    )
    parser_transcribe.add_argument(
        "--domain",
        default=None,
        help="Domaine du contenu : ia, reseau, cyber, systeme, programmation, etc."
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

    parser_reenrich = subparsers.add_parser(
        "reenrich",
        help="Ré-enrichir une note existante avec Gemini (depuis l'export JSON)."
    )
    parser_reenrich.add_argument(
        "--name",
        required=True,
        help="Nom de la note existante (sans extension)."
    )
    parser_reenrich.add_argument(
        "--title",
        default=None,
        help="Titre de la note (sinon celui proposé par Gemini)."
    )
    parser_reenrich.add_argument(
        "--domain",
        default=None,
        help="Domaine du contenu."
    )
    parser_reenrich.add_argument(
        "--obsidian-dir",
        default=None,
        help="Chemin vers le vault Obsidian ou un dossier d'export."
    )
    parser_reenrich.add_argument(
        "--obsidian-subdir",
        default=None,
        help="Sous-dossier dans le vault Obsidian."
    )
    parser_reenrich.set_defaults(func=command_reenrich)

    parser_run = subparsers.add_parser(
        "run",
        help="Enregistrer puis transcrire automatiquement."
    )
    parser_run.add_argument(
        "--name",
        default=None,
        help="Nom de la capture/transcription. Si absent, nom horodaté "
             "automatique (puis renommé d'après le titre Gemini si disponible)."
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
        "--title",
        default=None,
        help="Titre de la note (ex: 'Cours sur les LLM')."
    )
    parser_run.add_argument(
        "--domain",
        default=None,
        help="Domaine du contenu : ia, reseau, cyber, systeme, programmation, etc."
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
