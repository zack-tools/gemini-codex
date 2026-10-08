#!/usr/bin/env python3
"""
Unit tests for quota_switch_guard.py
"""

import unittest
from quota_switch_guard import evaluate_status, read_current_codex_config


class TestQuotaSwitchGuard(unittest.TestCase):
    def setUp(self):
        self.mock_quotas = {
            "openai": {
                "percent": 95.0,
                "primaryPercent": 95.0,
                "secondaryPercent": 98.0,
                "resetTimeLocal": "2026-10-09 10:00:00",
                "planType": "plus",
            },
            "gemini": {
                "percent": 45.0,
                "resetTimeLocal": "2026-10-09 05:00:00",
                "modelId": "gemini-3.8-flash-high",
            },
            "claude": {
                "percent": 100.0,
                "resetTimeLocal": "2026-10-09 08:00:00",
                "modelId": "claude-sonnet-4-6",
            },
        }

    def test_status_ok(self):
        cfg = {"provider": "openai", "model": "gpt-5.5"}
        res = evaluate_status(cfg, self.mock_quotas, warn_threshold=10.0, switch_threshold=5.0)
        self.assertEqual(res["level"], "OK")
        self.assertFalse(res["dual_depleted"])

    def test_status_warning(self):
        quotas = dict(self.mock_quotas)
        quotas["openai"] = {"percent": 8.5, "resetTimeLocal": "2026-10-09 10:00:00"}
        cfg = {"provider": "openai", "model": "gpt-5.5"}
        res = evaluate_status(cfg, quotas, warn_threshold=10.0, switch_threshold=5.0)
        self.assertEqual(res["level"], "WARNING")
        self.assertIn("額度預警", res["message"])

    def test_status_critical_switch_openai_to_gemini(self):
        quotas = dict(self.mock_quotas)
        quotas["openai"] = {"percent": 3.0, "resetTimeLocal": "2026-10-09 10:00:00"}
        cfg = {"provider": "openai", "model": "gpt-5.5"}
        res = evaluate_status(cfg, quotas, warn_threshold=10.0, switch_threshold=5.0)
        self.assertEqual(res["level"], "CRITICAL_SWITCH")
        self.assertEqual(res["target"]["provider"], "gemini")

    def test_status_critical_switch_gemini_to_openai(self):
        quotas = dict(self.mock_quotas)
        quotas["gemini"] = {"percent": 4.0, "resetTimeLocal": "2026-10-09 05:00:00"}
        cfg = {"provider": "gemini", "model": "gemini-3.8-flash-high"}
        res = evaluate_status(cfg, quotas, warn_threshold=10.0, switch_threshold=5.0)
        self.assertEqual(res["level"], "CRITICAL_SWITCH")
        self.assertEqual(res["target"]["provider"], "openai")

    def test_dual_critical_alert(self):
        quotas = dict(self.mock_quotas)
        quotas["openai"] = {"percent": 2.0, "resetTimeLocal": "2026-10-09 10:00:00"}
        quotas["gemini"] = {"percent": 3.0, "resetTimeLocal": "2026-10-09 05:00:00"}
        cfg = {"provider": "openai", "model": "gpt-5.5"}
        res = evaluate_status(cfg, quotas, warn_threshold=10.0, switch_threshold=5.0)
        self.assertEqual(res["level"], "CRITICAL_SWITCH")
        self.assertTrue(res["dual_critical"])
        self.assertIn("雙重耗盡警報", res["dual_message"])


if __name__ == "__main__":
    unittest.main()
