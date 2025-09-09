import os
import subprocess
from datetime import datetime

def git_push(file_path, message=None):
    if not message:
        message = f"Add log {os.path.basename(file_path)} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    ssh_key = os.environ.get("SSH_PRIVATE_KEY")
    git_env = os.environ.copy()

    if ssh_key:
        ssh_path = "/tmp/id_ed25519"
        with open(ssh_path, "w") as f:
            f.write(ssh_key)
        os.chmod(ssh_path, 0o600)
        git_env["GIT_SSH_COMMAND"] = f"ssh -i {ssh_path} -o StrictHostKeyChecking=no"

    try:
        # Set Git identity
        subprocess.run(["git", "config", "user.name", "mdjargum-coder"], check=True, env=git_env)
        subprocess.run(["git", "config", "user.email", "mdjargum@gmail.com"], check=True, env=git_env)

        # Stage file
        subprocess.run(["git", "add", file_path], check=True, env=git_env)

        # Commit
        subprocess.run(["git", "commit", "-m", message], check=True, env=git_env)

        # Push
        subprocess.run(["git", "push", "origin", "master"], check=True, env=git_env)

        print(f"✅ Log {file_path} berhasil dipush ke GitHub")
    except subprocess.CalledProcessError as e:
        print("⚠️ Git push gagal:", e)
