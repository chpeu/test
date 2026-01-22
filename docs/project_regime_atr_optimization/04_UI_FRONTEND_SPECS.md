# 🖥️ SPÉCIFICATIONS UI FRONTEND - ML Dashboard
## Interface utilisateur pour le système ML Adaptatif

> **Version:** 1.0.0 | **Date:** 11/12/2025 | **Statut:** 📋 PLANIFIÉ

---

## 🎯 OBJECTIFS UI

1. **Visualiser** l'état du système ML en temps réel
2. **Configurer** les modules ML (activation/désactivation)
3. **Monitorer** les performances par contexte
4. **Alerter** en cas de drift ou anomalie

---

## 📁 STRUCTURE FICHIERS FRONTEND

```
frontend/src/lib/components/ml/
├── MLPanel.svelte              # Container principal (existant)
├── CorrelationAnalytics.svelte # Analyse corrélations (existant)
│
├── MLDashboard.svelte          # 🆕 Vue d'ensemble système
├── MLConfigPanel.svelte        # 🆕 Configuration toggles
├── ThresholdOptimizer.svelte   # 🆕 Visualisation seuils dynamiques
├── DriftIndicator.svelte       # 🆕 Alertes drift
├── RegimeClassifier.svelte     # 🆕 Status classifier ML
└── SLTPPredictor.svelte        # 🆕 Status predicteur SL/TP
```

---

## 🧩 COMPOSANTS DÉTAILLÉS

### 1. MLDashboard.svelte

**Description:** Vue d'ensemble du système ML avec métriques clés.

```svelte
<script>
  import { onMount, onDestroy } from 'svelte';
  
  let mlStatus = {
    tradeFilter: { enabled: true, confidence: 0.68, threshold: 0.55 },
    regimeDetector: { enabled: true, current: 'VOLATILE', confidence: 0.87 },
    sltpPredictor: { enabled: false, status: 'waiting_data' },
    onlineLearning: { enabled: true, lastUpdate: '12 min ago' },
    driftDetected: false
  };
  
  let performanceByContext = [];
  let ws;
  
  onMount(async () => {
    // Charger données initiales
    await loadMLStatus();
    await loadPerformanceData();
    
    // WebSocket pour updates temps réel
    ws = new WebSocket('ws://localhost:8000/ws/ml-status');
    ws.onmessage = (event) => {
      mlStatus = JSON.parse(event.data);
    };
  });
  
  onDestroy(() => {
    if (ws) ws.close();
  });
</script>

<div class="ml-dashboard">
  <header>
    <h2>🧠 ML Dashboard</h2>
    <button on:click={() => showConfig = true}>⚙️ Config</button>
  </header>
  
  <!-- Cartes status modules -->
  <div class="status-cards">
    <StatusCard 
      title="Trade Filter"
      icon="🎯"
      enabled={mlStatus.tradeFilter.enabled}
      metrics={[
        { label: 'Confidence', value: mlStatus.tradeFilter.confidence, format: 'percent' },
        { label: 'Threshold', value: mlStatus.tradeFilter.threshold }
      ]}
    />
    
    <StatusCard 
      title="Regime"
      icon="📊"
      enabled={mlStatus.regimeDetector.enabled}
      highlight={mlStatus.regimeDetector.current}
      metrics={[
        { label: 'Current', value: mlStatus.regimeDetector.current },
        { label: 'Confidence', value: mlStatus.regimeDetector.confidence, format: 'percent' }
      ]}
    />
    
    <StatusCard 
      title="SL/TP"
      icon="💰"
      enabled={mlStatus.sltpPredictor.enabled}
      status={mlStatus.sltpPredictor.status}
    />
  </div>
  
  <!-- Performance par contexte -->
  <PerformanceTable data={performanceByContext} />
  
  <!-- Online Learning status -->
  <OnlineLearningStatus 
    lastUpdate={mlStatus.onlineLearning.lastUpdate}
    driftDetected={mlStatus.driftDetected}
  />
</div>
```

---

### 2. MLConfigPanel.svelte

**Description:** Panel de configuration pour activer/désactiver les modules.

