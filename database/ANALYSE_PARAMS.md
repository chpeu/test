# Analyse des paramètres - Déséquilibre 128 vs 111

## Problème
- **128 paramètres** dans le tuple `params`
- **111 placeholders** dans VALUES
- **17 paramètres en trop**

## D'après les logs
- Paramètre 13: `gross_pnl_usdt` (0.01)
- Paramètre 14: `pnl_pct` = `gross_pnl_pct` (0.07)
- Paramètre 15: `pnl_usdt` = `gross_pnl_usdt` (0.01) - **DOUBLON!**

## Colonnes dans INSERT (ordre)
1. timestamp_entry
2. timestamp_exit
3. session_id
4. opportunity_id
5. scan_log_id
6. symbol
7. direction
8. entry_price
9. exit_price
10. size_usdt
11. tp_price
12. sl_price
13. gross_pnl_usdt
14. pnl_pct
15. pnl_usdt
16. net_pnl_usdt
17. net_pnl_pct
18. fees_usdt
19. slippage_pct
20. slippage_usdt
21. exit_reason
22. duration_seconds
23. tp_sl_mode
24. break_even_set
25. break_even_triggered_at
26. trailing_stop_activated
27. trailing_stop_triggered_at
28. partial_tp_executed
29. partial_tp_triggered_at
30. partial_tp_profit
31. partial_tp_percent
32. tp_escalier_levels_executed
33. tp_escalier_profits
34. early_invalidation_triggered
35. early_invalidation_triggered_at
36. early_invalidation_threshold
37. early_invalidation_elapsed
38. early_invalidation_atr_pct
39. early_invalidation_pnl_pct
40-111. (indicateurs, métriques, etc.)

Total: **111 colonnes**

## Paramètres dans tuple params (ordre)
1-5. entry_timestamp, exit_timestamp, session_id, opportunity_id, scan_log_id
6. symbol
7. direction
8. entry_price
9. exit_price
10. size_usdt
11. tp_price
12. sl_price
13. gross_pnl_usdt
14. pnl_pct (gross_pnl_pct)
15. pnl_usdt (gross_pnl_usdt) - **DOUBLON!**
16-128. (autres paramètres)

## Solution
Le paramètre 15 est un doublon. Il faut le supprimer, mais il reste encore 16 paramètres en trop à identifier.

