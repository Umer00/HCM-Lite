# HCM Lite — Saylani Hackathon project

A responsive, role-based Human Capital Management web app built to the supplied HCM Lite challenge brief. Stack: **Python 3 + Flask + SQLite + HTML/CSS/JavaScript**. The app starts empty unless you provide first-admin environment variables. Employee and attendance figures are database-backed, not preloaded demo records.

## Features implemented

- First-run company/Admin setup; login, logout, password change, password hashing, role guards
- Admin, HR and Employee views; server-side role checks
- Company settings, departments, public holidays, HR account create/deactivate
- Employee registration with employee login, search/filter, CSV export, CSV dry-run validation/import
- Web check-in/out, server-stamped time, late/half-day statuses, correction request and HR review
- Leave apply/cancel, working-day counting, holidays/weekends, quota balance, overlap/balance checks, HR approval/rejection and notifications
- Monthly payroll draft, gross salary formula, absence/unpaid/half-day deductions, challenge tax slabs, Admin-only finalization/locking, PDF payslips
- Role-aware dashboards and database-backed KPIs, announcements, notifications, read-only audit log
- Assistant with database-backed tools for headcount, leave, attendance, salary-scope checks, policy Q&A, smart leave drafts, dashboard context suggestions and optional hosted LLM API
- Health endpoint: `/api/health`

## Run locally (Windows, macOS or Linux)

1. Install Python 3.10+ from https://www.python.org/downloads/ (on Windows, tick **Add Python to PATH**).
2. Extract this ZIP to a normal folder, for example `hcm-lite`.
3. Open Terminal / PowerShell in that folder.
4. Create a virtual environment:
   - Windows: `py -m venv .venv` then `.venv\\Scripts\\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
5. Install dependencies: `python -m pip install -r requirements.txt`
6. Set a secure secret and optional admin credentials. Easiest: copy `.env.example` to `.env` and load those values in your shell, or set environment variables directly. The app does **not** automatically parse `.env`; for local development you can set them manually:
   - PowerShell: `$env:SECRET_KEY='a-long-random-secret'; $env:ADMIN_EMAIL='admin@example.com'; $env:ADMIN_PASSWORD='Use-A-Strong-Password-123!'`
   - macOS/Linux: `export SECRET_KEY='a-long-random-secret'; export ADMIN_EMAIL='admin@example.com'; export ADMIN_PASSWORD='Use-A-Strong-Password-123!'`
   Alternatively, leave `ADMIN_EMAIL` and `ADMIN_PASSWORD` unset and open `/setup` to create the first Admin through the UI.
7. Run: `python app.py`
8. Open http://127.0.0.1:5000 . For a fresh database, create the company at `/setup` then sign in.

The SQLite database is created automatically beside `app.py` as `hcm_lite.db`. Back it up before deleting or replacing it. Do not use the Flask development server for a production deployment.

## Optional AI API

The core assistant tools work without a paid key and answer from local database data for supported questions. To enable hosted LLM answers for general policy questions, set these **on the server only**:

- `AI_API_KEY` — your provider key
- `AI_BASE_URL` — compatible chat-completions endpoint (default points to OpenAI-compatible API)
- `AI_MODEL` — a model available to your provider

The AI integration is optional and gracefully falls back if unavailable. Do not commit real API keys. The challenge requires a hosted LLM API with tool calling for full AI scoring; this starter integration sends a constrained context prompt for general questions and implements local database-backed assistant tools, but does not yet expose a formal provider-native tool-calling loop. For strict full compliance, add provider-native tool calling and verify it against your chosen API.

## Deploy (generic)

Use a Python web host that supports Flask and persistent storage. Set the start command to `gunicorn app:app` (add `gunicorn` to requirements if the host requires it), set `PORT` if required, and configure `SECRET_KEY`, `DATABASE_PATH`, Admin credentials and optional AI variables in the host's environment settings. Keep the SQLite file on a persistent disk; ephemeral filesystems can reset the database on restart. For production, use a production WSGI server, HTTPS, secure secret values, backups and an appropriate database such as PostgreSQL for concurrent use.

The challenge asks for two LMS submissions: a Git repository link and a live hosted project link. You must create/authorize those accounts and submit those links yourself; this package does not claim it has been deployed.

## 5-minute demo script

1. Fresh install → create company and Admin.
2. Admin adds a department, holiday (optional), and HR login.
3. HR registers 2–3 employees and securely shares temporary passwords.
4. Employee changes password, checks in, and asks AI about leave balance.
5. Employee creates a leave request; HR approves it.
6. HR checks dashboard and generates payroll draft; Admin finalizes it.
7. Employee downloads own payslip; ask the assistant for a colleague's salary and verify refusal; Admin opens audit log.

## CSV format

Required headers: `code,name,email,basic_salary,join_date`. Optional: `phone,address,department,designation,gender,status`. `join_date` must be ISO `YYYY-MM-DD`. Department names must already exist. Use dry-run first.

## Known limitations to verify before judging

- Camera + GPS attendance, face matching/liveness, attrition risk score, absence anomaly flags, three-lates penalty, and PWA/dark mode are bonus items and are not implemented in this starter.
- Smart leave prefill currently supports common phrases such as “next Monday and Tuesday off”, “tomorrow”, and “today”; review the suggested dates and form before submitting.
- Tax rules are the illustrative rules in the brief, not legal/tax advice.
- This is a hackathon starter, not a security-audited production HR/payroll system. Configure secrets, HTTPS, backups, and test all business rules with your judges' expected scenarios.
