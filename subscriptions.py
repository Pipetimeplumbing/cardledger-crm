"""Stripe hosted subscriptions. Customer access changes only after signed webhooks."""
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from flask import request, jsonify, g

def stripe_request(path,fields=None):
    key=os.environ.get('STRIPE_SECRET_KEY','')
    if not key:raise ValueError('Subscription billing is not connected yet.')
    data=urllib.parse.urlencode(fields).encode() if fields is not None else None
    headers={'Authorization':'Bearer '+key}
    if data is not None:headers['Content-Type']='application/x-www-form-urlencoded'
    req=urllib.request.Request('https://api.stripe.com/v1/'+path,data=data,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
    except (urllib.error.URLError,TimeoutError,json.JSONDecodeError):raise ValueError('Stripe could not complete this request. Check billing configuration and try again.')

def valid_signature(body,header,secret,now=None):
    if not secret:return False
    pieces={}
    for part in header.split(','):
        key,separator,value=part.partition('=')
        if separator:pieces.setdefault(key,[]).append(value)
    try:timestamp=int(pieces.get('t',[''])[0])
    except ValueError:return False
    if abs((now or time.time())-timestamp)>300:return False
    expected=hmac.new(secret.encode(),str(timestamp).encode()+b'.'+body,hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected,value) for value in pieces.get('v1',[]))

def install_subscriptions(app,accounts):
    def config():
        base=os.environ.get('APP_BASE_URL','').rstrip('/')
        url=urllib.parse.urlsplit(base)
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
            raise ValueError('Set APP_BASE_URL to the public HTTPS website origin.')
        price=os.environ.get('STRIPE_PRICE_ID','')
        if not price:raise ValueError('Set up the $5 monthly subscription price in Stripe first.')
        return base,price

    def verify_price(price):
        details=stripe_request('prices/'+urllib.parse.quote(price,safe=''))
        recurring=details.get('recurring') or {}
        if not details.get('active') or details.get('currency')!='usd' or details.get('unit_amount')!=500 or recurring.get('interval')!='month' or recurring.get('interval_count')!=1:
            raise ValueError('The Stripe price must be active and charge exactly $5 USD every month.')

    @app.get('/api/billing/status')
    def status():
        configured=all(os.environ.get(key) for key in ('STRIPE_SECRET_KEY','STRIPE_PRICE_ID','STRIPE_WEBHOOK_SECRET','APP_BASE_URL'))
        return jsonify(configured=configured,monthly_price_usd=5,user={k:g.account[k] for k in ('email','name','owner','billing_status')})

    @app.post('/api/billing/checkout')
    def checkout():
        if g.owner:return jsonify(error='The owner account does not need a subscription.'),400
        if g.account['billing_status'] in ('active','trialing'):return jsonify(error='This account already has a subscription. Use Manage subscription.'),409
        base,price=config();verify_price(price)
        if not os.environ.get('STRIPE_WEBHOOK_SECRET'):raise ValueError('Configure signed Stripe webhooks before enabling checkout.')
        with accounts() as db:
            db.execute('BEGIN IMMEDIATE')
            user=db.execute('SELECT * FROM users WHERE id=?',(g.account['id'],)).fetchone()
            customer=user['stripe_customer']
            if not customer:
                customer=stripe_request('customers',{'email':user['email'],'name':user['name'],'metadata[cardledger_account]':user['id']})['id']
                db.execute('UPDATE users SET stripe_customer=? WHERE id=?',(customer,user['id']))
        existing=stripe_request('subscriptions?'+urllib.parse.urlencode({'customer':customer,'status':'all','limit':100}))
        if any(s.get('status') in ('active','trialing') and any(i.get('price',{}).get('id')==price for i in s.get('items',{}).get('data',[])) for s in existing.get('data',[])):
            return jsonify(error='A subscription already exists. Wait for confirmation or use Manage subscription.'),409
        with accounts() as db:
            db.execute('BEGIN IMMEDIATE')
            pending=db.execute('SELECT url,expires FROM billing_checkouts WHERE user_id=?',(g.account['id'],)).fetchone()
            if pending and pending['expires']>int(time.time()):return jsonify(url=pending['url'])
            session=stripe_request('checkout/sessions',{'mode':'subscription','customer':customer,'line_items[0][price]':price,'line_items[0][quantity]':'1','client_reference_id':g.account['id'],'success_url':base+'/account?checkout=complete','cancel_url':base+'/account?checkout=cancelled'})
            db.execute('INSERT INTO billing_checkouts VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET url=excluded.url,expires=excluded.expires',(g.account['id'],session['url'],session.get('expires_at',int(time.time())+1800)))
        return jsonify(url=session['url'])

    @app.post('/api/billing/portal')
    def portal():
        base,_=config()
        customer=g.account['stripe_customer']
        if not customer:return jsonify(error='This account has no Stripe billing record yet.'),400
        session=stripe_request('billing_portal/sessions',{'customer':customer,'return_url':base+'/account'})
        return jsonify(url=session['url'])

    @app.post('/api/billing/webhook')
    def webhook():
        body=request.get_data(cache=True)
        if not valid_signature(body,request.headers.get('Stripe-Signature',''),os.environ.get('STRIPE_WEBHOOK_SECRET','')):return jsonify(error='Invalid webhook signature.'),400
        try:event=json.loads(body)
        except (json.JSONDecodeError,UnicodeDecodeError):return jsonify(error='Invalid event.'),400
        if not isinstance(event,dict) or not isinstance(event.get('id'),str):return jsonify(error='Invalid event.'),400
        with accounts() as db:
            if db.execute('SELECT 1 FROM stripe_events WHERE id=?',(event['id'],)).fetchone():return jsonify(ok=True)
        supported={'checkout.session.completed','customer.subscription.created','customer.subscription.updated','customer.subscription.deleted','invoice.payment_succeeded','invoice.payment_failed'}
        if event.get('type') not in supported:return jsonify(ok=True)
        obj=event.get('data',{}).get('object',{});customer=obj.get('customer')
        if not isinstance(customer,str):return jsonify(error='Missing customer.'),400
        with accounts() as db:user=db.execute('SELECT id FROM users WHERE stripe_customer=? AND owner=0',(customer,)).fetchone()
        if not user:return jsonify(ok=True)
        # Fetch current subscription state so old/out-of-order events cannot restore access.
        _,price=config()
        with accounts() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM stripe_events WHERE id=?',(event['id'],)).fetchone():return jsonify(ok=True)
            listing=stripe_request('subscriptions?'+urllib.parse.urlencode({'customer':customer,'status':'all','limit':100}))
            eligible=[s for s in listing.get('data',[]) if any(i.get('price',{}).get('id')==price for i in s.get('items',{}).get('data',[]))]
            active=next((s for s in eligible if s.get('status') in ('active','trialing')),None)
            new_status=active['status'] if active else 'inactive'
            db.execute('UPDATE users SET billing_status=? WHERE id=?',(new_status,user['id']))
            if new_status in ('active','trialing'):db.execute('DELETE FROM billing_checkouts WHERE user_id=?',(user['id'],))
            db.execute('INSERT OR IGNORE INTO stripe_events VALUES(?,?)',(event['id'],int(time.time())))
        return jsonify(ok=True)
