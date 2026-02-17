# Bot-sysadmin

Telegram-бот для приёма заявок на техподдержку с распределением по администраторам.

## Возможности

### Пользователь
- Создание заявки через ЛС бота с выбором категории, приоритета и описанием (текст/фото)
- Создание заявки из группового чата (`/ticket <описание>`)
- Просмотр своих заявок (`/my`)
- Проверка статуса заявки (`/status #00001`)
- Переписка с админом через бота

### Администратор
- Уведомления о новых заявках в чате админов
- Кнопка «Взять в работу» — заявка закрепляется за админом
- Ответ пользователю: команда `/reply`, reply на сообщение, кнопка «Ответить»
- Смена приоритета, категории, описания
- Перевод заявки в ожидание (`on_hold`) и передача другому админу (`/transfer`)
- Закрытие заявки (кнопка или `/close`)
- Статистика (`/stats`)
- Автоматические напоминания по просроченным заявкам

### Старший админ
- Добавление/удаление администраторов (`/addadmin`, `/removeadmin`, `/admins`)

## Стек

- Python 3.12, aiogram 3.x
- SQLite (aiosqlite) + SQLAlchemy 2.x async
- Docker / Docker Compose

---

## Деплой

### Требования

- Сервер с Linux (Ubuntu 22.04+ / Debian 12+ / любой дистрибутив с Docker)
- Docker и Docker Compose ([инструкция по установке](https://docs.docker.com/engine/install/))
- Telegram-бот (токен от [@BotFather](https://t.me/BotFather))
- Группа администраторов в Telegram (бот добавлен в неё)

### Шаг 1 — Клонировать репозиторий

```bash
git clone https://github.com/koavart-dotcom/Bot-sysadmin.git
cd Bot-sysadmin
```

### Шаг 2 — Создать Telegram-бота

1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь `/newbot`, задай имя и username
3. Скопируй токен (формат: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Там же можно настроить описание и аватар бота

### Шаг 3 — Подготовить группу админов

1. Создай группу в Telegram для администраторов
2. Добавь бота в эту группу и дай ему права администратора
3. Узнай `ADMIN_CHAT_ID` группы — отправь в группу любое сообщение, затем открой:
   ```
   https://api.telegram.org/bot<ТОКЕН>/getUpdates
   ```
   В ответе найди `"chat":{"id":-100XXXXXXXXXX}` — это и есть ID группы (отрицательное число)

### Шаг 4 — Узнать ID старших админов

Каждый админ может узнать свой ID, написав боту [@userinfobot](https://t.me/userinfobot) или [@getmyid_bot](https://t.me/getmyid_bot).

### Шаг 5 — Настроить переменные окружения

```bash
cp .env.example .env
nano .env
```

Заполни:

```env
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_CHAT_ID=-1001234567890
SENIOR_ADMIN_IDS=111111111,222222222
DATABASE_URL=sqlite+aiosqlite:///data/bot.db
LOG_LEVEL=INFO
```

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от BotFather |
| `ADMIN_CHAT_ID` | ID группы администраторов (отрицательное число) |
| `SENIOR_ADMIN_IDS` | Telegram ID старших админов через запятую |
| `DATABASE_URL` | Строка подключения к БД (по умолчанию SQLite, менять не нужно) |
| `LOG_LEVEL` | Уровень логирования: `INFO` или `DEBUG` |

### Шаг 6 — Запустить

```bash
docker compose up --build -d
```

Проверить что бот запустился:

```bash
docker compose logs -f
```

Должно быть:
```
bot-1  | INFO __main__: Initializing database...
bot-1  | INFO __main__: Starting bot...
bot-1  | INFO aiogram.dispatcher: Start polling
bot-1  | INFO bot.utils.reminders: Reminder loop started (interval: 300s)
```

### Готово!

Напиши боту `/start` в Telegram — он ответит приветствием.

---

## Управление

```bash
# Запуск
docker compose up --build -d

# Логи (в реальном времени)
docker compose logs -f

# Остановка
docker compose down

# Перезапуск
docker compose restart

# Обновление (после git pull)
docker compose up --build -d
```

## Обновление

```bash
cd Bot-sysadmin
git pull
docker compose up --build -d
```

БД хранится в `./data/bot.db` и сохраняется между перезапусками через Docker volume.

---

## Команды бота

| Команда | Роль | Описание |
|---|---|---|
| `/start` | все | Главное меню |
| `/help` | все | Список команд |
| `/new` | пользователь | Создать заявку (ЛС) |
| `/ticket <текст>` | пользователь | Создать заявку (из группы) |
| `/my` | пользователь | Мои заявки |
| `/status #N` | пользователь | Статус заявки |
| `/cancel` | все | Отменить текущее действие |
| `/tickets` | админ | Открытые заявки |
| `/reply #N текст` | админ | Ответить на заявку |
| `/close #N` | админ | Закрыть заявку |
| `/priority #N low/medium/high` | админ | Сменить приоритет |
| `/transfer #N` | админ | Передать заявку другому админу |
| `/stats` | админ | Статистика по заявкам |
| `/edit #N` | админ | Управление заявкой |
| `/delete #N` | админ | Удалить заявку |
| `/addadmin ID` | ст. админ | Добавить админа |
| `/removeadmin ID` | ст. админ | Удалить админа |
| `/admins` | ст. админ | Список админов |

## Структура проекта

```
bot/
├── main.py           — точка входа, запуск polling и reminders
├── config.py         — конфигурация из .env
├── db/
│   ├── models.py     — модели (User, Admin, Ticket, TicketMessage)
│   └── database.py   — подключение к БД
├── handlers/
│   ├── common.py     — /start, /help, /cancel
│   ├── user.py       — создание заявки, ответ пользователя
│   └── admin.py      — взятие/закрытие заявок, ответы админа, stats, transfer
├── keyboards/
│   └── inline.py     — inline-клавиатуры
├── middlewares/
│   └── access.py     — проверка прав доступа
└── utils/
    ├── ticket.py     — форматирование и генерация номеров
    └── reminders.py  — фоновые напоминания
```

## Лицензия

MIT
