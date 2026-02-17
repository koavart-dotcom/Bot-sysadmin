from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

CATEGORIES = [
    ("network", "Сеть / Интернет"),
    ("software", "Программное обеспечение"),
    ("hardware", "Оборудование"),
    ("access", "Доступы / Учётные записи"),
    ("other", "Другое"),
]

PRIORITIES = [
    ("low", "🟢 Низкий — не срочно"),
    ("medium", "🟡 Средний — мешает работе"),
    ("high", "🔴 Высокий — работа остановлена"),
]


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Создать заявку", callback_data="new_ticket")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Мои заявки", callback_data="my_tickets")
    )
    return builder.as_markup()


def categories_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in CATEGORIES:
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"cat:{code}")
        )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()


def priorities_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in PRIORITIES:
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"pri:{code}")
        )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_ticket"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )
    return builder.as_markup()


def take_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔧 Взять в работу", callback_data=f"take_ticket:{ticket_id}"
        )
    )
    return builder.as_markup()


def ticket_taken_keyboard(admin_name: str, ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"👷 Заявку взял: {admin_name}", callback_data="noop"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✍️ Ответить", callback_data=f"admin_reply_ticket:{ticket_id}"
        ),
        InlineKeyboardButton(
            text="✅ Закрыть заявку", callback_data=f"close_ticket:{ticket_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="⏸ Ожидание", callback_data=f"hold_ticket:{ticket_id}"
        ),
        InlineKeyboardButton(
            text="⚙️ Управление", callback_data=f"admin_manage_ticket:{ticket_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Мои заявки", callback_data="admin_my_tickets"
        )
    )
    return builder.as_markup()


def reply_to_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✍️ Ответить", callback_data=f"reply_ticket:{ticket_id}"
        )
    )
    return builder.as_markup()


def close_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Закрыть заявку", callback_data=f"close_ticket:{ticket_id}"
        )
    )
    return builder.as_markup()


def admin_manage_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📁 Категория", callback_data=f"admin_edit_cat:{ticket_id}"
        ),
        InlineKeyboardButton(
            text="⚡ Приоритет", callback_data=f"admin_edit_pri:{ticket_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Описание", callback_data=f"admin_edit_desc:{ticket_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🧹 Очистить историю", callback_data=f"admin_clear_history:{ticket_id}"
        ),
        InlineKeyboardButton(
            text="🗑 Удалить заявку", callback_data=f"admin_delete_ticket:{ticket_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад", callback_data=f"admin_manage_back:{ticket_id}"
        )
    )
    return builder.as_markup()


def admin_categories_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in CATEGORIES:
        builder.row(
            InlineKeyboardButton(
                text=label, callback_data=f"admin_set_cat:{ticket_id}:{code}"
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад", callback_data=f"admin_manage_ticket:{ticket_id}"
        )
    )
    return builder.as_markup()


def admin_priorities_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in PRIORITIES:
        builder.row(
            InlineKeyboardButton(
                text=label, callback_data=f"admin_set_pri:{ticket_id}:{code}"
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад", callback_data=f"admin_manage_ticket:{ticket_id}"
        )
    )
    return builder.as_markup()


def admin_confirm_delete_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🗑 Да, удалить", callback_data=f"admin_confirm_del:{ticket_id}"
        ),
        InlineKeyboardButton(
            text="◀️ Отмена", callback_data=f"admin_manage_ticket:{ticket_id}"
        ),
    )
    return builder.as_markup()


def admin_my_tickets_keyboard(tickets) -> InlineKeyboardMarkup:
    cat_map = dict(CATEGORIES)
    builder = InlineKeyboardBuilder()
    for t in tickets:
        cat_label = cat_map.get(t.category, t.category)
        label = f"{t.ticket_number} — {cat_label}"
        builder.row(
            InlineKeyboardButton(
                text=label, callback_data=f"admin_manage_ticket:{t.id}"
            )
        )
    return builder.as_markup()


def admin_confirm_clear_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🧹 Да, очистить", callback_data=f"admin_confirm_clear:{ticket_id}"
        ),
        InlineKeyboardButton(
            text="◀️ Отмена", callback_data=f"admin_manage_ticket:{ticket_id}"
        ),
    )
    return builder.as_markup()
