"""TASK-039 finite text/JSON/AST checks. Never imports or calls business code."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / 'data/runtime_initial_judgment_recording_protocol_checks'
PROTOCOL = 'docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_PROTOCOL_V1_DRAFT.md'
CASES = 'docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_CASES_V1_DRAFT.md'
CHECKER = 'tests/check_runtime_initial_judgment_recording_protocol.py'
RECEIPT = 'docs/EXEC_REPORT_039_R1.md'
TASK = 'docs/tasks/TASK-039-R1_DRAFT.md'
BASE = 'data/reviews/task038_gpt_20261017_003401/source_hashes_after.json'
REVIEW_RESULT = 'data/reviews/task038_gpt_20261017_003401/review_result.json'
REVIEW = 'docs/reviews/REVIEW_TASK_038.md'
R1_RESULT = 'data/reviews/task039_gpt_20261017_015556/review_result.json'
OBSERVED = 'data/reviews/task039_gpt_20261017_015556/source_hashes_observed.json'
OBSERVED_SHA = 'b0d9c2f41129266033f84abb83dd4803efdf8e8e43b0ebace9f230ae5f0f3f81'
OLD_PROTOCOL = 'docs/proposals/HUMAN_INITIAL_JUDGMENT_PROTOCOL_V1_DRAFT.md'
CORE = 'scripts/build_demo_human_initial_judgment.py'
STORE = 'scripts/store_demo_human_initial_judgment.py'
HISTORY = 'scripts/inspect_demo_human_initial_judgment_history.py'
RUNTIME = 'scripts/runtime_gate1.py'
BASE_SHA = 'e841d1caa03c0445246db76148551175cfa7ea2522fe21d1c5dd954d4d40dcb9'
FROZEN = {
    RUNTIME: 'ca1139abbe18fc9cd2f1c3ad893f42b8b1b5b5bce28d1ed1216c0434309b6b9a',
    CORE: '312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35',
    STORE: 'a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c',
    HISTORY: '7276ddb704d27cec031ca3c2af4122a3c2c890d613bd4cfa90e6454d72000b22',
    'docs/AUDIT_CONTRACT.md': '174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad',
    'docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md': '042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d',
    OLD_PROTOCOL: 'df5dace5f8ec2dfca820f9c74db6f5fa1d3a947005610ad72b8e8d59d1c38cfe',
    'data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json': '81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560',
    'data/reviews/task036r1_gpt_20261016_193749/human_history_fixture_supplement.json': 'e7bb88137e11e4db2b24aeaa05a4a488084f7d57fd424f25c2166de17696868a',
}
SCHEMA_COUNTS = {
    'success': 12, 'identity': 3, 'started': 7, 'source_binding': 7,
    'registry_binding': 5, 'initial_judgment_history': 2,
    'contract_effective_record': 3, 'pre_history_binding': 3, 'context': 10,
    'receipt': 8, 'file_descriptor': 4, 'envelope_binding': 2, 'lock': 5,
    'failure': 11, 'chain_item': 2, 'boundaries': 9, 'snapshot_files': 6,
    'envelope_files': 3, 'submission_required': 9, 'submission_optional': 2,
    'history_expectations': 4, 'prior_history': 3, 'history_index': 4,
    'store_return': 11, 'history_return': 12,
}
SYMBOLS = ['H_EVENT', 'H_ACTOR', 'H_DECLARATION', 'H_TIME', 'H_ASSESSMENT', 'H_REASON']
NOT_EXECUTED = {
    name: {'count': None, 'reason': '文档/有限静态范围，未来接口尚未实现；未运行'}
    for name in ('runtime_save', 'runtime_verify', 'concurrency', 'physical_handle',
                 'history_inspect', 'store_save', 'store_verify', 'initial_core',
                 'Gate_business', 'normalization_SQL_recalculation_facts_build',
                 'real_data', 'identity_authentication', 'AI_final_judgment')
}


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def machine(text, marker):
    start, end = '<!-- ' + marker + '_BEGIN -->', '<!-- ' + marker + '_END -->'
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(marker + ': expected one block')
    block = text.split(start, 1)[1].split(end, 1)[0].strip()
    if not block.startswith('```json') or not block.endswith('```'):
        raise ValueError(marker + ': expected JSON fence')
    return json.loads(block[7:-3], object_pairs_hook=no_duplicate_keys)


def assignment(tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('AST literal assignment absent: ' + name)


def return_keys(tree, name):
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
    for ret in ast.walk(node):
        if isinstance(ret, ast.Return):
            for value in ast.walk(ret.value):
                if isinstance(value, ast.Dict) and all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in value.keys):
                    return [k.value for k in value.keys]
    raise ValueError('AST closed return dict absent: ' + name)


def formula(expression, **values):
    """Only integer literals, n/m, + and *; no eval/exec or imported functions."""
    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult)):
            left, right = walk(node.left), walk(node.right)
            return left + right if isinstance(node.op, ast.Add) else left * right
        raise ValueError('unsupported call formula: ' + expression)
    return walk(ast.parse(expression, mode='eval').body)


def expected_digest_roles():
    """Finite field contracts, independent of the candidate metadata/suffixes."""
    fp = {
        'source_binding.registry_binding.run_binding_sha256': 'registry.run_binding',
        'context.prepared_request.request_sha256': 'context.prepared_request.request',
        'materials.materials_fingerprint': 'materials minus top-level materials_fingerprint',
        'materials.fact_snapshot.packet_canonical_sha256': 'materials.fact_snapshot.packet',
        'materials.fact_snapshot.source_fingerprints.normalized_payload_sha256': 'bound normalized object',
        'materials.fact_snapshot.source_fingerprints.screening_report_sha256': 'bound screening_report object',
        'materials.fact_snapshot.source_fingerprints.crosscheck_report_sha256': 'bound crosscheck_report object',
        'store.fingerprints.submission_fingerprint': 'received submission snapshot',
        'store.fingerprints.materials_snapshot_fingerprint': 'complete materials snapshot',
        'store.fingerprints.materials_body_fingerprint': 'materials minus top-level materials_fingerprint',
        'store.fingerprints.expectations_fingerprint': 'independent expectations snapshot',
        'store.fingerprints.prior_history_fingerprint': 'saved prior_history P0',
        'store.fingerprints.record_fingerprint': 'judgment_result.record',
        'store.fingerprints.binding_fingerprint': 'judgment_result.record.binding',
        'pre_history_binding.prior_history_fingerprint': 'saved prior_history P0',
        'history_verification.prior_history_fingerprint': 'that verification.prior_history',
        'history_verification.inventory_fingerprint': 'that verification.inventory',
        'receipt.post_history_fingerprint': 'saved H1.prior_history',
        'success.record_fingerprint': 'target judgment_result.record',
        'file_descriptor.object_fingerprint': 'object parsed from the same described file buffer',
    }
    files = {
        'source_binding.registry_binding.registry_file_sha256': 'runtime_registry.json exact bytes',
        'materials.fact_snapshot.source_fingerprints.workbook_sha256': 'bound source/input.xlsx exact bytes',
        'success.manifest_file_sha256': 'target manifest.json exact bytes',
        'receipt.snapshot_manifest_file_sha256': 'target manifest.json exact bytes',
        'receipt.started_file_sha256': 'this started.json writer buffer',
        'receipt.context_file_sha256': 'this context.json writer buffer',
        'file_descriptor.file_sha256': 'the described JSON file exact bytes',
    }
    return {**{key: {'role': 'FP', 'basis': value} for key, value in fp.items()},
            **{key: {'role': 'FILE', 'basis': value} for key, value in files.items()}}


def audit_digest_roles(candidate, expected):
    problems = []
    if type(candidate) is not dict:
        return {'ok': False, 'problems': [{'field': 'digest_roles', 'reason': 'must be object'}]}
    for key in sorted(set(candidate) | set(expected)):
        if key not in expected or key not in candidate:
            problems.append({'field': 'digest_roles.' + key, 'reason': 'unknown or missing field contract'})
        elif canon(candidate[key]) != canon(expected[key]):
            problems.append({'field': 'digest_roles.' + key, 'expected': expected[key], 'candidate': candidate[key]})
    return {'ok': not problems, 'problems': problems}


def ast_fingerprint_assignment(tree, function, field, expression):
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    hits = []
    for value in ast.walk(node):
        if isinstance(value, ast.Dict):
            for key, item in zip(value.keys, value.values):
                if isinstance(key, ast.Constant) and key.value == field and isinstance(item, ast.Call):
                    if isinstance(item.func, ast.Name) and item.func.id in ('fingerprint', '_fp'):
                        hits.append({'line': item.lineno, 'expression': ast.unparse(item)})
    return {'ok': any(row['expression'] == expression for row in hits), 'hits': hits}


def run_checks(require_receipt, role_control=False):
    checks, references, buffers = [], {}, {}

    def read(relative):
        raw = (ROOT / relative).read_bytes()
        references[relative] = {'relative': relative, 'byte_size': len(raw), 'file_sha256': sha(raw),
                                'source': 'actual_same_buffer_read'}
        buffers[relative] = raw
        return raw

    def check(name, ok, evidence):
        checks.append({'id': f'ST-{len(checks)+1:02d}', 'name': name,
                       'passed': bool(ok), 'evidence': evidence, 'scope': 'STATIC_ONLY'})

    baseline_raw = read(BASE)
    baseline = json.loads(baseline_raw)
    check('accepted snapshot identity/count', sha(baseline_raw) == BASE_SHA and len(baseline) == 168728,
          {'sha256': sha(baseline_raw), 'entries': len(baseline)})
    accepted = json.loads(read(REVIEW_RESULT))
    read(REVIEW)
    check('TASK038 accepted precondition', accepted['verdict'] == 'ACCEPTED', accepted['verdict'])
    r1_result = json.loads(read(R1_RESULT))
    check('R1 NOT_ACCEPTED+B1 repair precondition', r1_result['verdict'] == 'NOT_ACCEPTED' and
          [row['id'] for row in r1_result['semantic_blockers']] == ['B1'], r1_result['semantic_blockers'])
    observed_raw = read(OBSERVED)
    check('NOT_ACCEPTED observed snapshot, not acceptance', sha(observed_raw) == OBSERVED_SHA == r1_result['observed_baseline_sha256'] and
          len(json.loads(observed_raw)) == 168771 == r1_result['observed_baseline_entries'] and
          r1_result['observed_snapshot_is_accepted_baseline'] is False, {'sha256': sha(observed_raw), 'entries': 168771})
    task_raw = read(TASK)
    check('TASK039-R1 task identity', sha(task_raw) == '38acd35bb1b5836a1be065fe676d69310b64c757797232e797af9c389d4b7b52' == r1_result['next_task_sha256'], sha(task_raw))
    for relative, expected in FROZEN.items():
        raw = read(relative)
        check('frozen identity: ' + relative, sha(raw) == expected == baseline[relative], references[relative])
    old_cases = 'docs/proposals/HUMAN_INITIAL_JUDGMENT_CASES_V1_DRAFT.md'
    check('frozen original cases baseline identity', sha(read(old_cases)) == baseline[old_cases], references[old_cases])
    authorization = 'data/reviews/task038_authorization_20261016/final_chain_authorization.json'
    check('038 extra-chain authorization source identity', sha(read(authorization)) == baseline[authorization], references[authorization])
    protocol_text = read(PROTOCOL).decode('utf-8')
    cases_text = read(CASES).decode('utf-8')
    schema = machine(protocol_text, 'TASK039_SCHEMA')
    design_cases = machine(cases_text, 'TASK039_CASES')
    check('design metadata revision 1.1 only', schema['design_version'] == design_cases['design_version'] == 'TASK-039-recording-design-1.1', schema['design_version'])
    observed = json.loads(observed_raw)
    backup_root = 'data/runtime_initial_judgment_recording_protocol_checks/task039_r1_prepare_01/'
    old_protocol_raw = read(backup_root + 'source_1_before.bin')
    old_cases_raw = read(backup_root + 'source_2_before.bin')
    before_schema = machine(old_protocol_raw.decode('utf-8'), 'TASK039_SCHEMA')
    before_cases = machine(old_cases_raw.decode('utf-8'), 'TASK039_CASES')
    comparable_schema = {k: v for k, v in schema.items() if k not in ('digest_roles', 'digest_role_contract')}
    comparable_schema['design_version'] = before_schema['design_version']
    check('all preexisting business shapes/constants/formulas unchanged',
          sha(old_protocol_raw) == observed[PROTOCOL] and canon(comparable_schema) == canon(before_schema),
          {'source': backup_root + 'source_1_before.bin', 'only_design_metadata_changed': True})
    prefix = json.loads(canon(design_cases['cases'][:43]))
    prefix[1]['prior_satisfied'] = before_cases['cases'][1]['prior_satisfied']
    check('original 43 cases preserved except C1 exact field clarification',
          sha(old_cases_raw) == observed[CASES] and canon(prefix) == canon(before_cases['cases']),
          {'source': backup_root + 'source_2_before.bin', 'C1_field_only': True, 'new_case': 'RC-44'})
    old_schema = machine(buffers[OLD_PROTOCOL].decode('utf-8'), 'TASK034_SCHEMA')
    check('draft labels and no implemented claim',
          'RUNTIME_INITIAL_JUDGMENT_RECORDING_DESIGN_NOT_IMPLEMENTED' in protocol_text and
          'RUNTIME_INITIAL_JUDGMENT_RECORDING_CASES_NOT_EXECUTED' in cases_text,
          {'protocol': 'NOT_IMPLEMENTED', 'cases': 'NOT_EXECUTED'})
    for name, count in SCHEMA_COUNTS.items():
        keys = schema[name]
        check('closed ordered keys: ' + name,
              type(keys) is list and len(keys) == count == len(set(keys)) and all(type(k) is str for k in keys), keys)
    constants = {'stage_version': 'TASK-039-runtime-human-initial-judgment-1.0',
                 'save_status': 'RT_HUMAN_INITIAL_JUDGMENT_RECORDED',
                 'verify_status': 'RT_HUMAN_INITIAL_JUDGMENT_VERIFIED',
                 'scope': 'RUNTIME_CURRENT_MATERIALS_AND_DECLARED_HISTORY_ONLY'}
    check('case/protocol constants exact', canon(design_cases['constants']) == canon(constants) and
          all(schema[k] == v for k, v in constants.items()) and design_cases['design_version'] == schema['design_version'], constants)
    check('case schema references complete', design_cases['schema_uses'] == list(SCHEMA_COUNTS), design_cases['schema_uses'])
    for key, old_key in [('submission_required', 'submission_required'), ('submission_optional', 'submission_optional'),
                         ('prior_history', 'prior_history'), ('history_index', 'history_entry')]:
        check('frozen TASK034 ordered schema: ' + key, schema[key] == old_schema[old_key], schema[key])
    trees = {name: ast.parse(buffers[name].decode('utf-8-sig')) for name in (CORE, STORE, HISTORY, RUNTIME)}
    role_sources = []
    for source, field, obj, value_key in [
            ('data/runtime/task038_review_003401/normal/runtime_registry.json',
             'source_binding.registry_binding.run_binding_sha256', 'run_binding', 'run_binding_sha256'),
            ('data/reviews/task038_gpt_20261017_003401/fixed_empty_request.json',
             'context.prepared_request.request_sha256', 'request', 'request_sha256')]:
        raw = read(source)
        parsed = json.loads(raw)
        fp, file_sha, plus_lf = sha(canon(parsed[obj])), sha(raw), sha(canon(parsed[obj]) + b'\n')
        proof = {'field': field, 'source': source, 'source_file_sha256': file_sha,
                 'byte_size': len(raw), 'observed_value': parsed[value_key],
                 'independent_object_FP': fp, 'containing_file_FILE': file_sha,
                 'canonical_object_plus_LF_sha256': plus_lf, 'same_buffer': True,
                 'source_kind': 'ACCEPTED_TASK038_READ_ONLY_NOT_RERUN'}
        role_sources.append(proof)
        check('independent accepted source FP role: ' + field,
              file_sha == baseline[source] and parsed[value_key] == fp and fp != file_sha and fp != plus_lf, proof)
    ast_roles = {}
    for function, field, expr in [
            ('build_runtime_registry', 'run_binding_sha256', 'fingerprint(binding)'),
            ('prepare_runtime_initial_judgment_request', 'request_sha256', 'fingerprint(request)'),
            ('prepare_runtime_initial_judgment_request', 'packet_canonical_sha256', 'fingerprint(packet)'),
            ('_validate_fact_packet_033', 'normalized_payload_sha256', 'fingerprint(normalized)'),
            ('_validate_fact_packet_033', 'screening_report_sha256', 'fingerprint(screen)'),
            ('_validate_fact_packet_033', 'crosscheck_report_sha256', 'fingerprint(cross)')]:
        proof = ast_fingerprint_assignment(trees[RUNTIME], function, field, expr)
        ast_roles[field] = proof
        check('frozen AST field role: ' + field, proof['ok'], proof)
    expected_roles = expected_digest_roles()
    candidate_roles = json.loads(canon(schema['digest_roles']))
    if role_control:
        # Pure-memory candidate-only mutation. Never changes docs/expected/source buffers.
        candidate_roles['source_binding.registry_binding.run_binding_sha256']['role'] = 'FILE'
    role_audit = audit_digest_roles(candidate_roles, expected_roles)
    check('finite explicit field/source digest role audit', role_audit['ok'], role_audit)
    invalid_roles = json.loads(canon(expected_roles))
    invalid_roles['source_binding.registry_binding.run_binding_sha256']['role'] = 'FILE'
    isolated = audit_digest_roles(invalid_roles, expected_roles)
    check('same role auditor rejects in-memory suffix confusion',
          audit_digest_roles(expected_roles, expected_roles)['ok'] and not isolated['ok'] and
          isolated['problems'][0]['field'] == 'digest_roles.source_binding.registry_binding.run_binding_sha256', isolated)
    check('no suffix-based classification contract', schema['digest_role_contract'] == 'EXPLICIT_FIELD_SOURCE_NOT_SUFFIX' and
          '不能根据后缀猜测角色' in protocol_text and '及所有`*_fingerprint`/`*_sha256`分别' not in protocol_text,
          schema['digest_role_contract'])
    for name, key in [('_SUBMISSION', 'submission_required'), ('_OPTIONAL', 'submission_optional')]:
        check('real core AST: ' + name, list(assignment(trees[CORE], name)) == schema[key], list(assignment(trees[CORE], name)))
    for name, key in [('_MATERIALS', 'materials'), ('_EXPECTATIONS', 'expectations'), ('_BOUNDARIES', 'boundaries')]:
        check('real core unchanged TASK034 shape: ' + name,
              list(assignment(trees[CORE], name)) == old_schema[key], list(assignment(trees[CORE], name)))
    check('six frozen leaf files', sorted([*assignment(trees[STORE], 'PAYLOADS'), 'manifest.json']) == schema['snapshot_files'], schema['snapshot_files'])
    check('frozen store full eleven-key return', return_keys(trees[STORE], '_build_return') == schema['store_return'], return_keys(trees[STORE], '_build_return'))
    check('history/store return identity', list(assignment(trees[HISTORY], 'VERIFICATION_KEYS')) == schema['store_return'], schema['store_return'])
    check('frozen history full twelve-key return', return_keys(trees[HISTORY], '_build_return') == schema['history_return'], return_keys(trees[HISTORY], '_build_return'))
    check('frozen history expectations/index', list(assignment(trees[HISTORY], 'EXPECTED_KEYS')) == schema['history_expectations'] and
          list(assignment(trees[HISTORY], 'INDEX_KEYS')) == schema['history_index'], schema['history_expectations'])
    check('store statuses fully named', all(assignment(trees[STORE], name) in protocol_text for name in ('STORED', 'VERIFIED')),
          {name: assignment(trees[STORE], name) for name in ('STORED', 'VERIFIED')})
    code_blocks = re.findall(r'```python\s*(.*?)```', protocol_text, re.S)
    future = ast.parse('\n'.join(code_blocks))
    future_names = ['save_runtime_initial_judgment', 'verify_runtime_initial_judgment']
    check('only two future definitions', [n.name for n in future.body if isinstance(n, ast.FunctionDef)] == future_names, future_names)
    for node, label in zip(future.body, ('save', 'verify')):
        a = node.args
        observed = {'positional': [x.arg for x in a.args], 'keyword_only': [x.arg for x in a.kwonlyargs]}
        check('future exact signature: ' + label, observed['positional'] == schema[label + '_positional'] and
              observed['keyword_only'] == schema[label + '_keyword_only'] and not a.vararg and not a.kwarg and
              not a.posonlyargs and not a.defaults and all(x is None for x in a.kw_defaults), observed)
    existing_names = {n.name for n in trees[RUNTIME].body if isinstance(n, ast.FunctionDef)}
    check('future functions absent current implementation', not (set(future_names) & existing_names), sorted(set(future_names) & existing_names))
    check('fixed save/verify order', schema['save_order'] == [f'S{i}' for i in range(1, 10)] and
          schema['verify_order'] == [f'V{i}' for i in range(1, 9)] and
          all('**' + s + ' ' in protocol_text for s in schema['save_order'] + schema['verify_order']),
          {'save': schema['save_order'], 'verify': schema['verify_order']})
    counts = []
    for n in (0, 2):
        observed = {key: formula(value, n=n) for key, value in schema['save_calls'].items()}
        expected = {'public_prepare': 1, 'history_total': 2, 'initial_store_save': 1,
                    'initial_store_verify': 2*n+1, 'initial_core_construct': 1,
                    'initial_core_verify': 2*n+1, 'initial_core_total': 2*n+2, 'direct_initial_core': 0}
        counts.append({'kind': 'save_design', 'n': n, 'predicted': observed})
        check('save graph formula n=' + str(n), observed == expected, counts[-1])
    for m in (1, 3):
        observed = {key: formula(value, m=m) for key, value in schema['verify_calls'].items()}
        expected = {'public_prepare': 0, 'history_total': 1, 'initial_store_save': 0,
                    'initial_store_verify': m, 'initial_core_total': m, 'direct_initial_core': 0}
        counts.append({'kind': 'verify_design', 'm': m, 'predicted': observed})
        check('verify graph formula m=' + str(m), observed == expected, counts[-1])
    graph = {'gate1_verify': 6, 'gate2_verify': 5, 'load_inspect': 5, 'screen_inspect': 2,
             'crosscheck_inspect': 1, 'fact_inspect': 1, 'fact_render': 1,
             'gate_store_verify': 11, 'gate_core': 11, 'frozen_prepare': 6}
    check('accepted038 read-only dependency graph preserved', schema['gate_fact_calls'] == graph, graph)
    graph_source = 'data/runtime_initial_judgment_request_tests/task038_run_03/normal_call_graph.json'
    graph_raw = read(graph_source)
    earlier = json.loads(graph_raw)['predicted']
    names = {'gate1_verify': 'runtime.verify_gate1_effective_approval',
             'gate2_verify': 'runtime.verify_runtime_gate2_decision',
             'load_inspect': 'runtime.inspect_gate1_approved_load',
             'screen_inspect': 'runtime.inspect_gate2_approved_screen',
             'crosscheck_inspect': 'runtime.inspect_gate2_rule_crosscheck',
             'fact_inspect': 'runtime.inspect_gate2_fact_packet', 'fact_render': 'facts.render',
             'gate_store_verify': 'gate.store.verify', 'gate_core': 'gate.core',
             'frozen_prepare': 'source.prepare'}
    check('038 graph cross-reference is frozen source, not new execution',
          sha(graph_raw) == baseline[graph_source] and {k: earlier[v] for k, v in names.items()} == graph,
          {'relative': graph_source, 'source': 'READ_OLD_EVIDENCE_NOT_RERUN'})
    check('FILE/FP and strict type rules explicit', all(s in protocol_text for s in (
          'FILE(b)=SHA-256(确切原字节)', 'FP(x)=SHA-256(C(x))', 'False/0及0/0.0不同', 'type(x) is int', '本次待写缓冲')),
          {'FILE': 'exact_bytes', 'FP': 'canonical_object', 'no_candidate_expectation_refresh': True})
    rows = design_cases['cases']
    check('44 unique continuous cases', [r['id'] for r in rows] == [f'RC-{i:02d}' for i in range(1, 45)], [r['id'] for r in rows])
    row_keys = ['id', 'family', 'prior_satisfied', 'basis', 'change', 'expected', 'writes', 'calls']
    check('each symbolic case has eight complete fields', all(list(r) == row_keys and all(type(v) is str and bool(v.strip()) for v in r.values()) for r in rows), row_keys)
    required_families = ['正常首版', '零线索', '暂不能判断', '同域两个并发保存', '不同运行共用域', '真实独占半写',
                         '诊断故障不盖主异常', '保存后只加自身', '未声明新增叶', '最后必要消费后变化']
    check('distinct mandatory problem families', all(any(r['family'] == family for r in rows) for family in required_families), required_families)
    checks_by_case = {row['id']: row for row in rows}
    role_case = design_cases['digest_role_case']
    check('RC44 bound to exact role fields', role_case['case_id'] == 'RC-44' and
          role_case['role_contract'] == schema['digest_role_contract'] and
          role_case['fields'] == ['source_binding.registry_binding.run_binding_sha256', 'context.prepared_request.request_sha256', 'receipt.context_file_sha256'] and
          all(field in checks_by_case['RC-44']['change'] and field in expected_roles for field in role_case['fields']), role_case)
    check('C1 real zero-findings paths', 'materials.fact_snapshot.finding_ids' in checks_by_case['RC-02']['prior_satisfied'] and
          'packet.findings' in checks_by_case['RC-02']['prior_satisfied'] and 'packet.finding_ids' not in cases_text,
          checks_by_case['RC-02']['prior_satisfied'])
    coverage = {
        'old_prior_immutable': (protocol_text, '旧P0和旧expectations绝不改成H1'),
        'no_self_subtraction': (protocol_text, 'P0不是Hc减自身'),
        'current_full_namespace': (protocol_text, '真实history.inspect一次，Hc完整十二键'),
        'private_branch_not_public_skip': (protocol_text, '没有skip/ignore/force/allow_existing'),
        'later_other_batch': (protocol_text, '其他批次后来合法新记录'),
        'independent_post_inventory': (checks_by_case['RC-27']['basis'], 'E0+本次S已核验manifest FILE'),
        'real_partial_writer': (checks_by_case['RC-22']['change'], '句柄写半份后OSError'),
        'receipt_sentinel': (checks_by_case['RC-25']['expected'], 'Error write.receipt'),
        'all_final_consumption': (protocol_text, '全部必要消费/解析/FP/返回构造之后'),
        'no_cross_root_atomicity_claim': (protocol_text, '两个输出根不原子'),
        'failure_preserves_primary': (protocol_text, '不顶替主异常、stage或field'),
        'outer_failure_dominates': (protocol_text, '任一FAIL不得被外层全局旧PASS或默认0覆盖'),
        'lock_handle_identity': (protocol_text, '不得关闭后仅凭路径unlink'),
        'lock_failure_preserved': (protocol_text, '失败不设置删除标记'),
        'fixed_context_layout': (protocol_text, '历史叶不放context/receipt/锁/日志'),
    }
    for name, (text, anchor) in coverage.items():
        check('explicit design obligation: ' + name, anchor in text, anchor)
    check('only registered human symbols', schema['human_symbols'] == SYMBOLS == design_cases['human_symbols'] and
          set(re.findall(r'\bH_[A-Z_]+\b', protocol_text + cases_text)) == set(SYMBOLS), SYMBOLS)
    check('cases contain no positive human submission object', not any('submission' in r and isinstance(r['submission'], dict) for r in rows) and
          not any(k in design_cases for k in ('submission', 'actor', 'assessment', 'reason', 'decided_at_raw')),
          'symbolic conditions only; no populated human payload')
    check('dynamic activity explicitly null', design_cases['dynamic_execution']['count'] is None and
          type(design_cases['dynamic_execution']['reason']) is str, design_cases['dynamic_execution'])
    check('eight core permissions unchanged/nine runtime permissions false by specification',
          len(old_schema['boundaries']) == 8 and len(schema['boundaries']) == 9 and
          '九键全false' in protocol_text and '不能把persisted改true' in protocol_text,
          {'frozen_core': old_schema['boundaries'], 'runtime': schema['boundaries']})
    own_raw = read(CHECKER)
    own_ast = ast.parse(own_raw.decode('utf-8'))
    imports = sorted({node.module.split('.')[0] if isinstance(node, ast.ImportFrom) else alias.name.split('.')[0]
                      for node in ast.walk(own_ast) if isinstance(node, (ast.Import, ast.ImportFrom))
                      for alias in (node.names if isinstance(node, ast.Import) else [None])})
    called_names = {n.func.id for n in ast.walk(own_ast) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    check('static checker imports only stdlib and never loads business', set(imports) <= {'__future__', 'argparse', 'ast', 'hashlib', 'json', 'pathlib', 're', 'sys'} and
          not (called_names & {'exec', 'eval', 'compile', '__import__'}), {'imports': imports, 'business_imports': []})
    if require_receipt:
        read(RECEIPT)
    failures = [row for row in checks if not row['passed']]
    return {'checks': checks, 'digest_role_evidence': {'independent_same_buffer_sources': role_sources,
            'frozen_AST': ast_roles, 'candidate_role_audit': role_audit,
            'in_memory_isolation': isolated, 'expected_roles_source': 'frozen_field_contracts_and_independent_accepted_buffers'},
            'schema_comparison': {'design_schema': schema, 'frozen_TASK034_schema': old_schema,
            'symbolic_case_index': rows, 'predicted_graph_examples_not_executed': counts},
            'reference_registry': {'scope': 'FINITE_FILE_READS_ONLY', 'files': list(references.values())},
            'delivery_identities': {'scope': 'STATIC_DELIVERY', 'files': [references[f] for f in (PROTOCOL, CASES, CHECKER, RECEIPT) if f in references]},
            'summary': {'task': 'TASK-039-R1', 'status': 'FAIL' if failures else 'PASS', 'scope': 'STATIC_ONLY',
                        'checks_total': len(checks), 'checks_failed': len(failures), 'failures': failures,
                        'business_dynamic_execution': NOT_EXECUTED,
                        'limitation': '有限文本/JSON/AST/SHA一致性；不证明未来代码/并发/句柄/保存恢复行为',
                        'protection_scan': {'count': None, 'reason': '静态检查不扫描项目树；交付定稿后另行唯一最终扫描'}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='finite local checks, no artifacts written')
    parser.add_argument('--out-dir')
    parser.add_argument('--role-control', action='store_true', help='pure-memory candidate role mismatch; same auditor controls exit')
    args = parser.parse_args()
    if args.check_only == bool(args.out_dir):
        parser.error('choose --check-only or --out-dir')
    scripts_root = str((ROOT / 'scripts').resolve()).casefold().replace('\\', '/') + '/'
    scripts_entries = []
    def profile(frame, event, arg):
        if event == 'call' and frame.f_code.co_filename.casefold().replace('\\', '/').startswith(scripts_root):
            scripts_entries.append({'file': frame.f_code.co_filename, 'function': frame.f_code.co_name,
                                    'code_identity': id(frame.f_code)})
    before_modules = set(sys.modules)
    previous_profile = sys.getprofile()
    sys.setprofile(profile)
    try:
        result = run_checks(require_receipt=not args.check_only, role_control=args.role_control)
    finally:
        sys.setprofile(previous_profile)
    business_imports = []
    for name in sorted(set(sys.modules) - before_modules):
        filename = getattr(sys.modules[name], '__file__', '')
        if type(filename) is str and filename.casefold().replace('\\', '/').startswith(scripts_root):
            business_imports.append({'module': name, 'file': filename})
    proof = {'source': 'actual_sys_setprofile_call_frames_and_new_sys_modules',
             'scripts_code_entries': scripts_entries, 'scripts_code_entry_count': len(scripts_entries),
             'business_imports': business_imports, 'business_import_count': len(business_imports),
             'future_dynamic_operations': NOT_EXECUTED}
    result['static_execution_observation'] = proof
    result['checks'].append({'id': f'ST-{len(result["checks"])+1:02d}', 'name': 'actual static window has no business entry/import',
                             'passed': not scripts_entries and not business_imports, 'scope': 'STATIC_ONLY', 'evidence': proof})
    failures = [row for row in result['checks'] if not row['passed']]
    result['summary'].update(status='FAIL' if failures else 'PASS', checks_total=len(result['checks']),
                             checks_failed=len(failures), failures=failures)
    if args.out_dir:
        raw = Path(args.out_dir)
        target = (ROOT / raw).resolve() if not raw.is_absolute() else raw.resolve()
        target.relative_to(EVIDENCE_ROOT.resolve())
        if target == EVIDENCE_ROOT.resolve() or not target.name.startswith('task039_r1_'):
            raise ValueError('output must be a task039_r1 round strictly below evidence root')
        if target.exists() and any(target.iterdir()):
            raise ValueError('output already contains evidence; choose a new round')
        target.mkdir(parents=True, exist_ok=True)
        for name, value in result.items():
            with (target / (name + '.json')).open('xb') as handle:
                handle.write(canon(value) + b'\n')
    summary = result['summary']
    print(json.dumps({'status': summary['status'], 'checks_total': summary['checks_total'],
                      'checks_failed': summary['checks_failed'], 'failures': summary['failures']}, ensure_ascii=False))
    return 1 if summary['checks_failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
