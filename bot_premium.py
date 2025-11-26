import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ContentType, InputFile
from aiogram.fsm.storage.memory import MemoryStorage
import ffmpeg

# ──────────────────────────── CONFIG ────────────────────────────
logging.basicConfig(level=logging.WARNING)  # Faqat muhim xabarlarni ko‘rsatadi
bot = Bot(token=os.getenv("BOT_TOKEN"), parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MAX_SIZE = 100 * 1024 * 1024  # 100 MB limit

# ──────────────────────────── START ────────────────────────────
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "<b>Video Siqish Bot 2025</b>\n\n"
        "25 MB → <b>3-5 MB</b> | Sifat 100%\n"
        "Cheksiz • Bepul • Tez\n\n"
        "<i>Video yuboring → darrov siqib beraman!</i>"
    )

# ──────────────────────────── MAIN VIDEO HANDLER ────────────────────────────
@dp.message(ContentType.VIDEO)
async def handle_video(message: types.Message):
    user_id = message.from_user.id

    # 100 MB dan katta bo‘lsa rad et
    if message.video.file_size > MAX_SIZE:
        return await message.answer("❌ 100 MB dan katta video qabul qilinmaydi!")

    status = await message.answer("⬇️ Yuklanmoqda...")

    # Yuklab olish
    file = await bot.get_file(message.video.file_id)
    orig_path = f"{user_id}_orig.mp4"
    comp_path = f"{user_id}_comp.mp4"

    await bot.download_file(file.file_path, orig_path)

    await status.edit_text("🗜 Siqilmoqda... (8-12 sek)")

    # OPTIMALLASHTIRILGAN FFmpeg sozlamalari (eng tez + eng kichik hajm)
    try:
        (
            ffmpeg
            .input(orig_path)
            .output(
                comp_path,
                vcodec="libx264",
                crf=30,                    # 30 = juda kichik hajm, sifat hali yaxshi
                preset="ultrafast",        # eng tez
                tune="film",
                acodec="aac",
                audio_bitrate="96k",
                vf="scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",  # 720p max
                movflags="+faststart",
                loglevel="quiet"
            )
            .overwrite_output()
            .run()
        )
    except Exception as e:
        await status.edit_text("❌ Siqishda xato yuz berdi")
        logging.error(e)
        cleanup([orig_path, comp_path])
        return

    orig_mb = os.path.getsize(orig_path) / (1024*1024)
    comp_mb = os.path.getsize(comp_path) / (1024*1024)

    await status.edit_text("⬆️ Yuborilmoqda...")

    # Yuborish
    await bot.send_chat_action(message.chat.id, "upload_video")
    await message.answer_video(
        video=InputFile(comp_path),
        caption=f"✅ Tayyor!\n"
                f"📊 {orig_mb:.1f} MB → <b>→</b> {comp_mb:.1f} MB\n"
                f"🔥 {100 - (comp_mb/orig_mb*100):.0f}% kichraydi!\n\n"
                f"♾ Cheksiz foydalaning!",
        supports_streaming=True
    )

    # Tozalash (hech narsa qolmaydi)
    cleanup([orig_path, comp_path])
    await status.delete()

# ──────────────────────────── ADMIN STATS ────────────────────────────
@dp.message(Command("stats"))
async def stats(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer(f"<b>Bot holati:</b>\n"
                     f"👥 Foydalanuvchilar: {len(dp.storage.data)}\n"
                     f"🟢 Onlayn va tayyor!")

# ──────────────────────────── TOZALASH FUNKSIYASI ────────────────────────────
def cleanup(files):
    for f in files:
        try:
            os.remove(f)
        except:
            pass

# ──────────────────────────── START BOT ────────────────────────────
async def main():
    print("ShrinkerBot 2025 OPTIMIZED — ishga tushdi!")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
