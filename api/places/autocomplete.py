from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, os, requests

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        q = qs.get('input', [''])[0]
        api_key = os.environ.get('GOOGLE_PLACES_API_KEY', '')
        if not q or not api_key:
            self._json({'predictions': []})
            return
        r = requests.get('https://maps.googleapis.com/maps/api/place/autocomplete/json', params={
            'input': q, 'key': api_key, 'language': 'ja', 'components': 'country:jp',
            'location': '33.25,130.1', 'radius': 80000
        }, timeout=5)
        self._json(r.json())

    def _json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
