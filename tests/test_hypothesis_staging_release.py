"""Pure package identity/static dispatch checks; no server or Docker build."""

from hashlib import sha256
import os
from pathlib import Path
import tempfile
import unittest

from staging.release_identity import ASSETS, LEGACY_COMMIT, LEGACY_TREE, validate_release, verified_asset, version_page_requested


class ReleaseIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("PAPERCLIP_RUN_SCRATCH_DIR"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = self.root / "releases/product"
        self.release.mkdir(parents=True)
        paths = ("rms_project/urls.py", "rms/navigation_urls.py", "rms/hypothesis_api_urls.py", *(url.lstrip("/") for url in ASSETS))
        inventory = {}
        for name in paths:
            path = self.release / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"Invented pinned content\n")
            inventory[name] = sha256(path.read_bytes()).hexdigest()
        self.metadata = {"package_version": 2, "integrated_navigation": True, "commit": "a" * 40, "tree": "b" * 40, "file_sha256": inventory}

    def test_integrated_home_reaches_application_and_version_endpoint_stays_available(self):
        self.assertEqual(validate_release(self.root, self.metadata), self.release)
        self.assertFalse(version_page_requested("/", self.metadata))
        self.assertTrue(version_page_requested("/__staging/version", self.metadata))

    def test_every_allowlisted_integrated_asset_is_verified_and_typed(self):
        for url, mime in ASSETS.items():
            with self.subTest(url=url):
                self.assertEqual(verified_asset(url, self.release, self.metadata), (b"Invented pinned content\n", mime))
        self.assertIsNone(verified_asset("/static/../../private", self.release, self.metadata))

    def test_tampered_product_or_static_is_rejected(self):
        (self.release / "static/rms/record_form.js").write_text("Invented changed script")
        with self.assertRaises(ValueError):
            validate_release(self.root, self.metadata)
        with self.assertRaises(ValueError):
            verified_asset("/static/rms/record_form.js", self.release, self.metadata)

    def test_missing_routes_asset_inventory_or_path_escape_is_rejected(self):
        del self.metadata["file_sha256"]["rms_project/urls.py"]
        with self.assertRaises(ValueError):
            validate_release(self.root, self.metadata)

    def test_existing_legacy_package_keeps_its_original_pin_and_home(self):
        legacy = self.root / "releases" / LEGACY_COMMIT
        path = legacy / "static/rms/rms_forms.js"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"Invented legacy asset")
        metadata = {"commit": LEGACY_COMMIT, "tree": LEGACY_TREE, "static_sha256": sha256(path.read_bytes()).hexdigest()}
        self.assertEqual(validate_release(self.root, metadata), legacy)
        self.assertTrue(version_page_requested("/", metadata))
        metadata["commit"] = "c" * 40
        with self.assertRaises(ValueError):
            validate_release(self.root, metadata)
