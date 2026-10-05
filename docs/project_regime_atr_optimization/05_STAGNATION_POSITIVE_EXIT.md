# 🎯 Stagnation Positive Exit - Spécification Technique

## 📋 Résumé Exécutif

### Problème Identifié
Sur 459 trades sortis en STAGNATION:
- **PnL total**: -210.25%
- **MFE moyen** (max profit atteint): +0.097%
- **53% des trades** ont atteint MFE > 0.05% avant de retomber en négatif
- **31% des trades** ont atteint MFE > 0.10%

**Constat**: La majorité des trades STAGNATION atteignent un profit positif avant de stagner et finir en perte.

### Solution Proposée
Implémenter une **sortie anticipée en profit** lorsque le trade stagne, plutôt que d'attendre le timeout complet et sortir en perte.

### Impact Estimé
| Scénario | PnL Total |
|----------|-----------|
| Actuel | -210.25% |
| Avec sortie positive | -193.85% |
| **Gain** | **+16.4%** |

---

## 🔧 Nouveaux Paramètres

### 1. `stagnation_positive_exit_enabled` (Toggle)
- **Type**: `boolean`
- **Défaut**: `true`
- **Description**: Active la sortie anticipée si le trade est en profit pendant la phase de stagnation

### 2. `stagnation_positive_threshold` (Slider)
- **Type**: `float`
- **Défaut**: `0.03` (0.03%)
- **Min**: `0.01`
- **Max**: `0.15`
- **Step**: `0.01`
- **Description**: Seuil de profit minimum pour déclencher une sortie positive en stagnation

### 3. `stagnation_positive_timeout_seconds` (Slider)
- **Type**: `integer`
- **Défaut**: `60` (1 minute) ⚠️ CORRIGÉ: doit être PLUS COURT que timeout normal (120s)
- **Min**: `30`
- **Max**: `120`
- **Step**: `15`
- **Description**: Timeout réduit si le trade est en profit (DOIT être < stagnation_exit_timeout_seconds)

### 4. `stagnation_use_mfe_tracking` (Toggle)
- **Type**: `boolean`
- **Défaut**: `true`
- **Description**: Suivre le MFE et sortir si le prix retombe significativement après un pic de profit

### 5. `stagnation_mfe_pullback_pct` (Slider)
- **Type**: `float`
- **Défaut**: `0.08` (0.08%) ⚠️ CORRIGÉ: moins agressif pour éviter faux signaux
- **Min**: `0.03`
- **Max**: `0.20`
- **Step**: `0.01`
- **Description**: Sortir si le prix a chuté de X% depuis le MFE (seulement si stagnation détectée)

---

## 🔄 Logique de Sortie Stagnation (Mise à jour)

```python
def _check_stagnation_exit(self, pnl: float) -> Optional[str]:
    """
    Logique de sortie stagnation améliorée avec sortie positive.
    
    Priorités:
    1. Si PnL >= stagnation_positive_threshold ET timeout_positive atteint → SORTIR (profit)
    2. Si MFE tracking activé ET pullback > seuil → SORTIR (protéger profit)
    3. Si PnL >= min_pnl_to_stay → RESTER (attendre TP)
    4. Si PnL <= max_loss_to_exit ET timeout_normal atteint → SORTIR (limiter perte)
    5. Si timeout_normal atteint ET PnL entre les deux seuils → SORTIR (stagnation)
    """
    
    # Phase 1: Sortie positive anticipée
    if stagnation_positive_exit_enabled:
        if pnl >= stagnation_positive_threshold:
            if elapsed >= stagnation_positive_timeout_seconds:
                return 'STAGNATION_POSITIVE'
    
    # Phase 2: Protection MFE (pullback) - SEULEMENT si stagnation détectée
    if stagnation_use_mfe_tracking and self.active_position.stagnation_detected_at:
        mfe = self.active_position.max_favorable_excursion or 0
        if mfe > stagnation_positive_threshold:
            pullback = mfe - pnl
            if pullback >= stagnation_mfe_pullback_pct:
                return 'STAGNATION_MFE_PROTECT'
    
    # Phase 3: Logique existante (timeout normal)
    if elapsed >= timeout_normal:
        if pnl >= min_pnl_to_stay:
            return None  # Rester
        if pnl <= max_loss_to_exit:
            return 'STAGNATION'
        return 'STAGNATION'
    
    return None
```

---

## 📊 Intégration Base de Données

### Nouvelles colonnes table `trades`

```sql
-- Migration: Ajouter colonnes stagnation positive exit
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_stagnation_positive_exit_enabled BOOLEAN DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_stagnation_positive_threshold DOUBLE PRECISION DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_stagnation_positive_timeout_seconds INTEGER DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_stagnation_use_mfe_tracking BOOLEAN DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_stagnation_mfe_pullback_pct DOUBLE PRECISION DEFAULT NULL;

-- Colonnes pour tracking
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stagnation_mfe_at_exit DOUBLE PRECISION DEFAULT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stagnation_positive_triggered BOOLEAN DEFAULT FALSE;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stagnation_pullback_at_exit DOUBLE PRECISION DEFAULT NULL;

-- Index pour analyse
CREATE INDEX IF NOT EXISTS idx_trade_stagnation_positive ON trades (stagnation_positive_triggered) WHERE stagnation_positive_triggered = true;
CREATE INDEX IF NOT EXISTS idx_trade_exit_reason_stagnation ON trades (exit_reason) WHERE exit_reason LIKE 'STAGNATION%';
```

