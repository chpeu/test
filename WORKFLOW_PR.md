# 🔄 Workflow Pull Request (PR) - Trade Cursor v7.0

## 📋 Processus Standard

### 1. Créer une Branche

```bash
# Depuis master (toujours à jour)
git checkout master
git pull origin master

# Créer une nouvelle branche
git checkout -b feat/nom-de-la-fonctionnalite
# ou
git checkout -b fix/nom-du-bug
# ou
git checkout -b docs/nom-du-doc
```

**Conventions de nommage** :
- `feat/` : Nouvelles fonctionnalités
- `fix/` : Corrections de bugs
- `docs/` : Documentation
- `refactor/` : Refactoring
- `style/` : Changements de style (CSS, formatage)
- `test/` : Ajout de tests

**Exemples** :
- `feat/style-port5000-onglets`
- `fix/build-production-error`
- `docs/deployment-guide`
- `refactor/scanner-module`

---

### 2. Développer et Commiter

```bash
# Faire vos modifications
# ...

# Ajouter les fichiers modifiés
git add .

# Commiter avec un message clair
git commit -m "feat: Description de la fonctionnalité

- Détail 1
- Détail 2
- Détail 3"

# Répéter pour plusieurs commits si nécessaire
```

**Format des messages de commit** :
```
type: Description courte (50 caractères max)

Description détaillée (optionnelle)
- Point 1
- Point 2
```

**Types** :
- `feat:` Nouvelle fonctionnalité
- `fix:` Correction de bug
- `docs:` Documentation
- `style:` Formatage, CSS
- `refactor:` Refactoring
- `test:` Tests
- `chore:` Maintenance

---

### 3. Pousser la Branche

```bash
# Premier push (créer la branche distante)
git push -u origin feat/nom-de-la-fonctionnalite

# Pushes suivants
git push
```

---

### 4. Créer la Pull Request sur GitHub

**Option A : Via le lien GitHub**
```
https://github.com/chpeu/trade_cursor_py/pull/new/feat/nom-de-la-fonctionnalite
```

**Option B : Via GitHub CLI** (si installé)
```bash
gh pr create --title "feat: Description" --body "Détails de la PR"
```

**Option C : Via l'interface GitHub**
1. Aller sur https://github.com/chpeu/trade_cursor_py
2. Cliquer sur "Pull requests"
3. Cliquer sur "New pull request"
4. Sélectionner votre branche
5. Remplir le titre et la description

---

### 5. Template de Description PR

```markdown
## 📋 Description

Brève description de ce que fait cette PR.

## 🎯 Type de changement

- [ ] Nouvelle fonctionnalité
- [ ] Correction de bug
- [ ] Amélioration de performance
- [ ] Refactoring
- [ ] Documentation
- [ ] Style/CSS

## ✅ Checklist

- [ ] Code testé localement
- [ ] Build production réussi (`npm run build`)
- [ ] Pas d'erreurs de linting
- [ ] Documentation mise à jour si nécessaire
- [ ] Tests passent (si applicable)

## 📸 Screenshots (si applicable)

## 🔗 Issues liées

Closes #123

## 📝 Notes additionnelles

Toute information supplémentaire pertinente.
```

---

### 6. Review et Merge

**Processus** :
1. **Review** : Attendre la review (auto-review ou manuelle)
2. **Corrections** : Si des changements sont demandés, faire des commits supplémentaires
3. **Approbation** : Une fois approuvée, la PR peut être mergée
4. **Merge** : Merge sur `master` (ou `develop` selon votre workflow)

**Commandes utiles** :
```bash
# Mettre à jour la branche avec master
git checkout master
git pull origin master
git checkout feat/nom-de-la-fonctionnalite
git merge master  # ou git rebase master

# Après merge, supprimer la branche locale
git checkout master
git pull origin master
git branch -d feat/nom-de-la-fonctionnalite
```

---

## 🚀 Workflow Rapide (Résumé)

```bash
# 1. Créer branche
git checkout master
git pull origin master
git checkout -b feat/ma-fonctionnalite

# 2. Développer
# ... faire vos modifications ...

# 3. Commiter
git add .
git commit -m "feat: Ma fonctionnalité"

# 4. Pousser
git push -u origin feat/ma-fonctionnalite

# 5. Créer PR sur GitHub
# Aller sur: https://github.com/chpeu/trade_cursor_py/pull/new/feat/ma-fonctionnalite
```

---

## 📝 Exemples Concrets

### Exemple 1 : Nouvelle Fonctionnalité

```bash
git checkout master
git pull origin master
git checkout -b feat/dark-mode-toggle

# ... modifications ...

git add .
git commit -m "feat: Ajout toggle dark/light mode

- Ajout composant ThemeToggle
- Intégration dans header
- Persistance préférence localStorage"

git push -u origin feat/dark-mode-toggle
```

### Exemple 2 : Correction Bug

```bash
git checkout master
git pull origin master
git checkout -b fix/websocket-reconnection

# ... corrections ...

git add .
git commit -m "fix: Correction reconnexion WebSocket

- Ajout retry logic
- Gestion erreurs améliorée
- Logs détaillés"

git push -u origin fix/websocket-reconnection
```

---

## ⚠️ Bonnes Pratiques

1. **Toujours partir de master à jour**
   ```bash
   git checkout master
   git pull origin master
   ```

2. **Une PR = Une fonctionnalité**
   - Éviter les PRs trop grandes
   - Séparer les fonctionnalités indépendantes

3. **Messages de commit clairs**
   - Utiliser le format conventionnel
   - Décrire le "quoi" et le "pourquoi"

4. **Tester avant de pousser**
   ```bash
   # Frontend
   cd frontend
   npm run build
   npm run preview
   
   # Backend
   python main.py
   ```

5. **Garder la branche à jour**
   ```bash
   # Si master a évolué pendant votre développement
   git checkout master
   git pull origin master
   git checkout feat/ma-branche
   git merge master
   ```

---

## 🔄 Workflow Actuel vs Recommandé

### ❌ Ancien Workflow (direct sur master)
```bash
git checkout master
git add .
git commit -m "feat: ..."
git push origin master
```

### ✅ Nouveau Workflow (avec PR)
```bash
git checkout master
git pull origin master
git checkout -b feat/...
# ... modifications ...
git add .
git commit -m "feat: ..."
git push -u origin feat/...
# Créer PR sur GitHub
```

---

## 📚 Ressources

- [GitHub Flow](https://guides.github.com/introduction/flow/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Git Branching](https://git-scm.com/book/en/v2/Git-Branching-Branching-Workflows)

---

**Dernière mise à jour** : 2025-11-08  
**Statut** : ✅ Workflow actif

