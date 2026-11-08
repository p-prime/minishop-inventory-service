import os, json, uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict, model_validator
from sqlalchemy import text
from .common import database, transaction, row, install_health

class Product(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name: str = Field(min_length=1,max_length=120,pattern=r".*\S.*")
    stock: int = Field(ge=0,le=1000000,strict=True)
class Stock(BaseModel):
    model_config=ConfigDict(extra="forbid")
    delta: int = Field(ge=-1000000,le=1000000,strict=True)
class Item(BaseModel):
    model_config=ConfigDict(extra="forbid")
    product_id: str = Field(min_length=1,max_length=64)
    quantity: int = Field(gt=0,le=1000000,strict=True)
class Reserve(BaseModel):
    model_config=ConfigDict(extra="forbid")
    reservation_id: str = Field(min_length=1,max_length=64)
    items: list[Item] = Field(min_length=1,max_length=50)
    @model_validator(mode="after")
    def unique(self):
        if len({i.product_id for i in self.items})!=len(self.items): raise ValueError("Duplicate product IDs")
        return self

def create_app(url=None):
    app=FastAPI(title="MiniShop Inventory",version="1.0.0")
    e=database(url or os.getenv("DATABASE_URL","sqlite:///inventory.db"))
    app.state.engine=e
    with e.begin() as c:
        for sql in ["CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, name TEXT NOT NULL, stock INTEGER NOT NULL CHECK(stock>=0))", "CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('RESERVED','REJECTED','RELEASED')))" ]: c.execute(text(sql))
    install_health(app,e)
    @app.post("/products",status_code=201)
    def create(p:Product):
        pid=str(uuid.uuid4())
        with transaction(e) as c: c.execute(text("INSERT INTO products VALUES (:id,:name,:stock)"),dict(id=pid,**p.model_dump()))
        return dict(id=pid,**p.model_dump())
    @app.get("/products")
    def products():
        with e.connect() as c: return [dict(r) for r in c.execute(text("SELECT * FROM products ORDER BY id")).mappings()]
    @app.get("/products/{pid}")
    def product(pid:str):
        with e.connect() as c: p=row(c,"SELECT * FROM products WHERE id=:id",id=pid)
        if not p: raise HTTPException(404,"Product not found")
        return p
    @app.get("/products/{pid}/stock")
    def stock(pid:str): return dict(product_id=pid,available=product(pid)['stock'])
    @app.patch("/products/{pid}/stock")
    def update_stock(pid:str,body:Stock):
        with transaction(e) as c:
            if not row(c,"SELECT id FROM products WHERE id=:id",id=pid): raise HTTPException(404,"Product not found")
            changed=c.execute(text("UPDATE products SET stock=stock+:d WHERE id=:id AND stock+:d>=0"),dict(d=body.delta,id=pid)).rowcount
            if not changed: raise HTTPException(409,"Stock would be negative")
            return row(c,"SELECT * FROM products WHERE id=:id",id=pid)
    @app.post("/reservations")
    def reserve(body:Reserve):
        payload=json.dumps(sorted([i.model_dump() for i in body.items],key=lambda i:i['product_id']),sort_keys=True)
        with transaction(e) as c:
            old=row(c,"SELECT * FROM reservations WHERE id=:id",id=body.reservation_id)
            if old:
                if old['payload']!=payload: raise HTTPException(409,"Reservation ID reused with different items")
                return dict(id=old['id'],status=old['status'])
            # Pre-check under an immediate write transaction. No writer can interleave.
            valid=all((p:=row(c,"SELECT stock FROM products WHERE id=:id",id=i.product_id)) is not None and p['stock']>=i.quantity for i in body.items)
            state="RESERVED" if valid else "REJECTED"
            if valid:
                for i in body.items:
                    changed=c.execute(text("UPDATE products SET stock=stock-:q WHERE id=:id AND stock>=:q"),dict(q=i.quantity,id=i.product_id)).rowcount
                    if changed!=1: raise RuntimeError("Atomic stock invariant violated")
            c.execute(text("INSERT INTO reservations VALUES (:id,:payload,:status)"),dict(id=body.reservation_id,payload=payload,status=state))
        return dict(id=body.reservation_id,status=state)
    @app.get("/reservations/{rid}")
    def reservation(rid:str):
        with e.connect() as c: r=row(c,"SELECT * FROM reservations WHERE id=:id",id=rid)
        if not r: raise HTTPException(404,"Reservation not found")
        return dict(id=r['id'],status=r['status'],items=json.loads(r['payload']))
    @app.post("/reservations/{rid}/release")
    def release(rid:str):
        with transaction(e) as c:
            r=row(c,"SELECT * FROM reservations WHERE id=:id",id=rid)
            if not r: raise HTTPException(404,"Reservation not found")
            if r['status']=="RESERVED":
                for i in json.loads(r['payload']): c.execute(text("UPDATE products SET stock=stock+:q WHERE id=:id"),dict(q=i['quantity'],id=i['product_id']))
                c.execute(text("UPDATE reservations SET status='RELEASED' WHERE id=:id"),dict(id=rid))
                r['status']='RELEASED'
        return dict(id=rid,status=r['status'])
    return app
app=create_app()
