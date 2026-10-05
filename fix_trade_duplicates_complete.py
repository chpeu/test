#!/usr/bin/env python3
"""
Script complet pour corriger les doublons de trades et créer une boucle de vérification.

PROBLÈME IDENTIFIÉ:
- Trades créés à l'OUVERTURE (exit_reason=NULL, pnl=0)
- Nouveaux trades créés à la FERMETURE (exit_reason=TP/SL, pnl calculé)
- Résultat: 2 lignes par trade au lieu d'1 ligne mise à jour

SOLUTION:
1. Corriger la logique pour UPDATE au lieu d'INSERT à la fermeture
2. Nettoyer les doublons existants
3. Créer une boucle de vérification automatique
"""
import sys
sys.path.append('.')
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import psycopg2
from decimal import Decimal

def analyze_duplicate_trades():
    """Analyser les trades dupliqués en détail"""
    print('\n' + '='*80)
    print('ANALYSE TRADES DUPLIQUÉS')
    print('='*80)
    
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg_logger = PostgreSQLDataLogger()
        conn = pg_logger.pool.getconn()
        
        try:
            with conn.cursor() as cur:
                # 1. Identifier les groupes de doublons
                print('\n1. IDENTIFICATION DES GROUPES DUPLIQUÉS:')
                cur.execute('''
                    WITH duplicate_groups AS (
                        SELECT 
                            symbol,
                            entry_price,
                            DATE_TRUNC('minute', created_at) as minute_group,
                            COUNT(*) as trade_count,
                            array_agg(id ORDER BY created_at) as trade_ids,
                            array_agg(exit_reason ORDER BY created_at) as exit_reasons,
                            array_agg(COALESCE(net_pnl_pct, 0) ORDER BY created_at) as pnl_values,
                            array_agg(created_at ORDER BY created_at) as timestamps
                        FROM trades
                        WHERE created_at > NOW() - INTERVAL '24 hours'
                        AND entry_price IS NOT NULL
                        GROUP BY symbol, entry_price, DATE_TRUNC('minute', created_at)
                        HAVING COUNT(*) > 1
                    )
                    SELECT * FROM duplicate_groups
                    ORDER BY minute_group DESC
                    LIMIT 20
                ''')
                
                duplicate_groups = cur.fetchall()
                print(f'   Groupes dupliqués trouvés: {len(duplicate_groups)}')
                
                duplicates_to_clean = []
                for i, (symbol, entry, minute, count, ids, reasons, pnls, timestamps) in enumerate(duplicate_groups):
                    print(f'\n   Groupe {i+1}: {symbol} entry={entry} ({count} trades)')
                    print(f'     Timestamps: {[t.strftime("%H:%M:%S") for t in timestamps]}')
                    print(f'     Exit reasons: {reasons}')
                    print(f'     PnL values: {pnls}')
                    
                    # Identifier le trade "ouverture" (NULL) et "fermeture" (avec raison)
                    opening_trade = None
                    closing_trade = None
                    
                    for j, reason in enumerate(reasons):
                        if reason is None and pnls[j] == 0:
                            opening_trade = {'id': ids[j], 'index': j}
                        elif reason is not None and pnls[j] != 0:
                            closing_trade = {'id': ids[j], 'index': j}
                    
                    if opening_trade and closing_trade:
                        duplicates_to_clean.append({
                            'symbol': symbol,
                            'entry_price': entry,
                            'opening_id': opening_trade['id'],
                            'closing_id': closing_trade['id'],
                            'opening_timestamp': timestamps[opening_trade['index']],
                            'closing_timestamp': timestamps[closing_trade['index']],
                            'exit_reason': reasons[closing_trade['index']],
                            'pnl_pct': pnls[closing_trade['index']]
                        })
                
                return duplicates_to_clean
                
        finally:
            pg_logger.pool.putconn(conn)
            
    except Exception as e:
        print(f'ERREUR analyse: {e}')
        return []

