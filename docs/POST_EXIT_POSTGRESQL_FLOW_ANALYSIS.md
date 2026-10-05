# 🔄 Analyse du Flux PostExit → PostgreSQL
**Date:** 25 Janvier 2026  
**Status:** Architecture complète retracée ✅

---

## 📋 Vue d'ensemble

Le système PostExit analyse les prix après clôture des trades pour générer des **targets ML** optimisant les paramètres de sortie (SL/TP/Trailing). Voici le flux complet de données.

## 🔄 Flux Principal: Trade Fermé → Base PostgreSQL

```
1. POSITION FERMÉE
   ↓
2. PostExitManager.start_tracking_sync()
   ↓
3. PostExitTracker créé + ajouté aux actifs
   ↓
4. PostExitLoop (1s intervals) → Prix live
   ↓
5. PostExitTracker.add_sample() → Accumulation samples
   ↓
6. Fin tracking (timeout/limite) → _complete_tracker()
   ↓
7. Calcul métriques finales → compute_final_metrics()
   ↓
8. _save_to_database() → PostgreSQL
   ├─ INSERT trade_post_exit_analysis (métriques)
   └─ INSERT trade_post_exit_samples (samples bruts)
```

---

## 🔧 Composants Architecture

### 1. **PostExitManager** (`core/post_exit/manager.py`)

**Point d'entrée:** `start_tracking_sync()` ligne 4446 dans `position_manager.py`

```python
post_exit_manager.start_tracking_sync(
    trade_id=db_trade_id,        # UUID string (requis pour FK)
    symbol=position.symbol,
    direction=position.direction,
    exit_price=exit_price,
    exit_reason=reason,
    realized_pnl_pct=net_pnl_pct,
    realized_pnl_usdt=net_pnl_usdt,
    # ... autres params
)
```

**Configuration:**
- `tracking_duration_sec`: 300s par défaut (5 min)  
- `sample_interval_ms`: 2000ms par défaut (0.5Hz)
- `max_concurrent_trackers`: 10 max
- `store_raw_samples`: True (sauvegarde échantillons)

### 2. **PostExitTracker** (`core/post_exit/tracker.py`)

**Responsabilités:**
- Collecte échantillons prix (1 sample / 2s pendant 5 min)
- Calcul MFE/MAE post-exit en temps réel
- Détection flags (would_have_hit_original_tp/sl, price_returned_to_entry)

**Métriques calculées:**
```python
{
    "exit_efficiency_pct": realized / (realized + mfe_missed) * 100,
    "regret_pct": post_exit_mfe_pct,
    "regret_usdt": regret en $,
    "exit_timing_grade": "A+" à "F",
    "ml_optimal_sl_pct": SL optimal calculé,
    "ml_optimal_trailing_trigger": Trigger trailing optimal,
    "ml_optimal_trailing_distance": Distance trailing optimale (simulation)
}
```

### 3. **PostExitLoop** (`core/callbacks/post_exit_loop.py`)

**Boucle autonome** démarrée dans `main.py` ligne 403:
- Récupère prix live pour tous symboles en tracking
- Cadence: 1 seconde par défaut
- Envoie prix via `PostExitManager.on_price_update_sync()`

### 4. **Base PostgreSQL** (Tables)

#### Table `trade_post_exit_analysis`
```sql
CREATE TABLE trade_post_exit_analysis (
    trade_id UUID NOT NULL PRIMARY KEY,        -- FK vers trades(id)
    exit_efficiency_pct DECIMAL(10, 4),        -- Métrique clé ML
    regret_pct DECIMAL(10, 4),                 -- PnL% manqué
    post_exit_mfe_pct DECIMAL(10, 4),          -- Max profit post-exit
    post_exit_mae_pct DECIMAL(10, 4),          -- Max loss post-exit
    ml_optimal_sl_pct DECIMAL(10, 4),          -- Target ML: SL optimal
    ml_optimal_trailing_trigger DECIMAL(10, 4), -- Target ML: Trailing optimal
    ml_optimal_trailing_distance FLOAT,        -- Target ML: Distance optimale
    sample_count INTEGER,                      -- Nb échantillons collectés
    -- ... 20+ colonnes total
);
```

#### Table `trade_post_exit_samples` 
```sql
CREATE TABLE trade_post_exit_samples (
    trade_id UUID NOT NULL,                   -- FK vers trades(id)
    sample_index INTEGER NOT NULL,            -- 0, 1, 2, ... N
    timestamp TIMESTAMPTZ NOT NULL,
    price DECIMAL(20, 10) NOT NULL,
    pnl_vs_exit_pct DECIMAL(10, 4),          -- PnL% depuis exit
    cumulative_mfe_pct DECIMAL(10, 4),       -- MFE cumulé
    cumulative_mae_pct DECIMAL(10, 4)        -- MAE cumulé
);
```

---

## ⚠️ Points d'Échec Potentiels

### 1. **PostgreSQL DataLogger Non Disponible**
**Localisation:** `_save_to_database()` ligne 320-328  
**Symptôme:** Logs `❌ PostExit DB: DataLogger non disponible`  
**Cause:** 
- `POSTGRES_ENABLED=false` dans `.env`
- Échec connexion PostgreSQL
- Import error psycopg2

