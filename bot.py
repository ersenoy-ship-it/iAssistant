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

# ================= НАСТРОЙКИ =================
TOKEN = os.getenv("BOT_TOKEN")
DEV_URL = "https://t.me/ZYB_19" 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

QR_GENERATING, IMG_CONVERTING, WAITING_FOR_OCR = range(1, 4)

def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔳 Создать QR"), KeyboardButton("🖼 Конвертер")],
        [KeyboardButton("📝 Текст с фото"), KeyboardButton("ℹ️ Инфо")],
        [KeyboardButton("❌ Отмена")]
    ], resize_keyboard=True)

# ================= ФУНКЦИИ =================

def generate_qr(text):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="#ffffff")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}! 👋\nЯ iAssistant. Выберите действие:",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💻 Разработчик", url=DEV_URL)]])
    await update.message.reply_text(" **iAssistant Support**\nВсе системы работают штатно ✅", reply_markup=kb, parse_mode="Markdown")

async def qr_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔗 Пришлите текст для QR:")
    return QR_GENERATING

async def qr_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qr_img = generate_qr(update.message.text)
    await update.message.reply_photo(photo=qr_img, caption="✨ Готово", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def img_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Пришлите фото для PNG:")
    return IMG_CONVERTING

async def img_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = await update.message.photo[-1].get_file()
    img_bytes = await photo.download_as_bytearray()
    img = Image.open(io.BytesIO(img_bytes))
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    out.seek(0)
    await update.message.reply_document(document=out, filename="result.png", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def ocr_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Пришлите фото с текстом:")
    return WAITING_FOR_OCR

async def ocr_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = await update.message.photo[-1].get_file()
        api_url = f"https://api.ocr.space/parse/imageurl?apikey=K89996852888957&url={photo.file_path}&language=rus"
        res = requests.get(api_url).json()
        text = res["ParsedResults"][0]["ParsedText"] if res.get("ParsedResults") else "Текст не найден."
        await update.message.reply_text(f"📖 **Текст:**\n`{text}`", parse_mode="Markdown", reply_markup=main_menu_keyboard())
    except:
        await update.message.reply_text("Ошибка OCR.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ================= ЗАПУСК =================

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Text(["ℹ️ Инфо", "Инфо"]), info_handler))

conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Text("🔳 Создать QR"), qr_request),
        MessageHandler(filters.Text("🖼 Конвертер"), img_request),
        MessageHandler(filters.Text("📝 Текст с фото"), ocr_request),
    ],
    states={
        QR_GENERATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, qr_process)],
        IMG_CONVERTING: [MessageHandler(filters.PHOTO, img_process)],
        WAITING_FOR_OCR: [MessageHandler(filters.PHOTO, ocr_process)],
    },
    fallbacks=[MessageHandler(filters.Text(["❌ Отмена", "Отмена"]), cancel)]
)
app.add_handler(conv)

server = Flask(__name__)
@server.route("/")
def h(): return "OK", 200

def run_bot():
    """Ультимативный запуск бота через asyncio.run"""
    try:
        logger.info("🤖 Подготовка к запуску бота...")
        
        # Для версии 20.x+ часто лучше использовать такой подход:
        async def start_polling():
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            logger.info("🤖 Бот запущен и слушает сообщения!")
            # Держим цикл живым
            while True:
                await asyncio.sleep(3600)

        asyncio.run(start_polling())
    except Exception as e:
        logger.error(f"❌ Ошибка в потоке бота: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Запускаем сервер
    logger.info(f"🚀 Запуск Flask на порту {port}")
    server.run(host="0.0.0.0", port=port)

    # Запускаем Flask (основной поток)
    logger.info(f"Запуск Flask на порту {port}...")
    server.run(host="0.0.0.0", port=port)
