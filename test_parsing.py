"""Parser tests against a real-shaped schedule payload (no network needed)."""
import json
from pathlib import Path

import pytest

from mlbboard.mlb_client import MLBClient
from mlbboard.models import (
    STATUS_FINAL,
    STATUS_LIVE,
    STATUS_OTHER,
    STATUS_UPCOMING,
)

SAMPLE = Path(__file__).parent / "sample_schedule.json"


@pytest.fixture
def days():
    payload = json.loads(SAMPLE.read_text())
    return MLBClient.parse_schedule(payload)


def test_one_day_four_games(days):
    assert len(days) == 1
    assert days[0].date_iso == "2026-06-10"
    assert len(days[0].games) == 4


def test_games_sorted_by_start_time(days):
    starts = [g.start_utc for g in days[0].games]
    assert starts == sorted(starts)


def test_final_game(days):
    final = next(g for g in days[0].games if g.game_pk == 800001)
    assert final.status == STATUS_FINAL
    assert final.away.abbreviation == "WSH"
    assert final.home.abbreviation == "PIT"
    assert (final.away_score, final.home_score) == (3, 0)
    assert final.away_is_winner is True
    assert final.home_is_winner is False
    assert final.away.record == "30-35"
    assert final.away_pitcher.name == "Jake Irvin"
    assert final.has_score is True


def test_live_game_inning_label(days):
    live = next(g for g in days[0].games if g.game_pk == 800002)
    assert live.status == STATUS_LIVE
    assert live.inning_label == "Top 7th"
    assert (live.away_score, live.home_score) == (2, 4)


def test_upcoming_game_has_no_score_and_tbd_pitcher(days):
    upcoming = next(g for g in days[0].games if g.game_pk == 800003)
    assert upcoming.status == STATUS_UPCOMING
    assert upcoming.has_score is False
    assert upcoming.away_score is None
    assert upcoming.away_pitcher.name == "Clayton Kershaw"
    # Home probable pitcher missing in the payload -> TBD
    assert upcoming.home_pitcher.name == "TBD"


def test_postponed_maps_to_other(days):
    postponed = next(g for g in days[0].games if g.game_pk == 800004)
    assert postponed.status == STATUS_OTHER
    assert postponed.detailed_state == "Postponed"


def test_empty_payload_returns_no_days():
    assert MLBClient.parse_schedule({"totalGames": 0, "dates": []}) == []
