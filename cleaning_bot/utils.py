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
        lines.append(f"\n{emoji} *{room}*")
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
    assignments_list = list(assignments)
    highest_level = _highest_level_for_assignments(assignments_list)
    if not highest_level:
        return ""
    return f"Сегодня по плану {highest_level}"


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
        entries = sorted(grouped[name], key=lambda item: item[0])
        if mode == "month":
            total_completed = sum(item[1] for item in entries)
            total_tasks = sum(item[2] for item in entries)
            emoji = progress_emoji(total_completed, total_tasks)
            if total_tasks:
                percent = round((total_completed / total_tasks) * 100)
                lines.append(f"Всего — {total_completed}/{total_tasks} ({percent}%) {emoji}")
            else:
                lines.append(f"Всего — 0/0 {emoji}")
        else:
            for task_date, completed, total in entries:
                label = _format_day_label(task_date, mode)
                emoji = progress_emoji(completed, total)
                lines.append(f"{label} — {completed}/{total} {emoji}")
        lines.append("")

    return "\n".join(lines).strip()


def _format_day_label(task_date: date, mode: str) -> str:
    if mode == "week":
        weekday_labels = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
        return weekday_labels[task_date.weekday()]
    return task_date.strftime("%d.%m")


def progress_emoji(completed: int, total: int) -> str:
    if total == 0:
        return "-"
    if completed == 0:
        return "😡"

    ratio = completed / total
    if ratio >= 1:
        return "✅"
    if ratio >= 0.8:
        return "😀"
    if ratio >= 0.6:
        return "🙂"
    if ratio >= 0.4:
        return "😐"
    if ratio >= 0.2:
        return "😕"
    return "😢"


def _highest_level_for_assignments(assignments: Sequence[Assignment]) -> str | None:
    if not assignments:
        return None

    available = {assignment.level for assignment in assignments}
    if not available:
        return None

    try:
        return max(available, key=LEVEL_ORDER.index)
    except ValueError as exc:  # pragma: no cover - guard clause
        raise ValueError("Unknown level in assignments") from exc


def format_daily_report(
    task_date: date, rows: Sequence[Tuple[int, str, date, int, int]]
) -> str:
    header = f"📅 Подведем итоги за {task_date.strftime('%d.%m.%Y')}"
    if not rows:
        return header + "\nНет данных за сегодня."

    totals: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))
    for _, name, _, completed, total in rows:
        prev_completed, prev_total = totals[name]
        totals[name] = (prev_completed + completed, prev_total + total)

    lines = [header]
    for name in sorted(totals.keys()):
        completed, total = totals[name]
        emoji = progress_emoji(completed, total)
        lines.append(f"• {name}: {completed}/{total} задач выполнено {emoji}")
    return "\n".join(lines)
