# Le robot servi par systemd — mis en place le 19/11/2026

## Pourquoi

Avant : le robot et le tableau de bord étaient lancés à la main dans un terminal.

- un plantage, une coupure réseau ou un redémarrage de la machine = le robot ne
  repartait pas, et personne n'était prévenu ;
- un redémarrage « manuel » tuait souvent le script lanceur en laissant vivant le
  serveur enfant (uvicorn) : l'instance suivante échouait à se brancher sur le
  port 5000 et quittait sans rien dire. Le robot tournait alors sur du code plus
  ancien que le dépôt, sans que personne le sache ;
- l'interface, elle, mourait avec le terminal.

## Ce qui est installé

| Service systemd | Ce qu'il fait | Redémarre | Alerte |
|---|---|---|---|
| `tradebot` | le robot (`uvicorn main:app`, 127.0.0.1:5000) | toujours, toutes les 10 s | oui |
| `tradebot-dashboard` | le tableau de bord (`vite preview`, Tailscale:3000) | toujours, toutes les 10 s | oui |
| `alerte-tradebot@` | écrit l'alerte et prévient si Telegram est réglé | à chaque échec | — |

Le robot attend que la base PostgreSQL soit prête (jusqu'à 60 s) avant de
démarrer : sinon il démarrerait sans mémoire et son garde-fou repartirait de
zéro.

## Installation (une seule fois, par Seb)

```bash
cd "/home/seb/projet pi/test-claude-analyze-maintainability-01Hs9SEWv5USATGMzA2kzaag"
bash deploy/installer_service.sh
```

Le script arrête les instances lancées à la main, copie les trois fichiers dans
`/etc/systemd/system`, active et démarre les deux services. Il demande le mot de
passe administrateur. Retour en arrière :
`sudo systemctl disable --now tradebot tradebot-dashboard`.

## Commandes utiles

```bash
systemctl status tradebot                 # est-il vivant ?
journalctl -u tradebot -f                 # ses logs en direct
journalctl -u tradebot --since -1h -p err # ses erreurs de la dernière heure
ss -ltnp | grep 5000                      # qui occupe le port (UN seul processus)
tail -f /home/seb/logs/alertes-tradebot.log
sudo systemctl restart tradebot           # redémarrage propre
```

## Alertes Telegram (à activer)

Le fichier `/home/seb/.config/tradebot-alertes.env` (à créer à la main, jamais
dans le dépôt, jamais collé dans une conversation) :

```
TELEGRAM_BOT_TOKEN=…
TELEGRAM_CHAT_ID=…
```

Sans ce fichier, l'alerte va quand même dans `/home/seb/logs/alertes-tradebot.log`
et dans le journal système.

## Si l'adresse Tailscale change

Modifier l'adresse dans `deploy/tradebot-dashboard.service`, puis :

```bash
sudo systemctl daemon-reload && sudo systemctl restart tradebot-dashboard
```

## Ce que le service ne remplace pas

Le service empêche le robot de rester éteint. Il ne remplace pas le garde-fou :
les compteurs (prises du jour, pertes de suite, PnL) vivent dans la base
PostgreSQL, pas dans la mémoire du service — un redémarrage, même automatique,
ne les efface plus depuis le chantier « compteurs persistés » du même jour.
