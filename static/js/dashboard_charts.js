/**
 * 📊 DASHBOARD CHARTS - JavaScript
 * Gestion graphiques Chart.js + temps réel via SocketIO
 */

// ==================== SOCKET.IO CONNECTION ====================

const socket = io();

socket.on('connect', () => {
    console.log('✅ Connected to Socket.IO');
    updateConnectionStatus(true);
});

socket.on('disconnect', () => {
    console.warn('❌ Disconnected from Socket.IO');
    updateConnectionStatus(false);
});

function updateConnectionStatus(connected) {
    const statusElement = document.getElementById('connectionStatus');
    if (connected) {
        statusElement.textContent = '🟢 Connecté';
        statusElement.className = 'connected';
    } else {
        statusElement.textContent = '🔴 Déconnecté';
        statusElement.className = 'disconnected';
    }
}

// ==================== CHARTS INITIALIZATION ====================

let charts = {};

// Equity Curve Chart
charts.equity = new Chart(document.getElementById('equityChart'), {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Capital',
            data: [],
            borderColor: '#00ff88',
            backgroundColor: 'rgba(0, 255, 136, 0.1)',
            borderWidth: 2,
            fill: true,
            tension: 0.4
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { color: '#fff' }
            }
        },
        scales: {
            x: {
                ticks: { color: '#fff' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' }
            },
            y: {
                ticks: { color: '#fff' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' }
            }
        }
    }
});

// Win/Loss Ratio Chart
charts.winLoss = new Chart(document.getElementById('winLossChart'), {
    type: 'doughnut',
    data: {
        labels: ['Wins', 'Losses'],
        datasets: [{
            data: [0, 0],
            backgroundColor: ['#00ff88', '#ff4757'],
            borderWidth: 0
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { color: '#fff' }
            }
        }
    }
});

