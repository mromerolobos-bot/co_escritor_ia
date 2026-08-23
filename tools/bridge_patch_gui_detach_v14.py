from pathlib import Path
import sys

if len(sys.argv) < 2:
    raise SystemExit('usage: bridge_patch_gui_detach_v14.py <inverse_bridge_daemon.py> [test_bridge.py]')

daemon = Path(sys.argv[1])
text = daemon.read_text(encoding='utf-8')
old = '''def run_command_safe(\n    cmd_str: str,\n    cwd: str,\n    timeout: int = 60,\n    destructive_approved: bool = False\n) -> Tuple[int, str, str, Optional[str]]:\n    \"\"\"\n    Ejecuta un comando de forma segura utilizando shlex/argv (shell=False).\n    Retorna (exit_code, stdout, stderr, error_msg).\n    \"\"\"\n    is_safe, reason = is_command_safe(cmd_str, destructive_approved)\n    if not is_safe:\n        return -1, \"\", reason, reason\n\n    try:\n        argv = shlex.split(cmd_str, posix=(sys.platform != \"win32\"))\n    except Exception as e:\n        err = f\"Error al parsear comando en argv: {e}\"\n        return -1, \"\", err, err\n\n    if not argv:\n        return 0, \"\", \"\", None\n\n    try:\n        proc = subprocess.run(\n            argv,\n            shell=False,\n            cwd=cwd,\n            capture_output=True,\n            text=True,\n            timeout=timeout\n        )\n        return proc.returncode, proc.stdout, proc.stderr, None\n    except FileNotFoundError:\n        err = f\"Ejecutable no encontrado: '{argv[0]}'\"\n        return -1, \"\", err, err\n    except subprocess.TimeoutExpired:\n        err = f\"Comando excedió el tiempo límite ({timeout}s): '{cmd_str}'\"\n        return -1, \"\", err, err\n    except Exception as e:\n        err = f\"Excepción ejecutando comando '{cmd_str}': {e}\"\n        return -1, \"\", err, err\n'''
new = '''GUI_EXECUTABLES = {\n    \"notepad.exe\", \"notepad\", \"explorer.exe\", \"explorer\",\n    \"msedge.exe\", \"msedge\", \"chrome.exe\", \"chrome\",\n    \"firefox.exe\", \"firefox\", \"antigravity.exe\", \"antigravity\",\n}\n\n\ndef _strip_detach_prefix(cmd_str: str) -> Tuple[str, bool]:\n    stripped = cmd_str.strip()\n    if stripped.upper().startswith(\"DETACH:\"):\n        return stripped[len(\"DETACH:\"):].strip(), True\n    return cmd_str, False\n\n\ndef _is_gui_command(argv: List[str]) -> bool:\n    if not argv:\n        return False\n    exe = os.path.basename(argv[0]).lower()\n    return exe in GUI_EXECUTABLES\n\n\ndef run_command_safe(\n    cmd_str: str,\n    cwd: str,\n    timeout: int = 60,\n    destructive_approved: bool = False\n) -> Tuple[int, str, str, Optional[str]]:\n    \"\"\"\n    Ejecuta comandos con shell=False. Los comandos prefijados con DETACH: y una\n    allowlist pequeña de aplicaciones GUI conocidas se lanzan con Popen y retornan\n    inmediatamente para evitar bloquear el daemon esperando a que cierre una ventana.\n    Retorna (exit_code, stdout, stderr, error_msg).\n    \"\"\"\n    executable_cmd, explicit_detach = _strip_detach_prefix(cmd_str)\n    is_safe, reason = is_command_safe(executable_cmd, destructive_approved)\n    if not is_safe:\n        return -1, \"\", reason, reason\n\n    try:\n        argv = shlex.split(executable_cmd, posix=(sys.platform != \"win32\"))\n    except Exception as e:\n        err = f\"Error al parsear comando en argv: {e}\"\n        return -1, \"\", err, err\n\n    if not argv:\n        return 0, \"\", \"\", None\n\n    detached = explicit_detach or _is_gui_command(argv)\n    try:\n        if detached:\n            creationflags = 0\n            if sys.platform == \"win32\":\n                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS\n            proc = subprocess.Popen(\n                argv,\n                shell=False,\n                cwd=cwd,\n                stdin=subprocess.DEVNULL,\n                stdout=subprocess.DEVNULL,\n                stderr=subprocess.DEVNULL,\n                close_fds=True,\n                creationflags=creationflags,\n            )\n            return 0, f\"DETACHED pid={proc.pid}\", \"\", None\n\n        proc = subprocess.run(\n            argv,\n            shell=False,\n            cwd=cwd,\n            capture_output=True,\n            text=True,\n            timeout=timeout\n        )\n        return proc.returncode, proc.stdout, proc.stderr, None\n    except FileNotFoundError:\n        err = f\"Ejecutable no encontrado: '{argv[0]}'\"\n        return -1, \"\", err, err\n    except subprocess.TimeoutExpired:\n        err = f\"Comando excedió el tiempo límite ({timeout}s): '{executable_cmd}'\"\n        return -1, \"\", err, err\n    except Exception as e:\n        err = f\"Excepción ejecutando comando '{executable_cmd}': {e}\"\n        return -1, \"\", err, err\n'''
if old not in text:
    raise SystemExit('expected run_command_safe block not found; refusing to patch')
text = text.replace(old, new, 1)
text = text.replace('Inverse Bridge Daemon (V1.3)', 'Inverse Bridge Daemon (V1.4)', 1)
text = text.replace('Antigravity-InverseBridge/1.3', 'Antigravity-InverseBridge/1.4')
daemon.write_text(text, encoding='utf-8')
print('PATCHED:', daemon)

if len(sys.argv) >= 3:
    tests = Path(sys.argv[2])
    t = tests.read_text(encoding='utf-8')
    marker = 'if __name__ == "__main__":'
    additions = r'''

    def test_detach_prefix_returns_immediately(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            code, out, err, problem = bridge.run_command_safe(
                'DETACH: python -c "import time; time.sleep(3)"', td, timeout=1
            )
            self.assertEqual(code, 0)
            self.assertIsNone(problem)
            self.assertIn('DETACHED pid=', out)

    def test_known_gui_command_is_classified_for_detach(self):
        self.assertTrue(bridge._is_gui_command(['notepad.exe', 'x.txt']))
        self.assertTrue(bridge._is_gui_command(['explorer.exe', '.']))
        self.assertFalse(bridge._is_gui_command(['python', '--version']))
'''
    if 'test_detach_prefix_returns_immediately' not in t:
        if marker not in t:
            raise SystemExit('test marker not found; daemon patched but tests unchanged')
        t = t.replace(marker, additions + '\n\n' + marker, 1)
        tests.write_text(t, encoding='utf-8')
        print('TESTS_PATCHED:', tests)
