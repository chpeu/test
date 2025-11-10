# 📚 Index Documentation Complète - Trade Cursor v7.0

Navigation centralisée pour toute la documentation du projet.

---

## 🚀 DÉMARRAGE RAPIDE

| Document | Description | Audience |
|----------|-------------|----------|
| [README.md](../README.md) | Vue d'ensemble du projet | Tous |
| [DEMARRAGE_RAPIDE.md](../DEMARRAGE_RAPIDE.md) | Quick start guide | Débutants |
| [GUIDE_UTILISATION_RAPIDE.md](../GUIDE_UTILISATION_RAPIDE.md) | Guide d'utilisation rapide | Utilisateurs |
| [GUIDE_INSTALLATION_V66.md](../GUIDE_INSTALLATION_V66.md) | Guide d'installation complet | DevOps |

---

## 📡 WEBSOCKET & ARCHITECTURE

| Document | Description | Taille |
|----------|-------------|--------|
| [WEBSOCKET_API.md](../WEBSOCKET_API.md) | **API WebSocket complète** - 10 commandes, 11 événements | 11K |
| [WEBSOCKET_ARCHITECTURE.md](../WEBSOCKET_ARCHITECTURE.md) | **Architecture avec diagrammes ASCII** | 29K |
| [OBSOLETE_FILES.md](../OBSOLETE_FILES.md) | Liste fichiers obsolètes (Socket.IO, templates HTML) | 4K |

**Contenu WEBSOCKET_API.md**:
- Format des messages (command, response, event)
- 10 commandes WebSocket (start_scanner, get_config, update_config, etc.)
- 11 événements temps réel (status, config_updated, sessions_update, etc.)
- Gestion d'erreurs (timeout, rate limit, retry)
- Métriques & monitoring
- Exemples d'utilisation TypeScript
- Table de migration REST → WebSocket

**Contenu WEBSOCKET_ARCHITECTURE.md**:
- Diagrammes ASCII architecture complète
- Flow de communication bidirectionnelle
- Séquences commande/réponse/événement
- Mécanismes (retry, rate limiting, queue overflow)
- Comparaison performance (REST vs WebSocket: -87.5% bande passante)
- Couches de sécurité

---

## 🔧 GUIDES CONFIGURATION

| Document | Description | Audience |
|----------|-------------|----------|
| [GUIDE_TELEGRAM.md](../GUIDE_TELEGRAM.md) | Configuration notifications Telegram | Utilisateurs |
| [GUIDE_MULTI_INSTANCES.md](../GUIDE_MULTI_INSTANCES.md) | Déploiement multi-instances | DevOps |
| [GUIDE_DOCKER_WINDOWS.md](../GUIDE_DOCKER_WINDOWS.md) | Docker sous Windows | Windows Users |
| [README_WINDOWS.md](../README_WINDOWS.md) | Guide spécifique Windows | Windows Users |
| [README_ARCHITECTURE_V2.md](../README_ARCHITECTURE_V2.md) | Architecture V2 détaillée | Développeurs |

---

## 📖 DOCUMENTATION TECHNIQUE

### Calculs & Indicateurs
| Document | Description | Taille |
|----------|-------------|--------|
| [CALCUL_FRAIS_SLIPPAGE.md](technical/CALCUL_FRAIS_SLIPPAGE.md) | Calcul frais et slippage MEXC | 9K |
| [CALCUL_PNL.md](technical/CALCUL_PNL.md) | Calcul PnL positions | 5.5K |
| [EXPLICATION_PATTERNS_SETUPS.md](technical/EXPLICATION_PATTERNS_SETUPS.md) | Patterns de trading détaillés | 6K |

### Configuration
| Document | Description | Taille |
|----------|-------------|--------|
| [GUIDE_VERIFICATION_PARAMETRES.md](technical/GUIDE_VERIFICATION_PARAMETRES.md) | Vérification paramètres système | 5.7K |
| [LISTE_PARAMETRES_47.md](technical/LISTE_PARAMETRES_47.md) | Liste complète des 47 paramètres | 13K |

---

## 📱 GUIDES UTILISATEUR

| Document | Description | Taille |
|----------|-------------|--------|
| [ACCES_IPHONE.md](guides/ACCES_IPHONE.md) | Accès interface depuis iPhone | 4K |

---

## 🗂️ ARCHIVES

### Migration WebSocket (8 fichiers)
📂 [archive/websocket-migration/](archive/websocket-migration/)

