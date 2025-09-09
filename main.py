from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base, get_db
from models import ChamberLog
import os

# Buat tabel database
Base.metadata.create_all(bind=engine)

app = FastAPI()

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
def list_archives():
    files = sorted(os.listdir(ARCHIVE_FOLDER))
    return {
        "archives": [
            f"http://127.0.0.1:8000/download/{fname}"
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
