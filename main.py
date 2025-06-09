import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

TOKEN = "7611408660:AAH9fAiPglhU4ldLCLhwFt4_3qvTiFZhTbw"  # توکن خودت رو بذار

logging.basicConfig(level=logging.INFO)

games = {}  # group_id -> game data
user_states = {}

# اضافه کردن تعداد مجاز تغییر سوال به تنظیمات بازی
# برای هر بازی، تعداد تغییر سوال مجاز را ذخیره می‌کنیم (default=1)
DEFAULT_CHANGE_LIMIT = 1

def load_questions():
    with open("truth.txt", "r", encoding="utf-8") as f:
        truths = [line.strip() for line in f if line.strip()]
    with open("dare.txt", "r", encoding="utf-8") as f:
        dares = [line.strip() for line in f if line.strip()]
    return truths, dares

truth_questions, dare_challenges = load_questions()

def get_game(chat_id):
    if chat_id not in games:
        games[chat_id] = {
            'creator': None,
            'members': [],
            'state': 'waiting',  # 'waiting', 'started'
            'current_index': 0,
            'current_msg_id': None,
            'current_question_type': None,
            'used_change': {},  # user_id -> تعداد دفعات تغییر سوال استفاده شده
            'change_limit': DEFAULT_CHANGE_LIMIT,
            'message_id': None,
            'current_user': None,
        }
    return games[chat_id]

async def start_game_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("بازی جدید", callback_data='بازی_جدید')]]
    await update.message.reply_text("برای شروع بازی دکمه زیر را بزنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    user_name = query.from_user.first_name

    if chat_id in games:
        games.pop(chat_id)

    games[chat_id] = {
        'creator': user_id,
        'members': [user_id],
        'state': 'waiting',
        'used_change': {user_id: 0},
        'change_limit': DEFAULT_CHANGE_LIMIT,
        'message_id': None,
        'current_index': 0,
        'current_msg_id': None,
        'current_question_type': None,
        'current_user': None,
    }
    game = games[chat_id]

    member_names = [user_name]

    text = f"بازی توسط {user_name} ساخته شد!\n\nاعضای بازی:\n" + "\n".join(member_names)
    keyboard = [
        [InlineKeyboardButton("عضویت", callback_data='عضویت')],
        [InlineKeyboardButton("شروع بازی", callback_data='شروع_بازی')]
    ]

    await query.message.delete()
    sent_msg = await context.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard))
    game['message_id'] = sent_msg.message_id
    await query.answer()

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    game = get_game(chat_id)

    if user_id in game['members']:
        await query.answer("شما قبلاً عضو بازی شده‌اید.", show_alert=False)
        return

    game['members'].append(user_id)
    game['used_change'][user_id] = 0

    member_names = []
    for uid in game['members']:
        try:
            member = await context.bot.get_chat_member(chat_id, uid)
            member_names.append(member.user.first_name)
        except Exception:
            member_names.append("نامشخص")

    creator_name = (await context.bot.get_chat_member(chat_id, game['creator'])).user.first_name

    text = f"بازی توسط {creator_name} ساخته شد!\n\nاعضای بازی:\n" + "\n".join(member_names)
    keyboard = [
        [InlineKeyboardButton("عضویت", callback_data='عضویت')],
        [InlineKeyboardButton("شروع بازی", callback_data='شروع_بازی')]
    ]

    # **اینجا به جای ارسال پیام جدید، پیام قبلی را ویرایش می‌کنیم**
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    await query.answer()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    game = get_game(chat_id)
    if user_id != game['creator']:
        await query.answer("فقط سازنده بازی می‌تواند بازی را شروع کند.", show_alert=False)
        return

    if len(game['members']) < 2:
        await query.answer("برای شروع بازی حداقل دو عضو لازم است.", show_alert=False)
        return

    game['state'] = 'started'
    game['current_index'] = 0

    await query.message.delete()
    await query.answer()
    await send_turn_message(chat_id, context)

