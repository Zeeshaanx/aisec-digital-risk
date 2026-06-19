#!/bin/bash
set -e

echo "[searxng] Waiting for Redis..."
until redis-cli ping 2>/dev/null | grep -q PONG; do
    sleep 1
done
echo "[searxng] Redis ready."

# Fix SearXNG settings to use localhost redis
sed -i 's|redis://redis:6379|redis://127.0.0.1:6379|g' /etc/searxng/settings.yml
sed -i 's|http://searxng:8080/|http://127.0.0.1:8080/|g' /etc/searxng/settings.yml

export SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml

# Try different ways SearXNG might be installed
if command -v searxng-run &>/dev/null; then
    exec searxng-run
elif [ -f /opt/searxng/searx/webapp.py ]; then
    cd /opt/searxng
    exec python searx/webapp.py
elif python3 -c "import searx" 2>/dev/null; then
    exec python3 -m searx.webapp
else
    echo "[searxng] SearXNG not found, starting placeholder on port 8080..."
    exec python3 -c "
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if '/search' in self.path:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'results': [], 'query': ''}).encode())
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'SearXNG placeholder')
    def log_message(self, *args): pass

HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
"
fi
