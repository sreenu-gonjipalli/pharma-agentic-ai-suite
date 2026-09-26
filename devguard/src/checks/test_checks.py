"""Unit tests for src/checks/ against the fixed B-2291 / S-1042 demo case (PROGRESS.md)."""
import csv
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from checks.excursion import excursion_events  # noqa: E402
from checks.service import service_breach  # noqa: E402
from checks.visit import visit_window_breach  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")


def read_csv(name):
    with open(os.path.join(DATA_DIR, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestExcursion(unittest.TestCase):
    def test_b2291_single_excursion_20min_peak72(self):
        rows = [r for r in read_csv("equipment_traces.csv") if r["batch_id"] == "B-2291"]
        events = excursion_events(rows)
        above = [e for e in events if e["direction"] == "above"]
        self.assertEqual(len(above), 1)
        event = above[0]
        self.assertEqual(event["duration_min"], 20)
        self.assertEqual(event["extreme_temp_c"], 72.0)
        self.assertAlmostEqual(event["magnitude_c"], 7.0)

    def test_in_spec_batch_has_no_excursion(self):
        rows = [r for r in read_csv("equipment_traces.csv") if r["batch_id"] == "B-2293"]
        self.assertEqual(excursion_events(rows), [])


class TestServiceBreach(unittest.TestCase):
    def test_oven04_overdue_for_b2291_process_date(self):
        rows = [r for r in read_csv("maintenance.csv") if r["equipment_id"] == "Oven-04"]
        result = service_breach(rows, "2026-08-01")
        self.assertEqual(result["last_service_date"], "2025-06-01")
        self.assertTrue(result["breach"])
        self.assertAlmostEqual(result["months_since_service"], 14.0, delta=0.2)

    def test_not_overdue_before_next_due_date(self):
        rows = [r for r in read_csv("maintenance.csv") if r["equipment_id"] == "Oven-04"]
        result = service_breach(rows, "2026-01-01")
        self.assertFalse(result["breach"])


class TestVisitWindow(unittest.TestCase):
    def test_visit3_breaches_5day_window_by_9_days(self):
        result = visit_window_breach("2026-06-05", 5, "2026-06-14")
        self.assertTrue(result["breach"])
        self.assertEqual(result["days_offset"], 9)

    def test_visit2_within_3day_window(self):
        result = visit_window_breach("2026-05-08", 3, "2026-05-06")
        self.assertFalse(result["breach"])
        self.assertEqual(result["days_offset"], -2)


if __name__ == "__main__":
    unittest.main()
