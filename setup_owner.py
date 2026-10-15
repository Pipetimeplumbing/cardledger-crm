"""Create or reset the owner from a trusted local/hosting console."""
import getpass
import re
import secrets
import sys
import time
from werkzeug.security import generate_password_hash
from app import app

email=input('Owner email: ').strip().lower()
if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):sys.exit('Enter a valid email.')
password=getpass.getpass('Password (at least 12 characters): ')
if not 12<=len(password)<=128:sys.exit('Use a password with 12–128 characters.')
if password!=getpass.getpass('Confirm password: '):sys.exit('Passwords did not match.')
with app.extensions['accounts_connection']() as db:
    owner=db.execute('SELECT * FROM users WHERE owner=1').fetchone()
    if owner:
        if '--reset' not in sys.argv:sys.exit('An owner exists. Run with --reset from your trusted console to reset it.')
        if owner['email']!=email:sys.exit('Use the existing owner email.')
        db.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(password),owner['id']))
        db.execute('DELETE FROM auth_sessions WHERE user_id=?',(owner['id'],))
    else:
        db.execute('INSERT INTO users(id,email,password_hash,name,owner,billing_status,created) VALUES(?,?,?,?,1,?,?)',(secrets.token_hex(16),email,generate_password_hash(password),'Owner','owner',int(time.time())))
print('Owner login saved. Your existing inventory remains in the owner workspace.')
