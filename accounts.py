"""Authentication and per-account inventory database isolation."""
import hashlib
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from flask import request, jsonify, g, redirect, stream_with_context
from werkzeug.security import generate_password_hash, check_password_hash

def install_accounts(app,legacy_db,initialize):
    accounts_db=legacy_db.parent/'accounts.sqlite'
    accounts_db.parent.mkdir(parents=True,exist_ok=True)
    @contextmanager
    def accounts():
        db=sqlite3.connect(accounts_db,timeout=15);db.row_factory=sqlite3.Row
        try:yield db;db.commit()
        except Exception:db.rollback();raise
        finally:db.close()
    app.extensions['accounts_connection']=accounts
    with accounts() as db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,name TEXT NOT NULL,owner INTEGER NOT NULL DEFAULT 0,billing_status TEXT NOT NULL DEFAULT 'inactive',stripe_customer TEXT UNIQUE,created INTEGER NOT NULL);
          CREATE UNIQUE INDEX IF NOT EXISTS single_owner ON users(owner) WHERE owner=1;
          CREATE TABLE IF NOT EXISTS auth_sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS auth_attempts(ip TEXT,timestamp INTEGER);
          CREATE TABLE IF NOT EXISTS stripe_events(id TEXT PRIMARY KEY,created INTEGER);
          CREATE TABLE IF NOT EXISTS billing_checkouts(user_id TEXT PRIMARY KEY,url TEXT NOT NULL,expires INTEGER NOT NULL);
        ''')
        email=os.environ.get('OWNER_EMAIL','').strip().lower();password=os.environ.get('OWNER_PASSWORD','')
        if email and password and not db.execute('SELECT 1 FROM users WHERE owner=1').fetchone():
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not 12<=len(password)<=128:
                raise ValueError('Set a valid OWNER_EMAIL and a 12–128 character OWNER_PASSWORD.')
            db.execute('INSERT INTO users(id,email,password_hash,name,owner,billing_status,created) VALUES(?,?,?,?,1,?,?)',(secrets.token_hex(16),email,generate_password_hash(password),'Owner','owner',int(time.time())))
    dummy=generate_password_hash(secrets.token_urlsafe(32))
    hosted=bool(os.environ.get('RENDER')) or os.environ.get('CARDLEDGER_HOSTED')=='true'
    app.config['CARDLEDGER_HOSTED']=hosted

    def public_user(row):
        return {key:row[key] for key in ('id','email','name','owner','billing_status')}

    def session_user():
        token=request.cookies.get('cardledger_session','')
        with accounts() as db:
            return db.execute('SELECT u.* FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()

    public_paths={'/login','/login.html','/auth.js','/auth.css','/style.css','/health','/api/auth/login','/api/auth/register','/api/auth/logout','/api/auth/options','/api/billing/webhook'}

    @app.before_request
    def authentication():
        # Stripe posts raw signed payloads; all browser mutations require same-origin JSON.
        if request.method in ('POST','PATCH','DELETE') and request.path!='/api/billing/webhook':
            origin=request.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=request.host:return jsonify(error='Request origin not allowed.'),403
            if not request.is_json:return jsonify(error='Send JSON data.'),415
        if request.path in public_paths:return
        # Local desktop start/stop can inspect identity, without exposing inventory.
        if request.path=='/api/version' and not hosted:return
        user=session_user()
        if not user:
            if request.path.startswith('/api/'):return jsonify(error='Please sign in.',login_required=True),401
            return redirect('/login')
        g.account=dict(user);g.owner=bool(user['owner'])
        db_path=legacy_db if user['owner'] else legacy_db.parent/'workspaces'/user['id']/'collection.sqlite'
        g.inventory_db=db_path
        billing_path=request.path.startswith('/api/billing/') or request.path in ('/account','/account.html','/auth.js','/api/auth/me','/api/auth/logout','/api/auth/password','/api/auth/delete')
        static=request.path in ('/style.css','/billing.js')
        if not user['owner'] and user['billing_status'] not in ('active','trialing') and not billing_path and not static:
            if request.path.startswith('/api/'):return jsonify(error='An active subscription is required.',subscription_required=True),402
            return redirect('/account')

    def issue_session(user_id):
        token=secrets.token_urlsafe(32);now=int(time.time())
        with accounts() as db:
            db.execute('DELETE FROM auth_sessions WHERE expires<?',(now,))
            db.execute('INSERT INTO auth_sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user_id,now+86400))
        response=jsonify(ok=True)
        response.set_cookie('cardledger_session',token,max_age=86400,httponly=True,secure=hosted or request.is_secure,samesite='Lax',path='/')
        return response

    def rate_limit():
        now=int(time.time());ip=request.remote_addr or 'unknown'
        with accounts() as db:
            db.execute('DELETE FROM auth_attempts WHERE timestamp<?',(now-900,))
            if db.execute('SELECT COUNT(*) FROM auth_attempts WHERE ip=?',(ip,)).fetchone()[0]>=20:return True
            db.execute('INSERT INTO auth_attempts VALUES(?,?)',(ip,now))
        return False

    @app.get('/health')
    def health():return jsonify(status='ok')

    @app.get('/login')
    def login_page():return app.send_static_file('login.html')

    @app.get('/account')
    def billing_page():return app.send_static_file('account.html')

    @app.get('/api/auth/options')
    def options():
        with accounts() as db:owner_exists=bool(db.execute('SELECT 1 FROM users WHERE owner=1').fetchone())
        return jsonify(signup_enabled=os.environ.get('ENABLE_SIGNUP')=='true' and owner_exists,owner_configured=owner_exists)

    @app.post('/api/auth/<action>')
    def auth_action(action):
        if action=='logout':
            token=request.cookies.get('cardledger_session','')
            with accounts() as db:db.execute('DELETE FROM auth_sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
            response=jsonify(ok=True);response.delete_cookie('cardledger_session',path='/');return response
        if action not in ('login','register','password'):return jsonify(error='Not found'),404
        if rate_limit():return jsonify(error='Too many attempts. Try again in 15 minutes.'),429
        data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Invalid request.'),400
        if action=='password':
            user=g.account;old=data.get('password');new=data.get('new_password')
            if not isinstance(old,str) or len(old)>128 or not isinstance(new,str) or not 12<=len(new)<=128:return jsonify(error='Use a new password with 12–128 characters.'),400
            if not check_password_hash(user['password_hash'],old):return jsonify(error='Current password is incorrect.'),401
            with accounts() as db:
                db.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(new),user['id']))
                db.execute('DELETE FROM auth_sessions WHERE user_id=?',(user['id'],))
            return issue_session(user['id'])
        email=data.get('email','');password=data.get('password','')
        if not isinstance(email,str) or not isinstance(password,str) or len(email)>254 or len(password)>128:return jsonify(error='Enter a valid email and password.'),400
        email=email.strip().lower()
        if action=='login':
            with accounts() as db:user=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            valid=check_password_hash(user['password_hash'] if user else dummy,password)
            if not user or not valid:return jsonify(error='Email or password is incorrect.'),401
            return issue_session(user['id'])
        if os.environ.get('ENABLE_SIGNUP')!='true':return jsonify(error='New account signup is not open yet.'),403
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not 12<=len(password)<=128:return jsonify(error='Use a valid email and a password with 12–128 characters.'),400
        name=data.get('name','')
        if not isinstance(name,str) or not 1<=len(name.strip())<=100:return jsonify(error='Enter your name.'),400
        identifier=secrets.token_hex(16)
        with accounts() as db:
            if not db.execute('SELECT 1 FROM users WHERE owner=1').fetchone():return jsonify(error='The owner account must be configured first.'),503
            if db.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone():return jsonify(error='Unable to create that account. Try signing in.'),409
            path=legacy_db.parent/'workspaces'/identifier/'collection.sqlite';path.parent.mkdir(parents=True,exist_ok=True)
            initialize(path)
            db.execute('INSERT INTO users(id,email,password_hash,name,created) VALUES(?,?,?,?,?)',(identifier,email,generate_password_hash(password),name.strip(),int(time.time())))
        return issue_session(identifier)

    @app.get('/api/auth/me')
    def me():return jsonify(user=public_user(g.account))

    from subscriptions import install_subscriptions
    install_subscriptions(app,accounts)