### Nouvelles valeurs `exit_reason`

| exit_reason | Description |
|-------------|-------------|
| `STAGNATION` | Sortie stagnation classique (timeout + perte) |
| `STAGNATION_POSITIVE` | Sortie stagnation avec profit (nouvelle) |
| `STAGNATION_MFE_PROTECT` | Sortie protection MFE après pullback (nouvelle) |

---

## 🎛️ Intégration VariablesPanel.svelte

### Ajout dans les defaults (ligne ~67)

```javascript
// 🔥 HYBRID: Stagnation Positive Exit (NOUVEAU)
stagnation_positive_exit_enabled: true,
stagnation_positive_threshold: 0.03,
stagnation_positive_timeout_seconds: 60,  // ⚠️ CORRIGÉ: < timeout normal (120s)
stagnation_use_mfe_tracking: true,
stagnation_mfe_pullback_pct: 0.08,  // ⚠️ CORRIGÉ: moins agressif
```

### Ajout dans le groupe Export Excel (configGroups ~645)

```javascript
'⏰ Hybrid: Sortie Stagnation': {
    stagnation_exit_enabled: tradingConfig.stagnation_exit_enabled,
    stagnation_exit_timeout_seconds: tradingConfig.stagnation_exit_timeout_seconds,
    stagnation_exit_min_pnl_to_stay: tradingConfig.stagnation_exit_min_pnl_to_stay,
    stagnation_exit_max_loss_to_exit: tradingConfig.stagnation_exit_max_loss_to_exit,
    // 🔥 NOUVEAU: Stagnation Positive
    stagnation_positive_exit_enabled: tradingConfig.stagnation_positive_exit_enabled,
    stagnation_positive_threshold: tradingConfig.stagnation_positive_threshold,
    stagnation_positive_timeout_seconds: tradingConfig.stagnation_positive_timeout_seconds,
    stagnation_use_mfe_tracking: tradingConfig.stagnation_use_mfe_tracking,
    stagnation_mfe_pullback_pct: tradingConfig.stagnation_mfe_pullback_pct,
},
```

### Nouveau bloc UI (après ligne ~3213)

```svelte
<!-- 🔥 NOUVEAU: Stagnation Positive Exit -->
<div class="sub-section">
    <h5 class="sub-title">✅ Sortie Positive Anticipée</h5>
    
    <div class="variable-item checkbox-item">
        <label class="checkbox-label">
            <input
                type="checkbox"
                bind:checked={config.stagnation_positive_exit_enabled}
                on:change={() => triggerAutoSave('stagnation_positive_exit_enabled', config.stagnation_positive_exit_enabled ? 'Activé' : 'Désactivé')}
            />
            <span class="checkmark"></span>
            <span class="checkbox-text">
                <span class="var-name">Sortie Positive</span>
                <span class="var-desc">Sortir en profit si le trade stagne</span>
            </span>
        </label>
    </div>

    {#if config.stagnation_positive_exit_enabled}
        <div class="variable-item">
            <div class="var-header">
                <label for="stagnation-positive-threshold">
                    <span class="var-name">Seuil Profit (%)</span>
                    <span class="var-desc">Profit minimum pour déclencher sortie positive</span>
                </label>
                <button class="btn-reset" on:click={() => resetVariable('stagnation_positive_threshold')} title="Réinitialiser">⟲</button>
            </div>
            <div class="slider-container">
                <input
                    id="stagnation-positive-threshold"
                    type="range"
                    step="0.01"
                    min="0.01"
                    max="0.15"
                    bind:value={config.stagnation_positive_threshold}
                    on:change={() => triggerAutoSave('stagnation_positive_threshold', `${config.stagnation_positive_threshold.toFixed(2)}%`)}
                />
                <span class="slider-value">{Number(config.stagnation_positive_threshold).toFixed(2)}%</span>
            </div>
        </div>

        <div class="variable-item">
            <div class="var-header">
                <label for="stagnation-positive-timeout">
                    <span class="var-name">Timeout Positif (s)</span>
                    <span class="var-desc">Durée réduite avant sortie si en profit</span>
                </label>
                <button class="btn-reset" on:click={() => resetVariable('stagnation_positive_timeout_seconds')} title="Réinitialiser">⟲</button>
            </div>
            <div class="slider-container">
                <input
                    id="stagnation-positive-timeout"
                    type="range"
                    step="30"
                    min="60"
                    max="300"
                    bind:value={config.stagnation_positive_timeout_seconds}
                    on:change={() => triggerAutoSave('stagnation_positive_timeout_seconds', `${config.stagnation_positive_timeout_seconds}s`)}
                />
                <span class="slider-value">{Number(config.stagnation_positive_timeout_seconds).toFixed(0)}s</span>
            </div>
        </div>
    {/if}
</div>

<!-- 🔥 NOUVEAU: MFE Protection -->
<div class="sub-section">
    <h5 class="sub-title">📈 Protection MFE</h5>
    
    <div class="variable-item checkbox-item">
        <label class="checkbox-label">
            <input
                type="checkbox"
                bind:checked={config.stagnation_use_mfe_tracking}
                on:change={() => triggerAutoSave('stagnation_use_mfe_tracking', config.stagnation_use_mfe_tracking ? 'Activé' : 'Désactivé')}
            />
            <span class="checkmark"></span>
            <span class="checkbox-text">
                <span class="var-name">Tracking MFE</span>
                <span class="var-desc">Protéger le profit max atteint</span>
            </span>
        </label>
    </div>

    {#if config.stagnation_use_mfe_tracking}
        <div class="variable-item">
            <div class="var-header">
                <label for="stagnation-mfe-pullback">
                    <span class="var-name">Pullback Max (%)</span>
                    <span class="var-desc">Sortir si le prix chute de X% depuis le MFE</span>
                </label>
                <button class="btn-reset" on:click={() => resetVariable('stagnation_mfe_pullback_pct')} title="Réinitialiser">⟲</button>
            </div>
            <div class="slider-container">
                <input
                    id="stagnation-mfe-pullback"
                    type="range"
                    step="0.01"
                    min="0.02"
                    max="0.15"
                    bind:value={config.stagnation_mfe_pullback_pct}
                    on:change={() => triggerAutoSave('stagnation_mfe_pullback_pct', `${config.stagnation_mfe_pullback_pct.toFixed(2)}%`)}
                />
                <span class="slider-value">{Number(config.stagnation_mfe_pullback_pct).toFixed(2)}%</span>
            </div>
        </div>
    {/if}
</div>
```

