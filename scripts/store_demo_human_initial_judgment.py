"""TASK-036: exclusive snapshots and read-only verification; STORED_SNAPSHOTS_ONLY.

Does not inspect business material paths, enumerate history, authenticate people,
connect a workflow, save an actual batch judgment or enable AI. No production CLI.
"""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

STORE_VERSION = 'TASK-036-human-initial-judgment-store-1.1'
MANIFEST_VERSION = 'TASK-036-human-initial-judgment-store-manifest-1.0'
FAILURE_VERSION = 'TASK-036-human-initial-judgment-store-failure-1.0'
SCOPE = 'STORED_SNAPSHOTS_ONLY'
STORED = 'HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_STORED'
VERIFIED = 'HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_VERIFIED'
ROOT = Path(__file__).absolute().parents[1]
RECORDS_ROOT = ROOT / 'data/human_initial_judgment_records'
COMPONENT_PATHS = {
    'core_file_sha256': ROOT / 'scripts/build_demo_human_initial_judgment.py',
    'store_file_sha256': Path(__file__).absolute(),
    'protocol_file_sha256': ROOT / 'docs/proposals/HUMAN_INITIAL_JUDGMENT_PROTOCOL_V1_DRAFT.md',
    'cases_file_sha256': ROOT / 'docs/proposals/HUMAN_INITIAL_JUDGMENT_CASES_V1_DRAFT.md',
    'contract_file_sha256': ROOT / 'docs/AUDIT_CONTRACT.md',
    'contract_effective_record_file_sha256': ROOT / 'docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md'}
FROZEN = {
    'core_file_sha256': '312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35',
    'protocol_file_sha256': 'df5dace5f8ec2dfca820f9c74db6f5fa1d3a947005610ad72b8e8d59d1c38cfe',
    'cases_file_sha256': 'e02e1f49e16ebff6a3b683e4c76ece6dd81697569e4876d090a4cccb67d07d46',
    'contract_file_sha256': '174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad',
    'contract_effective_record_file_sha256': '042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d'}
PAYLOADS = ('expectations.json', 'judgment_result.json', 'materials.json', 'prior_history.json', 'submission.json')
FILES = tuple(sorted((*PAYLOADS, 'manifest.json')))
MANIFEST_KEYS = ('manifest_version', 'store_status', 'scope', 'identity', 'component_bindings',
                 'fingerprints', 'payloads', 'technical_registration', 'boundaries')
IDENTITY_KEYS = ('batch_id', 'event_id', 'request_id')
FINGERPRINT_KEYS = ('submission_fingerprint', 'materials_snapshot_fingerprint', 'materials_body_fingerprint',
                    'expectations_fingerprint', 'prior_history_fingerprint', 'record_fingerprint', 'binding_fingerprint')
ENTRY_KEYS = ('relative', 'byte_size', 'file_sha256', 'object_fingerprint')
BOUNDARIES = ('workflow_connected', 'execution_allowed', 'next_step_allowed', 'ai_enabled',
              'identity_authenticated', 'source_authenticity_proven', 'audit_conclusion_formed',
              'final_judgment_recorded', 'complete_history_verified')
FAILURE_KEYS = ('failure_version', 'scope', 'identity', 'stage', 'classification', 'field',
                'reason', 'exception_type', 'cause_chain', 'technical_registration')
_HEX = re.compile(r'[0-9a-f]{64}')
_UTC = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+00:00')


class HumanInitialJudgmentStoreBlocked(Exception):
    def __init__(self, field, reason):
        self.field, self.reason, self.reasons = field, reason, [reason]
        super().__init__(f'{field}: {reason}')


class HumanInitialJudgmentStoreError(Exception):
    def __init__(self, stage, reason):
        self.stage, self.reason, self.reasons = stage, reason, [reason]
        super().__init__(f'[{stage}] {reason}')


def _block(field, reason):
    raise HumanInitialJudgmentStoreBlocked(field, reason)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _sha(raw): return hashlib.sha256(raw).hexdigest()
def _fp(value): return _sha(_canonical(value))
def _buffer(value): return _canonical(value) + b'\n'


