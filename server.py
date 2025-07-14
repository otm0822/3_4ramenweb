from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, os
from datetime import datetime

# ─── 앱 설정 ──────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "orders.db")

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
CORS(app)

# ─── DB 초기화 ─────────────────────────────────
conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT,
    item        TEXT,
    quantity    INTEGER,
    toppings    TEXT,
    deliverer   TEXT,
    address     TEXT,
    completed   INTEGER DEFAULT 0
)
""")
conn.commit()

# ─── 정적 파일 서빙 ─────────────────────────────
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

# ─── 주문 등록 ───────────────────────────────────
@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO orders (timestamp,item,quantity,toppings,deliverer,address) VALUES (?,?,?,?,?,?)",
        (
            ts,
            data["item"],
            data["quantity"],
            ",".join(data["toppings"]),
            data["deliverer"],
            data["address"]
        )
    )
    conn.commit()
    return jsonify(status="ok"), 201

# ─── 주문 조회 ───────────────────────────────────
@app.route("/api/orders", methods=["GET"])
def list_orders():
    c.execute(
        "SELECT id,timestamp,item,quantity,toppings,deliverer,address,completed "
        "FROM orders ORDER BY id DESC"
    )
    rows = c.fetchall()
    orders = []
    for r in rows:
        orders.append({
            "id":        r[0],
            "timestamp": r[1],
            "item":      r[2],
            "quantity":  r[3],
            "toppings":  r[4].split(",") if r[4] else [],
            "deliverer": r[5],
            "address":   r[6],
            "completed": bool(r[7])
        })
    return jsonify(orders)

# ─── 주문 완료 처리 ───────────────────────────────
@app.route("/api/orders/<int:order_id>/complete", methods=["POST"])
def complete_order(order_id):
    c.execute("UPDATE orders SET completed=1 WHERE id=?", (order_id,))
    conn.commit()
    return jsonify(status="ok")

# ─── 앱 실행 ─────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
