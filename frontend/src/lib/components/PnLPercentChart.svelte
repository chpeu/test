<script>
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';
	import { pnlColors, styleChart, watchTheme } from '$lib/themeColors';
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
					borderColor: null,
					backgroundColor: null,
					borderWidth: 3,
					fill: true,
					tension: 0.4,
					pointRadius: 5,
					pointHoverRadius: 8,
					pointBackgroundColor: null,
					pointBorderColor: null,
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
						color: null,
						font: {
							size: 12,
							family: "'Courier New', monospace"
						},
						padding: 15
					}
				},
				tooltip: {
					backgroundColor: null,
					titleColor: null,
					bodyColor: null,
					borderColor: null,
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
						color: null
					},
					ticks: {
						color: null,
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
						color: null
					},
					ticks: {
						color: null,
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
		styleChart(chart);
		const unsubscribeTheme = watchTheme(() => {
			if (!chart) return;
			const last = chart.data.datasets[0].data.at(-1) || 0;
			Object.assign(chart.data.datasets[0], pnlColors(last >= 0));
			styleChart(chart);
		});

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

			// Couleur dynamique (vert si positif, rouge si négatif), selon le thème
			const lastValue = cumulativeData[cumulativeData.length - 1] || 0;
			Object.assign(chart.data.datasets[0], pnlColors(lastValue >= 0));

			chart.update('none'); // Update sans animation pour performance
		});

		return () => {
			unsubscribe();
			unsubscribeTheme();
		};
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
		background: var(--bg-secondary);
		border-radius: 12px;
		padding: 20px;
		border: 2px solid var(--border);
	}

	.chart-header {
		margin-bottom: 20px;
	}

	.chart-header h3 {
		font-size: 18px;
		color: var(--accent-green);
		font-weight: bold;
		margin-bottom: 5px;
	}

	.chart-info {
		font-size: 12px;
		color: var(--text-secondary);
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

