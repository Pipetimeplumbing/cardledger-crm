import hashlib
import hmac
import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

class AccountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.environment=patch.dict(os.environ,{'DATABASE_PATH':str(Path(cls.temp.name)/'collection.sqlite'),'OWNER_EMAIL':'owner@example.com','OWNER_PASSWORD':'owner-password-1234','ENABLE_SIGNUP':'true','APP_BASE_URL':'https://cards.example.com','STRIPE_PRICE_ID':'price_monthly','STRIPE_WEBHOOK_SECRET':'test-webhook-secret','STRIPE_SECRET_KEY':'test-secret'})
        cls.environment.start()
        spec=importlib.util.spec_from_file_location('isolated_accounts_app',Path(__file__).parents[1]/'app.py');cls.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.module)
    @classmethod
    def tearDownClass(cls):cls.environment.stop();cls.temp.cleanup()
    def setUp(self):
        self.owner=self.module.app.test_client();self.owner.post('/api/auth/login',json={'email':'owner@example.com','password':'owner-password-1234'})
        with self.module.app.extensions['accounts_connection']() as db:db.execute('DELETE FROM auth_attempts')
    def customer(self):
        client=self.module.app.test_client();email=str(time.time_ns())+'@example.com'
        response=client.post('/api/auth/register',json={'email':email,'name':'Customer','password':'customer-password-123'})
        self.assertEqual(response.status_code,200,response.json)
        return client,client.get('/api/auth/me').json['user']['id']
    def activate(self,identifier):
        with self.module.app.extensions['accounts_connection']() as db:db.execute("UPDATE users SET billing_status='active' WHERE id=?",(identifier,))
    def test_anonymous_and_subscription_gates(self):
        visitor=self.module.app.test_client()
        for path in ('/api/state','/api/backup','/api/export/clients','/api/shopify/status'):
            self.assertEqual(visitor.get(path).status_code,401,path)
        self.assertEqual(visitor.get('/').status_code,302)
        customer,identifier=self.customer()
        self.assertEqual(customer.get('/api/state').status_code,402)
        response=customer.get('/account?checkout=complete')
        self.assertEqual(response.status_code,200);response.close()
        self.assertEqual(customer.get('/api/state').status_code,402)
        self.assertEqual(customer.get('/api/billing/status').status_code,200)
        self.assertEqual(self.owner.get('/api/state').status_code,200)
    def test_workspaces_receipts_and_backups_are_isolated(self):
        alice,aid=self.customer();bob,bid=self.customer();self.activate(aid);self.activate(bid)
        r=alice.post('/api/cards',json={'player':'Private Alice card','sport':'Pokémon','quantity':2,'unit_cost':'10','market_price':'20'})
        self.assertEqual(r.status_code,201)
        card=r.json['id']
        sale=alice.post('/api/sales',json={'card_id':card,'quantity':1,'unit_price':'20','sold_on':'2025-01-01'}).json['id']
        self.assertEqual(bob.get('/api/state').json['cards'],[])
        self.assertEqual(bob.get(f'/receipts/{sale}').status_code,404)
        self.assertEqual(bob.delete(f'/api/cards/{card}',json={}).status_code,404)
        self.assertNotIn('Private Alice card',bob.get('/api/export/inventory').text)
        self.assertEqual(alice.get('/api/backup').status_code,200)
        self.assertEqual(bob.post(f'/api/cards/{card}/shopify',json={}).status_code,400)
    def test_signed_webhook_and_revocation(self):
        import subscriptions
        customer,identifier=self.customer()
        customer_id='cus_'+identifier
        with self.module.app.extensions['accounts_connection']() as db:db.execute('UPDATE users SET stripe_customer=? WHERE id=?',(customer_id,identifier))
        event={'id':'evt_'+identifier,'type':'customer.subscription.updated','data':{'object':{'customer':customer_id}}}
        body=json.dumps(event).encode();timestamp=int(time.time())
        signature=hmac.new(b'test-webhook-secret',str(timestamp).encode()+b'.'+body,hashlib.sha256).hexdigest()
        self.assertEqual(customer.post('/api/billing/webhook',data=body,content_type='application/json').status_code,400)
        active={'data':[{'status':'active','items':{'data':[{'price':{'id':'price_monthly'}}]}}]}
        with patch.object(subscriptions,'stripe_request',return_value=active):
            response=customer.post('/api/billing/webhook',data=body,content_type='application/json',headers={'Stripe-Signature':f't={timestamp},v1={signature}'})
            self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(customer.get('/api/state').status_code,200)
        event['id']+='cancelled';body=json.dumps(event).encode();signature=hmac.new(b'test-webhook-secret',str(timestamp).encode()+b'.'+body,hashlib.sha256).hexdigest()
        with patch.object(subscriptions,'stripe_request',return_value={'data':[]}):
            self.assertEqual(customer.post('/api/billing/webhook',data=body,content_type='application/json',headers={'Stripe-Signature':f't={timestamp},v1={signature}'}).status_code,200)
        self.assertEqual(customer.get('/api/state').status_code,402)
        self.assertFalse(subscriptions.valid_signature(body,f't={timestamp-1000},v1={signature}','test-webhook-secret'))
    def test_price_enforced_and_logout(self):
        import subscriptions
        customer,identifier=self.customer()
        with patch.object(subscriptions,'stripe_request',return_value={'active':True,'currency':'usd','unit_amount':1000,'recurring':{'interval':'month','interval_count':1}}):
            response=customer.post('/api/billing/checkout',json={})
            self.assertEqual(response.status_code,400)
            self.assertIn('$5',response.json['error'])
        self.assertEqual(customer.post('/api/auth/logout',json={}).status_code,200)
        self.assertEqual(customer.get('/api/auth/me').status_code,401)

    def test_checkout_reuses_pending_session_and_owner_exempt(self):
        import subscriptions
        customer,identifier=self.customer();calls=[]
        def api(path,fields=None):
            calls.append(path)
            if path.startswith('prices/'):
                return {'active':True,'currency':'usd','unit_amount':500,'recurring':{'interval':'month','interval_count':1}}
            if path=='customers':return {'id':'cus_'+identifier}
            if path.startswith('subscriptions?'):return {'data':[]}
            if path=='checkout/sessions':return {'url':'https://checkout.stripe.com/test-session','expires_at':int(time.time())+1800}
            if path=='billing_portal/sessions':return {'url':'https://billing.stripe.com/test-portal'}
            raise AssertionError(path)
        with patch.object(subscriptions,'stripe_request',side_effect=api):
            first=customer.post('/api/billing/checkout',json={});second=customer.post('/api/billing/checkout',json={})
            self.assertEqual(first.status_code,200);self.assertEqual(first.json,second.json)
            self.assertEqual(calls.count('checkout/sessions'),1)
            self.assertEqual(customer.get('/api/state').status_code,402)
            self.assertEqual(customer.post('/api/billing/portal',json={}).status_code,200)
            self.assertEqual(self.owner.post('/api/billing/checkout',json={}).status_code,400)

    def test_password_change_revokes_other_sessions(self):
        customer,identifier=self.customer()
        user=customer.get('/api/auth/me').json['user']
        other=self.module.app.test_client()
        self.assertEqual(other.post('/api/auth/login',json={'email':user['email'],'password':'customer-password-123'}).status_code,200)
        response=customer.post('/api/auth/password',json={'password':'customer-password-123','new_password':'new-customer-password-123'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(other.get('/api/auth/me').status_code,401)
        self.assertEqual(customer.get('/api/auth/me').status_code,200)
