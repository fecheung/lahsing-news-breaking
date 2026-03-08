import functions_framework
from google.cloud import storage
import logging

# 引入你之前寫好的邏輯
# 確保 breaking_monitor.py 與 main.py 在同一個資料夾
from breaking_monitor import process_breaking_news

# 設定標準日誌紀錄，這在 Google Cloud Console 的 Log Explorer 中可以看到
logging.basicConfig(level=logging.INFO)

@functions_framework.http
def start_breaking_monitor(request):
    """
    Cloud Function 進入點 (Entry Point)
    
    這個函數會處理 HTTP 請求（例如來自 Cloud Scheduler 的定時觸發）。
    """
    logging.info("Breaking News Monitor triggered.")

    try:
        # 執行核心邏輯：抓取、翻譯、更新 GCS
        # 注意：在雲端環境，不需要手動載入 JSON 金鑰，storage.Client() 會自動抓取權限
        process_breaking_news()
        
        logging.info("Process completed successfully.")
        return "Breaking News Monitor execution finished.", 200

    except Exception as e:
        # 捕捉所有錯誤並紀錄到 Cloud Logs
        error_msg = f"An error occurred during execution: {str(e)}"
        logging.error(error_msg)
        return f"Internal Server Error: {str(e)}", 500

# ---------------------------------------------------------
# 本地測試用 (當你在 VS Code 直接執行 python main.py 時)
# ---------------------------------------------------------

@functions_framework.http
def permalink_handler(request):
    """POST /permalink
    Accepts a JSON snapshot and uploads it to gs://lahsing-news-contents/permalinks/{id}.json
    Requires Authorization: Bearer <UPLOADER_SECRET> if UPLOADER_SECRET env var is set.
    """
    from flask import jsonify
    import os
    import json
    try:
        # Auth check (optional)
        expected = os.environ.get('UPLOADER_SECRET')
        if expected:
            auth = request.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                return (jsonify({'status': 'error', 'message': 'Missing Authorization header'}), 401)
            token = auth.split(' ', 1)[1].strip()
            if token != expected:
                return (jsonify({'status': 'error', 'message': 'Forbidden'}), 403)

        data = request.get_json(silent=True)
        if not data or 'id' not in data:
            return (jsonify({'status': 'error', 'message': 'Missing id in payload'}), 400)

        obj_id = str(data['id'])
        object_name = f"permalinks/{obj_id}.json"
        bucket_name = os.environ.get('GCS_BUCKET_NAME', 'lahsing-news-contents')

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        if blob.exists():
            public_url = f"https://storage.googleapis.com/{bucket_name}/{object_name}"
            return (jsonify({'status': 'ok', 'public_url': public_url, 'skipped': True}), 200)

        # Upload
        blob.upload_from_string(json.dumps(data, ensure_ascii=False), content_type='application/json')
        try:
            blob.make_public()
        except Exception:
            logging.warning('make_public failed; continuing')

        public_url = f"https://storage.googleapis.com/{bucket_name}/{object_name}"
        return (jsonify({'status': 'ok', 'public_url': public_url}), 200)

    except Exception as e:
        logging.exception('Permalink upload failed')
        return (jsonify({'status': 'error', 'message': str(e)}), 500)

if __name__ == "__main__":
    # 在本地模擬一個 request 對象
    class MockRequest:
        def __init__(self):
            pass
            
    print("Running local test...")
    start_breaking_monitor(MockRequest())