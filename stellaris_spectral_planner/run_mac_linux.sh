#!/usr/bin/env bash
set -e
if [ ! -d ".venv" ]; then
  echo "No .venv found. Create it first using the README instructions."
  exit 1
fi
source .venv/bin/activate
streamlit run app.py
