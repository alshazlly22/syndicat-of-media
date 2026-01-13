import os, sqlite3
from flask import Flask, render_template_string, request, redirect, session, url_for
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'shazlly_master_locked_2026'

# إعدادات الملفات
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- قاعدة البيانات ---
def get_db():
    p = os.path.join(os.path.dirname(__file__), 'syndicate_core.db')
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn

def log_act(action):
    db = get_db()
    db.execute("INSERT INTO logs (u, act, dt) VALUES (?, ?, ?)", 
               (session.get('user', 'unknown'), action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    db.commit()
def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (u TEXT PRIMARY KEY, p TEXT, r TEXT, perms TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, u TEXT, act TEXT, dt TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS members (
        uid TEXT PRIMARY KEY, name TEXT, nat_id TEXT, phone TEXT, address TEXT, 
        qual TEXT, branch TEXT, work TEXT, req_job TEXT, 
        img_p TEXT, img_cf TEXT, img_cb TEXT,
        status TEXT DEFAULT 'نشط', added_by TEXT, date TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS refunds (
        id INTEGER PRIMARY KEY, applicant_name TEXT, applicant_id TEXT, amt REAL, 
        reason TEXT, status TEXT DEFAULT 'قيد الانتظار', staff TEXT, date TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS revenues (
        id INTEGER PRIMARY KEY, source_name TEXT, amt REAL, reason TEXT, staff TEXT, date TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS disciplinary (
        id INTEGER PRIMARY KEY, uid TEXT, u_name TEXT, session_num TEXT, 
        violation TEXT, decision TEXT, severity TEXT, head TEXT, date TEXT,
        UNIQUE(uid, session_num, date))""")
    c.execute("CREATE TABLE IF NOT EXISTS frozen (id INTEGER PRIMARY KEY, uid TEXT, name TEXT, reason TEXT, staff TEXT, date TEXT, UNIQUE(uid, date))")
    c.execute("CREATE TABLE IF NOT EXISTS consultants (id INTEGER PRIMARY KEY, name TEXT, spec TEXT, phone TEXT, address TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY, title TEXT, sender TEXT, phone TEXT, details TEXT, 
        cat TEXT, status TEXT DEFAULT 'جديد', staff TEXT, date TEXT)""")
    c.execute("CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)")
    c.execute("INSERT OR IGNORE INTO users VALUES ('alshazlly', '111', 'admin', 'all')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('logo', ''), ('main_img', '')")
    conn.commit(); conn.close()

# --- التصميم ---
def get_style():
    return """<style>
    :root { --side: #0f172a; --gold: #ca8a04; --bg: #f8fafc; --green: #10b981; --red: #ef4444; }
    body{margin:0; font-family:'Segoe UI', Tahoma; background:var(--bg); direction:rtl; display:flex;}
    .sidebar{width:260px; background:var(--side); color:white; height:100vh; position:fixed; padding:15px; border-left:3px solid var(--gold); overflow-y:auto;}
    .main{margin-right:260px; width:calc(100% - 260px); padding:20px; box-sizing:border-box;}
    .card{background:white; padding:20px; border-radius:12px; box-shadow:0 2px 10px rgba(0,0,0,0.05); margin-bottom:20px; border-top:4px solid var(--gold);}
    .grid{display:grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap:15px;}
    input, select, textarea{padding:12px; border:1px solid #e2e8f0; border-radius:8px; width:100%; margin-bottom:10px; font-family:inherit;}
    .btn{background:var(--gold); color:white; border:none; padding:12px; border-radius:8px; cursor:pointer; font-weight:bold; width:100%;}
    .btn-danger { background:var(--red); color:white; border:none; padding:10px; border-radius:8px; cursor:pointer; }
    .nav-link{color:#94a3b8; display:block; padding:12px; text-decoration:none; border-radius:8px; font-size:14px; margin-bottom:5px;}
    .nav-link:hover, .active{background:rgba(202, 138, 4, 0.1); color:var(--gold);}
    table{width:100%; border-collapse:collapse; margin-top:10px;} th, td{padding:10px; border:1px solid #eee; text-align:center;}
    /* تنسيق صورة الواجهة لتناسب الإطار */
    .main-img-container { width: 100%; max-height: 250px; overflow: hidden; border-radius: 12px; margin-bottom: 20px; background: #eee; display: flex; justify-content: center; align-items: center; }
    .main-img-container img { width: 100%; height: 100%; object-fit: contain; }
    /* تنسيق إطار الأخبار المطور */
    .news-frame { width: 100%; height: 700px; border: none; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    </style>"""

def wrap(content, title):
    db = get_db()
    u_name = session.get('user', '')
    
    # جلب اللوجو وصلاحيات المستخدم
    logo_data = db.execute("SELECT v FROM settings WHERE k='logo'").fetchone()
    l_path = f"/static/uploads/{logo_data['v']}" if logo_data and logo_data['v'] else ""
    user_row = db.execute("SELECT perms FROM users WHERE u=?", (u_name,)).fetchone()
    p = user_row['perms'] if user_row else ""
    is_admin = (u_name == 'alshazlly')
    is_view_only = 'view_only' in p and not is_admin

    # بناء القائمة الجانبية (Sidebar) باللون الأسود الملكي لكسر حدة اللون الفاتح
    all_links = [
        ('🏠 الرئيسية', '/dashboard', 'all'),
        ('👥 شؤون الأعضاء', '/members', 'members'),
        ('💰 الإدارة المالية', '/refunds', 'finance'),
        ('⚖️ اللجنة التأديبية', '/disciplinary', 'disciplinary'),
        ('🚫 سجل الشطب', '/frozen', 'frozen'),
        ('👨‍💼 قسم المستشارين', '/consultants', 'consult'),
        ('📩 الشكاوي والمهام', '/tasks', 'tasks')
    ]

    menu_html = ""
    for label, link, key in all_links:
        if key == 'all' or key in p or is_admin:
            menu_html += f'<a href="{link}" class="nav-link"><span>{label}</span></a>'

    admin_tools = ""
    if is_admin:
        admin_tools = f"""
        <div class="admin-label">التحكم السيادي</div>
        <a href="/admin_users" class="nav-link admin-link">⚙️ إدارة النظام</a>
        <a href="/logs" class="nav-link admin-link">📜 الرقابة العامة</a>
        """

    return f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <title>{title} | Premium Off-White System</title>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-offwhite: #fcfaf7; /* لون الأوف وايت الملكي */
                --side-bg: #0c0c0c;     /* أسود مطفي للقائمة */
                --gold: #b89550;        /* ذهبي معتق */
                --gold-light: #d4af37;
                --text-dark: #2d3436;
                --gray-soft: #95a5a6;
                --danger: #d63031;
                --card-white: #ffffff;
            }}
            * {{ box-sizing: border-box; font-family: 'Cairo', sans-serif; }}
            body {{ margin: 0; background: var(--bg-offwhite); color: var(--text-dark); display: flex; height: 100vh; overflow: hidden; }}

            /* القائمة الجانبية (Contrast) */
            .sidebar {{ 
                width: 280px; background: var(--side-bg); display: flex; flex-direction: column;
                box-shadow: 10px 0 30px rgba(0,0,0,0.1); z-index: 100;
            }}
            .logo-box {{ padding: 45px 20px; text-align: center; border-bottom: 1px solid rgba(184, 149, 80, 0.2); }}
            .logo-box img {{ max-width: 140px; filter: brightness(1.2); }}
            
            .nav-menu {{ flex: 1; padding: 20px 0; overflow-y: auto; }}
            .nav-link {{ 
                display: flex; align-items: center; padding: 14px 30px; color: #ced4da; 
                text-decoration: none; font-size: 15px; transition: 0.3s all;
                border-right: 4px solid transparent;
            }}
            .nav-link:hover {{ background: rgba(184, 149, 80, 0.1); color: var(--gold-light); border-right-color: var(--gold); }}
            
            .admin-label {{ padding: 25px 30px 10px; font-size: 11px; color: #555; text-transform: uppercase; letter-spacing: 2px; }}
            .admin-link {{ color: var(--gold) !important; font-weight: bold; }}

            /* المحتوى الرئيسي */
            .main-content {{ flex: 1; display: flex; flex-direction: column; position: relative; }}
            .header-bar {{ 
                background: var(--card-white); height: 80px; display: flex; align-items: center; 
                justify-content: space-between; padding: 0 40px; border-bottom: 1px solid #eee;
            }}
            .header-bar h2 {{ color: var(--text-dark); margin: 0; font-weight: 700; border-right: 5px solid var(--gold); padding-right: 15px; }}
            
            .user-box {{ 
                display: flex; align-items: center; gap: 15px; background: var(--bg-offwhite); 
                padding: 10px 20px; border-radius: 12px; border: 1px solid #eee;
            }}
            
            .scroll-area {{ flex: 1; padding: 35px 50px; overflow-y: auto; }}

            /* البطاقات (Cards) الاحترافية بالفلفل الذهبي */
            .card {{ 
                background: var(--card-white); border-radius: 20px; padding: 30px; 
                border: 1px solid rgba(0,0,0,0.03); margin-bottom: 25px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.02);
            }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 25px; }}
            
            /* المدخلات والأزرار */
            input, select {{ 
                background: #fff; border: 1px solid #e0e0e0; color: #333;
                padding: 12px 18px; border-radius: 12px; outline: none; transition: 0.3s;
            }}
            input:focus {{ border-color: var(--gold); box-shadow: 0 5px 15px rgba(184, 149, 80, 0.1); }}
            
            .btn {{ 
                background: linear-gradient(135deg, var(--side-bg) 0%, #333 100%);
                color: var(--gold); border: 1px solid var(--gold); padding: 12px 28px; 
                border-radius: 12px; cursor: pointer; font-weight: 700; transition: 0.3s;
            }}
            .btn:hover {{ background: var(--gold); color: white; transform: translateY(-2px); }}
            
            /* الجداول (تنسيق ملكي) */
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ padding: 20px; color: var(--side-bg); background: #f8f9fa; font-weight: 700; border-bottom: 2px solid var(--gold); text-align: center; }}
            td {{ padding: 18px; border-bottom: 1px solid #f1f1f1; text-align: center; color: #444; }}
            tr:hover td {{ background: #fffdf5; color: var(--gold); }}

            .logout-btn {{ 
                margin: 25px; padding: 15px; background: #fff1f1; color: var(--danger); 
                text-decoration: none; text-align: center; border-radius: 12px; font-weight: bold;
                transition: 0.3s; border: 1px solid #ffebeb;
            }}
            .logout-btn:hover {{ background: var(--danger); color: white; }}

            .view-only-restrict {{ display: {'none' if is_view_only else 'block'}; }}
        </style>
    </head>
    <body>
        <aside class="sidebar">
            <div class="logo-box">
                {f'<img src="{l_path}">' if l_path else f"<h2 style='color:var(--gold)'>نقابة الإعلام</h2>"}
            </div>
            <nav class="nav-menu">
                {menu_html}
                {admin_tools}
            </nav>
            <a href="/logout" class="logout-btn">🚪 خروج آمن</a>
        </aside>

        <main class="main-content">
            <header class="header-bar">
                <h2>{title}</h2>
                <div class="user-box">
                    <div style="text-align: left;">
                        <div style="font-size:14px; color:var(--text-dark); font-weight:bold;">{u_name}</div>
                        <div style="font-size:11px; color:var(--gold);">{"وضع الرقابة" if is_view_only else "إدارة النظام"}</div>
                    </div>
                    <div style="width:40px; height:40px; background:var(--side-bg); border: 2px solid var(--gold); border-radius:50%; display:flex; align-items:center; justify-content:center; color:var(--gold); font-weight:bold;">
                        {u_name[0].upper()}
                    </div>
                </div>
            </header>

            <div class="scroll-area">
                {content}
            </div>
        </main>
    </body>
    </html>
    """

# --- المسارات ---

@app.route('/')
def root(): return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db(); u = conn.execute("SELECT * FROM users WHERE u=? AND p=?", (request.form['u'], request.form['p'])).fetchone()
        if u: 
            session['user'], session['role'], session['perms'] = u['u'], u['r'], u['perms']
            return redirect('/dashboard')
    return f'<html><head>{get_style()}</head><body style="justify-content:center;align-items:center;background:var(--side);display:flex;"><div style="background:white;padding:40px;border-radius:20px;width:320px;text-align:center;"><h2>دخول</h2><form method="POST"><input name="u" placeholder="المستخدم"><input name="p" type="password" placeholder="السر"><button class="btn">دخول</button></form></div></body></html>'

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session: return redirect('/login')
    conn = get_db()
    u_name = session.get('user')
    is_admin = (u_name == 'alshazlly')
    
    # جلب صلاحيات الموظف
    user_row = conn.execute("SELECT perms FROM users WHERE u=?", (u_name,)).fetchone()
    p = user_row['perms'] if user_row else ""
    is_view_only = 'view_only' in p

    # --- 1. معالجة الأوامر (إرسال شكوى من الرئيسية + أوامر المدير) ---
    if request.method == 'POST':
        # متاح للموظف إرسال شكوى/مهمة فقط
        if 'send_task' in request.form:
            title = request.form.get('t_title')
            desc = request.form.get('t_desc')
            conn.execute("INSERT INTO tasks (title, description, sender, status, date) VALUES (?,?,?,?,?)",
                         (title, desc, u_name, 'جديد', datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            return redirect('/dashboard?success=1')
            
        # أوامر المدير (الصور ورابط جوجل)
        if is_admin:
            if 'upload_header' in request.form:
                f = request.files.get('header_img')
                if f:
                    fname = "header_main.jpg"
                    f.save(os.path.join(UPLOAD_FOLDER, fname))
                    conn.execute("INSERT OR REPLACE INTO settings (k, v) VALUES ('main_banner', ?)", (fname,))
            elif 'upload_img' in request.form:
                idx = request.form.get('idx')
                f = request.files.get('img_file')
                if f:
                    fname = secure_filename(f"slot_{idx}_{f.filename}")
                    f.save(os.path.join(UPLOAD_FOLDER, fname))
                    conn.execute("INSERT OR REPLACE INTO settings (k, v) VALUES (?, ?)", (f"slot_{idx}", fname))
            elif 'del_img' in request.form:
                idx = request.form.get('idx')
                conn.execute("DELETE FROM settings WHERE k=?", (f"slot_{idx}",))
            elif 'save_google' in request.form:
                url = request.form.get('google_url')
                conn.execute("INSERT OR REPLACE INTO settings (k, v) VALUES ('google_form', ?)", (url,))
            conn.commit()
            return redirect('/dashboard')

    # --- 2. جلب بيانات الصور ---
    header_data = conn.execute("SELECT v FROM settings WHERE k='main_banner'").fetchone()
    header_src = f"/static/uploads/{header_data['v']}" if header_data else ""
    google_url = conn.execute("SELECT v FROM settings WHERE k='google_form'").fetchone()
    g_link = google_url['v'] if google_url else ""

    # --- 3. بناء واجهة المستخدم ---
    
    # أ- صورة الرأس
    h = f"""<div class='card' style='padding:0; border:none; overflow:hidden; margin-bottom:20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);'>
        <div style='width:100%; background:#2c3e50; min-height:150px;'>
            { f'<img src="{header_src}" style="width:100%; display:block; object-fit: contain;">' if header_src else '<div style="color:white; padding:50px; text-align:center;">بانتظار رفع صورة الواجهة</div>' }
        </div>
        {"<form method='POST' enctype='multipart/form-data' style='background:#f8fafc; padding:10px; border-top:1px solid #ddd; display:flex; align-items:center; gap:10px;'>" if is_admin else ""}
        {f"<b>تحديث الواجهة:</b><input type='file' name='header_img'><button name='upload_header' class='btn'>رفع</button></form>" if is_admin else ""}
    </div>"""

    # ب- قسم البحث السريع (يظهر للموظف ذو صلاحية الرؤية)
    if is_view_only and not is_admin:
        h += """<div class='card' style='background: #f0f9ff; border: 1px solid #bae6fd;'>
            <h4 style='margin-top:0; color:#0369a1;'>🔍 مركز البحث الشامل (الاستعلام فقط)</h4>
            <div class='grid' style='grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;'>
                <form action='/members' method='GET'><input name='search' placeholder='🔍 بحث في الأعضاء...'><button class='btn' style='width:100%; margin-top:5px; background:#0369a1;'>بحث الأعضاء</button></form>
                <form action='/refunds' method='GET'><input name='search' placeholder='💰 بحث في المالية...'><button class='btn' style='width:100%; margin-top:5px; background:#0369a1;'>بحث المالية</button></form>
                <form action='/consultants' method='GET'><input name='search' placeholder='👨‍💼 بحث مستشار...'><button class='btn' style='width:100%; margin-top:5px; background:#0369a1;'>بحث مستشارين</button></form>
                <form action='/disciplinary' method='GET'><input name='search' placeholder='⚖️ بحث في التأديبية...'><button class='btn' style='width:100%; margin-top:5px; background:#075985;'>بحث التأديبية</button></form>
                <form action='/frozen' method='GET'><input name='search' placeholder='🚫 بحث في الشطب والفصل...'><button class='btn' style='width:100%; margin-top:5px; background:#075985;'>بحث الشطب</button></form>
            </div>
        </div>"""

    # ج- قسم تسجيل مهمة/شكوى (يظهر للجميع)
    h += f"""<div class='card' style='border-right: 5px solid #fbbf24; background: #fffdf5;'>
        <h4 style='color: #854d0e;'>📩 تسجيل شكوى أو مهمة عمل جديدة</h4>
        <form method='POST' class='grid' style='display:flex; gap:10px; flex-wrap: wrap;'>
            <input name='t_title' placeholder='عنوان الشكوى أو المهمة' required style='flex:1; min-width:200px;'>
            <input name='t_desc' placeholder='تفاصيل الموضوع...' required style='flex:2; min-width:300px;'>
            <button name='send_task' class='btn' style='background:#fbbf24; color:#000; font-weight:bold; min-width:120px;'>إرسال للمدير</button>
        </form>
        { "<p style='color:green; font-weight:bold; margin-top:10px;'>✅ تم إرسال المهمة بنجاح إلى قسم الشكاوي!</p>" if request.args.get('success') else "" }
    </div>"""

    # د- الـ 10 إطارات
    h += "<div style='display: flex; flex-wrap: wrap; gap: 15px; margin-bottom:25px; justify-content: center;'>"
    for i in range(1, 11):
        img_slot = conn.execute("SELECT v FROM settings WHERE k=?", (f"slot_{i}",)).fetchone()
        slot_src = f"/static/uploads/{img_slot['v']}" if img_slot else ""
        h += f"""<div class='card' style='width: 200px; height: 120px; padding: 5px; text-align: center; position: relative;'>
            <div style='width: 100%; height: 75px; background: #f1f5f9; border-radius: 4px; display: flex; align-items: center; justify-content: center; overflow: hidden;'>
                { f'<img src="{slot_src}" style="max-width:100%; max-height:100%;">' if slot_src else f"<span>إطار {i}</span>" }
            </div>
            { f'<form method="POST" enctype="multipart/form-data" style="margin-top:5px;"><input type="hidden" name="idx" value="{i}"><input type="file" name="img_file" style="font-size:8px; width:130px;" onchange="this.form.submit()"><input type="hidden" name="upload_img"></form>' if is_admin and not slot_src else "" }
            { f'<form method="POST" style="position:absolute; top:2px; right:2px;"><input type="hidden" name="idx" value="{i}"><button name="del_img" style="background:red; color:white; border:none; border-radius:50%; width:18px; height:18px; cursor:pointer;">×</button></form>' if is_admin and slot_src else "" }
        </div>"""
    h += "</div>"

    # هـ- استمارة جوجل وفيسبوك
    h += f"""<div class='grid'>
        <div class='card' style='height: 460px; display: flex; flex-direction: column;'>
            <h4>📋 استمارة جوجل</h4>
            <div style='flex: 1; border: 1px solid #eee;'>
                { f'<iframe src="{g_link}" width="100%" height="100%" frameborder="0"></iframe>' if g_link else "لا يوجد رابط" }
            </div>
            { f'<form method="POST" style="margin-top:10px;"><input name="google_url" value="{g_link}" style="width:70%; font-size:11px;"><button name="save_google" class="btn">حفظ</button></form>' if is_admin else "" }
        </div>
        <div class='card' style='height: 460px;'>
            <h4>📢 أخبار النقابة</h4>
            <iframe src='https://www.facebook.com/plugins/page.php?href=https://facebook.com/Syndicate.of.Media.workers&tabs=timeline' style="width:100%; height:380px; border:none;"></iframe>
        </div>
    </div>"""

    return render_template_string(wrap(h, "لوحة التحكم"))

import smtplib
from email.mime.text import MIMEText
from email.header import Header

def send_email_notification(subject, sender_name, phone, details, category):
    # إعدادات البريد الإلكتروني
    msg_from = "your-email@gmail.com" # إيميلك الذي سيرسل
    msg_to = "syndicate.of.media.workers@gmail.com"
    password = "your-app-password" # كلمة مرور التطبيقات من جوجل
    
    body = f"""
    تم تسجيل {category} جديد في النظام:
    ----------------------------------
    الموضوع: {subject}
    المقدم: {sender_name}
    الهاتف: {phone}
    التفاصيل: {details}
    بواسطة الموظف: {session.get('user')}
    التاريخ: {datetime.now().strftime("%Y-%m-%d %H:%M")}
    """
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = Header(f"إشعار جديد: {subject}", 'utf-8')
    msg['From'] = msg_from
    msg['To'] = msg_to

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(msg_from, password)
            server.sendmail(msg_from, msg_to, msg.as_string())
    except Exception as e:
        print(f"خطأ في إرسال الإيميل: {e}")

@app.route('/tasks', methods=['GET', 'POST'])
def tasks():
    if 'user' not in session: return redirect('/login')
    conn = get_db()
    u_name = session.get('user')
    is_admin = (u_name == 'alshazlly')
    search = request.args.get('search', '')

    if request.method == 'POST':
        # 1. معالجة الحذف (للمدير فقط أو حسب الصلاحية)
        if 'delete_id' in request.form and is_admin:
            conn.execute("DELETE FROM tasks WHERE id = ?", (request.form['delete_id'],))
            conn.commit()
            return redirect('/tasks')

        # 2. معالجة الإضافة الجديدة
        title = request.form['t']
        sender = request.form['sender']
        phone = request.form['phone']
        details = request.form['d']
        cat = request.form['cat'] # سيستقبل "شكوى" أو "طلب"
        
        conn.execute("INSERT INTO tasks (title, sender, phone, details, cat, staff, date) VALUES (?,?,?,?,?,?,?)", 
                     (title, sender, phone, details, cat, u_name, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        
        # إرسال الإيميل تلقائياً
        send_email_notification(title, sender, phone, details, cat)
        
        return redirect('/tasks')

    # جلب البيانات
    data = conn.execute("SELECT * FROM tasks WHERE (title LIKE ? OR sender LIKE ?) ORDER BY id DESC", 
                        (f"%{search}%", f"%{search}%")).fetchall()

    # واجهة البحث
    h = f"<div class='card'><h4>🔍 بحث في الشكاوي والطلبات</h4><form method='GET' style='display:flex; gap:10px;'><input name='search' placeholder='بحث بالعنوان أو الاسم...' value='{search}' style='flex:1'><button class='btn'>بحث</button></form></div>"

    # واجهة الإضافة (مع تغيير "مهمة" إلى "طلب")
    h += """<div class='card'><h4>📩 إضافة جديد</h4><form method='POST' class='grid'>
            <select name='cat'><option value='شكوى'>شكوى</option><option value='طلب'>طلب</option></select>
            <input name='t' placeholder='الموضوع' required>
            <input name='sender' placeholder='المقدم' required>
            <input name='phone' placeholder='الهاتف'>
            <textarea name='d' placeholder='التفاصيل' style='grid-column:span 2'></textarea>
            <button class='btn'>حفظ وإرسال إشعار</button></form></div>"""

    # الجدول مع خاصية الحذف
    h += "<table><tr><th>النوع</th><th>العنوان</th><th>المقدم</th><th>التاريخ</th>"
    if is_admin: h += "<th>إجراء</th>"
    h += "</tr>"
    
    for r in data: 
        h += f"<tr><td><span style='color:{'#d63031' if r['cat']=='شكوى' else '#b89550'}'>{r['cat']}</span></td>"
        h += f"<td>{r['title']}</td><td>{r['sender']}</td><td>{r['date']}</td>"
        if is_admin:
            h += f"""<td><form method='POST' onsubmit="return confirm('هل أنت متأكد من الحذف؟');">
                     <input type='hidden' name='delete_id' value='{r['id']}'>
                     <button class='btn-red' style='padding:5px 10px; font-size:12px;'>حذف</button>
                     </form></td>"""
        h += "</tr>"
        
    return render_template_string(wrap(h + "</table>", "الشكاوي والطلبات"))
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if session.get('role') != 'admin': return redirect('/')
    conn = get_db()
    if request.method == 'POST':
        if 'del_main' in request.form:
            conn.execute("UPDATE settings SET v='' WHERE k='main_img'"); conn.commit()
        else:
            for key in ['logo', 'main_img']:
                if key in request.files and request.files[key].filename:
                    fname = secure_filename(request.files[key].filename)
                    request.files[key].save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                    conn.execute("UPDATE settings SET v=? WHERE k=?", (fname, key))
            conn.commit()
    return render_template_string(wrap("<div class='card'><form method='POST' enctype='multipart/form-data'><h5>تحديث الشعار</h5><input type='file' name='logo'><h5>تحديث صورة الواجهة</h5><input type='file' name='main_img'><button class='btn'>تحديث</button></form><hr><form method='POST'><button name='del_main' class='btn-danger' style='width:100%'>حذف صورة الواجهة الحالية</button></form></div>", "الإعدادات"))

# --- باقي المسارات (المالية، الأعضاء، التأديب، الشطب، المستشارين، السجل) تظل كما هي دون تغيير ---

@app.route('/members', methods=['GET', 'POST'])
def members():
    db = get_db()
    search = request.args.get('q', '')
    
    # --- 1. عملية الحفظ (POST) ---
    if request.method == 'POST':
        fnames = {}
        for key in ['img_p', 'img_cf', 'img_cb']:
            if key in request.files:
                f = request.files[key]
                if f.filename:
                    fname = secure_filename(f"{datetime.now().timestamp()}_{f.filename}")
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                    fnames[key] = fname
                else: fnames[key] = ""
        
        db.execute("""INSERT INTO members (uid, name, nat_id, phone, address, qual, branch, work, img_p, img_cf, img_cb, date) 
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", 
                   (request.form['id'], request.form['n'], request.form['nat'], request.form['p'], 
                    request.form['addr'], request.form['qul'], request.form['br'], request.form['wrk'],
                    fnames.get('img_p',''), fnames.get('img_cf',''), fnames.get('img_cb',''), datetime.now().strftime("%Y-%m-%d")))
        db.commit()

    # --- 2. عملية البحث والجلب (GET) ---
    if search:
        data = db.execute("SELECT * FROM members WHERE name LIKE ? OR uid LIKE ? OR nat_id LIKE ?", (f'%{search}%', f'%{search}%', f'%{search}%')).fetchall()
    else:
        data = db.execute("SELECT * FROM members ORDER BY date DESC LIMIT 50").fetchall()

    # --- 3. بناء الواجهة (HTML) ---
    h = """<div class='card'><h4>إضافة عضو جديد بالتفاصيل</h4>
        <form method='POST' enctype='multipart/form-data'>
        <div class='grid'>
            <input name='id' placeholder='رقم القيد' required> <input name='n' placeholder='الاسم الكامل' required>
            <input name='nat' placeholder='الرقم القومي'> <input name='p' placeholder='الهاتف'>
            <input name='addr' placeholder='العنوان بالتفصيل'> <input name='qul' placeholder='المؤهل الدراسي'>
            <input name='br' placeholder='فرع النقابة'> <input name='wrk' placeholder='جهة العمل'>
        </div>
        <div class='grid'>
            <div><label class='file-label'>الصورة الشخصية</label><input type='file' name='img_p'></div>
            <div><label class='file-label'>وجه البطاقة</label><input type='file' name='img_cf'></div>
            <div><label class='file-label'>ظهر البطاقة</label><input type='file' name='img_cb'></div>
        </div>
        <button class='btn'>حفظ العضو والمرفقات</button></form></div>
        
        <div class='search-box'><form method='GET' style='display:flex; width:100%; gap:10px;'>
        <input name='q' placeholder='بحث بالاسم أو رقم القيد...' style='margin:0' value='""" + search + """'>
        <button class='btn' style='width:100px'>بحث</button></form></div>
        
        <div class='card' style='overflow-x:auto;'><table><tr><th>صورة</th><th>القيد</th><th>الاسم</th><th>الرقم القومي</th><th>المرفقات</th></tr>"""
    
    for r in data: 
        img_p = f"<img src='/static/uploads/{r['img_p']}' style='width:35px;height:35px;border-radius:50%;' onclick='window.open(this.src)'>" if r['img_p'] else "👤"
        id_f = f"<a href='/static/uploads/{r['img_cf']}' target='_blank' style='color:#ca8a04;text-decoration:none;font-size:12px;'>[وجه]</a>" if r['img_cf'] else ""
        id_b = f"<a href='/static/uploads/{r['img_cb']}' target='_blank' style='color:#ca8a04;text-decoration:none;font-size:12px;'>[ظهر]</a>" if r['img_cb'] else ""
        
        h += f"<tr><td>{img_p}</td><td>{r['uid']}</td><td>{r['name']}</td><td>{r['nat_id']}</td><td>{id_f} {id_b}</td></tr>"
    
    return render_template_string(wrap(h + "</table></div>", "قاعدة بيانات الأعضاء"))
@app.route('/refunds', methods=['GET', 'POST'])
def refunds():
    if 'user' not in session: return redirect('/login')
    conn = get_db()
    
    # --- 1. معالجة عمليات الحذف (إضافة جديدة) ---
    if request.method == 'POST' and 'del_rev' in request.form:
        conn.execute("DELETE FROM revenues WHERE id=?", (request.form['del_rev'],))
        conn.execute("INSERT INTO logs (u, act, dt) VALUES (?,?,?)", (session['user'], "حذف سجل إيرادات", datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
    elif request.method == 'POST' and 'del_ref' in request.form:
        conn.execute("DELETE FROM refunds WHERE id=?", (request.form['del_ref'],))
        conn.execute("INSERT INTO logs (u, act, dt) VALUES (?,?,?)", (session['user'], "حذف سجل مصروفات", datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()

    # --- 2. معالجة الإضافات (نفس كودك مع توثيق السجل) ---
    if request.method == 'POST' and 'add_rev' in request.form:
        conn.execute("INSERT INTO revenues (source_name, amt, reason, staff, date) VALUES (?,?,?,?,?)", 
                     (request.form['n'], request.form['a'], request.form['r'], session['user'], datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
    elif request.method == 'POST' and 'add_ref' in request.form:
        conn.execute("INSERT INTO refunds (applicant_name, applicant_id, amt, reason, staff, date, status) VALUES (?,?,?,?,?,?,?)", 
                     (request.form['n'], request.form['id'], request.form['a'], request.form['r'], session['user'], datetime.now().strftime("%Y-%m-%d"), "منصرف"))
        conn.commit()

    # --- 3. حساب الإحصائيات (إضافة جديدة) ---
    total_rev = conn.execute("SELECT SUM(amt) FROM revenues").fetchone()[0] or 0
    total_ref = conn.execute("SELECT SUM(amt) FROM refunds").fetchone()[0] or 0
    balance = total_rev - total_ref

    search = request.args.get('search', '')
    rev_data = conn.execute("SELECT * FROM revenues WHERE source_name LIKE ? ORDER BY id DESC", (f"%{search}%",)).fetchall()
    ref_data = conn.execute("SELECT * FROM refunds WHERE applicant_name LIKE ? ORDER BY id DESC", (f"%{search}%",)).fetchall()

    # --- 4. بناء واجهة المستخدم ---
    # شاشة الإحصائيات
    h = f"""
    <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; text-align: center;'>
        <div class='card' style='background:#dcfce7;'><h5>📈 إجمالي الوارد</h5><h3>{total_rev:,.2f}</h3></div>
        <div class='card' style='background:#fee2e2;'><h5>📉 إجمالي المنصرف</h5><h3>{total_ref:,.2f}</h3></div>
        <div class='card' style='background:#e0f2fe;'><h5>💰 صافي الرصيد</h5><h3>{balance:,.2f}</h3></div>
    </div>
    """
    
    h += f"<div class='card'><h4>🔍 بحث مالي</h4><form method='GET' style='display:flex; gap:10px;'><input name='search' placeholder='بحث باسم المصدر أو المستلم...' value='{search}'><button class='btn'>بحث</button></form></div>"
    
    h += "<div class='grid'><div class='card'><h4>➕ تسجيل وارد</h4><form method='POST'><input type='hidden' name='add_rev'><input name='n' placeholder='المصدر'><input name='a' placeholder='المبلغ'><input name='r' placeholder='البيان'><button class='btn'>حفظ</button></form></div>"
    h += "<div class='card'><h4>➖ تسجيل منصرف</h4><form method='POST'><input type='hidden' name='add_ref'><input name='n' placeholder='المستلم'><input name='id' placeholder='رقم القيد'><input name='a' placeholder='المبلغ'><input name='r' placeholder='السبب'><button class='btn' style='background:red'>حفظ</button></form></div></div>"
    
    # جدول البيانات مع إضافة خانة الحذف والنوع
    h += "<div class='card'><table><tr style='background:#f4f7f6;'><th>الاسم/المصدر</th><th>المبلغ</th><th>البيان</th><th>الحالة</th><th>إجراء</th></tr>"
    
    for r in rev_data: 
        h += f"""<tr><td>{r['source_name']}</td><td>{r['amt']}</td><td>{r['reason']}</td><td style='color:green'>وارد (+)</td>
              <td><form method='POST' style='margin:0'><input type='hidden' name='del_rev' value='{r['id']}'><button style='color:red; background:none; border:none; cursor:pointer;'>حذف</button></form></td></tr>"""
    
    for r in ref_data: 
        h += f"""<tr><td>{r['applicant_name']}</td><td>{r['amt']}</td><td>{r['reason']}</td><td style='color:red'>منصرف (-)</td>
              <td><form method='POST' style='margin:0'><input type='hidden' name='del_ref' value='{r['id']}'><button style='color:red; background:none; border:none; cursor:pointer;'>حذف</button></form></td></tr>"""
    
    return render_template_string(wrap(h + "</table></div>", "الإدارة المالية"))

@app.route('/disciplinary', methods=['GET', 'POST'])
def disciplinary():
    if 'user' not in session: return redirect('/login')
    conn = get_db()
    
    # 1. معالجة عمليات الحذف والإضافة
    if request.method == 'POST':
        if 'del_id' in request.form:
            conn.execute("DELETE FROM disciplinary WHERE id=?", (request.form['del_id'],))
            conn.execute("INSERT INTO logs (u, act, dt) VALUES (?,?,?)", 
                         (session['user'], f"حذف قرار تأديبي رقم: {request.form['del_id']}", datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            return redirect('/disciplinary')

        conn.execute("INSERT INTO disciplinary (uid, u_name, session_num, violation, decision, severity, head, date) VALUES (?,?,?,?,?,?,?,?)",
                     (request.form['uid'], request.form['un'], request.form['sn'], request.form['v'], request.form['d'], request.form['s'], request.form['h'], datetime.now().strftime("%Y-%m-%d")))
        conn.execute("INSERT INTO logs (u, act, dt) VALUES (?,?,?)", (session['user'], f"قرار تأديبي للعضو: {request.form['un']}", datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        return redirect('/disciplinary')

    # 2. معالجة البحث (تعديل سطر جلب البيانات)
    search_q = request.args.get('q', '') # جلب نص البحث من الرابط
    if search_q:
        data = conn.execute("SELECT * FROM disciplinary WHERE u_name LIKE ? OR uid LIKE ? ORDER BY id DESC", 
                            ('%'+search_q+'%', '%'+search_q+'%')).fetchall()
    else:
        data = conn.execute("SELECT * FROM disciplinary ORDER BY id DESC").fetchall()

    # 3. واجهة المستخدم (إضافة خانة البحث)
    h = """<div class='card'><h4>⚖️ إصدار قرار لجنة تأديبية</h4><form method='POST' class='grid'>
    <input name='uid' placeholder='رقم القيد'><input name='un' placeholder='الاسم'><input name='sn' placeholder='رقم الجلسة'><input name='v' placeholder='نوع المخالفة'>
    <input name='s' placeholder='العقوبة'><input name='h' placeholder='رئيس اللجنة'><textarea name='d' placeholder='تفاصيل القرار' style='grid-column: span 2'></textarea>
    <button class='btn'>حفظ القرار</button></form></div>"""
    
    # إضافة خانة البحث هنا
    h += f"""<div class='card' style='background: #f1f5f9;'>
        <form method='GET' style='display:flex; gap:10px;'>
            <input name='q' placeholder='بحث باسم العضو أو رقم القيد...' value='{search_q}' style='margin:0'>
            <button class='btn' style='width:100px'>🔍 بحث</button>
            <a href='/disciplinary' class='btn' style='width:100px; background:#64748b; text-decoration:none; text-align:center; line-height:40px; padding:0'>إلغاء</a>
        </form>
    </div>"""

    h += """<div class='card'><h4>📜 سجل القرارات التاريخية</h4><table>
    <tr><th>القيد</th><th>الاسم</th><th>القرار</th><th>التاريخ</th><th>إجراء</th></tr>"""

    for r in data: 
        h += f"""<tr>
            <td>{r['uid']}</td>
            <td>{r['u_name']}</td>
            <td>{r['decision']}</td>
            <td>{r['date']}</td>
            <td>
                <form method='POST' style='margin:0' onsubmit='return confirm("هل أنت متأكد من حذف هذا القرار؟")'>
                    <input type='hidden' name='del_id' value='{r['id']}'>
                    <button type='submit' style='background:none; border:none; color:red; cursor:pointer; font-weight:bold;'>حذف</button>
                </form>
            </td>
        </tr>"""
    
    return render_template_string(wrap(h + "</table></div>", "اللجنة التأديبية"))

@app.route('/frozen', methods=['GET', 'POST'])
def frozen():
    if not session.get('user'): return redirect('/login')
    db = get_db()
    
    # --- 1. معالجة العمليات (إضافة قرار أو حذفه) ---
    if request.method == 'POST':
        if 'del_id' in request.form:
            # حذف قرار الشطب
            db.execute("DELETE FROM frozen WHERE id=?", (request.form.get('del_id'),))
            db.commit()
        else:
            # إضافة قرار شطب جديد
            db.execute("INSERT INTO frozen (uid, name, reason, date) VALUES (?, ?, ?, ?)", 
                       (request.form.get('u_id'), request.form.get('u_name'), 
                        request.form.get('reason'), datetime.now().strftime("%Y-%m-%d")))
            db.commit()

    # --- 2. جلب البيانات من الجدول ---
    data = db.execute("SELECT * FROM frozen ORDER BY id DESC").fetchall()
    
    # --- 3. بناء الواجهة ---
    h = """<div class='card'><h4>🚫 تسجيل قرار شطب أو فصل</h4>
        <form method='POST' class='grid'>
            <input name='u_id' placeholder='رقم القيد' required> 
            <input name='u_name' placeholder='اسم العضو' required>
            <input name='reason' placeholder='سبب الشطب أو الفصل' required style='grid-column: span 2;'>
            <button class='btn'>إصدار القرار</button>
        </form></div>"""

    h += """<div class='card'><table>
            <tr><th>رقم القيد</th><th>الاسم</th><th>السبب</th><th>التاريخ</th><th>إجراء</th></tr>"""
    
    for r in data:
        h += f"""<tr>
                    <td>{r['uid']}</td>
                    <td>{r['name']}</td>
                    <td>{r['reason']}</td>
                    <td>{r['date']}</td>
                    <td>
                        <form method='POST' style='display:inline;'>
                            <input type='hidden' name='del_id' value='{r['id']}'>
                            <button class='btn-red' onclick='return confirm(\"هل تريد التراجع عن قرار الشطب؟\")'>حذف</button>
                        </form>
                    </td>
                </tr>"""
    
    return render_template_string(wrap(h + "</table></div>", "قسم الشطب والفصل"))

@app.route('/consultants', methods=['GET', 'POST'])
def consultants():
    if 'user' not in session: return redirect('/login')
    conn = get_db()
    
    # 1. معالجة العمليات (إضافة، تعديل، حذف)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            conn.execute("INSERT INTO consultants (name, spec, phone, address) VALUES (?,?,?,?)", 
                         (request.form['n'], request.form['s'], request.form['p'], request.form['a']))
        elif action == 'edit_save':
            conn.execute("UPDATE consultants SET name=?, spec=?, phone=?, address=? WHERE id=?", 
                         (request.form['n'], request.form['s'], request.form['p'], request.form['a'], request.form['id']))
        elif action == 'delete':
            conn.execute("DELETE FROM consultants WHERE id=?", (request.form['id'],))
        
        conn.commit()
        return redirect('/consultants')

    # 2. جلب البيانات وبيانات التعديل
    edit_id = request.args.get('edit')
    edit_item = conn.execute("SELECT * FROM consultants WHERE id=?", (edit_id,)).fetchone() if edit_id else None
    data = conn.execute("SELECT * FROM consultants ORDER BY id DESC").fetchall()

    # 3. واجهة المستخدم
    # نموذج الإضافة والتعديل
    h = f"""<div class='card'>
        <h4>{"📝 تعديل بيانات مستشار" if edit_item else "👨‍💼 إضافة مستشار جديد"}</h4>
        <form method='POST' class='grid'>
            <input type='hidden' name='action' value='{"edit_save" if edit_item else "add"}'>
            <input type='hidden' name='id' value='{edit_item['id'] if edit_item else ""}'>
            <input name='n' placeholder='الاسم' value='{edit_item['name'] if edit_item else ""}' required>
            <input name='s' placeholder='التخصص' value='{edit_item['spec'] if edit_item else ""}' required>
            <input name='p' placeholder='الهاتف' value='{edit_item['phone'] if edit_item else ""}' required>
            <input name='a' placeholder='العنوان' value='{edit_item['address'] if edit_item else ""}' required>
            <button class='btn'>{"حفظ التعديلات" if edit_item else "إضافة"}</button>
            {"<a href='/consultants' style='color:red; margin-right:10px;'>إلغاء</a>" if edit_item else ""}
        </form></div>"""

    # جدول عرض البيانات
    h += """<div class='card'><h4>📋 قائمة المستشارين المسجلين</h4>
    <table style='width:100%'>
    <tr style='background:#f4f7f6;'><th>الاسم</th><th>التخصص</th><th>الهاتف</th><th>العنوان</th><th>إجراءات</th></tr>"""
    
    for r in data:
        h += f"""<tr>
            <td>{r['name']}</td>
            <td>{r['spec']}</td>
            <td>{r['phone']}</td>
            <td>{r['address']}</td>
            <td>
                <div style='display:flex; gap:10px;'>
                    <a href='?edit={r['id']}' style='color:orange; text-decoration:none;'>تعديل</a>
                    <form method='POST' style='margin:0' onsubmit='return confirm("حذف المستشار؟")'>
                        <input type='hidden' name='action' value='delete'>
                        <input type='hidden' name='id' value='{r['id']}'>
                        <button style='background:none; border:none; color:red; cursor:pointer;'>حذف</button>
                    </form>
                </div>
            </td></tr>"""
    
    return render_template_string(wrap(h + "</table></div>", "إدارة المستشارين"))

@app.route('/admin_users', methods=['GET', 'POST'])
def admin_users():
    if session.get('user') != 'alshazlly': return redirect('/dashboard')
    db = get_db()
    
    if request.method == 'POST':
        if 'del' in request.form:
            db.execute("DELETE FROM users WHERE u=?", (request.form.get('del'),))
        else:
            u_name = request.form.get('u')
            u_pass = request.form.get('p_pass')
            perms_list = request.form.getlist('p')
            perms_str = ",".join(perms_list)
            if u_name and u_pass:
                db.execute("INSERT OR REPLACE INTO users VALUES (?, ?, 'staff', ?)", (u_name, u_pass, perms_str))
        db.commit()

    users = db.execute("SELECT * FROM users WHERE u != 'alshazlly'").fetchall()
    
    h = """<div class='card'><h4>🔑 إدارة الحسابات والصلاحيات</h4>
        <form method='POST' class='grid'>
            <input name='u' placeholder='اسم المستخدم' required>
            <input name='p_pass' placeholder='كلمة السر' required type='password'>
            
            <div style='grid-column: 1 / -1; background: #f8fafc; padding: 15px; border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 10px;'>
                <p style='margin-top:0; font-weight:bold; color:var(--side); border-bottom:1px solid #eee; padding-bottom:5px;'>حدد الأقسام المسموح بدخولها:</p>
                <div style='display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px;'>
                    <label><input type='checkbox' name='p' value='members'> 👥 الأعضاء</label>
                    <label><input type='checkbox' name='p' value='finance'> 💰 المالية</label>
                    <label><input type='checkbox' name='p' value='disciplinary'> ⚖️ التأديبية</label>
                    <label><input type='checkbox' name='p' value='frozen'> 🚫 الشطب</label>
                    <label><input type='checkbox' name='p' value='consult'> 👨‍💼 المستشارين</label>
                    <label><input type='checkbox' name='p' value='tasks'> 📩 الشكاوي والمهام</label>
                    <label style='color: #2563eb; font-weight: bold;'><input type='checkbox' name='p' value='view_only'> 👁️ عرض وبحث فقط</label>
                </div>
                <p style='font-size: 11px; color: #64748b; margin-top: 10px;'>* ملحوظة: صلاحية "عرض وبحث فقط" تمنع الحذف في كل الأقسام عدا الشكاوي.</p>
            </div>
            <button class='btn'>حفظ الحساب</button>
        </form></div>"""

    h += "<div class='card'><table><tr><th>المستخدم</th><th>الصلاحيات</th><th>إجراء</th></tr>"
    for u in users:
        h += f"<tr><td>{u['u']}</td><td><small>{u['perms']}</small></td><td><form method='POST'><input type='hidden' name='del' value='{u['u']}'><button class='btn-red'>حذف الحساب</button></form></td></tr>"
    
    return render_template_string(wrap(h + "</table></div>", "إدارة الحسابات"))

@app.route('/logs')
def logs():
    if session.get('role') != 'admin': return redirect('/')
    conn = get_db(); data = conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 100").fetchall()
    h = "<table><tr><th>الموظف</th><th>الإجراء</th><th>التوقيت</th></tr>"
    for r in data: h += f"<tr><td>{r['u']}</td><td>{r['act']}</td><td>{r['dt']}</td></tr>"
    return render_template_string(wrap(h + "</table>", "سجل الرقابة"))

@app.route('/logout')
def logout(): session.clear(); return redirect('/login')
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)