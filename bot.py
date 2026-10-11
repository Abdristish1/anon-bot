import logging
import asyncio
import sqlite3
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8956162380:AAERUhuI8Yy69hiJX6x5rHjuW4wpR0Ngoo8"
ADMIN_ID = 5499124395
CHANNEL_ID = "@tihinagimnazii3"
DB_FILE = "pending.db"
# ====================================================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ── База данных ──────────────────────────────────────
def db_init():
    """Создаём таблицу при запуске если её нет"""
    with sqlite3.connect(DB_FILE) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS pending (
                admin_msg_id  INTEGER PRIMARY KEY,
                chat_id       INTEGER NOT NULL,
                user_msg_id   INTEGER NOT NULL
            )
        """)

def db_save(admin_msg_id: int, chat_id: int, user_msg_id: int):
    with sqlite3.connect(DB_FILE) as con:
        con.execute(
            "INSERT OR REPLACE INTO pending VALUES (?, ?, ?)",
            (admin_msg_id, chat_id, user_msg_id)
        )

def db_get(admin_msg_id: int):
    with sqlite3.connect(DB_FILE) as con:
        row = con.execute(
            "SELECT chat_id, user_msg_id FROM pending WHERE admin_msg_id = ?",
            (admin_msg_id,)
        ).fetchone()
    return row  # (chat_id, user_msg_id) или None

def db_delete(admin_msg_id: int):
    with sqlite3.connect(DB_FILE) as con:
        con.execute("DELETE FROM pending WHERE admin_msg_id = ?", (admin_msg_id,))
# ─────────────────────────────────────────────────────


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Это анонимный бот.\n\n"
        "Напиши своё сообщение — оно будет опубликовано в канал анонимно.\n"
        "✉️ Просто напиши текст или отправь медиа 👇"
    )


@dp.message(F.chat.type == "private", ~F.from_user.id.in_({ADMIN_ID}))
async def handle_user_message(message: Message):
    """Получаем сообщение — отправляем копию админу на модерацию"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Опубликовать", callback_data="approve"),
        InlineKeyboardButton(text="❌ Отклонить",   callback_data="reject"),
    ]])

    # Отправляем копию (без имени отправителя!) админу
    sent = await message.copy_to(chat_id=ADMIN_ID, reply_markup=keyboard)

    # Сохраняем в БД: по ID сообщения у админа находим оригинал
    db_save(sent.message_id, message.chat.id, message.message_id)

    await message.answer("✅ Сообщение отправлено на проверку!")


@dp.callback_query(F.data == "approve")
async def approve_message(callback: CallbackQuery):
    """Админ нажал ✅ — публикуем в канал"""
    row = db_get(callback.message.message_id)

    if row:
        chat_id, user_msg_id = row
        # Копируем оригинальное сообщение пользователя в канал (анонимно)
        await bot.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=chat_id,
            message_id=user_msg_id
        )
        db_delete(callback.message.message_id)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("✅ <b>Опубликовано в канал</b>", parse_mode="HTML")
    else:
        await callback.message.reply("⚠️ Сообщение уже обработано или не найдено")

    await callback.answer()


@dp.callback_query(F.data == "reject")
async def reject_message(callback: CallbackQuery):
    """Админ нажал ❌ — отклоняем"""
    db_delete(callback.message.message_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply("❌ <b>Отклонено</b>", parse_mode="HTML")
    await callback.answer()


async def main():
    db_init()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
