"""Package tests use invented Git archives and never build or deploy a service."""

from hashlib import sha256
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from staging import release_identity


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("PAPERCLIP_RUN_SCRATCH_DIR"))
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "package"
        spec = importlib.util.spec_from_file_location("hn_package", Path(__file__).resolve().parents[1] / "staging/build-hn-package.py")
        self.builder = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"release_identity": release_identity}):
            spec.loader.exec_module(self.builder)
        self.files = {name: b"Invented archive input\n" for name in (
            "rms_project/urls.py", "rms/navigation_urls.py", "rms/hypothesis_api_urls.py",
            *(url.lstrip("/") for url in release_identity.ASSETS),
            *("staging/" + name for name in ("Dockerfile.hn", "compose.yaml", "entrypoint.sh", "requirements-staging.lock", "runtime.py", "request_policy.py", "release_identity.py", "create-principals.py", "README.md")),
        )}
        manifest = {"files": [{"path": name, "bytes": len(data), "sha256": sha256(data).hexdigest()} for name, data in sorted(self.files.items())]}
        self.files["docs/RMS-HN-INTEGRATED-SOURCE-MANIFEST.json"] = json.dumps(manifest).encode()

    def archive(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for name, data in self.files.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        return buffer.getvalue()

    def git(self, *args):
        return b"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n" if args[0] == "rev-parse" else self.archive()

    def test_explicit_commit_package_contains_only_archive_bound_recipe_and_manifest(self):
        with patch.object(self.builder, "git", side_effect=self.git):
            metadata = self.builder.build(self.output, "a" * 40, "b" * 40)
        self.assertEqual(metadata["package_version"], 2)
        self.assertEqual(metadata["file_sha256"], {name: sha256(data).hexdigest() for name, data in self.files.items()})
        self.assertEqual((self.output / "runtime.py").read_bytes(), self.files["staging/runtime.py"])
        self.assertEqual((self.output / "Dockerfile").read_bytes(), self.files["staging/Dockerfile.hn"])
        compressed = (self.output / "product.tar.gz").read_bytes()
        self.assertEqual((self.output / "product.tar.gz.sha256").read_text(), sha256(compressed).hexdigest() + "  product.tar.gz\n")

    def test_tree_mismatch_does_not_create_output(self):
        with patch.object(self.builder, "git", side_effect=self.git), self.assertRaisesRegex(ValueError, "commit/tree mismatch"):
            self.builder.build(self.output, "a" * 40, "c" * 40)
        self.assertFalse(self.output.exists())

    def test_manifest_mismatch_does_not_create_output(self):
        self.files["rms_project/urls.py"] = b"Invented tampered routes"
        with patch.object(self.builder, "git", side_effect=self.git), self.assertRaisesRegex(ValueError, "differs from integrated manifest"):
            self.builder.build(self.output, "a" * 40, "b" * 40)
        self.assertFalse(self.output.exists())

    def test_existing_package_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / "sentinel"
        sentinel.write_bytes(b"Preserved evidence")
        with patch.object(self.builder, "git", side_effect=self.git), self.assertRaisesRegex(ValueError, "overwrite"):
            self.builder.build(self.output, "a" * 40, "b" * 40)
        self.assertEqual(sentinel.read_bytes(), b"Preserved evidence")

    def test_moving_or_partial_git_refs_are_rejected_before_git(self):
        with patch.object(self.builder, "git") as git, self.assertRaises(ValueError):
            self.builder.build(self.output, "HEAD", "b" * 40)
        git.assert_not_called()

    def test_two_packages_have_identical_archive_and_metadata(self):
        with patch.object(self.builder, "git", side_effect=self.git):
            self.builder.build(self.output, "a" * 40, "b" * 40)
            other = self.output.with_name("second-package")
            self.builder.build(other, "a" * 40, "b" * 40)
        for name in ("metadata.json", "product.tar.gz", "product.tar.gz.sha256"):
            self.assertEqual((self.output / name).read_bytes(), (other / name).read_bytes())
