"""Builder source checks. No DB, provider call or research result."""
from copy import deepcopy
from io import BytesIO
import json
import os
import unittest
from unittest.mock import patch
os.environ.setdefault('DJANGO_SETTINGS_MODULE','rms_project.settings')
import django
django.setup()
from rms.test_plan_validation import validate_request, draft_completeness, resolved_configurations, TestPlanValidationError, SCHEMA
from rms.test_plan_api import StrictJSONParser
from rms import test_plan_services as service
from rms.permissions import has_rms_read_access, has_rms_write_access
from rms.research_context_common import Forbidden, AuthenticationRequired

PIN='HYPV-00000000-0000-4000-8000-000000000001'


def minimal(): return {'hypothesis_version_id':PIN,'fields':{'title':'Invented first plan'},'criteria':[],'data_requirements':[]}


def complete_fixture():
    p=validate_request('PlanCreate',minimal()); f=p['fields']
    for name in SCHEMA['$defs']['PlanFields']['x-completeness-required']:
        rule=SCHEMA['$defs']['PlanFields']['properties'][name]
        if rule['type']==['string','null'] and 'enum' not in rule and 'format' not in rule: f[name]='Invented definition only.'
    f.update(title='Invented ALFA baseline',measurement_basis='gross_return',time_zone='America/New_York',evaluation_design='development_only',development_start='2016-01-01',development_end='2020-12-31',trial_budget=2,benchmark_alignment='same_as_hypothesis',benchmark_input_mode='defined_without_external_input',expected_outputs=['Invented signal table'],reviewer_roles=['Research reviewer'],parameters=[{'name':'lookback_sessions','type':'integer','baseline_value':20,'units':'sessions','meaning':'Completed sessions'}],variations=[{'key':'longer','name':'Longer lookback','rationale':'Invented bounded sensitivity','parameter_overrides':{'lookback_sessions':40}}])
    p['criteria']=[{'criterion_id':None,'criterion_version_id':None,'fields':{'name':'Invented mean return','metric':'Invented gross trade mean','units':'dimensionless','rule_type':'numeric','operator':'gt','threshold':'0','upper_threshold':None,'objective_rule':None,'sample_requirement':'Invented twenty trades; otherwise inconclusive','evaluator_role':'Invented researcher','mandatory':True,'applies_to':'all_configurations'}}]
    d={}
    for n,rule in SCHEMA['$defs']['DataFields']['properties'].items():
        d[n]=[] if rule['type']=='array' else None
    for n in SCHEMA['$defs']['DataFields']['x-completeness-required']:
        rule=SCHEMA['$defs']['DataFields']['properties'][n]
        if rule['type']==['string','null'] and 'enum' not in rule and 'format' not in rule: d[n]='Invented definition only.'
    d.update(key='daily_bars',name='Invented daily bars',used_by_configurations=['baseline','longer'],documentation_url='https://data.example.invalid/docs',documentation_checked_at='2026-10-03T12:00:00Z',access_method='rest_api',execution_location='other_existing_tool',execution_tool='Invented fixture tool',source_time_zone='America/New_York',coverage_start='2015-10-01',coverage_end='2020-12-31',credential_requirement='none',field_schema=[{'name':'close','data_type':'decimal string','units_meaning':'USD fixture','nullable':False,'use':'Invented signal'}],base_url='https://data.example.invalid',http_method='GET',endpoint_path='/v1/bars',request_parameters='instrument=ALFA; inclusive start,end; no auth',response_selector='items',pagination_rule='next_cursor until null',request_limits='Invented 500 rows per page',response_example='Invented shape: {close: "100.00"}')
    p['data_requirements']=[{'data_requirement_id':None,'data_requirement_version_id':None,'fields':d}]
    return validate_request('PlanCreate',p)


