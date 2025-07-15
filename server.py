# server.py
import os, sys
from datetime import datetime
from functools import wraps
from urllib.parse import quote_plus

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean,
    Text, DateTime, Enum, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# ─── DB 접속 정보 ─────────────────────────────────────────────
DB_HOST = "svc.sel5.cloudtype.app"; DB_PORT = 31392
DB_USER = "root"; RAW_PW = "dghs2018!@"; DB_NAME = "ramen_orders"
DB_PW   = quote_plus(RAW_PW)

DATABASE_URL = (
    f"mysql+mysqlconnector://{DB_USER}:{DB_PW}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

# ─── SQLAlchemy ─────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    echo=True,                   # SQL문 그대로 표준출력
    pool_pre_ping=True,
    connect_args={"collation": "utf8mb4_general_ci"}  # MariaDB용
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# flush 단계마다 어떤 객체를 INSERT/UPDATE 하는지 로그
@event.listens_for(Session, "after_flush")
def _after_flush(sess, ctx):
    for o in sess.new:     print(f"[SQLA] INSERT 예정 → {o!r}", file=sys.stderr)
    for o in sess.dirty:   print(f"[SQLA] UPDATE 예정 → {o!r}", file=sys.stderr)
    for o in sess.deleted: print(f"[SQLA] DELETE 예정 → {o!r}", file=sys.stderr)

class Order(Base):
    __tablename__ = "orders"
    id         = Column(Integer, primary_key=True)
    timestamp  = Column(DateTime, default=datetime.utcnow, nullable=False)
    item       = Column(String(100), nullable=False)
    quantity   = Column(Integer, nullable=False)
    toppings   = Column(Text)
    deliverer  = Column(String(100))
    address    = Column(Text)
    completed  = Column(Boolean, default=False, nullable=False)
    order_type = Column(Enum("delivery","dinein", name="order_types"),
                        default="delivery", nullable=False)
    def __repr__(self):
        return f"<Order id={self.id} {self.item}×{self.quantity}>"

Base.metadata.create_all(bind=engine)

# ─── Flask ──────────────────────────────────────────────────
app = Flask(__name__,
            static_folder=os.path.abspath(os.path.dirname(__file__)),
            static_url_path="")
CORS(app)

SECRET_PASSWORD = "55983200"
def _auth(p): return p == SECRET_PASSWORD
def _need(): return Response('로그인이 필요합니다.', 401,
                              {'WWW-Authenticate':'Basic realm="Login Required"'})
def requires_auth(f):
    @wraps(f)
    def _wrap(*a, **kw):
        auth = request.authorization
        if not auth or not _auth(auth.password):
            return _need()
        return f(*a, **kw)
    return _wrap

@app.route("/")
def idx(): return send_from_directory(app.static_folder, "index.html")
@app.route("/admin"); @requires_auth
def adm(): return send_from_directory(app.static_folder, "admin.html")

# ─── API ────────────────────────────────────────────────────
@app.route("/api/orders", methods=["GET"])
def list_orders():
    db = SessionLocal()
    data = [{
        "id":o.id,"timestamp":o.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "item":o.item,"quantity":o.quantity,
        "toppings":o.toppings.split(",") if o.toppings else [],
        "deliverer":o.deliverer,"address":o.address,
        "completed":o.completed,"orderType":o.order_type
    } for o in db.query(Order).order_by(Order.id.desc())]
    db.close(); return jsonify(data)

@app.route("/api/orders", methods=["POST"])
def create_order():
    j = request.get_json()
    db = SessionLocal()
    o = Order(
        item=j["item"], quantity=j["quantity"],
        toppings=",".join(j.get("toppings", [])),
        deliverer=j.get("deliverer",""), address=j.get("address",""),
        order_type=j.get("orderType","delivery")
    )
    db.add(o)
    try:
        db.commit()
        print(f"[COMMIT] 새 주문 id={o.id}", file=sys.stderr)
    except Exception as e:
        db.rollback(); print("!!! COMMIT ERROR:", e, file=sys.stderr); raise
    finally:
        db.close()
    return jsonify(status="ok"), 201

@app.route("/api/orders/<int:oid>/complete", methods=["POST"])
def complete_order(oid):
    db=SessionLocal(); o=db.query(Order).get(oid)
    if o: o.completed=True; db.commit(); print(f"[COMMIT] 완료 id={oid}", file=sys.stderr)
    db.close(); return jsonify(status="ok")
@app.route("/api/orders/<int:oid>/uncomplete", methods=["POST"])
def uncomplete_order(oid):
    db=SessionLocal(); o=db.query(Order).get(oid)
    if o: o.completed=False; db.commit(); print(f"[COMMIT] 취소 id={oid}", file=sys.stderr)
    db.close(); return jsonify(status="ok")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)