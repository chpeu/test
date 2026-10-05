#!/usr/bin/env python3
"""
Debug PostExit Triggering - Vérifie pourquoi PostExit ne se déclenche plus
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

def main():
    print("🔍 DEBUG POST-EXIT TRIGGERING")
    print("=" * 60)
    
    try:
        # 1. Vérifier que les modules PostExit s'importent correctement
        print("\n📦 VÉRIFICATION IMPORTS")
        print("-" * 40)
        
        try:
            from core.post_exit import get_post_exit_manager
            print("✅ core.post_exit.manager importé")
        except Exception as e:
            print(f"❌ Erreur import post_exit.manager: {e}")
            return
            
        try:
            from core.callbacks.post_exit_loop import start_post_exit_loop, is_running
            print("✅ core.callbacks.post_exit_loop importé")
        except Exception as e:
            print(f"❌ Erreur import post_exit_loop: {e}")
            return
            
        # 2. Tester l'initialisation du PostExitManager
        print("\n🎛️ INITIALISATION POSTEXITMANAGER")
        print("-" * 40)
        
        try:
            manager = get_post_exit_manager()
            print(f"✅ PostExitManager instance créée: {manager}")
            
            # Status du manager
            status = manager.get_tracker_status()
            print(f"📊 Status manager:")
            print(f"   - Enabled: {status['enabled']}")
            print(f"   - Active trackers: {status['active_count']}")
            print(f"   - Completed trackers: {status['completed_count']}")
            print(f"   - Config: {status['config']}")
            
        except Exception as e:
            print(f"❌ Erreur initialisation PostExitManager: {e}")
            import traceback
            traceback.print_exc()
        
        # 3. Vérifier state de PostExitLoop
        print("\n🔄 ÉTAT POST-EXIT LOOP")
        print("-" * 40)
        
        try:
            is_loop_running = is_running()
            print(f"Loop running: {is_loop_running}")
            
            if not is_loop_running:
                print("⚠️ PostExitLoop n'est pas en cours d'exécution !")
                print("   Cela expliquerait pourquoi les prix ne sont pas collectés")
                
        except Exception as e:
            print(f"❌ Erreur vérification loop: {e}")
        
        # 4. Tester création tracker manuel
        print("\n🧪 TEST CRÉATION TRACKER")
        print("-" * 40)
        
        try:
            import uuid
            from datetime import datetime, timezone
            
            test_trade_id = str(uuid.uuid4())
            print(f"Test trade_id: {test_trade_id}")
            
            # Test start_tracking_sync (version thread-safe)
            manager.start_tracking_sync(
                trade_id=test_trade_id,
                symbol="TEST/USDT",
                direction="LONG",
                exit_price=100.0,
                exit_reason="TEST",
                realized_pnl_pct=0.5,
                realized_pnl_usdt=5.0,
                original_sl=99.0,
                original_tp=101.0,
                entry_price=99.5,
                trade_duration_sec=60
            )
            
            # Vérifier qu'il a été ajouté
            active_symbols = manager.get_active_symbols()
            if "TEST/USDT" in active_symbols:
                print("✅ Tracker de test créé avec succès")
                print(f"   Active symbols: {active_symbols}")
                
                # Nettoyer le test
                if hasattr(manager, 'active_trackers'):
                    if "TEST/USDT" in manager.active_trackers:
                        del manager.active_trackers["TEST/USDT"]
                        print("🧹 Tracker de test nettoyé")
            else:
                print("❌ Tracker de test non créé")
                
        except Exception as e:
            print(f"❌ Erreur test tracker: {e}")
            import traceback
            traceback.print_exc()
        
        # 5. Vérifier la dernière analyse en base pour comprendre quand ça a cessé
        print("\n📊 ANALYSE TEMPORELLE")
        print("-" * 40)
        
        try:
            import psycopg2
            from psycopg2.extras import DictCursor
            
            conn = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=os.getenv('POSTGRES_PORT', '5432'),
                database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                user=os.getenv('POSTGRES_USER', 'postgres'),
                password=os.getenv('POSTGRES_PASSWORD', '')
            )
            cursor = conn.cursor(cursor_factory=DictCursor)
            
            # Dernières analyses PostExit
            cursor.execute("""
                SELECT 
                    created_at,
                    symbol,
                    exit_efficiency_pct,
                    sample_count,
                    exit_timing_grade
                FROM trade_post_exit_analysis 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            
            recent_analyses = cursor.fetchall()
            if recent_analyses:
                print("📈 Dernières analyses PostExit:")
                for i, row in enumerate(recent_analyses, 1):
                    created_str = row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    print(f"  {i:2d}. {created_str} | {row['symbol']:<15} | Eff: {row['exit_efficiency_pct']:6.1f}% | Grade: {row['exit_timing_grade']} | Samples: {row['sample_count']}")
                
                # Calculer depuis quand pas de nouvelle analyse
                last_analysis = recent_analyses[0]['created_at']
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                time_since = now - last_analysis.replace(tzinfo=timezone.utc)
                
                hours_since = time_since.total_seconds() / 3600
                print(f"\n⏰ Dernière analyse: il y a {hours_since:.1f} heures")
                
                if hours_since > 24:
                    print("🔴 PROBLÈME: Aucune analyse PostExit depuis >24h")
                elif hours_since > 6:
                    print("🟡 ATTENTION: Aucune analyse PostExit depuis >6h") 
                else:
                    print("🟢 OK: Analyses PostExit récentes")
                    
            else:
                print("❌ Aucune analyse PostExit trouvée")
                
            # Vérifier aussi les trades récents pour voir s'il y a eu des fermetures
            cursor.execute("""
                SELECT 
                    timestamp_exit,
                    symbol,
                    direction,
                    exit_reason,
                    net_pnl_pct
                FROM trades 
                WHERE timestamp_exit > NOW() - INTERVAL '24 hours'
                ORDER BY timestamp_exit DESC 
                LIMIT 10
            """)
            
            recent_trades = cursor.fetchall()
            if recent_trades:
                print(f"\n📊 {len(recent_trades)} trades fermés (24h):")
                for i, row in enumerate(recent_trades, 1):
                    exit_str = row['timestamp_exit'].strftime('%Y-%m-%d %H:%M:%S')
                    print(f"  {i:2d}. {exit_str} | {row['symbol']:<15} | {row['direction']:<5} | {row['exit_reason']:<15} | PnL: {row['net_pnl_pct']:6.2f}%")
            else:
                print("\n📊 Aucun trade fermé dans les 24h")
                print("   → PostExit ne peut pas se déclencher sans fermeture de trade")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ Erreur analyse temporelle: {e}")
        
        # 6. Vérifier les logs d'erreur récents
        print("\n📝 VÉRIFICATION LOGS RÉCENTS")
        print("-" * 40)
        
        log_file = Path("logs/app.log")
        if log_file.exists():
            try:
                # Lire les dernières 50 lignes
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    recent_lines = lines[-50:] if len(lines) > 50 else lines
                    
                # Chercher les erreurs PostExit
                post_exit_errors = []
                for line in recent_lines:
                    if any(keyword in line.lower() for keyword in ['postexit', 'post_exit', 'post-exit']):
                        if any(error_keyword in line.lower() for error_keyword in ['error', 'erreur', 'exception', '❌']):
                            post_exit_errors.append(line.strip())
                
                if post_exit_errors:
                    print(f"🔴 {len(post_exit_errors)} erreurs PostExit trouvées:")
                    for error in post_exit_errors[-5:]:  # 5 plus récentes
                        print(f"   {error}")
                else:
                    print("🟢 Aucune erreur PostExit récente dans les logs")
                    
            except Exception as e:
                print(f"❌ Erreur lecture logs: {e}")
        else:
            print("⚠️ Fichier log non trouvé")
        
        print("\n" + "=" * 60)
        print("📋 DIAGNOSTIC")
        print("=" * 60)
        
        print("🔧 POINTS DE VÉRIFICATION POUR RÉSOUDRE:")
        print("1. Si PostExitLoop n'est pas running → Vérifier démarrage dans main.py")
        print("2. Si pas de trades récents → Problème en amont (pas de trading)")
        print("3. Si erreurs dans logs → Corriger les exceptions")
        print("4. Si tout semble OK → Vérifier price_provider dans loop")
        
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
