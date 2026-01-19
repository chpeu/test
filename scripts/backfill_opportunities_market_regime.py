#!/usr/bin/env python3
"""
Script de backfill pour les colonnes market_regime dans opportunities
======================================================================

Remplit rétroactivement les colonnes market_regime NULL en utilisant:
1. Les données de market_regime_history (si disponibles pour la période)
2. Un fallback vers 'UNKNOWN' si pas de données

Usage:
    python scripts/backfill_opportunities_market_regime.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

def backfill_market_regime():
    """Remplit les colonnes market_regime NULL dans opportunities"""
    
    print("=" * 80)
    print("BACKFILL MARKET REGIME - TABLE OPPORTUNITIES")
    print("=" * 80)
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=5432,
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Compter les opportunities avec market_regime NULL
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM opportunities 
            WHERE market_regime IS NULL
        """)
        null_count = cursor.fetchone()['count']
        
        print(f"\n📊 Opportunities avec market_regime NULL: {null_count}")
        
        if null_count == 0:
            print("✅ Toutes les opportunities ont déjà un market_regime!")
            return
        
        # 2. Stratégie de backfill simple
        print("\n🔄 Stratégie: Mettre 'UNKNOWN' pour toutes les anciennes opportunities")
        print("   (Les nouvelles opportunities auront le régime correct après redémarrage)")
        
        # Mettre UNKNOWN pour toutes les colonnes NULL
        cursor.execute("""
            UPDATE opportunities
            SET market_regime = 'UNKNOWN'
            WHERE market_regime IS NULL
        """)
        
        updated = cursor.rowcount
        conn.commit()
        
        print(f"✅ {updated} opportunities mises à jour avec 'UNKNOWN'")
        
        # 4. Vérification finale
        cursor.execute("""
            SELECT 
                market_regime,
                COUNT(*) as count
            FROM opportunities
            GROUP BY market_regime
            ORDER BY count DESC
        """)
        
        print("\n📊 Distribution des market_regime après backfill:")
        for row in cursor.fetchall():
            regime = row['market_regime'] or 'NULL'
            count = row['count']
            print(f"   {regime:15s}: {count:6d}")
        
        # 5. Vérifier les autres colonnes NULL
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(market_regime) as has_regime,
                COUNT(market_regime_score) as has_score,
                COUNT(market_regime_confidence) as has_confidence,
                COUNT(market_regime_reason) as has_reason,
                COUNT(session_context) as has_session,
                COUNT(market_regime_details) as has_details,
                COUNT(market_regime_signal) as has_signal
            FROM opportunities
        """)
        
        stats = cursor.fetchone()
        total = stats['total']
        
        print(f"\n📊 Remplissage des colonnes market_regime (sur {total} total):")
        print(f"   market_regime:            {stats['has_regime']:6d} ({stats['has_regime']/total*100:.1f}%)")
        print(f"   market_regime_score:      {stats['has_score']:6d} ({stats['has_score']/total*100:.1f}%)")
        print(f"   market_regime_confidence: {stats['has_confidence']:6d} ({stats['has_confidence']/total*100:.1f}%)")
        print(f"   market_regime_reason:     {stats['has_reason']:6d} ({stats['has_reason']/total*100:.1f}%)")
        print(f"   session_context:          {stats['has_session']:6d} ({stats['has_session']/total*100:.1f}%)")
        print(f"   market_regime_details:    {stats['has_details']:6d} ({stats['has_details']/total*100:.1f}%)")
        print(f"   market_regime_signal:     {stats['has_signal']:6d} ({stats['has_signal']/total*100:.1f}%)")
        
        print("\n" + "=" * 80)
        print("✅ Backfill terminé!")
        print("=" * 80)
        print("\n💡 Note: Les autres colonnes market_regime_* resteront NULL pour les anciennes")
        print("   opportunities car ces données n'étaient pas collectées à l'époque.")
        print("   Les NOUVELLES opportunities (après redémarrage) auront toutes les colonnes remplies.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    backfill_market_regime()
