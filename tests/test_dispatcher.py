import asyncio
from types import SimpleNamespace

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
