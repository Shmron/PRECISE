#!/usr/bin/env python3
"""
PRECISE DuckDB Access Request Service — port 35488
- /request            user submits an access request
- /status/<id>        user checks their request status
- /admin              admin dashboard (login required)
- /admin/login        admin login form
- /admin/approve      approve a request and issue API key
- /admin/reject       reject a request
"""
import sys, os
sys.path.insert(0, '/home/rutendo/PRECISE')

from flask import (Flask, request, jsonify, render_template_string,
                   redirect, url_for, session, flash)
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
import access_db

app = Flask(__name__)
app.secret_key = os.urandom(32)   # ephemeral — session survives only while process runs

# All URLs behind /duckrequest/ nginx prefix
PREFIX = '/duckrequest'

SMTP_FROM   = 'rutendosibanda18@gmail.com'
SMTP_PASS   = 'tulwiwtiswekzlhf'
ADMIN_EMAILS = [
    'rutendo.sibanda@ceshhar.org',
    'nyonih@staff.msu.ac.zw',           # bongani
    'zororo.chinwadzimba@ceshhar.org',   # zororo
]

COUNTRIES = ['Kenya', 'Mozambique', 'Gambia']

CATALOGUE_CODE = os.environ.get('CATALOGUE_ACCESS_CODE', 'PRECISE2024')
HE2AT_CODE     = os.environ.get('HE2AT_ACCESS_CODE', 'HE2AT2022')


# ── Email helpers ─────────────────────────────────────────────────────────────

def _send(to, subject, body, attachments=None):
    """Send a plain-text email with optional (filename, bytes, subtype) attachments."""
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From']    = SMTP_FROM
        msg['To']      = to
        msg.set_content(body)
        if attachments:
            for fname, data, subtype in attachments:
                msg.add_attachment(data, maintype='application',
                                   subtype=subtype, filename=fname)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(SMTP_FROM, SMTP_PASS)
            s.send_message(msg)
    except Exception:
        pass


def _build_instructions_pdf(name, api_key, countries):
    """Return PDF bytes containing the access instructions for this user."""
    countries_str = ', '.join(countries)

    r_snippet = (
        f'library(httr)\n\n'
        f'resp <- POST(\n'
        f'  "http://localhost:5000/api/query/csv",\n'
        f'  add_headers("X-API-Key" = "{api_key}"),\n'
        f'  body = list(sql = "SELECT * FROM daily_data"),\n'
        f'  encode = "json"\n'
        f')\n\n'
        f'tmp <- tempfile(fileext = ".csv")\n'
        f'writeBin(content(resp, "raw"), tmp)\n'
        f'df <- read.csv(tmp)\n\n'
        f'dim(df)   # rows x columns\n'
        f'head(df)  # first 6 rows'
    )

    py_snippet = (
        f'import sys\n'
        f'sys.path.insert(0, "/home/rutendo/PRECISE")\n'
        f'from precise_db import PreciseDB\n\n'
        f'db = PreciseDB(api_key="{api_key}")\n'
        f'df = db.query("SELECT * FROM daily_data")\n'
        f'db.close()\n\n'
        f'# df is a pandas DataFrame ready for analysis'
    )

    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    # Title
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(26, 83, 92)   # #1a535c
    pdf.cell(0, 10, 'PRECISE DuckDB — Access Instructions', ln=True)
    pdf.ln(2)

    # Subtitle
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 7, 'PALS Lab Team  |  placealert.org', ln=True)
    pdf.ln(6)

    # User details box
    pdf.set_fill_color(240, 253, 244)
    pdf.set_draw_color(16, 185, 129)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(55, 65, 81)
    pdf.cell(0, 8, f'Name: {name}', ln=True, fill=True)
    pdf.cell(0, 8, f'Approved countries: {countries_str}', ln=True, fill=True)
    pdf.ln(2)

    # API Key
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(55, 65, 81)
    pdf.cell(0, 7, 'Your API Key:', ln=True)
    pdf.set_font('Courier', '', 9)
    pdf.set_fill_color(243, 244, 246)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(0, 8, api_key, ln=True, fill=True)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(0, 6, 'Keep this key private. Do not share it.', ln=True)
    pdf.ln(6)

    # Divider
    pdf.set_draw_color(226, 232, 240)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(5)

    def section(title, code):
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(26, 83, 92)
        pdf.cell(0, 8, title, ln=True)
        pdf.ln(2)
        pdf.set_fill_color(15, 23, 42)
        pdf.set_text_color(205, 214, 244)
        pdf.set_font('Courier', '', 8.5)
        # multi-line code block
        pdf.multi_cell(0, 5.5, code, fill=True)
        pdf.ln(6)

    section('PYTHON  (PALSlab Hub notebook)', py_snippet)

    pdf.set_draw_color(226, 232, 240)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(5)

    section('R  (PALSlab Hub notebook)', r_snippet)

    # Footer note
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(107, 114, 128)
    pdf.multi_cell(0, 5,
        'R note: Uses the CSV endpoint to avoid R memory limits on large tables. '
        'httr is a standard R package. Remove LIMIT or adjust the query as needed.'
    )

    return bytes(pdf.output())


def notify_admin(req_id, name, email, institution, hub_user, countries, purpose):
    countries_str = ', '.join(countries)
    body = (
        f'A new DuckDB access request requires your approval.\n\n'
        f'Name:         {name}\n'
        f'Email:        {email}\n'
        f'Institution:  {institution}\n'
        f'Hub Username: {hub_user}\n'
        f'Countries:    {countries_str}\n\n'
        f'Purpose:\n{purpose}\n\n'
        f'Review at: https://placealert.org/duckrequest/admin\n'
        f'Request ID: {req_id}'
    )
    for addr in ADMIN_EMAILS:
        _send(addr, f'[PRECISE DuckDB] New access request from {name}', body)