Documentation historique de la migration Socket.IO → WebSocket natif (Oct-Nov 2025):
- WEBSOCKET_NATIVE_MIGRATION.md (17K) - Guide complet migration
- WEBSOCKET_BIDIRECTIONNEL.md (26K) - Implémentation bidirectionnelle
- WEBSOCKET_IMPLEMENTATION_GUIDE.md (6K) - Guide implémentation
- WEBSOCKET_MIGRATION_STATUS.md (5K) - État migration
- WEBSOCKET_MIGRATION_COMPLETE.md (5K) - Confirmation complète
- WEBSOCKET_IMPROVEMENTS.md (14K) - Améliorations proposées
- WEBSOCKET_NATIVE_EXAMPLES.md (20K) - Exemples d'utilisation
- WEBSOCKET_ARCHITECTURE.md (15K) - Architecture v1 (ancienne)

**Statut**: ✅ Migration 100% terminée - Fichiers archivés pour historique uniquement

### Développement Historique (28 fichiers)
📂 [archive/development/](archive/development/)

Documentation historique du développement:
- **Phases**: PHASE1_COMPLETE.md, PHASE1_TESTS.md, DOCUMENTATION_PHASE_8.md
- **Corrections**: CORRECTIONS_COMPLETED.md, CORRECTIONS_FINALES.md, CORRECTIFS_DEPLOIEMENT.md
- **Migrations**: MIGRATION_SVELTE.md, MIGRATION_SVELTE5.md
- **Refactoring**: REFACTORING_SUMMARY.md, REFACTORING_GUIDE.md
- **Analyses**: ANALYSE_DETAILLEE.md, COVERAGE_REPORT.md, ARCHITECTURE_COMPARISON.md
- **Frontend**: FRONTEND_STATUS_UPDATE.md, FRONTEND_CORRECTIONS_STATUS.md
- **Workflow**: WORKFLOW_PR.md, PR_EXPLANATION.md
- **Déploiement**: PRODUCTION_DEPLOYMENT.md, DEPLOIEMENT_CORRIGE.md
- Et 10+ autres fichiers historiques

**Statut**: Archivé - Conservation pour traçabilité uniquement

### Résumés de Développement (40 fichiers)
📂 [archive/resume/](archive/resume/)

Résumés quotidiens et par phase du développement (RESUME_*.md)

### Corrections Historiques (26 fichiers)
📂 [archive/fix/](archive/fix/)

Documentation des bugs corrigés et patches appliqués (FIX_*.md)

### Analyses Techniques (16 fichiers)
📂 [archive/analyse/](archive/analyse/)

Analyses détaillées de problèmes, risques et architectures (ANALYSE_*.md)

### Documentation Diverse (69 fichiers)
📂 [archive/autres/](archive/autres/)

Guides secondaires, implémentations détaillées, plans et propositions

**Total archivé**: 159 fichiers (151 initiaux + 8 WebSocket migration)

---

## 🎯 DOCUMENTATION PAR CAS D'USAGE

### Je veux démarrer le bot
1. [DEMARRAGE_RAPIDE.md](../DEMARRAGE_RAPIDE.md) - Installation et premier lancement
2. [GUIDE_INSTALLATION_V66.md](../GUIDE_INSTALLATION_V66.md) - Installation complète
3. [GUIDE_UTILISATION_RAPIDE.md](../GUIDE_UTILISATION_RAPIDE.md) - Utilisation de base

### Je veux comprendre l'architecture
1. [README.md](../README.md) - Vue d'ensemble v7.0
2. [WEBSOCKET_ARCHITECTURE.md](../WEBSOCKET_ARCHITECTURE.md) - Architecture WebSocket
3. [README_ARCHITECTURE_V2.md](../README_ARCHITECTURE_V2.md) - Architecture V2 détaillée

### Je veux développer/contribuer
1. [WEBSOCKET_API.md](../WEBSOCKET_API.md) - API complète avec exemples
2. [WEBSOCKET_ARCHITECTURE.md](../WEBSOCKET_ARCHITECTURE.md) - Diagrammes techniques
3. Frontend: `frontend/src/lib/utils/websocket-impl.ts` - Client WebSocket TypeScript
4. Backend: `main.py` - Endpoint WebSocket + commandes
5. Backend: `core/websocket_manager.py` - Gestionnaire WebSocket

### Je veux configurer les notifications
1. [GUIDE_TELEGRAM.md](../GUIDE_TELEGRAM.md) - Configuration Telegram complète

