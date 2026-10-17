#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-014-R1 验证入口：独立复算接入宿主（crosscheck-rules / 0006）的 B1—B4 定点与最终回归。

用法：
    .venv\\Scripts\\python.exe -B tests\\test_crosscheck_demo_workflow.py --out-dir data\\workflow_host_tests\\<容器>
    ... --only b1|g4|late          # 定点子集（B3 要求：局部失败只诊断受影响项）

证据口径（B3）：
- 每次 CLI 调用与每次公开 API 调用各有一条可直接核对的记录，含完整 command/exit_code/stdout/stderr 路径；
  API 记录引用单份完整返回或完整异常（含异常链）文件。
- receiver/checker 实际命令、退出码与原文与记录双向对应；筛查入口与复算入口分列。
- CLI 子进程内部核心调用次数不可观测 → 记 null，不把推导值冒充实测。
- missing/unregistered 进入正式 failures 并导致非零退出；另有一项隔离自测（审核副本去掉一条登记即失败）。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOST_PATH = PROJECT_ROOT / "scripts" / "run_demo_workflow.py"
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
BATCHES_ROOT = PROJECT_ROOT / "data" / "batches"
GENERATED = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a"
SQLITE_ROOT = PROJECT_ROOT / "data" / "sqlite_tests" / "workflow_gate2"
REPORT_BASELINE = (PROJECT_ROOT / "data" / "reviews" / "task014_gpt_20261012_213445"
                   / "source_hashes_after.json")
MAIN_BASELINE = (PROJECT_ROOT / "data" / "reviews" / "task013_r4_20261012_201824"
                 / "source_hashes_after.json")
SKIP_DIRS = {".venv", ".git"}
FROZEN_CORE = "8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2"
FROZEN_SCREEN_TEST = "27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca"

PROTECTED_FILES = [
    "scripts/control_demo_workflow.py", "scripts/receive_demo_batch.py",
    "scripts/check_demo_data.py", "scripts/normalize_demo_data.py",
    "scripts/store_demo_sqlite.py", "scripts/screen_demo_sqlite.py",
    "scripts/crosscheck_demo_rules.py", "scripts/build_demo_fact_packet.py",
    "sql/demo_schema.sql", "docs/SPEC_V1.md", "docs/AUDIT_CONTRACT_DRAFT.md",
    "tests/test_run_demo_workflow.py", "tests/test_record_demo_gate2_decision.py",
    "tests/test_screen_demo_workflow.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha256(payload) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False)
                          .encode("utf-8")).hexdigest()


