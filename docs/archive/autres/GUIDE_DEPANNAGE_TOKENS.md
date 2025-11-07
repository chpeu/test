# 🔧 Guide de Dépannage : Tokens Telegram ne se chargent pas

## ⚠️ Symptôme

Les tokens Telegram sauvegardés via `/settings` ne se chargent pas au redémarrage du bot.

---

## 🔍 Diagnostic

### Étape 1 : Vérifier que python-dotenv est installé

```bash
pip list | grep python-dotenv
```

**Si pas installé** :
```bash
pip install python-dotenv
```

---

### Étape 2 : Vérifier que le fichier .env existe

Le fichier `.env` doit être à la **racine du projet** :

```
trade_cursor_py/
├── .env          ← Ici (même niveau que main.py)
├── main.py
├── config.py
├── core/
└── ...
```

**Vérifier** :
```bash
# Windows PowerShell
Test-Path .env

# Linux/Mac
ls -la .env
```

---

### Étape 3 : Vérifier le contenu du fichier .env

Le fichier `.env` doit contenir :

```bash
# .env
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

**⚠️ Important** :
- Pas d'espaces autour du `=`
- Pas de guillemets (sauf si nécessaire)
- Une ligne par variable

---

### Étape 4 : Vérifier que .env est dans .gitignore

Le fichier `.env` ne doit **PAS** être commité dans Git :

```bash
# .gitignore
.env
*.env
```

**Vérifier** :
```bash
git check-ignore .env
# Doit retourner : .env
```

---

### Étape 5 : Tester le chargement manuellement

**Dans Python** :
```python
from dotenv import load_dotenv
import os

# Charger .env
load_dotenv()

# Vérifier les variables
print("Token:", os.getenv("TELEGRAM_BOT_TOKEN"))
print("Chat ID:", os.getenv("TELEGRAM_CHAT_ID"))
```

**Si `None`** : Le fichier `.env` n'est pas lu correctement.

---

### Étape 6 : Vérifier le chemin du fichier .env

Par défaut, `load_dotenv()` cherche `.env` dans le **répertoire courant**.

**Si le bot est lancé depuis un autre répertoire** :

```python
# Dans config.py (déjà fait)
from dotenv import load_dotenv
from pathlib import Path

# Charger depuis la racine du projet
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)
```

---

## 🔧 Solutions

### Solution 1 : Réinstaller python-dotenv

```bash
pip uninstall python-dotenv
pip install python-dotenv
```

---

### Solution 2 : Créer le fichier .env manuellement

**Windows PowerShell** :
```powershell
# Créer fichier .env
@"
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
"@ | Out-File -FilePath .env -Encoding utf8
```

**Linux/Mac** :
```bash
cat > .env << EOF
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
EOF
```

---

### Solution 3 : Utiliser variables d'environnement système

**Au lieu de `.env`**, utiliser les variables d'environnement système :

**Windows PowerShell** :
```powershell
$env:TELEGRAM_BOT_TOKEN="123456789:ABC-DEF..."
$env:TELEGRAM_CHAT_ID="123456789"
python main.py
```

**Linux/Mac** :
```bash
export TELEGRAM_BOT_TOKEN="123456789:ABC-DEF..."
export TELEGRAM_CHAT_ID="123456789"
python main.py
```

---

### Solution 4 : Vérifier les permissions du fichier .env

**Windows** : Vérifier que le fichier n'est pas en lecture seule.

**Linux/Mac** :
```bash
chmod 644 .env
```

---

## 🧪 Test complet

### 1. Créer fichier .env
```bash
# .env
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

### 2. Tester chargement
```python
from dotenv import load_dotenv
import os
load_dotenv()
print(os.getenv("TELEGRAM_BOT_TOKEN"))
```

### 3. Redémarrer le bot
```bash
python main.py
```

### 4. Vérifier dans les logs
```
📱 Notification Manager initialisé (Telegram activé)
```

**Si "Telegram désactivé"** : Les tokens ne sont pas chargés.

---

## 📋 Checklist

- [ ] `python-dotenv` installé (`pip install python-dotenv`)
- [ ] Fichier `.env` existe à la racine
- [ ] Fichier `.env` contient `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`
- [ ] Pas d'espaces autour du `=` dans `.env`
- [ ] Fichier `.env` dans `.gitignore`
- [ ] Bot lancé depuis le répertoire racine
- [ ] Test manuel de chargement fonctionne

---

## 🆘 Si rien ne fonctionne

1. **Vérifier les logs au démarrage** :
   ```
   📱 Notification Manager initialisé (Telegram activé)
   ```
   ou
   ```
   📱 Notification Manager initialisé (Telegram désactivé)
   ```

2. **Utiliser variables d'environnement système** (Solution 3) au lieu de `.env`

3. **Vérifier que `config.py` charge bien `.env`** :
   ```python
   # Dans config.py (déjà fait)
   try:
       from dotenv import load_dotenv
       load_dotenv()
   except ImportError:
       pass
   ```

---

*Guide créé le 2025-11-07*

