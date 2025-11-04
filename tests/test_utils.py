from datetime import date

from cleaning_bot.database import Assignment
from cleaning_bot.utils import format_assignments, format_levels_line


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
