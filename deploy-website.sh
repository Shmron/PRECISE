#!/bin/bash
# Deploy placealert.org website + portal.placealert.org
# Run with: sudo bash deploy-website.sh
set -e

WEBSITE_SRC="/home/rutendo/PRECISE/website"
WEBSITE_DEST="/var/www/website"
NGINX_CONF="/etc/nginx/conf.d/placealert.conf"
NGINX_BACKUP="/etc/nginx/conf.d/placealert.conf.bak.$(date +%Y%m%d%H%M%S)"

echo "=== Step 1: Create /var/www/website ==="
mkdir -p "$WEBSITE_DEST"

echo "=== Step 2: Sync website files ==="
rsync -av --delete "$WEBSITE_SRC/" "$WEBSITE_DEST/"
chown -R www-data:www-data "$WEBSITE_DEST"
chmod -R 755 "$WEBSITE_DEST"

echo "=== Step 3: Backup current nginx config ==="
cp "$NGINX_CONF" "$NGINX_BACKUP"
echo "Backed up to $NGINX_BACKUP"

echo "=== Step 4: Write new nginx config ==="
cat > "$NGINX_CONF" << 'NGINXEOF'
map $http_upgrade $connection_upgrade_pa {
    default upgrade;
    ''      close;
}

# ── HTTP → HTTPS redirects ────────────────────────────────────────────────────

server {
    listen 80;
    listen [::]:80;
    server_name placealert.org www.placealert.org;
    return 301 https://$host$request_uri;
}

# ── Public website: placealert.org ───────────────────────────────────────────

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name placealert.org www.placealert.org;

    ssl_certificate     /etc/letsencrypt/live/placealert.org-0001/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/placealert.org-0001/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    root  /var/www/website;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location /images/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /assets/ {
        expires 7d;
        add_header Cache-Control "public";
    }
}

# ── Research portal: portal.placealert.org ───────────────────────────────────
# NOTE: HTTP only until certbot adds SSL (see end of script for instructions)

server {
    listen 80;
    listen [::]:80;
    server_name portal.placealert.org;

    root  /var/www/precise;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location /data/ {
        alias /var/www/precise/data/;
        autoindex off;
    }

    location /catalogue/ {
        alias /var/www/precise/catalogue/;
        try_files $uri $uri/ /catalogue/index.html;
    }

    location /heat-catalogue/ {
        alias /var/www/precise/heat-catalogue/;
        try_files $uri $uri/ /heat-catalogue/index.html;
    }

    location /catalogue-request/ {
        proxy_pass http://127.0.0.1:8110/catalogue-request;
        proxy_set_header Host $host;
        add_header Access-Control-Allow-Origin *;
    }

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

    location /dbrequest/ {
        proxy_pass http://127.0.0.1:35487/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout    300s;
        proxy_send_timeout    300s;
        proxy_connect_timeout 10s;
        proxy_buffering       off;
    }

    location /dashboard/ {
        proxy_pass http://127.0.0.1:8502/dashboard/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    location /palsearth/ {
        proxy_pass http://127.0.0.1:8503/palsearth/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
        proxy_buffering off;
    }

    location /harmonaize/ {
        proxy_pass http://127.0.0.1:8082/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    location /neoheat/ {
        proxy_pass http://127.0.0.1:5001/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_read_timeout 120;
    }

    location /gipex/ {
        proxy_pass http://127.0.0.1:8087/gipex/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
        proxy_buffering off;
    }

    location /apex/ {
        proxy_pass http://127.0.0.1:8086/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
        proxy_buffering off;
    }
}

# ── PALSlab JupyterHub: pals.placealert.org ──────────────────────────────────

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name pals.placealert.org;

    ssl_certificate     /etc/letsencrypt/live/pals.placealert.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pals.placealert.org/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 100M;
    proxy_read_timeout 600s;

    location / {
        proxy_pass http://127.0.0.1:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade_pa;
        proxy_buffering off;
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name pals.placealert.org;
    if ($host = pals.placealert.org) {
        return 301 https://$host$request_uri;
    }
    return 404;
}
NGINXEOF

echo "=== Step 5: Test nginx config ==="
nginx -t

echo "=== Step 6: Reload nginx ==="
systemctl reload nginx

echo ""
echo "=== DONE: website live at https://placealert.org ==="
echo ""
echo "=== NEXT: Get SSL cert for portal.placealert.org ==="
echo "First add DNS A record:  portal.placealert.org → $(curl -s ifconfig.me)"
echo "Then run: sudo certbot --nginx -d portal.placealert.org"
echo ""
echo "Until the cert exists, portal.placealert.org runs HTTP only."
echo "To enable HTTP-only portal temporarily, run: sudo bash deploy-website.sh --portal-http"
