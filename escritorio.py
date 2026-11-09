"""Interfaz local de Papelera Universal OS."""
import csv
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
from decimal import Decimal

from papelera_os import D, receipt, import_universal, import_delmar, adjust_stock, backup
from operaciones import Register, bootstrap, daily_backup, restore, uid
from informes import sales_report


def pesos(cents):
    return '' if cents is None else f'{Decimal(cents)/100:.2f}'


def cents(value):
    number=D(value)*100
    if value is None or not str(value).strip() or number!=number.to_integral_value():
        raise ValueError('Ingresá un importe en pesos con hasta dos decimales')
    return int(number)


class Form(simpledialog.Dialog):
    def __init__(self,root,title,fields):
        self.fields=fields
        self.entries=[]
        super().__init__(root,title)

    def body(self,frame):
        for i,(label,default) in enumerate(self.fields):
            ttk.Label(frame,text=label).grid(row=i,column=0,sticky='w',padx=6,pady=5)
            if isinstance(default,tuple):
                entry=ttk.Combobox(frame,values=default,state='readonly',width=32)
                entry.current(0)
            else:
                entry=ttk.Entry(frame,width=35,show='*' if 'clave' in label.lower() else '')
                entry.insert(0,default)
            entry.grid(row=i,column=1,padx=6,pady=5)
            self.entries.append(entry)
        return self.entries[0]

    def apply(self):
        self.result=[e.get().strip() for e in self.entries]


class Cancelled(Exception):
    pass


def form(root,title,*fields):
    result=Form(root,title,fields).result
    if result is None:
        raise Cancelled()
    return result


