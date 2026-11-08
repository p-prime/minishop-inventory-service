import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
@pytest.fixture
def client(tmp_path):
    with TestClient(create_app('sqlite:///'+str(tmp_path/'test.db'))) as c: yield c

def product(c,stock=10): return c.post('/products',json={'name':'Notebook','stock':stock}).json()['id']
def request(c,p,r='r1',q=3): return c.post('/reservations',json={'reservation_id':r,'items':[{'product_id':p,'quantity':q}]})
def test_create_retrieve_list_stock(client):
    p=product(client)
    assert client.get('/products/'+p).json()['name']=='Notebook'
    assert len(client.get('/products').json())==1
    assert client.get('/products/'+p+'/stock').json()['available']==10

def test_stock_updates(client):
    p=product(client)
    assert client.patch('/products/'+p+'/stock',json={'delta':-4}).json()['stock']==6
    assert client.patch('/products/'+p+'/stock',json={'delta':-7}).status_code==409
    assert client.get('/products/'+p).json()['stock']==6

def test_reservation_duplicate_conflict_release(client):
    p=product(client)
    assert request(client,p).json()['status']=='RESERVED'
    assert request(client,p).json()['status']=='RESERVED'
    assert request(client,p,q=4).status_code==409
    assert client.get('/products/'+p).json()['stock']==7
    assert client.get('/reservations/r1').json()['status']=='RESERVED'
    for _ in range(2): assert client.post('/reservations/r1/release').json()['status']=='RELEASED'
    assert request(client,p).json()['status']=='RELEASED'
    assert client.get('/products/'+p).json()['stock']==10

def test_insufficient_and_atomic_multi_item(client):
    p=product(client); p2=product(client,1)
    r=client.post('/reservations',json={'reservation_id':'multi','items':[{'product_id':p,'quantity':2},{'product_id':p2,'quantity':2}]})
    assert r.json()['status']=='REJECTED'
    assert client.get('/products/'+p).json()['stock']==10
    assert request(client,p,'too-many',20).json()['status']=='REJECTED'

def test_concurrent_no_oversell(client):
    p=product(client)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        outcomes=list(pool.map(lambda i:request(client,p,str(i),1).json()['status'],range(25)))
    assert outcomes.count('RESERVED')==10
    assert outcomes.count('REJECTED')==15
    assert client.get('/products/'+p).json()['stock']==0

def test_concurrent_same_reservation(client):
    p=product(client)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(lambda _:request(client,p).status_code,range(12)))
    assert set(results)=={200}
    assert client.get('/products/'+p).json()['stock']==7

@pytest.mark.parametrize('body',[{'name':'','stock':1},{'name':'X','stock':-1},{'name':'X','stock':True},{'name':'X','stock':1,'other':2}])
def test_invalid_product(client,body): assert client.post('/products',json=body).status_code==422

def test_missing_health(client):
    assert client.get('/products/missing').status_code==404
    assert client.post('/reservations/missing/release').status_code==404
    assert client.get('/health').status_code==200
    assert client.get('/ready').status_code==200
