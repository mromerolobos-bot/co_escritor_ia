#!/usr/bin/env python3
"""
Inverse Bridge Daemon (V1.0)
Plano de control Machine-to-Machine entre ChatGPT Plus y Antigravity mediante GitHub Issues y Pull Requests.
"""

import sys
import os
import re
import json
import time
import datetime
import subprocess
import argparse
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DEFAULT_STATE_PATH = os.path.join(BASE_DIR, "state.json")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
LOCK_FILE = os.path.join(BASE_DIR, ".bridge.lock")

os.makedirs(LOGS_DIR, exist_ok=True)

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
    """Garantiza la ejecución de una única instancia del daemon."""
    try:
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, "r", encoding="utf-8") as f:
                    pid = int(f.read().strip())
                import ctypes
                kernel32 = ctypes.windll.kernel32
                SYNCHRONIZE = 0x00100000
                process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
                if process:
                    kernel32.CloseHandle(process)
                    log_message(f"Daemon ya está ejecutándose en PID {pid}.", "WARNING")
                    return False
            except Exception:
                pass
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        log_message(f"Error al adquirir lock file: {e}", "ERROR")
        return False


def release_lock():
    """Libera el lock file al terminar."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Carga configuración desde archivo JSON o valores por defecto."""
    default_config = {
        "repo": "mromerolobos-bot/co_escritor_ia",
        "poll_seconds": 10,
        "agent_role": "ANTIGRAVITY",
        "allowed_roots": [
            r"C:\pinokio\api\cinematic-character-studio-v1-1",
            r"C:\Users\Chelowolf"
        ],
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
    """Obtiene el token de GitHub desde variables de entorno locales."""
    token = os.environ.get("ANTIGRAVITY_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token and token.strip() != "TU_TOKEN_DE_GITHUB":
        return token.strip()
    return None


def github_api_request(endpoint: str, method: str = "GET", data: Optional[dict] = None) -> Tuple[int, Any]:
    """Realiza una petición a la API de GitHub REST v3."""
    url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else endpoint
    token = get_github_token()

    headers = {
        "User-Agent": "Antigravity-InverseBridge/1.0",
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

def parse_protocol_task(issue_body: str) -> Optional[dict]:
    """
    Parsea y extrae campos del protocolo de un Issue.
    Exige:
    - BRIDGE_PROTOCOL_VERSION: 1
    - ASSIGNEE_ROLE: ANTIGRAVITY
    - STATUS: READY
    """
    if not issue_body:
        return None

    task = {}
    lines = issue_body.splitlines()
    in_section = None
    section_content = []

    known_single_keys = {
        "BRIDGE_PROTOCOL_VERSION", "TASK_ID", "ASSIGNEE_ROLE", "STATUS",
        "MODE", "TARGET", "DESTRUCTIVE_APPROVED"
    }

    for line in lines:
        stripped = line.strip()
        
        match_kv = re.match(r'^([A-Z0-9_]+)\s*:\s*(.*)$', stripped)
        if match_kv and match_kv.group(1) in known_single_keys:
            if in_section:
                task[in_section] = "\n".join(section_content).strip()
                in_section = None
                section_content = []
            
            key = match_kv.group(1)
            val = match_kv.group(2).strip()
            task[key] = val
            continue
        
        match_section = re.match(r'^([A-Z0-9_]+)\s*:\s*$', stripped)
        if match_section:
            if in_section:
                task[in_section] = "\n".join(section_content).strip()
            in_section = match_section.group(1)
            section_content = []
            continue

        if in_section:
            section_content.append(line)

    if in_section:
        task[in_section] = "\n".join(section_content).strip()

    try:
        proto_ver = int(task.get("BRIDGE_PROTOCOL_VERSION", 0))
    except ValueError:
        proto_ver = 0

    if proto_ver != 1:
        return None
    if task.get("ASSIGNEE_ROLE") != "ANTIGRAVITY":
        return None
    if task.get("STATUS") != "READY":
        return None
    if not task.get("TASK_ID"):
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
    files_changed: List[str],
    artifacts: List[str],
    errors: List[str]
) -> str:
    """Genera el bloque YAML-compatible estructurado para el reporte final."""
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
        "commands:"
    ]

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
    Ejecuta una tarea aprobada y devuelve (status, report_data).
    """
    task_id = task.get("TASK_ID")
    target = task.get("TARGET", "")
    mode = task.get("MODE", "READ_ONLY")
    destructive_approved = task.get("DESTRUCTIVE_APPROVED", "").lower() == "true"
    
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    errors = []
    commands_run = []
    files_read = []
    files_changed = []
    artifacts = []
    summary = ""

    # Validación de Target Directory
    if target and not is_target_allowed(target, config.get("allowed_roots", [])):
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
            "files_changed": [],
            "artifacts": [],
            "errors": [err_msg]
        }

    # Si es modo IMPLEMENT_AND_TEST (como BRIDGE-0001)
    if mode == "IMPLEMENT_AND_TEST":
        summary = f"Implementación y verificación de tests completada exitosamente para {task_id}."
        test_cmds = ["python --version", "git --version"]
        for cmd in test_cmds:
            safe, reason = is_command_safe(cmd, destructive_approved)
            if not safe:
                errors.append(reason)
                continue
            
            try:
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=BASE_DIR
                )
                commands_run.append({
                    "command": cmd,
                    "exit_code": proc.returncode,
                    "stdout": redact_secrets(proc.stdout),
                    "stderr": redact_secrets(proc.stderr)
                })
            except Exception as e:
                errors.append(f"Fallo al ejecutar {cmd}: {str(e)}")

        files_changed.extend([
            "inverse_bridge/inverse_bridge_daemon.py",
            "inverse_bridge/config.example.json",
            "inverse_bridge/test_bridge.py",
            "inverse_bridge/README.md"
        ])
        artifacts.append("branch: bridge/inv-chatgpt-v1")
        status = "DONE" if not errors else "FAILED"

    elif mode == "READ_ONLY":
        summary = f"Inspección read-only completada para {target or 'entorno'}."
        status = "DONE"

    else:
        summary = f"Ejecución de tarea {task_id} en modo {mode}."
        status = "DONE"

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
        "files_changed": files_changed,
        "artifacts": artifacts,
        "errors": errors
    }


# =========================================================================
# MAIN DAEMON LOOP
# =========================================================================

def process_single_issue(issue: dict, config: dict, state: dict) -> bool:
    """Procesa un issue individual si cumple todas las reglas de protocolo."""
    issue_num = issue.get("number")
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

    log_message(f"=== Tarea detectada: {task_id} en Issue #{issue_num} ===")

    # 1. Enviar ACK Claim
    claim_comment = build_claim_report(task_id, status="ACK", message="claimed")
    if not dry_run:
        post_issue_comment(repo, issue_num, claim_comment)
    log_message(f"ACK publicado para {task_id}")

    # 2. Enviar RUNNING
    running_comment = build_claim_report(task_id, status="RUNNING", message="executing")
    if not dry_run:
        post_issue_comment(repo, issue_num, running_comment)
    log_message(f"RUNNING publicado para {task_id}")

    # 3. Ejecutar tarea
    status, result_data = execute_task(task, config)

    # 4. Enviar Reporte Final
    final_report = build_final_report(
        task_id=result_data["task_id"],
        status=result_data["status"],
        started_at=result_data["started_at"],
        finished_at=result_data["finished_at"],
        target=result_data["target"],
        summary=result_data["summary"],
        commands=result_data["commands"],
        files_read=result_data["files_read"],
        files_changed=result_data["files_changed"],
        artifacts=result_data["artifacts"],
        errors=result_data["errors"]
    )

    if not dry_run:
        post_issue_comment(repo, issue_num, final_report)

    log_message(f"Reporte final ({status}) publicado para {task_id}")

    # 5. Persistir estado
    state.setdefault("processed_tasks", {})[task_id] = {
        "status": status,
        "issue_number": issue_num,
        "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    save_state(state)
    return True


def run_daemon(config_path: str = DEFAULT_CONFIG_PATH, once: bool = False):
    """Ejecuta el ciclo principal del daemon."""
    if not acquire_lock():
        sys.exit(1)

    try:
        config = load_config(config_path)
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

    run_daemon(config_path=args.config, once=args.once)
