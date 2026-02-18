from dotenv import load_dotenv
load_dotenv()

from flask import Flask, send_from_directory, request, jsonify
import os, math, requests, json

app = Flask(__name__, static_folder='static')

GOOGLE_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')

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

init_db()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/config')
def get_config():
    return jsonify({'googleMapsApiKey': GOOGLE_API_KEY})

# --- Google Places Proxy ---
@app.route('/api/places/autocomplete')
def places_autocomplete():
    q = request.args.get('input', '')
    if not q or not GOOGLE_API_KEY:
        return jsonify({'predictions': []})
    r = requests.get('https://maps.googleapis.com/maps/api/place/autocomplete/json', params={
        'input': q, 'key': GOOGLE_API_KEY, 'language': 'ja', 'components': 'country:jp',
        'location': '33.25,130.1', 'radius': 80000
    }, timeout=5)
    return jsonify(r.json())

@app.route('/api/places/details')
def places_details():
    pid = request.args.get('place_id', '')
    if not pid or not GOOGLE_API_KEY:
        return jsonify({'result': {}})
    r = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params={
        'place_id': pid, 'key': GOOGLE_API_KEY, 'language': 'ja',
        'fields': 'name,geometry,formatted_phone_number,rating,formatted_address'
    }, timeout=5)
    return jsonify(r.json())

# --- Distance (Haversine x 1.3) ---
@app.route('/api/distance', methods=['POST'])
def calc_distance():
    data = request.get_json() or {}
    pts = data.get('points', [])
    if len(pts) < 2:
        return jsonify({'distances': []})
    results = []
    for i in range(len(pts) - 1):
        d = haversine(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
        road = d * 1.3
        mins = max(1, round(road / 40 * 60))  # ~40km/h avg
        results.append({'km': round(road, 1), 'minutes': mins, 'straight_km': round(d, 1)})
    return jsonify({'distances': results})

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

@app.route('/api/data/<key>', methods=['GET'])
def get_data(key):
    if not DATABASE_URL:
        return jsonify(None)
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_data WHERE key=%s", (key,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify(row[0] if row else None)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data/<key>', methods=['PUT'])
def put_data(key):
    if not DATABASE_URL:
        return jsonify({'ok': False, 'reason': 'no database'})
    try:
        data = request.get_json()
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
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
