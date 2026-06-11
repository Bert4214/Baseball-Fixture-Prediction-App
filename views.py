"""Flask routes and the presenter that turns ``Game`` objects into the plain
dicts the template (and the JSON endpoint) consume.

Keeping all formatting here means the template stays free of logic and the
same view-models serve both ``/`` and ``/api/games``.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, jsonify, render_template

from .dates import current_week, today_in
from .mlb_client import MLBClientError
from .models import STATUS_FINAL, STATUS_LIVE, STATUS_UPCOMING, Game

bp = Blueprint("board", __name__)

_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]


def _clock(dt: datetime) -> str:
    """12-hour clock without a platform-specific strftime ('7:05 PM')."""
    hour = dt.hour % 12 or 12
    suffix = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.minute:02d} {suffix}"


def _status_label(game: Game, tz: ZoneInfo) -> str:
    if game.status == STATUS_FINAL:
        return "Final"
    if game.status == STATUS_LIVE:
        return game.inning_label or "Live"
    if game.status == STATUS_UPCOMING:
        local = game.start_local(tz)
        if game.start_tbd or local is None:
            return "TBD"
        return _clock(local)
    return game.detailed_state or "—"


def _team_view(team, score, is_winner, pitcher) -> dict:
    return {
        "abbr": team.abbreviation,
        "name": team.short_name,
        "record": team.record,
        "score": score,
        "is_winner": is_winner,
        "pitcher": pitcher.name,
    }


def _game_view(game: Game, tz: ZoneInfo, predictor) -> dict:
    # Attach a projection to upcoming games, if the registered model offers one.
    if game.status == STATUS_UPCOMING and predictor is not None:
        projection = predictor.predict(game)
        if projection:
            game.predicted_away, game.predicted_home = projection

    if game.has_score:
        score_mode = "actual"
        away_score, home_score = game.away_score, game.home_score
    elif game.has_prediction:
        score_mode = "pred"
        away_score = round(game.predicted_away)
        home_score = round(game.predicted_home)
    else:
        score_mode = "none"
        away_score = home_score = None

    final = game.status == STATUS_FINAL
    return {
        "game_pk": game.game_pk,
        "status": game.status,
        "status_label": _status_label(game, tz),
        "venue": game.venue,
        "score_mode": score_mode,
        "away": _team_view(game.away, away_score, final and game.away_is_winner, game.away_pitcher),
        "home": _team_view(game.home, home_score, final and game.home_is_winner, game.home_pitcher),
    }


def build_board(days, tz: ZoneInfo, predictor, today: date) -> list[dict]:
    board = []
    for day in days:
        try:
            day_date = date.fromisoformat(day.date_iso)
            date_label = f"{_MONTHS[day_date.month]} {day_date.day}"
            weekday = _WEEKDAYS[day_date.weekday()]
            is_today = day_date == today
        except (ValueError, IndexError):
            date_label, weekday, is_today = day.date_iso, "", False
        board.append({
            "date_iso": day.date_iso,
            "date_label": date_label,
            "weekday": weekday,
            "is_today": is_today,
            "games": [_game_view(g, tz, predictor) for g in day.games],
        })
    return board


def _week_label(start: date, end: date) -> str:
    return (f"{_MONTHS[start.month]} {start.day} \u2013 "
            f"{_MONTHS[end.month]} {end.day}, {end.year}")


def _load_board():
    cfg = current_app.config
    tz = ZoneInfo(cfg["MLB_TZ"])
    client = cfg["MLB_CLIENT"]
    predictor = cfg.get("PREDICTOR")
    today = today_in(tz)
    start, end = current_week(today)
    days = client.get_schedule(start, end)
    board = build_board(days, tz, predictor, today)
    return board, tz, start, end


@bp.route("/")
def index():
    tz_name = current_app.config["MLB_TZ"]
    try:
        board, tz, start, end = _load_board()
        error = None
    except MLBClientError as exc:
        board, tz, error = [], ZoneInfo(tz_name), str(exc)
        start, end = current_week(today_in(tz))

    now = datetime.now(tz)
    return render_template(
        "index.html",
        board=board,
        error=error,
        week_label=_week_label(start, end),
        tz_abbr=now.tzname() or tz_name,
        updated_at=_clock(now),
    )


@bp.route("/api/games")
def api_games():
    try:
        board, _tz, start, end = _load_board()
    except MLBClientError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "days": board,
    })


@bp.route("/healthz")
def healthz():
    return {"status": "ok"}
