# 💾 GUIDE GIT PRATIQUE - Trade Cursor v6.0

**Git est maintenant configuré et initialisé!** ✅

---

## ✅ CE QUI EST DÉJÀ FAIT

- ✅ Repository Git initialisé
- ✅ Premier commit créé (Version initiale v6.0)
- ✅ `.gitignore` configuré (évite `.pyc`, `__pycache__`, etc.)

---

## 🚀 UTILISATION QUOTIDIENNE

### **1. VOIR L'HISTORIQUE**

```bash
git log
```

Affiche tous les commits avec messages.

**Version courte**:
```bash
git log --oneline
```

---

### **2. AVANT CHAQUE MODIFICATION**

**SAUVEGARDE** (important!)

```bash
git add .
git commit -m "Sauvegarde avant [nom de ta modification]"
```

**Exemple**:
```bash
git add .
git commit -m "Sauvegarde avant ajout feature smart_tp_sl"
```

**Pourquoi?** Pour pouvoir revenir en arrière si bug!

---

### **3. APRÈS MODIFICATION**

**Si ça fonctionne**:
```bash
git add .
git commit -m "Ajout feature smart_tp_sl - OK"
```

**Si ça bug**:
```bash
# Revenir en arrière
git reset --hard HEAD~1
```

**Explication**: `HEAD~1` = un commit avant le dernier

---

### **4. REVENIR À UNE VERSION SPÉCIFIQUE**

**Étape 1**: Voir l'historique
```bash
git log --oneline
```

**Exemple sortie**:
```
abc123f Ajout feature smart_tp_sl - OK
def456g Sauvegarde avant ajout feature smart_tp_sl
ghi789h Version initiale v6.0
```

**Étape 2**: Revenir à un commit
```bash
git checkout abc123f
```

**Revenir au dernier commit**:
```bash
git checkout master
```

---

## 📋 WORKFLOW COMPLET EXEMPLE

```bash
# 1. Tu veux ajouter une feature "position sizing"

# 2. SAUVEGARDE AVANT
git add .
git commit -m "Sauvegarde avant ajout position sizing"

# 3. Tu modifies position_manager.py
# ... ton code ...

# 4. Tu testes
python main.py

# 5. ÇA BUG!
# Revenir en arrière
git reset --hard HEAD~1

# 6. Tu corriges et ça marche
git add .
git commit -m "Ajout position sizing - OK"
```

---

## 🎯 COMMANDES ESSENTIELLES

### **Statut**
```bash
git status
```
Voir ce qui a changé

### **Voir l'historique**
```bash
git log --oneline
```
Liste des commits

### **Sauvegarder**
```bash
git add .
git commit -m "Ton message"
```

### **Revenir en arrière**
```bash
git reset --hard HEAD~1
```

### **Revenir à un commit spécifique**
```bash
git checkout <commit_hash>
```

### **Voir les différences**
```bash
git diff
```
Voir ce qui a changé avant commit

---

## 🔍 EXEMPLES CONCRETS

### **Exemple 1: Ajouter une feature**
```bash
# Sauvegarder
git add .
git commit -m "Sauvegarde avant ajout volume filter"

# Modifier
# ... code ...

# Tester, bug!
# Annuler
git reset --hard HEAD~1

# Corriger, marche!
git add .
git commit -m "Ajout volume filter - OK"
```

### **Exemple 2: Corriger un bug**
```bash
# Sauvegarder
git add .
git commit -m "Sauvegarde avant fix bug ATR"

# Corriger le bug
# ... fix ...

# Commit
git add .
git commit -m "Fix bug ATR calcul"
```

### **Exemple 3: Voir l'historique complet**
```bash
git log --oneline

# Sortie:
# abc123f Fix bug ATR calcul
# def456g Sauvegarde avant fix bug ATR
# ghi789h Ajout volume filter - OK
# jkl012i Sauvegarde avant ajout volume filter
# mno345p Version initiale v6.0

# Revenir à "Ajout volume filter"
git checkout ghi789h

# Revenir au présent
git checkout master
```

---

## ⚠️ COMMANDES DANGEREUSES

**NE PAS UTILISER** sans savoir ce qu'on fait:

```bash
git reset --hard  # Efface tout!
git clean -fd     # Supprime fichiers non trackés
```

**À EVITER**:
- `reset` sans garder de backup
- Commit messages vides

---

## 💡 CONSEILS

### **1. Commiter souvent**
- Avant chaque grosse modif
- Après chaque feature qui marche
- Ne pas attendre plusieurs jours

### **2. Messages clairs**
**❌ Mauvais**:
```bash
git commit -m "fix"
git commit -m "update"
```

**✅ Bon**:
```bash
git commit -m "Sauvegarde avant ajout smart TP/SL"
git commit -m "Ajout smart TP/SL - ATR adaptatif"
git commit -m "Fix bug calcul RSI sur timeframe court"
```

### **3. Voir l'historique régulièrement**
```bash
git log --oneline
```
Comprendre où on en est

### **4. Tester avant de commit**
```bash
python main.py  # Tester d'abord!
# Si OK, commiter
```

---

## 🎯 RÉSUMÉ ULTRA-SIMPLE

**Avant chaque modif**:
```bash
git add .
git commit -m "Sauvegarde avant [nom]"
```

**Si ça bug**:
```bash
git reset --hard HEAD~1
```

**Si ça marche**:
```bash
git add .
git commit -m "[nom] - OK"
```

**Voir l'historique**:
```bash
git log --oneline
```

---

## ✅ C'EST TOUT!

**Git est maintenant ton système de sauvegarde.**

**Tu peux modifier tranquille, tu auras toujours un retour en arrière!**

---

## 📞 AIDE

**Problèmes courants**:

**"nothing to commit"**:
- Rien n'a changé, c'est normal!

**"unmerged paths"**:
- Conflit Git, rare pour usage solo

**"not a git repository"**:
- Tu n'es pas dans `trade_cursor_py/`, faire `cd trade_cursor_py`

---

**Git est prêt! Utilise-le pour toutes tes modifications!** ✅




