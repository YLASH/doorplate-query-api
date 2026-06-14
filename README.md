# 🏠 Doorplate Query API

Taiwan doorplate data crawler + FastAPI query service with SQLite cache and Discord alerts.

> **架構演進紀錄**：初始版本採用 Selenium，為追求生產環境效能，主動進行架構重構，成功轉向純 HTTP 逆向工程。

---

## 系統架構

```
POST /query { city, township, date_from, date_to }
  ├─ SQLite Cache HIT  → 直接回傳資料 ✅
  └─ Cache MISS        → 寫入 crawl_queue
                         Discord 通知管理員爬取
                         爬完 POST /notify → Discord 通知 user
                         user 再查一次 → HIT
```

```
ris.gov.tw
  └─ requests.Session
       ├─ CaptchaKey 取得 → 人工輸入 → query API
       ├─ Session Cookie 自動維持狀態
       └─ 下一筆 CaptchaKey + Token 從回應自動更新
            ├─ save CSV（備份）
            └─ save SQLite（API 查詢用）
```

---

## 技術亮點

**Reverse Engineering — Selenium → Pure requests**
- 逆向分析 ris.gov.tw HTTP session 流程
- 破解 Session Cookie 狀態管理、CaptchaKey 動態取得與自動更新機制
- 單次查詢效率提升數倍，無需 headless browser

**FastAPI + Pydantic**
- `/query`：Cache-first 查詢，支援縣市／日期篩選
- `/notify`：爬蟲完成後觸發 Discord 通知
- `/queue`：待爬清單管理（管理員用）
- `timeout=30` 熔斷防止 DB Locked
- 「台／臺」自動容錯

**Discord Webhook 監控**
- Rich Embeds 結構化通知
- 新需求通知（管理員）+ 完成通知（user）
- 異常即時推播

**分級 Logging**
- INFO / WARNING / ERROR 分級
- File + Stream 雙 handler
- 每日自動換檔（`api_YYYYMMDD.log`）

---

## 資料現況

| 縣市 | 爬取區數 | 總筆數 | 查詢區間 |
|------|---------|--------|---------|
| 臺北市 | 12／12 區 | 3,187 筆 | 民國 114/09/01 ～ 114/11/30 |

> 南港區於該區間內無門牌初編資料（查詢成功，政府資料源本身為零筆）。

---

## DB Schema

**資料表：`taiwan_handicraft`**

| 欄位 | 說明 |
|------|------|
| `city` | 縣市（臺北市） |
| `district` | 行政區（大安區…） |
| `village` | 村里 |
| `neighborhood` | 鄰 |
| `detail` | 詳細門牌地址 |
| `編釘日期` | 西元格式（2025-10-29） |
| `編釘類別` | 門牌初編（值為 1） |
| `原始門牌地址` | 爬取原始字串（備查） |

PRIMARY KEY：`(city, district, detail, 編釘日期)`，防止重複寫入。

**資料表：`crawl_queue`**

| 欄位 | 說明 |
|------|------|
| `city` | 縣市 |
| `township` | 行政區 |
| `date_from` | 查詢起始日（民國格式） |
| `date_to` | 查詢結束日（民國格式） |
| `requested_at` | user 請求時間 |
| `status` | `pending` / `done` |

---

## 快速開始

```bash
pip install fastapi uvicorn requests beautifulsoup4 pandas python-dotenv
uvicorn api_v2:app --host 0.0.0.0 --port 8000 --reload
```

設定 `.env`：
```
DISCORD_WEBHOOK_URL=your_webhook_url
```

---

## API Endpoints

| Method | Path | 說明 |
|--------|------|------|
| POST | `/query` | 查詢門牌資料（含日期篩選，預設 114/09/01～114/11/30） |
| POST | `/notify` | 爬蟲完成後呼叫，送 Discord 通知 user |
| GET | `/queue` | 查看待爬清單（?status=pending／done） |
| GET | `/health` | 健康檢查 |

---

## Phase 2 規劃

- 驗證碼 OCR 自動化（全自動爬蟲）
- 擴充全台縣市資料
- 空間數據分析（住商／產險應用）
- LLM 整合查詢介面
