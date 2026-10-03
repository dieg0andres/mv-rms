"""Bounded ordinary DML probes through actual deployed app binding; ALWAYS rollback.
Does not prove least privilege or resistance to an administrator disabling guards.
No role/grant/DDL/TRUNCATE/auth changes, no fixture creation, no committed writes.
"""
import hashlib,json,sys,uuid
from pathlib import Path
CANDIDATE='aead8ff52128859fbae8b0f3d8ed2de67aff5131'
TREE='5880845c045af75e19c686cb5840b736a414abfa'
if sys.argv[1:] != ['--run']:
 print(json.dumps({'mode':'PLAN_ONLY','committed_writes':0,'action':'UPDATE primary key and DELETE one existing synthetic row per new guarded table, savepoint rollback and outer rollback','role':'actual deployed rms_staging app binding, privileged; not an ordinary-role proof'}));sys.exit(0)
metadata=Path('/srv/metadata.json').read_text();assert CANDIDATE in metadata and TREE in metadata
sys.path.insert(0,'/srv/adapter');import runtime
from django.db import connection,transaction,DatabaseError
identities=['rms_researchfamily','rms_investigation','rms_priorresearchassessment','rms_hypothesis','rms_researchassociationidentity']
versions=['rms_researchfamilyversion','rms_investigationversion','rms_priorresearchassessmentversion','rms_hypothesisversion','rms_researchassociation','rms_assessmentexternalreference','rms_hypothesiscorrectionimpact']
results=[];samples=[]
def fingerprint(table,row_id):
 q=connection.ops.quote_name(table)
 expression="to_jsonb(t) - 'latest_version'" if table in identities else 'to_jsonb(t)'
 with connection.cursor() as c:
  c.execute('SELECT ('+expression+')::text FROM '+q+' t WHERE id=%s',[row_id]);r=c.fetchone()
 return None if r is None else hashlib.sha256(r[0].encode()).hexdigest()
with transaction.atomic():
 with connection.cursor() as c:
  c.execute("SET LOCAL lock_timeout='500ms'");c.execute("SET LOCAL statement_timeout='2000ms'");c.execute("SET LOCAL idle_in_transaction_session_timeout='10000ms'")
  c.execute('SELECT current_database(),current_user,session_user');binding=c.fetchone();assert binding==('rms_staging','rms_staging','rms_staging')
  c.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=current_user');privileges=c.fetchone()
  c.execute("SELECT name FROM django_migrations WHERE app='rms' ORDER BY name");assert [r[0] for r in c.fetchall()]==['0001_initial','0002_source_invariants','0003_source_idea_contract','0004_hypothesis_records','0005_hypothesis_history_guards']
 for table in identities+versions:
  q=connection.ops.quote_name(table)
  with connection.cursor() as c:
   predicate='synthetic IS TRUE' if table in identities else "classification='synthetic'"
   c.execute('SELECT id FROM '+q+' WHERE '+predicate+' ORDER BY id LIMIT 1 FOR SHARE');sample=c.fetchone()
  if sample is None:
   results.append({'table':table,'result':'NOT EXECUTED','reason':'no existing synthetic row; no fixture added'});continue
  row_id=sample[0];before=fingerprint(table,row_id);samples.append((table,row_id,before))
  for operation in ['UPDATE','DELETE']:
   error_code=None;message=None;changed_rows=None
   try:
    with transaction.atomic():
     with connection.cursor() as c:
      if operation=='UPDATE': c.execute('UPDATE '+q+' SET id=%s WHERE id=%s',[uuid.uuid4(),row_id])
      else: c.execute('DELETE FROM '+q+' WHERE id=%s',[row_id])
      changed_rows=c.rowcount
     transaction.set_rollback(True)
   except DatabaseError as error:
    cause=error.__cause__;error_code=getattr(cause,'sqlstate',None)
    message=str(error).splitlines()[0]
   expected='Research identities are retained' if table in identities and operation=='DELETE' else ('Only append triggers may advance research watermarks' if table in identities else table+' rows are append-only')
   expected_code='P0001' if table in identities else '23000'
   passed=error_code==expected_code and message==expected and fingerprint(table,row_id)==before
   results.append({'table':table,'row_id':str(row_id),'operation':operation,'result':'PASS' if passed else 'FAIL','sqlstate':error_code,'expected_sqlstate':expected_code,'guard_message_matches':message==expected,'unexpected_affected_rows':changed_rows})
 transaction.set_rollback(True)
unchanged=all(fingerprint(t,r)==h for t,r,h in samples)
report={'candidate':CANDIDATE,'tree':TREE,'target':binding,'privilege_flags':dict(zip(['superuser','createdb','createrole','bypassrls'],privileges)),'scope':'ordinary UPDATE/DELETE trigger enforcement using actual deployed privileged application role; NOT least-privilege or privileged-administrator-proof','results':results,'checked_rows_unchanged':unchanged,'committed_writes':0,'outer_transaction_rolled_back':True,'result':'PASS' if unchanged and all(r['result']!='FAIL' for r in results) else 'FAIL'}
print(json.dumps(report,sort_keys=True))
sys.exit(0 if report['result']=='PASS' else 1)
