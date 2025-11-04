from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, TYPE_CHECKING

from .config import AppConfig
from .data_loaders import TaskMap, User
from .database import Assignment, Database
from .rotation import get_day_levels, rotate_rooms, weeks_between
from .utils import format_assignments, format_stats, format_user_summary

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from telegram import InlineKeyboardMarkup, Update
    from telegram.ext import Application, ContextTypes


@dataclass
class AppContext:
    config: AppConfig
    db: Database
    users: List[User]
    tasks: TaskMap


def register_handlers(app: "Application", ctx: AppContext) -> None:
    from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

    app.bot_data["app_context"] = ctx
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("chatid", chat_id))
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            welcome,
        )
    )
    app.add_handler(CallbackQueryHandler(on_task_completed, pattern=r"^task_done:"))


async def start(update, context) -> None:
    await welcome(update, context)


async def welcome(update, context) -> None:
    intro = (
        "Привет! Я бот для распределения домашних дел."
        "\n\nКаждое утро я пришлю твой список задач с кнопками для отметки"
        " выполнения, а вечером напомню о невыполненных делах."
    )
    hints = [
        "• Используй кнопку ✅ в сообщениях, чтобы отмечать завершённые задания.",
        "• Команда /admin доступна администраторам и показывает статистику.",
        "• Команда /chatid вернёт идентификатор текущего чата (только для админов).",
    ]
    text = intro + "\n" + "\n".join(hints)
    await update.effective_message.reply_text(text)


async def admin(update, context) -> None:
    from telegram.constants import ParseMode

    app_ctx = context.application.bot_data["app_context"]
    if update.effective_user.id not in app_ctx.config.bot.admin_ids:
        await update.message.reply_text("У вас нет доступа к админской информации")
        return

    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    rows = app_ctx.db.weekly_stats(monday, sunday)
    text = format_stats("текущую неделю", rows)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


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


async def on_task_completed(update, context) -> None:
    query = update.callback_query
    await query.answer()

    assignment_id = int(query.data.split(":", 1)[1])
    app_ctx = context.application.bot_data["app_context"]
    app_ctx.db.mark_completed(assignment_id)

    assignment = next(
        (
            item
            for item in app_ctx.db.list_assignments(
                datetime.now().date()
            )
            if item.id == assignment_id
        ),
        None,
    )
    if assignment:
        await query.edit_message_text(
            text=f"✅ Задача выполнена: {assignment.description}",
        )


async def send_daily_notifications(app) -> None:
    from telegram.constants import ParseMode

    ctx: AppContext = app.bot_data["app_context"]
    today = datetime.now().date()
    assignments_by_user = ensure_assignments_for_date(ctx, today)

    for user_id, assignments in assignments_by_user.items():
        if not assignments:
            continue
        text = build_personal_message(assignments, today)
        keyboard = build_keyboard(assignments)
        await app.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )

    summary = build_group_summary(ctx, assignments_by_user, today)
    await app.bot.send_message(
        chat_id=ctx.config.bot.group_chat_id,
        text=summary,
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
        text = "Напоминание! Остались невыполненные задачи:\n" + format_assignments(incomplete)
        keyboard = build_keyboard(incomplete)
        await app.bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )


def ensure_assignments_for_date(ctx: AppContext, target: date) -> Dict[int, List[Assignment]]:
    assignments = ctx.db.list_assignments(target)
    if assignments:
        return _group_by_user(assignments)

    levels = get_day_levels(target, ctx.config.scheduler)
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


def build_personal_message(assignments: List[Assignment], task_date: date) -> str:
    header = f"🧽 Задачи на {task_date.strftime('%d.%m.%Y')}"
    return header + "\n" + format_assignments(assignments)


def build_keyboard(assignments: List[Assignment]):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = [
        [InlineKeyboardButton(text=f"✅ {a.description}", callback_data=f"task_done:{a.id}")]
        for a in assignments
        if not a.completed
    ]
    return InlineKeyboardMarkup(buttons) if buttons else InlineKeyboardMarkup([])


def build_group_summary(
    ctx: AppContext, assignments_by_user: Dict[int, List[Assignment]], task_date: date
) -> str:
    lines = [f"📅 Задачи на {task_date.strftime('%d.%m.%Y')}"]
    for user in ctx.users:
        assignments = assignments_by_user.get(user.telegram_id, [])
        summary = format_user_summary(assignments)
        lines.append(f"• *{user.name}*: {summary}")
    return "\n".join(lines)
