# server.py  ─────────────────────────────────────────────────────────────
import os
from datetime import datetime
from functools import wraps
from urllib.parse import quote_plus

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

from sqlalchemy import (
    create_engine, Column, Integer, String,
    Boolean, Text, DateTime, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ─── DB 접속 정보 (하드코딩) ─────────────────────────────────────────────
DB_HOST = "svc.sel5.cloudtype.app"
DB_PORT = 31392
DB_USER = "root"
RAW_PW  = "dghs2018!@"          # 특수문자 포함 → URL-인코딩 필요
DB_PW   = quote_plus(RAW_PW)    # => dghs2018%21%40
DB_NAME = "ramen_orders"

DATABASE_URL = (
    f"mysql+mysqlconnector://{DB_USER}:{DB_PW}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"           # 문자셋
)

# ─── SQLAlchemy 엔진 · 세션 · 베이스 ──────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,                  # 연결 끊김 자동 재시도
    connect_args={"collation": "utf8mb4_general_ci"}  # ★ MariaDB용 정렬
)
SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()

# ─── ORM 모델 ────────────────────────────────────────────────────────
class Order(Base):
    __tablename__ = "orders"
    id         = Column(Integer, primary_key=True)
    timestamp  = Column(DateTime, default=datetime.utcnow, nullable=False)
    item       = Column(String(100), nullable=False)
    quantity   = Column(Integer, nullable=False)
    toppings   = Column(Text)                       # "김치,계란"
    deliverer  = Column(String(100))
    address    = Column(Text)
    completed  = Column(Boolean, default=False, nullable=False)
    order_type = Column(Enum("delivery", "dinein", name="order_types"),
                        default="delivery", nullable=False)

Base.metadata.create_all(bind=engine)               # 테이블 없으면 생성

# 연결 테스트
try:
    with engine.connect() as conn:
        conn.execute("SELECT 1")
    print("✅ DB 연결 성공:", DATABASE_URL)
except Exception as e:
    print("❌ DB 연결 실패:", e)

# ─── Flask 애플리케이션 ───────────────────────────────────────────────
app = Flask(__name__,
            static_folder=os.path.abspath(os.path.dirname(__file__)),
            static_url_path="")
CORS(app)

SECRET_PASSWORD = "55983200"

def check_auth(pw): return pw == SECRET_PASSWORD
def authenticate(): return Response('로그인이 필요합니다.', 401,
                                    {'WWW-Authenticate':'Basic realm="Login Required"'})
def requires_auth(f):
    @wraps(f)
    def _wrap(*a, **kw):
        auth = request.authorization
        if not auth or not check_auth(auth.password):
            return authenticate()
        return f(*a, **kw)
    return _wrap

# ─── 정적 파일 ───────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/admin")
@requires_auth
def admin():
    return send_from_directory(app.static_folder, "admin.html")

# ─── API 엔드포인트 ──────────────────────────────────────────────────
@app.route("/api/orders", methods=["GET"])
def list_orders():
    db = SessionLocal()
    rows = db.query(Order).order_by(Order.id.desc()).all()
    data = [{
        "id": o.id,
        "timestamp": o.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "item": o.item, "quantity": o.quantity,
        "toppings": o.toppings.split(",") if o.toppings else [],
        "deliverer": o.deliverer, "address": o.address,
        "completed": o.completed, "orderType": o.order_type
    } for o in rows]
    db.close()
    return jsonify(data)

@app.route("/api/orders", methods=["POST"])
def create_order():
    j = request.get_json()
    db = SessionLocal()
    db.add(Order(
        item=j["item"],
        quantity=j["quantity"],
        toppings=",".join(j.get("toppings", [])),
        deliverer=j.get("deliverer", ""),
        address=j.get("address", ""),
        order_type=j.get("orderType", "delivery")
    ))
    db.commit(); db.close()
    return jsonify(status="ok"), 201

@app.route("/api/orders/<int:oid>/complete", methods=["POST"])
def complete_order(oid):
    db = SessionLocal(); o=db.query(Order).get(oid)
    if o: o.completed=True; db.commit()
    db.close(); return jsonify(status="ok")

@app.route("/api/orders/<int:oid>/uncomplete", methods=["POST"])
def uncomplete_order(oid):
    db = SessionLocal(); o=db.query(Order).get(oid)
    if o: o.completed=False; db.commit()
    db.close(); return jsonify(status="ok")

# ─── 실행 ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)