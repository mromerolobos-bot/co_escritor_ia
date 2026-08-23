import os
import sys
import json
import time
import subprocess
import webbrowser
import tkinter as tk
from tkinter import messagebox, filedialog

APP_DIR = os.path.join(os.path.expanduser("~"), "InvChatGPTLauncher")
CONFIG_PATH = os.path.join(APP_DIR, "launcher_config.json")
CHATGPT_URL = "https://chatgpt.com/"
BRIDGE_MUTEX = r"Local\AntigravityInverseBridge_SingleInstance_Mutex"

os.makedirs(APP_DIR, exist_ok=True)


def load_config():
    cfg = {"antigravity_path": "", "daemon_path": ""}
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def token_exists():
    return bool(os.environ.get("ANTIGRAVITY_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN"))


def bridge_running():
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        SYNCHRONIZE = 0x00100000
        kernel32.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.OpenMutexW.restype = wintypes.HANDLE
        handle = kernel32.OpenMutexW(SYNCHRONIZE, False, BRIDGE_MUTEX)
        if handle:
            kernel32.CloseHandle(handle)
            return True
    except Exception:
        pass
    return False


def find_daemon(cfg):
    saved = cfg.get("daemon_path", "")
    if saved and os.path.isfile(saved):
        return saved

    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "co_escritor_ia", "inverse_bridge", "inverse_bridge_daemon.py"),
        os.path.join(home, "inverse_bridge", "inverse_bridge_daemon.py"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            cfg["daemon_path"] = p
            save_config(cfg)
            return p

    skip = {"AppData", ".git", "node_modules", "env", ".venv", "venv", "__pycache__", "models", "Downloads"}
    try:
        for root, dirs, files in os.walk(home):
            dirs[:] = [d for d in dirs if d not in skip]
            rel = os.path.relpath(root, home)
            if rel != "." and rel.count(os.sep) > 5:
                dirs[:] = []
                continue
            if "inverse_bridge_daemon.py" in files:
                p = os.path.join(root, "inverse_bridge_daemon.py")
                cfg["daemon_path"] = p
                save_config(cfg)
                return p
    except Exception:
        pass
    return ""


def start_bridge(cfg):
    if bridge_running():
        return True, "Bridge ya estaba activo."
    if not token_exists():
        return False, "No encuentro ANTIGRAVITY_GITHUB_TOKEN en las variables de entorno."
    daemon = find_daemon(cfg)
    if not daemon:
        return False, "No encontré inverse_bridge_daemon.py. Usa 'Elegir daemon' una vez."
    try:
        python_exe = sys.executable
        if python_exe.lower().endswith("pythonw.exe"):
            alt = os.path.join(os.path.dirname(python_exe), "python.exe")
            if os.path.isfile(alt):
                python_exe = alt
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        subprocess.Popen([python_exe, daemon], cwd=os.path.dirname(daemon), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
        for _ in range(20):
            time.sleep(0.25)
            if bridge_running():
                return True, "Bridge iniciado."
        return True, "Se lanzó el daemon; aún no confirmé el mutex."
    except Exception as e:
        return False, f"No pude iniciar el bridge: {e}"


def start_antigravity(cfg):
    saved = cfg.get("antigravity_path", "")
    if saved and os.path.isfile(saved):
        try:
            subprocess.Popen([saved], close_fds=True)
            return True, "Antigravity iniciado."
        except Exception:
            pass

    if sys.platform == "win32":
        ps = (
            "$a = Get-StartApps | Where-Object { $_.Name -match 'Antigravity' } | Select-Object -First 1; "
            "if ($a) { Start-Process explorer.exe ('shell:AppsFolder\\' + $a.AppID); exit 0 } else { exit 2 }"
        )
        try:
            r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], capture_output=True, text=True, timeout=12, creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode == 0:
                return True, "Antigravity iniciado desde Inicio de Windows."
        except Exception:
            pass
    return False, "No pude localizar Antigravity automáticamente."


def choose_antigravity(cfg):
    p = filedialog.askopenfilename(title="Selecciona Antigravity", filetypes=[("Aplicaciones", "*.exe"), ("Todos los archivos", "*.*")])
    if p:
        cfg["antigravity_path"] = p
        save_config(cfg)
        refresh_status()
        messagebox.showinfo("Guardado", "Ruta de Antigravity guardada.")


def choose_daemon(cfg):
    p = filedialog.askopenfilename(title="Selecciona inverse_bridge_daemon.py", filetypes=[("Python", "*.py"), ("Todos los archivos", "*.*")])
    if p:
        cfg["daemon_path"] = p
        save_config(cfg)
        refresh_status()
        messagebox.showinfo("Guardado", "Ruta del daemon guardada.")


def open_chatgpt():
    webbrowser.open(CHATGPT_URL, new=2)


def start_all():
    status_var.set("Iniciando...")
    root.update_idletasks()
    ok_bridge, msg_bridge = start_bridge(cfg)
    open_chatgpt()
    ok_ag, msg_ag = start_antigravity(cfg)
    refresh_status()
    if not ok_ag:
        messagebox.showwarning("Antigravity no localizado", msg_ag + "\n\nSelecciona su .exe una sola vez con el botón 'Elegir Antigravity'.")
    if not ok_bridge:
        messagebox.showwarning("Bridge", msg_bridge)


def refresh_status():
    bridge = "ACTIVO" if bridge_running() else "DETENIDO"
    token = "OK" if token_exists() else "FALTA"
    daemon = cfg.get("daemon_path", "")
    ag = cfg.get("antigravity_path", "")
    daemon_text = os.path.basename(daemon) if daemon and os.path.isfile(daemon) else "auto"
    ag_text = os.path.basename(ag) if ag and os.path.isfile(ag) else "auto"
    status_var.set(f"Bridge: {bridge}   |   Token: {token}\nDaemon: {daemon_text}   |   Antigravity: {ag_text}")


cfg = load_config()
root = tk.Tk()
root.title("Cerebro + Manos")
root.geometry("520x275")
root.resizable(False, False)

tk.Label(root, text="Cerebro + Manos", font=("Segoe UI", 20, "bold")).pack(pady=(20, 5))
tk.Label(root, text="Un doble clic abre ChatGPT, Antigravity y mantiene /inv_chatgpt activo.", font=("Segoe UI", 10)).pack(pady=(0, 16))
tk.Button(root, text="INICIAR TODO", font=("Segoe UI", 12, "bold"), width=24, height=2, command=start_all).pack()

status_var = tk.StringVar()
tk.Label(root, textvariable=status_var, font=("Consolas", 9), justify="center").pack(pady=12)

buttons = tk.Frame(root)
buttons.pack()
tk.Button(buttons, text="Elegir Antigravity", command=lambda: choose_antigravity(cfg)).grid(row=0, column=0, padx=5)
tk.Button(buttons, text="Elegir daemon", command=lambda: choose_daemon(cfg)).grid(row=0, column=1, padx=5)
tk.Button(buttons, text="Abrir ChatGPT", command=open_chatgpt).grid(row=0, column=2, padx=5)

refresh_status()
root.after(400, start_all)
root.mainloop()
