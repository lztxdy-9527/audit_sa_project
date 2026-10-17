#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-026-R3 测试入口：补 read 计划 scope 收尾与真实证据裁决。

两种模式：

1. 正常观察并定稿（业务只跑这一次）：

       .venv\\Scripts\\python.exe -B tests\\test_runtime_gate1_registry.py \\
           --out-dir data\\runtime_gate1_registry_tests\\task026r3_run_01

2. 真实收尾重放（复用上面这次观察的独立副本，业务调用增量 0）：

       ... --replay <观察目录的副本> --mutate none|checks|payload|args|late-checks

第 2 种与第 1 种走**同一套**冻结/写盘/审核/字节确认代码；注入只改目标字节或目标字段，
独立期望一字节不动。任一审核失败/漂移都必须：顶层返回 1、磁盘 summary=FAIL、failures 非空。
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
GATE1_RECORDS_ROOT = DATA / "human_gate_decision_records" / "gate1"
TEST_ROOT = DATA / "runtime_gate1_registry_tests"

CHECKER_SOURCES = {
    "normal": DATA / "batches" / "task024r8_run_01" / "inputs" / "C06b_normal.xlsx",
    "blocked": (DATA / "batches" / "task003_r1_gpt_20261011_041850" / "fixture_sweep"
                / "C14a" / "source" / "input.xlsx"),
}

CHECKS: list = []
FAILURES: list = []
API_RECORDS: list = []
PREPARE_RECORDS: list = []
OBSERVED = {"api": 0}
CALL_COUNTER = {"value": 0}
ROUND = {"id": None}
REPLAY_FROM: list = []

FORBIDDEN_NAMES = {
    "build_human_gate_decision_record": "P1",
    "save_human_gate_decision_snapshots": "store",
    "verify_human_gate_decision_snapshots": "store",
    "load_normalized_to_sqlite": "sqlite",
    "normalize_workbook": "normalize",
}
PUBLIC_API_NAMES = ("build_runtime_registry", "read_runtime_registry",
                    "prepare_runtime_gate1_request")

EVIDENCE_FILES = ("expected_observations.json", "summary.json", "checks.json",
                  "failures.json", "api_records.json", "prepare_records.json",
                  "audit_failure.json")


def check(name: str, ok: bool, detail=None) -> None:
    CHECKS.append({"name": name, "ok": bool(ok),
                   "detail": detail if detail is not None else ""})
    if not ok:
        FAILURES.append(name)


def canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reading(path) -> dict:
    data = Path(path).read_bytes()
    return {"path": str(Path(path)), "byte_size": len(data), "file_sha256": sha_bytes(data),
            "is_file": True}


def next_call_id() -> str:
    CALL_COUNTER["value"] += 1
    return f"call_{CALL_COUNTER['value']:03d}"


def jsonable(value):
    """把路径对象等转成可 JSON 化的形式，并保留真实文件现场。"""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, os.PathLike):
        path = Path(value)
        entry = {"path": str(path), "kind": "path"}
        if path.exists() and path.is_file():
            entry["reading"] = reading(path)
        elif path.exists():
            entry["kind"] = "dir"
        return entry
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    return {"repr": repr(value), "type": type(value).__name__}


