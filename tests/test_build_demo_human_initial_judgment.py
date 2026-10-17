#!/usr/bin/env python
"""TASK-035 bounded pure-memory protocol tests with registered human input only.

The accepted TASK-028 short evidence closure is reused read-only, never its suite.
Technical projections are memory fixtures, not current Gate/fact/history verification.
"""
from __future__ import annotations
import argparse
import ast
import builtins
import copy
from contextlib import contextmanager
import datetime
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import random
import secrets
import socket
import subprocess
import sys
import time
import traceback
import types
import uuid

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / 'data/human_initial_judgment_tests'
CORE_PATH = ROOT / 'scripts/build_demo_human_initial_judgment.py'
FIXTURE = ROOT / 'data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json'
SUPPLEMENT = TEST_ROOT / 'task035_setup_01/human_fixture_supplement_02.json'
TEXT_SUPPLEMENT = TEST_ROOT / 'task035_setup_01/human_fixture_supplement_03.json'
PACKET = ROOT / 'data/runtime/task033_r1_run_02/normal.facts/fact_packet.json'
def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
def sha(raw): return hashlib.sha256(raw).hexdigest()
def fp(value): return sha(canon(value))
def evidence_value(value):
    """Lossless tagged evidence for illegal JSON candidates; never changes core inputs."""
    if type(value) is bytes: return {'$python_type': 'bytes', 'hex': value.hex()}
    if type(value) is float and not math.isfinite(value):
        return {'$python_type': 'float', 'repr': repr(value)}
    if type(value) is str:
        try: value.encode('utf-8')
        except UnicodeError: return {'$python_type': 'str', 'escaped': ascii(value)}
        return value
    if type(value) in (list, tuple): return [evidence_value(item) for item in value]
    if type(value) is dict: return {key: evidence_value(item) for key, item in value.items()}
    return value
def input_points(refs):
    points = []
    for value in refs:
        snapshot = evidence_value(copy.deepcopy(value))
        try: raw_fp, reason = fp(value), None
        except (TypeError, ValueError, UnicodeError) as exc:
            raw_fp, reason = None, type(exc).__name__ + ': ' + str(exc)
        points.append({'reference_id': id(value), 'snapshot': snapshot, 'fingerprint': fp(snapshot),
            'fingerprint_scope': 'recorded_evidence_snapshot', 'raw_canonical_sha256': raw_fp,
            'raw_canonical_unavailable_reason': reason})
    return points
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
def evidence_module():
    e = load(ROOT / 'tests/test_runtime_approved_load.py', 'task035_readonly_short_closure')
    e.jsonable, e.core_input_point = evidence_value, input_points
    original = e.build_candidate
    def build(*args, **kwargs):
        value = original(*args, **kwargs)
        value['summary']['task'] = 'TASK-035'
        observer = args[1]
        value['summary']['observed'] = {'pure_core_original_code_entries': observer.count if observer else None,
            'new_calls_in_replay': None if observer else 'external code profiler required; historical records are not calls',
            'other_business_entries': None, 'reason': 'no other business module imported or invoked by this suite'}
        value['summary']['record_categories'] = {role: sum(x.get('record_category') == role for x in value['api_records'])
            for role in ('pure_core', 'evidence_audit_helper_control')}
        return value
    e.build_candidate = build
    return e

@contextmanager
def pure_guard(log, prove=False):
    saved, phase = [], {'value': 'probe' if prove else 'core'}
    def replace(obj, key, fn):
        saved.append((obj, key, getattr(obj, key)))
        setattr(obj, key, fn)
    def denied(name):
        def block(*args, **kwargs):
            log[phase['value']].append(name)
            raise AssertionError('TASK035_GUARD:' + name)
        return block
    try:
        targets = [(builtins, 'open'), (io, 'open'), (os, 'open'), (socket, 'socket'), (subprocess, 'Popen'),
            (time, 'time'), (time, 'time_ns'), (time, 'monotonic'), (time, 'perf_counter'), (time, 'sleep'),
            (random, 'random'), (random, 'randint'), (random, 'randrange'), (random, 'getrandbits'),
            (secrets, 'token_bytes'), (uuid, 'uuid4'), (os, 'getenv'), (type(os.environ), '__getitem__')]
        for obj, name in targets: replace(obj, name, denied(obj.__name__ + '.' + name))
        original_date, original_datetime = datetime.date, datetime.datetime
        class GuardDate(original_date):
            today = classmethod(denied('datetime.date.today'))
        class GuardDatetime(original_datetime):
            now = classmethod(denied('datetime.datetime.now'))
            utcnow = classmethod(denied('datetime.datetime.utcnow'))
            today = classmethod(denied('datetime.datetime.today'))
        replace(datetime, 'date', GuardDate)
        replace(datetime, 'datetime', GuardDatetime)
        if prove:
            probes = [('builtins.open', lambda: builtins.open('TASK035_MUST_NOT_BE_OPENED', 'rb')),
                ('io.open', lambda: io.open('TASK035_MUST_NOT_BE_OPENED', 'rb')),
                ('os.open', lambda: os.open('TASK035_MUST_NOT_BE_OPENED', os.O_RDONLY)),
                ('socket.socket', socket.socket), ('subprocess.Popen', lambda: subprocess.Popen(['TASK035_MUST_NOT_START'])),
                ('time.time', time.time), ('time.time_ns', time.time_ns), ('time.monotonic', time.monotonic),
                ('time.perf_counter', time.perf_counter), ('time.sleep', lambda: time.sleep(0)),
                ('random.random', random.random), ('random.randint', lambda: random.randint(0, 1)),
                ('random.randrange', lambda: random.randrange(1)), ('random.getrandbits', lambda: random.getrandbits(1)),
                ('secrets.token_bytes', secrets.token_bytes), ('uuid.uuid4', uuid.uuid4),
                ('os.getenv', lambda: os.getenv('TASK035_PROBE')),
                ('os._Environ.__getitem__', lambda: os.environ['TASK035_PROBE']),
                ('datetime.date.today', datetime.date.today), ('datetime.datetime.now', datetime.datetime.now),
                ('datetime.datetime.utcnow', datetime.datetime.utcnow), ('datetime.datetime.today', datetime.datetime.today)]
            for name, probe in probes:
                try: probe()
                except AssertionError as exc: log['proof'].append({'entry': name, 'blocked': True, 'message': str(exc)})
                else: log['proof'].append({'entry': name, 'blocked': False})
        phase['value'] = 'core'
        yield
    finally:
        for obj, name, original in reversed(saved): setattr(obj, name, original)

