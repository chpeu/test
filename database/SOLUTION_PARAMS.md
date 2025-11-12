# Solution - Déséquilibre paramètres 128 vs 111

## Problème identifié
- **128 paramètres** dans le tuple `params`
- **111 placeholders** dans VALUES
- **17 paramètres en trop**

## D'après les logs
- Paramètre 13: `gross_pnl_usdt` (0.01)
- Paramètre 14: `pnl_pct` = `gross_pnl_pct` (0.07)
- Paramètre 15: `pnl_usdt` = `gross_pnl_usdt` (0.01) - **DOUBLON!**

## Solution immédiate
Le paramètre 15 (ligne 926) est un doublon de `gross_pnl_usdt`. Il faut le supprimer.

Mais il reste encore 16 paramètres en trop. Le problème est que le comptage manuel donne 127 paramètres, mais les logs indiquent 128. Il y a peut-être un paramètre supplémentaire quelque part, ou le comptage manuel est incorrect.

## Action
1. Supprimer le paramètre 15 (doublon de gross_pnl_usdt)
2. Vérifier le nombre de paramètres après suppression
3. Identifier les autres paramètres en trop si nécessaire

