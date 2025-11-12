#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comptage précis de tous les paramètres"""

# Comptage manuel ligne par ligne du tuple params (lignes 915-1017)
# En comptant chaque paramètre séparément

params_count = 0

# Ligne 916: 5 paramètres
params_count += 5  # entry_timestamp, exit_timestamp, session_id, opportunity_id, scan_log_id

# Ligne 917-923: 7 paramètres
params_count += 7  # symbol, direction, entry_price, exit_price, size_usdt, tp_price, sl_price

# Ligne 924-931: 8 paramètres
params_count += 8  # gross_pnl_usdt, gross_pnl_pct, gross_pnl_usdt (pnl_usdt), net_pnl_usdt, net_pnl_pct, fees, slippage, slippage_usdt

# Ligne 932-933: 2 paramètres
params_count += 2  # reason, duration_seconds

# Ligne 934: 1 paramètre
params_count += 1  # tp_sl_mode

# Ligne 935-942: 8 paramètres
params_count += 8  # break_even_triggered, break_even_triggered_at, trailing_stop_triggered, trailing_stop_triggered_at, partial_tp_triggered, partial_tp_triggered_at, partial_tp_profit, partial_tp_percent

# Ligne 943-944: 2 paramètres
params_count += 2  # len(tp_escalier_levels_hit), tp_escalier_profits

# Ligne 946-951: 6 paramètres
params_count += 6  # early_invalidation_triggered, early_invalidation_triggered_at, early_invalidation_threshold, early_invalidation_elapsed, early_invalidation_atr_pct, early_invalidation_pnl_pct

# Ligne 953-954: 4 paramètres
params_count += 4  # rsi_1m, rsi_5m, rsi_prev_1m, rsi_prev_5m

# Ligne 956-959: 8 paramètres
params_count += 8  # macd_1m, macd_signal_1m, macd_hist_1m, macd_hist_prev_1m, macd_5m, macd_signal_5m, macd_hist_5m, macd_hist_prev_5m

# Ligne 961-963: 8 paramètres
params_count += 8  # adx_1m, adx_5m, di_plus_1m, di_minus_1m, di_gap_1m, di_plus_5m, di_minus_5m, di_gap_5m

# Ligne 965-966: 6 paramètres
params_count += 6  # ema9_1m, ema21_1m, ema_diff_pct_1m, ema9_5m, ema21_5m, ema_diff_pct_5m

# Ligne 968-969: 4 paramètres
params_count += 4  # atr_1m, atr_pct_1m, atr_5m, atr_pct_5m

# Ligne 971-974: 12 paramètres
params_count += 12  # bb_upper_1m, bb_middle_1m, bb_lower_1m, bb_width_1m, bb_distance_to_lower_1m, bb_distance_to_upper_1m, bb_upper_5m, bb_middle_5m, bb_lower_5m, bb_width_5m, bb_distance_to_lower_5m, bb_distance_to_upper_5m

# Ligne 976-979: 8 paramètres
params_count += 8  # volume_1m, volume_avg_1m, volume_ratio_1m, volume_spike_1m, volume_5m, volume_avg_5m, volume_ratio_5m, volume_spike_5m

# Ligne 981-985: 5 paramètres
params_count += 5  # score, spread_pct, balance_score, entry_conditions, len(entry_conditions)

# Ligne 987: 2 paramètres
params_count += 2  # entry_hour, entry_day

# Ligne 989-996: 13 paramètres (pas 12!)
params_count += 13  # exit_rsi_1m, exit_rsi_5m (2), exit_macd_hist_1m, exit_macd_hist_5m (2), exit_adx_1m, exit_adx_5m (2), exit_atr_pct_1m, exit_atr_pct_5m (2), exit_score (1), exit_volume_ratio_1m, exit_volume_ratio_5m (2), exit_spread_pct (1), exit_balance_score (1) = 13

# Ligne 997: 1 paramètre
params_count += 1  # entry_to_exit_price_change_pct

# Ligne 999: 2 paramètres
params_count += 2  # exit_hour, exit_day

# Ligne 1001-1002: 4 paramètres
params_count += 4  # max_favorable_excursion, max_adverse_excursion, max_favorable_excursion_usdt, max_adverse_excursion_usdt

# Ligne 1004-1005: 2 paramètres
params_count += 2  # risk_reward_ratio, profit_factor (None)

# Ligne 1007-1008: 4 paramètres
params_count += 4  # entry_to_max_profit_price_change_pct, entry_to_max_loss_price_change_pct, max_drawdown_pct, max_drawdown_usdt

# Ligne 1010-1013: 4 paramètres
params_count += 4  # entry_book_depth, entry_bid_vol, entry_ask_vol, entry_orderbook_imbalance

# Ligne 1015-1016: 2 paramètres
params_count += 2  # config_snapshot, win

total = params_count
print(f"Total paramètres comptés manuellement: {total}")
print(f"Placeholders attendus: 111")
print(f"Différence: {total - 111}")

# D'après les logs, il y a 128 paramètres
# Donc il y a 128 - 111 = 17 paramètres en trop
# Mais le comptage manuel donne {total}, donc il y a {128 - total} paramètres supplémentaires non comptés

