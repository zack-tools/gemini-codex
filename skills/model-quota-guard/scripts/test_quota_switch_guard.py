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


    def test_switch_provider_mock(self):
        import tempfile, shutil
        from pathlib import Path
        import quota_switch_guard

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_codex = Path(tmpdir) / ".codex"
            mock_codex.mkdir()
            orig = Path.home() / ".codex" / "config.toml"
            if orig.exists():
                shutil.copyfile(orig, mock_codex / "config.toml")
            else:
                (mock_codex / "config.toml").write_text('model_provider = "custom"\nmodel = "gemini-3.8-flash-high"\n')
            
            quota_switch_guard.CODEX_DIR = mock_codex
            quota_switch_guard.CC_SWITCH_DIR = Path(tmpdir) / ".cc-switch"

            # 1. Test OpenAI switch
            success = quota_switch_guard.switch_provider("openai")
            self.assertTrue(success)
            text1 = (mock_codex / "config.toml").read_text()
            self.assertIn('model_provider = "openai_http"', text1)
            self.assertIn('model = "gpt-5.5"', text1)

            # 2. Test Gemini switch
            success = quota_switch_guard.switch_provider("gemini")
            self.assertTrue(success)
            text2 = (mock_codex / "config.toml").read_text()
            self.assertIn('model_provider = "custom"', text2)
            self.assertIn('model = "gemini-3.8-flash-high"', text2)

            # 3. Test Claude switch
            success = quota_switch_guard.switch_provider("claude")
            self.assertTrue(success)
            text3 = (mock_codex / "config.toml").read_text()
            self.assertIn('model_provider = "custom"', text3)
            self.assertIn('model = "claude-sonnet-4-6"', text3)

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
