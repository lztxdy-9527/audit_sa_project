#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-011 开发验证入口：接收 → Gate1 待确认 → 标准化／装载 → Gate2 待确认。

真实执行冻结上游（receiver／checker／normalizer／store／controller），按卡 §7 逐项留痕。
用法：
    .venv\\Scripts\\python.exe -B tests\\test_prepare_demo_gate2.py --out-dir data\\workflow_host_tests\\<新容器>
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOST = PROJECT_ROOT / "scripts" / "run_demo_workflow.py"
CONTROLLER = PROJECT_ROOT / "scripts" / "control_demo_workflow.py"
NORMALIZER = PROJECT_ROOT / "scripts" / "normalize_demo_data.py"
STORE = PROJECT_ROOT / "scripts" / "store_demo_sqlite.py"
RECEIVER = PROJECT_ROOT / "scripts" / "receive_demo_batch.py"
CHECKER = PROJECT_ROOT / "scripts" / "check_demo_data.py"
SCREEN = PROJECT_ROOT / "scripts" / "screen_demo_sqlite.py"
CROSSCHECK = PROJECT_ROOT / "scripts" / "crosscheck_demo_rules.py"
FACT_PACKET = PROJECT_ROOT / "scripts" / "build_demo_fact_packet.py"
GENERATOR = PROJECT_ROOT / "scripts" / "generate_demo_data.py"
GROUND_TRUTH = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a" / "evaluation" / "ground_truth.json"
MAIN_WORKBOOK = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a" / "input" / "erp_export.xlsx"
FIXTURES = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a" / "fixtures"
BATCHES_ROOT = PROJECT_ROOT / "data" / "batches"
HOST_TESTS_ROOT = PROJECT_ROOT / "data" / "workflow_host_tests"
SQLITE_ROOT = PROJECT_ROOT / "data" / "sqlite_tests"
TASK011_CONTAINER_NAME = "task011_01"

MAIN_EXPECTED = {"row_counts": {"suppliers": 20, "payables": 993, "payments": 1000, "allocations": 1005},
                 "settled_pay_master_total": 267949329, "settled_refund_master_total": 700000,
                 "master_net": 267249329, "known_payable_link_net": 266249329,
                 "missing_payable_link_net": 1000000}
NET_CHECK_KEYS = ("master_net_equals_known_plus_missing", "master_net_equals_normalized",
                  "known_net_equals_normalized", "missing_net_equals_normalized",
                  "empty_ap_id_equals_normalized", "unknown_ap_id_equals_normalized")
