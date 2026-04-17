from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, os, requests

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        pid = qs.get('place_id', [''])[0]
        api_key = os.environ.get('GOOGLE_PLACES_API_KEY', '')
        if not pid or not api_key:
            self._json({'result': {}})
            return
        r = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params={
            'place_id': pid, 'key': api_key, 'language': 'ja',
            'fields': 'name,geometry,formatted_phone_number,rating,user_ratings_total,formatted_address,opening_hours,website,price_level,types,reviews,photos'
        }, timeout=5)
        self._json(r.json())

    def _json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
