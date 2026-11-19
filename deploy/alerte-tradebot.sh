#!/usr/bin/env bash
# Alerte quand le robot (ou le tableau de bord) tombe et ne redémarre plus.
#
# Appelé par systemd via OnFailure=alerte-tradebot@%n.service.
# Deux canaux, dans cet ordre :
#   1. une ligne dans /home/seb/logs/alertes-tradebot.log — marche toujours ;
#   2. un message Telegram si (et seulement si) le fichier de réglages existe :
#        /home/seb/.config/tradebot-alertes.env
#        TELEGRAM_BOT_TOKEN=…   TELEGRAM_CHAT_ID=…
#      Ce fichier n'est jamais dans le dépôt et ne passe par aucune main que la
#      mienne : c'est Seb qui le remplit.
#
# Le script ne doit JAMAIS échouer : une alerte qui casse une alerte masque la
# panne. On sort toujours en 0.

unite="${1:-inconnue}"
journal_alerte="/home/seb/logs/alertes-tradebot.log"
reglages="/home/seb/.config/tradebot-alertes.env"

mkdir -p "$(dirname "$journal_alerte")"
ligne="$(date '+%Y-%m-%d %H:%M:%S') | ALERTE | $unite est en échec — systemd n'a pas réussi à le relancer"
echo "$ligne" >> "$journal_alerte"
echo "$ligne"

if [ -f "$reglages" ]; then
    # shellcheck disable=SC1090
    . "$reglages"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -m 10 -X POST \
            "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
            --data-urlencode "text=🛑 $ligne" >/dev/null 2>&1
    fi
fi

exit 0
