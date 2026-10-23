import json
from pathlib import Path
import tempfile
import unittest
from ensure_model_routes import repair

class RouteGuardTests(unittest.TestCase):
    def fixture(self, base, active=True):
        home, switch = base / "codex", base / "switch"
        home.mkdir(); switch.mkdir()
        (switch / "live-state.json").write_text(json.dumps({"apps":{"codex":{"stack":{"enabled":active}}}}))
        (home / "config.toml").write_text('model = "gemini-3.8-flash-high"\nmodel_catalog_json = "model_catalog.json"\n[model_providers.custom]\nbase_url = "http://127.0.0.1:15721/v1"\n')
        (home / "cc-switch-model-catalog.json").write_text(json.dumps({"models":[{"slug":"gpt-6.1-sol"},{"slug":"ccs-gemini/gemini-3.8-flash-high"}]}))
        (home / "model_catalog.json").write_text('{"models":[{"slug":"gemini-3.8-flash-high"}]}')
        return home, switch

    def test_update_regression_and_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            home,switch=self.fixture(Path(d))
            repair(home,switch)
            text=(home/"config.toml").read_text()
            self.assertIn('model = "ccs-gemini/gemini-3.8-flash-high"', text)
            self.assertIn('base_url = "http://127.0.0.1:15721/v1"',text)
            self.assertEqual((home/"model_catalog.json").read_bytes(),(home/"cc-switch-model-catalog.json").read_bytes())
            self.assertEqual(repair(home,switch)["changed"],[])
            # Simulate an update overwriting the catalog a second time.
            (home/"model_catalog.json").write_text('{"models":[]}')
            self.assertEqual(repair(home,switch)["changed"],["model_catalog.json"])

    def test_direct_mode_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            home,switch=self.fixture(Path(d),False)
            before={p.name:p.read_bytes() for p in home.iterdir()}
            self.assertEqual(repair(home,switch)["status"],"skipped")
            self.assertEqual(before,{p.name:p.read_bytes() for p in home.iterdir()})

    def test_invalid_route_fails_without_config_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            home,switch=self.fixture(Path(d))
            (home/"cc-switch-model-catalog.json").write_text('{"models":[{"slug":"gemini-bad"}]}')
            before=(home/"config.toml").read_bytes()
            with self.assertRaises(ValueError): repair(home,switch)
            self.assertEqual(before,(home/"config.toml").read_bytes())

if __name__ == "__main__": unittest.main()
