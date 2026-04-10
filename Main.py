import asyncio
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3
import random

# ========== تنظیمات ==========
TOKEN = "8788496160:AAGL-BLICNOhi2bCjdSvMQi-Rvix7HxLz0M"  # ستاسو توکن
ADMIN_IDS = [8518408753]  # ستاسو چت آیدی

# دوه چینلونه (کاروونکي باید دلته ګډون وکړي)
REQUIRED_CHANNELS = [
    {"username": "@WahidModeX", "url": "https://t.me/WahidModeX"},
    {"username": "@ProTech43", "url": "https://t.me/ProTech43"}
]

# د بوټ تنظیمات
BOT_NAME = "Afg Plus Pay"
MIN_WITHDRAWAL = 10.00
WITHDRAWAL_FEE = 0.50
EARN_PER_AD = 0.20
MAX_ADS_PER_DAY = 10
REFERRAL_BONUS = 0.50
# ====================================

# ډیټابیس
conn = sqlite3.connect('afg_plus_pay.db', check_same_thread=False)
cursor = conn.cursor()

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

cursor.execute('''
CREATE TABLE IF NOT EXISTS invites (
    user_id INTEGER PRIMARY KEY,
    invite_code TEXT UNIQUE,
    total_invites INTEGER DEFAULT 0,
    total_bonus REAL DEFAULT 0
)
''')

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

cursor.execute('''
CREATE TABLE IF NOT EXISTS ad_watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    watch_date TEXT,
    earned REAL
)
''')

conn.commit()

# ========== د ډیټابیس دندې ==========
def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def create_user(user_id, username, first_name, invited_by=0):
    today = str(date.today())
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, join_date, invited_by)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, today, invited_by))
    
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

# ========== د چینل ګډون چک ==========
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

