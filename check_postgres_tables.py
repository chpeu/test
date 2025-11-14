#!/usr/bin/env python3
"""
Script pour vérifier les tables PostgreSQL de trade_cursor_ml
"""
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("❌ psycopg2 n'est pas installé")
    print("Installez-le avec : pip install psycopg2-binary")
    exit(1)

def check_postgres_connection():
    """Vérifie la connexion PostgreSQL et liste les tables"""

    # Configuration depuis .env
    config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    if not config['password']:
        print("⚠️ POSTGRES_PASSWORD n'est pas défini dans .env")
        config['password'] = input("Entrez le mot de passe PostgreSQL : ")

    try:
        # Connexion
        print(f"🔌 Connexion à {config['database']}@{config['host']}:{config['port']}...")
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()

        print("✅ Connexion réussie !\n")

        # Lister les tables
        cursor.execute("""
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name;
        """)

        tables = cursor.fetchall()

        if tables:
            print(f"📊 Tables trouvées ({len(tables)}) :\n")
            print(f"{'Schema':<15} {'Table':<30} {'Type':<15}")
            print("=" * 60)
            for schema, table, table_type in tables:
                print(f"{schema:<15} {table:<30} {table_type:<15}")

            # Compter les lignes par table
            print("\n📈 Nombre de lignes par table :\n")
            for schema, table, _ in tables:
                try:
                    cursor.execute(
                        sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                            sql.Identifier(schema),
                            sql.Identifier(table)
                        )
                    )
                    count = cursor.fetchone()[0]
                    print(f"  {schema}.{table}: {count:,} lignes")
                except Exception as e:
                    print(f"  {schema}.{table}: Erreur - {e}")
        else:
            print("⚠️ Aucune table trouvée dans la base de données")

        cursor.close()
        conn.close()

    except psycopg2.OperationalError as e:
        print(f"❌ Erreur de connexion PostgreSQL :")
        print(f"   {e}")
        print("\n💡 Vérifiez que :")
        print("   1. PostgreSQL est démarré")
        print("   2. Le mot de passe est correct dans .env")
        print("   3. La base de données existe")
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    check_postgres_connection()
