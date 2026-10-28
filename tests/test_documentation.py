"""Check user-facing docs and release packaging without HA dependencies."""
import pathlib
import unittest

BASE=pathlib.Path(__file__).resolve().parents[1]
class DocumentationTests(unittest.TestCase):
    def test_links_and_key_topics(self):
        readme=(BASE/"README.md").read_text(encoding="utf-8")
        for language in ("CS","EN"):
            path=BASE/f"docs/USER_GUIDE_{language}.md"
            self.assertTrue(path.is_file())
            self.assertIn(f"docs/USER_GUIDE_{language}.md", readme)
            content=path.read_text(encoding="utf-8")
            self.assertGreater(len(content), 3500)
        cs=(BASE/"docs/USER_GUIDE_CS.md").read_text(encoding="utf-8")
        en=(BASE/"docs/USER_GUIDE_EN.md").read_text(encoding="utf-8")
        for token in ("120", "60", "100", "999", "1,0", "2,0", "refrakce", "NTP"):
            self.assertIn(token,cs)
        for token in ("120", "60", "100", "999", "1.0", "2.0", "refraction", "NTP"):
            self.assertIn(token,en)
        workflow=(BASE/".github/workflows/check.yml").read_text()
        self.assertIn('root / "docs"',workflow)
        self.assertIn('"docs/USER_GUIDE_CS.md"',workflow)
        self.assertIn('"docs/USER_GUIDE_EN.md"',workflow)
if __name__ == "__main__":
    unittest.main()
