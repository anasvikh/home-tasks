from datetime import date

from cleaning_bot.config import AppConfig, BotConfig, DatabaseConfig, FilesConfig, SchedulerConfig
from cleaning_bot.data_loaders import TaskMap, User
from cleaning_bot.database import Database
from cleaning_bot.dispatcher import AppContext, ensure_assignments_for_date


class DummyAppConfig(AppConfig):
    pass


def build_context(tmp_path):
    scheduler = SchedulerConfig(
        timezone="UTC",
        daily_notification_time="10:00",
        reminder_time="18:00",
        report_time="22:00",
        rotation_start=date(2024, 1, 1),
        extended_interval_weeks=5,
        general_interval_weeks=26,
    )
    config = AppConfig(
        bot=BotConfig(token="token", admin_ids=[1], group_chat_id=-1),
        scheduler=scheduler,
        database=DatabaseConfig(path=tmp_path / "db.sqlite3"),
        files=FilesConfig(tasks=tmp_path / "tasks.json", users=tmp_path / "users.json"),
    )
    tasks: TaskMap = {
        "Кухня": {
            "базовый минимум": ["Задача 1"],
            "легкая уборка": ["Задача 1.5"],
            "обычная уборка": ["Задача 2"],
        }
    }
    users = [User(telegram_id=1, name="Аня")]
    db = Database(config.database.path)
    db.sync_users(users)
    ctx = AppContext(config=config, db=db, users=users, tasks=tasks)
    return ctx


def test_ensure_assignments_creates_records(tmp_path):
    ctx = build_context(tmp_path)
    target = date(2024, 1, 6)  # Saturday -> regular cleaning
    assignments = ensure_assignments_for_date(ctx, target)
    assert 1 in assignments
    # regular уровень включает ежедневный, лёгкий и обычный -> 3 задания
    assert len(assignments[1]) == 3


def test_ensure_assignments_idempotent(tmp_path):
    ctx = build_context(tmp_path)
    target = date(2024, 1, 6)
    first = ensure_assignments_for_date(ctx, target)
    second = ensure_assignments_for_date(ctx, target)
    assert len(first[1]) == len(second[1])
