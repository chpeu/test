# PROCÉDURES DE MAINTENANCE - TRADE CURSOR V7.0
## Guide Opérationnel Architecture Modulaire

---

## 🔧 **MAINTENANCE QUOTIDIENNE**

### **Health Check Système (Daily 9h00)**
```bash
# 1. Status général
python scripts/health_check.py --full-report

# 2. Feature flags status
python -c "
from core.feature_flags import get_feature_flags_manager
ffm = get_feature_flags_manager()
print('Position Manager:', ffm.get_flag('use_testable_position_manager').rollout_percentage, '%')
print('Analyzer:', ffm.get_flag('use_testable_analyzer').rollout_percentage, '%') 
print('Scanner:', ffm.get_flag('use_testable_scanner').rollout_percentage, '%')
"

# 3. Performance check
python test_phase4_integration_rollout.py | grep "Success Rate"
# Target: >90%
```

### **Monitoring Dashboard (Continu)**
```python
# Consulter dashboard temps réel
from core.monitoring.scanner_phase3_dashboard import ScannerPhase3Dashboard
import asyncio

dashboard = ScannerPhase3Dashboard()
asyncio.run(dashboard.display_current_status())

# Alertes à surveiller:
# 🔥 CRITICAL: Error rate > 2%
# ⚠️ WARNING: Performance degradation > 15%
# 📊 INFO: Rollout progression updates
```

---

## 🚨 **PROCÉDURES D'URGENCE**

### **Rollback Immédiat**
```python
# Emergency rollback toutes phases
from core.feature_flags import get_feature_flags_manager

def emergency_rollback():
    ffm = get_feature_flags_manager()
    ffm.enable_flag('use_testable_position_manager', 0.0)
    ffm.enable_flag('use_testable_analyzer', 0.0)
    ffm.enable_flag('use_testable_scanner', 0.0)
    print("🚨 EMERGENCY ROLLBACK EXECUTED")

# Usage: python -c "exec(open('maintenance_procedures.py').read()); emergency_rollback()"
```

### **Incident Response**
```
🚨 INCIDENT WORKFLOW:
1. Assess impact (< 2min)
2. Rollback if critical (< 5min)  
3. Notify stakeholders (< 10min)
4. Investigate root cause
5. Implement fix
6. Post-mortem documentation
```

---

## 📈 **ROLLOUT PROGRESSIF**

### **Extension Scanner 25% → 50%**
```python
# Validation avant extension
python test_phase4_integration_rollout.py
# Require: Success Rate > 90%

# Extension rollout
from core.feature_flags import get_feature_flags_manager
ffm = get_feature_flags_manager()
ffm.enable_flag('use_testable_scanner', 50.0)

# Monitor 24h post-extension
python scripts/monitor_deployment.py --duration 1440
```

### **Finalisation 100% (Planifiée)**
```python
# Phase finale toutes composantes
ROLLOUT_FINAL = {
    'Position Manager': '75% → 100%',
    'Analyzer': '50% → 100%', 
    'Scanner': '25% → 100%'
}

# Execution sécurisée progressive
# Semaine 1: 75% → 90% Position Manager
# Semaine 2: 50% → 75% Analyzer  
# Semaine 3: 25% → 50% Scanner
# Semaine 4: Tout à 100%
```

---

## 🔍 **TROUBLESHOOTING GUIDE**

### **Performance Issues**
```bash
# 1. Cache performance
python scripts/check_cache_performance.py
# Target: Hit rate >80%

# 2. Component bottlenecks  
python scripts/analyze_component_performance.py
# Identify slow components

# 3. Temporary rollout reduction
# Reduce rollout percentage problematic component
```

### **Integration Failures**
```python
# Cross-component validation
python test_phase4_integration_rollout.py --verbose
# Analyze failing test details

# Component isolation testing
from core.factories.position_factory import get_configured_position_factory
factory = get_configured_position_factory("production")
# Test individual components
```

---

## 📋 **MAINTENANCE CHECKLIST**

### **Weekly Tasks**
- [ ] Health check complet système
- [ ] Performance benchmarks validation  
- [ ] Feature flags review et ajustement
- [ ] Tests intégration full suite
- [ ] Documentation updates si nécessaire
- [ ] Security patches application
- [ ] Database maintenance et optimization

### **Monthly Tasks**  
- [ ] Architecture review et amélioration continue
- [ ] Performance optimization initiatives
- [ ] Rollout progression evaluation
- [ ] Team training et knowledge sharing
- [ ] Backup/recovery procedures testing
- [ ] Monitoring dashboards enhancement
- [ ] Legacy deprecation progress

---

## 🎯 **SUCCESS METRICS**

```
KPIs MAINTENANCE:
✅ System Uptime: >99.9%
✅ Test Success Rate: >90%
✅ Performance: No regression >10%
✅ Rollout Progression: On schedule
✅ Incident Resolution: <4h MTTR
```

---

*Maintenance Guide v7.0 - Trade Cursor Architecture*  
*Dernière MAJ: 23 Janvier 2026*  
*Status: Production Ready*
