from datetime import date

from cleaning_bot.database import Assignment
from cleaning_bot.utils import format_assignments, format_levels_line, format_stats


def _assignment(
    *,
    id: int,
    room: str,
    level: str,
    description: str,
    completed: bool = False,
):
    return Assignment(
        id=id,
        task_date=date(2024, 1, 1),
        user_id=1,
        room=room,
        level=level,
        description=description,
        completed=completed,
        completed_at=None,
    )


def test_format_assignments_orders_and_decorates_tasks():
    assignments = [
        _assignment(id=1, room="Кухня", level="ежедневный минимум", description="Проверить мусор"),
        _assignment(
            id=2,
            room="Кухня",
            level="обычная уборка",
            description="Помыть плиту",
            completed=True,
        ),
        _assignment(id=3, room="Спальня", level="легкая уборка", description="Подготовить пол"),
    ]

    text = format_assignments(assignments)

    assert "🍽️ *Кухня*" in text
    assert "🛏️ *Спальня*" in text
    assert "✅ Помыть плиту" in text
    assert "⬜️" not in text


def test_format_levels_line_lists_levels_in_order():
    assignments = [
        _assignment(id=1, room="Кухня", level="обычная уборка", description="Помыть плиту"),
        _assignment(id=2, room="Кухня", level="легкая уборка", description="Запустить робота"),
    ]

    text = format_levels_line(assignments)

    assert text == "Уровни уборки: ежедневный минимум, легкая уборка, обычная уборка"


def test_format_stats_renders_weekly_and_monthly_views():
    rows = [
        (1, "Настя", date(2024, 1, 1), 0, 4),
        (1, "Настя", date(2024, 1, 2), 2, 4),
        (2, "Андрей", date(2024, 1, 1), 4, 4),
    ]

    weekly = format_stats("неделю", rows, mode="week")
    monthly = format_stats("месяц", rows, mode="month")

    assert "📊 Статистика за неделю" in weekly
    assert "пн — 0/4 😡" in weekly
    assert "вт — 2/4 😐" in weekly
    assert "✅" in weekly

    assert "📊 Статистика за месяц" in monthly
    assert "01.01 — 0/4 😡" in monthly


def test_format_stats_handles_empty_rows():
    text = format_stats("неделю", [], mode="week")
    assert text.endswith("Пока нет данных")
