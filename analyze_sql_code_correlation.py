#!/usr/bin/env python3
"""
Analyse de corrélation entre les tables PostgreSQL et le code Python
"""
import re
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set

# Couleurs pour l'affichage
class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def extract_tables_from_schema(schema_file: str) -> List[str]:
    """Extraire la liste des tables depuis le fichier de schéma SQL"""
    tables = []
    with open(schema_file, 'r', encoding='utf-8') as f:
        content = f.read()
        # Chercher CREATE TABLE statements
        pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)'
        matches = re.findall(pattern, content, re.IGNORECASE)
        tables.extend(matches)
    return sorted(set(tables))

def extract_views_from_schema(schema_file: str) -> List[str]:
    """Extraire la liste des vues depuis le fichier de schéma SQL"""
    views = []
    with open(schema_file, 'r', encoding='utf-8') as f:
        content = f.read()
        # Chercher CREATE VIEW statements
        pattern = r'CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(\w+)'
        matches = re.findall(pattern, content, re.IGNORECASE)
        views.extend(matches)
    return sorted(set(views))

def find_table_usage_in_code(table_name: str, code_dir: str) -> Dict[str, List[str]]:
    """Trouver l'utilisation d'une table dans le code Python"""
    usage = defaultdict(list)

    for py_file in Path(code_dir).rglob('*.py'):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

                # Chercher les références à la table
                patterns = [
                    rf'INSERT\s+INTO\s+{table_name}',
                    rf'UPDATE\s+{table_name}',
                    rf'DELETE\s+FROM\s+{table_name}',
                    rf'FROM\s+{table_name}',
                    rf'JOIN\s+{table_name}',
                    rf'"{table_name}"',
                    rf"'{table_name}'",
                ]

                for line_num, line in enumerate(lines, 1):
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            usage[str(py_file.relative_to(code_dir))].append(
                                f"  Ligne {line_num}: {line.strip()[:100]}"
                            )
                            break
        except Exception as e:
            pass

    return dict(usage)

def analyze_table_columns(schema_file: str, table_name: str) -> List[str]:
    """Extraire les colonnes d'une table depuis le schéma"""
    columns = []
    with open(schema_file, 'r', encoding='utf-8') as f:
        content = f.read()

        # Trouver la définition de la table
        pattern = rf'CREATE\s+TABLE\s+{table_name}\s*\((.*?)\);'
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)

        if match:
            table_def = match.group(1)
            # Extraire les colonnes (ligne commençant par 4 espaces ou tab, puis nom)
            col_pattern = r'^\s+(\w+)\s+(?:VARCHAR|INTEGER|FLOAT|BOOLEAN|TEXT|UUID|BIGINT|BIGSERIAL|TIMESTAMPTZ|JSONB|DATE)'
            for line in table_def.split('\n'):
                col_match = re.match(col_pattern, line.strip(), re.IGNORECASE)
                if col_match:
                    columns.append(col_match.group(1))

    return columns

