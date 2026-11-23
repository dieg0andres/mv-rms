"""Invented principals and independent origins used only in dashboard tests."""

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

from rms.dashboard_projection import CaseSummary, PipelineSnapshot, SyntheticLedgerSnapshot, Watermark


AS_OF = datetime(2026, 11, 22, 18, tzinfo=UTC)
BOTH = frozenset({"founder_viewer", "editor"})
EDITOR = frozenset({"editor"})
OUTSIDE_SCOPE = frozenset({"unassigned"})


@dataclass(frozen=True)
class FixtureGroups:
    role: str

    def filter(self, *, name=None, name__in=()):
        return SimpleNamespace(exists=lambda: self.role == name or self.role in name__in)


class FixtureAuthenticationBackend:
    def authenticate(self, request, username=None, password=None):
        if username not in {*BOTH, "unassigned", "inactive"} or password != "invented-dashboard-only":
            return None
        return SimpleNamespace(
            groups=FixtureGroups("founder_viewer" if username == "inactive" else username),
            is_authenticated=True,
            is_active=username != "inactive",
        )

    def get_user(self, user_id):
        return None


PIPELINE_CASES = (
    (BOTH, CaseSummary(
        title="Invented maple case", stage="Plan review", owner="Casey Example",
        blocker="Quarantined fixture evidence", next_action="Check <sample> provenance",
        last_changed_at=datetime(2026, 11, 20, 18, tzinfo=UTC),
        health="Blocked", exception="Not eligible for review", authority_mode="Manual approval",
    )),
    (EDITOR, CaseSummary(
        title="Editor-only spruce example", stage="Intake", owner=None,
        blocker=None, next_action=None, last_changed_at=None, health=None,
        exception=None, authority_mode=None,
    )),
    (OUTSIDE_SCOPE, CaseSummary(
        title="Hidden larch sentinel", stage="Review", owner="Hidden owner sentinel",
        blocker="Hidden blocker sentinel", next_action="Hidden action sentinel",
        last_changed_at=None, health="Hidden health sentinel", exception="Hidden exception sentinel",
        authority_mode=None,
    )),
)


class InventedDashboardProvider:
    @staticmethod
    def _visible(actor, roles):
        return bool(actor.is_active and actor.groups.filter(name__in=BOTH & roles).exists())

    @staticmethod
    def _watermark(source, version, freshness="current"):
        return Watermark(source, version, "fixture-policy-1", AS_OF, freshness)

    def pipeline(self, *, actor):
        cases = tuple(case for roles, case in PIPELINE_CASES if self._visible(actor, roles))
        return PipelineSnapshot(self._watermark("Invented case projection", "case-1"), cases)

    def _ledger(self, *, actor, origin, version, examples):
        count = sum(self._visible(actor, roles) for roles, label in examples)
        return SyntheticLedgerSnapshot(self._watermark(origin, version), count)

    def activity(self, *, actor):
        return self._ledger(actor=actor, origin="Invented activity register", version="act-2", examples=(
            (BOTH, "initial trial"), (BOTH, "variant"), (EDITOR, "rerun"), (OUTSIDE_SCOPE, "other trial"),
        ))

    def early_closures(self, *, actor):
        return self._ledger(actor=actor, origin="Invented closure register", version="close-3", examples=(
            (EDITOR, "closed during screening"), (OUTSIDE_SCOPE, "closed during intake"),
        ))

    def full_validation(self, *, actor):
        return self._ledger(actor=actor, origin="Invented cycle register", version="cycle-4", examples=(
            (BOTH, "hypothetical passed example"), (BOTH, "variant"), (BOTH, "rerun"),
            (BOTH, "failed"), (BOTH, "inconclusive"), (OUTSIDE_SCOPE, "out-of-scope example"),
        ))

    def qualifications(self, *, actor):
        return self._ledger(actor=actor, origin="Invented qualification register", version="qual-5", examples=(
            (BOTH, "hypothetical qualification"), (EDITOR, "failed candidate"),
            (EDITOR, "inconclusive candidate"), (OUTSIDE_SCOPE, "out-of-scope example"),
        ))
