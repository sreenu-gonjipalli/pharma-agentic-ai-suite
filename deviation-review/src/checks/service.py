"""Service/calibration-interval breach detection (CLAUDE.md Rule 2: numbers from code).

Given an equipment_id's maintenance history and a process date, finds the most recent service
on or before that date and determines whether the equipment was overdue.
"""
from datetime import date


def _parse(d: str) -> date:
    return date.fromisoformat(d)


def service_breach(maintenance_rows: list[dict], process_date: str) -> dict:
    """Return the most recent service on/before process_date, months elapsed since it (30.44
    days/month), and whether that exceeds the record's own schedule_months -- equivalently,
    whether process_date falls after that service's next_due_date."""
    process = _parse(process_date)
    prior = [r for r in maintenance_rows if _parse(r["service_date"]) <= process]
    if not prior:
        return {
            "last_service_date": None,
            "months_since_service": None,
            "schedule_months": None,
            "next_due_date": None,
            "breach": None,
            "reason": "no service record on or before process_date",
        }

    last = max(prior, key=lambda r: _parse(r["service_date"]))
    last_service = _parse(last["service_date"])
    days_since = (process - last_service).days
    months_since = round(days_since / 30.44, 2)
    next_due = _parse(last["next_due_date"])
    breach = process > next_due

    return {
        "last_service_date": last["service_date"],
        "months_since_service": months_since,
        "schedule_months": int(last["schedule_months"]),
        "next_due_date": last["next_due_date"],
        "breach": breach,
        "days_overdue": (process - next_due).days if breach else 0,
    }
