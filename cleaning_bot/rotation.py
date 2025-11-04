from __future__ import annotations

from datetime import date
from typing import Dict, List, Sequence

from .config import SchedulerConfig
from .data_loaders import TaskMap, User


LEVEL_DAILY = "ежедневный минимум"
LEVEL_LIGHT = "легкая уборка"
LEVEL_REGULAR = "обычная уборка"
LEVEL_EXTENDED = "расширенная уборка"
LEVEL_GENERAL = "генеральная уборка"


def get_day_levels(target: date, cfg: SchedulerConfig) -> List[str]:
    weekday = target.weekday()
    levels = [LEVEL_DAILY]
    if weekday == 2:  # Wednesday
        levels.append(LEVEL_LIGHT)

    weeks_since_start = weeks_between(cfg.rotation_start, target)
    week_number = weeks_since_start + 1  # use 1-based counting for recurring events
    general_due = week_number % cfg.general_interval_weeks == 0
    extended_due = week_number % cfg.extended_interval_weeks == 0

    if weekday in (5, 6):  # Saturday/Sunday
        if general_due:
            levels.append(LEVEL_GENERAL)
        elif extended_due:
            levels.append(LEVEL_EXTENDED)
        else:
            levels.append(LEVEL_REGULAR)
    return levels


def weeks_between(start: date, target: date) -> int:
    delta = target - start
    if delta.days < 0:
        return 0
    return delta.days // 7


def rotate_rooms(users: Sequence[User], rooms: Sequence[str], week_index: int) -> Dict[int, List[str]]:
    if not users:
        raise ValueError("Users list cannot be empty")
    assignments: Dict[int, List[str]] = {user.telegram_id: [] for user in users}
    for idx, room in enumerate(rooms):
        user = users[(idx + week_index) % len(users)]
        assignments[user.telegram_id].append(room)
    return assignments


def general_rotation_rooms(rooms: Sequence[str], week_index: int, per_cycle: int = 2) -> List[str]:
    if per_cycle <= 0:
        raise ValueError("per_cycle must be positive")
    start = (week_index * per_cycle) % len(rooms)
    selection = []
    for offset in range(per_cycle):
        selection.append(rooms[(start + offset) % len(rooms)])
    return selection


def ensure_level_available(tasks: TaskMap, level: str) -> None:
    missing = [room for room, room_tasks in tasks.items() if level not in room_tasks]
    if missing:
        raise ValueError(f"Level '{level}' missing for rooms: {', '.join(missing)}")
