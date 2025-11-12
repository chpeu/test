<script>
	import { exportToCSV, exportToJSON, exportSummary, exportAnalytics, exportSetupAnalysis } from '$lib/utils/export';
	import { tradeHistory } from '$lib/stores/trades';
	import { stats } from '$lib/stores/stats';
	import { formatUSDT } from '$lib/utils/format';

	$: tradesCount = $tradeHistory?.length || 0;
	$: totalPnL = ($tradeHistory || []).reduce((sum, t) => sum + (t.net_pnl_usdt || 0), 0);
</script>

<div class="export-panel" data-debug-name="exportPanel">
	<div class="export-header" data-debug-name="exportHeader">
		<h2 data-debug-name="exportTitle">📥 Export Trades</h2>
		<div class="stats-preview" data-debug-name="statsPreview">
			<span class="stat" data-debug-name="tradesCount">{tradesCount} trades</span>
			<span class="stat" class:profit={totalPnL >= 0} class:loss={totalPnL < 0} data-debug-name="totalPnL">
				{totalPnL >= 0 ? '+' : ''}{formatUSDT(totalPnL)} USDT
			</span>
		</div>
	</div>

	<div class="export-options" data-debug-name="exportOptions">
		<!-- Excel Export -->
		<div class="export-option" data-debug-name="exportOption.excel">
			<div class="option-icon" data-debug-name="exportOption.excel.icon">📊</div>
			<div class="option-content" data-debug-name="exportOption.excel.content">
				<h3 data-debug-name="exportOption.excel.title">Excel Spreadsheet</h3>
				<p data-debug-name="exportOption.excel.description">Export all trades to Excel format (.xlsx) with proper formatting.</p>
				<ul class="feature-list" data-debug-name="exportOption.excel.features">
					<li>✅ All trade details</li>
					<li>✅ Formatted columns and cells</li>
					<li>✅ Easy to analyze</li>
				</ul>
				<button class="export-btn" on:click={exportToCSV} disabled={tradesCount === 0} data-debug-name="exportBtn.excel">
					📥 Export Excel
				</button>
			</div>
		</div>

		<!-- JSON Export -->
		<div class="export-option" data-debug-name="exportOption.json">
			<div class="option-icon" data-debug-name="exportOption.json.icon">📦</div>
			<div class="option-content" data-debug-name="exportOption.json.content">
				<h3 data-debug-name="exportOption.json.title">JSON Data</h3>
				<p data-debug-name="exportOption.json.description">Complete export including stats, trades, and metadata.</p>
				<ul class="feature-list" data-debug-name="exportOption.json.features">
					<li>✅ Full data structure</li>
					<li>✅ Includes statistics</li>
					<li>✅ Programmatic access</li>
				</ul>
				<button class="export-btn" on:click={exportToJSON} disabled={tradesCount === 0} data-debug-name="exportBtn.json">
					📥 Export JSON
				</button>
			</div>
		</div>

		<!-- Summary Report -->
		<div class="export-option" data-debug-name="exportOption.summary">
			<div class="option-icon" data-debug-name="exportOption.summary.icon">📝</div>
			<div class="option-content" data-debug-name="exportOption.summary.content">
				<h3 data-debug-name="exportOption.summary.title">Summary Report</h3>
				<p data-debug-name="exportOption.summary.description">Human-readable Markdown report with key statistics.</p>
				<ul class="feature-list" data-debug-name="exportOption.summary.features">
					<li>✅ Performance summary</li>
					<li>✅ Best/worst trades</li>
					<li>✅ Markdown format</li>
				</ul>
				<button class="export-btn" on:click={exportSummary} disabled={tradesCount === 0} data-debug-name="exportBtn.summary">
					📥 Export Report
				</button>
			</div>
		</div>

		<!-- Analytics Export -->
		<div class="export-option" data-debug-name="exportOption.analytics">
			<div class="option-icon" data-debug-name="exportOption.analytics.icon">📈</div>
			<div class="option-content" data-debug-name="exportOption.analytics.content">
				<h3 data-debug-name="exportOption.analytics.title">Performance Analytics</h3>
				<p data-debug-name="exportOption.analytics.description">Advanced analytics with symbol breakdown and time analysis.</p>
				<ul class="feature-list" data-debug-name="exportOption.analytics.features">
					<li>✅ Per-symbol stats</li>
					<li>✅ Hourly distribution</li>
					<li>✅ Daily PnL chart data</li>
				</ul>
				<button class="export-btn" on:click={exportAnalytics} disabled={tradesCount === 0} data-debug-name="exportBtn.analytics">
					📥 Export Analytics
				</button>
			</div>
		</div>

		<!-- Setup Analysis Export -->
		<div class="export-option" data-debug-name="exportOption.setupAnalysis">
			<div class="option-icon" data-debug-name="exportOption.setupAnalysis.icon">🔬</div>
			<div class="option-content" data-debug-name="exportOption.setupAnalysis.content">
				<h3 data-debug-name="exportOption.setupAnalysis.title">Analyse des Setups/Trade</h3>
				<p data-debug-name="exportOption.setupAnalysis.description">Complete analysis export with all trades, configuration parameters, and TP/SL settings.</p>
				<ul class="feature-list" data-debug-name="exportOption.setupAnalysis.features">
					<li>✅ All trades with details</li>
					<li>✅ Complete configuration</li>
					<li>✅ TP/SL parameters</li>
					<li>✅ Thresholds & patterns</li>
				</ul>
				<button class="export-btn" on:click={exportSetupAnalysis} disabled={tradesCount === 0} data-debug-name="exportBtn.setupAnalysis">
					📥 Export Analysis
				</button>
			</div>
		</div>
	</div>

	{#if tradesCount === 0}
		<div class="empty-state" data-debug-name="emptyState">
			<span class="empty-icon" data-debug-name="emptyIcon">📭</span>
			<p data-debug-name="emptyMessage">No trades available to export</p>
			<p class="hint" data-debug-name="emptyHint">Start trading to generate exportable data</p>
		</div>
	{/if}
</div>

<style>
	.export-panel {
		background: var(--bg-secondary);
		border-radius: 12px;
		padding: 24px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
	}

	.export-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 30px;
		padding-bottom: 16px;
		border-bottom: 2px solid var(--bg-tertiary);
	}

	.export-header h2 {
		font-size: 24px;
		color: var(--accent-green);
		margin: 0;
	}

	.stats-preview {
		display: flex;
		gap: 20px;
		font-size: 14px;
	}

	.stat {
		padding: 6px 12px;
		background: var(--bg-tertiary);
		border-radius: 6px;
		font-weight: 500;
	}

	.stat.profit {
		color: var(--accent-green);
		background: rgba(0, 255, 136, 0.1);
	}

	.stat.loss {
		color: var(--accent-red);
		background: rgba(255, 68, 68, 0.1);
	}

	.export-options {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
		gap: 20px;
	}

	.export-option {
		background: var(--bg-primary);
		border: 1px solid var(--bg-tertiary);
		border-radius: 10px;
		padding: 20px;
		transition: all 0.3s ease;
	}

	.export-option:hover {
		border-color: var(--accent-green);
		transform: translateY(-4px);
		box-shadow: 0 6px 16px rgba(0, 255, 136, 0.1);
	}

	.option-icon {
		font-size: 48px;
		margin-bottom: 16px;
		text-align: center;
	}

	.option-content h3 {
		font-size: 18px;
		color: var(--accent-blue);
		margin-bottom: 8px;
	}

	.option-content p {
		color: var(--text-secondary);
		font-size: 13px;
		margin-bottom: 12px;
		line-height: 1.5;
	}

	.feature-list {
		list-style: none;
		padding: 0;
		margin: 12px 0 16px 0;
	}

	.feature-list li {
		font-size: 12px;
		color: var(--text-secondary);
		padding: 4px 0;
	}

	.export-btn {
		width: 100%;
		background: var(--accent-green);
		color: var(--bg-primary);
		border: none;
		padding: 12px 20px;
		border-radius: 8px;
		font-size: 14px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s ease;
		font-family: 'Courier New', monospace;
	}

	.export-btn:hover:not(:disabled) {
		background: #00cc6a;
		transform: scale(1.02);
		box-shadow: 0 4px 12px rgba(0, 255, 136, 0.3);
	}

	.export-btn:active:not(:disabled) {
		transform: scale(0.98);
	}

	.export-btn:disabled {
		background: var(--bg-tertiary);
		color: var(--text-secondary);
		cursor: not-allowed;
		opacity: 0.5;
	}

	.empty-state {
		text-align: center;
		padding: 40px;
		color: var(--text-secondary);
	}

	.empty-icon {
		font-size: 64px;
		display: block;
		margin-bottom: 16px;
		opacity: 0.5;
	}

	.empty-state p {
		margin: 8px 0;
	}

	.empty-state .hint {
		font-size: 12px;
		font-style: italic;
	}

	@media (max-width: 768px) {
		.export-header {
			flex-direction: column;
			gap: 12px;
			align-items: flex-start;
		}

		.stats-preview {
			flex-direction: column;
			gap: 8px;
		}

		.export-options {
			grid-template-columns: 1fr;
		}
	}
</style>
