import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os

def get_9news_breaking_story():
    """抓取 9News 首頁並尋找突發新聞"""
    url = "https://www.9news.com.au/"
    headers = {'User-Agent': 'Mozilla/5.0'} # 模擬瀏覽器
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Try several possible selectors for breaking/top story
        selectors = [
            '.story__headline--is-breaking',
            '.story__headline',
            '.c-breaking-news',
            '.breaking',
            'a[data-testid="top-story"]'
        ]

        top_story = None
        for sel in selectors:
            top_story = soup.select_one(sel)
            if top_story:
                break

        if top_story:
            # safe-get anchor and href
            anchor = top_story.find('a') or top_story.select_one('a')
            link = None
            if anchor:
                link = anchor.get('href') or anchor.get('data-href')
            # normalize relative URLs
            if link:
                from urllib.parse import urljoin
                link = urljoin(url, link)

            # get title from anchor text or element text
            title = None
            if anchor:
                title = anchor.get_text(strip=True)
            if not title:
                title = top_story.get_text(strip=True)

            # fetch article content if link available
            full_content = ""
            article_soup = None
            try:
                if link:
                    article_response = requests.get(link, headers=headers, timeout=10)
                    article_soup = BeautifulSoup(article_response.text, 'html.parser')
            except Exception:
                article_soup = None

            # try common paragraph containers
            paragraphs = []
            if article_soup:
                for psel in ['.p-rich-text__content p', 'article p', '.article-body p', 'p']:
                    paragraphs = article_soup.select(psel)
                    if paragraphs:
                        break
            if paragraphs:
                full_content = "\n\n".join([p.get_text(strip=True) for p in paragraphs])

            # try to get image url from meta tags or img
            image_url = ""
            if article_soup:
                meta_img = article_soup.select_one('meta[property="og:image"]') or article_soup.select_one('meta[name="og:image"]')
                if meta_img and meta_img.get('content'):
                    image_url = meta_img.get('content')
                else:
                    img = article_soup.select_one('img')
                    if img and img.get('src'):
                        image_url = urljoin(url, img.get('src'))
            # fallback: try image inside top_story
            if not image_url:
                img2 = top_story.find('img')
                if img2 and img2.get('src'):
                    from urllib.parse import urljoin
                    image_url = urljoin(url, img2.get('src'))

            return {
                "title": title or "",
                "url": link or url,
                "content": full_content,
                "publishedAt": datetime.utcnow().isoformat() + "Z",
                "imageUrl": image_url or ""
            }
    except Exception as e:
        print(f"[ERROR] Scaping 9News failed: {e}")
    return None

def process_breaking_news():
    # 1. 檢查有無突發
    breaking_story = get_9news_breaking_story()
    if not breaking_story:
        return

    # 2. 檢查是否處理過 (防止重複發布)
    # 建議在 GCS 存一個 'last_breaking_url.txt'
    last_url = download_text_from_gcs("last_breaking_url.txt")
    if breaking_story['url'] == last_url:
        print("[INFO] No new breaking news.")
        return

    # 3. 呼叫您的 LLM 翻譯 (使用我們之前修好的 parse_json_safely)
    translated_item = translate_breaking_story(breaking_story) 
    # 注意：這裡翻譯出來應該是一個 Dict
    
    if translated_item:
        # 4. 下載現有的 news.json
        current_news_list = download_json_from_gcs("news.json")
        
        # 5. 插入到最前面 (index 0)
        current_news_list.insert(0, translated_item[0])
        
        # 6. (選做) 保持檔案大小，例如只保留最新的 50 條
        final_list = current_news_list[:50]
        
        # 7. 上傳回 GCS
        upload_json_to_gcs("news.json", final_list)
        upload_text_to_gcs("last_breaking_url.txt", breaking_story['url'])
        print(f"[SUCCESS] Breaking News posted: {translated_item[0]['title']}")



from google.cloud import storage

BUCKET_NAME = "lahsing-news-contents" # 請替換為您的 Bucket 名稱


class StorageBackend:
    """Wraps Google Cloud Storage with a local-filesystem fallback."""
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.use_local = False
        self.local_dir = os.path.join(os.path.dirname(__file__), "local_storage")
        try:
            self.client = storage.Client()
            self.bucket = self.client.bucket(bucket_name)
        except Exception as e:
            print(f"[WARN] GCS client init failed ({e}); using local storage at {self.local_dir}.")
            self.use_local = True
            os.makedirs(self.local_dir, exist_ok=True)

    def _local_path(self, file_name: str) -> str:
        return os.path.join(self.local_dir, file_name)

    def download_text(self, file_name: str) -> str:
        if self.use_local:
            path = self._local_path(file_name)
            if not os.path.exists(path):
                return ""
            with open(path, 'r', encoding='utf-8') as fh:
                return fh.read().strip()
        blob = self.bucket.blob(file_name)
        if not blob.exists():
            return ""
        return blob.download_as_text().strip()

    def upload_text(self, file_name: str, content: str):
        if self.use_local:
            path = self._local_path(file_name)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(content)
            print(f"[INFO] Uploaded {file_name} to local storage.")
            return
        blob = self.bucket.blob(file_name)
        blob.upload_from_string(content, content_type='text/plain')
        print(f"[INFO] Uploaded {file_name} to GCS.")

    def download_json(self, file_name: str) -> list:
        try:
            if self.use_local:
                path = self._local_path(file_name)
                if not os.path.exists(path):
                    return []
                with open(path, 'r', encoding='utf-8') as fh:
                    return json.load(fh)
            blob = self.bucket.blob(file_name)
            if not blob.exists():
                return []
            data = blob.download_as_text()
            return json.loads(data)
        except Exception:
            return []

    def upload_json(self, file_name: str, data: list):
        if self.use_local:
            path = self._local_path(file_name)
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            print(f"[INFO] Saved {file_name} to local storage.")
            return
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        blob = self.bucket.blob(file_name)
        blob.upload_from_string(json_data, content_type='application/json')
        print(f"[INFO] Successfully updated {file_name} on GCS.")


