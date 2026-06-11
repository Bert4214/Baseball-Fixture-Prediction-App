"""Domain models for the matchup board.

These wrap the raw MLB Stats API ``/schedule`` response into small, typed
objects that the rest of the app (and, later, the prediction model) can use
without knowing anything about the API's JSON shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

# Our own status buckets, mapped from the API's abstractGameState/detailedState.
STATUS_UPCOMING = "upcoming"
STATUS_LIVE = "live"
STATUS_FINAL = "final"
STATUS_OTHER = "other"  # postponed, suspended, cancelled, delayed, etc.


def _parse_utc(value: Optional[str]) -> Optional[datetime]:
    """Parse an API timestamp like '2025-04-15T22:40:00Z' into a tz-aware UTC datetime."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _map_status(abstract: str, detailed: str) -> str:
    lowered = (detailed or "").lower()
    for marker in ("postpone", "suspend", "cancel", "delay", "forfeit"):
        if marker in lowered:
            return STATUS_OTHER
    if abstract == "Final":
        return STATUS_FINAL
    if abstract == "Live":
        return STATUS_LIVE
    if abstract == "Preview":
        return STATUS_UPCOMING
    return STATUS_OTHER


@dataclass(frozen=True)
class Pitcher:
    id: Optional[int]
    name: str

    @classmethod
    def from_api(cls, data: Optional[dict]) -> "Pitcher":
        if not data:
            return cls(id=None, name="TBD")
        return cls(id=data.get("id"), name=data.get("fullName") or "TBD")


@dataclass(frozen=True)
class Team:
    id: Optional[int]
    name: str          # "Washington Nationals"
    abbreviation: str  # "WSH"
    short_name: str    # "Nationals"
    wins: Optional[int]
    losses: Optional[int]

    @property
    def record(self) -> str:
        if self.wins is None or self.losses is None:
            return ""
        return f"{self.wins}-{self.losses}"

    @classmethod
    def from_api(cls, side: dict) -> "Team":
        team = side.get("team", {}) or {}
        record = side.get("leagueRecord", {}) or {}
        abbreviation = team.get("abbreviation") or (team.get("teamCode") or "").upper() or "—"
        return cls(
            id=team.get("id"),
            name=team.get("name", "Unknown"),
            abbreviation=abbreviation,
            short_name=team.get("teamName") or team.get("name", "Unknown"),
            wins=record.get("wins"),
            losses=record.get("losses"),
        )


@dataclass
class Game:
    game_pk: Optional[int]
    start_utc: Optional[datetime]
    start_tbd: bool
    status: str            # one of STATUS_*
    detailed_state: str    # raw detailedState, for edge cases (Postponed, etc.)
    away: Team
    home: Team
    away_score: Optional[int]
    home_score: Optional[int]
    away_is_winner: bool
    home_is_winner: bool
    away_pitcher: Pitcher
    home_pitcher: Pitcher
    venue: str
    inning_label: str = ""        # e.g. "Top 5th" for live games
    series_description: str = ""
    double_header: str = "N"
    game_number: int = 1

    # --- Hooks for later phases -------------------------------------------
    # Populated by a Predictor (the GBDT/DNN from steps 3-4). None until then,
    # which is what makes the board show "projection pending" for upcoming games.
    predicted_away: Optional[float] = None
    predicted_home: Optional[float] = None

    @property
    def has_score(self) -> bool:
        return self.away_score is not None and self.home_score is not None

    @property
    def has_prediction(self) -> bool:
        return self.predicted_away is not None and self.predicted_home is not None

    def start_local(self, tz: ZoneInfo) -> Optional[datetime]:
        if self.start_utc is None:
            return None
        return self.start_utc.astimezone(tz)

    @classmethod
    def from_api(cls, g: dict) -> "Game":
        status_obj = g.get("status", {}) or {}
        abstract = status_obj.get("abstractGameState", "")
        detailed = status_obj.get("detailedState", abstract)
        status = _map_status(abstract, detailed)

        teams = g.get("teams", {}) or {}
        away_side = teams.get("away", {}) or {}
        home_side = teams.get("home", {}) or {}

        inning_label = ""
        if status == STATUS_LIVE:
            line = g.get("linescore", {}) or {}
            half = line.get("inningState") or line.get("inningHalf") or ""
            ordinal = line.get("currentInningOrdinal") or ""
            inning_label = f"{half} {ordinal}".strip()

        return cls(
            game_pk=g.get("gamePk"),
            start_utc=_parse_utc(g.get("gameDate")),
            start_tbd=bool(status_obj.get("startTimeTBD", False)),
            status=status,
            detailed_state=detailed,
            away=Team.from_api(away_side),
            home=Team.from_api(home_side),
            away_score=away_side.get("score"),
            home_score=home_side.get("score"),
            away_is_winner=bool(away_side.get("isWinner", False)),
            home_is_winner=bool(home_side.get("isWinner", False)),
            away_pitcher=Pitcher.from_api(away_side.get("probablePitcher")),
            home_pitcher=Pitcher.from_api(home_side.get("probablePitcher")),
            venue=(g.get("venue", {}) or {}).get("name", ""),
            inning_label=inning_label,
            series_description=g.get("seriesDescription", ""),
            double_header=g.get("doubleHeader", "N"),
            game_number=g.get("gameNumber", 1),
        )


@dataclass
class GameDay:
    date_iso: str          # "2025-04-15", straight from the API's dates[].date
    games: list[Game]
