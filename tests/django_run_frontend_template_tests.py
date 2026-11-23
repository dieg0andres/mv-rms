"""Database-free render checks for invented Run and Result page fixtures."""
from django import forms
from django.template.loader import render_to_string
from django.test import SimpleTestCase


PLAN_URL = '/test-plans/TPL-invented/versions/TPLV-invented'
RUN_URL = PLAN_URL + '/runs/RUN-invented'
RESULT_URL = RUN_URL + '/results/RESV-invented'
STAMP = '2026-11-22T12:30:00Z'
SCOPE = {'plan_url': PLAN_URL, 'runs_url': PLAN_URL + '/runs', 'attempt_url': RUN_URL,
         'run_id': 'RUN-invented', 'plan_version_id': 'TPLV-invented', 'result_id': 'RESV-invented'}


class RunAttemptTemplateTests(SimpleTestCase):
    def test_failed_attempt_keeps_its_history_and_links_retry_without_authoring(self):
        page = render_to_string('rms/run_attempt_detail.html', {
            'scope': SCOPE,
            'attempt': {'run_id': SCOPE['run_id'], 'plan_version_id': SCOPE['plan_version_id'],
                        'configuration_key': 'baseline', 'external_reference': 'synthetic:failed',
                        'retry_successor': 'RUN-invented-retry',
                        'retry_successor_url': SCOPE['runs_url'] + '/RUN-invented-retry'},
            'execution_state': 'Failed',
            'events': [{'label': 'Failed', 'recorded_at': STAMP, 'recorded_by': 'fictional-reporter',
                        'reason': '<script>invented reason</script>'}],
        })
        self.assertInHTML('<h1>Synthetic run attempt</h1>', page)
        self.assertInHTML(f'<a href="{PLAN_URL}">Exact Test Plan definition</a>', page)
        self.assertIn('RUN-invented-retry', page)
        self.assertInHTML('<dt>Execution state</dt>', page)
        self.assertIn('No result recorded', page)
        self.assertIn('&lt;script&gt;invented reason&lt;/script&gt;', page)
        self.assertNotIn('Record an update', page)
        self.assertNotIn('<form', page)

    def test_completed_is_not_criteria_pass_and_history_pins_exact_result(self):
        page = render_to_string('rms/run_attempt_detail.html', {
            'scope': SCOPE, 'attempt': SCOPE, 'execution_state': 'Completed',
            'result_outcome': 'Mandatory criterion failed',
            'result_versions': [{'number': 1, 'id': 'RESV-original', 'url': RUN_URL + '/results/RESV-original',
                                 'outcome': 'Mandatory criterion failed', 'current': False},
                                {'number': 2, 'id': 'RESV-invented', 'url': RESULT_URL,
                                 'outcome': 'Mandatory criterion failed', 'current': True}],
        })
        self.assertIn('Completed', page)
        self.assertIn('Mandatory criterion failed', page)
        self.assertInHTML(f'<a href="{RUN_URL}/results/RESV-original">View result and history — version 1</a>', page)
        self.assertInHTML(f'<a href="{RESULT_URL}">View result and history — version 2</a>', page)
        self.assertIn('Historical', page)


class RunResultTemplateTests(SimpleTestCase):
    def render_result(self, **extra):
        return render_to_string('rms/run_result_detail.html', {
            'scope': SCOPE, 'execution_state': 'Completed',
            'result': {'id': SCOPE['result_id'], 'number': 2, 'current': False,
                       'outcome': 'Mandatory criterion failed', 'recorded_by': 'fictional-editor',
                       'recorded_at': STAMP, 'corrects': {'id': 'RESV-original',
                                                         'url': RUN_URL + '/results/RESV-original'},
                       'correction_reason': 'Invented correction'},
            'criteria': [{'id': 'CRIV-invented', 'label': 'Invented criterion', 'observation': 0,
                          'requirement': 'Mandatory', 'outcome': 'Failed', 'explanation': '<i>fiction</i>'}],
            'artifacts': [{'label': 'Invented artifact', 'byte_length': 12, 'sha256': 'a' * 64,
                           'provenance': 'Invented reporter', 'content_base64': 'do-not-render-content'}],
            **extra,
        })

    def test_historical_result_shows_lineage_zero_observation_and_metadata_only(self):
        page = self.render_result()
        self.assertIn('Historical result. This is not the current result version.', page)
        self.assertInHTML(f'<a href="{RUN_URL}/results/RESV-original"><code>RESV-original</code></a>', page)
        self.assertInHTML('<dd>0</dd>', page)
        self.assertIn('CRIV-invented', page)
        self.assertIn('&lt;i&gt;fiction&lt;/i&gt;', page)
        self.assertIn('a' * 64, page)
        self.assertNotIn('do-not-render-content', page)
        self.assertNotIn('Record an update', page)

    def test_result_links_to_its_own_readable_assurance_overview(self):
        assurance = RESULT_URL + '/assurance'
        page = self.render_result(assurance_url=assurance)
        self.assertInHTML(f'<a href="{assurance}">Open assurance for this exact result version</a>', page)
        self.assertNotIn('Record independent review', page)


class RunActionTemplateTests(SimpleTestCase):
    def test_bound_validation_error_keeps_input_and_associates_error_and_label(self):
        class FixtureForm(forms.Form):
            explanation = forms.CharField(widget=forms.Textarea, label='Explanation')
            idempotency_key = forms.CharField(widget=forms.HiddenInput)

        form = FixtureForm({'explanation': '<script>invented evidence</script>', 'idempotency_key': 'invented-key'})
        form.add_error('explanation', 'Explain the invented observation.')
        page = render_to_string('rms/run_workflow_action.html', {
            'scope': SCOPE, 'form': form, 'csrf_token': 'invented-test-token',
            'action': {'url': RESULT_URL + '/review', 'label': 'Record independent review',
                       'return_url': RESULT_URL, 'return_label': 'Back to exact result', 'submit_label': 'Save review'},
        })
        self.assertIn('tabindex="-1" data-run-error-summary', page)
        self.assertInHTML('<a href="#id_explanation">Explanation: Explain the invented observation.</a>', page)
        self.assertInHTML('<label for="id_explanation">Explanation:</label>', page)
        self.assertIn('aria-describedby="id_explanation_error"', page)
        self.assertIn('&lt;script&gt;invented evidence&lt;/script&gt;', page)
        self.assertIn('value="invented-key"', page)
        self.assertIn('name="csrfmiddlewaretoken" value="invented-test-token"', page)
        self.assertNotIn('Saved.', page)
