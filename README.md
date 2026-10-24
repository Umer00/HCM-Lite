# 🏢 HCM-Lite — Human Capital Management System

### A Smarter Way to Manage People, Attendance, Leave & Payroll

**HCM-Lite** is a lightweight, role-based Human Capital Management (HCM) web application designed to simplify everyday HR operations. Built with Python, Flask, and SQLite, it brings employee records, attendance tracking, leave management, payroll processing, and AI-assisted HR support into one centralized platform.

From employee onboarding to payroll finalization, HCM-Lite helps organizations manage essential workforce processes through dedicated Admin, HR, and Employee interfaces.

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [User Roles](#-user-roles)
- [Technology Stack](#️-technology-stack)
- [Application Modules](#-application-modules)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Configuration](#️-configuration)
- [AI Assistant](#-ai-assistant)
- [Security & Data Management](#-security--data-management)
- [Demo Workflow](#-demo-workflow)
- [Limitations](#-limitations)
- [Future Enhancements](#-future-enhancements)
- [License](#-license)

---

## 🌟 Overview

Managing employee information, daily attendance, leave requests, and monthly payroll across separate systems can create unnecessary administrative work.

HCM-Lite addresses these challenges by providing a centralized HR management solution with role-based access, database-backed dashboards, configurable company settings, and streamlined workflows.

The application supports three user roles:

- **Admin:** Oversees company settings, user access, departments, and payroll finalization.
- **HR:** Manages employee records, attendance, leave approvals, and payroll preparation.
- **Employee:** Accesses personal information, records attendance, submits leave requests, and views payslips.

The application starts with an empty database unless initial administrator credentials are configured. Company setup and account creation are handled through the application.

## ✨ Key Features

### 👥 1. Employee Management

- Register and maintain employee records.
- Store employee IDs, contact details, departments, designations, and salary information.
- Search and filter employee records.
- Import employee data through CSV files.
- Export employee records to CSV.
- Validate imported data before committing changes.

### ⏰ 2. Attendance Management

- Record employee check-in and check-out times.
- Automatically timestamp attendance through the server.
- Identify late arrivals and half-day attendance.
- Review attendance records and trends.
- Submit attendance correction requests for review.

### 🏖️ 3. Leave Management

- Submit and cancel leave requests.
- Support annual, sick, casual, and unpaid leave categories.
- Calculate working days while accounting for configured weekends and public holidays.
- Track available leave balances.
- Validate leave balances and overlapping requests.
- Approve or reject requests with reviewer comments.
- Notify relevant users about workflow updates.

### 💰 4. Payroll Management

- Prepare monthly payroll drafts.
- Calculate gross salary using configured salary components.
- Account for applicable absence, unpaid leave, and half-day deductions.
- Apply the illustrative tax slabs defined for the project.
- Allow authorized administrators to finalize and lock payroll runs.
- Generate PDF payslips for employees.

**Note:** Payroll tax calculations are based on the project's challenge requirements and are not a substitute for current legal or tax advice.

### 📊 5. Role-Based Dashboards

Provide relevant information based on each user's role.

- Employee headcount and department summaries.
- Daily attendance and late-arrival statistics.
- Pending and recent leave requests.
- Payroll cost summaries.
- Attendance trends.
- Personal attendance history and leave balances for employees.

Dashboard statistics are derived from application database records rather than fixed demonstration figures.

### 🤖 6. AI-Assisted HR Support

The built-in assistant provides support for selected HR-related tasks, including:

- Headcount and employee-related queries.
- Attendance and leave balance questions.
- Salary-scope and access checks.
- HR policy questions.
- Suggested leave request details.
- Dashboard-context recommendations.

Local database-backed assistant tools can operate without a hosted AI API key for supported questions. An optional compatible hosted language-model API can extend responses to general policy questions.

The optional AI integration is a starter implementation and does not yet provide the complete provider-native tool-calling workflow required by the original challenge.

### 🔔 7. Notifications & Announcements

- Notify relevant users about signup requests and workflow events.
- Provide a centralized announcements feature.
- Maintain user notification records.
- Support clearer communication between employees, HR, and administrators.

### 🧾 8. Audit Logging

Maintain a read-only record of selected application actions, including relevant account, employee, settings, and approval changes.

Audit entries can capture the actor, action, affected record, timestamps, and available before-and-after data.

### ⚙️ 9. Company Settings & Account Administration

- Configure company information.
- Set office start time and grace period.
- Configure half-day thresholds and weekend days.
- Define leave quotas.
- Maintain departments and public holidays.
- Create or deactivate HR accounts.
- Review and approve registration requests.
- Require password changes where applicable.

---

## 👤 User Roles

| Capability | Admin | HR | Employee |
|---|:---:|:---:|:---:|
| Company settings | ✅ | — | — |
| Department management | ✅ | — | — |
| HR account administration | ✅ | — | — |
| Employee registration and management | ✅ | ✅ | — |
| CSV employee import | — | ✅ | — |
| Employee CSV export | ✅ | ✅ | — |
| Attendance check-in/out | — | — | ✅ |
| Attendance review | ✅ | ✅ | Personal records |
| Leave approval | ✅ | ✅ | — |
| Leave application | — | — | ✅ |
| Payroll draft preparation | — | ✅ | — |
| Payroll finalization | ✅ | — | — |
| Personal payslip access | — | — | ✅ |
| AI assistant | Role-aware | Role-aware | Role-aware |
| Audit log | Available to authorized users | — | — |

Access is controlled through server-side role checks. The table summarizes the intended application workflow; individual permissions should be verified against the relevant routes before production use.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.10+ | Application logic |
| Flask | Web framework and routing |
| SQLite | Relational database |
| HTML | Page structure |
| CSS | User interface styling |
| JavaScript | Client-side interactions |
| ReportLab | PDF document generation |
| Requests | HTTP requests for optional integrations |
| Gunicorn | Production WSGI server support |
| Git & GitHub | Version control and project hosting |

---

## 🧩 Application Modules

HCM-Lite organizes its functionality around interconnected HR workflows:

| Module | Main Responsibility |
|---|---|
| Authentication & Access | Login, logout, password management, and role checks |
| Employee Directory | Employee records, search, CSV import, and export |
| Attendance | Check-in/out, attendance status, and correction requests |
| Leave Management | Applications, quotas, working-day calculations, and approvals |
| Payroll | Monthly drafts, salary calculations, deductions, and payslips |
| Dashboard | Role-specific workforce summaries and KPIs |
| Notifications | Signup and workflow notifications |
| AI Assistant | Selected HR queries and database-backed tools |
| Audit Log | Read-only activity history |
| Company Settings | Departments, holidays, office rules, and leave quotas |

---

## 📂 Project Structure

```text
HCM-Lite/
│
├── LICENSE
├── README.md
│
└── hcm-lite/
    ├── app.py
    ├── requirements.txt
    ├── templates/
    ├── static/
    └── hcm_lite.db       # Created automatically at runtime
```

The application database is created automatically when the application initializes. The `templates/` and `static/` directories are used by the Flask application for page rendering and static assets.

---

## 🚀 Getting Started

Follow these steps to run HCM-Lite locally.

### Prerequisites

- Python 3.10 or later
- Git
- A terminal or command prompt
- Internet access for installing dependencies

### 1. Clone the Repository

```bash
git clone https://github.com/Umer00/HCM-Lite.git
```

### 2. Enter the Application Directory

```bash
cd HCM-Lite/hcm-lite
```

### 3. Create a Virtual Environment

**Windows — PowerShell**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 5. Configure Environment Variables

Set a secure Flask secret key before running the application.

**Windows — PowerShell**

```powershell
$env:SECRET_KEY = "replace-with-a-long-random-secret"
```

**macOS / Linux**

```bash
export SECRET_KEY="replace-with-a-long-random-secret"
```

For an automatically created administrator account, you can also configure:

```text
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=your-strong-password
```

Set these as environment variables in the same terminal session before starting the application.

Alternatively, leave the administrator credentials unset and create the initial company and administrator through the `/setup` page.

**Important:** The application does not automatically load `.env` files. Set environment variables directly in your terminal or through your deployment platform's configuration.

### 6. Start the Application

```bash
python app.py
```

### 7. Open HCM-Lite

Visit the following address in your browser:

**http://127.0.0.1:5000**

For a fresh installation, open `/setup` to create the company and initial administrator account, then sign in.

The SQLite database is created as `hcm_lite.db` alongside `app.py`, unless a custom `DATABASE_PATH` is configured.

---

## ⚙️ Configuration

The application supports environment-based configuration.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Flask session signing secret |
| `DATABASE_PATH` | Optional custom SQLite database path |
| `ADMIN_EMAIL` | Optional initial administrator email |
| `ADMIN_PASSWORD` | Optional initial administrator password |
| `AI_API_KEY` | Optional hosted AI provider key |
| `AI_BASE_URL` | Optional compatible chat-completions endpoint |
| `AI_MODEL` | Model name supported by the configured provider |

Keep credentials and API keys out of source control. Configure sensitive values through environment variables or your hosting provider's secret management facilities.

---

## 🤖 AI Assistant Setup

The core assistant tools can answer supported questions using local database information without requiring a paid AI API key.

To enable the optional hosted language-model integration, configure the following server-side environment variables:

```text
AI_API_KEY=your-provider-api-key
AI_BASE_URL=your-compatible-api-endpoint
AI_MODEL=your-provider-model
```

Use values appropriate to your chosen provider. The AI integration can fall back when the hosted service is unavailable.

**Privacy reminder:** Never commit real API keys or expose provider credentials in browser-side code.

---

## 🧪 Suggested Demo Workflow

Use this workflow to demonstrate the main features of HCM-Lite:

1. Launch a fresh installation and create a company with an administrator account.
2. Add departments and configure office hours or public holidays.
3. Create an HR account and sign in with the appropriate role.
4. Register employees or import records using a validated CSV file.
5. Sign in as an employee and record attendance.
6. Submit a leave request and review it through the HR interface.
7. Prepare a monthly payroll draft and finalize it as an administrator.
8. Generate and access a PDF payslip through the appropriate account.
9. Explore dashboard summaries, notifications, and audit records.
10. Test the assistant's supported HR questions and role-based access restrictions.

This sequence demonstrates how the application's modules work together in a typical HR workflow.

---

## 🔐 Security & Data Management

HCM-Lite includes several security-related mechanisms:

- Password hashing using Werkzeug security utilities.
- Server-side authentication and role checks.
- Restricted access to role-specific operations.
- Validation of important employee and payroll inputs.
- Password-change requirements where configured.
- Audit records for selected operations.
- Environment-based configuration for secrets and optional integrations.

However, these mechanisms do not mean the application has undergone an independent security audit.

Before production deployment:

- Replace development secrets with strong, unique values.
- Use HTTPS and a production WSGI server.
- Configure persistent storage and regular database backups.
- Review session security, CSRF protection, authorization rules, and sensitive-data handling.
- Test payroll, leave, and attendance calculations against expected business rules.
- Use a production database such as PostgreSQL when concurrent usage requirements justify it.

Do not use the Flask development server as a production hosting solution.

---

## ⚠️ Limitations

The current project is a hackathon starter and should not be represented as a fully production-audited HR platform.

The following features are identified as not implemented in the current starter:

- Camera and GPS-based attendance verification.
- Facial matching and liveness detection.
- Employee attrition risk scoring.
- Absence anomaly detection.
- Automatic penalties for three late arrivals.
- Progressive Web App (PWA) functionality and dark mode.
- Complete provider-native AI tool calling.

The optional AI integration also requires further work for full compliance with the original challenge's hosted-LLM tool-calling requirements.

---

## 🔮 Future Enhancements

Potential improvements include:

- PostgreSQL integration for larger deployments.
- Comprehensive automated tests for attendance, leave, and payroll.
- Stronger session and request security controls.
- Advanced workforce analytics and customizable reports.
- More extensive employee self-service functionality.
- Improved mobile accessibility and responsive design.
- Verified camera/GPS attendance workflows, with appropriate consent and privacy controls.
- Advanced AI tool calling with explicit authorization and auditability.
- Deployment automation and monitoring.

---

## 📜 License

This project is distributed under the **MIT License**. Refer to the [`LICENSE`](LICENSE) file for the applicable terms.

---

## ⭐ Support

If you find HCM-Lite useful as a learning project or a starting point for HR workflow automation, consider starring the repository and exploring its modules.

**Built with Python, Flask, SQLite, and a focus on simplifying HR operations.**