```svelte
<script>
  export let config = {};
  
  let modules = [
    {
      id: 'gb_filter',
      name: 'GradientBoosting Trade Filter',
      description: 'Filtre les trades avec ML (64-69% accuracy)',
      enabled: true,
      params: [
        { key: 'gb_min_confidence', label: 'Min Confidence', type: 'slider', min: 0.4, max: 0.75, step: 0.05 }
      ]
    },
    {
      id: 'threshold_optimizer',
      name: 'Contextual Threshold Optimizer',
      description: 'Ajuste le seuil selon contexte (régime, session)',
      enabled: false,
      phase: '2D',
      params: [
        { key: 'threshold_min', label: 'Min Threshold', type: 'slider', min: 0.4, max: 0.6, step: 0.05 },
        { key: 'threshold_max', label: 'Max Threshold', type: 'slider', min: 0.5, max: 0.75, step: 0.05 },
        { key: 'optimizer_mode', label: 'Mode', type: 'select', options: ['thompson_sampling', 'ucb', 'fixed'] }
      ]
    },
    {
      id: 'regime_classifier',
      name: 'ML Regime Classifier',
      description: 'Détecte le régime via LightGBM (remplace seuils ATR)',
      enabled: false,
      phase: '3A',
      requiresData: 500,
      currentData: 304
    },
    {
      id: 'sltp_predictor',
      name: 'Dynamic SL/TP Predictor',
      description: 'Prédit multiplicateurs optimaux par setup',
      enabled: false,
      phase: '3B',
      requiresData: 500,
      currentData: 304
    },
    {
      id: 'online_learning',
      name: 'Online Learning',
      description: 'Apprentissage incrémental après chaque trade',
      enabled: false,
      phase: '3C',
      params: [
        { key: 'learning_rate', label: 'Learning Rate', type: 'slider', min: 0.001, max: 0.1, step: 0.005 },
        { key: 'update_frequency', label: 'Update', type: 'select', options: ['each_trade', 'each_10_trades', 'hourly'] }
      ]
    },
    {
      id: 'drift_detection',
      name: 'Drift Detection',
      description: 'Détecte changements comportement marché',
      enabled: true,
      params: [
        { key: 'drift_algorithm', label: 'Algorithm', type: 'select', options: ['adwin', 'page_hinkley', 'ddm'] },
        { key: 'alert_threshold', label: 'Alert Threshold', type: 'slider', min: 0.01, max: 0.1, step: 0.01 }
      ]
    }
  ];
  
  async function saveConfig() {
    await fetch('/api/ml/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
  }
</script>

<div class="config-panel">
  <h2>⚙️ ML Configuration</h2>
  
  {#each modules as module}
    <div class="module-config" class:disabled={!module.enabled}>
      <div class="module-header">
        <label class="toggle">
          <input type="checkbox" bind:checked={module.enabled} />
          <span class="slider"></span>
        </label>
        <div class="module-info">
          <h3>{module.name}</h3>
          <p>{module.description}</p>
          {#if module.phase}
            <span class="phase-badge">Phase {module.phase}</span>
          {/if}
        </div>
      </div>
      
      {#if module.enabled && module.params}
        <div class="module-params">
          {#each module.params as param}
            {#if param.type === 'slider'}
              <label>
                {param.label}: {config[param.key] || param.min}
                <input 
                  type="range" 
                  min={param.min} 
                  max={param.max} 
                  step={param.step}
                  bind:value={config[param.key]}
                />
              </label>
            {:else if param.type === 'select'}
              <label>
                {param.label}:
                <select bind:value={config[param.key]}>
                  {#each param.options as opt}
                    <option value={opt}>{opt}</option>
                  {/each}
                </select>
              </label>
            {/if}
          {/each}
        </div>
      {/if}
      
      {#if module.requiresData}
        <div class="data-progress">
          <span>Données: {module.currentData}/{module.requiresData}</span>
          <div class="progress-bar">
            <div 
              class="progress" 
              style="width: {(module.currentData / module.requiresData) * 100}%"
            ></div>
          </div>
        </div>
      {/if}
    </div>
  {/each}
  
  <div class="actions">
    <button on:click={saveConfig}>💾 Sauvegarder</button>
    <button on:click={resetDefaults}>↩️ Reset Defaults</button>
  </div>
</div>
```

---

### 3. ThresholdOptimizer.svelte

**Description:** Visualisation des seuils dynamiques par contexte.

```svelte
<script>
  export let thresholds = {};
  
  // Données par contexte
  let contextData = [
    { regime: 'CALME', session: 'EUROPE', threshold: 0.52, winrate: 58, trades: 45, pnl: 12.5 },
    { regime: 'CALME', session: 'US', threshold: 0.58, winrate: 48, trades: 32, pnl: 2.1 },
    { regime: 'VOLATILE', session: 'EUROPE', threshold: 0.48, winrate: 62, trades: 28, pnl: 18.3 },
    // ...
  ];
</script>

<div class="threshold-optimizer">
  <h3>📊 Seuils Dynamiques par Contexte</h3>
  
  <div class="heatmap">
    <!-- Heatmap régime x session avec couleur = threshold -->
    <table>
      <thead>
        <tr>
          <th></th>
          <th>ASIA</th>
          <th>EUROPE</th>
          <th>US</th>
        </tr>
      </thead>
      <tbody>
        {#each ['CALME', 'NORMAL', 'VOLATILE'] as regime}
          <tr>
            <td>{regime}</td>
            {#each ['ASIA', 'EUROPE', 'US'] as session}
              {@const ctx = contextData.find(c => c.regime === regime && c.session === session)}
              <td 
                class="cell"
                style="background: {getColorForThreshold(ctx?.threshold || 0.55)}"
                title="WR: {ctx?.winrate}% | Trades: {ctx?.trades}"
              >
                {(ctx?.threshold || 0.55).toFixed(2)}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  
  <div class="legend">
    <span class="low">0.45 (Agressif)</span>
    <span class="gradient"></span>
    <span class="high">0.70 (Conservateur)</span>
  </div>
</div>
```

