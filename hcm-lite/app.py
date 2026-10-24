import os, io, csv, json, math, sqlite3, secrets, calendar
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, g, request, redirect, url_for, session, flash, render_template, jsonify, send_file, Response
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(APP_DIR, 'hcm_lite.db'))
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-me')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

SCHEMA = '''
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','hr','employee')), active INTEGER NOT NULL DEFAULT 1, must_change_password INTEGER NOT NULL DEFAULT 0, employee_id INTEGER, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS departments (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS designations (id INTEGER PRIMARY KEY, name TEXT NOT NULL, department_id INTEGER, UNIQUE(name,department_id));
CREATE TABLE IF NOT EXISTS holidays (id INTEGER PRIMARY KEY, day TEXT UNIQUE NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT DEFAULT '', address TEXT DEFAULT '', department_id INTEGER, designation TEXT DEFAULT '', basic_salary REAL NOT NULL CHECK(basic_salary > 0), join_date TEXT NOT NULL, gender TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, FOREIGN KEY(department_id) REFERENCES departments(id));
CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY, employee_id INTEGER NOT NULL, day TEXT NOT NULL, check_in TEXT, check_out TEXT, status TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'web', correction_reason TEXT, correction_status TEXT, created_at TEXT NOT NULL, UNIQUE(employee_id,day), FOREIGN KEY(employee_id) REFERENCES employees(id));
CREATE TABLE IF NOT EXISTS leaves (id INTEGER PRIMARY KEY, employee_id INTEGER NOT NULL, kind TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, days REAL NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', reviewer_id INTEGER, reviewer_comment TEXT DEFAULT '', created_at TEXT NOT NULL, FOREIGN KEY(employee_id) REFERENCES employees(id));
CREATE TABLE IF NOT EXISTS payroll_runs (id INTEGER PRIMARY KEY, month TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'draft', created_by INTEGER NOT NULL, finalized_by INTEGER, created_at TEXT NOT NULL, finalized_at TEXT);
CREATE TABLE IF NOT EXISTS payslips (id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, employee_id INTEGER NOT NULL, basic REAL NOT NULL, hra REAL NOT NULL, medical REAL NOT NULL, gross REAL NOT NULL, tax REAL NOT NULL, absent_deduction REAL NOT NULL, unpaid_deduction REAL NOT NULL, halfday_deduction REAL NOT NULL, net REAL NOT NULL, working_days INTEGER NOT NULL, data_json TEXT NOT NULL, UNIQUE(run_id,employee_id), FOREIGN KEY(run_id) REFERENCES payroll_runs(id), FOREIGN KEY(employee_id) REFERENCES employees(id));
CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, author_id INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, message TEXT NOT NULL, read_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY, actor_id INTEGER, actor_email TEXT, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id TEXT, before_json TEXT, after_json TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_logs (id INTEGER PRIMARY KEY, user_id INTEGER, question TEXT NOT NULL, tool_name TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS signup_requests (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('hr','employee')), status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
'''

def now(): return datetime.now().replace(microsecond=0).isoformat(sep=' ')
def today(): return date.today().isoformat()
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db
@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None: db.close()

def audit(action, entity, entity_id=None, before=None, after=None):
    u = getattr(g, 'user', None)
    get_db().execute('INSERT INTO audit_log(actor_id,actor_email,action,entity,entity_id,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?,?)',
        (u['id'] if u else None, u['email'] if u else 'system', action, entity, str(entity_id) if entity_id is not None else None,
         json.dumps(dict(before), default=str) if before else None, json.dumps(dict(after), default=str) if after else None, now()))

def init_db():
    db = sqlite3.connect(DB_PATH); db.row_factory = sqlite3.Row; db.executescript(SCHEMA)
    for k,v in {'office_start':'09:00','grace_minutes':'15','half_day_hours':'5','weekend_days':'5,6','office_lat':'','office_lng':'','office_radius_m':'150','company_name':'','annual_quota':'14','sick_quota':'8','casual_quota':'10'}.items():
        db.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
    db.commit()
    admin_email = os.environ.get('ADMIN_EMAIL','').strip().lower(); admin_pw = os.environ.get('ADMIN_PASSWORD','')
    if admin_email and admin_pw and not db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        db.execute('INSERT OR IGNORE INTO users(email,password_hash,role,created_at) VALUES(?,?,?,?)',(admin_email,generate_password_hash(admin_pw),'admin',now())); db.commit()
    db.close()
init_db()

@app.before_request
def load_user():
    g.user = None
    if session.get('uid'):
        g.user = get_db().execute('SELECT * FROM users WHERE id=? AND active=1',(session['uid'],)).fetchone()
        if not g.user: session.clear()

def login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not g.user: return redirect(url_for('login'))
        if g.user['must_change_password'] and request.endpoint not in ('change_password','logout','static'):
            return redirect(url_for('change_password'))
        return fn(*a,**kw)
    return wrapper

def roles(*allowed):
    def deco(fn):
        @wraps(fn)
        @login_required
        def wrapper(*a,**kw):
            if g.user['role'] not in allowed: return render_template('error.html',message='You do not have permission to access this page.'),403
            return fn(*a,**kw)
        return wrapper
    return deco

def setting(key, default=''):
    r=get_db().execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone(); return r['value'] if r else default
def employee_for_user():
    return get_db().execute('SELECT e.*,d.name department FROM employees e LEFT JOIN departments d ON d.id=e.department_id WHERE e.id=?',(g.user['employee_id'],)).fetchone()
def working_days(start, end):
    a=date.fromisoformat(start); b=date.fromisoformat(end); weekend=set(int(x) for x in setting('weekend_days','5,6').split(',') if x.strip().isdigit())
    holidays={r['day'] for r in get_db().execute('SELECT day FROM holidays WHERE day BETWEEN ? AND ?',(start,end))}
    n=0
    while a<=b:
        if a.weekday() not in weekend and a.isoformat() not in holidays: n+=1
        a+=timedelta(days=1)
    return n
def leave_quota(kind): return float(setting({'annual':'annual_quota','sick':'sick_quota','casual':'casual_quota'}.get(kind,''),'0')) if kind!='unpaid' else 999999.0
def leave_balance(eid, kind):
    used=get_db().execute("SELECT COALESCE(SUM(days),0) n FROM leaves WHERE employee_id=? AND kind=? AND status='approved' AND strftime('%Y',start_date)=?",(eid,kind,str(date.today().year))).fetchone()['n']
    return max(0,leave_quota(kind)-used)
