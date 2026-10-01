"""IntervalSchedule + CronSchedule unit coverage."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from raft.controller.schedule import CronSchedule, IntervalSchedule


class TestIntervalSchedule:
    def test_next_fire_and_describe(self) -> None:
        sched = IntervalSchedule(15.0)
        when = datetime(2026, 1, 1, 12, 0, 0)
        assert sched.next_fire_after(when) == when + timedelta(seconds=15)
        assert "15" in sched.describe()

    def test_rejects_non_positive(self) -> None:
        with pytest.raises(ValueError, match="interval_seconds"):
            IntervalSchedule(0)

    def test_as_cron_whole_minutes_only(self) -> None:
        assert IntervalSchedule(15.0).as_cron() is None
        assert IntervalSchedule(90.0).as_cron() is None
        cron = IntervalSchedule(60.0).as_cron()
        assert cron is not None
        assert cron.expression == "*/1 * * * *"
        assert IntervalSchedule(300.0).as_cron().expression == "*/5 * * * *"

    def test_as_cron_hourly(self) -> None:
        cron = IntervalSchedule(3600.0).as_cron()
        assert cron is not None
        assert cron.expression == "0 */1 * * *"

    def test_as_cron_rejects_day_scale(self) -> None:
        assert IntervalSchedule(86400.0).as_cron() is None


class TestCronSchedule:
    def test_every_minute(self) -> None:
        sched = CronSchedule("*/1 * * * *")
        when = datetime(2026, 1, 1, 12, 0, 30)
        assert sched.next_fire_after(when) == datetime(2026, 1, 1, 12, 1, 0)

    def test_top_of_hour(self) -> None:
        sched = CronSchedule("0 * * * *")
        when = datetime(2026, 1, 1, 12, 15, 0)
        assert sched.next_fire_after(when) == datetime(2026, 1, 1, 13, 0, 0)

    def test_lists_ranges_steps(self) -> None:
        sched = CronSchedule("0,30 9-11 */2 * 1")
        when = datetime(2026, 1, 5, 8, 0, 0)  # Monday
        nxt = sched.next_fire_after(when)
        assert nxt.minute in (0, 30)
        assert nxt.hour in (9, 10, 11)
        assert "cron" in sched.describe()

    def test_rejects_bad_field_count(self) -> None:
        with pytest.raises(ValueError, match="5 fields"):
            CronSchedule("* * *")

    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            CronSchedule("60 * * * *")

    def test_rejects_inverted_range(self) -> None:
        with pytest.raises(ValueError, match="inverted"):
            CronSchedule("10-5 * * * *")

    def test_rejects_bad_step(self) -> None:
        with pytest.raises(ValueError, match="step"):
            CronSchedule("*/0 * * * *")

    def test_rejects_empty_token(self) -> None:
        with pytest.raises(ValueError, match="empty cron"):
            CronSchedule(", * * * *")

    def test_no_match_within_year(self) -> None:
        # 31 Feb never occurs on the calendar walk.
        sched = CronSchedule("0 0 31 2 *")
        with pytest.raises(ValueError, match="no cron match"):
            sched.next_fire_after(datetime(2026, 1, 1, 0, 0, 0))
