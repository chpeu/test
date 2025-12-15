# -*- coding: utf-8 -*-
"""
Analyse et creation de meilleures features pour ameliorer le ML
"""

import sys
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import RobustScaler
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score
from sklearn.utils.class_weight import compute_class_weight
from pathlib import Path
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import time

print("=" * 70)
print("  AMELIORATION DES FEATURES ML")
print("=" * 70)

def load_raw_data():
    """Charge les donnees brutes"""
    env_path = Path('.env')
    env_vars = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
    conn_str = f"postgresql://{env_vars.get('POSTGRES_USER')}:{password}@{env_vars.get('POSTGRES_HOST')}:{env_vars.get('POSTGRES_PORT')}/{env_vars.get('POSTGRES_DB')}"
    engine = create_engine(conn_str)
    
    df = pd.read_sql("SELECT * FROM ml_features WHERE target_pnl IS NOT NULL", engine)
    engine.dispose()
    
    print(f"Donnees chargees: {len(df)} samples")
    return df

def analyze_feature_importance(df):
    """Analyse l'importance de chaque feature"""
    print("\n=== ANALYSE IMPORTANCE DES FEATURES ===")
    
    # Target binaire
    df['target'] = (df['target_pnl'] > 0).astype(int)
    
    # Features numeriques
    exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target', 'scan_id']
    feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]
    
    X = df[feature_cols].fillna(0).values
    y = df['target'].values
    
    # Correlation avec target
    correlations = []
    for i, col in enumerate(feature_cols):
        corr = np.corrcoef(X[:, i], y)[0, 1]
        if not np.isnan(corr):
            correlations.append((col, abs(corr), corr))
    
    correlations.sort(key=lambda x: x[1], reverse=True)
    
    print("\nTop 20 features les plus correlees avec le target:")
    print(f"{'Feature':<40} {'|Corr|':<10} {'Direction'}")
    print("-" * 60)
    for col, abs_corr, corr in correlations[:20]:
        direction = "+" if corr > 0 else "-"
        print(f"{col:<40} {abs_corr:<10.4f} {direction}")
    
    # Mutual Information
    print("\n\nAnalyse Mutual Information...")
    mi_scores = mutual_info_classif(X, y, random_state=42)
    mi_ranking = [(feature_cols[i], mi_scores[i]) for i in range(len(feature_cols))]
    mi_ranking.sort(key=lambda x: x[1], reverse=True)
    
    print("\nTop 20 features par Mutual Information:")
    print(f"{'Feature':<40} {'MI Score':<10}")
    print("-" * 50)
    for col, score in mi_ranking[:20]:
        print(f"{col:<40} {score:<10.4f}")
    
    return correlations, mi_ranking, feature_cols, X, y

