import telebot
import sqlite3
import json
import os
import random
import string
from datetime import datetime, date
from telebot import types

# ============================================================
#  CONFIGURATION — EDIT THESE
# ============================================================
BOT_TOKEN    = "8752034680:AAFClfX0NwflANlKrcD5WPANd-Hfipw088U"
ADMIN_ID     = 6270522295
UPI_ID       = "yourname@upi"                  # Step 3: Apna UPI ID daalo
WEB_APP_URL  = "https://firesm.netlify.app"
DAILY_REWARD = 0.08                            # Daily reward amount (₹)
MIN_WITHDRAW = 50.0                            # Minimum withdrawal (₹)
REFER_BONUS  = 5.0                             # Referral bonus (₹)
# ============================================================

bot = telebot.TeleBot(BOT_TOKEN)

# ─── DATABASE SETUP ───────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id     INTEGER PRIMARY KEY,
        username    TEXT,
        full_name   TEXT,
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
        utr         TEXT,
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

    # Insert default services if empty
    c.execute("SELECT COUNT(*) FROM services")
    if c.fetchone()[0] == 0:
        default_services = [
            # Instagram
            ("Instagram","Followers","Real Followers",100,100000,10),
            ("Instagram","Followers","Premium Followers",100,50000,20),
            ("Instagram","Likes","Post Likes",50,500000,2),
            ("Instagram","Views","Reel / Video Views",100,2147483647,5),
            ("Instagram","Views","Story Views",100,1000000,3),
            ("Instagram","Comments","Random Comments",10,10000,30),
            # YouTube
            ("YouTube","Views","Video Views",1000,10000000,8),
            ("YouTube","Subscribers","Channel Subscribers",100,500000,15),
            ("YouTube","Likes","Video Likes",100,500000,5),
            ("YouTube","Watch Hours","Watch Hours",100,10000,50),
            # Telegram
            ("Telegram","Members","Channel Members",100,1000000,6),
            ("Telegram","Members","Group Members",100,500000,6),
            ("Telegram","Views","Post Views",100,5000000,1),
            # Facebook
            ("Facebook","Likes","Page Likes",100,500000,8),
            ("Facebook","Followers","Profile Followers",100,500000,10),
            ("Facebook","Views","Video Views",1000,5000000,5),
            # WhatsApp
            ("WhatsApp","Members","Group Members",50,100000,12),
        ]
        c.executemany(
            "INSERT INTO services (platform,category,name,min_qty,max_qty,rate_per_k) VALUES (?,?,?,?,?,?)",
            default_services
        )

    conn.commit()
    conn.close()