def call_api(module, operation: str, function, before_paths, *args, **kwargs):
    """同一套轻量记录路径：完整 args/kwargs、调用前读数、返回深拷贝或完整异常。"""
    call_id = next_call_id()
    OBSERVED["api"] += 1
    before = {str(path): reading(path) for path in before_paths if Path(path).exists()}
    record = {"call_id": call_id, "operation": operation,
              "args": [jsonable(item) for item in args],
              "kwargs": {key: jsonable(value) for key, value in kwargs.items()},
              "before": before}
    API_RECORDS.append(record)  # 嵌套观察关联当前正在执行的调用，而不是上一次调用。
    try:
        result = function(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - 全部拒绝/错误统一登记
        record.update({"outcome": "exception", "exception_type": type(exc).__name__,
                       "exception_str": str(exc), "field": getattr(exc, "field", None),
                       "stage": getattr(exc, "stage", None),
                       "traceback": traceback.format_exc(),
                       "cause_chain": _cause_chain(exc)})
        return exc, None, call_id
    snapshot = copy.deepcopy(result)
    record.update({"outcome": "returned", "return": snapshot})
    return None, result, call_id


def _cause_chain(exc: BaseException) -> list:
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


class EntryObserver:
    """轻量 sys.setprofile：按真实代码身份计数公开 API、冻结准备器与禁止入口。"""

    def __init__(self, prepare_module):
        self.api = {name: 0 for name in PUBLIC_API_NAMES}
        self.prepare = 0
        self.forbidden: list = []
        self._runtime_file = str(Path(PROJECT_ROOT / "scripts" / "runtime_gate1.py").resolve())
        self._prepare_file = str(Path(prepare_module.__file__).resolve())

    def __call__(self, frame, event, arg):
        if event == "call":
            filename = frame.f_code.co_filename
            name = frame.f_code.co_name
            if filename == self._runtime_file and name in self.api:
                self.api[name] += 1
            elif filename == self._prepare_file and name == "prepare_human_gate1_request":
                self.prepare += 1
            elif name in FORBIDDEN_NAMES:
                self.forbidden.append(f"{FORBIDDEN_NAMES[name]}:{name}:{filename}")
        return None


def observe_frozen_prepare(prepare_module) -> None:
    """在**实际加载使用的冻结准备器模块**上观察：每次完整输入与完整返回/异常。"""
    real = prepare_module.prepare_human_gate1_request

    def wrapper(batch_dir, request_id, *args, **kwargs):
        before = {}
        batch_path = Path(batch_dir)
        if batch_path.exists():
            before[str(batch_path)] = {"kind": "dir"}
            for name in ("batch_manifest.json", "source/input.xlsx",
                         "checks/quality_report.json"):
                target = batch_path / name
                if target.is_file():
                    before[name] = reading(target)
        record = {"nested_id": f"prepare_{len(PREPARE_RECORDS) + 1:03d}",
                  "args": [jsonable(batch_dir), jsonable(request_id)],
                  "kwargs": {key: jsonable(value) for key, value in kwargs.items()},
                  "before": before,
                  "caller_api": API_RECORDS[-1]["call_id"] if API_RECORDS else None}
        try:
            result = real(batch_dir, request_id, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            record.update({"outcome": "exception", "exception_type": type(exc).__name__,
                           "exception_str": str(exc),
                           "field": getattr(exc, "field", None),
                           "stage": getattr(exc, "stage", None),
                           "traceback": traceback.format_exc(),
                           "cause_chain": _cause_chain(exc)})
            PREPARE_RECORDS.append(record)
            raise
        record.update({"outcome": "returned", "return": copy.deepcopy(result)})
        PREPARE_RECORDS.append(record)
        return result

    prepare_module.prepare_human_gate1_request = wrapper


def receive_batch(out_dir: Path, workbook: Path, description: str) -> dict:
    command = [sys.executable, "-B", str(PROJECT_ROOT / "scripts" / "receive_demo_batch.py"),
               "--workbook", str(workbook), "--out-dir", str(out_dir),
               "--source-description", description]
    completed = subprocess.run(command, capture_output=True, text=True,
                               cwd=str(PROJECT_ROOT))
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {"command": [str(item) for item in command], "returncode": completed.returncode,
            "stdout_full": stdout, "stderr_full": stderr,
            "stdout_byte_size": len(stdout.encode("utf-8")),
            "stderr_byte_size": len(stderr.encode("utf-8")),
            "stdout_sha256": sha_bytes(stdout.encode("utf-8")),
            "stderr_sha256": sha_bytes(stderr.encode("utf-8")),
            "out_dir": str(out_dir)}


# --------------------------------------------------------------------------- 业务观察


def group_normal(module, batch_dir: Path, runtime_dir: Path, scope_dir: Path) -> dict:
    leaf = runtime_dir / "registry_normal"
    exc, built, build_id = call_api(module, "build_runtime_registry",
                                    module.build_runtime_registry,
                                    [batch_dir / "source" / "input.xlsx"],
                                    batch_dir, leaf, scope_dir=scope_dir)
    check("1.1 build 正常控制成功", exc is None and built is not None,
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    registry = built["registry"] if built else {}
    check("1.2 build 外层恰三键",
          built is not None and sorted(built.keys())
          == ["registry", "registry_file_sha256", "registry_sha256"],
          sorted(built.keys()) if built else None)
    check("1.3 registry 恰 13 键", len(registry) == 13
          and sorted(registry) == sorted(module.REGISTRY_KEYS), len(registry))
    check("1.4 返回 SHA 与磁盘一致",
          built is not None and built["registry_file_sha256"]
          == sha_bytes((leaf / "runtime_registry.json").read_bytes()), "sha")
    check("1.5 技术登记时间合法",
          bool(registry) and re.fullmatch(
              r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
              registry["registered_at"]) is not None, registry.get("registered_at"))
    check("1.6 code_manifest 14 / rules_manifest 4",
          len(registry.get("code_manifest", {}).get("entries", [])) == 14
          and len(registry.get("rules_manifest", {}).get("entries", [])) == 4, "14/4")
    check("1.7 batch_files 恰 8 项且与批次实读一致",
          len(registry.get("batch_files", [])) == 8
          and all(item["file_sha256"]
                  == sha_bytes((batch_dir / item["relative"][6:]).read_bytes())
                  for item in registry["batch_files"]), "8")
    check("1.8 成功叶恰两份登记文件且 scope 未被创建",
          sorted(item.name for item in leaf.iterdir())
          == ["runtime_registry.json", "runtime_registry_readback.json"]
          and not scope_dir.exists(), "two")

    exc_r, read, read_id = call_api(module, "read_runtime_registry",
                                    module.read_runtime_registry,
                                    [leaf / "runtime_registry.json",
                                     leaf / "runtime_registry_readback.json"], leaf)
    check("1.9 read 正常控制成功且外层恰两键",
          exc_r is None and sorted(read.keys()) == ["registry", "registry_file_sha256"],
          f"{type(exc_r).__name__}")
    check("1.10 read 返回登记与 build 规范相等",
          read is not None and canonical(read["registry"]) == canonical(registry), "equal")

    exc_p, prepared, prepare_id = call_api(
        module, "prepare_runtime_gate1_request",
        module.prepare_runtime_gate1_request,
        [batch_dir / "source" / "input.xlsx", leaf / "runtime_registry.json"],
        batch_dir, leaf, "FIXTURE-REQ-G1-0001")
    check("1.11 prepare 正常控制成功且外层恰两键",
          exc_p is None and sorted(prepared.keys()) == ["request", "request_sha256"],
          f"{type(exc_p).__name__}")
    request = prepared["request"] if prepared else {}
    check("1.12 request 六键 / files 32 项升序唯一 / boundaries 全 false",
          sorted(request.keys()) == sorted(module.REQUEST_KEYS)
          and len(request["materials"]["files"]) == 32
          and [item["relative"] for item in request["materials"]["files"]]
          == sorted((item["relative"] for item in request["materials"]["files"]),
                    key=lambda v: v.encode("utf-8"))
          and all(value is False for value in request["boundaries"].values()), "shapes")
    check("1.13 request_sha256 为规范指纹",
          prepared is not None and prepared["request_sha256"] == digest(request), "sha")
    for raw_id in ("0001", "line\nbreak", "a" * 64):
        exc_i, out, _ = call_api(module, "prepare_runtime_gate1_request",
                                 module.prepare_runtime_gate1_request,
                                 [batch_dir / "source" / "input.xlsx"], batch_dir, leaf,
                                 raw_id)
        check(f"1.14 request_id 原样保留：{raw_id[:10]!r}",
              exc_i is None
              and out["request"]["expectations"]["expected_request_id"] == raw_id, raw_id)
    for bad in ("", "   ", 7, None):
        exc_b, _, _ = call_api(module, "prepare_runtime_gate1_request",
                               module.prepare_runtime_gate1_request, [], batch_dir, leaf,
                               bad)
        check(f"1.15 非法 request_id 拒绝：{bad!r}",
              isinstance(exc_b, module.RuntimeGate1Blocked), type(exc_b).__name__)
    return {"call_ids": [build_id, read_id, prepare_id],
            "registry_file_sha256": built["registry_file_sha256"] if built else None}


def group_blocked(module, blocked_batch: Path, runtime_dir: Path, scope_dir: Path) -> dict:
    leaf = runtime_dir / "registry_blocked"
    exc, built, _ = call_api(module, "build_runtime_registry",
                             module.build_runtime_registry,
                             [blocked_batch / "source" / "input.xlsx"],
                             blocked_batch, leaf, scope_dir=scope_dir)
    check("2.1 BLOCKED 批次可登记", exc is None and built is not None,
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    exc_p, prepared, _ = call_api(module, "prepare_runtime_gate1_request",
                                  module.prepare_runtime_gate1_request,
                                  [blocked_batch / "source" / "input.xlsx"],
                                  blocked_batch, leaf, "REQ-G1-BLOCKED")
    quality = prepared["request"]["materials"]["quality"] if prepared else {}
    check("2.2 BLOCKED 可候审且保留真实阻断分类",
          exc_p is None and quality.get("status") == "BLOCKED"
          and any("REQUIRED_COLUMN_MISSING" in item
                  for item in quality.get("structural_blockers", [])),
          quality.get("status"))
    check("2.3 来源状态/退出码原样",
          exc_p is None
          and prepared["request"]["evidence"]["source_batch_status"] == "BLOCKED_QUALITY"
          and prepared["request"]["evidence"]["source_receive_exit_code"] == 1, "exit 1")
    return {"blocked_registry_sha256": built["registry_sha256"] if built else None}


def group_read_scope_finish(module, batch_dir: Path, runtime_dir: Path,
                            scope_dir: Path) -> dict:
    """read 末端计划 scope 状态：隔离项目模型（不碰真实记录根）。"""
    base_leaf = runtime_dir / "registry_normal"
    results = {}
    control_exc, _, _ = call_api(module, "read_runtime_registry",
                                 module.read_runtime_registry, [], base_leaf)
    check("3.1 干净路径 read 成功（模型前置条件）", control_exc is None,
          type(control_exc).__name__)

    # 隔离项目模型：镜像 docs/config/scripts/sql 与**空的记录根**，使登记字节可核验、
    # 初始“计划 scope 尚不存在”成立，而末端检查成为唯一拦截点。不碰真实记录根。
    isolated_root = runtime_dir / "isolated_scope_model"
    if isolated_root.exists():
        raise RuntimeError(f"隔离目录已存在，拒绝清理或重建：{isolated_root}")
    isolated_root.mkdir(parents=True)
    for part in ("docs", "config", "scripts", "sql"):
        shutil.copytree(PROJECT_ROOT / part, isolated_root / part)
    (isolated_root / "data" / "human_gate_decision_records" / "gate1").mkdir(parents=True)
    clean_root = isolated_root / "data" / "human_gate_decision_records" / "gate1"
    original_project_root = module.PROJECT_ROOT
    original_records_root = module.GATE1_RECORDS_ROOT
    real_identity = module._require_current_static_identity
    state = {"created": False, "plan": None}

    def identity_with_scope_creation(registry, self_capture, captures):
        real_identity(registry, self_capture, captures)
        if not state["created"]:
            state["created"] = True
            plan = isolated_root / registry["scope_ref"]
            plan.mkdir(parents=True, exist_ok=True)
            state["plan"] = str(plan)

    module.PROJECT_ROOT = isolated_root
    module.GATE1_RECORDS_ROOT = clean_root
    module._require_current_static_identity = identity_with_scope_creation
    try:
        exc, _, _ = call_api(module, "read_runtime_registry", module.read_runtime_registry,
                             [], base_leaf)
    finally:
        module._require_current_static_identity = real_identity
        module.GATE1_RECORDS_ROOT = original_records_root
        module.PROJECT_ROOT = original_project_root
    check("3.2 静态核验后计划 scope 被创建 → 本次 read 拒绝并定位",
          state["created"] and isinstance(exc, module.RuntimeGate1Blocked)
          and getattr(exc, "field", "") == "registry.scope_ref",
          f"{type(exc).__name__}: {getattr(exc, 'field', '')} "
          f"(injected={state['created']}, plan={state['plan']})")
    check("3.3 隔离模型未触碰真实记录根",
          not (GATE1_RECORDS_ROOT / f"{ROUND['id']}_scope").exists(), "clean")
    results["read_scope_finish"] = {
        "injected": state["created"], "plan": state["plan"],
        "field": getattr(exc, "field", None),
        "model": "字节相同的隔离项目根；未在真实记录根建删 scope"}

    existing = next((item for item in sorted(GATE1_RECORDS_ROOT.iterdir())
                     if item.is_dir() and not any(item.iterdir())), None)
    check("3.4 存在可只读复用的既有旧 scope", existing is not None,
          str(existing) if existing else None)
    results["existing_scope"] = str(existing) if existing else None
    return results


# --------------------------------------------------------------------------- 收尾


def freeze_expectations() -> dict:
    """从本次实际完整观察取得独立深拷贝预期（此后不刷新）。"""
    return {"api_records": copy.deepcopy(API_RECORDS),
            "prepare_records": copy.deepcopy(PREPARE_RECORDS),
            "checks": copy.deepcopy(CHECKS), "round": ROUND["id"]}


def audit_against_expectations(evidence: dict, expected: dict) -> dict:
    """同一个真实审核 helper：读对象及长度/SHA → 与独立完整期望比较 → ID/计数/台账。"""
    problems = []
    api_records = evidence["api_records"]
    prepare_records = evidence["prepare_records"]
    checks = evidence["checks"]
    failures = evidence["failures"]
    summary = evidence["summary"]
    ledger = evidence["ledger"]
    expected_api = {item["call_id"]: item for item in expected["api_records"]}
    expected_prepare = {item["nested_id"]: item for item in expected["prepare_records"]}
    expected_checks = {item["name"]: item for item in expected["checks"]}
    if canonical(evidence["expected"]) != canonical(expected):
        problems.append("independent_expectation_changed")

    api_ids = [item["call_id"] for item in api_records]
    if len(set(api_ids)) != len(api_ids):
        problems.append("api_call_id_duplicate")
    if set(api_ids) != set(expected_api) or len(api_ids) != len(expected_api):
        problems.append("api_call_ids_incomplete")
    if summary.get("api_call_ids") != api_ids:
        problems.append("api_call_ids_mismatch")
    if summary.get("api_call_count") != len(api_ids):
        problems.append("api_call_count_mismatch")
    nested_ids = [item["nested_id"] for item in prepare_records]
    if len(set(nested_ids)) != len(nested_ids):
        problems.append("nested_id_duplicate")
    if set(nested_ids) != set(expected_prepare) or len(nested_ids) != len(expected_prepare):
        problems.append("nested_ids_incomplete")
    check_names = [item["name"] for item in checks]
    if set(check_names) != set(expected_checks) or len(check_names) != len(expected_checks):
        problems.append("check_names_incomplete")
    if summary.get("nested_call_ids") != nested_ids:
        problems.append("nested_call_ids_mismatch")
    if summary.get("nested_call_count") != len(nested_ids):
        problems.append("nested_call_count_mismatch")

    for item in api_records:
        expected_item = expected_api.get(item["call_id"])
        if expected_item is None:
            problems.append(f"unexpected_call_id:{item['call_id']}")
            continue
        if canonical(item) != canonical(expected_item):
            problems.append(f"api_record_mismatch:{item['call_id']}")
    for item in prepare_records:
        expected_item = expected_prepare.get(item["nested_id"])
        if expected_item is None:
            problems.append(f"unexpected_nested_id:{item['nested_id']}")
            continue
        if canonical(item) != canonical(expected_item):
            problems.append(f"prepare_record_mismatch:{item['nested_id']}")
    for item in checks:
        expected_item = expected_checks.get(item["name"])
        if expected_item is None:
            problems.append(f"unexpected_check:{item['name']}")
            continue
        if canonical(item) != canonical(expected_item):
            problems.append(f"check_mismatch:{item['name']}")

    failed_names = sorted({item["name"] for item in checks if not item["ok"]})
    if failed_names:
        problems.append("checks_failed")
    if summary.get("checks_total") != len(checks):
        problems.append("checks_total_mismatch")
    if summary.get("checks_failed") != len(failed_names):
        problems.append("checks_failed_mismatch")
    if sorted(failures) != failed_names:
        problems.append("failures_list_mismatch")
    expected_audit = summary.get("expected_audit", {})
    if expected_audit.get("expected_final_status") != summary.get("status"):
        problems.append("expected_audit_status_mismatch")

    ledger_paths = [item["path"] for item in ledger]
    if len(set(ledger_paths)) != len(ledger_paths):
        problems.append("ledger_duplicate")
    for item in ledger:
        path = Path(item["abs_path"])
        if not path.is_file():
            problems.append(f"ledger_missing:{item['path']}")
            continue
        data = evidence["_buffers"].get(item["path"])
        if data is None:
            data = path.read_bytes()
            evidence["_buffers"][item["path"]] = data
        if len(data) != item["byte_size"] or sha_bytes(data) != item["file_sha256"]:
            problems.append(f"ledger_drift:{item['path']}")
    return {"audit_ok": not problems, "problems": sorted(set(problems)),
            "api_records": len(api_records), "prepare_records": len(prepare_records),
            "checks": len(checks), "ledger": len(ledger)}


def load_evidence(root: Path, *, ledger=None) -> dict:
    buffers = {}
    def read_json(name):
        buffers[name] = (root / name).read_bytes()
        return json.loads(buffers[name].decode("utf-8"))

    return {"expected": read_json("expected_observations.json"),
            "summary": read_json("summary.json"), "checks": read_json("checks.json"),
            "failures": read_json("failures.json"),
            "api_records": read_json("api_records.json"),
            "prepare_records": read_json("prepare_records.json"),
            "ledger": read_json("file_ledger.json") if ledger is None else ledger,
            "_buffers": buffers}


def finish(out_dir: Path, checkpoint: dict, mutate, observer, receiver_records,
           results) -> int:
    """同一套真实收尾：冻结 → 写盘 → 末次审核 → 有界字节确认 → 失败落盘。"""
    expected = copy.deepcopy(checkpoint["expected"])
    checks = copy.deepcopy(checkpoint["checks"])
    api_records = copy.deepcopy(checkpoint["api_records"])
    prepare_records = copy.deepcopy(checkpoint["prepare_records"])
    failed_names = sorted({item["name"] for item in checks if not item["ok"]})
    summary = {
        "task": "TASK-026-R3",
        "round": ROUND["id"],
        "status": "FAIL" if failed_names else "PASS",
        "checks_total": len(checks),
        "checks_failed": len(failed_names),
        "api_call_ids": [item["call_id"] for item in api_records],
        "api_call_count": len(api_records),
        "nested_call_ids": [item["nested_id"] for item in prepare_records],
        "nested_call_count": len(prepare_records),
        "expected_audit": {
            "expected_final_status": "FAIL" if failed_names else "PASS",
            "independent_expectation":
                "expected_observations.json（本次完整观察的独立深拷贝）"},
        "observed": {"api_calls": OBSERVED["api"],
                     "prepare_calls_profiled": (observer.prepare if observer else None),
                     "prepare_records": len(prepare_records),
                     "api_by_name": (observer.api if observer else None),
                     "forbidden_hits": (observer.forbidden if observer else []),
                     "subprocess_internal_counts": None,
                     "subprocess_internal_counts_reason":
                         "接收器子进程内部入口计数不在本进程观察范围"},
        "receivers": receiver_records,
        "results": results,
        "replay": {"mutate": mutate,
                   "replay_source": REPLAY_FROM[-1] if REPLAY_FROM else None},
    }
    payloads = {
        "expected_observations.json": canonical(expected) + b"\n",
        "summary.json": canonical(summary) + b"\n",
        "checks.json": canonical(checks) + b"\n",
        "failures.json": canonical(failed_names) + b"\n",
        "api_records.json": canonical(api_records) + b"\n",
        "prepare_records.json": canonical(prepare_records) + b"\n",
    }
    for name, payload in payloads.items():
        (out_dir / name).write_bytes(payload)

    # ---- 注入边界：正常待写缓冲已定稿并写盘之后、正式末次审核之前 ----
    if mutate == "checks":
        checks[0]["ok"] = False
        checks[0]["detail"] = "injected disk-check change after write, before final audit"
        (out_dir / "checks.json").write_bytes(canonical(checks) + b"\n")
        failed_names = sorted({item["name"] for item in checks if not item["ok"]})
    elif mutate == "payload":
        for item in api_records:
            if item["outcome"] == "returned" and isinstance(item.get("return"), dict) \
                    and "registry_file_sha256" in item["return"]:
                item["return"]["registry_file_sha256"] = "0" * 64
                (out_dir / "api_records.json").write_bytes(canonical(api_records) + b"\n")
                break
    elif mutate == "args":
        for item in api_records:
            if item["outcome"] == "returned" and item.get("args"):
                item["args"][0] = "/tmp/task026r3-replaced-input"
                (out_dir / "api_records.json").write_bytes(canonical(api_records) + b"\n")
                break

    # 预期来自本次待写缓冲，不从注入后的候选采集；诊断生成后只写一次最终台账。
    ledger = [{"path": name, "abs_path": str(out_dir / name),
               "byte_size": len(payload), "file_sha256": sha_bytes(payload)}
              for name, payload in sorted(payloads.items())]

    # ---- 正式末次审核（真实 helper）：读盘 + 与独立完整期望比较 ----
    evidence = load_evidence(out_dir, ledger=ledger)
    audit = audit_against_expectations(evidence, expected)
    audit_failure = {
        "content_audit_status": "PASS" if audit["audit_ok"] else "FAIL",
        "audit_ok": audit["audit_ok"], "problems": audit["problems"],
        "failure_reasons": audit["problems"],
        "boundary": "after-write-before-final-audit",
    }
    payloads["audit_failure.json"] = canonical(audit_failure) + b"\n"
    (out_dir / "audit_failure.json").write_bytes(payloads["audit_failure.json"])
    ledger.append({"path": "audit_failure.json", "abs_path": str(out_dir / "audit_failure.json"),
                   "byte_size": len(payloads["audit_failure.json"]),
                   "file_sha256": sha_bytes(payloads["audit_failure.json"])})
    ledger_buffer = canonical(ledger) + b"\n"
    (out_dir / "file_ledger.json").write_bytes(ledger_buffer)
    if mutate == "late-checks":
        with open(out_dir / "checks.json", "ab") as handle:
            handle.write(b"\n")

    # ---- 全部语义消费之后的最后一次有界原始字节确认 ----
    drift = []
    for name, buffer in {**payloads, "file_ledger.json": ledger_buffer}.items():
        path = out_dir / name
        if not path.is_file():
            drift.append(f"missing:{name}")
            continue
        data = path.read_bytes()
        if data != buffer:
            drift.append(f"drift:{name}")
    final_bytes_ok = not drift

    ok = audit["audit_ok"] and final_bytes_ok and not failed_names
    failures_count = len(failed_names)
    if not ok:
        # 失败事实落盘：磁盘 summary=FAIL 且 failures 非空（坏候选保留，不重建期望/台账）
        summary["status"] = "FAIL"
        summary["failure_reasons"] = sorted(set(audit["problems"]) | set(drift))
        (out_dir / "summary.json").write_bytes(canonical(summary) + b"\n")
        combined = sorted(set(failed_names)
                          | {f"audit:{item}" for item in audit["problems"]}
                          | {f"bytes:{item}" for item in drift})
        (out_dir / "failures.json").write_bytes(canonical(combined) + b"\n")
        failures_count = len(combined)
    print(json.dumps({"status": "PASS" if ok else "FAIL", "audit_ok": audit["audit_ok"],
                      "final_bytes_ok": final_bytes_ok, "problems": audit["problems"],
                      "drift": drift, "mutate": mutate, "checks": len(checks),
                      "api_records": len(api_records),
                      "prepare_records": len(prepare_records),
                      "disk_status": summary["status"],
                      "failures_count": failures_count,
                      "note": "审核失败/漂移 → 顶层 1、磁盘 FAIL、failures 非空"},
                     ensure_ascii=False))
    return 0 if ok else 1


def checkpoint() -> dict:
    return {"expected": freeze_expectations(), "checks": copy.deepcopy(CHECKS),
            "api_records": copy.deepcopy(API_RECORDS),
            "prepare_records": copy.deepcopy(PREPARE_RECORDS)}


def replay_mode(work_dir: Path, out_dir: Path, mutate: str) -> int:
    """在观察副本上走同一套真实收尾（业务调用增量 0）。"""
    REPLAY_FROM.append(str(work_dir))
    evidence = load_evidence(work_dir)
    ROUND["id"] = evidence["expected"].get("round") or work_dir.name
    checkpoint_data = {"expected": evidence["expected"], "checks": evidence["checks"],
                       "api_records": evidence["api_records"],
                       "prepare_records": evidence["prepare_records"]}
    summary = evidence["summary"]
    return finish(out_dir, checkpoint_data, mutate, None,
                  summary.get("receivers", {}), summary.get("results", {}))


# --------------------------------------------------------------------------- main


def resolve_out_dir(raw: str) -> tuple:
    """任何 mkdir 之前：解析后核对 TEST_ROOT 严格后代，并保留原路径逐级 reparse 检查。"""
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
        if os.name != "nt" and step.is_symlink():
            return None, f"路径含符号链接：{step}"
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        return None, f"无法解析路径：{candidate}：{exc}"
    try:
        relative = resolved.relative_to(TEST_ROOT.resolve())
    except ValueError:
        return None, (f"out-dir 解析后必须位于 {TEST_ROOT} 之内"
                      f"（不接受 .. 越界/同前缀兄弟）：{resolved}")
    if str(relative) in ("", "."):
        return None, "out-dir 不能是证据根本身"
    return resolved, None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TASK-026-R3 测试入口")
    parser.add_argument("--out-dir")
    parser.add_argument("--replay", help="复用一次观察的独立副本，走同一套真实收尾")
    parser.add_argument("--mutate", default="none",
                        choices=("none", "checks", "payload", "args", "late-checks"))
    args = parser.parse_args(argv)

    if not args.out_dir:
        print(json.dumps({"status": "FAIL", "reason": "缺少 --out-dir"}, ensure_ascii=False))
        return 1

    out_dir, problem = resolve_out_dir(args.out_dir)
    if problem:
        print(json.dumps({"status": "FAIL", "reason": problem, "created": False},
                         ensure_ascii=False))
        return 1
    if out_dir.exists():
        print(json.dumps({"status": "FAIL",
                          "reason": f"out-dir 必须从未存在，拒绝覆盖或清理：{out_dir}"},
                         ensure_ascii=False))
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.replay:
        return replay_mode(Path(args.replay).resolve(), out_dir, args.mutate)
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

    receiver_records = {}
    inputs_dir = batch_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    for key in ("normal", "blocked"):
        target_input = inputs_dir / f"{key}.xlsx"
        shutil.copyfile(CHECKER_SOURCES[key], target_input)
        receiver_records[key] = receive_batch(
            batch_dir / f"batch_{key}", target_input,
            f"TASK-026-R3 测试样本 {key}：不构成业务范围确认")
    check("0.1 接收器 CLI 两次真实执行且返回码 0/1",
          receiver_records["normal"]["returncode"] == 0
          and receiver_records["blocked"]["returncode"] == 1,
          {key: value["returncode"] for key, value in receiver_records.items()})

    module = load_module()
    prepare_module = module._load_frozen_prepare()
    observe_frozen_prepare(prepare_module)
    observer = EntryObserver(prepare_module)
    scope_dir = GATE1_RECORDS_ROOT / f"{ROUND['id']}_scope"
    normal_batch = batch_dir / "batch_normal"
    blocked_batch = batch_dir / "batch_blocked"

    sys.setprofile(observer)
    try:
        results = {"normal": group_normal(module, normal_batch, runtime_dir, scope_dir),
                   "blocked": group_blocked(module, blocked_batch, runtime_dir, scope_dir),
                   "read_scope": group_read_scope_finish(module, normal_batch, runtime_dir,
                                                        scope_dir)}
    finally:
        sys.setprofile(None)
    for api_name, count in observer.api.items():
        registered = sum(item["operation"] == api_name for item in API_RECORDS)
        check(f"4.1 真实公开 API 与完整登记闭合：{api_name}",
              count >= 1 and count == registered, {"profiled": count, "registered": registered})
    check("4.2 冻结准备器真实调用次数与完整记录数闭合",
          observer.prepare == len(PREPARE_RECORDS) and observer.prepare >= 1,
          {"profiled": observer.prepare, "records": len(PREPARE_RECORDS)})
    check("4.3 禁止入口真实观察命中 0", observer.forbidden == [], observer.forbidden)
    check("4.4 计划 scope 未被创建", not scope_dir.exists(), "clean")
    return finish(out_dir, checkpoint(), "none", observer, receiver_records, results)


if __name__ == "__main__":
    raise SystemExit(main())
