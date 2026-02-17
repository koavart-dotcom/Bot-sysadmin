import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.config import settings
from bot.db.database import async_session
from bot.db.models import Ticket, TicketMessage, User
from bot.keyboards.inline import (
    categories_keyboard,
    confirm_keyboard,
    main_menu_keyboard,
    priorities_keyboard,
    reply_to_ticket_keyboard,
    take_ticket_keyboard,
)
from bot.utils.ticket import format_ticket, format_ticket_status, generate_ticket_number

logger = logging.getLogger(__name__)

router = Router()


class CreateTicket(StatesGroup):
    category = State()
    priority = State()
    description = State()
    confirm = State()


class ReplyTicket(StatesGroup):
    text = State()


async def _ensure_user(user_id: int, username: str | None, full_name: str) -> None:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            session.add(User(id=user_id, username=username, full_name=full_name))
        else:
            user.username = username
            user.full_name = full_name
        await session.commit()


@router.callback_query(F.data == "new_ticket")
async def cb_new_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CreateTicket.category)
    await callback.message.edit_text(
        "📁 Выберите категорию проблемы:",
        reply_markup=categories_keyboard(),
    )
    await callback.answer()


@router.message(Command("new"))
async def cmd_new_ticket(message: Message, state: FSMContext) -> None:
    await state.set_state(CreateTicket.category)
    await message.answer(
        "📁 Выберите категорию проблемы:",
        reply_markup=categories_keyboard(),
    )


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "❌ Действие отменено.\n\nВыберите действие:",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(CreateTicket.category, F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.split(":")[1]
    await state.update_data(category=category)
    await state.set_state(CreateTicket.priority)
    await callback.message.edit_text(
        "⚡ Выберите приоритет:",
        reply_markup=priorities_keyboard(),
    )
    await callback.answer()


@router.callback_query(CreateTicket.priority, F.data.startswith("pri:"))
async def cb_priority(callback: CallbackQuery, state: FSMContext) -> None:
    priority = callback.data.split(":")[1]
    await state.update_data(priority=priority)
    await state.set_state(CreateTicket.description)
    await callback.message.edit_text(
        "📝 Опишите проблему (можно приложить фото):",
    )
    await callback.answer()


@router.message(CreateTicket.description, F.photo)
async def msg_description_photo(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]
    caption = message.caption or ""
    await state.update_data(description=caption, file_id=photo.file_id)
    await _show_confirmation(message, state)


@router.message(CreateTicket.description, F.text)
async def msg_description_text(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text, file_id=None)
    await _show_confirmation(message, state)


async def _show_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(CreateTicket.confirm)

    text = format_ticket(
        ticket_number="(новая)",
        category=data["category"],
        priority=data["priority"],
        description=data["description"],
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    await message.answer(
        f"{text}\n\nПодтвердить отправку заявки?",
        reply_markup=confirm_keyboard(),
    )


@router.callback_query(CreateTicket.confirm, F.data == "confirm_ticket")
async def cb_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    user = callback.from_user

    await _ensure_user(user.id, user.username, user.full_name)

    ticket_number = await generate_ticket_number()

    async with async_session() as session:
        ticket = Ticket(
            ticket_number=ticket_number,
            user_id=user.id,
            category=data["category"],
            priority=data["priority"],
            status="new",
            description=data["description"],
        )
        session.add(ticket)
        await session.flush()

        session.add(TicketMessage(
            ticket_id=ticket.id,
            sender_id=user.id,
            sender_role="user",
            text=data["description"],
            file_id=data.get("file_id"),
        ))

        ticket_id = ticket.id
        await session.commit()

    logger.info("Ticket %s created by user %s", ticket_number, user.id)

    # Send notification to admin chat
    admin_text = format_ticket(
        ticket_number=ticket_number,
        category=data["category"],
        priority=data["priority"],
        description=data["description"],
        username=user.username,
        full_name=user.full_name,
    )

    try:
        file_id = data.get("file_id")
        if file_id:
            admin_msg = await callback.bot.send_photo(
                settings.ADMIN_CHAT_ID,
                photo=file_id,
                caption=admin_text,
                reply_markup=take_ticket_keyboard(ticket_id),
            )
        else:
            admin_msg = await callback.bot.send_message(
                settings.ADMIN_CHAT_ID,
                admin_text,
                reply_markup=take_ticket_keyboard(ticket_id),
            )

        # Save admin message_id for later editing
        async with async_session() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
            t = result.scalar_one()
            t.message_id = admin_msg.message_id
            await session.commit()
    except Exception:
        logger.exception("Failed to send ticket %s to admin chat", ticket_number)

    await state.clear()
    await callback.message.edit_text(
        f"✅ Заявка {ticket_number} создана!\n\n"
        "Мы уведомим вас, когда администратор возьмёт её в работу.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "my_tickets")
async def cb_my_tickets(callback: CallbackQuery) -> None:
    await _show_user_tickets(callback.from_user.id, callback=callback)


@router.message(Command("my"))
async def cmd_my_tickets(message: Message) -> None:
    await _show_user_tickets(message.from_user.id, message=message)


async def _show_user_tickets(
    user_id: int,
    message: Message | None = None,
    callback: CallbackQuery | None = None,
) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(Ticket)
            .where(Ticket.user_id == user_id)
            .order_by(Ticket.created_at.desc())
            .limit(10)
        )
        tickets = result.scalars().all()

    if not tickets:
        text = "У вас пока нет заявок."
    else:
        lines = ["📋 Ваши заявки:\n"]
        for t in tickets:
            lines.append(format_ticket_status(t))
            lines.append("")
        text = "\n".join(lines)

    if callback:
        try:
            await callback.message.edit_text(text, reply_markup=main_menu_keyboard())
        except TelegramBadRequest:
            pass
        await callback.answer()
    elif message:
        await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /status #00001")
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

    await message.answer(format_ticket_status(ticket))


@router.callback_query(F.data.startswith("reply_ticket:"))
async def cb_reply_ticket(callback: CallbackQuery, state: FSMContext) -> None:
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

    await state.set_state(ReplyTicket.text)
    await state.update_data(ticket_id=ticket_id, ticket_number=ticket.ticket_number)
    await callback.message.answer(
        f"✍️ Напишите ответ по заявке {ticket.ticket_number} (текст или фото).\n"
        "Для отмены — /cancel"
    )
    await callback.answer()


@router.message(ReplyTicket.text, F.photo)
async def msg_reply_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    ticket_id = data["ticket_id"]
    ticket_number = data["ticket_number"]
    photo = message.photo[-1]
    caption = message.caption or ""

    await _send_user_reply(
        message, state, ticket_id, ticket_number,
        text=caption, file_id=photo.file_id,
    )


@router.message(ReplyTicket.text, F.text)
async def msg_reply_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    ticket_id = data["ticket_id"]
    ticket_number = data["ticket_number"]

    await _send_user_reply(
        message, state, ticket_id, ticket_number,
        text=message.text, file_id=None,
    )


async def _send_user_reply(
    message: Message,
    state: FSMContext,
    ticket_id: int,
    ticket_number: str,
    text: str,
    file_id: str | None,
) -> None:
    user = message.from_user

    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()

        if ticket is None or ticket.status == "closed":
            await message.answer("Заявка не найдена или уже закрыта.")
            await state.clear()
            return

        admin_id = ticket.admin_id

        session.add(TicketMessage(
            ticket_id=ticket_id,
            sender_id=user.id,
            sender_role="user",
            text=text or None,
            file_id=file_id,
        ))
        await session.commit()

    username = f"@{user.username}" if user.username else user.full_name
    admin_text = (
        f"💬 Сообщение от пользователя {username} по заявке {ticket_number}:\n\n{text}"
        if text
        else f"💬 Сообщение от пользователя {username} по заявке {ticket_number}:"
    )

    # Send to admin's DM if ticket is assigned
    if admin_id:
        try:
            if file_id:
                await message.bot.send_photo(admin_id, photo=file_id, caption=admin_text)
            else:
                await message.bot.send_message(admin_id, admin_text)
        except Exception:
            logger.warning("Could not send reply to admin %s for ticket %s", admin_id, ticket_number)

    # Send to admin chat
    try:
        if file_id:
            await message.bot.send_photo(
                settings.ADMIN_CHAT_ID, photo=file_id, caption=admin_text,
            )
        else:
            await message.bot.send_message(settings.ADMIN_CHAT_ID, admin_text)
    except Exception:
        logger.warning("Could not send reply to admin chat for ticket %s", ticket_number)

    await state.clear()
    await message.answer(
        f"✅ Ваш ответ по заявке {ticket_number} отправлен.",
        reply_markup=main_menu_keyboard(),
    )



# --- /ticket from group chat ---


@router.message(Command("ticket"))
async def cmd_ticket(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.reply("Использование: /ticket <описание проблемы>")
        return

    description = args[1].strip()
    user = message.from_user

    await _ensure_user(user.id, user.username, user.full_name)

    ticket_number = await generate_ticket_number()

    async with async_session() as session:
        ticket = Ticket(
            ticket_number=ticket_number,
            user_id=user.id,
            category="other",
            priority="medium",
            status="new",
            description=description,
        )
        session.add(ticket)
        await session.flush()

        session.add(TicketMessage(
            ticket_id=ticket.id,
            sender_id=user.id,
            sender_role="user",
            text=description,
        ))

        ticket_id = ticket.id
        await session.commit()

    logger.info("Ticket %s created from group chat by user %s", ticket_number, user.id)

    # Send to admin chat
    admin_text = format_ticket(
        ticket_number=ticket_number,
        category="other",
        priority="medium",
        description=description,
        username=user.username,
        full_name=user.full_name,
    )

    try:
        admin_msg = await message.bot.send_message(
            settings.ADMIN_CHAT_ID,
            admin_text,
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
        logger.exception("Failed to send ticket %s to admin chat", ticket_number)

    await message.reply(f"✅ Заявка {ticket_number} создана!")
