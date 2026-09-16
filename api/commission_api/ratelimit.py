"""Limitation de débit des questions à l'assistant, pour la démo publique.

Deux protections complémentaires, en mémoire (un seul processus) :
- par visiteur (adresse IP) : questions par minute et par jour, pour qu'une seule personne ne monopolise pas la démo ;
- globale : questions par jour tous visiteurs confondus, pour rester sous le quota gratuit du fournisseur de modèle.

Les fenêtres sont glissantes. Une limite à 0 est désactivée.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

MINUTE = 60.0
DAY = 86_400.0


@dataclass(frozen=True)
class RateLimits:
    per_minute: int = 6
    per_day: int = 60
    global_per_day: int = 800

    @property
    def enabled(self) -> bool:
        return any((self.per_minute, self.per_day, self.global_per_day))


class RateLimitedError(Exception):
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


VISITOR_MINUTE_MESSAGE = "Trop de questions en peu de temps. Patientez un instant avant de relancer l'assistant."
VISITOR_DAY_MESSAGE = ("Vous avez atteint le nombre de questions autorisées par jour sur la démonstration. "
                       "Le simulateur reste disponible sans limite.")
GLOBAL_DAY_MESSAGE = ("La démonstration a atteint son nombre de questions pour aujourd'hui. "
                      "Le simulateur reste disponible sans limite.")


class RateLimiter:
    def __init__(self, limits: RateLimits, clock: Callable[[], float] = time.monotonic):
        self.limits = limits
        self._clock = clock
        self._lock = threading.Lock()
        self._visitors: dict[str, deque[float]] = {}
        self._global: deque[float] = deque()

    def acquire(self, visitor: str) -> None:
        """Enregistre une question, ou lève `RateLimitedError` si une limite est atteinte."""
        if not self.limits.enabled:
            return
        with self._lock:
            now = self._clock()
            self._prune(now)
            history = self._visitors.get(visitor, deque())
            checks = (
                (history, MINUTE, self.limits.per_minute, VISITOR_MINUTE_MESSAGE),
                (history, DAY, self.limits.per_day, VISITOR_DAY_MESSAGE),
                (self._global, DAY, self.limits.global_per_day, GLOBAL_DAY_MESSAGE),
            )
            for timestamps, window, limit, message in checks:
                recent = [t for t in timestamps if t > now - window] if window == MINUTE else timestamps
                if limit and len(recent) >= limit:
                    retry_after = max(1, math.ceil(recent[-limit] + window - now))
                    raise RateLimitedError(message, retry_after)
            history.append(now)
            self._visitors[visitor] = history
            self._global.append(now)

    def _prune(self, now: float) -> None:
        """Oublie ce qui date de plus d'un jour, et les visiteurs sans question récente."""
        horizon = now - DAY
        for timestamps in (self._global, *self._visitors.values()):
            while timestamps and timestamps[0] <= horizon:
                timestamps.popleft()
        for visitor in [v for v, timestamps in self._visitors.items() if not timestamps]:
            del self._visitors[visitor]
