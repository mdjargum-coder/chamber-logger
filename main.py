import os
import asyncio
import httpx
from fastapi import FastAPI
from database import SessionLocal
from models import ChamberLog
from datetime import datetime

app = FastAPI()

# === Konfigurasi ===
PING_URL = os.environ.get(
    "REPLIT_PING_URL",
    "https://4b07b8d1-5cf2-4d6d-bd0b-352fbfc2a886-00-6y30akrlro5p.pike.replit.dev/ping"
)
KEEPALIVE_INTERVAL = int(os.environ.get("KEEPALIVE_INTERVAL", 300))  # 5 menit
STARTUP_OFF_THRESHOLD = int(os.environ.get("STARTUP_OFF_THRESHOLD", 180))  # 3 menit

keepalive_task = None
keepalive_running = False


async def keep_alive():
    """Task ping Replit secara periodik"""
    global keepalive_running
    print("▶️ Keep-alive started")
    async with httpx.AsyncClient() as client:
        while keepalive_running:
            try:
                r = await client.head(PING_URL, timeout=10.0)
                print(f"🔄 Keep-alive ping → {r.status_code}")
            except Exception as e:
                print(f"⚠️ Keep-alive error: {e}")
            await asyncio.sleep(KEEPALIVE_INTERVAL)
    print("⏹️ Keep-alive stopped")


def get_last_chamber_log():
    """Ambil log terakhir dari DB"""
    db = SessionLocal()
    try:
        return db.query(ChamberLog).order_by(ChamberLog.id.desc()).first()
    finally:
        db.close()


def start_keepalive(loop):
    global keepalive_running, keepalive_task
    if not keepalive_running:
        keepalive_running = True
        keepalive_task = loop.create_task(keep_alive())


def stop_keepalive():
    global keepalive_running
    keepalive_running = False


@app.on_event("startup")
async def on_startup():
    loop = asyncio.get_event_loop()
    last_log = get_last_chamber_log()
    now = datetime.now()

    if last_log:
        created_at = last_log.created_at
        chamber_on = last_log.status == "ON"

        if chamber_on:
            print("✅ Startup: Chamber ON → keep-alive tidak jalan")
            stop_keepalive()
        else:
            # OFF → cek sudah lama atau baru mati
            if created_at and (now - created_at).total_seconds() > STARTUP_OFF_THRESHOLD:
                print("⚠️ Startup: Chamber OFF cukup lama → keep-alive jalan")
                start_keepalive(loop)
            else:
                print("⏸️ Startup: Chamber OFF tapi masih baru → keep-alive tidak perlu")
                stop_keepalive()
    else:
        print("ℹ️ Startup: Tidak ada log sebelumnya, default keep-alive jalan")
        start_keepalive(loop)


@app.on_event("shutdown")
async def on_shutdown():
    stop_keepalive()


@app.get("/")
async def root():
    return {"message": "Chamber logger is running"}


@app.get("/ping")
async def ping():
    return {"status": "ok"}
