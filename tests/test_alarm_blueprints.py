"""Validate alarm blueprints and ensure no mount control is added."""
import pathlib
import unittest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "blueprints/automation/tenmicron/tracking_stop_alarm.yaml",
    ROOT / "blueprints/automation/tenmicron/connection_lost_alarm.yaml",
]
class Loader(yaml.SafeLoader):
    pass
Loader.add_constructor("!input", lambda loader, node: {"input": loader.construct_scalar(node)})

class BlueprintTests(unittest.TestCase):
    def test_each_blueprint_is_valid_and_opt_in(self):
        for file in FILES:
            raw = file.read_text(encoding="utf-8")
            doc = yaml.load(raw, Loader=Loader)
            with self.subTest(file=file.name):
                self.assertEqual(doc["blueprint"]["domain"], "automation")
                self.assertIn("actions", doc)
                self.assertIsInstance(doc["triggers"], list)
                self.assertTrue(doc["blueprint"]["input"])
                self.assertIn("selector", next(iter(doc["blueprint"]["input"].values())))
                self.assertNotIn(":PsX#",raw)
                # A description may mention sirens; only default actions must stay passive.
                defaults = [
                    option.get("default")
                    for option in doc["blueprint"]["input"].values()
                    if isinstance(option, dict) and "default" in option
                ]
                self.assertNotIn("siren.turn_on", repr(defaults))
                self.assertNotIn("rest_command",raw)
                self.assertEqual(doc["mode"],"single")
    def test_tracking_alarm_requires_fresh_off_to_on(self):
        d=yaml.load(FILES[0].read_text(encoding="utf-8"), Loader=Loader)
        self.assertEqual(d["triggers"][0]["from"],"off")
        self.assertEqual(d["triggers"][0]["to"],"on")
        self.assertEqual(d["actions"]["input"],"alarm_actions")
    def test_connection_outage_requires_duration(self):
        d=yaml.load(FILES[1].read_text(encoding="utf-8"), Loader=Loader)
        self.assertEqual({t["to"] for t in d["triggers"]},{"unknown","unavailable"})
        self.assertTrue(all(t["for"]["input"]=="outage_duration" for t in d["triggers"]))
        self.assertEqual(d["actions"]["input"],"alert_actions")
