# CONFIGURATION OPTION 1 (Trailing moins agressif en mode ATR)
# À ajouter dans config.py

TRADING_CONFIG = {
    "tp_sl_mode": "ATR",  # Garder ATR
    
    # TP fixe comme filet de sécurité
    "tp_percent": 1.5,  # TP de secours si trailing ne se déclenche pas
    
    # SL plus raisonnable
    "atr_mult_sl": 1.2,  # Réduire de 1.6 à 1.2
    
    # Trailing beaucoup moins agressif
    "trailing_stop": {
        "atr_multiplier": 1.2,      # Distance = ATR × 1.2 (plus large)
        "min_distance": 0.15,       # Minimum 0.15%
        "max_distance": 0.50,       # Maximum 0.50%
    },
    "trailing_trigger_atr_mult": 2.0,  # Trigger plus tardif
    
    # Break-even plus tardif
    "break_even_atr_mult": 1.5,  # Au lieu de 1.2
}
