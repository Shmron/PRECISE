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
                countries_req TEXT NOT NULL,
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
                countries        TEXT NOT NULL,
                created_at       TEXT NOT NULL,
                is_active        INTEGER DEFAULT 1,
                last_used        TEXT,
                FOREIGN KEY (request_id) REFERENCES requests(id)
            );
            CREATE TABLE IF NOT EXISTS catalogue_tokens (
                token      TEXT PRIMARY KEY,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS admins (
                username       TEXT PRIMARY KEY,
                password       TEXT NOT NULL,
                email          TEXT,
                must_change_pw INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS admin_reset_tokens (
                token      TEXT PRIMARY KEY,
                username   TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS catalogue_requests (
                id          TEXT PRIMARY KEY,
                catalogue   TEXT NOT NULL,
                name        TEXT NOT NULL,
                email       TEXT NOT NULL,
                institution TEXT,
                reason      TEXT,
                status      TEXT DEFAULT 'pending',
                created_at  TEXT NOT NULL,
                reviewed_at TEXT,
                notes       TEXT
            );
            CREATE TABLE IF NOT EXISTS shared_conversations (
                share_id   TEXT PRIMARY KEY,
                catalogue  TEXT NOT NULL,
                title      TEXT,
                messages   TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS catalogue_users (
                id           TEXT PRIMARY KEY,
                catalogue    TEXT NOT NULL,
                name         TEXT NOT NULL,
                email        TEXT NOT NULL,
                password     TEXT NOT NULL,
                token_budget INTEGER DEFAULT 1000000,
                tokens_used  INTEGER DEFAULT 0,
                is_active    INTEGER DEFAULT 1,
                created_at   TEXT NOT NULL,
                last_used    TEXT,
                notes        TEXT
            );
        ''')
        # Add user_id to catalogue_tokens if upgrading from an older schema
        try:
            c.execute("ALTER TABLE catalogue_tokens ADD COLUMN user_id TEXT DEFAULT NULL")
        except Exception:
            pass
        # Add new columns to existing admins table if upgrading
        for sql in [
            "ALTER TABLE admins ADD COLUMN email TEXT",
            "ALTER TABLE admins ADD COLUMN must_change_pw INTEGER DEFAULT 0",
        ]:
            try:
                c.execute(sql)
            except Exception:
                pass
    _seed_admins()


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


# ── Admin accounts ────────────────────────────────────────────────────────────
# Multi-user admin table in SQLite. Seed runs once; use set_admin_password()
# to update a user's password, or add_admin() to create a new one.

_PASS_FILE = '/home/rutendo/PRECISE/.duck_admin_pass'

_INITIAL_ADMINS = {
    'rutendo': {'password': None,                'email': 'rutendo.sibanda@ceshhar.org',    'must_change_pw': 0},
    'zororo':  {'password': 'm3nLtUIm9byOqJmx', 'email': 'zororo.chinwadzimba@ceshhar.org','must_change_pw': 1},
    'bongani': {'password': 'fS0WYr1ODV8n2Bwp', 'email': 'nyonih@staff.msu.ac.zw',        'must_change_pw': 1},
}


def _seed_admins():
    """Insert default admin rows only if they don't already exist; patch emails on existing rows."""
    legacy_pass = open(_PASS_FILE).read().strip() if os.path.exists(_PASS_FILE) else 'precise-admin'
    with _conn() as c:
        for username, info in _INITIAL_ADMINS.items():
            existing = c.execute(
                "SELECT 1 FROM admins WHERE username=?", (username,)
            ).fetchone()
            if not existing:
                pw = info['password'] if info['password'] is not None else legacy_pass
                c.execute(
                    "INSERT INTO admins (username, password, email, must_change_pw) VALUES (?,?,?,?)",
                    (username, pw, info['email'], info['must_change_pw'])
                )
            else:
                # Patch email in if the column was just added
                c.execute(
                    "UPDATE admins SET email=? WHERE username=? AND (email IS NULL OR email='')",
                    (info['email'], username)
                )


def check_admin(username, password):
    """Return (True, must_change_pw) if credentials match, else (False, False)."""
    with _conn() as c:
        row = c.execute(
            "SELECT password, must_change_pw FROM admins WHERE username=?", (username,)
        ).fetchone()
    if row and row['password'] == password:
        return True, bool(row['must_change_pw'])
    return False, False


def get_admin_email(username):
    with _conn() as c:
        row = c.execute("SELECT email FROM admins WHERE username=?", (username,)).fetchone()
    return row['email'] if row else None


def set_admin_password(username, new_pass):
    with _conn() as c:
        c.execute(
            "UPDATE admins SET password=?, must_change_pw=0 WHERE username=?",
            (new_pass, username)
        )


def add_admin(username, password, email=None):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO admins (username, password, email, must_change_pw) VALUES (?,?,?,1)",
            (username, password, email)
        )


# ── Admin password-reset tokens ───────────────────────────────────────────────

_TOKEN_TTL_ADMIN = 3600  # 1 hour


def create_admin_reset_token(username):
    """Store a timed reset token for username, return the token string."""
    token = secrets.token_urlsafe(32)
    expires = (datetime.datetime.utcnow() +
               datetime.timedelta(seconds=_TOKEN_TTL_ADMIN)).isoformat()
    with _conn() as c:
        # Remove any stale tokens for this user
        c.execute("DELETE FROM admin_reset_tokens WHERE username=?", (username,))
        c.execute(
            "INSERT INTO admin_reset_tokens (token, username, expires_at) VALUES (?,?,?)",
            (token, username, expires)
        )
    return token


def verify_admin_reset_token(token):
    """Return username if token is valid and not expired, else None."""
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        row = c.execute(
            "SELECT username, expires_at FROM admin_reset_tokens WHERE token=?", (token,)
        ).fetchone()
    if not row:
        return None
    if now > row['expires_at']:
        with _conn() as c:
            c.execute("DELETE FROM admin_reset_tokens WHERE token=?", (token,))
        return None
    return row['username']


def consume_admin_reset_token(token, new_password):
    """Set new password if token valid. Returns username on success, None on failure."""
    username = verify_admin_reset_token(token)
    if not username:
        return None
    set_admin_password(username, new_password)
    with _conn() as c:
        c.execute("DELETE FROM admin_reset_tokens WHERE token=?", (token,))
    return username


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


# ── Catalogue user accounts ───────────────────────────────────────────────────

def create_catalogue_user(catalogue, name, email, password, token_budget=1_000_000, notes=''):
    user_id = secrets.token_hex(8)
    now     = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            '''INSERT OR IGNORE INTO catalogue_users
               (id, catalogue, name, email, password, token_budget, created_at, notes)
               VALUES (?,?,?,?,?,?,?,?)''',
            (user_id, catalogue, name, email.lower().strip(), password, token_budget, now, notes)
        )
    return user_id


def authenticate_catalogue_user(catalogue, email, password):
    """Return user dict if credentials match, else None."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM catalogue_users WHERE catalogue=? AND email=? AND password=?",
            (catalogue, email.lower().strip(), password)
        ).fetchone()
    return dict(row) if row else None


def get_catalogue_user(user_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM catalogue_users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_catalogue_user_from_token(token):
    """Return the catalogue user linked to a valid (non-expired) session token."""
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        row = c.execute(
            """SELECT cu.* FROM catalogue_users cu
               JOIN catalogue_tokens ct ON ct.user_id = cu.id
               WHERE ct.token=? AND ct.expires_at > ?""",
            (token, now)
        ).fetchone()
    return dict(row) if row else None


def get_catalogue_users(catalogue=None):
    with _conn() as c:
        if catalogue:
            rows = c.execute(
                "SELECT * FROM catalogue_users WHERE catalogue=? ORDER BY created_at DESC",
                (catalogue,)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM catalogue_users ORDER BY catalogue, created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def update_catalogue_user_budget(user_id, new_budget):
    with _conn() as c:
        c.execute("UPDATE catalogue_users SET token_budget=? WHERE id=?", (new_budget, user_id))


def revoke_catalogue_user(user_id):
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute("UPDATE catalogue_users SET is_active=0 WHERE id=?", (user_id,))
        c.execute("DELETE FROM catalogue_tokens WHERE user_id=?", (user_id,))


def reinstate_catalogue_user(user_id):
    with _conn() as c:
        c.execute("UPDATE catalogue_users SET is_active=1 WHERE id=?", (user_id,))


def add_tokens_used(user_id, tokens):
    """Atomically add to a user's tokens_used counter. Returns new total."""
    with _conn() as c:
        c.execute(
            "UPDATE catalogue_users SET tokens_used=tokens_used+?, last_used=? WHERE id=?",
            (tokens, datetime.datetime.utcnow().isoformat(), user_id)
        )
        row = c.execute("SELECT tokens_used FROM catalogue_users WHERE id=?", (user_id,)).fetchone()
    return row['tokens_used'] if row else 0


def issue_user_catalogue_token(user_id):
    """Issue a session token linked to a specific user."""
    token   = 'cat_' + secrets.token_urlsafe(32)
    expires = (datetime.datetime.utcnow() +
               datetime.timedelta(seconds=_TOKEN_TTL)).isoformat()
    now     = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute("DELETE FROM catalogue_tokens WHERE expires_at < ?", (now,))
        c.execute(
            "INSERT INTO catalogue_tokens (token, expires_at, user_id) VALUES (?,?,?)",
            (token, expires, user_id)
        )
        c.execute("UPDATE catalogue_users SET last_used=? WHERE id=?", (now, user_id))
    return token


# ── Catalogue access requests ─────────────────────────────────────────────────

def create_catalogue_request(catalogue, name, email, institution, reason):
    req_id = secrets.token_hex(8)
    now    = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            '''INSERT INTO catalogue_requests
               (id, catalogue, name, email, institution, reason, created_at)
               VALUES (?,?,?,?,?,?,?)''',
            (req_id, catalogue, name, email, institution, reason, now)
        )
    return req_id


def get_catalogue_requests(catalogue=None, status=None):
    with _conn() as c:
        if catalogue and status:
            rows = c.execute(
                "SELECT * FROM catalogue_requests WHERE catalogue=? AND status=? ORDER BY created_at DESC",
                (catalogue, status)
            ).fetchall()
        elif catalogue:
            rows = c.execute(
                "SELECT * FROM catalogue_requests WHERE catalogue=? ORDER BY created_at DESC",
                (catalogue,)
            ).fetchall()
        elif status:
            rows = c.execute(
                "SELECT * FROM catalogue_requests WHERE status=? ORDER BY created_at DESC",
                (status,)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM catalogue_requests ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def approve_catalogue_request(req_id, notes=''):
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        r = c.execute("SELECT * FROM catalogue_requests WHERE id=?", (req_id,)).fetchone()
        if not r:
            return None
        c.execute(
            "UPDATE catalogue_requests SET status='approved', reviewed_at=?, notes=? WHERE id=?",
            (now, notes, req_id)
        )
    return dict(r)


def reject_catalogue_request(req_id, notes=''):
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        r = c.execute("SELECT * FROM catalogue_requests WHERE id=?", (req_id,)).fetchone()
        if not r:
            return None
        c.execute(
            "UPDATE catalogue_requests SET status='rejected', reviewed_at=?, notes=? WHERE id=?",
            (now, notes, req_id)
        )
    return dict(r)


# ── Shared conversations ──────────────────────────────────────────────────────

def create_shared_conversation(catalogue, title, messages):
    share_id = 'sh_' + secrets.token_urlsafe(10)
    now      = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO shared_conversations (share_id, catalogue, title, messages, created_at) VALUES (?,?,?,?,?)",
            (share_id, catalogue, title, json.dumps(messages), now)
        )
    return share_id


def get_shared_conversation(share_id):
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM shared_conversations WHERE share_id=?", (share_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d['messages'] = json.loads(d['messages'])
    return d


init_db()
