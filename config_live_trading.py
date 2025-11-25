#!/usr/bin/env python3
"""
Configuration RECOMMANDÉE pour Trading LIVE sur MEXC
⚠️ Ajustée pour tenir compte des VRAIES contraintes de l'API
"""

# ============================================================================
# CONFIGURATION LIVE TRADING - MEXC API
# ============================================================================

LIVE_TRADING_CONFIG = {
    # ========================================================================
    # TP/SL - AJUSTÉS POUR LATENCE API (200-500ms)
    # ========================================================================
    "tp_sl_mode": "FIXE",

    # 🔥 LIVE: TP/SL minimum 0.8% pour couvrir latence + slippage
    # Règle: TP doit être > 2x la latence potentielle
    "tp_percent": 1.0,   # +1.0% (au lieu de 0.50%)
    "sl_percent": 0.5,   # -0.5% (au lieu de 0.20%)

    # 🔥 LIVE: Break-even déclenché plus tard (laisser le trade respirer)
    "break_even_trigger": 0.6,  # +0.6% (au lieu de 0.3%)

    # 🔥 LIVE: Trailing distance plus large (tolérer les micro-fluctuations)
    "trailing_distance": 0.3,  # 0.3% (au lieu de 0.15%)

    # ========================================================================
    # DURÉE MINIMALE DES TRADES
    # ========================================================================
    # 🔥 CRITIQUE: Empêcher trades < 5 secondes (impossible à exécuter en live)
    "min_trade_duration_seconds": 5,  # 5 secondes minimum

    # 🔥 LIVE: Ne pas fermer si trade trop récent (éviter spam API)
    "min_position_age_before_close": 3.0,  # 3 secondes avant de pouvoir fermer

    # ========================================================================
    # TRAILING STOP - AJUSTÉ POUR LIVE
    # ========================================================================
    "trailing_enabled": True,

    # 🔥 LIVE: Trigger plus haut (éviter activation trop rapide)
    "trailing_trigger_pnl": 0.5,  # +0.5% (au lieu de 0.15%)

    # Configuration ATR mode
    "atr_mult_tp": 2.0,  # 2.0x ATR (au lieu de 1.5x)
    "atr_mult_sl": 1.2,  # 1.2x ATR (au lieu de 1.0x)
    "atr_min": 0.3,      # 0.3% min (au lieu de 0.15%)
    "atr_max": 2.0,      # 2.0% max (au lieu de 1.5%)

    # ========================================================================
    # FILTRES DE QUALITÉ - PLUS STRICTS POUR LIVE
    # ========================================================================
    # 🔥 LIVE: Score minimum plus élevé (moins de trades, meilleure qualité)
    "min_score_required": 8.0,  # 8.0 (au lieu de 6.5)
    "min_score_adx_high": 7.5,  # 7.5 si ADX > 30
    "min_score_adx_low": 8.5,   # 8.5 si ADX < 25

    # 🔥 LIVE: Filtres plus stricts
    "snr_threshold": 0.25,       # 0.25% (au lieu de 0.15%)
    "breakout_threshold": 0.40,  # 0.40 (au lieu de 0.25)
    "wick_ratio_max": 3.0,       # 3.0 (au lieu de 4.5)
    "di_gap_min": 5.0,           # 5.0 (au lieu de 4.0)

    # ATR optimal range (plus strict)
    "optimal_atr_min_1m": 0.20,  # 0.20% min (au lieu de 0.12%)
    "optimal_atr_max_1m": 0.60,  # 0.60% max (au lieu de 0.75%)
    "optimal_atr_min_5m": 0.30,  # 0.30% min
    "optimal_atr_max_5m": 1.20,  # 1.20% max

    # ========================================================================
    # VOLUME & SPREAD - CRITIQUES POUR EXÉCUTION
    # ========================================================================
    # 🔥 LIVE: Volume multiplier plus élevé (s'assurer liquidité suffisante)
    "volume_multiplier": 1.2,  # 1.2x (au lieu de 0.95x)

    # 🔥 LIVE: Spread maximum acceptable (éviter paires illiquides)
    "max_spread_pct": 0.10,  # 0.10% max (rejeter si spread > 0.10%)

    # 🔥 LIVE: Slippage maximum toléré
    "max_slippage_pct": 0.05,  # 0.05% max (3% était trop permissif)

    # ========================================================================
    # EARLY INVALIDATION - AJUSTÉ POUR LIVE
    # ========================================================================
    # 🔥 LIVE: Fenêtre plus longue (laisser le trade se développer)
    "early_invalidation_window": 30,  # 30 secondes (au lieu de 15-20s)
    "early_invalidation_threshold": -0.15,  # -0.15% (au lieu de -0.10%)

    # ========================================================================
    # RATE LIMITING - PROTECTION API MEXC
    # ========================================================================
    # 🔥 MEXC LIMITS: 20 req/s, 10 orders/s
    "max_orders_per_second": 5,    # 5 ordres/s max (sécurité)
    "max_requests_per_second": 10,  # 10 req/s max (sécurité)

    # Cooldown entre trades sur même paire
    "min_cooldown_between_trades": 30,  # 30 secondes entre 2 trades sur même paire

    # ========================================================================
    # RISK MANAGEMENT - PLUS CONSERVATEUR EN LIVE
    # ========================================================================
    "account_size": 1000.0,     # Taille compte
    "risk_per_trade": 1.0,      # 1.0% par trade (au lieu de 2.0%)
    "max_daily_loss": -3.0,     # -3.0% max par jour
    "max_concurrent_positions": 1,  # 1 position max (scalping focus)

    # ========================================================================
    # AUTRES PARAMÈTRES
    # ========================================================================
    "trend_timeframe": "15m",
    "use_confluence": True,
    "use_weighted_scoring": True,

    # Patterns (tous activés)
    "use_breakout": True,
    "use_snr": True,
    "use_wick": True,
    "use_divergence": True,
    "use_engulfing": True,
    "use_hammer": True,
    "use_shooting_star": True,
    "use_doji": True,
    "use_marubozu": True,
    "use_morning_star": True,
    "use_evening_star": True,
}


