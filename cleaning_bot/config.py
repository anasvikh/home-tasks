from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List

import os


@dataclass(frozen=True)
class BotConfig:
    token: str
    admin_ids: List[int]
    group_chat_id: int


@dataclass(frozen=True)
class SchedulerConfig:
    timezone: str
    daily_notification_time: str
    reminder_time: str
    rotation_start: date
    extended_interval_weeks: int
    general_interval_weeks: int


@dataclass(frozen=True)
class DatabaseConfig:
    path: Path


@dataclass(frozen=True)
class FilesConfig:
    tasks: Path
    users: Path


@dataclass(frozen=True)
class AppConfig:
    bot: BotConfig
    scheduler: SchedulerConfig
    database: DatabaseConfig
    files: FilesConfig


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def load_config(path: Path | str) -> AppConfig:
    try:
        from dotenv import load_dotenv  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - configuration error
        raise RuntimeError(
            "python-dotenv is required to load configuration. Install package 'python-dotenv'."
        ) from exc
    load_dotenv()
    try:  # Local import to keep tests lightweight when PyYAML is absent
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - configuration error
        raise RuntimeError(
            "PyYAML is required to load configuration. Install package 'PyYAML'."
        ) from exc
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    bot_cfg = raw.get("bot", {})
    token_env = bot_cfg.get("token_env", "TELEGRAM_BOT_TOKEN")
    token = os.environ.get(token_env)
    if not token:
        raise RuntimeError(
            f"Bot token is not defined. Provide {token_env} env variable or .env file"
        )

    admin_ids = _ensure_int_list(bot_cfg.get("admin_ids", []))
    group_chat_id = int(bot_cfg.get("group_chat_id"))

    scheduler_cfg = raw.get("scheduler", {})
    scheduler = SchedulerConfig(
        timezone=scheduler_cfg.get("timezone", "UTC"),
        daily_notification_time=scheduler_cfg.get("daily_notification_time", "10:00"),
        reminder_time=scheduler_cfg.get("reminder_time", "20:00"),
        rotation_start=_parse_date(scheduler_cfg.get("rotation_start", "2024-01-01")),
        extended_interval_weeks=int(scheduler_cfg.get("extended_interval_weeks", 5)),
        general_interval_weeks=int(scheduler_cfg.get("general_interval_weeks", 26)),
    )

    db_cfg = raw.get("database", {})
    database = DatabaseConfig(path=Path(db_cfg.get("path", "db.sqlite3")))

    files_cfg = raw.get("files", {})
    files = FilesConfig(
        tasks=Path(files_cfg.get("tasks", "cleaning_bot/tasks.json")),
        users=Path(files_cfg.get("users", "cleaning_bot/users.json")),
    )

    return AppConfig(
        bot=BotConfig(token=token, admin_ids=admin_ids, group_chat_id=group_chat_id),
        scheduler=scheduler,
        database=database,
        files=files,
    )


def _ensure_int_list(values: Iterable) -> List[int]:
    result: List[int] = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError) as exc:  # pragma: no cover - guard clause
            raise ValueError(f"Invalid integer value: {value}") from exc
    return result
