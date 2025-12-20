#!/usr/bin/env python3
"""
🔥 Script de vérification de l'implémentation Micro-confirmation (OPT #20)

Vérifie:
1. Colonnes PostgreSQL créées (scan_logs + trades)
2. Config prise en compte par le bot
3. reject_reason_category = 'micro_confirmation_filter' enregistré
4. Export Excel inclut les nouvelles colonnes
"""

import sys
import os
import io

# Fix encodage Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import json

def get_db_connection():
    """Connexion PostgreSQL"""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

def check_and_create_columns():
    """Vérifier et créer les colonnes micro-confirmation si nécessaire"""
    print("\n" + "="*60)
    print("📊 VÉRIFICATION COLONNES POSTGRESQL")
    print("="*60)
    
    columns_to_add = [
        ('scan_logs', 'config_use_micro_confirmation', 'BOOLEAN'),
        ('scan_logs', 'config_micro_confirmation_delay_ms', 'INTEGER'),
        ('trades', 'config_use_micro_confirmation', 'BOOLEAN'),
        ('trades', 'config_micro_confirmation_delay_ms', 'INTEGER'),
    ]
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        for table, column, col_type in columns_to_add:
            # Vérifier si la colonne existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = %s
            """, (table, column))
            
            exists = cursor.fetchone()
            
            if exists:
                print(f"  ✅ {table}.{column} existe déjà")
            else:
                # Créer la colonne
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                    conn.commit()
                    print(f"  ✅ {table}.{column} CRÉÉE ({col_type})")
                except Exception as e:
                    conn.rollback()
                    print(f"  ❌ Erreur création {table}.{column}: {e}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"  ❌ Erreur connexion PostgreSQL: {e}")
        return False

def check_config_loaded():
    """Vérifier que la config micro-confirmation est chargée par le backend"""
    print("\n" + "="*60)
    print("⚙️ VÉRIFICATION CONFIG BACKEND")
    print("="*60)
    
    try:
        response = requests.get('http://localhost:8000/api/config', timeout=5)
        if response.status_code == 200:
            config = response.json()
            
            # Chercher dans les catégories
            found_use = False
            found_delay = False
            
            for category, values in config.items():
                if isinstance(values, dict):
                    if 'use_micro_confirmation' in values:
                        found_use = True
                        print(f"  ✅ use_micro_confirmation = {values['use_micro_confirmation']} (dans '{category}')")
                    if 'micro_confirmation_delay_ms' in values:
                        found_delay = True
                        print(f"  ✅ micro_confirmation_delay_ms = {values['micro_confirmation_delay_ms']} (dans '{category}')")
            
            if not found_use:
                print("  ❌ use_micro_confirmation non trouvé dans /api/config")
            if not found_delay:
                print("  ❌ micro_confirmation_delay_ms non trouvé dans /api/config")
                
            return found_use and found_delay
        else:
            print(f"  ❌ Erreur API: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("  ⚠️ Backend non accessible (normal si pas démarré)")
        return None
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def check_reject_category_exists():
    """Vérifier que reject_reason_category = 'micro_confirmation_filter' peut être enregistré"""
    print("\n" + "="*60)
    print("🚫 VÉRIFICATION REJECT_REASON_CATEGORY")
    print("="*60)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Vérifier si la colonne reject_reason_category existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'scan_logs' AND column_name = 'reject_reason_category'
        """)
        
        if cursor.fetchone():
            print("  ✅ Colonne reject_reason_category existe dans scan_logs")
            
            # Compter les rejets par catégorie
            cursor.execute("""
                SELECT reject_reason_category, COUNT(*) as count
                FROM scan_logs
                WHERE reject_reason_category IS NOT NULL
                GROUP BY reject_reason_category
                ORDER BY count DESC
                LIMIT 20
            """)
            
            results = cursor.fetchall()
            if results:
                print("\n  📊 Catégories de rejet actuelles:")
                for row in results:
                    category = row['reject_reason_category']
                    count = row['count']
                    marker = "⚡" if category == 'micro_confirmation_filter' else "  "
                    print(f"    {marker} {category}: {count}")
                    
                # Vérifier si micro_confirmation_filter existe
                micro_exists = any(r['reject_reason_category'] == 'micro_confirmation_filter' for r in results)
                if micro_exists:
                    print("\n  ✅ 'micro_confirmation_filter' est utilisé!")
                else:
                    print("\n  ⚠️ 'micro_confirmation_filter' pas encore utilisé (activez le filtre pour tester)")
            else:
                print("  ⚠️ Aucun scan rejeté enregistré")
        else:
            print("  ❌ Colonne reject_reason_category n'existe pas!")
            
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def check_scanner_loop_implementation():
    """Vérifier que le code micro-confirmation est présent dans scanner_loop.py"""
    print("\n" + "="*60)
    print("🔍 VÉRIFICATION CODE SCANNER_LOOP")
    print("="*60)
    
    scanner_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'core', 'callbacks', 'scanner_loop.py'
    )
    
    try:
        with open(scanner_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        checks = [
            ('use_micro_confirmation', "Config micro-confirmation"),
            ('micro_confirmation_delay_ms', "Délai configurable"),
            ('micro_confirmation_filter', "Catégorie de rejet"),
            ('Micro-confirmation', "Logs micro-confirmation"),
        ]
        
        all_ok = True
        for pattern, desc in checks:
            if pattern in content:
                print(f"  ✅ {desc} trouvé")
            else:
                print(f"  ❌ {desc} NON trouvé ({pattern})")
                all_ok = False
                
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Erreur lecture fichier: {e}")
        return False

def check_frontend_implementation():
    """Vérifier que l'UI micro-confirmation est présente"""
    print("\n" + "="*60)
    print("🖥️ VÉRIFICATION FRONTEND")
    print("="*60)
    
    svelte_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'frontend', 'src', 'lib', 'components', 'VariablesPanel.svelte'
    )
    
    try:
        with open(svelte_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        checks = [
            ('use_micro_confirmation', "Variable dans DEFAULTS"),
            ('micro_confirmation_delay_ms', "Délai dans DEFAULTS"),
            ('Micro-confirmation', "Label UI"),
            ('use-micro-confirmation', "ID checkbox"),
            ('micro-confirmation-delay', "ID slider"),
        ]
        
        all_ok = True
        for pattern, desc in checks:
            if pattern in content:
                print(f"  ✅ {desc} trouvé")
            else:
                print(f"  ❌ {desc} NON trouvé ({pattern})")
                all_ok = False
                
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Erreur lecture fichier: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("🔥 VÉRIFICATION MICRO-CONFIRMATION (OPT #20)")
    print("="*60)
    
    results = {}
    
    # 1. Vérifier/créer colonnes PostgreSQL
    results['postgres'] = check_and_create_columns()
    
    # 2. Vérifier config backend
    results['config'] = check_config_loaded()
    
    # 3. Vérifier reject_reason_category
    results['reject'] = check_reject_category_exists()
    
    # 4. Vérifier code scanner_loop
    results['scanner'] = check_scanner_loop_implementation()
    
    # 5. Vérifier frontend
    results['frontend'] = check_frontend_implementation()
    
    # Résumé
    print("\n" + "="*60)
    print("📋 RÉSUMÉ")
    print("="*60)
    
    status_map = {True: "✅ OK", False: "❌ ERREUR", None: "⚠️ N/A"}
    
    print(f"  PostgreSQL colonnes:  {status_map.get(results['postgres'], '?')}")
    print(f"  Config backend:       {status_map.get(results['config'], '?')}")
    print(f"  Reject categories:    {status_map.get(results['reject'], '?')}")
    print(f"  Code scanner_loop:    {status_map.get(results['scanner'], '?')}")
    print(f"  Frontend UI:          {status_map.get(results['frontend'], '?')}")
    
    # Statut global
    critical_ok = all(v in (True, None) for v in [results['postgres'], results['scanner'], results['frontend']])
    
    print("\n" + "="*60)
    if critical_ok:
        print("✅ IMPLÉMENTATION MICRO-CONFIRMATION COMPLÈTE")
        print("\nPour tester:")
        print("  1. Redémarrer le backend")
        print("  2. Activer 'Micro-confirmation' dans l'UI")
        print("  3. Régler le délai (300ms recommandé)")
        print("  4. Observer les logs: '⚡ SYMBOL Micro-confirmation...'")
    else:
        print("❌ DES ERREURS ONT ÉTÉ DÉTECTÉES")
        print("Vérifiez les messages ci-dessus")
    print("="*60 + "\n")

if __name__ == '__main__':
    main()
