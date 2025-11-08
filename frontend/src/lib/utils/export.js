import { get } from 'svelte/store';
import { trades } from '$lib/stores/trades';
import { stats } from '$lib/stores/stats';
import { format } from 'date-fns';

/**
 * Export trades to CSV format
 */
export function exportToCSV() {
	const allTrades = get(trades);

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

	// Convert trades to CSV rows
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
			(trade.pnl_usdt || 0).toFixed(2),
			(trade.pnl_percent || 0).toFixed(2),
			(trade.fees_usdt || 0).toFixed(4),
			(trade.net_pnl_usdt || 0).toFixed(2),
			duration,
			trade.exit_reason || '',
			trade.signals ? trade.signals.join(', ') : '',
			trade.score || 0
		].join(',');
	});

	// Combine headers and rows
	const csv = [headers.join(','), ...rows].join('\n');

	// Download
	downloadFile(csv, `trade-cursor-trades-${getDateStamp()}.csv`, 'text/csv');
}

/**
 * Export trades to JSON format
 */
export function exportToJSON() {
	const allTrades = get(trades);
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
	const allTrades = get(trades);
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
	const allTrades = get(trades);

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
