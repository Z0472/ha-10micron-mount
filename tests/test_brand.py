"""Check the local Home Assistant brand icon without external packages."""
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "tenmicron_mount"

class BrandIconTests(unittest.TestCase):
    def test_icon_is_transparent_png_in_expected_size(self):
        p = ROOT / "brand" / "icon.png"
        self.assertTrue(p.is_file(), "Missing Home Assistant integration brand icon")
        raw = p.read_bytes()
        self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", raw[16:24])
        self.assertEqual((width, height), (256, 256))
        # PNG palette transparency or RGBA are acceptable.
        self.assertTrue(b"tRNS" in raw or raw[25] in (4, 6))

if __name__ == "__main__":
    unittest.main()
