import csv
import io
import json
import re
from html import escape
import os
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, jsonify, request, Response, send_file, stream_with_context, render_template
from shopify_sync import Shopify, configuration

ROOT = Path(__file__).parent
VERSION = '1.7.0'
DB = Path(os.environ.get('DATABASE_PATH', str(ROOT / 'data' / 'collection.sqlite')))
DB.parent.mkdir(parents=True, exist_ok=True)
app = Flask(__name__, static_folder='public', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 32000

@contextmanager
def connection():
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

with connection() as db:
    db.executescript('''
        CREATE TABLE IF NOT EXISTS sync_state (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL);
        INSERT OR IGNORE INTO sync_state VALUES(1,0);
        CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS shopify_products (card_id INTEGER NOT NULL REFERENCES cards(id),store TEXT NOT NULL,product_id TEXT NOT NULL,variant_id TEXT NOT NULL,item_id TEXT NOT NULL,last_quantity INTEGER,PRIMARY KEY(card_id,store));
        CREATE TABLE IF NOT EXISTS adjustments (id INTEGER PRIMARY KEY, card_id INTEGER NOT NULL REFERENCES cards(id), quantity INTEGER NOT NULL, cost_removed INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS cards (
          id INTEGER PRIMARY KEY, player TEXT NOT NULL, sport TEXT NOT NULL,
          year TEXT NOT NULL, brand TEXT NOT NULL, card_number TEXT NOT NULL,
          grade TEXT NOT NULL, notes TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>=0),
          total_cost INTEGER NOT NULL CHECK(total_cost>=0), market_price INTEGER NOT NULL CHECK(market_price>=0),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS clients (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL,
          phone TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sales (
          id INTEGER PRIMARY KEY, card_id INTEGER NOT NULL REFERENCES cards(id),
          client_id INTEGER REFERENCES clients(id), quantity INTEGER NOT NULL CHECK(quantity>0),
          revenue INTEGER NOT NULL, cost_basis INTEGER NOT NULL, fees INTEGER NOT NULL,
          shipping INTEGER NOT NULL, sold_on TEXT NOT NULL, channel TEXT NOT NULL,
          notes TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS purchases (
          id INTEGER PRIMARY KEY, card_id INTEGER NOT NULL REFERENCES cards(id),
          quantity INTEGER NOT NULL, total_cost INTEGER NOT NULL,
          purchased_on TEXT NOT NULL DEFAULT CURRENT_DATE);
    ''')
    existing_columns={row[1] for row in db.execute('PRAGMA table_info(cards)')}
    for name in ('subset','serial_number','cert_number'):
        if name not in existing_columns:db.execute(f"ALTER TABLE cards ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
    if 'deleted' not in existing_columns:db.execute('ALTER TABLE cards ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0')
    sales_columns={row[1] for row in db.execute('PRAGMA table_info(sales)')}
    for name,default in (('payment_method','Not recorded'),('payment_status','Not recorded'),('card_snapshot',''),('client_snapshot','')):
        if name not in sales_columns:db.execute(f"ALTER TABLE sales ADD COLUMN {name} TEXT NOT NULL DEFAULT '{default}'")
    if not db.execute("SELECT 1 FROM settings WHERE key='categories_initialized'").fetchone():
        for name in ('Baseball','Basketball','Football','Hockey','Soccer','Pokémon','Marvel','Disney','Magic: The Gathering','Other'):
            db.execute('INSERT OR IGNORE INTO categories VALUES(?)',(name,))
        db.execute("INSERT OR IGNORE INTO categories SELECT DISTINCT sport FROM cards")
        db.execute("INSERT INTO settings VALUES('categories_initialized','yes')")
    for table in ('cards','clients','sales','purchases','categories','adjustments','settings'):
        for action in ('INSERT','UPDATE','DELETE'):
            db.execute(f'CREATE TRIGGER IF NOT EXISTS sync_{table}_{action.lower()} AFTER {action} ON {table} BEGIN UPDATE sync_state SET revision=revision+1 WHERE id=1; END')

def text(data, key, required=False, limit=200):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f'Enter a valid {key.replace("_", " ")}.')
    return value.strip()

def integer(data, key, minimum=1):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f'Enter a whole number for {key}.')
    try:
        result = int(str(value))
    except ValueError:
        raise ValueError(f'Enter a whole number for {key}.')
    if not minimum <= result <= 1000000:
        raise ValueError(f'{key.capitalize()} must be between {minimum} and 1,000,000.')
    return result

