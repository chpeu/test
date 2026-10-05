# 🏗️ PHASE 1: IMPLÉMENTATION
## Logging Contextuel + Régime V2 + What-If Régime

> **Prérequis:** Phase 0 complétée
> **Durée totale:** 10h | **Bot:** ✅ Running pendant tout

---

# PHASE 1A: LOGGING CONTEXTUEL (3h)

## 1A.1 Modification `postgresql_datalogger.py`

### Fonction `log_trade_atr_metrics()` - Enrichissement

```python
# Ajouter ces imports en haut du fichier
from utils.session_detector import get_current_session, get_day_info

# Dans la fonction log_trade_atr_metrics(), APRÈS les calculs existants:

def log_trade_atr_metrics(self, trade_id: str, trade_data: Dict[str, Any]) -> bool:
    """
    Logger enrichi Phase 1A: ajoute contexte Session/Heure.
    """
    # ... code existant pour extraire les métriques ATR ...
    
    # ═══════════════════════════════════════════════════════════════════
    # NOUVEAU PHASE 1A: Contexte Session/Heure
    # ═══════════════════════════════════════════════════════════════════
    
    session_info = get_current_session()
    day_info = get_day_info()
    
    session_market = session_info['name']
    hour_utc = day_info['hour_utc']
    day_of_week = day_info['day_of_week']
    is_weekend = day_info['is_weekend']
    session_atr_multiplier = session_info['atr_multiplier']
    
    # Méthode de détection (V1 par défaut, sera V2 après Phase 1B)
    regime_detection_method = 'RULE_BASED_V1'
    
    # Calculer stabilité régime
    regime_stability_minutes = None
    regime_confidence = None
    try:
        from core.market_regime_selector import get_regime_selector
        rs = get_regime_selector()
        if rs.regime_since:
            from datetime import datetime
            delta = datetime.now() - rs.regime_since
            regime_stability_minutes = int(delta.total_seconds() / 60)
        # Confidence sera rempli en Phase 1B
    except Exception as e:
        logger.debug(f"Erreur récupération régime: {e}")
    
    # ═══════════════════════════════════════════════════════════════════
    # MODIFIER LA QUERY INSERT pour inclure les nouvelles colonnes
    # ═══════════════════════════════════════════════════════════════════
    
    query = """
        INSERT INTO trade_atr_metrics (
            trade_id,
            -- Colonnes existantes (Phase 1.3 ATR Optimization)
            entry_atr_1m, entry_atr_5m, entry_atr_pct_1m, entry_atr_pct_5m,
            param_atr_mult_sl, param_atr_mult_tp,
            param_trailing_trigger_mult, param_trailing_distance_mult,
            param_be_atr_mult, param_stagnation_timeout, param_stagnation_min_pnl,
            market_volatility_state, market_trend_state, entry_adx,
            calculated_sl_price, calculated_tp_price,
            calculated_sl_pct, calculated_tp_pct,
            calculated_be_trigger_pnl_pct, calculated_trailing_trigger_pnl_pct,
            be_triggered, be_triggered_at,
            trailing_activated, trailing_activated_at,
            max_pnl_reached, min_pnl_reached,
            sl_mexc_price, sl_mexc_pct, sl_mexc_margin_used,
            
            -- NOUVELLES COLONNES Phase 1A
            session_market, hour_utc, day_of_week, is_weekend,
            regime_detection_method, regime_stability_minutes, regime_confidence,
            session_atr_multiplier
            
        ) VALUES (
            %s,
            -- Valeurs existantes
            %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s,
            %s, %s,
            %s, %s,
            %s, %s,
            %s, %s, %s,
            
            -- NOUVELLES VALEURS Phase 1A
            %s, %s, %s, %s,
            %s, %s, %s,
            %s
        )
        ON CONFLICT (trade_id) DO UPDATE SET
            -- MAJ colonnes Phase 1A si déjà existant
            session_market = EXCLUDED.session_market,
            hour_utc = EXCLUDED.hour_utc,
            day_of_week = EXCLUDED.day_of_week,
            is_weekend = EXCLUDED.is_weekend,
            regime_detection_method = EXCLUDED.regime_detection_method,
            regime_stability_minutes = EXCLUDED.regime_stability_minutes,
            session_atr_multiplier = EXCLUDED.session_atr_multiplier
    """
    
    params = (
        trade_id,
        # Valeurs existantes
        entry_atr_1m, entry_atr_5m, entry_atr_pct_1m, entry_atr_pct_5m,
        param_atr_mult_sl, param_atr_mult_tp,
        param_trailing_trigger_mult, param_trailing_distance_mult,
        param_be_atr_mult, param_stagnation_timeout, param_stagnation_min_pnl,
        market_volatility_state, market_trend_state, entry_adx,
        sl_price, tp_price,
        calculated_sl_pct, calculated_tp_pct,
        calculated_be_trigger_pnl_pct, calculated_trailing_trigger_pnl_pct,
        be_triggered, be_triggered_at,
        trailing_activated, trailing_activated_at,
        max_pnl_reached, min_pnl_reached,
        sl_mexc_price, sl_mexc_pct, sl_mexc_margin,
        
        # NOUVELLES VALEURS Phase 1A
        session_market, hour_utc, day_of_week, is_weekend,
        regime_detection_method, regime_stability_minutes, regime_confidence,
        session_atr_multiplier
    )
    
    # ... reste du code INSERT ...
```

