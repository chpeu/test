<script>
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';
	import { pnlChartData } from '$lib/stores/trades';

	let canvas;
	let chart;

	// Configuration du chart
	const chartConfig = {
		type: 'line',
		data: {
			labels: [],
			datasets: [
				{
					label: 'PnL Cumulatif (USDT)',
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
							label += context.parsed.y.toFixed(2) + ' USDT';
							return label;
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
							return value.toFixed(2) + ' $';
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

	onMount(() => {
		// Créer chart
		chart = new Chart(canvas, chartConfig);

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

<div class="pnl-chart-container">
	<div class="chart-header">
		<h3>📈 PnL Curve</h3>
		<div class="chart-info">Evolution du PnL cumulatif</div>
	</div>
	<div class="chart-wrapper">
		<canvas bind:this={canvas}></canvas>
	</div>
</div>

<style>
	.pnl-chart-container {
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
	}

	/* Mobile */
	@media (max-width: 768px) {
		.chart-wrapper {
			height: 250px;
		}
	}
</style>