def notify_user_approved(name, email, api_key, countries):
    countries_str = ', '.join(countries)
    body = (
        f'Hi {name},\n\n'
        f'Your request for access to the PRECISE DuckDB has been approved.\n\n'
        f'Approved countries: {countries_str}\n\n'
        f'Your API key:\n'
        f'  {api_key}\n\n'
        f'Keep this key private.\n\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'PYTHON (PALSlab Hub notebook)\n\n'
        f'  import sys\n'
        f'  sys.path.insert(0, "/home/rutendo/PRECISE")\n'
        f'  from precise_db import PreciseDB\n\n'
        f'  db = PreciseDB(api_key="{api_key}")\n'
        f'  df = db.query("SELECT * FROM daily_data")\n'
        f'  db.close()\n\n'
        f'  # df is a pandas DataFrame ready for analysis\n\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'R (PALSlab Hub notebook)\n\n'
        f'  library(httr)\n'
        f'  library(jsonlite)\n\n'
        f'  resp <- POST(\n'
        f'    "http://localhost:5000/api/query/csv",\n'
        f'    add_headers("X-API-Key" = "{api_key}"),\n'
        f'    body = list(sql = "SELECT * FROM daily_data"),\n'
        f'    encode = "json"\n'
        f'  )\n\n'
        f'  tmp <- tempfile(fileext = ".csv")\n'
        f'  writeBin(content(resp, "raw"), tmp)\n'
        f'  df <- read.csv(tmp)\n\n'
        f'  dim(df)   # rows x columns\n'
        f'  head(df)  # first 6 rows\n\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'PALS Lab Team\n\n'
        f'A PDF copy of these instructions is attached.'
    )
    try:
        pdf_bytes = _build_instructions_pdf(name, api_key, countries)
        attachments = [('PRECISE_Access_Instructions.pdf', pdf_bytes, 'pdf')]
    except Exception as e:
        app.logger.error(f'PDF generation failed: {e}')
        attachments = None
    _send(email, '[PRECISE DuckDB] Your access request has been approved',
          body, attachments=attachments)


def notify_user_rejected(name, email, notes):
    _send(
        email,
        '[PRECISE DuckDB] Your access request was not approved',
        f'Hi {name},\n\n'
        f'Unfortunately your request for access to the PRECISE DuckDB '
        f'was not approved at this time.\n\n'
        + (f'Reason: {notes}\n\n' if notes else '')
        + f'You may submit a new request if your circumstances change.\n\n'
          f'PALS Lab Team'
    )


# ── Shared CSS ────────────────────────────────────────────────────────────────

BASE_STYLE = '''
<style>
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
       background:#f0f4f8; min-height:100vh; padding:32px 16px; }
.page { max-width:580px; margin:0 auto; display:flex; flex-direction:column; gap:20px; }
.page.wide { max-width:900px; }
.card { background:white; border-radius:12px;
        box-shadow:0 4px 24px rgba(0,0,0,.08); padding:36px 40px; }
.logo  { font-size:22px; font-weight:700; color:#1a535c; margin-bottom:4px; }
.sub   { color:#6b7280; font-size:13px; margin-bottom:22px; }
.intro { background:#f0fdf4; border-left:3px solid #10b981;
         padding:12px 14px; border-radius:0 8px 8px 0;
         font-size:13px; color:#374151; margin-bottom:20px; line-height:1.6; }
.warn  { background:#fffbeb; border-left:3px solid #f59e0b;
         padding:12px 14px; border-radius:0 8px 8px 0;
         font-size:13px; color:#92400e; margin-bottom:20px; line-height:1.6; }
label  { display:block; font-size:13px; font-weight:600; color:#374151;
         margin:14px 0 5px; }
input,select,textarea {
  width:100%; padding:10px 12px; border:1px solid #d1d5db;
  border-radius:8px; font-size:14px; color:#111827; outline:none; }
input:focus,select:focus,textarea:focus {
  border-color:#10b981; box-shadow:0 0 0 3px rgba(16,185,129,.1); }
textarea { resize:vertical; min-height:70px; }
.check-group { display:flex; flex-wrap:wrap; gap:10px; margin-top:6px; }
.check-group label { margin:0; font-weight:400; display:flex; align-items:center;
                     gap:6px; cursor:pointer; }
.check-group input[type=checkbox] { width:auto; }
.btn { padding:11px 20px; border:none; border-radius:8px;
       font-size:14px; font-weight:600; cursor:pointer; transition:background .2s; }
.btn-primary   { background:#1a535c; color:white; width:100%; margin-top:20px; }
.btn-primary:hover   { background:#10b981; }
.btn-approve   { background:#10b981; color:white; }
.btn-approve:hover   { background:#059669; }
.btn-reject    { background:#ef4444; color:white; }
.btn-reject:hover    { background:#dc2626; }
.btn-sm { padding:6px 14px; font-size:13px; }
.btn:disabled { background:#9ca3af; cursor:not-allowed; }
.alert { padding:14px 16px; border-radius:8px; font-size:14px; margin-top:16px; }
.alert-ok   { background:#ecfdf5; border:1px solid #6ee7b7; color:#065f46; }
.alert-err  { background:#fef2f2; border:1px solid #fca5a5; color:#991b1b; }
.alert-info { background:#eff6ff; border:1px solid #93c5fd; color:#1e40af; }
.badge { display:inline-block; padding:2px 10px; border-radius:20px;
         font-size:12px; font-weight:600; }
.badge-pending  { background:#fef3c7; color:#92400e; }
.badge-approved { background:#d1fae5; color:#065f46; }
.badge-rejected { background:#fee2e2; color:#991b1b; }
.snippet { background:#0f172a; border-radius:10px; padding:16px;
           font-family:monospace; font-size:12.5px; color:#cdd6f4;
           line-height:1.7; white-space:pre-wrap; overflow-x:auto;
           margin-top:16px; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th { text-align:left; padding:10px 12px; background:#f8fafc;
     border-bottom:2px solid #e2e8f0; color:#374151; font-weight:600; }
td { padding:10px 12px; border-bottom:1px solid #f1f5f9; color:#374151; vertical-align:top; }
tr:hover td { background:#f8fafc; }
.back { text-align:center; font-size:13px; color:#6b7280; }
.back a { color:#1a535c; text-decoration:none; font-weight:600; }
.flash { padding:12px 16px; border-radius:8px; font-size:14px;
         margin-bottom:16px; }
.flash-ok  { background:#ecfdf5; color:#065f46; border:1px solid #6ee7b7; }
.flash-err { background:#fef2f2; color:#991b1b; border:1px solid #fca5a5; }
.modal-backdrop {
  display:none; position:fixed; inset:0; background:rgba(0,0,0,.5);
  z-index:1000; align-items:center; justify-content:center; }
.modal-backdrop.open { display:flex; }
.modal { background:white; border-radius:12px; padding:32px;
         max-width:440px; width:90%; box-shadow:0 25px 60px rgba(0,0,0,.3); }
.modal h3 { margin-bottom:14px; color:#1a535c; }
.modal-footer { display:flex; gap:10px; margin-top:20px; justify-content:flex-end; }
</style>
'''


