#!/usr/bin/env bash
# =====================================================================
#  Arranque local del Sistema NLP de Reportes Ciudadanos (Linux/Mac)
#  Uso:   bash run.sh
# =====================================================================
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"

echo "== Sistema NLP Reportes Ciudadanos =="

if [ ! -x "$PY" ]; then
  echo "Creando entorno virtual (.venv)..."
  python3 -m venv "$VENV"
fi

echo "Instalando dependencias..."
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
"$PY" -m pip install --quiet flask transformers safetensors

echo "Iniciando servidor en http://127.0.0.1:5000 ..."
cd "$ROOT/app"
exec "$PY" server.py