def money(data, key):
    value = data.get(key, '0')
    if isinstance(value, bool):
        raise ValueError(f'Enter a valid amount for {key}.')
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > 10000000:
            raise ValueError()
        return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'Enter a non-negative amount for {key.replace("_", " ")}.')

def json_data():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError('Invalid request data.')
    return value

@app.before_request
def protect_requests():
    if request.method in ('POST', 'PATCH', 'DELETE'):
        origin = request.headers.get('Origin')
        if origin and urlsplit(origin).netloc != request.host:
            return jsonify(error='Request origin not allowed.'), 403
        if not request.is_json:
            return jsonify(error='Send JSON data.'), 415

@app.after_request
def headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.errorhandler(ValueError)
def bad_input(error):
    return jsonify(error=str(error)), 400

@app.errorhandler(413)
def too_large(error):
    return jsonify(error='Request is too large.'), 413

@app.get('/')
def home():
    return app.send_static_file('index.html')

@app.get('/api/version')
def version():
    return jsonify(version=VERSION, folder=str(ROOT.resolve()),pid=os.getpid())

@app.get('/api/events')
def events():
    def stream():
        previous=None
        heartbeat=time.monotonic()
        yield 'retry: 2000\n\n'
        while True:
            with connection() as db:
                revision=db.execute('SELECT revision FROM sync_state WHERE id=1').fetchone()[0]
            if revision!=previous:
                yield f'event: change\ndata: {revision}\n\n'
                previous=revision
                heartbeat=time.monotonic()
            elif time.monotonic()-heartbeat>=15:
                yield ': heartbeat\n\n'
                heartbeat=time.monotonic()
            time.sleep(1)
    return Response(stream_with_context(stream()),mimetype='text/event-stream',headers={'X-Accel-Buffering':'no'})

@app.get('/api/state')
def state():
    with connection() as db:
        db.execute('BEGIN')
        revision=db.execute('SELECT revision FROM sync_state WHERE id=1').fetchone()[0]
        categories=[row[0] for row in db.execute('SELECT name FROM categories ORDER BY name COLLATE NOCASE')]
        payment_links={row['key'].removeprefix('payment_'):row['value'] for row in db.execute("SELECT key,value FROM settings WHERE key IN ('payment_paypal','payment_cashapp','payment_creditcard')")}
        adjustments=[dict(row) for row in db.execute('SELECT a.*,c.player FROM adjustments a JOIN cards c ON c.id=a.card_id ORDER BY a.id DESC LIMIT 50')]
        cards = [dict(row) for row in db.execute('SELECT * FROM cards WHERE deleted=0 ORDER BY created_at DESC,id DESC')]
        clients = [dict(row) for row in db.execute('SELECT c.*,COUNT(s.id) AS sale_count,COALESCE(SUM(s.revenue),0) AS spend FROM clients c LEFT JOIN sales s ON s.client_id=c.id GROUP BY c.id ORDER BY c.name')]
        sales = [dict(row) for row in db.execute('SELECT s.*,c.player,c.brand,c.year,c.card_number,c.grade,c.subset,c.serial_number,c.cert_number,cl.name AS client_name FROM sales s JOIN cards c ON c.id=s.card_id LEFT JOIN clients cl ON cl.id=s.client_id ORDER BY s.sold_on DESC,s.id DESC')]
    totals = dict(stock=sum(c['quantity'] for c in cards), unique_cards=sum(c['quantity']>0 for c in cards), cost_value=sum(c['total_cost'] for c in cards), market_value=sum(c['quantity']*c['market_price'] for c in cards), revenue=sum(s['revenue'] for s in sales), profit=sum(s['revenue']-s['cost_basis']-s['fees']-s['shipping'] for s in sales), sold=sum(s['quantity'] for s in sales), clients=len(clients))
    return jsonify(cards=cards, clients=clients, sales=sales, totals=totals, revision=revision, categories=categories, adjustments=adjustments, payment_links=payment_links)

