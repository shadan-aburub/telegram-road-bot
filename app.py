import logging
import nest_asyncio
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest

# 📝 إعداد تسجيل الأخطاء والمعلومات
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ✅ توكن البوت (استبدله بالتوكن الصحيح)
TOKEN = "7847557134:AAGgwjeq7y60ebnaWn6C8G4tdN0Ds1pnwvg"

# ✅ إعداد معلومات Telethon
api_id = "28676160"
api_hash = "e0f42bfeecf3d31695574a1d18205dcb"
phone_number = "+962788065755"

# ✅ قنوات Telegram لجلب الأخبار منها
channels = ["https://t.me/jehad_yassin1", "https://t.me/road_jehad"]

# 🛑 الكلمات التي إذا وُجدت في الخبر يتم استبعاده بالكامل
EXCLUDE_WORDS = ["?", "كيف", "حد عندو علم", "شو الوضع", "يعني مش ازمة"]

# 🟢 الكلمات المهمة التي نبحث عنها في الأخبار
KEYWORDS = ["مغلق", "ازمة", "أزمة", "سالكة", "مفتوح", "مفتوحة", "غير سالكة", "يغلق", "اغلاق", "فاتحة"]

# 🔹 دالة لجلب الأخبار من القنوات بدون الأخبار التي تحتوي على الكلمات الممنوعة
async def get_latest_news(start_time, end_time):
    news = []

    try:
        async with TelegramClient("session_name", api_id, api_hash) as client:
            if not client.is_user_authorized():
                await client.send_code_request(phone_number)
                await client.sign_in(phone_number, input('Please enter the code you received: '))
            
            for channel in channels:
                entity = await client.get_entity(channel)
                history = await client(GetHistoryRequest(
                    peer=entity,
                    limit=100,
                    offset_date=end_time,
                    offset_id=0,
                    max_id=0,
                    min_id=0,
                    add_offset=0,
                    hash=0
                ))

                for message in history.messages:
                    if message.message and not message.reply_to_msg_id and message.date.replace(tzinfo=timezone.utc) >= start_time:
                        if any(keyword in message.message for keyword in KEYWORDS):
                            # ✅ استبعاد الأخبار التي تحتوي على أي من الكلمات الممنوعة
                            exclude = False
                            for exclude_word in EXCLUDE_WORDS:
                                if exclude_word in message.message:
                                    exclude = True
                                    break
                            if exclude:
                                continue  # ⬅️ لا تضيف هذا الخبر إلى القائمة

                            news.append(f"📢 {message.message}")

        return news
    except Exception as e:
        logger.error(f"❌ خطأ في جلب الأخبار: {e}")
        return []

# 🔹 دالة للحصول على الأخبار كل ربع ساعة
async def get_news_every_quarter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """جلب الأخبار كل ربع ساعة"""
    while True:
        start_time = datetime.now(timezone.utc) - timedelta(minutes=15)
        end_time = datetime.now(timezone.utc)
        news = await get_latest_news(start_time, end_time)

        # إذا لم تكن هناك أخبار في آخر ربع ساعة، حاول جلب الأخبار الأقدم
        while not news:
            end_time = start_time
            start_time = start_time - timedelta(minutes=15)
            news = await get_latest_news(start_time, end_time)

        news_message = "\n\n".join(news) if news else "🚫 لا توجد أخبار جديدة."
        await send_message_in_chunks(update, news_message)
        await asyncio.sleep(900)  # الانتظار 15 دقيقة

# 🔹 دالة تقسيم الرسائل الطويلة إلى أجزاء صغيرة
async def send_message_in_chunks(update: Update, message: str) -> None:
    max_length = 4096  # الحد الأقصى لطول الرسالة في Telegram
    for i in range(0, len(message), max_length):
        await update.message.reply_text(message[i:i + max_length], parse_mode="Markdown")

# 🔹 دالة بدء البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إرسال رسالة ترحيب مع قائمة خيارات."""
    reply_keyboard = [["🛣️ حالة الطريق", "📰 أخبار الطرق كل ربع ساعة"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)

    await update.message.reply_text(
        "🚗 *مرحبًا بك في بوت أخبار وحالة الطرق!* \n\n"
        "اختر أحد الخيارات أدناه للحصول على التحديثات:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    logger.info("تم إرسال لوحة المفاتيح للمستخدم")

# 🔹 دالة طلب حالة الطريق
async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """طلب حالة الطريق من المستخدم."""
    await update.message.reply_text("🚗 الرجاء إدخال اسم المنطقة أو المكان:")
    return 1

# 🔹 دالة معالجة اسم المنطقة أو المكان وإرسال حالته
async def handle_location_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة اسم المنطقة أو المكان وإرسال طلب الحالة."""
    location_name = update.message.text
    start_of_day = datetime.now(timezone.utc) - timedelta(hours=12)
    news = await get_latest_news(start_of_day, datetime.now(timezone.utc))
    road_status = "معلومات غير متوفرة"

    for message in news:
        if location_name in message:
            if any(keyword in message for keyword in ["مغلق", "يغلق", "اغلاق", "غير سالكة"]):
                road_status = "مغلقة"
            elif any(keyword in message for keyword in ["مفتوح", "مفتوحة", "سالكة"]):
                road_status = "مفتوحة" if road_status == "معلومات غير متوفرة" else road_status
    
    await update.message.reply_text(f"🚗 حالة الطريق في {location_name}: {road_status}")
    return ConversationHandler.END

# 🔹 دالة معالجة الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة الرسائل وإرسال ردود مناسبة."""
    text = update.message.text
    logger.info(f"📩 رسالة مستلمة: {text}")

    reply_keyboard = [["🛣️ حالة الطريق", "📰 أخبار الطرق كل ربع ساعة"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)

    if text == "📰 أخبار الطرق كل ربع ساعة":
        await get_news_every_quarter(update, context)
    elif text == "🛣️ حالة الطريق":
        await handle_status(update, context)
    else:
        await update.message.reply_text("❌ الرجاء اختيار خيار من القائمة.", reply_markup=markup)

# 🔹 دالة التعامل مع الأخطاء
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"❌ خطأ غير متوقع: {context.error}")

# 🔹 تشغيل البوت
async def main():
    """تشغيل البوت."""
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('🛣️ حالة الطريق'), handle_status)],
        states={1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_location_name)]},
        fallbacks=[],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("✅ البوت قيد التشغيل...")
    await application.run_polling(poll_interval=10)

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())





 



















    






