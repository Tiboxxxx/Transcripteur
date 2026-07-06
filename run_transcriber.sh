#!/bin/bash

# Script de lancement simple pour Transcripteur Local
# Utilisation: ./run_transcriber.sh "Nom de ma formation"

set -e

if [ -z "$1" ]; then
    echo "❌ Usage: ./run_transcriber.sh \"Nom de votre formation\""
    echo "Exemple: ./run_transcriber.sh \"Cours Python Avancé\""
    exit 1
fi

FORMATION_NAME="$1"
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$PROJECT_DIR/venv"

# Vérifier et activer venv
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Venv non trouvé. Créez-le d'abord:"
    echo "   cd $PROJECT_DIR && python3 -m venv venv"
    exit 1
fi

source "$VENV_DIR/bin/activate"

echo "=========================================="
echo "🎙️  TRANSCRIPTEUR LOCAL - FORMATION"
echo "=========================================="
echo "📝 Formation: $FORMATION_NAME"
echo "📍 Dossier Obsidian: $(grep obsidian_dir $PROJECT_DIR/config.json | cut -d'"' -f4)"
echo ""
echo "⏱️  PRÊT À ENREGISTRER"
echo "   • Appuyez sur CTRL+C une fois pour arrêter"
echo "   • Le fichier sera transcrit automatiquement"
echo "   • Puis envoyé dans Obsidian"
echo ""
echo "⏳ Démarrage dans 3 secondes..."
sleep 3

cd "$PROJECT_DIR"
python3 app.py run \
    --name "$FORMATION_NAME" \
    --title "$FORMATION_NAME" \
    --domain "formation" \
    --delete-audio

echo ""
echo "=========================================="
echo "✅ TERMINÉ!"
echo "📁 Fichier sauvegardé dans Obsidian"
echo "=========================================="
