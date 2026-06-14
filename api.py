from __future__ import annotations
"""
門牌資料查詢 API
執行方式：uvicorn api:app --host 0.0.0.0 --port 8000 --reload
API 文件：http://localhost:8000/docs
"""

import sys
import sqlite3
import logging
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

# ──────────────────────────────────────────
# 🛠️ 1. 關鍵路徑防禦（絕對路徑對齊）
# ──────────────────────────────────────────
# 準確取得 api.py 當前所在的資料夾絕對路徑，確保無論從哪裡啟動服務都能正確找到資料庫與模組
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 強制把專案根目錄塞進搜尋路徑，防範引入試logger/notify 失敗
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# 鎖定根目錄下的資料庫絕對路徑
DB_PATH = os.path.join(BASE_DIR, "taiwan_address.db")

# ──────────────────────────────────────────
# 💾 2. 集中化日誌設定
# ──────────────────────────────────────────
# 1. 鎖定根目錄底下的 logs 資料夾並自動建立
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 2. 動態生成當天日誌檔名
log_filename = os.path.join(LOG_DIR, f"api_{datetime.now().strftime('%Y%m%d')}.log")

# 3. 一鍵設定 Logging 基礎配置（整合 Formatter 與 Handlers，防範 Uvicorn 重載衝突）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)  # 讓終端機也能同步看到彩色輸出
    ],
    force=True
)
logger = logging.getLogger("api")

# ──────────────────────────────────────────
# FastAPI 初始化
# ──────────────────────────────────────────
app = FastAPI(
    title="門牌資料查詢 API",
    description="查詢內政部戶政司門牌初編資料",
    version="2.0.0"
)


# ──────────────────────────────────────────
# Request / Response 資料模型
# ──────────────────────────────────────────
class QueryRequest(BaseModel):
    city: str = Field(..., examples=["台北市"])
    township: str = Field(..., examples=["大安區"])
    date_from: Optional[str] = Field("114/09/01", ...)
    date_to:   Optional[str] = Field("114/11/30", ...)

class DoorPlateRecord(BaseModel):
    city: str = Field(..., serialization_alias="縣市")
    township: str = Field(..., serialization_alias="鄉鎮市區")
    village: str = Field(..., serialization_alias="村里")
    neighborhood: str = Field(..., serialization_alias="鄰")
    detail: str = Field(..., serialization_alias="詳細門牌")
    date: str = Field(..., serialization_alias="編釘日期")
    category: str = Field(..., serialization_alias="編釘類別")

class QueryResponse(BaseModel):
    city:     str
    township: str
    total:    int
    cached:   bool   # True = DB 直接回傳；False 不會出現（那條路走 202）
    records:  List[DoorPlateRecord]

class NotifyRequest(BaseModel):
    city:     str = Field(..., examples=["台中市"])
    township: str = Field(..., examples=["大里區"])
    count:    int = Field(..., description="寫入 DB 的筆數")

# ──────────────────────────────────────────
#  DB 工具函式
# ──────────────────────────────────────────
def _city_variants(city: str) -> list[str]:
    """相容台 / 臺 兩種寫法"""
    return list({city, city.replace("台", "臺"), city.replace("臺", "台")})
 
 
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn
 
 
def ensure_queue_table():
    """啟動時確保 crawl_queue 資料表存在"""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crawl_queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                city        TEXT NOT NULL,
                township    TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                status      TEXT DEFAULT 'pending',   -- pending / done
                UNIQUE(city, township)
            )
        """)
        conn.commit()

def roc_to_ad(roc_str: str) -> str:
    """114/09/01 → 2025-09-01"""
    nums = re.findall(r'\d+', roc_str)
    if len(nums) == 3:
        year  = int(nums[0]) + 1911
        month = int(nums[1])
        day   = int(nums[2])
        return f"{year}-{month:02d}-{day:02d}"
    return roc_str


def check_cache(
    city: str, township: str,
    date_from: str,date_to: str,
) -> list[dict]:
    """
    查 DB 有沒有符合 city + township + 日期區間 的資料。
    有就回傳 list[dict]，沒有回 []。
    """
    variants     = _city_variants(city)
    placeholders = ",".join("?" * len(variants))
    df = roc_to_ad(date_from)  # "2025-09-01"
    dt = roc_to_ad(date_to)    # "2025-11-30"
 
    try:
        conn = _get_conn()
        cur  = conn.cursor()
        cur.execute(
            f"""
            SELECT city, district, village, neighborhood,
                   detail, 編釘日期, 編釘類別
            FROM   taiwan_handicraft
            WHERE  city      IN ({placeholders})
              AND  district   = ?
              AND  編釘日期  >= ?
              AND  編釘日期  <= ?
            ORDER  BY 編釘日期 DESC
            """,
            [*variants, township, df, dt],
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        logger.info(
            "check_cache %s %s [%s~%s] → %d 筆",
            city, township, date_from, date_to, len(rows),
        )
        return rows
    except Exception as e:
        logger.error("check_cache 失敗: %s", e, exc_info=True)
        raise

def enqueue(city: str, township: str):
    """把需求寫進 crawl_queue（同一組 city+township 只會有一筆）"""
    try:
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO crawl_queue (city, township, requested_at)
                VALUES (?, ?, ?)
                """,
                [city, township, datetime.now().isoformat()],
            )
            conn.commit()
        logger.info("已寫入 crawl_queue: %s %s", city, township)
    except Exception as e:
        logger.error("enqueue 失敗: %s", e, exc_info=True)


