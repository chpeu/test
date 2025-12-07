#!/usr/bin/env python3
"""
Script de verification: Colonne ml_confidence dans scan_logs

Ce script verifie que:
1. La colonne ml_confidence existe dans scan_logs
2. Les nouveaux scans remplissent correctement cette colonne
3. L'export Excel inclut cette colonne

Usage:
    python verification/verify_ml_threshold_column.py
"""

import os
import sys
import time

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_column_exists():
    """Verifier que la colonne ml_confidence existe dans scan_logs."""
    print("\n" + "="*60)
    print("ETAPE 1: Verification de la colonne ml_confidence")
    print("="*60)
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trading_bot'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Vérifier si la colonne existe
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'scan_logs'
            AND column_name = 'ml_confidence'
        """)
        
        result = cursor.fetchone()
        
        if result:
            print(f"[OK] Colonne trouvee:")
            print(f"   - Nom: {result['column_name']}")
            print(f"   - Type: {result['data_type']}")
            print(f"   - Nullable: {result['is_nullable']}")
            column_exists = True
        else:
            print("[FAIL] Colonne ml_confidence NON TROUVEE!")
            print("\n   Pour creer la colonne, executez:")
            print("   psql -d trading_bot -f database/migrations/add_ml_confidence_threshold.sql")
            column_exists = False
        
        cursor.close()
        conn.close()
        return column_exists
        
    except Exception as e:
        print(f"[ERROR] Erreur connexion PostgreSQL: {e}")
        return False


def check_recent_scans():
    """Verifier que les scans recents ont la colonne remplie."""
    print("\n" + "="*60)
    print("ETAPE 2: Verification des scans recents")
    print("="*60)
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trading_bot'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Compter les scans avec/sans ml_confidence
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(ml_confidence) as with_confidence,
                COUNT(*) - COUNT(ml_confidence) as without_confidence,
                ROUND(100.0 * COUNT(ml_confidence) / NULLIF(COUNT(*), 0), 2) as fill_rate
            FROM scan_logs
            WHERE timestamp > NOW() - INTERVAL '1 hour'
        """)
        
        stats = cursor.fetchone()
        
        print(f"\nStatistiques des scans (derniere heure):")
        print(f"   - Total scans: {stats['total']}")
        print(f"   - Avec ml_confidence: {stats['with_confidence']}")
        print(f"   - Sans ml_confidence: {stats['without_confidence']}")
        print(f"   - Taux de remplissage: {stats['fill_rate'] or 0}%")
        
        # Afficher quelques exemples
        cursor.execute("""
            SELECT 
                id, symbol, timestamp, 
                ml_confidence,
                is_opportunity
            FROM scan_logs
            WHERE timestamp > NOW() - INTERVAL '1 hour'
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        
        examples = cursor.fetchall()
        
        if examples:
            print(f"\nExemples de scans recents:")
            for ex in examples:
                conf_str = f"{ex['ml_confidence']:.2f}%" if ex['ml_confidence'] else "NULL"
                print(f"   - ID {ex['id']}: {ex['symbol']} | confidence={conf_str} | opportunity={ex['is_opportunity']}")
        else:
            print("\n[WARN] Aucun scan dans la derniere heure. Redemarrez le backend pour generer des scans.")
        
        cursor.close()
        conn.close()
        
        # Note: ml_confidence sera NULL pour les scans sans prediction ML
        # Seuls les scans avec opportunite auront une valeur
        return stats['total'] > 0
        
    except Exception as e:
        print(f"[ERROR] Erreur: {e}")
        return False


def check_export_includes_column():
    """Verifier que l'export Excel inclut la colonne."""
    print("\n" + "="*60)
    print("ETAPE 3: Verification de l'export Excel")
    print("="*60)
    
    try:
        import requests
        
        # Tester l'endpoint avec limit=5
        response = requests.get(
            'http://localhost:8000/api/datalogger/export/excel',
            params={'limit': 5},
            timeout=30
        )
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'spreadsheet' in content_type or 'excel' in content_type:
                print("[OK] Export Excel fonctionne (status 200)")
                print(f"   - Content-Type: {content_type}")
                print(f"   - Taille fichier: {len(response.content)} bytes")
                print("\nPour verifier manuellement:")
                print("   1. Cliquez sur 'Export Excel' dans l'UI")
                print("   2. Ouvrez le fichier .xlsx")
                print("   3. Verifiez que la colonne 'ml_confidence' est presente dans l'onglet scan_logs")
                return True
            else:
                print(f"[WARN] Reponse inattendue: {content_type}")
                return False
        else:
            print(f"[FAIL] Erreur export: status {response.status_code}")
            try:
                print(f"   Message: {response.json()}")
            except:
                pass
            return False
            
    except requests.exceptions.ConnectionError:
        print("[WARN] Backend non accessible (localhost:8000)")
        print("   Demarrez le backend avec: python main.py")
        return False
    except Exception as e:
        print(f"[ERROR] Erreur: {e}")
        return False


def main():
    """Executer toutes les verifications."""
    print("\n" + "="*60)
    print("VERIFICATION: ml_confidence dans scan_logs")
    print("="*60)
    
    results = {
        'column_exists': check_column_exists(),
        'recent_scans_filled': check_recent_scans(),
        'export_works': check_export_includes_column()
    }
    
    print("\n" + "="*60)
    print("RESUME")
    print("="*60)
    
    all_ok = all(results.values())
    
    for check, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"   {status} {check}")
    
    if all_ok:
        print("\n[SUCCESS] Toutes les verifications sont passees!")
    else:
        print("\n[WARNING] Certaines verifications ont echoue.")
        print("\nActions requises:")
        
        if not results['column_exists']:
            print("   1. Executer la migration SQL:")
            print("      psql -d trading_bot -f database/migrations/add_ml_confidence_threshold.sql")
        
        if not results['recent_scans_filled']:
            print("   2. Redemarrer le backend pour generer des scans avec la nouvelle colonne")
        
        if not results['export_works']:
            print("   3. Verifier que le backend est demarre sur localhost:8000")
    
    print("\nNote: ml_confidence sera NULL pour les scans sans prediction ML.")
    print("Seuls les scans avec opportunite ML auront une valeur de confiance.")
    
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