def create_notification(user_id,message): get_db().execute('INSERT INTO notifications(user_id,message,created_at) VALUES(?,?,?)',(user_id,message,now()))
def notify_role(role,message):
    for u in get_db().execute('SELECT id FROM users WHERE role=? AND active=1',(role,)): create_notification(u['id'],message)

def dashboard_data(role, eid=None):
    db=get_db(); month=date.today().strftime('%Y-%m')
    if role=='employee':
        att=db.execute('SELECT * FROM attendance WHERE employee_id=? ORDER BY day DESC LIMIT 30',(eid,)).fetchall()
        lv=db.execute('SELECT * FROM leaves WHERE employee_id=? ORDER BY id DESC LIMIT 8',(eid,)).fetchall()
        emp=db.execute('SELECT * FROM employees WHERE id=?',(eid,)).fetchone()
        hours=0
        for a in att:
            if a['check_in'] and a['check_out']:
                try: hours+=max(0,(datetime.fromisoformat(a['check_out'])-datetime.fromisoformat(a['check_in'])).total_seconds()/3600)
                except: pass
        return {'employee':emp,'attendance':att,'leaves':lv,'hours':round(hours,1),'late_count':sum(1 for a in att if a['status']=='late'),'balances':{k:leave_balance(eid,k) for k in ('casual','sick','annual','unpaid')}}
    where=''
    stats={
      'headcount':db.execute("SELECT COUNT(*) n FROM employees WHERE status IN ('active','probation')").fetchone()['n'],
      'present':db.execute("SELECT COUNT(*) n FROM attendance WHERE day=? AND status IN ('present','late','missing_checkout')",(today(),)).fetchone()['n'],
      'on_leave':db.execute("SELECT COUNT(DISTINCT employee_id) n FROM leaves WHERE status='approved' AND start_date<=? AND end_date>=?",(today(),today())).fetchone()['n'],
      'late':db.execute("SELECT COUNT(*) n FROM attendance WHERE day=? AND status='late'",(today(),)).fetchone()['n'],
      'pending':db.execute("SELECT COUNT(*) n FROM leaves WHERE status='pending'").fetchone()['n'],
      'departments':db.execute('SELECT d.name,COUNT(e.id) n FROM departments d LEFT JOIN employees e ON e.department_id=d.id AND e.status IN (\'active\',\'probation\') GROUP BY d.id ORDER BY d.name').fetchall(),
      'recent_leaves':db.execute('SELECT l.*,e.name employee_name FROM leaves l JOIN employees e ON e.id=l.employee_id ORDER BY l.id DESC LIMIT 8').fetchall(),
      'announcements':db.execute('SELECT a.*,u.email author FROM announcements a LEFT JOIN users u ON u.id=a.author_id ORDER BY a.id DESC LIMIT 5').fetchall(),
      'payroll_cost':db.execute("SELECT COALESCE(SUM(p.gross),0) n FROM payslips p JOIN payroll_runs r ON r.id=p.run_id WHERE r.month=?",(month,)).fetchone()['n'],
      'attendance_trend':db.execute("SELECT day,COUNT(*) total,SUM(CASE WHEN status='late' THEN 1 ELSE 0 END) late FROM attendance WHERE day>=date('now','-6 day') GROUP BY day ORDER BY day").fetchall()
    }
    return stats

@app.route('/')
def index(): return redirect(url_for('dashboard') if g.user else url_for('login'))
@app.route('/setup', methods=['GET','POST'])
def setup():
    db=get_db()
    if db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone(): return redirect(url_for('login'))
    if request.method=='POST':
        company=request.form.get('company_name','').strip(); email=request.form.get('email','').strip().lower(); pw=request.form.get('password','')
        if not company or not email or len(pw)<10: flash('Enter company, valid email and a password of at least 10 characters.','error')
        else:
            db.execute("UPDATE settings SET value=? WHERE key='company_name'",(company,)); db.execute('INSERT INTO users(email,password_hash,role,created_at) VALUES(?,?,?,?)',(email,generate_password_hash(pw),'admin',now())); db.commit(); flash('Company and Admin created. Please sign in.','success'); return redirect(url_for('login'))
    return render_template('setup.html')
@app.route('/login',methods=['GET','POST'])
def login():
    if g.user:return redirect(url_for('dashboard'))
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); pw=request.form.get('password','')
        u=get_db().execute('SELECT * FROM users WHERE email=? AND active=1',(email,)).fetchone()
        if u and check_password_hash(u['password_hash'],pw):
            session.clear(); session['uid']=u['id']; audit('login','user',u['id']); get_db().commit(); return redirect(url_for('change_password') if u['must_change_password'] else url_for('dashboard'))
        if get_db().execute("SELECT 1 FROM signup_requests WHERE email=? AND status='pending'",(email,)).fetchone():
            flash('Your signup is still awaiting approval.','error')
        else:
            flash('Email or password is incorrect.','error')
    return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.route('/register', methods=['GET','POST'])
def register():
    if g.user: return redirect(url_for('dashboard'))
    db = get_db()
    if not db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        return redirect(url_for('setup'))
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip().lower()
        pw = request.form.get('password','')
        role = request.form.get('role','employee')
        if role not in ('employee','hr') or not name or '@' not in email or len(pw) < 10:
            flash('Enter name, valid email and a password of at least 10 characters.','error')
        elif db.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone() or \
             db.execute("SELECT 1 FROM signup_requests WHERE email=? AND status='pending'",(email,)).fetchone():
            flash('This email already has an account or a pending request.','error')
        else:
            db.execute('INSERT INTO signup_requests(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',
                       (name,email,generate_password_hash(pw),role,now()))
            if role == 'hr': notify_role('admin', f'New HR signup request from {name}.')
            else:
                notify_role('hr', f'New employee signup request from {name}.')
                notify_role('admin', f'New employee signup request from {name}.')
            db.commit()
            flash('Request submitted. You can sign in once it is approved.','success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/signups')
@roles('admin','hr')
def signups():
    db = get_db()
    allowed = ('hr','employee') if g.user['role']=='admin' else ('employee',)
    q = ','.join('?'*len(allowed))
    rows = db.execute(f"SELECT * FROM signup_requests WHERE status='pending' AND role IN ({q}) ORDER BY id", allowed).fetchall()
    return render_template('signups.html', rows=rows, departments=db.execute('SELECT * FROM departments ORDER BY name').fetchall())

def can_review_signup(req):
    return g.user['role']=='admin' or (g.user['role']=='hr' and req['role']=='employee')

