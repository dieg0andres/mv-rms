import unittest

from rms import (
    DuplicateSourceVersionError,
    NonSyntheticSourceError,
    SourceOverwriteError,
    SourceVersion,
    SourceVersionKernel,
)


SOURCE_ID = "synthetic-source-001"
V1_BYTES = b"invented Source version one"
V2_BYTES = b"invented Source version two correction"


def source_v1(*, synthetic: bool | None = True) -> SourceVersion:
    return SourceVersion(
        source_id=SOURCE_ID,
        version=1,
        content=V1_BYTES,
        synthetic=synthetic,
    )


def source_v2() -> SourceVersion:
    return SourceVersion(
        source_id=SOURCE_ID,
        version=2,
        content=V2_BYTES,
        synthetic=True,
        corrects_version=1,
    )


class SourceVersionKernelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kernel = SourceVersionKernel()

    def test_creates_invented_source_v1(self) -> None:
        v1 = source_v1()

        self.assertIs(self.kernel.add(v1), v1)
        self.assertIs(self.kernel.get(SOURCE_ID, 1), v1)

    def test_appends_v2_under_stable_identity_and_exposes_it_as_latest(self) -> None:
        v1 = source_v1()
        v2 = source_v2()
        self.kernel.add(v1)

        self.kernel.add(v2)

        self.assertEqual(v1.source_id, v2.source_id)
        self.assertIs(self.kernel.latest(SOURCE_ID), v2)
        self.assertEqual(self.kernel.latest(SOURCE_ID).version, 2)

    def test_v2_correction_preserves_v1_bytes_and_retrieval(self) -> None:
        v1 = source_v1()
        original_v1_bytes = v1.content
        self.kernel.add(v1)
        self.kernel.add(source_v2())

        retrieved_v1 = self.kernel.get(SOURCE_ID, 1)

        self.assertIs(retrieved_v1, v1)
        self.assertEqual(retrieved_v1.content, original_v1_bytes)

    def test_rejects_overwrite_of_an_existing_version(self) -> None:
        self.kernel.add(source_v1())
        changed_v1 = SourceVersion(
            source_id=SOURCE_ID,
            version=1,
            content=b"changed invented bytes",
            synthetic=True,
        )

        with self.assertRaises(SourceOverwriteError):
            self.kernel.add(changed_v1)

        self.assertEqual(self.kernel.get(SOURCE_ID, 1).content, V1_BYTES)

    def test_rejects_duplicate_version(self) -> None:
        v1 = source_v1()
        self.kernel.add(v1)

        with self.assertRaises(DuplicateSourceVersionError):
            self.kernel.add(v1)

        self.assertIs(self.kernel.latest(SOURCE_ID), v1)

    def test_rejects_source_not_explicitly_marked_synthetic(self) -> None:
        for synthetic in (False, None):
            with self.subTest(synthetic=synthetic):
                with self.assertRaises(NonSyntheticSourceError):
                    self.kernel.add(source_v1(synthetic=synthetic))

        with self.assertRaises(NonSyntheticSourceError):
            self.kernel.add(
                SourceVersion(
                    source_id=SOURCE_ID,
                    version=1,
                    content=V1_BYTES,
                    synthetic=1,
                )
            )


if __name__ == "__main__":
