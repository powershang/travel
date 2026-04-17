from http.server import BaseHTTPRequestHandler
import json, math

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(length)) if length else {}
        pts = data.get('points', [])
        if len(pts) < 2:
            self._json({'distances': []})
            return
        results = []
        for i in range(len(pts) - 1):
            d = haversine(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
            road = d * 1.3
            mins = max(1, round(road / 40 * 60))
            results.append({'km': round(road, 1), 'minutes': mins, 'straight_km': round(d, 1)})
        self._json({'distances': results})

    def _json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