### Fonction `log_scan()` - Enrichissement

```python
def log_scan(self, scan_data: Dict[str, Any]) -> bool:
    """
    Logger scan enrichi Phase 1A.
    """
    # ═══════════════════════════════════════════════════════════════════
    # NOUVEAU PHASE 1A: Ajouter contexte session au scan
    # ═══════════════════════════════════════════════════════════════════
    
    from utils.session_detector import get_current_session
    
    session_info = get_current_session()
    
    # Récupérer régime actuel
    regime_at_scan = None
    regime_confidence_at_scan = None
    try:
        from core.market_regime_selector import get_regime_selector
        rs = get_regime_selector()
        if rs.current_regime:
            regime_at_scan = rs.current_regime.value
    except:
        pass
    
    # Enrichir scan_data
    scan_data['session_market'] = session_info['name']
    scan_data['hour_utc'] = session_info['hour_utc']
    scan_data['regime_at_scan'] = regime_at_scan
    scan_data['regime_confidence_at_scan'] = regime_confidence_at_scan
    
    # ... reste du code INSERT existant, ajouter les colonnes dans la query ...
```

---

## 1A.2 Modification `market_regime_selector.py`

### Fonction `_log_regime_change_to_db()` - Enrichissement

```python
def _log_regime_change_to_db(
    self,
    old_regime: MarketRegime,
    new_regime: MarketRegime,
    trigger: str = "auto"
) -> None:
    """
    Logger changement de régime enrichi Phase 1A.
    """
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        from utils.session_detector import get_current_session
        
        pg_logger = get_pg_datalogger()
        if not pg_logger or not pg_logger.enabled:
            return
        
        session_info = get_current_session()
        
        # ═══════════════════════════════════════════════════════════════
        # NOUVELLES MÉTRIQUES Phase 1A
        # ═══════════════════════════════════════════════════════════════
        
        detection_method = 'RULE_BASED_V1'  # Sera 'V2' après Phase 1B
        atr_median = getattr(self, 'last_atr_median', None)
        atr_smoothed = getattr(self, 'last_atr_smoothed', None)
        hysteresis_applied = getattr(self, 'hysteresis_was_applied', False)
        outliers_count = getattr(self, 'last_outliers_count', 0)
        ml_confidence = None  # Phase 3
        
        # Durée dans l'ancien régime
        old_duration_minutes = None
        if self.regime_since:
            from datetime import datetime
            old_duration_minutes = (datetime.now() - self.regime_since).total_seconds() / 60
        
        # ═══════════════════════════════════════════════════════════════
        # QUERY ENRICHIE
        # ═══════════════════════════════════════════════════════════════
        
        query = """
            INSERT INTO market_regime_history (
                timestamp, session_id, old_regime, new_regime,
                avg_atr, avg_adx, sample_count, trigger,
                old_regime_duration_minutes,
                -- NOUVELLES COLONNES Phase 1A
                detection_method, atr_median, atr_smoothed,
                session_market, hysteresis_applied, outliers_filtered_count,
                ml_confidence
            ) VALUES (
                NOW(), %s, %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, %s, %s,
                %s, %s, %s,
                %s
            )
        """
        
        session_id = pg_logger.get_or_create_session()
        
        params = (
            session_id,
            old_regime.value,
            new_regime.value,
            round(self.avg_atr, 4),
            round(self.avg_adx, 1) if self.avg_adx else None,
            self.atr_sample_count,
            trigger,
            round(old_duration_minutes, 1) if old_duration_minutes else None,
            # Nouvelles valeurs
            detection_method,
            round(atr_median, 4) if atr_median else None,
            round(atr_smoothed, 4) if atr_smoothed else None,
            session_info['name'],
            hysteresis_applied,
            outliers_count,
            ml_confidence
        )
        
        pg_logger._execute_query(query, params)
        logger.info(f"📝 Régime loggé: {old_regime.value}→{new_regime.value} | Session={session_info['name']}")
        
    except Exception as e:
        logger.error(f"❌ Erreur logging régime: {e}")
```

