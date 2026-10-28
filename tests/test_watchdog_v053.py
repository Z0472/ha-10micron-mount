"""WatchMount v8 alarm-status parity (without telescope access)."""
import importlib.util
import pathlib
import unittest

PATH=pathlib.Path(__file__).resolve().parents[1]/'custom_components'/'tenmicron_mount'/'watchdog.py'
spec=importlib.util.spec_from_file_location('gm_watchdog',PATH)
watchdog=importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)

class WatchdogParity(unittest.TestCase):
    def test_parking_park_unpark_home_even_when_not_tracking(self):
        for code in (2,3,4,5):
            with self.subTest(code=code):
                self.assertFalse(watchdog.evaluate(code,False,0)[0])
    def test_dither_grace(self):
        self.assertFalse(watchdog.evaluate(6,False,59.9)[0])
        self.assertTrue(watchdog.evaluate(6,False,60)[0])
    def test_tracking_active_auto_armed(self):
        self.assertEqual(watchdog.evaluate(0,True,0), (False,None,"Tracking – monitored"))
    def test_tracking_disabled_alerts_without_input_boolean(self):
        self.assertTrue(watchdog.evaluate(0,False,0)[0])
    def test_stopped_and_error_states_alert(self):
        for code in (1,7,8,9,11,98,99):
            with self.subTest(code=code):
                self.assertTrue(watchdog.evaluate(code,False,0)[0])
    def test_tracking_telemetry_error_does_not_silently_pass(self):
        self.assertTrue(watchdog.evaluate(0,None,0)[0])
    def test_no_alarm_on_noncritical_unknown_code_with_gtrk_true(self):
        self.assertFalse(watchdog.evaluate(10,True,0)[0])
if __name__=='__main__':unittest.main()