def _keys(value, keys, field):
    if type(value) is not dict: _block(field, '必须为严格对象')
    for key in keys:
        if key not in value: _block(field + '.' + key, '缺少必需字段')
    for key in value:
        if type(key) is not str: _block(field, '对象键必须为字符串')
    for key in sorted(value):
        if key not in keys: _block(field + '.' + key, '未知字段')


def _text(value, field):
    if type(value) is not str or not value.strip(): _block(field, '必须为非空原字符串')
    try: value.encode('utf-8')
    except UnicodeError as exc: raise HumanInitialJudgmentStoreBlocked(field, '不是合法UTF-8字符串') from exc


def _constant(value, expected, field):
    if type(value) is not type(expected) or value != expected: _block(field, '严格常量不符')


def _hex(value, field):
    if type(value) is not str or _HEX.fullmatch(value) is None: _block(field, '必须完整64位小写十六进制')


def _json_value(value, field):
    if value is None or type(value) in (bool, int): return
    if type(value) is str:  # Empty strings can be legitimate opaque data.
        try: value.encode('utf-8')
        except UnicodeError as exc: raise HumanInitialJudgmentStoreBlocked(field, '不是合法UTF-8字符串') from exc
        return
    if type(value) is float:
        if value != value or value in (float('inf'), float('-inf')): _block(field, 'JSON不能含NaN或Infinity')
        return
    if type(value) is list:
        for i, item in enumerate(value): _json_value(item, f'{field}[{i}]')
    elif type(value) is dict:
        for key, item in value.items():
            if type(key) is not str: _block(field, '对象键必须为字符串')
            _json_value(key, field); _json_value(item, field + '.' + key)
    else: _block(field, '不是JSON类型')


def _equal(value, expected, field):
    _json_value(value, field)
    if _canonical(value) != _canonical(expected): _block(field, '与独立绑定对象不一致')


def _lstat(path, stage):
    try: return path.lstat()
    except OSError as exc: raise HumanInitialJudgmentStoreError(stage, f'{path.name}: {exc}') from exc


def _reject_chain(path, field):
    node = Path(path.anchor)
    for part in path.parts[1:]:
        node /= part
        try: info = node.lstat()
        except FileNotFoundError: continue
        except OSError as exc: raise HumanInitialJudgmentStoreError('path', str(exc)) from exc
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            _block(field, '原始路径链含链接或reparse点')


def _resolve_leaf(raw, must_exist):
    field = 'record_dir' if must_exist else 'out_dir'
    if not isinstance(raw, (str, os.PathLike)): _block(field, '必须显式提供路径')
    try:
        value = os.fspath(raw)
        if type(value) is not str or not value.strip() or '\x00' in value: _block(field, '路径字符串非法')
        candidate = Path(value)
        # Only obtain the drive's current directory for a drive-relative path.
        # Joining preserves the caller's alias/.. segments until lstat sees them.
        base = Path(os.path.abspath(candidate.drive + '.')) if candidate.drive and not candidate.root else Path.cwd()
        absolute = base / candidate
        _reject_chain(absolute, field)
        resolved, root = absolute.resolve(), RECORDS_ROOT.resolve()
    except (OSError, ValueError) as exc: raise HumanInitialJudgmentStoreError('path', str(exc)) from exc
    if resolved == root or not resolved.is_relative_to(root): _block(field, '必须为记录根严格后代')
    _reject_chain(resolved, field)
    try: info = resolved.lstat()
    except FileNotFoundError:
        if must_exist: _block(field, '记录目录不存在')
        return resolved
    except OSError as exc: raise HumanInitialJudgmentStoreError('path', str(exc)) from exc
    if not must_exist: _block(field, '目标已存在，含空目录；不得覆盖')
    if not stat.S_ISDIR(info.st_mode): _block(field, '必须为正常目录')
    return resolved


def _normal_file(path):
    _reject_chain(path, path.name)
    info = _lstat(path, 'stat')
    if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        _block(path.name, '必须为无reparse的正常文件')


def _read_bytes(path, stage='read'):
    try: return path.read_bytes()
    except OSError as exc: raise HumanInitialJudgmentStoreError(stage, f'{path.name}: {exc}') from exc


def _parse(raw, field):
    try: value = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError) as exc: raise HumanInitialJudgmentStoreBlocked(field, '不是合法UTF-8 JSON') from exc
    _json_value(value, field)
    if _buffer(value) != raw: _block(field, '必须为规范JSON加恰一个LF、无BOM')
    return value


