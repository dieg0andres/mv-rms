"""Pure API-1 shape, cross-field and completeness rules; no retrieval or execution."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qsl
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .hypothesis_validation import HypothesisValidationError

SCHEMA_PATH = Path(__file__).with_name('test_plan_schema.json')
SCHEMA = json.loads(SCHEMA_PATH.read_text())
SCHEMA_SHA256 = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
SCHEMA_VERSION = SCHEMA['x-schema-version']
TestPlanValidationError = HypothesisValidationError


def issue(path, code='invalid_value', message='Value does not match the published contract.'):
    return {'path': path, 'code': code, 'message': message}


def pointer(path, key):
    return path + '/' + str(key).replace('~', '~0').replace('/', '~1')


def _validate(value, rule, path, errors):
    if '$ref' in rule:
        rule = SCHEMA['$defs'][rule['$ref'].split('/')[-1]]
    types = rule.get('type', [])
    types = [types] if isinstance(types, str) else types
    if isinstance(value, str) and rule.get('x-trim'):
        value = value.strip()
        if not value and 'null' in types:
            value = None
    kinds = {'null': value is None, 'string': isinstance(value, str), 'integer': type(value) is int,
             'boolean': type(value) is bool, 'array': isinstance(value, list),
             'object': isinstance(value, dict) and all(isinstance(k, str) for k in value)}
    if types and not any(kinds.get(t, False) for t in types):
        errors.append(issue(path, 'invalid_type')); return value
    if ('enum' in rule and value not in rule['enum']) or ('const' in rule and value != rule['const']):
        errors.append(issue(path, 'invalid_value'))
    if value is None:
        return value
    if isinstance(value, str):
        if len(value) < rule.get('minLength', 0): errors.append(issue(path, 'required'))
        if len(value) > rule.get('maxLength', len(value)): errors.append(issue(path, 'too_long'))
        if 'pattern' in rule and re.fullmatch(rule['pattern'], value) is None: errors.append(issue(path, 'invalid_format'))
        fmt = rule.get('format')
        try:
            if fmt == 'date' and date.fromisoformat(value).isoformat() != value: raise ValueError
            if fmt == 'date-time':
                dt = datetime.fromisoformat(value)
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z',value) or dt.tzinfo is None: raise ValueError
            if fmt == 'iana-zone': ZoneInfo(value)
            if fmt in ('https-uri', 'evidence-uri'):
                url = urlsplit(value)
                if fmt == 'https-uri' and (url.scheme != 'https' or not url.hostname): raise ValueError
                if fmt == 'evidence-uri' and (url.scheme not in ('https','urn') or not (url.netloc or url.path)): raise ValueError
                if url.username or url.password: raise ValueError
                if any(k.lower() in ('token','password','secret','signature','sig','key','api_key','access_token','x-amz-signature','x-amz-credential') for k,_ in parse_qsl(url.query)): raise ValueError
        except (ValueError, ZoneInfoNotFoundError): errors.append(issue(path, 'invalid_format'))
    if type(value) is int and (value < rule.get('minimum',value) or value > rule.get('maximum',value)):
        errors.append(issue(path,'out_of_range'))
    if isinstance(value,list):
        if not rule.get('minItems',0) <= len(value) <= rule.get('maxItems',len(value)): errors.append(issue(path,'invalid_size'))
        return [_validate(v,rule.get('items',{}),pointer(path,i),errors) for i,v in enumerate(value)]
    if isinstance(value,dict):
        props = rule.get('properties',{})
        if not rule.get('minProperties',0) <= len(value) <= rule.get('maxProperties',len(value)): errors.append(issue(path,'invalid_size'))
        for k in rule.get('required',[]):
            if k not in value: errors.append(issue(pointer(path,k),'required'))
        result={}
        for k,v in value.items():
            if k not in props and rule.get('additionalProperties') is False: errors.append(issue(pointer(path,k),'unknown_field'))
            else: result[k]=_validate(v,props.get(k,rule.get('additionalProperties',{}) if isinstance(rule.get('additionalProperties'),dict) else {}),pointer(path,k),errors)
        return result
    return value


def _fill(fields, definition):
    props=SCHEMA['$defs'][definition]['properties']
    return {k: fields.get(k, [] if rule.get('type')=='array' else None) for k,rule in props.items()}


def _unique(items, key, path, errors):
    seen=set()
    for i,item in enumerate(items):
        value=item.get(key)
        if value is not None and value in seen: errors.append(issue(pointer(pointer(path,i),key),'duplicate_value'))
        seen.add(value)


def _typed(value,kind):
    if kind=='decimal': return isinstance(value,str) and re.fullmatch(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?',value) is not None and len(value)<=128
    return {'integer':type(value) is int, 'boolean':type(value) is bool,'string':isinstance(value,str) and len(value)<=4000}.get(kind,False)


def resolved_configurations(fields):
    baseline={p['name']:p['baseline_value'] for p in fields['parameters']}
    return [{'key':'baseline','parameters':baseline}]+[{'key':v['key'],'parameters':{**baseline,**v['parameter_overrides']}} for v in fields['variations']]


def _configuration_identity(parameters, declarations):
    # Decimal spelling does not create another experiment (1.0 equals 1.00).
    return tuple((k,Decimal(v) if declarations[k]['type']=='decimal' else json.dumps(v,sort_keys=True)) for k,v in sorted(parameters.items()))


def _pair(fields, start, end, path, errors):
    if fields.get(start) and fields.get(end) and fields[start]>fields[end]: errors.append(issue(pointer(path,end),'date_order'))


def _irrelevant(fields, names, path, errors):
    for n in names:
        if fields.get(n) not in (None,[]): errors.append(issue(pointer(path,n),'incompatible_field'))


def _secrets(value,path,errors):
    if isinstance(value,dict):
        for k,v in value.items(): _secrets(v,pointer(path,k),errors)
    elif isinstance(value,list):
        for i,v in enumerate(value): _secrets(v,pointer(path,i),errors)
    elif isinstance(value,str) and re.search(r'(?i)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bBearer\s+[a-z0-9._~-]{8,}|\b(?:password|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[\"\']?[^\s\"\']{8,}|postgres(?:ql)?://[^\s]+@)',value):
        errors.append(issue(path,'unsafe_evidence','Remove credential values from this field.'))


def _snapshot_rules(p,errors):
    f=p['fields']; params=f['parameters']; variations=f['variations']; data=p['data_requirements']
    _unique(params,'name','/fields/parameters',errors); _unique(variations,'key','/fields/variations',errors)
    declarations={x['name']:x for x in params}
    for i,x in enumerate(params):
        if not _typed(x['baseline_value'],x['type']): errors.append(issue(f'/fields/parameters/{i}/baseline_value','invalid_type'))
    for i,v in enumerate(variations):
        if v['key']=='baseline': errors.append(issue(f'/fields/variations/{i}/key','reserved_key'))
        for k,val in v['parameter_overrides'].items():
            if k not in declarations: errors.append(issue(pointer(f'/fields/variations/{i}/parameter_overrides',k),'unknown_parameter'))
            elif not _typed(val,declarations[k]['type']): errors.append(issue(pointer(f'/fields/variations/{i}/parameter_overrides',k),'invalid_type'))
    if not errors:
        seen=set()
        for i,c in enumerate(resolved_configurations(f)):
            token=_configuration_identity(c['parameters'],declarations)
            if token in seen: errors.append(issue('/fields/variations/'+str(i-1),'duplicate_configuration'))
            seen.add(token)
    if f['trial_budget'] is not None and f['trial_budget']<1+len(variations): errors.append(issue('/fields/trial_budget','insufficient_budget'))
    _pair(f,'development_start','development_end','/fields',errors)
    _pair(f,'initial_evaluation_start','initial_evaluation_end','/fields',errors)
    if f['evaluation_design']=='development_only': _irrelevant(f,['initial_evaluation_start','initial_evaluation_end'],'/fields',errors)
    if f['initial_evaluation_start'] and f['development_end'] and f['initial_evaluation_start']<=f['development_end']: errors.append(issue('/fields/initial_evaluation_start','period_overlap'))
    if f['benchmark_alignment']=='same_as_hypothesis': _irrelevant(f,['benchmark_difference_reason'],'/fields',errors)
    if f['benchmark_input_mode']=='defined_without_external_input': _irrelevant(f,['benchmark_data_keys'],'/fields',errors)
    keys=[x['fields']['key'] for x in data]
    if len(set(keys))!=len(keys): errors.append(issue('/data_requirements','duplicate_key'))
    for i,k in enumerate(f['benchmark_data_keys']):
        if k not in keys: errors.append(issue(f'/fields/benchmark_data_keys/{i}','unknown_data_key'))
    if len(set(f['benchmark_data_keys']))!=len(f['benchmark_data_keys']): errors.append(issue('/fields/benchmark_data_keys','duplicate_value'))
    for kind,identity,version in [('criteria','criterion_id','criterion_version_id'),('data_requirements','data_requirement_id','data_requirement_version_id')]:
        _unique(p[kind],identity,'/'+kind,errors)
        for i,child in enumerate(p[kind]):
            if (child[identity] is None)!=(child[version] is None): errors.append(issue(f'/{kind}/{i}','incomplete_identity'))
    for i,child in enumerate(p['criteria']):
        c=child['fields']; path=f'/criteria/{i}/fields'
        if c['rule_type'] is None and c['objective_rule'] is not None:
            _irrelevant(c,['operator','threshold','upper_threshold'],path,errors)
        if c['rule_type']=='objective_rule': _irrelevant(c,['operator','threshold','upper_threshold'],path,errors)
        if c['rule_type']=='numeric': _irrelevant(c,['objective_rule'],path,errors)
        if c['operator'] is not None and c['operator']!='between_inclusive': _irrelevant(c,['upper_threshold'],path,errors)
        if c['threshold'] is not None and c['upper_threshold'] is not None and Decimal(c['threshold'])>Decimal(c['upper_threshold']): errors.append(issue(path+'/upper_threshold','threshold_order'))
    configs={'baseline',*(v['key'] for v in variations)}
    methods=SCHEMA['$defs']['DataFields']['x-method-fields']
    for i,child in enumerate(data):
        d=child['fields']; path=f'/data_requirements/{i}/fields'
        _pair(d,'coverage_start','coverage_end',path,errors)
        selections=d['used_by_configurations']
        if selections and (len(set(selections))!=len(selections) or not set(selections)<=configs): errors.append(issue(path+'/used_by_configurations','invalid_configuration'))
        if d['access_method'] is None:
            populated=[method for method,names in methods.items() if any(d[n] is not None for n in names)]
            if len(populated)>1: errors.append(issue(path+'/access_method','incompatible_field'))
        if d['access_method']:
            _irrelevant(d,[n for method,names in methods.items() if method!=d['access_method'] for n in names],path,errors)
        if d['execution_location'] and d['execution_location']!='other_existing_tool': _irrelevant(d,['execution_tool'],path,errors)
        if d['credential_requirement'] and d['credential_requirement']!='existing_alias': _irrelevant(d,['credential_alias'],path,errors)
        _unique(d['field_schema'],'name',path+'/field_schema',errors)
        _secrets(d,path,errors)


def validate_json_size(payload):
    errors=[]
    try:
        if len(json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8'))>SCHEMA['x-max-request-bytes']: errors.append(issue('','too_large'))
    except (ValueError,TypeError,UnicodeError): errors.append(issue('','invalid_json'))
    if errors: raise TestPlanValidationError(errors)


def validate_request(name,payload):
    if name not in ('PlanCreate','PlanCorrection','CheckCreate','PlanListQuery','CheckListQuery'): raise ValueError('Unknown request schema.')
    validate_json_size(payload)
    errors=[]
    p=_validate(deepcopy(payload),SCHEMA['$defs'][name],'',errors)
    if errors: raise TestPlanValidationError(errors)
    if name.startswith('Plan') and name!='PlanListQuery':
        if name=='PlanCorrection':
            for k in SCHEMA['$defs']['PlanFields']['properties']:
                if k not in p['fields']: errors.append(issue('/fields/'+k,'required_snapshot_field'))
        p['fields']=_fill(p['fields'],'PlanFields')
        for collection,definition in [('parameters','Parameter'),('variations','Variation')]:
            for index,item in enumerate(p['fields'][collection]):
                if name=='PlanCorrection':
                    for key in SCHEMA['$defs'][definition]['properties']:
                        if key not in item: errors.append(issue(f'/fields/{collection}/{index}/{key}','required_snapshot_field'))
                p['fields'][collection][index]=_fill(item,definition)
        p.setdefault('criteria',[]); p.setdefault('data_requirements',[])
        for coll,definition in [('criteria','CriterionFields'),('data_requirements','DataFields')]:
            for index,item in enumerate(p[coll]):
                if name=='PlanCorrection':
                    for key in SCHEMA['$defs'][definition]['properties']:
                        if key not in item['fields']: errors.append(issue(f'/{coll}/{index}/fields/{key}','required_snapshot_field'))
                item['fields']=_fill(item['fields'],definition)
                if coll=='data_requirements':
                    for field_index,field in enumerate(item['fields']['field_schema']):
                        if name=='PlanCorrection':
                            for key in SCHEMA['$defs']['DataField']['properties']:
                                if key not in field: errors.append(issue(f'/{coll}/{index}/fields/field_schema/{field_index}/{key}','required_snapshot_field'))
                        item['fields']['field_schema'][field_index]=_fill(field,'DataField')
        _snapshot_rules(p,errors)
        if name=='PlanCreate' and any(x.get('criterion_id') or x.get('data_requirement_id') for x in p['criteria']+p['data_requirements']): errors.append(issue('','new_children_required'))
    if name=='CheckCreate':
        if p['expected_current_check_id']!=p['supersedes_check_id']: errors.append(issue('/supersedes_check_id','current_report_mismatch'))
        if bool(p['supersedes_check_id'])!=bool(p['correction_reason']): errors.append(issue('/correction_reason','correction_shape'))
        _secrets(p,'',errors)
    if name.endswith('ListQuery'):
        p.setdefault('page',1); p.setdefault('page_size',25)
    if errors: raise TestPlanValidationError(errors)
    return p


def draft_completeness(snapshot):
    """Snapshot is normalized by validate_request or persisted services."""
    missing=[]
    def need(fields,names,path):
        for n in names:
            if fields.get(n) is None or fields.get(n)==[] or fields.get(n)=='': missing.append(issue(pointer(path,n),'required_for_completeness','Required for draft completeness.'))
    f=snapshot['fields']; need(f,SCHEMA['$defs']['PlanFields']['x-completeness-required'],'/fields')
    if f['evaluation_design']=='development_and_initial_evaluation': need(f,['initial_evaluation_start','initial_evaluation_end'],'/fields')
    if f['benchmark_alignment']=='different': need(f,['benchmark_difference_reason'],'/fields')
    if f['benchmark_input_mode']=='data_requirements': need(f,['benchmark_data_keys'],'/fields')
    for i,p in enumerate(f['parameters']):
        need(p,['meaning'],f'/fields/parameters/{i}')
        if p['type'] in ('integer','decimal') and not p.get('units') and 'dimensionless' not in (p.get('meaning') or '').lower(): need(p,['units'],f'/fields/parameters/{i}')
    for i,v in enumerate(f['variations']): need(v,['name','rationale'],f'/fields/variations/{i}')
    if not snapshot['criteria']: missing.append(issue('/criteria','required_for_completeness','Include a mandatory criterion.'))
    elif not any(x['fields']['mandatory'] is True for x in snapshot['criteria']): missing.append(issue('/criteria','required_for_completeness','Include a mandatory criterion.'))
    for i,child in enumerate(snapshot['criteria']):
        c=child['fields']; path=f'/criteria/{i}/fields'
        need(c,SCHEMA['$defs']['CriterionFields']['x-completeness-required'],path)
        if c['rule_type']=='numeric':
            need(c,['units','operator','threshold'],path)
            if c['operator']=='between_inclusive': need(c,['upper_threshold'],path)
        if c['rule_type']=='objective_rule': need(c,['objective_rule'],path)
    if not snapshot['data_requirements']: missing.append(issue('/data_requirements','required_for_completeness','Include a data requirement.'))
    for i,child in enumerate(snapshot['data_requirements']):
        d=child['fields']; path=f'/data_requirements/{i}/fields'
        need(d,SCHEMA['$defs']['DataFields']['x-completeness-required'],path)
        if d['access_method']: need(d,SCHEMA['$defs']['DataFields']['x-method-fields'][d['access_method']],path)
        if d['execution_location']=='other_existing_tool': need(d,['execution_tool'],path)
        if d['credential_requirement']=='existing_alias': need(d,['credential_alias'],path)
        for j,x in enumerate(d['field_schema']): need(x,['data_type','units_meaning','nullable','use'],path+f'/field_schema/{j}')
    def missing_order(entry):
        parts=entry['path'].split('/')[1:]
        sections=SCHEMA['x-completeness-sections']
        for section,paths in enumerate(sections):
            for position,base in enumerate(paths):
                if entry['path']==base or entry['path'].startswith(base+'/'):
                    suffix=entry['path'][len(base):].strip('/').split('/')
                    # Integer item order, then declared child-field order.
                    item=int(suffix[0]) if suffix and suffix[0].isdigit() else -1
                    if parts[0] in ('criteria','data_requirements'):
                        definition='CriterionFields' if parts[0]=='criteria' else 'DataFields'
                        names=SCHEMA['$defs'][definition]['x-field-order']
                        name=parts[3] if len(parts)>3 else ''
                        field=names.index(name) if name in names else -1
                        nested=int(parts[4]) if len(parts)>4 and parts[4].isdigit() else -1
                        return section,position,item,field,nested
                    return section,position,item,-1,-1
        return len(sections),0,0,0,0
    missing.sort(key=missing_order)
    return {'schema_version':SCHEMA_VERSION,'draft_completeness':'incomplete' if missing else 'complete','missing_fields':missing}
