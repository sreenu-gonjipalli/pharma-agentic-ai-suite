"""Visit-window breach detection (CLAUDE.md Rule 2: numbers from code).

Recomputes the offset between a planned and actual visit date and whether it falls outside the
protocol's permitted window, independent of any pre-labeled column in the source data.
"""
from datetime import date


def visit_window_breach(planned_date: str, visit_window_days: int, actual_date: str) -> dict:
    planned = date.fromisoformat(planned_date)
    actual = date.fromisoformat(actual_date)
    days_offset = (actual - planned).days
    window = int(visit_window_days)
    breach = abs(days_offset) > window

    return {
        "planned_date": planned_date,
        "actual_date": actual_date,
        "window_days": window,
        "days_offset": days_offset,
        "breach": breach,
    }
