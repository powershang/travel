from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse
import json, os

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

def get_db():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL:
        return
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_data (
                key TEXT PRIMARY KEY,
                value JSONB NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB init error: {e}")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        key = self._get_key()
        if not DATABASE_URL:
            self._json(None)
            return
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT value FROM app_data WHERE key=%s", (key,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            self._json(row[0] if row else None)
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def do_PUT(self):
        key = self._get_key()
        if not DATABASE_URL:
            self._json({'ok': False, 'reason': 'no database'})
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length)) if length else None
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO app_data (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
            """, (key, json.dumps(data)))
            conn.commit()
            cur.close()
            conn.close()
            self._json({'ok': True})
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _get_key(self):
        path = urlparse(self.path).path
        # /api/data/somekey -> somekey
        parts = path.strip('/').split('/')
        return parts[-1] if parts else ''

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
