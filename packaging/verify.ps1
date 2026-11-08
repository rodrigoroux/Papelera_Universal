# Verificación en un perfil Windows descartable.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$install = Join-Path $env:TEMP "PapeleraValidacion"
$env:USERPROFILE = Join-Path $env:TEMP ("PapeleraPerfil-" + [guid]::NewGuid())
New-Item -ItemType Directory $env:USERPROFILE | Out-Null
function Run-Checked($file, $arguments) {
  $proc = Start-Process -FilePath $file -ArgumentList $arguments -PassThru -Wait
  if ($proc.ExitCode -ne 0) { throw "Falló $file ($($proc.ExitCode))." }
}
$setup = (Resolve-Path "release/PapeleraUniversalOS-Setup-x64.exe").Path
$exe = Join-Path $install "PapeleraUniversalOS.exe"
$flags = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=`"$install`""
Run-Checked $setup $flags
Run-Checked $exe "--verificar"
@'
from pathlib import Path
from papelera_os import connect
from operaciones import bootstrap, Register
db = connect(Path.home() / "PapeleraUniversalOS" / "papelera.db")
bootstrap(db, "prueba", "clave-sintetica")
reg = Register(db, "prueba", "clave-sintetica")
reg.product("QA", "Producto de validación", 300)
order = reg.order("Proveedor", "QA", "5", 100)
reg.receive(order, "5", "recepcion")
reg.open_till(0)
reg.checkout([("QA","2")], {"efectivo":600}, None, "venta")
reg.close_till(600)
db.close()
'@ | python -
if ($LASTEXITCODE) { throw "Falló la preparación de datos" }
Run-Checked $setup $flags
Run-Checked $exe "--verificar"
@'
import sqlite3
from pathlib import Path
db = sqlite3.connect(Path.home() / "PapeleraUniversalOS" / "papelera.db")
assert db.execute("select stock_qty from products where code='QA'").fetchone() == ("3",)
assert db.execute("select total_cents from sales").fetchone() == (600,)
assert db.execute("pragma integrity_check").fetchone() == ("ok",)
db.close()
'@ | python -
if ($LASTEXITCODE) { throw "Falló la verificación posterior a la reinstalación" }
