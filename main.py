import asyncio
import httpx
import threading
from fastapi import FastAPI
import uvicorn
from database import SessionLocal
from models import ChamberLog

PING_URL = "https://4b07b8d1-5cf2-4d6d-bd0b-352fbfc2a886-00-6y30akrlro5p.pike.replit.dev/ping"
KEEP_ALIVE_INTERVAL = 300   # 5 menit

app = FastAPI()

# ===== STATE =====
keep_alive_task = None
stop_event = threading.Event()


@app.get("/")
def home():
    return {"status": "ok"}


@app.head("/ping")
def ping():
    return {"status": "alive"}


def keep_alive_loop():
    """Loop ping ke endpoint /ping tiap interval."""
    while not stop_event.is_set():
        try:
            r = httpx.head(PING_URL, timeout=10)
            print(f"🔄 Keep-alive ping → {r.status_code}")
        except Exception as e:
            print(f"❌ Keep-alive error: {e}")
        stop_event.wait(KEEP_ALIVE_INTERVAL)


def start_keep_alive():
    global keep_alive_task, stop_event
    if keep_alive_task is None or not keep_alive_task.is_alive():
        stop_event.clear()
        keep_alive_task = threading.Thread(target=keep_alive_loop, daemon=True)
        keep_alive_task.start()
        print("▶️ Keep-alive started")


def stop_keep_alive():
    global stop_event
    stop_event.set()
    print("⏹️ Keep-alive stopped")


def check_last_status():
    """Cek status terakhir chamber di database → tentukan keep-alive awal."""
    db = SessionLocal()
    last_log = db.query(ChamberLog).order_by(ChamberLog.timestamp.desc()).first()
    db.close()

    if last_log:
        # Jika lebih dari 3 menit tidak ada data → OFF
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        if (now - last_log.timestamp).total_seconds() > 180:
            print("⚠️ Startup: chamber OFF → start keep-alive")
            start_keep_alive()
        else:
            print("✅ Startup: chamber ON → no keep-alive")
    else:
        print("⚠️ Startup: belum ada log → asumsikan OFF")
        start_keep_alive()


if __name__ == "__main__":
    # Cek status terakhir saat start
    check_last_status()

    uvicorn.run(app, host="0.0.0.0", port=5000)
