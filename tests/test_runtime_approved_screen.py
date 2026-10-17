#!/usr/bin/env python
"""TASK-031 minimal frozen SQL screening integration and accepted evidence closure."""
from __future__ import annotations
import argparse
import builtins
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_approved_screen_tests"


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(data): return hashlib.sha256(data).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PREVIOUS = load(ROOT / "tests/test_runtime_gate2_decision.py", "task031_accepted_helpers")
SCENES = PREVIOUS.PREVIOUS.scene_bytes


class Observer(PREVIOUS.Observer):
    def __init__(self, rt, e):
        self.screen_window = False
        super().__init__(rt, e)
        for name in ("run_gate2_approved_screen", "inspect_gate2_approved_screen"):
            self.codes[getattr(rt, name).__code__] = name
            self.counts[name] = self.api[name] = 0
        self.wrap(rt._load_frozen_screen_031(), "screen_sqlite", "screen")

    def wrap(self, module, name, label, forbidden=False):
        super().wrap(module, name, label, forbidden)
        if label not in ("screen", "store_save"):
            return
        spy = getattr(module, name)
        def observed(*args, **kwargs):
            if label == "store_save" and self.screen_window:
                self.guard_hits.append("store_save_in_screen_window")
                raise AssertionError("screen must not save decisions")
            before_count = len(self.e.CORE_RECORDS)
            before = self.e.reading(args[0]) if label == "screen" else None
            try:
                return spy(*args, **kwargs)
            finally:
                if label == "screen":
                    after = self.e.reading(args[0])
                    for entry in self.e.CORE_RECORDS[before_count:]:
                        if entry["core"] == "screen":
                            entry["database_before"], entry["database_after"] = before, after
        setattr(module, name, observed)


def evidence_module():
    e = PREVIOUS.evidence_module()
    previous_build = e.build_candidate
    def build(*args, **kwargs):
        candidate = previous_build(*args, **kwargs)
        candidate["summary"]["task"] = "TASK-031"
        candidate["summary"]["record_categories"] = {
            "direct_public": sum(x.get("record_category") == "direct_public" for x in candidate["api_records"]),
            "helper_control": sum(x.get("record_category") == "helper_control" for x in candidate["api_records"])}
        return candidate
    e.build_candidate = build
    return e


