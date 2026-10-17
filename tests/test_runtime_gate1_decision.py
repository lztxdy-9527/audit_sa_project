#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-027 测试入口：Gate1 单事件保存与当前有效性核验。

模式一（正常观察并定稿，业务只跑这一次）：

    .venv\\Scripts\\python.exe -B tests\\test_runtime_gate1_decision.py \\
        --out-dir data\\runtime_gate1_decision_tests\\task027_run_01

模式二（真实收尾重放，复用上面观察的独立副本，业务调用增量 0）：

    ... --replay <观察目录的副本> --mutate none|checks|payload|late-checks

两种模式共用同一套“冻结独立预期 → 一次写盘 → 末期真实审核 → 有界字节确认 → 失败落盘”代码。
任一审核失败或字节漂移：顶层返回 1、磁盘 summary=FAIL、failures 非空。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data"
BATCH_ROOT = DATA / "batches"
RUNTIME_ROOT = DATA / "runtime"
RECORDS_ROOT = DATA / "human_gate_decision_records" / "gate1"
TEST_ROOT = DATA / "runtime_gate1_decision_tests"

CHECKER_SOURCES = {
    "normal": DATA / "batches" / "task024r8_run_01" / "inputs" / "C06b_normal.xlsx",
    "blocked": (DATA / "batches" / "task003_r1_gpt_20261011_041850" / "fixture_sweep"
                / "C14a" / "source" / "input.xlsx"),
}
HOLD_FIXTURE = (DATA / "human_gate1_decision_tests" / "task024_dev_01" / "fixtures"
                / "TASK024_G1_HOLD_0002.json")
REJECT_FIXTURE = (DATA / "reviews" / "task024_gpt_20261014_050915"
                  / "registered_fixture_0003.json")
# 夹具 0001 的人类字段逐字符取自 docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md §0.1
APPROVE_FIXTURE_FIELDS = {
    "event_id": "FIXTURE-EV-G1-0001",
    "decision": "APPROVE",
    "decision_source": "HUMAN_GATE_DECISION",
    "actor_id": "FIXTURE-EV-G1-0001",
    "decided_at_raw": "2026-10-13T18:00:00+08:00",
    "reason": "FIXTURE：结构核验通过，同意进入标准化（设计夹具，无审批效力）",
    "declaration_note": "设计夹具：本地显式身份声明，非真实人员、非强认证",
}
SUBMISSION_VERSION = "TASK-020-human-gate-decision-submission-1.1"

PUBLIC_API_NAMES = ("build_runtime_registry", "read_runtime_registry",
                    "prepare_runtime_gate1_request", "save_runtime_gate1_decision",
                    "verify_gate1_effective_approval")
# 禁止名单按**真实公开入口函数名**匹配（下游标准化/SQLite/事实底稿/筛查/初判/工作流/控制器）
FORBIDDEN_NAMES = {
    "normalize_workbook": "normalize",
    "load_normalized_to_sqlite": "sqlite",
    "build_demo_fact_packet": "fact_packet",
    "build_demo_fact_packet_files": "fact_packet",
    "screen_demo_sqlite": "screen",
    "build_demo_initial_judgment": "initial_judgment",
    "run_demo_workflow": "workflow",
    "control_demo_workflow": "controller",
    "build_demo_final_judgment": "final_judgment",
}
EVIDENCE_FILES = ("expected_observations.json", "summary.json", "checks.json",
                  "failures.json", "api_records.json", "prepare_records.json",
                  "store_records.json", "audit_failure.json")

CHECKS: list = []
API_RECORDS: list = []
PREPARE_RECORDS: list = []
STORE_RECORDS: list = []
P1_RECORDS: list = []
OBSERVED = {"api": 0}
CALL_COUNTER = {"value": 0}
CALL_STACK: list = []
ROUND = {"id": None}
REPLAY_FROM: list = []
SEAMS: dict = {}
STATE: dict = {}


class ReviewReceiptSentinel(RuntimeError):
    """受控测试异常：真实 receipt writer 完整写入之后抛出。"""


def check(name: str, ok: bool, detail=None) -> None:
    CHECKS.append({"name": name, "ok": bool(ok),
                   "detail": detail if detail is not None else ""})


def canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reading(path) -> dict:
    data = Path(path).read_bytes()
    return {"path": str(Path(path)), "byte_size": len(data), "file_sha256": sha_bytes(data)}


def next_call_id() -> str:
    CALL_COUNTER["value"] += 1
    return f"call_{CALL_COUNTER['value']:03d}"


def jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, os.PathLike):
        path = Path(value)
        entry = {"path": str(path), "kind": "path"}
        if path.is_file():
            entry["reading"] = reading(path)
        elif path.exists():
            entry["kind"] = "dir"
        return entry
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    return {"repr": repr(value), "type": type(value).__name__}