---

## 1A.3 Script de Vérification Phase 1A

### Fichier: `verification/verify_phase_1a_logging.py`

```python
"""
Vérifie que le logging contextuel Phase 1A fonctionne.
"""
import psycopg2
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_phase_1a():
    print("=" * 60)
    print("🔍 VÉRIFICATION PHASE 1A: Logging Contextuel")
    print("=" * 60)
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    
    results = {}
    
    with conn.cursor() as cur:
        # 1. Vérifier trade_atr_metrics
        print("\n📊 trade_atr_metrics:")
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(session_market) as with_session,
                   COUNT(hour_utc) as with_hour
            FROM trade_atr_metrics
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        row = cur.fetchone()
        total, with_session, with_hour = row
        
        if total > 0:
            pct = 100 * with_session / total
            status = "✅" if pct > 90 else "⚠️"
            print(f"  {status} {with_session}/{total} trades avec session_market ({pct:.0f}%)")
            results['trades'] = pct > 90
        else:
            print("  ⏳ Aucun trade récent - en attente de données")
            results['trades'] = None
        
        # 2. Vérifier scan_logs
        print("\n📊 scan_logs:")
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(session_market) as with_session
            FROM scan_logs
            WHERE created_at > NOW() - INTERVAL '1 hour'
        """)
        row = cur.fetchone()
        total, with_session = row
        
        if total > 0:
            pct = 100 * with_session / total
            status = "✅" if pct > 90 else "⚠️"
            print(f"  {status} {with_session}/{total} scans avec session_market ({pct:.0f}%)")
            results['scans'] = pct > 90
        else:
            print("  ⏳ Aucun scan récent - en attente")
            results['scans'] = None
        
        # 3. Vérifier market_regime_history
        print("\n📊 market_regime_history:")
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(detection_method) as with_method,
                   COUNT(session_market) as with_session
            FROM market_regime_history
            WHERE timestamp > NOW() - INTERVAL '24 hours'
        """)
        row = cur.fetchone()
        total, with_method, with_session = row
        
        if total > 0:
            print(f"  ✅ {total} changements de régime loggés")
            print(f"     - {with_method} avec detection_method")
            print(f"     - {with_session} avec session_market")
            results['regime_history'] = with_method > 0
        else:
            print("  ⏳ Aucun changement de régime - normal si régime stable")
            results['regime_history'] = None
        
        # 4. Distribution par session
        print("\n📊 Distribution des scans par session (dernière heure):")
        cur.execute("""
            SELECT session_market, COUNT(*) 
            FROM scan_logs 
            WHERE session_market IS NOT NULL 
              AND created_at > NOW() - INTERVAL '1 hour'
            GROUP BY session_market
            ORDER BY COUNT(*) DESC
        """)
        rows = cur.fetchall()
        if rows:
            for session, count in rows:
                print(f"  - {session}: {count}")
        else:
            print("  ⏳ Pas encore de données")
    
    conn.close()
    
    # Résumé
    print("\n" + "=" * 60)
    print("📋 RÉSUMÉ PHASE 1A:")
    
    all_ok = True
    for key, value in results.items():
        if value is None:
            print(f"  ⏳ {key}: En attente de données")
        elif value:
            print(f"  ✅ {key}: OK")
        else:
            print(f"  ❌ {key}: ÉCHEC")
            all_ok = False
    
    if all_ok and all(v is not None for v in results.values()):
        print("\n✅ PHASE 1A VALIDÉE")
    elif any(v is False for v in results.values()):
        print("\n❌ PHASE 1A: Corrections nécessaires")
    else:
        print("\n⏳ PHASE 1A: En attente de trades/scans pour validation complète")
    
    print("=" * 60)
    return all_ok


if __name__ == "__main__":
    verify_phase_1a()
```

