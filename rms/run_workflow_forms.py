"""Translate ordinary HTML form values into the shared Run service envelopes."""
import base64
import hashlib
from uuid import uuid4

from django import forms

from .run_result_models import RunLifecycleEvent
from .run_result_validation import MAX_ARTIFACT_BYTES


def narrative(label):
    return forms.CharField(label=label, max_length=2000, widget=forms.Textarea(attrs={'rows': 4}))


class RunForm(forms.Form):
    idempotency_key = forms.CharField(max_length=128, widget=forms.HiddenInput)
    expected_event_id = forms.CharField(required=False, max_length=42, widget=forms.HiddenInput)

    def __init__(self, *args, event_id=None, **kwargs):
        super().__init__(*args, initial={'expected_event_id': event_id, 'idempotency_key': str(uuid4())}, **kwargs)

    def payload(self):
        return {key: value for key, value in self.cleaned_data.items() if key != 'idempotency_key'} | {
            'expected_event_id': self.cleaned_data['expected_event_id'] or None,
        }

    def error_field(self, path):
        return path.strip('/').replace('-', '_').lower()


class EventForm(RunForm):
    state = forms.ChoiceField(label='Observed execution state', choices=[('', 'Choose a state'), *(
        (state, state.capitalize()) for state in RunLifecycleEvent.STATES
    )])
    reason = narrative('What was observed?')


class RetryForm(RunForm):
    external_reference = forms.CharField(max_length=106, label='New synthetic external reference',
                                        help_text='Invented label starting with synthetic:.')
    reason = narrative('Reason for recording a separate retry')


class ResultForm(RunForm):
    expected_result_version_id = forms.CharField(required=False, max_length=42, widget=forms.HiddenInput)
    correction_reason = narrative('Reason for correcting the previous result')
    summary = narrative('Result summary')

    def __init__(self, *args, result_id=None, criteria=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.criteria = criteria
        self.initial['expected_result_version_id'] = result_id
        if not (self.data.get('expected_result_version_id') if self.is_bound else result_id):
            del self.fields['correction_reason']
        for index, item in enumerate(criteria):
            rule = item['rule']
            label = rule['name'] or item['criterion_version_id']
            sample = forms.ChoiceField(label=f'{label}: Sample requirement met?', choices=[
                ('', 'Choose yes or no'), ('yes', 'Yes'), ('no', 'No'),
            ], help_text=rule.get('sample_requirement'))
            self.fields[f'{index}_sample_satisfied'] = sample
            if rule.get('rule_type') == 'numeric':
                self.fields[f'{index}_observed_value'] = forms.CharField(
                    label=f'{label}: Observed value', required=False, max_length=128,
                    help_text=f"{rule.get('operator', '')} {rule.get('threshold', '')} "
                              f"{rule.get('upper_threshold') or ''} {rule.get('units', '')} · "
                              f"Exact criterion {item['criterion_version_id']}",
                )
            else:
                self.fields[f'{index}_reported_outcome'] = forms.ChoiceField(
                    label=f'{label}: Reported outcome', choices=[('', 'Choose an outcome'), ('passed', 'Passed'),
                        ('failed', 'Failed'), ('inconclusive', 'Inconclusive')],
                    help_text=rule.get('objective_rule'),
                )
            self.fields[f'{index}_explanation'] = narrative(f'{label}: Explanation')
        self.fields['artifact_text'] = forms.CharField(label='Invented artifact text', max_length=MAX_ARTIFACT_BYTES,
                                                      strip=False, widget=forms.Textarea(attrs={'rows': 4}))
        self.fields['synthetic_confirmed'] = forms.BooleanField(label='I confirm the artifact is invented')

    def payload(self):
        clean = self.cleaned_data
        artifact_bytes = clean['artifact_text'].encode('utf-8')
        return {
            'completed_event_id': clean['expected_event_id'] or None,
            'expected_result_version_id': clean['expected_result_version_id'] or None,
            'correction_reason': clean.get('correction_reason'), 'summary': clean['summary'],
            'assessments': [{
                'criterion_edge_id': criterion['criterion_edge_id'], 'criterion_version_id': criterion['criterion_version_id'],
                'sample_satisfied': clean[f'{index}_sample_satisfied'] == 'yes',
                'observed_value': clean.get(f'{index}_observed_value') or None,
                'reported_outcome': clean.get(f'{index}_reported_outcome') or None,
                'explanation': clean[f'{index}_explanation'],
            } for index, criterion in enumerate(self.criteria)],
            'artifact': {'content_base64': base64.b64encode(artifact_bytes).decode('ascii'),
                         'sha256': hashlib.sha256(artifact_bytes).hexdigest(),
                         'synthetic_confirmed': clean['synthetic_confirmed']},
        }

    def error_field(self, path):
        parts = path.strip('/').split('/')
        if parts[0] == 'artifact':
            return 'artifact_text'
        if parts[0] == 'assessments' and len(parts) == 3:
            return f'{parts[1]}_{parts[2]}'
        return super().error_field(path)
