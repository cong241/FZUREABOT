from datetime import date

import pytest

from qqbot.models import DutyEntry, Settings
from qqbot.napcat import NapCatError
from qqbot.service import ReminderService


class FakeClient:
    def __init__(self):
        self.login_qq = 3851479069
        self.send_error = None
        self.calls = []

    def get_login_info(self):
        self.calls.append("login")
        return {"user_id": self.login_qq, "nickname": "机器人"}

    def get_group_member_info(self, group_id, user_id):
        self.calls.append(f"member:{group_id}:{user_id}")
        return {"group_id": group_id, "user_id": user_id, "card": "25级-电控-郭子旋"}

    def send_group_reminder(self, group_id, user_id):
        self.calls.append(f"send:{group_id}:{user_id}")
        if self.send_error:
            raise self.send_error
        return {"message_id": 42}


@pytest.fixture
def client():
    return FakeClient()


@pytest.fixture
def saved():
    return []


@pytest.fixture
def service(client, saved):
    settings = Settings(3851479069, 1094289617, "20:00", "C:/onebot.json")
    roster = [DutyEntry(date(2026, 9, 23), 3060569778, "郭子旋")]
    return ReminderService(
        settings,
        roster,
        set(),
        client_factory=lambda: client,
        persist_sent=lambda dates: saved.append(set(dates)),
    )


def test_missing_date_returns_skipped(service):
    result = service.send(date(2026, 9, 27))
    assert result.status == "skipped"
    assert "没有排班" in result.message


def test_duplicate_is_blocked_without_calling_client(service, client):
    service.sent_dates.add("2026-09-23")
    result = service.send(date(2026, 9, 23))
    assert result.status == "skipped"
    assert client.calls == []


def test_force_bypasses_duplicate_guard(service, client):
    service.sent_dates.add("2026-09-23")
    assert service.send(date(2026, 9, 23), force=True).status == "sent"


def test_wrong_logged_in_account_blocks_send_and_does_not_record(service, client):
    client.login_qq = 123
    result = service.send(date(2026, 9, 23))
    assert result.status == "error"
    assert "3851479069" in result.message
    assert "2026-09-23" not in service.sent_dates


def test_failed_send_is_not_recorded(service, client):
    client.send_error = NapCatError("failed")
    assert service.send(date(2026, 9, 23)).status == "error"
    assert "2026-09-23" not in service.sent_dates


def test_success_records_date_after_member_check(service, client, saved):
    result = service.send(date(2026, 9, 23))
    assert result.status == "sent"
    assert result.actual_card == "25级-电控-郭子旋"
    assert client.calls == [
        "login",
        "member:1094289617:3060569778",
        "send:1094289617:3060569778",
    ]
    assert "2026-09-23" in service.sent_dates
    assert saved == [{"2026-09-23"}]


def test_preview_never_creates_client(service, client):
    result = service.preview(date(2026, 9, 23))
    assert result.status == "preview"
    assert result.entry.name == "郭子旋"
    assert client.calls == []
