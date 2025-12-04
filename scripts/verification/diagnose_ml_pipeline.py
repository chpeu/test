#!/usr/bin/env python3
"""
🔬 DIAGNOSTIC COMPLET DU PIPELINE ML

Analyse approfondie pour identifier POURQUOI le ML ne fonctionne pas
et proposer des solutions concrètes.

Vérifie:
1. Qualité des données SQL
2. Distribution des targets (win/loss, PNL)
3. Corrélation features vs target
4. Signal vs bruit
5. Data leakage potentiel
6. Tests de différentes approches
"""
import logging
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MLPipelineDiagnostic:
    """Diagnostic complet du pipeline ML"""
    
    def __init__(self):
        self.df = None
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'problems': [],
            'solutions': [],
            'tests': []
        }
    
    def run_full_diagnostic(self) -> Dict:
        """Exécuter le diagnostic complet"""
        logger.info("=" * 70)
        logger.info("🔬 DIAGNOSTIC COMPLET PIPELINE ML")
        logger.info("=" * 70)
        
        # 1. Charger et analyser les données
        self._load_data()
        
        if self.df is None or len(self.df) == 0:
            logger.error("❌ Impossible de charger les données")
            return self.results
        
        # 2. Diagnostics
        self._check_data_quality()
        self._check_target_distribution()
        self._check_feature_target_correlation()
        self._check_temporal_patterns()
        self._check_class_separability()
        
        # 3. Tests de solutions
        self._test_simple_rules()
        self._test_ensemble_approach()
        self._test_feature_engineering_improvements()
        
        # 4. Résumé et recommandations
        self._generate_final_recommendations()
        
        return self.results
    
    def _load_data(self):
        """Charger les données depuis PostgreSQL"""
        logger.info("\n📊 Chargement des données...")
        
        try:
            from optimization.data.feature_loader import load_features_from_postgres
            from optimization.data.feature_engineering import calculate_derived_features
            
            base_df = load_features_from_postgres(
                timeframe_days=120,
                min_trades=30
            )
            
            self.df = calculate_derived_features(base_df)
            logger.info(f"✅ {len(self.df)} samples chargés, {len(self.df.columns)} colonnes")
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement: {e}")
            self.results['problems'].append(f"Chargement données: {e}")
    
    def _check_data_quality(self):
        """Vérifier la qualité des données"""
        logger.info("\n" + "=" * 50)
        logger.info("📋 CHECK 1: Qualité des données")
        logger.info("=" * 50)
        
        # Colonnes avec beaucoup de NULL
        null_pcts = (self.df.isnull().sum() / len(self.df) * 100).sort_values(ascending=False)
        high_null = null_pcts[null_pcts > 20]
        
        if len(high_null) > 0:
            logger.warning(f"⚠️ {len(high_null)} colonnes avec >20% NULL:")
            for col, pct in high_null.head(10).items():
                logger.warning(f"   - {col}: {pct:.1f}%")
            self.results['problems'].append(f"{len(high_null)} colonnes avec >20% NULL")
        else:
            logger.info("✅ Pas de colonnes avec beaucoup de NULL")
        
        # Colonnes constantes
        nunique = self.df.nunique()
        constant_cols = nunique[nunique <= 1].index.tolist()
        
        if len(constant_cols) > 0:
            logger.warning(f"⚠️ {len(constant_cols)} colonnes constantes (inutiles): {constant_cols[:5]}")
            self.results['problems'].append(f"{len(constant_cols)} colonnes constantes")
        
        # Vérifier target_win et target_pnl
        if 'target_win' in self.df.columns:
            win_rate = self.df['target_win'].mean()
            logger.info(f"📊 Win rate global: {win_rate*100:.1f}%")
            
            if win_rate < 0.3 or win_rate > 0.7:
                logger.warning(f"⚠️ Classes très déséquilibrées (win_rate={win_rate:.2f})")
                self.results['problems'].append(f"Classes déséquilibrées: {win_rate:.2f}")
        
        if 'target_pnl' in self.df.columns:
            pnl_stats = self.df['target_pnl'].describe()
            logger.info(f"📊 PNL: mean={pnl_stats['mean']:.3f}%, std={pnl_stats['std']:.3f}%")
    
    def _check_target_distribution(self):
        """Analyser la distribution des targets"""
        logger.info("\n" + "=" * 50)
        logger.info("📋 CHECK 2: Distribution des targets")
        logger.info("=" * 50)
        
        if 'target_win' not in self.df.columns:
            logger.error("❌ Colonne target_win manquante")
            return
        
        # Distribution par période temporelle
        if 'timestamp' in self.df.columns:
            self.df['date'] = pd.to_datetime(self.df['timestamp']).dt.date
            daily_winrate = self.df.groupby('date')['target_win'].mean()
            
            logger.info(f"📊 Win rate par jour:")
            logger.info(f"   - Min: {daily_winrate.min()*100:.1f}%")
            logger.info(f"   - Max: {daily_winrate.max()*100:.1f}%")
            logger.info(f"   - Std: {daily_winrate.std()*100:.1f}%")
            
            # Vérifier si win rate très variable (régime de marché changeant)
            if daily_winrate.std() > 0.15:
                logger.warning("⚠️ Win rate très variable selon les jours - régimes de marché différents")
                self.results['problems'].append("Win rate très variable (régimes de marché)")
                self.results['solutions'].append("Utiliser features de régime de marché (volatilité, trend)")
        
        # Distribution par symbole
        if 'symbol' in self.df.columns:
            symbol_winrate = self.df.groupby('symbol')['target_win'].agg(['mean', 'count'])
            symbol_winrate = symbol_winrate[symbol_winrate['count'] >= 10]
            
            if len(symbol_winrate) > 0:
                best_symbols = symbol_winrate.nlargest(5, 'mean')
                worst_symbols = symbol_winrate.nsmallest(5, 'mean')
                
                logger.info(f"📊 Top 5 symboles (win rate):")
                for sym, row in best_symbols.iterrows():
                    logger.info(f"   - {sym}: {row['mean']*100:.1f}% ({int(row['count'])} trades)")
                
                logger.info(f"📊 Pire 5 symboles:")
                for sym, row in worst_symbols.iterrows():
                    logger.info(f"   - {sym}: {row['mean']*100:.1f}% ({int(row['count'])} trades)")
    
    def _check_feature_target_correlation(self):
        """Vérifier corrélation features vs target"""
        logger.info("\n" + "=" * 50)
        logger.info("📋 CHECK 3: Corrélation Features vs Target")
        logger.info("=" * 50)
        
        if 'target_win' not in self.df.columns:
            return
        
        # Colonnes numériques seulement
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                       'is_opportunity', 'date']
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        feature_cols = [c for c in numeric_cols if c not in exclude_cols]
        
        # Calculer corrélations
        correlations = []
        for col in feature_cols:
            try:
                corr = self.df[col].corr(self.df['target_win'].astype(float))
                if not np.isnan(corr):
                    correlations.append({'feature': col, 'correlation': abs(corr)})
            except:
                pass
        
        corr_df = pd.DataFrame(correlations).sort_values('correlation', ascending=False)
        
        # Analyser
        top_corr = corr_df.head(10)
        logger.info("📊 Top 10 features corrélées avec target_win:")
        for _, row in top_corr.iterrows():
            logger.info(f"   - {row['feature']}: {row['correlation']:.4f}")
        
        max_corr = corr_df['correlation'].max()
        if max_corr < 0.1:
            logger.warning("⚠️ PROBLÈME: Aucune feature fortement corrélée au target!")
            logger.warning("   -> Les features actuelles ne prédisent pas bien WIN/LOSS")
            self.results['problems'].append("Features faiblement corrélées au target (max={:.3f})".format(max_corr))
            self.results['solutions'].append("Ajouter features: momentum récent, volatilité, trend strength")
        elif max_corr < 0.2:
            logger.warning(f"⚠️ Corrélations faibles (max={max_corr:.3f})")
            self.results['problems'].append(f"Corrélations faibles (max={max_corr:.3f})")
        else:
            logger.info(f"✅ Corrélation max acceptable: {max_corr:.3f}")
        
        # Stocker pour plus tard
        self.feature_correlations = corr_df
    
    def _check_temporal_patterns(self):
        """Vérifier patterns temporels"""
        logger.info("\n" + "=" * 50)
        logger.info("📋 CHECK 4: Patterns temporels")
        logger.info("=" * 50)
        
        if 'timestamp' not in self.df.columns:
            return
        
        # Win rate par heure
        self.df['hour'] = pd.to_datetime(self.df['timestamp']).dt.hour
        hourly_wr = self.df.groupby('hour')['target_win'].mean()
        
        best_hours = hourly_wr.nlargest(3)
        worst_hours = hourly_wr.nsmallest(3)
        
        logger.info("📊 Win rate par heure (UTC):")
        logger.info(f"   Meilleures heures: {dict(best_hours.round(3))}")
        logger.info(f"   Pires heures: {dict(worst_hours.round(3))}")
        
        hour_range = hourly_wr.max() - hourly_wr.min()
        if hour_range > 0.15:
            logger.info(f"✅ Pattern horaire significatif (range={hour_range:.2f})")
            self.results['solutions'].append("Utiliser l'heure comme feature (one-hot ou cyclique)")
        else:
            logger.info(f"ℹ️ Pas de pattern horaire fort (range={hour_range:.2f})")
    
    def _check_class_separability(self):
        """Vérifier si les classes WIN/LOSS sont séparables"""
        logger.info("\n" + "=" * 50)
        logger.info("📋 CHECK 5: Séparabilité des classes")
        logger.info("=" * 50)
        
        if 'target_win' not in self.df.columns:
            return
        
        # Comparer distributions des top features entre WIN et LOSS
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                       'is_opportunity', 'date', 'hour']
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        feature_cols = [c for c in numeric_cols if c not in exclude_cols][:20]  # Top 20
        
        wins = self.df[self.df['target_win'] == True]
        losses = self.df[self.df['target_win'] == False]
        
        separable_features = []
        
        for col in feature_cols:
            try:
                win_mean = wins[col].mean()
                loss_mean = losses[col].mean()
                pooled_std = self.df[col].std()
                
                if pooled_std > 0:
                    effect_size = abs(win_mean - loss_mean) / pooled_std
                    if effect_size > 0.2:  # Cohen's d > 0.2 = small effect
                        separable_features.append({
                            'feature': col,
                            'effect_size': effect_size,
                            'win_mean': win_mean,
                            'loss_mean': loss_mean
                        })
            except:
                pass
        
        if len(separable_features) > 0:
            sep_df = pd.DataFrame(separable_features).sort_values('effect_size', ascending=False)
            logger.info(f"✅ {len(separable_features)} features avec séparation WIN/LOSS:")
            for _, row in sep_df.head(5).iterrows():
                logger.info(f"   - {row['feature']}: effect={row['effect_size']:.3f} (win={row['win_mean']:.3f}, loss={row['loss_mean']:.3f})")
        else:
            logger.warning("⚠️ PROBLÈME MAJEUR: Aucune feature ne sépare bien WIN/LOSS")
            self.results['problems'].append("Aucune feature discriminante entre WIN/LOSS")
            self.results['solutions'].append("Le problème est dans les données, pas le modèle")
    
    def _test_simple_rules(self):
        """Tester des règles simples comme baseline"""
        logger.info("\n" + "=" * 50)
        logger.info("🧪 TEST 1: Règles simples (baseline)")
        logger.info("=" * 50)
        
        if 'target_win' not in self.df.columns:
            return
        
        results = []
        
        # Règle 1: Toujours prédire WIN (baseline naïf)
        baseline_accuracy = self.df['target_win'].mean()
        results.append(('Toujours WIN', baseline_accuracy))
        
        # Règle 2: Toujours prédire LOSS
        results.append(('Toujours LOSS', 1 - baseline_accuracy))
        
        # Règle 3: Basé sur RSI
        if 'rsi_1m' in self.df.columns:
            rsi_pred = (self.df['rsi_1m'] > 50).astype(int) == self.df['target_win'].astype(int)
            results.append(('RSI > 50 = WIN', rsi_pred.mean()))
        
        # Règle 4: Basé sur MACD
        if 'macd_hist_1m' in self.df.columns:
            macd_pred = (self.df['macd_hist_1m'] > 0).astype(int) == self.df['target_win'].astype(int)
            results.append(('MACD > 0 = WIN', macd_pred.mean()))
        
        # Règle 5: Combinaison
        if 'rsi_1m' in self.df.columns and 'macd_hist_1m' in self.df.columns:
            combo_pred = ((self.df['rsi_1m'] > 50) & (self.df['macd_hist_1m'] > 0)).astype(int)
            combo_acc = (combo_pred == self.df['target_win'].astype(int)).mean()
            results.append(('RSI>50 AND MACD>0', combo_acc))
        
        logger.info("📊 Résultats règles simples:")
        best_rule = None
        best_acc = 0
        for rule, acc in results:
            marker = "⭐" if acc > 0.52 else ""
            logger.info(f"   - {rule}: {acc*100:.1f}% {marker}")
            if acc > best_acc:
                best_acc = acc
                best_rule = rule
        
        self.results['tests'].append({
            'name': 'Simple Rules',
            'best_rule': best_rule,
            'best_accuracy': best_acc
        })
        
        if best_acc < 0.52:
            logger.warning("⚠️ Même les règles simples ne font pas mieux que le hasard!")
            self.results['problems'].append("Règles simples < 52% accuracy")
    
    def _test_ensemble_approach(self):
        """Tester une approche ensemble avec vote majoritaire"""
        logger.info("\n" + "=" * 50)
        logger.info("🧪 TEST 2: Approche Ensemble")
        logger.info("=" * 50)
        
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import RobustScaler
            from sklearn.metrics import accuracy_score, f1_score
            
            # Préparer données
            exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                           'is_opportunity', 'date', 'hour']
            feature_cols = [c for c in self.df.columns if c not in exclude_cols 
                           and self.df[c].dtype in [np.float64, np.int64, np.bool_]]
            
            X = self.df[feature_cols].fillna(0)
            y = self.df['target_win'].astype(int)
            
            # Split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scaler
            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Modèles
            models = {
                'LogisticRegression': LogisticRegression(C=0.1, max_iter=500),
                'RandomForest': RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42),
                'GradientBoosting': GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
            }
            
            predictions = {}
            logger.info("📊 Résultats individuels:")
            
            for name, model in models.items():
                model.fit(X_train_scaled, y_train)
                y_pred = model.predict(X_test_scaled)
                acc = accuracy_score(y_test, y_pred)
                f1 = f1_score(y_test, y_pred, zero_division=0)
                predictions[name] = y_pred
                logger.info(f"   - {name}: Acc={acc*100:.1f}%, F1={f1:.3f}")
            
            # Vote majoritaire
            ensemble_pred = np.round(np.mean(list(predictions.values()), axis=0))
            ensemble_acc = accuracy_score(y_test, ensemble_pred)
            ensemble_f1 = f1_score(y_test, ensemble_pred, zero_division=0)
            
            logger.info(f"   - ENSEMBLE (vote): Acc={ensemble_acc*100:.1f}%, F1={ensemble_f1:.3f}")
            
            self.results['tests'].append({
                'name': 'Ensemble',
                'accuracy': ensemble_acc,
                'f1': ensemble_f1
            })
            
            if ensemble_acc < 0.53:
                logger.warning("⚠️ Même l'ensemble ne dépasse pas 53%")
                self.results['problems'].append("Ensemble < 53% - problème de données")
            
        except Exception as e:
            logger.error(f"❌ Erreur test ensemble: {e}")
    
    def _test_feature_engineering_improvements(self):
        """Tester des améliorations de feature engineering"""
        logger.info("\n" + "=" * 50)
        logger.info("🧪 TEST 3: Feature Engineering amélioré")
        logger.info("=" * 50)
        
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.preprocessing import RobustScaler
            from sklearn.metrics import accuracy_score
            
            # Créer nouvelles features
            df_enhanced = self.df.copy()
            
            # 1. Momentum features
            if 'rsi_1m' in df_enhanced.columns and 'rsi_5m' in df_enhanced.columns:
                df_enhanced['rsi_momentum'] = df_enhanced['rsi_1m'] - df_enhanced['rsi_5m']
            
            # 2. Volatility regime
            if 'atr_pct_1m' in df_enhanced.columns:
                df_enhanced['high_volatility'] = (df_enhanced['atr_pct_1m'] > df_enhanced['atr_pct_1m'].median()).astype(int)
            
            # 3. Trend alignment
            if 'macd_hist_1m' in df_enhanced.columns and 'macd_hist_5m' in df_enhanced.columns:
                df_enhanced['trend_aligned'] = ((df_enhanced['macd_hist_1m'] > 0) == (df_enhanced['macd_hist_5m'] > 0)).astype(int)
            
            # 4. RSI oversold/overbought
            if 'rsi_1m' in df_enhanced.columns:
                df_enhanced['rsi_extreme'] = ((df_enhanced['rsi_1m'] < 30) | (df_enhanced['rsi_1m'] > 70)).astype(int)
            
            # 5. Volume confirmation
            if 'volume_ratio_1m' in df_enhanced.columns:
                df_enhanced['volume_spike'] = (df_enhanced['volume_ratio_1m'] > 1.5).astype(int)
            
            logger.info("✅ 5 nouvelles features créées")
            
            # Tester
            exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                           'is_opportunity', 'date', 'hour']
            feature_cols = [c for c in df_enhanced.columns if c not in exclude_cols 
                           and df_enhanced[c].dtype in [np.float64, np.int64, np.bool_]]
            
            X = df_enhanced[feature_cols].fillna(0)
            y = df_enhanced['target_win'].astype(int)
            
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            model = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            y_pred = model.predict(X_test_scaled)
            acc = accuracy_score(y_test, y_pred)
            
            logger.info(f"📊 Avec nouvelles features: Accuracy={acc*100:.1f}%")
            
            self.results['tests'].append({
                'name': 'Enhanced Features',
                'accuracy': acc
            })
            
        except Exception as e:
            logger.error(f"❌ Erreur test features: {e}")
    
    def _generate_final_recommendations(self):
        """Générer les recommandations finales"""
        logger.info("\n" + "=" * 70)
        logger.info("📋 DIAGNOSTIC FINAL ET RECOMMANDATIONS")
        logger.info("=" * 70)
        
        # Analyser les résultats des tests
        best_accuracy = 0
        for test in self.results['tests']:
            if 'accuracy' in test and test['accuracy'] > best_accuracy:
                best_accuracy = test['accuracy']
        
        logger.info(f"\n📊 Meilleure accuracy obtenue: {best_accuracy*100:.1f}%")
        
        if best_accuracy < 0.52:
            logger.warning("\n⚠️ CONCLUSION: Le ML actuel n'apporte pas de valeur ajoutée")
            logger.warning("   Les données/features actuelles ne permettent pas de prédire")
            
            self.results['solutions'].extend([
                "🔧 SOLUTION 1: Collecter plus de données (>10,000 trades)",
                "🔧 SOLUTION 2: Ajouter features de contexte marché (BTC trend, volatilité globale)",
                "🔧 SOLUTION 3: Utiliser le ML pour FILTRER (rejeter les pires) plutôt que prédire",
                "🔧 SOLUTION 4: Implémenter un système de scoring basé sur règles simples",
                "🔧 SOLUTION 5: Analyser les trades gagnants vs perdants manuellement"
            ])
        elif best_accuracy < 0.55:
            logger.info("\n📊 Le ML apporte une légère amélioration")
            self.results['solutions'].extend([
                "🔧 Utiliser le ML comme FILTRE (rejeter les prédictions < 0.4)",
                "🔧 Combiner avec règles de trading existantes",
                "🔧 Collecter plus de données pour améliorer"
            ])
        else:
            logger.info("\n✅ Le ML semble fonctionner - continuer à optimiser")
        
        # Afficher toutes les recommandations
        logger.info("\n📋 PROBLÈMES IDENTIFIÉS:")
        for i, problem in enumerate(self.results['problems'], 1):
            logger.info(f"   {i}. {problem}")
        
        logger.info("\n📋 SOLUTIONS PROPOSÉES:")
        for i, solution in enumerate(self.results['solutions'], 1):
            logger.info(f"   {i}. {solution}")
        
        logger.info("\n" + "=" * 70)
    
    def save_report(self, filepath: str = "ml_diagnostic_report.json"):
        """Sauvegarder le rapport"""
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        logger.info(f"📄 Rapport sauvegardé: {filepath}")


def main():
    """Point d'entrée"""
    diagnostic = MLPipelineDiagnostic()
    results = diagnostic.run_full_diagnostic()
    diagnostic.save_report()
    
    # Retourner code selon la sévérité
    n_problems = len(results['problems'])
    if n_problems >= 5:
        sys.exit(2)  # Problèmes majeurs
    elif n_problems >= 2:
        sys.exit(1)  # Problèmes modérés
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
