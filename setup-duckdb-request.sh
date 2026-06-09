#!/bin/bash
# Run with: sudo bash /home/rutendo/PRECISE/setup-duckdb-request.sh
# Sets up:
#   1. Systemd service for the DuckDB Access Request service (port 35488)
#   2. Nginx location blocks for /duckrequest/ and /precise-api/
#   3. Enables and starts the service

set -e

echo "=== Setting up PRECISE DuckDB Access Request service ==="

# ── 1. Systemd service ────────────────────────────────────────────────────────
cat > /etc/systemd/system/duckdb-request.service << 'EOF'
[Unit]
Description=PRECISE DuckDB Access Request Service
After=network.target

[Service]
User=rutendo
WorkingDirectory=/home/rutendo/PRECISE
ExecStart=/usr/bin/python3 /home/rutendo/PRECISE/duckdb_request.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable duckdb-request
systemctl restart duckdb-request
echo "✓ duckdb-request service started on port 35488"

# ── 2. Nginx — add /duckrequest/ and /precise-api/ blocks ────────────────────
NGINX_CONF=/etc/nginx/sites-available/portal

# Guard: only patch if not already done
if grep -q '/duckrequest/' "$NGINX_CONF"; then
    echo "✓ /duckrequest/ block already present — skipping"
else
    python3 - "$NGINX_CONF" << 'PYEOF'
import sys
path = sys.argv[1]
content = open(path).read()

new_blocks = """
    # PRECISE DuckDB Access Request — test access service
    location /duckrequest/ {
        proxy_pass http://127.0.0.1:35488/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }

    # PRECISE DuckDB REST API — exposed for external notebook access
    location /precise-api/ {
        proxy_pass http://127.0.0.1:5000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

"""
# Insert before the existing /dbrequest/ block
content = content.replace(
    '# Database Access Request',
    new_blocks + '    # Database Access Request'
)
open(path, 'w').write(content)
print("✓ Nginx blocks added")
PYEOF
fi

# Test and reload nginx
nginx -t && systemctl reload nginx && echo "✓ Nginx reloaded"

echo ""
echo "=== Done ==="
echo "  DuckDB request form:  https://placealert.org/duckrequest/request"
echo "  PRECISE DuckDB API:   https://placealert.org/precise-api/api/health"
echo "  Portal:               https://placealert.org/"
