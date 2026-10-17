# -*- coding: utf-8 -*-
"""TASK-024 测试与证据入口：Gate1 决定保存与限定历史核验适配器。

用法（本卡唯一入口）：
    .venv\\Scripts\\python.exe -B tests\\test_record_demo_human_gate1.py \\
        --out-dir data\\human_gate1_decision_tests\\task024_<轮次>

测试的人类字段只来自**明确登记夹具**：项目权威夹具
`docs/proposals/HUMAN_GATE_DECISION_CASES_V1_DRAFT.md` 第 2 个 JSON 块（`FIXTURE-EV-G1-0001`），
以及 GPT 登记夹具 `data/human_gate1_decision_tests/task024_dev_01/fixtures/TASK024_G1_HOLD_0002.json`
（`FIXTURE-EV-G1-0002`）。程序不生成人类内容；外层标 `PROTOCOL_TEST_FIXTURE_ONLY`。

只读使用：冻结准备器（`prepare_demo_human_gate1.py`）与冻结存储（`store_demo_human_gate_decision.py`）
的公开 API，以及本卡新增适配器 `record_demo_human_gate1.py`。不接宿主/控制器/Gate2/真实初判/AI。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import marshal
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = PROJECT_ROOT / "scripts" / "record_demo_human_gate1.py"
STORE_PATH = PROJECT_ROOT / "scripts" / "store_demo_human_gate_decision.py"
RECEIVER_PATH = PROJECT_ROOT / "scripts" / "receive_demo_batch.py"
CASES_DOC = PROJECT_ROOT / "docs" / "proposals" / "HUMAN_GATE_DECISION_CASES_V1_DRAFT.md"
HOLD_FIXTURE = (PROJECT_ROOT / "data" / "human_gate1_decision_tests" / "task024_dev_01"
                / "fixtures" / "TASK024_G1_HOLD_0002.json")
FIXTURE_XLSX = (PROJECT_ROOT / "data" / "generated" / "demo_20260930_a" / "fixtures"
                / "C06b.xlsx")
RECORDS_ROOT = PROJECT_ROOT / "data" / "human_gate_decision_records" / "gate1"
PYTHON = sys.executable

CHECKS: list = []
FAILURES: list = []
CALLS: list = []
CALL_INDEX = itertools.count(1)
SUITE_OUT_DIR: Path | None = None
SAMPLES: list = []


def check(name, ok, detail=""):
    record = {"name": name, "ok": bool(ok), "detail": str(detail)[:500]}
    CHECKS.append(record)
    if not ok:
        FAILURES.append(record)
    return bool(ok)


def canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def fingerprint(obj):
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def load_adapter():
    spec = importlib.util.spec_from_file_location("record_demo_human_gate1_under_test",
                                                 ADAPTER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_store():
    spec = importlib.util.spec_from_file_location("store_demo_human_gate_decision_under_test",
                                                 STORE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def doc_fixture():
    text = CASES_DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
    return json.loads(blocks[1])


def hold_fixture():
    return json.loads(HOLD_FIXTURE.read_text(encoding="utf-8"))["fragment"]


def reject_fixture():
    """第三份已登记合成夹具（EV-0003/REJECT，仅只读复用）。"""
    path = (PROJECT_ROOT / "data" / "reviews" /
            "task024_gpt_20261014_050915" / "registered_fixture_0003.json")
    return json.loads(path.read_text(encoding="utf-8"))["fragment"]


def run_receiver(xlsx: Path, out_dir: Path, description: str, round_dir: Path):
    """E2.5：真实接收器调用——保存完整 stdout/stderr 原文引用并独立核对内部 checker 证据。"""
    completed = subprocess.run(
        [str(PYTHON), "-B", str(RECEIVER_PATH), "--workbook", str(xlsx),
         "--out-dir", str(out_dir), "--source-description", description],
        capture_output=True, text=True)
    stdout_path = round_dir / f"receiver_{out_dir.name}.stdout.txt"
    stderr_path = round_dir / f"receiver_{out_dir.name}.stderr.txt"
    stdout_path.write_bytes((completed.stdout or "").encode("utf-8"))
    stderr_path.write_bytes((completed.stderr or "").encode("utf-8"))

    def reference(path: Path, text: str):
        data = path.read_bytes()
        return {"reference": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "byte_size": len(data), "file_sha256": sha_bytes(data),
                "text_sha256": sha_bytes(text.encode("utf-8")), "text": text}

    def artifact(relative: str):
        path = out_dir / relative
        data = path.read_bytes() if path.exists() else None
        return {"path": relative, "exists": data is not None,
                "byte_size": len(data) if data is not None else None,
                "file_sha256": sha_bytes(data) if data is not None else None}

    manifest_path = out_dir / "batch_manifest.json"
    manifest = (json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.exists() else {})
    invocation = manifest.get("checker_invocation") or {}
    record = {"out_dir": str(out_dir.relative_to(PROJECT_ROOT)).replace("\\", "/"),
              "returncode": completed.returncode,
              "description": description,
              "stdout": reference(stdout_path, completed.stdout or ""),
              "stderr": reference(stderr_path, completed.stderr or ""),
              "internal_checker": {
                  "attempted": invocation.get("attempted"),
                  "started": invocation.get("started"),
                  "exit_code": invocation.get("exit_code"),
                  "argv": invocation.get("argv"),
                  "report_result": invocation.get("report_result"),
                  "report_matches_snapshot": invocation.get("report_matches_snapshot"),
                  "report_matches_checker": invocation.get("report_matches_checker"),
                  "artifacts": [artifact("checks/quality_report.json"),
                                artifact("logs/checker.stdout.txt"),
                                artifact("logs/checker.stderr.txt"),
                                artifact("code_snapshot/check_demo_data.py")]},
              "manifest_receive_exit_code": manifest.get("receive_exit_code"),
              "manifest_batch_status": manifest.get("batch_status"),
              "direct_checker_cli_runs": 0,
              "direct_checker_cli_reason": "本套件不直接调用 checker CLI；内部启动数由批次清单与日志观测分列"}
    SAMPLES.append(record)
    return record


def build_samples(batch_root: Path):
    inputs = batch_root / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    samples = {}
    for name, mutate, description in (
            ("C06b_normal", None, "TASK-024 测试样本 A（合成夹具 C06b 正常）：不构成业务范围确认"),
            ("C06b_normal_b", None, "TASK-024 测试样本 B（合成夹具 C06b 正常）：不构成业务范围确认"),
            ("C06b_currency_usd", "usd", "TASK-024 测试样本（仅币种 USD）：不构成业务范围确认")):
        xlsx = inputs / f"{name}.xlsx"
        shutil.copyfile(FIXTURE_XLSX, xlsx)
        if mutate == "usd":
            from openpyxl import load_workbook
            workbook = load_workbook(xlsx)
            sheet = workbook["payables"]
            header = [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
            sheet.cell(row=2, column=header.index("currency") + 1).value = "USD"
            workbook.save(xlsx)
            workbook.close()
        record = run_receiver(xlsx, batch_root / name, description, SUITE_OUT_DIR)
        samples[name] = record
    return samples


def submission_for(module, batch: Path, request_id: str, fixture, decision=None):
    """按冻结 schema 组装 submission；人类字段只来自登记夹具。

    E2.1：此处的公开 prepare 调用**同样进入统一登记**（不再有未登记的真实公开 API 调用）。
    """
    entry = call(module, f"submission::{next(CALL_INDEX)}::{request_id}::{batch.name}",
                 call="prepare", _function=module.prepare_human_gate1_decision_request,
                 batch_dir=batch, request_id=request_id)
    if entry.get("outcome") != "returned":
        raise RuntimeError(f"submission 准备阶段失败：{entry.get('case_id')} "
                           f"{entry.get('field') or entry.get('stage')}")
    request = entry["result"]
    return {
        "submission_version": "TASK-020-human-gate-decision-submission-1.1",
        "event_id": fixture["event_id"], "batch_id": batch.name,
        "gate": fixture.get("gate", "GATE1"),
        "request_binding": {"request_id": request_id,
                            "materials_binding":
                                request["materials"]["materials_fingerprint"]},
        "decision": decision or fixture["decision"],
        "decision_source": fixture.get("decision_source", "HUMAN_GATE_DECISION"),
        "actor": fixture["actor"], "decided_at_raw": fixture["decided_at_raw"],
        "reason": fixture["reason"], "prior_decision_binding": None,
    }


class EntryObserver:
    """E2.1 独立入口观察：按 (文件基名, 函数名) 统计真实 frame 进入，不依赖任何包装计数。"""

    TARGET_FILES = ("record_demo_human_gate1.py", "prepare_demo_human_gate1.py",
                    "store_demo_human_gate_decision.py",
                    "build_demo_human_gate_decision.py")
    # E2.3：测试注入 wrapper 位于测试文件内，显式排除；其余文件只按真实函数名计数
    SELF_FILE = "test_record_demo_human_gate1.py"
    TRACKED = ("prepare_human_gate1_request", "save_human_gate_decision_snapshots",
               "verify_human_gate_decision_snapshots", "build_human_gate_decision_record",
               "_call_p1_once", "save_human_gate1_decision", "verify_human_gate1_decision",
               "prepare_human_gate1_decision_request")

    def __init__(self):
        self.counts: dict = {}
        self.trace_counts: dict = {}
        self.samples: dict = {}

    def _profile(self, frame, event, arg):
        if event == "call":
            filename = Path(frame.f_code.co_filename).name
            if filename == self.SELF_FILE:
                return  # 测试注入 wrapper 单独分列：不计入业务函数层
            if frame.f_code.co_name in self.TRACKED and filename.endswith(".py"):
                key = f"{filename}::{frame.f_code.co_name}"
                self.counts[key] = self.counts.get(key, 0) + 1
                if len(self.samples.get(key, ())) < 2:
                    self.samples.setdefault(key, []).append(
                        {"file": filename, "function": frame.f_code.co_name,
                         "firstlineno": frame.f_code.co_firstlineno})

    def _trace(self, frame, event, arg):
        """独立第二通道（settrace call 事件）：作为真实入口的独立聚合计数。"""
        if event == "call":
            filename = Path(frame.f_code.co_filename).name
            if filename != self.SELF_FILE and frame.f_code.co_name in self.TRACKED:
                key = f"{filename}::{frame.f_code.co_name}"
                self.trace_counts[key] = self.trace_counts.get(key, 0) + 1
        return self._trace

    def start(self):
        sys.setprofile(self._profile)
        sys.settrace(self._trace)

    def stop(self):
        sys.setprofile(None)
        sys.settrace(None)

    def layer_trace(self, function):
        return sum(count for key, count in self.trace_counts.items()
                   if key.endswith(f"::{function}"))

    def layer(self, filename, function):
        return self.counts.get(f"{filename}::{function}", 0)

    def payload(self):
        return {"counts": dict(sorted(self.counts.items())),
                "trace_counts": dict(sorted(self.trace_counts.items())),
                "samples": {key: value for key, value in sorted(self.samples.items())},
                "adapter_prepare": self.layer("record_demo_human_gate1.py",
                                              "prepare_human_gate1_decision_request"),
                "adapter_save": self.layer("record_demo_human_gate1.py",
                                           "save_human_gate1_decision"),
                "adapter_verify": self.layer("record_demo_human_gate1.py",
                                             "verify_human_gate1_decision"),
                "frozen_prepare": self.layer("prepare_demo_human_gate1.py",
                                             "prepare_human_gate1_request"),
                "store_save": self.layer("store_demo_human_gate_decision.py",
                                         "save_human_gate_decision_snapshots"),
                "store_verify": self.layer("store_demo_human_gate_decision.py",
                                           "verify_human_gate_decision_snapshots"),
                "scope_enumerate": self.layer("record_demo_human_gate1.py", "_list_scope")}


CORE_OBSERVATIONS: list = []
RETAINED: list = []
EXPECTED_MUTATION = {"active": False}
# 故障豁免只对**当前一次 API/观察窗口**有效；收尾即失效。历史登记仅作只读证据。
MUTATION_WINDOW = {"paths": set(), "active": False}
EXPECTED_PATH_LOG: list = []
ACTIVE_OBSERVER = None
LAYER_FUNCTIONS = {"frozen_prepare": "prepare_human_gate1_request",
                   "store_save": "save_human_gate_decision_snapshots",
                   "store_verify": "verify_human_gate_decision_snapshots",
                   "real_p1": "build_human_gate_decision_record",
                   "real_p1_seam": "_call_p1_once"}


def layer_frames(layer):
    if ACTIVE_OBSERVER is None or layer not in LAYER_FUNCTIONS:
        return None
    name = LAYER_FUNCTIONS[layer]
    return sum(count for key, count in ACTIVE_OBSERVER.counts.items()
               if key.endswith(f"::{name}"))


def code_fingerprint(function):
    """调用前后的真实引用指纹：代码对象身份 + 字节哈希（不依赖任何包装）。"""
    code = getattr(function, "__code__", None)
    if code is None:
        return {"kind": "non_python", "repr": repr(function)[:200]}
    # 稳定指纹：不依赖 marshal 的可变序列化，直接用代码对象的结构化摘要
    payload = b"|".join([
        code.co_filename.encode("utf-8", "replace"), str(code.co_firstlineno).encode(),
        code.co_name.encode(), str(code.co_argcount).encode(),
        ",".join(code.co_varnames).encode(), bytes(code.co_code),
        repr(code.co_consts).encode("utf-8", "replace")])
    return {"kind": "python", "module": getattr(function, "__module__", None),
            "qualname": getattr(function, "__qualname__", None),
            "file": Path(code.co_filename).name, "firstlineno": code.co_firstlineno,
            "code_sha256": sha_bytes(payload)}


def describe_input(value):
    if isinstance(value, Path):
        return {"kind": "path", "path": str(value)}
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        buffer = canonical_bytes(value)
        return {"kind": "json", "byte_size": len(buffer), "sha256": sha_bytes(buffer),
                "value": value}
    return {"kind": type(value).__name__, "repr": repr(value)[:200]}


def deep_snapshot(value):
    """独立深拷贝（canonical 往返），保存为独立对象、不留原输入别名。"""
    return json.loads(independent_canonical(value))


def object_fingerprint(value):
    """实际消费对象的规范指纹（测试侧独立实现，独立于函数代码指纹）。

    路径型输入按**真实文件现场**取指纹（长度 + SHA），不能只以 str(path) 代表文件未变。
    """
    if isinstance(value, Path):
        scene = (bounded_dir_scene(value, "path_dir") if value.is_dir()
                 else describe_input(value, "path").copy())
        scene.pop("field", None)
        return independent_fingerprint(scene)
    return independent_fingerprint(value)


def bounded_dir_scene(path: Path, role="input_dir"):
    """有界目录现场：只读该目录首层（≤32 项），逐项记类型/大小/SHA；不 rglob 项目或历史根。"""
    try:
        entries = sorted(entry.name for entry in os.scandir(path))
    except OSError as exc:
        return {"kind": "path", "role": role, "path": _project_rel(path),
                "exists": False, "read_error": str(exc)}
    files, dirs, subdir_files = {}, {}, {}
    for name in entries[:32]:
        child = path / name
        if child.is_dir():
            try:
                inner = sorted(entry.name for entry in os.scandir(child))
            except OSError:
                dirs[name], subdir_files[name] = None, None
                continue
            dirs[name] = inner[:32]
            scenes = {}
            for inner_name in inner[:32]:
                inner_path = child / inner_name
                if inner_path.is_file():
                    data = inner_path.read_bytes()
                    scenes[inner_name] = {"byte_size": len(data),
                                          "file_sha256": sha_bytes(data),
                                          "relative": f"{name}/{inner_name}"}
            subdir_files[name] = scenes
        elif child.is_file():
            data = child.read_bytes()
            files[name] = {"byte_size": len(data), "file_sha256": sha_bytes(data),
                           "relative": name}
    return {"kind": "path", "role": role, "path": _project_rel(path), "exists": True,
            "is_dir": True, "entry_count": len(entries), "entries": entries,
            "file_scenes": files, "subdir_entries": dirs, "subdir_file_scenes": subdir_files}


def _project_rel(path: Path) -> str:
    text = str(path)
    return (str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            if text.startswith(str(PROJECT_ROOT)) else text)


def describe_input(value, field="input", role="input"):
    """输入描述：对象记规范指纹 + 独立深拷贝快照（自洽）；路径按角色记真实有界现场。"""
    if isinstance(value, Path):
        if value.is_dir():
            return dict(bounded_dir_scene(value, role), field=field)
        data = value.read_bytes() if value.is_file() else None
        return {"kind": "path", "role": role, "field": field, "path": _project_rel(value),
                "exists": data is not None, "is_dir": False,
                "byte_size": len(data) if data is not None else None,
                "file_sha256": sha_bytes(data) if data is not None else None,
                "output_target": role == "output_dir",
                "expected_created_after_write": role == "output_dir" and data is None}
    snapshot = deep_snapshot(value)
    payload = independent_canonical(snapshot).encode("utf-8")
    return {"kind": type(value).__name__, "field": field,
            "canonical_sha256": sha_bytes(payload), "byte_size": len(payload),
            "snapshot": snapshot, "alias_free": snapshot is not value}


PATH_ROLES = {"frozen_prepare": {0: "input_dir"}, "store_save": {0: "output_dir"},
              "store_verify": {0: "input_dir"}}


def observe_core(layer, case_id, function, *args, **kwargs):
    """真实核心调用观察：实际消费对象引用三时点 + 独立深拷贝输入/输出快照。

    `code_stability` 只描述**函数代码**在这段时间内未变，不代表消费对象引用不变；
    对象不变性由同一引用的规范指纹在调用前后比较（`input_unchanged`）证明。
    """
    frames_before = layer_frames(layer)
    argument_refs = list(args) + list(kwargs.values())
    positions = [f"arg[{index}]" for index in range(len(args))] + \
        [f"kwarg[{key}]" for key in kwargs]
    roles = [PATH_ROLES.get(layer, {}).get(index, "input")
             for index in range(len(args))] + ["input"] * len(kwargs)
    before_fingerprints = [object_fingerprint(value) for value in argument_refs]
    watched = [index for index, role in enumerate(roles)
               if role != "output_dir"]
    entry = {"case_id": case_id, "layer": layer,
             "code_stability": {"reference_before": code_fingerprint(function),
                                "scope": "function_code_only"},
             "inputs": [describe_input(value, field,
                                       PATH_ROLES.get(layer, {}).get(index, "input"))
                        for index, (value, field) in enumerate(
                            zip(args, positions[:len(args)]))],
             "input_kwargs": {key: describe_input(value, f"kwarg[{key}]")
                              for key, value in kwargs.items()},
             "input_fingerprints_before": before_fingerprints,
             "input_positions": positions}
    try:
        result = function(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 - 真实异常原样记录并上抛
        after_fingerprints = [object_fingerprint(value) for value in argument_refs]
        entry.update({"outcome": "raised", "exception_type": f"{type(exc).__name__}",
                      "exception_message": str(exc),
                      "exception_chain": [{"type": f"{type(node).__name__}",
                                           "message": str(node)}
                                          for node in _cause_chain(exc)],
                      "traceback": traceback.format_exc(),
                      "input_fingerprints_after": after_fingerprints,
                      "input_roles": roles,
                      "output_targets": [index for index, role in enumerate(roles)
                                         if role == "output_dir"],
                      "input_unchanged": all(
                          before_fingerprints[index] == after_fingerprints[index]
                          for index in watched)})
        entry["code_stability"]["reference_after"] = code_fingerprint(function)
        entry["code_stability"]["code_unchanged"] = (
            entry["code_stability"]["reference_before"]
            == entry["code_stability"]["reference_after"])
        frames_after = layer_frames(layer)
        entry["frame_delta"] = (None if frames_before is None or frames_after is None
                                else frames_after - frames_before)
        CORE_OBSERVATIONS.append(entry)
        RETAINED.append({"entry": entry, "refs": argument_refs,
                         "before": before_fingerprints, "watched": watched})
        raise
    after_fingerprints = [object_fingerprint(value) for value in argument_refs]
    if isinstance(result, (dict, list)):
        output_snapshot = deep_snapshot(result)
        payload = independent_canonical(output_snapshot).encode("utf-8")
        entry["result"] = {"kind": type(result).__name__, "byte_size": len(payload),
                           "sha256": sha_bytes(payload), "item_count": len(result),
                           "present": True, "snapshot": output_snapshot,
                           "alias_free": output_snapshot is not result}
    else:
        entry["result"] = {"kind": type(result).__name__, "repr": repr(result)[:200],
                           "present": True}
    entry.update({"outcome": "returned", "input_fingerprints_after": after_fingerprints,
                  "input_roles": roles,
                  "output_targets": [index for index, role in enumerate(roles)
                                     if role == "output_dir"],
                  "input_unchanged": all(
                      before_fingerprints[index] == after_fingerprints[index]
                      for index in watched)})
    output_after = [bounded_dir_scene(value, "output_dir_after")
                    for index, value in enumerate(args)
                    if isinstance(value, Path)
                    and PATH_ROLES.get(layer, {}).get(index) == "output_dir"]
    if output_after:
        entry["output_scene_after"] = output_after
    entry["code_stability"]["reference_after"] = code_fingerprint(function)
    entry["code_stability"]["code_unchanged"] = (
        entry["code_stability"]["reference_before"]
        == entry["code_stability"]["reference_after"])
    frames_after = layer_frames(layer)
    entry["frame_delta"] = (None if frames_before is None or frames_after is None
                            else frames_after - frames_before)
    CORE_OBSERVATIONS.append(entry)
    RETAINED.append({"entry": entry, "refs": argument_refs,
                     "before": before_fingerprints, "watched": watched})
    return result


def _cause_chain(exc):
    chain, node, seen = [], exc, 0
    while node is not None and seen < 12:
        chain.append(node)
        node = node.__cause__ or node.__context__
        seen += 1
    return chain


def _project_relative_for_probe(item):
    return {"case_id": item.get("case_id"), "outcome": item.get("outcome"),
            "input_unchanged": item.get("input_unchanged"),
            "input_unchanged_through_api": item.get("input_unchanged_through_api")}


def finalize_api_time_point():
    """E2.2 第三时点：所属公开 API 收尾时，对同一保留引用再取一次独立规范指纹。

    private 引用只用于本函数计算，不写入证据 JSON；比较结果写入条目。
    """
    for item in RETAINED:
        entry = item["entry"]
        now = [object_fingerprint(value) for value in item["refs"]]
        entry["input_unchanged_through_api"] = all(
            item["before"][index] == now[index] for index in item["watched"])
        entry["three_time_points_equal"] = (
            entry.get("input_unchanged") is True
            and entry["input_unchanged_through_api"] is True)
        changed_paths = set()
        for index in item["watched"]:
            value = item["refs"][index]
            if not isinstance(value, Path) or not value.is_dir():
                continue
            before_scene = (entry["inputs"][index]
                            if index < len(entry.get("inputs") or []) else None)
            if before_scene is None:
                continue
            after_scene = bounded_dir_scene(value, before_scene.get("role", "input_dir"))
            before_all = dict(before_scene.get("file_scenes") or {})
            after_all = dict(after_scene.get("file_scenes") or {})
            for sub, scenes in (before_scene.get("subdir_file_scenes") or {}).items():
                for name, record in (scenes or {}).items():
                    before_all[f"{sub}/{name}"] = record
            for sub, scenes in (after_scene.get("subdir_file_scenes") or {}).items():
                for name, record in (scenes or {}).items():
                    after_all[f"{sub}/{name}"] = record
            for key in sorted(set(before_all) | set(after_all)):
                left = (before_all.get(key) or {}).get("file_sha256")
                right = (after_all.get(key) or {}).get("file_sha256")
                if left != right:
                    changed_paths.add(key)
        object_changed = any(item["before"][index] != now[index]
                             for index in item["watched"]
                             if not isinstance(item["refs"][index], Path))
        if not changed_paths and object_changed and EXPECTED_MUTATION["active"]:
            changed_paths = {"<object-input>"}
        entry["mutation_paths"] = sorted(changed_paths)
        window_paths = set(MUTATION_WINDOW["paths"])
        entry["window_paths"] = sorted(window_paths)
        entry["window_active"] = bool(MUTATION_WINDOW["active"])
        # 预期变更：只认**当前窗口**登记过的注入目标（历史登记不作豁免）
        entry["expected_mutation"] = bool(changed_paths) and (
            (window_paths and changed_paths <= window_paths)
            or (changed_paths == {"<object-input>"} and MUTATION_WINDOW["active"]))
        entry["three_time_points_equal_or_expected"] = (
            entry["three_time_points_equal"] or entry["expected_mutation"])
    RETAINED.clear()
    EXPECTED_MUTATION["active"] = False
    MUTATION_WINDOW["paths"].clear()   # 本次窗口结束即失效
    MUTATION_WINDOW["active"] = False


def call(module, case_id, **kwargs):
    """一次真实公开 API 调用；记录完整返回或异常+traceback/cause。"""
    function = kwargs.pop("_function")
    call_name = kwargs.pop("call")
    entry = {"case_id": case_id, "call": call_name,
             "kwargs": {key: (str(value) if isinstance(value, Path) else value)
                        for key, value in kwargs.items()}}
    try:
        result = function(**kwargs)
    except (module.HumanGate1DecisionBlocked, module.HumanGate1DecisionError) as exc:
        entry.update({"outcome": ("blocked"
                                  if isinstance(exc, module.HumanGate1DecisionBlocked)
                                  else "error"),
                      "field": getattr(exc, "field", None),
                      "stage": getattr(exc, "stage", None), "reason": str(exc),
                      "exception_chain": module._exception_detail(exc)["cause_chain"],
                      "traceback": module._exception_detail(exc)["traceback"]})
        CALLS.append(entry)
        return entry
    entry.update({"outcome": "returned", "result": result})
    CALLS.append(entry)
    return entry


def independent_canonical(value) -> str:
    """测试侧独立 canonical 实现（不调用生产 helper）：手写排序/分隔/严格类型。"""
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda item: item[0].encode("utf-8"))
        return "{" + ",".join(
            f"{independent_canonical(key)}:{independent_canonical(item)}"
            for key, item in items) + "}"
    if isinstance(value, list):
        return "[" + ",".join(independent_canonical(item) for item in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("non-finite float")
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return "null"
    raise TypeError(f"unsupported type: {type(value).__name__}")


def independent_fingerprint(value) -> str:
    return sha_bytes(independent_canonical(value).encode("utf-8"))


def independent_material_reads(snapshot_materials, source_batch_relative):
    """独立实读 32 项材料与 14 项代码声明：直接从项目文件复算长度/SHA。"""
    problems = []
    files = snapshot_materials.get("files") or []
    if len(files) != 32:
        problems.append(f"materials.files 必须 32 项，实际 {len(files)}")
    batch_dir = PROJECT_ROOT / source_batch_relative
    for item in files:
        relative = item.get("relative") or ""
        if relative.startswith("project/"):
            path = PROJECT_ROOT / relative.split("project/", 1)[1]
        elif relative.startswith("batch/"):
            path = batch_dir / relative[len("batch/"):]
        else:
            path = batch_dir / relative
        if not path.is_file():
            problems.append(f"{relative}: 项目文件不存在")
            continue
        data = path.read_bytes()
        if len(data) != item.get("byte_size"):
            problems.append(f"{relative}: 实际长度 {len(data)} != 声明 {item.get('byte_size')}")
        if sha_bytes(data) != item.get("file_sha256"):
            problems.append(f"{relative}: 实际 SHA 与声明不一致")
    body = {key: value for key, value in snapshot_materials.items()
            if key != "materials_fingerprint"}
    if independent_fingerprint(body) != snapshot_materials.get("materials_fingerprint"):
        problems.append("materials_fingerprint 与独立复算不一致")
    return problems


def independent_code_reads(snapshot_context):
    problems = []
    entries = ((((snapshot_context.get("request") or {}).get("evidence") or {})
                .get("code_manifest") or {}).get("entries")) or []
    if len(entries) != 14:
        problems.append(f"code_manifest.entries 必须 14 项，实际 {len(entries)}")
    for item in entries:
        relative = item.get("relative") or ""
        path = PROJECT_ROOT / relative
        if not path.is_file():
            problems.append(f"{relative}: 代码文件不存在")
            continue
        if sha_bytes(path.read_bytes()) != item.get("file_sha256"):
            problems.append(f"{relative}: 代码实际 SHA 与声明不一致")
    return problems


class WriterProbe:
    """只包装真实独占句柄：经 os.open 记录 fd→路径，按真实文件名注入 OSError/sentinel。"""

    class Sentinel(OSError):
        def __init__(self):
            super().__init__("r1-probe-receipt-sentinel: 完整写入后由测试注入的 sentinel 异常")

    def __init__(self, actions):
        self.actions = dict(actions)
        self.writes = []
        self.opened = []
        self.original_fdopen = os.fdopen
        self.original_open = os.open

    def install(self):
        actions, writes, opened = self.actions, self.writes, self.opened
        original_fdopen, original_open = self.original_fdopen, self.original_open
        fd_paths = {}

        def open_proxy(path, flags, *args, **kwargs):
            handle = original_open(path, flags, *args, **kwargs)
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
                fd_paths[handle] = str(path)
                opened.append({"path": str(path), "flags": flags})
            return handle

        class Proxy:
            def __init__(self, stream, path):
                self._stream = stream
                self._path = path

            def write(self, data):
                writes.append({"path": self._path, "bytes": len(data)})
                action = actions.get(Path(self._path).name)
                if action == "fail":
                    raise OSError(28, f"probe failure-write OSError: {self._path}")
                if action == "half":
                    self._stream.write(data[: max(1, len(data) // 2)])
                    self._stream.flush()
                    raise OSError(28, f"probe half-write OSError: {self._path}")
                if action == "sentinel":
                    self._stream.write(data)
                    self._stream.flush()
                    raise WriterProbe.Sentinel()
                return self._stream.write(data)

            def flush(self):
                return self._stream.flush()

            def fileno(self):
                return self._stream.fileno()

            def close(self):
                return self._stream.close()

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                self._stream.close()
                return False

        def fdopen_proxy(handle, mode="r", *args, **kwargs):
            stream = original_fdopen(handle, mode, *args, **kwargs)
            path = fd_paths.get(handle)
            return Proxy(stream, path) if path else stream

        os.open = open_proxy
        os.fdopen = fdopen_proxy

    def uninstall(self):
        os.open = self.original_open
        os.fdopen = self.original_fdopen


def chain_text(exc):
    parts, cursor = [], exc
    while cursor is not None and len(parts) < 8:
        parts.append(f"{type(cursor).__name__}: {cursor}")
        cursor = cursor.__cause__ or cursor.__context__
    return " <- ".join(parts)


class R1Points:
    """由套件注入的依赖（module/helpers/check/fixtures/容器路径）。"""

    def __init__(self, suite):
        self.s = suite
        self.module = suite["module"]
        self.round_name = suite["round_name"]
        self.batch_a = suite["batch_a"]
        self.batch_b = suite["batch_b"]
        self.records_root = suite["records_root"]
        self.fixtures = suite["fixtures"]
        self.results = []
        self.seq = 0

    # ---------------------------------------------------------------- 基础设施
    def scope(self, suffix):
        scope = self.records_root / f"{self.round_name}_{suffix}"
        scope.mkdir(parents=True, exist_ok=True)
        return scope

    def r1_check(self, name, ok, detail):
        self.results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
        self.s["check"](f"R1-{name}", ok, json.dumps(detail, ensure_ascii=False)[:300])

    def save(self, case_id, batch, request_id, fixture, event_dir, scope):
        submission = self.s["submission_for"](self.module, batch, request_id, fixture)
        return self.s["call"](self.module, case_id, call="save",
                              _function=self.module.save_human_gate1_decision,
                              batch_dir=batch, request_id=request_id, submission=submission,
                              event_dir=event_dir, scope_dir=scope)

    def verify(self, case_id, event_dir, batch, scope):
        return self.s["call"](self.module, case_id, call="verify",
                              _function=self.module.verify_human_gate1_decision,
                              event_dir=event_dir, batch_dir=batch, scope_dir=scope)

    ARG_NAMES = {"prepare": ("batch_dir", "request_id"),
                 "save": ("batch_dir", "request_id", "submission", "event_dir", "scope_dir"),
                 "verify": ("event_dir", "batch_dir", "scope_dir")}

    def outcome(self, function, *args, **kwargs):
        for call_name, target in (
                ("prepare", self.module.prepare_human_gate1_decision_request),
                ("save", self.module.save_human_gate1_decision),
                ("verify", self.module.verify_human_gate1_decision)):
            if function is target:
                self.seq += 1
                call_kwargs = dict(zip(self.ARG_NAMES[call_name], args))
                call_kwargs.update(kwargs)
                entry = self.s["call"](self.module, f"R1-{call_name}-{self.seq}",
                                       call=call_name, _function=function, **call_kwargs)
                if entry.get("outcome") == "returned":
                    return "returned", entry.get("result")
                return entry.get("outcome"), {"field": entry.get("field"),
                                              "stage": entry.get("stage"),
                                              "reason": entry.get("reason"),
                                              "chain": chain_text_from_entry(entry)}
        try:
            return "returned", function(*args, **kwargs)
        except (self.module.HumanGate1DecisionBlocked,
                self.module.HumanGate1DecisionError) as exc:
            return ("blocked" if isinstance(exc, self.module.HumanGate1DecisionBlocked)
                    else "error",
                    {"field": getattr(exc, "field", None),
                     "stage": getattr(exc, "stage", None), "reason": str(exc),
                     "chain": chain_text(exc)})

    def backup(self, scope):
        return {path: path.read_bytes() for path in scope.rglob("*") if path.is_file()}

    def restore(self, backup):
        for path, data in backup.items():
            path.write_bytes(data)

    def sync_outer(self, scope, early_name="event_0001", later_name="event_0002"):
        early = scope / early_name
        context_bytes = (early / "context.json").read_bytes()
        receipt = json.loads((early / "receipt.json").read_text(encoding="utf-8"))
        receipt["context_file_sha256"] = self.s["sha_bytes"](context_bytes)
        (early / "receipt.json").write_bytes(
            self.s["canonical_bytes"](receipt) + b"\n")
        later = scope / later_name
        if later.exists():
            later_context = json.loads((later / "context.json").read_text(encoding="utf-8"))
            for item in later_context["prior_scope"]["prior_events"]:
                if item["event_relative"] == early_name:
                    item["context_file_sha256"] = self.s["sha_bytes"](context_bytes)
                    item["receipt_file_sha256"] = self.s["sha_bytes"](
                        (early / "receipt.json").read_bytes())
            (later / "context.json").write_bytes(
                self.s["canonical_bytes"](later_context) + b"\n")
            later_receipt = json.loads((later / "receipt.json").read_text(encoding="utf-8"))
            later_receipt["context_file_sha256"] = self.s["sha_bytes"](
                (later / "context.json").read_bytes())
            (later / "receipt.json").write_bytes(
                self.s["canonical_bytes"](later_receipt) + b"\n")

    # ---------------------------------------------------------------- B1
    def run_b1(self):
        module = self.module
        f1, f2 = self.fixtures[0], self.fixtures[1]
        scope = self.scope("r1b1")
        first = self.save("R1-B1-save-1", self.batch_a, "FIXTURE-REQ-G1-0001", f1,
                          scope / "event_0001", scope)
        second = self.save("R1-B1-save-2", self.batch_b, "FIXTURE-REQ-G1-0002", f2,
                           scope / "event_0002", scope)
        target = scope / "event_0002"
        control = self.verify("R1-B1-control", target, self.batch_b, scope)
        self.r1_check("B1.0 无注入对照：两事件保存成功且目标 verify 成功",
                      first.get("outcome") == "returned"
                      and second.get("outcome") == "returned"
                      and control.get("outcome") == "returned",
                      {"save1": first.get("outcome"), "save2": second.get("outcome"),
                       "verify": control.get("outcome")})

        original_confirm = module._final_confirm_decision_request
        state = {"hits": 0}

        def inject_once(mutate, undo, hits_target=1, paths=()):
            state["hits"] = 0

            def wrapper(request, batch_dir, adapter_buffer):
                result = original_confirm(request, batch_dir, adapter_buffer)
                state["hits"] += 1
                if state["hits"] == hits_target:
                    EXPECTED_MUTATION["active"] = True
                    MUTATION_WINDOW["active"] = True
                    MUTATION_WINDOW["paths"].update(paths)
                    EXPECTED_PATH_LOG.append({"paths": sorted(paths),
                                              "where": "r1-b1-inject"})
                    mutate()
                return result

            module._final_confirm_decision_request = wrapper
            try:
                outcome_name, payload = self.outcome(module.verify_human_gate1_decision,
                                                     target, self.batch_b, scope_dir=scope)
            finally:
                module._final_confirm_decision_request = original_confirm
                undo()
            restored = self.outcome(module.verify_human_gate1_decision, target,
                                    self.batch_b, scope_dir=scope)[0]
            return outcome_name, payload, restored

        earlier = scope / "event_0001" / "context.json"
        earlier_bytes = earlier.read_bytes()
        name, payload, restored = inject_once(
            lambda: earlier.write_bytes(earlier_bytes + b"\n"),
            lambda: earlier.write_bytes(earlier_bytes), paths=("context.json",))
        self.r1_check("B1.1 较早事件 context 加 LF → 本次 Blocked 并定位",
                      name == "blocked" and "event_0001/context.json" in (payload.get("field") or "")
                      and state["hits"] == 1 and restored == "returned",
                      payload)

        source = self.batch_b / "checks" / "quality_report.json"
        source_bytes = source.read_bytes()
        name, payload, restored = inject_once(
            lambda: source.write_bytes(source_bytes + b"\n"),
            lambda: source.write_bytes(source_bytes),
            paths=("checks/quality_report.json",))
        self.r1_check("B1.2 当前源加 LF → 本次 Blocked 并定位",
                      name == "blocked" and "quality_report.json" in (payload.get("field") or "")
                      and restored == "returned", payload)

        failure = target / "failure.json"

        def add_failure():
            failure.write_bytes(self.s["canonical_bytes"]({
                "failure_version": module.FAILURE_VERSION, "status": "ERROR",
                "stage": "probe", "field": None, "reason": "R1 探针注入",
                "exception_chain": [], "boundaries": dict(module.BOUNDARIES)}) + b"\n")

        name, payload, restored = inject_once(
            add_failure, lambda: failure.unlink(missing_ok=True),
            paths=("failure.json",))
        self.r1_check("B1.3 目标新增 failure.json → 本次 Blocked 并定位",
                      name == "blocked" and "failure.json" in (payload.get("field") or "")
                      and restored == "returned", payload)

        stray = scope / "unregistered_event"
        name, payload, restored = inject_once(
            lambda: stray.mkdir(parents=True, exist_ok=True),
            lambda: stray.rmdir() if stray.exists() else None,
            paths=("unregistered_event",))
        self.r1_check("B1.4 scope 新增空事件目录 → 本次 Blocked 并定位 scope_dir",
                      name == "blocked" and (payload.get("field") or "") == "scope_dir"
                      and restored == "returned", payload)

        # save 接缝：先测来源确认次数，再在“仍有后续必要消费”的接缝注入
        control_scope = self.scope("r1b1_save_control")
        counts = {"n": 0}
        request_id_seam = "FIXTURE-REQ-G1-0001"
        submission_seam = self.s["submission_for"](module, self.batch_a, request_id_seam, f1)

        def counting(request, batch_dir, adapter_buffer):
            counts["n"] += 1
            return original_confirm(request, batch_dir, adapter_buffer)

        module._final_confirm_decision_request = counting
        try:
            control_save = self.s["call"](
                module, "R1-B1-save-control", call="save",
                _function=module.save_human_gate1_decision, batch_dir=self.batch_a,
                request_id=request_id_seam, submission=submission_seam,
                event_dir=control_scope / "event_0001", scope_dir=control_scope)
        finally:
            module._final_confirm_decision_request = original_confirm
        total = counts["n"]
        inject_scope = self.scope("r1b1_save_inject")
        save_state = {"hits": 0}
        save_source = self.batch_a / "checks" / "quality_report.json"
        save_source_bytes = save_source.read_bytes()

        def save_wrapper(request, batch_dir, adapter_buffer):
            result = original_confirm(request, batch_dir, adapter_buffer)
            save_state["hits"] += 1
            if save_state["hits"] == total - 1:
                save_source.write_bytes(save_source_bytes + b"\n")
            return result

        original_snapshot = module._source_snapshot
        snap_state = {"hits": 0}

        def snapshot_wrapper(request, batch_dir):
            result = original_snapshot(request, batch_dir)
            snap_state["hits"] += 1
            EXPECTED_MUTATION["active"] = True
            MUTATION_WINDOW["active"] = True
            MUTATION_WINDOW["paths"].add("checks/quality_report.json")
            EXPECTED_PATH_LOG.append({"paths": ["checks/quality_report.json"],
                                      "where": "r1-b1.5-save-seam"})
            save_source.write_bytes(save_source_bytes + b"\n")
            return result

        module._final_confirm_decision_request = original_confirm
        module._source_snapshot = snapshot_wrapper
        try:
            probe_save = self.s["call"](
                module, "R1-B1-save-seam", call="save",
                _function=module.save_human_gate1_decision, batch_dir=self.batch_a,
                request_id=request_id_seam, submission=submission_seam,
                event_dir=inject_scope / "event_0001", scope_dir=inject_scope)
        finally:
            module._source_snapshot = original_snapshot
            save_source.write_bytes(save_source_bytes)
        failure_path = inject_scope / "event_0001" / "failure.json"
        failure_keys = (sorted(json.loads(failure_path.read_text(encoding="utf-8")))
                        if failure_path.exists() else [])
        self.r1_check("B1.5 save 接缝注入 → 本次拒绝并留恰七键 failure（对照次数 %d）" % total,
                      control_save.get("outcome") == "returned"
                      and probe_save.get("outcome") in ("blocked", "error")
                      and total >= 1 and snap_state["hits"] == 1
                      and failure_keys == sorted(module.FAILURE_KEYS),
                      {"total_confirm_calls": total, "snapshot_hits": snap_state["hits"],
                       "outcome": probe_save.get("outcome"),
                       "field": probe_save.get("field"), "failure_keys": failure_keys})
        return scope

    # ---------------------------------------------------------------- B2
    def run_b2(self):
        f1, f2, f3 = self.fixtures
        lex = self.scope("r1b2lex")
        first = self.save("R1-B2-z_first", self.batch_a, "FIXTURE-REQ-G1-0001", f1,
                          lex / "z_first", lex)
        second = self.save("R1-B2-a_second", self.batch_b, "FIXTURE-REQ-G1-0002", f2,
                           lex / "a_second", lex)
        lex_verify = [self.verify(f"R1-B2-verify-{name}", lex / name, batch, lex).get("outcome")
                      for name, batch in (("z_first", self.batch_a),
                                          ("a_second", self.batch_b))]
        self.r1_check("B2.1 字典序反例：z_first(rev1)→a_second(rev2) 均可保存可恢复",
                      first.get("outcome") == "returned" and second.get("outcome") == "returned"
                      and lex_verify == ["returned", "returned"],
                      {"saves": [first.get("outcome"), second.get("outcome")],
                       "verifies": lex_verify})

        order = self.scope("r1b2order")
        plan = (("event_0001", self.batch_b, "FIXTURE-REQ-G1-0002", f2),
                ("event_0002", self.batch_a, "FIXTURE-REQ-G1-0001", f1),
                ("event_0003", self.batch_b, "FIXTURE-REQ-G1-0003", f3))
        save_outcomes, verify_outcomes = [], []
        for dirname, batch, request_id, fixture in plan:
            save_outcomes.append(self.save(f"R1-B2-save-{dirname}", batch, request_id, fixture,
                                           order / dirname, order).get("outcome"))
        for dirname, batch, request_id, fixture in plan:
            verify_outcomes.append(self.verify(f"R1-B2-verify-{dirname}", order / dirname,
                                               batch, order).get("outcome"))
        context3 = json.loads((order / "event_0003" / "context.json").read_text(encoding="utf-8"))
        history3 = json.loads((order / "event_0003" / "snapshots" / "prior_history.json")
                              .read_text(encoding="utf-8"))
        self.r1_check(
            "B2.2 三事件序 EV-0002→EV-0001→EV-0003：三次保存三次恢复，prior_events 按 revision、records 按 event_id",
            save_outcomes == ["returned"] * 3 and verify_outcomes == ["returned"] * 3
            and context3["revision"] == 3
            and [item["event_relative"] for item in context3["prior_scope"]["prior_events"]]
            == ["event_0001", "event_0002"]
            and [item["record"]["event_id"] for item in history3["records"]]
            == ["FIXTURE-EV-G1-0001", "FIXTURE-EV-G1-0002"],
            {"saves": save_outcomes, "verifies": verify_outcomes,
             "revision": context3["revision"],
             "prior_events": [i["event_relative"]
                              for i in context3["prior_scope"]["prior_events"]],
             "records": [i["record"]["event_id"] for i in history3["records"]]})

    # ---------------------------------------------------------------- B3
    def run_b3(self, scope):
        f2 = self.fixtures[1]
        target = scope / "event_0002"

        def scenario(title, mutate, expected_field):
            backup = self.backup(scope)
            before = self.outcome(self.module.verify_human_gate1_decision, target,
                                  self.batch_b, scope_dir=scope)[0]
            mutate(scope)
            name, payload = self.outcome(self.module.verify_human_gate1_decision, target,
                                         self.batch_b, scope_dir=scope)
            self.restore(backup)
            after = self.outcome(self.module.verify_human_gate1_decision, target,
                                 self.batch_b, scope_dir=scope)[0]
            self.r1_check(f"B3-{title} 被拒并定位 {expected_field}",
                          before == "returned" and name == "blocked"
                          and expected_field in (payload.get("field") or "")
                          and after == "returned",
                          {"before": before, "result": payload, "after": after})

        def mutate_request_empty(root):
            path = root / "event_0001" / "context.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["request"] = {}
            path.write_bytes(self.s["canonical_bytes"](payload) + b"\n")
            self.sync_outer(root)

        def mutate_relative(root):
            path = root / "event_0001" / "context.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["source_batch_relative"] = 7
            path.write_bytes(self.s["canonical_bytes"](payload) + b"\n")
            self.sync_outer(root)

        def mutate_byte_size(root):
            path = root / "event_0001" / "context.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["snapshot_files"][0]["byte_size"] = float(
                payload["snapshot_files"][0]["byte_size"])
            path.write_bytes(self.s["canonical_bytes"](payload) + b"\n")
            self.sync_outer(root)

        def mutate_prior_revision(root):
            path = root / "event_0002" / "context.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["prior_scope"]["prior_events"][0]["revision"] = float(
                payload["prior_scope"]["prior_events"][0]["revision"])
            path.write_bytes(self.s["canonical_bytes"](payload) + b"\n")
            receipt_path = root / "event_0002" / "receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["context_file_sha256"] = self.s["sha_bytes"](path.read_bytes())
            receipt_path.write_bytes(self.s["canonical_bytes"](receipt) + b"\n")

        def mutate_boundary(root):
            path = root / "event_0001" / "context.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["boundaries"]["execution_allowed"] = 0
            path.write_bytes(self.s["canonical_bytes"](payload) + b"\n")
            self.sync_outer(root)

        def mutate_missing_nested(root):
            path = root / "event_0001" / "context.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            del payload["request"]["evidence"]["code_manifest"]
            path.write_bytes(self.s["canonical_bytes"](payload) + b"\n")
            self.sync_outer(root)

        def mutate_extra_nested(root):
            path = root / "event_0001" / "context.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["request"]["materials"]["unexpected"] = 1
            path.write_bytes(self.s["canonical_bytes"](payload) + b"\n")
            self.sync_outer(root)

        scenario("request-empty", mutate_request_empty, "context.request")
        scenario("relative-int", mutate_relative, "source_batch_relative")
        scenario("byte-size-float", mutate_byte_size, "snapshot_files")
        scenario("prior-revision-float", mutate_prior_revision, "prior_events")
        scenario("false-to-zero", mutate_boundary, "boundaries")
        scenario("missing-nested-key", mutate_missing_nested, "evidence")
        scenario("extra-nested-key", mutate_extra_nested, "materials")

        # 键顺序 canonical 等值对照
        path = scope / "event_0001" / "context.json"
        backup = self.backup(scope)
        payload = json.loads(path.read_text(encoding="utf-8"))
        reordered = {key: payload[key] for key in reversed(list(payload))}
        path.write_text(json.dumps(reordered, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        self.sync_outer(scope)
        order_outcome = self.outcome(self.module.verify_human_gate1_decision, target,
                                     self.batch_b, scope_dir=scope)[0]
        self.restore(backup)
        restored = self.outcome(self.module.verify_human_gate1_decision, target,
                                self.batch_b, scope_dir=scope)[0]
        self.r1_check("B3-key-order 同对象不同键序按 canonical 等值仍成功",
                      order_outcome == "returned" and restored == "returned",
                      {"order": order_outcome, "restored": restored})

    # ---------------------------------------------------------------- B4 + E1
    def run_b4_e1(self):
        module = self.module
        f1 = self.fixtures[0]
        broken = self.s["batch_root"] / "r1_no_packet"
        if broken.exists():
            shutil.rmtree(broken)
        shutil.copytree(self.batch_a, broken)
        (broken / "gate1_packet.md").unlink()
        name, payload = self.outcome(module.prepare_human_gate1_decision_request, broken,
                                     "FIXTURE-REQ-G1-0001")
        self.r1_check("B4.1 prepare 缺 gate1_packet → 本层 Blocked（field/reason 保留）",
                      name == "blocked" and bool(payload.get("field")), payload)

        scope = self.scope("r1b4")
        submission = self.s["submission_for"](module, self.batch_a, "FIXTURE-REQ-G1-0001", f1)
        name, payload = self.outcome(module.save_human_gate1_decision, broken,
                                     "FIXTURE-REQ-G1-0001", submission,
                                     scope / "event_0001", scope_dir=scope)
        self.r1_check("B4.2 save 缺 gate1_packet → Blocked、不建事件、无自锁残留",
                      name == "blocked" and not (scope / "event_0001").exists()
                      and not (scope / ".gate1.lock").exists(), payload)

        preset = scope / ".gate1.lock"
        preset.write_bytes(b'{"lock_version":"r1-probe","operation":"SAVE"}\n')
        name, payload = self.outcome(module.save_human_gate1_decision, broken,
                                     "FIXTURE-REQ-G1-0001", submission,
                                     scope / "event_0002", scope_dir=scope)
        untouched = preset.read_bytes().startswith(b'{"lock_version":"r1-probe"')
        preset.unlink()
        self.r1_check("B4.3 既有锁存在 → 拒绝且既有锁字节未动",
                      name == "blocked" and "lock" in (payload.get("field") or "")
                      and untouched, payload)

        good = self.scope("r1b4good")
        self.save("R1-B4-good-save", self.batch_a, "FIXTURE-REQ-G1-0001", f1,
                  good / "event_0001", good)
        name, payload = self.outcome(module.verify_human_gate1_decision,
                                     good / "event_0001", broken, scope_dir=good)
        self.r1_check("B4.4 verify 用缺 gate1_packet 的批次 → Blocked（不冒充成功）",
                      name in ("blocked", "error"), payload)

        original_spec = importlib.util.spec_from_file_location

        def failing_spec(target_name, path, *args, **kwargs):
            spec = original_spec(target_name, path, *args, **kwargs)
            if spec is not None and str(path).endswith("prepare_demo_human_gate1.py"):
                real_loader = spec.loader

                class FailingLoader:
                    def exec_module(self, target_module):
                        raise ImportError("r1-probe: exec_module ImportError")

                    def __getattr__(self, attr):
                        return getattr(real_loader, attr)

                spec.loader = FailingLoader()
            return spec

        def clear_caches():
            module._PREPARE_CACHE["module"] = None
            module._STORE_CACHE["module"] = None
            for key in [k for k in sys.modules if "demo_human_gate" in k]:
                sys.modules.pop(key, None)

        clear_caches()
        importlib.util.spec_from_file_location = failing_spec
        try:
            name, payload = self.outcome(module.prepare_human_gate1_decision_request,
                                         self.batch_a, "FIXTURE-REQ-G1-0001")
        finally:
            importlib.util.spec_from_file_location = original_spec
        clear_caches()
        recovered = self.outcome(module.prepare_human_gate1_decision_request, self.batch_a,
                                 "FIXTURE-REQ-G1-0001")[0]
        self.r1_check("B4.5 loader exec_module ImportError → Error+原因链，撤销后正常",
                      name == "error" and payload.get("stage") == "prepare_load"
                      and "ImportError" in payload.get("chain", "") and recovered == "returned",
                      {"result": payload, "after_undo": recovered})

        probe_scope = self.scope("r1e1_half")
        probe = WriterProbe({"context.json": "half"})
        probe.install()
        try:
            entry = self.save("R1-E1-half", self.batch_a, "FIXTURE-REQ-G1-0001", f1,
                              probe_scope / "event_0001", probe_scope)
        finally:
            probe.uninstall()
        failure_path = probe_scope / "event_0001" / "failure.json"
        self.r1_check("E1.1 真实 context 半写 OSError → Error、原 OSError 在链中、现场保留",
                      entry.get("outcome") == "error"
                      and "half-write" in chain_text_from_entry(entry)
                      and failure_path.exists()
                      and any(item["path"].endswith("context.json") for item in probe.writes),
                      {"entry": {k: entry.get(k) for k in ("outcome", "stage", "field")},
                       "writes": probe.writes[:4],
                       "failure_bytes": failure_path.stat().st_size
                       if failure_path.exists() else None})

        sentinel_scope = self.scope("r1e1_sentinel")
        probe_b = WriterProbe({"receipt.json": "sentinel"})
        probe_b.install()
        try:
            entry_b = self.save("R1-E1-sentinel", self.batch_a, "FIXTURE-REQ-G1-0001", f1,
                                sentinel_scope / "event_0001", sentinel_scope)
        finally:
            probe_b.uninstall()
        receipt_path = sentinel_scope / "event_0001" / "receipt.json"
        self.r1_check("E1.2 receipt 完整写后 sentinel → Error、sentinel 在链中、完整 receipt 保留",
                      entry_b.get("outcome") == "error"
                      and "Sentinel" in chain_text_from_entry(entry_b)
                      and "r1-probe-receipt-sentinel" in chain_text_from_entry(entry_b)
                      and receipt_path.exists()
                      and (sentinel_scope / "event_0001" / "failure.json").exists(),
                      {"entry": {k: entry_b.get(k) for k in ("outcome", "stage", "field")},
                       "receipt_bytes": receipt_path.stat().st_size
                       if receipt_path.exists() else None})

        double_scope = self.scope("r1b43_double")
        probe_c = WriterProbe({"context.json": "half", "failure.json": "fail"})
        probe_c.install()
        try:
            entry_c = self.save("R1-B4.6-double", self.batch_a, "FIXTURE-REQ-G1-0001", f1,
                                double_scope / "event_0001", double_scope)
        finally:
            probe_c.uninstall()
        double_failure = double_scope / "event_0001" / "failure.json"
        reason = entry_c.get("reason") or ""
        self.r1_check("B4.6 context 写失败 + 诊断写失败 → 主/次错误均报告、failure 0 字节",
                      entry_c.get("outcome") == "error" and "half-write" in reason
                      and "failure_write" in reason and double_failure.exists()
                      and double_failure.stat().st_size == 0,
                      {"outcome": entry_c.get("outcome"), "reason": reason[:200],
                       "failure_bytes": double_failure.stat().st_size
                       if double_failure.exists() else None})

    def run_api_time_point_control(self):
        """辨识度控制：真实核心返回且 observe_core 返回后、父 API 收尾前改写保留引用。

        用一次真实 save（内部会调用真实 P1）作为窗口；第三时点必须检出，且移除“预期变更”
        标记后同一正式规则必须拒绝该条记录。
        """
        module = self.module
        f1 = self.fixtures[0]
        store_obj = module.load_frozen_store()
        p1 = store_obj.load_frozen_p1_core()
        inner = getattr(p1, "build_human_gate_decision_record")
        inner_seam = getattr(store_obj, "_call_p1_once", None)
        scope = self.scope("r3e22")
        request_id = "FIXTURE-REQ-G1-0001"
        submission = self.s["submission_for"](module, self.batch_a, request_id, f1)
        records_before = len(CORE_OBSERVATIONS)

        def outside_wrapper(*args, **kwargs):
            result = inner(*args, **kwargs)
            # observe_core 已返回；父 API 尚未收尾 → 改写实际消费对象
            for value in list(args) + list(kwargs.values()):
                if isinstance(value, dict):
                    value["touched_before_api_finalization"] = True
            return result

        original_finalize = finalize_api_time_point
        mutated = {"done": False}

        def mutating_finalize():
            """在 observe_core 已返回、父 API 尚未收尾的窗口内改写保留的真实引用。"""
            if not mutated["done"]:
                MUTATION_WINDOW["active"] = True
                for item in RETAINED:
                    for index in item["watched"]:
                        ref = item["refs"][index]
                        if isinstance(ref, dict) and ref:
                            key = sorted(ref)[0]
                            if isinstance(ref[key], dict):
                                ref[key]["touched_before_api_finalization"] = True
                                mutated["done"] = True
                            elif isinstance(ref[key], str):
                                ref[key] = ref[key] + "|touched"
                                mutated["done"] = True
                        if mutated["done"]:
                            break
                    if mutated["done"]:
                        break
            return original_finalize()

        globals()["finalize_api_time_point"] = mutating_finalize
        EXPECTED_MUTATION["active"] = True
        try:
            entry = self.s["call"](module, "R3-E2.2-third-point", call="save",
                                   _function=module.save_human_gate1_decision,
                                   batch_dir=self.batch_a, request_id=request_id,
                                   submission=submission,
                                   event_dir=scope / "event_0001", scope_dir=scope)
        finally:
            globals()["finalize_api_time_point"] = original_finalize
            self._third_point_mutation = mutated
        produced = [item for item in CORE_OBSERVATIONS[records_before:]]
        detected = any(item.get("input_unchanged_through_api") is False
                       for item in produced)
        flagged = [item["case_id"] for item in produced
                   if item.get("input_unchanged_through_api") is False]
        # 移除“预期变更”标记后，同一正式规则必须拒绝
        formal_problems = []
        for item in produced:
            if item.get("input_unchanged_through_api") is not True \
                    and item.get("expected_mutation") is not True:
                formal_problems.append(
                    f"{item['case_id']}: 第三时点不一致（无预期变更标记时正式拒绝）")
        simulated = []
        for item in produced:
            if item.get("input_unchanged_through_api") is not True:
                simulated.append(f"{item['case_id']}: 输入对象在所属公开 API 收尾时发生变化")
        self.r1_check(
            "R3-E2.2-third-point 父 API 收尾前改写保留引用 → 第三时点检出并由正式规则拒绝",
            detected and bool(flagged) and bool(simulated) and mutated["done"]
            and entry.get("outcome") == "returned",
            {"produced": len(produced), "detected": detected, "flagged": flagged[:4],
             "mutation_applied": mutated["done"],
             "formal_when_unmarked": simulated[:2]})

    def run_r4_prepare_byte_control(self):
        """E2 辨识度控制：真实 prepare 恰一次；观察器返回后、API 收尾前改 batch 字节。

        第三时点必须检出，并由**共享正式审核规则**判失败；证明后按“隔离控制”单列标记，
        原件通过、坏候选失败分列，不以清除审核失败冒充原件通过。
        """
        module = self.module
        target = self.batch_a / "checks" / "quality_report.json"
        original = target.read_bytes()
        fp_before = object_fingerprint(self.batch_a)
        records_before = len(CORE_OBSERVATIONS)
        original_finalize = finalize_api_time_point
        state = {"injected": False}

        def mutating_finalize():
            if not state["injected"]:
                state["injected"] = True
                EXPECTED_MUTATION["active"] = True
                target.write_bytes(original + b"\n")
            return original_finalize()

        MUTATION_WINDOW["paths"].clear()   # 控制项只使用本次窗口登记
        MUTATION_WINDOW["active"] = False
        globals()["finalize_api_time_point"] = mutating_finalize
        try:
            entry = self.s["call"](module, "R4-E2-prepare-byte", call="prepare",
                                   _function=module.prepare_human_gate1_decision_request,
                                   batch_dir=self.batch_a,
                                   request_id="FIXTURE-REQ-G1-0001")
        finally:
            globals()["finalize_api_time_point"] = original_finalize
            target.write_bytes(original)
        produced = [item for item in CORE_OBSERVATIONS[records_before:]]
        prepare_entries = [item for item in produced if item["layer"] == "frozen_prepare"]
        fp_restored = object_fingerprint(self.batch_a)
        target_entry = prepare_entries[0] if prepare_entries else {}
        # 共享正式审核规则（与 evidence_audit 同一判据文本）
        formal_problems = []
        if target_entry.get("expected_mutation") is not True:
            if target_entry.get("input_unchanged_through_api") is not True:
                formal_problems.append(
                    f"{target_entry.get('case_id')}: 输入对象在所属公开 API 收尾时发生变化"
                    f"（第三时点不一致）")
            if target_entry.get("three_time_points_equal") is not True:
                formal_problems.append(
                    f"{target_entry.get('case_id')}: 消费对象三时点不一致")
        clauses = {
            "prepare_called_once": len(prepare_entries) == 1,
            "injected_once": state["injected"] is True,
            "second_point_clean": target_entry.get("input_unchanged") is True,
            "third_point_detected": target_entry.get("input_unchanged_through_api") is False,
            "mutation_path_located": target_entry.get("mutation_paths")
            == ["checks/quality_report.json"],
            "formal_audit_rejects": bool(formal_problems),
            "file_restored": fp_restored == fp_before,
            "api_returned": entry.get("outcome") == "returned",
        }
        # 证明后按隔离控制单列（避免把故意注入当业务异常），并保留证明记录
        if target_entry:
            target_entry["expected_mutation"] = True
            target_entry["control_proof"] = {"formal_problems": formal_problems,
                                             "clauses": clauses}
        self.r1_check(
            "R4-E2-prepare-byte 真实 prepare 一次 + 收尾前改 quality_report 字节 → 第三时点检出且共享审核拒绝",
            all(clauses.values()),
            {"clauses": clauses, "formal_problems": formal_problems,
             "mutation_paths": target_entry.get("mutation_paths")})

    def run_r5_window_controls(self):
        """R5 控制：豁免只在本窗口有效；未登记/额外目标/异常收尾的后续变化必须被**实际
        `evidence_audit`** 拒绝。异常为测试注入的真实父 API 收尾，不声称核心天然出错。
        """
        module = self.module
        original_finalize = globals()["finalize_api_time_point"]
        production_final = module._final_confirm_decision_request

        def isolated_audit(entry):
            """用真实 `evidence_audit` 审核只含该条真实核心观察的隔离候选（不复制判据）。"""
            layer = (entry or {}).get("layer")
            candidate = {
                "calls.json": {"parsed": [{"case_id": "R5-isolated-anchor",
                                           "call": "prepare", "outcome": "returned",
                                           "result": {"status":
                                                      "HUMAN_GATE1_DECISION_REQUEST_PREPARED"}}]},
                "samples.json": {"parsed": []},
                "checks.json": {"parsed": []},
                "failures.json": {"parsed": []},
                "core_observations.json": {"parsed": [entry] if entry else []},
                "summary.json": {"parsed": {"counts": {"receiver_runs": 0,
                                                       "prepare_calls": 1,
                                                       "save_calls": 0,
                                                       "verify_calls": 0},
                                            "checks_total": 0,
                                            "core_entry_total": 1 if entry else 0,
                                            "layer_closure": {layer: {
                                                "entries": 1 if entry else 0,
                                                "frames_trace": 1,
                                                "unique_ids": 1}}}},
            }
            return evidence_audit(candidate)

        def mark_negative_control(observation, label, isolated, kind):
            """标注隔离负向控制：真实观察原值不动，只附本控制的自述与真实审核结果。"""
            if observation is None:
                return
            observation["negative_control"] = {
                "kind": kind,
                "label": label,
                "expected_audit_ok": False,
                "actual_audit_ok": bool(isolated.get("ok")),
                "observation_flags_rewritten": False,
                "registered": [],
                "scope": "预期被真实 evidence_audit 拒绝，不作为正向样本"}

        def run_prepare(case_id, registered=(), changes=(), error_kind=None):
            """一次真实公开 prepare：真实 `_final_confirm_decision_request` 返回后（API 收尾前）
            才改本轮文件字节；`registered` 决定本窗口是否登记（不登记即真实无登记晚变更）。
            """
            module._PREPARE_CACHE["module"] = None
            records_before = len(CORE_OBSERVATIONS)
            originals = {rel: (self.batch_a / rel).read_bytes() for rel in changes}
            state = {"injected": False, "hits": 0, "registered": list(registered),
                     "changed": list(changes), "exception": None}

            def inject_after_real_final(*args, **kwargs):
                value = production_final(*args, **kwargs)
                state["hits"] += 1
                if registered:
                    MUTATION_WINDOW["active"] = True
                    MUTATION_WINDOW["paths"].update(registered)
                    EXPECTED_PATH_LOG.append({"paths": sorted(registered),
                                              "where": case_id})
                for relative, raw in originals.items():
                    (self.batch_a / relative).write_bytes(raw + b"\n")
                state["injected"] = bool(originals)
                if error_kind == "blocked":
                    raise module.HumanGate1DecisionBlocked(
                        "r5_control_field",
                        "PROTOCOL_TEST_FIXTURE_ONLY 受控父 API 收尾拒绝（测试注入）")
                if error_kind == "error":
                    raise module.HumanGate1DecisionError(
                        "r5_control_stage",
                        "PROTOCOL_TEST_FIXTURE_ONLY 受控父 API 收尾运行错误（测试注入）")
                return value

            module._final_confirm_decision_request = inject_after_real_final
            try:
                call_entry = self.s["call"](
                    module, case_id, call="prepare",
                    _function=module.prepare_human_gate1_decision_request,
                    batch_dir=self.batch_a, request_id="FIXTURE-REQ-G1-0001")
                produced = [item for item in CORE_OBSERVATIONS[records_before:]
                            if item["layer"] == "frozen_prepare"]
            finally:
                module._final_confirm_decision_request = production_final
                for relative, raw in originals.items():
                    (self.batch_a / relative).write_bytes(raw)
                state["restored"] = all((self.batch_a / relative).read_bytes() == raw
                                        for relative, raw in originals.items())
            observation = produced[0] if produced else None
            if observation is not None:
                observation["injection_site"] = (
                    "真实 _final_confirm_decision_request 返回后 / 所属公开 API 收尾之前")
                observation["injection_control"] = {
                    "case_id": case_id, "registered": sorted(registered),
                    "changed": sorted(changes), "error_kind": error_kind,
                    "observation_flags_rewritten": False}
            record = {"case_id": case_id, "registered": sorted(registered),
                      "changed": sorted(changes), "error_kind": error_kind,
                      "api_outcome": call_entry.get("outcome"),
                      "field": call_entry.get("field"), "stage": call_entry.get("stage"),
                      "reason": call_entry.get("reason"),
                      "exception_chain": call_entry.get("exception_chain"),
                      "traceback_present": bool(call_entry.get("traceback")),
                      "injection_hits": state["hits"], "injected": state["injected"],
                      "bytes_restored": state.get("restored"),
                      "window_after": {"paths": sorted(MUTATION_WINDOW["paths"]),
                                       "active": MUTATION_WINDOW["active"]}}
            return call_entry, observation, state, record

        # 1) 正常调用：无注入 → 三时点一致、实际 audit 通过
        entry1, obs1, state1, rec1 = run_prepare("R5-normal")
        audit1 = isolated_audit(obs1) if obs1 else {"ok": False, "problems": ["no entry"]}
        rec1.update({"isolated_audit": audit1, "expectation": "真实 audit 通过"})
        R5_CONTROL_LOG.append(rec1)
        clauses = {"three_time_points_equal": bool(obs1) and
                   obs1.get("three_time_points_equal") is True,
                   "input_unchanged_through_api": bool(obs1) and
                   obs1.get("input_unchanged_through_api") is True,
                   "actual_evidence_audit_ok": audit1["ok"] is True}
        self.r1_check("R5.1 正常调用：无注入 → 三时点一致且真实 evidence_audit 通过",
                      all(clauses.values()),
                      {"clauses": clauses, "problems": audit1.get("problems", [])[:3]})

        # 2) 合法故意窗口：本窗口登记并晚改字节 → 检出、定位、按预期控制分列（真实 audit 通过）
        entry2, obs2, state2, rec2 = run_prepare(
            "R5-legal-window", ("checks/quality_report.json",),
            ("checks/quality_report.json",))
        audit2 = isolated_audit(obs2) if obs2 else {"ok": False, "problems": ["no entry"]}
        rec2.update({"isolated_audit": audit2, "expectation": "真实 audit 接受该登记控制条目"})
        R5_CONTROL_LOG.append(rec2)
        clauses = {"injected_after_real_final": state2["injected"] is True,
                   "detected_third_time_point": bool(obs2) and
                   obs2.get("input_unchanged_through_api") is False,
                   "located": bool(obs2) and obs2.get("mutation_paths")
                   == ["checks/quality_report.json"],
                   "marked_expected": bool(obs2) and obs2.get("expected_mutation") is True,
                   "actual_evidence_audit_accepts_expected": audit2["ok"] is True}
        self.r1_check("R5.2 合法故意窗口：检出+定位+按预期控制分列（真实 audit 通过该控制条目）",
                      all(clauses.values()),
                      {"clauses": clauses, "problems": audit2.get("problems", [])[:3]})

        # 3) 合法窗口结束后的紧接下一调用：窗口起点为空，注入的晚变更无新登记 → 真实 audit 拒绝
        entry3, obs3, state3, rec3 = run_prepare("R5-next-call-unregistered-same-path")
        window_before_probe = {"paths": sorted(MUTATION_WINDOW["paths"]),
                               "active": MUTATION_WINDOW["active"]}
        probe_entry, obs3p, probe_state, rec3p = run_prepare(
            "R5-unregistered-late-change", (), ("checks/quality_report.json",))
        audit3 = isolated_audit(obs3p) if obs3p else {"ok": False, "problems": ["no entry"]}
        mark_negative_control(obs3p, "未登记晚变更：合法窗口结束后的紧接调用", audit3,
                              "unregistered_late_change")
        rec3.update({"window_before_probe": window_before_probe,
                     "isolated_audit": audit3,
                     "expectation": "无登记真实晚变更必须被真实 audit 拒绝"})
        rec3p.update({"isolated_audit": audit3, "parent": rec3["case_id"]})
        R5_CONTROL_LOG.extend([rec3, rec3p])
        clauses = {"legit_window_ended_empty": window_before_probe == {"paths": [],
                                                                      "active": False},
                   "probe_unregistered": probe_state["registered"] == [],
                   "probe_changed_after_real_final": probe_state["injected"] is True,
                   "real_observation_not_rewritten": bool(obs3p) and
                   obs3p.get("expected_mutation") is False and
                   obs3p.get("window_active") is False and
                   obs3p.get("window_paths") == [],
                   "actual_evidence_audit_rejects": audit3["ok"] is False,
                   "problem_located": any("第三时点" in text or "三时点" in text
                                          for text in audit3.get("problems") or [])}
        self.r1_check("R5.3 合法窗口结束后紧接调用：无新登记的真实晚变更被实际 evidence_audit 拒绝",
                      all(clauses.values()),
                      {"clauses": clauses, "problems": audit3.get("problems", [])[:3]})

        # 4) 合法窗口内额外改一个未登记目标 → 实际 audit 拒绝并定位额外差异
        extra = self.batch_a / "logs" / "checker.stdout.txt"
        extra_original = extra.read_bytes()
        entry4, obs4, state4, rec4 = run_prepare(
            "R5-extra-target", ("checks/quality_report.json",),
            ("checks/quality_report.json", "logs/checker.stdout.txt"))
        extra.write_bytes(extra_original)
        not_exempted_value = bool(obs4) and obs4.get("expected_mutation") is False
        audit4 = isolated_audit(obs4) if obs4 else {"ok": False, "problems": ["no entry"]}
        mark_negative_control(obs4, "当前窗口内额外未登记目标（额外目标差异）", audit4,
                              "extra_target_in_window")
        rec4.update({"isolated_audit_before_marking": audit4,
                     "not_exempted_before_marking": not_exempted_value})
        if obs4:
            obs4["control_proof"] = {"audit_problems": audit4.get("problems", [])[:3],
                                     "scope": "R5.4 额外未登记目标（真实观察，未改标）",
                                     "not_exempted_before_marking": not_exempted_value}
        R5_CONTROL_LOG.append(rec4)
        clauses = {"detected_extra": bool(obs4) and "logs/checker.stdout.txt"
                   in (obs4.get("mutation_paths") or []),
                   "not_exempted": not_exempted_value,
                   "mutation_paths_complete": bool(obs4) and
                   sorted(obs4.get("mutation_paths") or []) == sorted(
                       ["checks/quality_report.json", "logs/checker.stdout.txt"]),
                   "actual_evidence_audit_rejects": audit4["ok"] is False,
                   "control_marked_as_expectation_rejected": (
                       obs4 or {}).get("negative_control", {}).get("actual_audit_ok")
                   is False}
        self.r1_check("R5.4 窗口内额外未登记目标 → 不被豁免、实际 audit 拒绝并定位额外差异",
                      all(clauses.values()),
                      {"clauses": clauses,
                       "mutation_paths": (obs4 or {}).get("mutation_paths"),
                       "problems": audit4.get("problems", [])[:3]})

        # 5) 真实异常收尾：受控 Blocked / Error 让真实 finally 清空窗口；后续未登记晚变更仍被拒
        ex_obs = {}
        for kind in ("blocked", "error"):
            entry_x, obs_x, state_x, rec_x = run_prepare(
                f"R5-controlled-{kind}-finally", ("checks/quality_report.json",),
                ("checks/quality_report.json",), kind)
            window_after = {"paths": sorted(MUTATION_WINDOW["paths"]),
                            "active": MUTATION_WINDOW["active"]}
            rec_x.update({"window_after_exception": window_after,
                          "bytes_restored": state_x.get("restored")})
            R5_CONTROL_LOG.append(rec_x)
            ex_obs[kind] = (rec_x, obs_x)
            clauses = {"api_outcome_is_%s" % kind: rec_x["api_outcome"] == kind,
                       "field_or_stage_recorded": bool(rec_x.get("field")
                                                       or rec_x.get("stage")),
                       "reason_recorded": bool(rec_x.get("reason")),
                       "exception_chain_recorded": bool(rec_x.get("exception_chain")),
                       "traceback_recorded": rec_x["traceback_present"] is True,
                       "real_final_invoked_before_raise": state_x["hits"] == 1,
                       "window_registered_during_call": state_x["injected"] is True,
                       "window_cleared_by_real_finally": window_after
                       == {"paths": [], "active": False},
                       "injected_bytes_restored": state_x.get("restored") is True}
            self.r1_check(f"R5.5a 受控父 API {kind} 收尾：真实 finally 清空窗口并完整登记异常"
                          f"（测试注入）", all(clauses.values()), {"clauses": clauses})
        window_all_clear = MUTATION_WINDOW["paths"] == set() and \
            MUTATION_WINDOW["active"] is False
        entry6, obs6, state6, rec6 = run_prepare("R5-normal-after-exceptions")
        audit6 = isolated_audit(obs6) if obs6 else {"ok": False, "problems": ["no entry"]}
        rec6.update({"isolated_audit": audit6, "expectation": "异常后正常调用干净"})
        R5_CONTROL_LOG.append(rec6)
        entry7, obs7, state7, rec7 = run_prepare(
            "R5-after-exception-unregistered-late-change", (),
            ("checks/quality_report.json",))
        audit7 = isolated_audit(obs7) if obs7 else {"ok": False, "problems": ["no entry"]}
        mark_negative_control(obs7, "未登记晚变更：受控异常收尾之后的普通调用", audit7,
                              "unregistered_late_change")
        rec7.update({"isolated_audit": audit7,
                     "expectation": "异常后一次无登记晚变更仍被真实 audit 拒绝"})
        R5_CONTROL_LOG.append(rec7)
        clauses = {"window_clear_after_both_exceptions": window_all_clear,
                   "next_call_no_registration": state6["registered"] == []
                   and state6["injected"] is False,
                   "next_normal_call_clean": bool(obs6) and
                   obs6.get("three_time_points_equal") is True and audit6["ok"] is True,
                   "post_exception_late_change_rejected": audit7["ok"] is False,
                   "post_exception_control_marked":
                       (obs7 or {}).get("negative_control", {}).get("actual_audit_ok")
                       is False,
                   "exception_controls_declared_injection":
                       all(obs.get("injection_control", {}).get("error_kind") == kind
                           for kind, (_, obs) in ex_obs.items() if obs)}
        self.r1_check("R5.5 异常收尾后窗口与登记失效：后续正常调用干净、后续无登记晚变更仍被真实 "
                      "evidence_audit 拒绝", all(clauses.values()),
                      {"clauses": clauses, "problems": audit7.get("problems", [])[:3],
                       "log_entries": len(EXPECTED_PATH_LOG)})
    def run_r4_points(self):
        """R4 定点：① 目标事件/目标 snapshots 未知项 → 本次 save 即拒；② 目录八路径字节覆盖。"""
        module = self.module
        f1 = self.fixtures[0]
        request_id = "FIXTURE-REQ-G1-0001"
        original_snapshot = module._source_snapshot

        def target_probe(tag, mutate, undo, expect_in_field):
            scope = self.scope(f"r4_{tag}")
            submission = self.s["submission_for"](module, self.batch_a, request_id, f1)
            state = {"hits": 0}

            def wrapper(request, batch_dir):
                result = original_snapshot(request, batch_dir)
                if state["hits"] == 0:
                    state["hits"] = 1
                    EXPECTED_MUTATION["active"] = True
                    mutate(scope / "event_0001")
                return result

            module._source_snapshot = wrapper
            try:
                entry = self.s["call"](module, f"R4-{tag}", call="save",
                                       _function=module.save_human_gate1_decision,
                                       batch_dir=self.batch_a, request_id=request_id,
                                       submission=submission,
                                       event_dir=scope / "event_0001", scope_dir=scope)
            finally:
                module._source_snapshot = original_snapshot
            failure_path = scope / "event_0001" / "failure.json"
            failure_payload = (json.loads(failure_path.read_text(encoding="utf-8"))
                               if failure_path.exists() else {})
            kept = self.outcome(module.verify_human_gate1_decision,
                                scope / "event_0001", self.batch_a, scope_dir=scope)[0]
            boundaries = failure_payload.get("boundaries") or {}
            clauses = {
                "injected_once": state["hits"] == 1,
                "this_save_rejected": entry.get("outcome") in ("blocked", "error"),
                "located": expect_in_field in (entry.get("field") or ""),
                "failure_seven_keys": sorted(failure_payload) == sorted(module.FAILURE_KEYS),
                "failure_permissions_false": boundaries.get("execution_allowed") is False
                and boundaries.get("workflow_connected") is False
                and boundaries.get("ai_enabled") is False
                and boundaries.get("human_initial_judgment_saved") is False,
                "verify_rejects_after_undo": kept in ("blocked", "error"),
            }
            self.r1_check(
                f"R4-B1-{tag} 本次 save 即拒并定位、failure 恰七键、撤销后 verify 仍拒",
                all(clauses.values()),
                {"clauses": clauses, "entry": {k: entry.get(k) for k in ("outcome", "field")},
                 "failure_keys": sorted(failure_payload), "boundaries": boundaries,
                 "verify_after_undo": kept})
            return scope

        def add_top(scope):
            (scope / "unknown.json").write_bytes(b"{}\n")

        def add_snapshot(scope):
            (scope / "snapshots" / "unknown.json").write_bytes(b"{}\n")

        target_probe("target-unknown", add_top, None, "event_0001")
        target_probe("snapshots-unknown", add_snapshot, None, "snapshots")

        # 正常对照：未注入的新 scope 保存 + 只读恢复
        normal = self.scope("r4_normal")
        submission = self.s["submission_for"](module, self.batch_a, request_id, f1)
        saved = self.s["call"](module, "R4-normal-save", call="save",
                               _function=module.save_human_gate1_decision,
                               batch_dir=self.batch_a, request_id=request_id,
                               submission=submission, event_dir=normal / "event_0001",
                               scope_dir=normal)
        recovered = self.outcome(module.verify_human_gate1_decision, normal / "event_0001",
                                 self.batch_a, scope_dir=normal)[0]
        self.r1_check("R4-B1-normal 未注入新 scope 正常保存 + 只读恢复成功",
                      saved.get("outcome") == "returned" and recovered == "returned",
                      {"save": saved.get("outcome"), "verify": recovered})

        # E2：目录八路径字节覆盖（四类嵌套文件各加 LF → 指纹变化并可定位）
        paths = ("checks/quality_report.json", "source/input.xlsx",
                 "logs/checker.stdout.txt", "code_snapshot/check_demo_data.py")
        results = []
        for relative in paths:
            target = self.batch_a / relative
            original = target.read_bytes()
            scene_before = bounded_dir_scene(self.batch_a, "input_dir")
            fp_before = object_fingerprint(self.batch_a)
            target.write_bytes(original + b"\n")
            scene_after = bounded_dir_scene(self.batch_a, "input_dir")
            fp_after = object_fingerprint(self.batch_a)
            target.write_bytes(original)
            fp_restored = object_fingerprint(self.batch_a)
            before_all, after_all = {}, {}
            for sub, scenes in (scene_before.get("subdir_file_scenes") or {}).items():
                for name, record in (scenes or {}).items():
                    before_all[f"{sub}/{name}"] = record.get("file_sha256")
            for name, record in (scene_before.get("file_scenes") or {}).items():
                before_all[name] = record.get("file_sha256")
            for sub, scenes in (scene_after.get("subdir_file_scenes") or {}).items():
                for name, record in (scenes or {}).items():
                    after_all[f"{sub}/{name}"] = record.get("file_sha256")
            for name, record in (scene_after.get("file_scenes") or {}).items():
                after_all[name] = record.get("file_sha256")
            changed = sorted(key for key in set(before_all) | set(after_all)
                             if before_all.get(key) != after_all.get(key))
            results.append({"relative": relative, "changed": changed,
                            "fingerprint_changed": fp_before != fp_after,
                            "restored": fp_restored == fp_before})
        self.r1_check(
            "R4-E2 八路径字节覆盖：四类嵌套文件各加 LF → 目录指纹变化并定位 relative、恢复回原值",
            all(item["fingerprint_changed"] and item["changed"] == [item["relative"]]
                and item["restored"] for item in results),
            json.dumps(results, ensure_ascii=False)[:400])

    def run_r3_b1_b3(self, scope, target=None):
        """R3 定点：B1 终端各层集合（事件 unknown.json / 批次 checks unknown.json）与 B3 绑定反例。"""
        module = self.module
        f1, f2 = self.fixtures[0], self.fixtures[1]
        scope = scope or self.scope("r3b1")
        target = target or (scope / "event_0002")
        original_snapshot = module._source_snapshot

        def inject_after_snapshot(mutate, undo, batch=self.batch_b, event=target, paths=()):
            state = {"hits": 0}

            def wrapper(request, batch_dir):
                result = original_snapshot(request, batch_dir)
                state["hits"] += 1
                EXPECTED_MUTATION["active"] = True
                MUTATION_WINDOW["active"] = True
                MUTATION_WINDOW["paths"].update(paths)
                EXPECTED_PATH_LOG.append({"paths": sorted(paths),
                                          "where": f"probe:{tag}" if 'tag' in dir() else "probe"})
                mutate()
                return result

            module._source_snapshot = wrapper
            try:
                name, payload = self.outcome(module.verify_human_gate1_decision, event,
                                             batch, scope_dir=scope)
            finally:
                module._source_snapshot = original_snapshot
            # 撤销 wrapper、保留注入现场：仍应拒绝
            kept = self.outcome(module.verify_human_gate1_decision, event, batch,
                                scope_dir=scope)[0]
            undo()
            restored = self.outcome(module.verify_human_gate1_decision, event, batch,
                                    scope_dir=scope)[0]
            return name, payload, kept, restored, state["hits"]

        earlier_unknown = scope / "event_0001" / "unknown.json"
        name, payload, kept, restored, hits = inject_after_snapshot(
            lambda: earlier_unknown.write_bytes(b"{}\n"),
            lambda: earlier_unknown.unlink(missing_ok=True),
            paths=("unknown.json",))
        self.r1_check("R3-B1.1 较早事件新增 unknown.json → 本次 Blocked 并定位、撤销仍拒、移除后正常",
                      name == "blocked" and "event_0001" in (payload.get("field") or "")
                      and kept == "blocked" and restored == "returned" and hits == 1,
                      {"result": payload, "kept": kept, "restored": restored})

        batch_unknown = self.batch_b / "checks" / "unknown.json"
        name, payload, kept, restored, hits = inject_after_snapshot(
            lambda: batch_unknown.write_bytes(b"{}\n"),
            lambda: batch_unknown.unlink(missing_ok=True),
            paths=("checks/unknown.json",))
        self.r1_check("R3-B1.2 当前批次 checks/ 新增 unknown.json → 本次 Blocked 并定位、移除后正常",
                      name == "blocked" and "checks" in (payload.get("field") or "")
                      and kept == "blocked" and restored == "returned"
                      and not (scope / "event_0002" / "failure.json").exists(),
                      {"result": payload, "kept": kept, "restored": restored,
                       "verify_wrote_failure": (scope / "event_0002"
                                                / "failure.json").exists()})

        # save 侧：语义阶段末注入批次内部集合变化 → 拒绝并留恰七键 failure
        save_scope = self.scope("r3b1_save")
        request_id = "FIXTURE-REQ-G1-0001"
        submission = self.s["submission_for"](module, self.batch_a, request_id, f1)

        save_unknown = self.batch_a / "checks" / "unknown.json"

        def save_wrapper(request, batch_dir):
            result = original_snapshot(request, batch_dir)
            EXPECTED_MUTATION["active"] = True
            MUTATION_WINDOW["active"] = True
            MUTATION_WINDOW["paths"].add("checks/unknown.json")
            EXPECTED_PATH_LOG.append({"paths": ["checks/unknown.json"],
                                      "where": "r3-b1.3-save"})
            save_unknown.write_bytes(b"{}\n")
            return result

        module._source_snapshot = save_wrapper
        try:
            probe = self.s["call"](module, "R3-B1.3-save-batch-set", call="save",
                                   _function=module.save_human_gate1_decision,
                                   batch_dir=self.batch_a, request_id=request_id,
                                   submission=submission,
                                   event_dir=save_scope / "event_0001", scope_dir=save_scope)
        finally:
            module._source_snapshot = original_snapshot
            save_unknown.unlink(missing_ok=True)
        failure_path = save_scope / "event_0001" / "failure.json"
        failure_keys = (sorted(json.loads(failure_path.read_text(encoding="utf-8")))
                        if failure_path.exists() else [])
        self.r1_check("R3-B1.3 save 阶段内部集合变化 → 拒绝并留恰七键 failure",
                      probe.get("outcome") in ("blocked", "error")
                      and failure_keys == sorted(module.FAILURE_KEYS),
                      {"outcome": probe.get("outcome"), "field": probe.get("field"),
                       "failure_keys": failure_keys})

        # B3 三例：与冻结配置绑定冲突 / 非真实日历 / 公司矛盾
        def b3(title, mutate, expected):
            backup = self.backup(scope)
            before = self.outcome(module.verify_human_gate1_decision, target, self.batch_b,
                                  scope_dir=scope)[0]
            mutate()
            name, payload = self.outcome(module.verify_human_gate1_decision, target,
                                         self.batch_b, scope_dir=scope)
            self.restore(backup)
            after = self.outcome(module.verify_human_gate1_decision, target, self.batch_b,
                                 scope_dir=scope)[0]
            self.r1_check(f"R3-B3-{title}", before == "returned" and name == "blocked"
                          and expected in (payload.get("field") or "")
                          and after == "returned",
                          {"before": before, "result": payload, "after": after})

        def mutate(field, value):
            def apply():
                path = scope / "event_0001" / "context.json"
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["request"]["evidence"]["source_scope"][field] = value
                path.write_bytes(self.s["canonical_bytes"](payload) + b"\n")
                self.sync_outer(scope)
            return apply

        b3("currency→USD（配置绑定仍 CNY）", mutate("currency", "USD"), "currency")
        b3("period_start=2026-09-00（非真实日历）", mutate("period_start", "2026-09-00"),
           "period_start")
        b3("company 与配置矛盾", mutate("company", "另一家公司"), "company")

    def run_observability_control(self):
        """观察器辨识度故障：受控函数在真实 observe_core 路径上改写内存输入。

        观察器必须检出对象变化（`input_unchanged=False`）并保留调用前快照；该控制条目
        **不进入正式证据**（弹出），避免把测试注入当业务证据。
        """
        module = self.module
        submission = {"submission_version": "probe", "reason": "R2 观察器辨识度故障"}
        before_snapshot = deep_snapshot(submission)

        def controlled(submission_arg):
            submission_arg["reason"] = "被测试改写（观察器辨识度故障）"
            return submission_arg

        records_before = len(CORE_OBSERVATIONS)
        observe_core("observability_control", "control-mutation::1", controlled, submission)
        entry = CORE_OBSERVATIONS.pop()
        detection = {
            "records_delta": len(CORE_OBSERVATIONS) - records_before,
            "input_unchanged": entry.get("input_unchanged"),
            "pre_call_snapshot_reason": (entry["inputs"][0].get("snapshot") or {}).get("reason"),
            "pre_call_snapshot_independent": before_snapshot is not submission,
            "code_fingerprint_says": (entry.get("code_stability") or {}).get("code_unchanged"),
            "code_scope": (entry.get("code_stability") or {}).get("scope"),
        }
        self.r1_check(
            "E2.2c 观察器辨识度：受控改写内存输入 → 检出对象变化、保留原前快照、代码指纹不冒称对象不变",
            detection["records_delta"] == 0 and detection["input_unchanged"] is False
            and detection["pre_call_snapshot_reason"] == "R2 观察器辨识度故障"
            and detection["pre_call_snapshot_independent"] is True
            and detection["code_fingerprint_says"] is True
            and detection["code_scope"] == "function_code_only",
            detection)

    def run_all(self):
        scope = self.run_b1()
        self.run_b2()
        self.run_b3(scope)
        self.run_b4_e1()
        self.run_observability_control()
        self.run_api_time_point_control()
        self.run_r4_points()
        self.run_r4_prepare_byte_control()
        self.run_r5_window_controls()
        b1_scope = self.scope("r3b1")
        r3_saves = [self.save(f"R3-B1-seed-{index}", batch, request_id, fixture,
                              b1_scope / dirname, b1_scope)
                    for index, (dirname, batch, request_id, fixture) in enumerate((
                        ("event_0001", self.batch_a, "FIXTURE-REQ-G1-0001", self.fixtures[0]),
                        ("event_0002", self.batch_b, "FIXTURE-REQ-G1-0002", self.fixtures[1])))]
        if all(item.get("outcome") == "returned" for item in r3_saves):
            self.run_r3_b1_b3(b1_scope)
        return {"checks": len(self.results),
                "failed": len([item for item in self.results if not item["ok"]]),
                "results": self.results}


def chain_text_from_entry(entry):
    chain = entry.get("exception_chain") or []
    return " <- ".join(f"{item.get('type')}: {item.get('message')}" for item in chain)


def strict_equals(left, right, path=""):
    """类型敏感比较：False/0、0/0.0 不等；字典键顺序无关；返回按路径定位的差异。"""
    if type(left) is not type(right):
        return [f"{path or '<root>'}: 类型不同 {type(left).__name__} != {type(right).__name__}"]
    if isinstance(left, dict):
        diffs = []
        for key in sorted(set(left) | set(right)):
            if key not in left:
                diffs.append(f"{path}.{key}: 预期缺该键")
            elif key not in right:
                diffs.append(f"{path}.{key}: 实际缺该键")
            else:
                diffs.extend(strict_equals(left[key], right[key], f"{path}.{key}"))
        return diffs
    if isinstance(left, list):
        if len(left) != len(right):
            return [f"{path}: 长度 {len(left)} != {len(right)}"]
        diffs = []
        for index, (expect, actual) in enumerate(zip(left, right)):
            diffs.extend(strict_equals(expect, actual, f"{path}[{index}]"))
        return diffs
    if left != right:
        return [f"{path}: {left!r} != {right!r}"]
    return []


def _unique_id_closure(name, parsed, id_fields):
    """真实入口/条目/唯一 ID 闭合：登记条数必须与解析条数一致且 ID 互不重复。"""
    problems = []
    if not isinstance(parsed, list):
        return [f"{name}: 期待列表，实际 {type(parsed).__name__}"]
    for field in id_fields:
        values = [item.get(field) if isinstance(item, dict) else None for item in parsed]
        missing = [index for index, value in enumerate(values) if value in (None, "")]
        if missing:
            problems.append(f"{name}: {field} 缺失或为空（{len(missing)} 项）")
            continue
        if len(set(values)) != len(values):
            problems.append(f"{name}: {field} 必须唯一（{len(values)} 项）")
    return problems


def audit_ledger(ledger, audited, negative_controls=None, expect_failure=False):
    """E2.4：台账读回审核——台账登记的字节/判据必须与本次同缓冲审核读数逐项闭合。

    台账**不得**内嵌自身 SHA；本审核只读台账对象与本次读数，不重算台账自身摘要。
    `negative_controls` 为本次真实观察到的隔离负向控制（预期被真实审核拒绝的具名控制），
    必须逐项如实登记，任何不一致（漏记、伪记、自述与预期/实际不符）都支配失败。
    `expect_failure=True` 表示本次台账本就是在真实失败下冻结的（失败判据已在登记前定稿）：
    此时要求台账如实记录失败，而不是要求它假装成功。
    """
    problems = []
    entries = ledger.get("entries") or {}
    if ledger.get("entry_count") != len(audited):
        problems.append("台账 entry_count 与审核载荷数不一致")
    if sorted(ledger.get("covered") or []) != sorted(audited):
        problems.append("台账 covered 与审核载荷集合不一致")
    for name, record in audited.items():
        claimed = entries.get(name) or {}
        if claimed.get("byte_size") != record.get("byte_size"):
            problems.append(f"{name}: 台账字节长度与审核读数不一致")
        if claimed.get("file_sha256") != record.get("file_sha256"):
            problems.append(f"{name}: 台账 SHA 与审核读数不一致")
        for field in ("entry_count", "unique_ids"):
            if field in claimed and claimed.get(field) != record.get(field):
                problems.append(f"{name}: 台账 {field} 与审核读数不一致")
    if ledger.get("byte_drift"):
        problems.append("台账含非空 byte_drift")
    for key in ("pending_audit", "disk_audit", "expectation_compare"):
        if (ledger.get(key) or {}).get("ok") is not True:
            problems.append(f"台账 {key} 不为 ok")
    if expect_failure:
        if ledger.get("final_audit_failed") is not True:
            problems.append("台账已登记真实失败，final_audit_failed 必须为 true")
    else:
        # content_audit 只作信息登记：内容一致已由 expectation_compare 支配。
        if ledger.get("final_audit_failed") is not False:
            problems.append("台账 final_audit_failed 应为 false")
    if negative_controls is not None:
        declared = ledger.get("negative_controls")
        if declared is None:
            problems.append("本次真实观察存在隔离负向控制，但台账未登记（不得缺省）")
        else:
            observed_ids = sorted(negative_controls)
            declared_ids = sorted(declared or {})
            if observed_ids != declared_ids:
                problems.append("台账登记的隔离负向控制与实际观察集合不一致")
            for case_id, item in (negative_controls or {}).items():
                claimed = (declared or {}).get(case_id) or {}
                for field in ("expected_audit_ok", "actual_audit_ok", "expected_mutation",
                              "kind", "observation_flags_rewritten"):
                    if claimed.get(field) != item.get(field):
                        problems.append(f"{case_id}: 台账负向控制 {field} 与真实观察不一致")
                if item.get("kind") == "unregistered_late_change" \
                        and item.get("window_paths_empty") is not True:
                    problems.append(f"{case_id}: 未登记晚变更未观察到窗口已失效")
                if item.get("not_exempted") is not True:
                    problems.append(f"{case_id}: 隔离负向控制被错误豁免为预期变更")
                if item.get("actual_audit_ok") is not False:
                    problems.append(f"{case_id}: 隔离负向控制未被真实审核拒绝")
                if item.get("expected_audit_ok") != item.get("actual_audit_ok"):
                    problems.append(f"{case_id}: 负向控制的自述预期与实际审核结果不符")
    return {"ok": not problems, "problems": problems[:24],
            "entry_count": ledger.get("entry_count"),
            "covered": sorted(ledger.get("covered") or [])}


def disk_readback(name, claimed, path: Path):
    """最终磁盘独立台账核对：不走同缓冲，直接从最后磁盘字节复算长度/SHA。"""
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"name": name, "ok": False, "read_error": str(exc),
                "claimed_byte_size": claimed.get("byte_size"),
                "claimed_file_sha256": claimed.get("file_sha256")}
    actual = {"byte_size": len(data), "file_sha256": sha_bytes(data)}
    ok = (actual["byte_size"] == claimed.get("byte_size")
          and actual["file_sha256"] == claimed.get("file_sha256"))
    return {"name": name, "ok": ok, "claimed_byte_size": claimed.get("byte_size"),
            "actual_byte_size": actual["byte_size"],
            "claimed_file_sha256": claimed.get("file_sha256"),
            "actual_file_sha256": actual["file_sha256"]}


def content_audit_readback(out_dir: Path, frozen: dict, audited: dict):
    """最终磁盘内容审核：重新解析磁盘载荷并逐项核对对象、长度、SHA 与读回读数一致。"""
    problems = []
    for name, claimed in (frozen or {}).items():
        path = out_dir / name
        try:
            data = path.read_bytes()
        except OSError as exc:
            problems.append(f"{name}: 最终磁盘读取失败（{exc}）")
            continue
        record = (audited or {}).get(name) or {}
        expected_buffer = canonical_bytes(claimed) + b"\n"
        if data != expected_buffer:
            problems.append(f"{name}: 最终磁盘字节与冻结载荷字节不一致")
        if record.get("byte_size") != len(data):
            problems.append(f"{name}: 最终磁盘长度与同缓冲读数不一致")
        if record.get("file_sha256") != sha_bytes(data):
            problems.append(f"{name}: 最终磁盘 SHA 与同缓冲读数不一致")
        try:
            parsed = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"{name}: 最终磁盘内容无法解析（{exc}）")
            continue
        if strict_equals(claimed, parsed, name):
            problems.append(f"{name}: 最终磁盘内容与冻结载荷不一致")
    return {"ok": not problems, "problems": problems[:24]}


def late_byte_fault(name, buffer: bytes):
    """收尾故障构造：最后一次必要读数之后给载荷尾部加 LF（测试注入，供支配性反例）。"""
    return buffer + b"\n"


def compare_expectation(expectation, audited):
    """终审比对：预期（观察后独立深拷贝）与首轮同缓冲读数的完整 canonical 比较。"""
    problems, per_payload = [], {}
    for name, payload in expectation.items():
        entry = audited.get(name) or {}
        expected_buffer = canonical_bytes(payload) + b"\n"
        diffs = strict_equals(payload, entry.get("parsed"), name)
        if entry.get("byte_size") != len(expected_buffer):
            diffs.append(f"{name}: 字节长度 {entry.get('byte_size')} != {len(expected_buffer)}")
        if entry.get("file_sha256") != sha_bytes(expected_buffer):
            diffs.append(f"{name}: 字节 SHA 与预期不一致")
        per_payload[name] = {"diff_count": len(diffs), "diffs": diffs[:12]}
        problems.extend(diffs[:12])
    return {"ok": not problems, "problems": problems[:24], "per_payload": per_payload}


def locate_call_diff(expectation, candidate, call_id):
    """按 call_id 定位差异（内容替换/类型替换的定位证据）。"""
    diffs = []
    for name in ("calls.json", "core_observations.json"):
        expected_items = expectation.get(name) or []
        actual_items = candidate.get(name) or []
        for index, item in enumerate(expected_items):
            if item.get("case_id") != call_id:
                continue
            actual = actual_items[index] if index < len(actual_items) else {}
            diffs += strict_equals(item, actual, f"{name}[{call_id}]")
    return diffs


POST_AUDITS: list = []

SUITE_ONLY: str | None = None


OBSERVED: dict = {}

R5_CONTROL_LOG: list = []


def post_audit(name, ok, detail=""):
    """写盘后审核结论：不进 checks.json（避免与已审核字节不一致），但决定支配与返回码。"""
    entry = {"name": name, "ok": bool(ok), "detail": str(detail)[:400]}
    POST_AUDITS.append(entry)
    print(("POST-OK   " if ok else "POST-FAIL ") + name + " :: " + str(detail)[:160])
    return entry


def write_payloads(out_dir: Path, payloads: dict):
    buffers = {}
    for name, payload in payloads.items():
        buffer = canonical_bytes(payload) + b"\n"
        (out_dir / name).write_bytes(buffer)
        buffers[name] = buffer
    return buffers


def read_payloads(out_dir: Path, names):
    """首轮终审读数：逐文件同缓冲取字节长度/SHA/对象。"""
    audited = {}
    for name in names:
        data = (out_dir / name).read_bytes()
        audited[name] = {"byte_size": len(data), "file_sha256": sha_bytes(data),
                         "parsed": json.loads(data.decode("utf-8"))}
    return audited


def evidence_audit(audited):
    """实际收尾审核：完整调用登记、case_id 双向唯一、记录完整、样本与检查闭合。"""
    problems = []
    calls = audited["calls.json"]["parsed"]
    checks = audited["checks.json"]["parsed"]
    samples = audited["samples.json"]["parsed"]
    summary = audited["summary.json"]["parsed"]
    case_ids = [item.get("case_id") for item in calls]
    counts = summary.get("counts", {})
    declared = (counts.get("prepare_calls", 0) + counts.get("save_calls", 0)
                + counts.get("verify_calls", 0))
    if len(calls) != declared:
        problems.append(f"调用登记 {len(calls)} 与声明总数 {declared} 不一致")
    for call_name in ("prepare", "save", "verify"):
        if len([item for item in calls if item.get("call") == call_name]) != \
                counts.get(f"{call_name}_calls"):
            problems.append(f"{call_name} 登记数与声明不一致")
    if len(set(case_ids)) != len(case_ids):
        problems.append("case_id 必须唯一")
    if not case_ids or any(not isinstance(item, str) or item == "" for item in case_ids):
        problems.append("case_id 必须为非空字符串")
    for item in calls:
        if item.get("call") not in ("prepare", "save", "verify"):
            problems.append(f"{item.get('case_id')}: 未知调用类型")
        complete = (("result" in item and isinstance(item["result"], dict))
                    or item.get("outcome") in ("blocked", "error"))
        if not complete:
            problems.append(f"{item.get('case_id')}: 记录不完整")
        if item.get("outcome") == "returned":
            result = item.get("result")
            if not isinstance(result, dict) or not isinstance(result.get("status"), str) \
                    or not result.get("status"):
                problems.append(
                    f"{item.get('case_id')}: 返回对象缺 status（疑为 {{}} 占位返回）")
        if item.get("outcome") in ("blocked", "error") and "exception_chain" not in item:
            problems.append(f"{item.get('case_id')}: 异常记录缺原因链")
    if len(checks) != summary.get("checks_total"):
        problems.append("checks 数量与 summary 不一致")
    if len([item for item in checks if not item.get("ok")]) != len(
            audited["failures.json"]["parsed"]) and summary.get("status") == "PASS":
        problems.append("failures 与检查结果不一致")
    if len(samples) != summary.get("counts", {}).get("receiver_runs"):
        problems.append("接收器样本数与计数不一致")
    core = audited.get("core_observations.json", {}).get("parsed", [])
    declared_core = summary.get("core_entry_total")
    if not isinstance(declared_core, int) or len(core) != declared_core:
        problems.append(f"核心观察登记 {len(core)} 与声明总数 {declared_core} 不一致")
    layer_closure = summary.get("layer_closure") or {}
    for layer, item in layer_closure.items():
        observed = len([entry for entry in core if entry.get("layer") == layer])
        if item.get("entries") != observed:
            problems.append(f"{layer}: 逐层条目 {observed} 与声明 {item.get('entries')} 不一致")
    core_ids = [item.get("case_id") for item in core]
    if len(set(core_ids)) != len(core_ids):
        problems.append("核心观察 case_id 必须唯一")
    for item in core:
        if not item.get("case_id") or not item.get("layer"):
            problems.append("核心观察缺 case_id/layer")
            continue
        if (item.get("code_stability") or {}).get("code_unchanged") is not True:
            problems.append(f"{item['case_id']}: 函数代码指纹在调用前后不一致")
        if (item.get("code_stability") or {}).get("scope") != "function_code_only":
            problems.append(f"{item['case_id']}: 未标注代码指纹只测函数代码")
        if item.get("input_unchanged") is not True:
            problems.append(f"{item['case_id']}: 输入对象在同一引用上发生变化（返回时点）")
        if item.get("expected_mutation") is True:
            if item.get("three_time_points_equal") is True:
                problems.append(
                    f"{item['case_id']}: 标记为预期变更但三时点未检出变化（控制失效）")
        else:
            if item.get("input_unchanged_through_api") is not True:
                problems.append(
                    f"{item['case_id']}: 输入对象在所属公开 API 收尾时发生变化（第三时点不一致）")
            if item.get("three_time_points_equal") is not True:
                problems.append(f"{item['case_id']}: 消费对象三时点不一致")
        for desc in list(item.get("inputs") or []) + list(
                (item.get("input_kwargs") or {}).values()):
            if "snapshot" in desc:
                payload = independent_canonical(desc["snapshot"]).encode("utf-8")
                if desc.get("canonical_sha256") != sha_bytes(payload) or \
                        desc.get("byte_size") != len(payload):
                    problems.append(f"{item['case_id']}: 输入描述与完整值不自洽"
                                    f"（{desc.get('field')}）")
                if desc.get("alias_free") is False:
                    problems.append(f"{item['case_id']}: 输入描述保留了原输入别名")
        if item.get("outcome") == "returned":
            result = item.get("result") or {}
            if result.get("present") is not True:
                problems.append(f"{item['case_id']}: 返回记录缺失（空列表须记 item_count=0）")
            elif result.get("kind") in ("dict", "list") and "item_count" not in result:
                problems.append(f"{item['case_id']}: 容器返回缺 item_count（无法区分空与缺）")
            if result.get("kind") in ("dict", "list") and "snapshot" in result:
                payload = independent_canonical(result["snapshot"]).encode("utf-8")
                if result.get("sha256") != sha_bytes(payload) or \
                        result.get("byte_size") != len(payload):
                    problems.append(f"{item['case_id']}: 返回描述与完整返回快照不自洽")
                if result.get("alias_free") is False:
                    problems.append(f"{item['case_id']}: 返回快照不是独立对象")
        elif item.get("outcome") == "raised":
            if not item.get("exception_type") or not item.get("traceback") \
                    or not item.get("exception_chain"):
                problems.append(f"{item['case_id']}: 异常记录不完整")
        else:
            problems.append(f"{item['case_id']}: 未知结局")
    return {"ok": not problems, "problems": problems, "call_count": len(calls),
            "unique_case_ids": len(set(case_ids)), "check_count": len(checks),
            "sample_count": len(samples), "core_observation_count": len(core),
            "core_layers": sorted({item.get("layer") for item in core})}


























































NEGATIVE_CONTROL_LABEL = "R6 隔离负向控制：未登记晚变更（预期被真实 evidence_audit 拒绝）"


def collect_negative_controls(payloads: dict) -> dict:
    """本次真实观察到的隔离负向控制：预期被真实审核拒绝、不作为正向样本的具名控制。"""
    controls = {}
    for entry in payloads.get("core_observations.json", []):
        marker = entry.get("negative_control") or {}
        if marker.get("kind") not in ("unregistered_late_change",
                                      "extra_target_in_window"):
            continue
        expected_mutation = entry.get("expected_mutation")
        controls[entry.get("case_id")] = {
            "case_id": entry.get("case_id"), "layer": entry.get("layer"),
            "kind": marker.get("kind"), "label": marker.get("label"),
            "expected_audit_ok": marker.get("expected_audit_ok"),
            "actual_audit_ok": marker.get("actual_audit_ok"),
            "expected_mutation": expected_mutation,
            "window_paths_empty": (entry.get("window_paths") == []
                                   and entry.get("window_active") is False),
            "input_unchanged_through_api": entry.get("input_unchanged_through_api"),
            "mutation_paths": sorted(entry.get("mutation_paths") or []),
            "observation_flags_rewritten": marker.get("observation_flags_rewritten"),
            "registered": marker.get("registered"),
            "not_exempted": expected_mutation is False,
        }
    return controls


def evaluated_evidence(payloads: dict, checks_total: int) -> dict:
    """审核范围视图：保留全部已登记条目，只把已登记的隔离负向控制排除在收敛审核之外，
    并按该范围如实改写 summary 声明的条目数（不删任何登记条目）。"""
    core = payloads.get("core_observations.json", [])
    excluded = {entry.get("case_id") for entry in core
                if (entry.get("negative_control") or {}).get("kind")
                in ("unregistered_late_change", "extra_target_in_window")}
    scoped_core = [entry for entry in core if entry.get("case_id") not in excluded]
    evaluated = dict(payloads)
    evaluated["core_observations.json"] = scoped_core
    summary = dict(payloads.get("summary.json") or {})
    scoped_closure = {}
    for layer, item in (summary.get("layer_closure") or {}).items():
        entry = dict(item)
        entry["entries"] = len([obs for obs in scoped_core
                                if obs.get("layer") == layer])
        scoped_closure[layer] = entry
    summary["layer_closure"] = scoped_closure
    summary["core_entry_total"] = len(scoped_core)
    summary["checks_total"] = checks_total
    summary["audit_scope_note"] = (
        "本轮 summary 声明的条目数按收敛审核范围（排除已登记的隔离负向控制）如实改写")
    evaluated["summary.json"] = summary
    return evaluated


def _r7_frozen_view(scope: dict) -> dict:
    """按本轮统一规范（canonical + LF）冻结视图：长度/SHA/解析对象/条目数与唯一 ID 读数。"""
    view = {}
    for name, value in scope.items():
        buffer = canonical_bytes(value) + b"\n"
        record = {"byte_size": len(buffer), "file_sha256": sha_bytes(buffer),
                  "parsed": json.loads(buffer.decode("utf-8"))}
        record["entry_count"] = len(value)
        ids = (("case_id",) if name in ("calls.json", "core_observations.json")
               else (("name",) if name in ("checks.json", "failures.json") else ()))
        record["unique_ids"] = (len({entry.get(ids[0]) for entry in value})
                                if ids else len(value))
        view[name] = record
    return view


def _r7_audit_shas(scope: dict) -> dict:
    """审核读数：逐项长度/SHA（bytes 原样，其他对象按统一规范）。"""
    out = {}
    for name, value in scope.items():
        buffer = (bytes(value) if isinstance(value, (bytes, bytearray))
                  else canonical_bytes(value) + b"\n")
        out[name] = {"byte_size": len(buffer), "file_sha256": sha_bytes(buffer)}
    return out


def run_r5_entry(out_dir: Path, payloads: dict, fault: str | None = None,
                 fault_target: str = "checks.json") -> dict:
    """真正 --only r5 顶层末次收尾：一次写盘 → 真实末次审核 → 顶层判定。

    分界：本函数是**唯一**的对外成功判定处；早期阶段只产生真实观察与 B1 控制结果。
    写盘后不改任何已登记载荷字节（只另写报告/读回诊断）。真实末次审核与末次原始字节确认
    均在本轮根最终磁盘字节上执行，并共同支配 FAILURES、summary 与返回码。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    CALLS, SAMPLES = payloads["calls.json"], payloads["samples.json"]
    CHECKS, FAILURES = payloads["checks.json"], payloads["failures.json"]
    SUMMARY, CORE = payloads["summary.json"], payloads["core_observations.json"]
    fault = None if fault in (None, "", "none") else fault
    negative_controls = collect_negative_controls(payloads)
    checks_total = len(CHECKS)
    base_failures_count = len(FAILURES)
    injection = {"fault": fault, "target": fault_target if fault else None,
                 "scope": "受控测试注入，不代表核心天然发生该故障",
                 "observation_flags_rewritten": False,
                 "phase": "顶层末次收尾（写盘后真实末次审核边界）"}
    if fault == "ledger_readback_problem":
        injection.update({"hit_counter": 0, "target_hit": 1,
                          "boundary": "真实末次 audit_ledger 返回后受控映射（恰 1 次）"})
    if fault == "late_byte_after_final_read":
        injection.update({"hit_counter": 0, "target_hit": 1,
                          "boundary": "末次真实读取返回原值后追加 LF（恰 1 次）"})
    real_audit_ledger, real_content_audit = audit_ledger, content_audit_readback
    post_audit_failed = [item for item in POST_AUDITS if not item["ok"]]
    declared_holder = [False]

    def freeze_summary(status, failures_count, extra=None) -> dict:
        summary = dict(SUMMARY)
        summary["mode"] = "r5"
        summary["status"] = status
        summary["checks_total"] = checks_total
        summary["checks_failed"] = failures_count
        summary["payload_unique_ids"] = {
            name: {"entry_count": len(value),
                   "unique_ids": len({json.dumps(item, ensure_ascii=False, sort_keys=True)
                                      for item in value})}
            for name, value in (("calls.json", CALLS), ("checks.json", CHECKS),
                                ("failures.json", FAILURES),
                                ("core_observations.json", CORE))}
        if extra:
            summary.update(extra)
        return summary

    def build_ledger(writes_obj, view, declared, expect_shas) -> dict:
        return {"entries": view, "entry_count": len(view), "covered": sorted(writes_obj),
                "expectation_source": "本次真实观察（内存定稿→一次写入→同缓冲读回）",
                "mode": "r5", "expected_path_log": EXPECTED_PATH_LOG,
                "disk_audit": disk_audit, "pending_audit": disk_audit,
                "content_audit": {"ok": not expectation_compare["ok"],
                                  "problems": list(expectation_compare["problems"])},
                "expectation_compare": expectation_compare, "byte_drift": [],
                "injected_control": dict(injection),
                "final_audit_failed": declared,
                "negative_controls": negative_controls,
                "audit_scope": {
                    "scope": "全部登记载荷逐项读回；收敛审核排除本次已登记的隔离负向控制",
                    "excluded_negative_controls": sorted(negative_controls),
                    "evaluated_case_ids":
                        [entry.get("case_id") for entry in
                         evaluated_evidence(writes_obj,
                                            checks_total)["core_observations.json"]],
                    "registered_payload_entry_counts":
                        {name: len(value) for name, value in payloads.items()},
                    "evaluated_payload_entry_counts":
                        {name: len(value) for name, value in
                         evaluated_evidence(writes_obj, checks_total).items()}},
                "final_entry_basis": {
                    "note": "最终台账按最后写出的精确字节登记；写盘后不改任何已登记载荷",
                    "expectation_sha256": {name: item["file_sha256"]
                                           for name, item in expect_shas.items()},
                    "expectation_byte_size": {name: item["byte_size"]
                                              for name, item in expect_shas.items()},
                    "final_audit_scope":
                        "顶层末次审核与末次原始字节确认均在本轮根最终磁盘字节上执行"},
                "post_audits": list(POST_AUDITS)}

    def compile_payloads(declared: bool):
        """按结论定稿六个载荷 + 冻结视图 + 内容判据（写盘前后共用，同一确定字节）。"""
        if declared and not FAILURES:
            FAILURES.append({"name": "R7-R5-only-末次收尾审核失败",
                             "detail": json.dumps(
                                 {"stage": "写盘前定稿", "injected_control": injection},
                                 ensure_ascii=False)[:600]})
        writes = dict(payloads)
        writes["failures.json"] = FAILURES
        writes["summary.json"] = freeze_summary(
            "FAIL" if (declared or FAILURES) else "PASS", len(FAILURES),
            {"final_audit_failed": bool(declared) or bool(FAILURES),
             "post_write_failures_added": 0,
             "late_entry_audit": {"same_buffer": True,
                                  "ledger_audit_ok": None,
                                  "disk_confirmation_failed": [],
                                  "late_drift_after_final_read": [],
                                  "dominates_return_code": True}})
        view = _r7_frozen_view(writes)
        evaluated = evaluated_evidence(writes, checks_total)
        disk = evidence_audit(_r7_frozen_view(evaluated))
        compared = compare_expectation(
            json.loads(canonical_bytes(writes).decode("utf-8")), view)
        return writes, view, disk, compared

    def integrity_failed(disk, compared) -> bool:
        return ((not disk["ok"]) or (not compared["ok"])
                or bool(post_audit_failed))

    # ---- 1) 写盘前定稿：真实 helper 在同一确定字节上判定（失败登记先进入载荷）
    declared = False
    writes, view, disk_audit, expectation_compare = compile_payloads(declared)
    if integrity_failed(disk_audit, expectation_compare):
        declared = True
        writes, view, disk_audit, expectation_compare = compile_payloads(declared)

    # ---- 2) 一次写盘：六个已登记载荷 + 最终台账（写盘后不再改这些字节）
    final_payloads = dict(writes)
    expect_shas = _r7_audit_shas(final_payloads)
    for name, value in final_payloads.items():
        (out_dir / name).write_bytes(canonical_bytes(value) + b"\n")
    final_ledger = build_ledger(final_payloads, view, declared, expect_shas)
    ledger_buffer = canonical_bytes(final_ledger) + b"\n"
    (out_dir / "evidence_ledger.json").write_bytes(ledger_buffer)

    # ---- 3) 真实末次审核：在最终磁盘字节上实际调用 audit_ledger（故障一在此受控映射）
    declared_holder[0] = declared
    ledger_read = (out_dir / "evidence_ledger.json").read_bytes()
    same_buffer = ledger_read == ledger_buffer
    ledger_audit = dict(real_audit_ledger(
        json.loads(ledger_read.decode("utf-8")), view, negative_controls, declared))
    if fault == "ledger_readback_problem":
        injection["hit_counter"] += 1
        if injection["hit_counter"] == injection["target_hit"]:
            ledger_audit_real = {"ok": ledger_audit.get("ok"),
                                 "problems": list(ledger_audit.get("problems") or []),
                                 "entry_count": final_ledger["entry_count"],
                                 "covered": sorted(final_payloads),
                                 "note": "受控映射前真实 helper 的原始读数"}
            ledger_audit = dict(ledger_audit)
            ledger_audit["ok"] = False
            ledger_audit["problems"] = [
                "R7 受控映射：顶层末次台账读回审核被测试注入标记为非空问题"] + list(
                ledger_audit.get("problems") or [])
            ledger_audit["injected_control"] = True
            injection.update({"applied": True,
                              "applied_at_hit": injection["hit_counter"]})
        else:
            ledger_audit_real = dict(ledger_audit)
    else:
        ledger_audit_real = dict(ledger_audit)

    disk_confirmation = [disk_readback(name, view.get(name) or {}, out_dir / name)
                         for name in sorted(final_payloads)]
    disk_confirmation.append(disk_readback("evidence_ledger.json", {
        "byte_size": len(ledger_buffer), "file_sha256": sha_bytes(ledger_buffer)},
        out_dir / "evidence_ledger.json"))
    content_readback = real_content_audit(out_dir, final_payloads, view)

    # ---- 4) 末次必要消费后的字节变化（故障二：真实读取返回原值后恰一次追加 LF）
    if fault == "late_byte_after_final_read":
        injection["hit_counter"] += 1
        if injection["hit_counter"] == injection["target_hit"]:
            before = (out_dir / fault_target).read_bytes()
            (out_dir / fault_target).write_bytes(before + b"\n")
            injection.update({"applied": True,
                              "applied_at_hit": injection["hit_counter"],
                              "added": "LF", "byte_size_before": len(before),
                              "byte_size_after": len(before) + 1,
                              "sha256_before": sha_bytes(before),
                              "sha256_after": sha_bytes(before + b"\n"),
                              "note": "真实读取返回原值后才改变该字节；不同步任何哈希"})
    late_confirmation = {}
    for name, item in sorted(expect_shas.items()) + [
            ("evidence_ledger.json", {"byte_size": len(ledger_buffer),
                                      "file_sha256": sha_bytes(ledger_buffer)})]:
        data = (out_dir / name).read_bytes()
        late_confirmation[name] = {
            "expected_byte_size": item["byte_size"], "actual_byte_size": len(data),
            "expected_file_sha256": item["file_sha256"],
            "actual_file_sha256": sha_bytes(data),
            "ok": (len(data) == item["byte_size"]
                   and sha_bytes(data) == item["file_sha256"])}
    late_drift = [{"name": name, **{key: item[key] for key in
                                    ("expected_byte_size", "actual_byte_size",
                                     "expected_file_sha256", "actual_file_sha256")}}
                  for name, item in late_confirmation.items() if not item["ok"]]

    # ---- 5) 末次判据支配顶层结论与返回码（此后不再读取任何已核验候选文件）
    disk_failed = ((not disk_audit["ok"]) or (not expectation_compare["ok"])
                   or not same_buffer or ledger_audit.get("ok") is not True
                   or any(not item["ok"] for item in disk_confirmation)
                   or not content_readback["ok"] or bool(late_drift)
                   or bool(post_audit_failed))
    entry_failed = bool(declared) or disk_failed
    if entry_failed:
        already = any(item.get("name") == "R7-R5-only-末次收尾审核失败"
                      for item in FAILURES)
        if not already:
            FAILURES.append({"name": "R7-R5-only-末次收尾审核失败",
                             "detail": json.dumps(
                                 {"disk_audit_ok": disk_audit["ok"],
                                  "expectation_ok": expectation_compare["ok"],
                                  "same_buffer": same_buffer,
                                  "ledger_audit_ok": ledger_audit.get("ok"),
                                  "ledger_audit_problems":
                                      (ledger_audit.get("problems") or [])[:6],
                                  "disk_confirmation_failed":
                                      [item["name"] for item in disk_confirmation
                                       if not item["ok"]],
                                  "content_readback_problems":
                                      (content_readback.get("problems") or [])[:4],
                                  "late_drift_after_final_read": late_drift,
                                  "injected_control": injection},
                                 ensure_ascii=False)[:900]})
        buffer = canonical_bytes(FAILURES) + b"\n"
        (out_dir / "failures.json").write_bytes(buffer)
        # 失败元数据是协议允许的追加；台账条目与声明同步，坏候选保留
        view = dict(view)
        view["failures.json"] = {
            "byte_size": len(buffer), "file_sha256": sha_bytes(buffer),
            "parsed": json.loads(buffer.decode("utf-8")),
            "entry_count": len(FAILURES),
            "unique_ids": len({item.get("name") for item in FAILURES})}
        final_ledger = dict(final_ledger)
        final_ledger.update({"entries": view, "entry_count": len(view),
                             "covered": sorted(final_payloads),
                             "final_audit_failed": True})
        ledger_buffer = canonical_bytes(final_ledger) + b"\n"
        (out_dir / "evidence_ledger.json").write_bytes(ledger_buffer)
        status = "FAIL"
        result_summary = freeze_summary(status, len(FAILURES),
                                        {"final_audit_failed": True,
                                         "post_write_failures_added":
                                             len(FAILURES) - base_failures_count,
                                         "late_entry_audit": {
                                             "same_buffer": same_buffer,
                                             "ledger_audit_ok": ledger_audit.get("ok"),
                                             "disk_confirmation_failed":
                                                 [item["name"] for item in
                                                  disk_confirmation if not item["ok"]],
                                             "late_drift_after_final_read": late_drift,
                                             "dominates_return_code": True}})
        (out_dir / "summary.json").write_bytes(
            canonical_bytes(result_summary) + b"\n")
    else:
        status = "PASS"
        # 成功路径：summary 已在写盘前按同一末次审核块定稿并随六载荷一次写出，
        # 此处直接采用内存中的同一对象（不再读取候选文件）。
        result_summary = dict(final_payloads["summary.json"])
    readback_payload = {
        "same_buffer": same_buffer,
        "ledger_audit_ok": ledger_audit.get("ok"),
        "readback_audit": ledger_audit,
        "readback_audit_real_helper": ledger_audit_real,
        "final_disk_confirmation": disk_confirmation,
        "content_audit_readback": content_readback,
        "late_byte_confirmation": late_confirmation,
        "late_drift_after_final_read": late_drift,
        "byte_drift": [],
        "post_audits": POST_AUDITS,
        "post_audit_failed": [item["name"] for item in post_audit_failed],
        "negative_controls": negative_controls,
        "injected_control": injection,
        "expectation_sha256": {name: item["file_sha256"]
                               for name, item in expect_shas.items()},
        "dominance": {"disk_audit_ok": disk_audit["ok"],
                      "expectation_compare_ok": expectation_compare["ok"],
                      "same_buffer": same_buffer,
                      "ledger_audit_ok": ledger_audit.get("ok"),
                      "late_drift_count": len(late_drift),
                      "declared_failed_before_write": bool(declared),
                      "top_level_failed": entry_failed,
                      "exit_code_if_failed": 1},
        "counts": {"checks_total": len(CHECKS), "checks_failed": len(FAILURES),
                   "calls": len(CALLS), "samples": len(SAMPLES),
                   "core_observations": len(CORE)}}
    (out_dir / "ledger_readback.json").write_bytes(
        canonical_bytes(readback_payload) + b"\n")
    if entry_failed:
        (out_dir / "final_audit_diagnostic.json").write_bytes(canonical_bytes(
            {"detected": {"disk_audit": disk_audit,
                          "late_drift_after_final_read": late_drift,
                          "readback_problems":
                              (ledger_audit.get("problems") or [])[:8],
                          "injected_control": injection},
             "dominates_exit_code": True}) + b"\n")
    return {"out_dir": _project_rel(out_dir), "mode": "r5", "fault": fault,
            "injected_control": injection, "exit_code": 1 if entry_failed else 0,
            "summary_status": status, "failures": len(FAILURES),
            "checks_total": len(CHECKS), "entry_failed": entry_failed,
            "declared_failed_before_write": bool(declared),
            "disk_audit_ok": disk_audit["ok"],
            "expectation_compare_ok": expectation_compare["ok"],
            "same_buffer": same_buffer, "ledger_audit_ok": ledger_audit.get("ok"),
            "ledger_audit_real_helper_ok": ledger_audit_real.get("ok"),
            "final_disk_confirmation": disk_confirmation,
            "content_audit_readback_ok": content_readback["ok"],
            "late_confirmation": late_confirmation,
            "late_drift_after_final_read": late_drift, "byte_drift": [],
            "negative_controls": negative_controls,
            "expectation_sha256": {name: item["file_sha256"]
                                   for name, item in expect_shas.items()},
            "frozen_payload_byte_sizes": {name: item["byte_size"]
                                          for name, item in expect_shas.items()},
            "frozen_payload_sha256": {name: item["file_sha256"]
                                      for name, item in expect_shas.items()},
            "result_summary": result_summary,
            "ledger_byte_size": len(ledger_buffer),
            "ledger_sha256": sha_bytes(ledger_buffer)}



