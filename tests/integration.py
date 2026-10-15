"""Integration checks against real PostgreSQL; isolated test rows are removed."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import re
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
import psycopg
from werkzeug.security import generate_password_hash
from app import app, connect, record_movement

prefix='test-'+uuid.uuid4().hex[:12]
password=secrets.token_urlsafe(24)
created=[]
cat_id=user_id=None
checks=0
app.config['TESTING']=True
client=app.test_client()
BASE='https://localhost'


def check(condition,label):
    global checks
    if not condition: raise AssertionError(label)
    checks+=1
    print('PASS: '+label,flush=True)


def token(path):
    response=client.get(path,base_url=BASE)
    check(response.status_code==200,'page available: '+path)
    return re.search(r'name="csrf_token" value="([^"]+)"',response.text).group(1)


def post(path,fields,follow=False):
    fields={'csrf_token':token(path),**fields}
    return client.post(path,data=fields,base_url=BASE,headers={'Referer':BASE+path},follow_redirects=follow)


def quantity(pid):
    with connect() as db:
        return db.execute('SELECT quantity FROM products WHERE id=%s',(pid,)).fetchone()['quantity']


try:
    with connect() as db:
        user_id=db.execute('INSERT INTO users(username,password_hash) VALUES (%s,%s) RETURNING id',(prefix,generate_password_hash(password))).fetchone()['id']
    check(client.get('/',base_url=BASE).status_code==302,'anonymous inventory access requires login')
    check(client.post('/login',data={'username':prefix,'password':password},base_url=BASE).status_code==400,'missing CSRF token rejected')
    check(post('/login',{'username':prefix,'password':'wrong'}).status_code==401,'wrong password rejected')
    response=post('/login',{'username':prefix,'password':password})
    check(response.status_code==302,'correct password accepted')
    check('HttpOnly' in response.headers.get('Set-Cookie','') and 'SameSite=Lax' in response.headers.get('Set-Cookie',''),'session cookie has HttpOnly and SameSite')
    post('/categories',{'name':prefix})
    with connect() as db:
        cat_id=db.execute('SELECT id FROM categories WHERE name=%s',(prefix,)).fetchone()['id']
    check(cat_id is not None,'category created through protected form')
    values={'sku':prefix,'name':'<script>alert(1)</script> Test product','price':'12.50','category_id':cat_id,'low_stock_threshold':'5'}
    check(post('/products/new',{**values,'price':'-1'}).status_code==400,'negative price rejected')
    check(post('/products/new',{**values,'price':'NaN'}).status_code==400,'non-finite price rejected')
    response=post('/products/new',values)
    check(response.status_code==302,'product created through form')
    pid=int(response.location.rsplit('/',1)[-1]); created.append(pid)
    check(post('/products/new',values).status_code==400,'duplicate SKU rejected')
    response=client.get('/products/'+str(pid),base_url=BASE)
    check('<script>alert(1)</script>' not in response.text and '&lt;script&gt;' in response.text,'product name is HTML escaped')
    check(response.headers.get('X-Frame-Options')=='DENY','security response headers present')
    def movement(kind,n,rid=None):
        return post('/products/'+str(pid),{'kind':kind,'quantity':str(n),'note':'Integration test','request_id':rid or str(uuid.uuid4())},True)
    movement('receive',10); check(quantity(pid)==10,'receipt: 0 + 10 = 10')
    movement('sale',2); check(quantity(pid)==8,'sale: 10 - 2 = 8')
    movement('receive',5); check(quantity(pid)==13,'receipt: 8 + 5 = 13')
    with connect() as db: before=db.execute('SELECT count(*) AS n FROM movements WHERE product_id=%s',(pid,)).fetchone()['n']
    response=movement('sale',99)
    with connect() as db: after=db.execute('SELECT count(*) AS n FROM movements WHERE product_id=%s',(pid,)).fetchone()['n']
    check(quantity(pid)==13 and before==after and 'Not enough stock' in response.text,'overselling rejected without partial movement')
    rid=str(uuid.uuid4()); movement('receive',1,rid); movement('receive',1,rid)
    check(quantity(pid)==14,'duplicate form submission changes stock only once')
    movement('receive',0); check(quantity(pid)==14,'zero movement quantity rejected')
    record_movement(pid,user_id,'sale',13,'Prepare concurrent sale test',uuid.uuid4())
    def competing_sale(_):
        try:
            return record_movement(pid,user_id,'sale',1,'Concurrent sale',uuid.uuid4())
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(competing_sale,range(2)))
    check(sum(results)==1 and quantity(pid)==0,'two simultaneous sales of final unit: exactly one succeeds')
    record_movement(pid,user_id,'receive',5,'Prepare duplicate concurrency',uuid.uuid4())
    shared=uuid.uuid4()
    def duplicate_sale(_):
        try: return record_movement(pid,user_id,'sale',1,'Duplicate concurrent submission',shared)
        except psycopg.errors.UniqueViolation: return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(duplicate_sale,range(2)))
    check(sum(results)==1 and quantity(pid)==4,'concurrent duplicate request rolls back extra stock update')
    response=client.get('/?low=1&q='+prefix,base_url=BASE)
    check(prefix.upper() in response.text,'low-stock filter finds below-threshold product')
    check(client.get('/movements',base_url=BASE).status_code==200,'movement history renders')
    check(client.get('/health',base_url=BASE).json['database']=='ok','health endpoint checks database')
    client.post('/logout',data={'csrf_token':token('/')},base_url=BASE,headers={'Referer':BASE+'/'})
    check(client.get('/',base_url=BASE).status_code==302,'logout removes inventory access')
    print(f'\nALL {checks} CHECKS PASSED',flush=True)
finally:
    with connect() as db:
        if cat_id:
            db.execute('DELETE FROM movements WHERE product_id IN (SELECT id FROM products WHERE category_id=%s)',(cat_id,))
            db.execute('DELETE FROM products WHERE category_id=%s',(cat_id,))
            db.execute('DELETE FROM categories WHERE id=%s',(cat_id,))
        db.execute('DELETE FROM login_attempts WHERE username=%s',(prefix,))
        if user_id: db.execute('DELETE FROM users WHERE id=%s',(user_id,))
    print('Temporary test records removed.',flush=True)
