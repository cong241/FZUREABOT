from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Iterable, Protocol

from .models import DutyEntry, Settings
from .napcat import NapCatError


class ReminderClient(Protocol):
    def get_login_info(self) -> dict: ...
    def get_group_member_info(self, group_id: int, user_id: int) -> dict: ...
    def send_group_reminder(self, group_id: int, user_id: int) -> dict: ...


@dataclass(frozen=True, slots=True)
class ReminderResult:
    status: str
    message: str
    entry: DutyEntry | None = None
    message_id: int | None = None
    actual_card: str = ""


class ReminderService:
    def __init__(
        self,
        settings: Settings,
        roster: Iterable[DutyEntry],
        sent_dates: set[str],
        *,
        client_factory: Callable[[], ReminderClient],
        persist_sent: Callable[[set[str]], None],
    ) -> None:
        self.settings = settings
        self.roster = {entry.duty_date: entry for entry in roster}
        self.sent_dates = sent_dates
        self.client_factory = client_factory
        self.persist_sent = persist_sent

    def preview(self, duty_date: date) -> ReminderResult:
        entry = self.roster.get(duty_date)
        if entry is None:
            return ReminderResult("skipped", f"{duty_date.isoformat()} 没有排班")
        return ReminderResult(
            "preview",
            f"{entry.name}（QQ {entry.qq}）将在 {duty_date.isoformat()} 值班",
            entry=entry,
        )

    def send(self, duty_date: date, *, force: bool = False) -> ReminderResult:
        preview = self.preview(duty_date)
        if preview.entry is None:
            return preview
        entry = preview.entry
        key = duty_date.isoformat()
        if key in self.sent_dates and not force:
            return ReminderResult(
                "skipped", f"{key} 已经提醒过，未重复发送", entry=entry
            )
        try:
            client = self.client_factory()
            login = client.get_login_info()
            actual_qq = int(login.get("user_id", 0))
            if actual_qq != self.settings.robot_qq:
                return ReminderResult(
                    "error",
                    f"机器人账号不符：需要 {self.settings.robot_qq}，实际 {actual_qq}",
                    entry=entry,
                )
            member = client.get_group_member_info(self.settings.group_id, entry.qq)
            actual_card = str(member.get("card") or member.get("nickname") or entry.name)
            sent = client.send_group_reminder(self.settings.group_id, entry.qq)
        except (NapCatError, ValueError, OSError) as exc:
            return ReminderResult("error", f"发送失败：{exc}", entry=entry)

        self.sent_dates.add(key)
        try:
            self.persist_sent(self.sent_dates)
        except (ValueError, OSError) as exc:
            return ReminderResult(
                "error",
                f"消息已发送，但发送记录保存失败：{exc}",
                entry=entry,
                message_id=sent.get("message_id"),
                actual_card=actual_card,
            )
        return ReminderResult(
            "sent",
            f"已提醒 {actual_card}（{key} 值班）",
            entry=entry,
            message_id=sent.get("message_id"),
            actual_card=actual_card,
        )
