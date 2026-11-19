"""Écart papier ↔ live : ce que les mêmes trades auraient coûté en compte réel.

Usage :
    PYTHONPATH=. .venv/bin/python scripts/mesure_ecart_papier_live.py [--jours 3]

Le papier remplit au **dernier prix**, sans frais, sans spread, sans latence et
sans financement. Le live paie tout cela. Cette sonde reprend les trades déjà
fermés et leur applique les coûts réels de MEXC, cause par cause, pour que la
performance mesurée en papier soit comparable à ce que le compte réel donnera.

Ce qui est mesuré ici : frais taker, spread du carnet d'ordres, financement des
perpétuels, dépassement du stop (la bougie dépasse le prix de sortie).
Ce qui NE peut pas être mesuré sans live : le glissement à l'exécution (le
chemin réel l'enregistre déjà dans `actual_slippage_pct`), les ordres rejetés,
les remplacements partiels, et l'écart prix de dernière transaction / prix de
marque utilisé pour le calcul du résultat par l'échange.
"""

import argparse
import asyncio
import statistics
import subprocess
from datetime import datetime, timezone

import ccxt.async_support as ccxt

from core.frais_paires import table_frais

COLONNES = """
select symbol, direction, entry_price, exit_price, net_pnl_pct,
       coalesce(exit_reason,'?') raison, timestamp_entry, timestamp_exit
from trades
where net_pnl_pct is not null and timestamp_exit > now() - (%s || ' hours')::interval
order by timestamp_exit desc
"""


def lire_trades(heures):
    out = subprocess.run(
        ["docker", "exec", "tradebot-pg", "psql", "-U", "postgres", "-d",
         "trade_cursor_ml", "-t", "-A", "-F", "\t", "-c", COLONNES % heures],
        capture_output=True, text=True, check=False,
    )
    if out.returncode:
        raise SystemExit(f"requête impossible: {out.stderr.strip()}")
    trades = []
    for ligne in out.stdout.strip().splitlines():
        colonnes = ligne.split("\t")
        if len(colonnes) < 8:
            continue
        symbole, sens, entree, sortie, pnl, raison, t_entree, t_sortie = colonnes[:8]
        duree = (
            datetime.fromisoformat(t_sortie.replace(" ", "T")).replace(tzinfo=timezone.utc)
            - datetime.fromisoformat(t_entree.replace(" ", "T")).replace(tzinfo=timezone.utc)
        )
        trades.append({
            "symbol": symbole,
            "direction": sens,
            "entry": float(entree),
            "exit": float(sortie) if sortie not in ("", "NULL") else None,
            "pnl_pct": float(pnl),
            "reason": raison,
            "horodatage_sortie": t_sortie,
            "heures": duree.total_seconds() / 3600,
        })
    return trades


