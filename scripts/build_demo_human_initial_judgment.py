"""TASK-035: deterministic human-declared initial judgment validation in memory only.

No storage, runtime connection, approval, identity authentication or AI permission.
Protocol versions and schemas are the accepted TASK-034 design, not the simulator.
"""
from __future__ import annotations

import copy
from datetime import date
import hashlib
import json
import math
import re

CORE_VERSION = 'TASK-035-human-initial-judgment-core-1.1'
SUBMISSION_VERSION = 'TASK-034-human-initial-judgment-submission-1.0'
MATERIALS_VERSION = 'TASK-034-human-initial-judgment-materials-1.0'
EXPECTATIONS_VERSION = 'TASK-034-human-initial-judgment-expectations-1.0'
RECORD_VERSION = 'TASK-034-human-initial-judgment-record-1.0'
RECORD_STATUS = 'HUMAN_INITIAL_JUDGMENT_VALIDATED'
NOTE = '仅在内存校验人类明确提交及其绑定；未保存，不批准执行，不认证身份，不形成审计结论，不开放AI或终判。'
_SUBMISSION = ('submission_version', 'event_id', 'batch_id', 'request_binding',
               'submission_source', 'actor', 'decided_at_raw', 'assessment', 'reason')
_OPTIONAL = ('finding_notes', 'evidence_requests')
_MATERIALS = ('materials_version', 'batch_id', 'runtime_version', 'entity', 'contract_binding',
              'run_binding', 'fact_snapshot', 'gate_links', 'files', 'materials_fingerprint')
_EXPECTATIONS = ('expectations_version', 'expected_batch_id', 'expected_request_id',
                 'expected_materials_fingerprint', 'expected_contract', 'expected_runtime_version',
                 'expected_run_binding', 'expected_fact_binding', 'expected_gate_links',
                 'expected_files', 'expected_history_scope', 'expected_prior_history_fingerprint')
_SOURCE = ('workbook_sha256', 'normalized_payload_sha256', 'screening_report_sha256', 'crosscheck_report_sha256')
_FACT_BINDING = ('inspect_binding', 'packet_canonical_sha256', 'finding_ids', 'source_fingerprints')
_GATE = ('gate', 'batch_id', 'event_id', 'record_fingerprint', 'record_file_sha256',
         'materials_fingerprint', 'contract_binding', 'run_binding', 'decision', 'actor_kind')
_FILE_ROLES = ('facts.started', 'facts.packet', 'facts.markdown', 'facts.artifacts',
               'runtime.registry', 'contract', 'gate1.record', 'gate2.record')
_PACKET = ('packet_version', 'batch_status', 'mode', 'next_step_allowed', 'entity', 'banner',
           'bindings', 'summary', 'reconciliation', 'findings', 'amount_labels', 'limits')
_CARD = ('finding_id', 'rule_id', 'rule_name', 'rule_template', 'hit_key', 'amounts_cents',
         'amounts_display_cny', 'related_ids', 'source_rows', 'evidence', 'context', 'refund_summary')
_RULES = ('R01', 'R02', 'R03', 'R04')
_BOUNDARIES = ('persisted', 'execution_allowed', 'next_step_allowed', 'ai_enabled',
               'final_judgment_recorded', 'identity_authenticated', 'source_authenticity_proven',
               'audit_conclusion_formed')
_ENTITY = {'company': '澄明商贸有限公司', 'currency': '人民币（CNY）',
           'period': {'period_start': '2026-09-01', 'period_end': '2026-09-30'}, 'cutoff_date': '2026-09-30'}
_HEX = re.compile(r'[0-9a-f]{64}')
_TIME = re.compile(r'([0-9]{4})-([0-9]{2})-([0-9]{2})(?:T([0-9]{2}):([0-9]{2}):([0-9]{2})([+-])([0-9]{2}):([0-9]{2}))?')


class HumanInitialJudgmentBlocked(Exception):
    def __init__(self, field: str, reason: str):
        self.field, self.reason, self.reasons = field, reason, [reason]
        super().__init__(f'{field}: {reason}')


