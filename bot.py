import telebot
import json
import os
import requests
import random
import string
import qrcode
import io
from datetime import datetime, date
from telebot import types

# ============================================================
#  CONFIG
# ============================================================
BOT_TOKEN   = "8752034680:AAFClfX0NwflANlKrcD5WPANd-Hfipw088U"
ADMIN_ID    = 6270522295
ADMIN_TG    = "@contactmonis"
WEB_APP_URL = "https://firesm.netlify.app"

# Firebase Realtime DB
FB_URL = "https://fire-service-20e49-default-rtdb.firebaseio.com"

bot = telebot.TeleBot(BOT_TOKEN)

# ── FIREBASE HELPERS ──────────────────────────────────────────
def fb_get(path):
    r = requests.get(f"{FB_URL}/{path}.json")
    return r.json() if r.status_code == 200 else None

def fb_set(path, data):
    r = requests.put(f"{FB_URL}/{path}.json", json=data)
    return r.json()

def fb_update(path, data):
    r = requests.patch(f"{FB_URL}/{path}.json", json=data)
    return r.json()

def fb_push(path, data):
    r = requests.post(f"{FB_URL}/{path}.json", json=data)
    return r.json()  # returns {"name": "-key"}

def fb_delete(path):
    requests.delete(f"{FB_URL}/{path}.json")

# ── USER HELPERS ──────────────────────────────────────────────
def get_user(user_id):
    return fb_get(f"users/{user_id}")

def get_balance(user_id):
    bal = fb_get(f"users/{user_id}/balance")
    return float(bal) if bal else 0.0

def add_balance(user_id, amount):
    cur = get_balance(user_id)
    fb_update(f"users/{user_id}", {"balance": round(cur + amount, 2)})

def deduct_balance(user_id, amount):
    cur = get_balance(user_id)
    fb_update(f"users/{user_id}", {"balance": round(cur - amount, 2)})

def get_settings():
    s = fb_get("settings") or {}
    return {
        "upi_id":       s.get("upi_id", "monisbhai@fam"),
        "min_withdraw": float(s.get("min_withdraw", 50)),
        "daily_reward": float(s.get("daily_reward", 0.08)),
        "refer_bonus":  float(s.get("refer_bonus", 5))
    }

def create_user(user_id, username, full_name, referred_by=None):
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    data = {
        "user_id":     user_id,
        "username":    username,
        "full_name":   full_name,
        "balance":     0,
        "refer_code":  code,
        "referred_by": referred_by,
        "last_reward": None,
        "joined_at":   datetime.now().isoformat()
    }
    fb_set(f"users/{user_id}", data)
    if referred_by:
        s = get_settings()
        add_balance(referred_by, s["refer_bonus"])
        try:
            bot.send_message(referred_by,
                f"🎉 *Referral Bonus!*\n\nSomeone joined using your link!\n+₹{s['refer_bonus']} added to your wallet!",
                parse_mode="Markdown")
        except: pass

def gen_qr(amount, upi_id):
    upi_url = f"upi://pay?pa={upi_id}&pn=FireService&am={amount:.2f}&cu=INR&tn=FireServiceWallet"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio

