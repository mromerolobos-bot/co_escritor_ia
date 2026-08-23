import os
import sys
import urllib.request
import subprocess

APP_DIR = os.path.join(os.path.expanduser("~"), "InvChatGPTLauncher")
LAUNCHER_PATH = os.path.join(APP_DIR, "launcher.pyw")
RAW_URL = "https://raw.githubusercontent.com/mromerolobos-bot/co_escritor_ia/launcher/cerebro-manos/tools/cerebro_manos/launcher.pyw"

os.makedirs(APP_DIR, exist_ok=True)
urllib.request.urlretrieve(RAW_URL, LAUNCHER_PATH)

# Verify syntax without executing the GUI.
subprocess.run([sys.executable, "-m", "py_compile", LAUNCHER_PATH], check=True)

# Build a normal Windows desktop shortcut using only built-in Windows tooling.
desktop = os.path.join(os.path.expanduser("~"), "Desktop")
os.makedirs(desktop, exist_ok=True)
shortcut = os.path.join(desktop, "Cerebro + Manos.lnk")

pythonw = sys.executable
if pythonw.lower().endswith("python.exe"):
    candidate = os.path.join(os.path.dirname(pythonw), "pythonw.exe")
    if os.path.isfile(candidate):
        pythonw = candidate

q = lambda s: s.replace("'", "''")
ps = (
    "$ws=New-Object -ComObject WScript.Shell;"
    f"$s=$ws.CreateShortcut('{q(shortcut)}');"
    f"$s.TargetPath='{q(pythonw)}';"
    f"$s.Arguments='\"{q(LAUNCHER_PATH)}\"';"
    f"$s.WorkingDirectory='{q(APP_DIR)}';"
    "$s.Description='Inicia ChatGPT, Antigravity y /inv_chatgpt';"
    "$s.Save();"
)
result = subprocess.run(
    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    raise RuntimeError(result.stderr.strip() or "No se pudo crear el acceso directo")

print("READY:", LAUNCHER_PATH)
print("SHORTCUT:", shortcut)