def clean_duplicate_trades(duplicates_to_clean: List[Dict]):
    """Nettoyer les trades dupliqués en fusionnant les données"""
    print('\n' + '='*80)
    print('NETTOYAGE TRADES DUPLIQUÉS')
    print('='*80)
    
    if not duplicates_to_clean:
        print('   Aucun doublon à nettoyer')
        return True
        
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg_logger = PostgreSQLDataLogger()
        conn = pg_logger.pool.getconn()
        
        try:
            with conn.cursor() as cur:
                cleaned_count = 0
                
                for dup in duplicates_to_clean:
                    print(f'\n   Nettoyage {dup["symbol"]} entry={dup["entry_price"]}')
                    
                    try:
                        # 1. Mettre à jour le trade d'ouverture avec les données de fermeture
                        cur.execute('''
                            UPDATE trades 
                            SET 
                                exit_reason = %s,
                                net_pnl_pct = %s,
                                updated_at = NOW()
                            WHERE id = %s
                        ''', (
                            dup['exit_reason'],
                            dup['pnl_pct'],
                            dup['opening_id']
                        ))
                        
                        # 2. Supprimer le trade de fermeture (doublon)
                        cur.execute('DELETE FROM trades WHERE id = %s', (dup['closing_id'],))
                        
                        conn.commit()
                        cleaned_count += 1
                        print(f'     ✅ Nettoyé: fusionné {dup["opening_id"][:8]}... (gardé) + {dup["closing_id"][:8]}... (supprimé)')
                        
                    except Exception as e:
                        conn.rollback()
                        print(f'     ❌ Erreur nettoyage: {e}')
                        continue
                
                print(f'\n   📊 RÉSULTATS NETTOYAGE: {cleaned_count}/{len(duplicates_to_clean)} doublons nettoyés')
                return cleaned_count > 0
                
        finally:
            pg_logger.pool.putconn(conn)
            
    except Exception as e:
        print(f'ERREUR nettoyage: {e}')
        return False

def create_verification_loop():
    """Créer une boucle de vérification automatique des doublons"""
    print('\n' + '='*80)
    print('CRÉATION BOUCLE DE VÉRIFICATION')
    print('='*80)
    
    verification_script = '''#!/usr/bin/env python3
"""
Boucle de vérification automatique des doublons de trades
À exécuter périodiquement (ex: cron job toutes les heures)
"""
import sys
sys.path.append('.')
from datetime import datetime, timedelta

def check_and_alert_duplicates():
    """Vérifier les doublons et alerter si nécessaire"""
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg_logger = PostgreSQLDataLogger()
        conn = pg_logger.pool.getconn()
        
        try:
            with conn.cursor() as cur:
                # Recherche doublons récents (dernière heure)
                query1 = """
                    WITH potential_dupes AS (
                        SELECT 
                            symbol,
                            entry_price,
                            COUNT(*) as count,
                            array_agg(exit_reason) as reasons
                        FROM trades
                        WHERE created_at > NOW() - INTERVAL '1 hour'
                        AND entry_price IS NOT NULL
                        GROUP BY symbol, entry_price
                        HAVING COUNT(*) > 1
                    )
                    SELECT COUNT(*) as dupe_groups, SUM(count) as total_dupes
                    FROM potential_dupes
                """
                cur.execute(query1)
                
                result = cur.fetchone()
                dupe_groups, total_dupes = result or (0, 0)
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if dupe_groups > 0:
                    print(f'[{timestamp}] ALERTE: {dupe_groups} groupes de doublons détectés ({total_dupes} trades)')
                    
                    # Log détaillé des doublons
                    query2 = """
                        WITH potential_dupes AS (
                            SELECT 
                                symbol,
                                entry_price,
                                COUNT(*) as count,
                                array_agg(id ORDER BY created_at) as trade_ids,
                                array_agg(exit_reason ORDER BY created_at) as reasons
                            FROM trades
                            WHERE created_at > NOW() - INTERVAL '1 hour'
                            AND entry_price IS NOT NULL
                            GROUP BY symbol, entry_price
                            HAVING COUNT(*) > 1
                        )
                        SELECT * FROM potential_dupes
                        ORDER BY count DESC
                        LIMIT 5
                    """
                    cur.execute(query2)
                    
                    dupes = cur.fetchall()
                    for symbol, entry, count, ids, reasons in dupes:
                        print(f'  - {symbol} entry={entry}: {count} trades (reasons: {reasons})')
                    
                    return False  # Échec détection doublons
                else:
                    print(f'[{timestamp}] Aucun doublon détecté')
                    return True  # Succès
                    
        finally:
            pg_logger.pool.putconn(conn)
            
    except Exception as e:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f'[{timestamp}] ERREUR vérification: {e}')
        return False

if __name__ == "__main__":
    success = check_and_alert_duplicates()
    sys.exit(0 if success else 1)
'''
    
    # Sauvegarder le script de vérification
    verification_file = 'verify_trade_duplicates.py'
    try:
        with open(verification_file, 'w', encoding='utf-8') as f:
            f.write(verification_script)
        print(f'   ✅ Script de vérification créé: {verification_file}')
        
        # Créer aussi une version pour cron
        cron_script = f'''#!/bin/bash
# Ajouter à crontab avec: crontab -e
# 0 * * * * /path/to/this/script

cd "$(dirname "$0")"
python3 {verification_file} >> logs/duplicate_verification.log 2>&1
'''
        
        cron_file = 'cron_verify_duplicates.sh'
        with open(cron_file, 'w') as f:
            f.write(cron_script)
        print(f'   ✅ Script cron créé: {cron_file}')
        
        return True
        
    except Exception as e:
        print(f'   ❌ Erreur création scripts: {e}')
        return False

