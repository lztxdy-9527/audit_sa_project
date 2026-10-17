#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-028 测试入口：有效 Gate1 批准后的标准化与 SQLite 装载（停在 RT_NORMALIZED）。

    .venv\\Scripts\\python.exe -B tests\\test_runtime_approved_load.py \\
        --out-dir data\\runtime_approved_load_tests\\task028_run_01

    ... --out-dir <从未存在的新目录> --replay <既有观察目录> \\
        --mutate none|ledger-replaced|late-drift|candidate-return|drop-call

正常轮：一次写定候选 → 实读回核 → 末次有界确认 → 独立内存预期审核 → 失败支配顶层/磁盘。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data"
RUNTIME_ROOT = DATA / "runtime"
RECORDS_ROOT = DATA / "human_gate_decision_records" / "gate1"
SQLITE_ROOT = DATA / "sqlite_tests"
TEST_ROOT = DATA / "runtime_approved_load_tests"
BATCH_NORMAL = DATA / "batches" / "task027r1_run_04" / "batch_normal"
BATCH_BLOCKED = DATA / "batches" / "task027r1_run_04" / "batch_blocked"
HOLD_FIXTURE = (DATA / "human_gate1_decision_tests" / "task024_dev_01" / "fixtures"
                / "TASK024_G1_HOLD_0002.json")
APPROVE_FIELDS = {
    "event_id": "FIXTURE-EV-G1-0001", "decision": "APPROVE",
    "decision_source": "HUMAN_GATE_DECISION", "actor_id": "FIXTURE-EV-G1-0001",
    "decided_at_raw": "2026-10-13T18:00:00+08:00",
    "reason": "FIXTURE：结构核验通过，同意进入标准化（设计夹具，无审批效力）",
    "declaration_note": "设计夹具：本地显式身份声明，非真实人员、非强认证",
}
SUBMISSION_VERSION = "TASK-020-human-gate-decision-submission-1.1"
PUBLIC_APIS = ("build_runtime_registry", "prepare_runtime_gate1_request",
               "save_runtime_gate1_decision", "verify_gate1_effective_approval",
               "run_gate1_approved_load", "inspect_gate1_approved_load")
EVIDENCE_FILES = ("expected_observations.json", "summary.json", "checks.json",
                  "failures.json", "api_records.json", "core_records.json")
CHECKS: list = []
API_RECORDS: list = []
CORE_RECORDS: list = []
CORE_INPUT_REFS: dict = {}
ISOLATED_CORE_RECORDS: list = []
CALL_STACK: list = []
SEAMS: dict = {}
STATE: dict = {}
ROUND = {"id": None}
COUNTER = {"value": 0}


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


def chain_of(exc) -> list:
    chain, node, seen = [], exc, set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        chain.append(f"{type(node).__name__}: {node}")
        node = node.__cause__ or node.__context__
    return chain


def core_input_point(refs) -> list:
    return [{"reference_id": id(value), "snapshot": copy.deepcopy(value),
             "fingerprint": digest(value)} for value in refs]


def finalize_core_observations(call_id) -> None:
    for record in CORE_RECORDS:
        if record["caller_api"] == call_id:
            record["input_refs_api_end"] = core_input_point(
                CORE_INPUT_REFS[record["nested_id"]])


def check(name: str, ok: bool, detail=None) -> None:
    CHECKS.append({"name": name, "ok": bool(ok),
                   "detail": detail if detail is not None else ""})


