"""Client d'enqueue Hub → Magos. Le pipeline réel (embed → cold) vit côté Magos (embed_cron.py)."""

import threading

import requests

from services.magos import _magos_url


def enqueue_for_embedding(numero_dossier: str) -> None:
    """Fire-and-forget : ajoute le cas à la queue Magos. Indépendant de la DB source.

    Le cron embed_cron.py embed les lames puis les passe en cold par lame — ne jamais
    cold ici, ça priverait l'embedding des lames encore hot.
    """
    if not numero_dossier:
        return

    def _fire():
        try:
            requests.post(f"{_magos_url()}/api/queue/embed",
                          json={"case_number": numero_dossier}, timeout=10)
        except requests.RequestException:
            pass
    threading.Thread(target=_fire, daemon=True).start()
