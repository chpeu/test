# 🏗️ PHASE 0: INFRASTRUCTURE
## Migration SQL + Configuration + Helpers

> **Durée estimée:** 2h | **Bot:** ✅ Peut rester running | **Risque:** Aucun

---

## 0.1 MIGRATION SQL

### Fichier: `database/migrations/add_regime_context_columns.sql`

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRATION: Market Regime V2 + Saisonnalité + ML Integration
-- Date: 09/12/2025
-- Compatibilité: PostgreSQL 12+
-- SAFE: Toutes les commandes sont IF NOT EXISTS
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ TABLE: trade_atr_metrics                                                │
-- │ +15 colonnes pour contexte complet                                      │
-- └─────────────────────────────────────────────────────────────────────────┘

-- Saisonnalité
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    session_market VARCHAR(20) DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    hour_utc INT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    day_of_week INT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    is_weekend BOOLEAN DEFAULT FALSE;

-- Régime V2 Metadata
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_detection_method VARCHAR(30) DEFAULT 'RULE_BASED_V1';
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_atr_median FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_atr_smoothed FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_confidence FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_stability_minutes INT DEFAULT NULL;

-- ML Régime (Phase 3)
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_ml_predicted VARCHAR(20) DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_ml_confidence FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    regime_ml_vs_rule_match BOOLEAN DEFAULT NULL;

-- What-If Régime
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    pnl_if_calme_params FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    pnl_if_normal_params FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    pnl_if_volatile_params FLOAT DEFAULT NULL;
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    optimal_regime_retrospective VARCHAR(20) DEFAULT NULL;

-- Session Multiplier appliqué
ALTER TABLE trade_atr_metrics ADD COLUMN IF NOT EXISTS 
    session_atr_multiplier FLOAT DEFAULT 1.0;

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ TABLE: market_regime_history                                            │
-- │ +7 colonnes pour traçabilité V2                                        │
-- └─────────────────────────────────────────────────────────────────────────┘

ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    detection_method VARCHAR(30) DEFAULT 'RULE_BASED_V1';
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    atr_median FLOAT DEFAULT NULL;
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    atr_smoothed FLOAT DEFAULT NULL;
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    session_market VARCHAR(20) DEFAULT NULL;
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    hysteresis_applied BOOLEAN DEFAULT FALSE;
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    outliers_filtered_count INT DEFAULT 0;
ALTER TABLE market_regime_history ADD COLUMN IF NOT EXISTS 
    ml_confidence FLOAT DEFAULT NULL;

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ TABLE: scan_logs                                                        │
-- │ +4 colonnes pour contexte au moment du scan                            │
-- └─────────────────────────────────────────────────────────────────────────┘

ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS 
    session_market VARCHAR(20) DEFAULT NULL;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS 
    hour_utc INT DEFAULT NULL;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS 
    regime_at_scan VARCHAR(20) DEFAULT NULL;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS 
    regime_confidence_at_scan FLOAT DEFAULT NULL;

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ INDEX pour performance                                                  │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE INDEX IF NOT EXISTS idx_tam_session_hour 
    ON trade_atr_metrics(session_market, hour_utc);
CREATE INDEX IF NOT EXISTS idx_tam_regime_method 
    ON trade_atr_metrics(regime_detection_method);
CREATE INDEX IF NOT EXISTS idx_tam_optimal_regime 
    ON trade_atr_metrics(optimal_regime_retrospective);
CREATE INDEX IF NOT EXISTS idx_scan_session 
    ON scan_logs(session_market, hour_utc);
CREATE INDEX IF NOT EXISTS idx_mrh_method 
    ON market_regime_history(detection_method);

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ VUES d'analyse                                                          │
-- └─────────────────────────────────────────────────────────────────────────┘

-- Performance par Session
CREATE OR REPLACE VIEW v_performance_by_session AS
SELECT 
    tam.session_market,
    COUNT(*) as total_trades,
    SUM(CASE WHEN t.pnl_percent > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN t.pnl_percent <= 0 THEN 1 ELSE 0 END) as losses,
    ROUND(100.0 * SUM(CASE WHEN t.pnl_percent > 0 THEN 1 ELSE 0 END) 
          / NULLIF(COUNT(*), 0), 2) as win_rate,
    ROUND(AVG(t.pnl_percent)::numeric, 4) as avg_pnl_pct,
    ROUND(SUM(t.pnl_percent)::numeric, 4) as total_pnl_pct,
    ROUND(AVG(CASE WHEN t.pnl_percent > 0 THEN t.pnl_percent END)::numeric, 4) as avg_win,
    ROUND(AVG(CASE WHEN t.pnl_percent <= 0 THEN t.pnl_percent END)::numeric, 4) as avg_loss
