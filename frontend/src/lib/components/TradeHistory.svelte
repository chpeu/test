<script>
	import { sortedTrades } from '$lib/stores/trades';
	import { derived } from 'svelte/store';

	import { formatAdaptive, formatPercent, formatUSDT, formatPrice, getSignificantDecimals } from '$lib/utils/format';

	const ORDER_EVENT_TYPES = new Set(['PARTIAL_TP', 'TP_ESCALIER_LEVEL', 'EXIT']);
	const ORDER_EVENT_LABELS = {
		PARTIAL_TP: 'TP partiel',
		TP_ESCALIER_LEVEL: 'TP escalier',
		EXIT: 'Sortie finale'
	};
	const ORDER_EVENT_ORDER = ['PARTIAL_TP', 'TP_ESCALIER_LEVEL', 'EXIT'];

	// 🔥 PAGINATION: Variables de pagination
	let currentPage = 1;
	const tradesPerPage = 50;

	// Trades paginés
	const paginatedTrades = derived(sortedTrades, $trades => {
		const start = (currentPage - 1) * tradesPerPage;
		const end = start + tradesPerPage;
		return $trades.slice(start, end);
	});

	// 🔥 Détails d'ordres (trade_events)
	let expandedTrades = {}; // Utiliser un objet simple pour la réactivité
	let tradeEventsById = {};
	let tradeEventsLoading = {};
	let tradeEventsError = {};

	function getTradeEventId(trade) {
		return trade?.id || trade?.trade_id || trade?.closure_id;
	}

	function getTradeKey(trade, index) {
		// Priorité absolue à l'ID technique pour la stabilité du state Svelte
		const id = trade?.id || trade?.trade_id || trade?.closure_id || trade?._trade_id || trade?.id_trade;
		if (id) return String(id);
		
		// Fallback sur symbole + timestamp précis
		const symbol = trade?.symbol || 'trade';
		const ts = trade?.closed_at || trade?.opened_at || trade?.timestamp || '';
		return `${symbol}_${ts}`;
	}

	async function loadTradeEvents(tradeEventId) {
		if (!tradeEventId || tradeEventsById[tradeEventId] || tradeEventsLoading[tradeEventId]) return;
		
		// Mise à jour réactive des états de chargement
		tradeEventsLoading = { ...tradeEventsLoading, [tradeEventId]: true };
		tradeEventsError = { ...tradeEventsError, [tradeEventId]: null };
		
		try {
			const { getWebSocket, sendRequestViaWS } = await import('$lib/utils/websocket');
			const ws = getWebSocket();
			if (!ws || !ws.connected) {
				throw new Error('WebSocket non connecté');
			}
			const response = await sendRequestViaWS('trade_events', { trade_id: tradeEventId });
			const payload = response?.data || response || {};
			if (payload?.error) {
				throw new Error(payload.error);
			}
			tradeEventsById = { ...tradeEventsById, [tradeEventId]: payload?.events || [] };
		} catch (err) {
			console.error(`❌ Erreur chargement events (${tradeEventId}):`, err);
			tradeEventsError = { ...tradeEventsError, [tradeEventId]: err?.message || 'Erreur chargement ordres' };
		} finally {
			tradeEventsLoading = { ...tradeEventsLoading, [tradeEventId]: false };
		}
	}

	function toggleTrade(event, trade, index) {
		if (event) {
			event.preventDefault();
			event.stopPropagation();
		}
		
		const tradeKey = getTradeKey(trade, index);
		const id = trade?.id || trade?.trade_id || trade?.closure_id;
		
		console.log('🔵 Toggle Trade HISTORY:', { 
			tradeKey, 
			symbol: trade?.symbol, 
			id,
			currentlyExpanded: !!expandedTrades[tradeKey]
		});

		// Nouvelle référence d'objet pour garantir la réactivité Svelte 4
		const nextExpanded = { ...expandedTrades };
		
		if (nextExpanded[tradeKey]) {
			delete nextExpanded[tradeKey];
			console.log('🔽 Expansion FERMÉE for:', tradeKey);
		} else {
			nextExpanded[tradeKey] = true;
			console.log('🔼 Expansion OUVERTE for:', tradeKey);
			
			const tradeEventId = getTradeEventId(trade);
			if (tradeEventId) {
				console.log('📡 Fetching events for:', tradeEventId);
				loadTradeEvents(tradeEventId);
			} else {
				console.log('⚠️ No tradeEventId found, fallback only');
			}
		}
		
		expandedTrades = nextExpanded;
	}

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

	function getReliableSizeUsdt(trade) {
		const initialSize = Number(trade.size_initial_usdt || 0);
		const executedSize = Number(trade.size_executed_usdt || trade.size || trade.filled_size_usdt || trade.position_size_usdt || 0);
		const pnlUsdt = Number(trade.net_pnl_usdt || 0);
		const pnlPct = Number(trade.net_pnl_pct || 0);

		let calculatedSize = 0;
		if (pnlPct !== 0 && Math.abs(pnlPct) > 0.001) {
			calculatedSize = Math.abs(pnlUsdt / (pnlPct / 100));
		}

		let size = executedSize;
		if (initialSize > 0 && executedSize > 3 * initialSize) {
			size = calculatedSize > 0 ? calculatedSize : initialSize;
		} else if (calculatedSize > 0 && executedSize > 0 && Math.abs(calculatedSize - executedSize) > executedSize * 0.5) {
			size = calculatedSize;
		} else if (size <= 0 && initialSize > 0) {
			size = initialSize;
		} else if (size <= 0 && calculatedSize > 0) {
			size = calculatedSize;
		}

		return size > 0 ? size : 0;
	}

	// 🔥 FIX: Somme simple des colonnes (frais/slippage DÉJÀ déduits dans net_pnl_*)
	const sessionPnL = derived(sortedTrades, $trades => {
		if ($trades.length === 0) return 0;
		return $trades.reduce((sum, trade) => sum + (trade.net_pnl_usdt || 0), 0);
	});

	const sessionPnLPct = derived(sortedTrades, $trades => {
		if ($trades.length === 0) return 0;
		const totalPnlUsdt = $trades.reduce((sum, trade) => sum + Number(trade.net_pnl_usdt || 0), 0);
		const totalSizeUsdt = $trades.reduce((sum, trade) => sum + getReliableSizeUsdt(trade), 0);
		if (!totalSizeUsdt) return 0;
		return (totalPnlUsdt / totalSizeUsdt) * 100;
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

	function getEventLabel(event) {
		return ORDER_EVENT_LABELS[event?.event_type] || event?.event_type || 'Ordre';
	}

	function getEventMeta(event) {
		const details = event?.details || {};
		const metaBits = [];
		if (details.level !== undefined) {
			metaBits.push(`Niveau ${details.level}`);
		}
		if (details.sold_pct !== undefined) {
			metaBits.push(`${formatPercent(details.sold_pct)}%`);
		}
		if (details.sold_usdt !== undefined) {
			metaBits.push(`${formatUSDT(details.sold_usdt)} USDT`);
		}
		if (details.sold_qty !== undefined) {
			metaBits.push(`${formatQuantity(details.sold_qty)} qty`);
		}
		if (details.sold_contracts !== undefined) {
			metaBits.push(`${formatQuantity(details.sold_contracts)} ctr`);
		}
		if (details.remaining_usdt !== undefined) {
			metaBits.push(`reste ${formatUSDT(details.remaining_usdt)} USDT`);
		}
		if (details.remaining_qty !== undefined) {
			metaBits.push(`reste ${formatQuantity(details.remaining_qty)} qty`);
		}
		if (details.remaining_contracts !== undefined) {
			metaBits.push(`reste ${formatQuantity(details.remaining_contracts)} ctr`);
		}
		return metaBits.join(' · ');
	}

	function formatQuantity(value) {
		if (value === null || value === undefined || isNaN(value)) return '0';
		return formatAdaptive(value, 2, 6);
	}

	function getEventPnlPct(event) {
		const value = event?.pnl_pct_at_event;
		if (value === null || value === undefined || isNaN(value)) return 'N/A';
		return `${value >= 0 ? '+' : ''}${formatPercent(value)}%`;
	}

	function getEventPnlUsdt(event) {
		const value = event?.pnl_usdt_at_event;
		if (value === null || value === undefined || isNaN(value)) return 'N/A';
		return `${value >= 0 ? '+' : ''}${formatUSDT(value)} USDT`;
	}

	function getEventPrice(event, trade) {
		const price = event?.price_at_event ?? event?.details?.price ?? event?.details?.fill_price;
		if (!price) return 'N/A';
		const entryPrice = trade?.entry_price || trade?.entry;
		const decimals = entryPrice ? getSignificantDecimals(entryPrice) : null;
		return formatPrice(price, decimals);
	}

	function getEventTimestamp(event, trade) {
		const timestamp = event?.event_timestamp || trade?.closed_at || trade?.timestamp;
		if (!timestamp) return null;
		return formatTime(timestamp);
	}

	function buildFallbackExit(trade) {
		const exitPrice = trade?.exit_price || trade?.close_price || trade?.filled_exit_price || trade?.exit;
		const pnlPct = trade?.net_pnl_pct ?? trade?.pnl_pct;
		const pnlUsdt = trade?.net_pnl_usdt ?? trade?.pnl_usdt;
		if (exitPrice === undefined && pnlPct === undefined && pnlUsdt === undefined) return null;
		return {
			event_type: 'EXIT',
			event_timestamp: trade?.closed_at || trade?.timestamp,
			price_at_event: exitPrice,
			pnl_pct_at_event: pnlPct,
			pnl_usdt_at_event: pnlUsdt,
			details: {
				reason: trade?.reason || trade?.close_reason
			}
		};
	}

	function groupOrderEvents(orderEvents) {
		if (!orderEvents?.length) return [];
		const groups = [];
		ORDER_EVENT_ORDER.forEach(type => {
			const events = orderEvents.filter(event => event?.event_type === type);
			if (events.length) {
				const sorted = [...events].sort((a, b) => {
					const aTime = a?.event_timestamp ? new Date(a.event_timestamp).getTime() : 0;
					const bTime = b?.event_timestamp ? new Date(b.event_timestamp).getTime() : 0;
					return aTime - bTime;
				});
				groups.push({
					type,
					label: ORDER_EVENT_LABELS[type] || type,
					events: sorted
				});
			}
		});

		const extras = orderEvents.filter(event => !ORDER_EVENT_ORDER.includes(event?.event_type));
		if (extras.length) {
			groups.push({
				type: 'OTHER',
				label: 'Autres',
				events: extras
			});
		}

		return groups;
	}

	function getOrderEvents(trade) {
		const tradeEventId = getTradeEventId(trade);
		const events = (tradeEventId && tradeEventsById[tradeEventId]) || [];
		const orderEvents = (events || []).filter(event => ORDER_EVENT_TYPES.has(event?.event_type));
		const hasExit = orderEvents.some(event => event?.event_type === 'EXIT');
		if (!hasExit) {
			const fallbackExit = buildFallbackExit(trade);
			if (fallbackExit) {
				return [...orderEvents, fallbackExit];
			}
		}
		return orderEvents;
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
						<th class="expand-column" data-debug-name="tradeHistory.column.expand"></th>
						<th data-debug-name="tradeHistory.column.index">#</th>
						<th data-debug-name="tradeHistory.column.time">Heure</th>
						<th data-debug-name="tradeHistory.column.symbol">Paire</th>
						<th data-debug-name="tradeHistory.column.direction">Dir</th>
						<th data-debug-name="tradeHistory.column.reason">Raison</th>
						<th data-debug-name="tradeHistory.column.entryPrice">Prix Entrée</th>
						<th data-debug-name="tradeHistory.column.exitPrice">Prix Sortie</th>
						<th data-debug-name="tradeHistory.column.sizeUsdt" title="Montant USDT à l'ouverture">Size USDT</th>
						<th data-debug-name="tradeHistory.column.pnlNet">PnL Net %</th>
						<th data-debug-name="tradeHistory.column.pnlUsdt" title="PnL réalisé depuis API MEXC (frais inclus)">PnL Réalisé USDT</th>
						<th data-debug-name="tradeHistory.column.duration">Duration</th>
					</tr>
				</thead>
				<tbody>
					{#each $paginatedTrades as trade, index (getTradeKey(trade, index))}
					{@const tradeKey = getTradeKey(trade, index)}
					{@const tradeEventId = getTradeEventId(trade)}
					{@const globalIndex = (currentPage - 1) * tradesPerPage + index}
					{@const isWin = (trade.net_pnl_usdt || 0) >= 0}
					<tr class:row-win={isWin} class:row-loss={!isWin} class:row-expanded={expandedTrades[tradeKey]} data-debug-name="trade[{globalIndex}]" on:click={(e) => toggleTrade(e, trade, index)} style="cursor: pointer;">
						<td class="expand-cell" data-debug-name="trade.expand">
							<button class="expand-toggle" on:click|stopPropagation={(e) => toggleTrade(e, trade, index)} aria-label="Afficher les ordres">
								<span class:expanded={expandedTrades[tradeKey]} style="pointer-events: none;">▶</span>
							</button>
						</td>
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
						<!-- 🔥 Size USDT (montant réellement exécuté) -->
						<td class="size-usdt" data-debug-name="trade.size">
							{(() => {
								// 🔥 FIX: Validation intelligente de la taille
								// Si size_executed_usdt est > 3x size_initial_usdt, c'est probablement une erreur
								const initialSize = trade.size_initial_usdt || 0;
								const executedSize = trade.size_executed_usdt || trade.size || trade.filled_size_usdt || trade.position_size_usdt || 0;
								
								// 🔥 FIX: Recalculer size depuis PnL si disponible (plus fiable)
								const pnlUsdt = trade.net_pnl_usdt || 0;
								const pnlPct = trade.net_pnl_pct || 0;
								let calculatedSize = 0;
								if (pnlPct !== 0 && Math.abs(pnlPct) > 0.001) {
									calculatedSize = Math.abs(pnlUsdt / (pnlPct / 100));
								}
								
								// Utiliser la taille la plus fiable
								let size = executedSize;
								if (initialSize > 0 && executedSize > 3 * initialSize) {
									// Taille exécutée suspicieusement grande - utiliser calculée ou initiale
									size = calculatedSize > 0 ? calculatedSize : initialSize;
								} else if (calculatedSize > 0 && Math.abs(calculatedSize - executedSize) > executedSize * 0.5) {
									// Écart > 50% entre calculée et exécutée - utiliser calculée
									size = calculatedSize;
								}
								
								return size > 0 ? formatUSDT(size) : 'N/A';
							})()}
						</td>
						<!-- 🔥 PnL Net % calculé depuis size et pnl_usdt réel -->
						<td class="pnl-net" class:positive={isWin} class:negative={!isWin} data-debug-name="trade.net_pnl_pct">
							{(() => {
								// Priorité 1: net_pnl_pct du backend
								if (trade.net_pnl_pct !== undefined && trade.net_pnl_pct !== null) {
									return `${trade.net_pnl_pct >= 0 ? '+' : ''}${formatPercent(trade.net_pnl_pct)}%`;
								}
								// Priorité 2: Calculer depuis size_executed (réelle) et pnl_usdt
								const size = trade.size_executed_usdt || trade.size || trade.filled_size_usdt || trade.position_size_usdt || 0;
								const pnlUsdt = trade.net_pnl_usdt || 0;
								if (size > 0) {
									const pnlPct = (pnlUsdt / size) * 100;
									return `${pnlPct >= 0 ? '+' : ''}${formatPercent(pnlPct)}%`;
								}
								return 'N/A';
							})()}
						</td>
						<!-- 🔥 FIX: PnL Réalisé USDT = PnL réel depuis API MEXC (4 décimales comme l'API) -->
						<td class="pnl-usdt" class:positive={(trade.net_pnl_usdt || 0) >= 0} class:negative={(trade.net_pnl_usdt || 0) < 0} data-debug-name="trade.net_pnl_usdt" title="PnL réalisé depuis API MEXC | Entry: {trade.entry_price || trade.entry || 'N/A'} | Exit: {trade.exit_price || trade.exit || 'N/A'}">
							{(trade.net_pnl_usdt || 0) >= 0 ? '+' : ''}{(trade.net_pnl_usdt || 0).toFixed(4)} USDT
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
					{#if expandedTrades[tradeKey]}
					{@const orderEvents = getOrderEvents(trade)}
					{@const orderGroups = groupOrderEvents(orderEvents)}
					<tr class="order-row" data-debug-name="trade[{globalIndex}].orders">
						<td colspan="12">
							<div class="order-details">
								<div class="order-details-header">Ordres du trade</div>
								{#if tradeEventId && tradeEventsLoading[tradeEventId]}
									<div class="order-details-status loading">Chargement des ordres...</div>
								{:else}
									{#if tradeEventId && tradeEventsError[tradeEventId]}
										<div class="order-details-status error">{tradeEventsError[tradeEventId]}</div>
										{#if orderGroups.length > 0}
											<div class="order-details-status hint">Fallback local (sortie finale)</div>
										{/if}
									{/if}

									{#if orderGroups.length === 0}
										<div class="order-details-status empty">Aucun ordre enregistré</div>
									{:else}
										<div class="order-groups">
											{#each orderGroups as group}
												<div class="order-group" data-debug-name="trade[{globalIndex}].orders.group.{group.type}">
													<div class="order-group-title">
														{group.label}
														<span class="order-group-count">{group.events.length}</span>
													</div>
													<div class="order-list">
														{#each group.events as event}
															{@const eventTime = getEventTimestamp(event, trade)}
															<div
																class="order-item"
																class:order-partial={event?.event_type === 'PARTIAL_TP'}
																class:order-escalier={event?.event_type === 'TP_ESCALIER_LEVEL'}
																class:order-final={event?.event_type === 'EXIT'}
																class:order-positive={event?.pnl_usdt_at_event !== null && event?.pnl_usdt_at_event !== undefined && event?.pnl_usdt_at_event >= 0}
																class:order-negative={event?.pnl_usdt_at_event !== null && event?.pnl_usdt_at_event !== undefined && event?.pnl_usdt_at_event < 0}
															>
																<div class="order-main">
																	<span class="order-type">{getEventLabel(event)}</span>
																	{#if eventTime}
																		<span class="order-time">{eventTime}</span>
																	{/if}
																	{#if getEventMeta(event)}
																		<span class="order-meta">{getEventMeta(event)}</span>
																	{/if}
																	{#if event?.details?.reason}
																		<span class="order-reason">{event.details.reason}</span>
																	{/if}
																</div>
																<div class="order-metrics">
																	<span class="order-price">Sortie: {getEventPrice(event, trade)}</span>
																	<span class="order-pnl">{getEventPnlPct(event)}</span>
																	<span class="order-pnl-usdt">{getEventPnlUsdt(event)}</span>
																</div>
															</div>
														{/each}
													</div>
												</div>
											{/each}
										</div>
									{/if}
								{/if}
							</div>
						</td>
					</tr>
				{/if}
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

	/* 🔥 Surlignage vert/rouge des lignes selon PnL */
	.trades-table tbody tr.row-win {
		background: rgba(0, 255, 136, 0.08);
		border-left: 4px solid #00ff88;
	}

	.trades-table tbody tr.row-win:hover {
		background: rgba(0, 255, 136, 0.15);
	}

	.trades-table tbody tr.row-loss {
		background: rgba(255, 68, 68, 0.08);
		border-left: 4px solid #ff4444;
	}

	.trades-table tbody tr.row-loss:hover {
		background: rgba(255, 68, 68, 0.15);
	}

	/* Legacy classes pour compatibilité */
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

	.expand-column {
		width: 34px;
	}

	.expand-cell {
		text-align: center;
		padding: 6px 4px;
	}

	.row-expanded {
		background: rgba(0, 170, 255, 0.08);
		border-left-color: #00aaff;
	}

	.row-expanded:hover {
		background: rgba(0, 170, 255, 0.16);
	}

	.expand-toggle {
		background: rgba(0, 170, 255, 0.15);
		border: 1px solid rgba(0, 170, 255, 0.4);
		color: #00aaff;
		width: 26px;
		height: 26px;
		border-radius: 6px;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s ease;
		font-weight: bold;
		padding: 0;
	}

	.expand-toggle:hover {
		background: rgba(0, 170, 255, 0.25);
		transform: translateY(-1px);
		box-shadow: 0 4px 10px rgba(0, 170, 255, 0.25);
	}

	.expand-toggle span {
		display: inline-block;
		transition: transform 0.2s ease;
	}

	.expand-toggle span.expanded {
		transform: rotate(90deg);
	}

	.order-row td {
		padding: 0;
		background: rgba(10, 14, 39, 0.9);
		border-bottom: 1px solid #2a3a6b;
	}

	.order-details {
		padding: 14px 16px 16px;
		border-top: 1px solid rgba(0, 170, 255, 0.2);
		background: linear-gradient(180deg, rgba(0, 170, 255, 0.06), rgba(10, 14, 39, 0.9));
	}

	.order-details-header {
		text-transform: uppercase;
		font-size: 11px;
		letter-spacing: 0.8px;
		color: #7ed0ff;
		margin-bottom: 10px;
		font-weight: 700;
	}

	.order-details-status {
		font-size: 12px;
		color: #8897c4;
		margin-bottom: 10px;
	}

	.order-details-status.loading {
		color: #7ed0ff;
	}

	.order-details-status.error {
		color: #ff6b6b;
	}

	.order-details-status.hint {
		color: #ffd166;
	}

	.order-details-status.empty {
		color: #6c7aa6;
	}

	.order-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.order-groups {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.order-group {
		padding-top: 4px;
	}

	.order-group-title {
		display: flex;
		align-items: center;
		justify-content: space-between;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.7px;
		color: #9bb8ff;
		margin-bottom: 6px;
		font-weight: 700;
	}

	.order-group-count {
		background: rgba(0, 170, 255, 0.18);
		color: #7ed0ff;
		font-size: 10px;
		padding: 2px 8px;
		border-radius: 999px;
		border: 1px solid rgba(0, 170, 255, 0.35);
	}

	.order-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 10px 12px;
		border-radius: 8px;
		background: rgba(30, 39, 73, 0.6);
		border: 1px solid rgba(126, 208, 255, 0.15);
		font-size: 12px;
		gap: 12px;
	}

	.order-item.order-partial {
		border-color: rgba(0, 255, 136, 0.4);
		background: rgba(0, 255, 136, 0.08);
	}

	.order-item.order-escalier {
		border-color: rgba(255, 209, 102, 0.45);
		background: rgba(255, 209, 102, 0.12);
	}

	.order-item.order-final {
		border-color: rgba(126, 208, 255, 0.4);
		background: rgba(0, 170, 255, 0.12);
	}

	.order-main {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	.order-time {
		font-size: 11px;
		color: #6c7aa6;
		font-family: 'Courier New', monospace;
	}

	.order-type {
		font-weight: 700;
		color: #ffffff;
	}

	.order-meta {
		color: #ffd166;
		font-weight: 600;
	}

	.order-reason {
		color: #7ed0ff;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.order-metrics {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
		font-family: 'Courier New', monospace;
		color: #c7d4ff;
	}

	.order-price {
		color: #7ed0ff;
		font-weight: 600;
	}

	.order-pnl {
		font-weight: 700;
	}

	.order-pnl-usdt {
		font-weight: 700;
	}

	.order-positive .order-pnl,
	.order-positive .order-pnl-usdt {
		color: #00ff88;
	}

	.order-negative .order-pnl,
	.order-negative .order-pnl-usdt {
		color: #ff6b6b;
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

	.size-usdt {
		color: #ffaa00;
		font-family: 'Courier New', monospace;
		font-weight: 500;
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
