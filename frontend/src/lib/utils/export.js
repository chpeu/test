import { get } from 'svelte/store';
import { tradeHistory } from '$lib/stores/trades';
import { stats } from '$lib/stores/stats';
import { format } from 'date-fns';
import * as XLSX from 'xlsx';

/**
 * Export trades to Excel format (xlsx)
 */
export function exportToCSV() {
	const allTrades = get(tradeHistory);

	if (!allTrades || allTrades.length === 0) {
		alert('⚠️ No trades to export');
		return;
	}

	// Headers
	const headers = [
		'Date',
		'Symbol',
		'Direction',
		'Entry Price',
		'Exit Price',
		'Size (USDT)',
		'PnL (USDT)',
		'PnL (%)',
		'Fees (USDT)',
		'Net PnL (USDT)',
		'Duration (min)',
		'Exit Reason',
		'Signals',
		'Score'
	];

	// Convert trades to rows
	const rows = allTrades.map(trade => {
		const date = trade.closed_at || trade.opened_at || new Date().toISOString();
		const duration = trade.duration_seconds
			? Math.round(trade.duration_seconds / 60)
			: 0;

		return [
			formatDate(date),
			trade.symbol || '',
			trade.direction || '',
			trade.entry || 0,
			trade.exit || 0,
			trade.size || 0,
			parseFloat((trade.pnl_usdt || 0).toFixed(2)),
			parseFloat((trade.pnl_percent || 0).toFixed(2)),
			parseFloat((trade.fees_usdt || 0).toFixed(4)),
			parseFloat((trade.net_pnl_usdt || 0).toFixed(2)),
			duration,
			trade.exit_reason || '',
			trade.signals ? trade.signals.join(', ') : '',
			trade.score || 0
		];
	});

	// Create workbook and worksheet
	const wb = XLSX.utils.book_new();
	const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);

	// Set column widths for better readability
	const colWidths = [
		{ wch: 18 }, // Date
		{ wch: 15 }, // Symbol
		{ wch: 10 }, // Direction
		{ wch: 12 }, // Entry Price
		{ wch: 12 }, // Exit Price
		{ wch: 12 }, // Size (USDT)
		{ wch: 12 }, // PnL (USDT)
		{ wch: 10 }, // PnL (%)
		{ wch: 12 }, // Fees (USDT)
		{ wch: 14 }, // Net PnL (USDT)
		{ wch: 14 }, // Duration (min)
		{ wch: 15 }, // Exit Reason
		{ wch: 30 }, // Signals
		{ wch: 8 }   // Score
	];
	ws['!cols'] = colWidths;

	// Style header row (bold)
	const headerRange = XLSX.utils.decode_range(ws['!ref'] || 'A1');
	for (let col = headerRange.s.c; col <= headerRange.e.c; col++) {
		const cellAddress = XLSX.utils.encode_cell({ r: 0, c: col });
		if (!ws[cellAddress]) continue;
		ws[cellAddress].s = {
			font: { bold: true },
			fill: { fgColor: { rgb: 'E0E0E0' } },
			alignment: { horizontal: 'center', vertical: 'center' }
		};
	}

	// Add worksheet to workbook
	XLSX.utils.book_append_sheet(wb, ws, 'Trades');

	// Write file
	const filename = `trade-cursor-trades-${getDateStamp()}.xlsx`;
	XLSX.writeFile(wb, filename);
	console.log(`✅ Exported: ${filename}`);
}

/**
 * Export trades to JSON format
 */
export function exportToJSON() {
	const allTrades = get(tradeHistory);
	const currentStats = get(stats);

	if (!allTrades || allTrades.length === 0) {
		alert('⚠️ No trades to export');
		return;
	}

	const exportData = {
		exported_at: new Date().toISOString(),
		version: '7.0.0',
		stats: currentStats,
		trades: allTrades,
		summary: {
			total_trades: allTrades.length,
			total_pnl: allTrades.reduce((sum, t) => sum + (t.net_pnl_usdt || 0), 0),
			wins: allTrades.filter(t => (t.net_pnl_usdt || 0) > 0).length,
			losses: allTrades.filter(t => (t.net_pnl_usdt || 0) <= 0).length
		}
	};

	const json = JSON.stringify(exportData, null, 2);

	downloadFile(json, `trade-cursor-export-${getDateStamp()}.json`, 'application/json');
}