def _layout(target):
    _reject_chain(target, 'record_dir')
    try: return sorted(p.name for p in target.iterdir())
    except OSError as exc: raise HumanInitialJudgmentStoreError('enumerate', str(exc)) from exc


def _capture_components():
    captures = {}
    for key, path in COMPONENT_PATHS.items():
        _normal_file(path)
        raw = _read_bytes(path, 'bindings')
        if key in FROZEN and _sha(raw) != FROZEN[key]: _block('component_bindings.' + key, '冻结组件身份不符')
        captures[key] = {'path': path, 'bytes': raw}
    return captures


def _confirm_components(captures):
    for key, value in captures.items():
        _normal_file(value['path'])
        if _read_bytes(value['path'], 'final_read') != value['bytes']:
            _block('component_bindings.' + key, '组件字节较操作开始发生变化')


def _load_core(captures):
    module = types.ModuleType('_task036_frozen_initial_judgment_core')
    module.__file__ = str(captures['core_file_sha256']['path'])
    try: exec(compile(captures['core_file_sha256']['bytes'], module.__file__, 'exec'), module.__dict__)
    except (OSError, ImportError) as exc: raise HumanInitialJudgmentStoreError('core_load', str(exc)) from exc
    return module


def _invoke_core(module, snapshots):
    try:
        return module.build_human_initial_judgment_record(snapshots['submission'], snapshots['materials'],
            snapshots['expectations'], prior_history=snapshots['prior_history'])
    except module.HumanInitialJudgmentBlocked as exc:
        raise HumanInitialJudgmentStoreBlocked(exc.field, exc.reason) from exc
    except module.HumanInitialJudgmentError as exc:
        raise HumanInitialJudgmentStoreError(exc.stage, exc.reason) from exc


def _validate_result(result):
    _keys(result, ('record', 'record_fingerprint'), 'judgment_result')
    record = result['record']
    _keys(record, ('record_version', 'record_status', 'mode', 'binding', 'human_initial_judgment',
                   'decided_at_source', 'history_binding', 'boundaries', 'note'), 'judgment_result.record')
    _keys(record['binding'], ('batch_id', 'request_id', 'materials_fingerprint', 'runtime_version', 'entity',
        'contract_binding', 'run_binding', 'fact_binding', 'gate_links', 'files'), 'judgment_result.record.binding')
    _keys(record['human_initial_judgment'], ('submission_version', 'event_id', 'batch_id', 'request_binding',
        'submission_source', 'actor', 'decided_at_raw', 'assessment', 'reason', 'finding_notes', 'evidence_requests'),
        'judgment_result.record.human_initial_judgment')
    _hex(result['record_fingerprint'], 'judgment_result.record_fingerprint')
    _equal(result['record_fingerprint'], _fp(record), 'judgment_result.record_fingerprint')
    return record


def _identity(snapshots, result):
    record = _validate_result(result)
    identity = {'batch_id': record['binding']['batch_id'], 'event_id': record['human_initial_judgment']['event_id'],
                'request_id': record['binding']['request_id']}
    for key in IDENTITY_KEYS: _text(identity[key], 'identity.' + key)
    # Full input/result equality is independently checked against the real core;
    # these projections close the manifest identity rather than infer it from paths.
    for role in ('submission', 'materials', 'expectations', 'prior_history'):
        if type(snapshots[role]) is not dict: _block(role, '必须为对象快照')
    submission = snapshots['submission']
    for key in ('batch_id', 'event_id', 'request_binding'):
        if key not in submission: _block('submission.' + key, '缺少必需字段')
    _keys(submission['request_binding'], ('request_id', 'materials_fingerprint'), 'submission.request_binding')
    _equal(submission['batch_id'], identity['batch_id'], 'identity.batch_id')
    _equal(submission['event_id'], identity['event_id'], 'identity.event_id')
    _equal(submission['request_binding']['request_id'], identity['request_id'], 'identity.request_id')
    return identity


