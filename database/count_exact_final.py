#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour compter exactement le nombre de colonnes dans INSERT,
le nombre de placeholders dans VALUES, et le nombre de paramètres dans params
"""

# Colonnes dans l'INSERT (lignes 668-734)
columns = [
    # Ligne 669
    "timestamp_entry", "timestamp_exit", "session_id", "opportunity_id", "scan_log_id", "symbol",
    # Ligne 670
    "direction", "entry_price", "exit_price",
    # Ligne 671
    "size_usdt", "tp_price", "sl_price", "gross_pnl_usdt", "pnl_pct", "pnl_usdt",
    # Ligne 672
    "net_pnl_usdt", "net_pnl_pct",
    # Ligne 673
    "fees_usdt", "slippage_pct", "slippage_usdt",
    # Ligne 674
    "exit_reason", "duration_seconds",
    # Ligne 675
    "tp_sl_mode", "break_even_set",
    # Ligne 676
    "break_even_triggered_at",
    # Ligne 677
    "trailing_stop_activated", "trailing_stop_triggered_at",
    # Ligne 678
    "partial_tp_executed", "partial_tp_triggered_at",
    # Ligne 679
    "partial_tp_profit", "partial_tp_percent",
    # Ligne 680
    "tp_escalier_levels_executed", "tp_escalier_profits",
    # Ligne 681
    "early_invalidation_triggered", "early_invalidation_triggered_at",
    # Ligne 682
    "early_invalidation_threshold", "early_invalidation_elapsed",
    # Ligne 683
    "early_invalidation_atr_pct", "early_invalidation_pnl_pct",
    # Ligne 685
    "entry_rsi_1m", "entry_rsi_5m", "entry_rsi_prev_1m", "entry_rsi_prev_5m",
    # Ligne 687
    "entry_macd_1m", "entry_macd_signal_1m", "entry_macd_hist_1m", "entry_macd_hist_prev_1m",
    "entry_macd_5m", "entry_macd_signal_5m", "entry_macd_hist_5m", "entry_macd_hist_prev_5m",
    # Ligne 690
    "entry_adx_1m", "entry_adx_5m",
    # Ligne 691
    "entry_di_plus_1m", "entry_di_minus_1m", "entry_di_gap_1m",
    # Ligne 692
    "entry_di_plus_5m", "entry_di_minus_5m", "entry_di_gap_5m",
    # Ligne 694
    "entry_ema9_1m", "entry_ema21_1m", "entry_ema_diff_pct_1m",
    # Ligne 695
    "entry_ema9_5m", "entry_ema21_5m", "entry_ema_diff_pct_5m",
    # Ligne 697
    "entry_atr_1m", "entry_atr_pct_1m", "entry_atr_5m", "entry_atr_pct_5m",
    # Ligne 699
    "entry_bb_upper_1m", "entry_bb_middle_1m", "entry_bb_lower_1m",
    # Ligne 700
    "entry_bb_width_1m", "entry_bb_distance_to_lower_1m", "entry_bb_distance_to_upper_1m",
    # Ligne 701
    "entry_bb_upper_5m", "entry_bb_middle_5m", "entry_bb_lower_5m",
    # Ligne 702
    "entry_bb_width_5m", "entry_bb_distance_to_lower_5m", "entry_bb_distance_to_upper_5m",
    # Ligne 704
    "entry_volume_1m", "entry_volume_avg_1m", "entry_volume_ratio_1m", "entry_volume_spike_1m",
    # Ligne 705
    "entry_volume_5m", "entry_volume_avg_5m", "entry_volume_ratio_5m", "entry_volume_spike_5m",
    # Ligne 707
    "entry_score", "entry_spread_pct", "entry_balance_score",
    # Ligne 708
    "entry_conditions", "entry_condition_count",
    # Ligne 710
    "entry_hour_of_day", "entry_day_of_week",
    # Ligne 712
    "exit_rsi_1m", "exit_rsi_5m",
    # Ligne 713
    "exit_macd_hist_1m", "exit_macd_hist_5m",
    # Ligne 714
    "exit_adx_1m", "exit_adx_5m",
    # Ligne 715
    "exit_atr_pct_1m", "exit_atr_pct_5m",
    # Ligne 716
    "exit_score", "exit_volume_ratio_1m", "exit_volume_ratio_5m",
    # Ligne 717
    "exit_spread_pct", "exit_balance_score",
    # Ligne 718
    "entry_to_exit_price_change_pct",
    # Ligne 720
    "exit_hour_of_day", "exit_day_of_week",
    # Ligne 722
    "max_favorable_excursion", "max_adverse_excursion",
    # Ligne 723
    "max_favorable_excursion_usdt", "max_adverse_excursion_usdt",
    # Ligne 725
    "risk_reward_ratio",
    # Ligne 726
    "profit_factor",
    # Ligne 728
    "entry_to_max_profit_price_change_pct", "entry_to_max_loss_price_change_pct",
    # Ligne 729
    "max_drawdown_pct", "max_drawdown_usdt",
    # Ligne 731
    "entry_book_depth", "entry_bid_vol", "entry_ask_vol", "entry_orderbook_imbalance",
    # Ligne 733
    "config_snapshot",
    # Ligne 734
    "win"
]

# Placeholders dans VALUES (lignes 736-758)
# Ligne 737: 10
# Ligne 738: 10
# Ligne 739: 8
# Ligne 740: 4
# Ligne 741: 8
# Ligne 742: 10
# Ligne 743: 4
# Ligne 744: 6
# Ligne 745: 6
# Ligne 746: 4
# Ligne 747: 8
# Ligne 748: 4
# Ligne 749: 2
# Ligne 750: 6
# Ligne 751: 6
# Ligne 752: 2
# Ligne 753: 4
# Ligne 754: 2
# Ligne 755: 4
# Ligne 756: 2
# Ligne 757: 17

placeholders_per_line = [10, 10, 8, 4, 8, 10, 4, 6, 6, 4, 8, 4, 2, 6, 6, 2, 4, 2, 4, 2, 17]

# Paramètres dans params (lignes 915-1017)
# On va compter en analysant le code

import sys
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print("COMPTAGE EXACT")
print("=" * 80)

print(f"\nNombre de colonnes dans INSERT: {len(columns)}")
print(f"Nombre de placeholders dans VALUES: {sum(placeholders_per_line)}")

print(f"\nListe des colonnes ({len(columns)}):")
for i, col in enumerate(columns, 1):
    print(f"  {i:3d}. {col}")

print(f"\nPlaceholders par ligne:")
for i, count in enumerate(placeholders_per_line, 737):
    print(f"  Ligne {i}: {count} placeholders")

print(f"\nTotal placeholders: {sum(placeholders_per_line)}")

# Maintenant, comptons les paramètres dans params
# D'après le code, on a:
# - Ligne 915-916: 5 paramètres (entry_timestamp, exit_timestamp, session_id, opportunity_id, scan_log_id)
# - Ligne 917-920: 4 paramètres (symbol, direction, entry_price, exit_price)
# - Ligne 921: 1 paramètre (size_usdt)
# - Ligne 922-923: 2 paramètres (tp_price, sl_price)
# - Ligne 924: 1 paramètre (gross_pnl_usdt)
# - Ligne 925: 1 paramètre (pnl_pct)
# - Ligne 926: 1 paramètre (pnl_usdt) - DOUBLON avec gross_pnl_usdt
# - Ligne 927-928: 2 paramètres (net_pnl_usdt, net_pnl_pct)
# - Ligne 929-931: 3 paramètres (fees, slippage, slippage_usdt)
# - Ligne 932-933: 2 paramètres (reason, duration_seconds)
# - Ligne 934: 1 paramètre (tp_sl_mode)
# - Ligne 935-936: 2 paramètres (break_even_triggered, break_even_triggered_at)
# - Ligne 937-938: 2 paramètres (trailing_stop_triggered, trailing_stop_triggered_at)
# - Ligne 939-940: 2 paramètres (partial_tp_triggered, partial_tp_triggered_at)
# - Ligne 941-942: 2 paramètres (partial_tp_profit, partial_tp_percent)
# - Ligne 943-944: 2 paramètres (tp_escalier_levels_executed, tp_escalier_profits)
# - Ligne 946-951: 6 paramètres (early_invalidation)
# - Ligne 953-954: 4 paramètres (entry_rsi)
# - Ligne 956-959: 8 paramètres (entry_macd)
# - Ligne 961-963: 9 paramètres (entry_adx)
# - Ligne 965-966: 6 paramètres (entry_ema)
# - Ligne 968-969: 4 paramètres (entry_atr)
# - Ligne 971-974: 12 paramètres (entry_bb)
# - Ligne 976-979: 8 paramètres (entry_volume)
# - Ligne 981-985: 5 paramètres (entry_score, spread, balance, conditions, condition_count)
# - Ligne 987: 2 paramètres (entry_hour, entry_day)
# - Ligne 989-996: 10 paramètres (exit_indicators)
# - Ligne 997: 1 paramètre (entry_to_exit_price_change_pct)
# - Ligne 999: 2 paramètres (exit_hour, exit_day)
# - Ligne 1001-1002: 4 paramètres (max_favorable_excursion, max_adverse_excursion)
# - Ligne 1004-1005: 2 paramètres (risk_reward_ratio, profit_factor)
# - Ligne 1007-1008: 4 paramètres (entry_to_max_profit, entry_to_max_loss, max_drawdown_pct, max_drawdown_usdt)
# - Ligne 1010-1013: 4 paramètres (scalability)
# - Ligne 1015: 1 paramètre (config_snapshot)
# - Ligne 1016: 1 paramètre (win)

params_count = (
    5 +  # entry_timestamp, exit_timestamp, session_id, opportunity_id, scan_log_id
    4 +  # symbol, direction, entry_price, exit_price
    1 +  # size_usdt
    2 +  # tp_price, sl_price
    1 +  # gross_pnl_usdt
    1 +  # pnl_pct
    1 +  # pnl_usdt (DOUBLON)
    2 +  # net_pnl_usdt, net_pnl_pct
    3 +  # fees, slippage, slippage_usdt
    2 +  # reason, duration_seconds
    1 +  # tp_sl_mode
    2 +  # break_even_triggered, break_even_triggered_at
    2 +  # trailing_stop_triggered, trailing_stop_triggered_at
    2 +  # partial_tp_triggered, partial_tp_triggered_at
    2 +  # partial_tp_profit, partial_tp_percent
    2 +  # tp_escalier_levels_executed, tp_escalier_profits
    6 +  # early_invalidation (6 paramètres)
    4 +  # entry_rsi (4 paramètres)
    8 +  # entry_macd (8 paramètres)
    9 +  # entry_adx (9 paramètres)
    6 +  # entry_ema (6 paramètres)
    4 +  # entry_atr (4 paramètres)
    12 +  # entry_bb (12 paramètres)
    8 +  # entry_volume (8 paramètres)
    5 +  # entry_score, spread, balance, conditions, condition_count
    2 +  # entry_hour, entry_day
    10 +  # exit_indicators (10 paramètres)
    1 +  # entry_to_exit_price_change_pct
    2 +  # exit_hour, exit_day
    4 +  # max_favorable_excursion, max_adverse_excursion (4 paramètres)
    2 +  # risk_reward_ratio, profit_factor
    4 +  # entry_to_max_profit, entry_to_max_loss, max_drawdown_pct, max_drawdown_usdt
    4 +  # scalability (4 paramètres)
    1 +  # config_snapshot
    1   # win
)

print(f"\nNombre de paramètres dans params (calculé): {params_count}")

print("\n" + "=" * 80)
print("DIFFÉRENCE")
print("=" * 80)
print(f"Colonnes: {len(columns)}")
print(f"Placeholders: {sum(placeholders_per_line)}")
print(f"Paramètres: {params_count}")
print(f"\nDifférence paramètres - placeholders: {params_count - sum(placeholders_per_line)}")
print(f"Différence paramètres - colonnes: {params_count - len(columns)}")
print(f"Différence colonnes - placeholders: {len(columns) - sum(placeholders_per_line)}")

