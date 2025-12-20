import json
import sys
from google.cloud import storage

# Configuration
KEY_PATH = r"C:\Users\felix\develop\flutter\projects\lahsing\lahsing-news-breaking\lahsing-480407-b9d3f83f4a49.json"
BUCKET_NAME = "lahsing-news-contents"
FILE_NAME = "news.json"

def main():
    client = storage.Client.from_service_account_json(KEY_PATH)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(FILE_NAME)

    if not blob.exists():
        print(f"{FILE_NAME} does not exist in bucket {BUCKET_NAME}.")
        return 1

    data_text = blob.download_as_text()
    try:
        data = json.loads(data_text)
    except Exception as e:
        print(f"Failed to parse {FILE_NAME}: {e}")
        return 1

    if not isinstance(data, list) or len(data) == 0:
        print("news.json is empty or not a list; nothing to remove.")
        return 0

    removed = None

    # Prefer removing the most recent item (index 0) if it looks like a breaking news
    first = data[0]
    title = first.get('title', '') if isinstance(first, dict) else ''
    if isinstance(title, str) and title.startswith('【突發】'):
        removed = data.pop(0)
    else:
        # fallback: attempt to find an item with '突發' in the title
        for i, item in enumerate(data):
            t = item.get('title', '') if isinstance(item, dict) else ''
            if isinstance(t, str) and '突發' in t:
                removed = data.pop(i)
                break

    if not removed:
        print('No breaking-news item found to remove.')
        return 0

    # upload modified list back to GCS
    blob.upload_from_string(json.dumps(data, ensure_ascii=False, indent=2), content_type='application/json')
    print(f"Removed breaking item: {removed.get('title')}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
