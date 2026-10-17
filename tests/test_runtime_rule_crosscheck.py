#!/usr/bin/env python
"""TASK-032 targeted independent crosscheck integration; reuse accepted short closure."""
from __future__ import annotations
import argparse
import builtins
import copy
import json
import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_rule_crosscheck_tests"

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec);sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

PREVIOUS = load(ROOT / "tests/test_runtime_approved_screen.py", "task032_accepted_helpers")
canon, sha, SCENES = PREVIOUS.canon, PREVIOUS.sha, PREVIOUS.SCENES

class Observer(PREVIOUS.Observer):
    def __init__(self, rt, e):
        self.crosscheck_window = False
        super().__init__(rt, e)
        for name in ("run_gate2_rule_crosscheck", "inspect_gate2_rule_crosscheck"):
            self.codes[getattr(rt, name).__code__] = name
            self.counts[name] = self.api[name] = 0
        self.wrap(rt, "inspect_gate2_approved_screen", "screen_inspect")
        self.wrap(rt._load_frozen_crosscheck_032(), "verify_rule_facts", "crosscheck")

    def wrap(self, module, name, label, forbidden=False):
        super().wrap(module, name, label, forbidden)
        if label != "screen": return
        real = getattr(module, name)
        def observed(*args, **kwargs):
            if self.crosscheck_window:
                self.guard_hits.append("SQL_screen_in_crosscheck_window")
                raise AssertionError("crosscheck cannot run SQL screen")
            return real(*args, **kwargs)
        setattr(module, name, observed)

def evidence_module():
    e = PREVIOUS.evidence_module()
    original = e.build_candidate
    def build(*args, **kwargs):
        candidate = original(*args, **kwargs)
        candidate["summary"]["task"] = "TASK-032"
        return candidate
    e.build_candidate = build
    return e

