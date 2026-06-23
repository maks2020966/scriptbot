import asyncio
import sqlite3
import os

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
MINIAPP_URL = os.environ.get("MINIAPP_URL", "https://scriptbot.onrender.com")

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


class AddCheatFile(StatesGroup):
    waiting_name = State()
    waiting_file = State()


WELCOME_TEXT = """
🔥 <b>Добро пожаловать!</b>

🤖 Это лучший бот со скриптами!

📂 Здесь ты найдёшь скрипты для любимых игр.

⚡ Выбери действие в меню ниже:

👇 <b>Нажми на MiniApp чтобы зайти в меню</b>
"""


def main_menu():
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🌐 Открыть MiniApp",
                web_app=WebAppInfo(url=MINIAPP_URL)
            )]
        ]
    )
    return kb


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

    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# Команда тільки для адміна — додати чит з файлом exe
@dp.message(F.text == "/addcheat")
async def cmd_add_cheat(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddCheatFile.waiting_name)
    await message.answer("🎮 Введите название чита 👇")


@dp.message(AddCheatFile.waiting_name)
async def do_add_cheat_name(message: Message, state: FSMContext):
    await state.update_data(cheat_name=message.text)
    await state.set_state(AddCheatFile.waiting_file)
    await message.answer(
        "📎 Прикрепите файл (.exe) или отправьте ссылку 👇"
    )


@dp.message(AddCheatFile.waiting_file, F.document)
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
        f"✅ Чит <b>'{name}'</b> добавлен с файлом!",
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await state.clear()


