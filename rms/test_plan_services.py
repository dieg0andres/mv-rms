"""Authorized transactional API-1 services, shared by pages and API adapters."""
import hashlib
import json
import re
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from . import test_plan_models as m
from .test_plan_validation import validate_json_size, validate_request, draft_completeness, resolved_configurations, issue, TestPlanValidationError
from .hypothesis_models import HypothesisVersion, Hypothesis, Investigation
from .research_context_services import edge
from .hypothesis_services import hypothesis_read
from .research_context_common import require_actor, resolve as resolve_hn, wire, lock_lineage, StaleVersion
from .rr14_scope import ReadScope, authoring_scope, read_one
from .models import IdempotencyRecord
from .services import canonical_json_bytes, _lock_idempotency_key, _replay_or_conflict, IdempotencyConflict, ResourceNotFound, StoredResponse


def digest(content):
    return hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def _visible(model):
    if model in (m.TestPlan,m.CriterionProfile,m.DataRequirement): return model.objects.filter(synthetic=True)
    if model is m.TestPlanAssociation: return model.objects.filter(plan_version__classification='synthetic',plan_version__authority_reference=m.AUTHORITY_REFERENCE)
    return model.objects.filter(classification='synthetic',authority_reference=m.AUTHORITY_REFERENCE)


def _get(model,public_id,**filters):
    try: return _visible(model).get(public_id=public_id,**filters)
    except model.DoesNotExist as exc: raise ResourceNotFound from exc


def _error(path,code='inconsistent_context'):
    raise TestPlanValidationError([issue(path,code)])


def _head(plan_id,lock=False):
    qs=_visible(m.TestPlan)
    if lock: qs=qs.select_for_update()
    try:
        plan=qs.get(public_id=plan_id)
        return plan,_visible(m.TestPlanVersion).get(record=plan,version=plan.latest_version)
    except (m.TestPlan.DoesNotExist,m.TestPlanVersion.DoesNotExist) as exc: raise ResourceNotFound from exc


def _row_seal(item):
    item.row_digest=digest({f.attname:wire(getattr(item,f.attname)) for f in item._meta.concrete_fields if f.name!='row_digest'})
    return item


def _append(model,record,actor,fields,old=None,reason=None,changed=(),**extra):
    now=timezone.now()
    item=model(record=record,version=old.version+1 if old else 1,fields=fields,
               corrects_version=old.version if old else None,correction_reason=reason,
               created_at=now,recorded_at=now,created_by=actor.get_username(),changed_fields=list(changed),
               content_digest=digest({'schema_version':'1.0','fields':fields}),**extra)
    _row_seal(item).save(force_insert=True)
    record.refresh_from_db(fields=['latest_version'])
    return item


def _scoped_replay(key,request_digest,path,scope,acknowledge):
    record=IdempotencyRecord.objects.filter(key=key).first()
    if record is None: return None
    if record.request_path!=path: raise IdempotencyConflict
    try:
        binding=json.loads(bytes(record.response_bytes))
    except (ValueError,TypeError) as error:
        raise ResourceNotFound from error
    if not isinstance(binding,dict): raise ResourceNotFound
    response=acknowledge(scope,record.response_status,binding)
    if record.request_sha256!=request_digest: raise IdempotencyConflict
    return StoredResponse(record.response_status,canonical_json_bytes(response))


def _execute(actor,key,payload,name,path,operation, *, scoped, authorize, acknowledge, binding_fields):
    require_actor(actor,write=True)
    scope=authoring_scope(actor,required=scoped)
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}',key): _error('/Idempotency-Key','invalid_format')
    validate_json_size(payload)
    storage_key='TP:'+digest([str(actor.pk),key])
    request_digest=digest({'actor':str(actor.pk),'method':'POST','path':path,'payload':payload})
    with transaction.atomic():
        lock_lineage()  # Same lock as Hypothesis and upstream writes.
        if scope is not None:
            normalized=validate_request(name,payload)
            authorize(scope,normalized)
        _lock_idempotency_key(storage_key)
        replay=(_replay_or_conflict(storage_key,request_digest) if scope is None else
                _scoped_replay(storage_key,request_digest,path,scope,acknowledge))
        if replay is not None: return replay
        if scope is None: normalized=validate_request(name,payload)
        status,body=operation(normalized,scope is not None)
        binding=body if scope is None else {field: body[field] for field in binding_fields}
        response=body if scope is None else acknowledge(scope,status,binding)
        IdempotencyRecord.objects.create(key=storage_key,request_method='POST',request_path=path,request_sha256=request_digest,response_status=status,response_identity=body.get('plan_id',body.get('check_id')),response_bytes=canonical_json_bytes(binding))
        return StoredResponse(status,canonical_json_bytes(response))


