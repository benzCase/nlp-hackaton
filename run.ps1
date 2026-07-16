# =====================================================================
#  Arranque local del Sistema NLP de Reportes Ciudadanos (Windows)
#  Uso:   .\run.ps1
# =====================================================================
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venv = Join-Path $root ".venv"
$py   = Join-Path $venv "Scripts\python.exe"

Write-Host "== Sistema NLP Reportes Ciudadanos ==" -ForegroundColor Cyan

# 1) Entorno virtual
if (-not (Test-Path $py)) {
    Write-Host "Creando entorno virtual (.venv)..." -ForegroundColor Yellow
    python -m venv $venv
}

# 2) Dependencias
Write-Host "Instalando dependencias..." -ForegroundColor Yellow
& $py -m pip install --quiet --upgrade pip
# torch CPU desde el indice oficial (evita descargas CUDA innecesarias)
& $py -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
& $py -m pip install --quiet flask transformers safetensors

# 3) Arranque
Write-Host "Iniciando servidor en http://127.0.0.1:5000 ..." -ForegroundColor Green
Set-Location (Join-Path $root "app")
& $py server.py