def clean_payloads(payloads: dict) -> dict:
    """载荷快照：每个末次收尾运行都用独立副本，避免副本之间互相污染失败登记。"""
    return {name: (json.loads(json.dumps(value, ensure_ascii=False))
                   if isinstance(value, (list, dict)) else value)
            for name, value in payloads.items()}






def register_r5_closure_checks(checks: list, names) -> None:
    """预登记本轮定点收尾三项检查（真实结果在收尾后写回），使载荷计数与实际检查数一致。

    预登记条目的 ok 记为字符串 `pending:closure-check`：既不是通过，也不是失败，
    直到真实收尾判定写回布尔值（不留下任何"看起来已通过"或"看起来已失败"的占位）。
    """
    for name in names:
        checks.append({"name": name, "ok": "pending:closure-check",
                       "detail": "收尾判定执行中（真实结果写回同一登记条目）"})


def finalize_r5_closure_checks(checks: list, results) -> None:
    """把真实收尾判定写回预登记条目（不新增、不删除登记条目）。"""
    by_name = {}
    for item in results:
        by_name[item["name"]] = item
    for entry in checks:
        item = by_name.get(entry.get("name"))
        if item is not None:
            entry["ok"] = bool(item["ok"])
            entry["detail"] = str(item["detail"])


def build_r5_round_summary(out_dir: Path, batch_root: Path,
                           checks_total_for_closure: int, registered_checks: list):
    """早期阶段：真实接收/真实 prepare 观察 + B1 窗口控制。**不产出任何成功结论**。"""
    round_name = out_dir.name
    print(f"R5 定点轮次：{round_name}")
    module = load_adapter()
    counters = {"store_save": 0, "store_verify": 0, "p1_seam": 0, "p1_entry": 0}
    live_store, observer = install_observation(module, counters)
    fixture1 = doc_fixture()
    samples = build_samples(batch_root)
    batch_a = batch_root / "C06b_normal"
    batch_b = batch_root / "C06b_normal_b"
    points = R1Points({"module": module, "round_name": round_name, "batch_a": batch_a,
                       "batch_b": batch_b, "batch_root": batch_root,
                       "records_root": RECORDS_ROOT,
                       "fixtures": (fixture1, hold_fixture()),
                       "check": check, "sha_bytes": sha_bytes,
                       "canonical_bytes": canonical_bytes,
                       "submission_for": submission_for, "call": call})
    points.run_r5_window_controls()
    observer.stop()
    observations = observer.payload()
    summary = {"mode": "r5", "round": round_name,
               "counts": {"prepare_calls": len([item for item in CALLS
                                                if item.get("call") == "prepare"]),
                          "save_calls": len([item for item in CALLS
                                             if item.get("call") == "save"]),
                          "verify_calls": len([item for item in CALLS
                                               if item.get("call") == "verify"]),
                          "receiver_runs": len(SAMPLES),
                          "store_save_calls": counters["store_save"],
                          "store_verify_calls": counters["store_verify"],
                          "p1_entry": counters.get("p1_entry"),
                          "p1_seam": counters.get("p1_seam")},
               "entry_observations": observations,
               "core_entry_total": len(CORE_OBSERVATIONS),
               "layer_closure": {
                   layer: {"entries": len([item for item in CORE_OBSERVATIONS
                                           if item.get("layer") == layer]),
                           "frames_trace": sum(
                               count for key, count in
                               observations.get("trace_counts", {}).items()
                               if key.endswith(f"::{LAYER_FUNCTIONS[layer]}")),
                           "unique_ids": len({item.get("case_id")
                                              for item in CORE_OBSERVATIONS
                                              if item.get("layer") == layer}),
                           "source": "本模式实际观察（真实入口 trace 计数 + 核心登记条目）"}
                   for layer in sorted({item.get("layer") for item in CORE_OBSERVATIONS})},
               "negative_control_entry_ids": sorted(
                   entry.get("case_id") for entry in CORE_OBSERVATIONS
                   if (entry.get("negative_control") or {}).get("kind")
                   in ("unregistered_late_change", "extra_target_in_window")),
               "expected_path_log": EXPECTED_PATH_LOG,
               "not_executed": {"host_or_controller": None, "normalization_or_db": None,
                                "gate2": None, "real_initial_judgment": None,
                                "ai_or_final_judgment": None,
                                "cross_scope_history_discovery": None,
                                "direct_checker_cli": 0, "new_junction": None},
               "boundaries": {"execution_allowed": False, "workflow_connected": False,
                              "human_initial_judgment_saved": False, "ai_enabled": False,
                              "identity_authenticated": False,
                              "source_authenticity_proven": False}}
    summary["core_entry_total"] = len(CORE_OBSERVATIONS)
    summary["checks_total"] = len(registered_checks)
    payloads = {"calls.json": CALLS, "samples.json": SAMPLES,
                "checks.json": registered_checks, "failures.json": FAILURES,
                "summary.json": summary, "core_observations.json": CORE_OBSERVATIONS}
    return summary, payloads



