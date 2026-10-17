#!/usr/bin/env python
"""TASK-029 targeted tests. Reuse the accepted TASK-028 evidence closure, read-only."""
from __future__ import annotations

import argparse
import builtins
import copy
import hashlib
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_gate2_request_tests"
PUBLIC = ("build_runtime_registry", "read_runtime_registry", "prepare_runtime_gate1_request",
          "save_runtime_gate1_decision", "verify_gate1_effective_approval",
          "run_gate1_approved_load", "inspect_gate1_approved_load", "prepare_runtime_gate2_request")


def canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def scene_bytes(paths):
    """Only explicitly bounded scene roots/files, never the entire data/project tree."""
    out = {}
    def visit(path, depth):
        if path.is_file():
            data = path.read_bytes()
            out[str(path)] = {"byte_size": len(data), "file_sha256": sha(data)}
        elif path.is_dir():
            children = sorted(path.iterdir())
            if len(children) > 32:
                raise AssertionError(f"unbounded scene: {path}")
            out[str(path)] = {"members": [p.name for p in children]}
            if depth:
                for child in children:
                    visit(child, depth - 1)
        else:
            out[str(path)] = {"absent": True}
    for path in paths:
        visit(Path(path), 3)
    return out


class Observations:
    """Complete wrappers plus independent original-code profile counts, with API ownership."""
    def __init__(self, rt, evidence):
        self.e = evidence
        self.codes = {getattr(rt, name).__code__: name for name in PUBLIC}
        self.counts = {name: 0 for name in PUBLIC}
        self.api = {name: 0 for name in PUBLIC}
        self.normalizer = self.loader = 0
        self._other = {}
        self.gate2 = False
        self.guard_hits = []
        self.nested = {}
        self.serial = 0
        self.wrap(rt, "inspect_gate1_approved_load", "inspect")
        self.wrap(rt, "verify_gate1_effective_approval", "gate1_verify")
        self.wrap(rt._load_frozen_prepare(), "prepare_human_gate1_request", "frozen_prepare")
        store = rt._load_frozen_store()
        self.wrap(store, "save_human_gate_decision_snapshots", "store_save", forbidden=True)
        self.wrap(store, "verify_human_gate_decision_snapshots", "store_verify")
        self.wrap(store._core(), "build_human_gate_decision_record", "p1")
        self.wrap(rt._load_frozen_normalizer(), "normalize_workbook", "normalizer", forbidden=True)
        self.wrap(rt._load_frozen_sqlite_core(), "load_normalized_to_sqlite", "loader", forbidden=True)

    def profile(self, frame, event, arg):
        if event == "call" and frame.f_code in self.codes:
            name = self.codes[frame.f_code]
            self.counts[name] = self.counts.get(name, 0) + 1
            if name in self.api:
                self.api[name] += 1
            else:
                self._other[name] = self._other.get(name, 0) + 1
            if name == "normalizer":
                self.normalizer += 1
            if name == "loader":
                self.loader += 1
        return None

    def wrap(self, module, name, label, forbidden=False):
        real = getattr(module, name)
        self.codes.setdefault(real.__code__, label)
        self.counts.setdefault(label, 0)
        def observed(*args, **kwargs):
            if self.gate2 and forbidden:
                self.guard_hits.append(label)
                raise AssertionError(f"Gate2 preparation called {label}")
            self.serial += 1
            nid = f"nested_{self.serial:04d}"
            refs = [value for value in (*args, *kwargs.values()) if isinstance(value, (dict, list))]
            rec = {"nested_id": nid, "core": label,
                   "caller_api": self.e.CALL_STACK[-1] if self.e.CALL_STACK else None,
                   "args": self.e.jsonable(args), "kwargs": self.e.jsonable(kwargs),
                   "input_path_scene": scene_bytes([a for a in (*args, *kwargs.values())
                                                    if isinstance(a, os.PathLike)])}
            if refs:
                self.e.CORE_INPUT_REFS[nid] = refs
                rec["input_refs_before"] = self.e.core_input_point(refs)
            try:
                result = real(*args, **kwargs)
                rec.update(outcome="returned", **{"return": copy.deepcopy(result)})
                return result
            except Exception as exc:
                rec.update(outcome="exception", exception_type=type(exc).__name__,
                           exception_str=str(exc), field=getattr(exc, "field", None),
                           stage=getattr(exc, "stage", None), reasons=copy.deepcopy(getattr(exc, "reasons", None)),
                           cause_chain=self.e.chain_of(exc), traceback=traceback.format_exc())
                raise
            finally:
                if refs:
                    rec["input_refs_after"] = self.e.core_input_point(refs)
                self.e.CORE_RECORDS.append(rec)
                self.nested[label] = self.nested.get(label, 0) + 1
        setattr(module, name, observed)


