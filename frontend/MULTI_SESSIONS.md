# 🔀 Multi-Sessions Guide - Trade Cursor v7.0

Gérer plusieurs bots de trading simultanément avec une seule interface.

---

## 📋 Vue d'ensemble

La fonctionnalité **Multi-Sessions** permet de:
- Exécuter plusieurs instances du bot en parallèle
- Chaque session peut trader différentes paires ou stratégies
- Interface unifiée pour monitorer toutes les sessions
- Agrégation des statistiques globales

---

## 🏗️ Architecture Requise

### Backend (FastAPI)

```
backend/
├── main.py                    # Point d'entrée principal
├── session_manager.py         # Nouveau: Gestion des sessions
├── bot_instances/
│   ├── session_1.py          # Instance bot 1
│   ├── session_2.py          # Instance bot 2
│   └── session_N.py          # Instance bot N
└── config/
    ├── session_1.json        # Config session 1
    ├── session_2.json        # Config session 2
    └── session_N.json        # Config session N
```

### Frontend (SvelteKit)

```
frontend/src/lib/
├── stores/
│   ├── sessions.js           # Nouveau: Store sessions
│   └── activeSession.js      # Nouveau: Session active
├── components/
│   ├── SessionSelector.svelte    # Sélecteur de session
│   ├── SessionCard.svelte        # Card par session
│   └── GlobalStats.svelte        # Stats agrégées
```

---

## 🔧 Implémentation Backend

### 1. Session Manager (`session_manager.py`)

```python
# backend/session_manager.py

from typing import Dict, List, Optional
import asyncio
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class BotSession:
    """Représente une session de bot"""
    session_id: str
    name: str
    pairs: List[str]
    status: str  # 'running', 'stopped', 'paused'
    strategy: str
    config: dict
    created_at: datetime
    stats: dict = None

class SessionManager:
    """Gestionnaire de sessions multiples"""

    def __init__(self):
        self.sessions: Dict[str, BotSession] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}

    def create_session(
        self,
        session_id: str,
        name: str,
        pairs: List[str],
        strategy: str,
        config: dict
    ) -> BotSession:
        """Créer une nouvelle session"""

        session = BotSession(
            session_id=session_id,
            name=name,
            pairs=pairs,
            status='stopped',
            strategy=strategy,
            config=config,
            created_at=datetime.now(),
            stats={'trades': 0, 'pnl': 0}
        )

        self.sessions[session_id] = session
        return session

    async def start_session(self, session_id: str):
        """Démarrer une session"""

        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.sessions[session_id]

        # Créer une task asyncio pour cette session
        task = asyncio.create_task(
            self._run_session(session)
        )

        self.running_tasks[session_id] = task
        session.status = 'running'

    async def stop_session(self, session_id: str):
        """Arrêter une session"""

        if session_id in self.running_tasks:
            task = self.running_tasks[session_id]
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            del self.running_tasks[session_id]

        self.sessions[session_id].status = 'stopped'

    async def _run_session(self, session: BotSession):
        """Boucle principale d'une session"""

        from bot_core import TradingBot  # Import du bot principal

        # Créer instance du bot pour cette session
        bot = TradingBot(
            pairs=session.pairs,
            config=session.config
        )

        # Lancer le bot
        await bot.run()

    def get_all_sessions(self) -> List[BotSession]:
        """Retourner toutes les sessions"""
        return list(self.sessions.values())

    def get_session(self, session_id: str) -> Optional[BotSession]:
        """Retourner une session spécifique"""
        return self.sessions.get(session_id)

    def get_global_stats(self) -> dict:
        """Statistiques agrégées de toutes les sessions"""

        total_trades = sum(s.stats['trades'] for s in self.sessions.values())
        total_pnl = sum(s.stats['pnl'] for s in self.sessions.values())

        running_sessions = sum(
            1 for s in self.sessions.values() if s.status == 'running'
        )

        return {
            'total_sessions': len(self.sessions),
            'running_sessions': running_sessions,
            'total_trades': total_trades,
            'total_pnl': total_pnl
        }
```

### 2. API Endpoints (`main.py`)