FROM trade_atr_metrics tam
JOIN trades t ON t.id = tam.trade_id
WHERE tam.session_market IS NOT NULL
GROUP BY tam.session_market
ORDER BY win_rate DESC;

-- Performance par Régime × Session
CREATE OR REPLACE VIEW v_performance_by_regime_session AS
SELECT 
    tam.market_volatility_state as regime,
    tam.session_market,
    COUNT(*) as trades,
    ROUND(100.0 * SUM(CASE WHEN t.pnl_percent > 0 THEN 1 ELSE 0 END) 
          / NULLIF(COUNT(*), 0), 2) as win_rate,
    ROUND(AVG(t.pnl_percent)::numeric, 4) as avg_pnl
FROM trade_atr_metrics tam
JOIN trades t ON t.id = tam.trade_id
WHERE tam.session_market IS NOT NULL 
  AND tam.market_volatility_state IS NOT NULL
GROUP BY tam.market_volatility_state, tam.session_market
HAVING COUNT(*) >= 3
ORDER BY regime, win_rate DESC;

-- Analyse Régime Optimal Rétrospectif
CREATE OR REPLACE VIEW v_optimal_regime_analysis AS
SELECT 
    market_volatility_state as regime_used,
    optimal_regime_retrospective as would_be_optimal,
    COUNT(*) as occurrences,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY market_volatility_state), 2) 
        as pct_of_used_regime,
    ROUND(AVG(CASE 
        WHEN market_volatility_state = optimal_regime_retrospective THEN 1 
        ELSE 0 
    END) * 100, 2) as regime_was_correct_pct
FROM trade_atr_metrics
WHERE optimal_regime_retrospective IS NOT NULL
GROUP BY market_volatility_state, optimal_regime_retrospective
ORDER BY regime_used, occurrences DESC;

-- Performance par Heure UTC
CREATE OR REPLACE VIEW v_performance_by_hour AS
SELECT 
    tam.hour_utc,
    COUNT(*) as trades,
    ROUND(100.0 * SUM(CASE WHEN t.pnl_percent > 0 THEN 1 ELSE 0 END) 
          / NULLIF(COUNT(*), 0), 2) as win_rate,
    ROUND(AVG(t.pnl_percent)::numeric, 4) as avg_pnl
FROM trade_atr_metrics tam
JOIN trades t ON t.id = tam.trade_id
WHERE tam.hour_utc IS NOT NULL
GROUP BY tam.hour_utc
ORDER BY tam.hour_utc;

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VÉRIFICATION POST-MIGRATION
-- ═══════════════════════════════════════════════════════════════════════════