@contextmanager
def readonly_guard(hits):
    saved = []
    def replace(obj, name, fn):
        saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, fn)
    def deny(name):
        def blocked(*args, **kwargs):
            hits.append(name)
            raise AssertionError(name)
        return blocked
    for mod in (builtins, io):
        original = mod.open
        def opened(file, mode="r", *args, _original=original, **kwargs):
            if any(flag in mode for flag in "wax+"):
                hits.append("write_open")
                raise AssertionError("write_open")
            return _original(file, mode, *args, **kwargs)
        replace(mod, "open", opened)
    original_os_open = os.open
    def os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            hits.append("os.open.write")
            raise AssertionError("os.open.write")
        return original_os_open(path, flags, *args, **kwargs)
    replace(os, "open", os_open)
    for obj, name in ((os, "mkdir"), (os, "unlink"), (os, "rename"), (socket, "socket"),
                      (subprocess, "Popen")):
        replace(obj, name, deny(name))
    try:
        yield
    finally:
        for obj, name, fn in reversed(saved):
            setattr(obj, name, fn)


def configure_evidence():
    e = load(ROOT / "tests/test_runtime_approved_load.py", "task029_accepted_closure")
    original_build = e.build_candidate
    def candidate(*args, **kwargs):
        result = original_build(*args, **kwargs)
        result["summary"]["task"] = "TASK-029"
        direct = {}
        for entry in result["api_records"]:
            operation = entry["operation"]
            direct[operation] = direct.get(operation, 0) + 1
        result["summary"]["direct_api_records_by_operation"] = direct
        result["summary"]["observed"]["role_note"] = (
            "直接测试调用以 direct_api_records_by_operation 为准；公开函数 profile 包含内部调用，"
            "冻结 prepare/store/P1 和计算入口另列，不能相加冒充直接 API 次数。")
        return result
    e.build_candidate = candidate
    def finalize(call_id):
        for record in e.CORE_RECORDS:
            nid = record["nested_id"]
            if record["caller_api"] == call_id and nid in e.CORE_INPUT_REFS:
                record["input_refs_api_end"] = e.core_input_point(e.CORE_INPUT_REFS[nid])
    e.finalize_core_observations = finalize
    return e