# ─── DB HELPERS ────────────────────────────────────────────────
def get_user(user_id):
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def create_user(user_id, username, full_name, referred_by=None):
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("""INSERT OR IGNORE INTO users
        (user_id,username,full_name,balance,refer_code,referred_by,joined_at)
        VALUES (?,?,?,0,?,?,?)""",
        (user_id, username, full_name, code, referred_by, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    # Give referral bonus to referrer
    if referred_by:
        add_balance(referred_by, REFER_BONUS)

def add_balance(user_id, amount):
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def deduct_balance(user_id, amount):
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def get_balance(user_id):
    user = get_user(user_id)
    return user[3] if user else 0

def get_services(platform=None):
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    if platform:
        c.execute("SELECT * FROM services WHERE platform=? AND active=1", (platform,))
    else:
        c.execute("SELECT * FROM services WHERE active=1")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_services():
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM services")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_users():
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_orders():
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_payments():
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM payments ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_withdrawals():
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM withdrawals ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_services_json():
    """Return services as JSON for web app"""
    services = get_services()
    result = {}
    for s in services:
        sid, platform, category, name, min_q, max_q, rate, active = s
        if platform not in result:
            result[platform] = {}
        if category not in result[platform]:
            result[platform][category] = []
        result[platform][category].append({
            "id": sid, "name": name,
            "min": min_q, "max": max_q, "rate": rate
        })
    return json.dumps(result)

# ─── KEYBOARDS ─────────────────────────────────────────────────
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
    if user_id == ADMIN_ID:
        kb.add("⚙️ Admin Panel")
    return kb

def admin_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("👥 All Users", "📦 All Orders")
    kb.add("💳 Payments", "💸 Withdrawals")
    kb.add("✅ Approve Payment", "❌ Reject Payment")
    kb.add("✅ Approve Withdrawal", "❌ Reject Withdrawal")
    kb.add("📢 Broadcast", "🛠️ Manage Services")
    kb.add("📊 Stats", "🔙 Back to Main")
    return kb

# ─── /start ────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def start(msg):
    user_id   = msg.from_user.id
    username  = msg.from_user.username or ""
    full_name = msg.from_user.first_name + (" " + msg.from_user.last_name if msg.from_user.last_name else "")

    referred_by = None
    parts = msg.text.split()
    if len(parts) > 1:
        ref_code = parts[1]
        conn = sqlite3.connect("fire_service.db")
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE refer_code=?", (ref_code,))
        row = c.fetchone()
        conn.close()
        if row and row[0] != user_id:
            referred_by = row[0]

    existing = get_user(user_id)
    if not existing:
        create_user(user_id, username, full_name, referred_by)
        welcome = "new"
    else:
        welcome = "back"

    if welcome == "new":
        text = (
            f"🔥 *Welcome to FIRE SERVICE!*\n\n"
            f"Instagram • YouTube • Telegram\n"
            f"Instant • Trusted • Premium\n\n"
            f"🎉 Account created successfully!\n"
            f"You can now order social media services.\n\n"
            f"Any issue? Contact @{username or 'support'}"
        )
    else:
        text = "✅ *Welcome back!*\nYou're all set 🎉"

    bot.send_message(msg.chat.id, text, parse_mode="Markdown",
                     reply_markup=main_keyboard(user_id))

# ─── BALANCE ───────────────────────────────────────────────────
@bot.message_handler(commands=["balance"])
def balance_cmd(msg):
    bal = get_balance(msg.from_user.id)
    bot.send_message(msg.chat.id,
        f"💰 *Your Current Balance:* ₹{bal:.2f}\n\nUse 'Add Fund 💰' to top up your wallet!",
        parse_mode="Markdown", reply_markup=main_keyboard(msg.from_user.id))

@bot.message_handler(func=lambda m: m.text == "💼 My Balance")
def my_balance(msg):
    balance_cmd(msg)

# ─── DAILY REWARD ──────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🎁 Daily Reward")
def daily_reward(msg):
    user_id = msg.from_user.id
    user = get_user(user_id)
    if not user:
        return

    today = str(date.today())
    last_reward = user[6]  # last_reward column

    if last_reward == today:
        bot.send_message(msg.chat.id,
            "⏰ *Already claimed!*\nCome back tomorrow for your next reward 🎁",
            parse_mode="Markdown")
        return

    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("UPDATE users SET balance=balance+?, last_reward=? WHERE user_id=?",
              (DAILY_REWARD, today, user_id))
    conn.commit()
    conn.close()

    new_bal = get_balance(user_id)
    bot.send_message(msg.chat.id,
        f"🎉 *Congratulations!*\n\n"
        f"You received ₹{DAILY_REWARD} as today's daily reward.\n\n"
        f"💸 New Balance: ₹{new_bal:.2f}",
        parse_mode="Markdown")

# ─── ADD FUND ──────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "💰 Add Fund")
def add_fund(msg):
    user_id = msg.from_user.id
    text = (
        f"💳 *Add Fund to Wallet*\n\n"
        f"UPI ID: `{UPI_ID}`\n\n"
        f"📌 *Steps:*\n"
        f"1. Pay any amount via UPI\n"
        f"2. Send the UTR/Transaction ID below\n"
        f"3. Admin will verify & add balance\n\n"
        f"⬇️ *Reply with:* `/pay <amount> <UTR>`\n"
        f"Example: `/pay 100 123456789012`"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["pay"])
def pay_cmd(msg):
    user_id = msg.from_user.id
    parts = msg.text.split()
    if len(parts) != 3:
        bot.send_message(msg.chat.id, "❌ Format: `/pay <amount> <UTR>`", parse_mode="Markdown")
        return

    try:
        amount = float(parts[1])
        utr = parts[2]
    except:
        bot.send_message(msg.chat.id, "❌ Invalid amount!", parse_mode="Markdown")
        return

    if amount < 10:
        bot.send_message(msg.chat.id, "❌ Minimum add ₹10", parse_mode="Markdown")
        return

    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    # Check duplicate UTR
    c.execute("SELECT id FROM payments WHERE utr=?", (utr,))
    if c.fetchone():
        conn.close()
        bot.send_message(msg.chat.id, "❌ This UTR is already submitted!", parse_mode="Markdown")
        return

    c.execute("INSERT INTO payments (user_id,amount,utr,status,created_at) VALUES (?,?,?,'Pending',?)",
              (user_id, amount, utr, datetime.now().isoformat()))
    pay_id = c.lastrowid
    conn.commit()
    conn.close()

    user = get_user(user_id)
    bot.send_message(msg.chat.id,
        f"✅ *Payment request submitted!*\n\n"
        f"Amount: ₹{amount}\nUTR: `{utr}`\n"
        f"Status: ⏳ Pending\n\nAdmin will verify soon.",
        parse_mode="Markdown")

    # Notify admin
    bot.send_message(ADMIN_ID,
        f"💳 *New Payment Request* #{pay_id}\n\n"
        f"User: {user[2]} (ID: {user_id})\n"
        f"Amount: ₹{amount}\nUTR: `{utr}`\n\n"
        f"✅ `/approve_pay {pay_id}`\n❌ `/reject_pay {pay_id}`",
        parse_mode="Markdown")

# ─── REFER & EARN ──────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🤝 Refer and Earn")
def refer_earn(msg):
    user_id = msg.from_user.id
    user = get_user(user_id)
    if not user:
        return

    ref_code = user[4]
    ref_link = f"https://t.me/{bot.get_me().username}?start={ref_code}"

    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,))
    total_refs = c.fetchone()[0]
    conn.close()

    text = (
        f"🤝 *Refer & Earn Program*\n\n"
        f"🎁 Earn *₹{REFER_BONUS}* for every friend you refer!\n\n"
        f"Your Referral Link:\n`{ref_link}`\n\n"
        f"👥 Total Referrals: *{total_refs}*\n"
        f"💰 Earned: *₹{total_refs * REFER_BONUS:.2f}*\n\n"
        f"📌 Share this link with friends!"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# ─── EARN MONEY ────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "💸 Earn money")
def earn_money(msg):
    user_id = msg.from_user.id
    bal = get_balance(user_id)
    text = (
        f"💸 *Ways to Earn Money*\n\n"
        f"1️⃣ *Daily Reward* – ₹{DAILY_REWARD} every day\n"
        f"2️⃣ *Refer Friends* – ₹{REFER_BONUS} per referral\n\n"
        f"💰 Current Balance: ₹{bal:.2f}\n"
        f"📤 Min Withdrawal: ₹{MIN_WITHDRAW}\n\n"
        f"To withdraw: `/withdraw <amount> <upi_id>`\n"
        f"Example: `/withdraw 50 yourname@upi`"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# ─── WITHDRAW ──────────────────────────────────────────────────
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
        bot.send_message(msg.chat.id, f"❌ Minimum withdrawal is ₹{MIN_WITHDRAW}", parse_mode="Markdown")
        return

    if bal < amount:
        bot.send_message(msg.chat.id, f"❌ Insufficient balance! Your balance: ₹{bal:.2f}", parse_mode="Markdown")
        return

    deduct_balance(user_id, amount)

    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("INSERT INTO withdrawals (user_id,amount,upi_id,status,created_at) VALUES (?,?,?,'Pending',?)",
              (user_id, amount, upi_id, datetime.now().isoformat()))
    wid = c.lastrowid
    conn.commit()
    conn.close()

    user = get_user(user_id)
    bot.send_message(msg.chat.id,
        f"✅ *Withdrawal request submitted!*\n\n"
        f"Amount: ₹{amount}\nUPI: `{upi_id}`\n"
        f"Status: ⏳ Processing",
        parse_mode="Markdown")

    bot.send_message(ADMIN_ID,
        f"💸 *Withdrawal Request* #{wid}\n\n"
        f"User: {user[2]} (ID: {user_id})\n"
        f"Amount: ₹{amount}\nUPI: `{upi_id}`\n\n"
        f"✅ `/approve_wd {wid}`\n❌ `/reject_wd {wid}`",
        parse_mode="Markdown")

# ─── MY ORDERS ─────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "📋 My Orders")
def my_orders(msg):
    user_id = msg.from_user.id
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,))
    orders = c.fetchall()
    conn.close()

    if not orders:
        bot.send_message(msg.chat.id, "📭 No orders yet!\nUse 'Social Media Service' to place an order.")
        return

    text = "📋 *Your Recent Orders:*\n\n"
    for o in orders:
        oid, uid, platform, service, sub_service, link, qty, price, status, created = o
        status_emoji = "✅" if status == "Completed" else "⏳" if status == "Pending" else "▶️" if status == "Processing" else "❌"
        text += (
            f"#{oid} {status_emoji} *{status}*\n"
            f"📱 {platform} • {sub_service}\n"
            f"🔢 Qty: {qty} | 💰 ₹{price:.2f}\n\n"
        )

    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# ─── WEB APP DATA (order from web app) ────────────────────────
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
                f"❌ *Insufficient Balance!*\n\n"
                f"Required: ₹{price:.2f}\nYour Balance: ₹{bal:.2f}\n\n"
                f"Use 'Add Fund 💰' to top up!",
                parse_mode="Markdown")
            return

        deduct_balance(user_id, price)

        conn = sqlite3.connect("fire_service.db")
        c = conn.cursor()
        c.execute("""INSERT INTO orders
            (user_id,platform,service,sub_service,link,quantity,price,status,created_at)
            VALUES (?,?,?,?,?,?,?,'Pending',?)""",
            (user_id, platform, service, sub_service, link, quantity, price, datetime.now().isoformat()))
        order_id = c.lastrowid
        conn.commit()
        conn.close()

        new_bal = get_balance(user_id)
        user = get_user(user_id)

        bot.send_message(msg.chat.id,
            f"✅ *Order Placed Successfully!*\n\n"
            f"🆔 Order ID: #{order_id}\n"
            f"📱 Platform: {platform}\n"
            f"⚙️ Service: {sub_service}\n"
            f"🔗 Link: `{link}`\n"
            f"🔢 Quantity: {quantity:,}\n"
            f"💰 Price: ₹{price:.2f}\n"
            f"💼 New Balance: ₹{new_bal:.2f}\n"
            f"📊 Status: ⏳ Pending",
            parse_mode="Markdown")

        # Notify admin
        bot.send_message(ADMIN_ID,
            f"📦 *New Order* #{order_id}\n\n"
            f"User: {user[2]} (ID: {user_id})\n"
            f"Platform: {platform} | {sub_service}\n"
            f"Link: {link}\nQty: {quantity:,}\nPrice: ₹{price:.2f}\n\n"
            f"🔄 `/processing {order_id}`\n"
            f"✅ `/complete {order_id}`\n"
            f"❌ `/cancel_order {order_id}`",
            parse_mode="Markdown")

    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Order failed: {str(e)}")

