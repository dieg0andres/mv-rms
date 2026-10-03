"""Append-only identity and version rules for synthetic RMS Sources."""

from dataclasses import dataclass


class SourceVersionError(ValueError):
    """Base error for rejected Source versions."""


class NonSyntheticSourceError(SourceVersionError):
    """Raised when a Source is not explicitly marked synthetic."""


class DuplicateSourceVersionError(SourceVersionError):
    """Raised when an identical logical ID and version already exists."""


class SourceOverwriteError(SourceVersionError):
    """Raised when an existing Source version would be changed."""


class SourceVersionSequenceError(SourceVersionError):
    """Raised when a Source version does not extend the current history."""


@dataclass(frozen=True, slots=True)
class SourceVersion:
    """One immutable version of a synthetic Source."""

    source_id: str
    version: int
    content: bytes
    synthetic: bool | None
    corrects_version: int | None = None


class SourceVersionKernel:
    """In-memory append-only Source version kernel."""

    def __init__(self) -> None:
        self._versions: dict[str, dict[int, SourceVersion]] = {}

    def add(self, record: SourceVersion) -> SourceVersion:
        """Create v1 or append the next correction without rewriting history."""
        self._validate_record(record)
        history = self._versions.get(record.source_id)

        if history is None:
            if record.version != 1 or record.corrects_version is not None:
                raise SourceVersionSequenceError(
                    "a new Source must start at version 1 without a correction link"
                )
            self._versions[record.source_id] = {1: record}
            return record

        existing = history.get(record.version)
        if existing is not None:
            if existing == record:
                raise DuplicateSourceVersionError(
                    f"Source {record.source_id!r} version {record.version} already exists"
                )
            raise SourceOverwriteError(
                f"Source {record.source_id!r} version {record.version} is immutable"
            )

        latest_version = max(history)
        if (
            record.version != latest_version + 1
            or record.corrects_version != latest_version
        ):
            raise SourceVersionSequenceError(
                "a correction must be the next version and link to the latest version"
            )

        history[record.version] = record
        return record

    def get(self, source_id: str, version: int) -> SourceVersion:
        """Return an exact historical Source version."""
        return self._versions[source_id][version]

    def latest(self, source_id: str) -> SourceVersion:
        """Return the highest Source version for a stable logical ID."""
        history = self._versions[source_id]
        return history[max(history)]

    def history(self, source_id: str) -> tuple[SourceVersion, ...]:
        """Return an ordered, immutable snapshot of a Source's history."""
        history = self._versions[source_id]
        return tuple(history[version] for version in sorted(history))

    @staticmethod
    def _validate_record(record: SourceVersion) -> None:
        if record.synthetic is not True:
            raise NonSyntheticSourceError(
                "Source versions must be explicitly marked synthetic=True"
            )
        if not isinstance(record.source_id, str) or not record.source_id:
            raise SourceVersionError("source_id must be a non-empty string")
        if type(record.content) is not bytes:
            raise SourceVersionError("content must be immutable bytes")
        if not isinstance(record.version, int) or isinstance(record.version, bool):
            raise SourceVersionError("version must be an integer")
