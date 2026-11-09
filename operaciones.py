"""Servicios de operación local. Los importes de este módulo están en centavos."""
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import hmac
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from papelera_os import D, now, audit, backup, calculate_price, sell


def uid():
    return str(uuid.uuid4())


@contextmanager
def transaction(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


SCHEMA = """
CREATE TABLE users(name TEXT PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('administrador','vendedor')), salt BLOB NOT NULL, digest BLOB NOT NULL);
CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, segment TEXT NOT NULL, tax_id TEXT, terms TEXT);
CREATE TABLE suppliers(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE orders(id INTEGER PRIMARY KEY, supplier INTEGER REFERENCES suppliers, product TEXT REFERENCES products, quantity TEXT NOT NULL, received TEXT NOT NULL DEFAULT '0', unit_cost INTEGER NOT NULL, created TEXT NOT NULL);
CREATE TABLE deliveries(id TEXT PRIMARY KEY, purchase INTEGER REFERENCES orders, qty TEXT NOT NULL, actor TEXT REFERENCES users, created TEXT NOT NULL);
CREATE TABLE tills(id INTEGER PRIMARY KEY, opened TEXT NOT NULL, opening INTEGER NOT NULL, closed TEXT, counted INTEGER, expected INTEGER, actor TEXT REFERENCES users);
CREATE UNIQUE INDEX one_open_till ON tills((1)) WHERE closed IS NULL;
CREATE TABLE cash_entries(id TEXT PRIMARY KEY, till INTEGER REFERENCES tills, amount INTEGER NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL, actor TEXT REFERENCES users);
CREATE TABLE checkouts(id TEXT PRIMARY KEY, sale TEXT UNIQUE REFERENCES sales, till INTEGER REFERENCES tills, customer INTEGER REFERENCES customers, actor TEXT REFERENCES users);
CREATE TABLE tenders(sale TEXT REFERENCES sales, method TEXT NOT NULL, amount INTEGER NOT NULL, PRIMARY KEY(sale,method));
CREATE TABLE reversals(sale TEXT PRIMARY KEY REFERENCES sales, till INTEGER REFERENCES tills, reason TEXT NOT NULL, actor TEXT REFERENCES users, created TEXT NOT NULL);
CREATE TABLE product_details(product TEXT PRIMARY KEY REFERENCES products, category TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, minimum TEXT NOT NULL DEFAULT '0');
CREATE TABLE cost_reviews(source TEXT PRIMARY KEY REFERENCES supplier_rows, product TEXT REFERENCES products, units TEXT NOT NULL, tier TEXT NOT NULL, old_cost INTEGER, new_cost INTEGER NOT NULL, old_price INTEGER, new_price INTEGER, actor TEXT REFERENCES users, created TEXT NOT NULL);
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE fiscal_pending(sale TEXT PRIMARY KEY REFERENCES sales, created TEXT NOT NULL, actor TEXT REFERENCES users);
"""


def migrate(db):
    version = db.execute('PRAGMA user_version').fetchone()[0]
    if version == 1:
        return
    if version != 0:
        raise ValueError('Esta base requiere una versión más reciente de la aplicación')
    path = Path(db.execute('PRAGMA database_list').fetchone()[2])
    if db.execute('SELECT EXISTS(SELECT 1 FROM products UNION ALL SELECT 1 FROM imports)').fetchone()[0]:
        backup(db, path.parent / 'respaldos' / ('antes-migracion-' + uid() + '.sqlite'))
    with transaction(db):
        if db.execute('PRAGMA user_version').fetchone()[0] == 0:
            for statement in SCHEMA.split(';'):
                if statement.strip():
                    db.execute(statement)
            db.execute('PRAGMA user_version=1')


def daily_backup(db):
    path = Path(db.execute('PRAGMA database_list').fetchone()[2])
    target = path.parent / 'respaldos' / (datetime.now().date().isoformat() + '.sqlite')
    if not target.exists():
        backup(db, target)


def restore(db, path):
    live = Path(db.execute('PRAGMA database_list').fetchone()[2])
    source = Path(path).resolve(strict=True)
    if source.samefile(live):
        raise ValueError('Elegí una copia distinta de la base actual')
    other = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
    try:
        # Stage the entire snapshot before touching the live connection.
        stage = sqlite3.connect(':memory:')
        try:
            other.backup(stage)
            validate_snapshot(db, stage)
            safety = live.parent / 'respaldos' / ('antes-restaurar-' + uid() + '.sqlite')
            backup(db, safety)
            stage.backup(db)
        finally:
            stage.close()
    finally:
        other.close()
    migrate(db)
    return safety


def validate_snapshot(live, stage):
    if stage.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or stage.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('La copia contiene errores de integridad')
    version = stage.execute('PRAGMA user_version').fetchone()[0]
    if version not in (0, 1):
        raise ValueError('Versión de copia incompatible')
    core = {'imports','products','sales','sale_items','inventory_movements','supplier_rows','audit'}
    required = core if version == 0 else {r[0] for r in live.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    for table in required:
        expected = [(r[1],r[2],r[5]) for r in live.execute(f'PRAGMA table_info("{table}")')]
        actual = [(r[1],r[2],r[5]) for r in stage.execute(f'PRAGMA table_info("{table}")')]
        if expected != actual:
            raise ValueError('Estructura incompatible en ' + table)


def user_record(name, password, role):
    if not name.strip() or len(password) < 8 or role not in ('administrador','vendedor'):
        raise ValueError('Indicá usuario, rol válido y clave de al menos 8 caracteres')
    salt = os.urandom(16)
    return name.strip(), role, salt, hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)


def bootstrap(db, name, password):
    with transaction(db):
        if db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            raise ValueError('Ya existe un administrador')
        db.execute('INSERT INTO users VALUES(?,?,?,?)', user_record(name,password,'administrador'))


class Register:
    def __init__(self, db, name, password):
        row = db.execute('SELECT * FROM users WHERE name=?', (name,)).fetchone()
        if not row or not hmac.compare_digest(row['digest'], hashlib.pbkdf2_hmac('sha256',password.encode(),row['salt'],600000)):
            raise PermissionError('Usuario o clave incorrectos')
        self.db, self.actor = db, name
        self.role = row['role']

    def admin(self):
        if self.role != 'administrador':
            raise PermissionError('Requiere un administrador')

    def log(self, action, **details):
        audit(self.db,action,dict(details,actor=self.actor))

    def add_user(self,name,password,role):
        self.admin()
        with transaction(self.db):
            self.db.execute('INSERT INTO users VALUES(?,?,?,?)',user_record(name,password,role))
            self.log('alta_usuario',usuario=name,rol=role)

    def customer(self, name, segment, tax_id='', terms=''):
        if not name.strip() or segment not in ('Retail','Comercio','Mayorista'):
            raise ValueError('Revisá nombre y segmento')
        with transaction(self.db):
            key = self.db.execute('INSERT INTO customers(name,segment,tax_id,terms) VALUES(?,?,?,?)',(name.strip(),segment,tax_id,terms)).lastrowid
            self.log('cliente',id=key)
        return key

    def product(self,code,name,price,category='',minimum='0',active=True):
        self.admin()
        if not code.strip() or not name.strip() or price < 0 or D(minimum)<0:
            raise ValueError('Revisá código, nombre, precio y mínimo')
        with transaction(self.db):
            p=self.db.execute('SELECT * FROM products WHERE code=?',(code,)).fetchone()
            pid=p['id'] if p else uid()
            if p:
                self.db.execute('UPDATE products SET name=?,unit_price_cents=?,updated_at=? WHERE id=?',(name,price,now(),pid))
            else:
                self.db.execute('INSERT INTO products(id,code,name,unit_price_cents,opening_qty,stock_qty,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(pid,code,name,price,'0','0',now(),now()))
            self.db.execute('INSERT OR REPLACE INTO product_details VALUES(?,?,?,?)',(pid,category,int(active),str(D(minimum))))
            self.log('producto',codigo=code,precio_anterior=p['unit_price_cents'] if p else None,precio=price,activo=active)

    def order(self,supplier,code,quantity,unit_cost):
        self.admin()
        q=D(quantity)
        if not supplier.strip() or q<=0 or unit_cost<0:
            raise ValueError('Revisá proveedor, cantidad y costo')
        with transaction(self.db):
            db=self.db
            p=db.execute('SELECT id FROM products WHERE code=?',(code,)).fetchone()
            if not p:
                raise ValueError('Producto inexistente')
            db.execute('INSERT OR IGNORE INTO suppliers(name) VALUES(?)',(supplier.strip(),))
            key=db.execute('INSERT INTO orders(supplier,product,quantity,unit_cost,created) SELECT id,?,?,?,? FROM suppliers WHERE name=?',(p[0],str(q),unit_cost,now(),supplier.strip())).lastrowid
            self.log('pedido',id=key)
        return key

    def receive(self,order,quantity,request_id):
        self.admin()
        q=D(quantity)
        with transaction(self.db):
            done=self.db.execute('SELECT purchase,qty FROM deliveries WHERE id=?',(request_id,)).fetchone()
            if done:
                if done[0]!=order or D(done[1])!=q:
                    raise ValueError('Referencia de recepción ya utilizada')
                return
            row=self.db.execute('SELECT * FROM orders WHERE id=?',(order,)).fetchone()
            if not row or q<=0 or q+D(row['received'])>D(row['quantity']):
                raise ValueError('Cantidad fuera del saldo pendiente')
            self.db.execute('INSERT INTO deliveries VALUES(?,?,?,?,?)',(request_id,order,str(q),self.actor,now()))
            self.db.execute('UPDATE orders SET received=? WHERE id=?',(str(q+D(row['received'])),order))
            self.move(row['product'],q,'purchase',request_id)
            self.log('recepción',pedido=order,cantidad=str(q))

    def move(self,pid,delta,kind,ref):
        old=self.db.execute('SELECT stock_qty FROM products WHERE id=?',(pid,)).fetchone()[0]
        self.db.execute('UPDATE products SET stock_qty=?,updated_at=? WHERE id=?',(str(D(old)+delta),now(),pid))
        self.db.execute('INSERT INTO inventory_movements VALUES(?,?,?,?,?,?)',(uid(),pid,str(delta),kind,ref,now()))

    def open_till(self,initial):
        if initial<0:
            raise ValueError('Saldo inicial negativo')
        with transaction(self.db):
            if self.db.execute('SELECT 1 FROM tills WHERE closed IS NULL').fetchone():
                raise ValueError('Ya hay una caja abierta')
            self.db.execute('INSERT INTO tills(opened,opening,actor) VALUES(?,?,?)',(now(),initial,self.actor))
            self.log('apertura',inicial=initial)

    def till(self):
        row=self.db.execute('SELECT * FROM tills WHERE closed IS NULL').fetchone()
        if not row:
            raise ValueError('Primero abrí la caja')
        return row

    def cash(self,amount,reason):
        self.admin()
        if not amount or not reason.strip():
            raise ValueError('Indicá importe y motivo')
        with transaction(self.db):
            self.db.execute('INSERT INTO cash_entries VALUES(?,?,?,?,?,?)',(uid(),self.till()['id'],amount,reason,now(),self.actor))
            self.log('movimiento_caja',importe=amount,motivo=reason)

    def checkout(self,items,payments,customer,request_id,expected_prices=None):
        with transaction(self.db):
            if self.db.execute('SELECT 1 FROM checkouts WHERE id=?',(request_id,)).fetchone():
                raise ValueError('Esta venta ya fue registrada')
            till=self.till()['id']
            if expected_prices is not None:
                for code, _ in items:
                    row=self.db.execute('SELECT unit_price_cents FROM products WHERE code=?',(code,)).fetchone()
                    if not row or code not in expected_prices or row[0]!=expected_prices[code]:
                        raise ValueError('Cambió el precio de '+code+'. Revisá el carrito antes de cobrar')
            if not payments or any(k not in ('efectivo','tarjeta','transferencia') or type(v)!=int or v<=0 for k,v in payments.items()):
                raise ValueError('Medios o importes inválidos')
            sale=sell(self.db,items,' + '.join(payments),managed=True)
            if sum(payments.values())!=sale['total_cents']:
                raise ValueError('Los medios de pago deben sumar el total exacto')
            self.db.execute('INSERT INTO checkouts VALUES(?,?,?,?,?)',(request_id,sale['id'],till,customer,self.actor))
            self.db.executemany('INSERT INTO tenders VALUES(?,?,?)',[(sale['id'],k,v) for k,v in payments.items()])
            self.log('cobro',venta=sale['id'])
        return sale

    def reverse(self,number,reason):
        self.admin()
        if not reason.strip():
            raise ValueError('Motivo obligatorio')
        with transaction(self.db):
            till=self.till()['id']
            sale=self.db.execute('SELECT s.id FROM sales s JOIN checkouts c ON c.sale=s.id WHERE receipt_number=?',(number,)).fetchone()
            if not sale or self.db.execute('SELECT 1 FROM reversals WHERE sale=?',(sale[0],)).fetchone():
                raise ValueError('Venta inexistente, anterior a caja o ya anulada')
            self.db.execute('INSERT INTO reversals VALUES(?,?,?,?,?)',(sale[0],till,reason,self.actor,now()))
            for r in self.db.execute('SELECT * FROM sale_items WHERE sale_id=?',(sale[0],)):
                self.move(r['product_id'],D(r['qty']),'reversal',sale[0])
            self.log('anulación',venta=sale[0],motivo=reason)

    def expected(self):
        t=self.till()
        def amount(sql):
            return self.db.execute(sql,(t['id'],)).fetchone()[0] or 0
        cash_in=amount("SELECT SUM(amount) FROM tenders JOIN checkouts USING(sale) WHERE till=? AND method='efectivo'")
        cash_out=amount("SELECT SUM(amount) FROM tenders JOIN reversals USING(sale) WHERE till=? AND method='efectivo'")
        return t['opening']+cash_in-cash_out+amount('SELECT SUM(amount) FROM cash_entries WHERE till=?')

    def close_till(self,counted):
        if counted<0:
            raise ValueError('El arqueo debe ser positivo o cero')
        with transaction(self.db):
            expected=self.expected()
            self.db.execute('UPDATE tills SET closed=?,expected=?,counted=? WHERE id=?',(now(),expected,counted,self.till()['id']))
            self.log('cierre',esperado=expected,contado=counted,diferencia=counted-expected)
        return expected

    def preview_cost(self,source,code,units,tier,mode='',rate=''):
        self.admin()
        if tier not in ('minor','major') or D(units)<=0:
            raise ValueError('Revisá la escala y las unidades por presentación')
        p=self.db.execute('SELECT * FROM products WHERE code=?',(code,)).fetchone()
        s=self.db.execute('SELECT * FROM supplier_rows WHERE id=?',(source,)).fetchone()
        if not p or not s or s[tier+'_cents'] is None or s[tier+'_cents']<=0:
            raise ValueError('Producto, fila o costo inválidos')
        latest=self.db.execute("SELECT id FROM imports WHERE kind='delmar' ORDER BY imported_at DESC LIMIT 1").fetchone()
        if latest[0]!=s['import_id']:
            raise ValueError('La fila pertenece a una lista anterior')
        cost=int((Decimal(s[tier+'_cents'])/D(units)).quantize(Decimal(1),rounding=ROUND_HALF_UP))
        if cost<=0:
            raise ValueError('Costo unitario inferior a un centavo')
        price=calculate_price(cost,rate,mode) if mode else p['unit_price_cents']
        setting=self.db.execute("SELECT value FROM settings WHERE key='alerta_costo'").fetchone()
        limit=D(setting[0]) if setting else Decimal('25')
        old=p['cost_cents']
        change=(Decimal(cost-old)*100/old) if old and old>0 else None
        return dict(source=source,source_name=s['name'],product=p['id'],name=p['name'],code=code,units=str(D(units)),tier=tier,
                    old_cost=old,new_cost=cost,old_price=p['unit_price_cents'],new_price=price,mode=mode,rate=rate,
                    alert=change is None or abs(change)>=limit)

    def apply_cost(self,preview,confirm_alert=False):
        with transaction(self.db):
            fresh=self.preview_cost(*(preview[k] for k in ('source','code','units','tier','mode','rate')))
            if fresh!=preview or (fresh['alert'] and not confirm_alert):
                raise ValueError('La propuesta requiere una revisión actualizada')
            if self.db.execute('SELECT 1 FROM cost_reviews WHERE source=?',(fresh['source'],)).fetchone():
                raise ValueError('La fila ya fue aplicada')
            data=[fresh[k] for k in ('source','product','units','tier','old_cost','new_cost','old_price','new_price')]
            self.db.execute('INSERT INTO cost_reviews VALUES(?,?,?,?,?,?,?,?,?,?)',(*data,self.actor,now()))
            self.db.execute("UPDATE supplier_rows SET product_id=?,match_status='approved' WHERE id=?",(fresh['product'],fresh['source']))
            self.db.execute('UPDATE products SET cost_cents=?,unit_price_cents=?,updated_at=? WHERE id=?',(fresh['new_cost'],fresh['new_price'],now(),fresh['product']))
            self.log('costo_aprobado',**fresh)

    def threshold(self,value):
        self.admin()
        if D(value)<=0:
            raise ValueError('El umbral debe ser positivo')
        with transaction(self.db):
            self.db.execute("INSERT OR REPLACE INTO settings VALUES('alerta_costo',?)",(str(D(value)),))
            self.log('umbral_costo',porcentaje=str(value))

    def queue_fiscal(self,number):
        self.admin()
        with transaction(self.db):
            sale=self.db.execute('SELECT id FROM sales WHERE receipt_number=?',(number,)).fetchone()
            if not sale:
                raise ValueError('Venta inexistente')
            self.db.execute('INSERT OR IGNORE INTO fiscal_pending VALUES(?,?,?)',(sale[0],now(),self.actor))
            self.log('solicitud_fiscal_pendiente',venta=sale[0])