# ─── ADMIN PANEL ───────────────────────────────────────────────
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
    users = get_all_users()
    orders = get_all_orders()
    payments = get_all_payments()

    total_users = len(users)
    total_orders = len(orders)
    pending_orders = sum(1 for o in orders if o[8] == "Pending")
    total_revenue = sum(o[7] for o in orders if o[8] != "Cancelled")
    pending_payments = sum(p[2] for p in payments if p[4] == "Pending")

    text = (
        f"📊 *FIRE SERVICE Stats*\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📦 Total Orders: {total_orders}\n"
        f"⏳ Pending Orders: {pending_orders}\n"
        f"💰 Total Revenue: ₹{total_revenue:.2f}\n"
        f"💳 Pending Payments: ₹{pending_payments:.2f}"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👥 All Users" and is_admin(m))
def all_users(msg):
    users = get_all_users()
    text = f"👥 *All Users ({len(users)}):*\n\n"
    for u in users[:20]:
        text += f"• {u[2]} (ID: {u[0]}) — ₹{u[3]:.2f}\n"
    if len(users) > 20:
        text += f"\n...and {len(users)-20} more"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📦 All Orders" and is_admin(m))
def all_orders_admin(msg):
    orders = get_all_orders()
    if not orders:
        bot.send_message(msg.chat.id, "No orders yet.")
        return
    text = f"📦 *Recent Orders ({len(orders)}):*\n\n"
    for o in orders[:10]:
        text += f"#{o[0]} | {o[2]} | {o[5][:30]}... | ₹{o[7]} | {o[8]}\n"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💳 Payments" and is_admin(m))
def all_payments(msg):
    payments = get_all_payments()
    if not payments:
        bot.send_message(msg.chat.id, "No payments yet.")
        return
    text = "💳 *Pending Payments:*\n\n"
    for p in payments:
        if p[4] == "Pending":
            text += f"#{p[0]} | User:{p[1]} | ₹{p[2]} | UTR:{p[3]}\n"
    bot.send_message(msg.chat.id, text or "No pending payments.", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💸 Withdrawals" and is_admin(m))
def all_withdrawals(msg):
    wds = get_all_withdrawals()
    if not wds:
        bot.send_message(msg.chat.id, "No withdrawals yet.")
        return
    text = "💸 *Pending Withdrawals:*\n\n"
    for w in wds:
        if w[4] == "Pending":
            text += f"#{w[0]} | User:{w[1]} | ₹{w[2]} | UPI:{w[3]}\n"
    bot.send_message(msg.chat.id, text or "No pending withdrawals.", parse_mode="Markdown")

# ─── ADMIN COMMANDS ────────────────────────────────────────────
@bot.message_handler(commands=["approve_pay"])
def approve_pay(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    pay_id = int(parts[1])

    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM payments WHERE id=?", (pay_id,))
    pay = c.fetchone()
    if not pay or pay[4] != "Pending":
        conn.close()
        bot.send_message(msg.chat.id, "❌ Payment not found or already processed.")
        return
    c.execute("UPDATE payments SET status='Approved' WHERE id=?", (pay_id,))
    conn.commit()
    conn.close()

    add_balance(pay[1], pay[2])
    new_bal = get_balance(pay[1])

    bot.send_message(msg.chat.id, f"✅ Payment #{pay_id} approved! ₹{pay[2]} added to user {pay[1]}")
    try:
        bot.send_message(pay[1],
            f"✅ *Payment Approved!*\n\n"
            f"₹{pay[2]} added to your wallet.\n"
            f"💰 New Balance: ₹{new_bal:.2f}",
            parse_mode="Markdown")
    except: pass

@bot.message_handler(commands=["reject_pay"])
def reject_pay(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    pay_id = int(parts[1])

    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM payments WHERE id=?", (pay_id,))
    pay = c.fetchone()
    if not pay:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Payment not found.")
        return
    c.execute("UPDATE payments SET status='Rejected' WHERE id=?", (pay_id,))
    conn.commit()
    conn.close()

    bot.send_message(msg.chat.id, f"❌ Payment #{pay_id} rejected.")
    try:
        bot.send_message(pay[1],
            f"❌ *Payment Rejected!*\n\nUTR: {pay[3]}\nAmount: ₹{pay[2]}\n\nContact support if error.",
            parse_mode="Markdown")
    except: pass

@bot.message_handler(commands=["approve_wd"])
def approve_wd(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    wid = int(parts[1])

    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM withdrawals WHERE id=?", (wid,))
    wd = c.fetchone()
    if not wd:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Withdrawal not found.")
        return
    c.execute("UPDATE withdrawals SET status='Paid' WHERE id=?", (wid,))
    conn.commit()
    conn.close()

    bot.send_message(msg.chat.id, f"✅ Withdrawal #{wid} marked as paid!")
    try:
        bot.send_message(wd[1],
            f"✅ *Withdrawal Paid!*\n\n₹{wd[2]} sent to `{wd[3]}`",
            parse_mode="Markdown")
    except: pass

@bot.message_handler(commands=["reject_wd"])
def reject_wd(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    wid = int(parts[1])

    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM withdrawals WHERE id=?", (wid,))
    wd = c.fetchone()
    if not wd:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Not found.")
        return
    c.execute("UPDATE withdrawals SET status='Rejected' WHERE id=?", (wid,))
    # Refund balance
    conn.commit()
    conn.close()

    add_balance(wd[1], wd[2])
    bot.send_message(msg.chat.id, f"❌ Withdrawal #{wid} rejected. Balance refunded.")
    try:
        bot.send_message(wd[1],
            f"❌ *Withdrawal Rejected*\n\n₹{wd[2]} refunded to your wallet.",
            parse_mode="Markdown")
    except: pass

@bot.message_handler(commands=["complete"])
def complete_order(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    oid = int(parts[1])

    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE id=?", (oid,))
    order = c.fetchone()
    if not order:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Order not found.")
        return
    c.execute("UPDATE orders SET status='Completed' WHERE id=?", (oid,))
    conn.commit()
    conn.close()

    bot.send_message(msg.chat.id, f"✅ Order #{oid} marked as Completed!")
    try:
        bot.send_message(order[1],
            f"✅ *Order Completed!*\n\n"
            f"🆔 Order #{oid}\n"
            f"⚙️ {order[5]}\n"
            f"🔢 Qty: {order[6]:,}",
            parse_mode="Markdown")
    except: pass

@bot.message_handler(commands=["processing"])
def processing_order(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    oid = int(parts[1])
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("UPDATE orders SET status='Processing' WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    bot.send_message(msg.chat.id, f"▶️ Order #{oid} set to Processing!")

@bot.message_handler(commands=["cancel_order"])
def cancel_order(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2: return
    oid = int(parts[1])

    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE id=?", (oid,))
    order = c.fetchone()
    if not order:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Order not found.")
        return
    c.execute("UPDATE orders SET status='Cancelled' WHERE id=?", (oid,))
    conn.commit()
    conn.close()

    # Refund
    add_balance(order[1], order[7])
    bot.send_message(msg.chat.id, f"❌ Order #{oid} cancelled. ₹{order[7]:.2f} refunded.")
    try:
        bot.send_message(order[1],
            f"❌ *Order Cancelled*\n\n"
            f"Order #{oid} cancelled.\n"
            f"₹{order[7]:.2f} refunded to your wallet.",
            parse_mode="Markdown")
    except: pass

# ─── ADD BALANCE MANUALLY ──────────────────────────────────────
@bot.message_handler(commands=["addbal"])
def addbal_cmd(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 3:
        bot.send_message(msg.chat.id, "Usage: /addbal <user_id> <amount>")
        return
    uid = int(parts[1])
    amount = float(parts[2])
    add_balance(uid, amount)
    bot.send_message(msg.chat.id, f"✅ Added ₹{amount} to user {uid}")
    try:
        bot.send_message(uid,
            f"💰 *Balance Added!*\n₹{amount} added to your wallet by admin.",
            parse_mode="Markdown")
    except: pass

# ─── BROADCAST ────────────────────────────────────────────────
broadcast_state = {}

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast" and is_admin(m))
def broadcast_start(msg):
    broadcast_state[msg.from_user.id] = True
    bot.send_message(msg.chat.id, "📢 Send the message to broadcast to all users:")

@bot.message_handler(func=lambda m: broadcast_state.get(m.from_user.id) and is_admin(m))
def broadcast_send(msg):
    broadcast_state.pop(msg.from_user.id, None)
    users = get_all_users()
    sent = 0
    failed = 0
    for u in users:
        try:
            bot.send_message(u[0], f"📢 *Announcement*\n\n{msg.text}", parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
    bot.send_message(msg.chat.id, f"✅ Broadcast done!\nSent: {sent} | Failed: {failed}")

# ─── SERVICES API for Web App ──────────────────────────────────
@bot.message_handler(commands=["services_json"])
def services_json_cmd(msg):
    """Admin can call this to see services JSON"""
    if not is_admin(msg): return
    svc = get_services_json()
    bot.send_message(msg.chat.id, f"```json\n{svc[:3000]}\n```", parse_mode="Markdown")

# ─── MANAGE SERVICES ──────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🛠️ Manage Services" and is_admin(m))
def manage_services(msg):
    services = get_all_services()
    text = "🛠️ *All Services:*\n\nFormat: ID | Platform | Category | Name | Rate/1K\n\n"
    for s in services:
        status = "✅" if s[7] else "❌"
        text += f"{status} #{s[0]} | {s[1]} | {s[3]} | ₹{s[6]}/1K\n"
    text += "\n*Commands:*\n"
    text += "`/edit_service <id> <rate>` — Change rate\n"
    text += "`/toggle_service <id>` — Enable/Disable\n"
    text += "`/add_service <platform> <category> <name> <min> <max> <rate>`"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["edit_service"])
def edit_service(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 3:
        bot.send_message(msg.chat.id, "Usage: /edit_service <id> <new_rate>")
        return
    sid = int(parts[1])
    rate = float(parts[2])
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("UPDATE services SET rate_per_k=? WHERE id=?", (rate, sid))
    conn.commit()
    conn.close()
    bot.send_message(msg.chat.id, f"✅ Service #{sid} rate updated to ₹{rate}/1K")

@bot.message_handler(commands=["toggle_service"])
def toggle_service(msg):
    if not is_admin(msg): return
    parts = msg.text.split()
    if len(parts) != 2:
        bot.send_message(msg.chat.id, "Usage: /toggle_service <id>")
        return
    sid = int(parts[1])
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("SELECT active FROM services WHERE id=?", (sid,))
    row = c.fetchone()
    if not row:
        conn.close()
        bot.send_message(msg.chat.id, "❌ Service not found.")
        return
    new_status = 0 if row[0] == 1 else 1
    c.execute("UPDATE services SET active=? WHERE id=?", (new_status, sid))
    conn.commit()
    conn.close()
    status_text = "enabled ✅" if new_status else "disabled ❌"
    bot.send_message(msg.chat.id, f"Service #{sid} is now {status_text}")

@bot.message_handler(commands=["add_service"])
def add_service_cmd(msg):
    if not is_admin(msg): return
    parts = msg.text.split(maxsplit=7)
    if len(parts) != 8:
        bot.send_message(msg.chat.id,
            "Usage: /add_service <platform> <category> <name> <min> <max> <rate>\n"
            "Example: /add_service Instagram Likes 'Post Likes' 50 500000 2")
        return
    _, platform, category, name, min_q, max_q, rate = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
    conn = sqlite3.connect("fire_service.db")
    c = conn.cursor()
    c.execute("INSERT INTO services (platform,category,name,min_qty,max_qty,rate_per_k) VALUES (?,?,?,?,?,?)",
              (platform, category, name, int(min_q), int(max_q), float(rate)))
    conn.commit()
    conn.close()
    bot.send_message(msg.chat.id, f"✅ Service '{name}' added for {platform}!")

# ─── HELP ─────────────────────────────────────────────────────
@bot.message_handler(commands=["help"])
def help_cmd(msg):
    text = (
        "🔥 *FIRE SERVICE Help*\n\n"
        "📱 *Order Services:* Use the Social Media Service button\n"
        "💰 *Add Fund:* Pay via UPI → send UTR\n"
        "💸 *Withdraw:* `/withdraw <amount> <upi_id>`\n"
        "🎁 *Daily Reward:* Free ₹ every day\n"
        "🤝 *Refer:* Earn ₹5 per referral\n"
        "📋 *Orders:* Check order history\n\n"
        "⚙️ *User Commands:*\n"
        "`/balance` — Check balance\n"
        "`/pay <amount> <UTR>` — Add funds\n"
        "`/withdraw <amount> <upi>` — Withdraw\n\n"
        "Any issue? Contact support."
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# ─── RUN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔥 FIRE SERVICE Bot starting...")
    init_db()
    print(f"✅ Database initialized")
    print(f"✅ Admin ID: {ADMIN_ID}")
    print(f"✅ Web App URL: {WEB_APP_URL}")
    print("🚀 Bot is running!")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
