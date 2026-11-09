import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from operaciones import Register, bootstrap, restore, daily_backup
from papelera_os import connect, backup, D, xlsx_rows, import_universal, import_delmar, sell, receipt
from escritorio import REPORTS
from informes import sales_report


def workbook(path, rows):
    with ZipFile(path,'w') as zipfile:
        zipfile.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Lista" r:id="r1"/></sheets></workbook>')
        zipfile.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        sheet=ET.Element('worksheet',xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main')
        data=ET.SubElement(sheet,'sheetData')
        for n,values in enumerate(rows,1):
            row=ET.SubElement(data,'row',r=str(n))
            for key,value in values.items():
                cell=ET.SubElement(row,'c',r=key+str(n),t='inlineStr')
                ET.SubElement(ET.SubElement(cell,'is'),'t').text=value
        zipfile.writestr('xl/worksheets/sheet1.xml',ET.tostring(sheet))


class OperatingTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'local.db'
        self.db=connect(self.path)
        self.addCleanup(self.db.close)
        bootstrap(self.db,'dueño','clave-local')
        self.reg=Register(self.db,'dueño','clave-local')
        self.reg.product('001','Bolsa',250,'Bolsas','2')

    def scalar(self,query):
        return self.db.execute(query).fetchone()[0]

    def test_operating_day_offline_then_restart(self):
        with patch('socket.socket',side_effect=AssertionError('Acceso de red')):
            order=self.reg.order('Proveedor','001','5',120)
            self.reg.receive(order,'2','recepción-a')
            self.reg.receive(order,'2','recepción-a')
            self.reg.receive(order,'3','recepción-b')
            with self.assertRaises(ValueError):
                self.reg.receive(order,'1','sobrante')
            self.reg.open_till(1000)
            client=self.reg.customer('Prueba','Comercio')
            sale=self.reg.checkout([('001','3')],{'efectivo':250,'tarjeta':500},client,'venta-1')
            with self.assertRaises(ValueError):
                self.reg.checkout([('001','3')],{'efectivo':750},None,'venta-1')
            self.assertEqual(self.scalar('SELECT stock_qty FROM products'),'2')
            self.reg.cash(-50,'Cambio')
            self.assertEqual(self.reg.close_till(1180),1200)
            self.reg.open_till(300)
            self.reg.reverse(sale['receipt_number'],'Devolución completa')
            with self.assertRaises(ValueError):
                self.reg.reverse(sale['receipt_number'],'Duplicada')
            self.assertEqual(self.reg.close_till(50),50)
            self.assertEqual(self.scalar('SELECT stock_qty FROM products'),'5')
            self.reg.queue_fiscal(sale['receipt_number'])
            self.reg.queue_fiscal(sale['receipt_number'])
            self.assertEqual(self.scalar('SELECT count(*) FROM fiscal_pending'),1)
            for q in REPORTS.values():
                self.db.execute(q).fetchall()
            reopened=connect(self.path)
            try:
                self.assertEqual(reopened.execute('SELECT COUNT(*) FROM reversals').fetchone()[0],1)
                self.assertEqual(reopened.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            finally:
                reopened.close()

    def test_payment_mismatch_rolls_back_every_write(self):
        order=self.reg.order('P','001','2',50)
        self.reg.receive(order,'2','r')
        self.reg.open_till(0)
        with self.assertRaises(ValueError):
            self.reg.checkout([('001','2')],{'efectivo':499},None,'bad')
        self.assertEqual(self.scalar('SELECT count(*) FROM sales'),0)
        self.assertEqual(self.scalar('SELECT stock_qty FROM products'),'2')
        self.assertEqual(self.scalar("SELECT count(*) FROM inventory_movements WHERE kind='sale'"),0)

    def test_accounts(self):
        with self.assertRaises(PermissionError):
            Register(self.db,'dueño','incorrecta')
        self.reg.add_user('caja','clave-caja','vendedor')
        cashier=Register(self.db,'caja','clave-caja')
        for action in (lambda:cashier.threshold('9'),lambda:cashier.order('foo','001','4',20),
                       lambda:cashier.product('002','test',10),lambda:cashier.add_user('x','local-123','administrador')):
            with self.assertRaises(PermissionError):
                action()
        with self.assertRaises(ValueError):
            bootstrap(self.db,'otro','clave-otra')

    def test_verified_restore_and_invalid_snapshot(self):
        target=self.path.with_suffix('.sqlite')
        backup(self.db,target)
        self.reg.product('002','Producto',500)
        safety=restore(self.db,target)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM products'),1)
        safety_db=sqlite3.connect(safety)
        try:
            self.assertEqual(safety_db.execute('SELECT COUNT(*) FROM products').fetchone()[0],2)
        finally:
            safety_db.close()
        wrong=self.path.parent/'otro.db'
        conn=sqlite3.connect(wrong)
        conn.execute('CREATE TABLE products(id)')
        conn.close()
        with self.assertRaises(ValueError):
            restore(self.db,wrong)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM products'),1)
        daily_backup(self.db)
        with self.assertRaises(ValueError):
            backup(self.db,self.path)

    def test_supplier_approval_and_stale_preview(self):
        path=self.path.parent/'supplier.xlsx'
        workbook(path,[{'A':'CODIGO','B':'Bolsas'},{'A':'001','B':'Bulto de prueba','C':'35','D':'30'}])
        self.assertEqual(import_delmar(self.db,path)['possible_matches'],1)
        row=self.scalar('SELECT id FROM supplier_rows')
        first=self.reg.preview_cost(row,'001','10','minor')
        with self.assertRaises(ValueError):
            self.reg.apply_cost(first)
        self.reg.product('001','Bolsa',260)
        with self.assertRaises(ValueError):
            self.reg.apply_cost(first,True)
        fresh=self.reg.preview_cost(row,'001','10','minor')
        self.reg.apply_cost(fresh,True)
        self.assertEqual(self.scalar('SELECT cost_cents FROM products'),350)
        self.assertEqual(self.scalar('SELECT unit_price_cents FROM products'),260)
        with self.assertRaises(ValueError):
            self.reg.apply_cost(fresh,True)
        self.assertEqual(import_delmar(self.db,path)['status'],'already_imported')

    def test_competing_sales_preserve_last_unit(self):
        order=self.reg.order('P','001','1',200)
        self.reg.receive(order,'1','entrada')
        def worker(_):
            db=connect(self.path)
            try:
                try:
                    sell(db,[('001','1')])
                    return True
                except ValueError:
                    return False
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(worker,[1,2])),1)
        self.assertEqual(self.scalar('SELECT stock_qty FROM products'),'0')

    def test_duplicate_opening_preserves_snapshot(self):
        path=self.path.parent/'opening.xlsx'
        workbook(path,[{}, {'B':'CODIGO','C':'Producto'},
                       {'B':'099','C':'Producto','D':'2','F':'4.50','K':'50','M':'2','N':'5'},
                       {'B':'099','C':'Duplicado','N':'55'}])
        db=connect(self.path.parent/'other.db')
        try:
            r=import_universal(db,path)
            self.assertEqual((r['count'],len(r['warnings'])),(1,1))
            self.assertEqual(import_universal(db,path)['status'],'already_imported')
            self.assertEqual(tuple(db.execute('SELECT code,stock_qty,unit_price_cents FROM products').fetchone()),('099','5',450))
        finally:
            db.close()

    def test_invalid_quantities(self):
        for value in ('NaN','Infinity','-Infinity','aaa','1e1000'):
            with self.assertRaises(ValueError):
                D(value)

    def test_changed_prices_cannot_hide_in_same_total(self):
        self.reg.product('002','Caja',250)
        for code in ('001','002'):
            order=self.reg.order('P',code,'2',100)
            self.reg.receive(order,'2','entrada-'+code)
        self.reg.open_till(0)
        self.reg.product('001','Bolsa',200)
        self.reg.product('002','Caja',300)
        with self.assertRaisesRegex(ValueError,'Cambió el precio'):
            self.reg.checkout([('001','1'),('002','1')],{'efectivo':500},None,'vieja',{'001':250,'002':250})
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM sales'),0)
        self.assertEqual(self.scalar("SELECT stock_qty FROM products WHERE code='001'"),'2')
        self.reg.checkout([('001','1'),('002','1')],{'efectivo':500},None,'nueva',{'001':200,'002':300})

    def test_sales_period_state_and_exact_totals(self):
        order=self.reg.order('P','001','5',100)
        self.reg.receive(order,'5','entrada')
        self.reg.open_till(0)
        first=self.reg.checkout([('001','1')],{'efectivo':250},None,'primera')
        second=self.reg.checkout([('001','2')],{'tarjeta':500},None,'segunda')
        with self.db:
            self.db.execute("UPDATE sales SET created_at='2026-10-01T12:00:00+00:00' WHERE id=?",(first['id'],))
            self.db.execute("UPDATE sales SET created_at='2026-11-01T12:00:00+00:00' WHERE id=?",(second['id'],))
        self.reg.reverse(second['receipt_number'],'Prueba')
        rows,totals=sales_report(self.db,'2026-10-01','2026-10-31')
        self.assertEqual(([r['ticket'] for r in rows],totals),([first['receipt_number']],{'confirmed':250,'cancelled':0}))
        rows,totals=sales_report(self.db)
        self.assertEqual(totals,{'confirmed':250,'cancelled':500})
        self.assertEqual(len(sales_report(self.db,state='Registradas')[0]),1)
        self.assertEqual(sales_report(self.db,state='Anuladas')[0][0]['ticket'],second['receipt_number'])
        self.assertEqual(sales_report(self.db,'2027-01-01')[1],{'confirmed':0,'cancelled':0})
        for start,end in [('2026-02-30',''),('2026-11-02','2026-11-01'),('01/11/2026','')]:
            with self.assertRaises(ValueError):
                sales_report(self.db,start,end)

    def test_discount_ticket_report_cash_and_reversal(self):
        order=self.reg.order('P','001','3',100)
        self.reg.receive(order,'3','entrada')
        self.reg.open_till(100)
        sale=self.reg.checkout([('001','2')],{'efectivo':200,'tarjeta':225},None,'venta',discount=75,discount_reason='Atención comercial')
        self.assertEqual((sale['subtotal_cents'],sale['total_cents']),(500,425))
        self.assertIn('DESCUENTO: $ 0.75',receipt(sale))
        self.assertEqual(self.reg.expected(),300)
        rows,totals=sales_report(self.db)
        self.assertEqual((rows[0]['discount_cents'],totals['confirmed']),(75,425))
        self.reg.reverse(sale['receipt_number'],'Devolución')
        self.assertEqual(self.reg.expected(),100)
        self.assertEqual(self.scalar('SELECT stock_qty FROM products'),'3')
        self.assertEqual(sales_report(self.db)[1],{'confirmed':0,'cancelled':425})
        snapshot=self.path.with_suffix('.sqlite')
        backup(self.db,snapshot)
        restore(self.db,snapshot)
        self.assertEqual(self.scalar('SELECT amount FROM sale_discounts'),75)

    def test_invalid_discount_is_atomic_and_requires_admin(self):
        order=self.reg.order('P','001','3',100)
        self.reg.receive(order,'3','entrada')
        self.reg.open_till(0)
        for discount,reason,payment in [(-1,'Motivo',250),(250,'Motivo',1),(251,'Motivo',1),(10,'',240),(10,'Motivo',250),(True,'Motivo',249)]:
            with self.assertRaises(ValueError):
                self.reg.checkout([('001','1')],{'efectivo':payment},None,'rechazada',discount=discount,discount_reason=reason)
            self.assertEqual(self.scalar('SELECT COUNT(*) FROM sales'),0)
            self.assertEqual(self.scalar('SELECT COUNT(*) FROM sale_discounts'),0)
            self.assertEqual(self.scalar('SELECT stock_qty FROM products'),'3')
        self.reg.add_user('caja','clave-caja','vendedor')
        cashier=Register(self.db,'caja','clave-caja')
        with self.assertRaises(PermissionError):
            cashier.checkout([('001','1')],{'efectivo':240},None,'no-autorizada',discount=10,discount_reason='Motivo')
        cashier.checkout([('001','1')],{'efectivo':250},None,'normal')

    def test_upgrade_and_restore_v1_keeps_existing_sales(self):
        order=self.reg.order('P','001','2',100)
        self.reg.receive(order,'2','entrada')
        self.reg.open_till(0)
        sale=self.reg.checkout([('001','1')],{'efectivo':250},None,'original')
        with self.db:
            self.db.execute('DROP TABLE sale_discounts')
            self.db.execute('PRAGMA user_version=1')
        old=self.path.with_suffix('.v1.sqlite')
        backup(self.db,old)
        from operaciones import migrate
        migrate(self.db)
        self.assertEqual(self.scalar('PRAGMA user_version'),2)
        migrate(self.db)
        restore(self.db,old)
        self.assertEqual(self.scalar('PRAGMA user_version'),2)
        self.assertEqual(self.scalar('SELECT id FROM sales'),sale['id'])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM sale_discounts'),0)
        self.assertEqual(sales_report(self.db)[1]['confirmed'],250)