---

# PHASE 1B: RÉGIME V2 QUICK WINS (4h)

## 1B.1 Nouvelles Méthodes `market_regime_selector.py`

### Import et Constantes

```python
# Ajouter en haut du fichier
import statistics
from typing import List, Dict, Tuple, Optional

# Après les imports existants
from utils.effective_config import get_effective_value
from utils.session_detector import get_current_session
```

### Méthode: `calculate_atr_metric()`

```python
def calculate_atr_metric(self, atr_values: List[float]) -> float:
    """
    Calcule la métrique ATR selon la config V2.
    
    Features:
    - Filtrage des outliers (si activé)
    - Médiane au lieu de moyenne (si activé)
    
    Returns:
        ATR calculé (médiane ou moyenne selon config)
    """
    use_median = get_effective_value('market_regime_use_median') or False
    outlier_filter = get_effective_value('market_regime_outlier_filter') or True
    outlier_threshold = get_effective_value('market_regime_outlier_std_threshold') or 2.5
    
    values = atr_values.copy()
    self.last_outliers_count = 0
    
    # Filtrer les outliers si activé et assez de données
    if outlier_filter and len(values) >= 5:
        mean = statistics.mean(values)
        try:
            std = statistics.stdev(values)
            if std > 0:
                original_count = len(values)
                values = [v for v in values if abs(v - mean) <= outlier_threshold * std]
                self.last_outliers_count = original_count - len(values)
                
                if self.last_outliers_count > 0:
                    logger.debug(
                        f"🔍 Outliers filtrés: {self.last_outliers_count} paires exclues "
                        f"(seuil: {outlier_threshold}σ)"
                    )
        except statistics.StatisticsError:
            pass  # Pas assez de variance
    
    # Calcul final
    if not values:
        values = atr_values  # Fallback si tout filtré
    
    if use_median:
        result = statistics.median(values)
        self.last_atr_median = result
        logger.debug(f"📊 ATR Médian: {result:.4f}% (n={len(values)})")
    else:
        result = sum(values) / len(values)
        self.last_atr_median = None
        logger.debug(f"📊 ATR Moyen: {result:.4f}% (n={len(values)})")
    
    return result
```

### Méthode: `apply_smoothing()`

```python
def apply_smoothing(self, new_value: float) -> float:
    """
    Applique un lissage EMA pour stabiliser les changements.
    
    Formula: EMA = α × new + (1-α) × previous
    
    Returns:
        Valeur lissée (ou brute si smoothing désactivé)
    """
    use_smoothing = get_effective_value('market_regime_use_smoothing') or False
    alpha = get_effective_value('market_regime_smoothing_alpha') or 0.3
    
    if not use_smoothing:
        self.last_atr_smoothed = new_value
        return new_value
    
    # Initialisation au premier appel
    if not hasattr(self, '_ema_value') or self._ema_value is None:
        self._ema_value = new_value
        self.last_atr_smoothed = new_value
        logger.debug(f"📈 EMA initialisé: {new_value:.4f}%")
        return new_value
    
    # Calcul EMA
    smoothed = alpha * new_value + (1 - alpha) * self._ema_value
    self._ema_value = smoothed
    self.last_atr_smoothed = smoothed
    
    logger.debug(
        f"📈 Lissage EMA: brut={new_value:.4f}% → lissé={smoothed:.4f}% (α={alpha})"
    )
    
    return smoothed
```

