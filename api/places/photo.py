from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os, requests

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        ref = qs.get('ref', [''])[0]
        w = qs.get('w', ['400'])[0]
        api_key = os.environ.get('GOOGLE_PLACES_API_KEY', '')
        if not ref or not api_key:
            self.send_response(404)
            self.end_headers()
            return
        r = requests.get('https://maps.googleapis.com/maps/api/place/photo', params={
            'photoreference': ref, 'maxwidth': w, 'key': api_key
        }, timeout=10, stream=True)
        self.send_response(200)
        self.send_header('Content-Type', r.headers.get('Content-Type', 'image/jpeg'))
        self.send_header('Cache-Control', 'public, max-age=86400')
        self.end_headers()
        self.wfile.write(r.content)
