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

class EntityTranslationTests(unittest.TestCase):
    def test_all_entities_are_translated_without_hardcoded_names(self):
        import re
        files = {
            "sensor": (ROOT / "sensor.py").read_text(encoding="utf-8"),
            "binary_sensor": (ROOT / "binary_sensor.py").read_text(encoding="utf-8"),
            "button": (ROOT / "button.py").read_text(encoding="utf-8"),
        }
        en = json.loads((ROOT / "translations/en.json").read_text(encoding="utf-8"))
        cs = json.loads((ROOT / "translations/cs.json").read_text(encoding="utf-8"))
        for domain, code in files.items():
            self.assertIn("_attr_translation_key", code)
            self.assertNotIn("_attr_name =", code)
            self.assertEqual(en["entity"][domain].keys(), cs["entity"][domain].keys())
            self.assertTrue(all(item["name"].strip() for item in cs["entity"][domain].values()))
        self.assertIn("park_separation", en["entity"]["sensor"])
        self.assertIn("park_geometry", cs["entity"]["binary_sensor"])
        self.assertIn("time_check", cs["entity"]["button"])

    def test_park_reference_is_visible_early_in_form(self):
        code = (ROOT / "config_flow.py").read_text(encoding="utf-8")
        self.assertLess(code.index('vol.Optional("park_alt"'), code.index('vol.Optional("ntp_servers"'))
        self.assertLess(code.index('vol.Optional("park_az"'), code.index('vol.Optional("ntp_servers"'))