@app.post('/api/payment-links')
def payment_links():
    data=json_data();links={}
    for key in ('paypal','cashapp','creditcard'):
        url=text(data,key,limit=1500)
        try:
            parsed=urlsplit(url)
            valid=not url or (parsed.scheme=='https' and parsed.hostname and not parsed.username and not parsed.password and not any(c.isspace() for c in url))
        except ValueError:valid=False
        if not valid:raise ValueError('Payment links must be public HTTPS URLs, without credentials.')
        links[key]=url
    with connection() as db:
        for key,url in links.items():db.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('payment_'+key,url))
    return jsonify(ok=True)

@app.get('/api/monthly-sales')
def monthly_sales():
    with connection() as db:
        rows=db.execute("SELECT substr(sold_on,1,7) AS month,COUNT(*) AS transactions,SUM(quantity) AS pieces,SUM(revenue) AS revenue,SUM(cost_basis) AS cost,SUM(fees) AS fees,SUM(shipping) AS shipping,SUM(revenue-cost_basis-fees-shipping) AS profit FROM sales GROUP BY month ORDER BY month DESC").fetchall()
    return jsonify(months=[dict(row) for row in rows])

@app.get('/api/shopify/status')
def shopify_status():
    values,missing,valid=configuration()
    return jsonify(configured=not missing and valid,missing=missing,valid_store=valid)

@app.post('/api/cards/<int:identifier>/shopify')
def sync_shopify(identifier):
    json_data();client=Shopify()
    client.validate_currency()
    # Hold the write lock so local sales cannot race an external stock push.
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM cards WHERE id=? AND deleted=0',(identifier,)).fetchone()
        if not row:return jsonify(error='Inventory item not found.'),404
        card=dict(row)
        mapping=db.execute('SELECT * FROM shopify_products WHERE card_id=? AND store=?',(identifier,client.store)).fetchone()
        if not mapping:
            # Persist IDs before further calls, so retries do not create another product.
            product,variant,item=client.create(card)
            db.execute('INSERT INTO shopify_products(card_id,store,product_id,variant_id,item_id) VALUES(?,?,?,?,?)',(identifier,client.store,product,variant,item))
            db.commit();db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM cards WHERE id=? AND deleted=0',(identifier,)).fetchone()
            if not row:raise ValueError('Inventory was deleted while the product was being created. Review the draft product in Shopify.')
            card=dict(row)
            mapping=db.execute('SELECT * FROM shopify_products WHERE card_id=? AND store=?',(identifier,client.store)).fetchone()
        if mapping['last_quantity'] is None:client.update_price(mapping['product_id'],mapping['variant_id'],card)
        quantity=client.quantity(mapping['item_id'])
        if quantity is None:
            client.activate(mapping['item_id']);quantity=client.quantity(mapping['item_id'])
        if quantity is None:raise ValueError('Shopify inventory could not be activated at this location.')
        expected=mapping['last_quantity'] if mapping['last_quantity'] is not None else 0
        if quantity!=expected and quantity!=card['quantity']:raise ValueError('Shopify stock changed outside this CRM. Record the corresponding store sale, restock, or removal in CardLedger to match Shopify, then retry. No stock was overwritten.')
        client.update_price(mapping['product_id'],mapping['variant_id'],card)
        client.set_quantity(mapping['item_id'],card['quantity'],quantity)
        db.execute('UPDATE shopify_products SET last_quantity=? WHERE card_id=? AND store=?',(card['quantity'],identifier,client.store))
    return jsonify(ok=True,product_id=mapping['product_id'],quantity=card['quantity'])

