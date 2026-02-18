from dotenv import load_dotenv
load_dotenv()

from flask import Flask, send_from_directory, request, jsonify, Response
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
        'fields': 'name,geometry,formatted_phone_number,rating,user_ratings_total,formatted_address,opening_hours,website,price_level,types,reviews,photos'
    }, timeout=5)
    return jsonify(r.json())

@app.route('/api/places/photo')
def places_photo():
    ref = request.args.get('ref', '')
    w = request.args.get('w', '400')
    if not ref or not GOOGLE_API_KEY:
        return Response('', status=404)
    r = requests.get('https://maps.googleapis.com/maps/api/place/photo', params={
        'photoreference': ref, 'maxwidth': w, 'key': GOOGLE_API_KEY
    }, timeout=10, stream=True)
    return Response(r.content, content_type=r.headers.get('Content-Type', 'image/jpeg'),
                    headers={'Cache-Control': 'public, max-age=86400'})

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

@app.route('/api/review', methods=['POST'])
def ai_review():
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return jsonify({'error': '未設定 ANTHROPIC_API_KEY'}), 500
    try:
        import anthropic
        data = request.get_json() or {}
        user_prompt = data.get('user_prompt', '').strip() or '請幫我全面審查行程並給建議'
        itinerary_json = data.get('itinerary_json', {})
        client = anthropic.Anthropic(api_key=api_key)
        system_prompt = ('你是一位專業的日本旅行顧問，精通九州（特別是佐賀、長崎、福岡）地區。請用繁體中文回覆。'
            '針對使用者提供的行程，請全面分析以下面向：\n'
            '1. **時間合理性**：每個景點停留時間、交通時間是否合理\n'
            '2. **路線效率**：是否有繞路或可優化的路線\n'
            '3. **景點/美食推薦**：根據路線推薦附近值得順道造訪的景點或美食\n'
            '4. **備案方案**：若遇雨天或景點臨時關閉的替代方案\n'
            '5. **帶小孩注意事項**：適合親子的建議\n\n'
            '請用 Markdown 格式回覆，使用標題和清單讓內容清晰易讀。\n\n'
            '【重要】審查建議寫完後，你必須在 <!-- SUGGESTED_JSON --> 標記之後，'
            '輸出修改後的完整行程 JSON。格式與輸入的 JSON 完全相同，'
            '只修改你建議調整的部分，其餘保持原樣。JSON 必須是合法的 JSON 格式，不要用 markdown code block 包裹。')
        import json
        user_message = f'{user_prompt}\n\n以下是我的行程 JSON：\n{json.dumps(itinerary_json, ensure_ascii=False, indent=2)}'
        msg = client.messages.create(
            model='claude-sonnet-4-5-20250929',
            max_tokens=8192,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_message}]
        )
        review_text = msg.content[0].text
        return jsonify({'review': review_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
