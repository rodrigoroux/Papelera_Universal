"""Papelera Universal OS v0.1: prototipo local, sin facturación fiscal."""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, uuid, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

M='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS={'m':M,'r':R}
def now(): return datetime.now(timezone.utc).isoformat()
def D(x):
    if x is None or str(x).strip()=='': return Decimal('0')
    return Decimal(str(x).replace(',','.'))
def money(x):
    if x is None or str(x).strip()=='': return None
    try: return int((D(x)*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    except (InvalidOperation,ValueError): return None
def xlsx_rows(path):
    with zipfile.ZipFile(path) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(t.text or '' for t in e.iter() if t.tag.endswith('}t')) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        rels={r.get('Id'):r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sheet in wb.findall('.//m:sheets/m:sheet',NS):
            target=rels.get(sheet.get('{%s}id'%R),'')
            target=target.lstrip('/') if target.startswith('/') else 'xl/'+target.lstrip('/')
            if target not in z.namelist(): continue
            root=ET.fromstring(z.read(target))
            for row in root.findall('.//m:sheetData/m:row',NS):
                v={}
                for cell in row.findall('m:c',NS):
                    k=re.match('[A-Z]+',cell.get('r',''))
                    if not k:continue
                    node=cell.find('m:v',NS)
                    value=node.text if node is not None else None
                    if cell.get('t')=='s' and value is not None:value=shared[int(value)]
                    elif cell.get('t')=='inlineStr':value=''.join(t.text or '' for t in cell.iter() if t.tag.endswith('}t'))
                    if value is not None:v[k.group()]=str(value).strip()
                yield sheet.get('name',''),int(row.get('r')),v

def connect(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(path,timeout=15)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=15000')
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript("""
    CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY,code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,
      cost_cents INTEGER,legacy_factor TEXT,unit_price_cents INTEGER,price3_cents INTEGER,
      price5_cents INTEGER,price50_cents INTEGER,gastro_price_cents INTEGER,
      opening_qty TEXT NOT NULL,stock_qty TEXT NOT NULL,source_row INTEGER,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY,kind TEXT NOT NULL,filename TEXT NOT NULL,
      sha256 TEXT NOT NULL,rows_count INTEGER NOT NULL,imported_at TEXT NOT NULL,UNIQUE(kind,sha256));
    CREATE TABLE IF NOT EXISTS inventory_movements(id TEXT PRIMARY KEY,product_id TEXT NOT NULL REFERENCES products(id),
      qty_delta TEXT NOT NULL,kind TEXT NOT NULL,reference TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS supplier_rows(id TEXT PRIMARY KEY,import_id TEXT NOT NULL REFERENCES imports(id),
      sheet TEXT NOT NULL,row_number INTEGER NOT NULL,category TEXT,supplier_code TEXT NOT NULL,name TEXT NOT NULL,
      minor_cents INTEGER,major_cents INTEGER,product_id TEXT REFERENCES products(id),match_status TEXT NOT NULL,
      UNIQUE(import_id,sheet,row_number));
    CREATE TABLE IF NOT EXISTS sales(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,total_cents INTEGER NOT NULL,
      payment_method TEXT NOT NULL,receipt_number INTEGER NOT NULL UNIQUE);
    CREATE TABLE IF NOT EXISTS sale_items(id TEXT PRIMARY KEY,sale_id TEXT NOT NULL REFERENCES sales(id),
      product_id TEXT NOT NULL REFERENCES products(id),qty TEXT NOT NULL,unit_price_cents INTEGER NOT NULL,total_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,action TEXT NOT NULL,details TEXT NOT NULL,created_at TEXT NOT NULL);
    """)
    return c
def audit(c,action,payload):
    c.execute('INSERT INTO audit VALUES(?,?,?,?)',(str(uuid.uuid4()),action,json.dumps(payload,ensure_ascii=False),now()))
def import_universal(c,path):
    path=Path(path);digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if c.execute("SELECT 1 FROM imports WHERE kind='universal' AND sha256=?",(digest,)).fetchone():
        return {'status':'already_imported','count':0}
    if c.execute('SELECT COUNT(*) FROM products').fetchone()[0]:
        raise ValueError('Base existente: no se permite importar apertura sobre datos operativos')
    data=[];seen=set();warnings=[]
    for sheet,n,v in xlsx_rows(path):
        code=v.get('B','').strip();name=v.get('C','').strip()
        if n<3 or not code or not name or code.upper() in ('CODIGO','TOTAL','TOTALES'):continue
        if code in seen:warnings.append('Código duplicado '+code);continue
        seen.add(code)
        qty=D(v.get('N'))
        if qty<0:warnings.append('Stock negativo '+code)
        data.append((code,name,money(v.get('D')),v.get('E'),money(v.get('F')),
          money(v.get('G')),money(v.get('H')),money(v.get('I')),money(v.get('J')),str(qty),n))
    if not data:raise ValueError('No hay productos reconocibles')
    with c:
        imp=str(uuid.uuid4())
        c.execute('INSERT INTO imports VALUES(?,?,?,?,?,?)',(imp,'universal',path.name,digest,len(data),now()))
        for code,name,cost,factor,price,p3,p5,p50,gastro,qty,n in data:
            pid=str(uuid.uuid4());stamp=now()
            c.execute('INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (pid,code,name,cost,factor,price,p3,p5,p50,gastro,qty,qty,n,stamp,stamp))
            if D(qty)!=0:
                c.execute('INSERT INTO inventory_movements VALUES(?,?,?,?,?,?)',(str(uuid.uuid4()),pid,qty,'opening',imp,stamp))
        audit(c,'import_universal',{'count':len(data),'warnings':warnings})
    return {'status':'imported','count':len(data),'warnings':warnings}
def import_delmar(c,path):
    path=Path(path);digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if c.execute("SELECT 1 FROM imports WHERE kind='delmar' AND sha256=?",(digest,)).fetchone():
        return {'status':'already_imported','count':0}
    rows=[];category=''
    for sheet,n,v in xlsx_rows(path):
        if sheet.lower().startswith('resumen'):continue
        code=v.get('A','').strip();name=v.get('B','').strip()
        if code.upper()=='CODIGO':category=name;continue
        if not re.fullmatch(r'[0-9]+[A-Za-z0-9./-]*',code) or not name:continue
        minor=money(v.get('C'));major=money(v.get('D'))
        if minor is None and major is None:continue
        rows.append((sheet,n,category,code,name,minor,major))
    if not rows:raise ValueError('Lista Del Mar sin productos reconocibles')
    hits=0
    with c:
        imp=str(uuid.uuid4())
        c.execute('INSERT INTO imports VALUES(?,?,?,?,?,?)',(imp,'delmar',path.name,digest,len(rows),now()))
        for sheet,n,category,code,name,minor,major in rows:
            p=c.execute('SELECT id FROM products WHERE code=?',(code,)).fetchone()
            if p:hits+=1
            c.execute('INSERT INTO supplier_rows VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (str(uuid.uuid4()),imp,sheet,n,category,code,name,minor,major,p['id'] if p else None,
                 'possible_code_match' if p else 'unmatched'))
        audit(c,'import_delmar',{'count':len(rows),'possible_matches':hits})
    return {'status':'staged_pending_review','count':len(rows),'possible_matches':hits,
      'message':'No se modificaron costos ni precios'}
def calculate_price(cost_cents,factor,mode='factor'):
    cost=Decimal(cost_cents);f=D(factor)
    if cost<0 or f<0:raise ValueError('Costo o factor negativo')
    if mode=='factor':n=cost*f
    elif mode=='markup':n=cost*(1+f/100)
    elif mode=='margin':
        if f>=100:raise ValueError('Margen bruto inválido')
        n=cost/(1-f/100)
    else:raise ValueError('Modo desconocido')
    return int(n.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def preview_prices(c):
    latest=c.execute("SELECT id FROM imports WHERE kind='delmar' ORDER BY imported_at DESC LIMIT 1").fetchone()
    if not latest:return []
    out=[]
    q="""SELECT s.*,p.name product_name,p.cost_cents,p.unit_price_cents,p.legacy_factor
         FROM supplier_rows s JOIN products p ON p.id=s.product_id WHERE s.import_id=? ORDER BY s.sheet,s.row_number"""
    for r in c.execute(q,(latest['id'],)):
        cost=r['minor_cents'];factor=r['legacy_factor']
        price=calculate_price(cost,factor) if cost is not None and D(factor)>0 else None
        out.append({'supplier_code':r['supplier_code'],'supplier_name':r['name'],
          'product_name':r['product_name'],'old_cost':r['cost_cents'],
          'possible_new_cost':cost,'old_price':r['unit_price_cents'],
          'simulated_price':price,'status':'REQUIERE VALIDAR PRODUCTO Y PRESENTACIÓN'})
    return out
def adjust_stock(c,code,delta,reason):
    qty=D(delta)
    if qty==0:raise ValueError('Cantidad cero')
    if not reason.strip():raise ValueError('Motivo obligatorio')
    with c:
        p=c.execute('SELECT id,stock_qty FROM products WHERE code=?',(str(code),)).fetchone()
        if not p:raise ValueError('Producto inexistente')
        new=D(p['stock_qty'])+qty
        if new<0:raise ValueError('Stock insuficiente')
        c.execute('UPDATE products SET stock_qty=?,updated_at=? WHERE id=?',(str(new),now(),p['id']))
        c.execute('INSERT INTO inventory_movements VALUES(?,?,?,?,?,?)',
            (str(uuid.uuid4()),p['id'],str(qty),'adjustment',reason,now()))
        audit(c,'adjust_stock',{'code':str(code),'delta':str(qty),'reason':reason})
    return str(new)
def sell(c,items,payment='efectivo'):
    if not items:raise ValueError('Carrito vacío')
    basket={}
    for code,qty in items:
        q=D(qty)
        if q<=0:raise ValueError('Cantidad inválida')
        basket[str(code)]=basket.get(str(code),Decimal(0))+q
    with c:
        rows=[];total=0
        for code,q in basket.items():
            p=c.execute('SELECT * FROM products WHERE code=?',(code,)).fetchone()
            if not p:raise ValueError('Código inexistente '+code)
            if p['unit_price_cents'] is None:raise ValueError('Sin precio '+code)
            if D(p['stock_qty'])<q:raise ValueError('Stock insuficiente '+code)
            line=int((Decimal(p['unit_price_cents'])*q).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            rows.append((p,q,line));total+=line
        sid=str(uuid.uuid4())
        number=c.execute('SELECT COALESCE(MAX(receipt_number),0)+1 FROM sales').fetchone()[0]
        c.execute('INSERT INTO sales VALUES(?,?,?,?,?)',(sid,now(),total,payment,number))
        for p,q,line in rows:
            c.execute('INSERT INTO sale_items VALUES(?,?,?,?,?,?)',
                (str(uuid.uuid4()),sid,p['id'],str(q),p['unit_price_cents'],line))
            c.execute('UPDATE products SET stock_qty=?,updated_at=? WHERE id=?',
                (str(D(p['stock_qty'])-q),now(),p['id']))
            c.execute('INSERT INTO inventory_movements VALUES(?,?,?,?,?,?)',
                (str(uuid.uuid4()),p['id'],str(-q),'sale',sid,now()))
        audit(c,'sale',{'id':sid,'receipt_number':number,'total_cents':total})
    return {'id':sid,'receipt_number':number,'total_cents':total,'payment':payment,
      'lines':[(p['code'],str(q),line) for p,q,line in rows]}
def receipt(sale):
    lines=['PAPELERA UNIVERSAL','*** COMPROBANTE INTERNO - NO FISCAL ***',
      'Venta #'+str(sale['receipt_number']),'Medio: '+sale['payment'],'---------------------']
    for code,qty,line in sale['lines']:lines.append('%s x%s $%.2f'%(code,qty,line/100))
    lines.extend(['---------------------','TOTAL: $ %.2f'%(sale['total_cents']/100),
      'NO VALIDO COMO FACTURA FISCAL'])
    return '\n'.join(lines)
def backup(c,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    target=sqlite3.connect(path)
    try:c.backup(target)
    finally:target.close()
    verify=sqlite3.connect(path)
    try:
        if verify.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise RuntimeError('Respaldo corrupto')
    finally:verify.close()
    return str(path)
def run_gui(c):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox,simpledialog
    root=tk.Tk();root.title('Papelera Universal OS · Prototipo NO FISCAL');root.geometry('1160x700')
    top=ttk.Frame(root,padding=12);top.pack(fill='x')
    ttk.Label(top,text='PAPELERA UNIVERSAL OS',font=('Arial',17,'bold')).pack(side='left')
    query=tk.StringVar()
    ttk.Entry(top,textvariable=query,width=37).pack(side='right')
    ttk.Label(top,text='Buscar código / nombre').pack(side='right',padx=8)
    fields=('code','name','cost','price','stock')
    tree=ttk.Treeview(root,columns=fields,show='headings')
    for key,label,width in [('code','Código',120),('name','Producto',560),('cost','Costo',130),
       ('price','Precio venta',130),('stock','Stock',100)]:
        tree.heading(key,text=label);tree.column(key,width=width)
    tree.pack(fill='both',expand=True,padx=12,pady=8)
    status=tk.StringVar(value='Datos locales');ttk.Label(root,textvariable=status).pack()
    def refresh(*_):
        for node in tree.get_children():tree.delete(node)
        t='%'+query.get().strip()+'%'
        data=c.execute('SELECT * FROM products WHERE code LIKE ? OR name LIKE ? ORDER BY name LIMIT 500',(t,t)).fetchall()
        for row in data:
            def fmt(n):return '' if n is None else '$ %.2f'%(n/100)
            tree.insert('','end',values=(row['code'],row['name'],fmt(row['cost_cents']),
              fmt(row['unit_price_cents']),row['stock_qty']))
        status.set('%d productos visibles · SIN FACTURACIÓN FISCAL'%len(data))
    query.trace_add('write',refresh)
    toolbar=ttk.Frame(root,padding=12);toolbar.pack(fill='x')
    def selected():
        picked=tree.selection()
        if not picked:messagebox.showwarning('Atención','Seleccioná un producto');return None
        return str(tree.item(picked[0])['values'][0])
    def load(kind):
        path=filedialog.askopenfilename(filetypes=[('Excel','*.xlsx')])
        if not path:return
        try:
            result=import_universal(c,path) if kind=='universal' else import_delmar(c,path)
            messagebox.showinfo('Importación',json.dumps(result,ensure_ascii=False,indent=2)[:1600]);refresh()
        except Exception as ex:messagebox.showerror('Error',str(ex))
    def stock():
        code=selected()
        if code is None:return
        qty=simpledialog.askstring('Stock','Cantidad (negativa para restar)')
        if qty is None:return
        reason=simpledialog.askstring('Motivo','Motivo del ajuste')
        if reason is None:return
        try:adjust_stock(c,code,qty,reason);refresh()
        except Exception as ex:messagebox.showerror('Error',str(ex))
    def sale():
        code=selected()
        if code is None:return
        qty=simpledialog.askstring('Venta','Cantidad',initialvalue='1')
        if qty is None or not messagebox.askyesno('Confirmar','¿Registrar venta y descontar stock?'):return
        try:messagebox.showinfo('Comprobante NO FISCAL',receipt(sell(c,[(code,qty)])));refresh()
        except Exception as ex:messagebox.showerror('Error',str(ex))
    def simulate():
        vals=preview_prices(c)
        messagebox.showinfo('Simulación',str(len(vals))+' posibles coincidencias; NO SE APLICARON CAMBIOS.\n'+
          '\n'.join(str(x['supplier_code'])+': '+str(x['possible_new_cost'])+' centavos' for x in vals[:15]))
    def save():
        path=filedialog.asksaveasfilename(defaultextension='.sqlite')
        if path:
            try:backup(c,path);messagebox.showinfo('Backup','Guardado y verificado')
            except Exception as ex:messagebox.showerror('Error',str(ex))
    for label,callback in [('Importar Papelera',lambda:load('universal')),('Importar Del Mar',lambda:load('delmar')),
        ('Simular precios',simulate),('Ajustar stock',stock),('Venta rápida',sale),('Respaldar',save)]:
        ttk.Button(toolbar,text=label,command=callback).pack(side='left',padx=4)
    refresh();root.mainloop()
def cli():
    p=argparse.ArgumentParser(description='Papelera Universal OS v0.1')
    p.add_argument('--db',default=str(Path.home()/'PapeleraUniversalOS'/'papelera.db'))
    sp=p.add_subparsers(dest='action',required=True)
    for name in ('import-universal','import-delmar','backup'):
        x=sp.add_parser(name);x.add_argument('path')
    for name in ('gui','stats','preview-prices'):sp.add_parser(name)
    x=sp.add_parser('search');x.add_argument('term')
    x=sp.add_parser('adjust-stock');x.add_argument('code');x.add_argument('delta');x.add_argument('reason')
    x=sp.add_parser('sell');x.add_argument('code');x.add_argument('qty')
    args=p.parse_args();c=connect(args.db)
    if args.action=='gui':run_gui(c);return
    if args.action=='import-universal':result=import_universal(c,args.path)
    elif args.action=='import-delmar':result=import_delmar(c,args.path)
    elif args.action=='backup':result={'backup':backup(c,args.path)}
    elif args.action=='stats':result={'products':c.execute('SELECT COUNT(*) FROM products').fetchone()[0],
      'sales':c.execute('SELECT COUNT(*) FROM sales').fetchone()[0],
      'supplier_rows':c.execute('SELECT COUNT(*) FROM supplier_rows').fetchone()[0]}
    elif args.action=='preview-prices':result=preview_prices(c)
    elif args.action=='search':
        q='%'+args.term+'%'
        result=[dict(r) for r in c.execute('SELECT code,name,cost_cents,unit_price_cents,stock_qty FROM products WHERE code LIKE ? OR name LIKE ? ORDER BY name',(q,q))]
    elif args.action=='adjust-stock':result={'stock':adjust_stock(c,args.code,args.delta,args.reason)}
    elif args.action=='sell':result=receipt(sell(c,[(args.code,args.qty)]))
    print(result if isinstance(result,str) else json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':cli()
