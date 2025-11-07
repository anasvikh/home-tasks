import asyncio
import sys
from datetime import date, datetime
from types import ModuleType, SimpleNamespace


def _build_context(app_ctx):
    application = SimpleNamespace(bot_data={"app_context": app_ctx})
    return SimpleNamespace(application=application)


def _stub_parse_mode(monkeypatch):
    constants_module = ModuleType("telegram.constants")
    constants_module.ParseMode = SimpleNamespace(MARKDOWN="Markdown")
    telegram_module = ModuleType("telegram")
    telegram_module.constants = constants_module
    error_module = ModuleType("telegram.error")

    class DummyError(Exception):
        pass

    error_module.TelegramError = DummyError
    error_module.BadRequest = DummyError
    telegram_module.error = error_module
    monkeypatch.setitem(sys.modules, "telegram.constants", constants_module)
    monkeypatch.setitem(sys.modules, "telegram.error", error_module)
    monkeypatch.setitem(sys.modules, "telegram", telegram_module)

from cleaning_bot import dispatcher
from cleaning_bot.database import Assignment


def test_welcome_on_group_mention_triggers_welcome(monkeypatch):
    called = {}

    async def fake_welcome(update, context):
        called["value"] = True

    monkeypatch.setattr(dispatcher, "welcome", fake_welcome)

    message = SimpleNamespace(
        text="@mr_proper_to_do_bot привет",
        entities=[SimpleNamespace(type="mention", offset=0, length=20)],
    )
    update = SimpleNamespace(effective_message=message)
    context = SimpleNamespace(bot=SimpleNamespace(username="mr_proper_to_do_bot"))

    asyncio.run(dispatcher.welcome_on_group_mention(update, context))

    assert called.get("value") is True


def test_welcome_on_group_mention_ignores_other_mentions(monkeypatch):
    called = {}

    async def fake_welcome(update, context):
        called["value"] = True

    monkeypatch.setattr(dispatcher, "welcome", fake_welcome)

    message = SimpleNamespace(
        text="@someone_else привет",
        entities=[SimpleNamespace(type="mention", offset=0, length=13)],
    )
    update = SimpleNamespace(effective_message=message)
    context = SimpleNamespace(bot=SimpleNamespace(username="mr_proper_to_do_bot"))

    asyncio.run(dispatcher.welcome_on_group_mention(update, context))

    assert called.get("value") is None


def test_tasks_command_private_sends_personal_summary(monkeypatch):
    captured = {}
    stored = {}
    _stub_parse_mode(monkeypatch)

    def fake_ensure(ctx, target):  # noqa: ARG001
        return {42: ["assignment"]}

    monkeypatch.setattr(dispatcher, "ensure_assignments_for_date", fake_ensure)
    monkeypatch.setattr(
        dispatcher, "build_personal_message", lambda a, d, **kwargs: "personal"
    )
    monkeypatch.setattr(dispatcher, "build_keyboard", lambda a: "keyboard")
    monkeypatch.setattr(
        dispatcher,
        "_store_personal_task_message",
        lambda app, day, user_id, message: stored.update(
            {"app": app, "date": day, "user_id": user_id, "message": message}
        ),
    )

    async def reply_text(text, **kwargs):
        captured["text"] = text
        captured["kwargs"] = kwargs
        return SimpleNamespace(chat_id=123, message_id=777)

    app_ctx = SimpleNamespace(users=[], config=None)
    update = SimpleNamespace(
        effective_message=SimpleNamespace(reply_text=reply_text),
        effective_chat=SimpleNamespace(type="private"),
        effective_user=SimpleNamespace(id=42),
    )
    context = _build_context(app_ctx)

    asyncio.run(dispatcher.tasks_command(update, context))

    assert captured["text"] == "personal"
    assert captured["kwargs"]["reply_markup"] == "keyboard"
    assert stored["user_id"] == 42
    assert stored["message"].message_id == 777


