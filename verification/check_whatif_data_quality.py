"""
Script de vérification de la qualité des données What-If (Phase 1C/2D)
Vérifie le taux de remplissage des colonnes pnl_if_... et la cohérence des données.
"""
import os
import sys
import logging
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
# from tabulate import tabulate  # Removed to avoid dependency

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Logger setup
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_connection():
    try:
        from dotenv import load_dotenv
        load_dotenv()
        return psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
    except Exception as e:
        logger.error(f"Erreur connexion DB: {e}")
        return None

def check_whatif_coverage():
    conn = get_connection()
    if not conn:
        return

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Stats globales
        logger.info("📊 Vérification couverture What-If...")
        
        # Compter total trades dans la table principale
        cur.execute("SELECT COUNT(*) as cnt FROM trades")
        total_trades_real = cur.fetchone()['cnt']
        
        query_coverage = """
        SELECT 
            COUNT(*) as total_metrics,
            SUM(CASE WHEN pnl_if_no_be IS NOT NULL THEN 1 ELSE 0 END) as count_whatif_classic,
            SUM(CASE WHEN pnl_if_calme_params IS NOT NULL THEN 1 ELSE 0 END) as count_whatif_regime,
            SUM(CASE WHEN optimal_regime_retrospective IS NOT NULL THEN 1 ELSE 0 END) as count_optimal_regime
        FROM trade_atr_metrics
        """
        cur.execute(query_coverage)
        coverage = cur.fetchone()
        
        # 2. Stats récentes (24h)
        query_recent = """
        SELECT 
            COUNT(*) as total_recent,
            SUM(CASE WHEN tam.pnl_if_calme_params IS NOT NULL THEN 1 ELSE 0 END) as filled_recent
        FROM trades t
        LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
        WHERE t.timestamp_entry > NOW() - INTERVAL '24 hours'
        """
        cur.execute(query_recent)
        recent = cur.fetchone()

        # 3. Vérifier cohérence valeurs
        # Est-ce que pnl_if_calme_params est différent de pnl_if_volatile_params ? (Sinon simulation inutile)
        query_variance = """
        SELECT 
            AVG(CASE WHEN pnl_if_calme_params != pnl_if_volatile_params THEN 1.0 ELSE 0.0 END) as variance_rate
        FROM trade_atr_metrics
        WHERE pnl_if_calme_params IS NOT NULL
        """
        cur.execute(query_variance)
        variance = cur.fetchone()

        # Affichage
        print("\n=== RAPPORT QUALITÉ DONNÉES WHAT-IF ===")
        
        data = [
            ["Métrique", "Valeur"],
            ["-"*30, "-"*20],
            ["Total Trades (Table 'trades')", str(total_trades_real)],
            ["Total Trades (Table 'metrics')", str(coverage['total_metrics'])],
            ["Couverture Metrics", f"{coverage['total_metrics']/total_trades_real*100:.1f}%" if total_trades_real else "N/A"],
            ["What-If Classique (No BE/Trail)", f"{coverage['count_whatif_classic']} ({coverage['count_whatif_classic']/coverage['total_metrics']*100:.1f}%)" if coverage['total_metrics'] else "0"],
            ["What-If Régime (Calme/Volatile)", f"{coverage['count_whatif_regime']} ({coverage['count_whatif_regime']/coverage['total_metrics']*100:.1f}%)" if coverage['total_metrics'] else "0"],
            ["Optimal Régime Identifié", f"{coverage['count_optimal_regime']} ({coverage['count_optimal_regime']/coverage['total_metrics']*100:.1f}%)" if coverage['total_metrics'] else "0"],
            ["Remplissage Récent (24h)", f"{recent['filled_recent']}/{recent['total_recent']} ({recent['filled_recent']/recent['total_recent']*100:.1f}%)" if recent['total_recent'] else "N/A"],
            ["Taux de Variance (Simu utile)", f"{variance['variance_rate']*100:.1f}%" if variance['variance_rate'] else "N/A"]
        ]
        
        # Simple manual formatting
        for row in data:
            print(f"{str(row[0]):<35} | {str(row[1]):<20}")
        
        if recent['total_recent'] > 0 and recent['filled_recent'] < recent['total_recent']:
            print(f"\n❌ ALERTE: {recent['total_recent'] - recent['filled_recent']} trades récents n'ont pas de What-If !")
        elif coverage['count_whatif_regime'] < coverage['total_metrics'] * 0.9:
            print("\n⚠️ ATTENTION: Couverture incomplète des métriques existantes.")
        else:
            print("\n✅ Données What-If saines.")

    except Exception as e:
        logger.error(f"Erreur analyse: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_whatif_coverage()
