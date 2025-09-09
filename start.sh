#!/bin/bash
# Pastikan executable
# chmod +x start.sh

# Jalankan mqtt_logger.py di background
python mqtt_logger.py &

# Jalankan FastAPI
uvicorn main:app --host 0.0.0.0 --port 8000
