import asyncio
import os
import io
import logging
import threading
import qrcode
import requests
from flask import Flask
from PIL import Image
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройка логирования, чтобы видеть ВСЁ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
DEV_URL = "https://t.me/ZYB_19" 

QR_GENERATING, IMG_CONVERTING, WAITING_FOR_OCR = range(1, 4)

def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔳 Создать QR"), KeyboardButton("🖼 Конвертер")],
        [KeyboardButton("📝 Текст с фото"), KeyboardButton("ℹ️ Инфо")],
        [KeyboardButton("❌ Отмена")]
    ], resize_keyboard=True)

# --- БАЗОВЫЕ КОМАНДЫ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"--- Получена команда /start от {update.effective_user.id} ---")
    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}! 👋\nЯ iAssistant. Выберите действие на клавиатуре:",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отмена. Возврат в меню.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💻 Разработчик", url=DEV_URL)]])
    await update.message.reply_text(" **iAssistant Support**\nВсе системы работают штатно ✅", reply_markup=kb, parse_mode="Markdown")

# --- ЛОГИКА QR ---
async def qr_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔗 Пришлите текст для создания QR-кода:")
    return QR_GENERATING

async def qr_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Генерация QR...")
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(update.message.text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="#ffffff")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    await update.message.reply_photo(photo=bio, caption="✨ Твой QR-код готов!", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# --- ЛОГИКА ФОТО (OCR) ---
async def ocr_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Пришлите фото, с которого нужно считать текст:")
    return WAITING_FOR_OCR

async def ocr_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Читаю текст...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        files = {'file': ('img.jpg', io.BytesIO(photo_bytes), 'image/jpeg')}
        payload = {'apikey': 'K89996852888957', 'language': 'rus', 'OCREngine': 2}
        res = requests.post('https://api.ocr.space/parse/image', files=files, data=payload, timeout=20).json()
        
        if res.get("ParsedResults"):
            text = res["ParsedResults"][0]["ParsedText"]
            await msg.edit_text(f"📖 **Результат:**\n\n`{text}`", parse_mode="Markdown")
        else:
            await msg.edit_text("❌ Не удалось найти текст.")
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        await msg.edit_text("❌ Ошибка при обработке.")
    return ConversationHandler.END

# ================= ЗАПУСК =================

server = Flask(__name__)
@server.route("/")
def health(): return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    if not TOKEN:
        print("ОШИБКА: BOT_TOKEN не найден в переменных окружения!")
        exit(1)

    # 1. Запуск Flask
    threading.Thread(target=run_flask, daemon=True).start()

    # 2. Настройка бота
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Text(["ℹ️ Инфо", "Инфо"]), info_handler))

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Text("🔳 Создать QR"), qr_request),
            MessageHandler(filters.Text("📝 Текст с фото"), ocr_request),
        ],
        states={
            QR_GENERATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, qr_process)],
            WAITING_FOR_OCR: [MessageHandler(filters.PHOTO, ocr_process)],
        },
        fallbacks=[MessageHandler(filters.Text(["❌ Отмена", "Отмена"]), cancel)]
    )
    app.add_handler(conv)

    print("--- РОБОТ ВЫХОДИТ НА СВЯЗЬ ---")
    app.run_polling()
