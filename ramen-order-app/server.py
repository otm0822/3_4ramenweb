from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

# ─── Flask 앱 생성: static_folder='.' 로 지정하고, static_url_path='' 으로 루트에서 바로 서빙
app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)  # 브라우저 CORS 허용

# ─── 1) DB 초기화 (orders 테이블)
conn = sqlite3.connect("orders.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    item TEXT,
    quantity INTEGER,
    toppings TEXT,
    address TEXT
)
""")
conn.commit()

# ─── 2) 정적 파일 서빙 (index.html)
@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

# ─── 3) 주문 등록 엔드포인트
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

# ─── 4) 주문 조회 엔드포인트
@app.route("/api/orders", methods=["GET"])
def list_orders():
    c.execute(
        "SELECT timestamp, item, quantity, toppings, address "
        "FROM orders ORDER BY id DESC"
    )
    rows = c.fetchall()
    orders = [
        {
            "timestamp": r[0],
            "item":      r[1],
            "quantity":  r[2],
            "toppings":  r[3].split(",") if r[3] else [],
            "address":   r[4]
        }
        for r in rows
    ]
    return jsonify(orders), 200

# ─── 5) 앱 실행 (Railway 등 PaaS의 PORT 환경변수 사용)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