/**
 * Export summary report (Markdown)
 */
export function exportSummary() {
	const allTrades = get(tradeHistory);
	const currentStats = get(stats);

	if (!allTrades || allTrades.length === 0) {
		alert('⚠️ No trades to export');
		return;
	}

	const totalPnL = allTrades.reduce((sum, t) => sum + (t.net_pnl_usdt || 0), 0);
	const wins = allTrades.filter(t => (t.net_pnl_usdt || 0) > 0);
	const losses = allTrades.filter(t => (t.net_pnl_usdt || 0) <= 0);
	const avgWin = wins.length > 0 ? wins.reduce((sum, t) => sum + t.net_pnl_usdt, 0) / wins.length : 0;
	const avgLoss = losses.length > 0 ? losses.reduce((sum, t) => sum + t.net_pnl_usdt, 0) / losses.length : 0;
	const bestTrade = allTrades.reduce((best, t) => (t.net_pnl_usdt > best.net_pnl_usdt ? t : best), allTrades[0]);
	const worstTrade = allTrades.reduce((worst, t) => (t.net_pnl_usdt < worst.net_pnl_usdt ? t : worst), allTrades[0]);

	const markdown = `# 📊 Trade Cursor v7.0 - Trading Report

**Generated:** ${formatDate(new Date().toISOString())}

---

## 📈 Summary

| Metric | Value |
|--------|-------|
| **Total Trades** | ${allTrades.length} |
| **Wins** | ${wins.length} (${((wins.length / allTrades.length) * 100).toFixed(1)}%) |
| **Losses** | ${losses.length} (${((losses.length / allTrades.length) * 100).toFixed(1)}%) |
| **Win Rate** | ${currentStats.winrate?.toFixed(1) || 0}% |
| **Total PnL** | ${totalPnL >= 0 ? '🟢' : '🔴'} ${totalPnL.toFixed(2)} USDT |
| **Avg Win** | +${avgWin.toFixed(2)} USDT |
| **Avg Loss** | ${avgLoss.toFixed(2)} USDT |
| **W/L Ratio** | ${(Math.abs(avgWin / avgLoss) || 0).toFixed(2)} |

---

## 🏆 Best & Worst Trades

### Best Trade
- **Symbol:** ${bestTrade.symbol}
- **Direction:** ${bestTrade.direction}
- **PnL:** +${bestTrade.net_pnl_usdt?.toFixed(2)} USDT (${bestTrade.pnl_percent?.toFixed(2)}%)
- **Date:** ${formatDate(bestTrade.closed_at)}

### Worst Trade
- **Symbol:** ${worstTrade.symbol}
- **Direction:** ${worstTrade.direction}
- **PnL:** ${worstTrade.net_pnl_usdt?.toFixed(2)} USDT (${worstTrade.pnl_percent?.toFixed(2)}%)
- **Date:** ${formatDate(worstTrade.closed_at)}

---

## 📋 Trade History

| Date | Symbol | Direction | Entry | Exit | PnL (USDT) | PnL (%) |
|------|--------|-----------|-------|------|------------|---------|
${allTrades
	.slice(0, 50)
	.map(
		t =>
			`| ${formatDate(t.closed_at)} | ${t.symbol} | ${t.direction} | ${t.entry} | ${t.exit} | ${(t.net_pnl_usdt || 0).toFixed(2)} | ${(t.pnl_percent || 0).toFixed(2)}% |`
	)
	.join('\n')}
${allTrades.length > 50 ? `\n*...and ${allTrades.length - 50} more trades*` : ''}

---

## 💡 Notes

- This report was generated automatically by Trade Cursor v7.0
- All timestamps are in UTC
- PnL includes trading fees
- For full trade data, export to JSON or CSV

---

**Trade smart, trade safe! 🚀**
`;

	downloadFile(markdown, `trade-cursor-report-${getDateStamp()}.md`, 'text/markdown');
}

