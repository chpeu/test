<script>
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';
	import { sortedTrades } from '$lib/stores/trades';

	let canvas;
	let chart;
	let maxTrades = 10; // Afficher les 10 derniers trades

	// Configuration du chart
	const chartConfig = {
		type: 'bar',
		data: {
			labels: [],
			datasets: [
				{
					label: 'Size (USDT)',
					data: [],
					backgroundColor: [],
					borderColor: [],
					borderWidth: 2,
					borderRadius: 6,
					hoverBorderWidth: 3
				}
			]
		},
		options: {
			responsive: true,
			maintainAspectRatio: false,
			plugins: {
				legend: {
					display: true,
					position: 'top',
					labels: {
						color: '#fff',
						font: {
							size: 12,
							family: "'Courier New', monospace"
						},
						padding: 15
					}
				},
				tooltip: {
					backgroundColor: 'rgba(10, 14, 39, 0.9)',
					titleColor: '#00ff88',
					bodyColor: '#fff',
					borderColor: '#00ff88',
					borderWidth: 1,
					padding: 12,
					callbacks: {
						title: function (context) {
							return context[0].label;
						},
						label: function (context) {
							const size = context.parsed.y;
							return `Size: ${size.toFixed(2)} USDT`;
						},
						afterLabel: function (context) {
							const index = context.dataIndex;
							const trade = lastTrades[index];
							if (trade) {
								const pnl = trade.net_pnl_usdt >= 0 ? `+${trade.net_pnl_usdt.toFixed(2)}` : trade.net_pnl_usdt.toFixed(2);
								return `PnL: ${pnl} USDT (${trade.net_pnl_pct.toFixed(2)}%)`;
							}
							return '';
						}
					}
				}
			},
			scales: {
				y: {
					beginAtZero: true,
					grid: {
						color: 'rgba(42, 58, 107, 0.3)'
					},
					ticks: {
						color: '#888',
						font: {
							size: 11,
							family: "'Courier New', monospace"
						},
						callback: function (value) {
							return value.toFixed(0) + ' $';
						}
					}
				},
				x: {
					grid: {
						display: false
					},
					ticks: {
						color: '#888',
						font: {
							size: 10,
							family: "'Courier New', monospace"
						},
						maxRotation: 45,
						minRotation: 45
					}
				}
			}
		}
	};

	let lastTrades = [];

	onMount(() => {
		// Créer chart
		chart = new Chart(canvas, chartConfig);

		// Souscrire aux trades
		const unsubscribe = sortedTrades.subscribe((trades) => {
			if (!chart || !trades || trades.length === 0) return;

			// Prendre les N derniers trades
			lastTrades = trades.slice(0, maxTrades).reverse();

			// Extraire données
			const labels = lastTrades.map((t) => `${t.symbol} ${t.direction === 'LONG' ? '📈' : '📉'}`);
			const sizes = lastTrades.map((t) => t.size || 0);

			// Couleurs basées sur PnL
			const bgColors = lastTrades.map((t) =>
				t.net_pnl_usdt >= 0 ? 'rgba(0, 255, 136, 0.7)' : 'rgba(255, 68, 68, 0.7)'
			);
			const borderColors = lastTrades.map((t) =>
				t.net_pnl_usdt >= 0 ? '#00ff88' : '#ff4444'
			);

			// Mettre à jour chart
			chart.data.labels = labels;
			chart.data.datasets[0].data = sizes;
			chart.data.datasets[0].backgroundColor = bgColors;
			chart.data.datasets[0].borderColor = borderColors;

			chart.update('none');
		});

		return unsubscribe;
	});

	onDestroy(() => {
		if (chart) {
			chart.destroy();
		}
	});
</script>

<div class="volume-chart-container">
	<div class="chart-header">
		<h3>📊 Trade Sizes</h3>
		<div class="chart-info">Position size par trade ({maxTrades} derniers)</div>
	</div>
	<div class="chart-wrapper">
		<canvas bind:this={canvas}></canvas>
	</div>

	<!-- Controls -->
	<div class="chart-controls">
		<label for="max-trades">Afficher:</label>
		<select id="max-trades" bind:value={maxTrades}>
			<option value={5}>5 trades</option>
			<option value={10}>10 trades</option>
			<option value={15}>15 trades</option>
			<option value={20}>20 trades</option>
		</select>
	</div>
</div>

<style>
	.volume-chart-container {
		background: #1e2749;
		border-radius: 12px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.chart-header {
		margin-bottom: 20px;
	}

	.chart-header h3 {
		font-size: 18px;
		color: #00ff88;
		font-weight: bold;
		margin-bottom: 5px;
	}

	.chart-info {
		font-size: 12px;
		color: #888;
	}

	.chart-wrapper {
		position: relative;
		height: 300px;
		width: 100%;
		margin-bottom: 15px;
	}

	.chart-controls {
		display: flex;
		align-items: center;
		gap: 10px;
		justify-content: center;
	}

	.chart-controls label {
		font-size: 13px;
		color: #888;
	}

	.chart-controls select {
		padding: 8px 12px;
		background: #0a0e27;
		color: #00ff88;
		border: 2px solid #00ff88;
		border-radius: 6px;
		font-size: 13px;
		font-family: 'Courier New', monospace;
		cursor: pointer;
	}

	.chart-controls select:hover {
		background: rgba(0, 255, 136, 0.1);
	}

	/* Mobile */
	@media (max-width: 768px) {
		.chart-wrapper {
			height: 250px;
		}
	}
</style>