```python
# backend/main.py (ajouter ces endpoints)

from session_manager import SessionManager

session_mgr = SessionManager()

@app.post("/api/sessions/create")
async def create_session(request: Request):
    """Créer une nouvelle session"""
    data = await request.json()

    session = session_mgr.create_session(
        session_id=data['session_id'],
        name=data['name'],
        pairs=data['pairs'],
        strategy=data['strategy'],
        config=data['config']
    )

    return {"status": "success", "session": session}

@app.post("/api/sessions/{session_id}/start")
async def start_session(session_id: str):
    """Démarrer une session"""
    await session_mgr.start_session(session_id)
    return {"status": "started"}

@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Arrêter une session"""
    await session_mgr.stop_session(session_id)
    return {"status": "stopped"}

@app.get("/api/sessions")
async def get_sessions():
    """Lister toutes les sessions"""
    sessions = session_mgr.get_all_sessions()
    return {"sessions": sessions}

@app.get("/api/sessions/stats/global")
async def get_global_stats():
    """Stats globales de toutes les sessions"""
    return session_mgr.get_global_stats()

# WebSocket pour broadcast des updates
@socketio.on('session_update')
async def handle_session_update(session_id: str, data: dict):
    """Broadcast update d'une session à tous les clients"""
    await socketio.emit('session_update', {
        'session_id': session_id,
        'data': data
    })
```

---

## 🎨 Implémentation Frontend

### 1. Store Sessions (`sessions.js`)

```javascript
// frontend/src/lib/stores/sessions.js

import { writable, derived } from 'svelte/store';

// Toutes les sessions
export const sessions = writable([]);

// Session actuellement sélectionnée
export const activeSessionId = writable(null);

// Session active (dérivé)
export const activeSession = derived(
	[sessions, activeSessionId],
	([$sessions, $activeSessionId]) => {
		return $sessions.find(s => s.session_id === $activeSessionId) || null;
	}
);

// Stats globales
export const globalStats = writable({
	total_sessions: 0,
	running_sessions: 0,
	total_trades: 0,
	total_pnl: 0
});

// Fonctions API
export async function createSession(sessionData) {
	const res = await fetch('/api/sessions/create', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(sessionData)
	});

	const data = await res.json();

	// Recharger la liste
	await loadSessions();

	return data.session;
}

export async function startSession(sessionId) {
	await fetch(`/api/sessions/${sessionId}/start`, { method: 'POST' });
	await loadSessions();
}

export async function stopSession(sessionId) {
	await fetch(`/api/sessions/${sessionId}/stop`, { method: 'POST' });
	await loadSessions();
}

export async function loadSessions() {
	const res = await fetch('/api/sessions');
	const data = await res.json();
	sessions.set(data.sessions);
}

export async function loadGlobalStats() {
	const res = await fetch('/api/sessions/stats/global');
	const data = await res.json();
	globalStats.set(data);
}
```

### 2. Composant SessionSelector (`SessionSelector.svelte`)

```svelte
<!-- frontend/src/lib/components/SessionSelector.svelte -->

<script>
	import { sessions, activeSessionId, createSession } from '$lib/stores/sessions';

	let showCreateModal = false;
	let newSessionName = '';
	let newSessionPairs = '';

	function selectSession(sessionId) {
		activeSessionId.set(sessionId);
	}

	async function handleCreate() {
		await createSession({
			session_id: `session_${Date.now()}`,
			name: newSessionName,
			pairs: newSessionPairs.split(',').map(p => p.trim()),
			strategy: 'scalping',
			config: {}
		});

		showCreateModal = false;
		newSessionName = '';
		newSessionPairs = '';
	}
</script>

<div class="session-selector">
	<div class="selector-header">
		<h3>📂 Sessions</h3>
		<button on:click={() => showCreateModal = true}>➕ New</button>
	</div>

	<div class="session-list">
		{#each $sessions as session}
			<div
				class="session-item"
				class:active={session.session_id === $activeSessionId}
				on:click={() => selectSession(session.session_id)}
			>
				<div class="session-info">
					<span class="session-name">{session.name}</span>
					<span class="session-status" class:running={session.status === 'running'}>
						{session.status === 'running' ? '🟢' : '⚫'}
					</span>
				</div>
				<div class="session-stats">
					<span>{session.stats?.trades || 0} trades</span>
					<span>{(session.stats?.pnl || 0).toFixed(2)} USDT</span>
				</div>
			</div>
		{/each}
	</div>

	{#if showCreateModal}
		<!-- Modal de création -->
		<div class="modal">
			<div class="modal-content">
				<h3>Create New Session</h3>
				<input placeholder="Session name" bind:value={newSessionName} />
				<input placeholder="Pairs (BTC/USDT, ETH/USDT)" bind:value={newSessionPairs} />
				<div class="modal-actions">
					<button on:click={handleCreate}>Create</button>
					<button on:click={() => showCreateModal = false}>Cancel</button>
				</div>
			</div>
		</div>
	{/if}
</div>
```