def mark_done(city: str, township: str):
    """爬蟲完成後更新 queue 狀態"""
    variants     = _city_variants(city)
    placeholders = ",".join("?" * len(variants))
    try:
        with _get_conn() as conn:
            conn.execute(
                f"UPDATE crawl_queue SET status='done' WHERE city IN ({placeholders}) AND township=?",
                [*variants, township],
            )
            conn.commit()
    except Exception as e:
        logger.error("mark_done 失敗: %s", e, exc_info=True)

# ──────────────────────────────────────────
# 🔔 Discord 通知
# ──────────────────────────────────────────
def _notify(title: str, message: str):
    try:
        from notifier import send_alert
        send_alert(title=title, message=message)
    except Exception as e:
        logger.warning("Discord 通知失敗（不影響主流程）: %s", e)


# ──────────────────────────────────────────
#  🌐 Endpoints
# ──────────────────────────────────────────

@app.on_event("startup")
def startup():
    ensure_queue_table()
    logger.info("🚀 門牌查詢 API 啟動，DB=%s", DB_PATH)



@app.post("/query", summary="查詢門牌資料")
def query_door_plates(req: QueryRequest):
    """
    輸入縣市與鄉鎮市區，回傳門牌初編資料。
 
    - **DB 有資料（200）**：直接回傳，`cached: true`
    - **DB 無資料（202）**：系統已記錄，人工爬取中，完成後 Discord 通知
    """
    logger.info("POST /query city=%s township=%s", req.city, req.township)
 
    # 1. 查快取
    try:
        rows = check_cache(req.city, req.township)
    except Exception:
        raise HTTPException(status_code=500, detail="資料庫查詢失敗，請確認服務狀態")
    
     # 2a. HIT → 直接回傳
    if rows:
        logger.info("Cache HIT → 回傳 %d 筆", len(rows))
        records = [
            DoorPlateRecord(
                city         = r.get("city", ""),
                township     = r.get("district", ""),
                village      = r.get("village", ""),
                neighborhood = r.get("neighborhood", ""),
                detail       = r.get("detail", ""),
                date         = r.get("編釘日期", ""),
                category     = r.get("編釘類別", ""),
            )
            for r in rows
        ]
        return QueryResponse(
            city     = req.city,
            township = req.township,
            total    = len(records),
            cached   = True,
            records  = records,
        )
    
    # 2b. MISS → 寫 queue，回 202
    logger.warning("Cache MISS → 寫入 crawl_queue: %s %s", req.city, req.township)
    enqueue(req.city, req.township)
 
    # 同時送 Discord 提醒你（管理員）有新需求
    _notify(
        title   = f"📋 新爬蟲需求：{req.city} {req.township}",
        message = f"User 查詢了 {req.city} {req.township}，DB 無資料，請手動執行爬蟲後呼叫 POST /notify。",
    )
 
    return JSONResponse(
        status_code = 202,
        content = {
            "status":   "queued",
            "city":     req.city,
            "township": req.township,
            "message":  (
                f"目前尚無 {req.city} {req.township} 的資料，"
                f"系統已記錄您的需求，預計更新後將透過 Discord 通知，"
                f"完成後請再查詢一次。"
            ),
        },
    )


@app.post("/notify", summary="爬蟲完成後呼叫，送 Discord 通知 user")
def crawl_done_notify(req: NotifyRequest):
    """
    你手動跑完爬蟲後呼叫這個 endpoint。
    它會：
    1. 更新 crawl_queue 狀態為 done
    2. 送 Discord 通知告知 user 可以再查詢
    """
    logger.info("POST /notify city=%s township=%s count=%d", req.city, req.township, req.count)
    mark_done(req.city, req.township)
    _notify(
        title   = f"✅ 資料已更新：{req.city} {req.township}",
        message = f"共 {req.count} 筆資料已寫入，請再呼叫 POST /query 查詢。",
    )
    return {"status": "ok", "message": f"Discord 通知已送出，{req.city} {req.township} 標記完成。"}
 
 
@app.get("/queue", summary="查看待爬清單（管理員用）")
def get_queue():
    """查看 crawl_queue 裡還有哪些 pending 的需求"""
    try:
        conn = _get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT city, township, requested_at, status FROM crawl_queue ORDER BY id DESC")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"total": len(rows), "queue": rows}
    except Exception as e:
        logger.error("get_queue 失敗: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/health", summary="健康檢查")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

