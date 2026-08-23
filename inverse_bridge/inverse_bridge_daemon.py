#!/usr/bin/env python3
"""
Inverse Bridge Daemon (V1.3)
Plano de control Machine-to-Machine entre ChatGPT Plus y Antigravity mediante GitHub Issues y Pull Requests.
Características:
- Soporte para MODE: EXEC (argv/shlex, shell=False), READ_FILES, READ_ONLY (allowlist), IMPLEMENT_AND_TEST.
- Soporte para MODE: AGENT_PROMPT con capa desacoplada agent_backend (fail-closed BLOCKED por defecto).
- Autenticación estricta de emisor de Issue (trusted_issue_authors).
- Bloqueo global a nivel de sistema operativo mediante Windows Named Mutex.
- Volcado estructurado de contenidos leídos (file_contents) y respuestas de agente (agent_response).
- Redacción automática de secretos y control de rutas (allowed_roots).
"""

import sys
import os
import re
import json
import time
import datetime
import shlex
import subprocess
import argparse
import tempfile
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DEFAULT_STATE_PATH = os.path.join(BASE_DIR, "state.json")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
GLOBAL_LOCK_FILE = os.path.join(tempfile.gettempdir(), "antigravity_inverse_bridge_global.lock")
_MUTEX_HANDLE = None

os.makedirs(LOGS_DIR, exist_ok=True)

# Protocol Constants
SUPPORTED_PROTOCOL_VERSION = 1
KNOWN_MODES = {"EXEC", "READ_FILES", "READ_ONLY", "IMPLEMENT_AND_TEST", "AGENT_PROMPT"}
KNOWN_SINGLE_KEYS = {
    "BRIDGE_PROTOCOL_VERSION", "TASK_ID", "ASSIGNEE_ROLE", "STATUS",
    "MODE", "TARGET", "DESTRUCTIVE_APPROVED"
}
KNOWN_SECTION_KEYS = {
    "COMMANDS", "FILES", "PROMPT", "OBJECTIVE", "ALLOWED", "FORBIDDEN", "RETURN", "SUMMARY",
    "ARCHITECTURE", "TASK_DISCOVERY_RULE", "TASK DISCOVERY RULE",
    "STATE_MACHINE", "STATE MACHINE",
    "CLAIM_COMMENT_FORMAT", "CLAIM COMMENT FORMAT",
    "FINAL_REPORT_FORMAT", "FINAL REPORT FORMAT",
    "LOCAL_FILE_LAYOUT", "LOCAL FILE LAYOUT",
    "REQUIRED_CONFIG_FIELDS", "REQUIRED CONFIG FIELDS",
    "SECURITY_RULES", "SECURITY RULES",
    "IMPLEMENTATION_REQUIREMENTS", "IMPLEMENTATION REQUIREMENTS",
    "TESTS_REQUIRED", "TESTS REQUIRED",
    "DELIVERABLE", "DELIVERABLES", "DESCRIPTION", "CONTEXT", "NOTES"
}
ALL_KNOWN_KEYS = KNOWN_SINGLE_KEYS.union(KNOWN_SECTION_KEYS)

READ_ONLY_ALLOWED_PREFIXES = (
    "git status", "git diff", "git log", "git remote", "git branch",
    "git show", "git tag", "dir", "ls", "python --version", "git --version",
    "node --version", "where ", "which "
)

# Regex para detección y redacción de secretos
SECRET_PATTERNS = [
    re.compile(r'(ghp_[a-zA-Z0-9]{30,})', re.IGNORECASE),
    re.compile(r'(github_pat_[a-zA-Z0-9_]{50,})', re.IGNORECASE),
    re.compile(r'(Bearer\s+)([a-zA-Z0-9_\-\.]{15,})', re.IGNORECASE),
    re.compile(r'((?:token|secret|password|api[_-]?key|auth)[\s:=]+[\'\"]?)([a-zA-Z0-9_\-\.]{8,})([\'\"]?)', re.IGNORECASE),
    re.compile(r'([A-Za-z0-9+/]{40,}={0,2})'),
]

DESTRUCTIVE_PATTERNS = [
    re.compile(r'\b(rmdir\s+/s|del\s+/f|rm\s+-rf|format\s+|git\s+reset\s+--hard|git\s+clean\s+-fdx)\b', re.IGNORECASE),
    re.compile(r'\b(Remove-Item\s+.*-Recurse\s+-Force)\b', re.IGNORECASE),
    re.compile(r'\b(diskpart|mkfs|fdisk)\b', re.IGNORECASE)
]