def run_tests(e, rt, obs, out):
    round_id = out.name
    runtime = ROOT / "data/runtime" / round_id
    records = ROOT / "data/human_gate_decision_records/gate1" / round_id
    dbroot = ROOT / "data/sqlite_tests" / round_id
    for root in (runtime, records, dbroot):
        root.mkdir(parents=True, exist_ok=False)
    batch = e.BATCH_NORMAL
    def call(label, fn, *args, **kwargs):
        before = copy.deepcopy(obs.counts)
        result = e.call_api(rt, label, fn, *args, **kwargs)
        e.API_RECORDS[-1]["actual_entry_deltas"] = {k: obs.counts[k] - before.get(k, 0)
                                                   for k in obs.counts}
        return result[0], copy.deepcopy(result[1]), result[2]
    def create(tag, fields=None, do_load=True):
        leaf, scope = runtime / tag, records / tag
        _, built, _ = call("build", rt.build_runtime_registry, batch, leaf, scope_dir=scope)
        _, prepared, _ = call("gate1_prepare", rt.prepare_runtime_gate1_request,
                              batch, leaf, "FIXTURE-REQ-G1-0001")
        if not built or not prepared:
            raise AssertionError("normal fixture setup failed")
        fields = fields or e.APPROVE_FIELDS
        sub = e.submission_for(fields, prepared["request"]["materials"]["materials_fingerprint"],
                               "FIXTURE-REQ-G1-0001", prepared["request"]["materials"]["batch_id"])
        event = scope / "event_0001"
        error, saved, _ = call("gate1_save", rt.save_runtime_gate1_decision, batch, leaf,
                               "FIXTURE-REQ-G1-0001", sub, event, scope_dir=scope)
        if error:
            raise error
        database = dbroot / tag / "runtime.sqlite3"
        args = {"scope_dir": scope, "event_relative": event.relative_to(ROOT).as_posix(),
                "database_path": database}
        if do_load:
            error, loaded, _ = call("approved_load", rt.run_gate1_approved_load,
                                    batch, leaf, **args)
            if error:
                raise error
        return {"leaf": leaf, "scope": scope, "event": event, "database": database,
                "args": args, "prepared": prepared, "saved": saved,
                "load": leaf.with_name(leaf.name + ".load")}
    scene = create("normal")
    paths = [batch, scene["leaf"], scene["scope"], scene["load"], scene["database"].parent]
    start = scene_bytes(paths)
    def prepare(scene=scene, request_id="G2\nREQ-001", **overrides):
        args = dict(scene["args"], **overrides)
        obs.gate2 = True
        try:
            return call("gate2_prepare", rt.prepare_runtime_gate2_request,
                        batch, scene["leaf"], request_id, **args)
        finally:
            obs.gate2 = False
    hits = []
    with readonly_guard(hits):
        error, first, _ = prepare()
        error2, second, _ = prepare()
    e.check("G1.two_readonly_requests", error is None and error2 is None and
            canon(first) == canon(second) and not hits and start == scene_bytes(paths),
            {"guard_hits": hits})
    if error:
        raise error
    request = first["request"]
    material, exp = request["materials"], request["expectations"]
    mapping = {
        "registry/runtime_registry.json": scene["leaf"] / "runtime_registry.json",
        "registry/runtime_registry_readback.json": scene["leaf"] / "runtime_registry_readback.json",
        "gate1/decision_result.json": scene["event"] / "snapshots/decision_result.json",
        "source/batch_manifest.json": batch / "batch_manifest.json",
        "source/quality_report.json": batch / "checks/quality_report.json",
        "load/started.json": scene["load"] / "started.json",
        "normalized/normalized.json": scene["load"] / "normalized.json",
        "load/load_report.json": scene["load"] / "load_report.json",
        "load/artifacts.json": scene["load"] / "artifacts.json",
        "sqlite/runtime.sqlite3": scene["database"],
    }
    expected_files = [{"relative": rel, "byte_size": len(path.read_bytes()),
                       "file_sha256": sha(path.read_bytes())}
                      for rel, path in sorted(mapping.items(), key=lambda pair: pair[0].encode("utf-8"))]
    sizes = [len(first), len(request), len(material), len(exp), len(request["evidence"]),
             len(request["boundaries"]), len(exp["expected_prior_gate1"])]
    e.check("G1.shape_materials", sizes == [2, 6, 7, 8, 7, 7, 5] and
            canon(material["files"]) == canon(expected_files) and
            exp["expected_files"] == {x["relative"]: x["file_sha256"] for x in expected_files} and
            all(type(x["byte_size"]) is int for x in material["files"]) and
            all(v is False for v in request["boundaries"].values()), {"sizes": sizes})
    record = scene["saved"]["record"]
    prior = {"gate": "GATE1", "batch_id": record["batch_id"], "event_id": record["event_id"],
             "record_fingerprint": scene["saved"]["record_fingerprint"],
             "run_binding": record["binding"]["run_binding"]}
    e.check("G1.bindings_and_hashes", canon(prior) == canon(exp["expected_prior_gate1"]) and
            canon(material["run_binding"]) == canon(record["binding"]["run_binding"]) and
            material["materials_fingerprint"] != record["binding"]["materials_fingerprint"] and
            sha(canon({k: v for k, v in material.items() if k != "materials_fingerprint"})) ==
            material["materials_fingerprint"] and sha(canon(request)) == first["request_sha256"] and
            exp["expected_request_id"] == "G2\nREQ-001")
    first["request"]["expectations"]["expected_run_binding"]["input"]["file_sha256"] = "0" * 64
    e.check("G1.no_alias", canon(request["materials"]["run_binding"]) ==
            canon(record["binding"]["run_binding"]) and scene_bytes(paths) == start)
    error3, hexid, _ = prepare(request_id="a" * 64)
    e.check("G1.ordinary_hex_id", error3 is None and
            hexid["request"]["expectations"]["expected_request_id"] == "a" * 64)

    def rejected(label, **kwargs):
        before = scene_bytes(paths)
        error, result, cid = prepare(**kwargs)
        e.check(label, isinstance(error, rt.RuntimeGate1Blocked) and result is None and
                before == scene_bytes(paths), {"call_id": cid, "field": getattr(error, "field", None)})
    rejected("G2.empty_id", request_id=" ")
    rejected("G2.nonstring_id", request_id=7)
    rejected("G2.wrong_database", database_path=ROOT / "data/runtime/not_allowed.sqlite3")

    # Only this round's own bytes are changed; preserve candidates, restore exact originals.
    def altered(label, path, new_bytes, expected_field):
        original = path.read_bytes() if path.exists() else None
        path.write_bytes(new_bytes)
        before = scene_bytes(paths)
        try:
            error, result, cid = prepare()
            e.check(label, isinstance(error, (rt.RuntimeGate1Blocked, rt.RuntimeGate1Error)) and
                    expected_field in str(getattr(error, "field", getattr(error, "stage", ""))) and
                    before == scene_bytes(paths), {"call_id": cid, "field": getattr(error, "field", None),
                                                 "stage": getattr(error, "stage", None)})
            (out / (label + ".candidate.bin")).write_bytes(path.read_bytes())
        finally:
            if original is None:
                path.unlink()  # exact new injected file only; absent-state restoration, no directory cleanup
            else:
                path.write_bytes(original)
    failure = {"failure_version": rt.FAILURE_VERSION_028, "kind": "BLOCKED", "stage": "fixture",
               "field": "fixture", "reason": "PROTOCOL_TEST_FIXTURE_ONLY", "cause_chain": []}
    altered("G2.valid_failure", scene["load"] / "failure.json", canon(failure) + b"\n", "failure.fixture")
    started_path = scene["load"] / "started.json"
    started = json.loads(started_path.read_bytes())
    started["bindings"]["run_binding"]["input"]["file_sha256"] = "0" * 64
    altered("G2.wrong_binding", started_path, canon(started) + b"\n", "started.bindings.run_binding")
    unloaded = create("unloaded", do_load=False)
    error, _, cid = prepare(unloaded)
    e.check("G2.no_load", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "load_dir",
            {"call_id": cid, "field": getattr(error, "field", None)})
    held = create("hold", fields=e.hold_fields(), do_load=False)
    held["load"].mkdir()
    for name in rt.APPROVED_LOAD_FILES:
        (held["load"] / name).write_bytes((scene["load"] / name).read_bytes())
    # Deliberately borrowed outputs: only the earlier effective Gate1 precondition is tested.
    held["args"]["database_path"] = scene["database"]
    error, _, cid = prepare(held)
    e.check("G2.nonapprove", isinstance(error, rt.RuntimeGate1Blocked) and error.field == "gate1.effective",
            {"call_id": cid, "field": getattr(error, "field", None),
             "fixture_scope": "HOLD genuine record; borrowed outputs never claimed valid"})

    real_inspect = rt.inspect_gate1_approved_load
    for label, target in (("database", scene["database"]),
                          ("event", scene["event"] / "context.json"),
                          ("unknown", scene["load"] / "unknown.json")):
        before = scene_bytes(paths)
        original = target.read_bytes() if target.exists() else None
        hit = [0]
        def injected(*args, **kwargs):
            returned = real_inspect(*args, **kwargs)
            hit[0] += 1
            target.write_bytes((original or b"{}") + b"\n")
            return returned
        rt.inspect_gate1_approved_load = injected
        try:
            error, _, cid = prepare()
        finally:
            rt.inspect_gate1_approved_load = real_inspect
        bad = scene_bytes(paths)
        follow_error, _, follow_cid = prepare()
        (out / f"G3.{label}.candidate.bin").write_bytes(target.read_bytes())
        if original is None:
            target.unlink()  # restore this newly injected file's absent state after preserving bad bytes
        else:
            target.write_bytes(original)
        restored_error, _, restored_cid = prepare()
        field = getattr(error, "field", "")
        expected_target = {"database": "runtime.sqlite3", "event": "context.json", "unknown": "load_dir"}[label]
        e.check(f"G3.{label}", isinstance(error, rt.RuntimeGate1Blocked) and hit == [1] and
                expected_target in field and follow_error is not None and restored_error is None and
                before == scene_bytes(paths) and not (scene["load"] / "failure.json").exists(),
                {"hit": hit[0], "field": field, "call_id": cid, "after_wrapper": follow_cid,
                 "restored": restored_cid, "bad_scene": bad})

    g2records = [r for r in e.API_RECORDS if r["operation"] == "gate2_prepare"]
    e.check("G4.one_inspect_no_save_or_compute", all(
        r["actual_entry_deltas"].get("prepare_runtime_gate2_request", 0) == 1 and
        r["actual_entry_deltas"].get("inspect_gate1_approved_load", 0) <= 1 and
        (r["outcome"] != "returned" or
         r["actual_entry_deltas"].get("inspect_gate1_approved_load", 0) == 1) and
        all(r["actual_entry_deltas"].get(n, 0) == 0 for n in ("store_save", "normalizer", "loader"))
        for r in g2records) and not obs.guard_hits, {"gate2_calls": len(g2records), "guard_hits": obs.guard_hits})
    # Every original code entry matches an independently complete wrapper entry count.
    closure = {label: {"profile": obs.counts.get(
        {"inspect": "inspect_gate1_approved_load", "gate1_verify": "verify_gate1_effective_approval"}.get(label, label), 0),
                       "entries": count} for label, count in obs.nested.items()}
    e.check("G4.nested_count_closure", all(x["profile"] == x["entries"] for x in closure.values()), closure)
    e.check("G4.source_unchanged", scene_bytes([batch]) == {k: v for k, v in start.items()
            if k == str(batch) or k.startswith(str(batch) + os.sep)})
    return {"nested_counts": closure, "gate2_direct_calls": len(g2records),
            "readonly_guard_hits": hits, "new_receiver_calls": 0,
            "source_receiver_evidence": scene_bytes([batch / "logs", batch / "checks/quality_report.json"]),
            "not_executed": {name: {"count": None, "reason": "outside TASK-029 scope"} for name in
                ("gate2_save", "screening", "crosscheck", "fact_packet", "initial_judgment", "AI", "new_junction", "historical_suites")}}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--replay")
    parser.add_argument("--mutate", choices=("none", "candidate-return", "ledger-late", "checks-late"), default="none")
    args = parser.parse_args(argv)
    out = Path(args.out_dir).resolve()
    if not out.is_relative_to(TEST_ROOT.resolve()) or out == TEST_ROOT.resolve() or out.exists():
        raise SystemExit("out-dir must be a never-existing strict descendant of test root")
    if not out.name.startswith("task029_"):
        raise SystemExit("round must use task029_ prefix")
    e = configure_evidence()
    e.ROUND["id"] = out.name
    out.mkdir(parents=True, exist_ok=False)
    obs = None
    if args.replay:
        source = Path(args.replay).resolve()
        if not source.is_relative_to(TEST_ROOT.resolve()) or source == out:
            raise SystemExit("replay source outside test root")
        checkpoint = json.loads((source / "expected_observations.json").read_bytes())
        extra = {"replay_only": True, "new_business_calls": 0, "source": str(source)}
    else:
        if args.mutate != "none":
            raise SystemExit("mutations require replay")
        rt = load(ROOT / "scripts/runtime_gate1.py", "task029_runtime_under_test")
        obs = Observations(rt, e)
        sys.setprofile(obs.profile)
        try:
            extra = run_tests(e, rt, obs, out)
        finally:
            sys.setprofile(None)
        checkpoint = e.freeze_expectations()
    original_read = Path.read_bytes
    injection = {"hits": 0}
    if args.mutate in ("ledger-late", "checks-late"):
        def read_then_mutate(path):
            result = original_read(path)
            frame = sys._getframe(1)
            if (frame.f_code is e.finish.__code__ and "terminal_buffers" in frame.f_locals
                    and path == out / "expected_observations.json" and injection["hits"] == 0):
                # All semantic/ledger consumption has finished; terminal raw-byte loop has started.
                target = out / ("file_ledger.json" if args.mutate == "ledger-late" else "checks.json")
                before = original_read(target)
                with open(target, "ab") as handle:
                    handle.write(b"\n")
                injection.update(hits=1, target=target.name,
                                 boundary="after_content_and_ledger_audit_in_terminal_loop",
                                 before_size=len(before), after_size=len(before) + 1,
                                 before_sha256=sha(before), after_sha256=sha(before + b"\n"))
            return result
        Path.read_bytes = read_then_mutate
    # The accepted finish detects actual content/byte failures; no flag-based failure verdict.
    try:
        code = e.finish(out, checkpoint, "candidate-return" if args.mutate == "candidate-return" else "none", obs, extra)
    finally:
        Path.read_bytes = original_read
    if args.mutate in ("ledger-late", "checks-late"):
        (out / "control_observation.json").write_bytes(canon(injection) + b"\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
