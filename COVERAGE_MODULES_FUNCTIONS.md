# Coverage Report (Modules / Functions)

Generated from `coverage.xml` on `2026-01-25 14:20:34`.

Total python modules in coverage: **118**

## Modules summary (worst coverage first)

| Module | Lines Covered | Lines Total | Coverage |
|---|---:|---:|---:|
| `implementations/testable_market_data_collector.py` | 0 | 337 | 0.00% |
| `implementations/testable_pair_filter.py` | 0 | 358 | 0.00% |
| `implementations/testable_scalability_scorer.py` | 0 | 310 | 0.00% |
| `implementations/testable_scan_pipeline.py` | 0 | 286 | 0.00% |
| `implementations/testable_scanner_orchestrator.py` | 0 | 129 | 0.00% |
| `monitoring/refactoring_dashboard.py` | 0 | 219 | 0.00% |
| `monitoring/scanner_phase3_dashboard.py` | 0 | 276 | 0.00% |
| `trading_circuit_breaker.py` | 0 | 213 | 0.00% |
| `bootstrap.py` | 13 | 360 | 3.61% |
| `routes/config.py` | 35 | 386 | 9.07% |
| `routes/websocket.py` | 22 | 181 | 12.15% |
| `routes/export.py` | 26 | 197 | 13.20% |
| `routes/position.py` | 31 | 211 | 14.69% |
| `regime_endpoints.py` | 25 | 168 | 14.88% |
| `routes/ml_config.py` | 31 | 184 | 16.85% |
| `routes/notifications.py` | 14 | 81 | 17.28% |
| `callbacks/post_exit_loop.py` | 14 | 74 | 18.92% |
| `implementations/testable_signal_validator.py` | 54 | 281 | 19.22% |
| `btc_indicator.py` | 30 | 140 | 21.43% |
| `routes/price.py` | 18 | 79 | 22.78% |
| `routes/ml_legacy.py` | 424 | 1821 | 23.28% |
| `routes/ml_dashboard.py` | 68 | 289 | 23.53% |
| `analysis/what_if_simulator.py` | 78 | 284 | 27.46% |
| `market_regime_selector.py` | 139 | 481 | 28.90% |
| `analysis/correlation_engine.py` | 59 | 197 | 29.95% |
| `analyzer.py` | 304 | 967 | 31.44% |
| `analyzer/advanced_filters.py` | 61 | 190 | 32.11% |
| `callbacks/position_check_loop.py` | 120 | 343 | 34.99% |
| `reliability.py` | 191 | 494 | 38.66% |
| `implementations/mock_position_components.py` | 117 | 292 | 40.07% |
| `routes/logs.py` | 16 | 38 | 42.11% |
| `callbacks/scanner_loop.py` | 315 | 746 | 42.23% |
| `pair_scorer.py` | 70 | 165 | 42.42% |
| `routes/ml_ev_analysis.py` | 7 | 16 | 43.75% |
| `position_manager.py` | 1043 | 2278 | 45.79% |
| `error_logger.py` | 30 | 63 | 47.62% |
| `live_trading_endpoints.py` | 220 | 453 | 48.57% |
| `routes/scanner.py` | 61 | 124 | 49.19% |
| `implementations/testable_position_manager.py` | 108 | 216 | 50.00% |
| `routes/dashboard.py` | 103 | 206 | 50.00% |
| `postgresql_datalogger.py` | 676 | 1326 | 50.98% |
| `implementations/testable_analyzer_v2.py` | 134 | 257 | 52.14% |
| `factories/position_manager_factory.py` | 86 | 162 | 53.09% |
| `config_manager.py` | 102 | 183 | 55.74% |
| `implementations/testable_analysis_orchestrator.py` | 179 | 321 | 55.76% |
| `implementations/testable_analyzer.py` | 157 | 280 | 56.07% |
| `implementations/testable_position_orchestrator.py` | 83 | 146 | 56.85% |
| `routes/ml_predictions.py` | 61 | 99 | 61.62% |
| `price_provider.py` | 218 | 350 | 62.29% |
| `error_handling.py` | 121 | 194 | 62.37% |
| `interfaces/analyzer_interface.py` | 86 | 133 | 64.66% |
| `state_manager.py` | 344 | 520 | 66.15% |
| `routes/__init__.py` | 57 | 86 | 66.28% |
| `factories/position_factory.py` | 318 | 479 | 66.39% |
| `analyzer/__init__.py` | 18 | 26 | 69.23% |
| `feature_flags.py` | 177 | 254 | 69.69% |
| `callbacks/__init__.py` | 7 | 10 | 70.00% |
| `routes/metrics.py` | 7 | 10 | 70.00% |
| `mexc.py` | 73 | 104 | 70.19% |
| `callbacks/scalability_refresh.py` | 104 | 147 | 70.75% |
| `implementations/testable_signal_generator.py` | 198 | 275 | 72.00% |
| `implementations/testable_score_calculator.py` | 212 | 294 | 72.11% |
| `routes/ml_common.py` | 36 | 49 | 73.47% |
| `implementations/testable_position_calculator.py` | 128 | 173 | 73.99% |
| `analyzer/market_data.py` | 96 | 129 | 74.42% |
| `analyzer/risk_detector.py` | 88 | 118 | 74.58% |
| `routes/ml_models.py` | 135 | 180 | 75.00% |
| `websocket_manager.py` | 136 | 181 | 75.14% |
| `post_exit/manager.py` | 196 | 260 | 75.38% |
| `analytics_database.py` | 163 | 216 | 75.46% |
| `implementations/testable_indicator_calculator.py` | 214 | 274 | 78.10% |
| `implementations/testable_position_validator.py` | 202 | 258 | 78.29% |
| `scanner.py` | 348 | 444 | 78.38% |
| `analyzer/trend_calculator.py` | 33 | 42 | 78.57% |
| `scheduler.py` | 81 | 102 | 79.41% |
| `implementations/mock_scanner_components.py` | 164 | 206 | 79.61% |
| `position/partial_tp_manager.py` | 47 | 58 | 81.03% |
| `shutdown.py` | 69 | 85 | 81.18% |
| `analyzer/signal_generator.py` | 127 | 156 | 81.41% |
| `analyzer/scoring.py` | 94 | 115 | 81.74% |
| `interfaces/scanner_interfaces.py` | 343 | 418 | 82.06% |
| `interfaces/position_manager_interface.py` | 66 | 80 | 82.50% |
| `routes/ml_tasks.py` | 29 | 35 | 82.86% |
| `ml/drift_detector.py` | 151 | 182 | 82.97% |
| `interfaces/position_interfaces.py` | 78 | 94 | 82.98% |
| `position/sl_services.py` | 84 | 99 | 84.85% |
| `indicators.py` | 180 | 210 | 85.71% |
| `post_exit/tracker.py` | 165 | 191 | 86.39% |
| `interfaces/analyzer_interfaces.py` | 203 | 233 | 87.12% |
| `routes/analytics.py` | 7 | 8 | 87.50% |
| `database.py` | 93 | 104 | 89.42% |
| `simple_pg_logger.py` | 160 | 175 | 91.43% |
| `ml/threshold_optimizer.py` | 176 | 192 | 91.67% |
| `position/adaptive_sizing.py` | 149 | 162 | 91.98% |
| `correlation_dynamic.py` | 49 | 53 | 92.45% |
| `__init__.py` | 17 | 18 | 94.44% |
| `analyzer/correlation.py` | 63 | 65 | 96.92% |
| `analyzer/filters.py` | 98 | 101 | 97.03% |
| `analysis/__init__.py` | 2 | 2 | 100.00% |
| `auth.py` | 49 | 49 | 100.00% |
| `exceptions.py` | 174 | 174 | 100.00% |
| `factories/__init__.py` | 0 | 0 | 100.00% |
| `implementations/__init__.py` | 0 | 0 | 100.00% |
| `interfaces/__init__.py` | 0 | 0 | 100.00% |
| `metrics.py` | 75 | 75 | 100.00% |
| `ml/__init__.py` | 3 | 3 | 100.00% |
| `monitoring/__init__.py` | 0 | 0 | 100.00% |
| `position/__init__.py` | 9 | 9 | 100.00% |
| `position/analytics_logger.py` | 50 | 50 | 100.00% |
| `position/early_invalidation.py` | 129 | 129 | 100.00% |
| `position/pnl_calculator.py` | 85 | 85 | 100.00% |
| `position/recovery_mode.py` | 76 | 76 | 100.00% |
| `position/tp_escalier_manager.py` | 54 | 54 | 100.00% |
| `position/tp_sl_calculator.py` | 150 | 150 | 100.00% |
| `position/trailing_stop.py` | 77 | 77 | 100.00% |
| `post_exit/__init__.py` | 3 | 3 | 100.00% |
| `routes/ml.py` | 24 | 24 | 100.00% |
| `routes/ml_calibration.py` | 108 | 108 | 100.00% |