def _fingerprints(snapshots, result):
    s, m, e, h = (snapshots[k] for k in ('submission', 'materials', 'expectations', 'prior_history'))
    if type(m) is not dict: _block('materials', '必须为对象快照')
    return {'submission_fingerprint': _fp(s), 'materials_snapshot_fingerprint': _fp(m),
        'materials_body_fingerprint': _fp({k: v for k, v in m.items() if k != 'materials_fingerprint'}),
        'expectations_fingerprint': _fp(e), 'prior_history_fingerprint': _fp(h),
        'record_fingerprint': _fp(result['record']), 'binding_fingerprint': _fp(result['record']['binding'])}


def _registration():
    return {'registered_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat(), 'source': 'PROGRAM_GENERATED_TECHNICAL'}


def _validate_registration(value, field):
    _keys(value, ('registered_at_utc', 'source'), field)
    _constant(value['source'], 'PROGRAM_GENERATED_TECHNICAL', field + '.source')
    raw = value['registered_at_utc']
    if type(raw) is not str or _UTC.fullmatch(raw) is None: _block(field + '.registered_at_utc', '必须为UTC秒精度技术时间')
    try: datetime.fromisoformat(raw)
    except ValueError as exc: raise HumanInitialJudgmentStoreBlocked(field + '.registered_at_utc', '非法公历时间') from exc


def _entry(name, raw, obj):
    return {'relative': name, 'byte_size': len(raw), 'file_sha256': _sha(raw), 'object_fingerprint': _fp(obj)}


def _build_return(status, manifest, buffers, objects):
    return copy.deepcopy({'status': status, 'scope': SCOPE, 'identity': manifest['identity'],
        'record_fingerprint': manifest['fingerprints']['record_fingerprint'], 'manifest_file_sha256': _sha(buffers['manifest.json']),
        'technical_registration': manifest['technical_registration'], 'component_bindings': manifest['component_bindings'],
        'files': [_entry(name, buffers[name], objects[name]) for name in FILES], 'boundaries': manifest['boundaries'],
        'snapshots': {name: objects[name + '.json'] for name in ('submission', 'materials', 'expectations', 'prior_history')},
        'judgment_result': objects['judgment_result.json']})


def _input_confirm(values, before):
    for name, value in values.items(): _equal(value, before[name], 'inputs.' + name)


def _write_exclusive(path, buffer):
    try:
        with path.open('xb') as stream: stream.write(buffer)
    except OSError as exc: raise HumanInitialJudgmentStoreError('write.' + path.name, str(exc)) from exc


def _terminal_confirm(target, buffers, captures):
    _confirm_components(captures)
    if _layout(target) != list(FILES): _block('files', '必须恰为六文件且无failure/子目录/未知项')
    for name in FILES:
        _normal_file(target / name)
        if _read_bytes(target / name, 'final_read') != buffers[name]: _block(name, '末次实读与本次起始/待写字节不一致')
    if _layout(target) != list(FILES): _block('files', '末次目录集合发生变化')


def _chain(exc):
    result, seen = [], set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc)); result.append({'exception_type': type(exc).__name__, 'message': str(exc)})
        exc = exc.__cause__ or exc.__context__
    return result


def _write_failure(leaf, identity, stage, exc):
    try:
        failure = {'failure_version': FAILURE_VERSION, 'scope': SCOPE, 'identity': identity, 'stage': getattr(exc, 'stage', stage),
            'classification': 'BLOCKED' if isinstance(exc, HumanInitialJudgmentStoreBlocked) else 'ERROR',
            'field': getattr(exc, 'field', None), 'reason': exc.reason, 'exception_type': type(exc).__name__,
            'cause_chain': _chain(exc), 'technical_registration': _registration()}
        _write_exclusive(leaf / 'failure.json', _buffer(failure))
    except Exception as secondary:
        try: details = _chain(secondary)
        except Exception:
            # The diagnostic chain helper itself may be the failed operation.
            details = [{'exception_type': type(secondary).__name__, 'message': repr(secondary.args)}]
        exc.secondary_errors = details
        exc.args = (*exc.args, {'failure_diagnostic_secondary': details})


