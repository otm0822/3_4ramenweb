import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ─── 앱 기본 설정 ───────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# static_folder='.' + static_url_path='' → 루트 경로에서 index.html, images/* 모두 서빙
app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
CORS(app)

# ─── 1) DB 초기화 ───────────────────────────────────────────────
db_path = os.path.join(BASE_DIR, "orders.db")
conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    item      TEXT,
    quantity  INTEGER,
    toppings  TEXT,
    address   TEXT
)
""")
conn.commit()

# ─── 2) 정적 파일 서빙 (index.html) ────────────────────────────
@app.route("/")
def serve_index():
    # BASE_DIR/index.html 리턴
    return send_from_directory(BASE_DIR, "index.html")

# ─── 3) 주문 등록 API ───────────────────────────────────────────
@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO orders (timestamp, item, quantity, toppings, address) VALUES (?, ?, ?, ?, ?)",
        (
            ts,
            data.get("item", ""),
            data.get("quantity", 1),
            ",".join(data.get("toppings", [])),
            data.get("address", "")
        )
    )
    conn.commit()
    return jsonify({"status": "ok"}), 201

# ─── 4) 주문 조회 API ───────────────────────────────────────────
@app.route("/api/orders", methods=["GET"])
def list_orders():
    c.execute(
        "SELECT timestamp, item, quantity, toppings, address "
        "FROM orders ORDER BY id DESC"
    )
    rows = c.fetchall()
    orders = []
    for ts, item, qty, tops, addr in rows:
        orders.append({
            "timestamp": ts,
            "item":      item,
            "quantity":  qty,
            "toppings":  tops.split(",") if tops else [],
            "address":   addr
        })
    return jsonify(orders), 200

# ─── 5) 앱 실행 (개발용) ────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
