#!/usr/bin/env python3
"""Run with: sudo python3 /home/rutendo/PRECISE/nginx-dashboard-rename.py"""

path = '/etc/nginx/sites-available/portal'
content = open(path).read()

if '/dashboard/' in content and '/zororo/' not in content:
    print("Already updated — /dashboard/ block present.")
else:
    content = content.replace(
        """    location /zororo/ {
        proxy_pass http://127.0.0.1:8502/zororo/;""",
        """    location /dashboard/ {
        proxy_pass http://127.0.0.1:8502/dashboard/;"""
    )
    open(path, 'w').write(content)
    print("Done — /zororo/ renamed to /dashboard/.")

import subprocess
result = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
print(result.stdout + result.stderr)
if result.returncode == 0:
    subprocess.run(['systemctl', 'reload', 'nginx'])
    print("nginx reloaded.")
else:
    print("nginx config test FAILED — not reloading.")
