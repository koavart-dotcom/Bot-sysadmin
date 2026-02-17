# Bot-sysadmin

Telegram-бот для приёма заявок на техподдержку с распределением по администраторам.

## ТЗ

Техническое задание — [TZ.md](TZ.md)

## Стек

- Python 3.11+, aiogram 3.x, SQLite (aiosqlite), SQLAlchemy 2.x async
- Конфигурация через .env (python-dotenv)

## Структура

- `bot/main.py` — точка входа
- `bot/config.py` — конфигурация
- `bot/db/` — модели и подключение к БД
- `bot/handlers/` — хендлеры (user, admin, common)
- `bot/keyboards/` — inline-клавиатуры
- `bot/middlewares/` — проверка доступа
- `bot/utils/` — утилиты

## Конвенции

- Асинхронный код (async/await)
- Хендлеры разделены по ролям: user.py, admin.py, common.py
- Все данные хранятся в SQLite, файл `data/bot.db`
- Переменные окружения: BOT_TOKEN, ADMIN_CHAT_ID, SENIOR_ADMIN_IDS, DATABASE_URL, LOG_LEVEL

## Запуск

```bash
pip install -r requirements.txt
cp .env.example .env  # заполнить токен и ID
python -m bot.main
```
