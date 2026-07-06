# Transcripteur Local

## 1. Objectif

Transcripteur Local est un outil Python permettant de capturer l’audio système d’un ordinateur Ubuntu, puis de le transcrire automatiquement en texte avec Faster-Whisper.

L’outil est conçu pour transformer une vidéo, un live, une conférence ou un contenu audio lu sur l’ordinateur en fichiers exploitables :

* Markdown pour Obsidian ;
* TXT pour lecture simple ;
* JSON pour traitement automatisé futur.

## 2. Fonctionnalités actuelles

* Capture de l’audio système via FFmpeg.
* Détection automatique de la source audio par défaut.
* Enregistrement avec durée fixe.
* Enregistrement manuel avec arrêt par `CTRL+C`.
* Transcription locale avec Faster-Whisper.
* Utilisation GPU CUDA si disponible.
* Fallback CPU prévu.
* Export multi-format :

  * Markdown ;
  * TXT ;
  * JSON.
* Commande de vérification de l’environnement.
* Lanceur simplifié `./transcripteur`.

## 3. Environnement validé

Projet testé sur :

* Ubuntu 26.04 LTS ;
* FFmpeg 8.0.1 ;
* Python 3.14.4 ;
* NVIDIA RTX A1000 6GB Laptop GPU ;
* CTranslate2 CUDA détecté ;
* PipeWire/PulseAudio via `pactl`.

## 4. Structure du projet

```text
transcripteur-local/
  app.py
  transcripteur
  requirements.txt
  captures/
  transcriptions/
    markdown/
    txt/
    json/
  logs/
  .venv/
```

## 5. Installation

Créer l’environnement virtuel :

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Installer les dépendances :

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Vérifier que les outils système sont installés :

```bash
sudo apt update
sudo apt install -y ffmpeg pulseaudio-utils pavucontrol
```

## 6. Vérification de l’environnement

```bash
./transcripteur check
```

Résultat attendu :

```text
[OK] Python
[OK] FFmpeg
[OK] pactl
[OK] Source monitor
[OK] NVIDIA
[OK] CTranslate2 CUDA
```

## 7. Lister les sources audio

```bash
./transcripteur sources
```

Cette commande affiche les sorties et sources audio disponibles.

La source utilisée pour capturer le son système est généralement une source de type :

```text
nom_de_sortie_audio.monitor
```

## 8. Enregistrer avec une durée fixe

Exemple : enregistrer 5 minutes.

```bash
./transcripteur record --name video_5min --duration 300
```

Le fichier audio sera créé dans :

```text
captures/video_5min.wav
```

## 9. Enregistrer manuellement

```bash
./transcripteur record --name video_libre
```

Pour arrêter l’enregistrement :

```text
CTRL+C
```

Appuyer une seule fois sur `CTRL+C` afin de laisser FFmpeg fermer correctement le fichier WAV.

## 10. Transcrire un fichier existant

```bash
./transcripteur transcribe --file captures/video_libre.wav
```

## 11. Enregistrer et transcrire automatiquement

Avec durée fixe :

```bash
./transcripteur run --name video_test --duration 300
```

Sans durée fixe, avec arrêt manuel :

```bash
./transcripteur run --name video_test
```

Puis arrêter avec :

```text
CTRL+C
```

## 12. Forcer le périphérique de calcul

Mode automatique, recommandé :

```bash
./transcripteur run --name test --duration 300 --device auto
```

Forcer le GPU CUDA :

```bash
./transcripteur run --name test --duration 300 --device cuda
```

Forcer le CPU :

```bash
./transcripteur run --name test --duration 300 --device cpu
```

## 13. Choisir le modèle Whisper

Modèle par défaut :

```text
small
```

Exemples :

```bash
./transcripteur run --name test_base --duration 300 --model base
./transcripteur run --name test_small --duration 300 --model small
./transcripteur run --name test_medium --duration 300 --model medium
```

Recommandation actuelle :

* `base` : rapide, qualité moyenne ;
* `small` : bon compromis ;
* `medium` : meilleure qualité, plus lourd ;
* `large` : non recommandé sur GPU 6 Go pour l’instant.

## 14. Sorties générées

Pour une commande :

```bash
./transcripteur run --name exemple --duration 300
```

Les fichiers générés sont :

```text
captures/exemple.wav
transcriptions/markdown/exemple.md
transcriptions/txt/exemple.txt
transcriptions/json/exemple.json
```

## 15. Supprimer l’audio après transcription

```bash
./transcripteur run --name exemple --duration 300 --delete-audio
```

Cette option supprime le fichier WAV après génération des transcriptions.

À utiliser uniquement lorsque la transcription est validée.

## 16. Afficher les logs FFmpeg détaillés

```bash
./transcripteur run --name debug --duration 30 --verbose
```

## 17. Limites connues

* La qualité dépend fortement de l’audio source.
* Les noms propres, acronymes, anglicismes et termes techniques peuvent être mal transcrits.
* Le modèle `small` est rapide, mais imparfait.
* Les longues vidéos doivent être testées progressivement.
* L’enregistrement de réunions ou conversations privées doit respecter les règles de consentement et de confidentialité.
* Le projet ne fait pas encore de résumé automatique.
* Le projet ne fait pas encore d’intégration directe dans un vault Obsidian.

## 18. État du projet

Version actuelle : V1.5B

Fonctions validées :

* capture audio système ;
* transcription GPU ;
* export Markdown/TXT/JSON ;
* mode manuel ;
* mode durée fixe ;
* commande `check` ;
* lanceur `./transcripteur`.

## 19. Roadmap courte

Prochaines étapes possibles :

1. Export direct vers un dossier Obsidian.
2. Nettoyage automatique de la transcription.
3. Test du modèle `medium`.
4. Segmentation longue durée.
5. Résumé automatique.
6. Interface graphique simple.
