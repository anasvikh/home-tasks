from datetime import date

import pytest

from cleaning_bot.config import SchedulerConfig
from cleaning_bot.rotation import (
    LEVEL_DAILY,
    LEVEL_EXTENDED,
    LEVEL_GENERAL,
    LEVEL_LIGHT,
    LEVEL_REGULAR,
    get_day_levels,
    rotate_rooms,
    weeks_between,
)
from cleaning_bot.data_loaders import User


def make_config():
    return SchedulerConfig(
        timezone="UTC",
        daily_notification_time="10:00",
        reminder_time="20:00",
        rotation_start=date(2024, 1, 1),
        extended_interval_weeks=5,
        general_interval_weeks=26,
    )


def test_get_day_levels_basic():
    cfg = make_config()
    monday = date(2024, 1, 1)
    assert get_day_levels(monday, cfg) == [LEVEL_DAILY]


def test_get_day_levels_wednesday_light():
    cfg = make_config()
    wednesday = date(2024, 1, 3)
    assert LEVEL_LIGHT in get_day_levels(wednesday, cfg)


def test_get_day_levels_weekend_regular():
    cfg = make_config()
    saturday = date(2024, 1, 6)
    levels = get_day_levels(saturday, cfg)
    assert LEVEL_REGULAR in levels
    assert LEVEL_GENERAL not in levels


def test_get_day_levels_extended_every_fifth_week():
    cfg = make_config()
    # 5 weeks after start -> extended cleaning
    target = date(2024, 2, 3)
    levels = get_day_levels(target, cfg)
    assert LEVEL_EXTENDED in levels


def test_get_day_levels_general_every_26_weeks():
    cfg = make_config()
    target = date(2024, 6, 29)
    levels = get_day_levels(target, cfg)
    assert LEVEL_GENERAL in levels
    assert LEVEL_EXTENDED not in levels


def test_rotate_rooms_round_robin():
    users = [User(telegram_id=1, name="A"), User(telegram_id=2, name="B")]
    rooms = ["Кухня", "Ванная", "Туалет"]
    assignments = rotate_rooms(users, rooms, week_index=1)
    assert assignments[1] == ["Ванная"]
    assert assignments[2] == ["Кухня", "Туалет"]


def test_weeks_between_before_start():
    cfg = make_config()
    assert weeks_between(cfg.rotation_start, date(2023, 12, 1)) == 0
