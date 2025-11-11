<script>
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';
	import { tradeHistory } from '$lib/stores/trades';
	import { formatPercent } from '$lib/utils/format';

	let canvas;
	let chart;

	// Configuration du chart
	const chartConfig = {
		type: 'line',
		data: {
			labels: [],
			datasets: [
				{
					label: 'PnL Cumulatif (%)',
					data: [],
					borderColor: '#00ff88',
					backgroundColor: 'rgba(0, 255, 136, 0.1)',
					borderWidth: 3,
					fill: true,
					tension: 0.4,
					pointRadius: 5,
					pointHoverRadius: 8,
					pointBackgroundColor: '#00ff88',
					pointBorderColor: '#fff',
					pointBorderWidth: 2
				}
			]
		},
		options: {
			responsive: true,
			maintainAspectRatio: false,
			interaction: {
				intersect: false,
				mode: 'index'
			},
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
					displayColors: false,
					callbacks: {
						label: function (context) {
							let label = context.dataset.label || '';
							if (label) {
								label += ': ';
							}
							const value = context.parsed.y;
							label += formatPercent(value) + '%';
							return label;
						}
					}
				}
			},
			scales: {
				y: {
					beginAtZero: false,
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
							return formatPercent(value) + '%';
						}
					}
				},
				x: {
					grid: {
						color: 'rgba(42, 58, 107, 0.2)'
					},
					ticks: {
						color: '#888',
						font: {
							size: 11,
							family: "'Courier New', monospace"
						},
						maxRotation: 0,
						minRotation: 0
					}
				}
			}
		}
	};

	onMount(() => {
		// Créer chart
		chart = new Chart(canvas, chartConfig);

		// Souscrire aux trades pour calculer le PnL cumulatif en %
		const unsubscribe = tradeHistory.subscribe((trades) => {
			if (!chart) return;
			
			// 🔥 FIX: Nettoyer le graphique si pas de trades
			if (!trades || trades.length === 0) {
				chart.data.labels = [];
				chart.data.datasets[0].data = [];
				chart.update('none');
				return;
			}

			// Trier les trades par date de fermeture
			const sortedTrades = [...trades].sort((a, b) => {
				const dateA = new Date(a.closed_at || a.opened_at || 0);
				const dateB = new Date(b.closed_at || b.opened_at || 0);
				return dateA - dateB;
			});

			// Calculer PnL cumulatif en %
			let cumulativePct = 0;
			const labels = [];
			const cumulativeData = [];

			sortedTrades.forEach((trade, index) => {
				// Utiliser net_pnl_pct si disponible, sinon pnl_pct
				const pnlPct = trade.net_pnl_pct || trade.pnl_pct || 0;
				cumulativePct += pnlPct;
				cumulativeData.push(cumulativePct);

				// Créer label simple avec numéro de trade
				labels.push(`#${index + 1}`);
			});

			// Mettre à jour chart
			chart.data.labels = labels;
			chart.data.datasets[0].data = cumulativeData;

			// Couleur dynamique (vert si positif, rouge si négatif)
			const lastValue = cumulativeData[cumulativeData.length - 1] || 0;
			if (lastValue >= 0) {
				chart.data.datasets[0].borderColor = '#00ff88';
				chart.data.datasets[0].backgroundColor = 'rgba(0, 255, 136, 0.1)';
				chart.data.datasets[0].pointBackgroundColor = '#00ff88';
			} else {
				chart.data.datasets[0].borderColor = '#ff4444';
				chart.data.datasets[0].backgroundColor = 'rgba(255, 68, 68, 0.1)';
				chart.data.datasets[0].pointBackgroundColor = '#ff4444';
			}

			chart.update('none'); // Update sans animation pour performance
		});

		return unsubscribe;
	});

	onDestroy(() => {
		if (chart) {
			chart.destroy();
		}
	});
</script>

<div class="pnl-percent-chart-container" data-debug-name="pnlPercentChartContainer">
	<div class="chart-header" data-debug-name="chartHeader">
		<h3 data-debug-name="chartTitle">📊 PnL Curve (%)</h3>
		<div class="chart-info" data-debug-name="chartInfo">Evolution du % profit net cumulatif</div>
	</div>
	<div class="chart-wrapper" data-debug-name="chartWrapper">
		<canvas bind:this={canvas} data-debug-name="pnlPercentChart.canvas"></canvas>
	</div>
</div>

<style>
	.pnl-percent-chart-container {
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
		height: 450px;
		width: 100%;
	}

	/* Mobile */
	@media (max-width: 768px) {
		.chart-wrapper {
			height: 350px;
		}
	}
</style>