# ══════════════════════════════════════════════════════════════════════════════
# USER ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
@app.route('/request')
def request_form():
    return render_template_string(BASE_STYLE + '''
<div class="page">
 <div class="card">
  <div class="logo">PRECISE DuckDB</div>
  <div class="sub">PRECISE Network — Access Request</div>
  <div class="intro">
    Fill in the form below to request access to the PRECISE Big Table dataset via
    <strong>DuckDB</strong>. Your request will be reviewed by the admin and you will
    receive an email once a decision has been made — the same process as for PALSlab Hub.
  </div>
  <div class="warn">
    Access is granted per country. You will only be able to query data for the
    countries approved in your request.
  </div>
  <form id="f">
    <label>Full Name</label>
    <input id="name" type="text" required placeholder="e.g. Jane Researcher"/>
    <label>Email Address</label>
    <input id="email" type="email" required placeholder="you@institution.org"/>
    <label>Institution</label>
    <input id="inst" type="text" required placeholder="e.g. CESHHAR / University of..."/>
    <label>PALSlab Hub Username</label>
    <input id="hub" type="text" required placeholder="Your JupyterHub login username"/>
    <label>Countries Needed</label>
    <div class="check-group">
      <label><input type="checkbox" name="country" value="Kenya"/> Kenya</label>
      <label><input type="checkbox" name="country" value="Mozambique"/> Mozambique</label>
      <label><input type="checkbox" name="country" value="Gambia"/> The Gambia</label>
    </div>
    <label>Purpose / Research Question</label>
    <textarea id="purpose" placeholder="Describe what you plan to analyse..."></textarea>
    <button class="btn btn-primary" type="submit" id="sub">Submit Request</button>
  </form>
  <div id="msg"></div>
 </div>
 <div class="back"><a href="/">← Back to PALS Lab Portal</a></div>
</div>
<script>
document.getElementById('f').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = document.getElementById('sub');
  btn.disabled = true; btn.textContent = 'Submitting…';
  const countries = [...document.querySelectorAll('input[name=country]:checked')].map(x=>x.value);
  if (!countries.length) {
    document.getElementById('msg').innerHTML =
      '<div class="alert alert-err">Please select at least one country.</div>';
    btn.disabled=false; btn.textContent='Submit Request'; return;
  }
  const r = await fetch('submit', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      name: document.getElementById('name').value.trim(),
      email: document.getElementById('email').value.trim(),
      institution: document.getElementById('inst').value.trim(),
      hub_user: document.getElementById('hub').value.trim(),
      purpose: document.getElementById('purpose').value.trim(),
      countries
    })
  });
  const d = await r.json();
  if (d.ok) {
    document.getElementById('f').style.display='none';
    document.getElementById('msg').innerHTML =
      '<div class="alert alert-ok"><strong>Request submitted!</strong><br>' +
      'You will receive an email when your request has been reviewed.<br><br>' +
      'Your request ID: <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px">'
      + d.request_id + '</code><br>' +
      '<small>Save this to check your status at <a href="status/'
      + d.request_id + '">/duckrequest/status/' + d.request_id + '</a></small></div>';
  } else {
    document.getElementById('msg').innerHTML =
      '<div class="alert alert-err">Error: ' + (d.error||'unknown') + '</div>';
    btn.disabled=false; btn.textContent='Submit Request';
  }
});
</script>
''')


@app.route('/submit', methods=['POST'])
def submit():
    d = request.get_json(force=True)
    name        = d.get('name','').strip()
    email       = d.get('email','').strip()
    institution = d.get('institution','').strip()
    hub_user    = d.get('hub_user','').strip()
    purpose     = d.get('purpose','').strip()
    countries   = [c for c in d.get('countries',[]) if c in COUNTRIES]

    if not all([name, email, institution, hub_user, countries]):
        return jsonify({'ok': False, 'error': 'Missing required fields or no valid countries'})

    req_id = access_db.create_request(name, email, institution, hub_user, purpose, countries)
    notify_admin(req_id, name, email, institution, hub_user, countries, purpose)

    return jsonify({'ok': True, 'request_id': req_id})


