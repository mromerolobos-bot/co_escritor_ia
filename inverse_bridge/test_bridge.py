#!/usr/bin/env python3
"""
Test Suite for Inverse Bridge Daemon
Tests all safety rules, protocol parsing, deduplication, secret redaction, and execution.
"""

import os
import sys
import unittest
import tempfile
import json
import subprocess

# Asegurar import de inverse_bridge_daemon
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inverse_bridge_daemon import (
    parse_protocol_task,
    is_target_allowed,
    is_command_safe,
    redact_secrets,
    build_claim_report,
    build_final_report,
    execute_task,
    process_single_issue,
    load_state,
    save_state
)


class TestInverseBridge(unittest.TestCase):

    def setUp(self):
        self.config = {
            "repo": "mromerolobos-bot/co_escritor_ia",
            "poll_seconds": 10,
            "agent_role": "ANTIGRAVITY",
            "allowed_roots": [
                r"C:\pinokio\api\cinematic-character-studio-v1-1",
                r"C:\Users\Chelowolf"
            ],
            "dry_run": True
        }

    # 1. Parser test for valid task
    def test_parser_valid_task(self):
        valid_body = """
BRIDGE_PROTOCOL_VERSION: 1
TASK_ID: TEST-0001
ASSIGNEE_ROLE: ANTIGRAVITY
STATUS: READY
MODE: READ_ONLY
TARGET: C:\\Users\\Chelowolf
"""
        task = parse_protocol_task(valid_body)
        self.assertIsNotNone(task)
        self.assertEqual(task.get("TASK_ID"), "TEST-0001")
        self.assertEqual(task.get("ASSIGNEE_ROLE"), "ANTIGRAVITY")
        self.assertEqual(task.get("STATUS"), "READY")
        self.assertEqual(task.get("MODE"), "READ_ONLY")

    # 2. Reject task with wrong role or wrong status
    def test_reject_wrong_role_or_status(self):
        wrong_role = """
BRIDGE_PROTOCOL_VERSION: 1
TASK_ID: TEST-0002
ASSIGNEE_ROLE: HUMAN_DIRECTOR
STATUS: READY
"""
        self.assertIsNone(parse_protocol_task(wrong_role))

        not_ready = """
BRIDGE_PROTOCOL_VERSION: 1
TASK_ID: TEST-0003
ASSIGNEE_ROLE: ANTIGRAVITY
STATUS: IN_PROGRESS
"""
        self.assertIsNone(parse_protocol_task(not_ready))

        wrong_version = """
BRIDGE_PROTOCOL_VERSION: 2
TASK_ID: TEST-0004
ASSIGNEE_ROLE: ANTIGRAVITY
STATUS: READY
"""
        self.assertIsNone(parse_protocol_task(wrong_version))

    # 3. Reject target outside allowed_roots
    def test_reject_target_outside_allowed_roots(self):
        allowed_path = r"C:\Users\Chelowolf\Documents\test"
        forbidden_path = r"C:\Windows\System32"
        
        self.assertTrue(is_target_allowed(allowed_path, self.config["allowed_roots"]))
        self.assertFalse(is_target_allowed(forbidden_path, self.config["allowed_roots"]))

        # Execution check
        task = {
            "TASK_ID": "TEST-FORBIDDEN",
            "TARGET": forbidden_path,
            "MODE": "READ_ONLY"
        }
        status, result = execute_task(task, self.config)
        self.assertEqual(status, "BLOCKED")
        self.assertIn("Ruta objetivo no permitida", result["errors"][0])

    # 4. Deduplication test
    def test_deduplication(self):
        state = {
            "processed_tasks": {
                "ALREADY_DONE_TASK": {"status": "DONE"}
            }
        }
        issue = {
            "number": 99,
            "body": """
BRIDGE_PROTOCOL_VERSION: 1
TASK_ID: ALREADY_DONE_TASK
ASSIGNEE_ROLE: ANTIGRAVITY
STATUS: READY
"""
        }
        processed = process_single_issue(issue, self.config, state)
        self.assertFalse(processed, "Should not re-process already processed task")

    # 5. Secret-redaction test
    def test_secret_redaction(self):
        sample_text = "My token is ghp_123456789012345678901234567890ABCDEF and bearer github_pat_11ABCDEFG123456789012345678901234567890_test"
        redacted = redact_secrets(sample_text)
        self.assertNotIn("ghp_123456789012345678901234567890ABCDEF", redacted)
        self.assertNotIn("github_pat_11ABCDEFG123456789012345678901234567890_test", redacted)
        self.assertIn("[REDACTED]", redacted)

    # 6. Destructive command safety check
    def test_destructive_command_blocking(self):
        safe_cmd = "git --version"
        destructive_cmd = "rmdir /s /q C:\\something"
        
        is_safe, _ = is_command_safe(safe_cmd, destructive_approved=False)
        self.assertTrue(is_safe)

        is_safe, _ = is_command_safe(destructive_cmd, destructive_approved=False)
        self.assertFalse(is_safe)

        is_safe_override, _ = is_command_safe(destructive_cmd, destructive_approved=True)
        self.assertTrue(is_safe_override)

    # 7. End-to-end harmless task test (python --version & git --version)
    def test_e2e_harmless_task(self):
        task = {
            "BRIDGE_PROTOCOL_VERSION": "1",
            "TASK_ID": "TEST-E2E-001",
            "ASSIGNEE_ROLE": "ANTIGRAVITY",
            "STATUS": "READY",
            "MODE": "IMPLEMENT_AND_TEST",
            "TARGET": r"C:\Users\Chelowolf"
        }
        status, result = execute_task(task, self.config)
        self.assertEqual(status, "DONE")
        self.assertTrue(len(result["commands"]) >= 2)
        
        # Verificar que se generó reporte válido
        final_report = build_final_report(
            task_id=result["task_id"],
            status=result["status"],
            started_at=result["started_at"],
            finished_at=result["finished_at"],
            target=result["target"],
            summary=result["summary"],
            commands=result["commands"],
            files_read=result["files_read"],
            files_changed=result["files_changed"],
            artifacts=result["artifacts"],
            errors=result["errors"]
        )
        self.assertIn("<<<INV_CHATGPT_REPORT>>>", final_report)
        self.assertIn("status: DONE", final_report)
        self.assertIn("<<<END_INV_CHATGPT_REPORT>>>", final_report)


if __name__ == "__main__":
    unittest.main()
