#!/usr/bin/env python3
"""
Patch pour corriger le bug TRADING_CONFIG dans position_check_loop.py
"""

import os
import shutil

def patch_position_check_loop():
    """Applique le patch pour corriger le bug"""
    file_path = "core/callbacks/position_check_loop.py"
    
    # Backup
    backup_path = f"{file_path}.backup"
    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)
        print(f"✅ Backup créé: {backup_path}")
    
    # Lire le fichier
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Vérifier si le patch est déjà appliqué
    if "# PATCH_NEXT_EVENT" in content:
        print("✅ Patch déjà appliqué")
        return
    
    # Appliquer le patch
    patch_code = """
    # PATCH_NEXT_EVENT: Gestion du cas où TRADING_CONFIG n'est pas disponible
    try:
        trading_config_local = TRADING_CONFIG
    except NameError:
        # Fallback si TRADING_CONFIG non défini
        trading_config_local = {
            'break_even_use_atr': False,
            'trailing_stop': {},
            'trailing_use_atr_trigger': False,
            'break_even_atr_mult': 0.5,
            'trailing_trigger_atr_mult': 1.5,
            'trailing_distance_mult': 1.0,
            'break_even_trigger': 0.3,
            'trailing_trigger_pnl': 1.0,
            'trailing_distance': 0.1,
            'stagnation_exit_enabled': False,
            'stagnation_exit_timeout_seconds': None,
            'stagnation_positive_timeout_seconds': None,
            'stagnation_exit_min_pnl_to_stay': None,
            'stagnation_positive_threshold': None,
            'stagnation_mfe_pullback_pct': None
        }
        logger.warning("⚠️ TRADING_CONFIG non défini, utilisation des valeurs par défaut")
    
    # Utiliser trading_config_local au lieu de TRADING_CONFIG
    break_even_use_atr = trading_config_local.get('break_even_use_atr', False)
    trailing_config = trading_config_local.get('trailing_stop', {})
    trailing_use_atr_trigger = (
        trailing_config.get('use_atr_trigger', False)
        or trading_config_local.get('trailing_use_atr_trigger', False)
    )
    
    be_atr_mult_effective = effective_config.get('break_even_atr_mult') or trading_config_local.get('break_even_atr_mult', 0.5)
    trailing_trigger_atr_mult_effective = effective_config.get('trailing_trigger_atr_mult') or trading_config_local.get('trailing_trigger_atr_mult', 1.5)
    trailing_distance_mult_effective = (
        effective_config.get('trailing_distance_mult')
        or trading_config_local.get('trailing_distance_atr_mult')
        or trading_config_local.get('trailing_atr_multiplier')
        or trading_config_local.get('trailing_distance_mult')
        or 1.0
    )
    
    break_even_trigger_pct = None
    if break_even_use_atr and atr_percent is not None:
        break_even_trigger_pct = atr_percent * be_atr_mult_effective
    else:
        break_even_trigger_pct = trading_config_local.get('break_even_trigger', None)
    
    trailing_trigger_pct = None
    trailing_distance_pct = None
    if trailing_use_atr_trigger and atr_percent is not None:
        trailing_trigger_pct = atr_percent * trailing_trigger_atr_mult_effective
        trailing_distance_pct = atr_percent * trailing_distance_mult_effective
    else:
        trailing_trigger_pct = (
            trailing_config.get('trigger_pnl')
            or trading_config_local.get('trailing_trigger_pnl', None)
        )
        trailing_distance_pct = trading_config_local.get('trailing_distance', None)
    
    stagnation_config = trading_config_local.get('stagnation_exit', {})
    stagnation_enabled = trading_config_local.get('stagnation_exit_enabled', stagnation_config.get('enabled', False))
    stagnation_timeout = effective_config.get('stagnation_exit_timeout_seconds')
    if stagnation_timeout is None:
        stagnation_timeout = trading_config_local.get('stagnation_exit_timeout_seconds', stagnation_config.get('timeout_seconds', None))
    
    stagnation_positive_timeout = effective_config.get('stagnation_positive_timeout_seconds')
    if stagnation_positive_timeout is None:
        stagnation_positive_timeout = trading_config_local.get('stagnation_positive_timeout_seconds', None)
    
    stagnation_min_pnl_to_stay = effective_config.get('stagnation_exit_min_pnl_to_stay')
    if stagnation_min_pnl_to_stay is None:
        stagnation_min_pnl_to_stay = trading_config_local.get('stagnation_exit_min_pnl_to_stay', None)
    
    stagnation_positive_threshold = trading_config_local.get('stagnation_positive_threshold', None)
    stagnation_mfe_pullback_pct = trading_config_local.get('stagnation_mfe_pullback_pct', None)
"""
    
    # Remplacer la section problématique
    old_section = """    break_even_use_atr = TRADING_CONFIG.get('break_even_use_atr', False)
    trailing_config = TRADING_CONFIG.get('trailing_stop', {})
    trailing_use_atr_trigger = (
        trailing_config.get('use_atr_trigger', False)
        or TRADING_CONFIG.get('trailing_use_atr_trigger', False)
    )
    
    be_atr_mult_effective = effective_config.get('break_even_atr_mult') or TRADING_CONFIG.get('break_even_atr_mult', 0.5)
    trailing_trigger_atr_mult_effective = effective_config.get('trailing_trigger_atr_mult') or TRADING_CONFIG.get('trailing_trigger_atr_mult', 1.5)
    trailing_distance_mult_effective = (
        effective_config.get('trailing_distance_mult')
        or TRADING_CONFIG.get('trailing_distance_atr_mult')
        or TRADING_CONFIG.get('trailing_atr_multiplier')
        or TRADING_CONFIG.get('trailing_distance_mult')
        or 1.0
    )
    
    break_even_trigger_pct = None
    if break_even_use_atr and atr_percent is not None:
        break_even_trigger_pct = atr_percent * be_atr_mult_effective
    else:
        break_even_trigger_pct = TRADING_CONFIG.get('break_even_trigger', None)
    
    trailing_trigger_pct = None
    trailing_distance_pct = None
    if trailing_use_atr_trigger and atr_percent is not None:
        trailing_trigger_pct = atr_percent * trailing_trigger_atr_mult_effective
        trailing_distance_pct = atr_percent * trailing_distance_mult_effective
    else:
        trailing_trigger_pct = (
            trailing_config.get('trigger_pnl')
            or TRADING_CONFIG.get('trailing_trigger_pnl', None)
        )
        trailing_distance_pct = TRADING_CONFIG.get('trailing_distance', None)
    
    stagnation_config = TRADING_CONFIG.get('stagnation_exit', {})
    stagnation_enabled = TRADING_CONFIG.get('stagnation_exit_enabled', stagnation_config.get('enabled', False))
    stagnation_timeout = effective_config.get('stagnation_exit_timeout_seconds')
    if stagnation_timeout is None:
        stagnation_timeout = TRADING_CONFIG.get('stagnation_exit_timeout_seconds', stagnation_config.get('timeout_seconds', None))
    
    stagnation_positive_timeout = effective_config.get('stagnation_positive_timeout_seconds')
    if stagnation_positive_timeout is None:
        stagnation_positive_timeout = TRADING_CONFIG.get('stagnation_positive_timeout_seconds', None)
    
    stagnation_min_pnl_to_stay = effective_config.get('stagnation_exit_min_pnl_to_stay')
    if stagnation_min_pnl_to_stay is None:
        stagnation_min_pnl_to_stay = TRADING_CONFIG.get('stagnation_exit_min_pnl_to_stay', None)
    
    stagnation_positive_threshold = TRADING_CONFIG.get('stagnation_positive_threshold', None)
    stagnation_mfe_pullback_pct = TRADING_CONFIG.get('stagnation_mfe_pullback_pct', None)"""
    
    if old_section in content:
        content = content.replace(old_section, patch_code)
        
        # Écrire le fichier patché
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Patch appliqué avec succès!")
        print("   Le bot utilisera des valeurs par défaut si TRADING_CONFIG n'est pas défini")
    else:
        print("⚠️ Section à patcher non trouvée")

if __name__ == "__main__":
    os.chdir("c:\\Users\\sebta\\Documents\\clone github\\test\\test")
    patch_position_check_loop()