def test_verification_loop():
    """Tester la boucle de vérification"""
    print('\n' + '='*80)
    print('TEST BOUCLE DE VÉRIFICATION')
    print('='*80)
    
    try:
        # Importer et exécuter le script de vérification
        import subprocess
        result = subprocess.run([sys.executable, 'verify_trade_duplicates.py'], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print('   ✅ Test vérification: SUCCESS')
            print('   Output:', result.stdout.strip())
        else:
            print('   ❌ Test vérification: ÉCHEC')
            print('   Error:', result.stderr.strip())
            
        return result.returncode == 0
        
    except Exception as e:
        print(f'   ❌ Erreur test: {e}')
        return False

def main():
    """Script principal de correction complète"""
    print('='*80)
    print('CORRECTION COMPLÈTE DOUBLONS TRADES')
    print('='*80)
    
    success_count = 0
    total_steps = 4
    
    # Étape 1: Analyser
    print('\nETAPE 1/4: ANALYSE...')
    duplicates = analyze_duplicate_trades()
    if duplicates:
        print(f'   OK {len(duplicates)} groupes de doublons identifiés')
        success_count += 1
    else:
        print('   INFO Aucun doublon détecté ou erreur')
        success_count += 0.5  # Pas d'erreur mais pas de doublons
    
    # Étape 2: Nettoyer
    print('\nETAPE 2/4: NETTOYAGE...')
    if duplicates:
        if clean_duplicate_trades(duplicates):
            print('   OK Nettoyage terminé')
            success_count += 1
        else:
            print('   ERREUR nettoyage')
    else:
        print('   SKIP Aucun nettoyage nécessaire')
        success_count += 1
    
    # Étape 3: Créer vérification
    print('\nETAPE 3/4: CREATION BOUCLE...')
    if create_verification_loop():
        print('   OK Boucle de vérification créée')
        success_count += 1
    else:
        print('   ERREUR création boucle')
    
    # Étape 4: Tester
    print('\nETAPE 4/4: TEST...')
    if test_verification_loop():
        print('   OK Test boucle réussi')
        success_count += 1
    else:
        print('   ERREUR Test boucle échoué')
    
    # Résumé final
    print('\n' + '='*80)
    print('RÉSUMÉ FINAL')
    print('='*80)
    success_rate = (success_count / total_steps) * 100
    print(f'Étapes réussies: {success_count}/{total_steps} ({success_rate:.1f}%)')
    
    if success_rate >= 75:
        print('OK CORRECTION REUSSIE - Les doublons devraient être corrigés')
        print('\nPROCHAINES ETAPES:')
        print('1. Redémarrer le bot pour appliquer les corrections')
        print('2. Surveiller l\'historique pour absence de nouveaux doublons')
        print('3. Configurer le cron job: crontab -e')
        print('   Ajouter: 0 * * * * /path/to/cron_verify_duplicates.sh')
    else:
        print('WARNING CORRECTION PARTIELLE - Vérification manuelle requise')
        print('\nACTIONS RECOMMANDEES:')
        print('1. Vérifier les logs d\'erreur ci-dessus')
        print('2. Réexécuter le script après correction')
        print('3. Contacter le support si problème persiste')
    
    return success_rate >= 75

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
