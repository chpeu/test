"""
EDA (Exploratory Data Analysis) pour Trading ML
Identifie les problèmes de données et features
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, List
import matplotlib
matplotlib.use('Agg')  # Backend non-interactif
import matplotlib.pyplot as plt
import seaborn as sns

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features

logger = logging.getLogger(__name__)


def analyze_label_quality(df: pd.DataFrame, target_col: str = 'target_win') -> Dict:
    """
    Analyse qualité des labels win/loss

    Problèmes fréquents:
    - Déséquilibre extrême (>80% dans une classe)
    - Labels incohérents (win avec PNL négatif)
    - Trop de trades marginaux (PNL proche de 0)
    """
    logger.info("=" * 60)
    logger.info("🎯 ANALYSE QUALITÉ DES LABELS")
    logger.info("=" * 60)

    # Distribution basique
    win_count = (df[target_col] == 1).sum()
    loss_count = (df[target_col] == 0).sum()
    win_pct = win_count / len(df) * 100

    logger.info(f"Wins: {win_count} ({win_pct:.1f}%)")
    logger.info(f"Loss: {loss_count} ({100-win_pct:.1f}%)")

    # Incohérences (si target_pnl disponible)
    if 'target_pnl' in df.columns:
        # Wins avec PNL négatif
        false_wins = df[(df[target_col] == 1) & (df['target_pnl'] < 0)]
        # Loss avec PNL positif
        false_losses = df[(df[target_col] == 0) & (df['target_pnl'] > 0)]

        logger.info(f"\n⚠️ INCOHÉRENCES:")
        logger.info(f"  - Wins avec PNL < 0: {len(false_wins)} ({len(false_wins)/len(df)*100:.1f}%)")
        logger.info(f"  - Loss avec PNL > 0: {len(false_losses)} ({len(false_losses)/len(df)*100:.1f}%)")

        # Trades marginaux (PNL proche de 0 = bruit)
        marginal_threshold = 0.1  # 0.1% de variation
        marginal_trades = df[abs(df['target_pnl']) < marginal_threshold]

        logger.info(f"\n📊 Trades marginaux (|PNL| < {marginal_threshold}%):")
        logger.info(f"  - Count: {len(marginal_trades)} ({len(marginal_trades)/len(df)*100:.1f}%)")
        logger.info(f"  → Recommandation: Exclure du training (bruit aléatoire)")

    # Déséquilibre
    if win_pct < 30 or win_pct > 70:
        logger.warning(f"\n⚠️ DÉSÉQUILIBRE IMPORTANT: {win_pct:.1f}% wins")
        logger.warning("Recommandations:")
        logger.warning("  1. Utiliser scale_pos_weight")
        logger.warning("  2. SMOTE (oversampling)")
        logger.warning("  3. Focal Loss")

    logger.info("=" * 60)

    return {
        'win_count': win_count,
        'loss_count': loss_count,
        'win_pct': win_pct,
        'marginal_trades': len(marginal_trades) if 'target_pnl' in df.columns else 0,
    }


def analyze_feature_distributions(
    df: pd.DataFrame,
    target_col: str = 'target_win',
    top_n: int = 20
) -> pd.DataFrame:
    """
    Analyse distributions features: Win vs Loss

    Identifie features discriminantes en comparant:
    - Moyenne win vs loss
    - Écart-type
    - KS statistic (séparabilité)
    """
    logger.info("=" * 60)
    logger.info("📊 ANALYSE DISTRIBUTIONS FEATURES (Win vs Loss)")
    logger.info("=" * 60)

    # Séparer données
    df_win = df[df[target_col] == 1]
    df_loss = df[df[target_col] == 0]

    # Colonnes features
    exclude_cols = ['scan_id', 'timestamp', 'symbol', target_col, 'target_pnl', 'is_opportunity']
    feature_cols = [col for col in df.columns if col not in exclude_cols]

    results = []

    for col in feature_cols:
        # Skip non-numeric
        if df[col].dtype == 'object':
            continue

        # Stats win
        mean_win = df_win[col].mean()
        std_win = df_win[col].std()

        # Stats loss
        mean_loss = df_loss[col].mean()
        std_loss = df_loss[col].std()

        # Différence relative
        if abs(mean_loss) > 1e-10:
            diff_pct = abs(mean_win - mean_loss) / abs(mean_loss) * 100
        else:
            diff_pct = 0

        # Kolmogorov-Smirnov test (séparabilité)
        from scipy.stats import ks_2samp
        ks_stat, ks_pvalue = ks_2samp(
            df_win[col].dropna(),
            df_loss[col].dropna()
        )

        results.append({
            'feature': col,
            'mean_win': mean_win,
            'mean_loss': mean_loss,
            'diff_pct': diff_pct,
            'std_win': std_win,
            'std_loss': std_loss,
            'ks_stat': ks_stat,
            'ks_pvalue': ks_pvalue,
            'separable': ks_pvalue < 0.05  # Significativement différent
        })

    results_df = pd.DataFrame(results)

    # Trier par KS stat (features les plus discriminantes)
    results_df = results_df.sort_values('ks_stat', ascending=False)

    logger.info(f"\n🔝 TOP {top_n} FEATURES DISCRIMINANTES:")
    logger.info("-" * 80)
    logger.info(f"{'Feature':<30} {'Mean Win':>10} {'Mean Loss':>10} {'Diff%':>8} {'KS Stat':>8}")
    logger.info("-" * 80)

    for i, row in results_df.head(top_n).iterrows():
        logger.info(
            f"{row['feature']:<30} {row['mean_win']:>10.4f} {row['mean_loss']:>10.4f} "
            f"{row['diff_pct']:>7.1f}% {row['ks_stat']:>8.4f}"
        )

    # Features non-discriminantes (à exclure ?)
    non_discriminant = results_df[results_df['ks_pvalue'] > 0.1]
    logger.info(f"\n⚠️ Features NON-DISCRIMINANTES (p-value > 0.1): {len(non_discriminant)}")
    if len(non_discriminant) > 0:
        logger.info(f"Exclure: {list(non_discriminant['feature'].head(10))}")

    logger.info("=" * 60)

    return results_df


def detect_data_leakage(df: pd.DataFrame, target_col: str = 'target_win') -> Dict:
    """
    Détecte data leakage (features qui "connaissent" le futur)

    Signes de leakage:
    - Features avec corrélation parfaite (>0.95) avec target
    - Features contenant "pnl", "exit", "profit" dans le nom
    """
    logger.info("=" * 60)
    logger.info("🔍 DÉTECTION DATA LEAKAGE")
    logger.info("=" * 60)

    exclude_cols = ['scan_id', 'timestamp', 'symbol', target_col, 'target_pnl', 'is_opportunity']
    feature_cols = [col for col in df.columns if col not in exclude_cols]

    # Corrélations avec target
    correlations = []
    for col in feature_cols:
        if df[col].dtype in ['int64', 'float64', 'bool']:
            corr = df[col].corr(df[target_col])
            correlations.append({'feature': col, 'correlation': abs(corr)})

    corr_df = pd.DataFrame(correlations).sort_values('correlation', ascending=False)

    # Features suspectes (corrélation très haute)
    suspicious = corr_df[corr_df['correlation'] > 0.8]

    logger.info("⚠️ FEATURES SUSPECTES (corrélation > 0.8 avec target):")
    if len(suspicious) > 0:
        for _, row in suspicious.iterrows():
            logger.info(f"  - {row['feature']}: {row['correlation']:.4f}")
        logger.warning("  → Vérifier si ces features contiennent info du futur!")
    else:
        logger.info("  ✅ Aucune corrélation suspecte détectée")

    # Features avec noms suspects
    leak_keywords = ['pnl', 'profit', 'exit', 'close', 'result']
    leak_features = [col for col in feature_cols if any(kw in col.lower() for kw in leak_keywords)]

    if leak_features:
        logger.warning(f"\n⚠️ Features avec noms suspects: {leak_features}")

    logger.info("=" * 60)

    return {
        'suspicious_features': list(suspicious['feature']) if len(suspicious) > 0 else [],
        'leak_candidates': leak_features
    }


def suggest_new_features(df: pd.DataFrame, results_df: pd.DataFrame) -> List[str]:
    """
    Suggère nouvelles features basées sur analyse

    Basé sur:
    - Features discriminantes actuelles
    - Patterns métier trading
    """
    logger.info("=" * 60)
    logger.info("💡 SUGGESTIONS NOUVELLES FEATURES")
    logger.info("=" * 60)

    suggestions = []

    # Top features discriminantes
    top_features = results_df.head(10)['feature'].tolist()

    # 1. Interactions entre top features
    logger.info("\n1️⃣ INTERACTIONS (produits de features discriminantes):")
    interactions = []
    for i in range(min(3, len(top_features))):
        for j in range(i+1, min(5, len(top_features))):
            interaction = f"{top_features[i]} × {top_features[j]}"
            interactions.append(interaction)

    for inter in interactions[:5]:
        logger.info(f"  - {inter}")
        suggestions.append(inter)

    # 2. Features de contexte marché
    logger.info("\n2️⃣ CONTEXTE MARCHÉ:")
    market_features = [
        "market_regime (trending/ranging/volatile)",
        "trade_hour (session trading)",
        "day_of_week (lundi-vendredi)",
        "recent_volatility_spike (dernière 1h)",
        "market_momentum_alignment (1m/5m/15m aligned)"
    ]
    for feat in market_features:
        logger.info(f"  - {feat}")
        suggestions.append(feat)

    # 3. Features d'historique
    logger.info("\n3️⃣ HISTORIQUE RÉCENT:")
    history_features = [
        "last_3_trades_winrate",
        "last_5_trades_avg_pnl",
        "recent_drawdown (max loss récent)",
        "consecutive_wins",
        "consecutive_losses"
    ]
    for feat in history_features:
        logger.info(f"  - {feat}")
        suggestions.append(feat)

    # 4. Features de qualité signal
    logger.info("\n4️⃣ QUALITÉ SIGNAL:")
    quality_features = [
        "multi_timeframe_confluence_score",
        "pattern_strength (candlestick strength)",
        "volume_confirmation (volume valide pattern)",
        "risk_reward_ratio",
        "entry_timing_score"
    ]
    for feat in quality_features:
        logger.info(f"  - {feat}")
        suggestions.append(feat)

    logger.info("=" * 60)

    return suggestions


def run_full_eda(
    timeframe_days: int = 90,
    min_trades: int = 50,
    save_report: bool = True
) -> Dict:
    """
    EDA complète: Analyse toutes les dimensions

    Returns:
        Dict avec tous les résultats d'analyse
    """
    logger.info("\n" + "=" * 80)
    logger.info("🔬 EXPLORATORY DATA ANALYSIS (EDA) - TRADING ML")
    logger.info("=" * 80 + "\n")

    # 1. Charger données
    logger.info("📥 Chargement données...")
    base_df = load_features_from_postgres(
        timeframe_days=timeframe_days,
        min_trades=min_trades
    )

    df = calculate_derived_features(base_df)

    logger.info(f"✅ {len(df)} trades chargés, {len(df.columns)} features\n")

    # 2. Analyse labels
    label_analysis = analyze_label_quality(df)

    # 3. Analyse distributions
    feature_analysis = analyze_feature_distributions(df, top_n=20)

    # 4. Détection leakage
    leakage_analysis = detect_data_leakage(df)

    # 5. Suggestions
    suggestions = suggest_new_features(df, feature_analysis)

    # 6. Résumé global
    logger.info("\n" + "=" * 80)
    logger.info("📋 RÉSUMÉ & RECOMMANDATIONS")
    logger.info("=" * 80)

    logger.info(f"\n✅ Données: {len(df)} trades")
    logger.info(f"✅ Win rate: {label_analysis['win_pct']:.1f}%")
    logger.info(f"✅ Features: {len(df.columns)}")

    # Diagnostic
    logger.info("\n🔴 PROBLÈMES IDENTIFIÉS:")

    problems = []
    if label_analysis['win_pct'] < 35 or label_analysis['win_pct'] > 65:
        problems.append(f"Déséquilibre classes ({label_analysis['win_pct']:.1f}% wins)")

    if label_analysis.get('marginal_trades', 0) > len(df) * 0.2:
        problems.append(f"Trop de trades marginaux ({label_analysis['marginal_trades']})")

    if len(leakage_analysis['suspicious_features']) > 0:
        problems.append(f"Data leakage possible ({len(leakage_analysis['suspicious_features'])} features)")

    non_separable = feature_analysis[feature_analysis['separable'] == False]
    if len(non_separable) > len(feature_analysis) * 0.5:
        problems.append(f"{len(non_separable)} features non-discriminantes (>50%)")

    if len(problems) == 0:
        logger.info("  ✅ Aucun problème majeur détecté!")
    else:
        for i, prob in enumerate(problems, 1):
            logger.info(f"  {i}. {prob}")

    logger.info("\n💡 ACTIONS PRIORITAIRES:")
    logger.info("  1. Utiliser SPLIT TEMPOREL (pas random)")
    logger.info("  2. Filtrer trades marginaux (PNL proche de 0)")
    logger.info("  3. Utiliser seulement top 30 features discriminantes")
    logger.info("  4. Ajouter features de contexte marché")
    logger.info("  5. Tester walk-forward validation")

    logger.info("=" * 80 + "\n")

    # Sauvegarder rapport
    if save_report:
        report_path = "optimization/analysis/eda_report.txt"
        # TODO: Sauvegarder rapport texte

    return {
        'df': df,
        'label_analysis': label_analysis,
        'feature_analysis': feature_analysis,
        'leakage_analysis': leakage_analysis,
        'suggestions': suggestions,
        'problems': problems
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    results = run_full_eda(timeframe_days=90, min_trades=50)
