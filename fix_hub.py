path = '/etc/palslab-hub/jupyterhub_config.py'
content = open(path).read()

# 1. Fix all pals.harmonaize.uk links to pals.placealert.org
content = content.replace('https://pals.harmonaize.uk', 'https://pals.placealert.org')

# 2. Make _send_email accept a list or string for to_addr
old_send = '''def _send_email(to_addr, subject, body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From']    = SMTP_FROM
    msg['To']      = to_addr
    msg.set_content(body)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(SMTP_FROM, SMTP_PASS)
        s.send_message(msg)'''

new_send = '''def _send_email(to_addr, subject, body):
    recipients = to_addr if isinstance(to_addr, list) else [to_addr]
    for addr in recipients:
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From']    = SMTP_FROM
            msg['To']      = addr
            msg.set_content(body)
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                s.login(SMTP_FROM, SMTP_PASS)
                s.send_message(msg)
        except Exception:
            pass'''

content = content.replace(old_send, new_send)

# 3. Change ADMIN_EMAIL to include all three admins
content = content.replace(
    "ADMIN_EMAIL = 'rutendo.sibanda@ceshhar.org'",
    "ADMIN_EMAIL = ['rutendo.sibanda@ceshhar.org', 'nyonih@staff.msu.ac.zw', 'zororo.chinwadzimba@ceshhar.org']"
)

# 4. Add bongani and zororo as JupyterHub admins
content = content.replace(
    "c.Authenticator.admin_users = {'rutendo'}",
    "c.Authenticator.admin_users = {'rutendo', 'bongani', 'zororo.chinwadzimba'}"
)

open(path, 'w').write(content)
print("Done — verifying key lines:")
for line in content.splitlines():
    if any(k in line for k in ['ADMIN_EMAIL', 'admin_users', 'placealert', 'harmonaize']):
        print(' ', line.strip())
