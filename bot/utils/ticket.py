from sqlalchemy import func, select

from bot.db.database import async_session
from bot.db.models import Ticket
from bot.keyboards.inline import CATEGORIES, PRIORITIES


async def generate_ticket_number() -> str:
    async with async_session() as session:
        result = await session.execute(select(func.max(Ticket.id)))
        max_id = result.scalar_one() or 0
    return f"#{max_id + 1:05d}"


def get_category_label(code: str) -> str:
    for c, label in CATEGORIES:
        if c == code:
            return label
    return code


def get_priority_label(code: str) -> str:
    for c, label in PRIORITIES:
        if c == code:
            return label
    return code


STATUS_LABELS = {
    "new": "🆕 Новая",
    "in_progress": "🔧 В работе",
    "on_hold": "⏸ Ожидание",
    "closed": "✅ Закрыта",
}


def format_ticket(ticket_number: str, category: str, priority: str,
                  description: str, username: str | None, full_name: str) -> str:
    user_display = f"@{username}" if username else full_name
    return (
        f"🎫 Заявка {ticket_number}\n"
        f"📁 Категория: {get_category_label(category)}\n"
        f"⚡ Приоритет: {get_priority_label(priority)}\n"
        f"👤 Пользователь: {user_display}\n"
        f"📝 Описание:\n{description}"
    )


def format_ticket_status(ticket) -> str:
    status_label = STATUS_LABELS.get(ticket.status, ticket.status)
    return (
        f"🎫 {ticket.ticket_number} — {status_label}\n"
        f"📁 {get_category_label(ticket.category)}\n"
        f"⚡ {get_priority_label(ticket.priority)}\n"
        f"📝 {ticket.description[:80]}{'...' if len(ticket.description) > 80 else ''}\n"
        f"📅 {ticket.created_at:%d.%m.%Y %H:%M}"
    )