def test_tasks_command_group_sends_personal_blocks(monkeypatch):
    calls = []
    _stub_parse_mode(monkeypatch)

    def fake_ensure(ctx, target):  # noqa: ARG001
        return {1: ["assignment-1"], 2: ["assignment-2"]}

    monkeypatch.setattr(dispatcher, "ensure_assignments_for_date", fake_ensure)

    blocks = [
        dispatcher.GroupBlock(text="*Настя*\npersonal", keyboard="keyboard-1", user_id=1),
        dispatcher.GroupBlock(text="*Андрей*\npersonal", keyboard="keyboard-2", user_id=2),
    ]
    monkeypatch.setattr(dispatcher, "build_group_blocks", lambda ctx, data, day: blocks)

    async def reply_text(text, **kwargs):
        calls.append((text, kwargs))
        return SimpleNamespace(chat_id=-100, message_id=len(calls))

    users = [SimpleNamespace(telegram_id=1, name="Настя"), SimpleNamespace(telegram_id=2, name="Андрей")]
    app_ctx = SimpleNamespace(users=users, config=None)
    update = SimpleNamespace(
        effective_message=SimpleNamespace(reply_text=reply_text),
        effective_chat=SimpleNamespace(type="group"),
        effective_user=SimpleNamespace(id=42),
    )
    context = _build_context(app_ctx)
    context.application.bot = SimpleNamespace()

    asyncio.run(dispatcher.tasks_command(update, context))

    assert len(calls) == 2
    assert calls[0][0] == "*Настя*\npersonal"
    assert calls[1][0] == "*Андрей*\npersonal"
    assert calls[0][1]["reply_markup"] == "keyboard-1"


def test_tasks_command_group_handles_empty(monkeypatch):
    calls = []
    _stub_parse_mode(monkeypatch)

    monkeypatch.setattr(dispatcher, "ensure_assignments_for_date", lambda ctx, target: {})
    monkeypatch.setattr(dispatcher, "build_group_blocks", lambda ctx, data, day: [])

    async def reply_text(text, **kwargs):
        calls.append((text, kwargs))

    app_ctx = SimpleNamespace(users=[], config=None)
    update = SimpleNamespace(
        effective_message=SimpleNamespace(reply_text=reply_text),
        effective_chat=SimpleNamespace(type="group"),
        effective_user=SimpleNamespace(id=42),
    )
    context = _build_context(app_ctx)

    asyncio.run(dispatcher.tasks_command(update, context))

    assert calls == [("Сегодня задач нет.", {"parse_mode": "Markdown"})]


def test_build_personal_message_hides_completed_for_groups():
    task_date = date(2024, 1, 1)
    assignments = [
        Assignment(
            id=1,
            task_date=task_date,
            user_id=1,
            room="Кухня",
            level="базовый минимум",
            description="Помыть пол",
            completed=False,
            completed_at=None,
        ),
        Assignment(
            id=2,
            task_date=task_date,
            user_id=1,
            room="Кухня",
            level="легкая уборка",
            description="Протереть стол",
            completed=True,
            completed_at=None,
        ),
    ]

    text = dispatcher.build_personal_message(
        assignments,
        task_date,
        include_completed=False,
    )

    assert "Помыть пол" in text
    assert "Протереть стол" not in text


def test_build_personal_message_reports_no_tasks_when_all_done():
    task_date = date(2024, 1, 1)
    assignments = [
        Assignment(
            id=1,
            task_date=task_date,
            user_id=1,
            room="Кухня",
            level="базовый минимум",
            description="Помыть пол",
            completed=True,
            completed_at=None,
        )
    ]

    text = dispatcher.build_personal_message(
        assignments,
        task_date,
        include_completed=False,
    )

    assert "Нет задач 🎉" in text
    assert "Помыть пол" not in text


def test_send_daily_notifications_posts_greeting_and_blocks(monkeypatch):
    _stub_parse_mode(monkeypatch)

    app_ctx = SimpleNamespace(
        users=[SimpleNamespace(telegram_id=1, name="Настя")],
        config=SimpleNamespace(bot=SimpleNamespace(group_chat_id=-100)),
        db=SimpleNamespace(),
    )

    monkeypatch.setattr(
        dispatcher,
        "ensure_assignments_for_date",
        lambda ctx, target: {1: ["assignment"]},
    )

    block = dispatcher.GroupBlock(text="*Настя*\ntext", keyboard="keyboard", user_id=1)
    monkeypatch.setattr(dispatcher, "build_group_blocks", lambda ctx, data, day: [block])
    monkeypatch.setattr(dispatcher, "build_morning_greeting", lambda day: "greeting")

    sent = []

    async def fake_send_message(**kwargs):
        sent.append(kwargs)
        return SimpleNamespace(chat_id=kwargs["chat_id"], message_id=len(sent))

    app = SimpleNamespace(
        bot_data={"app_context": app_ctx},
        bot=SimpleNamespace(send_message=fake_send_message),
    )

    asyncio.run(dispatcher.send_daily_notifications(app))

    assert sent[0]["chat_id"] == -100
    assert sent[0]["text"] == "greeting"
    assert sent[1]["text"] == "*Настя*\ntext"
    assert sent[1]["reply_markup"] == "keyboard"


