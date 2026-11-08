import os, json, logging, time
from contextlib import contextmanager
from sqlalchemy import create_engine, text, event
from sqlalchemy.exc import OperationalError
from fastapi import HTTPException

def database(url):
    if not url.startswith("sqlite:///"):
        raise RuntimeError("This prototype supports SQLite only; PostgreSQL needs transaction adaptation")
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 15})
    @event.listens_for(engine, "connect")
    def pragmas(db, _):
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
    return engine

@contextmanager
def transaction(engine):
    with engine.connect() as c:
        try:
            c.exec_driver_sql("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except OperationalError as exc:
            c.rollback()
            raise HTTPException(503, "Database busy or unavailable; retry same key") from exc
        except BaseException:
            c.rollback()
            raise

def row(c, sql, **params):
    r=c.execute(text(sql), params).mappings().first()
    return dict(r) if r else None

def install_health(app, engine):
    @app.middleware("http")
    async def log_request(request, call_next):
        start=time.monotonic()
        response=await call_next(request)
        logging.getLogger("minishop").warning(json.dumps({"method":request.method,"path":request.url.path,"status":response.status_code,"duration_ms":round((time.monotonic()-start)*1000,2)}))
        return response
    @app.get("/health")
    def health(): return {"status":"alive"}
    @app.get("/ready")
    def ready():
        try:
            with engine.connect() as c: c.execute(text("SELECT 1"))
        except Exception as exc: raise HTTPException(503,"Database unavailable") from exc
        return {"status":"ready"}
