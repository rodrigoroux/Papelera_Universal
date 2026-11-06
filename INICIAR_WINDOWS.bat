@echo off
cd /d "%~dp0"
py -3 papelera_os.py gui
if errorlevel 1 (
 echo No se pudo abrir Papelera Universal OS. Instala Python 3.10+ con Tkinter.
 pause
)
