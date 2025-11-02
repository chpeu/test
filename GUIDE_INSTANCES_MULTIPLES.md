# 🔄 GUIDE: LANCER PLUSIEURS INSTANCES

**Question**: "Comment lancer plusieurs instances?"

---

## 🎯 PROBLÈME ACTUEL

Le code utilise **port 5000 fixe**:
```python
# main.py ligne 133
socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

**Une seule instance** peut tourner sur un port à la fois.

---

## ✅ SOLUTION 1: Ports Différents (Simple)

### **Modifier `main.py`**:
```python
import sys

# Récupérer le port depuis les arguments
port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

if __name__ == '__main__':
    logger.info(f"🚀 Trade Cursor v6.0 démarré sur port {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
```

### **Lancer plusieurs instances**:
```bash
# Terminal 1
python main.py 5000

# Terminal 2
python main.py 5001

# Terminal 3
python main.py 5002
```

**Accès**:
- http://localhost:5000 (Instance 1)
- http://localhost:5001 (Instance 2)
- http://localhost:5002 (Instance 3)

---

## ✅ SOLUTION 2: Fichier Config (Recommandé)

### **Créer `instances.json`**:
```json
{
  "instances": [
    {
      "name": "Instance 1",
      "port": 5000,
      "account_size": 1000,
      "use_atr": true
    },
    {
      "name": "Instance 2", 
      "port": 5001,
      "account_size": 500,
      "use_atr": false
    }
  ]
}
```

### **Modifier `config.py`**:
```python
import json

def load_instance_config(instance_id=0):
    """Charger config d'une instance"""
    with open('instances.json', 'r') as f:
        instances = json.load(f)
        return instances['instances'][instance_id]

# Usage
config = load_instance_config(0)  # Instance 0
account_size = config['account_size']
use_atr = config['use_atr']
```

### **Lancer**:
```bash
# Terminal 1
python main.py 0

# Terminal 2
python main.py 1
```

---

## ✅ SOLUTION 3: Script Batch Multi-Instances

### **Créer `lancer_multiples.bat`**:
```batch
@echo off
echo Lancement de 3 instances...

start "Instance 1 - Port 5000" python main.py 5000
timeout /t 2
start "Instance 2 - Port 5001" python main.py 5001
timeout /t 2
start "Instance 3 - Port 5002" python main.py 5002

echo Instances lancees!
echo.
echo http://localhost:5000 - Instance 1
echo http://localhost:5001 - Instance 2
echo http://localhost:5002 - Instance 3
```

Double-cliquer sur `lancer_multiples.bat` = 3 instances simultanées!

---

## ✅ SOLUTION 4: Docker Compose (Avancé)

### **Créer `docker-compose.yml`**:
```yaml
version: '3.8'

services:
  instance1:
    build: .
    ports:
      - "5000:5000"
    environment:
      - ACCOUNT_SIZE=1000
    command: python main.py 5000
  
  instance2:
    build: .
    ports:
      - "5001:5000"
    environment:
      - ACCOUNT_SIZE=500
    command: python main.py 5000
  
  instance3:
    build: .
    ports:
      - "5002:5000"
    environment:
      - ACCOUNT_SIZE=2000
    command: python main.py 5000
```

### **Lancer**:
```bash
docker-compose up -d
```

---

## 🎯 RECOMMANDATION

**Pour débuter**: **Solution 1 (Ports Différents)**
- Simple à implémenter
- Pas de fichiers supplémentaires
- Flexible

**Pour production**: **Solution 2 (Config)**
- Configuration centralisée
- Plus professionnel
- Évolutif

---

**Tu préfères quelle solution?**