# ── KEYBOARDS ─────────────────────────────────────────────────
def main_kb(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(types.KeyboardButton("🛍️ Open Services",
        web_app=types.WebAppInfo(url=f"{WEB_APP_URL}?uid={user_id}")))
    kb.add("💰 Add Fund", "🤝 Refer & Earn")
    kb.add("🎁 Daily Reward", "💼 My Balance")
    kb.add("📋 My Orders", "📞 Support")
    if user_id == ADMIN_ID:
        kb.add("⚙️ Admin Panel")
    return kb

def admin_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("👥 Users", "📦 Orders")
    kb.add("💳 Payments", "💸 Withdrawals")
    kb.add("📊 Stats", "📢 Broadcast")
    kb.add("🔙 Main Menu")
    return kb

def cancel_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("❌ Cancel")
    return kb

# ── /start ────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def start(msg):
    uid  = msg.from_user.id
    uname = msg.from_user.username or ""
    fname = (msg.from_user.first_name or "") + (" " + msg.from_user.last_name if msg.from_user.last_name else "")

    referred_by = None
    parts = msg.text.split()
    if len(parts) > 1:
        all_users = fb_get("users") or {}
        for u in all_users.values():
            if u.get("refer_code") == parts[1] and u.get("user_id") != uid:
                referred_by = u["user_id"]
                break

    existing = get_user(uid)
    if not existing:
        create_user(uid, uname, fname, referred_by)
        bot.send_message(msg.chat.id,
            f"🔥 *Welcome to FIRE SERVICE!*\n\n"
            f"Social media services — Fast & Trusted!\n"
            f"Instagram • YouTube • Telegram • Facebook\n\n"
            f"✅ Account created!\n\n"
            f"❓ Support: {ADMIN_TG}",
            parse_mode="Markdown", reply_markup=main_kb(uid))
        try:
            bot.send_message(ADMIN_ID,
                f"🆕 *New User!*\n\n"
                f"👤 {fname}\n🆔 `{uid}`\n📛 @{uname or 'none'}\n"
                f"🕐 {datetime.now().strftime('%d %b %Y %I:%M %p')}\n"
                f"{'👥 Ref: '+str(referred_by) if referred_by else '🔗 Direct'}",
                parse_mode="Markdown")
        except: pass
    else:
        bal = get_balance(uid)
        bot.send_message(msg.chat.id,
            f"✅ *Welcome back, {fname}!*\n\n💰 Balance: ₹{bal:.2f}",
            parse_mode="Markdown", reply_markup=main_kb(uid))

# ── BALANCE ───────────────────────────────────────────────────
@bot.message_handler(commands=["balance"])
@bot.message_handler(func=lambda m: m.text == "💼 My Balance")
def my_balance(msg):
    uid = msg.from_user.id
    bal = get_balance(uid)
    bot.send_message(msg.chat.id,
        f"💰 *Your Balance*\n\n₹{bal:.2f}",
        parse_mode="Markdown")

# ── SUPPORT ───────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "📞 Support")
def support(msg):
    bot.send_message(msg.chat.id, f"📞 Contact: {ADMIN_TG}")

# ── DAILY REWARD ──────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🎁 Daily Reward")
def daily_reward(msg):
    uid = msg.from_user.id
    user = get_user(uid)
    if not user: return
    s = get_settings()
    today = str(date.today())
    if user.get("last_reward") == today:
        bot.send_message(msg.chat.id, "⏰ Already claimed today! Come back tomorrow 🎁")
        return
    add_balance(uid, s["daily_reward"])
    fb_update(f"users/{uid}", {"last_reward": today})
    new_bal = get_balance(uid)
    bot.send_message(msg.chat.id,
        f"🎉 *Daily Reward Claimed!*\n\n+₹{s['daily_reward']}\n💰 Balance: ₹{new_bal:.2f}",
        parse_mode="Markdown")

# ── REFER ─────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🤝 Refer & Earn")
def refer(msg):
    uid = msg.from_user.id
    user = get_user(uid)
    if not user: return
    s = get_settings()
    me = bot.get_me()
    link = f"https://t.me/{me.username}?start={user['refer_code']}"
    all_users = fb_get("users") or {}
    refs = sum(1 for u in all_users.values() if str(u.get("referred_by")) == str(uid))
    bot.send_message(msg.chat.id,
        f"🤝 *Refer & Earn ₹{s['refer_bonus']} per referral!*\n\n"
        f"Your link:\n`{link}`\n\n👥 Referrals: *{refs}*\n💰 Earned: ₹{refs*s['refer_bonus']:.2f}",
        parse_mode="Markdown")

# ── ADD FUND ──────────────────────────────────────────────────
pay_states = {}

@bot.message_handler(func=lambda m: m.text == "💰 Add Fund")
def add_fund(msg):
    uid = msg.from_user.id
    s = get_settings()
    bot.send_message(msg.chat.id,
        f"💳 *Add Fund*\n\nEnter amount (Min ₹10):",
        parse_mode="Markdown", reply_markup=cancel_kb())
    pay_states[uid] = {"step": "amount"}

@bot.message_handler(func=lambda m: pay_states.get(m.from_user.id, {}).get("step") == "amount")
def fund_amount(msg):
    uid = msg.from_user.id
    if msg.text == "❌ Cancel":
        pay_states.pop(uid, None)
        bot.send_message(msg.chat.id, "❌ Cancelled.", reply_markup=main_kb(uid))
        return
    try:
        amt = float(msg.text.strip())
    except:
        bot.send_message(msg.chat.id, "❌ Invalid! Enter a number:", reply_markup=cancel_kb())
        return
    if amt < 10:
        bot.send_message(msg.chat.id, "❌ Minimum ₹10", reply_markup=cancel_kb())
        return
    s = get_settings()
    upi = s["upi_id"]
    pay_states[uid] = {"step": "screenshot", "amount": amt}
    qr = gen_qr(amt, upi)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📸 Submit Screenshot", "❌ Cancel")
    bot.send_photo(msg.chat.id, qr,
        caption=f"📲 *Pay ₹{amt:.2f} via UPI*\n\n"
                f"UPI ID: `{upi}`\nAmount: ₹{amt:.2f}\n\n"
                f"1️⃣ Scan QR or pay to UPI above\n"
                f"2️⃣ Click *Submit Screenshot*\n"
                f"3️⃣ Send payment photo\n"
                f"4️⃣ Admin verifies & adds balance ✅",
        parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: pay_states.get(m.from_user.id, {}).get("step") == "screenshot")
def fund_ss_prompt(msg):
    uid = msg.from_user.id
    if msg.text == "❌ Cancel":
        pay_states.pop(uid, None)
        bot.send_message(msg.chat.id, "❌ Cancelled.", reply_markup=main_kb(uid))
        return
    if msg.text == "📸 Submit Screenshot":
        bot.send_message(msg.chat.id, "📸 Send your payment screenshot now:",
                        reply_markup=cancel_kb())
        pay_states[uid]["step"] = "photo"

@bot.message_handler(content_types=["photo"],
    func=lambda m: pay_states.get(m.from_user.id, {}).get("step") == "photo")
def fund_photo(msg):
    uid = msg.from_user.id
    state = pay_states.pop(uid, {})
    amt = state.get("amount", 0)
    user = get_user(uid)
    file_id = msg.photo[-1].file_id

    # Save to Firebase
    pay_ref = fb_push("payments", {
        "user_id":    uid,
        "amount":     amt,
        "screenshot": file_id,
        "status":     "Pending",
        "created_at": datetime.now().isoformat()
    })
    pay_id = pay_ref.get("name", "unknown")

    bot.send_message(msg.chat.id,
        f"✅ *Submitted!*\n\n💰 ₹{amt:.2f}\n⏳ Pending approval\n\nSupport: {ADMIN_TG}",
        parse_mode="Markdown", reply_markup=main_kb(uid))

    # Admin notification with inline buttons
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(f"✅ Approve ₹{amt}", callback_data=f"apay|{pay_id}|{uid}|{amt}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"rpay|{pay_id}|{uid}|{amt}")
    )
    try:
        bot.send_photo(ADMIN_ID, file_id,
            caption=f"💳 *New Payment*\n\n"
                    f"👤 {user['full_name'] if user else uid}\n"
                    f"🆔 `{uid}`\n💰 ₹{amt:.2f}\n"
                    f"🕐 {datetime.now().strftime('%d %b %I:%M %p')}",
            parse_mode="Markdown", reply_markup=markup)
    except: pass

# ── CALLBACKS ─────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Not authorized")
        return

    parts = call.data.split("|")
    action = parts[0]

    # Payment approve/reject
    if action == "apay":
        _, pay_id, uid, amt = parts
        uid = int(uid); amt = float(amt)
        fb_update(f"payments/{pay_id}", {"status": "Approved"})
        add_balance(uid, amt)
        new_bal = get_balance(uid)
        bot.answer_callback_query(call.id, f"✅ Approved ₹{amt}")
        bot.edit_message_caption(caption=call.message.caption + "\n\n✅ APPROVED",
            chat_id=call.message.chat.id, message_id=call.message.message_id)
        try:
            bot.send_message(uid,
                f"✅ *Payment Approved!*\n\n₹{amt} added to wallet!\n💰 Balance: ₹{new_bal:.2f}",
                parse_mode="Markdown", reply_markup=main_kb(uid))
        except: pass

    elif action == "rpay":
        _, pay_id, uid, amt = parts
        uid = int(uid); amt = float(amt)
        fb_update(f"payments/{pay_id}", {"status": "Rejected"})
        bot.answer_callback_query(call.id, "❌ Rejected")
        bot.edit_message_caption(caption=call.message.caption + "\n\n❌ REJECTED",
            chat_id=call.message.chat.id, message_id=call.message.message_id)
        try:
            bot.send_message(uid, f"❌ *Payment Rejected*\n\n₹{amt}\nContact {ADMIN_TG}", parse_mode="Markdown")
        except: pass

    # Withdrawal approve/reject
    elif action == "awd":
        _, wd_id, uid, amt, upi = parts
        uid = int(uid); amt = float(amt)
        fb_update(f"withdrawals/{wd_id}", {"status": "Paid"})
        bot.answer_callback_query(call.id, "✅ Marked Paid")
        bot.edit_message_text(call.message.text + "\n\n✅ PAID",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        try:
            bot.send_message(uid, f"✅ *Withdrawal Paid!*\n\n₹{amt} → `{upi}`", parse_mode="Markdown")
        except: pass

    elif action == "rwd":
        _, wd_id, uid, amt, upi = parts
        uid = int(uid); amt = float(amt)
        fb_update(f"withdrawals/{wd_id}", {"status": "Rejected"})
        add_balance(uid, amt)
        bot.answer_callback_query(call.id, "❌ Rejected & Refunded")
        bot.edit_message_text(call.message.text + "\n\n❌ REJECTED — Refunded",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        try:
            bot.send_message(uid, f"❌ *Withdrawal Rejected*\n\n₹{amt} refunded.", parse_mode="Markdown")
        except: pass

    # Order actions
    elif action == "proc":
        _, oid, uid = parts
        fb_update(f"orders/{oid}", {"status": "Processing"})
        bot.answer_callback_query(call.id, "▶️ Processing")
        try:
            bot.send_message(int(uid), "▶️ *Your order is Processing!*", parse_mode="Markdown")
        except: pass

    elif action == "comp":
        _, oid, uid = parts
        fb_update(f"orders/{oid}", {"status": "Completed"})
        bot.answer_callback_query(call.id, "✅ Completed")
        bot.edit_message_text(call.message.text + "\n\n✅ COMPLETED",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        try:
            bot.send_message(int(uid), "✅ *Order Completed!* 🎉", parse_mode="Markdown")
        except: pass

    elif action == "canc":
        _, oid, uid, price = parts
        uid = int(uid); price = float(price)
        fb_update(f"orders/{oid}", {"status": "Cancelled"})
        add_balance(uid, price)
        bot.answer_callback_query(call.id, "❌ Cancelled & Refunded")
        bot.edit_message_text(call.message.text + "\n\n❌ CANCELLED — Refunded",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        try:
            bot.send_message(uid, f"❌ *Order Cancelled*\n\n₹{price} refunded.", parse_mode="Markdown")
        except: pass

# ── WEB APP ORDER ─────────────────────────────────────────────
@bot.message_handler(content_types=["web_app_data"])
def web_order(msg):
    uid = msg.from_user.id
    try:
        data = json.loads(msg.web_app_data.data)
        price = float(data["price"])
        bal = get_balance(uid)
        if bal < price:
            bot.send_message(msg.chat.id, f"❌ Insufficient balance!\nNeed ₹{price:.2f}, have ₹{bal:.2f}")
            return
        deduct_balance(uid, price)
        order_ref = fb_push("orders", {
            "user_id":    uid,
            "platform":   data["platform"],
            "service":    data["service"],
            "link":       data["link"],
            "quantity":   int(data["quantity"]),
            "price":      price,
            "status":     "Pending",
            "created_at": datetime.now().isoformat()
        })
        oid = order_ref.get("name","?")
        new_bal = get_balance(uid)
        user = get_user(uid)
        bot.send_message(msg.chat.id,
            f"✅ *Order Placed!*\n\n🆔 {oid[-6:]}\n📱 {data['platform']} | {data['service']}\n"
            f"🔗 {data['link']}\n🔢 {int(data['quantity']):,}\n💰 ₹{price:.2f}\n"
            f"🏦 Balance: ₹{new_bal:.2f}",
            parse_mode="Markdown")
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("▶️ Processing", callback_data=f"proc|{oid}|{uid}"),
            types.InlineKeyboardButton("✅ Complete", callback_data=f"comp|{oid}|{uid}")
        )
        markup.add(types.InlineKeyboardButton("❌ Cancel+Refund", callback_data=f"canc|{oid}|{uid}|{price}"))
        bot.send_message(ADMIN_ID,
            f"📦 *New Order*\n\n👤 {user['full_name'] if user else uid}\n🆔 `{uid}`\n"
            f"📱 {data['platform']} | {data['service']}\n🔗 {data['link']}\n"
            f"🔢 {int(data['quantity']):,}\n💰 ₹{price:.2f}",
            parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Error: {e}")

# ── WITHDRAW ──────────────────────────────────────────────────
@bot.message_handler(commands=["withdraw"])
def withdraw(msg):
    uid = msg.from_user.id
    s = get_settings()
    parts = msg.text.split()
    if len(parts) != 3:
        bot.send_message(msg.chat.id, f"❌ Format: `/withdraw <amount> <upi_id>`", parse_mode="Markdown")
        return
    try: amt = float(parts[1])
    except:
        bot.send_message(msg.chat.id, "❌ Invalid amount!")
        return
    upi = parts[2]
    bal = get_balance(uid)
    if amt < s["min_withdraw"]:
        bot.send_message(msg.chat.id, f"❌ Minimum ₹{s['min_withdraw']}")
        return
    if bal < amt:
        bot.send_message(msg.chat.id, f"❌ Insufficient! Balance: ₹{bal:.2f}")
        return
    deduct_balance(uid, amt)
    wd_ref = fb_push("withdrawals", {
        "user_id":    uid,
        "amount":     amt,
        "upi_id":     upi,
        "status":     "Pending",
        "created_at": datetime.now().isoformat()
    })
    wid = wd_ref.get("name","?")
    user = get_user(uid)
    bot.send_message(msg.chat.id, f"✅ Withdrawal requested!\n₹{amt} → `{upi}`", parse_mode="Markdown")
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(f"✅ Pay ₹{amt}", callback_data=f"awd|{wid}|{uid}|{amt}|{upi}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"rwd|{wid}|{uid}|{amt}|{upi}")
    )
    bot.send_message(ADMIN_ID,
        f"💸 *Withdrawal*\n\n👤 {user['full_name'] if user else uid}\n🆔 `{uid}`\n💰 ₹{amt}\nUPI: `{upi}`",
        parse_mode="Markdown", reply_markup=markup)

# ── ADMIN: /addbal ────────────────────────────────────────────
@bot.message_handler(commands=["addbal"])
def addbal(msg):
    if msg.from_user.id != ADMIN_ID: return
    parts = msg.text.split()
    if len(parts) != 3:
        bot.send_message(msg.chat.id, "Usage: /addbal <user_id> <amount>")
        return
    uid = int(parts[1]); amt = float(parts[2])
    add_balance(uid, amt)
    new_bal = get_balance(uid)
    bot.send_message(msg.chat.id, f"✅ ₹{amt} added to {uid}\nNew balance: ₹{new_bal:.2f}")
    try:
        bot.send_message(uid,
            f"💰 *Balance Added!*\n\n+₹{amt} by admin\n🏦 Balance: ₹{new_bal:.2f}",
            parse_mode="Markdown", reply_markup=main_kb(uid))
    except: pass

# ── ADMIN PANEL ───────────────────────────────────────────────
def is_admin(m): return m.from_user.id == ADMIN_ID

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel" and is_admin(m))
def admin_panel(msg):
    bot.send_message(msg.chat.id, "⚙️ *Admin Panel*", parse_mode="Markdown", reply_markup=admin_kb())

@bot.message_handler(func=lambda m: m.text == "🔙 Main Menu" and is_admin(m))
def back_main(msg):
    bot.send_message(msg.chat.id, "🏠 Main Menu", reply_markup=main_kb(msg.from_user.id))

@bot.message_handler(func=lambda m: m.text == "📊 Stats" and is_admin(m))
def stats_cmd(msg):
    users = fb_get("users") or {}
    orders = fb_get("orders") or {}
    pays = fb_get("payments") or {}
    ords = list(orders.values())
    rev = sum(o["price"] for o in ords if o.get("status") != "Cancelled")
    pending = sum(1 for o in ords if o.get("status") == "Pending")
    p_pay = sum(p["amount"] for p in pays.values() if p.get("status") == "Pending")
    bot.send_message(msg.chat.id,
        f"📊 *FIRE SERVICE Stats*\n\n"
        f"👥 Users: {len(users)}\n📦 Orders: {len(ords)}\n"
        f"⏳ Pending orders: {pending}\n💰 Revenue: ₹{rev:.2f}\n"
        f"💳 Pending payments: ₹{p_pay:.2f}",
        parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👥 Users" and is_admin(m))
def users_cmd(msg):
    users = fb_get("users") or {}
    if not users:
        bot.send_message(msg.chat.id, "No users yet.")
        return
    text = f"👥 *Users ({len(users)}):*\n\n"
    for u in list(users.values())[:15]:
        text += f"• {u['full_name']} | ₹{u.get('balance',0):.2f}\n  `{u['user_id']}`\n\n"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💳 Payments" and is_admin(m))
def payments_cmd(msg):
    pays = fb_get("payments") or {}
    pending = [(k,v) for k,v in pays.items() if v.get("status") == "Pending"]
    if not pending:
        bot.send_message(msg.chat.id, "✅ No pending payments.")
        return
    for pid, p in pending[:5]:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(f"✅ Approve ₹{p['amount']}", callback_data=f"apay|{pid}|{p['user_id']}|{p['amount']}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rpay|{pid}|{p['user_id']}|{p['amount']}")
        )
        if p.get("screenshot"):
            try:
                bot.send_photo(msg.chat.id, p["screenshot"],
                    caption=f"💳 User: `{p['user_id']}`\nAmount: ₹{p['amount']}",
                    parse_mode="Markdown", reply_markup=markup)
                continue
            except: pass
        bot.send_message(msg.chat.id,
            f"💳 User: `{p['user_id']}`\nAmount: ₹{p['amount']}",
            parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💸 Withdrawals" and is_admin(m))
def wds_cmd(msg):
    wds = fb_get("withdrawals") or {}
    pending = [(k,v) for k,v in wds.items() if v.get("status") == "Pending"]
    if not pending:
        bot.send_message(msg.chat.id, "✅ No pending withdrawals.")
        return
    for wid, w in pending[:5]:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(f"✅ Pay ₹{w['amount']}", callback_data=f"awd|{wid}|{w['user_id']}|{w['amount']}|{w['upi_id']}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rwd|{wid}|{w['user_id']}|{w['amount']}|{w['upi_id']}")
        )
        bot.send_message(msg.chat.id,
            f"💸 User: `{w['user_id']}`\nAmount: ₹{w['amount']}\nUPI: {w['upi_id']}",
            parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📦 Orders" and is_admin(m))
def orders_cmd(msg):
    orders = fb_get("orders") or {}
    ords = list(orders.items())[-10:]
    if not ords:
        bot.send_message(msg.chat.id, "No orders yet.")
        return
    text = "📦 *Recent Orders:*\n\n"
    for oid, o in reversed(ords):
        text += f"• {o['platform']} | {o['service']} | ₹{o['price']} | {o['status']}\n  User: `{o['user_id']}`\n\n"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# Broadcast state
bc_state = {}

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast" and is_admin(m))
def broadcast_start(msg):
    bc_state[msg.from_user.id] = True
    bot.send_message(msg.chat.id, "📢 Send the broadcast message:", reply_markup=cancel_kb())

@bot.message_handler(func=lambda m: bc_state.get(m.from_user.id) and is_admin(m))
def broadcast_send(msg):
    if msg.text == "❌ Cancel":
        bc_state.pop(msg.from_user.id, None)
        bot.send_message(msg.chat.id, "❌ Cancelled.", reply_markup=admin_kb())
        return
    bc_state.pop(msg.from_user.id, None)
    users = fb_get("users") or {}
    sent = failed = 0
    for u in users.values():
        try:
            bot.send_message(u["user_id"], f"📢 *Announcement*\n\n{msg.text}", parse_mode="Markdown")
            sent += 1
        except: failed += 1
    bot.send_message(msg.chat.id, f"✅ Broadcast: {sent} sent, {failed} failed", reply_markup=admin_kb())

# ── MY ORDERS ─────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "📋 My Orders")
def my_orders(msg):
    uid = msg.from_user.id
    orders = fb_get("orders") or {}
    my = [o for o in orders.values() if str(o.get("user_id")) == str(uid)]
    my.sort(key=lambda o: o.get("created_at",""), reverse=True)
    if not my:
        bot.send_message(msg.chat.id, "📭 No orders yet!")
        return
    text = "📋 *Your Orders:*\n\n"
    em = {"Completed":"✅","Pending":"⏳","Processing":"▶️","Cancelled":"❌"}
    for o in my[:10]:
        text += f"{em.get(o['status'],'⏳')} *{o['status']}*\n{o['platform']} • {o['service']}\n₹{o['price']} | {o.get('quantity',0):,}\n\n"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# ── RUN ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔥 FIRE SERVICE Bot starting...")
    print(f"✅ Admin: {ADMIN_ID} | Firebase: fire-service-20e49")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