class Desk:
    def __init__(self,root,service):
        self.root,self.service,self.db=root,service,service.db
        self.basket={}
        self.query=tk.StringVar()
        self.status=tk.StringVar()
        root.title('Papelera Universal OS')
        root.geometry('1080x710')
        root.minsize(800,540)
        top=ttk.Frame(root,padding=12)
        top.pack(fill='x')
        ttk.Label(top,text='Papelera Universal',font=('Segoe UI',19,'bold')).pack(side='left')
        ttk.Label(top,text=service.actor+' · '+service.role).pack(side='right')
        self.tabs=ttk.Notebook(root)
        self.tabs.pack(fill='both',expand=True,padx=12)
        self.catalog=self.tab('Productos')
        bar=ttk.Frame(self.catalog)
        bar.pack(fill='x')
        ttk.Label(bar,text='Buscar código o nombre').pack(side='left')
        entry=ttk.Entry(bar,textvariable=self.query)
        entry.pack(side='left',fill='x',expand=True,padx=8)
        self.products=self.grid(self.catalog,['Código','Producto','Categoría','Precio $','Stock','Estado'])
        self.buttons(self.catalog,[('Agregar al carrito',self.add),('Editar',self.edit),('Nuevo producto',lambda:self.edit(True)),('Ajustar stock',self.adjust)])
        self.pos=self.tab('Venta y caja')
        self.cart=self.grid(self.pos,['Código','Producto','Cantidad','Precio $','Subtotal $'])
        self.total=tk.StringVar()
        ttk.Label(self.pos,textvariable=self.total,font=('Segoe UI',16,'bold')).pack(anchor='e')
        self.buttons(self.pos,[('Quitar línea',self.remove),('Cobrar',self.pay),('Abrir caja',self.open),('Ingreso / egreso',self.cash),('Cerrar caja',self.close),('Anular venta',self.reverse)])
        self.buy=self.tab('Compras')
        self.orders=self.grid(self.buy,['Pedido','Proveedor','Código','Producto','Pedido (uds.)','Recibido','Costo unit. $'])
        self.buttons(self.buy,[('Nuevo pedido',self.order),('Recibir selección',self.receive)])
        self.people=self.tab('Clientes')
        self.clients=self.grid(self.people,['ID','Nombre','Segmento','Identificación fiscal','Condiciones'])
        self.buttons(self.people,[('Nuevo cliente',self.customer)])
        self.imports=self.tab('Importaciones')
        self.filter_supplier=tk.StringVar()
        ttk.Label(self.imports,text='Buscar en la última lista del proveedor').pack(anchor='w')
        ttk.Entry(self.imports,textvariable=self.filter_supplier).pack(fill='x')
        self.rows=self.grid(self.imports,['Código','Descripción del proveedor','Menor $','Mayor $','Estado'])
        self.buttons(self.imports,[('Importar apertura',lambda:self.load(True)),('Importar Del Mar',lambda:self.load(False)),('Revisar y aplicar fila',self.review),('Umbral de alerta',self.threshold)])
        self.reports=self.tab('Historial')
        self.report=tk.StringVar(value='Ventas')
        picker=ttk.Combobox(self.reports,textvariable=self.report,values=list(REPORTS),state='readonly')
        picker.pack(anchor='w')
        picker.bind('<<ComboboxSelected>>',lambda e:self.show_report())
        filters=ttk.Frame(self.reports)
        filters.pack(fill='x')
        self.date_start=tk.StringVar()
        self.date_end=tk.StringVar()
        self.sale_state=tk.StringVar(value='Todas')
        for label,var in [('Desde AAAA-MM-DD',self.date_start),('Hasta AAAA-MM-DD',self.date_end)]:
            ttk.Label(filters,text=label).pack(side='left')
            ttk.Entry(filters,textvariable=var,width=12).pack(side='left',padx=4)
        ttk.Combobox(filters,textvariable=self.sale_state,values=('Todas','Registradas','Anuladas'),state='readonly',width=13).pack(side='left')
        ttk.Button(filters,text='Aplicar',command=lambda:self.action(self.show_report)).pack(side='left')
        self.report_total=tk.StringVar()
        ttk.Label(self.reports,textvariable=self.report_total).pack(anchor='w')
        self.history=self.grid(self.reports,['Detalle'])
        self.buttons(self.reports,[('Exportar CSV',self.export),('Reimprimir ticket',self.reprint),('Solicitud fiscal pendiente',self.pending)])
        self.control=self.tab('Respaldo y usuarios')
        self.buttons(self.control,[('Crear respaldo',self.save),('Restaurar respaldo',self.restore),('Alta de usuario',self.user)])
        ttk.Label(root,textvariable=self.status,padding=8).pack(anchor='w')
        self.query.trace_add('write',lambda *_:self.find())
        self.filter_supplier.trace_add('write',lambda *_:self.find_supplier())
        entry.focus_set()
        self.refresh()

    def tab(self,label):
        frame=ttk.Frame(self.tabs,padding=9)
        self.tabs.add(frame,text=label)
        return frame

    def grid(self,frame,labels):
        area=ttk.Frame(frame)
        area.pack(fill='both',expand=True)
        tree=ttk.Treeview(area,columns=labels,show='headings',selectmode='browse')
        for label in labels:
            tree.heading(label,text=label)
            tree.column(label,width=165 if 'Producto' in label or 'Descripción' in label else 90,minwidth=45)
        scroll=ttk.Scrollbar(area,command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        tree.pack(fill='both',expand=True)
        return tree

    def buttons(self,parent,buttons):
        frame=ttk.Frame(parent,padding=4)
        frame.pack(fill='x')
        for label,callback in buttons:
            ttk.Button(frame,text=label,command=lambda f=callback:self.action(f)).pack(side='left',padx=2)

    def action(self,f):
        try:
            f()
            if self.root.winfo_exists():
                self.refresh()
        except Cancelled:
            pass
        except Exception as ex:
            messagebox.showerror('Operación',str(ex),parent=self.root)

    def ask(self,title,*fields):
        return form(self.root,title,*fields)

    def pick(self,tree):
        if not tree.selection():
            raise ValueError('Seleccioná una fila')
        return tree.selection()[0]

    def find(self):
        self.products.delete(*self.products.get_children())
        q='%'+self.query.get().strip()+'%'
        for r in self.db.execute("""SELECT p.*, d.category,COALESCE(d.active,1) enabled FROM products p
                LEFT JOIN product_details d ON d.product=p.id WHERE code LIKE ? OR name LIKE ? OR category LIKE ? ORDER BY name LIMIT 500""",(q,q,q)):
            self.products.insert('','end',iid=r['id'],values=(r['code'],r['name'],r['category'] or '',pesos(r['unit_price_cents']),r['stock_qty'],'Activo' if r['enabled'] else 'Inactivo'))

    def find_supplier(self):
        self.rows.delete(*self.rows.get_children())
        q='%'+self.filter_supplier.get()+'%'
        for r in self.db.execute("""SELECT * FROM supplier_rows WHERE import_id=(SELECT id FROM imports WHERE kind='delmar'
                    ORDER BY imported_at DESC LIMIT 1) AND (supplier_code LIKE ? OR name LIKE ?) ORDER BY sheet,row_number LIMIT 500""",(q,q)):
            self.rows.insert('','end',iid=r['id'],values=(r['supplier_code'],r['name'],pesos(r['minor_cents']),pesos(r['major_cents']),r['match_status']))

    def refresh(self):
        self.find()
        self.find_supplier()
        for tree,sql in [(self.orders,"SELECT o.id,s.name,p.code,p.name,o.quantity,o.received,o.unit_cost FROM orders o JOIN suppliers s ON s.id=o.supplier JOIN products p ON p.id=o.product ORDER BY o.id DESC"),
                         (self.clients,'SELECT * FROM customers ORDER BY name')]:
            tree.delete(*tree.get_children())
            for r in self.db.execute(sql):
                vals=list(r)
                if tree is self.orders:
                    vals[-1]=pesos(vals[-1])
                tree.insert('','end',iid=str(r[0]),values=vals)
        self.cart.delete(*self.cart.get_children())
        self.cart_prices={}
        total=0
        from decimal import ROUND_HALF_UP
        for code,q in self.basket.items():
            p=self.db.execute('SELECT name,unit_price_cents FROM products WHERE code=?',(code,)).fetchone()
            if p is None or p[1] is None:
                raise ValueError('Artículo sin precio vigente: '+code)
            line=int((q*p[1]).quantize(Decimal(1),rounding=ROUND_HALF_UP))
            total+=line
            self.cart_prices[code]=p[1]
            self.cart.insert('','end',iid=code,values=(code,p[0],str(q),pesos(p[1]),pesos(line)))
        self.amount=total
        self.total.set('Total $ '+pesos(total))
        opened=self.db.execute('SELECT id FROM tills WHERE closed IS NULL').fetchone()
        self.status.set(('Caja abierta #'+str(opened[0]) if opened else 'Caja cerrada')+'    ·    Comprobantes internos NO FISCALES')
        self.show_report()

    def product(self):
        return self.db.execute('SELECT * FROM products WHERE id=?',(self.pick(self.products),)).fetchone()

    def edit(self,new=False):
        self.service.admin()
        p=None if new else self.product()
        extra=None if new else self.db.execute('SELECT * FROM product_details WHERE product=?',(p['id'],)).fetchone()
        fields=[('Nombre',p['name'] if p else ''),('Precio unitario $',pesos(p['unit_price_cents']) if p else ''),('Categoría',extra['category'] if extra else ''),('Stock mínimo',extra['minimum'] if extra else '0'),('Estado',('Inactivo','Activo') if extra and not extra['active'] else ('Activo','Inactivo'))]
        if new:
            fields.insert(0,('Código',''))
        values=self.ask('Producto',*fields)
        code=values.pop(0) if new else p['code']
        if new and self.db.execute('SELECT 1 FROM products WHERE code=?',(code,)).fetchone():
            raise ValueError('El código ya existe')
        name,price,category,minimum,state=values
        if messagebox.askyesno('Producto','¿Guardar los cambios?'):
            self.service.product(code,name,cents(price),category,minimum,state=='Activo')

    def adjust(self):
        self.service.admin()
        code=self.product()['code']
        q,reason=self.ask('Ajuste de '+code,('Cantidad (+ / −)',''),('Motivo',''))
        adjust_stock(self.db,code,q,self.service.actor+' · '+reason) if reason else self.invalid('Motivo obligatorio')

    def invalid(self,text):
        raise ValueError(text)

    def add(self):
        p=self.product()
        if p['unit_price_cents'] is None:
            raise ValueError('El artículo no tiene precio')
        q=D(self.ask('Agregar '+p['code'],('Cantidad en unidades base','1'))[0])
        if q<=0:
            raise ValueError('Cantidad inválida')
        self.basket[p['code']]=self.basket.get(p['code'],Decimal(0))+q
        self.tabs.select(self.pos)

    def remove(self):
        del self.basket[self.pick(self.cart)]

    def pay(self):
        self.service.till()
        if not self.basket:
            raise ValueError('Carrito vacío')
        expected_prices=dict(self.cart_prices)
        clients=['Consumidor final']+[f"{r[0]} · {r[1]}" for r in self.db.execute('SELECT id,name FROM customers ORDER BY name')]
        cash,card,transfer,customer=self.ask('Cobrar $ '+pesos(self.amount),('Efectivo $',pesos(self.amount)),('Tarjeta $','0'),('Transferencia $','0'),('Cliente',tuple(clients)))
        pays={k:cents(v) for k,v in zip(('efectivo','tarjeta','transferencia'),(cash,card,transfer)) if D(v)!=0}
        if messagebox.askyesno('Confirmar venta','¿Registrar el cobro de $ '+pesos(self.amount)+'?'):
            try:
                data=self.service.checkout(list(self.basket.items()),pays,None if customer==clients[0] else int(customer.split(' · ')[0]),uid(),expected_prices)
            except ValueError:
                self.refresh()
                raise
            self.basket.clear()
            messagebox.showinfo('Ticket interno',receipt(data))

    def open(self):
        self.service.open_till(cents(self.ask('Abrir caja',('Efectivo inicial $','0'))[0]))

    def close(self):
        counted=cents(self.ask('Arqueo',('Efectivo contado $',''))[0])
        expected=self.service.expected()
        if messagebox.askyesno('Cerrar caja',f'Esperado $ {pesos(expected)} · Diferencia $ {pesos(counted-expected)}. ¿Cerrar?'):
            self.service.close_till(counted)

    def cash(self):
        amount,reason=self.ask('Movimiento',('Importe firmado $',''),('Motivo',''))
        self.service.cash(cents(amount),reason)

    def reverse(self):
        number,reason=self.ask('Anular venta completa',('Número de ticket',''),('Motivo',''))
        if messagebox.askyesno('Anulación','¿Devolver todos los artículos y revertir los medios de pago originales?'):
            self.service.reverse(int(number),reason)

    def order(self):
        name,code,q,price=self.ask('Nuevo pedido',('Proveedor',''),('Código interno',''),('Cantidad en unidades base',''),('Costo por unidad $',''))
        self.service.order(name,code,q,cents(price))

    def receive(self):
        key=int(self.pick(self.orders))
        q=self.ask('Recepción del pedido '+str(key),('Cantidad recibida en unidades base',''))[0]
        if messagebox.askyesno('Recepción',f'¿Ingresar {q} unidades al stock?'):
            self.service.receive(key,q,uid())

    def customer(self):
        self.service.customer(*self.ask('Cliente',('Nombre',''),('Segmento',('Retail','Comercio','Mayorista')),('CUIT / identificación',''),('Condiciones','')))

    def load(self,opening):
        self.service.admin()
        path=filedialog.askopenfilename(filetypes=[('Excel','*.xlsx')])
        if path and messagebox.askyesno('Importación','¿Importar el stock de apertura?' if opening else '¿Cargar la lista para revisión?'):
            result=(import_universal if opening else import_delmar)(self.db,path)
            messagebox.showinfo('Importación',f"Filas cargadas: {result['count']}\nEstado: {result['status']}\n"+'\n'.join(result.get('warnings',[])[:20]))

    def review(self):
        key=self.pick(self.rows)
        code,units,tier,mode,rate=self.ask('Vincular presentación',('Código interno confirmado',''),('Unidades base por presentación',''),('Escala',('minor','major')),('Precio de venta',('Conservar','factor','markup','margin')),('Valor de la regla',''))
        if mode!='Conservar' and not rate:
            raise ValueError('Indicá el valor de la regla')
        r=self.service.preview_cost(key,code,units,tier,'' if mode=='Conservar' else mode,rate)
        msg=f"{r['source_name']} → {r['name']} ({units} unidades).\nCosto $ {pesos(r['old_cost'])} → {pesos(r['new_cost'])}\nPrecio $ {pesos(r['old_price'])} → {pesos(r['new_price'])}"
        if messagebox.askyesno('Confirmar equivalencia y cambio',msg) and (not r['alert'] or messagebox.askyesno('Alerta de costo','Variación significativa o sin referencia. ¿Autorizar expresamente?')):
            self.service.apply_cost(r,confirm_alert=r['alert'])

    def threshold(self):
        self.service.threshold(self.ask('Alerta',('Variación límite (%)',''))[0])

    def report_data(self):
        if self.report.get()=='Ventas':
            rows,totals=sales_report(self.db,self.date_start.get().strip(),self.date_end.get().strip(),self.sale_state.get())
            self.report_total.set(f"{len(rows)} ventas · Registradas $ {pesos(totals['confirmed'])} · Anuladas $ {pesos(totals['cancelled'])}. Fecha de venta; las anuladas se excluyen del total registrado.")
            return ['Ticket','Fecha','Cliente','Total $','Medio','Estado'],[(r['ticket'],r['fecha'],r['cliente'],pesos(r['total_cents']),r['medio'],r['estado']) for r in rows]
        self.report_total.set('Vista: primeras 500 filas. CSV: todas las filas. Los filtros de fecha y estado se aplican a Ventas.')
        sql=REPORTS[self.report.get()]
        rows=self.db.execute(sql)
        return [c[0] for c in rows.description],rows

    def show_report(self):
        labels,rows=self.report_data()
        self.history.delete(*self.history.get_children())
        self.history.configure(columns=labels)
        for label in labels:
            self.history.heading(label,text=label)
            self.history.column(label,width=105,minwidth=40)
        import itertools
        for row in itertools.islice(rows,500):
            self.history.insert('','end',values=[v if v is not None else '' for v in row])
        if self.report.get()=='Ventas' and len(rows)>500:
            self.report_total.set(self.report_total.get()+' Vista: primeras 500; CSV completo.')

    def export(self):
        labels,rows=self.report_data()
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV para Excel','*.csv')])
        if path:
            with open(path,'w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f,delimiter=';')
                w.writerow(labels)
                for r in rows:
                    w.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in r])

    def reprint(self):
        number=self.ask('Reimprimir',('Número de ticket',''))[0]
        s=self.db.execute('SELECT * FROM sales WHERE receipt_number=?',(number,)).fetchone()
        if not s:
            raise ValueError('Venta inexistente')
        lines=self.db.execute('SELECT p.code,i.qty,i.total_cents FROM sale_items i JOIN products p ON p.id=i.product_id WHERE sale_id=?',(s['id'],)).fetchall()
        messagebox.showinfo('Ticket interno',receipt(dict(s,payment=s['payment_method'],lines=lines)))

    def pending(self):
        self.service.queue_fiscal(int(self.ask('Solicitud pendiente de ARCA',('Número de ticket',''))[0]))
        messagebox.showinfo('Solicitud guardada','Pendiente local. No se emitió factura ni CAE.')

    def save(self):
        self.service.admin()
        path=filedialog.asksaveasfilename(defaultextension='.sqlite')
        if path:
            backup(self.db,path)
            messagebox.showinfo('Respaldo','Copia verificada')

    def restore(self):
        self.service.admin()
        path=filedialog.askopenfilename(filetypes=[('SQLite','*.sqlite *.db')])
        if path and messagebox.askyesno('Restaurar','¿Reemplazar los datos actuales con la copia? Se guardará un respaldo previo y se cerrará la aplicación.'):
            safety=restore(self.db,path)
            messagebox.showinfo('Restauración','Restauración completada. Copia previa: '+str(safety))
            self.root.destroy()
            raise Cancelled()

    def user(self):
        self.service.add_user(*self.ask('Alta de usuario',('Usuario',''),('Clave',''),('Rol',('vendedor','administrador'))))


