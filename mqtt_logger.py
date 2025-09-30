import paho.mqtt.client as mqtt
import json
import time
import os
import csv
from datetime import datetime, timezone, timedelta

from database import SessionLocal
from models import ChamberLog
from git_push import git_push
from main import start_keep_alive, stop_keep_alive   # 🔥 import fungsi kontrol keep-alive

# ===== CONFIG =====
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "chamber/log"
LOG_INTERVAL = 60          # tulis log tiap 1 menit
TIMEOUT_OFF = 120          # kalau 2 menit tidak ada data → OFF
WIB = timezone(timedelta(hours=7))

# ===== STATE =====
last_data_time = None
last_log_time = None
session_start_time = None
chamber_on = False
chamber_off_notified = False
new_data_received = False

# ===== FOLDER LOG =====
if not os.path.exists("logs"):
    os.makedirs("logs")


def archive_session_to_csv(start_time, end_time):
    """Export data session ke CSV & push ke Git."""
    filename = f"logs/session_{start_time.strftime('%Y%m%d_%H%M%S')}_to_{end_time.strftime('%Y%m%d_%H%M%S')}.csv"

    db = SessionLocal()
    logs = db.query(ChamberLog).filter(
        ChamberLog.timestamp >= start_time,
        ChamberLog.timestamp <= end_time
    ).all()
    db.close()

    if not logs:
        return None

    with open(filename, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "humidity1", "temperature1", "humidity2", "temperature2"])
        for log in logs:
            writer.writerow([log.timestamp, log.humidity1, log.temperature1, log.humidity2, log.temperature2])

    git_push(filename)
    print(f"📁 Session archived to {filename}")
    return filename


def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    global last_data_time, last_log_time, chamber_on, session_start_time
    global chamber_off_notified, new_data_received

    try:
        data = json.loads(msg.payload.decode())
        humidity1 = data.get("humidity1")
        temperature1 = data.get("temperature1")
        humidity2 = data.get("humidity2")
        temperature2 = data.get("temperature2")
        now = datetime.now(WIB)

        last_data_time = datetime.now(timezone.utc)
        new_data_received = True

        if last_log_time is None or (now - last_log_time).total_seconds() >= LOG_INTERVAL:
            db = SessionLocal()
            log = ChamberLog(
                timestamp=now,
                humidity1=humidity1,
                temperature1=temperature1,
                humidity2=humidity2,
                temperature2=temperature2
            )
            db.add(log)
            db.commit()
            db.close()

            last_log_time = now
            print(f"📝 Logged at {now.strftime('%H:%M:%S WIB')} | H1={humidity1}, T1={temperature1}, H2={humidity2}, T2={temperature2}")

    except Exception as e:
        print("Error processing message:", e)


def check_chamber_status():
    """Pantau status chamber ON/OFF."""
    global chamber_on, chamber_off_notified, session_start_time, new_data_received, last_data_time

    now = datetime.now(timezone.utc)

    # Jika ada data baru & chamber sebelumnya OFF → berarti ON
    if new_data_received and not chamber_on:
        chamber_on = True
        session_start_time = datetime.now(timezone.utc).astimezone(WIB)
        print("✅ Chamber ON - session started")
        chamber_off_notified = False
        new_data_received = False   # reset flag

        # 🔥 Stop keep-alive saat chamber ON
        stop_keep_alive()
        print("✅ Chamber hidup, stop keep-alive")

    # Jika chamber ON tapi tidak ada data > TIMEOUT_OFF → berarti OFF
    if chamber_on and last_data_time and now - last_data_time > TIMEOUT_OFF:
        chamber_on = False
        session_end_time = datetime.now(timezone.utc).astimezone(WIB)

        # Simpan ke CSV
        if session_start_time:
            archive_session_to_csv(session_start_time, session_end_time)

        chamber_off_notified = True
        session_start_time = None
        print("⚠️ Chamber OFF - session ended")

        # 🔥 Start keep-alive saat chamber OFF
        start_keep_alive()
        print("⚠️ Chamber mati, start keep-alive")


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    try:
        while True:
            check_chamber_status()
            time.sleep(5)
    except KeyboardInterrupt:
        client.loop_stop()


if __name__ == "__main__":
    main()