def run(e, rt, obs, out):
    rid = out.name
    runtime = ROOT / "data/runtime" / rid
    gate1 = ROOT / "data/human_gate_decision_records/gate1" / rid
    gate2 = ROOT / "data/human_gate_decision_records/gate2" / rid
    dbroot = ROOT / "data/sqlite_tests" / rid
    for root in (runtime, gate1, dbroot): root.mkdir(parents=True, exist_ok=False)
    batch = e.BATCH_NORMAL
    assert sha((batch / "source/input.xlsx").read_bytes()) == "8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341"
    source_before = SCENES([batch])
    fixture = (ROOT / "data/decision_protocol_checks/task020r2_run_01/fixture_values.json").read_bytes()
    assert sha(fixture) == "6d8126aee3497a9c00cfee7493e2d04783e3284a61b911dd688bff29b433b337"
    g2fields = json.loads(fixture)["BASE2"]["submission"]

    def call(label, fn, *args, category="direct_public", **kwargs):
        before = copy.deepcopy(obs.counts)
        prior = obs.gate2, obs.screen_window, obs.crosscheck_window
        obs.crosscheck_window = label in ("crosscheck", "crosscheck_inspect")
        obs.gate2 = obs.screen_window = obs.crosscheck_window or label == "screen_inspect"
        try:
            error, value, cid = e.call_api(rt, label, fn, *args, **kwargs)
            e.API_RECORDS[-1].update(record_category=category, reasons=copy.deepcopy(getattr(error, "reasons", None)),
                actual_entry_deltas={key: obs.counts[key] - before.get(key, 0) for key in obs.counts})
            return error, copy.deepcopy(value), cid
        finally:
            obs.gate2, obs.screen_window, obs.crosscheck_window = prior

    def setup(tag, screen=True):
        leaf, scope = runtime / tag, gate1 / tag
        event = scope / "event_0001"
        error, _, _ = call("registry", rt.build_runtime_registry, batch, leaf, scope_dir=scope)
        if error: raise error
        error, request, _ = call("g1_prepare", rt.prepare_runtime_gate1_request, batch, leaf, "FIXTURE-REQ-G1-0001")
        if error: raise error
        materials = request["request"]["materials"]
        sub = e.submission_for(e.APPROVE_FIELDS, materials["materials_fingerprint"], "FIXTURE-REQ-G1-0001", materials["batch_id"])
        error, record1, _ = call("g1_save", rt.save_runtime_gate1_decision, batch, leaf, "FIXTURE-REQ-G1-0001", sub, event, scope_dir=scope)
        if error: raise error
        params = dict(scope_dir=scope, event_relative=event.relative_to(ROOT).as_posix(), database_path=dbroot / tag / "runtime.sqlite3")
        error, _, _ = call("load", rt.run_gate1_approved_load, batch, leaf, **params)
        if error: raise error
        error, request2, _ = call("g2_prepare", rt.prepare_runtime_gate2_request, batch, leaf, "FIXTURE-REQ-G2-0001", **params)
        if error: raise error
        sub2 = copy.deepcopy(g2fields)
        sub2["batch_id"] = materials["batch_id"]
        sub2["request_binding"] = {"request_id": "FIXTURE-REQ-G2-0001", "materials_binding": request2["request"]["materials"]["materials_fingerprint"]}
        sub2["prior_decision_binding"] = {"wrapper_version": rt.GATE2_WRAPPER_VERSION, "record": record1["record"], "record_fingerprint": record1["record_fingerprint"]}
        event2 = gate2 / tag / "event_0001"
        error, _, _ = call("g2_save", rt.save_runtime_gate2_decision, batch, leaf, "FIXTURE-REQ-G2-0001", sub2, event2, **params)
        if error: raise error
        params["gate2_event_relative"] = event2.relative_to(ROOT).as_posix()
        scene = dict(leaf=leaf, scope=scope, event2=event2, params=params,
                     screen=leaf.with_name(tag + ".screen"), output=leaf.with_name(tag + ".crosscheck"))
        if screen:
            error, _, _ = call("screen", rt.run_gate2_approved_screen, batch, leaf, **params)
            if error: raise error
        return scene

    def crosscheck(scene, **overrides):
        return call("crosscheck", rt.run_gate2_rule_crosscheck, batch, scene["leaf"], **dict(scene["params"], **overrides))
    def inspect(scene):
        return call("crosscheck_inspect", rt.inspect_gate2_rule_crosscheck, batch, scene["leaf"], **scene["params"])
    def sources(scene):
        return SCENES([batch, scene["leaf"], scene["scope"], scene["event2"], scene["screen"],
            scene["leaf"].with_name(scene["leaf"].name + ".load"), scene["params"]["database_path"].parent])
    def delta(): return e.API_RECORDS[-1]["actual_entry_deltas"]

    normal = setup("normal", screen=False)
    error, _, cid = crosscheck(normal)
    e.check("G1.missing_screen", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "screen_dir" and
        delta()["crosscheck"] == 0 and not normal["output"].exists(), {"call_id": cid, "field": getattr(error, "field", None)})
    error, _, _ = call("screen", rt.run_gate2_approved_screen, batch, normal["leaf"], **normal["params"])
    if error: raise error
    before = sources(normal)
    error, _, cid = crosscheck(normal, gate2_event_relative=normal["params"]["gate2_event_relative"].replace("event_0001", "event_0002"))
    e.check("G1.wrong_gate2", isinstance(error, rt.RuntimeGate1Blocked) and delta()["crosscheck"] == 0 and not normal["output"].exists(), {"call_id": cid})
    database = normal["params"]["database_path"]
    raw_db = database.read_bytes();(out / "database.original.bin").write_bytes(raw_db)
    real_screen_inspect, hit = rt.inspect_gate2_approved_screen, [0]
    def inspected_then_change(*args, **kwargs):
        returned = real_screen_inspect(*args, **kwargs);hit[0] += 1
        database.write_bytes(raw_db + b"\n")
        return returned
    rt.inspect_gate2_approved_screen = inspected_then_change
    try: error, _, cid = crosscheck(normal)
    finally: rt.inspect_gate2_approved_screen = real_screen_inspect
    (out / "database.before_core.bad.bin").write_bytes(database.read_bytes());database.write_bytes(raw_db)
    e.check("G3.pre_core_change", isinstance(error, rt.RuntimeGate1Blocked) and hit == [1] and delta()["crosscheck"] == 0 and
        not normal["output"].exists(), {"call_id": cid, "hit": hit[0], "field": getattr(error, "field", None)})
    error, recorded, run_id = crosscheck(normal)
    if error: raise error
    semantics, real_eq = [], rt._require_equivalent_030
    def observe(value, expected, field):
        result = real_eq(value, expected, field);semantics.append(field);return result
    rt._require_equivalent_030 = observe
    hits = []
    try:
        with PREVIOUS.PREVIOUS.PREVIOUS.readonly_guard(hits): error, restored, inspect_id = inspect(normal)
    finally: rt._require_equivalent_030 = real_eq
    report_path = normal["output"] / "crosscheck_report.json"
    artifact_path = normal["output"] / "artifacts.json"
    report_raw, artifact_raw = report_path.read_bytes(), artifact_path.read_bytes()
    (out / "report.original.bin").write_bytes(report_raw);(out / "artifacts.original.bin").write_bytes(artifact_raw)
    report = json.loads(report_raw)
    core_record = next(item for item in e.CORE_RECORDS if item["core"] == "crosscheck" and item["caller_api"] == run_id)
    e.check("G1.normal", error is None and not hits and canon(recorded) == canon(restored) and len(recorded) == 6 and
        len(recorded["artifacts"]) == 15 and len(recorded["boundaries"]) == 7 and all(v is False for v in recorded["boundaries"].values()) and
        before == sources(normal) and len(list(normal["output"].iterdir())) == 3,
        {"run": run_id, "inspect": inspect_id, "readonly_hits": hits})
    e.check("G1.true_core_and_facts", canon(core_record["return"]) + b"\n" == report_raw and
        core_record["input_refs_before"] == core_record["input_refs_after"] == core_record["input_refs_api_end"] and
        report["matched"] is True and len(report["comparison"]["matched_dimensions"]) == 10 and not report["differences"] and
        report["rule_recomputed_counts"] == {"R01":0,"R02":1,"R03":0,"R04":0,"total":1} and
        report["recomputed_facts"]["statistics"]["r02_overpayment_total_cents"] == 400000,
        {"call_id": run_id, "crosscheck_entry_delta": next(x for x in e.API_RECORDS if x["call_id"] == run_id)["actual_entry_deltas"]["crosscheck"]})
    error, _, cid = crosscheck(normal)
    e.check("G1.repeat", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "crosscheck_dir" and delta()["crosscheck"] == 0, {"call_id": cid})
    last_field, hit = semantics[-1], [0]
    def change_after_last(value, expected, field):
        result = real_eq(value, expected, field)
        if field == last_field:
            hit[0] += 1;report_path.write_bytes(report_raw + b"\n")
        return result
    rt._require_equivalent_030 = change_after_last
    try: error, _, cid = inspect(normal)
    finally: rt._require_equivalent_030 = real_eq
    e.check("G3.inspect_late", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "crosscheck.crosscheck_report.json" and
        hit == [1] and not (normal["output"] / "failure.json").exists(), {"call_id": cid,"hit":hit[0],"last_semantic_field":last_field})
    (out / "report.late.bad.bin").write_bytes(report_path.read_bytes())
    retained, _, retained_id = inspect(normal)
    report_path.write_bytes(report_raw)
    clean, _, clean_id = inspect(normal)
    e.check("G3.retained_and_restored", retained is not None and clean is None and before == sources(normal), {"retained":retained_id,"restored":clean_id})

    protocol_controls = (
        ("executed_bool", lambda v: v["comparison"]["dimensions"]["source_rows"].update(executed=1), "crosscheck.report.comparison.dimensions.source_rows.executed"),
        ("count_float", lambda v: v["rule_recomputed_counts"].update(R02=1.0), "crosscheck.report.rule_recomputed_counts.R02"),
        ("dimension_list", lambda v: v["comparison"]["matched_dimensions"].pop(), "crosscheck.report.comparison.matched_dimensions"))
    for label, mutate, expected_field in protocol_controls:
        candidate = json.loads(report_raw);mutate(candidate);raw = canon(candidate) + b"\n"
        report_path.write_bytes(raw)
        artifacts = json.loads(artifact_raw);artifacts.update(report_file_sha256=sha(raw), report_canonical_sha256=sha(canon(candidate)))
        artifact_path.write_bytes(canon(artifacts) + b"\n")
        error, _, cid = inspect(normal)
        (out / (label + ".report.bad.bin")).write_bytes(raw)
        (out / (label + ".artifacts.bad.bin")).write_bytes(artifact_path.read_bytes())
        report_path.write_bytes(report_raw);artifact_path.write_bytes(artifact_raw)
        e.check("G1.protocol_" + label, isinstance(error, rt.RuntimeGate1Blocked) and error.field == expected_field and
            not (normal["output"] / "failure.json").exists(), {"call_id":cid,"field":getattr(error,"field",None)})

    mismatch = setup("mismatch")
    screen_path, screen_artifact = mismatch["screen"] / "screening_report.json", mismatch["screen"] / "artifacts.json"
    sr, sa = screen_path.read_bytes(), screen_artifact.read_bytes()
    (out / "mismatch.screen.original.bin").write_bytes(sr);(out / "mismatch.artifacts.original.bin").write_bytes(sa)
    candidate = json.loads(sr);row_map = candidate["findings"][0]["source_rows"]["payables"]
    row_id = sorted(row_map)[0];old_row = row_map[row_id];row_map[row_id] = old_row + 1
    changed = canon(candidate) + b"\n";screen_path.write_bytes(changed)
    artifacts = json.loads(sa);artifacts.update(report_file_sha256=sha(changed),report_canonical_sha256=sha(canon(candidate)))
    screen_artifact.write_bytes(canon(artifacts) + b"\n")
    snapshot = sources(mismatch)
    error, _, prerequisite_id = call("screen_inspect", rt.inspect_gate2_approved_screen, batch, mismatch["leaf"], **mismatch["params"])
    if error: raise error
    error, _, cid = crosscheck(mismatch)
    actual = next(item for item in e.CORE_RECORDS if item["core"] == "crosscheck" and item["caller_api"] == cid)
    saved_report = (mismatch["output"] / "crosscheck_report.json").read_bytes()
    diagnostic = json.loads((mismatch["output"] / "failure.json").read_bytes())
    e.check("G2.true_mismatch", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "crosscheck.report.matched" and
        actual["return"]["matched"] is False and actual["return"]["differences"] and
        "source_rows" in actual["return"]["comparison"]["unmatched_dimensions"] and canon(actual["return"]) + b"\n" == saved_report and
        not (mismatch["output"] / "artifacts.json").exists() and diagnostic["kind"] == "BLOCKED" and snapshot == sources(mismatch),
        {"public_screen_inspect":prerequisite_id,"call_id":cid,"mutation_field":"findings[0].source_rows.payables."+row_id,
         "old_row":old_row,"new_row":old_row+1,"differences":actual["return"]["differences"]})
    snapshot2 = SCENES([mismatch["output"]]);error, _, cid = inspect(mismatch)
    e.check("G2.failure_persists", isinstance(error,rt.RuntimeGate1Blocked) and error.field.startswith("crosscheck.failure.") and
        snapshot2 == SCENES([mismatch["output"]]), {"call_id":cid})

    half_scene = setup("half_artifacts")
    real_open, half = builtins.open, {"hits":0}
    class HalfWriter:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): self.stream.__enter__();return self
        def __exit__(self,*args): return self.stream.__exit__(*args)
        def __getattr__(self,name): return getattr(self.stream,name)
        def write(self, data):
            length = len(data)//2;self.stream.write(data[:length]);self.stream.flush()
            half.update(hits=half["hits"]+1,mode="xb",expected=len(data),written=length)
            raise OSError("TASK032_REAL_ARTIFACTS_HALF_WRITE")
    def opened(path,mode="r",*args,**kwargs):
        stream = real_open(path,mode,*args,**kwargs)
        if isinstance(path,(str,Path)) and Path(path) == half_scene["output"] / "artifacts.json" and mode == "xb": return HalfWriter(stream)
        return stream
    builtins.open = opened
    try: error, _, cid = crosscheck(half_scene)
    finally: builtins.open = real_open
    diagnostic = json.loads((half_scene["output"] / "failure.json").read_bytes())
    e.check("G3.real_half_write", isinstance(error,rt.RuntimeGate1Error) and half["hits"]==1 and len(diagnostic)==6 and
        (half_scene["output"] / "artifacts.json").stat().st_size == half["written"] and
        any("OSError" in cause for cause in diagnostic["cause_chain"]), {"call_id":cid,"stage":getattr(error,"stage",None),"writer":half,"diagnostic":diagnostic})
    snapshot = SCENES([half_scene["output"]]);error, _, cid = inspect(half_scene)
    e.check("G3.half_failure_priority", isinstance(error,rt.RuntimeGate1Error) and error.stage.startswith("crosscheck.failure.") and
        snapshot == SCENES([half_scene["output"]]), {"call_id":cid})

    empty_leaf, empty_scope = runtime / "existing_empty", gate1 / "existing_empty"
    error, _, _ = call("registry",rt.build_runtime_registry,batch,empty_leaf,scope_dir=empty_scope)
    if error: raise error
    empty_output = empty_leaf.with_name("existing_empty.crosscheck");empty_output.mkdir()
    error, _, cid = call("crosscheck",rt.run_gate2_rule_crosscheck,batch,empty_leaf,**normal["params"])
    e.check("G1.existing_empty", isinstance(error,rt.RuntimeGate1Blocked) and error.field == "crosscheck_dir" and not list(empty_output.iterdir()), {"call_id":cid,"precondition_only":True})

    core = rt._load_frozen_crosscheck_032();real = core.verify_rule_facts
    for cls, mapped in ((core.CrossCheckBlocked,rt.RuntimeGate1Blocked),(core.CrossCheckError,rt.RuntimeGate1Error)):
        reasons, hit = ["controlled reason 1","controlled reason 2"], [0]
        def controlled(*args,**kwargs): hit[0]+=1;raise cls("TASK032_CONTROLLED_MAPPING",reasons)
        core.verify_rule_facts = controlled
        try:
            error, _, cid = call("mapping_helper",rt._call_frozen_entry,core,"verify_rule_facts",{}, {},category="helper_control")
        finally: core.verify_rule_facts = real
        e.check("G3.mapping_"+cls.__name__, isinstance(error,mapped) and isinstance(error.__cause__,cls) and error.reasons==reasons and hit==[1],
                {"call_id":cid,"hit":hit[0],"scope":"controlled actual class mapping; no real crosscheck entry"})
    windows = [item for item in e.API_RECORDS if item["operation"] in ("crosscheck","crosscheck_inspect")]
    e.check("G4.forbidden_entries", not obs.guard_hits and all(all(item["actual_entry_deltas"].get(k,0)==0 for k in
        ("normalizer","loader","store_save","screen")) for item in windows) and
        all(item["actual_entry_deltas"]["crosscheck"]==0 for item in windows if item["operation"]=="crosscheck_inspect"),
        {"window_calls":len(windows),"guard_hits":obs.guard_hits})
    key_map = {"inspect":"inspect_gate1_approved_load","gate1_verify":"verify_gate1_effective_approval","screen_inspect":"inspect_gate2_approved_screen"}
    counts = {name:{"entries":count,"profile":obs.counts[key_map.get(name,name)]} for name,count in obs.nested.items()}
    e.check("G4.count_closure",all(v["entries"]==v["profile"] for v in counts.values()),counts)
    e.check("G4.source_unchanged", source_before==SCENES([batch]))
    return {"fixture_label":"PROTOCOL_TEST_FIXTURE_ONLY","fixture_sha256":sha(fixture),"counts":counts,"new_receiver_calls":0,
        "not_executed":{name:{"count":None,"reason":"outside TASK-032; not reported as guarded zero"} for name in
            ("facts","human_initial_judgment","AI","new_junction","historical_suites")}}

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument("--out-dir",required=True);parser.add_argument("--replay")
    parser.add_argument("--mutate",choices=("none","candidate-return","ledger-late","checks-late"),default="none")
    args=parser.parse_args(argv);out=Path(args.out_dir).resolve()
    if not out.is_relative_to(TEST_ROOT.resolve()) or out==TEST_ROOT.resolve() or out.exists() or not out.name.startswith("task032_"):
        raise SystemExit("out-dir must be never-existing task032_ strict descendant")
    e=evidence_module();e.ROUND["id"]=out.name;out.mkdir(parents=True,exist_ok=False);obs=None
    if args.replay:
        source=Path(args.replay).resolve()
        if not source.is_relative_to(TEST_ROOT.resolve()) or source==out: raise SystemExit("invalid replay source")
        checkpoint=json.loads((source/"expected_observations.json").read_bytes())
        extra={"replay_only":True,"new_business_calls":0,"source":str(source)}
    else:
        if args.mutate!="none": raise SystemExit("mutations require replay")
        rt=load(ROOT/"scripts/runtime_gate1.py","task032_runtime_under_test");obs=Observer(rt,e);sys.setprofile(obs.profile)
        try: extra=run(e,rt,obs,out)
        finally: sys.setprofile(None)
        checkpoint=e.freeze_expectations()
    original_read,injection=Path.read_bytes,{"hits":0}
    if args.mutate in ("ledger-late","checks-late"):
        def read_then_mutate(path):
            result=original_read(path);frame=sys._getframe(1)
            if frame.f_code is e.finish.__code__ and "terminal_buffers" in frame.f_locals and path==out/"expected_observations.json" and not injection["hits"]:
                target=out/("file_ledger.json" if args.mutate=="ledger-late" else "checks.json");before=original_read(target)
                with open(target,"ab") as stream: stream.write(b"\n")
                injection.update(hits=1,target=target.name,before_size=len(before),after_size=len(before)+1,
                    before_sha256=sha(before),after_sha256=sha(before+b"\n"),boundary="after_semantic_ledger_consumption_in_terminal_byte_loop")
            return result
        Path.read_bytes=read_then_mutate
    try: code=e.finish(out,checkpoint,"candidate-return" if args.mutate=="candidate-return" else "none",obs,extra)
    finally: Path.read_bytes=original_read
    if args.mutate in ("ledger-late","checks-late"):
        (out/"control_observation.json").write_bytes(canon(injection)+b"\n")
    return code

if __name__=="__main__": raise SystemExit(main())
