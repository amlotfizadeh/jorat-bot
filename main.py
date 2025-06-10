import logging
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
#from telegram.request import HTTPXRequest

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


logging.basicConfig(level=logging.INFO)

ADMIN_ID = 7406086721  
pending_questions = {}  

games = {}  # group_id -> game data
user_states = {}

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
            'used_questions': {}, 
        }
    return games[chat_id]

async def start_game_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    game = games.get(chat_id)

    if game and game['state'] == 'started':
        # بازی در حال اجرا است، پیام اعضا را با دکمه‌های جدید مجدد ارسال کن
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
            [InlineKeyboardButton("تعیین تعداد تغییر سوال", callback_data='تعیین_تعداد')],
            [InlineKeyboardButton("پایان بازی", callback_data='پایان_بازی')]
        ]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        keyboard = [[InlineKeyboardButton("بازی جدید", callback_data='بازی_جدید')]]
        await update.message.reply_text("برای شروع بازی دکمه زیر را بزنید:", reply_markup=InlineKeyboardMarkup(keyboard))


async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    user_name = query.from_user.first_name

    # اگر بازی در حال اجرا باشد اجازه ساخت بازی جدید نده
    if chat_id in games and games[chat_id]['state'] == 'started':
        await query.answer("بازی در حال حاضر در جریان است. ابتدا بازی فعلی را تمام کنید.", show_alert=True)
        return

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
        'used_questions': {}, 
    }
    game = games[chat_id]

    member_names = [user_name]
    text = f"بازی توسط {user_name} ساخته شد!\n\nاعضای بازی:\n" + "\n".join(member_names)

    keyboard = [
        [InlineKeyboardButton("عضویت", callback_data='عضویت')],
        [InlineKeyboardButton("شروع بازی", callback_data='شروع_بازی')]
    ]

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
    game['used_questions'][user_id] = {'حقیقت': set(), 'جرأت': set()}

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

    # تغییر دکمه‌های پیام اصلی (حذف نشود)
    member_names = []
    for uid in game['members']:
        try:
            member = await context.bot.get_chat_member(chat_id, uid)
            member_names.append(member.user.first_name)
        except Exception:
            member_names.append("نامشخص")

    text = f"بازی توسط {(await context.bot.get_chat_member(chat_id, game['creator'])).user.first_name} ساخته شد!\n\nاعضای بازی:\n" + "\n".join(member_names)
    keyboard = [
        [InlineKeyboardButton("تعیین تعداد تغییر سوال", callback_data='تعیین_تعداد')],
        [InlineKeyboardButton("پایان بازی", callback_data='پایان_بازی')]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    await query.answer()
    await send_turn_message(chat_id, context)



async def game_settings_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    game = get_game(chat_id)

    if user_id != game['creator']:
        await query.answer("فقط سازنده بازی می‌تواند این تنظیمات را تغییر دهد.", show_alert=True)
        return

    if query.data == 'تعیین_تعداد':
        await query.message.reply_text("لطفاً تعداد دفعات مجاز تغییر سوال را ارسال کنید:")
        user_states[user_id] = {"setting_change_limit": True}
        await query.answer()
    elif query.data == 'پایان_بازی':
        games.pop(chat_id, None)
        await query.message.edit_text("بازی با موفقیت به پایان رسید. می‌توانید بازی جدیدی شروع کنید.")
        await query.answer()






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



def get_unique_question(user_id, qtype, game):
    used = game['used_questions'].get(user_id, {'حقیقت': set(), 'جرأت': set()})
    questions = truth_questions if qtype == 'حقیقت' else dare_challenges
    available = list(set(questions) - used[qtype])
    if not available:
        return None  # همه سوال‌ها تکراری شدن!
    q = random.choice(available)
    used[qtype].add(q)
    game['used_questions'][user_id] = used
    return q



async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    game = get_game(chat_id)

    if user_id != game['current_user']:
        await query.answer("نوبت شما نیست!", show_alert=False)
        return

    game['used_change'][user_id] = 0

    qtype = query.data
    game['current_question_type'] = qtype
    q = get_unique_question(user_id, qtype, game)

    if q is None:
        await query.answer("سؤال جدیدی برای شما باقی نمانده", show_alert=True)
        return  #  اینجا باید return داخل if باشه

    keyboard = [
        [InlineKeyboardButton("تغییر سوال", callback_data='تغییر_سوال')],
        [InlineKeyboardButton("جواب دادم", callback_data='جواب_دادم')]
    ]

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

    used = game['used_change'].get(user_id, 0)
    if used >= game.get('change_limit', DEFAULT_CHANGE_LIMIT):
        await query.answer(f"شما فقط {game.get('change_limit', DEFAULT_CHANGE_LIMIT)} بار می‌تونید سوال رو تغییر بدید.", show_alert=False)
        return

    qtype = game['current_question_type']
    q = get_unique_question(user_id, qtype, game)

    if q is None:
        await query.answer("سؤال جدیدی برای شما باقی نمانده", show_alert=True)
        return  #  اینجا باید return داخل if باشه

    game['used_change'][user_id] = used + 1

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

    elif query.data == 'set_تغییر_تعداد':
        await query.message.edit_text("لطفاً تعداد دفعات مجاز تغییر سوال را (عدد صحیح) ارسال کنید:")
        user_states[user_id] = {"setting_change_limit": True}
        await query.answer()

    elif query.data == 'set_پاک_کردن_بازی':
        games.pop(chat_id, None)
        await query.message.edit_text("بازی پاک شد. می‌توانید بازی جدید بسازید.")
        await query.answer()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id)
    if not state:
        return

    # حالت افزودن سوال جدید
    if state.get("state") == "awaiting_question":
        q_type = state["question_type"]  # 'dare' یا 'truth'

        # ارسال برای ادمین جهت تأیید
        keyboard = [
            [
                InlineKeyboardButton(" تأیید", callback_data=f"confirm_{q_type}_{user_id}"),
                InlineKeyboardButton(" لغو", callback_data=f"reject_{user_id}"),
                InlineKeyboardButton(" ویرایش", callback_data=f"edit_{q_type}_{user_id}")
            ]
        ]
        await context.bot.send_message(
            ADMIN_ID,
            text=f"سوال جدید برای {'جرأت' if q_type == 'dare' else 'حقیقت'}:\n\n{text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        await update.message.reply_text("سوالت برای بررسی به ادمین ارسال شد.")
        user_states.pop(user_id)
        return
     # حالت ویرایش توسط ادمین
    elif state.get("edit_mode"):
        q_type = state["q_type"]
        original_text = state["original_text"]
        target_user = state["target_user"]

        filename = "dare.txt" if q_type == "dare" else "truth.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(text.strip() + "\n")

        await update.message.reply_text(f" سوال ویرایش و ذخیره شد:\n\n{text}")
        await context.bot.send_message(target_user, " سوالت توسط ادمین ویرایش و ذخیره شد.")
        user_states.pop(user_id)

async def review_question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    parts = data.split("_")
    action = parts[0]
    q_type = parts[1] if action != "reject" else None
    target_user = int(parts[-1])
    message_text = query.message.text.split("\n\n", 1)[1]  # متن سوال

    if query.from_user.id != ADMIN_ID:
        await query.answer("شما اجازه انجام این کار را ندارید.", show_alert=True)
        return

    if action == "confirm":
        filename = "dare.txt" if q_type == "dare" else "truth.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(message_text.strip() + "\n")
        await query.edit_message_text(f" سوال ذخیره شد:\n\n{message_text}")
        await context.bot.send_message(target_user, " سوالت تأیید و ذخیره شد. مرسی!")

    elif action == "reject":
        await query.edit_message_text(" سوال رد شد.")
        await context.bot.send_message(target_user, " سوالت رد شد.")

    elif action == "edit":
        user_states[ADMIN_ID] = {
            "edit_mode": True,
            "q_type": q_type,
            "original_text": message_text,
            "target_user": target_user,
            "message_id": query.message.message_id
        }
        await query.message.reply_text(" لطفاً سوال ویرایش‌شده را بفرست:")
        await query.answer()





async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    keyboard = [
        [InlineKeyboardButton(" اضافه به جرأت", callback_data="add_dare")],
        [InlineKeyboardButton(" اضافه به حقیقت", callback_data="add_truth")]
    ]
    await update.message.reply_text("می‌خوای سوالت رو به کدوم بخش اضافه کنی؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def add_question_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    q_type = query.data.split("_")[1]  # dare یا truth
    user_states[user_id] = {"state": "awaiting_question", "question_type": q_type}
    await query.message.edit_text(f"لطفاً سوال جدید برای {'جرأت' if q_type == 'dare' else 'حقیقت'} را ارسال کن:")
    await query.answer()







#PROXY_URL = 'socks5://127.0.0.1:10808'
# ثبت هندلرها
def main():
    #req = HTTPXRequest(proxy_url=PROXY_URL)
    #app = ApplicationBuilder().token(TOKEN).request(req).build()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_game_message))
    app.add_handler(CallbackQueryHandler(new_game, pattern="^بازی_جدید$"))
    app.add_handler(CallbackQueryHandler(join, pattern="^عضویت$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^شروع_بازی$"))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern="^(جرأت|حقیقت)$"))
    app.add_handler(CallbackQueryHandler(change_question, pattern="^تغییر_سوال$"))
    app.add_handler(CallbackQueryHandler(answered, pattern="^جواب_دادم$"))

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    app.add_handler(CallbackQueryHandler(game_settings_buttons, pattern="^(تعیین_تعداد|پایان_بازی)$"))
    app.add_handler(CallbackQueryHandler(review_question_handler, pattern="^(confirm|reject|edit)_(dare|truth)?_?\d+$"))

    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CallbackQueryHandler(add_question_choice, pattern="^add_(dare|truth)$"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.run_polling()

if __name__ == '__main__':
    main()
