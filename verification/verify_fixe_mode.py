"""
Script de vérification du mode FIXE
Vérifie que les trades en mode FIXE se comportent correctement :
- Pas de fermeture par MFE_PROTECT ou STAGNATION_POSITIVE
- TP/SL basés sur pourcentages fixes
- Pas d'utilisation de l'ATR
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any


def get_recent_trades(limit: int = 4) -> List[Dict[str, Any]]:
    """Récupérer les derniers trades de la base de données SQLite locale"""
    db_path = ROOT_DIR / 'data' / 'analytics.db'
    
    if not db_path.exists():
        print(f"❌ Base de données SQLite introuvable: {db_path}")
        return []
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    try:
        query = """
            SELECT 
                id,
                symbol,
                direction,
                entry,
                exit,
                tp,
                sl,
                size_usdt,
                pnl_usdt,
                pnl_pct,
                exit_reason,
                tp_sl_mode,
                opened_at,
                closed_at,
                duration_seconds
            FROM trades
            WHERE closed_at IS NOT NULL
            ORDER BY closed_at DESC
            LIMIT ?
        """
        
        cursor = conn.cursor()
        rows = cursor.execute(query, (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_trade_atr_metrics(trade_id: int) -> Dict[str, Any]:
    """Récupérer les métriques depuis le champ config_snapshot du trade"""
    db_path = ROOT_DIR / 'data' / 'analytics.db'
    
    if not db_path.exists():
        return {}
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    try:
        # Récupérer le config_snapshot et exit_reason du trade
        query = """
            SELECT 
                exit_reason,
                config_snapshot
            FROM trades
            WHERE id = ?
        """
        
        cursor = conn.cursor()
        row = cursor.execute(query, (trade_id,)).fetchone()
        
        if not row:
            return {}
        
        result = {}
        exit_reason = row['exit_reason']
        
        # Détecter si c'est une sortie par stagnation positive
        if exit_reason and 'STAGNATION_POSITIVE' in exit_reason:
            result['stagnation_positive_triggered'] = True
        else:
            result['stagnation_positive_triggered'] = False
        
        # Parser le config_snapshot si disponible (format JSON)
        config_snapshot = row['config_snapshot']
        if config_snapshot:
            import json
            try:
                config = json.loads(config_snapshot)
                result['param_tp_pct_fixed'] = config.get('tp_percent')
                result['param_sl_pct_fixed'] = config.get('sl_percent')
                result['param_atr_mult_tp'] = config.get('atr_mult_tp')
                result['param_atr_mult_sl'] = config.get('atr_mult_sl')
            except:
                pass
        
        return result
    finally:
        conn.close()


def verify_fixe_trade(trade: Dict[str, Any], metrics: Dict[str, Any]) -> List[str]:
    """
    Vérifier qu'un trade en mode FIXE se comporte correctement
    
    Returns:
        Liste des erreurs trouvées (vide si tout est OK)
    """
    errors = []
    
    # 1. Vérifier le mode TP/SL
    tp_sl_mode = trade.get('tp_sl_mode')
    if tp_sl_mode != 'FIXE':
        errors.append(f"❌ Mode TP/SL incorrect: {tp_sl_mode} (attendu: FIXE)")
        return errors  # Si pas en mode FIXE, les autres vérifications ne sont pas pertinentes
    
    # 2. Vérifier que le trade ne s'est PAS fermé par MFE_PROTECT ou STAGNATION_POSITIVE
    exit_reason = trade.get('exit_reason', '')
    forbidden_exits = ['STAGNATION_MFE_PROTECT', 'STAGNATION_POSITIVE']
    if exit_reason in forbidden_exits:
        errors.append(
            f"❌ Sortie interdite en mode FIXE: {exit_reason} "
            f"(ce mécanisme ne devrait s'appliquer qu'en mode ATR)"
        )
    
    # 3. Vérifier que stagnation_positive_triggered est FALSE
    if metrics.get('stagnation_positive_triggered'):
        errors.append(
            f"❌ stagnation_positive_triggered=TRUE en mode FIXE "
            f"(ne devrait être activé qu'en mode ATR)"
        )
    
    # 4. Vérifier que les métriques MFE stagnation sont NULL (non utilisées en FIXE)
    if metrics.get('stagnation_mfe_at_exit') is not None:
        errors.append(
            f"⚠️ stagnation_mfe_at_exit renseigné en mode FIXE "
            f"(devrait être NULL car MFE protect non utilisé)"
        )
    
    # 5. Vérifier que les TP/SL sont basés sur des pourcentages fixes
    tp_pct_fixed = metrics.get('param_tp_pct_fixed')
    sl_pct_fixed = metrics.get('param_sl_pct_fixed')
    atr_mult_tp = metrics.get('param_atr_mult_tp')
    atr_mult_sl = metrics.get('param_atr_mult_sl')
    
    if tp_pct_fixed is None or sl_pct_fixed is None:
        errors.append(
            f"❌ Pourcentages fixes TP/SL manquants: "
            f"tp_pct_fixed={tp_pct_fixed}, sl_pct_fixed={sl_pct_fixed}"
        )
    
    # 6. Vérifier que les multiplicateurs ATR ne sont PAS utilisés
    if atr_mult_tp is not None or atr_mult_sl is not None:
        errors.append(
            f"⚠️ Multiplicateurs ATR renseignés en mode FIXE: "
            f"atr_mult_tp={atr_mult_tp}, atr_mult_sl={atr_mult_sl} "
            f"(devraient être NULL en mode FIXE)"
        )
    
    # 7. Calculer les TP/SL attendus et vérifier qu'ils correspondent
    if tp_pct_fixed is not None and sl_pct_fixed is not None:
        entry = trade.get('entry')
        tp_actual = trade.get('tp')
        sl_actual = trade.get('sl')
        direction = trade.get('direction')
        
        if entry and tp_actual and sl_actual:
            # Calculer TP/SL attendus en mode FIXE
            if direction == 'LONG':
                tp_expected = entry * (1 + tp_pct_fixed / 100)
                sl_expected = entry * (1 - sl_pct_fixed / 100)
            else:  # SHORT
                tp_expected = entry * (1 - tp_pct_fixed / 100)
                sl_expected = entry * (1 + sl_pct_fixed / 100)
            
            # Tolérance de 0.01% pour les arrondis
            tp_tolerance = abs(tp_actual - tp_expected) / entry * 100
            sl_tolerance = abs(sl_actual - sl_expected) / entry * 100
            
            if tp_tolerance > 0.01:
                errors.append(
                    f"⚠️ TP ne correspond pas au mode FIXE: "
                    f"attendu={tp_expected:.8f}, réel={tp_actual:.8f} "
                    f"(écart={tp_tolerance:.4f}%)"
                )
            
            if sl_tolerance > 0.01:
                errors.append(
                    f"⚠️ SL ne correspond pas au mode FIXE: "
                    f"attendu={sl_expected:.8f}, réel={sl_actual:.8f} "
                    f"(écart={sl_tolerance:.4f}%)"
                )
    
    return errors


def main():
    """Fonction principale"""
    print("=" * 80)
    print("VÉRIFICATION MODE FIXE - 4 DERNIERS TRADES")
    print("=" * 80)
    print()
    
    # Récupérer les derniers trades
    print("📊 Récupération des 4 derniers trades...")
    trades = get_recent_trades(limit=4)
    
    if not trades:
        print("❌ Aucun trade trouvé dans la base de données")
        return
    
    print(f"✅ {len(trades)} trades récupérés\n")
    
    # Vérifier chaque trade
    all_errors = []
    
    for i, trade in enumerate(trades, 1):
        trade_id = trade['id']
        symbol = trade['symbol']
        direction = trade['direction']
        tp_sl_mode = trade.get('tp_sl_mode', 'UNKNOWN')
        exit_reason = trade.get('exit_reason', 'UNKNOWN')
        closed_at = trade.get('closed_at')
        pnl_pct = trade.get('pnl_pct', 0)
        
        print(f"{'─' * 80}")
        print(f"Trade #{i} - ID {trade_id}")
        print(f"{'─' * 80}")
        print(f"  Symbole:      {symbol} {direction}")
        print(f"  Mode TP/SL:   {tp_sl_mode}")
        print(f"  Sortie:       {exit_reason}")
        print(f"  PnL:          {pnl_pct:.2f}%")
        print(f"  Fermé à:      {closed_at}")
        print()
        
        # Récupérer les métriques ATR
        metrics = get_trade_atr_metrics(trade_id)
        
        # Vérifier le trade
        errors = verify_fixe_trade(trade, metrics)
        
        if errors:
            print("  ⚠️ PROBLÈMES DÉTECTÉS:")
            for error in errors:
                print(f"    {error}")
            all_errors.extend(errors)
        else:
            if tp_sl_mode == 'FIXE':
                print("  ✅ Trade FIXE conforme - Aucun problème détecté")
            else:
                print(f"  ℹ️ Trade en mode {tp_sl_mode} (pas de vérification FIXE)")
        
        print()
    
    # Résumé final
    print("=" * 80)
    print("RÉSUMÉ DE LA VÉRIFICATION")
    print("=" * 80)
    
    fixe_trades = [t for t in trades if t.get('tp_sl_mode') == 'FIXE']
    
    if not fixe_trades:
        print("⚠️ Aucun trade en mode FIXE trouvé dans les 4 derniers trades")
    elif not all_errors:
        print(f"✅ TOUS LES TRADES FIXE SONT CONFORMES ({len(fixe_trades)}/{len(trades)} trades)")
        print("   - Pas de sortie par MFE_PROTECT ou STAGNATION_POSITIVE")
        print("   - TP/SL basés sur pourcentages fixes")
        print("   - Pas d'utilisation de l'ATR")
    else:
        print(f"❌ {len(all_errors)} ERREUR(S) DÉTECTÉE(S) sur {len(fixe_trades)} trade(s) FIXE")
        print("\nActions recommandées:")
        print("1. Vérifier que le backend a bien été redémarré après les corrections")
        print("2. Vérifier le paramètre tp_sl_mode dans la configuration")
        print("3. Analyser les logs pour comprendre pourquoi MFE_PROTECT s'est déclenché")
    
    print()


if __name__ == "__main__":
    main()
