"""Pure tests for user-visible clock-check results, no HA installation required."""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "tenmicron_mount" / "clock_feedback.py"
spec = importlib.util.spec_from_file_location("clock_feedback", MODULE)
feedback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feedback)

class ClockFeedbackTests(unittest.TestCase):
    def test_read_only_success_and_ntp_details(self):
        now = datetime(2026, 10, 28, 16, 30, tzinfo=timezone.utc)
        snap = feedback.capture_check({
            "ok": True, "mode":"dry_run", "before_ms":-12.34,
            "ntp_system_offset_ms": 2.5, "ntp_servers_used": ["ntp.example"],
            "ntp_errors":[], "corrections": []
        }, now=now)
        self.assertEqual(snap["mount_offset_ms"], -12.34)
        self.assertEqual(snap["status"], "ok")
        title, message = feedback.notification(snap,"cs")
        self.assertIn("kontrola hodin", title)
        self.assertIn("-12,34 ms", message)
        self.assertIn("ntp.example",message)
        self.assertIn("nebyl změněn",message)
        self.assertIn("NTP − HA",message)
    def test_errors_remain_visible_and_no_false_success(self):
        snap = feedback.capture_check(error="NTP timeout")
        self.assertEqual(snap["status"], "error")
        title, message = feedback.notification(snap,"en")
        self.assertIn("ERROR", title)
        self.assertIn("NTP timeout",message)
        self.assertIn("not changed",message)
    def test_dry_run_suggestions_are_never_reported_applied(self):
        snap = feedback.capture_check({
            "ok":True,"before_ms":500,
            "corrections":[{"type":"fine","adjustment_ms":-500}],
        })
        self.assertIn("not applied", feedback.notification(snap, "en")[1])
    def test_publishing_is_manual_only_and_does_not_modify_mount_commands(self):
        source = (MODULE.parent / "__init__.py").read_text()
        self.assertIn('source != "manual"',source)
        self.assertIn('if operation == "time_check":',source)
        self.assertIn('self._publish_clock_check(error=str(exc)',source)
        self.assertNotIn('":SUDT#"', (MODULE).read_text())

if __name__ == "__main__":
    unittest.main()