/**
 * Export performance analytics (JSON)
 */
export function exportAnalytics() {
	const allTrades = get(tradeHistory);

	if (!allTrades || allTrades.length === 0) {
		alert('⚠️ No trades to export');
		return;
	}

	// Group trades by symbol
	const bySymbol = {};
	allTrades.forEach(trade => {
		if (!bySymbol[trade.symbol]) {
			bySymbol[trade.symbol] = [];
		}
		bySymbol[trade.symbol].push(trade);
	});

	// Calculate stats per symbol
	const symbolStats = Object.entries(bySymbol).map(([symbol, symbolTrades]) => {
		const wins = symbolTrades.filter(t => (t.net_pnl_usdt || 0) > 0).length;
		const totalPnL = symbolTrades.reduce((sum, t) => sum + (t.net_pnl_usdt || 0), 0);

		return {
			symbol,
			trades: symbolTrades.length,
			wins,
			losses: symbolTrades.length - wins,
			winrate: ((wins / symbolTrades.length) * 100).toFixed(1),
			total_pnl: totalPnL.toFixed(2),
			avg_pnl: (totalPnL / symbolTrades.length).toFixed(2)
		};
	});

	// Sort by total PnL
	symbolStats.sort((a, b) => parseFloat(b.total_pnl) - parseFloat(a.total_pnl));

	// Group trades by direction
	const longTrades = allTrades.filter(t => t.direction === 'LONG');
	const shortTrades = allTrades.filter(t => t.direction === 'SHORT');

	const analytics = {
		exported_at: new Date().toISOString(),
		overview: {
			total_trades: allTrades.length,
			long_trades: longTrades.length,
			short_trades: shortTrades.length,
			long_winrate: longTrades.length > 0
				? ((longTrades.filter(t => (t.net_pnl_usdt || 0) > 0).length / longTrades.length) * 100).toFixed(1)
				: 0,
			short_winrate: shortTrades.length > 0
				? ((shortTrades.filter(t => (t.net_pnl_usdt || 0) > 0).length / shortTrades.length) * 100).toFixed(1)
				: 0
		},
		by_symbol: symbolStats,
		hourly_distribution: getHourlyDistribution(allTrades),
		daily_pnl: getDailyPnL(allTrades)
	};

	const json = JSON.stringify(analytics, null, 2);

	downloadFile(json, `trade-cursor-analytics-${getDateStamp()}.json`, 'application/json');
}

// Helper functions

function formatDate(dateString) {
	try {
		return format(new Date(dateString), 'yyyy-MM-dd HH:mm');
	} catch {
		return dateString;
	}
}

function getDateStamp() {
	return format(new Date(), 'yyyy-MM-dd-HHmm');
}

function downloadFile(content, filename, mimeType) {
	const blob = new Blob([content], { type: mimeType });
	const url = URL.createObjectURL(blob);

	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);

	URL.revokeObjectURL(url);

	console.log(`✅ Exported: ${filename}`);
}

function getHourlyDistribution(allTrades) {
	const hours = new Array(24).fill(0);

	allTrades.forEach(trade => {
		const date = new Date(trade.opened_at || trade.closed_at);
		const hour = date.getUTCHours();
		hours[hour]++;
	});

	return hours.map((count, hour) => ({ hour, trades: count }));
}

function getDailyPnL(allTrades) {
	const dailyPnL = {};

	allTrades.forEach(trade => {
		const date = new Date(trade.closed_at || trade.opened_at);
		const day = format(date, 'yyyy-MM-dd');

		if (!dailyPnL[day]) {
			dailyPnL[day] = 0;
		}

		dailyPnL[day] += trade.net_pnl_usdt || 0;
	});

	return Object.entries(dailyPnL)
		.map(([date, pnl]) => ({ date, pnl: parseFloat(pnl.toFixed(2)) }))
		.sort((a, b) => new Date(a.date) - new Date(b.date));
}

