# 🎙️ Transcripteur Local

Enregistre l'audio de ton PC (vidéos, podcasts, formations), le transcrit
**localement** avec Whisper, l'enrichit avec Gemini (résumé, structure, titre
automatique) et envoie la note finale dans **Obsidian**.

```
Audio système → Whisper (local) → Gemini (cloud, optionnel) → Note Obsidian
```

Tout se pilote depuis un **tableau de bord web** ou en ligne de commande.

---

## 🚀 Utilisation quotidienne

### Option A — Tableau de bord web (recommandé)

```bash
./transcripteur-web
```

Puis ouvre **http://localhost:8765** :

1. Lance ta vidéo ou ton podcast.
2. Clique **⏺ Enregistrer**.
3. Écoute tranquillement (timer en direct, alerte si aucun son n'est capté).
4. Clique **⏹ Arrêter et transcrire** — tout s'enchaîne automatiquement.
5. La bannière verte affiche le titre trouvé par Gemini ; clique **Ouvrir ↗**
   pour ouvrir la note dans Obsidian.

Le tableau de bord affiche aussi :
- **Tokens Gemini restants** (jauge, remise à zéro chaque mois), coût estimé.
- **Notes récentes** avec durée audio et lien Obsidian.
- **Captures audio** : bouton *📝 Transcrire* pour un `.wav` jamais transcrit.
- Bouton *✨ Ré-enrichir* : régénère résumé/structure/titre d'une note
  existante (⚠️ remplace son contenu dans le vault).
- Boutons *🗑* : suppression d'une note (exports + copie Obsidian) ou d'un
  audio, avec confirmation obligatoire.
- Interrupteur pour activer/désactiver l'enrichissement Gemini.
- Le **Journal** en bas montre ce qui se passe (utile en cas d'erreur).

### Option B — Ligne de commande

```bash
./transcripteur                  # enregistre immédiatement, CTRL+C pour arrêter
./transcripteur run --name "mon_cours" --title "Cours Python" --domain formation
./transcripteur transcribe --file captures/mon_fichier.wav
./transcripteur reenrich --name "ma_note"
./transcripteur record --duration 300        # audio seul, 5 minutes
./transcripteur check                        # vérifier l'environnement
./transcripteur sources                      # lister les sources audio
```

Sans `--name`, un nom horodaté est généré (`capture_2026-07-06_14h32`) puis
remplacé par le titre proposé par Gemini. Rien n'est jamais écrasé : en cas de
doublon, un suffixe `_2`, `_3`… est ajouté.

---

## 📦 Installation (nouvelle machine)

Prérequis : Ubuntu/Linux, Python 3.10+, FFmpeg, PulseAudio/PipeWire
(`pactl`). GPU NVIDIA optionnel (bascule CPU automatique).

```bash
git clone <ton-depot> transcripteur-local && cd transcripteur-local
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp config.example.json config.json    # puis éditer (voir Configuration)
./transcripteur check                 # tout doit être [OK]
```

---

## ⚙️ Configuration (`config.json`)

```json
{
  "default_model": "small",
  "default_language": "fr",
  "default_device": "cpu",
  "obsidian_dir": "/home/moi/Documents/MonVault",
  "obsidian_subdir": "00_INBOX",
  "obsidian_monthly_folders": true,
  "gemini_api_key": "...",
  "enable_gemini_enrichment": true
}
```

- `default_model` : `tiny` | `base` | `small` | `medium` —
  `default_device` : `auto` | `cuda` | `cpu`.
- **Clé Gemini** : gratuite sur [Google AI Studio](https://aistudio.google.com/apikey).
  Préférer la variable d'environnement `GEMINI_API_KEY` (prioritaire sur le
  fichier). ⚠️ `config.json` est exclu de git — ne jamais y committer la clé.
- **Modèles utilisés** : `gemini-flash-latest`, avec bascule automatique sur
  `gemini-2.5-flash` en cas de surcharge (503). Les modèles Pro ne sont pas
  disponibles dans le free tier.
- **Sans clé / enrichissement désactivé** : tout fonctionne, la note contient
  la transcription sans résumé ni titre automatique.

---

## 📁 Ce que produit chaque session

| Fichier | Emplacement |
|---|---|
| Audio brut `.wav` | `captures/` (sauf `--delete-audio`) |
| Note Markdown enrichie | `transcriptions/markdown/` + copie dans le vault, classée par mois (`00_INBOX/2026-07/…`) |
| Texte brut `.txt` | `transcriptions/txt/` |
| Export `.json` (segments horodatés) | `transcriptions/json/` — sert au ré-enrichissement |
| Suivi du quota Gemini | `logs/gemini_stats.json` (reset mensuel automatique) |

---

## 🧪 Tester

```bash
./venv/bin/python test_app_units.py    # tests unitaires (aucun réseau)
./venv/bin/python test_gemini.py       # test de la clé et de l'API Gemini
./transcripteur check                  # environnement audio/GPU
```

Test complet : dashboard → enregistrer 1 min d'une vidéo → arrêter → vérifier
la note dans Obsidian.

---

## 🔧 Dépannage

| Symptôme | Cause probable / solution |
|---|---|
| « Aucun son détecté » pendant l'enregistrement | La vidéo ne joue pas, volume coupé, ou mauvaise source → `./transcripteur sources` |
| Erreur 503 Gemini dans le journal | Surcharge temporaire Google — retry et fallback sont automatiques ; sinon *✨ Ré-enrichir* plus tard |
| Erreur 429 `RESOURCE_EXHAUSTED` | Quota gratuit épuisé ou modèle Pro demandé → vérifier la jauge du dashboard |
| Fichier audio vide | Source monitor absente → `./transcripteur check` |
| Le dashboard ne répond plus | Relancer `./transcripteur-web` |
| GPU non détecté | Normal en `"default_device": "cpu"` ; sinon vérifier `nvidia-smi` |

---

## 📚 Historique et documentation

- `V1.10_CHANGES.md` — mode zéro-friction, dashboard web, titre auto Gemini.
- `V1.9_CHANGES.md`, `MIGRATION_V1.9.txt`, `SETUP_GEMINI.md` — intégration Gemini.
- Historique complet : `git log` (les anciennes versions `app_v*.py` sont dans
  le premier commit).

**Version courante : V1.11** — ré-enrichissement, transcription des captures,
tokens exacts, fallback de modèle.
