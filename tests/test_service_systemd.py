"""Les fichiers de service doivent rester valables.

Un fichier de service mal écrit ne prévient pas : le robot ne démarre simplement
pas au démarrage de la machine, ou redémarre en boucle sans que personne regarde.
`systemd-analyze verify` est appelé ici pour ne pas découvrir ça un soir de panne.
"""

import os
import subprocess
from pathlib import Path

DEPOT = Path(__file__).resolve().parent.parent
DEPLOY = DEPOT / "deploy"


def lire(nom: str) -> str:
    return (DEPLOY / nom).read_text(encoding="utf-8")


def section(texte: str, nom: str) -> str:
    debut = texte.index(f"[{nom}]")
    suite = texte.find("[", debut + 1)
    return texte[debut : suite if suite != -1 else len(texte)]


def test_le_robot_redemarre_toujours_apres_un_plantage():
    service = lire("tradebot.service")
    assert "Restart=always" in service
    assert "RestartSec=10" in service
    assert "OnFailure=alerte-tradebot@%n.service" in section(service, "Unit")
    assert "StartLimitIntervalSec=0" in section(service, "Unit")


def test_attente_de_la_base_avant_de_demarrer():
    """Sans la base, le garde-fou repartirait de zéro : le robot doit attendre."""
    service = lire("tradebot.service")
    assert "pg_isready" in section(service, "Service")


def test_les_chemins_avec_espaces_sont_protegés():
    """Le dossier du projet contient un espace : non protégé, systemd couperait
    la commande et le service ne démarrerait jamais."""
    for nom in ("tradebot.service", "tradebot-dashboard.service", "alerte-tradebot@.service"):
        service = lire(nom)
        for ligne in service.splitlines():
            if ligne.startswith("ExecStart=") and "projet pi" in ligne:
                assert '"' in ligne, f"{nom} : chemin avec espace non protégé"


def test_systemd_analyze_accepte_les_fichiers():
    if not shutil_which("systemd-analyze"):
        return
    for nom in ("tradebot.service", "tradebot-dashboard.service"):
        resultat = subprocess.run(
            ["systemd-analyze", "verify", str(DEPLOY / nom)],
            capture_output=True,
            text=True,
            check=False,
        )
        message = (resultat.stdout + resultat.stderr).strip()
        assert not message, f"{nom} refusé par systemd : {message}"


def shutil_which(nom: str):
    import shutil

    return shutil.which(nom)


def test_le_script_alerte_ne_peut_pas_echouer():
    """Une alerte qui casse masque la panne : le script sort toujours en 0."""
    script = DEPLOY / "alerte-tradebot.sh"
    assert os.access(script, os.X_OK)
    assert "exit 0" in script.read_text(encoding="utf-8")
    resultat = subprocess.run(
        ["bash", str(script), "test-unite.service"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert resultat.returncode == 0
    assert "ALERTE" in resultat.stdout
