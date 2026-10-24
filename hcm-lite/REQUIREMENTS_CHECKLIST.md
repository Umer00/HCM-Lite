# Challenge requirement checklist

## Required — status in this build
- [x] Web app, responsive layout, role-based dashboards
- [x] First-run company/Admin setup
- [x] Login/logout, password change, bcrypt-style secure hashing via Werkzeug, role checks in server routes
- [x] Company settings, departments, leave quotas, public holidays
- [x] Admin creates/deactivates HR logins
- [x] HR registers employee and creates employee login with temporary password
- [x] Employee directory, search/filter, CSV export
- [x] CSV import validation/dry-run (HR)
- [x] Web check-in/out; server timestamp; one attendance record per day; late/half-day rules
- [x] Employee correction request; HR correction inbox
- [x] Leave request, cancel pending leave, balance, working-day/holiday/weekend checks, overlap/balance rejection
- [x] HR leave approve/reject with comment
- [x] Salary structure, monthly draft payroll, illustrative tax slabs and deductions
- [x] Admin-only payroll finalization and lock
- [x] Payslip PDF download with employee data-scope check
- [x] Admin/HR/Employee dashboard views and server-computed KPIs
- [x] Assistant for supported database-backed questions and policy Q&A; AI log; optional hosted LLM fallback
- [x] Smart leave draft for common natural-language date phrases; employee confirms in regular form
- [x] Announcements, notifications, audit log
- [x] README, environment example, health endpoint

## Needs completion / external setup / testing
- [ ] Configure a real hosted LLM API and implement provider-native tool calling for full AI rubric compliance
- [ ] Deploy to a hosting provider with persistent storage and set environment variables
- [ ] Create Git repository and submit repository + live URL in each student's LMS portal
- [ ] Run full acceptance tests in an environment with dependencies installed
- [ ] Bonus: camera + GPS/face attendance, face matching/liveness, attrition risk, absence anomaly, three-lates penalty, PWA/dark mode

This checklist is candid: the project includes the core implementation, but external deployment and provider-specific AI tool calling cannot be claimed complete from this environment.
