import json
from datetime import date

import pytest

from qqbot.models import DutyEntry, Settings
from qqbot.storage import (
    load_roster,
    load_sent_dates,
    load_settings,
    next_workday,
    save_roster,
    save_sent_dates,
)


def test_save_roster_sorts_by_date_and_round_trips(tmp_path):
    path = tmp_path / "roster.json"
    entries = [
        DutyEntry(date(2026, 9, 24), 1, "乙"),
        DutyEntry(date(2026, 9, 23), 2, "甲"),
    ]
    save_roster(path, entries)
    assert [x.duty_date.isoformat() for x in load_roster(path)] == [
        "2026-09-23",
        "2026-09-24",
    ]


def test_duplicate_duty_date_is_rejected(tmp_path):
    path = tmp_path / "roster.json"
    entries = [
        DutyEntry(date(2026, 9, 23), 1, "甲"),
        DutyEntry(date(2026, 9, 23), 2, "乙"),
    ]
    with pytest.raises(ValueError, match="重复日期"):
        save_roster(path, entries)


def test_invalid_qq_and_blank_name_are_rejected():
    with pytest.raises(ValueError, match="QQ"):
        DutyEntry(date(2026, 9, 23), 0, "甲")
    with pytest.raises(ValueError, match="姓名"):
        DutyEntry(date(2026, 9, 23), 1, " ")


def test_corrupt_json_is_not_overwritten(tmp_path):
    path = tmp_path / "roster.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="无法读取"):
        load_roster(path)
    assert path.read_text(encoding="utf-8") == "{broken"


def test_settings_round_trip_from_json(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "robot_qq": 3851479069,
                "group_id": 1094289617,
                "send_time": "20:00",
                "napcat_config": "C:/onebot.json",
            }
        ),
        encoding="utf-8",
    )
    assert load_settings(path) == Settings(
        robot_qq=3851479069,
        group_id=1094289617,
        send_time="20:00",
        napcat_config="C:/onebot.json",
    )


def test_sent_dates_are_sorted_and_unique(tmp_path):
    path = tmp_path / "sent.json"
    save_sent_dates(path, {"2026-09-24", "2026-09-23", "2026-09-24"})
    assert load_sent_dates(path) == {"2026-09-23", "2026-09-24"}


def test_next_workday_skips_weekend():
    assert next_workday(date(2026, 9, 25)) == date(2026, 9, 28)
    assert next_workday(date(2026, 9, 24)) == date(2026, 9, 25)
