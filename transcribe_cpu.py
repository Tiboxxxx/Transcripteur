from faster_whisper import WhisperModel

audio_file = "test_capture.wav"

model = WhisperModel(
    "small",
    device="cuda",
    compute_type="int8_float16"
)

segments, info = model.transcribe(
    audio_file,
    language="fr",
    beam_size=5
)

print(f"Langue détectée : {info.language}")
print(f"Probabilité : {info.language_probability:.2f}")

with open("transcription_gpu.md", "w", encoding="utf-8") as f:
    f.write("# Transcription GPU\n\n")

    for segment in segments:
        line = f"[{segment.start:.2f} - {segment.end:.2f}] {segment.text.strip()}"
        print(line)
        f.write(line + "\n")