async def send_turn_message(chat_id, context):
    game = get_game(chat_id)
    user_id = game['members'][game['current_index']]
    user = await context.bot.get_chat_member(chat_id, user_id)

    keyboard = [
        [InlineKeyboardButton("جرأت", callback_data='جرأت'),
         InlineKeyboardButton("حقیقت", callback_data='حقیقت')]
    ]

    # نوبت کاربر با تگ HTML اعلام می‌شود و فقط به همان کاربر اجازه انتخاب دکمه داده می‌شود
    msg = await context.bot.send_message(
        chat_id,
        text=f"نوبت {user.user.mention_html()} است. یکی را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    game['current_msg_id'] = msg.message_id
    game['current_user'] = user.user.id

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    game = get_game(chat_id)

    # فقط کاربر نوبت دار اجازه انتخاب دارد
    if user_id != game['current_user']:
        await query.answer("نوبت شما نیست!", show_alert=False)
        return

    # بازنشانی دفعات تغییر سوال برای این نوبت
    game['used_change'][user_id] = 0

    if query.data == 'حقیقت':
        q = random.choice(truth_questions)
        game['current_question_type'] = 'حقیقت'
    else:
        q = random.choice(dare_challenges)
        game['current_question_type'] = 'جرأت'

    keyboard = [
        [InlineKeyboardButton("تغییر سوال", callback_data='تغییر_سوال')],
        [InlineKeyboardButton("جواب دادم", callback_data='جواب_دادم')]
    ]

    # پیام را ویرایش می‌کنیم به جای ارسال پیام جدید
    await query.message.edit_text(f"{query.message.text_html}\n\nسوال: {q}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    await query.answer()

async def change_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    game = get_game(chat_id)

    if user_id != game.get('current_user'):
        await query.answer("فقط کسی که نوبتش هست می‌تونه سوال رو عوض کنه.", show_alert=False)
        return

    # چک کردن تعداد دفعات تغییر سوال
    used = game['used_change'].get(user_id, 0)
    if used >= game.get('change_limit', DEFAULT_CHANGE_LIMIT):
        await query.answer(f"شما فقط {game.get('change_limit', DEFAULT_CHANGE_LIMIT)} بار می‌تونید سوال رو تغییر بدید.", show_alert=False)
        return

    if game['current_question_type'] == 'حقیقت':
        q = random.choice(truth_questions)
    else:
        q = random.choice(dare_challenges)

    game['used_change'][user_id] = used + 1

    # ویرایش پیام سوال در همان پیام
    base_text = query.message.text_html.split('سوال:')[0]
    await query.message.edit_text(f"{base_text}\n\nسوال: {q}", parse_mode="HTML", reply_markup=query.message.reply_markup)
    await query.answer()

async def answered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    game = get_game(chat_id)

    if user_id != game.get('current_user'):
        await query.answer("فقط کسی که نوبتش هست می‌تونه پاسخ بده.", show_alert=False)
        return

    await query.message.delete()
    game['current_index'] = (game['current_index'] + 1) % len(game['members'])
    await send_turn_message(chat_id, context)
    await query.answer()

# حذف دستور /add و /clear و اضافه کردن همه به دستور /set

async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    game = get_game(chat_id)

    # فقط سازنده اجازه تغییر تنظیمات را دارد
    if game['creator'] != user_id:
        await update.message.reply_text("فقط سازنده بازی می‌تواند تنظیمات را تغییر دهد.")
        return

    keyboard = [
        #[InlineKeyboardButton("افزودن سوال جدید", callback_data='set_افزودن_سوال')],  # حذف شد
        [InlineKeyboardButton(f"تعیین تعداد تغییر سوال (فعلی: {game.get('change_limit', DEFAULT_CHANGE_LIMIT)})", callback_data='set_تغییر_تعداد')],
        [InlineKeyboardButton("پاک کردن بازی", callback_data='set_پاک_کردن_بازی')]
    ]

    await update.message.reply_text("پنل تنظیمات بازی:", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    game = get_game(chat_id)

    if user_id != game['creator']:
        await query.answer("فقط سازنده بازی اجازه استفاده از این پنل را دارد.", show_alert=True)
        return

    if query.data == 'set_تغییر_تعداد':
        await query.message.edit_text("لطفاً تعداد دفعات مجاز تغییر سوال را (عدد صحیح) ارسال کنید:")
        user_states[user_id] = {"setting_change_limit": True}
        await query.answer()

    elif query.data == 'set_پاک_کردن_بازی':
        games.pop(chat_id, None)
        await query.message.edit_text("بازی پاک شد. می‌توانید بازی جدید بسازید.")
        await query.answer()

    else:
        await query.answer()  # برای دیگر داده‌ها پاسخی ندهد



async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    # اگر کاربر در حال اضافه کردن سوال است
    if user_id in user_states:
        state = user_states[user_id]

        if state.get("adding_to") in ["truth", "dare"]:
            category = state["adding_to"]
            filename = "truth.txt" if category == "truth" else "dare.txt"

            with open(filename, "a", encoding="utf-8") as f:
                f.write(text + "\n")

            global truth_questions, dare_challenges
            truth_questions, dare_challenges = load_questions()

            await update.message.reply_text(f"سوال شما به دسته {'حقیقت' if category=='truth' else 'جرأت'} اضافه شد.")
            user_states.pop(user_id)
            return

        if state.get("setting_change_limit"):
            if text.isdigit() and int(text) > 0:
                # باید بازی سازنده را پیدا کنیم (به ازای گروه)
                for chat_id, game in games.items():
                    if game['creator'] == user_id:
                        game['change_limit'] = int(text)
                        await update.message.reply_text(f"تعداد دفعات مجاز تغییر سوال به {text} تنظیم شد.")
                        user_states.pop(user_id)
                        return
                await update.message.reply_text("شما در هیچ بازی سازنده نیستید.")
            else:
                await update.message.reply_text("لطفاً یک عدد صحیح بزرگتر از صفر ارسال کنید.")
            return

    # اگر در حالت معمولی است، نادیده گرفته شود یا پیام عادی باشد

# حذف کامل دستورات /add و /clear

# اضافه کردن دستور /add برای اضافه کردن سوال (برای همه)
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("اضافه کردن به حقیقت", callback_data='اضافه_حقیقت')],
        [InlineKeyboardButton("اضافه کردن به جرأت", callback_data='اضافه_جرأت')],
        [InlineKeyboardButton("لغو", callback_data='add_لغو')]
    ]
    await update.message.reply_text("کدام دسته سوال را می‌خواهید اضافه کنید؟", reply_markup=InlineKeyboardMarkup(keyboard))


# هندلر دکمه‌های اضافه کردن سوال (مستقل از set)
async def add_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == 'اضافه_حقیقت':
        user_states[user_id] = {"adding_to": "truth"}
        await query.message.edit_text("لطفاً سوال جدید حقیقت را ارسال کنید:")
        await query.answer()

    elif query.data == 'اضافه_جرأت':
        user_states[user_id] = {"adding_to": "dare"}
        await query.message.edit_text("لطفاً سوال جدید جرأت را ارسال کنید:")
        await query.answer()

    elif query.data == 'add_لغو':
        user_states.pop(user_id, None)
        await query.message.edit_text("عملیات اضافه کردن سوال لغو شد.")
        await query.answer()

    else:
        await query.answer()

# پایان بازی
async def finish_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    game = get_game(chat_id)

    if game['creator'] != user_id:
        await update.message.reply_text("فقط سازنده بازی می‌تونه بازی رو پایان بده.")
        return

    keyboard = [
        [InlineKeyboardButton("بله، پایان بده", callback_data='تأیید_پایان')],
        [InlineKeyboardButton("لغو", callback_data='لغو_پایان')]
    ]
    await update.message.reply_text("آیا مطمئنید می‌خواهید بازی را پایان دهید؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def finish_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    game = get_game(chat_id)

    if query.data == 'تأیید_پایان':
        if game['creator'] == user_id:
            games.pop(chat_id, None)
            await query.message.edit_text("بازی پایان یافت.")
        else:
            await query.answer("فقط سازنده می‌تواند بازی را پایان دهد.", show_alert=True)
    else:
        await query.message.delete()

# ثبت هندلرها با تغییرات جدید
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_game_message))
    app.add_handler(CallbackQueryHandler(new_game, pattern="^بازی_جدید$"))
    app.add_handler(CallbackQueryHandler(join, pattern="^عضویت$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^شروع_بازی$"))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern="^(جرأت|حقیقت)$"))
    app.add_handler(CallbackQueryHandler(change_question, pattern="^تغییر_سوال$"))
    app.add_handler(CallbackQueryHandler(answered, pattern="^جواب_دادم$"))

    app.add_handler(CommandHandler("set", set_command))
    app.add_handler(CallbackQueryHandler(set_button_handler, pattern="^set_.*$|^set_پاک_کردن_بازی$"))

    # هندلرهای مربوط به اضافه کردن سوال (مستقل)
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CallbackQueryHandler(add_button_handler, pattern="^اضافه_.*$|^add_لغو$"))

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    app.add_handler(CommandHandler("finish", finish_command))
    app.add_handler(CallbackQueryHandler(finish_confirm, pattern="^(تأیید_پایان|لغو_پایان)$"))

    app.run_polling()
