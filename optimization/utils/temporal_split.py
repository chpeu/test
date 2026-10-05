"""
Temporal Train-Test Split pour Trading ML
Évite le data leakage en respectant l'ordre chronologique
"""
import pandas as pd
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def temporal_train_test_split(
    df: pd.DataFrame,
    target_col: str = 'target_win',
    test_size: float = 0.2,
    validation_size: float = 0.1,
    timestamp_col: str = 'timestamp'
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split temporel: Train → Validation → Test

    CRITIQUE pour trading: Ne JAMAIS mélanger passé et futur

    Args:
        df: DataFrame avec timestamp
        target_col: Colonne target
        test_size: % des données les plus récentes pour test
        validation_size: % pour validation
        timestamp_col: Colonne timestamp

    Returns:
        train_df, val_df, test_df (chronologiquement ordonnés)
    """
    # 🔥 FIX: Vérifier si DataFrame vide ou colonnes manquantes
    if df is None or len(df) == 0:
        logger.warning("⚠️ DataFrame vide fourni à temporal_train_test_split - retour DataFrames vides")
        empty_df = pd.DataFrame()
        return empty_df, empty_df, empty_df
    
    if timestamp_col not in df.columns:
        logger.warning(f"⚠️ Colonne timestamp '{timestamp_col}' manquante - utilisation de l'index")
        # Créer une colonne timestamp artificielle basée sur l'index
        df = df.copy()
        df[timestamp_col] = range(len(df))
    
    # Trier par timestamp
    try:
        df_sorted = df.sort_values(timestamp_col).reset_index(drop=True)
    except Exception as e:
        logger.warning(f"⚠️ Erreur lors du tri par timestamp: {e} - utilisation des données sans tri")
        df_sorted = df.copy().reset_index(drop=True)

    n = len(df_sorted)
    
    # 🔥 FIX: Vérifier minimum d'échantillons pour split
    if n < 3:
        logger.warning(f"⚠️ Pas assez d'échantillons ({n}) pour split temporel - retour données dans train uniquement")
        return df_sorted.copy(), pd.DataFrame(columns=df.columns), pd.DataFrame(columns=df.columns)

    # Calculer indices de split
    test_start_idx = max(1, int(n * (1 - test_size)))
    val_start_idx = max(1, int(n * (1 - test_size - validation_size)))
    
    # S'assurer qu'on a au moins 1 échantillon dans chaque split
    if val_start_idx >= test_start_idx:
        val_start_idx = max(1, test_start_idx - 1)
    if val_start_idx <= 0:
        val_start_idx = 1

    # Split
    train_df = df_sorted.iloc[:val_start_idx].copy()
    val_df = df_sorted.iloc[val_start_idx:test_start_idx].copy()
    test_df = df_sorted.iloc[test_start_idx:].copy()

    # Stats
    logger.info("=" * 60)
    logger.info("📅 TEMPORAL SPLIT (chronologique)")
    logger.info("=" * 60)
    logger.info(f"Train: {len(train_df)} samples | {train_df[timestamp_col].min()} → {train_df[timestamp_col].max()}")
    logger.info(f"Val:   {len(val_df)} samples | {val_df[timestamp_col].min()} → {val_df[timestamp_col].max()}")
    logger.info(f"Test:  {len(test_df)} samples | {test_df[timestamp_col].min()} → {test_df[timestamp_col].max()}")

    # Distribution classes
    if target_col in df.columns:
        train_win = (train_df[target_col] == 1).mean() * 100
        val_win = (val_df[target_col] == 1).mean() * 100
        test_win = (test_df[target_col] == 1).mean() * 100

        logger.info(f"\nWin% Train: {train_win:.1f}% | Val: {val_win:.1f}% | Test: {test_win:.1f}%")

        # Alerte si déséquilibre temporel
        if abs(train_win - test_win) > 15:
            logger.warning(
                f"⚠️ ALERTE: Win% varie de {abs(train_win - test_win):.1f}% entre train et test"
            )
            logger.warning("Cela peut indiquer: 1) Changement de stratégie 2) Conditions marché différentes")

    logger.info("=" * 60)

    return train_df, val_df, test_df


def walk_forward_validation(
    df: pd.DataFrame,
    n_splits: int = 5,
    train_size: float = 0.7,
    timestamp_col: str = 'timestamp'
):
    """
    Walk-Forward Validation: Simule trading réel

    Chaque fold avance dans le temps:
    Fold 1: Train[0:70%]    → Test[70:80%]
    Fold 2: Train[0:75%]    → Test[75:85%]
    Fold 3: Train[0:80%]    → Test[80:90%]
    ...

    Returns:
        Liste de (train_df, test_df) pour chaque fold
    """
    df_sorted = df.sort_values(timestamp_col).reset_index(drop=True)
    n = len(df_sorted)

    folds = []

    for i in range(n_splits):
        # Calculer indices progressifs
        train_end_idx = int(n * (train_size + i * (1 - train_size) / n_splits))
        test_end_idx = min(int(train_end_idx + n * (1 - train_size) / n_splits), n)

        train_df = df_sorted.iloc[:train_end_idx].copy()
        test_df = df_sorted.iloc[train_end_idx:test_end_idx].copy()

        logger.info(
            f"Fold {i+1}: Train[0:{train_end_idx}] → Test[{train_end_idx}:{test_end_idx}]"
        )

        folds.append((train_df, test_df))

    return folds
