#!/usr/bin/env python3
"""Synthetic data generator for DevGuard Phase 1 (CLAUDE.md Rule 4: synthetic data only).

Writes 5 CSVs to ../data/ plus 2 small PDFs (SOP, protocol). Deterministic (seeded) except
where noted -- the fixed demo case (B-2291, PROGRESS.md "Fixed demo case") is hand-written,
not randomized, so every number in it matches CLAUDE.md exactly.

Run: python3 scripts/gen_data.py
"""
import csv
import os
import random
from datetime import date, datetime, timedelta

from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

random.seed(42)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Manufacturing side: equipment, batches, maintenance, temperature traces, lab results
# ---------------------------------------------------------------------------

EQUIPMENT = [f"Oven-{i:02d}" for i in range(1, 7)]
SPEC_SETPOINT_C = 60.0
SPEC_TOLERANCE_C = 5.0
SPEC_LOW_C = SPEC_SETPOINT_C - SPEC_TOLERANCE_C
SPEC_HIGH_C = SPEC_SETPOINT_C + SPEC_TOLERANCE_C
STEP_MINUTES = 240  # 4h drying step
SERVICE_SCHEDULE_MONTHS = 12

# Batches on Oven-04 that share the overdue-service window with the fixed demo case.
# Rule 1/2 in CLAUDE.md: equipment overdue-service alone is not evidence of product impact --
# each of these still needs its own lab result checked, which is why B-2293/B-2296 get normal
# moisture results below while B-2291 gets the actual excursion + out-of-spec result.
DEMO_CASE_ID = "B-2291"
DEMO_EQUIPMENT = "Oven-04"
DEMO_PROCESS_DATE = date(2026, 8, 1)
OVEN04_LAST_SERVICE = date(2025, 6, 1)          # 14 months before DEMO_PROCESS_DATE
OVEN04_NEXT_DUE = date(2026, 6, 1)               # 12-month schedule -- overdue by the demo date
AFFECTED_BATCHES = ["B-2293", "B-2296"]          # "2 other batches affected"

# 17 batches total: the demo cluster (3, all on Oven-04) + 14 routine batches on other ovens.
# Routine IDs start at 2300 specifically so they never collide with 2291/2293/2296 above.
ALL_BATCH_IDS = [DEMO_CASE_ID] + AFFECTED_BATCHES + [f"B-{2300 + i}" for i in range(14)]

BATCH_EQUIPMENT = {}
BATCH_DATE = {}
_other_ovens = [e for e in EQUIPMENT if e != DEMO_EQUIPMENT]
_day_cursor = date(2026, 1, 5)
for bid in ALL_BATCH_IDS:
    if bid == DEMO_CASE_ID:
        BATCH_EQUIPMENT[bid] = DEMO_EQUIPMENT
        BATCH_DATE[bid] = DEMO_PROCESS_DATE
    elif bid == "B-2293":
        BATCH_EQUIPMENT[bid] = DEMO_EQUIPMENT
        BATCH_DATE[bid] = date(2026, 6, 20)   # after last service, before the demo batch
    elif bid == "B-2296":
        BATCH_EQUIPMENT[bid] = DEMO_EQUIPMENT
        BATCH_DATE[bid] = date(2026, 7, 15)
    else:
        BATCH_EQUIPMENT[bid] = random.choice(_other_ovens)
        BATCH_DATE[bid] = _day_cursor
        _day_cursor += timedelta(days=random.randint(6, 11))


