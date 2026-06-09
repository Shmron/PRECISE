import os
import sys
import traceback
from multiprocessing import Process

# Ensure the palsearth package root is on sys.path when running in subprocess
PALSEARTH_ROOT = '/home/rutendo/PRECISE/palsearth'


def _run_job(job_id):
    """Target function for subprocess: runs extraction for a given job_id."""
    if PALSEARTH_ROOT not in sys.path:
        sys.path.insert(0, PALSEARTH_ROOT)

    from core.jobs_db import get_job, update_job
    from core.extractor import run_extraction
    from core.notifications import notify_complete, notify_failed
    from core.auth import get_user

    job = get_job(job_id)
    if not job:
        return

    update_job(job_id, status='running', progress=0)

    def update_progress(pct, status=None, error=None):
        kwargs = {'progress': pct}
        if status:
            kwargs['status'] = status
        if error:
            kwargs['error_msg'] = error
        update_job(job_id, **kwargs)

    try:
        output_path = run_extraction(job, update_progress_fn=update_progress)
        output_filename = os.path.basename(output_path)
        update_job(job_id, status='complete', progress=100,
                   output_filename=output_filename)
        # Notify user
        user_row = get_user(job['username'])
        if user_row and user_row[3]:
            job_updated = get_job(job_id)
            notify_complete(job_updated, user_row[3])
            update_job(job_id, notified=1)
    except Exception as e:
        err_msg = traceback.format_exc()
        print(f"[worker] Job {job_id} failed: {err_msg}")
        update_job(job_id, status='failed', error_msg=str(e)[:2000])
        # Notify user of failure
        try:
            from core.auth import get_user
            user_row = get_user(job['username'])
            if user_row and user_row[3]:
                job_updated = get_job(job_id)
                notify_failed(job_updated, user_row[3])
                update_job(job_id, notified=1)
        except Exception:
            pass


def run_job_in_background(job_id):
    """Launch extraction job in a daemon subprocess."""
    p = Process(target=_run_job, args=(job_id,))
    p.daemon = True
    p.start()
    return p
