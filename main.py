import asyncio
import httpx
from sqlalchemy.orm import Session
from database import SessionLocal
import threading

KEEP_ALIVE_URL = "https://4b07b8d1-5cf2-4d6d-bd0b-352fbfc2a886-00-6y30akrlro5p.pike.replit.dev/ping"
PING_INTERVAL = 120  # 2 menit sekali
ping_task = None
stop_event = threading.Event()


def get_last_status():
    """Ambil status terakhir dari database."""
    db: Session = SessionLocal()
    try:
        last_log = db.query(ChamberLog).order_by(ChamberLog.id.desc()).first()
        return last_log.status if last_log else "OFF"
    finally:
        db.close()


async def ping_loop():
    """Loop keep-alive yang jalan di background."""
    async with httpx.AsyncClient() as client:
        while not stop_event.is_set():
            try:
                resp = await client.get(KEEP_ALIVE_URL, timeout=10)
                print(f"🌍 Keep-alive ping → {resp.status_code}")
            except Exception as e:
                print(f"⚠️ Keep-alive gagal: {e}")
            await asyncio.sleep(PING_INTERVAL)


def start_keep_alive():
    """Mulai keep-alive loop (hanya sekali)."""
    global ping_task, stop_event
    if ping_task is None or not ping_task.is_alive():
        stop_event.clear()
        ping_task = threading.Thread(target=lambda: asyncio.run(ping_loop()), daemon=True)
        ping_task.start()
        print("✅ Keep-alive loop DIMULAI")


def stop_keep_alive():
    """Hentikan keep-alive loop."""
    global stop_event
    stop_event.set()
    print("🛑 Keep-alive loop DIHENTIKAN")


# === Jalankan sekali saat startup ===
if get_last_status() == "OFF":
    start_keep_alive()
