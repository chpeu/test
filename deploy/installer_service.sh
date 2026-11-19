#!/usr/bin/env bash
# Installe le robot et son tableau de bord en services systemd.
#
# À faire UNE FOIS, par Seb (le script demande le mot de passe administrateur) :
#
#     bash deploy/installer_service.sh
#
# Ce qu'il fait, dans l'ordre :
#   1. arrête les instances lancées à la main (celles qui occupent le port 5000) ;
#   2. copie les trois fichiers de service dans /etc/systemd/system ;
#   3. crée le dossier de journal d'alertes ;
#   4. recharge systemd, active et démarre les deux services ;
#   5. montre l'état, avec les commandes pour consulter les journaux.
#
# Rien n'est destructeur : aucun fichier du projet n'est touché, et pour revenir
# en arrière il suffit de `sudo systemctl disable --now tradebot tradebot-dashboard`.

set -euo pipefail

DEPOT="$(cd "$(dirname "$0")/.." && pwd)"
CIBLE="/etc/systemd/system"
UNITES=(tradebot.service tradebot-dashboard.service "alerte-tradebot@.service"
        tradebot-vigie.service tradebot-vigie.timer)

echo "Dépôt : $DEPOT"
echo "Unités : ${UNITES[*]}"

# Le site (SvelteKit, adaptateur node) se construit dans `.svelte-kit/output`.
# `npm` vit dans nvm : sans son chemin dans PATH, un lancement en root ne le
# trouve pas (mesuré le 19/11/2026).
export PATH="/home/seb/.nvm/versions/node/v24.15.0/bin:$PATH"

if [ ! -f "$DEPOT/frontend/.svelte-kit/output/server/index.js" ]; then
    echo "⚠️  Le tableau de bord n'est pas construit — construction en cours."
    (cd "$DEPOT/frontend" && npm run build)
fi

echo
echo "1/5 Arrêt des instances lancées à la main (le port 5000 doit être libre)…"
# Le motif entre crochets évite que pkill ne tue ce propre script.
pkill -f "[u]vicorn main:app" 2>/dev/null || true
pkill -f "[v]ite preview" 2>/dev/null || true
sleep 3

echo "2/5 Installation des fichiers de service…"
for unite in "${UNITES[@]}"; do
    sudo install -m 644 "$DEPOT/deploy/$unite" "$CIBLE/$unite"
done
chmod +x "$DEPOT/deploy/alerte-tradebot.sh"

echo "3/5 Dossier de journal d'alertes…"
mkdir -p /home/seb/logs
chown seb:seb /home/seb/logs 2>/dev/null || true

echo "4/5 Activation et démarrage…"
sudo systemctl daemon-reload
sudo systemctl enable --now tradebot.service tradebot-dashboard.service
sudo systemctl enable --now tradebot-vigie.timer

echo "5/5 État…"
systemctl --no-pager --full status tradebot.service tradebot-dashboard.service | sed -n '1,40p'

cat <<'AIDE'

Vigie (toutes les 5 min) :  systemctl list-timers tradebot-vigie.timer
Pour suivre le robot :      journalctl -u tradebot -f
Pour suivre les alertes :   tail -f /home/seb/logs/alertes-tradebot.log
Pour vérifier le port :     ss -ltnp | grep 5000
Pour redémarrer :           sudo systemctl restart tradebot
Pour arrêter tout :         sudo systemctl disable --now tradebot tradebot-dashboard

Alertes Telegram (facultatif) : créer /home/seb/.config/tradebot-alertes.env
contenant TELEGRAM_BOT_TOKEN=… et TELEGRAM_CHAT_ID=… — ce fichier n'est jamais
dans le dépôt et ne doit jamais être collé dans une conversation.
AIDE
