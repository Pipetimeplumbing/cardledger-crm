import importlib.util
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

class TrackerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ['DATABASE_PATH'] = str(Path(cls.temp.name) / 'test.sqlite')
        spec=importlib.util.spec_from_file_location('tracker_app',Path(__file__).parents[1]/'app.py')
        cls.module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.client=cls.module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        with self.module.connection() as db:
            for table in ('adjustments','sales','purchases','cards','clients'):db.execute(f'DELETE FROM {table}')

    def add_card(self,quantity=3,cost='10.00'):
        r=self.client.post('/api/cards',json=dict(player='Test Player',sport='Baseball',year='2024',brand='Topps',grade='PSA 10',quantity=quantity,unit_cost=cost,market_price='25.00'))
        self.assertEqual(r.status_code,201,r.json)
        return r.json['id']

    def sale(self,card,quantity=1,**extra):
        return self.client.post('/api/sales',json=dict(card_id=card,quantity=quantity,unit_price='25.00',fees='2.50',shipping='3.00',sold_on=date.today().isoformat(),**extra))

    def test_sale_profit_stock_and_client_spend(self):
        card=self.add_card()
        buyer=self.client.post('/api/clients',json=dict(name='Buyer',email='buyer@example.com')).json['id']
        r=self.sale(card,2,client_id=buyer);self.assertEqual(r.status_code,201)
        state=self.client.get('/api/state').json
        self.assertEqual(state['totals']['stock'],1)
        self.assertEqual(state['totals']['cost_value'],1000)
        self.assertEqual(state['totals']['market_value'],2500)
        self.assertEqual(state['totals']['revenue'],5000)
        self.assertEqual(state['totals']['profit'],2450)
        self.assertEqual(state['clients'][0]['spend'],5000)
        self.assertEqual(state['clients'][0]['sale_count'],1)

    def test_overselling_and_invalid_client_are_atomic(self):
        card=self.add_card(1)
        self.assertEqual(self.sale(card,2).status_code,400)
        self.assertEqual(self.sale(card,1,client_id=999).status_code,400)
        state=self.client.get('/api/state').json
        self.assertEqual(state['totals']['stock'],1)
        self.assertEqual(len(state['sales']),0)

    def test_restock_cost_and_rounding_conserve_cents(self):
        card=self.add_card(2,'0.01')
        self.assertEqual(self.client.post(f'/api/cards/{card}/restock',json=dict(quantity=1,unit_cost='0.02')).status_code,200)
        for _ in range(3):self.assertEqual(self.sale(card).status_code,201)
        state=self.client.get('/api/state').json
        self.assertEqual(sum(s['cost_basis'] for s in state['sales']),4)
        self.assertEqual(state['totals']['cost_value'],0)
        self.assertEqual(state['totals']['stock'],0)

    def test_metadata_edit_does_not_change_recorded_cost(self):
        card=self.add_card();self.sale(card)
        r=self.client.patch(f'/api/cards/{card}',json=dict(player='Edited Player',sport='Baseball',market_price='100.00'))
        self.assertEqual(r.status_code,200)
        state=self.client.get('/api/state').json
        self.assertEqual(state['sales'][0]['cost_basis'],1000)
        self.assertEqual(state['totals']['cost_value'],2000)
        self.assertEqual(state['totals']['market_value'],20000)

    def test_bad_amounts_and_dates_are_rejected(self):
        for value in ('NaN','Infinity','-1',True):
            r=self.client.post('/api/cards',json=dict(player='Card',sport='Basketball',quantity=1,unit_cost=value))
            self.assertEqual(r.status_code,400)
        card=self.add_card()
        r=self.client.post('/api/sales',json=dict(card_id=card,quantity=1,sold_on='2999-01-01'))
        self.assertEqual(r.status_code,400)
        self.assertEqual(self.client.get('/api/state').json['totals']['stock'],3)

    def test_backup_and_safe_exports(self):
        self.add_card()
        self.client.post('/api/clients',json=dict(name='=dangerous formula',phone='+14015550123'))
        export=self.client.get('/api/export/clients')
        self.assertEqual(export.status_code,200)
        self.assertIn("'=dangerous formula",export.text)
        self.assertIn("'+14015550123",export.text)
        for kind in ('inventory','sales'):self.assertEqual(self.client.get('/api/export/'+kind).status_code,200)
        backup=self.client.get('/api/backup')
        self.assertEqual(backup.status_code,200)
        path=Path(self.temp.name)/'backup.sqlite';path.write_bytes(backup.data)
        with sqlite3.connect(path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM cards').fetchone()[0],1)

    def test_origin_and_non_json_protection(self):
        self.assertEqual(self.client.post('/api/clients',json=dict(name='Test'),headers={'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/clients',data='name=Test').status_code,415)

    def test_persisted_database_can_be_reopened(self):
        card=self.add_card()
        with sqlite3.connect(self.module.DB) as db:
            self.assertEqual(db.execute('SELECT quantity FROM cards WHERE id=?',(card,)).fetchone()[0],3)
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        response.close()

    def test_remove_stock_and_category_controls(self):
        card=self.add_card(3,'10.00')
        previous=self.client.get('/api/state').json['revision']
        self.assertEqual(self.client.post(f'/api/cards/{card}/remove-stock',json=dict(quantity=4,reason='Damaged')).status_code,400)
        self.assertEqual(self.client.post(f'/api/cards/{card}/remove-stock',json=dict(quantity=1,reason='Damaged')).status_code,200)
        state=self.client.get('/api/state').json
        self.assertEqual(state['totals']['stock'],2)
        self.assertEqual(state['totals']['cost_value'],2000)
        self.assertEqual(state['totals']['profit'],0)
        self.assertEqual(state['adjustments'][0]['cost_removed'],1000)
        self.assertGreater(state['revision'],previous)
        self.assertEqual(self.client.delete('/api/categories',json=dict(name='Baseball')).status_code,400)
        self.assertEqual(self.client.post('/api/categories',json=dict(name='Custom category')).status_code,201)
        self.assertEqual(self.client.delete('/api/categories',json=dict(name='Custom category')).status_code,200)
        self.assertNotIn('Custom category',self.client.get('/api/state').json['categories'])

    def test_subset_serial_and_grading_certificate(self):
        payload=dict(player='Test Player',sport='Baseball',quantity=1,unit_cost='10',market_price='20',subset='Silver Prizm',grade='PSA 10',serial_number='025/199',cert_number='001234567890')
        response=self.client.post('/api/cards',json=payload)
        self.assertEqual(response.status_code,201)
        card=response.json['id']
        saved=self.client.get('/api/state').json['cards'][0]
        for key in ('subset','grade','serial_number','cert_number'):self.assertEqual(saved[key],payload[key])
        payload['subset']='Gold Prizm'
        self.assertEqual(self.client.patch(f'/api/cards/{card}',json=payload).status_code,200)
        self.assertEqual(self.sale(card).status_code,201)
        sale=self.client.get('/api/state').json['sales'][0]
        self.assertEqual(sale['subset'],'Gold Prizm')
        self.assertEqual(sale['cert_number'],'001234567890')
        self.assertIn('025/199',self.client.get('/api/export/inventory').text)

if __name__=='__main__':unittest.main()
