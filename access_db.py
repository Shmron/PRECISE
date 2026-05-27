"""
Access control database for PRECISE DuckDB requests.
SQLite-backed store for requests, approvals, and API keys.
"""
import sqlite3, secrets, json, datetime, os

DB_PATH = '/home/rutendo/PRECISE/access_control.db'

COUNTRIES = ['Kenya', 'Mozambique', 'Gambia']


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.executescript('''
            CREATE TABLE IF NOT EXISTS requests (
                id            TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL,
                institution   TEXT,
                hub_user      TEXT,
                purpose       TEXT,
                countries_req TEXT NOT NULL,   -- JSON list
                status        TEXT DEFAULT 'pending',
                created_at    TEXT NOT NULL,
                reviewed_at   TEXT,
                notes         TEXT
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                key              TEXT PRIMARY KEY,
                request_id       TEXT NOT NULL,
                name             TEXT NOT NULL,
                email            TEXT NOT NULL,
                countries        TEXT NOT NULL,  -- JSON list of approved countries
                created_at       TEXT NOT NULL,
                is_active        INTEGER DEFAULT 1,
                last_used        TEXT,
                FOREIGN KEY (request_id) REFERENCES requests(id)
            );
            CREATE TABLE IF NOT EXISTS catalogue_tokens (
                token      TEXT PRIMARY KEY,
                expires_at TEXT NOT NULL
            );
        ''')


# ── Requests ──────────────────────────────────────────────────────────────────

def create_request(name, email, institution, hub_user, purpose, countries):
    req_id = secrets.token_hex(8)
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            '''INSERT INTO requests
               (id, name, email, institution, hub_user, purpose, countries_req, created_at)
               VALUES (?,?,?,?,?,?,?,?)''',
            (req_id, name, email, institution, hub_user, purpose,
             json.dumps(countries), now)
        )
    return req_id


def get_requests(status=None):
    with _conn() as c:
        if status:
            rows = c.execute(
                "SELECT * FROM requests WHERE status=? ORDER BY created_at DESC",
                (status,)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM requests ORDER BY created_at DESC"
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['countries_req'] = json.loads(d['countries_req'])
        result.append(d)
    return result


def get_request(req_id):
    with _conn() as c:
        r = c.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d['countries_req'] = json.loads(d['countries_req'])
    return d


def get_request_with_key(req_id):
    d = get_request(req_id)
    if not d:
        return None
    if d['status'] == 'approved':
        with _conn() as c:
            k = c.execute(
                "SELECT key, countries FROM api_keys WHERE request_id=? AND is_active=1",
                (req_id,)
            ).fetchone()
        if k:
            d['api_key'] = k['key']
            d['countries'] = json.loads(k['countries'])
    return d


# ── Approvals / rejections ────────────────────────────────────────────────────

def approve_request(req_id, countries_allowed, notes=''):
    """Returns (api_key, request_dict) or (None, None) if not found."""
    req = get_request(req_id)
    if not req:
        return None, None
    # Guard against duplicate approvals (e.g. double-click)
    with _conn() as c:
        existing = c.execute(
            "SELECT key FROM api_keys WHERE request_id=? AND is_active=1",
            (req_id,)
        ).fetchone()
        if existing:
            req['status'] = 'approved'
            return existing['key'], req
    key = 'pals_' + secrets.token_urlsafe(30)
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "UPDATE requests SET status='approved', reviewed_at=?, notes=? WHERE id=?",
            (now, notes, req_id)
        )
        c.execute(
            '''INSERT INTO api_keys
               (key, request_id, name, email, countries, created_at)
               VALUES (?,?,?,?,?,?)''',
            (key, req_id, req['name'], req['email'],
             json.dumps(countries_allowed), now)
        )
    req['status'] = 'approved'
    return key, req


def reject_request(req_id, notes=''):
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "UPDATE requests SET status='rejected', reviewed_at=?, notes=? WHERE id=?",
            (now, notes, req_id)
        )


# ── API key validation (called by api.py) ────────────────────────────────────

def validate_key(api_key):
    """Returns {'name', 'email', 'countries': [...]} or None."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM api_keys WHERE key=? AND is_active=1",
            (api_key,)
        ).fetchone()
        if row:
            c.execute(
                "UPDATE api_keys SET last_used=? WHERE key=?",
                (datetime.datetime.utcnow().isoformat(), api_key)
            )
            return {
                'name':      row['name'],
                'email':     row['email'],
                'countries': json.loads(row['countries']),
            }
    return None


def revoke_access(req_id):
    """Deactivate all keys for a request and mark it revoked."""
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute("UPDATE api_keys  SET is_active=0           WHERE request_id=?", (req_id,))
        c.execute("UPDATE requests  SET status='revoked', reviewed_at=? WHERE id=?", (now, req_id))


def revoke_key(api_key):
    with _conn() as c:
        c.execute("UPDATE api_keys SET is_active=0 WHERE key=?", (api_key,))


# ── Admin password ────────────────────────────────────────────────────────────
# Stored as a plain secret in a dotfile. Run set_admin_password() once to change it.

_PASS_FILE = '/home/rutendo/PRECISE/.duck_admin_pass'

ADMIN_USERNAME = 'rutendo'


def get_admin_password():
    if os.path.exists(_PASS_FILE):
        return open(_PASS_FILE).read().strip()
    return 'precise-admin'   # default — change immediately


def set_admin_password(new_pass):
    with open(_PASS_FILE, 'w') as f:
        f.write(new_pass)
    os.chmod(_PASS_FILE, 0o600)


# ── Catalogue session tokens (SQLite-backed, survive restarts) ────────────────

_TOKEN_TTL = 8 * 3600  # seconds

def issue_catalogue_token() -> str:
    token = 'cat_' + secrets.token_urlsafe(32)
    expires = (datetime.datetime.utcnow() +
               datetime.timedelta(seconds=_TOKEN_TTL)).isoformat()
    with _conn() as c:
        c.execute("DELETE FROM catalogue_tokens WHERE expires_at < ?",
                  (datetime.datetime.utcnow().isoformat(),))
        c.execute("INSERT INTO catalogue_tokens (token, expires_at) VALUES (?, ?)",
                  (token, expires))
    return token


def validate_catalogue_token(token: str) -> bool:
    if not token:
        return False
    with _conn() as c:
        row = c.execute(
            "SELECT expires_at FROM catalogue_tokens WHERE token=?", (token,)
        ).fetchone()
    if not row:
        return False
    if datetime.datetime.utcnow().isoformat() > row['expires_at']:
        with _conn() as c:
            c.execute("DELETE FROM catalogue_tokens WHERE token=?", (token,))
        return False
    return True


init_db()
