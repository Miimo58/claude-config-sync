import os
import tempfile
import unittest
from scripts.lib import secretscan


class TestSecretScan(unittest.TestCase):
    def test_detects_common_tokens(self):
        self.assertTrue(secretscan.scan_text("key sk-abcdefghij1234567890"))
        self.assertTrue(secretscan.scan_text("ghp_ABCDEFGHIJ1234567890abcd"))
        self.assertTrue(secretscan.scan_text("AKIAIOSFODNN7EXAMPLE"))
        self.assertTrue(secretscan.scan_text("-----BEGIN RSA PRIVATE KEY-----"))

    def test_detects_long_secret_valued_keys(self):
        self.assertTrue(secretscan.scan_text('"apiKey": "abcdefghijklmnopqrst1234"'))
        self.assertTrue(secretscan.scan_text('"password": "hunter2hunter2hunter2"'))

    def test_clean_text_returns_empty(self):
        self.assertEqual(secretscan.scan_text("model: opus\ntheme: dark"), [])
        # short / placeholder values are not flagged
        self.assertEqual(secretscan.scan_text('"token": "x"'), [])

    def test_scan_paths_reports_offending_file(self):
        with tempfile.TemporaryDirectory() as d:
            clean = os.path.join(d, "ok.md")
            bad = os.path.join(d, "bad.json")
            with open(clean, "w") as fh:
                fh.write("hello world")
            with open(bad, "w") as fh:
                fh.write("ghp_ABCDEFGHIJ1234567890abcd")
            findings = secretscan.scan_paths([clean, bad])
            self.assertNotIn(clean, findings)
            self.assertIn(bad, findings)
