import sqlite3
import bcrypt
import smtplib
import os
from email.mime.text import MIMEText
from datetime import datetime

HUB_DB = '/var/lib/palslab-hub/jupyterhub.sqlite'
SMTP_FROM = 'rutendosibanda18@gmail.com'
SMTP_PASS = os.environ.get('SMTP_APP_PASSWORD', '')
ADMIN_EMAIL = 'rutendosibanda18@gmail.com'


def get_user(username):
    conn = sqlite3.connect(HUB_DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT username, password, is_authorized, email FROM users_info WHERE username=?",
        (username,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def login(username, password):
    row = get_user(username)
    if not row:
        return False, "User not found"
    stored_hash = row[1]
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode()
    if not bcrypt.checkpw(password.encode(), stored_hash):
        return False, "Incorrect password"
    if not row[2]:
        return False, "Account pending approval. Admin will notify you."
    return True, "OK"


def register(username, password, email):
    row = get_user(username)
    if row:
        return False, "Username already exists"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    conn = sqlite3.connect(HUB_DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users_info (username, password, is_authorized, email) VALUES (?, ?, 0, ?)",
        (username, hashed, email)
    )
    conn.commit()
    conn.close()
    # Also add to JupyterHub users table
    try:
        conn2 = sqlite3.connect(HUB_DB)
        cur2 = conn2.cursor()
        cur2.execute(
            "INSERT OR IGNORE INTO users (name, admin, created, last_activity, cookie_id, state, encrypted_auth_state) "
            "VALUES (?, 0, ?, ?, '', '{}', NULL)",
            (username, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
        )
        conn2.commit()
        conn2.close()
    except Exception:
        pass
    # Email admin
    try:
        msg = MIMEText(
            f"New PALSearth registration:\nUsername: {username}\nEmail: {email}\n\n"
            f"Approve at: https://pals.placealert.org/hub/authorize"
        )
        msg['Subject'] = f'[PALSearth] New user: {username}'
        msg['From'] = SMTP_FROM
        msg['To'] = ADMIN_EMAIL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(SMTP_FROM, SMTP_PASS)
            s.send_message(msg)
    except Exception:
        pass
    return True, "Registration submitted. Admin will approve your account shortly."