def _edges(item,kind):
    return item.associations.filter(kind=kind).order_by('position')


def _hypothesis(item):
    return item.associations.get(kind='HypothesisPlan').hypothesis_version


def _children(item,kind):
    if kind=='criteria':
        return [{'criterion_id':a.criterion_version.record.public_id,'criterion_version_id':a.criterion_version.public_id,'fields':a.criterion_version.fields} for a in _edges(item,'PlanCriterion').select_related('criterion_version__record')]
    return [{'data_requirement_id':a.data_requirement_version.record.public_id,'data_requirement_version_id':a.data_requirement_version.public_id,'fields':a.data_requirement_version.fields} for a in _edges(item,'PlanDataRequirement').select_related('data_requirement_version__record')]


def _snapshot(item):
    return {'hypothesis_version_id':_hypothesis(item).public_id,'fields':item.fields,'criteria':_children(item,'criteria'),'data_requirements':_children(item,'data_requirements')}


def _child_inputs(p,old):
    """Resolve every supplied child before any write; exact preceding membership."""
    result={}
    for coll,id_key,v_key,model in [('criteria','criterion_id','criterion_version_id',m.CriterionProfileVersion),('data_requirements','data_requirement_id','data_requirement_version_id',m.DataRequirementVersion)]:
        previous={x[id_key]:x[v_key] for x in _children(old,coll)} if old else {}
        result[coll]=[]
        for i,x in enumerate(p[coll]):
            prior=None
            if x[id_key] is not None:
                prior=_get(model,x[v_key])
                if previous.get(x[id_key])!=x[v_key] or prior.record.public_id!=x[id_key] or prior.record.plan_id!=old.record_id: _error(f'/{coll}/{i}','child_not_in_predecessor')
            result[coll].append((x,prior))
    return result


def _persist_children(inputs,plan,actor,reason):
    result={}
    for coll,identity,model in [('criteria',m.CriterionProfile,m.CriterionProfileVersion),('data_requirements',m.DataRequirement,m.DataRequirementVersion)]:
        result[coll]=[]
        for x,old in inputs[coll]:
            if old and old.fields==x['fields']: item=old
            else:
                record=old.record if old else identity.objects.create(plan=plan)
                changed=['/fields/'+k for k,v in x['fields'].items() if not old or old.fields.get(k)!=v]
                item=_append(model,record,actor,x['fields'],old,reason if old else None,changed)
            result[coll].append(item)
    return result


def _link_token(a):
    target=a.hypothesis_version or a.criterion_version or a.data_requirement_version
    required='-' if a.required is None else '1' if a.required else '0'
    return f'{a.kind}:{a.position}:{target.public_id}:{required}:{a.public_id}\n'


