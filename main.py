# main.py (perbaikan)
import os
import threading
import asyncio
import httpx
from fastapi import FastAPI, Depends
from database import SessionLocal
from models import ChamberLog            # <---- PENTING: import model
from datetime import datetime

app = FastAPI()

KEEP_ALIVE_URL = os.environ.get(
    "REPLIT_PING_URL",
    "https://4b07b8d1-5cf2-4d6d-bd0b-352fbfc2a886-00-6y30akrlro5p.pike.replit.dev/ping"
)
PING_INTERVAL = int(os.environ.get("PING_INTERVAL", 120))

# threading control
_ping_thread = None
_stop_event = threading.Event()


async def _ping_once():
    async with httpx.AsyncClient() as client:
        return await client.head(KEEP_ALIVE_URL, timeout=10)


async def _ping_loop_async():
    async with httpx.AsyncClient() as client:
        while not _stop_event.is_set():
            try:
                r = await client.head(KEEP_ALIVE_URL, timeout=10)
                print(f"🔄 Keep-alive ping → {r.status_code}")
            except Exception as e:
                print("⚠️ Keep-alive error:", e)
            await asyncio.sleep(PING_INTERVAL)
    print("⏹️ Keep-alive loop ended")


def _start_ping_thread():
    global _ping_thread, _stop_event
    if _ping_thread is None or not _ping_thread.is_alive():
        _stop_event.clear()
        # run async loop inside thread
        _ping_thread = threading.Thread(target=lambda: asyncio.run(_ping_loop_async()), daemon=True)
        _ping_thread.start()
        print("▶️ Keep-alive thread started")


def _stop_ping_thread():
    global _stop_event
    _stop_event.set()
    print("🛑 Keep-alive thread signalled to stop")


# synchronous wrappers exported for mqtt_logger to call
def start_keep_alive():
    _start_ping_thread()


def stop_keep_alive():
    _stop_ping_thread()


def _get_last_log():
    db = SessionLocal()
    try:
        return db.query(ChamberLog).order_by(ChamberLog.id.desc()).first()
    finally:
        db.close()


@app.on_event("startup")
async def on_startup():
    # cek status terakhir dari DB dan tentukan apakah perlu start keep-alive
    last = _get_last_log()
    now = datetime.now()
    STARTUP_OFF_THRESHOLD = int(os.environ.get("STARTUP_OFF_THRESHOLD", 180))  # detik

    if last is None:
        print("ℹ️ Startup: no previous log found -> starting keep-alive")
        _start_ping_thread()
        return

    # jika ada field status dan bernilai "OFF" -> start
    last_status = getattr(last, "status", None)
    created_at = getattr(last, "created_at", None)

    if last_status == "OFF":
        print("⚠️ Startup: last status OFF -> starting keep-alive")
        _start_ping_thread()
        return

    # fallback: jika last.created_at terlalu lama -> start
    if created_at:
        # buat created_at dan now sama tipe (naive)
        try:
            if (now - created_at).total_seconds() > STARTUP_OFF_THRESHOLD:
                print("⚠️ Startup: last log too old -> starting keep-alive")
                _start_ping_thread()
            else:
                print("✅ Startup: recent log found -> keep-alive not needed")
        except Exception:
            # jika tipe timezone mismatch, just start keep-alive as safe fallback
            print("⚠️ Startup: datetime mismatch -> starting keep-alive")
            _start_ping_thread()
    else:
        print("ℹ️ Startup: last log has no created_at -> starting keep-alive")
        _start_ping_thread()


@app.on_event("shutdown")
async def on_shutdown():
    _stop_ping_thread()


@app.get("/")
def root():
    return {"message": "ok"}


@app.head("/ping")
@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/logs")
def get_logs(db: Session = Depends(get_db)):
    logs = db.query(ChamberLog).order_by(ChamberLog.timestamp.desc()).limit(200).all()
    # urutkan biar lama → baru
    logs = list(reversed(logs))
    return [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "humidity1": log.humidity1,
            "temperature1": log.temperature1,
            "humidity2": log.humidity2,
            "temperature2": log.temperature2,
            "status": log.status,
        }
        for log in logs
    ]