-- Lancer cette requête pour vérifier:
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'trade_atr_metrics' 
--   AND column_name LIKE 'session_%' OR column_name LIKE 'regime_%'
-- ORDER BY ordinal_position;
```

---

## 0.2 HELPER SESSION DETECTOR

### Fichier: `utils/session_detector.py`

```python
"""
Détection de la session de marché basée sur l'heure UTC.
Utilisé par: postgresql_datalogger, market_regime_selector, analyzer

Version: 1.0
Date: 09/12/2025
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Configuration des sessions (heures UTC)
DEFAULT_SESSIONS = {
    "ASIA": {
        "start_hour_utc": 0,
        "end_hour_utc": 7,
        "atr_threshold_multiplier": 0.80,
        "min_score_adjustment": 0.5,
        "description": "Marché asiatique - Range/Calme"
    },
    "EUROPE_OPEN": {
        "start_hour_utc": 7,
        "end_hour_utc": 9,
        "atr_threshold_multiplier": 1.20,
        "min_score_adjustment": 0.0,
        "description": "Ouverture Europe - Breakouts"
    },
    "EUROPE": {
        "start_hour_utc": 9,
        "end_hour_utc": 13,
        "atr_threshold_multiplier": 1.00,
        "min_score_adjustment": 0.0,
        "description": "Session Europe - Normal"
    },
    "US_PREMARKET": {
        "start_hour_utc": 13,
        "end_hour_utc": 14,
        "atr_threshold_multiplier": 1.10,
        "min_score_adjustment": 0.3,
        "description": "Pré-ouverture US - Anticipation"
    },
    "US_OPEN": {
        "start_hour_utc": 14,
        "end_hour_utc": 16,
        "atr_threshold_multiplier": 1.50,
        "min_score_adjustment": -0.5,
        "description": "Ouverture US - MAX Volatilité"
    },
    "US_SESSION": {
        "start_hour_utc": 16,
        "end_hour_utc": 20,
        "atr_threshold_multiplier": 1.20,
        "min_score_adjustment": 0.0,
        "description": "Session US active"
    },
    "US_CLOSE": {
        "start_hour_utc": 20,
        "end_hour_utc": 21,
        "atr_threshold_multiplier": 1.30,
        "min_score_adjustment": -0.3,
        "description": "Clôture US - Pic secondaire"
    },
    "NIGHT": {
        "start_hour_utc": 21,
        "end_hour_utc": 24,
        "atr_threshold_multiplier": 0.70,
        "min_score_adjustment": 1.0,
        "description": "Nuit - Très calme"
    }
}


def get_sessions_config() -> Dict[str, Dict]:
    """Retourne la config des sessions (depuis config ou défaut)"""
    try:
        from config import MARKET_REGIME_V2_CONFIG
        return MARKET_REGIME_V2_CONFIG.get('sessions', DEFAULT_SESSIONS)
    except ImportError:
        return DEFAULT_SESSIONS


def get_current_session(hour_utc: Optional[int] = None) -> Dict[str, Any]:
    """
    Retourne la session de marché actuelle.
    
    Args:
        hour_utc: Heure UTC (0-23). Si None, utilise l'heure actuelle.
    
    Returns:
        Dict avec: name, description, atr_multiplier, score_adjustment, hour_utc
    
    Example:
        >>> session = get_current_session()
        >>> print(f"Session: {session['name']}, Multiplier: {session['atr_multiplier']}")
    """
    if hour_utc is None:
        hour_utc = datetime.now(timezone.utc).hour
    
    sessions = get_sessions_config()
    
    for session_name, config in sessions.items():
        start = config['start_hour_utc']
        end = config['end_hour_utc']
        
        # Cas normal (pas de passage minuit)
        if start < end:
            if start <= hour_utc < end:
                return _format_session_result(session_name, config, hour_utc)
        # Cas passage minuit (ex: NIGHT 21-24 puis ASIA 0-7)
        else:
            if hour_utc >= start or hour_utc < end:
                return _format_session_result(session_name, config, hour_utc)
    
    # Fallback (ne devrait pas arriver)
    logger.warning(f"Session non trouvée pour heure UTC {hour_utc}")
    return {
        "name": "UNKNOWN",
        "description": "Session non identifiée",
        "atr_multiplier": 1.0,
        "score_adjustment": 0.0,
        "hour_utc": hour_utc
    }


def _format_session_result(name: str, config: Dict, hour_utc: int) -> Dict[str, Any]:
    """Formate le résultat de session"""
    return {
        "name": name,
        "description": config.get('description', ''),
        "atr_multiplier": config.get('atr_threshold_multiplier', 1.0),
        "score_adjustment": config.get('min_score_adjustment', 0.0),
        "hour_utc": hour_utc,
        "start_hour": config.get('start_hour_utc'),
        "end_hour": config.get('end_hour_utc')
    }


def get_day_info(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Retourne les informations du jour.
    
    Returns:
        Dict avec: day_of_week (0-6), day_name, is_weekend, hour_utc, minute
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    return {
        "day_of_week": dt.weekday(),  # 0=Lundi, 6=Dimanche
        "day_name": dt.strftime("%A"),
        "is_weekend": dt.weekday() >= 5,
        "hour_utc": dt.hour,
        "minute": dt.minute,
        "timestamp_utc": dt.isoformat()
    }


def get_full_context() -> Dict[str, Any]:
    """
    Retourne le contexte complet (session + jour).
    Pratique pour le logging.
    """
    session = get_current_session()
    day = get_day_info()
    
    return {
        **session,
        **day,
        "context_string": f"{session['name']}_{day['day_name'][:3]}_{day['hour_utc']:02d}h"
    }


# ═══════════════════════════════════════════════════════════════════════════
# TESTS UNITAIRES
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Test Session Detector ===\n")
    
    # Test chaque heure
    print("Sessions par heure UTC:")
    print("-" * 60)
    for hour in range(24):
        session = get_current_session(hour)
        print(f"  {hour:02d}:00 UTC → {session['name']:15s} (×{session['atr_multiplier']:.2f})")
    
    print("\n" + "-" * 60)
    print("Session actuelle:")
    ctx = get_full_context()
    print(f"  {ctx['context_string']}")
    print(f"  Multiplier ATR: ×{ctx['atr_multiplier']}")
    print(f"  Ajustement Score: {ctx['score_adjustment']:+.1f}")
```

---

## 0.3 CONFIGURATION VARIABLES

### Ajout dans `config.py`

```python
# ═══════════════════════════════════════════════════════════════════════════
# MARKET REGIME V2 CONFIGURATION
# Section à ajouter après TRADING_CONFIG
# ═══════════════════════════════════════════════════════════════════════════

MARKET_REGIME_V2_CONFIG = {
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ MASTER TOGGLES                                                      │
    # │ Tous désactivés par défaut = comportement V1 inchangé              │
    # └─────────────────────────────────────────────────────────────────────┘
    "v2_enabled": False,
    "use_median": False,
    "use_hysteresis": False,
    "use_smoothing": False,
    "use_atr_5m": False,
    "use_seasonality": False,
    "use_ml_regime": False,
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ CALCUL ATR                                                          │
    # └─────────────────────────────────────────────────────────────────────┘
    "outlier_filter_enabled": True,
    "outlier_std_threshold": 2.5,
    "min_pairs_for_valid_regime": 5,
    "atr_1m_weight": 0.40,
    "atr_5m_weight": 0.60,
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ HYSTÉRÉSIS                                                          │
    # └─────────────────────────────────────────────────────────────────────┘
    "hysteresis_buffer_percent": 0.10,
    "threshold_calme_max": 0.20,
    "threshold_normal_max": 0.40,
    "threshold_adx_choppy": 20,
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ LISSAGE TEMPOREL                                                    │
    # └─────────────────────────────────────────────────────────────────────┘
    "smoothing_alpha": 0.3,
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ STABILITÉ                                                           │
    # └─────────────────────────────────────────────────────────────────────┘
    "min_regime_duration_minutes": 30,
    "confirmation_required_checks": 2,
    "cooldown_after_change_minutes": 15,
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ SESSIONS (voir utils/session_detector.py pour détails)             │
    # └─────────────────────────────────────────────────────────────────────┘
    "sessions": {
        "ASIA":        {"start_hour_utc": 0,  "end_hour_utc": 7,  "atr_threshold_multiplier": 0.80, "min_score_adjustment": 0.5},
        "EUROPE_OPEN": {"start_hour_utc": 7,  "end_hour_utc": 9,  "atr_threshold_multiplier": 1.20, "min_score_adjustment": 0.0},
        "EUROPE":      {"start_hour_utc": 9,  "end_hour_utc": 13, "atr_threshold_multiplier": 1.00, "min_score_adjustment": 0.0},
        "US_PREMARKET":{"start_hour_utc": 13, "end_hour_utc": 14, "atr_threshold_multiplier": 1.10, "min_score_adjustment": 0.3},
        "US_OPEN":     {"start_hour_utc": 14, "end_hour_utc": 16, "atr_threshold_multiplier": 1.50, "min_score_adjustment": -0.5},
        "US_SESSION":  {"start_hour_utc": 16, "end_hour_utc": 20, "atr_threshold_multiplier": 1.20, "min_score_adjustment": 0.0},
        "US_CLOSE":    {"start_hour_utc": 20, "end_hour_utc": 21, "atr_threshold_multiplier": 1.30, "min_score_adjustment": -0.3},
        "NIGHT":       {"start_hour_utc": 21, "end_hour_utc": 24, "atr_threshold_multiplier": 0.70, "min_score_adjustment": 1.0},
    },
    
    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ LOGGING                                                             │
    # └─────────────────────────────────────────────────────────────────────┘
    "log_regime_details": True,
    "log_session_changes": True,
    "emit_websocket_on_change": True,
}
```

### Ajout dans `config_overrides.json`

```json
{
  "market_regime_v2_enabled": false,
  "market_regime_use_median": false,
  "market_regime_use_hysteresis": false,
  "market_regime_use_smoothing": false,
  "market_regime_use_atr_5m": false,
  "market_regime_use_seasonality": false,
  "market_regime_hysteresis_buffer": 0.10,
  "market_regime_smoothing_alpha": 0.3,
  "market_regime_atr_1m_weight": 0.40,
  "market_regime_atr_5m_weight": 0.60,
  "market_regime_min_duration_minutes": 30
}
```

---

## 0.4 SCRIPT DE MIGRATION

### Fichier: `verification/run_regime_v2_migration.py`

```python
"""
Exécute la migration SQL pour Market Regime V2.
SAFE: Toutes les commandes sont IF NOT EXISTS.

