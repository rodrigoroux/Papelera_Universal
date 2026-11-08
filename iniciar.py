"""Punto de entrada del instalador de escritorio."""
import sys
import traceback
from pathlib import Path
from tkinter import messagebox
from papelera_os import connect, run_gui


def main():
    home=Path.home()/'PapeleraUniversalOS'
    try:
        db=connect(home/'papelera.db')
        try:
            if '--verificar' in sys.argv:
                # Used by the installer acceptance job; includes Tk initialization.
                import tkinter as tk
                from escritorio import REPORTS
                root=tk.Tk()
                for report in REPORTS.values():
                    db.execute(report).fetchone()
                root.update()
                root.destroy()
            else:
                run_gui(db)
        finally:
            db.close()
    except Exception as ex:
        home.mkdir(parents=True,exist_ok=True)
        (home/'error-inicio.log').write_text(traceback.format_exc(),encoding='utf-8')
        if '--verificar' not in sys.argv:
            messagebox.showerror('Papelera Universal',str(ex))
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
