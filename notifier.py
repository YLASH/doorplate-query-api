import os
import json
import urllib.request
from datetime import datetime

# ──────────────────────────────────────────
# ⚙️ Discord Webhook 配置
# ──────────────────────────────────────────
# 從專案根目錄的 .env 檔案載入環境變數
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 若未安裝 python-dotenv，直接從系統環境變數讀取
 
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_alert(title: str, message: str):
    """
    【試題 3 - 工業級異常通知中心】
    當爬蟲換頁超時、API 查詢空值、或系統重大崩潰時，
    發送高階 Rich Embeds（帶紅條的內嵌卡片）至 Discord 頻道。
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 保底終端機日誌輸出
    print(f"📡 異常通知中心啟動：正在發送『{title}』警報至 Discord...")

    # 檢查是否維持預設值，若未配置則進行保底提示
    if not DISCORD_WEBHOOK_URL or "webhooks" not in DISCORD_WEBHOOK_URL:
        print("ℹ️ 您尚未配置真實的 Discord Webhook 網址，警報內容如下：")
        print(f"[{title}] {message}")
        return

    try:
        # 🎨 設計 Discord JSON 監控載荷
        payload = {
            "username": "門牌系統監控官",  # 顯示的機器人暱稱
            "avatar_url": "https://i.imgur.com/KdfG8A2.png",
            "embeds": [{
                "title": f"🚨 系統異常通報: {title}",
                "description": f"📅 **發生時間**: `{now_str}`\n💬 **詳細情況**: {message}",
                "color": 13341999,  
                "footer": {
                    "text": "自動自動化防禦系統 • 試題 3 成果呈現"
                }
            }]
        }
        
        # 將資料轉為 bytes
        data_payload = json.dumps(payload).encode("utf-8")
        
        # 建立請求對象，設定逾時防禦
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=data_payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        
        # 發射請求
        with urllib.request.urlopen(req, timeout=5.0) as response:
            if response.status in [200, 204]:
                print("✅ [Discord] 警報卡片傳送成功！")
            else:
                print(f"⚠️ [Discord] 傳送回應異常，狀態碼: {response.status}")
                
    except Exception as ds_err:
        # 終極大網防禦：即使網路斷線或 Discord 伺服器掛掉，也只印警告，絕對不阻斷爬蟲或 API 的運行！
        print(f"❌ [通知中心崩潰] 無法傳送警報至 Discord。原因: {str(ds_err)}")