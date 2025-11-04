from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, Iterable, List, Sequence, Tuple

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


def format_stats(period_label: str, rows: Sequence[Tuple[int, str, date, int, int]], *, mode: str) -> str:
    grouped: Dict[str, List[Tuple[date, int, int]]] = defaultdict(list)
    for _, name, task_date, completed, total in rows:
        grouped[name].append((task_date, completed, total))

    header = f"📊 Статистика за {period_label}"
    if not grouped:
        return f"{header}\nПока нет данных"

    lines = [header]
    for name in sorted(grouped.keys()):
        lines.append(f"*{name}*")
        for task_date, completed, total in sorted(grouped[name], key=lambda item: item[0]):
            label = _format_day_label(task_date, mode)
            emoji = _progress_emoji(completed, total)
            lines.append(f"{label} — {completed}/{total} {emoji}")
        lines.append("")

    return "\n".join(lines).strip()


def _format_day_label(task_date: date, mode: str) -> str:
    if mode == "week":
        weekday_labels = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
        return weekday_labels[task_date.weekday()]
    return task_date.strftime("%d.%m")


def _progress_emoji(completed: int, total: int) -> str:
    if total == 0:
        return "-"
    if completed == 0:
        return "😡"
    ratio = completed / total
    if ratio < 0.5:
        return "😞"
    if ratio == 0.5:
        return "😐"
    if completed == total:
        return "✅"
    return "🙂"


def _levels_for_assignments(assignments: Iterable[Assignment]) -> List[str]:
    assignments_list = list(assignments)
    available = {assignment.level for assignment in assignments_list}
    if not available:
        return []
    max_index = max(LEVEL_ORDER.index(level) for level in available)
    return list(LEVEL_ORDER[: max_index + 1])