# ========== لومړی پیغام (د Open App تڼۍ سره) ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    # د ریفرل چک
    invited_by = 0
    if args and args[0].startswith('ref_'):
        try:
            invited_by = int(args[0].split('_')[1])
            if invited_by == user.id:
                invited_by = 0
        except:
            pass
    
    create_user(user.id, user.username, user.first_name, invited_by)
    
    # د Open App تڼۍ سره کیبورډ
    keyboard = [
        [InlineKeyboardButton("🚀 Open App", callback_data='open_app')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
💰 *{BOT_NAME}* 💰

Welcome *{user.first_name}!* 🤝

Click the button below to open the app and start earning money!

🎬 *Earn $0.20 per ad*
👥 *Get $0.50 per referral*
📊 *Watch 10 ads daily*

👇 *Tap Open App to continue* 👇
"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# ========== د بشپړې پاڼې ښودل (لکه تصویر کې) ==========
async def open_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # د چینل ګډون چک
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        keyboard = []
        for channel in not_joined:
            keyboard.append([InlineKeyboardButton(f"📢 Join {channel['username']}", url=channel['url'])])
        keyboard.append([InlineKeyboardButton("✅ I've Joined", callback_data='check_sub')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚠️ *Please join our channels first!* ⚠️\n\nAfter joining, click the button below.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    user_data = get_user(user_id)
    if not user_data:
        create_user(user_id, query.from_user.username, query.from_user.first_name)
        user_data = get_user(user_id)
    
    balance = user_data[2] if user_data else 0
    total_watched = user_data[3] if user_data else 0
    total_earned = user_data[4] if user_data else 0
    today_watched = user_data[5] if user_data else 0
    
    # د بشپړې پاڼې کیبورډ (لکه تصویر کې)
    keyboard = [
        [InlineKeyboardButton("🎬 Watch Ad", callback_data='watch_ad')],
        [InlineKeyboardButton("💰 My Balance", callback_data='balance')],
        [InlineKeyboardButton("👥 Invite Friends", callback_data='invite')],
        [InlineKeyboardButton("📤 Withdraw", callback_data='withdraw')],
        [InlineKeyboardButton("📊 Statistics", callback_data='stats')],
        [InlineKeyboardButton("🌐 Language", callback_data='language')],
        [InlineKeyboardButton("🛎️ Customer Support", callback_data='support')],
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # د تصویر سره سم متن
    main_text = f"""
💰 *{BOT_NAME} - Earning* 💰

📊 *TOTALS*
• *TOTAL BALANCE*  
  *${balance:.2f}*  
  Available to withdraw

---

🎬 *Ads & Earn*
Complete and watch a short video ads and earn *${EARN_PER_AD}*

---

🎥 *Watch Ad*
Complete video to earn instantly
+${EARN_PER_AD}
{today_watched} / {MAX_ADS_PER_DAY} today

---

✅ *Ready to earn*
• *TOTAL WATCHED*  
  {total_watched} ads
• *TOTAL EARNED*  
  *${total_earned:.2f}*
"""
    
    await query.edit_message_text(main_text, reply_markup=reply_markup, parse_mode='Markdown')

# ========== د ګډون چک کال بیک ==========
async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    not_joined = await check_subscription(user_id, context)
    
    if not_joined:
        keyboard = []
        for channel in not_joined:
            keyboard.append([InlineKeyboardButton(f"📢 Join {channel['username']}", url=channel['url'])])
        keyboard.append([InlineKeyboardButton("✅ I've Joined", callback_data='check_sub')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚠️ *Please join our channels first!* ⚠️\n\nAfter joining, click the button below.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await open_app(update, context)

# ========== د اعلان لیدل ==========
async def watch_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎬 Ad is loading...")
    
    user_id = query.from_user.id
    
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        await open_app(update, context)
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
    
    # د اعلان لیدل
    ad_message = await query.edit_message_text(
        "🎬 *Watching Ad...*\n\n"
        "⏳ Please wait 3 seconds\n"
        f"💰 You will earn *+${EARN_PER_AD}*!",
        parse_mode='Markdown'
    )
    
    await asyncio.sleep(3)
    
    # پیسې اضافه کول
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
    
    await ad_message.edit_text(
        f"✅ *Ad Completed!*\n\n"
        f"🎉 You earned: *+${EARN_PER_AD}*\n"
        f"💰 New Balance: *${new_balance:.2f}*\n"
        f"📊 Today: {new_today_watched}/{MAX_ADS_PER_DAY} ads\n\n"
        f"🔙 Click back to continue earning!",
        parse_mode='Markdown'
    )
    
    await asyncio.sleep(2)
    await open_app(update, context)

# ========== بیلانس ښودل ==========
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        await open_app(update, context)
        return
    
    user_data = get_user(user_id)
    
    if not user_data:
        await query.edit_message_text("❌ Error! Please use /start")
        return
    
    invite_data = cursor.execute('SELECT total_invites, total_bonus FROM invites WHERE user_id = ?', (user_id,)).fetchone()
    total_invites = invite_data[0] if invite_data else 0
    bonus_earned = invite_data[1] if invite_data else 0
    
    keyboard = [[InlineKeyboardButton("🔙 Back to App", callback_data='open_app')]]
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

# ========== ملګري رابلل ==========
async def invite_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        await open_app(update, context)
        return
    
    bot_username = (await context.bot.get_me()).username
    invite_code = f"ref_{user_id}"
    
    cursor.execute('INSERT OR IGNORE INTO invites (user_id, invite_code) VALUES (?, ?)', (user_id, invite_code))
    conn.commit()
    
    invite_data = cursor.execute('SELECT total_invites, total_bonus FROM invites WHERE user_id = ?', (user_id,)).fetchone()
    total_invites = invite_data[0] if invite_data else 0
    bonus_earned = invite_data[1] if invite_data else 0
    
    keyboard = [[InlineKeyboardButton("🔙 Back to App", callback_data='open_app')],
                [InlineKeyboardButton("📋 Copy Link", callback_data=f'copy_{invite_code}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👥 *Invite Friends & Earn ${REFERRAL_BONUS} Each!*\n\n"
        f"🎁 *Bonus per friend:* `+${REFERRAL_BONUS}`\n"
        f"🔗 *Your Invite Link:*\n"
        f"`https://t.me/{bot_username}?start={invite_code}`\n\n"
        f"📊 *Your Stats*\n"
        f"• Invited: {total_invites}\n"
        f"• Bonus Earned: `${bonus_earned:.2f}`\n\n"
        f"💡 Share this link with your friends!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ========== پیسې ایستل ==========
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        await open_app(update, context)
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
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🆕 *New Withdrawal Request*\n\n"
                f"👤 User: @{query.from_user.username or 'N/A'}\n"
                f"💰 Amount: `${amount:.2f}`\n"
                f"🆔 ID: #{withdrawal_id}",
                parse_mode='Markdown'
            )
        except:
            pass
    
    keyboard = [[InlineKeyboardButton("🔙 Back to App", callback_data='open_app')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✅ *Withdrawal Request Submitted!*\n\n"
        f"💰 Amount: *${amount:.2f}*\n"
        f"🆔 Request ID: #{withdrawal_id}\n\n"
        f"⏳ Your request will be processed within 24-48 hours.\n"
        f"Thank you for using *{BOT_NAME}!* 🙏",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ========== احصایه ==========
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    not_joined = await check_subscription(user_id, context)
    if not_joined:
        await open_app(update, context)
        return
    
    user_data = get_user(user_id)
    
    total_users = cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_ads = cursor.execute('SELECT SUM(total_watched) FROM users').fetchone()[0] or 0
    total_paid = cursor.execute('SELECT SUM(total_earned) FROM users').fetchone()[0] or 0
    
    keyboard = [[InlineKeyboardButton("🔙 Back to App", callback_data='open_app')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📊 *Global Statistics*\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🎬 Total Ads Watched: {total_ads}\n"
        f"💰 Total Paid Out: `${total_paid:.2f}`\n\n"
        f"📈 *Your Stats*\n"
        f"• Ads Watched: {user_data[3]}\n"
        f"• Total Earned: `${user_data[4]:.2f}`",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ========== ژبه ==========
async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🇺🇸 English", callback_data='lang_en')],
        [InlineKeyboardButton("🇵🇰 پښتو", callback_data='lang_ps')],
        [InlineKeyboardButton("🇦🇫 دری", callback_data='lang_dr')],
        [InlineKeyboardButton("🔙 Back", callback_data='open_app')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🌐 *Select Language / ژبه غوره کړئ*\n\n"
        "Choose your preferred language:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ========== ملاتړ ==========
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("🔙 Back to App", callback_data='open_app')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🛎️ *Customer Support*\n\n"
        f"📧 Email: support@afgpluspay.com\n"
        f"📱 Telegram: @Kingwahidafg\n\n"
        f"⏳ Response time: 24 hours\n\n"
        f"*Common Issues:*\n"
        f"• Withdrawal takes 24-48 hours\n"
        f"• Daily reset at 00:00 UTC\n"
        f"• Minimum withdrawal: ${MIN_WITHDRAWAL}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ========== اډمین پینل ==========
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
        pending_text += f"• User: `{p[0]}` | Amount: `${p[1]:.2f}`\n"
    
    if not pending_text:
        pending_text = "No pending withdrawals"
    
    keyboard = [
        [InlineKeyboardButton("📊 Refresh", callback_data='admin')],
        [InlineKeyboardButton("🔙 Back to App", callback_data='open_app')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👑 *Admin Panel - {BOT_NAME}*\n\n"
        f"📈 *Statistics*\n"
        f"👥 Total Users: {total_users}\n"
        f"🎬 Total Ads: {total_ads}\n"
        f"💰 Total Paid: `${total_paid:.2f}`\n"
        f"⏳ Pending Withdrawals: {pending_withdrawals}\n\n"
        f"📋 *Pending Withdrawals:*\n{pending_text}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ========== مین فنکشن ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(open_app, pattern='open_app'))
    app.add_handler(CallbackQueryHandler(check_subscription_callback, pattern='check_sub'))
    app.add_handler(CallbackQueryHandler(watch_ad, pattern='watch_ad'))
    app.add_handler(CallbackQueryHandler(show_balance, pattern='balance'))
    app.add_handler(CallbackQueryHandler(invite_friends, pattern='invite'))
    app.add_handler(CallbackQueryHandler(withdraw, pattern='withdraw'))
    app.add_handler(CallbackQueryHandler(show_stats, pattern='stats'))
    app.add_handler(CallbackQueryHandler(language, pattern='language'))
    app.add_handler(CallbackQueryHandler(support, pattern='support'))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern='admin'))
    
    print(f"✅ {BOT_NAME} Bot is running!")
    print(f"👑 Admin ID: {ADMIN_IDS[0]}")
    print(f"📢 Channels: @WahidModeX and @ProTech43")
    
    app.run_polling()

if __name__ == "__main__":
    main()