def _save(p,actor,plan,hyp,inputs,old=None):
    children=_persist_children(inputs,plan,actor,p.get('correction_reason'))
    item=m.TestPlanVersion(record=plan)  # Generate UUIDs before sealing endpoint set.
    now=timezone.now(); edges=[m.TestPlanAssociation(plan_version=item,kind='HypothesisPlan',position=0,required=True,hypothesis_version=hyp,created_by=actor.get_username(),created_at=now)]
    for coll,kind,fk in [('criteria','PlanCriterion','criterion_version'),('data_requirements','PlanDataRequirement','data_requirement_version')]:
        for i,child in enumerate(children[coll],1):
            required=child.fields['mandatory'] if coll=='criteria' else bool(child.fields['used_by_configurations'])
            edges.append(m.TestPlanAssociation(plan_version=item,kind=kind,position=i,required=required,created_by=actor.get_username(),created_at=now,**{fk:child}))
    edges.sort(key=lambda a:(a.kind,a.position))
    link_digest=hashlib.sha256(''.join(_link_token(a) for a in edges).encode()).hexdigest()
    definition={'schema_version':'1.0','hypothesis_version_id':hyp.public_id,'fields':p['fields'],
                'criteria':[{'version_id':c.public_id,'content_digest':c.content_digest} for c in children['criteria']],
                'data_requirements':[{'version_id':c.public_id,'content_digest':c.content_digest} for c in children['data_requirements']],
                'link_digest':link_digest,'link_count':len(edges)}
    config_digest=digest(definition)
    configurations=[{**c,'digest':digest({'schema_version':'1.0','config_digest':config_digest,**c})} for c in resolved_configurations(p['fields'])]
    before=_snapshot(old) if old else None
    changed=[]
    if before:
        if before['hypothesis_version_id']!=p['hypothesis_version_id']: changed.append('/hypothesis_version_id')
        changed.extend('/fields/'+k for k,v in p['fields'].items() if before['fields'].get(k)!=v)
        for coll in ['criteria','data_requirements']:
            if before[coll]!=p[coll]: changed.append('/'+coll)
    saved=_append(m.TestPlanVersion,plan,actor,p['fields'],old,p.get('correction_reason'),changed,
                  id=item.id,public_id=item.public_id,link_count=len(edges),link_digest=link_digest,config_digest=config_digest,configurations=configurations)
    for a in edges:
        a.plan_version=saved; _row_seal(a).save(force_insert=True)
    return saved


def _receipt_identity(binding,field):
    identity=binding.get(field)
    if not isinstance(identity,str) or not identity: raise ResourceNotFound
    return identity


def _authorize_plan_hypothesis(scope,binding):
    read_one(scope.hypotheses(),public_id=_receipt_identity(binding,'hypothesis_version_id'))


def _acknowledge_plan_create(scope,status,binding):
    _authorize_plan_hypothesis(scope,binding)
    return {'saved': True}


def _acknowledge_plan_correction(scope,status,binding,plan_id):
    version=read_one(scope.plans(),record__public_id=plan_id,
                     public_id=_receipt_identity(binding,'plan_version_id'))
    receipt={'plan_id': plan_id,'plan_version_id': version.public_id,'version': version.version}
    if status==200: receipt['no_change']=True
    return receipt


def create_test_plan(*,actor,idempotency_key,payload,scoped=False):
    def operation(p,scoped):
        hyp=resolve_hn(HypothesisVersion,p['hypothesis_version_id'])
        inputs=_child_inputs(p,None)
        plan=m.TestPlan.objects.create()
        item=_save(p,actor,plan,hyp,inputs)
        if scoped:
            return 201,{'plan_id': plan.public_id,'hypothesis_version_id': hyp.public_id}
        return 201,_read(item)
    return _execute(actor,idempotency_key,payload,'PlanCreate','/api/v1/test-plans',operation,
                    scoped=scoped,authorize=_authorize_plan_hypothesis,acknowledge=_acknowledge_plan_create,
                    binding_fields=('hypothesis_version_id',))


def correct_test_plan(*,actor,plan_id,idempotency_key,payload,scoped=False):
    def authorize(scope,normalized):
        scope.exact(m.TestPlan,plan_id)
        _authorize_plan_hypothesis(scope,normalized)

    def operation(p,scoped):
        plan,old=_head(plan_id,True)
        if plan.latest_version!=p['expected_latest_version']: raise StaleVersion
        hyp=resolve_hn(HypothesisVersion,p['hypothesis_version_id'])
        if hyp.record_id!=_hypothesis(old).record_id: _error('/hypothesis_version_id','different_hypothesis')
        if hyp.version<_hypothesis(old).version: _error('/hypothesis_version_id','older_hypothesis')
        inputs=_child_inputs(p,old)
        proposed={k:p[k] for k in ['hypothesis_version_id','fields','criteria','data_requirements']}
        if proposed==_snapshot(old):
            if scoped: return 200,{'plan_id': plan.public_id,'plan_version_id': old.public_id}
            return 200,{**_read(old),'no_change':True}
        item=_save(p,actor,plan,hyp,inputs,old)
        if scoped: return 201,{'plan_id': plan.public_id,'plan_version_id': item.public_id}
        return 201,_read(item)
    return _execute(actor,idempotency_key,payload,'PlanCorrection',f'/api/v1/test-plans/{plan_id}/corrections',operation,
                    scoped=scoped,authorize=authorize,
                    acknowledge=lambda scope,status,binding: _acknowledge_plan_correction(scope,status,binding,plan_id),
                    binding_fields=('plan_version_id',))