### Méthode: `should_change_regime()`

```python
def should_change_regime(
    self,
    current: MarketRegime,
    proposed: MarketRegime,
    atr_value: float
) -> bool:
    """
    Applique l'hystérésis pour éviter le flip-flop.
    
    Avec buffer 10%:
    - CALME→NORMAL: ATR > 0.22 (pas 0.20)
    - NORMAL→CALME: ATR < 0.18 (pas 0.20)
    
    Returns:
        True si le changement doit être appliqué
    """
    use_hysteresis = get_effective_value('market_regime_use_hysteresis') or False
    buffer = get_effective_value('market_regime_hysteresis_buffer') or 0.10
    
    self.hysteresis_was_applied = False
    
    if not use_hysteresis:
        return current != proposed
    
    if current == proposed:
        return False
    
    # Seuils de base
    threshold_calme = get_effective_value('market_regime_threshold_calme_max') or 0.20
    threshold_normal = get_effective_value('market_regime_threshold_normal_max') or 0.40
    
    # Map des transitions avec seuils bufferisés
    # Pour monter: seuil + buffer | Pour descendre: seuil - buffer
    transitions = {
        # Montées (plus difficile)
        (MarketRegime.CALME, MarketRegime.NORMAL): (threshold_calme * (1 + buffer), '>'),
        (MarketRegime.NORMAL, MarketRegime.VOLATILE): (threshold_normal * (1 + buffer), '>'),
        (MarketRegime.CALME, MarketRegime.VOLATILE): (threshold_normal * (1 + buffer), '>'),
        
        # Descentes (plus difficile)
        (MarketRegime.NORMAL, MarketRegime.CALME): (threshold_calme * (1 - buffer), '<'),
        (MarketRegime.VOLATILE, MarketRegime.NORMAL): (threshold_normal * (1 - buffer), '<'),
        (MarketRegime.VOLATILE, MarketRegime.CALME): (threshold_calme * (1 - buffer), '<'),
    }
    
    key = (current, proposed)
    if key not in transitions:
        # Transition CHOPPY ou autre non définie
        return True
    
    threshold_with_buffer, direction = transitions[key]
    
    # Vérifier si le seuil bufferisé est franchi
    if direction == '>':
        should_change = atr_value > threshold_with_buffer
    else:
        should_change = atr_value < threshold_with_buffer
    
    # Logger si bloqué par hystérésis
    if not should_change and current != proposed:
        self.hysteresis_was_applied = True
        logger.info(
            f"🚫 Hystérésis: {current.value}→{proposed.value} BLOQUÉ | "
            f"ATR={atr_value:.3f}% {direction} {threshold_with_buffer:.3f}% requis"
        )
    
    return should_change
```

### Méthode: `calculate_combined_atr()`

```python
def calculate_combined_atr(
    self,
    atr_1m_values: List[float],
    atr_5m_values: List[float]
) -> float:
    """
    Combine ATR 1m et 5m avec pondération configurable.
    
    Returns:
        ATR combiné (ou ATR 1m seul si 5m désactivé)
    """
    use_atr_5m = get_effective_value('market_regime_use_atr_5m') or False
    weight_1m = get_effective_value('market_regime_atr_1m_weight') or 0.40
    weight_5m = get_effective_value('market_regime_atr_5m_weight') or 0.60
    
    # Calcul ATR 1m (avec médiane/outliers si activés)
    atr_1m = self.calculate_atr_metric(atr_1m_values)
    
    if not use_atr_5m or not atr_5m_values:
        return atr_1m
    
    # Calcul ATR 5m
    atr_5m = self.calculate_atr_metric(atr_5m_values)
    
    # Combinaison pondérée
    combined = (atr_1m * weight_1m) + (atr_5m * weight_5m)
    
    logger.debug(
        f"📊 ATR Combiné: 1m={atr_1m:.4f}%×{weight_1m:.0%} + "
        f"5m={atr_5m:.4f}%×{weight_5m:.0%} = {combined:.4f}%"
    )
    
    return combined
```

