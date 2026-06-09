block = """
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
"""
path = '/etc/nginx/conf.d/placealert.conf'
content = open(path).read()
if '/harmonaize/' not in content:
    content = content.replace('    location /neoheat/', block + '    location /neoheat/')
    open(path, 'w').write(content)
    print("Done - harmonaize block added")
else:
    print("Already present")
