import os
import subprocess
from datetime import datetime

def git_push(file_path, message=None):
    if not message:
        message = f"Add log {os.path.basename(file_path)} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    ssh_key = os.environ.get("SSH_PRIVATE_KEY")
    if ssh_key:
        # Tulis sementara ke file id_ed25519
        ssh_path = "/tmp/id_ed25519"
        with open(ssh_path, "w") as f:
            f.write(ssh_key)
        os.chmod(ssh_path, 0o600)
        os.environ["GIT_SSH_COMMAND"] = f"ssh -i {ssh_path} -o StrictHostKeyChecking=no"

    try:
        subprocess.run(["git", "add", file_path], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "push", "origin", "master"], check=True)
        print(f"✅ Log {file_path} berhasil dipush ke GitHub")
    except subprocess.CalledProcessError as e:
        print("⚠️ Git push gagal:", e)
