# 🚀 Plan d'Action Concret - Amélioration Coverage 66% → 80%+

**Date de création:** 2025-11-10
**Coverage actuel:** 66.30%
**Objectif:** 80%+
**Temps estimé:** 12-15h

---

## 📅 Planning par Journée

### **Jour 1: Quick Wins (3-4h)** → Target: 70%

#### Session 1 (2h): Tests routes simples
```bash
# 1. Créer structure tests routes
mkdir -p tests/api
touch tests/api/__init__.py
touch tests/api/test_routes_health.py

# 2. Installer httpx si pas déjà fait
pip install httpx

# 3. Créer tests pour routes simples (health, status, etc.)
# Voir REFACTORING_EXAMPLES.md pour exemples

# 4. Run tests
pytest tests/api/test_routes_health.py -v --cov=api/routes
```

**Fichiers à créer:**
- `tests/api/test_routes_health.py` (30 lignes)
- Tests pour `/health`, `/status`, `/config`

**Gain estimé:** +1.5%

#### Session 2 (1-2h): Compléter reliability tests
```bash
# 1. Créer tests circuit breaker
touch tests/test_reliability_circuit_breaker.py

# 2. Créer tests retry logic
touch tests/test_reliability_retry.py

# 3. Run tests
pytest tests/test_reliability*.py -v --cov=api/reliability
```

**Fichiers à créer:**
- `tests/test_reliability_circuit_breaker.py` (40 lignes)
- `tests/test_reliability_retry.py` (30 lignes)

**Gain estimé:** +1.5%

**Total Jour 1:** 66.30% + 3.0% = **69.30%**

---

### **Jour 2: Refactorisation Analyzer (4-5h)** → Target: 74%

#### Session 1 (2h): Extraire VolumeAnalyzer
```bash
# 1. Créer nouveau module
touch core/analyzer/volume_analyzer.py
touch tests/test_volume_analyzer.py

# 2. Copier code de check_volume_quality vers VolumeAnalyzer
# Voir REFACTORING_EXAMPLES.md

# 3. Modifier analyzer.py pour utiliser VolumeAnalyzer
# self.volume_analyzer = VolumeAnalyzer()
# result = self.volume_analyzer.check_quality(...)

# 4. Créer tests complets
# 6 tests minimum (voir exemples)

# 5. Run tests
pytest tests/test_volume_analyzer.py -v --cov=core/analyzer/volume_analyzer
```

**Gain estimé:** +0.3%

#### Session 2 (2-3h): Refactoriser analyze_timeframe
```bash
# 1. Backup analyzer.py
cp core/analyzer.py core/analyzer.py.backup

# 2. Extraire méthodes privées:
# - _fetch_market_data()
# - _calculate_indicators()
# - _apply_filters()
# - _generate_signals()
# - _calculate_score()
# - _build_result()

# 3. Créer tests pour chaque méthode
touch tests/test_analyzer_pipeline.py

# 4. Run tests
pytest tests/test_analyzer_pipeline.py -v --cov=core/analyzer
```

**Gain estimé:** +5.0%

**Total Jour 2:** 69.30% + 5.3% = **74.60%**

---

### **Jour 3: Routes FastAPI avec DI (5-6h)** → Target: 80%+

#### Session 1 (2h): Setup Dependency Injection
```bash
# 1. Créer fichier dependencies
touch api/dependencies.py

# 2. Ajouter fonctions get_*():
# - get_analyzer()
# - get_position_manager()
# - get_client()

# 3. Modifier routes pour utiliser Depends()
# Voir REFACTORING_EXAMPLES.md

# 4. Test manuel
curl http://localhost:8000/analyze -X POST -d '{"symbol":"BTC/USDT:USDT"}'
```

#### Session 2 (3-4h): Tests routes complètes
```bash
# 1. Créer tests pour chaque groupe de routes
touch tests/api/test_routes_trading.py
touch tests/api/test_routes_analytics.py
touch tests/api/test_routes_scanner.py
touch tests/api/test_routes_dashboard.py

# 2. Utiliser TestClient + dependency_overrides
# app.dependency_overrides[get_analyzer] = lambda: mock_analyzer

# 3. Run tests
pytest tests/api/ -v --cov=api/routes --cov=api/routes/
```

**Fichiers à créer:**
- `api/dependencies.py` (50 lignes)
- `tests/api/test_routes_trading.py` (100+ lignes)
- `tests/api/test_routes_analytics.py` (80 lignes)
- `tests/api/test_routes_scanner.py` (60 lignes)
- `tests/api/test_routes_dashboard.py` (80 lignes)

**Gain estimé:** +8.0%

**Total Jour 3:** 74.60% + 8.0% = **82.60%** ✅ (Objectif dépassé!)

