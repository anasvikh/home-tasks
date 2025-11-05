from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple, TYPE_CHECKING

from .config import AppConfig
from .data_loaders import TaskMap, User
from .database import Assignment, Database
from .rotation import expand_levels, get_day_levels, rotate_rooms, weeks_between
from .utils import (
    format_assignments,
    format_daily_report,
    format_levels_line,
    format_stats,
    format_user_summary,
)

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from telegram import InlineKeyboardMarkup, Update
    from telegram.ext import Application, ContextTypes


@dataclass
class AppContext:
    config: AppConfig
    db: Database
    users: List[User]
    tasks: TaskMap


@dataclass
class GroupTaskMessage:
    chat_id: int
    message_id: int


@dataclass
class PersonalTaskMessage:
    chat_id: int
    message_id: int


def register_handlers(app: "Application", ctx: AppContext) -> None:
    from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

    app.bot_data["app_context"] = ctx
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chatid", chat_id))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            welcome,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & filters.Entity("mention"),
            welcome_on_group_mention,
        )
    )
    app.add_handler(CallbackQueryHandler(on_task_completed, pattern=r"^task_done:"))


async def start(update, context) -> None:
    await welcome(update, context)


async def welcome_on_group_mention(update, context) -> None:
    message = update.effective_message
    if not message or not message.text:
        return

    bot_username = context.bot.username
    if not bot_username:
        return

    bot_mention = f"@{bot_username.lower()}"

    for entity in message.entities or []:
        if entity.type != "mention":
            continue
        mention = message.text[entity.offset : entity.offset + entity.length].lower()
        if mention == bot_mention:
            await welcome(update, context)
            break


async def welcome(update, context) -> None:
    intro = (
        "Привет! Я бот для распределения домашних дел."
        "\n\nКаждое утро я буду отправлять твой список задач с кнопками для отметки"
        " выполнения, а вечером напомню о невыполненных делах."
    )
    hints = [
        "• Используй кнопку ✅ в сообщениях, чтобы отмечать завершённые задания.",
        "• Команда /tasks вернёт актуальный список дел в любой момент.",
        "• Команда /stats покажет прогресс за неделю и месяц.",
    ]
    text = intro + "\n" + "\n".join(hints)
    await update.effective_message.reply_text(text)


