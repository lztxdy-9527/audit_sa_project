#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-012 开发验证入口：接收 → Gate1 决定 → 真实标准化／装载 → Gate2 模拟决定与重启恢复。

真实执行冻结上游（receiver／checker／normalizer／store／controller），按卡 §5 八组逐项留痕。
用法：
    .venv\\Scripts\\python.exe -B tests\\test_record_demo_gate2_decision.py --out-dir data\\workflow_host_tests\\<新容器>
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import traceback
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
C02_WORKBOOK = FIXTURES / "C02.xlsx"
C07B_WORKBOOK = FIXTURES / "C07b.xlsx"
C12_WORKBOOK = FIXTURES / "C12.xlsx"

PROTECTED = [NORMALIZER, STORE, CONTROLLER, RECEIVER, CHECKER, SCREEN, CROSSCHECK, FACT_PACKET,
             PROJECT_ROOT / "sql" / "demo_schema.sql", PROJECT_ROOT / "docs" / "SPEC_V1.md",
             PROJECT_ROOT / "docs" / "AUDIT_CONTRACT_DRAFT.md",
             PROJECT_ROOT / "tests" / "test_run_demo_workflow.py",
             PROJECT_ROOT / "tests" / "test_prepare_demo_gate2.py"]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TASK-012 验证入口")
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

    host = load_module(HOST, "task012_host")
    controller = load_module(CONTROLLER, "task012_controller")
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
    copy_records: list = []
    expected_starts: list = []
    deliberate_tamper_batches: list = []  # 探针故意保留的非法现场（不计作审计问题，逐项登记）
    counts = {"start_cli": 0, "status_cli": 0, "record_cli": 0, "prepare_cli": 0, "record_gate2_cli": 0,
              "host_api_calls": 0, "private_probe_calls": 0, "controller_sample_calls": 0,
              "controller_replay_calls_inproc": 0, "controller_replay_calls_cli_unobserved": None,
              "receiver_starts_host": 0, "receiver_starts_direct": 0, "receiver_starts": 0,
              "checker_runs": 0, "normalize_calls_inproc": 0, "load_calls_inproc": 0,
              "normalize_calls_cli_unobserved": None, "load_calls_cli_unobserved": None,
              "normalize_calls_cli_derived": 0, "load_calls_cli_derived": 0,
              "copies": 0, "fault_injections": 0, "simulated_decisions": 0, "real_approvals": 0,
              "rejections_observed": 0}

    real_normalize_fn = host.NORMALIZER_MODULE.normalize_workbook
    real_load_fn = host.STORE_MODULE.load_normalized_to_sqlite

    def counting_normalize(*call_args, **call_kwargs):
        counts["normalize_calls_inproc"] += 1
        return real_normalize_fn(*call_args, **call_kwargs)

    def counting_load(*call_args, **call_kwargs):
        counts["load_calls_inproc"] += 1
        return real_load_fn(*call_args, **call_kwargs)

    host.NORMALIZER_MODULE.normalize_workbook = counting_normalize
    host.STORE_MODULE.load_normalized_to_sqlite = counting_load

    def register_start(batch_dir: Path, entry: str, result: dict) -> None:
        relative = str(Path(batch_dir).relative_to(PROJECT_ROOT))
        if relative not in expected_starts:
            expected_starts.append(relative)
        if entry == "direct_receiver":
            counts["receiver_starts_direct"] += 1
            counts["private_probe_calls"] += 1
        elif entry == "host_cli":
            counts["receiver_starts_host"] += 1

    def register_copy(destination: Path, source: Path, case: str) -> None:
        counts["copies"] += 1
        copy_records.append({"copy": str(destination.relative_to(PROJECT_ROOT)),
                             "source": str(source.relative_to(PROJECT_ROOT)), "case": case,
                             "note": "副本不计真实接收／标准化／装载"})

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
        existed_before = bool(target_arg and target_arg.exists() and (target_arg / "source").exists())
        command = [sys.executable, "-B", str(HOST), *sub_args]
        completed = subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        index = len(cli_logs) + 1
        (container / "cli_logs").mkdir(exist_ok=True)
        out_path = container / "cli_logs" / f"{index:03d}_{label}.stdout.txt"
        err_path = container / "cli_logs" / f"{index:03d}_{label}.stderr.txt"
        out_path.write_text(completed.stdout, encoding="utf-8", newline="\n")
        err_path.write_text(completed.stderr, encoding="utf-8", newline="\n")
        payload = None
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
        entry = {"label": label, "command": command, "exit_code": completed.returncode,
                 "expect_exit": expect_exit, "stdout_path": str(out_path.relative_to(container)),
                 "stderr_path": str(err_path.relative_to(container)), "payload": payload,
                 "stderr_tail": completed.stderr[-500:],
                 "ok": completed.returncode == expect_exit}
        cli_logs.append(entry)
        command_name = sub_args[0] if sub_args else ""
        if command_name == "start":
            counts["start_cli"] += 1
            if target_arg is not None and not existed_before and (target_arg / "source").exists():
                register_start(target_arg, "host_cli", {"command": command, "exit_code": completed.returncode})
        elif command_name == "status":
            counts["status_cli"] += 1
        elif command_name == "record-simulated-decision":
            counts["record_cli"] += 1
        elif command_name == "prepare-gate2":
            counts["prepare_cli"] += 1
            if completed.returncode == 0:
                counts["normalize_calls_cli_derived"] += 1
                counts["load_calls_cli_derived"] += 1
        elif command_name == "record-simulated-gate2-decision":
            counts["record_gate2_cli"] += 1
        if completed.returncode != 0:
            counts["rejections_observed"] += 1
        print(f"    CLI {label}: exit={completed.returncode}（期望 {expect_exit}）")
        return entry

    def batch_path(leaf: str) -> Path:
        return batch_parent / leaf

    def copy_batch(leaf: str, source: Path) -> Path:
        destination = batch_parent / leaf / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        register_copy(destination, source, leaf)
        return destination

    def copy_batch_with_database(leaf: str, source: Path) -> Path:
        """造样：复制批次，并把源批次的推导数据库复制到副本自己的推导路径，使副本现场自洽。"""
        destination = copy_batch(leaf, source)
        source_db = host._gate2_paths(source, "probe")["database_path"]
        copy_db = host._gate2_paths(destination, "probe")["database_path"]
        copy_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_db, copy_db)
        copy_records.append({"copy": str(copy_db.relative_to(PROJECT_ROOT)),
                             "source": str(source_db.relative_to(PROJECT_ROOT)), "case": leaf,
                             "note": "造样：为副本补齐其推导路径下的数据库（同内容），不冒称新装载"})
        return destination

    def write_decision(name: str, batch_dir: Path, gate: str, revision: int, kind: str,
                       *, event_id: str = None, mutate=None) -> Path:
        payload = json.loads((batch_dir / "workflow" / "checkpoints" /
                              f"{revision:04d}.json").read_text(encoding="utf-8"))
        request = payload["workflow"]["state"]["requests"][gate]
        confirm_key = controller.CONFIRMATION_KEY[gate]
        decision = {
            "event_id": event_id or f"EVT-{name}",
            "batch_id": batch_dir.name,
            "gate": gate,
            "request_id": request["request_id"],
            "materials_sha256": request["materials_sha256"],
            "decision": kind,
            "actor_kind": "SIMULATED_HUMAN",
            "actor_id": "tester-01",
            "occurred_at": "2026-10-11T16:00:00+08:00",
            "reason": f"显式模拟 {gate} {kind}（测试样例，不是真实批准）",
            "simulation": "SIMULATED_TEST_ONLY",
            "confirmations": {confirm_key: True},
        }
        if mutate is not None:
            mutate(decision)
        path = container / f"decision_{name}.json"
        path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def decision_body_sha(decision: dict) -> str:
        return host.canonical_sha256({k: v for k, v in decision.items() if k != "decision_sha256"})

    def chain_state(batch_dir: Path, revision: int) -> dict:
        return json.loads((batch_dir / "workflow" / "checkpoints" / f"{revision:04d}.json").read_text(
            encoding="utf-8"))

    def matches(exc: Exception, expect_class: str, target: str) -> bool:
        if expect_class == "WorkflowHostBlocked" and not isinstance(exc, host.WorkflowHostBlocked):
            return False
        if expect_class == "WorkflowHostError" and not isinstance(exc, host.WorkflowHostError):
            return False
        return target in str(exc)

    def _jsonable(value):
        """把实参/返回值转成可解析 JSON，Path 转字符串，异常对象转完整描述（不截断）。"""
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(key): _jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_jsonable(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return {"__type__": f"{type(value).__module__}.{type(value).__name__}", "repr": repr(value)}

    def _exception_chain(exc: BaseException) -> list:
        """完整异常链：类名、消息、参数、可用字段与 traceback（不截断）。"""
        chain, seen, current = [], set(), exc
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            entry = {"class": type(current).__name__,
                     "module": type(current).__module__,
                     "message": str(current),
                     "args": _jsonable(list(current.args))}
            for attr in ("stage", "reasons", "batch_id", "result"):
                if hasattr(current, attr):
                    entry[attr] = _jsonable(getattr(current, attr))
            entry["cause_class"] = type(current.__cause__).__name__ if current.__cause__ else None
            entry["traceback"] = traceback.format_exception(type(current), current, current.__traceback__)
            chain.append(entry)
            current = current.__cause__ or current.__context__
        return chain

    def run_api(label: str, func, expect_exception=None, target: str = "", **kwargs) -> dict:
        # 公开 API 计数由统一观察层按真实入口事件导出，这里不再额外累加（避免同一调用重复计数）
        observed_wrapper = getattr(func, "__wrapped__", None)
        real_entry = observed_wrapper if observed_wrapper is not None else func
        call_record = {"label": label,
                       "function": f"{getattr(real_entry, '__module__', '')}."
                                   f"{getattr(real_entry, '__name__', repr(real_entry))}",
                       "called_through_observed_entry": observed_wrapper is not None,
                       "arguments": _jsonable(kwargs), "expect_exception": expect_exception,
                       "target_reason": target}
        try:
            result = func(**kwargs)
            call_record["outcome"] = {"kind": "returned", "result": _jsonable(result)}
            return {"label": label, "result": result, "exception": None, "ok": expect_exception is None,
                    "record": call_record}
        except Exception as exc:  # noqa: BLE001
            expected_class = expect_exception or ""
            ok = bool(expected_class) and matches(exc, expected_class, target)
            chain = _exception_chain(exc)
            call_record["outcome"] = {"kind": "exception", "exception_class": type(exc).__name__,
                                      "message": str(exc), "chain": chain}
            return {"label": label, "result": None, "exception": exc,
                    "exception_class": type(exc).__name__, "message": str(exc),
                    "chain": chain, "ok": ok, "target": target, "expect": expected_class,
                    "record": call_record}

    def persist_probe_record(case: str, payload: dict, *, expect_message: str = None,
                             expect_decision_body_sha256: str = None) -> dict:
        """把完整结构化探针记录落盘、读回核对，返回可解析引用（checks 中只留摘要时据此指向全文）。"""
        directory = container / "g9_probe_records"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{case}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        readback = json.loads(path.read_text(encoding="utf-8"))
        stored_message = (readback.get("outcome") or {}).get("message")
        stored_decision = ((readback.get("decision") or {}).get("decision_body_sha256"))
        checks = {
            "readback_identical": host.canonical_json(readback) == host.canonical_json(payload),
            "message_complete": (expect_message is None or stored_message == expect_message),
            "decision_body_preserved": (expect_decision_body_sha256 is None
                                        or stored_decision == expect_decision_body_sha256),
            "message_length": len(stored_message) if isinstance(stored_message, str) else None,
        }
        checks["ok"] = all(value for key, value in checks.items() if key != "message_length")
        return {"full_record": str(path.relative_to(container)),
                "full_record_sha256": sha256(path), "full_record_bytes": path.stat().st_size,
                "full_record_checks": checks,
                "summary_note": "checks 中仅保留摘要；完整调用现场见 full_record 指向的 JSON。"}

    # 已冻结的 TASK-011 验证容器（既有合法 C02／C07b 现场，供复用其材料）
    frozen_container = HOST_TESTS_ROOT / "task011r1_final_01"
    frozen_batches = BATCHES_ROOT / "task011r1_final_01"
    print(f"复用已冻结现场：{frozen_container}（存在：{frozen_container.exists()}）")

    # =====================================================================
    # G1：MAIN 全流程
    # =====================================================================
    g1_problems: list = []
    g1_probes: list = []
    main_batch = batch_path("main_01")
    run_cli("g1_start", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir", str(main_batch),
                         "--source-description", "合成 ERP 导出（TASK-012 验证用）"], 0)
    run_cli("g1_status_pending", ["status", "--batch-dir", str(main_batch)], 0)
    gate1_decision = write_decision("g1_gate1", main_batch, "GATE1", 1, "APPROVE")
    run_cli("g1_record_gate1", ["record-simulated-decision", "--batch-dir", str(main_batch),
                                "--decision-file", str(gate1_decision)], 0)

    # 统一真实入口观察：同一入口只在此计一次；故障 wrapper 必须调用这里返回的观察包装器
    api_events: list = []
    controller_events: list = []
    controller_sample_events: list = []

    def observe_entry(owner, attr, key, entry, events):
        original = getattr(owner, attr)

        def wrapper(*call_args, **call_kwargs):
            counts[key] += 1
            events.append({"entry": entry, "attr": attr, "order": len(events) + 1})
            try:
                result = original(*call_args, **call_kwargs)
            except BaseException as exc:  # noqa: BLE001 - 抛错前已进入的调用同样已计入
                events[-1]["exception_class"] = type(exc).__name__
                raise
            events[-1]["ok"] = True
            return result

        wrapper.__wrapped__ = original
        wrapper.__obs_original__ = original
        setattr(owner, attr, wrapper)
        return wrapper

    # 公开宿主 API：含经 status/record helper 进入的 inspect_dev_batch、直接调用与抛错前已进入的调用
    for _name in ("start_dev_batch", "inspect_dev_batch", "prepare_dev_gate2",
                  "record_simulated_gate1_decision", "record_simulated_gate2_decision"):
        observe_entry(host, _name, "host_api_calls", "host_api", api_events)

    # 宿主内部控制器重放（进程内可观测）：包装对象本身即后续 wrapper 必须调用的真实入口
    observed_controller = {}
    for _name in ("record_dev_decision", "prepare_dev_gate", "check_dev_action"):
        observed_controller[_name] = observe_entry(host.CONTROLLER_MODULE, _name,
                                                   "controller_replay_calls_inproc", "controller",
                                                   controller_events)
    # 测试侧造样调用（测试自己的控制器模块实例）单列，不与宿主内部重放混计
    for _name in ("record_dev_decision", "prepare_dev_gate", "check_dev_action"):
        observe_entry(controller, _name, "controller_sample_calls", "controller_sample",
                      controller_sample_events)

    normalize_before = counts["normalize_calls_inproc"]
    prepare = run_cli("g1_prepare_gate2", ["prepare-gate2", "--batch-dir", str(main_batch)], 0)
    if counts["normalize_calls_cli_derived"] < 1:
        g1_problems.append("CLI prepare-gate2 成功一次即应推导一次真实标准化调用（子进程内次数不可观测）")
    if counts["normalize_calls_inproc"] != normalize_before:
        g1_problems.append("CLI prepare-gate2 不得被进程内观测为额外调用（子进程内次数不可观测，另列 null）")

    before_hashes = {rev: sha256(main_batch / "workflow" / "checkpoints" / f"{rev:04d}.json")
                     for rev in (1, 2, 3)}
    before_gate2 = {name: sha256(main_batch / "workflow" / "gate2" / name)
                    for name in ("normalized.json", "load_report.json", "artifacts.json")}
    before_db = sha256(host._gate2_paths(main_batch, "probe")["database_path"])

    normalize_during_decision = counts["normalize_calls_inproc"]
    load_during_decision = counts["load_calls_inproc"]
    gate2_decision = write_decision("g1_gate2", main_batch, "GATE2", 3, "APPROVE")
    gate2_result = run_cli("g1_record_gate2", ["record-simulated-gate2-decision",
                                               "--batch-dir", str(main_batch),
                                               "--decision-file", str(gate2_decision)], 0)
    if gate2_result["payload"] and gate2_result["payload"].get("phase") != "DEV_GATE2_APPROVED":
        g1_problems.append(f"MAIN Gate2 APPROVE 后 phase 应为 DEV_GATE2_APPROVED，实际 "
                           f"{gate2_result['payload'].get('phase')!r}")

    status_after = run_cli("g1_status_after", ["status", "--batch-dir", str(main_batch)], 0)
    status_payload = status_after["payload"] or {}
    if status_payload.get("phase") != "DEV_GATE2_APPROVED":
        g1_problems.append(f"新进程 status 应恢复 DEV_GATE2_APPROVED，实际 {status_payload.get('phase')!r}")
    actions = status_payload.get("actions_simulated_allowed") or {}
    if actions.get("SCREEN_AND_BUILD_FACTS") is not True:
        g1_problems.append(f"Gate2 APPROVED 必须声明 SCREEN_AND_BUILD_FACTS 模拟可行，实际 {actions!r}")
    if actions.get("NORMALIZE_AND_LOAD") is not False:
        g1_problems.append("Gate2 APPROVED 后 NORMALIZE_AND_LOAD 不得再允许")
    if status_payload.get("next_step_allowed") is not False or status_payload.get("real_approvals") != 0:
        g1_problems.append("真实 next_step_allowed 必须 false、真实批准必须 0")
    if counts["normalize_calls_inproc"] != normalize_during_decision or \
            counts["load_calls_inproc"] != load_during_decision:
        g1_problems.append("Gate2 决定与 status 阶段（进程内可观测面）不得再调用标准化／装载")
    if status_after["payload"].get("gate2_decision", {}).get("decision") != "APPROVE":
        g1_problems.append("status 必须给出 Gate2 决定摘要")

    after_hashes = {rev: sha256(main_batch / "workflow" / "checkpoints" / f"{rev:04d}.json")
                    for rev in (1, 2, 3)}
    after_gate2 = {name: sha256(main_batch / "workflow" / "gate2" / name)
                   for name in ("normalized.json", "load_report.json", "artifacts.json")}
    after_db = sha256(host._gate2_paths(main_batch, "probe")["database_path"])
    if before_hashes != after_hashes:
        g1_problems.append(f"0001—0003 在 Gate2 决定调用前后字节必须不变：{before_hashes} -> {after_hashes}")
    if before_gate2 != after_gate2 or before_db != after_db:
        g1_problems.append("Gate2 材料与数据库字节在决定调用前后必须不变")
    cp4 = chain_state(main_batch, 4)
    if cp4["previous_file_sha256"] != after_hashes[3]:
        g1_problems.append("0004 前序必须是初始实读的 0003 字节哈希")
    if cp4["revision"] != 4 or cp4["operation"]["kind"] != "SIMULATED_GATE2_DECISION":
        g1_problems.append(f"0004 形状不符：{cp4.get('revision')!r}/{cp4['operation'].get('kind')!r}")
    if len(json.loads(json.dumps(cp4["workflow"]["state"]["simulated_decisions"]))) != 2:
        g1_problems.append("决定总数必须恰为 2")
    if cp4["workflow"]["state"]["gate1_approval"] is not None or \
            cp4["workflow"]["state"]["gate2_approval"] is not None:
        g1_problems.append("真实批准字段必须恒为 null")
    g1_probes.append({"case": "G1_MAIN", "phase": status_payload.get("phase"),
                      "actions": actions, "checkpoints_unchanged": before_hashes == after_hashes,
                      "materials_unchanged": before_gate2 == after_gate2 and before_db == after_db,
                      "ok": not g1_problems})
    record("G1_MAIN_FULL_FLOW", "flow", g1_problems, probes=g1_probes)

    # =====================================================================
    # G2：HOLD／REJECT 停止态与 C07b 缺失关联仍可 APPROVE
    # =====================================================================
    g2_problems: list = []
    g2_probes: list = []
    c07b_probes: list = []
    for kind, expect_phase in (("HOLD", "DEV_GATE2_HELD"), ("REJECT", "DEV_GATE2_REJECTED")):
        leaf = f"c02_{kind.lower()}"
        target = batch_path(leaf)
        run_cli(f"g2_start_{kind}", ["start", "--workbook", str(C02_WORKBOOK), "--batch-dir", str(target),
                                     "--source-description", f"C02 小样（{kind} 用例）"], 0)
        run_cli(f"g2_gate1_{kind}", ["record-simulated-decision", "--batch-dir", str(target),
                                     "--decision-file", str(write_decision(f"g2_gate1_{kind}", target,
                                                                           "GATE1", 1, "APPROVE"))], 0)
        run_cli(f"g2_prepare_{kind}", ["prepare-gate2", "--batch-dir", str(target)], 0)
        result = run_cli(f"g2_gate2_{kind}", ["record-simulated-gate2-decision", "--batch-dir", str(target),
                                              "--decision-file", str(write_decision(f"g2_gate2_{kind}", target,
                                                                                    "GATE2", 3, kind))], 0)
        if result["payload"].get("phase") != expect_phase:
            g2_problems.append(f"{kind} 后 phase 应为 {expect_phase}，实际 {result['payload'].get('phase')!r}")
        if result["payload"].get("simulated_action_allowed") is not False:
            g2_problems.append(f"{kind} 为停止态，SCREEN_AND_BUILD_FACTS 不得允许")
        status = run_cli(f"g2_status_{kind}", ["status", "--batch-dir", str(target)], 0)
        if status["payload"].get("phase") != expect_phase:
            g2_problems.append(f"{kind} 重启恢复 phase 不符：{status['payload'].get('phase')!r}")
        actions = status["payload"].get("actions_simulated_allowed") or {}
        if any(actions.values()):
            g2_problems.append(f"{kind} 停止态不得允许任何后续动作：{actions!r}")
        again = run_cli(f"g2_repeat_{kind}", ["record-simulated-gate2-decision", "--batch-dir", str(target),
                                              "--decision-file", str(write_decision(f"g2_again_{kind}", target,
                                                                                    "GATE2", 3, kind,
                                                                                    event_id=f"EVT-AGAIN-{kind}"))], 1)
        if not (again["exit_code"] == 1 and "0004" in str(again["payload"].get("message"))):
            g2_problems.append(f"{kind} 后重复提交必须按 0004 阻断：{str(again['payload'].get('message'))[:120]}")
        g2_probes.append({"case": f"G2_{kind}", "phase": status["payload"].get("phase"),
                          "actions": actions, "repeat_exit": again["exit_code"], "ok": True})

    c07b = batch_path("c07b_missing")
    run_cli("g2_start_c07b", ["start", "--workbook", str(C07B_WORKBOOK), "--batch-dir", str(c07b),
                              "--source-description", "C07b 合法部分未匹配关联小样"], 0)
    run_cli("g2_gate1_c07b", ["record-simulated-decision", "--batch-dir", str(c07b),
                              "--decision-file", str(write_decision("g2_gate1_c07b", c07b, "GATE1", 1,
                                                                    "APPROVE"))], 0)
    c07b_prepare = run_api("g2_prepare_c07b_api", host.prepare_dev_gate2, batch_dir=c07b)
    if not c07b_prepare["ok"] or (c07b_prepare["result"] or {}).get("phase") != "DEV_GATE2_PENDING":
        g2_problems.append(f"C07b 进程内 API prepare-gate2 必须成功并停在 DEV_GATE2_PENDING："
                           f"{c07b_prepare.get('exception_class')}/{str(c07b_prepare.get('message'))[:160]}")
    c07b_first = run_cli("g2_gate2_c07b", ["record-simulated-gate2-decision", "--batch-dir", str(c07b),
                                           "--decision-file", str(write_decision("g2_gate2_c07b", c07b,
                                                                                 "GATE2", 3, "APPROVE"))], 0)
    if c07b_first["payload"].get("phase") != "DEV_GATE2_APPROVED":
        g2_problems.append("C07b 合法未匹配关联批次必须可模拟 APPROVE（不得当成质量问题）")
    c07b_report = json.loads((c07b / "workflow" / "gate2" / "load_report.json").read_text(encoding="utf-8"))
    missing = c07b_report.get("missing_payable_link_net")
    if not (isinstance(missing, int) and not isinstance(missing, bool) and missing > 0):
        g2_problems.append(f"C07b 合法未匹配关联必须保留非零缺失金额（实际 {missing!r}）")
    if c07b_report.get("known_payable_link_net", 0) + (missing or 0) != c07b_report.get("master_net"):
        g2_problems.append("C07b 资金净额必须等于已知关联净额加缺失关联净额")
    c07b_probes.append({"case": "G2_C07B", "phase": c07b_first["payload"].get("phase"),
                        "missing_payable_link_net": missing, "ok": True})
    record("G2_STOP_STATES_AND_MISSING_LINK", "flow", g2_problems, probes=g2_probes + c07b_probes)

    # =====================================================================
    # G3：拒绝面（早期阶段／停止态／失败准备／字段错误）
    # =====================================================================
    g3_problems: list = []
    g3_probes: list = []

    pending_batch = batch_path("g3_gate1_pending")
    run_cli("g3_start_pending", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir", str(pending_batch),
                                 "--source-description", "早期阶段用例"], 0)
    early = run_cli("g3_gate2_on_pending", ["record-simulated-gate2-decision", "--batch-dir",
                                            str(pending_batch),
                                            "--decision-file", str(write_decision("g3_pending", pending_batch,
                                                                                  "GATE1", 1, "APPROVE"))], 1)
    if not (early["exit_code"] == 1 and "Gate2 决定只能在合法" in str(early["payload"].get("message"))):
        g3_problems.append(f"Gate1 pending 阶段的 Gate2 记录必须按早期阶段阻断："
                           f"{str(early['payload'].get('message'))[:150]}")
    g3_probes.append({"case": "G3_GATE1_PENDING_REJECTED", "exit": early["exit_code"],
                      "message": str(early["payload"].get("message"))[:160], "ok": True})

    approved_batch = batch_path("g3_gate1_approved_unprepared")
    run_cli("g3_start_approved", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir",
                                  str(approved_batch), "--source-description", "未 prepare 用例"], 0)
    run_cli("g3_record_gate1", ["record-simulated-decision", "--batch-dir", str(approved_batch),
                                "--decision-file", str(write_decision("g3_approved", approved_batch,
                                                                      "GATE1", 1, "APPROVE"))], 0)
    unprepared = run_cli("g3_gate2_unprepared", ["record-simulated-gate2-decision", "--batch-dir",
                                                 str(approved_batch),
                                                 "--decision-file", str(write_decision("g3_unprepared",
                                                                                       approved_batch,
                                                                                       "GATE1", 1, "APPROVE"))], 1)
    if unprepared["exit_code"] != 1:
        g3_problems.append("Gate1 APPROVED 尚未 prepare 时 Gate2 记录必须拒绝")
    g3_probes.append({"case": "G3_UNPREPARED_REJECTED", "exit": unprepared["exit_code"],
                      "message": str(unprepared["payload"].get("message"))[:160], "ok": True})

    hold_batch = batch_path("g3_gate1_hold")
    run_cli("g3_start_hold", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir", str(hold_batch),
                              "--source-description", "Gate1 HOLD 用例"], 0)
    hold_result = run_cli("g3_hold", ["record-simulated-decision", "--batch-dir", str(hold_batch),
                                      "--decision-file", str(write_decision("g3_hold", hold_batch,
                                                                            "GATE1", 1, "HOLD"))], 0)
    after_hold = run_cli("g3_gate2_after_hold", ["record-simulated-gate2-decision", "--batch-dir",
                                                 str(hold_batch),
                                                 "--decision-file", str(write_decision("g3_after_hold",
                                                                                       hold_batch,
                                                                                       "GATE1", 2, "APPROVE"))], 1)
    if after_hold["exit_code"] != 1:
        g3_problems.append("Gate1 HOLD 后 Gate2 记录必须拒绝")
    g3_probes.append({"case": "G3_GATE1_HOLD_REJECTED", "exit": after_hold["exit_code"], "ok": True})

    # 上游标准化拒绝一项：包装真实上游（先真实调用后抛上游错误），命中计数 1
    normalize_fail_batch = batch_path("g3_normalize_rejected")
    run_cli("g3_norm_start", ["start", "--workbook", str(C02_WORKBOOK), "--batch-dir",
                              str(normalize_fail_batch), "--source-description",
                              "上游标准化拒绝探针（C02 小样，专供探针）"], 0)
    run_cli("g3_norm_gate1", ["record-simulated-decision", "--batch-dir", str(normalize_fail_batch),
                              "--decision-file", str(write_decision("g3_norm_gate1", normalize_fail_batch,
                                                                    "GATE1", 1, "APPROVE"))], 0)
    real_normalize_for_fault = host.NORMALIZER_MODULE.normalize_workbook
    normalize_hits = {"n": 0}

    def normalize_then_reject(workbook, quality_report):
        normalize_hits["n"] += 1
        real_normalize_for_fault(workbook, quality_report)  # 真实调用冻结上游（经计数包装）
        raise host.NORMALIZER_MODULE.NormalizationError("测试注入：上游标准化拒绝（真实调用之后）")

    host.NORMALIZER_MODULE.normalize_workbook = normalize_then_reject
    counts["fault_injections"] += 1
    counts["normalize_calls_inproc"] += 0
    probe = run_api("g3_normalize_rejected", host.prepare_dev_gate2,
                    expect_exception="WorkflowHostError", target="NormalizationError",
                    batch_dir=normalize_fail_batch)
    host.NORMALIZER_MODULE.normalize_workbook = real_normalize_for_fault
    norm_failure_file = normalize_fail_batch / "workflow" / "gate2" / "failure.json"
    norm_ok = (probe["ok"] and normalize_hits["n"] == 1 and norm_failure_file.is_file()
               and not (normalize_fail_batch / "workflow" / "checkpoints" / "0003.json").exists())
    if not norm_ok:
        g3_problems.append(f"上游标准化拒绝必须 exit 2 语义＋保存 failure.json＋无 0003："
                           f"hits={normalize_hits['n']} failure={norm_failure_file.is_file()} "
                           f"msg={str(probe.get('message'))[:160]}")
    norm_reopen = run_cli("g3_norm_status", ["status", "--batch-dir", str(normalize_fail_batch)], 2)
    if norm_reopen["exit_code"] != 2:
        g3_problems.append(f"失败准备批次恢复必须保留 2：实际 {norm_reopen['exit_code']}")
    norm_record = run_cli("g3_norm_record", ["record-simulated-gate2-decision", "--batch-dir",
                                             str(normalize_fail_batch),
                                             "--decision-file", str(write_decision("g3_norm_record",
                                                                                   normalize_fail_batch,
                                                                                   "GATE1", 1, "APPROVE"))], 2)
    if norm_record["exit_code"] != 2:
        g3_problems.append("失败准备批次不得接受 Gate2 决定（保持 2）")
    g3_probes.append({"case": "G3_UPSTREAM_NORMALIZE_REJECTED", "hits": normalize_hits["n"],
                      "exception_class": probe.get("exception_class"),
                      "message": str(probe.get("message"))[:200],
                      "failure_saved": norm_failure_file.is_file(),
                      "status_exit": norm_reopen["exit_code"], "ok": norm_ok})

    # 装载运行失败一项：同样先真实调用后抛上游错误
    load_fail_batch = batch_path("g3_load_failed")
    run_cli("g3_load_start", ["start", "--workbook", str(C02_WORKBOOK), "--batch-dir", str(load_fail_batch),
                              "--source-description", "装载失败探针（C02 小样，专供探针）"], 0)
    run_cli("g3_load_gate1", ["record-simulated-decision", "--batch-dir", str(load_fail_batch),
                              "--decision-file", str(write_decision("g3_load_gate1", load_fail_batch,
                                                                    "GATE1", 1, "APPROVE"))], 0)
    real_load_for_fault = host.STORE_MODULE.load_normalized_to_sqlite
    load_hits = {"n": 0}

    def load_then_fail(normalized, database_path, *args, **kwargs):
        load_hits["n"] += 1
        real_load_for_fault(normalized, database_path, *args, **kwargs)  # 真实调用冻结上游（经计数包装）
        raise host.STORE_MODULE.SqliteLoadError("测试注入：装载运行失败（真实调用之后）")

    host.STORE_MODULE.load_normalized_to_sqlite = load_then_fail
    counts["fault_injections"] += 1
    probe = run_api("g3_load_failed", host.prepare_dev_gate2,
                    expect_exception="WorkflowHostError", target="SqliteLoadError",
                    batch_dir=load_fail_batch)
    host.STORE_MODULE.load_normalized_to_sqlite = real_load_for_fault
    load_failure_file = load_fail_batch / "workflow" / "gate2" / "failure.json"
    load_ok = (probe["ok"] and load_hits["n"] == 1 and load_failure_file.is_file()
               and not (load_fail_batch / "workflow" / "checkpoints" / "0003.json").exists())
    if not load_ok:
        g3_problems.append(f"装载运行失败必须 exit 2 语义＋保存 failure.json＋无 0003："
                           f"hits={load_hits['n']} failure={load_failure_file.is_file()} "
                           f"msg={str(probe.get('message'))[:160]}")
    load_repeat = run_api("g3_load_repeat", host.prepare_dev_gate2,
                          expect_exception="WorkflowHostBlocked", target="gate2",
                          batch_dir=load_fail_batch)
    if not load_repeat["ok"]:
        g3_problems.append("失败准备批次不得重试 prepare-gate2（现场保留）")
    g3_probes.append({"case": "G3_UPSTREAM_LOAD_FAILED", "hits": load_hits["n"],
                      "exception_class": probe.get("exception_class"),
                      "message": str(probe.get("message"))[:200],
                      "failure_saved": load_failure_file.is_file(),
                      "repeat_exception": load_repeat.get("exception_class"), "ok": load_ok})

    # 字段级错误（在新内存决定上；复用 MAIN 的 0003 材料，不重跑重型流程）
    field_cases = [
        ("gate", "WorkflowHostBlocked", "gate", lambda d: d.__setitem__("gate", "GATE1")),
        ("request_id", "WorkflowHostBlocked", "request_id",
         lambda d: d.__setitem__("request_id", "OTHER-REQUEST")),
        ("materials", "WorkflowHostBlocked", "materials_sha256",
         lambda d: d.__setitem__("materials_sha256", "0" * 64)),
        ("actor_ai", "WorkflowHostBlocked", "actor_kind",
         lambda d: d.__setitem__("actor_kind", "AI")),
        ("simulation_real", "WorkflowHostBlocked", "simulation",
         lambda d: d.__setitem__("simulation", "REAL")),
        ("missing_reason", "WorkflowHostBlocked", "reason", lambda d: d.pop("reason")),
        ("confirmation_false", "WorkflowHostBlocked", "confirmations",
         lambda d: d["confirmations"].__setitem__("reconciliation_reviewed", False)),
        ("confirmation_one", "WorkflowHostBlocked", "confirmations",
         lambda d: d["confirmations"].__setitem__("reconciliation_reviewed", 1)),
        ("duplicate_event", "WorkflowHostBlocked", "event_id",
         lambda d: d.__setitem__("event_id", "EVT-g3_field_gate1")),
    ]
    field_base = batch_path("g3_field_base")
    run_cli("g3_field_start", ["start", "--workbook", str(C02_WORKBOOK), "--batch-dir", str(field_base),
                               "--source-description", "字段探针基准（C02 小样，专供探针）"], 0)
    run_cli("g3_field_gate1", ["record-simulated-decision", "--batch-dir", str(field_base),
                               "--decision-file", str(write_decision("g3_field_gate1", field_base,
                                                                     "GATE1", 1, "APPROVE"))], 0)
    run_cli("g3_field_prepare", ["prepare-gate2", "--batch-dir", str(field_base)], 0)
    field_positive = run_cli("g3_field_positive", ["status", "--batch-dir", str(field_base)], 0)
    if field_positive["payload"].get("phase") != "DEV_GATE2_PENDING":
        g3_problems.append("字段探针基准批次必须停在 DEV_GATE2_PENDING")
    for name, expect_class, target, mutate in field_cases:
        path = write_decision(f"g3_field_{name}", field_base, "GATE2", 3, "APPROVE", mutate=mutate)
        probe = run_api(f"g3_field_{name}", host.record_simulated_gate2_decision,
                        expect_exception=expect_class, target=target,
                        batch_dir=field_base, decision=json.loads(path.read_text(encoding="utf-8")))
        if not probe["ok"]:
            g3_problems.append(f"字段用例 {name} 必须按 {expect_class}/{target} 阻断，实际 "
                               f"{probe.get('exception_class')!r}/{str(probe.get('message'))[:140]}")
        g3_probes.append({"case": f"G3_FIELD_{name}", "exception_class": probe.get("exception_class"),
                          "message": str(probe.get("message"))[:170], "target": target,
                          "ok": probe["ok"]})
    if (field_base / "workflow" / "checkpoints" / "0005.json").exists():
        g3_problems.append("字段级拒绝不得产生 0005")
    if (field_base / "workflow" / "checkpoints" / "0004.json").exists():
        g3_problems.append("字段级拒绝不得写出 0004")
    field_after = run_cli("g3_field_after", ["status", "--batch-dir", str(field_base)], 0)
    if field_after["payload"].get("phase") != "DEV_GATE2_PENDING":
        g3_problems.append("字段级拒绝后基准批次必须仍是 DEV_GATE2_PENDING")
    record("G3_REJECTION_SURFACE", "flow", g3_problems, probes=g3_probes)

    # =====================================================================
    # G4：决定后的重复／冲突与旧版本回归
    # =====================================================================
    g4_problems: list = []
    g4_probes: list = []
    fixed_before = {rev: sha256(main_batch / "workflow" / "checkpoints" / f"{rev:04d}.json")
                    for rev in (1, 2, 3, 4)}
    repeat = run_cli("g4_repeat_gate2", ["record-simulated-gate2-decision", "--batch-dir", str(main_batch),
                                         "--decision-file", str(write_decision("g4_repeat", main_batch,
                                                                               "GATE2", 3, "HOLD",
                                                                               event_id="EVT-G4-REPEAT"))], 1)
    if not (repeat["exit_code"] == 1 and "0004" in str(repeat["payload"].get("message"))):
        g4_problems.append("重复 Gate2 决定必须按已有 0004 阻断")
    gate1_again = run_cli("g4_gate1_again", ["record-simulated-decision", "--batch-dir", str(main_batch),
                                             "--decision-file", str(write_decision("g4_gate1_again", main_batch,
                                                                                   "GATE1", 1, "APPROVE"))], 1)
    if gate1_again["exit_code"] != 1:
        g4_problems.append("Gate2 决定后 Gate1 记录命令必须拒绝")
    prepare_again = run_cli("g4_prepare_again", ["prepare-gate2", "--batch-dir", str(main_batch)], 1)
    if prepare_again["exit_code"] != 1:
        g4_problems.append("Gate2 决定后 prepare-gate2 必须拒绝")
    fixed_after = {rev: sha256(main_batch / "workflow" / "checkpoints" / f"{rev:04d}.json")
                   for rev in (1, 2, 3, 4)}
    if fixed_before != fixed_after:
        g4_problems.append("重复／冲突提交不得改变任何 checkpoint 字节")
    if (main_batch / "workflow" / "checkpoints" / "0005.json").exists():
        g4_problems.append("不得产生 0005")
    gate2_again_api = run_api("g4_conflict_api", host.record_simulated_gate2_decision,
                              expect_exception="WorkflowHostBlocked", target="0004",
                              batch_dir=main_batch,
                              decision={"event_id": "EVT-G4-API", "batch_id": main_batch.name,
                                        "gate": "GATE2", "request_id": "x", "materials_sha256": "0" * 64,
                                        "decision": "REJECT", "actor_kind": "SIMULATED_HUMAN",
                                        "actor_id": "tester-01",
                                        "occurred_at": "2026-10-11T16:00:00+08:00", "reason": "冲突",
                                        "simulation": "SIMULATED_TEST_ONLY"})
    if not gate2_again_api["ok"]:
        g4_problems.append(f"API 冲突提交必须按 0004 阻断：{str(gate2_again_api.get('message'))[:140]}")

    legacy = run_cli("g4_legacy_batch", ["record-simulated-gate2-decision", "--batch-dir", str(
        BATCHES_ROOT / "dev_receive_003_main_02"), "--decision-file", str(gate2_decision)], 1)
    if legacy["exit_code"] != 1:
        g4_problems.append("旧纯接收批次必须拒绝（不接管历史产物）")
    g4_probes.append({"case": "G4_LOCK_AND_LEGACY", "repeat_exit": repeat["exit_code"],
                      "gate1_exit": gate1_again["exit_code"], "prepare_exit": prepare_again["exit_code"],
                      "api_exit": gate2_again_api.get("exception_class"),
                      "legacy_exit": legacy["exit_code"],
                      "checkpoints_unchanged": fixed_before == fixed_after, "ok": True})
    record("G4_DECISION_LOCK_AND_LEGACY", "flow", g4_problems, probes=g4_probes)

    # =====================================================================
    # G5：0004 篡改（在专供探针的真实批次上造样，逐项即时恢复原位）
    # =====================================================================
    g5_problems: list = []
    g5_probes: list = []
    g5_base = batch_path("g5_base")
    run_cli("g5_start", ["start", "--workbook", str(C02_WORKBOOK), "--batch-dir", str(g5_base),
                         "--source-description", "0004 篡改探针基准（C02 小样，专供探针）"], 0)
    run_cli("g5_gate1", ["record-simulated-decision", "--batch-dir", str(g5_base),
                         "--decision-file", str(write_decision("g5_gate1", g5_base, "GATE1", 1,
                                                               "APPROVE"))], 0)
    run_cli("g5_prepare", ["prepare-gate2", "--batch-dir", str(g5_base)], 0)
    run_cli("g5_gate2", ["record-simulated-gate2-decision", "--batch-dir", str(g5_base),
                         "--decision-file", str(write_decision("g5_gate2", g5_base, "GATE2", 3,
                                                               "APPROVE"))], 0)
    g5_positive = run_cli("g5_positive", ["status", "--batch-dir", str(g5_base)], 0)
    if g5_positive["exit_code"] != 0 or g5_positive["payload"].get("phase") != "DEV_GATE2_APPROVED":
        g5_problems.append("G5 探针基准批次必须先是合法 DEV_GATE2_APPROVED")

    cp4_path = g5_base / "workflow" / "checkpoints" / "0004.json"
    report_path = g5_base / "workflow" / "gate2" / "load_report.json"
    database_path = host._gate2_paths(g5_base, "probe")["database_path"]

    def tamper_json(path: Path, mutate) -> list:
        original = path.read_bytes()
        payload = json.loads(original.decode("utf-8"))
        mutate(payload)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return [(path, original)]

    def tamper_bytes(path: Path, extra: bytes) -> list:
        original = path.read_bytes()
        path.write_bytes(original + extra)
        return [(path, original)]

    def tamper_new_file(path: Path) -> list:
        path.write_text("{}", encoding="utf-8")
        return [(path, None)]

    def restore(files: list) -> None:
        for path, original in files:
            if original is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_bytes(original)

    def tamper_probe(label: str, target: str, mutate) -> None:
        """造样（仅本测试专供批次）→ 本次 status 即按目标原因拒绝 → 即时恢复并复核正向。"""
        files = mutate()
        counts["fault_injections"] += 1
        entry = run_cli(label, ["status", "--batch-dir", str(g5_base)], 1)
        message = str(entry["payload"].get("message")) if entry["payload"] else entry["stderr_tail"]
        ok = entry["exit_code"] == 1 and target in message
        if not ok:
            g5_problems.append(f"{label} 必须按 {target} 阻断（exit={entry['exit_code']}）：{message[:200]}")
        restore(files)
        restored_ok = all((not path.exists()) if original is None else (path.read_bytes() == original)
                          for path, original in files)
        control = run_cli(f"{label}_restored", ["status", "--batch-dir", str(g5_base)], 0)
        if not restored_ok or control["exit_code"] != 0:
            g5_problems.append(f"{label} 造样后未能恢复原位（restored={restored_ok}, "
                               f"control_exit={control['exit_code']}）")
        g5_probes.append({"case": f"G5_{label}", "exit": entry["exit_code"], "target": target,
                          "message": message[:220], "restored": restored_ok,
                          "control_exit": control["exit_code"],
                          "note": "造样仅在本探针专供批次上，随后即时恢复原位", "ok": ok})

    tamper_probe("prev_link", "previous_file_sha256",
                 lambda: tamper_json(cp4_path, lambda payload: payload.__setitem__(
                     "previous_file_sha256", "0" * 64)))
    tamper_probe("operation_decision", "operation.decision",
                 lambda: tamper_json(cp4_path, lambda payload: payload["operation"]["decision"].__setitem__(
                     "reason", "被改写的理由")))
    tamper_probe("phase_forged", "phase_after",
                 lambda: tamper_json(cp4_path, lambda payload: payload["operation"].__setitem__(
                     "phase_after", "DEV_GATE2_PENDING")))
    tamper_probe("not_gate2_operation", "operation.kind",
                 lambda: tamper_json(cp4_path, lambda payload: payload["operation"].__setitem__(
                     "kind", "SIMULATED_GATE1_DECISION")))
    tamper_probe("body_sha", "decision_sha256",
                 lambda: tamper_json(cp4_path, lambda payload: payload["operation"].__setitem__(
                     "decision_sha256", "1" * 64)))
    tamper_probe("revision", "revision",
                 lambda: tamper_json(cp4_path, lambda payload: payload.__setitem__("revision", 3)))
    tamper_probe("database_bytes", "database_sha256",
                 lambda: tamper_bytes(database_path, b"-- tampered"))
    tamper_probe("load_report_bytes", "load_report",
                 lambda: tamper_bytes(report_path, b"\n"))
    tamper_probe("unknown_0005", "0005.json",
                 lambda: tamper_new_file(g5_base / "workflow" / "checkpoints" / "0005.json"))

    # 副本现场：路径派生值指向原批次 → 必须拒绝（副本不计真实接收／标准化／装载）
    inconsistent = copy_batch("g5_copy_inconsistent", main_batch)
    copy_entry = run_cli("g5_copy_inconsistent", ["status", "--batch-dir", str(inconsistent)], 1)
    copy_message = str(copy_entry["payload"].get("message")) if copy_entry["payload"] else ""
    copy_ok = copy_entry["exit_code"] == 1 and ("database_path" in copy_message
                                                or "output_relative" in copy_message
                                                or "database_sha256" in copy_message)
    if not copy_ok:
        g5_problems.append(f"路径派生不一致的副本现场必须被拒绝：exit={copy_entry['exit_code']} "
                           f"msg={copy_message[:180]}")
    g5_probes.append({"case": "G5_COPY_INCONSISTENT_PATH", "exit": copy_entry["exit_code"],
                      "message": copy_message[:200],
                      "note": "造样副本：其 artifacts 仍指向原批次的推导路径，宿主必须拒绝而非照单接收",
                      "ok": copy_ok})
    record("G5_CHECKPOINT_TAMPERING", "flow", g5_problems, probes=g5_probes)

    # =====================================================================
    # G6：0004 真实 writer 部分写入与写后抛错
    # =====================================================================
    g6_problems: list = []
    g6_probes: list = []
    writer_batch = batch_path("g6_writer")
    run_cli("g6_start", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir", str(writer_batch),
                         "--source-description", "0004 writer 故障用例"], 0)
    run_cli("g6_gate1", ["record-simulated-decision", "--batch-dir", str(writer_batch),
                         "--decision-file", str(write_decision("g6_gate1", writer_batch, "GATE1", 1,
                                                               "APPROVE"))], 0)
    run_cli("g6_prepare", ["prepare-gate2", "--batch-dir", str(writer_batch)], 0)
    writer_decision = json.loads(write_decision("g6_gate2", writer_batch, "GATE2", 3, "APPROVE").read_text(
        encoding="utf-8"))
    old_hashes_before = {rev: sha256(writer_batch / "workflow" / "checkpoints" / f"{rev:04d}.json")
                         for rev in (1, 2, 3)}
    sentinel = "SENTINEL-TASK012-0004-PARTIAL-WRITE"
    fault_state = {"opens": 0, "writes": 0, "raises": 0, "full_text": None, "full_bytes": None,
                   "full_sha256": None, "target": writer_batch / "workflow" / "checkpoints" / "0004.json"}
    real_open = open
    real_writer = host._write_exclusive_json
    fault_state: dict

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
            if fault_state["full_text"] is None:
                fault_state["full_text"] = text
                fault_state["full_bytes"] = len(text.encode("utf-8"))
                fault_state["full_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunk = text[: self._remaining]
            written = self._handle.write(chunk)
            self._remaining -= len(chunk)
            self.bytes_written += len(chunk)
            fault_state["writes"] += 1
            if self._remaining <= 0:
                fault_state["raises"] += 1
                raise OSError(sentinel)
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
            fault_state["opens"] += 1
            return FaultyHandle(handle, 40)
        return handle

    import builtins as _builtins
    original_open = _builtins.open
    _builtins.open = faulty_open
    counts["fault_injections"] += 1
    writer_exception = None
    try:
        try:
            host.record_simulated_gate2_decision(writer_batch, writer_decision)
        except Exception as exc:  # noqa: BLE001
            writer_exception = exc
    finally:
        _builtins.open = original_open
        host._write_exclusive_json = real_writer
    half = fault_state["target"]
    half_bytes = half.stat().st_size if half.is_file() else 0
    old_hashes_after = {rev: sha256(writer_batch / "workflow" / "checkpoints" / f"{rev:04d}.json")
                        for rev in (1, 2, 3)}
    cause = getattr(writer_exception, "__cause__", None)
    writer_ok = (fault_state["opens"] == 1 and fault_state["writes"] == 1 and fault_state["raises"] == 1
                 and isinstance(writer_exception, host.WorkflowHostError)
                 and isinstance(cause, OSError) and str(cause) == sentinel
                 and 0 < half_bytes < fault_state["full_bytes"]
                 and old_hashes_before == old_hashes_after and half.is_file())
    if not writer_ok:
        g6_problems.append(f"0004 真实 writer 部分写入未按预期：{fault_state} "
                           f"half={half_bytes}/{fault_state['full_bytes']} "
                           f"exc={type(writer_exception).__name__} cause={cause!r}")
    writer_status = run_cli("g6_writer_status", ["status", "--batch-dir", str(writer_batch)], 1)
    if writer_status["exit_code"] != 1:
        g6_problems.append("半文件 0004 之后的恢复必须拒绝")
    # 完整 writer 证据：原 UTF-8 字节另存 + 文件字节数/哈希核对 + 两组真实哈希与异常链
    writer_full_text = fault_state.get("full_text")
    writer_full_path = container / "writer_full_expected_0004.json"
    writer_full_saved = {"saved": False}
    if isinstance(writer_full_text, str):
        with open(writer_full_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(writer_full_text)
        saved_bytes = writer_full_path.stat().st_size
        saved_sha = sha256(writer_full_path)
        try:
            parsed_full = json.loads(writer_full_path.read_text(encoding="utf-8"))
            full_parses = isinstance(parsed_full, dict) and set(parsed_full) >= {
                "checkpoint_version", "revision", "previous_file_sha256", "batch_id",
                "host_manifest_file_sha256", "workflow", "operation"}
        except json.JSONDecodeError:
            full_parses = False
        writer_full_saved = {"saved": True, "path": str(writer_full_path.relative_to(PROJECT_ROOT)),
                             "file_bytes": saved_bytes, "file_sha256": saved_sha,
                             "captured_utf8_bytes": fault_state["full_bytes"],
                             "captured_utf8_sha256": fault_state["full_sha256"],
                             "bytes_match_capture": saved_bytes == fault_state["full_bytes"],
                             "sha_match_capture": saved_sha == fault_state["full_sha256"],
                             "parses_as_complete_checkpoint": full_parses}
        if not (writer_full_saved["bytes_match_capture"] and writer_full_saved["sha_match_capture"]
                and full_parses):
            g6_problems.append(f"完整待写 0004 证据保存不一致：{writer_full_saved}")
    else:
        g6_problems.append("未捕获到 writer 完整待写文本")
    writer_evidence = {
        "case": "G6_0004_PARTIAL_WRITE_EVIDENCE",
        "sentinel": sentinel,
        "stage_order": ["_write_exclusive_json:open(exclusive)", "FaultyHandle.write(部分内容)",
                        "OSError(sentinel)", "WorkflowHostError(写入失败，阶段 record_gate2)"],
        "opens": fault_state["opens"], "writes": fault_state["writes"], "raises": fault_state["raises"],
        "partial_bytes": half_bytes, "full_utf8_bytes": fault_state["full_bytes"],
        "full_utf8_sha256": fault_state["full_sha256"],
        "partial_less_than_full": 0 < half_bytes < fault_state["full_bytes"],
        "old_checkpoint_sha256_before": {str(rev): old_hashes_before[rev] for rev in (1, 2, 3)},
        "old_checkpoint_sha256_after": {str(rev): old_hashes_after[rev] for rev in (1, 2, 3)},
        "old_checkpoints_unchanged": old_hashes_before == old_hashes_after,
        "exception_class": type(writer_exception).__name__ if writer_exception else None,
        "exception_message": str(writer_exception) if writer_exception else None,
        "cause_class": type(cause).__name__ if cause is not None else None,
        "cause_message": str(cause) if cause is not None else None,
        "half_file_preserved": half.is_file(),
        "full_text_saved": writer_full_saved,
        "ok": writer_ok,
    }
    (container / "writer_evidence.json").write_text(
        json.dumps(writer_evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    g6_probes.append({"case": "G6_0004_PARTIAL_WRITE", "opens": fault_state["opens"],
                      "writes": fault_state["writes"], "raises": fault_state["raises"],
                      "partial_bytes": half_bytes, "full_utf8_bytes": fault_state["full_bytes"],
                      "full_sha256": fault_state["full_sha256"],
                      "cause_class": type(cause).__name__ if cause is not None else None,
                      "old_checkpoint_sha256_before": {str(rev): old_hashes_before[rev] for rev in (1, 2, 3)},
                      "old_checkpoint_sha256_after": {str(rev): old_hashes_after[rev] for rev in (1, 2, 3)},
                      "old_checkpoints_unchanged": old_hashes_before == old_hashes_after,
                      "full_text_evidence": writer_full_saved,
                      "status_exit": writer_status["exit_code"], "ok": writer_ok})

    # 完整 0004 写后抛错：原命令失败，独立 status 按磁盘事实恢复
    post_batch = batch_path("g6_post_write_error")
    run_cli("g6_post_start", ["start", "--workbook", str(MAIN_WORKBOOK), "--batch-dir", str(post_batch),
                              "--source-description", "0004 写后抛错用例"], 0)
    run_cli("g6_post_gate1", ["record-simulated-decision", "--batch-dir", str(post_batch),
                              "--decision-file", str(write_decision("g6_post_gate1", post_batch, "GATE1", 1,
                                                                    "APPROVE"))], 0)
    run_cli("g6_post_prepare", ["prepare-gate2", "--batch-dir", str(post_batch)], 0)
    post_decision = json.loads(write_decision("g6_post_gate2", post_batch, "GATE2", 3, "APPROVE").read_text(
        encoding="utf-8"))

    def writer_then_raise(path, payload, stage):
        result = real_writer(path, payload, stage)
        raise host.WorkflowHostError(f"注入：完整 0004 写后抛错（{sentinel}-POST）", stage=stage)

    host._write_exclusive_json = writer_then_raise
    counts["fault_injections"] += 1
    post_exception = None
    try:
        host.record_simulated_gate2_decision(post_batch, post_decision)
    except Exception as exc:  # noqa: BLE001
        post_exception = exc
    finally:
        host._write_exclusive_json = real_writer
    if not isinstance(post_exception, host.WorkflowHostError):
        g6_problems.append("完整 0004 写后抛错时原命令必须失败（不得返回成功）")
    if not (post_batch / "workflow" / "checkpoints" / "0004.json").is_file():
        g6_problems.append("写后抛错现场的完整 0004 必须保留")
    recovered = run_cli("g6_post_status", ["status", "--batch-dir", str(post_batch)], 0)
    if recovered["exit_code"] != 0 or recovered["payload"].get("phase") != "DEV_GATE2_APPROVED":
        g6_problems.append(f"独立 status 必须按磁盘事实恢复“决定已记录”：exit={recovered['exit_code']}, "
                           f"phase={recovered['payload'].get('phase')!r}")
    g6_probes.append({"case": "G6_POST_WRITE_ERROR_RECOVERY",
                      "original_command_failed": isinstance(post_exception, host.WorkflowHostError),
                      "decision_persisted": (post_batch / "workflow" / "checkpoints" / "0004.json").is_file(),
                      "status_exit": recovered["exit_code"],
                      "phase": recovered["payload"].get("phase"), "ok": True})
    record("G6_WRITER_AND_POST_WRITE_ERROR", "flow", g6_problems, probes=g6_probes)

    # =====================================================================
    # G7：有界收尾变化（决定重放返回时改 0004；写后重放时改 load_report）
    # =====================================================================
    g7_problems: list = []
    g7_probes: list = []
    # 故障 wrapper 必须调用观察包装器（计数不绕过；不把包装器进入次数当真实核心执行次数）
    observed_record_decision = host.CONTROLLER_MODULE.record_dev_decision

    # 7a：合法的真实批次在决定纯重放返回时被改 0004 字节 → 本次即拒绝
    tail_batch = post_batch
    tail_cp4 = tail_batch / "workflow" / "checkpoints" / "0004.json"
    original_cp4 = tail_cp4.read_bytes()
    tail_hits = {"n": 0}

    def replay_then_change_0004(workflow, decision, *, current_bindings,
                                _observed=observed_record_decision):
        result = _observed(workflow, decision, current_bindings=current_bindings)
        if tail_hits["n"] == 0:
            payload = json.loads(tail_cp4.read_text(encoding="utf-8"))
            payload["operation"]["decision"]["reason"] = "收尾注入：决定重放返回时改 0004 字节"
            tail_cp4.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            tail_hits["n"] += 1
        return result

    before_cp4 = sha256(tail_cp4)
    host.CONTROLLER_MODULE.record_dev_decision = replay_then_change_0004  # 注入仅覆盖本探针
    counts["fault_injections"] += 1
    tail_probe = run_api("g7_tail_0004", host.inspect_dev_batch, expect_exception="WorkflowHostBlocked",
                         target="0004.json", batch_dir=tail_batch)
    host.CONTROLLER_MODULE.record_dev_decision = observed_record_decision
    after_cp4 = sha256(tail_cp4)
    tail_ok = (tail_hits["n"] == 1 and tail_probe["ok"] and before_cp4 != after_cp4)
    if not tail_ok:
        g7_problems.append(f"决定重放返回时改 0004 必须本次即拒绝：hits={tail_hits['n']} "
                           f"before==after={before_cp4 == after_cp4} "
                           f"msg={str(tail_probe.get('message'))[:200]}")
    tail_cp4.write_bytes(original_cp4)
    tail_control = run_cli("g7_tail_0004_restored", ["status", "--batch-dir", str(tail_batch)], 0)
    if tail_control["exit_code"] != 0:
        g7_problems.append("恢复 0004 原位后必须重新通过（造样已复原）")
    g7_probes.append({"case": "G7_TAIL_0004_CHANGE", "hits": tail_hits["n"],
                      "exception_class": tail_probe.get("exception_class"),
                      "message": str(tail_probe.get("message"))[:220],
                      "before": before_cp4, "after": after_cp4,
                      "restored_control_exit": tail_control["exit_code"], "ok": tail_ok})

    # 7b：真实批次停在 0003 pending，写后重放时改 load_report 字节 → 本次即拒绝；改动保留时恢复也拒绝
    report_base = batch_path("g7_report_base")
    run_cli("g7_report_start", ["start", "--workbook", str(C02_WORKBOOK), "--batch-dir", str(report_base),
                                "--source-description", "收尾变化探针基准（C02 小样，专供探针）"], 0)
    run_cli("g7_report_gate1", ["record-simulated-decision", "--batch-dir", str(report_base),
                                "--decision-file", str(write_decision("g7_report_gate1", report_base,
                                                                      "GATE1", 1, "APPROVE"))], 0)
    run_cli("g7_report_prepare", ["prepare-gate2", "--batch-dir", str(report_base)], 0)
    report_file = report_base / "workflow" / "gate2" / "load_report.json"
    original_report = report_file.read_bytes()
    report_hits = {"n": 0}

    def replay_then_change_report(workflow, decision, *, current_bindings,
                                  _observed=observed_record_decision):
        result = _observed(workflow, decision, current_bindings=current_bindings)
        report_hits["n"] += 1
        if report_hits["n"] == 2:  # 写后重放（第一次是写入前的决定复算）
            payload = json.loads(report_file.read_text(encoding="utf-8"))
            payload["tampered_note"] = "收尾注入：写后重放改 load_report 字节"
            report_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
        return result

    report_decision = json.loads(write_decision("g7_report_gate2", report_base, "GATE2", 3,
                                                "APPROVE").read_text(encoding="utf-8"))
    before_report = sha256(report_file)
    host.CONTROLLER_MODULE.record_dev_decision = replay_then_change_report
    counts["fault_injections"] += 1
    report_probe = run_api("g7_report_after_write", host.record_simulated_gate2_decision,
                           expect_exception="WorkflowHostBlocked", target="load_report",
                           batch_dir=report_base, decision=report_decision)
    host.CONTROLLER_MODULE.record_dev_decision = observed_record_decision
    after_report = sha256(report_file)
    later = run_cli("g7_report_later_status", ["status", "--batch-dir", str(report_base)], 1)
    report_ok = (report_hits["n"] >= 2 and report_probe["ok"] and before_report != after_report
                 and later["exit_code"] == 1 and "load_report" in str(later["payload"].get("message")))
    if not report_ok:
        g7_problems.append(f"写后重放改 load_report 必须本次即拒绝且改动保留时恢复也拒绝："
                           f"hits={report_hits['n']} probe_ok={report_probe['ok']} "
                           f"later_exit={later['exit_code']} msg={str(report_probe.get('message'))[:200]}")
    report_file.write_bytes(original_report)
    report_control = run_cli("g7_report_restored", ["status", "--batch-dir", str(report_base)], 0)
    if report_control["exit_code"] != 0:
        g7_problems.append("恢复 load_report 原位后必须重新通过")
    g7_probes.append({"case": "G7_TAIL_LOAD_REPORT_CHANGE", "hits": report_hits["n"],
                      "exception_class": report_probe.get("exception_class"),
                      "message": str(report_probe.get("message"))[:220],
                      "before": before_report, "after": after_report,
                      "later_status_exit": later["exit_code"],
                      "restored_control_exit": report_control["exit_code"], "ok": report_ok})

    positive = run_cli("g7_positive", ["status", "--batch-dir", str(main_batch)], 0)
    if positive["exit_code"] != 0:
        g7_problems.append("未变化的正常批次不得被误拒")
    g7_probes.append({"case": "G7_POSITIVE_CONTROL", "exit": positive["exit_code"],
                      "phase": positive["payload"].get("phase"), "ok": positive["exit_code"] == 0})
    record("G7_BOUNDED_TAIL_CHANGES", "flow", g7_problems, probes=g7_probes)

    # =====================================================================
    # G8：只读与静态守卫、隔离自测、计数
    # =====================================================================
    g8_problems: list = []
    g8_probes: list = []
    guard_batch = main_batch  # 真实批次；守卫只用只读 API，不造副本（副本的推导路径与记录不一致）
    tree_before = {str(p.relative_to(guard_batch)): sha256(p)
                   for p in sorted(guard_batch.rglob("*")) if p.is_file()}
    db_path = host._gate2_paths(guard_batch, "guard")["database_path"]
    guard_phase_expected = "DEV_GATE2_APPROVED"
    db_before = sha256(db_path)
    calls = {"subprocess": 0, "normalize": 0, "load": 0, "socket": 0}

    def guard_subprocess(*args, **kwargs):
        calls["subprocess"] += 1
        raise AssertionError("status 守卫：不得启动子进程")

    def guard_normalize(*args, **kwargs):
        calls["normalize"] += 1
        raise AssertionError("status 守卫：不得调用标准化")

    def guard_load(*args, **kwargs):
        calls["load"] += 1
        raise AssertionError("status 守卫：不得调用装载")

    import socket as _socket
    real_socket = _socket.socket

    def guard_socket(*args, **kwargs):
        calls["socket"] += 1
        raise AssertionError("status 守卫：不得建立网络连接")

    real_subprocess_run = host.subprocess.run
    real_norm = host.NORMALIZER_MODULE.normalize_workbook
    real_load_fn = host.STORE_MODULE.load_normalized_to_sqlite
    host.subprocess.run = guard_subprocess
    host.NORMALIZER_MODULE.normalize_workbook = guard_normalize
    host.STORE_MODULE.load_normalized_to_sqlite = guard_load
    _socket.socket = guard_socket
    try:
        guard_result = host.inspect_dev_batch(guard_batch)
        guard_ok = guard_result["phase"] == guard_phase_expected and all(v == 0 for v in calls.values())
    except Exception as exc:  # noqa: BLE001
        guard_ok = False
        guard_result = {"exception": f"{type(exc).__name__}: {exc}"}
    finally:
        host.subprocess.run = real_subprocess_run
        host.NORMALIZER_MODULE.normalize_workbook = real_norm
        host.STORE_MODULE.load_normalized_to_sqlite = real_load_fn
        _socket.socket = real_socket
    tree_after = {str(p.relative_to(guard_batch)): sha256(p)
                  for p in sorted(guard_batch.rglob("*")) if p.is_file()}
    if not guard_ok:
        g8_problems.append(f"status 只读守卫失败：calls={calls}, result={str(guard_result)[:200]}")
    if tree_before != tree_after or sha256(db_path) != db_before:
        g8_problems.append("status 不得写入批次树或数据库")

    host_source = HOST.read_text(encoding="utf-8")
    import ast as _ast
    host_tree = _ast.parse(host_source)
    imported: set = set()
    for node in _ast.walk(host_tree):
        if isinstance(node, _ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, _ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    allowed_imports = {"argparse", "copy", "hashlib", "importlib", "json", "os", "re", "subprocess",
                       "sys", "datetime", "pathlib", "ast", "builtins", "__future__"}
    forbidden_imports = sorted(imported - allowed_imports)
    called_forbidden = [name for name in ("screen_demo_sqlite", "crosscheck_demo_rules",
                                         "build_demo_fact_packet", "generate_demo_data")
                        if f"{name}." in host_source and f"_load_upstream_module" not in host_source]
    if forbidden_imports:
        g8_problems.append(f"宿主只允许标准库导入，实际出现：{forbidden_imports}")
    call_roots = set()
    for node in _ast.walk(host_tree):
        if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute):
            value = node.func.value
            if isinstance(value, _ast.Name):
                call_roots.add(value.id)
    module_call_roots = {name for name in call_roots if name.endswith("_MODULE")}
    allowed_call_roots = {"CONTROLLER_MODULE", "NORMALIZER_MODULE", "STORE_MODULE"}
    forbidden_calls = sorted(module_call_roots - allowed_call_roots)
    if forbidden_calls:
        g8_problems.append(f"宿主只允许调用冻结控制器／标准化器／装载器的公共 API，"
                           f"实际出现调用根：{forbidden_calls}")
    for name in ("screen_demo_sqlite", "crosscheck_demo_rules", "build_demo_fact_packet",
                 "generate_demo_data"):
        if f"import {name}" in host_source or f"from {name}" in host_source:
            g8_problems.append(f"宿主不得导入 {name}")
    for token in ("ground_truth", "openai", "anthropic", "requests."):
        if f'"{token}' in host_source.replace("_sha256", ""):
            g8_problems.append(f"宿主不得引用 {token}")
    subprocess_calls = host_source.count("subprocess.run(")
    if subprocess_calls != 1:
        g8_problems.append(f"宿主只允许一个子进程调用点（冻结接收器），实际 {subprocess_calls}")
    if "record-simulated-gate2-decision" not in host_source or "prepare-gate2" not in host_source:
        g8_problems.append("宿主必须提供 prepare-gate2 与 record-simulated-gate2-decision")
    g8_probes.append({"case": "G8_READONLY_AND_STATIC", "upstream_module_handles":
                      sorted(name for name in call_roots if name.endswith("_MODULE")),
                      "guard_calls": calls,
                      "tree_unchanged": tree_before == tree_after, "database_unchanged":
                      sha256(db_path) == db_before, "imports": sorted(imported),
                      "forbidden_imports": forbidden_imports, "forbidden_calls": forbidden_calls,
                      "subprocess_calls": subprocess_calls, "ok": not g8_problems})

    # 隔离 matcher 自测：类别正确但目标原因不符必须判失败
    class _BlockedLike(host.WorkflowHostBlocked):
        pass

    matcher_cases = [
        {"name": "类别+目标原因均正确", "expect": True,
         "actual": matches(host.WorkflowHostBlocked("字段 0004.json 不可用：xxx"), "WorkflowHostBlocked",
                           "0004.json")},
        {"name": "类别正确、目标原因不符", "expect": False,
         "actual": matches(host.WorkflowHostBlocked("字段 0003.json 不可用：xxx"), "WorkflowHostBlocked",
                           "0004.json")},
        {"name": "类别不符", "expect": False,
         "actual": matches(host.WorkflowHostError("字段 0004.json 不可用：xxx"), "WorkflowHostBlocked",
                           "0004.json")},
    ]
    matcher_self_test = {"case": "TASK012_matcher_self_test", "cases": matcher_cases,
                         "ok": all(item["expect"] == item["actual"] for item in matcher_cases)}
    if not matcher_self_test["ok"]:
        failures.append({"case": "TASK012_MATCHER_SELF_TEST", "kind": "selftest", "result": "FAIL",
                         "problems": [str(matcher_cases)]})

    record("G8_GUARDS_AND_COUNTS", "flow", g8_problems, probes=g8_probes)

    # =====================================================================
    # G9：R1 收尾探针（F01 0004 进入最终复测；F02 最后一次控制器调用后真实复测绑定）
    # =====================================================================
    g9_problems: list = []
    g9_probes: list = []
    observed_check_action = host.CONTROLLER_MODULE.check_dev_action

    def make_distinct_batch(leaf: str, workbook: Path, note: str) -> Path:
        target = batch_path(leaf)
        run_cli(f"{leaf}_start", ["start", "--workbook", str(workbook), "--batch-dir", str(target),
                                  "--source-description", note], 0)
        run_cli(f"{leaf}_gate1", ["record-simulated-decision", "--batch-dir", str(target),
                                  "--decision-file", str(write_decision(f"{leaf}_gate1", target,
                                                                        "GATE1", 1, "APPROVE"))], 0)
        run_cli(f"{leaf}_prepare", ["prepare-gate2", "--batch-dir", str(target)], 0)
        return target

    # 9a（F01）：record 最后一次 SCREEN 动作检查真实返回后改 0004.operation.phase_after → 本次即拒绝
    f01_batch = make_distinct_batch("g9_f01_tail", C02_WORKBOOK, "F01 收尾集合探针（C02 小样，专供探针）")
    f01_decision_path = write_decision("g9_f01_gate2", f01_batch, "GATE2", 3, "APPROVE")
    f01_decision = json.loads(f01_decision_path.read_text(encoding="utf-8"))
    f01_cp4 = f01_batch / "workflow" / "checkpoints" / "0004.json"
    f01_state = {"screen_returns": 0, "hits": 0, "before": None, "after": None, "injected_at_screen": None}

    def check_then_change_0004(workflow, action_name, *, current_bindings,
                               _observed=observed_check_action, _state=f01_state, _path=f01_cp4):
        result = _observed(workflow, action_name, current_bindings=current_bindings)
        if action_name == "SCREEN_AND_BUILD_FACTS":
            _state["screen_returns"] += 1
            if _state["hits"] == 0 and _path.is_file():
                payload = json.loads(_path.read_text(encoding="utf-8"))
                if payload["operation"].get("phase_after") == "DEV_GATE2_APPROVED":
                    _state["before"] = sha256(_path)
                    payload["operation"]["phase_after"] = "DEV_GATE2_HELD"
                    _path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
                    _state["after"] = sha256(_path)
                    _state["hits"] += 1
                    _state["injected_at_screen"] = _state["screen_returns"]
        return result

    host.CONTROLLER_MODULE.check_dev_action = check_then_change_0004
    counts["fault_injections"] += 1
    f01_probe = run_api("g9_f01_tail_0004", host.record_simulated_gate2_decision,
                        expect_exception="WorkflowHostBlocked", target="0004.json",
                        batch_dir=f01_batch, decision=f01_decision)
    host.CONTROLLER_MODULE.check_dev_action = observed_check_action
    f01_ok = (f01_state["hits"] == 1 and f01_probe["ok"]
              and f01_state["before"] is not None and f01_state["before"] != f01_state["after"])
    if not f01_ok:
        g9_problems.append(f"F01 必须本次即拒绝且指向 0004：hits={f01_state['hits']} "
                           f"probe_ok={f01_probe['ok']} before==after={f01_state['before'] == f01_state['after']} "
                           f"msg={str(f01_probe.get('message'))[:200]}")
    deliberate_tamper_batches.append(str(f01_batch.relative_to(PROJECT_ROOT)))  # 0004 篡改按探针要求保留
    f01_later = run_cli("g9_f01_later_status", ["status", "--batch-dir", str(f01_batch)], 1)
    if f01_later["exit_code"] != 1 or "phase_after" not in str(f01_later["payload"].get("message")):
        g9_problems.append(f"撤销 wrapper 后新进程 status 必须拒绝并指向 phase_after："
                           f"exit={f01_later['exit_code']} msg={str(f01_later['payload'].get('message'))[:160]}")
    f01_full = {
        "case": "G9_F01_TAIL_0004_EXPECTED_SET",
        "call": f01_probe["record"],
        "function": f01_probe["record"]["function"],
        "batch_dir": str(f01_batch.relative_to(PROJECT_ROOT)),
        "arguments": f01_probe["record"]["arguments"],
        "decision": {"path": str(f01_decision_path.relative_to(PROJECT_ROOT)),
                     "body": f01_decision,
                     "decision_body_sha256": decision_body_sha(f01_decision)},
        "expect_exception": "WorkflowHostBlocked", "target_reason": "workflow/checkpoints/0004.json",
        "outcome": f01_probe["record"]["outcome"],
        "injection": {"point": "record 最后一次 SCREEN_AND_BUILD_FACTS 动作检查真实返回之后",
                      "relation": "冻结 check_dev_action 先真实返回，随后才修改磁盘 0004（旧 JSON 已被消费）",
                      "target_file": str(f01_cp4.relative_to(PROJECT_ROOT)),
                      "field_changed": "operation.phase_after → DEV_GATE2_HELD",
                      "hits": f01_state["hits"],
                      "injected_at_screen_return": f01_state["injected_at_screen"],
                      "before_sha256": f01_state["before"], "after_sha256": f01_state["after"]},
        "later_cli": {"command": f01_later["command"], "exit_code": f01_later["exit_code"],
                      "stdout_path": f01_later["stdout_path"], "stderr_path": f01_later["stderr_path"],
                      "payload": f01_later["payload"], "stderr_tail": f01_later["stderr_tail"]},
        "current_call_rejected": bool(f01_probe["ok"]),
    }
    f01_ref = persist_probe_record("G9_F01_TAIL_0004_EXPECTED_SET", f01_full,
                                   expect_message=str(f01_probe.get("message")),
                                   expect_decision_body_sha256=decision_body_sha(f01_decision))
    if not f01_ref["full_record_checks"]["ok"]:
        g9_problems.append(f"F01 完整记录读回核对失败：{f01_ref['full_record_checks']}")
    g9_probes.append({"case": "G9_F01_TAIL_0004_EXPECTED_SET", "hits": f01_state["hits"],
                      "injected_at_screen_return": f01_state["injected_at_screen"],
                      "exception_class": f01_probe.get("exception_class"),
                      "message": str(f01_probe.get("message"))[:240],
                      "before": f01_state["before"], "after": f01_state["after"],
                      "later_cli_exit": f01_later["exit_code"],
                      "later_cli_message": str(f01_later["payload"].get("message"))[:200],
                      "current_call_rejected": bool(f01_probe["ok"]), **f01_ref,
                      "ok": f01_ok and f01_later["exit_code"] == 1
                      and f01_ref["full_record_checks"]["ok"]})

    # 9b（F02 record）：record 最后一次 SCREEN 动作检查真实返回后改快照 → 本次即拒绝
    f02_rec_batch = make_distinct_batch("g9_f02_record", C02_WORKBOOK, "F02 record 绑定收尾探针")
    f02_rec_decision_path = write_decision("g9_f02_record_gate2", f02_rec_batch, "GATE2", 3, "APPROVE")
    f02_rec_decision = json.loads(f02_rec_decision_path.read_text(encoding="utf-8"))
    f02_snapshot = f02_rec_batch / "source" / "input.xlsx"
    f02_rec_state = {"screen_returns": 0, "hits": 0, "before": None, "after": None}

    def check_then_change_snapshot(workflow, action_name, *, current_bindings,
                                   _observed=observed_check_action, _state=f02_rec_state,
                                   _snapshot=f02_snapshot, _batch=f02_rec_batch):
        result = _observed(workflow, action_name, current_bindings=current_bindings)
        if action_name == "SCREEN_AND_BUILD_FACTS":
            _state["screen_returns"] += 1
            if _state["hits"] == 0 and (_batch / "workflow" / "checkpoints" / "0004.json").is_file():
                _state["before"] = sha256(_snapshot)
                _snapshot.write_bytes(_snapshot.read_bytes() + b"R1")
                _state["after"] = sha256(_snapshot)
                _state["hits"] += 1
        return result

    f02_rec_original = f02_snapshot.read_bytes()
    host.CONTROLLER_MODULE.check_dev_action = check_then_change_snapshot
    counts["fault_injections"] += 1
    f02_rec_probe = run_api("g9_f02_record_tail", host.record_simulated_gate2_decision,
                            expect_exception="WorkflowHostBlocked", target="source/input.xlsx",
                            batch_dir=f02_rec_batch, decision=f02_rec_decision)
    host.CONTROLLER_MODULE.check_dev_action = observed_check_action
    f02_rec_ok = (f02_rec_state["hits"] == 1 and f02_rec_probe["ok"]
                  and f02_rec_state["before"] != f02_rec_state["after"])
    if not f02_rec_ok:
        g9_problems.append(f"F02 record 必须本次即拒绝并指出快照/绑定变化：hits={f02_rec_state['hits']} "
                           f"probe_ok={f02_rec_probe['ok']} msg={str(f02_rec_probe.get('message'))[:200]}")
    f02_rec_later = run_cli("g9_f02_record_later_status", ["status", "--batch-dir", str(f02_rec_batch)], 1)
    if f02_rec_later["exit_code"] != 1:
        g9_problems.append(f"撤销 wrapper 后新进程 status 必须拒绝：exit={f02_rec_later['exit_code']}")
    f02_snapshot.write_bytes(f02_rec_original)
    f02_rec_control = run_cli("g9_f02_record_restored", ["status", "--batch-dir", str(f02_rec_batch)], 0)
    if f02_rec_control["exit_code"] != 0:
        g9_problems.append("恢复快照原位后必须重新通过（未变化正向不误拒）")
    f02_rec_full = {
        "case": "G9_F02_RECORD_STATIC_BINDING_TAIL",
        "call": f02_rec_probe["record"],
        "function": f02_rec_probe["record"]["function"],
        "batch_dir": str(f02_rec_batch.relative_to(PROJECT_ROOT)),
        "arguments": f02_rec_probe["record"]["arguments"],
        "decision": {"path": str(f02_rec_decision_path.relative_to(PROJECT_ROOT)),
                     "body": f02_rec_decision,
                     "decision_body_sha256": decision_body_sha(f02_rec_decision)},
        "expect_exception": "WorkflowHostBlocked", "target_reason": "source/input.xlsx",
        "outcome": f02_rec_probe["record"]["outcome"],
        "injection": {"point": "record 最后一次 SCREEN_AND_BUILD_FACTS 动作检查真实返回之后",
                      "relation": "冻结 check_dev_action 先真实返回，随后才修改批次快照（旧读数已被消费）",
                      "target_file": str(f02_snapshot.relative_to(PROJECT_ROOT)),
                      "field_changed": "source/input.xlsx 追加字节（input_sha256 / receive_materials 变化）",
                      "hits": f02_rec_state["hits"],
                      "screen_returns_when_injected": f02_rec_state["screen_returns"],
                      "before_sha256": f02_rec_state["before"], "after_sha256": f02_rec_state["after"]},
        "later_cli": {"command": f02_rec_later["command"], "exit_code": f02_rec_later["exit_code"],
                      "stdout_path": f02_rec_later["stdout_path"],
                      "stderr_path": f02_rec_later["stderr_path"],
                      "payload": f02_rec_later["payload"], "stderr_tail": f02_rec_later["stderr_tail"]},
        "positive_control": {"restored_snapshot": True, "cli_command": f02_rec_control["command"],
                             "exit_code": f02_rec_control["exit_code"],
                             "stdout_path": f02_rec_control["stdout_path"],
                             "payload": f02_rec_control["payload"]},
        "current_call_rejected": bool(f02_rec_probe["ok"]),
    }
    f02_rec_ref = persist_probe_record("G9_F02_RECORD_STATIC_BINDING_TAIL", f02_rec_full,
                                       expect_message=str(f02_rec_probe.get("message")),
                                       expect_decision_body_sha256=decision_body_sha(f02_rec_decision))
    if not f02_rec_ref["full_record_checks"]["ok"]:
        g9_problems.append(f"F02 record 完整记录读回核对失败：{f02_rec_ref['full_record_checks']}")
    g9_probes.append({"case": "G9_F02_RECORD_STATIC_BINDING_TAIL", "hits": f02_rec_state["hits"],
                      "exception_class": f02_rec_probe.get("exception_class"),
                      "message": str(f02_rec_probe.get("message"))[:240],
                      "before": f02_rec_state["before"], "after": f02_rec_state["after"],
                      "later_cli_exit": f02_rec_later["exit_code"],
                      "later_cli_message": str(f02_rec_later["payload"].get("message"))[:200],
                      "restored_control_exit": f02_rec_control["exit_code"],
                      "current_call_rejected": bool(f02_rec_probe["ok"]), **f02_rec_ref,
                      "ok": f02_rec_ok and f02_rec_later["exit_code"] == 1
                      and f02_rec_ref["full_record_checks"]["ok"]})

    # 9c（F02 status）：已决定批次 status 最后一次动作检查真实返回后改快照 → 本次即拒绝
    f02_st_batch = make_distinct_batch("g9_f02_status", C02_WORKBOOK, "F02 status 绑定收尾探针")
    run_cli("g9_f02_status_decision", ["record-simulated-gate2-decision", "--batch-dir", str(f02_st_batch),
                                       "--decision-file", str(write_decision("g9_f02_status_gate2",
                                                                             f02_st_batch, "GATE2", 3,
                                                                             "APPROVE"))], 0)
    f02_st_snapshot = f02_st_batch / "source" / "input.xlsx"
    f02_st_original = f02_st_snapshot.read_bytes()
    f02_st_state = {"screen_returns": 0, "hits": 0, "before": None, "after": None}

    def check_then_change_snapshot_status(workflow, action_name, *, current_bindings,
                                          _observed=observed_check_action, _state=f02_st_state,
                                          _snapshot=f02_st_snapshot):
        result = _observed(workflow, action_name, current_bindings=current_bindings)
        if action_name == "SCREEN_AND_BUILD_FACTS":
            _state["screen_returns"] += 1
            if _state["screen_returns"] == 2 and _state["hits"] == 0:
                _state["before"] = sha256(_snapshot)
                _snapshot.write_bytes(_snapshot.read_bytes() + b"R1")
                _state["after"] = sha256(_snapshot)
                _state["hits"] += 1
        return result

    host.CONTROLLER_MODULE.check_dev_action = check_then_change_snapshot_status
    counts["fault_injections"] += 1
    f02_st_probe = run_api("g9_f02_status_tail", host.inspect_dev_batch,
                           expect_exception="WorkflowHostBlocked", target="source/input.xlsx",
                           batch_dir=f02_st_batch)
    host.CONTROLLER_MODULE.check_dev_action = observed_check_action
    f02_st_ok = (f02_st_state["hits"] == 1 and f02_st_probe["ok"]
                 and f02_st_state["before"] != f02_st_state["after"])
    if not f02_st_ok:
        g9_problems.append(f"F02 status 必须本次即拒绝：hits={f02_st_state['hits']} "
                           f"probe_ok={f02_st_probe['ok']} msg={str(f02_st_probe.get('message'))[:200]}")
    f02_st_later = run_cli("g9_f02_status_later", ["status", "--batch-dir", str(f02_st_batch)], 1)
    if f02_st_later["exit_code"] != 1:
        g9_problems.append(f"撤销 wrapper 后新进程 status 必须拒绝：exit={f02_st_later['exit_code']}")
    f02_st_snapshot.write_bytes(f02_st_original)
    f02_st_control = run_cli("g9_f02_status_restored", ["status", "--batch-dir", str(f02_st_batch)], 0)
    if f02_st_control["exit_code"] != 0:
        g9_problems.append("恢复快照原位后已决定批次必须重新正常恢复")
    f02_st_decision_payload = json.loads((f02_st_batch / "workflow" / "checkpoints" /
                                          "0004.json").read_text(encoding="utf-8"))
    f02_st_full = {
        "case": "G9_F02_STATUS_STATIC_BINDING_TAIL",
        "call": f02_st_probe["record"],
        "function": f02_st_probe["record"]["function"],
        "batch_dir": str(f02_st_batch.relative_to(PROJECT_ROOT)),
        "arguments": f02_st_probe["record"]["arguments"],
        "decision": {"path": str((f02_st_batch / "workflow" / "checkpoints" /
                                  "0004.json").relative_to(PROJECT_ROOT)),
                     "body": f02_st_decision_payload["operation"]["decision"],
                     "decision_body_sha256": decision_body_sha(
                         f02_st_decision_payload["operation"]["decision"])},
        "expect_exception": "WorkflowHostBlocked", "target_reason": "source/input.xlsx",
        "outcome": f02_st_probe["record"]["outcome"],
        "injection": {"point": "status 最后一次动作检查（other_actions 中第 2 次 SCREEN 检查）真实返回之后",
                      "relation": "冻结 check_dev_action 先真实返回，随后才修改批次快照",
                      "target_file": str(f02_st_snapshot.relative_to(PROJECT_ROOT)),
                      "field_changed": "source/input.xlsx 追加字节（input_sha256 / receive_materials 变化）",
                      "hits": f02_st_state["hits"],
                      "screen_returns_when_injected": f02_st_state["screen_returns"],
                      "before_sha256": f02_st_state["before"], "after_sha256": f02_st_state["after"]},
        "later_cli": {"command": f02_st_later["command"], "exit_code": f02_st_later["exit_code"],
                      "stdout_path": f02_st_later["stdout_path"],
                      "stderr_path": f02_st_later["stderr_path"],
                      "payload": f02_st_later["payload"], "stderr_tail": f02_st_later["stderr_tail"]},
        "positive_control": {"restored_snapshot": True, "cli_command": f02_st_control["command"],
                             "exit_code": f02_st_control["exit_code"],
                             "stdout_path": f02_st_control["stdout_path"],
                             "payload": f02_st_control["payload"]},
        "current_call_rejected": bool(f02_st_probe["ok"]),
    }
    f02_st_ref = persist_probe_record("G9_F02_STATUS_STATIC_BINDING_TAIL", f02_st_full,
                                      expect_message=str(f02_st_probe.get("message")),
                                      expect_decision_body_sha256=decision_body_sha(
                                          f02_st_decision_payload["operation"]["decision"]))
    if not f02_st_ref["full_record_checks"]["ok"]:
        g9_problems.append(f"F02 status 完整记录读回核对失败：{f02_st_ref['full_record_checks']}")
    g9_probes.append({"case": "G9_F02_STATUS_STATIC_BINDING_TAIL", "hits": f02_st_state["hits"],
                      "screen_returns": f02_st_state["screen_returns"],
                      "exception_class": f02_st_probe.get("exception_class"),
                      "message": str(f02_st_probe.get("message"))[:240],
                      "before": f02_st_state["before"], "after": f02_st_state["after"],
                      "later_cli_exit": f02_st_later["exit_code"],
                      "later_cli_message": str(f02_st_later["payload"].get("message"))[:200],
                      "restored_control_exit": f02_st_control["exit_code"],
                      "current_call_rejected": bool(f02_st_probe["ok"]), **f02_st_ref,
                      "ok": f02_st_ok and f02_st_later["exit_code"] == 1
                      and f02_st_ref["full_record_checks"]["ok"]})

    # 9d：未变化的 Gate2 pending / APPROVED / HELD / REJECTED 仍正常恢复（正向对照）
    for _case, _batch_dir in (("approved_gate2", tail_batch), ("approve", main_batch),
                              ("hold", batch_path("c02_hold")),
                              ("reject", batch_path("c02_reject"))):
        _entry = run_cli(f"g9_positive_{_case}", ["status", "--batch-dir", str(_batch_dir)], 0)
        if _entry["exit_code"] != 0:
            g9_problems.append(f"未变化的 {_case} 批次必须正常恢复：exit={_entry['exit_code']}")
        g9_probes.append({"case": f"G9_POSITIVE_{_case.upper()}", "exit": _entry["exit_code"],
                          "phase": _entry["payload"].get("phase"), "ok": _entry["exit_code"] == 0})
    record("G9_R1_FINAL_TAIL_PROBES", "flow", g9_problems, probes=g9_probes)

    # =====================================================================
    # G10：计数审计（在全部探针之后运行，覆盖本次全部真实调用）
    # =====================================================================
    g10_problems: list = []
    g10_probes: list = []
    # 计数：登记的真实启动与独立调用记录一一对应
    copy_paths = {item["copy"] for item in copy_records}
    receiver_records = []
    for record_path in sorted(batch_parent.rglob("receive_invocation.json")):
        batch_dir = record_path.parent.parent
        relative = str(batch_dir.relative_to(PROJECT_ROOT))
        if any(relative == c or relative.startswith(c + "/") for c in copy_paths):
            continue
        payload = json.loads(record_path.read_text(encoding="utf-8"))
        receiver_records.append({"batch": relative, "exit_code": payload["exit_code"],
                                 "command": payload["command"]})
    checker_records = []
    unreadable = []
    for manifest_path in sorted(batch_parent.rglob("batch_manifest.json")):
        batch_dir = manifest_path.parent
        relative = str(batch_dir.relative_to(PROJECT_ROOT))
        if any(relative == c or relative.startswith(c + "/") for c in copy_paths):
            continue
        if not manifest_path.is_file():
            unreadable.append(relative)
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest.get("checker_invocation") or {}).get("started") is True:
            checker_records.append({"batch": relative})
    counts["receiver_starts"] = len(receiver_records)
    counts["receiver_starts_host"] = len(receiver_records) - counts["receiver_starts_direct"]
    counts["checker_runs"] = len(checker_records)
    def audit_call_records(registered: list, records: list, copies: list) -> dict:
        """双向审计判定：正式 G10 与隔离内存对照共用同一规则。

        缺记录（登记了但没有独立调用记录）与未登记记录（有记录但未登记启动）都必须判不通过；
        `verdict` 即最终用于 G10 的成功/失败判定。副本按其自身路径层级排除。
        """
        copy_parts = [Path(item["copy"]).parts for item in copies]

        def under_copy(relative: str) -> bool:
            parts = Path(relative).parts
            return any(parts[: len(entry)] == entry for entry in copy_parts)

        registered_set = set(registered)
        observed_records = {item["batch"] for item in records}
        missing = sorted(item for item in registered
                         if item not in observed_records and not under_copy(item))
        unregistered = sorted(item["batch"] for item in records
                              if item["batch"] not in registered_set and not under_copy(item["batch"]))
        problems = []
        if missing:
            problems.append(f"已登记的真实接收启动缺少独立调用记录：{missing}")
        if unregistered:
            problems.append(f"存在未登记的接收调用记录：{unregistered}")
        return {"registered": len(registered), "records": len(records),
                "missing_records": missing, "unregistered_records": unregistered,
                "problems": problems, "verdict": "FAIL" if problems else "PASS", "ok": not problems}

    # 正式审计：缺记录／未登记记录都进入 G10 的正式 problems（→ G10 FAIL、入口不得退出 0）
    formal_audit = audit_call_records(expected_starts, receiver_records, copy_records)
    if not formal_audit["ok"]:
        g10_problems.extend(formal_audit["problems"])
    missing_records = formal_audit["missing_records"]
    unregistered_records = formal_audit["unregistered_records"]

    # 三个内存对照：同一 helper、同一判定规则，证明 G10 的成功/失败判定随之改变
    complete_control = audit_call_records(expected_starts, receiver_records, copy_records)
    dropped_target = receiver_records[0]["batch"] if receiver_records else None
    dropped_control = audit_call_records(expected_starts, receiver_records[1:], copy_records)
    extra_record = {"batch": str((batch_parent / "__in_memory_unregistered__").relative_to(PROJECT_ROOT)),
                    "exit_code": 0, "command": ["in-memory", "probe"]}
    unregistered_control = audit_call_records(expected_starts, [*receiver_records, extra_record], copy_records)
    def g10_verdict(problems: list) -> str:
        """G10 的正式成功/失败判定（与 record() 用法一致：problems 非空即 FAIL）。"""
        return "FAIL" if problems else "PASS"

    control_checks = {
        "complete_passes": complete_control["verdict"] == "PASS",
        "g10_verdict_fails_when_record_missing": (
            g10_verdict(list(g10_problems) + dropped_control["problems"]) == "FAIL"
            and g10_verdict(list(g10_problems)) == formal_audit["verdict"]),
        "g10_verdict_fails_when_record_unregistered": (
            g10_verdict(list(g10_problems) + unregistered_control["problems"]) == "FAIL"),
        "dropped_record_fails_with_missing": (dropped_control["verdict"] == "FAIL"
                                             and bool(dropped_control["missing_records"])),
        "unregistered_record_fails_with_unregistered": (
            unregistered_control["verdict"] == "FAIL"
            and bool(unregistered_control["unregistered_records"])),
        "verdict_changes_for_both_directions": (complete_control["verdict"] != dropped_control["verdict"]
                                               and complete_control["verdict"]
                                               != unregistered_control["verdict"]),
    }
    count_self_test = {
        "case": "TASK012_count_self_test",
        "shared_rule": "audit_call_records（正式 G10 判定与三项内存对照使用同一规则）",
        "formal_audit": {"registered": formal_audit["registered"], "records": formal_audit["records"],
                         "missing_records": formal_audit["missing_records"],
                         "unregistered_records": formal_audit["unregistered_records"],
                         "verdict": formal_audit["verdict"]},
        "controls": {
            "complete_registration_matches_records": {
                "verdict": complete_control["verdict"], "missing": complete_control["missing_records"],
                "unregistered": complete_control["unregistered_records"]},
            "one_registered_record_removed": {
                "dropped_record": dropped_target, "verdict": dropped_control["verdict"],
                "missing": dropped_control["missing_records"],
                "unregistered": dropped_control["unregistered_records"]},
            "one_unregistered_record_added": {
                "added_record": extra_record["batch"], "verdict": unregistered_control["verdict"],
                "missing": unregistered_control["missing_records"],
                "unregistered": unregistered_control["unregistered_records"]},
        },
        "control_checks": control_checks,
        "g10_verdict_controls": {
            "formal": g10_verdict(list(g10_problems)),
            "if_one_registered_record_removed": g10_verdict(
                list(g10_problems) + dropped_control["problems"]),
            "if_one_unregistered_record_added": g10_verdict(
                list(g10_problems) + unregistered_control["problems"]),
            "note": "与正式 G10 使用同一判定表达式；缺记录/未登记记录都会把正式判定翻成 FAIL。",
        },
        "g10_rule": ("G10 正式判定 = g10_problems 为空则 PASS、否则 FAIL；"
                     "缺记录与未登记记录都由 audit_call_records 产出正式 problems，故正式入口不会退出 0。"),
    }
    count_self_test["ok"] = all(control_checks.values())
    if not count_self_test["ok"]:
        failures.append({"case": "TASK012_COUNT_SELF_TEST", "kind": "selftest", "result": "FAIL",
                         "problems": [key for key, value in control_checks.items() if not value]})
    (container / "count_self_test.json").write_text(
        json.dumps(count_self_test, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # 0004 分类：原始文件数 / 可解析原始记录 / 副本记录 / 半文件（副本用 Path 层级识别，不拼字符串前缀）
    def _under_copy(path: Path) -> bool:
        parts = path.relative_to(PROJECT_ROOT).parts
        for item in copy_records:
            copy_parts = Path(item["copy"]).parts
            if parts[: len(copy_parts)] == copy_parts:
                return True
        return False

    raw_0004 = sorted(batch_parent.rglob("workflow/checkpoints/0004.json"))
    originals_0004 = [path for path in raw_0004 if not _under_copy(path)]
    copies_0004 = [path for path in raw_0004 if _under_copy(path)]
    half_files_0004, parsable_originals = [], []
    for path in raw_0004:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            half_files_0004.append(str(path.relative_to(PROJECT_ROOT)))
            continue
        if not _under_copy(path):
            parsable_originals.append(path)
    # “合法决定已保存”必须有恢复／重放证据：对每份原始记录做一次真实恢复核验
    verified_by_recovery, illegal_original = [], []
    deliberately_tampered = []
    for path in parsable_originals:
        batch_dir = path.parent.parent.parent
        batch_rel = str(batch_dir.relative_to(PROJECT_ROOT))
        if batch_rel in deliberate_tamper_batches:
            deliberately_tampered.append({"batch": batch_rel, "reason": "探针故意保留的非法现场"})
            continue
        try:
            inspected = host.inspect_dev_batch(batch_dir)
        except Exception as exc:  # noqa: BLE001
            illegal_original.append({"batch": str(batch_dir.relative_to(PROJECT_ROOT)),
                                     "exception": f"{type(exc).__name__}: {str(exc)[:160]}"})
            continue
        if str(inspected.get("phase", "")).startswith("DEV_GATE2_"):
            verified_by_recovery.append({"batch": str(batch_dir.relative_to(PROJECT_ROOT)),
                                         "phase": inspected.get("phase")})
        else:
            illegal_original.append({"batch": str(batch_dir.relative_to(PROJECT_ROOT)),
                                     "phase": inspected.get("phase")})
    counts["gate2_decision_raw_files"] = len(raw_0004)
    counts["gate2_decision_original_parsable"] = len(parsable_originals)
    counts["gate2_decision_copies"] = len(copies_0004)
    counts["gate2_decision_half_files"] = len(half_files_0004)
    counts["gate2_decisions_verified_by_recovery"] = len(verified_by_recovery)
    decision_files_audit = {
        "raw_files": len(raw_0004), "raw_originals": len(originals_0004),
        "original_parsable": len(parsable_originals), "copies": len(copies_0004),
        "half_files": half_files_0004,
        "verified_by_recovery": verified_by_recovery, "illegal_original": illegal_original,
        "deliberately_tampered_left": deliberately_tampered,
        "note": ("原始文件数不是已保存决定数；HOLD/REJECT 同样是决定；"
                 "合法决定以恢复／重放证据为准，完整 JSON 不是充分条件。"),
    }
    if illegal_original:
        g10_problems.append(f"存在原始 0004 记录无法按恢复协议确认：{illegal_original}")
    # 双向核对已由上方共用规则 audit_call_records 完成（missing 与 unregistered 均进入 G10 正式 problems）
    entry_events = {"api_events": api_events, "controller_events": controller_events,
                    "controller_sample_events": controller_sample_events,
                    "counts": {"host_api_calls": counts["host_api_calls"],
                               "controller_replay_calls_inproc": counts["controller_replay_calls_inproc"],
                               "controller_sample_calls": counts["controller_sample_calls"]},
                    "note": ("紧凑入口事件列表：只留入口名/顺序/返回或异常分类等计数证据，"
                             "不为每次内部重放复制完整 workflow。")}
    events_path = container / "entry_events.json"
    events_path.write_text(json.dumps(entry_events, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    events_readback = json.loads(events_path.read_text(encoding="utf-8"))
    events_checks = {
        "readback_identical": events_readback == entry_events,
        "api_events_match_count": len(api_events) == counts["host_api_calls"],
        "controller_events_match_count": len(controller_events) == counts["controller_replay_calls_inproc"],
        "controller_sample_events_match_count": (len(controller_sample_events)
                                                 == counts["controller_sample_calls"]),
    }
    if not all(events_checks.values()):
        g10_problems.append(f"入口事件列表与计数不一致：{events_checks}")
    g10_probes.append({"case": "G10_COUNT_AUDIT", "receiver_records": len(receiver_records),
                      "checker_records": len(checker_records), "copies": len(copy_records),
                      "unreadable_manifests": unreadable,
                      "formal_audit_verdict": formal_audit["verdict"],
                      "missing_records": missing_records,
                      "unregistered_records": unregistered_records,
                      "decision_files_audit": decision_files_audit,
                      "host_api_events": len(api_events),
                      "controller_replay_events": len(controller_events),
                      "controller_sample_events": len(controller_sample_events),
                      "entry_events_file": "entry_events.json", "entry_events_checks": events_checks,
                      "count_self_test_file": "count_self_test.json",
                      "count_self_test_controls": count_self_test["control_checks"],
                      "matcher_self_test": matcher_self_test["ok"],
                      "count_self_test": count_self_test["ok"], "ok": not g10_problems})
    record("G10_COUNT_AUDIT", "flow", g10_problems, probes=g10_probes)

    # =====================================================================
    # 最终一次落盘并读回
    # =====================================================================
    protected_after = {str(p.relative_to(PROJECT_ROOT)): sha256(p) for p in PROTECTED if p.exists()}
    changed = [rel for rel, value in protected_before.items() if protected_after.get(rel) != value]
    if changed:
        failures.append({"case": "INTEGRITY_protected_files", "kind": "integrity", "result": "FAIL",
                         "problems": [f"受保护文件被修改：{changed}"]})
        print(f"[FAIL] INTEGRITY_protected_files 受保护文件被修改：{changed}")
    else:
        print(f"[PASS] INTEGRITY_protected_files 受保护文件哈希一致（{len(protected_before)} 个）")

    counts["real_approvals"] = 0
    summary_counts = dict(counts)
    final = {
        "task": "TASK-012",
        "out_dir": str(container),
        "batch_parent": str(batch_parent),
        "python": sys.version.split()[0],
        "host": {"path": str(HOST), "sha256": sha256(HOST), "version": host.HOST_VERSION},
        "guide_sha256": sha256(PROJECT_ROOT / "docs" / "WORKFLOW_HOST_GUIDE.md"),
        "counts": summary_counts,
        "checks": checks,
        "cli_logs": cli_logs,
        "failures": failures,
        "copies": copy_records,
        "receiver_records": receiver_records,
        "checker_records": checker_records,
        "self_tests": {"matcher_self_test": matcher_self_test, "count_self_test": count_self_test},
        "protected_files_count": len(protected_before),
        "protected_files_unchanged": not changed,
        "note": ("本入口只做开发态接收、显式模拟决定与真实标准化／装载；未执行规则筛查、复算、底稿或 AI。"
                 "模拟 APPROVE 不是真实批准。"),
    }
    save_problems: list = []
    artifacts = {"summary.json": final, "checks.json": checks, "cli_logs.json": cli_logs,
                 "self_tests.json": final["self_tests"], "counts.json": summary_counts}
    for name, payload in artifacts.items():
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
    readback_problems: list = []
    persisted = json.loads((container / "summary.json").read_text(encoding="utf-8"))
    persisted_counts = json.loads((container / "counts.json").read_text(encoding="utf-8"))
    if persisted["counts"] != persisted_counts:
        readback_problems.append("summary 与 counts.json 不一致")
    if len(persisted["checks"]) != len(checks) or len(persisted["failures"]) != len(failures):
        readback_problems.append("summary 与内存 checks／failures 数量不一致")
    if save_problems or readback_problems:
        failures.append({"case": "TASK012_FINAL_READBACK", "kind": "artifact", "result": "FAIL",
                         "problems": save_problems + readback_problems})
        print(f"[FAIL] TASK012_FINAL_READBACK {save_problems + readback_problems}")
    else:
        print("[PASS] TASK012_FINAL_READBACK 最终汇总一次落盘并读回一致")

    print()
    print(f"CLI：start {counts['start_cli']}／status {counts['status_cli']}／record {counts['record_cli']}／"
          f"prepare-gate2 {counts['prepare_cli']}／record-gate2 {counts['record_gate2_cli']}")
    print(f"公开宿主 API {counts['host_api_calls']}（含 status helper）；私有探针 {counts['private_probe_calls']}；"
          f"控制器造样调用 {counts['controller_sample_calls']}；"
          f"宿主内部控制器重放（进程内可观测）{counts['controller_replay_calls_inproc']}"
          f"（CLI 内 {counts['controller_replay_calls_cli_unobserved']}）")
    print(f"真实接收 {counts['receiver_starts']}（宿主 {counts['receiver_starts_host']} ＋ 直接 "
          f"{counts['receiver_starts_direct']}）、checker {counts['checker_runs']}、"
          f"进程内标准化／装载 {counts['normalize_calls_inproc']}／{counts['load_calls_inproc']}"
          f"（CLI 内未观测 {counts['normalize_calls_cli_unobserved']}／"
          f"{counts['load_calls_cli_unobserved']}，按成功 CLI 推导 {counts['normalize_calls_cli_derived']}／"
          f"{counts['load_calls_cli_derived']}）")
    print(f"副本 {counts['copies']}、故障注入 {counts['fault_injections']}、真实批准 "
          f"{counts['real_approvals']}、负向拒绝 {counts['rejections_observed']}")
    print(f"0004 文件：原始 {counts['gate2_decision_raw_files']}（可解析原始 "
          f"{counts['gate2_decision_original_parsable']}／副本 {counts['gate2_decision_copies']}／半文件 "
          f"{counts['gate2_decision_half_files']}）；经恢复核验的合法决定 "
          f"{counts['gate2_decisions_verified_by_recovery']}")
    print(f"真实入口事件：公开 API {len(api_events)}、宿主内部控制器重放 {len(controller_events)}、"
          f"测试造样 {len(controller_sample_events)}")
    print(f"测试失败 {len(failures)}；受保护文件前后哈希一致: {not changed}（{len(protected_before)} 个）")
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
