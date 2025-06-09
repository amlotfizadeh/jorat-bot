from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os, random

TOKEN = os.environ.get("BOT_TOKEN")

questions = ["راستشو بگو: آخرین باری که دروغ گفتی؟", "چه چیزی رو از همه پنهان کردی؟"]
dares = ["برو به یکی از اعضا پیام بده که دوستش داری!", "تا ۱ دقیقه فقط ایموجی حرف بزن!"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! آماده‌ای؟ برای بازی /play رو بزن")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = random.choice(["truth", "dare"])
    if choice == "truth":
        await update.message.reply_text(f"😇 حقیقت: {random.choice(questions)}")
    else:
        await update.message.reply_text(f"🔥 جرأت: {random.choice(dares)}")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("play", play))

app.run_polling()