def run(e, rt, obs, out):
    rid = out.name
    runtime = ROOT / "data/runtime" / rid
    gate1 = ROOT / "data/human_gate_decision_records/gate1" / rid
    gate2 = ROOT / "data/human_gate_decision_records/gate2" / rid
    databases = ROOT / "data/sqlite_tests" / rid
    for parent in (runtime, gate1, databases): parent.mkdir(parents=True, exist_ok=False)
    batch = e.BATCH_NORMAL
    assert sha((batch / "source/input.xlsx").read_bytes()) == "8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341"
    fixture_path = ROOT / "data/decision_protocol_checks/task020r2_run_01/fixture_values.json"
    fixture_raw = fixture_path.read_bytes()
    assert sha(fixture_raw) == "6d8126aee3497a9c00cfee7493e2d04783e3284a61b911dd688bff29b433b337"
    g2fields = json.loads(fixture_raw)["BASE2"]["submission"]
    hold_raw = e.HOLD_FIXTURE.read_bytes()
    assert sha(hold_raw) == "8e3cf5670e91f3c48776360ab8fc22b6fef3f9bce76f56d3793804142b5cd4fa"
    original_source = SCENES([batch])

    def call(label, fn, *args, category="direct_public", **kwargs):
        before = copy.deepcopy(obs.counts)
        prior = obs.gate2, obs.screen_window
        obs.gate2 = obs.screen_window = label in ("screen", "inspect")
        try:
            error, value, cid = e.call_api(rt, label, fn, *args, **kwargs)
            e.API_RECORDS[-1].update(record_category=category, reasons=copy.deepcopy(getattr(error, "reasons", None)),
                actual_entry_deltas={key: obs.counts[key] - before.get(key, 0) for key in obs.counts})
            return error, copy.deepcopy(value), cid
        finally:
            obs.gate2, obs.screen_window = prior

    def setup(tag, hold=False):
        leaf, scope, event = runtime / tag, gate1 / tag, gate1 / tag / "event_0001"
        error, _, _ = call("registry", rt.build_runtime_registry, batch, leaf, scope_dir=scope)
        if error: raise error
        error, prepared, _ = call("g1_prepare", rt.prepare_runtime_gate1_request, batch, leaf, "FIXTURE-REQ-G1-0001")
        if error: raise error
        material = prepared["request"]["materials"]
        sub = e.submission_for(e.APPROVE_FIELDS, material["materials_fingerprint"], "FIXTURE-REQ-G1-0001", material["batch_id"])
        error, saved1, _ = call("g1_save", rt.save_runtime_gate1_decision, batch, leaf, "FIXTURE-REQ-G1-0001", sub, event, scope_dir=scope)
        if error: raise error
        args = {"scope_dir": scope, "event_relative": event.relative_to(ROOT).as_posix(),
                "database_path": databases / tag / "runtime.sqlite3"}
        error, _, _ = call("load", rt.run_gate1_approved_load, batch, leaf, **args)
        if error: raise error
        error, request2, _ = call("g2_prepare", rt.prepare_runtime_gate2_request, batch, leaf, "FIXTURE-REQ-G2-0001", **args)
        if error: raise error
        value = copy.deepcopy(g2fields)
        if hold:
            hold_fields = json.loads(hold_raw)["fragment"]
            for key in ("event_id", "actor", "decided_at_raw", "reason", "decision", "decision_source"):
                value[key] = copy.deepcopy(hold_fields[key])
        value["batch_id"] = material["batch_id"]
        value["request_binding"] = {"request_id": "FIXTURE-REQ-G2-0001", "materials_binding": request2["request"]["materials"]["materials_fingerprint"]}
        value["prior_decision_binding"] = {"wrapper_version": rt.GATE2_WRAPPER_VERSION,
            "record": saved1["record"], "record_fingerprint": saved1["record_fingerprint"]}
        event2 = gate2 / tag / "event_0001"
        error, saved2, _ = call("g2_save", rt.save_runtime_gate2_decision, batch, leaf, "FIXTURE-REQ-G2-0001", value, event2, **args)
        if error: raise error
        args["gate2_event_relative"] = event2.relative_to(ROOT).as_posix()
        return {"leaf": leaf, "scope": scope, "event": event, "event2": event2, "args": args,
                "output": leaf.with_name(tag + ".screen"), "saved2": saved2}

    def screen(scene, **overrides): return call("screen", rt.run_gate2_approved_screen, batch, scene["leaf"], **dict(scene["args"], **overrides))
    def inspect(scene): return call("inspect", rt.inspect_gate2_approved_screen, batch, scene["leaf"], **scene["args"])
    def sources(scene): return SCENES([batch, scene["leaf"], scene["scope"], scene["event2"],
        scene["leaf"].with_name(scene["leaf"].name + ".load"), scene["args"]["database_path"].parent])

    normal = setup("normal")
    before = sources(normal)
    error, _, cid = screen(normal, gate2_event_relative=normal["args"]["gate2_event_relative"].replace("event_0001", "event_0002"))
    e.check("G2.wrong_gate2", isinstance(error, rt.RuntimeGate1Blocked) and not normal["output"].exists() and
            e.API_RECORDS[-1]["actual_entry_deltas"]["screen"] == 0, {"call_id": cid, "field": getattr(error, "field", None)})
    error, _, cid = screen(normal, database_path=ROOT / "data/runtime/outside.sqlite3")
    e.check("G2.database_path", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "database_path" and not normal["output"].exists(), {"call_id": cid})

    context_path, receipt_path = normal["event2"] / "context.json", normal["event2"] / "receipt.json"
    context_original, receipt_original = context_path.read_bytes(), receipt_path.read_bytes()
    (out / "gate2.context.original.bin").write_bytes(context_original)
    (out / "gate2.receipt.original.bin").write_bytes(receipt_original)
    context = json.loads(context_original);context["gate1_event_relative"] = "OTHER"
    bad = canon(context) + b"\n";context_path.write_bytes(bad)
    receipt = json.loads(receipt_original);receipt["context_file_sha256"] = sha(bad);receipt_path.write_bytes(canon(receipt) + b"\n")
    error, _, cid = screen(normal)
    e.check("G2.inner_binding", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "gate2.context.gate1_event_relative" and
            not normal["output"].exists(), {"call_id": cid, "field": getattr(error, "field", None)})
    (out / "gate2.context.bad.bin").write_bytes(context_path.read_bytes());(out / "gate2.receipt.bad.bin").write_bytes(receipt_path.read_bytes())
    context_path.write_bytes(context_original);receipt_path.write_bytes(receipt_original)

    injected_failure = normal["event2"] / "failure.json"
    payload = {"failure_version": rt.GATE2_FAILURE_VERSION, "stage": "fixture", "field": "fixture",
               "reason": "PROTOCOL_TEST_FIXTURE_ONLY", "cause_chain": []}
    injected_failure.write_bytes(canon(payload) + b"\n")
    error, _, cid = screen(normal)
    e.check("G2.existing_failure", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "gate2.failure" and
            not normal["output"].exists(), {"call_id": cid})
    (out / "gate2.failure.injected.bin").write_bytes(injected_failure.read_bytes());injected_failure.unlink()  # exact own injected single-file absent-state restoration

    database = normal["args"]["database_path"]
    database_original = database.read_bytes();(out / "database.original.bin").write_bytes(database_original)
    real_verify, hit = rt.verify_runtime_gate2_decision, [0]
    def verified_then_change(*args, **kwargs):
        returned = real_verify(*args, **kwargs);hit[0] += 1
        database.write_bytes(database_original + b"\n")
        return returned
    rt.verify_runtime_gate2_decision = verified_then_change
    try: error, _, cid = screen(normal)
    finally: rt.verify_runtime_gate2_decision = real_verify
    (out / "database.late.bad.bin").write_bytes(database.read_bytes());database.write_bytes(database_original)
    e.check("G3.before_screen", isinstance(error, rt.RuntimeGate1Blocked) and hit == [1] and
            e.API_RECORDS[-1]["actual_entry_deltas"]["screen"] == 0 and not normal["output"].exists(),
            {"call_id": cid, "field": getattr(error, "field", None), "hit": hit[0]})

    error, recorded, cid_run = screen(normal)
    if error: raise error
    semantic, real_equivalent = [], rt._require_equivalent_030
    def observe_fields(value, expected, field):
        returned = real_equivalent(value, expected, field);semantic.append(field);return returned
    rt._require_equivalent_030 = observe_fields
    hits = []
    try:
        with PREVIOUS.PREVIOUS.readonly_guard(hits): error, restored, cid_inspect = inspect(normal)
    finally: rt._require_equivalent_030 = real_equivalent
    core_record = next(c for c in e.CORE_RECORDS if c["caller_api"] == cid_run and c["core"] == "screen")
    report_path = normal["output"] / "screening_report.json"
    report_original = report_path.read_bytes();(out / "screen_report.original.bin").write_bytes(report_original)
    report = json.loads(report_original)
    e.check("G1.normal", error is None and len(recorded) == 6 and canon(recorded) == canon(restored) and
            len(list(normal["output"].iterdir())) == 3 and not hits and before == sources(normal) and
            all(v is False for v in recorded["boundaries"].values()), {"run": cid_run, "inspect": cid_inspect, "readonly_hits": hits})
    e.check("G1.real_report_and_facts", canon(core_record["return"]) == canon(report) and canon(core_record["return"]) + b"\n" == report_original and
            report["rule_hit_counts"] == {"R01": 0, "R02": 1, "R03": 0, "R04": 0, "total": 1} and
            report["statistics"]["r02_overpayment_total_cents"] == 1000000 - 100000 - 500000 and
            core_record["database_before"] == core_record["database_after"] and
            core_record["input_refs_before"] == core_record["input_refs_after"] == core_record["input_refs_api_end"],
            {"screen_original_entry_delta": next(c for c in e.API_RECORDS if c['call_id'] == cid_run)['actual_entry_deltas']['screen']})
    error, _, cid = screen(normal)
    e.check("G2.repeat", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "screen_dir", {"call_id": cid})
    last_field, hit = semantic[-1], [0]
    def last_semantic(value, expected, field):
        returned = real_equivalent(value, expected, field)
        if field == last_field:
            hit[0] += 1;report_path.write_bytes(report_original + b"\n")
        return returned
    rt._require_equivalent_030 = last_semantic
    try: error, _, cid = inspect(normal)
    finally: rt._require_equivalent_030 = real_equivalent
    e.check("G3.inspect_late", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "screen.screening_report.json" and
            hit == [1] and not (normal["output"] / "failure.json").exists(),
            {"call_id": cid, "last_observed_semantic_field": last_field, "hit": hit[0]})
    (out / "screen_report.late.bad.bin").write_bytes(report_path.read_bytes())
    error_still, _, cid_still = inspect(normal)
    report_path.write_bytes(report_original)
    error_restored, _, cid_restored = inspect(normal)
    e.check("G3.inspect_retained_restored", error_still is not None and error_restored is None and before == sources(normal),
            {"retained": cid_still, "restored": cid_restored})

    hold = setup("hold", hold=True)
    gate2_args = dict(hold["args"])
    error, held, cid = call("g2_verify", rt.verify_runtime_gate2_decision, batch, hold["leaf"], **gate2_args)
    error2, _, cid2 = screen(hold)
    e.check("G2.hold", error is None and held["record"]["decision"] == "HOLD" and
            isinstance(error2, rt.RuntimeGate1Blocked) and error2.field == "gate2.record.decision" and
            not hold["output"].exists() and e.API_RECORDS[-1]["actual_entry_deltas"]["screen"] == 0,
            {"verify": cid, "run": cid2})
    lock = hold["leaf"].with_name("hold.gate2.lock");lock.mkdir();(lock / "lock.json").write_bytes(b"PROTOCOL_TEST_FIXTURE_ONLY\n")
    lock_before = SCENES([lock]);error, _, cid = screen(hold)
    e.check("G2.lock", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "gate2_lock" and lock_before == SCENES([lock]), {"call_id": cid})
    empty_leaf, empty_scope = runtime / "existing_empty", gate1 / "existing_empty"
    error, _, _ = call("registry", rt.build_runtime_registry, batch, empty_leaf, scope_dir=empty_scope)
    if error: raise error
    empty_output = empty_leaf.with_name("existing_empty.screen");empty_output.mkdir()
    error, _, cid = call("screen", rt.run_gate2_approved_screen, batch, empty_leaf,
        scope_dir=empty_scope, event_relative=(empty_scope / "event_0001").relative_to(ROOT).as_posix(),
        database_path=database, gate2_event_relative=(gate2 / "existing_empty/event_0001").relative_to(ROOT).as_posix())
    e.check("G2.existing_empty", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "screen_dir" and
            not list(empty_output.iterdir()), {"call_id": cid, "precondition_layer_only": True})

    late = setup("writer_late")
    real_writer, hit = rt._write_exclusive, [0]
    def write_then_change(path, buffer, stage):
        returned = real_writer(path, buffer, stage)
        if path == late["output"] / "screening_report.json":
            hit[0] += 1;path.write_bytes(buffer + b"\n")
        return returned
    rt._write_exclusive = write_then_change
    try: error, _, cid = screen(late)
    finally: rt._write_exclusive = real_writer
    e.check("G3.writer_return_binding", isinstance(error, rt.RuntimeGate1Blocked) and
            error.field == "screen.screening_report.json" and hit == [1], {"call_id": cid, "hit": hit[0]})

    half_scene = setup("half_artifacts")
    real_open, half = builtins.open, {"hits": 0}
    class HalfWriter:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): self.stream.__enter__();return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def __getattr__(self, name): return getattr(self.stream, name)
        def write(self, data):
            length = len(data) // 2;self.stream.write(data[:length]);self.stream.flush()
            half.update(hits=half["hits"] + 1, mode="xb", expected=len(data), written=length)
            raise OSError("TASK031_REAL_ARTIFACTS_HALF_WRITE")
    def half_open(path, mode="r", *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        if isinstance(path, (str, Path)) and Path(path) == half_scene["output"] / "artifacts.json" and mode == "xb":
            return HalfWriter(stream)
        return stream
    builtins.open = half_open
    try: error, _, cid = screen(half_scene)
    finally: builtins.open = real_open
    diag = json.loads((half_scene["output"] / "failure.json").read_bytes())
    e.check("G3.real_half_write", isinstance(error, rt.RuntimeGate1Error) and half["hits"] == 1 and len(diag) == 6 and
            (half_scene["output"] / "artifacts.json").stat().st_size == half["written"] and
            any("OSError" in text for text in diag["cause_chain"]), {"call_id": cid, "stage": getattr(error, "stage", None), "writer": half, "diagnostic": diag})
    scene_before = SCENES([half_scene["output"]]);error, _, cid = inspect(half_scene)
    e.check("G3.failure_priority", isinstance(error, rt.RuntimeGate1Error) and
            error.stage.startswith("screen.failure.") and scene_before == SCENES([half_scene["output"]]), {"call_id": cid})

    core = rt._load_frozen_screen_031();real_entry = core.screen_sqlite
    mapping = []
    for cls, expected in ((core.RuleScreenBlocked, rt.RuntimeGate1Blocked), (core.RuleScreenError, rt.RuntimeGate1Error)):
        reasons, hit = ["controlled reason 1", "controlled reason 2"], [0]
        def controlled(*args, **kwargs):
            hit[0] += 1;raise cls("TASK031_CONTROLLED_CLASS_MAPPING", reasons)
        core.screen_sqlite = controlled
        try:
            error, _, cid = call("mapping_helper", rt._call_frozen_entry, core, "screen_sqlite",
                str(database), json.loads((normal["leaf"].with_name("normal.load") / "load_report.json").read_bytes()),
                category="helper_control", cutoff_date="2026-09-30")
        finally: core.screen_sqlite = real_entry
        e.check("G3.mapping_" + cls.__name__, isinstance(error, expected) and isinstance(error.__cause__, cls) and
                error.reasons == reasons and hit == [1], {"call_id": cid, "hit": hit[0], "scope": "controlled helper mapping, not business discovery"})
        mapping.append({"call_id": cid, "original_class": cls.__name__, "mapped_class": type(error).__name__, "reasons": error.reasons})
    scoped = [x for x in e.API_RECORDS if x["operation"] in ("screen", "inspect")]
    e.check("G4.forbidden_entries", not obs.guard_hits and all(all(r["actual_entry_deltas"].get(k, 0) == 0
        for k in ("normalizer", "loader", "store_save")) for r in scoped) and all(r["actual_entry_deltas"]["screen"] == 0 for r in scoped if r["operation"] == "inspect"),
        {"window_calls": len(scoped), "guard_hits": obs.guard_hits})
    count_map = {"inspect": "inspect_gate1_approved_load", "gate1_verify": "verify_gate1_effective_approval"}
    counts = {key: {"entries": count, "profile": obs.counts.get(count_map.get(key, key), 0)} for key, count in obs.nested.items()}
    e.check("G4.count_closure", all(value["entries"] == value["profile"] for value in counts.values()), counts)
    e.check("G4.source_unchanged", original_source == SCENES([batch]))
    return {"fixture_label": "PROTOCOL_TEST_FIXTURE_ONLY", "fixture_sha256": sha(fixture_raw), "HOLD_sha256": sha(hold_raw),
            "counts": counts, "mapping_controls": mapping, "new_receiver_calls": 0,
            "not_executed": {name: {"count": None, "reason": "outside TASK-031 scope; not reported as guarded zero"}
                for name in ("crosscheck", "facts", "human_initial_judgment", "AI", "new_junction", "historical_suites")}}


def main(argv=None):
    parser = argparse.ArgumentParser();parser.add_argument("--out-dir", required=True);parser.add_argument("--replay")
    parser.add_argument("--mutate", choices=("none", "candidate-return", "ledger-late", "checks-late"), default="none")
    args = parser.parse_args(argv);out = Path(args.out_dir).resolve()
    if not out.is_relative_to(TEST_ROOT.resolve()) or out == TEST_ROOT.resolve() or out.exists() or not out.name.startswith("task031_"):
        raise SystemExit("out-dir must be never-existing task031_ strict descendant")
    e = evidence_module();e.ROUND["id"] = out.name;out.mkdir(parents=True, exist_ok=False);obs = None
    if args.replay:
        source = Path(args.replay).resolve()
        if not source.is_relative_to(TEST_ROOT.resolve()) or source == out: raise SystemExit("invalid replay source")
        checkpoint = json.loads((source / "expected_observations.json").read_bytes());extra = {"replay_only": True, "new_business_calls": 0, "source": str(source)}
    else:
        if args.mutate != "none": raise SystemExit("mutations require replay")
        rt = load(ROOT / "scripts/runtime_gate1.py", "task031_runtime_under_test");obs = Observer(rt, e);sys.setprofile(obs.profile)
        try: extra = run(e, rt, obs, out)
        finally: sys.setprofile(None)
        checkpoint = e.freeze_expectations()
    original_read, injection = Path.read_bytes, {"hits": 0}
    if args.mutate in ("ledger-late", "checks-late"):
        def read_then_mutate(path):
            result = original_read(path);frame = sys._getframe(1)
            if frame.f_code is e.finish.__code__ and "terminal_buffers" in frame.f_locals and path == out / "expected_observations.json" and not injection["hits"]:
                target = out / ("file_ledger.json" if args.mutate == "ledger-late" else "checks.json");before = original_read(target)
                with open(target, "ab") as stream: stream.write(b"\n")
                injection.update(hits=1, target=target.name, before_size=len(before), after_size=len(before)+1,
                    before_sha256=sha(before), after_sha256=sha(before+b"\n"), boundary="after_semantic_ledger_consumption_in_terminal_byte_loop")
            return result
        Path.read_bytes = read_then_mutate
    try: code = e.finish(out, checkpoint, "candidate-return" if args.mutate == "candidate-return" else "none", obs, extra)
    finally: Path.read_bytes = original_read
    if args.mutate in ("ledger-late", "checks-late"):
        (out / "control_observation.json").write_bytes(canon(injection) + b"\n")
    return code


if __name__ == "__main__": raise SystemExit(main())
