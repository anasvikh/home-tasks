from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from .database import Assignment
from .rotation import LEVEL_ORDER


ROOM_EMOJI: Dict[str, str] = {
    "Кухня": "🍽️",
    "Спальня": "🛏️",
    "Кабинет": "💼",
    "Туалет": "🚽",
    "Ванная": "🛁",
    "Коридор": "🚪",
}


def format_assignments(assignments: Iterable[Assignment]) -> str:
    assignments_list = list(assignments)
    if not assignments_list:
        return "Нет задач 🎉"

    grouped: Dict[str, List[Assignment]] = defaultdict(list)
    for assignment in assignments_list:
        grouped[assignment.room].append(assignment)

    lines: List[str] = []
    for room in sorted(grouped.keys()):
        emoji = ROOM_EMOJI.get(room, "🧹")
        lines.append(f"{emoji} *{room}*")
        ordered = sorted(
            grouped[room],
            key=lambda item: (LEVEL_ORDER.index(item.level), item.id),
        )
        for assignment in ordered:
            lines.append(f"  - {_format_task_line(assignment)}")
    return "\n".join(lines)


def _format_task_line(assignment: Assignment) -> str:
    if assignment.completed:
        return f"✅ {assignment.description}"
    return assignment.description


def format_levels_line(assignments: Iterable[Assignment]) -> str:
    levels = _levels_for_assignments(assignments)
    if not levels:
        return ""
    joined = ", ".join(levels)
    return f"Уровни уборки: {joined}"


def format_user_summary(assignments: Iterable[Assignment]) -> str:
    total = 0
    done = 0
    for assignment in assignments:
        total += 1
        if assignment.completed:
            done += 1
    if total == 0:
        return "Нет задач"
    return f"{done}/{total} задач выполнено"


def format_stats(week_label: str, rows: List[tuple[int, str, int, int]]) -> str:
    lines = [f"📊 Статистика за {week_label}"]
    if not rows:
        lines.append("Пока нет данных")
    for _, name, completed, total in rows:
        lines.append(f"• *{name}*: {completed}/{total}")
    return "\n".join(lines)


def _levels_for_assignments(assignments: Iterable[Assignment]) -> List[str]:
    assignments_list = list(assignments)
    available = {assignment.level for assignment in assignments_list}
    if not available:
        return []
    max_index = max(LEVEL_ORDER.index(level) for level in available)
    return list(LEVEL_ORDER[: max_index + 1])
