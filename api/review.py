from http.server import BaseHTTPRequestHandler
import json, os

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            self._json({'error': '未設定 ANTHROPIC_API_KEY'}, 500)
            return
        try:
            import anthropic
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length)) if length else {}
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
            user_message = f'{user_prompt}\n\n以下是我的行程 JSON：\n{json.dumps(itinerary_json, ensure_ascii=False, indent=2)}'
            msg = client.messages.create(
                model='claude-sonnet-4-5-20250929',
                max_tokens=8192,
                system=system_prompt,
                messages=[{'role': 'user', 'content': user_message}]
            )
            review_text = msg.content[0].text
            self._json({'review': review_text})
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
