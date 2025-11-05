from datetime import date

from datetime import date

from cleaning_bot.database import Assignment
from cleaning_bot.utils import (
    format_assignments,
    format_daily_report,
    format_levels_line,
    format_stats,
)


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
        _assignment(id=1, room="Кухня", level="базовый минимум", description="Проверить мусор"),
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


def test_format_levels_line_shows_only_highest_level():
    assignments = [
        _assignment(id=1, room="Кухня", level="обычная уборка", description="Помыть плиту"),
        _assignment(id=2, room="Кухня", level="легкая уборка", description="Запустить робота"),
    ]

    text = format_levels_line(assignments)

    assert text == "Сегодня по плану обычная уборка"


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
    assert "Всего — 2/8 (25%) 😞" in monthly


def test_format_stats_handles_empty_rows():
    text = format_stats("неделю", [], mode="week")
    assert text.endswith("Пока нет данных")


def test_format_daily_report_summarises_rows():
    rows = [
        (1, "Настя", date(2024, 1, 1), 5, 5),
        (2, "Андрей", date(2024, 1, 1), 3, 6),
    ]

    text = format_daily_report(date(2024, 1, 1), rows)

    assert "📅 Подведем итоги за 01.01.2024" in text
    assert "• Настя: 5/5 задач выполнено ✅" in text
    assert "• Андрей: 3/6 задач выполнено 😐" in text


def test_format_daily_report_handles_empty():
    text = format_daily_report(date(2024, 1, 1), [])
    assert text.endswith("Нет данных за сегодня.")
