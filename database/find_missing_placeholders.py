#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identifier les colonnes dans INSERT qui n'ont pas de placeholder dans VALUES"""

# Liste complète des colonnes dans INSERT (dans l'ordre)
insert_cols_list = [
    # Ligne 669
    'timestamp_entry', 'timestamp_exit', 'session_id', 'opportunity_id', 'scan_log_id', 'symbol',
    # Ligne 670
    'direction', 'entry_price', 'exit_price',
    # Ligne 671
    'size_usdt', 'tp_price', 'sl_price', 'gross_pnl_usdt', 'pnl_pct', 'pnl_usdt',
    # Ligne 672
    'net_pnl_usdt', 'net_pnl_pct',
    # Ligne 673
    'fees_usdt', 'slippage_pct', 'slippage_usdt',
    # Ligne 674
    'exit_reason', 'duration_seconds',
    # Ligne 675
    'tp_sl_mode', 'break_even_set',
    # Ligne 676
    'break_even_triggered_at',
    # Ligne 677
    'trailing_stop_activated', 'trailing_stop_triggered_at',
    # Ligne 678
    'partial_tp_executed', 'partial_tp_triggered_at',
    # Ligne 679
    'partial_tp_profit', 'partial_tp_percent',
    # Ligne 680
    'tp_escalier_levels_executed', 'tp_escalier_profits',
    # Ligne 681
    'early_invalidation_triggered', 'early_invalidation_triggered_at',
    # Ligne 682
    'early_invalidation_threshold', 'early_invalidation_elapsed', 'early_invalidation_atr_pct',
    # Ligne 683
    'early_invalidation_pnl_pct',
    # Ligne 685
    'entry_rsi_1m', 'entry_rsi_5m', 'entry_rsi_prev_1m', 'entry_rsi_prev_5m',
    # Ligne 687-688
    'entry_macd_1m', 'entry_macd_signal_1m', 'entry_macd_hist_1m', 'entry_macd_hist_prev_1m',
    'entry_macd_5m', 'entry_macd_signal_5m', 'entry_macd_hist_5m', 'entry_macd_hist_prev_5m',
    # Ligne 690-692
    'entry_adx_1m', 'entry_adx_5m',
    'entry_di_plus_1m', 'entry_di_minus_1m', 'entry_di_gap_1m',
    'entry_di_plus_5m', 'entry_di_minus_5m', 'entry_di_gap_5m',
    # Ligne 694-695
    'entry_ema9_1m', 'entry_ema21_1m', 'entry_ema_diff_pct_1m',
    'entry_ema9_5m', 'entry_ema21_5m', 'entry_ema_diff_pct_5m',
    # Ligne 697
    'entry_atr_1m', 'entry_atr_pct_1m', 'entry_atr_5m', 'entry_atr_pct_5m',
    # Ligne 699-702
    'entry_bb_upper_1m', 'entry_bb_middle_1m', 'entry_bb_lower_1m',
    'entry_bb_width_1m', 'entry_bb_distance_to_lower_1m', 'entry_bb_distance_to_upper_1m',
    'entry_bb_upper_5m', 'entry_bb_middle_5m', 'entry_bb_lower_5m',
    'entry_bb_width_5m', 'entry_bb_distance_to_lower_5m', 'entry_bb_distance_to_upper_5m',
    # Ligne 704-705
    'entry_volume_1m', 'entry_volume_avg_1m', 'entry_volume_ratio_1m', 'entry_volume_spike_1m',
    'entry_volume_5m', 'entry_volume_avg_5m', 'entry_volume_ratio_5m', 'entry_volume_spike_5m',
    # Ligne 707-708
    'entry_score', 'entry_spread_pct', 'entry_balance_score',
    'entry_conditions', 'entry_condition_count',
    # Ligne 710
    'entry_hour_of_day', 'entry_day_of_week',
    # Ligne 712-717
    'exit_rsi_1m', 'exit_rsi_5m',
    'exit_macd_hist_1m', 'exit_macd_hist_5m',
    'exit_adx_1m', 'exit_adx_5m',
    'exit_atr_pct_1m', 'exit_atr_pct_5m',
    'exit_score', 'exit_volume_ratio_1m', 'exit_volume_ratio_5m',
    'exit_spread_pct', 'exit_balance_score',
    # Ligne 718
    'entry_to_exit_price_change_pct',
    # Ligne 720
    'exit_hour_of_day', 'exit_day_of_week',
    # Ligne 722-723
    'max_favorable_excursion', 'max_adverse_excursion',
    'max_favorable_excursion_usdt', 'max_adverse_excursion_usdt',
    # Ligne 725-726
    'risk_reward_ratio', 'profit_factor',
    # Ligne 728-729
    'entry_to_max_profit_price_change_pct', 'entry_to_max_loss_price_change_pct',
    'max_drawdown_pct', 'max_drawdown_usdt',
    # Ligne 731
    'entry_book_depth', 'entry_bid_vol', 'entry_ask_vol', 'entry_orderbook_imbalance',
    # Ligne 733
    'config_snapshot',
    # Ligne 734
    'win'
]

print(f"Total colonnes dans INSERT: {len(insert_cols_list)}")
print(f"Placeholders attendus: 111")
print(f"Différence: {len(insert_cols_list) - 111}")

# Afficher les 20 premières et dernières colonnes
print(f"\nPremières 20 colonnes:")
for i, col in enumerate(insert_cols_list[:20], 1):
    print(f"  {i}: {col}")

print(f"\nDernières 20 colonnes:")
for i, col in enumerate(insert_cols_list[-20:], len(insert_cols_list) - 19):
    print(f"  {i}: {col}")

