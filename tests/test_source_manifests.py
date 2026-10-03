import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError

from rms import (
    SOURCE_MANIFEST_SCHEMA_VERSION,
    SourceManifestVerificationError,
    SourceVersion,
    SourceVersionKernel,
    generate_source_manifest,
    source_manifest_digest,
    verify_source_manifest,
)


SOURCE_ID = "synthetic-source-001"
V1_BYTES = b"invented Source version one"
V2_BYTES = b"invented Source version two correction"


def source_v1(*, content: bytes = V1_BYTES) -> SourceVersion:
    return SourceVersion(
        source_id=SOURCE_ID,
        version=1,
        content=content,
        synthetic=True,
    )


def source_v2() -> SourceVersion:
    return SourceVersion(
        source_id=SOURCE_ID,
        version=2,
        content=V2_BYTES,
        synthetic=True,
        corrects_version=1,
    )


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


class SourceHistoryTests(unittest.TestCase):
    def test_history_is_ordered_immutable_snapshot(self) -> None:
        kernel = SourceVersionKernel()
        v1 = source_v1()
        v2 = source_v2()
        kernel.add(v1)
        kernel.add(v2)

        history = kernel.history(SOURCE_ID)

        self.assertEqual(history, (v1, v2))
        self.assertIs(history[0], v1)
        self.assertIs(history[1], v2)
        with self.assertRaises(TypeError):
            history[0] = v2  # type: ignore[index]
        with self.assertRaises(FrozenInstanceError):
            history[0].content = b"changed"  # type: ignore[misc]

    def test_kernel_rejects_mutable_content(self) -> None:
        kernel = SourceVersionKernel()
        mutable_content = bytearray(V1_BYTES)

        with self.assertRaises(ValueError):
            kernel.add(
                SourceVersion(
                    source_id=SOURCE_ID,
                    version=1,
                    content=mutable_content,  # type: ignore[arg-type]
                    synthetic=True,
                )
            )


class SourceManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.v1 = source_v1()
        self.v2 = source_v2()
        self.versions = (self.v1, self.v2)
        self.manifest = generate_source_manifest(self.versions)
        self.digest = source_manifest_digest(self.manifest)

    def decoded_manifest(self) -> dict[str, object]:
        return json.loads(self.manifest.decode("utf-8"))

    def test_manifest_records_exact_metadata_and_hashes_without_raw_content(self) -> None:
        decoded = self.decoded_manifest()
        entries = decoded["versions"]

        self.assertEqual(decoded["schema_version"], SOURCE_MANIFEST_SCHEMA_VERSION)
        self.assertEqual([entry["version"] for entry in entries], [1, 2])
        self.assertEqual([entry["source_id"] for entry in entries], [SOURCE_ID] * 2)
        self.assertEqual([entry["corrects_version"] for entry in entries], [None, 1])
        self.assertEqual([entry["synthetic"] for entry in entries], [True, True])
        self.assertEqual(
            [entry["byte_length"] for entry in entries],
            [len(V1_BYTES), len(V2_BYTES)],
        )
        self.assertEqual(
            [entry["content_sha256"] for entry in entries],
            [hashlib.sha256(V1_BYTES).hexdigest(), hashlib.sha256(V2_BYTES).hexdigest()],
        )
        self.assertNotIn(V1_BYTES, self.manifest)
        self.assertNotIn(V2_BYTES, self.manifest)
        self.assertNotIn("content", entries[0])
        self.assertEqual(self.manifest, canonical_bytes(decoded))

    def test_generation_and_digest_are_byte_for_byte_deterministic(self) -> None:
        repeated_manifest = generate_source_manifest(self.versions)

        self.assertEqual(repeated_manifest, self.manifest)
        self.assertEqual(source_manifest_digest(repeated_manifest), self.digest)
        self.assertEqual(self.digest, hashlib.sha256(self.manifest).hexdigest())

    def test_adding_v2_does_not_change_v1_entry_or_content(self) -> None:
        kernel = SourceVersionKernel()
        original_v1_content = self.v1.content
        kernel.add(self.v1)
        v1_manifest = json.loads(generate_source_manifest(kernel.history(SOURCE_ID)))
        original_v1_entry = dict(v1_manifest["versions"][0])

        kernel.add(self.v2)
        v2_manifest = json.loads(generate_source_manifest(kernel.history(SOURCE_ID)))

        self.assertEqual(v2_manifest["versions"][0], original_v1_entry)
        self.assertEqual(kernel.get(SOURCE_ID, 1).content, original_v1_content)

    def test_verifies_unchanged_manifest(self) -> None:
        self.assertIsNone(
            verify_source_manifest(self.manifest, self.digest, self.versions)
        )

    def test_rejects_malformed_schema(self) -> None:
        for malformed in (
            {"schema_version": 2, "versions": self.decoded_manifest()["versions"]},
            {"schema_version": 1},
            {**self.decoded_manifest(), "unexpected": True},
        ):
            with self.subTest(malformed=malformed):
                manifest = canonical_bytes(malformed)
                with self.assertRaises(SourceManifestVerificationError):
                    verify_source_manifest(
                        manifest, source_manifest_digest(manifest), self.versions
                    )

    def test_rejects_missing_version(self) -> None:
        changed = self.decoded_manifest()
        changed["versions"] = changed["versions"][:1]
        self.assert_changed_manifest_rejected(changed)

    def test_rejects_reordered_versions(self) -> None:
        changed = self.decoded_manifest()
        changed["versions"] = list(reversed(changed["versions"]))
        self.assert_changed_manifest_rejected(changed)

    def test_rejects_duplicate_version(self) -> None:
        changed = self.decoded_manifest()
        changed["versions"] = [changed["versions"][0], changed["versions"][0]]
        self.assert_changed_manifest_rejected(changed)

    def test_rejects_broken_correction_link(self) -> None:
        changed = self.decoded_manifest()
        changed["versions"][1]["corrects_version"] = None
        self.assert_changed_manifest_rejected(changed)

    def test_rejects_changed_metadata(self) -> None:
        changed = self.decoded_manifest()
        changed["versions"][0]["byte_length"] += 1
        self.assert_changed_manifest_rejected(changed)

    def test_rejects_changed_content_bytes(self) -> None:
        changed_versions = (source_v1(content=b"changed invented bytes"), self.v2)

        with self.assertRaises(SourceManifestVerificationError):
            verify_source_manifest(self.manifest, self.digest, changed_versions)

    def test_rejects_digest_mismatch(self) -> None:
        with self.assertRaises(SourceManifestVerificationError):
            verify_source_manifest(self.manifest, "0" * 64, self.versions)

    def assert_changed_manifest_rejected(self, changed: object) -> None:
        manifest = canonical_bytes(changed)
        with self.assertRaises(SourceManifestVerificationError):
            verify_source_manifest(
                manifest, source_manifest_digest(manifest), self.versions
            )
