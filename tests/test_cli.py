from datetime import date

from QQBot import main
from qqbot.models import DutyEntry
from qqbot.service import ReminderResult


class FakeApplication:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.client_created = False
        self.gui_opened = False
        self.send_args = None

    def preview(self, duty_date):
        return ReminderResult(
            "preview",
            "郭子旋（QQ 3060569778）将在 2026-09-23 值班",
            entry=DutyEntry(date(2026, 9, 23), 3060569778, "郭子旋"),
        )

    def send(self, duty_date, force=False):
        self.client_created = True
        self.send_args = (duty_date, force)
        return ReminderResult("sent", "发送成功")

    def run_gui(self):
        self.gui_opened = True


def test_dry_run_prints_target_without_creating_client(capsys):
    created = []

    def factory(base_dir):
        app = FakeApplication(base_dir)
        created.append(app)
        return app

    code = main(
        ["--dry-run"],
        app_factory=factory,
        today_provider=lambda: date(2026, 9, 22),
    )
    assert code == 0
    assert "郭子旋" in capsys.readouterr().out
    assert created[0].client_created is False


def test_force_requires_send_now(capsys):
    assert main(["--force"], app_factory=FakeApplication) != 0
    assert "--force 只能和 --send-now 一起使用" in capsys.readouterr().err


def test_send_now_passes_force_and_tomorrow():
    created = []

    def factory(base_dir):
        app = FakeApplication(base_dir)
        created.append(app)
        return app

    code = main(
        ["--send-now", "--force"],
        app_factory=factory,
        today_provider=lambda: date(2026, 9, 22),
    )
    assert code == 0
    assert created[0].send_args == (date(2026, 9, 23), True)


def test_default_opens_gui():
    created = []

    def factory(base_dir):
        app = FakeApplication(base_dir)
        created.append(app)
        return app

    assert main([], app_factory=factory) == 0
    assert created[0].gui_opened is True
