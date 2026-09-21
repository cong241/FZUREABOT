from datetime import date

import pytest

from qqbot.gui import parse_entry_fields
from qqbot.scheduler import SchedulerController


class FakeJob:
    def __init__(self, owner):
        self.owner = owner
        self.at_time = None

    @property
    def day(self):
        return self

    def at(self, value):
        self.at_time = value
        self.owner.registered_time = value
        return self

    def do(self, callback):
        self.callback = callback
        return self


class FakeSchedule:
    def __init__(self):
        self.registered_time = None
        self.cancelled = []
        self.pending_runs = 0

    def every(self):
        return FakeJob(self)

    def cancel_job(self, job):
        self.cancelled.append(job)

    def run_pending(self):
        self.pending_runs += 1


def test_scheduler_registers_daily_local_time():
    fake = FakeSchedule()
    controller = SchedulerController("20:00", lambda: None, schedule_module=fake)
    controller.start()
    assert fake.registered_time == "20:00"
    assert controller.running is True


def test_stop_clears_only_its_own_job():
    fake = FakeSchedule()
    controller = SchedulerController("20:00", lambda: None, schedule_module=fake)
    controller.start()
    job = controller.job
    controller.stop()
    assert fake.cancelled == [job]
    assert controller.running is False


def test_start_is_idempotent_and_run_pending_delegates():
    fake = FakeSchedule()
    controller = SchedulerController("20:00", lambda: None, schedule_module=fake)
    first = controller.start()
    second = controller.start()
    controller.run_pending()
    assert first is second
    assert fake.pending_runs == 1


def test_parse_entry_fields_validates_and_normalizes():
    entry = parse_entry_fields("2026-09-23", "3060569778", " 郭子旋 ")
    assert entry.duty_date == date(2026, 9, 23)
    assert entry.qq == 3060569778
    assert entry.name == "郭子旋"


@pytest.mark.parametrize(
    "date_text,qq_text,name,error",
    [
        ("2026/09/23", "1", "甲", "日期"),
        ("2026-09-23", "abc", "甲", "QQ"),
        ("2026-09-23", "1", " ", "姓名"),
    ],
)
def test_parse_entry_fields_rejects_invalid_values(date_text, qq_text, name, error):
    with pytest.raises(ValueError, match=error):
        parse_entry_fields(date_text, qq_text, name)