storage_backend = StorageBackend(BUCKET_NAME)

def download_text_from_gcs(file_name: str) -> str:
    """從 GCS 下載純文字檔案 (用於讀取最後處理的 URL)"""
    try:
        return storage_backend.download_text(file_name)
    except Exception as e:
        print(f"[ERROR] download_text_from_gcs failed: {e}")
        return ""

def upload_text_to_gcs(file_name: str, content: str):
    """將純文字上傳到 GCS (用於記錄最後處理的 URL)"""
    try:
        storage_backend.upload_text(file_name, content)
    except Exception as e:
        print(f"[ERROR] upload_text_to_gcs failed: {e}")

def download_json_from_gcs(file_name: str) -> list:
    """從 GCS 下載 news.json 並轉換為 Python List"""
    try:
        return storage_backend.download_json(file_name)
    except Exception as e:
        print(f"[ERROR] download_json_from_gcs failed: {e}")
        return []

def upload_json_to_gcs(file_name: str, data: list):
    """將 Python List 轉為 JSON 並上傳到 GCS"""
    try:
        storage_backend.upload_json(file_name, data)
    except Exception as e:
        print(f"[ERROR] upload_json_to_gcs failed: {e}")


import os
from openai import OpenAI

# 初始化 OpenAI 客戶端
# 建議在雲端環境變數中設定 OPENAI_API_KEY
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "您的_OPENAI_API_KEY"))

def translate_breaking_story(breaking_data: dict):
    """
    將抓取的 9News 數據發送給 OpenAI gpt-4o-mini，獲取翻譯後的 JSON 陣列。
    """
    
    # 這是我們精心調校的「Mary」新聞記者 Prompt
    system_prompt = "你是一位住在悉尼的資深香港新聞記者 Mary。你負責將英文突發新聞轉換為繁體中文（香港書面語）的 JSON 數據。"
    
    user_content = f"""
    **任務：** 生成一個符合規範的 JSON array [{{...}}]。

    **輸入數據：**
    - publishedAt: {breaking_data['publishedAt']}
    - title: {breaking_data['title']}
    - content: {breaking_data['content']}
    - url: {breaking_data['url']}
    - urlToImage: {breaking_data['imageUrl']}

    **輸出欄位要求：**
    1. date: 使用 "{breaking_data['publishedAt']}"。
    2. title: 以 **【突發】** 開頭，撰寫吸睛標題。
    3. summary: 簡短摘要。
    4. articleDetail: 完整翻譯內容並保持分段 (用 \\n 分隔)。內容中請用單引號 '。
    5. region: 選擇最貼切的澳洲城市。
    6. category: 選擇適合的新聞類別。
    7. imageUrl: 直接複製 "{breaking_data['imageUrl']}"，嚴禁 Markdown 格式。
    8. citations: 將 "{breaking_data['url']}" 放入單元素陣列 ["..."]。

    **【強制格式】**
    - 輸出必須是且僅是一個 JSON array。
    - 嚴禁使用 Markdown 代碼塊標記 (不要出現 ```json)。
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # 使用效能與速度平衡的 mini 模型
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3, # 降低隨機性，確保格式穩定
        )
        
        raw_text = response.choices[0].message.content.strip()
        
        # 使用我們之前寫好的 parse_json_safely 進行解析
        return parse_json_safely(raw_text)

    except Exception as e:
        print(f"[ERROR] OpenAI API call failed: {e}")
        return None


def parse_json_safely(raw_text: str):
    """Try to extract and parse a JSON array from possibly noisy LLM output.

    Returns the parsed Python object (usually a list) or None on failure.
    """
    try:
        # Quick attempt: pure JSON
        return json.loads(raw_text)
    except Exception:
        pass

    # Attempt to find the first JSON array in the text
    import re
    pattern = re.compile(r"\[.*\]", re.DOTALL)
    match = pattern.search(raw_text)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # Fallback: try to evaluate loosely formatted Python-like dict/list
    try:
        from ast import literal_eval
        return literal_eval(raw_text)
    except Exception:
        pass

    print("[WARN] parse_json_safely: failed to parse JSON from LLM output")
    return None