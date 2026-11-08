$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
function Check-Exit {
  if ($LASTEXITCODE -ne 0) { throw "Falló el comando anterior ($LASTEXITCODE)." }
}
python -m unittest discover -s tests -v
Check-Exit
python -m pip install pyinstaller==6.16.0
Check-Exit
python -m PyInstaller --noconfirm --clean --windowed --onedir --name PapeleraUniversalOS iniciar.py
Check-Exit
$compiler = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
if (!(Test-Path $compiler)) { throw "Se necesita Inno Setup 6 para compilar el instalador." }
& $compiler packaging/setup.iss
Check-Exit