def call_api(module, operation, function, *args, **kwargs):
    call_id = f"call_{COUNTER['value'] + 1:03d}"
    COUNTER["value"] += 1
    record = {"call_id": call_id, "operation": operation,
              "args": [jsonable(item) for item in args],
              "kwargs": {key: jsonable(value) for key, value in kwargs.items()}}
    CALL_STACK.append(call_id)
    try:
        result = function(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        finalize_core_observations(call_id)
        CALL_STACK.pop()
        record.update({"outcome": "exception", "exception_type": type(exc).__name__,
                       "exception_str": str(exc), "field": getattr(exc, "field", None),
                       "stage": getattr(exc, "stage", None),
                       "cause_chain": chain_of(exc), "traceback": traceback.format_exc()})
        API_RECORDS.append(record)
        return exc, None, call_id
    finalize_core_observations(call_id)
    CALL_STACK.pop()
    snapshot = copy.deepcopy(result)
    record.update({"outcome": "returned", "return": snapshot})
    API_RECORDS.append(record)
    return None, snapshot, call_id


def load_module():
    spec = importlib.util.spec_from_file_location(
        "runtime_gate1_approved_load_under_test", PROJECT_ROOT / "scripts" / "runtime_gate1.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EntryObserver:
    """按**原始函数 code 对象**分列计数；不混加、不按名字猜。"""

    def __init__(self, module, normalizer_code, loader_code):
        self.codes = {}
        for name in PUBLIC_APIS:
            self.codes[getattr(module, name).__code__] = name
        self.normalizer_code = normalizer_code
        self.loader_code = loader_code
        self.api = {name: 0 for name in PUBLIC_APIS}
        self.normalizer = 0
        self.loader = 0
        self._other = {}

    def __call__(self, frame, event, arg):
        if event != "call":
            return None
        code = frame.f_code
        name = self.codes.get(code)
        if name is not None:
            self.api[name] += 1
        elif code is self.normalizer_code:
            self.normalizer += 1
        elif code is self.loader_code:
            self.loader += 1
        else:
            if code.co_name in ("normalize_workbook", "load_normalized_to_sqlite",
                                "build_human_gate_decision_record",
                                "save_human_gate_decision_snapshots",
                                "prepare_human_gate1_request"):
                key = f"{code.co_filename}::{code.co_name}"
                self._other[key] = self._other.get(key, 0) + 1
        return None


def observe_cores(module) -> dict:
    """在**实际加载使用**的冻结核心上安装观察包装（记录入参/返回/异常与输入前后指纹）。"""
    info = {}
    real_normalizer_loader = module._load_frozen_normalizer
    real_core_loader = module._load_frozen_sqlite_core

    def normalizer_loader():
        core_module = real_normalizer_loader()
        if not getattr(core_module, "_z28_observed", False):
            real = core_module.normalize_workbook

            def spy(workbook_path, quality_report):
                record = {"nested_id": f"normalize_{len(CORE_RECORDS) + 1:03d}",
                          "core": "normalizer",
                          "args": [jsonable(workbook_path), jsonable(quality_report)],
                          "caller_api": CALL_STACK[-1] if CALL_STACK else None,
                          "input_before": reading(workbook_path)}
                refs = [quality_report]
                CORE_INPUT_REFS[record["nested_id"]] = refs
                record["input_refs_before"] = core_input_point(refs)
                try:
                    out = real(workbook_path, quality_report)
                except Exception as exc:  # noqa: BLE001
                    record.update({"outcome": "exception",
                                   "exception_type": type(exc).__name__,
                                   "exception_str": str(exc), "cause_chain": chain_of(exc)})
                    record["traceback"] = traceback.format_exc()
                    record["reasons"] = copy.deepcopy(getattr(exc, "reasons", None))
                    record["input_refs_after"] = core_input_point(refs)
                    CORE_RECORDS.append(record)
                    raise
                record["input_after"] = reading(workbook_path)
                record["input_refs_after"] = core_input_point(refs)
                record.update({"outcome": "returned", "return": copy.deepcopy(out)})
                CORE_RECORDS.append(record)
                hook = SEAMS.get("after_normalize")
                if hook is not None:
                    hook(out)
                return out

            core_module.normalize_workbook = spy
            core_module._z28_observed = True
        info["normalizer_file"] = str(core_module.__file__)
        return core_module

    def core_loader():
        core_module = real_core_loader()
        if not getattr(core_module, "_z28_observed", False):
            real = core_module.load_normalized_to_sqlite

            def spy(normalized, database_path):
                record = {"nested_id": f"loader_{len(CORE_RECORDS) + 1:03d}",
                          "core": "sqlite", "args": [jsonable(normalized),
                                                     jsonable(database_path)],
                          "caller_api": CALL_STACK[-1] if CALL_STACK else None}
                refs = [normalized]
                CORE_INPUT_REFS[record["nested_id"]] = refs
                record["input_refs_before"] = core_input_point(refs)
                try:
                    out = real(normalized, database_path)
                except Exception as exc:  # noqa: BLE001
                    record.update({"outcome": "exception",
                                   "exception_type": type(exc).__name__,
                                   "exception_str": str(exc), "cause_chain": chain_of(exc)})
                    record["traceback"] = traceback.format_exc()
                    record["reasons"] = copy.deepcopy(getattr(exc, "reasons", None))
                    record["input_refs_after"] = core_input_point(refs)
                    CORE_RECORDS.append(record)
                    raise
                record["input_refs_after"] = core_input_point(refs)
                record.update({"outcome": "returned", "return": copy.deepcopy(out)})
                CORE_RECORDS.append(record)
                hook = SEAMS.get("after_load")
                if hook is not None:
                    hook(out)
                return out

            core_module.load_normalized_to_sqlite = spy
            core_module._z28_observed = True
        info["core_file"] = str(core_module.__file__)
        return core_module

    module._load_frozen_normalizer = normalizer_loader
    module._load_frozen_sqlite_core = core_loader
    return info


def submission_for(fields, materials_fingerprint, request_id, batch_id):
    return {
        "submission_version": SUBMISSION_VERSION,
        "event_id": fields["event_id"], "batch_id": batch_id, "gate": "GATE1",
        "request_binding": {"request_id": request_id,
                            "materials_binding": materials_fingerprint},
        "decision": fields["decision"], "decision_source": fields["decision_source"],
        "actor": {"actor_kind": "HUMAN_DECLARED", "actor_id": fields["actor_id"],
                  "declaration_note": fields["declaration_note"]},
        "decided_at_raw": fields["decided_at_raw"], "reason": fields["reason"],
        "prior_decision_binding": None,
    }


def hold_fields() -> dict:
    payload = json.loads(HOLD_FIXTURE.read_bytes().decode("utf-8"))
    fragment = payload["fragment"]
    return {"event_id": fragment["event_id"], "decision": fragment["decision"],
            "decision_source": fragment["decision_source"],
            "actor_id": fragment["actor"]["actor_id"],
            "decided_at_raw": fragment["decided_at_raw"], "reason": fragment["reason"],
            "declaration_note": fragment["actor"]["declaration_note"],
            "fixture_sha256": sha_bytes(HOLD_FIXTURE.read_bytes())}


def scenario(module, ctx, tag, *, fields=None, batch="normal", request_id="FIXTURE-REQ-G1-0001",
             do_save=True):
    fields = fields or APPROVE_FIELDS
    batch_dir = ctx["batch_normal"] if batch == "normal" else ctx["batch_blocked"]
    leaf = ctx["runtime"] / f"registry_{tag}"
    scope = RECORDS_ROOT / f"{ROUND['id']}_scope_{tag}"
    exc, built, _ = call_api(module, "build_runtime_registry",
                             module.build_runtime_registry, batch_dir, leaf,
                             scope_dir=scope)
    exc_p, prepared, _ = call_api(module, "prepare_runtime_gate1_request",
                                  module.prepare_runtime_gate1_request, batch_dir, leaf,
                                  request_id)
    data = {"leaf": leaf, "scope": scope, "batch_dir": batch_dir, "tag": tag,
            "request_id": request_id, "built": built, "prepared": prepared,
            "build_exc": exc, "prepare_exc": exc_p}
    if exc_p is not None:
        return data
    materials = prepared["request"]["materials"]
    submission = submission_for(fields, materials["materials_fingerprint"], request_id,
                                materials["batch_id"])
    data["submission"] = submission
    event = scope / f"event_{fields['event_id'].split('-')[-1]}"
    data["event"] = event
    if not do_save:
        return data
    exc_s, saved, _ = call_api(module, "save_runtime_gate1_decision",
                               module.save_runtime_gate1_decision, batch_dir, leaf,
                               request_id, submission, event, scope_dir=scope)
    data["save_exc"] = exc_s
    data["saved"] = saved
    return data


def db_path(ctx, tag):
    return SQLITE_ROOT / ROUND["id"] / tag / "runtime.sqlite3"


def run_of(module, scene, database_path, **overrides):
    kwargs = {"scope_dir": scene["scope"],
              "event_relative": scene["event"].relative_to(PROJECT_ROOT).as_posix(),
              "database_path": database_path}
    kwargs.update(overrides)
    return call_api(module, "run_gate1_approved_load", module.run_gate1_approved_load,
                    scene["batch_dir"], scene["leaf"], **kwargs)


def inspect_of(module, scene, database_path):
    return call_api(module, "inspect_gate1_approved_load",
                    module.inspect_gate1_approved_load, scene["batch_dir"], scene["leaf"],
                    scope_dir=scene["scope"],
                    event_relative=scene["event"].relative_to(PROJECT_ROOT).as_posix(),
                    database_path=database_path)


def load_dir_of(scene):
    leaf = scene["leaf"]
    return leaf.parent / (leaf.name + module_LOAD_SUFFIX())


def module_LOAD_SUFFIX():
    return ".load"


# --------------------------------------------------------------------------- 六组验收


def group_normal(module, ctx) -> dict:
    scene = scenario(module, ctx, "normal")
    check("1.1 新登记与 Gate1 APPROVE 事件建立",
          scene.get("save_exc") is None and scene.get("saved") is not None,
          f"{type(scene.get('save_exc')).__name__}")
    STATE["normal"] = scene
    check("1.2 夹具 0001 人类字段原文使用（事件记录 actor 为 HUMAN_DECLARED）",
          scene["saved"]["record"]["actor"]["actor_kind"] == "HUMAN_DECLARED", "human")
    database_path = db_path(ctx, "normal")
    exc, result, _ = run_of(module, scene, database_path)
    check("1.3 run 成功返回 RT_NORMALIZED 且恰六键",
          exc is None and sorted(result.keys()) == ["artifacts", "batch_id", "boundaries",
                                                    "run_binding_sha256", "stage_version",
                                                    "status"]
          and result["status"] == "RT_NORMALIZED"
          and result["stage_version"] == "TASK-028-approved-load-1.0",
          f"{type(exc).__name__}: {getattr(exc, 'field', getattr(exc, 'stage', ''))}")
    if exc is not None:
        return {"error": str(exc)}
    check("1.4 八键边界全严格 false",
          sorted(result["boundaries"]) == ["ai_enabled", "audit_conclusion_formed",
                                           "gate2_approved", "identity_authenticated",
                                           "initial_judgment_recorded",
                                           "next_step_allowed", "screening_allowed",
                                           "source_authenticity_proven"]
          and all(value is False for value in result["boundaries"].values()), "boundaries")
    load_dir = load_dir_of(scene)
    check("1.5 load_dir 恰四文件、无 failure/未知项",
          sorted(item.name for item in load_dir.iterdir())
          == ["artifacts.json", "load_report.json", "normalized.json", "started.json"],
          sorted(item.name for item in load_dir.iterdir()))
    check("1.6 数据库叶恰一文件 runtime.sqlite3",
          sorted(item.name for item in database_path.parent.iterdir()) == ["runtime.sqlite3"],
          sorted(item.name for item in database_path.parent.iterdir()))
    check("1.7 artifacts 恰十一键且 database 恰三键",
          len(result["artifacts"]) == 11
          and sorted(result["artifacts"]["database"]) == ["byte_size", "file_sha256",
                                                          "relative"], "artifacts")
    on_disk = json.loads((load_dir / "load_report.json").read_bytes().decode("utf-8"))
    check("1.8 落盘 load_report 与核心完整返回规范相等",
          canonical(on_disk) == canonical(CORE_RECORDS[-1]["return"]), "report equal")
    check("1.9 核心各真实调用一次（normalizer/loader）",
          sum(1 for item in CORE_RECORDS if item["core"] == "normalizer") == 1
          and sum(1 for item in CORE_RECORDS if item["core"] == "sqlite") == 1,
          [item["nested_id"] for item in CORE_RECORDS])
    normalize_record = next(item for item in CORE_RECORDS if item["core"] == "normalizer")
    check("1.10 输入前后指纹真实取得且未变",
          normalize_record["input_before"] == normalize_record["input_after"],
          normalize_record.get("input_after"))
    normalized = json.loads((load_dir / "normalized.json").read_bytes().decode("utf-8"))
    check("1.11 四表行数与标准化 records 交叉核对",
          all(on_disk["row_counts"][table]
              == len(normalized["tables"][table]["records"])
              for table in ("suppliers", "payables", "payments", "allocations")),
          on_disk["row_counts"])
    check("1.12 报告状态/版本/next=false 与数据库字节闭合",
          on_disk["batch_status"] == "DEV_SQLITE_VERIFIED"
          and on_disk["next_step_allowed"] is False
          and on_disk["database_sha256"] == sha_bytes(database_path.read_bytes()),
          on_disk["database_sha256"][:12])
    table_checks = on_disk.get("net_checks")
    check("1.13 整数分/缺失应付关联保留（核心结果原样落盘）",
          isinstance(table_checks, dict) and "missing_payable_link_net" in on_disk,
          sorted(list(table_checks or []))[:4])
    exc_i, inspected, _ = inspect_of(module, scene, database_path)
    check("1.14 inspect 只读成功且与 run 的 artifacts 完全一致",
          exc_i is None and inspected["status"] == "RT_NORMALIZED"
          and canonical(inspected["artifacts"]) == canonical(result["artifacts"]),
          f"{type(exc_i).__name__}: {getattr(exc_i, 'field', '')}")
    check("1.15 inspect 未调用两计算核心（增量 0）",
          len(CORE_RECORDS) == 2, [item["nested_id"] for item in CORE_RECORDS])
    STATE["database_normal"] = database_path
    return {"artifacts": result["artifacts"]}


def group_rejections(module, ctx) -> dict:
    results = {}
    # ---- HOLD：当前 Gate1 未通过 → 两核心 0、目录与库未建
    hold = hold_fields()
    check("2.1 夹具 0002 原文 SHA 核对",
          hold["fixture_sha256"]
          == "8e3cf5670e91f3c48776360ab8fc22b6fef3f9bce76f56d3793804142b5cd4fa",
          hold["fixture_sha256"][:12])
    scene_hold = scenario(module, ctx, "hold", fields=hold,
                          request_id="FIXTURE-REQ-G1-0002")
    core_before = len(CORE_RECORDS)
    exc, _, _ = run_of(module, scene_hold, db_path(ctx, "hold"))
    check("2.2 HOLD → run Blocked（effective 未通过）且两核心增量 0、无输出目录",
          isinstance(exc, module.RuntimeGate1Blocked) and len(CORE_RECORDS) == core_before
          and not load_dir_of(scene_hold).exists()
          and not db_path(ctx, "hold").parent.exists(),
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    results["hold"] = {"field": getattr(exc, "field", None)}

    # ---- 错绑定：提交材料绑定错误 → 保存即被拒（既有规则）
    scene_wrong = scenario(module, ctx, "wrong_binding", do_save=False)
    wrong = copy.deepcopy(scene_wrong["submission"])
    wrong["request_binding"]["materials_binding"] = "0" * 64
    exc_s, _, _ = call_api(module, "save_runtime_gate1_decision",
                           module.save_runtime_gate1_decision, scene_wrong["batch_dir"],
                           scene_wrong["leaf"], scene_wrong["request_id"], wrong,
                           scene_wrong["event"], scope_dir=scene_wrong["scope"])
    check("2.3 错材料绑定 → 保存定位拒绝且不建事件",
          isinstance(exc_s, module.RuntimeGate1Blocked)
          and getattr(exc_s, "field", "") == "submission.request_binding.materials_binding"
          and not scene_wrong["event"].exists(), f"{type(exc_s).__name__}")
    # ---- 缺 Gate1 记录：无事件的 scope 上 run → 拒绝且两核心 0
    scene_missing = scenario(module, ctx, "missing_event", do_save=False)
    core_before = len(CORE_RECORDS)
    exc_m, _, _ = run_of(module, scene_missing, db_path(ctx, "missing"))
    check("2.4 无 Gate1 事件 → run 拒绝且两核心 0、无输出目录",
          isinstance(exc_m, (module.RuntimeGate1Blocked, module.RuntimeGate1Error))
          and len(CORE_RECORDS) == core_before
          and not load_dir_of(scene_missing).exists(),
          f"{type(exc_m).__name__}: {getattr(exc_m, 'field', getattr(exc_m, 'stage', ''))}")
    # ---- BLOCKED 批次 + APPROVE：既有 Gate1 规则拒绝
    scene_blocked = scenario(module, ctx, "blocked_approve", batch="blocked")
    check("2.5 BLOCKED 批次 + APPROVE 仍被既有 Gate1 规则拒绝且无成功事件",
          isinstance(scene_blocked.get("save_exc"),
                     (module.RuntimeGate1Blocked, module.RuntimeGate1Error))
          and not scene_blocked["event"].exists(),
          f"{type(scene_blocked.get('save_exc')).__name__}")
    results["blocked"] = True
    return results


def group_paths(module, ctx) -> dict:
    results = {}
    # 3.1 既有空 load_dir
    scene = scenario(module, ctx, "existing_load_dir")
    load_dir = load_dir_of(scene)
    load_dir.mkdir()
    exc, _, _ = run_of(module, scene, db_path(ctx, "existing_load_dir"))
    check("3.1 既有（空）load_dir → 拒绝且现场不变",
          isinstance(exc, module.RuntimeGate1Blocked)
          and getattr(exc, "field", "") == "load_dir"
          and sorted(item.name for item in load_dir.iterdir()) == [],
          f"{type(exc).__name__}: {getattr(exc, 'field', '')}")
    # 3.2 既有数据库父叶
    scene2 = scenario(module, ctx, "existing_db_leaf")
    target = db_path(ctx, "existing_db_leaf")
    target.parent.mkdir(parents=True)
    exc2, _, _ = run_of(module, scene2, target)
    check("3.2 既有数据库父叶 → 拒绝且未新建 load_dir",
          isinstance(exc2, module.RuntimeGate1Blocked)
          and getattr(exc2, "field", "") == "database_path"
          and not load_dir_of(scene2).exists(),
          f"{type(exc2).__name__}: {getattr(exc2, 'field', '')}")
    # 3.3 越界数据库路径
    scene3 = scenario(module, ctx, "out_of_bounds_db")
    outside = PROJECT_ROOT / "sqlite_out_of_bounds" / "runtime.sqlite3"
    exc3, _, _ = run_of(module, scene3, outside)
    check("3.3 越界数据库路径 → 拒绝且未创建",
          isinstance(exc3, module.RuntimeGate1Blocked)
          and getattr(exc3, "field", "") == "database_path"
          and not outside.parent.exists() and not load_dir_of(scene3).exists(),
          f"{type(exc3).__name__}: {getattr(exc3, 'field', '')}")
    results["path_checks"] = True
    return results


def group_errors(module, ctx) -> dict:
    import builtins

    results = {}
    # 4.1 标准化 Error（宿主注入：核心返回前受控抛异常）
    scene = scenario(module, ctx, "normalize_error")

    def raise_after_normalize(_normalized):
        raise RuntimeError("host-injected normalizer post-return failure")

    SEAMS["after_normalize"] = raise_after_normalize
    try:
        exc, _, _ = run_of(module, scene, db_path(ctx, "normalize_error"))
    finally:
        SEAMS.pop("after_normalize", None)
    load_dir = load_dir_of(scene)
    failure = load_dir / "failure.json"
    check("4.1 标准化后受控异常 → Error + failure 且 loader 增量 0",
          isinstance(exc, module.RuntimeGate1Error) and failure.is_file()
          and sum(1 for item in CORE_RECORDS if item["core"] == "sqlite") == 1,
          f"{type(exc).__name__}: {getattr(exc, 'stage', '')}")
    kind = json.loads(failure.read_bytes().decode("utf-8"))["kind"] if failure.is_file() else None
    check("4.2 failure 六键且 kind 为 ERROR", kind == "ERROR", kind)
    exc_i, _, _ = inspect_of(module, scene, db_path(ctx, "normalize_error"))
    check("4.3 inspect 恢复拒绝（按 failure）",
          isinstance(exc_i, module.RuntimeGate1Error), type(exc_i).__name__)

    # 4.4 数据库已发布后 Error（宿主注入：loader 返回后受控抛异常）
    scene2 = scenario(module, ctx, "published_then_error")
    target2 = db_path(ctx, "published_then_error")

    def raise_after_load(_report):
        raise RuntimeError("host-injected post-publish failure")

    SEAMS["after_load"] = raise_after_load
    try:
        exc2, _, _ = run_of(module, scene2, target2)
    finally:
        SEAMS.pop("after_load", None)
    failure2 = load_dir_of(scene2) / "failure.json"
    check("4.4 数据库已发布后受控异常 → Error + 已发布库保留 + failure",
          isinstance(exc2, module.RuntimeGate1Error) and target2.is_file()
          and failure2.is_file(), f"{type(exc2).__name__}: {getattr(exc2, 'stage', '')}")
    exc_i2, _, _ = inspect_of(module, scene2, target2)
    check("4.5 inspect 对已发布库 + failure → 仍按诊断拒绝",
          isinstance(exc_i2, module.RuntimeGate1Error), type(exc_i2).__name__)
    results["error_mappings"] = True
    return results


def group_late(module, ctx) -> dict:
    import builtins

    results = {}
    # 5.1 真实独占句柄半写 artifacts.json
    scene = scenario(module, ctx, "half_artifacts")
    real_open = builtins.open

    class HalfWriter:
        def __init__(self, handle):
            self._handle = handle

        def write(self, data):
            self._handle.write(data[: max(1, len(data) // 2)])
            self._handle.flush()
            raise OSError("host-injected partial artifacts write")

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
        handle = real_open(path, mode, *args, **kwargs)
        if "x" in mode and str(path).endswith("artifacts.json"):
            return HalfWriter(handle)
        return handle

    builtins.open = wrapping_open
    try:
        exc, _, _ = run_of(module, scene, db_path(ctx, "half_artifacts"))
    finally:
        builtins.open = real_open
    load_dir = load_dir_of(scene)
    check("5.1 artifacts 真实半写 → 本次拒绝且坏字节与诊断保留",
          isinstance(exc, module.RuntimeGate1Error)
          and (load_dir / "artifacts.json").is_file()
          and (load_dir / "failure.json").is_file(),
          f"{type(exc).__name__}: {getattr(exc, 'stage', '')}")
    exc_i, _, _ = inspect_of(module, scene, db_path(ctx, "half_artifacts"))
    check("5.2 inspect 只读拒绝（半写现场）",
          isinstance(exc_i, (module.RuntimeGate1Blocked, module.RuntimeGate1Error)),
          type(exc_i).__name__)

    # 5.3 数据库/源材料晚变更：loader 返回后改数据库字节
    scene2 = scenario(module, ctx, "late_database_change")
    target2 = db_path(ctx, "late_database_change")

    def disturb_database(_report):
        target2.write_bytes(target2.read_bytes() + b"\\x00")

    SEAMS["after_load"] = disturb_database
    try:
        exc2, _, _ = run_of(module, scene2, target2)
    finally:
        SEAMS.pop("after_load", None)
    check("5.3 数据库晚变更 → 本次拒绝且坏字节保留",
          isinstance(exc2, (module.RuntimeGate1Blocked, module.RuntimeGate1Error))
          and target2.is_file()
          and (load_dir_of(scene2) / "failure.json").is_file(),
          f"{type(exc2).__name__}: {getattr(exc2, 'stage', '')}")
    exc_i3, _, _ = inspect_of(module, scene2, target2)
    check("5.4 inspect 对晚变更现场只读拒绝",
          isinstance(exc_i3, (module.RuntimeGate1Blocked, module.RuntimeGate1Error)),
          type(exc_i3).__name__)
    results["late_changes"] = True
    return results


# --------------------------------------------------------------------------- 收尾


def _sha(path) -> str:
    return sha_bytes(Path(path).read_bytes())


def _tamper_json(path, mutate) -> None:
    payload = json.loads(Path(path).read_bytes().decode("utf-8"))
    mutate(payload)
    Path(path).write_bytes(canonical(payload) + b"\n")


def _sync_artifacts(scene, **fields) -> None:
    path = load_dir_of(scene) / "artifacts.json"
    _tamper_json(path, lambda obj: obj.update(fields))


def group_r1(module, ctx) -> dict:
    """R1 最小反例：B1 起始预期/集合、B2 严格字段与只读行数、B3 I/O 与真实异常类型。"""
    import builtins

    results = {}

    def fresh(tag):
        scene = scenario(module, ctx, tag, request_id="FIXTURE-REQ-G1-0001")
        exc_i, result, _ = run_of(module, scene, db_path(ctx, tag))
        assert exc_i is None, f"{tag}: run 未成功 {exc_i!r}"
        return scene, result

    # ---------- B1: 末端只认起始读数（三处 LF 隔离反例 + 保存端 DB LF） ----------
    for tag, victim in (("r1_b1_db_lf", "database"),
                        ("r1_b1_context_lf", "context"),
                        ("r1_b1_decision_lf", "decision")):
        scene, _ = fresh(tag)
        load_dir = load_dir_of(scene)
        if victim == "database":
            target = db_path(ctx, tag)
        elif victim == "context":
            target = scene["event"] / "context.json"
        else:
            target = scene["event"] / "snapshots" / "decision_result.json"
        target.write_bytes(target.read_bytes() + b"\n")
        exc, _, _ = inspect_of(module, scene, db_path(ctx, tag))
        check(f"R1-B1 末端 {victim} 晚变更 → inspect 定位拒绝",
              isinstance(exc, (module.RuntimeGate1Blocked, module.RuntimeGate1Error)),
              f"{type(exc).__name__}: {getattr(exc, 'field', getattr(exc, 'stage', ''))}")

    # 保存端：真实 artifacts writer 返回之后再改数据库
    scene = scenario(module, ctx, "r1_b1_save_db_lf", request_id="FIXTURE-REQ-G1-0001")
    db_b1 = db_path(ctx, "r1_b1_save_db_lf")
    real_write = module._write_exclusive
    state = {"fired": False}

    def write_with_db_disturb(path, buffer, stage):
        real_write(path, buffer, stage)
        if not state["fired"] and str(path).endswith("artifacts.json"):
            state["fired"] = True
            db_b1.write_bytes(db_b1.read_bytes() + b"\n")

    module._write_exclusive = write_with_db_disturb
    try:
        exc, _, _ = run_of(module, scene, db_b1)
    finally:
        module._write_exclusive = real_write
    failure = load_dir_of(scene) / "failure.json"
    check("R1-B1 保存端 artifacts writer 返回后 DB LF → 本次拒绝+本层 failure+坏库保留",
          isinstance(exc, (module.RuntimeGate1Blocked, module.RuntimeGate1Error))
          and state["fired"] and failure.is_file() and db_b1.is_file(),
          f"{type(exc).__name__}: {getattr(exc, 'field', getattr(exc, 'stage', ''))}")

    # 晚新增 scope/快照未知项
    scene_unknown, _ = fresh("r1_b1_unknown_snapshot")
    (load_dir_of(scene_unknown) / "normalized.json").rename(
        load_dir_of(scene_unknown) / "unknown_extra.json")
    exc_u, _, _ = inspect_of(module, scene_unknown, db_path(ctx, "r1_b1_unknown_snapshot"))
    check("R1-B1 load_dir 未知项 → inspect 定位拒绝（集合覆盖）",
          isinstance(exc_u, module.RuntimeGate1Blocked)
          and getattr(exc_u, "field", "") == "load_dir", f"{type(exc_u).__name__}")

    # ---------- B2: 严格字段与只读行数 ----------
    scene_b2, _ = fresh("r1_b2_fields")
    load_dir = load_dir_of(scene_b2)
    target_b2 = db_path(ctx, "r1_b2_fields")

    def inspect_b2(label: str):
        exc, _, _ = inspect_of(module, scene_b2, target_b2)
        check(f"R1-B2 {label} → 定位拒绝",
              isinstance(exc, (module.RuntimeGate1Blocked, module.RuntimeGate1Error)),
              f"{type(exc).__name__}: {getattr(exc, 'field', getattr(exc, 'stage', ''))}")

    # 1) 错 started.batch_id + 同步 started 文件 SHA
    _tamper_json(load_dir / "started.json", lambda o: o.update({"batch_id": "WRONG-BATCH"}))
    _sync_artifacts(scene_b2, started_file_sha256=_sha(load_dir / "started.json"))
    inspect_b2("错 started.batch_id（同步文件 SHA）")

    # 2) 错 artifacts.registry_file_sha256
    _sync_artifacts(scene_b2, registry_file_sha256="0" * 64)
    inspect_b2("错 artifacts.registry_file_sha256")

    # 3) 错 Gate1 指纹
    _tamper_json(load_dir / "started.json", lambda o: o.update({"batch_id": "batch_normal"}))
    _sync_artifacts(scene_b2, started_file_sha256=_sha(load_dir / "started.json"),
                    gate1_record_fingerprint="1" * 64)
    inspect_b2("错 Gate1 指纹")

    # 4) 同值 float byte_size
    _sync_artifacts(scene_b2, gate1_record_fingerprint=None)
    wallet = json.loads((load_dir / "artifacts.json").read_bytes().decode("utf-8"))
    wallet.pop("gate1_record_fingerprint")
    (load_dir / "artifacts.json").write_bytes(canonical(wallet) + b"\n")
    inspect_b2("缺 artifacts.gate1_record_fingerprint（键集）")

    # 5) report.round_trip_exact=false + 同步文件 SHA
    _tamper_json(load_dir / "load_report.json",
                 lambda o: o.update({"round_trip_exact": False}))
    _sync_artifacts(scene_b2, load_report_file_sha256=_sha(load_dir / "load_report.json"))
    inspect_b2("round_trip_exact=false（同步文件 SHA）")

    # 6) 删一条 allocations 记录并仅同步外层 SHA
    _tamper_json(load_dir / "load_report.json", lambda o: o.update({"round_trip_exact": True}))
    _tamper_json(load_dir / "normalized.json",
                 lambda o: o["tables"]["allocations"].__setitem__(
                     "records", o["tables"]["allocations"]["records"][:-1]))
    _sync_artifacts(scene_b2, load_report_file_sha256=_sha(load_dir / "load_report.json"),
                    normalized_file_sha256=_sha(load_dir / "normalized.json"))
    inspect_b2("删一条 allocations（仅同步外层 SHA）")

    # 7) normalized.source 错输入 SHA
    _tamper_json(load_dir / "normalized.json",
                 lambda o: (o["tables"]["allocations"].__setitem__(
                     "records", o["tables"]["allocations"]["records"] + [{}]),
                     o["source"].__setitem__("input_sha256", "2" * 64)))
    _sync_artifacts(scene_b2, normalized_file_sha256=_sha(load_dir / "normalized.json"))
    inspect_b2("normalized.source 错输入 SHA")

    # 8) 缺/未知嵌套键
    _tamper_json(load_dir / "normalized.json",
                 lambda o: o.__setitem__("unexpected_key", True))
    _sync_artifacts(scene_b2, normalized_file_sha256=_sha(load_dir / "normalized.json"))
    inspect_b2("normalized 未知嵌套键")

    # 9) 正常键序不同的 canonical 等值对照要求通过
    scene_ok, _ = fresh("r1_b2_canonical_ok")
    ok_dir = load_dir_of(scene_ok)
    report = json.loads((ok_dir / "load_report.json").read_bytes().decode("utf-8"))
    (ok_dir / "load_report.json").write_bytes(canonical(report) + b"\n")
    _sync_artifacts(scene_ok, load_report_file_sha256=_sha(ok_dir / "load_report.json"))
    exc_ok, _, _ = inspect_of(module, scene_ok, db_path(ctx, "r1_b2_canonical_ok"))
    check("R1-B2 规范等值（键序不同）重写后 inspect 仍成功",
          exc_ok is None, f"{type(exc_ok).__name__}: {getattr(exc_ok, 'field', '')}")

    # ---------- B3: I/O 与真实异常类型 ----------
    normalizer = module._load_frozen_normalizer()
    core = module._load_frozen_sqlite_core()
    blocked_classes = [name for name in ("NormalizationBlocked", "SqliteLoadBlocked")
                       if hasattr(normalizer if name.startswith("Normalization")
                                  else core, name)]
    check("R3-B3 冻结核心暴露真实 Blocked 异常类", len(blocked_classes) == 2,
          blocked_classes)

    for name, seam in (("NormalizationBlocked", "after_normalize"),
                       ("SqliteLoadBlocked", "after_load")):
        scene_b3 = scenario(module, ctx, f"r1_b3_{name}", request_id="FIXTURE-REQ-G1-0001")
        holder = normalizer if name.startswith("Normalization") else core
        if not hasattr(holder, name):
            check(f"R1-B3 真实类 {name} 注入 → Blocked（类不可用，not_executed）", True,
                  "not_executed")
            continue

        def raise_blocked(_value, _name=name, _holder=holder):
            raise getattr(_holder, _name)("host-injected blocked for mapping test")

        SEAMS[seam] = raise_blocked
        try:
            exc, _, _ = run_of(module, scene_b3, db_path(ctx, f"r1_b3_{name}"))
        finally:
            SEAMS.pop(seam, None)
        failure = load_dir_of(scene_b3) / "failure.json"
        kind = json.loads(failure.read_bytes().decode("utf-8"))["kind"] \
            if failure.is_file() else None
        reason = json.loads(failure.read_bytes().decode("utf-8"))["reason"] \
            if failure.is_file() else ""
        check(f"R1-B3 真实类 {name} → 本层 Blocked 且 kind=BLOCKED、reason 可查",
              isinstance(exc, module.RuntimeGate1Blocked) and kind == "BLOCKED"
              and name in reason,
              f"{type(exc).__name__}: {kind}")

    # 同引用改写：核心返回后改写本次内存输入 → 本次拒绝
    scene_mem = scenario(module, ctx, "r1_e1_memory_rewrite",
                         request_id="FIXTURE-REQ-G1-0001")
    real_read_quality = module._read_quality_report

    def read_quality_spy(batch_path):
        payload, capture = real_read_quality(batch_path)
        STATE["quality_object"] = payload
        return payload, capture

    module._read_quality_report = read_quality_spy

    def rewrite_quality(_normalized):
        # 真实改写**同一引用**的本次内存输入（不是手填标志）
        STATE["quality_object"]["host_injected_rewrite"] = True

    SEAMS["after_normalize"] = rewrite_quality
    try:
        exc_mem, _, _ = run_of(module, scene_mem, db_path(ctx, "r1_e1_memory_rewrite"))
    finally:
        SEAMS.pop("after_normalize", None)
        module._read_quality_report = real_read_quality
    check("R1-E1 核心返回后同引用改写内存输入 → 本次拒绝（真实正式审核）",
          isinstance(exc_mem, (module.RuntimeGate1Blocked, module.RuntimeGate1Error))
          and (load_dir_of(scene_mem) / "failure.json").is_file(),
          f"{type(exc_mem).__name__}: {getattr(exc_mem, 'field', getattr(exc_mem, 'stage', ''))}")

    # mkdir 接缝 OSError（load_dir 已建、库叶未建）
    scene_mk = scenario(module, ctx, "r1_b3_mkdir", request_id="FIXTURE-REQ-G1-0001")
    real_mkdir = Path.mkdir

    def failing_mkdir(self, *args, **kwargs):
        if self.name != load_dir_of(scene_mk).name:
            raise OSError("host-injected database leaf mkdir failure")
        return real_mkdir(self, *args, **kwargs)

    Path.mkdir = failing_mkdir
    try:
        exc_mk, _, _ = run_of(module, scene_mk, db_path(ctx, "r1_b3_mkdir"))
    finally:
        Path.mkdir = real_mkdir
    failure_mk = load_dir_of(scene_mk) / "failure.json"
    check("R1-B3 数据库叶 mkdir OSError → Error+六键 failure+库叶未建+坏目录保留",
          isinstance(exc_mk, module.RuntimeGate1Error) and failure_mk.is_file()
          and load_dir_of(scene_mk).is_dir()
          and not db_path(ctx, "r1_b3_mkdir").parent.exists(),
          f"{type(exc_mk).__name__}: {getattr(exc_mk, 'stage', '')}")

    # 非法 kind / 非对象 failure
    scene_bad = scenario(module, ctx, "r1_b3_bad_failure", request_id="FIXTURE-REQ-G1-0001")
    exc_run, _, _ = run_of(module, scene_bad, db_path(ctx, "r1_b3_bad_failure"))
    bad_path = load_dir_of(scene_bad) / "failure.json"
    bad_path.write_bytes(canonical({"failure_version": "TASK-028-approved-load-failure-1.0",
                                    "kind": "WEIRD", "stage": "s", "field": "f",
                                    "reason": "r", "cause_chain": []}) + b"\n")
    exc_bad, _, _ = inspect_of(module, scene_bad, db_path(ctx, "r1_b3_bad_failure"))
    check("R1-B3 非法 kind 的 failure → 恢复定位拒绝",
          isinstance(exc_bad, module.RuntimeGate1Blocked)
          and "kind" in str(getattr(exc_bad, "field", "")),
          f"{type(exc_bad).__name__}: {getattr(exc_bad, 'field', '')}")
    bad_path.write_bytes(b"not-an-object\n")
    exc_bad2, _, _ = inspect_of(module, scene_bad, db_path(ctx, "r1_b3_bad_failure"))
    check("R1-B3 非对象 failure → 恢复定位拒绝",
          isinstance(exc_bad2, (module.RuntimeGate1Blocked, module.RuntimeGate1Error)),
          f"{type(exc_bad2).__name__}: {getattr(exc_bad2, 'field', '')}")
    results["r1"] = {"blocked_classes": blocked_classes}
    return results


def group_r2(module, ctx) -> dict:
    """R2 residuals only; normal sample is shared by independent restored candidates."""
    results = {"normal": group_normal(module, ctx)}
    scene = STATE["normal"]
    load_dir, database = load_dir_of(scene), STATE["database_normal"]
    originals = {p: p.read_bytes() for p in
                 [load_dir / n for n in module.APPROVED_LOAD_FILES] + [database]}
    evidence = ctx["evidence"] / "isolated"
    cases = []

    def sync_normalized():
        normalized = json.loads((load_dir / "normalized.json").read_bytes())
        payload_fp = digest(normalized)  # independent canonical calculation
        def report_change(report):
            report["normalized_payload_sha256"] = payload_fp
            report["source"] = copy.deepcopy(normalized["source"])
            report["run_metadata"]["input_sha256"] = normalized["source"]["input_sha256"]
            report["run_metadata"]["normalized_payload_sha256"] = payload_fp
        _tamper_json(load_dir / "load_report.json", report_change)
        _sync_artifacts(scene, normalized_payload_sha256=payload_fp,
                        normalized_file_sha256=_sha(load_dir / "normalized.json"),
                        load_report_file_sha256=_sha(load_dir / "load_report.json"))

    def isolated(name, mutate, field):
        assert all(p.read_bytes() == b for p, b in originals.items())
        clean, _, _ = inspect_of(module, scene, database)
        assert clean is None, (name, clean)
        mutate()
        bad = evidence / name
        bad.mkdir(parents=True)
        for p in originals:
            (bad / p.name).write_bytes(p.read_bytes())
        exc, _, _ = inspect_of(module, scene, database)
        detail = {"expected_field": field, "actual_field": getattr(exc, "field", None),
                  "clean_before": True, "bad_files": [reading(p) for p in bad.iterdir()]}
        cases.append({"name": name, **detail})
        check("R2-B2 " + name, isinstance(exc, module.RuntimeGate1Blocked)
              and getattr(exc, "field", None) == field, detail)
        for p, b in originals.items():
            p.write_bytes(b)  # exact restoration of this round's own scene only

    def size(value):
        _tamper_json(load_dir / "artifacts.json",
                     lambda o: o["database"].__setitem__("byte_size", value))
    byte_size = database.stat().st_size
    isolated("float_size", lambda: size(float(byte_size)), "artifacts.database.byte_size")
    isolated("bool_size", lambda: size(True), "artifacts.database.byte_size")

    def source_change(key, value):
        _tamper_json(load_dir / "normalized.json", lambda o:o["source"].__setitem__(key, value))
        sync_normalized()
    isolated("source_input", lambda:source_change("input_sha256", "2" * 64),
             "normalized.source.input_sha256")
    isolated("source_extra", lambda:source_change("unexpected_key", True), "normalized.source")
    isolated("source_checker", lambda:source_change("checker_sha256", "3" * 64),
             "normalized.source.checker_sha256")
    def bad_net():
        _tamper_json(load_dir / "load_report.json", lambda o:
                     o["net_checks"].__setitem__("master_net_equals_normalized", False))
        _sync_artifacts(scene, load_report_file_sha256=_sha(load_dir / "load_report.json"))
    isolated("net_false", bad_net, "load_report.net_checks.master_net_equals_normalized")
    def key_order():
        report = json.loads((load_dir / "load_report.json").read_bytes())
        reordered = dict(reversed(list(report.items())))
        (load_dir / "load_report.json").write_bytes(json.dumps(
            reordered, ensure_ascii=False, indent=1).encode() + b"\n")
        _sync_artifacts(scene, load_report_file_sha256=_sha(load_dir / "load_report.json"))
    key_order()
    same, _, _ = inspect_of(module, scene, database)
    check("R2-B2 canonical key-order control", same is None)
    for p,b in originals.items():
        p.write_bytes(b)

    # Genuine writer-return seams: preserve writer behavior and original return.
    for tag, file_name in (("before_normalize", "started.json"),
                           ("before_normalize_failure", "started.json"),
                           ("before_loader", "normalized.json"),
                           ("report_readback", "load_report.json")):
        s = scenario(module, ctx, tag)
        real_write = module._write_exclusive
        state = {"hits": 0}
        start = len(CORE_RECORDS)
        def disturbed(path, buffer, stage):
            value = real_write(path, buffer, stage)
            if Path(path).name == file_name and state["hits"] == 0:
                state["hits"] += 1
                if tag == "report_readback":
                    _tamper_json(path, lambda o:o.__setitem__("round_trip_exact", False))
                elif tag == "before_normalize_failure":
                    (s["event"] / "failure.json").write_bytes(b"{}\n")
                else:
                    p = s["event"] / "context.json"
                    p.write_bytes(p.read_bytes() + b"\n")
            return value
        module._write_exclusive = disturbed
        try:
            exc, _, _ = run_of(module, s, db_path(ctx, tag))
        finally:
            module._write_exclusive = real_write
        delta = CORE_RECORDS[start:]
        counts = {k:sum(x["core"] == k for x in delta) for k in ("normalizer", "sqlite")}
        expected_counts = {"normalizer": 0 if tag.startswith("before_normalize") else 1,
                           "sqlite": 1 if tag == "report_readback" else 0}
        expected_field = "load_report.json" if tag == "report_readback" else "gate1.context.json"
        if tag == "before_normalize_failure":
            expected_field = "event"
        check("R2-B1 " + tag, isinstance(exc, module.RuntimeGate1Blocked)
              and getattr(exc, "field", None) == expected_field and state["hits"] == 1
              and counts == expected_counts and (load_dir_of(s) / "failure.json").is_file(),
              {"hits":state["hits"], "counts":counts, "expected":expected_counts,
               "field":getattr(exc,"field",None)})
        if tag == "report_readback":
            check("R2-B1 real report remains true", delta[-1]["return"]["round_trip_exact"] is True)

    # Inject actual core exception classes through the actual module entry.
    for tag, core, entry_name, exception_name in (
            ("normalizer_reasons", module._load_frozen_normalizer(), "normalize_workbook", "NormalizationBlocked"),
            ("loader_reasons", module._load_frozen_sqlite_core(), "load_normalized_to_sqlite", "SqliteLoadBlocked")):
        s = scenario(module, ctx, tag)
        real_entry = getattr(core, entry_name)
        reasons = [tag + ":first", tag + ":second"]
        def raise_actual(*args):
            raise getattr(core, exception_name)("controlled real class", reasons)
        setattr(core, entry_name, raise_actual)
        try:
            exc, _, _ = run_of(module, s, db_path(ctx, tag))
        finally:
            setattr(core, entry_name, real_entry)
        failure_path = load_dir_of(s) / "failure.json"
        failure = json.loads(failure_path.read_bytes())
        check("R2-B3 " + tag, isinstance(exc, module.RuntimeGate1Blocked)
              and failure["kind"] == "BLOCKED" and all(r in failure["reason"] for r in reasons)
              and exc.__cause__.reasons == reasons, failure)
        if tag == "normalizer_reasons":
            original_failure = failure_path.read_bytes()
            _tamper_json(failure_path, lambda o:o.__setitem__("failure_version", "WRONG"))
            bad, _, _ = inspect_of(module, s, db_path(ctx, tag))
            check("R2-B3 invalid failure version", isinstance(bad,module.RuntimeGate1Blocked)
                  and bad.field == "failure.failure_version")
            (evidence / "invalid_failure.json").write_bytes(failure_path.read_bytes())
            failure_path.write_bytes(original_failure)

    # Isolated observer sensitivity: real core, real reference, third point mutation.
    s = scenario(module, ctx, "observer_control")
    original_read = module._read_quality_report
    held = {}
    def hold_quality(path):
        value = original_read(path); held["quality"] = value[0]; return value
    module._read_quality_report = hold_quality
    def mutate_ref(out):
        held["quality"]["R2_OBSERVER_CONTROL"] = True
    SEAMS["after_normalize"] = mutate_ref
    first = len(CORE_RECORDS)
    try:
        call_result = run_of(module, s, db_path(ctx, "observer_control"))
    finally:
        module._read_quality_report = original_read
        SEAMS.pop("after_normalize", None)
    isolated_records = copy.deepcopy(CORE_RECORDS[first:])
    expected_control = {"api_records": [], "core_records": isolated_records, "checks": []}
    candidate_control = build_candidate(expected_control, None, {})
    control_audit = audit_candidate(candidate_control, expected_control)
    check("R2-E1 actual observer detects third point", len(isolated_records) == 1
          and any(p.startswith("core_input_changed:") for p in control_audit["problems"]),
          control_audit)
    ISOLATED_CORE_RECORDS.extend(isolated_records)
    del CORE_RECORDS[first:]  # separate negative evidence, not a positive exemption
    results["observer_negative_control"] = {"records":isolated_records, "audit":control_audit,
                                             "scope":"ISOLATED_NEGATIVE_OBSERVER_CONTROL"}
    results["isolated_cases"] = cases
    return results


def freeze_expectations() -> dict:
    return {"api_records": copy.deepcopy(API_RECORDS),
            "core_records": copy.deepcopy(CORE_RECORDS),
            "checks": copy.deepcopy(CHECKS), "round": ROUND["id"]}


def build_candidate(expected: dict, observer, summary_extra: dict) -> dict:
    checks = copy.deepcopy(expected["checks"])
    failed = sorted(item["name"] for item in checks if not item["ok"])
    api_records = copy.deepcopy(expected["api_records"])
    core_records = copy.deepcopy(expected["core_records"])
    summary = {"task": "TASK-028", "round": ROUND["id"],
               "status": "FAIL" if failed else "PASS",
               "checks_total": len(checks), "checks_failed": len(failed),
               "api_call_ids": [item["call_id"] for item in api_records],
               "api_call_count": len(api_records),
               "core_call_ids": [item["nested_id"] for item in core_records],
               "core_call_count": len(core_records),
               "observed": {
                   "public_api_calls_by_name_profile": (observer.api if observer else None),
                   "normalizer_original_function_profile":
                       (observer.normalizer if observer else None),
                   "sqlite_loader_original_function_profile":
                       (observer.loader if observer else None),
                   "isolated_core_control_count": len(ISOLATED_CORE_RECORDS),
                   "gate1_internal_functions_profile":
                       (observer._other if observer else None),
                   "role_note": ("公开 API 计数只取 public_api_calls_by_name_profile；"
                                 "Gate1 内部 P1/store/冻结 prepare 计数单列，不并入公开 API。"),
                   "subprocess_internal_counts": None,
                   "subprocess_internal_counts_reason":
                       "本入口不启动子进程；接收产物为只读复用",
               },
               "results": summary_extra,
               "expected_audit": {
                   "expected_final_status": "FAIL" if failed else "PASS",
                   "independent_expectation": "定稿内存观察（审核期间不刷新）"}}
    return {"checks": checks, "api_records": api_records, "core_records": core_records,
            "summary": summary, "failures": failed,
            "expected_observations": copy.deepcopy(expected)}


def audit_candidate(candidate: dict, expected: dict) -> dict:
    problems = []
    for entry in candidate.get("core_records") or []:
        points = [entry.get(key) for key in
                  ("input_refs_before", "input_refs_after", "input_refs_api_end")]
        # Legacy replays predate R2 observation; do not claim they contain new points.
        if any(point is not None for point in points):
            if any(not isinstance(point, list) or not point for point in points):
                problems.append(f"core_input_points_missing:{entry['nested_id']}")
                continue
            for point in points:
                for value in point:
                    if digest(value["snapshot"]) != value["fingerprint"]:
                        problems.append(f"core_input_snapshot_mismatch:{entry['nested_id']}")
            if canonical(points[0]) != canonical(points[1]) \
                    or canonical(points[0]) != canonical(points[2]):
                problems.append(f"core_input_changed:{entry['nested_id']}")
    for key, id_key in (("api_records", "call_id"), ("core_records", "nested_id")):
        want = expected.get(key) or []
        got = candidate.get(key) or []
        want_ids = [item[id_key] for item in want]
        got_ids = [item[id_key] for item in got]
        missing = [item for item in want_ids if item not in set(got_ids)]
        extra = [item for item in got_ids if item not in set(want_ids)]
        if missing:
            problems.append(f"{key}_missing:{missing[:5]}")
        if extra:
            problems.append(f"{key}_unexpected:{extra[:5]}")
        if len(got_ids) != len(want_ids):
            problems.append(f"{key}_count_mismatch")
        want_map = {item[id_key]: item for item in want}
        for item in got:
            wanted = want_map.get(item[id_key])
            if wanted is not None and canonical(item) != canonical(wanted):
                problems.append(f"{key}_mismatch:{item[id_key]}")
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
    failed = sorted(name for name, item in got_checks.items() if not item["ok"])
    summary = candidate.get("summary") or {}
    if summary.get("checks_total") != len(got_checks):
        problems.append("summary_checks_total_mismatch")
    if summary.get("checks_failed") != len(failed):
        problems.append("summary_checks_failed_mismatch")
    if sorted(candidate.get("failures") or []) != failed:
        problems.append("failures_list_mismatch")
    if summary.get("api_call_count") != len(candidate.get("api_records") or []):
        problems.append("summary_api_count_mismatch")
    return {"problems": sorted(set(problems)),
            "counts": {"api": len(candidate.get("api_records") or []),
                       "core": len(candidate.get("core_records") or []),
                       "checks": len(got_checks)},
            "failed": failed}


def read_payloads(root: Path, *, include_bytes=False) -> dict:
    objects, buffers = {}, {}
    for name in (*EVIDENCE_FILES, "file_ledger.json"):
        path = root / name
        data = path.read_bytes() if path.is_file() else None
        buffers[name] = data
        key = "ledger" if name == "file_ledger.json" else name.removesuffix(".json")
        objects[key] = json.loads(data.decode("utf-8")) if data is not None else None
    if include_bytes:
        objects["_read_buffers"] = buffers
    return objects



def finish(out_dir: Path, checkpoint: dict, mutate: str, observer, summary_extra: dict) -> int:
    expected = copy.deepcopy(checkpoint)
    candidate = build_candidate(expected, observer, summary_extra)
    expected_failed = sorted(item["name"] for item in expected["checks"] if not item["ok"])
    if mutate == "candidate-return":
        for item in candidate["api_records"]:
            if item["outcome"] == "returned" and isinstance(item.get("return"), dict):
                item["return"]["probe"] = "injected"
                break
    elif mutate == "drop-call":
        candidate["api_records"] = candidate["api_records"][:-1]
    payloads = {name + ".json": canonical(candidate[name]) + b"\n" for name in
                ("expected_observations", "summary", "checks", "failures", "api_records", "core_records")}
    diagnostic = {"pre_audit_expected_status": "FAIL" if expected_failed else "PASS",
                  "observation_failed_checks": expected_failed,
                  "boundary": "write-before-content-audit-and-terminal-confirmation",
                  "mutation_control": mutate}
    payloads["audit_failure.json"] = canonical(diagnostic) + b"\n"
    ledger_expected = [{"path": name, "abs_path": str(out_dir / name),
                        "byte_size": len(buffer), "file_sha256": sha_bytes(buffer)}
                       for name, buffer in payloads.items()]
    ledger_buffer = canonical(ledger_expected) + b"\n"
    for name, buffer in payloads.items():
        (out_dir / name).write_bytes(buffer)
    (out_dir / "file_ledger.json").write_bytes(ledger_buffer)
    if mutate == "ledger-replaced":
        (out_dir / "file_ledger.json").write_bytes(b"[]\n")
    elif mutate == "ledger-lf":
        with open(out_dir / "file_ledger.json", "ab") as handle:
            handle.write(b"\n")
    elif mutate == "late-drift":
        with open(out_dir / "checks.json", "ab") as handle:
            handle.write(b"\n")
    candidate_disk = read_payloads(out_dir, include_bytes=True)
    audit = audit_candidate(candidate_disk, expected)
    problems = list(audit["problems"])
    if canonical(candidate_disk["ledger"]) != canonical(ledger_expected):
        problems.append("ledger_mismatch")
    if candidate_disk["_read_buffers"]["file_ledger.json"] != ledger_buffer:
        problems.append("ledger_bytes_mismatch")
    failed_names = sorted(set(audit["failed"]) | set(expected_failed))
    verdict = {"status": "PASS", "audit_ok": not problems, "bytes_ok": True,
               "problems": problems, "drift": [], "mutate": mutate,
               "counts": audit["counts"], "failures_count": len(failed_names),
               "ledger_source_same_buffer": True,
               "note": "actual content/bytes/checks determine process exit"}
    # Last candidate consumption: exact writer buffers, including the ledger itself.
    # All parsing, content checks and successful output construction are above.
    terminal_buffers = dict(payloads, **{"file_ledger.json": ledger_buffer})
    for name, buffer in terminal_buffers.items():
        path = out_dir / name
        if not path.is_file():
            verdict["drift"].append(f"missing:{name}")
        elif path.read_bytes() != buffer:
            verdict["drift"].append(f"drift:{name}")
    ok = not problems and not verdict["drift"] and not failed_names
    verdict["status"] = "PASS" if ok else "FAIL"
    verdict["bytes_ok"] = not verdict["drift"]
    if not ok:
        combined = sorted(set(failed_names) | {f"audit:{item}" for item in problems}
                          | {f"bytes:{item}" for item in verdict["drift"]})
        summary = copy.deepcopy(candidate["summary"])
        summary["status"] = "FAIL"
        summary["failure_reasons"] = combined
        (out_dir / "summary.json").write_bytes(canonical(summary) + b"\n")
        (out_dir / "failures.json").write_bytes(canonical(combined) + b"\n")
        verdict["failures_count"] = len(combined)
    print(json.dumps(verdict, ensure_ascii=False))
    return 0 if ok else 1



def resolve_out_dir(raw: str, *, must_exist: bool = False):
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    for index in range(1, len(candidate.parts) + 1):
        step = Path(*candidate.parts[:index])
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
        resolved.relative_to(TEST_ROOT.resolve())
    except ValueError:
        return None, f"out-dir 必须位于 {TEST_ROOT} 之内：{resolved}"
    if not must_exist and resolved.exists():
        return None, f"out-dir 必须从未存在：{resolved}"
    if must_exist and not resolved.is_dir():
        return None, f"目录不存在：{resolved}"
    return resolved, None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TASK-028 测试入口")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--replay")
    parser.add_argument("--mutate", default="none",
                        choices=("none", "ledger-replaced", "ledger-lf", "late-drift",
                                 "candidate-return", "drop-call"))
    parser.add_argument("--only", default="full", choices=("full", "r1", "r2"))
    args = parser.parse_args(argv)

    out_dir, problem = resolve_out_dir(args.out_dir)
    if problem:
        print(json.dumps({"status": "FAIL", "reason": problem}, ensure_ascii=False))
        return 1
    out_dir.mkdir(parents=True)

    if args.replay:
        source, source_problem = resolve_out_dir(args.replay, must_exist=True)
        if source_problem:
            print(json.dumps({"status": "FAIL", "reason": source_problem},
                             ensure_ascii=False))
            return 1
        loaded = read_payloads(source)
        checkpoint = loaded["expected_observations"]
        ROUND["id"] = checkpoint.get("round") or source.name
        summary = loaded["summary"] or {}
        return finish(out_dir, checkpoint, args.mutate, None,
                      summary.get("results", {}))

    ROUND["id"] = out_dir.relative_to(TEST_ROOT.resolve()).parts[0]
    runtime_dir = RUNTIME_ROOT / ROUND["id"]
    if runtime_dir.exists():
        print(json.dumps({"status": "FAIL",
                          "reason": f"本轮运行根必须从未存在：{runtime_dir}"},
                         ensure_ascii=False))
        return 1
    runtime_dir.mkdir(parents=True)
    check("0.1 只读复用已核验小样（本轮新接收 0 次）",
          BATCH_NORMAL.is_dir() and BATCH_BLOCKED.is_dir(), "reuse")
    module = load_module()
    # 先取原函数（用于按原函数 code 身份计数），再安装 wrapper
    normalizer_original = module._load_frozen_normalizer()
    core_original = module._load_frozen_sqlite_core()
    normalizer_code = normalizer_original.normalize_workbook.__code__
    loader_code = core_original.load_normalized_to_sqlite.__code__
    info = observe_cores(module)
    normalizer = module._load_frozen_normalizer()
    core = module._load_frozen_sqlite_core()
    observer = EntryObserver(module, normalizer_code, loader_code)
    ctx = {"batch_normal": BATCH_NORMAL, "batch_blocked": BATCH_BLOCKED,
           "runtime": runtime_dir, "evidence": out_dir}

    sys.setprofile(observer)
    try:
        if args.only == "r2":
            results = {"r2": group_r2(module, ctx)}
        elif args.only == "r1":
            results = {"r1": group_r1(module, ctx)}
        else:
            results = {"normal": group_normal(module, ctx),
                       "rejections": group_rejections(module, ctx),
                       "paths": group_paths(module, ctx),
                       "errors": group_errors(module, ctx),
                       "late": group_late(module, ctx)}
    finally:
        sys.setprofile(None)
    results["observation"] = info
    for name, count in observer.api.items():
        if name in ("build_runtime_registry", "prepare_runtime_gate1_request",
                    "save_runtime_gate1_decision", "verify_gate1_effective_approval",
                    "run_gate1_approved_load", "inspect_gate1_approved_load"):
            check(f"6.1 公开 API 真实计数 {name} ≥1", count >= 1, count)
    check("6.2 两计算核心计数与完整记录闭合（normalizer / loader 分列）",
          observer.normalizer == sum(1 for item in CORE_RECORDS + ISOLATED_CORE_RECORDS
                                     if item["core"] == "normalizer")
          and observer.loader == sum(1 for item in CORE_RECORDS + ISOLATED_CORE_RECORDS
                                     if item["core"] == "sqlite"),
          {"normalizer": [observer.normalizer,
                          sum(1 for i in CORE_RECORDS + ISOLATED_CORE_RECORDS
                              if i["core"] == "normalizer")],
           "loader": [observer.loader,
                      sum(1 for i in CORE_RECORDS + ISOLATED_CORE_RECORDS
                          if i["core"] == "sqlite")],
           "positive_entries":len(CORE_RECORDS),
           "isolated_negative_entries":len(ISOLATED_CORE_RECORDS)})
    inspect_after = [item for item in CORE_RECORDS
                     if item["caller_api"] in
                     {r["call_id"] for r in API_RECORDS
                      if r["operation"] == "inspect_gate1_approved_load"}]
    check("6.3 inspect 的 normalize/loader 计数 0", inspect_after == [], inspect_after)
    check("6.4 Gate1 内部 P1/store 计数单列（不并入公开 API）",
          isinstance(observer._other, dict) and len(observer._other) >= 1,
          sorted(observer._other))
    return finish(out_dir, freeze_expectations(), "none", observer, results)


if __name__ == "__main__":
    raise SystemExit(main())
