from __future__ import annotations

from datetime import date
from typing import Dict, List, Sequence

from .config import SchedulerConfig
from .data_loaders import TaskMap, User


LEVEL_DAILY = "базовый минимум"
LEVEL_LIGHT = "легкая уборка"
LEVEL_REGULAR = "обычная уборка"
LEVEL_EXTENDED = "расширенная уборка"
LEVEL_GENERAL = "генеральная уборка"

LEVEL_ORDER: Sequence[str] = (
    LEVEL_DAILY,
    LEVEL_LIGHT,
    LEVEL_REGULAR,
    LEVEL_EXTENDED,
    LEVEL_GENERAL,
)


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



WEEKLY_ROOM_PLAN: Dict[str, Dict[int, Sequence[str]]] = {
    "odd": {
        0: ("Спальня", "Ванная", "Туалет"),
        1: ("Кабинет", "Кухня", "Коридор"),
    },
    "even": {
        0: ("Спальня", "Кухня", "Коридор"),
        1: ("Кабинет", "Ванная", "Туалет"),
    },
}


def rotate_rooms(
    users: Sequence[User], rooms: Sequence[str], week_index: int, weekday: int
) -> Dict[int, List[str]]:
    if not users:
        raise ValueError("Users list cannot be empty")

    assignments: Dict[int, List[str]] = {user.telegram_id: [] for user in users}
    used_rooms: set[str] = set()

    scheduled = _assign_by_week_table(users, rooms, week_index)
    for user_id, scheduled_rooms in scheduled.items():
        assignments.setdefault(user_id, [])
        assignments[user_id].extend(scheduled_rooms)
        used_rooms.update(scheduled_rooms)

    remaining_rooms = [room for room in rooms if room not in used_rooms]
    if remaining_rooms:
        for idx, room in enumerate(remaining_rooms):
            user = users[(idx + week_index) % len(users)]
            assignments[user.telegram_id].append(room)
    return assignments


def _assign_by_week_table(
    users: Sequence[User], rooms: Sequence[str], week_index: int
) -> Dict[int, List[str]]:
    if len(users) < 2:
        return {}

    week_number = week_index + 1
    plan_key = "odd" if week_number % 2 == 1 else "even"
    plan = WEEKLY_ROOM_PLAN[plan_key]

    assignments: Dict[int, List[str]] = {}
    for user_index, room_list in plan.items():
        if user_index >= len(users):
            continue
        filtered = [room for room in room_list if room in rooms]
        assignments[users[user_index].telegram_id] = filtered
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


def expand_levels(levels: Sequence[str]) -> List[str]:
    if not levels:
        return []

    max_index = -1
    for level in levels:
        try:
            idx = LEVEL_ORDER.index(level)
        except ValueError as exc:  # pragma: no cover - guard clause
            raise ValueError(f"Unknown level: {level}") from exc
        if idx > max_index:
            max_index = idx

    return list(LEVEL_ORDER[: max_index + 1])
