# bot_premium.py — SHRINKERBOT 2025 ULTIMATE FINAL (TO‘LIQ TUZATILGAN)
import os
import sqlite3
import asyncio
import secrets
import string
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    FSInputFile
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import ffmpeg

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CLOUD_CHANNEL = int(os.getenv("CLOUD_CHANNEL", 0))

if not all([BOT_TOKEN, ADMIN_ID, CLOUD_CHANNEL]):
    print("XATO: .env faylda BOT_TOKEN, ADMIN_ID yoki CLOUD_CHANNEL yo'q!")
    exit()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# ------------------- DATABASE -------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    videos_count INTEGER DEFAULT 0,
    is_premium INTEGER DEFAULT 0,
    premium_until INTEGER DEFAULT 0,
    quality TEXT DEFAULT 'medium',
    preview INTEGER DEFAULT 1
)""")
c.execute("""CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, used INTEGER DEFAULT 0, used_by INTEGER)""")
c.execute("""CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    file_id TEXT,
    file_name TEXT,
    date TEXT
)""")
conn.commit()

# ------------------- KONFIG -------------------
LIMIT_FREE = 10
MAX_SIZE_FREE = 500 * 1024 * 1024
MAX_SIZE_PREMIUM = 2 * 1024 * 1024 * 1024
MAX_CONCURRENT = 4
semaphore = asyncio.Semaphore(MAX_CONCURRENT)
PREMIUM_DAYS = 30

QUALITY_SETTINGS = {
    "low":    {"crf": 32, "preset": "veryfast"},
    "medium": {"crf": 28, "preset": "medium"},
    "high":   {"crf": 24, "preset": "slow"},
    "ultra":  {"crf": 20, "preset": "veryslow"}
}

# ------------------- YORDAMCHI -------------------
def format_size(b):
    for u in ['B', 'KB', 'MB', 'GB']:
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"

def get_user(uid):
    c.execute("SELECT videos_count, is_premium, premium_until, quality, preview FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users(user_id) VALUES(?)", (uid,))
        conn.commit()
        return 0, 0, 0, "medium", 1
    return row

def is_premium_now(uid):
    _, _, until, _, _ = get_user(uid)
    if until == 0: return False
    now = int(datetime.now().timestamp())
    if now > until:
        c.execute("UPDATE users SET is_premium=0, premium_until=0 WHERE user_id=?", (uid,))
        conn.commit()
        return False
    return True

def add_premium_days(uid, days=30):
    until = int((datetime.now() + timedelta(days=days)).timestamp())
    c.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?", (until, uid))
    conn.commit()
    return until

def can_compress(uid): return is_premium_now(uid) or get_user(uid)[0] < LIMIT_FREE
def increment_count(uid):
    if not is_premium_now(uid):
        c.execute("UPDATE users SET videos_count = videos_count + 1 WHERE user_id=?", (uid,))
        conn.commit()

# ------------------- TUGMALAR (pydantic 2.9+ mos) -------------------
def main_menu(uid):
    kb = [[KeyboardButton(text="Video siqish")]]
    row = [KeyboardButton(text="Premium olish"), KeyboardButton(text="Statistika")]
    if is_premium_now(uid):
        row.insert(1, KeyboardButton(text="Sozlamalar"))
    if uid == ADMIN_ID:
        row.append(KeyboardButton(text="Admin panel"))
    kb.append(row)
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def settings_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Sifat tanlash"), KeyboardButton(text="Preview")],
        [KeyboardButton(text="Tarix"), KeyboardButton(text="Obuna holati")],
        [KeyboardButton(text="Orqaga")]
    ], resize_keyboard=True)

def admin_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Yangi kod yaratish", callback_data="admin_newcode")],
        [InlineKeyboardButton(text="5 ta kod yaratish", callback_data="admin_newcode_5")],
        [InlineKeyboardButton(text="10 ta kod yaratish", callback_data="admin_newcode_10")],
        [InlineKeyboardButton(text="Foydalanuvchiga +30 kun", callback_data="admin_add30")],
        [InlineKeyboardButton(text="Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="Barchaga xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="Orqaga", callback_data="admin_back")]
    ])

def back_to_admin():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Orqaga", callback_data="admin_back")]])

# ------------------- START -------------------
@router.message(Command("start"))
async def start(message: types.Message):
    uid = message.from_user.id
    premium = is_premium_now(uid)
    _, _, until, _, _ = get_user(uid)

    if premium and until:
        days = (until - int(datetime.now().timestamp())) // 86400
        status = f"Premium | {days} kun qoldi"
        if days <= 3:
            await message.answer(f"Premiumingiz {days} kundan keyin tugaydi!\nYangi olish: @oxunov_mr")
    else:
        status = "Bepul"

    await message.answer(
        f"Assalomu alaykum <b>{message.from_user.first_name}</b>!\n\n"
        "ShrinkerBot – video hajmini 3-15 baravar kamaytiradi!\n"
        "<b>Sifat saqlanadi!</b>\n\n"
        f"Status: <b>{status}</b>\n\n"
        "Video yuboring",
        reply_markup=main_menu(uid)
    )

# ------------------- ADMIN PANELGA KIRISH -------------------
@router.message(F.text == "Admin panel")
async def show_admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Admin panel", reply_markup=admin_panel_kb())

# ------------------- PREMIUM KOD -------------------
@router.message(F.text.regexp(r"^[A-Z0-9]{8}$"))
async def activate_code(message: types.Message):
    code = message.text.strip().upper()
    c.execute("SELECT used FROM codes WHERE code=?", (code,))
    row = c.fetchone()
    if row and row[0] == 0:
        until = add_premium_days(message.from_user.id, PREMIUM_DAYS)
        c.execute("UPDATE codes SET used=1, used_by=? WHERE code=?", (message.from_user.id, code))
        conn.commit()
        await message.answer(
            "TABRIKLAYMIZ!\n\n"
            f"<b>{PREMIUM_DAYS} kunlik Premium</b> faollashtirildi!\n"
            f"Tugash: <b>{datetime.fromtimestamp(until):%d.%m.%Y}</b>\n\n"
            "Endi cheksiz + 2 GB + yuqori sifat!\n\nRahmat",
            reply_markup=main_menu(message.from_user.id)
        )
    else:
        await message.answer("Kod noto‘g‘ri yoki ishlatilgan!")

# ------------------- SOZLAMALAR -------------------
@router.message(F.text == "Sozlamalar")
async def settings(m: types.Message):
    if not is_premium_now(m.from_user.id):
        await m.answer("Sozlamalar faqat Premium uchun!")
        return
    await m.answer("Sozlamalar", reply_markup=settings_menu())

@router.message(F.text == "Sifat tanlash")
async def quality_select(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Low (tez)", callback_data="q_low")],
        [InlineKeyboardButton(text="Medium (tavsiya)", callback_data="q_medium")],
        [InlineKeyboardButton(text="High", callback_data="q_high")],
        [InlineKeyboardButton(text="Ultra (eng sifatli)", callback_data="q_ultra")],
    ])
    await m.answer("Siqish sifatini tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("q_"))
async def set_quality(cb: types.CallbackQuery):
    q = cb.data[2:]
    c.execute("UPDATE users SET quality=? WHERE user_id=?", (q, cb.from_user.id))
    conn.commit()
    await cb.message.edit_text(f"Sifat: <b>{q.upper()}</b> tanlandi")
    await cb.answer()

@router.message(F.text == "Preview")
async def toggle_preview(m: types.Message):
    _, _, _, _, prev = get_user(m.from_user.id)
    new = 0 if prev else 1
    c.execute("UPDATE users SET preview=? WHERE user_id=?", (new, m.from_user.id))
    conn.commit()
    await m.answer(f"Preview {'yoqildi' if new else 'o‘chirildi'}")

@router.message(F.text == "Tarix")
async def history(m: types.Message):
    c.execute("SELECT file_name, date, file_id FROM videos WHERE user_id=? ORDER BY id DESC LIMIT 15", (m.from_user.id,))
    rows = c.fetchall()
    if not rows:
        await m.answer("Tarix bo‘sh")
        return
    text = "Oxirgi videolar:\n\n"
    kb = []
    for i, (name, date, fid) in enumerate(rows, 1):
        name = name or "video.mp4"
        text += f"{i}. {name[:30]} — {date}\n"
        kb.append([InlineKeyboardButton(text=f"{i}. {name[:25]}", callback_data=f"re_{fid}")])
    await m.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("re_"))
async def resend_video(cb: types.CallbackQuery):
    await bot.send_video(cb.message.chat.id, cb.data[3:], caption="Tarixdan qayta yuklandi")
    await cb.answer()

@router.message(F.text == "Obuna holati")
async def sub_status(m: types.Message):
    if not is_premium_now(m.from_user.id):
        await m.answer("Sizda Premium yo‘q")
        return
    _, _, until, _, _ = get_user(m.from_user.id)
    days = (until - int(datetime.now().timestamp())) // 86400
    await m.answer(f"Premium faol\nQoldi: <b>{days}</b> kun\nTugash: <b>{datetime.fromtimestamp(until):%d.%m.%Y}</b>")

@router.message(F.text == "Orqaga")
async def back(m: types.Message):
    await m.answer("Bosh sahifa", reply_markup=main_menu(m.from_user.id))

# ------------------- VIDEO SIQISH -------------------
async def compress_video(input_path: str, uid: int):
    quality = get_user(uid)[3]
    s = QUALITY_SETTINGS.get(quality, QUALITY_SETTINGS["medium"])
    output_path = input_path.replace(".mp4", "_shrunk.mp4")
    stream = ffmpeg.input(input_path)
    stream = ffmpeg.output(stream, output_path, **{
        "c:v": "libx265", "crf": s["crf"], "preset": s["preset"],
        "c:a": "copy", "vf": "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    })
    await asyncio.to_thread(ffmpeg.run, stream, overwrite_output=True, quiet=True)
    return output_path

@router.message(F.video)
async def video_handler(message: types.Message):
    uid = message.from_user.id
    size = message.video.file_size
    premium = is_premium_now(uid)

    if size > MAX_SIZE_PREMIUM:
        await message.answer("2 GB dan katta fayllar hozircha qo‘llab-quvvatlanmaydi")
        return
    if not premium and size > MAX_SIZE_FREE:
        await message.answer("500 MB dan katta video faqat Premiumda!\n@oxunov_mr")
        return
    if not can_compress(uid):
        await message.answer("Bepul limit tugadi (10/10)\nPremium oling: @oxunov_mr")
        return

    status = await message.answer("Yuklanmoqda...")
    file = await bot.get_file(message.video.file_id)
    inp = f"temp_{uid}_{message.message_id}.mp4"

    try:
        await bot.download_file(file.file_path, inp, timeout=1200)
        orig = os.path.getsize(inp)
        await status.edit_text("Siqilmoqda... (H.265)")

        cloud_fid = message.video.file_id
        if size > 1000*1024*1024:
            sent = await bot.send_video(CLOUD_CHANNEL, message.video.file_id,
                                        caption=f"User: {uid} | {datetime.now():%d.%m %H:%M}")
            cloud_fid = sent.video.file_id

        async with semaphore:
            out = await compress_video(inp, uid)

        shrunk = os.path.getsize(out)
        saved = orig - shrunk
        perc = saved / orig * 100 if orig else 0

        await status.delete()
        await message.answer_video(
            FSInputFile(out),
            caption=f"Siqildi!\n\nOldin: <b>{format_size(orig)}</b>\n"
                    f"Keyin: <b>{format_size(shrunk)}</b>\n"
                    f"Kamayish: <b>{format_size(saved)}</b> ({perc:.1f}%)"
        )

        c.execute("INSERT INTO videos(user_id, file_id, file_name, date) VALUES(?, ?, ?, ?)",
                  (uid, cloud_fid, message.video.file_name or "video.mp4", datetime.now().strftime("%d.%m.%Y %H:%M")))
        conn.commit()
        increment_count(uid)

    except Exception as e:
        log.exception(e)
        await status.edit_text("Xatolik yuz berdi. Qayta urining.")
    finally:
        for p in (inp, out if 'out' in locals() else None):
            try: os.unlink(p) if p and os.path.exists(p) else None
            except: pass

# ------------------- ADMIN CALLBACKS -------------------
@router.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("Ruxsat yo‘q!", show_alert=True)
        return

    d = cb.data
    if d == "admin_newcode":
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        c.execute("INSERT OR IGNORE INTO codes(code) VALUES(?)", (code,))
        conn.commit()
        await cb.message.edit_text(f"Yangi kod:\n\n<code>{code}</code>\n\n30 kunlik Premium", reply_markup=back_to_admin())

    elif d in ("admin_newcode_5", "admin_newcode_10"):
        n = 5 if d.endswith("5") else 10
        codes = [''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)) for _ in range(n)]
        for code in codes: c.execute("INSERT OR IGNORE INTO codes(code) VALUES(?)", (code,))
        conn.commit()
        text = f"{n} ta yangi kod:\n\n" + "\n".join(f"<code>{c}</code>" for c in codes) + "\n\nHar biri — 30 kun"
        await cb.message.edit_text(text, reply_markup=back_to_admin())

    elif d == "admin_add30":
        await cb.message.edit_text("Foydalanuvchi ID sini yuboring:")

    elif d == "admin_stats":
        c.execute("SELECT COUNT(*) FROM users"); total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE premium_until > ?", (int(datetime.now().timestamp()),)); prem = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM videos"); vids = c.fetchone()[0]
        await cb.message.edit_text(f"Foydalanuvchilar: <b>{total}</b>\nPremium: <b>{prem}</b>\nVideo siqilgan: <b>{vids}</b>", reply_markup=back_to_admin())

    elif d == "admin_broadcast":
        await cb.message.edit_text("Xabar yuborish uchun reply qilib yuboring\n/cancel — bekor")

    elif d == "admin_back":
        await cb.message.edit_text("Admin panel", reply_markup=admin_panel_kb())

    await cb.answer()

@router.message(F.text.regexp(r"^\d+$"))
async def admin_add30_by_id(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        tid = int(m.text.strip())
        until = add_premium_days(tid, 30)
        await m.answer(f"{tid} ga +30 kun qo‘shildi!\nTugash: {datetime.fromtimestamp(until):%d.%m.%Y}")
    except:
        await m.answer("Xato ID")

@router.message(Command("broadcast"))
async def broadcast(m: types.Message):
    if m.from_user.id != ADMIN_ID or not m.reply_to_message: return
    await m.answer("Broadcast boshlandi...")
    c.execute("SELECT user_id FROM users")
    success = blocked = 0
    for (uid,) in c.fetchall():
        try:
            await bot.copy_message(uid, m.chat.id, m.reply_to_message.message_id)
            success += 1
            await asyncio.sleep(0.04)
        except: blocked += 1
    await m.answer(f"Yuborildi: {success}\nBloklagan: {blocked}")

@router.message(Command("cancel"))
async def cancel(m: types.Message):
    if m.from_user.id == ADMIN_ID:
        await m.answer("Amal bekor qilindi", reply_markup=admin_panel_kb())

# ------------------- RUN -------------------
async def main():
    print("ShrinkerBot 2025 ULTIMATE — ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
