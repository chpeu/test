<script>
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';
	import { stats } from '$lib/stores/stats';

	let canvas;
	let chart;

	// Configuration du chart
	const chartConfig = {
		type: 'doughnut',
		data: {
			labels: ['Wins', 'Losses'],
			datasets: [
				{
					data: [0, 0],
					backgroundColor: ['#00ff88', '#ff4444'],
					borderColor: ['#00cc6a', '#cc0000'],
					borderWidth: 2,
					hoverOffset: 10
				}
			]
		},
		options: {
			responsive: true,
			maintainAspectRatio: false,
			plugins: {
				legend: {
					display: true,
					position: 'bottom',
					labels: {
						color: '#fff',
						font: {
							size: 13,
							family: "'Courier New', monospace"
						},
						padding: 15,
						usePointStyle: true,
						pointStyle: 'circle'
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
						label: function (context) {
							const label = context.label || '';
							const value = context.parsed;
							const total = context.dataset.data.reduce((a, b) => a + b, 0);
							const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
							return `${label}: ${value} (${percentage}%)`;
						}
					}
				}
			}
		}
	};

	onMount(() => {
		// Créer chart
		chart = new Chart(canvas, chartConfig);

		// Souscrire aux stats
		const unsubscribe = stats.subscribe((data) => {
			if (!chart || !data) return;

			// Mettre à jour données
			chart.data.datasets[0].data = [data.wins || 0, data.losses || 0];
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

<div class="winloss-chart-container" data-debug-name="winLossChartContainer">
	<div class="chart-header" data-debug-name="chartHeader">
		<h3 data-debug-name="chartTitle">🎯 Win/Loss Distribution</h3>
		<div class="chart-info" data-debug-name="chartInfo">Répartition des résultats</div>
	</div>
	<div class="chart-wrapper" data-debug-name="chartWrapper">
		<canvas bind:this={canvas} data-debug-name="winLossChart.canvas"></canvas>
	</div>

	<!-- Stats rapides -->
	<div class="quick-stats" data-debug-name="quickStats">
		<div class="stat-item win" data-debug-name="statItem.wins">
			<div class="stat-value" data-debug-name="stats.wins">{$stats.wins}</div>
			<div class="stat-label" data-debug-name="statLabel.wins">Wins</div>
		</div>
		<div class="stat-item loss" data-debug-name="statItem.losses">
			<div class="stat-value" data-debug-name="stats.losses">{$stats.losses}</div>
			<div class="stat-label" data-debug-name="statLabel.losses">Losses</div>
		</div>
		<div class="stat-item total" data-debug-name="statItem.total">
			<div class="stat-value" data-debug-name="stats.total_trades">{$stats.total_trades}</div>
			<div class="stat-label" data-debug-name="statLabel.total">Total</div>
		</div>
	</div>
</div>

<style>
	.winloss-chart-container {
		background: #1e2749;
		border-radius: 12px;
		padding: 20px;
		border: 2px solid #2a3a6b;
	}

	.chart-header {
		margin-bottom: 20px;
		text-align: center;
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
		height: 250px;
		width: 100%;
		margin-bottom: 20px;
	}

	.quick-stats {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 10px;
	}

	.stat-item {
		text-align: center;
		padding: 12px;
		border-radius: 8px;
		background: #0a0e27;
		border: 2px solid;
	}

	.stat-item.win {
		border-color: #00ff88;
	}

	.stat-item.loss {
		border-color: #ff4444;
	}

	.stat-item.total {
		border-color: #00aaff;
	}

	.stat-value {
		font-size: 24px;
		font-weight: bold;
		margin-bottom: 5px;
	}

	.stat-item.win .stat-value {
		color: #00ff88;
	}

	.stat-item.loss .stat-value {
		color: #ff4444;
	}

	.stat-item.total .stat-value {
		color: #00aaff;
	}

	.stat-label {
		font-size: 11px;
		color: #888;
		text-transform: uppercase;
		font-weight: bold;
	}

	/* Mobile */
	@media (max-width: 768px) {
		.chart-wrapper {
			height: 200px;
		}

		.quick-stats {
			grid-template-columns: 1fr;
		}
	}
</style>