def _current_checks(item):
    return _visible(m.DataAccessCheck).filter(plan_version=item,superseded_by__isnull=True)


def _check_summary(item, *, scope=None):
    expected={(x.data_requirement_version_id,k) for x in _edges(item,'PlanDataRequirement') for k in x.data_requirement_version.fields['used_by_configurations']}
    reports={(x.data_requirement_version_id,x.configuration_key):x.fields['outcome'] for x in _current_checks(item)}
    applicable=[reports[k] for k in expected if k in reports]
    label='not_checked'
    if any(x!='passed' for x in applicable): label='issues_reported'
    elif expected and len(applicable)==len(expected): label='checks_reported_passed'
    elif applicable: label='partially_checked'
    history=_visible(m.DataAccessCheck).filter(plan_version__record=item.record).exclude(plan_version=item)
    if scope is not None: history=history.filter(plan_version__in=scope.plans())
    return {'status':label,'required_pairs':len(expected),'reported_pairs':len(applicable),'historical_report_count':history.count()}


def _read(item, *, scope=None):
    snapshot=_snapshot(item); hyp=_hypothesis(item); inherited=hypothesis_read(hyp,scope=scope)
    notices=list(inherited['upstream_notices'])
    hyp.record.refresh_from_db(fields=['latest_version'])
    if hyp.version<hyp.record.latest_version:
        newer_versions = hyp.record.versions.filter(version=hyp.record.latest_version)
        if scope is not None: newer_versions=scope.versions(newer_versions)
        newer_id=newer_versions.values_list('public_id',flat=True).first()
        if newer_id: notices.append({'code':'review_needed','kind':'hypothesis','pinned_version_id':hyp.public_id,'newer_version_id':newer_id})
    previous_versions=item.record.versions.filter(version=item.corrects_version)
    if scope is not None: previous_versions=scope.versions(previous_versions)
    previous_id=previous_versions.values_list('public_id',flat=True).first() if item.corrects_version else None
    path=f'/api/v1/test-plans/{item.record.public_id}'
    return {**snapshot,'stable_id':item.record.public_id,'version_id':item.public_id,'plan_id':item.record.public_id,'plan_version_id':item.public_id,'version':item.version,'schema_version':item.schema_version,'status':'draft','classification':item.classification,'authority_reference':item.authority_reference,'implementation_target':'quantconnect_lean','created_at':wire(item.created_at),'recorded_at':wire(item.recorded_at),'created_by':item.created_by,'row_digest':item.row_digest,'config_digest':item.config_digest,'configurations':item.configurations,'configuration_count':len(item.configurations),'corrects_version':item.corrects_version if previous_id else None,'correction_reason':item.correction_reason if previous_id else None,'changed_fields':item.changed_fields if previous_id or not item.corrects_version else [],'supersedes_version_id':previous_id,
            'associations':[{'association_id':a.public_id,'kind':a.kind,'position':a.position,'required':a.required,'row_digest':a.row_digest,'hypothesis_version_id':a.hypothesis_version.public_id if a.hypothesis_version_id else None,'criterion_version_id':a.criterion_version.public_id if a.criterion_version_id else None,'data_requirement_version_id':a.data_requirement_version.public_id if a.data_requirement_version_id else None} for a in item.associations.order_by('kind','position')],
            'hypothesis':inherited,'research_context':inherited['research_context'],**draft_completeness(snapshot),
            'current_indicators':{'as_of':wire(timezone.now()),'upstream_notices':notices,'check_summary':_check_summary(item,scope=scope)},
            'links':{'self':path+'/versions/'+item.public_id,'latest':path,'history':path+'/versions','corrections':path+'/corrections','data_checks':path+'/data-checks','hypothesis':inherited['links']['self']}}


def read_test_plan(*,actor,plan_id):
    require_actor(actor); scope=ReadScope(actor)
    return _read(scope.exact(m.TestPlan,plan_id),scope=scope)


def read_test_plan_version(*,actor,plan_id,version_id):
    require_actor(actor); scope=ReadScope(actor)
    return _read(read_one(scope.plans(),public_id=version_id,record__public_id=plan_id),scope=scope)


def read_test_plan_history(*,actor,plan_id):
    require_actor(actor); scope=ReadScope(actor)
    versions=list(scope.plans().filter(record__public_id=plan_id).order_by('version'))
    if not versions: raise ResourceNotFound
    return {'results':[_read(x,scope=scope) for x in versions]}


