from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

players = []
current_player_index = 0
questions = {
    "جرأت": ["جرأت سوال 1", "جرأت سوال 2"],
    "حقیقت": ["حقیقت سوال 1", "حقیقت سوال 2"]
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("عضویت", callback_data="join")],
                [InlineKeyboardButton("شروع بازی", callback_data="start_game")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("سلام! برای شروع بازی دکمه‌ها را بزنید:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_player_index
    query = update.callback_query
    await query.answer()

    if query.data == "join":
        user_id = query.from_user.id
        if user_id not in players:
            players.append(user_id)
            await query.edit_message_text(f"شما عضو بازی شدید. تعداد بازیکنان: {len(players)}")
        else:
            await query.answer("شما قبلا عضو شدید!", show_alert=True)

    elif query.data == "start_game":
        if not players:
            await query.answer("هیچ کسی عضو نیست!", show_alert=True)
            return
        current_player_index = 0
        await ask_dare_or_truth(update, context)

    elif query.data in ["جرأت", "حقیقت"]:
        player = players[current_player_index]
        question = questions[query.data][0]  # ساده گرفته شده، میتونی رندوم کنی
        await query.edit_message_text(f"برای بازیکن {player}: سوال {query.data}: {question}")
        # حالا دکمه پاسخ دادم رو می‌فرستیم
        keyboard = [[InlineKeyboardButton("پاسخ دادم", callback_data="answered")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=query.message.chat_id, text="وقتی پاسخ دادی، بزن پاسخ دادم", reply_markup=reply_markup)

    elif query.data == "answered":
        current_player_index += 1
        if current_player_index >= len(players):
            current_player_index = 0
            await context.bot.send_message(chat_id=query.message.chat_id, text="بازی تموم شد! دوباره شروع می‌کنیم.")
        await ask_dare_or_truth(update, context)

async def ask_dare_or_truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = players[current_player_index]
    keyboard = [[InlineKeyboardButton("جرأت", callback_data="جرأت"),
                 InlineKeyboardButton("حقیقت", callback_data="حقیقت")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"نوبت بازیکن {player} است: جرأت یا حقیقت؟", reply_markup=reply_markup)

if __name__ == "__main__":
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()
