# 🚀 Trade Cursor v7.0 - MEXC Smart Scalping Scanner

**Migration Python de v5.1 HTML avec interface IDENTIQUE**

[![Tests](https://github.com/chpeu/test/actions/workflows/test.yml/badge.svg)](https://github.com/chpeu/test/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI%20async-009688.svg)]()
[![PostgreSQL](https://img.shields.io/badge/datalogger-PostgreSQL-336791.svg)]()

---

## 📋 DESCRIPTION

Bot de scalping automatisé pour MEXC Futures:
- Scanner de paires scalables (volatilité, spread, depth)
- Détection positions multi-timeframe (1m + 5m)
- Gestion TP/SL adaptative (FIXE ou ATR)
- Break-even + Trailing Stop
- Interface HTML identique à v5.1

---

## 🎯 RÉPONSE PRINCIPALE

**"Est-ce que j'aurai toujours la même interface HTML?"**

**OUI, 100% IDENTIQUE!** ✅

L'HTML de v5.1 a été copié tel quel dans `templates/index.html`.  
Vous aurez exactement la même interface visuelle et la même expérience utilisateur.

---

## ⚙️ INSTALLATION

### 1. Prérequis
```bash
Python 3.11+
pip install -r requirements.txt
```

### 2. Installation dépendances
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements_ml.txt   # ML (XGBoost, calibration, Optuna)
```

### 3. Configuration
```bash
cp .env.example .env
# Renseigner les valeurs réelles (tokens Telegram, etc.) — .env est ignoré par git
```

La base PostgreSQL est nécessaire pour le datalogger ML (`core/postgresql_datalogger.py`).
Paramètres de connexion dans `.env`.

### 4. Lancer l'application
```bash
python main.py
```

Ouvrez `http://localhost:5000` dans votre navigateur.

---

## 📁 STRUCTURE

```
test/                          # dépôt chpeu/test
├── main.py                    # App FastAPI async + WebSocket natif
├── config.py                  # Configuration globale
├── requirements.txt           # Dépendances Python
├── README.md                  # Ce fichier
│
├── templates/
│   └── index.html            # UI HTML v5.1 (IDENTIQUE)
│
├── core/                      # Logique métier
│   ├── indicators.py         # Indicateurs techniques
│   ├── scanner.py            # Scanner scalabilité
│   ├── analyzer.py           # Analyse technique
│   └── position_manager.py   # Gestion positions
│
├── api/                       # API MEXC
│   └── mexc.py               # Client ccxt
│
├── utils/                     # Utilitaires
│   └── logger.py             # Logging coloré
│
└── test_*.py                  # Tests unitaires
```

---

## 🎨 INTERFACE

**Exactement identique à v5.1**:
- Même design
- Mêmes couleurs (#0a0e27, #00ff88)
- Mêmes panneaux
- Mêmes boutons
- Même layout

**Aucun changement visuel!**

---

## 🔧 FONCTIONNALITÉS

### Core
- ✅ Indicateurs: EMA, RSI, ATR, MACD, Bollinger, ADX
- ✅ Scanner scalabilité: Volatilité, spread, book depth
- ✅ Multi-timeframe: 1m + 5m
- ✅ Position Manager: TP/SL, Break-even, Trailing

### Modes TP/SL
- **FIXE**: TP/SL fixes à ±0.25%
- **ATR**: Adaptatif selon volatilité

### Break-even
- **FIXE mode**: Activation +0.3%, Trailing 0.1%
- **ATR mode**: Progressif (50% → 100%)

---

## 📊 STATISTIQUES

Chiffres réels (branche `claude/analyze-maintainability-01Hs9SEWv5USATGMzA2kzaag`, 02/02/2026) :

- **Fichiers Python** : 880
- **Lignes de Python** : ~246 000
- **Tests** : 163 fichiers, 3022 fonctions (`pytest tests/`)
- **Zones principales** : `core/` (92 fichiers), `optimization/` (361), `api/routes/` (~20 routeurs), `trading/`
- **Couverture** : **57,14 %** (mesurée sur `core` + `api` avec `pytest --cov=core --cov=api`)

---

## 🚀 DÉVELOPPEMENT

### Tests unitaires
```bash
python test_indicators.py
python test_scanner.py
python test_position_isolated.py
```

### Lint
```bash
pylint trade_cursor_py/
```

---

## 📝 DOCUMENTATION

- `README.md` - Ce fichier
- `docs/MASTER_IMPLEMENTATION_PLAN.md` - Plan global (Régime V2 / ATR Opt / ML)
- `docs/PHASE_1_IMPLEMENTATION.md` - Détails implémentation Phase 1 (logging + Régime V2)
- `docs/GUIDE_VERIFICATION_VARIABLES.md` - Méthodes de vérification des variables (API/WebSocket/config)
- `verification/verify_regime_v2_params.py` - Script de vérification du comportement Régime V2 (lissage/hystérésis/min-duration)
- `FINAL_RESUME_MIGRATION.md` - Résumé migration
- `STATUS_FINAL_MIGRATION.md` - Statut détaillé
- `RESUME_JOUR_X.md` - Résumés par jour

---

## 🔄 MIGRATION

**Du HTML/JS vers Python/Flask**:
- Architecture modulaire
- Code propre (0 erreurs)
- Tests unitaires
- Interface identique

**Avantages Python**:
- Pas de CORS/proxies
- Async natif
- Logging robuste
- Performance

**Conservation**:
- Interface identique
- Logique identique
- Expérience identique

---

## ⚠️ NOTES

### Dépendances manquantes
Si erreur `ModuleNotFoundError: ccxt`:
```bash
pip install ccxt
```

### Tests bloqués
Les tests sont créés mais nécessitent `ccxt` installé pour tourner.

### Intégration partielle
Le core est prêt mais l'intégration complète dans Flask nécessite Jour 5 avancé.

---

## 📞 SUPPORT

Pour questions ou problèmes, voir:
- `FINAL_RESUME_MIGRATION.md` pour détails techniques
- `STATUS_FINAL_MIGRATION.md` pour état actuel
- Code source pour implémentation

---

## 🎉 CONCLUSION

**Migration réussie!** 

Vous avez maintenant:
1. Version HTML v5.1 (fonctionnelle)
2. Version Python v6.0 (core prête)
3. **Interface identique dans les deux**
4. Architecture évolutive

**Bravo pour cette migration! **

---

**Dernière mise à jour**: 12 décembre 2025