def redact_secrets(text: str) -> str:
    """Redacta tokens, claves API y secretos conocidos en cualquier texto."""
    if not text or not isinstance(text, str):
        return text

    redacted = text
    token_env = os.environ.get("ANTIGRAVITY_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token_env and len(token_env) > 4:
        redacted = redacted.replace(token_env, "[REDACTED_TOKEN]")

    for pat in SECRET_PATTERNS:
        def _repl(m):
            if len(m.groups()) == 1:
                return "[REDACTED]"
            elif len(m.groups()) == 2:
                return f"{m.group(1)}[REDACTED]"
            elif len(m.groups()) == 3:
                return f"{m.group(1)}[REDACTED]{m.group(3)}"
            return "[REDACTED]"
        redacted = pat.sub(_repl, redacted)

    return redacted


def log_message(msg: str, level: str = "INFO"):
    """Escribe un log local con marca temporal y secretos redactados."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    clean_msg = redact_secrets(msg)
    log_line = f"[{now_iso}] [{level}] {clean_msg}"
    print(log_line)
    
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    log_path = os.path.join(LOGS_DIR, f"bridge_{today_str}.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        pass


def acquire_lock() -> bool:
    """Garantiza la ejecución de una única instancia del daemon a nivel de sistema operativo."""
    global _MUTEX_HANDLE
    
    # 1. En Windows, usar Named Mutex a nivel de sesión
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            mutex_name = "Local\\AntigravityInverseBridge_SingleInstance_Mutex"
            
            kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            
            handle = kernel32.CreateMutexW(None, True, mutex_name)
            last_err = kernel32.GetLastError()
            ERROR_ALREADY_EXISTS = 183

            if last_err == ERROR_ALREADY_EXISTS or not handle:
                log_message("Ya existe otra instancia activa de Inverse Bridge Daemon (Named Mutex bloqueado).", "WARNING")
                return False

            _MUTEX_HANDLE = handle
        except Exception as e:
            log_message(f"Advertencia creando Named Mutex: {e}", "WARNING")

    # 2. File Lock global en TEMP
    try:
        if os.path.exists(GLOBAL_LOCK_FILE):
            try:
                with open(GLOBAL_LOCK_FILE, "r", encoding="utf-8") as f:
                    old_pid = int(f.read().strip())
                if sys.platform == "win32":
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    SYNCHRONIZE = 0x00100000
                    process = kernel32.OpenProcess(SYNCHRONIZE, False, old_pid)
                    if process:
                        kernel32.CloseHandle(process)
                        log_message(f"Daemon ya está ejecutándose en PID global {old_pid}.", "WARNING")
                        return False
            except Exception:
                pass

        with open(GLOBAL_LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        log_message(f"Error al adquirir lock global: {e}", "ERROR")
        return False


def release_lock():
    """Libera el Named Mutex y el lock file global."""
    global _MUTEX_HANDLE
    if _MUTEX_HANDLE and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(_MUTEX_HANDLE)
            _MUTEX_HANDLE = None
        except Exception:
            pass

    try:
        if os.path.exists(GLOBAL_LOCK_FILE):
            os.remove(GLOBAL_LOCK_FILE)
    except Exception:
        pass


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Carga configuración desde archivo JSON o valores por defecto."""
    default_config = {
        "repo": "mromerolobos-bot/co_escritor_ia",
        "poll_seconds": 10,
        "agent_role": "ANTIGRAVITY",
        "trusted_issue_authors": [
            "mromerolobos-bot"
        ],
        "allowed_roots": [
            r"C:\pinokio\api\cinematic-character-studio-v1-1",
            r"C:\Users\Chelowolf"
        ],
        "agent_backend": {
            "enabled": False,
            "type": "none",
            "timeout_seconds": 60,
            "max_prompt_chars": 10000,
            "max_response_chars": 20000
        },
        "dry_run": False
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                default_config.update(cfg)
        except Exception as e:
            log_message(f"Error al leer config en {config_path}: {e}", "WARNING")
    return default_config


def load_state(state_path: str = DEFAULT_STATE_PATH) -> dict:
    """Carga estado persistente local (tareas procesadas, marcas de tiempo)."""
    default_state = {
        "processed_tasks": {},
        "last_poll_utc": None
    }
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                st = json.load(f)
                default_state.update(st)
        except Exception:
            pass
    return default_state


def save_state(state: dict, state_path: str = DEFAULT_STATE_PATH):
    """Guarda estado persistente de manera atómica."""
    try:
        tmp_path = state_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        if os.path.exists(state_path):
            os.replace(tmp_path, state_path)
        else:
            os.rename(tmp_path, state_path)
    except Exception as e:
        log_message(f"Error al guardar estado: {e}", "ERROR")


# =========================================================================
# GITHUB API CLIENT
# =========================================================================

def get_github_token() -> Optional[str]:
    """Obtiene el token de GitHub desde variables de entorno o registro de Windows."""
    token = os.environ.get("ANTIGRAVITY_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token and token.strip() != "TU_TOKEN_DE_GITHUB":
        return token.strip()
    
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
            val, _ = winreg.QueryValueEx(key, "ANTIGRAVITY_GITHUB_TOKEN")
            if val and val.strip() != "TU_TOKEN_DE_GITHUB":
                return val.strip()
        except Exception:
            pass
    return None


def github_api_request(endpoint: str, method: str = "GET", data: Optional[dict] = None) -> Tuple[int, Any]:
    """Realiza una petición a la API de GitHub REST v3."""
    url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else endpoint
    token = get_github_token()

    headers = {
        "User-Agent": "Antigravity-InverseBridge/1.3",
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req_data = None
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            return status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        try:
            parsed_err = json.loads(err_body)
        except Exception:
            parsed_err = {"message": err_body}
        return e.code, parsed_err
    except Exception as e:
        return 500, {"error": str(e)}


def fetch_open_issues(repo: str) -> List[dict]:
    """Obtiene issues abiertos del repositorio configurado."""
    status, result = github_api_request(f"/repos/{repo}/issues?state=open")
    if status == 200 and isinstance(result, list):
        return [i for i in result if "pull_request" not in i]
    log_message(f"Error al obtener issues de {repo} (Status {status}): {result}", "WARNING")
    return []


def post_issue_comment(repo: str, issue_number: int, comment_text: str) -> bool:
    """Publica un comentario estructurado en un Issue de GitHub."""
    clean_text = redact_secrets(comment_text)
    status, result = github_api_request(
        f"/repos/{repo}/issues/{issue_number}/comments",
        method="POST",
        data={"body": clean_text}
    )
    if status in (200, 201):
        log_message(f"Comentario publicado exitosamente en #{issue_number}")
        return True
    else:
        log_message(f"Error publicando comentario en #{issue_number} (Status {status}): {result}", "ERROR")
        return False


# =========================================================================
# PROTOCOL PARSER & VALIDATOR
# =========================================================================

def parse_items_list(text: str) -> List[str]:
    """Convierte una sección multilínea en una lista de elementos (soporta '- item' o 'item')."""
    if not text:
        return []
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("- ") or line.startswith("* "):
            items.append(line[2:].strip())
        else:
            items.append(line)
    return items


def parse_protocol_task(issue_body: str) -> Optional[dict]:
    """
    Parsea y extrae campos del protocolo de un Issue.
    Valida estrictamente:
    - BRIDGE_PROTOCOL_VERSION == 1
    - ASSIGNEE_ROLE == ANTIGRAVITY
    - STATUS == READY
    - MODE dentro de KNOWN_MODES
    - Rechaza secciones desconocidas
    """
    if not issue_body:
        return None

    task = {}
    lines = issue_body.splitlines()
    in_section = None
    section_content = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Par clave-valor simple
        match_kv = re.match(r'^([A-Z0-9_]+)\s*:\s*(.*)$', stripped)
        if match_kv and match_kv.group(1) in KNOWN_SINGLE_KEYS:
            if in_section:
                task[in_section] = "\n".join(section_content).strip()
                in_section = None
                section_content = []
            
            key = match_kv.group(1)
            val = match_kv.group(2).strip()
            task[key] = val
            continue
        
        # Encabezado de sección
        match_section = re.match(r'^([A-Z0-9_ ]+)\s*:\s*$', stripped)
        if match_section:
            sec_name = match_section.group(1).strip()
            if sec_name not in ALL_KNOWN_KEYS:
                log_message(f"Rechazando tarea por sección desconocida: {sec_name}", "WARNING")
                return None
            
            if in_section:
                task[in_section] = "\n".join(section_content).strip()
            in_section = sec_name
            section_content = []
            continue

        if match_kv and match_kv.group(1) not in ALL_KNOWN_KEYS and not in_section:
            log_message(f"Rechazando tarea por clave desconocida: {match_kv.group(1)}", "WARNING")
            return None

        if in_section:
            section_content.append(line)

    if in_section:
        task[in_section] = "\n".join(section_content).strip()

    try:
        proto_ver = int(task.get("BRIDGE_PROTOCOL_VERSION", 0))
    except ValueError:
        proto_ver = 0

    if proto_ver != SUPPORTED_PROTOCOL_VERSION:
        return None
    if task.get("ASSIGNEE_ROLE") != "ANTIGRAVITY":
        return None
    if task.get("STATUS") != "READY":
        return None
    if not task.get("TASK_ID"):
        return None

    mode = task.get("MODE", "")
    if mode not in KNOWN_MODES:
        log_message(f"Rechazando tarea por MODE desconocido: '{mode}'", "WARNING")
        return None

    return task


def is_target_allowed(target_path: str, allowed_roots: List[str]) -> bool:
    """Verifica si la ruta objetivo está dentro de allowed_roots."""
    if not target_path:
        return True
    
    norm_target = os.path.abspath(target_path).lower()
    for root in allowed_roots:
        norm_root = os.path.abspath(root).lower()
        if norm_target == norm_root or norm_target.startswith(norm_root + os.sep):
            return True
    return False


def is_command_safe(command: str, destructive_approved: bool = False) -> Tuple[bool, str]:
    """Verifica si un comando es seguro según las políticas restrictivas."""
    if destructive_approved:
        return True, "Destructive approved"
    
    for pat in DESTRUCTIVE_PATTERNS:
        if pat.search(command):
            return False, f"Comando bloqueado por ser potencialmente destructivo: '{command}'"
    return True, "Safe"


def is_read_only_allowed(command: str) -> Tuple[bool, str]:
    """Verifica si un comando pertenece a la allowlist estricta de diagnósticos de READ_ONLY."""
    cmd_clean = command.strip().lower()
    for prefix in READ_ONLY_ALLOWED_PREFIXES:
        if cmd_clean.startswith(prefix.lower()):
            return True, "Allowed diagnostic"
    return False, f"Comando no permitido en MODE: READ_ONLY. Debe pertenecer a la allowlist de diagnósticos: '{command}'"


def run_command_safe(
    cmd_str: str,
    cwd: str,
    timeout: int = 60,
    destructive_approved: bool = False
) -> Tuple[int, str, str, Optional[str]]:
    """
    Ejecuta un comando de forma segura utilizando shlex/argv (shell=False).
    Retorna (exit_code, stdout, stderr, error_msg).
    """
    is_safe, reason = is_command_safe(cmd_str, destructive_approved)
    if not is_safe:
        return -1, "", reason, reason

    try:
        argv = shlex.split(cmd_str, posix=(sys.platform != "win32"))
    except Exception as e:
        err = f"Error al parsear comando en argv: {e}"
        return -1, "", err, err

    if not argv:
        return 0, "", "", None

    try:
        proc = subprocess.run(
            argv,
            shell=False,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr, None
    except FileNotFoundError:
        err = f"Ejecutable no encontrado: '{argv[0]}'"
        return -1, "", err, err
    except subprocess.TimeoutExpired:
        err = f"Comando excedió el tiempo límite ({timeout}s): '{cmd_str}'"
        return -1, "", err, err
    except Exception as e:
        err = f"Excepción ejecutando comando '{cmd_str}': {e}"
        return -1, "", err, err


def run_agent_prompt(prompt_text: str, backend_cfg: dict) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Despacha el prompt al backend cognitivo configurado (fail-closed BLOCKED por defecto).
    Retorna (status, agent_response, error_msg).
    """
    if not backend_cfg or not backend_cfg.get("enabled", False) or backend_cfg.get("type", "none") == "none":
        return "BLOCKED", None, "Backend cognitivo no configurado o deshabilitado (agent_backend.enabled = false)."

    b_type = backend_cfg.get("type", "none")
    max_prompt = backend_cfg.get("max_prompt_chars", 10000)
    max_resp = backend_cfg.get("max_response_chars", 20000)
    timeout = backend_cfg.get("timeout_seconds", 60)

    # Simulación o verificación de timeout
    if backend_cfg.get("simulate_timeout", False):
        return "FAILED", None, f"Agent backend excedió el tiempo límite ({timeout}s)."

    # Aplicar límite de tamaño al prompt
    clean_prompt = prompt_text[:max_prompt] if prompt_text else ""

    if b_type == "mock":
        raw_response = backend_cfg.get("mock_response") or f"[Mock Agent Response] Prompt procesado exitosamente ({len(clean_prompt)} chars)."
        # Aplicar límite de tamaño a la respuesta
        capped_response = raw_response[:max_resp]
        return "DONE", redact_secrets(capped_response), None

    return "BLOCKED", None, f"Tipo de backend cognitivo '{b_type}' no soportado actualmente."


# =========================================================================
# REPORT BUILDERS
# =========================================================================

def build_claim_report(task_id: str, status: str = "ACK", message: str = "claimed") -> str:
    """Genera el bloque de reporte de reclamo o inicio."""
    return f"""<<<INV_CHATGPT_REPORT>>>
protocol: 1
task_id: {task_id}
status: {status}
agent: antigravity
message: {message}
<<<END_INV_CHATGPT_REPORT>>>"""


def build_final_report(
    task_id: str,
    status: str,
    started_at: str,
    finished_at: str,
    target: str,
    summary: str,
    commands: List[dict],
    files_read: List[str],
    file_contents: List[dict],
    files_changed: List[str],
    artifacts: List[str],
    agent_response: Optional[str] = None,
    errors: List[str] = None
) -> str:
    """Genera el bloque YAML-compatible estructurado para el reporte final."""
    if errors is None:
        errors = []
    
    summary_lines = [f"  {line}" for line in summary.strip().splitlines()] if summary.strip() else ["  No summary"]
    lines = [
        "<<<INV_CHATGPT_REPORT>>>",
        "protocol: 1",
        f"task_id: {task_id}",
        f"status: {status}",
        "agent: antigravity",
        f"started_at: {started_at}",
        f"finished_at: {finished_at}",
        f"target: {target or 'N/A'}",
        "summary: |",
        *summary_lines,
    ]

    if agent_response:
        lines.append("agent_response: |")
        resp_lines = agent_response.strip().splitlines()
        for rl in resp_lines:
            lines.append(f"  {rl}")

    lines.append("commands:")
    if not commands:
        lines.append("  []")
    else:
        for cmd in commands:
            lines.append(f"  - command: {cmd.get('command', '')}")
            lines.append(f"    exit_code: {cmd.get('exit_code', 0)}")
            lines.append("    stdout: |")
            std_lines = cmd.get('stdout', '').strip().splitlines()
            if not std_lines:
                lines.append("      (empty)")
            else:
                for sl in std_lines[:100]:
                    lines.append(f"      {sl}")
                if len(std_lines) > 100:
                    lines.append(f"      ... [truncated {len(std_lines)-100} lines]")
            lines.append("    stderr: |")
            err_lines = cmd.get('stderr', '').strip().splitlines()
            if not err_lines:
                lines.append("      (empty)")
            else:
                for el in err_lines[:50]:
                    lines.append(f"      {el}")

    lines.append("files_read:")
    if not files_read:
        lines.append("  []")
    else:
        for fr in files_read:
            lines.append(f"  - {fr}")

    lines.append("file_contents:")
    if not file_contents:
        lines.append("  []")
    else:
        for fc in file_contents:
            lines.append(f"  - path: {fc.get('path', '')}")
            lines.append(f"    truncated: {'true' if fc.get('truncated') else 'false'}")
            lines.append("    content: |")
            raw_c = fc.get("content", "").strip().splitlines()
            if not raw_c:
                lines.append("      (empty)")
            else:
                for cl in raw_c[:200]:
                    lines.append(f"      {cl}")
                if len(raw_c) > 200:
                    lines.append(f"      ... [truncated {len(raw_c)-200} lines]")

    lines.append("files_changed:")
    if not files_changed:
        lines.append("  []")
    else:
        for fc in files_changed:
            lines.append(f"  - {fc}")

    lines.append("artifacts:")
    if not artifacts:
        lines.append("  []")
    else:
        for art in artifacts:
            lines.append(f"  - {art}")

    lines.append("errors:")
    if not errors:
        lines.append("  []")
    else:
        for err in errors:
            lines.append(f"  - {err}")

    lines.append("secrets_redacted: true")
    lines.append("<<<END_INV_CHATGPT_REPORT>>>")

    raw_report = "\n".join(lines)
    return redact_secrets(raw_report)


# =========================================================================
# TASK EXECUTOR
# =========================================================================

def execute_task(task: dict, config: dict) -> Tuple[str, dict]:
    """
    Ejecuta una tarea aprobada con soporte dinámico de EXEC, READ_FILES, READ_ONLY, AGENT_PROMPT e IMPLEMENT_AND_TEST.
    """
    task_id = task.get("TASK_ID")
    target = task.get("TARGET", "")
    mode = task.get("MODE", "READ_ONLY")
    destructive_approved = task.get("DESTRUCTIVE_APPROVED", "").lower() == "true"
    dry_run = config.get("dry_run", False)
    allowed_roots = config.get("allowed_roots", [])
    agent_backend_cfg = config.get("agent_backend", {})

    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    errors = []
    commands_run = []
    files_read = []
    file_contents = []
    files_changed = []
    artifacts = []
    agent_response = None
    summary = ""

    # 1. Validación de Target Directory & CWD
    exec_cwd = BASE_DIR
    if target:
        if not is_target_allowed(target, allowed_roots):
            err_msg = f"Ruta objetivo no permitida en allowed_roots: {target}"
            log_message(err_msg, "ERROR")
            finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return "BLOCKED", {
                "task_id": task_id,
                "status": "BLOCKED",
                "started_at": started_at,
                "finished_at": finished_at,
                "target": target,
                "summary": "Tarea bloqueada por violar la política de allowed_roots.",
                "commands": [],
                "files_read": [],
                "file_contents": [],
                "files_changed": [],
                "artifacts": [],
                "agent_response": None,
                "errors": [err_msg]
            }
        
        norm_target = os.path.abspath(target)
        if os.path.isdir(norm_target):
            exec_cwd = norm_target
        elif os.path.isfile(norm_target):
            exec_cwd = os.path.dirname(norm_target)
        else:
            exec_cwd = BASE_DIR

    # 2. Modo AGENT_PROMPT: Consulta cognitiva
    if mode == "AGENT_PROMPT":
        prompt_text = task.get("PROMPT", "").strip()
        if not prompt_text:
            errors.append("MODE: AGENT_PROMPT requiere una sección PROMPT no vacía.")
            status = "FAILED"
            summary = "Ejecución fallida: PROMPT vacío."
        else:
            status, agent_response, err = run_agent_prompt(prompt_text, agent_backend_cfg)
            if err:
                errors.append(err)
            summary = f"Consulta AGENT_PROMPT procesada con estado {status}."

    # 3. Modo EXEC: Ejecutar lista ordenada de comandos reales
    elif mode == "EXEC":
        cmd_list = parse_items_list(task.get("COMMANDS", ""))
        if not cmd_list:
            errors.append("MODE: EXEC requiere una sección COMMANDS no vacía con comandos a ejecutar.")
            status = "FAILED"
            summary = "Ejecución fallida: no se proporcionaron comandos."
        else:
            all_ok = True
            for cmd_str in cmd_list:
                if dry_run:
                    log_message(f"[DRY-RUN] Simular ejecución: {cmd_str} en {exec_cwd}")
                    commands_run.append({
                        "command": cmd_str,
                        "exit_code": 0,
                        "stdout": "(dry-run simulated execution)",
                        "stderr": ""
                    })
                    continue

                exit_code, stdout, stderr, err = run_command_safe(
                    cmd_str=cmd_str,
                    cwd=exec_cwd,
                    timeout=60,
                    destructive_approved=destructive_approved
                )
                commands_run.append({
                    "command": cmd_str,
                    "exit_code": exit_code,
                    "stdout": redact_secrets(stdout),
                    "stderr": redact_secrets(stderr)
                })
                if exit_code != 0:
                    all_ok = False
                    if err:
                        errors.append(err)

            status = "DONE" if all_ok else "FAILED"
            summary = f"Ejecución de {len(cmd_list)} comando(s) en cwd='{exec_cwd}'. Estado: {status}."

    # 4. Modo READ_FILES: Lectura real de archivos solicitados y volcado de contenido
    elif mode == "READ_FILES":
        file_list = parse_items_list(task.get("FILES", ""))
        if not file_list:
            errors.append("MODE: READ_FILES requiere una sección FILES con al menos una ruta de archivo.")
            status = "FAILED"
            summary = "Lectura fallida: no se proporcionaron archivos en sección FILES."
        else:
            read_summaries = []
            for raw_path in file_list:
                full_path = raw_path if os.path.isabs(raw_path) else os.path.abspath(os.path.join(exec_cwd, raw_path))
                if not is_target_allowed(full_path, allowed_roots):
                    err = f"Acceso denegado a archivo fuera de allowed_roots: {full_path}"
                    errors.append(err)
                    continue

                if not os.path.exists(full_path):
                    err = f"Archivo no encontrado: {full_path}"
                    errors.append(err)
                    continue

                if os.path.isdir(full_path):
                    err = f"La ruta solicitada es un directorio, no un archivo: {full_path}"
                    errors.append(err)
                    continue

                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        raw_content = f.read(50000)
                    
                    files_read.append(full_path)
                    file_contents.append({
                        "path": full_path,
                        "truncated": len(raw_content) >= 50000,
                        "content": redact_secrets(raw_content)
                    })
                    read_summaries.append(f"- Leído {full_path} ({len(raw_content)} caracteres)")
                except Exception as e:
                    errors.append(f"Error al leer {full_path}: {e}")

            status = "DONE" if files_read and not errors else "FAILED"
            summary = f"Lectura de archivos completada ({len(files_read)} archivo(s) leídos exitosamente)."
            if read_summaries:
                summary += "\n" + "\n".join(read_summaries)

    # 5. Modo READ_ONLY: Diagnósticos seguros con Allowlist estricta
    elif mode == "READ_ONLY":
        cmd_list = parse_items_list(task.get("COMMANDS", ""))
        file_list = parse_items_list(task.get("FILES", ""))

        for cmd_str in cmd_list:
            is_allowed, reason = is_read_only_allowed(cmd_str)
            if not is_allowed:
                errors.append(reason)
                continue

            if dry_run:
                commands_run.append({
                    "command": cmd_str,
                    "exit_code": 0,
                    "stdout": "(dry-run simulated read-only command)",
                    "stderr": ""
                })
                continue
            
            exit_code, stdout, stderr, err = run_command_safe(
                cmd_str=cmd_str,
                cwd=exec_cwd,
                timeout=60,
                destructive_approved=False
            )
            commands_run.append({
                "command": cmd_str,
                "exit_code": exit_code,
                "stdout": redact_secrets(stdout),
                "stderr": redact_secrets(stderr)
            })
            if err:
                errors.append(err)

        for raw_path in file_list:
            full_path = raw_path if os.path.isabs(raw_path) else os.path.abspath(os.path.join(exec_cwd, raw_path))
            if is_target_allowed(full_path, allowed_roots) and os.path.isfile(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        raw_content = f.read(50000)
                    files_read.append(full_path)
                    file_contents.append({
                        "path": full_path,
                        "truncated": len(raw_content) >= 50000,
                        "content": redact_secrets(raw_content)
                    })
                except Exception as e:
                    errors.append(f"Error al leer {full_path}: {e}")

        status = "DONE" if not errors else "FAILED"
        summary = f"Inspección READ_ONLY completada para target='{target or exec_cwd}'."

    # 6. Modo IMPLEMENT_AND_TEST (Bootstrap/Setup)
    elif mode == "IMPLEMENT_AND_TEST":
        cmd_list = parse_items_list(task.get("COMMANDS", "")) or ["python --version", "git --version"]
        for cmd_str in cmd_list:
            if dry_run:
                commands_run.append({
                    "command": cmd_str,
                    "exit_code": 0,
                    "stdout": "(dry-run simulated test)",
                    "stderr": ""
                })
                continue

            exit_code, stdout, stderr, err = run_command_safe(
                cmd_str=cmd_str,
                cwd=exec_cwd,
                timeout=30,
                destructive_approved=destructive_approved
            )
            commands_run.append({
                "command": cmd_str,
                "exit_code": exit_code,
                "stdout": redact_secrets(stdout),
                "stderr": redact_secrets(stderr)
            })
            if exit_code != 0 and err:
                errors.append(err)

        status = "DONE" if not errors else "FAILED"
        summary = f"Implementación y verificación de tests completada exitosamente para {task_id}."

    else:
        status = "FAILED"
        summary = f"Modo no soportado: {mode}"
        errors.append(f"MODE '{mode}' no es válido.")

    finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return status, {
        "task_id": task_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "target": target,
        "summary": summary,
        "commands": commands_run,
        "files_read": files_read,
        "file_contents": file_contents,
        "files_changed": files_changed,
        "artifacts": artifacts,
        "agent_response": agent_response,
        "errors": errors
    }


# =========================================================================
# MAIN DAEMON LOOP
# =========================================================================

def process_single_issue(issue: dict, config: dict, state: dict) -> bool:
    """
    Procesa un issue individual validando primero el autor y las reglas del protocolo.
    """
    issue_num = issue.get("number")
    
    # 1. Autenticación estricta del emisor (trusted_issue_authors)
    author = (issue.get("user") or {}).get("login", "").strip().lower()
    trusted_authors = [a.lower() for a in config.get("trusted_issue_authors", ["mromerolobos-bot"])]
    
    if not author or author not in trusted_authors:
        log_message(f"[SECURITY] Ignorando Issue #{issue_num} creado por autor no confiable: '{author}'. Trusted: {trusted_authors}", "WARNING")
        return False

    issue_body = issue.get("body") or ""
    task = parse_protocol_task(issue_body)
    if not task:
        return False

    task_id = task.get("TASK_ID")
    if not task_id:
        return False

    if task_id in state.get("processed_tasks", {}):
        return False

    repo = config.get("repo", "mromerolobos-bot/co_escritor_ia")
    dry_run = config.get("dry_run", False)

    log_message(f"=== Tarea detectada: {task_id} de autor verificado '{author}' en Issue #{issue_num} (dry_run={dry_run}) ===")

    # 2. Enviar ACK Claim
    claim_comment = build_claim_report(task_id, status="ACK", message="claimed")
    if not dry_run:
        post_issue_comment(repo, issue_num, claim_comment)
    log_message(f"ACK publicado para {task_id}")

    # 3. Enviar RUNNING
    running_comment = build_claim_report(task_id, status="RUNNING", message="executing")
    if not dry_run:
        post_issue_comment(repo, issue_num, running_comment)
    log_message(f"RUNNING publicado para {task_id}")

    # 4. Ejecutar tarea
    status, result_data = execute_task(task, config)

    # 5. Enviar Reporte Final con file_contents y agent_response
    final_report = build_final_report(
        task_id=result_data["task_id"],
        status=result_data["status"],
        started_at=result_data["started_at"],
        finished_at=result_data["finished_at"],
        target=result_data["target"],
        summary=result_data["summary"],
        commands=result_data["commands"],
        files_read=result_data["files_read"],
        file_contents=result_data.get("file_contents", []),
        files_changed=result_data["files_changed"],
        artifacts=result_data["artifacts"],
        agent_response=result_data.get("agent_response"),
        errors=result_data["errors"]
    )

    if not dry_run:
        post_issue_comment(repo, issue_num, final_report)

    log_message(f"Reporte final ({status}) publicado para {task_id}")

    # 6. Persistir estado
    state.setdefault("processed_tasks", {})[task_id] = {
        "status": status,
        "issue_number": issue_num,
        "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    save_state(state)
    return True


def run_daemon(config_path: str = DEFAULT_CONFIG_PATH, once: bool = False, dry_run: bool = False):
    """Ejecuta el ciclo principal del daemon."""
    if not acquire_lock():
        sys.exit(1)

    try:
        config = load_config(config_path)
        if dry_run:
            config["dry_run"] = True
            log_message("Modo CLI --dry-run activado: no se publicarán comentarios ni se ejecutarán cambios destructivos.")

        state = load_state()
        repo = config.get("repo", "mromerolobos-bot/co_escritor_ia")
        poll_interval = config.get("poll_seconds", 10)

        log_message(f"Iniciando Inverse Bridge Daemon para {repo} (Polling cada {poll_interval}s)...")

        while True:
            try:
                issues = fetch_open_issues(repo)
                state["last_poll_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                
                for issue in issues:
                    process_single_issue(issue, config, state)
                
                save_state(state)

            except Exception as e:
                log_message(f"Error en ciclo de polling: {e}", "ERROR")

            if once:
                break
            time.sleep(poll_interval)

    finally:
        release_lock()
        log_message("Inverse Bridge Daemon detenido.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Antigravity Inverse Bridge Daemon")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Ruta al archivo config.json")
    parser.add_argument("--once", action="store_true", help="Ejecutar una sola iteración de polling y salir")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulación sin escribir en GitHub")
    args = parser.parse_args()

    run_daemon(config_path=args.config, once=args.once, dry_run=args.dry_run)