def write_maintenance():
    rows = []
    for eq in EQUIPMENT:
        if eq == DEMO_EQUIPMENT:
            # 4 historical services ending in the overdue one that matters for the demo case.
            services = [date(2023, 6, 3), date(2024, 6, 5), date(2025, 6, 1)]
        else:
            # Routine equipment: serviced roughly on schedule through mid-2026.
            services = []
            d = date(2023, random.randint(1, 6), random.randint(1, 28))
            while d < date(2026, 9, 1):
                services.append(d)
                d = d + timedelta(days=SERVICE_SCHEDULE_MONTHS * 30 + random.randint(-10, 10))
        for i, service_date in enumerate(services):
            rows.append({
                "equipment_id": eq,
                "service_date": service_date.isoformat(),
                "service_type": "Preventive maintenance" if i < len(services) - 1 else "Preventive maintenance (last on record)",
                "technician": random.choice(["J. Alvarez", "M. Chen", "R. Osei", "P. Fontaine"]),
                "next_due_date": (service_date + timedelta(days=SERVICE_SCHEDULE_MONTHS * 30)).isoformat(),
                "schedule_months": SERVICE_SCHEDULE_MONTHS,
            })
    path = os.path.join(DATA_DIR, "maintenance.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def demo_trace_points(batch_id):
    """5-minute resolution for the 3 demo-cluster batches (Oven-04), so Phase 3's excursion
    duration check has enough resolution to measure the 20-minute B-2291 excursion precisely."""
    points = []
    for minute in range(0, STEP_MINUTES + 1, 5):
        if batch_id == DEMO_CASE_ID and 100 <= minute <= 120:
            # Peak 72C for a 20-minute window (100-120 min), CLAUDE.md's fixed demo case.
            temp = 72.0 if 100 < minute < 120 else 68.0
        elif batch_id == DEMO_CASE_ID:
            temp = round(SPEC_SETPOINT_C + random.uniform(-1.5, 1.5), 1)
        else:
            # B-2293 / B-2296: same overdue oven, but no excursion -- stays in spec.
            temp = round(SPEC_SETPOINT_C + random.uniform(-2.0, 2.0), 1)
        points.append((minute, temp))
    return points


def routine_trace_points():
    """20-minute resolution for the 14 routine (non-demo) batches -- coarser is fine since
    nothing needs to be measured precisely on these."""
    points = []
    for minute in range(0, STEP_MINUTES + 1, 20):
        temp = round(SPEC_SETPOINT_C + random.uniform(-2.5, 2.5), 1)
        points.append((minute, temp))
    return points


def write_equipment_traces():
    rows = []
    for bid in ALL_BATCH_IDS:
        process_date = BATCH_DATE[bid]
        equipment = BATCH_EQUIPMENT[bid]
        start = datetime.combine(process_date, datetime.min.time()).replace(hour=8)
        pts = demo_trace_points(bid) if bid in (DEMO_CASE_ID, *AFFECTED_BATCHES) else routine_trace_points()
        for minute, temp in pts:
            ts = start + timedelta(minutes=minute)
            rows.append({
                "batch_id": bid,
                "equipment_id": equipment,
                "timestamp": ts.isoformat(),
                "elapsed_min": minute,
                "temperature_c": temp,
                "setpoint_c": SPEC_SETPOINT_C,
                "spec_low_c": SPEC_LOW_C,
                "spec_high_c": SPEC_HIGH_C,
            })
    path = os.path.join(DATA_DIR, "equipment_traces.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


LAB_TESTS = [
    ("Assay", "%", 95.0, 105.0),
    ("Moisture content", "%", 0.0, 0.5),
    ("Dissolution (Q30min)", "%", 80.0, 100.0),
    ("Appearance", "pass/fail", None, None),
    ("Related substances, total", "%", 0.0, 1.0),
    ("Hardness", "kP", 8.0, 15.0),
]


def write_lab_results():
    rows = []
    for bid in ALL_BATCH_IDS:
        test_date = BATCH_DATE[bid] + timedelta(days=2)
        for name, unit, lo, hi in LAB_TESTS:
            if bid == DEMO_CASE_ID and name == "Moisture content":
                # The actual product-impact evidence for the demo case: over-dried product
                # from the 72C excursion pushed moisture content out of spec.
                value = 0.8
            elif unit == "pass/fail":
                value = "pass"
            else:
                mid = (lo + hi) / 2
                spread = (hi - lo) * 0.2
                value = round(random.uniform(mid - spread, mid + spread), 2)
            pass_fail = "pass"
            if unit != "pass/fail" and lo is not None and not (lo <= value <= hi):
                pass_fail = "fail"
            rows.append({
                "batch_id": bid,
                "test_name": name,
                "result_value": value,
                "unit": unit,
                "spec_low": lo if lo is not None else "",
                "spec_high": hi if hi is not None else "",
                "pass_fail": pass_fail,
                "test_date": test_date.isoformat(),
            })
    path = os.path.join(DATA_DIR, "lab_results.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Clinical side: subjects, visit windows
# ---------------------------------------------------------------------------

VISIT_SCHEDULE = [
    ("Screening", 0, 0),
    ("Baseline", 14, 3),
    ("Visit 2", 28, 3),
    ("Visit 3", 56, 5),
    ("Visit 4 (EOT)", 84, 5),
    ("Follow-up", 112, 7),
]

DEMO_SUBJECT = "S-1042"


def write_subject_visits():
    rows = []
    subjects = [DEMO_SUBJECT] + [f"S-{1000 + i}" for i in range(1, 18)]
    for sid in subjects:
        enrollment = date(2026, 1, 12) + timedelta(days=random.randint(0, 120))
        for visit_name, day_offset, window_days in VISIT_SCHEDULE:
            planned = enrollment + timedelta(days=day_offset)
            if sid == DEMO_SUBJECT and visit_name == "Visit 3":
                # Fixed clinical demo deviation: Visit 3 falls 9 days late against a +/-5 day window.
                actual = planned + timedelta(days=9)
            else:
                actual = planned + timedelta(days=random.randint(-window_days, window_days))
            offset = (actual - planned).days
            rows.append({
                "subject_id": sid,
                "visit_name": visit_name,
                "planned_date": planned.isoformat(),
                "visit_window_days": window_days,
                "actual_date": actual.isoformat(),
                "days_offset": offset,
                "within_window": abs(offset) <= window_days,
            })
    path = os.path.join(DATA_DIR, "subject_visits.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Deviation log (both domains)
# ---------------------------------------------------------------------------

def write_deviations():
    rows = [
        {
            "deviation_id": "DEV-2026-0091",
            "domain": "manufacturing",
            "batch_id": DEMO_CASE_ID,
            "subject_id": "",
            "date": DEMO_PROCESS_DATE.isoformat(),
            "equipment_id": DEMO_EQUIPMENT,
            "description": (
                "Drying step temperature excursion: spec 60C +/-5C for 4h, actual peak 72C "
                "sustained for approximately 20 minutes on Oven-04."
            ),
            "status": "open",
        },
        {
            "deviation_id": "DEV-2026-0034",
            "domain": "clinical",
            "batch_id": "",
            "subject_id": DEMO_SUBJECT,
            "date": "2026-04-01",
            "equipment_id": "",
            "description": "Visit 3 conducted 9 days outside the protocol-specified +/-5 day window.",
            "status": "open",
        },
    ]
    other_manu = [b for b in ALL_BATCH_IDS if b != DEMO_CASE_ID]
    for i, bid in enumerate(random.sample(other_manu, k=min(14, len(other_manu)))):
        rows.append({
            "deviation_id": f"DEV-2026-{100 + i:04d}",
            "domain": "manufacturing",
            "batch_id": bid,
            "subject_id": "",
            "date": BATCH_DATE[bid].isoformat(),
            "equipment_id": BATCH_EQUIPMENT[bid],
            "description": random.choice([
                "Minor label reconciliation discrepancy, resolved same shift.",
                "Late entry in batch record, backfilled and countersigned.",
                "Environmental monitoring excursion in staging area, within action limit.",
            ]),
            "status": random.choice(["closed", "closed", "open"]),
        })
    for i in range(12):
        sid = f"S-{1001 + i}"
        rows.append({
            "deviation_id": f"DEV-2026-{200 + i:04d}",
            "domain": "clinical",
            "batch_id": "",
            "subject_id": sid,
            "date": "2026-05-01",
            "equipment_id": "",
            "description": random.choice([
                "Informed consent re-signed after protocol amendment, minor administrative delay.",
                "Lab sample shipped 1 day outside temperature-controlled window.",
                "Concomitant medication log updated retrospectively.",
            ]),
            "status": random.choice(["closed", "closed", "open"]),
        })
    path = os.path.join(DATA_DIR, "deviations.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# PDFs (SOP + protocol) -- small, synthetic, just enough text for Phase 2's BM25 doc server
# ---------------------------------------------------------------------------

def write_pdf(path, title, paragraphs):
    doc = SimpleDocTemplate(path, pagesize=LETTER)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    for p in paragraphs:
        story.append(Paragraph(p, styles["BodyText"]))
        story.append(Spacer(1, 8))
    doc.build(story)


def write_sop_pdf():
    path = os.path.join(DATA_DIR, "SOP-Drying-001.pdf")
    write_pdf(path, "SOP-DRYING-001: Fluid-Bed Drying Step (Synthetic)", [
        "1. Purpose. This SOP defines the drying step parameters for oral solid dosage batches "
        "processed in Oven-01 through Oven-06.",
        "2. Process parameters. Target set point is 60C, with a permitted tolerance of +/-5C "
        "(i.e. 55C to 65C), held for a duration of 4 hours (240 minutes).",
        "3. Equipment qualification. Each oven must undergo preventive maintenance and "
        "recalibration on a 12-month schedule. A batch may not be released if it was processed "
        "on equipment whose most recent service is more than 12 months prior to the process date; "
        "such batches must be flagged for deviation review.",
        "4. Temperature excursion handling. Any excursion above 65C for any duration must be "
        "logged as a deviation. Moisture content testing (spec: 0.0-0.5%) is the primary release "
        "test sensitive to over-drying caused by a high-temperature excursion.",
        "5. This is a synthetic document generated for the DevGuard prototype and does not "
        "describe a real product or process.",
    ])


def write_protocol_pdf():
    path = os.path.join(DATA_DIR, "Protocol-CT-2026-07.pdf")
    write_pdf(path, "Protocol CT-2026-07: Visit Schedule (Synthetic)", [
        "1. Purpose. This excerpt of the study protocol defines the subject visit schedule and "
        "permitted visit windows.",
        "2. Visit schedule. Screening (Day 0, no window), Baseline (Day 14, +/-3 days), Visit 2 "
        "(Day 28, +/-3 days), Visit 3 (Day 56, +/-5 days), Visit 4/End of Treatment (Day 84, "
        "+/-5 days), Follow-up (Day 112, +/-7 days).",
        "3. Deviation handling. Any visit conducted outside its permitted window must be logged "
        "as a protocol deviation and assessed for reportability to the sponsor and IRB/EC, "
        "classified as Major or Minor per the study's deviation classification guide.",
        "4. This is a synthetic document generated for the DevGuard prototype and does not "
        "describe a real study, site, or subject.",
    ])


def main():
    counts = {}
    counts["maintenance.csv"] = write_maintenance()
    counts["equipment_traces.csv"] = write_equipment_traces()
    counts["lab_results.csv"] = write_lab_results()
    counts["subject_visits.csv"] = write_subject_visits()
    counts["deviations.csv"] = write_deviations()
    write_sop_pdf()
    write_protocol_pdf()

    total = sum(counts.values())
    print("Rows written:")
    for name, n in counts.items():
        print(f"  {name}: {n}")
    print(f"  TOTAL: {total}")
    print("PDFs written: SOP-Drying-001.pdf, Protocol-CT-2026-07.pdf")
    assert DEMO_CASE_ID in ALL_BATCH_IDS, "fixed demo case B-2291 missing from batch list"


if __name__ == "__main__":
    main()
