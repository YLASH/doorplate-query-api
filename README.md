

## 🛠️ 環境準備

**Python 版本：** 3.9+  
**瀏覽器：** Google Chrome（需與 ChromeDriver 版本一致）

```bash
# 1. Clone 專案
git clone https://gitlab.com/YLASH/cathay-ds-project
cd cathay-ds-project

# 2. 安裝套件
pip install -r requirements.txt
```

> ⚠️ Windows 環境若 `greenlet` 編譯失敗，請先確認已安裝 Visual C++ Build Tools，或改用 `pip install greenlet --pre`。

---

## 🚀 執行說明

## ：自動化爬蟲

**目標：** 爬取[內政部戶政司門牌查詢網站](https://www.ris.gov.tw/app/portal/3053)，條件為臺北市各區、民國 114/09/01～114/11/30、編訂類別「門牌初編」。

**執行方式：**

1. 開啟 `task1/crawler_main.ipynb`
2. 依序執行所有 Cell
3. 程式將自動：
   - 啟動 Chrome 瀏覽器並操控表單
   - 爬取各行政區門牌資料
   - 清洗並輸出 `臺北市門牌大數據總表_已清洗.csv`
   - 寫入 `taiwan_address.db`（SQLite）
   - 將執行 Log 寫至 `logs/` 目錄

> 💡 **驗證碼說明：**  本次測驗已於開發期間完成人工驗證，爬蟲可正常執行。程式碼內已留有未來全自動化升級的規劃註解（方案 A：ddddocr 本地 AI 辨識；方案 B：第三方打碼平台 API），詳見 crawler_main.ipynb

**輸出欄位（CSV / DB）：**

| 欄位名稱 | 說明 |
|---|---|
| 縣市 | 爬取縣市（臺北市） |
| 行政區 | 各區名稱（大安區…） |
| 門牌地址 | 完整門牌地址 |
| 編訂類別 | 門牌初編 |
| 編釘日期 | 對應查詢區間內之日期 |
| _(其他欄位依網頁實際擷取)_ | |

**不選用 Selenium 之技術評估：**

目標網站採動態渲染（JavaScript 驅動），頁面包含 iframe 巢狀結構與地圖熱區點擊互動，純 `requests` + BeautifulSoup 無法取得動態載入資料。Selenium 可完整模擬瀏覽器行為，精準操控表單下拉選單與日期輸入框，為本題最適合的爬蟲工具。

---

### 2：FastAPI 門牌查詢服務

**執行方式：**
>⚠️ 請務必在專案根目錄下執行以下指令，否則 試題3.notifier 中文模組路徑在 Linux / macOS 環境下會找不到。

```bash
uvicorn task2.api:app --host 0.0.0.0 --port 8000 --reload
```

**API 互動文件：** http://localhost:8000/docs

**Request 範例（POST /query）：**

```json
{
  "city": "台北市",
  "township": "大安區"
}
```

**Response 範例：**

```json
{
  "city": "台北市",
  "township": "大安區",
  "total": 128,
  "records": [
    {
      "縣市": "臺北市",
      "鄉鎮市區": "大安區",
      "村里": "學府里",
      "鄰": "003鄰",
      "詳細門牌": "和平東路二段１２３號三樓",
      "編釘日期": "2025-11-28",
      "編釘類別": "門牌初編"
    }
  ]
}
```

> 查詢結果為空時，系統將自動觸發 `notifier.py` 發送 Discord 異常警報。

---

### 3：Log 收集與異常通報

#### 即時 Log 監控儀表板

1. 開啟 `task3/log_monitor.ipynb`
2. 執行全部 Cell
3. 儀表板將以 Regex 解析 `logs/` 目錄下所有 `.log` 檔案，並以顏色區分 INFO / WARNING / ERROR 層級，支援歷史紀錄查詢。

#### Discord 異常通報

通報觸發條件：

| 觸發來源 | 觸發條件 | 通報內容 |
|---|---|---|
| 試題 1 爬蟲 | 爬取過程發生異常（requests 失敗、網站改版等） | 異常類型、錯誤訊息、時間戳記 |
| 試題 2 API | 查詢結果回傳為空 | 查詢參數（縣市、行政區）、時間戳記 |

**設定 Discord Webhook：**

在 `task3/notifier.py` 中填入你的 Webhook URL：

```python
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/your_webhook_url"
```

---
### 執行結果示範
 
#### 爬蟲執行 Log

### 試題 4：系統架構圖

![系統架構圖](screenshots/系統架構圖.jpg)

---

## ⭐ 延伸計畫

### 方案：自動執行

在 `crawler_main.ipynb` 最後新增以下排程程式碼，即可讓爬蟲每日自動執行：

```python
from apscheduler.schedulers.blocking import BlockingScheduler

def scheduled_crawl():
    """排程任務：自動重跑完整爬蟲流程"""
    logger.info("⏰ [排程觸發] 定時爬蟲任務啟動...")
    # 此處呼叫主爬蟲函式
    run_full_crawl()

scheduler = BlockingScheduler(timezone="Asia/Taipei")

# 每日早上 08:00 執行
scheduler.add_job(scheduled_crawl, 'cron', hour=8, minute=0)

logger.info("🗓️ 排程器啟動，每日 08:00 自動爬取門牌資料")
scheduler.start()
```

安裝套件：

```bash
pip install apscheduler
```

> 若部署於 Linux 伺服器，亦可改用系統層 **crontab** 設定，達到更輕量的排程效果：
> ```
> # crontab -e
> 0 8 * * * cd /path/to/project && python -m jupyter nbconvert --to notebook --execute task1/crawler_main.ipynb
> ```

---

## 📋 需求套件

請參閱 `requirements.txt`，主要依賴如下：

```
selenium>=4.0
pandas>=1.3
beautifulsoup4>=4.9
fastapi>=0.100
uvicorn>=0.20
sqlalchemy>=2.0
requests>=2.28
apscheduler>=3.9
ipywidgets>=8.0
```

---

## ⚠️ 注意事項

- 執行前請確認 Chrome 與 ChromeDriver 版本一致，建議使用 `webdriver-manager` 自動管理版本
- Discord Webhook URL 請勿上傳至 Git，建議使用環境變數或 `.env` 檔案管理
- SQLite DB 檔案（`taiwan_address.db`）會在爬蟲第一次執行後自動建立，無需手動準備
- `logs/` 目錄亦由程式自動建立，無需手動新增
