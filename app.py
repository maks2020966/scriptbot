import asyncio
import sqlite3
import os
import json
from threading import Thread

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from aiohttp import web

TOKEN = os.environ.get("TOKEN", "YOUR_BOT_TOKEN")
ADMIN_ID = 8320214186
MINIAPP_URL = os.environ.get("MINIAPP_URL", "https://YOUR_APP.onrender.com")

bot = Bot(TOKEN)
dp = Dispatcher()

db = sqlite3.connect("data.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS scripts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT UNIQUE,
    script TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_scripts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    game TEXT,
    script TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    name TEXT,
    game TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS cheats(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    link TEXT,
    file_id TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS guides(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT
)
""")

db.commit()


class SearchScript(StatesGroup):
    waiting_game = State()
    waiting_confirm = State()


class RequestScript(StatesGroup):
    waiting_name = State()
    waiting_game = State()


class AddScript(StatesGroup):
    waiting_game = State()
    waiting_script = State()


class UpdateScript(StatesGroup):
    waiting_game = State()
    waiting_script = State()


class AddCheat(StatesGroup):
    waiting_name = State()
    waiting_file = State()


class ReplyUser(StatesGroup):
    waiting_user_id = State()
    waiting_message = State()


class Broadcast(StatesGroup):
    waiting_message = State()


class AddGuide(StatesGroup):
    waiting_video = State()


WELCOME_TEXT = """
🔥 <b>Добро пожаловать!</b>

🤖 Это лучший бот со скриптами!

📂 Здесь ты найдёшь скрипты для любимых игр.

⚡ Выбери действие в меню ниже:
"""


def main_menu(is_admin=False):
    buttons = [
        [KeyboardButton(text="🔍 Помощь с скриптами")],
        [KeyboardButton(text="📂 Скрипты")],
        [KeyboardButton(text="🎮 Скачать чит")],
        [KeyboardButton(text="📹 Гайды как скачать чит")],
        [KeyboardButton(text="🌐 MiniApp")]
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить скрипт"), KeyboardButton(text="🔄 Обновить скрипт")],
        [KeyboardButton(text="🗑 Удалить скрипт")],
        [KeyboardButton(text="➕ Добавить чит"), KeyboardButton(text="🗑 Удалить чит")],
        [KeyboardButton(text="📹 Добавить гайд"), KeyboardButton(text="🗑 Удалить гайды")],
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="📩 Заявки")],
        [KeyboardButton(text="✉️ Ответить пользователю")],
        [KeyboardButton(text="◀️ Назад")]
    ],
    resize_keyboard=True
)

get_script_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📥 Получить скрипт", callback_data="confirm_get")]
    ]
)

no_script_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📝 Запросить скрипт", callback_data="request_script")]
    ]
)


def user_scripts_keyboard(scripts):
    keyboard = []
    for row in scripts:
        us_id = row[0]
        game = row[1]
        keyboard.append([
            InlineKeyboardButton(
                text=f"📁 {game}",
                callback_data=f"s{us_id}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def requests_keyboard(reqs):
    keyboard = []
    for req in reqs:
        req_id = req[0]
        game = req[3]
        keyboard.append([
            InlineKeyboardButton(
                text=f"📩 #{req_id} — {game}",
                callback_data=f"r{req_id}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def delete_scripts_keyboard(scripts):
    keyboard = []
    for row in scripts:
        sid = row[0]
        game = row[1]
        keyboard.append([
            InlineKeyboardButton(
                text=f"🗑 {game}",
                callback_data=f"ds{sid}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def delete_cheats_keyboard(cheats):
    keyboard = []
    for row in cheats:
        cid = row[0]
        name = row[1]
        keyboard.append([
            InlineKeyboardButton(
                text=f"🗑 {name}",
                callback_data=f"dc{cid}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def cheats_keyboard(cheats):
    keyboard = []
    for row in cheats:
        cid = row[0]
        name = row[1]
        keyboard.append([
            InlineKeyboardButton(
                text=f"🎮 {name}",
                callback_data=f"gc{cid}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def save_user(user_id):
    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (user_id,)
    )
    db.commit()


# ==================== БОТ ====================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    save_user(message.from_user.id)
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu(is_admin)
    )


@dp.message(F.text == "◀️ Назад")
async def cmd_back(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "🏠 <b>Главное меню</b>",
        parse_mode="HTML",
        reply_markup=main_menu(is_admin)
    )


@dp.message(F.text == "🌐 MiniApp")
async def cmd_miniapp(message: Message):
    save_user(message.from_user.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🌐 Открыть MiniApp",
                web_app=WebAppInfo(url=MINIAPP_URL)
            )]
        ]
    )
    await message.answer(
        "🌐 <b>Откройте MiniApp</b>\n\n"
        "Нажмите кнопку ниже 👇",
        parse_mode="HTML",
        reply_markup=kb
    )


@dp.message(F.text == "🔍 Помощь с скриптами")
async def cmd_help(message: Message, state: FSMContext):
    save_user(message.from_user.id)
    await state.set_state(SearchScript.waiting_game)
    await message.answer(
        "🔍 <b>Поиск скриптов</b>\n\n"
        "Я помогаю только со скриптами.\n"
        "Напишите название игры 👇",
        parse_mode="HTML"
    )


@dp.message(SearchScript.waiting_game)
async def do_search(message: Message, state: FSMContext):
    game = message.text.strip().lower()
    cursor.execute("SELECT game, script FROM scripts WHERE game=?", (game,))
    result = cursor.fetchone()

    if result:
        await state.update_data(found_game=result[0], found_script=result[1])
        await state.set_state(SearchScript.waiting_confirm)
        await message.answer(
            "✅ <b>Скрипт найден!</b>\n\n"
            "Нажмите кнопку ниже чтобы получить его 👇",
            parse_mode="HTML",
            reply_markup=get_script_kb
        )
    else:
        await state.clear()
        await message.answer(
            "❌ <b>К сожалению, скрипта нет.</b>\n\n"
            "Вы можете запросить его добавление 👇",
            parse_mode="HTML",
            reply_markup=no_script_kb
        )


@dp.callback_query(F.data == "confirm_get")
async def do_confirm_get(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game = data.get("found_game")
    script = data.get("found_script")

    if not game or not script:
        await call.answer("❌ Ошибка. Попробуйте снова.", show_alert=True)
        await state.clear()
        return

    user_id = call.from_user.id

    cursor.execute(
        "SELECT id FROM user_scripts WHERE user_id=? AND game=?",
        (user_id, game)
    )
    already = cursor.fetchone()

    if already:
        await call.answer("⚠️ Этот скрипт уже сохранён.", show_alert=True)
        await state.clear()
        return

    cursor.execute(
        "INSERT INTO user_scripts(user_id, game, script) VALUES(?,?,?)",
        (user_id, game, script)
    )
    db.commit()
    await state.clear()

    cursor.execute(
        "SELECT id, game FROM user_scripts WHERE user_id=?",
        (user_id,)
    )
    user_scripts = cursor.fetchall()

    await call.message.edit_text(
        "✅ <b>Скрипт сохранён!</b>\n\n"
        "📂 Ваши скрипты:",
        parse_mode="HTML",
        reply_markup=user_scripts_keyboard(user_scripts)
    )
    await call.answer("✅ Готово!")


@dp.message(F.text == "📂 Скрипты")
async def cmd_scripts(message: Message):
    save_user(message.from_user.id)
    cursor.execute(
        "SELECT id, game FROM user_scripts WHERE user_id=?",
        (message.from_user.id,)
    )
    scripts = cursor.fetchall()

    if not scripts:
        await message.answer(
            "📂 <b>У вас нет сохранённых скриптов.</b>\n\n"
            "Перейдите в раздел '🔍 Помощь с скриптами'.",
            parse_mode="HTML"
        )
        return

    await message.answer(
        "📂 <b>Ваши скрипты:</b>\n\n"
        "Нажмите на название чтобы открыть 👇",
        parse_mode="HTML",
        reply_markup=user_scripts_keyboard(scripts)
    )


@dp.callback_query(F.data.startswith("s"))
async def do_show_script(call: CallbackQuery):
    if call.data in ("request_script", "confirm_get"):
        return

    try:
        us_id = int(call.data[1:])
    except ValueError:
        await call.answer("❌ Ошибка.", show_alert=True)
        return

    cursor.execute(
        "SELECT game, script FROM user_scripts WHERE id=? AND user_id=?",
        (us_id, call.from_user.id)
    )
    result = cursor.fetchone()

    if not result:
        await call.answer("❌ Скрипт не найден.", show_alert=True)
        return

    await call.message.answer(
        f"📁 <b>{result[0]}</b>\n\n"
        f"<code>{result[1]}</code>",
        parse_mode="HTML"
    )
    await call.answer()


@dp.callback_query(F.data == "request_script")
async def do_request_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(RequestScript.waiting_name)
    await call.message.edit_text(
        "📝 <b>Запрос на добавление скрипта</b>\n\n"
        "Как вас зовут? 👇",
        parse_mode="HTML"
    )
    await call.answer()


@dp.message(RequestScript.waiting_name)
async def do_request_name(message: Message, state: FSMContext):
    await state.update_data(req_name=message.text)
    await state.set_state(RequestScript.waiting_game)
    await message.answer("🎮 Для какой игры нужен скрипт? 👇")


@dp.message(RequestScript.waiting_game)
async def do_request_game(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("req_name")
    game = message.text
    username = message.from_user.username or "нет"

    cursor.execute(
        "INSERT INTO requests(user_id, username, name, game) VALUES(?,?,?,?)",
        (message.from_user.id, username, name, game)
    )
    db.commit()

    await bot.send_message(
        ADMIN_ID,
        f"📩 <b>Новая заявка</b>\n\n"
        f"👤 Имя: {name}\n"
        f"🎮 Игра: {game}\n"
        f"📱 Username: @{username}\n"
        f"🆔 ID: {message.from_user.id}",
        parse_mode="HTML"
    )

    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "✅ <b>Ваш запрос отправлен администрации!</b>",
        parse_mode="HTML",
        reply_markup=main_menu(is_admin)
    )
    await state.clear()


@dp.message(F.text == "📹 Гайды как скачать чит")
async def cmd_guides(message: Message):
    save_user(message.from_user.id)
    cursor.execute("SELECT video_id FROM guides")
    guides = cursor.fetchall()

    if not guides:
        await message.answer(
            "📹 <b>Гайдов пока нет.</b>",
            parse_mode="HTML"
        )
        return

    await message.answer("📹 <b>Гайды:</b>", parse_mode="HTML")
    for guide in guides:
        try:
            await message.answer_video(
                video=guide[0],
                caption="📹 <b>Гайд как скачать чит</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass


@dp.message(F.text == "🎮 Скачать чит")
async def cmd_cheats(message: Message):
    save_user(message.from_user.id)
    cursor.execute("SELECT id, name FROM cheats")
    cheats = cursor.fetchall()

    if not cheats:
        await message.answer(
            "🎮 <b>Читов пока нет.</b>",
            parse_mode="HTML"
        )
        return

    await message.answer(
        "🎮 <b>Доступные читы:</b>",
        parse_mode="HTML",
        reply_markup=cheats_keyboard(cheats)
    )


@dp.callback_query(F.data.startswith("gc"))
async def do_get_cheat(call: CallbackQuery):
    try:
        cid = int(call.data[2:])
    except ValueError:
        await call.answer("❌ Ошибка.", show_alert=True)
        return

    cursor.execute(
        "SELECT name, link, file_id FROM cheats WHERE id=?",
        (cid,)
    )
    result = cursor.fetchone()

    if not result:
        await call.answer("❌ Чит не найден.", show_alert=True)
        return

    name, link, file_id = result

    if file_id:
        await call.message.answer_document(
            document=file_id,
            caption=f"🎮 <b>{name}</b>",
            parse_mode="HTML"
        )
    elif link:
        await call.message.answer(
            f"🎮 <b>{name}</b>\n\n🔗 {link}",
            parse_mode="HTML"
        )

    await call.answer()


@dp.message(F.text == "⚙️ Админ-панель")
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    await message.answer(
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"👥 Пользователей: {total}",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


@dp.message(F.text == "➕ Добавить скрипт")
async def cmd_add_script(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddScript.waiting_game)
    await message.answer("🎮 Введите название игры 👇")


@dp.message(AddScript.waiting_game)
async def do_add_script_game(message: Message, state: FSMContext):
    await state.update_data(add_game=message.text)
    await state.set_state(AddScript.waiting_script)
    await message.answer("📝 Введите текст скрипта 👇")


@dp.message(AddScript.waiting_script)
async def do_add_script_text(message: Message, state: FSMContext):
    data = await state.get_data()
    game = data.get("add_game")

    cursor.execute(
        "INSERT OR REPLACE INTO scripts(game, script) VALUES(?,?)",
        (game.lower(), message.text)
    )
    db.commit()

    await message.answer(
        f"✅ Скрипт для <b>'{game}'</b> добавлен!",
        parse_mode="HTML",
        reply_markup=admin_menu
    )
    await state.clear()


@dp.message(F.text == "🔄 Обновить скрипт")
async def cmd_update_script(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(UpdateScript.waiting_game)
    await message.answer("🔄 Введите название игры 👇")


@dp.message(UpdateScript.waiting_game)
async def do_update_script_game(message: Message, state: FSMContext):
    game = message.text.strip().lower()
    cursor.execute("SELECT id FROM scripts WHERE game=?", (game,))
    result = cursor.fetchone()

    if not result:
        await message.answer("❌ Скрипт не найден.", reply_markup=admin_menu)
        await state.clear()
        return

    await state.update_data(update_game=game)
    await state.set_state(UpdateScript.waiting_script)
    await message.answer("📝 Введите новый текст скрипта 👇")


@dp.message(UpdateScript.waiting_script)
async def do_update_script_text(message: Message, state: FSMContext):
    data = await state.get_data()
    game = data.get("update_game")

    cursor.execute("UPDATE scripts SET script=? WHERE game=?", (message.text, game))
    cursor.execute("UPDATE user_scripts SET script=? WHERE game=?", (message.text, game))
    db.commit()

    await message.answer(
        f"✅ Скрипт для <b>'{game}'</b> обновлён!",
        parse_mode="HTML",
        reply_markup=admin_menu
    )
    await state.clear()


@dp.message(F.text == "🗑 Удалить скрипт")
async def cmd_delete_script(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT id, game FROM scripts")
    scripts = cursor.fetchall()

    if not scripts:
        await message.answer("❌ Скриптов нет.", reply_markup=admin_menu)
        return

    await message.answer(
        "🗑 <b>Выберите скрипт для удаления:</b>",
        parse_mode="HTML",
        reply_markup=delete_scripts_keyboard(scripts)
    )


@dp.callback_query(F.data.startswith("ds"))
async def do_delete_script(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    try:
        sid = int(call.data[2:])
    except ValueError:
        await call.answer("❌ Ошибка.", show_alert=True)
        return

    cursor.execute("SELECT game FROM scripts WHERE id=?", (sid,))
    result = cursor.fetchone()

    if not result:
        await call.answer("❌ Не найден.", show_alert=True)
        return

    game = result[0]
    cursor.execute("DELETE FROM scripts WHERE id=?", (sid,))
    cursor.execute("DELETE FROM user_scripts WHERE game=?", (game,))
    db.commit()

    await call.message.edit_text(
        f"✅ Скрипт <b>'{game}'</b> удалён!",
        parse_mode="HTML"
    )
    await call.answer("✅ Удалено!")


@dp.message(F.text == "➕ Добавить чит")
async def cmd_add_cheat(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddCheat.waiting_name)
    await message.answer("🎮 Введите название чита 👇")


@dp.message(AddCheat.waiting_name)
async def do_add_cheat_name(message: Message, state: FSMContext):
    await state.update_data(cheat_name=message.text)
    await state.set_state(AddCheat.waiting_file)
    await message.answer("📎 Отправьте файл (.exe) или ссылку 👇")


@dp.message(AddCheat.waiting_file, F.document)
async def do_add_cheat_file(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("cheat_name")
    file_id = message.document.file_id

    cursor.execute(
        "INSERT INTO cheats(name, link, file_id) VALUES(?,?,?)",
        (name, None, file_id)
    )
    db.commit()

    await message.answer(
        f"✅ Чит <b>'{name}'</b> добавлен!",
        parse_mode="HTML",
        reply_markup=admin_menu
    )
    await state.clear()


@dp.message(AddCheat.waiting_file, F.text)
async def do_add_cheat_link(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("cheat_name")

    cursor.execute(
        "INSERT INTO cheats(name, link, file_id) VALUES(?,?,?)",
        (name, message.text, None)
    )
    db.commit()

    await message.answer(
        f"✅ Чит <b>'{name}'</b> добавлен!",
        parse_mode="HTML",
        reply_markup=admin_menu
    )
    await state.clear()


@dp.message(F.text == "🗑 Удалить чит")
async def cmd_delete_cheat(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT id, name FROM cheats")
    cheats = cursor.fetchall()

    if not cheats:
        await message.answer("❌ Читов нет.", reply_markup=admin_menu)
        return

    await message.answer(
        "🗑 <b>Выберите чит для удаления:</b>",
        parse_mode="HTML",
        reply_markup=delete_cheats_keyboard(cheats)
    )


@dp.callback_query(F.data.startswith("dc"))
async def do_delete_cheat(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    try:
        cid = int(call.data[2:])
    except ValueError:
        await call.answer("❌ Ошибка.", show_alert=True)
        return

    cursor.execute("SELECT name FROM cheats WHERE id=?", (cid,))
    result = cursor.fetchone()

    if not result:
        await call.answer("❌ Не найден.", show_alert=True)
        return

    cursor.execute("DELETE FROM cheats WHERE id=?", (cid,))
    db.commit()

    await call.message.edit_text(
        f"✅ Чит <b>'{result[0]}'</b> удалён!",
        parse_mode="HTML"
    )
    await call.answer("✅ Удалено!")


@dp.message(F.text == "📹 Добавить гайд")
async def cmd_add_guide(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddGuide.waiting_video)
    await message.answer("📹 Отправьте видео 👇")


@dp.message(AddGuide.waiting_video, F.video)
async def do_add_guide(message: Message, state: FSMContext):
    cursor.execute(
        "INSERT INTO guides(video_id) VALUES(?)",
        (message.video.file_id,)
    )
    db.commit()

    await message.answer(
        "✅ <b>Гайд добавлен!</b>",
        parse_mode="HTML",
        reply_markup=admin_menu
    )
    await state.clear()


@dp.message(AddGuide.waiting_video)
async def do_add_guide_wrong(message: Message):
    await message.answer("❌ Отправьте именно видео!")


@dp.message(F.text == "🗑 Удалить гайды")
async def cmd_delete_guides(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("DELETE FROM guides")
    db.commit()

    await message.answer(
        "✅ <b>Все гайды удалены!</b>",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


@dp.message(F.text == "📢 Рассылка")
async def cmd_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(Broadcast.waiting_message)
    await message.answer(
        "📢 Отправьте текст, фото или видео для рассылки 👇"
    )


@dp.message(Broadcast.waiting_message, F.text)
async def do_broadcast_text(message: Message, state: FSMContext):
    await state.clear()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    sent = 0
    failed = 0

    for user in users:
        try:
            await bot.send_message(
                user[0],
                f"📢 <b>Объявление:</b>\n\n{message.text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена!\n"
        f"✉️ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=admin_menu
    )


@dp.message(Broadcast.waiting_message, F.photo)
async def do_broadcast_photo(message: Message, state: FSMContext):
    await state.clear()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    photo_id = message.photo[-1].file_id
    caption = message.caption or ""
    sent = 0
    failed = 0

    for user in users:
        try:
            await bot.send_photo(
                user[0],
                photo=photo_id,
                caption=f"📢 <b>Объявление:</b>\n\n{caption}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена!\n"
        f"✉️ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=admin_menu
    )


@dp.message(Broadcast.waiting_message, F.video)
async def do_broadcast_video(message: Message, state: FSMContext):
    await state.clear()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    video_id = message.video.file_id
    caption = message.caption or ""
    sent = 0
    failed = 0

    for user in users:
        try:
            await bot.send_video(
                user[0],
                video=video_id,
                caption=f"📢 <b>Объявление:</b>\n\n{caption}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена!\n"
        f"✉️ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=admin_menu
    )


@dp.message(F.text == "📩 Заявки")
async def cmd_requests(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT id, user_id, name, game FROM requests")
    reqs = cursor.fetchall()

    if not reqs:
        await message.answer("📩 <b>Заявок нет.</b>", parse_mode="HTML")
        return

    await message.answer(
        "📩 <b>Список заявок:</b>",
        parse_mode="HTML",
        reply_markup=requests_keyboard(reqs)
    )


@dp.callback_query(F.data.startswith("r"))
async def do_view_request(call: CallbackQuery):
    if call.data == "request_script":
        return
    if call.from_user.id != ADMIN_ID:
        return

    try:
        req_id = int(call.data[1:])
    except ValueError:
        await call.answer("❌ Ошибка.", show_alert=True)
        return

    cursor.execute(
        "SELECT user_id, username, name, game FROM requests WHERE id=?",
        (req_id,)
    )
    req = cursor.fetchone()

    if not req:
        await call.answer("❌ Заявка не найдена.", show_alert=True)
        return

    user_id, username, name, game = req
    await call.message.answer(
        f"📩 <b>Заявка #{req_id}</b>\n\n"
        f"👤 Имя: {name}\n"
        f"🎮 Игра: {game}\n"
        f"📱 Username: @{username}\n"
        f"🆔 ID: {user_id}",
        parse_mode="HTML"
    )
    await call.answer()


@dp.message(F.text == "✉️ Ответить пользователю")
async def cmd_reply(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(ReplyUser.waiting_user_id)
    await message.answer("🆔 Введите ID пользователя 👇")


@dp.message(ReplyUser.waiting_user_id)
async def do_reply_id(message: Message, state: FSMContext):
    await state.update_data(reply_uid=message.text)
    await state.set_state(ReplyUser.waiting_message)
    await message.answer("✉️ Введите сообщение 👇")


@dp.message(ReplyUser.waiting_message)
async def do_reply_msg(message: Message, state: FSMContext):
    data = await state.get_data()

    try:
        user_id = int(data.get("reply_uid"))
    except ValueError:
        await message.answer("❌ Неверный ID.")
        await state.clear()
        return

    try:
        await bot.send_message(
            user_id,
            f"📩 <b>Сообщение от администратора:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer("✅ Сообщение отправлено!", reply_markup=admin_menu)
    except Exception:
        await message.answer("❌ Не удалось отправить.", reply_markup=admin_menu)

    await state.clear()


# ==================== API СЕРВЕР ====================

routes = web.RouteTableDef()


@routes.get('/api/scripts')
async def api_scripts(request):
    cursor.execute("SELECT game, script FROM scripts")
    scripts = [{"game": r[0], "script": r[1]} for r in cursor.fetchall()]
    return web.json_response(scripts, headers={"Access-Control-Allow-Origin": "*"})


@routes.get('/api/my')
async def api_my(request):
    user_id = int(request.query.get('user_id', 0))
    cursor.execute(
        "SELECT game, script FROM user_scripts WHERE user_id=?",
        (user_id,)
    )
    scripts = [{"game": r[0], "script": r[1]} for r in cursor.fetchall()]
    return web.json_response(scripts, headers={"Access-Control-Allow-Origin": "*"})


@routes.post('/api/save')
async def api_save(request):
    data = await request.json()
    user_id = data.get("user_id")
    game = data.get("game")

    cursor.execute("SELECT script FROM scripts WHERE game=?", (game,))
    result = cursor.fetchone()

    if not result:
        return web.json_response({"message": "❌ Не найден"})

    cursor.execute(
        "SELECT id FROM user_scripts WHERE user_id=? AND game=?",
        (user_id, game)
    )
    if cursor.fetchone():
        return web.json_response({"message": "⚠️ Уже сохранён"})

    cursor.execute(
        "INSERT INTO user_scripts(user_id, game, script) VALUES(?,?,?)",
        (user_id, game, result[0])
    )
    db.commit()
    return web.json_response(
        {"message": "✅ Сохранён!"},
        headers={"Access-Control-Allow-Origin": "*"}
    )


@routes.get('/api/cheats')
async def api_cheats(request):
    cursor.execute("SELECT id, name, link FROM cheats")
    cheats = [{"id": r[0], "name": r[1], "link": r[2] or ""} for r in cursor.fetchall()]
    return web.json_response(cheats, headers={"Access-Control-Allow-Origin": "*"})


@routes.get('/api/guides')
async def api_guides(request):
    cursor.execute("SELECT id FROM guides")
    guides = [{"id": r[0]} for r in cursor.fetchall()]
    return web.json_response(guides, headers={"Access-Control-Allow-Origin": "*"})


@routes.get('/api/admin/stats')
async def api_stats(request):
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM scripts")
    scripts = cursor.fetchone()[0]
    return web.json_response(
        {"users": users, "scripts": scripts},
        headers={"Access-Control-Allow-Origin": "*"}
    )


@routes.post('/api/admin/add_script')
async def api_add_script(request):
    data = await request.json()
    if data.get("admin_id") != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403)

    cursor.execute(
        "INSERT OR REPLACE INTO scripts(game, script) VALUES(?,?)",
        (data["game"].lower(), data["script"])
    )
    db.commit()
    return web.json_response({"message": "ok"})


@routes.post('/api/admin/delete_script')
async def api_delete_script(request):
    data = await request.json()
    if data.get("admin_id") != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403)

    game = data["game"]
    cursor.execute("DELETE FROM scripts WHERE game=?", (game,))
    cursor.execute("DELETE FROM user_scripts WHERE game=?", (game,))
    db.commit()
    return web.json_response({"message": "ok"})


@routes.post('/api/admin/add_cheat')
async def api_add_cheat(request):
    data = await request.json()
    if data.get("admin_id") != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403)

    cursor.execute(
        "INSERT INTO cheats(name, link, file_id) VALUES(?,?,?)",
        (data["name"], data["link"], None)
    )
    db.commit()
    return web.json_response({"message": "ok"})


@routes.post('/api/admin/delete_cheat')
async def api_delete_cheat(request):
    data = await request.json()
    if data.get("admin_id") != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403)

    cursor.execute("DELETE FROM cheats WHERE id=?", (data["id"],))
    db.commit()
    return web.json_response({"message": "ok"})


@routes.post('/api/admin/broadcast')
async def api_broadcast(request):
    data = await request.json()
    if data.get("admin_id") != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403)

    text = data.get("text", "")
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    for user in users:
        try:
            await bot.send_message(
                user[0],
                f"📢 <b>Объявление:</b>\n\n{text}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    return web.json_response({"message": "ok"})


@routes.get('/')
async def index(request):
    return web.FileResponse('./miniapp/index.html')


@routes.options('/{tail:.*}')
async def cors_handler(request):
    return web.Response(headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })


# ==================== ЗАПУСК ====================

async def main():
    app = web.Application()
    app.router.add_routes(routes)
    app.router.add_static('/static/', path='./miniapp/')

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    print(f"✅ Сервер запущен на порту {port}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())