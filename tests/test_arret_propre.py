"""Le robot doit savoir rendre son tablier.

Mesuré le 19/11/2026 : `systemctl restart tradebot` ne se terminait jamais. Le
gestionnaire d'arrêt installait ses propres gestionnaires pour SIGTERM et SIGINT,
faisait le ménage (watchdog arrêté, bases fermées, journaux vidés) mais ne rendait
jamais la main : le processus restait vivant, systemd attendait 90 secondes avant
de tuer, et le redémarrage n'aboutissait pas. Un robot qu'on ne peut pas arrêter
est un robot qu'on ne peut pas mettre à jour.
"""

import asyncio
import inspect
import signal

from core.shutdown import GracefulShutdown


def test_apres_le_menage_le_signal_est_rendu(monkeypatch):
    ordre = []
    gestionnaire = GracefulShutdown(timeout=5.0)

    async def menage_factice():
        ordre.append("menage")

    monkeypatch.setattr(gestionnaire, "shutdown", menage_factice)
    def observer(sig, action):
        # asyncio installe lui-même des gestionnaires (SIGINT) pendant asyncio.run :
        # on ne regarde que le signal qui nous occupe.
        if sig == signal.SIGTERM:
            ordre.append(f"action:{sig}")

    monkeypatch.setattr(signal, "signal", observer)
    monkeypatch.setattr(
        gestionnaire, "_loop", type("FausseBoucle", (), {"remove_signal_handler": lambda self, sig: None})()
    )

    import os as module_os

    monkeypatch.setattr(
        module_os, "kill", lambda pid, sig: ordre.append(f"signal:{sig}") if sig == signal.SIGTERM else None
    )

    asyncio.run(gestionnaire._nettoyer_puis_rendre_la_main(signal.SIGTERM))

    assert ordre == ["menage", f"action:{signal.SIGTERM}", f"signal:{signal.SIGTERM}"], (
        "le ménage doit se faire AVANT que le signal soit renvoyé, sinon les bases "
        "se ferment à moitié"
    )


def test_le_signal_renvoye_est_le_bon(monkeypatch):
    gestionnaire = GracefulShutdown(timeout=5.0)
    recus = []

    async def menage_factice():
        pass

    monkeypatch.setattr(gestionnaire, "shutdown", menage_factice)
    import os as module_os

    monkeypatch.setattr(module_os, "kill", lambda pid, sig: recus.append(sig))

    asyncio.run(gestionnaire._nettoyer_puis_rendre_la_main(signal.SIGINT))
    assert recus == [signal.SIGINT]


def test_le_programme_ne_garde_pas_la_main_en_source():
    """Filet de sécurité : la chaîne menage -> rendre la main doit rester écrite."""
    source = inspect.getsource(GracefulShutdown)
    assert "_nettoyer_puis_rendre_la_main" in source
    assert "signal.SIG_DFL" in source
    assert "os.kill(os.getpid(), sig)" in source
