from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base, get_db
from models import ChamberLog
import os
import asyncio
import httpx

# ===== DB SETUP =====
Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ARCHIVE_FOLDER = "archives"
os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

# ===== ROUTES =====
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

# ===== KEEP ALIVE LOOP =====
async def keep_alive_loop():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                db = SessionLocal()
                last_log = db.query(ChamberLog).order_by(ChamberLog.id.desc()).first()
                db.close()

                if last_log and last_log.status == "OFF":
                    await client.head("https://your-app-name.repl.co/ping", timeout=10)
                    print("🔄 Keep-alive ping sent (chamber OFF)")
                else:
                    print("✅ Chamber ON, keep-alive tidak jalan")

            except Exception as e:
                print(f"⚠️ Keep-alive error: {e}")

            await asyncio.sleep(120)  # tiap 2 menit

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(keep_alive_loop())
