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
if __name__ == "__main__":
    # 在本地模擬一個 request 對象
    class MockRequest:
        def __init__(self):
            pass
            
    print("Running local test...")
    start_breaking_monitor(MockRequest())