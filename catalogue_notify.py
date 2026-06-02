#!/usr/bin/env python3
"""Tiny HTTP service for catalogue access requests. Runs on port 8110."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, smtplib, urllib.parse
from email.message import EmailMessage

import os
SMTP_FROM   = 'rutendosibanda18@gmail.com'
SMTP_PASS   = os.environ.get('SMTP_APP_PASSWORD', '')
ADMIN_EMAIL = 'rutendo.sibanda@ceshhar.org'

def send_email(to, subject, body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From']    = SMTP_FROM
    msg['To']      = to
    msg.set_content(body)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(SMTP_FROM, SMTP_PASS)
        s.send_message(msg)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence access log

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != '/catalogue-request':
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        try:
            data = json.loads(body)
            name        = data.get('name', '').strip()
            email       = data.get('email', '').strip()
            institution = data.get('institution', '').strip()
            reason      = data.get('reason', '').strip()

            send_email(
                ADMIN_EMAIL,
                f'[PRECISE Catalogue] Access request from {name}',
                f'Name:        {name}\n'
                f'Email:       {email}\n'
                f'Institution: {institution}\n\n'
                f'Reason:\n{reason}\n\n'
                f'Reply to this person with the access code if approved.'
            )
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception as e:
            self.send_response(500)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': False, 'error': str(e)}).encode())

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8110), Handler)
    print('Catalogue notify service running on port 8110')
    server.serve_forever()
