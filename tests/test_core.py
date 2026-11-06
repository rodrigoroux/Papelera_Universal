import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from papelera_os import connect, calculate_price, adjust_stock, sell, backup, receipt

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=connect(Path(self.tmp.name)/"test.sqlite")
        self.db.execute("""INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          ("test1","ABC","Producto de prueba",10000,"2",20000,None,None,None,None,
           "10","10",1,"2026-11-06","2026-11-06"))
        self.db.commit()
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def test_factor_markup_margin(self):
        self.assertEqual(calculate_price(217500,"2.1"),456750)
        self.assertEqual(calculate_price(10000,"80","markup"),18000)
        self.assertEqual(calculate_price(10000,"40","margin"),16667)
        with self.assertRaises(ValueError):
            calculate_price(100,"100","margin")
    def test_sale_deducts_stock(self):
        sale=sell(self.db,[("ABC","2")])
        self.assertEqual(sale["total_cents"],40000)
        self.assertIn("NO FISCAL",receipt(sale))
        self.assertEqual(Decimal(self.db.execute("SELECT stock_qty FROM products").fetchone()[0]),8)
    def test_sale_failure_is_atomic(self):
        with self.assertRaises(ValueError):
            sell(self.db,[("ABC","2"),("INEXISTENTE","1")])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM sales").fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT stock_qty FROM products").fetchone()[0],"10")
    def test_duplicate_item_aggregated(self):
        sell(self.db,[("ABC","2"),("ABC","3")])
        self.assertEqual(self.db.execute("SELECT stock_qty FROM products").fetchone()[0],"5")
    def test_stock_adjustment(self):
        self.assertEqual(adjust_stock(self.db,"ABC","3","conteo"),"13")
        with self.assertRaises(ValueError):
            adjust_stock(self.db,"ABC","-100","conteo")
    def test_backup(self):
        path=Path(self.tmp.name)/"backup.sqlite"
        self.assertEqual(backup(self.db,path),str(path))
        self.assertTrue(path.exists())

if __name__=="__main__":
    unittest.main()
