"""SOURCE ONLY: idempotent invented fixture on a separately authorized facility."""

import hashlib
import json
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from rms.hypothesis_fixture import hypothesis_fields
from rms.hypothesis_models import HypothesisVersion
from rms.hypothesis_services import create_hypothesis, correct_hypothesis
from rms.hypothesis_validation import SCHEMA
from rms.models import IdempotencyRecord, Idea, Source
from rms.research_context_common import lock_lineage, require_actor
from rms.research_context_services import create_investigation, create_research_family
from rms.services import canonical_json_bytes, create_idea, correct_idea, create_source


FIXTURE_ID = "RMS-HN-F1-20261003"
SOURCE_ID = "synthetic-hn-f1-20261003"


def unpack(stored):
    return json.loads(stored.body)


class Command(BaseCommand):
    help = "Add invented HN-F1 records without changing existing records. Requires separate DB authorization."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True, help="Existing editor username; creates no account or grant.")
        parser.add_argument("--review-time", required=True, help="Explicit fictional review UTC timestamp ending in Z.")

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(username=options["actor"])
            require_actor(actor, write=True)
            if not options["review_time"].endswith("Z"):
                raise ValueError("UTC review timestamp required")
            review_time = datetime.fromisoformat(options["review_time"])
            if review_time.tzinfo is None:
                raise ValueError("UTC review timestamp required")
            self.load(actor, options["review_time"])
        except (get_user_model().DoesNotExist, ValueError) as error:
            raise CommandError("Supply an existing editor and an explicit UTC fictional review time.") from error

    def load(self, actor, review_time):
        digest = hashlib.sha256(canonical_json_bytes({"fixture": FIXTURE_ID, "actor": str(actor.pk), "review_time": review_time})).hexdigest()
        with transaction.atomic():
            lock_lineage()
            marker = IdempotencyRecord.objects.filter(key=FIXTURE_ID).first()
            if marker is not None:
                if marker.request_sha256 != digest:
                    raise CommandError("Fixture identity conflicts with different actor or review time; nothing changed.")
                saved = json.loads(bytes(marker.response_bytes))
                for item in saved["hypothesis_versions"]:
                    version = HypothesisVersion.objects.get(public_id=item["version_id"])
                    if version.row_digest != item["row_digest"]:
                        raise CommandError("Fixture history digest mismatch; nothing changed.")
                self.stdout.write(FIXTURE_ID + " unchanged")
                return
            if Source.objects.filter(source_id=SOURCE_ID).exists():
                raise CommandError("Fixture Source identity already exists without its receipt; nothing changed.")
            def key(action):
                return FIXTURE_ID + ":" + action
            source = unpack(create_source(
                source_id=SOURCE_ID, content=b"Invented next-session reversal fixture only. No research evidence.",
                fields={"title": "Invented HN source", "source_type": "other", "citation": "RMS-HN-F1 invented fixture",
                        "observed_available_at": datetime.fromisoformat("2026-10-03T00:00:00+00:00"), "authors": None,
                        "publisher": None, "published_at": None, "canonical_url": None, "rights_note": "Invented software fixture; no external material."},
                actor=actor.get_username(), idempotency_key=key("source"), request_path="/api/v1/sources",
            ))
            idea_fields = {"title": "Invented transient selling pressure", "mechanism": "Fictional temporary liquidity pressure.",
                           "testable_claim": "Invented next-session reversal proposition.", "falsification": "Later valid research may find no predicted advantage.",
                           "eligible_market": "etfs", "workflow_status": "draft", "rejection_reason": None}
            contributions = [{"source_version_id": source["latest_source_version_id"], "contribution": "Invented supporting rationale, not empirical evidence."}]
            idea = unpack(create_idea(fields=idea_fields, contributions=contributions, actor=actor.get_username(),
                                     idempotency_key=key("idea"), request_path="/api/v1/ideas"))
            family = unpack(create_research_family(actor=actor, idempotency_key=key("family"), payload={"fields": {
                "name": "Invented temporary liquidity pressure", "mechanism_boundary": "Temporary price pressure variants; fictional grouping.",
                "distinctness_rule": "Shared liquidity mechanism; no novelty or research-cycle credit.", "risk_review_reference": None}}))
            case = unpack(create_investigation(actor=actor, idempotency_key=key("case"), payload={
                "family_version_id": family["family_version_id"],
                "fields": {"title": "Invented next-session reversal", "owner_role": "Research", "priority": "normal", "next_action": "Review fictional draft fields", "blocker_text": "No research execution is authorized."},
                "prior_research_assessment": {
                    "query_scope": "Selected saved HN-F1 Source, Idea and family only; fictional manual-review example.", "query_time": review_time,
                    "policy_version": SCHEMA["$defs"]["AssessmentFields"]["properties"]["policy_version"]["const"],
                    "result_watermark": "Exact saved versions named in record_links, inspected by the fixture recipe only.",
                    "finding": "extends", "rationale": "Fictional case extends the selected invented Idea within its explicitly selected family.",
                    "limitations": "This is an invented manual assessment, not a completed human novelty search; no real or other family records were reviewed.",
                    "record_links": [{"kind": "source", "version_id": source["latest_source_version_id"]}, {"kind": "idea", "version_id": idea["latest_idea_version_id"]}, {"kind": "research_family", "version_id": family["family_version_id"]}],
                }}))
            payload = {"originating_idea_version_id": idea["latest_idea_version_id"], "origin_rationale": "Explicit fictional direct origin; no research approval.",
                       "investigation_version_id": case["investigation_version_id"],
                       "idea_family_binding": {"mode": "create", "family_version_id": family["family_version_id"], "rationale": "Explicit fixture editor confirmation: this Idea fits the fictional liquidity-pressure family."},
                       "fields": hypothesis_fields()}
            first = unpack(create_hypothesis(actor=actor, idempotency_key=key("hypothesis"), payload=payload))
            sibling_payload = {**payload, "fields": {**payload["fields"], "title": "Invented sibling liquidity-pressure variant"},
                               "idea_family_binding": {"mode": "existing", "association_version_id": first["research_context"]["idea_family_association"]["version_id"]}}
            sibling = unpack(create_hypothesis(actor=actor, idempotency_key=key("sibling"), payload=sibling_payload))
            changed_idea = unpack(correct_idea(idea_id=idea["idea_id"], fields={**idea_fields, "mechanism": "Revised invented liquidity-pressure description; no result."}, contributions=contributions,
                                               actor=actor.get_username(), expected_latest_version=1, correction_reason="Correct invented mechanism wording.",
                                               idempotency_key=key("idea-correction"), request_path=f"/api/v1/ideas/{idea['idea_id']}/corrections"))
            corrected_payload = {**payload, "originating_idea_version_id": changed_idea["latest_idea_version_id"], "expected_latest_version": 1,
                                 "correction_reason": "Explicitly adopt invented Idea v2 and revise one entry rule.",
                                 "fields": {**payload["fields"], "entry_conditions": payload["fields"]["entry_conditions"] + " Skip an entry if the fictional instrument is marked unavailable."}}
            second = unpack(correct_hypothesis(actor=actor, hypothesis_id=first["hypothesis_id"], idempotency_key=key("hypothesis-correction"), payload=corrected_payload))
            receipt = {"fixture": FIXTURE_ID, "family_id": family["family_id"], "investigation_id": case["investigation_id"],
                       "hypothesis_versions": [{"version_id": item["hypothesis_version_id"], "row_digest": item["row_digest"]} for item in (first, second, sibling)]}
            IdempotencyRecord.objects.create(key=FIXTURE_ID, request_method="POST", request_path="management:load_rms_hn_fixture", request_sha256=digest,
                                             response_status=201, response_identity=FIXTURE_ID, response_bytes=canonical_json_bytes(receipt))
        self.stdout.write(json.dumps(receipt, sort_keys=True))