### Méthode: `get_session_adjusted_thresholds()`

```python
def get_session_adjusted_thresholds(self) -> Dict[str, float]:
    """
    Retourne les seuils ajustés selon la session actuelle.
    
    Returns:
        Dict avec calme_max, normal_max, session, multiplier
    """
    use_seasonality = get_effective_value('market_regime_use_seasonality') or False
    
    # Seuils de base
    base_calme = get_effective_value('market_regime_threshold_calme_max') or 0.20
    base_normal = get_effective_value('market_regime_threshold_normal_max') or 0.40
    
    if not use_seasonality:
        return {
            "calme_max": base_calme,
            "normal_max": base_normal,
            "session": None,
            "multiplier": 1.0
        }
    
    # Récupérer multiplicateur session
    session = get_current_session()
    multiplier = session.get('atr_multiplier', 1.0)
    
    adjusted = {
        "calme_max": base_calme * multiplier,
        "normal_max": base_normal * multiplier,
        "session": session['name'],
        "multiplier": multiplier
    }
    
    logger.debug(
        f"🕐 Session {session['name']}: seuils ×{multiplier:.2f} | "
        f"CALME<{adjusted['calme_max']:.3f}% | NORMAL<{adjusted['normal_max']:.3f}%"
    )
    
    return adjusted
```

### Méthode: `check_regime_v2()` - Assemblage Final

```python
async def check_regime_v2(
    self,
    atr_1m_values: List[float],
    atr_5m_values: Optional[List[float]] = None,
    adx_values: Optional[List[float]] = None,
    force: bool = False,
    trigger: str = "auto"
) -> Tuple[MarketRegime, bool]:
    """
    Version V2 complète du check_regime.
    
    Intègre:
    - Médiane (anti-outliers)
    - Hystérésis (anti-flip-flop)
    - Lissage EMA (stabilité temporelle)
    - ATR 5m combiné
    - Seuils ajustés par session
    
    Returns:
        Tuple (régime_actuel, changement_effectué)
    """
    v2_enabled = get_effective_value('market_regime_v2_enabled') or False
    
    # Fallback V1 si désactivé
    if not v2_enabled:
        return await self.check_regime(atr_1m_values, adx_values, force, trigger)
    
    now = datetime.now()
    
    # Stocker métriques
    self.atr_values = atr_1m_values
    self.atr_sample_count = len(atr_1m_values)
    
    # === ÉTAPE 1: Calcul ATR combiné ===
    combined_atr = self.calculate_combined_atr(atr_1m_values, atr_5m_values or [])
    
    # === ÉTAPE 2: Lissage temporel ===
    smoothed_atr = self.apply_smoothing(combined_atr)
    
    # === ÉTAPE 3: Seuils ajustés session ===
    thresholds = self.get_session_adjusted_thresholds()
    
    # === ÉTAPE 4: Calculer ADX ===
    avg_adx = sum(adx_values) / len(adx_values) if adx_values else 25.0
    self.avg_adx = avg_adx
    self.avg_atr = smoothed_atr
    
    # === ÉTAPE 5: Déterminer régime proposé ===
    proposed_regime = self._determine_regime_v2(smoothed_atr, avg_adx, thresholds)
    
    # === ÉTAPE 6: Appliquer hystérésis ===
    should_change = self.should_change_regime(
        self.current_regime, proposed_regime, smoothed_atr
    )
    
    # === ÉTAPE 7: Vérifier durée minimum ===
    min_duration = get_effective_value('market_regime_min_duration_minutes') or 30
    if should_change and self.regime_since and not force:
        duration = (now - self.regime_since).total_seconds() / 60
        if duration < min_duration:
            should_change = False
            logger.debug(f"⏱️ Durée min: {duration:.1f}/{min_duration} min - changement bloqué")
    
    # === ÉTAPE 8: Appliquer changement ===
    old_regime = self.current_regime
    changed = False
    
    if should_change:
        self.current_regime = proposed_regime
        self.current_config = self.regime_configs.get(proposed_regime.value)
        self.regime_since = now
        changed = True
        
        logger.info(
            f"🌡️ RÉGIME V2: {old_regime.value} → {proposed_regime.value} | "
            f"ATR={smoothed_atr:.3f}% | Session={thresholds.get('session', 'N/A')}"
        )
        
        self._log_regime_change_to_db(old_regime, proposed_regime, trigger)
        self._notify_regime_change(old_regime, proposed_regime)
    else:
        logger.debug(
            f"🌡️ Régime stable: {self.current_regime.value} | "
            f"ATR={smoothed_atr:.3f}%"
        )
    
    # MAJ timestamps
    self.last_check = now
    self.next_check = now + self.check_interval
    
    return self.current_regime, changed


def _determine_regime_v2(
    self,
    atr: float,
    adx: float,
    thresholds: Dict[str, float]
) -> MarketRegime:
    """Détermine le régime avec seuils potentiellement ajustés"""
    adx_choppy = get_effective_value('market_regime_threshold_adx_choppy') or 20
    
    if adx < adx_choppy:
        return MarketRegime.CHOPPY
    
    if atr < thresholds['calme_max']:
        return MarketRegime.CALME
    elif atr < thresholds['normal_max']:
        return MarketRegime.NORMAL
    else:
        return MarketRegime.VOLATILE
```

