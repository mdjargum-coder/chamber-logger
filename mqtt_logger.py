import paho.mqtt.client as mqtt
import json
import time
import os
import csv
from datetime import datetime, timezone, timedelta

from database import SessionLocal
from models import ChamberLog
from git_push import git_push
from main import start_keep_alive, stop_keep_alive   # 🔥 import fungsi keep-alive

# ===== CONFIG =====
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "chamber/log"
LOG_INTERVAL = 60      # tulis log tiap 1 menit
TIMEOUT_OFF = 60       # 1 menit tanpa data = chamber OFF
ARCHIVE_FOLDER = os.path.join(os.path.dirname(__file__), "archives")
TIMEZONE_OFFSET = 7    # WIB = UTC+7

# ===== VARIABEL =====
latest_data = None
last_data_time = None
last_write_time = time.time()
chamber_on = False
session_start_time = None
chamber_off_notified = False
new_data_received = False

# Pastikan folder archives ada
os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

# WIB timezone
WIB = timezone(timedelta(hours=TIMEZONE_OFFSET))

# ===== CALLBACKS =====
def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    global latest_data, last_data_time, new_data_received
    try:
        payload = json.loads(msg.payload.decode())
        latest_data = payload
        last_data_time = time.time()
        new_data_received = True
    except Exception as e:
        print("Error parsing message:", e)

# ===== ARCHIVE FUNCTION =====
def archive_session_to_csv(start_time, end_time):
    if not start_time or not end_time:
        return None

    db = SessionLocal()
    try:
        logs = db.query(ChamberLog).filter(
            ChamberLog.created_at >= start_time,
            ChamberLog.created_at <= end_time
        ).all()

        if not logs:
            print("⚠️ No logs found for this session")
            return None

        file_name = f"session_{start_time.strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        file_path = os.path.join(ARCHIVE_FOLDER, file_name)

        fieldnames = ["id","tanggal","waktu","temperature1","temperature2","humidity1","humidity2","status","created_at"]
        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for log in logs:
                writer.writerow({
                    "id": log.id,
                    "tanggal": log.tanggal,
                    "waktu": log.waktu,
                    "temperature1": log.temperature1,
                    "temperature2": log.temperature2,
                    "humidity1": log.humidity1,
                    "humidity2": log.humidity2,
                    "status": log.status,
                    "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S")
                })

        print(f"📦 Archived session → {file_path}")
        git_push(file_path)
        return file_path
    finally:
        db.close()

# ===== STATUS LOG HELPERS =====
def log_status(status: str):
    db = SessionLocal()
    try:
        dt = datetime.now(timezone.utc).astimezone(WIB)
        log = ChamberLog(
            tanggal=dt.strftime("%Y-%m-%d"),
            waktu=dt.strftime("%H:%M:%S"),
            humidity1=None,
            temperature1=None,
            humidity2=None,
            temperature2=None,
            status=status,
            created_at=dt
        )
        db.add(log)
        db.commit()
        print(f"📌 {status} status logged into DB")
    finally:
        db.close()

def handle_chamber_on():
    stop_keep_alive()
    print("✅ Chamber hidup, stop keep-alive")
    log_status("ON")

def handle_chamber_off():
    start_keep_alive()
    print("⚠️ Chamber mati, start keep-alive")
    log_status("OFF")

# ===== MQTT CLIENT =====
client = mqtt.Client(protocol=mqtt.MQTTv311)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)

# ===== LOOP =====
while True:
    client.loop(timeout=1.0)
    now = time.time()
    
    # Chamber baru ON
    if new_data_received and not chamber_on:
        chamber_on = True
        session_start_time = datetime.now(timezone.utc).astimezone(WIB)
        print("✅ Chamber ON - session started")
        chamber_off_notified = False
        new_data_received = False
        handle_chamber_on()

    # Chamber mati (tidak ada data > TIMEOUT_OFF)
    if chamber_on and last_data_time and now - last_data_time > TIMEOUT_OFF:
        chamber_on = False
        session_end_time = datetime.now(timezone.utc).astimezone(WIB)
        if not chamber_off_notified:
            db = SessionLocal()
            logs = db.query(ChamberLog).filter(
                ChamberLog.created_at >= session_start_time,
                ChamberLog.created_at <= session_end_time
            ).count()
            db.close()

            if logs > 0:
                print("⚠️ Chamber OFF - session ended")
                archive_session_to_csv(session_start_time, session_end_time)
            else:
                print("⚠️ Chamber OFF - no logs, skipped archive")
       
            chamber_off_notified = True
            handle_chamber_off()

        session_start_time = None

    # Simpan data ke DB tiap 1 menit sekali
    if chamber_on and latest_data and now - last_write_time >= LOG_INTERVAL:
        db = SessionLocal()
        try:
            dt = datetime.now(timezone.utc).astimezone(WIB)
            log = ChamberLog(
                tanggal=dt.strftime("%Y-%m-%d"),
                waktu=dt.strftime("%H:%M:%S"),
                temperature1=latest_data.get("temperature1"),
                temperature2=latest_data.get("temperature2"),
                humidity1=latest_data.get("humidity1"),
                humidity2=latest_data.get("humidity2"),
                status="ON",
                created_at=dt
            )
            db.add(log)
            db.commit()
            print(f"📝 Logged at {dt.strftime('%H:%M:%S')} WIB | "
                  f"H1={log.humidity1}, T1={log.temperature1}, "
                  f"H2={log.humidity2}, T2={log.temperature2}")
        finally:
            db.close()
        last_write_time = now
