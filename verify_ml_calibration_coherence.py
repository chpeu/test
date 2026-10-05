#!/usr/bin/env python3
"""
Vérification cohérence ML Calibration vs Modèle GB entraîné
"""
import sys
sys.path.append('.')
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

def main():
    print('='*80)
    print('VERIFICATION COHERENCE ML CALIBRATION vs MODELE GB')  
    print('='*80)

    # 1. Vérifier les métadonnées du modèle GB actuel
    print('\n1. MODELE GB ACTUEL:')
    meta_path = Path('optimization/saved_models/best_classifier_metadata.json')
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            gb_metadata = json.load(f)
        
        gb_training_date = gb_metadata.get('timestamp', 'inconnue')
        gb_accuracy = gb_metadata.get('metrics', {}).get('test_accuracy', 0)
        gb_f1 = gb_metadata.get('metrics', {}).get('f1_score', 0)
        
        print(f'   Date entrainement GB: {gb_training_date}')
        print(f'   Test Accuracy GB: {gb_accuracy*100:.1f}%')
        print(f'   F1 Score GB: {gb_f1*100:.1f}%')
        
        # Extraire la date pour comparaison
        if gb_training_date != 'inconnue':
            try:
                gb_date = datetime.fromisoformat(gb_training_date.replace('Z', '+00:00'))
                print(f'   Date parsee: {gb_date}')
            except ValueError:
                # Fallback si format différent
                gb_date = datetime.fromisoformat(gb_training_date.split('.')[0])
                print(f'   Date parsee (fallback): {gb_date}')
    else:
        print('   [ERROR] Metadata modele GB non trouvee')
        return

    # 2. Analyser les données de calibration
    print('\n2. DONNEES ML CALIBRATION:')
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg_logger = PostgreSQLDataLogger()
        
        conn = pg_logger.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Récupérer les données de calibration avec timestamps
                cur.execute("""
                    SELECT direction, confidence_bucket, total_trades, actual_winrate,
                           created_at, updated_at
                    FROM ml_calibration
                    WHERE total_trades > 0
                    ORDER BY direction, confidence_bucket
                """)
                calibration_data = cur.fetchall()
                
                if calibration_data:
                    print(f'   Total buckets avec donnees: {len(calibration_data)}')
                    
                    # Analyser les dates de création
                    creation_dates = [row[4] for row in calibration_data if row[4]]
                    update_dates = [row[5] for row in calibration_data if row[5]]
                    
                    if creation_dates:
                        oldest_creation = min(creation_dates)
                        newest_creation = max(creation_dates)
                        print(f'   Plus ancienne creation: {oldest_creation}')
                        print(f'   Plus recente creation: {newest_creation}')
                    
                    if update_dates:
                        latest_update = max(update_dates)
                        print(f'   Derniere mise a jour: {latest_update}')
                        
                        # Comparer avec la date d'entraînement GB
                        if 'gb_date' in locals():
                            # Convertir gb_date en naive pour comparaison
                            gb_date_naive = gb_date.replace(tzinfo=None)
                            latest_update_naive = latest_update.replace(tzinfo=None)
                            
                            if latest_update_naive > gb_date_naive:
                                print(f'   [OK] Calibration mise a jour APRES entrainement GB')
                            else:
                                print(f'   [WARNING] Calibration plus ancienne que le modele GB!')
                                print(f'             Modele GB: {gb_date_naive}')
                                print(f'             Derniere calib: {latest_update_naive}')
                else:
                    print('   [ERROR] Aucune donnee de calibration trouvee')
                    return

        finally:
            pg_logger.pool.putconn(conn)

        # 3. Analyser la distribution des winrates par bucket
        print('\n3. ANALYSE WINRATES PAR CONFIDENCE BUCKET:')
        
        conn = pg_logger.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Calculer les winrates moyens par direction
                cur.execute("""
                    SELECT direction, 
                           AVG(actual_winrate) as avg_winrate,
                           SUM(total_trades) as total_trades,
                           COUNT(*) as num_buckets
                    FROM ml_calibration
                    WHERE total_trades > 0
                    GROUP BY direction
                """)
                direction_stats = cur.fetchall()
                
                for direction, avg_winrate, total_trades, num_buckets in direction_stats:
                    print(f'   {direction}:')
                    print(f'      Winrate moyen: {avg_winrate:.1f}%')
                    print(f'      Total trades: {total_trades}')
                    print(f'      Nombre buckets: {num_buckets}')
                    
                    # Comparer avec les métriques GB globales
                    expected_accuracy = gb_accuracy * 100
                    diff = abs(float(avg_winrate) - expected_accuracy)
                    
                    if diff < 10:  # Tolérance de 10%
                        print(f'      [OK] Coherent avec GB accuracy ({expected_accuracy:.1f}%)')
                    else:
                        print(f'      [WARNING] Ecart significatif avec GB accuracy!')
                        print(f'                Calibration: {avg_winrate:.1f}% vs GB: {expected_accuracy:.1f}%')

        finally:
            pg_logger.pool.putconn(conn)

        # 4. Analyser les trades récents avec confidences GB
        print('\n4. TRADES RECENTS AVEC CONFIDENCES GB:')
        
        conn = pg_logger.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Chercher des trades avec ml_confidence après la date d'entraînement GB
                if 'gb_date' in locals():
                    cur.execute("""
                        SELECT COUNT(*) as total_trades,
                               AVG(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as actual_winrate,
                               AVG(ml_confidence) as avg_confidence,
                               MIN(ml_confidence) as min_confidence,
                               MAX(ml_confidence) as max_confidence
                        FROM trades
                        WHERE ml_confidence IS NOT NULL
                        AND created_at > %s
                        AND outcome IN ('WIN', 'LOSS')
                    """, (gb_date,))
                    
                    result = cur.fetchone()
                    if result and result[0] > 0:
                        total, winrate, avg_conf, min_conf, max_conf = result
                        print(f'   Trades apres entrainement GB: {total}')
                        print(f'   Winrate observe: {winrate*100:.1f}%')
                        print(f'   Confidence moyenne: {avg_conf*100:.1f}%')
                        print(f'   Range confidence: {min_conf*100:.1f}% - {max_conf*100:.1f}%')
                        
                        # Comparer avec accuracy GB
                        expected_accuracy = gb_accuracy * 100
                        diff = abs(winrate*100 - expected_accuracy)
                        
                        if diff < 5:  # Tolérance de 5%
                            print(f'   [OK] Performance coherente avec modele GB')
                        else:
                            print(f'   [WARNING] Performance diverge du modele GB!')
                            print(f'             Observe: {winrate*100:.1f}% vs Attendu: {expected_accuracy:.1f}%')
                    else:
                        print('   [WARNING] Aucun trade avec ml_confidence apres entrainement GB')

        finally:
            pg_logger.pool.putconn(conn)

        # 5. Vérifier les seuils de calibration
        print('\n5. VERIFICATION SEUILS CALIBRATION:')
        
        try:
            from config import TRADING_CONFIG
            
            ml_calib_enabled = TRADING_CONFIG.get('ml_calibration_enabled', False)
            min_winrate = TRADING_CONFIG.get('ml_calib_min_winrate', 40.0)
            
            print(f'   ml_calibration_enabled: {ml_calib_enabled}')
            try:
                min_winrate_value = float(min_winrate)
                min_winrate_pct = min_winrate_value * 100.0 if min_winrate_value <= 1.0 else min_winrate_value
                print(f'   ml_calib_min_winrate: {min_winrate_pct:.0f}%')
            except Exception:
                print(f'   ml_calib_min_winrate: {min_winrate}')
            
            # Vérifier si les seuils sont cohérents avec le modèle GB
            gb_accuracy_threshold = gb_accuracy * 0.8  # 80% de l'accuracy GB comme seuil raisonnable
            
            try:
                min_wr = float(min_winrate)
                min_wr = min_wr * 100.0 if min_wr <= 1.0 else min_wr
                if (min_wr / 100.0) >= gb_accuracy_threshold:
                    print(f'   [OK] Seuil coherent avec modele GB (min {gb_accuracy_threshold*100:.1f}%)')
                else:
                    print(f'   [WARNING] Seuil peut-etre trop bas par rapport au modele GB')
                    print(f'             Recommande min: {gb_accuracy_threshold*100:.1f}%')
            except Exception:
                print('   [WARNING] Seuil ml_calib_min_winrate non numérique, impossible de comparer')

        except Exception as e:
            print(f'   [ERROR] Erreur config: {e}')

    except Exception as e:
        print(f'   [ERROR] Erreur analyse calibration: {e}')

    print('\n' + '='*80)
    print('VERIFICATION TERMINEE')
    print('='*80)

if __name__ == "__main__":
    main()