def test_send_daily_notifications_handles_empty_assignments(monkeypatch):
    _stub_parse_mode(monkeypatch)

    app_ctx = SimpleNamespace(
        users=[],
        config=SimpleNamespace(bot=SimpleNamespace(group_chat_id=-100)),
        db=SimpleNamespace(),
    )

    monkeypatch.setattr(
        dispatcher,
        "ensure_assignments_for_date",
        lambda ctx, target: {},
    )
    monkeypatch.setattr(dispatcher, "build_group_blocks", lambda ctx, data, day: [])
    monkeypatch.setattr(dispatcher, "build_morning_greeting", lambda day: "greeting")

    sent = []

    async def fake_send_message(**kwargs):
        sent.append(kwargs)
        return SimpleNamespace(chat_id=kwargs.get("chat_id", 0), message_id=len(sent))

    app = SimpleNamespace(
        bot_data={"app_context": app_ctx},
        bot=SimpleNamespace(send_message=fake_send_message),
    )

    asyncio.run(dispatcher.send_daily_notifications(app))

    assert sent[0]["text"] == "greeting"
    assert sent[1]["text"] == "Сегодня задач нет."


def test_send_evening_reminders_store_personal_message(monkeypatch):
    _stub_parse_mode(monkeypatch)

    today = date(2024, 1, 1)
    monkeypatch.setattr(
        dispatcher,
        "datetime",
        SimpleNamespace(now=lambda: datetime(2024, 1, 1)),
    )

    assignments = [SimpleNamespace(id=1)]

    class FakeDB:
        def list_incomplete_for_user(self, task_date, user_id):
            assert task_date == today
            if user_id == 1:
                return assignments
            return []

    monkeypatch.setattr(dispatcher, "format_levels_line", lambda items: "levels")
    monkeypatch.setattr(dispatcher, "format_assignments", lambda items: "assignments")
    monkeypatch.setattr(dispatcher, "build_keyboard", lambda items: "keyboard")

    stored = {}

    def store_personal(app, day, user_id, message):
        stored["app"] = app
        stored["date"] = day
        stored["user_id"] = user_id
        stored["message"] = message

    monkeypatch.setattr(dispatcher, "_store_personal_task_message", store_personal)

    sent = []

    async def fake_send_message(**kwargs):
        sent.append(kwargs)
        return SimpleNamespace(chat_id=kwargs["chat_id"], message_id=100 + len(sent))

    app_ctx = SimpleNamespace(
        users=[SimpleNamespace(telegram_id=1, name="Настя")],
        db=FakeDB(),
    )
    app = SimpleNamespace(
        bot_data={"app_context": app_ctx},
        bot=SimpleNamespace(send_message=fake_send_message),
    )

    asyncio.run(dispatcher.send_evening_reminders(app))

    assert sent[0]["chat_id"] == 1
    assert sent[0]["reply_markup"] == "keyboard"
    assert stored["user_id"] == 1
    assert stored["date"] == today
    assert stored["message"].message_id == 101


def test_send_daily_report_uses_formatter(monkeypatch):
    _stub_parse_mode(monkeypatch)

    rows = [("ignored",)]
    app_ctx = SimpleNamespace(
        db=SimpleNamespace(daily_stats=lambda start, end: rows),
        config=SimpleNamespace(bot=SimpleNamespace(group_chat_id=-100)),
    )

    monkeypatch.setattr(dispatcher, "format_daily_report", lambda day, rows: "report")

    sent = []

    async def fake_send_message(**kwargs):
        sent.append(kwargs)
        return SimpleNamespace(chat_id=kwargs.get("chat_id", 0), message_id=len(sent))

    app = SimpleNamespace(
        bot_data={"app_context": app_ctx},
        bot=SimpleNamespace(send_message=fake_send_message),
    )

    asyncio.run(dispatcher.send_daily_report(app))

    assert sent[0]["text"] == "report"


def test_stats_command_uses_daily_stats(monkeypatch):
    calls = []
    _stub_parse_mode(monkeypatch)

    rows = [(1, "Настя", date(2024, 1, 1), 3, 4)]
    monkeypatch.setattr(dispatcher, "format_stats", lambda label, r, mode: f"{label}:{mode}")

    class FakeDB:
        def daily_stats(self, start, end):  # noqa: ARG002
            return rows

    app_ctx = SimpleNamespace(db=FakeDB(), users=[], config=None)

    async def reply_text(text, **kwargs):
        calls.append((text, kwargs))

    update = SimpleNamespace(
        effective_message=SimpleNamespace(reply_text=reply_text),
        effective_chat=SimpleNamespace(type="private"),
    )
    context = _build_context(app_ctx)

    asyncio.run(dispatcher.stats_command(update, context))

    assert "неделю:week" in calls[0][0]
    assert "месяц:month" in calls[0][0]


