import os
import subprocess
from datetime import datetime

def git_push(file_path, message=None):
    if not message:
        message = f"Add log {os.path.basename(file_path)} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("⚠️ GITHUB_TOKEN tidak ditemukan di environment. Log tetap tersimpan lokal.")
        return

    try:
        # Konfigurasi user Git (bot account saja, tidak pakai email pribadi)
        subprocess.run(["git", "config", "user.name", "chamber-logger-bot"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@chamber-logger.local"], check=True)

        # Stage file
        subprocess.run(["git", "add", file_path], check=True)

        # Commit (jika ada perubahan)
        subprocess.run(["git", "commit", "-m", message], check=True)

        # Push dengan token
        repo_url = f"https://{token}@github.com/mdjargum-coder/chamber-logger.git"
        subprocess.run(["git", "push", repo_url, "master"], check=True)

        print(f"✅ Log {file_path} berhasil dipush ke GitHub")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git push gagal: {e}. Log tetap tersimpan di lokal.")
    except Exception as e:
        print(f"❌ Error tidak terduga: {e}. Log tetap tersimpan di lokal.")
