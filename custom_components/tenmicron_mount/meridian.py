"""Read-only 10Micron meridian / tracking-end telemetry.

:Glmt#: track-through-meridian limit in degrees
:Glms#: GoTo/slew-through-meridian limit in degrees
:Gmte#: estimated minutes until tracking END (horizon OR meridian)
:GMF#: permitted meridian side(s)
:Guaf#: unattended flip enabled, single-character response (optional '#')
:pS#: actual pier side (East / West)
:GS#/:GR#: mount's sidereal time and current RA for signed hour angle

Important: :Gmte# is NOT an exact time-to-flip. An external APT/ASCOM
GoTo can flip at a different time, and unattended flip may be disabled.
No motion or configuration commands are sent by this module.
"""

from datetime import datetime, timedelta, timezone
import re

_SIDES = {1: "Both", 2: "West only", 3: "East only"}
_HMS = re.compile(r"^(\d{1,2}):(\d{2}(?:\.\d+)?)(?::(\d{2}(?:\.\d+)?))?$")


def _integer(raw, minimum, maximum):
    if raw is None or not re.fullmatch(r"\d+", str(raw).strip()):
        return None
    number = int(str(raw).strip())
    return number if minimum <= number <= maximum else None


def _horizon_degrees(raw):
    # :Go# may return signed DD* (high/low) or signed DD (ultra).
    value = str(raw or "").strip()
    if not re.fullmatch(r"[+-]?\d{1,2}\*?", value):
        return None
    degrees = int(value.rstrip("*"))
    return degrees if -5 <= degrees <= 90 else None


def _clock_hours(raw):
    match = _HMS.fullmatch(str(raw or "").strip())
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    h, m, s = int(hours), float(minutes), float(seconds or 0)
    if h > 23 or m >= 60 or s >= 60:
        return None
    return h + m / 60 + s / 3600


def build_meridian_data(raw, *, status_code, tracking, now=None):
    """Convert independently polled responses to HA-safe values.

    A missing/invalid response produces None (unknown), never a safe 'False'
    warning state. Out-of-tracking states do not emit false countdown alerts.
    """
    now = now or datetime.now(timezone.utc)
    result = {
        "meridian_track_limit_deg": _integer(raw.get("meridian_track_limit_deg"), 0, 30),
        "meridian_slew_limit_deg": _integer(raw.get("meridian_slew_limit_deg"), 0, 30),
        "horizon_limit_deg": _horizon_degrees(raw.get("horizon_limit_deg")),
        "tracking_end_minutes": _integer(raw.get("tracking_end_minutes"), 0, 9999),
        "meridian_allowed_side_code": _integer(raw.get("meridian_allowed_side"), 1, 3),
        "unattended_flip": None,
        "pier_side": None,
        "hour_angle_minutes": None,
        "meridian_transit_minutes": None,
        "tracking_end_estimated_utc": None,
        "tracking_limit_soon": None,
        "tracking_limit_critical": None,
        "meridian_transit_soon": None,
    }
    result["meridian_allowed_side"] = _SIDES.get(result["meridian_allowed_side_code"])
    flip_raw = str(raw.get("unattended_flip") or "").strip().rstrip("#")
    if flip_raw in ("0", "1"):
        result["unattended_flip"] = flip_raw == "1"
    side = str(raw.get("pier_side") or "").strip()
    result["pier_side"] = side if side in ("East", "West") else None

    lst = _clock_hours(raw.get("sidereal_time"))
    ra = _clock_hours(raw.get("right_ascension"))
    if lst is not None and ra is not None:
        # Signed local hour angle in (-12h, +12h]. Positive = after transit.
        ha_minutes = ((lst - ra + 12) % 24 - 12) * 60
        result["hour_angle_minutes"] = round(ha_minutes, 2)
        if ha_minutes <= 0:
            result["meridian_transit_minutes"] = round(-ha_minutes, 2)

    active = (status_code == 0 and tracking is True)
    if active:
        end = result["tracking_end_minutes"]
        if end is not None:
            result["tracking_limit_soon"] = end <= 30
            result["tracking_limit_critical"] = end <= 5
            result["tracking_end_estimated_utc"] = (
                now + timedelta(minutes=end)
            ).isoformat()
        transit = result["meridian_transit_minutes"]
        if transit is not None:
            result["meridian_transit_soon"] = transit <= 30
        elif result["hour_angle_minutes"] is not None and result["hour_angle_minutes"] > 0:
            # Valid LST/RA confirm that the object already crossed the
            # meridian. There is no upcoming transit to warn about.
            # Do not confuse this with a missing telemetry reading.
            result["meridian_transit_soon"] = False
    elif status_code in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 98, 99) or tracking is False:
        result["tracking_limit_soon"] = False
        result["tracking_limit_critical"] = False
        result["meridian_transit_soon"] = False
    # A tracking state with an unreadable flag remains unknown.
    return result