# ============================================================================
# COMPARAISON CONFIG BACKTEST vs LIVE
# ============================================================================

COMPARISON_TABLE = """
╔═══════════════════════════════════════════════════════════════════════════╗
║                     BACKTEST vs LIVE TRADING CONFIG                       ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  PARAMÈTRE              │  BACKTEST (actuel)  │  LIVE (recommandé)        ║
╠═════════════════════════╪═════════════════════╪═══════════════════════════╣
║  TP %                   │  0.50%              │  1.0%   (2x plus large)   ║
║  SL %                   │  0.20%              │  0.5%   (2.5x plus large) ║
║  Break-even trigger     │  0.30%              │  0.6%   (2x plus haut)    ║
║  Trailing distance      │  0.15%              │  0.3%   (2x plus large)   ║
║  Trailing trigger       │  0.15%              │  0.5%   (3x plus haut)    ║
║  Min score required     │  6.5                │  8.0    (plus strict)     ║
║  Risk per trade         │  2.0%               │  1.0%   (plus conservateur║
║  Min trade duration     │  AUCUN              │  5s     (CRITIQUE!)       ║
║  Max spread             │  AUCUN              │  0.10%  (CRITIQUE!)       ║
║  Volume multiplier      │  0.95x              │  1.2x   (plus strict)     ║
║  Early invalidation     │  15-20s             │  30s    (plus tolérant)   ║
╚═════════════════════════╧═════════════════════╧═══════════════════════════╝

RÈGLE D'OR LIVE TRADING:
┌─────────────────────────────────────────────────────────────────────────┐
│ Durée minimale trade = (Latence API × 2) + (Buffer sécurité)           │
│                      = (500ms × 2) + 4000ms                             │
│                      = 5000ms = 5 secondes MINIMUM                      │
└─────────────────────────────────────────────────────────────────────────┘

LATENCES TYPIQUES MEXC:
- REST API call:        100-300ms
- Order placement:      50-150ms
- WebSocket update:     50-100ms
- Total par opération:  200-550ms
- Total pour 1 trade:   400-1100ms (entrée + sortie)

RISQUE AVEC CONFIG ACTUELLE (backtest):
├─ Trades de 1s → IMPOSSIBLE à exécuter en live
├─ TP 0.50% → Mangé par slippage + latence
├─ SL 0.20% → Dépassé avant exécution de l'ordre
└─ Résultat: Perte garantie sur la majorité des trades
"""


# ============================================================================
# RECOMMANDATIONS AVANT DE PASSER EN LIVE
# ============================================================================

RECOMMENDATIONS = """
╔═══════════════════════════════════════════════════════════════════════════╗
║                   CHECKLIST AVANT LIVE TRADING                            ║
╠═══════════════════════════════════════════════════════════════════════════╣

 ✅ 1. TESTER EN PAPER TRADING AVEC CONFIG LIVE
    └─ Utiliser config_live_trading.py pendant 1 semaine minimum
    └─ Vérifier que durée moyenne des trades > 10 secondes
    └─ Confirmer que slippage réel < 0.05%

 ✅ 2. VÉRIFIER CONNEXION API MEXC
    └─ Mesurer latence réelle avec votre serveur
    └─ Tester pendant heures de pic (Asia, Europe, US sessions)
    └─ Confirmer rate limits respectés

 ✅ 3. SÉLECTIONNER PAIRES ADAPTÉES
    └─ Volume 24h > $5M minimum
    └─ Spread moyen < 0.08%
    └─ Orderbook depth > $50k à ±0.5%
    └─ Éviter paires trop volatiles (BTC, ETH mieux que shitcoins)

 ✅ 4. DÉMARRER PETIT
    └─ Account size test: $100-500 max
    └─ Risk per trade: 0.5-1.0% max
    └─ Max 3-5 trades/jour les premiers jours
    └─ Analyser chaque trade individuellement

 ✅ 5. MONITORING STRICT
    └─ Logger TOUTES les latences API
    └─ Comparer prix théorique vs prix exécuté
    └─ Tracker slippage réel par paire
    └─ Arrêter si slippage moyen > 0.10%

 ✅ 6. SÉCURITÉ
    └─ API keys avec permissions LIMITÉES (spot trading only)
    └─ IP whitelist activée
    └─ 2FA obligatoire
    └─ Withdrawal permissions DÉSACTIVÉES sur API keys

╚═══════════════════════════════════════════════════════════════════════════╝
"""


if __name__ == "__main__":
    print(COMPARISON_TABLE)
    print("\n")
    print(RECOMMENDATIONS)
