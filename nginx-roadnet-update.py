#!/usr/bin/env python3
"""Run with: sudo python3 /home/rutendo/PRECISE/nginx-roadnet-update.py"""

path = '/etc/nginx/sites-available/portal'
content = open(path).read()

if '/roadnet/' in content:
    print("Already patched — /roadnet/ block already present.")
else:
    new_block = """
    # Road Network Density — static H3 web map
    location /roadnet/ {
        alias /var/www/precise/roadnet/;
        try_files $uri $uri/ /roadnet/index.html;
        gzip_static on;
        add_header Cache-Control "no-cache";
    }

"""
    content = content.replace('    location /catalogue/', new_block + '    location /catalogue/')
    open(path, 'w').write(content)
    print("Done — /roadnet/ block added.")

import subprocess
result = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
print(result.stdout + result.stderr)
if result.returncode == 0:
    subprocess.run(['systemctl', 'reload', 'nginx'])
    print("nginx reloaded successfully.")
else:
    print("nginx config test FAILED — not reloading.")