class Observer:
    def __init__(self, core, e):
        self.e, self.count = e, 0
        self.real = core.build_human_initial_judgment_record
        self.code = self.real.__code__
        self.step_codes = {getattr(core, name).__code__: i for i, name in enumerate((
            '_submission', '_materials', '_expectations', '_history', '_binding_relations',
            '_materials_digest', '_file_relations', '_fact_gate_relations',
            '_optional_relations', '_history_relations'), 1)}
        self.steps_by_parent = {}
        self.native_returns = {}
        self.api, self.normalizer, self.loader, self._other = {}, None, None, {}
        def observed(*args, **kwargs):
            cid = e.CALL_STACK[-1]
            nid = f'core_{len(e.CORE_RECORDS)+1:04d}'
            refs = [*args[:3], kwargs.get('prior_history')]
            e.CORE_INPUT_REFS[nid] = refs
            record = {'nested_id': nid, 'core': 'human_initial_judgment', 'caller_api': cid,
                'args': e.jsonable(args), 'kwargs': e.jsonable(kwargs), 'input_refs_before': e.core_input_point(refs)}
            try:
                returned = self.real(*args, **kwargs)
                self.native_returns[cid] = returned
                record.update(outcome='returned', **{'return': copy.deepcopy(returned)})
                return returned
            except Exception as exc:
                record.update(outcome='exception', exception_type=type(exc).__name__, exception_str=str(exc),
                    field=getattr(exc, 'field', None), stage=getattr(exc, 'stage', None), reasons=copy.deepcopy(getattr(exc, 'reasons', None)),
                    cause_chain=e.chain_of(exc), traceback=traceback.format_exc())
                raise
            finally:
                record['input_refs_after'] = e.core_input_point(refs)
                e.CORE_RECORDS.append(record)
        core.build_human_initial_judgment_record = observed
    def profile(self, frame, event, arg):
        if event == 'call' and frame.f_code is self.code:
            self.count += 1
            self.api['build_human_initial_judgment_record'] = self.count
        if event == 'call' and frame.f_code in self.step_codes and self.e.CALL_STACK:
            self.steps_by_parent.setdefault(self.e.CALL_STACK[-1], []).append(self.step_codes[frame.f_code])

def make_base(packet, packet_raw, human, contract_raw):
    """Independent test constructor. All non-packet/contract file claims are technical memory fixtures."""
    batch, request = 'TECHNICAL-BATCH-035', 'TECHNICAL-REQUEST-035'
    contract = {'contract_version': 'V1', 'contract_file_sha256': sha(contract_raw), 'contract_effective': True}
    run = {'code': {'file_sha256': sha(b'TECHNICAL-runtime-code'), 'manifest_fingerprint': fp({'technical': 'code-manifest'})},
           'rules': {'version': 'TECHNICAL-RULES-035', 'manifest_fingerprint': fp({'technical': 'rule-manifest'})},
           'config': {'file_sha256': sha(b'TECHNICAL-config')}, 'input': {'file_sha256': packet['bindings']['workbook_sha256']}}
    role_names = ('facts.started', 'facts.packet', 'facts.markdown', 'facts.artifacts', 'runtime.registry', 'contract', 'gate1.record', 'gate2.record')
    buffers = {role: canon({'fixture_label': 'PROTOCOL_TEST_FIXTURE_ONLY', 'technical_role': role})+b'\n' for role in role_names}
    buffers.update({'facts.packet': packet_raw, 'contract': contract_raw})
    files = sorted([{'role': role, 'relative': 'fixture035/' + role.replace('.', '/') + '.json',
        'file_sha256': sha(buffers[role]), 'byte_size': len(buffers[role])} for role in role_names], key=lambda x: x['relative'].encode('utf-8'))
    gates = {}
    for role, gate in (('gate1', 'GATE1'), ('gate2', 'GATE2')):
        gates[role] = {'gate': gate, 'batch_id': batch, 'event_id': 'TECHNICAL-'+gate+'-REFERENCE',
            'record_fingerprint': fp({'technical_gate_record': gate}), 'record_file_sha256': sha(buffers[role+'.record']),
            'materials_fingerprint': fp({'technical_gate_material': gate}), 'contract_binding': copy.deepcopy(contract),
            'run_binding': copy.deepcopy(run), 'decision': 'APPROVE', 'actor_kind': 'HUMAN_DECLARED'}
    gates['gate2']['prior_gate1_fingerprint'] = gates['gate1']['record_fingerprint']
    fact = {'inspect_binding': {'stage_version': 'TASK-033-fact-packet-1.0', 'status': 'RT_FACT_PACKET_RECORDED',
            'batch_id': batch, 'run_binding_sha256': fp(run)}, 'packet': copy.deepcopy(packet),
        'packet_canonical_sha256': fp(packet), 'finding_ids': [x['finding_id'] for x in packet['findings']],
        'source_fingerprints': {key: packet['bindings'][key] for key in ('workbook_sha256', 'normalized_payload_sha256', 'screening_report_sha256', 'crosscheck_report_sha256')}}
    material = {'materials_version': 'TASK-034-human-initial-judgment-materials-1.0', 'batch_id': batch,
        'runtime_version': 'TECHNICAL-RUNTIME-035', 'entity': copy.deepcopy(packet['entity']), 'contract_binding': contract,
        'run_binding': run, 'fact_snapshot': fact, 'gate_links': gates, 'files': files}
    material['materials_fingerprint'] = fp(material)
    submission = {'submission_version': 'TASK-034-human-initial-judgment-submission-1.0', 'event_id': human['event_id'], 'batch_id': batch,
        'request_binding': {'request_id': request, 'materials_fingerprint': material['materials_fingerprint']},
        'submission_source': 'HUMAN_INITIAL_JUDGMENT', 'actor': {'actor_kind': 'HUMAN_DECLARED', 'actor_id': human['actor_id'], 'declaration_note': human['declaration_note']},
        'decided_at_raw': human['decided_at_raw'], 'assessment': human['assessment'], 'reason': human['reason']}
    history = {'declared_complete': True, 'declared_scope': 'TECHNICAL-INITIAL-JUDGMENT-INDEX', 'records': []}
    expected = {'expectations_version': 'TASK-034-human-initial-judgment-expectations-1.0', 'expected_batch_id': batch,
        'expected_request_id': request, 'expected_materials_fingerprint': material['materials_fingerprint'],
        'expected_contract': copy.deepcopy(contract), 'expected_runtime_version': material['runtime_version'], 'expected_run_binding': copy.deepcopy(run),
        'expected_fact_binding': copy.deepcopy({k: v for k, v in fact.items() if k != 'packet'}), 'expected_gate_links': copy.deepcopy(gates),
        'expected_files': copy.deepcopy(files), 'expected_history_scope': history['declared_scope'], 'expected_prior_history_fingerprint': fp(history)}
    return [submission, material, expected, history]

