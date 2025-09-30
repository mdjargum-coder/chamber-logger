from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base, get_db
from models import ChamberLog
import os
import asyncio
import httpx

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
PING_URL = "https://4b07b8d1-5cf2-4d6d-bd0b-352fbfc2a886-00-6y30akrlro5p.pike.replit.dev/ping" 
PING_INTERVAL = 120  # 2 menit sekali

_keep_alive_task = None


async def _keep_alive_loop():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.head(PING_URL, timeout=10)
                print(f"🔄 Keep-alive ping → {r.status_code}")
        except Exception as e:
            print(f"⚠️ Keep-alive error: {e}")
        await asyncio.sleep(PING_INTERVAL)


def start_keep_alive():
    """Aktifkan keep-alive ping"""
    global _keep_alive_task
    if _keep_alive_task is None or _keep_alive_task.done():
        loop = asyncio.get_event_loop()
        _keep_alive_task = loop.create_task(_keep_alive_loop())
        print("▶️ Keep-alive started")


def stop_keep_alive():
    """Matikan keep-alive ping"""
    global _keep_alive_task
    if _keep_alive_task and not _keep_alive_task.done():
        _keep_alive_task.cancel()
        _keep_alive_task = None
        print("⏹️ Keep-alive stopped")


# ===== API ENDPOINTS =====
@app.get("/")
def root():
    return {"message": "Chamber Logger API running"}


@app.get("/logs")
def get_logs(db: Session = Depends(get_db)):
    return db.query(ChamberLog).all()


@app.get("/status")
def status(db: Session = Depends(get_db)):
    last_log = db.query(ChamberLog).order_by(ChamberLog.id.desc()).first()
    if last_log:
        return {"status": last_log.status, "last_entry": last_log}
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


@app.get("/ping")
@app.head("/ping")
def ping():
    return {"status": "ok"}


# ===== STARTUP EVENT =====
@app.on_event("startup")
async def startup_event():
    """Cek status terakhir chamber dari DB saat startup"""
    db = SessionLocal()
    try:
        last_log = db.query(ChamberLog).order_by(ChamberLog.id.desc()).first()
        if not last_log or last_log.status == "OFF":
            start_keep_alive()
        else:
            stop_keep_alive()
    finally:
        db.close()
