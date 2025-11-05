# 📋 RÉPONSES RAPIDES

---

## ❓ Question 1: "Comment lancer plusieurs instances?"

### ✅ **RÉPONSE**: Modifier le port

**Option Simple**:
```bash
# Terminal 1
python main.py 5000

# Terminal 2  
python main.py 5001

# Terminal 3
python main.py 5002
```

**Détails**: Voir `GUIDE_INSTANCES_MULTIPLES.md`

---

## ❓ Question 2: "Comment faire pour toujours garder une sauvegarde?"

### ✅ **RÉPONSE**: Utiliser Git

**Setup** (une seule fois):
```bash
cd trade_cursor_py
git init
git add .
git commit -m "Version initiale"
```

**Avant chaque modif**:
```bash
git add .
git commit -m "Sauvegarde avant [nom modif]"
```

**Après modif, si bug**:
```bash
git reset --hard HEAD~1  # Retour en arrière
```

**Détails**: Voir `GUIDE_SAUVEGARDE.md`

---

## 🎯 RECOMMANDATION

**Les deux guides sont créés dans `trade_cursor_py/`:**
- ✅ `GUIDE_INSTANCES_MULTIPLES.md` - Multiples instances
- ✅ `GUIDE_SAUVEGARDE.md` - Système de sauvegarde

**Tu veux que j'implémente ces solutions maintenant?**