def same_json(left, right) -> bool:
    return (json.dumps(left, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            == json.dumps(right, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def load_host():
    spec = importlib.util.spec_from_file_location("task014r1_host", HOST_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load_host()


def tree_hashes(root: Path) -> dict:
    if not root.exists():
        return {}
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def _load_json_if_parseable(path: Path) -> tuple:
    """现场可能是半写/损坏文件：可解析返回 (对象, True)，否则返回 ({}, False)。"""
    if not path.is_file():
        return {}, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}, False


def collect_batch_outcome(batch_dir: Path) -> dict:
    """从磁盘现场导出单个批次的复核结果（不依赖测试内部手工递增）。"""
    screening_path = batch_dir / "workflow" / "screening" / "screening_report.json"
    screening, _ = _load_json_if_parseable(screening_path)
    report_path = batch_dir / "workflow" / "crosscheck" / "crosscheck_report.json"
    report, report_parseable = _load_json_if_parseable(report_path)
    failure_path = batch_dir / "workflow" / "crosscheck" / "failure.json"
    failure, failure_parseable = _load_json_if_parseable(failure_path)
    voucher_path = batch_dir / "workflow" / "checkpoints" / "0006.json"
    voucher, voucher_parseable = _load_json_if_parseable(voucher_path)
    return {
        "screening_status": screening.get("batch_status"),
        "findings_total": len(screening.get("findings") or []),
        "crosscheck_report_present": report_path.is_file(),
        "crosscheck_report_parseable": report_parseable,
        "failure_parseable": failure_parseable,
        "voucher_0006_parseable": voucher_parseable,
        "crosscheck_report_sha256": sha256(report_path) if report_path.is_file() else None,
        "crosscheck_batch_status": report.get("batch_status"),
        "crosscheck_matched": report.get("matched"),
        "crosscheck_difference_count": (report.get("comparison") or {}).get("difference_count"),
        "failure_present": failure_path.is_file(),
        "failure_result": (failure.get("observed_outputs") or {}).get("result"),
        "failure_target_exit_code": failure.get("target_exit_code"),
        "voucher_0006_present": voucher_path.is_file(),
        "voucher_0006_sha256": sha256(voucher_path) if voucher_path.is_file() else None,
        "voucher_revision": voucher.get("revision"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TASK-014-R1 验证入口")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--only", default="all", choices=["all", "b1", "g4", "late"])
    args = parser.parse_args(argv)
    only = args.only

    container = Path(args.out_dir).resolve()
    for sub in ("cli_logs", "probe_records", "core_returns", "api_records", "isolation"):
        (container / sub).mkdir(parents=True, exist_ok=True)
    batch_parent = BATCHES_ROOT / container.name
    batch_parent.mkdir(parents=True, exist_ok=True)
    sqlite_parent = SQLITE_ROOT / container.name
    sqlite_parent.mkdir(parents=True, exist_ok=True)

    checks: list = []
    failures: list = []
    cli_records: list = []
    api_records: list = []
    tamper_records: list = []
    call_registry: list = []  # 权威调用登记表：每次真实调用发生时登记一条（隔离自测用其副本）
    counts = {
        "cli_calls": {}, "api_calls": {},
        "core_observations": {"verify_rule_facts_inprocess_observed": 0,
                              "screen_sqlite_inprocess_observed": 0,
                              "cli_internal_core_calls": None},
        "fault_injections": 0, "copies": 0, "receiver_starts": 0,
        "simulated_decisions": 0, "real_approvals": 0,
        "matched_crosscheck_reports": 0, "mismatch_crosscheck_reports": 0,
        "crosscheck_success_vouchers_0006": 0, "crosscheck_failure_scenes": 0,
        "checker_invocations": 0, "unregistered_records": 0, "missing_records": 0,
    }

    def record(name: str, kind: str, problems: list, **extra) -> None:
        entry = {"case": name, "kind": kind, "result": "PASS" if not problems else "FAIL",
                 "problems": problems, **extra}
        checks.append(entry)
        print(f"    [{'PASS' if not problems else 'FAIL'}] {name}"
              + ("" if not problems else f" | {problems[:2]}"))
        if problems:
            failures.append({"case": name, "problems": problems})

    def save_json(path: Path, payload) -> Path:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        return path

    def rel(path: Path) -> str:
        return str(path.relative_to(container)).replace("\\", "/")

    def batch_path(name: str) -> Path:
        return batch_parent / name

    def caller_names(depth: int, frame) -> list:
        names = []
        while frame is not None and len(names) < depth:
            names.append(frame.f_code.co_name)
            frame = frame.f_back
        return names

    def run_cli(label: str, sub_args: list, expect_exit) -> dict:
        command = [str(PYTHON), "-B", str(HOST_PATH), *sub_args]
        done = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True,
                              encoding="utf-8")
        stdout_path = container / "cli_logs" / f"{label}.stdout.txt"
        stderr_path = container / "cli_logs" / f"{label}.stderr.txt"
        stdout_path.write_text(done.stdout or "", encoding="utf-8")
        stderr_path.write_text(done.stderr or "", encoding="utf-8")
        try:
            payload = json.loads(done.stdout)
        except (json.JSONDecodeError, TypeError):
            payload = None
        subcommand = next((item for item in ("start", "status", "record-simulated-decision",
                                             "prepare-gate2", "record-simulated-gate2-decision",
                                             "screen-rules", "crosscheck-rules")
                           if item in sub_args), "unknown")
        return_path = container / "cli_logs" / f"{label}.return.json"
        save_json(return_path, payload if payload is not None
                  else {"_non_json_stdout": True, "_raw_sha256": hashlib.sha256(
                      (done.stdout or "").encode("utf-8")).hexdigest()})
        entry = {"record_kind": "cli", "label": label, "subcommand": subcommand,
                 "command": command, "cwd": str(PROJECT_ROOT), "exit_code": done.returncode,
                 "expected_exit": expect_exit,
                 "ok": (expect_exit is None or done.returncode == expect_exit),
                 "stdout_path": rel(stdout_path), "stderr_path": rel(stderr_path),
                 "stdout_sha256": sha256(stdout_path), "stderr_sha256": sha256(stderr_path),
                 "return_object_path": rel(return_path),
                 "return_object_sha256": sha256(return_path),
                 "return_object": payload}
        cli_records.append(entry)
        call_registry.append({"record": f"cli:{label}", "record_kind": "cli",
                              "subcommand": subcommand, "exit_code": done.returncode})
        counts["cli_calls"][subcommand] = counts["cli_calls"].get(subcommand, 0) + 1
        if subcommand == "start":
            counts["receiver_starts"] += 1
        if subcommand in ("record-simulated-decision", "record-simulated-gate2-decision"):
            counts["simulated_decisions"] += 1
        return entry

    def record_api(label: str, func, *func_args, expect_exception=None, **func_kwargs) -> dict:
        result, error = None, None
        try:
            result = func(*func_args, **func_kwargs)
        except Exception as exc:  # noqa: BLE001
            error = exc
        return_path = container / "api_records" / f"{label}.return.json"
        error_path = container / "api_records" / f"{label}.exception.json"
        if result is not None:
            save_json(return_path, result)
        if error is not None:
            # traceback 必须取自该异常对象自身（不能在 except 之外调用 format_exc，否则得到
            # "NoneType: None"）
            tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
            save_json(error_path, {"exception_class": type(error).__name__, "message": str(error),
                                   "stage": getattr(error, "stage", None),
                                   "reasons": [str(item) for item in
                                               getattr(error, "reasons", []) or []],
                                   "exception_chain": host._exception_chain(error),
                                   "traceback_source": "exception.__traceback__",
                                   "traceback": "".join(tb_lines)})
        entry = {"record_kind": "api", "label": label, "entry": getattr(func, "__name__", str(func)),
                 "args": [str(item) for item in func_args],
                 "outcome": ("returned" if error is None else "raised"),
                 "exception_class": type(error).__name__ if error else None,
                 "return_path": rel(return_path) if result is not None else None,
                 "return_sha256": sha256(return_path) if result is not None else None,
                 "exception_path": rel(error_path) if error is not None else None,
                 "exception_sha256": sha256(error_path) if error is not None else None,
                 "expected_exception": (expect_exception.__name__ if expect_exception else None)}
        api_records.append(entry)
        call_registry.append({"record": f"api:{label}", "record_kind": "api",
                              "entry": entry["entry"], "outcome": entry["outcome"]})
        counts["api_calls"][entry["entry"]] = counts["api_calls"].get(entry["entry"], 0) + 1
        if error is not None and expect_exception is not None \
                and not isinstance(error, expect_exception):
            failures.append({"case": f"api:{label}",
                             "problems": [f"期望 {expect_exception.__name__}，实际 "
                                          f"{type(error).__name__}: {error}"]})
        return entry

    def write_decision(batch_dir: Path, revision: int, gate: str, value: str, event_id: str) -> Path:
        payload = json.loads((batch_dir / f"workflow/checkpoints/{revision:04d}.json")
                             .read_text(encoding="utf-8"))
        request = payload["workflow"]["state"]["requests"][gate]
        body = {"event_id": event_id, "batch_id": batch_dir.name, "gate": gate,
                "request_id": request["request_id"],
                "materials_sha256": request["materials_sha256"],
                "decision": value, "actor_kind": "SIMULATED_HUMAN", "actor_id": "t14r1-tester",
                "occurred_at": "2026-10-12T22:00:00+08:00",
                "reason": "TASK-014-R1 开发态验证（模拟，非真实批准）",
                "simulation": "SIMULATED_TEST_ONLY",
                "confirmations": ({"scope_and_source_reviewed": True} if gate == "GATE1"
                                  else {"reconciliation_reviewed": True})}
        path = container / f"decision_{batch_dir.name}_{gate}_{value}.json"
        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return path

    def to_gate2_decision(name: str, fixture: str, value: str,
                          workbook: Path | None = None) -> Path:
        target = batch_path(name)
        run_cli(f"{name}_start", ["start", "--workbook",
                                  str(workbook or (GENERATED / "fixtures" / fixture)),
                                  "--batch-dir", str(target),
                                  "--source-description", f"TASK-014-R1 {name}"], 0)
        run_cli(f"{name}_gate1", ["record-simulated-decision", "--batch-dir", str(target),
                                  "--decision-file",
                                  str(write_decision(target, 1, "GATE1", "APPROVE",
                                                     f"EVT-{name}-G1"))], 0)
        run_cli(f"{name}_prepare", ["prepare-gate2", "--batch-dir", str(target)], 0)
        run_cli(f"{name}_gate2", ["record-simulated-gate2-decision", "--batch-dir", str(target),
                                  "--decision-file",
                                  str(write_decision(target, 3, "GATE2", value,
                                                     f"EVT-{name}-G2"))], 0)
        return target

    def screen_batch(name: str, fixture: str, value: str = "APPROVE", *,
                     tamper: bool = False) -> Path:
        target = to_gate2_decision(name, fixture, value)
        if not tamper:
            run_cli(f"{name}_screen", ["screen-rules", "--batch-dir", str(target)], 0)
            return target
        real_core = host.SCREEN_MODULE.screen_sqlite
        captured = {"real_return": None, "changed": None, "exception": None}

        def tampered_core(database, load_report, *, cutoff_date=None):
            result = real_core(database, load_report, cutoff_date=cutoff_date)
            counts["core_observations"]["screen_sqlite_inprocess_observed"] += 1
            captured["real_return"] = copy.deepcopy(result)
            changed = copy.deepcopy(result)
            for finding in changed.get("findings") or []:
                amounts = finding.get("amounts_cents")
                if not isinstance(amounts, dict):
                    continue
                for field in ("paid_total", "overpayment", "refund_total", "net_total",
                              "payable_amount", "allocated_amount", "paid_amount"):
                    value_int = amounts.get(field)
                    if isinstance(value_int, int) and not isinstance(value_int, bool):
                        amounts[field] = value_int + 1
                        captured["changed"] = {"rule_id": finding.get("rule_id"), "field": field,
                                               "field_path": f"amounts_cents.{field}",
                                               "before": value_int, "after": value_int + 1}
                        break
                if captured["changed"]:
                    break
            assert captured["changed"] is not None, "故障造样未找到可改整数分事实"
            counts["fault_injections"] += 1
            return changed

        host.SCREEN_MODULE.screen_sqlite = tampered_core
        try:
            # 必须在**本进程内**调用：CLI 是子进程，测试进程补丁不影响它。
            # 该公开调用同时进入同一直接记录入口（不得只留 probe 记录）。
            screen_api = record_api(f"{name}_screen_tampered", host.screen_dev_batch, target,
                                    expect_exception=None)
        finally:
            host.SCREEN_MODULE.screen_sqlite = real_core
        assert captured["changed"] is not None, "造样筛查未生效"
        assert screen_api["outcome"] == "returned", \
            f"造样筛查未按预期成功：{screen_api['exception_class']}"
        captured["api_label"] = screen_api["label"]
        captured["api_return_path"] = screen_api["return_path"]
        captured["api_record"] = screen_api
        source_record = save_json(container / "core_returns" / f"{name}_tamper_source.json", {
            "case": f"{name}_tamper_source", "batch_dir": str(target),
            "public_entry": "host.screen_dev_batch（进程内，包装真实 screen_sqlite）",
            "changed_fact": captured["changed"],
            "api_label": captured["api_label"],
            "api_return_reference": captured["api_return_path"],
            "note": "先取得真实核心返回，再深拷贝只改一处已存在整数分事实；宿主保存该测试报告；"
                    "该公开调用已登记进同一记录入口。"})
        captured["source_record"] = rel(source_record)
        tamper_records.append(captured)
        return target

    # ================================================================ B1
    print("== B1：真正最后一次复算摘要读取之后变更 → 本次调用即阻断")
    b1_problems: list = []
    b1_batch = screen_batch("b1_chain", "C06b.xlsx")
    run_cli("b1_crosscheck", ["crosscheck-rules", "--batch-dir", str(b1_batch)], 0)
    report_path = b1_batch / "workflow/crosscheck/crosscheck_report.json"
    report_backup = report_path.read_bytes()

    real_reader = host._read_crosscheck_outputs
    real_tail = host._verify_crosscheck_tail
    real_action = host.CONTROLLER_MODULE.check_dev_action
    baseline_sequence: list = []
    guard = {"verify_rule_facts": 0, "screen_sqlite": 0, "normalize_workbook": 0,
             "load_normalized_to_sqlite": 0}
    read_counter = {"n": 0}

    def traced_reader(batch_dir, stage, _real=real_reader):
        outputs = _real(batch_dir, stage)
        read_counter["n"] += 1
        baseline_sequence.append({"kind": "read_crosscheck_outputs", "stage": stage,
                                  "return_index": read_counter["n"],
                                  "caller": caller_names(4, sys._getframe(1)),
                                  "report_file_sha256_at_return": sha256(report_path)})
        return outputs

    def traced_tail(batch_dir, expected, stage, _real=real_tail):
        baseline_sequence.append({"kind": "verify_crosscheck_tail", "stage": stage,
                                  "caller": caller_names(4, sys._getframe(1)),
                                  "report_file_sha256_at_check": sha256(report_path)})
        return _real(batch_dir, expected, stage)

    def traced_action(workflow, action, *, current_bindings=None, _real=real_action):
        result = _real(workflow, action, current_bindings=current_bindings)
        baseline_sequence.append({"kind": "check_dev_action", "action": action,
                                  "caller": caller_names(4, sys._getframe(1))})
        return result

    host._read_crosscheck_outputs = traced_reader
    host._verify_crosscheck_tail = traced_tail
    host.CONTROLLER_MODULE.check_dev_action = traced_action
    baseline_api = record_api("b1_baseline_status", host.inspect_dev_batch, b1_batch)
    host._read_crosscheck_outputs = real_reader
    host._verify_crosscheck_tail = real_tail
    host.CONTROLLER_MODULE.check_dev_action = real_action

    reader_returns = [item for item in baseline_sequence
                      if item["kind"] == "read_crosscheck_outputs"]
    last_index = reader_returns[-1]["return_index"] if reader_returns else 0
    last_position = max((index for index, item in enumerate(baseline_sequence)
                         if item["kind"] == "read_crosscheck_outputs"), default=-1)
    tail_after_last_read = [item for item in baseline_sequence[last_position + 1:]
                            if item["kind"] == "verify_crosscheck_tail"]
    if baseline_api["outcome"] != "returned":
        b1_problems.append("未注入的合法调用必须成功（时序基线）")
    if last_index == 0:
        b1_problems.append("未观测到复算输出读取")
    if not tail_after_last_read:
        b1_problems.append("最后一次复算输出读取之后没有收尾磁盘复测（B1 未生效）")

    injected = {"done": False, "at": None, "before_sha256": None, "after_sha256": None,
                "returned_object_sha256": None, "only_change":
                    "workflow/crosscheck/crosscheck_report.json"}
    current = {"n": 0}

    def injecting_reader(batch_dir, stage, _real=real_reader):
        outputs = _real(batch_dir, stage)
        current["n"] += 1
        if current["n"] == last_index and not injected["done"]:
            injected["returned_object_sha256"] = canonical_sha256(outputs["report"])
            injected["before_sha256"] = sha256(report_path)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            payload["recomputed_facts"]["findings"] = []
            report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
            injected["after_sha256"] = sha256(report_path)
            injected["done"] = True
            injected["at"] = current["n"]
        return outputs

    host._read_crosscheck_outputs = injecting_reader
    injection_api = record_api("b1_late_injection_status", host.inspect_dev_batch, b1_batch,
                               expect_exception=host.WorkflowHostBlocked)
    host._read_crosscheck_outputs = real_reader
    injection_exception = None
    if injection_api["exception_path"]:
        injection_exception = json.loads((container / injection_api["exception_path"])
                                         .read_text(encoding="utf-8"))
    revoked = run_cli("b1_revoked_status", ["status", "--batch-dir", str(b1_batch)], 1)
    report_path.write_bytes(report_backup)
    restored = run_cli("b1_restored_status", ["status", "--batch-dir", str(b1_batch)], 0)

    b1_ok = (injection_api["outcome"] == "raised"
             and injection_api["exception_class"] == "WorkflowHostBlocked"
             and injected["done"] and injected["at"] == last_index
             and injected["before_sha256"] != injected["after_sha256"]
             and injection_exception is not None
             and "crosscheck_report.json" in injection_exception["message"]
             and revoked["exit_code"] == 1 and restored["exit_code"] == 0)
    if not b1_ok:
        b1_problems.append(
            f"B1 晚变更未被本次调用阻断或恢复不符：outcome={injection_api['outcome']} "
            f"injected_at={injected['at']}/{last_index} revoked={revoked['exit_code']} "
            f"restored={restored['exit_code']} "
            f"msg={(injection_exception or {}).get('message')}")
    save_json(container / "probe_records" / "b1_late_final_reader.json", {
        "case": "b1_late_final_reader", "batch_dir": str(b1_batch),
        "baseline_sequence": baseline_sequence, "last_reader_return_index": last_index,
        "tail_checks_after_last_read": len(tail_after_last_read),
        "tail_after_last_read_records": tail_after_last_read,
        "injection": injected, "api_record": injection_api, "exception": injection_exception,
        "revoked_cli_exit": revoked["exit_code"], "restored_cli_exit": restored["exit_code"],
        "note": "序号与调用位置来自未注入的合法调用实测；注入只在最后一次读取完整返回原始对象之后"
                "单次发生，wrapper 原样返回（返回对象指纹在注入前记录）。"})
    record("B1_LAST_SUMMARY_READ_THEN_CHANGE_BLOCKED", "host", b1_problems,
           last_reader_index=last_index, tail_after_last_read=len(tail_after_last_read))

    # ================================================================ B2
    print("== B2：有效失败诊断优先于半写 0006（恢复原诊断与退出 2）")
    b2_problems: list = []
    b2_probes: list = []
    for label, mode in (("partial", "partial"), ("throw", "throw")):
        target = screen_batch(f"b2_{label}", "C06b.xlsx")
        before = tree_hashes(target)
        sentinel = f"SENTINEL-T14R2-{label.upper()}-0006"
        state = {"target": (target / "workflow/checkpoints/0006.json").resolve(),
                 "open_calls": 0, "target_open": 0, "target_mode": None, "target_newline": None,
                 "target_kwargs": None, "text": None, "text_bytes": None, "write_hits": 0,
                 "handle_write_calls": 0, "partial_bytes": None, "path": None, "stage": None}
        real_open = open

        if mode == "partial":
            # 半写：不替换 writer 函数，只包装真实 writer 自己 open(..., mode='x', newline='\n')
            # 得到的写句柄；序列化与独占模式仍是真实实现。
            class _ObservedHandle:
                def __init__(self, handle, _state=state):
                    self._handle = handle

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    self._handle.close()
                    return False

                def write(self, text_str, _state=state):
                    if Path(getattr(self._handle, "name", "")).resolve() == _state["target"]:
                        _state["write_hits"] += 1
                        _state["handle_write_calls"] += 1
                        encoded = text_str.encode("utf-8")
                        _state["text"] = text_str
                        _state["text_bytes"] = encoded
                        partial = encoded[: max(1, len(encoded) // 2)]
                        # 真实句柄写入前半段；随后在真实 writer 的写调用上抛出 I/O 故障
                        written = self._handle.write(partial.decode("utf-8"))
                        _state["partial_bytes"] = len(partial)
                        del written
                        raise OSError("T14R2 注入的 0006 写入 I/O 故障（半写现场保留）")
                    return self._handle.write(text_str)

                def __getattr__(self, name):
                    return getattr(self._handle, name)

            def observed_open(file, open_mode="r", *open_args, _state=state, _real=real_open,
                              **open_kwargs):
                _state["open_calls"] += 1
                handle = _real(file, open_mode, *open_args, **open_kwargs)
                try:
                    resolved = Path(getattr(handle, "name", file)).resolve()
                except (OSError, TypeError):
                    return handle
                if resolved != _state["target"]:
                    return handle
                _state["target_open"] += 1
                _state["target_mode"] = open_mode
                _state["target_newline"] = open_kwargs.get("newline")
                _state["target_kwargs"] = {key: str(value) for key, value in open_kwargs.items()}
                return _ObservedHandle(handle)

            host.__builtins__["open"] = observed_open
        else:
            # 完整后 sentinel：保留真实 writer 函数，先让它完整写入并读回核验，再抛出运行失败；
            # 序列化、独占模式与全部写后核验仍是真实实现（GPT 本轮已通过该方法）。
            real_writer = host._write_exclusive_json

            def writer_then_sentinel(path, payload, stage,
                                     _real=real_writer, _state=state, _sentinel=sentinel):
                sha = _real(path, payload, stage)
                if Path(path).resolve() == _state["target"]:
                    _state["path"] = sha
                    _state["stage"] = stage
                    _state["target_open"] += 1
                    with real_open(path, "rb") as handle:
                        _state["text_bytes"] = handle.read()
                    _state["write_hits"] = 1
                    raise RuntimeError(_sentinel)
                return sha

            host._write_exclusive_json = writer_then_sentinel

        counts["fault_injections"] += 1
        try:
            api_entry = record_api(f"b2_{label}_crosscheck", host.crosscheck_dev_batch, target,
                                   expect_exception=host.WorkflowHostError)
        finally:
            host.__builtins__["open"] = real_open
            if mode == "throw":
                host._write_exclusive_json = real_writer

        after = tree_hashes(target)
        old_changed = sorted(path for path in before if before[path] != after.get(path))
        failure_path = target / "workflow/crosscheck/failure.json"
        failure = json.loads(failure_path.read_text(encoding="utf-8")) \
            if failure_path.is_file() else None
        recovery = run_cli(f"b2_{label}_recovery_status", ["status", "--batch-dir", str(target)], 2)
        recovery_payload = recovery["return_object"] or {}
        old_checkpoints_unchanged = all(before.get(path) == after.get(path) for path in before
                                        if "workflow/checkpoints/" in path and "0006" not in path)

        # 待写文本：按确切 UTF-8 字节写单份文件，再重新读取该文件计算字节数与文件哈希
        pending_path = container / "core_returns" / f"b2_{label}_pending_0006.json"
        if state["text_bytes"] is not None:
            with real_open(pending_path, "wb") as pending_handle:
                pending_handle.write(state["text_bytes"])
        pending_reread = pending_path.read_bytes() if pending_path.is_file() else b""
        pending_matches_buffer = (state["text_bytes"] is not None
                                 and pending_reread == state["text_bytes"])
        expected_partial = (state["text_bytes"] or b"")[: max(1, len(state["text_bytes"] or b"") // 2)]
        actual_partial = state["target"].read_bytes() if state["target"].is_file() else b""
        partial_matches = (actual_partial == expected_partial) if mode == "partial" else None

        ok = (api_entry["outcome"] == "raised"
              and api_entry["exception_class"] == "WorkflowHostError"
              and state["write_hits"] == 1
              and state["text_bytes"] is not None
              and pending_matches_buffer
              and recovery["exit_code"] == 2
              and recovery_payload.get("exception_class") == "WorkflowHostError"
              and failure is not None
              and failure["target_exit_code"] == 2
              and failure["exception_class"] == "WorkflowHostError"
              and failure["stage"] == "crosscheck"
              and any(link["class"] in ("OSError", "RuntimeError")
                      for link in failure["exception_chain"])
              and old_checkpoints_unchanged)
        if mode == "partial":
            ok = ok and state["target_open"] == 1 and state["target_mode"] == "x" \
                and state["target_newline"] == "\n" and partial_matches
        else:
            ok = ok and sentinel in json.dumps(failure, ensure_ascii=False)
        if not ok:
            b2_problems.append(
                f"{label}: 真实 writer 半写/恢复不符：outcome={api_entry['outcome']} "
                f"target_open={state['target_open']} mode={state['target_mode']!r} "
                f"newline={state['target_newline']!r} write_hits={state['write_hits']} "
                f"pending_matches={pending_matches_buffer} partial_matches={partial_matches} "
                f"recovery={recovery['exit_code']} stage={(failure or {}).get('stage')} "
                f"chain={[link.get('class') for link in (failure or {}).get('exception_chain', [])]}")
        if not pending_matches_buffer:
            b2_problems.append(f"{label}: 待写文本文件与真实 writer 缓冲不一致（引用不实）")
        probe = {"case": f"b2_{label}", "batch_dir": str(target), "mode": mode,
                 "public_entry": ("host.crosscheck_dev_batch（进程内；partial：仅包装真实 writer 自己 "
                                  "open 的写句柄，不替换 writer；throw：保留真实 writer 完整写入后抛 sentinel）"),
                 "real_writer": {
                     "function": "_write_exclusive_json",
                     "target_open_calls": state["target_open"],
                     "total_open_calls_observed": state["open_calls"],
                     "open_mode": state["target_mode"],
                     "open_newline": state["target_newline"],
                     "open_kwargs": state["target_kwargs"],
                     "write_hits": state["write_hits"],
                     "handle_write_calls": state["handle_write_calls"],
                     "serialization_untouched": True,
                     "written_sha256": state.get("path")},
                 "pending_full_text": {
                     "path": rel(pending_path),
                     "file_bytes": pending_path.stat().st_size if pending_path.is_file() else None,
                     "file_sha256": sha256(pending_path) if pending_path.is_file() else None,
                     "buffer_bytes": len(state["text_bytes"] or b""),
                     "buffer_sha256": hashlib.sha256(state["text_bytes"] or b"").hexdigest(),
                     "reread_matches_buffer": pending_matches_buffer},
                 "half_written": {"expected_partial_bytes": len(expected_partial),
                                  "actual_bytes_on_disk": len(actual_partial),
                                  "matches": partial_matches},
                 "actual_checkpoint6_bytes": (state["target"].stat().st_size
                                              if state["target"].is_file() else None),
                 "api_record": api_entry, "failure": failure,
                 "recovery_cli": {"exit_code": recovery["exit_code"],
                                  "payload": recovery["return_object"]},
                 "old_files_changed": old_changed,
                 "old_checkpoints_unchanged": old_checkpoints_unchanged,
                 "sentinel": sentinel if mode == "throw" else None,
                 "note": ("partial：真实 writer 进入 1 次、写入命中 1 次、模式 x、newline '\\n'，"
                          "前半段写入后抛 OSError 并由 writer 的 OSError 分支映射为 WorkflowHostError；"
                          "throw：真实 writer 完整写入并读回核验成功后抛 sentinel（与本卡 §2「已有通过证据、"
                          "只修正其文本引用元数据」一致）。")}
        save_json(container / "probe_records" / f"b2_{label}_persistence.json", probe)
        b2_probes.append({"case": f"b2_{label}", "ok": ok, "recovery_exit": recovery["exit_code"],
                          "target_open": state["target_open"], "mode": state["target_mode"],
                          "pending_matches": pending_matches_buffer})
        counts["crosscheck_failure_scenes"] += 1
    record("B2_FAILURE_DIAGNOSTIC_PRECEDENCE_AND_EXIT2", "host", b2_problems, probes=b2_probes)

    # ================================================================ B4
    print("== B4：normalized 同缓冲读取与 started.json 规范对象指纹")
    b4_problems: list = []
    started = json.loads((b1_batch / "workflow/crosscheck/started.json").read_text(encoding="utf-8"))
    outputs = host._read_gate2_outputs(b1_batch, "probe")
    normalized_object_sha = canonical_sha256(outputs["normalized"])
    screening_report_obj = json.loads((b1_batch / "workflow/screening/screening_report.json")
                                      .read_text(encoding="utf-8"))
    screening_object_sha = canonical_sha256(screening_report_obj)
    for key in ("normalized_payload_sha256", "screening_report_canonical_sha256"):
        if key not in started:
            b4_problems.append(f"started.json 缺少 {key}")
    if started.get("normalized_payload_sha256") != normalized_object_sha:
        b4_problems.append("started.normalized_payload_sha256 与本批次对象指纹不一致")
    if started.get("normalized_payload_sha256") != outputs["load_report"]["normalized_payload_sha256"]:
        b4_problems.append("started.normalized_payload_sha256 与装载报告声明不一致")
    if started.get("screening_report_canonical_sha256") != screening_object_sha:
        b4_problems.append("started.screening_report_canonical_sha256 与筛查报告对象指纹不一致")
    if started.get("normalized_file_sha256") == started.get("normalized_payload_sha256"):
        b4_problems.append("文件字节哈希与对象指纹不得混用（当前值相同）")
    started_path = b1_batch / "workflow/crosscheck/started.json"
    started_backup = started_path.read_bytes()
    wrong = json.loads(started_backup.decode("utf-8"))
    wrong["normalized_payload_sha256"] = "0" * 64
    started_path.write_text(json.dumps(wrong, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts["fault_injections"] += 1
    tampered_status = run_cli("b4_started_fingerprint_tampered",
                              ["status", "--batch-dir", str(b1_batch)], 1)
    tampered_message = (tampered_status["return_object"] or {}).get("message") or ""
    started_path.write_bytes(started_backup)
    restored_status = run_cli("b4_started_fingerprint_restored",
                              ["status", "--batch-dir", str(b1_batch)], 0)
    if "normalized_payload_sha256" not in tampered_message:
        b4_problems.append(f"恢复端未严格校验 started 对象指纹：{tampered_message[:160]}")
    if restored_status["exit_code"] != 0:
        b4_problems.append("恢复原件后 status 未回到退出 0")
    save_json(container / "probe_records" / "b4_started_and_same_buffer.json", {
        "case": "b4_started_and_same_buffer", "batch_dir": str(b1_batch), "started": started,
        "normalized_file_sha256_same_buffer": outputs["normalized_file_sha256"],
        "normalized_payload_sha256_from_object": normalized_object_sha,
        "load_report_declared_normalized_payload_sha256":
            outputs["load_report"]["normalized_payload_sha256"],
        "screening_report_canonical_sha256": screening_object_sha,
        "tampered_field_rejection": {"exit_code": tampered_status["exit_code"],
                                     "message": tampered_message},
        "restored_exit_code": restored_status["exit_code"],
        "note": "对象与文件字节哈希来自同一次读取缓冲（_read_json_with_bytes）；started.json 分别保存"
                "文件字节哈希与规范对象指纹，恢复端严格校验。"})
    record("B4_SAME_BUFFER_AND_STARTED_FINGERPRINTS", "host", b4_problems)

    if only in ("b1", "g4", "late"):
        save_json(container / "summary.json", {"mode": f"only={only}", "checks": checks,
                                              "failures": failures, "counts": counts})
        print(f"定点模式 only={only}：{len(checks)} 项检查、{len(failures)} 项失败")
        return 1 if failures else 0

    # ================================================================ G1
    print("== G1 MAIN：完整建链到一次真实 MATCHED 复算并保存 0006")
    g1_problems: list = []
    main_batch = to_gate2_decision("main_01", "", "APPROVE",
                                   workbook=GENERATED / "input" / "erp_export.xlsx")
    run_cli("main_screen", ["screen-rules", "--batch-dir", str(main_batch)], 0)
    screen_report = json.loads((main_batch / "workflow/screening/screening_report.json")
                               .read_text(encoding="utf-8"))
    distribution = {rule: sum(1 for item in screen_report["findings"]
                              if item.get("rule_id") == rule)
                    for rule in ("R01", "R02", "R03", "R04")}
    if distribution != {"R01": 3, "R02": 5, "R03": 2, "R04": 2}:
        g1_problems.append(f"MAIN 筛查分布不符：{distribution}")
    if screen_report["statistics"]["r02_overpayment_total_cents"] != 1600000:
        g1_problems.append("MAIN R02 超额不是 1,600,000 分")

    core_state = {"count": 0, "return_path": None}
    real_verify = host.CROSSCHECK_MODULE.verify_rule_facts

    def capturing_verify(normalized, screening_report_input):
        # 调用前：保留真实输入对象的引用快照，并在调用**之前**计算指纹
        core_state["normalized_input_ref"] = normalized
        core_state["screening_input_ref"] = screening_report_input
        core_state["normalized_before_sha256"] = canonical_sha256(normalized)
        core_state["screening_before_sha256"] = canonical_sha256(screening_report_input)
        result = real_verify(normalized, screening_report_input)
        counts["core_observations"]["verify_rule_facts_inprocess_observed"] += 1
        core_state["count"] += 1
        path = save_json(container / "core_returns" / "main_01_verify_rule_facts_return.json",
                         result)
        core_state["return_path"] = rel(path)
        return result

    host.CROSSCHECK_MODULE.verify_rule_facts = capturing_verify
    crosscheck_api = record_api("main_crosscheck", host.crosscheck_dev_batch, main_batch)
    # 公开调用完成之后：对**保留的真实输入对象引用**再算指纹，与调用前指纹比较
    core_state["normalized_after_sha256"] = canonical_sha256(core_state["normalized_input_ref"])
    core_state["screening_after_sha256"] = canonical_sha256(core_state["screening_input_ref"])
    core_state["input_object_references_retained"] = True
    host.CROSSCHECK_MODULE.verify_rule_facts = real_verify

    api_return = (json.loads((container / crosscheck_api["return_path"]).read_text(encoding="utf-8"))
                  if crosscheck_api["return_path"] else {})
    real_return = (json.loads((container / core_state["return_path"]).read_text(encoding="utf-8"))
                   if core_state["return_path"] else None)
    report_on_disk_path = main_batch / "workflow/crosscheck/crosscheck_report.json"
    report_on_disk = json.loads(report_on_disk_path.read_text(encoding="utf-8"))
    if core_state["count"] != 1:
        g1_problems.append(f"冻结复算核心必须真实调用恰 1 次，实际 {core_state['count']}")
    if real_return is None or not same_json(report_on_disk, real_return):
        g1_problems.append("落盘报告与冻结核心本次完整真实返回不严格相等")
    if core_state["normalized_before_sha256"] != core_state["normalized_after_sha256"] \
            or core_state["screening_before_sha256"] != core_state["screening_after_sha256"]:
        g1_problems.append("复算修改了传入的 normalized／screening_report 对象")
    if api_return.get("crosscheck_status") != "RULE_CROSSCHECK_RECORDED" \
            or api_return.get("crosscheck_matched") is not True \
            or api_return.get("phase") != "DEV_GATE2_APPROVED":
        g1_problems.append(f"复算返回不符：{api_return.get('crosscheck_status')!r}/"
                           f"{api_return.get('crosscheck_matched')!r}/{api_return.get('phase')!r}")
    if api_return.get("next_step_allowed") is not False or api_return.get("real_approvals") != 0:
        g1_problems.append("next_step_allowed 必须 false、真实批准必须 0")
    recomputed = (real_return or {}).get("rule_recomputed_counts", {})
    if {key: recomputed.get(key) for key in ("R01", "R02", "R03", "R04")} != distribution:
        g1_problems.append(f"复算计数与筛查分布不一致：{recomputed} vs {distribution}")
    dimensions = (real_return or {}).get("comparison", {}).get("dimensions", {})
    if set(dimensions) != set(host.CROSSCHECK_DIMENSIONS):
        g1_problems.append(f"十维度不齐：{sorted(dimensions)}")
    for name in host.CROSSCHECK_DIMENSIONS:
        item = dimensions.get(name, {})
        if item.get("executed") is not True or item.get("matched") is not True \
                or not isinstance(item.get("difference_count"), int) \
                or isinstance(item.get("difference_count"), bool) \
                or item.get("difference_count") != 0:
            g1_problems.append(f"维度 {name} 未按严格成功口径：{item}")
    if (real_return or {}).get("differences") != [] \
            or (real_return or {}).get("comparison", {}).get("difference_count") != 0:
        g1_problems.append("MATCHED 报告必须差异为空且差异数为 0")
    checkpoint6 = json.loads((main_batch / "workflow/checkpoints/0006.json")
                             .read_text(encoding="utf-8"))
    checkpoint5 = json.loads((main_batch / "workflow/checkpoints/0005.json")
                             .read_text(encoding="utf-8"))
    if checkpoint6["revision"] != 6 or checkpoint6["operation"]["kind"] != "RUN_RULE_CROSSCHECK":
        g1_problems.append("0006 形状不符")
    if checkpoint6["previous_file_sha256"] != sha256(main_batch / "workflow/checkpoints/0005.json"):
        g1_problems.append("0006 前序必须等于 0005 实读字节哈希")
    if not same_json(checkpoint6["workflow"], checkpoint5["workflow"]):
        g1_problems.append("0006 workflow 必须与 0005 严格相等")
    counts["matched_crosscheck_reports"] += 1
    counts["crosscheck_success_vouchers_0006"] += 1
    save_json(container / "probe_records" / "g1_main_crosscheck.json", {
        "case": "g1_main_crosscheck", "batch_dir": str(main_batch), "api_record": crosscheck_api,
        "core_return_path": core_state["return_path"],
        "core_return_canonical_sha256": canonical_sha256(real_return) if real_return else None,
        "on_disk_report_canonical_sha256": canonical_sha256(report_on_disk),
        "on_disk_report_file_sha256": sha256(report_on_disk_path),
        "core_observed_calls": core_state["count"],
        "input_object_fingerprints": {
            "normalized_before": core_state.get("normalized_before_sha256"),
            "normalized_after": core_state.get("normalized_after_sha256"),
            "screening_before": core_state.get("screening_before_sha256"),
            "screening_after": core_state.get("screening_after_sha256")},
        "input_object_files": {
            "normalized": {"path": "workflow/gate2/normalized.json",
                           "file_sha256": sha256(main_batch / "workflow/gate2/normalized.json")},
            "screening_report": {"path": "workflow/screening/screening_report.json",
                                 "file_sha256": sha256(
                                     main_batch / "workflow/screening/screening_report.json")}},
        "distribution": distribution, "recomputed_counts": recomputed,
        "dimensions": dimensions, "differences": (real_return or {}).get("differences"),
        "checkpoint6": {"revision": checkpoint6["revision"],
                        "kind": checkpoint6["operation"]["kind"],
                        "previous_file_sha256": checkpoint6["previous_file_sha256"]},
        "note": "完整真实返回单份保存于 core_return_path；两个输入完整对象已有文件，以相对路径与"
                "字节哈希引用。"})
    record("G1_MAIN_CROSSCHECK_MATCHED", "flow", g1_problems, distribution=distribution,
           core_calls=core_state["count"])

    # ================================================================ G2
    print("== G2 小样与路径边界")
    g2_problems: list = []
    samples = {}
    for name, fixture in (("g2_c06b", "C06b.xlsx"), ("g2_c03", "C03.xlsx"),
                          ("g2_c07b", "C07b.xlsx")):
        target = screen_batch(name, fixture)
        entry = run_cli(f"{name}_crosscheck", ["crosscheck-rules", "--batch-dir", str(target)], 0)
        payload = entry["return_object"] or {}
        report = json.loads((target / "workflow/crosscheck/crosscheck_report.json")
                            .read_text(encoding="utf-8"))
        repeat = run_cli(f"{name}_repeat_crosscheck",
                         ["crosscheck-rules", "--batch-dir", str(target)], 1)
        status = run_cli(f"{name}_status", ["status", "--batch-dir", str(target)], 0)
        status_payload = status["return_object"] or {}
        ok = (entry["exit_code"] == 0
              and payload.get("crosscheck_status") == "RULE_CROSSCHECK_RECORDED"
              and payload.get("crosscheck_matched") is True
              and report["batch_status"] == "DEV_CROSSCHECK_MATCHED"
              and report["differences"] == []
              and repeat["exit_code"] == 1
              and status_payload.get("crosscheck_status") == "RULE_CROSSCHECK_RECORDED")
        if not ok:
            g2_problems.append(f"{name} 不符：crosscheck={entry['exit_code']} "
                               f"repeat={repeat['exit_code']}")
        counts["matched_crosscheck_reports"] += 1
        counts["crosscheck_success_vouchers_0006"] += 1
        samples[name] = {"batch_dir": str(target), "crosscheck_exit": entry["exit_code"],
                         "matched": payload.get("crosscheck_matched"),
                         "recomputed_counts": report["rule_recomputed_counts"],
                         "repeat_exit": repeat["exit_code"], "status_exit": status["exit_code"]}
    early_target = to_gate2_decision("g2_early", "C06b.xlsx", "APPROVE")
    early = run_cli("g2_early_crosscheck", ["crosscheck-rules", "--batch-dir", str(early_target)], 1)
    early_message = (early["return_object"] or {}).get("message") or ""
    if "0005" not in early_message or (early_target / "workflow/crosscheck").exists():
        g2_problems.append(f"过早调用未被拒绝或产生现场：{early_message[:160]}")
    hold_target = to_gate2_decision("g2_hold", "C06b.xlsx", "HOLD")
    hold = run_cli("g2_hold_crosscheck", ["crosscheck-rules", "--batch-dir", str(hold_target)], 1)
    hold_message = (hold["return_object"] or {}).get("message") or ""
    if "0005" not in hold_message or (hold_target / "workflow/crosscheck").exists():
        g2_problems.append(f"HOLD 对照未被拒绝或产生现场：{hold_message[:160]}")
    save_json(container / "probe_records" / "g2_samples_and_boundaries.json", {
        "case": "g2_samples_and_boundaries", "samples": samples,
        "early": {"batch_dir": str(early_target), "exit_code": early["exit_code"],
                  "message": early_message},
        "hold": {"batch_dir": str(hold_target), "exit_code": hold["exit_code"],
                 "message": hold_message}})
    record("G2_SAMPLES_AND_PATH_BOUNDARIES", "flow", g2_problems, samples=list(samples))

    # ================================================================ G3
    print("== G3 真实 MISMATCH")
    g3_problems: list = []
    mismatch_batch = screen_batch("g3_mismatch", "C06b.xlsx", tamper=True)
    tamper = tamper_records[-1]
    mismatch = run_cli("g3_mismatch_crosscheck",
                       ["crosscheck-rules", "--batch-dir", str(mismatch_batch)], 1)
    mismatch_payload = mismatch["return_object"] or {}
    mismatch_message = mismatch_payload.get("message") or ""
    mismatch_report_path = mismatch_batch / "workflow/crosscheck/crosscheck_report.json"
    mismatch_report = (json.loads(mismatch_report_path.read_text(encoding="utf-8"))
                       if mismatch_report_path.is_file() else None)
    checkpoint6_exists = (mismatch_batch / "workflow/checkpoints/0006.json").exists()
    failure_path = mismatch_batch / "workflow/crosscheck/failure.json"
    failure = json.loads(failure_path.read_text(encoding="utf-8")) if failure_path.is_file() else None
    status_after = run_cli("g3_mismatch_status", ["status", "--batch-dir", str(mismatch_batch)], 1)
    field_paths = [str(item.get("field_path") or "")
                   for item in (mismatch_report or {}).get("differences") or []]
    ok = (mismatch["exit_code"] == 1
          and mismatch_payload.get("exception_class") == "WorkflowHostBlocked"
          and "BLOCKED_CROSSCHECK" in mismatch_message
          and mismatch_report is not None
          and mismatch_report["batch_status"] == "DEV_CROSSCHECK_MISMATCH"
          and mismatch_report["matched"] is False
          and mismatch_report["comparison"]["difference_count"] > 0
          and not checkpoint6_exists
          and failure is not None and failure["target_exit_code"] == 1
          and (failure.get("observed_outputs") or {}).get("result") == "BLOCKED_CROSSCHECK"
          and status_after["exit_code"] == 1
          and any(tamper["changed"]["field"] in path for path in field_paths))
    if not ok:
        g3_problems.append(f"MISMATCH 处置不符：exit={mismatch['exit_code']} "
                           f"0006={checkpoint6_exists} status_after={status_after['exit_code']} "
                           f"field_paths={field_paths}")
    counts["mismatch_crosscheck_reports"] += 1
    counts["crosscheck_failure_scenes"] += 1
    save_json(container / "probe_records" / "g3_real_mismatch.json", {
        "case": "g3_real_mismatch", "batch_dir": str(mismatch_batch),
        "tamper_source_record": tamper["source_record"], "changed_fact": tamper["changed"],
        "cli_record": mismatch, "exception_class": mismatch_payload.get("exception_class"),
        "message": mismatch_message, "difference_field_paths": field_paths,
        "differences": (mismatch_report or {}).get("differences"),
        "checkpoint_0006_exists": checkpoint6_exists, "failure": failure,
        "status_after_exit": status_after["exit_code"]})
    record("G3_REAL_MISMATCH", "flow", g3_problems, field_paths=field_paths)

    # ================================================================ G5 路径反例
    print("== G5 路径反例（固定报告相对路径）")
    g5_problems: list = []
    path_target = screen_batch("g5_path", "C06b.xlsx")
    run_cli("g5_path_crosscheck", ["crosscheck-rules", "--batch-dir", str(path_target)], 0)
    checkpoint6_path = path_target / "workflow/checkpoints/0006.json"
    backup6 = checkpoint6_path.read_bytes()
    payload6 = json.loads(checkpoint6_path.read_text(encoding="utf-8"))
    original_relative = payload6["operation"]["report_relative"]
    payload6["operation"]["report_relative"] = "workflow/crosscheck/not_the_report.json"
    checkpoint6_path.write_text(json.dumps(payload6, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    counts["fault_injections"] += 1
    path_status = run_cli("g5_path_status", ["status", "--batch-dir", str(path_target)], 1)
    path_message = (path_status["return_object"] or {}).get("message") or ""
    checkpoint6_path.write_bytes(backup6)
    path_restored = run_cli("g5_path_restored", ["status", "--batch-dir", str(path_target)], 0)
    if "report_relative" not in path_message or "0006.json" not in path_message \
            or path_restored["exit_code"] != 0:
        g5_problems.append(f"路径反例不符：exit={path_status['exit_code']} "
                           f"restored={path_restored['exit_code']} msg={path_message[:160]}")
    save_json(container / "probe_records" / "g5_path_field_rejection.json", {
        "case": "g5_path_field_rejection", "batch_dir": str(path_target),
        "original_relative": original_relative,
        "changed_relative": payload6["operation"]["report_relative"],
        "exit_code": path_status["exit_code"], "message": path_message,
        "restored_exit": path_restored["exit_code"]})
    record("G5_PATH_FIELD_REJECTION", "flow", g5_problems)

    # ================================================================ G6
    print("== G6 链、只读（同进程）与输入完整")
    g6_problems: list = []
    chain_names = sorted(item.name for item in (main_batch / "workflow/checkpoints").iterdir())
    if chain_names != ["000%d.json" % index for index in range(1, 7)]:
        g6_problems.append(f"链不是连续 0001—0006：{chain_names}")
    if (main_batch / "workflow/checkpoints/0007.json").exists():
        g6_problems.append("不得存在 0007")
    state6 = checkpoint6["workflow"]["state"]
    if state6["gate1_approval"] is not None or state6["gate2_approval"] is not None:
        g6_problems.append("真实批准必须仍为 null")
    if state6["next_step_allowed"] is not False:
        g6_problems.append("next_step_allowed 必须仍为 false")

    guard_names = [("verify_rule_facts", host.CROSSCHECK_MODULE, "verify_rule_facts"),
                   ("screen_sqlite", host.SCREEN_MODULE, "screen_sqlite"),
                   ("normalize_workbook", host.NORMALIZER_MODULE, "normalize_workbook"),
                   ("load_normalized_to_sqlite", host.STORE_MODULE, "load_normalized_to_sqlite")]
    guards = {}
    for label, module, attr in guard_names:
        if not hasattr(module, attr):
            g6_problems.append(f"待禁用的下游函数不存在：{label}")
            continue
        guards[label] = (module, attr, getattr(module, attr))

        def forbidden(*_args, _label=label, **_kwargs):
            guard[_label] += 1
            raise AssertionError(f"status 不得调用下游核心 {_label}")

        setattr(module, attr, forbidden)
    tree_before = tree_hashes(main_batch)
    readonly_api = record_api("g6_readonly_status_inprocess", host.inspect_dev_batch, main_batch)
    tree_after = tree_hashes(main_batch)
    for label, (module, attr, original) in guards.items():
        setattr(module, attr, original)
    readonly_return = (json.loads((container / readonly_api["return_path"]).read_text(encoding="utf-8"))
                       if readonly_api["return_path"] else {})
    if readonly_api["outcome"] != "returned":
        g6_problems.append(f"同进程只读 status 未成功：{readonly_api['exception_class']}")
    if any(value != 0 for value in guard.values()):
        g6_problems.append(f"只读 status 触达了下游核心：{guard}")
    if tree_before != tree_after:
        g6_problems.append("只读 status 改写了批次文件")
    cli_readonly = run_cli("g6_readonly_status_cli", ["status", "--batch-dir", str(main_batch)], 0)
    if cli_readonly["exit_code"] != 0:
        g6_problems.append("普通 CLI 只读恢复未成功")
    db_path = sqlite_parent / main_batch.name / "audit.sqlite3"
    artifacts_on_disk = json.loads((main_batch / "workflow/crosscheck/artifacts.json")
                                   .read_text(encoding="utf-8"))
    if sha256(db_path) != artifacts_on_disk["database_sha256"]:
        g6_problems.append("数据库字节与 0006 声明不一致")
    save_json(container / "probe_records" / "g6_chain_readonly_and_input.json", {
        "case": "g6_chain_readonly_and_input", "batch_dir": str(main_batch),
        "checkpoints": chain_names, "phase": readonly_return.get("phase"),
        "crosscheck_status": readonly_return.get("crosscheck_status"),
        "completed_actions": readonly_return.get("completed_actions"),
        "same_process_readonly": {"api_record": readonly_api, "guarded_functions": sorted(guards),
                                  "guard_hits": guard, "tree_unchanged": tree_before == tree_after},
        "cli_readonly": {"exit_code": cli_readonly["exit_code"]},
        "input_object_fingerprints": {
            "normalized_before": core_state.get("normalized_before_sha256"),
            "normalized_after": core_state.get("normalized_after_sha256"),
            "screening_before": core_state.get("screening_before_sha256"),
            "screening_after": core_state.get("screening_after_sha256")},
        "database_sha256": sha256(db_path),
        "state6_approvals": {"gate1": state6["gate1_approval"], "gate2": state6["gate2_approval"]},
        "next_step_allowed": state6["next_step_allowed"]})
    record("G6_CHAIN_READONLY_AND_INPUT_INTEGRITY", "flow", g6_problems, guard_hits=guard,
           chain=chain_names)

    # ================================================================ 现场清单与 receiver/checker 核对
    print("== 现场清单（从记录与磁盘导出）与 receiver/checker 双向核对")
    scene_problems: list = []
    scene_records: list = []
    checker_records: list = []
    for batch_dir in sorted((item for item in batch_parent.iterdir() if item.is_dir()),
                            key=lambda item: item.name):
        manifest_path = batch_dir / "batch_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) \
            if manifest_path.is_file() else {}
        invocation = manifest.get("checker_invocation")
        entry = {"batch": batch_dir.name, "batch_manifest": manifest_path.is_file(),
                 "batch_manifest_sha256": sha256(manifest_path) if manifest_path.is_file() else None,
                 "checker_invocation_present": isinstance(invocation, dict)}
        if isinstance(invocation, dict):
            entry["checker"] = {
                "argv": invocation.get("argv"), "attempted": invocation.get("attempted"),
                "started": invocation.get("started"), "exit_code": invocation.get("exit_code"),
                "report_result": invocation.get("report_result")}
            for key in ("report", "stdout_log", "stderr_log"):
                reference = invocation.get(key) or {}
                reference_path = batch_dir / str(reference.get("path") or "")
                exists = reference_path.is_file()
                actual_sha = sha256(reference_path) if exists else None
                entry[f"{key}_reference"] = {
                    "path": str(reference.get("path")), "exists": exists,
                    "declared_exists": reference.get("exists"),
                    "declared_sha256": reference.get("sha256"), "actual_sha256": actual_sha,
                    "verified": bool(exists and actual_sha == reference.get("sha256")
                                     and reference.get("exists") is True)}
                if not entry[f"{key}_reference"]["verified"]:
                    scene_problems.append(f"{batch_dir.name}: checker {key} 引用未验证通过")
            if not (invocation.get("started") is True and invocation.get("exit_code") == 0):
                scene_problems.append(f"{batch_dir.name}: checker 未记录 started=true/exit_code=0")
            checker_records.append({"batch": batch_dir.name,
                                    "argv": invocation.get("argv"),
                                    "started": invocation.get("started"),
                                    "exit_code": invocation.get("exit_code"),
                                    "report_result": invocation.get("report_result"),
                                    "stdout_sha256": (invocation.get("stdout_log") or {}).get("sha256"),
                                    "stderr_sha256": (invocation.get("stderr_log") or {}).get("sha256")})
        # receiver 实际命令与退出码：宿主清单 receive + receive_invocation.json
        host_manifest_path = batch_dir / "workflow" / "host_manifest.json"
        host_manifest = json.loads(host_manifest_path.read_text(encoding="utf-8")) \
            if host_manifest_path.is_file() else {}
        receive = host_manifest.get("receive") or {}
        invocation_record = batch_dir / "workflow" / "receive_invocation.json"
        inv_payload = json.loads(invocation_record.read_text(encoding="utf-8")) \
            if invocation_record.is_file() else {}
        entry["receiver"] = {
            "manifest_command": receive.get("command"), "manifest_exit_code": receive.get("exit_code"),
            "invocation_command": inv_payload.get("command"),
            "invocation_exit_code": inv_payload.get("exit_code"),
            "command_matches": receive.get("command") == inv_payload.get("command"),
            "exit_code_matches": receive.get("exit_code") == inv_payload.get("exit_code")}
        entry["outcome"] = collect_batch_outcome(batch_dir)
        scene_records.append(entry)

    receiver_batches = [item for item in scene_records if item["receiver"].get("manifest_exit_code") == 0]
    checker_started = [item for item in checker_records if item.get("started") is True]
    checker_exit_zero = [item for item in checker_records if item.get("exit_code") == 0]
    mismatched_receiver = [item["batch"] for item in scene_records
                           if not item["receiver"].get("command_matches")
                           or not item["receiver"].get("exit_code_matches")]
    if len(checker_started) != len(scene_records):
        scene_problems.append(f"checker started 数与批次不符：{len(checker_started)}/{len(scene_records)}")
    if len(checker_exit_zero) != len(scene_records):
        scene_problems.append(f"checker exit_code=0 数与批次不符：{len(checker_exit_zero)}/"
                              f"{len(scene_records)}")
    if mismatched_receiver:
        scene_problems.append(f"receiver 命令/退出码在清单与调用记录间不一致：{mismatched_receiver}")
    if not scene_records:
        scene_problems.append("未发现任何批次现场")
    counts["checker_invocations_started_by_receiver"] = len(checker_started)
    counts["checker_invocations_exit_zero"] = len(checker_exit_zero)
    counts["receiver_starts_recorded"] = len(receiver_batches)
    save_json(container / "probe_records" / "scene_inventory_and_subprocess_audit.json", {
        "case": "scene_inventory_and_subprocess_audit", "batches": scene_records,
        "checker_records": checker_records,
        "counts": {"batches": len(scene_records), "checker_started": len(checker_started),
                   "checker_exit_zero": len(checker_exit_zero)},
        "note": "checker 由 receiver 子进程实际启动：直接 checker CLI 调用为 0，但真实执行次数按批次留痕核对。"})
    record("SCENE_INVENTORY_AND_SUBPROCESS_AUDIT", "evidence", scene_problems,
           batches=len(scene_records), checker_started=len(checker_started))

    # ================================================================ G7 保护比较
    print("== G7 保护比较（R1 基线与 R4 主基线，一次扫描复用）")
    g7_problems: list = []
    current_scan = {}
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        if relative.split("/")[0] in SKIP_DIRS:
            continue
        try:
            current_scan[relative] = sha256(path)
        except OSError:
            continue
    scan_path = save_json(container / "protected_scan.json", current_scan)

    allowed_r1 = {"scripts/run_demo_workflow.py", "docs/WORKFLOW_HOST_GUIDE.md",
                  "tests/test_crosscheck_demo_workflow.py"}
    allowed_r4 = {"scripts/run_demo_workflow.py", "docs/WORKFLOW_HOST_GUIDE.md"}
    comparisons = {}
    for label, baseline_path, allowed in (("r1_gpt", REPORT_BASELINE, allowed_r1),
                                          ("r4_main", MAIN_BASELINE, allowed_r4)):
        if not baseline_path.is_file():
            g7_problems.append(f"基线缺失：{baseline_path}")
            continue
        baseline_raw = json.loads(baseline_path.read_text(encoding="utf-8"))
        # 基线键为 Windows 反斜杠形式，扫描键为正斜杠形式：统一归一后比较（否则会假报全量缺失）
        baseline = {name.replace("\\", "/"): digest for name, digest in baseline_raw.items()}
        changed = sorted(name for name, digest in baseline.items()
                         if name in current_scan and current_scan[name] != digest)
        missing = sorted(name for name in baseline if name not in current_scan)
        unexpected = sorted(name for name in changed if name not in allowed)
        comparisons[label] = {"baseline_path": str(baseline_path),
                              "baseline_sha256": sha256(baseline_path),
                              "baseline_entries": len(baseline),
                              "scanned_entries": len(current_scan), "changed": changed,
                              "missing": missing, "unexpected_changes": unexpected,
                              "allowed": sorted(allowed),
                              "ok": not missing and not unexpected}
        if missing:
            g7_problems.append(f"{label} 缺失 {len(missing)}：{missing[:5]}")
        if unexpected:
            g7_problems.append(f"{label} 预期外变化：{unexpected[:5]}")
    for rel_path in PROTECTED_FILES:
        if not (PROJECT_ROOT / rel_path).is_file():
            g7_problems.append(f"受保护文件缺失：{rel_path}")
    if sha256(PROJECT_ROOT / "scripts/crosscheck_demo_rules.py") != FROZEN_CORE:
        g7_problems.append("冻结复核核心被修改")
    if sha256(PROJECT_ROOT / "tests/test_screen_demo_workflow.py") != FROZEN_SCREEN_TEST:
        g7_problems.append("TASK-013 测试被修改")
    save_json(container / "probe_records" / "g7_protected_comparison.json", {
        "case": "g7_protected_comparison", "scan_path": rel(scan_path),
        "comparisons": comparisons, "frozen_core_sha256": FROZEN_CORE,
        "frozen_screen_test_sha256": FROZEN_SCREEN_TEST})
    record("G7_PROTECTED_COMPARISON", "host", g7_problems,
           comparisons={key: value["ok"] for key, value in comparisons.items()})

    # ================================================================ 记录审计与隔离自测
    print("== 记录审计（missing/unregistered 进入正式 failures）与隔离自测")
    audit_problems: list = []
    registered_cli = {item["label"] for item in cli_records}
    ledger_entries = []
    for item in cli_records:
        for key in ("stdout_path", "stderr_path", "return_object_path"):
            target_file = container / item[key]
            digest_key = {"stdout_path": "stdout_sha256", "stderr_path": "stderr_sha256",
                          "return_object_path": "return_object_sha256"}[key]
            ledger_entries.append({"record": f"cli:{item['label']}", "field": key,
                                   "path": item[key], "exists": target_file.is_file(),
                                   "expected_sha256": item.get(digest_key),
                                   "actual_sha256": sha256(target_file)
                                   if target_file.is_file() else None})
    for item in api_records:
        for key in ("return_path", "exception_path"):
            if not item.get(key):
                continue
            target_file = container / item[key]
            digest_key = "return_sha256" if key == "return_path" else "exception_sha256"
            ledger_entries.append({"record": f"api:{item['label']}", "field": key,
                                   "path": item[key], "exists": target_file.is_file(),
                                   "expected_sha256": item.get(digest_key),
                                   "actual_sha256": sha256(target_file)
                                   if target_file.is_file() else None})

    def audit_ledger(payload) -> list:
        problems = []
        for item in payload["file_ledger"]:
            target_file = container / item["path"]
            if not target_file.is_file():
                problems.append(f"记录文件缺失：{item['path']}")
            elif item.get("expected_sha256") is not None \
                    and sha256(target_file) != item["expected_sha256"]:
                problems.append(f"记录哈希不符：{item['path']}")
        return problems

    registry_path = save_json(container / "call_registry.json",
                              {"calls": call_registry, "cli": len(cli_records),
                               "api": len(api_records)})
    ledger = {"cli_records": cli_records, "api_records": api_records,
              "file_ledger": ledger_entries, "counts": counts,
              "call_registry_path": rel(registry_path),
              "registered_calls": [item["record"] for item in call_registry]}
    ledger_path = save_json(container / "evidence_ledger.json", ledger)
    ledger_problems = audit_ledger(ledger)
    if ledger_problems:
        audit_problems.extend(ledger_problems[:5])

    def audit_registration(payload) -> list:
        """正式门槛：每个真实调用都必须在登记表内，且登记表内不得有未对应记录的条目。"""
        problems = []
        ledger_names = {item["record"] for item in payload["file_ledger"]}
        cli_names = {f"cli:{item['label']}" for item in payload["cli_records"]}
        api_names = {f"api:{item['label']}" for item in payload["api_records"]}
        record_names = cli_names | api_names
        registry_names = {item["record"] for item in payload.get("registry_calls", [])}
        for name in sorted(record_names - ledger_names):
            problems.append(f"调用记录未登记进文件台账：{name}")
        if payload.get("expect_registry"):
            for name in sorted(record_names - registry_names):
                problems.append(f"调用未登记进权威登记表：{name}")
            for name in sorted(registry_names - record_names):
                problems.append(f"登记表存在无对应记录的条目：{name}")
        return problems

    ledger["registry_calls"] = call_registry
    ledger["expect_registry"] = True
    save_json(ledger_path, ledger)

    # 总体计数：从现场清单导出（不得只按子集手工递增）
    scenes = []
    for batch_dir in sorted((item for item in batch_parent.iterdir() if item.is_dir()),
                            key=lambda item: item.name):
        scenes.append({"batch": batch_dir.name, **collect_batch_outcome(batch_dir)})
    matched_reports = [item for item in scenes if item["crosscheck_matched"] is True]
    success_vouchers = [item for item in scenes
                        if item["voucher_0006_present"] and item["voucher_0006_parseable"]
                        and not item["failure_present"]]
    failure_scenes = [item for item in scenes if item["failure_present"]]
    mismatch_scenes = [item for item in scenes
                       if item["crosscheck_batch_status"] == "DEV_CROSSCHECK_MISMATCH"]
    counts["matched_crosscheck_reports_total"] = len(matched_reports)
    counts["crosscheck_success_vouchers_total"] = len(success_vouchers)
    counts["crosscheck_failure_scenes_total"] = len(failure_scenes)
    counts["mismatch_crosscheck_reports_total"] = len(mismatch_scenes)
    counts["matched_reports_scope"] = "总体（现场全部批次导出）"
    counts["success_vouchers_scope"] = "总体（含可解析 0006 且无 failure 的批次）"
    counts["matched_reports_in_flow_checks"] = counts["matched_crosscheck_reports"]
    counts["success_vouchers_in_flow_checks"] = counts["crosscheck_success_vouchers_0006"]
    counts["flow_check_scope"] = "子集（G1 与 G2 三个小样共 4 个批次）"
    save_json(container / "scene_outcomes.json", {"scenes": scenes,
                                                  "derived_counts": {
                                                      key: counts[key] for key in (
                                                          "matched_crosscheck_reports_total",
                                                          "crosscheck_success_vouchers_total",
                                                          "crosscheck_failure_scenes_total",
                                                          "mismatch_crosscheck_reports_total")}})

    registration_problems = audit_registration(ledger)
    counts["missing_records"] = len(ledger_problems) + len(registration_problems)
    if registration_problems:
        audit_problems.extend(registration_problems[:5])

    stdout_files = sorted(item.name for item in (container / "cli_logs").glob("*.stdout.txt"))
    stderr_files = sorted(item.name for item in (container / "cli_logs").glob("*.stderr.txt"))
    if len(stdout_files) != len(cli_records) or len(stderr_files) != len(cli_records):
        audit_problems.append(f"CLI 原文与记录数量不符：stdout={len(stdout_files)} "
                              f"stderr={len(stderr_files)} records={len(cli_records)}")
    unregistered_files = [name for name in stdout_files
                          if name[: -len(".stdout.txt")] not in registered_cli]
    counts["unregistered_records"] = len(unregistered_files)
    if unregistered_files:
        audit_problems.append(f"存在未登记 CLI 原文：{unregistered_files[:3]}")

    # 隔离自测：只从审核副本去掉一条登记记录，审计必须失败（不改真实日志与历史容器）
    isolation_problems: list = []
    copy_path = container / "isolation" / "evidence_ledger_minus_one.json"
    trimmed = copy.deepcopy(ledger)
    removed = trimmed["file_ledger"].pop(0)
    removed_registry = trimmed["registry_calls"].pop(0)
    save_json(copy_path, trimmed)
    isolation_failures = audit_ledger(trimmed) + audit_registration(trimmed)
    if not isolation_failures:
        isolation_problems.append(
            f"隔离自测未失败（去掉的登记：{removed['record']}／{removed['field']}、"
            f"登记表条目 {removed_registry['record']}）")
    save_json(container / "isolation" / "isolation_result.json", {
        "removed_ledger_entry": removed, "removed_registry_entry": removed_registry,
        "audit_problems_on_trimmed": isolation_failures,
        "audit_problems_on_original": ledger_problems + registration_problems,
        "note": "只操作审核副本 evidence_ledger_minus_one.json；真实 CLI 原文、登记表与历史容器未改动。"})
    record("EVIDENCE_LEDGER_AUDIT_AND_ISOLATION", "evidence",
           audit_problems + isolation_problems, cli_records=len(cli_records),
           api_records=len(api_records), ledger_path=rel(ledger_path))

    # ================================================================ 汇总
    summary = {
        "call_registry_path": rel(registry_path),
        "host_version": host.HOST_VERSION, "checkpoint_version": host.CHECKPOINT_VERSION,
        "crosscheck_versions": {"start": host.CROSSCHECK_START_VERSION,
                                "artifacts": host.CROSSCHECK_ARTIFACTS_VERSION,
                                "failure": host.CROSSCHECK_FAILURE_VERSION},
        "container": str(container), "batch_parent": str(batch_parent),
        "sqlite_parent": str(sqlite_parent), "checks": checks, "failures": failures,
        "counts": counts,
        "artifacts": {"host_sha256": sha256(HOST_PATH),
                      "guide_sha256": sha256(PROJECT_ROOT / "docs/WORKFLOW_HOST_GUIDE.md"),
                      "test_sha256": sha256(Path(__file__)),
                      "crosscheck_core_sha256": FROZEN_CORE,
                      "screen_test_sha256": FROZEN_SCREEN_TEST},
        "records": {"cli": len(cli_records), "api": len(api_records)},
        "total_counts_from_scenes": {key: counts[key] for key in (
            "matched_crosscheck_reports_total", "crosscheck_success_vouchers_total",
            "crosscheck_failure_scenes_total", "mismatch_crosscheck_reports_total",
            "receiver_starts_recorded", "checker_invocations_started_by_receiver",
            "checker_invocations_exit_zero")},
        "subset_counts_in_flow_checks": {
            "matched_crosscheck_reports": counts["matched_reports_in_flow_checks"],
            "success_vouchers_0006": counts["success_vouchers_in_flow_checks"],
            "scope": counts["flow_check_scope"]},
        "scene_outcomes_path": rel(container / "scene_outcomes.json"),
    }
    save_json(container / "checks.json", checks)
    save_json(container / "counts.json", counts)
    save_json(container / "cli_logs.json", cli_records)
    save_json(container / "api_records.json", api_records)
    save_json(container / "summary.json", summary)

    print(f"检查项 {len(checks)}：{sum(1 for c in checks if c['result'] == 'PASS')} PASS / "
          f"{sum(1 for c in checks if c['result'] == 'FAIL')} FAIL")
    print(f"CLI 记录 {len(cli_records)} 条 / API 记录 {len(api_records)} 条；"
          f"missing={counts['missing_records']} unregistered={counts['unregistered_records']}")
    print(f"进程内观测复算核心 "
          f"{counts['core_observations']['verify_rule_facts_inprocess_observed']} 次、筛查核心 "
          f"{counts['core_observations']['screen_sqlite_inprocess_observed']} 次；"
          f"CLI 内部核心次数={counts['core_observations']['cli_internal_core_calls']}（不可观测，记 null）")
    print("【总体·从现场导出】批次 "
          f"{len(scenes)}；MATCHED 报告 {counts['matched_crosscheck_reports_total']}；"
          f"MISMATCH 报告 {counts['mismatch_crosscheck_reports_total']}；"
          f"成功凭证（可解析 0006 且无 failure）{counts['crosscheck_success_vouchers_total']}；"
          f"失败现场 {counts['crosscheck_failure_scenes_total']}")
    print(f"【子集·本轮流程检查批次】MATCHED {counts['matched_reports_in_flow_checks']}；"
          f"成功凭证 {counts['success_vouchers_in_flow_checks']}（范围：G1 与 G2 三小样）")
    print("【子进程实际执行·从批次留痕导出】receiver 启动 "
          f"{counts['receiver_starts_recorded']}；checker 由 receiver 启动 "
          f"{counts['checker_invocations_started_by_receiver']}（exit_code=0 "
          f"{counts['checker_invocations_exit_zero']}）；直接 checker CLI 调用 0")
    print(f"模拟决定 {counts['simulated_decisions']}；真实批准 {counts['real_approvals']}")
    print(f"测试失败 {len(failures)}；汇总 {container / 'summary.json'}")
    if failures or counts["missing_records"] or counts["unregistered_records"]:
        print("存在断言失败、保护失败或记录审计失败，返回非零退出码（不输出成功结论）。")
        return 1
    print("全部预期成立。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
