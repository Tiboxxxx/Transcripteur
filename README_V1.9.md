# 🎙️ Transcripteur Local V1.9 - Gemini Edition

## Résumé rapide

**V1.9 ajoute l'enrichissement IA Gemini** à votre pipeline de transcription locale.

```
Enregistrement audio → Transcription Whisper (local) → Enrichissement Gemini → Obsidian
```

## ✨ Nouveautés V1.9

| Fonctionnalité | Avant | Après |
|---|---|---|
| **Transcription** | Whisper local | Whisper local (identique) |
| **Enrichissement** | ❌ Aucun | ✅ Résumé, keywords, sentiment |
| **Modèle IA** | Whisper uniquement | Whisper + Gemini 1.5 Flash |
| **Coûts** | Gratuit (GPU local) | Gratuit + ~free tier Gemini |

## 🚀 Démarrage rapide

### 1️⃣ Obtenir une clé Gemini (2 min)
Allez sur [Google AI Studio](https://aistudio.google.com/apikey) et créez une clé API.

### 2️⃣ Configurer la clé (1 min)
**Option A (Simple)** : Éditez `config.json` :
```json
{
  "gemini_api_key": "AIzaSy..."
}
```

**Option B (Sécurisé)** : Variable d'env :
```bash
export GEMINI_API_KEY="AIzaSy..."
```

### 3️⃣ Tester (30 sec)
```bash
source venv/bin/activate
python3 test_gemini.py
```

### 4️⃣ Utiliser (même qu'avant)
```bash
python3 app.py run --name "ma_video" --duration 120
```

## 📦 Fichiers modifiés

```
app.py                  ← Code principal (Whisper + Gemini)
config.json             ← Nouvelle config Gemini
test_gemini.py          ← Test API Gemini
SETUP_GEMINI.md         ← Guide complet configuration
V1.9_CHANGES.md         ← Détails techniques
venv/                   ← Nouvel environnement Python isolé
```

## 📋 Configuration complète

Voir **[SETUP_GEMINI.md](SETUP_GEMINI.md)** pour :
- ✅ Obtenir une clé API valide
- ✅ Tester la configuration
- ✅ Dépannage
- ✅ Sécurité (ne pas committer la clé!)

## 🎯 Cas d'usage

### Avant V1.9 : Texte brut
```
[00:15 - 00:45] Aujourd'hui on parle du machine learning...
[00:45 - 01:30] Le machine learning c'est...
[01:30 - 02:00] Il y a trois types...
```

### Après V1.9 : Enrichi avec contexte
```markdown
---
type: transcription_video
summary: Discussion sur le machine learning et ses 3 types
keywords: machine learning, deep learning, réseau neuronal
sentiment: neutre
---

## Résumé
Discussion sur le machine learning et ses 3 types...

## Transcription nettoyée
Aujourd'hui on parle du machine learning...
```

## ⚡ Performance

| Étape | Durée | Où |
|---|---|---|
| Enregistrement | Variable | Local (GPU/CPU) |
| Transcription Whisper | ~30s/10min audio | GPU local |
| Enrichissement Gemini | ~5-10s | Cloud Google |
| **Total** | ~40s/10min | Mixte |

## 💰 Coûts

✅ **Gratuit** jusqu'à 1M tokens/jour (Gemini Flash)
- ~1000 transcriptions/jour sans frais

Voir [Pricing Gemini](https://ai.google.dev/pricing)

## ⚙️ Options avancées

### Désactiver Gemini temporairement
```json
{
  "enable_gemini_enrichment": false
}
```

### Force une langue spécifique
```bash
python3 app.py run --name "test" --language en
```

### Utiliser avec Obsidian
```bash
python3 app.py run \
  --name "ma_video" \
  --obsidian-dir "/path/to/vault" \
  --obsidian-subdir "00_INBOX"
```

## 🛡️ Sécurité Important

⚠️ **Ne pas committer** `config.json` avec clé API!

```bash
echo "config.json" >> .gitignore
git rm --cached config.json
```

Utilisez plutôt une variable d'env :
```bash
export GEMINI_API_KEY="..."
```

## 📞 Support

- **Bug?** Consultez [SETUP_GEMINI.md](SETUP_GEMINI.md) section Dépannage
- **Questions API Gemini?** [Documentation Google AI](https://ai.google.dev)
- **Code principal?** [V1.9_CHANGES.md](V1.9_CHANGES.md)

## 📝 Changelog V1.9

```
✨ Nouvelle fonction init_gemini() pour configuration
✨ Nouvelle fonction enrich_with_gemini() pour enrichissement
✨ Support complet frontmatter YAML enrichi
✨ Variable d'env GEMINI_API_KEY
✨ Env Python isolé avec venv/
🔄 Migration vers nouveau SDK google-genai
📚 Documentation setup et dépannage
🧪 Script test_gemini.py inclus
```

## 🔄 Backward Compatibility

✅ Fonctionne sans clé Gemini (enrichissement sauté)
✅ Même format export (MD/TXT/JSON)
✅ Même commandes CLI
✅ Whisper inchangé

## 🎓 Prochaines étapes

1. [Configurer Gemini](SETUP_GEMINI.md) (5 min)
2. Tester avec `python3 test_gemini.py`
3. Utiliser normalement : `python3 app.py run --name "test"`
4. Profiter de transcriptions enrichies! 🚀

---

**Version** : V1.9 Gemini Edition  
**Stabilité** : ✅ Production Ready  
**License** : Projet local  
**Dernière MAJ** : 2026-06-27