## Functions by module

### `implementations/testable_market_data_collector.py` (0.00% - 0/337)

(No functions detected or source unavailable.)

### `implementations/testable_pair_filter.py` (0.00% - 0/358)

(No functions detected or source unavailable.)

### `implementations/testable_scalability_scorer.py` (0.00% - 0/310)

(No functions detected or source unavailable.)

### `implementations/testable_scan_pipeline.py` (0.00% - 0/286)

(No functions detected or source unavailable.)

### `implementations/testable_scanner_orchestrator.py` (0.00% - 0/129)

(No functions detected or source unavailable.)

### `monitoring/refactoring_dashboard.py` (0.00% - 0/219)

(No functions detected or source unavailable.)

### `monitoring/scanner_phase3_dashboard.py` (0.00% - 0/276)

(No functions detected or source unavailable.)

### `trading_circuit_breaker.py` (0.00% - 0/213)

(No functions detected or source unavailable.)

### `bootstrap.py` (3.61% - 13/360)

(No functions detected or source unavailable.)

### `routes/config.py` (9.07% - 35/386)

(No functions detected or source unavailable.)

### `routes/websocket.py` (12.15% - 22/181)

(No functions detected or source unavailable.)

### `routes/export.py` (13.20% - 26/197)

(No functions detected or source unavailable.)