// PnL Distribution Chart
charts.pnlDistribution = new Chart(document.getElementById('pnlDistributionChart'), {
    type: 'bar',
    data: {
        labels: [],
        datasets: [{
            label: 'PnL (%)',
            data: [],
            backgroundColor: [],
            borderWidth: 0
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                ticks: { color: '#fff' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' }
            },
            y: {
                ticks: { color: '#fff' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' }
            }
        }
    }
});

// Symbol Chart
charts.symbol = new Chart(document.getElementById('symbolChart'), {
    type: 'bar',
    data: {
        labels: [],
        datasets: [{
            label: 'Trades',
            data: [],
            backgroundColor: '#667eea',
            borderWidth: 0
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                ticks: { color: '#fff' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' }
            },
            y: {
                ticks: { color: '#fff' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' }
            }
        }
    }
});

// Hourly Performance Chart
charts.hourly = new Chart(document.getElementById('hourlyChart'), {
    type: 'bar',
    data: {
        labels: Array.from({length: 24}, (_, i) => `${i}h`),
        datasets: [{
            label: 'PnL',
            data: Array(24).fill(0),
            backgroundColor: [],
            borderWidth: 0
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                ticks: { color: '#fff' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' }
            },
            y: {
                ticks: { color: '#fff' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' }
            }
        }
    }
});

// Exit Reason Chart
charts.exitReason = new Chart(document.getElementById('exitReasonChart'), {
    type: 'pie',
    data: {
        labels: [],
        datasets: [{
            data: [],
            backgroundColor: [
                '#00ff88',
                '#ff4757',
                '#ffd93d',
                '#667eea',
                '#764ba2',
                '#f8b500'
            ],
            borderWidth: 0
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { color: '#fff' }
            }
        }
    }
});

// ==================== DATA LOADING ====================

async function loadInitialData() {
    try {
        // Charger stats
        const statsResponse = await fetch('/api/stats');
        const statsData = await statsResponse.json();
        
        if (statsData.success) {
            updateStats(statsData.stats);
        }
        
        // Charger trades
        const tradesResponse = await fetch('/api/trades?limit=500');
        const tradesData = await tradesResponse.json();
        
        if (tradesData.success) {
            updateChartsWithTrades(tradesData.trades);
        }
        
    } catch (error) {
        console.error('❌ Erreur chargement données:', error);
    }
}

// ==================== STATS UPDATE ====================

function updateStats(stats) {
    // Capital
    const capital = stats.capital || 1000;
    document.getElementById('statCapital').textContent = `$${capital.toFixed(2)}`;
    
    // PnL Total
    const pnlTotal = stats.pnl_total || 0;
    const pnlElement = document.getElementById('statPnl');
    pnlElement.textContent = `$${pnlTotal.toFixed(2)}`;
    pnlElement.className = pnlTotal > 0 ? 'stat-value positive' : pnlTotal < 0 ? 'stat-value negative' : 'stat-value neutral';
    
    // Winrate
    const winrate = stats.winrate || 0;
    document.getElementById('statWinrate').textContent = `${winrate.toFixed(1)}%`;
    
    // Trades
    const totalTrades = stats.total_trades || 0;
    document.getElementById('statTrades').textContent = totalTrades;
    
    // Profit Factor
    const profitFactor = stats.profit_factor || 0;
    document.getElementById('statProfitFactor').textContent = profitFactor.toFixed(2);
    
    // Max Drawdown
    const maxDD = stats.max_drawdown || 0;
    document.getElementById('statMaxDD').textContent = `${maxDD.toFixed(1)}%`;
}

// ==================== CHARTS UPDATE ====================

function updateChartsWithTrades(trades) {
    if (!trades || trades.length === 0) {
        console.warn('⚠️ Aucun trade à afficher');
        return;
    }
    
    // Equity Curve
    updateEquityCurve(trades);
    
    // Win/Loss
    updateWinLoss(trades);
    
    // PnL Distribution
    updatePnlDistribution(trades);
    
    // Trades par Symbole
    updateSymbolChart(trades);
    
    // Hourly Performance
    updateHourlyChart(trades);
    
    // Exit Reasons
    updateExitReasonChart(trades);
}

function updateEquityCurve(trades) {
    const equityData = [];
    const labels = [];
    let capital = 1000;
    
    trades.forEach((trade, index) => {
        capital += (trade.pnl_usdt || 0);
        equityData.push(capital);
        
        // Label tous les 10 trades
        if (index % 10 === 0) {
            labels.push(`T${index + 1}`);
        } else {
            labels.push('');
        }
    });
    
    charts.equity.data.labels = labels;
    charts.equity.data.datasets[0].data = equityData;
    charts.equity.update();
}

function updateWinLoss(trades) {
    const wins = trades.filter(t => (t.pnl_usdt || 0) > 0).length;
    const losses = trades.filter(t => (t.pnl_usdt || 0) < 0).length;
    
    charts.winLoss.data.datasets[0].data = [wins, losses];
    charts.winLoss.update();
}

function updatePnlDistribution(trades) {
    const pnls = trades.map(t => t.pnl_pct || 0).slice(-20); // 20 derniers
    const labels = pnls.map((_, i) => `T${trades.length - 20 + i + 1}`);
    const colors = pnls.map(pnl => pnl > 0 ? '#00ff88' : '#ff4757');
    
    charts.pnlDistribution.data.labels = labels;
    charts.pnlDistribution.data.datasets[0].data = pnls;
    charts.pnlDistribution.data.datasets[0].backgroundColor = colors;
    charts.pnlDistribution.update();
}

function updateSymbolChart(trades) {
    // Compter trades par symbole
    const symbolCounts = {};
    trades.forEach(trade => {
        const symbol = trade.symbol || 'Unknown';
        symbolCounts[symbol] = (symbolCounts[symbol] || 0) + 1;
    });
    
    // Trier et prendre top 10
    const sortedSymbols = Object.entries(symbolCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
    
    const labels = sortedSymbols.map(([symbol, _]) => symbol);
    const data = sortedSymbols.map(([_, count]) => count);
    
    charts.symbol.data.labels = labels;
    charts.symbol.data.datasets[0].data = data;
    charts.symbol.update();
}

function updateHourlyChart(trades) {
    // Agréger PnL par heure
    const hourlyPnl = Array(24).fill(0);
    
    trades.forEach(trade => {
        if (trade.start_time) {
            const hour = new Date(trade.start_time * 1000).getHours();
            hourlyPnl[hour] += (trade.pnl_usdt || 0);
        }
    });
    
    const colors = hourlyPnl.map(pnl => pnl > 0 ? '#00ff88' : pnl < 0 ? '#ff4757' : '#667eea');
    
    charts.hourly.data.datasets[0].data = hourlyPnl;
    charts.hourly.data.datasets[0].backgroundColor = colors;
    charts.hourly.update();
}

function updateExitReasonChart(trades) {
    // Compter raisons fermeture
    const reasonCounts = {};
    trades.forEach(trade => {
        const reason = trade.exit_reason || 'Unknown';
        reasonCounts[reason] = (reasonCounts[reason] || 0) + 1;
    });
    
    const labels = Object.keys(reasonCounts);
    const data = Object.values(reasonCounts);
    
    charts.exitReason.data.labels = labels;
    charts.exitReason.data.datasets[0].data = data;
    charts.exitReason.update();
}

// ==================== REAL-TIME UPDATES ====================

socket.on('position_opened', (data) => {
    console.log('🟢 Position ouverte (temps réel):', data);
    
    // Recharger données pour mettre à jour stats et graphiques
    loadInitialData();
});

socket.on('position_closed', (data) => {
    console.log('🔔 Position fermée (temps réel):', data);
    
    // Recharger données pour mettre à jour stats et graphiques
    loadInitialData();
});

socket.on('tp_escalier_level', (data) => {
    console.log('🎯 TP Escalier niveau atteint (temps réel):', data);
    
    // Recharger données pour mettre à jour stats
    loadInitialData();
});

socket.on('stats_update', (data) => {
    console.log('📊 Stats update (temps réel):', data);
    updateStats(data);
});

// ==================== INITIALIZATION ====================

// Charger données initiales
loadInitialData();

// Refresh périodique (toutes les 30s)
setInterval(() => {
    loadInitialData();
}, 30000);

console.log('📊 Dashboard Charts initialisé');

