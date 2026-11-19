"""Un petit jeu de donnees ML synthetique, partage par les tests d'entrainement.

Le format est celui que le scanneur laisse dans PostgreSQL : une ligne par prise
de position, colonnes = features connues du moteur (rsi, macd, adx, bandes de
Bollinger, volume...) + deux colonnes a predire (`target_win`, `target_pnl`).

260 prises suffisent : assez pour que sklearn et xgboost fassent un vrai
apprentissage (avec un vrai score), assez peu pour que la suite de tests reste
sous la seconde par tour.
"""

import random

import pandas as pd

NB_PRISES = 260


def jeu_de_donnees(nb=NB_PRISES, graine=7):
    """Construit un jeu ou `target_win` est reellement lie a `adx_1m`.

    Le lien existe (force > 30 et macd positif = prise gagnante) : un modele qui
    apprend doit donc battre un modele qui répond au hasard, et les scores
    annonces dans les tests ont une signification.
    """
    rnd = random.Random(graine)
    lignes = []
    base_ts = 1_730_000_000

    for i in range(nb):
        adx = rnd.uniform(12, 55)
        rsi_1m = rnd.uniform(25, 75)
        rsi_5m = rnd.uniform(25, 75)
        macd = rnd.uniform(-0.6, 0.6)
        direction = 1 if (adx > 30 and macd > 0) else -1
        pnl = rnd.uniform(0.4, 4.5) * direction
        gagne = 1 if pnl > 0 else 0

        lignes.append(
            {
                "scan_id": f"scan-{i}",
                "timestamp": base_ts + i * 3600,
                "symbol": "BTC/USDT",
                "price": rnd.uniform(20000, 70000),
                "target_win": gagne,
                "target_pnl": abs(pnl) * direction,
                "is_opportunity": 1,
                "is_manual": 0,
                "rsi_1m": rsi_1m,
                "rsi_5m": rsi_5m,
                "rsi_prev_1m": rsi_1m - rnd.uniform(-2, 2),
                "macd_hist_1m": macd,
                "macd_hist_5m": macd + rnd.uniform(-0.1, 0.1),
                "macd_hist_prev_1m": macd - rnd.uniform(-0.05, 0.05),
                "adx_1m": adx,
                "di_gap_1m": rnd.uniform(-20, 20),
                "bb_distance_to_lower_1m": rnd.uniform(0.01, 1.5),
                "bb_distance_to_upper_1m": rnd.uniform(0.01, 1.5),
                "bb_width_1m": rnd.uniform(0.05, 1.2),
                "atr_pct_1m": rnd.uniform(0.1, 1.4),
                "atr_pct_5m": rnd.uniform(0.1, 1.6),
                "volume_ratio_1m": rnd.uniform(0.4, 2.5),
                "volume_spike_1m": rnd.uniform(0.5, 3.0),
                "ema_diff_pct_1m": rnd.uniform(-0.4, 0.4),
                "ema_diff_pct_5m": rnd.uniform(-0.4, 0.4),
            }
        )

    return pd.DataFrame(lignes)