@app.route('/status/<req_id>')
def status(req_id):
    req = access_db.get_request_with_key(req_id)
    if not req:
        return render_template_string(BASE_STYLE + '''
<div class="page"><div class="card">
  <div class="logo">PRECISE DuckDB</div>
  <div class="alert alert-err">Request ID not found.</div>
  <div class="back" style="margin-top:16px"><a href="/duckrequest/request">← Make a request</a></div>
</div></div>'''), 404

    status_label = {
        'pending':  '<span class="badge badge-pending">Pending review</span>',
        'approved': '<span class="badge badge-approved">Approved</span>',
        'rejected': '<span class="badge badge-rejected">Rejected</span>',
    }.get(req['status'], req['status'])

    snippet = ''
    if req['status'] == 'approved':
        key = req.get('api_key','')
        countries = req.get('countries', [])
        c_str = ', '.join(countries)
        snippet = f'''
<div style="display:flex;gap:8px;margin-bottom:0">
  <button onclick="showTab('py')" id="tab-py"
    style="padding:6px 16px;border:none;border-radius:6px 6px 0 0;cursor:pointer;background:#1e293b;color:#f8fafc;font-weight:600">Python</button>
  <button onclick="showTab('r')" id="tab-r"
    style="padding:6px 16px;border:none;border-radius:6px 6px 0 0;cursor:pointer;background:#334155;color:#94a3b8">R</button>
</div>
<div id="snippet-py" class="snippet" style="margin-top:0;border-radius:0 6px 6px 6px">import sys
sys.path.insert(0, "/home/rutendo/PRECISE")
from precise_db import PreciseDB

db = PreciseDB(api_key="{key}")
df = db.query("SELECT * FROM daily_data")
db.close()

# df is a pandas DataFrame — use it for your analysis</div>
<div id="snippet-r" class="snippet" style="display:none;margin-top:0;border-radius:0 6px 6px 6px">library(httr)
library(jsonlite)

resp &lt;- POST(
  "http://localhost:5000/api/query",
  add_headers("X-API-Key" = "{key}"),
  content_type_json(),
  body = '{{"sql": "SELECT * FROM daily_data"}}'
)

result &lt;- fromJSON(content(resp, as = "text"))
df     &lt;- as.data.frame(result$rows)
colnames(df) &lt;- result$columns

# df is a data.frame — use it for your analysis</div>
<script>
function showTab(lang) {{
  document.getElementById('snippet-py').style.display = lang==='py' ? 'block' : 'none';
  document.getElementById('snippet-r').style.display  = lang==='r'  ? 'block' : 'none';
  document.getElementById('tab-py').style.background  = lang==='py' ? '#1e293b' : '#334155';
  document.getElementById('tab-py').style.color       = lang==='py' ? '#f8fafc' : '#94a3b8';
  document.getElementById('tab-r').style.background   = lang==='r'  ? '#1e293b' : '#334155';
  document.getElementById('tab-r').style.color        = lang==='r'  ? '#f8fafc' : '#94a3b8';
}}
</script>'''

    return render_template_string(BASE_STYLE + '''
<div class="page">
 <div class="card">
  <div class="logo">PRECISE DuckDB — Request Status</div>
  <div class="sub">Request ID: <code>{{ req_id }}</code></div>
  <table style="margin-bottom:16px">
    <tr><th>Name</th><td>{{ req.name }}</td></tr>
    <tr><th>Email</th><td>{{ req.email }}</td></tr>
    <tr><th>Countries requested</th><td>{{ req.countries_req | join(', ') }}</td></tr>
    <tr><th>Submitted</th><td>{{ req.created_at[:19] | replace("T"," ") }} UTC</td></tr>
    <tr><th>Status</th><td>{{ status_label | safe }}</td></tr>
    {% if req.reviewed_at %}
    <tr><th>Reviewed</th><td>{{ req.reviewed_at[:19] | replace("T"," ") }} UTC</td></tr>
    {% endif %}
    {% if req.notes %}
    <tr><th>Notes</th><td>{{ req.notes }}</td></tr>
    {% endif %}
  </table>
  {% if req.status == 'approved' %}
  <div class="intro">Your API key has been issued. Keep it private.
  {% if req.api_key %}
  <br><br><strong>API Key:</strong>
  <code style="display:block;margin-top:6px;background:#f3f4f6;padding:8px 10px;
               border-radius:6px;word-break:break-all;font-size:12px">{{ req.api_key }}</code>
  {% endif %}
  </div>
  {{ snippet | safe }}
  {% elif req.status == 'pending' %}
  <div class="warn">Your request is awaiting review. You will receive an email once a decision has been made.</div>
  {% elif req.status == 'rejected' %}
  <div class="alert alert-err">Your request was not approved. {{ req.notes or '' }}</div>
  {% endif %}
 </div>
 <div class="back"><a href="/duckrequest/request">← Submit a new request</a></div>
</div>
''', req=req, req_id=req_id, status_label=status_label, snippet=snippet)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(PREFIX + '/admin/login')
        return f(*args, **kwargs)
    return decorated


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        ok, must_change = access_db.check_admin(username, password)
        if ok:
            if must_change:
                session['pending_admin'] = username
                return redirect(PREFIX + '/admin/change-password?first=1')
            session['admin'] = True
            session['admin_user'] = username
            return redirect(PREFIX + '/admin')
        error = 'Incorrect username or password.'
    return render_template_string(BASE_STYLE + '''
<div class="page" style="max-width:380px;margin:80px auto">
 <div class="card">
  <div class="logo">PRECISE DuckDB</div>
  <div class="sub">Admin — Login</div>
  {% if error %}<div class="alert alert-err">{{ error }}</div>{% endif %}
  <form method="post">
    <label>Username</label>
    <input type="text" name="username" autofocus autocomplete="username" placeholder="username"/>
    <label>Password</label>
    <input type="password" name="password" autocomplete="current-password"/>
    <button class="btn btn-primary" type="submit">Login</button>
  </form>
  <p style="margin-top:1rem;font-size:13px;text-align:center">
    <a href="{{ prefix }}/admin/forgot-password" style="color:var(--teal)">Forgot password?</a>
  </p>
 </div>
</div>
''', error=error, prefix=PREFIX)


@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def admin_forgot_password():
    message = ''
    alert   = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = access_db.get_admin_email(username)
        message  = 'If that username is registered, a reset link has been sent to the associated email address.'
        alert    = 'alert-info'
        if email:
            token     = access_db.create_admin_reset_token(username)
            reset_url = f'https://placealert.org/duckrequest/admin/reset-password?token={token}'
            _send(
                email,
                '[PRECISE DuckDB] Password reset request',
                f'Hi {username},\n\n'
                f'A password reset was requested for your PRECISE DuckDB admin account.\n'
                f'Click the link below within 1 hour to set a new password:\n\n'
                f'    {reset_url}\n\n'
                f'If you did not request this, ignore this email.\n\n'
                f'— Place Alert Labs'
            )
    return render_template_string(BASE_STYLE + '''
<div class="page" style="max-width:400px;margin:80px auto">
 <div class="card">
  <div class="logo">PRECISE DuckDB</div>
  <div class="sub">Reset Password</div>
  {% if message %}<div class="alert {{ alert }}">{{ message }}</div>{% endif %}
  {% if not message %}
  <p style="font-size:14px;color:#666;margin-bottom:1.25rem">
    Enter your admin username and we will email you a reset link.
  </p>
  <form method="post">
    <label>Username</label>
    <input type="text" name="username" autofocus placeholder="username"/>
    <button class="btn btn-primary" type="submit">Send reset link</button>
  </form>
  {% endif %}
  <p style="margin-top:1rem;font-size:13px;text-align:center">
    <a href="{{ prefix }}/admin/login" style="color:var(--teal)">Back to login</a>
  </p>
 </div>
</div>
''', message=message, alert=alert, prefix=PREFIX)


@app.route('/admin/reset-password', methods=['GET', 'POST'])
def admin_reset_password():
    token   = request.args.get('token', '') or request.form.get('token', '')
    message = ''
    alert   = ''
    done    = False
    username = access_db.verify_admin_reset_token(token)
    valid   = username is not None

    if request.method == 'POST' and valid:
        new_pw  = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if not new_pw or len(new_pw) < 8:
            message, alert = 'Password must be at least 8 characters.', 'alert-err'
        elif new_pw != confirm:
            message, alert = 'Passwords do not match.', 'alert-err'
        else:
            access_db.consume_admin_reset_token(token, new_pw)
            message, alert, done = 'Password updated. You can now log in.', 'alert-ok', True
            valid = False

    if not valid and not done:
        message = message or 'This reset link is invalid or has expired.'
        alert   = alert   or 'alert-err'

    return render_template_string(BASE_STYLE + '''
<div class="page" style="max-width:400px;margin:80px auto">
 <div class="card">
  <div class="logo">PRECISE DuckDB</div>
  <div class="sub">Set New Password</div>
  {% if message %}<div class="alert {{ alert }}">{{ message }}</div>{% endif %}
  {% if valid %}
  <form method="post">
    <input type="hidden" name="token" value="{{ token }}"/>
    <label>New password</label>
    <input type="password" name="new_password" autofocus autocomplete="new-password"
           placeholder="At least 8 characters"/>
    <label>Confirm password</label>
    <input type="password" name="confirm_password" autocomplete="new-password"/>
    <button class="btn btn-primary" type="submit">Set password</button>
  </form>
  {% endif %}
  <p style="margin-top:1rem;font-size:13px;text-align:center">
    <a href="{{ prefix }}/admin/login" style="color:var(--teal)">Back to login</a>
  </p>
 </div>
</div>
''', token=token, valid=valid, message=message, alert=alert, prefix=PREFIX)


