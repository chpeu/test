<script>
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';
	import { pnlChartData } from '$lib/stores/trades';
	import { tokens, pnlColors, styleChart, watchTheme } from '$lib/themeColors';

	let canvas;
	let chart;

	// Configuration du chart
	const chartConfig = /** @type {any} */ ({
		type: 'line',
		data: {
			labels: [],
			datasets: [
				{
					label: 'PnL Cumulatif (USDT)',
					data: [],
					borderColor: undefined,
					backgroundColor: undefined,
					borderWidth: 3,
					fill: true,
					tension: 0.4,
					pointRadius: 5,
					pointHoverRadius: 8,
					pointBackgroundColor: undefined,
					pointBorderColor: undefined,
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
						color: undefined,
						font: {
							size: 12,
							family: "ui-monospace, 'JetBrains Mono', monospace"
						},
						padding: 15
					}
				},
				tooltip: {
					backgroundColor: undefined,
					titleColor: undefined,
					bodyColor: undefined,
					borderColor: undefined,
					borderWidth: 1,
					padding: 12,
					displayColors: false,
					callbacks: {
						label: function (context) {
							let label = context.dataset.label || '';
							if (label) {
								label += ': ';
							}
							// 🔥 FIX: Formatage adaptatif pour USDT
							const value = context.parsed.y;
							const absValue = Math.abs(value);
							let decimals = 2;
							if (absValue < 0.01) decimals = 4;
							else if (absValue < 1) decimals = 3;
							else if (absValue >= 10) decimals = 1;
							label += value.toFixed(decimals).replace(/\.?0+$/, '') + ' USDT';
							return label;
						}
					}
				}
			},
			scales: {
				y: {
					beginAtZero: true,
					grid: {
						color: undefined
					},
					ticks: {
						color: undefined,
						font: {
							size: 11,
							family: "ui-monospace, 'JetBrains Mono', monospace"
						},
						callback: function (value) {
							// 🔥 FIX: Formatage adaptatif pour les ticks
							const absValue = Math.abs(value);
							let decimals = 2;
							if (absValue < 0.01) decimals = 4;
							else if (absValue < 1) decimals = 3;
							else if (absValue >= 10) decimals = 1;
							return value.toFixed(decimals).replace(/\.?0+$/, '') + ' $';
						}
					}
				},
				x: {
					grid: {
						color: undefined
					},
					ticks: {
						color: undefined,
						font: {
							size: 10,
							family: "ui-monospace, 'JetBrains Mono', monospace"
						},
						maxRotation: 45,
						minRotation: 45
					}
				}
			}
		}
	});

	onMount(() => {
		// Créer chart avec les couleurs du thème courant
		const t = tokens();
		chartConfig.data.datasets[0] = { ...chartConfig.data.datasets[0], ...pnlColors(true), pointBorderColor: t.textPrimary };
		chart = new Chart(canvas, chartConfig);
		styleChart(chart);
		// Bascule dark/light → recoloration immédiate
		const unsubscribeTheme = watchTheme(() => {
			if (!chart) return;
			const last = chart.data.datasets[0].data.at(-1) || 0;
			Object.assign(chart.data.datasets[0], pnlColors(last >= 0), { pointBorderColor: tokens().textPrimary });
			styleChart(chart);
		});

		// Souscrire aux données
		const unsubscribe = pnlChartData.subscribe((data) => {
			if (!chart) return;
			
			// 🔥 FIX: Nettoyer le graphique si pas de données
			if (!data || !data.values || data.values.length === 0) {
				chart.data.labels = [];
				chart.data.datasets[0].data = [];
				chart.update('none');
				return;
			}

			// 🔥 FIX: Vérifier que les données sont valides
			if (!Array.isArray(data.values) || !Array.isArray(data.labels)) {
				console.warn('PnLChart: Données invalides', data);
				return;
			}

			// Calculer PnL cumulatif
			let cumulative = 0;
			const cumulativeData = data.values.map((val) => {
				const numVal = Number(val) || 0;
				cumulative += numVal;
				return cumulative;
			});

			// Mettre à jour chart
			chart.data.labels = data.labels;
			chart.data.datasets[0].data = cumulativeData;

			// Couleur dynamique (vert si positif, rouge si négatif), selon le thème
			const lastValue = cumulativeData[cumulativeData.length - 1] || 0;
			Object.assign(chart.data.datasets[0], pnlColors(lastValue >= 0), { pointBorderColor: tokens().textPrimary });

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

<div class="pnl-chart-container" data-debug-name="pnlChartContainer">
	<div class="chart-header" data-debug-name="chartHeader">
		<h3 data-debug-name="chartTitle">📈 PnL Curve</h3>
		<div class="chart-info" data-debug-name="chartInfo">Evolution du PnL cumulatif</div>
	</div>
	<div class="chart-wrapper" data-debug-name="chartWrapper">
		<canvas bind:this={canvas} data-debug-name="pnlChart.canvas"></canvas>
	</div>
</div>

<style>
	.pnl-chart-container {
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
		height: 300px;
		width: 100%;
	}

	/* Mobile */
	@media (max-width: 768px) {
		.chart-wrapper {
			height: 250px;
		}
	}
</style>
