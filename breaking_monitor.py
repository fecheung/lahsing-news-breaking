import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def get_9news_breaking_story():
    """抓取 9News 首頁並尋找突發新聞"""
    url = "https://www.9news.com.au/"
    headers = {'User-Agent': 'Mozilla/5.0'} # 模擬瀏覽器
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 9News 通常會給突發新聞加上特定的 CSS Class，如 'c-breaking-news'
        # 這裡我們尋找帶有 "Breaking" 字眼的頭條
        top_story = soup.select_one('.story__headline, .story__headline--is-breaking')
        
        if top_story:
            link = top_story.find('a')['href']
            title = top_story.get_text().strip()
            
            # 獲取內文（為了 articleDetail）
            article_response = requests.get(link, headers=headers)
            article_soup = BeautifulSoup(article_response.text, 'html.parser')
            # 抓取正文段落
            paragraphs = article_soup.select('.p-rich-text__content p')
            full_content = "\n\n".join([p.get_text() for p in paragraphs])
            
            return {
                "title": title,
                "url": link,
                "content": full_content,
                "publishedAt": datetime.utcnow().isoformat() + "Z"
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
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

def download_text_from_gcs(file_name: str) -> str:
    """從 GCS 下載純文字檔案 (用於讀取最後處理的 URL)"""
    try:
        blob = bucket.blob(file_name)
        if not blob.exists():
            return ""
        return blob.download_as_text().strip()
    except Exception as e:
        print(f"[ERROR] download_text_from_gcs failed: {e}")
        return ""

def upload_text_to_gcs(file_name: str, content: str):
    """將純文字上傳到 GCS (用於記錄最後處理的 URL)"""
    try:
        blob = bucket.blob(file_name)
        blob.upload_from_string(content, content_type='text/plain')
        print(f"[INFO] Uploaded {file_name} to GCS.")
    except Exception as e:
        print(f"[ERROR] upload_text_to_gcs failed: {e}")

def download_json_from_gcs(file_name: str) -> list:
    """從 GCS 下載 news.json 並轉換為 Python List"""
    try:
        blob = bucket.blob(file_name)
        if not blob.exists():
            return []
        data = blob.download_as_text()
        return json.loads(data)
    except Exception as e:
        print(f"[ERROR] download_json_from_gcs failed: {e}")
        return []

def upload_json_to_gcs(file_name: str, data: list):
    """將 Python List 轉為 JSON 並上傳到 GCS"""
    try:
        blob = bucket.blob(file_name)
        # 確保以 UTF-8 編碼上傳，避免中文亂碼
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        blob.upload_from_string(json_data, content_type='application/json')
        print(f"[INFO] Successfully updated {file_name} on GCS.")
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