from __future__ import annotations

from datetime import datetime, time
from typing import Callable

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import SchedulerConfig
from .dispatcher import (
    send_daily_notifications,
    send_daily_report,
    send_evening_reminders,
)


class BotScheduler:
    def __init__(self, cfg: SchedulerConfig):
        timezone = pytz.timezone(cfg.timezone)
        self._cfg = cfg
        self._scheduler = AsyncIOScheduler(timezone=timezone)

    def start(self, app) -> None:
        daily_time = _parse_time(self._cfg.daily_notification_time)
        reminder_time = _parse_time(self._cfg.reminder_time)
        report_time = _parse_time(self._cfg.report_time)
        self._scheduler.add_job(
            send_daily_notifications,
            trigger="cron",
            hour=daily_time.hour,
            minute=daily_time.minute,
            args=[app],
            id="daily_tasks",
            replace_existing=True,
        )
        self._scheduler.add_job(
            send_evening_reminders,
            trigger="cron",
            hour=reminder_time.hour,
            minute=reminder_time.minute,
            args=[app],
            id="evening_reminder",
            replace_existing=True,
        )
        self._scheduler.add_job(
            send_daily_report,
            trigger="cron",
            hour=report_time.hour,
            minute=report_time.minute,
            args=[app],
            id="daily_report",
            replace_existing=True,
        )
        self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown()


def _parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()
