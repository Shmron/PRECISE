import sqlite3
import uuid
import json
from datetime import datetime

JOBS_DB = '/home/rutendo/PRECISE/palsearth/palsearth_jobs.db'


def _get_conn():
    conn = sqlite3.connect(JOBS_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            datasets TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            geometry_type TEXT NOT NULL,
            input_filename TEXT NOT NULL,
            output_filename TEXT,
            progress INTEGER DEFAULT 0,
            error_msg TEXT,
            ee_project TEXT NOT NULL,
            stats_requested TEXT NOT NULL,
            output_format TEXT NOT NULL DEFAULT 'csv',
            notified INTEGER DEFAULT 0,
            downloaded INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()


def create_job(username, datasets, start_date, end_date, geometry_type,
               input_filename, ee_project, stats_requested, output_format='csv'):
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO jobs (
            id, username, status, created_at, updated_at,
            datasets, start_date, end_date, geometry_type,
            input_filename, output_filename, progress, error_msg,
            ee_project, stats_requested, output_format, notified, downloaded
        ) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, ?, ?, ?, 0, 0)
    ''', (
        job_id, username, now, now,
        json.dumps(datasets), start_date, end_date, geometry_type,
        input_filename, ee_project, json.dumps(stats_requested), output_format
    ))
    conn.commit()
    conn.close()
    return job_id


def get_job(job_id):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_user_jobs(username):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE username=? ORDER BY created_at DESC", (username,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_all_jobs():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


_ALLOWED_JOB_COLS = frozenset({
    'status', 'progress', 'error_msg', 'output_filename',
    'notified', 'downloaded', 'updated_at',
})

def update_job(job_id, **kwargs):
    if not kwargs:
        return
    kwargs['updated_at'] = datetime.utcnow().isoformat()
    bad = set(kwargs) - _ALLOWED_JOB_COLS
    if bad:
        raise ValueError(f"update_job: disallowed column(s): {bad}")
    set_clause = ', '.join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE jobs SET {set_clause} WHERE id=?", values)
    conn.commit()
    conn.close()


# Initialise DB on import
init_db()
