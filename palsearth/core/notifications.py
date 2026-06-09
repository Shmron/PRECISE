import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_FROM = 'rutendosibanda18@gmail.com'
SMTP_PASS = os.environ.get('SMTP_APP_PASSWORD', '')


def _send_email(to_addr, subject, body):
    if not to_addr:
        return
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = SMTP_FROM
        msg['To'] = to_addr
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(SMTP_FROM, SMTP_PASS)
            s.send_message(msg)
    except Exception as e:
        print(f"[notifications] Failed to send email to {to_addr}: {e}")


def notify_complete(job, user_email):
    job_id = job.get('id', '')
    short_id = job_id[:8]
    datasets = job.get('datasets', '[]')
    output_fmt = job.get('output_format', 'csv')
    body = (
        f"Your PALSearth extraction job has completed successfully!\n\n"
        f"Job ID: {short_id}\n"
        f"Datasets: {datasets}\n"
        f"Output format: {output_fmt.upper()}\n\n"
        f"Log in to PALSearth to download your results:\n"
        f"https://placealert.org/palsearth\n\n"
        f"Navigate to 'My Jobs' to find and download your output file.\n\n"
        f"-- PALSearth Team"
    )
    _send_email(user_email, f'[PALSearth] Job {short_id} complete', body)


def notify_failed(job, user_email):
    job_id = job.get('id', '')
    short_id = job_id[:8]
    error_msg = job.get('error_msg', 'Unknown error')
    body = (
        f"Your PALSearth extraction job has failed.\n\n"
        f"Job ID: {short_id}\n"
        f"Error: {error_msg}\n\n"
        f"Please check your Earth Engine project settings and input file, "
        f"then try submitting again:\n"
        f"https://placealert.org/palsearth\n\n"
        f"If the problem persists, contact the admin.\n\n"
        f"-- PALSearth Team"
    )
    _send_email(user_email, f'[PALSearth] Job {short_id} failed', body)