class Validation(unittest.TestCase):
    def invalid(self,p,path=None):
        with self.assertRaises(TestPlanValidationError) as ctx: validate_request('PlanCreate',p)
        if path is not None: self.assertIn(path,[i['path'] for i in ctx.exception.issues])

    def test_title_only_explicit_empty_no_defaults(self):
        p=validate_request('PlanCreate',minimal())
        self.assertIsNone(p['fields']['trial_budget']); self.assertEqual(p['fields']['parameters'],[])
        self.assertEqual(draft_completeness(p)['missing_fields'][0]['path'],'/fields/objective')
        self.assertEqual(resolved_configurations(p['fields']),[{'key':'baseline','parameters':{}}])

    def test_complete_definition_is_not_checks_or_approval(self):
        p=complete_fixture()
        self.assertEqual(draft_completeness(p)['draft_completeness'],'complete')
        self.assertEqual([x['key'] for x in resolved_configurations(p['fields'])],['baseline','longer'])

    def test_partial_repeatable_objects_fill_explicit_nulls(self):
        p=minimal();p['fields']['parameters']=[{'name':'lookback','type':'integer','baseline_value':20}]
        p['fields']['variations']=[{'key':'longer','parameter_overrides':{'lookback':40}}]
        p['data_requirements']=[{'data_requirement_id':None,'data_requirement_version_id':None,'fields':{'key':'bars','field_schema':[{'name':'close'}]}}]
        p=validate_request('PlanCreate',p)
        self.assertIsNone(p['fields']['parameters'][0]['units'])
        self.assertIsNone(p['fields']['variations'][0]['rationale'])
        self.assertIsNone(p['data_requirements'][0]['fields']['field_schema'][0]['nullable'])

    def test_no_cost_approval_or_client_metadata(self):
        for key in ['cost_model','status','classification','implementation_target']:
            with self.subTest(key=key):
                p=minimal(); p['fields'][key]='invented'; self.invalid(p,'/fields/'+key)

    def test_snapshot_correction_requires_explicit_clears(self):
        p=minimal(); p.update(expected_latest_version=1,correction_reason='Invented revision')
        with self.assertRaises(TestPlanValidationError): validate_request('PlanCorrection',p)
        p=validate_request('PlanCreate',minimal()); p.update(expected_latest_version=1,correction_reason='Invented revision')
        self.assertEqual(validate_request('PlanCorrection',p)['fields']['variations'],[])

    def test_numeric_and_boolean_types(self):
        for val in [True,0,-1,'2']:
            p=minimal(); p['fields']['trial_budget']=val; self.invalid(p,'/fields/trial_budget')

    def test_dates_zones_and_order(self):
        for k,v in [('development_start','2026-02-30'),('development_start','20261003'),('time_zone','Invented/NoZone')]:
            p=minimal(); p['fields'][k]=v; self.invalid(p,'/fields/'+k)
        p=minimal(); p['fields'].update(development_start='2026-10-03',development_end='2026-10-02'); self.invalid(p,'/fields/development_end')

    def test_missing_date_endpoint_draft_not_guessed(self):
        p=minimal(); p['fields']['development_start']='2026-10-03'
        p=validate_request('PlanCreate',p); self.assertIsNone(p['fields']['development_end'])

    def test_evaluation_conditionals(self):
        p=complete_fixture();p['fields']['initial_evaluation_start']='2021-01-01';self.invalid(p,'/fields/initial_evaluation_start')
        p=complete_fixture();p['fields'].update(evaluation_design='development_and_initial_evaluation',initial_evaluation_start='2020-12-31',initial_evaluation_end='2021-01-01');self.invalid(p,'/fields/initial_evaluation_start')

    def test_parameter_unknown_wrong_type_duplicate_budget(self):
        for override in [{'unknown':40},{'lookback_sessions':True},{'lookback_sessions':20}]:
            p=complete_fixture();p['fields']['variations'][0]['parameter_overrides']=override;self.invalid(p)
        p=complete_fixture();p['fields']['trial_budget']=1;self.invalid(p,'/fields/trial_budget')
        p=complete_fixture();p['fields']['parameters']*=2;self.invalid(p,'/fields/parameters/1/name')

    def test_decimal_semantic_duplicates_and_nonfinite(self):
        p=complete_fixture();p['fields']['parameters'][0].update(type='decimal',baseline_value='1.0');p['fields']['variations'][0]['parameter_overrides']={'lookback_sessions':'1.00'};self.invalid(p)
        for v in ['NaN','Infinity','1e2',3.14]:
            p=complete_fixture();p['criteria'][0]['fields']['threshold']=v;self.invalid(p,'/criteria/0/fields/threshold')

    def test_exact_decimal_precision_does_not_round_identity(self):
        p=complete_fixture()
        p['fields']['parameters'][0].update(type='decimal',baseline_value='1.00000000000000000000000000001')
        p['fields']['variations'][0]['parameter_overrides']={'lookback_sessions':'1.00000000000000000000000000002'}
        self.assertEqual(len(resolved_configurations(validate_request('PlanCreate',p)['fields'])),2)

    def test_completeness_follows_form_sections(self):
        paths=[x['path'] for x in draft_completeness(validate_request('PlanCreate',minimal()))['missing_fields']]
        self.assertLess(paths.index('/fields/pseudocode'),paths.index('/data_requirements'))
        self.assertLess(paths.index('/data_requirements'),paths.index('/fields/development_start'))
        self.assertLess(paths.index('/fields/development_start'),paths.index('/criteria'))
        self.assertLess(paths.index('/criteria'),paths.index('/fields/overall_interpretation'))

    def test_criterion_conditionals(self):
        p=complete_fixture();p['criteria'][0]['fields']['rule_type']='objective_rule';self.invalid(p,'/criteria/0/fields/threshold')
        p=complete_fixture();p['criteria'][0]['fields'].update(operator='between_inclusive',threshold='2',upper_threshold='1');self.invalid(p,'/criteria/0/fields/upper_threshold')
        p=complete_fixture();p['criteria'][0]['fields']['mandatory']=None
        self.assertEqual(draft_completeness(validate_request('PlanCreate',p))['draft_completeness'],'incomplete')

    def test_data_methods_and_inert_snippets(self):
        p=complete_fixture();d=p['data_requirements'][0]['fields'];d['retrieval_instructions']='<script>invented()</script>\nNever execute this fixture.'
        self.assertEqual(validate_request('PlanCreate',p)['data_requirements'][0]['fields']['retrieval_instructions'],d['retrieval_instructions'])
        for method in ['lean_sdk','existing_file']:
            p=complete_fixture();d=p['data_requirements'][0]['fields'];d['access_method']=method
            self.invalid(p,'/data_requirements/0/fields/base_url')
            for n in SCHEMA['$defs']['DataFields']['x-method-fields']['rest_api']:d[n]=None
            for n in SCHEMA['$defs']['DataFields']['x-method-fields'][method]:d[n]='Invented documented value'
            self.assertEqual(draft_completeness(validate_request('PlanCreate',p))['draft_completeness'],'complete')

    def test_keys_ownership_shape_and_configuration_references(self):
        p=complete_fixture();p['data_requirements'][0]['fields']['used_by_configurations']=['unlisted'];self.invalid(p)
        p=complete_fixture();p['data_requirements']*=2;self.invalid(p,'/data_requirements')
        p=complete_fixture();p['fields']['benchmark_data_keys']=['unknown'];p['fields']['benchmark_input_mode']='data_requirements';self.invalid(p)
        p=complete_fixture();p['criteria'][0]['criterion_id']='CRT-00000000-0000-4000-8000-000000000001';self.invalid(p)

    def test_size_and_whitespace(self):
        p=minimal();p['fields']['pseudocode']='x'*20001;self.invalid(p,'/fields/pseudocode')
        p=minimal();p['fields']['objective']=' \n ';self.assertIsNone(validate_request('PlanCreate',p)['fields']['objective'])
        p=minimal();p['fields']['title']=' ';self.invalid(p,'/fields/title')
        p=complete_fixture();p['data_requirements'][0]['fields']['retrieval_instructions']='x'*524289;self.invalid(p)

    def test_credentials_rejected_without_echo(self):
        p=complete_fixture();p['data_requirements'][0]['fields']['retrieval_instructions']='Authorization: Bearer inventedcredential1234'
        with self.assertRaises(TestPlanValidationError) as c:validate_request('PlanCreate',p)
        self.assertNotIn('inventedcredential1234',str(c.exception.issues))
        p=complete_fixture();p['data_requirements'][0]['fields']['documentation_url']='https://example.invalid/?token=invented'
        self.invalid(p)

    def test_report_validation(self):
        p={'plan_version_id':'TPLV-00000000-0000-4000-8000-000000000001','data_requirement_version_id':'DREQV-00000000-0000-4000-8000-000000000001','configuration_key':'baseline','performed_at':'2026-10-03T12:00:00Z','performed_by':'Invented author','tool':'Invented fixture test','outcome':'passed','check_scope':'Three invented rows','observations':'Invented schema matched','evidence_references':[{'label':'Invented fixture','uri':'urn:mv-rms:invented-fixture:v1','revision':None,'sha256':None}],'limitations':'No real provider or historical coverage checked','sanitized_evidence_confirmed':True,'expected_current_check_id':None,'supersedes_check_id':None,'correction_reason':None}
        self.assertEqual(validate_request('CheckCreate',p)['outcome'],'passed')
        p['supersedes_check_id']='DCHK-00000000-0000-4000-8000-000000000001'
        with self.assertRaises(TestPlanValidationError):validate_request('CheckCreate',p)

    def test_duplicate_keys_and_charset_parser(self):
        parser=StrictJSONParser()
        for raw in [b'{"fields":{"title":"x","title":"y"}}',b'{"x":NaN}',b'\xff']:
            with self.assertRaises(Exception): parser.parse(BytesIO(raw),'application/json; charset=utf-8')
        self.assertEqual(parser.parse(BytesIO(json.dumps(minimal()).encode()),'application/json; charset=utf-8'),minimal())