### Je veux comprendre les calculs
1. [CALCUL_PNL.md](technical/CALCUL_PNL.md) - Calculs PnL
2. [CALCUL_FRAIS_SLIPPAGE.md](technical/CALCUL_FRAIS_SLIPPAGE.md) - Frais et slippage
3. [EXPLICATION_PATTERNS_SETUPS.md](technical/EXPLICATION_PATTERNS_SETUPS.md) - Patterns trading

### Je veux déployer en production
1. [GUIDE_MULTI_INSTANCES.md](../GUIDE_MULTI_INSTANCES.md) - Multi-instances
2. [GUIDE_DOCKER_WINDOWS.md](../GUIDE_DOCKER_WINDOWS.md) - Docker sous Windows

### Je cherche l'historique du projet
1. [archive/websocket-migration/](archive/websocket-migration/) - Migration WebSocket
2. [archive/development/](archive/development/) - Développement historique
3. [archive/resume/](archive/resume/) - Résumés chronologiques
4. [archive/fix/](archive/fix/) - Corrections historiques

---

## 📊 STATISTIQUES DOCUMENTATION

### Documentation Active
- **Guides essentiels**: 12 fichiers (~90K)
- **Documentation technique**: 5 fichiers (~40K)
- **Guides utilisateur**: 1 fichier (~4K)
- **Total actif**: 18 fichiers (~134K)

### Archives
- **Migration WebSocket**: 8 fichiers (~107K)
- **Développement**: 28 fichiers
- **Résumés**: 40 fichiers
- **Corrections**: 26 fichiers
- **Analyses**: 16 fichiers
- **Autres**: 69 fichiers
- **Total archivé**: 187 fichiers

### Organisation
```
docs/
├── DOCUMENTATION_INDEX.md (ce fichier)
├── technical/ (5 fichiers - 40K)
├── guides/ (1 fichier - 4K)
└── archive/
    ├── websocket-migration/ (8 fichiers - 107K)
    ├── development/ (28 fichiers)
    ├── resume/ (40 fichiers)
    ├── fix/ (26 fichiers)
    ├── analyse/ (16 fichiers)
    └── autres/ (69 fichiers)
```

---

## 🔍 RECHERCHE RAPIDE

### Par Technologie
- **WebSocket**: WEBSOCKET_API.md, WEBSOCKET_ARCHITECTURE.md
- **FastAPI**: README.md, main.py
- **Svelte**: README.md, frontend/
- **TypeScript**: websocket-impl.ts, WEBSOCKET_API.md
- **Python**: README.md, core/, api/
- **Telegram**: GUIDE_TELEGRAM.md
- **Docker**: GUIDE_DOCKER_WINDOWS.md

### Par Thème
- **Installation**: DEMARRAGE_RAPIDE.md, GUIDE_INSTALLATION_V66.md
- **Configuration**: GUIDE_TELEGRAM.md, LISTE_PARAMETRES_47.md
- **Trading**: EXPLICATION_PATTERNS_SETUPS.md, CALCUL_PNL.md
- **Déploiement**: GUIDE_MULTI_INSTANCES.md, GUIDE_DOCKER_WINDOWS.md
- **Développement**: WEBSOCKET_API.md, WEBSOCKET_ARCHITECTURE.md
- **Historique**: archive/

---

## 🆕 DERNIERS AJOUTS

**10 Novembre 2025**:
- ✅ WEBSOCKET_API.md - API complète WebSocket
- ✅ WEBSOCKET_ARCHITECTURE.md - Architecture v2 avec diagrammes
- ✅ OBSOLETE_FILES.md - Liste fichiers obsolètes
- ✅ docs/archive/websocket-migration/ - Archive migration WebSocket
- ✅ docs/archive/development/ - Archive développement
- ✅ README.md mis à jour (WebSocket v7.0)
- ✅ DOCUMENTATION_INDEX.md (ce fichier)

---

## 📞 SUPPORT

Pour toute question sur la documentation:
1. Consultez d'abord cet index
2. Lisez le document approprié
3. Vérifiez les archives si nécessaire
4. Consultez le code source (main.py, websocket-impl.ts)

---

**Dernière mise à jour**: 10 Novembre 2025
**Version documentation**: v7.0
**Maintenu par**: Équipe Trade Cursor
**Branche**: claude/fix-multiple-errors-011CUycbZyp8U3cuy4HYLNWy
