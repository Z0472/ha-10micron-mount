"""Check translation completeness and JSON formatting without HA dependencies."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "tenmicron_mount"

class TranslationTests(unittest.TestCase):
    def test_english_and_czech_translation_keys(self):
        with (ROOT / "translations" / "en.json").open(encoding="utf-8") as f:
            en = json.load(f)
        with (ROOT / "translations" / "cs.json").open(encoding="utf-8") as f:
            cs = json.load(f)
        for group, step in (("config", "user"), ("options", "init")):
            for translation in (en, cs):
                data = translation[group]["step"][step]["data"]
                self.assertEqual(set(data), set(en[group]["step"][step]["data"]))
                self.assertTrue(all(isinstance(v, str) and v.strip() for v in data.values()))
                self.assertIn("invalid_config", translation[group]["error"])
        for name in ("host", "port", "ntp_servers", "temperature_entity", "pressure_entity",
                     "time_sync_enabled", "refraction_enabled", "auto_time_sync_enabled",
                     "auto_refraction_enabled", "native_controls_enabled"):
            self.assertIn(name, en["config"]["step"]["user"]["data"])

if __name__ == "__main__":
    unittest.main()