def main():
    schema_file = 'database/schema_postgresql_complete.sql'
    code_dir = '.'

    print(f"\n{Color.BOLD}{Color.CYAN}=" * 80)
    print(f"ANALYSE DE CORRÉLATION : TABLES POSTGRESQL ↔ CODE PYTHON")
    print(f"=" * 80 + Color.END + "\n")

    # 1. Extraire les tables du schéma
    print(f"{Color.BOLD}{Color.BLUE}📊 TABLES DÉFINIES DANS LE SCHÉMA SQL{Color.END}\n")
    tables = extract_tables_from_schema(schema_file)

    print(f"{Color.GREEN}✅ {len(tables)} tables trouvées :{Color.END}\n")
    for i, table in enumerate(tables, 1):
        print(f"  {i:2d}. {table}")

    # 2. Extraire les vues
    print(f"\n{Color.BOLD}{Color.BLUE}👁️  VUES DÉFINIES DANS LE SCHÉMA SQL{Color.END}\n")
    views = extract_views_from_schema(schema_file)

    print(f"{Color.GREEN}✅ {len(views)} vues trouvées :{Color.END}\n")
    for i, view in enumerate(views, 1):
        print(f"  {i:2d}. {view}")

    # 3. Analyser l'utilisation de chaque table dans le code
    print(f"\n{Color.BOLD}{Color.CYAN}=" * 80)
    print(f"CORRÉLATION TABLES ↔ CODE PYTHON")
    print(f"=" * 80 + Color.END + "\n")

    tables_used = []
    tables_unused = []

    for table in tables:
        usage = find_table_usage_in_code(table, code_dir)

        if usage:
            tables_used.append(table)
            print(f"{Color.BOLD}{Color.GREEN}✅ TABLE: {table}{Color.END}")
            print(f"   {Color.CYAN}Utilisée dans {len(usage)} fichier(s):{Color.END}")

            for file, lines in usage.items():
                print(f"   📄 {file}")
                for line in lines[:3]:  # Limiter à 3 exemples par fichier
                    print(f"      {line[:120]}")
                if len(lines) > 3:
                    print(f"      ... et {len(lines) - 3} autres références")
            print()
        else:
            tables_unused.append(table)

    # 4. Tables non utilisées
    if tables_unused:
        print(f"\n{Color.BOLD}{Color.YELLOW}⚠️  TABLES NON UTILISÉES DANS LE CODE :{Color.END}\n")
        for table in tables_unused:
            print(f"   - {table}")

    # 5. Statistiques finales
    print(f"\n{Color.BOLD}{Color.CYAN}=" * 80)
    print(f"STATISTIQUES")
    print(f"=" * 80 + Color.END + "\n")

    total_tables = len(tables)
    used_count = len(tables_used)
    unused_count = len(tables_unused)
    usage_pct = (used_count / total_tables * 100) if total_tables > 0 else 0

    print(f"📊 Total de tables    : {total_tables}")
    print(f"{Color.GREEN}✅ Tables utilisées   : {used_count} ({usage_pct:.1f}%){Color.END}")
    print(f"{Color.YELLOW}⚠️  Tables non utilisées: {unused_count}{Color.END}")
    print(f"👁️  Total de vues     : {len(views)}")

    # 6. Fichiers Python principaux qui utilisent PostgreSQL
    print(f"\n{Color.BOLD}{Color.BLUE}📁 FICHIERS PYTHON UTILISANT POSTGRESQL :{Color.END}\n")

    pg_files = [
        'core/postgresql_datalogger.py',
        'core/simple_pg_logger.py',
        'core/database.py',
        'core/analytics_database.py',
        'check_postgres_tables.py',
    ]

    for pg_file in pg_files:
        if os.path.exists(pg_file):
            print(f"   ✅ {pg_file}")
        else:
            print(f"   ❌ {pg_file} (non trouvé)")

    # 7. Détails des tables principales
    print(f"\n{Color.BOLD}{Color.CYAN}=" * 80)
    print(f"DÉTAILS DES TABLES PRINCIPALES")
    print(f"=" * 80 + Color.END + "\n")

    main_tables = ['scan_logs', 'opportunities', 'trades', 'trading_sessions']

    for table in main_tables:
        if table in tables:
            columns = analyze_table_columns(schema_file, table)
            print(f"{Color.BOLD}{Color.GREEN}📋 {table.upper()}{Color.END}")
            print(f"   Colonnes : {len(columns)}")
            if columns:
                print(f"   Échantillon : {', '.join(columns[:5])}")
                if len(columns) > 5:
                    print(f"   ... et {len(columns) - 5} autres colonnes")
            print()

    print(f"{Color.BOLD}{Color.CYAN}=" * 80)
    print(f"ANALYSE TERMINÉE")
    print(f"=" * 80 + Color.END + "\n")

if __name__ == "__main__":
    main()
