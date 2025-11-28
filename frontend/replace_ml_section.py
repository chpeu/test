#!/usr/bin/env python3
"""Script pour remplacer la section ML dans VariablesPanel.svelte"""

import re

# Lire le fichier original
with open(r'src\lib\components\VariablesPanel.svelte', 'r', encoding='utf-8') as f:
    content = f.read()

# Lire le nouveau contenu ML
with open(r'ML_SECTION_NEW.svelte', 'r', encoding='utf-8') as f:
    new_ml = f.read()

# Retirer la première ligne de commentaire et garder juste le contenu
new_ml = new_ml.replace('<!-- ONGLET MACHINE LEARNING - VERSION RÉORGANISÉE -->\n', '')

# Pattern pour trouver toute la section ML (de "<!-- ONGLET MACHINE LEARNING -->" jusqu'au {/if})
# On utilise DOTALL pour matcher sur plusieurs lignes
pattern = r'(\t<!-- ONGLET MACHINE LEARNING -->.*?^\t\{/if\}\n)'

# Remplacer
content_new = re.sub(pattern, '\t' + new_ml, content, flags=re.MULTILINE | re.DOTALL)

# Sauvegarder
with open(r'src\lib\components\VariablesPanel.svelte', 'w', encoding='utf-8') as f:
    f.write(content_new)

print("Section ML remplacee avec succes!")
print("   - 3 nouveaux parametres ajoutes (colsample_bylevel, gamma, scale_pos_weight)")
print("   - Metriques deplacees apres Filtrage ML")
print("   - Historique des optimisations deplace avant Hyperparametres")
print("   - Panel d'optimisation en derniere position")