@dp.message(AddCheatFile.waiting_file, F.text)
async def do_add_cheat_link(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("cheat_name")

    cursor.execute(
        "INSERT INTO cheats(name, link, file_id) VALUES(?,?,?)",
        (name, message.text, None)
    )
    db.commit()

    await message.answer(
        f"✅ Чит <b>'{name}'</b> добавлен со ссылкой!",
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await state.clear()


# Команда для адміна — додати гайд (відео)
@dp.message(F.text == "/addguide")
async def cmd_add_guide(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📹 Отправьте видео гайд 👇")


@dp.message(F.video)
async def do_add_guide_video(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute(
        "INSERT INTO guides(video_id) VALUES(?)",
        (message.video.file_id,)
    )
    db.commit()

    await message.answer("✅ Гайд добавлен!")


# Отримати чит за ID (від MiniApp)
async def send_cheat_to_user(user_id, cheat_id):
    cursor.execute(
        "SELECT name, link, file_id FROM cheats WHERE id=?",
        (cheat_id,)
    )
    result = cursor.fetchone()
    if not result:
        return

    name, link, file_id = result

    try:
        if file_id:
            await bot.send_document(
                user_id,
                document=file_id,
                caption=f"🎮 <b>{name}</b>",
                parse_mode="HTML"
            )
        elif link:
            await bot.send_message(
                user_id,
                f"🎮 <b>{name}</b>\n\n🔗 {link}",
                parse_mode="HTML"
            )
    except Exception:
        pass


# ==================== API СЕРВЕР ====================

routes = web.RouteTableDef()

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
}


@routes.get('/api/scripts')
async def api_scripts(request):
    cursor.execute("SELECT game, script FROM scripts")
    scripts = [{"game": r[0], "script": r[1]} for r in cursor.fetchall()]
    return web.json_response(scripts, headers=CORS)


@routes.get('/api/my')
async def api_my(request):
    user_id = int(request.query.get('user_id', 0))
    cursor.execute(
        "SELECT game, script FROM user_scripts WHERE user_id=?",
        (user_id,)
    )
    scripts = [{"game": r[0], "script": r[1]} for r in cursor.fetchall()]
    return web.json_response(scripts, headers=CORS)


@routes.post('/api/save')
async def api_save(request):
    data = await request.json()
    user_id = data.get("user_id")
    game = data.get("game")

    cursor.execute("SELECT script FROM scripts WHERE game=?", (game,))
    result = cursor.fetchone()

    if not result:
        return web.json_response({"message": "❌ Не найден"}, headers=CORS)

    cursor.execute(
        "SELECT id FROM user_scripts WHERE user_id=? AND game=?",
        (user_id, game)
    )
    if cursor.fetchone():
        return web.json_response({"message": "⚠️ Уже сохранён"}, headers=CORS)

    cursor.execute(
        "INSERT INTO user_scripts(user_id, game, script) VALUES(?,?,?)",
        (user_id, game, result[0])
    )
    db.commit()
    return web.json_response({"message": "✅ Сохранён!"}, headers=CORS)


@routes.get('/api/cheats')
async def api_cheats(request):
    cursor.execute("SELECT id, name, link, file_id FROM cheats")
    cheats = [{
        "id": r[0],
        "name": r[1],
        "link": r[2] or "",
        "has_file": bool(r[3])
    } for r in cursor.fetchall()]
    return web.json_response(cheats, headers=CORS)


@routes.post('/api/get_cheat')
async def api_get_cheat(request):
    data = await request.json()
    user_id = data.get("user_id")
    cheat_id = data.get("cheat_id")

    await send_cheat_to_user(user_id, cheat_id)
    return web.json_response({"message": "✅ Отправлено в бот!"}, headers=CORS)


@routes.get('/api/guides')
async def api_guides(request):
    cursor.execute("SELECT id FROM guides")
    guides = [{"id": r[0]} for r in cursor.fetchall()]
    return web.json_response(guides, headers=CORS)


@routes.get('/api/admin/stats')
async def api_stats(request):
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM scripts")
    scripts = cursor.fetchone()[0]
    return web.json_response(
        {"users": users, "scripts": scripts},
        headers=CORS
    )


@routes.post('/api/admin/add_script')
async def api_add_script(request):
    data = await request.json()
    if data.get("admin_id") != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403, headers=CORS)

    cursor.execute(
        "INSERT OR REPLACE INTO scripts(game, script) VALUES(?,?)",
        (data["game"].lower(), data["script"])
    )
    db.commit()
    return web.json_response({"message": "ok"}, headers=CORS)


@routes.post('/api/admin/delete_script')
async def api_delete_script(request):
    data = await request.json()
    if data.get("admin_id") != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403, headers=CORS)

    game = data["game"]
    cursor.execute("DELETE FROM scripts WHERE game=?", (game,))
    cursor.execute("DELETE FROM user_scripts WHERE game=?", (game,))
    db.commit()
    return web.json_response({"message": "ok"}, headers=CORS)


@routes.post('/api/admin/add_cheat')
async def api_add_cheat(request):
    data = await request.json()
    if data.get("admin_id") != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403, headers=CORS)

    cursor.execute(
        "INSERT INTO cheats(name, link, file_id) VALUES(?,?,?)",
        (data["name"], data["link"], None)
    )
    db.commit()
    return web.json_response({"message": "ok"}, headers=CORS)


@routes.post('/api/admin/delete_cheat')
async def api_delete_cheat(request):
    data = await request.json()
    if data.get("admin_id") != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403, headers=CORS)

    cursor.execute("DELETE FROM cheats WHERE id=?", (data["id"],))
    db.commit()
    return web.json_response({"message": "ok"}, headers=CORS)


@routes.post('/api/admin/broadcast')
async def api_broadcast(request):
    data = await request.json()
    if data.get("admin_id") != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403, headers=CORS)

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

    return web.json_response({"message": "ok"}, headers=CORS)


@routes.get('/')
async def index(request):
    if os.path.exists('./miniapp/index.html'):
        return web.FileResponse('./miniapp/index.html')
    return web.Response(text="MiniApp не найден", status=404)


@routes.options('/{tail:.*}')
async def cors_handler(request):
    return web.Response(headers=CORS)


# ==================== ЗАПУСК ====================

async def main():
    app = web.Application()
    app.router.add_routes(routes)

    if os.path.exists('./miniapp'):
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
