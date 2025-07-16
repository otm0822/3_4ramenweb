# server.py
import os
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

# ─── 설정 ─────────────────────────────────────────────────────
BASE_DIR        = os.path.abspath(os.path.dirname(__file__))
DB_PATH         = os.path.join(BASE_DIR, "orders.db")
SECRET_PASSWORD = "55983200"

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
CORS(app)

# ─── HTTP Basic Auth 헬퍼 ────────────────────────────────────
def check_auth(password):
    return password == SECRET_PASSWORD

def authenticate():
    return Response(
        '로그인이 필요합니다.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ─── DB 초기화 ───────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
    completed   INTEGER DEFAULT 0,
    order_type  TEXT,
    cooking     INTEGER DEFAULT 0    -- 0:대기, 1:조리중
)
""")
conn.commit()

# ─── 정적 파일 서빙 ───────────────────────────────────────────
@app.route("/")
def serve_index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/admin")
@requires_auth
def serve_admin():
    return send_from_directory(BASE_DIR, "admin.html")

# ─── 주문 조회 ───────────────────────────────────────────────
@app.route("/api/orders", methods=["GET"])
def list_orders():
    c.execute("""
      SELECT id, timestamp, item, quantity, toppings, deliverer, address, completed, order_type, cooking
      FROM orders ORDER BY id DESC
    """)
    rows = c.fetchall()
    orders = []
    for r in rows:
        orders.append({
            "id":         r[0],
            "timestamp":  r[1],
            "item":       r[2],
            "quantity":   r[3],
            "toppings":   r[4].split(",") if r[4] else [],
            "deliverer":  r[5],
            "address":    r[6],
            "completed":  bool(r[7]),
            "orderType":  r[8],
            "cooking":    bool(r[9])
        })
    return jsonify(orders), 200

# ─── 주문 등록 ───────────────────────────────────────────────
@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    toppings  = ",".join(data.get("toppings", []))
    order_type = data.get("orderType", "delivery")
    c.execute("""
      INSERT INTO orders
        (timestamp, item, quantity, toppings, deliverer, address, order_type)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        ts,
        data["item"],
        data["quantity"],
        toppings,
        data.get("deliverer",""),
        data.get("address",""),
        order_type
    ))
    conn.commit()
    return jsonify(status="ok"), 201

# ─── 조리 시작 처리 ───────────────────────────────────────────
@app.route("/api/orders/<int:order_id>/start_cooking", methods=["POST"])
def start_cooking(order_id):
    c.execute("UPDATE orders SET cooking = 1 WHERE id = ?", (order_id,))
    conn.commit()
    return jsonify(status="ok"), 200

# ─── 주문 완료 처리 ───────────────────────────────────────────
@app.route("/api/orders/<int:order_id>/complete", methods=["POST"])
def complete_order(order_id):
    c.execute("UPDATE orders SET completed = 1 WHERE id = ?", (order_id,))
    conn.commit()
    return jsonify(status="ok"), 200

# ─── 주문 완료 취소 ───────────────────────────────────────────
@app.route("/api/orders/<int:order_id>/uncomplete", methods=["POST"])
def uncomplete_order(order_id):
    c.execute("UPDATE orders SET completed = 0 WHERE id = ?", (order_id,))
    conn.commit()
    return jsonify(status="ok"), 200

# ─── 앱 실행 ─────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