---

## 1B.2 Intégration dans `main.py`

### Modifier `scan_top_pairs_task()` pour utiliser V2

```python
# Dans scan_top_pairs_task(), remplacer l'appel à check_regime

# AVANT (V1):
# await regime_selector.check_regime(atr_values, adx_values, force=True)

# APRÈS (V2):
from utils.effective_config import get_effective_value

v2_enabled = get_effective_value('market_regime_v2_enabled') or False

if v2_enabled:
    # Collecter ATR 5m aussi
    atr_5m_values = []
    for pair_data in scanned_pairs:
        if 'atr_5m_pct' in pair_data:
            atr_5m_values.append(pair_data['atr_5m_pct'])
    
    await regime_selector.check_regime_v2(
        atr_values, 
        atr_5m_values,
        adx_values, 
        force=True
    )
else:
    await regime_selector.check_regime(atr_values, adx_values, force=True)
```

---

## 1B.3 Checklist Phase 1B

```
[ ] 1. Ajouter imports dans market_regime_selector.py
[ ] 2. Implémenter calculate_atr_metric()
[ ] 3. Implémenter apply_smoothing()
[ ] 4. Implémenter should_change_regime()
[ ] 5. Implémenter calculate_combined_atr()
[ ] 6. Implémenter get_session_adjusted_thresholds()
[ ] 7. Implémenter check_regime_v2()
[ ] 8. Modifier main.py pour appeler check_regime_v2
[ ] 9. Modifier _log_regime_change_to_db() pour detection_method='RULE_BASED_V2'
[ ] 10. Ajouter toggles frontend (VariablesPanel.svelte)
[ ] 11. Tester avec v2_enabled=false (comportement V1)
[ ] 12. Activer toggles un par un et vérifier
[ ] 13. Script vérification Phase 1B
```

---

# PHASE 1C: WHAT-IF RÉGIME (3h)

## 1C.1 Extension `what_if_simulator.py`

