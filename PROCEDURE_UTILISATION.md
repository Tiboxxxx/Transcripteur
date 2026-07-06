# 📋 Procédure d'utilisation - Transcripteur Local V1.9

## 🎯 Objectif
Enregistrer, transcrire et exporter automatiquement vos formations dans Obsidian en une seule commande.

---

## 🚀 Démarrage rapide

### Étape 1 : Ouvrir un terminal

Peu importe le répertoire où vous êtes.

### Étape 2 : Lancer l'enregistrement

```bash
transcriber "Titre de votre formation"
```

**Exemple:**
```bash
transcriber "Cours Python Avancé"
transcriber "Réunion Équipe - 27 juin"
transcriber "Tutoriel Django REST"
```

### Étape 3 : Enregistrer
- L'application va enregistrer l'audio du système
- **Appuyez sur CTRL+C une fois** quand vous avez fini
- Attendez la fin automatique (quelques secondes)

### Étape 4 : Vérifier dans Obsidian
- Allez dans votre vault Obsidian
- Dossier: **00_INBOX**
- Vous trouverez le fichier transcrit! ✅

---

## 📝 Détails du processus

### Qu'est-ce qui se passe automatiquement?

1. ✅ **Enregistrement audio** - Capture l'audio système (vos explications)
2. ✅ **Transcription Whisper** - Convertit audio → texte (local, gratuit)
3. ✅ **Création Markdown** - Génère un fichier formaté
4. ✅ **Export Obsidian** - Envoie dans votre vault
5. ✅ **Nettoyage** - Supprime le fichier audio (économise l'espace)

### Fichiers générés

Pour chaque enregistrement, vous obtenez:

```
transcriptions/
├── markdown/
│   └── "Titre de votre formation".md ← Celui-ci va dans Obsidian
├── txt/
│   └── "Titre de votre formation".txt
├── json/
│   └── "Titre de votre formation".json
└── captures/
    └── "Titre de votre formation".wav (SUPPRIMÉ après)
```

---

## ⚙️ Configuration

### Vérifier votre config

```bash
cat /home/oneweb/projets/transcripteur-local/config.json
```

**Paramètres importants:**

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| `obsidian_dir` | `/home/oneweb/Documents/MonVault` | Chemin vers votre vault |
| `obsidian_subdir` | `00_INBOX` | Dossier de destination |
| `default_device` | `cpu` | Utilise le CPU (pas GPU) |
| `enable_gemini_enrichment` | `false` | Enrichissement désactivé |

### Modifier la config

```bash
nano /home/oneweb/projets/transcripteur-local/config.json
```

Changez:
- `obsidian_dir` → Chemin réel de votre vault
- `obsidian_subdir` → Dossier où vous voulez les fichiers

---

## 🔧 Dépannage

### "La commande transcriber n'a pas été trouvée"

**Solution 1** - Utiliser le chemin complet:
```bash
/home/oneweb/projets/transcripteur-local/run_transcriber.sh "Titre"
```

**Solution 2** - Créer un alias temporaire (dans le terminal):
```bash
alias transcriber="/home/oneweb/projets/transcripteur-local/run_transcriber.sh"
transcriber "Titre"
```

**Solution 3** - Ajouter au ~/.bashrc permanent:
```bash
echo 'alias transcriber="/home/oneweb/projets/transcripteur-local/run_transcriber.sh"' >> ~/.bashrc
source ~/.bashrc
transcriber "Titre"
```

### "Fichier audio non trouvé"

Vérifiez que:
- ✅ FFmpeg est installé: `ffmpeg -version`
- ✅ Vous avez du son système (test: `pactl get-default-sink`)
- ✅ PulseAudio/PipeWire est actif

### "Obsidian ne reçoit pas le fichier"

Vérifiez dans config.json:
```bash
grep obsidian_dir /home/oneweb/projets/transcripteur-local/config.json
```

Le chemin doit être correct et le dossier doit exister.

### "FFmpeg library error"

Relancez le venv:
```bash
cd /home/oneweb/projets/transcripteur-local
source venv/bin/activate
python3 app.py run --name "Test" --duration 5
```

---

## 💡 Conseils d'utilisation

### Avant d'enregistrer
- Testez votre audio: `pactl list short sources`
- Vérifiez Obsidian est fermé ou synchronisé
- Donnez un titre unique à chaque formation

### Pendant l'enregistrement
- Parlez clairement et distinctement
- Évitez les bruits parasites
- L'enregistrement commence immédiatement

### Après l'enregistrement
- **Appuyez CTRL+C une fois** - le script arrête proprement
- Attendez 30-60 secondes (transcription + export)
- Vérifiez le fichier dans Obsidian

### Format du titre
```
✅ Bon: "Cours Python Avancé"
✅ Bon: "Réunion 27 juin 2026"
❌ Mauvais: "test" (trop vague)
❌ Mauvais: "Mon cours / avec des slashes" (problème de chemin)
```

---

## 🎓 Exemple complet

```bash
# Terminal 1 - Lancer l'enregistrement
transcriber "Machine Learning avec Python"

# [L'app affiche:]
# ==========================================
# 🎙️  TRANSCRIPTEUR LOCAL - FORMATION
# ==========================================
# 📝 Formation: Machine Learning avec Python
# 📍 Dossier Obsidian: /home/oneweb/Documents/MonVault
# 
# ⏱️  PRÊT À ENREGISTRER
#    • Appuyez sur CTRL+C une fois pour arrêter
#    • Le fichier sera transcrit automatiquement
#    • Puis envoyé dans Obsidian
#
# ⏳ Démarrage dans 3 secondes...

# [Enregistrement démarre... vous parlez pendant 5 minutes]

# [Vous appuyez sur CTRL+C]
# [La transcription se fait...]
# [20 secondes plus tard:]

# ==========================================
# ✅ TERMINÉ!
# 📁 Fichier sauvegardé dans Obsidian
# ==========================================

# Terminal 2 - Vérifier dans Obsidian
# → Allez dans Obsidian
# → Ouvrez le dossier 00_INBOX
# → Vous trouvez "Machine Learning avec Python.md" ✨
```

---

## 📞 Support rapide

| Problème | Commande à tester |
|----------|------------------|
| Vérifier l'audio | `pactl list short sources` |
| Tester le setup | `cd ~/projets/transcripteur-local && python3 app.py check` |
| Voir la config | `cat ~/projets/transcripteur-local/config.json` |
| Éditer la config | `nano ~/projets/transcripteur-local/config.json` |
| Voir les logs | `ls ~/projets/transcripteur-local/logs/` |

---

## 📚 Versions et modèles

**Version actuelle:** V1.9  
**Transcription:** Whisper (local, gratuit)  
**Enrichissement:** Désactivé (Gemini échoue sur ce compte)  
**Langue par défaut:** Français (fr)  
**Appareil:** CPU (mode compatible)

---

## ✨ C'est tout!

**À partir de maintenant:**

```bash
transcriber "Votre titre"
```

Et c'est automatique! 🚀

Vos formations sont transcrites, formatées et dans Obsidian en quelques secondes.

**Besoin d'aide?** Vérifiez la section "Dépannage" ci-dessus.
