import os
import threading
import asyncio
import httpx
from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from database import SessionLocal, engine, Base, get_db
from models import ChamberLog
from datetime import datetime
from sqlalchemy.orm import Session

# Buat tabel database
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # atau domain frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ARCHIVE_FOLDER = "archives"
os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

# ===== KEEP ALIVE CONFIG =====
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
        _ping_thread = threading.Thread(
            target=lambda: asyncio.run(_ping_loop_async()), daemon=True
        )
        _ping_thread.start()
        print("▶️ Keep-alive thread started")


def _stop_ping_thread():
    global _stop_event
    _stop_event.set()
    print("🛑 Keep-alive thread signalled to stop")


# dependency untuk DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_last_log():
    db = SessionLocal()
    try:
        return db.query(ChamberLog).order_by(ChamberLog.id.desc()).first()
    finally:
        db.close()

# ===== STARTUP EVENT =====
@app.on_event("startup")
async def on_startup():
    last = _get_last_log()
    now = datetime.now()
    STARTUP_OFF_THRESHOLD = int(os.environ.get("STARTUP_OFF_THRESHOLD", 180))

    if last is None:
        print("ℹ️ Startup: no previous log found -> starting keep-alive")
        _start_ping_thread()
        return

    last_status = getattr(last, "status", None)
    created_at = getattr(last, "created_at", None)

    if last_status == "OFF":
        print("⚠️ Startup: last status OFF -> starting keep-alive")
        _start_ping_thread()
        return

    if created_at:
        try:
            if (now - created_at).total_seconds() > STARTUP_OFF_THRESHOLD:
                print("⚠️ Startup: last log too old -> starting keep-alive")
                _start_ping_thread()
            else:
                print("✅ Startup: recent log found -> keep-alive not needed")
        except Exception:
            print("⚠️ Startup: datetime mismatch -> starting keep-alive")
            _start_ping_thread()
    else:
        print("ℹ️ Startup: last log has no created_at -> starting keep-alive")
        _start_ping_thread()


@app.on_event("shutdown")
async def on_shutdown():
    _stop_ping_thread()

# ===== API ENDPOINTS =====
@app.get("/")
def root():
    return {"message": "ok"}

@app.get("/status")
def status(db: Session = Depends(get_db)):
    last_log = db.query(ChamberLog).order_by(ChamberLog.created_at.desc()).first()
    if last_log:
        return {
            "status": last_log.status,
            "last_entry": {
                "id": last_log.id,
                "timestamp": last_log.created_at.isoformat() if last_log.created_at else None,
                "temperature1": last_log.temperature1,
                "temperature2": last_log.temperature2,
                "humidity1": last_log.humidity1,
                "humidity2": last_log.humidity2,
            }
        }
    return {"status": "OFF", "last_entry": None}


@app.get("/archives")
def list_archives(request: Request):
    files = sorted(os.listdir(ARCHIVE_FOLDER))
    base_url = str(request.base_url).replace("http://", "https://").rstrip("/")

    return {
        "archives": [
            f"{base_url}/download/{fname}"
            for fname in files if fname.endswith(".csv")
        ]
    }

@app.get("/download/{filename}")
def download_csv(filename: str):
    file_path = os.path.join(ARCHIVE_FOLDER, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/csv", filename=filename)
    return {"error": "File not found"}

@app.head("/ping")
@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/logs")
def get_logs(db: Session = Depends(get_db)):
    logs = db.query(ChamberLog).order_by(ChamberLog.created_at.desc()).limit(200).all()
    logs = list(reversed(logs))
    return [
        {
            "id": log.id,
            "timestamp": log.created_at.isoformat() if log.created_at else None,
            "humidity1": log.humidity1,
            "temperature1": log.temperature1,
            "humidity2": log.humidity2,
            "temperature2": log.temperature2,
            "status": log.status,
        }
        for log in logs
    ]