def create_new_features(df):
    """Cree de nouvelles features engineered"""
    print("\n=== CREATION DE NOUVELLES FEATURES ===")
    
    df = df.copy()
    new_features = []
    
    # 1. Ratios entre indicateurs
    if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
        df['rsi_ratio_1m_5m'] = df['rsi_1m'] / (df['rsi_5m'] + 1e-6)
        new_features.append('rsi_ratio_1m_5m')
    
    # 2. Difference RSI par rapport a 50 (neutre)
    if 'rsi_1m' in df.columns:
        df['rsi_distance_50_1m'] = abs(df['rsi_1m'] - 50)
        new_features.append('rsi_distance_50_1m')
    
    if 'rsi_5m' in df.columns:
        df['rsi_distance_50_5m'] = abs(df['rsi_5m'] - 50)
        new_features.append('rsi_distance_50_5m')
    
    # 3. Momentum combine
    if 'macd_hist_1m' in df.columns and 'rsi_1m' in df.columns:
        # Normaliser et combiner
        df['momentum_combined'] = (df['macd_hist_1m'] / (abs(df['macd_hist_1m']).max() + 1e-6)) * ((df['rsi_1m'] - 50) / 50)
        new_features.append('momentum_combined')
    
    # 4. Volatilite relative
    if 'atr_pct_1m' in df.columns and 'atr_pct_5m' in df.columns:
        df['volatility_ratio'] = df['atr_pct_1m'] / (df['atr_pct_5m'] + 1e-6)
        new_features.append('volatility_ratio')
    
    # 5. Force de tendance
    if 'adx_1m' in df.columns and 'di_gap_1m' in df.columns:
        df['trend_strength'] = df['adx_1m'] * abs(df['di_gap_1m'])
        new_features.append('trend_strength')
    
    # 6. Confluence score
    confluence_cols = [c for c in df.columns if 'passed' in c.lower()]
    if confluence_cols:
        df['confluence_score'] = df[confluence_cols].sum(axis=1)
        new_features.append('confluence_score')
    
    # 7. RSI momentum (changement)
    if 'rsi_1m' in df.columns and 'rsi_prev_1m' in df.columns:
        df['rsi_momentum'] = df['rsi_1m'] - df['rsi_prev_1m']
        new_features.append('rsi_momentum')
    
    # 8. MACD acceleration
    if 'macd_hist_1m' in df.columns and 'macd_hist_prev_1m' in df.columns:
        df['macd_acceleration'] = df['macd_hist_1m'] - df['macd_hist_prev_1m']
        new_features.append('macd_acceleration')
    
    # 9. Volume pressure
    if 'volume_ratio_1m' in df.columns and 'volume_spike_1m' in df.columns:
        df['volume_pressure'] = df['volume_ratio_1m'] * df['volume_spike_1m']
        new_features.append('volume_pressure')
    
    # 10. BB squeeze indicator
    if 'bb_width_1m' in df.columns:
        df['bb_squeeze'] = 1 / (df['bb_width_1m'] + 1e-6)
        new_features.append('bb_squeeze')
    
    # 11. Price position dans BB
    if 'bb_distance_to_lower_1m' in df.columns and 'bb_distance_to_upper_1m' in df.columns:
        df['bb_position'] = df['bb_distance_to_lower_1m'] / (df['bb_distance_to_lower_1m'] + df['bb_distance_to_upper_1m'] + 1e-6)
        new_features.append('bb_position')
    
    # 12. EMA trend strength
    if 'ema_diff_pct_1m' in df.columns and 'ema_diff_pct_5m' in df.columns:
        df['ema_trend_aligned'] = np.sign(df['ema_diff_pct_1m']) * np.sign(df['ema_diff_pct_5m'])
        new_features.append('ema_trend_aligned')
    
    # 13. Oversold/Overbought extremes
    if 'rsi_1m' in df.columns:
        df['rsi_extreme'] = ((df['rsi_1m'] < 30) | (df['rsi_1m'] > 70)).astype(int)
        new_features.append('rsi_extreme')
    
    # 14. DI crossover signal
    if 'di_plus_1m' in df.columns and 'di_minus_1m' in df.columns:
        df['di_bullish'] = (df['di_plus_1m'] > df['di_minus_1m']).astype(int)
        new_features.append('di_bullish')
    
    # 15. Multi-timeframe agreement
    if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
        # Les deux RSI doivent etre du meme cote de 50
        df['mtf_rsi_agree'] = (((df['rsi_1m'] > 50) & (df['rsi_5m'] > 50)) | ((df['rsi_1m'] < 50) & (df['rsi_5m'] < 50))).astype(int)
        new_features.append('mtf_rsi_agree')
    
    print(f"Nouvelles features creees: {len(new_features)}")
    for f in new_features:
        print(f"  - {f}")
    
    return df, new_features