---

## 🎯 Checklist de Validation

### Avant chaque session
- [ ] Git pull pour sync
- [ ] Créer branche feature si besoin
- [ ] Vérifier tests existants passent

### Pendant le développement
- [ ] Écrire tests AVANT le code (TDD)
- [ ] Commit atomiques fréquents
- [ ] Run tests après chaque changement
- [ ] Vérifier coverage augmente

### Après chaque session
- [ ] All tests pass (pytest tests/)
- [ ] Coverage a augmenté
- [ ] Code review rapide
- [ ] Push vers remote
- [ ] Mettre à jour ce document

---

## 📊 Suivi de Progression

| Jour | Session | Tâche | Temps | Coverage | Status |
|------|---------|-------|-------|----------|--------|
| 1 | 1 | Routes health | 2h | 67.8% | ⏳ TODO |
| 1 | 2 | Reliability tests | 1.5h | 69.3% | ⏳ TODO |
| 2 | 1 | VolumeAnalyzer | 2h | 69.6% | ⏳ TODO |
| 2 | 2 | Analyzer pipeline | 3h | 74.6% | ⏳ TODO |
| 3 | 1 | DI Setup | 2h | 74.6% | ⏳ TODO |
| 3 | 2 | Routes tests | 4h | 82.6% | ⏳ TODO |

**Légende:**
- ⏳ TODO
- 🔄 IN PROGRESS
- ✅ DONE
- ❌ BLOCKED

---

## 🛠️ Commandes Utiles

### Vérifier coverage d'un module
```bash
pytest tests/test_MODULE.py --cov=core/MODULE --cov-report=term-missing -v
```

### Vérifier coverage global
```bash
pytest tests/ --cov=core --cov=api --cov-report=term-missing -q
```

### Identifier lignes non couvertes
```bash
pytest tests/ --cov=core/analyzer --cov-report=html
open htmlcov/index.html
```

### Run tests en mode watch
```bash
pip install pytest-watch
ptw -- tests/ --cov=core --cov=api
```

### Générer rapport coverage détaillé
```bash
pytest tests/ --cov=core --cov=api --cov-report=html --cov-report=term
```

---

## 🐛 Troubleshooting

### Tests échouent après refactoring
```bash
# 1. Vérifier imports
python -c "from core.analyzer import TechnicalAnalyzer; print('OK')"

# 2. Restaurer backup si besoin
cp core/analyzer.py.backup core/analyzer.py

# 3. Relancer tests progressivement
pytest tests/test_analyzer.py::TestClass::test_method -v
```

### Coverage n'augmente pas
```bash
# 1. Vérifier que les nouveaux tests s'exécutent
pytest tests/test_NEW.py -v

# 2. Vérifier les lignes testées
pytest tests/ --cov=MODULE --cov-report=annotate
cat MODULE.py,cover
```

### Dependency injection ne fonctionne pas
```bash
# 1. Vérifier que la dépendance est bien déclarée
grep -n "Depends" api/routes.py

# 2. Vérifier l'override dans les tests
grep -n "dependency_overrides" tests/api/

# 3. Cleanup après tests
app.dependency_overrides.clear()
```

---

## 📈 Métriques de Succès

### Objectifs quantitatifs
- ✅ Coverage ≥ 80%
- ✅ Tests ≥ 700
- ✅ Modules 100% ≥ 10
- ✅ Modules <50% = 0
- ✅ CI/CD passe (exit code 0)

### Objectifs qualitatifs
- Code plus modulaire et testable
- Dépendances injectées plutôt que globales
- Méthodes < 50 lignes
- Classes avec responsabilité unique
- Documentation à jour

---

## 🎓 Ressources

### Documentation
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest Fixtures](https://docs.pytest.org/en/latest/fixture.html)
- [Coverage.py](https://coverage.readthedocs.io/)
- [Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)

### Exemples dans le projet
- `REFACTORING_EXAMPLES.md` - Code examples
- `REFACTORING_ANALYSIS.md` - Stratégie complète
- `tests/test_analytics_logger.py` - Exemple tests complets 100%
- `tests/test_analyzer_filters.py` - Exemple tests avec mocks

---

## 📝 Notes de Session

### Session X - Date
**Objectif:**

**Réalisé:**
- [ ] Task 1
- [ ] Task 2

**Coverage:** Before → After

**Problèmes rencontrés:**

**Solutions:**

**Next steps:**

---

## ✅ Validation Finale

Avant de merger dans main:
- [ ] Coverage ≥ 80%
- [ ] All tests pass (0 failed)
- [ ] CI/CD green
- [ ] Code review done
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Git tags created

---

**Dernière mise à jour:** 2025-11-10
**Responsable:** Claude AI
**Status:** 📋 READY TO START
