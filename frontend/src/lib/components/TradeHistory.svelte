<script>
	import { sortedTrades } from '$lib/stores/trades';
	import { derived } from 'svelte/store';

	import { formatAdaptive, formatPercent, formatUSDT, formatPrice, getSignificantDecimals } from '$lib/utils/format';

	// 🔥 PAGINATION: Variables de pagination
	let currentPage = 1;
	const tradesPerPage = 50;

	// Trades paginés
	const paginatedTrades = derived(sortedTrades, $trades => {
		const start = (currentPage - 1) * tradesPerPage;
		const end = start + tradesPerPage;
		return $trades.slice(start, end);
	});

	// Nombre total de pages
	const totalPages = derived(sortedTrades, $trades => {
		return Math.ceil($trades.length / tradesPerPage);
	});

	// Navigation pagination
	function nextPage() {
		if (currentPage < $totalPages) {
			currentPage++;
		}
	}

	function prevPage() {
		if (currentPage > 1) {
			currentPage--;
		}
	}

	function goToPage(page) {
		if (page >= 1 && page <= $totalPages) {
			currentPage = page;
		}
	}

	// Reset page quand les trades changent
	$: if ($sortedTrades.length > 0 && currentPage > $totalPages) {
		currentPage = 1;
	}

	// 🔥 FIX: Somme simple des colonnes (frais/slippage DÉJÀ déduits dans net_pnl_*)
	const sessionPnL = derived(sortedTrades, $trades => {
		if ($trades.length === 0) return 0;
		return $trades.reduce((sum, trade) => sum + (trade.net_pnl_usdt || 0), 0);
	});

	const sessionPnLPct = derived(sortedTrades, $trades => {
		if ($trades.length === 0) return 0;
		return $trades.reduce((sum, trade) => sum + (trade.net_pnl_pct || 0), 0);
	});

	function formatTime(dateStr) {
		if (!dateStr) return '';
		const date = new Date(dateStr);
		return date.toLocaleTimeString('fr-FR', {
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit',
			hour12: false
		});
	}

	function formatDuration(openedAt, closedAt) {
		if (!openedAt || !closedAt) return 'N/A';
		const diff = new Date(closedAt) - new Date(openedAt);
		const seconds = Math.floor(diff / 1000);
		const minutes = Math.floor(seconds / 60);
		const hours = Math.floor(minutes / 60);

		if (hours > 0) return `${hours}h ${minutes % 60}m`;
		if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
		return `${seconds}s`;
	}

	// 🔥 FIX: Formater la durée depuis des secondes (format backend)
	function formatDurationFromSeconds(seconds) {
		if (!seconds || seconds <= 0) return 'N/A';
		const minutes = Math.floor(seconds / 60);
		const hours = Math.floor(minutes / 60);

		if (hours > 0) return `${hours}h ${minutes % 60}m`;
		if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
		return `${seconds}s`;
	}
</script>

