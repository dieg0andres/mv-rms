"""RR14 synthetic-only read authority. Never derives a grant from a write."""

from contextvars import ContextVar
import json
from pathlib import Path

from django.conf import settings
from django.db.models import Exists, F, OuterRef, Q, Value
from django.db.models.functions import Concat
from django.http import HttpResponseNotAllowed
from django.utils.cache import add_never_cache_headers

from .hypothesis_models import (
    AUTHORITY_REFERENCE, HypothesisVersion, InvestigationVersion,
    PriorResearchAssessmentVersion, ResearchAssociation, ResearchFamilyVersion,
)
from .permissions import has_rms_read_access
from .models import IdempotencyRecord
from .services import ResourceNotFound
from .test_plan_models import AUTHORITY_REFERENCE as PLAN_AUTHORITY
from .test_plan_models import TestPlanAssociation, TestPlanVersion


_snapshot = ContextVar('rr14_scope_snapshot', default=None)

_PRIVATE_JSON_RESOURCES = frozenset({
    'test-plans', 'criterion-profiles', 'data-requirements',
    'hypotheses', 'investigations', 'research-families',
    'prior-research-assessments', 'idea-family-associations',
})

_HELD_BROWSER_WRITES = frozenset()


def _load():
    path = getattr(settings, 'RMS_RR14_SCOPE_FILE', '')
    if not path:
        return {}
    try:
        with Path(path).open('rb') as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            return {}
        document = json.loads(raw, object_pairs_hook=_unique_keys)
        if not isinstance(document, dict) or set(document) != {'format', 'principals'}:
            return {}
        if document['format'] != 'rr14-disposable-synthetic-v1' or not isinstance(document['principals'], dict):
            return {}
        for grant in document['principals'].values():
            required = {'username', 'cases', 'plans'}
            if not isinstance(grant, dict) or not required <= set(grant) <= required | {'family_versions', 'hypotheses'}:
                return {}
            if not isinstance(grant['username'], str):
                return {}
            for identities in (grant.get(field, []) for field in ('cases', 'plans', 'family_versions', 'hypotheses')):
                if not isinstance(identities, list) or not all(isinstance(item, str) and item for item in identities):
                    return {}
        return document['principals']
    except (OSError, ValueError, RecursionError):
        return {}


