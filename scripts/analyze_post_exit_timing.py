"""
Analyse des timings post-exit pour optimiser les paramètres
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

def analyze_post_exit_timing():
    # Utiliser le datalogger existant
    from core.postgresql_datalogger import get_pg_datalogger
    
    datalogger = get_pg_datalogger()
    if not datalogger or not datalogger.enabled:
        print("❌ PostgreSQL DataLogger non disponible")
        return
    
    conn = datalogger._get_connection()
    if not conn:
        print("❌ Connexion PostgreSQL non disponible")
        return
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Statistiques générales
    cursor.execute("""
        SELECT 
            COUNT(*) as total_trades,
            AVG(tracking_duration_sec) as avg_tracking_duration,
            AVG(sample_count) as avg_samples,
            AVG(sample_interval_ms) as avg_interval_ms,
            AVG(time_to_mfe_sec) as avg_time_to_mfe,
            MAX(time_to_mfe_sec) as max_time_to_mfe,
            MIN(time_to_mfe_sec) as min_time_to_mfe
        FROM trade_post_exit_analysis
        WHERE time_to_mfe_sec IS NOT NULL
    """)
    stats = cursor.fetchone()
    
    print("=" * 70)
    print("📊 ANALYSE DES TIMINGS POST-EXIT")
    print("=" * 70)
    print(f"\n📈 Statistiques générales ({stats['total_trades']} trades):")
    print(f"   - Durée tracking: {stats['avg_tracking_duration']:.0f}s (5 min)")
    print(f"   - Samples moyens: {stats['avg_samples']:.0f}")
    print(f"   - Interval: {stats['avg_interval_ms']:.0f}ms")
    
    print(f"\n⏱️ Temps jusqu'au MFE post-exit:")
    print(f"   - Moyenne: {stats['avg_time_to_mfe']:.1f}s")
    print(f"   - Min: {stats['min_time_to_mfe']:.1f}s")
    print(f"   - Max: {stats['max_time_to_mfe']:.1f}s")
    
    # 2. Distribution du temps jusqu'au MFE
    cursor.execute("""
        SELECT 
            CASE 
                WHEN time_to_mfe_sec <= 30 THEN '0-30s'
                WHEN time_to_mfe_sec <= 60 THEN '30-60s'
                WHEN time_to_mfe_sec <= 120 THEN '1-2min'
                WHEN time_to_mfe_sec <= 180 THEN '2-3min'
                WHEN time_to_mfe_sec <= 240 THEN '3-4min'
                WHEN time_to_mfe_sec <= 300 THEN '4-5min'
                ELSE '>5min'
            END as time_bucket,
            COUNT(*) as count
        FROM trade_post_exit_analysis
        WHERE time_to_mfe_sec IS NOT NULL
        GROUP BY 1
        ORDER BY 
            CASE 
                WHEN time_to_mfe_sec <= 30 THEN 1
                WHEN time_to_mfe_sec <= 60 THEN 2
                WHEN time_to_mfe_sec <= 120 THEN 3
                WHEN time_to_mfe_sec <= 180 THEN 4
                WHEN time_to_mfe_sec <= 240 THEN 5
                WHEN time_to_mfe_sec <= 300 THEN 6
                ELSE 7
            END
    """)
    
    print(f"\n📊 Distribution du temps jusqu'au MFE:")
    for row in cursor.fetchall():
        pct = row['count'] / stats['total_trades'] * 100
        bar = '█' * int(pct / 2)
        print(f"   {row['time_bucket']:8s}: {bar} {row['count']} ({pct:.0f}%)")
    
    # 3. Trades où le MFE arrive après 5 min
    cursor.execute("""
        SELECT 
            COUNT(*) as count,
            AVG(post_exit_mfe_pct) as avg_mfe
        FROM trade_post_exit_analysis
        WHERE time_to_mfe_sec > 300 OR time_to_mfe_sec IS NULL
    """)
    late_mfe = cursor.fetchone()
    
    print(f"\n⚠️ Trades avec MFE après 5 min ou non capturé:")
    print(f"   - Count: {late_mfe['count']}")
    if late_mfe['avg_mfe']:
        print(f"   - MFE moyen: {late_mfe['avg_mfe']:.2f}%")
    
    # 4. Recommandations
    print("\n" + "=" * 70)
    print("🎯 RECOMMANDATIONS")
    print("=" * 70)
    
    avg_time = float(stats['avg_time_to_mfe'] or 0)
    max_time = float(stats['max_time_to_mfe'] or 0)
    
    if max_time <= 180:
        print("\n✅ Durée 5 min est SUFFISANTE")
        print("   - Le MFE arrive en moyenne en {:.0f}s".format(avg_time))
        print("   - Max observé: {:.0f}s".format(max_time))
        print("   - Vous pourriez même réduire à 3 min sans perdre d'info")
    elif max_time <= 300:
        print("\n✅ Durée 5 min est CORRECTE")
        print("   - Le MFE arrive parfois proche de 5 min")
        print("   - Gardez 5 min pour capturer tous les MFE")
    else:
        print("\n⚠️ Durée 5 min pourrait être INSUFFISANTE")
        print("   - Certains MFE arrivent après 5 min")
        print("   - Considérez augmenter à 7-10 min")
    
    conn.close()

if __name__ == "__main__":
    analyze_post_exit_timing()
