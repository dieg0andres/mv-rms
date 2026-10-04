"""Database-free adapter checks against the exact Backend API-1 schema.

RMS_TP_FRONTEND_SCHEMA is only a test input override for separate owned worktrees.
It never alters application runtime schema discovery or service behavior.
"""
from copy import deepcopy
from html.parser import HTMLParser
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.conf import settings
from django.core import signing
from django.db import DatabaseError
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve
from rest_framework.test import force_authenticate

from rms.navigation_views import NavigationPage
from rms.services import ResourceNotFound, ServiceError, StoredResponse
from rms.test_plan_views import (TestPlanEditorPage, TestPlanDetailPage, TestPlanListPage,
    TestPlanHistoryPage, DataCheckEditorPage, DataCheckListPage, editor_groups,
    read_plan_schema, decode_form, form_node, revision_payload)

PIN = 'HYPV-00000000-0000-4000-8000-000000000001'
HYP = 'HYP-00000000-0000-4000-8000-000000000001'
PLAN = 'TPL-00000000-0000-4000-8000-000000000001'
VERSION = 'TPLV-00000000-0000-4000-8000-000000000001'


def actor(role='editor', active=True):
    groups = Mock()
    groups.filter.side_effect = lambda **query: SimpleNamespace(exists=lambda: role in query.get('name__in', [query.get('name')]))
    return SimpleNamespace(pk=15, is_authenticated=True, is_active=active, groups=groups)


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.labels=[]; self.inputs={}; self.in_template=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag == 'template': self.in_template += 1
        if self.in_template: return
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag=='label': self.labels.append(attrs.get('for'))
        if tag=='input': self.inputs[attrs.get('name')] = attrs.get('value', '')
    def handle_endtag(self, tag):
        if tag=='template': self.in_template -= 1


class TestPlanRenderingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = read_plan_schema(os.environ.get('RMS_TP_FRONTEND_SCHEMA') or Path(settings.BASE_DIR) / 'rms/test_plan_schema.json')

    def setUp(self):
        self.factory=RequestFactory()
        self.reader=patch('rms.test_plan_views.read_plan_schema', return_value=self.schema)
        self.reader.start(); self.addCleanup(self.reader.stop)

    def request(self, method='get', data=None, role='editor', active=True, path='/test-plans/new'):
        request=getattr(self.factory, method)(path, data or {})
        request._dont_enforce_csrf_checks=True
        force_authenticate(request, user=actor(role, active))
        return request

    def snapshot(self):
        fields={name: [] if shape.get('type')=='array' else None for name,shape in self.schema['$defs']['PlanFields']['properties'].items()}
        fields['title']='Invented plan'
        return {'hypothesis_version_id': PIN, 'fields':fields, 'criteria': [], 'data_requirements': []}

    def record(self):
        return {**self.snapshot(), 'plan_id': PLAN, 'plan_version_id': VERSION, 'version':1,
            'hypothesis': {'stable_id':HYP,'version_id':PIN,'hypothesis_version_id':PIN,'version':1,'fields':{'title':'Invented claim','claim':'Invented mechanism','intended_benchmark_name':'Intended comparison'},'draft_completeness':'incomplete'},
            'research_context':{}, 'classification':'synthetic','draft_completeness':'incomplete',
            'missing_fields':[{'path':'/fields/pseudocode','message':'Describe algorithm'}],
            'current_indicators':{'as_of':'2026-10-03T00:00:00Z','upstream_notices':[], 'check_summary':{'status':'not_checked'}}, 'configurations':[{'key':'baseline','parameters':{},'digest':'invented'}]}

    def submitted(self, payload=None):
        payload=payload or self.snapshot()
        def flatten(value, path=''):
            out={}
            if isinstance(value,dict):
                # map control is one JSON field
                if path.endswith('/parameter_overrides'): return {path:json.dumps(value)}
                for key,item in value.items(): out.update(flatten(item,path+'/'+key))
            elif isinstance(value,list):
                if value and isinstance(value[0],dict):
                    for i,item in enumerate(value): out.update(flatten(item,path+'/'+str(i)))
                else: out[path]='\n'.join(value)
            else: out[path]='' if value is None else 'true' if value is True else 'false' if value is False else str(value)
            return out
        return {**flatten(payload), 'idempotency_key':'invented-original-key'}

    def test_schema_transport_retains_typed_repeat_items_order_and_decimal_strings(self):
        p=self.snapshot();p['fields']['parameters']=[{'name':'days','type':'integer','baseline_value':20,'units':'sessions','meaning':'lookback'}, {'name':'ratio','type':'decimal','baseline_value':'0.10','units':'dimensionless','meaning':'ratio'}]
        p['fields']['variations']=[{'key':'longer','name':'Longer','rationale':'invented','parameter_overrides':{'days':40}}]
        p['criteria']=[{'criterion_id':None,'criterion_version_id':None,'fields':{'name':'Second','mandatory':False}}, {'criterion_id':None,'criterion_version_id':None,'fields':{'name':'First','mandatory':True}}]
        result=decode_form(self.schema,self.schema['$defs']['PlanCreate'],self.submitted(p))
        self.assertEqual(result['fields'],p['fields'])
        self.assertEqual([x['fields']['name'] for x in result['criteria']],['Second','First'])
        self.assertIs(result['criteria'][0]['fields']['mandatory'],False)
        self.assertEqual(result['fields']['parameters'][1]['baseline_value'],'0.10')

    def test_malformed_override_and_duplicate_json_keys_remain_for_shared_rejection(self):
        p=self.snapshot();p['fields']['variations']=[{'key':'invented','parameter_overrides':{}}]
        raw=self.submitted(p);raw['/fields/variations/0/parameter_overrides']='{"days":20,"days":40}'
        result=decode_form(self.schema,self.schema['$defs']['PlanCreate'],raw)
        self.assertEqual(result['fields']['variations'][0]['parameter_overrides'],raw['/fields/variations/0/parameter_overrides'])

    def test_render_complete_editor_semantic_labels_unique_ids_and_inert_text(self):
        p=self.snapshot();p['fields']['pseudocode']='<script>invented()</script>';p['fields']['parameters']=[{'name':'invented','type':'integer','baseline_value':3,'units':'days','meaning':'fixture'}]
        html=render_to_string('rms/test_plan_form.html',{'payload':p,'groups':editor_groups(self.schema,p),'idempotency_key':'invented-key'})
        parser=FormParser();parser.feed(html)
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
        self.assertTrue(all(label in parser.ids for label in parser.labels))
        self.assertIn('&lt;script&gt;invented()&lt;/script&gt;',html)
        for heading in ['Purpose and Hypothesis','Strategy specification','Data','Test design','Evaluation','Review']: self.assertIn(heading,html)
        self.assertIn('Save draft',html);self.assertNotIn('<script>invented()',html)

    def test_failed_reference_retains_all_owned_text_order_and_key_rotates(self):
        p=self.snapshot();p['fields']['title']='<script>mine</script>'
        p['data_requirements']=[{'data_requirement_id':None,'data_requirement_version_id':None,'fields':{'key':'bars','retrieval_instructions':'<script>inert</script>','used_by_configurations':['baseline']}}]
        with patch('rms.test_plan_views.plan_service',side_effect=ResourceNotFound):
            response=TestPlanEditorPage.as_view()(self.request('post',self.submitted(p)))
        self.assertEqual(response.status_code,404);response.render();html=response.content.decode()
        self.assertIn('&lt;script&gt;mine&lt;/script&gt;',html);self.assertIn('&lt;script&gt;inert&lt;/script&gt;',html)
        self.assertEqual(response.context_data['payload']['data_requirements'][0]['fields']['key'],'bars')
        self.assertNotEqual(response.context_data['idempotency_key'],'invented-original-key')
        self.assertNotIn('Draft saved.',html)

    def test_unknown_save_locks_exact_payload_key_for_signed_unchanged_retry(self):
        p=self.snapshot();raw=self.submitted(p)
        with patch('rms.test_plan_views.plan_service',side_effect=DatabaseError):
            response=TestPlanEditorPage.as_view()(self.request('post',raw))
        self.assertEqual(response.status_code,503);response.render()
        token=response.context_data['retry_token']
        retry=signing.loads(token,salt='test-plan-retry')
        self.assertEqual(retry['payload'],p);self.assertEqual(retry['key'],'invented-original-key')
        retry_data={'retry_token':token,'idempotency_key':'invented-original-key','/fields/title':'attempted change'}
        stored=StoredResponse(201,json.dumps(self.record()).encode())
        with patch('rms.test_plan_views.plan_service',return_value=stored) as service:
            result=TestPlanEditorPage.as_view()(self.request('post',retry_data))
        self.assertEqual(result.status_code,303)
        self.assertEqual(service.call_args.kwargs['payload'],p)
        self.assertEqual(service.call_args.kwargs['idempotency_key'],'invented-original-key')
        self.assertIn(b'<fieldset disabled>',response.content)

    def test_forged_retry_never_calls_service(self):
        with patch('rms.test_plan_views.plan_service') as service:
            response=TestPlanEditorPage.as_view()(self.request('post',{'retry_token':'forged','idempotency_key':'invented'}))
        self.assertEqual(response.status_code,400);service.assert_not_called()

    def test_stale_conflict_preserves_proposal_and_explicit_reapply_changes_only_head(self):
        p=revision_payload(self.record());p['fields']['title']='Losing proposal';p['correction_reason']='Invented reason'
        with patch('rms.test_plan_views.plan_service',side_effect=ServiceError):
            response=TestPlanEditorPage.as_view()(self.request('post',self.submitted(p)),plan_id=PLAN)
        self.assertEqual(response.status_code,409);response.render()
        self.assertEqual(response.context_data['payload']['expected_latest_version'],1)
        self.assertIn(b'Compare latest in another tab',response.content)
        latest={**self.record(),'version':2};raw=self.submitted(p);raw['operation']='reapply_latest'
        with patch('rms.test_plan_views.plan_service',return_value=latest) as service:
            response=TestPlanEditorPage.as_view()(self.request('post',raw),plan_id=PLAN)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context_data['payload']['fields']['title'],'Losing proposal')
        self.assertEqual(response.context_data['payload']['expected_latest_version'],2)
        self.assertEqual(service.call_args.args[0],'read_test_plan')

    def test_exact_creation_pin_is_read_before_render_and_mismatch_hidden(self):
        q={'hypothesis_id':HYP,'hypothesis_version':'1','hypothesis_version_id':PIN}
        with patch('rms.test_plan_views.plan_service',return_value=self.record()['hypothesis']) as service:
            response=TestPlanEditorPage.as_view()(self.request(data=q))
        self.assertEqual(response.status_code,200)
        self.assertEqual(service.call_args.kwargs['version_id'],PIN)
        q['hypothesis_version_id']='HYPV-wrong'
        with patch('rms.test_plan_views.plan_service',return_value=self.record()['hypothesis']):
            response=TestPlanEditorPage.as_view()(self.request(data=q))
        self.assertEqual(response.status_code,404)

    def test_role_denials_precede_service_reads_and_schema_parsing(self):
        for role,active in [('none',True),('editor',False)]:
            for page in [TestPlanDetailPage,TestPlanListPage,TestPlanHistoryPage,DataCheckListPage,TestPlanEditorPage,DataCheckEditorPage]:
                with self.subTest(role=role,page=page):
                    kwargs={} if page in (TestPlanListPage,TestPlanEditorPage) else {'plan_id':PLAN}
                    with patch('rms.test_plan_views.plan_service') as service:
                        response=page.as_view()(self.request(role=role,active=active),**kwargs)
                    self.assertEqual(response.status_code,403);service.assert_not_called()
        with patch('rms.test_plan_views.plan_service') as service:
            response=TestPlanListPage.as_view()(self.factory.get('/test-plans'))
        self.assertEqual(response.status_code,401);service.assert_not_called()

    def test_viewer_reads_definition_history_checks_without_write_controls(self):
        record=self.record()
        for page,result,kwargs in [(TestPlanDetailPage,record,{'plan_id':PLAN}), (TestPlanHistoryPage,{'results':[record]}, {'plan_id':PLAN}), (DataCheckListPage,{'results':[],'count':0}, {'plan_id':PLAN})]:
            with patch('rms.test_plan_views.plan_service',return_value=result):
                response=page.as_view()(self.request(role='founder_viewer'),**kwargs)
            self.assertEqual(response.status_code,200);response.render()
            self.assertNotIn(b'Revise plan',response.content);self.assertNotIn(b'/data-checks/new',response.content)
            self.assertIn('no-store',response['Cache-Control'])

    def test_completeness_notices_and_checks_remain_separate_exact_service_outputs(self):
        record=self.record();record.update(draft_completeness='complete')
        record['current_indicators'].update(upstream_notices=[{'code':'review_needed','newer_version_id':'HYPV-invented2'}],check_summary={'status':'issues_reported'})
        with patch('rms.test_plan_views.plan_service',return_value=record):
            response=TestPlanDetailPage.as_view()(self.request(role='founder_viewer'),plan_id=PLAN,version_id=VERSION)
        response.render();html=response.content.decode()
        for label in ['Draft complete','Upstream review needed','Issues reported','Exact historical definition','Intended comparison']: self.assertIn(label,html)
        self.assertEqual(response.context_data['record'],record)

    def test_detail_query_cannot_fabricate_save_success(self):
        with patch('rms.test_plan_views.plan_service',return_value=self.record()):
            response=TestPlanDetailPage.as_view()(self.request(data={'saved':'1','receipt':'forged'}),plan_id=PLAN)
        response.render();self.assertNotIn(b'Draft saved.',response.content)

    def test_pagination_preserves_exact_version_filter_and_does_not_echo_api_url(self):
        result={'count':30,'page':1,'page_size':25,'next':'https://example.invalid/api?x','previous':None,'results':[]}
        with patch('rms.test_plan_views.plan_service',return_value=result):
            response=TestPlanListPage.as_view()(self.request(data={'hypothesis_version_id':PIN}))
        self.assertIn('hypothesis_version_id='+PIN,response.context_data['listing']['next'])
        self.assertNotIn('example.invalid',response.context_data['listing']['next'])

    def test_unknown_list_and_empty_list_are_different_states(self):
        with patch('rms.test_plan_views.plan_service',side_effect=DatabaseError):
            unavailable=TestPlanListPage.as_view()(self.request())
        unavailable.render();self.assertEqual(unavailable.status_code,503);self.assertIn(b'unknown, not zero',unavailable.content)
        with patch('rms.test_plan_views.plan_service',return_value={'count':0,'results':[]}):
            empty=TestPlanListPage.as_view()(self.request())
        empty.render();self.assertIn(b'No permitted plans',empty.content)

    def test_routes_reachable_in_owned_urlconf(self):
        for route in ['/test-plans','/test-plans/new',f'/test-plans/{PLAN}',f'/test-plans/{PLAN}/revise',f'/test-plans/{PLAN}/history',f'/test-plans/{PLAN}/versions/{VERSION}',f'/test-plans/{PLAN}/data-checks',f'/test-plans/{PLAN}/data-checks/new',f'/test-plans/{PLAN}/data-checks/DCHK-invented']:
            self.assertIsNotNone(resolve(route,urlconf='rms.test_plan_navigation_urls'))

    def test_home_plan_count_is_permission_scoped_and_unknown_when_unavailable(self):
        with patch('rms.navigation_views.shared_service',return_value={'count':0}), patch('rms.test_plan_views.plan_service',return_value={'count':3}) as service:
            response=NavigationPage.as_view()(self.request(path='/'))
        response.render();self.assertIn(b'Test Plans',response.content)
        self.assertEqual(response.context_data['home_counts'][-1]['count'],3)
        self.assertIs(service.call_args.kwargs['actor'].is_active,True)

    def test_fresh_get_sets_csrf_cookie_and_native_form_has_token(self):
        with patch('rms.test_plan_views.plan_service',return_value=self.record()['hypothesis']):
            response=TestPlanEditorPage.as_view()(self.request(data={'hypothesis_id':HYP,'hypothesis_version':'1','hypothesis_version_id':PIN}))
        response.render();self.assertIn('csrftoken',response.cookies);self.assertIn(b'csrfmiddlewaretoken',response.content)

    def test_explicit_sanitized_confirmation_is_not_fabricated_in_check_form(self):
        html=render_to_string('rms/test_plan_form.html',{'check_form':True,'groups':[{'label':'Report','nodes':[form_node(self.schema,self.schema['$defs']['CheckCreate'],'',{'plan_version_id':VERSION})]}]})
        self.assertIn('Confirm evidence contains no credentials',html)
        parser=FormParser();parser.feed(html)
        self.assertIn('/plan_version_id',parser.inputs)
        self.assertNotIn('value="true" selected',html)

    def test_unknown_form_paths_are_rejected_without_service_call_and_retained(self):
        raw=self.submitted();raw['/fields/invented_unknown']='own invented text'
        with patch('rms.test_plan_views.plan_service') as service:
            response=TestPlanEditorPage.as_view()(self.request('post',raw))
        self.assertEqual(response.status_code,400);service.assert_not_called();response.render()
        self.assertIn(b'own invented text',response.content)

    def test_post_requires_csrf_even_with_forced_authentication(self):
        request=self.request('post',self.submitted());request._dont_enforce_csrf_checks=False
        with patch('rms.test_plan_views.plan_service') as service:
            response=TestPlanEditorPage.as_view()(request)
        self.assertEqual(response.status_code,403);service.assert_not_called()

    def test_shared_validation_errors_bind_to_exact_item_and_preserve_value(self):
        class Invalid(Exception):
            issues=[{'path':'/criteria/0/fields/threshold','message':'Supply decimal text'}]
        p=self.snapshot();p['criteria']=[{'criterion_id':None,'criterion_version_id':None,'fields':{'name':'Invented','threshold':'abc'}}]
        with patch('rms.test_plan_views.plan_service',side_effect=Invalid):
            response=TestPlanEditorPage.as_view()(self.request('post',self.submitted(p)))
        response.render();html=response.content.decode()
        self.assertEqual(response.status_code,400)
        self.assertIn('Criteria / Item 1 / Fields / Threshold',html)
        self.assertIn('aria-describedby="tp/criteria/0/fields/threshold-errors"',html)
        self.assertIn('value="abc"',html)

    def test_version_history_uses_exact_ids_and_reports_revision_reason(self):
        record=self.record();record.update(correction_reason='Invented correction',changed_fields=['/fields/title'])
        with patch('rms.test_plan_views.plan_service',return_value={'results':[record]}):
            response=TestPlanHistoryPage.as_view()(self.request(role='founder_viewer'),plan_id=PLAN)
        response.render();self.assertIn(('/versions/'+VERSION).encode(),response.content)
        self.assertIn(b'Invented correction',response.content)
        self.assertIn(b'/fields/title',response.content)

    def test_html_and_json_use_identical_backend_shape_completeness_and_safe_errors(self):
        import importlib
        import importlib.util
        validator_path=os.environ.get('RMS_TP_FRONTEND_VALIDATOR')
        if validator_path:
            spec=importlib.util.spec_from_file_location('rms.frontend_frozen_test_plan_validation',validator_path)
            validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
        else:
            validator=importlib.import_module('rms.test_plan_validation')
        p=self.snapshot()
        html_payload=decode_form(self.schema,self.schema['$defs']['PlanCreate'],self.submitted(p))
        from_html=validator.validate_request('PlanCreate',html_payload)
        from_json=validator.validate_request('PlanCreate',json.loads(json.dumps(p)))
        self.assertEqual(from_html,from_json)
        self.assertEqual(validator.draft_completeness(from_html),validator.draft_completeness(from_json))
        p['fields']['trial_budget']=0
        def errors(value):
            try: validator.validate_request('PlanCreate',value)
            except Exception as error: return error.issues
            self.fail('Shared validator unexpectedly accepted invalid trial budget')
        self.assertEqual(errors(decode_form(self.schema,self.schema['$defs']['PlanCreate'],self.submitted(p))),errors(p))

    def test_partial_objective_rule_survives_save_detail_and_reopen_without_inferred_type(self):
        from urllib.parse import parse_qs, urlsplit
        from rms.test_plan_validation import validate_request, draft_completeness

        text = 'Invented output rule: <script>never_execute()</script>'
        proposed = self.snapshot()
        proposed['criteria'] = [{'criterion_id': None, 'criterion_version_id': None,
            'fields': {'name': 'Invented objective criterion', 'rule_type': None,
                       'objective_rule': text, 'mandatory': True}}]
        normalized = validate_request('PlanCreate', proposed)
        existing = {**self.record(), **deepcopy(normalized)}
        existing['criteria'][0].update(
            criterion_id='CRT-00000000-0000-4000-8000-000000000001',
            criterion_version_id='CRTV-00000000-0000-4000-8000-000000000001')

        for plan_id, kind in [(None, 'PlanCreate'), (PLAN, 'PlanCorrection')]:
            with self.subTest(request=kind):
                payload = deepcopy(normalized) if plan_id is None else revision_payload(existing)
                if plan_id:
                    payload['correction_reason'] = 'Invented incomplete-rule revision'
                before = deepcopy(payload)
                saved = {}

                def shared_save(operation, **kwargs):
                    self.assertEqual(operation, 'create_test_plan' if plan_id is None else 'correct_test_plan')
                    from_html = validate_request(kind, kwargs['payload'])
                    self.assertEqual(from_html, validate_request(kind, payload))
                    saved.update(self.record(), **deepcopy(from_html))
                    saved.update(draft_completeness(from_html))
                    return StoredResponse(201, json.dumps(saved).encode())

                # Persistence is mocked; the adopted validator/completeness and
                # POST, signed receipt, detail and editor templates are real.
                with patch('rms.test_plan_views.plan_service', side_effect=shared_save):
                    response = TestPlanEditorPage.as_view()(
                        self.request('post', self.submitted(payload)), plan_id=plan_id)
                self.assertEqual(response.status_code, 303)
                self.assertEqual(payload, before)
                self.assertIsNone(saved['criteria'][0]['fields']['rule_type'])
                self.assertEqual(saved['criteria'][0]['fields']['objective_rule'], text)
                self.assertIn('/criteria/0/fields/rule_type', [item['path'] for item in saved['missing_fields']])

                receipt = parse_qs(urlsplit(response['Location']).query)['receipt'][0]
                with patch('rms.test_plan_views.plan_service', return_value=saved):
                    detail = TestPlanDetailPage.as_view()(
                        self.request(data={'receipt': receipt}), plan_id=PLAN, version_id=VERSION)
                    reopened = TestPlanEditorPage.as_view()(self.request(), plan_id=PLAN)
                detail.render(); reopened.render()
                self.assertEqual(detail.status_code, 200)
                self.assertIn(b'Draft saved.', detail.content)
                self.assertIn(b'Draft incomplete', detail.content)
                self.assertIn(b'/criteria/0/fields/rule_type', detail.content)
                self.assertIn(b'Not checked', detail.content)
                for rendered in [detail.content, reopened.content]:
                    self.assertIn(b'&lt;script&gt;never_execute()&lt;/script&gt;', rendered)
                    self.assertNotIn(b'<script>never_execute()', rendered)
                self.assertIsNone(reopened.context_data['payload']['criteria'][0]['fields']['rule_type'])
                select = reopened.content.decode().split('name="/criteria/0/fields/rule_type"', 1)[1].split('</select>', 1)[0]
                self.assertNotIn(' selected', select)

    def test_explicit_reapply_updates_current_child_references_and_retains_definitions(self):
        record=self.record()
        record['criteria']=[{'criterion_id':'CRT-invented1','criterion_version_id':'CRTV-old','fields':{'name':'My proposal'}}, {'criterion_id':'CRT-removed','criterion_version_id':'CRTV-removed','fields':{'name':'My removed-item proposal'}}]
        p=revision_payload(record);p['correction_reason']='Deliberate reapplication'
        latest=self.record();latest.update(version=2)
        latest['criteria']=[{'criterion_id':'CRT-invented1','criterion_version_id':'CRTV-current','fields':{'name':'Other editor'}}]
        raw=self.submitted(p);raw['operation']='reapply_latest'
        with patch('rms.test_plan_views.plan_service',return_value=latest):
            response=TestPlanEditorPage.as_view()(self.request('post',raw),plan_id=PLAN)
        proposal=response.context_data['payload'];self.assertEqual(proposal['criteria'][0]['criterion_version_id'],'CRTV-current')
        self.assertEqual(proposal['criteria'][0]['fields']['name'],'My proposal')
        self.assertIsNone(proposal['criteria'][1]['criterion_id'])
        self.assertEqual(proposal['criteria'][1]['fields']['name'],'My removed-item proposal')
        self.assertEqual(proposal['hypothesis_version_id'],PIN)