async def chat_id(update, context) -> None:
    from telegram.constants import ParseMode

    app_ctx = context.application.bot_data["app_context"]
    user_id = update.effective_user.id if update.effective_user else None
    if user_id not in app_ctx.config.bot.admin_ids:
        await update.message.reply_text("Команда доступна только администраторам бота.")
        return

    chat = update.effective_chat
    chat_id_value = chat.id if chat else "неизвестно"
    lines = [f"ID этого чата: `{chat_id_value}`"]

    if chat and chat.type in {"group", "supergroup"}:
        lines.append(
            "Добавьте это значение в `bot.group_chat_id` внутри `cleaning_bot/config.yaml`,"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def tasks_command(update, context) -> None:
    from telegram.constants import ParseMode

    app_ctx = context.application.bot_data["app_context"]
    today = datetime.now().date()
    assignments_by_user = ensure_assignments_for_date(app_ctx, today)

    chat = update.effective_chat
    message = update.effective_message
    if chat and chat.type == "private":
        user = update.effective_user
        user_id = user.id if user else None
        assignments = (
            assignments_by_user.get(user_id, []) if user_id is not None else []
        )

        if not assignments:
            await message.reply_text(
                "На сегодня для тебя нет назначенных задач.",
            )
            return

        text = build_personal_message(assignments, today)
        keyboard = build_keyboard(assignments)
        sent_message = await message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        _store_personal_task_message(
            context.application,
            today,
            user_id,
            sent_message,
        )
        return

    sent_any = False
    for block in build_group_blocks(app_ctx, assignments_by_user, today):
        sent_message = await message.reply_text(
            block.text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=block.keyboard,
        )
        _store_group_task_message(
            context.application,
            today,
            block.user_id,
            sent_message,
        )
        sent_any = True

    if not sent_any:
        await message.reply_text(
            "Сегодня задач нет.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def stats_command(update, context) -> None:
    from telegram.constants import ParseMode

    app_ctx = context.application.bot_data["app_context"]
    today = datetime.now().date()

    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    month_start = today.replace(day=1)

    week_rows = app_ctx.db.daily_stats(week_start, week_end)
    month_rows = app_ctx.db.daily_stats(month_start, today)

    parts = [
        format_stats("неделю", week_rows, mode="week"),
        format_stats("месяц", month_rows, mode="month"),
    ]
    text = "\n\n".join(part for part in parts if part)
    if not text:
        text = "Пока нет данных для отображения статистики."

    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def on_task_completed(update, context) -> None:
    query = update.callback_query
    app_ctx = context.application.bot_data["app_context"]

    assignment_id = int(query.data.split(":", 1)[1])
    assignment = app_ctx.db.get_assignment(assignment_id)

    if not assignment:
        await query.answer("Не удалось найти задачу. Попробуй ещё раз позже.", show_alert=True)
        return

    user = query.from_user
    if not user or user.id != assignment.user_id:
        await query.answer("Эта задача закреплена за другим участником.", show_alert=True)
        return

    await query.answer()
    app_ctx.db.mark_completed(assignment_id)

    from telegram.constants import ParseMode

    message = query.message
    if not message:
        await _refresh_group_task_message(context, assignment)
        return

    task_date = assignment.task_date
    is_reminder = bool(message.text and message.text.startswith("Напоминаю"))

    if is_reminder:
        remaining = app_ctx.db.list_incomplete_for_user(task_date, assignment.user_id)
        if remaining:
            levels_line = format_levels_line(remaining)
            parts = ["Напоминаю, что сегодня ещё есть невыполненные задачи:"]
            if levels_line:
                parts.append(levels_line)
            parts.append(format_assignments(remaining))
            new_text = "\n".join(parts)
        else:
            new_text = "Все задачи на сегодня выполнены! 🎉"
        keyboard = build_keyboard(remaining)
    else:
        assignments = app_ctx.db.list_assignments_for_user(task_date, assignment.user_id)
        new_text = build_personal_message(assignments, task_date)
        if message.chat and message.chat.type in {"group", "supergroup"}:
            owner_name = next(
                (u.name for u in app_ctx.users if u.telegram_id == assignment.user_id),
                "",
            )
            if owner_name:
                new_text = f"*{owner_name}*\n{new_text}"
        keyboard = build_keyboard(assignments)

    await query.edit_message_text(
        text=new_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )

    await _refresh_group_task_message(context, assignment)
    await _refresh_personal_task_message(context, assignment)


async def send_daily_notifications(app) -> None:
    from telegram.constants import ParseMode

    ctx: AppContext = app.bot_data["app_context"]
    today = datetime.now().date()
    assignments_by_user = ensure_assignments_for_date(ctx, today)
    group_chat_id = ctx.config.bot.group_chat_id

    greeting = build_morning_greeting(today)
    await app.bot.send_message(
        chat_id=group_chat_id,
        text=greeting,
        parse_mode=ParseMode.MARKDOWN,
    )

    sent_any = False
    for block in build_group_blocks(ctx, assignments_by_user, today):
        sent_message = await app.bot.send_message(
            chat_id=group_chat_id,
            text=block.text,
            reply_markup=block.keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )
        _store_group_task_message(app, today, block.user_id, sent_message)
        sent_any = True

    if not sent_any:
        await app.bot.send_message(
            chat_id=group_chat_id,
            text="Сегодня задач нет.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def send_evening_reminders(app) -> None:
    from telegram.constants import ParseMode

    ctx: AppContext = app.bot_data["app_context"]
    today = datetime.now().date()
    for user in ctx.users:
        incomplete = ctx.db.list_incomplete_for_user(today, user.telegram_id)
        if not incomplete:
            continue
        levels_line = format_levels_line(incomplete)
        parts = ["Напоминаю, что сегодня ещё есть невыполненные задачи:"]
        if levels_line:
            parts.append(levels_line)
        parts.append(format_assignments(incomplete))
        text = "\n".join(parts)
        keyboard = build_keyboard(incomplete)
        sent_message = await app.bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        _store_personal_task_message(app, today, user.telegram_id, sent_message)


async def send_daily_report(app) -> None:
    from telegram.constants import ParseMode

    ctx: AppContext = app.bot_data["app_context"]
    today = datetime.now().date()
    rows = ctx.db.daily_stats(today, today)
    report = format_daily_report(today, rows)
    await app.bot.send_message(
        chat_id=ctx.config.bot.group_chat_id,
        text=report,
        parse_mode=ParseMode.MARKDOWN,
    )


def ensure_assignments_for_date(ctx: AppContext, target: date) -> Dict[int, List[Assignment]]:
    assignments = ctx.db.list_assignments(target)
    if assignments:
        return _group_by_user(assignments)

    levels = expand_levels(get_day_levels(target, ctx.config.scheduler))
    rooms = list(ctx.tasks.keys())
    week_index = weeks_between(ctx.config.scheduler.rotation_start, target)
    room_rotation = rotate_rooms(ctx.users, rooms, week_index, target.weekday())

    for user in ctx.users:
        assigned_rooms = room_rotation.get(user.telegram_id, [])
        for room in assigned_rooms:
            for level in levels:
                room_tasks = ctx.tasks[room].get(level, [])
                for description in room_tasks:
                    ctx.db.add_assignment(target, user.telegram_id, room, level, description)

    assignments = ctx.db.list_assignments(target)
    return _group_by_user(assignments)


def _group_by_user(assignments: List[Assignment]) -> Dict[int, List[Assignment]]:
    grouped: Dict[int, List[Assignment]] = {}
    for assignment in assignments:
        grouped.setdefault(assignment.user_id, []).append(assignment)
    return grouped


@dataclass
class GroupBlock:
    text: str
    keyboard: "InlineKeyboardMarkup | None"
    user_id: int


def build_group_blocks(
    ctx: AppContext, assignments_by_user: Dict[int, List[Assignment]], task_date: date
) -> List[GroupBlock]:
    blocks: List[GroupBlock] = []
    for user in ctx.users:
        assignments = assignments_by_user.get(user.telegram_id, [])
        if not assignments:
            continue
        text = build_personal_message(assignments, task_date)
        keyboard = build_keyboard(assignments)
        blocks.append(
            GroupBlock(
                text=f"*{user.name}*\n{text}",
                keyboard=keyboard,
                user_id=user.telegram_id,
            )
        )
    return blocks


def build_personal_message(assignments: List[Assignment], task_date: date) -> str:
    header = f"🧽 Задачи на {task_date.strftime('%d.%m.%Y')}"
    levels_line = format_levels_line(assignments)
    parts = [header]
    if levels_line:
        parts.append(levels_line)
    parts.append(format_assignments(assignments))
    return "\n".join(parts)


def build_keyboard(assignments: List[Assignment]):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = [
        [InlineKeyboardButton(text=f"✅ {a.room}: {a.description}", callback_data=f"task_done:{a.id}")]
        for a in assignments
        if not a.completed
    ]
    if not buttons:
        return None
    return InlineKeyboardMarkup(buttons)


def _group_task_message_store(app: "Application") -> Dict[Tuple[str, int], GroupTaskMessage]:
    return app.bot_data.setdefault("group_task_messages", {})


def _store_group_task_message(app, task_date: date, user_id: int, message) -> None:
    if not message:
        return
    store = _group_task_message_store(app)
    store[(task_date.isoformat(), user_id)] = GroupTaskMessage(
        chat_id=message.chat_id,
        message_id=message.message_id,
    )


def _remove_group_task_message(app, task_date: date, user_id: int) -> None:
    store = app.bot_data.get("group_task_messages")
    if not store:
        return
    store.pop((task_date.isoformat(), user_id), None)


async def _refresh_group_task_message(context, assignment: Assignment) -> None:
    app = context.application
    store = app.bot_data.get("group_task_messages", {})
    key = (assignment.task_date.isoformat(), assignment.user_id)
    message_ref = store.get(key)
    if not message_ref:
        return

    app_ctx: AppContext = app.bot_data["app_context"]
    assignments = app_ctx.db.list_assignments_for_user(
        assignment.task_date,
        assignment.user_id,
    )
    text = build_personal_message(assignments, assignment.task_date)
    owner_name = next(
        (u.name for u in app_ctx.users if u.telegram_id == assignment.user_id),
        "",
    )
    if owner_name:
        text = f"*{owner_name}*\n{text}"
    keyboard = build_keyboard(assignments)

    from telegram.constants import ParseMode
    from telegram.error import TelegramError

    try:
        await app.bot.edit_message_text(
            chat_id=message_ref.chat_id,
            message_id=message_ref.message_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except TelegramError:  # pragma: no cover - depends on Telegram API errors
        _remove_group_task_message(app, assignment.task_date, assignment.user_id)


def _personal_task_message_store(app: "Application") -> Dict[Tuple[str, int], PersonalTaskMessage]:
    return app.bot_data.setdefault("personal_task_messages", {})


def _store_personal_task_message(app, task_date: date, user_id: int, message) -> None:
    if not message:
        return
    store = _personal_task_message_store(app)
    store[(task_date.isoformat(), user_id)] = PersonalTaskMessage(
        chat_id=message.chat_id,
        message_id=message.message_id,
    )


def _remove_personal_task_message(app, task_date: date, user_id: int) -> None:
    store = app.bot_data.get("personal_task_messages")
    if not store:
        return
    store.pop((task_date.isoformat(), user_id), None)


async def _refresh_personal_task_message(context, assignment: Assignment) -> None:
    app = context.application
    store = app.bot_data.get("personal_task_messages", {})
    key = (assignment.task_date.isoformat(), assignment.user_id)
    message_ref = store.get(key)
    if not message_ref:
        return

    app_ctx: AppContext = app.bot_data["app_context"]
    assignments = app_ctx.db.list_assignments_for_user(
        assignment.task_date,
        assignment.user_id,
    )
    text = build_personal_message(assignments, assignment.task_date)
    keyboard = build_keyboard(assignments)

    from telegram.constants import ParseMode
    from telegram.error import TelegramError

    try:
        await app.bot.edit_message_text(
            chat_id=message_ref.chat_id,
            message_id=message_ref.message_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except TelegramError:  # pragma: no cover - depends on Telegram API errors
        _remove_personal_task_message(app, assignment.task_date, assignment.user_id)


def build_group_summary(
    ctx: AppContext, assignments_by_user: Dict[int, List[Assignment]], task_date: date
) -> str:
    lines = [f"📅 Задачи на {task_date.strftime('%d.%m.%Y')}"]
    for user in ctx.users:
        assignments = assignments_by_user.get(user.telegram_id, [])
        summary = format_user_summary(assignments)
        lines.append(f"• *{user.name}*: {summary}")
    return "\n".join(lines)


def build_morning_greeting(task_date: date) -> str:
    return (
        f"Доброе утро! ✨ Сегодня {task_date.strftime('%d.%m.%Y')}"
    )