@app.route('/admin/change-password', methods=['GET', 'POST'])
def admin_change_password():
    """For first-time setup (pending_admin) or logged-in admins wanting to change password."""
    first      = request.args.get('first') == '1'
    pending    = session.get('pending_admin')
    logged_in  = session.get('admin')

    if not pending and not logged_in:
        return redirect(PREFIX + '/admin/login')

    username = pending or session.get('admin_user', '')
    message  = ''
    alert    = ''

    if request.method == 'POST':
        new_pw  = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        # For logged-in (non-first-time) require current password
        if logged_in and not pending:
            current = request.form.get('current_password', '')
            ok, _   = access_db.check_admin(username, current)
            if not ok:
                message, alert = 'Current password is incorrect.', 'alert-err'
        if not message:
            if not new_pw or len(new_pw) < 8:
                message, alert = 'New password must be at least 8 characters.', 'alert-err'
            elif new_pw != confirm:
                message, alert = 'Passwords do not match.', 'alert-err'
            else:
                access_db.set_admin_password(username, new_pw)
                session.pop('pending_admin', None)
                session['admin']      = True
                session['admin_user'] = username
                return redirect(PREFIX + '/admin')

    return render_template_string(BASE_STYLE + '''
<div class="page" style="max-width:400px;margin:80px auto">
 <div class="card">
  <div class="logo">PRECISE DuckDB</div>
  <div class="sub">{% if first %}Set Your Password{% else %}Change Password{% endif %}</div>
  {% if first %}
  <p style="font-size:14px;color:#666;margin-bottom:1.25rem">
    Welcome, <strong>{{ username }}</strong>. Please set a personal password before continuing.
  </p>
  {% endif %}
  {% if message %}<div class="alert {{ alert }}">{{ message }}</div>{% endif %}
  <form method="post">
    {% if not first %}
    <label>Current password</label>
    <input type="password" name="current_password" autocomplete="current-password"/>
    {% endif %}
    <label>New password</label>
    <input type="password" name="new_password" autofocus autocomplete="new-password"
           placeholder="At least 8 characters"/>
    <label>Confirm new password</label>
    <input type="password" name="confirm_password" autocomplete="new-password"/>
    <button class="btn btn-primary" type="submit">
      {% if first %}Set password &amp; continue{% else %}Update password{% endif %}
    </button>
  </form>
  {% if not first %}
  <p style="margin-top:1rem;font-size:13px;text-align:center">
    <a href="{{ prefix }}/admin" style="color:var(--teal)">Cancel</a>
  </p>
  {% endif %}
 </div>
</div>
''', first=first, username=username, message=message, alert=alert, prefix=PREFIX)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(PREFIX + '/admin/login')


