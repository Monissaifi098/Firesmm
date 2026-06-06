"""
FIRE SERVICE — Flask API Server
Serves: Web App (index.html) + API endpoints for Bot
Deploy on Render as a Web Service
"""

from flask import Flask, jsonify, request, send_from_directory
import sqlite3
import os
import json
from datetime import datetime

app = Flask(__name__, static_folder=".")

DB_PATH = "fire_service.db"

# ─── DB HELPERS ───────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ─── STATIC FILE ──────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# ─── API: BALANCE ─────────────────────────────────────────────
@app.route("/api/balance")
def api_balance():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"balance": 0})
    conn = get_db()
    user = conn.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    return jsonify({"balance": user["balance"] if user else 0})

# ─── API: SERVICES ────────────────────────────────────────────
@app.route("/api/services")
def api_services():
    conn = get_db()
    rows = conn.execute("SELECT * FROM services WHERE active=1").fetchall()
    conn.close()

    result = {}
    for s in rows:
        platform = s["platform"]
        category = s["category"]
        if platform not in result:
            result[platform] = {}
        if category not in result[platform]:
            result[platform][category] = []
        result[platform][category].append({
            "id":   s["id"],
            "name": s["name"],
            "min":  s["min_qty"],
            "max":  s["max_qty"],
            "rate": s["rate_per_k"]
        })
    return jsonify(result)

# ─── API: ORDERS (user) ───────────────────────────────────────
@app.route("/api/orders")
def api_orders():
    uid = request.args.get("uid")
    if not uid:
        return jsonify([])
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (uid,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ─── API: PLACE ORDER ─────────────────────────────────────────
@app.route("/api/order", methods=["POST"])
def api_place_order():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"})

    user_id    = data.get("user_id")
    platform   = data.get("platform")
    service    = data.get("service")
    sub_service = data.get("sub_service")
    link       = data.get("link")
    quantity   = data.get("quantity")
    price      = data.get("price")

    if not all([user_id, platform, link, quantity, price]):
        return jsonify({"success": False, "error": "Missing fields"})

    conn = get_db()
    user = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()

    if not user:
        conn.close()
        return jsonify({"success": False, "error": "User not found"})

    if user["balance"] < float(price):
        conn.close()
        return jsonify({"success": False, "error": "Insufficient balance"})

    # Deduct balance and create order
    conn.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (price, user_id))
    conn.execute("""
        INSERT INTO orders (user_id,platform,service,sub_service,link,quantity,price,status,created_at)
        VALUES (?,?,?,?,?,?,?,'Pending',?)
    """, (user_id, platform, service, sub_service, link, quantity, price, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

# ─── HEALTH CHECK ─────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "Fire Service"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
