#!/usr/bin/env bash
# La vigie : toutes les 5 minutes, elle répond à deux questions qu'aucun
# redémarrage automatique ne pose tout seul :
#   1. le robot répond-il vraiment sur le port 5000 ?
#   2. redémarre-t-il en boucle sans s'en sortir ?
#
# Pourquoi elle existe (mesuré le 19/11/2026, le soir de la mise en service) :
# une ancienne instance lancée à la main gardait le port 5000. Le service,
# lui, réessayait tous les 10 s et échouait — « address already in use » —
# 14 fois de suite. `Restart=always` appelle ça un succès : l'unité n'est jamais
# passée en état « failed », donc `OnFailure` n'a jamais sonné. Une boucle de
# redémarrage silencieuse, avec le robot éteint.

set -u

SERVICE="tradebot.service"
MARQUEUR="/home/seb/logs/.vigie-tradebot"
ALERTE="/home/seb/projet pi/test-claude-analyze-maintainability-01Hs9SEWv5USATGMzA2kzaag/deploy/alerte-tradebot.sh"
PORT="5000"

combien=$(systemctl show -p NRestarts --value "$SERVICE" 2>/dev/null || echo 0)
precedent=$(cat "$MARQUEUR" 2>/dev/null || echo 0)
echo "$combien" > "$MARQUEUR"

if ! curl -sf -m 10 -o /dev/null "http://127.0.0.1:${PORT}/api/status"; then
    "$ALERTE" "robot" "ne répond pas sur le port ${PORT} — est-ce qu'un autre programme le garde ?"
elif [ "${combien:-0}" -gt "${precedent:-0}" ]; then
    "$ALERTE" "robot" "a redémarré $((combien - precedent)) fois depuis la dernière vigie — il tourne probablement en boucle"
fi

# Une vigie ne doit jamais être la cause d'une panne de plus.
exit 0
