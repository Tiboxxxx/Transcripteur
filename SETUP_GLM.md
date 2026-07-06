# Configuration API GLM 5.2 pour Transcripteur V1.9

## 📋 Obtenir une clé API GLM 5.2

### Étape 1 : Créer un compte Zhipu AI
1. Allez sur https://open.bigmodel.cn
2. Cliquez sur **"登录/注册"** (Login/Register)
3. Créez un compte (email ou WeChat)

### Étape 2 : Obtenir la clé API
1. Une fois connecté, allez dans **"API钥匙"** (API Keys)
2. Cliquez sur **"+ 创建API钥匙"** (Create API Key)
3. Une clé sera générée (commence par `sk-...`)
4. **Copiez-la**

## ⚙️ Configuration du Transcripteur

### Méthode 1 : config.json (Simple)

```bash
nano config.json
```

Remplissez la clé API :
```json
{
  "glm_api_key": "sk-xxxxxxxxxxxxx",
  "enable_glm_enrichment": true
}
```

Sauvegardez (Ctrl+X, Y, Enter).

### Méthode 2 : Variable d'environnement (Plus sécurisé)

```bash
export GLM_API_KEY="sk-xxxxxxxxxxxxx"
```

Ou ajoutez à `~/.bashrc` :
```bash
echo 'export GLM_API_KEY="sk-xxxxxxxxxxxxx"' >> ~/.bashrc
source ~/.bashrc
```

## 🧪 Test de la configuration

```bash
cd /home/oneweb/projets/transcripteur-local
source venv/bin/activate
python3 << 'EOF'
import json
from zhipuai import ZhipuAI
from pathlib import Path

config = json.loads(Path("config.json").read_text())
api_key = config.get("glm_api_key") or os.getenv("GLM_API_KEY")

if not api_key:
    print("[FAIL] Pas de clé API GLM")
    exit(1)

try:
    client = ZhipuAI(api_key=api_key)
    response = client.chat.completions.create(
        model="glm-4-flash",
        messages=[{"role": "user", "content": "Bonjour!"}]
    )
    print("[OK] GLM API fonctionne!")
    print(f"Réponse: {response.choices[0].message.content[:50]}...")
except Exception as e:
    print(f"[FAIL] {e}")
EOF
```

## ⚡ Utilisation

Une fois configuré, l'enrichissement GLM s'exécute automatiquement :

```bash
source venv/bin/activate

# Enregistrement + transcription + enrichissement GLM
python3 app.py run --name "ma_video" --duration 120

# Ou transcription d'un fichier existant
python3 app.py transcribe --file captures/ma_video.wav
```

## 🛡️ Sécurité

### ⚠️ Important
- **Ne pas committer** `config.json` avec clé API en Git
- Ajouter à `.gitignore` :
  ```
  config.json
  ```

### Meilleures pratiques
1. Préférez la variable d'env `GLM_API_KEY`
2. Ne partagez jamais votre clé API
3. Si compromise, régénérez-la dans Zhipu AI
4. Utilisez des permissions de clé API restrictives

## 💰 Coûts

### Plan gratuit : GLM 4 Flash
- **Limite gratuite** : 2M tokens/mois
- **Tarification** : Gratuit pour usage personnel

### Estimation pour vos besoins
- Une transcription = ~500-1000 tokens GLM
- 2M tokens = ~2000 transcriptions gratuites/mois ✅

Voir [GLM Pricing](https://open.bigmodel.cn/pricing)

## 🐛 Dépannage

### "Aucune clé GLM API trouvée"
```
[WARN] Aucune clé GLM API trouvée (GLM_API_KEY env ou config.json)
```

**Solutions** :
- Vérifier que la clé commence par `sk-`
- Vérifier `config.json` > `glm_api_key` est remplie
- Ou définir `export GLM_API_KEY="sk-..."`

### "API key not valid"
- Vérifier que la clé commence par `sk-`
- Régénérer une nouvelle clé dans Zhipu AI
- Attendre quelques minutes après création

### "GLM 5.2 échoue silencieusement"
L'enrichissement est optionnel. Le pipeline continue :
```
[WARN] Enrichissement GLM 5.2 échoué, continuation sans
```
Vérifiez les logs et la clé API.

## 📚 Modèles disponibles

GLM offre plusieurs modèles :
- `glm-4-flash` : Fast, efficace (par défaut)
- `glm-4-plus` : Plus précis
- `glm-4-long-context` : Contexte long (128k tokens)

Vous pouvez changer le modèle dans `app.py` à la ligne avec `model="glm-4-flash"`

## 📞 Support

- **Documentation GLM** : https://open.bigmodel.cn/docs
- **API Reference** : https://open.bigmodel.cn/docs/api
- **Status Page** : https://open.bigmodel.cn/status

---

**Besoin d'aide ?** Consultez [README_V1.9.md](README_V1.9.md) pour plus de détails.
