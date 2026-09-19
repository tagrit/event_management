"""Plain unittest, no Frappe dependency - runs with:
    python -m unittest event_management.event_management.tests.test_schedule_utils
or directly with a plain `python -m pytest` / `python -m unittest` against
this file's path, since schedule_utils.py imports nothing but datetime.
"""

import unittest
from datetime import datetime, time

from event_management.event_management.schedule_utils import schedule_is_due


# 2026-09-17 is a Thursday, 2026-09-14 is a Monday (verified against a real
# calendar) - used as fixed reference points so the tests are reproducible.
THURSDAY = datetime(2026, 9, 17)
MONDAY = datetime(2026, 9, 14)


class TestScheduleIsDue(unittest.TestCase):
    def test_fires_at_exact_scheduled_time(self):
        now_dt = THURSDAY.replace(hour=14, minute=0)
        self.assertTrue(schedule_is_due(now_dt, "Thursday", time(14, 0), last_run_value=None))

    def test_fires_within_window_after_scheduled_time(self):
        now_dt = THURSDAY.replace(hour=14, minute=10)
        self.assertTrue(schedule_is_due(now_dt, "Thursday", time(14, 0), last_run_value=None))

    def test_does_not_fire_before_scheduled_time(self):
        now_dt = THURSDAY.replace(hour=13, minute=59)
        self.assertFalse(schedule_is_due(now_dt, "Thursday", time(14, 0), last_run_value=None))

    def test_does_not_fire_at_or_after_window_end(self):
        # window_minutes defaults to 15, so 14:15 is the first tick outside it.
        now_dt = THURSDAY.replace(hour=14, minute=15)
        self.assertFalse(schedule_is_due(now_dt, "Thursday", time(14, 0), last_run_value=None))

    def test_last_tick_inside_window_still_fires(self):
        now_dt = THURSDAY.replace(hour=14, minute=14)
        self.assertTrue(schedule_is_due(now_dt, "Thursday", time(14, 0), last_run_value=None))

    def test_does_not_fire_on_wrong_day(self):
        now_dt = MONDAY.replace(hour=14, minute=0)
        self.assertFalse(schedule_is_due(now_dt, "Thursday", time(14, 0), last_run_value=None))

    def test_does_not_fire_twice_same_day(self):
        now_dt = THURSDAY.replace(hour=14, minute=5)
        already_ran_today = str(now_dt.date())
        self.assertFalse(schedule_is_due(now_dt, "Thursday", time(14, 0), last_run_value=already_ran_today))

    def test_fires_again_on_a_later_day_even_if_last_run_is_set(self):
        now_dt = THURSDAY.replace(hour=14, minute=5)
        ran_on_a_previous_thursday = "2026-09-10"
        self.assertTrue(schedule_is_due(now_dt, "Thursday", time(14, 0), last_run_value=ran_on_a_previous_thursday))

    def test_missing_day_or_time_never_fires(self):
        now_dt = THURSDAY.replace(hour=14, minute=0)
        self.assertFalse(schedule_is_due(now_dt, None, time(14, 0), last_run_value=None))
        self.assertFalse(schedule_is_due(now_dt, "Thursday", None, last_run_value=None))

    def test_custom_window_size_is_respected(self):
        now_dt = THURSDAY.replace(hour=9, minute=4)
        self.assertTrue(schedule_is_due(now_dt, "Thursday", time(9, 0), last_run_value=None, window_minutes=5))
        now_dt = THURSDAY.replace(hour=9, minute=6)
        self.assertFalse(schedule_is_due(now_dt, "Thursday", time(9, 0), last_run_value=None, window_minutes=5))

    def test_monday_reminder_schedule_example(self):
        # Mirrors the real config: reminders at Monday 09:00.
        now_dt = MONDAY.replace(hour=9, minute=0)
        self.assertTrue(schedule_is_due(now_dt, "Monday", time(9, 0), last_run_value=None))
        now_dt = MONDAY.replace(hour=8, minute=45)
        self.assertFalse(schedule_is_due(now_dt, "Monday", time(9, 0), last_run_value=None))


if __name__ == "__main__":
    unittest.main()
