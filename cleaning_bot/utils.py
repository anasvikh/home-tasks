from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, Iterable, List

from .database import Assignment


def format_assignments(assignments: Iterable[Assignment]) -> str:
    grouped: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    for assignment in assignments:
        grouped[assignment.room][assignment.level].append(_format_task_line(assignment))

    lines: List[str] = []
    for room in sorted(grouped.keys()):
        lines.append(f"🏠 *{room}*")
        for level in sorted(grouped[room].keys()):
            lines.append(f"  • _{level}_")
            for task in grouped[room][level]:
                lines.append(f"    - {task}")
    return "\n".join(lines) if lines else "Нет задач 🎉"


def _format_task_line(assignment: Assignment) -> str:
    status = "✅" if assignment.completed else "⬜️"
    return f"{status} {assignment.description}"


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
