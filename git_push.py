import subprocess
import os
from datetime import datetime

def git_push(file_path, message=None):
    """
    Push file log baru ke GitHub (folder archives/).
    file_path: path file CSV yang baru dibuat.
    message: commit message (optional).
    """

    if not message:
        message = f"Add log {os.path.basename(file_path)} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    try:
        # Stage file
        subprocess.run(["git", "add", file_path], check=True)

        # Commit
        subprocess.run(["git", "commit", "-m", message], check=True)

        # Push
        subprocess.run(["git", "push", "origin", "master"], check=True)

        print(f"✅ Log {file_path} berhasil dipush ke GitHub")
    except subprocess.CalledProcessError as e:
        print("⚠️ Git push gagal:", e)