def _unique_keys(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('Duplicate grant keys')
    return result


def scope_response(get_response):
    """Use one snapshot per response, never cache protected HTTP responses."""
    def middleware(request):
        token = _snapshot.set(_load())
        try:
            response = get_response(request)
            leading_path, api_root, relative = request.path_info.partition('/api/v1/')
            if not leading_path and api_root and relative.partition('/')[0] in _PRIVATE_JSON_RESOURCES:
                response['Cache-Control'] = 'private, no-store'
            elif 'no-store' not in response.get('Cache-Control', ''):
                add_never_cache_headers(response)
            return response
        finally:
            _snapshot.reset(token)

    def hold_unverified_browser_writes(request, view, args, kwargs):
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.resolver_match.url_name in _HELD_BROWSER_WRITES:
            return HttpResponseNotAllowed(['GET', 'HEAD', 'OPTIONS'])

    middleware.process_view = hold_unverified_browser_writes
    return middleware


def authoring_scope(actor, *, required):
    """Use the HTTP scope snapshot; offline fixture seeding keeps its internal receipt."""
    return ReadScope(actor) if required or _snapshot.get() is not None else None


class ReadScope:
    def __init__(self, actor):
        document = _snapshot.get()
        if document is None:
            document = _load()
        grant = document.get(str(actor.pk), {}) if has_rms_read_access(actor) else {}
        self.available = bool(grant) and grant['username'] == actor.get_username()
        self.case_ids = grant['cases'] if self.available else ()
        self.plan_ids = grant['plans'] if self.available else ()
        self.family_version_ids = grant.get('family_versions', ()) if self.available else ()
        self.hypothesis_ids = grant.get('hypotheses', ()) if self.available else ()

    def cases(self):
        return InvestigationVersion.objects.filter(
            record__public_id__in=self.case_ids, record__synthetic=True,
            classification='synthetic', authority_reference=AUTHORITY_REFERENCE,
        )

    def _case_edges(self, kind):
        return ResearchAssociation.objects.filter(
            kind=kind, classification='synthetic', authority_reference=AUTHORITY_REFERENCE,
            investigation_version__in=self.cases(),
        )

    def hypotheses(self):
        authored = IdempotencyRecord.objects.filter(request_path='/api/v1/hypotheses',
            response_identity=Concat(Value('scoped:'), OuterRef('record__public_id')), key__startswith='HN:')
        return HypothesisVersion.objects.filter(
            Exists(self._case_edges('HypothesisInvestigation').filter(hypothesis_version=OuterRef('pk'))),
            record__synthetic=True, classification='synthetic', authority_reference=AUTHORITY_REFERENCE,
        ).filter(~Exists(authored) | Q(record__public_id__in=self.hypothesis_ids))

    def plans(self):
        parent = TestPlanAssociation.objects.filter(
            plan_version=OuterRef('pk'), kind='HypothesisPlan', hypothesis_version__in=self.hypotheses(),
        )
        return TestPlanVersion.objects.filter(
            Exists(parent), record__public_id__in=self.plan_ids, record__synthetic=True,
            classification='synthetic', authority_reference=PLAN_AUTHORITY,
        )

    def families(self):
        return self._family_versions().filter(
            Q(public_id__in=self.family_version_ids) | self._case_family_predicate(),
        )

    def _case_family_predicate(self):
        return Exists(self._case_edges('InvestigationFamily').filter(family_version=OuterRef('pk')))

    def _family_versions(self):
        return ResearchFamilyVersion.objects.filter(
            record__synthetic=True, classification='synthetic', authority_reference=AUTHORITY_REFERENCE,
        )

    def case_families(self):
        return self._family_versions().filter(self._case_family_predicate())

    def assessments(self):
        restricted_links = ResearchAssociation.objects.filter(kind='AssessmentRecord', assessment_version=OuterRef('pk')).filter(
            Q(investigation_version__isnull=False) & ~Q(investigation_version__in=self.cases()) |
            Q(family_version__isnull=False) & ~Q(family_version__in=self.case_families()),
        )
        return PriorResearchAssessmentVersion.objects.filter(
            Exists(self._case_edges('PriorResearchInvestigation').filter(assessment_version=OuterRef('pk'))),
            ~Exists(restricted_links),
            record__synthetic=True, classification='synthetic', authority_reference=AUTHORITY_REFERENCE,
        )

    def classifications(self):
        return ResearchAssociation.objects.filter(
            kind='IdeaFamily', classification='synthetic', authority_reference=AUTHORITY_REFERENCE,
            family_version__in=self.case_families(),
        )

    def versions(self, queryset):
        policy = {
            InvestigationVersion: self.cases, HypothesisVersion: self.hypotheses,
            TestPlanVersion: self.plans, ResearchFamilyVersion: self.families,
            PriorResearchAssessmentVersion: self.assessments, ResearchAssociation: self.classifications,
        }.get(queryset.model)
        return queryset.filter(pk__in=policy().values('pk')) if policy is not None else queryset

    def heads(self, records):
        versions = self.versions(records.model._meta.get_field('versions').related_model.objects.all())
        visible_head = versions.filter(record_id=OuterRef('pk'), version=OuterRef('latest_version'))
        return records.filter(Exists(visible_head))

    def exact(self, record_model, identity, version=None):
        versions = self.versions(record_model._meta.get_field('versions').related_model.objects.all())
        return read_one(versions, record__public_id=identity,
                        version=F('record__latest_version') if version is None else version)

    def allows(self, version):
        return self.versions(type(version).objects.filter(pk=version.pk)).exists()


def read_one(queryset, **identity):
    try:
        return queryset.get(**identity)
    except queryset.model.DoesNotExist as error:
        raise ResourceNotFound from error
