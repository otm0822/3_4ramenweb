# server.py
import os
import sys
from datetime import datetime
from functools import wraps
from urllib.parse import quote_plus, urlencode

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

from sqlalchemy import (
    create_engine, Column, Integer, String, Text,
    Boolean, DateTime, Enum, event, inspect, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ───────────────────── 1. DB 설정 ──────────────────────────
DB_HOST = "svc.sel5.cloudtype.app"
DB_PORT = 31392
DB_USER = "root"
RAW_PW  = "dghs2018!@"
DB_PW   = quote_plus(RAW_PW)  # 암호에 특수문자 있을 때 안전하게 인코딩
DB_NAME = "ramen_orders"
_q      = urlencode({"charset": "utf8mb4"})

# 1-1) 데이터베이스가 없으면 생성 (bootstrap_engine)
bootstrap_engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PW}@{DB_HOST}:{DB_PORT}/?{_q}",
    pool_pre_ping=True,
)
with bootstrap_engine.connect() as conn:
    conn.execute(
        text(f"""
            CREATE DATABASE IF NOT EXISTS `{DB_NAME}`
            DEFAULT CHARACTER SET utf8mb4
            COLLATE utf8mb4_general_ci
        """)
    )

# 1-2) 실제 사용 엔진
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PW}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?{_q}"
)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    encoding="utf8mb4",
)

# 1-3) 연결 시마다 문자셋 강제 적용
@event.listens_for(engine, "connect")
def _set_charset(conn, _):
    with conn.cursor() as cur:
        cur.execute("SET NAMES utf8mb4 COLLATE utf8mb4_general_ci")

# 세션과 베이스 준비
SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()

# ───────────────────── 2. ORM 모델 ─────────────────────────
class Order(Base):
    __tablename__ = "orders"

    id         = Column(Integer, primary_key=True, index=True)
    timestamp  = Column(DateTime, default=datetime.utcnow, nullable=False)
    item       = Column(String(100), nullable=False)
    quantity   = Column(Integer, nullable=False)
    toppings   = Column(Text)                      # "김치,계란"
    deliverer  = Column(String(100))
    address    = Column(Text)
    completed  = Column(Boolean, default=False, nullable=False)
    order_type = Column(
        Enum("delivery", "dinein", name="order_types"),
        default="delivery", nullable=False
    )

# ─── 테이블 덮어쓰기: 있으면 DROP → CREATE ───────────────────
if inspect(engine).has_table(Order.__tablename__):
    Base.metadata.drop_all(bind=engine, tables=[Order.__table__])
Base.metadata.create_all(bind=engine)

# ───────────────────── 3. Flask 설정 ───────────────────────
app = Flask(
    __name__,
    static_folder=os.path.abspath(os.path.dirname(__file__)),
    static_url_path=""
)
CORS(app)

# ─── 간단한 Basic-Auth (admin 보호) ─────────────────────────
ADMIN_PASS = "55983200"
def _need_auth():
    return Response(
        "인증 필요", 401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )

def requires_auth(fn):
    @wraps(fn)
    def _wrap(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.password != ADMIN_PASS:
            return _need_auth()
        return fn(*args, **kwargs)
    return _wrap

# ───────────────────── 4. 정적 파일 서빙 ────────────────────
@app.route("/")
def index():  # 고객 화면
    return send_from_directory(app.static_folder, "index.html")

@app.route("/admin")
@requires_auth
def admin():  # 관리자 화면
    return send_from_directory(app.static_folder, "admin.html")

# ───────────────────── 5. REST API ─────────────────────────
@app.route("/api/orders", methods=["GET"])
def list_orders():
    db: Session = SessionLocal()
    rows = db.query(Order).order_by(Order.id.desc()).all()
    result = [
        {
            "id":        o.id,
            "timestamp": o.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "item":      o.item,
            "quantity":  o.quantity,
            "toppings":  o.toppings.split(",") if o.toppings else [],
            "deliverer": o.deliverer,
            "address":   o.address,
            "completed": o.completed,
            "orderType": o.order_type,
        }
        for o in rows
    ]
    db.close()
    return jsonify(result), 200

@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(force=True)
    new = Order(
        item       = data["item"],
        quantity   = data["quantity"],
        toppings   = ",".join(data.get("toppings", [])),
        deliverer  = data.get("deliverer", ""),
        address    = data.get("address", ""),
        order_type = data.get("orderType", "delivery"),
    )
    db: Session = SessionLocal()
    db.add(new)
    try:
        db.commit()
        print(f"[DB] INSERT id={new.id}", file=sys.stderr)
    except Exception as e:
        db.rollback()
        print("DB ERROR:", e, file=sys.stderr)
        return jsonify(error=str(e)), 500
    finally:
        db.close()
    return jsonify(status="ok"), 201

@app.route("/api/orders/<int:oid>/complete", methods=["POST"])
def complete_order(oid):
    db: Session = SessionLocal()
    row = db.get(Order, oid)
    if row:
        row.completed = True
        db.commit()
        print(f"[DB] COMPLETE id={oid}", file=sys.stderr)
    db.close()
    return jsonify(status="ok"), 200

@app.route("/api/orders/<int:oid>/uncomplete", methods=["POST"])
def uncomplete_order(oid):
    db: Session = SessionLocal()
    row = db.get(Order, oid)
    if row:
        row.completed = False
        db.commit()
        print(f"[DB] UNCOMPLETE id={oid}", file=sys.stderr)
    db.close()
    return jsonify(status="ok"), 200

# ───────────────────── 6. 서버 실행 ───────────────────────────
if __name__ == "__main__":
    # Cloudtype 헬스체크가 5000번 포트로만 오기 때문에, 고정으로 5000번 바인딩합니다.
    app.run(host="0.0.0.0", port=5000)