PROTECTED = [NORMALIZER, STORE, CONTROLLER, RECEIVER, CHECKER, SCREEN, CROSSCHECK, FACT_PACKET,
             PROJECT_ROOT / "sql" / "demo_schema.sql", PROJECT_ROOT / "docs" / "SPEC_V1.md",
             PROJECT_ROOT / "docs" / "AUDIT_CONTRACT_DRAFT.md",
             PROJECT_ROOT / "tests" / "test_run_demo_workflow.py",
             PROJECT_ROOT / "docs" / "WORKFLOW_HOST_GUIDE.md"]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TASK-011 验证入口")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    container = Path(args.out_dir)
    if not container.is_absolute():
        container = (Path.cwd() / container).resolve()
    try:
        container.relative_to(HOST_TESTS_ROOT)
    except ValueError:
        print(f"out-dir 必须位于 {HOST_TESTS_ROOT} 之内：{container}", file=sys.stderr)
        return 2
    if container == HOST_TESTS_ROOT or container.exists():
        print(f"out-dir 必须是尚不存在的新容器：{container}", file=sys.stderr)
        return 2

    host = load_module(HOST, "task011_host")
    controller = load_module(CONTROLLER, "task011_controller")
    container.mkdir(parents=True)
    batch_parent = BATCHES_ROOT / container.name
    batch_parent.mkdir(parents=True)

    original_stdout, original_stderr = sys.stdout, sys.stderr
    stdout_tee = (container / "stdout.txt").open("w", encoding="utf-8", newline="\n")
    stderr_tee = (container / "stderr.txt").open("w", encoding="utf-8", newline="\n")
    sys.stdout, sys.stderr = stdout_tee, stderr_tee

    protected_before = {str(p.relative_to(PROJECT_ROOT)): sha256(p) for p in PROTECTED if p.exists()}
    checks: list = []
    failures: list = []
    cli_logs: list = []
    case_logs: list = []
    helper_self_test: dict = {}
    counts = {"start_cli": 0, "status_cli": 0, "record_cli": 0, "prepare_cli": 0,
              "host_api_calls": 0, "private_probe_calls": 0, "controller_calls": 0,
              "receiver_starts_host": 0, "receiver_starts_direct": 0, "receiver_starts": 0,
              "checker_runs": 0, "normalize_calls_inproc": 0, "load_calls_inproc": 0,
              "normalize_calls_cli_unobserved": None, "load_calls_cli_unobserved": None,
              "normalize_calls_cli_derived": 0, "load_calls_cli_derived": 0,
              "copies": 0, "fault_injections": 0, "simulated_decisions": 0, "real_approvals": 0,
              "rejections_observed": 0}
    copy_records: list = []
    expected_starts: list = []
    start_records: list = []

    def register_start(batch_dir: Path, entry: str, result: dict) -> None:
        """登记一次真实接收启动（宿主 CLI／宿主 API／测试直接调用接收器）。"""
        relative = str(Path(batch_dir).relative_to(PROJECT_ROOT))
        record = {"batch": relative, "entry": entry, "command": result.get("command"),
                  "exit_code": result.get("exit_code"),
                  "recorded_by": result.get("recorded_by", entry)}
        start_records.append(record)
        if relative not in expected_starts:
            expected_starts.append(relative)
        if entry == "direct_receiver":
            counts["receiver_starts_direct"] += 1
            counts["private_probe_calls"] += 1
        else:
            counts["receiver_starts_host"] += 1

    def record(case: str, kind: str, problems: list, **extra) -> None:
        detail = {"case": case, "kind": kind, "result": "PASS" if not problems else "FAIL",
                  "problems": list(problems)}
        detail.update(extra)
        checks.append(detail)
        if problems:
            failures.append(detail)
        print(f"[{'PASS' if not problems else 'FAIL'}] {case}"
              + (f"  | {'; '.join(str(p) for p in problems[:4])}" if problems else ""))
        for problem in problems:
            print(f"    - {problem}", file=sys.stderr)

    def run_cli(label: str, sub_args: list, expect_exit: int) -> dict:
        target_arg = None
        if "--batch-dir" in sub_args:
            target_arg = Path(sub_args[sub_args.index("--batch-dir") + 1])
        existed_before = bool(target_arg and target_arg.exists())
        command = [sys.executable, "-B", str(HOST), *sub_args]
        completed = subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        index = len(cli_logs) + 1
        (container / "cli_logs").mkdir(exist_ok=True)
        out_path = container / "cli_logs" / f"{index:03d}_{label}.stdout.txt"
        err_path = container / "cli_logs" / f"{index:03d}_{label}.stderr.txt"
        out_path.write_text(completed.stdout, encoding="utf-8")
        err_path.write_text(completed.stderr, encoding="utf-8")
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
        entry = {"label": label, "command": command, "cwd": str(PROJECT_ROOT),
                 "exit_code": completed.returncode, "expect_exit": expect_exit,
                 "stdout_path": str(out_path.relative_to(container)),
                 "stderr_path": str(err_path.relative_to(container)),
                 "payload": payload, "stderr_tail": completed.stderr[-400:],
                 "ok": completed.returncode == expect_exit}
        cli_logs.append(entry)
        command_name = sub_args[0]
        if command_name == "start":
            counts["start_cli"] += 1
            if target_arg is not None and not existed_before and target_arg.exists():
                invocation = target_arg / "workflow" / "receive_invocation.json"
                payload_record = (json.loads(invocation.read_text("utf-8"))
                                  if invocation.is_file() else {})
                register_start(target_arg, "host_cli_start",
                               {"command": payload_record.get("command"),
                                "exit_code": payload_record.get("exit_code"),
                                "recorded_by": "receive_invocation.json"})
        elif command_name == "status":
            counts["status_cli"] += 1
        elif command_name == "record-simulated-decision":
            counts["record_cli"] += 1
        elif command_name == "prepare-gate2":
            counts["prepare_cli"] += 1
        print(f"    CLI {label}: exit={completed.returncode}（期望 {expect_exit}）")
        return entry

    def batch_path(leaf: str) -> Path:
        return batch_parent / leaf

    def write_decision(path: Path, batch_dir: Path, decision: str, event_id: str, **overrides) -> Path:
        checkpoint = json.loads((batch_dir / "workflow" / "checkpoints" / "0001.json").read_text("utf-8"))
        request = checkpoint["workflow"]["state"]["requests"]["GATE1"]
        payload = {"event_id": event_id, "batch_id": batch_dir.name, "gate": "GATE1",
                   "request_id": request["request_id"], "materials_sha256": request["materials_sha256"],
                   "decision": decision, "actor_kind": "SIMULATED_HUMAN", "actor_id": "tester-01",
                   "occurred_at": "2026-10-11T15:30:00+08:00",
                   "reason": f"TASK-011 开发测试：模拟 {decision}（非真实批准）",
                   "simulation": "SIMULATED_TEST_ONLY"}
        if decision == "APPROVE":
            payload["confirmations"] = {"scope_and_source_reviewed": True}
        payload.update(overrides)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def measured(batch_dir: Path) -> dict:
        return host._measure_bindings(batch_dir)

    def derive_db(batch_dir: Path) -> Path:
        return host._gate2_paths(batch_dir, "test")["database_path"]

    counters = {"normalize": 0, "load": 0}
    real_normalize = host.NORMALIZER_MODULE.normalize_workbook
    real_load = host.STORE_MODULE.load_normalized_to_sqlite

    def counting_normalize(*a, **kw):
        """进程内真实调用计数：先计数再调用真实上游（故障前调用也会被计入）。"""
        counters["normalize"] += 1
        counts["normalize_calls_inproc"] += 1
        return real_normalize(*a, **kw)

    def counting_load(*a, **kw):
        counters["load"] += 1
        counts["load_calls_inproc"] += 1
        return real_load(*a, **kw)

    host.NORMALIZER_MODULE.normalize_workbook = counting_normalize
    host.STORE_MODULE.load_normalized_to_sqlite = counting_load

    def retarget_copy(case: str, source: Path, *, copy_database: bool = True) -> Path:
        """复制批次到同叶子名的新父目录，并把固定数据库路径重定向到副本自己的推导路径。"""
        destination = batch_parent / case / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        counts["copies"] += 1
        copy_records.append({"copy": str(destination.relative_to(PROJECT_ROOT)),
                             "source": str(source.relative_to(PROJECT_ROOT)), "case": case,
                             "note": "副本不计真实接收；同步外层引用后用于定点故障"})
        source_db = derive_db(source)
        destination_db = derive_db(destination)
        if copy_database:
            destination_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_db, destination_db)
        paths = host._gate2_paths(destination, "test")
        artifacts_path = destination / "workflow" / "gate2" / "artifacts.json"
        artifacts = json.loads(artifacts_path.read_text("utf-8"))
        artifacts["database_path"] = str(destination_db)
        artifacts["output_relative"] = paths["relative"]
        artifacts_path.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
        report_path = destination / "workflow" / "gate2" / "load_report.json"
        report = json.loads(report_path.read_text("utf-8"))
        report["database_path"] = str(destination_db)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifacts["load_report_file_sha256"] = sha256(report_path)
        normalized = json.loads((destination / "workflow" / "gate2" / "normalized.json").read_text("utf-8"))
        bindings = measured(destination)
        materials = host._gate2_materials(destination, {"manifest": {
            "bindings_sha256": json.loads((destination / "workflow" / "host_manifest.json").read_text(
                "utf-8"))["bindings_sha256"],
            "source": json.loads((destination / "workflow" / "host_manifest.json").read_text(
                "utf-8"))["source"]}}, normalized, report)
        base = json.loads((destination / "workflow" / "checkpoints" / "0002.json").read_text("utf-8"))
        workflow = controller.prepare_dev_gate(base["workflow"], "GATE2", materials,
                                              current_bindings=bindings)
        counts["controller_calls"] += 1
        artifacts["normalized_file_sha256"] = sha256(destination / "workflow" / "gate2" / "normalized.json")
        artifacts["database_sha256"] = sha256(destination_db)
        artifacts_path.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
        artifacts_file_sha = sha256(artifacts_path)
        decision = base["workflow"]["state"]["simulated_decisions"][-1]
        body_sha = controller.canonical_sha256({k: v for k, v in decision.items() if k != "decision_sha256"})
        checkpoint = {
            "checkpoint_version": host.CHECKPOINT_VERSION, "revision": 3,
            "previous_file_sha256": sha256(destination / "workflow" / "checkpoints" / "0002.json"),
            "batch_id": destination.name,
            "host_manifest_file_sha256": sha256(destination / "workflow" / "host_manifest.json"),
            "workflow": workflow,
            "operation": {"kind": host.OPERATION_PREPARE_GATE2, "at_utc": "2026-10-11T15:31:00+00:00",
                          "artifacts": artifacts, "artifacts_file_sha256": artifacts_file_sha,
                          "materials_sha256": controller.canonical_sha256(materials),
                          "phase_after": workflow["state"]["phase"],
                          "bindings_sha256": workflow["state"]["run_bindings_sha256"],
                          "gate1_decision_sha256": body_sha,
                          "database_sha256": artifacts["database_sha256"],
                          "normalized_payload_sha256": artifacts["normalized_payload_sha256"],
                          "database_path": str(destination_db),
                          "output_relative": paths["relative"]},
        }
        (destination / "workflow" / "checkpoints" / "0003.json").write_text(
            json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        failure = destination / "workflow" / "gate2" / "failure.json"
        if failure.exists():
            failure.unlink()
        return destination

    def sync_checkpoint_state(destination: Path) -> None:
        """把 0003 内 workflow 的外层指纹与 state 同步（仅用于测试副本）。"""
        path = destination / "workflow" / "checkpoints" / "0003.json"
        payload = json.loads(path.read_text("utf-8"))
        payload["workflow"]["state_sha256"] = controller.canonical_sha256(payload["workflow"]["state"])
        payload["previous_file_sha256"] = sha256(destination / "workflow" / "checkpoints" / "0002.json")
        payload["host_manifest_file_sha256"] = sha256(destination / "workflow" / "host_manifest.json")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tamper_chain_link(destination: Path) -> None:
        """只改 0003 顶层的 chain 前序哈希（外层链引用）。"""
        path = destination / "workflow" / "checkpoints" / "0003.json"
        payload = json.loads(path.read_text("utf-8"))
        payload["previous_file_sha256"] = "0" * 64
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def rewrite_operation(destination: Path, **fields) -> None:
        path = destination / "workflow" / "checkpoints" / "0003.json"
        payload = json.loads(path.read_text("utf-8"))
        payload["operation"].update(fields)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def load_gate2(destination: Path) -> tuple:
        return (json.loads((destination / "workflow" / "gate2" / "normalized.json").read_text("utf-8")),
                json.loads((destination / "workflow" / "gate2" / "load_report.json").read_text("utf-8")))

    def expect_status_blocked(label: str, batch_dir: Path, expect_exit: int, target_reason: str,
                              probe_records: list) -> bool:
        entry = run_cli(label, ["status", "--batch-dir", str(batch_dir)], expect_exit)
        payload = entry["payload"] or {}
        actual_class = payload.get("exception_class")
        message = payload.get("message", "")
        expected_class = "WorkflowHostBlocked" if expect_exit == 1 else "WorkflowHostError"
        ok = entry["exit_code"] == expect_exit and actual_class == expected_class \
            and target_reason in message
        probe_records.append({"case": label, "exit": entry["exit_code"],
                              "expect_class": expected_class, "actual_class": actual_class,
                              "target_reason": target_reason, "message": message[:260], "ok": ok})
        if not ok:
            failures.append({"case": label, "kind": "probe", "result": "FAIL",
                             "problems": [f"exit={entry['exit_code']} class={actual_class} msg={message[:160]}"]})
        print(f"    {label}: exit={entry['exit_code']} class={actual_class} "
              f"reason={'OK' if target_reason in message else 'MISSING'}")
        return ok

    def guarded_matches(record: dict, expect_class: str, target_reason: str) -> bool:
        """判据 helper：类别与目标原因同时匹配才通过。"""
        return (record.get("actual_class") == expect_class and record.get("exit") == (
            1 if expect_class == "WorkflowHostBlocked" else 2)
            and target_reason in (record.get("message") or ""))

    # ------------------------------------------------------------------
    # G1 MAIN
    # ------------------------------------------------------------------
    g1: list = []
    probe_records: list = []
    main = batch_path("main_01")
    main_result = run_cli("g1_start_main", ["start", "--workbook", str(MAIN_WORKBOOK),
                                            "--batch-dir", str(main),
                                            "--source-description", "合成 ERP 导出（主样本，开发测试）"], 0)
    if main_result["exit_code"] != 0 or main_result["payload"].get("phase") != "DEV_GATE1_PENDING":
        g1.append("MAIN start 未停在 DEV_GATE1_PENDING")
    pass  # checker 计数改为按清单 started 派生
    pending_status = run_cli("g1_status_pending", ["status", "--batch-dir", str(main)], 0)
    if pending_status["payload"].get("phase") != "DEV_GATE1_PENDING":
        g1.append("MAIN status 未读到 DEV_GATE1_PENDING")
    if pending_status["payload"].get("simulated_action_allowed") is not False:
        g1.append("pending 阶段 NORMALIZE_AND_LOAD 不应允许")

    downstream_before = (counters["normalize"], counters["load"])
    decision_path = write_decision(container / "decision_approve.json", main, "APPROVE", "EVT-MAIN-1")
    approve = run_cli("g1_record_approve", ["record-simulated-decision", "--batch-dir", str(main),
                                            "--decision-file", str(decision_path)], 0)
    if approve["payload"].get("phase") != "DEV_GATE1_APPROVED":
        g1.append("模拟 APPROVE 未进入 DEV_GATE1_APPROVED")
    if (counters["normalize"], counters["load"]) != downstream_before:
        g1.append("保存 Gate1 决定时不应触发标准化／装载")
    if approve["payload"].get("real_approvals") != 0:
        g1.append("真实批准必须仍为 0")

    c1_before = sha256(main / "workflow" / "checkpoints" / "0001.json")
    c2_before = sha256(main / "workflow" / "checkpoints" / "0002.json")
    prepare = run_cli("g1_prepare_gate2", ["prepare-gate2", "--batch-dir", str(main)], 0)
    if prepare["exit_code"] != 0 or prepare["payload"].get("phase") != "DEV_GATE2_PENDING":
        g1.append(f"prepare-gate2 未形成 Gate2 pending：{prepare['exit_code']} "
                  f"{prepare['payload'].get('message', '')[:160] if prepare['payload'] else ''}")
    main_gate2_files = ["normalized.json", "load_report.json", "artifacts.json"]
    missing_products = [name for name in main_gate2_files
                        if not (main / "workflow" / "gate2" / name).is_file()]
    if missing_products or not derive_db(main).is_file():
        g1.append(f"MAIN 缺少本次真实产物：{missing_products}")
    if (prepare["payload"] or {}).get("artifacts", {}).get("database_sha256") != sha256(derive_db(main)):
        g1.append("MAIN prepare 返回的数据库哈希与实际不符")
    if (prepare["payload"] or {}).get("gate1_decision", {}).get("decision") != "APPROVE":
        g1.append("MAIN prepare 未绑定 Gate1 模拟 APPROVE 指纹")
    probe_records.append({"case": "G1_main_products", "missing_products": missing_products,
                          "database_exists": derive_db(main).is_file(), "ok": not missing_products})
    if sha256(main / "workflow" / "checkpoints" / "0001.json") != c1_before or \
            sha256(main / "workflow" / "checkpoints" / "0002.json") != c2_before:
        g1.append("prepare-gate2 后旧 0001／0002 字节发生变化")

    gate2_status = run_cli("g1_status_gate2", ["status", "--batch-dir", str(main)], 0)
    if gate2_status["payload"].get("phase") != "DEV_GATE2_PENDING":
        g1.append("重启后 status 未恢复 DEV_GATE2_PENDING")
    if gate2_status["payload"].get("action_checked") != "SCREEN_AND_BUILD_FACTS":
        g1.append("Gate2 pending 的 action_checked 应为 SCREEN_AND_BUILD_FACTS")
    if gate2_status["payload"].get("simulated_action_allowed") is not False:
        g1.append("Gate2 未批准时筛查不应允许")
    allowed = gate2_status["payload"].get("actions_simulated_allowed") or {}
    if allowed.get("NORMALIZE_AND_LOAD") is not False:
        g1.append("已完成标准化装载后 NORMALIZE_AND_LOAD 不应再允许")
    if gate2_status["payload"].get("next_step_allowed") is not False:
        g1.append("next_step_allowed 必须严格 false")

    normalized, report = load_gate2(main)
    artifacts = json.loads((main / "workflow" / "gate2" / "artifacts.json").read_text("utf-8"))
    database = derive_db(main)
    pass  # checker 计数改为按清单 started 派生
    money_checks = []
    for table, expected in MAIN_EXPECTED["row_counts"].items():
        actual = report["row_counts"].get(table)
        money_checks.append({"field": f"row_counts.{table}", "expected": expected, "actual": actual,
                             "ok": actual == expected})
    for field in ("settled_pay_master_total", "settled_refund_master_total", "master_net",
                  "known_payable_link_net", "missing_payable_link_net"):
        actual = report.get(field)
        money_checks.append({"field": field, "expected": MAIN_EXPECTED[field], "actual": actual,
                             "ok": actual == MAIN_EXPECTED[field]})
    money_checks.append({"field": "master_net=known+missing",
                         "expected": report["known_payable_link_net"] + report["missing_payable_link_net"],
                         "actual": report["master_net"],
                         "ok": report["master_net"] == report["known_payable_link_net"]
                         + report["missing_payable_link_net"]})
    money_checks.append({"field": "settled_pay master=allocation",
                         "expected": report["settled_pay_allocation_total"],
                         "actual": report["settled_pay_master_total"],
                         "ok": report["settled_pay_master_total"] == report["settled_pay_allocation_total"]})
    money_checks.append({"field": "settled_refund master=allocation",
                         "expected": report["settled_refund_allocation_total"],
                         "actual": report["settled_refund_master_total"],
                         "ok": report["settled_refund_master_total"]
                         == report["settled_refund_allocation_total"]})
    failed_money = [item for item in money_checks if not item["ok"]]
    if failed_money:
        g1.append(f"MAIN 数量金额核对失败：{failed_money[:3]}")
    if not all(report["net_checks"].get(key) is True for key in NET_CHECK_KEYS):
        g1.append("MAIN net_checks 六项未全部为 true")
    if report.get("batch_status") != "DEV_SQLITE_VERIFIED" or report.get("round_trip_exact") is not True:
        g1.append("MAIN 装载报告状态／往返标志不符")
    if report.get("database_sha256") != sha256(database) or report.get("database_path") != str(database):
        g1.append("MAIN 数据库字节哈希或路径与实际不符")
    if artifacts["database_sha256"] != sha256(database):
        g1.append("artifacts 数据库哈希与实际不符")
    if artifacts["normalized_payload_sha256"] != controller.canonical_sha256(normalized):
        g1.append("artifacts normalized 指纹与实际对象不符")
    if report["normalized_payload_sha256"] != controller.canonical_sha256(normalized):
        g1.append("load_report normalized 指纹与实际对象不符")
    source_hash = json.loads((main / "workflow" / "host_manifest.json").read_text("utf-8"))[
        "bindings"]["input_sha256"]
    if normalized["source"]["input_sha256"] != source_hash:
        g1.append("normalized 来源哈希与批次绑定不符")
    checkpoint3 = json.loads((main / "workflow" / "checkpoints" / "0003.json").read_text("utf-8"))
    if checkpoint3["operation"]["kind"] != "PREPARE_GATE2":
        g1.append("0003 操作种类不是 PREPARE_GATE2")
    decision2 = json.loads((main / "workflow" / "checkpoints" / "0002.json").read_text("utf-8"))[
        "workflow"]["state"]["simulated_decisions"][-1]
    body_sha = controller.canonical_sha256({k: v for k, v in decision2.items() if k != "decision_sha256"})
    if checkpoint3["operation"]["gate1_decision_sha256"] != body_sha:
        g1.append("0003 未绑定本 workflow 的 Gate1 APPROVE 正文指纹")
    if checkpoint3["workflow"]["state"]["history"][:len(
            checkpoint3["workflow"]["state"]["history"])] == []:
        g1.append("0003 历史为空")
    record("G1_MAIN_FULL_FLOW", "flow", g1, money_checks=money_checks,
           artifacts=artifacts, note="MAIN 真实标准化与装载各一次，停在 Gate2 待确认")

    # ------------------------------------------------------------------
    # G2 小样 C02 与 C07b
    # ------------------------------------------------------------------
    g2: list = []
    for fixture, leaf, expected_missing in (("C02", "c02_small", None), ("C07b", "c07b_missing", "nonzero")):
        target = batch_path(leaf)
        started = run_cli(f"g2_start_{leaf}", ["start", "--workbook", str(FIXTURES / f"{fixture}.xlsx"),
                                               "--batch-dir", str(target),
                                               "--source-description", f"{fixture} 小样（开发测试）"], 0)
        if started["exit_code"] != 0:
            g2.append(f"{fixture} start 失败")
            continue
        pass  # checker 计数改为按清单 started 派生
        decision_file = write_decision(container / f"decision_{leaf}.json", target, "APPROVE",
                                       f"EVT-{fixture}-1")
        approved = run_cli(f"g2_record_{leaf}", ["record-simulated-decision", "--batch-dir", str(target),
                                                 "--decision-file", str(decision_file)], 0)
        if approved["payload"].get("phase") != "DEV_GATE1_APPROVED":
            g2.append(f"{fixture} 模拟 APPROVE 失败")
        prepared = run_cli(f"g2_prepare_{leaf}", ["prepare-gate2", "--batch-dir", str(target)], 0)
        if prepared["exit_code"] != 0 or prepared["payload"].get("phase") != "DEV_GATE2_PENDING":
            g2.append(f"{fixture} 未形成 Gate2 pending："
                      f"{prepared['payload'].get('message', '')[:140] if prepared['payload'] else ''}")
            continue
        normalized, report = load_gate2(target)
        if report["normalized_payload_sha256"] != controller.canonical_sha256(normalized):
            g2.append(f"{fixture} normalized 指纹不符")
        if report.get("round_trip_exact") is not True:
            g2.append(f"{fixture} 往返不一致")
        if report.get("database_sha256") != sha256(derive_db(target)):
            g2.append(f"{fixture} 数据库字节哈希不符")
        for table in MAIN_EXPECTED["row_counts"]:
            if report["row_counts"].get(table) != len(normalized["tables"][table]["records"]):
                g2.append(f"{fixture} {table} 行数与标准化记录数不符")
        if not all(isinstance(report["row_counts"].get(table), int)
                   and not isinstance(report["row_counts"].get(table), bool)
                   for table in MAIN_EXPECTED["row_counts"]):
            g2.append(f"{fixture} 行数必须是整数非 bool")
        if expected_missing == "nonzero" and not report["missing_payable_link_net"] > 0:
            g2.append("C07b 缺失应付关联净额应非零并仍可提交 Gate2")
        if expected_missing == "nonzero" and report["master_net"] != (
                report["known_payable_link_net"] + report["missing_payable_link_net"]):
            g2.append("C07b 净额勾稽不成立")
        case_logs.append({"case": f"G2_{fixture}", "row_counts": report["row_counts"],
                          "master_net": report["master_net"],
                          "known": report["known_payable_link_net"],
                          "missing": report["missing_payable_link_net"]})
    record("G2_SMALL_SAMPLES", "flow", g2)

    # ------------------------------------------------------------------
    # G3 前提拒绝与接收层有限回归
    # ------------------------------------------------------------------
    g3: list = []
    for decision, leaf in (("HOLD", "hold_case"), ("REJECT", "reject_case")):
        target = batch_path(leaf)
        run_cli(f"g3_start_{leaf}", ["start", "--workbook", str(MAIN_WORKBOOK),
                                     "--batch-dir", str(target),
                                     "--source-description", f"{decision} 用例（开发测试）"], 0)
        pass  # checker 计数改为按清单 started 派生
        decision_file = write_decision(container / f"decision_{leaf}.json", target, decision,
                                       f"EVT-{decision}-1")
        run_cli(f"g3_record_{leaf}", ["record-simulated-decision", "--batch-dir", str(target),
                                      "--decision-file", str(decision_file)], 0)
        before = (counters["normalize"], counters["load"])
        counts["host_api_calls"] += 1
        outcome = "ok"
        try:
            host.prepare_dev_gate2(target)
        except host.WorkflowHostBlocked:
            outcome = "blocked"
        except host.WorkflowHostError as exc:
            outcome = f"error: {exc}"
        if outcome != "blocked":
            g3.append(f"{decision} 的 prepare-gate2 应被阻断，实际 {outcome}")
        if (counters["normalize"], counters["load"]) != before:
            g3.append(f"{decision} 被拒绝时不应调用标准化／装载")
        probe_records.append({"case": f"G3_prepare_{decision}", "outcome": outcome,
                              "normalize_calls": counters["normalize"] - before[0],
                              "load_calls": counters["load"] - before[1], "ok": outcome == "blocked"})

    pending_target = batch_path("pending_case")
    run_cli("g3_start_pending", ["start", "--workbook", str(MAIN_WORKBOOK),
                                 "--batch-dir", str(pending_target),
                                 "--source-description", "pending 用例（开发测试）"], 0)
    pass  # checker 计数改为按清单 started 派生
    before = (counters["normalize"], counters["load"])
    counts["host_api_calls"] += 1
    try:
        host.prepare_dev_gate2(pending_target)
        pending_outcome = "ok"
    except host.WorkflowHostBlocked:
        pending_outcome = "blocked"
    if pending_outcome != "blocked":
        g3.append("Gate1 pending 的 prepare-gate2 应被阻断")
    if (counters["normalize"], counters["load"]) != before:
        g3.append("pending 被拒绝时不应调用标准化／装载")
    probe_records.append({"case": "G3_prepare_pending", "outcome": pending_outcome,
                          "normalize_calls": counters["normalize"] - before[0],
                          "load_calls": counters["load"] - before[1], "ok": pending_outcome == "blocked"})

    c12 = batch_path("c12_blocked")
    c12_result = run_cli("g3_start_c12", ["start", "--workbook", str(FIXTURES / "C12.xlsx"),
                                          "--batch-dir", str(c12),
                                          "--source-description", "质量坏例 C12（开发测试）"], 1)
    if c12_result["exit_code"] != 1 or (c12_result["payload"] or {}).get("result") != "blocked":
        g3.append("C12 应被真实阻断并返回 1")
    if (counters["normalize"], counters["load"]) != before:
        g3.append("C12 阻断时不应出现下游调用")
    c12_status = run_cli("g3_status_c12", ["status", "--batch-dir", str(c12)], 1)
    if "BLOCKED_QUALITY" not in (c12_status["payload"] or {}).get("message", ""):
        g3.append("C12 的 status 未恢复质量阻断")

    runtime_bad = container / "not_a_zip.xlsx"
    runtime_bad.write_text("这不是一个 ZIP 工作簿", encoding="utf-8")
    runtime_target = batch_path("runtime_failed")
    runtime_result = run_cli("g3_start_runtime", ["start", "--workbook", str(runtime_bad),
                                                  "--batch-dir", str(runtime_target),
                                                  "--source-description", "运行失败小样"], 2)
    if runtime_result["exit_code"] != 2:
        g3.append("接收运行失败应返回 2")
    runtime_manifest = json.loads((runtime_target / "workflow" / "host_manifest.json").read_text("utf-8"))
    if runtime_manifest["receive"]["exit_code"] != 2 or runtime_manifest["status"] != "FAILED_RUNTIME":
        g3.append("接收运行失败批次的真实退出码／状态未被如实保留")
    runtime_status = run_cli("g3_status_runtime", ["status", "--batch-dir", str(runtime_target)], 2)
    if runtime_status["exit_code"] != 2:
        g3.append("运行失败批次的 status 应返回 2")
    record("G3_PRECONDITIONS_AND_RECEIVE_REGRESSION", "flow", g3, probes=probe_records)

    # ------------------------------------------------------------------
    # G4 Gate2 锁定与路径冲突
    # ------------------------------------------------------------------
    g4: list = []
    lock_probes: list = []
    db_before = sha256(derive_db(main))
    c3_before = sha256(main / "workflow" / "checkpoints" / "0003.json")
    repeat_prepare = run_cli("g4_repeat_prepare", ["prepare-gate2", "--batch-dir", str(main)], 1)
    if repeat_prepare["exit_code"] != 1 or "已开始存在" not in (repeat_prepare["payload"] or {}).get("message", ""):
        g4.append("Gate2 pending 后重复 prepare 未被拒绝")
    repeat_record = run_cli("g4_repeat_record", ["record-simulated-decision", "--batch-dir", str(main),
                                                 "--decision-file", str(decision_path)], 1)
    if repeat_record["exit_code"] != 1 or "Gate2" not in (repeat_record["payload"] or {}).get("message", ""):
        g4.append("Gate2 pending 后重复提交 Gate1 决定未被拒绝")
    if (main / "workflow" / "checkpoints" / "0004.json").exists():
        g4.append("不得生成 0004")
    if sha256(derive_db(main)) != db_before or sha256(main / "workflow" / "checkpoints" / "0003.json") != c3_before:
        g4.append("被拒绝的操作改变了数据库或 0003 字节")
    if host.HOST_VERSION != "TASK-011-workflow-host-1.2":
        g4.append("宿主实现版本不是 TASK-011-workflow-host-1.2")
    if host.CHECKPOINT_VERSION != "TASK-011-checkpoint-1.1":
        g4.append("checkpoint 版本不是 TASK-011-checkpoint-1.1")
    if host.HOST_MANIFEST_VERSION != "TASK-011-host-manifest-1.1":
        g4.append("宿主清单版本不是 TASK-011-host-manifest-1.1")
    if not hasattr(host, "prepare_dev_gate2"):
        g4.append("缺少 prepare_dev_gate2 公共函数")
    gate2_decision_surface = [name for name in dir(host)
                              if "gate2" in name.lower() and "decision" in name.lower()]
    if gate2_decision_surface:
        g4.append(f"不应存在 Gate2 决定接口：{gate2_decision_surface}")

    legacy = retarget_copy("g4_legacy", main)
    manifest_path = legacy / "workflow" / "host_manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest["manifest_version"] = "TASK-010-host-manifest-1.3"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    expect_status_blocked("g4_legacy_version", legacy, 1, "旧宿主版本", lock_probes)

    plain = batch_path("plain_receive")
    # 直接调用宿主私有 _run_receiver（不产生宿主 receive_invocation.json）：
    # 记录真实命令与真实退出码，并作为“直接接收启动”登记，不计入公开宿主 API。
    real_subprocess_run = host.subprocess.run
    captured = {}

    def recording_run(command, *a, **kw):
        captured["command"] = list(command)
        completed = real_subprocess_run(command, *a, **kw)
        captured["exit_code"] = completed.returncode
        return completed

    host.subprocess.run = recording_run
    try:
        plain_result = host._run_receiver(MAIN_WORKBOOK, plain, "纯接收（无宿主清单）")
    finally:
        host.subprocess.run = real_subprocess_run
    register_start(plain, "direct_receiver",
                   {"command": captured.get("command"), "exit_code": captured.get("exit_code"),
                    "recorded_by": "测试侧包装宿主私有 _run_receiver 的真实子进程调用"})
    if captured.get("exit_code") != 0:
        lock_probes.append({"case": "g4_plain_receive_invocation", "ok": False,
                            "command": captured.get("command"), "exit_code": captured.get("exit_code")})
        g4.append("plain_receive 直接接收未成功")
    expect_status_blocked("g4_plain_receive", plain, 1, "不是本宿主创建的", lock_probes)

    conflict = batch_path("db_conflict")
    run_cli("g4_start_conflict", ["start", "--workbook", str(MAIN_WORKBOOK),
                                  "--batch-dir", str(conflict),
                                  "--source-description", "数据库路径冲突用例"], 0)
    pass  # checker 计数改为按清单 started 派生
    conflict_decision = write_decision(container / "decision_conflict.json", conflict, "APPROVE",
                                       "EVT-CONFLICT-1")
    run_cli("g4_record_conflict", ["record-simulated-decision", "--batch-dir", str(conflict),
                                   "--decision-file", str(conflict_decision)], 0)
    conflict_db = derive_db(conflict)
    conflict_db.parent.mkdir(parents=True, exist_ok=True)
    conflict_db.write_bytes(b"pre-existing")
    before = (counters["normalize"], counters["load"])
    counts["host_api_calls"] += 1
    try:
        host.prepare_dev_gate2(conflict)
        conflict_outcome = "ok"
    except host.WorkflowHostBlocked:
        conflict_outcome = "blocked"
    if conflict_outcome != "blocked":
        g4.append("数据库路径冲突应在业务调用前被拒绝")
    if (counters["normalize"], counters["load"]) != before:
        g4.append("路径冲突时不应调用标准化／装载")
    if conflict_db.read_bytes() != b"pre-existing":
        g4.append("被拒绝的路径冲突不得改动已有文件")
    probe_records.append({"case": "G4_db_path_conflict", "outcome": conflict_outcome,
                          "normalize_calls": counters["normalize"] - before[0],
                          "load_calls": counters["load"] - before[1], "ok": conflict_outcome == "blocked"})
    record("G4_GATE2_LOCK_AND_PATH_CONFLICTS", "flow", g4, probes=lock_probes)

    # ------------------------------------------------------------------
    # G5 产物篡改与内层指纹
    # ------------------------------------------------------------------
    g5: list = []
    tamper_probes: list = []
    for case, target_reason, tamper in (
        ("g5_normalized", "normalized_file_sha256",
         lambda d: (d / "workflow" / "gate2" / "normalized.json").write_bytes(
             (d / "workflow" / "gate2" / "normalized.json").read_bytes() + b" ")),
        ("g5_load_report", "load_report_file_sha256",
         lambda d: (d / "workflow" / "gate2" / "load_report.json").write_bytes(
             (d / "workflow" / "gate2" / "load_report.json").read_bytes() + b" ")),
        ("g5_database", "database_sha256",
         lambda d: derive_db(d).write_bytes(derive_db(d).read_bytes() + b"Z")),
        ("g5_prev_link", "previous_file_sha256", lambda d: tamper_chain_link(d)),
        ("g5_operation_summary", "materials_sha256",
         lambda d: rewrite_operation(d, materials_sha256="0" * 64)),
    ):
        copy_dir = retarget_copy(case, main)
        tamper(copy_dir)
        counts["fault_injections"] += 1
        expect_status_blocked(f"{case}_status", copy_dir, 1, target_reason, tamper_probes)

    inner1 = retarget_copy("g5_inner_normalized_sha", main)
    rewrite_operation(inner1, normalized_payload_sha256="0" * 64)
    counts["fault_injections"] += 1
    expect_status_blocked("g5_inner_normalized_sha_status", inner1, 1, "normalized_payload_sha256",
                          tamper_probes)
    inner2 = retarget_copy("g5_inner_gate1_sha", main)
    rewrite_operation(inner2, gate1_decision_sha256="0" * 64)
    counts["fault_injections"] += 1
    expect_status_blocked("g5_inner_gate1_sha_status", inner2, 1, "gate1_decision_sha256", tamper_probes)
    record("G5_ARTIFACT_TAMPERING", "flow", g5, probes=tamper_probes)

    # ------------------------------------------------------------------
    # G6 有限上游错误
    # ------------------------------------------------------------------
    g6: list = []
    error_probes: list = []
    normalize_sentinel = "TASK-011-SENTINEL-NORMALIZE-BLOCKED"
    load_sentinel = "TASK-011-SENTINEL-LOAD-ERROR"

    def blocked_normalize(workbook, quality_report):
        # 先发生一次真实标准化调用（必须计入进程内计数），随后按上游语义抛错
        counting_normalize(workbook, quality_report)
        raise host.NORMALIZER_MODULE.NormalizationBlocked(normalize_sentinel)

    def failing_load(normalized, database_path):
        # 先发生一次真实装载调用（必须计入进程内计数），随后按上游语义抛错
        counting_load(normalized, database_path)
        raise host.STORE_MODULE.SqliteLoadError(load_sentinel)

    for case, wrapper, expect_exit, sentinel, attribute in (
        ("g6_normalize_blocked", blocked_normalize, 1, normalize_sentinel, "normalize_workbook"),
        ("g6_load_error", failing_load, 2, load_sentinel, "load_normalized_to_sqlite"),
    ):
        target = batch_path(case)
        run_cli(f"{case}_start", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir", str(target),
                                  "--source-description", f"{case} 用例"], 0)
        pass  # checker 计数改为按清单 started 派生
        decision_file = write_decision(container / f"decision_{case}.json", target, "APPROVE",
                                       f"EVT-{case}")
        run_cli(f"{case}_record", ["record-simulated-decision", "--batch-dir", str(target),
                                   "--decision-file", str(decision_file)], 0)
        hits = {"count": 0}
        original = getattr(host.NORMALIZER_MODULE if attribute == "normalize_workbook"
                           else host.STORE_MODULE, attribute)

        def wrapper_marked(*a, _hits=hits, _wrapper=wrapper, **kw):
            _hits["count"] += 1
            return _wrapper(*a, **kw)

        if attribute == "normalize_workbook":
            host.NORMALIZER_MODULE.normalize_workbook = wrapper_marked
        else:
            host.STORE_MODULE.load_normalized_to_sqlite = wrapper_marked
        counts["fault_injections"] += 1
        counts["host_api_calls"] += 1
        outcome, message = "ok", ""
        try:
            host.prepare_dev_gate2(target)
        except host.WorkflowHostBlocked as exc:
            outcome, message = "blocked", str(exc)
        except host.WorkflowHostError as exc:
            outcome, message = "error", str(exc)
        finally:
            if attribute == "normalize_workbook":
                host.NORMALIZER_MODULE.normalize_workbook = counting_normalize
            else:
                host.STORE_MODULE.load_normalized_to_sqlite = counting_load
        expected_kind = "blocked" if expect_exit == 1 else "error"
        ok = outcome == expected_kind and sentinel in message and hits["count"] == 1
        if not ok:
            g6.append(f"{case} 未按预期映射：outcome={outcome} hits={hits['count']} msg={message[:120]}")
        failure_path = target / "workflow" / "gate2" / "failure.json"
        if not failure_path.is_file():
            g6.append(f"{case} 未保存失败诊断")
        else:
            failure = json.loads(failure_path.read_text("utf-8"))
            if sentinel not in json.dumps(failure, ensure_ascii=False):
                g6.append(f"{case} 失败诊断未保留原始原因")
        expect_status_blocked(f"{case}_status", target, expect_exit, "gate2", error_probes)
        retry = run_cli(f"{case}_repeat", ["prepare-gate2", "--batch-dir", str(target)], 1)
        if retry["exit_code"] != 1:
            g6.append(f"{case} 失败后重复 prepare 应被拒绝")
        error_probes.append({"case": case, "outcome": outcome, "hits": hits["count"],
                             "sentinel_found": sentinel in message, "ok": ok,
                             "note": "测试内依赖故障：wrapper 先调用真实上游，再抛上游异常类型"})
    record("G6_LIMITED_UPSTREAM_ERRORS", "flow", g6, probes=error_probes)

    # ------------------------------------------------------------------
    # G7 0003 真实 writer 部分写入
    # ------------------------------------------------------------------
    g7: list = []
    writer_target = batch_path("writer_case")
    run_cli("g7_start", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir", str(writer_target),
                         "--source-description", "writer 故障用例"], 0)
    pass  # checker 计数改为按清单 started 派生
    writer_decision = write_decision(container / "decision_writer.json", writer_target, "APPROVE",
                                     "EVT-WRITER-1")
    run_cli("g7_record", ["record-simulated-decision", "--batch-dir", str(writer_target),
                          "--decision-file", str(writer_decision)], 0)
    c1_before_writer = sha256(writer_target / "workflow" / "checkpoints" / "0001.json")
    c2_before_writer = sha256(writer_target / "workflow" / "checkpoints" / "0002.json")
    sentinel = "TASK-011-SENTINEL-PARTIAL-GATE2-WRITE"
    state = {"opens": 0, "writes": 0, "raises": 0, "full_text": None, "full_bytes": None,
             "full_sha256": None, "proxy": None,
             "target": writer_target / "workflow" / "checkpoints" / "0003.json"}
    real_open = open
    real_writer_fn = host._write_exclusive_json

    class PartialHandle:
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
                state["full_bytes"] = len(text.encode("utf-8"))
                state["full_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunk = text[: self._remaining]
            written = self._handle.write(chunk)
            self._remaining -= len(chunk)
            self.bytes_written += len(chunk)
            state["writes"] += 1
            if self._remaining <= 0:
                state["raises"] += 1
                raise OSError(sentinel)
            return written

        def __getattr__(self, name):
            return getattr(self._handle, name)

    import builtins
    original_builtin_open = builtins.open

    def guarded_open(file, mode="r", *a, **kw):
        handle = real_open(file, mode, *a, **kw)
        try:
            is_target = Path(file) == state["target"] and "x" in mode
        except TypeError:
            is_target = False
        if is_target:
            state["opens"] += 1
            proxy = PartialHandle(handle, 40)
            state["proxy"] = proxy
            return proxy
        return handle

    builtins.open = guarded_open
    counts["fault_injections"] += 1
    counts["host_api_calls"] += 1
    writer_outcome, writer_message, writer_exception = "ok", "", None
    try:
        host.prepare_dev_gate2(writer_target)
    except host.WorkflowHostError as exc:
        writer_outcome, writer_message, writer_exception = "error", str(exc), exc
    except host.WorkflowHostBlocked as exc:
        writer_outcome, writer_message, writer_exception = "blocked", str(exc), exc
    finally:
        builtins.open = original_builtin_open
    chain = None
    cursor = writer_exception
    for _ in range(5):
        if cursor is None:
            break
        candidate = cursor.__cause__ or cursor.__context__
        if isinstance(candidate, OSError) and str(candidate) == sentinel:
            chain = candidate
            break
        cursor = candidate
    half = state["target"]
    half_size = half.stat().st_size if half.is_file() else 0
    ok = (state["opens"] == 1 and state["writes"] == 1 and state["raises"] == 1
          and isinstance(state["full_bytes"], int) and 0 < half_size < state["full_bytes"]
          and writer_outcome == "error" and isinstance(chain, OSError) and str(chain) == sentinel
          and sha256(writer_target / "workflow" / "checkpoints" / "0001.json") == c1_before_writer
          and sha256(writer_target / "workflow" / "checkpoints" / "0002.json") == c2_before_writer
          and half.is_file())
    if not ok:
        g7.append(f"0003 writer 部分写入未按预期处理：opens={state['opens']} writes={state['writes']} "
                  f"raises={state['raises']} half={half_size} full={state['full_bytes']} "
                  f"cause={type(chain).__name__ if chain else None}")
    if isinstance(state["full_text"], str):
        (container / "writer_full_expected_0003.json").write_text(state["full_text"], encoding="utf-8",
                                                                 newline="\n")
        try:
            parsed = json.loads(state["full_text"])
            complete = set(parsed.keys()) >= {"checkpoint_version", "revision", "previous_file_sha256",
                                             "batch_id", "host_manifest_file_sha256", "workflow",
                                             "operation"}
        except json.JSONDecodeError:
            complete = False
        if not complete:
            g7.append("捕获的完整待写内容不是完整 checkpoint")
    else:
        g7.append("未捕获到 0003 的完整待写内容")
    expect_status_blocked("g7_status", writer_target, 1, "0003.json", probe_records)
    writer_evidence = {"case": "G7_0003_writer_partial_write", "opens": state["opens"],
                       "writes": state["writes"], "raises": state["raises"],
                       "partial_bytes": half_size, "captured_full_text_bytes": state["full_bytes"],
                       "captured_full_text_sha256": state["full_sha256"],
                       "exception_class": type(writer_exception).__name__ if writer_exception else None,
                       "cause_class": type(chain).__name__ if chain else None,
                       "cause_message": str(chain) if chain else None, "sentinel": sentinel,
                       "old_0001_sha256_before": c1_before_writer,
                       "old_0001_sha256_after": sha256(writer_target / "workflow" / "checkpoints" /
                                                       "0001.json"),
                       "old_0002_sha256_before": c2_before_writer,
                       "old_0002_sha256_after": sha256(writer_target / "workflow" / "checkpoints" /
                                                       "0002.json"),
                       "ok": ok}
    (container / "writer_evidence.json").write_text(
        json.dumps(writer_evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record("G7_GATE2_WRITER_PARTIAL_WRITE", "flow", g7, evidence=writer_evidence)

    # ------------------------------------------------------------------
    # G8 写后产物变化与只读／隔离守卫
    # ------------------------------------------------------------------
    g8: list = []
    change_target = batch_path("post_write_change")
    run_cli("g8_start", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir", str(change_target),
                         "--source-description", "写后产物变化用例"], 0)
    pass  # checker 计数改为按清单 started 派生
    change_decision = write_decision(container / "decision_change.json", change_target, "APPROVE",
                                     "EVT-CHANGE-1")
    run_cli("g8_record", ["record-simulated-decision", "--batch-dir", str(change_target),
                          "--decision-file", str(change_decision)], 0)
    real_writer_once = host._write_exclusive_json
    changed = {"count": 0}

    def writer_then_change(path, payload, stage, _real=real_writer_once, _state=changed,
                           _target=change_target):
        result = _real(path, payload, stage)
        if path.name == "0003.json" and _state["count"] == 0:
            report = _target / "workflow" / "gate2" / "load_report.json"
            report.write_bytes(report.read_bytes() + b" ")
            _state["count"] += 1
        return result

    host._write_exclusive_json = writer_then_change
    counts["fault_injections"] += 1
    counts["host_api_calls"] += 1
    try:
        host.prepare_dev_gate2(change_target)
        change_outcome = "ok"
    except host.WorkflowHostError as exc:
        change_outcome = f"error: {exc}"
    except host.WorkflowHostBlocked as exc:
        change_outcome = f"blocked: {exc}"
    finally:
        host._write_exclusive_json = real_writer_once
    if change_outcome == "ok" or changed["count"] != 1:
        g8.append(f"写后产物变化时不得宣告成功：outcome={change_outcome} hits={changed['count']}")
    change_status = run_cli("g8_status", ["status", "--batch-dir", str(change_target)], 1)
    if change_status["exit_code"] not in (1, 2):
        g8.append("写后变化的批次 status 应被拒绝")

    readonly = batch_path("readonly_case")
    run_cli("g8_start_readonly", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir", str(readonly),
                                  "--source-description", "只读守卫用例"], 0)
    pass  # checker 计数改为按清单 started 派生
    readonly_decision = write_decision(container / "decision_readonly.json", readonly, "APPROVE",
                                       "EVT-READONLY-1")
    run_cli("g8_record_readonly", ["record-simulated-decision", "--batch-dir", str(readonly),
                                   "--decision-file", str(readonly_decision)], 0)
    run_cli("g8_prepare_readonly", ["prepare-gate2", "--batch-dir", str(readonly)], 0)
    tree_before = {str(item.relative_to(readonly)): sha256(item)
                   for item in readonly.rglob("*") if item.is_file()}
    import socket
    spawn_calls = {"count": 0}
    real_subprocess_run = subprocess.run
    real_normalize_guard = counters["normalize"]
    real_load_guard = counters["load"]

    def forbidden_run(*a, **kw):
        spawn_calls["count"] += 1
        raise AssertionError("status 不得启动子进程")

    def forbidden_socket(*a, **kw):
        raise AssertionError("status 不得使用网络")

    subprocess.run = forbidden_run
    socket.socket = forbidden_socket
    counts["host_api_calls"] += 1
    try:
        readonly_payload = host.inspect_dev_batch(readonly)
        readonly_guard_outcome = "ok"
    except (host.WorkflowHostBlocked, host.WorkflowHostError) as exc:
        readonly_payload, readonly_guard_outcome = {}, f"{type(exc).__name__}: {exc}"
    finally:
        subprocess.run = real_subprocess_run
    readonly_status = {"exit_code": 0 if readonly_guard_outcome == "ok" else 1,
                       "payload": readonly_payload}
    if readonly_guard_outcome != "ok":
        g8.append(f"只读守卫下的进程内 status 应成功：{readonly_guard_outcome[:120]}")
    tree_after = {str(item.relative_to(readonly)): sha256(item)
                  for item in readonly.rglob("*") if item.is_file()}
    if tree_before != tree_after:
        g8.append("status 前后批次文件字节发生变化（应为只读）")
    if counters["normalize"] != real_normalize_guard or counters["load"] != real_load_guard:
        g8.append("status 期间不应调用标准化或装载")
    if spawn_calls["count"] != 0:
        g8.append("status 期间出现了子进程调用")
    if readonly_status["payload"].get("phase") != "DEV_GATE2_PENDING":
        g8.append("只读守卫下应读到 DEV_GATE2_PENDING")
    cli_readonly = run_cli("g8_status_readonly_cli", ["status", "--batch-dir", str(readonly)], 0)
    if cli_readonly["exit_code"] != 0:
        g8.append("只读批次的新进程 status 应成功")

    import ast
    host_source = HOST.read_text(encoding="utf-8")
    tree = ast.parse(host_source)
    imported = set()
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                called.add(func.attr)
            elif isinstance(func, ast.Name):
                called.add(func.id)
    forbidden_imports = [name for name in imported
                         if name in ("requests", "urllib", "socket", "openai", "http")]
    forbidden_calls = [name for name in called
                       if name in ("screen_database", "crosscheck_rules", "build_fact_packet",
                                   "generate_demo_data", "load_ground_truth", "run_screen",
                                   "run_crosscheck", "run_fact_packet")]
    forbidden_modules = [name for name in ("support", "case_support") if name in imported]
    if forbidden_imports:
        g8.append(f"宿主不得导入网络库：{forbidden_imports}")
    if forbidden_calls:
        g8.append(f"宿主不得调用筛查／复算／底稿／生成器：{forbidden_calls}")
    if forbidden_modules:
        g8.append(f"宿主不得导入生成器辅助模块：{forbidden_modules}")
    subprocess_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr in ("run", "Popen", "check_output", "call")]
    if len(subprocess_calls) != 1:
        g8.append(f"宿主只应有唯一子进程调用点，实际 {len(subprocess_calls)}")
    if "SCREEN_AND_BUILD_FACTS" not in host_source:
        g8.append("应声明筛查动作常量用于状态说明")
    print(f"    静态守卫：导入 {sorted(imported)}；子进程调用点 {len(subprocess_calls)}")
    record("G8_POST_WRITE_CHANGE_AND_GUARDS", "flow", g8,
           note="status 只读、不启子进程、不联网、不调用筛查／复算／底稿／生成器")

    # ------------------------------------------------------------------
    # G10 R1：失败诊断不被完整 0003 掩盖、收尾复测、artifacts 语义
    # ------------------------------------------------------------------
    g10: list = []
    r1_probes: list = []

    def build_gate1_approved(leaf: str) -> Path:
        """全新批次：真实 start + 显式模拟 APPROVE（未 prepare）。"""
        target = batch_path(leaf)
        run_cli(f"g10_{leaf}_start", ["start", "--workbook", str(MAIN_WORKBOOK),
                                      "--batch-dir", str(target),
                                      "--source-description", f"{leaf} R1 探针"], 0)
        decision_file = write_decision(container / f"decision_{leaf}.json", target, "APPROVE",
                                       f"EVT-{leaf}")
        run_cli(f"g10_{leaf}_record", ["record-simulated-decision", "--batch-dir", str(target),
                                       "--decision-file", str(decision_file)], 0)
        return target

    def status_inproc(batch_dir: Path) -> tuple:
        try:
            return 0, host.inspect_dev_batch(batch_dir)
        except host.WorkflowHostBlocked as exc:
            return 1, {"exception_class": "WorkflowHostBlocked", "message": str(exc)}
        except host.WorkflowHostError as exc:
            return 2, {"exception_class": "WorkflowHostError", "message": str(exc)}

    # --- F01：真实 writer 写完完整 0003 后再抛运行失败（含 sentinel OSError 原因链）---
    f01_sentinel = "SENTINEL-F01-POST-WRITE-OSERROR"
    f01 = build_gate1_approved("g10_f01")
    real_writer = host._write_exclusive_json
    f01_hits = {"count": 0}

    def writer_complete_then_fail(path, payload, stage, _real=real_writer, _hits=f01_hits):
        result = _real(path, payload, stage)
        if Path(path).name == "0003.json" and _hits["count"] == 0:
            _hits["count"] += 1
            try:
                raise OSError(f01_sentinel)
            except OSError as cause:
                raise host.WorkflowHostError(
                    f"注入：0003 写完后宿主运行失败（{f01_sentinel}）",
                    reasons=[f01_sentinel, "注入阶段=post_write_verify"],
                    stage="post_write_verify") from cause
        return result

    host._write_exclusive_json = writer_complete_then_raise = writer_complete_then_fail
    f01_outcome, f01_message = "ok", ""
    counts["host_api_calls"] += 1
    try:
        host.prepare_dev_gate2(f01)
    except host.WorkflowHostError as exc:
        f01_outcome, f01_message = "error", str(exc)
    except host.WorkflowHostBlocked as exc:
        f01_outcome, f01_message = "blocked", str(exc)
    finally:
        host._write_exclusive_json = real_writer
    counts["fault_injections"] += 1
    f01_0003 = f01 / "workflow" / "checkpoints" / "0003.json"
    f01_failure_path = f01 / "workflow" / "gate2" / "failure.json"
    f01_ok = f01_outcome == "error" and f01_hits["count"] == 1 and f01_0003.is_file() \
        and f01_failure_path.is_file()
    f01_failure = json.loads(f01_failure_path.read_text("utf-8")) if f01_failure_path.is_file() else {}
    if f01_failure:
        f01_ok = f01_ok and f01_failure.get("failure_version") == host.FAILURE_VERSION \
            and f01_failure.get("exception_class") == "WorkflowHostError" \
            and f01_failure.get("stage") == "post_write_verify" \
            and f01_sentinel in json.dumps(f01_failure.get("reasons"), ensure_ascii=False) \
            and isinstance(f01_failure.get("observed_outputs"), dict)
    if not f01_ok:
        g10.append(f"F01 未按预期保存失败诊断：outcome={f01_outcome} hits={f01_hits['count']} "
                   f"msg={f01_message[:140]}")
    f01_restore = expect_status_blocked("g10_f01_restore_status", f01, 2, f01_sentinel, r1_probes)
    if not f01_restore:
        g10.append("F01 撤销 wrapper 后 status 仍被当作成功状态")
    r1_probes.append({"case": "g10_f01_failure_record", "hits": f01_hits["count"], "outcome": f01_outcome,
                      "0003_exists": f01_0003.is_file(), "failure_exists": f01_failure_path.is_file(),
                      "failure": {k: f01_failure.get(k) for k in ("failure_version", "stage",
                                                                  "exception_class")},
                      "cause_chain": "OSError(sentinel) → WorkflowHostError",
                      "target_reason": f01_sentinel, "ok": f01_ok})

    # F01 反向：失败诊断容器/字段/版本非法与半文件 0003 一律协议阻断
    # 说明：本轮变体一律在**全新的本版本批次**上真实构建（复制批次会改变推导路径，
    # 使路径类核验先于失败诊断触发，无法定向验证失败诊断本身）。
    def f01_injected_batch(leaf: str) -> tuple:
        target = build_gate1_approved(leaf)
        writer_real = host._write_exclusive_json
        hits = {"count": 0}

        def writer_inject(path, payload, stage, _real=writer_real, _hits=hits):
            result = _real(path, payload, stage)
            if Path(path).name == "0003.json" and _hits["count"] == 0:
                _hits["count"] += 1
                try:
                    raise OSError(f01_sentinel)
                except OSError as cause:
                    raise host.WorkflowHostError(
                        f"注入：0003 写完后宿主运行失败（{f01_sentinel}）",
                        reasons=[f01_sentinel], stage="post_write_verify") from cause
            return result

        host._write_exclusive_json = writer_inject
        counts["host_api_calls"] += 1
        try:
            host.prepare_dev_gate2(target)
            outcome = "ok"
        except host.WorkflowHostError:
            outcome = "error"
        except host.WorkflowHostBlocked:
            outcome = "blocked"
        finally:
            host._write_exclusive_json = writer_real
        counts["fault_injections"] += 1
        return target, outcome, hits["count"]

    def rewrite_failure(target: Path, mutate) -> None:
        path = target / "workflow" / "gate2" / "failure.json"
        payload = json.loads(path.read_text("utf-8"))
        mutate(payload)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    variant_specs = (
        ("g10_f01_bad_version",
         lambda t: rewrite_failure(t, lambda pl: pl.__setitem__("failure_version", "UNSUPPORTED-1.0")),
         "failure.json.failure_version"),
        ("g10_f01_incomplete_failure",
         lambda t: rewrite_failure(t, lambda pl: pl.pop("reasons", None)),
         "failure.json.reasons"),
        ("g10_f01_invalid_json",
         lambda t: (t / "workflow" / "gate2" / "failure.json").write_text("{ 这不是 JSON",
                                                                         encoding="utf-8"),
         "failure.json"),
        ("g10_f01_failure_not_file",
         lambda t: ((t / "workflow" / "gate2" / "failure.json").unlink(),
                    (t / "workflow" / "gate2" / "failure.json").mkdir()),
         "failure.json"),
        ("g10_f01_half_0003",
         lambda t: (t / "workflow" / "checkpoints" / "0003.json").write_bytes(
             (t / "workflow" / "checkpoints" / "0003.json").read_bytes()[:40]),
         "0003.json"),
    )
    for label, mutate, reason in variant_specs:
        variant, variant_outcome, variant_hits = f01_injected_batch(label)
        if variant_outcome != "error" or variant_hits != 1:
            g10.append(f"{label} 注入 prepare 未按预期失败：{variant_outcome} hits={variant_hits}")
        mutate(variant)
        expect_status_blocked(label, variant, 1, reason, r1_probes)

    # F01 正向：正常成功批次不得有 failure.json
    if (main / "workflow" / "gate2" / "failure.json").exists():
        g10.append("成功批次存在 failure.json")
    if not (main / "workflow" / "checkpoints" / "0003.json").is_file():
        g10.append("成功批次缺少 0003")

    # --- F02：三个收尾复测探针（各命中 1，且撤销后仍拒绝）---
    def f02_status_probe(leaf: str, which: str) -> None:
        source = build_gate1_approved(leaf)
        run_cli(f"{leaf}_prepare", ["prepare-gate2", "--batch-dir", str(source)], 0)
        before = {"hash": None, "after": None}
        real_prepare = host.CONTROLLER_MODULE.prepare_dev_gate
        hits = {"n": 0}

        def wrapper(workflow, gate, materials, current_bindings=None, _real=real_prepare,
                    _target=source, _which=which, _hits=hits, _before=before):
            result = _real(workflow, gate, materials, current_bindings=current_bindings)
            if _hits["n"] == 0:
                _hits["n"] += 1
                path = (host._gate2_paths(_target, "probe")["database_path"] if _which == "database"
                        else _target / "workflow" / "gate2" / "load_report.json")
                _before["hash"] = sha256(path)
                path.write_bytes(path.read_bytes() + b"\n")
                _before["after"] = sha256(path)
            return result

        host.CONTROLLER_MODULE.prepare_dev_gate = wrapper
        counts["fault_injections"] += 1
        counts["controller_calls"] += 1
        try:
            exit_code, payload = status_inproc(source)
        finally:
            host.CONTROLLER_MODULE.prepare_dev_gate = real_prepare
        changed = ("audit.sqlite3" if which == "database" else "load_report.json")
        later_reason = ("database_sha256" if which == "database" else "load_report_file_sha256")
        ok = exit_code == 1 and "收尾复测" in payload.get("message", "") and changed in payload.get(
            "message", "") and hits["n"] == 1 and before["hash"] != before["after"]
        if not ok:
            g10.append(f"F02 status 探针（{which}）未在本次调用内拒绝：exit={exit_code} "
                       f"hits={hits['n']} msg={payload.get('message', '')[:140]}")
        after_entry = expect_status_blocked(f"{leaf}_later_status", source, 1, later_reason, r1_probes)
        if not after_entry:
            g10.append(f"F02 status 探针（{which}）撤销后未拒绝")
        r1_probes.append({"case": f"g10_f02_status_{which}", "injected": hits["n"],
                          "before_sha256": before["hash"], "after_sha256": before["after"],
                          "injection_point": "初次材料核验之后、纯 prepare_dev_gate 重放返回时",
                          "current_exit": exit_code, "later_exit": 1,
                          "target_reason": changed, "ok": ok})

    f02_status_probe("g10_f02_db", "database")
    f02_status_probe("g10_f02_report", "load_report")

    # 探针 3：实际 prepare 的第二次重放返回时改 load_report（同进程 prepare）
    f02p3 = build_gate1_approved("g10_f02_prepare")
    real_prepare3 = host.CONTROLLER_MODULE.prepare_dev_gate
    hits3 = {"n": 0}
    f02p3_before = {"hash": None, "after": None}

    def wrapper3(workflow, gate, materials, current_bindings=None, _real=real_prepare3,
                 _target=f02p3, _hits=hits3, _before=f02p3_before):
        result = _real(workflow, gate, materials, current_bindings=current_bindings)
        _hits["n"] += 1
        if _hits["n"] == 2:
            path = _target / "workflow" / "gate2" / "load_report.json"
            _before["hash"] = sha256(path)
            path.write_bytes(path.read_bytes() + b"\n")
            _before["after"] = sha256(path)
        return result

    host.CONTROLLER_MODULE.prepare_dev_gate = wrapper3
    counts["fault_injections"] += 1
    counts["controller_calls"] += 1
    counts["host_api_calls"] += 1
    p3_outcome, p3_message = "ok", ""
    try:
        host.prepare_dev_gate2(f02p3)
    except host.WorkflowHostBlocked as exc:
        p3_outcome, p3_message = "blocked", str(exc)
    except host.WorkflowHostError as exc:
        p3_outcome, p3_message = "error", str(exc)
    finally:
        host.CONTROLLER_MODULE.prepare_dev_gate = real_prepare3
    p3_ok = (p3_outcome == "blocked" and hits3["n"] == 2 and "收尾复测" in p3_message
             and "load_report.json" in p3_message and f02p3_before["hash"] != f02p3_before["after"])
    if not p3_ok:
        g10.append(f"F02 prepare 探针未在本次调用内拒绝：outcome={p3_outcome} hits={hits3['n']} "
                   f"msg={p3_message[:140]}")
    p3_later = expect_status_blocked("g10_f02_prepare_later_status", f02p3, 1, "load_report.json",
                                     r1_probes)
    if not p3_later:
        g10.append("F02 prepare 探针撤销后 status 未拒绝")
    r1_probes.append({"case": "g10_f02_prepare_second_replay", "replays": hits3["n"],
                      "before_sha256": f02p3_before["hash"], "after_sha256": f02p3_before["after"],
                      "injection_point": "实际 prepare 的第二次 prepare_dev_gate（写后重放）返回时",
                      "current_outcome": p3_outcome, "later_exit": 1,
                      "target_reason": "load_report.json 收尾复测", "ok": p3_ok})

    # F02 正向：未变化的正常批次不误拒
    positive_exit, positive_payload = status_inproc(main)
    if positive_exit != 0 or positive_payload.get("phase") != "DEV_GATE2_PENDING":
        g10.append(f"正常 Gate2 批次被误拒：exit={positive_exit}")
    r1_probes.append({"case": "g10_f02_positive_control", "exit": positive_exit,
                      "phase": positive_payload.get("phase"),
                      "target_reason": "未变化正向不误拒", "ok": positive_exit == 0})

    # --- F03：artifacts 字节引用与语义声明 ---
    def sync_artifacts(destination: Path, mutate) -> dict:
        artifacts_path = destination / "workflow" / "gate2" / "artifacts.json"
        artifacts = json.loads(artifacts_path.read_text("utf-8"))
        mutate(artifacts)
        artifacts_path.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
        checkpoint_path = destination / "workflow" / "checkpoints" / "0003.json"
        checkpoint = json.loads(checkpoint_path.read_text("utf-8"))
        checkpoint["operation"]["artifacts"] = json.loads(json.dumps(artifacts))
        checkpoint["operation"]["artifacts_file_sha256"] = sha256(artifacts_path)
        checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
        return {"artifacts_file_sha256": sha256(artifacts_path)}

    f03_source = retarget_copy("g10_f03_base", main)
    f03_cases = []
    only_newline = retarget_copy("g10_f03_newline", main)
    path = only_newline / "workflow" / "gate2" / "artifacts.json"
    path.write_bytes(path.read_bytes() + b"\n")
    counts["fault_injections"] += 1
    f03_cases.append(("仅换行（语义不变，字节变化）", only_newline, "operation.artifacts_file_sha256"))

    for leaf, field in (("g10_f03_db_zero", "database_sha256"),
                        ("g10_f03_norm_zero", "normalized_payload_sha256"),
                        ("g10_f03_gate1_zero", "gate1_decision_sha256"),
                        ("g10_f03_manifest_zero", "host_manifest_file_sha256")):
        target = retarget_copy(leaf, main)
        sync_artifacts(target, lambda a, _f=field: a.__setitem__(_f, "0" * 64))
        counts["fault_injections"] += 1
        f03_cases.append((f"{field} 全零（同步文件哈希与摘要副本）", target, f"artifacts.json.{field}"))

    unknown_version = retarget_copy("g10_f03_unknown_version", main)
    sync_artifacts(unknown_version, lambda a: a.__setitem__("artifacts_version", "UNSUPPORTED-VERSION"))
    counts["fault_injections"] += 1
    f03_cases.append(("artifacts_version 未知（同步）", unknown_version, "artifacts_version"))

    bad_checkpoint_version = retarget_copy("g10_f03_checkpoint_version", main)
    sync_artifacts(bad_checkpoint_version, lambda a: a.__setitem__("checkpoint_version", "TASK-000-x"))
    counts["fault_injections"] += 1
    f03_cases.append(("artifacts.checkpoint_version 不符（同步）", bad_checkpoint_version,
                      "checkpoint_version"))

    for name, target, reason in f03_cases:
        expect_status_blocked(f"g10_f03_{reason.split('.')[-1]}_{name[:6]}", target, 1, reason, r1_probes)

    # --- F02 剩余反例（R2）：checkpoint 初始字节与哈希必须同源，收尾复测拒绝晚期变化 ---
    timing = build_gate1_approved("g10_f02_ckpt_timing")
    run_cli("g10_f02_ckpt_timing_prepare", ["prepare-gate2", "--batch-dir", str(timing)], 0)
    positive_code, positive_payload = status_inproc(timing)
    positive_ok = (
        positive_code == 0
        and positive_payload.get("phase") == "DEV_GATE2_PENDING"
        and positive_payload.get("gate1_approval") is None
        and positive_payload.get("gate2_approval") is None
        and positive_payload.get("next_step_allowed") is False
    )
    if not positive_ok:
        g10.append(f"F02 时序探针正向控制未通过：exit={positive_code} "
                   f"phase={positive_payload.get('phase')!r}")
    timing_0003 = timing / "workflow" / "checkpoints" / "0003.json"
    timing_before = sha256(timing_0003)
    timing_real_prepare = host.CONTROLLER_MODULE.prepare_dev_gate
    timing_hits = {"n": 0}

    def timing_wrapper(workflow, gate, materials, current_bindings=None,
                       _real=timing_real_prepare, _path=timing_0003, _hits=timing_hits):
        result = _real(workflow, gate, materials, current_bindings=current_bindings)
        if _hits["n"] == 0:
            _hits["n"] += 1
            payload = json.loads(_path.read_text(encoding="utf-8"))
            payload["operation"]["materials_sha256"] = "0" * 64
            _path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result

    host.CONTROLLER_MODULE.prepare_dev_gate = timing_wrapper
    counts["fault_injections"] += 1
    counts["controller_calls"] += 1
    try:
        timing_code, timing_payload = status_inproc(timing)
    finally:
        host.CONTROLLER_MODULE.prepare_dev_gate = timing_real_prepare
    timing_after = sha256(timing_0003)
    timing_message = timing_payload.get("message", "")
    timing_ok = (
        timing_code == 1
        and timing_payload.get("exception_class") == "WorkflowHostBlocked"
        and "workflow/checkpoints/0003.json" in timing_message
        and "收尾复测" in timing_message
        and "变化" in timing_message
        and timing_hits["n"] == 1
        and timing_before != timing_after
    )
    if not timing_ok:
        g10.append(f"F02 时序探针未在本次调用内拒绝：exit={timing_code} hits={timing_hits['n']} "
                   f"before!=after={timing_before != timing_after} msg={timing_message[:160]}")
    timing_later = run_cli("g10_f02_ckpt_timing_later_status",
                           ["status", "--batch-dir", str(timing)], 1)
    later_message = (timing_later.get("payload") or {}).get("message", "")
    later_ok = (timing_later["exit_code"] == 1
                and "0003.json.operation.materials_sha256" in later_message)
    if not later_ok:
        g10.append(f"F02 时序探针撤销后 CLI status 未指向 materials_sha256："
                   f"exit={timing_later['exit_code']} msg={later_message[:160]}")
    r1_probes.append({
        "case": "g10_f02_checkpoint_initial_bytes_timing",
        "injection_point": "Gate2 纯 prepare_dev_gate 重放返回时（旧 JSON 已被消费）",
        "changed_field": "0003.json.operation.materials_sha256 → 64 个 0",
        "hits": timing_hits["n"],
        "before_sha256": timing_before, "after_sha256": timing_after,
        "before_taken_at": "故障调用之前", "after_taken_at": "调用结束后",
        "positive_control": {"exit": positive_code, "phase": positive_payload.get("phase"),
                             "gate1_approval": positive_payload.get("gate1_approval"),
                             "gate2_approval": positive_payload.get("gate2_approval"),
                             "next_step_allowed": positive_payload.get("next_step_allowed"),
                             "ok": positive_ok},
        "current_exit": timing_code,
        "current_exception_class": timing_payload.get("exception_class"),
        "current_message": timing_message[:400],
        "later_cli_command": ["status", "--batch-dir", str(timing)],
        "later_cli_exit": timing_later["exit_code"],
        "later_cli_message": later_message[:400],
        "target_reason": "workflow/checkpoints/0003.json 收尾字节变化（本次即拒绝）",
        "later_target_reason": "0003.json.operation.materials_sha256",
        "ok": bool(timing_ok and later_ok),
    })

    record("G10_R1_FAILURE_TAIL_AND_ARTIFACT_SEMANTICS", "flow", g10, probes=r1_probes)

    # ------------------------------------------------------------------
    # G9 自测、计数与一次性落盘
    # ------------------------------------------------------------------
    g9: list = []
    synthetic_ok = guarded_matches({"actual_class": "WorkflowHostBlocked", "exit": 1, "message": "目标原因"},
                                  "WorkflowHostBlocked", "目标原因")
    synthetic_bad = guarded_matches({"actual_class": "WorkflowHostBlocked", "exit": 1, "message": "别的原因"},
                                    "WorkflowHostBlocked", "目标原因")
    helper_self_test = {"case": "TASK-011_probe_matcher_self_test",
                        "positive": synthetic_ok, "class_right_reason_wrong": synthetic_bad,
                        "ok": synthetic_ok and not synthetic_bad}
    if not helper_self_test["ok"]:
        failures.append({"case": "TASK-011_MATCHER_SELF_TEST", "kind": "selftest", "result": "FAIL",
                         "problems": ["类别正确但目标原因不符未被判失败"]})

    def is_copy(relative: str) -> bool:
        copy_paths = {item["copy"] for item in copy_records}
        return any(relative == item or relative.startswith(item + "/") for item in copy_paths)

    def receive_identities(batch_root: Path) -> list:
        """所有非副本的接收身份（含无宿主清单的直接接收与运行失败样本）。"""
        identities = []
        for manifest_path in sorted(batch_root.rglob("batch_manifest.json")):
            batch_dir = manifest_path.parent
            relative = str(batch_dir.relative_to(PROJECT_ROOT))
            if is_copy(relative):
                continue
            invocation = {}
            if manifest_path.is_file():
                try:
                    invocation = (json.loads(manifest_path.read_text("utf-8"))
                                  .get("checker_invocation") or {})
                except json.JSONDecodeError:
                    invocation = {}
            identities.append({"batch": relative,
                               "checker_started": invocation.get("started") is True,
                               "checker_exit_code": invocation.get("exit_code"),
                               "has_host_invocation": (batch_dir / "workflow" /
                                                       "receive_invocation.json").is_file()})
        return identities

    def audit_calls(batch_root: Path, starts: list, identities: list) -> dict:
        """登记的真实启动与留痕一一对应核对（不只比总数）。"""
        registered = {item["batch"] for item in starts
                      if not is_copy(item["batch"])}
        host_records = set()
        for record_path in sorted(batch_root.rglob("receive_invocation.json")):
            relative = str(record_path.parent.parent.relative_to(PROJECT_ROOT))
            if is_copy(relative):
                continue
            host_records.add(relative)
        direct_only = {item["batch"] for item in starts if item["entry"] == "direct_receiver"}
        identity_paths = {item["batch"] for item in identities}
        unregistered_host_records = sorted(host_records - registered)
        missing_records = sorted(registered - host_records - direct_only)
        unregistered_identities = sorted(identity_paths - registered - host_records)
        missing_trace = sorted((registered | host_records) - identity_paths - direct_only)
        return {"registered_starts": len(registered), "host_invocation_records": len(host_records),
                "direct_receiver_starts": len(direct_only),
                "receiver_total": len(registered),
                "receive_identities": len(identity_paths),
                "checker_started_total": sum(1 for item in identities if item["checker_started"]),
                "unregistered_host_records": unregistered_host_records,
                "missing_records": missing_records,
                "unregistered_identities": unregistered_identities,
                "missing_trace": missing_trace, "starts": starts, "identities": identities}

    identities = receive_identities(batch_parent)
    audit = audit_calls(batch_parent, start_records, identities)

    # 计数核验自测（只在新内存副本上）：少一条启动记录 / 多一条未登记记录
    drop_probe = audit_calls(batch_parent, start_records[1:], identities)
    extra_record = dict(start_records[0])
    extra_record["batch"] = "data/batches/<未登记批次>"
    extra_probe = audit_calls(batch_parent, start_records + [extra_record], identities)
    count_self_test = {"case": "TASK-011_count_audit_self_test",
                       "drop_one_start_in_memory": bool(start_records),
                       "detected_missing_after_drop": bool(drop_probe["unregistered_host_records"]
                                                           or drop_probe["missing_trace"]),
                       "detected_unregistered_after_add": bool(extra_probe["unregistered_identities"]
                                                               or extra_probe["missing_trace"]),
                       "drop_probe": {k: drop_probe[k] for k in ("registered_starts",
                                                                 "unregistered_host_records",
                                                                 "missing_trace")},
                       "extra_probe": {k: extra_probe[k] for k in ("registered_starts",
                                                                   "unregistered_identities",
                                                                   "missing_trace")}}
    count_self_test["ok"] = bool(count_self_test["detected_missing_after_drop"]
                                 and count_self_test["detected_unregistered_after_add"])
    if not count_self_test["ok"]:
        failures.append({"case": "TASK-011_COUNT_SELF_TEST", "kind": "selftest", "result": "FAIL",
                         "problems": ["计数核验在缺少留痕或出现未登记记录时未判定不一致"]})

    for key in ("unregistered_host_records", "missing_records", "unregistered_identities",
                "missing_trace"):
        if audit[key]:
            g9.append(f"{key}={audit[key]}")

    # 拒绝次数一律从本轮真实调用的留痕导出（不使用常量）：
    #   - 实际负向调用：CLI 日志中期望退出码为 1／2 的真实调用
    #   - 探针层记录：各组探针里带 exit 的定向负向观察（应为前者的子集）
    negative_calls = [log["label"] for log in cli_logs if log["expect_exit"] in (1, 2)]
    rejection_records = [item for group in (probe_records, lock_probes, tamper_probes, error_probes,
                                            r1_probes)
                         for item in group if isinstance(item, dict) and item.get("exit") in (1, 2)]
    counts["rejections_observed"] = len(negative_calls)
    counts["rejection_probes_recorded"] = len(rejection_records)
    if len(rejection_records) > len(negative_calls):
        g9.append("探针记录的拒绝数多于真实负向调用数")
    counts["simulated_decisions"] = sum(
        1 for log in cli_logs if "record-simulated-decision" in log["command"] and log["exit_code"] == 0)

    # CLI 子进程内的标准化/装载不可直接观测：按该子进程成功完成的 prepare 推导并分列
    cli_prepare_ok = sum(1 for log in cli_logs
                         if log["command"][2].endswith("run_demo_workflow.py")
                         and "prepare-gate2" in log["command"] and log["exit_code"] == 0)
    counts["normalize_calls_cli_unobserved"] = None
    counts["load_calls_cli_unobserved"] = None
    counts["normalize_calls_cli_derived"] = cli_prepare_ok
    counts["load_calls_cli_derived"] = cli_prepare_ok
    counts["receiver_starts"] = audit["receiver_total"]
    counts["checker_runs"] = audit["checker_started_total"]
    counts["real_approvals"] = 0
    if audit["receiver_total"] != len(registered_union := {item["batch"] for item in start_records
                                                           if not is_copy(item["batch"])}):
        g9.append("接收启动登记数与唯一批次不一致")
    record("G9_SELF_TESTS_AND_COUNTS", "flow", g9,
           probes=[helper_self_test, count_self_test],
           count_audit={k: audit[k] for k in ("registered_starts", "host_invocation_records",
                                              "direct_receiver_starts", "receiver_total",
                                              "receive_identities", "checker_started_total",
                                              "unregistered_host_records", "missing_records",
                                              "unregistered_identities", "missing_trace")},
           counts=dict(counts))

    protected_after = {str(p.relative_to(PROJECT_ROOT)): sha256(p) for p in PROTECTED if p.exists()}
    changed_protected = [name for name in protected_before
                         if protected_after.get(name) != protected_before[name]]
    if changed_protected:
        failures.append({"case": "PROTECTED_FILES", "kind": "integrity", "result": "FAIL",
                         "problems": changed_protected})

    summary = {
        "task": "TASK-011",
        "out_dir": str(container),
        "batch_parent": str(batch_parent),
        "python": sys.version.split()[0],
        "host": {"path": str(HOST), "sha256": sha256(HOST), "version": host.HOST_VERSION},
        "counts": dict(counts),
        "checks": checks,
        "cli_logs": cli_logs,
        "case_logs": case_logs,
        "failures": failures,
        "self_tests": {"probe_matcher": helper_self_test, "count_audit": count_self_test},
        "count_basis": {
            "receiver": "宿主 receive_invocation.json + 测试侧登记的直接 receiver 启动（一一对应）",
            "checker": "各接收身份的 batch_manifest.checker_invocation.started（含运行失败样本）",
            "inproc_normalize_load": "测试侧计数包装真实上游（故障前调用也计）",
            "cli_normalize_load": "子进程内不可直接观测，按成功完成的 CLI prepare 推导并分列",
        },
        "protected_files_count": len(protected_before),
        "protected_files_unchanged": not changed_protected,
        "note": ("本入口真实运行接收、质量核验、标准化与 SQLite 装载，停在 Gate2 待确认；"
                 "未执行筛查、复算、底稿或 AI，未提交任何 Gate2 决定。"),
    }
    final_artifacts = {"summary.json": summary, "checks.json": checks, "cli_logs.json": cli_logs}
    save_problems = []
    for name, payload in final_artifacts.items():
        path = container / name
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            readback = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            save_problems.append(f"{name}: {exc}")
            continue
        if controller.canonical_json(readback) != controller.canonical_json(payload):
            save_problems.append(f"{name} 读回不一致")
    readback_problems = []
    persisted = json.loads((container / "summary.json").read_text("utf-8"))
    if len(persisted["checks"]) != len(checks):
        readback_problems.append("summary.checks 与内存不一致")
    if len(persisted["failures"]) != len(failures):
        readback_problems.append("summary.failures 与内存不一致")
    readback_summary = {"case": "TASK-011_FINAL_ARTIFACT_READBACK", "save_problems": save_problems,
                        "readback_problems": readback_problems,
                        "files": sorted(final_artifacts), "ok": not save_problems and not readback_problems}
    if not readback_summary["ok"]:
        failures.append({"case": "TASK-011_FINAL_ARTIFACT_READBACK", "kind": "artifact", "result": "FAIL",
                         "problems": save_problems + readback_problems})
        print(f"[FAIL] TASK-011_FINAL_ARTIFACT_READBACK {save_problems + readback_problems}")
    else:
        print("[PASS] TASK-011_FINAL_ARTIFACT_READBACK 最终汇总一次落盘并读回一致")
    (container / "final_readback.json").write_text(
        json.dumps(readback_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (container / "self_tests.json").write_text(
        json.dumps(summary["self_tests"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"CLI 调用：start {counts['start_cli']}、status {counts['status_cli']}、"
          f"record {counts['record_cli']}、prepare-gate2 {counts['prepare_cli']}；"
          f"宿主 API {counts['host_api_calls']}；控制器调用 {counts['controller_calls']}")
    print(f"真实接收 {counts['receiver_starts']}"
          f"（宿主启动 {counts['receiver_starts_host']} + 直接接收器调用 {counts['receiver_starts_direct']}）、"
          f"checker {counts['checker_runs']}（按清单 checker_invocation.started 派生）")
    print(f"进程内标准化 {counts['normalize_calls_inproc']}、进程内装载 {counts['load_calls_inproc']}；"
          f"CLI 子进程内次数未直接观测={counts['normalize_calls_cli_unobserved']}，"
          f"按成功完成的 CLI prepare 推导 {counts['normalize_calls_cli_derived']}；"
          f"副本 {counts['copies']}、故障注入 {counts['fault_injections']}、"
          f"拒绝 {counts['rejections_observed']}、真实批准 {counts['real_approvals']}")
    print(f"测试失败 {len(failures)}；受保护文件前后哈希一致: {summary['protected_files_unchanged']}"
          f"（{summary['protected_files_count']} 个）")
    print(f"汇总: {container / 'summary.json'}")
    result_code = 1 if failures else 0
    print("全部预期成立。" if not failures else "存在断言失败或保护失败，返回非零退出码。")
    sys.stdout, sys.stderr = original_stdout, original_stderr
    stdout_tee.close()
    stderr_tee.close()
    return result_code


if __name__ == "__main__":
    sys.exit(main())