@app.route('/signups/<int:sid>/approve', methods=['POST'])
@roles('admin','hr')
def approve_signup(sid):
    db = get_db()
    r = db.execute("SELECT * FROM signup_requests WHERE id=? AND status='pending'",(sid,)).fetchone()
    if not r or not can_review_signup(r):
        flash('Request not found or you cannot review it.','error'); return redirect(url_for('signups'))
    try:
        if r['role'] == 'hr':
            db.execute('INSERT INTO users(email,password_hash,role,created_at) VALUES(?,?,?,?)',
                       (r['email'],r['password_hash'],'hr',now()))
        else:
            code = request.form['code'].strip()
            salary = float(request.form['basic_salary'])
            if not code or salary <= 0: raise ValueError('Enter employee code and a valid salary.')
            join = request.form.get('join_date') or today()
            dept = request.form.get('department_id') or None
            cur = db.execute('INSERT INTO employees(code,name,email,department_id,designation,basic_salary,join_date,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                             (code,r['name'],r['email'],dept,request.form.get('designation',''),salary,join,'active',now()))
            db.execute('INSERT INTO users(email,password_hash,role,must_change_password,employee_id,created_at) VALUES(?,?,?,?,?,?)',
                       (r['email'],r['password_hash'],'employee',0,cur.lastrowid,now()))
        db.execute("UPDATE signup_requests SET status='approved' WHERE id=?",(sid,))
        audit('approve_signup','signup_request',sid,after={'email':r['email'],'role':r['role']})
        db.commit(); flash('Account approved and created.','success')
    except (ValueError,KeyError) as e:
        db.rollback(); flash(str(e) or 'Invalid data.','error')
    except sqlite3.IntegrityError:
        db.rollback(); flash('Email or employee code already exists.','error')
    return redirect(url_for('signups'))

@app.route('/signups/<int:sid>/reject', methods=['POST'])
@roles('admin','hr')
def reject_signup(sid):
    db = get_db()
    r = db.execute("SELECT * FROM signup_requests WHERE id=? AND status='pending'",(sid,)).fetchone()
    if r and can_review_signup(r):
        db.execute("UPDATE signup_requests SET status='rejected' WHERE id=?",(sid,))
        audit('reject_signup','signup_request',sid,after={'email':r['email']}); db.commit(); flash('Request rejected.','success')
    return redirect(url_for('signups'))

@app.route('/change-password',methods=['GET','POST'])
@login_required
def change_password():
    if request.method=='POST':
        p=request.form.get('password','')
        if len(p)<10: flash('Use at least 10 characters.','error')
        else:
            get_db().execute('UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?',(generate_password_hash(p),g.user['id'])); audit('change_password','user',g.user['id']); get_db().commit(); flash('Password updated.','success'); return redirect(url_for('dashboard'))
    return render_template('change_password.html')
@app.route('/dashboard')
@login_required
def dashboard():
    data=dashboard_data(g.user['role'],g.user['employee_id']) if g.user['role']=='employee' and g.user['employee_id'] else dashboard_data(g.user['role'])
    return render_template('dashboard.html',data=data)

@app.route('/settings',methods=['GET','POST'])
@roles('admin')
def settings_page():
    db=get_db()
    if request.method=='POST':
        fields=['company_name','office_start','grace_minutes','half_day_hours','weekend_days','office_lat','office_lng','office_radius_m','annual_quota','sick_quota','casual_quota']
        before={k:setting(k) for k in fields}
        for k in fields:
            v=request.form.get(k,before[k]).strip()
            if k in ('grace_minutes','half_day_hours','office_radius_m','annual_quota','sick_quota','casual_quota'):
                try:
                    if float(v)<0: raise ValueError()
                except: flash(f'Invalid value for {k}.','error'); return redirect(url_for('settings_page'))
            db.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,v))
        audit('update','settings','company',before,{k:setting(k) for k in fields}); db.commit(); flash('Settings saved.','success'); return redirect(url_for('settings_page'))
    return render_template('settings.html',settings={k:setting(k) for k in ['company_name','office_start','grace_minutes','half_day_hours','weekend_days','office_lat','office_lng','office_radius_m','annual_quota','sick_quota','casual_quota']})

@app.route('/departments',methods=['GET','POST'])
@roles('admin')
def departments():
    db=get_db()
    if request.method=='POST':
        name=request.form.get('name','').strip()
        if name:
            try: db.execute('INSERT INTO departments(name) VALUES(?)',(name,)); audit('create','department',name,after={'name':name}); db.commit(); flash('Department added.','success')
            except sqlite3.IntegrityError: flash('Department already exists.','error')
        return redirect(url_for('departments'))
    return render_template('departments.html',departments=db.execute('SELECT * FROM departments ORDER BY name').fetchall())

@app.route('/users',methods=['GET','POST'])
@roles('admin')
def users_page():
    db=get_db()
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); pw=request.form.get('password',''); role=request.form.get('role','hr')
        if role not in ('hr',) or len(pw)<10 or '@' not in email: flash('Create an HR login with a valid email and password of at least 10 characters.','error')
        else:
            try: cur=db.execute('INSERT INTO users(email,password_hash,role,created_at) VALUES(?,?,?,?)',(email,generate_password_hash(pw),'hr',now())); audit('create','user',cur.lastrowid,after={'email':email,'role':'hr'}); db.commit(); flash('HR login created.','success')
            except sqlite3.IntegrityError: flash('Email already exists.','error')
        return redirect(url_for('users_page'))
    return render_template('users.html',users=get_db().execute('SELECT id,email,role,active,created_at FROM users ORDER BY id').fetchall())
@app.route('/users/<int:uid>/toggle',methods=['POST'])
@roles('admin')
def toggle_user(uid):
    db=get_db(); u=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    if not u or u['id']==g.user['id'] or u['role']=='admin': flash('This account cannot be deactivated here.','error')
    else: db.execute('UPDATE users SET active=? WHERE id=?',(0 if u['active'] else 1,uid)); audit('deactivate' if u['active'] else 'activate','user',uid,before={'active':u['active']},after={'active':0 if u['active'] else 1}); db.commit(); flash('Account updated.','success')
    return redirect(url_for('users_page'))

