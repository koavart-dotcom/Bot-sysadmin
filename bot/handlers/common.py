from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.inline import main_menu_keyboard

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать в службу техподдержки!\n\n"
        "Я помогу вам создать заявку и отследить её статус.\n"
        "Выберите действие:",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "📖 Доступные команды:\n\n"
        "/start — Главное меню\n"
        "/new — Создать новую заявку\n"
        "/ticket <описание> — Создать заявку из группового чата\n"
        "/my — Мои заявки\n"
        "/status <номер> — Статус заявки\n"
        "/cancel — Отменить текущее действие\n\n"
        "👷 Команды администратора:\n"
        "/tickets — Открытые заявки\n"
        "/close <номер> — Закрыть заявку\n"
        "/priority <номер> <low/medium/high> — Сменить приоритет\n"
        "/reply <номер> <текст> — Ответить пользователю по заявке\n"
        "/transfer <номер> — Передать заявку другому админу\n"
        "/stats — Статистика по заявкам\n\n"
        "👑 Команды старшего админа:\n"
        "/addadmin <user_id> — Добавить администратора\n"
        "/removeadmin <user_id> — Удалить администратора\n"
        "/admins — Список администраторов"
    )
    await message.answer(text)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активного действия для отмены.")
        return
    await state.clear()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=main_menu_keyboard(),
    )
