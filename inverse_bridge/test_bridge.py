#!/usr/bin/env python3
"""
Comprehensive Test Suite for Inverse Bridge Daemon V1.2
Covers all PR review requirements and V1.2 security enhancements:
1. Parser valid task
2. Reject unknown role / status / version
3. Reject unknown MODE
4. Reject unknown section/key
5. Reject target outside allowed_roots
6. Deduplication test
7. Secret redaction test
8. Destructive command safety blocking
9. EXEC mode with real commands payload (shell=False, cwd=TARGET)
10. READ_FILES mode with structured file_contents dumping
11. READ_ONLY allowlist diagnostic enforcement
12. Effective CLI --dry-run
13. Untrusted author rejection test (trusted_issue_authors)
14. Trusted author acceptance test
15. Full End-to-End Pipeline simulation
"""

import os
import sys
import unittest
import tempfile
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inverse_bridge_daemon import (
    parse_protocol_task,
    parse_items_list,
    is_target_allowed,
    is_command_safe,
    is_read_only_allowed,
    run_command_safe,
    redact_secrets,
    build_claim_report,
    build_final_report,
    execute_task,
    process_single_issue,
    load_state,
    save_state
)


class TestInverseBridgeV12(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "repo": "mromerolobos-bot/co_escritor_ia",
            "poll_seconds": 10,
            "agent_role": "ANTIGRAVITY",
            "trusted_issue_authors": ["mromerolobos-bot"],
            "allowed_roots": [
                r"C:\pinokio\api\cinematic-character-studio-v1-1",
                r"C:\Users\Chelowolf",
                self.temp_dir
            ],
            "dry_run": False
        }

    # 1. Parser test for valid task
    def test_parser_valid_task(self):
        valid_body = """
BRIDGE_PROTOCOL_VERSION: 1
TASK_ID: TEST-0001
ASSIGNEE_ROLE: ANTIGRAVITY
STATUS: READY
MODE: EXEC
TARGET: C:\\Users\\Chelowolf
COMMANDS:
  - python --version
  - git --version
"""
        task = parse_protocol_task(valid_body)
        self.assertIsNotNone(task)
        self.assertEqual(task.get("TASK_ID"), "TEST-0001")
        self.assertEqual(task.get("ASSIGNEE_ROLE"), "ANTIGRAVITY")
        self.assertEqual(task.get("STATUS"), "READY")
        self.assertEqual(task.get("MODE"), "EXEC")
        cmds = parse_items_list(task.get("COMMANDS", ""))
        self.assertEqual(len(cmds), 2)
        self.assertEqual(cmds[0], "python --version")
        self.assertEqual(cmds[1], "git --version")

    # 2. Reject wrong role, status or version
    def test_reject_wrong_role_or_status(self):
        wrong_role = "BRIDGE_PROTOCOL_VERSION: 1\nTASK_ID: T1\nASSIGNEE_ROLE: DIRECTOR\nSTATUS: READY\nMODE: EXEC\n"
        self.assertIsNone(parse_protocol_task(wrong_role))

        not_ready = "BRIDGE_PROTOCOL_VERSION: 1\nTASK_ID: T2\nASSIGNEE_ROLE: ANTIGRAVITY\nSTATUS: IN_PROGRESS\nMODE: EXEC\n"
        self.assertIsNone(parse_protocol_task(not_ready))

        wrong_version = "BRIDGE_PROTOCOL_VERSION: 2\nTASK_ID: T3\nASSIGNEE_ROLE: ANTIGRAVITY\nSTATUS: READY\nMODE: EXEC\n"
        self.assertIsNone(parse_protocol_task(wrong_version))

    # 3. Reject unknown MODE
    def test_reject_unknown_mode(self):
        invalid_mode = "BRIDGE_PROTOCOL_VERSION: 1\nTASK_ID: T4\nASSIGNEE_ROLE: ANTIGRAVITY\nSTATUS: READY\nMODE: ARBITRARY_SUPER_MODE\n"
        self.assertIsNone(parse_protocol_task(invalid_mode))

    # 4. Reject unknown section/key
    def test_reject_unknown_section(self):
        unknown_sec = "BRIDGE_PROTOCOL_VERSION: 1\nTASK_ID: T5\nASSIGNEE_ROLE: ANTIGRAVITY\nSTATUS: READY\nMODE: EXEC\nUNKNOWN_SECTION_KEY:\n- hello\n"
        self.assertIsNone(parse_protocol_task(unknown_sec))

    # 5. Reject target outside allowed_roots
    def test_reject_target_outside_allowed_roots(self):
        allowed_path = r"C:\Users\Chelowolf\Documents\test"
        forbidden_path = r"C:\Windows\System32"
        
        self.assertTrue(is_target_allowed(allowed_path, self.config["allowed_roots"]))
        self.assertFalse(is_target_allowed(forbidden_path, self.config["allowed_roots"]))

        task = {
            "BRIDGE_PROTOCOL_VERSION": "1",
            "TASK_ID": "TEST-FORBIDDEN",
            "TARGET": forbidden_path,
            "MODE": "EXEC",
            "COMMANDS": "python --version"
        }
        status, result = execute_task(task, self.config)
        self.assertEqual(status, "BLOCKED")
        self.assertIn("Ruta objetivo no permitida", result["errors"][0])

    # 6. Deduplication test
    def test_deduplication(self):
        state = {
            "processed_tasks": {
                "TASK-ALREADY-DONE": {"status": "DONE"}
            }
        }
        issue = {
            "number": 99,
            "user": {"login": "mromerolobos-bot"},
            "body": "BRIDGE_PROTOCOL_VERSION: 1\nTASK_ID: TASK-ALREADY-DONE\nASSIGNEE_ROLE: ANTIGRAVITY\nSTATUS: READY\nMODE: EXEC\nCOMMANDS:\n- python --version\n"
        }
        processed = process_single_issue(issue, self.config, state)
        self.assertFalse(processed, "Should not re-process already processed task")

    # 7. Secret redaction test
    def test_secret_redaction(self):
        sample = "Token is ghp_123456789012345678901234567890ABCDEF and github_pat_11FAKE_SYNTHETIC_TEST_TOKEN_NOT_REAL_12345678901234567890"
        redacted = redact_secrets(sample)
        self.assertNotIn("ghp_123456789012345678901234567890ABCDEF", redacted)
        self.assertNotIn("github_pat_11FAKE_SYNTHETIC_TEST_TOKEN_NOT_REAL_12345678901234567890", redacted)
        self.assertIn("[REDACTED]", redacted)

    # 8. Destructive command blocking test
    def test_destructive_command_blocking(self):
        safe_cmd = "git status"
        destructive_cmd = "rmdir /s /q C:\\something"
        
        is_safe, _ = is_command_safe(safe_cmd, destructive_approved=False)
        self.assertTrue(is_safe)

        is_safe, _ = is_command_safe(destructive_cmd, destructive_approved=False)
        self.assertFalse(is_safe)

        is_safe_override, _ = is_command_safe(destructive_cmd, destructive_approved=True)
        self.assertTrue(is_safe_override)

    # 9. EXEC mode with real commands payload and cwd=TARGET (shell=False)
    def test_exec_mode_real_commands(self):
        task = {
            "BRIDGE_PROTOCOL_VERSION": "1",
            "TASK_ID": "TEST-EXEC-001",
            "ASSIGNEE_ROLE": "ANTIGRAVITY",
            "STATUS": "READY",
            "MODE": "EXEC",
            "TARGET": self.temp_dir,
            "COMMANDS": "python --version\ngit --version"
        }
        status, result = execute_task(task, self.config)
        self.assertEqual(status, "DONE")
        self.assertEqual(len(result["commands"]), 2)
        self.assertEqual(result["commands"][0]["exit_code"], 0)
        self.assertIn("Python", result["commands"][0]["stdout"])
        self.assertEqual(result["commands"][1]["exit_code"], 0)
        self.assertIn("git", result["commands"][1]["stdout"].lower())

    # 10. READ_FILES mode with structured file_contents dumping
    def test_read_files_mode_with_contents(self):
        test_file = os.path.join(self.temp_dir, "sample.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Hello from Inverse Bridge test file content!")

        task = {
            "BRIDGE_PROTOCOL_VERSION": "1",
            "TASK_ID": "TEST-READ-001",
            "ASSIGNEE_ROLE": "ANTIGRAVITY",
            "STATUS": "READY",
            "MODE": "READ_FILES",
            "TARGET": self.temp_dir,
            "FILES": f"- {test_file}"
        }
        status, result = execute_task(task, self.config)
        self.assertEqual(status, "DONE")
        self.assertIn(test_file, result["files_read"])
        self.assertEqual(len(result["file_contents"]), 1)
        self.assertEqual(result["file_contents"][0]["path"], test_file)
        self.assertEqual(result["file_contents"][0]["truncated"], False)
        self.assertIn("Hello from Inverse Bridge test file content!", result["file_contents"][0]["content"])

    # 11. READ_ONLY allowlist diagnostic enforcement
    def test_read_only_allowlist(self):
        allowed_cmd = "git status"
        forbidden_cmd = "powershell -Command Remove-Item"
        
        ok, _ = is_read_only_allowed(allowed_cmd)
        self.assertTrue(ok)
        
        ok, reason = is_read_only_allowed(forbidden_cmd)
        self.assertFalse(ok)
        self.assertIn("allowlist de diagnósticos", reason)

    # 12. Effective CLI dry-run
    def test_dry_run_flag(self):
        dry_config = self.config.copy()
        dry_config["dry_run"] = True
        
        task = {
            "BRIDGE_PROTOCOL_VERSION": "1",
            "TASK_ID": "TEST-DRY-001",
            "ASSIGNEE_ROLE": "ANTIGRAVITY",
            "STATUS": "READY",
            "MODE": "EXEC",
            "TARGET": self.temp_dir,
            "COMMANDS": "- python --version"
        }
        status, result = execute_task(task, dry_config)
        self.assertEqual(status, "DONE")
        self.assertIn("dry-run simulated execution", result["commands"][0]["stdout"])

    # 13. Untrusted author rejection test (trusted_issue_authors)
    def test_untrusted_author_rejection(self):
        untrusted_issue = {
            "number": 102,
            "user": {"login": "attacker-or-unknown-user"},
            "body": f"""
BRIDGE_PROTOCOL_VERSION: 1
TASK_ID: ATTACK-001
ASSIGNEE_ROLE: ANTIGRAVITY
STATUS: READY
MODE: EXEC
TARGET: {self.temp_dir}
COMMANDS:
  - python --version
"""
        }
        state = {"processed_tasks": {}}
        processed = process_single_issue(untrusted_issue, self.config, state)
        self.assertFalse(processed, "Issue from untrusted author must be ignored completely")
        self.assertNotIn("ATTACK-001", state["processed_tasks"])

    # 14. Trusted author acceptance test
    def test_trusted_author_acceptance(self):
        trusted_issue = {
            "number": 103,
            "user": {"login": "mromerolobos-bot"},
            "body": f"""
BRIDGE_PROTOCOL_VERSION: 1
TASK_ID: TRUSTED-001
ASSIGNEE_ROLE: ANTIGRAVITY
STATUS: READY
MODE: EXEC
TARGET: {self.temp_dir}
COMMANDS:
  - python --version
"""
        }
        dry_config = self.config.copy()
        dry_config["dry_run"] = True
        state = {"processed_tasks": {}}
        
        processed = process_single_issue(trusted_issue, dry_config, state)
        self.assertTrue(processed, "Issue from trusted author must be accepted and processed")
        self.assertIn("TRUSTED-001", state["processed_tasks"])

    # 15. Full End-to-End Pipeline simulation
    def test_end_to_end_pipeline(self):
        issue = {
            "number": 104,
            "user": {"login": "mromerolobos-bot"},
            "body": f"""
BRIDGE_PROTOCOL_VERSION: 1
TASK_ID: E2E-TEST-V12
ASSIGNEE_ROLE: ANTIGRAVITY
STATUS: READY
MODE: EXEC
TARGET: {self.temp_dir}
COMMANDS:
  - python -c "print('E2E_V12_SUCCESS')"
"""
        }
        dry_config = self.config.copy()
        dry_config["dry_run"] = True
        state = {"processed_tasks": {}}
        
        processed = process_single_issue(issue, dry_config, state)
        self.assertTrue(processed)
        self.assertIn("E2E-TEST-V12", state["processed_tasks"])
        self.assertEqual(state["processed_tasks"]["E2E-TEST-V12"]["status"], "DONE")


if __name__ == "__main__":
    unittest.main()
