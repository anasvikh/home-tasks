from __future__ import annotations

import asyncio
from pathlib import Path

from telegram.ext import Application

from .config import load_config
from .data_loaders import load_tasks, load_users
from .database import Database
from .dispatcher import AppContext, register_handlers
from .rotation import (
    LEVEL_DAILY,
    LEVEL_EXTENDED,
    LEVEL_GENERAL,
    LEVEL_LIGHT,
    LEVEL_REGULAR,
    ensure_level_available,
)
from .scheduler import BotScheduler


DEFAULT_CONFIG_PATH = Path("cleaning_bot/config.yaml")


def build_application(config_path: Path | str = DEFAULT_CONFIG_PATH) -> Application:
    cfg = load_config(config_path)
    tasks = load_tasks(cfg.files.tasks)
    users = load_users(cfg.files.users)
    database = Database(cfg.database.path)
    database.sync_users(users)

    for level in [
        LEVEL_DAILY,
        LEVEL_LIGHT,
        LEVEL_REGULAR,
        LEVEL_EXTENDED,
        LEVEL_GENERAL,
    ]:
        ensure_level_available(tasks, level)

    scheduler = BotScheduler(cfg.scheduler)

    async def on_start(app: Application) -> None:
        scheduler.start(app)

    async def on_shutdown(app: Application) -> None:  # pragma: no cover - cleanup
        scheduler.shutdown()

    application = (
        Application.builder()
        .token(cfg.bot.token)
        .post_init(on_start)
        .post_shutdown(on_shutdown)
        .build()
    )

    ctx = AppContext(config=cfg, db=database, users=users, tasks=tasks)
    register_handlers(application, ctx)

    return application


def main() -> None:
    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