@app.get('/receipts/<int:identifier>')
def receipt(identifier):
    with connection() as db:
        row=db.execute('SELECT * FROM sales WHERE id=?',(identifier,)).fetchone()
        if not row:return 'Sale not found',404
        sale=dict(row)
        card=json.loads(sale['card_snapshot']) if sale['card_snapshot'] else dict(db.execute('SELECT * FROM cards WHERE id=?',(sale['card_id'],)).fetchone())
        client=json.loads(sale['client_snapshot']) if sale['client_snapshot'] else None
        if not client and sale['client_id']:
            row=db.execute('SELECT * FROM clients WHERE id=?',(sale['client_id'],)).fetchone();client=dict(row) if row else None
        links={r['key'].removeprefix('payment_'):r['value'] for r in db.execute("SELECT key,value FROM settings WHERE key IN ('payment_paypal','payment_cashapp','payment_creditcard') AND value<>''")}
    return render_template('receipt.html',sale=sale,card=card,client=client,links=links,usd=lambda cents:f'${cents/100:,.2f}')

@app.patch('/api/sales/<int:identifier>/payment')
def update_payment(identifier):
    data=json_data();method=text(data,'payment_method',True);status=text(data,'payment_status',True)
    if method not in ('PayPal','Cash App','Credit card','Cash','Other','Not recorded') or status not in ('Pending','Paid','Not recorded'):raise ValueError('Choose a valid payment method and status.')
    with connection() as db:
        if not db.execute('UPDATE sales SET payment_method=?,payment_status=? WHERE id=?',(method,status,identifier)).rowcount:return jsonify(error='Sale not found.'),404
    return jsonify(ok=True)

@app.post('/api/categories')
def add_category():
    name=text(json_data(),'name',True,100)
    with connection() as db:
        if db.execute('SELECT 1 FROM categories WHERE lower(name)=lower(?)',(name,)).fetchone():raise ValueError('This category already exists.')
        db.execute('INSERT INTO categories VALUES(?)',(name,))
    return jsonify(ok=True),201

@app.delete('/api/categories')
def delete_category():
    name=text(json_data(),'name',True,100)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM cards WHERE sport=? AND deleted=0',(name,)).fetchone():raise ValueError('This category is used by inventory. Move those cards to another category before removing it.')
        if not db.execute('DELETE FROM categories WHERE name=?',(name,)).rowcount:return jsonify(error='Category not found.'),404
    return jsonify(ok=True)

