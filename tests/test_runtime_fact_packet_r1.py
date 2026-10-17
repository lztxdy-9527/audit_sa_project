#!/usr/bin/env python
"""TASK-033-R1: one current chain, four context negatives, accepted R03 memory control.

The TASK-033 test/closure helpers are imported read-only; its business suite is not run.
"""
from __future__ import annotations
import argparse
import copy
import json
import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / 'data/runtime_fact_packet_tests'

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

PREVIOUS = load(ROOT / 'tests/test_runtime_fact_packet.py', 'task033_r1_readonly_helpers')
canon, sha, SCENES = PREVIOUS.canon, PREVIOUS.sha, PREVIOUS.SCENES
readonly_guard = PREVIOUS.PREVIOUS.PREVIOUS.PREVIOUS.PREVIOUS.readonly_guard

class Observer(PREVIOUS.Observer):
    def __init__(self, rt, e):
        self.test_renderer = False
        super().__init__(rt, e)
        self.wrap(rt, '_validate_fact_context_033', 'context_helper')
        self.wrap(rt, '_validate_fact_payable_033', 'payable_context_helper')

    def wrap(self, module, name, label, forbidden=False):
        super().wrap(module, name, label, forbidden)
        if label != 'facts_render':
            return
        real = getattr(module, name)
        def observed(*args, **kwargs):
            start = len(self.e.CORE_RECORDS)
            try:
                return real(*args, **kwargs)
            finally:
                if self.test_renderer:
                    for record in self.e.CORE_RECORDS[start:]:
                        if record['core'] == label:
                            record['renderer_role'] = 'test_candidate_generation'
        setattr(module, name, observed)

def evidence_module():
    e = PREVIOUS.evidence_module()
    original = e.build_candidate
    def build(*args, **kwargs):
        candidate = original(*args, **kwargs)
        candidate['summary']['task'] = 'TASK-033-R1'
        candidate['summary']['record_categories'] = {
            category: sum(x.get('record_category') == category for x in candidate['api_records'])
            for category in ('direct_public', 'test_candidate_renderer', 'historical_context_helper')}
        return candidate
    e.build_candidate = build
    return e

