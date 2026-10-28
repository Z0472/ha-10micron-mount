"""Parse LX200-like angular strings returned by 10Micron."""
import re

ANGLE_RE = re.compile(r"^\s*([+-]?\d{1,3})\s*[^\d+-]+\s*(\d{1,2})(?:\s*[^\d]+\s*(\d{1,2}(?:\.\d+)?))?\s*[^\d]*$")

def parse_angle(raw: str, *, azimuth: bool = False) -> float:
    match = ANGLE_RE.fullmatch(raw)
    if not match:
        raise ValueError(f"Unexpected angle format {raw!r}")
    deg_text, minute_text, sec_text = match.groups()
    degrees = int(deg_text)
    minutes = int(minute_text)
    seconds = float(sec_text) if sec_text else 0.0
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"Invalid DMS angle {raw!r}")
    sign = -1 if deg_text.startswith('-') else 1
    result = sign * (abs(degrees) + minutes / 60 + seconds / 3600)
    if azimuth and not (0 <= result < 360):
        raise ValueError(f"Invalid azimuth {raw!r}")
    if not azimuth and not (-90 <= result <= 90):
        raise ValueError(f"Invalid altitude {raw!r}")
    return round(result, 6)

def angular_distance(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)
