# main.py
import os
import asyncio
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import ChamberLog

# buat tabel (jika belum)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# konfigurasi keep-alive
# Prefer environment var REPLIT_PING_URL, jika tidak ada, ganti manual di bawah
PING_URL = os.environ.get(
    "REPLIT_PING_URL",
    "https://4b07b8d1-5cf2-4d6d-bd0b-352fbfc2a886-00-6y30akrlro5p.pike.replit.dev/ping"
)
KEEP_ALIVE_INTERVAL = int(os.environ.get("KEEP_ALIVE_INTERVAL_SECONDS", 120))  # default 2 menit

# state
_keep_alive_task: asyncio.Task | None = None
_keep_alive_lock = asyncio.Lock()


@app.get("/")
def root():
    return {"message": "Chamber Logger API running"}


@app.head("/ping")
@app.get("/ping")
def ping():
    # simple reply for UptimeRobot (HEAD or GET)
    return {"status": "ok"}


# utility: baca last log record safely
def _get_last_log():
    db: Session = SessionLocal()
    try:
        last = db.query(ChamberLog).order_by(ChamberLog.id.desc()).first()
        return last
    finally:
        db.close()


# ===== keep-alive coroutine =====
async def _keep_alive_loop():
    """Task yang nge-head PING_URL tiap interval sampai dibatalkan."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.head(PING_URL, timeout=10)
                # jangan spam console — print ringkas
                print(f"🔄 keep-alive: {resp.status_code}")
            except Exception as e:
                print(f"⚠️ keep-alive error: {e}")
            await asyncio.sleep(KEEP_ALIVE_INTERVAL)


async def _start_keep_alive_async():
    global _keep_alive_task
    async with _keep_alive_lock:
        if _keep_alive_task is None or _keep_alive_task.done():
            loop = asyncio.get_running_loop()
            _keep_alive_task = loop.create_task(_keep_alive_loop())
            print("▶️ keep-alive started")


async def _stop_keep_alive_async():
    global _keep_alive_task
    async with _keep_alive_lock:
        if _keep_alive_task and not _keep_alive_task.done():
            _keep_alive_task.cancel()
            try:
                await _keep_alive_task
            except asyncio.CancelledError:
                pass
            _keep_alive_task = None
            print("⏹️ keep-alive stopped")


# synchronous wrappers so mqtt_logger (synchronous) can call them
def start_keep_alive():
    """Sync wrapper — schedule start on event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # not in running loop (e.g., main called outside uvicorn) — spawn background task
        asyncio.run(_start_keep_alive_async())
    else:
        # in running loop
        asyncio.create_task(_start_keep_alive_async())


def stop_keep_alive():
    """Sync wrapper — schedule stop on event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_stop_keep_alive_async())
    else:
        asyncio.create_task(_stop_keep_alive_async())


# startup: cek DB, kalau last entry menunjukkan OFF atau tidak ada entry => start keep-alive
@app.on_event("startup")
async def on_startup():
    last = _get_last_log()
    if not last:
        print("⚠️ Startup: no logs found → assume OFF, starting keep-alive")
        await _start_keep_alive_async()
        return

    # jika last.status exists and equals "OFF", atau created_at lama (no recent data), start
    try:
        if getattr(last, "status", None) == "OFF":
            print("⚠️ Startup: last status OFF → starting keep-alive")
            await _start_keep_alive_async()
            return
    except Exception:
        pass

    # fallback: if last created_at is older than TIMEOUT threshold (3 minutes) start keep-alive
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    created_at = getattr(last, "created_at", None)
    if created_at and (now - created_at).total_seconds() > int(os.environ.get("STARTUP_OFF_THRESHOLD", 180)):
        print("⚠️ Startup: last entry too old → starting keep-alive")
        await _start_keep_alive_async()
    else:
        print("✅ Startup: chamber likely ON → keep-alive not started")


# allow running main.py directly for local dev
if __name__ == "__main__":
    import uvicorn
    # start normally (uvicorn will call on_startup)
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), reload=False)
