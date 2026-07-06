# Configuration API Gemini pour Transcripteur V1.9

## 📋 Prérequis
- Compte Google gratuit
- Accès à Google AI Studio (gratuit)

## 🔑 Obtenir une clé API Gemini valide

### Option 1 : Google AI Studio (Gratuit, recommandé pour démarrer)

1. Allez sur [Google AI Studio](https://aistudio.google.com/apikey)
2. Cliquez sur **"Create API Key"** → **"Create API key in new project"**
3. Une clé API sera générée (commence par `AIza...`)
4. **Copiez-la**

### Option 2 : Google Cloud Console (Production)

1. Allez sur [Google Cloud Console](https://console.cloud.google.com)
2. Créez un nouveau projet
3. Activez l'API Generative AI
4. Créez une clé API (API Key)
5. Copiez-la

## ⚙️ Configuration du Transcripteur

### Méthode 1 : config.json (Simple)

```bash
# Éditez config.json
nano config.json
```

Remplissez la clé API :
```json
{
  "gemini_api_key": "AIzaSyCSMwvAJ_xgnKGr0QDL...",
  "enable_gemini_enrichment": true
}
```

Sauvegardez et quittez (Ctrl+X, Y, Enter).

### Méthode 2 : Variable d'environnement (Plus sécurisé)

```bash
export GEMINI_API_KEY="AIzaSyCSMwvAJ_xgnKGr0QDL..."
```

Ou ajoutez à votre `~/.bashrc` :
```bash
echo 'export GEMINI_API_KEY="AIzaSyCSMwvAJ_xgnKGr0QDL..."' >> ~/.bashrc
source ~/.bashrc
```

## 🧪 Test de la configuration

```bash
source venv/bin/activate
python3 test_gemini.py
```

Résultat attendu :
```
=== Gemini V1.9 API Test ===

[INFO] Testing Gemini API with key: AIzaSyCSMwvAJ_...
[OK] Gemini client initialized
[OK] API response received
[OK] JSON parsed successfully
[OK] Enrichment: {'summary': '...', 'keywords': [...], ...}

=== Test Result: PASSED ===
```

## ⚡ Utilisation

Une fois configuré, l'enrichissement Gemini s'exécute automatiquement :

```bash
source venv/bin/activate

# Enregistrement + transcription + enrichissement Gemini
python3 app.py run --name "ma_reunion" --duration 120

# Ou transcription d'un fichier existant
python3 app.py transcribe --file captures/ma_reunion.wav
```

## 🛡️ Sécurité

### ⚠️ Important
- **Ne pas committer** `config.json` avec clé API en Git
- Ajouter à `.gitignore` :
  ```
  config.json
  ```

### Meilleures pratiques
1. Préférez la variable d'env `GEMINI_API_KEY`
2. Ne partagez jamais votre clé API
3. Si compromise, régénérez-la dans Google AI Studio
4. Utilisez des permissions de clé API restrictives en production

## 💰 Coûts

### Modèle gratuit : Gemini 1.5 Flash
- **Limite gratuite** : 15 RPM (requêtes/minute), 1M tokens/jour
- **Tarification** : Gratuit jusqu'à 1M tokens/jour

### Estimation pour vos besoins
- Une transcription = ~500-1000 tokens Gemini
- 1M tokens = ~1000 transcriptions gratuites/jour ✅

Voir [Google AI Pricing](https://ai.google.dev/pricing)

## 🐛 Dépannage

### "API key not valid"
```
[FAIL] Error: 400 INVALID_ARGUMENT. API key not valid.
```

**Solutions** :
- Vérifier que la clé commence par `AIza`
- Régénérer une nouvelle clé dans Google AI Studio
- Attendre quelques minutes après création

### "enable_gemini_enrichment: false"
L'enrichissement Gemini est désactivé. Changez dans `config.json` :
```json
{
  "enable_gemini_enrichment": true
}
```

### Gemini échoue silencieusement
L'enrichissement est optionnel. Le pipeline continue :
```
[WARN] Enrichissement Gemini échoué, continuation sans
```
Vérifiez les logs et la clé API.

## 📚 Documentation complète

- [Gemini API Documentation](https://ai.google.dev)
- [Python SDK Reference](https://ai.google.dev/tutorials/python_quickstart)
- [API Quotas](https://ai.google.dev/quotas)

---

**Besoin d'aide ?** Consultez `V1.9_CHANGES.md` pour plus de détails sur V1.9.