---

### 4. DriftIndicator.svelte

**Description:** Indicateur d'alerte pour drift détecté.

```svelte
<script>
  export let driftStatus = {
    pnlDrift: false,
    winrateDrift: false,
    lastCheck: new Date(),
    history: []
  };
  
  $: hasDrift = driftStatus.pnlDrift || driftStatus.winrateDrift;
</script>

<div class="drift-indicator" class:alert={hasDrift}>
  <div class="status">
    {#if hasDrift}
      <span class="icon">⚠️</span>
      <span class="text">Drift Détecté!</span>
    {:else}
      <span class="icon">✅</span>
      <span class="text">Marché Stable</span>
    {/if}
  </div>
  
  {#if hasDrift}
    <div class="drift-details">
      {#if driftStatus.pnlDrift}
        <div class="drift-type">
          📉 PnL Drift: Le comportement PnL a changé significativement
        </div>
      {/if}
      {#if driftStatus.winrateDrift}
        <div class="drift-type">
          📊 WinRate Drift: Le taux de win a changé significativement
        </div>
      {/if}
      <button on:click={triggerRetrain}>🔄 Déclencher Réentraînement</button>
    </div>
  {/if}
  
  <div class="last-check">
    Dernière vérification: {formatTime(driftStatus.lastCheck)}
  </div>
</div>
```

---

## 🔌 API ENDPOINTS REQUIS

### GET /api/ml/status
```json
{
  "trade_filter": {
    "enabled": true,
    "model_loaded": true,
    "last_prediction": {
      "confidence": 0.68,
      "threshold_used": 0.55,
      "result": "trade"
    }
  },
  "regime_detector": {
    "mode": "rules",  // "rules" ou "ml"
    "current_regime": "VOLATILE",
    "confidence": 0.87,
    "since": "2025-12-11T14:32:00Z"
  },
  "threshold_optimizer": {
    "enabled": true,
    "mode": "thompson_sampling",
    "contexts_tracked": 12,
    "current_thresholds": {
      "VOLATILE_EUROPE": 0.48,
      "CALME_ASIA": 0.62
    }
  },
  "online_learning": {
    "enabled": true,
    "last_update": "2025-12-11T14:45:00Z",
    "trades_since_update": 3
  },
  "drift_detection": {
    "pnl_drift": false,
    "winrate_drift": false,
    "last_check": "2025-12-11T14:50:00Z"
  }
}
```

### POST /api/ml/config
```json
{
  "gb_filter_enabled": true,
  "gb_min_confidence": 0.55,
  "threshold_optimizer_enabled": true,
  "threshold_min": 0.45,
  "threshold_max": 0.70,
  "threshold_mode": "thompson_sampling",
  "regime_classifier_enabled": false,
  "sltp_predictor_enabled": false,
  "online_learning_enabled": true,
  "online_learning_rate": 0.01,
  "drift_detection_enabled": true,
  "drift_algorithm": "adwin"
}
```

### GET /api/ml/performance/context
```json
{
  "by_context": [
    {
      "regime": "VOLATILE",
      "session": "EUROPE",
      "trades": 45,
      "winrate": 62.5,
      "pnl": 18.32,
      "optimal_threshold": 0.48,
      "current_threshold": 0.55
    }
  ],
  "recommendations": [
    {
      "context": "CALME_ASIA",
      "action": "increase_threshold",
      "from": 0.55,
      "to": 0.62,
      "reason": "WinRate 35% < 40%"
    }
  ]
}
```

---

## 🎨 DESIGN GUIDELINES

### Couleurs

| Élément | Couleur | Usage |
|---------|---------|-------|
| Enabled/Success | `#28a745` | Modules actifs, trades gagnants |
| Disabled/Error | `#dc3545` | Modules désactivés, alertes |
| Warning/Drift | `#ffc107` | Drift détecté, attention |
| Neutral | `#6c757d` | Texte secondaire |
| Primary | `#4a9eff` | Actions principales |
| Background | `#1a1a2e` | Fond principal |
| Card | `#252540` | Fond cartes |

### Responsive

- Desktop: 3 colonnes pour status cards
- Tablet: 2 colonnes
- Mobile: 1 colonne, panels repliables

---

## ✅ CHECKLIST IMPLÉMENTATION

- [ ] MLDashboard.svelte créé
- [ ] MLConfigPanel.svelte créé
- [ ] ThresholdOptimizer.svelte créé
- [ ] DriftIndicator.svelte créé
- [ ] API /api/ml/status créée
- [ ] API /api/ml/config créée
- [ ] API /api/ml/performance/context créée
- [ ] WebSocket /ws/ml-status créé
- [ ] Tests composants
- [ ] Intégration dans MLPanel.svelte
