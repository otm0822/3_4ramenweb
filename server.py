from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)  # 클라이언트(브라우저)에서 호출 허용

# 1) DB 초기화 (orders 테이블)
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
)""")
conn.commit()

# 2) 주문 등록 엔드포인트
@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO orders (timestamp,item,quantity,toppings,address) VALUES (?,?,?,?,?)",
        (ts, data["item"], data["quantity"], ",".join(data["toppings"]), data["address"])
    )
    conn.commit()
    return jsonify({"status":"ok"}), 201

# 3) 주문 조회 엔드포인트
@app.route("/api/orders", methods=["GET"])
def list_orders():
    c.execute("SELECT timestamp,item,quantity,toppings,address FROM orders ORDER BY id DESC")
    rows = c.fetchall()
    orders = [
        {"timestamp":r[0], "item":r[1], "quantity":r[2], "toppings":r[3], "address":r[4]}
        for r in rows
    ]
    return jsonify(orders)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
