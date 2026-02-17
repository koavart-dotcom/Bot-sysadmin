import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import select

from bot.config import settings
from bot.db.database import async_session
from bot.db.models import Ticket
from bot.keyboards.inline import take_ticket_keyboard
from bot.utils.ticket import format_ticket_status

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 5 * 60  # 5 minutes

NEW_THRESHOLD = timedelta(minutes=30)
ON_HOLD_THRESHOLD = timedelta(hours=24)
IN_PROGRESS_THRESHOLD = timedelta(hours=48)


async def check_reminders(bot: Bot) -> None:
    now = datetime.utcnow()

    async with async_session() as session:
        # new > 30 min — re-notify admin chat
        result = await session.execute(
            select(Ticket).where(
                Ticket.status == "new",
                Ticket.created_at < now - NEW_THRESHOLD,
            )
        )
        new_tickets = result.scalars().all()

        for ticket in new_tickets:
            try:
                await bot.send_message(
                    settings.ADMIN_CHAT_ID,
                    f"⏰ Напоминание: заявка {ticket.ticket_number} ожидает назначения "
                    f"более 30 минут!\n\n{format_ticket_status(ticket)}",
                    reply_markup=take_ticket_keyboard(ticket.id),
                )
            except Exception:
                logger.warning("Failed to send reminder for new ticket %s", ticket.ticket_number)

        # on_hold > 24h — remind user
        result = await session.execute(
            select(Ticket).where(
                Ticket.status == "on_hold",
                Ticket.updated_at < now - ON_HOLD_THRESHOLD,
            )
        )
        hold_tickets = result.scalars().all()

        for ticket in hold_tickets:
            try:
                await bot.send_message(
                    ticket.user_id,
                    f"⏰ Напоминание: ваша заявка {ticket.ticket_number} находится в ожидании.\n"
                    "Пожалуйста, предоставьте запрошенную информацию.",
                )
            except Exception:
                logger.warning("Failed to send hold reminder for ticket %s", ticket.ticket_number)

        # in_progress > 48h — remind admin
        result = await session.execute(
            select(Ticket).where(
                Ticket.status == "in_progress",
                Ticket.updated_at < now - IN_PROGRESS_THRESHOLD,
            )
        )
        progress_tickets = result.scalars().all()

        for ticket in progress_tickets:
            if ticket.admin_id:
                try:
                    await bot.send_message(
                        ticket.admin_id,
                        f"⏰ Напоминание: заявка {ticket.ticket_number} в работе более 48 часов.\n\n"
                        f"{format_ticket_status(ticket)}",
                    )
                except Exception:
                    logger.warning("Failed to send progress reminder for ticket %s", ticket.ticket_number)


async def reminder_loop(bot: Bot) -> None:
    logger.info("Reminder loop started (interval: %ds)", CHECK_INTERVAL)
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        try:
            await check_reminders(bot)
        except Exception:
            logger.exception("Error in reminder check")
