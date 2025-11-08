<script>
	import { exportToCSV, exportToJSON, exportSummary, exportAnalytics } from '$lib/utils/export';
	import { trades } from '$lib/stores/trades';
	import { stats } from '$lib/stores/stats';

	$: tradesCount = $trades?.length || 0;
	$: totalPnL = ($trades || []).reduce((sum, t) => sum + (t.net_pnl_usdt || 0), 0);
</script>

<div class="export-panel">
	<div class="export-header">
		<h2>📥 Export Trades</h2>
		<div class="stats-preview">
			<span class="stat">{tradesCount} trades</span>
			<span class="stat" class:profit={totalPnL >= 0} class:loss={totalPnL < 0}>
				{totalPnL >= 0 ? '+' : ''}{totalPnL.toFixed(2)} USDT
			</span>
		</div>
	</div>

	<div class="export-options">
		<!-- CSV Export -->
		<div class="export-option">
			<div class="option-icon">📊</div>
			<div class="option-content">
				<h3>CSV Spreadsheet</h3>
				<p>Export all trades to CSV format for Excel, Google Sheets, etc.</p>
				<ul class="feature-list">
					<li>✅ All trade details</li>
					<li>✅ Compatible with Excel</li>
					<li>✅ Easy to analyze</li>
				</ul>
				<button class="export-btn" on:click={exportToCSV} disabled={tradesCount === 0}>
					📥 Export CSV
				</button>
			</div>
		</div>

		<!-- JSON Export -->
		<div class="export-option">
			<div class="option-icon">📦</div>
			<div class="option-content">
				<h3>JSON Data</h3>
				<p>Complete export including stats, trades, and metadata.</p>
				<ul class="feature-list">
					<li>✅ Full data structure</li>
					<li>✅ Includes statistics</li>
					<li>✅ Programmatic access</li>
				</ul>
				<button class="export-btn" on:click={exportToJSON} disabled={tradesCount === 0}>
					📥 Export JSON
				</button>
			</div>
		</div>

		<!-- Summary Report -->
		<div class="export-option">
			<div class="option-icon">📝</div>
			<div class="option-content">
				<h3>Summary Report</h3>
				<p>Human-readable Markdown report with key statistics.</p>
				<ul class="feature-list">
					<li>✅ Performance summary</li>
					<li>✅ Best/worst trades</li>
					<li>✅ Markdown format</li>
				</ul>
				<button class="export-btn" on:click={exportSummary} disabled={tradesCount === 0}>
					📥 Export Report
				</button>
			</div>
		</div>

		<!-- Analytics Export -->
		<div class="export-option">
			<div class="option-icon">📈</div>
			<div class="option-content">
				<h3>Performance Analytics</h3>
				<p>Advanced analytics with symbol breakdown and time analysis.</p>
				<ul class="feature-list">
					<li>✅ Per-symbol stats</li>
					<li>✅ Hourly distribution</li>
					<li>✅ Daily PnL chart data</li>
				</ul>
				<button class="export-btn" on:click={exportAnalytics} disabled={tradesCount === 0}>
					📥 Export Analytics
				</button>
			</div>
		</div>
	</div>

	{#if tradesCount === 0}
		<div class="empty-state">
			<span class="empty-icon">📭</span>
			<p>No trades available to export</p>
			<p class="hint">Start trading to generate exportable data</p>
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
