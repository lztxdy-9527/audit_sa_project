#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-010 开发态接收宿主：开发验证入口。

用法：

    & 'D:\\harness work\\audit_sa_project\\.venv\\Scripts\\python.exe' -B `
      'D:\\harness work\\audit_sa_project\\tests\\test_run_demo_workflow.py' `
      --out-dir 'D:\\harness work\\audit_sa_project\\data\\workflow_host_tests\\task010_01'

本入口用**真实子进程**调用宿主 CLI（因此每一步都是新进程，可验证重启恢复），并真实调用冻结接收器与 checker。
批次建立在 `data/batches/<本容器名>/<案例>` 下；不修改任何现有批次、冻结脚本或原合成工作簿。
退出码：0 全部符合预期；1 断言或保护失败；2 参数或环境问题。
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOST_TESTS_ROOT = (PROJECT_ROOT / "data" / "workflow_host_tests").resolve()
BATCHES_ROOT = (PROJECT_ROOT / "data" / "batches").resolve()
HOST = PROJECT_ROOT / "scripts" / "run_demo_workflow.py"
DEMO_WORKBOOK = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a" / "input" / "erp_export.xlsx"
C12_WORKBOOK = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a" / "fixtures" / "C12.xlsx"
OLD_RECEIVE_BATCH = BATCHES_ROOT / "dev_receive_003_main_02"
PROTECTED_FILES = [
    HOST,
    PROJECT_ROOT / "scripts" / "control_demo_workflow.py",
    PROJECT_ROOT / "scripts" / "receive_demo_batch.py",
    PROJECT_ROOT / "scripts" / "check_demo_data.py",
    PROJECT_ROOT / "scripts" / "normalize_demo_data.py",
    PROJECT_ROOT / "scripts" / "store_demo_sqlite.py",
    PROJECT_ROOT / "scripts" / "screen_demo_sqlite.py",
    PROJECT_ROOT / "scripts" / "crosscheck_demo_rules.py",
    PROJECT_ROOT / "scripts" / "build_demo_fact_packet.py",
    PROJECT_ROOT / "sql" / "demo_schema.sql",
    *[PROJECT_ROOT / "sql" / "rules" / f"r0{index}.sql" for index in (1, 2, 3, 4)],
    PROJECT_ROOT / "docs" / "SPEC_V1.md",
    PROJECT_ROOT / "docs" / "AUDIT_CONTRACT_DRAFT.md",
    DEMO_WORKBOOK,
    C12_WORKBOOK,
]
FORBIDDEN_IMPORTS = {"sqlite3", "openpyxl", "pandas", "numpy", "chromadb", "requests", "urllib",
                     "http", "socket", "openai", "anthropic", "normalize_demo_data", "store_demo_sqlite",
                     "screen_demo_sqlite", "crosscheck_demo_rules", "build_demo_fact_packet"}
FORBIDDEN_TOKENS = ("ground_truth", "fixture_expectations", "make_demo_data", "screen_sqlite",
                    ".sql", "openai", "anthropic", "llm")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    print(f"RUNTIME_ERROR: {message}", file=sys.stderr)
    sys.exit(2)


class Tee:
    def __init__(self, stream, path: Path):
        self._stream = stream
        self._file = path.open("w", encoding="utf-8")

    def write(self, data):
        self._stream.write(data)
        self._file.write(data)
        return len(data)

    def flush(self):
        self._stream.flush()
        self._file.flush()

    def close(self):
        self._file.close()