class HumanInitialJudgmentError(Exception):
    def __init__(self, stage: str, reason: str):
        self.stage, self.reason, self.reasons = stage, reason, [reason]
        super().__init__(f'[{stage}] {reason}')


def _block(field, reason):
    raise HumanInitialJudgmentBlocked(field, reason)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _fingerprint(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _object(value, field):
    if type(value) is not dict:
        _block(field, '必须为严格dict对象')
    return value


def _list(value, field):
    if type(value) is not list:
        _block(field, '必须为严格list')
    return value


def _keys(value, required, field, optional=()):
    _object(value, field)
    for key in required:
        if key not in value:
            _block(field + '.' + key, '缺少必需字段')
    if any(type(key) is not str for key in value):
        _block(field, '对象键必须是字符串')
    for key in value:
        try: key.encode('utf-8')
        except UnicodeError as exc:
            raise HumanInitialJudgmentBlocked(field, '对象键不能编码为UTF-8') from exc
    for key in sorted(value, key=lambda x: x.encode('utf-8')):
        if key not in required and key not in optional:
            _block(field + '.' + key, '未知字段')
    return value


def _text(value, field):
    if type(value) is not str or not value.strip():
        _block(field, '必须为去空白判非空的原字符串')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise HumanInitialJudgmentBlocked(field, '字符串不能编码为UTF-8') from exc
    return value


def _sha(value, field):
    if type(value) is not str or _HEX.fullmatch(value) is None:
        _block(field, '必须恰为64位小写十六进制完整字符串')


def _constant(value, expected, field):
    if type(value) is not type(expected) or value != expected:
        _block(field, f'必须为严格常量 {expected!r}')


def _integer(value, field, nonnegative=False):
    if type(value) is not int or (nonnegative and value < 0):
        _block(field, '必须为严格非负整数' if nonnegative else '必须为严格整数')


def _json(value, field, active=None):
    """Reject non-JSON values before downstream consumers; opaque business data stays opaque."""
    if value is None or type(value) in (bool, int):
        return
    if type(value) is str:
        try: value.encode('utf-8')
        except UnicodeError as exc: raise HumanInitialJudgmentBlocked(field, '字符串不能编码为UTF-8') from exc
        return
    if type(value) is float:
        if not math.isfinite(value): _block(field, 'JSON不能含NaN或Infinity')
        return
    if type(value) not in (dict, list):
        _block(field, '不是允许的JSON值类型')
    active = set() if active is None else active
    if id(value) in active: _block(field, 'JSON不能包含循环引用')
    active.add(id(value))
    try:
        if type(value) is dict:
            for key, child in value.items():
                if type(key) is not str: _block(field, '对象键必须为字符串')
                _json(key, field, active)
                _json(child, field + '.' + key, active)
        else:
            for i, child in enumerate(value): _json(child, f'{field}[{i}]', active)
    finally:
        active.remove(id(value))


def _equal(value, expected, field):
    if _canonical(value) != _canonical(expected):
        _block(field, '与本次独立预期或实际输入关系不一致')


def _match(value, expected, field):
    """Type-sensitive canonical equality with leaf diagnostics for already validated schemas."""
    if _canonical(value) == _canonical(expected): return
    if type(value) is dict and type(expected) is dict and set(value) == set(expected):
        # Only diagnostic traversal: the declared protocol orders, never either
        # caller's insertion order. This does not sort or repair input objects.
        orders = (('company', 'currency', 'period', 'cutoff_date'),
                  ('period_start', 'period_end'),
                  ('contract_version', 'contract_file_sha256', 'contract_effective'),
                  ('code', 'rules', 'config', 'input'),
                  ('file_sha256', 'manifest_fingerprint'), ('version', 'manifest_fingerprint'),
                  ('file_sha256',), _FACT_BINDING,
                  ('stage_version', 'status', 'batch_id', 'run_binding_sha256'),
                  _SOURCE, ('gate1', 'gate2'), _GATE, (*_GATE, 'prior_gate1_fingerprint'),
                  ('role', 'relative', 'file_sha256', 'byte_size'))
        keys = next((order for order in orders if set(order) == set(value)), None)
        # Opaque JSON has no declared business schema; only stable key diagnostics.
        if keys is None: keys = sorted(value, key=lambda key: key.encode('utf-8'))
        for key in keys: _match(value[key], expected[key], field + '.' + key)
    elif type(value) is list and type(expected) is list and len(value) == len(expected):
        for i, (left, right) in enumerate(zip(value, expected)): _match(left, right, f'{field}[{i}]')
    _block(field, '与本次独立预期或实际输入关系不一致')


def _entity(value, field):
    _keys(value, ('company', 'currency', 'period', 'cutoff_date'), field)
    for key in ('company', 'currency'):
        _text(value[key], field + '.' + key)
        _constant(value[key], _ENTITY[key], field + '.' + key)
    _keys(value['period'], ('period_start', 'period_end'), field + '.period')
    for key in ('period_start', 'period_end'):
        _text(value['period'][key], field + '.period.' + key)
        _constant(value['period'][key], _ENTITY['period'][key], field + '.period.' + key)
    _text(value['cutoff_date'], field + '.cutoff_date')
    _constant(value['cutoff_date'], _ENTITY['cutoff_date'], field + '.cutoff_date')
    _match(value, _ENTITY, field)


def _contract(value, field):
    _keys(value, ('contract_version', 'contract_file_sha256', 'contract_effective'), field)
    _constant(value['contract_version'], 'V1', field + '.contract_version')
    _sha(value['contract_file_sha256'], field + '.contract_file_sha256')
    _constant(value['contract_effective'], True, field + '.contract_effective')


def _run_binding(value, field):
    _keys(value, ('code', 'rules', 'config', 'input'), field)
    for role, keys in (('code', ('file_sha256', 'manifest_fingerprint')),
                       ('rules', ('version', 'manifest_fingerprint')),
                       ('config', ('file_sha256',)), ('input', ('file_sha256',))):
        _keys(value[role], keys, field + '.' + role)
        for key in keys:
            (_text if key == 'version' else _sha)(value[role][key], field + '.' + role + '.' + key)


def _ids(values, field):
    _list(values, field)
    seen = set()
    for i, value in enumerate(values):
        _text(value, f'{field}[{i}]')
        if value in seen: _block(f'{field}[{i}]', '原ID重复')
        seen.add(value)


def _fact_binding_shape(value, field, packet=False):
    _keys(value, ('inspect_binding', 'packet', 'packet_canonical_sha256', 'finding_ids', 'source_fingerprints') if packet else _FACT_BINDING, field)
    binding = _keys(value['inspect_binding'], ('stage_version', 'status', 'batch_id', 'run_binding_sha256'), field + '.inspect_binding')
    _constant(binding['stage_version'], 'TASK-033-fact-packet-1.0', field + '.inspect_binding.stage_version')
    _constant(binding['status'], 'RT_FACT_PACKET_RECORDED', field + '.inspect_binding.status')
    _text(binding['batch_id'], field + '.inspect_binding.batch_id')
    _sha(binding['run_binding_sha256'], field + '.inspect_binding.run_binding_sha256')
    if packet: _packet_shape(value['packet'], field + '.packet')
    _sha(value['packet_canonical_sha256'], field + '.packet_canonical_sha256')
    _ids(value['finding_ids'], field + '.finding_ids')
    source = _keys(value['source_fingerprints'], _SOURCE, field + '.source_fingerprints')
    for key in _SOURCE: _sha(source[key], field + '.source_fingerprints.' + key)


def _packet_shape(value, field):
    _keys(value, _PACKET, field)
    for key, expected in (('packet_version', 'TASK-008-fact-packet-1.1'), ('batch_status', 'DEV_FACT_PACKET_READY'),
                          ('mode', 'DEVELOPMENT_TEST_ONLY'), ('next_step_allowed', False)):
        _constant(value[key], expected, field + '.' + key)
    _entity(value['entity'], field + '.entity')
    bindings = _keys(value['bindings'], (*_SOURCE, 'upstream_versions', 'upstream_declared_database'), field + '.bindings')
    for key in _SOURCE: _sha(bindings[key], field + '.bindings.' + key)
    for key in ('upstream_versions', 'upstream_declared_database'): _object(bindings[key], field + '.bindings.' + key)
    summary = _keys(value['summary'], ('rule_counts', 'total_findings', 'involved_payments',
                    'r02_overpayment_total_cents', 'r02_overpayment_basis'), field + '.summary')
    _keys(summary['rule_counts'], _RULES, field + '.summary.rule_counts')
    for rule in _RULES: _integer(summary['rule_counts'][rule], field + '.summary.rule_counts.' + rule, True)
    _integer(summary['total_findings'], field + '.summary.total_findings', True)
    _integer(summary['r02_overpayment_total_cents'], field + '.summary.r02_overpayment_total_cents')
    findings = _list(value['findings'], field + '.findings')
    seen = set()
    for i, finding in enumerate(findings):
        at = f'{field}.findings[{i}]'
        _keys(finding, _CARD, at, ('missing_kind',))
        _text(finding['finding_id'], at + '.finding_id')
        _text(finding['rule_id'], at + '.rule_id')
        if finding['rule_id'] not in _RULES: _block(at + '.rule_id', '未知规则ID')
        if finding['rule_id'] == 'R03':
            if 'missing_kind' not in finding: _block(at + '.missing_kind', '缺少R03必需字段')
        elif 'missing_kind' in finding: _block(at + '.missing_kind', '非R03不能含该字段')
        if finding['finding_id'] in seen: _block(at + '.finding_id', '线索ID重复')
        seen.add(finding['finding_id'])


def _gate_links(value, field):
    _keys(value, ('gate1', 'gate2'), field)
    for role, gate in (('gate1', 'GATE1'), ('gate2', 'GATE2')):
        at = field + '.' + role
        member = _keys(value[role], (*_GATE, 'prior_gate1_fingerprint') if role == 'gate2' else _GATE, at)
        _constant(member['gate'], gate, at + '.gate')
        _text(member['batch_id'], at + '.batch_id')
        _text(member['event_id'], at + '.event_id')
        for key in ('record_fingerprint', 'record_file_sha256', 'materials_fingerprint'): _sha(member[key], at + '.' + key)
        _contract(member['contract_binding'], at + '.contract_binding')
        _run_binding(member['run_binding'], at + '.run_binding')
        _constant(member['decision'], 'APPROVE', at + '.decision')
        _constant(member['actor_kind'], 'HUMAN_DECLARED', at + '.actor_kind')
        if role == 'gate2': _sha(member['prior_gate1_fingerprint'], at + '.prior_gate1_fingerprint')


def _files(value, field):
    _list(value, field)
    roles, relatives, previous = set(), set(), None
    for i, item in enumerate(value):
        at = f'{field}[{i}]'
        _keys(item, ('role', 'relative', 'file_sha256', 'byte_size'), at)
        _text(item['role'], at + '.role')
        if item['role'] not in _FILE_ROLES: _block(at + '.role', '未知材料角色')
        if item['role'] in roles: _block(at + '.role', '材料角色重复')
        roles.add(item['role'])
        relative = _text(item['relative'], at + '.relative')
        if relative.startswith('/') or '\\' in relative or ':' in relative or any(p in ('', '.', '..') for p in relative.split('/')):
            _block(at + '.relative', '必须为不规范化的安全项目相对POSIX路径')
        encoded = relative.encode('utf-8')
        if relative in relatives or (previous is not None and encoded <= previous):
            _block(at + '.relative', '相对路径必须唯一且按UTF-8字节严格升序')
        relatives.add(relative)
        previous = encoded
        _sha(item['file_sha256'], at + '.file_sha256')
        _integer(item['byte_size'], at + '.byte_size', True)
    if roles != set(_FILE_ROLES): _block(field, '必须完整包含八个固定材料角色')


def _submission(value):
    field = 'submission'
    _keys(value, _SUBMISSION, field, _OPTIONAL)
    _constant(value['submission_version'], SUBMISSION_VERSION, field + '.submission_version')
    for key in ('event_id', 'batch_id'): _text(value[key], field + '.' + key)
    request = _keys(value['request_binding'], ('request_id', 'materials_fingerprint'), field + '.request_binding')
    _text(request['request_id'], field + '.request_binding.request_id')
    _sha(request['materials_fingerprint'], field + '.request_binding.materials_fingerprint')
    _constant(value['submission_source'], 'HUMAN_INITIAL_JUDGMENT', field + '.submission_source')
    actor = _keys(value['actor'], ('actor_kind', 'actor_id', 'declaration_note'), field + '.actor')
    _constant(actor['actor_kind'], 'HUMAN_DECLARED', field + '.actor.actor_kind')
    for key in ('actor_id', 'declaration_note'): _text(actor[key], field + '.actor.' + key)
    for key in ('decided_at_raw', 'assessment', 'reason'): _text(value[key], field + '.' + key)
    for role, text_key in (('finding_notes', 'note'), ('evidence_requests', 'request')):
        entries = _list(value[role], field + '.' + role) if role in value else []
        seen = set()
        for i, item in enumerate(entries):
            at = f'{field}.{role}[{i}]'
            _keys(item, ('finding_id', text_key), at)
            if role == 'finding_notes' or item['finding_id'] is not None: _text(item['finding_id'], at + '.finding_id')
            _text(item[text_key], at + '.' + text_key)
            token = item['finding_id'] if role == 'finding_notes' else _canonical([item['finding_id'], item[text_key]])
            if token in seen: _block(at + ('.finding_id' if role == 'finding_notes' else '.request'), '可选成员重复')
            seen.add(token)
    _json(value, field)


def _materials(value):
    field = 'materials'
    _keys(value, _MATERIALS, field)
    _constant(value['materials_version'], MATERIALS_VERSION, field + '.materials_version')
    for key in ('batch_id', 'runtime_version'): _text(value[key], field + '.' + key)
    _entity(value['entity'], field + '.entity')
    _contract(value['contract_binding'], field + '.contract_binding')
    _run_binding(value['run_binding'], field + '.run_binding')
    _fact_binding_shape(value['fact_snapshot'], field + '.fact_snapshot', packet=True)
    _gate_links(value['gate_links'], field + '.gate_links')
    _files(value['files'], field + '.files')
    _sha(value['materials_fingerprint'], field + '.materials_fingerprint')
    _json(value, field)


def _expectations(value):
    field = 'expectations'
    _keys(value, _EXPECTATIONS, field)
    _constant(value['expectations_version'], EXPECTATIONS_VERSION, field + '.expectations_version')
    for key in ('expected_batch_id', 'expected_request_id'): _text(value[key], field + '.' + key)
    _sha(value['expected_materials_fingerprint'], field + '.expected_materials_fingerprint')
    _contract(value['expected_contract'], field + '.expected_contract')
    _text(value['expected_runtime_version'], field + '.expected_runtime_version')
    _run_binding(value['expected_run_binding'], field + '.expected_run_binding')
    _fact_binding_shape(value['expected_fact_binding'], field + '.expected_fact_binding')
    _gate_links(value['expected_gate_links'], field + '.expected_gate_links')
    _files(value['expected_files'], field + '.expected_files')
    _text(value['expected_history_scope'], field + '.expected_history_scope')
    _sha(value['expected_prior_history_fingerprint'], field + '.expected_prior_history_fingerprint')
    _json(value, field)


def _history(value):
    field = 'prior_history'
    if value is None: _block(field, '历史完整性声明缺失；不能默认空历史')
    _keys(value, ('declared_complete', 'declared_scope', 'records'), field)
    _constant(value['declared_complete'], True, field + '.declared_complete')
    _text(value['declared_scope'], field + '.declared_scope')
    previous = None
    for i, item in enumerate(_list(value['records'], field + '.records')):
        at = f'{field}.records[{i}]'
        _keys(item, ('event_id', 'batch_id', 'record_fingerprint', 'binding_fingerprint'), at)
        _text(item['event_id'], at + '.event_id')
        _text(item['batch_id'], at + '.batch_id')
        for key in ('record_fingerprint', 'binding_fingerprint'): _sha(item[key], at + '.' + key)
        current = item['event_id'].encode('utf-8')
        if previous is not None and current <= previous: _block(at + '.event_id', '历史事件ID必须唯一且按UTF-8字节严格升序')
        previous = current
    _json(value, field)


def _time(value):
    field = 'submission.decided_at_raw'
    match = _TIME.fullmatch(value)
    if match is None: _block(field, '只允许日期或带明确偏移的秒精度时间原文')
    year, month, day, hour, minute, second, _, offset_hour, offset_minute = match.groups()
    try: date(int(year), int(month), int(day))
    except ValueError as exc: raise HumanInitialJudgmentBlocked(field, '不是合法公历日期') from exc
    if hour is not None:
        if int(hour) > 23 or int(minute) > 59 or int(second) > 59: _block(field, '时间分量越界（不接受闰秒）')
        oh, om = int(offset_hour), int(offset_minute)
        if oh > 14 or om > 59 or (oh == 14 and om != 0): _block(field, '偏移超出±14:00范围')


def _binding_relations(submission, materials, expectations):
    _time(submission['decided_at_raw'])
    _equal(submission['batch_id'], materials['batch_id'], 'submission.batch_id')
    _equal(materials['batch_id'], expectations['expected_batch_id'], 'materials.batch_id')
    _equal(submission['request_binding']['request_id'], expectations['expected_request_id'], 'submission.request_binding.request_id')
    _equal(materials['runtime_version'], expectations['expected_runtime_version'], 'materials.runtime_version')
    _match(materials['contract_binding'], expectations['expected_contract'], 'materials.contract_binding')
    _match(materials['run_binding'], expectations['expected_run_binding'], 'materials.run_binding')


def _materials_digest(submission, materials, expectations):
    digest = _fingerprint({key: value for key, value in materials.items() if key != 'materials_fingerprint'})
    _equal(materials['materials_fingerprint'], digest, 'materials.materials_fingerprint')
    _equal(submission['request_binding']['materials_fingerprint'], digest, 'submission.request_binding.materials_fingerprint')
    _equal(expectations['expected_materials_fingerprint'], digest, 'expectations.expected_materials_fingerprint')


def _file_relations(materials, expectations):
    _match(materials['files'], expectations['expected_files'], 'materials.files')
    for i, item in enumerate(materials['files']):
        if item['role'] == 'contract': expected = materials['contract_binding']['contract_file_sha256']
        elif item['role'] in ('gate1.record', 'gate2.record'):
            expected = materials['gate_links'][item['role'].split('.')[0]]['record_file_sha256']
        else: continue
        _equal(item['file_sha256'], expected, f'materials.files[{i}].file_sha256')


def _fact_gate_relations(materials, expectations):
    fact = materials['fact_snapshot']
    field = 'materials.fact_snapshot'
    packet = fact['packet']
    _equal(fact['packet_canonical_sha256'], _fingerprint(packet), field + '.packet_canonical_sha256')
    _equal(expectations['expected_fact_binding']['packet_canonical_sha256'], fact['packet_canonical_sha256'],
           'expectations.expected_fact_binding.packet_canonical_sha256')
    findings = packet['findings']
    _equal(fact['finding_ids'], [item['finding_id'] for item in findings], field + '.finding_ids')
    for rule in _RULES:
        _equal(packet['summary']['rule_counts'][rule], sum(item['rule_id'] == rule for item in findings), field + '.packet.summary.rule_counts.' + rule)
    _equal(packet['summary']['total_findings'], len(findings), field + '.packet.summary.total_findings')
    for key in _SOURCE: _equal(fact['source_fingerprints'][key], packet['bindings'][key], field + '.source_fingerprints.' + key)
    _equal(fact['source_fingerprints']['workbook_sha256'], materials['run_binding']['input']['file_sha256'], field + '.source_fingerprints.workbook_sha256')
    _equal(fact['inspect_binding']['batch_id'], materials['batch_id'], field + '.inspect_binding.batch_id')
    _equal(fact['inspect_binding']['run_binding_sha256'], _fingerprint(materials['run_binding']), field + '.inspect_binding.run_binding_sha256')
    projection = {key: fact[key] for key in _FACT_BINDING}
    _match(projection, expectations['expected_fact_binding'], field)
    for role in ('gate1', 'gate2'):
        gate, at = materials['gate_links'][role], 'materials.gate_links.' + role
        _equal(gate['batch_id'], materials['batch_id'], at + '.batch_id')
        _match(gate['contract_binding'], materials['contract_binding'], at + '.contract_binding')
        _match(gate['run_binding'], materials['run_binding'], at + '.run_binding')
    _equal(materials['gate_links']['gate2']['prior_gate1_fingerprint'], materials['gate_links']['gate1']['record_fingerprint'],
           'materials.gate_links.gate2.prior_gate1_fingerprint')
    _match(materials['gate_links'], expectations['expected_gate_links'], 'materials.gate_links')


def _optional_relations(submission, materials):
    ids = set(materials['fact_snapshot']['finding_ids'])
    for role in _OPTIONAL:
        for i, entry in enumerate(submission.get(role, [])):
            if entry['finding_id'] is not None and entry['finding_id'] not in ids:
                _block(f'submission.{role}[{i}].finding_id', '必须引用当前事实包原finding_id')


def _history_relations(submission, expectations, prior_history):
    _equal(prior_history['declared_scope'], expectations['expected_history_scope'], 'prior_history.declared_scope')
    _equal(expectations['expected_prior_history_fingerprint'], _fingerprint(prior_history), 'expectations.expected_prior_history_fingerprint')
    if any(item['event_id'] == submission['event_id'] for item in prior_history['records']): _block('submission.event_id', '声明范围内事件ID已存在')
    if any(item['batch_id'] == submission['batch_id'] for item in prior_history['records']): _block('prior_history.records', '首版不接受同批第二个初判或覆盖修订')


def build_human_initial_judgment_record(submission: dict, materials: dict,
                                       expectations: dict, *, prior_history: dict | None = None) -> dict:
    """Validate only supplied objects/independent expectations; never read or persist a record."""
    try:
        # Protocol steps 1--4: strict schemas before any relationship consumer.
        _submission(submission)
        _materials(materials)
        _expectations(expectations)
        _history(prior_history)
        inputs = (submission, materials, expectations, prior_history)
        before = copy.deepcopy(inputs)
        # Steps 5--10. No expectation is refreshed from a candidate.
        _binding_relations(submission, materials, expectations)
        _materials_digest(submission, materials, expectations)
        _file_relations(materials, expectations)
        _fact_gate_relations(materials, expectations)
        _optional_relations(submission, materials)
        _history_relations(submission, expectations, prior_history)
        human = copy.deepcopy(submission)
        for key in _OPTIONAL:
            if key not in human: human[key] = []
        record = copy.deepcopy({
            'record_version': RECORD_VERSION, 'record_status': RECORD_STATUS, 'mode': 'LOCAL_DECLARED_SYNTHETIC',
            'binding': {'batch_id': materials['batch_id'], 'request_id': submission['request_binding']['request_id'],
                'materials_fingerprint': materials['materials_fingerprint'], 'runtime_version': materials['runtime_version'],
                'entity': materials['entity'], 'contract_binding': materials['contract_binding'], 'run_binding': materials['run_binding'],
                'fact_binding': {key: materials['fact_snapshot'][key] for key in _FACT_BINDING},
                'gate_links': materials['gate_links'], 'files': materials['files']},
            'human_initial_judgment': human, 'decided_at_source': 'HUMAN_PROVIDED_RAW',
            'history_binding': {'declared_scope': prior_history['declared_scope'], 'prior_history_fingerprint': _fingerprint(prior_history)},
            'boundaries': {key: False for key in _BOUNDARIES}, 'note': NOTE})
        for value, snapshot, field in zip(inputs, before, ('submission', 'materials', 'expectations', 'prior_history')):
            _equal(value, snapshot, field)
        return {'record': record, 'record_fingerprint': _fingerprint(record)}
    except HumanInitialJudgmentBlocked:
        raise
    except HumanInitialJudgmentError:
        raise
    except Exception as exc:
        raise HumanInitialJudgmentError('internal', f'{type(exc).__name__}: {exc}') from exc
