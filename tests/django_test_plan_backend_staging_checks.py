"""Explicit builder checks on existing rms_staging. Never creates/reset a DB.

Invoke only in a Director-coordinated staging mutation slot after applying 0006/7.
Adds at most three invented plans with retained history and reports. No cleanup.
Source-only unittest checks do not invoke this module's main().
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from threading import Barrier
import uuid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hypothesis-version-id',required=True)
    parser.add_argument('--editor-username',required=True)
    parser.add_argument('--run-label',required=True)
    parser.add_argument('--expected-sql-role',required=True)
    args=parser.parse_args()
    # No synthetic/default DB fallback; settings and credentials remain injected.
    if os.environ.get('RMS_DB_NAME')!='rms_staging': parser.error('An explicit existing rms_staging binding is required.')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','rms_project.settings')
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connection,transaction,DatabaseError,connections
    from rms import test_plan_services as s
    from rms import test_plan_models as m
    from rms.permissions import has_rms_write_access
    from rms.services import IdempotencyConflict
    from rms.research_context_common import StaleVersion
    from tests.test_test_plan_backend_validation import minimal,complete_fixture

    if connection.settings_dict['NAME']!='rms_staging': raise RuntimeError('Unexpected database target.')
    with connection.cursor() as cur:
        cur.execute('SELECT current_database(),current_user,r.rolsuper,r.rolbypassrls FROM pg_roles r WHERE r.rolname=current_user')
        database,role,superuser,bypassrls=cur.fetchone()
        cur.execute("SELECT app,name FROM django_migrations WHERE app='rms' ORDER BY name")
        migrations=[row[1] for row in cur.fetchall()]
    if role!=args.expected_sql_role: raise RuntimeError('SQL role does not match coordinated slot.')
    if '0007_test_plan_history_guards' not in migrations: raise RuntimeError('Required additive migrations are not installed.')
    actor=get_user_model().objects.get(username=args.editor_username)
    if not has_rms_write_access(actor): raise RuntimeError('An existing active RMS editor is required.')
    s.read_hypothesis_version(actor=actor,version_id=args.hypothesis_version_id)

    def auth_fingerprint():
        tables=['auth_user','auth_group','auth_permission','auth_user_groups','auth_user_user_permissions','auth_group_permissions']
        contents={}
        with connection.cursor() as cur:
            for table in tables:
                cur.execute('SELECT to_jsonb(t) FROM '+table+' t ORDER BY t.id')
                contents[table]=[row[0] for row in cur.fetchall()]
        return s.digest(contents)

    auth_before=auth_fingerprint()
    results=[]; namespace='tp-builder-'+args.run_label+'-'+uuid.uuid4().hex
    def key(label): return namespace+':'+label
    def body(stored): return json.loads(stored.body)
    def success(name,**evidence): results.append({'check':name,'result':'PASS',**evidence})
    def correction(read,reason):
        return {k:deepcopy(read[k]) for k in ['hypothesis_version_id','fields','criteria','data_requirements']}|{'expected_latest_version':read['version'],'correction_reason':reason}
    def no_partial_counts():
        return tuple(model.objects.count() for model in [m.TestPlan,m.TestPlanVersion,m.CriterionProfile,m.CriterionProfileVersion,m.DataRequirement,m.DataRequirementVersion,m.TestPlanAssociation,m.DataAccessCheck])

    # First persistent title-only slice, replay, revision and unchanged exact v1.
    payload=minimal();payload['hypothesis_version_id']=args.hypothesis_version_id;payload['fields']['title']='Invented '+namespace
    first=s.create_test_plan(actor=actor,idempotency_key=key('create'),payload=payload)
    v1=body(first); assert first.status==201 and v1['draft_completeness']=='incomplete'
    frozen={k:deepcopy(v1[k]) for k in ['fields','criteria','data_requirements','config_digest','associations']}
    replay=s.create_test_plan(actor=actor,idempotency_key=key('create'),payload=payload)
    assert replay==first
    try:s.create_test_plan(actor=actor,idempotency_key=key('create'),payload={**payload,'fields':{'title':'Invented conflicting payload'}})
    except IdempotencyConflict:pass
    else:raise AssertionError('Payload reuse did not conflict')
    proposal=correction(v1,'Invented title-only revision');proposal['fields']['title']+=' revised'
    v2=body(s.correct_test_plan(actor=actor,plan_id=v1['plan_id'],idempotency_key=key('revise'),payload=proposal))
    old=s.read_test_plan_version(actor=actor,plan_id=v1['plan_id'],version_id=v1['plan_version_id'])
    assert v2['version']==2 and {k:old[k] for k in frozen}==frozen
    same=correction(v2,'Invented no-change submission')
    unchanged=s.correct_test_plan(actor=actor,plan_id=v1['plan_id'],idempotency_key=key('nochange'),payload=same)
    assert unchanged.status==200 and body(unchanged)['no_change'] is True
    success('title_only_create_read_revise_replay_nochange',plan_id=v1['plan_id'],v1=v1['plan_version_id'],v2=v2['plan_version_id'])

    # Full invented definition, child reuse/change/removal, finite configurations.
    payload=complete_fixture();payload['hypothesis_version_id']=args.hypothesis_version_id;payload['fields']['title']='Invented complete '+namespace
    full=body(s.create_test_plan(actor=actor,idempotency_key=key('full'),payload=payload))
    assert full['draft_completeness']=='complete' and full['configuration_count']==2
    changed=correction(full,'Invented criterion refinement');changed['criteria'][0]['fields']['threshold']='0.01'
    full2=body(s.correct_test_plan(actor=actor,plan_id=full['plan_id'],idempotency_key=key('criterion'),payload=changed))
    assert full2['criteria'][0]['criterion_id']==full['criteria'][0]['criterion_id']
    assert full2['criteria'][0]['criterion_version_id']!=full['criteria'][0]['criterion_version_id']
    assert full2['data_requirements']==full['data_requirements']
    success('complete_definition_child_versioning',plan_id=full['plan_id'],config_digest=full['config_digest'])

    counts=no_partial_counts()
    bad=correction(v2,'Invented cross-plan child probe');bad['criteria']=deepcopy(full2['criteria'])
    from rms.test_plan_validation import TestPlanValidationError
    try:s.correct_test_plan(actor=actor,plan_id=v2['plan_id'],idempotency_key=key('crossplan'),payload=bad)
    except TestPlanValidationError:pass
    else:raise AssertionError('Cross-plan adoption succeeded')
    try:s.correct_test_plan(actor=actor,plan_id=v2['plan_id'],idempotency_key=key('stale'),payload=proposal)
    except StaleVersion:pass
    else:raise AssertionError('Stale proposal succeeded')
    assert counts==no_partial_counts()
    success('denied_cross_plan_and_stale_no_partial_writes')

    def report(read,config='baseline',current=None):
        return {'plan_version_id':read['plan_version_id'],'data_requirement_version_id':read['data_requirements'][0]['data_requirement_version_id'],'configuration_key':config,'performed_at':'2026-10-03T12:00:00Z','performed_by':'Invented fixture author','tool':'Invented builder fixture tool','outcome':'passed','check_scope':'Three invented schema rows only','observations':'Invented fixture schema matched; no provider accessed','evidence_references':[{'label':'Invented fixture source','uri':'urn:mv-rms:invented-tp-builder:'+namespace,'revision':None,'sha256':None}],'limitations':'Invented evidence only; no account entitlement, provider access or historical coverage established','sanitized_evidence_confirmed':True,'expected_current_check_id':current,'supersedes_check_id':current,'correction_reason':'Invented report correction' if current else None}
    check1=body(s.record_data_access_check(actor=actor,plan_id=full['plan_id'],idempotency_key=key('check1'),payload=report(full)))
    check2payload=report(full,current=check1['check_id']);check2payload['outcome']='failed'
    check2=body(s.record_data_access_check(actor=actor,plan_id=full['plan_id'],idempotency_key=key('check2'),payload=check2payload))
    assert check2['supersedes_check_id']==check1['check_id']
    original=s.read_data_access_check(actor=actor,plan_id=full['plan_id'],check_id=check1['check_id'])
    assert original['outcome']=='passed' and original['superseded_by_check_id']==check2['check_id']
    current=s.read_test_plan(actor=actor,plan_id=full['plan_id'])
    assert current['current_indicators']['check_summary']['status']=='not_checked'
    assert current['current_indicators']['check_summary']['historical_report_count']==2
    success('report_history_and_no_current_version_credit',first_check=check1['check_id'],successor_check=check2['check_id'])

    # Distinct sessions; barrier is after each thread loads its actor and before
    # independent calls enter the shared lineage lock. Commits are retained.
    barrier=Barrier(2)
    proposals=[]
    for suffix in ['a','b']:
        p=correction(full2,'Invented overlapping revision '+suffix);p['fields']['objective']+=' '+suffix;proposals.append(p)
    def concurrent_revision(index):
        connections.close_all()
        try:
            local_actor=get_user_model().objects.get(pk=actor.pk);barrier.wait(timeout=20)
            try:return {'result':'created','body':body(s.correct_test_plan(actor=local_actor,plan_id=full['plan_id'],idempotency_key=key('overlap'+str(index)),payload=proposals[index]))}
            except StaleVersion:return {'result':'conflict'}
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool: overlap=list(pool.map(concurrent_revision,[0,1]))
    assert sorted(x['result'] for x in overlap)==['conflict','created']
    head=s.read_test_plan(actor=actor,plan_id=full['plan_id']);assert head['version']==3
    success('committed_distinct_session_revision_conflict',head=head['plan_version_id'])

    # Two report corrections against the same observed current report/binding.
    seed_check=body(s.record_data_access_check(actor=actor,plan_id=full['plan_id'],idempotency_key=key('checkseed'),payload=report(head)))
    barrier=Barrier(2)
    def concurrent_check(index):
        connections.close_all()
        try:
            local_actor=get_user_model().objects.get(pk=actor.pk);barrier.wait(timeout=20)
            try:return {'result':'created','body':body(s.record_data_access_check(actor=local_actor,plan_id=full['plan_id'],idempotency_key=key('checkoverlap'+str(index)),payload=report(head,current=seed_check['check_id'])))}
            except StaleVersion:return {'result':'conflict'}
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool: overlap_checks=list(pool.map(concurrent_check,[0,1]))
    assert sorted(x['result'] for x in overlap_checks)==['conflict','created']
    success('committed_distinct_session_report_conflict')

    # These negative DML probes rollback independently, even on unexpected success.
    def denied_dml(name,operation):
        denied=False
        try:
            with transaction.atomic():
                operation()
                with connection.cursor() as cur:cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
                transaction.set_rollback(True)
        except DatabaseError:denied=True
        if not denied:raise AssertionError(name+' unexpectedly succeeded')
        success(name,sql_role=role)
    historical=m.TestPlanVersion.objects.get(public_id=full['plan_version_id'])
    denied_dml('postgres_version_update_denied',lambda:m.TestPlanVersion.objects.filter(pk=historical.pk).update(fields={'title':'Invented tamper'}))
    denied_dml('postgres_version_delete_denied',lambda:m.TestPlanVersion.objects.filter(pk=historical.pk)._raw_delete('default'))
    edge=m.TestPlanAssociation.objects.filter(plan_version=historical,kind='PlanCriterion').get()
    denied_dml('postgres_edge_delete_denied',lambda:m.TestPlanAssociation.objects.filter(pk=edge.pk)._raw_delete('default'))
    def late_insert():
        # Valid owned child, new identity, append sequence and FK shape. Only the
        # historical association commitment should reject this late attachment.
        identity=m.CriterionProfile.objects.create(plan=historical.record)
        criterion=s._append(m.CriterionProfileVersion,identity,actor,deepcopy(edge.criterion_version.fields))
        extra=m.TestPlanAssociation(plan_version=historical,kind='PlanCriterion',position=2,required=True,criterion_version=criterion,created_by=actor.get_username())
        s._row_seal(extra).save(force_insert=True)
    counts=no_partial_counts();denied_dml('postgres_late_association_insert_denied',late_insert);assert counts==no_partial_counts()
    auth_after=auth_fingerprint();assert auth_after==auth_before
    success('auth_records_unchanged',before=auth_before,after=auth_after)
    print(json.dumps({'kind':'builder_existing_staging_checks','database':database,'sql_role':role,'superuser':superuser,'bypassrls':bypassrls,'candidate_schema_sha256':__import__('rms.test_plan_validation',fromlist=['SCHEMA_SHA256']).SCHEMA_SHA256,'run_label':args.run_label,'migrations':migrations,'retained_plan_ids':[v1['plan_id'],full['plan_id']],'checks':results,'limitations':['Builder evidence only; independent TP01–TP24 and browser checks remain separate.','Actual SQL role is recorded; owner/superuser results do not prove administrator-resistant immutability.','No reset, auth mutation, provider access, strategy execution or database creation.']},indent=2))


if __name__=='__main__':main()