@app.route('/employees',methods=['GET','POST'])
@roles('admin','hr')
def employees():
    db=get_db()
    if request.method=='POST':
        try:
            code=request.form['code'].strip(); name=request.form['name'].strip(); email=request.form['email'].strip().lower(); salary=float(request.form['basic_salary']); join=request.form.get('join_date') or today(); dept=request.form.get('department_id') or None
            if not code or not name or '@' not in email or salary<=0: raise ValueError('Check required fields and salary.')
            temp=request.form.get('temp_password') or secrets.token_urlsafe(10)
            cur=db.execute('INSERT INTO employees(code,name,email,phone,address,department_id,designation,basic_salary,join_date,gender,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(code,name,email,request.form.get('phone',''),request.form.get('address',''),dept,request.form.get('designation',''),salary,join,request.form.get('gender',''),request.form.get('status','active'),now()))
            eid=cur.lastrowid; uid=db.execute('INSERT INTO users(email,password_hash,role,must_change_password,employee_id,created_at) VALUES(?,?,?,?,?,?)',(email,generate_password_hash(temp),'employee',1,eid,now())).lastrowid
            audit('create','employee',eid,after={'code':code,'name':name,'email':email,'salary':salary}); create_notification(uid,'Your employee account is ready. Change your temporary password at first sign-in.'); db.commit()
            flash(f'Employee registered. Temporary password: {temp} — copy it now and share securely.','success')
        except (ValueError,KeyError) as e: db.rollback(); flash(str(e) or 'Invalid employee data.','error')
        except sqlite3.IntegrityError: db.rollback(); flash('Employee code or email already exists.','error')
        return redirect(url_for('employees'))
    q=request.args.get('q','').strip(); dept=request.args.get('department','')
    sql='SELECT e.*,d.name department FROM employees e LEFT JOIN departments d ON d.id=e.department_id WHERE (e.name LIKE ? OR e.email LIKE ? OR e.code LIKE ?)'; args=[f'%{q}%']*3
    if dept: sql+=' AND e.department_id=?'; args.append(dept)
    sql+=' ORDER BY e.id DESC LIMIT 200'
    return render_template('employees.html',employees=db.execute(sql,args).fetchall(),departments=db.execute('SELECT * FROM departments ORDER BY name').fetchall(),q=q,dept=dept)
@app.route('/employees/export.csv')
@roles('admin','hr')
def export_employees():
    rows=get_db().execute('SELECT e.code,e.name,e.email,e.phone,e.address,d.name department,e.designation,e.basic_salary,e.join_date,e.gender,e.status FROM employees e LEFT JOIN departments d ON d.id=e.department_id').fetchall()
    out=io.StringIO(); w=csv.writer(out); w.writerow(rows[0].keys() if rows else ['code','name','email','phone','address','department','designation','basic_salary','join_date','gender','status']); w.writerows([tuple(r) for r in rows]); return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=employees.csv'})
@app.route('/employees/import',methods=['POST'])
@roles('hr')
def import_employees():
    f=request.files.get('file')
    if not f or not f.filename.lower().endswith('.csv'): flash('Upload a CSV file.','error'); return redirect(url_for('employees'))
    try: rows=list(csv.DictReader(io.StringIO(f.stream.read().decode('utf-8-sig'))))
    except: flash('Could not read CSV. Use UTF-8 encoding.','error'); return redirect(url_for('employees'))
    errors=[]; valid=[]; seen=set()
    for i,r in enumerate(rows,2):
        try:
            if not all(r.get(k,'').strip() for k in ('code','name','email','basic_salary','join_date')): raise ValueError('required field missing')
            if '@' not in r['email'] or float(r['basic_salary'])<=0: raise ValueError('invalid email or salary')
            if r['code'] in seen or r['email'].lower() in seen: raise ValueError('duplicate in file')
            if get_db().execute('SELECT 1 FROM employees WHERE code=? OR email=?',(r['code'],r['email'].lower())).fetchone(): raise ValueError('code/email already exists')
            if r.get('department') and not get_db().execute('SELECT 1 FROM departments WHERE name=?',(r['department'],)).fetchone(): raise ValueError('unknown department')
            date.fromisoformat(r['join_date']); seen.update((r['code'],r['email'].lower())); valid.append(r)
        except Exception as e: errors.append(f"Row {i}: {e}")
    if request.form.get('dry_run')=='1' or errors: flash(f"Dry run: {len(valid)} valid rows, {len(errors)} errors. " + '; '.join(errors[:8]),'error' if errors else 'success')
    else:
        db=get_db()
        for r in valid:
            d=db.execute('SELECT id FROM departments WHERE name=?',(r.get('department',''),)).fetchone() if r.get('department') else None
            temp=secrets.token_urlsafe(10); cur=db.execute('INSERT INTO employees(code,name,email,phone,address,department_id,designation,basic_salary,join_date,gender,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(r['code'],r['name'],r['email'].lower(),r.get('phone',''),r.get('address',''),d['id'] if d else None,r.get('designation',''),float(r['basic_salary']),r['join_date'],r.get('gender',''),r.get('status','active'),now()))
            db.execute('INSERT INTO users(email,password_hash,role,must_change_password,employee_id,created_at) VALUES(?,?,?,?,?,?)',(r['email'].lower(),generate_password_hash(temp),'employee',1,cur.lastrowid,now()))
        audit('import','employees',after={'count':len(valid)}); db.commit(); flash(f'Imported {len(valid)} employees. Temporary passwords were generated; arrange secure distribution.','success')
    return redirect(url_for('employees'))

@app.route('/attendance',methods=['GET','POST'])
@roles('admin','hr','employee')
def attendance():
    db=get_db(); eid=g.user['employee_id'] if g.user['role']=='employee' else request.args.get('employee_id')
    if request.method=='POST':
        if g.user['role']!='employee': return render_template('error.html',message='Only employees can check themselves in/out.'),403
        emp=employee_for_user()
        if not emp: flash('Your account is not linked to an employee record. Contact HR.','error'); return redirect(url_for('dashboard'))
        day=today(); row=db.execute('SELECT * FROM attendance WHERE employee_id=? AND day=?',(emp['id'],day)).fetchone(); stamp=now()
        if request.form.get('action')=='in':
            if row: flash('You already have an attendance record today.','error')
            else:
                start=datetime.strptime(setting('office_start','09:00'),'%H:%M').time(); grace=int(setting('grace_minutes','15')); status='late' if datetime.now().time()> (datetime.combine(date.today(),start)+timedelta(minutes=grace)).time() else 'present'
                db.execute('INSERT INTO attendance(employee_id,day,check_in,status,source,created_at) VALUES(?,?,?,?,?,?)',(emp['id'],day,stamp,status,'web',stamp)); audit('check_in','attendance',emp['id'],after={'day':day,'status':status}); db.commit(); flash(f'Checked in successfully ({status}).','success')
        elif request.form.get('action')=='out':
            if not row or row['check_out']: flash('No open check-in found for today.','error')
            else:
                hours=(datetime.fromisoformat(stamp)-datetime.fromisoformat(row['check_in'])).total_seconds()/3600; status='half_day' if hours<float(setting('half_day_hours','5')) else row['status']
                db.execute('UPDATE attendance SET check_out=?,status=? WHERE id=?',(stamp,status,row['id'])); audit('check_out','attendance',row['id'],before=row,after={'check_out':stamp,'status':status}); db.commit(); flash('Checked out successfully.','success')
        return redirect(url_for('attendance'))
    sql='SELECT a.*,e.name employee_name,e.code FROM attendance a JOIN employees e ON e.id=a.employee_id'; args=[]
    if g.user['role']=='employee': sql+=' WHERE a.employee_id=?'; args=[g.user['employee_id']]
    elif eid: sql+=' WHERE a.employee_id=?'; args=[eid]
    sql+=' ORDER BY a.day DESC LIMIT 200'
    todayrow=db.execute('SELECT * FROM attendance WHERE employee_id=? AND day=?',(g.user['employee_id'],today())).fetchone() if g.user['role']=='employee' and g.user['employee_id'] else None
    return render_template('attendance.html',rows=db.execute(sql,args).fetchall(),todayrow=todayrow,employees=db.execute('SELECT id,name,code FROM employees ORDER BY name').fetchall())
@app.route('/attendance/correction',methods=['POST'])
@roles('employee')
def correction_request():
    reason=request.form.get('reason','').strip(); day=request.form.get('day',today()); eid=g.user['employee_id']
    if not eid or not reason: flash('Enter a reason.','error')
    else:
        db=get_db(); row=db.execute('SELECT * FROM attendance WHERE employee_id=? AND day=?',(eid,day)).fetchone()
        if row: db.execute('UPDATE attendance SET correction_reason=?,correction_status=? WHERE id=?',(reason,'pending',row['id']))
        else: db.execute('INSERT INTO attendance(employee_id,day,status,correction_reason,correction_status,created_at) VALUES(?,?,?,?,?,?)',(eid,day,'pending_correction',reason,'pending',now()))
        notify_role('hr',f'Attendance correction requested by employee #{eid} for {day}.'); audit('request_correction','attendance',eid,after={'day':day,'reason':reason}); db.commit(); flash('Correction request sent to HR.','success')
    return redirect(url_for('attendance'))
@app.route('/attendance/corrections',methods=['GET','POST'])
@roles('hr')
def corrections():
    db=get_db()
    if request.method=='POST':
        aid=request.form.get('id'); decision=request.form.get('decision'); row=db.execute('SELECT * FROM attendance WHERE id=?',(aid,)).fetchone()
        if row and row['correction_status']=='pending':
            if decision=='approve':
                if row['status']=='pending_correction': db.execute("UPDATE attendance SET status='present',check_in=COALESCE(check_in,?),correction_status='approved' WHERE id=?",(now(),aid))
                else: db.execute("UPDATE attendance SET correction_status='approved' WHERE id=?",(aid,))
            else: db.execute("UPDATE attendance SET correction_status='rejected' WHERE id=?",(aid,))
            audit('review_correction','attendance',aid,before=row,after={'decision':decision}); db.commit(); flash('Correction reviewed.','success')
        return redirect(url_for('corrections'))
    rows=db.execute("SELECT a.*,e.name employee_name,e.code FROM attendance a JOIN employees e ON e.id=a.employee_id WHERE a.correction_status='pending' ORDER BY a.day").fetchall(); return render_template('corrections.html',rows=rows)

@app.route('/leaves',methods=['GET','POST'])
@roles('admin','hr','employee')
def leaves():
    db=get_db()
    if request.method=='POST':
        if g.user['role']!='employee': return render_template('error.html',message='Only employees submit leave requests.'),403
        eid=g.user['employee_id']; kind=request.form.get('kind'); start=request.form.get('start_date'); end=request.form.get('end_date'); reason=request.form.get('reason','').strip()
        try:
            if not eid or kind not in ('annual','sick','casual','unpaid') or not start or not end or not reason: raise ValueError('Fill every field.')
            if end<start: raise ValueError('End date must not be before start date.')
            days=working_days(start,end)
            if days<1: raise ValueError('Selected dates contain no working days.')
            overlap=db.execute("SELECT 1 FROM leaves WHERE employee_id=? AND status IN ('pending','approved') AND NOT(end_date<? OR start_date>?)",(eid,start,end)).fetchone()
            if overlap: raise ValueError('This request overlaps another pending/approved leave.')
            if kind!='unpaid' and days>leave_balance(eid,kind): raise ValueError('Not enough leave balance for this request.')
            cur=db.execute('INSERT INTO leaves(employee_id,kind,start_date,end_date,days,reason,created_at) VALUES(?,?,?,?,?,?,?)',(eid,kind,start,end,days,reason,now())); notify_role('hr',f'New {kind} leave request for employee #{eid}.'); audit('create','leave',cur.lastrowid,after={'kind':kind,'start':start,'end':end,'days':days}); db.commit(); flash(f'Leave request submitted ({days} working day(s)).','success')
        except ValueError as e: flash(str(e),'error')
        return redirect(url_for('leaves'))
    sql='SELECT l.*,e.name employee_name,e.code,u.email reviewer_email FROM leaves l JOIN employees e ON e.id=l.employee_id LEFT JOIN users u ON u.id=l.reviewer_id'; args=[]
    if g.user['role']=='employee': sql+=' WHERE l.employee_id=?'; args=[g.user['employee_id']]
    sql+=' ORDER BY l.id DESC LIMIT 200'
    return render_template('leaves.html',rows=db.execute(sql,args).fetchall(),balances={k:leave_balance(g.user['employee_id'],k) for k in ('casual','sick','annual','unpaid')} if g.user['role']=='employee' and g.user['employee_id'] else {},employees=db.execute('SELECT id,name FROM employees ORDER BY name').fetchall())
@app.route('/leaves/<int:lid>/review',methods=['POST'])
@roles('hr')
def review_leave(lid):
    db=get_db(); row=db.execute('SELECT * FROM leaves WHERE id=?',(lid,)).fetchone(); decision=request.form.get('decision'); comment=request.form.get('comment','').strip()
    if not row or row['status']!='pending' or decision not in ('approve','reject'): flash('Request is no longer pending.','error')
    else:
        status='approved' if decision=='approve' else 'rejected'
        db.execute('UPDATE leaves SET status=?,reviewer_id=?,reviewer_comment=? WHERE id=?',(status,g.user['id'],comment,lid)); user=db.execute('SELECT id FROM users WHERE employee_id=?',(row['employee_id'],)).fetchone()
        if user: create_notification(user['id'],f'Your leave request #{lid} was {status}. {comment}')
        audit(status,'leave',lid,before=row,after={'status':status,'comment':comment}); db.commit(); flash(f'Leave {status}.','success')
    return redirect(url_for('leaves'))
@app.route('/leaves/<int:lid>/cancel',methods=['POST'])
@roles('employee')
def cancel_leave(lid):
    db=get_db(); row=db.execute('SELECT * FROM leaves WHERE id=? AND employee_id=?',(lid,g.user['employee_id'])).fetchone()
    if row and row['status']=='pending': db.execute("UPDATE leaves SET status='cancelled' WHERE id=?",(lid,)); audit('cancel','leave',lid,before=row,after={'status':'cancelled'}); db.commit(); flash('Leave request cancelled.','success')
    else: flash('Only your pending leave can be cancelled.','error')
    return redirect(url_for('leaves'))

@app.route('/payroll',methods=['GET','POST'])
@roles('admin','hr')
def payroll():
    db=get_db()
    if request.method=='POST':
        month=request.form.get('month','')
        try:
            datetime.strptime(month,'%Y-%m'); start=month+'-01'; last=calendar.monthrange(int(month[:4]),int(month[5:]))[1]; end=f'{month}-{last:02d}'
            run=db.execute('SELECT * FROM payroll_runs WHERE month=?',(month,)).fetchone()
            if run and run['status']=='finalized': raise ValueError('This month is finalized and locked.')
            if not run:
                rid=db.execute('INSERT INTO payroll_runs(month,status,created_by,created_at) VALUES(?,?,?,?)',(month,'draft',g.user['id'],now())).lastrowid
            else: rid=run['id']; db.execute('DELETE FROM payslips WHERE run_id=?',(rid,))
            wd=working_days(start,end)
            if wd<1: raise ValueError('No working days in month.')
            emps=db.execute("SELECT * FROM employees WHERE status IN ('active','probation') AND join_date<=?",(end,)).fetchall()
            for e in emps:
                basic=e['basic_salary']; hra=basic*.4; med=basic*.1; gross=basic+hra+med
                join=max(date.fromisoformat(start),date.fromisoformat(e['join_date'])); effective_wd=working_days(join.isoformat(),end); gross_month=gross*(effective_wd/wd)
                att=db.execute("SELECT status,COUNT(*) n FROM attendance WHERE employee_id=? AND day BETWEEN ? AND ? GROUP BY status",(e['id'],start,end)).fetchall(); counts={r['status']:r['n'] for r in att}
                absences=0
                d=date.fromisoformat(start)
                while d<=date.fromisoformat(end):
                    if d.weekday() not in set(int(x) for x in setting('weekend_days','5,6').split(',')) and not db.execute('SELECT 1 FROM holidays WHERE day=?',(d.isoformat(),)).fetchone():
                        approved=db.execute("SELECT 1 FROM leaves WHERE employee_id=? AND status='approved' AND start_date<=? AND end_date>=?",(e['id'],d.isoformat(),d.isoformat())).fetchone()
                        record=db.execute('SELECT status FROM attendance WHERE employee_id=? AND day=?',(e['id'],d.isoformat())).fetchone()
                        if not record and not approved and d>=date.fromisoformat(e['join_date']): absences+=1
                    d+=timedelta(days=1)
                unpaid=db.execute("SELECT COALESCE(SUM(days),0) n FROM leaves WHERE employee_id=? AND status='approved' AND kind='unpaid' AND NOT(end_date<? OR start_date>?)",(e['id'],start,end)).fetchone()['n']
                half=counts.get('half_day',0); perday=gross/wd; absent_d=absences*perday; unpaid_d=unpaid*perday; half_d=half*.5*perday
                annual=gross_month*12
                if annual<=600000: tax=0
                elif annual<=1200000: tax=max(0,annual-600000)*.05/12
                elif annual<=2400000: tax=(30000+(annual-1200000)*.15)/12
                elif annual<=3600000: tax=(210000+(annual-2400000)*.25)/12
                else: tax=(510000+(annual-3600000)*.35)/12
                net=max(0,gross_month-absent_d-unpaid_d-half_d-tax)
                data={'absent_days':absences,'unpaid_days':unpaid,'half_days':half,'gross_month':round(gross_month,2)}
                db.execute('INSERT INTO payslips(run_id,employee_id,basic,hra,medical,gross,tax,absent_deduction,unpaid_deduction,halfday_deduction,net,working_days,data_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,e['id'],basic,hra,med,gross_month,tax,absent_d,unpaid_d,half_d,net,wd,json.dumps(data)))
            audit('create','payroll_run',rid,after={'month':month,'employees':len(emps)}); db.commit(); flash(f'Payroll draft generated for {month}. Review before finalizing.','success')
        except (ValueError,sqlite3.IntegrityError) as e: db.rollback(); flash(str(e),'error')
        return redirect(url_for('payroll'))
    runs=db.execute('SELECT r.*,u.email creator,(SELECT COUNT(*) FROM payslips p WHERE p.run_id=r.id) employees FROM payroll_runs r JOIN users u ON u.id=r.created_by ORDER BY r.month DESC').fetchall()
    return render_template('payroll.html',runs=runs,current_month=date.today().strftime('%Y-%m'))
@app.route('/payroll/<int:rid>/finalize',methods=['POST'])
@roles('admin')
def finalize_payroll(rid):
    db=get_db(); r=db.execute('SELECT * FROM payroll_runs WHERE id=?',(rid,)).fetchone()
    if r and r['status']=='draft': db.execute("UPDATE payroll_runs SET status='finalized',finalized_by=?,finalized_at=? WHERE id=?",(g.user['id'],now(),rid)); audit('finalize','payroll_run',rid,before=r,after={'status':'finalized'}); db.commit(); flash('Payroll finalized and locked.','success')
    else: flash('Payroll not found or already finalized.','error')
    return redirect(url_for('payroll'))
@app.route('/payroll/<int:rid>')
@roles('admin','hr')
def payroll_detail(rid):
    db=get_db(); run=db.execute('SELECT * FROM payroll_runs WHERE id=?',(rid,)).fetchone()
    if not run:return render_template('error.html',message='Payroll run not found.'),404
    rows=db.execute('SELECT p.*,e.name employee_name,e.code,e.email FROM payslips p JOIN employees e ON e.id=p.employee_id WHERE p.run_id=? ORDER BY e.name',(rid,)).fetchall()
    return render_template('payroll_detail.html',run=run,rows=rows)
@app.route('/payslip/<int:pid>.pdf')
@login_required
def payslip_pdf(pid):
    db=get_db(); sql='SELECT p.*,e.name employee_name,e.code,e.email,r.month,r.status run_status FROM payslips p JOIN employees e ON e.id=p.employee_id JOIN payroll_runs r ON r.id=p.run_id WHERE p.id=?'; row=db.execute(sql,(pid,)).fetchone()
    if not row:return render_template('error.html',message='Payslip not found.'),404
    if g.user['role']=='employee' and row['employee_id']!=g.user['employee_id']: return render_template('error.html',message='You can only download your own payslip.'),403
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf=io.BytesIO(); c=canvas.Canvas(buf,pagesize=A4); w,h=A4; y=h-65
    c.setFont('Helvetica-Bold',22); c.drawString(55,y,setting('company_name','HCM Lite')); y-=35; c.setFont('Helvetica-Bold',16); c.drawString(55,y,'Employee Payslip'); y-=28
    c.setFont('Helvetica',11)
    for label,val in [('Payroll month',row['month']),('Employee',row['employee_name']),('Employee code',row['code']),('Email',row['email']),('Run status',row['run_status'])]: c.drawString(55,y,f'{label}: {val}'); y-=20
    y-=12; c.setFont('Helvetica-Bold',12); c.drawString(55,y,'Earnings / deductions'); y-=25; c.setFont('Helvetica',11)
    items=[('Basic salary',row['basic']),('HRA',row['hra']),('Medical allowance',row['medical']),('Gross pay',row['gross']),('Tax',-row['tax']),('Absence deduction',-row['absent_deduction']),('Unpaid leave deduction',-row['unpaid_deduction']),('Half-day deduction',-row['halfday_deduction']),('NET PAY',row['net'])]
    for label,val in items: c.drawString(55,y,label); c.drawRightString(w-55,y,f'PKR {val:,.2f}'); y-=22
    c.setFont('Helvetica-Oblique',9); c.drawString(55,45,'Generated by HCM Lite. Tax slabs are illustrative challenge rules.'); c.save(); buf.seek(0)
    return send_file(buf,mimetype='application/pdf',as_attachment=True,download_name=f"payslip-{row['code']}-{row['month']}.pdf")

@app.route('/announcements',methods=['GET','POST'])
@roles('admin','hr','employee')
def announcements():
    db=get_db()
    if request.method=='POST':
        if g.user['role'] not in ('admin','hr'): return render_template('error.html',message='Employees cannot post announcements.'),403
        title=request.form.get('title','').strip(); body=request.form.get('body','').strip()
        if title and body:
            cur=db.execute('INSERT INTO announcements(title,body,author_id,created_at) VALUES(?,?,?,?)',(title,body,g.user['id'],now())); audit('create','announcement',cur.lastrowid,after={'title':title});
            for u in db.execute('SELECT id FROM users WHERE active=1'): create_notification(u['id'],f'New announcement: {title}')
            db.commit(); flash('Announcement posted.','success')
        else: flash('Enter a title and message.','error')
        return redirect(url_for('announcements'))
    rows=db.execute('SELECT a.*,u.email author FROM announcements a JOIN users u ON u.id=a.author_id ORDER BY a.id DESC').fetchall(); return render_template('announcements.html',rows=rows)
@app.route('/notifications')
@login_required
def notifications():
    db=get_db(); db.execute('UPDATE notifications SET read_at=? WHERE user_id=? AND read_at IS NULL',(now(),g.user['id'])); db.commit(); rows=db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100',(g.user['id'],)).fetchall(); return render_template('notifications.html',rows=rows)
@app.route('/audit')
@roles('admin')
def audit_page():
    rows=get_db().execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT 300').fetchall(); return render_template('audit.html',rows=rows)
@app.route('/holidays',methods=['GET','POST'])
@roles('admin')
def holidays():
    db=get_db()
    if request.method=='POST':
        day=request.form.get('day'); name=request.form.get('name','').strip()
        try: date.fromisoformat(day); db.execute('INSERT INTO holidays(day,name) VALUES(?,?)',(day,name)); audit('create','holiday',day,after={'day':day,'name':name}); db.commit(); flash('Holiday added.','success')
        except: db.rollback(); flash('Invalid or duplicate holiday.','error')
        return redirect(url_for('holidays'))
    return render_template('holidays.html',rows=db.execute('SELECT * FROM holidays ORDER BY day').fetchall())

@app.route('/ai',methods=['GET','POST'])
@roles('admin','hr','employee')
def ai_page():
    if request.method=='POST':
        q=request.form.get('question','').strip()
        if not q:return jsonify({'answer':'Please enter a question.'})
        smart=None
        if g.user['role']=='employee' and any(x in q.lower() for x in ('need','want','request')) and any(x in q.lower() for x in ('off','leave','holiday')):
            smart=parse_smart_leave(q)
        if smart:
            answer=f"I prepared a {smart['kind']} leave draft for {smart['start_date']} to {smart['end_date']} ({smart['days']} working day(s)). Please review and submit it yourself. I have not submitted or approved anything."; tool='smart_leave'
        else: answer,tool=answer_from_data(q)
        db=get_db(); db.execute('INSERT INTO ai_logs(user_id,question,tool_name,created_at) VALUES(?,?,?,?)',(g.user['id'],q,tool,now())); db.commit()
        return jsonify({'answer':answer,'label':'AI-generated' if os.environ.get('AI_API_KEY') else 'Data-grounded assistant','tool':tool,'smart_leave':smart})
    return render_template('ai.html')
def parse_smart_leave(q):
    low=q.lower(); today_d=date.today(); start=None; end=None
    # Handle common plain-language examples, including the hackathon's next-Monday/Tuesday example.
    if 'next monday' in low:
        days=(0-today_d.weekday())%7
        if days==0: days=7
        start=today_d+timedelta(days=days)
        end=start+timedelta(days=1) if 'tuesday' in low else start
    elif 'tomorrow' in low:
        start=today_d+timedelta(days=1); end=start+timedelta(days=1) if 'day after' in low else start
    elif 'today' in low:
        start=end=today_d
    if not start: return None
    kind='sick' if any(x in low for x in ('sick','ill','fever','doctor')) else ('annual' if 'annual' in low else ('unpaid' if 'unpaid' in low else 'casual'))
    reason=q.strip()
    days=working_days(start.isoformat(),end.isoformat())
    return {'kind':kind,'start_date':start.isoformat(),'end_date':end.isoformat(),'reason':reason,'days':days}

def answer_from_data(q):
    db=get_db(); role=g.user['role']; eid=g.user['employee_id']; low=q.lower(); tool='policy'
    if any(x in low for x in ('headcount','how many employee','active employee','total employee')):
        tool='get_headcount'
        if role=='employee': return 'I can only provide your own employee information. Ask about your profile, leave balance, attendance or company policies.',tool
        n=db.execute("SELECT COUNT(*) n FROM employees WHERE status IN ('active','probation')").fetchone()['n']; return f'There are {n} active/probation employees in the system.',tool
    if 'late' in low:
        tool='get_late_comers'
        if role=='employee':
            n=db.execute("SELECT COUNT(*) n FROM attendance WHERE employee_id=? AND status='late' AND day LIKE ?",(eid,date.today().strftime('%Y-%m')+'%')).fetchone()['n']; return f'You have {n} late attendance record(s) this month.',tool
        rows=db.execute("SELECT e.name,COUNT(*) n FROM attendance a JOIN employees e ON e.id=a.employee_id WHERE a.status='late' AND a.day LIKE ? GROUP BY e.id ORDER BY n DESC LIMIT 5",(date.today().strftime('%Y-%m')+'%',)).fetchall()
        return ('Top late-comers this month: '+', '.join(f"{r['name']} ({r['n']})" for r in rows)) if rows else 'No late attendance records this month.',tool
    if 'leave' in low and any(x in low for x in ('balance','left','remaining','sick','casual','annual')) and role=='employee':
        kind='sick' if 'sick' in low else ('casual' if 'casual' in low else 'annual'); tool='get_my_leave_balance'; return f'Your {kind} leave balance for {date.today().year} is {leave_balance(eid,kind):g} day(s).',tool
    if 'leave' in low and any(x in low for x in ('who','today','on leave')):
        tool='get_leave_summary'
        if role=='employee': return 'I can only show your own leave information.',tool
        rows=db.execute("SELECT e.name,l.kind FROM leaves l JOIN employees e ON e.id=l.employee_id WHERE l.status='approved' AND l.start_date<=? AND l.end_date>=?",(today(),today())).fetchall()
        return ('On approved leave today: '+', '.join(f"{r['name']} ({r['kind']})" for r in rows)) if rows else 'No approved leave records for today.',tool
    if 'salary' in low and role=='employee' and any(x in low for x in ('colleague','other','someone','friend')): return 'I cannot share another employee’s salary. You can view or download your own payslips.', 'permission_refusal'
    if 'salary' in low and role=='employee':
        row=db.execute('SELECT basic_salary FROM employees WHERE id=?',(eid,)).fetchone(); return (f'Your basic salary is PKR {row["basic_salary"]:,.2f}.') if row else 'Your employee record is not linked. Contact HR.', 'get_my_salary'
    if any(x in low for x in ('attendance rate','attendance summary','present today')):
        tool='get_attendance_summary'
        if role=='employee':
            n=db.execute("SELECT COUNT(*) n FROM attendance WHERE employee_id=? AND day LIKE ?",(eid,date.today().strftime('%Y-%m')+'%')).fetchone()['n']; return f'You have {n} attendance record(s) this month.',tool
        row=db.execute("SELECT COUNT(*) total,SUM(CASE WHEN status IN ('present','late','missing_checkout') THEN 1 ELSE 0 END) present FROM attendance WHERE day LIKE ?",(date.today().strftime('%Y-%m')+'%',)).fetchone(); rate=100*row['present']/row['total'] if row['total'] else 0; return f'This month, {row["present"] or 0} of {row["total"]} recorded attendance entries count as present/late/missing checkout ({rate:.1f}% of recorded entries).',tool
    if 'payroll' in low and role!='employee':
        tool='get_payroll_summary'; row=db.execute("SELECT COALESCE(SUM(p.gross),0) gross,COALESCE(SUM(p.net),0) net FROM payslips p JOIN payroll_runs r ON r.id=p.run_id WHERE r.month=?",(date.today().strftime('%Y-%m'),)).fetchone(); return f"Current month payroll totals in generated runs: gross PKR {row['gross']:,.2f}; net PKR {row['net']:,.2f}.",tool
    policies='Policy: office starts at '+setting('office_start','09:00')+'; grace period '+setting('grace_minutes','15')+' minutes; check-in after grace is late; under '+setting('half_day_hours','5')+' hours is half-day. Leave quotas: annual '+setting('annual_quota','14')+', sick '+setting('sick_quota','8')+', casual '+setting('casual_quota','10')+' days; unpaid leave is unlimited. HR reviews leave requests; only Admin finalizes payroll.'
    if any(x in low for x in ('leave','late','attendance','payroll','office','policy','holiday')): return policies,'policy'
    # Optional hosted LLM: data-grounded prompt, no direct DB access, fail safely.
    key=os.environ.get('AI_API_KEY'); base=os.environ.get('AI_BASE_URL','https://api.openai.com/v1/chat/completions'); model=os.environ.get('AI_MODEL','gpt-4o-mini')
    if key:
        try:
            import requests
            payload={'model':model,'messages':[{'role':'system','content':f'You are HCM Lite assistant. Role={role}. Answer only from the supplied context and policy. Never reveal other employees personal or salary data to employee role. If unknown, say you do not know. Do not claim to perform actions.'},{'role':'user','content':q+'\nContext/policy: '+policies}], 'temperature':0.2}
            resp=requests.post(base,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json=payload,timeout=15); resp.raise_for_status(); return resp.json()['choices'][0]['message']['content'],'llm_policy'
        except Exception: return 'The AI service is temporarily unavailable. Please use the standard forms or try again shortly.','fallback'
    return 'I can answer questions about attendance, leave balances, leave policies, headcount, late-comers and payroll summaries. For a question needing other data, configure AI_API_KEY in the backend environment.','help'

@app.route('/api/health')
def health(): return jsonify({'ok':True,'app':'HCM Lite','database':'connected'})
@app.errorhandler(413)
def too_large(e): return 'Upload too large. Maximum 2 MB.',413
@app.errorhandler(500)
def internal_error(e): return render_template('error.html',message='Unexpected server error. Check server logs; no secret details are shown here.'),500

if __name__=='__main__':
    host=os.environ.get('HOST','127.0.0.1'); port=int(os.environ.get('PORT','5000'))
    app.run(host=host,port=port,debug=False)