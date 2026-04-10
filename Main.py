import asyncio
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3
import random

# ========== CONFIGURATION ==========
TOKEN = "8788496160:AAGL-BLICNOhi2bCjdSvMQi-Rvix7HxLz0M"  # Your bot token
ADMIN_IDS = [8518408753]  # Your chat ID - Admin

# Force Subscribe Channels (users must join both to use bot)
REQUIRED_CHANNELS = [
    {"username": "@WahidModeX", "url": "https://t.me/WahidModeX"},
    {"username": "@ProTech43", "url": "https://t.me/ProTech43"}
]

# Bot settings
BOT_NAME = "Afg Plus Pay"
MIN_WITHDRAWAL = 10.00
WITHDRAWAL_FEE = 0.50
EARN_PER_AD = 0.20
MAX_ADS_PER_DAY = 10
REFERRAL_BONUS = 0.50
# ====================================

# Database setup
conn = sqlite3.connect('afg_plus_pay.db', check_same_thread=False)
cursor = conn.cursor()

# Users table
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    balance REAL DEFAULT 0,
    total_watched INTEGER DEFAULT 0,
    total_earned REAL DEFAULT 0,
    today_watched INTEGER DEFAULT 0,
    last_watch_date TEXT,
    invited_by INTEGER DEFAULT 0,
    join_date TEXT
)
''')

# Invites table
cursor.execute('''
CREATE TABLE IF NOT EXISTS invites (
    user_id INTEGER PRIMARY KEY,
    invite_code TEXT UNIQUE,
    total_invites INTEGER DEFAULT 0,
    total_bonus REAL DEFAULT 0
)
''')

# Withdrawals table
cursor.execute('''
CREATE TABLE IF NOT EXISTS withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    wallet_address TEXT,
    status TEXT DEFAULT 'pending',
    request_date TEXT
)
''')

# Ad watches log
cursor.execute('''
CREATE TABLE IF NOT EXISTS ad_watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    watch_date TEXT,
    earned REAL
)
''')

conn.commit()

# ========== DATABASE FUNCTIONS ==========
def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def create_user(user_id, username, first_name, invited_by=0):
    today = str(date.today())
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, join_date, invited_by)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, today, invited_by))
    
    # Give referral bonus
    if invited_by > 0 and invited_by != user_id:
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (invited_by,))
        inviter = cursor.fetchone()
        if inviter:
            new_balance = inviter[0] + REFERRAL_BONUS
            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, invited_by))
            
            cursor.execute('''
                INSERT OR REPLACE INTO invites (user_id, total_invites, total_bonus)
                VALUES (?, COALESCE((SELECT total_invites FROM invites WHERE user_id = ?), 0) + 1,
                        COALESCE((SELECT total_bonus FROM invites WHERE user_id = ?), 0) + ?)
            ''', (invited_by, invited_by, invited_by, REFERRAL_BONUS))
    
    conn.commit()

def reset_daily_watch():
    today = str(date.today())
    cursor.execute('UPDATE users SET today_watched = 0 WHERE last_watch_date != ?', (today,))
    cursor.execute('UPDATE users SET last_watch_date = ? WHERE last_watch_date IS NULL', (today,))
    conn.commit()

# ========== FORCE SUBSCRIBE CHECK ==========
async def check_subscription(user_id, context):
    not_joined = []
    for channel in REQUIRED_CHANNELS:
        try:
            chat_member = await context.bot.get_chat_member(channel["username"], user_id)
            if chat_member.status in ['left', 'kicked']:
                not_joined.append(channel)
        except:
            not_joined.append(channel)
    return not_joined

async def force_subscribe_message(update, context, not_joined):
    keyboard = []
    for channel in not_joined:
        keyboard.append([InlineKeyboardButton(f"📢 Join {channel['username']}", url=channel['url'])])
    
    keyboard.append([InlineKeyboardButton("✅ I've Joined", callback_data='check_subscription')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = f"""
⚠️ *Join Required!* ⚠️

Please join the following channels to use *{BOT_NAME}*:

"""
    for channel in not_joined:
        message_text += f"• {channel['username']}\n"
    
    message_text += "\nAfter joining, click the '✅ I've Joined' button to continue."
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

# ========== MAIN MENU ==========
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, user_data):
    today_watched = user_data[5] if user_data else 0
    
    keyboard = [
        [InlineKeyboardButton("🎬 Watch Ad (+$0.20)", callback_data='watch_ad')],
        [InlineKeyboardButton("💰 My Balance", callback_data='balance')],
        [InlineKeyboardButton("👥 Invite Friends", callback_data='invite')],
        [InlineKeyboardButton("📤 Withdraw", callback_data='withdraw')],
        [InlineKeyboardButton("📊 Statistics", callback_data='stats')],
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
💰 *{BOT_NAME}* 💰

Welcome back *{user_data[1] or 'User'}*! 🤝

🎬 *How to Earn:*
• Each ad: *+${EARN_PER_AD}*
• Daily limit: *{MAX_ADS_PER_DAY} ads*
• Referral bonus: *+${REFERRAL_BONUS}*

📊 *Today's Stats:*
• Watched today: *{today_watched}/{MAX_ADS_PER_DAY}*
• Current balance: *${user_data[2]:.2f}*

💡 Press buttons below to earn money!
"""
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# ========== COMMAND HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    # Check subscription
    not_joined = await check_subscription(user.id, context)
    if not_joined:
        await force_subscribe_message(update, context, not_joined)
        return
    
    # Check referral code
    invited_by = 0
    if args and args[0].startswith('ref_'):
        try:
            invited_by = int(args[0].split('_')[1])
            if invited_by == user.id:
                invited_by = 0
        except:
            pass
    
    create_user(user.id, user.username, user.first_name, invited_by)
    reset_daily_watch()
    
    user_data = get_user(user.id)
    await main_menu(update, context, user.id, user_data)

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    not_joined = await check_subscription(user_id, context)
    
    if not_joined:
        await force_subscribe_message(update, context, not_joined)
    else:
        user_data = get_user(user_id)
        if not user_data:
            create_user(user_id, query.from_user.username, query.from_user.first_name)
            user_data = get_user(user_id)
        await main_menu(update, context, user_id, user_data)

async def watch_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎬 Ad is loading...")
    
    user_id = query.from_user.id
    
    # Check subscription first
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        await force_subscribe_message(update, context, not_joined)
        return
    
    user_data = get_user(user_id)
    
    if not user_data:
        create_user(user_id, query.from_user.username, query.from_user.first_name)
        user_data = get_user(user_id)
    
    today = str(date.today())
    today_watched = user_data[5] if user_data[5] else 0
    last_date = user_data[6] or ""
    
    if last_date != today:
        today_watched = 0
        cursor.execute('UPDATE users SET today_watched = 0, last_watch_date = ? WHERE user_id = ?', (today, user_id))
        conn.commit()
    
    if today_watched >= MAX_ADS_PER_DAY:
        await query.edit_message_text(
            f"⛔ *Daily Limit Reached!*\n\n"
            f"You've watched {today_watched}/{MAX_ADS_PER_DAY} ads today.\n"
            f"Come back tomorrow! 🌙\n\n"
            f"💰 Total earned: *${user_data[4]:.2f}*",
            parse_mode='Markdown'
        )
        return
    
    # Simulate ad watching
    ad_message = await query.edit_message_text(
        "🎬 *Watching Ad...*\n\n"
        "⏳ Please wait 3 seconds\n"
        f"💰 You will earn *+${EARN_PER_AD}*!",
        parse_mode='Markdown'
    )
    
    await asyncio.sleep(3)
    
    # Add earnings
    new_balance = user_data[2] + EARN_PER_AD
    new_total_watched = user_data[3] + 1
    new_total_earned = user_data[4] + EARN_PER_AD
    new_today_watched = today_watched + 1
    
    cursor.execute('''
        UPDATE users SET 
            balance = ?,
            total_watched = ?,
            total_earned = ?,
            today_watched = ?,
            last_watch_date = ?
        WHERE user_id = ?
    ''', (new_balance, new_total_watched, new_total_earned, new_today_watched, today, user_id))
    
    cursor.execute('INSERT INTO ad_watches (user_id, watch_date, earned) VALUES (?, ?, ?)',
                   (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), EARN_PER_AD))
    conn.commit()
    
    keyboard = [[InlineKeyboardButton("🎬 Watch Another Ad", callback_data='watch_ad')],
                [InlineKeyboardButton("💰 Check Balance", callback_data='balance')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await ad_message.edit_text(
        f"✅ *Ad Completed Successfully!*\n\n"
        f"🎉 You earned: *+${EARN_PER_AD}*\n"
        f"💰 New Balance: *${new_balance:.2f}*\n"
        f"📊 Today: {new_today_watched}/{MAX_ADS_PER_DAY} ads\n\n"
        f"Watch another ad to earn more! 🚀",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        await force_subscribe_message(update, context, not_joined)
        return
    
    user_data = get_user(user_id)
    
    if not user_data:
        await query.edit_message_text("❌ Error! Please use /start")
        return
    
    invite_data = cursor.execute('SELECT total_invites, total_bonus FROM invites WHERE user_id = ?', (user_id,)).fetchone()
    total_invites = invite_data[0] if invite_data else 0
    bonus_earned = invite_data[1] if invite_data else 0
    
    keyboard = [[InlineKeyboardButton("🎬 Watch Ad", callback_data='watch_ad')],
                [InlineKeyboardButton("📤 Withdraw", callback_data='withdraw')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"💰 *Your Balance*\n\n"
        f"💵 *Current Balance:* `${user_data[2]:.2f}`\n"
        f"📊 *Total Ads Watched:* {user_data[3]}\n"
        f"🏆 *Total Earned:* `${user_data[4]:.2f}`\n"
        f"👥 *Friends Invited:* {total_invites}\n"
        f"🎁 *Referral Bonus:* `${bonus_earned:.2f}`\n\n"
        f"⚠️ *Minimum Withdrawal:* `${MIN_WITHDRAWAL}`\n"
        f"💳 *Withdrawal Fee:* `${WITHDRAWAL_FEE}`",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def invite_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        await force_subscribe_message(update, context, not_joined)
        return
    
    bot_username = (await context.bot.get_me()).username
    invite_code = f"ref_{user_id}"
    
    cursor.execute('INSERT OR IGNORE INTO invites (user_id, invite_code) VALUES (?, ?)', (user_id, invite_code))
    conn.commit()
    
    invite_data = cursor.execute('SELECT total_invites, total_bonus FROM invites WHERE user_id = ?', (user_id,)).fetchone()
    total_invites = invite_data[0] if invite_data else 0
    bonus_earned = invite_data[1] if invite_data else 0
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👥 *Invite Friends & Earn ${REFERRAL_BONUS} Each!*\n\n"
        f"🎁 *Bonus per friend:* `+${REFERRAL_BONUS}`\n"
        f"🔗 *Your Invite Link:*\n"
        f"`https://t.me/{bot_username}?start={invite_code}`\n\n"
        f"📊 *Your Stats*\n"
        f"• Invited: {total_invites}\n"
        f"• Bonus Earned: `${bonus_earned:.2f}`\n\n"
        f"💡 Share this link with your friends!\n"
        f"Everyone who joins gets `${EARN_PER_AD}` per ad!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        await force_subscribe_message(update, context, not_joined)
        return
    
    user_data = get_user(user_id)
    
    if not user_data or user_data[2] < MIN_WITHDRAWAL:
        await query.edit_message_text(
            f"❌ *Withdrawal Not Possible!*\n\n"
            f"Your balance: `${user_data[2]:.2f}`\n"
            f"Minimum required: `${MIN_WITHDRAWAL}`\n\n"
            f"Watch more ads to reach the minimum! 🎬",
            parse_mode='Markdown'
        )
        return
    
    amount = user_data[2] - WITHDRAWAL_FEE
    withdrawal_id = random.randint(1000, 9999)
    
    cursor.execute('''
        INSERT INTO withdrawals (user_id, amount, wallet_address, request_date, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (user_id, amount, f"USDT_{user_id}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    cursor.execute('UPDATE users SET balance = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    
    # Notify admin
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🆕 *New Withdrawal Request*\n\n"
                f"👤 User: @{query.from_user.username or 'N/A'}\n"
                f"💰 Amount: `${amount:.2f}`\n"
                f"🆔 ID: #{withdrawal_id}\n"
                f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                parse_mode='Markdown'
            )
        except:
            pass
    
    await query.edit_message_text(
        f"✅ *Withdrawal Request Submitted!*\n\n"
        f"💰 Amount: *${amount:.2f}*\n"
        f"🆔 Request ID: #{withdrawal_id}\n\n"
        f"⏳ Your request will be processed within 24-48 hours.\n"
        f"Thank you for using *{BOT_NAME}!* 🙏",
        parse_mode='Markdown'
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        await force_subscribe_message(update, context, not_joined)
        return
    
    user_data = get_user(user_id)
    
    total_users = cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_ads = cursor.execute('SELECT SUM(total_watched) FROM users').fetchone()[0] or 0
    total_paid = cursor.execute('SELECT SUM(total_earned) FROM users').fetchone()[0] or 0
    pending_withdrawals = cursor.execute('SELECT COUNT(*) FROM withdrawals WHERE status = "pending"').fetchone()[0]
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📊 *Global Statistics*\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🎬 Total Ads Watched: {total_ads}\n"
        f"💰 Total Paid Out: `${total_paid:.2f}`\n"
        f"⏳ Pending Withdrawals: {pending_withdrawals}\n\n"
        f"📈 *Your Stats*\n"
        f"• Ads Watched: {user_data[3]}\n"
        f"• Total Earned: `${user_data[4]:.2f}`",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("❌ You are not an admin!")
        return
    
    total_users = cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_ads = cursor.execute('SELECT SUM(total_watched) FROM users').fetchone()[0] or 0
    total_paid = cursor.execute('SELECT SUM(total_earned) FROM users').fetchone()[0] or 0
    pending_withdrawals = cursor.execute('SELECT COUNT(*) FROM withdrawals WHERE status = "pending"').fetchone()[0]
    
    cursor.execute('SELECT user_id, amount, request_date FROM withdrawals WHERE status = "pending" LIMIT 10')
    pending = cursor.fetchall()
    
    pending_text = ""
    for p in pending:
        pending_text += f"• User: `{p[0]}` | Amount: `${p[1]:.2f}` | Date: {p[2]}\n"
    
    if not pending_text:
        pending_text = "No pending withdrawals"
    
    keyboard = [
        [InlineKeyboardButton("📊 Refresh", callback_data='admin')],
        [InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👑 *Admin Panel - {BOT_NAME}*\n\n"
        f"📈 *Statistics*\n"
        f"👥 Total Users: {total_users}\n"
        f"🎬 Total Ads: {total_ads}\n"
        f"💰 Total Paid: `${total_paid:.2f}`\n"
        f"⏳ Pending Withdrawals: {pending_withdrawals}\n\n"
        f"📋 *Recent Withdrawals:*\n{pending_text}\n\n"
        f"💡 To process withdrawals, check your database!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    if not user_data:
        create_user(user_id, query.from_user.username, query.from_user.first_name)
        user_data = get_user(user_id)
    
    await main_menu(update, context, user_id, user_data)

# ========== MAIN FUNCTION ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(check_subscription_callback, pattern='check_subscription'))
    app.add_handler(CallbackQueryHandler(watch_ad, pattern='watch_ad'))
    app.add_handler(CallbackQueryHandler(show_balance, pattern='balance'))
    app.add_handler(CallbackQueryHandler(invite_friends, pattern='invite'))
    app.add_handler(CallbackQueryHandler(withdraw, pattern='withdraw'))
    app.add_handler(CallbackQueryHandler(show_stats, pattern='stats'))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern='admin'))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern='back_to_main'))
    
    print(f"✅ {BOT_NAME} Bot is running!")
    print(f"👑 Admin ID: {ADMIN_IDS[0]}")
    print(f"📢 Force Subscribe Channels: {[c['username'] for c in REQUIRED_CHANNELS]}")
    
    app.run_polling()

if __name__ == "__main__":
    main()