### `routes/position.py` (14.69% - 31/211)

(No functions detected or source unavailable.)

### `regime_endpoints.py` (14.88% - 25/168)

(No functions detected or source unavailable.)

### `routes/ml_config.py` (16.85% - 31/184)

(No functions detected or source unavailable.)

### `routes/notifications.py` (17.28% - 14/81)

(No functions detected or source unavailable.)

### `callbacks/post_exit_loop.py` (18.92% - 14/74)

(No functions detected or source unavailable.)

### `implementations/testable_signal_validator.py` (19.22% - 54/281)

(No functions detected or source unavailable.)

### `btc_indicator.py` (21.43% - 30/140)

(No functions detected or source unavailable.)

### `routes/price.py` (22.78% - 18/79)

(No functions detected or source unavailable.)

### `routes/ml_legacy.py` (23.28% - 424/1821)

(No functions detected or source unavailable.)

### `routes/ml_dashboard.py` (23.53% - 68/289)

(No functions detected or source unavailable.)

### `analysis/what_if_simulator.py` (27.46% - 78/284)

(No functions detected or source unavailable.)

### `market_regime_selector.py` (28.90% - 139/481)

(No functions detected or source unavailable.)

### `analysis/correlation_engine.py` (29.95% - 59/197)

(No functions detected or source unavailable.)

### `analyzer.py` (31.44% - 304/967)

(No functions detected or source unavailable.)

### `analyzer/advanced_filters.py` (32.11% - 61/190)

(No functions detected or source unavailable.)

### `callbacks/position_check_loop.py` (34.99% - 120/343)

(No functions detected or source unavailable.)

### `reliability.py` (38.66% - 191/494)

(No functions detected or source unavailable.)

### `implementations/mock_position_components.py` (40.07% - 117/292)

(No functions detected or source unavailable.)

### `routes/logs.py` (42.11% - 16/38)

(No functions detected or source unavailable.)

### `callbacks/scanner_loop.py` (42.23% - 315/746)

(No functions detected or source unavailable.)

### `pair_scorer.py` (42.42% - 70/165)

(No functions detected or source unavailable.)

### `routes/ml_ev_analysis.py` (43.75% - 7/16)

(No functions detected or source unavailable.)

### `position_manager.py` (45.79% - 1043/2278)

