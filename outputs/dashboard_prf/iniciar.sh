#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python_projeto=../../.venv/bin/python
if [ ! -x "$python_projeto" ]; then
  python3 -m venv ../../.venv
fi
if ! "$python_projeto" -c 'import streamlit, pandas, plotly' >/dev/null 2>&1; then
  "$python_projeto" -m pip install -r requirements.txt
fi
exec "$python_projeto" -m streamlit run app.py --server.address 127.0.0.1 \
  --server.port "${PROEX_DASHBOARD_PORT:-8501}" --server.headless true
