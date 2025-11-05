# 💾 DÉMONSTRATION GIT - Comment ça marche

---

## 📊 ÉTAT ACTUEL

**Git est initialisé et configuré!** Voici ton historique:

```
dc670e5 Ajout support instances multiples + scripts lancement + guides pratiques
d0003cc Version initiale v6.0 - Interface HTML identique, instances multiples, sauvegarde Git
```

**2 commits** déjà créés! ✅

---

## 🎯 UTILISATION SIMPLE

### **SCÉNARIO 1: Tu veux ajouter une feature**

```bash
# 1. SAUVEGARDE AVANT (important!)
cd "C:\Users\sebta\Documents\code scalp\trade_cursor_py"
git add .
git commit -m "Sauvegarde avant ajout volume filter smart"

# 2. Tu modifies core/analyzer.py
# ... ton code ...

# 3. Tester
python main.py

# 4a. ÇA BUG? → Annuler
git reset --hard HEAD~1

# 4b. ÇA MARCHE? → Sauvegarder
git add .
git commit -m "Ajout volume filter smart - OK"
```

**Résultat**: Historique mise à jour!

---

### **SCÉNARIO 2: Revenir en arrière**

```bash
# 1. Voir l'historique
git log --oneline

# Sortie:
# abc123f Ajout volume filter smart - OK
# def456g Sauvegarde avant ajout volume filter smart
# dc670e5 Ajout support instances multiples
# d0003cc Version initiale v6.0

# 2. Revenir à la version initiale
git checkout d0003cc

# 3. Revenir au présent
git checkout master
```

---

### **SCÉNARIO 3: Voir les changements**

```bash
# Modifier un fichier
# Puis voir les différences
git diff

# Voir ce qui sera commité
git status
```

---

## 📋 COMMANDES ESSENTIELLES

| Commande | Usage |
|----------|-------|
| `git status` | Voir ce qui a changé |
| `git log --oneline` | Historique des commits |
| `git add .` | Ajouter tous changements |
| `git commit -m "msg"` | Sauvegarder avec message |
| `git reset --hard HEAD~1` | Revenir 1 commit en arrière |
| `git checkout <hash>` | Revenir à un commit spécifique |
| `git checkout master` | Revenir au dernier commit |

---

## 💡 CONSEILS

### **1. Commiter souvent**
**❌ Mauvais**: Commit 1x par semaine  
**✅ Bon**: Commit avant/après chaque feature

### **2. Messages clairs**
**❌ Mauvais**: `git commit -m "fix"`  
**✅ Bon**: `git commit -m "Fix bug calcul RSI timeout"`

### **3. Tester avant**
Toujours tester avant de commit une feature OK!

---

## 🎯 RÉSUMÉ

**Git = Time machine pour code**

- ✅ Avant modif: `git commit`
- ✅ Si bug: `git reset --hard HEAD~1`
- ✅ Si OK: `git commit`
- ✅ Voir histoire: `git log --oneline`

**Simple et puissant!**

---

**Tu peux maintenant modifier sans stress, tu as toujours un retour en arrière!** ✅