(No functions detected or source unavailable.)

### `error_logger.py` (47.62% - 30/63)

(No functions detected or source unavailable.)

### `live_trading_endpoints.py` (48.57% - 220/453)

(No functions detected or source unavailable.)

### `routes/scanner.py` (49.19% - 61/124)

(No functions detected or source unavailable.)

### `implementations/testable_position_manager.py` (50.00% - 108/216)

(No functions detected or source unavailable.)

### `routes/dashboard.py` (50.00% - 103/206)

(No functions detected or source unavailable.)

### `postgresql_datalogger.py` (50.98% - 676/1326)

(No functions detected or source unavailable.)

### `implementations/testable_analyzer_v2.py` (52.14% - 134/257)

(No functions detected or source unavailable.)

### `factories/position_manager_factory.py` (53.09% - 86/162)

(No functions detected or source unavailable.)

### `config_manager.py` (55.74% - 102/183)

(No functions detected or source unavailable.)

### `implementations/testable_analysis_orchestrator.py` (55.76% - 179/321)

(No functions detected or source unavailable.)

### `implementations/testable_analyzer.py` (56.07% - 157/280)

(No functions detected or source unavailable.)

### `implementations/testable_position_orchestrator.py` (56.85% - 83/146)

(No functions detected or source unavailable.)

### `routes/ml_predictions.py` (61.62% - 61/99)

(No functions detected or source unavailable.)

### `price_provider.py` (62.29% - 218/350)

(No functions detected or source unavailable.)

### `error_handling.py` (62.37% - 121/194)

(No functions detected or source unavailable.)

### `interfaces/analyzer_interface.py` (64.66% - 86/133)

(No functions detected or source unavailable.)

### `state_manager.py` (66.15% - 344/520)

(No functions detected or source unavailable.)

### `routes/__init__.py` (66.28% - 57/86)

(No functions detected or source unavailable.)

### `factories/position_factory.py` (66.39% - 318/479)

(No functions detected or source unavailable.)

### `analyzer/__init__.py` (69.23% - 18/26)

(No functions detected or source unavailable.)

### `feature_flags.py` (69.69% - 177/254)

(No functions detected or source unavailable.)

### `callbacks/__init__.py` (70.00% - 7/10)

(No functions detected or source unavailable.)

### `routes/metrics.py` (70.00% - 7/10)

(No functions detected or source unavailable.)

### `mexc.py` (70.19% - 73/104)

(No functions detected or source unavailable.)

### `callbacks/scalability_refresh.py` (70.75% - 104/147)

(No functions detected or source unavailable.)

### `implementations/testable_signal_generator.py` (72.00% - 198/275)

(No functions detected or source unavailable.)

### `implementations/testable_score_calculator.py` (72.11% - 212/294)

(No functions detected or source unavailable.)

### `routes/ml_common.py` (73.47% - 36/49)

(No functions detected or source unavailable.)

### `implementations/testable_position_calculator.py` (73.99% - 128/173)

(No functions detected or source unavailable.)

### `analyzer/market_data.py` (74.42% - 96/129)

(No functions detected or source unavailable.)

### `analyzer/risk_detector.py` (74.58% - 88/118)

(No functions detected or source unavailable.)

### `routes/ml_models.py` (75.00% - 135/180)

(No functions detected or source unavailable.)

### `websocket_manager.py` (75.14% - 136/181)

(No functions detected or source unavailable.)

### `post_exit/manager.py` (75.38% - 196/260)

(No functions detected or source unavailable.)

### `analytics_database.py` (75.46% - 163/216)

(No functions detected or source unavailable.)

### `implementations/testable_indicator_calculator.py` (78.10% - 214/274)

(No functions detected or source unavailable.)

### `implementations/testable_position_validator.py` (78.29% - 202/258)

(No functions detected or source unavailable.)

### `scanner.py` (78.38% - 348/444)

(No functions detected or source unavailable.)

### `analyzer/trend_calculator.py` (78.57% - 33/42)

(No functions detected or source unavailable.)

### `scheduler.py` (79.41% - 81/102)

(No functions detected or source unavailable.)

### `implementations/mock_scanner_components.py` (79.61% - 164/206)