Usage:
    python verification/run_regime_v2_migration.py
"""
import psycopg2
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_migration():
    """Exécute la migration SQL"""
    print("=" * 60)
    print("🔧 MIGRATION: Market Regime V2")
    print("=" * 60)
    
    # Connexion
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        print("✅ Connexion PostgreSQL établie")
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return False
    
    # Charger et exécuter la migration
    migration_path = Path(__file__).parent.parent / 'database' / 'migrations' / 'add_regime_context_columns.sql'
    
    if not migration_path.exists():
        print(f"❌ Fichier migration non trouvé: {migration_path}")
        return False
    
    print(f"📄 Migration: {migration_path.name}")
    
    try:
        sql = migration_path.read_text(encoding='utf-8')
        
        with conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()
        
        print("✅ Migration exécutée avec succès")
        
    except Exception as e:
        print(f"❌ Erreur migration: {e}")
        conn.rollback()
        return False
    
    # Vérification
    print("\n📊 Vérification des nouvelles colonnes:")
    print("-" * 60)
    
    verifications = [
        ("trade_atr_metrics", ["session_market", "hour_utc", "regime_detection_method", "pnl_if_calme_params"]),
        ("market_regime_history", ["detection_method", "atr_median", "hysteresis_applied"]),
        ("scan_logs", ["session_market", "regime_at_scan"]),
    ]
    
    all_ok = True
    with conn.cursor() as cur:
        for table, columns in verifications:
            cur.execute(f"""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = '{table}'
            """)
            existing = {row[0] for row in cur.fetchall()}
            
            for col in columns:
                if col in existing:
                    print(f"  ✅ {table}.{col}")
                else:
                    print(f"  ❌ {table}.{col} MANQUANT!")
                    all_ok = False
    
    # Vérifier les vues
    print("\n📊 Vérification des vues:")
    views = ["v_performance_by_session", "v_performance_by_regime_session", "v_optimal_regime_analysis", "v_performance_by_hour"]
    
    with conn.cursor() as cur:
        for view in views:
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views 
                    WHERE table_name = '{view}'
                )
            """)
            exists = cur.fetchone()[0]
            status = "✅" if exists else "❌"
            print(f"  {status} {view}")
            if not exists:
                all_ok = False
    
    conn.close()
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ MIGRATION COMPLÈTE - Toutes les vérifications OK")
    else:
        print("⚠️ MIGRATION PARTIELLE - Vérifier les erreurs ci-dessus")
    print("=" * 60)
    
    return all_ok


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
```

---

## 0.5 CHECKLIST PHASE 0

```
[ ] 1. Créer database/migrations/add_regime_context_columns.sql
[ ] 2. Créer utils/session_detector.py
[ ] 3. Tester session_detector: python utils/session_detector.py
[ ] 4. Ajouter MARKET_REGIME_V2_CONFIG dans config.py
[ ] 5. Ajouter toggles dans config_overrides.json
[ ] 6. Créer verification/run_regime_v2_migration.py
[ ] 7. Exécuter migration: python verification/run_regime_v2_migration.py
[ ] 8. Vérifier que le bot tourne toujours normalement
[ ] 9. Commit: "Phase 0: Infrastructure Market Regime V2"
```

---

## 0.6 VALIDATION

Pour valider que Phase 0 est complète:

```bash
# 1. Test session detector
python utils/session_detector.py

# 2. Exécuter migration
python verification/run_regime_v2_migration.py

# 3. Vérifier que le bot démarre
python main.py
# (Ctrl+C après quelques secondes si OK)
```

**Phase 0 terminée quand:**
- ✅ Migration SQL exécutée sans erreur
- ✅ Toutes les colonnes créées
- ✅ Toutes les vues créées
- ✅ session_detector.py fonctionne
- ✅ Bot démarre normalement
