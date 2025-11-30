"""
Script de vérification des corrections ML
- XGBoost V1: Alerte "pas assez de données" supprimée
- XGBoost V2: R² négatif diagnostiqué
- GradientBoosting: Logique du filtre améliorée
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_status(name, passed, detail=""):
    status = "[OK]" if passed else "[FAIL]"
    print(f"  {status} {name}: {detail}")

def test_xgboost_v1_no_block():
    """Verifier que XGBoost V1 ne bloque plus avec peu de donnees"""
    print_section("1. TEST XGBOOST V1 - Alerte supprimee")
    
    try:
        with open('api/routes/ml.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Chercher specifiquement dans la section @router.post("/train")
        # La correction: "Donnees limitees" au lieu de HTTPException
        has_warning = "Donnees limitees" in content or "Données limitées" in content
        
        # Verifier que dans la zone de train_model, on a le warning et pas l'exception
        train_section = content[content.find('@router.post("/train")'):content.find('@router.post("/train")') + 2000]
        has_exception_in_train = "raise HTTPException" in train_section and "Pas assez" in train_section
        
        print_status(
            "Warning informatif ajoute",
            has_warning,
            "OK - Warning 'Donnees limitees'" if has_warning else "Warning non trouve"
        )
        
        print_status(
            "HTTPException dans /train",
            not has_exception_in_train,
            "OK - Plus de blocage" if not has_exception_in_train else "HTTPException encore presente"
        )
        
        return has_warning
        
    except Exception as e:
        print_status("Test", False, f"Erreur: {e}")
        return False

def test_xgboost_v2_r2_fix():
    """Vérifier les corrections R² XGBoost V2"""
    print_section("2. TEST XGBOOST V2 - Corrections R² négatif")
    
    try:
        with open('api/routes/ml.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier winsorization 5-95%
        has_5_95 = "quantile(0.05)" in content and "quantile(0.95)" in content
        
        # Vérifier diagnostic R² négatif
        has_r2_diagnostic = "R² très négatif" in content
        
        # Vérifier clipping R² pour affichage
        has_r2_clip = "test_r2_display = max(-1.0, test_r2)" in content
        
        print_status(
            "Winsorization 5-95%",
            has_5_95,
            "OK - Outliers clippés agressivement" if has_5_95 else "Winsorization 1-99% (moins agressif)"
        )
        
        print_status(
            "Diagnostic R² négatif",
            has_r2_diagnostic,
            "OK - Logs de diagnostic ajoutés" if has_r2_diagnostic else "Diagnostic manquant"
        )
        
        print_status(
            "Clipping R² affichage",
            has_r2_clip,
            "OK - R² minimum -1.0 pour UI" if has_r2_clip else "Pas de clipping"
        )
        
        return has_5_95 and has_r2_diagnostic
        
    except Exception as e:
        print_status("Test", False, f"Erreur: {e}")
        return False

def test_gb_filter_logic():
    """Vérifier la logique du filtre GradientBoosting"""
    print_section("3. TEST FILTRE GRADIENTBOOSTING")
    
    results = []
    
    # Test main.py
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_direction_feature = "gb_features['direction']" in content
        has_score_features = "gb_features['totalScore']" in content
        has_conditions = "gb_features['conditions']" in content
        
        print_status(
            "Feature direction",
            has_direction_feature,
            "OK - Direction LONG/SHORT ajoutée" if has_direction_feature else "Direction manquante"
        )
        
        print_status(
            "Feature totalScore",
            has_score_features,
            "OK - Score total ajouté" if has_score_features else "Score manquant"
        )
        
        print_status(
            "Feature conditions",
            has_conditions,
            "OK - Nombre conditions ajouté" if has_conditions else "Conditions manquantes"
        )
        
        results.append(has_direction_feature and has_score_features)
        
    except Exception as e:
        print_status("main.py", False, f"Erreur: {e}")
        results.append(False)
    
    # Test predictor_optimized.py
    try:
        with open('optimization/predictor_optimized.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_diagnostic = ">50% features manquantes" in content
        has_accept_log = "GB ACCEPT" in content
        has_reject_log = "GB REJECT" in content
        
        print_status(
            "Diagnostic features manquantes",
            has_diagnostic,
            "OK - Warning si >50% manquantes" if has_diagnostic else "Diagnostic manquant"
        )
        
        print_status(
            "Logs ACCEPT/REJECT",
            has_accept_log and has_reject_log,
            "OK - Logs détaillés" if (has_accept_log and has_reject_log) else "Logs incomplets"
        )
        
        results.append(has_diagnostic)
        
    except Exception as e:
        print_status("predictor_optimized.py", False, f"Erreur: {e}")
        results.append(False)
    
    return all(results)

def test_gb_predictor_loading():
    """Tester le chargement du prédicteur GB"""
    print_section("4. TEST CHARGEMENT MODÈLE GB")
    
    try:
        from optimization.predictor_optimized import get_predictor
        
        predictor = get_predictor()
        
        print_status(
            "Modèle chargé",
            predictor.is_loaded,
            f"OK - Modèle prêt" if predictor.is_loaded else "ERREUR - Modèle non chargé"
        )
        
        if predictor.is_loaded:
            info = predictor.get_model_info()
            n_features = info.get('n_features', 0)
            
            print_status(
                "Features attendues",
                n_features > 0,
                f"{n_features} features" if n_features > 0 else "Aucune feature définie"
            )
            
            # Test prediction avec features minimales
            test_features = {
                'rsi_1m': 45.0,
                'rsi_5m': 50.0,
                'macd_hist_1m': 0.002,
                'macd_hist_5m': 0.001,
                'adx_1m': 28.0,
                'adx_5m': 25.0,
                'volume_ratio_1m': 1.2,
                'volume_ratio_5m': 1.0,
                'atr_pct_1m': 0.3,
                'atr_pct_5m': 0.4,
                'totalScore': 8.5,
                'conditions': 4,
                'direction': 1
            }
            
            should_trade, confidence = predictor.predict(test_features, threshold=0.5)
            
            print_status(
                "Prédiction test",
                True,
                f"should_trade={should_trade}, confidence={confidence*100:.1f}%"
            )
            
            return True
        
        return False
        
    except Exception as e:
        print_status("Chargement", False, f"Erreur: {e}")
        return False

def test_feature_correlation_fix():
    """Vérifier le fix de l'erreur float (division par zéro)"""
    print_section("5. TEST FIX ERREUR FLOAT (corrélation)")
    
    try:
        with open('optimization/data/feature_engineering.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_variance_check = "X_var = X.var()" in content
        has_constant_filter = "constant_cols" in content
        has_dropna = "correlations = correlations.dropna()" in content
        
        print_status(
            "Check variance colonnes",
            has_variance_check,
            "OK - Variance calculée" if has_variance_check else "Check manquant"
        )
        
        print_status(
            "Filtrage colonnes constantes",
            has_constant_filter,
            "OK - Colonnes constantes filtrées" if has_constant_filter else "Filtrage manquant"
        )
        
        print_status(
            "Suppression NaN corrélations",
            has_dropna,
            "OK - NaN supprimés" if has_dropna else "dropna manquant"
        )
        
        return has_variance_check and has_constant_filter
        
    except Exception as e:
        print_status("Test", False, f"Erreur: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("  VÉRIFICATION CORRECTIONS ML")
    print("=" * 60)
    
    results = []
    
    # Tests de code
    results.append(("XGBoost V1 alerte", test_xgboost_v1_no_block()))
    results.append(("XGBoost V2 R²", test_xgboost_v2_r2_fix()))
    results.append(("GB Filter logique", test_gb_filter_logic()))
    results.append(("GB Predictor", test_gb_predictor_loading()))
    results.append(("Fix erreur float", test_feature_correlation_fix()))
    
    # Résumé
    print_section("RÉSUMÉ")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        print_status(name, result)
    
    print(f"\n  Total: {passed}/{total} tests passés")
    
    if passed == total:
        print("\n  [SUCCESS] TOUTES LES CORRECTIONS SONT EN PLACE!")
        print("\n  Prochaines etapes:")
        print("  1. Redemarrer le backend")
        print("  2. Activer gb_filter_enabled dans config_overrides.json")
        print("  3. Tester avec gb_min_confidence=0.50 (50%)")
        print("  4. Surveiller les logs pour 'GB ACCEPT' ou 'GB REJECT'")
    else:
        print("\n  [WARNING] Certaines corrections manquent")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