def _paginate(qs,q,path,render):
    from urllib.parse import urlencode
    count=qs.count(); start=(q['page']-1)*q['page_size']
    link=lambda n:path+'?'+urlencode({**q,'page':n})
    return {'count':count,'page':q['page'],'page_size':q['page_size'],'next':link(q['page']+1) if start+q['page_size']<count else None,'previous':link(q['page']-1) if q['page']>1 else None,'results':[render(x) for x in qs[start:start+q['page_size']]]}


def list_test_plans(*,actor,query):
    require_actor(actor); q=validate_request('PlanListQuery',query)
    scope=ReadScope(actor)
    qs=scope.plans().filter(version=F('record__latest_version'))
    hyp=None
    if 'hypothesis_version_id' in q: hyp=read_one(scope.hypotheses(),public_id=q['hypothesis_version_id'])
    if hyp and 'hypothesis_id' in q and hyp.record.public_id!=q['hypothesis_id']: _error('/hypothesis_id','inconsistent_filter')
    if 'hypothesis_id' in q: scope.exact(Hypothesis,q['hypothesis_id'])
    if 'case_id' in q:
        case=scope.exact(Investigation,q['case_id'])
        if hyp and edge(hyp,'HypothesisInvestigation').investigation_version.record_id!=case.record_id: _error('/case_id','inconsistent_filter')
    if 'hypothesis_id' in q: qs=qs.filter(associations__kind='HypothesisPlan',associations__hypothesis_version__record__public_id=q['hypothesis_id'])
    if hyp: qs=qs.filter(associations__kind='HypothesisPlan',associations__hypothesis_version=hyp)
    if 'case_id' in q: qs=qs.filter(associations__kind='HypothesisPlan',associations__hypothesis_version__research_associations__kind='HypothesisInvestigation',associations__hypothesis_version__research_associations__investigation_version__record__public_id=q['case_id'])
    return _paginate(qs.order_by('-record__created_at','record__public_id'),q,'/api/v1/test-plans',lambda item: _read(item,scope=scope))


def _read_child(item,kind):
    plan=item.record.plan
    return {'stable_id':item.record.public_id,'version_id':item.public_id,'version':item.version,'schema_version':item.schema_version,'classification':item.classification,'plan_id':plan.public_id,'fields':item.fields,'row_digest':item.row_digest,'content_digest':item.content_digest,'created_at':wire(item.created_at),'created_by':item.created_by,'correction_reason':item.correction_reason,'corrects_version':item.corrects_version,'links':{'plan':f'/api/v1/test-plans/{plan.public_id}','self':f'/api/v1/{kind}/versions/{item.public_id}'}}


def read_criterion_version(*,actor,version_id):
    require_actor(actor)
    return _read_child(read_one(_readable_children(ReadScope(actor), m.CriterionProfileVersion),public_id=version_id),'criterion-profiles')


def read_data_requirement_version(*,actor,version_id):
    require_actor(actor)
    return _read_child(read_one(_readable_children(ReadScope(actor), m.DataRequirementVersion),public_id=version_id),'data-requirements')


def _readable_children(scope, model):
    field='criterion_version' if model is m.CriterionProfileVersion else 'data_requirement_version'
    links=m.TestPlanAssociation.objects.filter(plan_version__in=scope.plans(), **{field+'__isnull':False})
    return _visible(model).filter(pk__in=links.values(field))


def _check_read(item):
    newer=_visible(m.DataAccessCheck).filter(supersedes=item).first()
    return {**item.fields,'check_id':item.public_id,'plan_id':item.plan_version.record.public_id,'plan_version_id':item.plan_version.public_id,'data_requirement_version_id':item.data_requirement_version.public_id,'configuration_key':item.configuration_key,'configuration_digest':item.configuration_digest,'requirement_digest':item.requirement_digest,'supersedes_check_id':item.supersedes.public_id if item.supersedes_id else None,'superseded_by_check_id':newer.public_id if newer else None,'entered_by':item.created_by,'recorded_at':wire(item.created_at),'classification':item.classification,'authority_reference':item.authority_reference,'row_digest':item.row_digest,'historical':item.plan_version.version!=item.plan_version.record.latest_version}