REPORTS={
    'Ventas':"""SELECT s.receipt_number Ticket,datetime(s.created_at,'localtime') Fecha,coalesce(k.name,'Consumidor final') Cliente,
            printf('%.2f',s.total_cents/100.0) 'Total $',s.payment_method Medio,CASE WHEN r.sale IS NULL THEN 'Registrada' ELSE 'Anulada' END Estado
            FROM sales s LEFT JOIN checkouts c ON c.sale=s.id LEFT JOIN customers k ON k.id=c.customer LEFT JOIN reversals r ON r.sale=s.id ORDER BY s.receipt_number DESC""",
    'Caja':"""SELECT id Caja,opened Apertura,closed Cierre,opening/100.0 'Inicial $',expected/100.0 'Esperado $',counted/100.0 'Contado $',(counted-expected)/100.0 'Diferencia $' FROM tills ORDER BY id DESC""",
    'Stock crítico':"""SELECT code Código,name Producto,stock_qty Stock,coalesce(minimum,'0') Mínimo FROM products LEFT JOIN product_details ON product=id WHERE CAST(stock_qty AS REAL)<=CAST(coalesce(minimum,'0') AS REAL) ORDER BY name""",
    'Movimientos':"""SELECT created_at Fecha,code Código,kind Movimiento,qty_delta Cantidad,reference Referencia FROM inventory_movements JOIN products ON products.id=product_id ORDER BY inventory_movements.rowid DESC""".replace('SELECT created_at','SELECT inventory_movements.created_at'),
    'Costos aprobados':"""SELECT c.created Fecha,p.code Código,old_cost/100.0 'Anterior $',new_cost/100.0 'Nuevo $',actor Usuario FROM cost_reviews c JOIN products p ON p.id=c.product ORDER BY c.rowid DESC""",
    'Pendientes fiscales':"""SELECT receipt_number Ticket,f.created Fecha,f.actor Usuario FROM fiscal_pending f JOIN sales s ON s.id=f.sale ORDER BY f.rowid DESC"""
}


def launch(db):
    root=tk.Tk()
    root.withdraw()
    try:
        if not db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            name,pw,repeat=form(root,'Primer ingreso · crear administrador',('Usuario',''),('Clave',''),('Repetir clave',''))
            if pw!=repeat:
                raise ValueError('Las claves no coinciden')
            bootstrap(db,name,pw)
        else:
            name,pw=form(root,'Ingresar a Papelera Universal',('Usuario',''),('Clave',''))
        service=Register(db,name,pw)
        daily_backup(db)
        Desk(root,service)
        root.deiconify()
        root.mainloop()
    except Cancelled:
        root.destroy()
    except Exception as ex:
        messagebox.showerror('Papelera Universal',str(ex),parent=root)
        root.destroy()
