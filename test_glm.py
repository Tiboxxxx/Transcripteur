#!/usr/bin/env python3
"""Test script for GLM 5.2 integration in V1.9"""

import json
import os
from pathlib import Path
from zhipuai import ZhipuAI

def test_glm_api():
    config_file = Path("config.json")
    if not config_file.exists():
        print("[FAIL] config.json not found")
        return False

    config = json.loads(config_file.read_text())
    api_key = config.get("glm_api_key") or os.getenv("GLM_API_KEY")

    if not api_key:
        print("[FAIL] glm_api_key not found in config.json or GLM_API_KEY env")
        return False

    print(f"[INFO] Testing GLM API with key: {api_key[:20]}...")

    try:
        client = ZhipuAI(api_key=api_key)
        print("[OK] GLM client initialized")

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

        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        print("[OK] API response received")
        print(f"[INFO] Response text: {response.choices[0].message.content[:100]}...")

        # Try to parse JSON
        json_str = response.choices[0].message.content
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
    print("=== GLM 5.2 V1.9 API Test ===\n")
    success = test_glm_api()
    print(f"\n=== Test Result: {'PASSED' if success else 'FAILED'} ===")
    exit(0 if success else 1)
