#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comptage des colonnes dans INSERT"""

# Comptage ligne par ligne des colonnes dans INSERT (lignes 669-734)
columns = [
    6,   # Ligne 669: timestamp_entry, timestamp_exit, session_id, opportunity_id, scan_log_id, symbol
    3,   # Ligne 670: direction, entry_price, exit_price
    6,   # Ligne 671: size_usdt, tp_price, sl_price, gross_pnl_usdt, pnl_pct, pnl_usdt
    2,   # Ligne 672: net_pnl_usdt, net_pnl_pct
    3,   # Ligne 673: fees_usdt, slippage_pct, slippage_usdt
    2,   # Ligne 674: exit_reason, duration_seconds
    2,   # Ligne 675: tp_sl_mode, break_even_set
    1,   # Ligne 676: break_even_triggered_at
    2,   # Ligne 677: trailing_stop_activated, trailing_stop_triggered_at
    2,   # Ligne 678: partial_tp_executed, partial_tp_triggered_at
    2,   # Ligne 679: partial_tp_profit, partial_tp_percent
    2,   # Ligne 680: tp_escalier_levels_executed, tp_escalier_profits
    2,   # Ligne 681: early_invalidation_triggered, early_invalidation_triggered_at
    3,   # Ligne 682: early_invalidation_threshold, early_invalidation_elapsed, early_invalidation_atr_pct
    1,   # Ligne 683: early_invalidation_pnl_pct
    4,   # Ligne 685: entry_rsi_1m, entry_rsi_5m, entry_rsi_prev_1m, entry_rsi_prev_5m
    8,   # Ligne 687-688: entry_macd_1m, entry_macd_signal_1m, entry_macd_hist_1m, entry_macd_hist_prev_1m, entry_macd_5m, entry_macd_signal_5m, entry_macd_hist_5m, entry_macd_hist_prev_5m
    8,   # Ligne 690-692: entry_adx_1m, entry_adx_5m, entry_di_plus_1m, entry_di_minus_1m, entry_di_gap_1m, entry_di_plus_5m, entry_di_minus_5m, entry_di_gap_5m
    6,   # Ligne 694-695: entry_ema9_1m, entry_ema21_1m, entry_ema_diff_pct_1m, entry_ema9_5m, entry_ema21_5m, entry_ema_diff_pct_5m
    4,   # Ligne 697: entry_atr_1m, entry_atr_pct_1m, entry_atr_5m, entry_atr_pct_5m
    12,  # Ligne 699-702: entry_bb_upper_1m, entry_bb_middle_1m, entry_bb_lower_1m, entry_bb_width_1m, entry_bb_distance_to_lower_1m, entry_bb_distance_to_upper_1m, entry_bb_upper_5m, entry_bb_middle_5m, entry_bb_lower_5m, entry_bb_width_5m, entry_bb_distance_to_lower_5m, entry_bb_distance_to_upper_5m
    8,   # Ligne 704-705: entry_volume_1m, entry_volume_avg_1m, entry_volume_ratio_1m, entry_volume_spike_1m, entry_volume_5m, entry_volume_avg_5m, entry_volume_ratio_5m, entry_volume_spike_5m
    5,   # Ligne 707-708: entry_score, entry_spread_pct, entry_balance_score, entry_conditions, entry_condition_count
    2,   # Ligne 710: entry_hour_of_day, entry_day_of_week
    13,  # Ligne 712-717: exit_rsi_1m, exit_rsi_5m (2), exit_macd_hist_1m, exit_macd_hist_5m (2), exit_adx_1m, exit_adx_5m (2), exit_atr_pct_1m, exit_atr_pct_5m (2), exit_score (1), exit_volume_ratio_1m, exit_volume_ratio_5m (2), exit_spread_pct (1), exit_balance_score (1) = 13
    1,   # Ligne 718: entry_to_exit_price_change_pct
    2,   # Ligne 720: exit_hour_of_day, exit_day_of_week
    4,   # Ligne 722-723: max_favorable_excursion, max_adverse_excursion, max_favorable_excursion_usdt, max_adverse_excursion_usdt
    2,   # Ligne 725-726: risk_reward_ratio, profit_factor
    4,   # Ligne 728-729: entry_to_max_profit_price_change_pct, entry_to_max_loss_price_change_pct, max_drawdown_pct, max_drawdown_usdt
    4,   # Ligne 731: entry_book_depth, entry_bid_vol, entry_ask_vol, entry_orderbook_imbalance
    1,   # Ligne 733: config_snapshot
    1,   # Ligne 734: win
]

total = sum(columns)
print(f"Total colonnes dans INSERT: {total}")
print(f"Placeholders attendus: 111")
print(f"Différence: {total - 111}")

# Vérifier la ligne 712-717 (indicateurs de sortie)
print("\nVérification ligne 712-717 (indicateurs de sortie):")
print("exit_rsi_1m, exit_rsi_5m (2)")
print("exit_macd_hist_1m, exit_macd_hist_5m (2)")
print("exit_adx_1m, exit_adx_5m (2)")
print("exit_atr_pct_1m, exit_atr_pct_5m (2)")
print("exit_score (1)")
print("exit_volume_ratio_1m, exit_volume_ratio_5m (2)")
print("exit_spread_pct (1)")
print("exit_balance_score (1)")
print("Total: 2+2+2+2+1+2+1+1 = 13 colonnes")

