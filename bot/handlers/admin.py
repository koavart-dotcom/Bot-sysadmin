import logging
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete as sa_delete, func, select

from bot.config import settings
from bot.db.database import async_session
from bot.db.models import Admin, Ticket, TicketMessage, User
from bot.keyboards.inline import (
    admin_categories_keyboard,
    admin_confirm_clear_keyboard,
    admin_confirm_delete_keyboard,
    admin_manage_keyboard,
    admin_my_tickets_keyboard,
    admin_priorities_keyboard,
    main_menu_keyboard,
    reply_to_ticket_keyboard,
    take_ticket_keyboard,
    ticket_taken_keyboard,
)
from bot.middlewares.access import is_admin
from bot.utils.ticket import (
    format_ticket,
    format_ticket_status,
    get_category_label,
    get_priority_label,
)

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("take_ticket:"))
async def cb_take_ticket(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not await is_admin(user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()

        if ticket is None:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        if ticket.status != "new":
            await callback.answer("Заявка уже взята в работу.", show_alert=True)
            return

        ticket.admin_id = user.id
        ticket.status = "in_progress"
        await session.commit()
        user_id = ticket.user_id
        ticket_number = ticket.ticket_number

    admin_name = f"@{user.username}" if user.username else user.full_name

    await callback.message.edit_reply_markup(
        reply_markup=ticket_taken_keyboard(admin_name, ticket_id),
    )
    await callback.answer("Вы взяли заявку в работу.")

    try:
        await callback.bot.send_message(
            user_id,
            f"🔧 Ваша заявка {ticket_number} взята в работу администратором {admin_name}.",
        )
    except Exception:
        logger.warning("Could not notify user %s about ticket %s", user_id, ticket_number)


@router.callback_query(F.data.startswith("close_ticket:"))
async def cb_close_ticket(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not await is_admin(user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()

        if ticket is None:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        if ticket.status == "closed":
            await callback.answer("Заявка уже закрыта.", show_alert=True)
            return

        ticket.status = "closed"
        ticket.closed_at = datetime.utcnow()
        await session.commit()
        user_id = ticket.user_id
        ticket_number = ticket.ticket_number

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Заявка закрыта.")

    try:
        await callback.bot.send_message(
            user_id,
            f"✅ Ваша заявка {ticket_number} закрыта.\n\nВыберите действие:",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        logger.warning("Could not notify user %s about closing ticket %s", user_id, ticket_number)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "admin_my_tickets")
async def cb_admin_my_tickets(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not await is_admin(user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(Ticket)
            .where(
                Ticket.admin_id == user.id,
                Ticket.status.in_(["new", "in_progress", "on_hold"]),
            )
            .order_by(Ticket.created_at.desc())
            .limit(15)
        )
        tickets = result.scalars().all()

    if not tickets:
        await callback.answer("У вас нет назначенных заявок.", show_alert=True)
        return

    lines = ["📋 Ваши заявки:\n"]
    for t in tickets:
        lines.append(format_ticket_status(t))
        lines.append("")

    await callback.message.answer(
        "\n".join(lines),
        reply_markup=admin_my_tickets_keyboard(tickets),
    )
    await callback.answer()


@router.message(Command("tickets"))
async def cmd_tickets(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    async with async_session() as session:
        result = await session.execute(
            select(Ticket)
            .where(Ticket.status.in_(["new", "in_progress", "on_hold"]))
            .order_by(Ticket.created_at.desc())
        )
        tickets = result.scalars().all()

    if not tickets:
        await message.answer("Нет открытых заявок.")
        return

    lines = ["📋 Открытые заявки:\n"]
    for t in tickets:
        lines.append(format_ticket_status(t))
        lines.append("")
    await message.answer("\n".join(lines))


@router.message(Command("close"))
async def cmd_close(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /close #00001")
        return

    ticket_number = args[1].strip()
    if not ticket_number.startswith("#"):
        ticket_number = f"#{ticket_number}"

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.ticket_number == ticket_number)
        )
        ticket = result.scalar_one_or_none()

        if ticket is None:
            await message.answer(f"Заявка {ticket_number} не найдена.")
            return

        if ticket.status == "closed":
            await message.answer(f"Заявка {ticket_number} уже закрыта.")
            return

        ticket.status = "closed"
        ticket.closed_at = datetime.utcnow()
        await session.commit()
        user_id = ticket.user_id

    await message.answer(f"✅ Заявка {ticket_number} закрыта.")

    try:
        await message.bot.send_message(
            user_id,
            f"✅ Ваша заявка {ticket_number} закрыта.\n\nВыберите действие:",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        logger.warning("Could not notify user %s about closing ticket %s", user_id, ticket_number)


@router.message(Command("priority"))
async def cmd_priority(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer("Использование: /priority #00001 low|medium|high")
        return

    ticket_number = args[1].strip()
    if not ticket_number.startswith("#"):
        ticket_number = f"#{ticket_number}"
    new_priority = args[2].strip().lower()

    if new_priority not in ("low", "medium", "high"):
        await message.answer("Приоритет должен быть: low, medium или high")
        return

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.ticket_number == ticket_number)
        )
        ticket = result.scalar_one_or_none()

        if ticket is None:
            await message.answer(f"Заявка {ticket_number} не найдена.")
            return

        ticket.priority = new_priority
        await session.commit()

    await message.answer(f"Приоритет заявки {ticket_number} изменён на {new_priority}.")


def _parse_reply_args(text: str) -> tuple[str, str] | None:
    """Parse '/reply #00001 some text' → ('#00001', 'some text') or None."""
    match = re.match(r"/reply\s+(#?\d+)\s*(.*)", text, re.DOTALL)
    if not match:
        return None
    ticket_number = match.group(1)
    if not ticket_number.startswith("#"):
        ticket_number = f"#{ticket_number}"
    reply_text = match.group(2).strip()
    return ticket_number, reply_text


@router.message(Command("reply"))
async def cmd_reply(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    text = message.text or message.caption or ""
    parsed = _parse_reply_args(text)

    if parsed is None:
        await message.answer("Использование: /reply #00001 текст ответа")
        return

    ticket_number, reply_text = parsed

    # Handle photo with caption "/reply #00001"
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
        # For photo messages, caption is used instead of text
        caption = message.caption or ""
        parsed = _parse_reply_args(caption)
        if parsed is None:
            await message.answer("Использование: отправьте фото с подписью /reply #00001")
            return
        ticket_number, reply_text = parsed

    if not reply_text and not file_id:
        await message.answer("Укажите текст ответа или приложите фото.")
        return

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.ticket_number == ticket_number)
        )
        ticket = result.scalar_one_or_none()

        if ticket is None:
            await message.answer(f"Заявка {ticket_number} не найдена.")
            return

        if ticket.status == "closed":
            await message.answer(f"Заявка {ticket_number} уже закрыта.")
            return

        user_id = ticket.user_id
        ticket_id = ticket.id

        session.add(TicketMessage(
            ticket_id=ticket_id,
            sender_id=message.from_user.id,
            sender_role="admin",
            text=reply_text or None,
            file_id=file_id,
        ))
        await session.commit()

    admin_name = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else message.from_user.full_name
    )
    user_text = f"💬 Ответ по заявке {ticket_number} от {admin_name}:\n\n{reply_text}" if reply_text else f"💬 Ответ по заявке {ticket_number} от {admin_name}:"

    try:
        if file_id:
            await message.bot.send_photo(
                user_id,
                photo=file_id,
                caption=user_text,
                reply_markup=reply_to_ticket_keyboard(ticket_id),
            )
        else:
            await message.bot.send_message(
                user_id,
                user_text,
                reply_markup=reply_to_ticket_keyboard(ticket_id),
            )
        await message.answer(f"✅ Ответ отправлен пользователю по заявке {ticket_number}.")
    except Exception:
        logger.warning("Could not send reply to user %s for ticket %s", user_id, ticket_number)
        await message.answer(f"⚠️ Не удалось отправить ответ пользователю по заявке {ticket_number}.")


# --- Inline button "Ответить" → prompt in admin group chat ---

# Maps prompt message_id → ticket_id for reply matching
_reply_prompts: dict[int, int] = {}

# Maps prompt message_id → ticket_id for description editing
_edit_prompts: dict[int, int] = {}


@router.callback_query(F.data.startswith("admin_reply_ticket:"))
async def cb_admin_reply_ticket(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not await is_admin(user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()

    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    if ticket.status == "closed":
        await callback.answer("Заявка уже закрыта.", show_alert=True)
        return

    admin_name = f"@{user.username}" if user.username else user.full_name
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_reply_prompt")]
    ])
    prompt_msg = await callback.message.reply(
        f"✍️ {admin_name}, ответьте на это сообщение, чтобы отправить ответ по заявке {ticket.ticket_number}.",
        reply_markup=cancel_kb,
    )
    _reply_prompts[prompt_msg.message_id] = ticket_id
    await callback.answer()


@router.callback_query(F.data == "cancel_reply_prompt")
async def cb_cancel_reply_prompt(callback: CallbackQuery) -> None:
    msg_id = callback.message.message_id
    _reply_prompts.pop(msg_id, None)
    await callback.message.delete()
    await callback.answer("Отменено.")


async def _send_admin_reply(
    message: Message,
    ticket_id: int,
    ticket_number: str,
    text: str,
    file_id: str | None,
) -> None:
    """Send admin reply to the user and save to DB. Shared by button and reply handler."""
    admin = message.from_user

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()

        if ticket is None or ticket.status == "closed":
            await message.reply("Заявка не найдена или уже закрыта.")
            return

        user_id = ticket.user_id

        session.add(TicketMessage(
            ticket_id=ticket_id,
            sender_id=admin.id,
            sender_role="admin",
            text=text or None,
            file_id=file_id,
        ))
        await session.commit()

    admin_name = f"@{admin.username}" if admin.username else admin.full_name
    user_text = (
        f"💬 Ответ по заявке {ticket_number} от {admin_name}:\n\n{text}"
        if text
        else f"💬 Ответ по заявке {ticket_number} от {admin_name}:"
    )

    try:
        if file_id:
            await message.bot.send_photo(
                user_id,
                photo=file_id,
                caption=user_text,
                reply_markup=reply_to_ticket_keyboard(ticket_id),
            )
        else:
            await message.bot.send_message(
                user_id,
                user_text,
                reply_markup=reply_to_ticket_keyboard(ticket_id),
            )
        await message.reply(f"✅ Ответ отправлен пользователю по заявке {ticket_number}.")
    except Exception:
        logger.warning("Could not send reply to user %s for ticket %s", user_id, ticket_number)
        await message.reply(f"⚠️ Не удалось отправить ответ пользователю по заявке {ticket_number}.")


# --- Admin manage ticket (inline buttons) ---


async def _get_ticket(ticket_id: int) -> Ticket | None:
    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()


@router.callback_query(F.data.startswith("admin_manage_ticket:"))
async def cb_admin_manage_ticket(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = await _get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    text = (
        f"⚙️ Управление заявкой {ticket.ticket_number}\n\n"
        f"📁 Категория: {get_category_label(ticket.category)}\n"
        f"⚡ Приоритет: {get_priority_label(ticket.priority)}\n"
        f"📝 Описание: {ticket.description[:100]}{'...' if len(ticket.description) > 100 else ''}"
    )
    await callback.message.edit_text(text, reply_markup=admin_manage_keyboard(ticket_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_manage_back:"))
async def cb_admin_manage_back(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = await _get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    admin_name = ""
    if ticket.admin_id:
        try:
            chat_member = await callback.bot.get_chat_member(
                settings.ADMIN_CHAT_ID, ticket.admin_id
            )
            u = chat_member.user
            admin_name = f"@{u.username}" if u.username else u.full_name
        except Exception:
            admin_name = str(ticket.admin_id)

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        t = result.scalar_one_or_none()
    if t is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == t.user_id)
        )
        user = result.scalar_one_or_none()
    username = user.username if user else None
    full_name = user.full_name if user else "Unknown"
    text = format_ticket(t.ticket_number, t.category, t.priority, t.description, username, full_name)
    await callback.message.edit_text(
        text, reply_markup=ticket_taken_keyboard(admin_name, ticket_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_cat:"))
async def cb_admin_edit_cat(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return
    ticket_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "📁 Выберите новую категорию:",
        reply_markup=admin_categories_keyboard(ticket_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_set_cat:"))
async def cb_admin_set_cat(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    parts = callback.data.split(":")
    ticket_id = int(parts[1])
    category = parts[2]

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return
        ticket.category = category
        await session.commit()

    await callback.answer(f"Категория изменена: {get_category_label(category)}")
    # Return to manage menu
    ticket = await _get_ticket(ticket_id)
    text = (
        f"⚙️ Управление заявкой {ticket.ticket_number}\n\n"
        f"📁 Категория: {get_category_label(ticket.category)}\n"
        f"⚡ Приоритет: {get_priority_label(ticket.priority)}\n"
        f"📝 Описание: {ticket.description[:100]}{'...' if len(ticket.description) > 100 else ''}"
    )
    await callback.message.edit_text(text, reply_markup=admin_manage_keyboard(ticket_id))


@router.callback_query(F.data.startswith("admin_edit_pri:"))
async def cb_admin_edit_pri(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return
    ticket_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "⚡ Выберите новый приоритет:",
        reply_markup=admin_priorities_keyboard(ticket_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_set_pri:"))
async def cb_admin_set_pri(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    parts = callback.data.split(":")
    ticket_id = int(parts[1])
    priority = parts[2]

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return
        ticket.priority = priority
        await session.commit()

    await callback.answer(f"Приоритет изменён: {get_priority_label(priority)}")
    ticket = await _get_ticket(ticket_id)
    text = (
        f"⚙️ Управление заявкой {ticket.ticket_number}\n\n"
        f"📁 Категория: {get_category_label(ticket.category)}\n"
        f"⚡ Приоритет: {get_priority_label(ticket.priority)}\n"
        f"📝 Описание: {ticket.description[:100]}{'...' if len(ticket.description) > 100 else ''}"
    )
    await callback.message.edit_text(text, reply_markup=admin_manage_keyboard(ticket_id))


@router.callback_query(F.data.startswith("admin_edit_desc:"))
async def cb_admin_edit_desc(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = await _get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    admin_name = (
        f"@{callback.from_user.username}"
        if callback.from_user.username
        else callback.from_user.full_name
    )
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_edit_prompt:{ticket_id}")]
    ])
    prompt_msg = await callback.message.reply(
        f"✏️ {admin_name}, ответьте на это сообщение с новым описанием для заявки {ticket.ticket_number}.",
        reply_markup=cancel_kb,
    )
    _edit_prompts[prompt_msg.message_id] = ticket_id
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_edit_prompt:"))
async def cb_cancel_edit_prompt(callback: CallbackQuery) -> None:
    msg_id = callback.message.message_id
    _edit_prompts.pop(msg_id, None)
    await callback.message.delete()
    await callback.answer("Отменено.")


@router.callback_query(F.data.startswith("admin_clear_history:"))
async def cb_admin_clear_history(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = await _get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    await callback.message.edit_text(
        f"🧹 Очистить всю историю переписки по заявке {ticket.ticket_number}?\n\n"
        "Это действие нельзя отменить. Сама заявка останется.",
        reply_markup=admin_confirm_clear_keyboard(ticket_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_clear:"))
async def cb_admin_confirm_clear(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        ticket_number = ticket.ticket_number

        await session.execute(
            sa_delete(TicketMessage).where(TicketMessage.ticket_id == ticket_id)
        )
        await session.commit()

    await callback.answer(f"История заявки {ticket_number} очищена.")
    ticket = await _get_ticket(ticket_id)
    text = (
        f"⚙️ Управление заявкой {ticket.ticket_number}\n\n"
        f"📁 Категория: {get_category_label(ticket.category)}\n"
        f"⚡ Приоритет: {get_priority_label(ticket.priority)}\n"
        f"📝 Описание: {ticket.description[:100]}{'...' if len(ticket.description) > 100 else ''}"
    )
    await callback.message.edit_text(text, reply_markup=admin_manage_keyboard(ticket_id))


@router.callback_query(F.data.startswith("admin_delete_ticket:"))
async def cb_admin_delete_ticket(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = await _get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    await callback.message.edit_text(
        f"🗑 Удалить заявку {ticket.ticket_number} полностью?\n\n"
        "Будут удалены заявка и вся история переписки. Это действие нельзя отменить.",
        reply_markup=admin_confirm_delete_keyboard(ticket_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_del:"))
async def cb_admin_confirm_del(callback: CallbackQuery) -> None:
    if not await is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        ticket_number = ticket.ticket_number
        await session.delete(ticket)
        await session.commit()

    await callback.message.edit_text(f"🗑 Заявка {ticket_number} удалена.")
    await callback.answer()


# --- /edit and /delete commands ---


@router.message(Command("edit"))
async def cmd_edit(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /edit #00001")
        return

    ticket_number = args[1].strip()
    if not ticket_number.startswith("#"):
        ticket_number = f"#{ticket_number}"

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.ticket_number == ticket_number)
        )
        ticket = result.scalar_one_or_none()

    if ticket is None:
        await message.answer(f"Заявка {ticket_number} не найдена.")
        return

    text = (
        f"⚙️ Управление заявкой {ticket.ticket_number}\n\n"
        f"📁 Категория: {get_category_label(ticket.category)}\n"
        f"⚡ Приоритет: {get_priority_label(ticket.priority)}\n"
        f"📝 Описание: {ticket.description[:100]}{'...' if len(ticket.description) > 100 else ''}"
    )
    await message.answer(text, reply_markup=admin_manage_keyboard(ticket.id))


@router.message(Command("delete"))
async def cmd_delete(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /delete #00001")
        return

    ticket_number = args[1].strip()
    if not ticket_number.startswith("#"):
        ticket_number = f"#{ticket_number}"

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.ticket_number == ticket_number)
        )
        ticket = result.scalar_one_or_none()

    if ticket is None:
        await message.answer(f"Заявка {ticket_number} не найдена.")
        return

    await message.answer(
        f"🗑 Удалить заявку {ticket.ticket_number} полностью?\n\n"
        "Будут удалены заявка и вся история переписки. Это действие нельзя отменить.",
        reply_markup=admin_confirm_delete_keyboard(ticket.id),
    )


# --- On hold ---


@router.callback_query(F.data.startswith("hold_ticket:"))
async def cb_hold_ticket(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not await is_admin(user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()

        if ticket is None:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        if ticket.status == "closed":
            await callback.answer("Заявка уже закрыта.", show_alert=True)
            return

        ticket.status = "on_hold"
        await session.commit()
        user_id = ticket.user_id
        ticket_number = ticket.ticket_number

    await callback.answer("Заявка переведена в ожидание.")

    try:
        await callback.bot.send_message(
            user_id,
            f"⏸ Ваша заявка {ticket_number} переведена в режим ожидания.\n"
            "Администратор ожидает дополнительную информацию от вас.",
        )
    except Exception:
        logger.warning("Could not notify user %s about hold ticket %s", user_id, ticket_number)


# --- Transfer ---


@router.message(Command("transfer"))
async def cmd_transfer(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /transfer #00001")
        return

    ticket_number = args[1].strip()
    if not ticket_number.startswith("#"):
        ticket_number = f"#{ticket_number}"

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.ticket_number == ticket_number)
        )
        ticket = result.scalar_one_or_none()

        if ticket is None:
            await message.answer(f"Заявка {ticket_number} не найдена.")
            return

        if ticket.status == "closed":
            await message.answer(f"Заявка {ticket_number} уже закрыта.")
            return

        ticket.admin_id = None
        ticket.status = "new"
        await session.commit()
        user_id = ticket.user_id
        ticket_id = ticket.id

    await message.answer(f"🔄 Заявка {ticket_number} возвращена в очередь.")

    # Re-post to admin chat with "Take" button
    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        result2 = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result2.scalar_one_or_none()

    if ticket and user:
        from bot.utils.ticket import format_ticket
        text = format_ticket(
            ticket_number=ticket.ticket_number,
            category=ticket.category,
            priority=ticket.priority,
            description=ticket.description,
            username=user.username,
            full_name=user.full_name,
        )
        try:
            admin_msg = await message.bot.send_message(
                settings.ADMIN_CHAT_ID,
                f"🔄 Заявка передана:\n\n{text}",
                reply_markup=take_ticket_keyboard(ticket_id),
            )
            async with async_session() as session:
                result = await session.execute(
                    select(Ticket).where(Ticket.id == ticket_id)
                )
                t = result.scalar_one()
                t.message_id = admin_msg.message_id
                await session.commit()
        except Exception:
            logger.warning("Could not re-post ticket %s to admin chat", ticket_number)

    try:
        await message.bot.send_message(
            user_id,
            f"🔄 Ваша заявка {ticket_number} передана другому администратору.",
        )
    except Exception:
        logger.warning("Could not notify user %s about transfer of ticket %s", user_id, ticket_number)


# --- Stats ---


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    async with async_session() as session:
        # Total tickets
        total = (await session.execute(select(func.count(Ticket.id)))).scalar_one()

        # By status
        status_rows = (await session.execute(
            select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
        )).all()

        # By priority
        priority_rows = (await session.execute(
            select(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority)
        )).all()

        # Average rating
        avg_rating = (await session.execute(
            select(func.avg(Ticket.rating)).where(Ticket.rating.isnot(None))
        )).scalar_one()

    from bot.utils.ticket import STATUS_LABELS, get_priority_label

    status_lines = []
    for status, count in status_rows:
        label = STATUS_LABELS.get(status, status)
        status_lines.append(f"  {label}: {count}")

    priority_lines = []
    for priority, count in priority_rows:
        label = get_priority_label(priority)
        priority_lines.append(f"  {label}: {count}")

    avg_str = f"{avg_rating:.1f}" if avg_rating else "—"

    text = (
        f"📊 Статистика заявок\n\n"
        f"Всего заявок: {total}\n\n"
        f"По статусам:\n" + "\n".join(status_lines) + "\n\n"
        f"По приоритетам:\n" + "\n".join(priority_lines) + "\n\n"
        f"Средняя оценка: {avg_str} ⭐"
    )
    await message.answer(text)


# --- Senior admin commands ---


def _is_senior(user_id: int) -> bool:
    return user_id in settings.SENIOR_ADMIN_IDS


@router.message(Command("addadmin"))
async def cmd_addadmin(message: Message) -> None:
    if not _is_senior(message.from_user.id):
        await message.answer("Только старший администратор может добавлять админов.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /addadmin <user_id>")
        return

    try:
        new_admin_id = int(args[1].strip())
    except ValueError:
        await message.answer("user_id должен быть числом.")
        return

    async with async_session() as session:
        result = await session.execute(
            select(Admin).where(Admin.id == new_admin_id)
        )
        admin = result.scalar_one_or_none()

        if admin is not None:
            if admin.is_active:
                await message.answer(f"Пользователь {new_admin_id} уже является админом.")
                return
            admin.is_active = True
            await session.commit()
            await message.answer(f"✅ Админ {new_admin_id} восстановлен.")
            return

        # Try to get user info from Telegram
        try:
            chat = await message.bot.get_chat(new_admin_id)
            username = chat.username
            full_name = chat.full_name or str(new_admin_id)
        except Exception:
            username = None
            full_name = str(new_admin_id)

        session.add(Admin(
            id=new_admin_id,
            username=username,
            full_name=full_name,
            is_senior=new_admin_id in settings.SENIOR_ADMIN_IDS,
            is_active=True,
        ))
        await session.commit()

    await message.answer(f"✅ Пользователь {new_admin_id} добавлен как администратор.")


@router.message(Command("removeadmin"))
async def cmd_removeadmin(message: Message) -> None:
    if not _is_senior(message.from_user.id):
        await message.answer("Только старший администратор может удалять админов.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /removeadmin <user_id>")
        return

    try:
        admin_id = int(args[1].strip())
    except ValueError:
        await message.answer("user_id должен быть числом.")
        return

    async with async_session() as session:
        result = await session.execute(
            select(Admin).where(Admin.id == admin_id)
        )
        admin = result.scalar_one_or_none()

        if admin is None:
            await message.answer(f"Админ {admin_id} не найден.")
            return

        if not admin.is_active:
            await message.answer(f"Админ {admin_id} уже деактивирован.")
            return

        admin.is_active = False
        await session.commit()

    await message.answer(f"✅ Админ {admin_id} деактивирован.")


@router.message(Command("admins"))
async def cmd_admins(message: Message) -> None:
    if not _is_senior(message.from_user.id):
        await message.answer("Только старший администратор может просматривать список админов.")
        return

    async with async_session() as session:
        result = await session.execute(
            select(Admin).where(Admin.is_active.is_(True))
        )
        admins = result.scalars().all()

    if not admins:
        await message.answer("Нет активных администраторов.")
        return

    lines = ["👥 Активные администраторы:\n"]
    for a in admins:
        name = f"@{a.username}" if a.username else a.full_name
        senior = " (старший)" if a.is_senior else ""
        lines.append(f"• {a.id} — {name}{senior}")

    await message.answer("\n".join(lines))


# --- Reply to bot message in admin chat (lowest priority — registered last) ---


@router.message(
    F.chat.id == settings.ADMIN_CHAT_ID,
    F.reply_to_message,
)
async def msg_admin_chat_reply(message: Message) -> None:
    if not await is_admin(message.from_user.id):
        return

    replied_msg_id = message.reply_to_message.message_id

    # Check edit description prompts first
    edit_ticket_id = _edit_prompts.pop(replied_msg_id, None)
    if edit_ticket_id is not None:
        new_desc = (message.text or "").strip()
        if not new_desc:
            await message.reply("Описание не может быть пустым.")
            _edit_prompts[replied_msg_id] = edit_ticket_id
            return

        async with async_session() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.id == edit_ticket_id)
            )
            ticket = result.scalar_one_or_none()
            if ticket is None:
                await message.reply("Заявка не найдена.")
                return
            ticket.description = new_desc
            await session.commit()
            ticket_number = ticket.ticket_number

        await message.reply(f"✏️ Описание заявки {ticket_number} обновлено.")
        return

    # Check prompt messages (from "Ответить" button)
    ticket_id = _reply_prompts.pop(replied_msg_id, None)
    if ticket_id is not None:
        async with async_session() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
            ticket = result.scalar_one_or_none()
    else:
        # Check original ticket message
        async with async_session() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.message_id == replied_msg_id)
            )
            ticket = result.scalar_one_or_none()

    if ticket is None:
        return

    if ticket.status == "closed":
        await message.reply("Заявка уже закрыта.")
        return

    text = message.text or message.caption or ""
    file_id = message.photo[-1].file_id if message.photo else None

    if not text and not file_id:
        return

    await _send_admin_reply(
        message,
        ticket_id=ticket.id,
        ticket_number=ticket.ticket_number,
        text=text,
        file_id=file_id,
    )
