from __future__ import annotations

from collections.abc import Callable
from typing import Any

import schedule


class SchedulerController:
    def __init__(
        self,
        send_time: str,
        callback: Callable[[], Any],
        *,
        schedule_module: Any = schedule,
    ) -> None:
        self.send_time = send_time
        self.callback = callback
        self.schedule = schedule_module
        self.job: Any | None = None

    @property
    def running(self) -> bool:
        return self.job is not None

    def start(self) -> Any:
        if self.job is None:
            self.job = self.schedule.every().day.at(self.send_time).do(self.callback)
        return self.job

    def stop(self) -> None:
        if self.job is not None:
            self.schedule.cancel_job(self.job)
            self.job = None

    def run_pending(self) -> None:
        self.schedule.run_pending()

