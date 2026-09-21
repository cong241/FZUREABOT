from __future__ import annotations

import argparse
import sys
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Sequence

from qqbot.gui import DutyBotWindow
from qqbot.napcat import NapCatClient, NapCatEndpoint
from qqbot.service import ReminderResult, ReminderService
from qqbot.storage import (
    load_roster,
    load_sent_dates,
    load_settings,
    save_sent_dates,
)


class Application:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.settings_path = base_dir / "settings.json"
        self.roster_path = base_dir / "roster.json"
        self.sent_path = base_dir / "sent_reminders.json"

    def _service(self, *, with_client: bool) -> ReminderService:
        settings = load_settings(self.settings_path)
        roster = load_roster(self.roster_path)
        sent_dates = load_sent_dates(self.sent_path)
        if with_client:
            endpoint = NapCatEndpoint.from_config(Path(settings.napcat_config))
            client_factory = lambda: NapCatClient(endpoint)
        else:
            client_factory = lambda: (_ for _ in ()).throw(
                RuntimeError("预览模式不允许创建网络客户端")
            )
        return ReminderService(
            settings,
            roster,
            sent_dates,
            client_factory=client_factory,
            persist_sent=lambda dates: save_sent_dates(self.sent_path, dates),
        )

    def preview(self, duty_date: date) -> ReminderResult:
        return self._service(with_client=False).preview(duty_date)

    def send(self, duty_date: date, force: bool = False) -> ReminderResult:
        return self._service(with_client=True).send(duty_date, force=force)

    def run_gui(self) -> None:
        root = tk.Tk()
        DutyBotWindow(root, self.base_dir)
        root.mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QQ 值班提醒机器人")
    parser.add_argument("--dry-run", action="store_true", help="只显示明天的值班人，不发送")
    parser.add_argument("--send-now", action="store_true", help="立即发送明天的值班提醒")
    parser.add_argument("--force", action="store_true", help="配合 --send-now 强制重发")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    app_factory: Callable[[Path], object] = Application,
    today_provider: Callable[[], date] = date.today,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.force and not args.send_now:
        print("--force 只能和 --send-now 一起使用", file=sys.stderr)
        return 2
    if args.dry_run and args.send_now:
        print("--dry-run 和 --send-now 不能同时使用", file=sys.stderr)
        return 2

    base_dir = Path(__file__).resolve().parent
    try:
        app = app_factory(base_dir)
        tomorrow = today_provider() + timedelta(days=1)
        if args.dry_run:
            result = app.preview(tomorrow)
            print(result.message)
            return 0 if result.status in {"preview", "skipped"} else 1
        if args.send_now:
            result = app.send(tomorrow, force=args.force)
            print(result.message)
            return 0 if result.status in {"sent", "skipped"} else 1
        app.run_gui()
        return 0
    except Exception as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