def run_r5_only(out_dir: Path) -> int:
    """--only r5 顶层入口：早期真实观察 + 一次正式末次收尾 + 两个控制故障副本。

    - 最外层返回码直接消费**实际最终正常根的 verdict**（不再只看全局 FAILURES）；
      两个故障副本的 1/FAIL 是控制证据，不能代替最外层判定，也不会把正常套件一律判失败。
    - 每个根（正式正常根与两个故障副本）的六载荷与台账各只写一次：不再有前置干跑写盘。
    """
    global SUITE_OUT_DIR
    SUITE_OUT_DIR = out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    round_name = out_dir.name
    batch_root = PROJECT_ROOT / "data" / "batches" / round_name
    R5_CONTROL_LOG.clear()
    control_names = [
        "R8-B 控制：顶层末次台账读回审核受控失败必须支配该副本 FAIL/非空 failures/返回 1",
        "R8-C 控制：末次必要消费后字节变化（追加 LF）必须支配该副本 FAIL/非空 failures/返回 1"]
    register_r5_closure_checks(CHECKS, control_names)
    observation, payloads = build_r5_round_summary(out_dir, batch_root, len(CHECKS),
                                                   CHECKS)
    payloads["checks.json"] = CHECKS
    payloads["failures.json"] = FAILURES
    payloads["summary.json"] = observation

    # ---- 两个控制故障副本（各自独立新根；复用同一真实观察，只改注入）
    fault_roots = {
        "ledger_readback_problem": out_dir / "entry_fault_1_ledger_readback",
        "late_byte_after_final_read":
            out_dir / "entry_fault_2_late_byte_after_final_read",
    }
    verdicts = {}
    for label, target in fault_roots.items():
        verdicts[label] = run_r5_entry(target, clean_payloads(payloads), fault=label)
    control_flags = {
        "fault_1_dominates": (
            verdicts["ledger_readback_problem"]["exit_code"] == 1
            and verdicts["ledger_readback_problem"]["summary_status"] == "FAIL"
            and verdicts["ledger_readback_problem"]["failures"] > 0
            and verdicts["ledger_readback_problem"]["ledger_audit_ok"] is False
            and verdicts["ledger_readback_problem"]["injected_control"].get("applied")
                is True
            and verdicts["ledger_readback_problem"]["injected_control"]
                .get("hit_counter") == 1),
        "fault_2_dominates": (
            verdicts["late_byte_after_final_read"]["exit_code"] == 1
            and verdicts["late_byte_after_final_read"]["summary_status"] == "FAIL"
            and verdicts["late_byte_after_final_read"]["failures"] > 0
            and bool(verdicts["late_byte_after_final_read"]
                     ["late_drift_after_final_read"])
            and verdicts["late_byte_after_final_read"]["injected_control"].get("applied")
                is True
            and verdicts["late_byte_after_final_read"]["injected_control"]
                .get("hit_counter") == 1)}

    def detail_for(verdict):
        return json.dumps(
            {key: verdict.get(key) for key in
             ("exit_code", "summary_status", "failures", "same_buffer",
              "ledger_audit_ok", "ledger_audit_real_helper_ok", "disk_audit_ok",
              "expectation_compare_ok", "late_drift_after_final_read",
              "declared_failed_before_write", "injected_control")},
            ensure_ascii=False)[:600]

    control_results = [
        {"name": control_names[0], "ok": control_flags["fault_1_dominates"],
         "detail": detail_for(verdicts["ledger_readback_problem"])},
        {"name": control_names[1], "ok": control_flags["fault_2_dominates"],
         "detail": detail_for(verdicts["late_byte_after_final_read"])}]
    finalize_r5_closure_checks(CHECKS, control_results)

    # ---- 正式正常根：六载荷与台账**只写一次**；控制失败登记先进入载荷
    normal_payloads = clean_payloads(payloads)
    for item in normal_payloads["checks.json"]:
        if item.get("ok") is False and item not in normal_payloads["failures.json"]:
            normal_payloads["failures.json"].append(item)
    normal = run_r5_entry(fault_roots.get("normal", out_dir), normal_payloads)
    verdicts["normal"] = normal

    # ---- 最外层：直接消费实际最终正常根 verdict + 本轮控制结果
    normal_clean = (normal["exit_code"] == 0 and normal["summary_status"] == "PASS"
                    and normal["entry_failed"] is False
                    and normal["same_buffer"] is True
                    and normal["ledger_audit_ok"] is True
                    and all(item["ok"] for item in normal["final_disk_confirmation"])
                    and all(item["ok"] for item in normal["late_confirmation"].values()))
    # 正式正常根自报成功时，最外层再做**一次**有界原始字节再确认：
    # 六载荷预期取自写前声明，台账预期取自本次 writer 的已绑定缓冲；
    # 不从候选磁盘重建预期，不一致即拒绝返回成功。
    # （自报失败时，失败元数据属协议允许的写入，改由该 verdict 支配。）
    outer_byte_confirmation = []
    outer_byte_drift = []
    if normal_clean:
        outer_declared = dict(normal["expectation_sha256"])
        outer_sizes = dict(normal["frozen_payload_byte_sizes"])
        outer_declared["evidence_ledger.json"] = normal["ledger_sha256"]
        outer_sizes["evidence_ledger.json"] = normal["ledger_byte_size"]
        for name in sorted(outer_declared):
            data = (out_dir / name).read_bytes()
            actual_sha = sha_bytes(data)
            item = {"name": name,
                    "declared_byte_size": outer_sizes.get(name),
                    "actual_byte_size": len(data),
                    "declared_file_sha256": outer_declared[name],
                    "actual_file_sha256": actual_sha,
                    "ok": (len(data) == outer_sizes.get(name)
                           and actual_sha == outer_declared[name])}
            outer_byte_confirmation.append(item)
            if not item["ok"]:
                outer_byte_drift.append(item)
        if outer_byte_drift:
            for item in outer_byte_drift:
                FAILURES.append({"name": "R8-最外层末次字节确认失败：" + item["name"],
                                 "detail": json.dumps(
                                     {"stage": "正式正常根的最外层有界字节再确认",
                                      "declared_byte_size": item["declared_byte_size"],
                                      "actual_byte_size": item["actual_byte_size"],
                                      "declared_file_sha256":
                                          item["declared_file_sha256"],
                                      "actual_file_sha256":
                                          item["actual_file_sha256"],
                                      "note": "该字节与写前声明不一致：拒绝返回成功"},
                                     ensure_ascii=False)[:600]})
            # 失败分支仅写失败元数据。保留坏候选与原台账，不重新读取可能损坏
            # 的 summary，也不通过重建台账消除刚刚检出的漂移。
            outer_summary = dict(normal["result_summary"])
            outer_summary["status"] = "FAIL"
            outer_summary["checks_failed"] = len(FAILURES)
            outer_summary["outer_byte_confirmation_failed"] = [
                item["name"] for item in outer_byte_drift]
            (out_dir / "failures.json").write_bytes(
                canonical_bytes(FAILURES) + b"\n")
            (out_dir / "summary.json").write_bytes(
                canonical_bytes(outer_summary) + b"\n")
            (out_dir / "outer_failure_diagnostic.json").write_bytes(canonical_bytes(
                {"outer_byte_confirmation": outer_byte_confirmation,
                 "outer_byte_drift": outer_byte_drift,
                 "dominates_return_code": True}) + b"\n")
    controls_ok = all(control_flags.values())
    outer_clean = not outer_byte_drift
    exit_code = 0 if (normal_clean and controls_ok and outer_clean) else 1
    (out_dir / "r8_entry_checks.json").write_bytes(canonical_bytes(
        {"purpose": "TASK-024-R8：最外层直接消费实际最终正常根 verdict（一次正式写盘、无前置写盘）",
         "outer_returns": {"normal_clean": normal_clean,
                           "controls_ok": controls_ok,
                           "outer_byte_confirmation_clean": outer_clean,
                           "exit_code": exit_code},
         "outer_byte_confirmation": outer_byte_confirmation,
         "outer_byte_drift": outer_byte_drift,
         "control_checks": control_results,
         "control_flags": control_flags,
         "actual_normal_verdict": detail_for(normal),
         "declared_control_checks_in_payload": control_names,
         "note": ("正常根末次实际结论与三个 R7 旧控制的单列证据：本轮载荷内只登记两个控制副本的"
                  "真实结论；正常根结论由本文件与根 summary/failures 如实分列，不再为自指改写载荷"),
         "verdicts": {label: {key: value for key, value in verdict.items()
                              if key in ("out_dir", "fault", "exit_code",
                                         "summary_status", "failures", "entry_failed",
                                         "declared_failed_before_write",
                                         "disk_audit_ok", "expectation_compare_ok",
                                         "same_buffer", "ledger_audit_ok",
                                         "ledger_audit_real_helper_ok",
                                         "late_drift_after_final_read", "byte_drift",
                                         "content_audit_readback_ok",
                                         "expectation_sha256",
                                         "frozen_payload_byte_sizes",
                                         "frozen_payload_sha256", "negative_controls",
                                         "injected_control")}
                      for label, verdict in verdicts.items()},
         "window_controls": R5_CONTROL_LOG}) + b"\n")
    print(f"R5 定点模式：{len(CHECKS)} 项检查、{len(FAILURES)} 项失败；"
          f"prepare {observation['counts']['prepare_calls']}、"
          f"save {observation['counts']['save_calls']}、"
          f"verify {observation['counts']['verify_calls']}；核心观察 "
          f"{len(CORE_OBSERVATIONS)}；窗口登记 {len(EXPECTED_PATH_LOG)} 条；"
          f"最终正常根 {normal['exit_code']}/{normal['summary_status']}"
          f"（外层 exit {exit_code}，控制 fault_1={control_flags['fault_1_dominates']}"
          f" fault_2={control_flags['fault_2_dominates']}）")
    return exit_code

