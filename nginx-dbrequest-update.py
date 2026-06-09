#!/usr/bin/env python3
"""Run with: sudo python3 /home/rutendo/PRECISE/nginx-dbrequest-update.py"""

path = '/etc/nginx/sites-available/portal'
content = open(path).read()

if '/dbrequest/' in content:
    print("Already patched — /dbrequest/ block already present.")
else:
    new_block = """
    # Database Access Request — token provisioning service
    location /dbrequest/ {
        proxy_pass http://127.0.0.1:35487/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60;
    }

"""
    content = content.replace('    location /catalogue/', new_block + '    location /catalogue/')
    open(path, 'w').write(content)
    print("Done — /dbrequest/ block added.")

import subprocess
result = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
print(result.stdout + result.stderr)
if result.returncode == 0:
    subprocess.run(['systemctl', 'reload', 'nginx'])
    print("nginx reloaded successfully.")
else:
    print("nginx config test FAILED — not reloading.")
