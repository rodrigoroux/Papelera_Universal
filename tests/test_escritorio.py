"""Prueba de Tk real en Windows; omisión explícita si no hay pantalla."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from escritorio import Desk
from operaciones import bootstrap, Register
from papelera_os import connect, D


class DesktopTests(unittest.TestCase):
    def test_native_desk_reports_and_cart(self):
        try:
            root=tk.Tk()
        except tk.TclError as ex:
            self.skipTest('Pantalla no disponible: '+str(ex))
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as folder:
            db=connect(Path(folder)/'test.db')
            try:
                bootstrap(db,'prueba','clave-sintetica')
                reg=Register(db,'prueba','clave-sintetica')
                reg.product('QA','Producto de prueba',300)
                order=reg.order('Proveedor','QA','5',100)
                reg.receive(order,'5','entrada')
                reg.open_till(0)
                reg.checkout([('QA','2')],{'efectivo':600},None,'venta')
                desk=Desk(root,reg)
                root.update()
                self.assertEqual(len(desk.history.get_children()),1)
                self.assertIn('Registradas $ 6.00',desk.report_total.get())
                desk.basket={'QA':D('1')}
                desk.refresh()
                self.assertEqual(desk.cart_prices,{'QA':300})
                with patch.object(desk,'ask',side_effect=[['0.50','Promoción'],['2.50','0','0','Consumidor final']]), patch('escritorio.messagebox.askyesno',return_value=True), patch('escritorio.messagebox.showinfo') as info:
                    desk.pay()
                    self.assertIn('DESCUENTO: $ 0.50',info.call_args.args[1])
                    self.assertIn('TOTAL: $ 2.50',info.call_args.args[1])
                self.assertEqual(desk.basket,{})
                with patch.object(desk,'ask',return_value=['2']), patch('escritorio.messagebox.showinfo') as info:
                    desk.reprint()
                    self.assertIn('DESCUENTO: $ 0.50',info.call_args.args[1])
                    self.assertIn('TOTAL: $ 2.50',info.call_args.args[1])
                desk.date_start.set('2099-01-01')
                desk.show_report()
                self.assertEqual(len(desk.history.get_children()),0)
                desk.date_start.set('')
                desk.report.set('Caja')
                desk.show_report()
                self.assertEqual(len(desk.history.get_children()),1)
            finally:
                db.close()