/**
 * Export complete setup/trade analysis to Excel (xlsx)
 * Includes: all trades, complete configuration, TP/SL parameters
 */
export async function exportSetupAnalysis() {
	const allTrades = get(tradeHistory);

	if (!allTrades || allTrades.length === 0) {
		alert('⚠️ No trades to export');
		return;
	}

	try {
		// Fetch complete configuration from backend
		const configResponse = await fetch('/api/config/complete');
		if (!configResponse.ok) {
			throw new Error(`Failed to fetch configuration: ${configResponse.status}`);
		}
		const completeConfig = await configResponse.json();

		// Create workbook
		const wb = XLSX.utils.book_new();

		// ===== SHEET 1: TRADES =====
		const tradeHeaders = [
			'Date',
			'Symbol',
			'Direction',
			'Entry Price',
			'Exit Price',
			'Size (USDT)',
			'PnL (USDT)',
			'PnL (%)',
			'Net PnL (USDT)',
			'Net PnL (%)',
			'Fees (USDT)',
			'Slippage (%)',
			'Duration (min)',
			'Exit Reason',
			'Signals',
			'Score',
			'Break Even Triggered',
			'Trailing Stop Triggered',
			'Partial TP Triggered'
		];

		const tradeRows = allTrades.map(trade => {
			const date = trade.closed_at || trade.opened_at || new Date().toISOString();
			const duration = trade.duration_seconds
				? Math.round(trade.duration_seconds / 60)
				: 0;

			return [
				formatDate(date),
				trade.symbol || '',
				trade.direction || '',
				trade.entry || 0,
				trade.exit || 0,
				trade.size || 0,
				parseFloat((trade.pnl_usdt || 0).toFixed(4)),
				parseFloat((trade.pnl_pct || 0).toFixed(4)),
				parseFloat((trade.net_pnl_usdt || 0).toFixed(4)),
				parseFloat((trade.net_pnl_pct || 0).toFixed(4)),
				parseFloat((trade.fees_usdt || 0).toFixed(4)),
				parseFloat((trade.slippage_pct || trade.slippage || 0).toFixed(4)),
				duration,
				trade.exit_reason || '',
				trade.signals ? trade.signals.join(', ') : '',
				trade.score || 0,
				trade.break_even_triggered ? 'Yes' : 'No',
				trade.trailing_stop_triggered ? 'Yes' : 'No',
				trade.partial_tp_triggered ? 'Yes' : 'No'
			];
		});

		const tradesWs = XLSX.utils.aoa_to_sheet([tradeHeaders, ...tradeRows]);
		tradesWs['!cols'] = tradeHeaders.map(() => ({ wch: 15 }));
		XLSX.utils.book_append_sheet(wb, tradesWs, 'Trades');

		// ===== SHEET 2: TRADING CONFIGURATION =====
		const configHeaders = ['Parameter', 'Value', 'Category'];
		const configRows = [];

		// Flatten TRADING_CONFIG
		const tradingConfig = completeConfig.trading_config || {};
		Object.keys(tradingConfig).sort().forEach(key => {
			const value = tradingConfig[key];
			let displayValue = value;
			
			if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
				displayValue = JSON.stringify(value);
			} else if (Array.isArray(value)) {
				displayValue = value.join(', ');
			} else if (typeof value === 'boolean') {
				displayValue = value ? 'Yes' : 'No';
			}

			configRows.push([
				key,
				displayValue,
				'Trading Configuration'
			]);
		});

		const configWs = XLSX.utils.aoa_to_sheet([configHeaders, ...configRows]);
		configWs['!cols'] = [{ wch: 30 }, { wch: 30 }, { wch: 25 }];
		XLSX.utils.book_append_sheet(wb, configWs, 'Configuration');

		// ===== SHEET 3: TP/SL CONFIGURATION =====
		const tpslHeaders = ['Parameter', 'Value', 'Description'];
		const tpslRows = [
			['tp_sl_mode', tradingConfig.tp_sl_mode || 'FIXE', 'TP/SL Mode (FIXE, ATR, ESCALIER)'],
			['tp_percent', tradingConfig.tp_percent || 0, 'Take Profit Percentage (%)'],
			['sl_percent', tradingConfig.sl_percent || 0, 'Stop Loss Percentage (%)'],
			['partial_tp_percent', tradingConfig.partial_tp_percent || 0, 'Partial TP Percentage (%)'],
			['break_even_trigger', tradingConfig.break_even_trigger || 0, 'Break Even Trigger (%)'],
			['trailing_distance', tradingConfig.trailing_distance || 0, 'Trailing Distance (%)'],
			['trailing_enabled', tradingConfig.trailing_enabled ? 'Yes' : 'No', 'Trailing Stop Enabled'],
			['trailing_trigger_pnl', tradingConfig.trailing_trigger_pnl || 0, 'Trailing Trigger PnL (%)'],
			['trailing_atr_multiplier', tradingConfig.trailing_atr_multiplier || 0, 'Trailing ATR Multiplier'],
			['trailing_min_distance', tradingConfig.trailing_min_distance || 0, 'Trailing Min Distance (%)'],
			['trailing_max_distance', tradingConfig.trailing_max_distance || 0, 'Trailing Max Distance (%)'],
			['atr_mult_tp', tradingConfig.atr_mult_tp || 0, 'ATR Multiplier TP'],
			['atr_mult_sl', tradingConfig.atr_mult_sl || 0, 'ATR Multiplier SL'],
			['atr_min', tradingConfig.atr_min || 0, 'ATR Minimum (%)'],
			['atr_max', tradingConfig.atr_max || 0, 'ATR Maximum (%)'],
			['escalier_level1_pnl', tradingConfig.escalier_level1_pnl || 0, 'Escalier Level 1 PnL (%)'],
			['escalier_level1_size', tradingConfig.escalier_level1_size || 0, 'Escalier Level 1 Size (%)'],
			['escalier_level2_pnl', tradingConfig.escalier_level2_pnl || 0, 'Escalier Level 2 PnL (%)'],
			['escalier_level2_size', tradingConfig.escalier_level2_size || 0, 'Escalier Level 2 Size (%)'],
			['escalier_level3_pnl', tradingConfig.escalier_level3_pnl || 0, 'Escalier Level 3 PnL (%)'],
			['escalier_level3_size', tradingConfig.escalier_level3_size || 0, 'Escalier Level 3 Size (%)'],
			['escalier_level4_pnl', tradingConfig.escalier_level4_pnl || 0, 'Escalier Level 4 PnL (%)'],
			['escalier_level4_size', tradingConfig.escalier_level4_size || 0, 'Escalier Level 4 Size (%)']
		];

		const tpslWs = XLSX.utils.aoa_to_sheet([tpslHeaders, ...tpslRows]);
		tpslWs['!cols'] = [{ wch: 25 }, { wch: 15 }, { wch: 40 }];
		XLSX.utils.book_append_sheet(wb, tpslWs, 'TP-SL Configuration');

		// ===== SHEET 4: THRESHOLDS & FILTERS =====
		const thresholdHeaders = ['Parameter', 'Value', 'Description'];
		const thresholdRows = [
			['snr_threshold', tradingConfig.snr_threshold || 0, 'SNR Threshold'],
			['breakout_threshold', tradingConfig.breakout_threshold || 0, 'Breakout Threshold'],
			['wick_ratio_max', tradingConfig.wick_ratio_max || 0, 'Wick Ratio Maximum'],
			['di_gap_min', tradingConfig.di_gap_min || 0, 'DI Gap Minimum'],
			['di_gap_adx_threshold', tradingConfig.di_gap_adx_threshold || 0, 'DI Gap ADX Threshold'],
			['min_score_required', tradingConfig.min_score_required || 0, 'Minimum Score Required'],
			['optimal_atr_min_1m', tradingConfig.optimal_atr_min_1m || 0, 'Optimal ATR Min 1m (%)'],
			['optimal_atr_max_1m', tradingConfig.optimal_atr_max_1m || 0, 'Optimal ATR Max 1m (%)'],
			['optimal_atr_min_5m', tradingConfig.optimal_atr_min_5m || 0, 'Optimal ATR Min 5m (%)'],
			['optimal_atr_max_5m', tradingConfig.optimal_atr_max_5m || 0, 'Optimal ATR Max 5m (%)']
		];

		const thresholdWs = XLSX.utils.aoa_to_sheet([thresholdHeaders, ...thresholdRows]);
		thresholdWs['!cols'] = [{ wch: 25 }, { wch: 15 }, { wch: 40 }];
		XLSX.utils.book_append_sheet(wb, thresholdWs, 'Thresholds & Filters');

		// ===== SHEET 5: PATTERNS =====
		const patternHeaders = ['Pattern', 'Enabled', 'Category'];
		const patternRows = [
			['use_breakout', tradingConfig.use_breakout ? 'Yes' : 'No', 'Technical Pattern'],
			['use_snr', tradingConfig.use_snr ? 'Yes' : 'No', 'Technical Pattern'],
			['use_wick', tradingConfig.use_wick ? 'Yes' : 'No', 'Technical Pattern'],
			['use_divergence', tradingConfig.use_divergence ? 'Yes' : 'No', 'Technical Pattern'],
			['use_engulfing', tradingConfig.use_engulfing ? 'Yes' : 'No', 'Candlestick Pattern'],
			['use_hammer', tradingConfig.use_hammer ? 'Yes' : 'No', 'Candlestick Pattern'],
			['use_shooting_star', tradingConfig.use_shooting_star ? 'Yes' : 'No', 'Candlestick Pattern'],
			['use_doji', tradingConfig.use_doji ? 'Yes' : 'No', 'Candlestick Pattern'],
			['use_marubozu', tradingConfig.use_marubozu ? 'Yes' : 'No', 'Candlestick Pattern'],
			['use_morning_star', tradingConfig.use_morning_star ? 'Yes' : 'No', 'Candlestick Pattern'],
			['use_evening_star', tradingConfig.use_evening_star ? 'Yes' : 'No', 'Candlestick Pattern'],
			['use_confluence', tradingConfig.use_confluence ? 'Yes' : 'No', 'Validation']
		];

		const patternWs = XLSX.utils.aoa_to_sheet([patternHeaders, ...patternRows]);
		patternWs['!cols'] = [{ wch: 25 }, { wch: 10 }, { wch: 25 }];
		XLSX.utils.book_append_sheet(wb, patternWs, 'Patterns');

		// Style header rows
		[tradesWs, configWs, tpslWs, thresholdWs, patternWs].forEach(ws => {
			const headerRange = XLSX.utils.decode_range(ws['!ref'] || 'A1');
			for (let col = headerRange.s.c; col <= headerRange.e.c; col++) {
				const cellAddress = XLSX.utils.encode_cell({ r: 0, c: col });
				if (!ws[cellAddress]) continue;
				ws[cellAddress].s = {
					font: { bold: true },
					fill: { fgColor: { rgb: 'E0E0E0' } },
					alignment: { horizontal: 'center', vertical: 'center' }
				};
			}
		});

		// Write file
		const filename = `trade-cursor-setup-analysis-${getDateStamp()}.xlsx`;
		XLSX.writeFile(wb, filename);
		console.log(`✅ Exported setup analysis: ${filename}`);
	} catch (err) {
		console.error('❌ Error exporting setup analysis:', err);
		alert(`❌ Erreur lors de l'export: ${err.message || 'Impossible de charger la configuration'}`);
	}
}