async def principal(jours):
    trades = lire_trades(jours * 24)
    if not trades:
        raise SystemExit("aucun trade fermé sur la période")

    frais = await table_frais(force=True)
    exchange = ccxt.mexc({"options": {"defaultType": "swap"}})
    spreads, financements, depassements = {}, {}, {}

    symboles = sorted({t["symbol"] for t in trades})
    for symbole in symboles:
        try:
            carnet = await exchange.fetch_order_book(symbole, 5)
            bid = (carnet.get("bids") or [[0]])[0][0]
            ask = (carnet.get("asks") or [[0]])[0][0]
            if bid and ask:
                spreads[symbole] = (ask - bid) / ((ask + bid) / 2) * 100
        except Exception:
            spreads[symbole] = None
        try:
            info = await exchange.fetch_funding_rate(symbole)
            taux = info.get("fundingRate")
            financements[symbole] = float(taux) if taux is not None else None
        except Exception:
            financements[symbole] = None

    # dépassement du stop : pour une sortie « stop », la bougie de 1 minute qui a
    # déclenché la sortie descend (LONG) ou monte (SHORT) plus bas que le prix de
    # sortie théorique. En live, l'ordre au marché se remplit sur ce territoire-là.
    for t in [x for x in trades if x["reason"] == "SL" and x["exit"]][:80]:
        # Les bougies autour de la SORTIE du trade, pas les 8 dernières minutes de
        # la paire : sinon on mesure n'importe quoi.
        sortie_ms = int(datetime.fromisoformat(
            t["horodatage_sortie"].replace(" ", "T")).replace(tzinfo=timezone.utc).timestamp() * 1000)
        try:
            bougies = await exchange.fetch_ohlcv(
                t["symbol"], "1m", since=sortie_ms - 120_000, limit=4
            )
        except Exception:
            continue
        encadrantes = [b for b in bougies if sortie_ms - 90_000 <= b[0] <= sortie_ms + 90_000]
        meches = [
            (t["exit"] - b[3]) if t["direction"] == "LONG" else (b[2] - t["exit"])
            for b in encadrantes
        ]
        depassement = max([m for m in meches if m > 0], default=0.0)
        depassements[(t["symbol"], t["exit"])] = depassement / t["entry"] * 100

    total_papier = sum(t["pnl_pct"] for t in trades)
    total_frais, total_spread, total_funding = 0.0, 0.0, 0.0
    par_cause = {"frais": [], "spread": [], "financement": [], "stop": []}

    for t in trades:
        taker = (frais.get(t["symbol"]) or (None, None))[0]
        if taker is not None:
            frais_pct = taker * 2 * 100
            total_frais += frais_pct
            par_cause["frais"].append(frais_pct)

        spread = spreads.get(t["symbol"])
        if spread is not None:
            total_spread += spread
            par_cause["spread"].append(spread)

        taux = financements.get(t["symbol"])
        if taux is not None:
            signe = 1 if t["direction"] == "LONG" else -1
            cout = signe * taux * (t["heures"] / 8) * 100
            total_funding += cout
            par_cause["financement"].append(cout)

        dep = depassements.get((t["symbol"], t["exit"]))
        if dep is not None:
            par_cause["stop"].append(dep)

    total_stop_max = sum(par_cause["stop"])
    total_stop_mid = total_stop_max / 2

    print(f"trades fermés analysés : {len(trades)} sur {jours} jour(s)")
    print(f"résultat papier        : {total_papier:+.2f} %\n")
    print("causes de décalage, en points de pourcentage cumulés :")
    print(f"  frais taker (× aller-retour)      : {-total_frais:+.2f}")
    print(f"  spread du carnet (1 traversée)    : {-total_spread:+.2f}")
    print(f"  financement des perpétuels        : {-total_funding:+.2f}")
    print(f"  dépassement du stop ({len(par_cause['stop'])} stops)      : {-total_stop_mid:+.2f}  "
          f"(fourchette 0 → -{total_stop_max:.2f})")
    ajuste = total_papier - total_frais - total_spread - total_funding - total_stop_mid
    print(f"\nrésultat ajusté « comme en live » : {ajuste:+.2f} %   "
          f"({total_papier:+.2f} → {ajuste:+.2f}, soit {ajuste - total_papier:+.2f} points)")

    def resumer(nom, valeurs):
        if not valeurs:
            return
        print(
            f"  {nom:<28} moyenne {statistics.mean(valeurs):+.4f} % par prise · "
            f"pire cas {max(valeurs):.4f} %"
        )

    print("\npar prise (moyenne et pire cas) :")
    for cause in ("frais", "spread", "financement", "stop"):
        resumer(cause, par_cause[cause])

    paires_payantes = sorted({t["symbol"] for t in trades if (frais.get(t["symbol"]) or (None,))[0] not in (0.0, None)})
    print(f"\npaires aujourd'hui payantes parmi ces trades : {len(paires_payantes)} {paires_payantes[:8]}")
    non_mesures = [c for c in spreads.values() if c is None]
    if non_mesures:
        print(f"  ({len(non_mesures)} carnets d'ordres illisibles sur la période)")
    await exchange.close()


if __name__ == "__main__":
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--jours", type=int, default=3)
    args = parseur.parse_args()
    asyncio.run(principal(args.jours))
