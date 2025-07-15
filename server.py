# server.py
import os
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, Text, DateTime, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ─── 설정 ─────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SECRET_PASSWORD = "55983200"

# MySQL(MariaDB) 연결 정보
#  svc.sel5.cloudtype.app:31392, 비밀번호 dghs2018!@
DATABASE_URL = (
    "mysql+pymysql://root:dghs2018!@"
    "svc.sel5.cloudtype.app:31392/ramen_orders"
    "?charset=utf8mb4"
)

# ─── SQLAlchemy 엔진 · 세션 생성 ────────────────────────────────
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ─── ORM 모델 정의 ─────────────────────────────────────────────
class Order(Base):
    __tablename__ = "orders"

    id         = Column(Integer, primary_key=True, index=True)
    timestamp  = Column(DateTime, nullable=False, default=datetime.utcnow)
    item       = Column(String(100), nullable=False)
    quantity   = Column(Integer, nullable=False)
    toppings   = Column(Text)                           # CSV: "김치,계란"
    deliverer  = Column(String(100))
    address    = Column(Text)
    completed  = Column(Boolean, default=False, nullable=False)
    order_type = Column(Enum('delivery','dinein', name="order_types"),
                        nullable=False, default='delivery')

# 테이블이 없으면 생성
Base.metadata.create_all(bind=engine)

# ─── Flask 앱 설정 ───────────────────────────────────────────
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
    db = SessionLocal()
    orders = db.query(Order).order_by(Order.id.desc()).all()
    result = []
    for o in orders:
        result.append({
            "id":        o.id,
            "timestamp": o.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "item":      o.item,
            "quantity":  o.quantity,
            "toppings":  o.toppings.split(",") if o.toppings else [],
            "deliverer": o.deliverer,
            "address":   o.address,
            "completed": o.completed,
            "orderType": o.order_type
        })
    db.close()
    return jsonify(result), 200

# ─── 주문 등록 ───────────────────────────────────────────────
@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json()
    db = SessionLocal()
    toppings_csv = ",".join(data.get("toppings", []))
    new_order = Order(
        timestamp  = datetime.now(),
        item       = data["item"],
        quantity   = data["quantity"],
        toppings   = toppings_csv,
        deliverer  = data.get("deliverer", ""),
        address    = data.get("address", ""),
        order_type = data.get("orderType", "delivery")
    )
    db.add(new_order)
    db.commit()
    db.close()
    return jsonify(status="ok"), 201

# ─── 주문 완료 처리 ───────────────────────────────────────────
@app.route("/api/orders/<int:order_id>/complete", methods=["POST"])
def complete_order(order_id):
    db = SessionLocal()
    o = db.query(Order).get(order_id)
    if o:
        o.completed = True
        db.commit()
    db.close()
    return jsonify(status="ok"), 200

# ─── 주문 완료 취소 ───────────────────────────────────────────
@app.route("/api/orders/<int:order_id>/uncomplete", methods=["POST"])
def uncomplete_order(order_id):
    db = SessionLocal()
    o = db.query(Order).get(order_id)
    if o:
        o.completed = False
        db.commit()
    db.close()
    return jsonify(status="ok"), 200

# ─── 서버 실행 ───────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