def evaluate_with_new_features(df, new_features):
    """Evalue le modele avec les nouvelles features"""
    print("\n=== EVALUATION AVEC NOUVELLES FEATURES ===")
    
    # Target
    df['target'] = (df['target_pnl'] > 0).astype(int)
    
    # Features originales
    exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target', 'scan_id']
    original_cols = [c for c in df.columns if c not in exclude and c not in new_features 
                    and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]
    
    # Toutes les features
    all_cols = original_cols + new_features
    
    X_original = df[original_cols].fillna(0).values
    X_all = df[all_cols].fillna(0).values
    y = df['target'].values
    
    # Class weights
    cw = compute_class_weight('balanced', classes=np.unique(y), y=y)
    
    def evaluate(X, name, k=20):
        # Selection
        k = min(k, X.shape[1])
        selector = SelectKBest(f_classif, k=k)
        X_sel = selector.fit_transform(X, y)
        
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        train_accs, test_accs, f1s, precs = [], [], [], []
        
        for train_idx, test_idx in cv.split(X_sel, y):
            X_train, X_test = X_sel[train_idx], X_sel[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
            
            scaler = RobustScaler()
            X_train_s = scaler.fit_transform(X_train)
            X_test_s = scaler.transform(X_test)
            
            model = HistGradientBoostingClassifier(
                max_iter=300, max_depth=2, learning_rate=0.089,
                min_samples_leaf=50, l2_regularization=0.9,
                random_state=42, early_stopping=True
            )
            model.fit(X_train_s, y_train, sample_weight=sw)
            
            y_train_pred = model.predict(X_train_s)
            y_test_pred = model.predict(X_test_s)
            
            train_accs.append(accuracy_score(y_train, y_train_pred))
            test_accs.append(accuracy_score(y_test, y_test_pred))
            f1s.append(f1_score(y_test, y_test_pred, zero_division=0))
            precs.append(precision_score(y_test, y_test_pred, zero_division=0))
        
        result = {
            'train_acc': np.mean(train_accs),
            'test_acc': np.mean(test_accs),
            'f1': np.mean(f1s),
            'precision': np.mean(precs),
            'gap': np.mean(train_accs) - np.mean(test_accs)
        }
        
        print(f"\n{name} (k={k}):")
        print(f"  Accuracy: {result['test_acc']*100:.1f}%")
        print(f"  F1 Score: {result['f1']:.3f}")
        print(f"  Precision: {result['precision']:.3f}")
        print(f"  Gap: {result['gap']*100:.1f}%")
        
        return result
    
    # Evaluer
    result_original = evaluate(X_original, "Features originales", k=20)
    result_all = evaluate(X_all, "Avec nouvelles features", k=25)
    
    # Comparaison
    print("\n" + "=" * 50)
    print("COMPARAISON:")
    print(f"  F1: {result_original['f1']:.3f} -> {result_all['f1']:.3f} ({'+' if result_all['f1'] > result_original['f1'] else ''}{(result_all['f1']-result_original['f1'])*100:.1f}%)")
    print(f"  Precision: {result_original['precision']:.3f} -> {result_all['precision']:.3f}")
    print(f"  Gap: {result_original['gap']*100:.1f}% -> {result_all['gap']*100:.1f}%")
    
    return result_original, result_all, all_cols

def find_best_feature_combination(df, all_cols, n_iterations=20):
    """Recherche la meilleure combinaison de features"""
    print(f"\n=== RECHERCHE MEILLEURE COMBINAISON ({n_iterations} iterations) ===")
    
    df['target'] = (df['target_pnl'] > 0).astype(int)
    X = df[all_cols].fillna(0).values
    y = df['target'].values
    
    cw = compute_class_weight('balanced', classes=np.unique(y), y=y)
    
    best_score = 0
    best_k = 20
    best_result = None
    
    for k in range(15, min(40, len(all_cols)), 2):
        selector = SelectKBest(f_classif, k=k)
        X_sel = selector.fit_transform(X, y)
        
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        f1s, precs, gaps = [], [], []
        
        for train_idx, test_idx in cv.split(X_sel, y):
            X_train, X_test = X_sel[train_idx], X_sel[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
            
            scaler = RobustScaler()
            X_train_s = scaler.fit_transform(X_train)
            X_test_s = scaler.transform(X_test)
            
            model = HistGradientBoostingClassifier(
                max_iter=300, max_depth=2, learning_rate=0.089,
                min_samples_leaf=50, l2_regularization=0.9,
                random_state=42, early_stopping=True
            )
            model.fit(X_train_s, y_train, sample_weight=sw)
            
            y_train_pred = model.predict(X_train_s)
            y_test_pred = model.predict(X_test_s)
            
            train_acc = accuracy_score(y_train, y_train_pred)
            test_acc = accuracy_score(y_test, y_test_pred)
            
            f1s.append(f1_score(y_test, y_test_pred, zero_division=0))
            precs.append(precision_score(y_test, y_test_pred, zero_division=0))
            gaps.append(train_acc - test_acc)
        
        f1 = np.mean(f1s)
        prec = np.mean(precs)
        gap = np.mean(gaps)
        
        # Score composite
        score = f1 + prec - gap * 0.5
        
        print(f"k={k}: F1={f1:.3f}, Prec={prec:.3f}, Gap={gap*100:.1f}% -> Score={score:.3f}")
        
        if score > best_score:
            best_score = score
            best_k = k
            best_result = {'f1': f1, 'precision': prec, 'gap': gap}
    
    print(f"\nMeilleur k={best_k} avec F1={best_result['f1']:.3f}, Prec={best_result['precision']:.3f}")
    
    return best_k, best_result

def test_random_forest_feature_importance(df, all_cols):
    """Utilise Random Forest pour identifier les features importantes"""
    print("\n=== RANDOM FOREST FEATURE IMPORTANCE ===")
    
    df['target'] = (df['target_pnl'] > 0).astype(int)
    X = df[all_cols].fillna(0).values
    y = df['target'].values
    
    # Train RF
    rf = RandomForestClassifier(n_estimators=200, max_depth=5, class_weight='balanced', random_state=42)
    rf.fit(X, y)
    
    # Feature importance
    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1]
    
    print("\nTop 25 features par importance RF:")
    print(f"{'Feature':<40} {'Importance':<10}")
    print("-" * 50)
    top_features = []
    for i in range(min(25, len(all_cols))):
        idx = indices[i]
        print(f"{all_cols[idx]:<40} {importances[idx]:<10.4f}")
        top_features.append(all_cols[idx])
    
    return top_features

def evaluate_top_features_only(df, top_features):
    """Evalue en utilisant seulement les top features"""
    print("\n=== EVALUATION AVEC TOP FEATURES SEULEMENT ===")
    
    df['target'] = (df['target_pnl'] > 0).astype(int)
    
    # S'assurer que toutes les features existent
    valid_features = [f for f in top_features if f in df.columns]
    
    X = df[valid_features].fillna(0).values
    y = df['target'].values
    
    cw = compute_class_weight('balanced', classes=np.unique(y), y=y)
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    train_accs, test_accs, f1s, precs = [], [], [], []
    
    for train_idx, test_idx in cv.split(X, y):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        sw = np.array([cw[0] if l==0 else cw[1] for l in y_train])
        
        scaler = RobustScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        model = HistGradientBoostingClassifier(
            max_iter=300, max_depth=2, learning_rate=0.089,
            min_samples_leaf=50, l2_regularization=0.9,
            random_state=42, early_stopping=True
        )
        model.fit(X_train_s, y_train, sample_weight=sw)
        
        y_train_pred = model.predict(X_train_s)
        y_test_pred = model.predict(X_test_s)
        
        train_accs.append(accuracy_score(y_train, y_train_pred))
        test_accs.append(accuracy_score(y_test, y_test_pred))
        f1s.append(f1_score(y_test, y_test_pred, zero_division=0))
        precs.append(precision_score(y_test, y_test_pred, zero_division=0))
    
    result = {
        'test_acc': np.mean(test_accs),
        'f1': np.mean(f1s),
        'precision': np.mean(precs),
        'gap': np.mean(train_accs) - np.mean(test_accs)
    }
    
    print(f"\nResultats avec {len(valid_features)} top features:")
    print(f"  Accuracy: {result['test_acc']*100:.1f}%")
    print(f"  F1 Score: {result['f1']:.3f}")
    print(f"  Precision: {result['precision']:.3f}")
    print(f"  Gap: {result['gap']*100:.1f}%")
    
    return result, valid_features

def main():
    # Charger donnees
    df = load_raw_data()
    
    # Analyser importance des features
    correlations, mi_ranking, original_cols, X, y = analyze_feature_importance(df)
    
    # Creer nouvelles features
    df, new_features = create_new_features(df)
    
    # Evaluer avec nouvelles features
    result_original, result_all, all_cols = evaluate_with_new_features(df, new_features)
    
    # Trouver meilleure combinaison
    best_k, best_result = find_best_feature_combination(df, all_cols)
    
    # RF Feature importance
    top_features = test_random_forest_feature_importance(df, all_cols)
    
    # Evaluer avec top features
    result_top, valid_features = evaluate_top_features_only(df, top_features)
    
    # Resume final
    print("\n" + "=" * 70)
    print("  RESUME FINAL")
    print("=" * 70)
    print(f"\n{'Approche':<35} {'Acc':<10} {'F1':<10} {'Prec':<10} {'Gap':<10}")
    print("-" * 70)
    print(f"{'Features originales (k=20)':<35} {result_original['test_acc']*100:<10.1f}% {result_original['f1']:<10.3f} {result_original['precision']:<10.3f} {result_original['gap']*100:<10.1f}%")
    print(f"{'+ Nouvelles features (k=25)':<35} {result_all['test_acc']*100:<10.1f}% {result_all['f1']:<10.3f} {result_all['precision']:<10.3f} {result_all['gap']*100:<10.1f}%")
    print(f"{f'Meilleur k={best_k}':<35} {'-':<10} {best_result['f1']:<10.3f} {best_result['precision']:<10.3f} {best_result['gap']*100:<10.1f}%")
    print(f"{'Top RF features':<35} {result_top['test_acc']*100:<10.1f}% {result_top['f1']:<10.3f} {result_top['precision']:<10.3f} {result_top['gap']*100:<10.1f}%")
    
    # Recommandation
    print("\n" + "=" * 70)
    print("  RECOMMANDATION")
    print("=" * 70)
    
    results = [
        ('Original k=20', result_original),
        ('Nouvelles features k=25', result_all),
        ('Top RF features', result_top),
    ]
    
    best = max(results, key=lambda x: x[1]['f1'] + x[1]['precision'] - x[1]['gap']*0.5)
    print(f"\nMeilleure approche: {best[0]}")
    print(f"  F1: {best[1]['f1']:.3f}")
    print(f"  Precision: {best[1]['precision']:.3f}")
    print(f"  Gap: {best[1]['gap']*100:.1f}%")
    
    # Sauvegarder les top features pour utilisation
    print(f"\nTop features identifies:")
    for f in valid_features[:15]:
        print(f"  - {f}")

if __name__ == "__main__":
    main()