def scope_for(round_name: str, scenario: str) -> Path:
    scope = RECORDS_ROOT / f"{round_name}_{scenario}"
    scope.mkdir(parents=True, exist_ok=True)
    return scope


class Guard:
    """真实 I/O 通道守卫：统计写入路径、网络与子进程尝试（不改行为、不吞异常）。"""

    def __init__(self, allowed_prefixes, label):
        self.allowed = tuple(Path(prefix).resolve() for prefix in allowed_prefixes)
        self.label = label
        self.write_paths, self.forbidden = [], []
        self.original = {}

    def _allowed(self, path):
        if not isinstance(path, (str, os.PathLike)):
            # 文件描述符形式（例如 os.fdopen(handle, "wb")）：不是路径，按允许处理
            return True
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError):
            return False
        return any(str(resolved).startswith(str(prefix)) for prefix in self.allowed)

    def _wrap_open(self, original):
        def wrapper(file, mode="r", *args, **kwargs):
            if (isinstance(mode, str) and any(flag in mode for flag in "wax+")
                    and isinstance(file, (str, os.PathLike))):
                if self._allowed(file):
                    self.write_paths.append(str(file))
                else:
                    self.forbidden.append({"op": "write_outside_scope", "path": str(file)})
            return original(file, mode, *args, **kwargs)
        return wrapper

    def install(self):
        import builtins
        import io as io_module
        import socket
        self.original["io.open"] = io_module.open
        io_module.open = self._wrap_open(io_module.open)
        self.original["builtins.open"] = builtins.open
        builtins.open = self._wrap_open(builtins.open)
        self.original["os.open"] = os.open

        def os_open(path, flags, *args, **kwargs):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND):
                if not isinstance(path, (str, os.PathLike)):
                    pass
                elif self._allowed(path):
                    self.write_paths.append(str(path))
                else:
                    self.forbidden.append({"op": "os_open_write_outside_scope",
                                           "path": str(path)})
            return self.original["os.open"](path, flags, *args, **kwargs)

        os.open = os_open
        self.original["socket.socket"] = socket.socket

        def socket_factory(*args, **kwargs):
            self.forbidden.append({"op": "network"})
            return self.original["socket.socket"](*args, **kwargs)

        socket.socket = socket_factory
        self.original["subprocess.Popen"] = subprocess.Popen

        def popen_factory(*args, **kwargs):
            self.forbidden.append({"op": "subprocess"})
            return self.original["subprocess.Popen"](*args, **kwargs)

        subprocess.Popen = popen_factory

    def uninstall(self):
        import builtins
        import io as io_module
        import socket
        io_module.open = self.original["io.open"]
        builtins.open = self.original["builtins.open"]
        os.open = self.original["os.open"]
        socket.socket = self.original["socket.socket"]
        subprocess.Popen = self.original["subprocess.Popen"]

    def payload(self):
        return {"label": self.label,
                "write_paths_inside_scope": self.write_paths,
                "write_ops_outside_scope": [item for item in self.forbidden
                                            if item["op"].startswith("os_open_write")
                                            or item["op"] == "write_outside_scope"],
                "network_or_subprocess": [item for item in self.forbidden
                                          if item["op"] in ("network", "subprocess")]}


