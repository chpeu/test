"""Compare ce que le robot ecrit en base avec ce que la base sait recevoir.

Le 18/11/2026, le journal PostgreSQL etait neuf et le depot contenait un schema
plus vieux que le code : 28 colonnes que le robot ecrit n'existaient pas dans
scan_logs, plus une dans market_context et une dans market_regime_history.
Resultat : des erreurs dans le journal et un historique qui restait a zero.

Usage (depuis la racine du projet) :
    .venv/bin/python database/verifier_ecarts_base.py              # regard seul
    .venv/bin/python database/verifier_ecarts_base.py --appliquer  # ajoute ce qui manque

Attention, premiere passe : la liste de colonnes est lue dans le code sans
executer le robot. Sur les requetes construites a la volee, elle peut proposer
un nom qui n'est pas une colonne (verifie table par table avant --appliquer).
Ce qu'elle a trouve de reel le 18/11/2026 : 28 colonnes manquantes dans
scan_logs, 6 dans market_regime_history, 1 dans market_context.

Regles :
  - on ne lit aucune valeur : seulement des noms de colonnes ;
  - les types sont devines par le nom (booleen / texte / nombre) ;
  - `--appliquer` fait uniquement des ADD COLUMN IF NOT EXISTS : jamais de
    suppression, jamais de changement d'une colonne qui existe deja.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

# On balaie tout le code qui ecrit en base, pas seulement le scribe :
# market_regime_history est ecrit par core/market_regime_selector.py.
DOSSIERS_BALAIES = [Path("core"), Path("api"), Path("ml"), Path("trading")]
CONTENEUR = "tradebot-pg"
BASE = "trade_cursor_ml"

INSERT = re.compile(r"INSERT\s+INTO\s+([a-z_]+)\s*\(", re.I)
NOM_COLONNE = re.compile(r"[a-z_][a-z0-9_]*\Z")


def _noms_dans_liste(bloc: str) -> list[str]:
    # On efface les commentaires SQL d'abord : la ligne
    #   -- Exit config params (Stagnation Positive, Trailing MFE, MFE Protection)
    # contenait un « ) » qui faisait s'arreter la lecture, et les huit colonnes
    # suivantes de trade_atr_metrics restaient invisibles (mesure du 18/11/2026 au
    # soir : l'outil annoncait « 0 manque » alors qu'il en manquait 24).
    bloc = re.sub(r"--[^\n]*", "", bloc)
    fin = bloc.find(")")
    noms = [x.strip().strip("\"'") for x in bloc[:fin].split(",")]
    return [x for x in noms if NOM_COLONNE.match(x)]


# Fonctions dont la liste de colonnes est construite en Python (paires
# (« nom », valeur)) et non ecrite en dur dans la requete. Table par table,
# declarees a la main : c'est le seul moyen trouvé pour ne pas inventer de
# colonnes en aspirant les dictionnaires voisins.
FONCTIONS_A_PAIRES: dict[str, str] = {
    "log_trade": "trades",
    "log_trade_atr_metrics": "trade_atr_metrics",
}


def _paires_de_listes(fonc: ast.FunctionDef) -> list[str]:
    """Noms des colonnes preparees en Python : uniquement les listes de couples.

    On regarde deux formes : `champs = [("nom", valeur), ...]` et
    `champs.extend([...])`. Une liste n'est retenue que si 80 % de ses elements
    sont des couples (« nom », valeur) : ça écarte les tuples isoles qui servent
    a autre chose (un `("true", "1", "yes")` de comparaison, un tuple de log).
    """
    noms: list[str] = []
    for n in ast.walk(fonc):
        liste: ast.List | None = None
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.List) and any(
            isinstance(t, ast.Name) for t in n.targets
        ):
            liste = n.value
        elif (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "extend"
            and n.args
            and isinstance(n.args[0], ast.List)
        ):
            liste = n.args[0]
        if liste is None or len(liste.elts) < 3:
            continue
        couples = [
            e.elts[0].value
            for e in liste.elts
            if isinstance(e, ast.Tuple)
            and len(e.elts) == 2
            and isinstance(e.elts[0], ast.Constant)
            and isinstance(e.elts[0].value, str)
            and NOM_COLONNE.match(e.elts[0].value)
        ]
        if len(couples) >= 0.8 * len(liste.elts):
            noms.extend(couples)
    return noms


def colonnes_par_table() -> dict[str, set[str]]:
    """Noms de colonnes utilises dans chaque INSERT INTO ... (...) du code."""
    sources = []
    for dossier in DOSSIERS_BALAIES:
        for chemin in dossier.rglob("*.py"):
            try:
                texte = chemin.read_text(encoding="utf-8", errors="replace")
            except UnicodeDecodeError:
                continue
            if "import sqlite3" in texte:
                # Ce fichier écrit dans un fichier SQLite (le dépôt en a deux :
                # core/database.py et core/analytics_database.py). Ses colonnes
                # n'ont rien à faire comparées aux tables PostgreSQL : mesuré le
                # 18/11/2026 au soir, ça fabriquait 31 fausses alertes sur `trades`
                # (entry, exit, fees, instance_port…) alors que l'écriture réelle
                # du même trade passait sans erreur.
                continue
            try:
                sources.append(ast.parse(texte))
            except SyntaxError:
                continue

    certain: dict[str, set[str]] = {}
    propose: dict[str, set[str]] = {}
    for arbre in sources:
        for n in ast.walk(arbre):
            # 1) INSERT ecrit en dur dans une chaine
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                m = INSERT.search(n.value)
                if m:
                    noms = _noms_dans_liste(n.value[m.end() :])
                    if noms:
                        certain.setdefault(m.group(1), set()).update(noms)
            # 2) couples (« nom », valeur) prepares en Python par une fonction
            #    dont on sait quelle table elle ecrit (voir FONCTIONS_A_PAIRES)
            if isinstance(n, ast.FunctionDef) and n.name in FONCTIONS_A_PAIRES:
                couples = _paires_de_listes(n)
                if len(couples) > 10:
                    propose.setdefault(FONCTIONS_A_PAIRES[n.name], set()).update(couples)
            # 3) liste construite en Python puis inseree dans la requete de lot
            if isinstance(n, ast.Assign):
                cible = next((t.id for t in n.targets if isinstance(t, ast.Name)), "")
                if cible == "columns" and isinstance(n.value, (ast.List, ast.Tuple)):
                    noms = [e.value for e in n.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                    if len(noms) > 20:  # la liste de scan_logs fait 147 noms
                        certain.setdefault("scan_logs", set()).update(noms)
    return certain, propose


def colonnes_en_base(table: str) -> set[str]:
    sortie = subprocess.run(
        f'docker exec {CONTENEUR} psql -U postgres -d {BASE} -t -A -c '
        f'"SELECT column_name FROM information_schema.columns WHERE table_name=\'{table}\'"',
        shell=True,
        capture_output=True,
        check=False,  # on lit les erreurs nous-mêmes, on ne plante pas
        text=True,
    ).stdout.split()
    return set(sortie)


# Etiquettes ecrites en toutes lettres, pas des nombres (mesure du 18/11/2026 :
# session_market vaut 'EUROPE_OPEN', regime_at_scan vaut 'VOLATILE').
TEXTES_CERTAINS = {"session_market", "regime_at_scan", "market_regime", "detection_method", "regime_name"}


def type_pour(nom: str) -> str:
    if "use_" in nom or "passed" in nom or nom.startswith(("is_", "anti_")) or nom.endswith(
        ("_enabled", "_detected", "_triggered", "_aligned")
    ):
        return "BOOLEAN"
    if nom in TEXTES_CERTAINS or re.search(r"(reason|category|type|pattern|direction|snapshot|name|version|comment|model|_market)\Z", nom):
        return "TEXT"
    return "DOUBLE PRECISION"


def main() -> int:
    ecrire = "--appliquer" in sys.argv
    certain, propose = colonnes_par_table()
    total = 0
    tables = sorted(set(certain) | set(propose))
    for table in tables:
        attendues = certain.get(table, set())
        suspects = propose.get(table, set())
        existantes = colonnes_en_base(table)
        if not existantes:
            print(f"{table}: table absente de la base — appliquer le schéma du dépôt ?")
            total += len(attendues)
            continue
        manquantes = sorted(attendues - existantes)
        a_verifier = sorted((suspects - existantes) - set(manquantes))
        print(f"{table}: {len(attendues)} colonnes écrites, {len(existantes)} en base, {len(manquantes)} manquantes")
        for c in manquantes:
            print(f"    + {c} -> {type_pour(c)}")
        if a_verifier:
            # Noms sortis d'une liste Python voisine : la requête réelle peut très
            # bien ne pas les écrire (mesure du 18/11/2026 : 31 noms signalés à
            # tort sur `trades`, écriture du même trade pourtant réussie).
            print(f"    à vérifier à la main (non appliqués) : {len(a_verifier)} — {', '.join(a_verifier[:12])}{'…' if len(a_verifier) > 12 else ''}")
        total += len(manquantes)
        if manquantes and ecrire:
            ddl = ";\n".join(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {c} {type_pour(c)}" for c in manquantes)
            Path("/tmp/ecarts_base.sql").write_text(ddl + ";\n", encoding="utf-8")
            r = subprocess.run(
                f"docker exec -i {CONTENEUR} psql -U postgres -d {BASE} < /tmp/ecarts_base.sql",
                shell=True,
                capture_output=True,
                check=False,  # idem : le rapport se fait ligne par ligne
                text=True,
            )
            erreurs = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("ERROR")]
            print(f"    applique, {len(erreurs)} erreur(s)")
            for e in erreurs[:3]:
                print("     ", e[:160])
    print(f"\ntotal colonnes manquantes : {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
