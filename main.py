import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)


TOKEN = "7611408660:AAH9fAiPglhU4ldLCLhwFt4_3qvTiFZhTbw"

logging.basicConfig(level=logging.INFO)

games = {}  # group_id -> game data
user_states = {}

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
            'used_change': {},
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

    # اگر بازی قبلی وجود داشت، پاکش کن
    if chat_id in games:
        games.pop(chat_id)

    # بازی جدید بساز
    games[chat_id] = {
        'creator': user_id,
        'members': [user_id],
        'state': 'waiting',
        'used_change': {},
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
    game['used_change'][user_id] = False

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

    if user_id != game['current_user']:
        await query.answer("نوبت شما نیست!", show_alert=False)
        return

    game['used_change'][user_id] = False

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

    await query.message.edit_text(f"{query.message.text_html}\n\nسوال: {q}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    await query.answer()

async def change_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    game = get_game(chat_id)

    # فقط کسی که نوبتش هست اجازه دارد
    if user_id != game.get('current_user'):
        await query.answer("فقط کسی که نوبتش هست می‌تونه سوال رو عوض کنه.", show_alert=False)
        return

    if game['used_change'].get(user_id, True):
        await query.answer("شما قبلاً سوال رو عوض کردید!", show_alert=False)
        return

    if game['current_question_type'] == 'حقیقت':
        q = random.choice(truth_questions)
    else:
        q = random.choice(dare_challenges)

    game['used_change'][user_id] = True
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


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("اضافه کردن به حقیقت", callback_data='اضافه_حقیقت')],
        [InlineKeyboardButton("اضافه کردن به جرأت", callback_data='اضافه_جرأت')]
    ]
    await update.message.reply_text("کدام دسته سوال را می‌خواهید اضافه کنید؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def add_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == 'اضافه_حقیقت':
        user_states[user_id] = {"adding_to": "truth"}
        await query.message.edit_text("لطفاً سوال حقیقت خود را ارسال کنید:")
    elif query.data == 'اضافه_جرأت':
        user_states[user_id] = {"adding_to": "dare"}
        await query.message.edit_text("لطفاً سوال جرأت خود را ارسال کنید:")
    await query.answer()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in user_states and user_states[user_id].get("adding_to") in ["truth", "dare"]:
        category = user_states[user_id]["adding_to"]
        text = update.message.text.strip()
        filename = "truth.txt" if category == "truth" else "dare.txt"

        with open(filename, "a", encoding="utf-8") as f:
            f.write(text + "\n")

        global truth_questions, dare_challenges
        truth_questions, dare_challenges = load_questions()

        await update.message.reply_text(f"سوال شما به دسته { 'حقیقت' if category=='truth' else 'جرأت' } اضافه شد.")
        user_states.pop(user_id)


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
    await update.message.reply_text("آیا مطمئنی می‌خوای بازی رو به پایان برسونی؟", reply_markup=InlineKeyboardMarkup(keyboard))


async def confirm_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    game = get_game(chat_id)

    if user_id != game['creator']:
        await query.answer("فقط سازنده بازی می‌تونه پایان بازی رو تأیید کنه.", show_alert=True)
        return

    games.pop(chat_id, None)
    await query.message.edit_text("بازی با موفقیت پایان یافت.")


    
async def cancel_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("پایان بازی لغو شد.")
    await query.message.edit_text("پایان بازی لغو شد.")



async def clear_cache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games:
        games.pop(chat_id)
        await update.message.reply_text("حافظه بازی‌های این گروه پاک شد و می‌توانید بازی جدید بسازید.")
    else:
        await update.message.reply_text("فعلاً بازی‌ای در این گروه فعال نیست که پاک شود.")



if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start_game_message))
    app.add_handler(CallbackQueryHandler(new_game, pattern='^بازی_جدید$'))
    app.add_handler(CallbackQueryHandler(join, pattern='^عضویت$'))
    app.add_handler(CallbackQueryHandler(start, pattern='^شروع_بازی$'))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern='^(حقیقت|جرأت)$'))
    app.add_handler(CallbackQueryHandler(change_question, pattern='^تغییر_سوال$'))
    app.add_handler(CallbackQueryHandler(answered, pattern='^جواب_دادم$'))

    app.add_handler(CommandHandler('add', add_command))
    app.add_handler(CallbackQueryHandler(add_button, pattern='^اضافه_'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_handler(CallbackQueryHandler(confirm_end, pattern='^تأیید_پایان$'))
    app.add_handler(CallbackQueryHandler(cancel_end, pattern='^لغو_پایان$'))

    app.add_handler(CommandHandler('finish', finish_command))
    app.add_handler(CommandHandler('clear', clear_cache))

    app.run_polling()