<div class="trade-history" data-debug-name="tradeHistory">
	<div class="history-header" data-debug-name="tradeHistory.header">
		<h3 data-debug-name="tradeHistory.title">📜 Historique des Trades</h3>
		<div class="header-stats" data-debug-name="tradeHistory.stats">
			<div class="total-count" data-debug-name="sortedTrades.length">{$sortedTrades.length} trades</div>
			{#if $sortedTrades.length > 0}
				<div class="session-pnl" class:positive={$sessionPnL >= 0} class:negative={$sessionPnL < 0} data-debug-name="sessionPnL">
					PnL Session: {formatUSDT($sessionPnL)} USDT ({formatPercent($sessionPnLPct)}%)
				</div>
			{/if}
		</div>
	</div>

	{#if $sortedTrades.length === 0}
		<div class="no-trades">
			<div class="no-trades-icon">📊</div>
			<div class="no-trades-text">Aucun trade pour le moment</div>
		</div>
	{:else}
		<div class="table-container">
			<table class="trades-table">
				<thead>
					<tr>
						<th data-debug-name="tradeHistory.column.index">#</th>
						<th data-debug-name="tradeHistory.column.time">Heure</th>
						<th data-debug-name="tradeHistory.column.symbol">Paire</th>
						<th data-debug-name="tradeHistory.column.direction">Dir</th>
						<th data-debug-name="tradeHistory.column.reason">Raison</th>
						<th data-debug-name="tradeHistory.column.entryPrice">Prix Entrée</th>
						<th data-debug-name="tradeHistory.column.exitPrice">Prix Sortie</th>
						<th data-debug-name="tradeHistory.column.pnlGross">PnL Brut %</th>
						<th data-debug-name="tradeHistory.column.slippage">Slippage</th>
						<th data-debug-name="tradeHistory.column.pnlNet">PnL Net %</th>
						<th data-debug-name="tradeHistory.column.pnlUsdt" title="PnL réel depuis API MEXC">PnL Total USDT</th>
						<th data-debug-name="tradeHistory.column.duration">Duration</th>
					</tr>
				</thead>
				<tbody>
					{#each $paginatedTrades as trade, index (trade.id || `${trade.symbol}_${trade.closed_at || trade.opened_at || trade.timestamp}_${index}`)}
						{@const globalIndex = (currentPage - 1) * tradesPerPage + index}
						<tr class:win={trade.net_pnl_usdt >= 0} class:loss={trade.net_pnl_usdt < 0} data-debug-name="trade[{globalIndex}]">
							<td class="index" data-debug-name="trade.index">{globalIndex + 1}</td>
							<td class="time" data-debug-name="trade.closed_at">{formatTime(trade.closed_at || trade.timestamp)}</td>
							<td class="symbol" data-debug-name="trade.symbol" title="Taille: {trade.filled_size_usdt ? trade.filled_size_usdt.toFixed(2) : (trade.size || 'N/A')} USDT">{trade.symbol}</td>
							<td class="direction" data-debug-name="trade.direction">
								<span class:long={trade.direction === 'LONG'} class:short={trade.direction === 'SHORT'} data-debug-name="trade.direction">
									{trade.direction}
								</span>
							</td>
							<td class="reason" data-debug-name="trade.reason">
								{#if trade.reason === 'MANUAL'}
									<span class="reason-manual" data-debug-name="trade.reason">👤 Manuel</span>
								{:else}
									{(() => {
										const reason = trade.reason || trade.close_reason || 'N/A';
										const pnl = trade.net_pnl_usdt || 0;
										
										// Clarifier les cas ambigus
										if (reason === 'TP' && pnl < 0) return 'TP (Slippage)';
										if (reason === 'SL' && pnl > 0) return 'SL (Profit)';
										
										return reason;
									})()}
								{/if}
							</td>
							<td class="entry-price" data-debug-name="trade.entry_price">
								{(() => {
									const entryPrice = trade.entry_price || trade.entry;
									return entryPrice ? formatPrice(entryPrice) : 'N/A';
								})()}
							</td>
							<td class="exit-price" data-debug-name="trade.exit_price">
								{(() => {
									const exitPrice = trade.exit_price || trade.close_price || trade.filled_exit_price || trade.exit;
									const entryPrice = trade.entry_price || trade.entry;
									
									// Si pas de prix de sortie ou prix suspect (0 ou 1 pour un actif > 10)
									if (!exitPrice || (exitPrice <= 1 && entryPrice > 10)) {
										// Essayer de reconstruire depuis PnL si possible
										if (entryPrice && trade.pnl_pct) {
											const pnlMult = 1 + (trade.pnl_pct / 100 * (trade.direction === 'SHORT' ? -1 : 1));
											const estPrice = entryPrice * pnlMult;
											const decimals = getSignificantDecimals(entryPrice);
											return `≈${formatPrice(estPrice, decimals)}`;
										}
										return exitPrice ? formatPrice(exitPrice) : 'N/A';
									}
									
									// Utiliser le nombre de décimales du prix d'entrée
									const decimals = entryPrice ? getSignificantDecimals(entryPrice) : null;
									return formatPrice(exitPrice, decimals);
								})()}
							</td>
							<td class="pnl-gross" class:positive={(trade.gross_pnl_pct || trade.pnl_pct || 0) >= 0} class:negative={(trade.gross_pnl_pct || trade.pnl_pct || 0) < 0} data-debug-name="trade.gross_pnl_pct">
								{(trade.gross_pnl_pct || trade.pnl_pct || 0) >= 0 ? '+' : ''}{formatPercent(trade.gross_pnl_pct || trade.pnl_pct || 0)}%
							</td>
							<td class="slippage" data-debug-name="trade.slippage">
								{(() => {
									// Essayer slippage_pct d'abord (en pourcentage)
									let slippageValue = trade.slippage_pct;
									// Sinon essayer slippage (peut être en % ou en décimales)
									if (slippageValue === undefined || slippageValue === null) {
										slippageValue = trade.slippage;
										// Si slippage est < 1, c'est probablement en décimales (0.001 = 0.1%), multiplier par 100
										if (slippageValue !== undefined && slippageValue !== null && Math.abs(slippageValue) < 1 && slippageValue !== 0) {
											slippageValue = slippageValue * 100;
										}
									}
									// Sinon calculer depuis slippage_usdt si disponible
									if ((slippageValue === undefined || slippageValue === null || slippageValue === 0) && trade.slippage_usdt && trade.size) {
										slippageValue = (trade.slippage_usdt / trade.size) * 100;
									}
									// Valeur par défaut
									if (slippageValue === undefined || slippageValue === null) {
										slippageValue = 0;
									}
									// 🔥 FIX: Forcer 3 décimales pour slippage
									return (slippageValue || 0).toFixed(3);
								})()}%
							</td>
							<!-- PnL Net % (frais/slippage DÉJÀ déduits) -->
							<td class="pnl-net" class:positive={(trade.net_pnl_pct || 0) >= 0} class:negative={(trade.net_pnl_pct || 0) < 0} data-debug-name="trade.net_pnl_pct">
								{(trade.net_pnl_pct || 0) >= 0 ? '+' : ''}{formatPercent(trade.net_pnl_pct || 0)}%
							</td>
							<!-- 🔥 FIX: PnL Total USDT = PnL réel depuis API MEXC -->
							<td class="pnl-usdt" class:positive={(trade.net_pnl_usdt || 0) >= 0} class:negative={(trade.net_pnl_usdt || 0) < 0} data-debug-name="trade.net_pnl_usdt" title="PnL réel depuis API MEXC (frais 0% sur paires scannées)">
								{(trade.net_pnl_usdt || 0) >= 0 ? '+' : ''}{(trade.net_pnl_usdt || 0).toFixed(3)} USDT
							</td>
							<!-- 🔥 FIX: Supprimé PnL Total USDT car redondant et calcul incorrect -->
							
							<!-- 🔥 FIX: Duration (calculée si manquante) -->
							<td class="duration" data-debug-name="trade.duration">
								{(() => {
									// Priorité 1: duration_seconds (format backend)
									if (trade.duration_seconds !== undefined && trade.duration_seconds !== null && trade.duration_seconds !== '') {
										return formatDurationFromSeconds(Number(trade.duration_seconds));
									}
									// Priorité 2: duration (en secondes, format backend)
									if (trade.duration !== undefined && trade.duration !== null && trade.duration !== '') {
										const durationNum = typeof trade.duration === 'number' ? trade.duration : Number(trade.duration);
										if (!isNaN(durationNum) && durationNum > 0) {
											return formatDurationFromSeconds(durationNum);
										}
									}
									// Priorité 3: Calculer depuis opened_at et closed_at
									if (trade.opened_at && trade.closed_at) {
										const calculated = formatDuration(trade.opened_at, trade.closed_at);
										if (calculated !== 'N/A') {
											return calculated;
										}
									}
									// Priorité 4: Calculer depuis timestamp et closed_at
									if (trade.timestamp && trade.closed_at) {
										const calculated = formatDuration(trade.timestamp, trade.closed_at);
										if (calculated !== 'N/A') {
											return calculated;
										}
									}
									// Fallback
									return 'N/A';
								})()}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<!-- 🔥 PAGINATION: Contrôles de pagination -->
		{#if $totalPages > 1}
			<div class="pagination">
				<button
					class="pagination-btn"
					on:click={prevPage}
					disabled={currentPage === 1}
				>
					« Précédent
				</button>

				<div class="pagination-info">
					Page {currentPage} sur {$totalPages}
					<span class="trades-range">
						({(currentPage - 1) * tradesPerPage + 1}-{Math.min(currentPage * tradesPerPage, $sortedTrades.length)} sur {$sortedTrades.length} trades)
					</span>
				</div>

				<button
					class="pagination-btn"
					on:click={nextPage}
					disabled={currentPage === $totalPages}
				>
					Suivant »
				</button>
			</div>
		{/if}
	{/if}
</div>

<style>
	.trade-history {
		background: #1e2749;
		border-radius: 12px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.history-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
		padding-bottom: 15px;
		border-bottom: 2px solid #2a3a6b;
		flex-wrap: wrap;
		gap: 15px;
	}

	.header-stats {
		display: flex;
		align-items: center;
		gap: 15px;
		flex-wrap: wrap;
	}

	.session-pnl {
		background: rgba(0, 170, 255, 0.2);
		color: #00aaff;
		padding: 6px 14px;
		border-radius: 12px;
		font-size: 12px;
		font-weight: bold;
		border: 1px solid #00aaff;
		font-family: 'Courier New', monospace;
	}

	.session-pnl.positive {
		background: rgba(0, 255, 136, 0.2);
		color: #00ff88;
		border-color: #00ff88;
	}

	.session-pnl.negative {
		background: rgba(255, 68, 68, 0.2);
		color: #ff4444;
		border-color: #ff4444;
	}

	.history-header h3 {
		font-size: 20px;
		color: #00ff88;
		font-weight: bold;
		margin: 0;
	}

	.total-count {
		background: rgba(0, 170, 255, 0.2);
		color: #00aaff;
		padding: 6px 14px;
		border-radius: 12px;
		font-size: 12px;
		font-weight: bold;
		border: 1px solid #00aaff;
	}

	.no-trades {
		text-align: center;
		padding: 60px 20px;
	}

	.no-trades-icon {
		font-size: 64px;
		margin-bottom: 15px;
		opacity: 0.5;
	}

	.no-trades-text {
		font-size: 14px;
		color: #888;
	}

	.table-container {
		overflow-x: auto;
		background: #0a0e27;
		border-radius: 8px;
		padding: 15px;
	}

	.trades-table {
		width: 100%;
		border-collapse: collapse;
		font-family: 'Courier New', monospace;
		font-size: 12px;
	}

	.trades-table thead {
		background: rgba(0, 255, 136, 0.1);
		border-bottom: 2px solid #00ff88;
	}

	.trades-table th {
		padding: 12px 10px;
		text-align: left;
		font-weight: bold;
		color: #00ff88;
		text-transform: uppercase;
		font-size: 11px;
		letter-spacing: 0.5px;
		border-bottom: 2px solid #00ff88;
	}

	.trades-table tbody tr {
		border-bottom: 1px solid #2a3a6b;
		transition: all 0.2s;
	}

	.trades-table tbody tr:hover {
		background: rgba(0, 255, 136, 0.05);
	}

	.trades-table tbody tr.win {
		border-left: 4px solid #00ff88;
	}

	.trades-table tbody tr.loss {
		border-left: 4px solid #ff4444;
	}

	.trades-table td {
		padding: 10px;
		color: #fff;
	}

	.index {
		color: #888;
		font-size: 11px;
		text-align: center;
		width: 40px;
	}

	.time {
		color: #888;
		font-size: 11px;
		white-space: nowrap;
		font-family: 'Courier New', monospace;
	}

	.symbol {
		font-weight: bold;
		color: #fff;
	}

	.direction span {
		padding: 4px 8px;
		border-radius: 4px;
		font-weight: bold;
		font-size: 11px;
	}

	.direction .long {
		background: rgba(0, 255, 136, 0.2);
		color: #00ff88;
		border: 1px solid #00ff88;
	}

	.direction .short {
		background: rgba(255, 68, 68, 0.2);
		color: #ff4444;
		border: 1px solid #ff4444;
	}

	.price {
		font-family: 'Courier New', monospace;
		color: #00aaff;
	}

	.exit-price {
		font-family: 'Courier New', monospace;
		color: #00aaff;
		font-weight: 500;
	}

	.size {
		color: #ffaa00;
	}

	.pnl-pct, .pnl-usdt {
		font-weight: bold;
	}

	.positive {
		color: #00ff88;
	}

	.negative {
		color: #ff4444;
	}

	.reason {
		color: #00aaff;
		font-size: 11px;
	}

	.reason-manual {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		color: #00aaff;
	}

	.pnl-gross {
		font-weight: bold;
	}

	.duration {
		color: #888;
		font-size: 11px;
	}

	.signals {
		color: #00aaff;
		font-size: 10px;
		max-width: 150px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* 🔥 PAGINATION: Styles */
	.pagination {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 20px;
		padding: 15px 20px;
		background: rgba(0, 170, 255, 0.1);
		border-radius: 8px;
		border: 1px solid #2a3a6b;
	}

	.pagination-btn {
		background: #00aaff;
		color: #0a0e27;
		border: none;
		padding: 10px 20px;
		border-radius: 6px;
		font-weight: bold;
		font-size: 13px;
		cursor: pointer;
		transition: all 0.2s;
		font-family: 'Courier New', monospace;
	}

	.pagination-btn:hover:not(:disabled) {
		background: #00ff88;
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(0, 255, 136, 0.3);
	}

	.pagination-btn:disabled {
		background: #2a3a6b;
		color: #666;
		cursor: not-allowed;
		opacity: 0.5;
	}

	.pagination-info {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 5px;
		color: #00aaff;
		font-weight: bold;
		font-size: 13px;
		font-family: 'Courier New', monospace;
	}

	.trades-range {
		font-size: 11px;
		color: #888;
		font-weight: normal;
	}

	/* Mobile responsive */
	@media (max-width: 1024px) {
		.table-container {
			overflow-x: scroll;
		}

		.trades-table {
			min-width: 1200px;
		}
	}

	@media (max-width: 768px) {
		.trades-table {
			font-size: 10px;
		}

		.trades-table th,
		.trades-table td {
			padding: 8px 6px;
		}

		.pagination {
			flex-direction: column;
			gap: 10px;
		}

		.pagination-btn {
			width: 100%;
		}
	}
</style>