(No functions detected or source unavailable.)

### `position/partial_tp_manager.py` (81.03% - 47/58)

(No functions detected or source unavailable.)

### `shutdown.py` (81.18% - 69/85)

(No functions detected or source unavailable.)

### `analyzer/signal_generator.py` (81.41% - 127/156)

(No functions detected or source unavailable.)

### `analyzer/scoring.py` (81.74% - 94/115)

(No functions detected or source unavailable.)

### `interfaces/scanner_interfaces.py` (82.06% - 343/418)

(No functions detected or source unavailable.)

### `interfaces/position_manager_interface.py` (82.50% - 66/80)

(No functions detected or source unavailable.)

### `routes/ml_tasks.py` (82.86% - 29/35)

(No functions detected or source unavailable.)

### `ml/drift_detector.py` (82.97% - 151/182)

(No functions detected or source unavailable.)

### `interfaces/position_interfaces.py` (82.98% - 78/94)

(No functions detected or source unavailable.)

### `position/sl_services.py` (84.85% - 84/99)

(No functions detected or source unavailable.)

### `indicators.py` (85.71% - 180/210)

(No functions detected or source unavailable.)

### `post_exit/tracker.py` (86.39% - 165/191)

(No functions detected or source unavailable.)

### `interfaces/analyzer_interfaces.py` (87.12% - 203/233)

(No functions detected or source unavailable.)

### `routes/analytics.py` (87.50% - 7/8)

(No functions detected or source unavailable.)

### `database.py` (89.42% - 93/104)

(No functions detected or source unavailable.)

### `simple_pg_logger.py` (91.43% - 160/175)

(No functions detected or source unavailable.)

### `ml/threshold_optimizer.py` (91.67% - 176/192)

(No functions detected or source unavailable.)

### `position/adaptive_sizing.py` (91.98% - 149/162)

(No functions detected or source unavailable.)

### `correlation_dynamic.py` (92.45% - 49/53)

(No functions detected or source unavailable.)

### `__init__.py` (94.44% - 17/18)

(No functions detected or source unavailable.)

### `analyzer/correlation.py` (96.92% - 63/65)

(No functions detected or source unavailable.)

### `analyzer/filters.py` (97.03% - 98/101)

(No functions detected or source unavailable.)

### `analysis/__init__.py` (100.00% - 2/2)

(No functions detected or source unavailable.)

### `auth.py` (100.00% - 49/49)

(No functions detected or source unavailable.)

### `exceptions.py` (100.00% - 174/174)

(No functions detected or source unavailable.)

### `factories/__init__.py` (100.00% - 0/0)

(No functions detected or source unavailable.)

### `implementations/__init__.py` (100.00% - 0/0)

(No functions detected or source unavailable.)

### `interfaces/__init__.py` (100.00% - 0/0)

(No functions detected or source unavailable.)

### `metrics.py` (100.00% - 75/75)

(No functions detected or source unavailable.)

### `ml/__init__.py` (100.00% - 3/3)

(No functions detected or source unavailable.)

### `monitoring/__init__.py` (100.00% - 0/0)

(No functions detected or source unavailable.)

### `position/__init__.py` (100.00% - 9/9)

(No functions detected or source unavailable.)

### `position/analytics_logger.py` (100.00% - 50/50)

(No functions detected or source unavailable.)

### `position/early_invalidation.py` (100.00% - 129/129)

(No functions detected or source unavailable.)

### `position/pnl_calculator.py` (100.00% - 85/85)

(No functions detected or source unavailable.)

### `position/recovery_mode.py` (100.00% - 76/76)

(No functions detected or source unavailable.)

### `position/tp_escalier_manager.py` (100.00% - 54/54)

(No functions detected or source unavailable.)

### `position/tp_sl_calculator.py` (100.00% - 150/150)

(No functions detected or source unavailable.)

### `position/trailing_stop.py` (100.00% - 77/77)

(No functions detected or source unavailable.)

### `post_exit/__init__.py` (100.00% - 3/3)

(No functions detected or source unavailable.)

### `routes/ml.py` (100.00% - 24/24)

(No functions detected or source unavailable.)

### `routes/ml_calibration.py` (100.00% - 108/108)

(No functions detected or source unavailable.)

