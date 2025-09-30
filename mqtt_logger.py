import os
import json
import time
import csv
import httpx
import asyncio
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
from database import SessionLocal
from models import ChamberLog
from git_push import git_push

# === Konfigurasi ===
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "chamber/log"
ARCHIVE_DIR = "Archives"
PING_URL = os.environ.get(
    "REPLIT_PING_URL",
    "https://4b07b8d1-5cf2-4d6d-bd0b-352fbfc2a886-00-6y30akrlro5p.pike.replit.dev/ping"
)
KEEPALIVE_INTERVAL = int(os.environ.get("KEEPALIVE_INTERVAL", 300))  # 5 menit
TIMEOUT_OFF = timedelta(minutes=5)  # dianggap OFF jika >5 menit tanpa data

os.makedirs(ARCHIVE_DIR, exist_ok=True)

# === State ===
last_write_time = None
session_start_time = None
chamber_on = False
keepalive_running = False
keepalive_task = None


# === DB Utils ===
def save_log_to_db(data):
    db = SessionLocal()
    try:
        log = ChamberLog(
            h1=data["h1"],
            t1=data["t1"],
            h2=data["h2"],
            t2=data["t2"],
            status="ON",
            created_at=datetime.now()
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        db.close()


def archive_session_to_csv(start_time, end_time):
    filename = f"{ARCHIVE_DIR}/session_{start_time.strftime('%Y%m%d_%H%M%S')}_{end_time.strftime('%Y%m%d_%H%M%S')}.csv"
    db = SessionLocal()
    try:
        logs = (
            db.query(ChamberLog)
            .filter(ChamberLog.created_at >= start_time, ChamberLog.created_at <= end_time)
            .all()
        )
        with open(filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["created_at", "h1", "t1", "h2", "t2", "status"])
            for log in logs:
                writer.writerow([log.created_at, log.h1, log.t1, log.h2, log.t2, log.status])
        git_push(filename, f"Archive log {os.path.basename(filename)}")
        print(f"📦 Archived session to {filename}")
    finally:
        db.close()


# === Keep-alive ===
async def keep_alive():
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


def start_keepalive(loop):
    global keepalive_running, keepalive_task
    if not keepalive_running:
        keepalive_running = True
        keepalive_task = loop.create_task(keep_alive())


def stop_keepalive():
    global keepalive_running
    keepalive_running = False


# === MQTT Handlers ===
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected with result code 0")
        client.subscribe(TOPIC)
    else:
        print(f"Failed to connect, result code {rc}")


def on_message(client, userdata, msg):
    global last_write_time, session_start_time, chamber_on

    try:
        payload = json.loads(msg.payload.decode())
        save_log_to_db(payload)

        now = datetime.now()
        last_write_time = now

        if not chamber_on:
            session_start_time = now
            chamber_on = True
            print("✅ Chamber ON - session started")
            stop_keepalive()

        print(
            f"📝 Logged at {now.strftime('%H:%M:%S')} | "
            f"H1={payload['h1']}, T1={payload['t1']}, "
            f"H2={payload['h2']}, T2={payload['t2']}"
        )

    except Exception as e:
        print(f"Error processing message: {e}")


def check_chamber_status():
    global last_write_time, session_start_time, chamber_on
    loop = asyncio.get_event_loop()
    now = datetime.now()

    if chamber_on and last_write_time and (now - last_write_time) > TIMEOUT_OFF:
        # dianggap mati
        chamber_on = False
        print("⚠️ Chamber OFF - session ended")
        if session_start_time:
            archive_session_to_csv(session_start_time, now)
        start_keepalive(loop)


# === Main Loop ===
def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)

    while True:
        client.loop(timeout=1.0)
        check_chamber_status()
        time.sleep(1)


if __name__ == "__main__":
    main()
