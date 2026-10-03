"""Additive synthetic Test Plan records and exact, sealed relationship edges."""
from functools import partial
import uuid
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from .hypothesis_models import ResearchIdentity, identifier

AUTHORITY_REFERENCE='MAU-150:contract:dec62ed2-adab-4ab3-bbfd-8dffbcee897d'


class TestPlan(ResearchIdentity):
    public_id=models.CharField(max_length=42,unique=True,default=partial(identifier,'TPL'),editable=False)


class PlanOwnedIdentity(ResearchIdentity):
    plan=models.ForeignKey(TestPlan,on_delete=models.PROTECT)
    class Meta(ResearchIdentity.Meta):
        abstract=True


class CriterionProfile(PlanOwnedIdentity):
    public_id=models.CharField(max_length=42,unique=True,default=partial(identifier,'CRT'),editable=False)


class DataRequirement(PlanOwnedIdentity):
    public_id=models.CharField(max_length=42,unique=True,default=partial(identifier,'DREQ'),editable=False)


class PlanContentVersion(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    public_id=models.CharField(max_length=42,unique=True,editable=False)
    version=models.PositiveIntegerField()
    schema_version=models.CharField(max_length=8,default='1.0',editable=False)
    classification=models.CharField(max_length=16,default='synthetic',editable=False)
    authority_reference=models.CharField(max_length=128,default=AUTHORITY_REFERENCE,editable=False)
    state=models.CharField(max_length=16,default='draft',editable=False)
    created_at=models.DateTimeField(default=timezone.now,editable=False)
    recorded_at=models.DateTimeField(default=timezone.now,editable=False)
    created_by=models.CharField(max_length=150,editable=False)
    row_digest=models.CharField(max_length=64,editable=False)
    content_digest=models.CharField(max_length=64,editable=False)
    fields=models.JSONField(default=dict)
    corrects_version=models.PositiveIntegerField(null=True,editable=False)
    correction_reason=models.CharField(max_length=4000,null=True)
    changed_fields=models.JSONField(default=list,editable=False)
    class Meta:
        abstract=True
        ordering=['version']
        constraints=[
            models.UniqueConstraint(fields=['record','version'],name='%(class)s_sequence'),
            models.CheckConstraint(condition=Q(version__gt=0),name='%(class)s_positive'),
            models.CheckConstraint(condition=Q(classification='synthetic',schema_version='1.0',authority_reference=AUTHORITY_REFERENCE,state='draft'),name='%(class)s_scope'),
            models.CheckConstraint(condition=Q(version=1,corrects_version__isnull=True,correction_reason__isnull=True)|(Q(version__gt=1,corrects_version=F('version')-1,correction_reason__isnull=False)&~Q(correction_reason='')),name='%(class)s_predecessor'),
        ]


class TestPlanVersion(PlanContentVersion):
    public_id=models.CharField(max_length=42,unique=True,default=partial(identifier,'TPLV'),editable=False)
    record=models.ForeignKey(TestPlan,on_delete=models.PROTECT,related_name='versions')
    config_digest=models.CharField(max_length=64,editable=False)
    configurations=models.JSONField(default=list,editable=False)
    link_count=models.PositiveSmallIntegerField(editable=False)
    link_digest=models.CharField(max_length=64,editable=False)


class CriterionProfileVersion(PlanContentVersion):
    public_id=models.CharField(max_length=42,unique=True,default=partial(identifier,'CRTV'),editable=False)
    record=models.ForeignKey(CriterionProfile,on_delete=models.PROTECT,related_name='versions')


class DataRequirementVersion(PlanContentVersion):
    public_id=models.CharField(max_length=42,unique=True,default=partial(identifier,'DREQV'),editable=False)
    record=models.ForeignKey(DataRequirement,on_delete=models.PROTECT,related_name='versions')


class TestPlanAssociation(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    public_id=models.CharField(max_length=42,unique=True,default=partial(identifier,'TPAS'),editable=False)
    plan_version=models.ForeignKey(TestPlanVersion,on_delete=models.PROTECT,related_name='associations')
    kind=models.CharField(max_length=32)
    position=models.PositiveSmallIntegerField()
    required=models.BooleanField(null=True)
    hypothesis_version=models.ForeignKey('rms.HypothesisVersion',null=True,on_delete=models.PROTECT,related_name='test_plan_associations')
    criterion_version=models.ForeignKey(CriterionProfileVersion,null=True,on_delete=models.PROTECT,related_name='plan_associations')
    data_requirement_version=models.ForeignKey(DataRequirementVersion,null=True,on_delete=models.PROTECT,related_name='plan_associations')
    created_at=models.DateTimeField(default=timezone.now,editable=False)
    created_by=models.CharField(max_length=150,editable=False)
    row_digest=models.CharField(max_length=64,editable=False)
    class Meta:
        ordering=['kind','position']
        constraints=[
            models.UniqueConstraint(fields=['plan_version','kind','position'],name='tp_edge_position'),
            models.UniqueConstraint(fields=['plan_version','criterion_version'],name='tp_unique_criterion'),
            models.UniqueConstraint(fields=['plan_version','data_requirement_version'],name='tp_unique_data'),
            models.CheckConstraint(condition=Q(kind='HypothesisPlan',position=0,required=True,hypothesis_version__isnull=False,criterion_version__isnull=True,data_requirement_version__isnull=True)|Q(kind='PlanCriterion',position__gt=0,hypothesis_version__isnull=True,criterion_version__isnull=False,data_requirement_version__isnull=True)|Q(kind='PlanDataRequirement',position__gt=0,hypothesis_version__isnull=True,criterion_version__isnull=True,data_requirement_version__isnull=False),name='tp_edge_shape'),
        ]


class DataAccessCheck(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    public_id=models.CharField(max_length=42,unique=True,default=partial(identifier,'DCHK'),editable=False)
    plan_version=models.ForeignKey(TestPlanVersion,on_delete=models.PROTECT,related_name='data_checks')
    data_requirement_version=models.ForeignKey(DataRequirementVersion,on_delete=models.PROTECT,related_name='data_checks')
    configuration_key=models.CharField(max_length=64)
    configuration_digest=models.CharField(max_length=64,editable=False)
    requirement_digest=models.CharField(max_length=64,editable=False)
    fields=models.JSONField()
    supersedes=models.OneToOneField('self',null=True,on_delete=models.PROTECT,related_name='superseded_by')
    created_at=models.DateTimeField(default=timezone.now,editable=False)
    created_by=models.CharField(max_length=150,editable=False)
    classification=models.CharField(max_length=16,default='synthetic',editable=False)
    authority_reference=models.CharField(max_length=128,default=AUTHORITY_REFERENCE,editable=False)
    row_digest=models.CharField(max_length=64,editable=False)
    class Meta:
        constraints=[
            models.UniqueConstraint(fields=['plan_version','data_requirement_version','configuration_key'],condition=Q(supersedes__isnull=True),name='tp_check_one_root'),
            models.CheckConstraint(condition=Q(classification='synthetic',authority_reference=AUTHORITY_REFERENCE),name='tp_check_scope'),
            models.CheckConstraint(condition=Q(fields__outcome__in=['passed','failed','inconclusive'],fields__sanitized_evidence_confirmed=True),name='tp_check_report_shape'),
        ]
