"""Temperature-excursion detection (CLAUDE.md Rule 2: numbers from code, never the model).

Walks a batch's temperature-trace rows (as returned by the `equipment` MCP server) and groups
contiguous out-of-spec readings into discrete excursion events with duration and magnitude.
"""


def excursion_events(trace_rows: list[dict]) -> list[dict]:
    """Return one event per contiguous run of readings outside [spec_low_c, spec_high_c],
    ordered by elapsed_min. Each event carries the elapsed-minute span, duration, peak/trough
    reading, and magnitude beyond the breached spec bound."""
    rows = sorted(trace_rows, key=lambda r: float(r["elapsed_min"]))
    events = []
    current = None

    for row in rows:
        temp = float(row["temperature_c"])
        spec_low = float(row["spec_low_c"])
        spec_high = float(row["spec_high_c"])
        elapsed = float(row["elapsed_min"])

        if temp > spec_high:
            direction, bound, magnitude = "above", spec_high, temp - spec_high
        elif temp < spec_low:
            direction, bound, magnitude = "below", spec_low, spec_low - temp
        else:
            direction = None

        if direction is None:
            if current is not None:
                events.append(current)
                current = None
            continue

        if current is not None and current["direction"] == direction:
            current["end_elapsed_min"] = elapsed
            current["readings"] += 1
            if direction == "above":
                current["extreme_temp_c"] = max(current["extreme_temp_c"], temp)
            else:
                current["extreme_temp_c"] = min(current["extreme_temp_c"], temp)
            current["magnitude_c"] = max(current["magnitude_c"], magnitude)
        else:
            if current is not None:
                events.append(current)
            current = {
                "direction": direction,
                "spec_bound_c": bound,
                "start_elapsed_min": elapsed,
                "end_elapsed_min": elapsed,
                "extreme_temp_c": temp,
                "magnitude_c": magnitude,
                "readings": 1,
            }

    if current is not None:
        events.append(current)

    for event in events:
        event["duration_min"] = event["end_elapsed_min"] - event["start_elapsed_min"]

    return events
