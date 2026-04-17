from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, os

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

def get_db():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        keys = qs.get('keys', [''])[0].split(',')
        keys = [k.strip() for k in keys if k.strip()]
        if not DATABASE_URL or not keys:
            self._json({})
            return
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT key, value FROM app_data WHERE key = ANY(%s)",
                (keys,)
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            result = {k: None for k in keys}
            for row in rows:
                result[row[0]] = row[1]
            self._json(result)
        except Exception as e:
            self._json({'_error': str(e)}, 500)

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
