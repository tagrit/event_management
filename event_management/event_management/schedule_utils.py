"""Pure date/time scheduling logic, deliberately free of any Frappe import.

Lets a configurable weekly schedule (day + time, stored on a Setting doctype)
be checked from a frequent cron tick without needing frappe.utils. Kept
dependency-free so it can be unit tested with plain `python -m unittest`,
without a Frappe site - see tests/test_schedule_utils.py.
"""

from datetime import timedelta


def schedule_is_due(now_dt, scheduled_day, scheduled_time, last_run_value, window_minutes=15):
    """Returns True exactly once per matching day: when `now_dt` falls on
    `scheduled_day` and inside the `window_minutes`-wide window starting at
    `scheduled_time`, and it hasn't already fired today per `last_run_value`.

    - now_dt: a datetime.datetime (the current moment).
    - scheduled_day: a weekday name matching now_dt.strftime("%A"), e.g. "Monday".
    - scheduled_time: a datetime.time (already parsed by the caller).
    - last_run_value: "YYYY-MM-DD" string of the last successful run, or None/"".
    - window_minutes: how wide the firing window is; should be >= the interval
      between checks (e.g. the cron cadence calling this) so no tick is missed.
    """
    if not scheduled_day or not scheduled_time:
        return False

    if now_dt.strftime("%A") != scheduled_day:
        return False

    scheduled_dt = now_dt.replace(
        hour=scheduled_time.hour,
        minute=scheduled_time.minute,
        second=0,
        microsecond=0
    )

    window = timedelta(minutes=window_minutes)
    if not (scheduled_dt <= now_dt < scheduled_dt + window):
        return False

    if last_run_value == str(now_dt.date()):
        return False  # already ran for this scheduled slot today

    return True