@app.route('/admin')
@admin_required
def admin_dashboard():
    pending  = access_db.get_requests('pending')
    approved = access_db.get_requests('approved')
    rejected = access_db.get_requests('rejected')
    revoked  = access_db.get_requests('revoked')

    cat_pending  = access_db.get_catalogue_requests(status='pending')
    cat_approved = access_db.get_catalogue_requests(status='approved')
    cat_rejected = access_db.get_catalogue_requests(status='rejected')

    def rows(reqs, mode):
        # mode: 'pending' | 'approved' | 'other'
        out = ''
        for r in reqs:
            badge = {
                'pending':  '<span class="badge badge-pending">Pending</span>',
                'approved': '<span class="badge badge-approved">Approved</span>',
                'rejected': '<span class="badge badge-rejected">Rejected</span>',
                'revoked':  '<span class="badge" style="background:#f3e8ff;color:#6b21a8">Revoked</span>',
            }.get(r['status'], r['status'])
            cntrs   = ', '.join(r['countries_req'])
            date    = r['created_at'][:10]
            actions = ''
            if mode == 'pending':
                actions = (
                    f'<button class="btn btn-approve btn-sm" '
                    f'onclick="openApprove(\'{r["id"]}\',\'{r["name"]}\','
                    f'{r["countries_req"]})">Approve</button>'
                    f'<button class="btn btn-reject btn-sm" '
                    f'onclick="openReject(\'{r["id"]}\',\'{r["name"]}\')" '
                    f'style="margin-left:6px">Reject</button>'
                )
            elif mode == 'approved':
                actions = (
                    f'<button class="btn btn-sm" '
                    f'style="background:#7c3aed;color:white" '
                    f'onclick="openRevoke(\'{r["id"]}\',\'{r["name"]}\')">Revoke</button>'
                )
            out += f'''<tr>
              <td>{date}</td>
              <td>{r["name"]}<br><small style="color:#6b7280">{r["email"]}</small></td>
              <td><small>{r["institution"]}</small></td>
              <td>{cntrs}</td>
              <td>{badge}</td>
              <td>{actions}</td>
            </tr>'''
        return out or '<tr><td colspan="6" style="color:#9ca3af;text-align:center">None</td></tr>'

    def cat_rows(reqs, mode):
        out = ''
        labels = {'precise': 'PRECISE', 'he2at': 'HE²AT'}
        for r in reqs:
            badge = {
                'pending':  '<span class="badge badge-pending">Pending</span>',
                'approved': '<span class="badge badge-approved">Approved</span>',
                'rejected': '<span class="badge badge-rejected">Rejected</span>',
            }.get(r['status'], r['status'])
            cat_label = labels.get(r['catalogue'], r['catalogue'])
            date      = r['created_at'][:10]
            actions   = ''
            if mode == 'pending':
                actions = (
                    f'<button class="btn btn-approve btn-sm" '
                    f'onclick="openCatApprove(\'{r["id"]}\',\'{r["name"]}\',\'{cat_label}\')">Approve</button>'
                    f'<button class="btn btn-reject btn-sm" style="margin-left:6px" '
                    f'onclick="openCatReject(\'{r["id"]}\',\'{r["name"]}\')">Reject</button>'
                )
            out += f'''<tr>
              <td>{date}</td>
              <td>{r["name"]}<br><small style="color:#6b7280">{r["email"]}</small></td>
              <td><small>{r.get("institution","")}</small></td>
              <td>{cat_label}</td>
              <td>{badge}</td>
              <td>{actions}</td>
            </tr>'''
        return out or '<tr><td colspan="6" style="color:#9ca3af;text-align:center">None</td></tr>'

    return render_template_string(BASE_STYLE + '''
<div class="page wide" style="margin:0 auto;padding:32px 24px">
 <div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
    <div>
      <div class="logo">PRECISE DuckDB — Admin</div>
      <div class="sub" style="margin-bottom:0">Access request management</div>
    </div>
    <a href="{{ prefix }}/admin/change-password" style="color:var(--teal);font-size:13px;text-decoration:none;margin-right:1rem">Change password</a>
    <a href="{{ prefix }}/admin/logout" style="color:#ef4444;font-size:13px;text-decoration:none">Logout</a>
  </div>

  <h3 style="margin-bottom:12px;color:#1a535c">
    Pending <span class="badge badge-pending">{{ pending|length }}</span>
  </h3>
  <table><tr>
    <th>Date</th><th>Requester</th><th>Institution</th>
    <th>Countries</th><th>Status</th><th>Actions</th>
  </tr>{{ pending_rows | safe }}</table>

  <h3 style="margin:28px 0 12px;color:#1a535c">
    Approved <span class="badge badge-approved">{{ approved|length }}</span>
  </h3>
  <table><tr>
    <th>Date</th><th>Requester</th><th>Institution</th>
    <th>Countries</th><th>Status</th><th>Actions</th>
  </tr>{{ approved_rows | safe }}</table>

  <h3 style="margin:28px 0 12px;color:#1a535c">
    Revoked <span class="badge" style="background:#f3e8ff;color:#6b21a8">{{ revoked|length }}</span>
  </h3>
  <table><tr>
    <th>Date</th><th>Requester</th><th>Institution</th>
    <th>Countries</th><th>Status</th><th></th>
  </tr>{{ revoked_rows | safe }}</table>

  <h3 style="margin:28px 0 12px;color:#1a535c">
    Rejected <span class="badge badge-rejected">{{ rejected|length }}</span>
  </h3>
  <table><tr>
    <th>Date</th><th>Requester</th><th>Institution</th>
    <th>Countries</th><th>Status</th><th></th>
  </tr>{{ rejected_rows | safe }}</table>
 </div>
</div>

<!-- Catalogue Access Requests -->
<div class="page wide" style="margin:0 auto;padding:0 24px 32px">
 <div class="card">
  <div class="logo" style="margin-bottom:4px">Catalogue Access Requests</div>
  <div class="sub" style="margin-bottom:20px">PRECISE and HE²AT catalogue access (code-based)</div>

  <h3 style="margin-bottom:12px;color:#1a535c">
    Pending <span class="badge badge-pending">{{ cat_pending|length }}</span>
  </h3>
  <table><tr>
    <th>Date</th><th>Requester</th><th>Institution</th>
    <th>Catalogue</th><th>Status</th><th>Actions</th>
  </tr>{{ cat_pending_rows | safe }}</table>

  <h3 style="margin:28px 0 12px;color:#1a535c">
    Approved <span class="badge badge-approved">{{ cat_approved|length }}</span>
  </h3>
  <table><tr>
    <th>Date</th><th>Requester</th><th>Institution</th>
    <th>Catalogue</th><th>Status</th><th></th>
  </tr>{{ cat_approved_rows | safe }}</table>

  <h3 style="margin:28px 0 12px;color:#1a535c">
    Rejected <span class="badge badge-rejected">{{ cat_rejected|length }}</span>
  </h3>
  <table><tr>
    <th>Date</th><th>Requester</th><th>Institution</th>
    <th>Catalogue</th><th>Status</th><th></th>
  </tr>{{ cat_rejected_rows | safe }}</table>
 </div>
</div>

<!-- Approve modal -->
<div class="modal-backdrop" id="approveModal">
  <div class="modal">
    <h3>Approve Request</h3>
    <p id="approveFor" style="font-size:13px;color:#6b7280;margin-bottom:16px"></p>
    <label style="margin-top:0">Grant access to which countries?</label>
    <div class="check-group" style="margin-top:8px">
      <label><input type="checkbox" id="ck_Kenya" value="Kenya"/> Kenya</label>
      <label><input type="checkbox" id="ck_Mozambique" value="Mozambique"/> Mozambique</label>
      <label><input type="checkbox" id="ck_Gambia" value="Gambia"/> The Gambia</label>
    </div>
    <label style="margin-top:16px">Notes (optional)</label>
    <textarea id="approveNotes" style="min-height:50px" placeholder="e.g. Approved for 12 months"></textarea>
    <div class="modal-footer">
      <button class="btn" onclick="closeModals()" style="background:#e5e7eb;color:#374151">Cancel</button>
      <button class="btn btn-approve" onclick="submitApprove()">Approve &amp; Send Key</button>
    </div>
  </div>
</div>

<!-- Reject modal -->
<div class="modal-backdrop" id="rejectModal">
  <div class="modal">
    <h3>Reject Request</h3>
    <p id="rejectFor" style="font-size:13px;color:#6b7280;margin-bottom:16px"></p>
    <label>Reason (optional, emailed to requester)</label>
    <textarea id="rejectNotes" style="min-height:60px" placeholder="e.g. Insufficient justification provided"></textarea>
    <div class="modal-footer">
      <button class="btn" onclick="closeModals()" style="background:#e5e7eb;color:#374151">Cancel</button>
      <button class="btn btn-reject" onclick="submitReject()">Reject Request</button>
    </div>
  </div>
</div>

<!-- Revoke modal -->
<div class="modal-backdrop" id="revokeModal">
  <div class="modal">
    <h3 style="color:#7c3aed">Revoke Access</h3>
    <p id="revokeFor" style="font-size:13px;color:#6b7280;margin-bottom:16px"></p>
    <div style="background:#faf5ff;border-left:3px solid #7c3aed;padding:10px 14px;
                border-radius:0 8px 8px 0;font-size:13px;color:#4c1d95;margin-bottom:16px">
      This immediately invalidates the user&#39;s API key.
      They will be notified by email and must re-apply for access.
    </div>
    <label>Reason (optional — emailed to user)</label>
    <textarea id="revokeNotes" style="min-height:60px" placeholder="e.g. Project period ended"></textarea>
    <div class="modal-footer">
      <button class="btn" onclick="closeModals()" style="background:#e5e7eb;color:#374151">Cancel</button>
      <button class="btn" style="background:#7c3aed;color:white" onclick="submitRevoke()">Revoke Access</button>
    </div>
  </div>
</div>

<script>
const PREFIX = '/duckrequest';
let _currentId = null;

function openApprove(id, name, countries) {
  _currentId = id;
  document.getElementById('approveFor').textContent = 'Requester: ' + name;
  ['Kenya','Mozambique','Gambia'].forEach(c => {
    document.getElementById('ck_' + c).checked = countries.includes(c);
  });
  document.getElementById('approveNotes').value = '';
  document.getElementById('approveModal').classList.add('open');
}

function openReject(id, name) {
  _currentId = id;
  document.getElementById('rejectFor').textContent = 'Requester: ' + name;
  document.getElementById('rejectNotes').value = '';
  document.getElementById('rejectModal').classList.add('open');
}

function openRevoke(id, name) {
  _currentId = id;
  document.getElementById('revokeFor').textContent =
    'Revoking access for: ' + name;
  document.getElementById('revokeNotes').value = '';
  document.getElementById('revokeModal').classList.add('open');
}

function closeModals() {
  document.querySelectorAll('.modal-backdrop').forEach(m => m.classList.remove('open'));
}

async function submitApprove() {
  const countries = ['Kenya','Mozambique','Gambia']
    .filter(c => document.getElementById('ck_' + c).checked);
  if (!countries.length) { alert('Select at least one country.'); return; }
  const notes = document.getElementById('approveNotes').value.trim();
  const btn = document.querySelector('#approveModal .btn-approve');
  btn.disabled = true; btn.textContent = 'Sending…';
  try {
    const r = await fetch(PREFIX + '/admin/approve', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({request_id: _currentId, countries, notes})
    });
    const d = await r.json();
    if (d.ok) location.reload(); else { alert('Error: ' + d.error); btn.disabled=false; btn.textContent='Approve & Send Key'; }
  } catch(e) { alert('Network error'); btn.disabled=false; btn.textContent='Approve & Send Key'; }
}

async function submitReject() {
  const notes = document.getElementById('rejectNotes').value.trim();
  const r = await fetch(PREFIX + '/admin/reject', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({request_id: _currentId, notes})
  });
  const d = await r.json();
  if (d.ok) location.reload(); else alert('Error: ' + d.error);
}

async function submitRevoke() {
  const notes = document.getElementById('revokeNotes').value.trim();
  const r = await fetch(PREFIX + '/admin/revoke', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({request_id: _currentId, notes})
  });
  const d = await r.json();
  if (d.ok) location.reload(); else alert('Error: ' + d.error);
}

async function submitCatApprove() {
  const notes = document.getElementById('catApproveNotes').value.trim();
  const btn = document.querySelector('#catApproveModal .btn-approve');
  btn.disabled = true; btn.textContent = 'Sending…';
  try {
    const r = await fetch(PREFIX + '/admin/cat-approve', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({request_id: _currentId, notes})
    });
    const d = await r.json();
    if (d.ok) location.reload(); else { alert('Error: ' + d.error); btn.disabled=false; btn.textContent='Approve & Send Code'; }
  } catch(e) { alert('Network error'); btn.disabled=false; btn.textContent='Approve & Send Code'; }
}

async function submitCatReject() {
  const notes = document.getElementById('catRejectNotes').value.trim();
  const r = await fetch(PREFIX + '/admin/cat-reject', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({request_id: _currentId, notes})
  });
  const d = await r.json();
  if (d.ok) location.reload(); else alert('Error: ' + d.error);
}

function openCatApprove(id, name, catalogue) {
  _currentId = id;
  document.getElementById('catApproveFor').textContent = name + ' (' + catalogue + ')';
  document.getElementById('catApproveNotes').value = '';
  document.getElementById('catApproveModal').classList.add('open');
}

function openCatReject(id, name) {
  _currentId = id;
  document.getElementById('catRejectFor').textContent = name;
  document.getElementById('catRejectNotes').value = '';
  document.getElementById('catRejectModal').classList.add('open');
}
</script>

<!-- Catalogue approve modal -->
<div class="modal-backdrop" id="catApproveModal">
  <div class="modal">
    <h3>Approve Catalogue Request</h3>
    <p id="catApproveFor" style="font-size:13px;color:#6b7280;margin-bottom:16px"></p>
    <p style="font-size:13px;color:#374151;margin-bottom:12px">The access code will be emailed automatically.</p>
    <label style="margin-top:0">Notes (optional, included in approval email)</label>
    <textarea id="catApproveNotes" style="min-height:50px" placeholder="e.g. Approved for 12 months"></textarea>
    <div class="modal-footer">
      <button class="btn" onclick="closeModals()" style="background:#e5e7eb;color:#374151">Cancel</button>
      <button class="btn btn-approve" onclick="submitCatApprove()">Approve &amp; Send Code</button>
    </div>
  </div>
</div>

<!-- Catalogue reject modal -->
<div class="modal-backdrop" id="catRejectModal">
  <div class="modal">
    <h3>Reject Catalogue Request</h3>
    <p id="catRejectFor" style="font-size:13px;color:#6b7280;margin-bottom:16px"></p>
    <label>Reason (optional, emailed to requester)</label>
    <textarea id="catRejectNotes" style="min-height:60px" placeholder="e.g. Insufficient justification"></textarea>
    <div class="modal-footer">
      <button class="btn" onclick="closeModals()" style="background:#e5e7eb;color:#374151">Cancel</button>
      <button class="btn btn-reject" onclick="submitCatReject()">Reject Request</button>
    </div>
  </div>
</div>
''',
    pending=pending, approved=approved, rejected=rejected, revoked=revoked,
    pending_rows=rows(pending, 'pending'),
    approved_rows=rows(approved, 'approved'),
    rejected_rows=rows(rejected, 'other'),
    revoked_rows=rows(revoked, 'other'),
    cat_pending=cat_pending, cat_approved=cat_approved, cat_rejected=cat_rejected,
    cat_pending_rows=cat_rows(cat_pending, 'pending'),
    cat_approved_rows=cat_rows(cat_approved, 'other'),
    cat_rejected_rows=cat_rows(cat_rejected, 'other'),
    prefix=PREFIX,
    )


