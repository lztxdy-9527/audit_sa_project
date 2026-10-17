#!/usr/bin/env python
"""TASK-030 targeted Gate2 persistence tests; accepted short closure is reused read-only."""
from __future__ import annotations
import argparse
import builtins
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_gate2_decision_tests"


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PREVIOUS = load(ROOT / "tests/test_runtime_gate2_request.py", "task030_readonly_helpers")


class Observer(PREVIOUS.Observations):
    def __init__(self, rt, evidence):
        super().__init__(rt, evidence)
        for name in ("save_runtime_gate2_decision", "verify_runtime_gate2_decision"):
            self.codes[getattr(rt, name).__code__] = name
            self.counts[name] = self.api[name] = 0

    def wrap(self, module, name, label, forbidden=False):
        super().wrap(module, name, label, forbidden=label in ("normalizer", "loader"))
        if label != "p1":
            return
        spy = getattr(module, name)
        def observed(*args, **kwargs):
            frame = sys._getframe(1)
            owner = None
            while frame:
                code_label = self.codes.get(frame.f_code)
                if code_label in ("store_save", "store_verify"):
                    owner = code_label
                    break
                frame = frame.f_back
            before = len(self.e.CORE_RECORDS)
            try:
                return spy(*args, **kwargs)
            finally:
                for rec in self.e.CORE_RECORDS[before:]:
                    if rec["core"] == "p1":
                        rec["within_store_operation"] = owner
        setattr(module, name, observed)


def evidence_module():
    evidence = PREVIOUS.configure_evidence()
    original = evidence.build_candidate
    def build(*args, **kwargs):
        candidate = original(*args, **kwargs)
        candidate["summary"]["task"] = "TASK-030"
        return candidate
    evidence.build_candidate = build
    return evidence