def run(e, rt, obs, out):
    rid = out.name
    runtime, gate1, gate2, dbroot = [ROOT / parent / rid for parent in (
        'data/runtime', 'data/human_gate_decision_records/gate1',
        'data/human_gate_decision_records/gate2', 'data/sqlite_tests')]
    for parent in (runtime, gate1, dbroot):
        parent.mkdir(parents=True, exist_ok=False)
    batch = e.BATCH_NORMAL
    source_before = SCENES([batch])
    assert sha((batch / 'source/input.xlsx').read_bytes()) == '8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341'
    fixture_raw = (ROOT / 'data/decision_protocol_checks/task020r2_run_01/fixture_values.json').read_bytes()
    assert sha(fixture_raw) == '6d8126aee3497a9c00cfee7493e2d04783e3284a61b911dd688bff29b433b337'
    g2fields = json.loads(fixture_raw)['BASE2']['submission']

    def call(label, fn, *args, category='direct_public', **kwargs):
        before = copy.deepcopy(obs.counts)
        prior = (obs.gate2, obs.screen_window, obs.crosscheck_window, obs.facts_window,
                 obs.facts_inspecting, obs.test_renderer)
        obs.facts_window = label in ('facts', 'facts_inspect')
        obs.facts_inspecting = label == 'facts_inspect'
        obs.test_renderer = category == 'test_candidate_renderer'
        obs.crosscheck_window = obs.facts_window
        obs.gate2 = obs.screen_window = obs.facts_window
        try:
            error, value, cid = e.call_api(rt, label, fn, *args, **kwargs)
            e.API_RECORDS[-1].update(record_category=category,
                reasons=copy.deepcopy(getattr(error, 'reasons', None)),
                actual_entry_deltas={k: obs.counts[k] - before.get(k, 0) for k in obs.counts})
            return error, value, cid
        finally:
            (obs.gate2, obs.screen_window, obs.crosscheck_window, obs.facts_window,
             obs.facts_inspecting, obs.test_renderer) = prior

    def must(label, fn, *args, **kwargs):
        error, value, cid = call(label, fn, *args, **kwargs)
        if error:
            raise error
        return value, cid

    leaf, scope = runtime / 'normal', gate1 / 'normal'
    event = scope / 'event_0001'
    must('registry', rt.build_runtime_registry, batch, leaf, scope_dir=scope)
    request, _ = must('g1_prepare', rt.prepare_runtime_gate1_request, batch, leaf, 'FIXTURE-REQ-G1-0001')
    materials = request['request']['materials']
    sub = e.submission_for(e.APPROVE_FIELDS, materials['materials_fingerprint'], 'FIXTURE-REQ-G1-0001', materials['batch_id'])
    record1, _ = must('g1_save', rt.save_runtime_gate1_decision, batch, leaf, 'FIXTURE-REQ-G1-0001', sub, event, scope_dir=scope)
    params = dict(scope_dir=scope, event_relative=event.relative_to(ROOT).as_posix(), database_path=dbroot / 'normal/runtime.sqlite3')
    must('load', rt.run_gate1_approved_load, batch, leaf, **params)
    request2, _ = must('g2_prepare', rt.prepare_runtime_gate2_request, batch, leaf, 'FIXTURE-REQ-G2-0001', **params)
    sub2 = copy.deepcopy(g2fields)
    sub2['batch_id'] = materials['batch_id']
    sub2['request_binding'] = {'request_id': 'FIXTURE-REQ-G2-0001', 'materials_binding': request2['request']['materials']['materials_fingerprint']}
    sub2['prior_decision_binding'] = {'wrapper_version': rt.GATE2_WRAPPER_VERSION, 'record': record1['record'], 'record_fingerprint': record1['record_fingerprint']}
    event2 = gate2 / 'normal/event_0001'
    must('g2_save', rt.save_runtime_gate2_decision, batch, leaf, 'FIXTURE-REQ-G2-0001', sub2, event2, **params)
    params['gate2_event_relative'] = event2.relative_to(ROOT).as_posix()
    must('screen', rt.run_gate2_approved_screen, batch, leaf, **params)
    must('crosscheck', rt.run_gate2_rule_crosscheck, batch, leaf, **params)
    upstream = [batch, leaf, scope, event2, params['database_path'].parent,
                *(leaf.with_name('normal' + suffix) for suffix in ('.load', '.screen', '.crosscheck'))]
    before = SCENES(upstream)
    recorded, build_id = must('facts', rt.run_gate2_fact_packet, batch, leaf, **params)
    hits = []
    with readonly_guard(hits):
        restored, inspect_id = must('facts_inspect', rt.inspect_gate2_fact_packet, batch, leaf, **params)
    output = leaf.with_name('normal.facts')
    paths = {name: output / name for name in ('fact_packet.json', 'fact_packet.md', 'artifacts.json')}
    originals = {name: path.read_bytes() for name, path in paths.items()}
    for name, raw in originals.items():
        (out / (name + '.original.bin')).write_bytes(raw)
    packet = json.loads(originals['fact_packet.json'])
    core = rt._load_frozen_facts_033()
    built = [x for x in e.CORE_RECORDS if x['core'] == 'facts_build' and x['caller_api'] == build_id]
    run_render = [x for x in e.CORE_RECORDS if x['core'] == 'facts_render' and x['caller_api'] == build_id]
    inspect_render = [x for x in e.CORE_RECORDS if x['core'] == 'facts_render' and x['caller_api'] == inspect_id]
    e.check('R1.normal', not hits and canon(recorded) == canon(restored) and len(recorded) == 6 and
        all(v is False for v in recorded['boundaries'].values()) and len(list(output.iterdir())) == 4 and
        before == SCENES(upstream), {'build_call': build_id, 'inspect_call': inspect_id, 'readonly_hits': hits})
    e.check('R1.real_build_render', len(built) == len(run_render) == len(inspect_render) == 1 and
        canon(built[0]['return']['packet']) + b'\n' == originals['fact_packet.json'] and
        built[0]['return']['packet_sha256'] == sha(canon(packet)) and
        built[0]['return']['markdown'].encode('utf-8') == originals['fact_packet.md'] and
        all(x['return'].encode('utf-8') == originals['fact_packet.md'] for x in run_render + inspect_render) and
        all(x['input_refs_before'] == x['input_refs_after'] == x['input_refs_api_end'] for x in built + run_render + inspect_render),
        {'build': 1, 'build_internal_render': len(run_render), 'inspect_render': len(inspect_render)})
    started = json.loads((output / 'started.json').read_bytes())
    e.check('R1.original_template_context', canon(packet['banner']) == canon(core.BANNER) and
        canon(packet['limits']) == canon(core.LIMITS) and canon(started['runtime_context']) == canon(rt.FACT_RUNTIME_CONTEXT) and
        '未实施正式契约与批准控制' in originals['fact_packet.md'].decode('utf-8'))
    e.check('R1.test_only_expected_fact', packet['summary']['rule_counts'] == {'R01': 0, 'R02': 1, 'R03': 0, 'R04': 0} and
        packet['summary']['r02_overpayment_total_cents'] == 400000,
        {'scope': 'test expectation only; not a production decision'})

    def candidate(tag, edit, expected_field, *, render=False):
        proposed = json.loads(originals['fact_packet.json'])
        edit(proposed['findings'][0]['context'])
        new_packet = canon(proposed) + b'\n'
        new_md = originals['fact_packet.md']
        renderer_id = None
        if render:
            error, text, renderer_id = call('candidate_renderer', core.render_markdown, proposed, category='test_candidate_renderer')
            if error:
                raise error
            new_md = text.encode('utf-8')
        artifact = json.loads(originals['artifacts.json'])
        artifact.update(packet_file_sha256=sha(new_packet), packet_canonical_sha256=sha(canon(proposed)),
                        markdown_file_sha256=sha(new_md), markdown_byte_size=len(new_md))
        payloads = {'fact_packet.json': new_packet, 'fact_packet.md': new_md, 'artifacts.json': canon(artifact) + b'\n'}
        for name, raw in payloads.items():
            paths[name].write_bytes(raw)
            (out / (tag + '.' + name + '.bad.bin')).write_bytes(raw)
        readonly_hits = []
        with readonly_guard(readonly_hits):
            error, _, cid = call('facts_inspect', rt.inspect_gate2_fact_packet, batch, leaf, **params)
        delta = e.API_RECORDS[-1]['actual_entry_deltas']
        expected_block = isinstance(error, rt.RuntimeGate1Blocked) and error.field == expected_field
        if tag == 'missing_status':
            expected_block = expected_block and '缺少' in error.reason
        e.check('R1.' + tag, expected_block,
            {'call_id': cid, 'field': getattr(error, 'field', None), 'exception': type(error).__name__,
             'reason': getattr(error, 'reason', None), 'test_renderer_call': renderer_id})
        e.check('R1.' + tag + '.before_renderer_readonly', delta['facts_render'] == delta['facts_build'] == 0 and
            not readonly_hits and not (output / 'failure.json').exists() and
            all(paths[name].read_bytes() == raw for name, raw in payloads.items()),
            {'inspect_call': cid, 'actual_entry_deltas': delta, 'candidate_sha256': {n: sha(v) for n, v in payloads.items()},
             'original_sha256': {n: sha(v) for n, v in originals.items()}, 'readonly_hits': readonly_hits})
        for name, raw in originals.items():
            paths[name].write_bytes(raw)

    assert packet['findings'][0]['context']['payable']['record_id'] == 'AP01'
    candidate('false_missing', lambda c: c.__setitem__('payable', {'label': '相关应付单', 'record_id': 'AP01', 'status': 'not_found'}),
              'facts.packet.findings[0].context.payable.status', render=True)
    candidate('missing_status', lambda c: c['payable'].__delitem__('status'), 'facts.packet.findings[0].context.payable.status')
    candidate('missing_payable', lambda c: c.__delitem__('payable'), 'facts.packet.findings[0].context.payable')
    assert len(packet['findings'][0]['context']['payments']) >= 2
    def swap(c):
        c['payments'][0], c['payments'][1] = c['payments'][1], c['payments'][0]
    candidate('payment_id_swap', swap, 'facts.packet.findings[0].context.payments[0].record_id')

    registration_path = ROOT / 'data/reviews/task033_gpt_20261016_034829/reference_fixture_identities.json'
    registration = json.loads(registration_path.read_bytes())
    baseline_path = ROOT / 'data/reviews/task032_gpt_20261016_030543/source_hashes_after.json'
    baseline_raw = baseline_path.read_bytes()
    assert sha(baseline_raw) == '002f0477e7a6d98273c8591c9f4537d8770e26c595f94398094d4e4814eba9c7'
    accepted = json.loads(baseline_raw)
    fixtures, identities = {}, {}
    for relative, identity in registration.items():
        raw = (ROOT / relative).read_bytes()
        assert sha(raw) == identity['sha256'] == accepted[relative] and len(raw) == identity['byte_size']
        fixtures[Path(relative).name] = json.loads(raw)
        identities[relative] = {'sha256': sha(raw), 'byte_size': len(raw)}
        (out / ('C07b.' + Path(relative).name + '.source.bin')).write_bytes(raw)
    r03 = next(x for x in fixtures['screening_report.json']['findings'] if x['rule_id'] == 'R03')
    r03card = next(x for x in fixtures['fact_packet.json']['findings'] if x['rule_id'] == 'R03' and canon(x['hit_key']) == canon(r03['hit_key']))
    # Historical accepted packet has a former supplier layout. Validate its exact
    # payable role with the shared production helper; do not migrate or relax the
    # current complete-context schema to accept an old presentation layout.
    index = {sheet: {row['data'][key]: row for row in fixtures['normalized.json']['tables'][sheet]['records']}
             for sheet, key in (('suppliers', 'supplier_id'), ('payables', 'ap_id'),
                                ('payments', 'payment_id'), ('allocations', 'allocation_id'))}
    error, _, cid = call('C07b_context_only', rt._validate_fact_payable_033,
        r03card['context']['payable'], index, r03['related_ids'], 'fixture.C07b.context.payable', category='historical_context_helper')
    e.check('R1.legitimate_R03', error is None and r03card['context']['payable']['status'] == 'not_found' and
        r03card['context']['payable']['record_id'] is None and r03card['context']['payable']['missing_kind_code'] == 'EMPTY_AP_ID' and
        all(e.API_RECORDS[-1]['actual_entry_deltas'].get(k, 0) == 0 for k in ('facts_build', 'facts_render', 'screen', 'crosscheck', 'normalizer', 'loader', 'store_save')),
        {'call_id': cid, 'source_identities': identities,
         'scope': 'exact historical payable context, current shared payable helper only; former full-context layout not migrated'})
    final_hits = []
    with readonly_guard(final_hits):
        final, final_id = must('facts_inspect', rt.inspect_gate2_fact_packet, batch, leaf, **params)
    e.check('R1.restored', not final_hits and canon(final) == canon(recorded) and
        not (output / 'failure.json').exists() and all(paths[n].read_bytes() == v for n, v in originals.items()) and
        before == SCENES(upstream) and source_before == SCENES([batch]), {'call_id': final_id, 'readonly_hits': final_hits})
    windows = [x for x in e.API_RECORDS if x['operation'] in ('facts', 'facts_inspect')]
    e.check('R1.no_downstream_recalculation', not obs.guard_hits and all(all(x['actual_entry_deltas'].get(k, 0) == 0
        for k in ('normalizer', 'loader', 'store_save', 'screen', 'crosscheck')) for x in windows) and
        all(x['actual_entry_deltas']['facts_build'] == 0 for x in windows if x['operation'] == 'facts_inspect'),
        {'guard_hits': obs.guard_hits, 'fact_windows': len(windows)})
    aliases = {'inspect': 'inspect_gate1_approved_load', 'gate1_verify': 'verify_gate1_effective_approval',
               'screen_inspect': 'inspect_gate2_approved_screen', 'crosscheck_inspect': 'inspect_gate2_rule_crosscheck'}
    counts = {k: {'entries': v, 'original_code_profile': obs.counts[aliases.get(k, k)]} for k, v in obs.nested.items()}
    e.check('R1.complete_observation_count_closure', all(x['entries'] == x['original_code_profile'] for x in counts.values()) and
        len(e.API_RECORDS) == len({x['call_id'] for x in e.API_RECORDS}) and
        all(x['caller_api'] in {a['call_id'] for a in e.API_RECORDS} for x in e.CORE_RECORDS), counts)
    e.check('R1.same_references_three_points', all(x['input_refs_before'] == x['input_refs_after'] == x['input_refs_api_end']
        for x in e.CORE_RECORDS if 'input_refs_before' in x), {'scope': 'all current nested consumption references'})
    return {'fixture_label': 'PROTOCOL_TEST_FIXTURE_ONLY', 'gate2_fixture_sha256': sha(fixture_raw), 'counts': counts,
        'new_receiver_calls': 0, 'reference_fixture_identities': identities,
        'not_executed': {name: {'count': None, 'reason': 'outside TASK-033-R1; old evidence reference only where applicable'} for name in
            ('half_write', 'prior_and_terminal_late_changes', 'classification_injections', 'historical_suites',
             'new_junction', 'human_initial_judgment', 'AI', 'subprocess_business_core_counts')}}

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--replay')
    parser.add_argument('--mutate', choices=('none', 'candidate-return', 'ledger-late', 'checks-late'), default='none')
    args = parser.parse_args(argv)
    out = Path(args.out_dir).resolve()
    if not out.is_relative_to(TEST_ROOT.resolve()) or out == TEST_ROOT.resolve() or out.exists() or not out.name.startswith('task033_r1_'):
        raise SystemExit('out-dir must be a never-existing task033_r1_ strict descendant')
    e = evidence_module()
    e.ROUND['id'] = out.name
    out.mkdir(parents=True, exist_ok=False)
    obs = None
    if args.replay:
        source = Path(args.replay).resolve()
        if not source.is_relative_to(TEST_ROOT.resolve()) or not source.name.startswith('task033_r1_') or source == out:
            raise SystemExit('invalid replay source')
        checkpoint = json.loads((source / 'expected_observations.json').read_bytes())
        extra = {'replay_only': True, 'business_calls_claim': 'measured by external exact-code observer; historical records not new calls', 'source': str(source)}
    else:
        if args.mutate != 'none':
            raise SystemExit('mutations require replay')
        rt = load(ROOT / 'scripts/runtime_gate1.py', 'task033_r1_runtime_under_test')
        obs = Observer(rt, e)
        sys.setprofile(obs.profile)
        try:
            extra = run(e, rt, obs, out)
        finally:
            sys.setprofile(None)
        checkpoint = e.freeze_expectations()
    original_read, injection = Path.read_bytes, {'hits': 0}
    if args.mutate in ('ledger-late', 'checks-late'):
        def read_then_mutate(path):
            result = original_read(path)
            frame = sys._getframe(1)
            if frame.f_code is e.finish.__code__ and 'terminal_buffers' in frame.f_locals and path == out / 'expected_observations.json' and not injection['hits']:
                target = out / ('file_ledger.json' if args.mutate == 'ledger-late' else 'checks.json')
                before = original_read(target)
                with open(target, 'ab') as stream:
                    stream.write(b'\n')
                injection.update(hits=1, target=target.name, before_size=len(before), after_size=len(before)+1,
                    before_sha256=sha(before), after_sha256=sha(before+b'\n'), boundary='after_semantic_consumption_in_terminal_byte_loop')
            return result
        Path.read_bytes = read_then_mutate
    try:
        code = e.finish(out, checkpoint, 'candidate-return' if args.mutate == 'candidate-return' else 'none', obs, extra)
    finally:
        Path.read_bytes = original_read
    if args.mutate in ('ledger-late', 'checks-late'):
        (out / 'control_observation.json').write_bytes(canon(injection)+b'\n')
    return code

if __name__ == '__main__':
    raise SystemExit(main())