@app.route('/admin/approve', methods=['POST'])
@admin_required
def admin_approve():
    d = request.get_json(force=True)
    req_id   = d.get('request_id','')
    countries = [c for c in d.get('countries',[]) if c in COUNTRIES]
    notes    = d.get('notes','')

    if not req_id or not countries:
        return jsonify({'ok': False, 'error': 'Missing request_id or countries'})

    key, req = access_db.approve_request(req_id, countries, notes)
    if not key:
        return jsonify({'ok': False, 'error': 'Request not found'})

    notify_user_approved(req['name'], req['email'], key, countries)
    return jsonify({'ok': True})


@app.route('/admin/reject', methods=['POST'])
@admin_required
def admin_reject():
    d = request.get_json(force=True)
    req_id = d.get('request_id','')
    notes  = d.get('notes','')
    if not req_id:
        return jsonify({'ok': False, 'error': 'Missing request_id'})
    req = access_db.get_request(req_id)
    if not req:
        return jsonify({'ok': False, 'error': 'Request not found'})
    access_db.reject_request(req_id, notes)
    notify_user_rejected(req['name'], req['email'], notes)
    return jsonify({'ok': True})


@app.route('/admin/revoke', methods=['POST'])
@admin_required
def admin_revoke():
    d = request.get_json(force=True)
    req_id = d.get('request_id','')
    notes  = d.get('notes','')
    if not req_id:
        return jsonify({'ok': False, 'error': 'Missing request_id'})
    req = access_db.get_request(req_id)
    if not req:
        return jsonify({'ok': False, 'error': 'Request not found'})
    access_db.revoke_access(req_id)
    _send(
        req['email'],
        '[PRECISE DuckDB] Your access has been revoked',
        f'Hi {req["name"]},\n\n'
        f'Your access to the PRECISE DuckDB has been revoked.\n\n'
        + (f'Reason: {notes}\n\n' if notes else '')
        + f'Your API key is no longer valid. Any further queries will be rejected.\n\n'
          f'You may submit a new access request at:\n'
          f'https://placealert.org/duckrequest/request\n\n'
          f'PALS Lab Team'
    )
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════════════════
# CATALOGUE ACCESS REQUESTS (PRECISE & HE2AT)
# ══════════════════════════════════════════════════════════════════════════════

