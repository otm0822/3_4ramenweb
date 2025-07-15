import os
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

from sqlalchemy import (
    create_engine, Column, Integer, String,
    Boolean, Text, DateTime, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ─── DB 접속 정보 (하드코딩) ───────────────────────────────────
DB_HOST     = "svc.sel5.cloudtype.app"
DB_PORT     = 31392
DB_USER     = "root"
DB_PASSWORD = "dghs2018!@"
DB_NAME     = "ramen_orders"

# SQLAlchemy + mysql-connector-python
DATABASE_URL = (
    f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4&connection_timeout=10"
)

# ─── SQLAlchemy 기본 세팅 ─────────────────────────────────────
engine       = create_engine(
    DATABASE_URL,
    echo=True,                 # SQL 로그 보기
    pool_pre_ping=True         # 연결 끊김 자동 재시도
)
SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()

# ─── Order 모델 ──────────────────────────────────────────────
class Order(Base):
    __tablename__ = "orders"
    id         = Column(Integer, primary_key=True, index=True)
    timestamp  = Column(DateTime, default=datetime.utcnow, nullable=False)
    item       = Column(String(100), nullable=False)
    quantity   = Column(Integer, nullable=False)
    toppings   = Column(Text)          # "김치,계란"
    deliverer  = Column(String(100))
    address    = Column(Text)
    completed  = Column(Boolean, default=False, nullable=False)
    order_type = Column(Enum("delivery", "dinein", name="order_types"),
                        default="delivery", nullable=False)

# 테이블이 없으면 생성
Base.metadata.create_all(bind=engine)

# 연결 테스트
try:
    with engine.connect() as conn:
        conn.execute("SELECT 1")
    print("✅ DB 연결 성공:", DATABASE_URL)
except Exception as e:
    print("❌ DB 연결 실패:", e)

# ─── Flask 앱 ────────────────────────────────────────────────
app = Flask(__name__, static_folder=os.path.abspath(os.path.dirname(__file__)), static_url_path="")
CORS(app)

SECRET_PASSWORD = "55983200"

def check_auth(password): return password == SECRET_PASSWORD
def authenticate():
    return Response('로그인이 필요합니다.', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})
def requires_auth(f):
    @wraps(f)
    def decorated(*a, **kw):
        auth = request.authorization
        if not auth or not check_auth(auth.password):
            return authenticate()
        return f(*a, **kw)
    return decorated

# ─── 정적 파일 ──────────────────────────────────────────────
@app.route("/")
def index():  return send_from_directory(app.static_folder, "index.html")
@app.route("/admin")
@requires_auth
def admin():  return send_from_directory(app.static_folder, "admin.html")

# ─── API ────────────────────────────────────────────────────
@app.route("/api/orders", methods=["GET"])
def list_orders():
    db = SessionLocal()
    rows = db.query(Order).order_by(Order.id.desc()).all()
    result = [{
        "id": o.id, "timestamp": o.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "item": o.item, "quantity": o.quantity,
        "toppings": o.toppings.split(",") if o.toppings else [],
        "deliverer": o.deliverer, "address": o.address,
        "completed": o.completed, "orderType": o.order_type
    } for o in rows]
    db.close()
    return jsonify(result)

@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json()
    db = SessionLocal()
    order = Order(
        item=data["item"],
        quantity=data["quantity"],
        toppings=",".join(data.get("toppings", [])),
        deliverer=data.get("deliverer", ""),
        address=data.get("address", ""),
        order_type=data.get("orderType", "delivery")
    )
    db.add(order); db.commit(); db.close()
    return jsonify(status="ok"), 201

@app.route("/api/orders/<int:oid>/complete", methods=["POST"])
def complete_order(oid):
    db = SessionLocal()
    o = db.query(Order).get(oid)
    if o: o.completed = True; db.commit()
    db.close(); return jsonify(status="ok")

@app.route("/api/orders/<int:oid>/uncomplete", methods=["POST"])
def uncomplete_order(oid):
    db = SessionLocal()
    o = db.query(Order).get(oid)
    if o: o.completed = False; db.commit()
    db.close(); return jsonify(status="ok")

# ─── 실행 ───────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)