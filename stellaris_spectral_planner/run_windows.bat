@echo off
if not exist .venv (
  echo No .venv found. Create it first using the README instructions.
  pause
  exit /b 1
)
call .venv\Scripts\activate
streamlit run app.py
pause
