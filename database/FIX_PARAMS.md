# Fix - Déséquilibre paramètres 128 vs 111

## Problème confirmé
- **111 placeholders** dans VALUES ✓
- **128 paramètres** dans tuple params (d'après les logs)
- **17 paramètres en trop**

## Solution
Le paramètre 15 (ligne 926) est un doublon de `gross_pnl_usdt`. Il faut le supprimer.

Mais il reste encore 16 paramètres en trop. Le problème est que le comptage manuel donne 127 paramètres, mais les logs indiquent 128. Il y a peut-être un paramètre supplémentaire quelque part, ou le comptage manuel est incorrect.

## Action immédiate
1. Supprimer le paramètre 15 (doublon de gross_pnl_usdt) - ligne 926
2. Vérifier le nombre de paramètres après suppression
3. Si le problème persiste, identifier les autres paramètres en trop

## Note
Le debug affiche les premiers et derniers paramètres. Cela aidera à identifier les paramètres en trop après la suppression du doublon.

