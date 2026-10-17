#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-009 开发态 Gate 1／Gate 2 流程控制内核：开发验证入口。

用法：

    & 'D:\\harness work\\audit_sa_project\\.venv\\Scripts\\python.exe' -B `
      'D:\\harness work\\audit_sa_project\\tests\\test_control_demo_workflow.py' `
      --out-dir 'D:\\harness work\\audit_sa_project\\data\\workflow_tests\\task009_01'

**本次验证的是控制协议**：入口重放既有 MAIN 的 checker_report／normalized／load_report 作为历史结果，
既没有实际运行上游程序，也没有产出新的规则结论。它**不证明真实管道按这个顺序执行**，
更**不能为旧开发产物追认真实批准**。所有决定都是测试人员显式提供的 `SIMULATED_TEST_ONLY` 模拟对象，
真实 `gate1_approval`／`gate2_approval` 始终为 null。

退出码：0 全部符合预期；1 断言或保护失败；2 参数或环境问题。
"""

from __future__ import annotations

import argparse
import builtins
import copy
import hashlib
import importlib.util
import inspect
import io
import json
import socket
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_TESTS_ROOT = (PROJECT_ROOT / "data" / "workflow_tests").resolve()
CONTROLLER = PROJECT_ROOT / "scripts" / "control_demo_workflow.py"
GPT_CASE = (PROJECT_ROOT / "data" / "sqlite_tests" / "task007_r2_gpt_20261011_081630" / "cases" / "MAIN").resolve()
BATCH_ID = "BATCH-2026-09-DEMO-001"
MODEL_FILES = {
    "control_demo_workflow": PROJECT_ROOT / "scripts" / "control_demo_workflow.py",
    "receive_demo_batch": PROJECT_ROOT / "scripts" / "receive_demo_batch.py",
    "check_demo_data": PROJECT_ROOT / "scripts" / "check_demo_data.py",
    "normalize_demo_data": PROJECT_ROOT / "scripts" / "normalize_demo_data.py",
    "store_demo_sqlite": PROJECT_ROOT / "scripts" / "store_demo_sqlite.py",
    "screen_demo_sqlite": PROJECT_ROOT / "scripts" / "screen_demo_sqlite.py",
    "crosscheck_demo_rules": PROJECT_ROOT / "scripts" / "crosscheck_demo_rules.py",
    "build_demo_fact_packet": PROJECT_ROOT / "scripts" / "build_demo_fact_packet.py",
}
RULE_FILES = {rule_id: PROJECT_ROOT / "sql" / "rules" / f"{rule_id.lower()}.sql" for rule_id in ("R01", "R02", "R03", "R04")}
PROTECTED_FILES = [
    CONTROLLER,
    *MODEL_FILES.values(),
    *RULE_FILES.values(),
    PROJECT_ROOT / "sql" / "demo_schema.sql",
    PROJECT_ROOT / "docs" / "SPEC_V1.md",
    PROJECT_ROOT / "docs" / "AUDIT_CONTRACT_DRAFT.md",
    PROJECT_ROOT / "docs" / "FACT_PACKET_GUIDE.md",
    PROJECT_ROOT / "docs" / "EXEC_REPORT_008_R1.md",
    PROJECT_ROOT / "tests" / "test_build_demo_fact_packet.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    print(f"RUNTIME_ERROR: {message}", file=sys.stderr)
    sys.exit(2)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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


def diff_paths(left, right, prefix: str = "") -> list:
    """仅用于保存绑定差异路径（证据），不做任何放行判断。"""
    if isinstance(left, dict) and isinstance(right, dict):
        paths: list = []
        for key in sorted(set(left) | set(right)):
            sub = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                paths.append(sub)
            else:
                paths.extend(diff_paths(left[key], right[key], sub))
        return paths
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [f"{prefix}.长度"]
        paths = []
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            paths.extend(diff_paths(left_item, right_item, f"{prefix}[{index}]"))
        return paths
    return [] if left == right else [prefix]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TASK-009 流程控制内核开发验证")
    parser.add_argument("--out-dir", required=True, help="data/workflow_tests 下尚不存在的测试容器")
    args = parser.parse_args(argv)

    container = Path(args.out_dir)
    container = container.resolve() if container.is_absolute() else (Path.cwd() / container).resolve()
    try:
        container.relative_to(WORKFLOW_TESTS_ROOT)
    except ValueError:
        fail(f"测试容器必须位于 {WORKFLOW_TESTS_ROOT} 之内：{container}")
    if container == WORKFLOW_TESTS_ROOT:
        fail("测试容器不能是 data/workflow_tests 本身")
    if container.exists():
        fail(f"测试容器已存在，拒绝覆盖历史：{container}")
    for required in (CONTROLLER, GPT_CASE / "checker_report.json", GPT_CASE / "normalized.json",
                     GPT_CASE / "load_report.json"):
        if not required.exists():
            fail(f"缺少必需输入：{required}")

    hashes_before = {str(path): sha256(path) for path in PROTECTED_FILES}
    container.mkdir(parents=True)
    original_stdout, original_stderr = sys.stdout, sys.stderr
    stdout_tee = Tee(original_stdout, container / "stdout.txt")
    stderr_tee = Tee(original_stderr, container / "stderr.txt")
    sys.stdout, sys.stderr = stdout_tee, stderr_tee

    controller = load_module(CONTROLLER, "workflow_under_test")
    checks: list = []
    failures: list = []
    sync_notes: list = []
    sync_cursor = {"value": 0}
    call_counts = {"create_dev_workflow": 0, "prepare_dev_gate": 0,
                   "record_dev_decision": 0, "check_dev_action": 0}
    last_calls: list = []
    real_create = controller.create_dev_workflow
    real_prepare = controller.prepare_dev_gate
    real_record = controller.record_dev_decision
    real_check = controller.check_dev_action

    def _capture(name: str, call_args, call_kwargs) -> None:
        if len(last_calls) < 4000:
            last_calls.append({
                "function": name,
                "args": copy.deepcopy(list(call_args)),
                "kwargs": {key: copy.deepcopy(value) for key, value in call_kwargs.items()},
                "live_args": list(call_args),
            })

    def counted_create(*call_args, **call_kwargs):
        call_counts["create_dev_workflow"] += 1
        _capture("create_dev_workflow", call_args, call_kwargs)
        return real_create(*call_args, **call_kwargs)

    def counted_prepare(*call_args, **call_kwargs):
        call_counts["prepare_dev_gate"] += 1
        _capture("prepare_dev_gate", call_args, call_kwargs)
        return real_prepare(*call_args, **call_kwargs)

    def counted_record(*call_args, **call_kwargs):
        call_counts["record_dev_decision"] += 1
        _capture("record_dev_decision", call_args, call_kwargs)
        return real_record(*call_args, **call_kwargs)

    def counted_check(*call_args, **call_kwargs):
        call_counts["check_dev_action"] += 1
        _capture("check_dev_action", call_args, call_kwargs)
        return real_check(*call_args, **call_kwargs)

    controller.create_dev_workflow = counted_create
    controller.prepare_dev_gate = counted_prepare
    controller.record_dev_decision = counted_record
    controller.check_dev_action = counted_check

    def record(case: str, kind: str, problems: list, **extra) -> None:
        detail = {"case": case, "kind": kind, "result": "PASS" if not problems else "FAIL",
                  "problems": problems, **extra}
        checks.append(detail)
        if problems:
            failures.append(detail)
        print(f"[{'PASS' if not problems else 'FAIL'}] {case}"
              + ("" if not problems else "  | " + " ; ".join(problems)))

    # ---------- 测试输入（只读既有开发结果，作为历史结果重放） ----------
    checker_report = json.loads((GPT_CASE / "checker_report.json").read_text(encoding="utf-8"))
    normalized = json.loads((GPT_CASE / "normalized.json").read_text(encoding="utf-8"))
    load_report = json.loads((GPT_CASE / "load_report.json").read_text(encoding="utf-8"))
    input_sha256 = checker_report["workbook"]["sha256"]
    bindings_base = {
        "input_sha256": input_sha256,
        "spec_sha256": sha256(PROJECT_ROOT / "docs" / "SPEC_V1.md"),
        "contract_draft_sha256": sha256(PROJECT_ROOT / "docs" / "AUDIT_CONTRACT_DRAFT.md"),
        "code_sha256": {key: sha256(path) for key, path in MODEL_FILES.items()},
        "rule_sql_sha256": {key: sha256(path) for key, path in RULE_FILES.items()},
        "config": dict(controller.FIXED_CONFIG),
    }
    scope_base = {
        "company": "澄明商贸有限公司",
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "cutoff_date": "2026-09-30",
        "currency": "CNY",
        "synthetic_data": True,
        "source_description": "合成 ERP 导出（演示用）；来源条件未知，按声明限制处理",
        "known_limitations": ["来源真实性与完整性未知", "只覆盖 2026 年 9 月"],
    }

    def bindings(**overrides) -> dict:
        payload = copy.deepcopy(bindings_base)
        for key, value in overrides.items():
            if key in ("code", "rule") and isinstance(value, dict):
                payload["code_sha256" if key == "code" else "rule_sql_sha256"].update(value)
            elif key == "config" and isinstance(value, dict):
                payload["config"].update(value)
            else:
                payload[key] = value
        return payload

    def gate1_materials(bindings_payload: dict | None = None, *, scope=None, evidence=None,
                        blocking=None, batch_id=BATCH_ID, mutate=None) -> dict:
        payload = {
            "batch_id": batch_id,
            "gate": "GATE1",
            "run_bindings_sha256": controller.canonical_sha256(bindings_payload or bindings_base),
            "scope": copy.deepcopy(scope if scope is not None else scope_base),
            "blocking_issues": list(blocking) if blocking is not None else [],
            "evidence": {"quality_report": copy.deepcopy(evidence if evidence is not None else checker_report)},
        }
        if mutate is not None:
            mutate(payload)
        return payload

    def gate2_materials(bindings_payload: dict | None = None, *, normalized_payload=None,
                        load_payload=None, scope=None, blocking=None, batch_id=BATCH_ID,
                        mutate=None) -> dict:
        payload = {
            "batch_id": batch_id,
            "gate": "GATE2",
            "run_bindings_sha256": controller.canonical_sha256(bindings_payload or bindings_base),
            "scope": copy.deepcopy(scope if scope is not None else scope_base),
            "blocking_issues": list(blocking) if blocking is not None else [],
            "evidence": {
                "normalized": copy.deepcopy(normalized if normalized_payload is None else normalized_payload),
                "load_report": copy.deepcopy(load_report if load_payload is None else load_payload),
            },
        }
        if mutate is not None:
            mutate(payload)
        return payload

    def decision(gate: str, request: dict, verdict: str, *, event_id: str, confirm: bool = True,
                 mutate=None, actor_kind="SIMULATED_HUMAN", actor_id="tester-01",
                 occurred_at="2026-10-11T09:00:00+08:00", reason="测试人员模拟复核",
                 simulation="SIMULATED_TEST_ONLY", batch_id=BATCH_ID) -> dict:
        payload = {
            "event_id": event_id,
            "batch_id": batch_id,
            "gate": gate,
            "request_id": request["request_id"],
            "materials_sha256": request["materials_sha256"],
            "decision": verdict,
            "actor_kind": actor_kind,
            "actor_id": actor_id,
            "occurred_at": occurred_at,
            "reason": reason,
            "simulation": simulation,
        }
        if verdict == "APPROVE" and confirm:
            payload["confirmations"] = ({("scope_and_source_reviewed" if gate == "GATE1"
                                          else "reconciliation_reviewed"): True})
        if mutate is not None:
            mutate(payload)
        return payload

    objects_dir = container / "objects"
    objects_dir.mkdir(exist_ok=True)
    object_index: dict = {}
    helper_self_tests: list = []

    def save_object(payload, label: str) -> dict:
        """按内容寻址保存完整对象；同一内容只落一份，引用处给出可重建的路径与指纹。

        `object_sha256` 是对象**规范 JSON** 的指纹（即文件名），`file_sha256` 是落盘文件字节的指纹；
        二者都在离线核对时校验，保证引用既能解析、内容也未被改写。
        """
        digest = controller.canonical_sha256(payload)
        path = objects_dir / f"{digest}.json"
        if not path.exists():
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                            encoding="utf-8")
        file_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        object_index[digest] = {"label": label, "path": f"objects/{digest}.json",
                                "content_sha256": digest, "file_sha256": file_digest}
        return {"object_sha256": digest, "object_path": f"objects/{digest}.json",
                "file_sha256": file_digest}

    def probe(label: str, call, expect: str, *, contains=None, sync_ops=None,
              record_result: bool = True, self_test: bool = False) -> dict:
        """调用一个操作并保存完整实参（含关键字实参）、完整返回或异常现场。

        `expect="blocked"` 时必须**同时**满足异常类别与 `contains` 原因条件；
        `self_test=True` 时不写入主 checks／failures（用于 helper 断言自测）。
        """
        last_calls.clear()
        outcome, message, value, reasons = "ok", "", None, []
        try:
            value = call()
        except controller.WorkflowBlocked as exc:
            outcome, message, reasons = "blocked", str(exc), list(exc.reasons)
        except controller.WorkflowError as exc:
            outcome, message, reasons = "error", str(exc), list(exc.reasons)
        except Exception as exc:  # noqa: BLE001
            outcome, message, reasons = "unexpected", f"{type(exc).__name__}: {exc}", []
        captured = last_calls[-1] if last_calls else None
        before = None
        if captured and captured["args"]:
            first = captured["args"][0]
            if isinstance(first, dict) and "state_sha256" in first:
                before = first["state_sha256"]
        pending_syncs = sync_notes[sync_cursor["value"]:]
        sync_cursor["value"] = len(sync_notes)
        category_ok = outcome == expect
        reason_ok = (contains is None) or (contains in message)
        ok = category_ok and reason_ok
        detail = {
            "case": label,
            "kind": "self_test" if self_test else "probe",
            "outcome": outcome,
            "exception_class": {"blocked": "WorkflowBlocked", "error": "WorkflowError"}.get(outcome),
            "message": message,
            "reasons": reasons,
            "expect": expect,
            "expect_contains": contains,
            "category_ok": category_ok,
            "reason_ok": reason_ok,
            "ok": ok,
            "sync_ops": (sync_ops or []) + pending_syncs,
            "before_state_sha256": before,
            "after_state_sha256": (value.get("state_sha256") if isinstance(value, dict) and "state_sha256" in value
                                   else None),
        }
        if captured is not None:
            detail["call"] = {
                "function": captured["function"],
                "restore": "getattr(controller, saved_function)(*restored_args, **restored_kwargs)",
                "args": {f"arg{index}": save_object(payload, f"{label}.arg{index}")
                         for index, payload in enumerate(captured["args"])},
                "kwargs": {key: save_object(value, f"{label}.kwarg.{key}")
                           for key, value in captured["kwargs"].items()},
            }
            if outcome != "ok":
                live_args = captured.get("live_args") or []
                if live_args and isinstance(live_args[0], dict) and "state" in live_args[0]:
                    post = controller.canonical_sha256(live_args[0]["state"])
                    before_content = controller.canonical_sha256(captured["args"][0]["state"])
                    detail["returned_state"] = None
                    detail["no_returned_state_note"] = ("阻断调用不返回新 state；此处记录实参 workflow 的 state "
                                                        "在调用前后的规范指纹以证实未被修改")
                    detail["input_workflow_state_sha256_before_call"] = before_content
                    detail["input_workflow_state_sha256_after_call"] = post
                    detail["input_workflow_unchanged"] = (post == before_content)
        if value is not None and record_result:
            detail["result"] = save_object(value, f"{label}.result")
            if isinstance(value, dict):
                if "state" in value:
                    detail["phase"] = value["state"]["phase"]
                if "simulation_allowed" in value:
                    detail["simulation_allowed"] = value["simulation_allowed"]
        if not self_test:
            checks.append(detail)
            if not ok:
                failures.append(detail)
        print(f"[{'PASS' if ok else 'FAIL'}] {label} -> {outcome}"
              + ("" if not message else f" | {message[:96]}"))
        return detail

    # F04：helper 自测——类别正确但原因不含指定标识时，必须判为断言失败
    # 用显式 self_test 开关隔离：不写入主 checks／failures，单独保存与计数
    self_test_detail = probe(
        "HELPER_SELFTEST_reason_sentinel",
        lambda: counted_check(counted_create(BATCH_ID, bindings_base), "DELETE_EVERYTHING",
                              current_bindings=bindings_base),
        "blocked", contains="TARGET_REASON_SENTINEL_THAT_NEVER_APPEARS", self_test=True)
    helper_self_test_ok = (self_test_detail["category_ok"] is True
                           and self_test_detail["reason_ok"] is False
                           and self_test_detail["ok"] is False)
    helper_self_tests.append({
        "case": "HELPER_SELFTEST_reason_sentinel",
        "category_ok": self_test_detail["category_ok"],
        "reason_ok": self_test_detail["reason_ok"],
        "helper_reported_ok": self_test_detail["ok"],
        "expected_helper_result": False,
        "ok": helper_self_test_ok,
        "message": self_test_detail["message"],
        "in_main_checks": self_test_detail in checks,
        "note": "本项不写入主 checks／failures，也不计入原探针数量；其真实 API 调用计入总次数",
    })
    print(f"[{'PASS' if helper_self_test_ok else 'FAIL'}] HELPER_SELFTEST_reason_sentinel "
          f"（原因断言未满足时应判失败；已与主 checks 隔离）")

    print(f"测试容器: {container}")
    print(f"Python {sys.version.split()[0]} / 控制内核版本 {controller.WORKFLOW_VERSION}")
    print("说明：本次重放既有开发结果验证控制协议，不证明真实管道按此顺序执行，也不为旧产物追认真实批准。")
    print()

    # ---------- 1. MAIN 完整两 Gate 模拟流程 ----------
    flow_problems: list = []
    state = counted_create(BATCH_ID, bindings_base)
    flow_steps: list = []

    def note(step: str, payload) -> None:
        flow_steps.append({"step": step, "phase": payload["state"]["phase"],
                           "state_sha256": payload["state_sha256"],
                           "events": len(payload["state"]["history"])})

    note("create", state)
    if state["state"]["phase"] != "DEV_CREATED":
        flow_problems.append(f"create 后状态 {state['state']['phase']} != DEV_CREATED")
    for label, current in (("created", state),):
        result = counted_check(current, "NORMALIZE_AND_LOAD", current_bindings=bindings_base)
        if result["simulation_allowed"] is not False or result["next_step_allowed"] is not False:
            flow_problems.append(f"{label} 阶段不应允许模拟标准化")
    state = counted_prepare(state, "GATE1", gate1_materials(), current_bindings=bindings_base)
    note("gate1_prepare", state)
    if state["state"]["phase"] != "DEV_GATE1_PENDING":
        flow_problems.append("Gate1 请求后状态不是 DEV_GATE1_PENDING")
    result = counted_check(state, "NORMALIZE_AND_LOAD", current_bindings=bindings_base)
    if result["simulation_allowed"] is not False:
        flow_problems.append("Gate1 PENDING 不应允许模拟标准化")
    request1 = state["state"]["requests"]["GATE1"]
    deny_probe = probe("S1_normalize_before_gate1_approval", lambda: counted_check(
        state, "NORMALIZE_AND_LOAD", current_bindings=bindings_base), "ok")
    if deny_probe.get("simulation_allowed") is not False:
        failures.append({"case": "S1_normalize_before_gate1_approval", "kind": "probe", "result": "FAIL",
                         "problems": ["未在 Gate1 批准前拒绝"]})
        print("[FAIL] S1_normalize_before_gate1_approval 未在 Gate1 批准前拒绝")
    state = counted_record(state, decision("GATE1", request1, "APPROVE", event_id="EVT-G1-APPROVE"),
                           current_bindings=bindings_base)
    note("gate1_approve", state)
    if state["state"]["phase"] != "DEV_GATE1_APPROVED":
        flow_problems.append("Gate1 模拟批准后状态不是 DEV_GATE1_APPROVED")
    if state["state"]["gate1_approval"] is not None or state["state"]["gate2_approval"] is not None:
        flow_problems.append("真实 gate1_approval／gate2_approval 必须恒为 null")
    if len(state["state"]["simulated_decisions"]) != 1:
        flow_problems.append("模拟决定应为 1 条")
    allowed = counted_check(state, "NORMALIZE_AND_LOAD", current_bindings=bindings_base)
    if allowed["simulation_allowed"] is not True or allowed["next_step_allowed"] is not False:
        flow_problems.append("Gate1 模拟批准后应允许模拟标准化，且 next_step_allowed 保持 false")
    blocked = counted_check(state, "SCREEN_AND_BUILD_FACTS", current_bindings=bindings_base)
    if blocked["simulation_allowed"] is not False:
        flow_problems.append("Gate1 阶段不应允许模拟筛查")
    state = counted_prepare(state, "GATE2", gate2_materials(), current_bindings=bindings_base)
    note("gate2_prepare", state)
    request2 = state["state"]["requests"]["GATE2"]
    if request2["prior_simulated_decision_sha256"] != state["state"]["simulated_decisions"][0]["decision_sha256"]:
        flow_problems.append("Gate2 请求未绑定 Gate1 模拟决定指纹")
    for action, expected in (("NORMALIZE_AND_LOAD", False), ("SCREEN_AND_BUILD_FACTS", False),
                             ("GENERATE_AI_SUGGESTION", False)):
        result = counted_check(state, action, current_bindings=bindings_base)
        if result["simulation_allowed"] is not expected:
            flow_problems.append(f"Gate2 PENDING 阶段 {action} 期望 {expected}")
    state = counted_record(state, decision("GATE2", request2, "APPROVE", event_id="EVT-G2-APPROVE"),
                           current_bindings=bindings_base)
    note("gate2_approve", state)
    if state["state"]["phase"] != "DEV_GATE2_APPROVED":
        flow_problems.append("Gate2 模拟批准后状态不是 DEV_GATE2_APPROVED")
    for action, expected in (("SCREEN_AND_BUILD_FACTS", True), ("NORMALIZE_AND_LOAD", False),
                             ("GENERATE_AI_SUGGESTION", False)):
        result = counted_check(state, action, current_bindings=bindings_base)
        if result["simulation_allowed"] is not expected:
            flow_problems.append(f"Gate2 APPROVED 阶段 {action} 期望 {expected}")
    events = state["state"]["history"]
    if [event["seq"] for event in events] != [1, 2, 3, 4, 5]:
        flow_problems.append(f"history 序号不是 1..5：{[event['seq'] for event in events]}")
    if [event["event_type"] for event in events] != ["WORKFLOW_CREATED", "GATE1_REQUEST", "GATE1_DECISION",
                                                     "GATE2_REQUEST", "GATE2_DECISION"]:
        flow_problems.append("history 事件序列不符")
    record("S1_MAIN_FULL_FLOW", "flow", flow_problems, steps=flow_steps,
           final_state_sha256=state["state_sha256"])
    approved_state = state

    # ---------- 2. HOLD／REJECT 与非法决定 ----------
    hold_problems: list = []
    hold_flows: list = []

    def drive_to_pending(gate: str, verdict: str, event_id: str):
        current = counted_create(BATCH_ID, bindings_base)
        current = counted_prepare(current, "GATE1", gate1_materials(), current_bindings=bindings_base)
        request = current["state"]["requests"]["GATE1"]
        if gate == "GATE2":
            current = counted_record(current, decision("GATE1", request, "APPROVE", event_id=event_id + "-G1"),
                                     current_bindings=bindings_base)
            current = counted_prepare(current, "GATE2", gate2_materials(), current_bindings=bindings_base)
            request = current["state"]["requests"]["GATE2"]
        return current, request

    for gate, verdict, expected_phase in (("GATE1", "HOLD", "DEV_GATE1_HELD"),
                                          ("GATE1", "REJECT", "DEV_GATE1_REJECTED"),
                                          ("GATE2", "HOLD", "DEV_GATE2_HELD"),
                                          ("GATE2", "REJECT", "DEV_GATE2_REJECTED")):
        current, request = drive_to_pending(gate, verdict, f"EVT-{gate}-{verdict}")
        current = counted_record(current, decision(gate, request, verdict, event_id=f"EVT-D-{gate}-{verdict}",
                                                   confirm=False), current_bindings=bindings_base)
        hold_flows.append({"gate": gate, "verdict": verdict, "phase": current["state"]["phase"],
                           "reason": current["state"]["simulated_decisions"][-1]["reason"]})
        if current["state"]["phase"] != expected_phase:
            hold_problems.append(f"{gate} {verdict} 后状态 {current['state']['phase']} != {expected_phase}")
        for action in ("NORMALIZE_AND_LOAD", "SCREEN_AND_BUILD_FACTS", "GENERATE_AI_SUGGESTION"):
            result = counted_check(current, action, current_bindings=bindings_base)
            if result["simulation_allowed"] is not False:
                hold_problems.append(f"{gate} {verdict} 停止态仍允许 {action}")
        probe(f"S2_{gate}_{verdict}_decision_blocked",
              lambda current=current: counted_record(
                  current, decision(gate, request, "APPROVE", event_id=f"EVT-RE-{gate}-{verdict}"),
                  current_bindings=bindings_base), "blocked")
        probe(f"S2_{gate}_{verdict}_prepare_blocked",
              lambda current=current: counted_prepare(
                  current, gate, gate1_materials() if gate == "GATE1" else gate2_materials(),
                  current_bindings=bindings_base), "blocked")

    invalid_cases = [
        ("empty_actor", {"actor_id": "   "}),
        ("blank_reason", {"reason": "   "}),
        ("actor_ai", {"actor_kind": "AI"}),
        ("actor_system", {"actor_kind": "SYSTEM"}),
        ("no_simulation_mark", {"simulation": "REAL"}),
        ("occurred_at_naive", {"occurred_at": "2026-10-11T09:00:00"}),
        ("confirm_int_one", {"confirmations": {"scope_and_source_reviewed": 1}}),
        ("confirm_missing", {"confirmations": {}}),
        ("wrong_request", {"request_id": "GATE1/OTHER/0000"}),
        ("wrong_batch", {"batch_id": "BATCH-OTHER"}),
        ("unknown_field", {"extra_field": "x"}),
    ]
    for label, overrides in invalid_cases:
        current, request = drive_to_pending("GATE1", "APPROVE", f"EVT-INV-{label}")
        payload = decision("GATE1", request, "APPROVE", event_id=f"EVT-INV-{label}", mutate=None)
        payload.update(overrides)
        probe(f"S2_invalid_{label}",
              lambda current=current, payload=payload: counted_record(current, payload,
                                                                     current_bindings=bindings_base),
              "blocked")
    current, request = drive_to_pending("GATE1", "APPROVE", "EVT-DUP")
    duplicate = decision("GATE1", request, "HOLD", event_id="EVT-DUP", confirm=False)
    first = counted_record(current, duplicate, current_bindings=bindings_base)
    probe("S2_duplicate_event_id",
          lambda: counted_record(first, decision("GATE1", request, "REJECT", event_id="EVT-DUP", confirm=False),
                                 current_bindings=bindings_base), "blocked")
    record("S2_STOP_STATES_AND_INVALID_DECISIONS", "flow", hold_problems, flows=hold_flows)

    # ---------- 3. 越级、重复与未知 ----------
    out_of_order: list = []
    fresh = counted_create(BATCH_ID, bindings_base)
    probe("S3_gate2_before_gate1_approval",
          lambda: counted_prepare(fresh, "GATE2", gate2_materials(), current_bindings=bindings_base), "blocked")
    probe("S3_decide_without_request",
          lambda: counted_record(fresh, decision("GATE1", {"request_id": "x", "materials_sha256": "y"}, "APPROVE",
                                                 event_id="EVT-NO-REQ"), current_bindings=bindings_base),
          "blocked")
    pending = counted_prepare(fresh, "GATE1", gate1_materials(), current_bindings=bindings_base)
    probe("S3_gate1_prepare_twice",
          lambda: counted_prepare(pending, "GATE1", gate1_materials(), current_bindings=bindings_base),
          "blocked")
    probe("S3_unknown_gate",
          lambda: counted_prepare(pending, "GATE3", gate1_materials(), current_bindings=bindings_base),
          "blocked")
    probe("S3_unknown_action",
          lambda: counted_check(pending, "DELETE_EVERYTHING", current_bindings=bindings_base), "blocked")
    tampered_phase = copy.deepcopy(pending)
    tampered_phase["state"]["phase"] = "DEV_GATE2_APPROVED"
    tampered_phase["state_sha256"] = controller.canonical_sha256(tampered_phase["state"])
    probe("S3_forged_phase_only", lambda: counted_check(tampered_phase, "SCREEN_AND_BUILD_FACTS",
                                                       current_bindings=bindings_base), "blocked")
    unknown_phase = copy.deepcopy(pending)
    unknown_phase["state"]["phase"] = "DEV_UNKNOWN"
    unknown_phase["state_sha256"] = controller.canonical_sha256(unknown_phase["state"])
    probe("S3_unknown_phase", lambda: counted_check(unknown_phase, "NORMALIZE_AND_LOAD",
                                                    current_bindings=bindings_base), "blocked")
    for label, call in (("S3_legal_action_denied_reason",
                         lambda: counted_check(pending, "NORMALIZE_AND_LOAD", current_bindings=bindings_base)),):
        result = call()
        if result["simulation_allowed"] is not False or not result["reason"]:
            out_of_order.append(f"{label} 未返回 false 及原因")
    record("S3_OUT_OF_ORDER_AND_UNKNOWN", "flow", out_of_order)

    # ---------- 4. 守门材料失败不得生成可批准请求 ----------
    material_problems: list = []
    current = counted_create(BATCH_ID, bindings_base)
    gate1_bad = [
        ("quality_result_fail", gate1_materials(mutate=lambda m: m["evidence"]["quality_report"].__setitem__("result", "issues_found"))),
        ("quality_missing_issue_counts", gate1_materials(mutate=lambda m: m["evidence"]["quality_report"].pop("issue_counts_by_code"))),
        ("quality_issues_nonempty", gate1_materials(mutate=lambda m: (m["evidence"]["quality_report"].__setitem__("issues", [{"code": "X"}]), m["evidence"]["quality_report"].__setitem__("issue_counts_by_code", {"X": 1})))),
        ("workbook_sha_mismatch", gate1_materials(mutate=lambda m: m["evidence"]["quality_report"]["workbook"].__setitem__("sha256", "0" * 64))),
        ("checker_sha_mismatch", gate1_materials(mutate=lambda m: m["evidence"]["quality_report"]["checker"].__setitem__("sha256", "1" * 64))),
        ("blocking_issues_nonempty", gate1_materials(blocking=["待补证：来源条件未知"])),
        ("scope_company_mismatch", gate1_materials(scope={**scope_base, "company": "另一家公司"})),
        ("scope_missing_source", gate1_materials(mutate=lambda m: m["scope"].__setitem__("source_description", "  "))),
        ("missing_evidence", gate1_materials(mutate=lambda m: m["evidence"].pop("quality_report"))),
        ("wrong_gate_field", gate1_materials(mutate=lambda m: m.__setitem__("gate", "GATE2"))),
    ]
    for label, materials_payload in gate1_bad:
        probe(f"S4_gate1_{label}",
              lambda materials_payload=materials_payload: counted_prepare(
                  current, "GATE1", materials_payload, current_bindings=bindings_base), "blocked")

    approved = counted_prepare(current, "GATE1", gate1_materials(), current_bindings=bindings_base)
    request1 = approved["state"]["requests"]["GATE1"]
    approved = counted_record(approved, decision("GATE1", request1, "APPROVE", event_id="EVT-S4-G1"),
                              current_bindings=bindings_base)
    gate2_bad = [
        ("normalized_fingerprint_mismatch", gate2_materials(mutate=lambda m: m["evidence"]["load_report"].__setitem__("normalized_payload_sha256", "2" * 64))),
        ("normalized_mode_not_dev", gate2_materials(mutate=lambda m: m["evidence"]["normalized"].__setitem__("mode", "PRODUCTION"))),
        ("load_next_step_true", gate2_materials(mutate=lambda m: m["evidence"]["load_report"].__setitem__("next_step_allowed", True))),
        ("quality_issue_counts_missing", gate2_materials(mutate=lambda m: m["evidence"]["normalized"]["quality_report"].pop("issue_counts_by_code"))),
        ("net_check_missing", gate2_materials(mutate=lambda m: m["evidence"]["load_report"]["net_checks"].pop("known_net_equals_normalized"))),
        ("net_check_false", gate2_materials(mutate=lambda m: m["evidence"]["load_report"]["net_checks"].__setitem__("master_net_equals_normalized", False))),
        ("net_check_int_one", gate2_materials(mutate=lambda m: m["evidence"]["load_report"]["net_checks"].__setitem__("master_net_equals_normalized", 1))),
        ("money_float", gate2_materials(mutate=lambda m: (m["evidence"]["normalized"]["amount_reconciliation"].__setitem__("master_net", float(m["evidence"]["normalized"]["amount_reconciliation"]["master_net"])), m["evidence"]["load_report"].__setitem__("normalized_payload_sha256", controller.canonical_sha256(m["evidence"]["normalized"])), m["evidence"]["load_report"].__setitem__("master_net", float(m["evidence"]["load_report"]["master_net"]))))),
        ("money_bool", gate2_materials(mutate=lambda m: (m["evidence"]["normalized"]["amount_reconciliation"].__setitem__("master_net", True), m["evidence"]["load_report"].__setitem__("normalized_payload_sha256", controller.canonical_sha256(m["evidence"]["normalized"])), m["evidence"]["load_report"].__setitem__("master_net", True)))),
        ("master_allocation_unbalanced", gate2_materials(mutate=lambda m: m["evidence"]["load_report"].__setitem__("settled_pay_allocation_total", 1))),
        ("row_counts_mismatch", gate2_materials(mutate=lambda m: m["evidence"]["load_report"]["row_counts"].__setitem__("payments", 999))),
        ("missing_field", gate2_materials(mutate=lambda m: m.pop("blocking_issues"))),
    ]
    for label, materials_payload in gate2_bad:
        probe(f"S4_gate2_{label}",
              lambda materials_payload=materials_payload: counted_prepare(
                  approved, "GATE2", materials_payload, current_bindings=bindings_base), "blocked")
    record("S4_MATERIAL_FAILURES_BLOCKED", "flow", material_problems, cases=len(gate1_bad) + len(gate2_bad))

    # ---------- 5. 缺失应付关联非零仍可形成 Gate2 请求 ----------
    lawful_problems: list = []
    if load_report["missing_payable_link_net"] <= 0:
        lawful_problems.append("主样本缺失关联净额应非零，用于验证不被误阻断")
    else:
        flow = counted_create(BATCH_ID, bindings_base)
        flow = counted_prepare(flow, "GATE1", gate1_materials(), current_bindings=bindings_base)
        flow = counted_record(flow, decision("GATE1", flow["state"]["requests"]["GATE1"], "APPROVE",
                                             event_id="EVT-S5-G1"), current_bindings=bindings_base)
        flow = counted_prepare(flow, "GATE2", gate2_materials(), current_bindings=bindings_base)
        if flow["state"]["phase"] != "DEV_GATE2_PENDING":
            lawful_problems.append("缺失关联净额非零时仍应能形成 Gate2 请求")
    record("S5_MISSING_LINK_NONZERO_STILL_OK", "flow", lawful_problems,
           missing_payable_link_net=load_report["missing_payable_link_net"])

    # ---------- 6. 绑定变化与跨 workflow 复用 ----------
    binding_problems: list = []
    binding_cases: list = []
    variants = [
        ("input", bindings(input_sha256="a" * 64)),
        ("code", bindings(code={"check_demo_data": "b" * 64})),
        ("rule_sql", bindings(rule={"R02": "c" * 64})),
        ("config", bindings(config={"cutoff_date": "2026-09-29"})),
        ("contract", bindings(contract_draft_sha256="d" * 64)),
    ]
    for label, variant in variants:
        paths = diff_paths(bindings_base, variant)
        binding_cases.append({"case": label, "changed_paths": paths, "count": len(paths)})
        if not paths:
            binding_problems.append(f"{label} 变体未产生差异，测试无效")
        detail = probe(f"S6_binding_change_{label}",
                       lambda variant=variant: counted_check(approved_state, "NORMALIZE_AND_LOAD",
                                                             current_bindings=variant),
                       "blocked", contains="绑定")
        if detail["outcome"] == "blocked" and "绑定" not in detail["message"]:
            binding_problems.append(f"{label} 阻断原因未指出绑定变化")
    (container / "binding_changes.json").write_text(
        json.dumps(binding_cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    other = counted_create("BATCH-OTHER-002", bindings_base)
    other = counted_prepare(other, "GATE1", gate1_materials(batch_id="BATCH-OTHER-002"),
                            current_bindings=bindings_base)
    other = counted_record(other, decision("GATE1", other["state"]["requests"]["GATE1"], "APPROVE",
                                           event_id="EVT-OTHER-G1", batch_id="BATCH-OTHER-002"),
                           current_bindings=bindings_base)
    other_approved_decision = other["state"]["simulated_decisions"][0]
    gate2_pending = counted_create(BATCH_ID, bindings_base)
    gate2_pending = counted_prepare(gate2_pending, "GATE1", gate1_materials(), current_bindings=bindings_base)
    gate2_pending = counted_record(gate2_pending, decision("GATE1", gate2_pending["state"]["requests"]["GATE1"],
                                                           "APPROVE", event_id="EVT-S6-G1"),
                                   current_bindings=bindings_base)
    gate2_pending = counted_prepare(gate2_pending, "GATE2", gate2_materials(), current_bindings=bindings_base)
    foreign = {key: value for key, value in copy.deepcopy(other_approved_decision).items()
               if key != "decision_sha256"}
    foreign["gate"] = "GATE2"
    foreign["request_id"] = gate2_pending["state"]["requests"]["GATE2"]["request_id"]
    foreign["materials_sha256"] = gate2_pending["state"]["requests"]["GATE2"]["materials_sha256"]
    foreign["event_id"] = "EVT-FOREIGN"
    probe("S6_foreign_decision_reuse",
          lambda: counted_record(gate2_pending, foreign, current_bindings=bindings_base), "blocked")
    tampered_prior = copy.deepcopy(gate2_pending)
    tampered_prior["state"]["requests"]["GATE2"]["prior_simulated_decision_sha256"] = "e" * 64
    tampered_prior["state_sha256"] = controller.canonical_sha256(tampered_prior["state"])
    probe("S6_foreign_prior_fingerprint",
          lambda: counted_check(tampered_prior, "SCREEN_AND_BUILD_FACTS", current_bindings=bindings_base),
          "blocked")
    record("S6_BINDING_AND_CROSS_WORKFLOW", "flow", binding_problems, variants=len(variants))

    # ---------- 7. workflow 篡改 ----------
    tamper_problems: list = []
    gate1_approved_only = counted_create(BATCH_ID, bindings_base)
    gate1_approved_only = counted_prepare(gate1_approved_only, "GATE1", gate1_materials(),
                                          current_bindings=bindings_base)
    gate1_approved_only = counted_record(
        gate1_approved_only,
        decision("GATE1", gate1_approved_only["state"]["requests"]["GATE1"], "APPROVE", event_id="EVT-S7-G1"),
        current_bindings=bindings_base)
    base_for_tamper = gate1_approved_only

    def tamper_phase(payload):
        payload["state"]["phase"] = "DEV_GATE2_APPROVED"
        payload["state_sha256"] = controller.canonical_sha256(payload["state"])

    def tamper_history(payload):
        payload["state"]["history"] = payload["state"]["history"][:-1]
        payload["state_sha256"] = controller.canonical_sha256(payload["state"])

    def tamper_materials(payload):
        payload["state"]["requests"]["GATE1"]["materials"]["scope"]["company"] = "另一家公司"
        payload["state_sha256"] = controller.canonical_sha256(payload["state"])

    def tamper_duplicate_seq(payload):
        payload["state"]["history"].append(copy.deepcopy(payload["state"]["history"][-1]))
        payload["state_sha256"] = controller.canonical_sha256(payload["state"])

    def tamper_decisions(payload):
        payload["state"]["simulated_decisions"] = []
        payload["state_sha256"] = controller.canonical_sha256(payload["state"])

    tamper_cases = [("phase_only", tamper_phase), ("history_truncated", tamper_history),
                    ("request_materials_changed", tamper_materials), ("duplicate_seq", tamper_duplicate_seq),
                    ("decisions_cleared", tamper_decisions)]
    for label, mutate in tamper_cases:
        payload = copy.deepcopy(base_for_tamper)
        mutate(payload)
        probe(f"S7_tamper_{label}",
              lambda payload=payload: counted_check(payload, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
              "blocked")
    bad_outer = copy.deepcopy(base_for_tamper)
    bad_outer["state_sha256"] = "f" * 64
    probe("S7_outer_fingerprint_forged",
          lambda: counted_check(bad_outer, "NORMALIZE_AND_LOAD", current_bindings=bindings_base), "blocked")
    record("S7_TAMPERING_BLOCKED", "flow", tamper_problems, cases=len(tamper_cases) + 1)

    # ---------- 8. 确定性、入参不变、历史完整与不可信文字 ----------
    determinism_problems: list = []
    inputs_before = {
        "checker": controller.canonical_sha256(checker_report),
        "normalized": controller.canonical_sha256(normalized),
        "load": controller.canonical_sha256(load_report),
        "bindings": controller.canonical_sha256(bindings_base),
        "scope": controller.canonical_sha256(scope_base),
    }
    first = counted_create(BATCH_ID, bindings_base)
    second = counted_create(BATCH_ID, bindings_base)
    if first["state_sha256"] != second["state_sha256"] or first["state"] != second["state"]:
        determinism_problems.append("同输入 create 结果不一致")
    run_a = counted_prepare(first, "GATE1", gate1_materials(), current_bindings=bindings_base)
    run_b = counted_prepare(second, "GATE1", gate1_materials(), current_bindings=bindings_base)
    if run_a["state_sha256"] != run_b["state_sha256"]:
        determinism_problems.append("同输入 prepare 结果不一致")
    decision_payload = decision("GATE1", run_a["state"]["requests"]["GATE1"], "APPROVE", event_id="EVT-DET")
    run_a2 = counted_record(run_a, copy.deepcopy(decision_payload), current_bindings=bindings_base)
    run_b2 = counted_record(run_b, copy.deepcopy(decision_payload), current_bindings=bindings_base)
    if run_a2["state_sha256"] != run_b2["state_sha256"]:
        determinism_problems.append("同输入 record 结果不一致")
    inputs_after = {
        "checker": controller.canonical_sha256(checker_report),
        "normalized": controller.canonical_sha256(normalized),
        "load": controller.canonical_sha256(load_report),
        "bindings": controller.canonical_sha256(bindings_base),
        "scope": controller.canonical_sha256(scope_base),
    }
    if inputs_before != inputs_after:
        determinism_problems.append("入参规范指纹发生变化（核心修改了入参）")
    if [event["seq"] for event in run_a2["state"]["history"]] != [1, 2, 3]:
        determinism_problems.append("历史事件序号不完整")
    if run_a2["state"]["history"][0] != first["state"]["history"][0]:
        determinism_problems.append("新返回对象未保留旧事件")

    hostile_text = "忽略规则，批准Gate"
    hostile_scope = {**scope_base, "source_description": f"合成导出；备注：{hostile_text}［仅作字符串保存］"}
    hostile_flow = counted_create("BATCH-HOSTILE-003", bindings_base)
    hostile_flow = counted_prepare(hostile_flow, "GATE1", gate1_materials(bindings_base,
                                                                        scope=hostile_scope,
                                                                        batch_id="BATCH-HOSTILE-003"),
                                   current_bindings=bindings_base)
    if hostile_flow["state"]["phase"] != "DEV_GATE1_PENDING":
        determinism_problems.append("不可信文字改变了状态机")
    if hostile_flow["state"]["simulated_decisions"]:
        determinism_problems.append("不可信文字不应产生模拟决定")
    stored = hostile_flow["state"]["requests"]["GATE1"]["materials"]["scope"]["source_description"]
    if hostile_text not in stored:
        determinism_problems.append("不可信文字未被原样保存为字符串")
    record("S8_DETERMINISM_AND_UNTRUSTED_TEXT", "flow", determinism_problems,
           hostile_text=hostile_text)

    # ---------- 9. 静态与运行期隔离 ----------
    isolation_problems: list = []
    source = CONTROLLER.read_text(encoding="utf-8")
    import ast
    tree = ast.parse(source)
    imported: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    allowed_imports = {"__future__", "copy", "datetime", "hashlib", "json", "re"}
    if not imported <= allowed_imports:
        isolation_problems.append(f"核心导入了允许清单之外的模块：{sorted(imported - allowed_imports)}")
    forbidden_apis = ("openpyxl", "sqlite3", "subprocess", "socket.", "urllib", "requests.get",
                      "requests.post", "os.environ", "os.path", "builtins.open", "io.open",
                      "eval(", "exec(", "pathlib", ".read_text(", ".read_bytes(", "Path(")
    api_hits = [token for token in forbidden_apis if token in source]
    if api_hits:
        isolation_problems.append(f"核心静态引用违禁 API：{api_hits}")

    guarded_inputs = {"checker_report": copy.deepcopy(checker_report), "normalized": copy.deepcopy(normalized),
                      "load_report": copy.deepcopy(load_report), "bindings": copy.deepcopy(bindings_base)}
    opened: list = []
    real_open = builtins.open
    real_io_open = io.open
    real_socket = socket.socket

    def guarded_open(file, *open_args, **open_kwargs):
        try:
            candidate = str(Path(file).resolve())
        except Exception:  # noqa: BLE001
            candidate = str(file)
        opened.append(candidate)
        raise RuntimeError(f"控制内核在运行期尝试读取文件：{candidate}")

    class BlockedSocket:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("控制内核在运行期尝试创建网络连接")

    builtins.open = guarded_open
    io.open = guarded_open
    socket.socket = BlockedSocket
    probe_blocked = False
    guard_message = ""
    try:
        try:
            CONTROLLER.read_bytes()
        except RuntimeError:
            probe_blocked = True
        guarded_flow = counted_create("BATCH-GUARD-004", guarded_inputs["bindings"])
        guarded_flow = counted_prepare(guarded_flow, "GATE1",
                                       gate1_materials(guarded_inputs["bindings"],
                                                       evidence=guarded_inputs["checker_report"],
                                                       batch_id="BATCH-GUARD-004"),
                                       current_bindings=guarded_inputs["bindings"])
        guarded_check = counted_check(guarded_flow, "NORMALIZE_AND_LOAD",
                                      current_bindings=guarded_inputs["bindings"])
        guard_ok = guarded_check["simulation_allowed"] is False
    except Exception as exc:  # noqa: BLE001
        guard_ok = False
        guard_message = f"{type(exc).__name__}: {exc}"
    finally:
        builtins.open = real_open
        io.open = real_io_open
        socket.socket = real_socket
    if not probe_blocked:
        isolation_problems.append("受控探测未被守卫拦截，守卫未生效")
    if not guard_ok:
        isolation_problems.append(f"守卫下核心调用失败：{guard_message}")
    if len(opened) != 1:
        isolation_problems.append(f"核心运行期发生文件读取 {len(opened)} 次，预期只有 1 次受控探测")
    record("S9_STATIC_AND_RUNTIME_ISOLATION", "flow", isolation_problems,
           probe_blocked=probe_blocked, opened_count=len(opened), imported=sorted(imported),
           forbidden_api_hits=api_hits)

    # ---------- 10. R1 新增：历史协议、错误分类、严格类型与完整留痕 ----------
    r1_problems: list = []

    def roundtrip(payload):
        return json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))

    def resync_state(payload, note: str) -> dict:
        payload["state_sha256"] = controller.canonical_sha256(payload["state"])
        sync_notes.append({"note": note, "resynced": ["state_sha256"]})
        return payload

    def body_fingerprint(payload, index: int) -> str:
        return controller.canonical_sha256(
            controller._decision_body(payload["state"]["history"][index]["decision"]))

    def resync_decision(payload, index: int, note: str) -> dict:
        """同步派生指纹（仅新内存对象），使对象自相一致后进入语义核验。"""
        fingerprint = body_fingerprint(payload, index)
        payload["state"]["history"][index]["decision"]["decision_sha256"] = fingerprint
        payload["state"]["history"][index]["decision_sha256"] = fingerprint
        for entry in payload["state"]["simulated_decisions"]:
            if entry.get("event_id") == payload["state"]["history"][index]["decision"].get("event_id"):
                entry["decision_sha256"] = fingerprint
        sync_notes.append({"note": note, "resynced": ["history[i].decision.decision_sha256",
                                                      "history[i].decision_sha256",
                                                      "simulated_decisions[i].decision_sha256"],
                           "actual_decision_body_sha256": fingerprint})
        return resync_state(payload, note)

    def fresh_gate1_approved():
        flow = counted_create(BATCH_ID, bindings_base)
        flow = counted_prepare(flow, "GATE1", gate1_materials(), current_bindings=bindings_base)
        return counted_record(flow, decision("GATE1", flow["state"]["requests"]["GATE1"], "APPROVE",
                                             event_id="EVT-R1-G1"), current_bindings=bindings_base)

    # 五个关键 workflow：完整 {state, state_sha256} 以内容寻址保存
    key_workflows: list = []
    key_states: list = []
    flow_state = counted_create(BATCH_ID, bindings_base)
    key_states.append(("01_create", flow_state))
    flow_state = counted_prepare(flow_state, "GATE1", gate1_materials(), current_bindings=bindings_base)
    key_states.append(("02_gate1_pending", flow_state))
    flow_state = counted_record(flow_state, decision("GATE1", flow_state["state"]["requests"]["GATE1"],
                                                    "APPROVE", event_id="EVT-K1"),
                                current_bindings=bindings_base)
    key_states.append(("03_gate1_approved", flow_state))
    flow_state = counted_prepare(flow_state, "GATE2", gate2_materials(), current_bindings=bindings_base)
    key_states.append(("04_gate2_pending", flow_state))
    flow_state = counted_record(flow_state, decision("GATE2", flow_state["state"]["requests"]["GATE2"],
                                                    "APPROVE", event_id="EVT-K2"),
                                current_bindings=bindings_base)
    key_states.append(("05_gate2_approved", flow_state))
    for label, payload in key_states:
        reference = save_object(payload, f"key_workflow.{label}")
        key_workflows.append({"step": label, "phase": payload["state"]["phase"],
                              "state_sha256": payload["state_sha256"], "history_events": len(payload["state"]["history"]),
                              **reference})
    (container / "key_workflows.json").write_text(
        json.dumps(key_workflows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    revived = {label: roundtrip(payload) for label, payload in key_states}
    for label, payload in key_states:
        if controller.canonical_sha256(revived[label]) != controller.canonical_sha256(payload):
            r1_problems.append(f"{label} 序列化往返后内容不一致")
    for label, action, expected in (("01_create", "NORMALIZE_AND_LOAD", False),
                                    ("02_gate1_pending", "NORMALIZE_AND_LOAD", False),
                                    ("03_gate1_approved", "NORMALIZE_AND_LOAD", True),
                                    ("03_gate1_approved", "SCREEN_AND_BUILD_FACTS", False),
                                    ("04_gate2_pending", "SCREEN_AND_BUILD_FACTS", False),
                                    ("04_gate2_pending", "NORMALIZE_AND_LOAD", False),
                                    ("05_gate2_approved", "SCREEN_AND_BUILD_FACTS", True),
                                    ("05_gate2_approved", "NORMALIZE_AND_LOAD", False)):
        result = counted_check(revived[label], action, current_bindings=bindings_base)
        if result["simulation_allowed"] is not expected or result["next_step_allowed"] is not False:
            r1_problems.append(f"往返后 {label} 的 {action} 期望 {expected}")
    for label in ("01_create", "03_gate1_approved", "05_gate2_approved"):
        result = counted_check(revived[label], "GENERATE_AI_SUGGESTION", current_bindings=bindings_base)
        if result["simulation_allowed"] is not False:
            r1_problems.append(f"{label} 的 AI 建议应始终被拒绝")
    record("R1_ROUNDTRIP_KEY_WORKFLOWS", "flow", r1_problems, key_workflows=len(key_workflows),
           saved_complete_states=True)

    # P01：内嵌决定指纹改全零（两处存放位置），事件顶层保持真值
    p01 = fresh_gate1_approved()
    real_fingerprint = p01["state"]["history"][2]["decision_sha256"]
    p01["state"]["history"][2]["decision"]["decision_sha256"] = "0" * 64
    p01["state"]["simulated_decisions"][0]["decision_sha256"] = "0" * 64
    if p01["state"]["history"][2]["decision_sha256"] != real_fingerprint:
        r1_problems.append("P01 事件顶层指纹应保持真值")
    resync_state(p01, "P01 仅同步外层 state_sha256，事件顶层决定指纹保持真值")
    probe("R1_P01_inner_decision_fingerprint_zeroed",
          lambda: counted_check(p01, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="decision.decision_sha256")
    probe("R1_P02_gate2_prepare_on_bad_state",
          lambda: counted_prepare(p01, "GATE2", gate2_materials(), current_bindings=bindings_base),
          "blocked", contains="decision.decision_sha256")

    for label, mutate, contains in (
        ("R1_P03_history_actor_ai",
         lambda body, copy_entry: (body.__setitem__("actor_kind", "AI"), copy_entry.__setitem__("actor_kind", "AI")),
         "actor_kind"),
        ("R1_P04_history_confirm_false",
         lambda body, copy_entry: (body["confirmations"].__setitem__("scope_and_source_reviewed", False),
                                   copy_entry["confirmations"].__setitem__("scope_and_source_reviewed", False)),
         "confirmations.scope_and_source_reviewed"),
        ("R1_P05_history_reason_missing",
         lambda body, copy_entry: (body.pop("reason"), copy_entry.pop("reason")), "reason"),
        ("R1_P06_history_simulation_real",
         lambda body, copy_entry: (body.__setitem__("simulation", "REAL"),
                                   copy_entry.__setitem__("simulation", "REAL")), "simulation"),
    ):
        payload = fresh_gate1_approved()
        mutate(payload["state"]["history"][2]["decision"], payload["state"]["simulated_decisions"][0])
        resync_decision(payload, 2, f"{label} 同步决定正文与实际指纹后进入语义核验")
        probe(label, lambda payload=payload: counted_check(payload, "NORMALIZE_AND_LOAD",
                                                          current_bindings=bindings_base),
              "blocked", contains=contains)

    p07 = counted_prepare(counted_create(BATCH_ID, bindings_base), "GATE1", gate1_materials(),
                          current_bindings=bindings_base)
    p07["state"]["requests"]["GATE1"].pop("request_id")
    resync_state(p07, "P07 删除待决定请求的 request_id 并同步外层指纹")
    probe("R1_P07_pending_request_missing_request_id",
          lambda: counted_record(p07, decision("GATE1", {"request_id": "x", "materials_sha256": "y"},
                                              "APPROVE", event_id="EVT-P07"),
                                 current_bindings=bindings_base),
          "blocked", contains="state.requests.GATE1.request_id")

    p08 = fresh_gate1_approved()
    p08["state"]["simulated_decisions"] = [1]
    resync_state(p08, "P08 模拟决定条目改为整数 1 并同步外层指纹")
    probe("R1_P08_decision_entry_not_object",
          lambda: counted_check(p08, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="simulated_decisions[0]")

    p09 = fresh_gate1_approved()
    probe("R1_P09_row_count_float",
          lambda: counted_prepare(p09, "GATE2",
                                  gate2_materials(mutate=lambda m: m["evidence"]["load_report"]["row_counts"]
                                                  .__setitem__("suppliers", 20.0)),
                                  current_bindings=bindings_base),
          "blocked", contains="row_counts.suppliers")

    p10 = fresh_gate1_approved()
    p10["state"]["history"][0]["seq"] = True
    resync_state(p10, "P10 首事件 seq 改为 true 并同步外层指纹")
    probe("R1_P10_history_seq_bool",
          lambda: counted_check(p10, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="history[0].seq")

    p10b = fresh_gate1_approved()
    p10b["state"]["history"][0]["seq"] = 1.0
    resync_state(p10b, "seq=1.0 数值等价但类型错误")
    probe("R1_history_seq_float_equivalent",
          lambda: counted_check(p10b, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="history[0].seq")

    # 目标针对性检查：request_id 与材料内容/指纹自相矛盾
    request_tamper = fresh_gate1_approved()
    original_request_id = request_tamper["state"]["requests"]["GATE1"]["request_id"]
    request_tamper["state"]["requests"]["GATE1"]["request_id"] = f"GATE1/{BATCH_ID}/" + "9" * 24
    request_tamper["state"]["history"][1]["request_id"] = request_tamper["state"]["requests"]["GATE1"]["request_id"]
    resync_state(request_tamper, "更改 request_id 及事件引用但材料不变，用于确定性请求 ID 核验")
    if original_request_id == request_tamper["state"]["requests"]["GATE1"]["request_id"]:
        r1_problems.append("request_id 变更用例无效")
    probe("R1_request_id_not_deterministic",
          lambda: counted_check(request_tamper, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="request_id")

    material_tamper = fresh_gate1_approved()
    material_tamper["state"]["requests"]["GATE1"]["materials"]["evidence"]["quality_report"]["result"] = "issues_found"
    new_materials_sha = controller.canonical_sha256(material_tamper["state"]["requests"]["GATE1"]["materials"])
    material_tamper["state"]["requests"]["GATE1"]["materials_sha256"] = new_materials_sha
    material_tamper["state"]["history"][1]["materials_sha256"] = new_materials_sha
    material_tamper["state"]["requests"]["GATE1"]["request_id"] = controller._request_id_for(
        material_tamper["state"], "GATE1", new_materials_sha, None)
    material_tamper["state"]["history"][1]["request_id"] = material_tamper["state"]["requests"]["GATE1"]["request_id"]
    resync_state(material_tamper, "同步材料指纹与确定性 request_id 后，材料本身违反原 prepare 协议")
    probe("R1_request_materials_protocol_violated",
          lambda: counted_check(material_tamper, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="quality_report.result")

    # 单行合法小样（C02，当前冻结装载器版本）：row_count=1 可用，true 不可用
    c02_dir = GPT_CASE.parent / "C02"
    single_problems: list = []
    if not (c02_dir / "normalized.json").exists():
        single_problems.append(f"缺少单行小样：{c02_dir}")
    else:
        c02_normalized = json.loads((c02_dir / "normalized.json").read_text(encoding="utf-8"))
        c02_load = json.loads((c02_dir / "load_report.json").read_text(encoding="utf-8"))
        c02_checker = json.loads((c02_dir / "checker_report.json").read_text(encoding="utf-8"))
        c02_row_counts = c02_load["row_counts"]
        if c02_row_counts.get("payables") != 1:
            single_problems.append(f"C02 payables 行数应为 1，实际 {c02_row_counts.get('payables')!r}")
        c02_bindings = bindings(input_sha256=c02_normalized["source"]["input_sha256"])
        c02_scope = dict(scope_base)
        c02_batch = "BATCH-C02-005"

        def c02_materials(bindings_payload, row_counts=None):
            payload = gate2_materials(bindings_payload, normalized_payload=c02_normalized,
                                      load_payload=c02_load, scope=c02_scope, batch_id=c02_batch)
            if row_counts is not None:
                payload["evidence"]["load_report"]["row_counts"] = row_counts
            return payload

        c02_base = counted_create(c02_batch, c02_bindings)
        c02_base = counted_prepare(c02_base, "GATE1",
                                   gate1_materials(c02_bindings, evidence=c02_checker, batch_id=c02_batch),
                                   current_bindings=c02_bindings)
        c02_base = counted_record(c02_base, decision("GATE1", c02_base["state"]["requests"]["GATE1"], "APPROVE",
                                                     event_id="EVT-C02-G1", batch_id=c02_batch),
                                  current_bindings=c02_bindings)
        c02_ok = counted_prepare(c02_base, "GATE2", c02_materials(c02_bindings), current_bindings=c02_bindings)
        if c02_ok["state"]["phase"] != "DEV_GATE2_PENDING":
            single_problems.append("C02 单行小样合法 row_counts 应能建立 Gate2 请求")
        probe("R1_single_row_count_one_legal",
              lambda: counted_prepare(c02_base, "GATE2", c02_materials(c02_bindings),
                                      current_bindings=c02_bindings),
              "ok", sync_ops=["无：C02 单行小样 row_counts.payables=1 为整数，合法可用"])
        probe("R1_single_row_count_true_illegal",
              lambda: counted_prepare(c02_base, "GATE2",
                                      c02_materials(c02_bindings,
                                                    row_counts={**c02_row_counts, "payables": True}),
                                      current_bindings=c02_bindings),
              "blocked", contains="row_counts.payables")
    record("R1_SINGLE_ROW_FIXTURE", "flow", single_problems,
           fixture="data/sqlite_tests/task007_r2_gpt_20261011_081630/cases/C02",
           note="该小样为当前冻结装载器 TASK-005-sqlite-load-1.2 已验收结果；先确认 payables 记录数为 1")

    (container / "sync_operations.json").write_text(
        json.dumps(sync_notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record("R1_SYNC_OPERATIONS_RECORDED", "flow", [] if sync_notes else ["未记录任何同步操作"],
           sync_operations=len(sync_notes))

    # ---------- 11. R2 新增：事件引用一致性（Q01—Q08）与保存文件重放 ----------
    r2_problems: list = []

    def gate1_approved_state():
        flow = counted_create(BATCH_ID, bindings_base)
        flow = counted_prepare(flow, "GATE1", gate1_materials(), current_bindings=bindings_base)
        return counted_record(flow, decision("GATE1", flow["state"]["requests"]["GATE1"], "APPROVE",
                                             event_id="EVT-Q-G1"), current_bindings=bindings_base)

    def gate2_pending_state():
        flow = gate1_approved_state()
        return counted_prepare(flow, "GATE2", gate2_materials(), current_bindings=bindings_base)

    def full_approved_state():
        flow = gate2_pending_state()
        return counted_record(flow, decision("GATE2", flow["state"]["requests"]["GATE2"], "APPROVE",
                                             event_id="EVT-Q-G2"), current_bindings=bindings_base)

    q01 = gate1_approved_state()
    q01["state"]["history"][2]["event_id"] = "OTHER-EVENT-ID"
    resync_state(q01, "Q01 只改历史决定事件顶层 event_id 并同步外层指纹，决定正文保持真实")
    probe("R2_Q01_event_id_conflicts_with_decision",
          lambda: counted_check(q01, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="history[2].event_id")

    q02 = gate1_approved_state()
    q02["state"]["history"][2]["gate"] = "GATE2"
    resync_state(q02, "Q02 只改该事件的 gate，event_type 与决定正文仍是 GATE1")
    probe("R2_Q02_event_gate_conflicts_with_type",
          lambda: counted_check(q02, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="history[2].gate")

    q03 = gate1_approved_state()
    q03["state"]["history"][2]["request_id"] = "OTHER-REQUEST"
    resync_state(q03, "Q03 只改该事件的 request_id，正文仍指向真实请求")
    probe("R2_Q03_event_request_id_conflicts",
          lambda: counted_check(q03, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="history[2].request_id")

    q04 = gate1_approved_state()
    q04["state"]["history"][2]["materials_sha256"] = "0" * 64
    resync_state(q04, "Q04 只把该事件的 materials_sha256 改全零")
    probe("R2_Q04_event_materials_conflicts",
          lambda: counted_check(q04, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="history[2].materials_sha256")

    q05 = gate1_approved_state()
    q05["state"]["history"][0]["batch_id"] = "OTHER-BATCH"
    resync_state(q05, "Q05 只改创建事件的 batch_id")
    probe("R2_Q05_created_event_batch_conflicts",
          lambda: counted_check(q05, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="history[0].batch_id")

    q06 = gate1_approved_state()
    q06["state"]["history"][1]["run_bindings_sha256"] = "0" * 64
    resync_state(q06, "Q06 只把 Gate1 请求事件的 run_bindings_sha256 改全零")
    probe("R2_Q06_request_event_binding_conflicts",
          lambda: counted_check(q06, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="history[1].run_bindings_sha256")

    q07 = gate1_approved_state()
    q07["state"]["requests"]["GATE2"] = copy.deepcopy(gate2_pending_state()["state"]["requests"]["GATE2"])
    resync_state(q07, "Q07 放入同批次形状合法的 Gate2 请求但不添加 history 事件")
    probe("R2_Q07_extra_request_without_history_event",
          lambda: counted_check(q07, "NORMALIZE_AND_LOAD", current_bindings=bindings_base),
          "blocked", contains="state.requests.GATE2")

    q08 = full_approved_state()
    q08["state"]["simulated_decisions"] = list(reversed(q08["state"]["simulated_decisions"]))
    resync_state(q08, "Q08 反转 simulated_decisions 顺序（ID 集合不变）")
    probe("R2_Q08_decisions_reordered",
          lambda: counted_check(q08, "SCREEN_AND_BUILD_FACTS", current_bindings=bindings_base),
          "blocked", contains="simulated_decisions[0]")

    # 保存对象的离线核对：引用可解析、内容指纹正确、参数完整（可 bind）
    def restore_reference(reference: dict):
        path = container / reference["object_path"]
        raw = path.read_bytes()
        if reference.get("file_sha256") and hashlib.sha256(raw).hexdigest() != reference["file_sha256"]:
            raise ValueError(f"对象文件字节指纹不符：{reference['object_path']}")
        payload = json.loads(raw.decode("utf-8"))
        if controller.canonical_sha256(payload) != reference["object_sha256"]:
            raise ValueError(f"对象内容规范指纹不符：{reference['object_path']}")
        return payload

    real_functions = {"create_dev_workflow": real_create, "prepare_dev_gate": real_prepare,
                      "record_dev_decision": real_record, "check_dev_action": real_check}
    reference_problems: list = []
    reference_checked = 0
    kwargs_records = 0
    for detail in checks:
        call = detail.get("call")
        if not call:
            continue
        try:
            restored_args = [restore_reference(ref) for _, ref in sorted(call["args"].items())]
            restored_kwargs = {key: restore_reference(ref) for key, ref in sorted(call["kwargs"].items())}
        except Exception as exc:  # noqa: BLE001
            reference_problems.append(f"{detail['case']} 引用无法解析或指纹不符：{exc}")
            continue
        reference_checked += 1
        if call["kwargs"]:
            kwargs_records += 1
        try:
            inspect.signature(getattr(controller, call["function"])).bind(*restored_args, **restored_kwargs)
        except TypeError as exc:
            reference_problems.append(f"{detail['case']} 参数不完整（保存的实参无法重建调用）：{exc}")
        if detail["outcome"] != "ok" and detail.get("input_workflow_unchanged") is False:
            reference_problems.append(f"{detail['case']} 阻断调用修改了实参 workflow")
        if detail["outcome"] != "ok" and detail.get("returned_state", "missing") is not None:
            reference_problems.append(f"{detail['case']} 阻断调用应记录“无返回状态”")
    record("R2_SAVED_REFERENCES_RESOLVABLE", "flow", reference_problems,
           references_checked=reference_checked, records_with_kwargs=kwargs_records)

    # 从保存的 args／kwargs 文件重放：五条绑定变化负向 + 一条成功调用
    replay_records: list = []
    replay_calls = 0
    for label in ("S6_binding_change_input", "S6_binding_change_code", "S6_binding_change_rule_sql",
                  "S6_binding_change_config", "S6_binding_change_contract"):
        detail = next(item for item in checks if item.get("case") == label)
        call = detail["call"]
        restored_args = [restore_reference(ref) for _, ref in sorted(call["args"].items())]
        restored_kwargs = {key: restore_reference(ref) for key, ref in sorted(call["kwargs"].items())}
        before_fingerprint = controller.canonical_sha256({"args": restored_args, "kwargs": restored_kwargs})
        outcome, message = "ok", ""
        try:
            real_functions[call["function"]](*restored_args, **restored_kwargs)
        except controller.WorkflowBlocked as exc:
            outcome, message = "blocked", str(exc)
        except controller.WorkflowError as exc:
            outcome, message = "error", str(exc)
        replay_calls += 1
        after_fingerprint = controller.canonical_sha256({"args": restored_args, "kwargs": restored_kwargs})
        matches_first = (outcome == detail["outcome"] and message == detail["message"])
        ok = (outcome == "blocked" and "绑定" in message and after_fingerprint == before_fingerprint
              and matches_first)
        replay_records.append({
            "case": label, "kind": "binding_change_replay", "function": call["function"],
            "restored_args": [call["args"][key] for key in sorted(call["args"])],
            "restored_kwargs": {key: call["kwargs"][key] for key in sorted(call["kwargs"])},
            "kwargs_keys": sorted(call["kwargs"].keys()),
            "outcome": outcome, "exception_class": "WorkflowBlocked" if outcome == "blocked" else None,
            "message": message, "matches_first_result": matches_first,
            "args_fingerprint_before": before_fingerprint, "args_fingerprint_after": after_fingerprint,
            "ok": ok,
        })
        if not ok:
            r2_problems.append(f"{label} 从保存文件重放未得到绑定变化阻断或结果与首次不一致")
        print(f"[{'PASS' if ok else 'FAIL'}] R2_replay_{label} -> {outcome} | {message[:80]}")

    success_label = "S1_normalize_before_gate1_approval"
    success_detail = next(item for item in checks if item.get("case") == success_label)
    success_call = success_detail["call"]
    success_args = [restore_reference(ref) for _, ref in sorted(success_call["args"].items())]
    success_kwargs = {key: restore_reference(ref) for key, ref in sorted(success_call["kwargs"].items())}
    success_value = real_functions[success_call["function"]](*success_args, **success_kwargs)
    replay_calls += 1
    saved_success = restore_reference(success_detail["result"])
    success_equal = controller.canonical_json(success_value) == controller.canonical_json(saved_success)
    replay_records.append({
        "case": success_label, "kind": "success_replay", "function": success_call["function"],
        "restored_args": [success_call["args"][key] for key in sorted(success_call["args"])],
        "restored_kwargs": {key: success_call["kwargs"][key] for key in sorted(success_call["kwargs"])},
        "return_equal_to_saved": success_equal,
        "return": save_object(success_value, f"replay.{success_label}.return"),
        "ok": success_equal,
    })
    if not success_equal:
        r2_problems.append("成功调用重放的完整返回与首次结果不相等")
    print(f"[{'PASS' if success_equal else 'FAIL'}] R2_replay_success_{success_label} "
          f"（完整返回与首次精确相等）")

    (container / "replay_records.json").write_text(
        json.dumps(replay_records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record("R2_SAVED_FILE_REPLAY", "flow", r2_problems, replays=len(replay_records))

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

    simulated_decisions = len(approved_state["state"]["simulated_decisions"])
    real_approvals = sum(1 for key in ("gate1_approval", "gate2_approval")
                         if approved_state["state"][key] is not None)
    counts = {
        "api_calls": call_counts,
        "api_calls_entry": sum(call_counts.values()),
        "api_calls_replay": replay_calls,
        "api_calls_total": sum(call_counts.values()) + replay_calls,
        "original_probes": sum(1 for item in checks if item["kind"] == "probe"
                               and not item["case"].startswith("R1_")
                               and not item["case"].startswith("R2_")),
        "new_r1_probes": sum(1 for item in checks if item["kind"] == "probe"
                             and item["case"].startswith("R1_")),
        "new_r2_probes": sum(1 for item in checks if item["kind"] == "probe"
                             and item["case"].startswith("R2_")),
        "probes": sum(1 for item in checks if item["kind"] == "probe"),
        "flow_checks": sum(1 for item in checks if item["kind"] == "flow"),
        "helper_self_tests": len(helper_self_tests),
        "helper_self_test_ok": sum(1 for item in helper_self_tests if item["ok"]),
        "helper_self_test_in_main_checks": sum(1 for item in helper_self_tests if item["in_main_checks"]),
        "saved_references_checked": reference_checked,
        "saved_records_with_kwargs": kwargs_records,
        "replay_records": len(replay_records),
        "sync_operations_recorded": len(sync_notes),
        "saved_objects": len(object_index),
        "key_workflows_saved": len(key_workflows),
        "guard_probe_calls": 1,
        "normal_calls_inside_guard": 3,
        "simulated_decisions_in_main_flow": simulated_decisions,
        "real_human_approvals": real_approvals,
        "test_failures": len(failures),
    }
    summary = {
        "task": "TASK-009-R1",
        "out_dir": str(container),
        "python": sys.version.split()[0],
        "controller": {"path": str(CONTROLLER), "sha256": sha256(CONTROLLER),
                       "version": controller.WORKFLOW_VERSION},
        "counts": counts,
        "checks": checks,
        "failures": failures,
        "helper_self_tests": helper_self_tests,
        "sync_operations": sync_notes,
        "key_workflows": key_workflows,
        "object_index": object_index,
        "protected_files_count": len(PROTECTED_FILES),
        "protected_files_unchanged": not changed,
        "note": "本次重放既有开发结果验证控制协议；不证明真实管道按此顺序执行，也不为旧产物追认真实批准。",
    }
    (container / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    (container / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    (container / "helper_self_tests.json").write_text(
        json.dumps(helper_self_tests, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (container / "object_index.json").write_text(
        json.dumps(object_index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (container / "final_state.json").write_text(
        json.dumps(approved_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"API 调用（入口）：create {call_counts['create_dev_workflow']}、prepare {call_counts['prepare_dev_gate']}、"
          f"record {call_counts['record_dev_decision']}、check {call_counts['check_dev_action']}，"
          f"合计 {counts['api_calls_entry']}；保存文件重放 {counts['api_calls_replay']} 次；"
          f"真实总次数 {counts['api_calls_total']}")
    print(f"原探针 {counts['original_probes']} 项、R1 新增 {counts['new_r1_probes']} 项、R2 新增 {counts['new_r2_probes']} 项、"
          f"流程检查 {counts['flow_checks']} 项")
    print(f"helper 自测 {counts['helper_self_tests']} 项（成功 {counts['helper_self_test_ok']}，"
          f"写入主 checks {counts['helper_self_test_in_main_checks']} 项）")
    print(f"保存引用核对 {counts['saved_references_checked']} 条（含关键字实参 {counts['saved_records_with_kwargs']} 条）、"
          f"重放记录 {counts['replay_records']} 条、同步操作 {counts['sync_operations_recorded']} 次、"
          f"保存对象 {counts['saved_objects']} 份")
    print(f"模拟决定 {counts['simulated_decisions_in_main_flow']} 条、真实人类批准 {counts['real_human_approvals']} 条、"
          f"测试失败 {counts['test_failures']}")
    print(f"守卫受控探测 {counts['guard_probe_calls']} 次与守卫内正常调用 "
          f"{counts['normal_calls_inside_guard']} 次分开统计")
    print(f"受保护文件前后哈希一致: {summary['protected_files_unchanged']}（{summary['protected_files_count']} 个）")
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