def expected_return(values):
    """Protocol-derived full record expectation; never calls any core helper."""
    s, m, e, h = copy.deepcopy(values)
    for key in ('finding_notes', 'evidence_requests'): s.setdefault(key, [])
    record = {'record_version': 'TASK-034-human-initial-judgment-record-1.0', 'record_status': 'HUMAN_INITIAL_JUDGMENT_VALIDATED',
        'mode': 'LOCAL_DECLARED_SYNTHETIC', 'binding': {'batch_id': m['batch_id'], 'request_id': s['request_binding']['request_id'],
            'materials_fingerprint': m['materials_fingerprint'], 'runtime_version': m['runtime_version'], 'entity': m['entity'],
            'contract_binding': m['contract_binding'], 'run_binding': m['run_binding'],
            'fact_binding': {k: v for k, v in m['fact_snapshot'].items() if k != 'packet'}, 'gate_links': m['gate_links'], 'files': m['files']},
        'human_initial_judgment': s, 'decided_at_source': 'HUMAN_PROVIDED_RAW',
        'history_binding': {'declared_scope': h['declared_scope'], 'prior_history_fingerprint': fp(h)},
        'boundaries': {k: False for k in ('persisted','execution_allowed','next_step_allowed','ai_enabled','final_judgment_recorded','identity_authenticated','source_authenticity_proven','audit_conclusion_formed')},
        'note': '仅在内存校验人类明确提交及其绑定；未保存，不批准执行，不认证身份，不形成审计结论，不开放AI或终判。'}
    return {'record': record, 'record_fingerprint': fp(record)}

def rebind(values):
    s, m, e, h = values
    digest = fp({k: v for k, v in m.items() if k != 'materials_fingerprint'})
    m['materials_fingerprint'] = s['request_binding']['materials_fingerprint'] = e['expected_materials_fingerprint'] = digest

def changed_paths(before, after, path):
    if canon(evidence_value(before)) == canon(evidence_value(after)): return []
    if type(before) is dict and type(after) is dict:
        result = []
        for key in sorted(set(before) | set(after)):
            if key not in before or key not in after: result.append(path+'.'+key)
            else: result.extend(changed_paths(before[key],after[key],path+'.'+key))
        return result
    if type(before) is list and type(after) is list and len(before)==len(after):
        return [name for i,(a,b) in enumerate(zip(before,after)) for name in changed_paths(a,b,f'{path}[{i}]')]
    return [path]

def reverse_object_keys(value):
    """Change dictionary insertion order recursively; keep list members/order intact."""
    if type(value) is dict:
        return {key: reverse_object_keys(item) for key, item in reversed(list(value.items()))}
    if type(value) is list: return [reverse_object_keys(item) for item in value]
    return value

