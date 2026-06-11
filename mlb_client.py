"""Thin client for the (undocumented) MLB Stats API.

Only the ``/schedule`` endpoint is needed for the board. We ask the API to
*hydrate* the team, linescore, and probable-pitcher sub-resources so a single
request returns everything the display needs.

Note on usage: the MLB Stats API is unofficial and MLB frames it as
educational / non-commercial. See the README before building anything you
intend to ship.
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import Optional

import requests

from .models import Game, GameDay

logger = logging.getLogger(__name__)

BASE_URL = "https://statsapi.mlb.com/api/v1"
# Sub-resources embedded in the schedule response (one call, everything we need).
SCHEDULE_HYDRATE = "team,linescore,probablePitcher"
DEFAULT_TIMEOUT = 10
USER_AGENT = "mlb-matchup-board/0.1"

# Sorts games with an unknown start time to the end of the day.
_FAR_FUTURE = float("inf")


class MLBClientError(RuntimeError):
    """Raised when the schedule cannot be retrieved after retries."""


class MLBClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        sport_id: int = 1,
        game_type: Optional[str] = "R",
        session: Optional[requests.Session] = None,
        cache_ttl: int = 60,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.sport_id = sport_id
        self.game_type = game_type  # "R" regular, "P" postseason, "S" spring, None = all
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        self._cache: dict[tuple, tuple[float, list[GameDay]]] = {}

    def get_schedule(self, start_date: date, end_date: date) -> list[GameDay]:
        """Return the slate for [start_date, end_date], grouped by day."""
        cache_key = (start_date.isoformat(), end_date.isoformat())
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

        params = {
            "sportId": self.sport_id,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "hydrate": SCHEDULE_HYDRATE,
        }
        if self.game_type:
            params["gameType"] = self.game_type

        payload = self._get("schedule", params)
        days = self.parse_schedule(payload)
        self._cache[cache_key] = (now + self.cache_ttl, days)
        return days

    def _get(self, path: str, params: dict) -> dict:
        url = f"{self.base_url}/{path}"
        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_err = exc
                logger.warning("schedule request failed (attempt %d/%d): %s",
                               attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    time.sleep(0.5 * attempt)
        raise MLBClientError(f"could not reach the MLB Stats API: {last_err}") from last_err

    @staticmethod
    def parse_schedule(payload: dict) -> list[GameDay]:
        days: list[GameDay] = []
        for date_entry in payload.get("dates", []):
            games = [Game.from_api(g) for g in date_entry.get("games", [])]
            games.sort(key=lambda g: (g.start_utc.timestamp() if g.start_utc else _FAR_FUTURE))
            days.append(GameDay(date_iso=date_entry.get("date", ""), games=games))
        return days
