#!/usr/bin/env python3
"""
FoetoPath — Rate-limiter pour tentatives de connexion.

Mécanisme en mémoire (dict Python + timestamps), adapté au déploiement
mono-instance. Après N échecs consécutifs, impose un délai progressif :
  - 1-2 échecs : pas de délai
  - 3 échecs   : 5 secondes
  - 4 échecs   : 15 secondes
  - 5 échecs   : 60 secondes
  - 6+ échecs  : 120 secondes

Les compteurs sont réinitialisés après un login réussi.
Nettoyage automatique des entrées expirées (> 30 min d'inactivité).
"""

import threading
import time
from dataclasses import dataclass, field

# ── Délais progressifs (en secondes) par nombre d'échecs ────────────────
_DELAY_SCHEDULE = {
    3: 5,
    4: 15,
    5: 60,
}
_MAX_DELAY = 120  # Au-delà de 5 échecs


@dataclass
class _AttemptRecord:
    count: int = 0
    last_attempt: float = 0.0


class LoginRateLimiter:
    """Rate-limiter en mémoire pour les tentatives de connexion."""

    def __init__(self, cleanup_interval: int = 1800):
        self._records: dict[str, _AttemptRecord] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = cleanup_interval  # 30 min

    def _key(self, username: str, ip: str) -> str:
        """Clé combinée username+IP pour éviter les contournements."""
        return f"{username.lower()}|{ip}"

    def _cleanup(self):
        """Supprime les entrées inactives depuis plus de cleanup_interval."""
        now = time.time()
        expired = [
            k for k, v in self._records.items()
            if now - v.last_attempt > self._cleanup_interval
        ]
        for k in expired:
            del self._records[k]

    def get_delay(self, username: str, ip: str) -> float:
        """Retourne le délai restant (en secondes) avant la prochaine tentative autorisée.
        Retourne 0 si aucun délai n'est requis.
        """
        key = self._key(username, ip)
        with self._lock:
            rec = self._records.get(key)
            if not rec or rec.count < 3:
                return 0.0

            required_delay = _DELAY_SCHEDULE.get(rec.count, _MAX_DELAY)
            elapsed = time.time() - rec.last_attempt
            remaining = required_delay - elapsed
            return max(0.0, remaining)

    def record_failure(self, username: str, ip: str):
        """Enregistre un échec de connexion."""
        key = self._key(username, ip)
        with self._lock:
            self._cleanup()
            rec = self._records.get(key)
            if rec is None:
                rec = _AttemptRecord()
                self._records[key] = rec
            rec.count += 1
            rec.last_attempt = time.time()

    def record_success(self, username: str, ip: str):
        """Réinitialise le compteur après un login réussi."""
        key = self._key(username, ip)
        with self._lock:
            self._records.pop(key, None)

    def get_attempt_count(self, username: str, ip: str) -> int:
        """Retourne le nombre d'échecs consécutifs."""
        key = self._key(username, ip)
        with self._lock:
            rec = self._records.get(key)
            return rec.count if rec else 0


# ── Instance globale (singleton) ─────────────────────────────────────────
login_limiter = LoginRateLimiter()
