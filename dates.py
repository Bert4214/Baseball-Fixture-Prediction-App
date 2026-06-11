"""Date-window helpers.

'The week' defaults to the Monday-Sunday calendar week that contains today,
so the board naturally holds both already-played and upcoming games.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def today_in(tz: ZoneInfo) -> date:
    """Today's date in the given display timezone (not the server's)."""
    return datetime.now(tz).date()


def current_week(today: date | None = None, tz: ZoneInfo | None = None) -> tuple[date, date]:
    """Monday..Sunday window containing ``today``."""
    if today is None:
        today = today_in(tz) if tz is not None else date.today()
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)


def rolling_window(days_back: int, days_forward: int,
                   today: date | None = None, tz: ZoneInfo | None = None) -> tuple[date, date]:
    """Alternative window: N days before today through M days after."""
    if today is None:
        today = today_in(tz) if tz is not None else date.today()
    return today - timedelta(days=days_back), today + timedelta(days=days_forward)
