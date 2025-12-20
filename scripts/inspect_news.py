import json
from google.cloud import storage
KEY_PATH = r"C:\Users\felix\develop\flutter\projects\lahsing\lahsing-news-breaking\lahsing-480407-b9d3f83f4a49.json"
BUCKET_NAME = "lahsing-news-contents"
FILE_NAME = "news.json"

client = storage.Client.from_service_account_json(KEY_PATH)
bucket = client.bucket(BUCKET_NAME)
blob = bucket.blob(FILE_NAME)
text = blob.download_as_text()
data = json.loads(text)
print('Total items:', len(data))
for i, item in enumerate(data[:10]):
    print(i, item.get('title'))