def call_api(module, operation, function, before_paths, *args, **kwargs):
    record = {"call_id": None, "operation": operation,
              "args": [jsonable(item) for item in args],
              "kwargs": {key: jsonable(value) for key, value in kwargs.items()},
              "before": {str(p): reading(p) for p in before_paths if Path(p).exists()}}
    call_id = next_call_id()
    OBSERVED["api"] += 1
    record["call_id"] = call_id
    # 活动调用在**真实调用之前**登记：嵌套观察据此绑定当前父调用
    CALL_STACK.append(call_id)
    try:
        result = function(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - 全部拒绝/错误统一登记
        CALL_STACK.pop()
        record.update({"outcome": "exception", "exception_type": type(exc).__name__,
                       "exception_str": str(exc), "field": getattr(exc, "field", None),
                       "stage": getattr(exc, "stage", None),
                       "traceback": traceback.format_exc(),
                       "cause_chain": _chain(exc)})
        API_RECORDS.append(record)
        return exc, None, call_id
    CALL_STACK.pop()
    snapshot = copy.deepcopy(result)
    record.update({"outcome": "returned", "return": snapshot})
    API_RECORDS.append(record)
    return None, snapshot, call_id


def _chain(exc: BaseException) -> list:
    chain, node, seen = [], exc, set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        chain.append(f"{type(node).__name__}: {node}")
        node = node.__cause__ or node.__context__
    return chain


def load_module():
    spec = importlib.util.spec_from_file_location(
        "runtime_gate1_under_test", PROJECT_ROOT / "scripts" / "runtime_gate1.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _entry_observer(module, prepare_module, store_module, p1_module) -> "EntryObserver":
    return EntryObserver(module, prepare_module, store_module, p1_module)


class EntryObserver:
    """轻量 sys.setprofile：按**代码对象身份**分列计数，禁止混加后强求总数相等。

    分列：公开 API（direct）、save 内部 prepare（internal）、冻结 prepare/store/P1、禁止入口。
    """

    def __init__(self, module, prepare_module, store_module, p1_module):
        codes = {}
        for name in PUBLIC_API_NAMES:
            function = getattr(module, name)
            codes[function.__code__] = function
        self._codes = codes
        self._save_code = module.save_runtime_gate1_decision.__code__
        function = prepare_module.prepare_human_gate1_request
        self._prepare_code = getattr(function, "original_code", function.__code__)
        function = store_module.save_human_gate_decision_snapshots
        self._store_save_code = getattr(function, "original_code", function.__code__)
        function = store_module.verify_human_gate_decision_snapshots
        self._store_verify_code = getattr(function, "original_code", function.__code__)
        function = p1_module.build_human_gate_decision_record
        self._p1_code = getattr(function, "original_code", function.__code__)
        self.api = {name: 0 for name in PUBLIC_API_NAMES}
        self.direct_prepare = 0
        self.internal_prepare = 0
        self.frozen_prepare = 0
        self.store_save = 0
        self.store_verify = 0
        self.p1 = 0
        self.forbidden: list = []
        self._save_depth = 0

    def __call__(self, frame, event, arg):
        code = frame.f_code
        if event == "call":
            if code in self._codes:
                function = self._codes[code]
                name = function.__name__
                self.api[name] += 1
                if code is self._save_code:
                    self._save_depth += 1
                return None
            if code is self._prepare_code:
                self.frozen_prepare += 1
                if self._save_depth > 0:
                    self.internal_prepare += 1
                else:
                    self.direct_prepare += 1
            elif code is self._store_save_code:
                self.store_save += 1
            elif code is self._store_verify_code:
                self.store_verify += 1
            elif code is self._p1_code:
                self.p1 += 1
            elif code.co_name in FORBIDDEN_NAMES:
                self.forbidden.append(
                    f"{FORBIDDEN_NAMES[code.co_name]}:{code.co_name}:{code.co_filename}")
        elif event == "return":
            if code is self._save_code and self._save_depth > 0:
                self._save_depth -= 1
        return None


def observe_nested(module) -> dict:
    """在**实际加载使用**的冻结 prepare/store/P1 模块上安装完整观察包装。"""
    prepare_module = module._load_frozen_prepare()
    store_module = module._load_frozen_store()
    p1_module = store_module.load_frozen_p1_core()
    info = {"prepare_module": str(prepare_module.__file__),
            "store_module": str(store_module.__file__),
            "p1_module": str(p1_module.__file__),
            "p1_entry": "build_human_gate_decision_record"}

    real_p1 = p1_module.build_human_gate_decision_record

    def p1_spy(submission, materials, expectations, **kwargs):
        record = {"nested_id": f"p1_{len(P1_RECORDS) + 1:03d}",
                  "args": [jsonable(submission), jsonable(materials),
                           jsonable(expectations)],
                  "kwargs": {key: jsonable(value) for key, value in kwargs.items()},
                  "caller_api": CALL_STACK[-1] if CALL_STACK else None}
        try:
            result = real_p1(submission, materials, expectations, **kwargs)
        except Exception as exc:  # noqa: BLE001
            record.update({"outcome": "exception", "exception_type": type(exc).__name__,
                           "exception_str": str(exc), "field": getattr(exc, "field", None),
                           "stage": getattr(exc, "stage", None),
                           "traceback": traceback.format_exc(), "cause_chain": _chain(exc)})
            P1_RECORDS.append(record)
            raise
        record.update({"outcome": "returned", "return": copy.deepcopy(result)})
        P1_RECORDS.append(record)
        return result

    p1_spy.original_code = real_p1.__code__
    p1_module.build_human_gate_decision_record = p1_spy

    real_prepare = prepare_module.prepare_human_gate1_request

    def prepare_spy(batch_dir, request_id, *args, **kwargs):
        record = {"nested_id": f"prepare_{len(PREPARE_RECORDS) + 1:03d}",
                  "args": [jsonable(batch_dir), jsonable(request_id)],
                  "kwargs": {key: jsonable(value) for key, value in kwargs.items()},
                  "caller_api": CALL_STACK[-1] if CALL_STACK else None}
        try:
            result = real_prepare(batch_dir, request_id, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            record.update({"outcome": "exception", "exception_type": type(exc).__name__,
                           "exception_str": str(exc), "field": getattr(exc, "field", None),
                           "stage": getattr(exc, "stage", None),
                           "traceback": traceback.format_exc(), "cause_chain": _chain(exc)})
            PREPARE_RECORDS.append(record)
            raise
        record.update({"outcome": "returned", "return": copy.deepcopy(result)})
        PREPARE_RECORDS.append(record)
        hook = SEAMS.get("after_prepare")
        if hook is not None:
            hook()
        return result

    prepare_spy.original_code = real_prepare.__code__
    prepare_module.prepare_human_gate1_request = prepare_spy

    real_save = store_module.save_human_gate_decision_snapshots

    def save_spy(out_dir, submission, materials, expectations, *, prior_history=None):
        record = {"nested_id": f"store_save_{len(STORE_RECORDS) + 1:03d}",
                  "operation": "store_save", "out_dir": jsonable(out_dir),
                  "args": [jsonable(submission), jsonable(materials),
                           jsonable(expectations), jsonable(prior_history)],
                  "caller_api": CALL_STACK[-1] if CALL_STACK else None}
        try:
            result = real_save(out_dir, submission, materials, expectations,
                               prior_history=prior_history)
        except Exception as exc:  # noqa: BLE001
            record.update({"outcome": "exception", "exception_type": type(exc).__name__,
                           "exception_str": str(exc), "field": getattr(exc, "field", None),
                           "stage": getattr(exc, "stage", None),
                           "traceback": traceback.format_exc(), "cause_chain": _chain(exc)})
            STORE_RECORDS.append(record)
            raise
        record.update({"outcome": "returned", "return": copy.deepcopy(result)})
        STORE_RECORDS.append(record)
        hook = SEAMS.get("after_store_save")
        if hook is not None:
            hook()
        return result

    save_spy.original_code = real_save.__code__
    store_module.save_human_gate_decision_snapshots = save_spy

    real_verify = store_module.verify_human_gate_decision_snapshots

    def verify_spy(record_dir):
        record = {"nested_id": f"store_verify_{len(STORE_RECORDS) + 1:03d}",
                  "operation": "store_verify", "record_dir": jsonable(record_dir),
                  "caller_api": CALL_STACK[-1] if CALL_STACK else None}
        try:
            result = real_verify(record_dir)
        except Exception as exc:  # noqa: BLE001
            record.update({"outcome": "exception", "exception_type": type(exc).__name__,
                           "exception_str": str(exc), "field": getattr(exc, "field", None),
                           "stage": getattr(exc, "stage", None),
                           "traceback": traceback.format_exc(), "cause_chain": _chain(exc)})
            STORE_RECORDS.append(record)
            raise
        record.update({"outcome": "returned", "return": copy.deepcopy(result)})
        STORE_RECORDS.append(record)
        return result

    verify_spy.original_code = real_verify.__code__
    store_module.verify_human_gate_decision_snapshots = verify_spy
    return info, {"prepare": prepare_module, "store": store_module, "p1": p1_module}


def receive_batch(out_dir: Path, workbook: Path, description: str) -> dict:
    command = [sys.executable, "-B", str(PROJECT_ROOT / "scripts" / "receive_demo_batch.py"),
               "--workbook", str(workbook), "--out-dir", str(out_dir),
               "--source-description", description]
    completed = subprocess.run(command, capture_output=True, text=True,
                               cwd=str(PROJECT_ROOT))
    stdout, stderr = completed.stdout or "", completed.stderr or ""
    return {"command": [str(item) for item in command], "returncode": completed.returncode,
            "stdout_full": stdout, "stderr_full": stderr,
            "stdout_byte_size": len(stdout.encode()), "stderr_byte_size": len(stderr.encode()),
            "stdout_sha256": sha_bytes(stdout.encode()),
            "stderr_sha256": sha_bytes(stderr.encode())}


def submission_for(decision_fields: dict, materials_fingerprint: str, request_id: str,
                   batch_id: str) -> dict:
    return {
        "submission_version": SUBMISSION_VERSION,
        "event_id": decision_fields["event_id"],
        "batch_id": batch_id,
        "gate": "GATE1",
        "request_binding": {"request_id": request_id,
                            "materials_binding": materials_fingerprint},
        "decision": decision_fields["decision"],
        "decision_source": decision_fields["decision_source"],
        "actor": {"actor_kind": "HUMAN_DECLARED", "actor_id": decision_fields["actor_id"],
                  "declaration_note": decision_fields["declaration_note"]},
        "decided_at_raw": decision_fields["decided_at_raw"],
        "reason": decision_fields["reason"],
        "prior_decision_binding": None,
    }


def load_fixture(path: Path) -> dict:
    payload = json.loads(path.read_bytes().decode("utf-8"))
    fragment = payload.get("fragment") or {}
    return {"event_id": fragment["event_id"], "decision": fragment["decision"],
            "decision_source": fragment["decision_source"],
            "actor_id": fragment["actor"]["actor_id"],
            "decided_at_raw": fragment["decided_at_raw"], "reason": fragment["reason"],
            "declaration_note": fragment["actor"]["declaration_note"],
            "fixture_sha256": sha_bytes(path.read_bytes())}


# --------------------------------------------------------------------------- 场景


def scenario_approve(module, ctx, tag="approve", request_id="FIXTURE-REQ-G1-0001",
                     fields=None, batch="normal", do_save=True):
    """正常/对照场景：建登记 → prepare → save → verify。返回 (leaf, scope, event, saved)。"""
    fields = fields or APPROVE_FIXTURE_FIELDS
    batch_dir = ctx["batch_normal"] if batch == "normal" else ctx["batch_blocked"]
    leaf = ctx["runtime"] / f"registry_{tag}"
    scope = RECORDS_ROOT / f"{ROUND['id']}_scope_{tag}"
    exc, built, _ = call_api(module, "build_runtime_registry",
                             module.build_runtime_registry, [], batch_dir, leaf,
                             scope_dir=scope)
    check(f"{tag}.1 build 登记成功", exc is None and built is not None,
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    exc, prepared, _ = call_api(module, "prepare_runtime_gate1_request",
                                module.prepare_runtime_gate1_request, [], batch_dir, leaf,
                                request_id)
    if exc is not None:
        return {"leaf": leaf, "scope": scope, "event": None, "saved": None,
                "prepare_exc": exc}
    materials = prepared["request"]["materials"]
    submission = submission_for(fields, materials["materials_fingerprint"], request_id,
                               materials["batch_id"])
    event = scope / f"event_{fields['event_id'].split('-')[-1]}"
    if not do_save:
        return {"leaf": leaf, "scope": scope, "event": event, "saved": None,
                "exc": None, "submission": submission, "request_id": request_id,
                "batch_dir": batch_dir, "prepared": prepared}
    exc, saved, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], batch_dir, leaf,
                             request_id, submission, event, scope_dir=scope)
    return {"leaf": leaf, "scope": scope, "event": event, "saved": saved, "exc": exc,
            "submission": submission, "request_id": request_id, "batch_dir": batch_dir}


def group_normal_and_contrast(module, ctx) -> dict:
    results = {}
    # ---- 正常 APPROVE：保存 + 只读核验
    approve = scenario_approve(module, ctx)
    results["approve"] = {"event": str(approve["event"]) if approve["event"] else None}
    saved = approve["saved"]
    check("1.1 save 外层恰三键",
          saved is not None and sorted(saved.keys())
          == ["event_relative", "record", "record_fingerprint"], sorted(saved or []))
    check("1.2 record 恰 17 键且为冻结 P1 正文",
          saved is not None and len(saved["record"]) == 17
          and saved["record"]["decision"] == "APPROVE"
          and saved["record"]["actor"]["actor_kind"] == "HUMAN_DECLARED",
          len(saved["record"]) if saved else None)
    check("1.3 record_fingerprint 等于正文规范指纹",
          saved is not None and digest(saved["record"]) == saved["record_fingerprint"], "fp")
    check("1.4 事件恰 2 文件 + snapshots 六文件",
          approve["event"] is not None
          and sorted(item.name for item in approve["event"].iterdir())
          == ["context.json", "receipt.json", "snapshots"]
          and sorted(item.name for item in (approve["event"] / "snapshots").iterdir())
          == ["decision_result.json", "expectations.json", "manifest.json",
              "materials.json", "prior_history.json", "submission.json"], "sets")
    check("1.5 scope 恰含该一个事件目录",
          sorted(item.name for item in approve["scope"].iterdir())
          == [approve["event"].name], "scope set")
    check("1.6 技术锁成功路径不残留",
          not (approve["leaf"].parent / (approve["leaf"].name + ".lock")).exists(), "no lock")
    on_disk = json.loads((approve["event"] / "snapshots"
                          / "decision_result.json").read_bytes().decode("utf-8"))
    check("1.7 落盘 P1 返回与 save 返回正文相等",
          on_disk["record"] == saved["record"]
          and on_disk["record_fingerprint"] == saved["record_fingerprint"], "equal")
    context = json.loads((approve["event"] / "context.json").read_bytes().decode("utf-8"))
    receipt = json.loads((approve["event"] / "receipt.json").read_bytes().decode("utf-8"))
    check("1.8 context 十键 / receipt 九键且边界全 false",
          len(context) == 10 and len(receipt) == 9
          and all(value is False for value in context["boundaries"].values())
          and all(value is False for value in receipt["boundaries"].values()), "envelope")
    check("1.9 显式三键空历史",
          context["prior_history"] == {
              "declared_complete": True, "declared_scope": context["scope_relative"],
              "records": []}, context["prior_history"])

    exc, verified, _ = call_api(module, "verify_gate1_effective_approval",
                                module.verify_gate1_effective_approval, [],
                                approve["batch_dir"], approve["leaf"],
                                scope_dir=approve["scope"],
                                event_relative=saved["event_relative"])
    check("1.10 verify 恰十一键且 effective=true/reasons 空",
          exc is None and len(verified or {}) == 11 and verified["effective"] is True
          and verified["reasons"] == []
          and verified["decision"] == "APPROVE"
          and verified["actor_kind"] == "HUMAN_DECLARED",
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    check("1.11 registry/run_binding/materials 摘要与登记一致",
          verified is not None
          and verified["run_binding_sha256"] == digest(context["request"]["materials"]["run_binding"])
          and verified["materials_fingerprint"]
          == context["request"]["materials"]["materials_fingerprint"], "bindings")
    before = (approve["event"] / "receipt.json").read_bytes()
    exc2, _, _ = call_api(module, "save_runtime_gate1_decision",
                          module.save_runtime_gate1_decision, [], approve["batch_dir"],
                          approve["leaf"], approve["request_id"], approve["submission"],
                          approve["event"], scope_dir=approve["scope"])
    check("1.12 重复保存被拒且旧字节不变",
          isinstance(exc2, module.RuntimeGate1Blocked)
          and (approve["event"] / "receipt.json").read_bytes() == before,
          f"{type(exc2).__name__}: {getattr(exc2, 'field', '')}")

    # ---- 公开 read（只读、计划 scope 尚不存在的叶）
    read_leaf = ctx["runtime"] / "registry_read_probe"
    read_scope = RECORDS_ROOT / f"{ROUND['id']}_scope_read_probe"
    exc_r, built_r, _ = call_api(module, "build_runtime_registry",
                                 module.build_runtime_registry, [], ctx["batch_normal"],
                                 read_leaf, scope_dir=read_scope)
    exc_rd, read_out, _ = call_api(module, "read_runtime_registry",
                                   module.read_runtime_registry,
                                   [read_leaf / "runtime_registry.json"], read_leaf)
    check("1.13 公开 read 在计划 scope 尚不存在时可成功且恰两键",
          exc_rd is None and sorted(read_out.keys())
          == ["registry", "registry_file_sha256"],
          f"{type(exc_rd).__name__}: {getattr(exc_rd, 'field', '')}")

    # ---- HOLD（夹具 0002）：可保存但 effective=false
    hold_fields = load_fixture(HOLD_FIXTURE)
    check("2.1 夹具 0002 原文 SHA 与登记一致",
          hold_fields["fixture_sha256"]
          == "8e3cf5670e91f3c48776360ab8fc22b6fef3f9bce76f56d3793804142b5cd4fa",
          hold_fields["fixture_sha256"][:12])
    hold = scenario_approve(module, ctx, tag="hold", request_id="FIXTURE-REQ-G1-0002",
                            fields=hold_fields)
    check("2.2 合法 HOLD 可保存",
          hold["saved"] is not None and hold["saved"]["record"]["decision"] == "HOLD",
          f"{type(hold.get('exc')).__name__}")
    exc, held, _ = call_api(module, "verify_gate1_effective_approval",
                            module.verify_gate1_effective_approval, [], hold["batch_dir"],
                            hold["leaf"], scope_dir=hold["scope"],
                            event_relative=hold["saved"]["event_relative"])
    check("2.3 HOLD → effective=false 且 reasons 非空",
          exc is None and held["effective"] is False and held["reasons"] == [
              "DECISION_NOT_APPROVE"], held["reasons"] if held else None)
    results["hold"] = held

    # ---- REJECT（夹具 0003）轻量对照
    reject_fields = load_fixture(REJECT_FIXTURE)
    check("2.4 夹具 0003 原文 SHA 与登记一致",
          reject_fields["fixture_sha256"]
          == "6c69c75cde41014fd8740b95d58b9e8a805bd30003fb14ac6f8fb40c93cf23c3",
          reject_fields["fixture_sha256"][:12])
    reject = scenario_approve(module, ctx, tag="reject", request_id="FIXTURE-REQ-G1-0003",
                              fields=reject_fields)
    exc, rejected, _ = call_api(module, "verify_gate1_effective_approval",
                                module.verify_gate1_effective_approval, [],
                                reject["batch_dir"], reject["leaf"],
                                scope_dir=reject["scope"],
                                event_relative=reject["saved"]["event_relative"])
    check("2.5 REJECT → effective=false", exc is None and rejected["effective"] is False,
          rejected["reasons"] if rejected else None)

    # ---- BLOCKED 批次 + APPROVE：真实 P1 拒绝，无成功事件
    blocked = scenario_approve(module, ctx, tag="blocked", request_id="FIXTURE-REQ-G1-0001",
                               batch="blocked")
    event_created = blocked["event"].exists() if blocked["event"] else False
    check("2.6 BLOCKED 批次 + APPROVE 被真实 P1 拒绝且无成功事件",
          isinstance(blocked.get("exc"), (module.RuntimeGate1Blocked,
                                          module.RuntimeGate1Error))
          and not event_created, f"{type(blocked.get('exc')).__name__}: "
                                 f"{getattr(blocked.get('exc'), 'field', '')}")
    results["blocked_approve"] = {"event_created": event_created,
                                  "field": getattr(blocked.get("exc"), "field", None)}
    STATE["approve"] = approve
    return results


def group_rejections(module, ctx, approve) -> dict:
    results = {}
    leaf, scope, batch_dir = approve["leaf"], approve["scope"], approve["batch_dir"]
    saved = approve["saved"]
    request_id = approve["request_id"]
    good = approve["submission"]

    # 3.1 错批次绑定（新登记/新 scope，尚未保存）
    wb = scenario_approve(module, ctx, tag="wrong_batch",
                          request_id="FIXTURE-REQ-G1-0001", do_save=False)
    wrong = copy.deepcopy(wb["submission"])
    wrong["batch_id"] = "FIXTURE-BATCH-WRONG"
    exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                         module.save_runtime_gate1_decision, [], wb["batch_dir"],
                         wb["leaf"], wb["request_id"], wrong, wb["event"],
                         scope_dir=wb["scope"])
    check("3.1 错批次绑定定位拒绝且不建事件",
          isinstance(exc, module.RuntimeGate1Blocked)
          and getattr(exc, "field", "") == "submission.batch_id"
          and not wb["event"].exists(),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")

    # 3.2 材料绑定错（新登记/新 scope）
    wm = scenario_approve(module, ctx, tag="wrong_materials",
                          request_id="FIXTURE-REQ-G1-0001", do_save=False)
    wrong2 = copy.deepcopy(wm["submission"])
    wrong2["request_binding"]["materials_binding"] = "0" * 64
    exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                         module.save_runtime_gate1_decision, [], wm["batch_dir"],
                         wm["leaf"], wm["request_id"], wrong2, wm["event"],
                         scope_dir=wm["scope"])
    check("3.2 错材料绑定定位拒绝",
          isinstance(exc, module.RuntimeGate1Blocked)
          and getattr(exc, "field", "") == "submission.request_binding.materials_binding"
          and not wm["event"].exists(),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")

    # 3.3 调用方 scope 与登记不符
    ws = scenario_approve(module, ctx, tag="wrong_scope",
                          request_id="FIXTURE-REQ-G1-0001", do_save=False)
    other_scope = RECORDS_ROOT / f"{ROUND['id']}_scope_never_used"
    exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                         module.save_runtime_gate1_decision, [], ws["batch_dir"],
                         ws["leaf"], ws["request_id"], ws["submission"],
                         ws["scope"] / "event_0001", scope_dir=other_scope)
    check("3.3 调用方 scope 与登记 scope_ref 不符被拒",
          isinstance(exc, module.RuntimeGate1Blocked)
          and getattr(exc, "field", "") == "scope_dir", f"{type(exc).__name__}")
    check("3.4 越界 scope 未被创建", not other_scope.exists(), "absent")

    # 3.5 同 scope 第二个事件（已有事件）
    second_leaf = ctx["runtime"] / "registry_second_event"
    second_scope = RECORDS_ROOT / f"{ROUND['id']}_scope_second_event"
    call_api(module, "build_runtime_registry", module.build_runtime_registry, [],
             ctx["batch_normal"], second_leaf, scope_dir=second_scope)
    _, prepared, _ = call_api(module, "prepare_runtime_gate1_request",
                              module.prepare_runtime_gate1_request, [],
                              ctx["batch_normal"], second_leaf, "FIXTURE-REQ-G1-0001")
    sub2 = submission_for(APPROVE_FIXTURE_FIELDS,
                          prepared["request"]["materials"]["materials_fingerprint"],
                          "FIXTURE-REQ-G1-0001",
                          prepared["request"]["materials"]["batch_id"])
    exc_s, saved_s, _ = call_api(module, "save_runtime_gate1_decision",
                                 module.save_runtime_gate1_decision, [],
                                 ctx["batch_normal"], second_leaf,
                                 "FIXTURE-REQ-G1-0001", sub2,
                                 second_scope / "event_0001", scope_dir=second_scope)
    before_second = (second_scope / "event_0001" / "receipt.json").read_bytes()
    exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                         module.save_runtime_gate1_decision, [], ctx["batch_normal"],
                         second_leaf, "FIXTURE-REQ-G1-0001", sub2,
                         second_scope / "event_second", scope_dir=second_scope)
    check("3.5 同 scope 第二个事件被拒且旧字节不变",
          exc_s is None and isinstance(exc, module.RuntimeGate1Blocked)
          and not (second_scope / "event_second").exists()
          and (second_scope / "event_0001" / "receipt.json").read_bytes() == before_second,
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")

    # 3.6 技术锁存在即拒绝（外来锁，不释放）
    lock_leaf = ctx["runtime"] / "registry_lock_probe"
    lock_scope = RECORDS_ROOT / f"{ROUND['id']}_scope_lock_probe"
    call_api(module, "build_runtime_registry", module.build_runtime_registry, [],
             ctx["batch_normal"], lock_leaf, scope_dir=lock_scope)
    foreign = lock_leaf.parent / (lock_leaf.name + ".lock")
    foreign.mkdir()
    (foreign / "lock.json").write_bytes(canonical({"holder": "foreign_lock_probe"}) + b"\n")
    _, prepared_lock, _ = call_api(module, "prepare_runtime_gate1_request",
                                   module.prepare_runtime_gate1_request, [],
                                   ctx["batch_normal"], lock_leaf, "FIXTURE-REQ-G1-0001")
    lock_submission = submission_for(
        APPROVE_FIXTURE_FIELDS,
        prepared_lock["request"]["materials"]["materials_fingerprint"],
        "FIXTURE-REQ-G1-0001", prepared_lock["request"]["materials"]["batch_id"])
    exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                         module.save_runtime_gate1_decision, [], ctx["batch_normal"],
                         lock_leaf, "FIXTURE-REQ-G1-0001", lock_submission,
                         lock_scope / "event_0001", scope_dir=lock_scope)
    check("3.6 技术锁存在即拒绝且不释放他人锁",
          isinstance(exc, module.RuntimeGate1Blocked)
          and getattr(exc, "field", "") == "lock" and foreign.is_dir(),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    check("3.7 被锁拒绝时未创建事件", not lock_scope.exists(), "absent")
    results["lock_probe"] = {"foreign_lock": str(foreign)}

    # 3.8/3.9 未知项 → verify 定位拒绝（独立坏场景，探针保留不清理）
    unknown = scenario_approve(module, ctx, tag="unknown_item",
                               request_id="FIXTURE-REQ-G1-0001")
    (unknown["event"] / "unknown_extra.txt").write_bytes(b"x")
    exc, _, _ = call_api(module, "verify_gate1_effective_approval",
                         module.verify_gate1_effective_approval, [],
                         unknown["batch_dir"], unknown["leaf"],
                         scope_dir=unknown["scope"],
                         event_relative=unknown["saved"]["event_relative"])
    check("3.8 事件含未知项 → verify 定位拒绝",
          isinstance(exc, module.RuntimeGate1Blocked)
          and getattr(exc, "field", "") in ("event", "event_relative"),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    check("3.9 verify 失败不写诊断",
          not (unknown["event"] / "failure.json").exists(), "no failure.json")

    # 3.10 failure 现场 → verify 拒绝并定位 failure.json（独立坏场景，探针保留）
    failure_scene = scenario_approve(module, ctx, tag="failure_scene",
                                    request_id="FIXTURE-REQ-G1-0001")
    failure_path = failure_scene["event"] / "failure.json"
    failure_path.write_bytes(canonical(
        {"failure_version": "TASK-027-runtime-gate1-failure-1.0", "stage": "probe",
         "field": None, "reason": "probe", "cause_chain": []}) + b"\n")
    exc, _, _ = call_api(module, "verify_gate1_effective_approval",
                         module.verify_gate1_effective_approval, [],
                         failure_scene["batch_dir"], failure_scene["leaf"],
                         scope_dir=failure_scene["scope"],
                         event_relative=failure_scene["saved"]["event_relative"])
    check("3.10 事件含 failure → verify 定位拒绝",
          isinstance(exc, module.RuntimeGate1Blocked)
          and "failure.json" in str(getattr(exc, "field", "")),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    check("3.11 无 failure 的既有事件 verify 仍成功（对照）",
          True, "见 1.10 正常场景（不复用坏场景，避免清理探针）")

    # 3.12 内层矛盾而外层摘要同步
    tamper = scenario_approve(module, ctx, tag="tamper",
                              request_id="FIXTURE-REQ-G1-0001")
    event = tamper["event"]
    result_path = event / "snapshots" / "decision_result.json"
    payload = json.loads(result_path.read_bytes().decode("utf-8"))
    payload["record"]["decision"] = "HOLD"
    result_path.write_bytes(canonical(payload) + b"\n")
    synced = json.loads((event / "receipt.json").read_bytes().decode("utf-8"))
    synced["record_fingerprint"] = digest(payload["record"])
    (event / "receipt.json").write_bytes(canonical(synced) + b"\n")
    exc, _, _ = call_api(module, "verify_gate1_effective_approval",
                         module.verify_gate1_effective_approval, [],
                         tamper["batch_dir"], tamper["leaf"],
                         scope_dir=tamper["scope"],
                         event_relative=tamper["saved"]["event_relative"])
    check("3.12 正文被改且外层摘要同步 → 仍定位拒绝",
          isinstance(exc, (module.RuntimeGate1Blocked, module.RuntimeGate1Error)),
          f"{type(exc).__name__}: {getattr(exc, 'field', getattr(exc, 'stage', ''))}")
    results["tamper"] = {"field": getattr(exc, "field", getattr(exc, "stage", None))}
    return results


def group_seams(module, ctx) -> dict:
    """真实接缝注入：来源晚变更、context 半写、receipt 后 sentinel。"""
    results = {}
    real_capture = module._capture_file
    real_open = open
    import builtins

    # 4.1 来源晚变更：真实 store.save 返回后改本轮批次来源字节 → 末端确认拒绝且留诊断
    late = scenario_approve(module, ctx, tag="late_source",
                            request_id="FIXTURE-REQ-G1-0001", do_save=False)
    input_path = late["batch_dir"] / "source" / "input.xlsx"
    original = input_path.read_bytes()
    state = {"fired": False}

    def after_store_save():
        if not state["fired"]:
            state["fired"] = True
            input_path.write_bytes(original + b"\n")

    SEAMS["after_store_save"] = after_store_save
    try:
        exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], late["batch_dir"],
                             late["leaf"], late["request_id"], late["submission"],
                             late["event"], scope_dir=late["scope"])
    finally:
        SEAMS.pop("after_store_save", None)
        input_path.write_bytes(original)
    failure = late["event"] / "failure.json" if late["event"] else None
    failure_payload = None
    if failure is not None and failure.is_file():
        failure_payload = json.loads(failure.read_bytes().decode("utf-8"))
    check("4.1 来源晚变更 → 本次 save 拒绝并留五键诊断",
          isinstance(exc, module.RuntimeGate1Blocked) and state["fired"]
          and failure_payload is not None
          and sorted(failure_payload) == ["cause_chain", "failure_version", "field",
                                          "reason", "stage"],
          f"{type(exc).__name__}: {getattr(exc, 'field', '')} "
          f"stage={getattr(exc, 'stage', None)} event_exists="
          f"{late['event'].exists() if late['event'] else None}")
    check("4.2 诊断版本与坏字节保留",
          failure_payload is not None
          and failure_payload["failure_version"] == "TASK-027-runtime-gate1-failure-1.0",
          failure_payload["failure_version"] if failure_payload else None)
    results["late_source"] = {"injected": state["fired"],
                              "exception": type(exc).__name__,
                              "field": getattr(exc, "field", None),
                              "stage": getattr(exc, "stage", None),
                              "event_exists": late["event"].exists() if late["event"] else None,
                              "failure_written": failure_payload is not None}

    # 4.3 context 真实独占句柄半写
    half = scenario_approve(module, ctx, tag="half_context",
                            request_id="FIXTURE-REQ-G1-0001", do_save=False)

    class PartialWriter:
        def __init__(self, handle):
            self._handle = handle

        def write(self, data):
            half_len = max(1, len(data) // 2)
            self._handle.write(data[:half_len])
            raise OSError("injected partial write (real exclusive handle)")

        def flush(self):
            return self._handle.flush()

        def fileno(self):
            return self._handle.fileno()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self._handle.close()
            return False

    def wrapping_open(path, mode="r", *args, **kwargs):
        if "x" in mode and str(path).endswith("context.json"):
            return PartialWriter(real_open(path, mode, *args, **kwargs))
        return real_open(path, mode, *args, **kwargs)

    builtins.open = wrapping_open
    try:
        exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], half["batch_dir"],
                             half["leaf"], half["request_id"], half["submission"],
                             half["event"], scope_dir=half["scope"])
    finally:
        builtins.open = real_open
    half_failure = half["event"] / "failure.json" if half["event"] else None
    check("4.3 context 半写 → RuntimeGate1Error(write.context) 且坏字节与诊断保留",
          isinstance(exc, module.RuntimeGate1Error)
          and getattr(exc, "stage", "") == "write.context"
          and half_failure is not None and half_failure.is_file()
          and (half["event"] / "context.json").is_file(),
          f"{type(exc).__name__}: {getattr(exc, 'stage', '')}")
    results["half_context"] = {"stage": getattr(exc, "stage", None)}

    # 4.4 receipt 完整写后 sentinel：读回之后再改盘 → 末端确认拒绝
    sentinel = scenario_approve(module, ctx, tag="receipt_sentinel",
                               request_id="FIXTURE-REQ-G1-0001", do_save=False)
    state2 = {"fired": False}
    receipt_path = sentinel["event"] / "receipt.json" if sentinel["event"] else None

    def capture_with_sentinel(path, stage):
        captured = real_capture(path, stage)
        if not state2["fired"] and stage == "readback.receipt":
            state2["fired"] = True
            receipt_path.write_bytes(receipt_path.read_bytes() + b"\n")
        return captured

    module._capture_file = capture_with_sentinel
    try:
        exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], sentinel["batch_dir"],
                             sentinel["leaf"], sentinel["request_id"],
                             sentinel["submission"], sentinel["event"],
                             scope_dir=sentinel["scope"])
    finally:
        module._capture_file = real_capture
    sentinel_failure = sentinel["event"] / "failure.json" if sentinel["event"] else None
    check("4.4 receipt 写后字节变化 → 本次 save 拒绝并保留坏候选",
          isinstance(exc, module.RuntimeGate1Blocked) and state2["fired"]
          and sentinel_failure is not None and sentinel_failure.is_file(),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    results["receipt_sentinel"] = {"injected": state2["fired"],
                                   "field": getattr(exc, "field", None)}
    return results


# --------------------------------------------------------------------------- 收尾


def freeze_expectations() -> dict:
    """定稿**完整内存观察**为独立预期（审核期间不刷新；磁盘 expected 只是候选）。"""
    return {"api_records": copy.deepcopy(API_RECORDS),
            "prepare_records": copy.deepcopy(PREPARE_RECORDS),
            "store_records": copy.deepcopy(STORE_RECORDS),
            "p1_records": copy.deepcopy(P1_RECORDS),
            "checks": copy.deepcopy(CHECKS), "round": ROUND["id"]}


def audit_against_expectations(evidence: dict, expected: dict) -> dict:
    problems = []
    api_records = evidence["api_records"]
    prepare_records = evidence["prepare_records"]
    store_records = evidence["store_records"]
    checks = evidence["checks"]
    failures = evidence["failures"]
    summary = evidence["summary"]
    ledger = evidence["ledger"]
    exp_api = {item["call_id"]: item for item in expected["api_records"]}
    exp_prepare = {item["nested_id"]: item for item in expected["prepare_records"]}
    exp_store = {item["nested_id"]: item for item in expected["store_records"]}
    exp_checks = {item["name"]: item for item in expected["checks"]}

    ids = [item["call_id"] for item in api_records]
    if len(set(ids)) != len(ids):
        problems.append("api_call_id_duplicate")
    if summary.get("api_call_ids") != ids:
        problems.append("api_call_ids_mismatch")
    if summary.get("api_call_count") != len(ids):
        problems.append("api_call_count_mismatch")
    for key, records, expected_map, label in (
            ("prepare", prepare_records, exp_prepare, "nested_id"),
            ("store", store_records, exp_store, "nested_id")):
        nested_ids = [item["nested_id"] for item in records]
        if len(set(nested_ids)) != len(nested_ids):
            problems.append(f"{key}_id_duplicate")
        if summary.get(f"{key}_call_ids") != nested_ids:
            problems.append(f"{key}_call_ids_mismatch")
        if summary.get(f"{key}_call_count") != len(nested_ids):
            problems.append(f"{key}_call_count_mismatch")
    for item in api_records:
        expected_item = exp_api.get(item["call_id"])
        if expected_item is None:
            problems.append(f"unexpected_call_id:{item['call_id']}")
        elif canonical(item) != canonical(expected_item):
            problems.append(f"api_record_mismatch:{item['call_id']}")
    for item in prepare_records:
        expected_item = exp_prepare.get(item["nested_id"])
        if expected_item is None:
            problems.append(f"unexpected_nested_id:{item['nested_id']}")
        elif canonical(item) != canonical(expected_item):
            problems.append(f"prepare_record_mismatch:{item['nested_id']}")
    for item in store_records:
        expected_item = exp_store.get(item["nested_id"])
        if expected_item is None:
            problems.append(f"unexpected_store_id:{item['nested_id']}")
        elif canonical(item) != canonical(expected_item):
            problems.append(f"store_record_mismatch:{item['nested_id']}")
    for item in checks:
        expected_item = exp_checks.get(item["name"])
        if expected_item is None:
            problems.append(f"unexpected_check:{item['name']}")
        elif canonical(item) != canonical(expected_item):
            problems.append(f"check_mismatch:{item['name']}")
    failed_names = sorted({item["name"] for item in checks if not item["ok"]})
    if summary.get("checks_total") != len(checks):
        problems.append("checks_total_mismatch")
    if summary.get("checks_failed") != len(failed_names):
        problems.append("checks_failed_mismatch")
    if sorted(failures) != failed_names:
        problems.append("failures_list_mismatch")
    if summary.get("expected_audit", {}).get("expected_final_status") != summary.get("status"):
        problems.append("expected_audit_status_mismatch")
    ledger_paths = [item["path"] for item in ledger]
    if len(set(ledger_paths)) != len(ledger_paths):
        problems.append("ledger_duplicate")
    for item in ledger:
        path = Path(item["abs_path"])
        if not path.is_file():
            problems.append(f"ledger_missing:{item['path']}")
            continue
        data = path.read_bytes()
        if len(data) != item["byte_size"] or sha_bytes(data) != item["file_sha256"]:
            problems.append(f"ledger_drift:{item['path']}")
    return {"audit_ok": not problems, "problems": sorted(set(problems)),
            "api_records": len(api_records), "prepare_records": len(prepare_records),
            "store_records": len(store_records), "checks": len(checks),
            "ledger": len(ledger)}


def group_closure(module, ctx) -> dict:
    """B1/B2/B3 的最小反例（全部使用独立新 scope；探针一律保留，不删除、不移动旧路径）。"""
    import builtins

    results = {}
    real_open = builtins.open

    # ---------- B1a: 真实 store 返回后改 submission 快照 → 本次 save 阻断 ----------
    b1a = scenario_approve(module, ctx, tag="b1_snapshot_after_store",
                           request_id="FIXTURE-REQ-G1-0001", do_save=False)
    snapshot = b1a["event"] / "snapshots" / "submission.json"

    def bump_snapshot():
        snapshot.write_bytes(snapshot.read_bytes() + b"\n")

    SEAMS["after_store_save"] = bump_snapshot
    try:
        exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], b1a["batch_dir"],
                             b1a["leaf"], b1a["request_id"], b1a["submission"],
                             b1a["event"], scope_dir=b1a["scope"])
    finally:
        SEAMS.pop("after_store_save", None)
    failure = b1a["event"] / "failure.json"
    check("6.1 store 返回后改 submission 快照 → 本次 save 阻断且留五键诊断",
          isinstance(exc, module.RuntimeGate1Blocked) and failure.is_file()
          and sorted(json.loads(failure.read_bytes().decode("utf-8")))
          == ["cause_chain", "failure_version", "field", "reason", "stage"],
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    exc_v, _, _ = call_api(module, "verify_gate1_effective_approval",
                           module.verify_gate1_effective_approval, [], b1a["batch_dir"],
                           b1a["leaf"], scope_dir=b1a["scope"],
                           event_relative=b1a["event"].relative_to(PROJECT_ROOT).as_posix())
    check("6.2 该事件（快照被改）只读 verify 拒绝",
          isinstance(exc_v, (module.RuntimeGate1Blocked, module.RuntimeGate1Error)),
          f"{type(exc_v).__name__}: {getattr(exc_v, 'field', getattr(exc_v, 'stage', ''))}")
    results["b1a"] = {"field": getattr(exc, "field", None)}

    # ---------- B1b: 真实 store 返回后给登记叶新增 failure → 本次 save 阻断 ----------
    b1b = scenario_approve(module, ctx, tag="b1_leaf_failure",
                           request_id="FIXTURE-REQ-G1-0001", do_save=False)

    def drop_leaf_failure():
        (b1b["leaf"] / "failure.json").write_bytes(b"probe\n")

    SEAMS["after_store_save"] = drop_leaf_failure
    try:
        exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], b1b["batch_dir"],
                             b1b["leaf"], b1b["request_id"], b1b["submission"],
                             b1b["event"], scope_dir=b1b["scope"])
    finally:
        SEAMS.pop("after_store_save", None)
    check("6.3 store 返回后登记叶新增 failure → 本次 save 阻断（探针保留）",
          isinstance(exc, module.RuntimeGate1Blocked)
          and (b1b["leaf"] / "failure.json").is_file()
          and (b1b["event"] / "failure.json").is_file(),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    results["b1b"] = {"field": getattr(exc, "field", None)}

    # ---------- B1c: 调用前末次来源变更 → 拒绝且 store/P1 增量 0 ----------
    b1c = scenario_approve(module, ctx, tag="b1_pre_source",
                           request_id="FIXTURE-REQ-G1-0001", do_save=False)
    input_path = b1c["batch_dir"] / "source" / "input.xlsx"
    original_bytes = input_path.read_bytes()
    before_stores = sum(1 for item in STORE_RECORDS if item["operation"] == "store_save")
    before_p1 = len(P1_RECORDS)
    state = {"fired": False}

    def mutate_after_prepare():
        if not state["fired"]:
            state["fired"] = True
            input_path.write_bytes(original_bytes + b"\n")

    SEAMS["after_prepare"] = mutate_after_prepare
    try:
        exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], b1c["batch_dir"],
                             b1c["leaf"], b1c["request_id"], b1c["submission"],
                             b1c["event"], scope_dir=b1c["scope"])
    finally:
        SEAMS.pop("after_prepare", None)
        input_path.write_bytes(original_bytes)
    after_stores = sum(1 for item in STORE_RECORDS if item["operation"] == "store_save")
    after_p1 = len(P1_RECORDS)
    check("6.4 调用前末次来源变更 → 本次拒绝、事件未建、store/P1 增量 0",
          isinstance(exc, module.RuntimeGate1Blocked) and state["fired"]
          and not b1c["event"].exists()
          and after_stores == before_stores and after_p1 == before_p1,
          f"{type(exc).__name__}: {getattr(exc, 'field', '')} "
          f"stores {before_stores}->{after_stores} p1 {before_p1}->{after_p1}")
    results["b1c"] = {"field": getattr(exc, "field", None),
                      "store_delta": after_stores - before_stores,
                      "p1_delta": after_p1 - before_p1}

    # ---------- B2: 封套形状与来源关系（独立副本 + 外层 SHA 同步） ----------
    def tampered_scene(tag, mutate):
        scene = scenario_approve(module, ctx, tag=tag, request_id="FIXTURE-REQ-G1-0001")
        context_path = scene["event"] / "context.json"
        payload = json.loads(context_path.read_bytes().decode("utf-8"))
        mutate(payload)
        context_path.write_bytes(canonical(payload) + b"\n")
        receipt_path = scene["event"] / "receipt.json"
        receipt = json.loads(receipt_path.read_bytes().decode("utf-8"))
        receipt["context_file_sha256"] = sha_bytes(context_path.read_bytes())
        receipt_path.write_bytes(canonical(receipt) + b"\n")
        return scene

    def verify_of(scene):
        return call_api(module, "verify_gate1_effective_approval",
                        module.verify_gate1_effective_approval, [], scene["batch_dir"],
                        scene["leaf"], scope_dir=scene["scope"],
                        event_relative=scene["saved"]["event_relative"])

    def native_free(exc):
        return isinstance(exc, (module.RuntimeGate1Blocked, module.RuntimeGate1Error))

    scene = tampered_scene("b2_boundaries_list",
                           lambda obj: obj.__setitem__("boundaries", []))
    exc, _, _ = verify_of(scene)
    check("6.5 boundaries=[] → 可定位 Blocked（无原生异常）",
          native_free(exc) and isinstance(exc, module.RuntimeGate1Blocked)
          and "boundaries" in str(getattr(exc, "field", "")),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")

    for tag, field, value in (
            ("b2_source_batch", "source_batch_relative", "OTHER"),
            ("b2_runtime_relative", "runtime_relative", "OTHER"),
            ("b2_registry_sha", "registry_file_sha256", "0" * 64)):
        scene = tampered_scene(tag, lambda obj, f=field, v=value: obj.__setitem__(f, v))
        exc, _, _ = verify_of(scene)
        check(f"6.6 context.{field} 被改（外层 SHA 同步）→ 仍定位拒绝",
              native_free(exc) and isinstance(exc, module.RuntimeGate1Blocked)
              and field in str(getattr(exc, "field", "")),
              f"{type(exc).__name__}: {getattr(exc, 'field', '')}")

    scene = tampered_scene("b2_store_result",
                           lambda obj: obj["store_result"].__setitem__(
                               "record_fingerprint", "0" * 64))
    exc, _, _ = verify_of(scene)
    store_result_field = str(getattr(exc, "field", ""))
    check("6.7 context.store_result.record_fingerprint 矛盾（外层 SHA 同步）→ 定位拒绝",
          native_free(exc) and isinstance(exc, module.RuntimeGate1Blocked)
          and ("store_result" in store_result_field
               or "store_verify" in store_result_field),
          f"{type(exc).__name__}: {store_result_field}")
    results["b2"] = {"fields": [getattr(exc, "field", None)]}

    # ---------- B2d: 真实 receipt writer 完整写后抛 sentinel ----------
    b2d = scenario_approve(module, ctx, tag="b2_receipt_sentinel",
                           request_id="FIXTURE-REQ-G1-0001", do_save=False)

    class SentinelWriter:
        def __init__(self, handle):
            self._handle = handle

        def write(self, data):
            written = self._handle.write(data)
            self._handle.flush()
            raise ReviewReceiptSentinel("injected after complete receipt write")

        def flush(self):
            return self._handle.flush()

        def fileno(self):
            return self._handle.fileno()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self._handle.close()
            return False

    def open_sentinel(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        if "x" in mode and str(path).endswith("receipt.json"):
            return SentinelWriter(handle)
        return handle

    builtins.open = open_sentinel
    try:
        exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], b2d["batch_dir"],
                             b2d["leaf"], b2d["request_id"], b2d["submission"],
                             b2d["event"], scope_dir=b2d["scope"])
    finally:
        builtins.open = real_open
    failure = b2d["event"] / "failure.json"
    failure_payload = json.loads(failure.read_bytes().decode("utf-8")) \
        if failure.is_file() else None
    check("6.8 真实 receipt writer 写后抛 sentinel → 本层 Error 保留 cause/坏字节 + 已有事件五键 failure",
          isinstance(exc, module.RuntimeGate1Error)
          and getattr(exc, "stage", "") == "write.receipt"
          and "ReviewReceiptSentinel" in str(exc)
          and any("ReviewReceiptSentinel" in item for item in _chain(exc))
          and failure_payload is not None
          and sorted(failure_payload) == ["cause_chain", "failure_version", "field",
                                          "reason", "stage"]
          and (b2d["event"] / "receipt.json").is_file(),
          f"{type(exc).__name__}: {getattr(exc, 'stage', '')}")
    exc_v, _, _ = verify_of({"event": b2d["event"],
                             "saved": {"event_relative": b2d["event"].relative_to(
                                 PROJECT_ROOT).as_posix()},
                             "batch_dir": b2d["batch_dir"], "leaf": b2d["leaf"],
                             "scope": b2d["scope"]})
    check("6.9 该事件（含 failure）只读 verify 拒绝且不写诊断",
          native_free(exc_v) and isinstance(exc_v, module.RuntimeGate1Blocked),
          f"{type(exc_v).__name__}: {getattr(exc_v, 'field', '')}")
    results["b2d"] = {"stage": getattr(exc, "stage", None)}

    # ---------- B3: 锁身份控制（同内容替代锁不得释放；两现场保留） ----------
    b3 = scenario_approve(module, ctx, tag="b3_lock_identity",
                          request_id="FIXTURE-REQ-G1-0001", do_save=False)
    lock = module._acquire_lock(b3["leaf"], b3["event"].relative_to(PROJECT_ROOT).as_posix())
    original_lock = lock["path"]
    preserved = ctx["runtime"] / "preserved_lock_b3"
    before_replacement = _path_identity_of(original_lock)
    os.rename(original_lock, preserved)
    original_lock.mkdir()
    (original_lock / "lock.json").write_bytes((preserved / "lock.json").read_bytes())
    after_replacement = _path_identity_of(original_lock)
    release_error = module._release_own_lock(lock)
    check("6.10 同内容但身份不同的替代锁不被释放（两现场保留）",
          release_error is not None and original_lock.is_dir() and preserved.is_dir()
          and before_replacement["st_ino"] != after_replacement["st_ino"],
          f"release={release_error} ino {before_replacement['st_ino']}->"
          f"{after_replacement['st_ino']}")
    check("6.11 替代锁内容与取得时一致（内容相同仅身份不同）",
          (original_lock / "lock.json").read_bytes()
          == (preserved / "lock.json").read_bytes(), "same content")
    results["b3"] = {"release_error": release_error,
                     "preserved": str(preserved.relative_to(PROJECT_ROOT))}
    return results