def _validate_failure(value):
    _keys(value, FAILURE_KEYS, 'failure.json')
    _constant(value['failure_version'], FAILURE_VERSION, 'failure.json.failure_version')
    _constant(value['scope'], SCOPE, 'failure.json.scope')
    _keys(value['identity'], IDENTITY_KEYS, 'failure.json.identity')
    for key in IDENTITY_KEYS: _text(value['identity'][key], 'failure.json.identity.' + key)
    for key in ('stage', 'reason', 'exception_type'): _text(value[key], 'failure.json.' + key)
    if type(value['classification']) is not str or value['classification'] not in ('BLOCKED', 'ERROR'):
        _block('failure.json.classification', '非法失败分类')
    if value['classification'] == 'BLOCKED': _text(value['field'], 'failure.json.field')
    elif value['field'] is not None: _block('failure.json.field', 'ERROR必须为null')
    if type(value['cause_chain']) is not list or not value['cause_chain']: _block('failure.json.cause_chain', '必须为非空实际异常列表')
    for i, item in enumerate(value['cause_chain']):
        field = f'failure.json.cause_chain[{i}]'
        _keys(item, ('exception_type', 'message'), field)
        _text(item['exception_type'], field + '.exception_type')
        if type(item['message']) is not str: _block(field + '.message', '必须为原字符串')
    _equal(value['cause_chain'][0]['exception_type'], value['exception_type'], 'failure.json.cause_chain[0].exception_type')
    _validate_registration(value['technical_registration'], 'failure.json.technical_registration')


def _validate_manifest(value):
    _keys(value, MANIFEST_KEYS, 'manifest')
    for key, constant in (('manifest_version', MANIFEST_VERSION), ('store_status', STORED), ('scope', SCOPE)):
        _constant(value[key], constant, 'manifest.' + key)
    _keys(value['identity'], IDENTITY_KEYS, 'manifest.identity')
    for key in IDENTITY_KEYS: _text(value['identity'][key], 'manifest.identity.' + key)
    _keys(value['component_bindings'], tuple(COMPONENT_PATHS), 'manifest.component_bindings')
    for key in COMPONENT_PATHS: _hex(value['component_bindings'][key], 'manifest.component_bindings.' + key)
    _keys(value['fingerprints'], FINGERPRINT_KEYS, 'manifest.fingerprints')
    for key in FINGERPRINT_KEYS: _hex(value['fingerprints'][key], 'manifest.fingerprints.' + key)
    _keys(value['boundaries'], BOUNDARIES, 'manifest.boundaries')
    for key in BOUNDARIES: _constant(value['boundaries'][key], False, 'manifest.boundaries.' + key)
    _validate_registration(value['technical_registration'], 'manifest.technical_registration')
    if type(value['payloads']) is not list or len(value['payloads']) != 5: _block('manifest.payloads', '必须完整五项')
    for i, (item, name) in enumerate(zip(value['payloads'], PAYLOADS)):
        field = f'manifest.payloads[{i}]'
        _keys(item, ENTRY_KEYS, field); _constant(item['relative'], name, field + '.relative')
        if type(item['byte_size']) is not int or item['byte_size'] < 0: _block(field + '.byte_size', '必须严格非负整数')
        for key in ('file_sha256', 'object_fingerprint'): _hex(item[key], field + '.' + key)


