"""Authenticated stock management backed by PostgreSQL."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
import os
import uuid
import psycopg
from psycopg.rows import dict_row
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import check_password_hash, generate_password_hash


def secret(name):
    return Path(os.environ.get(name+'_FILE', '/run/secrets/'+name.lower())).read_text().strip()


def connect():
    return psycopg.connect(host=os.environ.get('DB_HOST','db'), dbname=os.environ.get('DB_NAME','inventory'),
                          user=os.environ.get('DB_USER','inventory'), password=secret('DB_PASSWORD'),
                          connect_timeout=5, row_factory=dict_row)


app = Flask(__name__)
app.config.update(SECRET_KEY=secret('SESSION_KEY'), SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE','false')=='true',
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=2), MAX_CONTENT_LENGTH=32768)
CSRFProtect(app)
DUMMY_HASH = generate_password_hash('not-an-account-password')


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def load_user():
    g.user = None
    if session.get('user_id'):
        with connect() as db:
            g.user = db.execute('SELECT id,username FROM users WHERE id=%s',(session['user_id'],)).fetchone()
        if not g.user:
            session.clear()


@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
    if not request.path.startswith('/static/'):
        response.headers['Cache-Control']='no-store'
    return response


@app.errorhandler(CSRFError)
def csrf_error(error):
    return render_template('error.html',message='This form expired. Reload the page and try again.'),400


@app.errorhandler(404)
def missing(error):
    return render_template('error.html',message='That page or product could not be found.'),404


@app.errorhandler(psycopg.OperationalError)
def unavailable(error):
    app.logger.error('Database temporarily unavailable')
    return render_template('error.html',message='The database is temporarily unavailable. Please try again shortly.'),503


@app.get('/health')
def health():
    with connect() as db:
        row=db.execute('SELECT version FROM schema_migrations WHERE version=1').fetchone()
    return ({'service':'inventory-app','status':'ok','database':'ok'},200) if row else ({'status':'not-ready'},503)


@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form.get('username','').strip().lower()[:80]
        password=request.form.get('password','')[:256]
        with connect() as db:
            attempts=db.execute("SELECT count(*) AS n FROM login_attempts WHERE username=%s AND happened_at>now()-interval '15 minutes'",(username,)).fetchone()['n']
            if attempts>=8:
                return render_template('login.html',error='Too many attempts. Try again in 15 minutes.'),429
            user=db.execute('SELECT * FROM users WHERE username=%s',(username,)).fetchone()
            valid=check_password_hash(user['password_hash'] if user else DUMMY_HASH,password)
            if not user or not valid:
                db.execute('INSERT INTO login_attempts(username) VALUES (%s)',(username,))
                return render_template('login.html',error='Incorrect username or password.'),401
            db.execute('DELETE FROM login_attempts WHERE username=%s',(username,))
            db.execute("DELETE FROM login_attempts WHERE happened_at<now()-interval '1 day'")
        session.clear()
        session['user_id']=user['id']
        session.permanent=True
        return redirect(url_for('dashboard'))
    if g.user:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.get('/')
@login_required
def dashboard():
    query=request.args.get('q','').strip()[:100]
    category=request.args.get('category',type=int)
    low=request.args.get('low')=='1'
    page=max(1,min(request.args.get('page',1,type=int),100000))
    clauses,params=[],[]
    if query:
        clauses.append('(p.name ILIKE %s OR p.sku ILIKE %s)'); params.extend(['%'+query+'%']*2)
    if category:
        clauses.append('p.category_id=%s'); params.append(category)
    if low:
        clauses.append('p.quantity<=p.low_stock_threshold')
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    with connect() as db:
        stats=db.execute('SELECT count(*) AS products,COALESCE(sum(quantity),0) AS units,COALESCE(sum(quantity*price),0) AS value,count(*) FILTER (WHERE quantity<=low_stock_threshold) AS low FROM products').fetchone()
        cats=db.execute('SELECT * FROM categories ORDER BY name').fetchall()
        total=db.execute('SELECT count(*) AS n FROM products p'+where,params).fetchone()['n']
        products=db.execute('SELECT p.*,c.name AS category FROM products p JOIN categories c ON c.id=p.category_id'+where+' ORDER BY p.name,p.id LIMIT 25 OFFSET %s',params+[(page-1)*25]).fetchall()
        moves=db.execute('SELECT m.*,p.name AS product,p.sku,u.username FROM movements m JOIN products p ON p.id=m.product_id JOIN users u ON u.id=m.user_id ORDER BY m.id DESC LIMIT 8').fetchall()
    return render_template('dashboard.html',stats=stats,products=products,categories=cats,movements=moves,
                           query=query,category=category,low=low,page=page,pages=max(1,(total+24)//25),total=total)


@app.route('/categories',methods=['GET','POST'])
@login_required
def categories():
    if request.method=='POST':
        name=request.form.get('name','').strip()
        if not 1<=len(name)<=80:
            flash('Enter a category name between 1 and 80 characters.','error')
        else:
            try:
                with connect() as db:
                    db.execute('INSERT INTO categories(name) VALUES (%s)',(name,))
                flash('Category created.','success')
            except psycopg.errors.UniqueViolation:
                flash('That category already exists.','error')
        return redirect(url_for('categories'))
    with connect() as db:
        rows=db.execute('SELECT c.id,c.name,count(p.id) AS products FROM categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY c.id ORDER BY c.name').fetchall()
    return render_template('categories.html',categories=rows)


def product_values(form):
    sku=form.get('sku','').strip().upper(); name=form.get('name','').strip()
    if not sku or len(sku)>40 or not name or len(name)>120:
        raise ValueError('SKU (up to 40 characters) and name (up to 120) are required.')
    try:
        price=Decimal(form.get('price','')); category=int(form.get('category_id','')); threshold=int(form.get('low_stock_threshold','5'))
    except (InvalidOperation,ValueError):
        raise ValueError('Enter a valid price, category and whole-number threshold.')
    if not price.is_finite() or not 0<=price<=Decimal('9999999.99') or price!=price.quantize(Decimal('.01')):
        raise ValueError('Price must be nonnegative with at most two decimal places.')
    if not 0<=threshold<=1000000:
        raise ValueError('Low-stock threshold must be between 0 and 1000000.')
    return sku,name,price,category,threshold


@app.route('/products/new',methods=['GET','POST'])
@app.route('/products/<int:product_id>/edit',methods=['GET','POST'])
@login_required
def product_form(product_id=None):
    with connect() as db:
        cats=db.execute('SELECT * FROM categories ORDER BY name').fetchall()
        product=db.execute('SELECT * FROM products WHERE id=%s',(product_id,)).fetchone() if product_id else None
    if product_id and not product:
        abort(404)
    if request.method=='POST':
        try:
            values=product_values(request.form)
            with connect() as db:
                if product_id:
                    db.execute('UPDATE products SET sku=%s,name=%s,price=%s,category_id=%s,low_stock_threshold=%s WHERE id=%s',values+(product_id,))
                else:
                    product_id=db.execute('INSERT INTO products(sku,name,price,category_id,low_stock_threshold) VALUES (%s,%s,%s,%s,%s) RETURNING id',values).fetchone()['id']
            flash('Product saved. Use Receive stock to add units.','success')
            return redirect(url_for('product_detail',product_id=product_id))
        except (ValueError,psycopg.errors.UniqueViolation,psycopg.errors.ForeignKeyViolation) as error:
            flash(str(error) if isinstance(error,ValueError) else 'SKU already exists or the category is invalid.','error')
            product=dict(request.form); product['id']=product_id
            return render_template('product_form.html',product=product,categories=cats),400
    return render_template('product_form.html',product=product,categories=cats)


def record_movement(product_id,user_id,kind,quantity,note,request_id):
    if kind not in ('receive','sale') or not 1<=quantity<=1000000 or len(note)>200:
        raise ValueError('Choose sale or receipt, a quantity from 1 to 1000000, and a note up to 200 characters.')
    try:
        request_id=uuid.UUID(str(request_id))
    except (ValueError,TypeError):
        raise ValueError('Invalid form identifier. Reload the product page.')
    delta=quantity if kind=='receive' else -quantity
    # Atomic conditional UPDATE locks the product and rechecks available stock.
    # The movement insert shares the transaction: either both commit or neither.
    with connect() as db:
        if db.execute('SELECT id FROM movements WHERE request_id=%s',(request_id,)).fetchone():
            return False
        product=db.execute('UPDATE products SET quantity=quantity+%s WHERE id=%s AND quantity+%s BETWEEN 0 AND 100000000 RETURNING quantity,price',(delta,product_id,delta)).fetchone()
        if not product:
            raise ValueError('Not enough stock, product unavailable, or stock limit exceeded.')
        db.execute('INSERT INTO movements(product_id,user_id,kind,quantity,balance_after,unit_price,note,request_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                   (product_id,user_id,kind,quantity,product['quantity'],product['price'],note,request_id))
    return True


@app.route('/products/<int:product_id>',methods=['GET','POST'])
@login_required
def product_detail(product_id):
    if request.method=='POST':
        try:
            changed=record_movement(product_id,g.user['id'],request.form.get('kind'),int(request.form.get('quantity','')),
                                    request.form.get('note','').strip(),request.form.get('request_id'))
            flash('Stock movement recorded.' if changed else 'This movement was already recorded.','success')
        except psycopg.errors.UniqueViolation:
            flash('This movement was already recorded.','success')
        except ValueError as error:
            flash(str(error),'error')
        return redirect(url_for('product_detail',product_id=product_id))
    with connect() as db:
        product=db.execute('SELECT p.*,c.name AS category FROM products p JOIN categories c ON c.id=p.category_id WHERE p.id=%s',(product_id,)).fetchone()
        if not product:
            abort(404)
        moves=db.execute('SELECT m.*,u.username FROM movements m JOIN users u ON u.id=m.user_id WHERE product_id=%s ORDER BY m.id DESC LIMIT 100',(product_id,)).fetchall()
    return render_template('product.html',product=product,movements=moves,request_id=str(uuid.uuid4()))


@app.get('/movements')
@login_required
def movements():
    page=max(1,min(request.args.get('page',1,type=int),100000))
    with connect() as db:
        total=db.execute('SELECT count(*) AS n FROM movements').fetchone()['n']
        rows=db.execute('SELECT m.*,p.name AS product,p.sku,u.username FROM movements m JOIN products p ON p.id=m.product_id JOIN users u ON u.id=m.user_id ORDER BY m.id DESC LIMIT 50 OFFSET %s',((page-1)*50,)).fetchall()
    return render_template('movements.html',movements=rows,page=page,pages=max(1,(total+49)//50))