```python
def simulate_regime_scenarios(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simule le PnL avec les paramètres de chaque régime.
    
    Returns:
        Dict avec pnl_if_calme/normal/volatile et optimal_regime_retrospective
    """
    from core.market_regime_selector import DEFAULT_REGIME_CONFIGS
    
    entry_price = trade_data.get('entry_price', 0)
    exit_price = trade_data.get('exit_price', 0)
    direction = trade_data.get('direction', 'LONG')
    atr_pct = trade_data.get('entry_atr_pct_1m', 0.5)  # ATR au moment de l'entrée
    
    if not entry_price or not exit_price:
        return {}
    
    results = {}
    
    for regime_name, config in DEFAULT_REGIME_CONFIGS.items():
        if regime_name == "CHOPPY":
            continue
        
        # Calculer SL/TP avec les params de ce régime
        sl_distance_pct = atr_pct * config.atr_mult_sl / 100
        tp_distance_pct = atr_pct * config.atr_mult_tp / 100
        
        if direction == 'LONG':
            sim_sl = entry_price * (1 - sl_distance_pct)
            sim_tp = entry_price * (1 + tp_distance_pct)
        else:
            sim_sl = entry_price * (1 + sl_distance_pct)
            sim_tp = entry_price * (1 - tp_distance_pct)
        
        # Simuler: où le trade aurait fermé?
        # Simplification: on utilise le exit_price réel
        # En réalité, il faudrait le price path complet
        
        if direction == 'LONG':
            if exit_price <= sim_sl:
                sim_pnl = -sl_distance_pct * 100
            elif exit_price >= sim_tp:
                sim_pnl = tp_distance_pct * 100
            else:
                sim_pnl = ((exit_price - entry_price) / entry_price) * 100
        else:
            if exit_price >= sim_sl:
                sim_pnl = -sl_distance_pct * 100
            elif exit_price <= sim_tp:
                sim_pnl = tp_distance_pct * 100
            else:
                sim_pnl = ((entry_price - exit_price) / entry_price) * 100
        
        results[f"pnl_if_{regime_name.lower()}_params"] = round(sim_pnl, 4)
    
    # Déterminer le régime optimal
    if results:
        best_key = max(results, key=results.get)
        results["optimal_regime_retrospective"] = best_key.replace("pnl_if_", "").replace("_params", "").upper()
    
    return results
```

## 1C.2 Intégration dans `position_manager.py`

```python
# Dans close_position(), après les calculs What-If existants:

# === PHASE 1C: What-If Régime ===
try:
    from core.analysis.what_if_simulator import WhatIfSimulator
    
    whatif = WhatIfSimulator()
    
    regime_whatif_data = {
        'entry_price': entry_price,
        'exit_price': exit_price,
        'direction': direction,
        'entry_atr_pct_1m': self.active_position.get('entry_atr_pct_1m', 0.5),
    }
    
    regime_results = whatif.simulate_regime_scenarios(regime_whatif_data)
    
    if regime_results:
        # Update trade_atr_metrics
        pg_logger.update_trade_atr_metrics(trade_id, regime_results)
        
        logger.info(
            f"📊 What-If Régime: optimal={regime_results.get('optimal_regime_retrospective')} | "
            f"CALME={regime_results.get('pnl_if_calme_params', 'N/A')}% | "
            f"NORMAL={regime_results.get('pnl_if_normal_params', 'N/A')}% | "
            f"VOLATILE={regime_results.get('pnl_if_volatile_params', 'N/A')}%"
        )
except Exception as e:
    logger.debug(f"What-If Régime error (non-blocking): {e}")
```

---

## VALIDATION PHASE 1 COMPLÈTE

```bash
# Exécuter tous les tests de vérification
python verification/verify_phase_1a_logging.py
python verification/verify_phase_1b_regime_v2.py
python verification/verify_phase_1c_whatif_regime.py

# Vérifier les vues SQL
psql -c "SELECT * FROM v_performance_by_session;"
psql -c "SELECT * FROM v_optimal_regime_analysis;"
```

**Phase 1 terminée quand:**
- ✅ Tous les trades ont session_market rempli
- ✅ Régime V2 activable par toggle
- ✅ Hystérésis bloque les flip-flops
- ✅ What-If Régime calcule optimal_regime_retrospective
