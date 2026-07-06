#!/usr/bin/env python3
"""Test script for Gemini integration in V1.9"""

import json
from pathlib import Path
from google.genai import Client

def test_gemini_api():
    config_file = Path("config.json")
    if not config_file.exists():
        print("[FAIL] config.json not found")
        return False

    config = json.loads(config_file.read_text())
    api_key = config.get("gemini_api_key")

    if not api_key:
        print("[FAIL] gemini_api_key not found in config.json")
        return False

    print(f"[INFO] Testing Gemini API with key: {api_key[:20]}...")

    try:
        client = Client(api_key=api_key)
        print("[OK] Gemini client initialized")

        # Test generation
        test_text = "Bonjour, ceci est un test de transcription courte."
        prompt = f"""Enrichis cette transcription en français. Fournis un JSON valide avec:
- summary: résumé en 2-3 phrases
- keywords: liste de mots-clés (max 5)
- topics: sujets traités (liste)
- sentiment: positif/neutre/négatif
- quality_score: 0-100

Transcription:
{test_text}"""

        response = client.models.generate_content(
            model="models/gemini-flash-latest",
            contents=prompt
        )

        print("[OK] API response received")
        print(f"[INFO] Response text: {response.text[:100]}...")

        # Try to parse JSON
        json_str = response.text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        enrichment = json.loads(json_str.strip())
        print("[OK] JSON parsed successfully")
        print(f"[OK] Enrichment: {enrichment}")

        return True

    except Exception as error:
        print(f"[FAIL] Error: {error}")
        return False

if __name__ == "__main__":
    print("=== Gemini V1.9 API Test ===\n")
    success = test_gemini_api()
    print(f"\n=== Test Result: {'PASSED' if success else 'FAILED'} ===")
    exit(0 if success else 1)
