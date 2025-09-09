FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Pastikan folder data & archives ada
RUN mkdir -p /app/archives /app/data

# Pastikan start script executable
RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["./start.sh"]
