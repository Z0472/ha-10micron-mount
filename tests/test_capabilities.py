"""Pure guards test without importing Home Assistant."""
import importlib.util
import pathlib
import unittest

FILE = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "tenmicron_mount" / "capabilities.py"
spec = importlib.util.spec_from_file_location("capabilities", FILE)
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)

class GuardTests(unittest.TestCase):
    def test_no_ntp_disables_time(self):
        self.assertFalse(cap.feature_enabled({"time_sync_enabled": True}, "time_sync"))
        self.assertTrue(cap.feature_enabled({"time_sync_enabled": True, "ntp_servers":"0.pool.ntp.org"}, "time_sync"))
        self.assertFalse(cap.feature_enabled({"time_sync_enabled": False, "ntp_servers":"0.pool.ntp.org"}, "time_sync"))
        self.assertFalse(cap.has_ntp({"ntp_servers":"invalid name!"}))

    def test_refraction_requires_both_entities(self):
        conf={"refraction_enabled": True, "temperature_entity":"sensor.outdoor_temp"}
        self.assertFalse(cap.feature_enabled(conf, "refraction"))
        conf["pressure_entity"]="sensor.air_pressure"
        self.assertTrue(cap.feature_enabled(conf, "refraction"))
        self.assertFalse(cap.feature_enabled({**conf, "refraction_enabled":False}, "refraction"))

    def test_write_gates_and_automatic_are_opt_in(self):
        conf={"time_sync_enabled":True, "ntp_servers":"192.168.1.1",
              "native_controls_enabled":True, "legacy_writers_disabled_confirmed":False,
              "auto_time_sync_enabled":True}
        self.assertFalse(cap.write_armed(conf))
        self.assertFalse(cap.auto_allowed(conf,"time_sync"))
        conf["legacy_writers_disabled_confirmed"]=True
        self.assertTrue(cap.auto_allowed(conf, "time_sync"))
        conf["ntp_servers"]=""
        self.assertFalse(cap.auto_allowed(conf,"time_sync"))

    def test_refraction_auto_blocks_missing_sources(self):
        c={"refraction_enabled":True, "auto_refraction_enabled":True,
           "native_controls_enabled":True, "legacy_writers_disabled_confirmed":True,
           "temperature_entity":"sensor.temp"}
        self.assertFalse(cap.auto_allowed(c,"refraction"))
        c["pressure_entity"]="sensor.pressure"
        self.assertTrue(cap.auto_allowed(c,"refraction"))

if __name__ == "__main__":
    unittest.main()