def test_on_task_completed_updates_group_message(monkeypatch):
    _stub_parse_mode(monkeypatch)

    today = date(2024, 1, 1)
    monkeypatch.setattr(
        dispatcher,
        "datetime",
        SimpleNamespace(now=lambda: datetime(2024, 1, 1)),
    )

    assignment = Assignment(
        id=1,
        task_date=today,
        user_id=1,
        room="Кухня",
        level="базовый минимум",
        description="Проверить мусор",
        completed=False,
        completed_at=None,
    )

    class FakeDB:
        def __init__(self):
            self.completed = []

        def get_assignment(self, assignment_id):
            assert assignment_id == 1
            return assignment

        def mark_completed(self, assignment_id):
            self.completed.append(assignment_id)
            assignment.completed = True

        def list_assignments_for_user(self, task_date, user_id):
            assert task_date == today
            assert user_id == 1
            return [assignment]

    monkeypatch.setattr(
        dispatcher, "build_personal_message", lambda a, d, **kwargs: "updated"
    )
    monkeypatch.setattr(dispatcher, "build_keyboard", lambda a: "keyboard")

    edited = {}

    async def edit_message_text(**kwargs):
        edited.update(kwargs)

    bot_edits = []

    async def edit_bot_message(**kwargs):
        bot_edits.append(kwargs)

    answers = []

    async def answer(text=None, **kwargs):
        answers.append((text, kwargs))

    message = SimpleNamespace(
        text="*Настя*\nстарый текст",
        chat=SimpleNamespace(type="group"),
        edit_message_text=edit_message_text,
    )

    query = SimpleNamespace(
        data="task_done:1",
        from_user=SimpleNamespace(id=1),
        message=message,
        answer=answer,
        edit_message_text=edit_message_text,
    )

    app_ctx = SimpleNamespace(
        db=FakeDB(),
        users=[SimpleNamespace(telegram_id=1, name="Настя")],
    )
    context = _build_context(app_ctx)
    context.application.bot = SimpleNamespace(edit_message_text=edit_bot_message)
    context.application.bot_data["group_task_messages"] = {
        (today.isoformat(), 1): dispatcher.GroupTaskMessage(chat_id=-100, message_id=555)
    }
    context.application.bot_data["personal_task_messages"] = {
        (today.isoformat(), 1): dispatcher.PersonalTaskMessage(chat_id=1, message_id=999)
    }
    update = SimpleNamespace(callback_query=query)

    asyncio.run(dispatcher.on_task_completed(update, context))

    assert answers[0] == (None, {})
    assert edited["text"] == "*Настя*\nupdated"
    assert edited["reply_markup"] == "keyboard"
    assert app_ctx.db.completed == [1]
    assert bot_edits[0]["chat_id"] == -100
    assert bot_edits[0]["message_id"] == 555
    assert bot_edits[0]["text"] == "*Настя*\nupdated"
    assert bot_edits[0]["reply_markup"] == "keyboard"
    assert bot_edits[1]["chat_id"] == 1
    assert bot_edits[1]["message_id"] == 999
    assert bot_edits[1]["text"] == "updated"
    assert bot_edits[1]["reply_markup"] == "keyboard"


def test_on_task_completed_rejects_foreign_tasks(monkeypatch):
    _stub_parse_mode(monkeypatch)

    today = date(2024, 1, 1)
    monkeypatch.setattr(
        dispatcher,
        "datetime",
        SimpleNamespace(now=lambda: datetime(2024, 1, 1)),
    )

    assignment = Assignment(
        id=1,
        task_date=today,
        user_id=1,
        room="Кухня",
        level="базовый минимум",
        description="Проверить мусор",
        completed=False,
        completed_at=None,
    )

    class FakeDB:
        def get_assignment(self, assignment_id):
            assert assignment_id == 1
            return assignment

    answers = []

    async def answer(text=None, **kwargs):
        answers.append((text, kwargs))

    async def edit_message_text(**kwargs):  # pragma: no cover - should not be called
        raise AssertionError("edit_message_text should not be called")

    message = SimpleNamespace(
        text="*Андрей*\nстарый текст",
        chat=SimpleNamespace(type="group"),
        edit_message_text=edit_message_text,
    )

    query = SimpleNamespace(
        data="task_done:1",
        from_user=SimpleNamespace(id=2),
        message=message,
        answer=answer,
        edit_message_text=edit_message_text,
    )

    app_ctx = SimpleNamespace(
        db=FakeDB(),
        users=[SimpleNamespace(telegram_id=1, name="Настя")],
    )
    context = _build_context(app_ctx)
    update = SimpleNamespace(callback_query=query)

    asyncio.run(dispatcher.on_task_completed(update, context))

    assert answers == [("Эта задача закреплена за другим участником.", {"show_alert": True})]
