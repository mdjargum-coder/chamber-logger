from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base, get_db
from models import ChamberLog
import os

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

# Endpoint archives → daftar file CSV
@app.get("/archives")
def list_archives(request: Request):
    files = sorted(os.listdir(ARCHIVE_FOLDER))

    # paksa base_url selalu HTTPS
    base_url = str(request.base_url).replace("http://", "https://").rstrip("/")

    return {
        "archives": [
            f"{base_url}/download/{fname}"
            for fname in files if fname.endswith(".csv")
        ]
    }

# Endpoint download CSV tertentu
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