def save_human_initial_judgment_snapshots(submission: dict, materials: dict, expectations: dict,
                                        *, prior_history: dict | None = None, out_dir) -> dict:
    leaf, identity, stage = None, None, 'path'
    try:
        target = _resolve_leaf(out_dir, False)
        captures = _capture_components()
        original = {'submission': submission, 'materials': materials, 'expectations': expectations, 'prior_history': prior_history}
        stage = 'snapshot'; before = copy.deepcopy(original); snapshots = copy.deepcopy(original)
        stage = 'core_load'; core = _load_core(captures)
        _confirm_components(captures)  # after loading, before the one real call
        stage = 'core_call'; result = _invoke_core(core, snapshots)
        _input_confirm(snapshots, before); _input_confirm(original, before)
        identity = _identity(snapshots, result)
        _equal(snapshots['materials']['contract_binding']['contract_file_sha256'],
               FROZEN['contract_file_sha256'], 'materials.contract_binding.contract_file_sha256')
        stage = 'buffer'
        objects = {name + '.json': value for name, value in snapshots.items()}
        objects['judgment_result.json'] = result
        buffers = {name: _buffer(objects[name]) for name in PAYLOADS}
        bindings = {key: _sha(value['bytes']) for key, value in captures.items()}
        manifest = {'manifest_version': MANIFEST_VERSION, 'store_status': STORED, 'scope': SCOPE, 'identity': identity,
            'component_bindings': bindings, 'fingerprints': _fingerprints(snapshots, result),
            'payloads': [_entry(name, buffers[name], objects[name]) for name in PAYLOADS],
            'technical_registration': _registration(), 'boundaries': {key: False for key in BOUNDARIES}}
        objects['manifest.json'] = manifest; buffers['manifest.json'] = _buffer(manifest)
        stage = 'mkdir'; _reject_chain(target, 'out_dir'); target.parent.mkdir(parents=True, exist_ok=True)
        try: os.mkdir(target)
        except FileExistsError as exc: raise HumanInitialJudgmentStoreBlocked('out_dir', '独占目录已被占用') from exc
        leaf = target
        for name in (*PAYLOADS, 'manifest.json'):
            stage = 'write.' + name; _write_exclusive(leaf / name, buffers[name])
            _normal_file(leaf / name)
            actual = _read_bytes(leaf / name, 'readback')
            if actual != buffers[name]: _block(name, '读回与本次writer缓冲不一致')
            _equal(_parse(actual, name), objects[name], name)
        stage = 'final_confirmation'; returned = _build_return(STORED, manifest, buffers, objects)
        _input_confirm(snapshots, before); _input_confirm(original, before)
        _terminal_confirm(target, buffers, captures)
        return returned
    except (HumanInitialJudgmentStoreBlocked, HumanInitialJudgmentStoreError) as exc:
        if leaf is not None: _write_failure(leaf, identity, stage, exc)
        raise
    except Exception as cause:
        error = HumanInitialJudgmentStoreError(stage, f'{type(cause).__name__}: {cause}'); error.__cause__ = cause
        if leaf is not None: _write_failure(leaf, identity, stage, error)
        raise error from cause


def verify_human_initial_judgment_snapshots(record_dir) -> dict:
    stage = 'path'
    try:
        target = _resolve_leaf(record_dir, True)
        names = _layout(target)
        if 'failure.json' in names:
            _normal_file(target / 'failure.json')
            _validate_failure(_parse(_read_bytes(target / 'failure.json'), 'failure.json'))
            _block('failure.json', '有效失败事实优先，拒绝成功恢复')
        if names != list(FILES): _block('files', '必须恰六文件，无子目录或未知项')
        captures = _capture_components()
        buffers, objects = {}, {}
        for name in FILES:
            _normal_file(target / name); buffers[name] = _read_bytes(target / name)
            objects[name] = _parse(buffers[name], name)
        manifest = objects['manifest.json']; _validate_manifest(manifest)
        snapshots = {name: objects[name + '.json'] for name in ('submission', 'materials', 'expectations', 'prior_history')}
        judgment = objects['judgment_result.json']; identity = _identity(snapshots, judgment)
        _equal(identity, manifest['identity'], 'manifest.identity')
        _equal(_fingerprints(snapshots, judgment), manifest['fingerprints'], 'manifest.fingerprints')
        for i, item in enumerate(manifest['payloads']):
            name = item['relative']; _equal(_entry(name, buffers[name], objects[name]), item, f'manifest.payloads[{i}]')
        _equal({key: _sha(value['bytes']) for key, value in captures.items()}, manifest['component_bindings'], 'manifest.component_bindings')
        stage = 'core_load'; core = _load_core(captures)
        before = copy.deepcopy(snapshots); _confirm_components(captures)
        stage = 'core_call'; actual = _invoke_core(core, snapshots)
        _input_confirm(snapshots, before); _equal(actual, judgment, 'judgment_result')
        _equal(snapshots['materials']['contract_binding']['contract_file_sha256'], FROZEN['contract_file_sha256'],
               'materials.contract_binding.contract_file_sha256')
        stage = 'final_confirmation'; returned = _build_return(VERIFIED, manifest, buffers, objects)
        _input_confirm(snapshots, before)
        _terminal_confirm(target, buffers, captures)
        return returned
    except (HumanInitialJudgmentStoreBlocked, HumanInitialJudgmentStoreError): raise
    except Exception as cause:
        raise HumanInitialJudgmentStoreError(stage, f'{type(cause).__name__}: {cause}') from cause