def run(e, out):
    baseline = json.loads((ROOT/'data/reviews/task034_gpt_20261016_115103/source_hashes_after.json').read_bytes())
    source_paths = [FIXTURE, SUPPLEMENT, SUPPLEMENT.with_name('human_fixture_supplement_01.json'), PACKET, ROOT/'docs/AUDIT_CONTRACT.md']
    if TEXT_SUPPLEMENT.is_file(): source_paths.append(TEXT_SUPPLEMENT)
    sources = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p.read_bytes()), 'byte_size': p.stat().st_size} for p in source_paths}
    assert sources[FIXTURE.relative_to(ROOT).as_posix()]['sha256'] == '81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560'
    for p in (FIXTURE, PACKET, ROOT/'docs/AUDIT_CONTRACT.md'): assert sources[p.relative_to(ROOT).as_posix()]['sha256'] == baseline[p.relative_to(ROOT).as_posix()]
    for p in source_paths: (out/(p.name+'.source.bin')).write_bytes(p.read_bytes())
    human = json.loads(FIXTURE.read_bytes())['human_values']
    extra_human = json.loads(SUPPLEMENT.read_bytes())['human_values']
    packet_raw = PACKET.read_bytes()
    base = make_base(json.loads(packet_raw), packet_raw, human, (ROOT/'docs/AUDIT_CONTRACT.md').read_bytes())
    (out/'technical_base.json').write_bytes(canon({'fixture_label': 'PROTOCOL_TEST_FIXTURE_ONLY',
        'not_current_runtime_verification': True, 'submission': base[0], 'materials': base[1], 'expectations': base[2], 'prior_history': base[3]})+b'\n')
    raw = CORE_PATH.read_bytes()
    code = compile(raw, str(CORE_PATH), 'exec')
    core = types.ModuleType('task035_core_under_test')
    core.__file__ = str(CORE_PATH)
    sys.modules[core.__name__] = core
    guard_log = {'probe': [], 'proof': [], 'core': []}
    with pure_guard(guard_log, prove=True): exec(code, core.__dict__)
    e.check('IJ-34.import_guard', len(guard_log['proof']) == 22 and all(x['blocked'] for x in guard_log['proof']) and not guard_log['core'], guard_log)
    obs = Observer(core, e)
    case_map = {f'IJ-{i:02d}': [] for i in range(1, 35)}
    sys.setprofile(obs.profile)
    def invoke(label, values, *, field=None, rehash=False, omit_history=False, guarded=False, expect_error=False, step=None):
        if rehash: rebind(values)
        before = obs.count
        s, m, ex, h = values
        kwargs = {} if omit_history else {'prior_history': h}
        fn = core.build_human_initial_judgment_record
        def guarded_call(*args, **kw):
            with pure_guard(guard_log): return fn(*args, **kw)
        err, result, cid = e.call_api(core, label, guarded_call if guarded else fn, s, m, ex, **kwargs)
        e.API_RECORDS[-1].update(record_category='pure_core', reasons=copy.deepcopy(getattr(err,'reasons',None)),
            actual_core_delta=obs.count-before, controlled_candidate=field is not None or expect_error,
            expected_protocol_step=step,
            actual_protocol_steps_entered=obs.steps_by_parent.get(cid, []),
            actual_changed_paths_from_registered_base=[name for a,b,p in zip(base,values,('submission','materials','expectations','prior_history')) for name in changed_paths(a,b,p)],
            construction={'R_M_before_call': rehash, 'only_R_M_sync': ['materials.materials_fingerprint','submission.request_binding.materials_fingerprint','expectations.expected_materials_fingerprint'] if rehash else []})
        case_map.setdefault(label.split(':')[0], []).append(cid)
        if field is not None:
            e.check(label, isinstance(err, core.HumanInitialJudgmentBlocked) and err.field == field and err.reasons == [err.reason] and bool(err.reason) and result is None
                and (step is None or obs.steps_by_parent.get(cid)==list(range(1,step+1))),
                {'call_id': cid, 'expected_field': field, 'actual_field': getattr(err,'field',None), 'type': type(err).__name__,
                 'expected_protocol_step':step,'actual_protocol_steps_entered':obs.steps_by_parent.get(cid,[])})
        elif not expect_error:
            e.check(label, err is None and canon(result) == canon(expected_return(values)), {'call_id': cid, 'error': str(err) if err else None})
        return err, result, cid
    def bad(label, edit, field, rehash=False):
        values = copy.deepcopy(base)
        edit(values)
        return invoke(label, values, field=field, rehash=rehash)
    try:
        _, normal, normal_id = invoke('IJ-01:normal', copy.deepcopy(base))
        _, recursive_reversed, _ = invoke('R1:valid_recursive_key_reversal', reverse_object_keys(copy.deepcopy(base)))
        e.check('R1:success_record_unchanged', canon(normal)==canon(recursive_reversed)
            and all(type(x) is bool and x is False for x in normal['record']['boundaries'].values()))
        # Illegal candidates remain actual bytes/NaN/surrogate objects passed to the
        # core; only evidence serialization uses explicit reversible type tags.
        for label, location, key, value in (
            ('company_bytes', 'materials', 'company', b'bad-company'),
            ('company_nan', 'materials', 'company', float('nan')),
            ('period_start_bytes', 'materials', 'period_start', b'bad-date'),
            ('packet_company_bytes', 'packet', 'company', b'bad-company'),
            ('currency_bad_utf8', 'materials', 'currency', '\ud800'),
            ('period_end_null', 'materials', 'period_end', None),
            ('cutoff_integer', 'materials', 'cutoff_date', 20260930)):
            values=copy.deepcopy(base)
            entity=values[1]['fact_snapshot']['packet']['entity'] if location=='packet' else values[1]['entity']
            parent=entity['period'] if key.startswith('period_') else entity
            parent[key]=value
            prefix='materials.fact_snapshot.packet.entity' if location=='packet' else 'materials.entity'
            invoke('R1-B1:'+label,values,field=prefix+('.period.' if key.startswith('period_') else '.')+key,step=2)
        # Each relation candidate has correct earlier schemas. Expected values are
        # fixed before invocation; no refresh of a target's independent expectation.
        for candidate_reverse in (False,True):
            for expected_reverse in (False,True):
                suffix=f'candidate_reverse={candidate_reverse},expected_reverse={expected_reverse}'
                for family, first_field, step in (
                    ('entity','materials.entity.company',2),
                    ('run','materials.run_binding.code.file_sha256',5),
                    ('fact','materials.fact_snapshot.finding_ids[0]',8),
                    ('gate','materials.gate_links.gate2.event_id',8),
                    ('files','materials.files[1].file_sha256',7)):
                    values=copy.deepcopy(base)
                    if family=='entity':
                        values[1]['entity'].update(company='TECHNICAL-WRONG-COMPANY',currency='TECHNICAL-WRONG-CURRENCY')
                    elif family=='run':
                        values[1]['run_binding']['code']['file_sha256']='0'*64
                        values[1]['run_binding']['config']['file_sha256']='0'*64
                    elif family=='fact':
                        values[2]['expected_fact_binding']['finding_ids']=['TECHNICAL-WRONG-ID']
                        values[2]['expected_fact_binding']['source_fingerprints']['normalized_payload_sha256']='0'*64
                    elif family=='gate':
                        values[2]['expected_gate_links']['gate2'].update(event_id='TECHNICAL-WRONG-GATE-EVENT',record_fingerprint='0'*64)
                    else:
                        values[2]['expected_files'][1].update(file_sha256='0'*64,byte_size=999999)
                    if candidate_reverse: values[1]=reverse_object_keys(values[1])
                    if expected_reverse: values[2]=reverse_object_keys(values[2])
                    invoke('R1-B2:'+family+':'+suffix,values,field=first_field,step=step)
        for reversed_keys in (False,True):
            values=copy.deepcopy(base);values[0].update(Z_extra=False,A_extra=False)
            if reversed_keys: values[0]=reverse_object_keys(values[0])
            invoke('R1-B2:unknown_UTF8_order:'+str(reversed_keys),values,field='submission.A_extra',step=1)
        uncertain = copy.deepcopy(base);uncertain[0].update(extra_human)
        invoke('IJ-02:human_uncertain', uncertain)
        zero_packet = json.loads(packet_raw);zero_packet['findings']=[]
        zero_packet['summary'].update(rule_counts={r:0 for r in ('R01','R02','R03','R04')},total_findings=0,r02_overpayment_total_cents=0)
        zero = make_base(zero_packet,canon(zero_packet)+b'\n',human,(ROOT/'docs/AUDIT_CONTRACT.md').read_bytes())
        invoke('IJ-03:technical_zero_not_business_recalculation',zero)
        optional = copy.deepcopy(base);optional[0].update(finding_notes=[],evidence_requests=[])
        _, empty, _ = invoke('IJ-04:explicit_empty',optional)
        e.check('IJ-04:omitted_equals_empty',canon(normal)==canon(empty))
        fid = base[1]['fact_snapshot']['finding_ids'][0]
        optional = copy.deepcopy(base);optional[0]['finding_notes']=[{'finding_id':fid,'note':human['reason']}]
        invoke('IJ-05:registered_text_as_note',optional)
        optional = copy.deepcopy(base);optional[0]['evidence_requests']=[{'finding_id':fid,'request':human['reason']},{'finding_id':None,'request':extra_human['reason']}]
        invoke('IJ-06:registered_text_as_requests',optional)
        for key in ('submission_version','event_id','batch_id','request_binding','submission_source','actor','decided_at_raw','assessment','reason'):
            bad('IJ-07:missing_'+key,lambda v,k=key:v[0].pop(k),'submission.'+key)
        for key in ('assessment','reason','event_id'):
            bad('IJ-07:blank_'+key,lambda v,k=key:v[0].__setitem__(k,' \t\n'),'submission.'+key)
        for key,value in (('reason',7),('assessment',True),('finding_notes',None),('evidence_requests',{})):
            bad('IJ-07:type_'+key,lambda v,k=key,x=value:v[0].__setitem__(k,x),'submission.'+key)
        bad('IJ-07:missing_actor_id',lambda v:v[0]['actor'].pop('actor_id'),'submission.actor.actor_id')
        for key in ('ai_suggestion','final_judgment','phase','human_initial_judgment_saved'):
            bad('IJ-08:unknown_'+key,lambda v,k=key:v[0].__setitem__(k,False),'submission.'+key)
        for value in ('AI','SYSTEM','SIMULATED_HUMAN'):
            bad('IJ-09:actor_'+value,lambda v,x=value:v[0]['actor'].__setitem__('actor_kind',x),'submission.actor.actor_kind')
        bad('IJ-09:simulated_version',lambda v:v[0].__setitem__('submission_version','TASK-016-initial-judgment-submission-1.0'),'submission.submission_version')
        for label,obj in (('construction_memo',{'D2':'scope permission only'}),('chat_tendency',{'chat':'not a submission'})):
            bad('IJ-09:'+label,lambda v,x=obj:v.__setitem__(0,x),'submission.submission_version')
        nohuman = copy.deepcopy(zero);nohuman[0].pop('reason')
        invoke('IJ-10:zero_without_reason',nohuman,field='submission.reason')
        for name,note,field in (('unknown',[{'finding_id':'TECHNICAL-UNKNOWN','note':human['reason']}],'submission.finding_notes[0].finding_id'),
            ('duplicate',[{'finding_id':fid,'note':human['reason']}]*2,'submission.finding_notes[1].finding_id'),
            ('blank',[{'finding_id':fid,'note':' '}],'submission.finding_notes[0].note')):
            bad('IJ-11:'+name,lambda v,x=note:v[0].__setitem__('finding_notes',x),field)
        for name,entries,field in (('unknown',[{'finding_id':'TECHNICAL-UNKNOWN','request':human['reason']}],'submission.evidence_requests[0].finding_id'),
            ('duplicate',[{'finding_id':None,'request':human['reason']}]*2,'submission.evidence_requests[1].request'),
            ('missing_request',[{'finding_id':None}],'submission.evidence_requests[0].request'),
            ('wrong_id_type',[{'finding_id':True,'request':human['reason']}],'submission.evidence_requests[0].finding_id')):
            bad('IJ-12:'+name,lambda v,x=entries:v[0].__setitem__('evidence_requests',x),field)
        bad('IJ-13:batch',lambda v:v[0].__setitem__('batch_id','TECHNICAL-OTHER'),'submission.batch_id')
        bad('IJ-13:request',lambda v:v[0]['request_binding'].__setitem__('request_id','TECHNICAL-OTHER'),'submission.request_binding.request_id')
        for index,path,edit in ((1,'materials.materials_fingerprint',lambda v:v[1].__setitem__('materials_fingerprint','0'*64)),
            (0,'submission.request_binding.materials_fingerprint',lambda v:v[0]['request_binding'].__setitem__('materials_fingerprint','0'*64)),
            (2,'expectations.expected_materials_fingerprint',lambda v:v[2].__setitem__('expected_materials_fingerprint','0'*64))):
            bad('IJ-14:binding_'+str(index),edit,path)
        def packet_change(v):
            p=v[1]['fact_snapshot']['packet'];p['limits'].append('TECHNICAL controlled candidate change')
            v[1]['fact_snapshot']['packet_canonical_sha256']=fp(p)
        bad('IJ-15:old_packet_expectation',packet_change,'expectations.expected_fact_binding.packet_canonical_sha256',True)
        for key in ('normalized_payload_sha256','screening_report_sha256','crosscheck_report_sha256'):
            bad('IJ-16:source_'+key,lambda v,k=key:v[1]['fact_snapshot']['source_fingerprints'].__setitem__(k,'0'*64),'materials.fact_snapshot.source_fingerprints.'+key,True)
        bad('IJ-16:finding_ids',lambda v:v[1]['fact_snapshot'].__setitem__('finding_ids',['TECHNICAL-OTHER']),'materials.fact_snapshot.finding_ids',True)
        bad('IJ-16:inspect_run',lambda v:v[1]['fact_snapshot']['inspect_binding'].__setitem__('run_binding_sha256','0'*64),'materials.fact_snapshot.inspect_binding.run_binding_sha256',True)
        packet_index=next(i for i,x in enumerate(base[1]['files']) if x['role']=='facts.packet')
        assert base[1]['files'][packet_index]['file_sha256'] != fp(base[1]['fact_snapshot']['packet'])
        bad('IJ-17:FILE_to_FP',lambda v:v[1]['files'][packet_index].__setitem__('file_sha256',v[1]['fact_snapshot']['packet_canonical_sha256']),f'materials.files[{packet_index}].file_sha256',True)
        bad('IJ-17:FP_to_FILE',lambda v:v[1]['fact_snapshot'].__setitem__('packet_canonical_sha256',v[1]['files'][packet_index]['file_sha256']),'materials.fact_snapshot.packet_canonical_sha256',True)
        bad('IJ-18:missing_role',lambda v:v[1]['files'].pop(),'materials.files')
        bad('IJ-18:duplicate_role',lambda v:v[1]['files'][1].__setitem__('role',v[1]['files'][0]['role']),'materials.files[1].role')
        bad('IJ-18:duplicate_relative',lambda v:v[1]['files'][1].__setitem__('relative',v[1]['files'][0]['relative']),'materials.files[1].relative')
        bad('IJ-18:unsafe_relative',lambda v:v[1]['files'][0].__setitem__('relative','../outside'),'materials.files[0].relative')
        for value in (0.0,False): bad('IJ-18:strict_size_'+str(value),lambda v,x=value:v[1]['files'][0].__setitem__('byte_size',x),'materials.files[0].byte_size')
        bad('IJ-18:float_total',lambda v:v[1]['fact_snapshot']['packet']['summary'].__setitem__('total_findings',1.0),'materials.fact_snapshot.packet.summary.total_findings')
        for suffix in ('\n','\r\n',' '):
            bad('IJ-19:hash_suffix_'+repr(suffix),lambda v,x=suffix:v[0]['request_binding'].__setitem__('materials_fingerprint',base[0]['request_binding']['materials_fingerprint']+x),'submission.request_binding.materials_fingerprint')
        bad('IJ-19:uppercase',lambda v:v[1]['run_binding']['code'].__setitem__('file_sha256',base[1]['run_binding']['code']['file_sha256'].upper()),'materials.run_binding.code.file_sha256')
        bad('IJ-19:truncated',lambda v:v[2].__setitem__('expected_prior_history_fingerprint',base[2]['expected_prior_history_fingerprint'][:-1]),'expectations.expected_prior_history_fingerprint')
        technical_id=copy.deepcopy(base);technical_id[0]['request_binding']['request_id']=technical_id[2]['expected_request_id']='0abc123'
        invoke('IJ-19:leading_zero_technical_request',technical_id)
        technical_id=copy.deepcopy(base);technical_id[0]['request_binding']['request_id']=technical_id[2]['expected_request_id']='a'*64
        invoke('IJ-19:hex_technical_request',technical_id)
        bad('IJ-20:not_effective',lambda v:v[1]['contract_binding'].__setitem__('contract_effective',False),'materials.contract_binding.contract_effective')
        bad('IJ-20:bool_is_integer',lambda v:v[1]['contract_binding'].__setitem__('contract_effective',1),'materials.contract_binding.contract_effective')
        bad('IJ-20:contract_sha',lambda v:v[1]['contract_binding'].__setitem__('contract_file_sha256','0'*64),'materials.contract_binding.contract_file_sha256',True)
        for role,key in (('code','file_sha256'),('code','manifest_fingerprint'),('rules','version'),('rules','manifest_fingerprint'),('config','file_sha256'),('input','file_sha256')):
            bad('IJ-21:'+role+'.'+key,lambda v,r=role,k=key:v[1]['run_binding'][r].__setitem__(k,'TECHNICAL-OTHER' if k=='version' else '0'*64),'materials.run_binding.'+role+'.'+key,True)
        bad('IJ-21:runtime_version',lambda v:v[1].__setitem__('runtime_version','TECHNICAL-OTHER'),'materials.runtime_version',True)
        bad('IJ-22:gate_string',lambda v:v[1]['gate_links'].__setitem__('gate1','APPROVE'),'materials.gate_links.gate1')
        bad('IJ-22:gate_hold',lambda v:v[1]['gate_links']['gate2'].__setitem__('decision','HOLD'),'materials.gate_links.gate2.decision')
        bad('IJ-22:wrong_prior',lambda v:v[1]['gate_links']['gate2'].__setitem__('prior_gate1_fingerprint','0'*64),'materials.gate_links.gate2.prior_gate1_fingerprint',True)
        time_only=copy.deepcopy(base);time_only[0]['decided_at_raw']=extra_human['decided_at_raw'];invoke('IJ-23:human_explicit_offset',time_only)
        for value in ('2026-02-30','2026-02-29','2026-10-15T15:20:22','2026-10-15T15:20:22Z','2026-10-15T15:20:22.1+08:00',
                      '2026-10-15T15:20:22+14:01','2026-10-15T15:20:22+15:00','2026-10-15T15:20:22+0800','2026-10-15T24:20:22+08:00',
                      '2026-10-15T15:60:22+08:00','2026-10-15T15:20:60+08:00','2026-10-16\n','0000-01-01'):
            bad('IJ-24:'+repr(value),lambda v,x=value:v[0].__setitem__('decided_at_raw',x),'submission.decided_at_raw')
        invoke('IJ-25:omitted_history',copy.deepcopy(base),omit_history=True,field='prior_history')
        bad('IJ-25:null',lambda v:v.__setitem__(3,None),'prior_history')
        for key,value in (('declared_complete',False),('declared_complete',1),('declared_scope',' '),('records',{})):
            bad('IJ-25:'+key+'_'+str(value),lambda v,k=key,x=value:v[3].__setitem__(k,x),'prior_history.'+key)
        def history_other(v):
            v[3]['records']=[{'event_id':'TECHNICAL-HISTORY-OTHER','batch_id':'TECHNICAL-OTHER-BATCH','record_fingerprint':fp({'technical':'past-record'}),'binding_fingerprint':fp({'technical':'past-binding'})}]
            v[2]['expected_prior_history_fingerprint']=fp(v[3])
        other=copy.deepcopy(base);history_other(other)
        invoke('IJ-29:technical_verified_index_not_full_record',other)
        bad('IJ-26:partial_record_not_index',lambda v:v[3].__setitem__('records',[{'event_id':'TECHNICAL-HISTORY'}]),'prior_history.records[0].batch_id')
        history_bad=copy.deepcopy(other);history_bad[3]['records'][0]['record_fingerprint']='0'*64
        invoke('IJ-26:independent_history_fp',history_bad,field='expectations.expected_prior_history_fingerprint')
        history_dup=copy.deepcopy(other);history_dup[3]['records'].append(copy.deepcopy(history_dup[3]['records'][0]))
        invoke('IJ-26:duplicate_index_id',history_dup,field='prior_history.records[1].event_id')
        scope_bad=copy.deepcopy(base);scope_bad[3]['declared_scope']='TECHNICAL-OTHER-SCOPE';scope_bad[2]['expected_prior_history_fingerprint']=fp(scope_bad[3])
        invoke('IJ-25:scope_mismatch',scope_bad,field='prior_history.declared_scope')
        event_dup=copy.deepcopy(other);event_dup[3]['records'][0]['event_id']=human['event_id'];event_dup[2]['expected_prior_history_fingerprint']=fp(event_dup[3])
        invoke('IJ-27:event_duplicate',event_dup,field='submission.event_id')
        batch_dup=copy.deepcopy(other);batch_dup[3]['records'][0]['batch_id']=base[0]['batch_id'];batch_dup[2]['expected_prior_history_fingerprint']=fp(batch_dup[3])
        invoke('IJ-27:same_batch',batch_dup,field='prior_history.records')
        old=copy.deepcopy(base);old[0]['request_binding']['materials_fingerprint']='0'*64
        invoke('IJ-28:old_binding',old,field='submission.request_binding.materials_fingerprint')
        if TEXT_SUPPLEMENT.is_file():
            free=copy.deepcopy(base);free[0]['reason']=json.loads(TEXT_SUPPLEMENT.read_bytes())['human_values']['reason']
            invoke('IJ-30:human_instruction_text_is_data',free)
        _, repeated, _=invoke('IJ-31:determinism',copy.deepcopy(base))
        keyed=copy.deepcopy(base);keyed[0]=dict(reversed(list(keyed[0].items())))
        _, rekeyed, _=invoke('IJ-31:dictionary_order',keyed)
        e.check('IJ-31:full_canonical_determinism',canon(normal)==canon(repeated)==canon(rekeyed))
        native=obs.native_returns[normal_id];inputs= e.CORE_INPUT_REFS[next(x['nested_id'] for x in e.CORE_RECORDS if x['caller_api']==normal_id)]
        before=canon(inputs);native['record']['human_initial_judgment']['actor']['actor_id']='CONTROL_RETURN_MUTATION';native['record']['binding']['files'][0]['byte_size']=999
        e.check('IJ-32:no_alias_actual_return',canon(inputs)==before,{'raw_return_used':True,'not_e_call_api_deepcopy':True})
        real, hits=core._canonical,[0]
        def controlled(value):
            if type(value) is dict and value.get('record_version')=='TASK-034-human-initial-judgment-record-1.0':
                hits[0]+=1;raise ValueError('TASK035_CONTROLLED_INTERNAL_SERIALIZATION')
            return real(value)
        core._canonical=controlled
        try: error,_,cid=invoke('IJ-33:internal_serialization_control',copy.deepcopy(base),expect_error=True)
        finally: core._canonical=real
        e.check('IJ-33:actual_error_cause',isinstance(error,core.HumanInitialJudgmentError) and error.stage=='internal' and isinstance(error.__cause__,ValueError) and error.reasons==[error.reason] and hits==[1],{'call_id':cid,'hits':hits[0]})
        invoke('IJ-34:guarded_call',copy.deepcopy(base),guarded=True)
        e.check('IJ-34:actual_core_guard_zero',not guard_log['core'],guard_log)
        e.check('IJ-32:all_consumed_refs_three_points',all(canon(x['input_refs_before'])==canon(x['input_refs_after'])==canon(x['input_refs_api_end']) for x in e.CORE_RECORDS))
        e.check('counts.original_entry_closure',obs.count==len(e.CORE_RECORDS)==sum(x.get('record_category')=='pure_core' for x in e.API_RECORDS),{'profile':obs.count,'complete_entries':len(e.CORE_RECORDS)})
        e.check('counts.ID_and_parent_closure',len({x['nested_id'] for x in e.CORE_RECORDS})==len(e.CORE_RECORDS) and all(x['caller_api'] in {a['call_id'] for a in e.API_RECORDS} for x in e.CORE_RECORDS))
        # Real accepted audit helper isolation, using a bounded subset of actual observations.
        ap=next(x for x in e.API_RECORDS if x['call_id']==normal_id)
        cr=next(x for x in e.CORE_RECORDS if x['caller_api']==normal_id)
        expected={'api_records':[copy.deepcopy(ap)],'core_records':[copy.deepcopy(cr)],'checks':[],'round':out.name}
        candidate=e.build_candidate(expected,None,{})
        for name,edit in (('original',lambda c:None),('return_type',lambda c:c['core_records'][0]['return']['record']['boundaries'].__setitem__('persisted',0)),
                           ('drop_core',lambda c:c['core_records'].clear())):
            proposed=copy.deepcopy(candidate);edit(proposed)
            helper_core_before=obs.count
            err,result,cid=e.call_api(e,'evidence_audit:'+name,e.audit_candidate,proposed,expected)
            e.API_RECORDS[-1].update(record_category='evidence_audit_helper_control',actual_core_delta=obs.count-helper_core_before)
            e.check('audit_isolation.'+name,err is None and bool(result['problems'])==(name!='original'),{'call_id':cid,'problems':result['problems'] if result else None})
    finally:
        sys.setprofile(None)
    for p in source_paths: assert sha(p.read_bytes())==sources[p.relative_to(ROOT).as_posix()]['sha256']
    missing={'IJ-23.extra_boundaries': {'count':None,'reason':'no registered positive human values for leap day or ±14:00; date-only and explicit +08:00 were executed'}}
    if not TEXT_SUPPLEMENT.is_file(): missing['IJ-30']={'count':None,'reason':'registered human texts contain no instruction/D2 sentence; no additional positive human text invented'}
    (out/'case_map.json').write_bytes(canon({'actual_calls':case_map,'reused_observation_controls':{'IJ-32.no_alias':normal_id},'not_executed':missing,'not_all_symbolic_variants_executed':True})+b'\n')
    (out/'guard_proof.json').write_bytes(canon(guard_log)+b'\n')
    return obs, {'fixture_label':'PROTOCOL_TEST_FIXTURE_ONLY','sources':sources,'technical_projections_are_actual_Gate_verification':False,
        'actual_core_original_code_entries':obs.count,'case_map':'case_map.json','not_executed':missing,
        'other_business_cores':{'count':None,'reason':'not imported or invoked; no historical suites or runtime chains'},
        'persistence':{'count':None,'reason':'out of scope; memory core only'}}

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--out-dir',required=True);parser.add_argument('--replay')
    parser.add_argument('--mutate',choices=('none','candidate-return','ledger-late','checks-late'),default='none')
    args=parser.parse_args(argv);out=Path(args.out_dir).resolve()
    if not out.is_relative_to(TEST_ROOT.resolve()) or out==TEST_ROOT.resolve() or out.exists() or not out.name.startswith('task035_'):
        raise SystemExit('out-dir must be a never-existing task035_ strict descendant')
    e=evidence_module();e.ROUND['id']=out.name;out.mkdir(parents=True,exist_ok=False)
    if args.replay:
        source=Path(args.replay).resolve()
        if not source.is_relative_to(TEST_ROOT.resolve()) or not source.name.startswith('task035_') or source==out: raise SystemExit('invalid replay source')
        checkpoint=json.loads((source/'expected_observations.json').read_bytes());obs=None
        extra={'replay_only':True,'source':str(source),'replayed_records_are_new_calls':False}
    else:
        if args.mutate!='none': raise SystemExit('mutations require replay')
        obs,extra=run(e,out);checkpoint=e.freeze_expectations()
    original_read,injection=Path.read_bytes,{'hits':0}
    if args.mutate in ('ledger-late','checks-late'):
        def read_then_mutate(path):
            returned=original_read(path);frame=sys._getframe(1)
            if frame.f_code is e.finish.__code__ and 'terminal_buffers' in frame.f_locals and path==out/'expected_observations.json' and not injection['hits']:
                target=out/('file_ledger.json' if args.mutate=='ledger-late' else 'checks.json');before=original_read(target)
                with open(target,'ab') as stream: stream.write(b'\n')
                injection.update(hits=1,target=target.name,before_size=len(before),after_size=len(before)+1,
                    before_sha256=sha(before),after_sha256=sha(before+b'\n'),boundary='after semantic audit, inside final raw-byte loop')
            return returned
        Path.read_bytes=read_then_mutate
    try: result=e.finish(out,checkpoint,'candidate-return' if args.mutate=='candidate-return' else 'none',obs,extra)
    finally: Path.read_bytes=original_read
    if args.mutate in ('ledger-late','checks-late'): (out/'control_observation.json').write_bytes(canon(injection)+b'\n')
    return result

if __name__=='__main__': raise SystemExit(main())