def run(e, rt, obs, out):
    rid = out.name
    runtime = ROOT / "data/runtime" / rid
    gate1 = ROOT / "data/human_gate_decision_records/gate1" / rid
    gate2 = ROOT / "data/human_gate_decision_records/gate2" / rid
    dbroot = ROOT / "data/sqlite_tests" / rid
    for root in (runtime, gate1, dbroot):
        root.mkdir(parents=True, exist_ok=False)
    batch = e.BATCH_NORMAL
    fixture = ROOT / "data/decision_protocol_checks/task020r2_run_01/fixture_values.json"
    raw = fixture.read_bytes()
    assert len(raw) == 35465 and sha(raw) == "6d8126aee3497a9c00cfee7493e2d04783e3284a61b911dd688bff29b433b337"
    g2fields = json.loads(raw)["BASE2"]["submission"]
    holdraw = e.HOLD_FIXTURE.read_bytes()
    assert sha(holdraw) == "8e3cf5670e91f3c48776360ab8fc22b6fef3f9bce76f56d3793804142b5cd4fa"
    baseline_source = PREVIOUS.scene_bytes([batch])

    def call(label, fn, *args, **kwargs):
        before = copy.deepcopy(obs.counts)
        window = obs.gate2
        obs.gate2 = label in ("g2_prepare", "g2_save", "g2_verify")
        try:
            error, result, cid = e.call_api(rt, label, fn, *args, **kwargs)
            delta = {k: obs.counts[k] - before.get(k, 0) for k in obs.counts}
            e.API_RECORDS[-1]["actual_entry_deltas"] = delta
            return error, copy.deepcopy(result), cid
        finally:
            obs.gate2 = window

    def setup(tag):
        leaf, scope = runtime / tag, gate1 / tag
        error, _, _ = call("registry", rt.build_runtime_registry, batch, leaf, scope_dir=scope)
        if error:
            raise error
        error, prepared, _ = call("g1_prepare", rt.prepare_runtime_gate1_request,
                                  batch, leaf, "FIXTURE-REQ-G1-0001")
        if error:
            raise error
        material = prepared["request"]["materials"]
        sub = e.submission_for(e.APPROVE_FIELDS, material["materials_fingerprint"],
                               "FIXTURE-REQ-G1-0001", material["batch_id"])
        event = scope / "event_0001"
        error, saved, _ = call("g1_save", rt.save_runtime_gate1_decision, batch, leaf,
                               "FIXTURE-REQ-G1-0001", sub, event, scope_dir=scope)
        if error:
            raise error
        database = dbroot / tag / "runtime.sqlite3"
        args = {"scope_dir": scope, "event_relative": event.relative_to(ROOT).as_posix(),
                "database_path": database}
        error, _, _ = call("load", rt.run_gate1_approved_load, batch, leaf, **args)
        if error:
            raise error
        error, prepared2, _ = call("g2_prepare", rt.prepare_runtime_gate2_request,
                                   batch, leaf, "FIXTURE-REQ-G2-0001", **args)
        if error:
            raise error
        return {"leaf": leaf, "scope": scope, "event": event, "database": database,
                "args": args, "saved1": saved, "request": prepared2["request"],
                "event2": gate2 / tag / "event_0001", "tag": tag}

    def submission(scene, hold=False):
        value = copy.deepcopy(g2fields)
        if hold:
            fragment = json.loads(holdraw)["fragment"]
            for name in ("event_id", "decision", "actor", "decided_at_raw", "reason", "decision_source"):
                value[name] = copy.deepcopy(fragment[name])
        value["batch_id"] = scene["request"]["materials"]["batch_id"]
        value["request_binding"] = {"request_id": "FIXTURE-REQ-G2-0001",
            "materials_binding": scene["request"]["materials"]["materials_fingerprint"]}
        value["prior_decision_binding"] = {"wrapper_version": rt.GATE2_WRAPPER_VERSION,
            "record_fingerprint": scene["saved1"]["record_fingerprint"],
            "record": copy.deepcopy(scene["saved1"]["record"])}
        return value

    def save(scene, sub=None, target=None):
        return call("g2_save", rt.save_runtime_gate2_decision, batch, scene["leaf"],
                    "FIXTURE-REQ-G2-0001", sub if sub is not None else submission(scene),
                    target if target is not None else scene["event2"], **scene["args"])

    def verify(scene):
        return call("g2_verify", rt.verify_runtime_gate2_decision, batch, scene["leaf"],
                    gate2_event_relative=scene["event2"].relative_to(ROOT).as_posix(), **scene["args"])

    def source_scene(scene):
        return PREVIOUS.scene_bytes([batch, scene["leaf"], scene["scope"],
            scene["leaf"].with_name(scene["leaf"].name + ".load"), scene["database"].parent])

    normal = setup("normal")
    original_sources = source_scene(normal)
    for label, sub, target in (
            ("G2.material", {**submission(normal), "request_binding": {
                "request_id": "FIXTURE-REQ-G2-0001", "materials_binding": "0" * 64}}, None),
            ("G2.prior", {**submission(normal), "prior_decision_binding": "APPROVE"}, None),
            ("G2.path", submission(normal), normal["event2"].with_name("event_0002"))):
        error, _, cid = save(normal, sub, target)
        entry = e.API_RECORDS[-1]
        e.check(label, isinstance(error, rt.RuntimeGate1Blocked) and
                entry["actual_entry_deltas"]["store_save"] == 0 and
                not normal["event2"].exists(), {"call_id": cid, "field": getattr(error, "field", None)})
    forged = submission(normal)
    forged["prior_decision_binding"]["record"]["reason"] += "candidate altered"
    forged["prior_decision_binding"]["record_fingerprint"] = sha(canon(forged["prior_decision_binding"]["record"]))
    error, _, cid = save(normal, forged)
    e.check("G2.forged_complete_prior", isinstance(error, rt.RuntimeGate1Blocked) and
            error.field == "submission.prior_decision_binding" and
            e.API_RECORDS[-1]["actual_entry_deltas"]["store_save"] == 0, {"call_id": cid})

    lock_leaf, lock_g1 = runtime / "existing_lock", gate1 / "existing_lock"
    error, _, _ = call("registry", rt.build_runtime_registry, batch, lock_leaf, scope_dir=lock_g1)
    if error:
        raise error
    lock = lock_leaf.with_name(lock_leaf.name + ".gate2.lock")
    lock.mkdir()
    original_lock = b"PROTOCOL_TEST_FIXTURE_ONLY existing lock\n"
    (lock / "lock.json").write_bytes(original_lock)
    error, _, cid = call("g2_save", rt.save_runtime_gate2_decision, batch, lock_leaf,
        "FIXTURE-REQ-G2-0001", submission(normal), gate2 / "existing_lock/event_0001", scope_dir=lock_g1,
        event_relative=(lock_g1 / "event_0001").relative_to(ROOT).as_posix(), database_path=normal["database"])
    e.check("G2.existing_lock", isinstance(error, rt.RuntimeGate1Blocked) and
            error.field == "gate2_lock" and (lock / "lock.json").read_bytes() == original_lock,
            {"call_id": cid, "precondition_layer_only": True})
    # Deliberately isolated lock stays at its original exact path; no removal/move/reuse.

    db_bytes = normal["database"].read_bytes()
    (out / "pre_store_database.original.bin").write_bytes(db_bytes)
    real_prepare = rt._prepare_runtime_gate2_captured
    hit = [0]
    def late_prepare(*args, **kwargs):
        returned = real_prepare(*args, **kwargs)
        hit[0] += 1
        normal["database"].write_bytes(db_bytes + b"\n")
        return returned
    rt._prepare_runtime_gate2_captured = late_prepare
    try:
        error, _, cid = save(normal)
    finally:
        rt._prepare_runtime_gate2_captured = real_prepare
    (out / "pre_store_database.bad.bin").write_bytes(normal["database"].read_bytes())
    normal["database"].write_bytes(db_bytes)
    e.check("G3.before_store", isinstance(error, rt.RuntimeGate1Blocked) and hit == [1] and
            e.API_RECORDS[-1]["actual_entry_deltas"]["store_save"] == 0 and
            not normal["event2"].exists(), {"call_id": cid, "field": getattr(error, "field", None), "hit": hit[0]})

    error, saved, saved_id = save(normal)
    if error:
        raise error
    guarded_hits = []
    semantic_fields = []
    real_equivalent = rt._require_equivalent_030
    def observed_equivalent(value, expected, field):
        returned = real_equivalent(value, expected, field)
        semantic_fields.append(field)
        return returned
    rt._require_equivalent_030 = observed_equivalent
    try:
        with PREVIOUS.readonly_guard(guarded_hits):
            error, restored, restored_id = verify(normal)
    finally:
        rt._require_equivalent_030 = real_equivalent
    e.check("G1.save_verify", error is None and canon(saved) == canon(restored) and len(saved) == 3 and
            len(saved["record"]) == 17 and source_scene(normal) == original_sources and not guarded_hits,
            {"save_call": saved_id, "verify_call": restored_id, "guard_hits": guarded_hits})
    resultpath = normal["event2"] / "snapshots/decision_result.json"
    persisted = json.loads(resultpath.read_bytes())
    entry = next(r for r in e.API_RECORDS if r["call_id"] == saved_id)
    p1_new = [r for r in e.CORE_RECORDS if r["caller_api"] == saved_id and r["core"] == "p1"
              and r["within_store_operation"] == "store_save"]
    contextpath, receiptpath = normal["event2"] / "context.json", normal["event2"] / "receipt.json"
    context = json.loads(contextpath.read_bytes())
    receipt = json.loads(receiptpath.read_bytes())
    actual_files = sorted(p.relative_to(normal["event2"]).as_posix()
                          for p in normal["event2"].glob("*") if p.is_file()) + sorted(
                          p.relative_to(normal["event2"]).as_posix() for p in (normal["event2"] / "snapshots").iterdir())
    e.check("G1.real_core_and_history", len(p1_new) == 1 and canon(p1_new[0]["return"]) == canon(persisted) and
            len(context) == 14 and len(receipt) == 9 and len(actual_files) == 8 and
            canon(context["prior_history"]["records"][0]) == canon(submission(normal)["prior_decision_binding"]) and
            context["prior_history"]["declared_scope"] ==
            f"GATE2_SCOPE:{normal['event2'].parent.relative_to(ROOT).as_posix()}|BOUND_GATE1:{normal['args']['event_relative']}" and
            context["request"]["boundaries"]["request_persisted"] is False and
            all(v is False for v in saved["record"]["boundaries"].values()) and
            all(v is False for v in context["boundaries"].values()), {"new_P1_count": len(p1_new), "files": actual_files})
    # Independent actual byte map, not production helper output.
    paths = {"registry/runtime_registry.json": normal["leaf"] / "runtime_registry.json",
        "registry/runtime_registry_readback.json": normal["leaf"] / "runtime_registry_readback.json",
        "gate1/decision_result.json": normal["event"] / "snapshots/decision_result.json",
        "source/batch_manifest.json": batch / "batch_manifest.json",
        "source/quality_report.json": batch / "checks/quality_report.json",
        "sqlite/runtime.sqlite3": normal["database"]}
    for rel, name in (("load/started.json", "started.json"), ("normalized/normalized.json", "normalized.json"),
                      ("load/load_report.json", "load_report.json"), ("load/artifacts.json", "artifacts.json")):
        paths[rel] = normal["leaf"].with_name("normal.load") / name
    independent = []
    for rel, path in sorted(paths.items(), key=lambda p: p[0].encode()):
        data = path.read_bytes()
        independent.append({"relative": rel, "byte_size": len(data), "file_sha256": sha(data)})
    e.check("G1.ten_materials", canon(independent) == canon(context["request"]["materials"]["files"]))
    error, _, cid = save(normal)
    e.check("G2.second_event", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "gate2_scope",
            {"call_id": cid})

    # Canonical key order control and a self-consistent outer receipt with wrong inner identity.
    originals = {p: p.read_bytes() for p in (contextpath, receiptpath)}
    for p, data in originals.items():
        (out / (p.name + ".original.bin")).write_bytes(data)
    def write_context_receipt(value):
        data = canon(value) + b"\n"
        contextpath.write_bytes(data)
        changed_receipt = json.loads(originals[receiptpath])
        changed_receipt["context_file_sha256"] = sha(data)
        receiptpath.write_bytes(canon(changed_receipt) + b"\n")
    bad = copy.deepcopy(context)
    bad["gate1_event_relative"] = "OTHER"
    write_context_receipt(bad)
    before = PREVIOUS.scene_bytes([normal["event2"]])
    error, _, cid = verify(normal)
    e.check("G2.inner_binding", isinstance(error, rt.RuntimeGate1Blocked) and
            error.field == "gate2.context.gate1_event_relative" and before == PREVIOUS.scene_bytes([normal["event2"]]),
            {"call_id": cid, "field": getattr(error, "field", None)})
    (out / "inner_binding.context.bad.bin").write_bytes(contextpath.read_bytes())
    (out / "inner_binding.receipt.bad.bin").write_bytes(receiptpath.read_bytes())
    for p, data in originals.items():
        p.write_bytes(data)
    reordered = json.dumps(dict(reversed(list(context.items()))), ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
    contextpath.write_bytes(reordered)
    adjusted = json.loads(originals[receiptpath]); adjusted["context_file_sha256"] = sha(reordered)
    receiptpath.write_bytes(canon(adjusted) + b"\n")
    (out / "key_order.context.candidate.bin").write_bytes(contextpath.read_bytes())
    (out / "key_order.receipt.candidate.bin").write_bytes(receiptpath.read_bytes())
    error, _, cid = verify(normal)
    e.check("G2.key_order", error is None, {"call_id": cid})
    for p, data in originals.items():
        p.write_bytes(data)

    hit = [0]
    last_semantic_field = semantic_fields[-1]
    def late_equivalent(value, expected, field):
        returned = real_equivalent(value, expected, field)
        if field == last_semantic_field:
            hit[0] += 1
            contextpath.write_bytes(originals[contextpath] + b"\n")
        return returned
    rt._require_equivalent_030 = late_equivalent
    try:
        error, _, cid = verify(normal)
    finally:
        rt._require_equivalent_030 = real_equivalent
    (out / "verify_late_context.bad.bin").write_bytes(contextpath.read_bytes())
    e.check("G3.verify_late", isinstance(error, rt.RuntimeGate1Blocked) and
            error.field == "gate2.context.json" and hit == [1] and not (normal["event2"] / "failure.json").exists(),
            {"call_id": cid, "field": getattr(error, "field", None), "hit": hit[0],
             "observed_last_semantic_field": last_semantic_field})
    contextpath.write_bytes(originals[contextpath])
    error, _, cid = verify(normal)
    e.check("G3.verify_restored", error is None and source_scene(normal) == original_sources, {"call_id": cid})

    hold = setup("hold")
    error, saved_hold, cid = save(hold, submission(hold, hold=True))
    error2, verified_hold, cid2 = verify(hold) if error is None else (error, None, None)
    e.check("G1.hold", error is None and error2 is None and saved_hold["record"]["decision"] == "HOLD"
            and canon(saved_hold) == canon(verified_hold) and saved_hold["record"]["execution_allowed"] is False,
            {"save": cid, "verify": cid2})

    blank = setup("blank_reason")
    blank_sub = submission(blank); blank_sub["reason"] = " "
    error, _, cid = save(blank, blank_sub)
    diag = json.loads((blank["event2"] / "failure.json").read_bytes())
    e.check("G2.real_p1_rejection", isinstance(error, rt.RuntimeGate1Blocked) and
            error.field == "store.submission.reason" and len(diag) == 5 and
            e.API_RECORDS[-1]["actual_entry_deltas"]["store_save"] == 1,
            {"call_id": cid, "field": getattr(error, "field", None), "diagnostic": diag})

    empty_scope = gate2 / "empty_scope"
    empty_scope.mkdir(parents=True)
    # Early path precondition uses an independent registry plan; no unnecessary computation.
    empty_leaf, empty_g1 = runtime / "empty_scope", gate1 / "empty_scope"
    error, _, _ = call("registry", rt.build_runtime_registry, batch, empty_leaf, scope_dir=empty_g1)
    error, _, cid = call("g2_save", rt.save_runtime_gate2_decision, batch, empty_leaf,
        "FIXTURE-REQ-G2-0001", submission(normal), empty_scope / "event_0001", scope_dir=empty_g1,
        event_relative=(empty_g1 / "event_0001").relative_to(ROOT).as_posix(), database_path=normal["database"])
    e.check("G2.existing_empty_scope", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "gate2_scope"
            and not list(empty_scope.iterdir()), {"call_id": cid, "precondition_layer_only": True})

    tampered = setup("store_tamper")
    store = rt._load_frozen_store()
    real_save = store.save_human_gate_decision_snapshots
    hit = [0]
    def altered_store(*args, **kwargs):
        result = real_save(*args, **kwargs)
        target = tampered["event2"] / "snapshots/submission.json"
        target.write_bytes(target.read_bytes() + b"\n")
        manifest_path = target.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        for item in manifest["payloads"]:
            if item["relative"] == "submission.json":
                item["byte_size"] = target.stat().st_size
                item["file_sha256"] = sha(target.read_bytes())
        manifest_path.write_bytes(canon(manifest) + b"\n")
        hit[0] += 1
        return result
    store.save_human_gate_decision_snapshots = altered_store
    try:
        error, _, cid = save(tampered)
    finally:
        store.save_human_gate_decision_snapshots = real_save
    e.check("G3.store_return_binding", isinstance(error, rt.RuntimeGate1Blocked) and
            error.field == "store_result.manifest_file_sha256" and hit == [1],
            {"call_id": cid, "field": getattr(error, "field", None), "hit": hit[0]})

    partial = setup("partial_context")
    real_open = builtins.open
    half = {"hits": 0}
    class HalfWriter:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): self.stream.__enter__(); return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def __getattr__(self, name): return getattr(self.stream, name)
        def write(self, data):
            size = len(data) // 2
            self.stream.write(data[:size]); self.stream.flush()
            half.update(hits=half["hits"] + 1, mode="xb", expected=len(data), written=size)
            raise OSError("TASK030_REAL_CONTEXT_HALF_WRITE")
    def half_open(path, mode="r", *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        if Path(path) == partial["event2"] / "context.json" and mode == "xb":
            return HalfWriter(stream)
        return stream
    builtins.open = half_open
    try:
        error, _, cid = save(partial)
    finally:
        builtins.open = real_open
    diag = json.loads((partial["event2"] / "failure.json").read_bytes())
    e.check("G3.context_half_write", isinstance(error, rt.RuntimeGate1Error) and
            half["hits"] == 1 and (partial["event2"] / "context.json").stat().st_size == half["written"] and
            any("OSError" in value for value in diag["cause_chain"]),
            {"call_id": cid, "stage": getattr(error, "stage", None), "writer": half, "diagnostic": diag})

    sentinel = setup("receipt_sentinel")
    real_writer = rt._write_exclusive
    hit = [0]
    class ReceiptSentinel(RuntimeError): pass
    def written_then_throw(path, buffer, stage):
        result = real_writer(path, buffer, stage)
        if path == sentinel["event2"] / "receipt.json":
            hit[0] += 1
            assert path.read_bytes() == buffer
            raise ReceiptSentinel("TASK030_COMPLETE_RECEIPT_WRITTEN")
        return result
    rt._write_exclusive = written_then_throw
    try:
        error, _, cid = save(sentinel)
    finally:
        rt._write_exclusive = real_writer
    diag = json.loads((sentinel["event2"] / "failure.json").read_bytes())
    e.check("G3.receipt_sentinel", isinstance(error, rt.RuntimeGate1Error) and hit == [1] and
            any("ReceiptSentinel" in value for value in diag["cause_chain"]),
            {"call_id": cid, "stage": getattr(error, "stage", None), "hit": hit[0], "diagnostic": diag})
    failure_before = PREVIOUS.scene_bytes([sentinel["event2"]])
    error, _, cid = verify(sentinel)
    e.check("G3.failure_readonly", isinstance(error, rt.RuntimeGate1Blocked) and
            error.field == "gate2.failure" and failure_before == PREVIOUS.scene_bytes([sentinel["event2"]]),
            {"call_id": cid})

    scoped = [r for r in e.API_RECORDS if r["operation"] in ("g2_prepare", "g2_save", "g2_verify")]
    e.check("G4.no_computation", all(all(r["actual_entry_deltas"].get(k, 0) == 0
            for k in ("normalizer", "loader")) for r in scoped) and not obs.guard_hits,
            {"window_calls": len(scoped), "guard_hits": obs.guard_hits})
    counts = {label: {"entries": total, "profile": obs.counts.get(
        {"inspect": "inspect_gate1_approved_load", "gate1_verify": "verify_gate1_effective_approval"}.get(label, label), 0)}
        for label, total in obs.nested.items()}
    e.check("G4.profile_closure", all(x["entries"] == x["profile"] for x in counts.values()), counts)
    e.check("G4.source_unchanged", baseline_source == PREVIOUS.scene_bytes([batch]))
    return {"fixture_label": "PROTOCOL_TEST_FIXTURE_ONLY", "fixture_file_sha256": sha(raw),
            "HOLD_fixture_sha256": sha(holdraw), "nested_counts": counts,
            "source_receiver_reused_not_rerun": True,
            "not_executed": {name: {"count": None, "reason": "outside TASK-030 scope"}
                for name in ("screening", "execution_release", "AI", "initial_judgment", "new_junction", "historical_suites")}}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--replay")
    parser.add_argument("--mutate", choices=("none", "candidate-return", "ledger-late", "checks-late"), default="none")
    args = parser.parse_args(argv)
    out = Path(args.out_dir).resolve()
    if not out.is_relative_to(TEST_ROOT.resolve()) or out == TEST_ROOT.resolve() or out.exists() or not out.name.startswith("task030_"):
        raise SystemExit("out-dir must be a never-existing task030_ strict descendant")
    e = evidence_module()
    e.ROUND["id"] = out.name
    out.mkdir(parents=True, exist_ok=False)
    obs = None
    if args.replay:
        source = Path(args.replay).resolve()
        if not source.is_relative_to(TEST_ROOT.resolve()) or source == out:
            raise SystemExit("invalid replay source")
        checkpoint = json.loads((source / "expected_observations.json").read_bytes())
        extra = {"replay_only": True, "new_business_calls": 0, "source": str(source)}
    else:
        if args.mutate != "none": raise SystemExit("mutations require replay")
        rt = load(ROOT / "scripts/runtime_gate1.py", "task030_runtime_under_test")
        obs = Observer(rt, e)
        sys.setprofile(obs.profile)
        try:
            extra = run(e, rt, obs, out)
        finally:
            sys.setprofile(None)
        checkpoint = e.freeze_expectations()
    original_read, injection = Path.read_bytes, {"hits": 0}
    if args.mutate in ("ledger-late", "checks-late"):
        def read_then_mutate(path):
            result = original_read(path)
            frame = sys._getframe(1)
            if frame.f_code is e.finish.__code__ and "terminal_buffers" in frame.f_locals and path == out / "expected_observations.json" and not injection["hits"]:
                target = out / ("file_ledger.json" if args.mutate == "ledger-late" else "checks.json")
                before = original_read(target)
                with open(target, "ab") as stream: stream.write(b"\n")
                injection.update(hits=1, target=target.name, before_size=len(before), after_size=len(before)+1,
                    before_sha256=sha(before), after_sha256=sha(before+b"\n"),
                    boundary="after_semantic_ledger_consumption_in_terminal_byte_loop")
            return result
        Path.read_bytes = read_then_mutate
    try:
        code = e.finish(out, checkpoint, "candidate-return" if args.mutate == "candidate-return" else "none", obs, extra)
    finally:
        Path.read_bytes = original_read
    if args.mutate in ("ledger-late", "checks-late"):
        (out / "control_observation.json").write_bytes(canon(injection)+b"\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
