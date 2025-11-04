import asyncio
import sys
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


def test_tasks_command_group_sends_summary(monkeypatch):
    captured = {}
    _stub_parse_mode(monkeypatch)

    def fake_ensure(ctx, target):  # noqa: ARG001
        return {}

    monkeypatch.setattr(dispatcher, "ensure_assignments_for_date", fake_ensure)
    monkeypatch.setattr(dispatcher, "build_group_summary", lambda ctx, a, d: "summary")

    async def reply_text(text, **kwargs):
        captured["text"] = text
        captured["kwargs"] = kwargs

    app_ctx = SimpleNamespace(users=[], config=None)
    update = SimpleNamespace(
        effective_message=SimpleNamespace(reply_text=reply_text),
        effective_chat=SimpleNamespace(type="group"),
        effective_user=SimpleNamespace(id=42),
    )
    context = _build_context(app_ctx)

    asyncio.run(dispatcher.tasks_command(update, context))

    assert captured["text"] == "summary"
    assert captured["kwargs"]["parse_mode"]
