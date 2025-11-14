#!/usr/bin/env python3
"""
Export PostgreSQL DataLogger to Excel
Exporte toutes les tables du datalogger vers un fichier Excel multi-feuilles
"""

import os
import sys
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import argparse

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("❌ psycopg2 non installé. Installez-le avec: pip install psycopg2-binary")
    sys.exit(1)

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("❌ pandas non installé. Installez-le avec: pip install pandas")
    sys.exit(1)

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    print("❌ openpyxl non installé. Installez-le avec: pip install openpyxl")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataLoggerExporter:
    """Export PostgreSQL DataLogger to Excel"""

    # Liste de toutes les tables à exporter
    # Note: scan_logs est partitionnée - on interroge la table parente qui agrège toutes les partitions
    TABLES_TO_EXPORT = [
        'trading_sessions',
        'config_snapshots',
        'scan_logs',  # Table partitionnée - agrège toutes les partitions automatiquement
        'opportunities',
        'trades',
        'market_context',
        'scan_errors',
        'model_predictions',
        'features_engineered'
    ]

    def __init__(
        self,
        connection_string: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialiser l'exporteur

        Args:
            connection_string: String de connexion PostgreSQL complète
            host: Host PostgreSQL (si connection_string non fourni)
            port: Port PostgreSQL
            database: Nom de la base
            user: Utilisateur
            password: Mot de passe
        """
        # Construire connection string si non fourni
        if connection_string:
            self.connection_string = connection_string
        else:
            # Utiliser variables d'environnement ou paramètres
            host = host or os.getenv('POSTGRES_HOST', 'localhost')
            port = port or int(os.getenv('POSTGRES_PORT', '5432'))
            database = database or os.getenv('POSTGRES_DB', 'trade_cursor_ml')
            user = user or os.getenv('POSTGRES_USER', 'postgres')
            password = password or os.getenv('POSTGRES_PASSWORD', '')

            self.connection_string = (
                f"host={host} port={port} dbname={database} "
                f"user={user} password={password}"
            )

        self.conn = None

    def connect(self) -> bool:
        """Connecter à PostgreSQL"""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            logger.info("✅ Connecté à PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
            return False

    def disconnect(self):
        """Déconnecter de PostgreSQL"""
        if self.conn:
            self.conn.close()
            logger.info("🔌 Déconnecté de PostgreSQL")

    def get_table_data(self, table_name: str, limit: Optional[int] = None) -> Optional[pd.DataFrame]:
        """
        Récupérer les données d'une table

        Args:
            table_name: Nom de la table
            limit: Limite du nombre de lignes (None = toutes)

        Returns:
            DataFrame pandas avec les données, ou None si erreur
        """
        try:
            query = f"SELECT * FROM {table_name}"
            if limit:
                query += f" LIMIT {limit}"

            logger.info(f"📊 Lecture table: {table_name}")
            df = pd.read_sql_query(query, self.conn)

            # Convertir les colonnes datetime timezone-aware en timezone-naive
            # (Excel ne supporte pas les timezones)
            for col in df.columns:
                if pd.api.types.is_datetime64tz_dtype(df[col]):
                    df[col] = df[col].dt.tz_localize(None)

            logger.info(f"   ✅ {len(df)} lignes récupérées")
            return df
        except Exception as e:
            logger.warning(f"   ⚠️ Erreur lecture table {table_name}: {e}")
            return None

    def export_to_excel(
        self,
        output_file: Optional[str] = None,
        limit: Optional[int] = None,
        tables: Optional[List[str]] = None
    ) -> str:
        """
        Exporter toutes les tables vers Excel

        Args:
            output_file: Chemin du fichier de sortie (None = généré automatiquement)
            limit: Limite du nombre de lignes par table (None = toutes)
            tables: Liste des tables à exporter (None = toutes)

        Returns:
            Chemin du fichier créé
        """
        if not self.conn:
            raise RuntimeError("Pas de connexion PostgreSQL. Appelez connect() d'abord.")

        # Générer nom de fichier si non fourni
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"datalogger_export_{timestamp}.xlsx"

        # Déterminer les tables à exporter
        tables_to_export = tables or self.TABLES_TO_EXPORT

        logger.info(f"📥 Export vers: {output_file}")
        logger.info(f"📋 Tables à exporter: {len(tables_to_export)}")

        # Créer le writer Excel
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            exported_count = 0

            for table_name in tables_to_export:
                df = self.get_table_data(table_name, limit)

                if df is not None and not df.empty:
                    # Tronquer le nom de la feuille si nécessaire (max 31 caractères)
                    sheet_name = table_name[:31]

                    # Écrire dans Excel
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    exported_count += 1
                    logger.info(f"   ✅ Feuille '{sheet_name}' créée ({len(df)} lignes)")
                else:
                    logger.warning(f"   ⚠️ Table '{table_name}' vide ou inexistante - ignorée")

            logger.info(f"✅ Export terminé: {exported_count}/{len(tables_to_export)} tables exportées")
            logger.info(f"📄 Fichier créé: {output_file}")

        return output_file

    def export_summary(self) -> Dict[str, Any]:
        """
        Récupérer un résumé des données disponibles

        Returns:
            Dictionnaire avec le résumé
        """
        if not self.conn:
            raise RuntimeError("Pas de connexion PostgreSQL. Appelez connect() d'abord.")

        summary = {}

        for table_name in self.TABLES_TO_EXPORT:
            try:
                cursor = self.conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                summary[table_name] = {
                    'count': count,
                    'status': '✅' if count > 0 else '⚠️ vide'
                }
                cursor.close()
            except Exception as e:
                summary[table_name] = {
                    'count': 0,
                    'status': f'❌ erreur: {e}'
                }

        return summary


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='Export PostgreSQL DataLogger to Excel')
    parser.add_argument('--host', default=None, help='PostgreSQL host')
    parser.add_argument('--port', type=int, default=None, help='PostgreSQL port')
    parser.add_argument('--database', default=None, help='Database name')
    parser.add_argument('--user', default=None, help='PostgreSQL user')
    parser.add_argument('--password', default=None, help='PostgreSQL password')
    parser.add_argument('--output', '-o', default=None, help='Output Excel file')
    parser.add_argument('--limit', type=int, default=None, help='Limit rows per table')
    parser.add_argument('--tables', nargs='+', default=None, help='Specific tables to export')
    parser.add_argument('--summary', action='store_true', help='Show summary only')

    args = parser.parse_args()

    # Créer l'exporteur
    exporter = DataLoggerExporter(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password
    )

    # Connecter
    if not exporter.connect():
        logger.error("❌ Échec de la connexion - arrêt")
        return 1

    try:
        # Mode résumé
        if args.summary:
            logger.info("\n📊 RÉSUMÉ DES DONNÉES DISPONIBLES")
            logger.info("=" * 60)
            summary = exporter.export_summary()
            for table_name, info in summary.items():
                status = info['status']
                count = info['count']
                logger.info(f"{status} {table_name:25s} : {count:>10,} lignes")
            logger.info("=" * 60)
            return 0

        # Mode export
        output_file = exporter.export_to_excel(
            output_file=args.output,
            limit=args.limit,
            tables=args.tables
        )

        logger.info(f"\n✅ Export terminé avec succès!")
        logger.info(f"📄 Fichier: {output_file}")

        return 0

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'export: {e}", exc_info=True)
        return 1

    finally:
        exporter.disconnect()


if __name__ == '__main__':
    sys.exit(main())
