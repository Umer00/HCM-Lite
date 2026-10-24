@echo off
cd /d %~dp0
py -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt
if not exist .env echo Optional: copy .env.example to .env and set environment variables manually.
python app.py
pause
