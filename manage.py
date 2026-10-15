from pathlib import Path
import sys
import uuid
from psycopg import sql
from werkzeug.security import generate_password_hash
from app import connect, secret


def initialize():
    with connect() as db:
        db.execute(Path('schema.sql').read_text())
        if not db.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
            db.execute('INSERT INTO users(username,password_hash) VALUES (%s,%s)',('admin',generate_password_hash(secret('ADMIN_PASSWORD'))))
    print('Schema version 1 ready; administrator exists. No passwords printed.')


def seed():
    sample=[('KB-101','Mechanical keyboard','Peripherals','69.00',18,5),
            ('MS-204','Wireless mouse','Peripherals','24.50',32,8),
            ('CB-310','USB-C cable','Accessories','9.90',4,8),
            ('HB-402','USB-C hub','Accessories','39.00',12,4),
            ('NT-501','A5 notebook','Office supplies','6.50',48,10),
            ('ST-602','Laptop stand','Accessories','29.00',3,5)]
    with connect() as db:
        user=db.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id']
        for sku,name,category,price,qty,threshold in sample:
            db.execute('INSERT INTO categories(name) VALUES (%s) ON CONFLICT DO NOTHING',(category,))
            cat=db.execute('SELECT id FROM categories WHERE name=%s',(category,)).fetchone()['id']
            product=db.execute('INSERT INTO products(sku,name,price,category_id,quantity,low_stock_threshold) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(sku) DO NOTHING RETURNING id',(sku,name,price,cat,qty,threshold)).fetchone()
            if product:
                db.execute("INSERT INTO movements(product_id,user_id,kind,quantity,balance_after,unit_price,note,request_id) VALUES (%s,%s,'receive',%s,%s,%s,%s,%s)",(product['id'],user,qty,qty,price,'Fictional demo opening stock',uuid.uuid4()))
    print('Fictional demo inventory ready. Existing products were not changed.')


def reset_admin():
    with connect() as db:
        new_hash = generate_password_hash(secret('ADMIN_PASSWORD'))
        changed = db.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (new_hash,))
        if changed.rowcount != 1:
            raise RuntimeError('Expected exactly one administrator; password unchanged.')
    print('Administrator password rotated in database to match current secret. No passwords printed.')


def runtime_role():
    with connect() as db:
        if not db.execute("SELECT 1 FROM pg_roles WHERE rolname='inventory_web'").fetchone():
            db.execute('CREATE ROLE inventory_web LOGIN')
        db.execute(sql.SQL('ALTER ROLE inventory_web NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Literal(secret('APP_DB_PASSWORD'))))
        db.execute('REVOKE ALL ON DATABASE inventory FROM PUBLIC')
        db.execute('GRANT CONNECT ON DATABASE inventory TO inventory_web')
        db.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        db.execute('GRANT USAGE ON SCHEMA public TO inventory_web')
        db.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO inventory_web')
        db.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO inventory_web')
    print('Runtime role configured with data access, no schema ownership or administrative privileges.')


if __name__=='__main__':
    if sys.argv[1:]==['init']: initialize()
    elif sys.argv[1:]==['seed']: seed()
    elif sys.argv[1:]==['reset-admin']: reset_admin()
    elif sys.argv[1:]==['runtime-role']: runtime_role()
    else: raise SystemExit('Usage: python manage.py init | seed | reset-admin | runtime-role')
