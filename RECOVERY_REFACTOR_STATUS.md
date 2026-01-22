# Recovery Mode Refactor — Statut

## ✅ Ce qui a été fait

### 1) Ajout d’un état Recovery unifié (RecoveryState)
- **Fichier** : `core/position/recovery_mode.py`
- **Ajouts** :
  - `RecoveryState` dataclass (snapshot structuré)
  - `RecoveryModeManager.get_state()` (aucune modification de logique)

### 2) Feature flags sécurisés (OFF par défaut)
- **Fichier** : `config.py`
- **Ajouts** :
  - `recovery_refactor_enabled` (bascule RecoveryState)
  - `recovery_shadow_compare` (logs de comparaison)

### 3) Shadow logging (comparaison legacy vs state)
- **Sizing** : `core/position_manager.py`
- **Gating** : `core/analyzer.py`
- Active uniquement si `recovery_shadow_compare=True`

### 4) Bascule Analyzer sous flag (safe fallback)
- **Fichier** : `core/analyzer.py`
- Si `recovery_refactor_enabled=True`, l’Analyzer lit RecoveryState
- Sinon, **fallback legacy** automatique

### 5) Bascule Sizing sous flag (safe fallback)
- **Fichier** : `core/position_manager.py`
- Si `recovery_refactor_enabled=True`, sizing utilise RecoveryState
- Sinon, **fallback legacy** automatique

---

## 🔒 Garanties sécurité
- **Comportement inchangé par défaut** (flags OFF)
- Fallback legacy si `RecoveryState` absent
- Logs de comparaison disponibles avant bascule

---

## ⏳ Ce qu’il reste à faire

### A) Vérification terrain (shadow compare)
1. Activer temporairement :
   ```python
   "recovery_shadow_compare": True
   ```
2. Laisser tourner 1–2h
3. Vérifier qu’il n’y a pas de divergences dans les logs

### B) Activation progressive (si logs OK)
1. Activer :
   ```python
   "recovery_refactor_enabled": True
   ```
2. Surveiller sizing + rejets setup

### C) (Optionnel) Nettoyage final
- Supprimer l’ancienne logique legacy **après 2–3 jours stables**
- Garder un flag de rollback une semaine

### D) Tests supplémentaires à intégrer
**Objectif :** augmenter la couverture et sécuriser les règles Recovery.

1. **Unit tests `RecoveryModeManager.get_state()`**
   - `loss_streak=0` → `active=False`, `level=None`
   - `loss_streak=2` → level 1
   - `loss_streak=5` → level 3

2. **Analyzer gating (RecoveryState)**
   - Vérifier `min_score_boost` appliqué
   - Vérifier confluence forcée quand `confluence_forced=True`

3. **Position sizing (RecoveryState)**
   - Vérifier `position_size_mult` appliqué si `recovery_refactor_enabled=True`
   - Vérifier fallback legacy si flag OFF

4. **Edge cases**
   - Mode SIMPLE vs PROGRESSIVE
   - `recovery_mode.enabled=False` → aucun effet

💡 Proposition fichiers : `tests/test_recovery_state.py`, `tests/test_recovery_gating.py`, `tests/test_recovery_sizing.py`

---

## ✅ Checklist rapide
- [ ] `recovery_shadow_compare=True` (test)
- [ ] logs OK
- [ ] `recovery_refactor_enabled=True`
- [ ] stabilité confirmée

---

## Références code
- `core/position/recovery_mode.py`
- `core/position_manager.py`
- `core/analyzer.py`
- `config.py`