@app.post('/api/cards/<int:identifier>/remove-stock')
def remove_stock(identifier):
    data=json_data();quantity=integer(data,'quantity');reason=text(data,'reason',True,500)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        card=db.execute('SELECT * FROM cards WHERE id=? AND deleted=0',(identifier,)).fetchone()
        if not card:return jsonify(error='Card not found.'),404
        if quantity>card['quantity']:raise ValueError(f'Only {card["quantity"]} pieces are in stock.')
        basis=int((Decimal(card['total_cost'])*quantity/card['quantity']).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        db.execute('UPDATE cards SET quantity=quantity-?,total_cost=total_cost-? WHERE id=?',(quantity,basis,identifier))
        db.execute('INSERT INTO adjustments(card_id,quantity,cost_removed,reason) VALUES(?,?,?,?)',(identifier,quantity,basis,reason))
    return jsonify(ok=True)

@app.post('/api/cards')
def add_card():
    data = json_data()
    fields = [text(data,k,k in ('player','sport')) for k in ('player','sport','year','brand','card_number','grade','subset','serial_number','cert_number')]
    notes = text(data,'notes',limit=3000)
    quantity, cost, market = integer(data,'quantity'), money(data,'unit_cost'), money(data,'market_price')
    with connection() as db:
        cur = db.execute('INSERT INTO cards(player,sport,year,brand,card_number,grade,subset,serial_number,cert_number,notes,quantity,total_cost,market_price) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (*fields,notes,quantity,quantity*cost,market))
        db.execute('INSERT INTO purchases(card_id,quantity,total_cost) VALUES(?,?,?)',(cur.lastrowid,quantity,quantity*cost))
    return jsonify(id=cur.lastrowid),201

@app.patch('/api/cards/<int:identifier>')
def edit_card(identifier):
    data = json_data()
    fields = [text(data,k,k in ('player','sport')) for k in ('player','sport','year','brand','card_number','grade','subset','serial_number','cert_number')]
    with connection() as db:
        cur=db.execute('UPDATE cards SET player=?,sport=?,year=?,brand=?,card_number=?,grade=?,subset=?,serial_number=?,cert_number=?,notes=?,market_price=? WHERE id=? AND deleted=0',(*fields,text(data,'notes',limit=3000),money(data,'market_price'),identifier))
        if not cur.rowcount: return jsonify(error='Card not found.'),404
    return jsonify(ok=True)

@app.delete('/api/cards/<int:identifier>')
def delete_inventory(identifier):
    json_data()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        card=db.execute('SELECT * FROM cards WHERE id=? AND deleted=0',(identifier,)).fetchone()
        if not card:return jsonify(error='Inventory item not found.'),404
        if card['quantity']:
            db.execute('INSERT INTO adjustments(card_id,quantity,cost_removed,reason) VALUES(?,?,?,?)',(identifier,card['quantity'],card['total_cost'],'Inventory listing deleted'))
        db.execute('UPDATE cards SET deleted=1,quantity=0,total_cost=0 WHERE id=?',(identifier,))
    return jsonify(ok=True)

@app.post('/api/cards/<int:identifier>/restock')
def restock(identifier):
    data=json_data();quantity=integer(data,'quantity');cost=money(data,'unit_cost')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        card=db.execute('SELECT quantity FROM cards WHERE id=? AND deleted=0',(identifier,)).fetchone()
        if not card: return jsonify(error='Card not found.'),404
        if card['quantity']+quantity>1000000: raise ValueError('Stock cannot exceed 1,000,000 pieces.')
        db.execute('UPDATE cards SET quantity=quantity+?,total_cost=total_cost+? WHERE id=?',(quantity,quantity*cost,identifier))
        db.execute('INSERT INTO purchases(card_id,quantity,total_cost) VALUES(?,?,?)',(identifier,quantity,quantity*cost))
    return jsonify(ok=True)

@app.post('/api/clients')
@app.patch('/api/clients/<int:identifier>')
def save_client(identifier=None):
    data=json_data();fields=[text(data,'name',True),text(data,'email'),text(data,'phone'),text(data,'notes',limit=3000)]
    with connection() as db:
        if identifier is None:
            cur=db.execute('INSERT INTO clients(name,email,phone,notes) VALUES(?,?,?,?)',fields)
            identifier=cur.lastrowid
        else:
            cur=db.execute('UPDATE clients SET name=?,email=?,phone=?,notes=? WHERE id=?',(*fields,identifier))
            if not cur.rowcount:return jsonify(error='Client not found.'),404
    return jsonify(id=identifier),201 if request.method=='POST' else 200

@app.post('/api/sales')
def record_sale():
    data=json_data();card_id=integer(data,'card_id');quantity=integer(data,'quantity')
    unit_price,fees,shipping=money(data,'unit_price'),money(data,'fees'),money(data,'shipping')
    client_id=integer(data,'client_id') if data.get('client_id') not in ('',None) else None
    sold_on=text(data,'sold_on',True)
    try:
        sold=date.fromisoformat(sold_on)
        if sold>date.today():raise ValueError()
    except ValueError:raise ValueError('Choose a valid sale date that is not in the future.')
    channel,notes=text(data,'channel'),text(data,'notes',limit=3000)
    method=text(data,'payment_method') or 'Not recorded';status=text(data,'payment_status') or 'Not recorded'
    if method not in ('PayPal','Cash App','Credit card','Cash','Other','Not recorded') or status not in ('Pending','Paid','Not recorded'):raise ValueError('Choose a valid payment method and status.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        card=db.execute('SELECT * FROM cards WHERE id=? AND deleted=0',(card_id,)).fetchone()
        if not card:return jsonify(error='Card not found.'),404
        if quantity>card['quantity']:raise ValueError(f'Only {card["quantity"]} pieces are in stock.')
        if client_id and not db.execute('SELECT id FROM clients WHERE id=?',(client_id,)).fetchone():raise ValueError('Client not found.')
        # Allocate the exact remaining cost basis; final sale consumes any cent remainder.
        basis=int((Decimal(card['total_cost'])*quantity/card['quantity']).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        db.execute('UPDATE cards SET quantity=quantity-?,total_cost=total_cost-? WHERE id=?',(quantity,basis,card_id))
        client=db.execute('SELECT * FROM clients WHERE id=?',(client_id,)).fetchone() if client_id else None
        cur=db.execute('INSERT INTO sales(card_id,client_id,quantity,revenue,cost_basis,fees,shipping,sold_on,channel,notes,payment_method,payment_status,card_snapshot,client_snapshot) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(card_id,client_id,quantity,unit_price*quantity,basis,fees,shipping,sold_on,channel,notes,method,status,json.dumps(dict(card)),json.dumps(dict(client)) if client else ''))
    return jsonify(id=cur.lastrowid),201

def safe_cell(value):
    return "'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value

@app.get('/api/shopify/products.csv')
def shopify_products():
    headers=['Handle','Title','Body (HTML)','Vendor','Type','Tags','Published','Option1 Name','Option1 Value','Variant SKU','Variant Inventory Tracker','Variant Inventory Qty','Variant Inventory Policy','Variant Fulfillment Service','Variant Price','Variant Requires Shipping','Variant Taxable','Status']
    output=io.StringIO();writer=csv.writer(output);writer.writerow(headers)
    with connection() as db:cards=db.execute('SELECT * FROM cards WHERE deleted=0 AND quantity>0 ORDER BY id').fetchall()
    for c in cards:
        title=' · '.join(str(c[key]) for key in ('player','year','brand','subset','grade','serial_number') if c[key])
        handle=f'cardledger-{c["id"]}'
        description='<p>'+escape(title)+'</p>'
        if c['cert_number']:description+='<p>Grading certificate: '+escape(c['cert_number'])+'</p>'
        writer.writerow([safe_cell(v) for v in [handle,title,description,c['brand'],c['sport'],c['sport'],'FALSE','Title','Default Title',f'CL-{c["id"]}','shopify',c['quantity'],'deny','manual',f'{c["market_price"]/100:.2f}','TRUE','TRUE','draft']])
    return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename="cardledger-shopify-products.csv"'})

@app.get('/api/export/<kind>')
def export(kind):
    with connection() as db:
        if kind=='inventory':
            rows=db.execute('SELECT player,sport,year,brand,card_number,grade,subset,serial_number,cert_number,quantity,ROUND(total_cost/100.0,2) AS purchase_cost_usd,ROUND(market_price/100.0,2) AS estimated_unit_value_usd,notes FROM cards WHERE deleted=0').fetchall()
            names=['player','sport','year','brand','card_number','grade','subset','serial_number','cert_number','quantity','purchase_cost_usd','estimated_unit_value_usd','notes']
        elif kind=='clients':
            rows=db.execute('SELECT name,email,phone,notes FROM clients').fetchall();names=['name','email','phone','notes']
        elif kind=='sales':
            rows=db.execute('SELECT s.sold_on,c.player,cl.name,s.quantity,s.revenue/100.0,s.cost_basis/100.0,s.fees/100.0,s.shipping/100.0,(s.revenue-s.cost_basis-s.fees-s.shipping)/100.0,s.channel,s.notes,s.payment_method,s.payment_status FROM sales s JOIN cards c ON c.id=s.card_id LEFT JOIN clients cl ON cl.id=s.client_id ORDER BY s.sold_on DESC').fetchall()
            names=['date','player','client','quantity','revenue_usd','cost_basis_usd','fees_usd','shipping_usd','profit_usd','channel','notes','payment_method','payment_status']
        else:return jsonify(error='Export not found.'),404
    output=io.StringIO();writer=csv.writer(output);writer.writerow(names)
    writer.writerows([[safe_cell(value) for value in row] for row in rows])
    return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="cardledger-{kind}.csv"'})

@app.get('/api/backup')
def backup():
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'backup.sqlite'
        with connection() as source, sqlite3.connect(path) as target:source.backup(target)
        data=io.BytesIO(path.read_bytes())
    return send_file(data,mimetype='application/octet-stream',as_attachment=True,download_name=f'cardledger-{date.today()}.sqlite')

if __name__=='__main__':
    app.run(host='127.0.0.1',port=int(os.environ.get('PORT','3001')),debug=False)