CATALOGUE_LABELS = {'precise': 'PRECISE Catalogue', 'he2at': 'HE²AT Catalogue'}


def notify_catalogue_admin(req_id, catalogue, name, email, institution, reason):
    label = CATALOGUE_LABELS.get(catalogue, catalogue)
    body  = (
        f'A new {label} access request requires your approval.\n\n'
        f'Name:        {name}\n'
        f'Email:       {email}\n'
        f'Institution: {institution}\n\n'
        f'Reason:\n{reason}\n\n'
        f'Review at: https://placealert.org/duckrequest/admin\n'
        f'Request ID: {req_id}'
    )
    for addr in ADMIN_EMAILS:
        _send(addr, f'[{label}] New access request from {name}', body)


def notify_catalogue_approved(catalogue, name, email, notes):
    label = CATALOGUE_LABELS.get(catalogue, catalogue)
    code  = CATALOGUE_CODE if catalogue == 'precise' else HE2AT_CODE
    url   = ('https://placealert.org/catalogue/' if catalogue == 'precise'
             else 'https://placealert.org/heat-catalogue/')
    body  = (
        f'Hi {name},\n\n'
        f'Your request to access the {label} has been approved.\n\n'
        + (f'Notes from reviewer: {notes}\n\n' if notes else '')
        + f'Access code: {code}\n\n'
        f'Visit the catalogue and enter this code to log in:\n{url}\n\n'
        f'Keep this code private — do not share it publicly.\n\n'
        f'PALS Lab Team'
    )
    _send(email, f'[{label}] Your access request has been approved', body)


def notify_catalogue_rejected(catalogue, name, email, notes):
    label = CATALOGUE_LABELS.get(catalogue, catalogue)
    body  = (
        f'Hi {name},\n\n'
        f'Unfortunately your request to access the {label} '
        f'was not approved at this time.\n\n'
        + (f'Reason: {notes}\n\n' if notes else '')
        + f'You may reapply if your circumstances change.\n\n'
          f'PALS Lab Team'
    )
    _send(email, f'[{label}] Your access request was not approved', body)


@app.route('/cat-submit', methods=['POST', 'OPTIONS'])
def cat_submit():
    """Store a catalogue access request and notify admins."""
    if request.method == 'OPTIONS':
        resp = app.make_default_options_response()
        resp.headers['Access-Control-Allow-Origin']  = '*'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp
    d           = request.get_json(force=True) or {}
    catalogue   = d.get('catalogue', '').strip()
    name        = d.get('name', '').strip()
    email       = d.get('email', '').strip()
    institution = d.get('institution', '').strip()
    reason      = d.get('reason', '').strip()

    if catalogue not in ('precise', 'he2at') or not all([name, email]):
        return jsonify({'ok': False, 'error': 'Missing required fields'}), 400

    req_id = access_db.create_catalogue_request(catalogue, name, email, institution, reason)
    notify_catalogue_admin(req_id, catalogue, name, email, institution, reason)
    resp = jsonify({'ok': True, 'request_id': req_id})
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/admin/cat-approve', methods=['POST'])
@admin_required
def admin_cat_approve():
    d      = request.get_json(force=True) or {}
    req_id = d.get('request_id', '')
    notes  = d.get('notes', '')
    req    = access_db.approve_catalogue_request(req_id, notes)
    if not req:
        return jsonify({'ok': False, 'error': 'Request not found'})
    notify_catalogue_approved(req['catalogue'], req['name'], req['email'], notes)
    return jsonify({'ok': True})


@app.route('/admin/cat-reject', methods=['POST'])
@admin_required
def admin_cat_reject():
    d      = request.get_json(force=True) or {}
    req_id = d.get('request_id', '')
    notes  = d.get('notes', '')
    req    = access_db.reject_catalogue_request(req_id, notes)
    if not req:
        return jsonify({'ok': False, 'error': 'Request not found'})
    notify_catalogue_rejected(req['catalogue'], req['name'], req['email'], notes)
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=35488, debug=False)
