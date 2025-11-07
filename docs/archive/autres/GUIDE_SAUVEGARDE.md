# 💾 GUIDE: SAUVEGARDE & VERSIONS

**Question**: "Comment garder une sauvegarde entre chaque modif pour revenir en arrière?"

---

## 🎯 PROBLÈME

**Modifier le code = Risque de bug = Pas de retour en arrière possible**

---

## ✅ SOLUTION 1: Git (Recommandé ⭐⭐⭐⭐⭐)

### **Initialiser Git**:
```bash
cd trade_cursor_py
git init
git add .
git commit -m "Version de base v6.0"
```

### **Avant chaque modif**:
```bash
git add .
git commit -m "Sauvegarde avant modif X"
```

### **Après modif**:
```bash
git add .
git commit -m "Modification: amélioration Y"
```

### **Revenir en arrière**:
```bash
# Voir l'historique
git log --oneline

# Revenir à une version spécifique
git checkout <commit_hash>

# Revenir à la dernière sauvegarde
git checkout HEAD~1
```

### **Exemple workflow**:
```bash
# Travail normal
git commit -m "Sauvegarde avant ajout feature X"

# Tu ajoutes une feature
# ... modifie du code ...

# Tu testes, ça bug
# Revenir en arrière:
git reset --hard HEAD~1

# Ou revenir à une version spécifique:
git checkout abc123f
```

**Avantages**:
- ✅ Historique complet
- ✅ Retour en arrière facile
- ✅ Comparaison versions
- ✅ Gratuit
- ✅ Standard professionnel

---

## ✅ SOLUTION 2: Copie de Dossiers (Simple ⭐⭐⭐)

### **Avant chaque modif**:
```bash
# Copier le dossier
cp -r trade_cursor_py trade_cursor_py_backup_2025-11-02_avant_feature_X
```

### **Après modif, si bug**:
```bash
# Supprimer le dossier bugué
rm -rf trade_cursor_py

# Copier la sauvegarde
cp -r trade_cursor_py_backup_2025-11-02_avant_feature_X trade_cursor_py
```

**Avantages**:
- ✅ Simple
- ✅ Compréhensible

**Inconvénients**:
- ❌ Prend beaucoup d'espace
- ❌ Pas de comparaison
- ❌ Manuel

---

## ✅ SOLUTION 3: Script Backup Auto (Automatisé ⭐⭐⭐⭐)

### **Créer `backup.bat` (Windows)**:
```batch
@echo off
setlocal enabledelayedexpansion

:: Créer dossier backups si inexistant
if not exist "..\backups" mkdir "..\backups"

:: Générer nom de backup
set "timestamp=%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "timestamp=!timestamp: =0!"
set "backup_folder=..\backups\trade_cursor_py_!timestamp!"

:: Copier le dossier
xcopy /E /I /Y "trade_cursor_py" "!backup_folder!"

echo ✅ Sauvegarde creee: !backup_folder!
```

### **Créer `backup.sh` (Linux/Mac)**:
```bash
#!/bin/bash
BACKUP_DIR="../backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FOLDER="$BACKUP_DIR/trade_cursor_py_$TIMESTAMP"

mkdir -p "$BACKUP_DIR"
cp -r trade_cursor_py "$BACKUP_FOLDER"

echo "✅ Sauvegarde créée: $BACKUP_FOLDER"
```

### **Usage**:
```bash
# Avant chaque modif
backup.bat
# Puis modifier le code
```

**Avantages**:
- ✅ Automatique
- ✅ Timestamp
- ✅ Rapide

---

## ✅ SOLUTION 4: Git + Hooks Auto (Meilleur ⭐⭐⭐⭐⭐)

### **Setup**:
```bash
cd trade_cursor_py
git init
git add .
git commit -m "Version initiale v6.0"
```

### **Créer `.git/hooks/pre-commit`**:
```bash
#!/bin/bash
# Auto-commit avant chaque modification
git add .
git commit -m "Auto-save: $(date +'%Y-%m-%d %H:%M:%S')"
```

### **Créer `.git/hooks/post-commit`**:
```bash
#!/bin/bash
# Créer une copie de sauvegarde après chaque commit
BACKUP_DIR="../../backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FOLDER="$BACKUP_DIR/trade_cursor_py_$TIMESTAMP"

mkdir -p "$BACKUP_DIR"
cp -r . "$BACKUP_FOLDER"

echo "✅ Backup créé: $BACKUP_FOLDER"
```

**Résultat**: Chaque modification = auto-commit + auto-backup!

---

## 🎯 SOLUTION RECOMMANDÉE: Git Simple

### **Setup initial** (une seule fois):
```bash
cd trade_cursor_py
git init
git add .
git commit -m "Version initiale v6.0 fonctionnelle"
```

### **Workflow quotidien**:
```bash
# 1. Avant modifier le code
git add .
git commit -m "Sauvegarde avant [nom de la modif]"

# 2. Modifier le code
# ... tes modifications ...

# 3. Si ça bug, revenir en arrière
git reset --hard HEAD~1

# 4. Si ça marche, commiter
git add .
git commit -m "Ajout [nom de la modif]"
```

---

## 📋 EXEMPLE PRATIQUE

```bash
# Tu veux ajouter une feature "smart_tp_sl"

# 1. Sauvegarder
git add .
git commit -m "Sauvegarde avant ajout smart_tp_sl"

# 2. Modifier position_manager.py
# ... ajoutes la feature ...

# 3. Tester
python main.py

# 4. Ça bug!
# Revenir en arrière
git reset --hard HEAD~1

# 5. Ou si ça marche
git add .
git commit -m "Ajout smart_tp_sl - fonctionne!"
```

---

## 🎯 RECOMMANDATION FINALE

**Pour toi, je recommande**: **Git Simple**

**Pourquoi?**:
- ✅ Gratuit
- ✅ Standard
- ✅ Puissant
- ✅ Professionnel
- ✅ Pas complexe pour usage basique

**Setup maintenant?** Je peux t'aider à initialiser Git si tu veux!

---

**Quelle solution tu préfères?**