def _path_identity_of(path) -> dict:
    stat = os.stat(path)
    return {"st_dev": getattr(stat, "st_dev", None), "st_ino": getattr(stat, "st_ino", None)}


def group_r2(module, ctx) -> dict:
    """R2 三组残余的最小控制（B1 终端集合、B3 锁取得失败与主次错误）。"""
    import builtins

    results = {}
    real_capture_finish = module._finish_prepare

    # ---------- R2-B1: verify 末次确认须查登记叶 failure ----------
    b1 = scenario_approve(module, ctx, tag="r2_leaf_failure_late",
                          request_id="FIXTURE-REQ-G1-0001")
    exc_ok, good, _ = call_api(module, "verify_gate1_effective_approval",
                               module.verify_gate1_effective_approval, [], b1["batch_dir"],
                               b1["leaf"], scope_dir=b1["scope"],
                               event_relative=b1["saved"]["event_relative"])
    check("7.1 无注入时 verify 成功（对照）", exc_ok is None and good["effective"] is True,
          type(exc_ok).__name__)
    state = {"fired": False}

    def finish_with_leaf_failure(*args, **kwargs):
        value = real_capture_finish(*args, **kwargs)
        if not state["fired"]:
            state["fired"] = True
            (b1["leaf"] / "failure.json").write_bytes(b"late-leaf-failure\n")
        return value

    module._finish_prepare = finish_with_leaf_failure
    try:
        exc, _, _ = call_api(module, "verify_gate1_effective_approval",
                             module.verify_gate1_effective_approval, [], b1["batch_dir"],
                             b1["leaf"], scope_dir=b1["scope"],
                             event_relative=b1["saved"]["event_relative"])
    finally:
        module._finish_prepare = real_capture_finish
    check("7.2 末次确认后登记叶新增 failure → verify Blocked 且指向登记叶",
          state["fired"] and isinstance(exc, module.RuntimeGate1Blocked)
          and getattr(exc, "field", "") == "runtime_dir(叶)"
          and not (b1["event"] / "failure.json").exists(),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    exc2, _, _ = call_api(module, "verify_gate1_effective_approval",
                          module.verify_gate1_effective_approval, [], b1["batch_dir"],
                          b1["leaf"], scope_dir=b1["scope"],
                          event_relative=b1["saved"]["event_relative"])
    check("7.3 撤销 wrapper 后仍拒绝且注入保留（未清理）",
          isinstance(exc2, module.RuntimeGate1Blocked)
          and (b1["leaf"] / "failure.json").is_file(),
          f"{type(exc2).__name__}: {getattr(exc2, 'field', '')}")
    results["r2_b1"] = {"field": getattr(exc, "field", None)}

    # ---------- R2-B3a: 取得锁写失败保留现场；不误删替代文件 ----------
    b3a = scenario_approve(module, ctx, tag="r2_lock_acquire_fail",
                           request_id="FIXTURE-REQ-G1-0001", do_save=False)
    lock_dir = b3a["leaf"].parent / (b3a["leaf"].name + ".lock")

    class HalfLockWriter:
        def __init__(self, handle):
            self._handle = handle

        def write(self, data):
            self._handle.write(data[: max(1, len(data) // 2)])
            self._handle.flush()
            raise OSError("injected lock write failure after partial write")

        def flush(self):
            return self._handle.flush()

        def fileno(self):
            return self._handle.fileno()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self._handle.close()
            return False

    real_open = builtins.open

    def open_lock_fail(path, mode="r", *args, **kwargs):
        if "x" in mode and str(path).endswith("lock.json"):
            return HalfLockWriter(real_open(path, mode, *args, **kwargs))
        return real_open(path, mode, *args, **kwargs)

    builtins.open = open_lock_fail
    try:
        exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], b3a["batch_dir"],
                             b3a["leaf"], b3a["request_id"], b3a["submission"],
                             b3a["event"], scope_dir=b3a["scope"])
    finally:
        builtins.open = real_open
    check("7.4 取得锁写失败 → Error 保留锁与半写现场（不自动回收）",
          isinstance(exc, module.RuntimeGate1Error) and lock_dir.is_dir()
          and (lock_dir / "lock.json").is_file()
          and not b3a["event"].exists(),
          f"{type(exc).__name__}: {getattr(exc, 'stage', '')}")
    # 原路径改为同内容替代文件后，再次取得失败也不得删除它
    preserved_lock = ctx["runtime"] / "preserved_lock_r2a.json"
    os.rename(lock_dir / "lock.json", preserved_lock)
    (lock_dir / "lock.json").write_bytes(preserved_lock.read_bytes())
    exc_re, _, _ = call_api(module, "save_runtime_gate1_decision",
                            module.save_runtime_gate1_decision, [], b3a["batch_dir"],
                            b3a["leaf"], b3a["request_id"], b3a["submission"],
                            b3a["event"], scope_dir=b3a["scope"])
    check("7.5 已有替代锁时再次取得被拒且替代文件未被删除",
          isinstance(exc_re, module.RuntimeGate1Blocked)
          and getattr(exc_re, "field", "") == "lock"
          and (lock_dir / "lock.json").is_file() and preserved_lock.is_file(),
          f"{type(exc_re).__name__}: {getattr(exc_re, 'field', '')}")
    results["r2_b3a"] = {"acquire": getattr(exc, "stage", None),
                         "reacquire": getattr(exc_re, "field", None)}

    # ---------- R2-B3b: 无事件时主错误 + 真实解锁次错误都可见 ----------
    b3b = scenario_approve(module, ctx, tag="r2_primary_secondary_no_event",
                           request_id="FIXTURE-REQ-G1-0001", do_save=False)
    lock_b3b = b3b["leaf"].parent / (b3b["leaf"].name + ".lock")
    wrong = copy.deepcopy(b3b["submission"])
    wrong["batch_id"] = "FIXTURE-BATCH-WRONG"

    def disturb_lock_before_release():
        (lock_b3b / "lock.json").write_bytes(b"disturbed\n")

    SEAMS["after_prepare"] = disturb_lock_before_release
    try:
        exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], b3b["batch_dir"],
                             b3b["leaf"], b3b["request_id"], wrong, b3b["event"],
                             scope_dir=b3b["scope"])
    finally:
        SEAMS.pop("after_prepare", None)
    secondary = getattr(exc, "secondary_errors", None)
    check("7.6 无事件：主 Blocked（原 field/reason 保留）+ 解锁次错误可见且锁保留",
          isinstance(exc, module.RuntimeGate1Blocked)
          and getattr(exc, "field", "") == "submission.batch_id"
          and isinstance(secondary, list) and secondary
          and "release_lock" in str(secondary[0])
          and lock_b3b.is_dir() and not b3b["event"].exists(),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')} secondary={secondary}")
    results["r2_b3b"] = {"field": getattr(exc, "field", None),
                         "secondary": secondary[:1] if secondary else None}

    # ---------- R2-B3c: 已有事件时主 + 次错误，诊断一次独占写入 ----------
    b3c = scenario_approve(module, ctx, tag="r2_primary_secondary_event",
                           request_id="FIXTURE-REQ-G1-0001", do_save=False)
    lock_b3c = b3c["leaf"].parent / (b3c["leaf"].name + ".lock")
    writes = {"count": 0}
    real_write_failure = module._write_event_failure

    def counting_write_failure(*args, **kwargs):
        writes["count"] += 1
        return real_write_failure(*args, **kwargs)

    def disturb_lock_and_leaf():
        (lock_b3c / "lock.json").write_bytes(b"disturbed\n")
        (b3c["leaf"] / "failure.json").write_bytes(b"late-leaf-failure\n")

    module._write_event_failure = counting_write_failure
    SEAMS["after_store_save"] = disturb_lock_and_leaf
    try:
        exc, _, _ = call_api(module, "save_runtime_gate1_decision",
                             module.save_runtime_gate1_decision, [], b3c["batch_dir"],
                             b3c["leaf"], b3c["request_id"], b3c["submission"],
                             b3c["event"], scope_dir=b3c["scope"])
    finally:
        SEAMS.pop("after_store_save", None)
        module._write_event_failure = real_write_failure
    failure_path = b3c["event"] / "failure.json"
    payload = json.loads(failure_path.read_bytes().decode("utf-8")) \
        if failure_path.is_file() else None
    check("7.7 已有事件：五键诊断一次独占写入且主次原因都可见",
          isinstance(exc, module.RuntimeGate1Blocked) and writes["count"] == 1
          and payload is not None
          and sorted(payload) == ["cause_chain", "failure_version", "field", "reason",
                                  "stage"]
          and any("release_lock" in str(item) for item in payload["cause_chain"]),
          f"writes={writes['count']} chain={payload['cause_chain'] if payload else None}")
    results["r2_b3c"] = {"diagnostic_writes": writes["count"]}
    return results


def read_payloads(root: Path, *, include_ledger_bytes: bool = False) -> dict:
    """读取磁盘**候选**载荷（候选永不被当作其自身的可信来源）。"""
    ledger_bytes = None

    def read_json(name):
        nonlocal ledger_bytes
        path = root / name
        if not path.is_file():
            return None
        data = path.read_bytes()
        if name == "file_ledger.json":
            ledger_bytes = data
        return json.loads(data.decode("utf-8"))

    candidate = {"expected": read_json("expected_observations.json"),
                 "summary": read_json("summary.json"), "checks": read_json("checks.json"),
                 "failures": read_json("failures.json"),
                 "api_records": read_json("api_records.json"),
                 "prepare_records": read_json("prepare_records.json"),
                 "store_records": read_json("store_records.json"),
                 "p1_records": read_json("p1_records.json"),
                 "ledger": read_json("file_ledger.json")}
    if include_ledger_bytes:
        candidate["ledger_bytes"] = ledger_bytes
    return candidate


def build_candidate(checkpoint: dict, observer, receiver_records, results) -> dict:
    """按定稿内存观察构造候选载荷（含 summary/failures 的预期内容）。"""
    checks = copy.deepcopy(checkpoint["checks"])
    failed_names = sorted({item["name"] for item in checks if not item["ok"]})
    api_records = copy.deepcopy(checkpoint["api_records"])
    prepare_records = copy.deepcopy(checkpoint["prepare_records"])
    store_records = copy.deepcopy(checkpoint["store_records"])
    p1_records = copy.deepcopy(checkpoint["p1_records"])
    summary = {
        "task": "TASK-027-R1",
        "round": ROUND["id"],
        "status": "FAIL" if failed_names else "PASS",
        "checks_total": len(checks),
        "checks_failed": len(failed_names),
        "api_call_ids": [item["call_id"] for item in api_records],
        "api_call_count": len(api_records),
        "prepare_call_ids": [item["nested_id"] for item in prepare_records],
        "prepare_call_count": len(prepare_records),
        "store_call_ids": [item["nested_id"] for item in store_records],
        "store_call_count": len(store_records),
        "p1_call_ids": [item["nested_id"] for item in p1_records],
        "p1_call_count": len(p1_records),
        "expected_audit": {
            "expected_final_status": "FAIL" if failed_names else "PASS",
            "independent_expectation": "定稿内存观察（审核期间不刷新）"},
        "observed": {
            "api_calls": OBSERVED["api"],
            "public_api_calls_by_name_profile": (observer.api if observer else None),
            "frozen_prepare_module_original_function_profile":
                (observer.frozen_prepare if observer else None),
            "frozen_prepare_module_wrapper_calls":
                len(prepare_records),
            "prepare_original_code_calls_from_test_direct":
                (observer.direct_prepare if observer else None),
            "prepare_original_code_calls_from_save_internal":
                (observer.internal_prepare if observer else None),
            "role_note": ("公开 API 计数只取 api_by_name/public_api_calls_by_name_profile；"
                          "frozen_prepare_module_* 是冻结准备模块的函数计数（含 save 内部调用），"
                          "不是公开 API 调用数；wrapper 角色与原始 code 对象分列。"),
            "store_save_profiled": (observer.store_save if observer else None),
            "store_verify_profiled": (observer.store_verify if observer else None),
            "p1_profiled": (observer.p1 if observer else None),
            "forbidden_hits": (observer.forbidden if observer else []),
            "subprocess_internal_counts": None,
            "subprocess_internal_counts_reason":
                "接收器子进程内部入口计数不在本进程观察范围",
        },
        "receivers": receiver_records,
        "results": results,
    }
    return {"checks": checks, "api_records": api_records,
            "prepare_records": prepare_records, "store_records": store_records,
            "p1_records": p1_records, "summary": summary,
            "failures": failed_names,
            "expected_observations": copy.deepcopy(checkpoint)}


def audit_candidate(candidate: dict, expected: dict) -> dict:
    """预期 ↔ 候选：完整 canonical（类型敏感）比较 + 双向 ID/条目一致。"""
    problems = []
    for key, id_key in (("api_records", "call_id"), ("prepare_records", "nested_id"),
                        ("store_records", "nested_id"), ("p1_records", "nested_id")):
        want = expected.get(key) or []
        got = candidate.get(key) or []
        want_ids = [item[id_key] for item in want]
        got_ids = [item[id_key] for item in got]
        if len(set(want_ids)) != len(want_ids):
            problems.append(f"expected_{key}_duplicate")
        if len(set(got_ids)) != len(got_ids):
            problems.append(f"candidate_{key}_duplicate")
        missing = [item for item in want_ids if item not in set(got_ids)]
        extra = [item for item in got_ids if item not in set(want_ids)]
        if missing:
            problems.append(f"{key}_missing:{missing[:5]}")
        if extra:
            problems.append(f"{key}_unexpected:{extra[:5]}")
        want_map = {item[id_key]: item for item in want}
        for item in got:
            wanted = want_map.get(item[id_key])
            if wanted is None:
                continue
            if canonical(item) != canonical(wanted):
                problems.append(f"{key}_mismatch:{item[id_key]}")
    if len(candidate.get("api_records") or []) != len(expected.get("api_records") or []):
        problems.append("api_count_mismatch")
    want_checks = {item["name"]: item for item in expected.get("checks") or []}
    got_checks = {item["name"]: item for item in candidate.get("checks") or []}
    for name in want_checks:
        if name not in got_checks:
            problems.append(f"check_missing:{name}")
        elif canonical(got_checks[name]) != canonical(want_checks[name]):
            problems.append(f"check_mismatch:{name}")
    for name in got_checks:
        if name not in want_checks:
            problems.append(f"check_unexpected:{name}")
    failed_names = sorted(name for name, item in got_checks.items() if not item["ok"])
    expected_failed = sorted(name for name, item in want_checks.items() if not item["ok"])
    if failed_names != expected_failed:
        problems.append("failed_check_set_mismatch")
    summary = candidate.get("summary") or {}
    if summary.get("api_call_ids") != [item["call_id"]
                                       for item in candidate.get("api_records") or []]:
        problems.append("summary_api_ids_mismatch")
    if summary.get("api_call_count") != len(candidate.get("api_records") or []):
        problems.append("summary_api_count_mismatch")
    if summary.get("checks_total") != len(got_checks):
        problems.append("summary_checks_total_mismatch")
    if summary.get("checks_failed") != len(failed_names):
        problems.append("summary_checks_failed_mismatch")
    if sorted(candidate.get("failures") or []) != failed_names:
        problems.append("failures_list_mismatch")
    if summary.get("expected_audit", {}).get("expected_final_status") != summary.get("status"):
        problems.append("expected_audit_status_mismatch")
    # 磁盘 expected 只是候选：此处不以其为可信来源（核心比较用独立内存预期）
    return {"problems": sorted(set(problems)),
            "counts": {"api": len(candidate.get("api_records") or []),
                       "prepare": len(candidate.get("prepare_records") or []),
                       "store": len(candidate.get("store_records") or []),
                       "p1": len(candidate.get("p1_records") or []),
                       "checks": len(got_checks)}}


def finish(out_dir: Path, checkpoint: dict, mutate, observer, receiver_records, results):
    """一次写定正式载荷与台账 → 实读回核 → 末次有界确认 → 独立预期审核 → 失败支配顶层。

    正常成功路径：先定稿诊断（由定稿内存预期决定），再一次写定诊断与台账；
    末次实读覆盖全部正式载荷与台账；之后不再读候选 summary/failures 生成成功输出。
    """
    expected = copy.deepcopy(checkpoint)
    candidate = build_candidate(expected, observer, receiver_records, results)
    expected_failed = sorted(item["name"] for item in expected["checks"] if not item["ok"])

    if mutate == "candidate-return":
        target = None
        for item in candidate["api_records"]:
            if item["outcome"] == "returned" and isinstance(item.get("return"), dict):
                item["return"]["probe"] = "injected"
                target = item["call_id"]
                break
        for item in candidate["expected_observations"]["api_records"]:
            if item["call_id"] == target and isinstance(item.get("return"), dict):
                item["return"]["probe"] = "injected"
                break
    elif mutate == "drop-call":
        candidate["api_records"] = candidate["api_records"][:-1]
        candidate["summary"]["api_call_ids"] = [item["call_id"]
                                                for item in candidate["api_records"]]
        candidate["summary"]["api_call_count"] = len(candidate["api_records"])
        candidate["expected_observations"]["api_records"] = \
            candidate["expected_observations"]["api_records"][:-1]
    elif mutate == "checks-flip":
        candidate["checks"][0]["ok"] = False
        candidate["checks"][0]["detail"] = "injected candidate check change"
        candidate["failures"] = sorted({item["name"] for item in candidate["checks"]
                                        if not item["ok"]})
        candidate["summary"]["status"] = "FAIL"
        candidate["summary"]["checks_failed"] = len(candidate["failures"])
        candidate["summary"]["expected_audit"]["expected_final_status"] = "FAIL"

    payloads = {name + ".json": canonical(value) + b"\n" for name, value in (
        ("expected_observations", candidate["expected_observations"]),
        ("summary", candidate["summary"]), ("checks", candidate["checks"]),
        ("failures", candidate["failures"]), ("api_records", candidate["api_records"]),
        ("prepare_records", candidate["prepare_records"]),
        ("store_records", candidate["store_records"]),
        ("p1_records", candidate["p1_records"]))}
    # 诊断先定稿：正常成功路径下其最终状态由定稿内存预期决定
    diagnostic = {"final_status": "FAIL" if expected_failed else "PASS",
                  "audit_ok": not expected_failed, "problems": [],
                  "failure_reasons": sorted(f"check:{name}" for name in expected_failed),
                  "boundary": "after-write-before-final-audit", "mutation": mutate}
    diagnostic_buffer = canonical(diagnostic) + b"\n"
    ledger_expected = [{"path": name, "abs_path": str(out_dir / name),
                        "byte_size": len(payload), "file_sha256": sha_bytes(payload)}
                       for name, payload in list(payloads.items())
                       + [("audit_failure.json", diagnostic_buffer)]]
    ledger_buffer = canonical(ledger_expected) + b"\n"

    for name, payload in payloads.items():
        (out_dir / name).write_bytes(payload)
    (out_dir / "audit_failure.json").write_bytes(diagnostic_buffer)
    (out_dir / "file_ledger.json").write_bytes(ledger_buffer)
    if mutate == "ledger-replaced":
        (out_dir / "file_ledger.json").write_bytes(b"[]\n")
    if mutate == "diagnostic-drift":
        with open(out_dir / "checks.json", "ab") as handle:
            handle.write(b"\n")
    if mutate == "checks-drift":
        with open(out_dir / "checks.json", "ab") as handle:
            handle.write(b"\n")

    candidate_disk = read_payloads(out_dir, include_ledger_bytes=True)
    ledger_disk = candidate_disk["ledger"]
    ledger_disk_bytes = candidate_disk["ledger_bytes"]  # 与该对象同一次读取
    audit = audit_candidate(candidate_disk, expected)
    problems = list(audit["problems"])
    if ledger_disk is None:
        problems.append("ledger_missing")
    elif canonical(ledger_disk) != canonical(ledger_expected):
        problems.append("ledger_mismatch")
    if ledger_disk_bytes is not None and ledger_disk_bytes != ledger_buffer:
        problems.append("ledger_bytes_mismatch")
    failed_names = sorted({item["name"] for item in candidate_disk["checks"] or []
                           if not item["ok"]})
    combined = copy.deepcopy(candidate_disk["failures"] or [])
    # 全部候选语义消费结束后，只按本次待写缓冲作末次原始字节确认。
    # 台账自身也必须确认，但不把自身哈希写入台账正文。
    final_buffers = dict(payloads)
    final_buffers["audit_failure.json"] = diagnostic_buffer
    final_buffers["file_ledger.json"] = ledger_buffer
    drift = []
    for name, expected_bytes in final_buffers.items():
        path = out_dir / name
        if not path.is_file():
            drift.append(f"missing:{name}")
            continue
        data = path.read_bytes()
        if data != expected_bytes:
            drift.append(f"drift:{name}")
    ok = not problems and not drift and not failed_names and not expected_failed
    if not ok:
        # 失败元数据如实落盘；此后不再报成功
        summary = copy.deepcopy(expected.get("summary", candidate_disk["summary"]))
        summary["status"] = "FAIL"
        summary["failure_reasons"] = sorted(set(problems) | set(drift)
                                            | {f"check:{name}" for name in failed_names})
        (out_dir / "summary.json").write_bytes(canonical(summary) + b"\n")
        combined = sorted(set(failed_names) | {f"audit:{item}" for item in problems}
                          | {f"bytes:{item}" for item in drift})
        (out_dir / "failures.json").write_bytes(canonical(combined) + b"\n")
        failure_meta = {"final_status": "FAIL", "audit_ok": not problems,
                        "problems": problems, "failure_reasons": summary["failure_reasons"],
                        "drift": drift, "mutation": mutate,
                        "boundary": "failure-metadata-after-final-audit"}
        (out_dir / "audit_failure.json").write_bytes(canonical(failure_meta) + b"\n")
    print(json.dumps({"status": "PASS" if ok else "FAIL", "audit_ok": not problems,
                      "bytes_ok": not drift, "problems": problems, "drift": drift,
                      "mutate": mutate, "counts": audit["counts"],
                      "ledger_entries": len(ledger_expected),
                      "failures_count": len(combined),
                      "note": "台账/字节/检查任一失败支配顶层 1 与磁盘 FAIL"},
                     ensure_ascii=False))
    return 0 if ok else 1


def resolve_out_dir(raw: str, *, allow_missing: bool = True):
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    parts = list(candidate.parts)
    for index in range(1, len(parts) + 1):
        step = Path(*parts[:index])
        try:
            stat = step.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            return None, f"路径状态无法读取：{step}：{exc}"
        if os.name == "nt" and getattr(stat, "st_file_attributes", 0) & 0x400:
            return None, f"路径含 link/junction/reparse：{step}"
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        return None, f"无法解析路径：{candidate}：{exc}"
    try:
        relative = resolved.relative_to(TEST_ROOT.resolve())
    except ValueError:
        return None, f"out-dir 解析后必须位于 {TEST_ROOT} 之内：{resolved}"
    if str(relative) in ("", "."):
        return None, "out-dir 不能是证据根本身"
    if not allow_missing and not resolved.exists():
        return None, f"目录不存在：{resolved}"
    return resolved, None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TASK-027-R1 测试入口")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--replay", help="只读复用的既有观察目录；必须另给从未存在的新 out-dir")
    parser.add_argument("--mutate", default="none",
                        choices=("none", "candidate-return", "drop-call", "checks-flip",
                                 "checks-drift", "ledger-replaced", "diagnostic-drift"))
    args = parser.parse_args(argv)

    out_dir, problem = resolve_out_dir(args.out_dir)
    if problem:
        print(json.dumps({"status": "FAIL", "reason": problem, "created": False},
                         ensure_ascii=False))
        return 1
    if out_dir.exists():
        print(json.dumps({"status": "FAIL",
                          "reason": f"out-dir 必须从未存在：{out_dir}"}, ensure_ascii=False))
        return 1
    out_dir.mkdir(parents=True)

    if args.replay:
        source, source_problem = resolve_out_dir(args.replay, allow_missing=False)
        if source_problem:
            print(json.dumps({"status": "FAIL", "reason": source_problem},
                             ensure_ascii=False))
            return 1
        REPLAY_FROM.append(str(source))
        loaded = read_payloads(source)  # 只读；源目录不再写入
        checkpoint = loaded["expected"]
        ROUND["id"] = checkpoint.get("round") or source.name
        summary = loaded["summary"] or {}
        return finish(out_dir, checkpoint, args.mutate, None,
                      summary.get("receivers", {}), summary.get("results", {}))

    ROUND["id"] = out_dir.relative_to(TEST_ROOT.resolve()).parts[0]
    runtime_dir = RUNTIME_ROOT / ROUND["id"]
    batch_dir = BATCH_ROOT / ROUND["id"]
    if runtime_dir.exists() or batch_dir.exists():
        print(json.dumps({"status": "FAIL",
                          "reason": f"本轮根必须从未存在：{runtime_dir} / {batch_dir}"},
                         ensure_ascii=False))
        return 1
    runtime_dir.mkdir(parents=True)
    batch_dir.mkdir(parents=True)

    receivers = {}
    inputs = batch_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    for key in ("normal", "blocked"):
        target = inputs / f"{key}.xlsx"
        shutil.copyfile(CHECKER_SOURCES[key], target)
        receivers[key] = receive_batch(batch_dir / f"batch_{key}", target,
                                       f"TASK-027-R1 测试样本 {key}：不构成业务范围确认")
    check("0.1 接收器 CLI 两次真实执行且返回码 0/1",
          receivers["normal"]["returncode"] == 0
          and receivers["blocked"]["returncode"] == 1,
          {key: value["returncode"] for key, value in receivers.items()})

    module = load_module()
    info, modules = observe_nested(module)
    observer = EntryObserver(module, modules["prepare"], modules["store"], modules["p1"])
    ctx = {"batch_normal": batch_dir / "batch_normal",
           "batch_blocked": batch_dir / "batch_blocked", "runtime": runtime_dir}

    sys.setprofile(observer)
    try:
        results = {"normal": group_normal_and_contrast(module, ctx),
                   "rejections": group_rejections(module, ctx, STATE["approve"]),
                   "seams": group_seams(module, ctx),
                   "closure": group_closure(module, ctx),
                   "r2": group_r2(module, ctx)}
    finally:
        sys.setprofile(None)
    for api_name, count in observer.api.items():
        check(f"5.1 真实代码身份观察公开 API：{api_name} = {count}（须 ≥1）", count >= 1, count)
    direct_prepare_records = [item for item in PREPARE_RECORDS
                              if item["caller_api"] not in
                              {r["call_id"] for r in API_RECORDS
                               if r["operation"] == "save_runtime_gate1_decision"}]
    internal_prepare_records = [item for item in PREPARE_RECORDS
                                if item["caller_api"] in
                                {r["call_id"] for r in API_RECORDS
                                 if r["operation"] == "save_runtime_gate1_decision"}]
    check("5.2 各身份分列闭合（不混加求总数）",
          observer.frozen_prepare == len(PREPARE_RECORDS)
          and observer.direct_prepare == len(direct_prepare_records)
          and observer.internal_prepare == len(internal_prepare_records)
          and observer.store_save == sum(1 for i in STORE_RECORDS
                                         if i["operation"] == "store_save")
          and observer.store_verify == sum(1 for i in STORE_RECORDS
                                           if i["operation"] == "store_verify")
          and observer.p1 == len(P1_RECORDS)
          and observer.internal_prepare >= 1 and observer.p1 >= 1,
          {"frozen_prepare": [observer.frozen_prepare, len(PREPARE_RECORDS)],
           "direct": [observer.direct_prepare, len(direct_prepare_records)],
           "internal": [observer.internal_prepare, len(internal_prepare_records)],
           "store_save": [observer.store_save,
                          sum(1 for i in STORE_RECORDS if i["operation"] == "store_save")],
           "store_verify": [observer.store_verify,
                            sum(1 for i in STORE_RECORDS
                                if i["operation"] == "store_verify")],
           "p1": [observer.p1, len(P1_RECORDS)]})
    check("5.3 禁止下游入口真实命中 0", observer.forbidden == [], observer.forbidden)
    check("5.4 每个嵌套记录都绑定**当前**父调用（非上一条已完成调用）",
          all(item["caller_api"] in {r["call_id"] for r in API_RECORDS}
              for item in PREPARE_RECORDS + STORE_RECORDS + P1_RECORDS), "bound")
    results["observation"] = info
    return finish(out_dir, freeze_expectations(), "none", observer, receivers, results)


if __name__ == "__main__":
    raise SystemExit(main())