def record_data_access_check(*,actor,plan_id,idempotency_key,payload,scoped=False):
    def authorize(scope,binding):
        scope.exact(m.TestPlan,plan_id)
        version=read_one(scope.plans(),record__public_id=plan_id,
                         public_id=_receipt_identity(binding,'plan_version_id'))
        requirement_id=_receipt_identity(binding,'data_requirement_version_id')
        if not _edges(version,'PlanDataRequirement').filter(
            data_requirement_version__public_id=requirement_id,
            data_requirement_version__in=_readable_children(scope,m.DataRequirementVersion),
        ).exists(): raise ResourceNotFound

    def acknowledge(scope,status,binding):
        authorize(scope,binding)
        return {'saved': True}

    def operation(p,scoped):
        plan,_=_head(plan_id,True)
        version=_get(m.TestPlanVersion,p['plan_version_id'],record=plan)
        requirement=_get(m.DataRequirementVersion,p['data_requirement_version_id'])
        if not _edges(version,'PlanDataRequirement').filter(data_requirement_version=requirement).exists(): _error('/data_requirement_version_id','not_associated')
        config=next((x for x in version.configurations if x['key']==p['configuration_key']),None)
        if config is None or p['configuration_key'] not in requirement.fields['used_by_configurations']: _error('/configuration_key','not_applicable')
        current=_current_checks(version).filter(data_requirement_version=requirement,configuration_key=p['configuration_key']).first()
        if (current.public_id if current else None)!=p['expected_current_check_id']: raise StaleVersion
        report={k:v for k,v in p.items() if k not in ('plan_version_id','data_requirement_version_id','configuration_key','expected_current_check_id','supersedes_check_id')}
        item=m.DataAccessCheck(plan_version=version,data_requirement_version=requirement,configuration_key=p['configuration_key'],configuration_digest=config['digest'],requirement_digest=requirement.content_digest,fields=report,supersedes=current,created_by=actor.get_username())
        _row_seal(item).save(force_insert=True)
        if scoped:
            return 201,{'check_id': item.public_id,'plan_version_id': version.public_id,
                        'data_requirement_version_id': requirement.public_id}
        return 201,_check_read(item)
    return _execute(actor,idempotency_key,payload,'CheckCreate',f'/api/v1/test-plans/{plan_id}/data-checks',operation,
                    scoped=scoped,authorize=authorize,acknowledge=acknowledge,
                    binding_fields=('plan_version_id','data_requirement_version_id'))


def list_data_access_checks(*,actor,plan_id,query):
    require_actor(actor); q=validate_request('CheckListQuery',query); scope=ReadScope(actor)
    versions=scope.plans().filter(record__public_id=plan_id)
    if not versions.exists(): raise ResourceNotFound
    qs=_visible(m.DataAccessCheck).filter(plan_version__in=versions)
    version=read_one(versions,public_id=q['plan_version_id']) if 'plan_version_id' in q else None
    requirement=read_one(_readable_children(scope,m.DataRequirementVersion),public_id=q['data_requirement_version_id'],record__plan__public_id=plan_id) if 'data_requirement_version_id' in q else None
    if version: qs=qs.filter(plan_version=version)
    if requirement: qs=qs.filter(data_requirement_version=requirement)
    if version and requirement and not _edges(version,'PlanDataRequirement').filter(data_requirement_version=requirement).exists(): _error('/data_requirement_version_id','inconsistent_filter')
    if 'configuration_key' in q:
        if version and q['configuration_key'] not in {x['key'] for x in version.configurations}: _error('/configuration_key','inconsistent_filter')
        qs=qs.filter(configuration_key=q['configuration_key'])
    return _paginate(qs.order_by('created_at','public_id'),q,f'/api/v1/test-plans/{plan_id}/data-checks',_check_read)


def read_data_access_check(*,actor,plan_id,check_id):
    require_actor(actor)
    versions=ReadScope(actor).plans().filter(record__public_id=plan_id)
    return _check_read(read_one(_visible(m.DataAccessCheck),public_id=check_id,plan_version__in=versions))


def read_hypothesis_version(*,actor,version_id):
    """Authorized exact pin preview for plan creation; no new hypothesis content."""
    require_actor(actor)
    scope=ReadScope(actor)
    return hypothesis_read(read_one(scope.hypotheses(),public_id=version_id),scope=scope)
