# ✅ RÉSUMÉ : SEUILS CONFIGURABLES

**Trade Cursor v6.1**

---

## 🎯 RÉPONSE À TON QUESTION

**"Est-il possible d'implémenter des seuils modifiables à la volée (sur la page HTML) et quels sont les seuils les plus pertinents ?"**

**Réponse**: Oui, c’est fait. 4 seuils ajoutés dans l’interface HTML.

---

## 🎚️ 4 SEUILS CONFIGURABLES

### 1️⃣ **SNR** (Signal-to-Noise Ratio)
- **Plage**: 0.1-1.0
- **Défaut**: 0.3
- **Effet**: Plus bas = plus de trades

### 2️⃣ **Breakout**
- **Plage**: 0.1-1.0
- **Défaut**: 0.3
- **Effet**: Plus bas = moins de trades

### 3️⃣ **Wick Ratio**
- **Plage**: 1.5-5.0
- **Défaut**: 2.5
- **Effet**: Plus bas = plus strict

### 4️⃣ **DI Gap**
- **Plage**: 3.0-10.0
- **Défaut**: 5.0
- **Effet**: Plus bas = plus de trades

---

## 📍 OÙ TROUVER

Ouvre http://localhost:5000. Section **"⚙️ SEUILS PHASE 1+2 (Configurables)"**, juste avant **"🔍 SCANNER LES PAIRES"**.

---

## ⚠️ STATUS

**✅ Complété**:
- Sliders UI
- Variables JS
- Backend config
- Docs

**🔄 Reste à faire**:
- Liaison frontend ↔ backend si passage à Python 100%
- Activation JS si tu restes en HTML/JS pur

---

## 💡 COMMENT LES UTILISER

### **Trop peu de trades ?**
```
SNR: 0.3 → 0.2
Breakout: 0.3 → 0.2
Wick: 2.5 → 3.0
DI Gap: 5.0 → 4.0
```

### **Trop de faux signaux ?**
```
SNR: 0.3 → 0.4
Breakout: 0.3 → 0.4
Wick: 2.5 → 2.0
DI Gap: 5.0 → 6.0
```

---

## 📊 HIÉRARCHIE IMPORTANCE

**Pour toi (scalping crypto):**
1. **SNR** — impact fort
2. **Breakout** — impact moyen+
3. **Wick Ratio** — impact moyen
4. **DI Gap** — impact faible

---

**Date**: 2025-11-02  
**Commits**: 35d6ec6 + d5503ac  
**Fichiers**: `templates/index.html`, `config.py`, `core/analyzer.py`

