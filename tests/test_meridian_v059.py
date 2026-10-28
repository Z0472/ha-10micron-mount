"""Offline regression coverage for 10Micron meridian telemetry v0.5.9.

Run: python -m unittest discover -s tests -p 'test_meridian_v059.py'
No HA packages, telescope access or network access required.
"""
import importlib.util
import pathlib
import unittest
from datetime import datetime, timezone

MODULE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "custom_components" / "tenmicron_mount" / "meridian.py"
)
SPEC = importlib.util.spec_from_file_location("meridian_v059", MODULE)
meridian = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(meridian)

NOW = datetime(2026, 10, 18, 21, 0, tzinfo=timezone.utc)


def good(**updates):
    raw = {
        "meridian_track_limit_deg": "10",
        "meridian_slew_limit_deg": "5",
        "horizon_limit_deg": "+33*",
        "tracking_end_minutes": "0004",
        "meridian_allowed_side": "1",
        "unattended_flip": "0",
        "pier_side": "East",
        "sidereal_time": "10:00:00",
        "right_ascension": "10:20:00",
    }
    raw.update(updates)
    return raw


class MeridianTelemetryTests(unittest.TestCase):
    def snapshot(self, raw=None, status=0, tracking=True):
        return meridian.build_meridian_data(
            good() if raw is None else raw,
            status_code=status, tracking=tracking, now=NOW
        )

    def test_realistic_readback_and_alert(self):
        value = self.snapshot()
        self.assertEqual(value["meridian_track_limit_deg"], 10)
        self.assertEqual(value["meridian_slew_limit_deg"], 5)
        self.assertEqual(value["horizon_limit_deg"], 33)
        self.assertEqual(value["meridian_allowed_side"], "Both")
        self.assertEqual(value["pier_side"], "East")
        self.assertIs(value["unattended_flip"], False)
        self.assertEqual(value["tracking_end_minutes"], 4)
        self.assertEqual(value["tracking_end_estimated_utc"], "2026-10-18T21:04:00+00:00")
        self.assertTrue(value["tracking_limit_soon"])
        self.assertTrue(value["tracking_limit_critical"])
        self.assertAlmostEqual(value["hour_angle_minutes"], -20)
        self.assertAlmostEqual(value["meridian_transit_minutes"], 20)
        self.assertTrue(value["meridian_transit_soon"])

    def test_unattended_flip_is_observation_not_predicted_goto(self):
        value = self.snapshot(good(unattended_flip="1", tracking_end_minutes="0045"))
        self.assertIs(value["unattended_flip"], True)
        self.assertIs(value["tracking_limit_soon"], False)
        self.assertIs(value["tracking_limit_critical"], False)
        # 45 min until horizon/flip track END never becomes "45 min to automatic flip".
        self.assertNotIn("flip_minutes", value)

    def test_park_and_slew_never_raise_countdown_warning(self):
        for status in (1, 2, 3, 4, 5, 6, 7, 9, 11):
            with self.subTest(status=status):
                value = self.snapshot(status=status)
                self.assertFalse(value["tracking_limit_soon"])
                self.assertFalse(value["tracking_limit_critical"])
                self.assertFalse(value["meridian_transit_soon"])
                self.assertIsNone(value["tracking_end_estimated_utc"])

    def test_missing_flag_or_bad_minutes_never_means_safe(self):
        value = self.snapshot(good(tracking_end_minutes=None))
        self.assertIsNone(value["tracking_limit_soon"])
        self.assertIsNone(value["tracking_limit_critical"])
        value = self.snapshot(tracking=None)
        self.assertIsNone(value["tracking_limit_soon"])
        self.assertIsNone(value["meridian_transit_soon"])

    def test_invalid_individual_replies_stay_unknown(self):
        value = self.snapshot(good(
            meridian_track_limit_deg="oops",
            meridian_slew_limit_deg="-9",
            horizon_limit_deg="+95*",
            tracking_end_minutes="-1",
            meridian_allowed_side="0",
            pier_side="Unspecified",
            unattended_flip="2",
            sidereal_time="10:99:00",
        ))
        for key in (
            "meridian_track_limit_deg", "meridian_slew_limit_deg",
            "horizon_limit_deg", "tracking_end_minutes",
            "meridian_allowed_side", "pier_side", "unattended_flip",
            "tracking_limit_soon", "tracking_limit_critical",
            "hour_angle_minutes", "meridian_transit_minutes"
        ):
            self.assertIsNone(value[key], key)

    def test_side_codes_and_horizon_formats(self):
        self.assertEqual(self.snapshot(good(meridian_allowed_side="2"))["meridian_allowed_side"], "West only")
        self.assertEqual(self.snapshot(good(meridian_allowed_side="3"))["meridian_allowed_side"], "East only")
        self.assertEqual(self.snapshot(good(horizon_limit_deg="-05*"))["horizon_limit_deg"], -5)
        self.assertEqual(self.snapshot(good(horizon_limit_deg="+33"))["horizon_limit_deg"], 33)

    def test_sidereal_midnight_wrapping_and_after_transit(self):
        before = self.snapshot(good(sidereal_time="23:55:00", right_ascension="00:05:00"))
        self.assertAlmostEqual(before["hour_angle_minutes"], -10)
        self.assertAlmostEqual(before["meridian_transit_minutes"], 10)
        after = self.snapshot(good(sidereal_time="00:05:00", right_ascension="23:55:00"))
        self.assertAlmostEqual(after["hour_angle_minutes"], 10)
        self.assertIsNone(after["meridian_transit_minutes"])
        self.assertIs(after["meridian_transit_soon"], False)

    def test_post_meridian_kocab_scenario(self):
        """Realistic HA snapshot: +34.5 min, 720 min until tracking end."""
        after = self.snapshot(good(
            sidereal_time="10:34:30", right_ascension="10:00:00",
            tracking_end_minutes="0720"))
        self.assertAlmostEqual(after["hour_angle_minutes"], 34.5)
        self.assertIsNone(after["meridian_transit_minutes"])
        self.assertIs(after["meridian_transit_soon"], False)
        self.assertEqual(after["tracking_end_minutes"], 720)
        self.assertIs(after["tracking_limit_soon"], False)
        self.assertIs(after["tracking_limit_critical"], False)

    def test_exact_transit_boundary_before_and_after(self):
        on_meridian = self.snapshot(good(
            sidereal_time="10:00:00", right_ascension="10:00:00"))
        self.assertEqual(on_meridian["meridian_transit_minutes"], 0)
        self.assertIs(on_meridian["meridian_transit_soon"], True)
        just_after = self.snapshot(good(
            sidereal_time="10:00:01", right_ascension="10:00:00"))
        self.assertIsNone(just_after["meridian_transit_minutes"])
        self.assertIs(just_after["meridian_transit_soon"], False)
        just_before = self.snapshot(good(
            sidereal_time="09:59:59", right_ascension="10:00:00"))
        self.assertIs(just_before["meridian_transit_soon"], True)

    def test_unknown_lst_or_ra_does_not_silently_report_off(self):
        for raw in (
            good(sidereal_time=None),
            good(right_ascension=None),
            good(sidereal_time="not a clock"),
            good(right_ascension="10:99:00"),
        ):
            with self.subTest(raw=raw):
                state = self.snapshot(raw)
                self.assertIsNone(state["hour_angle_minutes"])
                self.assertIsNone(state["meridian_transit_soon"])
        # Unknown tracking state is not a confirmed inactive warning.
        self.assertIsNone(self.snapshot(good(
            sidereal_time="10:34:30", right_ascension="10:00:00"
        ), tracking=None)["meridian_transit_soon"])

    def test_warning_threshold_boundaries(self):
        for minutes, soon, critical in ((31, False, False), (30, True, False),
                                        (6, True, False), (5, True, True), (0, True, True)):
            with self.subTest(minutes=minutes):
                v = self.snapshot(good(tracking_end_minutes=str(minutes)))
                self.assertIs(v["tracking_limit_soon"], soon)
                self.assertIs(v["tracking_limit_critical"], critical)


if __name__ == "__main__":
    unittest.main()
