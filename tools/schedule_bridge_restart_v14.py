from pathlib import Path
import os
import subprocess
import sys
import tempfile
import textwrap

here = Path.cwd()
daemon = here / "inverse_bridge_daemon.py"
if not daemon.is_file():
    raise SystemExit(f"daemon not found in cwd: {daemon}")

parent_pid = os.getppid()
python_exe = sys.executable
watchdog = Path(tempfile.gettempdir()) / "inv_chatgpt_restart_v14_watchdog.py"
code = f'''import os, subprocess, sys, time
parent_pid = {parent_pid}
daemon = {str(daemon)!r}
python_exe = {python_exe!r}
time.sleep(5)
if sys.platform == "win32":
    subprocess.run(["taskkill", "/PID", str(parent_pid), "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
else:
    try:
        os.kill(parent_pid, 15)
    except OSError:
        pass
time.sleep(2)
flags = 0
if sys.platform == "win32":
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
subprocess.Popen([python_exe, daemon], cwd=os.path.dirname(daemon), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags)
'''
watchdog.write_text(code, encoding="utf-8")
flags = 0
if sys.platform == "win32":
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
subprocess.Popen([python_exe, str(watchdog)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags)
print(f"RESTART_SCHEDULED parent_pid={parent_pid} daemon={daemon}")
