"""Read-only contract for the synthetic dashboard; no record storage or credit rules."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol


@dataclass(frozen=True)
class Watermark:
    source: str
    version: str
    policy_version: str
    as_of: datetime
    freshness: Literal["current", "stale", "unknown"]


@dataclass(frozen=True)
class CaseSummary:
    title: str
    stage: str
    owner: str | None
    blocker: str | None
    next_action: str | None
    last_changed_at: datetime | None
    health: str | None
    exception: str | None
    authority_mode: str | None


@dataclass(frozen=True)
class PipelineSnapshot:
    watermark: Watermark
    cases: tuple[CaseSummary, ...]


@dataclass(frozen=True)
class SyntheticLedgerSnapshot:
    watermark: Watermark
    example_count: int


class DashboardSourceUnavailable(Exception):
    """An adapter may use this to report a known source outage without exposing details."""


class DashboardProvider(Protocol):
    """Only return authorized, synthetic projection data for the supplied actor."""

    def pipeline(self, *, actor) -> PipelineSnapshot | None: ...
    def activity(self, *, actor) -> SyntheticLedgerSnapshot | None: ...
    def early_closures(self, *, actor) -> SyntheticLedgerSnapshot | None: ...
    def full_validation(self, *, actor) -> SyntheticLedgerSnapshot | None: ...
    def qualifications(self, *, actor) -> SyntheticLedgerSnapshot | None: ...


LEDGERS = (
    ("activity", "Activity and trials", False),
    ("early_closures", "Early closures", False),
    ("full_validation", "Countable full-validation cycles", True),
    ("qualifications", "Qualifications", True),
)


def _read_projection(read, *, actor):
    try:
        return read(actor=actor)
    except DashboardSourceUnavailable:
        return None


def dashboard_context(*, actor, provider: DashboardProvider | None):
    pipeline = _read_projection(provider.pipeline, actor=actor) if provider else None
    ledgers = []
    for key, title, is_credit_ledger in LEDGERS:
        snapshot = _read_projection(getattr(provider, key), actor=actor) if provider else None
        current = snapshot is not None and snapshot.watermark.freshness == "current"
        ledgers.append({
            "key": key,
            "title": title,
            "watermark": snapshot.watermark if snapshot is not None else None,
            "example_count": snapshot.example_count if current else None,
            "zero_credit": current and is_credit_ledger,
        })
    return {"pipeline": pipeline, "ledgers": ledgers}
