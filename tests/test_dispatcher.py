import asyncio
import sys
from datetime import date
from types import ModuleType, SimpleNamespace


def _build_context(app_ctx):
    application = SimpleNamespace(bot_data={"app_context": app_ctx})
    return SimpleNamespace(application=application)


def _stub_parse_mode(monkeypatch):
    constants_module = ModuleType("telegram.constants")
    constants_module.ParseMode = SimpleNamespace(MARKDOWN="Markdown")
    telegram_module = ModuleType("telegram")
    telegram_module.constants = constants_module
    monkeypatch.setitem(sys.modules, "telegram.constants", constants_module)
    monkeypatch.setitem(sys.modules, "telegram", telegram_module)

from cleaning_bot import dispatcher


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
    _stub_parse_mode(monkeypatch)

    def fake_ensure(ctx, target):  # noqa: ARG001
        return {42: ["assignment"]}

    monkeypatch.setattr(dispatcher, "ensure_assignments_for_date", fake_ensure)
    monkeypatch.setattr(dispatcher, "build_personal_message", lambda a, d: "personal")
    monkeypatch.setattr(dispatcher, "build_keyboard", lambda a: "keyboard")

    async def reply_text(text, **kwargs):
        captured["text"] = text
        captured["kwargs"] = kwargs

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


def test_tasks_command_group_sends_personal_blocks(monkeypatch):
    calls = []
    _stub_parse_mode(monkeypatch)

    def fake_ensure(ctx, target):  # noqa: ARG001
        return {1: ["assignment-1"], 2: ["assignment-2"]}

    monkeypatch.setattr(dispatcher, "ensure_assignments_for_date", fake_ensure)
    monkeypatch.setattr(dispatcher, "build_personal_message", lambda a, d: "personal")
    monkeypatch.setattr(dispatcher, "build_keyboard", lambda a: "keyboard")

    async def reply_text(text, **kwargs):
        calls.append((text, kwargs))

    users = [SimpleNamespace(telegram_id=1, name="Настя"), SimpleNamespace(telegram_id=2, name="Андрей")]
    app_ctx = SimpleNamespace(users=users, config=None)
    update = SimpleNamespace(
        effective_message=SimpleNamespace(reply_text=reply_text),
        effective_chat=SimpleNamespace(type="group"),
        effective_user=SimpleNamespace(id=42),
    )
    context = _build_context(app_ctx)

    asyncio.run(dispatcher.tasks_command(update, context))

    assert len(calls) == 2
    assert calls[0][0].startswith("*Настя*\npersonal")
    assert calls[1][0].startswith("*Андрей*\npersonal")
    assert calls[0][1]["reply_markup"] == "keyboard"


def test_tasks_command_group_handles_empty(monkeypatch):
    calls = []
    _stub_parse_mode(monkeypatch)

    monkeypatch.setattr(dispatcher, "ensure_assignments_for_date", lambda ctx, target: {})

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