class Groups:
    def __init__(self,names):self.names=names
    def filter(self,**kw):return type('Query',(),{'exists':lambda _:bool(set(kw.get('name__in',[kw.get('name')])) & set(self.names))})()


class Actor:
    def __init__(self,names=(),active=True,authenticated=True):
        self.is_authenticated=authenticated;self.is_active=active;self.groups=Groups(names);self.is_staff=True;self.is_superuser=True


class Authorization(unittest.TestCase):
    def test_denied_operations_authorize_before_retrieval_or_replay(self):
        reads=[lambda a:service.read_test_plan(actor=a,plan_id='invented'),lambda a:service.read_test_plan_version(actor=a,plan_id='invented',version_id='invented'),lambda a:service.read_test_plan_history(actor=a,plan_id='invented'),lambda a:service.list_test_plans(actor=a,query={}),lambda a:service.read_criterion_version(actor=a,version_id='invented'),lambda a:service.read_data_requirement_version(actor=a,version_id='invented'),lambda a:service.list_data_access_checks(actor=a,plan_id='invented',query={}),lambda a:service.read_data_access_check(actor=a,plan_id='invented',check_id='invented')]
        writes=[lambda a:service.create_test_plan(actor=a,idempotency_key='fixture',payload={}),lambda a:service.correct_test_plan(actor=a,plan_id='invented',idempotency_key='fixture',payload={}),lambda a:service.record_data_access_check(actor=a,plan_id='invented',idempotency_key='fixture',payload={})]
        with patch.object(service,'_visible',side_effect=AssertionError('unauthorized retrieval')),patch.object(service,'validate_request',side_effect=AssertionError('unauthorized parsing')):
            for actor in [Actor(),Actor(['editor'],False),Actor(authenticated=False)]:
                for operation in reads+writes:
                    with self.assertRaises((Forbidden,AuthenticationRequired)):operation(actor)
            for operation in writes:
                with self.assertRaises(Forbidden):operation(Actor(['founder_viewer']))
        self.assertTrue(has_rms_read_access(Actor(['founder_viewer'])))
        self.assertTrue(has_rms_write_access(Actor(['editor'])))
        self.assertFalse(has_rms_write_access(Actor(['founder_viewer'])))
        self.assertFalse(has_rms_read_access(Actor()))


if __name__=='__main__': unittest.main()
