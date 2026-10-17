# -*- coding: utf-8 -*-
"""TASK-022-R1 测试与证据入口：快照保存/只读核验的异常、链接路径与观察证据定点修正。

运行（建议入口；证据容器与记录轮次根必须全新）：

    .venv\\Scripts\\python.exe -B tests\\test_store_demo_human_gate_decision.py \
        --out-dir data\\human_gate_decision_store_tests\\task022r1_<新名>

R1 变更：① verify 先做封闭类型/形状检查再消费、完整 I/O 错误映射、失败诊断先绑定原因链；
② 原始路径（含允许根）+ 解析后链路的链接/reparse 拒绝（保存与核验均适用）；
③ 存储 API / 嵌套真实 P1 / 测试直接真实 P1 三类调用分列登记并闭合、捕获真实 `io.open` 读取、
末次必要消费后再注入。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CASES_DOC = (PROJECT_ROOT / "docs" / "proposals"
             / "HUMAN_GATE_DECISION_CASES_V1_DRAFT.md")
RECORDS_ROOT = PROJECT_ROOT / "data" / "human_gate_decision_records"
P1_CORE_PATH = SCRIPTS_DIR / "build_demo_human_gate_decision.py"
STORE_PATH = SCRIPTS_DIR / "store_demo_human_gate_decision.py"
CONTRACT_PATH = PROJECT_ROOT / "docs" / "AUDIT_CONTRACT.md"
EFFECTIVE_RECORD_PATH = (PROJECT_ROOT / "docs" / "decisions"
                         / "AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md")
PROTOCOL_PATH = PROJECT_ROOT / "docs" / "proposals" / "HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md"
HOST_PATH = SCRIPTS_DIR / "run_demo_workflow.py"
CONTROLLER_PATH = SCRIPTS_DIR / "control_demo_workflow.py"
FIXTURE_TAG = "PROTOCOL_TEST_FIXTURE_ONLY"

# 冻结身份（生产组件只绑定前四项；其余由测试/保护层核对）
FROZEN = {
    "P1_core": "5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79",
    "contract": "174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad",
    "contract_effective_record":
        "042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d",
    "protocol": "68c931b33ac51bdc5634247748d20463816e1a3a2105202fdd43942db26a3e76",
    "cases": "bd1fc37dc2437454b87b5453d7df90a6dcd6f3f79e84c3e75a335381fcf2d2a6",
    "host": "3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307",
    "controller": "a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c",
}

sys.path.insert(0, str(SCRIPTS_DIR))
import store_demo_human_gate_decision as store  # noqa: E402

H = lambda ch: ch * 64  # noqa: E731


# --------------------------------------------------------------------------- 独立实现
def _canon(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _fp(obj) -> str:
    return hashlib.sha256(_canon(obj)).hexdigest()


def _lf(obj) -> bytes:
    return _canon(obj) + b"\n"


def _deep(obj):
    return json.loads(json.dumps(obj))


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


_ABBREV = re.compile(r"^([0-9a-f])\1{0,2}…\1$")


def _expand(node):
    if isinstance(node, dict):
        return {key: _expand(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_expand(item) for item in node]
    if isinstance(node, str):
        match = _ABBREV.match(node)
        if match:
            return match.group(1) * 64
    return node


def _doc_blocks():
    text = CASES_DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
    if len(blocks) != 3:
        raise SystemExit(f"案例正文 JSON 块数应为 3，实际 {len(blocks)}")
    return tuple(_expand(json.loads(block)) for block in blocks)


DOC_MATERIALS1, DOC_RECORD1, DOC_MATERIALS2 = _doc_blocks()


def _base1_inputs():
    materials = _deep(DOC_MATERIALS1)
    request_id = DOC_RECORD1["binding"]["request_id"]
    submission = {
        "submission_version": "TASK-020-human-gate-decision-submission-1.1",
        "event_id": DOC_RECORD1["event_id"], "batch_id": DOC_RECORD1["batch_id"],
        "gate": "GATE1",
        "request_binding": {"request_id": request_id,
                            "materials_binding": materials["materials_fingerprint"]},
        "decision": "APPROVE", "decision_source": "HUMAN_GATE_DECISION",
        "actor": _deep(DOC_RECORD1["actor"]),
        "decided_at_raw": DOC_RECORD1["decided_at_raw"], "reason": DOC_RECORD1["reason"],
        "prior_decision_binding": None,
    }
    expectations = {
        "expected_batch_id": materials["batch_id"], "expected_gate": "GATE1",
        "expected_request_id": request_id,
        "expected_materials_fingerprint": materials["materials_fingerprint"],
        "expected_files": {item["relative"]: item["file_sha256"]
                           for item in materials["files"]},
        "expected_contract": {
            "contract_version": materials["contract_binding"]["contract_version"],
            "contract_file_sha256": materials["contract_binding"]["contract_file_sha256"]},
        "expected_run_binding": _deep(materials["run_binding"]),
        "expected_prior_gate1": None,
    }
    prior_history = {"declared_complete": True, "declared_scope": "FIXTURE-SCOPE-2026-10-13",
                     "records": []}
    return {"submission": submission, "materials": materials, "expectations": expectations,
            "prior_history": prior_history}


def _gate2_inputs():
    materials = _deep(DOC_MATERIALS2)
    record = _deep(DOC_RECORD1)
    wrapper = {"wrapper_version": "TASK-020-human-gate-decision-record-wrapper-1.1",
               "record_fingerprint": _fp(record), "record": record}
    request_id = "FIXTURE-REQ-G2-0001"
    submission = {
        "submission_version": "TASK-020-human-gate-decision-submission-1.1",
        "event_id": "FIXTURE-EV-G2-0001", "batch_id": materials["batch_id"],
        "gate": "GATE2",
        "request_binding": {"request_id": request_id,
                            "materials_binding": materials["materials_fingerprint"]},
        "decision": "APPROVE", "decision_source": "HUMAN_GATE_DECISION",
        "actor": _deep(DOC_RECORD1["actor"]),
        "decided_at_raw": "2026-10-13T19:00:00+08:00",
        "reason": "FIXTURE：装载、质量与勾稽核验通过，同意进入规则筛查（设计夹具，无审批效力）",
        "prior_decision_binding": _deep(wrapper),
    }
    expectations = {
        "expected_batch_id": materials["batch_id"], "expected_gate": "GATE2",
        "expected_request_id": request_id,
        "expected_materials_fingerprint": materials["materials_fingerprint"],
        "expected_files": {item["relative"]: item["file_sha256"]
                           for item in materials["files"]},
        "expected_contract": {
            "contract_version": materials["contract_binding"]["contract_version"],
            "contract_file_sha256": materials["contract_binding"]["contract_file_sha256"]},
        "expected_run_binding": _deep(materials["run_binding"]),
        "expected_prior_gate1": {"gate": "GATE1", "batch_id": record["batch_id"],
                                 "event_id": record["event_id"],
                                 "record_fingerprint": wrapper["record_fingerprint"],
                                 "run_binding": _deep(record["binding"]["run_binding"])},
    }
    prior_history = {"declared_complete": True, "declared_scope": "FIXTURE-SCOPE-2026-10-13",
                     "records": [_deep(wrapper)]}
    return {"submission": submission, "materials": materials, "expectations": expectations,
            "prior_history": prior_history}


def _expected_record1(inputs):
    """从冻结正文 record1 + 本次输入独立推导期望记录（不调用被测核心）。

    仅用于 G1 的 Gate1 控制：记录中可派生的字段一律由输入对象重算。
    """
    record = _deep(DOC_RECORD1)
    submission = inputs["submission"]
    materials = inputs["materials"]
    record["gate"] = submission["gate"]
    record["batch_id"] = submission["batch_id"]
    record["event_id"] = submission["event_id"]
    record["decision"] = submission["decision"]
    record["reason"] = submission["reason"]
    record["decided_at_raw"] = submission["decided_at_raw"]
    record["actor"] = _deep(submission["actor"])
    record["binding"] = {
        "request_id": submission["request_binding"]["request_id"],
        "materials_fingerprint": materials["materials_fingerprint"],
        "materials_files": _deep(materials["files"]),
        "contract_binding": _deep(materials["contract_binding"]),
        "run_binding": _deep(materials["run_binding"]),
    }
    record["prior_gate1"] = None
    record["quality_summary"] = {
        "status": materials["quality"]["status"],
        "structural_blockers_count": len(materials["quality"]["structural_blockers"]),
        "quality_blockers_count": len(materials["quality"]["quality_blockers"]),
        "verification_failures_count": len(materials["quality"]["verification_failures"]),
    }
    return record


def _variant(inputs, mutate):
    out = _deep(inputs)
    mutate(out)
    return out


def _blocked_hold(inputs):
    def mutate(target):
        materials = target["materials"]
        materials["quality"] = {"status": "BLOCKED", "structural_blockers": [],
                                "quality_blockers": ["FIXTURE-QUALITY-1"],
                                "verification_failures": []}
        body = {key: value for key, value in materials.items()
                if key != "materials_fingerprint"}
        materials["materials_fingerprint"] = _fp(body)
        target["submission"]["request_binding"]["materials_binding"] = \
            materials["materials_fingerprint"]
        target["submission"]["decision"] = "HOLD"
        target["expectations"]["expected_materials_fingerprint"] = \
            materials["materials_fingerprint"]
    return _variant(inputs, mutate)


def _decide(inputs, decision):
    return _variant(inputs, lambda target: target["submission"].__setitem__(
        "decision", decision))


# --------------------------------------------------------------------------- 真实核心观察
class _P1Observer:
    """在冻结 P1 模块的公开函数上观察每次真实调用（完整输入/返回/异常 + 引用与指纹时点）。"""

    def __init__(self, module):
        self.module = module
        self.original = module.build_human_gate_decision_record
        self.code = self.original.__code__
        self.records = []
        self.consumed_refs = []
        self.entry_count = 0
        self.current_scope = "direct"

    def __call__(self, frame, event, arg):
        if event == "call" and frame.f_code is self.code:
            self.entry_count += 1

    def install(self):
        def wrapper(submission, materials, expectations, *, prior_history=None):
            entry = {
                "core_call_id": f"core-{len(self.records) + 1:03d}",
                "scope": self.current_scope,
                "kind": "nested" if self.current_scope != "direct" else "direct",
                "inputs": {"submission": _deep(submission), "materials": _deep(materials),
                           "expectations": _deep(expectations),
                           "prior_history": _deep(prior_history)},
                "input_ids": {"submission": id(submission), "materials": id(materials),
                              "expectations": id(expectations),
                              "prior_history": id(prior_history)},
                "input_fingerprints_before": {"submission": _fp(submission),
                                              "materials": _fp(materials),
                                              "expectations": _fp(expectations),
                                              "prior_history": _fp(prior_history)},
                "input_fingerprints_at_api_finalize": None,
                "result": None,
                "exception": None,
                "outcome": "unknown",
            }
            try:
                result = self.original(submission, materials, expectations,
                                       prior_history=prior_history)
            except BaseException as exc:  # noqa: BLE001
                entry["outcome"] = "raised"
                entry["exception"] = {"type": type(exc).__name__,
                                      "field": getattr(exc, "field", None),
                                      "stage": getattr(exc, "stage", None),
                                      "reason": str(exc),
                                      "traceback": traceback.format_exc(),
                                      "cause_chain": store._exception_chain(exc)}
                entry["input_fingerprints_after"] = {"submission": _fp(submission),
                                                     "materials": _fp(materials),
                                                     "expectations": _fp(expectations),
                                                     "prior_history": _fp(prior_history)}
                entry["references_unchanged"] = (
                    entry["input_ids"] == {"submission": id(submission),
                                           "materials": id(materials),
                                           "expectations": id(expectations),
                                           "prior_history": id(prior_history)})
                self.consumed_refs.append((entry["core_call_id"], submission, materials,
                                           expectations, prior_history))
                self.records.append(entry)
                raise
            entry["outcome"] = "returned"
            entry["result"] = _deep(result)
            entry["input_fingerprints_after"] = {"submission": _fp(submission),
                                                 "materials": _fp(materials),
                                                 "expectations": _fp(expectations),
                                                 "prior_history": _fp(prior_history)}
            entry["references_unchanged"] = (
                entry["input_ids"] == {"submission": id(submission),
                                       "materials": id(materials),
                                       "expectations": id(expectations),
                                       "prior_history": id(prior_history)})
            self.consumed_refs.append((entry["core_call_id"], submission, materials,
                                       expectations, prior_history))
            self.records.append(entry)
            return result

        self.module.build_human_gate_decision_record = wrapper
        sys.setprofile(self)

    def uninstall(self):
        self.module.build_human_gate_decision_record = self.original
        sys.setprofile(None)


# --------------------------------------------------------------------------- I/O 观察
class _IoGuard:
    """观察真实 open/io.open/os.open/os.write/os.read/os.close；守卫 socket/子进程。"""

    def __init__(self):
        self.log = []
        self.forbidden = 0
        self._saved = {}

    def _wrap(self, module, name, label):
        original = getattr(module, name)

        def guarded(*args, **kwargs):
            mode = None
            for value in list(args) + list(kwargs.values()):
                if isinstance(value, str) and value and value[0] in "rwxa":
                    mode = value
                    break
            entry = {"op": label, "arg": str(args[0])[:300] if args else None,
                     "mode": mode, "length": next((len(v) for v in args
                                                   if isinstance(v, (bytes, bytearray,
                                                                     memoryview))), None)}
            if label in ("open", "io.open", "os.open"):
                entry["access"] = ("write" if mode and any(ch in mode for ch in "wxa")
                                   else "read" if mode else "unknown")
            elif label == "os.write":
                entry["access"] = "write"
            elif label == "os.read":
                entry["access"] = "read"
            self.log.append(entry)
            return original(*args, **kwargs)

        self._saved[(module, name)] = original
        setattr(module, name, guarded)

    def _wrap_forbidden(self, module, name, label):
        original = getattr(module, name)

        def guarded(*args, **kwargs):
            self.forbidden += 1
            self.log.append({"op": f"FORBIDDEN:{label}", "arg": str(args)[:200],
                             "mode": None, "length": None})
            return original(*args, **kwargs)

        self._saved[(module, name)] = original
        setattr(module, name, guarded)

    def arm(self):
        import builtins
        import socket
        self._wrap(builtins, "open", "open")
        self._wrap(io, "open", "io.open")
        self._wrap(os, "open", "os.open")
        self._wrap(os, "write", "os.write")
        self._wrap(os, "read", "os.read")
        self._wrap(os, "close", "os.close")
        self._wrap_forbidden(socket, "socket", "socket.socket")
        self._wrap_forbidden(subprocess, "Popen", "subprocess.Popen")

    def disarm(self):
        for (module, name), original in self._saved.items():
            setattr(module, name, original)
        self._saved = {}

    def mark(self, label):
        self.log.append({"op": f"MARK:{label}", "arg": None, "mode": None, "length": None})


def _initial_input_scene(leaf):
    """verify 调用的**初始输入现场**：record_dir、文件集合与各文件确切大小/SHA。

    不存在/不可读时记录明确状态与原因，不填未观察的空白成功值。
    """
    if leaf is None:
        return {"status": "not_available", "reason": "无输入路径"}
    scene = {"record_dir": str(leaf)}
    try:
        if not leaf.exists():
            scene.update({"status": "not_available", "reason": "路径不存在"})
            return scene
        if not leaf.is_dir():
            scene.update({"status": "not_available", "reason": "路径不是目录"})
            return scene
        files = sorted(entry.name for entry in leaf.iterdir())
        scene["file_set"] = files
        sizes = {}
        for name in files:
            target = leaf / name
            if target.is_file():
                data = target.read_bytes()
                sizes[name] = {"bytes": len(data), "sha256": _sha_bytes(data)}
            else:
                sizes[name] = {"status": "not_available", "reason": "不是正常文件"}
        scene["files"] = sizes
        scene["status"] = "observed"
    except OSError as exc:
        scene.update({"status": "not_available", "reason": f"{type(exc).__name__}: {exc}"})
    return scene


def _dir_snapshot(path: Path):
    snapshot = {}
    for entry in sorted(path.rglob("*")):
        if entry.is_file():
            snapshot[entry.relative_to(path).as_posix()] = {
                "bytes": entry.stat().st_size, "sha256": _sha_file(entry)}
        else:
            snapshot[entry.relative_to(path).as_posix() + "/"] = {"dir": True}
    return snapshot


# --------------------------------------------------------------------------- 调用登记
class Registry:
    def __init__(self, observer, guard):
        self.records = []
        self.calls = 0
        self.observer = observer
        self.guard = guard

    def call(self, case_ids, kind, target, func, *args, guard=None, **kwargs):
        self.calls += 1
        call_id = f"call-{self.calls:03d}"
        log_before = len(self.guard.log)
        core_before = len(self.observer.records)
        self.observer.current_scope = call_id
        inputs = None
        if len(args) >= 4 and isinstance(args[1], dict):
            inputs = {"submission": _deep(args[1]), "materials": _deep(args[2]),
                      "expectations": _deep(args[3]),
                      "prior_history": _deep(kwargs.get("prior_history")),
                      "prior_history_omitted": "prior_history" not in kwargs,
                      "record_dir": None}
        else:
            leaf = Path(args[0]) if args else None
            inputs = {"record_dir": str(leaf),
                      "initial_input_scene": _initial_input_scene(leaf)}
        result = {"outcome": "unknown"}
        exception = None
        try:
            returned = func(*args, **kwargs)
            result = {"outcome": "returned", "keys": sorted(returned.keys()),
                      "status": returned.get("status"), "scope": returned.get("scope"),
                      "identity": returned.get("identity"),
                      "record_fingerprint": returned.get("record_fingerprint"),
                      "manifest_file_sha256": returned.get("manifest_file_sha256"),
                      "execution_allowed": returned.get("execution_allowed"),
                      "workflow_connected": returned.get("workflow_connected"),
                      "ai_enabled": returned.get("ai_enabled")}
        except store.HumanGateDecisionStoreBlocked as exc:
            result = {"outcome": "blocked", "field": exc.field, "reason": exc.reason}
            exception = {"type": type(exc).__name__, "field": exc.field, "reason": exc.reason,
                         "traceback": traceback.format_exc(),
                         "cause_chain": store._exception_chain(exc)}
        except store.HumanGateDecisionStoreError as exc:
            result = {"outcome": "error", "stage": exc.stage, "reason": exc.reason}
            exception = {"type": type(exc).__name__, "stage": exc.stage, "reason": exc.reason,
                         "traceback": traceback.format_exc(),
                         "cause_chain": store._exception_chain(exc)}
        except BaseException as exc:  # noqa: BLE001
            result = {"outcome": "unexpected", "exception_type": type(exc).__name__,
                      "reason": str(exc)}
            exception = {"type": type(exc).__name__, "reason": str(exc),
                         "traceback": traceback.format_exc(),
                         "cause_chain": store._exception_chain(exc)}
        finally:
            self.observer.current_scope = "direct"
            # API 收尾第三时点：从**保留的真实消费引用**复算指纹（不再调用核心、不修改对象）
            refs = {entry[0]: entry[1:] for entry in self.observer.consumed_refs}
            for entry in self.observer.records[core_before:]:
                held = refs.get(entry["core_call_id"])
                if held is None:
                    continue
                submission, materials, expectations, prior_history = held
                entry["input_fingerprints_at_api_finalize"] = {
                    "submission": _fp(submission), "materials": _fp(materials),
                    "expectations": _fp(expectations), "prior_history": _fp(prior_history)}
                entry["third_timepoint_matches"] = (
                    entry["input_fingerprints_at_api_finalize"]
                    == entry["input_fingerprints_before"]
                    == entry["input_fingerprints_after"])
        nested = self.observer.records[core_before:]
        record = {
            "call_id": call_id,
            "case_ids": list(case_ids),
            "kind": kind,
            "target": str(target) if target is not None else None,
            "inputs": inputs,
            "result": result,
            "exception": exception,
            "nested_core_call_ids": [entry["core_call_id"] for entry in nested],
            "nested_p1_calls_observed": len(nested),
            "io_ops_in_call": self.guard.log[log_before:],
        }
        self.records.append(record)
        return record


def _core_registry(observer):
    kinds = {}
    for entry in observer.records:
        kinds[entry["kind"]] = kinds.get(entry["kind"], 0) + 1
    return {
        "authoritative": True,
        "entries": observer.records,
        "total_core_entries": len(observer.records),
        "by_kind": kinds,
        "entry_frame_observation": observer.entry_count,
        "closure_ok": len(observer.records) == observer.entry_count,
        "core_call_ids": [entry["core_call_id"] for entry in observer.records],
    }


def _entry_complete(entry):
    """单条核心 entry 是否含完整输入与完整返回/异常载荷。

    R3：`returned` 的载荷必须是冻结 P1 的**完整两键外层**（`record` + `record_fingerprint`），
    `{}` 等不可能的成功外层不再被视为完整；完整内容是否等于**本次真实观察**由内容比较负责。
    """
    inputs = entry.get("inputs")
    if not isinstance(inputs, dict) or set(inputs.keys()) != {"submission", "materials",
                                                              "expectations", "prior_history"}:
        return False
    if entry.get("outcome") == "returned":
        result = entry.get("result")
        return (isinstance(result, dict)
                and set(result.keys()) == {"record", "record_fingerprint"}
                and isinstance(result.get("record"), dict)
                and isinstance(result.get("record_fingerprint"), str))
    exception = entry.get("exception")
    return (isinstance(exception, dict) and bool(exception.get("traceback"))
            and isinstance(exception.get("cause_chain"), list)
            and bool(exception.get("reason")))


def _canonical_equal(expected, candidate):
    """R4 **主判据**：按已约定 canonical JSON 字节严格相等（UTF-8/ensure_ascii=False/
    sort_keys=True/固定 separators/allow_nan=False），不使用 Python `==`。

    Python 宽松数值相等会掩盖 `false`/`0`/`0.0` 的规范差异；此处直接比较规范字节。
    """
    return _canon(expected) == _canon(candidate)


def _leaf_diagnostic(expected, candidate, path):
    return {
        "path": path or "(root)",
        "difference": "canonical_bytes_differ",
        "expected_type": type(expected).__name__,
        "candidate_type": type(candidate).__name__,
        "type_difference": type(expected) is not type(candidate),
        "expected_canonical": _canon(expected).decode("utf-8")[:120],
        "candidate_canonical": _canon(candidate).decode("utf-8")[:120],
        "expected_sha256": _sha_bytes(_canon(expected)),
        "candidate_sha256": _sha_bytes(_canon(candidate)),
    }


def _field_diff(expected, candidate, prefix="", limit=40):
    """**有界诊断**：按 canonical JSON 字节定位差异字段路径（不决定是否忽略真实差异）。

    值相等一律以规范字节判定（键顺序不同但规范字节相同的对象视为相等）。
    """
    if _canonical_equal(expected, candidate):
        return []
    diffs = []
    if isinstance(expected, dict) and isinstance(candidate, dict):
        for key in sorted(set(expected.keys()) | set(candidate.keys())):
            path = f"{prefix}.{key}" if prefix else key
            if key not in candidate:
                diffs.append({"path": path, "difference": "missing_in_candidate"})
            elif key not in expected:
                diffs.append({"path": path, "difference": "extra_in_candidate"})
            else:
                diffs.extend(_field_diff(expected[key], candidate[key], path, limit))
    elif isinstance(expected, list) and isinstance(candidate, list):
        if len(expected) != len(candidate):
            diffs.append({"path": f"{prefix}[len]", "difference": "length_differs",
                          "expected": len(expected), "candidate": len(candidate)})
        for index, (left, right) in enumerate(zip(expected, candidate)):
            diffs.extend(_field_diff(left, right, f"{prefix}[{index}]", limit))
    else:
        diffs.append(_leaf_diagnostic(expected, candidate, prefix))
    return diffs[:limit]


def _observation_expectation(core_registry, api_records, call_registry_payload):
    """R3：从**本次真实观察结果**建立独立深拷贝预期（不读候选磁盘文件、不再调用 P1）。

    在任何终审读取之前冻结；有界两轮审核中**不因候选文件变化而刷新**。
    """
    return {
        "frozen_at": "all_api_and_core_observations_finalized_before_finalization",
        "source": "in_memory_real_observations",
        "core_call_registry": _deep(core_registry),
        "api_records": _deep(api_records),
        "call_registry": _deep(call_registry_payload),
        "counts": {"core_entries": len(core_registry.get("entries", [])),
                   "core_ids": len(core_registry.get("core_call_ids", [])),
                   "api_calls": len(api_records)},
    }


def _located_differences(want, candidate, key):
    """按记录定位差异：core 按 `core_call_id`、api 按 `call_id`。"""
    if key == "core_call_registry":
        id_field = "core_call_id"
        want_items = want.get("entries", []) if isinstance(want, dict) else []
        cand_items = candidate.get("entries", []) if isinstance(candidate, dict) else []
        extra_label, missing_label = ("extra_entry_not_in_observation",
                                      "missing_entry_against_observation")
    else:
        id_field = "call_id"
        want_items = want if isinstance(want, list) else []
        cand_items = candidate if isinstance(candidate, list) else []
        extra_label, missing_label = ("extra_call_not_in_observation",
                                      "missing_call_against_observation")
    want_by_id = {item.get(id_field): item for item in want_items}
    cand_by_id = {item.get(id_field): item for item in cand_items}
    located = {}
    for item_id in sorted(set(want_by_id) | set(cand_by_id), key=str):
        left, right = want_by_id.get(item_id), cand_by_id.get(item_id)
        if left is None:
            located[item_id] = [extra_label]
        elif right is None:
            located[item_id] = [missing_label]
        else:
            entry_diff = _field_diff(left, right)
            if entry_diff:
                located[item_id] = [item["path"] for item in entry_diff]
    return located


def _content_compare(expected, core_parsed, api_parsed, call_parsed):
    """完整解析对象与定稿真实观察预期的规范比较（含按记录定位的差异）。"""
    details = {}
    ok = True
    for name, key, candidate in (("core_call_registry.json", "core_call_registry", core_parsed),
                                 ("api_records.json", "api_records", api_parsed),
                                 ("call_registry.json", "call_registry", call_parsed)):
        want = expected[key]
        # R4 主判据：canonical JSON 字节严格相等；field_diff 只做有界诊断
        equal = _canonical_equal(want, candidate)
        diff = [] if equal else _field_diff(want, candidate)
        entry = {"file": name, "equal": equal,
                 "primary_criterion": "canonical_json_bytes_strict_equal",
                 "differences": diff,
                 "candidate_sha256": _sha_bytes(_canon(candidate)),
                 "expected_sha256": _sha_bytes(_canon(want)),
                 "candidate_top_level": type(candidate).__name__}
        if isinstance(want, dict):
            entry["compared_keys"] = sorted(want.keys())
        if key in ("core_call_registry", "api_records"):
            entry["located_differences"] = _located_differences(want, candidate, key)
        details[key] = entry
        ok = ok and equal
    details["ok"] = ok
    return details


def _content_isolation(expected, core_registry, api_records, call_registry_payload):
    """R3 定点：`{}` 返回替换与**合法形状的自洽内容替换**都必须被完整内容比较拒绝。"""
    def candidate(mutate):
        payload = {"core": _deep(core_registry), "api": _deep(api_records),
                   "call": _deep(call_registry_payload)}
        mutate(payload)
        return _content_compare(expected, payload["core"], payload["api"], payload["call"])

    def empty_result(payload):
        for entry in payload["core"]["entries"]:
            if entry.get("outcome") == "returned":
                entry["result"] = {}
                return

    def rewritten_reason(payload):
        for entry in payload["core"]["entries"]:
            if entry.get("outcome") == "returned":
                record = entry["result"]["record"]
                record["reason"] = "FIXTURE：合法形状但与该次真实观察不同的理由（自洽改写）"
                entry["result"]["record_fingerprint"] = _fp(record)
                return

    def rewritten_input(payload):
        for entry in payload["core"]["entries"]:
            entry["inputs"]["submission"]["reason"] = "FIXTURE：与该次真实观察不同的输入理由"
            return

    def counts_preserved(payload):
        return (len(payload["core"]["entries"]) == len(core_registry["entries"])
                and payload["core"]["core_call_ids"] == core_registry["core_call_ids"]
                and payload["core"]["total_core_entries"]
                == core_registry["total_core_entries"])

    # R4 §3 类型定点：False→0、整数0→浮点0.0 必须拒绝；键顺序不同但规范字节相同须通过
    def bool_to_int(payload):
        for entry in payload["core"]["entries"]:
            if entry.get("outcome") == "returned":
                entry["result"]["record"]["boundaries"]["persisted"] = 0
                return

    def int_to_float(payload):
        for entry in payload["core"]["entries"]:
            if entry.get("outcome") == "returned":
                entry["result"]["record"]["quality_summary"]["structural_blockers_count"] = 0.0
                return

    type_bool = candidate(bool_to_int)
    type_float = candidate(int_to_float)
    bool_payload = {"core": _deep(core_registry), "api": _deep(api_records),
                    "call": _deep(call_registry_payload)}
    bool_to_int(bool_payload)
    float_payload = {"core": _deep(core_registry), "api": _deep(api_records),
                     "call": _deep(call_registry_payload)}
    int_to_float(float_payload)
    reordered = {"core": {key: _deep(core_registry[key])
                          for key in reversed(list(core_registry.keys()))},
                 "api": _deep(api_records), "call": _deep(call_registry_payload)}
    reordered_result = _content_compare(expected, reordered["core"], reordered["api"],
                                        reordered["call"])

    empty = candidate(empty_result)
    reason = candidate(rewritten_reason)
    input_change = candidate(rewritten_input)
    original = _content_compare(expected, core_registry, api_records, call_registry_payload)
    reason_payload = {"core": _deep(core_registry), "api": _deep(api_records),
                      "call": _deep(call_registry_payload)}
    rewritten_reason(reason_payload)
    empty_payload = {"core": _deep(core_registry), "api": _deep(api_records),
                     "call": _deep(call_registry_payload)}
    empty_result(empty_payload)
    return {
        "original_content_compare_ok": original["ok"],
        "empty_result_rejected": not empty["ok"],
        "empty_result_located": empty["core_call_registry"]["located_differences"],
        "empty_result_counts_preserved": counts_preserved(empty_payload),
        "self_consistent_reason_rejected": not reason["ok"],
        "self_consistent_reason_located": reason["core_call_registry"]["located_differences"],
        "self_consistent_reason_counts_preserved": counts_preserved(reason_payload),
        "input_change_rejected": not input_change["ok"],
        "input_change_located": input_change["core_call_registry"]["located_differences"],
        "entry_completeness_rejects_empty": not _entry_complete(
            {"outcome": "returned",
             "inputs": {"submission": {}, "materials": {}, "expectations": {},
                        "prior_history": {}},
             "result": {}, "exception": None}),
        "bool_to_int_rejected": not type_bool["ok"],
        "bool_to_int_equal_flag": type_bool["core_call_registry"]["equal"],
        "bool_to_int_located": type_bool["core_call_registry"]["located_differences"],
        "bool_to_int_counts_preserved": counts_preserved(bool_payload),
        "int_to_float_rejected": not type_float["ok"],
        "int_to_float_equal_flag": type_float["core_call_registry"]["equal"],
        "int_to_float_located": type_float["core_call_registry"]["located_differences"],
        "int_to_float_counts_preserved": counts_preserved(float_payload),
        "key_order_only_change_accepted": reordered_result["ok"],
        "key_order_canonical_equal": _canonical_equal(
            expected["core_call_registry"], reordered["core"]),
        "python_equal_would_miss": (0 == False and 0 == 0.0
                                    and not _canonical_equal(False, 0)
                                    and not _canonical_equal(0, 0.0)),
    }


def _core_audit(registry_payload, api_records):
    """审核**完整 entries**集合关系，而非只比 call_ids 字符串数量。"""
    ids = list(registry_payload.get("core_call_ids", []))
    entries = registry_payload.get("entries", [])
    entry_ids = [entry.get("core_call_id") for entry in entries]
    api_nested = [call_id for record in api_records
                  for call_id in record.get("nested_core_call_ids", [])]
    seen_ids = set()
    duplicates = sorted({item for item in ids if item in seen_ids or seen_ids.add(item)})
    seen_entries = set()
    duplicate_entry_ids = sorted({item for item in entry_ids
                                  if item in seen_entries or seen_entries.add(item)})
    detail = {
        "label": "core",
        "declared_total": registry_payload.get("total_core_entries"),
        "ids_total": len(ids),
        "entries_total": len(entries),
        "entry_frame_observation": registry_payload.get("entry_frame_observation"),
        "api_nested_total": len(api_nested),
        "duplicate_ids": duplicates,
        "duplicate_entry_ids": duplicate_entry_ids,
        "ids_without_entry": sorted(set(ids) - set(entry_ids)),
        "entries_without_id": sorted(set(entry_ids) - set(ids)),
        "incomplete_entry_ids": sorted(entry.get("core_call_id") for entry in entries
                                       if not _entry_complete(entry)),
        "missing_in_api_nested": sorted(set(ids) - set(api_nested)),
        "extra_in_api_nested": sorted(set(api_nested) - set(ids)),
    }
    detail["counts_consistent"] = (
        detail["declared_total"] == detail["ids_total"] == detail["entries_total"]
        == detail["api_nested_total"] == detail["entry_frame_observation"])
    detail["ok"] = (detail["counts_consistent"] and not duplicates
                    and not detail["duplicate_entry_ids"]
                    and not detail["ids_without_entry"]
                    and not detail["entries_without_id"]
                    and not detail["incomplete_entry_ids"]
                    and not detail["missing_in_api_nested"]
                    and not detail["extra_in_api_nested"])
    return detail


def _core_audit_from_disk(out_dir: Path, phase="final"):
    """真实磁盘读回：**同一读取缓冲**取对象与文件 SHA，再审核完整 entries 关系。"""
    registry_path = out_dir / "core_call_registry.json"
    api_path = out_dir / "api_records.json"
    try:
        registry_bytes = registry_path.read_bytes()
        api_bytes = api_path.read_bytes()
    except OSError as exc:
        return {"phase": phase, "ok": False, "io_error": str(exc), "label": "core"}
    registry_payload = json.loads(registry_bytes.decode("utf-8"))
    api_records = json.loads(api_bytes.decode("utf-8"))
    detail = _core_audit(registry_payload, api_records)
    detail.update({
        "phase": phase,
        "source": "disk_read_back",
        "same_buffer_binding": True,
        "core_call_registry_file_sha256": _sha_bytes(registry_bytes),
        "core_call_registry_file_bytes": len(registry_bytes),
        "api_records_file_sha256": _sha_bytes(api_bytes),
        "api_records_file_bytes": len(api_bytes),
    })
    return detail


def _audited_read(out_dir: Path, names):
    """一次性读入全部载荷字节（对象与 SHA 绑定于同一缓冲），供终审与台账期望使用。"""
    audited = {}
    for name in names:
        data = (out_dir / name).read_bytes()
        entry = {"bytes": len(data), "sha256": _sha_bytes(data)}
        if name.endswith(".json"):
            entry["parsed"] = json.loads(data.decode("utf-8"))
        audited[name] = entry
    return audited


def _api_audit_from_audited(audited):
    registry = audited["call_registry.json"]["parsed"]
    api_records = audited["api_records.json"]["parsed"]
    detail = _audit_pair(list(registry.get("call_ids", [])),
                         [record.get("call_id") for record in api_records], label="api")
    detail["declared_total_matches"] = registry.get("total_store_api_calls") == len(
        registry.get("call_ids", []))
    detail["ok"] = detail["ok"] and detail["declared_total_matches"]
    return detail


def _api_audit_from_disk(out_dir: Path):
    registry = json.loads((out_dir / "call_registry.json").read_text(encoding="utf-8"))
    api_records = json.loads((out_dir / "api_records.json").read_text(encoding="utf-8"))
    detail = _audit_pair(list(registry.get("call_ids", [])),
                         [record.get("call_id") for record in api_records], label="api")
    detail["declared_total_matches"] = registry.get("total_store_api_calls") == len(
        registry.get("call_ids", []))
    detail["ok"] = detail["ok"] and detail["declared_total_matches"]
    return detail


def _core_isolation(registry_payload, api_records):
    ids = list(registry_payload.get("core_call_ids", []))
    # 1) 只删一个 ID（保留完整 entries）——沿用 R1 成果
    copy_ids = dict(registry_payload)
    copy_ids["core_call_ids"] = ids[:-1]
    original = _core_audit(registry_payload, api_records)
    # 2) 只删一个**完整 entries 成员**，保留 ID 名单/声明 total/入口计数（R2 新增）
    entries = list(registry_payload.get("entries", []))
    copy_entries = dict(registry_payload)
    copy_entries["entries"] = entries[:-1]
    copy_entries_audit = _core_audit(copy_entries, api_records)
    # 3) 重复 entry（集合错误）
    duplicate = dict(registry_payload)
    duplicate["entries"] = entries + entries[:1]
    duplicate_audit = _core_audit(duplicate, api_records)
    # 4) 不完整 entry（空壳记录）
    hollow = dict(registry_payload)
    hollow_entries = [dict(entry) for entry in entries]
    hollow_entries[-1] = {**hollow_entries[-1], "inputs": None, "result": None,
                          "exception": None, "outcome": "returned"}
    hollow["entries"] = hollow_entries
    hollow_audit = _core_audit(hollow, api_records)
    return {
        "removed_core_call_id": ids[-1] if ids else None,
        "id_only_copy_audit": _core_audit(copy_ids, api_records),
        "id_only_copy_fails": not _core_audit(copy_ids, api_records)["ok"],
        "removed_entry_id": entries[-1].get("core_call_id") if entries else None,
        "entry_removed_copy_audit": copy_entries_audit,
        "entry_removed_copy_fails": not copy_entries_audit["ok"],
        "duplicate_entry_audit": duplicate_audit,
        "duplicate_entry_fails": not duplicate_audit["ok"],
        "hollow_entry_audit": hollow_audit,
        "hollow_entry_fails": not hollow_audit["ok"],
        "original_audit": original,
        "original_passes": bool(original["ok"]),
    }


# --------------------------------------------------------------------------- 断言与台账
def _check(checks, failures, name, condition, detail=""):
    ok = bool(condition)
    checks.append({"name": name, "ok": ok, "detail": detail})
    if not ok:
        failures.append({"name": name, "detail": detail})
    return ok


def _audit_pair(registry_ids, api_ids, label="api"):
    seen = set()
    duplicates = sorted({item for item in registry_ids if item in seen or seen.add(item)})
    return {"label": label, "registry_total": len(registry_ids), "api_total": len(api_ids),
            "duplicate_ids": duplicates,
            "missing_in_api": sorted(set(registry_ids) - set(api_ids)),
            "extra_in_api": sorted(set(api_ids) - set(registry_ids)),
            "ok": (len(registry_ids) == len(api_ids) and not duplicates
                   and set(registry_ids) == set(api_ids))}


def _api_audit_from_disk(out_dir: Path):
    registry = json.loads((out_dir / "call_registry.json").read_text(encoding="utf-8"))
    api_records = json.loads((out_dir / "api_records.json").read_text(encoding="utf-8"))
    detail = _audit_pair(list(registry.get("call_ids", [])),
                         [record.get("call_id") for record in api_records], label="api")
    detail["declared_total_matches"] = registry.get("total_store_api_calls") == len(
        registry.get("call_ids", []))
    detail["ok"] = detail["ok"] and detail["declared_total_matches"]
    return detail


def _ledger_validate(root: Path, entries: dict, ignore=()):
    missing, unregistered = [], []
    layered = set(LAYERED_FILES) | set(ignore) | {"evidence_ledger.json"}
    for relative, entry in entries.items():
        target = root / relative
        if not target.is_file():
            missing.append(relative)
            continue
        if target.stat().st_size != entry["bytes"] or _sha_file(target) != entry["sha256"]:
            missing.append(relative)
    for entry in sorted(root.rglob("*")):
        if entry.is_file():
            relative = entry.relative_to(root).as_posix()
            if relative not in entries and relative not in layered:
                unregistered.append(relative)
    return {"missing": missing, "unregistered": unregistered}


def _ledger_from_disk(root: Path, names, phase="stabilize"):
    return {"phase": phase,
            "entries": {name: {"exists": True, "bytes": (root / name).stat().st_size,
                               "sha256": _sha_file(root / name)} for name in names}}


def _file_ledger_isolation(root: Path, entries: dict):
    audit_copy = {key: value for key, value in entries.items() if key != "checks.json"}
    original = _ledger_validate(root, entries)
    copy_result = _ledger_validate(root, audit_copy)
    return {"removed_entry": "checks.json", "audit_copy_result": copy_result,
            "audit_copy_fails": bool(copy_result["unregistered"] or copy_result["missing"]),
            "original_result": original,
            "original_passes": not original["missing"] and not original["unregistered"]}


PAYLOADS = ("api_records.json", "call_registry.json", "checks.json", "core_call_registry.json",
            "counts.json", "failures.json", "fixture_registration.json",
            "io_observations.json", "isolation_self_tests.json", "read_observation.json",
            "store_inventory.json", "summary.json", "test_frozen_identities.json")
LAYERED_FILES = ("evidence_ledger.json", "final_audit_diagnostic.json",
                 "protection_result.json", "scan_protection.py")


def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _copy_record_dir(source: Path, target: Path):
    target.mkdir(parents=True, exist_ok=False)
    for entry in source.iterdir():
        shutil.copyfile(entry, target / entry.name)
    return target


def _rewrite_payload(record_dir: Path, name: str, obj):
    (record_dir / name).write_bytes(_lf(obj))


def _sync_manifest_entry(record_dir: Path, name: str, *, fingerprints=None):
    manifest = json.loads((record_dir / "manifest.json").read_text(encoding="utf-8"))
    data = (record_dir / name).read_bytes()
    for entry in manifest["payloads"]:
        if entry["relative"] == name:
            entry["byte_size"] = len(data)
            entry["file_sha256"] = _sha_bytes(data)
    if fingerprints:
        manifest["fingerprints"].update(fingerprints)
    (record_dir / "manifest.json").write_bytes(_lf(manifest))
    return manifest


def _bump_manifest(record_dir: Path, mutate):
    manifest = json.loads((record_dir / "manifest.json").read_text(encoding="utf-8"))
    mutate(manifest)
    (record_dir / "manifest.json").write_bytes(_lf(manifest))


def _mutate_submission_batch(record_dir: Path):
    submission = json.loads((record_dir / "submission.json").read_text(encoding="utf-8"))
    submission["batch_id"] = "FIXTURE-BATCH-Z"
    _rewrite_payload(record_dir, "submission.json", submission)
    _sync_manifest_entry(record_dir, "submission.json",
                         fingerprints={"submission_fingerprint": _fp(submission)})


def _mutate_inner_binding(record_dir: Path):
    submission = json.loads((record_dir / "submission.json").read_text(encoding="utf-8"))
    submission["request_binding"]["materials_binding"] = H("9")
    _rewrite_payload(record_dir, "submission.json", submission)
    _sync_manifest_entry(record_dir, "submission.json",
                         fingerprints={"submission_fingerprint": _fp(submission)})


def _outcome_counts(records):
    counts = {"returned": 0, "blocked": 0, "error": 0, "unexpected": 0}
    for record in records:
        counts[record["result"]["outcome"]] = counts.get(record["result"]["outcome"], 0) + 1
    return counts


def _kind_counts(records):
    counts = {}
    for record in records:
        counts[record["kind"]] = counts.get(record["kind"], 0) + 1
    return counts


def _create_junction(alias: Path, target: Path):
    """用真实 Windows junction（mklink /J）复现链接路径反例；失败则如实报告未执行。"""
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(target)],
                            capture_output=True, text=True)
    created = alias.exists() and os.path.islink(str(alias)) is False and _is_reparse(alias)
    return {"returncode": result.returncode, "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(), "created": bool(created)}


def _is_reparse(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    import stat as _stat
    if _stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(_stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


# --------------------------------------------------------------------------- 主流程
def run_suite(out_dir: Path):
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"证据容器必须为新/空目录，实际非空：{out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    round_root = RECORDS_ROOT / out_dir.name
    round_root.mkdir(parents=True, exist_ok=True)

    checks, failures = [], []
    observer = _P1Observer(store._core())
    observer.install()
    guard = _IoGuard()
    registry = Registry(observer, guard)

    def record_dir(name: str) -> Path:
        return round_root / name

    def store_call(case_ids, kind, leaf, func, *args, **kwargs):
        guard.arm()
        try:
            return registry.call(case_ids, kind, leaf, func, *args, guard=guard,
                                 **kwargs)
        finally:
            guard.disarm()

    def save_case(case_ids, leaf, inputs, *, prior_history="keep"):
        kwargs = {}
        if prior_history == "keep":
            kwargs["prior_history"] = inputs["prior_history"]
        elif prior_history == "omit":
            pass
        else:
            kwargs["prior_history"] = prior_history
        return store_call(case_ids, "save", leaf, store.save_human_gate_decision_snapshots,
                          leaf, inputs["submission"], inputs["materials"],
                          inputs["expectations"], **kwargs)

    def verify_case(case_ids, leaf):
        return store_call(case_ids, "verify", leaf,
                          store.verify_human_gate_decision_snapshots, leaf)

    base1 = _base1_inputs()
    gate2 = _gate2_inputs()

    # ---------------------------------------------------------------- G1 正常与确定性
    controls = (("g1_gate1_approve", base1, "G1-01", _expected_record1(base1)),
                ("g1_gate1_hold", _decide(base1, "HOLD"), "G1-02",
                 _expected_record1(_decide(base1, "HOLD"))),
                ("g1_gate1_reject", _decide(base1, "REJECT"), "G1-03",
                 _expected_record1(_decide(base1, "REJECT"))),
                ("g1_gate1_blocked_hold", _blocked_hold(base1), "G1-04",
                 _expected_record1(_blocked_hold(base1))),
                ("g1_gate2_approve", gate2, "G1-05", None))
    for name, inputs, case_id, expected_record in controls:
        leaf = record_dir(name)
        save = save_case([case_id], leaf, inputs)
        _check(checks, failures, f"{case_id} 保存成功且恰八键",
               save["result"]["outcome"] == "returned"
               and len(save["result"]["keys"]) == 8
               and save["result"]["status"] == store.STORE_STATUS_STORED
               and save["result"]["scope"] == store.SCOPE, str(save["result"]))
        _check(checks, failures, f"{case_id} 三个 false 严格布尔",
               save["result"]["execution_allowed"] is False
               and save["result"]["workflow_connected"] is False
               and save["result"]["ai_enabled"] is False, str(save["result"]))
        _check(checks, failures, f"{case_id} 真实 P1 恰一次嵌套调用且已登记",
               save["nested_p1_calls_observed"] == 1
               and len(save["nested_core_call_ids"]) == 1,
               str(save["nested_core_call_ids"]))
        _check(checks, failures, f"{case_id} 进入核心的四个真实引用与指纹前后不变",
               all(entry["references_unchanged"] is True
                   and entry["input_fingerprints_before"] == entry["input_fingerprints_after"]
                   for entry in observer.records
                   if entry["core_call_id"] in save["nested_core_call_ids"]),
               "核心调用输入引用/指纹发生变化")
        files = sorted(entry.name for entry in leaf.iterdir())
        _check(checks, failures, f"{case_id} 叶目录恰六份固定文件",
               files == sorted(store.FIXED_FILES), str(files))
        stored = json.loads((leaf / "decision_result.json").read_text(encoding="utf-8"))
        nested = [entry for entry in observer.records
                  if entry["core_call_id"] in save["nested_core_call_ids"]]
        first_return = nested[0]["result"] if nested else None
        _check(checks, failures, f"{case_id} decision_result 与保存那一次真实核心返回严格相等",
               first_return is not None and _lf(stored) == _lf(first_return)
               and set(stored.keys()) == {"record", "record_fingerprint"},
               "decision_result 与该次真实 P1 返回不一致（未二次调用核心）")
        if expected_record is not None:
            _check(checks, failures, f"{case_id} 记录与冻结正文独立推导期望规范相等",
                   _lf(stored["record"]) == _lf(expected_record),
                   "记录与独立推导期望不一致")
        manifest = json.loads((leaf / "manifest.json").read_text(encoding="utf-8"))
        _check(checks, failures, f"{case_id} manifest 恰八键与常量",
               sorted(manifest.keys()) == sorted(store.MANIFEST_KEYS)
               and manifest["manifest_version"] == store.MANIFEST_VERSION
               and manifest["store_status"] == store.STORE_STATUS_STORED
               and manifest["scope"] == store.SCOPE, str(sorted(manifest.keys())))
        _check(checks, failures, f"{case_id} manifest 组件绑定恰四项且与实读一致",
               sorted(manifest["component_bindings"].keys())
               == sorted(store.COMPONENT_BINDING_KEYS)
               and manifest["component_bindings"]["core_file_sha256"]
               == FROZEN["P1_core"]
               and manifest["component_bindings"]["contract_file_sha256"]
               == FROZEN["contract"]
               and manifest["component_bindings"]["store_file_sha256"] == _sha_file(STORE_PATH),
               "组件绑定不一致")
        _check(checks, failures, f"{case_id} manifest 六项指纹与独立复算一致",
               manifest["fingerprints"]["record_fingerprint"] == _fp(stored["record"])
               and manifest["fingerprints"]["materials_snapshot_fingerprint"]
               == _fp(inputs["materials"])
               and manifest["fingerprints"]["materials_body_fingerprint"]
               == _fp({key: value for key, value in inputs["materials"].items()
                       if key != "materials_fingerprint"})
               and manifest["fingerprints"]["prior_history_fingerprint"]
               == _fp(inputs["prior_history"]), "指纹不一致")
        _check(checks, failures, f"{case_id} payloads 恰五项升序且 SHA 实读一致",
               [entry["relative"] for entry in manifest["payloads"]]
               == sorted(store.PAYLOAD_FILES, key=lambda item: item.encode("utf-8"))
               and all(entry["byte_size"] == (leaf / entry["relative"]).stat().st_size
                       and entry["file_sha256"] == _sha_file(leaf / entry["relative"])
                       for entry in manifest["payloads"]), "payloads 不一致")
        verify = verify_case([case_id], leaf)
        _check(checks, failures, f"{case_id} 核验成功且恰八键",
               verify["result"]["outcome"] == "returned"
               and verify["result"]["status"] == store.STORE_STATUS_VERIFIED
               and len(verify["result"]["keys"]) == 8, str(verify["result"]))
        _check(checks, failures, f"{case_id} 核验真实 P1 恰一次且已登记",
               verify["nested_p1_calls_observed"] == 1, str(verify["nested_core_call_ids"]))
        _check(checks, failures, f"{case_id} 保存/核验 manifest 文件 SHA 一致",
               verify["result"]["manifest_file_sha256"]
               == save["result"]["manifest_file_sha256"], "manifest SHA 不一致")

    first, second = record_dir("g1_determinism_a"), record_dir("g1_determinism_b")
    save_case(["G1-06"], first, base1)
    save_case(["G1-06"], second, base1)
    _check(checks, failures, "G1-06 同输入同组件字节在两新目录逐文件相同",
           all((first / name).read_bytes() == (second / name).read_bytes()
               for name in store.FIXED_FILES), "两目录字节不同")

    # ---------------------------------------------------------------- G2 前提与路径
    existing_snapshot = _dir_snapshot(record_dir("g1_gate1_approve"))
    again = save_case(["G2-01"], record_dir("g1_gate1_approve"), base1)
    _check(checks, failures, "G2-01 已有叶目录拒绝且不覆盖",
           again["result"]["outcome"] == "blocked"
           and _dir_snapshot(record_dir("g1_gate1_approve")) == existing_snapshot,
           str(again["result"]))
    empty_dir = record_dir("g2_empty_dir")
    empty_dir.mkdir()
    empty = save_case(["G2-02"], empty_dir, base1)
    _check(checks, failures, "G2-02 已有空目录拒绝且目录仍为空",
           empty["result"]["outcome"] == "blocked" and not any(empty_dir.iterdir()),
           str(empty["result"]))
    outside = save_case(["G2-03"], PROJECT_ROOT / "data" / "task022r1_out_of_bounds", base1)
    _check(checks, failures, "G2-03 越界路径拒绝",
           outside["result"]["outcome"] == "blocked"
           and outside["result"].get("field") == "out_dir", str(outside["result"]))
    root_itself = save_case(["G2-04"], RECORDS_ROOT, base1)
    _check(checks, failures, "G2-04 允许根自身拒绝",
           root_itself["result"]["outcome"] == "blocked", str(root_itself["result"]))
    blank_reason = _variant(base1, lambda target: target["submission"].__setitem__(
        "reason", "   "))
    blank = save_case(["G2-05"], record_dir("g2_blank_reason"), blank_reason)
    _check(checks, failures, "G2-05 空白 reason 由真实 P1 拒绝且不建叶目录",
           blank["result"]["outcome"] == "blocked"
           and blank["result"].get("field") == "submission.reason"
           and not record_dir("g2_blank_reason").exists(), str(blank["result"]))
    simulated = _variant(base1, lambda target: target["submission"]["actor"].__setitem__(
        "actor_kind", "SIMULATED_HUMAN"))
    sim = save_case(["G2-06"], record_dir("g2_simulated_actor"), simulated)
    _check(checks, failures, "G2-06 模拟身份由真实 P1 拒绝且不建叶目录",
           sim["result"]["outcome"] == "blocked"
           and sim["result"].get("field") == "submission.actor.actor_kind"
           and not record_dir("g2_simulated_actor").exists(), str(sim["result"]))
    blocked_approve = _blocked_hold(base1)
    blocked_approve["submission"]["decision"] = "APPROVE"
    approve = save_case(["G2-07"], record_dir("g2_blocked_approve"), blocked_approve)
    _check(checks, failures, "G2-07 BLOCKED+APPROVE 由真实 P1 拒绝且不建叶目录",
           approve["result"]["outcome"] == "blocked"
           and approve["result"].get("field") == "submission.decision"
           and not record_dir("g2_blocked_approve").exists(), str(approve["result"]))
    missing_history = save_case(["G2-08"], record_dir("g2_missing_history"), base1,
                                prior_history=None)
    _check(checks, failures, "G2-08 None 历史由真实 P1 拒绝（不默认空历史）",
           missing_history["result"]["outcome"] == "blocked"
           and missing_history["result"].get("field") == "prior_history"
           and missing_history["nested_p1_calls_observed"] == 1
           and not record_dir("g2_missing_history").exists(),
           str(missing_history["result"]))
    omitted = save_case(["G2-09"], record_dir("g2_omitted_history"), base1,
                        prior_history="omit")
    _check(checks, failures, "G2-09 缺省省略历史同样被真实 P1 拒绝",
           omitted["result"]["outcome"] == "blocked"
           and omitted["result"].get("field") == "prior_history", str(omitted["result"]))
    verify_outside = verify_case(["G2-10"], RECORDS_ROOT)
    _check(checks, failures, "G2-10 核验越界/根自身拒绝",
           verify_outside["result"]["outcome"] == "blocked", str(verify_outside["result"]))

    # ---------------------------------------------------------------- G3 恢复负向与只读
    source = record_dir("g1_gate1_approve")

    def g3_case(case_id, name, mutate, expect):
        target = _copy_record_dir(source, record_dir(name))
        mutate(target)
        before = _dir_snapshot(target)
        record = verify_case([case_id], target)
        after = _dir_snapshot(target)
        field = record["result"].get("field") or ""
        ok = (record["result"]["outcome"] == "blocked" and expect(field))
        _check(checks, failures, f"{case_id} 定位拒绝且核验前后目录不变",
               ok and before == after,
               f"outcome={record['result']} field={field!r} dir_changed={before != after}")
        return record

    g3_case("G3-01", "g3_01_payload_byte",
            lambda target: (target / "submission.json").write_bytes(
                (target / "submission.json").read_bytes() + b" "),
            lambda field: "submission.json" in field or "payloads" in field)
    g3_case("G3-02", "g3_02_manifest_sha_lf",
            lambda target: _bump_manifest(target, lambda manifest: manifest["payloads"][0]
                                          .__setitem__("file_sha256", H("a") + "\n")),
            lambda field: field.endswith("file_sha256"))
    g3_case("G3-03", "g3_03_byte_size_bool",
            lambda target: _bump_manifest(target, lambda manifest: manifest["payloads"][0]
                                          .__setitem__("byte_size", True)),
            lambda field: field.endswith("byte_size"))
    g3_case("G3-04", "g3_04_unknown_item",
            lambda target: _bump_manifest(target, lambda manifest: manifest.__setitem__(
                "extra", True)),
            lambda field: field == "manifest.extra")
    g3_case("G3-05", "g3_05_missing_payload",
            lambda target: _bump_manifest(target, lambda manifest: manifest.__setitem__(
                "payloads", manifest["payloads"][:-1])),
            lambda field: field == "manifest.payloads")
    g3_case("G3-06", "g3_06_duplicate_payload",
            lambda target: _bump_manifest(target, lambda manifest: manifest.__setitem__(
                "payloads", manifest["payloads"][:1] + manifest["payloads"][:1]
                + manifest["payloads"][2:])),
            lambda field: field.startswith("manifest.payloads"))
    g3_case("G3-07", "g3_07_out_of_range_relative",
            lambda target: _bump_manifest(target, lambda manifest: manifest["payloads"][0]
                                          .__setitem__("relative", "../escape.json")),
            lambda field: field.endswith("relative"))
    g3_case("G3-08", "g3_08_failure_present",
            lambda target: (target / "failure.json").write_bytes(
                _lf({"failure_version": store.FAILURE_VERSION, "stage": "fixture",
                     "classification": "Blocked", "field": None, "reason": "FIXTURE",
                     "cause_chain": []})),
            lambda field: field == "failure.json")
    g3_case("G3-09", "g3_09_cross_file_batch", _mutate_submission_batch,
            lambda field: field == "submission.json.batch_id")
    g3_case("G3-10", "g3_10_inner_binding_synced_outer", _mutate_inner_binding,
            lambda field: field == "submission.json.request_binding.materials_binding")

    # R1 §2.1：错类型对象必须先被检查（不泄漏原生 AttributeError/TypeError）
    def type_case(case_id, name, file_name, payload_value):
        def mutate(target):
            (target / file_name).write_bytes(_lf(payload_value))
            _sync_manifest_entry(target, file_name)
        return g3_case(case_id, name, mutate, lambda field: field == file_name)

    type_case("G3-11", "g3_11_decision_result_list", "decision_result.json", [])
    type_case("G3-12", "g3_12_decision_result_null", "decision_result.json", None)
    type_case("G3-13", "g3_13_decision_result_number", "decision_result.json", 7)
    type_case("G3-14", "g3_14_materials_list", "materials.json", [])

    # ---------------------------------------------------------------- G4 writer / 晚变更 / I/O 映射
    sentinel = type("StoreInjectionSentinel", (RuntimeError,), {})
    original_os_write = os.write
    state = {"hits": 0}

    def partial_write(fd, data):
        if state["hits"] == 0 and isinstance(data, (bytes, bytearray, memoryview)):
            state["hits"] += 1
            original_os_write(fd, bytes(data)[:len(bytes(data)) // 2])
            raise OSError("injected partial write failure")
        return original_os_write(fd, data)

    os.write = partial_write
    partial_leaf = record_dir("g4_01_partial_write")
    try:
        partial = save_case(["G4-01"], partial_leaf, base1)
    finally:
        os.write = original_os_write
    failure_file = partial_leaf / store.FAILURE_FILE
    _check(checks, failures, "G4-01 半写 OSError → Error + 原因链 + 现场",
           partial["result"]["outcome"] == "error" and state["hits"] == 1
           and any("OSError" in item["type"]
                   for item in (partial["exception"] or {}).get("cause_chain", []))
           and failure_file.is_file(), str(partial["result"]))
    if failure_file.is_file():
        payload = json.loads(failure_file.read_text(encoding="utf-8"))
        _check(checks, failures, "G4-01 failure.json 版本/分类/阶段/链完整",
               payload["failure_version"] == store.FAILURE_VERSION
               and payload["classification"] == "Error" and payload["stage"]
               and any("OSError" in item["type"] for item in payload["cause_chain"]),
               json.dumps(payload, ensure_ascii=False)[:200])
    _check(checks, failures, "G4-01 既有记录未被影响",
           _dir_snapshot(record_dir("g1_gate1_approve")) == existing_snapshot,
           "既有记录发生变化")
    rejected = verify_case(["G4-01b"], partial_leaf)
    _check(checks, failures, "G4-01 含 failure 的记录核验拒绝",
           rejected["result"]["outcome"] == "blocked"
           and rejected["result"].get("field") == "failure.json", str(rejected["result"]))

    # R1 §2.3：manifest 写入读回后 sentinel —— API 与 failure.json 都须保留 RuntimeError 链
    original_hook = store._hook_after_manifest_readback
    sentinel_leaf = record_dir("g4_02_manifest_sentinel")
    store._hook_after_manifest_readback = lambda: (_ for _ in ()).throw(
        sentinel("injected post-manifest sentinel"))
    try:
        after_manifest = save_case(["G4-02"], sentinel_leaf, base1)
    finally:
        store._hook_after_manifest_readback = original_hook
    sentinel_failure = sentinel_leaf / store.FAILURE_FILE
    sentinel_payload = (json.loads(sentinel_failure.read_text(encoding="utf-8"))
                        if sentinel_failure.is_file() else {})
    _check(checks, failures, "G4-02 sentinel → API Error 保留 RuntimeError 链",
           after_manifest["result"]["outcome"] == "error"
           and any(item["type"] == "StoreInjectionSentinel"
                   for item in (after_manifest["exception"] or {}).get("cause_chain", [])),
           str(after_manifest["result"]))
    _check(checks, failures, "G4-02 failure.json 原因链与 API 一致（不含 sentinel 丢失）",
           any(item["type"] == "StoreInjectionSentinel"
               for item in sentinel_payload.get("cause_chain", [])),
           json.dumps(sentinel_payload.get("cause_chain"), ensure_ascii=False)[:200])
    sentinel_verify = verify_case(["G4-02b"], sentinel_leaf)
    _check(checks, failures, "G4-02 sentinel 现场核验拒绝",
           sentinel_verify["result"]["outcome"] == "blocked", str(sentinel_verify["result"]))

    # R1 §4.2：先无注入观察次序，再在**最后必要消费**（含末次组件绑定读取）之后单次改 LF
    order_probe_leaf = record_dir("g4_03_order_probe")
    guard.arm()
    try:
        order_probe = registry.call(["G4-03-probe"], "save", order_probe_leaf,
                                    store.save_human_gate_decision_snapshots,
                                    order_probe_leaf, base1["submission"], base1["materials"],
                                    base1["expectations"],
                                    prior_history=base1["prior_history"], guard=guard)
    finally:
        guard.disarm()
    probe_io = [entry for entry in order_probe["io_ops_in_call"]
                if entry["op"] in ("io.open", "open", "os.open", "os.write")]
    _check(checks, failures, "G4-03 先观察真实次序：保存含真实读取与写入事件",
           any(entry.get("access") == "write" for entry in probe_io)
           and any(entry.get("access") == "read" for entry in probe_io),
           f"op 数={len(probe_io)}")
    late_leaf = record_dir("g4_03_save_late_change")
    state["hits"] = 0
    guard.arm()
    try:
        guard.mark("save-start")
        store._hook_after_last_consumption = lambda stage: (
            guard.mark(f"inject:append-lf:submission.json:after-last-consumption:{stage}"),
            (late_leaf / "submission.json").write_bytes(
                (late_leaf / "submission.json").read_bytes() + b"\n"),
            state.__setitem__("hits", state["hits"] + 1))
        try:
            late_save = registry.call(["G4-03"], "save", late_leaf,
                                      store.save_human_gate_decision_snapshots,
                                      late_leaf, base1["submission"], base1["materials"],
                                      base1["expectations"],
                                      prior_history=base1["prior_history"],
                                      guard=guard)
        finally:
            store._hook_after_last_consumption = _store_hook_default
    finally:
        guard.disarm()
    _check(checks, failures, "G4-03 保存末次消费后追加 LF → 本次 Blocked 且指出文件",
           late_save["result"]["outcome"] == "blocked"
           and late_save["result"].get("field") == "submission.json"
           and state["hits"] == 1, str(late_save["result"]))

    verify_late_leaf = _copy_record_dir(source, record_dir("g4_04_verify_late_change"))
    state["hits"] = 0
    guard.arm()
    try:
        store._hook_after_last_consumption = lambda stage: (
            guard.mark(f"inject:append-lf:materials.json:after-last-consumption:{stage}"),
            (verify_late_leaf / "materials.json").write_bytes(
                (verify_late_leaf / "materials.json").read_bytes() + b"\n"),
            state.__setitem__("hits", state["hits"] + 1))
        try:
            late_verify = registry.call(["G4-04"], "verify", verify_late_leaf,
                                        store.verify_human_gate_decision_snapshots,
                                        verify_late_leaf, guard=guard)
        finally:
            store._hook_after_last_consumption = _store_hook_default
    finally:
        guard.disarm()
    _check(checks, failures, "G4-04 核验复算后追加 LF → 本次 Blocked 且不写 failure",
           late_verify["result"]["outcome"] == "blocked"
           and late_verify["result"].get("field") == "materials.json"
           and state["hits"] == 1
           and not (verify_late_leaf / store.FAILURE_FILE).exists(),
           str(late_verify["result"]))

    # R1 §2.2：末次同目标读取抛受控 OSError → StoreError(stage, reason) 且原因链齐备
    mapped_leaf = _copy_record_dir(source, record_dir("g4_05_final_read_oserror"))
    original_read_bytes = store._read_bytes
    seen_paths: dict = {}
    state["hits"] = 0

    def read_bytes_with_final_injection(path):
        key = str(path)
        seen_paths[key] = seen_paths.get(key, 0) + 1
        if seen_paths[key] == 2 and state["hits"] == 0:
            state["hits"] += 1
            raise OSError("injected final-read failure")
        return original_read_bytes(path)

    store._read_bytes = read_bytes_with_final_injection
    try:
        mapped = verify_case(["G4-05"], mapped_leaf)
    finally:
        store._read_bytes = original_read_bytes
    _check(checks, failures, "G4-05 末次读取 OSError → StoreError + OSError 原因链且不写 failure",
           mapped["result"]["outcome"] == "error" and state["hits"] == 1
           and mapped["result"].get("stage") == "final_read"
           and any("OSError" in item["type"]
                   for item in (mapped["exception"] or {}).get("cause_chain", []))
           and not (mapped_leaf / store.FAILURE_FILE).exists(),
           str(mapped["result"]))

    # R1 §3：真实 Windows junction 路径反例
    junction = {"attempted": True}
    target_dir = record_dir("junction_target")
    normal_leaf = target_dir / "normal_record"
    save_norm = store_call(["J-01"], "save", normal_leaf,
                           store.save_human_gate_decision_snapshots, normal_leaf,
                           base1["submission"], base1["materials"], base1["expectations"],
                           prior_history=base1["prior_history"])
    alias = record_dir("junction_alias")
    junction.update(_create_junction(alias, target_dir))
    junction["alias_lstat_reparse"] = _is_reparse(alias)
    junction["alias_resolves_to_target"] = (
        alias.resolve() == target_dir.resolve() if alias.exists() else None)
    if not junction.get("created"):
        junction["executed"] = False
        junction["note"] = "执行环境未允许建立真实 junction，如实报告未执行（不标通过）"
        _check(checks, failures, "J-01 正常直接路径保存成功（junction 未建立时的对照）",
               save_norm["result"]["outcome"] == "returned", str(save_norm["result"]))
    else:
        junction["executed"] = True
        target_before = _dir_snapshot(target_dir)
        alias_new = alias / "new_record"
        junction_save = store_call(["J-02"], "save", alias_new,
                                   store.save_human_gate_decision_snapshots, alias_new,
                                   base1["submission"], base1["materials"],
                                   base1["expectations"],
                                   prior_history=base1["prior_history"])
        junction_verify = store_call(["J-03"], "verify", alias / "normal_record",
                                     store.verify_human_gate_decision_snapshots,
                                     alias / "normal_record")
        target_after = _dir_snapshot(target_dir)
        junction["save_field"] = junction_save["result"].get("field")
        junction["save_p1_calls"] = junction_save["nested_p1_calls_observed"]
        junction["verify_field"] = junction_verify["result"].get("field")
        junction["target_unchanged"] = target_before == target_after
        _check(checks, failures, "J-02 经真实 junction 保存被拒（写入前 Blocked、真实 P1=0）",
               junction_save["result"]["outcome"] == "blocked"
               and junction_save["result"].get("field") == "out_dir"
               and junction_save["nested_p1_calls_observed"] == 0
               and not alias_new.exists(), str(junction_save["result"]))
        _check(checks, failures, "J-03 经真实 junction 核验被拒且目录字节不变",
               junction_verify["result"]["outcome"] == "blocked"
               and junction["target_unchanged"], str(junction_verify["result"]))

    # R2 §2：**首次加载** P1 的运行/I-O 错误必须映射为 StoreError（真实 spec + loader 注入）
    def with_loader_injection(action):
        original_spec_from = importlib.util.spec_from_file_location
        original_module = sys.modules.pop("build_demo_human_gate_decision", None)
        original_core = store._CORE
        store._CORE = None
        real_spec = original_spec_from("build_demo_human_gate_decision", P1_CORE_PATH)
        state = {"hits": 0}
        real_exec = real_spec.loader.exec_module

        def exec_with_injection(module):
            if state["hits"] == 0:
                state["hits"] += 1
                raise OSError("injected loader failure")
            return real_exec(module)

        real_spec.loader.exec_module = exec_with_injection
        importlib.util.spec_from_file_location = lambda name, path: real_spec
        try:
            record = action()
        finally:
            importlib.util.spec_from_file_location = original_spec_from
            sys.modules.pop("build_demo_human_gate_decision", None)
            store._CORE = None
            if original_module is not None:
                sys.modules["build_demo_human_gate_decision"] = original_module
                store._CORE = original_core
        return record, state["hits"]

    core_entries_before = len(observer.records)
    load_leaf = record_dir("g4_06_p1_load_save")
    load_save, load_hits = with_loader_injection(
        lambda: save_case(["G4-06"], load_leaf, base1))
    _check(checks, failures, "G4-06 首次加载 OSError → save StoreError(p1_load)+OSError 链",
           load_save["result"]["outcome"] == "error"
           and load_save["result"].get("stage") == "p1_load"
           and load_hits == 1
           and any("OSError" in item["type"]
                   for item in (load_save["exception"] or {}).get("cause_chain", []))
           and not load_leaf.exists()
           and len(observer.records) == core_entries_before, str(load_save["result"]))
    load_verify, load_hits_v = with_loader_injection(
        lambda: verify_case(["G4-07"], record_dir("g1_gate1_approve")))
    _check(checks, failures, "G4-07 首次加载 OSError → verify StoreError(p1_load)+OSError 链",
           load_verify["result"]["outcome"] == "error"
           and load_verify["result"].get("stage") == "p1_load"
           and load_hits_v == 1
           and any("OSError" in item["type"]
                   for item in (load_verify["exception"] or {}).get("cause_chain", []))
           and len(observer.records) == core_entries_before
           and not (record_dir("g1_gate1_approve") / store.FAILURE_FILE).exists(),
           str(load_verify["result"]))
    control_leaf = record_dir("g4_08_after_load_recovery")
    control_save = save_case(["G4-08"], control_leaf, base1)
    control_verify = verify_case(["G4-08"], control_leaf)
    _check(checks, failures, "G4-08 撤销注入后新记录仍可保存/核验（未复用半执行模块）",
           control_save["result"]["outcome"] == "returned"
           and control_verify["result"]["outcome"] == "returned"
           and control_save["nested_p1_calls_observed"] == 1,
           f"{control_save['result']} / {control_verify['result']}")

    # ---------------------------------------------------------------- G5 边界与观察
    read_events = [entry for entry in guard.log if entry.get("access") == "read"]
    write_events = [entry for entry in guard.log if entry.get("access") == "write"]
    core_registry = _core_registry(observer)
    pending_audit = _core_audit(core_registry, registry.records)
    _check(checks, failures, "R2-01 待写缓冲的完整 entries 审核通过（entries↔ID↔total↔入口↔API 嵌套）",
           pending_audit["ok"], json.dumps(pending_audit, ensure_ascii=False)[:400])
    verify_records = [record for record in registry.records if record["kind"] == "verify"]
    scenes = [record["inputs"].get("initial_input_scene") for record in verify_records]
    _check(checks, failures, "R2-02 verify 初始输入现场已登记（存在目录含文件集合与大小/SHA）",
           all(scene and scene.get("status") in ("observed", "not_available")
               for scene in scenes)
           and any(scene and scene.get("status") == "observed"
                   and scene.get("files") for scene in scenes)
           and all(scene and (scene.get("status") == "observed" or scene.get("reason"))
                   for scene in scenes),
           json.dumps([scene.get("status") if scene else None for scene in scenes],
                      ensure_ascii=False)[:200])
    nested_entries = [entry for entry in observer.records if entry["kind"] == "nested"]
    _check(checks, failures, "R2-03 三时点指纹来自同一引用且可独立复算",
           nested_entries
           and all(entry.get("input_fingerprints_at_api_finalize")
                   == entry["input_fingerprints_before"]
                   == entry["input_fingerprints_after"]
                   and entry.get("third_timepoint_matches") is True
                   for entry in nested_entries),
           f"nested={len(nested_entries)} finalize_missing="
           f"{sum(1 for entry in nested_entries if entry.get('input_fingerprints_at_api_finalize') is None)}")
    _check(checks, failures, "G5-01 三类调用分列并闭合（嵌套+直接=入口观察）",
           core_registry["closure_ok"] is True
           and core_registry["by_kind"].get("nested", 0)
           + core_registry["by_kind"].get("direct", 0) == observer.entry_count,
           json.dumps({"by_kind": core_registry["by_kind"],
                       "entry": observer.entry_count}, ensure_ascii=False))
    _check(checks, failures, "G5-02 每次核心调用均含完整输入快照与返回/异常",
           all(set(entry["inputs"].keys()) == {"submission", "materials", "expectations",
                                               "prior_history"}
               and (entry["result"] is not None or entry["exception"] is not None)
               for entry in observer.records),
           "存在缺少完整输入或返回的核心登记")
    success_saves = [record for record in registry.records if record["kind"] == "save"
                     and record["result"]["outcome"] == "returned"]
    success_verifies = [record for record in registry.records if record["kind"] == "verify"
                        and record["result"]["outcome"] == "returned"]
    _check(checks, failures, "G5-03 正常保存/核验各恰一次嵌套核心调用",
           all(record["nested_p1_calls_observed"] == 1 for record in success_saves)
           and all(record["nested_p1_calls_observed"] == 1 for record in success_verifies),
           "存在非 1 的嵌套核心调用")
    early = [record for record in registry.records
             if record["case_ids"][0] in ("G2-01", "G2-02", "G2-03", "G2-04", "J-02")]
    _check(checks, failures, "G5-04 提前路径拒绝时真实核心调用为 0",
           all(record["nested_p1_calls_observed"] == 0 for record in early),
           str([(record["case_ids"], record["nested_p1_calls_observed"])
                for record in early]))
    _check(checks, failures, "G5-05 守卫内 socket/子进程命中 0", guard.forbidden == 0,
           str(guard.forbidden))
    forbidden_modules = [name for name in sys.modules
                         if any(token in name for token in (
                             "run_demo_workflow", "control_demo_workflow",
                             "build_demo_fact_packet", "build_demo_initial_judgment",
                             "screen_demo", "store_demo_sqlite", "prepare_demo_gate2",
                             "record_demo_gate2_decision", "export_demo_review_bundle"))]
    _check(checks, failures, "G5-06 未导入宿主/控制器/业务核心", not forbidden_modules,
           str(forbidden_modules))
    import ast as _ast
    imported = set()
    for node in _ast.walk(_ast.parse(STORE_PATH.read_text(encoding="utf-8"))):
        if isinstance(node, _ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, _ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    _check(checks, failures, "G5-07 存储模块只导入标准库",
           not (imported - {"__future__", "copy", "hashlib", "importlib", "json", "os",
                            "stat", "sys", "pathlib"}), f"实际导入={sorted(imported)}")
    allowed_prefixes = (str(round_root), str(RECORDS_ROOT))
    allowed_component_files = {str(P1_CORE_PATH), str(STORE_PATH), str(CONTRACT_PATH),
                               str(EFFECTIVE_RECORD_PATH)}
    read_paths = {entry["arg"] for entry in read_events if entry["arg"]}
    outside_reads = sorted(path for path in read_paths
                           if not path.startswith(allowed_prefixes)
                           and path not in allowed_component_files)
    _check(checks, failures, "G5-08 真实读取通道仅覆盖本轮记录目录与四项固定组件",
           read_events and not outside_reads, f"reads={len(read_events)} outside={outside_reads[:5]}")
    _check(checks, failures, "G5-09 记录 boundaries 原样且外层不放行",
           all(record["result"].get("execution_allowed") is False
               for record in registry.records if record["result"]["outcome"] == "returned"),
           "存在 execution_allowed 非 false 的返回")
    _check(checks, failures, "G5-10 夹具标识未进入 P1 封闭 schema",
           all(FIXTURE_TAG not in json.dumps(inputs, ensure_ascii=False)
               for inputs in (base1, gate2)), "夹具标识出现在 P1 输入中")
    frozen_identities = {
        "P1_core": {"path": "scripts/build_demo_human_gate_decision.py",
                    "sha256": _sha_file(P1_CORE_PATH), "expected": FROZEN["P1_core"]},
        "store": {"path": "scripts/store_demo_human_gate_decision.py",
                  "sha256": _sha_file(STORE_PATH), "expected": None},
        "contract": {"path": "docs/AUDIT_CONTRACT.md", "sha256": _sha_file(CONTRACT_PATH),
                     "expected": FROZEN["contract"]},
        "contract_effective_record": {
            "path": "docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md",
            "sha256": _sha_file(EFFECTIVE_RECORD_PATH),
            "expected": FROZEN["contract_effective_record"]},
        "protocol": {"path": "docs/proposals/HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md",
                     "sha256": _sha_file(PROTOCOL_PATH), "expected": FROZEN["protocol"]},
        "cases": {"path": "docs/proposals/HUMAN_GATE_DECISION_CASES_V1_DRAFT.md",
                  "sha256": _sha_file(CASES_DOC), "expected": FROZEN["cases"]},
        "host": {"path": "scripts/run_demo_workflow.py", "sha256": _sha_file(HOST_PATH),
                 "expected": FROZEN["host"]},
        "controller": {"path": "scripts/control_demo_workflow.py",
                       "sha256": _sha_file(CONTROLLER_PATH), "expected": FROZEN["controller"]},
    }
    _check(checks, failures, "G5-11 测试/保护层独立核对全部冻结身份（含宿主/控制器）",
           all(entry["expected"] is None or entry["sha256"] == entry["expected"]
               for entry in frozen_identities.values()),
           json.dumps({key: value["sha256"][:12] for key, value in frozen_identities.items()},
                      ensure_ascii=False))

    # ---------------------------------------------------------------- G6 证据收尾
    fixture_registration = {
        "fixture_tag": FIXTURE_TAG,
        "declaration": ("全部合成审批输入均为协议测试夹具，不是主理人真实提交，"
                        "不产生任何批次批准效力"),
        "fixture_tag_inside_p1_schema": False,
        "record_round_root": round_root.relative_to(PROJECT_ROOT).as_posix(),
    }
    inventory = sorted(entry.relative_to(PROJECT_ROOT).as_posix()
                       for entry in round_root.rglob("*") if entry.is_file())
    store_inventory = {"round_root": round_root.relative_to(PROJECT_ROOT).as_posix(),
                       "file_count": len(inventory), "files": inventory,
                       "junction": junction}
    read_observation = {
        "read_events": len(read_events), "write_events": len(write_events),
        "forbidden_hits": guard.forbidden,
        "read_paths": sorted(read_paths),
        "outside_read_paths": outside_reads,
        "note": "覆盖真实 io.open/Path.read_bytes 读取通道；读/写分列",
    }
    counts = {
        "store_api_calls": len(registry.records),
        "store_api_by_outcome": _outcome_counts(registry.records),
        "store_api_by_kind": _kind_counts(registry.records),
        "nested_core_calls": core_registry["by_kind"].get("nested", 0),
        "direct_core_calls": core_registry["by_kind"].get("direct", 0),
        "total_core_entries": core_registry["total_core_entries"],
        "core_entry_frame_observation": observer.entry_count,
        "core_closure_ok": core_registry["closure_ok"],
        "guard_forbidden_hits": guard.forbidden,
        "read_events": len(read_events),
        "write_events": len(write_events),
        "not_executed": {"host_or_controller": None, "business_core": None,
                         "gate_adapter": None, "ai_or_final_judgment": None,
                         "real_initial_judgment": None, "subprocess_internal_counts": None,
                         "junction_case": None if junction.get("executed") else "not_executed"},
    }
    summary = {
        "task": "TASK-022-R4",
        "suite": "P2-S1 快照保存/只读核验：异常、链接、调用/读取观察与真实观察内容绑定（G1—G6）",
        "status": "PASS" if not failures else "FAIL",
        "checks_total": len(checks), "checks_failed": len(failures),
        "store_api_calls": len(registry.records),
        "nested_core_calls": counts["nested_core_calls"],
        "direct_core_calls": counts["direct_core_calls"],
        "core_entry_frame_observation": observer.entry_count,
        "core_closure_ok": core_registry["closure_ok"],
        "read_events": len(read_events), "write_events": len(write_events),
        "junction_executed": junction.get("executed"),
        "frozen_identities": frozen_identities,
        "boundaries": {"execution_allowed": False, "workflow_connected": False,
                       "ai_enabled": False, "real_gate_approval": None,
                       "real_initial_judgment": None, "workflow_0009": None},
        "not_executed": counts["not_executed"],
    }
    observer.uninstall()

    # R3 §2.1：全部 API 与真实核心观察定稿后、任何终审读取之前冻结独立深拷贝预期
    call_registry_payload = {
        "authoritative": True, "total_store_api_calls": len(registry.records),
        "call_ids": [record["call_id"] for record in registry.records],
        "by_kind": _kind_counts(registry.records),
        "by_outcome": _outcome_counts(registry.records),
        "note": "公开存储 API 次数与嵌套真实核心次数分列，不要求相等",
    }
    expectation = _observation_expectation(core_registry, registry.records,
                                           call_registry_payload)
    _check(checks, failures, "R3-01 定稿真实观察预期已冻结（深拷贝、独立于候选磁盘）",
           expectation["core_call_registry"] == core_registry
           and expectation["api_records"] == registry.records
           and expectation["core_call_registry"] is not core_registry
           and expectation["api_records"] is not registry.records
           and expectation["counts"]["core_entries"] == len(core_registry["entries"]),
           json.dumps(expectation["counts"], ensure_ascii=False))

    ledger_path = out_dir / "evidence_ledger.json"
    attempts = 0
    validation = {"missing": [], "unregistered": []}
    entries = {}
    while attempts < 3:
        attempts += 1
        _write_json(out_dir / "api_records.json", registry.records)
        _write_json(out_dir / "core_call_registry.json", core_registry)
        _write_json(out_dir / "call_registry.json", call_registry_payload)
        _write_json(out_dir / "counts.json", counts)
        _write_json(out_dir / "fixture_registration.json", fixture_registration)
        _write_json(out_dir / "store_inventory.json", store_inventory)
        _write_json(out_dir / "read_observation.json", read_observation)
        _write_json(out_dir / "test_frozen_identities.json", frozen_identities)
        _write_json(out_dir / "io_observations.json",
                    {"total_ops": len(guard.log), "ops": guard.log})
        _write_json(out_dir / "summary.json", summary)
        _write_json(out_dir / "checks.json", checks)
        _write_json(out_dir / "failures.json", failures)
        isolation = {"content_isolation": _content_isolation(
                         expectation, core_registry, registry.records, call_registry_payload),
                     "core_isolation": _core_isolation(core_registry, registry.records),
                     "api_isolation": _api_isolation(registry.records),
                     "file_ledger_isolation": _file_ledger_isolation(
                         out_dir, _ledger_from_disk(
                             out_dir, [name for name in PAYLOADS
                                       if name != "isolation_self_tests.json"])["entries"])}
        _write_json(out_dir / "isolation_self_tests.json", isolation)
        entries = _ledger_from_disk(out_dir, PAYLOADS)["entries"]
        validation = _ledger_validate(out_dir, entries)
        _check(checks, failures, "G6-01 台账逐项实读与磁盘一致",
               not validation["missing"] and not validation["unregistered"], str(validation))
        _check(checks, failures,
               "G6-02 删一条核心登记（ID 或完整 entry）由真实 audit 失败、原件通过",
               isolation["core_isolation"]["id_only_copy_fails"] is True
               and isolation["core_isolation"]["entry_removed_copy_fails"] is True
               and isolation["core_isolation"]["duplicate_entry_fails"] is True
               and isolation["core_isolation"]["hollow_entry_fails"] is True
               and isolation["core_isolation"]["original_passes"] is True,
               json.dumps(isolation["core_isolation"], ensure_ascii=False)[:400])
        _check(checks, failures, "G6-03 删一条存储 API 登记由真实 audit 失败、原件通过",
               isolation["api_isolation"]["audit_copy_fails"] is True
               and isolation["api_isolation"]["original_passes"] is True,
               json.dumps(isolation["api_isolation"], ensure_ascii=False)[:200])
        _check(checks, failures,
               "R4-01 canonical 主判据：False→0 与 整数0→浮点0.0 规范字节不同即拒绝",
               isolation["content_isolation"]["bool_to_int_rejected"] is True
               and isolation["content_isolation"]["int_to_float_rejected"] is True
               and isolation["content_isolation"]["bool_to_int_equal_flag"] is False
               and isolation["content_isolation"]["int_to_float_equal_flag"] is False
               and isolation["content_isolation"]["key_order_only_change_accepted"] is True
               and isolation["content_isolation"]["python_equal_would_miss"] is True
               and bool(isolation["content_isolation"]["bool_to_int_located"])
               and bool(isolation["content_isolation"]["int_to_float_located"]),
               json.dumps({key: isolation["content_isolation"][key] for key in (
                   "bool_to_int_located", "int_to_float_located",
                   "key_order_only_change_accepted", "python_equal_would_miss")},
                   ensure_ascii=False)[:400])
        _check(checks, failures,
               "R4-03 内容/类型隔离：{} 与合法形状自洽替换、False→0、整数→浮点均拒绝；仅键顺序不同仍通过",
               isolation["content_isolation"]["original_content_compare_ok"] is True
               and isolation["content_isolation"]["empty_result_rejected"] is True
               and isolation["content_isolation"]["self_consistent_reason_rejected"] is True
               and isolation["content_isolation"]["input_change_rejected"] is True
               and isolation["content_isolation"]["bool_to_int_rejected"] is True
               and isolation["content_isolation"]["bool_to_int_equal_flag"] is False
               and isolation["content_isolation"]["int_to_float_rejected"] is True
               and isolation["content_isolation"]["int_to_float_equal_flag"] is False
               and isolation["content_isolation"]["key_order_only_change_accepted"] is True
               and isolation["content_isolation"]["python_equal_would_miss"] is True
               and any(isolation["content_isolation"]["empty_result_located"].values()),
               json.dumps(isolation["content_isolation"], ensure_ascii=False)[:400])
        _check(checks, failures, "G6-04 文件台账隔离由真实 audit 判定",
               isolation["file_ledger_isolation"]["audit_copy_fails"] is True
               and isolation["file_ledger_isolation"]["original_passes"] is True,
               json.dumps(isolation["file_ledger_isolation"], ensure_ascii=False)[:200])
        if not validation["missing"] and not validation["unregistered"]:
            break
        failures.append({"name": "最终台账审核发现 missing/unregistered",
                         "detail": json.dumps(validation, ensure_ascii=False)})
        summary["status"] = "FAIL"
        summary["checks_failed"] = len(failures)
    # 终审（有界两轮）：**真实磁盘读回**（同一缓冲取对象与文件 SHA）→ 完整 entries 审核
    # → 与本次终审读数比较的字节漂移确认；台账期望绑定通过漂移确认的那次读数。
    core_disk_audit, api_disk_audit, drift = None, None, []
    audited = None
    audit_passes = 0
    while audit_passes < 2:
        audit_passes += 1
        summary["checks_total"] = len(checks)
        summary["checks_failed"] = len(failures)
        summary["status"] = "PASS" if not failures else "FAIL"
        _write_json(out_dir / "checks.json", checks)
        _write_json(out_dir / "failures.json", failures)
        _write_json(out_dir / "summary.json", summary)
        audited = _audited_read(out_dir, PAYLOADS)
        # R3 §2.2：同一缓冲取对象与 SHA，先做**完整内容比较**，再应用既有关系审核
        content = _content_compare(expectation,
                                   audited["core_call_registry.json"]["parsed"],
                                   audited["api_records.json"]["parsed"],
                                   audited["call_registry.json"]["parsed"])
        core_disk_audit = _core_audit_from_disk(out_dir, phase="final")
        api_disk_audit = _api_audit_from_audited(audited)
        drift = []
        for name in PAYLOADS:
            try:
                data = (out_dir / name).read_bytes()
            except OSError as exc:
                drift.append({"name": name, "error": str(exc)})
                continue
            if len(data) != audited[name]["bytes"] or _sha_bytes(data) != audited[name]["sha256"]:
                drift.append({"name": name, "bytes_now": len(data),
                              "sha256_now": _sha_bytes(data),
                              "bytes_audited": audited[name]["bytes"],
                              "sha256_audited": audited[name]["sha256"]})
        if audit_passes == 1:
            _check(checks, failures,
                   "R3-02 终审缓冲的完整对象与定稿真实观察一致（core/API/权威登记）",
                   content["ok"], json.dumps(content, ensure_ascii=False)[:600])
            _check(checks, failures,
                   "G6-05 核心登记完整 entries↔ID↔声明 total↔入口观察↔API 嵌套一致",
                   core_disk_audit["ok"],
                   json.dumps(core_disk_audit, ensure_ascii=False)[:400])
            _check(checks, failures, "G6-06 磁盘读回：存储 API 登记↔记录双向一致",
                   api_disk_audit["ok"], json.dumps(api_disk_audit, ensure_ascii=False)[:300])
            _check(checks, failures,
                   "G6-07 终审后字节漂移为 0（期望绑定终审读数，不重新采集）",
                   not drift, json.dumps(drift, ensure_ascii=False)[:400])
            if content["ok"] and core_disk_audit["ok"] and api_disk_audit["ok"] and not drift:
                continue
        if content["ok"] and core_disk_audit["ok"] and api_disk_audit["ok"] and not drift:
            break
        break
    audit_failed = (not content["ok"] or not core_disk_audit["ok"]
                    or not api_disk_audit["ok"] or bool(drift))
    ledger_from_audit = {name: {"exists": True, "bytes": audited[name]["bytes"],
                                "sha256": audited[name]["sha256"]} for name in PAYLOADS}
    if audit_failed:
        failures.append({"name": "终审内容/核心/磁盘审核失败（终审失败支配结论）",
                         "detail": json.dumps({"content": content, "core": core_disk_audit,
                                               "api": api_disk_audit, "drift": drift},
                                              ensure_ascii=False)[:1500]})
        summary["checks_total"] = len(checks)
        summary["checks_failed"] = len(failures)
        summary["status"] = "FAIL"
        summary["final_audit"] = {"content_compare_ok": content["ok"],
                                  "core_audit_ok": core_disk_audit["ok"],
                                  "api_audit_ok": api_disk_audit["ok"],
                                  "drift": drift, "dominates_exit_code": True}
        _write_json(out_dir / "checks.json", checks)
        _write_json(out_dir / "failures.json", failures)
        _write_json(out_dir / "summary.json", summary)
        _write_json(out_dir / "final_audit_diagnostic.json", {
            "detected": {"content_compare": content, "core_audit": core_disk_audit,
                         "api_audit": api_disk_audit, "byte_drift": drift},
            "ledger_entries_used": ledger_from_audit,
            "audit_failed": True, "dominates_exit_code": True,
            "post_audit_writes": ["checks.json", "failures.json", "summary.json",
                                  "final_audit_diagnostic.json"],
            "note": ("终审为真实磁盘读回并审核完整 entries；检测到问题即按失败结论更新并返回非零，"
                     "不重建台账、不以变更后的文件重新采集期望"),
        })
        _write_json(ledger_path, {"entries": ledger_from_audit,
                                  "entry_count": len(ledger_from_audit),
                                  "covered_payloads": list(PAYLOADS),
                                  "validated": {"missing": [], "unregistered": []},
                                  "final_audit_failed": True,
                                  "final_audit": {"content_compare": content,
                                                  "core_audit": core_disk_audit,
                                                  "api_audit": api_disk_audit, "drift": drift}})
        print(f"TASK-022-R4 测试组：{len(checks)} 项检查，{len(failures)} 项失败；"
              f"存储 API {len(registry.records)} 次、嵌套核心 {counts['nested_core_calls']}、"
              f"直接核心 {counts['direct_core_calls']}、入口观察 {observer.entry_count}")
        print(f"  终审失败：content_ok={content['ok']} core_audit_ok={core_disk_audit['ok']} "
              f"api_audit_ok={api_disk_audit['ok']} drift={len(drift)}")
        for item in failures[:10]:
            print(f"  - {item['name']}: {item['detail'][:200]}")
        return 1
    _write_json(ledger_path, {
        "entries": ledger_from_audit, "entry_count": len(ledger_from_audit),
        "covered_payloads": list(PAYLOADS),
        "self_excluded": "evidence_ledger.json（台账不内嵌自身 SHA）",
        "validate_attempts": attempts, "validated": validation,
        "expectation_source": ("本次终审真实读回缓冲（同一次读取取对象与文件 SHA）；"
                               "审核与漂移确认后不再改任何载荷"),
        "content_compare": content,
        "core_audit": core_disk_audit, "api_audit": api_disk_audit,
        "layered_post_hoc": ["protection_result.json", "scan_protection.py",
                            "final_audit_diagnostic.json"],
    })
    print(f"TASK-022-R4 测试组：{len(checks)} 项检查，{len(failures)} 项失败；"
          f"存储 API {len(registry.records)} 次、嵌套核心 {counts['nested_core_calls']}、"
          f"直接核心 {counts['direct_core_calls']}、入口观察 {observer.entry_count}；"
          f"读取事件 {len(read_events)}、守卫命中 {guard.forbidden}")
    for item in failures[:10]:
        print(f"  - {item['name']}: {item['detail'][:200]}")
    return 1 if failures else 0


def _api_isolation(records):
    ids = [record["call_id"] for record in records]
    original = _audit_pair(ids, ids, label="api")
    copy_audit = _audit_pair(ids[:-1], ids, label="api") if ids else original
    return {"removed_call_id": ids[-1] if ids else None, "audit_copy": copy_audit,
            "audit_copy_fails": (not copy_audit["ok"]) if ids else False,
            "original_passes": bool(original["ok"])}


_store_hook_default = store._hook_after_last_consumption


def main():
    parser = argparse.ArgumentParser(description="TASK-022-R1 快照存储测试与证据入口")
    parser.add_argument("--out-dir", required=True, help="全新空证据容器目录")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    return run_suite(out_dir)


if __name__ == "__main__":
    sys.exit(main())