### 2. **Trade ID Manquant/Invalide**
**Localisation:** `position_manager.py` ligne 4429-4433  
**Symptôme:** Log `⚠️ PostExit: Pas de trade_id pour {symbol}, skip tracking`  
**Cause:** 
- `position._trade_id` non défini
- Type incorrect (doit être UUID string)

### 3. **Tables PostgreSQL Manquantes**
**Symptôme:** Erreur SQL lors INSERT  
**Solution:** Exécuter migrations:
```bash
psql -U postgres -d trade_cursor_ml -f database/migrations/add_post_exit_analysis_tables.sql
psql -U postgres -d trade_cursor_ml -f database/migrations/add_post_exit_tracker_persistence.sql
psql -U postgres -d trade_cursor_ml -f database/migrations/add_symbol_to_post_exit.sql
psql -U postgres -d trade_cursor_ml -f database/migrations/add_ml_optimal_trailing_distance.sql
```

### 4. **Price Provider Indisponible**
**Localisation:** `post_exit_loop.py` ligne 60-63  
**Symptôme:** Pas de prix, échantillonnage raté  
**Cause:** API exchange down, WebSocket fermé

### 5. **Limite Trackers Concurrents**
**Localisation:** `manager.py` ligne 126-130  
**Symptôme:** Log `⚠️ PostExit: Limite de trackers atteinte`  
**Solution:** Augmenter `max_concurrent_trackers` ou réduire `tracking_duration_sec`

### 6. **Timeout/Complétion Forcée**
**Localisation:** `manager.py` ligne 240-243 (thread duration_complete)  
**Cause:** `tracking_duration_sec` écoulé  
**Comportement:** Sauvegarde avec samples collectés (même partiels)

---

## 📊 Métriques de Debug

### Logs à Surveiller
```
✅ PostExit {symbol}: Tracker créé (trade #{trade_id})
📊 PostExit {symbol}: Sample #{n} ajouté (MFE: {mfe}%, MAE: {mae}%)
⏰ PostExit {symbol}: Complétion par timeout après {duration}s
💾 PostExit {symbol}: Sauvegarde DB avec {count} samples...
✅ PostExit {symbol}: Terminé (efficiency: {eff}% | grade: {grade})
```

### Vérifications PostgreSQL
```sql
-- Compter analyses post-exit récentes
SELECT COUNT(*) FROM trade_post_exit_analysis 
WHERE created_at > NOW() - INTERVAL '24 hours';

-- Vérifier samples collectés
SELECT trade_id, sample_count, exit_efficiency_pct 
FROM trade_post_exit_analysis 
ORDER BY created_at DESC LIMIT 5;

-- Analyser distribution grades
SELECT exit_timing_grade, COUNT(*) 
FROM trade_post_exit_analysis 
GROUP BY exit_timing_grade;
```

---

## 🔄 Flux de Données Détaillé

### Phase 1: Initialisation (Trade Fermé)
1. `position_manager.close_position()` → Fermeture trade
2. Récupération `trade_id` (UUID) obligatoire  
3. Appel `post_exit_manager.start_tracking_sync()`
4. Validation params + création `PostExitTracker`
5. Ajout au dict `active_trackers[symbol]`

### Phase 2: Collecte (Durée Tracking)
1. `PostExitLoop` récupère prix toutes les 1s
2. Pour chaque symbole actif: `get_price(symbol)`  
3. `on_price_update_sync()` → `tracker.add_sample(price)`
4. Calcul MFE/MAE temps réel
5. Vérification flags (TP/SL auraient été touchés)

### Phase 3: Finalisation (Timeout/Limite)
1. Thread `_complete_tracker_sync()` déclenché
2. `compute_final_metrics()` → Calcul 20+ métriques
3. Simulation trailing optimal (tick-by-tick)
4. `_save_to_database()` → PostgreSQL

### Phase 4: Sauvegarde PostgreSQL
1. Connexion pool PostgreSQL
2. Transaction BEGIN
3. UPSERT `trade_post_exit_analysis` (métriques)
4. BATCH INSERT `trade_post_exit_samples` (si enabled)  
5. COMMIT + libération connexion

---

## ✅ État Architecture

- ✅ **Code PostExit** complet et fonctionnel
- ✅ **Tables PostgreSQL** définies avec migrations  
- ✅ **Intégration position_manager** opérationnelle
- ✅ **PostExitLoop** autonome démarrée dans main.py
- ✅ **DataLogger PostgreSQL** configuré et injecté
- ❓ **Tables créées** dans instance PostgreSQL (à vérifier)
- ❓ **Test bout-en-bout** avec trade réel (à valider)

---

## 🧪 Test Recommandé

Utiliser `scripts/test_post_exit_save.py` pour valider:
1. Connexion PostgreSQL  
2. Création tracker mock
3. Calcul métriques
4. Sauvegarde en base
5. Vérification données

**Commande:**
```bash
cd "c:\Users\sebta\Documents\clone github\test\test"
python scripts/test_post_exit_save.py
```
