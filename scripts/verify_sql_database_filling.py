#!/usr/bin/env python3
"""
Script pour vérifier que la base SQL se remplit correctement
Vérifie les colonnes corrigées et l'état général des scan_logs
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import asyncio

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def main():
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        from config import TRADING_CONFIG
        import psycopg2
        from psycopg2.extras import DictCursor
        
        print("🔍 VÉRIFICATION BASE DE DONNÉES SQL")
        print("=" * 60)
        
        # Connexion directe à PostgreSQL
        try:
            conn = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=os.getenv('POSTGRES_PORT', '5432'),
                database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                user=os.getenv('POSTGRES_USER', 'postgres'),
                password=os.getenv('POSTGRES_PASSWORD', '')
            )
            cursor = conn.cursor(cursor_factory=DictCursor)
            print("✅ Connexion PostgreSQL réussie")
        except Exception as e:
            print(f"❌ Erreur connexion PostgreSQL: {e}")
            return
        
        # 1. Statistiques générales de la table scan_logs
        print("\n📊 STATISTIQUES GÉNÉRALES")
        print("-" * 40)
        
        cursor.execute("SELECT COUNT(*) as total FROM scan_logs")
        total_scans = cursor.fetchone()['total']
        print(f"Total scans: {total_scans:,}")
        
        # Scans des dernières 24h
        cursor.execute("""
            SELECT COUNT(*) as recent 
            FROM scan_logs 
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """)
        recent_scans = cursor.fetchone()['recent']
        print(f"Scans dernières 24h: {recent_scans:,}")
        
        # 2. Vérification des colonnes corrigées (breakout_distance, wick_ratio, reject_reason_category)
        print("\n🔧 VÉRIFICATION COLONNES CORRIGÉES")
        print("-" * 40)
        
        # Colonnes à vérifier
        columns_to_check = [
            'breakout_distance_1m',
            'breakout_distance_5m', 
            'wick_ratio_1m',
            'wick_ratio_5m',
            'reject_reason_category',
            'ml_confidence',
            'ml_threshold_used',
            'ml_threshold_type'
        ]
        
        for column in columns_to_check:
            # Compter les NULL vs NON-NULL pour les dernières 24h
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT({column}) as non_null,
                    COUNT(*) - COUNT({column}) as null_count
                FROM scan_logs 
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)
            stats = cursor.fetchone()
            
            if stats['total'] > 0:
                null_pct = (stats['null_count'] / stats['total']) * 100
                non_null_pct = (stats['non_null'] / stats['total']) * 100
                status = "✅" if null_pct < 50 else "⚠️" if null_pct < 80 else "❌"
                
                print(f"  {status} {column:<25}: {stats['non_null']:>4}/{stats['total']:<4} remplis ({non_null_pct:.1f}%)")
            else:
                print(f"  ℹ️  {column:<25}: Aucun scan récent")
        
        # 3. Vérification des rejets récents avec catégories
        print("\n📋 ANALYSE DES REJETS RÉCENTS")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                reject_reason_category,
                COUNT(*) as count
            FROM scan_logs 
            WHERE created_at >= NOW() - INTERVAL '24 hours'
                AND reject_reason_category IS NOT NULL
            GROUP BY reject_reason_category
            ORDER BY count DESC
            LIMIT 10
        """)
        
        rejection_stats = cursor.fetchall()
        if rejection_stats:
            print("Top 10 catégories de rejet:")
            for stat in rejection_stats:
                print(f"  • {stat['reject_reason_category']:<25}: {stat['count']:>4} occurrences")
        else:
            print("  ℹ️  Aucun rejet catégorisé récent")
        
        # 4. Vérification des métriques ML
        print("\n🤖 MÉTRIQUES ML")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_ml,
                COUNT(ml_confidence) as with_confidence,
                COUNT(ml_threshold_used) as with_threshold,
                AVG(ml_confidence) as avg_confidence
            FROM scan_logs 
            WHERE created_at >= NOW() - INTERVAL '24 hours'
                AND reject_reason_category LIKE '%ml_%'
        """)
        
        ml_stats = cursor.fetchone()
        if ml_stats['total_ml'] > 0:
            print(f"  📊 Rejets ML: {ml_stats['total_ml']}")
            print(f"  🎯 Avec confiance: {ml_stats['with_confidence']}/{ml_stats['total_ml']}")
            print(f"  🎚️  Avec seuil: {ml_stats['with_threshold']}/{ml_stats['total_ml']}")
            if ml_stats['avg_confidence']:
                print(f"  📈 Confiance moyenne: {ml_stats['avg_confidence']:.1f}%")
        else:
            print("  ℹ️  Aucun rejet ML récent")
        
        # 5. Vérification des setups trouvés vs rejets
        print("\n🎯 SETUPS vs REJETS")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN is_opportunity = true THEN 1 END) as opportunities,
                COUNT(CASE WHEN is_opportunity = false THEN 1 END) as rejections,
                COUNT(*) as total
            FROM scan_logs 
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """)
        
        setup_stats = cursor.fetchone()
        if setup_stats['total'] > 0:
            opp_pct = (setup_stats['opportunities'] / setup_stats['total']) * 100
            rej_pct = (setup_stats['rejections'] / setup_stats['total']) * 100
            
            print(f"  ✅ Opportunités: {setup_stats['opportunities']:>4} ({opp_pct:.1f}%)")
            print(f"  ❌ Rejets: {setup_stats['rejections']:>4} ({rej_pct:.1f}%)")
        
        # 6. Exemples récents avec données complètes
        print("\n📝 EXEMPLES RÉCENTS (5 derniers)")
        print("-" * 40)
        
        cursor.execute("""
            SELECT 
                created_at,
                symbol,
                reject_reason_category,
                breakout_distance_1m,
                wick_ratio_1m,
                ml_confidence,
                is_opportunity
            FROM scan_logs 
            WHERE created_at >= NOW() - INTERVAL '2 hours'
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        recent_examples = cursor.fetchall()
        if recent_examples:
            for example in recent_examples:
                time_str = example['created_at'].strftime('%H:%M:%S')
                symbol = example['symbol'][:15] if example['symbol'] else 'N/A'
                category = example['reject_reason_category'][:20] if example['reject_reason_category'] else 'NULL'
                breakout = f"{example['breakout_distance_1m']:.3f}" if example['breakout_distance_1m'] else 'NULL'
                wick = f"{example['wick_ratio_1m']:.2f}" if example['wick_ratio_1m'] else 'NULL'
                ml_conf = f"{example['ml_confidence']:.1f}%" if example['ml_confidence'] else 'NULL'
                opp = "✅" if example['is_opportunity'] else "❌"
                
                print(f"  {time_str} | {symbol:<15} | {category:<20} | BD:{breakout:<6} | WR:{wick:<6} | ML:{ml_conf:<6} | {opp}")
        else:
            print("  ℹ️  Aucun scan très récent")
        
        # 7. Résumé et recommandations
        print("\n" + "=" * 60)
        print("📋 RÉSUMÉ")
        print("=" * 60)
        
        issues = []
        
        # Vérifier si les colonnes se remplissent bien
        if recent_scans == 0:
            issues.append("🔴 Aucun scan récent - Le bot semble arrêté")
        
        # Vérifier quelques colonnes critiques
        for column in ['breakout_distance_1m', 'wick_ratio_1m', 'reject_reason_category']:
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT({column}) as non_null
                FROM scan_logs 
                WHERE created_at >= NOW() - INTERVAL '2 hours'
            """)
            stats = cursor.fetchone()
            
            if stats['total'] > 10:  # Seulement si assez de données
                null_pct = ((stats['total'] - stats['non_null']) / stats['total']) * 100
                if null_pct > 70:
                    issues.append(f"🟡 {column}: {null_pct:.0f}% NULL (correction peut-être incomplète)")
        
        if not issues:
            print("✅ BASE DE DONNÉES EN BON ÉTAT")
            print("  • Les corrections de colonnes vides fonctionnent")
            print("  • Les scans se loggent correctement") 
        else:
            print("⚠️ PROBLÈMES DÉTECTÉS:")
            for issue in issues:
                print(f"  {issue}")
        
        cursor.close()
        conn.close()
        
    except ImportError as e:
        print(f"❌ Erreur import: {e}")
        print("Assurez-vous que le bot est démarré et que psycopg2 est installé")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
