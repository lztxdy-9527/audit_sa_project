"""TASK-040-R1：初判保存/只读恢复的定点修正动态测试与证据。

相对 TASK-040：补 S5 复确认（B1）与末次集合/failure/锁确认（B2）的对照控制、取锁序（B3）控制、
S8 返回审核契约（B4）的 RC-40/RC-44/RC-08/09 控制、独立预期先于候选（E3）台账与真实句柄半写（E4）。
只读复用 TASK-035 观察 helper 与 TASK-038 已接受 Observer/guard 定义（不执行其 run/main）。
边界：合成测试保存不等于真实批准；真实批准仍 null，不认证身份、不开放 AI/终判。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
BATCH = ROOT / "data/batches/task027r1_run_04/batch_normal"
SCRIPT = ROOT / "scripts" / "runtime_gate1.py"
SCOPE = "TASK037-DECLARED-TECHNICAL-NAMESPACE"
TASK037_SOURCE = ROOT / "data/human_initial_judgment_records/task037_run_01/two"
GATE_FIXTURE = ROOT / "data/decision_protocol_checks/task020r2_run_01/fixture_values.json"
LEAF_FILES = ("expectations.json", "judgment_result.json", "manifest.json",
              "materials.json", "prior_history.json", "submission.json")
ENVELOPE_FILES = ("context.json", "receipt.json", "started.json")
STORAGE_KEYS = ("status", "scope", "identity", "record_fingerprint", "manifest_file_sha256",
                "technical_registration", "component_bindings", "files", "boundaries",
                "snapshots", "judgment_result")
BOUNDARY_KEYS = ("workflow_connected", "execution_allowed", "next_step_allowed", "ai_enabled",
                 "identity_authenticated", "source_authenticity_proven",
                 "audit_conclusion_formed", "final_judgment_recorded",
                 "global_history_completeness_proven")
SUCCESS_KEYS = ("stage_version", "status", "scope", "identity", "record_relative",
                "record_fingerprint", "manifest_file_sha256", "storage_verification",
                "envelope_binding", "history_verification", "boundaries", "note")
HISTORY_EXPECTATIONS_VERSION = "TASK-037-human-initial-judgment-history-expectations-1.0"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fp(value):
    return sha(canon(value))


def read(path):
    return json.loads(Path(path).read_bytes())


def identity(path):
    raw = Path(path).read_bytes()
    return {"byte_size": len(raw), "sha256": sha(raw)}


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


def brief(value):
    if type(value) is dict:
        return {"keys": sorted(value), "identity": value.get("identity"),
                "status": value.get("status")}
    return {"type": type(value).__name__}


def safe_value(value):
    """JSON 安全证据投影：路径/字节/非有限浮点带标签，不改业务输入。"""
    if isinstance(value, Path):
        return {"$path": str(value)}
    if type(value) is bytes:
        return {"$python_type": "bytes", "hex": value.hex()}
    if type(value) is float and value != value:
        return {"$python_type": "float", "repr": repr(value)}
    if type(value) in (list, tuple):
        return [safe_value(item) for item in value]
    if type(value) is dict:
        return {str(key): safe_value(item) for key, item in value.items()}
    if isinstance(value, os.PathLike):
        return {"$path": str(value)}
    return value


class Scene:
    def __init__(self, name):
        self.name = name
        self.evidence = TEST_ROOT / name
        self.runtime = ROOT / "data/runtime" / name
        self.gate1 = ROOT / "data/human_gate_decision_records/gate1" / name
        self.gate2 = ROOT / "data/human_gate_decision_records/gate2" / name
        self.sqlite = ROOT / "data/sqlite_tests" / name
        self.history = ROOT / "data/human_initial_judgment_records" / name
        self.leaf = self.runtime / "normal"
        self.envelope = self.runtime / "normal.initial"
        self.scope = self.gate1 / "normal"
        self.event1 = self.scope / "event_0001"
        self.event2 = self.gate2 / "normal" / "event_0001"
        self.database = self.sqlite / "normal/runtime.sqlite3"
        self.namespace = self.history / "bound"
        self.record = self.namespace / "rec_0001"
        self.lock = self.history / "bound.initial_judgment.lock"
        self.params = {}

    def create(self):
        for path in (self.runtime, self.gate1, self.gate2, self.sqlite, self.history,
                     self.evidence):
            path.mkdir(parents=True, exist_ok=(path == self.evidence))
        self.namespace.mkdir()
        self.params = {"scope_dir": self.scope, "event_relative": rel(self.event1),
                       "database_path": self.database,
                       "gate2_event_relative": rel(self.event2)}
        return self

    def roots(self):
        return [BATCH, self.runtime, self.gate1, self.gate2, self.sqlite, self.history]


def make_module(tag="task040_r1_runtime_under_test"):
    return load(SCRIPT, tag)


def plain_call(log, label, fn, *a, **k):
    try:
        value = fn(*a, **k)
    except Exception as exc:  # noqa: BLE001
        log.append({"operation": label, "outcome": "exception",
                    "exception_type": type(exc).__name__,
                    "field": getattr(exc, "field", None),
                    "stage": getattr(exc, "stage", None),
                    "reason": getattr(exc, "reason", str(exc))})
        raise
    log.append({"operation": label, "outcome": "returned", "summary": brief(value)})
    return value


def build_chain(rt, scene, log):
    """一条新 profile 正常前提链：注册、Gate1、装载、Gate2、筛查、复算、事实各一次。"""
    registry = plain_call(log, "setup.registry", rt.build_runtime_registry, BATCH, scene.leaf,
                          scope_dir=scene.scope,
                          initial_judgment_history={"namespace_relative": rel(scene.namespace),
                                                    "declared_scope": SCOPE})["registry"]
    request1 = plain_call(log, "setup.gate1_request", rt.prepare_runtime_gate1_request, BATCH,
                          scene.leaf, "FIXTURE-REQ-G1-0001")
    fields = read(GATE_FIXTURE)
    submission1 = copy.deepcopy(fields["BASE1"]["submission"])
    submission1["batch_id"] = registry["batch_id"]
    submission1["request_binding"] = {
        "request_id": "FIXTURE-REQ-G1-0001",
        "materials_binding": request1["request"]["materials"]["materials_fingerprint"]}
    record1 = plain_call(log, "setup.gate1_save", rt.save_runtime_gate1_decision, BATCH,
                         scene.leaf, "FIXTURE-REQ-G1-0001", submission1, scene.event1,
                         scope_dir=scene.scope)
    plain_call(log, "setup.load", rt.run_gate1_approved_load, BATCH, scene.leaf,
               scope_dir=scene.scope, event_relative=rel(scene.event1),
               database_path=scene.database)
    request2 = plain_call(log, "setup.gate2_request", rt.prepare_runtime_gate2_request, BATCH,
                          scene.leaf, "FIXTURE-REQ-G2-0001", scope_dir=scene.scope,
                          event_relative=rel(scene.event1), database_path=scene.database)
    submission2 = copy.deepcopy(fields["BASE2"]["submission"])
    submission2["batch_id"] = registry["batch_id"]
    submission2["request_binding"] = {
        "request_id": "FIXTURE-REQ-G2-0001",
        "materials_binding": request2["request"]["materials"]["materials_fingerprint"]}
    submission2["prior_decision_binding"] = {
        "wrapper_version": rt.GATE2_WRAPPER_VERSION, "record": record1["record"],
        "record_fingerprint": record1["record_fingerprint"]}
    plain_call(log, "setup.gate2_save", rt.save_runtime_gate2_decision, BATCH, scene.leaf,
               "FIXTURE-REQ-G2-0001", submission2, scene.event2, scope_dir=scene.scope,
               event_relative=rel(scene.event1), database_path=scene.database)
    for label, function in (("screen", rt.run_gate2_approved_screen),
                            ("crosscheck", rt.run_gate2_rule_crosscheck),
                            ("facts", rt.run_gate2_fact_packet)):
        plain_call(log, "setup." + label, function, BATCH, scene.leaf, **scene.params)
    return registry


def build_submission(registry, materials_fingerprint, request_id, event_id):
    return {"submission_version": "TASK-034-human-initial-judgment-submission-1.0",
            "event_id": event_id, "batch_id": registry["batch_id"],
            "request_binding": {"request_id": request_id,
                                "materials_fingerprint": materials_fingerprint},
            "submission_source": "HUMAN_INITIAL_JUDGMENT",
            "actor": {"actor_kind": "HUMAN_DECLARED", "actor_id": "1",
                      "declaration_note": "1"},
            "decided_at_raw": "2026-10-16", "assessment": "通过",
            "reason": "无明显不一致且合规"}


def expectations_block(scene, entries):
    return {"expectations_version": HISTORY_EXPECTATIONS_VERSION,
            "expected_namespace_relative": rel(scene.namespace),
            "expected_declared_scope": SCOPE, "expected_entries": entries}


def leaf_entry(scene, name):
    return {"relative": name,
            "manifest_file_sha256": sha((scene.namespace / name / "manifest.json").read_bytes())}


def copy_task037_leaf(scene, name):
    """把已接受 TASK-037 合成独立六文件叶按原字节复制到本轮新域。"""
    target = scene.namespace / name
    target.mkdir()
    for leaf_name in LEAF_FILES:
        (target / leaf_name).write_bytes((TASK037_SOURCE / name / leaf_name).read_bytes())


def tree_snapshot(path):
    result = {}
    for item in sorted(Path(path).rglob("*")):
        if item.is_file():
            result[item.relative_to(path).as_posix()] = identity(item)
    return result


class Observer:
    """复用 TASK-038 已接受 guard；共享冻结模块只登记 code 标签，临时模块记录完整嵌套。"""

    LABELED = (
        ("_load_frozen_prepare", [("prepare_human_gate1_request", "source.prepare")], None, ()),
        ("_load_frozen_store",
         [("save_human_gate_decision_snapshots", "gate.store.save"),
          ("verify_human_gate_decision_snapshots", "gate.store.verify")],
         "_core", [("build_human_gate_decision_record", "gate.core")]),
        ("_load_frozen_normalizer", [("normalize_workbook", "algorithm.normalize")], None, ()),
        ("_load_frozen_sqlite_core", [("load_normalized_to_sqlite", "algorithm.load")], None, ()),
        ("_load_frozen_screen_031", [("screen_sqlite", "algorithm.screen")], None, ()),
        ("_load_frozen_crosscheck_032", [("verify_rule_facts", "algorithm.crosscheck")], None, ()),
        ("_load_frozen_facts_033",
         [("build_fact_packet", "algorithm.facts_build"), ("render_markdown", "facts.render")],
         None, ()),
    )
    WRAPPED = ("build_runtime_registry", "read_runtime_registry", "prepare_runtime_gate1_request",
               "save_runtime_gate1_decision", "verify_gate1_effective_approval",
               "run_gate1_approved_load", "inspect_gate1_approved_load",
               "prepare_runtime_gate2_request", "save_runtime_gate2_decision",
               "verify_runtime_gate2_decision", "run_gate2_approved_screen",
               "inspect_gate2_approved_screen", "run_gate2_rule_crosscheck",
               "inspect_gate2_rule_crosscheck", "run_gate2_fact_packet",
               "inspect_gate2_fact_packet", "prepare_runtime_initial_judgment_request",
               "save_runtime_initial_judgment", "verify_runtime_initial_judgment")
    FORBIDDEN = ("runtime.build_runtime_registry", "runtime.prepare_runtime_gate1_request",
                 "runtime.prepare_runtime_gate2_request")

    def __init__(self, rt, e):
        self.rt, self.e = rt, e
        self.api = {}
        self.codes = {}
        self.originals = []
        self.serial = 0
        self.stack = []
        self.phase = "setup"
        self.hits = []
        self.proof = []
        self.io = []
        self.modules = []
        self.normalizer = None
        self.loader = None
        self._other = {}
        self.count = 0
        self.allowed_reads = set()
        self.allowed_roots = []
        self.allowed_write_roots = []
        for name in self.WRAPPED:
            self.wrap(rt, name, "runtime." + name)
        for loader, entries, core_loader, core_entries in self.LABELED:
            original = getattr(rt, loader)
            setattr(rt, loader, self.labeled_loader(original, entries, core_loader, core_entries))
        self.hook_initial_history(rt)

    def register(self, label):
        self.api.setdefault(label, 0)

    def label(self, module, entries):
        for name, label in entries:
            function = getattr(module, name, None)
            if function is None:
                continue
            self.codes[id(function.__code__)] = label
            self.register(label)

    def labeled_loader(self, original, entries, core_loader, core_entries):
        def load(*a, **k):
            module = original(*a, **k)
            if core_loader is not None and not getattr(module, "__task040_core_hooked__", False):
                inner = getattr(module, core_loader)
                setattr(module, "__task040_core_hooked__", True)

                def core_load(*aa, **kk):
                    core = inner(*aa, **kk)
                    self.label(core, core_entries)
                    return core
                setattr(module, core_loader, core_load)
            self.label(module, entries)
            return module
        return load

    def hook_initial_history(self, rt):
        original = rt._load_initial_history_038

        def load(*a, **k):
            module = original(*a, **k)
            self.wrap(module, "inspect_human_initial_judgment_history", "history")
            load_store = module._load_store

            def store_load(*aa, **kk):
                store, raw = load_store(*aa, **kk)
                self.wrap(store, "save_human_initial_judgment_snapshots", "initial.store.save")
                self.wrap(store, "verify_human_initial_judgment_snapshots",
                          "initial.store.verify")
                core_load = store._load_core

                def load_core(*ab, **kb):
                    core = core_load(*ab, **kb)
                    self.wrap(core, "build_human_initial_judgment_record", "initial.core")
                    return core
                store._load_core = load_core
                return store, raw
            module._load_store = store_load
            return module
        rt._load_initial_history_038 = load

    def wrap(self, module, name, label):
        function = getattr(module, name)
        self.originals.append(function)
        self.codes[id(function.__code__)] = label
        self.register(label)
        e = self.e

        def observed(*a, **k):
            if self.phase == "request" and (
                    label.startswith("algorithm.") or ".save" in label
                    or label.startswith("runtime.run_") or label in self.FORBIDDEN):
                self.hits.append("forbidden_entry:" + label)
                raise AssertionError("TASK040_FORBIDDEN:" + label)
            call_id = e.CALL_STACK[-1] if e.CALL_STACK else None
            self.serial += 1
            nested = "entry_%05d" % self.serial
            refs = [*a, *k.values()]
            e.CORE_INPUT_REFS[nested] = refs
            row = {"nested_id": nested, "core": label, "caller_api": call_id,
                   "parent_nested_id": self.stack[-1] if self.stack else None,
                   "phase": self.phase, "args": e.jsonable(a), "kwargs": e.jsonable(k),
                   "input_refs_before": e.core_input_point(refs)}
            self.stack.append(nested)
            try:
                result = function(*a, **k)
                row.update(outcome="returned", **{"return": copy.deepcopy(result)})
                return result
            except Exception as exc:  # noqa: BLE001
                row.update(outcome="exception", exception_type=type(exc).__name__,
                           exception_str=str(exc), field=getattr(exc, "field", None),
                           stage=getattr(exc, "stage", None),
                           reasons=copy.deepcopy(getattr(exc, "reasons", None)),
                           traceback=traceback.format_exc(), cause_chain=e.chain_of(exc))
                raise
            finally:
                self.stack.pop()
                row["input_refs_after"] = e.core_input_point(refs)
                e.CORE_RECORDS.append(row)
        setattr(module, name, observed)

    def profile(self, frame, event, arg):
        if event != "call":
            return
        label = self.codes.get(id(frame.f_code))
        if label:
            self.api[label] += 1
            self.count += 1

    def all_counts(self):
        return dict(self.api)


def independent_expectations(registry):
    """E3：运行候选前由卡公式/结构常量固定独立预期台账（不读取候选返回值）。"""
    n, m1, m2 = 0, 1, 2
    save_graph = {
        "runtime.prepare_runtime_initial_judgment_request": 1,
        "initial.store.save": 1, "history": 2,
        "initial.store.verify": 2 * n + 1, "initial.core": 2 * n + 2,
        "runtime.verify_gate1_effective_approval": 6,
        "runtime.verify_runtime_gate2_decision": 5,
        "runtime.inspect_gate1_approved_load": 5,
        "runtime.inspect_gate2_approved_screen": 2,
        "runtime.inspect_gate2_rule_crosscheck": 1,
        "runtime.inspect_gate2_fact_packet": 1, "facts.render": 1,
        "gate.store.verify": 11, "gate.core": 11, "source.prepare": 6,
        "runtime.save_runtime_gate1_decision": 0, "runtime.save_runtime_gate2_decision": 0,
        "algorithm.normalize": 0, "algorithm.load": 0, "algorithm.screen": 0,
        "algorithm.crosscheck": 0, "algorithm.facts_build": 0}
    verify_graph = {
        "history": 1, "runtime.prepare_runtime_initial_judgment_request": 0,
        "runtime.save_runtime_initial_judgment": 0, "initial.store.save": 0,
        "runtime.verify_gate1_effective_approval": 6,
        "runtime.verify_runtime_gate2_decision": 5,
        "runtime.inspect_gate2_fact_packet": 1, "facts.render": 1,
        "algorithm.normalize": 0, "algorithm.load": 0, "algorithm.screen": 0,
        "algorithm.crosscheck": 0, "algorithm.facts_build": 0}
    return {
        "declared_before_run": True,
        "stage_version": "TASK-039-runtime-human-initial-judgment-1.0",
        "scope": "RUNTIME_CURRENT_MATERIALS_AND_DECLARED_HISTORY_ONLY",
        "success_status_save": "RT_HUMAN_INITIAL_JUDGMENT_RECORDED",
        "success_status_verify": "RT_HUMAN_INITIAL_JUDGMENT_VERIFIED",
        "success_keys": sorted(SUCCESS_KEYS),
        "storage_keys": sorted(STORAGE_KEYS),
        "boundaries": {key: False for key in BOUNDARY_KEYS},
        "leaf_files": list(LEAF_FILES),
        "envelope_files": list(ENVELOPE_FILES),
        "identity": {"batch_id": registry["batch_id"], "event_id": "2",
                     "request_id": "TECH-REQ-IJ-0001"},
        "h0_records": [], "h1_records": ["2"], "hc_records": ["1", "2"],
        "e1_relative_names": ["rec_0001", "z_first"],
        "save_graph": save_graph,
        "verify_graph_m1": dict(verify_graph, **{"initial.store.verify": m1,
                                                 "initial.core": m1}),
        "verify_graph_m2": dict(verify_graph, **{"initial.store.verify": m2,
                                                 "initial.core": m2}),
        "hardening": {
            "rebuild_success_calls": {"save": 1, "verify.manual_controls": 0},
            "h1_control_field": "result.record_relative",
            "h3_control_field": "sql/demo_schema.sql",
            "started_role_field": "started.source_binding.registry_binding.run_binding_sha256",
            "failure_fields": {
                "f01_bad_submission": "store.submission.assessment",
                "f03_store_half_write": "write.expectations.json",
                "f04_context_half_write": "write.context",
                "f05_receipt_sentinel": "write.receipt",
                "f06_release_failure": "release.lock",
                "rc44b_request_role": "context.prepared_request.request_sha256",
                "h1_candidate_control": "result.record_relative",
                "h3_schema_drift": "sql/demo_schema.sql"},
        },
    }


def run(e, rt, plain_rt, out):
    import types
    T03 = load(ROOT / "tests/test_runtime_initial_judgment_request.py",
               "task040_r1_reuse_task038_observer")
    e.jsonable = safe_value

    def points(refs):
        rows = []
        for value in refs:
            snapshot = safe_value(copy.deepcopy(value))
            rows.append({"reference_id": id(value), "snapshot": snapshot,
                         "fingerprint": fp(snapshot)})
        return rows
    e.core_input_point = points
    o = Observer(rt, e)
    o.guard = types.MethodType(T03.Observer.guard, o)
    # H1 硬化新增的内部构造调用单独计数，不并入业务调用图公式。
    o.codes[id(rt._rebuild_success_040.__code__)] = "hardening.rebuild_success"
    o.register("hardening.rebuild_success")
    results = {"setup_operations": [], "failure_scenes": [], "case_map": {}, "controls": {}}

    def call(label, function, *a, phase="setup", field=None, field_prefix=None, stage=None, **k):
        previous = o.phase
        o.phase = phase
        before = dict(o.api)

        def guarded(*args, **kwargs):
            with o.guard():
                return function(*args, **kwargs)
        try:
            err, value, cid = e.call_api(rt, label, guarded, *a, **k)
        finally:
            o.phase = previous
        delta = {key: o.api[key] - before.get(key, 0) for key in o.api}
        if e.API_RECORDS:
            e.API_RECORDS[-1].update(record_category=phase, actual_entries=delta)
        if field is not None:
            ok = isinstance(err, rt.RuntimeGate1Blocked) and err.field == field
        elif field_prefix is not None:
            current = getattr(err, "field", None)
            ok = isinstance(err, rt.RuntimeGate1Blocked) and isinstance(current, str) \
                and current.startswith(field_prefix)
        elif stage is not None:
            ok = isinstance(err, rt.RuntimeGate1Error) and err.stage == stage
        else:
            ok = err is None
        e.check(label if ok else label + "!", ok,
                {"field": getattr(err, "field", None), "stage": getattr(err, "stage", None),
                 "type": type(err).__name__ if err else None})
        print(json.dumps({"operation": label, "ok": ok,
                          "field": getattr(err, "field", None),
                          "stage": getattr(err, "stage", None),
                          "delta": delta}), flush=True)
        return err, value, cid

    scene = Scene(out.name).create()
    o.allowed_roots = list(scene.roots())
    o.allowed_write_roots = list(scene.roots())
    prep = rt._load_frozen_prepare()
    o.allowed_reads = {ROOT / path for _, path in prep.PROJECT_MATERIAL_FILES}
    o.allowed_reads |= {SCRIPT, ROOT / "scripts/prepare_demo_human_gate1.py"}
    o.allowed_reads |= {ROOT / path for path in rt.INITIAL_COMPONENT_SHA256}
    o.allowed_reads |= {ROOT / path for path in rt.RECORDING_COMPONENT_SHA256}

    sys.setprofile(o.profile)
    try:
        registry = build_chain(plain_rt, scene, results["setup_operations"])
        independent = independent_expectations(registry)
        results["independent_expectations"] = independent

        # B3：域/scope/锁错误在取锁之前拒绝，不产生锁/叶/封装，业务增量 0。
        dummy = build_submission(registry, "0" * 64, "TECH-REQ-IJ-0001", "2")
        err, _, save_cid = call("save.bad_namespace", rt.save_runtime_initial_judgment, BATCH,
                                scene.leaf, "TECH-REQ-IJ-0001", dummy, rel(scene.record),
                                phase="save",
                                field="history_expectations.expected_namespace_relative",
                                **scene.params,
                                history_expectations=dict(
                                    expectations_block(scene, []),
                                    expected_namespace_relative=rel(scene.history / "absent")))
        results["controls"]["bad_namespace"] = {
            "call_id": save_cid, "field": getattr(err, "field", None),
            "lock_exists": scene.lock.exists(), "record_exists": scene.record.exists(),
            "envelope_exists": scene.envelope.exists()}
        e.check("B3.1 错声明域在取锁前 Blocked 且无锁/叶/封装",
                getattr(err, "field", None) == "history_expectations.expected_namespace_relative"
                and not scene.lock.exists() and not scene.record.exists()
                and not scene.envelope.exists(), results["controls"]["bad_namespace"])
        e.check("B3.2 错声明域业务调用 0",
                all(e.API_RECORDS[-1]["actual_entries"].get(key, 0) == 0 for key in
                    ("runtime.prepare_runtime_initial_judgment_request", "initial.store.save",
                     "history", "runtime.verify_gate1_effective_approval")), None)
        err, _, _ = call("save.bad_scope", rt.save_runtime_initial_judgment, BATCH,
                         scene.leaf, "TECH-REQ-IJ-0001", dummy, rel(scene.record),
                         phase="save", field="history_expectations.expected_declared_scope",
                         **scene.params,
                         history_expectations=dict(expectations_block(scene, []),
                                                   expected_declared_scope="WRONG"))
        results["controls"]["bad_scope"] = {
            "field": getattr(err, "field", None), "lock_exists": scene.lock.exists(),
            "record_exists": scene.record.exists(), "envelope_exists": scene.envelope.exists()}
        e.check("B3.3 错 scope 在取锁前 Blocked 且无锁/叶/封装",
                getattr(err, "field", None) == "history_expectations.expected_declared_scope"
                and not scene.lock.exists() and not scene.record.exists()
                and not scene.envelope.exists(), results["controls"]["bad_scope"])
        held = rt._acquire_initial_lock(scene.lock, namespace_relative=rel(scene.namespace),
                                        runtime_relative=rel(scene.leaf),
                                        record_relative=rel(scene.record),
                                        request_id="TECH-REQ-IJ-LOCK")
        try:
            call("save.lock_control", rt.save_runtime_initial_judgment, BATCH, scene.leaf,
                 "TECH-REQ-IJ-0001", dummy, rel(scene.record), phase="save", field="lock",
                 **scene.params, history_expectations=expectations_block(scene, []))
        finally:
            release_error = rt._release_initial_lock(held)
        e.check("B3.4 控制锁按已持有句柄释放且未留下本次封装/叶",
                release_error is None and not scene.lock.exists()
                and not scene.envelope.exists() and not scene.record.exists(), release_error)

        # B1：S5 复确认对 Gate1 来源漂移精确 Blocked、store/core 增量 0、恢复后通过。
        control_envelope = scene.evidence / "b1_control_envelope"
        control_envelope.mkdir()
        started_buffer = b'{"started_probe":1}\n'
        (control_envelope / "started.json").write_bytes(started_buffer)
        held = rt._acquire_initial_lock(scene.lock, namespace_relative=rel(scene.namespace),
                                        runtime_relative=rel(scene.leaf),
                                        record_relative=rel(scene.record),
                                        request_id="TECH-REQ-IJ-S5")
        target = scene.event1 / "context.json"
        original = target.read_bytes()
        (scene.evidence / "b1_drift.original.bin").write_bytes(original)
        (scene.evidence / "b1_drift.tampered.bin").write_bytes(original + b"\n")
        check_ctx = rt._capture_initial_sources_038(
            BATCH, scene.leaf, dict(scene.params), expectations_block(scene, []))
        started_capture = {"bytes": started_buffer, "file_sha256": sha(started_buffer),
                           "byte_size": len(started_buffer),
                           "path": str(control_envelope / "started.json")}
        target.write_bytes(original + b"\n")
        before_counts = dict(o.api)
        err_s5 = None
        try:
            rt._pre_store_confirm_040(check_ctx, scene.record, control_envelope, held,
                                      started_capture, started_buffer, rel(scene.record),
                                      check_ctx["history"]["namespace"])
        except Exception as exc:  # noqa: BLE001
            err_s5 = exc
        finally:
            target.write_bytes(original)
        s5_delta = {key: o.api[key] - before_counts.get(key, 0) for key in o.api}
        results["controls"]["s5_drift"] = {
            "field": getattr(err_s5, "field", None), "type": type(err_s5).__name__,
            "store_delta": s5_delta.get("initial.store.save", 0),
            "core_delta": s5_delta.get("initial.core", 0)}
        e.check("B1.1 S5 复确认对 Gate1 来源漂移精确 Blocked",
                isinstance(err_s5, rt.RuntimeGate1Blocked)
                and str(getattr(err_s5, "field", "")).startswith("gate1_event."),
                results["controls"]["s5_drift"])
        e.check("B1.2 S5 复确认失败时 store/core 增量 0 且未建叶",
                s5_delta.get("initial.store.save", 0) == 0
                and s5_delta.get("initial.core", 0) == 0
                and not scene.record.exists(), s5_delta)
        err_s5b = None
        try:
            rt._pre_store_confirm_040(check_ctx, scene.record, control_envelope, held,
                                      started_capture, started_buffer, rel(scene.record),
                                      check_ctx["history"]["namespace"])
        except Exception as exc:  # noqa: BLE001
            err_s5b = exc
        e.check("B1.3 精确恢复后 S5 复确认通过",
                err_s5b is None, getattr(err_s5b, "field", None))
        release_error = rt._release_initial_lock(held)
        e.check("B1.4 S5 控制锁按已持有句柄释放",
                release_error is None and not scene.lock.exists(), release_error)

        witness = call("witness.initial_request",
                       rt.prepare_runtime_initial_judgment_request, BATCH, scene.leaf,
                       "TECH-REQ-IJ-0001", phase="request", **scene.params,
                       history_expectations=expectations_block(scene, []))
        if witness[0] is not None:
            raise witness[0]
        materials_fingerprint = witness[1]["request"]["materials"]["materials_fingerprint"]
        submission = build_submission(registry, materials_fingerprint, "TECH-REQ-IJ-0001", "2")
        submission_ref = submission
        submission_before = copy.deepcopy(submission)
        history_before = expectations_block(scene, [])
        err, saved, save_call = call("save.initial", rt.save_runtime_initial_judgment, BATCH,
                                     scene.leaf, "TECH-REQ-IJ-0001", submission,
                                     rel(scene.record), phase="save", **scene.params,
                                     history_expectations=history_before)
        e.check("S0 保存成功（无异常）", err is None, type(err).__name__ if err else None)
        if err is not None:
            raise err
        e.check("S1 返回恰台账十二键", sorted(saved) == independent["success_keys"],
                sorted(saved))
        e.check("S2 状态/scope/说明常量",
                saved["status"] == independent["success_status_save"]
                and saved["scope"] == independent["scope"]
                and saved["note"].startswith("仅表示合成运行"), saved["status"])
        e.check("S3 九权限边界严格 false 且键集等于台账",
                saved["boundaries"] == independent["boundaries"], saved["boundaries"])
        e.check("S4 身份等于台账批次/event2/技术请求",
                saved["identity"] == independent["identity"], saved["identity"])
        e.check("S5 storage_verification 恰台账十一键",
                sorted(saved["storage_verification"]) == independent["storage_keys"],
                sorted(saved["storage_verification"]))
        e.check("S6 manifest FILE/record 指纹与目标磁盘字节一致",
                saved["manifest_file_sha256"]
                == identity(scene.record / "manifest.json")["sha256"]
                and saved["record_fingerprint"]
                == fp(read(scene.record / "judgment_result.json")["record"]), None)
        record = read(scene.record / "judgment_result.json")["record"]
        e.check("S7 核心 persisted=false 且记录状态为已校验",
                record["boundaries"]["persisted"] is False
                and record["record_status"] == "HUMAN_INITIAL_JUDGMENT_VALIDATED",
                record["record_status"])
        e.check("S8 目标叶/封装集合等于台账",
                sorted(p.name for p in scene.record.iterdir())
                == sorted(independent["leaf_files"])
                and sorted(p.name for p in scene.envelope.iterdir())
                == sorted(independent["envelope_files"]) and not scene.lock.exists(), None)
        e.check("S9 原 submission 引用三时点不变且无别名",
                submission is submission_ref
                and canon(submission) == canon(submission_before)
                and canon(read(scene.record / "submission.json")) == canon(submission_before),
                None)
        e.check("S10 原 history_expectations 未被改写",
                canon(history_before) == canon(expectations_block(scene, [])), None)
        delta = e.API_RECORDS[-1]["actual_entries"]
        results["save_graph"] = {key: delta.get(key, 0) for key in independent["save_graph"]}
        e.check("S11 保存调用图等于台账公式",
                all(delta.get(key, 0) == value
                    for key, value in independent["save_graph"].items()), results["save_graph"])
        results["save_call_id"] = save_call
        envelope_before = tree_snapshot(scene.envelope)
        current = [leaf_entry(scene, "rec_0001")]
        err, verified, _ = call("verify.initial", rt.verify_runtime_initial_judgment, BATCH,
                                scene.leaf, phase="request", **scene.params,
                                record_relative=rel(scene.record),
                                history_expectations=expectations_block(scene, current))
        e.check("V1 恢复返回 VERIFIED 且稳定字段与保存一致",
                err is None and verified["status"] == "RT_HUMAN_INITIAL_JUDGMENT_VERIFIED"
                and verified["identity"] == saved["identity"]
                and verified["record_fingerprint"] == saved["record_fingerprint"]
                and verified["manifest_file_sha256"] == saved["manifest_file_sha256"]
                and {k: v for k, v in verified["storage_verification"].items() if k != "status"}
                == {k: v for k, v in saved["storage_verification"].items() if k != "status"},
                getattr(err, "field", None))
        vdelta = e.API_RECORDS[-1]["actual_entries"]
        results["verify_graph_m1"] = {key: vdelta.get(key, 0)
                                      for key in independent["verify_graph_m1"]}
        e.check("V2 m=1 恢复调用图等于台账公式",
                all(vdelta.get(key, 0) == value
                    for key, value in independent["verify_graph_m1"].items()),
                results["verify_graph_m1"])
        e.check("V3 m=1 历史记录等于台账",
                [r["event_id"] for r in
                 verified["history_verification"]["prior_history"]["records"]]
                == independent["h1_records"], None)
        e.check("V4 storage_verification 十一键键集（恢复）",
                sorted(verified["storage_verification"]) == independent["storage_keys"], None)
        e.check("V5 恢复全程未写目标/封装", tree_snapshot(scene.envelope) == envelope_before, None)
        pre_copy_ctx = rt._capture_initial_sources_038(
            BATCH, scene.leaf, dict(scene.params), expectations_block(scene, current))
        copy_task037_leaf(scene, "z_first")
        later = sorted([leaf_entry(scene, "rec_0001"), leaf_entry(scene, "z_first")],
                       key=lambda item: item["relative"].encode("utf-8"))
        envelope_after_copy = tree_snapshot(scene.envelope)
        err, verified_later, _ = call("verify.later_batch", rt.verify_runtime_initial_judgment,
                                      BATCH, scene.leaf, phase="request", **scene.params,
                                      record_relative=rel(scene.record),
                                      history_expectations=expectations_block(scene, later))
        e.check("R1 后来其他 batch 合法叶使 Hc>H1 时仍 VERIFIED",
                err is None and verified_later["status"] == "RT_HUMAN_INITIAL_JUDGMENT_VERIFIED"
                and [r["event_id"] for r in
                     verified_later["history_verification"]["prior_history"]["records"]]
                == independent["hc_records"], getattr(err, "field", None))
        ldelta = e.API_RECORDS[-1]["actual_entries"]
        results["verify_graph_m2"] = {key: ldelta.get(key, 0)
                                      for key in independent["verify_graph_m2"]}
        e.check("R2 m=2 恢复调用图等于台账公式",
                all(ldelta.get(key, 0) == value
                    for key, value in independent["verify_graph_m2"].items()),
                results["verify_graph_m2"])
        context_stored = read(scene.envelope / "context.json")
        e.check("R3 旧 P0/H1/receipt/封装字节未变",
                tree_snapshot(scene.envelope) == envelope_after_copy
                and read(scene.record / "prior_history.json")["records"] == []
                and read(scene.envelope / "receipt.json")["post_history_fingerprint"]
                == fp(context_stored["post_history_verification"]["prior_history"]), None)

        call("verify.incomplete_entries", rt.verify_runtime_initial_judgment, BATCH, scene.leaf,
             phase="request", field="history.expectations.expected_entries", **scene.params,
             record_relative=rel(scene.record),
             history_expectations=expectations_block(scene, later[1:]))
        held = rt._acquire_initial_lock(scene.lock, namespace_relative=rel(scene.namespace),
                                        runtime_relative=rel(scene.leaf),
                                        record_relative=rel(scene.record),
                                        request_id="TECH-REQ-IJ-LOCK")
        try:
            call("verify.lock_present", rt.verify_runtime_initial_judgment, BATCH, scene.leaf,
                 phase="request", field="lock", **scene.params,
                 record_relative=rel(scene.record),
                 history_expectations=expectations_block(scene, later))
        finally:
            release_error = rt._release_initial_lock(held)
        e.check("R4 控制锁按已持有句柄释放", release_error is None and not scene.lock.exists(),
                release_error)

        targeted = scene.record / "manifest.json"
        original = targeted.read_bytes()
        (scene.evidence / "manifest.tampered.bin").write_bytes(original + b"\n")
        targeted.write_bytes(original + b"\n")
        call("verify.record_byte_drift", rt.verify_runtime_initial_judgment, BATCH, scene.leaf,
             phase="request", field="history.entries[0].manifest.json", **scene.params,
             record_relative=rel(scene.record),
             history_expectations=expectations_block(scene, later))
        targeted.write_bytes(original)
        err, restored, _ = call("verify.record_restored", rt.verify_runtime_initial_judgment,
                                BATCH, scene.leaf, phase="request", **scene.params,
                                record_relative=rel(scene.record),
                                history_expectations=expectations_block(scene, later))
        e.check("R5 精确恢复本轮单文件后恢复成功且无失败诊断",
                err is None and restored["status"] == "RT_HUMAN_INITIAL_JUDGMENT_VERIFIED"
                and sorted(p.name for p in scene.record.iterdir()) == sorted(LEAF_FILES), None)

        facts_file = scene.runtime / "normal.facts" / "fact_packet.json"
        facts_original = facts_file.read_bytes()
        (scene.evidence / "facts.tampered.bin").write_bytes(facts_original + b"\n")
        facts_file.write_bytes(facts_original + b"\n")
        call("verify.source_drift", rt.verify_runtime_initial_judgment, BATCH, scene.leaf,
             phase="request", field_prefix="facts.", **scene.params,
             record_relative=rel(scene.record),
             history_expectations=expectations_block(scene, later))
        facts_file.write_bytes(facts_original)
        err, _, _ = call("verify.source_restored", rt.verify_runtime_initial_judgment, BATCH,
                         scene.leaf, phase="request", **scene.params,
                         record_relative=rel(scene.record),
                         history_expectations=expectations_block(scene, later))
        e.check("R6 来源材料精确恢复后再次成功", err is None, None)

        # RC-44 C：receipt.context_file_sha256 以 context 对象 FP 替 writer FILE。
        receipt_path = scene.envelope / "receipt.json"
        receipt_original = receipt_path.read_bytes()
        receipt_value = json.loads(receipt_original)
        context_value = json.loads((scene.envelope / "context.json").read_bytes())
        receipt_value["context_file_sha256"] = fp(context_value)
        (scene.evidence / "rc44_c.tampered.bin").write_bytes(canon(receipt_value) + b"\n")
        receipt_path.write_bytes(canon(receipt_value) + b"\n")
        call("verify.receipt_role_tamper", rt.verify_runtime_initial_judgment, BATCH, scene.leaf,
             phase="request", field="receipt.context_file_sha256", **scene.params,
             record_relative=rel(scene.record),
             history_expectations=expectations_block(scene, later))
        receipt_path.write_bytes(receipt_original)
        err, _, _ = call("verify.receipt_role_restored", rt.verify_runtime_initial_judgment,
                         BATCH, scene.leaf, phase="request", **scene.params,
                         record_relative=rel(scene.record),
                         history_expectations=expectations_block(scene, later))
        e.check("R7 RC-44C 精确恢复 receipt 后恢复成功", err is None, None)

        started_path = scene.envelope / "started.json"
        started_original = started_path.read_bytes()
        started_value = json.loads(started_original)
        started_value["source_binding"]["registry_binding"]["run_binding_sha256"] = \
            sha((scene.leaf / "runtime_registry.json").read_bytes())
        (scene.evidence / "rc44_a_read.tampered.bin").write_bytes(canon(started_value) + b"\n")
        started_path.write_bytes(canon(started_value) + b"\n")
        call("verify.started_role_tamper", rt.verify_runtime_initial_judgment, BATCH, scene.leaf,
             phase="request",
             field="started.source_binding.registry_binding.run_binding_sha256",
             **scene.params, record_relative=rel(scene.record),
             history_expectations=expectations_block(scene, later))
        started_path.write_bytes(started_original)
        err, _, _ = call("verify.started_role_restored", rt.verify_runtime_initial_judgment,
                         BATCH, scene.leaf, phase="request", **scene.params,
                         record_relative=rel(scene.record),
                         history_expectations=expectations_block(scene, later))
        e.check("R8 RC-44A 读路径（started 角色）精确恢复后成功", err is None, None)

        # H4：坏 envelope failure 缺键/未知键精确到 failure.<子键>；非本次目标旧叶缺缓冲显式 Blocked。
        control = scene.evidence / "h4_control_envelope"
        control.mkdir()
        failure_template = {"failure_version": rt.INITIAL_FAILURE_VERSION,
                            "scope": rt.INITIAL_RECORDING_SCOPE, "identity": None,
                            "stage": "bind.store", "classification": "BLOCKED",
                            "field": "lock", "reason": "r", "reasons": ["r"],
                            "exception_type": "RuntimeGate1Blocked",
                            "cause_chain": [{"exception_type": "RuntimeGate1Blocked",
                                             "message": "m"}],
                            "secondary_errors": []}
        missing = dict(failure_template)
        missing.pop("reason")
        (control / "failure.json").write_bytes(canon(missing) + b"\n")
        err_missing = None
        try:
            rt._read_envelope_failure_040(control)
        except Exception as exc:  # noqa: BLE001
            err_missing = exc
        unknown = dict(failure_template, zzz_unknown=1)
        (control / "failure.json").write_bytes(canon(unknown) + b"\n")
        err_unknown = None
        try:
            rt._read_envelope_failure_040(control)
        except Exception as exc:  # noqa: BLE001
            err_unknown = exc
        err_missing_buf = None
        try:
            rt._confirm_initial_history_040(pre_copy_ctx, [current[0], leaf_entry(scene, "z_first")])
        except Exception as exc:  # noqa: BLE001
            err_missing_buf = exc
        results["controls"]["h4"] = {
            "missing_key_field": getattr(err_missing, "field", None),
            "unknown_key_field": getattr(err_unknown, "field", None),
            "missing_buffer_field": getattr(err_missing_buf, "field", None)}
        e.check("H4.1 坏 failure 缺键精确到 failure.<子键>",
                isinstance(err_missing, rt.RuntimeGate1Blocked)
                and err_missing.field == "failure.reason", results["controls"]["h4"])
        e.check("H4.2 坏 failure 未知键精确到 failure.<键>",
                isinstance(err_unknown, rt.RuntimeGate1Blocked)
                and err_unknown.field == "failure.zzz_unknown", results["controls"]["h4"])
        e.check("H4.3 非本次目标旧叶缺缓冲显式 Blocked",
                isinstance(err_missing_buf, rt.RuntimeGate1Blocked)
                and err_missing_buf.field == "history.entries[1]", results["controls"]["h4"])

        results["controls"].update(audit_controls(e, rt, scene, saved))
        results["case_map"] = case_map(results)

        failures = (
            ("f01_bad_submission", "bad_submission", "store.submission.assessment", None),
            ("f03_store_half_write", "store_half_write", None, "write.expectations.json"),
            ("f04_context_half_write", "context_half_write", None, "write.context"),
            ("f05_receipt_sentinel", "receipt_sentinel", None, "write.receipt"),
            ("f06_release_failure", "release_failure", None, "release.lock"),
            ("rc44b_request_role", "request_role",
             "context.prepared_request.request_sha256", None),
            ("h1_candidate_control", "h1_candidate", "result.record_relative", None),
            ("h3_schema_drift", "schema_drift", "sql/demo_schema.sql", None),
        )
        for tag, kind, field, stage in failures:
            results["failure_scenes"].append(
                run_failure_scene(e, rt, o, plain_rt, scene.name + "_" + tag, tag, kind,
                                  field, stage, call))
        return o, results
    finally:
        sys.setprofile(None)


def audit_controls(e, rt, scene, saved):
    """对真实 `_audit_initial_success_040` 做候选内容/类型/首报控制（真实函数仍执行）。"""
    storage = saved["storage_verification"]
    store_save = dict(copy.deepcopy(storage),
                      status="HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_STORED")
    history = saved["history_verification"]
    envelope_captures = {name: rt._capture_file(scene.envelope / name, "control." + name)
                         for name in ENVELOPE_FILES}
    envelope_files = sorted(
        [rt._u040_descriptor(rel(scene.envelope / name), envelope_captures[name]["bytes"],
                             json.loads(envelope_captures[name]["bytes"]))
         for name in ENVELOPE_FILES], key=lambda item: item["relative"].encode("utf-8"))
    expected = rt._build_success_040(store_save, history, "rec_0001", rel(scene.record),
                                     scene.envelope, envelope_files, rt.INITIAL_SAVE_STATUS)

    def audit(candidate, expected_value):
        try:
            rt._audit_initial_success_040(candidate, expected_value, store_save, history,
                                          envelope_captures, envelope_files,
                                          store_save["identity"], rel(scene.record),
                                          rel(scene.envelope), rt.INITIAL_SAVE_STATUS)
            return None
        except Exception as exc:  # noqa: BLE001
            return exc

    def fresh():
        return copy.deepcopy(expected)

    result = {}
    candidate = fresh()
    target = candidate["storage_verification"]["judgment_result"]["record"]
    target["human_initial_judgment"]["assessment"] = "内容错误"
    candidate["storage_verification"]["judgment_result"]["record_fingerprint"] = fp(target)
    err = audit(candidate, fresh())
    result["rc40_content"] = {"type": type(err).__name__, "field": getattr(err, "field", None)}
    e.check("E1.1 RC-40 形状合法但内容错 → Blocked result.<内容字段>",
            isinstance(err, rt.RuntimeGate1Blocked)
            and str(getattr(err, "field", "")).startswith(
                "result.storage_verification.judgment_result.record"), result["rc40_content"])

    candidate = fresh()
    expected_copy = fresh()
    candidate["identity"]["event_id"] = "X"
    expected_copy["identity"]["event_id"] = "X"
    err = audit(candidate, expected_copy)
    result["rc40_audit"] = {"type": type(err).__name__, "stage": getattr(err, "stage", None),
                            "reasons": copy.deepcopy(getattr(err, "reasons", None))}
    e.check("E1.2 RC-40 内部内容审核失败 → Error audit.result 并保留 reasons",
            isinstance(err, rt.RuntimeGate1Error) and err.stage == "audit.result"
            and bool(getattr(err, "reasons", None)), result["rc40_audit"])

    candidate = fresh()
    candidate["boundaries"]["execution_allowed"] = 0
    err = audit(candidate, fresh())
    result["rc08_bool"] = getattr(err, "field", None)
    e.check("E4.1 RC-08 权限 false→0 → Blocked result.boundaries.execution_allowed",
            isinstance(err, rt.RuntimeGate1Blocked)
            and err.field == "result.boundaries.execution_allowed", result["rc08_bool"])

    candidate = fresh()
    size = candidate["envelope_binding"]["files"][0]["byte_size"]
    candidate["envelope_binding"]["files"][0]["byte_size"] = float(size)
    err = audit(candidate, fresh())
    result["rc08_float"] = getattr(err, "field", None)
    e.check("E4.2 RC-08 byte_size 整数→同值 float → Blocked 精确字段",
            isinstance(err, rt.RuntimeGate1Blocked)
            and err.field == "result.envelope_binding.files[0].byte_size", result["rc08_float"])

    bad_a = fresh()
    bad_a["record_relative"] = "data/other/rec"
    bad_a["record_fingerprint"] = "0" * 64
    bad_b = dict(reversed(list(bad_a.items())))
    err_a = audit(bad_a, fresh())
    err_b = audit(bad_b, fresh())
    result["rc09_order"] = {"first": getattr(err_a, "field", None),
                            "reversed": getattr(err_b, "field", None)}
    e.check("E4.3 RC-09 反序字典首报同一字段",
            isinstance(err_a, rt.RuntimeGate1Blocked)
            and isinstance(err_b, rt.RuntimeGate1Blocked)
            and err_a.field == err_b.field == "result.record_fingerprint", result["rc09_order"])
    valid = dict(reversed(list(fresh().items())))
    err_ok = audit(valid, fresh())
    e.check("E4.4 RC-09 纯键序不同的合法候选规范等值通过", err_ok is None,
            getattr(err_ok, "field", None))
    return result


def run_failure_scene(e, rt, o, plain_rt, name, tag, kind, expected_field, expected_stage, call):
    log = []
    scene = Scene(name).create()
    registry = build_chain(plain_rt, scene, log)
    witness = plain_rt.prepare_runtime_initial_judgment_request(
        BATCH, scene.leaf, "TECH-REQ-IJ-F-" + tag, **scene.params,
        history_expectations=expectations_block(scene, []))
    submission = build_submission(registry,
                                  witness["request"]["materials"]["materials_fingerprint"],
                                  "TECH-REQ-IJ-F-" + tag, "2")
    saved = {}
    if kind == "bad_submission":
        submission.pop("assessment")
    elif kind == "stale_materials":
        submission["request_binding"]["materials_fingerprint"] = "0" * 64
    elif kind == "store_half_write":
        # R1-E4：包装真实 writer 句柄写半份后 OSError；真实 writer 函数仍执行。
        real_open = Path.open

        class HalfStream:
            def __init__(self, stream):
                self._stream = stream

            def write(self, data):
                self._stream.write(data[:max(1, len(data) // 2)])
                self._stream.flush()
                raise OSError(5, "TASK040_R1_INJECTED_HALF_WRITE")

            def __enter__(self):
                self._stream.__enter__()
                return self

            def __exit__(self, *args):
                return self._stream.__exit__(*args)

            def __getattr__(self, item):
                return getattr(self._stream, item)

        def patched_open(self, *a, **k):
            stream = real_open(self, *a, **k)
            if Path(self).name == "expectations.json" and scene.record in Path(self).parents:
                saved["half_hit"] = str(self)
                return HalfStream(stream)
            return stream
        Path.open = patched_open
        saved["open"] = real_open
    elif kind in ("context_half_write", "receipt_sentinel"):
        real_write = rt._write_exclusive
        target_name = "context.json" if kind == "context_half_write" else "receipt.json"
        state = {"hit": 0}

        def writer(path, buffer, stage):
            if Path(path).name == target_name and not state["hit"]:
                state["hit"] = 1
                if kind == "context_half_write":
                    with open(path, "xb") as handle:
                        handle.write(buffer[: max(1, len(buffer) // 2)])
                        handle.flush()
                    raise OSError(5, "TASK040_R1_INJECTED_CONTEXT_HALF_WRITE")
                real_write(path, buffer, stage)
                raise OSError(5, "TASK040_R1_SENTINEL_AFTER_RECEIPT_WRITE")
            return real_write(path, buffer, stage)
        rt._write_exclusive = writer
        saved["writer"] = real_write
    elif kind == "release_failure":
        real_release = rt._release_initial_lock
        rt._release_initial_lock = lambda lock: "TASK040_R1_INJECTED_RELEASE_FAILURE"
        saved["release"] = real_release
    elif kind == "started_role":
        real_started = rt._initial_started_040

        def started_role(*a, **k):
            value = real_started(*a, **k)
            sources = a[7]
            value["source_binding"]["registry_binding"]["run_binding_sha256"] = \
                sources["leaf_captures"]["registry"]["file_sha256"]
            return value
        rt._initial_started_040 = started_role
        saved["started"] = real_started
    elif kind == "request_role":
        real_context = rt._initial_context_040

        def context_role(*a, **k):
            value = real_context(*a, **k)
            request = value["prepared_request"]["request"]
            value["prepared_request"]["request_sha256"] = sha(canon(request) + b"\n")
            return value
        rt._initial_context_040 = context_role
        saved["context"] = real_context
    elif kind == "h1_candidate":
        real_build = rt._build_success_040

        def candidate_control(*a, **k):
            value = real_build(*a, **k)
            value["record_relative"] = "data/other/rec"
            return value
        rt._build_success_040 = candidate_control
        saved["build"] = real_build
    elif kind == "schema_drift":
        real_write = rt._write_exclusive
        schema_path = ROOT / "sql/demo_schema.sql"
        original_schema = schema_path.read_bytes()
        saved["schema_original"] = original_schema
        saved["schema_path"] = schema_path
        drift_state = {"hit": 0}

        def drift_writer(path, buffer, stage):
            result = real_write(path, buffer, stage)
            if Path(path).name == "started.json" and not drift_state["hit"]:
                drift_state["hit"] = 1
                handle = os.open(schema_path, os.O_WRONLY | os.O_TRUNC)
                try:
                    os.write(handle, original_schema + b"\n")
                finally:
                    os.close(handle)
            return result
        rt._write_exclusive = drift_writer
        saved["writer"] = real_write
    previous_roots = (o.allowed_roots, o.allowed_write_roots)
    o.allowed_roots = list(scene.roots())
    o.allowed_write_roots = list(scene.roots())
    try:
        err, value, call_id = call("failure." + tag, rt.save_runtime_initial_judgment, BATCH,
                                   scene.leaf, "TECH-REQ-IJ-F-" + tag, submission,
                                   rel(scene.record), phase="save", field=expected_field,
                                   stage=expected_stage, **scene.params,
                                   history_expectations=expectations_block(scene, []))
    finally:
        o.allowed_roots, o.allowed_write_roots = previous_roots
        if "open" in saved:
            Path.open = saved["open"]
        if "writer" in saved:
            rt._write_exclusive = saved["writer"]
        if "release" in saved:
            rt._release_initial_lock = saved["release"]
        if "started" in saved:
            rt._initial_started_040 = saved["started"]
        if "context" in saved:
            rt._initial_context_040 = saved["context"]
        if "build" in saved:
            rt._build_success_040 = saved["build"]
        if "schema_original" in saved:
            saved["schema_path"].write_bytes(saved["schema_original"])
    delta = e.API_RECORDS[-1].get("actual_entries", {}) if e.API_RECORDS else {}
    observation = {"scene": name, "control": kind, "setup_operations": log,
                   "expected_field": expected_field, "expected_stage": expected_stage,
                   "observed_field": getattr(err, "field", None),
                   "observed_stage": getattr(err, "stage", None),
                   "observed_type": type(err).__name__ if err else None,
                   "call_id": call_id, "half_writer_hit": saved.get("half_hit"),
                   "record_dir_exists": scene.record.exists(),
                   "envelope_files": (sorted(p.name for p in scene.envelope.iterdir())
                                      if scene.envelope.is_dir() else []),
                   "lock_exists": scene.lock.exists(),
                   "lock_size": (scene.lock.stat().st_size if scene.lock.exists() else None),
                   "store_save_delta": delta.get("initial.store.save", 0),
                   "store_verify_delta": delta.get("initial.store.verify", 0),
                   "core_delta": delta.get("initial.core", 0),
                   "hardening_rebuild_calls": delta.get("hardening.rebuild_success", 0)}
    if expected_field is not None:
        e.check("F " + tag + " Blocked 精确 field",
                getattr(err, "field", None) == expected_field, observation)
    else:
        e.check("F " + tag + " Error 精确 stage",
                getattr(err, "stage", None) == expected_stage, observation)
    if kind == "store_half_write":
        e.check("F " + tag + " 真实 writer 句柄被包装（半写落盘）",
                bool(saved.get("half_hit")) and scene.record.exists(), observation)
    if kind == "h1_candidate":
        e.check("H1.1 公共路径候选构造控制被 S8 完整比较拒绝（result.record_relative）",
                isinstance(err, rt.RuntimeGate1Blocked)
                and err.field == "result.record_relative", observation)
        e.check("H1.2 公共路径控制前真实 store.save/store.verify/core 已执行",
                observation["store_save_delta"] == 1
                and observation["store_verify_delta"] == 1
                and observation["core_delta"] == 2, observation)
    if kind == "schema_drift":
        e.check("H3.1 S5 schema 漂移精确 Blocked 且 store/core 增量 0",
                isinstance(err, rt.RuntimeGate1Blocked)
                and err.field == "sql/demo_schema.sql"
                and observation["store_save_delta"] == 0
                and observation["core_delta"] == 0, observation)
    e.check("F " + tag + " 失败不返回成功值且保留现场",
            err is not None and value is None and scene.lock.exists(), observation)
    return observation


def case_map(results):
    names = {item["control"] for item in results.get("failure_scenes") or []}
    mapping = {("RC-%02d" % number): "NOT_EXECUTED" for number in range(1, 45)}
    mapping["RC-01"] = "实测：n=0 save + m=1 verify（S1-S11/V1-V5），m=2 后来 batch 恢复（R1-R3）"
    mapping["RC-02"] = "引用：零线索字段路径沿 TASK-039-R1 RC-02 已接受关系；本轮未造空命中链"
    mapping["RC-03"] = "引用：暂不能判断由人类原文决定，适配层不解释 assessment"
    mapping["RC-04"] = "实测：可选键省略样式在提交/快照保留（本次提交无 finding_notes/evidence_requests）"
    mapping["RC-05"] = "实测：" + ("bad_submission → store.submission.assessment"
                                if "bad_submission" in names else "未执行")
    mapping["RC-06"] = "引用：非法原始时间由冻结 core 时间校验承担；本轮未单独建链"
    mapping["RC-07"] = ("引用：TASK-040-R1 已接受现场 task040_r1_run_02_f02_stale_materials "
                        "（本轮不重复建链，store.* 同族由 f01 覆盖）")
    mapping["RC-08"] = "实测：E4.1 权限 false→0、E4.2 byte_size 整数→float（真实审核 Blocked result.*）"
    mapping["RC-09"] = "实测：E4.3 反序字典首报同一字段；E4.4 纯键序合法候选规范等值通过"
    mapping["RC-10"] = "引用：Gate/事实前提失败由既有 Gate 核验承担；本轮前提链全通过"
    mapping["RC-11"] = "实测：B1.1 S5 复确认对 Gate1 来源漂移 Blocked、B1.2 store/core 增量 0、B1.3 精确恢复后通过"
    mapping["RC-12"] = "实测：B3.1 错声明域在取锁前 Blocked，无锁/叶/封装、业务增量 0"
    mapping["RC-13"] = "实测：B3.3 错 scope 在取锁前 Blocked，无锁/叶/封装"
    mapping["RC-14"] = "实测：verify.incomplete_entries → history.expectations.expected_entries"
    mapping["RC-15"] = "未执行：需第二条已登记 event 链（本轮链预算）"
    mapping["RC-16"] = "未执行：会永久锁定唯一正常链"
    mapping["RC-17"] = "实测：save.lock_control 与 verify.lock_present 以真实独占句柄持有后拒绝；控制锁按句柄释放"
    mapping["RC-18"] = "未执行：需第二注册叶绑定同一域"
    mapping["RC-19"] = "实测：真实锁存在（f07 折叠为 save.lock_control）；坏锁类型未逐一注入"
    mapping["RC-20"] = "引用：同内容替代锁由真实共享句柄系统拒绝（架构端锁实验）"
    mapping["RC-21"] = "引用：alias/reparse/.. 原链拒绝由既有 TASK-038/039 路径检查承担"
    mapping["RC-22"] = "实测：f03 包装真实 store writer 句柄写半份后 OSError（真实 writer 执行）"
    mapping["RC-23"] = "引用：f03 产生半写诊断现场；坏 failure schema 控制未另建链"
    mapping["RC-24"] = "实测：f04 context 真实半写 Error write.context"
    mapping["RC-25"] = "实测：f05 receipt 真实写后 sentinel Error write.receipt"
    mapping["RC-26"] = "引用：f03 半写诊断保留主异常"
    mapping["RC-27"] = "实测：S8/S11 与 R3（保存后仅加自身目标）"
    mapping["RC-28"] = "未执行：未声明新增叶"
    mapping["RC-29"] = "实测：verify.record_byte_drift / verify.source_drift（末次消费后单文件漂移）"
    mapping["RC-30"] = "实测：verify.record_restored / verify.source_restored / verify.receipt_role_restored"
    mapping["RC-31"] = "实测：verify.initial（m=1 含自身）"
    mapping["RC-32"] = "实测：verify.later_batch（后来其他 batch 叶，Hc=2 > H1=1）"
    mapping["RC-33"] = "未执行：旧引用缺失"
    mapping["RC-34"] = "未执行：旧引用 FP 矛盾"
    mapping["RC-35"] = "未执行：当前域同 batch 第二份"
    mapping["RC-36"] = "未执行：当前域重复 event"
    mapping["RC-37"] = "未执行：旧请求再存（会永久锁定正常链）"
    mapping["RC-38"] = "引用：代码/配置/范围漂移由 registry 绑定拒绝"
    mapping["RC-39"] = "实测：恢复写/时钟/随机/网络/子进程守卫先证明生效、实际命中 0（TASK-040 V5 保留）"
    mapping["RC-40"] = "实测：E1.1 内容错 Blocked result.<内容字段>；E1.2 内部审核失败 Error audit.result 并支配外层"
    mapping["RC-41"] = "实测：CLI replay --mutate ledger-replaced → 1"
    mapping["RC-42"] = "实测：CLI replay --mutate late-drift → 1"
    mapping["RC-43"] = "实测：f06 注入释放失败 → Error release.lock，绝不返回 RECORDED"
    mapping["RC-44"] = ("实测：A rc44a_started → started.source_binding.registry_binding."
                        "run_binding_sha256（S4）；B rc44b_request → "
                        "context.prepared_request.request_sha256（S8）；C verify.receipt_role_tamper "
                        "→ receipt.context_file_sha256（V3）")
    mapping["failure_controls_executed"] = sorted(names)
    return mapping


def resolve_out_dir(raw, *, must_exist=False):
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(TEST_ROOT.resolve())
    except (OSError, ValueError):
        return None, "out-dir 必须位于 %s 之内" % TEST_ROOT
    if must_exist and not resolved.is_dir():
        return None, "目录不存在：%s" % resolved
    if not must_exist and resolved.exists():
        return None, "out-dir 必须从未存在：%s" % resolved
    return resolved, None


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-040-R1 初判保存/恢复测试入口")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--replay")
    parser.add_argument("--mutate", default="none",
                        choices=("none", "candidate-return", "ledger-replaced", "ledger-lf",
                                 "late-drift", "drop-call"))
    args = parser.parse_args(argv)
    out, problem = resolve_out_dir(args.out_dir)
    if problem:
        print(json.dumps({"status": "FAIL", "reason": problem}, ensure_ascii=False))
        return 1
    out.mkdir(parents=True)
    old = load(ROOT / "tests/test_build_demo_human_initial_judgment.py",
               "task040_r1_readonly_helpers_entry")
    e = old.evidence_module()
    e.ROUND["id"] = out.name
    base_build = e.build_candidate

    def build(expected, observer, extra):
        candidate = base_build(expected, observer, extra)
        candidate["summary"]["task"] = "TASK-040-R1"
        candidate["summary"]["observed"] = {
            "code_entries_by_original_code_object": (observer.all_counts() if observer else None),
            "recorded_nested_entries": (len(e.CORE_RECORDS) if observer else None),
            "replay_observations_are_new_calls": (False if observer else None),
            "reason_when_null": None if observer else "replay 只重放定稿观察，不算新调用"}
        candidate["summary"]["results"] = extra
        return candidate
    e.build_candidate = build

    if args.replay:
        source, problem = resolve_out_dir(args.replay, must_exist=True)
        if problem:
            print(json.dumps({"status": "FAIL", "reason": problem}, ensure_ascii=False))
            return 1
        checkpoint = read(source / "expected_observations.json")
        summary = read(source / "summary.json")
        return e.finish(out, checkpoint, args.mutate, None, summary.get("results", {}))

    rt = make_module()
    plain_rt = make_module("task040_r1_runtime_chain_plain")
    o, extra = run(e, rt, plain_rt, out)
    return e.finish(out, e.freeze_expectations(), "none", o, extra)


if __name__ == "__main__":
    raise SystemExit(main())
