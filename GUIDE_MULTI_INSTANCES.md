# 🔧 Guide Multi-Instances

**Comment gérer plusieurs instances du bot sur différents ports**

---

## 📋 VUE D'ENSEMBLE

Le bot supporte **plusieurs instances simultanées** sur différents ports. Chaque instance est **isolée** et fonctionne indépendamment.

**Avantages** :
- ✅ Tester différentes stratégies en parallèle
- ✅ Trader plusieurs paires simultanément
- ✅ Isoler les configurations par instance
- ✅ Éviter les conflits de données

---

## 🔧 ISOLATION PAR INSTANCE

### **1. Port HTTP**

Chaque instance écoute sur un **port différent** :

```bash
# Instance 1
python main.py 5000

# Instance 2
python main.py 5001

# Instance 3
python main.py 5002
```

**Accès** :
- Instance 1 : `http://localhost:5000`
- Instance 2 : `http://localhost:5001`
- Instance 3 : `http://localhost:5002`

---

### **2. Fichier Historique**

Chaque instance a son **propre fichier historique** :

```
trade_history_instance_5000.json  # Instance sur port 5000
trade_history_instance_5001.json  # Instance sur port 5001
trade_history_instance_5002.json  # Instance sur port 5002
```

**Code** : `main.py` ligne 85-89
```python
def get_trade_history_file():
    """Retourner le nom du fichier historique selon le port de l'instance"""
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    return f"trade_history_instance_{port}.json"
```

---

### **3. Base de Données Analytics**

Chaque instance a sa **propre base de données Analytics** :

```
analytics_instance_5000.db  # Instance sur port 5000
analytics_instance_5001.db  # Instance sur port 5001
analytics_instance_5002.db  # Instance sur port 5002
```

**Code** : `core/analytics_database.py` ligne 52
```python
self.instance_port = instance_port or 5000
# ...
db_path = f"analytics_instance_{self.instance_port}.db"
```

**Isolation** :
- ✅ Chaque instance a ses propres trades
- ✅ Chaque instance a ses propres stats
- ✅ Chaque instance a ses propres setups rejetés/validés
- ✅ Pas de conflit entre instances

---

### **4. SocketIO**

Chaque instance a son **propre serveur SocketIO** :

```python
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode='asgi')
socketio_app = socketio.ASGIApp(sio, app)
```

**Isolation** :
- ✅ Chaque instance gère ses propres connexions WebSocket
- ✅ Les événements SocketIO sont isolés par instance
- ✅ Pas de conflit entre instances

---

### **5. Session ID**

Chaque instance a un **session_id unique** :

**Code** : `main.py` ligne 869-871
```python
# Récupérer port instance pour multi-instances
port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
analytics_db = AnalyticsDatabase(db_path=ANALYTICS_DB_PATH, instance_port=port)
```

**Utilisation** :
- ✅ Identifie l'instance dans les logs Analytics
- ✅ Permet de filtrer les données par instance
- ✅ Permet d'agréger les données de toutes les instances

---

### **6. Configuration (TRADING_CONFIG)**

**Statut** : ⚠️ **Partagée entre instances**

**Problème** : `TRADING_CONFIG` dans `config.py` est **globale**, donc partagée entre toutes les instances.

**Impact** :
- Si une instance modifie `TRADING_CONFIG` via `/api/config`, **toutes les instances** sont affectées
- Les modifications sont **temporaires** (en mémoire) et **perdues au redémarrage**

**Solution recommandée** :
- Utiliser des **fichiers de config par instance** (futur)
- Ou documenter que les modifications `/api/config` affectent toutes les instances

---

### **7. État Application (app_state)**

**Statut** : ✅ **Isolé par instance**

**Code** : `main.py` ligne 202-214
```python
app_state = {
    'is_scanning': False,
    'active_position': None,
    'stats': {...},
    'top_pairs': [],
    'logs': [],
    'trade_history': []
}
```

**Isolation** :
- ✅ Chaque instance a son propre `app_state` en mémoire
- ✅ Chaque instance a sa propre position active
- ✅ Chaque instance a ses propres stats
- ✅ Chaque instance a ses propres top pairs

---

## 🚀 DÉMARRER PLUSIEURS INSTANCES

### **Méthode 1 : Terminaux Séparés**

**Windows PowerShell** :
```powershell
# Terminal 1
cd "C:\Users\sebta\Documents\code scalp\trade_cursor_py"
python main.py 5000

# Terminal 2
cd "C:\Users\sebta\Documents\code scalp\trade_cursor_py"
python main.py 5001

# Terminal 3
cd "C:\Users\sebta\Documents\code scalp\trade_cursor_py"
python main.py 5002
```

**Linux/Mac** :
```bash
# Terminal 1
python main.py 5000 &

# Terminal 2
python main.py 5001 &

# Terminal 3
python main.py 5002 &
```

---

### **Méthode 2 : Script de Démarrage**

Créer `start_instances.ps1` (Windows) :