### 3. Global Stats (`GlobalStats.svelte`)

```svelte
<!-- frontend/src/lib/components/GlobalStats.svelte -->

<script>
	import { globalStats } from '$lib/stores/sessions';
	import { onMount, onDestroy } from 'svelte';

	let interval;

	onMount(() => {
		// Charger stats globales toutes les 5 secondes
		interval = setInterval(loadGlobalStats, 5000);
		loadGlobalStats();
	});

	onDestroy(() => clearInterval(interval));
</script>

<div class="global-stats">
	<div class="stat-card">
		<div class="stat-label">Total Sessions</div>
		<div class="stat-value">{$globalStats.total_sessions}</div>
	</div>

	<div class="stat-card">
		<div class="stat-label">Running</div>
		<div class="stat-value running">{$globalStats.running_sessions}</div>
	</div>

	<div class="stat-card">
		<div class="stat-label">Total Trades</div>
		<div class="stat-value">{$globalStats.total_trades}</div>
	</div>

	<div class="stat-card">
		<div class="stat-label">Total PnL</div>
		<div class="stat-value" class:profit={$globalStats.total_pnl >= 0}>
			{$globalStats.total_pnl.toFixed(2)} USDT
		</div>
	</div>
</div>
```

---

## 🚀 Utilisation

### 1. Créer une session

```bash
# Via API
curl -X POST http://localhost:5000/api/sessions/create \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "btc_scalper",
    "name": "BTC Scalping",
    "pairs": ["BTC/USDT"],
    "strategy": "scalping",
    "config": {
      "max_position_size": 100,
      "stop_loss_percent": 2.0
    }
  }'
```

### 2. Démarrer une session

```bash
curl -X POST http://localhost:5000/api/sessions/btc_scalper/start
```

### 3. Interface Frontend

1. Cliquer sur "➕ New" dans SessionSelector
2. Entrer nom et paires
3. La session apparaît dans la liste
4. Cliquer pour sélectionner
5. Les données de la session active s'affichent

---

## 💡 Cas d'usage

### Cas 1: Stratégies différentes

```javascript
// Session 1: Scalping BTC
createSession({
	name: 'BTC Scalping',
	pairs: ['BTC/USDT'],
	strategy: 'scalping',
	config: { tp: 2%, sl: 1% }
});

// Session 2: Swing trading ETH
createSession({
	name: 'ETH Swing',
	pairs: ['ETH/USDT'],
	strategy: 'swing',
	config: { tp: 10%, sl: 5% }
});
```

### Cas 2: Multi-pairs

```javascript
// Session 1: Top 5 BTC pairs
createSession({
	name: 'BTC Majors',
	pairs: ['BTC/USDT', 'BTC/BUSD', 'BTC/EUR'],
	strategy: 'scalping'
});

// Session 2: Top 5 altcoins
createSession({
	name: 'Altcoins',
	pairs: ['ETH/USDT', 'SOL/USDT', 'AVAX/USDT'],
	strategy: 'momentum'
});
```

---

## ⚠️ Considérations

### Performance

- Chaque session = 1 processus asyncio
- Limite recommandée: **5-10 sessions simultanées**
- Monitorer CPU/RAM usage

### Risk Management

- Chaque session a son propre capital alloué
- PnL indépendant par session
- Position sizing par session

### Database

- Une table `sessions` pour persister les configs
- Une table `session_trades` pour les trades par session

```sql
CREATE TABLE sessions (
    session_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    pairs JSON NOT NULL,
    strategy VARCHAR NOT NULL,
    config JSON NOT NULL,
    status VARCHAR DEFAULT 'stopped',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE session_trades (
    trade_id SERIAL PRIMARY KEY,
    session_id VARCHAR REFERENCES sessions(session_id),
    symbol VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    entry DECIMAL NOT NULL,
    exit DECIMAL,
    pnl DECIMAL,
    opened_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP
);
```

---

## 🎯 Roadmap Implementation

1. **Phase 1**: Backend session_manager.py (2-3 jours)
2. **Phase 2**: API endpoints multi-sessions (1 jour)
3. **Phase 3**: Frontend stores + composants (2-3 jours)
4. **Phase 4**: Tests et optimisation (1-2 jours)

**Total: ~1 semaine** pour feature complète

---

## 📚 Ressources

- [Asyncio Tasks](https://docs.python.org/3/library/asyncio-task.html)
- [Svelte Stores](https://svelte.dev/docs#run-time-svelte-store)
- [Multi-threading in Python](https://realpython.com/intro-to-python-threading/)
