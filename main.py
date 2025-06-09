from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os, random

TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! برای بازی /play رو بزن")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questions = ["حقیقت: تا حالا عاشق شدی؟", "حقیقت: بزرگ‌ترین دروغی که گفتی چی بوده؟"]
    dares = ["جرأت: یه جمله عاشقانه توی گروه بنویس", "جرأت: یه جوک بی‌مزه بگو"]
    if random.choice(["truth", "dare"]) == "truth":
        await update.message.reply_text(random.choice(questions))
    else:
        await update.message.reply_text(random.choice(dares))

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("play", play))

app.run_polling()