---

## 📈 Requêtes SQL de Monitoring

### Comparaison avant/après activation

```sql
-- Performance par type de sortie stagnation
SELECT 
    exit_reason,
    COUNT(*) as trades,
    ROUND(SUM(net_pnl_pct)::numeric, 2) as total_pnl,
    ROUND(AVG(net_pnl_pct)::numeric, 3) as avg_pnl,
    ROUND(AVG(max_favorable_excursion)::numeric, 3) as avg_mfe
FROM trades
WHERE is_live_trade = true
  AND exit_reason LIKE 'STAGNATION%'
  AND timestamp_exit >= NOW() - INTERVAL '7 days'
GROUP BY exit_reason
ORDER BY trades DESC;
```

### Efficacité de la protection MFE

```sql
-- Trades où la protection MFE a sauvé du profit
SELECT 
    symbol,
    exit_reason,
    ROUND(net_pnl_pct::numeric, 3) as final_pnl,
    ROUND(max_favorable_excursion::numeric, 3) as mfe,
    ROUND((max_favorable_excursion - net_pnl_pct)::numeric, 3) as profit_saved
FROM trades
WHERE is_live_trade = true
  AND exit_reason = 'STAGNATION_MFE_PROTECT'
ORDER BY timestamp_exit DESC
LIMIT 20;
```

---

## ✅ Checklist Implémentation - TERMINÉE (14/12/2025)

### Backend (Python) ✅
- [x] Ajouter paramètres dans `config.py` → `TRADING_CONFIG` (lignes 84-89)
- [x] Ajouter handlers WebSocket dans `main.py` (lignes 5682-5711)
- [x] Modifier `position_manager.py` → `_check_stagnation_exit()` (lignes 2131-2249)
- [x] Mettre à jour `postgresql_datalogger.py` pour logger les nouvelles colonnes (lignes 1577-1590)
- [x] Ajouter migration SQL `database/migrations/add_stagnation_positive_exit.sql`

### Frontend (Svelte) ✅
- [x] Ajouter defaults dans `VariablesPanel.svelte` (lignes 67-76)
- [x] Ajouter dans `configGroups` pour export Excel (lignes 651-662)
- [x] Créer UI pour les nouveaux sliders/toggles (lignes 3226-3335)
- [x] Autosave et persistance fonctionnels

### Tests ✅
- [x] Colonnes SQL créées (8 colonnes vérifiées)
- [x] Nouveaux exit_reason implémentés: `STAGNATION_POSITIVE`, `STAGNATION_MFE_PROTECT`
- [ ] Attente premiers trades pour validation en production

---

## 📅 Historique

| Date | Action |
|------|--------|
| 2025-12-13 | Création de la spécification basée sur analyse des 459 trades STAGNATION |
| 2025-12-14 | Corrections: timeout positive < timeout normal, MFE protection seulement si stagnation détectée, pullback moins agressif |
| 2025-12-14 | **IMPLÉMENTATION COMPLÈTE** - Backend, Frontend, SQL, Logging |
| 2025-12-14 | Valeurs recommandées: timeout=90s, pullback=0.05% (basé sur analyse 533 trades STAGNATION) |
