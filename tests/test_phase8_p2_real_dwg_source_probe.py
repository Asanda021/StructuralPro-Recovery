"""Offline negative checks for acquisition provenance; not a DWG acceptance test."""
import unittest
from unittest.mock import patch
from scripts.phase8_p2_real_dwg_source_probe import (
    MAX_BYTES, SOURCE, RestrictedRedirect, approved_url, inspect_dwg, probe,
)


class CandidateProbeTests(unittest.TestCase):
    def test_url_allowlist_is_https_and_exact_host(self):
        self.assertTrue(approved_url(SOURCE))
        self.assertTrue(approved_url("https://files.innerscene.com/a.dwg"))
        for value in (
            "http://www.innerscene.com/a.dwg",
            "https://evil.example/a.dwg",
            "https://files.innerscene.com.evil.example/a",
            "https://user:pass@files.innerscene.com/a",
            "file:///etc/passwd",
        ):
            self.assertFalse(approved_url(value))

    def test_redirect_rejects_untrusted_host(self):
        with self.assertRaises(ValueError):
            RestrictedRedirect().redirect_request(None, None, 302, "move", {}, "https://evil.example/file.dwg")

    def test_signature_and_bounds_fail_closed(self):
        for sample in (b"", b"AC1032", b"notdwg" + b"0" * 1200, b"AC1036" + b"0" * 1200, b"AC1032" + b"0" * MAX_BYTES):
            with self.assertRaises(ValueError):
                inspect_dwg(sample)
        proof = inspect_dwg(b"AC1032" + b"0" * 2000)
        self.assertEqual(proof["dwg_signature"], "AC1032")
        self.assertEqual(len(proof["sha256"]), 64)
        legacy = inspect_dwg(b"AC1009" + b"0" * 2000)
        self.assertFalse(legacy["eligible_for_approved_acadsharp_versions"])
        self.assertEqual(legacy["compatibility"], "LEGACY_VERSION_OUTSIDE_APPROVED_BRIDGE")

    def test_arbitrary_source_cannot_be_substituted(self):
        with self.assertRaises(ValueError):
            probe("https://files.innerscene.com/other.dwg")


if __name__ == "__main__":
    unittest.main()