```powershell
# Instance 1
Start-Process python -ArgumentList "main.py", "5000" -WorkingDirectory "C:\Users\sebta\Documents\code scalp\trade_cursor_py"

# Instance 2
Start-Process python -ArgumentList "main.py", "5001" -WorkingDirectory "C:\Users\sebta\Documents\code scalp\trade_cursor_py"

# Instance 3
Start-Process python -ArgumentList "main.py", "5002" -WorkingDirectory "C:\Users\sebta\Documents\code scalp\trade_cursor_py"
```

**Exécuter** :
```powershell
.\start_instances.ps1
```

---

## 📊 AGRÉGER LES DONNÉES MULTI-INSTANCES

### **Problème**

Chaque instance a sa propre base de données Analytics, donc les stats sont **séparées**.

### **Solution : Script d'Agrégation**

Créer `aggregate_instances.py` :

```python
"""
Agréger les données de toutes les instances
"""
from core.analytics_database import AnalyticsDatabase
import sqlite3

def aggregate_all_instances(ports=[5000, 5001, 5002]):
    """Agréger les stats de toutes les instances"""
    
    all_trades = []
    all_stats = {
        'total_trades': 0,
        'wins': 0,
        'losses': 0,
        'winrate': 0.0
    }
    
    for port in ports:
        try:
            db = AnalyticsDatabase(instance_port=port)
            trades = db.get_trades(limit=10000)
            all_trades.extend(trades)
            
            # Calculer stats
            if trades:
                total = len(trades)
                wins = sum(1 for t in trades if t.get('pnl_usdt', 0) > 0)
                losses = total - wins
                
                all_stats['total_trades'] += total
                all_stats['wins'] += wins
                all_stats['losses'] += losses
                
        except Exception as e:
            print(f"❌ Erreur instance {port}: {e}")
    
    # Calculer winrate global
    if all_stats['total_trades'] > 0:
        all_stats['winrate'] = (all_stats['wins'] / all_stats['total_trades']) * 100
    
    return all_stats, all_trades

if __name__ == '__main__':
    stats, trades = aggregate_all_instances([5000, 5001, 5002])
    print(f"📊 Stats globales multi-instances:")
    print(f"  Total trades: {stats['total_trades']}")
    print(f"  Wins: {stats['wins']}")
    print(f"  Losses: {stats['losses']}")
    print(f"  Winrate: {stats['winrate']:.2f}%")
```

**Exécuter** :
```bash
python aggregate_instances.py
```

---

## 🔍 VÉRIFIER L'ISOLATION

### **Test 1 : Fichiers Historiques**

```bash
# Vérifier que chaque instance a son propre fichier
ls trade_history_instance_*.json

# Résultat attendu :
# trade_history_instance_5000.json
# trade_history_instance_5001.json
# trade_history_instance_5002.json
```

### **Test 2 : Bases de Données Analytics**

```bash
# Vérifier que chaque instance a sa propre DB
ls analytics_instance_*.db

# Résultat attendu :
# analytics_instance_5000.db
# analytics_instance_5001.db
# analytics_instance_5002.db
```

### **Test 3 : Ports HTTP**

```bash
# Vérifier que chaque instance écoute sur son port
netstat -ano | findstr :5000
netstat -ano | findstr :5001
netstat -ano | findstr :5002
```

### **Test 4 : Positions Actives**

1. **Ouvrir position** sur instance 5000
2. **Vérifier** que l'instance 5001 n'a **pas** de position active
3. **Vérifier** que l'instance 5002 n'a **pas** de position active

---

## ⚠️ LIMITATIONS ACTUELLES

### **1. Configuration Partagée**

**Problème** : `TRADING_CONFIG` est partagée entre instances

**Impact** : Modifications `/api/config` affectent toutes les instances

**Solution future** : Fichiers de config par instance

---

### **2. Pas d'Agrégation Automatique**

**Problème** : Pas de vue globale des stats de toutes les instances

**Solution** : Script d'agrégation manuel (voir ci-dessus)

---

### **3. Logs Mélangés**

**Problème** : Les logs de toutes les instances sont mélangés dans la console

**Solution future** : Fichiers de logs par instance

---

## ✅ RÉSUMÉ

**Isolation complète** :
- ✅ Port HTTP (5000, 5001, 5002, etc.)
- ✅ Fichier historique (`trade_history_instance_{port}.json`)
- ✅ Base Analytics (`analytics_instance_{port}.db`)
- ✅ SocketIO (serveur par instance)
- ✅ État application (`app_state` par instance)
- ✅ Session ID (par instance)

**Partagé** :
- ⚠️ Configuration `TRADING_CONFIG` (modifications affectent toutes les instances)

**Bonnes pratiques** :
- ✅ Utiliser des ports différents (5000, 5001, 5002, etc.)
- ✅ Documenter quelle instance fait quoi
- ✅ Utiliser des configurations différentes par instance
- ✅ Agréger les données si besoin d'une vue globale

---

**Tout est isolé sauf la configuration ! 🎉**

