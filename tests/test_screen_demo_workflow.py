#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-013 验证入口：只读 R01—R04 规则筛查的宿主接入与恢复。

用法：
    .venv\\Scripts\\python.exe -B tests\\test_screen_demo_workflow.py --out-dir data\\workflow_host_tests\\<容器>

本入口只读既有合成 Excel，不读答案册、不生成业务数据；所有批次与数据库都在本轮新容器下创建。
"""

from __future__ import annotations

import argparse
import ast
import builtins
import copy
import hashlib
import inspect
import io
import traceback
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOST_PATH = PROJECT_ROOT / "scripts" / "run_demo_workflow.py"
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
BATCHES_ROOT = PROJECT_ROOT / "data" / "batches"
GENERATED = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a"
MAIN_WORKBOOK = GENERATED / "input" / "erp_export.xlsx"
SQLITE_ROOT = PROJECT_ROOT / "data" / "sqlite_tests" / "workflow_gate2"
SCREEN_REL = "workflow/screening"

PROTECTED_FILES = [
    "scripts/control_demo_workflow.py",
    "scripts/receive_demo_batch.py",
    "scripts/check_demo_data.py",
    "scripts/normalize_demo_data.py",
    "scripts/store_demo_sqlite.py",
    "scripts/screen_demo_sqlite.py",
    "scripts/crosscheck_demo_rules.py",
    "scripts/build_demo_fact_packet.py",
    "sql/demo_schema.sql",
    "docs/SPEC_V1.md",
    "docs/AUDIT_CONTRACT_DRAFT.md",
    "tests/test_run_demo_workflow.py",
    "tests/test_record_demo_gate2_decision.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha256(payload) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def load_host():
    spec = importlib.util.spec_from_file_location("task013_host", HOST_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load_host()


def tree_hashes(root: Path) -> dict:
    if not root.exists():
        return {}
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def call_stack_names(limit: int = 8, skip: int = 1) -> list:
    """当前调用栈的函数名（由内向外，含当前帧）。用 traceback.extract_stack 只取名字，
    避免不同 Python 版本对帧属性（如 .name）的支持差异。

    `skip` 用于跳过测试侧自己的观察帧，避免“观察层把真实读取者挤出窗口”。
    """
    names = []
    for frame in traceback.extract_stack()[:-skip or None]:
        try:
            names.append(frame.name)
        except AttributeError:
            names.append("<unknown>")
    names.reverse()
    return names[:limit]


def call_stack_tail(limit: int = 7, skip: int = 1) -> list:
    names = []
    stack = traceback.extract_stack()[:-skip or None]
    for frame in stack[-limit:]:
        try:
            names.append(f"{str(frame.filename).split('/')[-1]}:{frame.lineno}:{frame.name}")
        except AttributeError:
            names.append("<unknown-frame>")
    return names


def probe_timing_verdict(trace: dict) -> dict:
    """纯内存时点判定：合格的末次读取探针必须同时满足

      1. 恰有一次注入，且注入点落在已记录的某次目标读取的序号上；
      2. 注入应当发生在**该轨迹最后一次内容消费读取**返回之后（未给出消费信息时，
         就是该轨迹的最后一次读取）；
      3. 注入之后不得再有**内容消费型**读取（只比较字节的守卫读取是宿主发现变化的手段，
         单独计数、不算“又消费了一次”）；
      4. 注入之后不得再有控制器调用。

    轨迹形状（两种事件都按真实发生顺序排列）：
      - reads:        [{"seq": k, "consumer_read": bool}]（k = 文件观察器的读取序号）
      - writes:       [{"after_read_seq": k, ...}]
      - controllers:  [{"after_reads": r, ...}]（r = 该次控制器调用发生时已返回的目标读取次数）
    """
    reads = list(trace.get("reads") or [])
    writes = list(trace.get("writes") or [])
    controllers = list((trace.get("controllers") or {}))
    ordered = ([(item.get("event_seq", item.get("seq")) if
                 (item.get("event_seq", item.get("seq")) is not None) else 0, "read", item)
                for item in reads]
               + [(item.get("event_seq", item.get("after_reads")) if
                   (item.get("event_seq", item.get("after_reads")) is not None) else 0,
                   "controller", item) for item in controllers])
    ordered.sort(key=lambda item: (item[0], item[1]))
    last_read_seq = (max((item.get("seq") or 0) for item in reads) if reads else 0)
    content_reads = [item for item in reads if item.get("consumer_read") is not False]
    content_seqs = sorted((item.get("seq") or 0) for item in content_reads)
    problems: list = []
    injection = None
    # 共同触发点：status 的第二次 `_read_screen_outputs` 完整返回之后。
    supplied_reader_returns = trace.get("reader_returns")
    if supplied_reader_returns is None:
        reader_returns = len(content_seqs)
    else:
        reader_returns = int(supplied_reader_returns)
    if reader_returns < 2:
        problems.append(f"只观测到 {reader_returns} 次 _read_screen_outputs 返回；"
                        "共同触发点要求第二次完整返回之后才注入")
    if not writes:
        problems.append("轨迹中缺少注入事件（未在真实读取边界改动磁盘）")
    else:
        write = writes[0]
        injection = {"after_read_seq": write.get("after_read_seq")}
        event_seq = write.get("event_seq", write.get("after_read_seq"))
        for index, (_, kind, item) in enumerate(ordered, start=1):
            if kind == "read" and item.get("seq") == event_seq:
                injection["event_index"] = index
                break
        if injection.get("event_index") is None:
            injection["event_index"] = 0
            problems.append("注入事件未落在已记录的读取事件序号上")
    after_injection_reads = 0
    after_injection_guard_reads = 0
    after_injection_controllers = 0
    injection_event_index = (injection or {}).get("event_index") or 0
    if injection_event_index:
        for _, kind, item in ordered[injection_event_index:]:
            if kind != "read":
                after_injection_controllers += 1
            elif item.get("consumer_read") is False:
                after_injection_guard_reads += 1
            else:
                after_injection_reads += 1
    if injection is not None and injection_event_index:
        if after_injection_reads:
            problems.append(f"注入之后仍有 {after_injection_reads} 次内容消费型目标读取")
        if after_injection_controllers:
            problems.append(f"注入之后仍有 {after_injection_controllers} 次控制器调用")
        supplied_after_readers = trace.get("reader_returns_after_injection")
        if supplied_after_readers not in (None, 0):
            problems.append(f"注入之后仍有 {supplied_after_readers} 次 _read_screen_outputs 返回")
    return {"reads_total": len(reads), "last_read_seq": last_read_seq,
            "content_read_seqs": content_seqs,
            "reader_returns": reader_returns,
            "reader_returns_before_injection": (min(reader_returns, 2) if injection else 0),
            "reader_returns_after_injection": after_injection_reads,
            "content_reads": len(content_reads),
            "guard_reads": len(reads) - len(content_reads),
            "injection_after_read_seq": (injection or {}).get("after_read_seq"),
            "after_injection_reads": after_injection_reads,
            "after_injection_guard_reads": after_injection_guard_reads,
            "after_injection_controllers": after_injection_controllers,
            "qualified": not problems, "problems": problems,
            "ordered_events": [{"index": index, "kind": kind,
                                **({"stage": item.get("stage"), "seq": item.get("seq"),
                                    "consumer_read": item.get("consumer_read")}
                                   if kind == "read"
                                   else {"name": item.get("name"), "after_reads": item.get("after_reads")})}
                               for index, (_, kind, item) in enumerate(ordered, start=1)],
            "reads": reads, "writes": writes, "controllers": controllers}


def truncate_trace_at_exception(trace: dict, exc) -> dict:
    """把读取轨迹截断到本次调用抛出阻断的那一点。

    同一进程内后续调用（撤销后的新进程 CLI 不在此列，但同一进程内的再次调用会出现）
    的读数不能算作本次注入的证据。判定方式：从异常逐帧 traceback 中取本测试文件里
    **最先**出现的帧（即抛出点），凡 stack_tail 里包含该帧的读取都按“抛出点及之后”处理。
    """
    if exc is None or not getattr(exc, "__traceback__", None):
        return trace
    self_name = "test_screen_demo_workflow.py"
    markers = [f"{self_name}:{frame.lineno}"
               for frame in traceback.extract_tb(exc.__traceback__)
               if Path(frame.filename).name == self_name]
    if not markers:
        return trace
    # 用最后一个测试侧调用帧（本次公开调用的发起帧）作为“抛出点”标记：凡 stack_tail 里包含该帧的
    # 目标读取都发生在抛出调用之内，其后（含该帧之后的再次调用）不再计入本次注入证据。
    marker = markers[-1]
    reads = list(trace.get("reads") or [])
    kept: list = []
    for item in reads:
        stack = item.get("stack_tail") or []
        if any(marker in str(entry) for entry in stack):
            break
        kept.append(item)
    if not kept:
        return trace
    writes = list(trace.get("writes") or [])
    writes = [item for item in writes
              if item.get("after_read_seq") is not None
              and any(read.get("seq") == item.get("after_read_seq") for read in kept)]
    return {**trace, "reads": kept, "writes": writes,
            "truncated_at": marker, "reads_before_truncation": len(reads)}


def audit_call_records(registered: dict, records: list, copies: list) -> dict:
    """共用审计规则：登记的真实启动与实际记录、副本必须一一对应。"""
    copy_paths = {item["copy"] for item in copies}
    observed = {item["batch"] for item in records}
    registered_paths = set(registered)
    missing = sorted(path for path in registered_paths if path not in observed)
    unregistered = sorted(path for path in observed if path not in registered_paths)
    return {"registered": len(registered_paths), "records": len(observed),
            "missing": missing, "unregistered": unregistered,
            "verdict": "PASS" if not missing and not unregistered else "FAIL",
            "copies": len(copy_paths)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TASK-013 只读规则筛查验证入口")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--smoke", action="store_true",
                        help="开发期定向小样：跳过 MAIN 业务基准与阶段 2—9（仅供轮内定向验证，"
                             "正式验收仍运行完整入口）")
    parser.add_argument("--only-g10", action="store_true",
                        help="开发期定向小样：只运行 G10-R3（F01／F02／F03）")
    args = parser.parse_args(argv)
    smoke = bool(args.smoke or args.only_g10)

    container = Path(args.out_dir).resolve()
    container.mkdir(parents=True, exist_ok=True)
    (container / "cli_logs").mkdir(exist_ok=True)
    batch_parent = BATCHES_ROOT / container.name
    batch_parent.mkdir(parents=True, exist_ok=True)
    sqlite_parent = SQLITE_ROOT / container.name
    sqlite_parent.mkdir(parents=True, exist_ok=True)

    checks: list = []
    failures: list = []
    cli_logs: list = []
    copy_records: list = []
    probe_records: list = []
    api_events: list = []
    controller_events: list = []
    core_events: list = []
    expected_starts: dict = {}
    counts = {"start_cli": 0, "status_cli": 0, "record_cli": 0, "prepare_cli": 0,
              "record_gate2_cli": 0, "screen_cli": 0, "public_api_calls_inproc": 0,
              "controller_create_inproc": 0, "controller_prepare_inproc": 0,
              "controller_record_inproc": 0, "controller_check_inproc": 0,
              "controller_all_inproc": 0, "controller_check_record_subset_inproc": 0,
              "screen_core_calls_inproc": 0, "screen_core_calls_inproc_host": 0,
              "screen_core_calls_inproc_test_direct": 0,
              "screen_cli_success": 0, "screen_cli_precondition_rejected": 0,
              "screen_cli_runtime_failed": 0,
              "receiver_starts": 0, "checker_runs": 0, "copies": 0, "fault_injections": 0,
              "simulated_decisions": 0, "real_approvals": 0}
    core_call_records: list = []
    core_returns_dir = container / "core_returns"
    # 单列自测容器：正式 failures 不因自测判定而变红（自测不合格会在对应正式组里另记问题）
    self_tests: dict = {}
    g8_problems: list = []

    protected_before = {rel: sha256(PROJECT_ROOT / rel) for rel in PROTECTED_FILES}

    # ------------------------------------------------------------------ helpers
    def batch_path(name: str) -> Path:
        return batch_parent / name

    def database_path(batch_dir: Path) -> Path:
        relative = Path(batch_dir).resolve().relative_to(BATCHES_ROOT.resolve())
        return SQLITE_ROOT / relative / "audit.sqlite3"

    def register_start(batch_dir) -> None:
        relative = str(Path(batch_dir).resolve().relative_to(PROJECT_ROOT))
        expected_starts[relative] = {"batch": relative}

    def register_copy(destination: Path, source: Path, case: str) -> None:
        counts["copies"] += 1
        copy_records.append({"copy": str(destination.relative_to(PROJECT_ROOT)),
                             "source": str(source.relative_to(PROJECT_ROOT)), "case": case,
                             "kind": "fault_copy", "note": "副本不计真实接收/checker/筛查调用"})

    def copy_batch(leaf: str, source: Path) -> Path:
        destination = batch_parent / leaf / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        register_copy(destination, source, leaf)
        return destination

    def run_cli(label: str, sub_args: list, expect_exit: int) -> dict:
        command = [str(PYTHON), "-B", str(HOST_PATH), *sub_args]
        completed = subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        stdout_path = container / "cli_logs" / f"{len(cli_logs) + 1:03d}_{label}.stdout.txt"
        stderr_path = container / "cli_logs" / f"{len(cli_logs) + 1:03d}_{label}.stderr.txt"
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
        entry = {"label": label, "command": command, "exit_code": completed.returncode,
                 "expect_exit": expect_exit, "payload": payload,
                 "stdout_path": str(stdout_path.relative_to(container)),
                 "stderr_path": str(stderr_path.relative_to(container)),
                 "ok": completed.returncode == expect_exit}
        cli_logs.append(entry)
        command_name = sub_args[0] if sub_args else ""
        counters = {"start": "start_cli", "status": "status_cli",
                    "record-simulated-decision": "record_cli", "prepare-gate2": "prepare_cli",
                    "record-simulated-gate2-decision": "record_gate2_cli",
                    "screen-rules": "screen_cli"}
        if command_name in counters:
            counts[counters[command_name]] += 1
        if command_name == "screen-rules":
            if completed.returncode == 0:
                counts["screen_cli_success"] += 1
            elif completed.returncode == 1:
                counts["screen_cli_precondition_rejected"] += 1
            else:
                counts["screen_cli_runtime_failed"] += 1
        if command_name == "start":
            target = Path(sub_args[sub_args.index("--batch-dir") + 1]).resolve()
            if target.exists():
                counts["receiver_starts"] += 1
                register_start(target)
                manifest = target / "batch_manifest.json"
                if manifest.is_file():
                    try:
                        if (json.loads(manifest.read_text(encoding="utf-8"))
                                .get("checker_invocation", {}).get("started") is True):
                            counts["checker_runs"] += 1
                    except json.JSONDecodeError:
                        pass
        print(f"    CLI {label}: exit={completed.returncode}（期望 {expect_exit}）")
        return entry

    def write_decision(batch_dir: Path, revision: int, gate: str, decision_value: str, event_id: str) -> Path:
        payload = json.loads((batch_dir / "workflow/checkpoints" / f"{revision:04d}.json")
                             .read_text(encoding="utf-8"))
        request = payload["workflow"]["state"]["requests"][gate]
        body = {"event_id": event_id, "batch_id": batch_dir.name, "gate": gate,
                "request_id": request["request_id"],
                "materials_sha256": request["materials_sha256"], "decision": decision_value,
                "actor_kind": "SIMULATED_HUMAN", "actor_id": "tester-01",
                "occurred_at": "2026-10-12T10:00:00+08:00",
                "reason": "TASK-013 测试入口模拟决定（开发态，非真实批准）",
                "simulation": "SIMULATED_TEST_ONLY",
                "confirmations": ({"scope_and_source_reviewed": True} if gate == "GATE1"
                                  else {"reconciliation_reviewed": True})}
        path = container / f"decision_{batch_dir.name}_{gate.lower()}_{decision_value.lower()}_{event_id}.json"
        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        counts["simulated_decisions"] += 1
        return path

    def chain_to_approved(name: str, workbook: Path, label: str) -> Path:
        """CLI（逐进程）走到 DEV_GATE2_APPROVED。"""
        target = batch_path(name)
        run_cli(f"{label}_start", ["start", "--workbook", str(workbook), "--batch-dir", str(target),
                                   "--source-description", f"TASK-013 {name}（合成数据）"], 0)
        run_cli(f"{label}_g1", ["record-simulated-decision", "--batch-dir", str(target),
                                "--decision-file", str(write_decision(target, 1, "GATE1", "APPROVE",
                                                                      f"EVT-{name}-G1"))], 0)
        run_cli(f"{label}_prepare", ["prepare-gate2", "--batch-dir", str(target)], 0)
        run_cli(f"{label}_g2", ["record-simulated-gate2-decision", "--batch-dir", str(target),
                                "--decision-file", str(write_decision(target, 3, "GATE2", "APPROVE",
                                                                      f"EVT-{name}-G2"))], 0)
        return target

    def chain_to_gate2_pending(name: str, workbook: Path, label: str) -> Path:
        """CLI（逐进程）走到 DEV_GATE2_PENDING（Gate2 决定之前）。"""
        target = batch_path(name)
        run_cli(f"{label}_start", ["start", "--workbook", str(workbook), "--batch-dir", str(target),
                                   "--source-description", f"TASK-013 {name}（合成数据）"], 0)
        run_cli(f"{label}_g1", ["record-simulated-decision", "--batch-dir", str(target),
                                "--decision-file", str(write_decision(target, 1, "GATE1", "APPROVE",
                                                                      f"EVT-{name}-G1"))], 0)
        run_cli(f"{label}_prepare", ["prepare-gate2", "--batch-dir", str(target)], 0)
        return target

    def screen_cli(name: str, target: Path, label: str, expect: int = 0) -> dict:
        return run_cli(label, ["screen-rules", "--batch-dir", str(target)], expect)

    def expect_blocked(entry: dict, targets: list) -> tuple:
        payload = entry.get("payload") or {}
        message = str(payload.get("message") or "")
        ok = (entry["exit_code"] == 1 and payload.get("exception_class") == "WorkflowHostBlocked"
              and any(token in message for token in targets))
        return ok, message

    def record_probe_file(root: Path, case: str, payload: dict) -> Path:
        """把探针完整记录（完整实参/返回/异常链/前后值）落盘并读回核对，供独立核验。"""
        directory = root / "probe_records"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{case}.json"
        text_out = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        path.write_bytes(text_out.encode("utf-8"))
        readback = json.loads(path.read_text(encoding="utf-8"))
        assert canonical_sha256(readback) == canonical_sha256(payload), f"{case}: 探针记录读回不一致"
        return path

    def _full_exception(exc) -> dict:
        """完整异常现场：类别、消息、stage、reasons、直接 cause 链与逐帧 traceback。"""
        import traceback as _tb
        chain = []
        node = exc
        seen = set()
        while node is not None and len(chain) < 6 and id(node) not in seen:
            seen.add(id(node))
            chain.append({"class": type(node).__name__, "message": str(node),
                          "stage": getattr(node, "stage", None),
                          "reasons": [str(x) for x in (getattr(node, "reasons", []) or [])]})
            node = node.__cause__ if node.__cause__ is not None else node.__context__
        return {
            "class": type(exc).__name__,
            "message": str(exc),
            "stage": getattr(exc, "stage", None),
            "reasons": [str(x) for x in (getattr(exc, "reasons", []) or [])],
            "cause_chain": chain,
            "traceback_frames": [f"{fr.filename}:{fr.lineno}:{fr.name}"
                                 for fr in _tb.extract_tb(exc.__traceback__)],
        }

    def record(case: str, kind: str, problems: list, **extra) -> None:
        detail = {"case": case, "kind": kind, "result": "PASS" if not problems else "FAIL",
                  "problems": problems, **extra}
        checks.append(detail)
        if problems:
            failures.append(detail)
        print(f"[{'PASS' if not problems else 'FAIL'}] {case}"
              + ("" if not problems else f" | {problems[:2]}"))

    # ------------------------------------------- in-process instrumentation (观察层)
    def instrument():
        for name in ("start_dev_batch", "inspect_dev_batch", "prepare_dev_gate2",
                     "record_simulated_gate1_decision", "record_simulated_gate2_decision",
                     "screen_dev_batch"):
            original = getattr(host, name)

            def wrapper(*args, _name=name, _original=original, **kwargs):
                event = {"entry": _name, "phase": "enter"}
                api_events.append(event)
                counts["public_api_calls_inproc"] += 1
                try:
                    result = _original(*args, **kwargs)
                    event["outcome"] = "returned"
                    return result
                except BaseException as exc:  # noqa: BLE001
                    event["outcome"] = type(exc).__name__
                    raise
            setattr(host, name, wrapper)
        controller_functions = {
            "create_dev_workflow": "controller_create_inproc",
            "prepare_dev_gate": "controller_prepare_inproc",
            "record_dev_decision": "controller_record_inproc",
            "check_dev_action": "controller_check_inproc",
        }
        for name, counter in controller_functions.items():
            original = getattr(host.CONTROLLER_MODULE, name)

            def wrapper(*args, _name=name, _counter=counter, _original=original, **kwargs):
                event = {"entry": _name, "kind": "controller"}
                controller_events.append(event)
                counts[_counter] += 1
                counts["controller_all_inproc"] += 1
                if _name in ("check_dev_action", "record_dev_decision"):
                    counts["controller_check_record_subset_inproc"] += 1
                try:
                    result = _original(*args, **kwargs)
                    event["outcome"] = "returned"
                    return result
                except BaseException as exc:  # noqa: BLE001
                    event["outcome"] = type(exc).__name__
                    raise
            setattr(host.CONTROLLER_MODULE, name, wrapper)
        original_core = host.SCREEN_MODULE.screen_sqlite

        def _core_caller():
            """区分宿主执行与测试直接比较：按调用栈里是否出现 screen_dev_batch。"""
            frame = inspect.currentframe()
            try:
                while frame is not None:
                    if frame.f_code.co_name == "screen_dev_batch":
                        return "host"
                    frame = frame.f_back
                return "test_direct"
            finally:
                del frame

        def core_wrapper(*args, **kwargs):
            caller = _core_caller()
            database_path = str(args[0]) if args else str(kwargs.get("database_path"))
            event = {"entry": "screen_sqlite", "kind": "screen_core", "caller": caller,
                     "database_path": database_path, "phase": "enter"}
            core_events.append(event)
            counts["screen_core_calls_inproc"] += 1
            counts["screen_core_calls_inproc_host" if caller == "host"
                   else "screen_core_calls_inproc_test_direct"] += 1
            try:
                result = original_core(*args, **kwargs)
                event["outcome"] = "returned"
                core_returns_dir.mkdir(parents=True, exist_ok=True)
                index = len(core_call_records) + 1
                payload_text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
                payload_path = core_returns_dir / f"{index:02d}_{caller}.json"
                payload_path.write_bytes(payload_text.encode("utf-8"))
                core_call_records.append({
                    "index": index, "caller": caller, "database_path": database_path,
                    "return_path": str(payload_path.relative_to(container)),
                    "return_file_sha256": sha256(payload_path),
                    "return_canonical_sha256": canonical_sha256(result),
                    "findings_total": len((result or {}).get("findings") or []),
                })
                event["return_canonical_sha256"] = canonical_sha256(result)
                return result
            except BaseException as exc:  # noqa: BLE001
                event["outcome"] = type(exc).__name__
                raise
        host.SCREEN_MODULE.screen_sqlite = core_wrapper

    instrument()

    # ------------------------------------------------------------------- G1 MAIN
    if smoke:
        print("    [定向小样] 跳过 G1 MAIN（--smoke／--only-g10）")
    else:
        g1_problems: list = []
        main_batch = chain_to_approved("main_01", MAIN_WORKBOOK, "g1_main")
        before = {rev: sha256(main_batch / "workflow/checkpoints" / f"{rev:04d}.json") for rev in (1, 2, 3, 4)}
        db_path = database_path(main_batch)
        db_before = sha256(db_path)
        try:
           g1_inproc_payload = host.screen_dev_batch(main_batch)
           entry = {"label": "g1_screen_inproc", "exit_code": 0, "payload": g1_inproc_payload,
                    "stdout_path": None, "stderr_path": None, "command": None}
        except host.WorkflowHostBlocked as exc:
           entry = {"label": "g1_screen_inproc", "exit_code": 1,
                    "payload": {"message": str(exc), "exception_class": "WorkflowHostBlocked"},
                    "stdout_path": None, "stderr_path": None, "command": None}
        except host.WorkflowHostError as exc:
           entry = {"label": "g1_screen_inproc", "exit_code": 2,
                    "payload": {"message": str(exc), "exception_class": "WorkflowHostError"},
                    "stdout_path": None, "stderr_path": None, "command": None}
        payload = entry.get("payload") or {}
        screening = payload.get("screening") or {}
        report_path = main_batch / SCREEN_REL / "screening_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        independent = host.SCREEN_MODULE.screen_sqlite(str(db_path), json.loads(
           (main_batch / "workflow/gate2/load_report.json").read_text(encoding="utf-8")),
           cutoff_date="2026-09-30")
        if entry["exit_code"] != 0:
           g1_problems.append(f"MAIN 筛查未成功：{str(payload.get('message'))[:160]}")
        if payload.get("phase") != "DEV_GATE2_APPROVED" or payload.get("screening_status") != "RULE_SCREEN_RECORDED":
           g1_problems.append(f"MAIN 筛查后状态不符：phase={payload.get('phase')!r} "
                              f"screening_status={payload.get('screening_status')!r}")
        if payload.get("next_step_allowed") is not False or payload.get("real_approvals") != 0:
           g1_problems.append("next_step_allowed 必须 false、真实批准必须 0")
        if canonical_sha256(report) != canonical_sha256(independent):
           g1_problems.append("宿主保存的报告与该次冻结核心实际返回不逐项相等")
        distribution = {rule: sum(1 for item in report["findings"] if item["rule_id"] == rule)
                       for rule in ("R01", "R02", "R03", "R04")}
        if len(report["findings"]) != 12 or distribution != {"R01": 3, "R02": 5, "R03": 2, "R04": 2}:
           g1_problems.append(f"MAIN 报告条数/分布不符：{len(report['findings'])} {distribution}")
        if report["statistics"]["r02_overpayment_total_cents"] != 1600000:
           g1_problems.append(f"R02 应付超额不符：{report['statistics']['r02_overpayment_total_cents']}")
        recon = report["overall_reconciliation"]
        if (recon["settled_pay_master_total"], recon["settled_refund_master_total"], recon["master_net"],
               recon["known_payable_link_net"], recon["missing_payable_link_net"]) != (
               267949329, 700000, 267249329, 266249329, 1000000):
           g1_problems.append(f"整体勾稽金额不符：{recon}")
        if sha256(db_path) != db_before:
           g1_problems.append("筛查改写了数据库字节")
        status = run_cli("g1_status", ["status", "--batch-dir", str(main_batch)], 0)
        status_payload = status.get("payload") or {}
        if status_payload.get("screening_status") != "RULE_SCREEN_RECORDED":
           g1_problems.append("新进程 status 未显示 RULE_SCREEN 完成")
        if (status_payload.get("screening") or {}).get("report_file_sha256") != screening.get("report_file_sha256"):
           g1_problems.append("status 的报告引用与筛查时不一致")
        if sha256(report_path) != payload["screening"]["report_file_sha256"]:
           g1_problems.append("status 期间报告文件被改写")
        for rev, digest in before.items():
           if sha256(main_batch / "workflow/checkpoints" / f"{rev:04d}.json") != digest:
               g1_problems.append(f"筛查改写了旧 checkpoint 000{rev}")
        # 证明“一次实际宿主调用并原样保存”：从观察层捕获宿主该次核心真实返回
        host_core_calls = [item for item in core_call_records
                          if item["caller"] == "host" and item["database_path"] == str(db_path)]
        test_direct_calls = [item for item in core_call_records
                            if item["caller"] == "test_direct" and item["database_path"] == str(db_path)]
        if len(host_core_calls) != 1:
           g1_problems.append(f"宿主应恰好真实调用筛查核心 1 次，实际 {len(host_core_calls)}")
        if host_core_calls and host_core_calls[0]["return_canonical_sha256"] != canonical_sha256(report):
           g1_problems.append("宿主保存的报告与宿主该次真实核心返回不严格相等（不得伪造核心返回）")
        if not test_direct_calls:
           g1_problems.append("缺少同输入独立再调用对照")
        g1_probes = [
           {"case": "g1_host_core_real_return", "caller": "host",
            "call": host_core_calls[0] if host_core_calls else None,
            "on_disk_report_canonical_sha256": canonical_sha256(report),
            "matches_on_disk_report": bool(host_core_calls) and host_core_calls[0][
                "return_canonical_sha256"] == canonical_sha256(report),
            "ok": len(host_core_calls) == 1},
           {"case": "g1_independent_reinvocation",
            "note": "同一输入的第二次直接核心调用（test_direct），仅作业务口径对照，不是宿主那次调用",
            "call": test_direct_calls[0] if test_direct_calls else None,
            "matches_on_disk_report": bool(test_direct_calls) and test_direct_calls[0][
                "return_canonical_sha256"] == canonical_sha256(report),
            "ok": bool(test_direct_calls)},
        ]
        record("G1_MAIN_FULL_FLOW", "flow", g1_problems,
              counts={"findings": len(report["findings"]), "distribution": distribution,
                      "r02_overpayment": report["statistics"]["r02_overpayment_total_cents"]},
              screening=screening, probes=g1_probes,
              host_core_real_calls=len(host_core_calls), test_direct_reinvocations=len(test_direct_calls))

    if smoke:
        print("    [定向小样] 跳过 G2—G9（--smoke／--only-g10）")
    else:
        # ------------------------------------------- G2 三个既有小样正向边界
        g2_problems: list = []
        samples = {}
        for name, fixture, checks_fn in (
                ("c03_merged", "C03.xlsx", "merged"),
                ("c07b_missing", "C07b.xlsx", "missing"),
                ("c06b_refund", "C06b.xlsx", "refund")):
            target = chain_to_approved(name, GENERATED / "fixtures" / fixture, f"g2_{name}")
            entry = screen_cli(name, target, f"g2_{name}_screen", 0)
            payload = entry.get("payload") or {}
            report = json.loads((target / SCREEN_REL / "screening_report.json").read_text(encoding="utf-8"))
            samples[name] = {"findings": len(report["findings"]),
                             "recon": report["overall_reconciliation"],
                             "distribution": {rule: sum(1 for item in report["findings"]
                                                        if item["rule_id"] == rule)
                                              for rule in ("R01", "R02", "R03", "R04")},
                             "exit": entry["exit_code"], "phase": payload.get("phase")}
            if entry["exit_code"] != 0 or payload.get("screening_status") != "RULE_SCREEN_RECORDED":
                g2_problems.append(f"{name} 筛查未成功")
            if checks_fn == "merged" and report["findings"]:
                g2_problems.append(f"C03 合并付款不应有命中，实际 {len(report['findings'])}")
            if checks_fn == "merged" and report["overall_reconciliation"]["settled_pay_master_total"] > 10000000:
                g2_problems.append("C03 金额疑似翻倍")
            if checks_fn == "missing":
                if not any(item["rule_id"] == "R03" for item in report["findings"]):
                    g2_problems.append("C07b 应保留 R03 未匹配关联线索")
                if report["overall_reconciliation"]["missing_payable_link_net"] <= 0:
                    g2_problems.append("C07b 缺失关联净额应保留非零")
            if checks_fn == "refund":
                if report["overall_reconciliation"]["settled_refund_master_total"] <= 0:
                    g2_problems.append("C06b 退款净额应保留")
                if not any(item["evidence"].get("entities") for item in report["findings"]):
                    g2_problems.append("C06b 命中应保留退款/实体证据")
        record("G2_SMALL_SAMPLES", "flow", g2_problems, samples=samples)

        # --------------------------------------------- G3 阶段与重复拒绝（核心调用 0）
        g3_problems: list = []
        core_before = len(core_events)
        # 另建批次停在 Gate2 pending（Gate2 决定之前）
        g3_gate2_pending = chain_to_gate2_pending("g3_gate2_pending", MAIN_WORKBOOK, "g3_g2p")
        # Gate1 pending 批次
        g3_gate1_pending = batch_path("g3_gate1_pending")
        run_cli("g3_g1p_start", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir", str(g3_gate1_pending),
                                 "--source-description", "TASK-013 G3（Gate1 pending）"], 0)
        # Gate2 HOLD / REJECT：在 Gate2 pending 上记录，再验证不得筛查
        hold_batch = chain_to_gate2_pending("g3_hold", MAIN_WORKBOOK, "g3_hold")
        hold_entry = run_cli("g3_hold_record", ["record-simulated-gate2-decision", "--batch-dir", str(hold_batch),
                                                "--decision-file", str(write_decision(hold_batch, 3, "GATE2", "HOLD",
                                                                                      "EVT-g3hold"))], 0)
        if hold_entry["exit_code"] != 0 or (hold_entry.get("payload") or {}).get("phase") != "DEV_GATE2_HELD":
            g3_problems.append(f"HOLD 记录未生效：{hold_entry['exit_code']} "
                               f"{(hold_entry.get('payload') or {}).get('phase')}")
        reject_batch = chain_to_gate2_pending("g3_reject", MAIN_WORKBOOK, "g3_reject")
        reject_entry = run_cli("g3_reject_record", ["record-simulated-gate2-decision",
                                                    "--batch-dir", str(reject_batch),
                                                    "--decision-file", str(write_decision(reject_batch, 3, "GATE2",
                                                                                          "REJECT", "EVT-g3reject"))], 0)
        if reject_entry["exit_code"] != 0 or (reject_entry.get("payload") or {}).get("phase") != "DEV_GATE2_REJECTED":
            g3_problems.append(f"REJECT 记录未生效：{reject_entry['exit_code']} "
                               f"{(reject_entry.get('payload') or {}).get('phase')}")
        rejections = []
        for label, target in (("gate1_pending", g3_gate1_pending), ("gate2_pending", g3_gate2_pending),
                              ("gate2_held", hold_batch), ("gate2_rejected", reject_batch)):
            before_tree = tree_hashes(target)
            entry = screen_cli(label, target, f"g3_{label}", 1)
            ok, message = expect_blocked(entry, ["checkpoint", "phase", "筛查"])
            if not ok:
                g3_problems.append(f"{label} 未被拒绝或原因不符：exit={entry['exit_code']} {message[:120]}")
            if (target / SCREEN_REL).exists():
                g3_problems.append(f"{label} 拒绝时不应创建筛查目录")
            if tree_hashes(target) != before_tree:
                g3_problems.append(f"{label} 拒绝前后文件字节发生变化")
            rejections.append({"case": label, "exit": entry["exit_code"], "message": message[:160]})
        # 重复筛查
        repeat = screen_cli("main_repeat", main_batch, "g3_repeat", 1)
        ok, message = expect_blocked(repeat, ["screening", "0005", "筛查"])
        if not ok:
            g3_problems.append(f"重复筛查未被拒绝：{message[:140]}")
        if len(sorted(main_batch.rglob("0006.json"))) != 0:
            g3_problems.append("重复筛查不得新增 0006")
        if len(core_events) != core_before:
            g3_problems.append("拒绝场景不得调用筛查核心")
        record("G3_PRECONDITIONS_AND_REPEAT", "flow", g3_problems, rejections=rejections)

        # --------------------------------------------- G4 报告与引用篡改命中目标字段
        g4_problems: list = []
        g4_probes = []

        # 专供探针的独立批次（不做整批复制，避免路径派生把所有探针提前拦掉）
        g4_probe_batch = chain_to_approved("g4_probe", MAIN_WORKBOOK, "g4_probe")
        run_cli("g4_probe_screen", ["screen-rules", "--batch-dir", str(g4_probe_batch)], 0)

        def tamper_probe(leaf: str, mutate, targets: list, sync=None) -> None:
            touched = list(mutate.files(g4_probe_batch))
            backups = {path: (path.read_bytes() if path.exists() else None) for path in touched}
            before_hashes = {str(path): (sha256(path) if path.exists() else None) for path in touched}
            try:
                mutate(g4_probe_batch)
                if sync is not None:
                    sync(g4_probe_batch)
                counts["fault_injections"] += 1
                entry = run_cli(f"g4_{leaf}", ["status", "--batch-dir", str(g4_probe_batch)], 1)
                ok, message = expect_blocked(entry, targets)
                after_hashes = {str(path): (sha256(path) if path.exists() else None) for path in touched}
            finally:
                for path, data in backups.items():
                    if data is None:
                        if path.exists():
                            path.unlink()
                    else:
                        path.write_bytes(data)
            if not ok:
                g4_problems.append(f"{leaf} 未命中目标原因：exit={entry['exit_code']} {message[:140]}")
            restored = run_cli(f"g4_{leaf}_restored", ["status", "--batch-dir", str(g4_probe_batch)], 0)
            if restored["exit_code"] != 0:
                g4_problems.append(f"{leaf} 恢复原位后 status 未重新通过")
            g4_probes.append({"case": leaf, "exit": entry["exit_code"], "message": message[:200],
                              "targets": targets, "ok": ok, "injected": 1,
                              "changed_files": sorted(before_hashes),
                              "before_hashes": before_hashes, "after_hashes": after_hashes,
                              "restored_status_exit": restored["exit_code"],
                              "note": "专用探针批次内造样并即时恢复原位，不改历史批次"})

        def sync_0005_artifacts_file_hash(batch_dir: Path) -> None:
            """仅同步新副本内 0005 的 artifacts 文件哈希与内嵌对象（造样留痕）。"""
            checkpoint_path = batch_dir / "workflow/checkpoints/0005.json"
            payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            artifacts_path = batch_dir / SCREEN_REL / "artifacts.json"
            payload["operation"]["artifacts_file_sha256"] = sha256(artifacts_path)
            payload["operation"]["artifacts"] = json.loads(artifacts_path.read_text(encoding="utf-8"))
            checkpoint_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        def append_report_byte(batch_dir: Path) -> None:
            report = batch_dir / SCREEN_REL / "screening_report.json"
            report.write_bytes(report.read_bytes() + b" ")

        append_report_byte.files = lambda b: [b / SCREEN_REL / "screening_report.json"]

        def change_artifacts_report_hash(batch_dir: Path) -> None:
            path = batch_dir / SCREEN_REL / "artifacts.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["report_file_sha256"] = "0" * 64
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        change_artifacts_report_hash.files = lambda b: [b / SCREEN_REL / "artifacts.json",
                                                        b / "workflow/checkpoints/0005.json"]

        def zero_0005_previous(batch_dir: Path) -> None:
            path = batch_dir / "workflow/checkpoints/0005.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["previous_file_sha256"] = "0" * 64
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        zero_0005_previous.files = lambda b: [b / "workflow/checkpoints/0005.json"]

        def change_0005_workflow(batch_dir: Path) -> None:
            path = batch_dir / "workflow/checkpoints/0005.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            state = payload["workflow"]["state"]
            state["mode"] = "DEVELOPMENT_TEST_ONLY_CHANGED"
            payload["workflow"]["state_sha256"] = canonical_sha256(state)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        change_0005_workflow.files = lambda b: [b / "workflow/checkpoints/0005.json"]

        def add_unknown_0006(batch_dir: Path) -> None:
            (batch_dir / "workflow/checkpoints/0006.json").write_text("{}\n", encoding="utf-8")

        add_unknown_0006.files = lambda b: [b / "workflow/checkpoints/0006.json"]

        tamper_probe("g4_report_bytes", append_report_byte,
                     ["screening_report.json", "report_file_sha256"])
        tamper_probe("g4_artifacts_report_hash", change_artifacts_report_hash,
                     ["artifacts.json.report_file_sha256", "report_file_sha256"],
                     sync=sync_0005_artifacts_file_hash)
        tamper_probe("g4_0005_previous", zero_0005_previous, ["previous_file_sha256", "0005.json"])
        tamper_probe("g4_0005_workflow", change_0005_workflow, ["workflow", "0005.json"])
        tamper_probe("g4_unknown_0006", add_unknown_0006, ["0006.json", "拒绝未知项"])
        # 对照：整批副本的数据库路径派生不一致时必须拒绝（不冒称上游重算）
        copied = copy_batch("g4_copy_path_control", g4_probe_batch)
        counts["fault_injections"] += 1
        copy_entry = run_cli("g4_copy_path_control", ["status", "--batch-dir", str(copied)], 1)
        copy_ok, copy_message = expect_blocked(copy_entry, ["database_path", "output_relative", "artifacts.json"])
        if not copy_ok:
            g4_problems.append(f"副本路径派生不一致未被拒绝：{copy_message[:140]}")
        g4_probes.append({"case": "g4_copy_path_control", "exit": copy_entry["exit_code"],
                          "message": copy_message[:200], "ok": copy_ok,
                          "note": "整批副本的推导数据库路径与记录不一致 → 协议阻断（对照）"})
        record("G4_REPORT_AND_REFERENCE_TAMPERING", "flow", g4_problems, probes=g4_probes)

        # ------------------------------------------- G5 真实失败现场（部分写入与 failure 优先）
        g5_problems: list = []
        g5_probes = []

        # (a) 0005 部分写入
        partial_batch = chain_to_approved("g5_partial", MAIN_WORKBOOK, "g5_partial")
        real_writer = host._write_exclusive_json
        real_open = builtins.open
        sentinel = "SENTINEL-T13-PARTIAL-0005"
        state = {"target": partial_batch / "workflow/checkpoints/0005.json", "opens": 0, "writes": 0,
                 "raises": 0, "full_text": None, "proxy": None}

        class FaultyHandle:
            def __init__(self, handle, limit):
                self._handle = handle
                self._remaining = limit
                self.bytes_written = 0

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self._handle.close()
                return False

            def write(self, text):
                if state["full_text"] is None:
                    state["full_text"] = text
                chunk = text[: self._remaining]
                self._handle.write(chunk)
                self._remaining -= len(chunk)
                self.bytes_written += len(chunk)
                state["writes"] += 1
                if self._remaining <= 0:
                    state["raises"] += 1
                    raise OSError(sentinel)
                return len(chunk)

            def __getattr__(self, name):
                return getattr(self._handle, name)

        def faulty_open(file, mode="r", *a, **kw):
            handle = real_open(file, mode, *a, **kw)
            try:
                is_target = Path(file) == state["target"] and "x" in mode
            except TypeError:
                is_target = False
            if is_target:
                state["opens"] += 1
                state["proxy"] = FaultyHandle(handle, 40)
                return state["proxy"]
            return handle

        old_hashes = {rev: sha256(partial_batch / "workflow/checkpoints" / f"{rev:04d}.json")
                      for rev in (1, 2, 3, 4)}
        builtins.open = faulty_open
        counts["fault_injections"] += 1
        partial_exception = None
        try:
            host.screen_dev_batch(partial_batch)
            partial_outcome = "ok"
        except host.WorkflowHostError as exc:
            partial_outcome, partial_exception = "error", exc
        except host.WorkflowHostBlocked as exc:
            partial_outcome, partial_exception = "blocked", exc
        finally:
            builtins.open = real_open
        half = state["target"]
        half_bytes = half.stat().st_size if half.is_file() else 0
        full_text = state["full_text"] or ""
        full_bytes = len(full_text.encode("utf-8")) if full_text else 0
        full_text_path = container / "g5_writer_full_expected_0005.json"
        full_text_path.write_bytes(full_text.encode("utf-8"))
        full_text_sha = sha256(full_text_path)
        full_text_parses = False
        if full_text:
            try:
                parsed_full = json.loads(full_text)
                full_text_parses = isinstance(parsed_full, dict) and set(parsed_full) >= {
                    "checkpoint_version", "revision", "previous_file_sha256", "batch_id",
                    "host_manifest_file_sha256", "workflow", "operation"}
            except json.JSONDecodeError:
                full_text_parses = False
        complete_bytes = len(json.dumps(json.loads((partial_batch / "workflow/checkpoints/0004.json")
                                                    .read_text(encoding="utf-8")),
                                        ensure_ascii=False, indent=2).encode("utf-8"))
        old_hashes_after = {rev: sha256(partial_batch / "workflow/checkpoints" / f"{rev:04d}.json")
                            for rev in (1, 2, 3, 4)}
        cause = partial_exception.__cause__ if isinstance(partial_exception, host.WorkflowHostError) else None
        cause_chain = (traceback.format_exception(type(partial_exception), partial_exception,
                                                  partial_exception.__traceback__)
                       if partial_exception is not None else [])
        cause_chain_text = "".join(cause_chain)
        partial_ok = (state["opens"] == 1 and state["writes"] == 1 and state["raises"] == 1
                      and 0 < half_bytes < full_bytes and partial_outcome != "ok"
                      and full_text_parses and full_bytes > 0
                      and isinstance(cause, OSError) and str(cause) == sentinel
                      and "OSError" in cause_chain_text and sentinel in cause_chain_text
                      and old_hashes_after == old_hashes
                      and (partial_batch / SCREEN_REL / "failure.json").is_file())
        if not partial_ok:
            g5_problems.append(f"0005 部分写入未按预期处理：outcome={partial_outcome} opens={state['opens']} "
                               f"writes={state['writes']} raises={state['raises']} half={half_bytes} full={full_bytes}")
        later = run_cli("g5_partial_status", ["status", "--batch-dir", str(partial_batch)], None)
        if later["exit_code"] == 0:
            g5_problems.append("0005 部分写入后 status 不得返回成功")
        partial_record = {
            "case": "g5_partial_write_0005",
            "function": "host._write_exclusive_json（生产 writer，经真实 builtins.open 代理拦截）",
            "target_file": str(half),
            "injection_point": "第 5 份 checkpoint（0005.json）独占写入的底层 handle.write",
            "opens": state["opens"], "writes": state["writes"], "raises": state["raises"],
            "partial_bytes": half_bytes, "full_utf8_bytes": full_bytes,
            "full_text_path": str(full_text_path.relative_to(container)),
            "full_text_file_sha256": full_text_sha, "full_text_parses_as_checkpoint": full_text_parses,
            "full_text_top_level_keys": sorted(json.loads(full_text).keys()) if full_text_parses else None,
            "reference_0004_file_bytes": complete_bytes,
            "exception_class": type(partial_exception).__name__ if partial_exception else None,
            "exception_message": str(partial_exception) if partial_exception else None,
            "cause_class": type(cause).__name__ if cause is not None else None,
            "cause_message": str(cause) if cause is not None else None,
            "sentinel": sentinel,
            "traceback": cause_chain,
            "old_0001_0004_sha256_before": old_hashes,
            "old_0001_0004_sha256_after": old_hashes_after,
            "old_checkpoints_unchanged": old_hashes_after == old_hashes,
            "partial_file_preserved": half.is_file(),
            "later_status_exit": later["exit_code"], "outcome": partial_outcome, "ok": partial_ok,
        }
        record_probe_file(container, "g5_partial_write_0005", partial_record)
        g5_probes.append({"case": "g5_partial_write_0005", "record": str(
            (container / "probe_records/g5_partial_write_0005.json").relative_to(container)),
            "record_sha256": sha256(container / "probe_records/g5_partial_write_0005.json"),
            "opens": state["opens"], "writes": state["writes"], "raises": state["raises"],
            "partial_bytes": half_bytes, "full_utf8_bytes": full_bytes,
            "old_checkpoints_unchanged": old_hashes_after == old_hashes,
            "later_status_exit": later["exit_code"], "ok": partial_ok})

        # (b) 完整 0005 写完后抛错 → failure 优先恢复
        throw_batch = chain_to_approved("g5_throw", MAIN_WORKBOOK, "g5_throw")
        writer_original = host._write_exclusive_json

        def writer_then_throw(path, payload, stage, _original=writer_original):
            result = _original(path, payload, stage)
            if Path(path).name == "0005.json":
                raise host.WorkflowHostError(f"注入：完整 0005 之后失败（{sentinel}）", stage="post_write_verify")
            return result

        host._write_exclusive_json = writer_then_throw
        counts["fault_injections"] += 1
        try:
            host.screen_dev_batch(throw_batch)
            throw_outcome = "ok"
        except host.WorkflowHostError as exc:
            throw_outcome = f"error: {str(exc)[:80]}"
        except host.WorkflowHostBlocked as exc:
            throw_outcome = f"blocked: {str(exc)[:80]}"
        finally:
            host._write_exclusive_json = writer_original
        throw_has_0005 = (throw_batch / "workflow/checkpoints/0005.json").is_file()
        throw_failure = throw_batch / SCREEN_REL / "failure.json"
        throw_status = run_cli("g5_throw_status", ["status", "--batch-dir", str(throw_batch)], 2)
        throw_ok = (throw_outcome != "ok" and throw_has_0005 and throw_failure.is_file()
                    and throw_status["exit_code"] == 2
                    and "SENTINEL-T13-PARTIAL-0005" in str((throw_status.get("payload") or {}).get("message")))
        if not throw_ok:
            g5_problems.append(f"完整 0005 后失败未按 failure 优先恢复：outcome={throw_outcome} "
                               f"0005={throw_has_0005} failure={throw_failure.is_file()} status={throw_status['exit_code']}")
        throw_record = {
            "case": "g5_complete_then_throw",
            "function": "host._write_exclusive_json 包装（真实 writer 先完成 0005，再抛 sentinel 错误）",
            "batch_dir": str(throw_batch),
            "outcome": throw_outcome, "0005_present": throw_has_0005,
            "failure_present": throw_failure.is_file(),
            "failure_document": (json.loads(throw_failure.read_text(encoding="utf-8"))
                                 if throw_failure.is_file() else None),
            "later_status_exit": throw_status["exit_code"],
            "later_status_payload": throw_status.get("payload"),
            "later_status_stdout_path": throw_status.get("stdout_path"),
            "later_status_stderr_path": throw_status.get("stderr_path"),
            "ok": throw_ok,
        }
        record_probe_file(container, "g5_complete_then_throw", throw_record)
        g5_probes.append({"case": "g5_complete_then_throw", "record": str(
            (container / "probe_records/g5_complete_then_throw.json").relative_to(container)),
            "outcome": throw_outcome, "0005_present": throw_has_0005,
            "failure_present": throw_failure.is_file(), "status_exit": throw_status["exit_code"],
            "ok": throw_ok})

        # (c) 非法 failure → 协议阻断（exit 1）
        failure_path = throw_batch / SCREEN_REL / "failure.json"
        failure_backup = failure_path.read_bytes()
        (throw_batch / SCREEN_REL / "failure.json").write_text("{ not json", encoding="utf-8")
        counts["fault_injections"] += 1
        broken_entry = run_cli("g5_broken_failure", ["status", "--batch-dir", str(throw_batch)], 1)
        failure_path.write_bytes(failure_backup)
        broken_ok, broken_message = expect_blocked(broken_entry, ["failure.json"])
        if not broken_ok:
            g5_problems.append(f"非法失败诊断未协议阻断：{broken_message[:140]}")
        g5_probes.append({"case": "g5_invalid_failure", "exit": broken_entry["exit_code"],
                          "message": broken_message[:160], "ok": broken_ok})
        record("G5_REAL_FAILURE_SCENES", "flow", g5_problems, probes=g5_probes)

        # ------------------------------------- G6 最终复测三探针（本次即拒绝）
        g6_problems: list = []
        g6_probes = []

        def with_last_action_mutation(mutate, action, screen_index, probe_target):
            """包装冻结 check_dev_action：按 SCREEN_AND_BUILD_FACTS 的**真实调用序号**改变现场。

            screen_index 为该入口内 SCREEN_AND_BUILD_FACTS 动作检查的序号（两个入口均为 2 次，
            即最后一次动作检查）；同时登记完整调用顺序与注入后的控制器调用数。
            """
            original = host.CONTROLLER_MODULE.check_dev_action
            state = {"screen_calls": 0, "all_calls": 0, "mutated": 0, "sequence": [],
                     "after_injection_calls": 0, "injected_after_screen_index": None,
                     "exception": None, "outcome": None, "public_entry": None,
                     "action_calls": []}

            def wrapper(workflow, name, **kwargs):
                result = original(workflow, name, **kwargs)
                state["all_calls"] += 1
                state["action_calls"].append({
                    "order": state["all_calls"], "action": name,
                    "kwargs_keys": sorted(kwargs.keys()),
                    "workflow_state_sha256": workflow.get("state_sha256"),
                    "workflow_phase": ((workflow.get("state") or {}).get("phase")),
                    "batch_id": ((workflow.get("state") or {}).get("batch_id")),
                    "returned": {"phase": result.get("phase"), "action": result.get("action"),
                                 "simulation_allowed": result.get("simulation_allowed"),
                                 "next_step_allowed": result.get("next_step_allowed")},
                })
                if name == "SCREEN_AND_BUILD_FACTS":
                    state["screen_calls"] += 1
                    state["sequence"].append({"order": state["all_calls"], "name": name,
                                              "screen_index": state["screen_calls"]})
                    if state["screen_calls"] == screen_index and state["mutated"] == 0 and mutate.ready():
                        mutate()
                        state["mutated"] += 1
                        state["injected_after_screen_index"] = state["screen_calls"]
                elif state["mutated"]:
                    state["after_injection_calls"] += 1
                if state["mutated"] and name == "SCREEN_AND_BUILD_FACTS" and \
                        state["screen_calls"] > (state["injected_after_screen_index"] or 0):
                    state["after_injection_calls"] += 1
                return result
            host.CONTROLLER_MODULE.check_dev_action = wrapper
            counts["fault_injections"] += 1
            try:
                if action == "screen":
                    try:
                        host.screen_dev_batch(probe_target)
                        outcome, message = "ok", ""
                    except host.WorkflowHostBlocked as exc:
                        outcome, message, state["exception"] = "blocked", str(exc), exc
                    except host.WorkflowHostError as exc:
                        outcome, message, state["exception"] = "error", str(exc), exc
                    code = 1 if outcome == "blocked" else (2 if outcome == "error" else 0)
                else:
                    try:
                        host.inspect_dev_batch(probe_target)
                        outcome, message, code = "ok", "", 0
                    except host.WorkflowHostBlocked as exc:
                        outcome, message, code, state["exception"] = "blocked", str(exc), 1, exc
                    except host.WorkflowHostError as exc:
                        outcome, message, code, state["exception"] = "error", str(exc), 2, exc
            finally:
                host.CONTROLLER_MODULE.check_dev_action = original
            return outcome, message, code, state

        # (a) 筛查提交入口：最后一次动作检查后改 0005
        probe_target = chain_to_approved("g6_tail_0005", MAIN_WORKBOOK, "g6_tail")
        tail_path = probe_target / "workflow/checkpoints/0005.json"

        captured_tail = {"before": None, "after": None, "at": None}

        def mutate_0005():
            # 真实 writer 已写出并关闭 0005；此处先取注入前的真实文件哈希，再改动
            captured_tail["before"] = sha256(tail_path)
            captured_tail["at"] = "写入并关闭 0005 之后、最后一次动作检查返回时"
            payload = json.loads(tail_path.read_text(encoding="utf-8"))
            payload["operation"]["at_utc"] = "2000-01-01T00:00:00+00:00"
            tail_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            captured_tail["after"] = sha256(tail_path)

        mutate_0005.ready = lambda: tail_path.is_file()
        outcome, message, code, state = with_last_action_mutation(mutate_0005, "screen", 2, probe_target)
        after_tail = sha256(tail_path) if tail_path.exists() else None
        before_tail = captured_tail["before"]
        tail_ok = (code == 1 and state["mutated"] == 1 and state["after_injection_calls"] == 0
                   and before_tail is not None and before_tail != after_tail
                   and "0005.json" in message and ("收尾" in message or "checkpoint" in message))
        if not tail_ok:
            g6_problems.append(f"0005 收尾变化未被本次调用拒绝：code={code} mutated={state['mutated']} {message[:140]}")
        later = run_cli("g6_tail_status", ["status", "--batch-dir", str(probe_target)], None)
        if later["exit_code"] == 0:
            g6_problems.append("撤销 wrapper 后 status 不得通过被改动的 0005")
        record_probe_file(container, "g6_tail_0005_change", {
            "case": "g6_tail_0005_change", "kind": "F02_tail",
            "function": "host.CONTROLLER_MODULE.check_dev_action 包装（公开入口 host.screen_dev_batch）",
            "public_entry": "host.screen_dev_batch",
            "arguments": {"batch_dir": str(probe_target)},
            "kwargs": {"batch_dir": str(probe_target)},
            "batch_dir": str(probe_target),
            "expect_exception_class": "WorkflowHostBlocked",
            "expect_target_reason": "0005.json",
            "injection_point": "第 2 次 SCREEN_AND_BUILD_FACTS 真实返回之后（最后一次动作检查）",
            "screen_calls": state["screen_calls"], "all_controller_calls": state["all_calls"],
            "hits": state["mutated"], "sequence": state["sequence"],
            "call_order": state["action_calls"],
            "after_injection_calls": state["after_injection_calls"],
            "changed_file": str(tail_path), "before_sha256": before_tail, "after_sha256": after_tail,
            "before_taken_at": captured_tail["at"], "mutated": state["mutated"],
            "exception": _full_exception(state["exception"]) if state.get("exception") else None,
            "exception_message_untruncated": message,
            "outcome": "blocked" if code == 1 else outcome, "code": code, "message": message,
            "later_cli": {"command": ["status", "--batch-dir", str(probe_target)],
                          "exit": later["exit_code"], "stdout_path": later.get("stdout_path"),
                          "stderr_path": later.get("stderr_path"),
                          "note": "保留改动现场、撤销 wrapper 后新进程 CLI 仍拒绝"},
            "restored_positive": {"note": "本探针使用 0005 专用批次，不恢复原件；恢复正向对照见"
                                          "G10-R3 的 r3_f02_* 探针"},
            "ok": tail_ok})
        g6_probes.append({"case": "g6_tail_0005_change", "code": code, "mutated": state["mutated"],
                          "after_injection_calls": state["after_injection_calls"],
                          "before": before_tail, "after": after_tail, "message": message[:200],
                          "record": "probe_records/g6_tail_0005_change.json",
                          "later_status_exit": later["exit_code"], "ok": tail_ok})

        # (b) status 入口：最后一次动作检查后改数据库
        db_probe = chain_to_approved("g6_db", MAIN_WORKBOOK, "g6_db")
        run_cli("g6_db_screen", ["screen-rules", "--batch-dir", str(db_probe)], 0)
        db_file = database_path(db_probe)
        before_db = sha256(db_file)

        def mutate_database():
            with open(db_file, "r+b") as handle:
                handle.seek(-1, os.SEEK_END)
                last = handle.read(1)
                handle.seek(-1, os.SEEK_END)
                handle.write(bytes([last[0] ^ 0xFF]))

        mutate_database.ready = lambda: db_file.is_file()

        db_capture = {"before": None, "at": None}
        mutate_database_original = mutate_database

        def mutate_database_timed():
            db_capture["before"] = sha256(db_file)
            db_capture["at"] = "status 最后一次 SCREEN 动作检查真实返回之后"
            mutate_database_original()

        mutate_database_timed.ready = lambda: db_file.is_file()
        outcome, message, code, state = with_last_action_mutation(mutate_database_timed, "status", 2, db_probe)
        after_db = sha256(db_file)
        db_ok = (code == 1 and state["mutated"] == 1 and state["after_injection_calls"] == 0
                 and db_capture["before"] is not None and db_capture["before"] != after_db
                 and "audit.sqlite3" in message)
        if not db_ok:
            g6_problems.append(f"status 收尾数据库变化未被本次调用拒绝：code={code} {message[:140]}")
        db_changed_cli = run_cli("g6_status_database_change_changed_cli",
                                 ["status", "--batch-dir", str(db_probe)], 1)
        mutate_database()  # 末字节 XOR 的逆变换即恢复原件
        db_restored_cli = run_cli("g6_status_database_change_restored_cli",
                                  ["status", "--batch-dir", str(db_probe)], 0)
        record_probe_file(container, "g6_status_database_change", {
            "case": "g6_status_database_change", "function": "host.CONTROLLER_MODULE.check_dev_action 包装",
            "public_entry": "host.inspect_dev_batch", "arguments": {"batch_dir": str(db_probe)},
            "batch_dir": str(db_probe),
            "expect_exception_class": "WorkflowHostBlocked", "expect_target_reason": "audit.sqlite3",
            "injection_point": "status 第 2 次 SCREEN_AND_BUILD_FACTS 真实返回之后",
            "screen_calls": state["screen_calls"], "all_controller_calls": state["all_calls"],
            "call_order": state["sequence"], "sequence": state["sequence"],
            "after_injection_calls": state["after_injection_calls"],
            "changed_file": str(db_file), "before_sha256": db_capture["before"], "after_sha256": after_db,
            "before_taken_at": db_capture["at"], "code": code, "message": message,
            "exception": _full_exception(state["exception"]) if state.get("exception") else None,
            "later_cli": {"command": ["status", "--batch-dir", str(db_probe)],
                          "exit_code": db_changed_cli["exit_code"],
                          "message": ((db_changed_cli.get("payload") or {}).get("message") or "")[:400],
                          "note": "保留改动现场、撤销 wrapper 后新进程 CLI 仍拒绝"},
            "restored_positive": {"exit_code": db_restored_cli["exit_code"],
                                 "phase": (db_restored_cli.get("payload") or {}).get("phase"),
                                 "note": "恢复原件后新进程 CLI 退出 0"},
            "ok": db_ok})
        g6_probes.append({"case": "g6_status_database_change", "code": code, "mutated": state["mutated"],
                          "after_injection_calls": state["after_injection_calls"],
                          "before": db_capture["before"], "after": after_db, "message": message[:200],
                          "record": "probe_records/g6_status_database_change.json", "ok": db_ok})

        # (c) status 入口：最后一次动作检查后改输入快照
        snap_probe = chain_to_approved("g6_snapshot", MAIN_WORKBOOK, "g6_snapshot")
        run_cli("g6_snapshot_screen", ["screen-rules", "--batch-dir", str(snap_probe)], 0)
        snapshot = snap_probe / "source/input.xlsx"
        before_snapshot = sha256(snapshot)

        def mutate_snapshot():
            snapshot.write_bytes(snapshot.read_bytes() + b"Z")

        snap_capture = {"before": None, "at": None}
        mutate_snapshot_original = mutate_snapshot

        def mutate_snapshot_timed():
            snap_capture["before"] = sha256(snapshot)
            snap_capture["at"] = "status 最后一次 SCREEN 动作检查真实返回之后"
            mutate_snapshot_original()

        mutate_snapshot_timed.ready = lambda: snapshot.is_file()
        outcome, message, code, state = with_last_action_mutation(mutate_snapshot_timed, "status", 2, snap_probe)
        after_snapshot = sha256(snapshot)
        snap_ok = (code == 1 and state["mutated"] == 1 and state["after_injection_calls"] == 0
                   and snap_capture["before"] is not None and snap_capture["before"] != after_snapshot
                   and ("input_sha256" in message or "source/input.xlsx" in message
                        or "绑定" in message or "bindings" in message))
        if not snap_ok:
            g6_problems.append(f"status 收尾快照变化未被本次调用拒绝：code={code} {message[:140]}")
        snap_changed_cli = run_cli("g6_status_snapshot_change_changed_cli",
                                   ["status", "--batch-dir", str(snap_probe)], 1)
        snapshot.write_bytes(snapshot.read_bytes()[:-1])  # 去掉注入时追加的字节，恢复原件
        snap_restored_cli = run_cli("g6_status_snapshot_change_restored_cli",
                                    ["status", "--batch-dir", str(snap_probe)], 0)
        record_probe_file(container, "g6_status_snapshot_change", {
            "case": "g6_status_snapshot_change", "function": "host.CONTROLLER_MODULE.check_dev_action 包装",
            "public_entry": "host.inspect_dev_batch", "arguments": {"batch_dir": str(snap_probe)},
            "batch_dir": str(snap_probe),
            "expect_exception_class": "WorkflowHostBlocked", "expect_target_reason": "input_sha256",
            "injection_point": "status 第 2 次 SCREEN_AND_BUILD_FACTS 真实返回之后（最后一次动作检查）",
            "screen_calls": state["screen_calls"], "all_controller_calls": state["all_calls"],
            "call_order": state["sequence"], "sequence": state["sequence"],
            "after_injection_calls": state["after_injection_calls"],
            "changed_file": str(snapshot), "before_sha256": snap_capture["before"],
            "after_sha256": after_snapshot, "before_taken_at": snap_capture["at"],
            "code": code, "message": message,
            "exception": _full_exception(state["exception"]) if state.get("exception") else None,
            "later_cli": {"command": ["status", "--batch-dir", str(snap_probe)],
                          "exit_code": snap_changed_cli["exit_code"],
                          "message": ((snap_changed_cli.get("payload") or {}).get("message") or "")[:400],
                          "note": "保留改动现场、撤销 wrapper 后新进程 CLI 仍拒绝"},
            "restored_positive": {"exit_code": snap_restored_cli["exit_code"],
                                 "phase": (snap_restored_cli.get("payload") or {}).get("phase"),
                                 "note": "恢复原件后新进程 CLI 退出 0"},
            "ok": snap_ok})
        g6_probes.append({"case": "g6_status_snapshot_change", "code": code, "mutated": state["mutated"],
                          "after_injection_calls": state["after_injection_calls"],
                          "before": snap_capture["before"], "after": after_snapshot,
                          "message": message[:200],
                          "record": "probe_records/g6_status_snapshot_change.json", "ok": snap_ok})

        # (d) 早期守卫探针（不能替代 G10-R3 的末次读取探针）：`_verify_screen_tail` 第一次返回后改报告
        f01_target = chain_to_approved("g6_f01_report", MAIN_WORKBOOK, "g6_f01")
        run_cli("g6_f01_screen", ["screen-rules", "--batch-dir", str(f01_target)], 0)
        f01_report = f01_target / SCREEN_REL / "screening_report.json"
        original_tail_fn = host._verify_screen_tail
        f01_state = {"calls": 0, "mutated": 0, "before": None, "after": None, "at": None,
                     "after_injection_calls": 0, "exception": None, "public_entry": None,
                     "batch_dir": str(f01_target)}

        def tail_wrapper(batch_dir, expected, stage, _original=original_tail_fn):
            result = _original(batch_dir, expected, stage)
            f01_state["calls"] += 1
            if f01_state["mutated"]:
                f01_state["after_injection_calls"] += 1
            elif f01_state["calls"] == 1:
                # 早期守卫：这是 status 里第一次 _verify_screen_tail 返回，其后还有
                # 第二次 _read_screen_outputs 与最终复测；因此只是早期守卫，不是末次读取边界。
                f01_state["before"] = sha256(f01_report)
                f01_state["at"] = "早期守卫：status 第一次 _verify_screen_tail 返回之后"
                payload = json.loads(f01_report.read_text(encoding="utf-8"))
                payload["findings"] = []
                f01_report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
                f01_state["after"] = sha256(f01_report)
                f01_state["mutated"] += 1
            return result

        host._verify_screen_tail = tail_wrapper
        counts["fault_injections"] += 1
        try:
            host.inspect_dev_batch(f01_target)
            f01_outcome, f01_message, f01_code = "ok", "", 0
        except host.WorkflowHostBlocked as exc:
            f01_outcome, f01_message, f01_code, f01_state["exception"] = "blocked", str(exc), 1, exc
        except host.WorkflowHostError as exc:
            f01_outcome, f01_message, f01_code, f01_state["exception"] = "error", str(exc), 2, exc
        finally:
            host._verify_screen_tail = original_tail_fn
        f01_later = run_cli("g6_f01_status", ["status", "--batch-dir", str(f01_target)], None)
        f01_ok = (f01_code == 1 and f01_state["mutated"] == 1 and f01_state["before"] is not None
                  and f01_state["before"] != f01_state["after"]
                  and ("screening_report.json" in f01_message or "报告" in f01_message)
                  and f01_later["exit_code"] != 0)
        if not f01_ok:
            g6_problems.append(f"F01 报告边界变化未被本次 status 拒绝：code={f01_code} "
                               f"mutated={f01_state['mutated']} {f01_message[:140]}")
        record_probe_file(container, "g6_f01_report_tail_change", {
            "case": "g6_f01_report_tail_change", "kind": "early_guard",
            "function": "host._verify_screen_tail 包装（早期守卫，不是末次读取边界）",
            "guard_note": ("本探针在 status 第一次 _verify_screen_tail 返回后注入；其后宿主仍会执行"
                           "第二次 _read_screen_outputs 与最终复测，因此只是早期守卫，"
                           "不能替代 G10-R3 的 r3_f01_report_last_read 末次读取探针。"),
            "public_entry": "host.inspect_dev_batch", "arguments": {"batch_dir": str(f01_target)},
            "batch_dir": str(f01_target),
            "expect_exception_class": "WorkflowHostBlocked",
            "expect_target_reason": "screening_report.json",
            "injection_point": f01_state["at"], "verify_tail_calls": f01_state["calls"],
            "after_injection_tail_calls": f01_state["after_injection_calls"],
            "hits": f01_state["mutated"],
            "call_order": [{"order": 1, "entry": "_verify_screen_tail", "stage": "status",
                            "note": "第一次（早期守卫）返回后注入"},
                           {"order": 2, "entry": "_read_screen_outputs", "stage": "status",
                            "note": "第二次报告消费"},
                           {"order": 3, "entry": "_verify_screen_tail", "stage": "status",
                            "note": "最终复测（本次调用内发现变化）"}],
            "exception": _full_exception(f01_state["exception"]) if f01_state["exception"] else None,
            "exception_message_untruncated": f01_message,
            "changed_file": str(f01_report), "before_sha256": f01_state["before"],
            "after_sha256": f01_state["after"], "mutated": f01_state["mutated"],
            "changed_field": "findings → []（其余引用与 checkpoint 不变）",
            "outcome": f01_outcome, "code": f01_code, "message": f01_message,
            "later_cli": {"command": ["status", "--batch-dir", str(f01_target)],
                          "exit": f01_later["exit_code"], "stdout_path": f01_later.get("stdout_path"),
                          "stderr_path": f01_later.get("stderr_path"),
                          "note": "保留改动现场、撤销 wrapper 后新进程 CLI 仍拒绝"},
            "restored_positive": {"note": "本探针不使用副本、不改历史批次；恢复由 G10-R3 的"
                                          "r3_f01_* 探针在同一小样上单独证明"},
            "ok": f01_ok})
        g6_probes.append({"case": "g6_f01_report_tail_change", "code": f01_code,
                          "mutated": f01_state["mutated"], "before": f01_state["before"],
                          "after": f01_state["after"], "message": f01_message[:200],
                          "record": "probe_records/g6_f01_report_tail_change.json",
                          "later_status_exit": f01_later["exit_code"], "ok": f01_ok})
        record("G6_FINAL_TAIL_PROBES", "flow", g6_problems, probes=g6_probes)

        # ------------------------------------------------- G7 只读与隔离守卫
        g7_problems: list = []
        guard_batch = chain_to_approved("g7_clean", MAIN_WORKBOOK, "g7_clean")
        run_cli("g7_clean_screen", ["screen-rules", "--batch-dir", str(guard_batch)], 0)
        original_run = subprocess.run
        original_socket = None
        try:
            import socket as socket_module
            original_socket = socket_module.socket

            def forbidden_socket(*a, **kw):
                raise AssertionError("status 不得建立网络连接")
            socket_module.socket = forbidden_socket

            def forbidden_run(*a, **kw):
                raise AssertionError("status 不得启动子进程")
            subprocess.run = forbidden_run
            tree_before = tree_hashes(guard_batch)
            guard_payload = host.inspect_dev_batch(guard_batch)
            tree_after = tree_hashes(guard_batch)
            socket_module.socket = original_socket
            subprocess.run = original_run
        finally:
            subprocess.run = original_run
            if original_socket is not None:
                import socket as socket_module
                socket_module.socket = original_socket
        if tree_before != tree_after:
            g7_problems.append("status 只读守卫下批次文件发生变化")
        if guard_payload.get("screening_status") != "RULE_SCREEN_RECORDED":
            g7_problems.append("守卫下 status 未显示筛查完成")
        # 静态检查：不得调用独立复算／底稿／LLM，也不得读取答案册或生成器
        tree = ast.parse(HOST_PATH.read_text(encoding="utf-8"))
        imported = sorted({node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
                          | {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                             for alias in node.names})
        forbidden_calls = sorted({node.func.id for node in ast.walk(tree)
                                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                                  and node.func.id in ("crosscheck_rules", "build_fact_packet",
                                                       "run_crosscheck", "build_packet")})
        if forbidden_calls:
            g7_problems.append(f"宿主不得调用复算／底稿：{forbidden_calls}")
        nonzero = [name for name in imported
                   if name.split(".")[0] not in {"__future__", "argparse", "copy", "datetime", "hashlib",
                                                 "importlib", "json", "os", "pathlib", "re", "subprocess",
                                                 "sys", "builtins", "socket", "shutil", "ast", "time"}]
        if nonzero:
            g7_problems.append(f"宿主出现非标准库导入：{nonzero}")
        imported_modules = sorted(sys.modules)
        suspicious_modules = [name for name in imported_modules
                              if "crosscheck" in name.lower() or "fact_packet" in name.lower()
                              or "openai" in name.lower() or "llm" in name.lower()]
        if suspicious_modules:
            g7_problems.append(f"宿主运行期导入了复算／底稿／LLM 模块：{suspicious_modules}")
        # 运行期事实：本次筛选只调用了筛查核心，未调用复算／底稿
        if counts["screen_core_calls_inproc"] < 1:
            g7_problems.append("本次未观测到筛查核心真实调用")
        record("G7_READONLY_AND_ISOLATION_GUARDS", "flow", g7_problems,
               guarded={"tree_unchanged": tree_before == tree_after,
                        "screening_status": guard_payload.get("screening_status"),
                        "imports": imported, "forbidden_calls": forbidden_calls})

        # ------------------------------------------- G8 计数、审计与最终产物读回
        # ------------------------------- G8-R1 F02 引用/语义反例与 F03 失败身份
        r1_problems: list = []
        r1_probes: list = []
        probe_workbook = GENERATED / "fixtures" / "C02.xlsx"

        def screen_paths_of(batch_dir: Path) -> dict:
            directory = batch_dir / SCREEN_REL
            return {"dir": directory, "started": directory / "started.json",
                    "report": directory / "screening_report.json",
                    "artifacts": directory / "artifacts.json", "failure": directory / "failure.json",
                    "checkpoint": batch_dir / "workflow/checkpoints/0005.json"}

        def sync_0005_refs(batch_dir: Path) -> None:
            """把磁盘上 screening 产物的实际哈希与对象写回 0005.operation（仅为进入目标语义核验的造样）。"""
            paths = screen_paths_of(batch_dir)
            payload = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
            payload["operation"]["started_file_sha256"] = sha256(paths["started"])
            payload["operation"]["report_file_sha256"] = sha256(paths["report"])
            payload["operation"]["artifacts_file_sha256"] = sha256(paths["artifacts"])
            payload["operation"]["artifacts"] = json.loads(paths["artifacts"].read_text(encoding="utf-8"))
            paths["checkpoint"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")

        def sync_artifacts_started_hash(batch_dir: Path) -> None:
            paths = screen_paths_of(batch_dir)
            artifacts = json.loads(paths["artifacts"].read_text(encoding="utf-8"))
            artifacts["started_file_sha256"] = sha256(paths["started"])
            paths["artifacts"].write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")

        def f02_probe(leaf: str, case: str, mutate, targets: list, *, sync_0005: bool = True,
                      sync_artifacts_started: bool = False, extra_note: str = "") -> None:
            target = chain_to_approved(leaf, probe_workbook, f"r1_{leaf}")
            screen_entry = screen_cli(leaf, target, f"r1_{leaf}_screen", 0)
            paths = screen_paths_of(target)
            backups = {path: path.read_bytes() for path in (paths["checkpoint"], paths["started"],
                                                            paths["report"], paths["artifacts"])}
            before = sha256(paths["checkpoint"])
            mutate(target, paths)
            if sync_artifacts_started:
                sync_artifacts_started_hash(target)
            if sync_0005:
                sync_0005_refs(target)
            after = sha256(paths["checkpoint"])
            counts["fault_injections"] += 1
            entry = run_cli(f"r1_{leaf}_status", ["status", "--batch-dir", str(target)], 1)
            ok, message = expect_blocked(entry, targets)
            for path, data in backups.items():
                path.write_bytes(data)
            restored = run_cli(f"r1_{leaf}_restore", ["status", "--batch-dir", str(target)], 0)
            positive_ok = restored["exit_code"] == 0
            record_probe_file(container, case, {
                "case": case, "kind": "F02", "batch_dir": str(target),
                "screening_exit": screen_entry["exit_code"], "changed": extra_note,
                "checkpoint_sha256_before": before, "checkpoint_sha256_after_sync": after,
                "expected_targets": targets, "outcome": entry["payload"].get("exception_class")
                if entry.get("payload") else None, "exit": entry["exit_code"], "message": message,
                "stdout_path": entry.get("stdout_path"), "stderr_path": entry.get("stderr_path"),
                "restored_positive_exit": restored["exit_code"], "ok": ok and positive_ok,
            })
            r1_probes.append({"case": case, "kind": "F02", "exit": entry["exit_code"],
                              "message": message[:220], "targets": targets,
                              "restored_positive_exit": restored["exit_code"],
                              "record": f"probe_records/{case}.json", "ok": ok and positive_ok})
            if not (ok and positive_ok):
                r1_problems.append(f"{case} 未按目标字段阻断或恢复后未通过：exit={entry['exit_code']} "
                                   f"{message[:140]} restored={restored['exit_code']}")

        # P01：operation.report_relative 改为不存在的文件
        def p01_mutate(target: Path, paths: dict) -> None:
            payload = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
            payload["operation"]["report_relative"] = "workflow/screening/not_a_report.json"
            paths["checkpoint"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")

        f02_probe("p01_report_relative", "F02_P01_report_relative", p01_mutate,
                  ["report_relative"], sync_0005=False,
                  extra_note="0005.operation.report_relative → 不存在的文件（未改任何产物文件）")

        # P02：artifacts.host_manifest_file_sha256 改为 bindings 内容指纹
        def p02_mutate(target: Path, paths: dict) -> None:
            artifacts = json.loads(paths["artifacts"].read_text(encoding="utf-8"))
            checkpoint = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
            artifacts["host_manifest_file_sha256"] = checkpoint["workflow"]["state"]["run_bindings_sha256"]
            paths["artifacts"].write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")

        f02_probe("p02_manifest_bindings", "F02_P02_manifest_hash_bindings", p02_mutate,
                  ["host_manifest_file_sha256"],
                  extra_note="artifacts.host_manifest_file_sha256 → bindings 内容指纹（同步文件引用哈希）")

        # P03：artifacts.host_version 错
        def p03_mutate(target: Path, paths: dict) -> None:
            artifacts = json.loads(paths["artifacts"].read_text(encoding="utf-8"))
            artifacts["host_version"] = "WRONG-HOST-VERSION"
            paths["artifacts"].write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")

        f02_probe("p03_artifacts_version", "F02_P03_artifacts_host_version", p03_mutate,
                  ["host_version"], extra_note="artifacts.host_version → WRONG-HOST-VERSION")

        # P04：started.host_version 错
        def p04_mutate(target: Path, paths: dict) -> None:
            started = json.loads(paths["started"].read_text(encoding="utf-8"))
            started["host_version"] = "WRONG-HOST-VERSION"
            paths["started"].write_text(json.dumps(started, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")

        f02_probe("p04_started_version", "F02_P04_started_host_version", p04_mutate,
                  ["host_version"], sync_artifacts_started=True,
                  extra_note="started.host_version → WRONG-HOST-VERSION（同步 artifacts/0005 的文件引用）")

        # P05：0005.operation.artifacts.cutoff_date 与真实 artifacts 不一致
        def p05_mutate(target: Path, paths: dict) -> None:
            payload = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
            payload["operation"]["artifacts"]["cutoff_date"] = "1900-01-01"
            paths["checkpoint"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")

        f02_probe("p05_embedded_cutoff", "F02_P05_embedded_cutoff_mismatch", p05_mutate,
                  ["operation.artifacts"], sync_0005=False,
                  extra_note="仅 0005.operation.artifacts.cutoff_date → 1900-01-01（真实 artifacts 仍为 2026-09-30）")

        # P06-形状：operation.artifacts 缺失/非对象
        def p06_mutate(target: Path, paths: dict) -> None:
            payload = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
            payload["operation"]["artifacts"] = "not-an-object"
            paths["checkpoint"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")

        f02_probe("p06_embedded_shape", "F02_P06_embedded_artifacts_shape", p06_mutate,
                  ["operation.artifacts"], sync_0005=False,
                  extra_note="0005.operation.artifacts → 字符串（形状对照）")

        # F03：以真实 writer 生成的失败诊断为基线，四项有界检查
        failure_baseline = failure_path.read_bytes()
        failure_targets = {"missing_batch_id": ["batch_id"], "wrong_batch_id": ["batch_id"],
                           "wrong_host_version": ["host_version"],
                           "bool_exit_code": ["target_exit_code"]}
        for case_name, targets in failure_targets.items():
            payload = json.loads(failure_baseline)
            if case_name == "missing_batch_id":
                payload.pop("batch_id", None)
            elif case_name == "wrong_batch_id":
                payload["batch_id"] = "OTHER-BATCH"
            elif case_name == "wrong_host_version":
                payload["host_version"] = "WRONG-HOST-VERSION"
            else:
                payload["target_exit_code"] = True
            failure_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            counts["fault_injections"] += 1
            entry = run_cli(f"r1_f03_{case_name}", ["status", "--batch-dir", str(throw_batch)], 1)
            ok, message = expect_blocked(entry, targets)
            record_probe_file(container, f"F03_{case_name}", {
                "case": f"F03_{case_name}", "kind": "F03", "batch_dir": str(throw_batch),
                "failure_baseline_sha256": sha256(failure_path), "mutated_field": case_name,
                "expected_targets": targets, "exit": entry["exit_code"], "message": message,
                "stdout_path": entry.get("stdout_path"), "stderr_path": entry.get("stderr_path"),
                "ok": ok,
            })
            r1_probes.append({"case": f"F03_{case_name}", "kind": "F03", "exit": entry["exit_code"],
                              "message": message[:220], "targets": targets,
                              "record": f"probe_records/F03_{case_name}.json", "ok": ok})
            if not ok:
                r1_problems.append(f"F03 {case_name} 未按目标字段阻断：{message[:140]}")
        failure_path.write_bytes(failure_baseline)
        counts["fault_injections"] += 1
        restored_failure = run_cli("r1_f03_restored", ["status", "--batch-dir", str(throw_batch)], 2)
        restored_ok = (restored_failure["exit_code"] == 2
                       and sentinel in str((restored_failure.get("payload") or {}).get("message")))
        if not restored_ok:
            r1_problems.append("恢复合法失败诊断后未恢复原失败（不得降为 READY）")
        record_probe_file(container, "F03_restored_legal_failure", {
            "case": "F03_restored_legal_failure", "kind": "F03", "batch_dir": str(throw_batch),
            "failure_sha256": sha256(failure_path), "exit": restored_failure["exit_code"],
            "message": (restored_failure.get("payload") or {}).get("message"),
            "stdout_path": restored_failure.get("stdout_path"), "ok": restored_ok,
        })
        r1_probes.append({"case": "F03_restored_legal_failure", "kind": "F03",
                          "exit": restored_failure["exit_code"],
                          "record": "probe_records/F03_restored_legal_failure.json", "ok": restored_ok})

        record("G9_R1_PROTOCOL_REGRESSIONS", "flow", r1_problems, probes=r1_probes)

    # --------- G10-R3：F01 末次读取探针 + F02 after 时点与完整调用记录 + F03 七阶段完整判定
    r3_problems: list = []
    r3_probes: list = []


    def _tree(root: Path) -> dict:
        return {str(item.relative_to(root)): sha256(item)
                for item in sorted(root.rglob("*")) if item.is_file()}

    def big_reference(prefix: str, payload) -> dict:
        """大对象（完整 API 返回／完整实参／完整哈希集合）独立落盘并给相对路径与实际字节 SHA-256。"""
        text_out = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        path = container / f"{prefix}.json"
        path.write_bytes(text_out.encode("utf-8"))
        readback = json.loads(path.read_text(encoding="utf-8"))
        assert canonical_sha256(readback) == canonical_sha256(payload), f"{prefix}: 大对象引用读回不一致"
        return {"reference_relative_path": str(path.relative_to(PROJECT_ROOT)),
                "reference_container_relative": str(path.relative_to(container)),
                "file_bytes": path.stat().st_size, "file_sha256": sha256(path),
                "canonical_sha256": canonical_sha256(payload),
                "note": "完整内容独立落盘（未截断），此处只给相对路径与实际字节哈希"}

    def tree_reference(prefix: str, tree: dict) -> dict:
        return {**big_reference(prefix, tree), "entries": len(tree)}

    def call_trace_reference(prefix: str, label: str, value) -> dict:
        return {"label": label, **big_reference(prefix, value)}

    def finding_shape(report: dict) -> dict:
        items = report.get("findings") or []
        first = items[0] if items else None
        return {"findings_total": len(items),
                "first_finding_rule_id": (first or {}).get("rule_id") if isinstance(first, dict) else None,
                "first_finding_keys": sorted(first.keys()) if isinstance(first, dict) else None,
                "second_finding_rule_id": (items[1] or {}).get("rule_id") if len(items) > 1
                and isinstance(items[1], dict) else None}

    def public_trace(case: str, entry: str, batch_dir: Path, expect_class: str, expect_reason: str,
                     injection_point: str, trace: dict, *,
                     outcome: str, exc, result, cli_entry: dict | None = None,
                     extra: dict | None = None, reference: bool = False,
                     reference_prefix: str | None = None) -> dict:
        """F01/F02 探针的统一完整记录：公开入口、完整实参、完整读取/控制器顺序、真实前后值、
        完整异常（类别/消息/stage/reasons/cause 链/逐帧 traceback）、撤销后 CLI 与正向对照。"""
        evidence = probe_timing_verdict(trace)
        payload = {
            "case": case, "kind": "F01_F02",
            "public_entry": entry,
            "arguments": {"batch_dir": str(batch_dir)},
            "kwargs": {"batch_dir": str(batch_dir)},
            "batch_dir": str(batch_dir),
            "expect_exception_class": expect_class, "expect_target_reason": expect_reason,
            "injection_point": injection_point,
            "injection": {"hits": len(trace.get("writes") or []),
                          "injection_after_read_seq": evidence["injection_after_read_seq"],
                          "target_read_count": evidence["reads_total"],
                          "after_injection_reads": evidence["after_injection_reads"],
                          "after_injection_controllers": evidence["after_injection_controllers"],
                          "writes": trace.get("writes"), "reads": trace.get("reads"),
                          "controllers": trace.get("controllers"),
                          "ordered_events": evidence["ordered_events"]},
            "timing_verdict": evidence,
            "outcome": outcome,
            "exception": _full_exception(exc) if exc is not None else None,
            "exception_message_untruncated": (str(exc) if exc is not None else None),
            "returned_that_call": (None if result is None else {
                "phase": result.get("phase"), "status": result.get("status"),
                "screening_status": result.get("screening_status"),
                "next_step_allowed": result.get("next_step_allowed"),
                "action_checked": result.get("action_checked"),
                "actions_simulated_allowed": result.get("actions_simulated_allowed"),
                "completed_actions": result.get("completed_actions"),
                "current_checkpoint": result.get("current_checkpoint"),
                "current_checkpoint_file_sha256": result.get("current_checkpoint_file_sha256")}),
            "call_order": trace.get("ordered_public") or evidence["ordered_events"],
            "cli": (None if cli_entry is None else {
                "label": cli_entry["label"], "command": cli_entry["command"],
                "exit_code": cli_entry["exit_code"], "expect_exit": cli_entry["expect_exit"],
                "ok": cli_entry["ok"], "exception_class": (cli_entry.get("payload") or {}).get(
                    "exception_class"),
                "message_untruncated": (cli_entry.get("payload") or {}).get("message"),
                "stdout_path": cli_entry.get("stdout_path"), "stderr_path": cli_entry.get("stderr_path")}),
            **(extra or {}),
        }
        if reference:
            payload["large_object_references"] = [
                call_trace_reference(f"{reference_prefix}_result", "完整本次调用返回", result),
                call_trace_reference(f"{reference_prefix}_exception",
                                     "完整异常现场（含未截断消息与逐帧 traceback）",
                                     _full_exception(exc) if exc is not None else None),
                call_trace_reference(f"{reference_prefix}_trace", "完整读取/控制器事件顺序", trace),
            ]
        return payload

    def record_public_probe(case: str, payload: dict, ok: bool, problems: list,
                            probe_timing: dict | None = None) -> None:
        payload = {**payload, "ok": ok, "problems": problems}
        path = record_probe_file(container, case, payload)
        r3_probes.append({"case": case, "record": str(path.relative_to(container)),
                          "record_file_sha256": sha256(path), "ok": ok, "problems": problems,
                          "timing_verdict": payload.get("timing_verdict"),
                          "probe_timing": probe_timing})


    # ---- F03/F01 共用：七个合法阶段都用 C06b 小样（不在每个阶段重跑 MAIN 业务基准）
    stage_workbook = GENERATED / "fixtures" / "C06b.xlsx"
    stage_cases = []

    def _gate1_pending_case() -> Path:
        target = batch_path("r3_stage_g1_pending")
        run_cli("r3_stage_g1_pending_start",
                ["start", "--workbook", str(stage_workbook), "--batch-dir", str(target),
                 "--source-description", "R3 阶段恢复用例（C06b 小样）"], 0)
        return target

    stage_cases.append(("gate1_pending", "r3_stage_g1_pending", _gate1_pending_case,
                        "DEV_GATE1_PENDING"))

    def _gate1_approved_case() -> Path:
        """停在 0002（Gate1 已模拟 APPROVE，尚未 prepare）。"""
        target = batch_path("r3_stage_g1_approved")
        run_cli("r3_stage_g1_approved_start",
                ["start", "--workbook", str(stage_workbook), "--batch-dir", str(target),
                 "--source-description", "R3 阶段恢复用例（C06b 小样）"], 0)
        run_cli("r3_stage_g1_approved_record",
                ["record-simulated-decision", "--batch-dir", str(target), "--decision-file",
                 str(write_decision(target, 1, "GATE1", "APPROVE", "EVT-R3-G1-APPROVED"))], 0)
        return target

    stage_cases.append(("gate1_approved", "r3_stage_g1_approved", _gate1_approved_case,
                        "DEV_GATE1_APPROVED"))
    stage_cases.append(("gate2_pending", "r3_stage_g2_pending",
                        lambda: chain_to_gate2_pending("r3_stage_g2_pending", stage_workbook,
                                                       "r3_stage_g2_pending"),
                        "DEV_GATE2_PENDING"))

    def _to_gate2_decision(name: str, value: str, event: str) -> Path:
        target = chain_to_gate2_pending(name, stage_workbook, name)
        decision = write_decision(target, 3, "GATE2", value, event)
        entry = run_cli(f"{name}_record", ["record-simulated-gate2-decision",
                                           "--batch-dir", str(target),
                                           "--decision-file", str(decision)], 0)
        assert entry["exit_code"] == 0, entry.get("stderr_tail")
        return target

    stage_cases.append(("gate2_approved", "r3_stage_g2_approved",
                        lambda: _to_gate2_decision("r3_stage_g2_approved", "APPROVE",
                                                   "EVT-R3-G2-APPROVE"),
                        "DEV_GATE2_APPROVED"))
    stage_cases.append(("gate2_held", "r3_stage_g2_held",
                        lambda: _to_gate2_decision("r3_stage_g2_held", "HOLD", "EVT-R3-G2-HOLD"),
                        "DEV_GATE2_HELD"))
    stage_cases.append(("gate2_rejected", "r3_stage_g2_rejected",
                        lambda: _to_gate2_decision("r3_stage_g2_rejected", "REJECT",
                                                   "EVT-R3-G2-REJECT"),
                        "DEV_GATE2_REJECTED"))

    def _screen_case() -> Path:
        target = _to_gate2_decision("r3_stage_screened", "APPROVE", "EVT-R3-G2-SCREEN")
        screen_cli("r3_stage_screened", target, "r3_stage_screened_screen", 0)
        return target

    stage_cases.append(("screened", "r3_stage_screened", _screen_case,
                        "DEV_GATE2_APPROVED"))

    # ---- F03：七阶段完整判定（API 与 CLI 双侧、真实批准来自当前 checkpoint 的 workflow.state）
    stage_records = []
    stage_targets = {}
    stage_files: list = []
    expected_stage_actions = {
        "gate1_pending": {"NORMALIZE_AND_LOAD": False, "SCREEN_AND_BUILD_FACTS": False},
        "gate1_approved": {"NORMALIZE_AND_LOAD": True, "SCREEN_AND_BUILD_FACTS": False},
        "gate2_pending": {"NORMALIZE_AND_LOAD": False, "SCREEN_AND_BUILD_FACTS": False},
        "gate2_approved": {"NORMALIZE_AND_LOAD": False, "SCREEN_AND_BUILD_FACTS": True},
        "gate2_held": {"NORMALIZE_AND_LOAD": False, "SCREEN_AND_BUILD_FACTS": False},
        "gate2_rejected": {"NORMALIZE_AND_LOAD": False, "SCREEN_AND_BUILD_FACTS": False},
        "screened": {"NORMALIZE_AND_LOAD": False, "SCREEN_AND_BUILD_FACTS": True},
    }
    stage_counter_before = dict(counts)
    stage_api_events_before = len(api_events)
    stage_controller_before = len(controller_events)
    stage_core_before = len(core_events)

    for stage_name, leaf, build, expected_phase in stage_cases:
        target = build()
        stage_targets[stage_name] = target
        tree_before = _tree(target)
        api_return = None
        api_error = None
        api_stage_calls: list = []
        controller_before_api = len(controller_events)
        try:
            api_return = host.inspect_dev_batch(target)
        except (host.WorkflowHostBlocked, host.WorkflowHostError) as exc:
            api_error = exc
        for event in controller_events[controller_before_api:]:
            api_stage_calls.append({"entry": event.get("entry"), "outcome": event.get("outcome")})
        tree_after_api = _tree(target)
        cli_entry = run_cli(f"r3_stage_{stage_name}_status",
                            ["status", "--batch-dir", str(target)], 0)
        tree_after_cli = _tree(target)
        cli_payload = cli_entry.get("payload") or {}
        api_result = api_return or {}
        checkpoint_rel = api_result.get("current_checkpoint")
        # current_checkpoint 是相对批次目录的路径（如 workflow/checkpoints/0004.json）
        checkpoint_file = (target / checkpoint_rel) if checkpoint_rel else None
        checkpoint_payload = (json.loads(checkpoint_file.read_text(encoding="utf-8"))
                              if checkpoint_file is not None and checkpoint_file.is_file() else None)
        checkpoint_state = ((checkpoint_payload or {}).get("workflow") or {}).get("state") or {}
        checkpoint_approvals = {"gate1_approval": checkpoint_state.get("gate1_approval", "<missing>"),
                               "gate2_approval": checkpoint_state.get("gate2_approval", "<missing>")}
        expected_actions = expected_stage_actions[stage_name]
        api_actions = api_result.get("actions_simulated_allowed") or {}
        cli_actions = cli_payload.get("actions_simulated_allowed") or {}
        expected_approvals_null = (checkpoint_state.get("gate1_approval", "<missing>") is None
                                   and checkpoint_state.get("gate2_approval", "<missing>") is None)
        readonly_proven = (tree_before == tree_after_api == tree_after_cli)
        operation = (checkpoint_payload or {}).get("operation") or {}
        findings = ((operation.get("artifacts") or {}).get("output_relative")
                    if isinstance(operation.get("artifacts"), dict) else None)
        evidence = {
            "stage": stage_name, "batch_dir": str(target),
            "batch_relative": str(target.relative_to(PROJECT_ROOT)),
            "workbook": str(stage_workbook),
            "workbook_sha256": sha256(stage_workbook),
            "expected_phase": expected_phase,
            "expected_actions_simulated_allowed": expected_actions,
            "public_entry": "host.inspect_dev_batch",
            "arguments": {"batch_dir": str(target)},
            "api_full_return": api_return,
            "api_error": (None if api_error is None else _full_exception(api_error)),
            "api_controller_calls_this_stage": api_stage_calls,
            "cli_command": cli_entry["command"], "cli_exit_code": cli_entry["exit_code"],
            "cli_payload_untruncated": cli_entry.get("payload"),
            "cli_stdout_path": cli_entry.get("stdout_path"),
            "cli_stderr_path": cli_entry.get("stderr_path"),
            "actual_phase": {"api": api_result.get("phase"), "cli": cli_payload.get("phase")},
            "next_step_allowed": {"api": api_result.get("next_step_allowed"),
                                  "cli": cli_payload.get("next_step_allowed")},
            "actions_simulated_allowed": {"api": api_actions, "cli": cli_actions},
            "completed_actions": {"api": api_result.get("completed_actions"),
                                  "cli": cli_payload.get("completed_actions")},
            "screening_status": {"api": api_result.get("screening_status"),
                                 "cli": cli_payload.get("screening_status")},
            "current_checkpoint": checkpoint_rel,
            "current_checkpoint_workflow_state_approvals": checkpoint_approvals,
            "real_approvals_are_null": expected_approvals_null,
            "screening_credential_0005": {
                "present": (checkpoint_payload or {}).get("revision") == 5,
                "kind": operation.get("kind"),
                "operation_keys": sorted(operation.keys()),
                "artifact_reference": findings,
            },
            "readonly": {"tree_before_equals_after_api": tree_before == tree_after_api,
                         "tree_before_equals_after_cli": tree_before == tree_after_cli},
            "hash_sets": {
                "before_api": tree_reference(f"r3_stage_{stage_name}_tree_before", tree_before),
                "after_api": tree_reference(f"r3_stage_{stage_name}_tree_after_api", tree_after_api),
                "after_cli": tree_reference(f"r3_stage_{stage_name}_tree_after_cli", tree_after_cli),
            },
        }
        problems: list = []
        if api_error is not None:
            problems.append(f"API 恢复抛错：{type(api_error).__name__}: {str(api_error)[:200]}")
        elif api_result.get("phase") != expected_phase:
            problems.append(f"API phase 不符：{api_result.get('phase')!r} != {expected_phase!r}")
        if api_result.get("next_step_allowed") is not False:
            problems.append("API next_step_allowed 不是严格 false")
        if api_result.get("status") != "READY":
            problems.append(f"API status 不是 READY：{api_result.get('status')!r}")
        if cli_entry["exit_code"] != 0:
            problems.append(f"CLI status 退出码 {cli_entry['exit_code']}（期望 0）")
        if cli_payload.get("phase") != expected_phase:
            problems.append(f"CLI phase 不符：{cli_payload.get('phase')!r} != {expected_phase!r}")
        if cli_payload.get("next_step_allowed") is not False:
            problems.append("CLI next_step_allowed 不是严格 false")
        for side, values in (("API", api_actions), ("CLI", cli_actions)):
            for action_name, want in expected_actions.items():
                got = values.get(action_name)
                if got is not want:
                    problems.append(f"{side} 动作允许值 {action_name}：{got!r} != 期望 {want!r}")
        if not expected_approvals_null:
            problems.append(f"当前 checkpoint 的真实批准不是 null：{checkpoint_approvals}")
        if stage_name == "screened":
            if api_result.get("screening_status") != "RULE_SCREEN_RECORDED" \
                    or cli_payload.get("screening_status") != "RULE_SCREEN_RECORDED":
                problems.append("screened 阶段缺少 RULE_SCREEN_RECORDED 凭证")
            if (checkpoint_payload or {}).get("revision") != 5 \
                    or ((checkpoint_payload or {}).get("operation") or {}).get("kind") != "RUN_RULE_SCREEN":
                problems.append("screened 阶段缺少 0005／RUN_RULE_SCREEN 凭证")
        if not readonly_proven:
            problems.append("只读性不成立：before／after_api／after_cli 树哈希集合不等")
        evidence = {**evidence, "problems": problems, "ok": not problems}
        path = record_probe_file(container, f"r3_stage_{stage_name}_full", evidence)
        stage_files.append({"stage": stage_name, "record": str(path.relative_to(container)),
                            "record_file_sha256": sha256(path), "problems": problems,
                            "ok": not problems})
        stage_records.append({
            "stage": stage_name, "batch": evidence["batch_relative"],
            "expected_phase": expected_phase,
            "api_phase": api_result.get("phase"), "cli_phase": cli_payload.get("phase"),
            "cli_exit": cli_entry["exit_code"],
            "api_actions_simulated_allowed": api_actions,
            "cli_actions_simulated_allowed": cli_actions,
            "checkpoint": checkpoint_rel,
            "real_approvals_from_checkpoint_state": checkpoint_approvals,
            "screening_status": {"api": api_result.get("screening_status")},
            "readonly_tree_unchanged": readonly_proven,
            "evidence_record": str(path.relative_to(container)),
            "evidence_record_sha256": sha256(path),
            "ok": not problems, "problems": problems,
        })
        if problems:
            r3_problems.append(f"F03 阶段 {stage_name} 未按协议完整通过：{problems[:3]}")
    record_probe_file(container, "r3_f01_f03_stage_summary", {"stages": stage_records})
    if not all(item["ok"] for item in stage_records):
        print("    F03 阶段判定明细：" + json.dumps(
            [{"stage": i["stage"], "ok": i["ok"], "api_phase": i["api_phase"],
              "cli_exit": i["cli_exit"], "problems": i["problems"][:2]}
             for i in stage_records], ensure_ascii=False)[:1200])

    # ---- F01/F02 共用：真实读取观察器（只观测，不改变宿主语义）
    real_read_screen_outputs = host._read_screen_outputs
    real_read_json_with_bytes = host._read_json_with_bytes

    def make_file_observer(target: Path, on_consumer_read=None) -> dict:
        """记录宿主对目标文件的每一次真实读取（含调用栈），可选择在“消费型读取”返回后触发钩子。

        拦住 `io.open`：pathlib 的两条读取路径（`Path.open` 与 `Path.read_bytes`）都经它，
        因此 `file_sha256` 这类只比较字节的守卫读取也会被观测到。
        消费型读取＝把内容当值消费的读取；守卫读取＝最内层真实读取者是 `file_sha256`。
        造样自身引起的读写通过 in_hook 抑制，不计入宿主读取轨迹。
        """
        observed = {"events": []}
        real_io_open = io.open
        state = {"in_hook": False}

        def observed_open(file, mode="r", *a, **kw):
            handle = real_io_open(file, mode, *a, **kw)
            if state["in_hook"]:
                return handle
            try:
                same = Path(file) == target
            except TypeError:
                same = False
            if not same:
                return handle
            event = {"mode": mode, "call": len(observed["events"]) + 1}
            observed["events"].append(event)
            if set(mode) & {"r", "+"}:
                position = handle.tell()
                data = handle.read()
                handle.seek(position)
                frames = call_stack_names(limit=12)
                read_index = observed.get("read_index", 0) + 1
                observed["read_index"] = read_index
                event["read_index"] = read_index
                event["bytes_read"] = len(data)
                event["sha256_after_read"] = hashlib.sha256(
                    data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()
                meaningful = [name for name in frames
                              if name not in ("observed_open", "open", "read_bytes", "read_text",
                                              "read_json", "<unknown>")]
                event["innermost_reader"] = meaningful[0] if meaningful else None
                event["consumer_read"] = not (meaningful and meaningful[0] == "file_sha256")
                event["stack_tail"] = call_stack_tail(limit=7, skip=0)
                if event["consumer_read"] and on_consumer_read is not None:
                    state["in_hook"] = True
                    try:
                        on_consumer_read(read_index, event)
                    finally:
                        state["in_hook"] = False
            return handle
        io.open = observed_open

        def suspend():
            state["in_hook"] = True

        def resume():
            state["in_hook"] = False

        def restore():
            setattr(io, "open", real_io_open)
        return {"observed": observed, "restore": restore, "suspend": suspend, "resume": resume}


    def read_probe_trace(label: str, path: Path, target_reads: list, calls: list,
                         injections: list, controllers: list) -> dict:
        return {"label": label, "target_changed": str(path), "reads": target_reads,
                "read_calls_total": len(calls),
                "read_calls": [{"index": item["index"], "stage": item.get("stage"),
                                "module": "_read_screen_outputs"} for item in calls],
                "writes": injections, "controllers": controllers,
                "ordered_public": [{"index": index, "kind": kind,
                                    "name": (item.get("stage") if kind == "read_screen_outputs"
                                             else (item.get("name") or item.get("entry")))}
                                   for index, kind, item in sorted(
                                       [*((item["call_index"], "read_screen_outputs", item)
                                          for item in calls),
                                        *((item["after_calls"], "controller", item)
                                          for item in controllers)],
                                       key=lambda pair: (pair[0], pair[1]))]}

    ref_map = {"report": "r3_f01_report", "load_report": "r3_f01_load_report",
               "0001": "r3_f01_checkpoint_0001"}
    # 每项给出“必须命中”的第一原因，以及该目标被读取位置允许的等价检测点（宿主按链顺序核验时
    # 可能先在等价检测点上给出同一目标的证据）。
    expect_reason_map = {"report": "screening_report.json",
                         "load_report": "workflow/gate2/load_report.json",
                         "0001": "0001.json"}
    expect_reason_alternates = {
        "report": ["screening_report.json", "0005.json"],
        "load_report": ["workflow/gate2/load_report.json", "0005.json"],
        "p01_report_relative": ["report_relative", "0005.json"],
        # 0001 的检测点必须指向 0001.json 自身（第二次 reader 返回后注入、由 checkpoint
        # 字节核验发现），不接受链上提前出现的前序引用代替。
        "0001": ["0001.json"],
    }

    def run_f01_probe(label: str, target: Path, path: Path, mutate, expect_reason: str,
                      reference_prefix: str,
                      alternates: list | None = None) -> tuple:
        """F01 共同触发点：真实 `_read_screen_outputs` 第二次完整返回原始对象之后，改本项唯一目标文件一次。

        固定顺序：保存真实 reader／真实 check_dev_action → reader wrapper 先调用真实函数，成功返回后
        才计数并记事件 → 计数等于 2 且尚未注入时改磁盘一次并原样返回 result → 同时包装真实
        check_dev_action（先执行真实函数，再记完整实参／返回与事件序号，统计注入后调用数）→
        try/finally 撤销两个 wrapper。不拦 io.open、不在读取句柄前预读、不按调用栈推断消费点。
        """
        before_tree = _tree(target)
        original_bytes = path.read_bytes()
        before_hash = sha256(path)
        state = {"reader_returns": 0, "reader_returns_after_injection": 0, "hits": 0,
                 "controller_calls_after_injection": 0, "returned_object_unchanged": None,
                 "events": [], "controller_calls": []}
        real_reader = host._read_screen_outputs
        real_control = host.CONTROLLER_MODULE.check_dev_action

        def log(event: str, **details) -> None:
            state["events"].append({"seq": len(state["events"]) + 1, "event": event, **details})

        def reader_wrapper(batch_dir, stage):
            result = real_reader(batch_dir, stage)
            state["reader_returns"] += 1
            index = state["reader_returns"]
            log("_read_screen_outputs_return", index=index, stage=stage,
                returned_object_sha256=canonical_sha256(result),
                files=("started", "report", "artifacts"))
            if state["hits"]:
                state["reader_returns_after_injection"] += 1
            if index == 2 and state["hits"] == 0:
                old_fingerprint = canonical_sha256(result)
                mutate()
                state["hits"] += 1
                state["returned_object_unchanged"] = canonical_sha256(result) == old_fingerprint
                log("disk_mutation_after_second_read_screen_outputs_return", target=str(path))
            return result

        def control_wrapper(workflow, name, **kwargs):
            result = real_control(workflow, name, **kwargs)
            state["controller_calls"].append({
                "seq": len(state["events"]) + 1, "entry": "check_dev_action", "action": name,
                "kwargs_keys": sorted(kwargs.keys()),
                "workflow_state_sha256": (workflow or {}).get("state_sha256"),
                "workflow_phase": ((workflow or {}).get("state") or {}).get("phase"),
                "batch_id": ((workflow or {}).get("state") or {}).get("batch_id"),
                "returned": {"phase": (result or {}).get("phase"),
                             "action": (result or {}).get("action"),
                             "simulation_allowed": (result or {}).get("simulation_allowed"),
                             "next_step_allowed": (result or {}).get("next_step_allowed")},
                "after_injection": bool(state["hits"])})
            log("controller_return", entry="check_dev_action", action=name,
                after_injection=bool(state["hits"]))
            if state["hits"]:
                state["controller_calls_after_injection"] += 1
            return result

        host._read_screen_outputs = reader_wrapper
        host.CONTROLLER_MODULE.check_dev_action = control_wrapper
        outcome, exc, result = "ok", None, None
        try:
            result = host.inspect_dev_batch(target)
        except host.WorkflowHostBlocked as caught:
            outcome, exc = "blocked", caught
        except host.WorkflowHostError as caught:
            outcome, exc = "error", caught
        finally:
            host._read_screen_outputs = real_reader
            host.CONTROLLER_MODULE.check_dev_action = real_control
        after_tree = _tree(target)
        after_hash = sha256(path)
        changed_paths = sorted(key for key in set(before_tree) | set(after_tree)
                               if before_tree.get(key) != after_tree.get(key))
        changed_cli = run_cli(f"{reference_prefix}_revoked_reject",
                              ["status", "--batch-dir", str(target)], 1)
        # 只恢复本目标原始字节（不得同步任何后继引用）
        path.write_bytes(original_bytes)
        restored_tree = _tree(target)
        restored = run_cli(f"{reference_prefix}_restored",
                           ["status", "--batch-dir", str(target)], 0)
        accepted_reasons = list(alternates or [expect_reason])
        problems: list = []
        if state["reader_returns"] != 2:
            problems.append(f"本次调用观测到 {state['reader_returns']} 次 _read_screen_outputs 返回，"
                            "共同触发点要求恰为 2 次")
        if state["hits"] != 1:
            problems.append(f"注入次数 {state['hits']} != 1")
        if not state["returned_object_unchanged"]:
            problems.append("注入后 reader 返回的对象指纹发生了变化（返回对象未保持原始值）")
        if state["reader_returns_after_injection"] != 0:
            problems.append(f"注入后仍有 {state['reader_returns_after_injection']} 次 _read_screen_outputs 返回")
        if state["controller_calls_after_injection"] != 0:
            problems.append(f"注入后仍有 {state['controller_calls_after_injection']} 次控制器调用")
        if not state["controller_calls"]:
            problems.append("控制器 wrapper 没有记录到任何真实调用（注入后 0 次不能由空记录充当测量）")
        if changed_paths != [str(path.relative_to(target))]:
            problems.append(f"目录差异不止本目标文件：{changed_paths}")
        if outcome != "blocked" or type(exc).__name__ != "WorkflowHostBlocked":
            problems.append(f"本次公开 API 未得到 WorkflowHostBlocked：outcome={outcome} "
                            f"exc={type(exc).__name__ if exc else None}")
        message = str(exc) if exc is not None else ""
        if exc is not None and (not any(item in message for item in accepted_reasons)
                                or str(getattr(exc, "stage", "")) != "status"):
            problems.append(f"阻断原因未指向目标：{message[:220]}（可接受：{accepted_reasons}）")
        if changed_cli["exit_code"] != 1:
            problems.append(f"保留变更现场的新进程 CLI 退出 {changed_cli['exit_code']}（期望 1）")
        if restored["exit_code"] != 0:
            problems.append(f"恢复本目标原件后新进程 CLI 退出 {restored['exit_code']}（期望 0）")
        if restored_tree != before_tree:
            problems.append("恢复本目标原件后的目录哈希集合与调用前不一致")
        timing_trace = {
            "reads": [{"seq": event["index"], "event_seq": event["seq"], "consumer_read": True,
                       "reader_return": True}
                      for event in state["events"]
                      if event["event"] == "_read_screen_outputs_return"],
            "writes": ([{"after_read_seq": 2, "event_seq": 2}] if state["hits"] else []),
            "controllers": [{"after_reads": item["seq"], "name": item["entry"]}
                            for item in state["controller_calls"]],
            "reader_returns": state["reader_returns"],
            "reader_returns_after_injection": state["reader_returns_after_injection"],
        }
        timing = probe_timing_verdict(timing_trace)
        if not timing["qualified"]:
            problems.append("时点判定不合格：" + "；".join(timing["problems"]))
        payload = public_trace(
            f"r3_f01_{label}_last_read", "host.inspect_dev_batch", target,
            "WorkflowHostBlocked", expect_reason,
            "真实 host._read_screen_outputs 第二次完整返回原始对象之后（共同触发点）；"
            "after 于调用结束且 wrapper 撤销之后、恢复本目标原件之前取得",
            timing_trace, outcome=outcome, exc=exc, result=result, cli_entry=changed_cli,
            extra={
                "hits": state["hits"], "injection_hits": state["hits"],
                "reader_returns": state["reader_returns"],
                "reader_returns_after_injection": state["reader_returns_after_injection"],
                "reader_return_events": [event for event in state["events"]
                                         if event["event"] == "_read_screen_outputs_return"],
                "controller_calls_after_injection": state["controller_calls_after_injection"],
                "controller_calls": state["controller_calls"],
                "event_order": state["events"],
                "returned_object_unchanged": state["returned_object_unchanged"],
                "accepted_reasons": accepted_reasons,
                "changed_paths": changed_paths,
                "before": {"file": before_hash, "tree_sha256": canonical_sha256(before_tree),
                           "tree_entries": len(before_tree)},
                "after": {"file": after_hash, "tree": after_tree,
                          "tree_sha256": canonical_sha256(after_tree),
                          "same_file_in_tree_sha256": after_tree.get(
                              str(path.relative_to(target))),
                          "file_equals_tree": after_tree.get(
                              str(path.relative_to(target))) == after_hash,
                          "taken_at": "调用结束且两个 wrapper 撤销之后、恢复本目标原件之前"},
                "restored_evidence": {"file": sha256(path),
                                      "tree_sha256": canonical_sha256(restored_tree),
                                      "tree_equals_before": restored_tree == before_tree,
                                      "note": "只恢复本目标原始字节，未同步任何后继引用"},
                "revoked_cli": {"label": changed_cli["label"], "command": changed_cli["command"],
                                "exit_code": changed_cli["exit_code"],
                                "expect_exit": changed_cli["expect_exit"],
                                "exception_class": (changed_cli.get("payload") or {}).get(
                                    "exception_class"),
                                "message_untruncated": (changed_cli.get("payload") or {}).get("message"),
                                "stdout_path": changed_cli.get("stdout_path"),
                                "stderr_path": changed_cli.get("stderr_path"),
                                "note": "保留变更现场、撤销两个 wrapper 后新进程 CLI 仍拒绝"},
                "restored_positive": {"label": restored["label"], "command": restored["command"],
                                      "exit_code": restored["exit_code"],
                                      "phase": (restored.get("payload") or {}).get("phase"),
                                      "note": "只恢复本目标原始字节后新进程 CLI 退出 0"},
                "unchanged_control": {"exit_code": restored["exit_code"],
                                      "phase": (restored.get("payload") or {}).get("phase"),
                                      "tree_equals_before": restored_tree == before_tree},
                "target": label,
                "timing_qualified": timing["qualified"],
                "large_value_references": [
                    call_trace_reference(f"{reference_prefix}_result", "完整本次调用返回", result),
                    call_trace_reference(f"{reference_prefix}_target_tree_after",
                                         "after 目录哈希集合（完整，恢复前）", after_tree),
                    call_trace_reference(f"{reference_prefix}_target_tree_before",
                                         "before 目录哈希集合（完整）", before_tree),
                    call_trace_reference(f"{reference_prefix}_event_order",
                                         "reader 返回与控制器调用事件顺序", state["events"]),
                ],
            },
            reference=True, reference_prefix=reference_prefix)
        record_public_probe(f"r3_f01_{label}_last_read", payload, not problems, problems,
                            probe_timing=timing)
        if problems:
            r3_problems.append(f"F01 {label} 末次读取探针不合格：{problems[:3]}")
        return not problems, timing

    def run_f02_probe(label: str, leaf: str, mutator, expect_reason: str, *,
                      sync_0005: bool, sync_artifacts_started: bool = False,
                      alternates: list | None = None) -> bool:
        """F02：真实 after 时点（撤销 wrapper 后、恢复原件前）＋完整调用现场。

        造样在公开调用之前完成，使宿主读到的是最终字节：这样失败会落在目标字段的语义核验上，
        而不是被“同一次调用内改了已消费 checkpoint”的字节复测提前拦下。时点与哈希证据以
        **整批目录**为单位：after 集合在调用结束且观察器撤销之后、恢复原件之前采集。
        """
        target = _screened_baseline(leaf, stage_workbook)
        sync = f02_sync_builder(target, sync_0005=sync_0005,
                                sync_artifacts_started=sync_artifacts_started)
        path = target / "workflow/checkpoints/0005.json"  # 目标标记：造样只发生在该批次内
        snapshots = {item: item.read_bytes() for item in sorted(target.rglob("*")) if item.is_file()}
        before_tree = _tree(target)
        mutator(target, f02_mutate_paths(target))
        sync(target)
        after_mutation_tree = _tree(target)
        changed_files = sorted(key for key in set(before_tree) | set(after_mutation_tree)
                               if before_tree.get(key) != after_mutation_tree.get(key))
        writes = [{
            "injected": label, "after_read_seq": None,
            "mutation": "F02 造样写入（公开调用之前完成，含引用同步）",
            "changed_files": changed_files,
            "before_sha256": {key: before_tree.get(key) for key in changed_files},
            "after_sha256": {key: after_mutation_tree.get(key) for key in changed_files}}]
        trace = {"reads": [], "writes": writes, "controllers": [], "read_calls": [],
                 "ordered_public": []}
        state = {"injections": 1, "calls": 0, "consumer_reads": 0}
        observer = make_file_observer(path, on_consumer_read=None)
        outcome, exc, result = "ok", None, None
        try:
            result = host.inspect_dev_batch(target)
        except host.WorkflowHostBlocked as caught:
            outcome, exc = "blocked", caught
        except host.WorkflowHostError as caught:
            outcome, exc = "error", caught
        # F02 时点：调用结束、观察器仍在时采集 after（测量动作挂起观察器，不污染轨迹）
        observer["suspend"]()
        try:
            after_tree = _tree(target)
            after_tree_sha = canonical_sha256(after_tree)
        finally:
            observer["resume"]()
        changed_cli = run_cli(f"{leaf}_changed_cli", ["status", "--batch-dir", str(target)], 1)
        observer["suspend"]()
        try:
            for key, data in snapshots.items():
                if key.is_file() and key.read_bytes() != data:
                    key.write_bytes(data)
            for extra in sorted(target.rglob("*")):
                if extra.is_file() and extra not in snapshots:
                    extra.unlink()
            restored_tree = _tree(target)
        finally:
            observer["resume"]()
        observer["restore"]()
        restored = run_cli(f"{leaf}_restored", ["status", "--batch-dir", str(target)], 0)
        problems: list = []
        if state["injections"] != 1:
            problems.append(f"注入次数 {state['injections']} != 1")
        if not changed_files:
            problems.append("造样没有改变任何文件的字节")
        for key in changed_files:
            if after_tree.get(key) != writes[0]["after_sha256"].get(key):
                problems.append(f"after.tree 中 {key} 的哈希与造样后实测不一致（时点被污染）")
        for key in changed_files:
            if before_tree.get(key) == after_tree.get(key):
                problems.append(f"before／after 的目标文件 {key} 哈希相同（时点不成立）")
        if outcome != "blocked" or type(exc).__name__ != "WorkflowHostBlocked":
            problems.append(f"未得 WorkflowHostBlocked：outcome={outcome} "
                            f"exc={type(exc).__name__ if exc else None}")
        f02_reasons = list(alternates or [expect_reason])
        if exc is not None and not any(item in str(exc) for item in f02_reasons):
            problems.append(f"阻断原因未指向目标：{str(exc)[:200]}（可接受：{f02_reasons}）")
        if changed_cli["exit_code"] != 1:
            problems.append(f"保留改动现场的新进程 CLI 退出 {changed_cli['exit_code']}（期望 1）")
        if restored["exit_code"] != 0 or restored_tree != before_tree:
            problems.append(f"恢复原件后 CLI 退出 {restored['exit_code']}、树是否与 before 相同="
                            f"{restored_tree == before_tree}")
        file_observed = [{"call": item["call"], "mode": item["mode"],
                          "read_index": item.get("read_index"),
                          "bytes_read": item.get("bytes_read"),
                          "sha256_after_read": item.get("sha256_after_read"),
                          "consumer_read": item.get("consumer_read"),
                          "stack_tail": item.get("stack_tail")}
                         for item in observer["observed"]["events"]]
        trace["reads"] = [{"seq": item["read_index"], "consumer_read": item["consumer_read"],
                           "sha256_after_read": item["sha256_after_read"],
                           "bytes_read": item["bytes_read"], "stack_tail": item["stack_tail"]}
                          for item in file_observed]
        f02_timing = probe_timing_verdict(trace) if writes else None
        payload = public_trace(
            f"r3_f02_{label}_tail_after_last_read", "host.inspect_dev_batch", target,
            "WorkflowHostBlocked", expect_reason,
            ("真实 host._read_screen_outputs 返回原始对象之后（本次筛查路径下该产物只被这样消费一次）；"
             "after 于调用结束且 wrapper 撤销之后、恢复原件之前取得"),
            {"reads": trace["reads"], "writes": writes, "controllers": trace["controllers"],
             "read_calls": trace["read_calls"], "ordered_public": trace["ordered_public"]},
            outcome=outcome, exc=exc, result=result, cli_entry=changed_cli,
            extra={
                "read_screen_outputs_calls": state["calls"], "hits": state["injections"],
                "injection_hits": state["injections"],
                "timing_verdict": f02_timing,
                "injected_after_read_seq": (f02_timing or {}).get("injection_after_read_seq"),
                "target_file_reads": trace["reads"], "file_observer_calls": file_observed,
                "target_read_consumer_calls": sum(1 for item in trace["reads"]
                                                  if item["consumer_read"]),
                "changed_files": changed_files,
                "before": {"tree": before_tree, "tree_sha256": canonical_sha256(before_tree),
                           "tree_entries": len(before_tree),
                           "changed_file_hashes": {key: before_tree.get(key) for key in changed_files}},
                "after": {"tree": after_tree, "tree_sha256": after_tree_sha,
                          "tree_entries": len(after_tree),
                          "changed_file_hashes": {key: after_tree.get(key) for key in changed_files},
                          "same_file_in_tree_sha256": {key: after_tree.get(key) for key in changed_files},
                          "file_equals_tree": all(
                              after_tree.get(key) == writes[0]["after_sha256"].get(key)
                              for key in changed_files),
                          "taken_at": "调用结束且 wrapper 撤销之后、恢复原件之前"},
                "restored_evidence": {"tree_sha256": canonical_sha256(restored_tree),
                                      "tree_equals_before": restored_tree == before_tree,
                                      "changed_file_hashes": {key: restored_tree.get(key)
                                                              for key in changed_files},
                                      "note": "恢复原件之后重新采集的集合，单独保存，不当作 after"},
                "changed_state_cli": {"label": changed_cli["label"], "command": changed_cli["command"],
                                      "exit_code": changed_cli["exit_code"],
                                      "expect_exit": changed_cli["expect_exit"],
                                      "exception_class": (changed_cli.get("payload") or {}).get(
                                          "exception_class"),
                                      "message_untruncated": (changed_cli.get("payload") or {}).get(
                                          "message"),
                                      "stdout_path": changed_cli.get("stdout_path"),
                                      "stderr_path": changed_cli.get("stderr_path"),
                                      "note": "保留改动现场、撤销 wrapper 后新进程 CLI 仍拒绝"},
                "restored_positive": {"label": restored["label"], "command": restored["command"],
                                      "exit_code": restored["exit_code"],
                                      "phase": (restored.get("payload") or {}).get("phase"),
                                      "screening_status": (restored.get("payload") or {}).get(
                                          "screening_status"),
                                      "note": "恢复原件后新进程 CLI 退出 0"},
                "unchanged_control": {"exit_code": restored["exit_code"],
                                      "phase": (restored.get("payload") or {}).get("phase"),
                                      "tree_equals_before": restored_tree == before_tree,
                                      "note": "同批次未注入时新进程 status 退出 0 且目录不变"},
                "target": label,
                "large_value_references": [
                    call_trace_reference(f"{leaf}_result", "完整本次调用返回", result),
                    call_trace_reference(f"{leaf}_target_tree_after",
                                         "F02 after 目录哈希集合（完整，恢复前）", after_tree),
                    call_trace_reference(f"{leaf}_target_tree_before",
                                         "F02 before 目录哈希集合（完整）", before_tree),
                    call_trace_reference(f"{leaf}_timing_trace", "完整读取/控制器事件顺序",
                                         {"reads": trace["reads"], "writes": writes,
                                          "controllers": trace["controllers"],
                                          "file_observer_calls": file_observed}),
                ],
            },
            reference=True, reference_prefix=leaf)
        record_public_probe(f"r3_f02_{label}_tail_after_last_read", payload,
                            not problems, problems)
        if problems:
            r3_problems.append(f"F02 {label} 探针不合格：{problems[:3]}")
        return not problems

    # ---- F01/F02 共用：真实筛查小样的独立建链（路径必须与本批次一致，因此不用整批副本）
    def _screened_baseline(name: str, workbook: Path) -> Path:
        target = _to_gate2_decision(name, "APPROVE", f"EVT-{name}-G2")
        screen_cli(name, target, f"{name}_screen", 0)
        return target

    # ---- F02 造样（与 R2 同形态，改用小样并在真实 after 时点留证）
    def p01_mutate(target: Path, paths: dict) -> None:
        payload = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
        payload["operation"]["report_relative"] = "workflow/screening/not_a_report.json"
        paths["checkpoint"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")

    def p02_mutate(target: Path, paths: dict) -> None:
        artifacts = json.loads(paths["artifacts"].read_text(encoding="utf-8"))
        checkpoint = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
        artifacts["host_manifest_file_sha256"] = checkpoint["workflow"]["state"]["run_bindings_sha256"]
        paths["artifacts"].write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")

    def p03_mutate(target: Path, paths: dict) -> None:
        artifacts = json.loads(paths["artifacts"].read_text(encoding="utf-8"))
        artifacts["host_version"] = "WRONG-HOST-VERSION"
        paths["artifacts"].write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")

    def p04_mutate(target: Path, paths: dict) -> None:
        started = json.loads(paths["started"].read_text(encoding="utf-8"))
        started["host_version"] = "WRONG-HOST-VERSION"
        paths["started"].write_text(json.dumps(started, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")

    def p05_mutate(target: Path, paths: dict) -> None:
        payload = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
        payload["operation"]["artifacts"]["cutoff_date"] = "1900-01-01"
        paths["checkpoint"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")

    def p06_mutate(target: Path, paths: dict) -> None:
        payload = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
        payload["operation"]["artifacts"] = "not-an-object"
        paths["checkpoint"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")

    def f02_target_from_plan(leaf: str) -> Path:
        return _screened_baseline(leaf, stage_workbook)

    def f02_mutate_paths(target: Path) -> dict:
        directory = target / SCREEN_REL
        return {"dir": directory, "started": directory / "started.json",
                "report": directory / "screening_report.json",
                "artifacts": directory / "artifacts.json",
                "failure": directory / "failure.json",
                "checkpoint": target / "workflow/checkpoints/0005.json"}

    def f02_sync_builder(target: Path, *, sync_0005: bool, sync_artifacts_started: bool):
        """把造样后的实际哈希同步进 0005／artifacts，使失败落到目标语义核验（与 R2 同形态）。"""
        def sync(batch_dir: Path) -> None:
            paths = f02_mutate_paths(batch_dir)
            if sync_artifacts_started:
                artifacts = json.loads(paths["artifacts"].read_text(encoding="utf-8"))
                artifacts["started_file_sha256"] = sha256(paths["started"])
                paths["artifacts"].write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")
            if sync_0005:
                payload = json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
                payload["operation"]["started_file_sha256"] = sha256(paths["started"])
                payload["operation"]["report_file_sha256"] = sha256(paths["report"])
                payload["operation"]["artifacts_file_sha256"] = sha256(paths["artifacts"])
                payload["operation"]["artifacts"] = json.loads(
                    paths["artifacts"].read_text(encoding="utf-8"))
                paths["checkpoint"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
        return sync

    # ---- F01：三个末次读取探针（报告 / load_report / 0001），各用专用小样批次
    f01_targets = {}
    f01_bases = {}
    f01_hits = {}
    f01_probe_ok = {}
    for label in ("report", "load_report", "0001"):
        try:
            target = _screened_baseline(f"r3_f01_baseline_{label}", stage_workbook)
        except Exception as caught:  # noqa: BLE001
            r3_problems.append(f"F01 {label} 基线小样建链失败：{type(caught).__name__}: {caught}")
            continue
        f01_targets[label] = target
        f01_bases[label] = {"report": target / SCREEN_REL / "screening_report.json",
                            "load_report": target / "workflow/gate2/load_report.json",
                            "0001": target / "workflow/checkpoints/0001.json"}[label]
    for label, target in f01_targets.items():
        path = f01_bases[label]
        report_shape = None
        if label == "report":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                original = list(payload.get("findings") or [])
                report_shape = finding_shape(payload)
                expected_after_findings = 1 if original else 0
                if not original or not isinstance(original[0], dict):
                    r3_problems.append("F01 报告探针的小样报告没有可改写的 findings 条目")
            except (OSError, json.JSONDecodeError) as caught:
                r3_problems.append(f"F01 报告探针无法读取小样报告：{caught}")

            def mutate_report(path=path):
                payload = json.loads(path.read_text(encoding="utf-8"))
                original = list(payload.get("findings") or [])
                payload["findings"] = ([{**original[0], "r3_injected": True}] if original else [])
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")

            mutate = mutate_report
        else:
            def mutate_newline(path=path):
                """F01 造样（load_report／0001）：只在本目标文件原始字节末尾追加一个换行。

                不读取、不改动任何其他文件；尤其不同步 0002 或任何后继引用。0001 的检测点
                必须落在 workflow/checkpoints/0001.json 自身。
                """
                path.write_bytes(path.read_bytes() + b"\n")

            mutate = mutate_newline
        try:
            ok, timing = run_f01_probe(label, target, path, mutate,
                                       expect_reason_map[label], ref_map[label],
                                       alternates=expect_reason_alternates[label])
        except Exception as caught:  # noqa: BLE001
            ok, timing = False, {"error": f"{type(caught).__name__}: {caught}"}
            r3_problems.append(f"F01 {label} 探针执行失败：{type(caught).__name__}: {caught}")
        f01_probe_ok[label] = ok
        f01_hits[label] = {"reader_returns": (timing or {}).get("reader_returns"),
                           "hits": (timing or {}).get("injection_after_read_seq") is not None,
                           "reader_returns_after_injection":
                               (timing or {}).get("reader_returns_after_injection"),
                           "controller_calls_after_injection":
                               (timing or {}).get("after_injection_controllers")}
        r3_probes.append({"case": f"r3_f01_{label}_hit_count",
                          "record": f"probe_records/r3_f01_{label}_last_read.json",
                          "record_file_sha256": sha256(container / "probe_records" /
                                                       f"r3_f01_{label}_last_read.json")
                          if (container / "probe_records" / f"r3_f01_{label}_last_read.json").is_file()
                          else None,
                          "reader_returns": (timing or {}).get("reader_returns"),
                          "reader_returns_after_injection":
                              (timing or {}).get("reader_returns_after_injection"),
                          "hits": (timing or {}).get("injection_after_read_seq") is not None,
                          "timing_qualified": bool((timing or {}).get("qualified")),
                          "ok": ok})
        if not (timing or {}).get("qualified"):
            r3_problems.append(f"F01 {label}：时点判定不合格：" +
                               "；".join((timing or {}).get("problems") or ["no timing"]))
        if label == "report" and report_shape is not None:
            r3_probes.append({"case": "r3_f01_report_findings_shape", "ok": True, "problems": [],
                              "report_key": "findings", "report_shape": report_shape,
                              "expected_findings_after_injection": expected_after_findings})

    # ---- F01 纯内存时点判定自测（单列于 self_tests，不污染正式 failures）
    timing_negative_cases = []
    base_probe = None
    for probe in r3_probes:
        timing = probe.get("probe_timing") or {}
        if timing.get("qualified"):
            base_probe = probe
            break
    self_test_error = None
    try:
        base_timing = dict((base_probe or {}).get("probe_timing") or {})
        if not base_timing.get("qualified") or int(base_timing.get("reader_returns") or 0) != 2:
            raise ValueError(f"真实探针共同的第二次 reader 返回边界未通过：{base_timing}")

        def trace_with(returns, inject_after, controllers=(), after_readers=0):
            return {"reader_returns": returns,
                    "reads": [{"seq": index, "consumer_read": True}
                              for index in range(1, returns + 1)],
                    "writes": ([{"after_read_seq": inject_after, "event_seq": inject_after}]
                               if inject_after else []),
                    "controllers": [{"after_reads": item.get("after_reads", returns + 1),
                                     "event_seq": returns + 1, "name": item.get("name")}
                                    for item in controllers],
                    "reader_returns_after_injection": after_readers}

        timing_negative_cases = [
            {"name": "合格轨迹（第二次 reader 完整返回后注入，其后两类调用为 0）",
             "trace": trace_with(2, 2), "expect_qualified": True},
            {"name": "缺注入（未在真实读取边界改磁盘）",
             "trace": trace_with(2, None), "expect_qualified": False},
            {"name": "只有第一次 reader 返回（共同边界未到达）",
             "trace": trace_with(1, 1), "expect_qualified": False},
            {"name": "注入早于第二次 reader 返回",
             "trace": trace_with(2, 1), "expect_qualified": False},
            {"name": "注入后仍有 reader 返回",
             "trace": trace_with(2, 2, after_readers=1), "expect_qualified": False},
            {"name": "注入后仍有控制器调用",
             "trace": trace_with(2, 2, controllers=[{"after_reads": 2, "name": "check_dev_action"}]),
             "expect_qualified": False},
        ]
        timing_negative_cases[3]["injected_early_problems"] = probe_timing_verdict(
            trace_with(2, 1))["problems"]
    except Exception as caught:  # noqa: BLE001
        self_test_error = f"{type(caught).__name__}: {caught}"
        timing_negative_cases = []
    timing_self_test = {
        "rule": "probe_timing_verdict（正式探针与自测共用同一判定）：恰有一次注入，且注入必须落在"
                "_read_screen_outputs 第二次完整返回之后；其后不得再有 reader 返回或控制器调用。"
                "不得用“单个目标文件只读一次”放宽此条件。",
        "cases": [
            {"name": item["name"], "expect_qualified": item["expect_qualified"],
             "actual_qualified": probe_timing_verdict(item["trace"])["qualified"],
             "verdict": probe_timing_verdict(item["trace"])}
            for item in timing_negative_cases],
        "real_probe_verdicts": [{"case": item["case"], "timing": item.get("timing")}
                                for item in r3_probes if item.get("timing")],
        "self_test_error": self_test_error,
    }
    timing_self_test["ok"] = (
        any(case.get("name", "").startswith("合格轨迹") for case in timing_self_test["cases"])
        and bool(timing_negative_cases)
        and all(item["expect_qualified"] == probe_timing_verdict(item["trace"])["qualified"]
                for item in timing_negative_cases)
        and all(item.get("expect_qualified") or not item.get("actual_qualified")
                for item in timing_self_test["cases"]))
    self_tests["f01_last_read_timing_self_test"] = timing_self_test
    if not timing_self_test["ok"]:
        r3_problems.append("F01 时点判定自测未按要求判定（单列于 self_tests，不并入 failures）")

    # ---- F02：真实 after 时点与完整调用记录（沿用 R2 造样形态，改用小样与真实 after）
    f02_mutate_plan = [
        ("p01_report_relative", "r3_f02_p01", p01_mutate, "report_relative",
         {"sync_0005": True, "sync_artifacts_started": False}),
        ("p02_manifest_bindings", "r3_f02_p02", p02_mutate, "host_manifest_file_sha256",
         {"sync_0005": True, "sync_artifacts_started": False}),
        ("p03_artifacts_version", "r3_f02_p03", p03_mutate, "host_version",
         {"sync_0005": True, "sync_artifacts_started": False}),
        ("p04_started_version", "r3_f02_p04", p04_mutate, "host_version",
         {"sync_0005": True, "sync_artifacts_started": True}),
        ("p05_embedded_cutoff", "r3_f02_p05", p05_mutate, "operation.artifacts",
         {"sync_0005": False, "sync_artifacts_started": False}),
        ("p06_embedded_shape", "r3_f02_p06", p06_mutate, "operation.artifacts",
         {"sync_0005": False, "sync_artifacts_started": False}),
    ]
    for case, leaf, mutator, expect_reason, sync_flags in f02_mutate_plan:
        try:
            run_f02_probe(case, leaf, mutator, expect_reason, **sync_flags,
                          alternates=expect_reason_alternates.get(case))
        except Exception as caught:  # noqa: BLE001
            r3_problems.append(
                f"F02 {case} 探针执行失败：{type(caught).__name__}: {caught} | "
                + " <- ".join(f"{frame.filename.split(chr(92))[-1]}:{frame.lineno}:{frame.name}"
                              for frame in traceback.extract_tb(caught.__traceback__)[-4:]))
    # ---- 计数：从入口事件与实际调用记录导出本组新增（不照抄旧轮总数）
    stage_counter_after = dict(counts)
    stage_counts = {
        "stage_workbook": str(stage_workbook), "stage_workbook_sha256": sha256(stage_workbook),
        "api_entries_this_section": len(api_events) - stage_api_events_before,
        "api_entries_this_section_by_entry": {},
        "controller_entries_this_section": len(controller_events) - stage_controller_before,
        "controller_entries_this_section_by_function": {},
        "screen_core_calls_this_section": len(core_events) - stage_core_before,
        "cli_calls_this_section": {key: stage_counter_after[key] - stage_counter_before[key]
                                   for key in ("start_cli", "status_cli", "record_cli", "prepare_cli",
                                               "record_gate2_cli", "screen_cli")},
        "screen_core_calls_inproc_at_section_start": stage_counter_before["screen_core_calls_inproc"],
        "screen_core_calls_inproc_host_at_section_start":
            stage_counter_before["screen_core_calls_inproc_host"],
        "screen_core_calls_inproc_test_direct_at_section_start":
            stage_counter_before["screen_core_calls_inproc_test_direct"],
        "normalize_load_inproc_this_section": 0,
        "cli_subprocess_core_calls_observable": None,
        "cli_subprocess_core_calls_derivation": counts["screen_cli_success"],
        "derivation_basis": ("进程内公开 API 与控制器入口由统一观察层导出（新增 helper 进入也计入）；"
                            "CLI 子进程内部核心调用不可观测，如实记 null 并按成功的 screen-rules 命令推导；"
                            "本组未在进程内进入标准化／装载，记 0。"),
    }
    for event in api_events[stage_api_events_before:]:
        key = event.get("entry")
        stage_counts["api_entries_this_section_by_entry"][key] = (
            stage_counts["api_entries_this_section_by_entry"].get(key, 0) + 1)
    for event in controller_events[stage_controller_before:]:
        key = event.get("entry")
        stage_counts["controller_entries_this_section_by_function"][key] = (
            stage_counts["controller_entries_this_section_by_function"].get(key, 0) + 1)
    (container / "r3_g10_counts.json").write_bytes(
        (json.dumps(stage_counts, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    r3_counts_reference = {"reference_relative_path": str(
        (container / "r3_g10_counts.json").relative_to(PROJECT_ROOT)),
        "file_sha256": sha256(container / "r3_g10_counts.json"),
        "api_entries_this_section": stage_counts["api_entries_this_section"],
        "controller_entries_this_section": stage_counts["controller_entries_this_section"],
        "screen_core_calls_this_section": stage_counts["screen_core_calls_this_section"],
        "cli_calls_this_section": stage_counts["cli_calls_this_section"],
        "normalize_load_inproc_this_section": 0,
        "cli_subprocess_core_calls_observable": None,
        "cli_subprocess_core_calls_derivation": stage_counts["cli_subprocess_core_calls_derivation"]}

    record("G10_R3_STAGE_RECOVERY_LAST_READ_TAILS_AND_CALL_EVIDENCE", "flow", r3_problems,
           stages=stage_records, probes=r3_probes,
           read_call_counts=f01_hits, counts_this_section=r3_counts_reference,
           timing_self_test=self_tests["f01_last_read_timing_self_test"],
           f02_probe_ok={item[0]: [probe["ok"] for probe in r3_probes
                                   if probe["case"] == f"r3_f02_{item[0]}_tail_after_last_read"]
                         for item in f02_mutate_plan})

    g8_problems: list = []
    receiver_records = []
    for path in sorted(batch_parent.rglob("receive_invocation.json")):
        batch_dir = path.parent.parent
        relative = str(batch_dir.relative_to(PROJECT_ROOT))
        if any(relative == item["copy"] or relative.startswith(item["copy"] + "/")
               for item in copy_records):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        receiver_records.append({"batch": relative, "exit_code": payload["exit_code"]})
    registered = {key: value for key, value in expected_starts.items()}
    audit = audit_call_records(registered, receiver_records, copy_records)
    if audit["verdict"] != "PASS":
        g8_problems.append(f"接收启动与调用记录未一一对应：{audit}")
    if audit["records"] != len(receiver_records):
        g8_problems.append("审计记录数不一致")

    # 隔离自测（全部在内存副本上）：删除一条**对应的实际记录**必须判 missing；
    # 加入一条未登记记录必须判 unregistered；两者都要令共用正式规则判定 FAIL。
    # 保留 G10-R3 已登记的时点判定自测，只追加 G8 自己的自测项。
    dropped_record = receiver_records[0] if receiver_records else None
    sim_missing = audit_call_records(dict(registered),
                                     [item for item in receiver_records
                                      if item is not dropped_record],
                                     copy_records)
    sim_unregistered = audit_call_records(
        dict(registered),
        list(receiver_records) + [{"batch": str((PROJECT_ROOT / "data/batches").relative_to(
            PROJECT_ROOT) / "__in_memory_unregistered__")}],
        copy_records)
    self_tests["count_audit_self_test"] = {
        "shared_rule": "audit_call_records（正式组与自测同一规则）",
        "complete_verdict": audit["verdict"],
        "dropped_record_batch": (dropped_record or {}).get("batch"),
        "removed_one_actual_record_verdict": sim_missing["verdict"],
        "removed_one_actual_record_missing": sim_missing["missing"][:2],
        "added_unregistered_verdict": sim_unregistered["verdict"],
        "added_unregistered_list": sim_unregistered["unregistered"][:2],
        "formal_would_fail_if_record_missing": sim_missing["verdict"] == "FAIL",
        "formal_would_fail_if_record_unregistered": sim_unregistered["verdict"] == "FAIL",
        "ok": (audit["verdict"] == "PASS"
               and sim_missing["verdict"] == "FAIL" and bool(sim_missing["missing"])
               and sim_unregistered["verdict"] == "FAIL" and bool(sim_unregistered["unregistered"])),
    }
    if not self_tests["count_audit_self_test"]["ok"]:
        g8_problems.append("计数审计自测未按要求判定")
    # 筛查入口对应：每个 0005 批次必须能对应到一次真实筛查入口
    # ——进程内宿主核心调用（core_call_records.caller == "host"）或成功的 CLI screen-rules 日志。
    cli_screen_ok = {}
    cli_screen_total = 0
    for item in cli_logs:
        command = item.get("command") or []
        if len(command) > 4 and command[3] == "screen-rules":
            cli_screen_total += 1
            target_arg = command[command.index("--batch-dir") + 1] if "--batch-dir" in command else None
            if target_arg is not None and item.get("exit_code") == 0:
                cli_screen_ok[str(Path(target_arg).resolve().relative_to(PROJECT_ROOT))] = item["label"]
    host_core_calls = [item for item in core_call_records if item["caller"] == "host"]
    host_core_dbs = {item["database_path"] for item in host_core_calls}
    screen_records = []
    for record_path in sorted(batch_parent.rglob("workflow/checkpoints/0005.json")):
        batch_dir = record_path.parent.parent.parent
        relative = str(batch_dir.relative_to(PROJECT_ROOT))
        if any(relative == item["copy"] or relative.startswith(item["copy"] + "/")
               for item in copy_records):
            continue
        db_rel = str(database_path(batch_dir))
        via_host = db_rel in host_core_dbs
        via_cli = relative in cli_screen_ok
        if via_host or via_cli:
            screen_records.append({"batch": relative, "database_path": db_rel,
                                   "entered_through": "host_inproc" if via_host else "cli_screen_rules"})
    cli_ok_without_0005 = [batch for batch in cli_screen_ok
                           if not (PROJECT_ROOT / batch / "workflow/checkpoints/0005.json").is_file()]
    screen_problems = []
    if len(screen_records) != len(cli_screen_ok) + len(
            {db for db in host_core_dbs if any(
                str(database_path(p.parent.parent.parent)) == db
                for p in batch_parent.rglob("workflow/checkpoints/0005.json"))}):
        screen_problems.append("筛查实际入口与 0005 记录数量不一致")
    if cli_ok_without_0005:
        screen_problems.append(f"成功的 CLI 筛查没有对应 0005：{cli_ok_without_0005[:3]}")
    screen_entry_ok = not screen_problems
    if not screen_entry_ok:
        g8_problems.append(f"筛查实际入口与 0005 记录未一一对应：{screen_problems}")
    self_tests["screen_entry_audit"] = {
        "rule": "同一 audit_call_records（按批次/数据库路径对应宿主调用或 CLI 日志与已保存 0005）",
        "batches_with_0005_including_copies": len(list(
            batch_parent.rglob("workflow/checkpoints/0005.json"))),
        "batches_with_0005_excluding_copies": len(screen_records),
        "matched_records": len(screen_records),
        "host_inproc_calls": len(host_core_calls),
        "cli_screen_rules_total": cli_screen_total,
        "cli_screen_rules_success": len(cli_screen_ok),
        "cli_success_without_0005": cli_ok_without_0005[:3],
        "problems": screen_problems,
        "basis": "进程内宿主调用按数据库路径对应；CLI screen-rules 按命令实参与退出码对应。",
        "ok": screen_entry_ok,
    }

    def matcher(exception, expected_class, expected_reason):
        if expected_class == "WorkflowHostError":
            if not isinstance(exception, host.WorkflowHostError):
                return False
        elif expected_class == "WorkflowHostBlocked":
            if not isinstance(exception, host.WorkflowHostBlocked):
                return False
        else:
            return False
        return expected_reason in str(exception)

    matcher_sample = None
    if not smoke:
        matcher_sample = partial_exception
    if matcher_sample is None:
        # 定向小样模式下 G5 未运行：用同一类型的真实异常做匹配器自测（不改变判定规则）
        matcher_sample = host.WorkflowHostError(
            "定向小样匹配器自测样本（SENTINEL-T13-PARTIAL-0005）", stage="self_test")
    matcher_reason = "SENTINEL-T13-PARTIAL-0005"

    self_tests["probe_matcher"] = {
        "cases": [
            {"name": "类别+原因正确", "expect": True,
             "actual": matcher(matcher_sample, "WorkflowHostError", matcher_reason)},
            {"name": "类别正确原因不符", "expect": False,
             "actual": matcher(matcher_sample, "WorkflowHostError", "另一个原因")},
            {"name": "类别不符", "expect": False,
             "actual": matcher(matcher_sample, "WorkflowHostBlocked", matcher_reason)},
        ],
    }
    self_tests["probe_matcher"]["ok"] = all(item["expect"] == item["actual"]
                                            for item in self_tests["probe_matcher"]["cases"])
    if not self_tests["probe_matcher"]["ok"]:
        g8_problems.append("异常匹配器自测未按要求判定")

    counts["real_approvals"] = 0
    entry_events = {"api_events": api_events, "controller_events": controller_events,
                    "core_events": core_events, "core_call_records": core_call_records,
                    "controller_by_function": {
                        "create_dev_workflow": counts["controller_create_inproc"],
                        "prepare_dev_gate": counts["controller_prepare_inproc"],
                        "record_dev_decision": counts["controller_record_inproc"],
                        "check_dev_action": counts["controller_check_inproc"],
                        "all_inproc": counts["controller_all_inproc"],
                        "check_record_subset_inproc": counts["controller_check_record_subset_inproc"],
                    },
                    "cli_screen_rules": {
                        "total": counts["screen_cli"],
                        "success": counts["screen_cli_success"],
                        "precondition_rejected": counts["screen_cli_precondition_rejected"],
                        "runtime_failed": counts["screen_cli_runtime_failed"],
                        "core_calls_in_cli_subprocess": None,
                        "derived_core_calls_from_success": counts["screen_cli_success"],
                        "derivation_basis": "每个成功的 screen-rules 命令恰好真实调用一次冻结核心；"
                                            "CLI 子进程内部不可观测，故记 null 另列推导值。",
                    },
                    "note": "紧凑入口事件列表：只留入口名/结果分类，供计数与留痕一一对应核对。"}
    (container / "entry_events.json").write_text(
        json.dumps(entry_events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record("G8_COUNT_AUDIT_AND_EVIDENCE", "flow", g8_problems, audit=audit, self_tests=self_tests)

    # ------------------------------------------------- 保护核对与最终一次落盘
    protected_changed = [rel for rel, digest in protected_before.items()
                         if sha256(PROJECT_ROOT / rel) != digest]
    if protected_changed:
        failures.append({"case": "INTEGRITY_protected_files", "kind": "integrity", "result": "FAIL",
                         "problems": protected_changed})
        print(f"[FAIL] INTEGRITY 受保护文件发生变化：{protected_changed}")
    else:
        print(f"[PASS] INTEGRITY 受保护文件 {len(protected_before)} 个前后一致")
    checks.append({"case": "INTEGRITY_protected_files", "kind": "integrity",
                   "result": "PASS" if not protected_changed else "FAIL",
                   "problems": protected_changed})

    summary = {
        "task": "TASK-013",
        "out_dir": str(container),
        "batch_parent": str(batch_parent),
        "sqlite_parent": str(sqlite_parent),
        "python": sys.version.split()[0],
        "host": {"path": str(HOST_PATH), "sha256": sha256(HOST_PATH), "version": host.HOST_VERSION,
                 "checkpoint_protocol": host.CHECKPOINT_VERSION,
                 "screen_start_version": host.SCREEN_START_VERSION},
        "counts": counts,
        "checks": checks,
        "cli_logs": cli_logs,
        "copy_records": copy_records,
        "probes": probe_records,
        "failures": failures,
        "self_tests": self_tests,
        "protected_files_count": len(protected_before),
        "protected_files_unchanged": not protected_changed,
        "note": ("本轮真实执行接收／标准化／装载／Gate2 决定／只读 R01—R04 筛查；"
                 "未执行独立复算、事实底稿、AI 或任何真实批准。"),
    }
    artifacts = {"summary.json": summary, "checks.json": checks, "cli_logs.json": cli_logs,
                 "counts.json": counts, "self_tests.json": self_tests,
                 "entry_events.json": entry_events}
    save_problems = []
    for name, payload in artifacts.items():
        path = container / name
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            readback = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            save_problems.append(f"{name} 写入/读回失败：{exc}")
            continue
        if canonical_sha256(readback) != canonical_sha256(payload):
            save_problems.append(f"{name} 读回内容不一致")
    persisted = json.loads((container / "summary.json").read_text(encoding="utf-8"))
    persisted_counts = json.loads((container / "counts.json").read_text(encoding="utf-8"))
    readback_problems = []
    if persisted["counts"] != persisted_counts:
        readback_problems.append("summary 与 counts 的计数不一致")
    if len(persisted["checks"]) != len(checks) or len(persisted["failures"]) != len(failures):
        readback_problems.append("summary 与内存 checks/failures 数量不一致")
    readback_ok = not save_problems and not readback_problems
    if not readback_ok:
        failures.append({"case": "FINAL_ARTIFACT_READBACK", "kind": "artifact", "result": "FAIL",
                         "problems": save_problems + readback_problems})
    readback_summary = {
        "case": "FINAL_ARTIFACT_READBACK", "kind": "artifact",
        "persisted_files": sorted(artifacts), "readback_problems": readback_problems,
        "save_problems": save_problems,
        "checks_persisted": len(checks), "failures_persisted": len(failures),
        "note": "本项为读回核对结果，独立保存于 final_readback.json，并如实打印；"
                "不计入 checks.json 的持久化检查条目数。",
        "ok": readback_ok,
    }
    (container / "final_readback.json").write_text(
        json.dumps(readback_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[{'PASS' if readback_ok else 'FAIL'}] FINAL_ARTIFACT_READBACK "
          f"{save_problems + readback_problems}（独立单列于 final_readback.json，"
          f"持久化检查条目 {len(checks)} 条 + 保护核对）")

    print()
    print(f"CLI 调用：start {counts['start_cli']}、status {counts['status_cli']}、"
          f"record {counts['record_cli']}、prepare-gate2 {counts['prepare_cli']}、"
          f"record-gate2 {counts['record_gate2_cli']}、screen {counts['screen_cli']}")
    print(f"进程内公开 API {counts['public_api_calls_inproc']}（含 helper 进入的 status）；"
          f"控制器入口分列 create {counts['controller_create_inproc']}、"
          f"prepare {counts['controller_prepare_inproc']}、record {counts['controller_record_inproc']}、"
          f"check {counts['controller_check_inproc']}（合计 {counts['controller_all_inproc']}；"
          f"其中 check+record 子集 {counts['controller_check_record_subset_inproc']}）")
    print(f"筛查核心（进程内可观测）{counts['screen_core_calls_inproc']}"
          f"＝宿主执行 {counts['screen_core_calls_inproc_host']}"
          f"＋测试直接再调用 {counts['screen_core_calls_inproc_test_direct']}；"
          f"CLI screen-rules 命令 {counts['screen_cli']}＝成功 {counts['screen_cli_success']}"
          f"＋前提拒绝 {counts['screen_cli_precondition_rejected']}"
          f"＋运行失败 {counts['screen_cli_runtime_failed']}（CLI 内部核心次数不可观测，记 null）")
    print(f"接收 {counts['receiver_starts']}、checker {counts['checker_runs']}、副本 {counts['copies']}、"
          f"故障注入 {counts['fault_injections']}、模拟决定 {counts['simulated_decisions']}、"
          f"真实批准 {counts['real_approvals']}")
    print(f"测试失败 {len(failures)}；受保护文件前后一致: {not protected_changed}")
    print(f"汇总: {container / 'summary.json'}")
    if failures:
        print("存在断言失败或保护失败，返回非零退出码（不输出总体成功结论）。")
        return 1
    print("全部预期成立。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
