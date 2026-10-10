#!/usr/bin/env python3
"""
Unit tests for quota_switch_guard.py
"""

import unittest
from unittest.mock import Mock, patch
import quota_switch_guard as guard
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
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_codex = Path(tmpdir) / ".codex"
            mock_codex.mkdir()
            fixture = 'model_provider = "custom"\nmodel = "gemini-3.8-flash-high"\n[profiles.other]\nmodel = "preserved-model"\n'
            (mock_codex / "config.toml").write_text(fixture)
            with patch.object(guard, "CODEX_DIR", mock_codex), patch.object(guard, "CC_SWITCH_DIR", Path(tmpdir) / ".cc-switch"), patch.object(guard.subprocess, "run") as run:
                for provider, model in [("openai", "gpt-5.5"), ("gemini", "gemini-3.8-flash-high"), ("claude", "claude-sonnet-4-6")]:
                    self.assertTrue(guard.switch_provider(provider))
                    text = (mock_codex / "config.toml").read_text()
                    self.assertIn(f'model = "{model}"', text)
                    self.assertIn('model = "preserved-model"', text)
                    self.assertEqual(guard.read_current_codex_config()["model"], model)
                sanitize = [call for call in run.call_args_list if str(call.args[0][-1]).endswith("sanitize_history.py")]
                self.assertEqual(len(sanitize), 3)
                self.assertTrue(all(call.kwargs["env"]["CODEX_HOME"] == str(mock_codex) for call in sanitize))

    def test_unknown_quota_does_not_trigger_switch(self):
        for provider in ("openai", "gemini", "claude"):
            res = evaluate_status({"provider": provider, "model": "unavailable"}, {})
            self.assertEqual(res["level"], "UNKNOWN")
            self.assertIsNone(res["current"]["percent"])
            self.assertFalse(res["dual_critical"])
            self.assertFalse(res["target"]["quota_available"])

    def test_unavailable_fallback_is_not_eligible(self):
        res = evaluate_status({"provider": "openai", "model": "gpt-5.5"}, {"openai": {"percent": 0}})
        self.assertEqual(res["level"], "CRITICAL_SWITCH")
        self.assertFalse(res["target"]["quota_available"])

    def test_fetch_uses_active_model_and_known_codex_windows(self):
        source = Mock()
        source.collect_antigravity_quota.return_value = {
            "gemini": {"percent": 0},
            "geminiModels": [{"modelId": "gemini-actual", "percent": 70}],
            "claudeModels": [{"modelId": guard.DEFAULT_CLAUDE_MODEL, "percent": None}],
        }
        source.collect_openai_quota.return_value = {"rateLimits": [
            {"name": "code_review", "primary": {"remainingPercent": 1}},
            {"name": "codex", "primary": None, "secondary": {"remainingPercent": 40}},
        ]}
        with patch.object(guard, "load_check_quota_module", return_value=source), patch.object(guard, "read_current_codex_config", return_value={"provider": "gemini", "model": "ccs-gemini/gemini-actual"}):
            quotas = guard.fetch_all_quotas()
        self.assertEqual(quotas["gemini"]["percent"], 70)
        self.assertEqual(quotas["openai"]["percent"], 40)
        self.assertIsNone(quotas["claude"]["percent"])

    def test_fetch_does_not_use_unrelated_or_missing_limits(self):
        source = Mock()
        source.collect_antigravity_quota.return_value = {"geminiModels": [{"modelId": "other", "percent": 100}]}
        source.collect_openai_quota.return_value = {"rateLimits": [{"name": "code_review", "primary": {"remainingPercent": 100}}]}
        with patch.object(guard, "load_check_quota_module", return_value=source), patch.object(guard, "read_current_codex_config", return_value={"provider": "gemini", "model": "missing"}):
            quotas = guard.fetch_all_quotas()
        self.assertIsNone(quotas["gemini"])
        self.assertIsNone(quotas["openai"])

    def test_auto_guard_with_unknown_quota_never_mutates(self):
        with patch.object(guard, "read_current_codex_config", return_value={"provider": "openai", "model": "unknown"}), patch.object(guard, "fetch_all_quotas", return_value={}), patch.object(guard, "switch_provider") as switch, patch.object(guard, "restart_codex") as restart, patch("sys.argv", ["guard", "--auto-guard", "--restart", "--json"]), patch("builtins.print"):
            guard.main()
        switch.assert_not_called()
        restart.assert_not_called()

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