def save_call(module, case_id, batch, request_id, submission, event_dir, scope):
    return call(module, case_id, call="save", _function=module.save_human_gate1_decision,
                batch_dir=batch, request_id=request_id, submission=submission,
                event_dir=event_dir, scope_dir=scope)


def verify_call(module, case_id, event_dir, batch, scope):
    return call(module, case_id, call="verify",
                _function=module.verify_human_gate1_decision, event_dir=event_dir,
                batch_dir=batch, scope_dir=scope)


def prepare_call(module, case_id, batch, request_id):
    return call(module, case_id, call="prepare",
                _function=module.prepare_human_gate1_decision_request,
                batch_dir=batch, request_id=request_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--only", default=None,
                        help="定点模式：r5 只跑豁免窗口控制与其证据收尾")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    if args.only == "r5":
        return run_r5_only(out_dir)
    return run_suite_main(out_dir)


def install_observation(module, counters):
    """安装真实观察器与公开 API 包装（主入口与 --only r5 共用）。返回 (live_store, observer)。"""
    global ACTIVE_OBSERVER

    def _install_prepare(module_obj):
        original = getattr(module_obj, "prepare_human_gate1_request", None)
        if original is None or getattr(original, "_r2_observed", False):
            return module_obj
        def observed(*args, **kwargs):
            return observe_core("frozen_prepare", f"core-prepare::{next(CALL_INDEX)}",
                                original, *args, **kwargs)
        observed._r2_observed = True
        module_obj.prepare_human_gate1_request = observed
        OBSERVED["frozen_prepare"] = original
        return module_obj

    SELF_FILE = "test_record_demo_human_gate1.py"

    def _install_store(store_obj):
        for attr, layer in (("save_human_gate_decision_snapshots", "store_save"),
                            ("verify_human_gate_decision_snapshots", "store_verify")):
            current = getattr(store_obj, attr, None)
            current_code = getattr(current, "__code__", None)
            if current_code is not None and \
                    Path(current_code.co_filename).name == EntryObserver.SELF_FILE:
                continue  # 测试注入 wrapper 保留在调用链上（其内层仍由本套件观察）
            original = OBSERVED.get(layer) or current   # 首次安装时绑定到的真实函数
            if original is None or getattr(original, "_r2_observed", False):
                continue
            if OBSERVED.get(layer) is None:
                OBSERVED[layer] = original
            if current is not None and current is not original \
                    and getattr(current, "_r2_observed", False):
                continue  # 已由本套件包装且内层为真实函数
            def make(layer_name, inner):
                def observed(*args, **kwargs):
                    if layer_name == "store_save":
                        counters["store_save"] += 1
                    else:
                        counters["store_verify"] += 1
                    return observe_core(layer_name, f"core-{layer_name}::{next(CALL_INDEX)}",
                                        inner, *args, **kwargs)
                observed._r2_observed = True
                return observed
            setattr(store_obj, attr, make(layer, original))
            OBSERVED[layer] = original
        core_loader = getattr(store_obj, "load_frozen_p1_core", None)
        p1_module = core_loader() if callable(core_loader) else None
        p1_function = getattr(p1_module, "build_human_gate_decision_record", None)
        if p1_function is not None and not getattr(p1_function, "_r2_observed", False):
            def observed_p1(*args, **kwargs):
                counters["p1_entry"] += 1
                return observe_core("real_p1", f"core-p1::{next(CALL_INDEX)}",
                                    p1_function, *args, **kwargs)
            observed_p1._r2_observed = True
            p1_module.build_human_gate_decision_record = observed_p1
            OBSERVED["real_p1"] = p1_function
        seam = getattr(store_obj, "_call_p1_once", None)
        if seam is not None and not getattr(seam, "_r2_observed", False):
            def observed_seam(*args, **kwargs):
                counters["p1_seam"] += 1
                return observe_core("real_p1_seam", f"core-p1seam::{next(CALL_INDEX)}",
                                    seam, *args, **kwargs)
            observed_seam._r2_observed = True
            store_obj._call_p1_once = observed_seam
            OBSERVED["real_p1_seam"] = seam
        return store_obj

    counters["p1_seam"] = 0
    counters["p1_entry"] = 0
    original_load_prepare = module.load_frozen_prepare
    original_load_store = module.load_frozen_store

    def loading_prepare(*args, **kwargs):
        return _install_prepare(original_load_prepare(*args, **kwargs))

    def loading_store(*args, **kwargs):
        return _install_store(original_load_store(*args, **kwargs))

    def install_public_api(name_):
        original = getattr(module, name_, None)
        if original is None or getattr(original, "_r3_api", False):
            return
        def wrapped(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            finally:
                finalize_api_time_point()
        wrapped._r3_api = True
        setattr(module, name_, wrapped)
        OBSERVED[f"api:{name_}"] = original

    for api_name in ("prepare_human_gate1_decision_request", "save_human_gate1_decision",
                     "verify_human_gate1_decision"):
        install_public_api(api_name)
    module.load_frozen_prepare = loading_prepare
    module.load_frozen_store = loading_store
    loading_prepare()
    live_store = loading_store()
    observer = EntryObserver()
    observer.start()
    global ACTIVE_OBSERVER
    ACTIVE_OBSERVER = observer
    return live_store, observer


def run_suite_main(out_dir: Path) -> int:
    global SUITE_OUT_DIR
    SUITE_OUT_DIR = out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    round_name = out_dir.name
    batch_root = PROJECT_ROOT / "data" / "batches" / round_name

    module = load_adapter()
    store = load_store()
    counters = {"store_save": 0, "store_verify": 0}
    live_store = module.load_frozen_store()
    frozen_save = live_store.save_human_gate_decision_snapshots
    frozen_verify = live_store.verify_human_gate_decision_snapshots

    live_store, observer = install_observation(module, counters)


    fixture1 = doc_fixture()
    fixture2 = hold_fixture()
    samples = build_samples(batch_root)
    batch_a = batch_root / "C06b_normal"
    batch_b = batch_root / "C06b_normal_b"
    batch_usd = batch_root / "C06b_currency_usd"

    # ---------------------------------------------------------------- S1 prepare
    p1 = prepare_call(module, "P1-prepare-A", batch_a, "FIXTURE-REQ-G1-0001")
    p1b = prepare_call(module, "P1b-prepare-A-repeat", batch_a, "FIXTURE-REQ-G1-0001")
    request = p1.get("result") or {}
    check("S1.1 prepare 恰六键且版本/状态为新层常量",
          p1["outcome"] == "returned"
          and sorted(request) == ["boundaries", "evidence", "expectations", "materials",
                                  "request_version", "status"]
          and request["request_version"] == module.REQUEST_VERSION
          and request["status"] == module.STATUS_REQUEST_PREPARED,
          json.dumps(p1.get("result", p1), ensure_ascii=False)[:200])
    files = request.get("materials", {}).get("files", [])
    entries = request.get("evidence", {}).get("code_manifest", {}).get("entries", [])
    check("S1.2 新层绑定 32 项材料 / 14 项代码且 code.file_sha256 为本适配器字节",
          len(files) == 32 and len(entries) == 14
          and request["materials"]["run_binding"]["code"]["file_sha256"]
          == sha_bytes(ADAPTER_PATH.read_bytes())
          and request["materials"]["run_binding"]["code"]["manifest_fingerprint"]
          == request["evidence"]["code_manifest"]["manifest_fingerprint"],
          f"files={len(files)} code={len(entries)}")
    core = store.load_frozen_p1_core()
    recomputed = core.fingerprint(core.materials_body(
        {key: value for key, value in request["materials"].items()
         if key != "materials_fingerprint"}))
    check("S1.3 材料指纹独立复算一致（冻结 P1 公开算法）",
          recomputed == request["materials"]["materials_fingerprint"],
          f"{recomputed[:16]} vs {request['materials']['materials_fingerprint'][:16]}")
    check("S1.4 八键期望由本次读数重建且与 32 项材料一一对应",
          sorted(request["expectations"]) == ["expected_batch_id", "expected_contract",
                                              "expected_files", "expected_gate",
                                              "expected_materials_fingerprint",
                                              "expected_prior_gate1", "expected_request_id",
                                              "expected_run_binding"]
          and len(request["expectations"]["expected_files"]) == 32
          and request["expectations"]["expected_materials_fingerprint"]
          == request["materials"]["materials_fingerprint"]
          and request["expectations"]["expected_prior_gate1"] is None,
          json.dumps(request["expectations"].get("expected_files", {}), ensure_ascii=False)[:120])
    check("S1.5 相同纯 prepare 输入确定性（canonical 字节相等）且无 submission 痕迹",
          p1b["outcome"] == "returned"
          and canonical_bytes(p1b["result"]) == canonical_bytes(request)
          and not any("submission" in key for key in request),
          "deterministic")
    ub = request.get("boundaries", {})
    check("S1.6 准备请求边界为冻结原七项严格 false",
          sorted(ub) == sorted(module.REQUEST_BOUNDARY_KEYS)
          and all(value is False for value in ub.values()),
          json.dumps(ub, ensure_ascii=False)[:160])

    # ---------------------------------------------------------------- S2 真 save + verify
    scope1 = scope_for(round_name, "s1")
    sub_a = submission_for(module, batch_a, "FIXTURE-REQ-G1-0001", fixture1)
    guard_save = Guard([scope1], "S2-save+verify")
    source_shas_before = {name: sha_bytes((batch_a / name).read_bytes())
                          for name in ("checks/quality_report.json", "source/input.xlsx",
                                       "batch_manifest.json")}
    guard_save.install()
    try:
        saved_a = save_call(module, "S2-save-A-APPROVE", batch_a, "FIXTURE-REQ-G1-0001", sub_a,
                            scope1 / "event_0001", scope1)
        verified_a = verify_call(module, "S2-verify-A", scope1 / "event_0001", batch_a, scope1)
    finally:
        guard_save.uninstall()
    result_a = saved_a.get("result") or {}
    check("S2.1 save 恰九键且 RECORDED / scope / boundaries 六项 false",
          saved_a["outcome"] == "returned"
          and sorted(result_a) == sorted(module.RESULT_KEYS)
          and result_a["status"] == module.STATUS_RECORDED
          and result_a["scope"] == module.SCOPE
          and sorted(result_a["identity"]) == ["batch_id", "decision", "event_id"]
          and result_a["store_result"]["status"] == store.STORE_STATUS_STORED
          and all(value is False for value in result_a["boundaries"].values()),
          json.dumps(saved_a.get("result", saved_a), ensure_ascii=False)[:260])
    event1 = scope1 / "event_0001"
    context1 = json.loads((event1 / "context.json").read_text(encoding="utf-8"))
    receipt1 = json.loads((event1 / "receipt.json").read_text(encoding="utf-8"))
    check("S2.2 封套：context 恰九键 / receipt 恰十键 / 快照恰冻结六文件 / scope 仅含本事件",
          len(context1) == 9 and len(receipt1) == 10
          and sorted(p.name for p in (event1 / "snapshots").iterdir())
          == sorted(module.SNAPSHOT_FILES)
          and sorted(p.name for p in scope1.iterdir()) == ["event_0001"]
          and context1["revision"] == 1
          and sorted(context1["prior_scope"]) == sorted(module.PRIOR_SCOPE_KEYS)
          and context1["prior_scope"]["prior_events"] == []
          and len(context1["snapshot_files"]) == 6,
          f"context={len(context1)} receipt={len(receipt1)}")
    verified_result = verified_a.get("result") or {}
    guard_payload = guard_save.payload()
    check("S2.3 verify 恰九键且 VERIFIED / 与 save 的记录指纹一致 / 无锁残留",
          verified_a["outcome"] == "returned"
          and sorted(verified_result) == sorted(module.RESULT_KEYS)
          and verified_result["status"] == module.STATUS_VERIFIED
          and verified_result["store_result"]["status"] == store.STORE_STATUS_VERIFIED
          and verified_result["record_fingerprint"] == result_a["record_fingerprint"]
          and not (scope1 / ".gate1.lock").exists(),
          json.dumps(verified_a.get("result", verified_a), ensure_ascii=False)[:240])
    guard_write_paths = [Path(path).resolve() for path in guard_payload["write_paths_inside_scope"]]
    guard_scope_paths = [path for path in guard_write_paths
                         if str(path).startswith(str(scope1.resolve()))]
    check("S2.4 守卫：网络/子进程 0、scope 外无写、生产源只读、写入仅限本 scope",
          not guard_payload["network_or_subprocess"]
          and not guard_payload["write_ops_outside_scope"]
          and len(guard_scope_paths) == len(guard_write_paths)
          and len(guard_write_paths) >= 9
          and {name: sha_bytes((batch_a / name).read_bytes())
               for name in source_shas_before} == source_shas_before,
          json.dumps({**guard_payload, "write_count": len(guard_write_paths),
                      "scope_writes": len(guard_scope_paths)}, ensure_ascii=False)[:300])

    # ---------------------------------------------------------------- S3 revision 2 追加
    sub_b = submission_for(module, batch_b, "FIXTURE-REQ-G1-0002", fixture2)
    saved_b = save_call(module, "S3-save-B-HOLD", batch_b, "FIXTURE-REQ-G1-0002", sub_b,
                        scope1 / "event_0002", scope1)
    context2 = json.loads((scope1 / "event_0002" / "context.json").read_text(encoding="utf-8"))
    history2 = json.loads((scope1 / "event_0002" / "snapshots" / "prior_history.json")
                          .read_text(encoding="utf-8"))
    check("S3.1 同 scope 追加为 revision 2 且先前事件被完整引用",
          saved_b["outcome"] == "returned" and context2["revision"] == 2
          and len(context2["prior_scope"]["prior_events"]) == 1
          and sorted(context2["prior_scope"]["prior_events"][0])
          == sorted(module.PRIOR_EVENT_KEYS)
          and context2["prior_scope"]["prior_events"][0]["event_relative"] == "event_0001"
          and len(context2["prior_scope"]["prior_events"][0]["snapshot_files"]) == 6,
          json.dumps(context2["prior_scope"]["prior_events"], ensure_ascii=False)[:260])
    check("S3.2 prior_history 完整 wrapper 与指纹闭合",
          history2["declared_complete"] is True
          and history2["declared_scope"].startswith(module.LOCAL_SCOPE_PREFIX)
          and len(history2["records"]) == 1
          and sorted(history2["records"][0]) == ["record", "record_fingerprint",
                                                 "wrapper_version"]
          and history2["records"][0]["record"]["event_id"] == fixture1["event_id"]
          and context2["prior_scope"]["prior_history_fingerprint"]
          == fingerprint(history2),
          json.dumps(history2["records"][0]["record_fingerprint"], ensure_ascii=False)[:80])
    verified_b = verify_call(module, "S3-verify-B", scope1 / "event_0002", batch_b, scope1)
    check("S3.3 两个事件均可只读核验（VERIFIED）",
          verified_b["outcome"] == "returned"
          and verified_b["result"]["status"] == module.STATUS_VERIFIED
          and verified_b["result"]["identity"]["decision"] == "HOLD",
          json.dumps(verified_b.get("result", verified_b), ensure_ascii=False)[:200])

    # ---------------------------------------------------------------- S4 HOLD 后追加 APPROVE
    scope2 = scope_for(round_name, "s2")
    sub_hold_b = submission_for(module, batch_b, "FIXTURE-REQ-G1-0002", fixture2)
    first_hold = save_call(module, "S4-save-B-HOLD", batch_b, "FIXTURE-REQ-G1-0002",
                           sub_hold_b, scope2 / "event_0001", scope2)
    sub_appr_b = submission_for(module, batch_b, "FIXTURE-REQ-G1-0001", fixture1)
    second_appr = save_call(module, "S4-save-B-APPROVE-after-HOLD", batch_b,
                            "FIXTURE-REQ-G1-0001", sub_appr_b, scope2 / "event_0002", scope2)
    check("S4.1 合法 HOLD 前序不被一律拒绝：同批次 HOLD 后可追加 APPROVE",
          first_hold["outcome"] == "returned" and second_appr["outcome"] == "returned"
          and json.loads((scope2 / "event_0002" / "context.json").read_text(
              encoding="utf-8"))["revision"] == 2,
          json.dumps(second_appr.get("result", second_appr), ensure_ascii=False)[:200])

    # ---------------------------------------------------------------- S5 同批次已有 APPROVE
    scope3 = scope_for(round_name, "s3")
    first_appr = save_call(module, "S5-save-A-APPROVE", batch_a, "FIXTURE-REQ-G1-0001",
                           submission_for(module, batch_a, "FIXTURE-REQ-G1-0001", fixture1),
                           scope3 / "event_0001", scope3)
    blocked_second = save_call(module, "S5-save-A-HOLD-after-APPROVE", batch_a,
                               "FIXTURE-REQ-G1-0002",
                               submission_for(module, batch_a, "FIXTURE-REQ-G1-0002",
                                              fixture2),
                               scope3 / "event_0002", scope3)
    check("S5.1 同批次 Gate1 已有 APPROVE 后再次提交被真实 P1 拒绝且不建事件",
          first_appr["outcome"] == "returned"
          and blocked_second["outcome"] in ("blocked", "error")
          and not (scope3 / "event_0002").exists(),
          json.dumps(blocked_second, ensure_ascii=False)[:260])

    # ---------------------------------------------------------------- S6 质量阻断材料
    scope4 = scope_for(round_name, "s4")
    usd_approve = save_call(module, "S6-save-USD-APPROVE", batch_usd,
                            "FIXTURE-REQ-G1-0001",
                            submission_for(module, batch_usd, "FIXTURE-REQ-G1-0001",
                                           fixture1),
                            scope4 / "event_0001", scope4)
    check("S6.1 质量阻断材料 + APPROVE 由真实 P1 拒绝、不建事件、不留锁",
          usd_approve["outcome"] == "blocked"
          and not (scope4 / "event_0001").exists()
          and sorted(p.name for p in scope4.iterdir()) == [],
          json.dumps(usd_approve, ensure_ascii=False)[:260])
    scope5 = scope_for(round_name, "s5")
    usd_hold = save_call(module, "S6-save-USD-HOLD", batch_usd, "FIXTURE-REQ-G1-0002",
                         submission_for(module, batch_usd, "FIXTURE-REQ-G1-0002", fixture2),
                         scope5 / "event_0001", scope5)
    check("S6.2 质量阻断材料 + HOLD 合法记录（RECORDED）",
          usd_hold["outcome"] == "returned"
          and usd_hold["result"]["identity"]["decision"] == "HOLD",
          json.dumps(usd_hold.get("result", usd_hold), ensure_ascii=False)[:200])

    # ---------------------------------------------------------------- S7 参数与路径拒绝
    scope6 = scope_for(round_name, "s6")
    good_a = submission_for(module, batch_a, "FIXTURE-REQ-G1-0001", fixture1)
    negatives = []
    negatives.append(("S7.1 scope_dir 缺省", save_call(
        module, "S7-none-scope", batch_a, "FIXTURE-REQ-G1-0001", good_a,
        scope6 / "event_x", None), "scope_dir"))
    negatives.append(("S7.2 scope 越界", save_call(
        module, "S7-out-of-bounds", batch_a, "FIXTURE-REQ-G1-0001", good_a,
        scope6 / "event_x", PROJECT_ROOT / "data" / "batches"), "scope_dir"))
    negatives.append(("S7.3 scope 不存在", save_call(
        module, "S7-missing-scope", batch_a, "FIXTURE-REQ-G1-0001", good_a,
        scope6 / "event_x", RECORDS_ROOT / f"{round_name}_nope"), "scope_dir"))
    (scope_for(round_name, "s6_pre") / "event_pre").mkdir(parents=True, exist_ok=True)
    negatives.append(("S7.4 event_dir 已存在（空目录）", save_call(
        module, "S7-event-exists", batch_a, "FIXTURE-REQ-G1-0001", good_a,
        scope_for(round_name, "s6_pre") / "event_pre",
        scope_for(round_name, "s6_pre")), "event_dir"))
    negatives.append(("S7.5 event_dir 非直接子目录", save_call(
        module, "S7-event-nested", batch_a, "FIXTURE-REQ-G1-0001", good_a,
        scope6 / "deep" / "event_y", scope6), "event_dir"))
    wrong_batch = dict(good_a, batch_id="NOT-THE-BATCH")
    negatives.append(("S7.6 错批次声明", save_call(
        module, "S7-wrong-batch", batch_a, "FIXTURE-REQ-G1-0001", wrong_batch,
        scope6 / "event_wrong_batch", scope6), "submission.batch_id"))
    wrong_materials = json.loads(json.dumps(good_a))
    wrong_materials["request_binding"]["materials_binding"] = "0" * 64
    negatives.append(("S7.7 错材料绑定", save_call(
        module, "S7-wrong-materials", batch_a, "FIXTURE-REQ-G1-0001", wrong_materials,
        scope6 / "event_wrong_materials", scope6), None))
    fake_actor = json.loads(json.dumps(good_a))
    fake_actor["actor"] = {"actor_kind": "SIMULATED", "actor_id": fixture1["actor"]["actor_id"],
                           "declaration_note": fixture1["actor"].get("declaration_note", "")}
    negatives.append(("S7.8 模拟 actor 声明", save_call(
        module, "S7-fake-actor", batch_a, "FIXTURE-REQ-G1-0001", fake_actor,
        scope6 / "event_fake_actor", scope6), None))
    (scope6 / ".gate1.lock").write_bytes(canonical_bytes(
        {"lock_version": module.LOCK_VERSION, "operation": "SAVE"}) + b"\n")
    negatives.append(("S7.9 占用锁", save_call(
        module, "S7-occupied-lock", batch_a, "FIXTURE-REQ-G1-0001", good_a,
        scope6 / "event_locked", scope6), "scope_dir.lock"))
    junction_probe = {"attempted": True}
    junction_target = RECORDS_ROOT / f"{round_name}_junc_target"
    junction_link = RECORDS_ROOT / f"{round_name}_junc"
    junction_target.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction_link),
                                str(junction_target)], capture_output=True, text=True)
    junction_probe["returncode"] = completed.returncode
    try:
        junction_probe["is_reparse"] = bool(
            os.lstat(junction_link).st_file_attributes & 0x400)
    except OSError:
        junction_probe["is_reparse"] = False
    if junction_probe["is_reparse"]:
        junction_entry = save_call(module, "S7.11 scope 真实 junction", batch_a,
                                   "FIXTURE-REQ-G1-0001", good_a,
                                   junction_link / "event_0001", junction_link)
        junction_probe["field"] = junction_entry.get("field")
        junction_probe["outcome"] = junction_entry["outcome"]
        junction_probe["event_created"] = (junction_link / "event_0001").exists()
        negatives.append(("S7.11 scope 真实 junction", junction_entry, "scope_dir"))
    else:
        junction_probe["note"] = "执行环境未允许建立 junction，如实报告未执行"
    for name, entry, expected_field in negatives:
        located = (entry["outcome"] in ("blocked", "error")
                   and (expected_field is None
                        or expected_field in (entry.get("field") or "")))
        check(f"{name} 结构化拒绝", located,
              json.dumps(entry, ensure_ascii=False)[:260])
    check("S7.10 早拒绝均未建立事件目录、scope 只留本次注入的锁",
          not (scope6 / "event_x").exists() and not (scope6 / "event_wrong_batch").exists()
          and not (scope6 / "event_wrong_materials").exists()
          and not (scope6 / "event_fake_actor").exists()
          and not (scope6 / "event_locked").exists()
          and sorted(p.name for p in scope6.iterdir()) == [".gate1.lock"],
          sorted(p.name for p in scope6.iterdir()))

    # ---------------------------------------------------------------- S8 历史枚举反例
    def scope_copy(scenario):
        target = scope_for(round_name, scenario)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(scope5, target)
        return target

    history_negatives = []
    copied = scope_copy("s8_missing_receipt")
    (copied / "event_0001" / "receipt.json").unlink()
    history_negatives.append(("S8.1 缺 receipt", verify_call(
        module, "S8-missing-receipt", copied / "event_0001", batch_usd, copied)))
    copied = scope_copy("s8_missing_snapshot")
    (copied / "event_0001" / "snapshots" / "manifest.json").unlink()
    history_negatives.append(("S8.2 缺六快照之一", verify_call(
        module, "S8-missing-snapshot", copied / "event_0001", batch_usd, copied)))
    copied = scope_copy("s8_unknown_item")
    (copied / "event_0001" / "extra.json").write_bytes(b"{}\n")
    history_negatives.append(("S8.3 事件目录未知项", verify_call(
        module, "S8-unknown-item", copied / "event_0001", batch_usd, copied)))
    copied = scope_copy("s8_identity_mismatch")
    receipt_path = copied / "event_0001" / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["batch_id"] = "OTHER-BATCH"
    receipt_path.write_bytes(canonical_bytes(receipt) + b"\n")
    history_negatives.append(("S8.4 封套 identity 矛盾", verify_call(
        module, "S8-identity-mismatch", copied / "event_0001", batch_usd, copied)))
    copied = scope_copy("s8_revision_gap")
    context_path = copied / "event_0001" / "context.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["revision"] = 7
    context_path.write_bytes(canonical_bytes(context) + b"\n")
    history_negatives.append(("S8.5 revision 非严格 1", verify_call(
        module, "S8-revision-gap", copied / "event_0001", batch_usd, copied)))
    copied = scope_copy("s8_failure_present")
    (copied / "event_0001" / "failure.json").write_bytes(canonical_bytes(
        {"failure_version": module.FAILURE_VERSION, "status": "ERROR", "stage": "x",
         "field": None, "reason": "注入", "exception_chain": [],
         "boundaries": dict(module.BOUNDARIES)}) + b"\n")
    history_negatives.append(("S8.6 事件含 failure 诊断", verify_call(
        module, "S8-failure-present", copied / "event_0001", batch_usd, copied)))
    copied = scope_copy("s8_lock_present")
    (copied / ".gate1.lock").write_bytes(canonical_bytes(
        {"lock_version": module.LOCK_VERSION, "operation": "SAVE"}) + b"\n")
    history_negatives.append(("S8.7 scope 存在锁（只读核验拒绝）", verify_call(
        module, "S8-lock-present", copied / "event_0001", batch_usd, copied)))
    copied = scope_copy("s8_unknown_scope_item")
    (copied / "stray.txt").write_bytes(b"x\n")
    history_negatives.append(("S8.8 scope 未知项", verify_call(
        module, "S8-unknown-scope-item", copied / "event_0001", batch_usd, copied)))
    for name, entry in history_negatives:
        check(f"{name} 被拒绝（不跳过坏目录）", entry["outcome"] in ("blocked", "error"),
              json.dumps(entry, ensure_ascii=False)[:220])

    # ---------------------------------------------------------------- S9 真实源晚变更
    scope9 = scope_for(round_name, "s9")
    source_file = batch_a / "checks" / "quality_report.json"
    source_original = source_file.read_bytes()
    late = {"hits": 0, "before": None, "after": None, "source": str(source_file)}
    live_store = module.load_frozen_store()
    original_save = live_store.save_human_gate_decision_snapshots

    def injecting_save(*args, **kwargs):
        result = original_save(*args, **kwargs)
        if late["hits"] == 0:
            late["hits"] = 1
            before = source_file.read_bytes()
            late["before"] = len(before)
            EXPECTED_MUTATION["active"] = True   # S9 为故意晚变更：由 API 收尾统一清除标记
            MUTATION_WINDOW["active"] = True
            MUTATION_WINDOW["paths"].add("checks/quality_report.json")
            EXPECTED_PATH_LOG.append({"paths": ["checks/quality_report.json"],
                                      "where": "S9-late-change"})
            source_file.write_bytes(before + b"\n")
            late["after"] = source_file.stat().st_size
        return result

    live_store.save_human_gate_decision_snapshots = injecting_save
    try:
        late_save = save_call(module, "S9-late-change", batch_a, "FIXTURE-REQ-G1-0001",
                              good_a, scope9 / "event_0001", scope9)
    finally:
        live_store.save_human_gate_decision_snapshots = original_save
    failure9 = scope9 / "event_0001" / "failure.json"
    failure_payload = (json.loads(failure9.read_text(encoding="utf-8"))
                      if failure9.is_file() else {})
    check("S9.1 真实源晚变更（store 返回后、封套最终确认前）本次 save 拒绝",
          late_save["outcome"] in ("blocked", "error") and late["hits"] == 1
          and late["after"] == late["before"] + 1,
          json.dumps(late_save, ensure_ascii=False)[:240])
    check("S9.2 本层 failure 恰为协议字段集合且现场保留（含定位被改文件）",
          sorted(failure_payload) == sorted(module.FAILURE_KEYS)
          and failure_payload.get("failure_version") == module.FAILURE_VERSION
          and failure_payload.get("status") in ("BLOCKED", "ERROR")
          and (failure_payload.get("field") is None
               or isinstance(failure_payload.get("field"), str))
          and isinstance(failure_payload.get("exception_chain"), list)
          and (scope9 / "event_0001" / "snapshots" / "manifest.json").is_file(),
          json.dumps(failure_payload, ensure_ascii=False)[:300])
    source_file.write_bytes(source_original)
    after_restore = verify_call(module, "S9-verify-after-restore",
                                scope9 / "event_0001", batch_a, scope9)
    check("S9.3 恢复原业务字节后 verify 仍拒绝失败事件（失败事实不被抹掉）",
          after_restore["outcome"] in ("blocked", "error")
          and failure9.is_file()
          and source_file.read_bytes() == source_original,
          json.dumps(after_restore, ensure_ascii=False)[:200])

    # ---------------------------------------------------------------- S9b 正常记录当前源变化
    scope12 = scope_for(round_name, "s12")
    normal_save = save_call(module, "S9b-save-normal", batch_b, "FIXTURE-REQ-G1-0002",
                            submission_for(module, batch_b, "FIXTURE-REQ-G1-0002", fixture2),
                            scope12 / "event_0001", scope12)
    source_b = batch_b / "checks" / "quality_report.json"
    source_b_original = source_b.read_bytes()
    normal_verify_before = verify_call(module, "S9b-verify-before", scope12 / "event_0001",
                                       batch_b, scope12)
    source_b.write_bytes(source_b_original + b"\n")
    normal_verify_after = verify_call(module, "S9b-verify-after-source-change",
                                      scope12 / "event_0001", batch_b, scope12)
    source_b.write_bytes(source_b_original)
    check("S9b 正常记录当前源变化时只读 verify 拒绝且不写 failure",
          normal_save["outcome"] == "returned"
          and normal_verify_before["outcome"] == "returned"
          and normal_verify_after["outcome"] in ("blocked", "error")
          and not (scope12 / "event_0001" / "failure.json").exists()
          and source_b.read_bytes() == source_b_original,
          json.dumps(normal_verify_after, ensure_ascii=False)[:240])

    # ---------------------------------------------------------------- S10 封套 writer 故障
    scope10 = scope_for(round_name, "s10a")
    writer_state = {"hits": 0}
    original_write = module._write_exclusive

    def half_write(path, buffer, stage, field):
        if Path(path).name == module.CONTEXT_FILE and writer_state["hits"] == 0:
            writer_state["hits"] = 1
            handle = os.open(Path(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(handle, "wb") as stream:
                stream.write(buffer[: max(1, len(buffer) // 2)])
            raise module.HumanGate1DecisionError("context_write", "注入：context 半写后失败")
        return original_write(path, buffer, stage, field)

    module._write_exclusive = half_write
    try:
        half = save_call(module, "S10-context-half-write", batch_a, "FIXTURE-REQ-G1-0001",
                         good_a, scope10 / "event_0001", scope10)
    finally:
        module._write_exclusive = original_write
    half_context = scope10 / "event_0001" / context_file_name if False else \
        scope10 / "event_0001" / "context.json"
    check("S10.1 context 半写 OSError → Error + 原因链 + failure 有效 + 半写现场保留",
          half["outcome"] == "error" and half.get("stage") == "context_write"
          and half_context.is_file()
          and (scope10 / "event_0001" / "failure.json").is_file()
          and (scope10 / "event_0001" / "snapshots" / "manifest.json").is_file(),
          json.dumps(half, ensure_ascii=False)[:240])

    scope11 = scope_for(round_name, "s10b")
    sentinel_state = {"hits": 0}

    def sentinel_write(path, buffer, stage, field):
        result = original_write(path, buffer, stage, field)
        if Path(path).name == module.RECEIPT_FILE and sentinel_state["hits"] == 0:
            sentinel_state["hits"] = 1
            with open(path, "ab") as stream:
                stream.write(b"X")
        return result

    module._write_exclusive = sentinel_write
    try:
        sentinel = save_call(module, "S10-receipt-sentinel", batch_a, "FIXTURE-REQ-G1-0001",
                             good_a, scope11 / "event_0001", scope11)
    finally:
        module._write_exclusive = original_write
    check("S10.2 receipt 完整写后 sentinel → 本次 save 拒绝 + failure 有效 + 现场保留",
          sentinel["outcome"] in ("blocked", "error")
          and (scope11 / "event_0001" / "receipt.json").is_file()
          and (scope11 / "event_0001" / "receipt.json").read_bytes().endswith(b"X")
          and (scope11 / "event_0001" / "failure.json").is_file(),
          json.dumps(sentinel, ensure_ascii=False)[:240])

    # ---------------------------------------------------------------- 证据收尾（定稿→一次写入→读数→审核→漂移）
    summary = {"task": "TASK-024",
               "suite": "Gate1 决定保存与限定历史核验适配器（32 项绑定、保存封套、历史范围、只读核验）",
               "fixture_policy": "人类字段只来自登记夹具；外层标 PROTOCOL_TEST_FIXTURE_ONLY",
               "status": "FAIL" if FAILURES else "PASS",
               "checks_total": len(CHECKS), "checks_failed": len(FAILURES),
               "counts": {
                   "prepare_calls": sum(1 for item in CALLS if item["call"] == "prepare"),
                   "save_calls": sum(1 for item in CALLS if item["call"] == "save"),
                   "verify_calls": sum(1 for item in CALLS if item["call"] == "verify"),
                   "store_save_calls_after_counting_installed": None,
                   "receiver_runs": len(SAMPLES),
                   "receiver_returncodes": {item["out_dir"].split("/")[-1]: item["returncode"]
                                            for item in SAMPLES},
                   "not_executed": {"host_or_controller": None, "normalization_or_db": None,
                                    "gate2": None, "real_initial_judgment": None,
                                    "ai_or_final_judgment": None,
                                    "cross_scope_history_discovery": None,
                                    "junction_case": None}},
               "boundaries": {"execution_allowed": False, "workflow_connected": False,
                              "human_initial_judgment_saved": False, "ai_enabled": False,
                              "identity_authenticated": False,
                              "source_authenticity_proven": False}}
    core_layers = sorted({item["layer"] for item in CORE_OBSERVATIONS})
    core_fingerprints_ok = all(
        (item.get("code_stability") or {}).get("code_unchanged") is True
        for item in CORE_OBSERVATIONS)
    core_complete = all(
        (item.get("outcome") == "returned" and (item.get("result") or {}).get("present") is True)
        or (item.get("outcome") == "raised" and item.get("exception_chain")
            and item.get("traceback"))
        for item in CORE_OBSERVATIONS)
    core_empty_distinct = all(
        "item_count" in (item.get("result") or {})
        for item in CORE_OBSERVATIONS
        if (item.get("result") or {}).get("kind") in ("dict", "list"))
    check("E2.2a 冻结 prepare/store.save/store.verify/P1 真实调用观察完整（输入+返回/异常+原因链）",
          core_complete and len(CORE_OBSERVATIONS) >= 20
          and {"frozen_prepare", "store_save", "store_verify"} <= set(core_layers),
          json.dumps({"layers": core_layers, "count": len(CORE_OBSERVATIONS)},
                     ensure_ascii=False))
    check("E2.2b 调用前后真实引用指纹一致（不被包装替换所掩盖）",
          core_fingerprints_ok,
          json.dumps([item["case_id"] for item in CORE_OBSERVATIONS
                      if (item.get("code_stability") or {}).get("code_unchanged")
                      is not True][:6], ensure_ascii=False))
    check("E2.2c 容器返回记 item_count（合法空结果与缺记录分开）",
          core_empty_distinct and counters.get("p1_seam", 0) > 0,
          json.dumps({"p1_seam_calls": counters.get("p1_seam"),
                      "container_results": len([item for item in CORE_OBSERVATIONS
                                                if (item.get("result") or {}).get("kind")
                                                in ("dict", "list")])}, ensure_ascii=False))
    summary["checks_total"] = len(CHECKS)
    summary["checks_failed"] = len(FAILURES)
    summary["core_entry_total"] = len(CORE_OBSERVATIONS)
    payloads = {"calls.json": CALLS, "samples.json": SAMPLES, "checks.json": CHECKS,
                "failures.json": FAILURES, "summary.json": summary,
                "core_observations.json": CORE_OBSERVATIONS}
    pending = {name: {"parsed": json.loads(canonical_bytes(payload))}
               for name, payload in payloads.items()}
    audit_pending = evidence_audit(pending)
    isolation = {"pending_audit_ok": audit_pending["ok"]}
    trimmed = dict(pending)
    trimmed["calls.json"] = {"parsed": pending["calls.json"]["parsed"][:-1]}
    isolation["removed_entry_rejected"] = not evidence_audit(trimmed)["ok"]
    duplicated = json.loads(json.dumps(pending["calls.json"]["parsed"]))
    duplicated.append(json.loads(json.dumps(duplicated[0])))
    dup_audit = dict(pending)
    dup_audit["calls.json"] = {"parsed": duplicated}
    isolation["duplicate_case_id_rejected"] = not evidence_audit(dup_audit)["ok"]
    check("E1 待写缓冲登记审核一致（完整记录 / case_id 唯一 / 总数与声明闭合）",
          audit_pending["ok"] and audit_pending["call_count"] == len(CALLS),
          json.dumps(audit_pending, ensure_ascii=False)[:280])
    check("E2 同一审核删除一条登记即失败、改出重复 case_id 亦失败",
          isolation["removed_entry_rejected"] is True
          and isolation["duplicate_case_id_rejected"] is True,
          json.dumps(isolation, ensure_ascii=False)[:200])

    # ---------------------------------------------------------------- R1 定点段
    r1_points = R1Points({"module": module, "round_name": round_name, "batch_a": batch_a,
                          "batch_b": batch_b, "batch_root": batch_root,
                          "records_root": RECORDS_ROOT,
                          "fixtures": (fixture1, fixture2, reject_fixture()),
                          "check": check, "sha_bytes": sha_bytes,
                          "canonical_bytes": canonical_bytes,
                          "submission_for": submission_for, "call": call})
    summary["r1_points"] = r1_points.run_all()
    summary["counts"]["prepare_calls"] = len([item for item in CALLS
                                              if item.get("call") == "prepare"])
    summary["counts"]["save_calls"] = len([item for item in CALLS
                                           if item.get("call") == "save"])
    summary["counts"]["verify_calls"] = len([item for item in CALLS
                                             if item.get("call") == "verify"])

    # ---------------------------------------------------------------- E2.1 入口观察闭合
    observer.stop()
    observations = observer.payload()
    summary["entry_observations"] = observations
    check("E2.1a 全部公开 prepare 调用（含 submission_for 准备）均进入同一登记",
          observations["adapter_prepare"] == summary["counts"]["prepare_calls"]
          and len([item for item in CALLS if item.get("call") == "prepare"])
          == summary["counts"]["prepare_calls"],
          json.dumps({"observed_prepare": observations["adapter_prepare"],
                      "registered_prepare": summary["counts"]["prepare_calls"]},
                     ensure_ascii=False))
    check("E2.1b 本层 save/verify 真实入口观察与登记一致",
          observations["adapter_save"] == summary["counts"]["save_calls"]
          and observations["adapter_verify"] == summary["counts"]["verify_calls"],
          json.dumps({"observed_save": observations["adapter_save"],
                      "registered_save": summary["counts"]["save_calls"],
                      "observed_verify": observations["adapter_verify"],
                      "registered_verify": summary["counts"]["verify_calls"]},
                     ensure_ascii=False))
    layer_pairs = (("frozen_prepare", "prepare_human_gate1_request"),
                   ("store_save", "save_human_gate_decision_snapshots"),
                   ("store_verify", "verify_human_gate_decision_snapshots"),
                   ("real_p1", "build_human_gate_decision_record"))
    closure = {}
    for layer, function in layer_pairs:
        frames = sum(count for key, count in observations["counts"].items()
                     if key.endswith(f"::{function}"))
        frames_trace = sum(count for key, count in observations["trace_counts"].items()
                           if key.endswith(f"::{function}"))
        all_items = [item for item in CORE_OBSERVATIONS if item["layer"] == layer]
        wrapper_items = [item for item in all_items
                         if (item.get("code_stability") or {}).get(
                             "reference_before", {}).get("file") == "test_record_demo_human_gate1.py"]
        business_items = [item for item in all_items if item not in wrapper_items]
        entries = [item for item in business_items if (item.get("frame_delta") or 0) >= 1]
        not_entered = [item["case_id"] for item in business_items
                       if item.get("frame_delta") == 0]
        ids = {item["case_id"] for item in entries}
        frames_by_delta = sum(item["frame_delta"] for item in entries)
        closure[layer] = {"frames_aggregate": frames, "frames_trace": frames_trace,
                          "frames_by_delta": frames_by_delta,
                          "entries": len(entries), "unique_ids": len(ids),
                          "not_entered": not_entered,
                          "test_wrapper_entries": sorted(item["case_id"]
                                                         for item in wrapper_items),
                          "cross_check_delta": frames_trace - len(entries),
                          "profile_vs_trace_delta": frames - frames_trace,
                          "seen_only_by_wrapper": sorted(
                              item["case_id"] for item in entries
                              if (item.get("frame_delta") or 0) != 1),
                          "closed": frames_trace == len(entries) == len(ids)
                          and len(entries) > 0}
    seam_entries = [item for item in CORE_OBSERVATIONS if item["layer"] == "real_p1_seam"]
    observations["layer_closure"] = closure
    observations["p1_entry"] = counters.get("p1_entry")
    observations["p1_seam"] = counters.get("p1_seam")
    summary["layer_closure"] = closure
    three_point_problems = [item["case_id"] for item in CORE_OBSERVATIONS
                            if item.get("expected_mutation") is not True
                            and (item.get("three_time_points_equal") is not True
                                 or item.get("input_unchanged_through_api") is not True)]
    expected_mutation_count = len([item for item in CORE_OBSERVATIONS
                                   if item.get("expected_mutation") is True])
    check("E2.2f 消费对象三时点（调用前 / 返回或异常后 / 所属公开 API 收尾）逐条一致",
          not three_point_problems and len(CORE_OBSERVATIONS) > 90,
          json.dumps({"problems": three_point_problems[:6],
                      "records": len(CORE_OBSERVATIONS),
                      "expected_mutation": expected_mutation_count},
                     ensure_ascii=False))
    path_problems, output_problems = [], []
    input_dir_scenes = 0
    output_scenes = 0
    for item in CORE_OBSERVATIONS:
        for desc in list(item.get("inputs") or []) + list(
                (item.get("input_kwargs") or {}).values()):
            if desc.get("kind") != "path":
                continue
            if desc.get("role", "").startswith("output_dir"):
                continue
            if desc.get("exists") is False and desc.get("is_dir") is not True:
                path_problems.append(f"{item['case_id']}:{desc.get('field')} exists=false")
            if desc.get("is_dir") is True:
                input_dir_scenes += 1
                if not isinstance(desc.get("entries"), list) or "file_scenes" not in desc:
                    path_problems.append(
                        f"{item['case_id']}:{desc.get('field')} 目录现场缺集合")
            elif desc.get("exists") is True and not desc.get("file_sha256"):
                path_problems.append(f"{item['case_id']}:{desc.get('field')} 缺文件 SHA")
        for desc in item.get("inputs") or []:
            if desc.get("role") == "output_dir":
                output_scenes += 1
                after = (item.get("output_scene_after") or [{}])[0]
                if item.get("outcome") != "returned":
                    # 早拒绝（如 P1 阻断）发生在建目录之前：写后现场应为未建立
                    if item.get("output_scene_after"):
                        output_problems.append(
                            f"{item['case_id']}: 拒绝路径不应产生输出目录")
                    continue
                if desc.get("exists") is not False or desc.get(
                        "expected_created_after_write") is not True:
                    output_problems.append(f"{item['case_id']}: 输出目标建立前应为不存在")
                produced = set((after.get("file_scenes") or {}).keys())
                snapshots_entries = set(
                    (after.get("subdir_entries") or {}).get("snapshots") or [])
                snapshots_expected = {"decision_result.json", "expectations.json",
                                      "manifest.json", "materials.json",
                                      "prior_history.json", "submission.json"}
                ok_shape = (produced == snapshots_expected and not snapshots_entries) or (
                    {"context.json", "receipt.json"} <= produced
                    and snapshots_entries == snapshots_expected)
                if not ok_shape:
                    output_problems.append(
                        f"{item['case_id']}: 写后集合不符："
                        f"{sorted(produced)} / {sorted(snapshots_entries)}")
    check("E2.1e 路径输入按角色记真实有界现场（目录记存在性与集合，不再 exists=false）",
          not path_problems and input_dir_scenes > 0,
          json.dumps({"problems": path_problems[:6], "dir_scenes": input_dir_scenes},
                     ensure_ascii=False))
    check("E2.1f store.save 的 out_dir 单列输出角色（建立前不存在、写后六文件为预期变化）",
          not output_problems and output_scenes > 0,
          json.dumps({"problems": output_problems[:6], "output_scenes": output_scenes},
                     ensure_ascii=False))
    summary["core_entry_total"] = len(CORE_OBSERVATIONS)
    summary["core_entry_layers"] = {layer: item["entries"] for layer, item in closure.items()}
    def _desc_self_consistent(desc):
        if desc.get("kind") == "path":
            if desc.get("is_dir") is True:
                return isinstance(desc.get("entries"), list)
            if desc.get("exists") is False:
                return desc.get("role") == "output_dir" or desc.get("output_target") is True
            return desc.get("byte_size") is not None and desc.get("file_sha256")
        if "snapshot" not in desc:
            return True
        payload = independent_canonical(desc["snapshot"]).encode("utf-8")
        return (desc.get("byte_size") == len(payload)
                and desc.get("canonical_sha256") == sha_bytes(payload))

    input_problems, output_problems, code_label_problems = [], [], []
    for item in CORE_OBSERVATIONS:
        if item.get("input_unchanged") is not True:
            input_problems.append(item["case_id"])
        descriptions = list(item.get("inputs") or []) + list(
            (item.get("input_kwargs") or {}).values())
        for desc in descriptions:
            if not _desc_self_consistent(desc) or desc.get("alias_free") is False:
                input_problems.append(f"{item['case_id']}:{desc.get('field')}")
        if item.get("outcome") == "returned" and (item.get("result") or {}).get(
                "kind") in ("dict", "list"):
            result = item["result"]
            payload = independent_canonical(result["snapshot"]).encode("utf-8")
            if result.get("sha256") != sha_bytes(payload) or \
                    result.get("byte_size") != len(payload) or result.get("alias_free") is False:
                output_problems.append(item["case_id"])
        if (item.get("code_stability") or {}).get("scope") != "function_code_only":
            code_label_problems.append(item["case_id"])
    check("E2.2d 输入对象三时点：同一引用指纹前后一致、描述与独立深拷贝快照自洽且无别名",
          not input_problems and len(CORE_OBSERVATIONS) > 90,
          json.dumps({"problems": input_problems[:6],
                      "records": len(CORE_OBSERVATIONS)}, ensure_ascii=False))
    check("E2.2e 输出独立快照自洽；代码指纹明确标注只测函数代码（不代表对象未变）",
          not output_problems and not code_label_problems,
          json.dumps({"output_problems": output_problems[:6],
                      "code_label_problems": code_label_problems[:6]}, ensure_ascii=False))
    check("E2.1c 分列层真实入口覆盖闭合（独立聚合入口 == 完整条目 == 唯一调用 ID，逐层）",
          all(item["closed"] for item in closure.values())
          and counters.get("p1_entry") == closure["real_p1"]["entries"],
          json.dumps(closure, ensure_ascii=False))
    check("E2.1d P1 入口与 store seam 分列（seam 不冒称 P1 入口；早拒绝记增量 0）",
          len(seam_entries) == counters.get("p1_seam")
          and closure["real_p1"]["entries"] == counters.get("p1_entry")
          and all(item["layer"] != "real_p1_seam" for item in CORE_OBSERVATIONS
                  if item["case_id"].startswith("core-p1::")),
          json.dumps({"p1_entry": counters.get("p1_entry"),
                      "p1_seam": counters.get("p1_seam"),
                      "seam_entries": len(seam_entries)}, ensure_ascii=False))
    summary["checks_total"] = len(CHECKS)
    summary["checks_failed"] = len(FAILURES)
    summary["status"] = "FAIL" if FAILURES else "PASS"
    summary["counts"]["store_save_calls"] = counters["store_save"]
    summary["counts"]["store_verify_calls"] = counters["store_verify"]
    payloads = {"calls.json": CALLS, "samples.json": SAMPLES, "checks.json": CHECKS,
                "failures.json": FAILURES, "summary.json": summary,
                "core_observations.json": CORE_OBSERVATIONS}
    # E2.3：真实观察完成后、任何终审读取前，独立深拷贝冻结完整预期（不来自候选磁盘）
    expectation = json.loads(canonical_bytes(payloads).decode("utf-8"))
    expectation_from_memory = all(
        canonical_bytes(expectation[name]) == canonical_bytes(payloads[name])
        for name in payloads)
    write_payloads(out_dir, payloads)
    audited = read_payloads(out_dir, list(payloads))
    expectation_compare = compare_expectation(expectation, audited)
    post_audit("E2.3a 预期为观察后独立深拷贝，且与首轮同缓冲读数 canonical 完全一致（含字节长度/SHA）",
          expectation_compare["ok"] and expectation_from_memory
          and all(entry["diff_count"] == 0
                  for entry in expectation_compare["per_payload"].values()),
          json.dumps({"ok": expectation_compare["ok"],
                      "problems": expectation_compare["problems"][:4]}, ensure_ascii=False))
    replaced = json.loads(canonical_bytes(expectation).decode("utf-8"))
    target_index = next(index for index, item in enumerate(replaced["calls.json"])
                        if item.get("outcome") == "returned")
    replaced_target_id = replaced["calls.json"][target_index]["case_id"]
    replaced["calls.json"][target_index]["reason"] = "隔离对照：自洽替换 reason"
    replaced_audit = compare_expectation(
        expectation, {name: {"parsed": value} for name, value in replaced.items()})
    replaced_located = locate_call_diff(expectation, replaced, replaced_target_id)
    zeroed = json.loads(canonical_bytes(expectation).decode("utf-8"))
    zeroed_index = next(index for index, item in enumerate(zeroed["core_observations.json"])
                        if isinstance((item.get("result") or {}).get("snapshot"), dict))
    zeroed_case = zeroed["core_observations.json"][zeroed_index]["case_id"]
    zeroed_value = zeroed["core_observations.json"][zeroed_index]["result"]["snapshot"]
    zeroed_path = ("execution_allowed" if "execution_allowed" in zeroed_value
                   else sorted(zeroed_value)[0])
    zeroed["core_observations.json"][zeroed_index]["result"]["snapshot"][zeroed_path] = 0
    zeroed_audit = compare_expectation(
        expectation, {name: {"parsed": value} for name, value in zeroed.items()})
    reordered = {name: {key: value for key, value in reversed(list(payload.items()))}
                 if isinstance(payload, dict) else payload
                 for name, payload in expectation.items()}
    reordered_audit = compare_expectation(reordered, audited)
    post_audit("E2.3b 内容替换与 False/数值混淆在隔离对照中被拒并定位 call_id/字段",
          not replaced_audit["ok"] and bool(replaced_located)
          and any(replaced_target_id in diff for diff in replaced_located)
          and not zeroed_audit["ok"]
          and any(zeroed_case in diff or zeroed_path in diff
                  for diff in zeroed_audit["problems"]),
          json.dumps({"replaced": replaced_located[:3],
                      "zeroed": [diff for diff in zeroed_audit["problems"]
                                 if zeroed_case in diff or zeroed_path in diff][:3]},
                     ensure_ascii=False))
    post_audit("E2.3c 键顺序不同但 canonical 等值仍通过；预期来源为本次内存观察（非候选磁盘）",
               reordered_audit["ok"] and expectation_from_memory,
               json.dumps({"reordered_ok": reordered_audit["ok"],
                           "from_memory": expectation_from_memory,
                           "pending_agreement": strict_equals(
                               expectation["calls.json"],
                               pending["calls.json"]["parsed"]) == []}, ensure_ascii=False))
    audit = evidence_audit(audited)
    drift = []
    for name in payloads:
        data = (out_dir / name).read_bytes()
        if sha_bytes(data) != audited[name]["file_sha256"]:
            drift.append({"name": name, "byte_size_now": len(data),
                          "sha256_audited": audited[name]["file_sha256"],
                          "sha256_now": sha_bytes(data)})
    ledger = {"entries": audited, "entry_count": len(audited), "covered": list(payloads),
              "expectation_source": "本次真实观察（内存定稿→一次写入→同缓冲读回）",
              "pending_audit": audit_pending, "disk_audit": audit,
              "expectation_compare": expectation_compare,
              "isolation_controls": isolation, "byte_drift": drift,
              "store_call_counters": counters, "entry_observations": observations,
              "core_observation_count": len(CORE_OBSERVATIONS),
              "core_observation_layers": sorted({item["layer"]
                                                  for item in CORE_OBSERVATIONS}),
              "final_audit_failed": bool(drift) or not audit["ok"]}
    ledger_buffer = canonical_bytes(ledger) + b"\n"
    (out_dir / "evidence_ledger.json").write_bytes(ledger_buffer)
    ledger_read = (out_dir / "evidence_ledger.json").read_bytes()
    ledger_audit = audit_ledger(json.loads(ledger_read.decode("utf-8")), audited)
    ledger_same_buffer = (ledger_read == ledger_buffer)
    mutated_ledger = json.loads(ledger_read.decode("utf-8"))
    first_name = sorted(mutated_ledger["entries"])[0]
    mutated_ledger["entries"][first_name]["file_sha256"] = "0" * 64
    mutated_audit = audit_ledger(mutated_ledger, audited)
    trimmed_ledger = json.loads(ledger_read.decode("utf-8"))
    trimmed_ledger["covered"] = trimmed_ledger["covered"][:-1]
    trimmed_audit = audit_ledger(trimmed_ledger, audited)
    post_audit("E2.4a 台账落盘后读回审核：登记字节与审核读数逐项闭合（同缓冲）",
          ledger_audit["ok"] and ledger_same_buffer,
          json.dumps({"readback": ledger_audit, "same_buffer": ledger_same_buffer},
                     ensure_ascii=False)[:300])
    post_audit("E2.4b 台账读回对照：改动登记 SHA 或删 covered 即被同一审核拒绝",
          not mutated_audit["ok"] and not trimmed_audit["ok"],
          json.dumps({"mutated": mutated_audit["problems"][:2],
                      "trimmed": trimmed_audit["problems"][:2]}, ensure_ascii=False))
    simulated = {"audit_ok": False, "drift": []}
    simulated_dominates = bool(simulated["drift"]) or not simulated["audit_ok"]
    post_audit("E2.4c 失败支配：审核失败/漂移即 FAIL+非零返回；本轮无失败且台账未重建期望",
          ledger["final_audit_failed"] is False and summary["status"] == "PASS"
          and ledger["expectation_compare"]["ok"] is True and simulated_dominates
          and simulated_dominates,
          json.dumps({"status": summary["status"],
                      "final_audit_failed": ledger["final_audit_failed"],
                      "expectation_ok": ledger["expectation_compare"]["ok"],
                      "simulated_dominates": simulated_dominates,
                      "drift": drift}, ensure_ascii=False))
    (out_dir / "ledger_readback.json").write_bytes(canonical_bytes(
        {"same_buffer": ledger_same_buffer, "readback_audit": ledger_audit,
         "isolation_controls": {"mutated_sha_rejected": not mutated_audit["ok"],
                                "trimmed_covered_rejected": not trimmed_audit["ok"]},
         "post_audits": POST_AUDITS,
         "post_audit_failed": [item["name"] for item in POST_AUDITS if not item["ok"]],
         "dominance": {"audit_ok": audit["ok"], "byte_drift": drift,
                       "post_audit_failed": [item["name"] for item in POST_AUDITS
                                             if not item["ok"]],
                       "final_audit_failed": ledger["final_audit_failed"],
                       "exit_code_if_failed": 1},
         "post_ledger_writes": ["ledger_readback.json"]}) + b"\n")
    post_audit_failed = [item for item in POST_AUDITS if not item["ok"]]
    audit_failed = (not audit["ok"] or bool(drift) or bool(post_audit_failed))
    if audit_failed:
        FAILURES.append({"name": "磁盘候选登记/内容/字节漂移或写盘后审核失败（支配结论与返回码）",
                         "detail": json.dumps({"disk_audit": audit, "byte_drift": drift},
                                              ensure_ascii=False)[:900]})
        (out_dir / "failures.json").write_bytes(canonical_bytes(FAILURES) + b"\n")
        failed_summary = dict(summary)
        failed_summary["checks_failed"] = len(FAILURES)
        failed_summary["status"] = "FAIL"
        summary["status"] = "FAIL"
        summary["checks_failed"] = len(FAILURES)
        (out_dir / "summary.json").write_bytes(canonical_bytes(failed_summary) + b"\n")
        (out_dir / "final_audit_diagnostic.json").write_bytes(canonical_bytes(
            {"detected": {"disk_audit": audit, "byte_drift": drift},
             "dominates_exit_code": True,
             "post_audit_writes": ["failures.json", "summary.json",
                                   "final_audit_diagnostic.json"]}) + b"\n")
    dominance_ok = (summary["status"] == ("FAIL" if FAILURES else "PASS"))
    print("[E2.4c-final] 失败支配：status=" + summary["status"]
          + f"、failures={len(FAILURES)}、返回码={'1' if FAILURES else '0'}、支配一致={dominance_ok}")
    print(f"TASK-024 测试组：{len(CHECKS)} 项检查，{len(FAILURES)} 项失败；"
          f"prepare {summary['counts']['prepare_calls']}、save "
          f"{summary['counts']['save_calls']}、verify {summary['counts']['verify_calls']}、"
          f"接收器 {summary['counts']['receiver_runs']}、"
          f"冻结 store.save 实际调用 {counters['store_save']}、"
          f"冻结 store.verify 实际调用 {counters['store_verify']}")
    for item in FAILURES[:12]:
        print(f"  - {item['name']}: {item['detail'][:200]}")
    return 1 if FAILURES else 0


context_file_name = "context.json"

if __name__ == "__main__":
    sys.exit(main())
