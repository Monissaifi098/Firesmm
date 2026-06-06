import telebot
import sqlite3
import json
import os
import random
import string
import qrcode
import io
import requests
from datetime import datetime, date
from telebot import types

# ============================================================
#  CONFIGURATION
# ============================================================
BOT_TOKEN    = "8752034680:AAFClfX0NwflANlKrcD5WPANd-Hfipw088U"
ADMIN_ID     = 6270522295
UPI_ID       = "monisbhai@fam"
ADMIN_TG     = "@contactmonis"
WEB_APP_URL  = "https://firesm.netlify.app"
DAILY_REWARD = 0.08
MIN_WITHDRAW = 50.0
REFER_BONUS  = 5.0
MIN_PAYMENT  = 10.0
# ============================================================

bot = telebot.TeleBot(BOT_TOKEN)

# ─── DATABASE ─────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("fire_service.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id     INTEGER PRIMARY KEY,
        username    TEXT,
        full_name   TEXT,
        phone       TEXT DEFAULT '',
        balance     REAL DEFAULT 0,
        refer_code  TEXT UNIQUE,
        referred_by INTEGER DEFAULT NULL,
        last_reward TEXT DEFAULT NULL,
        joined_at   TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        platform    TEXT,
        service     TEXT,
        sub_service TEXT,
        link        TEXT,
        quantity    INTEGER,
        price       REAL,
        status      TEXT DEFAULT 'Pending',
        created_at  TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS payments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        amount      REAL,
        utr         TEXT DEFAULT '',
        screenshot  TEXT DEFAULT '',
        status      TEXT DEFAULT 'Pending',
        created_at  TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        amount      REAL,
        upi_id      TEXT,
        status      TEXT DEFAULT 'Pending',
        created_at  TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS services (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        platform    TEXT,
        category    TEXT,
        name        TEXT,
        min_qty     INTEGER,
        max_qty     INTEGER,
        rate_per_k  REAL,
        active      INTEGER DEFAULT 1
    )""")

    # Default services
    c.execute("SELECT COUNT(*) FROM services")
    if c.fetchone()[0] == 0:
        default_services = [
            ("Instagram","Followers","Real Followers",100,100000,10),
            ("Instagram","Followers","Premium Followers",100,50000,20),
            ("Instagram","Likes","Post Likes",50,500000,2),
            ("Instagram","Views","Reel / Video Views",100,2147483647,5),
            ("Instagram","Views","Story Views",100,1000000,3),
            ("Instagram","Comments","Random Comments",10,10000,30),
            ("YouTube","Views","Video Views",1000,10000000,8),
            ("YouTube","Subscribers","Channel Subscribers",100,500000,15),
            ("YouTube","Likes","Video Likes",100,500000,5),
            ("YouTube","Watch Hours","Watch Hours",100,10000,50),
            ("Telegram","Members","Channel Members",100,1000000,6),
            ("Telegram","Members","Group Members",100,500000,6),
            ("Telegram","Views","Post Views",100,5000000,1),
            ("Facebook","Likes","Page Likes",100,500000,8),
            ("Facebook","Followers","Profile Followers",100,500000,10),
            ("Facebook","Views","Video Views",1000,5000000,5),
            ("WhatsApp","Members","Group Members",50,100000,12),
        ]
        c.executemany(
            "INSERT INTO services (platform,category,name,min_qty,max_qty,rate_per_k) VALUES (?,?,?,?,?,?)",
            default_services
        )

    conn.commit()
    conn.close()

# ─── DB HELPERS ───────────────────────────────────────────────
def get_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(user_id, username, full_name, referred_by=None):
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    conn = get_db()
    conn.execute("""INSERT OR IGNORE INTO users
        (user_id,username,full_name,balance,refer_code,referred_by,joined_at)
        VALUES (?,?,?,0,?,?,?)""",
        (user_id, username, full_name, code, referred_by, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    if referred_by:
        add_balance(referred_by, REFER_BONUS)

def add_balance(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def deduct_balance(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def get_balance(user_id):
    user = get_user(user_id)
    return user['balance'] if user else 0

def get_all_users():
    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_orders():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_payments():
    conn = get_db()
    rows = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_withdrawals():
    conn = get_db()
    rows = conn.execute("SELECT * FROM withdrawals ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ─── QR GENERATOR ─────────────────────────────────────────────
def generate_upi_qr(amount, user_name="User"):
    upi_url = f"upi://pay?pa={UPI_ID}&pn=FireService&am={amount:.2f}&cu=INR&tn=Fire+Service+Wallet+{user_name}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio

# ─── KEYBOARDS ────────────────────────────────────────────────
def main_keyboard(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    web_btn = types.KeyboardButton(
        "🛍️ Social Media Service",
        web_app=types.WebAppInfo(url=f"{WEB_APP_URL}?uid={user_id}")
    )
    kb.add(web_btn)
    kb.add("💰 Add Fund", "🤝 Refer and Earn")
    kb.add("💸 Earn money", "🎁 Daily Reward")
    kb.add("💼 My Balance", "📋 My Orders")
    kb.add("📞 Contact Support")
    if user_id == ADMIN_ID:
        kb.add("⚙️ Admin Panel")
    return kb

def admin_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("👥 All Users", "📦 All Orders")
    kb.add("💳 Payments", "💸 Withdrawals")
    kb.add("📢 Broadcast", "🛠️ Manage Services")
    kb.add("📊 Stats", "🔙 Back to Main")
    return kb

def cancel_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("❌ Cancel")
    return kb

# ─── /start ───────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def start(msg):
    user_id   = msg.from_user.id
    username  = msg.from_user.username or ""
    full_name = msg.from_user.first_name + (" " + msg.from_user.last_name if msg.from_user.last_name else "")

    referred_by = None
    parts = msg.text.split()
    if len(parts) > 1:
        ref_code = parts[1]
        conn = get_db()
        row = conn.execute("SELECT user_id FROM users WHERE refer_code=?", (ref_code,)).fetchone()
        conn.close()
        if row and row[0] != user_id:
            referred_by = row[0]

    existing = get_user(user_id)
    is_new = not existing

    if is_new:
        create_user(user_id, username, full_name, referred_by)
        text = (
            f"🔥 *Welcome to FIRE SERVICE!*\n\n"
            f"Instagram • YouTube • Telegram\n"
            f"Instant • Trusted • Premium\n\n"
            f"🎉 Account created successfully!\n"
            f"💰 Order social media services easily.\n\n"
            f"❓ Support: {ADMIN_TG}"
        )
        # Notify admin about new user
        try:
            bot.send_message(ADMIN_ID,
                f"🆕 *New User Joined!*\n\n"
                f"👤 Name: {full_name}\n"
                f"🆔 User ID: `{user_id}`\n"
                f"📛 Username: @{username or 'none'}\n"
                f"🕐 Time: {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
                f"{'👥 Referred by: ' + str(referred_by) if referred_by else '🔗 Direct join'}",
                parse_mode="Markdown")
        except: pass
    else:
        text = f"✅ *Welcome back, {full_name}!*\n\n💰 Balance: ₹{existing['balance']:.2f}"

    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))

# ─── BALANCE ──────────────────────────────────────────────────
@bot.message_handler(commands=["balance"])
@bot.message_handler(func=lambda m: m.text == "💼 My Balance")
def my_balance(msg):
    user_id = msg.from_user.id
    bal = get_balance(user_id)
    bot.send_message(msg.chat.id,
        f"💰 *Your Balance*\n\n₹{bal:.2f}\n\nUse *Add Fund* to recharge!",
        parse_mode="Markdown", reply_markup=main_keyboard(user_id))

# ─── CONTACT SUPPORT ──────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "📞 Contact Support")
def contact_support(msg):
    bot.send_message(msg.chat.id,
        f"📞 *Contact Support*\n\n"
        f"Telegram: {ADMIN_TG}\n\n"
        f"Send your query directly. We reply fast! 🚀",
        parse_mode="Markdown")

# ─── DAILY REWARD ─────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🎁 Daily Reward")
def daily_reward(msg):
    user_id = msg.from_user.id
    user = get_user(user_id)
    if not user: return

    today = str(date.today())
    if user.get('last_reward') == today:
        bot.send_message(msg.chat.id, "⏰ *Already claimed!*\nCome back tomorrow 🎁", parse_mode="Markdown")
        return

    conn = get_db()
    conn.execute("UPDATE users SET balance=balance+?, last_reward=? WHERE user_id=?",
                 (DAILY_REWARD, today, user_id))
    conn.commit()
    conn.close()

    new_bal = get_balance(user_id)
    bot.send_message(msg.chat.id,
        f"🎉 *Daily Reward Claimed!*\n\n+₹{DAILY_REWARD}\n💰 Balance: ₹{new_bal:.2f}",
        parse_mode="Markdown")

# ─── ADD FUND (QR flow) ───────────────────────────────────────
pay_state = {}  # user_id -> {'step': 'amount'/'screenshot', 'amount': X, 'pay_id': Y}

@bot.message_handler(func=lambda m: m.text == "💰 Add Fund")
def add_fund(msg):
    user_id = msg.from_user.id
    bot.send_message(msg.chat.id,
        f"💳 *Add Fund to Wallet*\n\n"
        f"UPI ID: `{UPI_ID}`\n\n"
        f"📌 Enter the amount you want to add:\n"
        f"_(Minimum: ₹{MIN_PAYMENT:.0f})_",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard())
    pay_state[user_id] = {'step': 'amount'}

@bot.message_handler(func=lambda m: pay_state.get(m.from_user.id, {}).get('step') == 'amount')
def pay_amount_entered(msg):
    user_id = msg.from_user.id
    if msg.text == "❌ Cancel":
        pay_state.pop(user_id, None)
        bot.send_message(msg.chat.id, "❌ Cancelled.", reply_markup=main_keyboard(user_id))
        return

    try:
        amount = float(msg.text.strip())
    except:
        bot.send_message(msg.chat.id, "❌ Invalid amount! Enter a number like 100", reply_markup=cancel_keyboard())
        return

    if amount < MIN_PAYMENT:
        bot.send_message(msg.chat.id, f"❌ Minimum amount is ₹{MIN_PAYMENT:.0f}", reply_markup=cancel_keyboard())
        return

    # Generate QR
    user = get_user(user_id)
    name = user['full_name'] if user else "User"
    qr_img = generate_upi_qr(amount, name)

    pay_state[user_id] = {'step': 'screenshot', 'amount': amount}

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📸 Send Screenshot", "❌ Cancel")

    bot.send_photo(msg.chat.id, qr_img,
        caption=f"📲 *Pay ₹{amount:.2f} via UPI*\n\n"
                f"🏦 UPI ID: `{UPI_ID}`\n"
                f"💰 Amount: ₹{amount:.2f}\n\n"
                f"1️⃣ Scan QR or pay to UPI ID above\n"
                f"2️⃣ Click *Send Screenshot* below\n"
                f"3️⃣ Upload payment screenshot\n"
                f"4️⃣ Admin will verify & add balance ✅",
        parse_mode="Markdown",
        reply_markup=kb)

@bot.message_handler(func=lambda m: pay_state.get(m.from_user.id, {}).get('step') == 'screenshot')
def pay_screenshot_prompt(msg):
    user_id = msg.from_user.id
    if msg.text == "❌ Cancel":
        pay_state.pop(user_id, None)
        bot.send_message(msg.chat.id, "❌ Cancelled.", reply_markup=main_keyboard(user_id))
        return
    if msg.text == "📸 Send Screenshot":
        bot.send_message(msg.chat.id,
            "📸 *Send your payment screenshot now*\n_(Upload the photo)_",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard())
        pay_state[user_id]['step'] = 'photo'

@bot.message_handler(content_types=["photo"],
                     func=lambda m: pay_state.get(m.from_user.id, {}).get('step') == 'photo')
def pay_photo_received(msg):
    user_id = msg.from_user.id
    state = pay_state.pop(user_id, {})
    amount = state.get('amount', 0)
    user = get_user(user_id)

    # Save to DB
    file_id = msg.photo[-1].file_id
    conn = get_db()
    conn.execute(
        "INSERT INTO payments (user_id,amount,screenshot,status,created_at) VALUES (?,?,?,'Pending',?)",
        (user_id, amount, file_id, datetime.now().isoformat())
    )
    pay_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()

    bot.send_message(msg.chat.id,
        f"✅ *Payment request submitted!*\n\n"
        f"💰 Amount: ₹{amount:.2f}\n"
        f"⏳ Status: Pending\n\n"
        f"Admin will verify and add balance soon.\n"
        f"Support: {ADMIN_TG}",
        parse_mode="Markdown",
        reply_markup=main_keyboard(user_id))

    # Notify admin with screenshot + approve/reject buttons
    caption = (
        f"💳 *New Payment Request #{pay_id}*\n\n"
        f"👤 {user['full_name'] if user else 'Unknown'}\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📛 @{user.get('username','') or 'none'}\n"
        f"💰 Amount: ₹{amount:.2f}\n"
        f"🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n\n"
        f"✅ `/approve_pay {pay_id}`\n"
        f"❌ `/reject_pay {pay_id}`"
    )

    # Inline buttons for quick approve/reject
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(f"✅ Approve ₹{amount:.2f}", callback_data=f"apay_{pay_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"rpay_{pay_id}")
    )

    try:
        bot.send_photo(ADMIN_ID, file_id, caption=caption, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        bot.send_message(ADMIN_ID, caption, parse_mode="Markdown", reply_markup=markup)

# ─── INLINE BUTTON CALLBACKS ──────────────────────────────────
@bot.callback_query_handler(func=lambda c: c.data.startswith("apay_") or c.data.startswith("rpay_"))
def handle_pay_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Not authorized")
        return

    action, pay_id = call.data.split("_", 1)
    pay_id = int(pay_id)

    conn = get_db()
    pay = conn.execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()

    if not pay:
        bot.answer_callback_query(call.id, "❌ Payment not found")
        conn.close()
        return

    if dict(pay)['status'] != 'Pending':
        bot.answer_callback_query(call.id, "⚠️ Already processed!")
        conn.close()
        return

    pay = dict(pay)

    if action == "apay":
        conn.execute("UPDATE payments SET status='Approved' WHERE id=?", (pay_id,))
        conn.commit()
        conn.close()
        add_balance(pay['user_id'], pay['amount'])
        new_bal = get_balance(pay['user_id'])

        bot.answer_callback_query(call.id, f"✅ Approved ₹{pay['amount']:.2f}")
        bot.edit_message_caption(
            caption=call.message.caption + f"\n\n✅ *APPROVED* by admin",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        try:
            bot.send_message(pay['user_id'],
                f"✅ *Payment Approved!*\n\n"
                f"💰 ₹{pay['amount']:.2f} added to your wallet!\n"
                f"🏦 New Balance: ₹{new_bal:.2f}\n\n"
                f"Use it to order services 🚀",
                parse_mode="Markdown",
                reply_markup=main_keyboard(pay['user_id']))
        except: pass

    else:  # reject
        conn.execute("UPDATE payments SET status='Rejected' WHERE id=?", (pay_id,))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, "❌ Rejected")
        bot.edit_message_caption(
            caption=call.message.caption + f"\n\n❌ *REJECTED* by admin",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        try:
            bot.send_message(pay['user_id'],
                f"❌ *Payment Rejected*\n\n"
                f"Amount: ₹{pay['amount']:.2f}\n\n"
                f"If this is a mistake, contact {ADMIN_TG}",
                parse_mode="Markdown")
        except: pass

# ─── REFER & EARN ─────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🤝 Refer and Earn")
def refer_earn(msg):
    user_id = msg.from_user.id
    user = get_user(user_id)
    if not user: return

    ref_code = user['refer_code']
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={ref_code}"

    conn = get_db()
    total_refs = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()[0]
    conn.close()

    bot.send_message(msg.chat.id,
        f"🤝 *Refer & Earn*\n\n"
        f"🎁 Earn ₹{REFER_BONUS} per referral!\n\n"
        f"Your Link:\n`{ref_link}`\n\n"
        f"👥 Referrals: *{total_refs}*\n"
        f"💰 Earned: *₹{total_refs * REFER_BONUS:.2f}*",
        parse_mode="Markdown")

# ─── EARN MONEY ───────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "💸 Earn money")
def earn_money(msg):
    user_id = msg.from_user.id
    bal = get_balance(user_id)
    bot.send_message(msg.chat.id,
        f"💸 *Ways to Earn*\n\n"
        f"1️⃣ Daily Reward – ₹{DAILY_REWARD}/day\n"
        f"2️⃣ Refer Friends – ₹{REFER_BONUS}/referral\n\n"
        f"💰 Balance: ₹{bal:.2f}\n"
        f"📤 Min Withdrawal: ₹{MIN_WITHDRAW}\n\n"
        f"`/withdraw <amount> <upi_id>`",
        parse_mode="Markdown")

# ─── WITHDRAW ─────────────────────────────────────────────────
@bot.message_handler(commands=["withdraw"])
def withdraw_cmd(msg):
    user_id = msg.from_user.id
    parts = msg.text.split()
    if len(parts) != 3:
        bot.send_message(msg.chat.id, "❌ Format: `/withdraw <amount> <upi_id>`", parse_mode="Markdown")
        return

    try:
        amount = float(parts[1])
    except:
        bot.send_message(msg.chat.id, "❌ Invalid amount!", parse_mode="Markdown")
        return

    upi_id = parts[2]
    bal = get_balance(user_id)

    if amount < MIN_WITHDRAW:
        bot.send_message(msg.chat.id, f"❌ Minimum withdrawal ₹{MIN_WITHDRAW}", parse_mode="Markdown")
        return
    if bal < amount:
        bot.send_message(msg.chat.id, f"❌ Insufficient balance! You have ₹{bal:.2f}", parse_mode="Markdown")
        return

    deduct_balance(user_id, amount)
    conn = get_db()
    conn.execute("INSERT INTO withdrawals (user_id,amount,upi_id,status,created_at) VALUES (?,?,?,'Pending',?)",
                 (user_id, amount, upi_id, datetime.now().isoformat()))
    wid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()

    user = get_user(user_id)
    bot.send_message(msg.chat.id,
        f"✅ *Withdrawal Requested!*\n\n"
        f"💰 Amount: ₹{amount}\nUPI: `{upi_id}`\n⏳ Processing...",
        parse_mode="Markdown")

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(f"✅ Pay ₹{amount}", callback_data=f"awd_{wid}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"rwd_{wid}")
    )
    bot.send_message(ADMIN_ID,
        f"💸 *Withdrawal #{wid}*\n\n"
        f"👤 {user['full_name']}\n"
        f"🆔 `{user_id}`\n"
        f"💰 ₹{amount}\nUPI: `{upi_id}`\n\n"
        f"✅ `/approve_wd {wid}`  ❌ `/reject_wd {wid}`",
        parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("awd_") or c.data.startswith("rwd_"))
def handle_wd_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Not authorized")
        return
    action, wid = call.data.split("_", 1)
    wid = int(wid)
    conn = get_db()
    wd = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
    if not wd:
        bot.answer_callback_query(call.id, "❌ Not found")
        conn.close()
        return
    wd = dict(wd)
    if wd['status'] != 'Pending':
        bot.answer_callback_query(call.id, "⚠️ Already processed")
        conn.close()
        return

    if action == "awd":
        conn.execute("UPDATE withdrawals SET status='Paid' WHERE id=?", (wid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "✅ Marked as Paid")
        bot.edit_message_text(call.message.text + "\n\n✅ *PAID*", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        try:
            bot.send_message(wd['user_id'], f"✅ *Withdrawal Paid!*\n\n₹{wd['amount']} sent to `{wd['upi_id']}`", parse_mode="Markdown")
        except: pass
    else:
        conn.execute("UPDATE withdrawals SET status='Rejected' WHERE id=?", (wid,))
        conn.commit()
        conn.close()
        add_balance(wd['user_id'], wd['amount'])
        bot.answer_callback_query(call.id, "❌ Rejected & Refunded")
        bot.edit_message_text(call.message.text + "\n\n❌ *REJECTED* — refunded", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        try:
            bot.send_message(wd['user_id'], f"❌ *Withdrawal Rejected*\n\n₹{wd['amount']} refunded to wallet.", parse_mode="Markdown")
        except: pass

# ─── MY ORDERS ────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "📋 My Orders")
def my_orders(msg):
    user_id = msg.from_user.id
    conn = get_db()
    orders = conn.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,)
    ).fetchall()
    conn.close()

    if not orders:
        bot.send_message(msg.chat.id, "📭 No orders yet!\nUse *Social Media Service* to order.", parse_mode="Markdown")
        return

    text = "📋 *Your Recent Orders:*\n\n"
    emojis = {"Completed":"✅","Pending":"⏳","Processing":"▶️","Cancelled":"❌"}
    for o in orders:
        o = dict(o)
        em = emojis.get(o['status'], "⏳")
        text += f"#{o['id']} {em} *{o['status']}*\n📱 {o['platform']} • {o['sub_service']}\n🔢 {o['quantity']:,} | ₹{o['price']:.2f}\n\n"

    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# ─── WEB APP ORDER ────────────────────────────────────────────
@bot.message_handler(content_types=["web_app_data"])
def web_app_order(msg):
    user_id = msg.from_user.id
    try:
        data = json.loads(msg.web_app_data.data)
        platform    = data["platform"]
        service     = data["service"]
        sub_service = data["sub_service"]
        link        = data["link"]
        quantity    = int(data["quantity"])
        price       = float(data["price"])

        bal = get_balance(user_id)
        if bal < price:
            bot.send_message(msg.chat.id,
                f"❌ *Insufficient Balance!*\n\nRequired: ₹{price:.2f}\nYour Balance: ₹{bal:.2f}\n\nUse *Add Fund* 💰",
                parse_mode="Markdown")
            return

        deduct_balance(user_id, price)
        conn = get_db()
        conn.execute("""INSERT INTO orders
            (user_id,platform,service,sub_service,link,quantity,price,status,created_at)
            VALUES (?,?,?,?,?,?,?,'Pending',?)""",
            (user_id, platform, service, sub_service, link, quantity, price, datetime.now().isoformat()))
        order_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()

        new_bal = get_balance(user_id)
        user = get_user(user_id)

        bot.send_message(msg.chat.id,
            f"✅ *Order Placed!*\n\n"
            f"🆔 #{order_id}\n📱 {platform} • {sub_service}\n"
            f"🔗 `{link}`\n🔢 {quantity:,}\n💰 ₹{price:.2f}\n"
            f"🏦 New Balance: ₹{new_bal:.2f}\n⏳ Status: Pending",
            parse_mode="Markdown")

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("▶️ Processing", callback_data=f"proc_{order_id}"),
            types.InlineKeyboardButton("✅ Complete", callback_data=f"comp_{order_id}")
        )
        markup.add(types.InlineKeyboardButton("❌ Cancel+Refund", callback_data=f"canc_{order_id}"))

        bot.send_message(ADMIN_ID,
            f"📦 *New Order #{order_id}*\n\n"
            f"👤 {user['full_name']} (ID: `{user_id}`)\n"
            f"📱 {platform} | {sub_service}\n"
            f"🔗 {link}\n🔢 {quantity:,}\n💰 ₹{price:.2f}",
            parse_mode="Markdown", reply_markup=markup)

    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Order failed: {str(e)}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("proc_") or c.data.startswith("comp_") or c.data.startswith("canc_"))
def handle_order_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Not authorized")
        return
    action, oid = call.data.split("_", 1)
    oid = int(oid)
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not order:
        bot.answer_callback_query(call.id, "❌ Order not found")
        conn.close()
        return
    order = dict(order)

    if action == "proc":
        conn.execute("UPDATE orders SET status='Processing' WHERE id=?", (oid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "▶️ Set to Processing")
        try:
            bot.send_message(order['user_id'], f"▶️ *Order #{oid} is Processing!*\nWe're working on it 🔥", parse_mode="Markdown")
        except: pass

    elif action == "comp":
        conn.execute("UPDATE orders SET status='Completed' WHERE id=?", (oid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "✅ Completed!")
        bot.edit_message_text(call.message.text + "\n\n✅ *COMPLETED*", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        try:
            bot.send_message(order['user_id'],
                f"✅ *Order Completed!*\n\n🆔 #{oid}\n📱 {order['sub_service']}\n🔢 {order['quantity']:,}",
                parse_mode="Markdown")
        except: pass

    elif action == "canc":
        conn.execute("UPDATE orders SET status='Cancelled' WHERE id=?", (oid,))
        conn.commit()
        conn.close()
        add_balance(order['user_id'], order['price'])
        bot.answer_callback_query(call.id, "❌ Cancelled & Refunded")
        bot.edit_message_text(call.message.text + "\n\n❌ *CANCELLED & REFUNDED*", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        try:
            bot.send_message(order['user_id'],
                f"❌ *Order #{oid} Cancelled*\n₹{order['price']:.2f} refunded to wallet.",
                parse_mode="Markdown")
        except: pass

# ─── ADMIN PANEL ──────────────────────────────────────────────
def is_admin(msg):
    return msg.from_user.id == ADMIN_ID

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel" and is_admin(m))
def admin_panel(msg):
    bot.send_message(msg.chat.id, "⚙️ *Admin Panel*\nSelect an option:",
                     parse_mode="Markdown", reply_markup=admin_keyboard())

@bot.message_handler(func=lambda m: m.text == "🔙 Back to Main" and is_admin(m))
def back_main(msg):
    bot.send_message(msg.chat.id, "🏠 Main Menu", reply_markup=main_keyboard(msg.from_user.id))

@bot.message_handler(func=lambda m: m.text == "📊 Stats" and is_admin(m))
def stats(msg):
    users    = get_all_users()
    orders   = get_all_orders()
    payments = get_all_payments()
    total_rev = sum(o['price'] for o in orders if o['status'] != 'Cancelled')
    pending_pay = sum(p['amount'] for p in payments if p['status'] == 'Pending')
    bot.send_message(msg.chat.id,
        f"📊 *FIRE SERVICE Stats*\n\n"
        f"👥 Users: {len(users)}\n"
        f"📦 Orders: {len(orders)}\n"
        f"⏳ Pending: {sum(1 for o in orders if o['status']=='Pending')}\n"
        f"💰 Revenue: ₹{total_rev:.2f}\n"
        f"💳 Pending Payments: ₹{pending_pay:.2f}",
        parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👥 All Users" and is_admin(m))
def all_users_cmd(msg):
    users = get_all_users()
    text = f"👥 *All Users ({len(users)}):*\n\n"
    for u in users[:20]:
        uname = f"@{u['username']}" if u.get('username') else "no username"
        text += f"• {u['full_name']} ({uname})\n  ID: `{u['user_id']}` | ₹{u['balance']:.2f}\n\n"
    if len(users) > 20:
        text += f"...and {len(users)-20} more"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📦 All Orders" and is_admin(m))
def all_orders_cmd(msg):
    orders = get_all_orders()
    if not orders:
        bot.send_message(msg.chat.id, "No orders yet.")
        return
    text = f"📦 *Recent Orders ({len(orders)}):*\n\n"
    for o in orders[:10]:
        text += f"#{o['id']} | {o['platform']} | ₹{o['price']} | {o['status']}\n"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💳 Payments" and is_admin(m))
def all_payments_cmd(msg):
    payments = get_all_payments()
    pending = [p for p in payments if p['status'] == 'Pending']
    if not pending:
        bot.send_message(msg.chat.id, "✅ No pending payments.")
        return
    for p in pending[:10]:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(f"✅ Approve ₹{p['amount']}", callback_data=f"apay_{p['id']}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rpay_{p['id']}")
        )
        bot.send_message(msg.chat.id,
            f"💳 Payment #{p['id']}\nUser: `{p['user_id']}`\nAmount: ₹{p['amount']}\nTime: {p['created_at'][:16]}",
            parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💸 Withdrawals" and is_admin(m))
def all_wds_cmd(msg):
    wds = get_all_withdrawals()
    pending = [w for w in wds if w['status'] == 'Pending']
    if not pending:
        bot.send_message(msg.chat.id, "✅ No pending withdrawals.")
        return
    for w in pending[:10]:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(f"✅ Pay ₹{w['amount']}", callback_data=f"awd_{w['id']}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rwd_{w['id']}")
        )
        bot.send_message(msg.chat.id,
            f"💸 Withdrawal #{w['id']}\nUser: `{w['user_id']}`\nAmount: ₹{w['amount']}\nUPI: {w['upi_id']}",
            parse_mode="Markdown", reply_markup=markup)

# ─── ADMIN COMMANDS ───────────────────────────────────────────
@bot.message_handler(commands=["addbal"])
def addbal_cmd(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 3:
        bot.send_message(msg.chat.id, "Usage: /addbal <user_id> <amount>")
        return
    uid, amount = int(parts[1]), float(parts[2])
    add_balance(uid, amount)
    new_bal = get_balance(uid)
    bot.send_message(msg.chat.id, f"✅ Added ₹{amount} to user {uid}\nNew balance: ₹{new_bal:.2f}")
    try:
        bot.send_message(uid,
            f"💰 *Balance Added!*\n\n+₹{amount} added by admin\n🏦 New Balance: ₹{new_bal:.2f}",
            parse_mode="Markdown", reply_markup=main_keyboard(uid))
    except: pass

@bot.message_handler(commands=["approve_pay"])
def approve_pay(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    pay_id = int(parts[1])
    conn = get_db()
    pay = conn.execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
    if not pay or dict(pay)['status'] != 'Pending':
        conn.close()
        bot.send_message(msg.chat.id, "❌ Not found or already processed.")
        return
    pay = dict(pay)
    conn.execute("UPDATE payments SET status='Approved' WHERE id=?", (pay_id,))
    conn.commit()
    conn.close()
    add_balance(pay['user_id'], pay['amount'])
    new_bal = get_balance(pay['user_id'])
    bot.send_message(msg.chat.id, f"✅ Payment #{pay_id} approved! ₹{pay['amount']} → user {pay['user_id']}")
    try:
        bot.send_message(pay['user_id'],
            f"✅ *Payment Approved!*\n\n₹{pay['amount']} added!\n🏦 Balance: ₹{new_bal:.2f}",
            parse_mode="Markdown", reply_markup=main_keyboard(pay['user_id']))
    except: pass

@bot.message_handler(commands=["reject_pay"])
def reject_pay(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    pay_id = int(parts[1])
    conn = get_db()
    pay = conn.execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
    if not pay:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Not found.")
        return
    pay = dict(pay)
    conn.execute("UPDATE payments SET status='Rejected' WHERE id=?", (pay_id,))
    conn.commit()
    conn.close()
    bot.send_message(msg.chat.id, f"❌ Payment #{pay_id} rejected.")
    try:
        bot.send_message(pay['user_id'],
            f"❌ *Payment Rejected*\n\nAmount: ₹{pay['amount']}\nContact {ADMIN_TG} for help.",
            parse_mode="Markdown")
    except: pass

@bot.message_handler(commands=["approve_wd"])
def approve_wd(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    wid = int(parts[1])
    conn = get_db()
    wd = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
    if not wd:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Not found.")
        return
    wd = dict(wd)
    conn.execute("UPDATE withdrawals SET status='Paid' WHERE id=?", (wid,))
    conn.commit()
    conn.close()
    bot.send_message(msg.chat.id, f"✅ Withdrawal #{wid} marked as paid!")
    try:
        bot.send_message(wd['user_id'], f"✅ *Withdrawal Paid!*\n₹{wd['amount']} → `{wd['upi_id']}`", parse_mode="Markdown")
    except: pass

@bot.message_handler(commands=["reject_wd"])
def reject_wd(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    wid = int(parts[1])
    conn = get_db()
    wd = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
    if not wd:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Not found.")
        return
    wd = dict(wd)
    conn.execute("UPDATE withdrawals SET status='Rejected' WHERE id=?", (wid,))
    conn.commit()
    conn.close()
    add_balance(wd['user_id'], wd['amount'])
    bot.send_message(msg.chat.id, f"❌ Rejected & ₹{wd['amount']} refunded.")
    try:
        bot.send_message(wd['user_id'], f"❌ *Withdrawal Rejected*\n₹{wd['amount']} refunded.", parse_mode="Markdown")
    except: pass

@bot.message_handler(commands=["complete"])
def complete_order(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    oid = int(parts[1])
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not order:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Not found.")
        return
    order = dict(order)
    conn.execute("UPDATE orders SET status='Completed' WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    bot.send_message(msg.chat.id, f"✅ Order #{oid} completed!")
    try:
        bot.send_message(order['user_id'], f"✅ *Order #{oid} Completed!*\n{order['sub_service']} | {order['quantity']:,}", parse_mode="Markdown")
    except: pass

@bot.message_handler(commands=["processing"])
def processing_order(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    oid = int(parts[1])
    conn = get_db()
    conn.execute("UPDATE orders SET status='Processing' WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    bot.send_message(msg.chat.id, f"▶️ Order #{oid} → Processing")

@bot.message_handler(commands=["cancel_order"])
def cancel_order(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    oid = int(parts[1])
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not order:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Not found.")
        return
    order = dict(order)
    conn.execute("UPDATE orders SET status='Cancelled' WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    add_balance(order['user_id'], order['price'])
    bot.send_message(msg.chat.id, f"❌ Order #{oid} cancelled. ₹{order['price']:.2f} refunded.")
    try:
        bot.send_message(order['user_id'], f"❌ *Order #{oid} Cancelled*\n₹{order['price']:.2f} refunded.", parse_mode="Markdown")
    except: pass

# ─── BROADCAST ────────────────────────────────────────────────
broadcast_state = {}

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast" and is_admin(m))
def broadcast_start(msg):
    broadcast_state[msg.from_user.id] = True
    bot.send_message(msg.chat.id, "📢 Send the message to broadcast:")

@bot.message_handler(func=lambda m: broadcast_state.get(m.from_user.id) and is_admin(m))
def broadcast_send(msg):
    broadcast_state.pop(msg.from_user.id, None)
    users = get_all_users()
    sent = failed = 0
    for u in users:
        try:
            bot.send_message(u['user_id'], f"📢 *Announcement*\n\n{msg.text}", parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
    bot.send_message(msg.chat.id, f"✅ Broadcast done!\nSent: {sent} | Failed: {failed}")

# ─── MANAGE SERVICES ──────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🛠️ Manage Services" and is_admin(m))
def manage_services(msg):
    conn = get_db()
    services = conn.execute("SELECT * FROM services").fetchall()
    conn.close()
    text = "🛠️ *Services:*\n\n"
    for s in services:
        s = dict(s)
        st = "✅" if s['active'] else "❌"
        text += f"{st} #{s['id']} {s['platform']} | {s['name']} | ₹{s['rate_per_k']}/K\n"
    text += "\n`/edit_service <id> <rate>`\n`/toggle_service <id>`\n`/add_service <plat> <cat> <name> <min> <max> <rate>`"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["edit_service"])
def edit_service(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 3: return
    sid, rate = int(parts[1]), float(parts[2])
    conn = get_db()
    conn.execute("UPDATE services SET rate_per_k=? WHERE id=?", (rate, sid))
    conn.commit()
    conn.close()
    bot.send_message(msg.chat.id, f"✅ Service #{sid} rate → ₹{rate}/K")

@bot.message_handler(commands=["toggle_service"])
def toggle_service(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    sid = int(parts[1])
    conn = get_db()
    row = conn.execute("SELECT active FROM services WHERE id=?", (sid,)).fetchone()
    if not row:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Not found.")
        return
    new = 0 if row[0] == 1 else 1
    conn.execute("UPDATE services SET active=? WHERE id=?", (new, sid))
    conn.commit()
    conn.close()
    bot.send_message(msg.chat.id, f"Service #{sid} {'✅ enabled' if new else '❌ disabled'}")

@bot.message_handler(commands=["add_service"])
def add_service_cmd(msg):
    if not is_admin(msg): return
    parts = msg.text.split(maxsplit=7)
    if len(parts) != 8:
        bot.send_message(msg.chat.id, "Usage: /add_service <platform> <category> <name> <min> <max> <rate>")
        return
    _, platform, category, name, min_q, max_q, rate = parts[1:]
    conn = get_db()
    conn.execute("INSERT INTO services (platform,category,name,min_qty,max_qty,rate_per_k) VALUES (?,?,?,?,?,?)",
                 (platform, category, name, int(min_q), int(max_q), float(rate)))
    conn.commit()
    conn.close()
    bot.send_message(msg.chat.id, f"✅ '{name}' added for {platform}!")

# ─── HELP ─────────────────────────────────────────────────────
@bot.message_handler(commands=["help"])
def help_cmd(msg):
    bot.send_message(msg.chat.id,
        f"🔥 *FIRE SERVICE Help*\n\n"
        f"💰 *Add Fund* → Enter amount → Pay UPI → Send screenshot\n"
        f"🛍️ *Order* → Use Social Media Service button\n"
        f"📋 *Orders* → Check history\n"
        f"🎁 *Daily Reward* → Free ₹{DAILY_REWARD} daily\n"
        f"🤝 *Refer* → Earn ₹{REFER_BONUS} per referral\n"
        f"💸 *Withdraw* → `/withdraw <amount> <upi>`\n\n"
        f"❓ Support: {ADMIN_TG}",
        parse_mode="Markdown")

# ─── RUN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    # Install qrcode if not present
    try:
        import qrcode
    except ImportError:
        os.system("pip install qrcode[pil] -q")
        import qrcode

    print("🔥 FIRE SERVICE Bot starting...")
    init_db()
    print(f"✅ DB ready | Admin: {ADMIN_ID} | UPI: {UPI_ID}")
    print("🚀 Polling...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