def tree_hashes(root: Path) -> dict:
    if not root.exists():
        return {}
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TASK-010 接收宿主开发验证")
    parser.add_argument("--out-dir", required=True, help="data/workflow_host_tests 下尚不存在的测试容器")
    args = parser.parse_args(argv)

    container = Path(args.out_dir)
    container = container.resolve() if container.is_absolute() else (Path.cwd() / container).resolve()
    try:
        container.relative_to(HOST_TESTS_ROOT)
    except ValueError:
        fail(f"测试容器必须位于 {HOST_TESTS_ROOT} 之内：{container}")
    if container == HOST_TESTS_ROOT:
        fail("测试容器不能是 data/workflow_host_tests 本身")
    if container.exists():
        fail(f"测试容器已存在，拒绝覆盖历史：{container}")
    batch_parent = BATCHES_ROOT / container.name
    if batch_parent.exists():
        fail(f"本容器的批次父目录已存在，拒绝覆盖：{batch_parent}")
    for required in (HOST, DEMO_WORKBOOK, C12_WORKBOOK):
        if not required.exists():
            fail(f"缺少必需输入：{required}")

    hashes_before = {str(path): sha256(path) for path in PROTECTED_FILES}
    container.mkdir(parents=True)
    (container / "cli_logs").mkdir(exist_ok=True)
    original_stdout, original_stderr = sys.stdout, sys.stderr
    stdout_tee = Tee(original_stdout, container / "stdout.txt")
    stderr_tee = Tee(original_stderr, container / "stderr.txt")
    sys.stdout, sys.stderr = stdout_tee, stderr_tee

    spec = importlib.util.spec_from_file_location("host_under_test", HOST)
    host = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(host)

    checks: list = []
    failures: list = []
    cli_logs: list = []
    counts = {"start_cli": 0, "status_cli": 0, "record_cli": 0, "host_api_calls": 0,
              "controller_sample_calls": 0, "receiver_starts": 0, "checker_runs": 0,
              "simulated_decisions": 0, "real_approvals": 0, "fault_injections": 0,
              "batch_copies": 0, "real_writer_faults": 0, "writer_partial_bytes": 0}
    copy_records: list = []
    expected_starts: list = []

    def register_start(batch_dir) -> None:
        """登记一次真实启动（CLI 或 API），供调用记录一一对应核对。"""
        relative = str(Path(batch_dir).relative_to(PROJECT_ROOT))
        if relative not in expected_starts:
            expected_starts.append(relative)

    def audit_starts(records, expected, copies):
        """核对“登记的真实启动”与“独立调用记录”是否一一对应（副本排除）。"""
        copy_paths = {item["copy"] for item in copies}
        observed = {item["batch"] for item in records}
        missing = [item for item in expected
                   if item not in observed
                   and not any(item == c or item.startswith(c + "/") for c in copy_paths)]
        return {"expected_starts": len(expected), "observed_records": len(observed),
                "missing_records": sorted(missing)}

    def register_copy(destination: Path, source: Path, case: str) -> None:
        counts["batch_copies"] += 1
        copy_records.append({"copy": str(destination.relative_to(PROJECT_ROOT)),
                             "source": str(source.relative_to(PROJECT_ROOT)), "case": case,
                             "kind": "fault_copy", "note": "副本不计真实接收／checker"})

    def record(case: str, kind: str, problems: list, **extra) -> None:
        detail = {"case": case, "kind": kind, "result": "PASS" if not problems else "FAIL",
                  "problems": problems, **extra}
        checks.append(detail)
        if problems:
            failures.append(detail)
        print(f"[{'PASS' if not problems else 'FAIL'}] {case}"
              + ("" if not problems else "  | " + " ; ".join(str(item) for item in problems)[:600]))

    def run_cli(label: str, sub_args: list, expect_exit: int) -> dict:
        target_arg = None
        if "--batch-dir" in sub_args:
            target_arg = Path(sub_args[sub_args.index("--batch-dir") + 1])
        existed_before = bool(target_arg and target_arg.exists())
        command = [sys.executable, "-B", str(HOST), *sub_args]
        completed = subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        stdout_path = container / "cli_logs" / f"{len(cli_logs) + 1:03d}_{label}.stdout.txt"
        stderr_path = container / "cli_logs" / f"{len(cli_logs) + 1:03d}_{label}.stderr.txt"
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        payload = None
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
        entry = {"label": label, "command": command, "cwd": str(PROJECT_ROOT),
                 "exit_code": completed.returncode, "expect_exit": expect_exit,
                 "stdout_path": str(stdout_path.relative_to(container)),
                 "stderr_path": str(stderr_path.relative_to(container)),
                 "payload": payload, "stderr_tail": completed.stderr[-400:],
                 "ok": completed.returncode == expect_exit}
        cli_logs.append(entry)
        if sub_args and sub_args[0] == "start":
            counts["start_cli"] += 1
            # 按“是否实际启动接收器”计数：批次目录由接收器创建（调用前不存在、调用后存在）
            if target_arg is not None and not existed_before and target_arg.exists():
                counts["receiver_starts"] += 1
                register_start(target_arg)
        elif sub_args and sub_args[0] == "status":
            counts["status_cli"] += 1
        elif sub_args and sub_args[0] == "record-simulated-decision":
            counts["record_cli"] += 1
        print(f"    CLI {label}: exit={completed.returncode}（期望 {expect_exit}）")
        return entry

    def write_decision(path: Path, batch_dir: Path, decision: str, *, event_id: str,
                       confirm: bool = True, mutate=None) -> Path:
        checkpoint = json.loads((batch_dir / "workflow" / "checkpoints" / "0001.json").read_text(encoding="utf-8"))
        request = checkpoint["workflow"]["state"]["requests"]["GATE1"]
        payload = {
            "event_id": event_id,
            "batch_id": batch_dir.name,
            "gate": "GATE1",
            "request_id": request["request_id"],
            "materials_sha256": request["materials_sha256"],
            "decision": decision,
            "actor_kind": "SIMULATED_HUMAN",
            "actor_id": "tester-01",
            "occurred_at": "2026-10-11T12:00:00+08:00",
            "reason": "测试人员模拟复核（非真实批准）",
            "simulation": "SIMULATED_TEST_ONLY",
        }
        if confirm:
            payload["confirmations"] = {"scope_and_source_reviewed": True}
        if mutate is not None:
            mutate(payload)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def batch_path(name: str) -> Path:
        return batch_parent / name

    print(f"测试容器: {container}")
    print(f"批次父目录: {batch_parent}")
    print(f"Python {sys.version.split()[0]} / 宿主版本 {host.HOST_VERSION}")
    print()

    # ---------- 1. MAIN 实际 start 与重启恢复 ----------
    g1_problems: list = []
    started = run_cli("g1_start_main", ["start", "--workbook", str(DEMO_WORKBOOK),
                                        "--batch-dir", str(batch_path("main_01")),
                                        "--source-description", "合成 ERP 导出（演示用）"], 0)
    batch1 = batch_path("main_01")
    if started["exit_code"] != 0 or not isinstance(started["payload"], dict):
        g1_problems.append(f"start 失败：exit={started['exit_code']} stderr={started['stderr_tail'][:200]}")
    else:
        payload = started["payload"]
        if payload.get("phase") != "DEV_GATE1_PENDING":
            g1_problems.append(f"start 后 phase={payload.get('phase')!r}")
        if payload.get("simulated_decisions") != 0 or payload.get("real_approvals") != 0:
            g1_problems.append("start 不得产生模拟决定或真实批准")
        host_manifest = json.loads((batch1 / "workflow" / "host_manifest.json").read_text(encoding="utf-8"))
        if host_manifest["receive"]["exit_code"] != 0:
            g1_problems.append("接收器退出码记录不符")
        if host_manifest["receive"]["command"][2] != str(PROJECT_ROOT / "scripts" / "receive_demo_batch.py"):
            g1_problems.append("真实调用命令未指向冻结接收器")
        if (batch1 / "workflow" / "receive.stdout.txt").read_text(encoding="utf-8") == "":
            g1_problems.append("未保存接收器 stdout")
        snapshot = sha256(batch1 / "source" / "input.xlsx")
        if snapshot != sha256(DEMO_WORKBOOK):
            g1_problems.append("批次快照与来源不一致")
        quality = json.loads((batch1 / "checks" / "quality_report.json").read_text(encoding="utf-8"))
        if quality.get("result") != "pass" or quality.get("issues") != [] or quality.get("issue_counts_by_code") != {}:
            g1_problems.append("质量报告不是 pass／空问题")
        if quality["workbook"]["sha256"] != snapshot or quality["checker"]["sha256"] != sha256(
                PROJECT_ROOT / "scripts" / "check_demo_data.py"):
            g1_problems.append("质量报告绑定与快照／checker 不符")
        counts["checker_runs"] += 1 if quality.get("result") == "pass" else 0
        for label, relative in host.RECEIVER_MATERIALS:
            if not (batch1 / relative).exists():
                g1_problems.append(f"缺少接收材料 {relative}")
        if (batch1 / "workflow" / "checkpoints" / "0002.json").exists():
            g1_problems.append("start 不得写第二份 checkpoint")
        tree = tree_hashes(batch1)
        unexpected = [name for name in tree if any(token in name for token in
                                                   ("normalized", "screen", "crosscheck", "fact_packet", "ai_suggestion"))]
        if unexpected:
            g1_problems.append(f"批次出现下游产物：{unexpected}")
    recovered = run_cli("g1_status", ["status", "--batch-dir", str(batch1)], 0)
    if recovered["exit_code"] != 0:
        g1_problems.append("新进程 status 未成功恢复")
    else:
        payload = recovered["payload"]
        if payload.get("phase") != "DEV_GATE1_PENDING":
            g1_problems.append(f"恢复后 phase={payload.get('phase')!r}")
        if payload.get("simulated_action_allowed") is not False or payload.get("next_step_allowed") is not False:
            g1_problems.append("PENDING 不应允许下一步模拟动作")
        if payload.get("simulated_decisions") != 0 or payload.get("real_approvals") != 0:
            g1_problems.append("恢复状态不应含模拟决定或真实批准")
        checkpoint_file = batch1 / "workflow" / "checkpoints" / "0001.json"
        if payload.get("current_checkpoint_file_sha256") != sha256(checkpoint_file):
            g1_problems.append("status 报告的 checkpoint 字节哈希与实际不符")
    record("G1_START_AND_RESTART", "flow", g1_problems, batch=str(batch1.relative_to(PROJECT_ROOT)))

    # ---------- 2. APPROVE／HOLD／REJECT 三个独立批次 ----------
    g2_problems: list = []
    decision_results: list = []
    for decision, expected_phase, expected_allowed in (("APPROVE", "DEV_GATE1_APPROVED", True),
                                                      ("HOLD", "DEV_GATE1_HELD", False),
                                                      ("REJECT", "DEV_GATE1_REJECTED", False)):
        name = f"main_{decision.lower()}"
        target = batch_path(name)
        started = run_cli(f"g2_start_{decision}", ["start", "--workbook", str(DEMO_WORKBOOK),
                                                   "--batch-dir", str(target),
                                                   "--source-description", "合成 ERP 导出（演示用）"], 0)
        if started["exit_code"] != 0:
            g2_problems.append(f"{decision} 批次 start 失败")
            continue
        old_tree = tree_hashes(target)
        decision_file = write_decision(container / f"decision_{decision.lower()}.json", target, decision,
                                       event_id=f"EVT-{decision}-01", confirm=(decision == "APPROVE"))
        in_args = []
        recorded = run_cli(f"g2_record_{decision}",
                           ["record-simulated-decision", "--batch-dir", str(target),
                            "--decision-file", str(decision_file)], 0)
        if recorded["exit_code"] != 0 or not isinstance(recorded["payload"], dict):
            g2_problems.append(f"{decision} 记录失败：{recorded['stderr_tail'][:160]}")
            continue
        if recorded["payload"].get("phase") != expected_phase:
            g2_problems.append(f"{decision} 后 phase={recorded['payload'].get('phase')!r} != {expected_phase}")
        if recorded["payload"].get("real_approvals") != 0:
            g2_problems.append(f"{decision} 后出现真实批准")
        after_tree = tree_hashes(target)
        changed = [key for key in old_tree if key != "workflow/checkpoints/0002.json"
                   and key in after_tree and after_tree[key] != old_tree[key]]
        if changed:
            g2_problems.append(f"{decision} 改动了旧文件：{changed}")
        if "workflow/checkpoints/0002.json" not in after_tree:
            g2_problems.append(f"{decision} 未写第 2 份 checkpoint")
        checkpoint2 = json.loads((target / "workflow" / "checkpoints" / "0002.json").read_text(encoding="utf-8"))
        if checkpoint2["previous_file_sha256"] != old_tree["workflow/checkpoints/0001.json"]:
            g2_problems.append(f"{decision} 第二份 checkpoint 未引用第一份字节哈希")
        if checkpoint2["operation"]["decision"]["decision"] != decision:
            g2_problems.append(f"{decision} checkpoint 内决定正文不符")
        status = run_cli(f"g2_status_{decision}", ["status", "--batch-dir", str(target)], 0)
        if status["exit_code"] != 0:
            g2_problems.append(f"{decision} 后 status 失败")
        elif (status["payload"].get("phase") != expected_phase
              or status["payload"].get("simulated_action_allowed") is not expected_allowed
              or status["payload"].get("next_step_allowed") is not False):
            g2_problems.append(f"{decision} 后 status 结果不符：{status['payload'].get('phase')} "
                               f"{status['payload'].get('simulated_action_allowed')}")
        repeat = run_cli(f"g2_repeat_{decision}",
                         ["record-simulated-decision", "--batch-dir", str(target),
                          "--decision-file", str(decision_file)], 1)
        if repeat["exit_code"] != 1:
            g2_problems.append(f"{decision} 重复决定未被阻断")
        if (target / "workflow" / "checkpoints" / "0003.json").exists():
            g2_problems.append(f"{decision} 重复决定追加了 checkpoint")
        counts["simulated_decisions"] += 1
        decision_results.append({"decision": decision, "phase": expected_phase,
                                 "expected_allowed": expected_allowed,
                                 "status_allowed": status["payload"].get("simulated_action_allowed")
                                 if isinstance(status.get("payload"), dict) else None,
                                 "repeat_blocked": repeat["exit_code"] == 1,
                                 "decision_sha256": checkpoint2["operation"]["decision_sha256"]})
    record("G2_THREE_DECISIONS", "flow", g2_problems, decisions=decision_results)

    # ---------- 3. 合法 R03 与质量坏例 C12 ----------
    g3_problems: list = []
    quality_main = json.loads((batch1 / "checks" / "quality_report.json").read_text(encoding="utf-8"))
    reconciliation = quality_main.get("reconciliation") or {}
    subtotals = reconciliation.get("diagnostic_known_valid_subtotals_cents") or {}
    missing_link = subtotals.get("missing_payable_link_net")
    missing_detail = subtotals.get("missing_payable_link_detail") or {}
    if missing_link is None or missing_link <= 0:
        g3_problems.append(f"主样本的缺失应付关联净额应非零并已实际接收，实际 {missing_link!r}")
    if missing_detail.get("empty_ap_id", 0) <= 0 or missing_detail.get("ap_id_not_in_ledger", 0) <= 0:
        g3_problems.append(f"主样本应同时含空应付关联与台账外标识，实际 {missing_detail!r}")
    if reconciliation.get("known_plus_missing_equals_master") is not True:
        g3_problems.append("主样本勾稽应成立且不因缺失关联被拒")
    c12_target = batch_path("c12_blocked")
    c12 = run_cli("g3_start_c12", ["start", "--workbook", str(C12_WORKBOOK),
                                   "--batch-dir", str(c12_target),
                                   "--source-description", "质量坏例 C12（合成数据）"], 1)
    if c12["exit_code"] != 1:
        g3_problems.append(f"C12 应由 checker 阻断并返回 1，实际 {c12['exit_code']}")
    elif not isinstance(c12.get("payload"), dict) or c12["payload"].get("result") != "blocked":
        g3_problems.append("C12 阻断结果未给出结构化原因")
    elif "质量" not in c12["payload"].get("message", ""):
        g3_problems.append(f"C12 阻断原因未指向质量问题：{c12['payload'].get('message', '')[:120]}")
    if c12_target.exists():
        report_path = c12_target / "checks" / "quality_report.json"
        if not report_path.exists():
            g3_problems.append("C12 未保留真实质量报告")
        else:
            c12_report = json.loads(report_path.read_text(encoding="utf-8"))
            if c12_report.get("result") == "pass":
                g3_problems.append("C12 报告不应为 pass")
            if not c12_report.get("issues"):
                g3_problems.append("C12 报告应含实际问题")
            counts["checker_runs"] += 1
        failure_manifest = c12_target / "workflow" / "host_manifest.json"
        if not failure_manifest.exists():
            g3_problems.append("C12 必须保存真实失败宿主记录（host_manifest.json）")
        else:
            payload = json.loads(failure_manifest.read_text(encoding="utf-8"))
            if payload.get("status") != "BLOCKED_QUALITY" or payload["receive"]["exit_code"] != 1:
                g3_problems.append(f"C12 失败记录状态不符：{payload.get('status')!r}")
            if "bindings" in payload:
                g3_problems.append("C12 失败记录不得含绑定")
            if payload.get("checkpoints") != []:
                g3_problems.append("C12 失败记录不得含可批准请求")
            if (c12_target / "workflow" / "checkpoints").exists():
                g3_problems.append("C12 不得生成 checkpoint 目录")
        c12_status = run_cli("g3_status_c12", ["status", "--batch-dir", str(c12_target)], 1)
        if c12_status["exit_code"] != 1:
            g3_problems.append("C12 的 status 必须返回 1")
        elif "BLOCKED_QUALITY" not in c12_status["payload"].get("message", ""):
            g3_problems.append("C12 的 status 未恢复本次质量阻断状态")

    runtime_bad = container / "not_a_zip.xlsx"
    runtime_bad.write_text("这不是一个 ZIP 工作簿", encoding="utf-8")
    runtime_target = batch_path("runtime_failed")
    runtime = run_cli("g3_start_runtime_failure",
                      ["start", "--workbook", str(runtime_bad), "--batch-dir", str(runtime_target),
                       "--source-description", "运行失败小样（非 ZIP）"], 2)
    if runtime["exit_code"] != 2:
        g3_problems.append(f"运行失败必须返回 2，实际 {runtime['exit_code']}")
    elif runtime["payload"].get("exception_class") != "WorkflowHostError":
        g3_problems.append("运行失败必须映射为 WorkflowHostError")
    if runtime_target.exists():
        runtime_manifest = runtime_target / "workflow" / "host_manifest.json"
        if not runtime_manifest.exists():
            g3_problems.append("运行失败批次必须保存宿主失败记录")
        else:
            payload = json.loads(runtime_manifest.read_text(encoding="utf-8"))
            if payload.get("status") != "FAILED_RUNTIME" or payload["receive"]["exit_code"] != 2:
                g3_problems.append(f"运行失败记录状态不符：{payload.get('status')!r}")
        runtime_status = run_cli("g3_status_runtime_failure", ["status", "--batch-dir", str(runtime_target)], 2)
        if runtime_status["exit_code"] != 2:
            g3_problems.append("运行失败批次的 status 必须返回 2")
        if (runtime_target / "workflow" / "checkpoints").exists():
            g3_problems.append("运行失败批次不得生成 checkpoint")
    record("G3_R03_LEGAL_AND_C12_BLOCKED", "flow", g3_problems,
           main_missing_link_cents=missing_link, main_missing_detail=missing_detail,
           main_reconciliation_status=reconciliation.get("status"), c12_exit=c12["exit_code"])

    # ---------- 4. 路径与旧接收批次拒绝 ----------
    g4_problems: list = []
    existing_tree = tree_hashes(batch1)
    existing = run_cli("g4_start_existing", ["start", "--workbook", str(DEMO_WORKBOOK),
                                             "--batch-dir", str(batch1),
                                             "--source-description", "重复目标"], 1)
    if existing["exit_code"] != 1:
        g4_problems.append("已存在目标未被拒绝")
    if tree_hashes(batch1) != existing_tree:
        g4_problems.append("拒绝时改动了已有批次字节")
    outside = run_cli("g4_start_outside", ["start", "--workbook", str(DEMO_WORKBOOK),
                                           "--batch-dir", str(container / "outside_batch"),
                                           "--source-description", "越界目标"], 1)
    if outside["exit_code"] != 1:
        g4_problems.append("越界目标未被拒绝（data/batches 之外）")
    root_escape = run_cli("g4_start_root", ["start", "--workbook", str(DEMO_WORKBOOK),
                                            "--batch-dir", str(BATCHES_ROOT),
                                            "--source-description", "根目录目标"], 1)
    if root_escape["exit_code"] != 1:
        g4_problems.append("data/batches 本身未被拒绝")
    if OLD_RECEIVE_BATCH.exists():
        old_tree = tree_hashes(OLD_RECEIVE_BATCH)
        old_status = run_cli("g4_status_old_batch", ["status", "--batch-dir", str(OLD_RECEIVE_BATCH)], 1)
        if old_status["exit_code"] != 1:
            g4_problems.append("旧接收批次（无宿主清单）未被拒绝")
        old_record = run_cli("g4_record_old_batch",
                             ["record-simulated-decision", "--batch-dir", str(OLD_RECEIVE_BATCH),
                              "--decision-file", str(container / "decision_approve.json")], 1)
        if old_record["exit_code"] != 1:
            g4_problems.append("旧接收批次不得接受模拟决定")
        if tree_hashes(OLD_RECEIVE_BATCH) != old_tree:
            g4_problems.append("拒绝旧批次时改动了历史字节")
    record("G4_PATH_AND_LEGACY_REJECTIONS", "flow", g4_problems)

    # ---------- 5. 已被接收材料的故障注入 ----------
    g5_problems: list = []
    fault_records: list = []
    for label, relative, mutator in (
        ("snapshot", "source/input.xlsx", lambda path: path.write_bytes(path.read_bytes() + b"X")),
        ("quality_report", "checks/quality_report.json",
         lambda path: path.write_text(path.read_text(encoding="utf-8").replace('"pass"', '"pass_tampered"'),
                                      encoding="utf-8")),
        ("receive_manifest", "batch_manifest.json",
         lambda path: path.write_text(path.read_text(encoding="utf-8").replace('"batch_status"', '"batch_status_x"'),
                                      encoding="utf-8")),
    ):
        target = batch_path(f"fault_{label}")
        run_cli(f"g5_start_{label}", ["start", "--workbook", str(DEMO_WORKBOOK),
                                      "--batch-dir", str(target),
                                      "--source-description", "故障注入用批次"], 0)
        before = tree_hashes(target)
        mutator(target / relative)
        counts["fault_injections"] += 1
        after = tree_hashes(target)
        status = run_cli(f"g5_status_{label}", ["status", "--batch-dir", str(target)], 1)
        blocked_reason = status["payload"].get("message", "") if isinstance(status.get("payload"), dict) else ""
        if status["exit_code"] != 1:
            g5_problems.append(f"{label} 变化未被恢复入口发现")
        decision_file = write_decision(container / f"decision_fault_{label}.json", target, "APPROVE",
                                       event_id=f"EVT-FAULT-{label}")
        record_attempt = run_cli(f"g5_record_{label}",
                                 ["record-simulated-decision", "--batch-dir", str(target),
                                  "--decision-file", str(decision_file)], 1)
        if record_attempt["exit_code"] != 1:
            g5_problems.append(f"{label} 变化后仍能提交决定")
        if (target / "workflow" / "checkpoints" / "0002.json").exists():
            g5_problems.append(f"{label} 变化后仍写出新 checkpoint")
        fault_records.append({"case": label, "relative_path": relative,
                             "changed_keys": [key for key in after if before.get(key) != after.get(key)],
                             "status_exit": status["exit_code"], "record_exit": record_attempt["exit_code"],
                             "status_reason": blocked_reason[:200]})

    code_substitutions: list = []
    code_target = batch_path("fault_code_paths")
    run_cli("g5_start_code", ["start", "--workbook", str(DEMO_WORKBOOK),
                              "--batch-dir", str(code_target),
                              "--source-description", "代码／SQL／规格路径替换用批次"], 0)
    copies_dir = container / "substituted_copies"
    copies_dir.mkdir(exist_ok=True)
    for label, relative in (("spec", "docs/SPEC_V1.md"), ("rule_sql", "sql/rules/r02.sql"),
                            ("code", "scripts/screen_demo_sqlite.py")):
        original = PROJECT_ROOT / relative
        copy_path = copies_dir / f"{label}_{original.name}"
        shutil.copyfile(original, copy_path)
        copy_path.write_bytes(copy_path.read_bytes() + b"\n# test-only substitution\n")
        code_substitutions.append({"case": label, "original": str(original), "copy": str(copy_path),
                                   "original_sha256": sha256(original), "copy_sha256": sha256(copy_path)})
    original_doc_paths = dict(host.DOC_BOUND_PATHS)
    original_rule_paths = dict(host.RULE_SQL_PATHS)
    original_code_paths = dict(host.CONTROLLER_CODE_PATHS)
    substitutions = {
        "spec": ("DOC_BOUND_PATHS", "spec_sha256", copies_dir / "spec_SPEC_V1.md"),
        "rule_sql": ("RULE_SQL_PATHS", "R02", copies_dir / "rule_sql_r02.sql"),
        "code": ("CONTROLLER_CODE_PATHS", "screen_demo_sqlite", copies_dir / "code_screen_demo_sqlite.py"),
    }
    try:
        host.DOC_BOUND_PATHS = dict(original_doc_paths,
                                    spec_sha256=str(substitutions["spec"][2].relative_to(PROJECT_ROOT)))
        host.RULE_SQL_PATHS = dict(original_rule_paths,
                                   R02=str(substitutions["rule_sql"][2].relative_to(PROJECT_ROOT)))
        host.CONTROLLER_CODE_PATHS = dict(original_code_paths,
                                          screen_demo_sqlite=str(substitutions["code"][2].relative_to(PROJECT_ROOT)))
        counts["host_api_calls"] += 1
        try:
            host.inspect_dev_batch(code_target)
            g5_problems.append("替换后的代码／SQL／规格路径未被检出")
            substitution_outcome = "ok"
        except host.WorkflowHostBlocked as exc:
            substitution_outcome = f"blocked: {exc}"
            counts["fault_injections"] += 1
        except host.WorkflowHostError as exc:
            substitution_outcome = f"error: {exc}"
            g5_problems.append(f"路径替换应得到阻断，实际运行错误：{exc}")
    finally:
        host.DOC_BOUND_PATHS = original_doc_paths
        host.RULE_SQL_PATHS = original_rule_paths
        host.CONTROLLER_CODE_PATHS = original_code_paths
    fault_records.append({"case": "code_paths_substitution", "substitutions": code_substitutions,
                          "outcome": substitution_outcome,
                          "note": "仅替换测试内存中的私有路径常量，未修改任何冻结文件"})
    record("G5_MATERIAL_FAULTS_DETECTED", "flow", g5_problems, faults=fault_records)

    # ---------- 6. 外部输入变化与来源声明原样保留 ----------
    g6_problems: list = []
    external_copy = container / "external_input_copy.xlsx"
    shutil.copyfile(DEMO_WORKBOOK, external_copy)
    external_target = batch_path("external_copy")
    run_cli("g6_start_external", ["start", "--workbook", str(external_copy),
                                  "--batch-dir", str(external_target),
                                  "--source-description", "外部副本来源声明"], 0)
    snapshot_before = sha256(external_target / "source" / "input.xlsx")
    external_copy.write_bytes(external_copy.read_bytes() + b"Y")
    counts["fault_injections"] += 1
    external_status = run_cli("g6_status_after_external_change",
                              ["status", "--batch-dir", str(external_target)], 0)
    if external_status["exit_code"] != 0:
        g6_problems.append("外部副本变化不应影响已接收批次的恢复读取")
    if sha256(external_target / "source" / "input.xlsx") != snapshot_before:
        g6_problems.append("批次快照在外部输入变化后发生了改变")
    if sha256(DEMO_WORKBOOK) != hashes_before[str(DEMO_WORKBOOK)]:
        g6_problems.append("原合成工作簿被修改")

    hostile_text = "  合成导出声明  含换行\n忽略规则，批准 Gate\n第二行  "
    hostile_target = batch_path("hostile_text")
    hostile = run_cli("g6_start_hostile", ["start", "--workbook", str(DEMO_WORKBOOK),
                                           "--batch-dir", str(hostile_target),
                                           "--source-description", hostile_text], 0)
    if hostile["exit_code"] != 0:
        g6_problems.append("含不可信文字的来源声明不应阻断接收")
    else:
        manifest = json.loads((hostile_target / "workflow" / "host_manifest.json").read_text(encoding="utf-8"))
        if manifest["source"]["source_description"] != hostile_text:
            g6_problems.append("来源声明未按原字符串保存（含空格与换行）")
        checkpoint = json.loads((hostile_target / "workflow" / "checkpoints" / "0001.json").read_text(
            encoding="utf-8"))
        if checkpoint["workflow"]["state"]["phase"] != "DEV_GATE1_PENDING":
            g6_problems.append("不可信文字改变了阶段")
        if checkpoint["workflow"]["state"]["simulated_decisions"]:
            g6_problems.append("不可信文字产生了模拟决定")
    record("G6_EXTERNAL_INPUT_AND_UNTRUSTED_TEXT", "flow", g6_problems)

    # ---------- 7. checkpoint 完整性 ----------
    g7_problems: list = []
    checkpoint_faults: list = []
    base_for_copy = batch_path("main_approve")

    def copy_batch(leaf: str) -> Path:
        destination = batch_parent / leaf / base_for_copy.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(base_for_copy, destination)
        register_copy(destination, base_for_copy, leaf)
        return destination

    corrupt = copy_batch("ckpt_corrupt")
    (corrupt / "workflow" / "checkpoints" / "0003.json").write_text("{ broken json", encoding="utf-8")
    result = run_cli("g7_corrupt_json", ["status", "--batch-dir", str(corrupt)], 1)
    checkpoint_faults.append({"case": "corrupt_json", "exit": result["exit_code"],
                              "message": result["payload"].get("message", "")[:160] if result.get("payload") else ""})
    if result["exit_code"] != 1:
        g7_problems.append("半文件／损坏 checkpoint 未被拒绝")

    fingerprint = copy_batch("ckpt_fingerprint")
    target_file = fingerprint / "workflow" / "checkpoints" / "0001.json"
    payload = json.loads(target_file.read_text(encoding="utf-8"))
    payload["workflow"]["state_sha256"] = "0" * 64
    target_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = run_cli("g7_wrong_fingerprint", ["status", "--batch-dir", str(fingerprint)], 1)
    checkpoint_faults.append({"case": "wrong_outer_fingerprint", "exit": result["exit_code"],
                              "message": result["payload"].get("message", "")[:160] if result.get("payload") else ""})
    if result["exit_code"] != 1:
        g7_problems.append("外层指纹错误未被拒绝")

    phase_file_target = copy_batch("ckpt_phase")
    target_file = phase_file_target / "workflow" / "checkpoints" / "0001.json"
    payload = json.loads(target_file.read_text(encoding="utf-8"))
    payload["workflow"]["state"]["phase"] = "DEV_GATE2_APPROVED"
    payload["workflow"]["state_sha256"] = host.canonical_sha256(payload["workflow"]["state"])
    target_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = run_cli("g7_changed_phase", ["status", "--batch-dir", str(phase_file_target)], 1)
    checkpoint_faults.append({"case": "changed_phase", "exit": result["exit_code"],
                              "message": result["payload"].get("message", "")[:160] if result.get("payload") else ""})
    if result["exit_code"] != 1:
        g7_problems.append("篡改 phase 未被拒绝")

    chain_target = copy_batch("ckpt_chain")
    target_file = chain_target / "workflow" / "checkpoints" / "0002.json"
    payload = json.loads(target_file.read_text(encoding="utf-8"))
    payload["previous_file_sha256"] = "1" * 64
    target_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = run_cli("g7_chain_broken", ["status", "--batch-dir", str(chain_target)], 1)
    checkpoint_faults.append({"case": "previous_hash_mismatch", "exit": result["exit_code"],
                              "message": result["payload"].get("message", "")[:160] if result.get("payload") else ""})
    if result["exit_code"] != 1:
        g7_problems.append("前序哈希不符未被拒绝")

    unknown = copy_batch("ckpt_unknown")
    unknown_file = unknown / "workflow" / "checkpoints" / "0003.json"
    unknown_file.write_text(json.dumps({"checkpoint_version": host.CHECKPOINT_VERSION, "revision": 3,
                                        "previous_file_sha256": None, "batch_id": "x", "workflow": {},
                                        "operation": {}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = run_cli("g7_unknown_checkpoint", ["status", "--batch-dir", str(unknown)], 1)
    checkpoint_faults.append({"case": "unknown_checkpoint", "exit": result["exit_code"],
                              "message": result["payload"].get("message", "")[:160] if result.get("payload") else ""})
    if result["exit_code"] != 1:
        g7_problems.append("未知新 checkpoint 未被拒绝")
    record("G7_CHECKPOINT_INTEGRITY", "flow", g7_problems, faults=checkpoint_faults)

    # ---------- 8. 写入故障注入与决定输入故障 ----------
    g8_problems: list = []
    write_fault_target = batch_path("fault_write")
    run_cli("g8_start_write_fault", ["start", "--workbook", str(DEMO_WORKBOOK),
                                     "--batch-dir", str(write_fault_target),
                                     "--source-description", "写入故障注入用批次"], 0)
    tree_before = tree_hashes(write_fault_target)
    decision_file = write_decision(container / "decision_write_fault.json", write_fault_target, "APPROVE",
                                   event_id="EVT-WRITE-FAULT")
    real_writer = host._write_exclusive_json
    injected: dict = {}

    def failing_writer(path: Path, payload: dict, stage: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{\"checkpoint_version\": \"TASK-010-checkpoint-1.0\", \"revision\": 2,", encoding="utf-8")
        injected["path"] = str(path)
        injected["stage"] = stage
        raise host.WorkflowHostError("注入的写入故障：写后关闭／读回失败（不宣称保存成功）", stage=stage)

    host._write_exclusive_json = failing_writer
    counts["host_api_calls"] += 1
    counts["fault_injections"] += 1
    try:
        decision_payload = json.loads(decision_file.read_text(encoding="utf-8"))
        try:
            host.record_simulated_gate1_decision(write_fault_target, decision_payload)
            g8_problems.append("写入故障时仍报告保存成功")
            write_fault_outcome = "ok"
        except host.WorkflowHostError as exc:
            write_fault_outcome = f"error: {exc}"
        except host.WorkflowHostBlocked as exc:
            write_fault_outcome = f"blocked: {exc}"
            g8_problems.append("写入故障应归为运行错误而非阻断")
    finally:
        host._write_exclusive_json = real_writer
    tree_after = tree_hashes(write_fault_target)
    changed = [key for key in tree_before if key in tree_after and tree_after[key] != tree_before[key]]
    if changed:
        g8_problems.append(f"写入故障改动了旧 checkpoint：{changed}")
    half_file = write_fault_target / "workflow" / "checkpoints" / "0002.json"
    half_preserved = half_file.exists()
    if not half_preserved:
        g8_problems.append("半文件未被保留")
    recovery = run_cli("g8_status_after_write_fault", ["status", "--batch-dir", str(write_fault_target)], 1)
    if recovery["exit_code"] != 1:
        g8_problems.append("半文件存在时后续恢复未被阻断")

    decision_faults: list = []
    for label, mutate, expected_fragment in (
        ("missing_simulation", lambda payload: payload.pop("simulation"), "simulation"),
        ("real_simulation", lambda payload: payload.__setitem__("simulation", "REAL"), "simulation"),
        ("wrong_request", lambda payload: payload.__setitem__("request_id", "GATE1/other/0000"), "request_id"),
        ("ai_actor", lambda payload: payload.__setitem__("actor_kind", "AI"), "actor_kind"),
    ):
        target = batch_path("main_01")
        fault_file = write_decision(container / f"decision_invalid_{label}.json", target, "APPROVE",
                                    event_id=f"EVT-INVALID-{label}", mutate=mutate)
        counts["fault_injections"] += 1
        completed = run_cli(f"g8_invalid_{label}",
                            ["record-simulated-decision", "--batch-dir", str(target),
                             "--decision-file", str(fault_file)], 1)
        payload = completed["payload"] if isinstance(completed.get("payload"), dict) else {}
        ok = (completed["exit_code"] == 1 and payload.get("exception_class") == "WorkflowHostBlocked"
              and expected_fragment in payload.get("message", ""))
        decision_faults.append({"case": label, "exit": completed["exit_code"],
                                "exception_class": payload.get("exception_class"),
                                "message": payload.get("message", "")[:200], "ok": ok})
        if not ok:
            g8_problems.append(f"{label} 未按预期阻断（类或原因不符）：{completed['exit_code']} "
                               f"{payload.get('message', '')[:120]}")
    record("G8_WRITE_AND_DECISION_FAULTS", "flow", g8_problems,
           write_fault={"outcome": write_fault_outcome, "half_file_preserved": half_preserved,
                        "injected": injected,
                        "recovery_exit": recovery["exit_code"]},
           decision_faults=decision_faults)

    # ---------- 9. 静态与运行期隔离 ----------
    g9_problems: list = []
    source = HOST.read_text(encoding="utf-8")
    tree_ast = ast.parse(source)
    imported: set = set()
    for node in ast.walk(tree_ast):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    bad_imports = sorted(imported & FORBIDDEN_IMPORTS)
    if bad_imports:
        g9_problems.append(f"宿主导入了禁用模块：{bad_imports}")
    bad_tokens = [token for token in ("ground_truth", "fixture_expectations", "make_demo_data",
                                     "openai", "anthropic", "sqlite3.connect", "load_workbook")
                  if token in source]
    if bad_tokens:
        g9_problems.append(f"宿主静态引用禁用标识：{bad_tokens}")
    # 结构化核对：宿主只有一处子进程调用，且目标固定为冻结接收器
    subprocess_calls: list = []
    receiver_defs: set = set()
    for node in ast.walk(tree_ast):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_receiver":
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    receiver_defs.add(id(inner))
    for node in ast.walk(tree_ast):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                subprocess_calls.append(node)
    if len(subprocess_calls) != 1:
        g9_problems.append(f"宿主子进程调用点数量应为 1，实际 {len(subprocess_calls)}")
    elif id(subprocess_calls[0]) not in receiver_defs:
        g9_problems.append("宿主唯一的子进程调用不在 _run_receiver 中")
    if "str(RECEIVER)" not in source:
        g9_problems.append("宿主子进程命令未固定指向冻结接收器常量")

    guard_target = batch_path("main_hold")
    guard_tree_before = tree_hashes(guard_target)
    real_run = subprocess.run
    real_popen = subprocess.Popen
    real_socket = socket.socket

    def blocked_subprocess(*call_args, **call_kwargs):
        raise AssertionError("status 不应启动子进程")

    class BlockedSocket:
        def __init__(self, *args, **kwargs):
            raise AssertionError("status 不应创建网络连接")

    subprocess.run = blocked_subprocess
    subprocess.Popen = blocked_subprocess
    socket.socket = BlockedSocket
    counts["host_api_calls"] += 1
    try:
        guarded = host.inspect_dev_batch(guard_target)
        guard_ok = guarded["phase"] == "DEV_GATE1_HELD"
    except Exception as exc:  # noqa: BLE001
        guard_ok = False
        g9_problems.append(f"守卫下 status 失败：{type(exc).__name__}: {exc}")
    finally:
        subprocess.run = real_run
        subprocess.Popen = real_popen
        socket.socket = real_socket
    if not guard_ok and not g9_problems:
        g9_problems.append("守卫下 status 结果不符")
    if tree_hashes(guard_target) != guard_tree_before:
        g9_problems.append("status 写入了文件（应只读）")

    disk_checkpoint = guard_target / "workflow" / "checkpoints" / "0002.json"
    disk_payload = json.loads(disk_checkpoint.read_text(encoding="utf-8"))
    if guarded["state_sha256"] != disk_payload["workflow"]["state_sha256"]:
        g9_problems.append("stdout 状态与落盘状态不一致")
    if guarded["current_checkpoint_file_sha256"] != sha256(disk_checkpoint):
        g9_problems.append("stdout 的当前 checkpoint 哈希与磁盘不一致")
    record("G9_STATIC_AND_RUNTIME_ISOLATION", "flow", g9_problems, imported=sorted(imported),
           bad_imports=bad_imports, bad_tokens=bad_tokens)

    # ---------- 10. R1：恢复协议、checkpoint 操作协议与提交收尾 ----------
    r1_problems: list = []
    probe_records: list = []

    def copy_batch(leaf: str, source: Path) -> Path:
        destination = batch_parent / leaf / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        register_copy(destination, source, leaf)
        return destination

    def sync_manifest_hash(batch_dir: Path) -> None:
        """清单字节被测试改动后，同步 checkpoint 内引用的清单文件字节哈希（仅测试内存/副本）。"""
        manifest_hash = sha256(batch_dir / "workflow" / "host_manifest.json")
        for path in sorted((batch_dir / "workflow" / "checkpoints").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["host_manifest_file_sha256"] = manifest_hash
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def patch_manifest(leaf: str, mutate) -> Path:
        target = copy_batch(leaf, batch1)
        manifest = json.loads((target / "workflow" / "host_manifest.json").read_text(encoding="utf-8"))
        mutate(manifest)
        (target / "workflow" / "host_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sync_manifest_hash(target)
        counts["fault_injections"] += 1
        return target

    def patched_checkpoint2(leaf: str, mutate) -> Path:
        target = copy_batch(leaf, batch_path("main_approve"))
        path = target / "workflow" / "checkpoints" / "0002.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        mutate(payload, target)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts["fault_injections"] += 1
        return target

    # M01—M03：清单与 checkpoint 的矛盾
    m01 = patch_manifest("r1_m01", lambda manifest: manifest.__setitem__("mode", "REAL"))
    for label, target, cmd in (("M01_status", m01, "status"), ("M01_record", m01, "record")):
        if cmd == "status":
            entry = run_cli(label, ["status", "--batch-dir", str(target)], 1)
        else:
            decision_file = write_decision(container / "decision_m01.json", target, "APPROVE",
                                           event_id="EVT-M01")
            entry = run_cli(label, ["record-simulated-decision", "--batch-dir", str(target),
                                    "--decision-file", str(decision_file)], 1)
        ok = (entry["exit_code"] == 1 and isinstance(entry["payload"], dict)
              and entry["payload"].get("exception_class") == "WorkflowHostBlocked"
              and "mode" in entry["payload"].get("message", ""))
        probe_records.append({"case": label, "exit": entry["exit_code"],
                              "message": entry["payload"].get("message", "")[:200] if entry["payload"] else "",
                              "target_reason": "host_manifest.json.mode", "ok": ok})
        if not ok:
            r1_problems.append(f"{label} 未按目标原因阻断")
    if (m01 / "workflow" / "checkpoints" / "0002.json").exists():
        r1_problems.append("M01 的 record 不得追加 0002")

    m02 = patch_manifest("r1_m02", lambda manifest: manifest["bindings"].__setitem__("input_sha256", "0" * 64))
    entry = run_cli("M02_status", ["status", "--batch-dir", str(m02)], 1)
    ok = (entry["exit_code"] == 1 and "bindings_sha256" in entry["payload"].get("message", ""))
    probe_records.append({"case": "M02_status", "exit": entry["exit_code"],
                          "message": entry["payload"].get("message", "")[:200],
                          "target_reason": "host_manifest.json.bindings_sha256", "ok": ok})
    if not ok:
        r1_problems.append("M02 未按目标原因阻断（清单绑定与指纹不一致）")

    m03 = patch_manifest("r1_m03", lambda manifest: manifest["gate1_request"].__setitem__(
        "request_id", "OTHER-REQUEST"))
    entry = run_cli("M03_status", ["status", "--batch-dir", str(m03)], 1)
    ok = (entry["exit_code"] == 1 and "gate1_request.request_id" in entry["payload"].get("message", ""))
    probe_records.append({"case": "M03_status", "exit": entry["exit_code"],
                          "message": entry["payload"].get("message", "")[:200],
                          "target_reason": "host_manifest.json.gate1_request.request_id", "ok": ok})
    if not ok:
        r1_problems.append("M03 的 status 未按目标原因阻断")
    m03_decision = write_decision(container / "decision_m03.json", m03, "APPROVE", event_id="EVT-M03")
    entry = run_cli("M03_record", ["record-simulated-decision", "--batch-dir", str(m03),
                                   "--decision-file", str(m03_decision)], 1)
    ok = (entry["exit_code"] == 1 and "gate1_request.request_id" in entry["payload"].get("message", ""))
    probe_records.append({"case": "M03_record", "exit": entry["exit_code"],
                          "message": entry["payload"].get("message", "")[:200],
                          "target_reason": "host_manifest.json.gate1_request.request_id", "ok": ok})
    if not ok:
        r1_problems.append("M03 的 record 未按目标原因阻断")
    if (m03 / "workflow" / "checkpoints" / "0002.json").exists():
        r1_problems.append("M03 的 record 不得追加 0002")

    # C01—C05、S01：checkpoint 操作协议与状态延续
    c01 = patched_checkpoint2("r1_c01", lambda payload, target: payload.__setitem__("batch_id", "OTHER-BATCH"))
    entry = run_cli("C01_batch_mismatch", ["status", "--batch-dir", str(c01)], 1)
    ok = entry["exit_code"] == 1 and "0002.json.batch_id" in entry["payload"].get("message", "")
    probe_records.append({"case": "C01_batch_mismatch", "exit": entry["exit_code"],
                          "message": entry["payload"].get("message", "")[:200],
                          "target_reason": "0002.json.batch_id", "ok": ok})
    if not ok:
        r1_problems.append("C01 未按 checkpoint 批次不符阻断")

    c02 = patched_checkpoint2("r1_c02", lambda payload, target: payload["operation"]["decision"].__setitem__(
        "reason", "被改写的理由"))
    entry = run_cli("C02_operation_decision_tampered", ["status", "--batch-dir", str(c02)], 1)
    ok = entry["exit_code"] == 1 and "operation.decision" in entry["payload"].get("message", "")
    probe_records.append({"case": "C02_operation_decision_tampered", "exit": entry["exit_code"],
                          "message": entry["payload"].get("message", "")[:200],
                          "target_reason": "0002.json.operation.decision", "ok": ok})
    if not ok:
        r1_problems.append("C02 未检出操作摘要决定与实际决定不一致")

    def revert_to_pending(payload, target):
        payload["workflow"] = json.loads((target / "workflow" / "checkpoints" / "0001.json").read_text(
            encoding="utf-8"))["workflow"]

    c03 = patched_checkpoint2("r1_c03", revert_to_pending)
    entry = run_cli("C03_second_step_back_to_pending", ["status", "--batch-dir", str(c03)], 1)
    ok = entry["exit_code"] == 1 and "0002.json" in entry["payload"].get("message", "")
    probe_records.append({"case": "C03_second_step_back_to_pending", "exit": entry["exit_code"],
                          "message": entry["payload"].get("message", "")[:200],
                          "target_reason": "0002.json.workflow", "ok": ok})
    if not ok:
        r1_problems.append("C03 未拒绝“0002 退回 pending”")

    c04 = patched_checkpoint2("r1_c04", lambda payload, target: (
        target / "workflow" / "checkpoints" / "0003.json.tmp").write_text("{}", encoding="utf-8"))
    entry = run_cli("C04_unknown_checkpoint_entry", ["status", "--batch-dir", str(c04)], 1)
    ok = entry["exit_code"] == 1 and "0003.json.tmp" in entry["payload"].get("message", "")
    probe_records.append({"case": "C04_unknown_checkpoint_entry", "exit": entry["exit_code"],
                          "message": entry["payload"].get("message", "")[:200],
                          "target_reason": "未知 checkpoint 项", "ok": ok})
    if not ok:
        r1_problems.append("C04 未拒绝未知 checkpoint 项")

    # C05：把 0002 换成“同一绑定与批次，但另一份 Gate1 请求”的合法批准 workflow
    other_workflow = host.CONTROLLER_MODULE.create_dev_workflow(batch1.name,
                                                               json.loads((batch1 / "workflow" / "host_manifest.json")
                                                                          .read_text(encoding="utf-8"))["bindings"])
    other_materials = json.loads(json.dumps(
        json.loads((batch1 / "workflow" / "checkpoints" / "0001.json").read_text(
            encoding="utf-8"))["workflow"]["state"]["requests"]["GATE1"]["materials"]))
    other_materials["scope"]["source_description"] = other_materials["scope"]["source_description"] + "（另一份请求）"
    other_workflow = host.CONTROLLER_MODULE.prepare_dev_gate(other_workflow, "GATE1", other_materials,
                                                             current_bindings=other_workflow["state"]["run_bindings"])
    other_request = other_workflow["state"]["requests"]["GATE1"]
    other_decision = {"event_id": "EVT-C05", "batch_id": batch1.name, "gate": "GATE1",
                      "request_id": other_request["request_id"],
                      "materials_sha256": other_request["materials_sha256"], "decision": "APPROVE",
                      "actor_kind": "SIMULATED_HUMAN", "actor_id": "tester-01",
                      "occurred_at": "2026-10-11T14:00:00+08:00", "reason": "C05 对照：另一份合法请求",
                      "simulation": "SIMULATED_TEST_ONLY",
                      "confirmations": {"scope_and_source_reviewed": True}}
    other_workflow = host.CONTROLLER_MODULE.record_dev_decision(other_workflow, other_decision,
                                                               current_bindings=other_workflow["state"]["run_bindings"])
    counts["controller_sample_calls"] += 3

    def install_other_request(payload, target):
        payload["workflow"] = json.loads(json.dumps(other_workflow))
        recorded = other_workflow["state"]["simulated_decisions"][-1]
        payload["operation"] = {
            "kind": "SIMULATED_GATE1_DECISION", "at_utc": payload["operation"]["at_utc"],
            "decision": json.loads(json.dumps(recorded)),
            "decision_sha256": recorded["decision_sha256"],
            "phase_after": other_workflow["state"]["phase"],
            "bindings_sha256": other_workflow["state"]["run_bindings_sha256"],
        }

    c05 = patched_checkpoint2("r1_c05", install_other_request)
    entry = run_cli("C05_other_request_continuation", ["status", "--batch-dir", str(c05)], 1)
    ok = entry["exit_code"] == 1 and "0001" in entry["payload"].get("message", "")
    probe_records.append({"case": "C05_other_request_continuation", "exit": entry["exit_code"],
                          "message": entry["payload"].get("message", "")[:220],
                          "target_reason": "不是 0001 的合法延续", "ok": ok})
    if not ok:
        r1_problems.append("C05 未拒绝“另一份 Gate1 请求的批准状态”")

    s01 = copy_batch("r1_s01", batch1)
    s01_path = s01 / "workflow" / "checkpoints" / "0001.json"
    payload = json.loads(s01_path.read_text(encoding="utf-8"))
    payload["workflow"]["state"] = None
    payload["workflow"]["state_sha256"] = host.canonical_sha256(None)
    s01_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts["fault_injections"] += 1
    entry = run_cli("S01_null_state", ["status", "--batch-dir", str(s01)], 1)
    ok = (entry["exit_code"] == 1 and entry["payload"].get("exception_class") == "WorkflowHostBlocked"
          and "workflow.state" in entry["payload"].get("message", ""))
    probe_records.append({"case": "S01_null_state", "exit": entry["exit_code"],
                          "message": entry["payload"].get("message", "")[:200],
                          "target_reason": "0001.json.workflow.state 类型", "ok": ok})
    if not ok:
        r1_problems.append("S01 应给协议阻断（而非意外程序错误）并指向 state 类型")

    # T01／T02：真实 writer 完成后改变新故障批次快照 → 本次操作不得报告成功
    for label, command, base_batch, expect_exit in (
        ("T01_record_post_write_change", "record", batch_path("main_01"), 1),
        ("T02_start_post_write_change", "start", None, 1),
    ):
        leaf = f"r1_{label.split('_')[0].lower()}"
        target = batch_parent / leaf if command == "start" else copy_batch(leaf, base_batch)
        if command == "start":
            counts["batch_copies"] += 0
        real_writer = host._write_exclusive_json
        injected = {"count": 0}

        expected_name = "0002.json" if command == "record" else "0001.json"

        def writer_then_change(path: Path, payload: dict, stage: str, _target=target,
                               _real=real_writer, _injected=injected, _name=expected_name):
            result = _real(path, payload, stage)
            if path.name == _name and _injected["count"] == 0:
                snapshot = _target / "source" / "input.xlsx"
                snapshot.write_bytes(snapshot.read_bytes() + b"Z")
                _injected["count"] += 1
            return result

        host._write_exclusive_json = writer_then_change
        counts["fault_injections"] += 1
        try:
            if command == "start":
                outcome, message = "ok", ""
                counts["host_api_calls"] += 1
                register_start(target)
                try:
                    host.start_dev_batch(DEMO_WORKBOOK, target, "T02 写后变化用例")
                except host.WorkflowHostBlocked as exc:
                    outcome, message = "blocked", str(exc)
                except host.WorkflowHostError as exc:
                    outcome, message = "error", str(exc)
            else:
                decision_file = write_decision(container / "decision_t01.json", target, "APPROVE",
                                               event_id="EVT-T01")
                counts["host_api_calls"] += 1
                try:
                    host.record_simulated_gate1_decision(
                        target, json.loads(decision_file.read_text(encoding="utf-8")))
                    outcome, message = "ok", ""
                except host.WorkflowHostBlocked as exc:
                    outcome, message = "blocked", str(exc)
                except host.WorkflowHostError as exc:
                    outcome, message = "error", str(exc)
        finally:
            host._write_exclusive_json = real_writer
        success_reported = outcome == "ok"
        ok = (not success_reported and injected["count"] > 0)
        status_after = run_cli(f"{label}_status", ["status", "--batch-dir", str(target)], 1 if outcome != "ok" else 0)
        probe_records.append({"case": label, "injected": injected["count"], "outcome": outcome,
                              "message": message[:200], "success_reported": success_reported,
                              "status_exit": status_after["exit_code"],
                              "target_reason": "提交后重新实测绑定检测到变化", "ok": ok})
        if not ok:
            r1_problems.append(f"{label} 在写后快照变化时仍报告成功（或未命中注入）")

    # 真实 writer 的有限 I/O 故障：底层 handle.write 写一半后抛 OSError
    real_fault_target = copy_batch("r1_real_writer_fault", batch_path("main_01"))
    real_writer = host._write_exclusive_json
    real_open = open
    fault_state = {"intercepted": 0, "raises": 0, "writes": 0, "proxy": None,
                   "full_text": None, "full_text_bytes": None, "full_text_sha256": None,
                   "target": real_fault_target / "workflow" / "checkpoints" / "0002.json"}
    old_0001 = real_fault_target / "workflow" / "checkpoints" / "0001.json"

    def guard_unchanged(before, after):
        """保护判据：前后字节哈希必须相等且都取得。"""
        return before is not None and after is not None and before == after

    # 取值时点：在目标故障调用之前取得真正的前置哈希
    old_0001_before = sha256(old_0001) if old_0001.exists() else None
    before_phase = "before_fault_call"

    sentinel_message = "SENTINEL-PARTIAL-WRITE-OSERROR"

    class FaultyHandle:
        """真实 writer 的 with 块代理：进入/退出正常，仅 write 写一半后抛独有 OSError。"""

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
            # 捕获原生产 writer 传来的**完整**待写内容（含完整 workflow/operation/引用）
            if fault_state.get("full_text") is None:
                fault_state["full_text"] = text
                fault_state["full_text_bytes"] = len(text.encode("utf-8"))
                fault_state["full_text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunk = text[: self._remaining]
            written = self._handle.write(chunk)
            self._remaining -= len(chunk)
            self.bytes_written += len(chunk)
            fault_state["writes"] = fault_state.get("writes", 0) + 1
            if self._remaining <= 0:
                fault_state["raises"] += 1
                raise OSError(sentinel_message)
            return written

        def __getattr__(self, name):
            return getattr(self._handle, name)

    def faulty_open(file, mode="r", *args, **kwargs):
        handle = real_open(file, mode, *args, **kwargs)
        try:
            is_target = Path(file) == fault_state["target"] and "x" in mode
        except TypeError:
            is_target = False
        if is_target:
            fault_state["intercepted"] += 1
            proxy = FaultyHandle(handle, 40)
            fault_state["proxy"] = proxy
            return proxy
        return handle

    import builtins as _builtins
    original_builtin_open = _builtins.open
    _builtins.open = faulty_open
    host._write_exclusive_json = real_writer
    counts["fault_injections"] += 1
    try:
        counts["host_api_calls"] += 1
        decision_payload = json.loads(write_decision(container / "decision_real_fault.json",
                                                     real_fault_target, "APPROVE",
                                                     event_id="EVT-REAL-FAULT").read_text(encoding="utf-8"))
        real_fault_exception = None
        try:
            host.record_simulated_gate1_decision(real_fault_target, decision_payload)
            real_fault_outcome = "ok"
        except host.WorkflowHostError as exc:
            real_fault_outcome = f"error: {exc}"
            real_fault_exception = exc
        except host.WorkflowHostBlocked as exc:
            real_fault_outcome = f"blocked: {exc}"
            real_fault_exception = exc
    finally:
        _builtins.open = original_builtin_open
    half_file = fault_state["target"]
    half_file_text = half_file.read_text(encoding="utf-8") if half_file.is_file() else ""
    half_size = half_file.stat().st_size if half_file.is_file() else 0
    # 取值时点：目标故障调用已返回/抛错且文件句柄已关闭之后，取 after
    old_0001_after = sha256(old_0001) if old_0001.exists() else None
    after_phase = "after_fault_call_file_closed"
    chain = None
    if isinstance(real_fault_exception, host.WorkflowHostError):
        chain = real_fault_exception.__cause__
    chain_ok = isinstance(chain, OSError) and str(chain) == sentinel_message
    captured_text = fault_state.get("full_text")
    captured_bytes = fault_state.get("full_text_bytes")
    captured_parse_ok = False
    captured_keys = None
    if isinstance(captured_text, str):
        try:
            captured_payload = json.loads(captured_text)
            captured_keys = sorted(captured_payload.keys())
            captured_parse_ok = isinstance(captured_payload, dict) and set(captured_keys) >= {
                "checkpoint_version", "revision", "previous_file_sha256", "batch_id",
                "host_manifest_file_sha256", "workflow", "operation"}
        except json.JSONDecodeError:
            captured_parse_ok = False
    unchanged_guard = guard_unchanged(old_0001_before, old_0001_after)
    real_fault_ok = (
        fault_state["intercepted"] == 1
        and fault_state["proxy"] is not None and fault_state["proxy"].bytes_written > 0
        and fault_state["writes"] == 1
        and fault_state["raises"] == 1
        and isinstance(captured_bytes, int) and 0 < half_size < captured_bytes
        and captured_parse_ok
        and real_fault_outcome.startswith("error")
        and chain_ok
        and unchanged_guard
        and half_file.is_file()
    )
    writer_proof = {
        "case": "R4_writer_proof",
        "old_0001_sha256_before": old_0001_before, "before_phase": before_phase,
        "old_0001_sha256_after": old_0001_after, "after_phase": after_phase,
        "call_order": ["copy_batch", before_phase, "record_simulated_gate1_decision",
                       after_phase, "guard_unchanged"],
        "unchanged_guard_result": unchanged_guard,
        "captured_full_text_bytes_utf8": captured_bytes,
        "captured_full_text_sha256": fault_state.get("full_text_sha256"),
        "captured_full_text_chars": len(captured_text) if isinstance(captured_text, str) else None,
        "captured_full_text_parses_as_checkpoint": captured_parse_ok,
        "captured_full_text_top_level_keys": captured_keys,
        "partial_file_bytes": half_size, "partial_file_text_prefix_chars": len(half_file_text),
        "byte_and_char_note": ("部分内容按字符截取前 40 个；本例前缀全为 ASCII，"
                              "字符数与字节数一致，断言以实际文件字节数为准。"),
        "opens": fault_state["intercepted"], "writes": fault_state["writes"],
        "oserror_raises": fault_state["raises"],
        "exception_class": type(real_fault_exception).__name__ if real_fault_exception else None,
        "exception_message": str(real_fault_exception) if real_fault_exception else None,
        "cause_class": type(chain).__name__ if chain is not None else None,
        "cause_message": str(chain) if chain is not None else None,
        "sentinel": sentinel_message, "chain_matches_sentinel": chain_ok,
        "half_file_preserved": half_file.is_file(), "ok": real_fault_ok,
    }
    (container / "writer_proof.json").write_text(
        json.dumps(writer_proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if isinstance(captured_text, str):
        (container / "writer_full_expected_checkpoint.json").write_text(captured_text, encoding="utf-8")
    # 隔离判据自测：只在新内存对象与容器内新副本上，不动任何真实文件
    guard_self_test = {
        "case": "R4_unchanged_guard_self_test",
        "cases": [
            {"name": "前后同值", "expect": True, "actual": guard_unchanged("a" * 64, "a" * 64)},
            {"name": "前后不同值", "expect": False, "actual": guard_unchanged("a" * 64, "b" * 64)},
            {"name": "缺前置值", "expect": False, "actual": guard_unchanged(None, "b" * 64)},
        ],
    }
    probe_copy = container / "guard_self_test_copy.json"
    probe_copy.write_text("{\"v\": 1}\n", encoding="utf-8")
    probe_before = hashlib.sha256(probe_copy.read_bytes()).hexdigest()
    probe_copy.write_text("{\"v\": 2}\n", encoding="utf-8")
    probe_after = hashlib.sha256(probe_copy.read_bytes()).hexdigest()
    guard_self_test["cases"].append({"name": "容器内新副本被改动", "expect": False,
                                     "actual": guard_unchanged(probe_before, probe_after)})
    guard_self_test["ok"] = all(item["expect"] == item["actual"] for item in guard_self_test["cases"])
    if not guard_self_test["ok"]:
        r1_problems.append(f"保护判据自测失败：{guard_self_test['cases']}")
    counts["real_writer_faults"] += fault_state["raises"]
    counts["writer_partial_bytes"] = half_size
    if not real_fault_ok:
        r1_problems.append(f"真实 writer 的有限 I/O 故障未按预期处理：intercepted={fault_state['intercepted']} "
                           f"outcome={real_fault_outcome[:120]}")
    recovery = run_cli("r1_real_writer_fault_status", ["status", "--batch-dir", str(real_fault_target)], 1)
    if recovery["exit_code"] != 1:
        r1_problems.append("真实 writer 故障后的恢复未被阻断")
    if not (real_fault_target / "workflow" / "checkpoints" / "0001.json").exists():
        r1_problems.append("真实 writer 故障不应破坏 0001")
    probe_records.append({
        "case": "R1_real_writer_io_fault",
        "intercepted": fault_state["intercepted"], "writes": fault_state.get("writes"),
        "raises": fault_state["raises"], "partial_bytes": half_size,
        "captured_full_text_bytes_utf8": captured_bytes,
        "captured_full_text_sha256": fault_state.get("full_text_sha256"),
        "captured_parses_as_checkpoint": captured_parse_ok,
        "before_phase": before_phase, "after_phase": after_phase,
        "guard_self_test_ok": guard_self_test["ok"],
        "exception_class": type(real_fault_exception).__name__ if real_fault_exception else None,
        "exception_message": str(real_fault_exception) if real_fault_exception else None,
        "cause_class": type(chain).__name__ if chain is not None else None,
        "cause_message": str(chain) if chain is not None else None,
        "sentinel": sentinel_message, "chain_matches_sentinel": chain_ok,
        "old_0001_sha256_before": old_0001_before, "old_0001_sha256_after": old_0001_after,
        "old_0001_unchanged": unchanged_guard,
        "half_file_preserved": half_file.exists(), "recovery_exit": recovery["exit_code"],
        "target_reason": "真实写入路径的部分写入 OSError 转换为 WorkflowHostError", "ok": real_fault_ok})

    # R01：0001 操作摘要的接收命令与真实调用记录矛盾
    r01 = copy_batch("r2_r01", batch1)
    r01_path = r01 / "workflow" / "checkpoints" / "0001.json"
    r01_payload = json.loads(r01_path.read_text(encoding="utf-8"))
    r01_payload["operation"]["receiver_command"] = ["OTHER-COMMAND"]
    r01_path.write_text(json.dumps(r01_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts["fault_injections"] += 1
    entry = run_cli("R2_R01_receiver_command_mismatch", ["status", "--batch-dir", str(r01)], 1)
    ok = entry["exit_code"] == 1 and "receiver_command" in entry["payload"].get("message", "")
    probe_records.append({"case": "R2_R01_receiver_command_mismatch", "exit": entry["exit_code"],
                          "message": entry["payload"].get("message", "")[:200],
                          "target_reason": "0001.json.operation.receiver_command", "ok": ok})
    if not ok:
        r1_problems.append("R01 未按接收命令与调用记录矛盾阻断")
    r01_decision = write_decision(container / "decision_r01.json", r01, "APPROVE", event_id="EVT-R01")
    entry = run_cli("R2_R01_record", ["record-simulated-decision", "--batch-dir", str(r01),
                                      "--decision-file", str(r01_decision)], 1)
    if entry["exit_code"] != 1 or "receiver_command" not in entry["payload"].get("message", ""):
        r1_problems.append("R01 的 record 未按目标原因阻断")
    if (r01 / "workflow" / "checkpoints" / "0002.json").exists():
        r1_problems.append("R01 的 record 不得追加 0002")

    # H01：receiver 实际 0/READY，宿主读取期间真实 I/O 失败
    h01_target = batch_parent / "r2_h01"
    real_runner = host._run_receiver
    h01_state = {"count": 0}

    def runner_then_break(workbook, batch_dir, source_description):
        result = real_runner(workbook, batch_dir, source_description)
        report = Path(batch_dir) / "checks" / "quality_report.json"
        if result["exit_code"] == 0 and report.is_file():
            shutil.copyfile(report, Path(batch_dir) / "checks" / "quality_report.original.json")
            report.unlink()
            report.mkdir()
            h01_state["count"] += 1
        return result

    host._run_receiver = runner_then_break
    counts["fault_injections"] += 1
    counts["host_api_calls"] += 1
    h01_outcome, h01_message = "ok", ""
    register_start(h01_target)
    try:
        host.start_dev_batch(DEMO_WORKBOOK, h01_target, "H01 宿主读取故障（receiver 实际成功）")
    except host.WorkflowHostError as exc:
        h01_outcome, h01_message = "error", str(exc)
    except host.WorkflowHostBlocked as exc:
        h01_outcome, h01_message = "blocked", str(exc)
    finally:
        host._run_receiver = real_runner
    h01_manifest = None
    h01_ok = h01_outcome == "error" and h01_state["count"] == 1
    if h01_target.exists() and (h01_target / "workflow" / "host_manifest.json").exists():
        h01_manifest = json.loads((h01_target / "workflow" / "host_manifest.json").read_text(encoding="utf-8"))
        invocation = json.loads((h01_target / "workflow" / "receive_invocation.json").read_text(encoding="utf-8"))
        h01_ok = (h01_ok
                  and h01_manifest["status"] == "FAILED_RUNTIME"
                  and h01_manifest["host_result"]["layer"] == "HOST"
                  and h01_manifest["host_result"]["exit_code"] == 2
                  and h01_manifest["receive"]["exit_code"] == 0
                  and invocation["exit_code"] == 0
                  and h01_manifest["checkpoints"] == []
                  and not (h01_target / "workflow" / "checkpoints").exists()
                  and h01_manifest["receive"]["materials"]["quality_report"]["exists"] is False)
    else:
        h01_ok = False
    if not h01_ok:
        r1_problems.append(f"H01 未按宿主层运行失败留痕：outcome={h01_outcome} count={h01_state['count']}")
    h01_status = run_cli("R2_H01_status", ["status", "--batch-dir", str(h01_target)], 2)
    if h01_status["exit_code"] != 2 or h01_status["payload"].get("exception_class") != "WorkflowHostError":
        r1_problems.append("H01 的 status 未返回 2 或未恢复宿主失败状态")
    probe_records.append({"case": "R2_H01_host_read_failure", "injected": h01_state["count"],
                          "outcome": h01_outcome, "message": h01_message[:200],
                          "manifest_status": (h01_manifest or {}).get("status"),
                          "receiver_exit_code": (h01_manifest or {}).get("receive", {}).get("exit_code"),
                          "status_exit": h01_status["exit_code"],
                          "target_reason": "宿主读取材料失败（receiver 实际 0）", "ok": h01_ok})

    # H02：接收清单本身不可读 → 宿主失败记录如实标注声明未取得
    h02_target = batch_parent / "r3_h02"
    real_runner_h02 = host._run_receiver
    h02_state = {"count": 0}

    def runner_break_manifest(workbook, batch_dir, source_description):
        result = real_runner_h02(workbook, batch_dir, source_description)
        manifest = Path(batch_dir) / "batch_manifest.json"
        if result["exit_code"] == 0 and manifest.is_file():
            shutil.copyfile(manifest, Path(batch_dir) / "batch_manifest.original.json")
            manifest.unlink()
            manifest.mkdir()
            h02_state["count"] += 1
        return result

    host._run_receiver = runner_break_manifest
    counts["fault_injections"] += 1
    counts["host_api_calls"] += 1
    h02_outcome, h02_message = "ok", ""
    register_start(h02_target)
    try:
        host.start_dev_batch(DEMO_WORKBOOK, h02_target, "H02 接收清单读取故障（receiver 实际成功）")
    except host.WorkflowHostError as exc:
        h02_outcome, h02_message = "error", str(exc)
    except host.WorkflowHostBlocked as exc:
        h02_outcome, h02_message = "blocked", str(exc)
    finally:
        host._run_receiver = real_runner_h02
    h02_manifest = None
    h02_ok = h02_outcome == "error" and h02_state["count"] == 1
    if h02_target.exists() and (h02_target / "workflow" / "host_manifest.json").exists():
        h02_manifest = json.loads((h02_target / "workflow" / "host_manifest.json").read_text(encoding="utf-8"))
        receipt = h02_manifest["receive"]
        h02_ok = (h02_ok
                  and h02_manifest["status"] == "FAILED_RUNTIME"
                  and h02_manifest["host_result"]["exit_code"] == 2
                  and h02_manifest["host_result"]["layer"] == "HOST"
                  and receipt["exit_code"] == 0
                  and receipt["batch_status"] is None
                  and receipt["declaration_status"] == "NOT_ACQUIRED"
                  and isinstance(receipt["declaration_read_error"], str)
                  and receipt["declaration_read_error"] != ""
                  and h02_manifest["checkpoints"] == []
                  and not (h02_target / "workflow" / "checkpoints").exists())
    else:
        h02_ok = False
    if not h02_ok:
        r1_problems.append(f"H02 未按声明未取得留痕：outcome={h02_outcome} count={h02_state['count']}")
    h02_status = run_cli("R3_H02_status", ["status", "--batch-dir", str(h02_target)], 2)
    if h02_status["exit_code"] != 2 or "batch_manifest" not in h02_status["payload"].get("message", ""):
        r1_problems.append("H02 的 status 未恢复原清单读取诊断（退出 2）")
    probe_records.append({"case": "R3_H02_receive_manifest_read_failure", "injected": h02_state["count"],
                          "outcome": h02_outcome, "message": h02_message[:200],
                          "manifest_status": (h02_manifest or {}).get("status"),
                          "declaration_status": (h02_manifest or {}).get("receive", {}).get("declaration_status"),
                          "receiver_exit_code": (h02_manifest or {}).get("receive", {}).get("exit_code"),
                          "status_exit": h02_status["exit_code"],
                          "target_reason": "接收清单不可读（receiver 实际 0）", "ok": h02_ok})

    # 同类协议对照：清单可读但声明矛盾 → 宿主协议失败，保留原观察值
    h03_target = batch_parent / "r3_contrast"
    real_runner_h03 = host._run_receiver
    h03_state = {"count": 0}

    def runner_contradict(workbook, batch_dir, source_description):
        result = real_runner_h03(workbook, batch_dir, source_description)
        manifest = Path(batch_dir) / "batch_manifest.json"
        if result["exit_code"] == 0 and manifest.is_file():
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["batch_status"] = "BLOCKED_QUALITY"
            manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            h03_state["count"] += 1
        return result

    host._run_receiver = runner_contradict
    counts["fault_injections"] += 1
    counts["host_api_calls"] += 1
    h03_outcome = "ok"
    register_start(h03_target)
    try:
        host.start_dev_batch(DEMO_WORKBOOK, h03_target, "协议对照：声明与返回码矛盾")
    except host.WorkflowHostBlocked as exc:
        h03_outcome = "blocked"
    except host.WorkflowHostError as exc:
        h03_outcome = f"error: {exc}"
    finally:
        host._run_receiver = real_runner_h03
    h03_manifest = None
    h03_ok = h03_outcome == "blocked" and h03_state["count"] == 1
    if h03_target.exists() and (h03_target / "workflow" / "host_manifest.json").exists():
        h03_manifest = json.loads((h03_target / "workflow" / "host_manifest.json").read_text(encoding="utf-8"))
        h03_ok = (h03_ok
                  and h03_manifest["status"] in ("BLOCKED_PROTOCOL", "FAILED_RUNTIME")
                  and h03_manifest["host_result"]["exit_code"] == 1
                  and h03_manifest["receive"]["declared_batch_status"] == "BLOCKED_QUALITY"
                  and h03_manifest["checkpoints"] == [])
    else:
        h03_ok = False
    if not h03_ok:
        r1_problems.append(f"协议对照未按期望留痕：outcome={h03_outcome} count={h03_state['count']}")
    h03_status = run_cli("R3_contrast_status", ["status", "--batch-dir", str(h03_target)], 1)
    if h03_status["exit_code"] != 1:
        r1_problems.append("协议对照的 status 未恢复原协议诊断（退出 1）")
    probe_records.append({"case": "R3_protocol_contrast", "injected": h03_state["count"],
                          "outcome": h03_outcome,
                          "manifest_status": (h03_manifest or {}).get("status"),
                          "declared": (h03_manifest or {}).get("receive", {}).get("declared_batch_status"),
                          "host_exit": (h03_manifest or {}).get("host_result", {}).get("exit_code"),
                          "status_exit": h03_status["exit_code"],
                          "target_reason": "已取得但矛盾的声明 → 宿主协议失败", "ok": h03_ok})

    record("R1_RECOVERY_PROTOCOL_AND_WRITE_TAIL", "flow", r1_problems, probes=probe_records)

    # ---------- 保护核对 ----------
    hashes_after = {str(path): sha256(path) for path in PROTECTED_FILES}
    changed = [path for path, digest in hashes_before.items() if hashes_after.get(path) != digest]
    if changed:
        failures.append({"case": "INTEGRITY_protected_files", "kind": "integrity", "result": "FAIL",
                         "problems": [f"受保护文件哈希不一致：{path}" for path in changed]})
        print("[FAIL] INTEGRITY_protected_files 哈希不一致")
        for path in changed:
            print(f"        - {path}")
    else:
        print("[PASS] INTEGRITY_protected_files 受保护文件哈希一致")

    counts["real_approvals"] = 0
    counts["checker_runs"] = sum(
        1 for name in ("main_01", "main_approve", "main_hold", "main_reject", "external_copy", "hostile_text",
                       "fault_snapshot", "fault_quality_report", "fault_receive_manifest", "fault_code_paths",
                       "fault_write", "c12_blocked")
        if (batch_path(name) / "checks" / "quality_report.json").exists())
    summary_counts = dict(counts)

    def _count_receiver_records():
        """按接收调用记录文件统计真实接收启动（副本不计）。"""
        copy_paths = {item["copy"] for item in copy_records}
        records = []
        for record_path in sorted(batch_parent.rglob("receive_invocation.json")):
            batch_dir = record_path.parent.parent
            relative = str(batch_dir.relative_to(PROJECT_ROOT))
            if any(relative == copy or relative.startswith(copy + "/") for copy in copy_paths):
                continue
            payload = json.loads(record_path.read_text(encoding="utf-8"))
            records.append({"batch": relative, "exit_code": payload["exit_code"],
                            "command": payload["command"]})
        return records

    receiver_records = _count_receiver_records()
    checker_records = []
    unreadable_manifests = []
    for manifest_path in sorted(batch_parent.rglob("batch_manifest.json")):
        batch_dir = manifest_path.parent
        relative = str(batch_dir.relative_to(PROJECT_ROOT))
        copies = {item["copy"] for item in copy_records}
        if any(relative == copy or relative.startswith(copy + "/") for copy in copies):
            continue
        if not manifest_path.is_file():
            # H02 类故障：清单原路径被替换为非文件，如实记录，不据此推进 checker 计数
            unreadable_manifests.append(relative)
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        invocation = manifest.get("checker_invocation") or {}
        if invocation.get("started") is True:
            checker_records.append({"batch": relative, "checker_exit_code": invocation.get("exit_code")})
    backup_confirmed = []
    for backup_path in sorted(batch_parent.rglob("batch_manifest.original.json")):
        batch_dir = backup_path.parent
        relative = str(batch_dir.relative_to(PROJECT_ROOT))
        copies = {item["copy"] for item in copy_records}
        if any(relative == copy or relative.startswith(copy + "/") for copy in copies):
            continue
        try:
            backup_payload = json.loads(backup_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (backup_payload.get("checker_invocation") or {}).get("started") is True:
            backup_confirmed.append({"batch": relative, "source": "batch_manifest.original.json"})
    entry_side = {"receiver_starts": summary_counts.get("receiver_starts"),
                  "checker_runs": summary_counts.get("checker_runs")}
    summary_counts["receiver_starts"] = len(receiver_records)
    summary_counts["checker_runs"] = len(checker_records) + len(backup_confirmed)
    summary_counts["checker_runs_visible_manifests"] = len(checker_records)
    summary_counts["checker_runs_backup_confirmed"] = len(backup_confirmed)
    summary_counts["batch_copies"] = len(copy_records)
    summary_counts["entry_side_counters"] = entry_side
    count_audit = {
        "declared": dict(summary_counts),
        "entry_side_counters": entry_side,
        "receiver_invocation_records": receiver_records,
        "receiver_starts_observed": len(receiver_records),
        "checker_started_observed": len(checker_records),
        "checker_records": checker_records,
        "copies": copy_records,
        "copies_observed": len(copy_records),
        "unreadable_manifests": unreadable_manifests,
        "checker_visible_manifests": len(checker_records),
        "checker_backup_confirmed": backup_confirmed,
        "checker_actual_total": len(checker_records) + len(backup_confirmed),
        "checker_count_basis": ("当前可读清单 started=true 计一次；清单被故障替换的批次"
                               "以保留的 batch_manifest.original.json 确认；两者相加为实际总数。"),
        "note": ("副本不计真实接收／checker；接收调用记录由宿主在子进程返回后独占写入，"
                 "checker 按清单 checker_invocation.started 计（运行失败也计）。"),
    }
    correspondence = audit_starts(receiver_records, expected_starts, copy_records)
    count_audit["correspondence"] = correspondence
    for key, observed in (("receiver_starts", len(receiver_records)),
                          ("checker_runs", len(checker_records) + len(backup_confirmed))):
        entry_value = entry_side.get(key) or 0
        if entry_value > observed:
            count_audit.setdefault("mismatches", []).append(
                {"field": key, "entry_side": entry_value, "records": observed,
                 "note": "入口侧计数多于实际调用记录：存在未留痕的启动"})
    if correspondence["missing_records"]:
        count_audit.setdefault("mismatches", []).append(
            {"field": "receiver_starts", "missing_records": correspondence["missing_records"],
             "note": "已登记的真实启动缺少独立调用记录"})

    # 隔离自测 1：计数核验本身能发现“启动无留痕”（只改内存审计对象）
    probe_audit = {"records": [dict(item) for item in receiver_records],
                   "expected": list(expected_starts), "copies": [dict(item) for item in copy_records]}
    if probe_audit["records"]:
        probe_audit["records"].pop(0)
    probe_correspondence = audit_starts(probe_audit["records"], probe_audit["expected"],
                                        probe_audit["copies"])
    count_self_test = {
        "case": "R3_count_audit_self_test",
        "dropped_record_from_in_memory_copy": True,
        "detected_missing": bool(probe_correspondence["missing_records"]),
        "missing_sample": probe_correspondence["missing_records"][:3],
        "expect": "去掉一条调用记录后必须判定不一致",
        "ok": bool(probe_correspondence["missing_records"]),
    }
    if not count_self_test["ok"]:
        failures.append({"case": "R3_COUNT_AUDIT_SELF_TEST", "kind": "selftest", "result": "FAIL",
                         "problems": ["去掉一条调用记录后未判定不一致"]})

    # 隔离自测 2：类别正确但原因不符必须判失败
    def matches_fault(exception, expected_class, expected_reason):
        if expected_class == "WorkflowHostError":
            if not isinstance(exception, host.WorkflowHostError):
                return False
        elif expected_class == "WorkflowHostBlocked":
            if not isinstance(exception, host.WorkflowHostBlocked):
                return False
        else:
            return False
        return expected_reason in str(exception)

    helper_self_test = {
        "case": "R3_fault_matcher_self_test",
        "cases": [
            {"name": "类别+目标原因均正确", "expect": True,
             "actual": matches_fault(real_fault_exception, "WorkflowHostError", sentinel_message)},
            {"name": "类别正确、原因不符", "expect": False,
             "actual": matches_fault(real_fault_exception, "WorkflowHostError", "另一个原因")},
            {"name": "类别不符", "expect": False,
             "actual": matches_fault(real_fault_exception, "WorkflowHostBlocked", sentinel_message)},
        ],
    }
    helper_self_test["ok"] = all(item["expect"] == item["actual"] for item in helper_self_test["cases"])
    if not helper_self_test["ok"]:
        failures.append({"case": "R3_FAULT_MATCHER_SELF_TEST", "kind": "selftest", "result": "FAIL",
                         "problems": [str(helper_self_test["cases"])]})
    (container / "self_tests.json").write_text(
        json.dumps({"count_audit_self_test": count_self_test,
                    "fault_matcher_self_test": helper_self_test,
                    "unchanged_guard_self_test": guard_self_test},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if count_self_test["ok"] and helper_self_test["ok"] and guard_self_test["ok"]:
        print("[PASS] R3/R4 隔离自测：计数核验可发现缺留痕；故障匹配器要求类别+目标原因一致；"
              "前后哈希判据在同值通过、改动后判失败")

    if count_audit.get("mismatches"):
        failures.append({"case": "R2_COUNT_AUDIT", "kind": "count", "result": "FAIL",
                         "problems": [str(count_audit["mismatches"])]})
        print(f"[FAIL] R2_COUNT_AUDIT 计数不一致：{count_audit['mismatches']}")
    else:
        print(f"[PASS] R2_COUNT_AUDIT 计数与调用记录一一对应"
              f"（接收 {len(receiver_records)}、checker {len(checker_records)}、副本 {len(copy_records)}）")

    # 最终一次落盘：先形成同一结果对象，再写盘并读回逐项核对
    summary = {
        "task": "TASK-010",
        "out_dir": str(container),
        "batch_parent": str(batch_parent),
        "python": sys.version.split()[0],
        "host": {"path": str(HOST), "sha256": sha256(HOST), "version": host.HOST_VERSION},
        "counts": summary_counts,
        "checks": checks,
        "cli_logs": cli_logs,
        "failures": failures,
        "protected_files_count": len(PROTECTED_FILES),
        "protected_files_unchanged": not changed,
        "note": "全部批次由真实接收器创建；本入口未执行标准化、SQLite、规则、复核、底稿或 AI。",
    }
    final_artifacts = {
        "summary.json": summary,
        "checks.json": checks,
        "cli_logs.json": cli_logs,
        "count_audit.json": count_audit,
    }
    save_problems = []
    for name, payload in final_artifacts.items():
        path = container / name
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            save_problems.append(f"{name} 写入失败：{exc}")
            continue
        try:
            readback = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            save_problems.append(f"{name} 读回失败：{exc}")
            continue
        if host.canonical_json(readback) != host.canonical_json(payload):
            save_problems.append(f"{name} 读回内容与写入不一致")
    readback_problems = []
    persisted_summary = json.loads((container / "summary.json").read_text(encoding="utf-8"))
    persisted_audit = json.loads((container / "count_audit.json").read_text(encoding="utf-8"))
    if persisted_summary["counts"]["receiver_starts"] != persisted_audit["receiver_starts_observed"]:
        readback_problems.append("summary 与 count_audit 的接收次数不一致")
    if persisted_summary["counts"]["checker_runs"] != persisted_audit["checker_actual_total"]:
        readback_problems.append("summary 与 count_audit 的 checker 实际总数不一致")
    if persisted_summary["counts"]["checker_runs_visible_manifests"] != persisted_audit[
            "checker_started_observed"]:
        readback_problems.append("summary 与 count_audit 的 checker 可见清单数不一致")
    if len(persisted_summary["checks"]) != len(checks):
        readback_problems.append("summary 与内存 checks 数量不一致")
    if len(persisted_summary["failures"]) != len(failures):
        readback_problems.append("summary 与内存 failures 数量不一致")
    readback_summary = {
        "case": "R3_FINAL_ARTIFACT_READBACK", "save_problems": save_problems,
        "readback_problems": readback_problems,
        "files": sorted(final_artifacts), "ok": not save_problems and not readback_problems,
    }
    if not readback_summary["ok"]:
        failures.append({"case": "R3_FINAL_ARTIFACT_READBACK", "kind": "artifact", "result": "FAIL",
                         "problems": save_problems + readback_problems})
        print(f"[FAIL] R3_FINAL_ARTIFACT_READBACK {save_problems + readback_problems}")
    else:
        print("[PASS] R3_FINAL_ARTIFACT_READBACK 最终汇总与审计一次落盘并读回一致")
    (container / "final_readback.json").write_text(
        json.dumps(readback_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"CLI 调用：start {counts['start_cli']}、status {counts['status_cli']}、"
          f"record-simulated-decision {counts['record_cli']}；宿主 API 直接调用 {counts['host_api_calls']}；"
          f"控制器造样 {counts['controller_sample_calls']}")
    print(f"真实接收启动 {summary_counts['receiver_starts']} 次（入口侧 {entry_side['receiver_starts']}）、"
          f"checker 运行 {summary_counts['checker_runs']} 次"
          f"（当前可读清单 {summary_counts['checker_runs_visible_manifests']} + 备份确认 "
          f"{summary_counts['checker_runs_backup_confirmed']}；入口侧 {entry_side['checker_runs']}）、"
          f"批次副本 {summary_counts['batch_copies']} 份、真实 writer 故障命中 {counts['real_writer_faults']} 次"
          f"（部分字节 {counts['writer_partial_bytes']}）、模拟决定 {counts['simulated_decisions']} 条、"
          f"真实批准 {counts['real_approvals']} 条、故障注入 {counts['fault_injections']} 次")
    print(f"测试失败 {counts and len(failures)}；受保护文件前后哈希一致: {summary['protected_files_unchanged']}"
          f"（{summary['protected_files_count']} 个）")
    print(f"汇总: {container / 'summary.json'}")
    result_code = 0
    if failures:
        print("存在断言失败或保护失败，返回非零退出码（不输出总体成功结论）。")
        result_code = 1
    else:
        print("全部预期成立。")
    sys.stdout, sys.stderr = original_stdout, original_stderr
    stdout_tee.close()
    stderr_tee.close()
    return result_code


if __name__ == "__main__":
    sys.exit(main())
