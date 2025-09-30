# mqtt_logger.py
import paho.mqtt.client as mqtt
import json
import time
import os
import csv
from datetime import datetime, timezone, timedelta

from database import SessionLocal
from models import ChamberLog
from git_push import git_push

# import control keep-alive (sync wrappers) from main
# NOTE: main.start_keep_alive/stop_keep_alive are synchronous wrappers that schedule the async tasks
from main import start_keep_alive, stop_keep_alive

# ===== CONFIG =====
BROKER = os.environ.get("MQTT_BROKER", "broker.hivemq.com")
PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPIC = os.environ.get("MQTT_TOPIC", "chamber/log")
LOG_INTERVAL = int(os.environ.get("LOG_INTERVAL", 60))      # seconds between DB writes
TIMEOUT_OFF = int(os.environ.get("TIMEOUT_OFF", 180))       # seconds to consider OFF
ARCHIVE_FOLDER = os.path.join(os.path.dirname(__file__), "archives")
TIMEZONE_OFFSET = int(os.environ.get("TIMEZONE_OFFSET", 7))  # WIB = UTC+7

# STATE
latest_data = None
last_data_time = None        # will be float: time.time()
last_write_time = 0
chamber_on = False
session_start_time = None
chamber_off_notified = False
new_data_received = False

os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

WIB = timezone(timedelta(hours=TIMEZONE_OFFSET))


def on_connect(client, userdata, flags, rc):
    print("MQTT connected, rc:", rc)
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    """Process incoming MQTT payload. Ensure last_data_time stays as float."""
    global latest_data, last_data_time, new_data_received
    try:
        payload = json.loads(msg.payload.decode())

        # remove unexpected keys that model doesn't accept (e.g., timestamp)
        payload.pop("timestamp", None)
        payload.pop("time", None)

        latest_data = payload
        last_data_time = time.time()   # keep as float seconds
        new_data_received = True

    except Exception as e:
        print("Error parsing message:", e)


def archive_session_to_csv(start_time, end_time):
    """Query DB using created_at (consistent) and write CSV."""
    if not start_time or not end_time:
        return None

    db = SessionLocal()
    try:
        logs = db.query(ChamberLog).filter(
            ChamberLog.created_at >= start_time,
            ChamberLog.created_at <= end_time
        ).order_by(ChamberLog.id.asc()).all()
    finally:
        db.close()

    if not logs:
        print("⚠️ archive: no logs in interval")
        return None

    filename = f"session_{start_time.strftime('%Y%m%d_%H%M%S')}.csv"
    path = os.path.join(ARCHIVE_FOLDER, filename)

    fieldnames = ["id", "tanggal", "waktu", "temperature1", "temperature2", "humidity1", "humidity2", "status", "created_at"]
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in logs:
                writer.writerow({
                    "id": r.id,
                    "tanggal": getattr(r, "tanggal", ""),
                    "waktu": getattr(r, "waktu", ""),
                    "temperature1": getattr(r, "temperature1", ""),
                    "temperature2": getattr(r, "temperature2", ""),
                    "humidity1": getattr(r, "humidity1", ""),
                    "humidity2": getattr(r, "humidity2", ""),
                    "status": getattr(r, "status", ""),
                    "created_at": getattr(r, "created_at").strftime("%Y-%m-%d %H:%M:%S") if getattr(r, "created_at", None) else ""
                })
        print(f"📦 Archived session → {path}")
        # push but don't let exceptions kill the worker
        try:
            git_push(path)
        except Exception as e:
            print("⚠️ git_push failed (caught):", e)
        return path
    except Exception as e:
        print("❌ Failed to write CSV:", e)
        return None


def handle_chamber_on():
    """Called when chamber becomes ON."""
    global chamber_off_notified
    chamber_off_notified = False
    try:
        stop_keep_alive()
    except Exception as e:
        print("⚠️ stop_keep_alive error:", e)
    print("✅ Chamber ON - keep-alive stopped")


def handle_chamber_off():
    """Called when chamber becomes OFF (after archiving)."""
    try:
        start_keep_alive()
    except Exception as e:
        print("⚠️ start_keep_alive error:", e)
    print("⚠️ Chamber OFF - keep-alive started")


def check_chamber_status():
    """Periodically called to decide ON/OFF and archive."""
    global chamber_on, session_start_time, chamber_off_notified, last_write_time

    now_ts = time.time()

    # new_data_received => chamber becomes ON
    if new_data_received and not chamber_on:
        chamber_on = True
        session_start_time = datetime.now(timezone.utc).astimezone(WIB)
        new_data_received_local = False
        print("✅ Chamber ON - session started")
        handle_chamber_on()

    # If chamber is ON and we've gone TIMEOUT_OFF seconds since last data => OFF
    if chamber_on and last_data_time and (now_ts - last_data_time) > TIMEOUT_OFF:
        chamber_on = False
        session_end = datetime.now(timezone.utc).astimezone(WIB)
        print("⚠️ Chamber OFF detected, archiving...")

        # archive
        try:
            if session_start_time:
                archive_session_to_csv(session_start_time, session_end)
        except Exception as e:
            print("⚠️ archive error:", e)

        chamber_off_notified = True
        session_start_time = None
        handle_chamber_off()

    # If chamber is ON, write DB every LOG_INTERVAL seconds
    if chamber_on and latest_data and (now_ts - last_write_time) >= LOG_INTERVAL:
        # prepare DB fields; ignore missing keys gracefully
        temp1 = latest_data.get("temperature1")
        temp2 = latest_data.get("temperature2")
        hum1 = latest_data.get("humidity1")
        hum2 = latest_data.get("humidity2")

        dt = datetime.now(timezone.utc).astimezone(WIB)
        db = SessionLocal()
        try:
            # map to your model fields (consistent with earlier main.py usage)
            log = ChamberLog(
                tanggal=dt.strftime("%Y-%m-%d"),
                waktu=dt.strftime("%H:%M:%S"),
                temperature1=temp1,
                temperature2=temp2,
                humidity1=hum1,
                humidity2=hum2,
                status="ON",
                created_at=dt
            )
            db.add(log)
            db.commit()
            print(f"📝 Logged at {dt.strftime('%H:%M:%S')} WIB | H1={hum1}, T1={temp1}, H2={hum2}, T2={temp2}")
        except Exception as e:
            print("❌ DB write error:", e)
        finally:
            db.close()

        # update last_write_time after successful write attempt
        global last_write_time
        last_write_time = now_ts


def main():
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(BROKER, PORT, 60)
    except Exception as e:
        print("⚠️ MQTT connect error:", e)
        # still continue; loop_start will attempt reconnect
    client.loop_start()

    try:
        while True:
            check_chamber_status()
            time.sleep(1)
    except KeyboardInterrupt:
        client.loop_stop()


if __name__ == "__main__":
    main()
