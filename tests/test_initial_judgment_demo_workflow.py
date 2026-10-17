#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-017 开发态宿主保存模拟独立初判——有界验证与证据入口。

用法::

    .venv\\Scripts\\python.exe -B tests\\test_initial_judgment_demo_workflow.py --out-dir <全新容器> [--only <子集>]

只做本卡 §7 的七组有限检查；不重跑 TASK-002—016 历史入口、冻结宿主测试或事实核心 21 组。
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
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

HOST_PATH = PROJECT_ROOT / "scripts" / "run_demo_workflow.py"
CORE_PATH = PROJECT_ROOT / "scripts" / "build_demo_initial_judgment.py"
CONTAINER_ROOT = PROJECT_ROOT / "data" / "workflow_host_tests"
BATCH_ROOT = PROJECT_ROOT / "data" / "batches"
SQLITE_ROOT = PROJECT_ROOT / "data" / "sqlite_tests" / "workflow_gate2"
WORKBOOK_MAIN = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a" / "input" / "erp_export.xlsx"
FIXTURE_ROOT = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a" / "fixtures"

BASELINE = (PROJECT_ROOT / "data" / "reviews" / "task016_r1_gpt_20261013_023714"
            / "source_hashes_after.json")
BASELINE_SHA256 = "7d7287cf5657489c1369b0206d02c3487b2b680fcec06133c7e13d2ecd81d6ea"
BASELINE_ENTRIES = 124539
ALLOWED_CHANGES = {"scripts/run_demo_workflow.py", "docs/WORKFLOW_HOST_GUIDE.md"}
R1_BASELINE = (PROJECT_ROOT / "data" / "reviews" / "task017_gpt_20261013_031915"
               / "source_hashes_after.json")
R1_BASELINE_SHA256 = "8b07d991b25326d322ffcfc1ee291d295eb37cafb303d7d4ba5020cd553aea2c"
R1_BASELINE_ENTRIES = 126441
R1_ALLOWED_CHANGES = {"scripts/run_demo_workflow.py",
                      "tests/test_initial_judgment_demo_workflow.py",
                      "docs/WORKFLOW_HOST_GUIDE.md"}
FROZEN_HASHES = {
    "scripts/build_demo_initial_judgment.py":
        "0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c",
    "tests/test_build_demo_initial_judgment.py":
        "c0ef730e59ad78f54d7d60014289ea56ca7e79c764f9afba515c1c77449b62f3",
    "docs/INITIAL_JUDGMENT_GUIDE.md":
        "2bbaa876ae7a76175f3462d9395b7bbc8e4bec5b1631030ff3fe32142d0286f5",
    "scripts/control_demo_workflow.py":
        "a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c",
    "scripts/build_demo_fact_packet.py":
        "f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62",
    "tests/test_fact_packet_demo_workflow.py":
        "90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e",
}
SKIP_DIRS = {".venv", ".git", "__pycache__"}
DOWNSTREAM_GUARDS = ("normalize_workbook", "load_normalized_to_sqlite", "screen_sqlite",
                     "verify_rule_facts", "build_fact_packet",
                     "build_initial_judgment_record")

PY = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")


def load_host():
    spec = importlib.util.spec_from_file_location("host_under_test", HOST_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["host_under_test"] = module
    spec.loader.exec_module(module)
    return module


HOST = load_host()
CORE = HOST.INITIAL_JUDGMENT_MODULE

CONTAINER: Path | None = None
CLI_RECORDS: list = []
API_RECORDS: list = []
CALL_REGISTRY: list = []
CHECKS: list = []
COUNTS = {
    "cli_calls": 0,
    "api_calls": 0,
    "core_calls_observed": 0,
    "api_returned": 0,
    "api_blocked": 0,
    "api_unexpected_errors": 0,
    "guard_hits": 0,
    "missing_records": None,
    "unregistered_records": None,
    "protection_executed": False,
    "isolation_self_test": None,
    "voucher_0008_physical_total": 0,
    "voucher_0008_parseable_total": 0,
    "voucher_0008_half_written_total": 0,
    "recorded_failure_scenes": 0,
    "recovered_success_total": 0,
    "fault_injections": 0,
}
HOST_API_CALLS: list = []
CORE_CALL_LOG: list = []


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path) -> str:
    return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()


def artifact(path_str: str) -> Path:
    return PROJECT_ROOT / str(path_str)


def canonical_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def canonical_sha256(payload) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def same_json(left, right) -> bool:
    try:
        return canonical_json(left) == canonical_json(right)
    except (TypeError, ValueError):
        return False


def save_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return path


def load_json_if_parseable(path) -> tuple:
    path = Path(path)
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, False


def tree_hashes(root: Path) -> dict:
    result = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256(path)
    return result


# ---------------------------------------------------------------------------
# 调用登记
# ---------------------------------------------------------------------------


def run_cli(label: str, args: list, expect_exit: int) -> dict:
    COUNTS["cli_calls"] += 1
    command = [PY, "-B", str(HOST_PATH), *args]
    done = subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
                          encoding="utf-8")
    payload = None
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError:
        payload = None
    entry = {"label": label, "kind": "cli", "command": command, "cwd": str(PROJECT_ROOT),
             "argv": args, "expect_exit_code": expect_exit, "exit_code": done.returncode,
             "exit_code_matches": done.returncode == expect_exit, "stdout": done.stdout,
             "stderr": done.stderr, "payload": payload}
    stdout_path = CONTAINER / "cli_logs" / f"{label}.stdout.txt"
    stderr_path = CONTAINER / "cli_logs" / f"{label}.stderr.txt"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(done.stdout or "", encoding="utf-8")
    stderr_path.write_text(done.stderr or "", encoding="utf-8")
    entry["stdout_path"] = rel(stdout_path)
    entry["stdout_sha256"] = sha256(stdout_path)
    entry["stderr_path"] = rel(stderr_path)
    entry["stderr_sha256"] = sha256(stderr_path)
    CLI_RECORDS.append(entry)
    CALL_REGISTRY.append({"record": f"cli:{label}", "kind": "cli",
                          "detail": f"exit={done.returncode}"})
    return entry


class RealCoreObserver:
    """在**宿主实际使用的模块对象**上包裹冻结纯核心，观察真实入参、三时点指纹与完整返回。

    只做观察：不改入参、不改返回、不在观察中写文件（返回后在测试层另存单份）。
    """

    def __init__(self, module):
        self.module = module
        self.real = module.build_initial_judgment_record
        self.calls: list = []
        self.active = False

    def activate(self) -> None:
        if not self.active:
            self.module.build_initial_judgment_record = self._observed
            self.active = True

    def deactivate(self) -> None:
        if self.active:
            self.module.build_initial_judgment_record = self.real
            self.active = False

    def mark(self) -> int:
        return len(self.calls)

    def window(self, start: int) -> list:
        return list(self.calls[start:])

    def _observed(self, batch_id, fact_packet, submission, *, expected_packet_sha256):
        entry = {"seq": len(self.calls) + 1, "batch_id": batch_id,
                 "expected_packet_sha256": expected_packet_sha256,
                 "packet_ref": fact_packet, "submission_ref": submission,
                 "before": {"packet": canonical_sha256(fact_packet),
                            "submission": canonical_sha256(submission)}}
        self.calls.append(entry)
        COUNTS["real_core_calls_observed"] = COUNTS.get("real_core_calls_observed", 0) + 1
        COUNTS["core_calls_observed"] = COUNTS["real_core_calls_observed"]
        try:
            result = self.real(batch_id, fact_packet, submission,
                               expected_packet_sha256=expected_packet_sha256)
        except BaseException as exc:  # noqa: BLE001
            entry["after_core"] = {"packet": canonical_sha256(fact_packet),
                                   "submission": canonical_sha256(submission)}
            entry["outcome"] = "raised"
            entry["exception_class"] = type(exc).__name__
            entry["message"] = str(exc)
            entry["traceback"] = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__))
            raise
        entry["after_core"] = {"packet": canonical_sha256(fact_packet),
                               "submission": canonical_sha256(submission)}
        entry["outcome"] = "returned"
        entry["complete_return"] = result
        entry["complete_return_sha256"] = canonical_sha256(result)
        return result


CORE_OBSERVER = RealCoreObserver(HOST.INITIAL_JUDGMENT_MODULE)


def record_api(label: str, func, *args, expect_exception=None, **kwargs) -> dict:
    """登记一次宿主公开 API 调用；真实纯核心次数由 CORE_OBSERVER 独立观察。"""
    COUNTS["api_calls"] += 1
    core_before = len(CORE_OBSERVER.calls)
    entry = {"label": label, "kind": "api", "function": getattr(func, "__name__", "core_recording"),
             "expect_exception": getattr(expect_exception, "__name__", None)}
    try:
        result = func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001
        matched = expect_exception is not None and isinstance(exc, expect_exception)
        entry["outcome"] = "raised" if matched else "unexpected"
        entry["exception_class"] = type(exc).__name__
        entry["message"] = str(exc)
        entry["reasons"] = [str(item) for item in getattr(exc, "reasons", []) or []]
        entry["stage"] = getattr(exc, "stage", None)
        entry["exception_chain"] = [
            {"class": type(item).__name__, "message": str(item)}
            for item in ([exc] + list(_cause_chain(exc)))]
        entry["traceback"] = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        path = CONTAINER / "api_records" / f"{label}.exception.json"
        save_json(path, entry)
        entry["exception_path"] = rel(path)
        entry["exception_sha256"] = sha256(path)
        COUNTS["api_blocked" if matched else "api_unexpected_errors"] += 1
    else:
        entry["outcome"] = "returned"
        path = CONTAINER / "api_records" / f"{label}.return.json"
        save_json(path, result)
        entry["return_path"] = rel(path)
        entry["return_sha256"] = sha256(path)
        COUNTS["api_returned"] += 1
    entry["host_api_delta"] = 1
    entry["core_calls_delta"] = len(CORE_OBSERVER.calls) - core_before
    API_RECORDS.append(entry)
    CALL_REGISTRY.append({"record": f"api:{label}", "kind": "api",
                          "detail": entry["outcome"],
                          "core_calls_delta": entry["core_calls_delta"]})
    return entry


def save_core_observations(label: str) -> list:
    """把本轮观察到的真实核心调用落盘（含完整返回单份保存与三时点指纹）。"""
    saved = []
    for entry in CORE_OBSERVER.calls:
        row = {key: value for key, value in entry.items()
               if key not in ("packet_ref", "submission_ref", "complete_return")}
        if "complete_return" in entry:
            path = CONTAINER / "core_returns" / f"{label}_call{entry['seq']}_return.json"
            save_json(path, entry["complete_return"])
            row["complete_return_path"] = rel(path)
            row["complete_return_file_sha256"] = sha256(path)
        if entry.get("traceback"):
            tb_path = CONTAINER / "core_returns" / f"{label}_call{entry['seq']}_traceback.txt"
            tb_path.parent.mkdir(parents=True, exist_ok=True)
            tb_path.write_text(entry["traceback"], encoding="utf-8")
            row["traceback_path"] = rel(tb_path)
        saved.append(row)
    return saved


def _cause_chain(exc):
    seen = []
    current = exc.__cause__ or exc.__context__
    while current is not None and len(seen) < 8:
        seen.append(current)
        current = current.__cause__ or current.__context__
    return seen


def check(case: str, owner: str, problems, **extra) -> None:
    result = "PASS" if not problems else "FAIL"
    CHECKS.append({"case": case, "owner": owner, "result": result, "problems": list(problems)[:12],
                   **extra})
    print(f"    [{result}] {case}")
    for problem in list(problems)[:6]:
        print(f"        - {problem}")


# ---------------------------------------------------------------------------
# 批次构建
# ---------------------------------------------------------------------------


def decision_file(batch: Path, revision: int, gate: str, value: str, event_id: str) -> str:
    payload = json.loads((batch / f"workflow/checkpoints/{revision:04d}.json")
                         .read_text(encoding="utf-8"))
    request = payload["workflow"]["state"]["requests"][gate]
    body = {"event_id": event_id, "batch_id": batch.name, "gate": gate,
            "request_id": request["request_id"], "materials_sha256": request["materials_sha256"],
            "decision": value, "actor_kind": "SIMULATED_HUMAN", "actor_id": "sim-analyst-01",
            "occurred_at": "2026-10-13T10:00:00+08:00",
            "reason": f"【模拟测试】TASK-017 有界验证用 {gate} 模拟决定（非真实批准）",
            "simulation": "SIMULATED_TEST_ONLY",
            "confirmations": ({"scope_and_source_reviewed": True} if gate == "GATE1"
                              else {"reconciliation_reviewed": True})}
    path = CONTAINER / "decisions" / f"{batch.name}_{gate}.json"
    save_json(path, body)
    return str(path)


def chain_to_fact_packet(label: str, fixture: str) -> tuple:
    """真实建链至 0007（接收 → Gate1 → 标准化/装载 → Gate2 → 筛查 → 复算 → 事实底稿）。"""
    batch = BATCH_ROOT / CONTAINER.name / label
    workbook = WORKBOOK_MAIN if fixture == "main" else FIXTURE_ROOT / fixture
    run_cli(f"{label}_start",
            ["start", "--workbook", str(workbook), "--batch-dir", str(batch),
             "--source-description", f"TASK-017 有界验证（{label}，合成数据，非真实审计）"], 0)
    run_cli(f"{label}_gate1",
            ["record-simulated-decision", "--batch-dir", str(batch), "--decision-file",
             decision_file(batch, 1, "GATE1", "APPROVE", f"EV-T17-{label}-G1")], 0)
    run_cli(f"{label}_prepare", ["prepare-gate2", "--batch-dir", str(batch)], 0)
    run_cli(f"{label}_gate2",
            ["record-simulated-gate2-decision", "--batch-dir", str(batch), "--decision-file",
             decision_file(batch, 3, "GATE2", "APPROVE", f"EV-T17-{label}-G2")], 0)
    run_cli(f"{label}_screen", ["screen-rules", "--batch-dir", str(batch)], 0)
    run_cli(f"{label}_crosscheck", ["crosscheck-rules", "--batch-dir", str(batch)], 0)
    run_cli(f"{label}_fact_packet", ["build-fact-packet", "--batch-dir", str(batch)], 0)
    return batch


def submission_for(batch: Path, event_id: str, assessment: str, reason: str, *, extra=None) -> dict:
    packet = json.loads((batch / "workflow/fact_packet/fact_packet.json")
                        .read_text(encoding="utf-8"))
    body = {
        "submission_version": CORE.SUBMISSION_VERSION,
        "event_id": event_id,
        "batch_id": batch.name,
        "fact_packet_sha256": canonical_sha256(packet),
        "scope": CORE.SCOPE,
        "actor_kind": CORE.ACTOR_KIND,
        "actor_id": "sim-analyst-01",
        "simulation": CORE.SIMULATION,
        "occurred_at": "2026-10-13T10:30:00+08:00",
        "assessment": assessment,
        "reason": reason,
    }
    if extra:
        body.update(extra)
    return body


def write_submission(label: str, submission: dict) -> Path:
    path = CONTAINER / "submissions" / f"{label}.json"
    save_json(path, submission)
    return path


# ---------------------------------------------------------------------------
# 各组
# ---------------------------------------------------------------------------


def group_main() -> list:
    problems: list = []
    batch = chain_to_fact_packet("main_01", "main")
    fact_path = batch / "workflow/fact_packet/fact_packet.json"
    packet = json.loads(fact_path.read_text(encoding="utf-8"))
    findings = packet["findings"]
    counts = packet["summary"]["rule_counts"]
    if len(findings) != 12:
        problems.append(f"MAIN 线索条数不是 12：{len(findings)}")
    if counts != {"R01": 3, "R02": 5, "R03": 2, "R04": 2}:
        problems.append(f"MAIN 规则分布不符：{counts}")
    if packet["summary"]["r02_overpayment_total_cents"] != 1600000:
        problems.append("MAIN R02 超额合计不是 1600000 分")
    packet_sha = canonical_sha256(packet)
    submission = submission_for(
        batch, "EV-SIM-T17-MAIN-0001",
        "【模拟测试】暂不能判断，需要补充证据后在结论中说明",
        "【模拟测试】现有线索不足以形成确定结论，需调用方补充原始凭证。",
        extra={"needed_evidence": ["【模拟测试】银行流水原件"],
               "finding_notes": [{"finding_id": findings[0]["finding_id"],
                                  "note": "【模拟测试】该线索待补充证据"}]})
    submission_path = write_submission("main_01", submission)
    core_mark = CORE_OBSERVER.mark()
    entry = record_api("main_record", HOST.record_simulated_initial_judgment, batch,
                       submission, expect_exception=HOST.WorkflowHostBlocked)
    observed_calls = CORE_OBSERVER.window(core_mark)
    saved_calls = save_core_observations("main")
    if not observed_calls:
        problems.append("未观察到真实纯核心调用")
        return problems
    real_call = observed_calls[0]
    packet_ref = real_call["packet_ref"]
    submission_ref = real_call["submission_ref"]
    before = dict(real_call["before"])
    after_core = dict(real_call["after_core"])
    after_public = {"packet": canonical_sha256(packet_ref),
                    "submission": canonical_sha256(submission_ref)}
    after = after_public
    if entry["outcome"] != "returned":
        problems.append(f"MAIN 保存未成功：{entry.get('exception_class')} {entry.get('message')}")
        return problems
    result = json.loads(artifact(entry["return_path"]).read_text(encoding="utf-8"))
    if entry["core_calls_delta"] != 1 or len(observed_calls) != 1:
        problems.append(f"MAIN 真实核心调用不是 1 次：delta={entry['core_calls_delta']} "
                        f"observed={len(observed_calls)}")
    if real_call["expected_packet_sha256"] != canonical_sha256(packet):
        problems.append("实际核心入参的 expected 指纹与 0007 事实包规范指纹不一致")
    if before != after_core or before != after_public:
        problems.append(f"MAIN 两个真实入参三时点指纹不一致：before={before} "
                        f"after_core={after_core} after_public={after_public}")
    if "complete_return" not in real_call:
        problems.append("未捕获完整真实核心返回")
    else:
        disk_payload, disk_ok = load_json_if_parseable(
            batch / "workflow/initial_judgment/initial_judgment.json")
        if not disk_ok:
            problems.append("落盘 initial_judgment.json 不可解析")
        elif not same_json(disk_payload, real_call["complete_return"]):
            problems.append("落盘 initial_judgment.json 与该次完整真实核心返回不严格相等")
        elif real_call["complete_return_sha256"] != canonical_sha256(disk_payload):
            problems.append("完整真实核心返回的规范指纹与落盘对象不一致")
    if result.get("initial_judgment_status") != "SIMULATED_INITIAL_JUDGMENT_RECORDED":
        problems.append("MAIN 未返回 SIMULATED_INITIAL_JUDGMENT_RECORDED")
    if result.get("completed_actions", [])[-1] != "SIMULATED_INITIAL_JUDGMENT":
        problems.append(f"completed_actions 未新增模拟初判项：{result.get('completed_actions')}")
    if result.get("real_approvals") != 0 or result.get("next_step_allowed") is not False:
        problems.append("MAIN 成功摘要的真实批准/next_step_allowed 不符")
    if result.get("ai_action_simulation_allowed") is not False:
        problems.append("MAIN 未记录 AI 动作真实 false")
    paths = HOST._initial_judgment_paths(batch)
    outputs = HOST._read_initial_judgment_outputs(batch, "test_read")
    layer = result["initial_judgment"]
    # 完整核心返回与落盘 initial_judgment.json 严格相等
    record_payload = outputs["record_payload"]
    if not same_json(record_payload["record"], {}) and record_payload["record_sha256"] != \
            canonical_sha256(record_payload["record"]):
        problems.append("落盘 initial_judgment.json 的 record_sha256 与 record 规范指纹不符")
    if layer["record_sha256"] != record_payload["record_sha256"]:
        problems.append("成功摘要的 record_sha256 与落盘记录不一致")
    if layer["initial_judgment_file_sha256"] != outputs["record_file_sha256"]:
        problems.append("成功摘要的 initial_judgment 文件哈希与实读不一致")
    if layer["submission_file_sha256"] != outputs["submission_file_sha256"]:
        problems.append("成功摘要的 submission 文件哈希与实读不一致")
    if not same_json(outputs["submission"], submission):
        problems.append("submission.json 快照与本次提交对象不严格相等")
    if outputs["submission"]["assessment"] != submission["assessment"]:
        problems.append("submission.json 未保留原文")
    if layer["record_sha256"] == layer["initial_judgment_file_sha256"]:
        problems.append("record 规范指纹与文件字节哈希被混用")
    # 0008
    checkpoint8, ok8 = load_json_if_parseable(batch / "workflow/checkpoints/0008.json")
    checkpoint7, _ = load_json_if_parseable(batch / "workflow/checkpoints/0007.json")
    if not ok8:
        problems.append("0008 不可解析")
        return problems
    if checkpoint8["revision"] != 8 or isinstance(checkpoint8["revision"], bool):
        problems.append("0008 revision 不是严格整数 8")
    if checkpoint8["operation"]["kind"] != "RECORD_SIMULATED_INITIAL_JUDGMENT":
        problems.append("0008 operation.kind 不符")
    if checkpoint8["previous_file_sha256"] != sha256(batch / "workflow/checkpoints/0007.json"):
        problems.append("0008 previous_file_sha256 与 0007 实读不符")
    if not same_json(checkpoint8["workflow"], checkpoint7["workflow"]):
        problems.append("0008 workflow 与 0007 不严格相等")
    state = checkpoint8["workflow"]["state"]
    if state["gate1_approval"] is not None or state["gate2_approval"] is not None:
        problems.append("真实批准必须仍为 null")
    if state["phase"] != HOST.CONTROLLER_MODULE.PHASE_G2_APPROVED:
        problems.append("phase 不再是 DEV_GATE2_APPROVED")
    if checkpoint8["operation"]["initial_judgment_status"] != \
            "SIMULATED_INITIAL_JUDGMENT_RECORDED":
        problems.append("0008 operation 状态不符")
    # 初期阶段 status
    status = run_cli("main_status", ["status", "--batch-dir", str(batch)], 0)
    if status["payload"].get("initial_judgment_status") != "SIMULATED_INITIAL_JUDGMENT_RECORDED":
        problems.append("status 未标记模拟初判完成")
    if [item["revision"] for item in status["payload"].get("checkpoints", [])] != \
            [1, 2, 3, 4, 5, 6, 7, 8]:
        problems.append("status 链不是 0001—0008")
    # 重复提交拒绝且旧文件不变
    before_tree = tree_hashes(batch / "workflow")
    repeat = run_cli("main_repeat", ["record-simulated-initial-judgment", "--batch-dir", str(batch),
                                     "--submission-file", str(submission_path)], 1)
    after_tree = tree_hashes(batch / "workflow")
    if before_tree != after_tree:
        problems.append("重复提交改变了旧文件")
    if "0008" not in json.dumps(repeat["payload"], ensure_ascii=False):
        problems.append("重复提交的诊断未指出已有 0008")
    save_json(CONTAINER / "probe_records" / "g1_main.json", {
        "case": "g1_main", "batch_dir": str(batch), "batch_id": batch.name,
        "packet_file_sha256": sha256(fact_path), "packet_sha256": packet_sha,
        "findings_total": len(findings), "rule_counts": counts,
        "r02_overpayment_total_cents": packet["summary"]["r02_overpayment_total_cents"],
        "api_record": entry, "core_observation": {
            "calls": saved_calls, "host_api_delta": entry.get("host_api_delta"),
            "core_calls_delta": entry.get("core_calls_delta")},
        "input_fingerprints": {"before": before, "after_core": after_core,
                               "after_public": after_public},
        "layer_relative": paths["relative"],
        "layer_file_sha256": {"started": outputs["started_file_sha256"],
                              "submission": outputs["submission_file_sha256"],
                              "initial_judgment": outputs["record_file_sha256"],
                              "artifacts": outputs["artifacts_file_sha256"]},
        "checkpoint_0008_file_sha256": sha256(batch / "workflow/checkpoints/0008.json"),
        "repeat_rejected_exit": repeat["exit_code"],
        "note": "MAIN 真实建链至 0007，随后以显式模拟文本保存一次并生成 0008。"})
    COUNTS["voucher_0008_physical_total"] += 1
    COUNTS["voucher_0008_parseable_total"] += 1
    COUNTS["recovered_success_total"] += 1
    return problems


def group_premise_and_samples() -> list:
    problems: list = []
    # C03 零条：可保存“暂不能判断”，不自动判无问题
    c03 = chain_to_fact_packet("g2_c03", "C03.xlsx")
    packet3 = json.loads((c03 / "workflow/fact_packet/fact_packet.json")
                         .read_text(encoding="utf-8"))
    if packet3["findings"]:
        problems.append(f"C03 预期零条线索，实际 {len(packet3['findings'])}")
    submission3 = submission_for(c03, "EV-SIM-T17-C03-0001",
                                 "【模拟测试】暂不能判断，需要补充证据",
                                 "【模拟测试】零条命中不等于无异常，仍需人工判断。")
    submission3 = copy.deepcopy(submission3)
    entry3 = record_api("g2_c03_record", HOST.record_simulated_initial_judgment, c03, submission3,
                        expect_exception=HOST.WorkflowHostBlocked)
    if entry3["outcome"] != "returned":
        problems.append(f"C03 零条保存未成功：{entry3.get('message')}")
    else:
        # 零条不自动判“无问题”：记录里的 assessment 必须仍是调用方原文
        record3 = HOST._read_initial_judgment_outputs(c03, "test_read")["record_payload"]["record"]
        simulated = record3["simulated_initial_judgment"]
        if simulated["assessment"] != submission3["assessment"]:
            problems.append("C03 提交原文被改写（零条不得自动判无问题）")
        if record3["source"]["finding_ids"] != []:
            problems.append("C03 记录的 finding_ids 不是空列表")
    COUNTS["voucher_0008_physical_total"] += 1
    COUNTS["voucher_0008_parseable_total"] += 1
    COUNTS["recovered_success_total"] += 1

    # 早期阶段（0006）拒绝
    early = BATCH_ROOT / CONTAINER.name / "g2_early"
    run_cli("g2_early_start", ["start", "--workbook", str(FIXTURE_ROOT / "C06b.xlsx"),
                               "--batch-dir", str(early), "--source-description",
                               "TASK-017 早期阶段反例（合成数据）"], 0)
    run_cli("g2_early_gate1", ["record-simulated-decision", "--batch-dir", str(early),
                               "--decision-file",
                               decision_file(early, 1, "GATE1", "APPROVE", "EV-T17-EARLY-G1")], 0)
    run_cli("g2_early_prepare", ["prepare-gate2", "--batch-dir", str(early)], 0)
    run_cli("g2_early_gate2", ["record-simulated-gate2-decision", "--batch-dir", str(early),
                               "--decision-file",
                               decision_file(early, 3, "GATE2", "APPROVE", "EV-T17-EARLY-G2")], 0)
    run_cli("g2_early_screen", ["screen-rules", "--batch-dir", str(early)], 0)
    run_cli("g2_early_crosscheck", ["crosscheck-rules", "--batch-dir", str(early)], 0)
    early_submission = {"submission_version": CORE.SUBMISSION_VERSION,
                        "event_id": "EV-SIM-T17-EARLY-1", "batch_id": early.name,
                        "fact_packet_sha256": "0" * 64, "scope": CORE.SCOPE,
                        "actor_kind": CORE.ACTOR_KIND, "actor_id": "sim",
                        "simulation": CORE.SIMULATION, "occurred_at": "2026-10-13T10:30:00+08:00",
                        "assessment": "【模拟测试】不应到达", "reason": "【模拟测试】早期阶段"}
    early_path = write_submission("early", early_submission)
    early_entry = record_api("g2_early_record", HOST.record_simulated_initial_judgment, early,
                             early_submission, expect_exception=HOST.WorkflowHostBlocked)
    if early_entry["outcome"] != "raised":
        problems.append("0006 早期阶段未被拒绝")
    if HOST._initial_judgment_dir(early).exists():
        problems.append("早期阶段拒绝前创建了本层目录")
    before_tree = tree_hashes(early / "workflow")
    run_cli("g2_early_repeat", ["record-simulated-initial-judgment", "--batch-dir", str(early),
                                "--submission-file", str(early_path)], 1)
    if before_tree != tree_hashes(early / "workflow"):
        problems.append("早期阶段拒绝后现场被改动")

    # HOLD 对照
    hold = BATCH_ROOT / CONTAINER.name / "g2_hold"
    run_cli("g2_hold_start", ["start", "--workbook", str(FIXTURE_ROOT / "C06b.xlsx"),
                              "--batch-dir", str(hold), "--source-description",
                              "TASK-017 HOLD 反例（合成数据）"], 0)
    run_cli("g2_hold_gate1", ["record-simulated-decision", "--batch-dir", str(hold),
                              "--decision-file",
                              decision_file(hold, 1, "GATE1", "HOLD", "EV-T17-HOLD-G1")], 0)
    hold_submission = dict(early_submission, event_id="EV-SIM-T17-HOLD-1", batch_id=hold.name)
    hold_path = write_submission("hold", hold_submission)
    hold_before = tree_hashes(hold / "workflow")
    hold_entry = record_api("g2_hold_record", HOST.record_simulated_initial_judgment, hold,
                            hold_submission, expect_exception=HOST.WorkflowHostBlocked)
    hold_after = tree_hashes(hold / "workflow")
    if hold_entry["outcome"] != "raised":
        problems.append("HOLD 批次未被拒绝")
    if hold_before != hold_after:
        problems.append("HOLD 拒绝后现场被改动")

    # 轻量预检反例（在合法 0007 上、建目录前拒绝）
    c06b = chain_to_fact_packet("g2_binding", "C06b.xlsx")
    good = submission_for(c06b, "EV-SIM-T17-BIND-1", "【模拟测试】暂不能判断",
                          "【模拟测试】需要补充证据")
    state7 = json.loads((c06b / "workflow/checkpoints/0007.json")
                        .read_text(encoding="utf-8"))["workflow"]["state"]
    reused_event_id = state7["simulated_decisions"][-1]["event_id"]
    if not reused_event_id:
        problems.append("无法取到既有 Gate 事件 ID")
    preflight_cases = [
        ("wrong_batch", dict(good, batch_id="other_batch")),
        ("wrong_packet", dict(good, fact_packet_sha256="f" * 64)),
        ("real_human", dict(good, actor_kind="HUMAN")),
        ("gate_event_reuse", dict(good, event_id=reused_event_id)),
    ]
    binding_before = tree_hashes(c06b / "workflow")
    for label, body in preflight_cases:
        entry = record_api(f"g2_preflight_{label}", HOST.record_simulated_initial_judgment, c06b,
                           body, expect_exception=HOST.WorkflowHostBlocked)
        if entry["outcome"] != "raised":
            problems.append(f"轻量预检反例 {label} 未被拒绝")
    if HOST._initial_judgment_dir(c06b).exists():
        problems.append("轻量预检拒绝却创建了本层目录")
    if binding_before != tree_hashes(c06b / "workflow"):
        problems.append("轻量预检拒绝后改变了旧文件")
    # 通过轻量预检但被真实核心拒绝：空白 reason
    blank = copy.deepcopy(good)
    blank["reason"] = "   "
    blank["event_id"] = "EV-SIM-T17-BLANK-1"
    blank_entry = record_api("g2_core_blank_reason", HOST.record_simulated_initial_judgment, c06b,
                             blank, expect_exception=HOST.WorkflowHostBlocked)
    if blank_entry["outcome"] != "raised":
        problems.append("空白 reason 未被 Blocked")
    failure, failure_ok = load_json_if_parseable(c06b / "workflow/initial_judgment/failure.json")
    if not failure_ok:
        problems.append("核心拒绝后未保存本层失败诊断")
    else:
        if failure.get("target_exit_code") != 1 or failure.get("stage") != "initial_judgment":
            problems.append(f"空白 reason 失败诊断的退出码/阶段不符：{failure.get('target_exit_code')}"
                            f"/{failure.get('stage')}")
        if not failure.get("exception_chain"):
            problems.append("失败诊断缺少异常链")
        if (c06b / "workflow/checkpoints/0008.json").exists():
            problems.append("核心拒绝却生成了 0008")
        COUNTS["recorded_failure_scenes"] += 1
    # 受控 InitialJudgmentError 映射退出 2（宿主映射注入，明确标注）
    injection = BATCH_ROOT / CONTAINER.name / "g2_error_injection"
    run_cli("g2_err_start", ["start", "--workbook", str(FIXTURE_ROOT / "C06b.xlsx"),
                             "--batch-dir", str(injection), "--source-description",
                             "TASK-017 运行失败映射反例（合成数据）"], 0)
    run_cli("g2_err_gate1", ["record-simulated-decision", "--batch-dir", str(injection),
                             "--decision-file",
                             decision_file(injection, 1, "GATE1", "APPROVE", "EV-T17-ERR-G1")], 0)
    run_cli("g2_err_prepare", ["prepare-gate2", "--batch-dir", str(injection)], 0)
    run_cli("g2_err_gate2", ["record-simulated-gate2-decision", "--batch-dir", str(injection),
                             "--decision-file",
                             decision_file(injection, 3, "GATE2", "APPROVE", "EV-T17-ERR-G2")], 0)
    run_cli("g2_err_screen", ["screen-rules", "--batch-dir", str(injection)], 0)
    run_cli("g2_err_crosscheck", ["crosscheck-rules", "--batch-dir", str(injection)], 0)
    run_cli("g2_err_fact_packet", ["build-fact-packet", "--batch-dir", str(injection)], 0)
    err_submission = submission_for(injection, "EV-SIM-T17-ERR-1", "【模拟测试】暂不能判断",
                                    "【模拟测试】需要补充证据")
    err_path = write_submission("error_injection", err_submission)
    real_builder = CORE.build_initial_judgment_record

    def raising_builder(*args, **kwargs):
        raise CORE.InitialJudgmentError("【测试注入】受控 InitialJudgmentError（非真实核心业务失败）")

    CORE.build_initial_judgment_record = raising_builder
    try:
        err_entry = record_api("g2_error_mapping", HOST.record_simulated_initial_judgment, injection,
                               err_submission, expect_exception=HOST.WorkflowHostError)
    finally:
        CORE.build_initial_judgment_record = real_builder
    if err_entry["outcome"] != "raised":
        problems.append("受控 InitialJudgmentError 未被映射为 WorkflowHostError")
    err_failure, err_ok = load_json_if_parseable(
        injection / "workflow/initial_judgment/failure.json")
    if not err_ok or err_failure.get("target_exit_code") != 2:
        problems.append("运行失败诊断的 target_exit_code 不是 2")
    err_status = run_cli("g2_err_status", ["status", "--batch-dir", str(injection)], 2)
    if err_status["exit_code"] != 2:
        problems.append("新进程 status 未按运行失败退出 2")
    err_cli = run_cli("g2_error_mapping_cli", ["record-simulated-initial-judgment",
                                               "--batch-dir", str(injection),
                                               "--submission-file", str(err_path)], 2)
    if err_cli["exit_code"] != 2:
        problems.append("CLI 未按运行失败退出 2")
    COUNTS["recorded_failure_scenes"] += 1
    save_json(CONTAINER / "probe_records" / "g2_premise_and_samples.json", {
        "case": "g2_premise_and_samples",
        "c03": {"api": entry3, "findings": len(packet3["findings"])},
        "early": {"api": early_entry, "dir_created": False},
        "hold": {"api": hold_entry},
        "preflight": [item["label"] for item in API_RECORDS
                      if item["label"].startswith("g2_preflight_")],
        "reused_gate_event_id": reused_event_id,
        "blank_reason": {"api": blank_entry, "failure": failure},
        "error_mapping": {"api": err_entry, "failure": err_failure,
                          "status_exit": err_status["exit_code"],
                          "note": "受控 InitialJudgmentError 为宿主映射注入，"
                                  "不冒称真实核心业务失败。"},
        "note": "C03 零条可保存暂不能判断且不自动判无问题；早期/HOLD/绑定/身份/事件复用均在"
                "建目录前或核心处拒绝。"})
    return problems


def group_persistence_faults() -> list:
    problems: list = []
    detail = []
    for mode in ("partial", "throw"):
        label = f"g3_{mode}"
        batch = chain_to_fact_packet(label, "C06b.xlsx")
        submission = submission_for(batch, f"EV-SIM-T17-{mode.upper()}-1",
                                    "【模拟测试】暂不能判断", "【模拟测试】需要补充证据")
        real_writer = HOST._write_exclusive_json
        state = {"hits": 0, "mode": None, "newline": None, "text_bytes": None, "target": None,
                 "buffer_sha256": None}
        real_open = open

        target = batch / "workflow/checkpoints/0008.json"
        state["target"] = target.resolve()

        class _ObservedHandle:
            def __init__(self, handle):
                self._handle = handle

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self._handle.close()
                return False

            def write(self, text_str):
                state["hits"] += 1
                encoded = text_str.encode("utf-8")
                state["text_bytes"] = encoded
                state["buffer_sha256"] = hashlib.sha256(encoded).hexdigest()
                boundary = max(1, len(encoded) // 2)
                self._handle.write(encoded[:boundary].decode("utf-8", errors="ignore"))
                if mode == "partial":
                    raise OSError("【测试注入】真实独占写句柄上单次 write 半写后失败")
                self._handle.write(encoded[boundary:].decode("utf-8", errors="ignore"))
                raise RuntimeError("【测试注入】0008 完整写入后抛 sentinel")

            def __getattr__(self, name):
                return getattr(self._handle, name)

        def observed_open(file, open_mode="r", *args, **kwargs):
            handle = real_open(file, open_mode, *args, **kwargs)
            try:
                resolved = Path(getattr(handle, "name", file)).resolve()
            except (OSError, TypeError):
                return handle
            if resolved != state["target"] or "b" in str(open_mode):
                return handle
            state["mode"] = open_mode
            state["newline"] = kwargs.get("newline")
            return _ObservedHandle(handle)

        def asserting_writer(path, payload, stage):
            if Path(path).resolve() == state["target"]:
                HOST.__builtins__["open"] = observed_open
            try:
                return real_writer(path, payload, stage)
            finally:
                HOST.__builtins__["open"] = real_open

        HOST._write_exclusive_json = asserting_writer
        COUNTS["fault_injections"] += 1
        try:
            entry = record_api(f"{label}_record", HOST.record_simulated_initial_judgment, batch,
                               submission, expect_exception=HOST.WorkflowHostError)
        finally:
            HOST._write_exclusive_json = real_writer
            HOST.__builtins__["open"] = real_open
        failure, failure_ok = load_json_if_parseable(
            batch / "workflow/initial_judgment/failure.json")
        status = run_cli(f"{label}_status", ["status", "--batch-dir", str(batch)], 2)
        half_bytes = target.read_bytes() if target.is_file() else b""
        expected_partial = (state["text_bytes"] or b"")[: max(1, len(state["text_bytes"] or b"") // 2)]
        old_unchanged = True
        for revision in range(1, 8):
            if not (batch / f"workflow/checkpoints/{revision:04d}.json").is_file():
                problems.append(f"{label}: 000{revision} 缺失")
        if entry["outcome"] != "raised":
            problems.append(f"{label}: 未映射为 WorkflowHostError")
        if not failure_ok or failure.get("target_exit_code") != 2 \
                or failure.get("stage") != "initial_judgment":
            problems.append(f"{label}: 失败诊断退出码/阶段不符")
        if not failure_ok or not failure.get("exception_chain"):
            problems.append(f"{label}: 失败诊断缺少异常链")
        if status["exit_code"] != 2:
            problems.append(f"{label}: 新进程 status 退出码不是 2")
        if state["hits"] != 1:
            problems.append(f"{label}: 真实 writer 写命中不是 1 次：{state['hits']}")
        if state["mode"] != "x":
            problems.append(f"{label}: 0008 未以独占模式写入：{state['mode']!r}")
        if state["newline"] != "\n":
            problems.append(f"{label}: 0008 未使用明确 LF：{state['newline']!r}")
        if mode == "partial":
            if half_bytes != expected_partial:
                problems.append(f"{label}: 半写字节与预期不符（{len(half_bytes)}）")
            COUNTS["voucher_0008_half_written_total"] += 1
        else:
            if not target.is_file():
                problems.append(f"{label}: 完整写入后 sentinel 未留下 0008 文件")
            COUNTS["voucher_0008_physical_total"] += 1
        COUNTS["recorded_failure_scenes"] += 1
        detail.append({"mode": mode, "api": entry, "failure": failure,
                       "status_exit": status["exit_code"], "write_hits": state["hits"],
                       "open_mode": state["mode"], "newline": state["newline"],
                       "half_written_bytes": len(half_bytes),
                       "expected_partial_bytes": len(expected_partial),
                       "buffer_sha256": state["buffer_sha256"],
                       "old_checkpoints_present": old_unchanged})
    save_json(CONTAINER / "probe_records" / "g3_persistence_faults.json", {
        "case": "g3_persistence_faults", "detail": detail,
        "note": "半写以真实独占写句柄上的单次 write 注入，不替换整只 writer；"
                "完整写入后 sentinel 不能被恢复当成功。"})
    return problems


def group_late_change() -> list:
    problems: list = []
    # 4a：写后最后一次控制器检查之后改 fact_packet.json
    batch = chain_to_fact_packet("g4_late_fact", "C06b.xlsx")
    submission = submission_for(batch, "EV-SIM-T17-LATE-1", "【模拟测试】暂不能判断",
                               "【模拟测试】需要补充证据")
    target = batch / "workflow/fact_packet/fact_packet.json"
    backup = target.read_bytes()
    real_action = HOST.CONTROLLER_MODULE.check_dev_action
    state = {"direct_calls": 0, "injected": False, "before": None, "after": None}

    def wrapped_action(workflow, action, *, current_bindings=None, _real=real_action, _state=state):
        result = _real(workflow, action, current_bindings=current_bindings)
        import sys as _sys
        frame = _sys._getframe(1)
        direct = (frame.f_code.co_name == "record_simulated_initial_judgment"
                  and action == HOST.CONTROLLER_MODULE.ACTION_SCREEN)
        if direct:
            _state["direct_calls"] += 1
        if direct and _state["direct_calls"] == 2 and not _state["injected"]:
            _state["before"] = sha256(target)
            with open(target, "ab") as handle:
                handle.write(b"\n")
            _state["after"] = sha256(target)
            _state["injected"] = True
        return result

    HOST.CONTROLLER_MODULE.check_dev_action = wrapped_action
    COUNTS["fault_injections"] += 1
    try:
        entry = record_api("g4_late_fact_record", HOST.record_simulated_initial_judgment, batch,
                           submission, expect_exception=HOST.WorkflowHostBlocked)
    finally:
        HOST.CONTROLLER_MODULE.check_dev_action = real_action
    if entry["outcome"] != "raised":
        problems.append("写后晚变更未被本次公开保存拒绝")
    if state["direct_calls"] != 2 or not state["injected"]:
        problems.append(f"注入点不符：direct_calls={state['direct_calls']} injected={state['injected']}")
    if state["before"] == state["after"]:
        problems.append("注入未真正改变目标文件")
    message = entry.get("message") or ""
    if "fact_packet.json" not in message:
        problems.append("本次拒绝未指向目标文件 fact_packet.json")
    revoked = run_cli("g4_late_fact_revoked", ["status", "--batch-dir", str(batch)], 1)
    target.write_bytes(backup)
    restored = run_cli("g4_late_fact_restored", ["status", "--batch-dir", str(batch)], 1)
    if restored["exit_code"] != 1:
        problems.append("恢复原件后仍应因有效失败事实退出 1")
    COUNTS["recorded_failure_scenes"] += 1
    save_json(CONTAINER / "probe_records" / "g4_late_change_fact_packet.json", {
        "case": "g4_late_change_fact_packet", "api": entry,
        "direct_controller_calls": state["direct_calls"], "injected": state["injected"],
        "before_sha256": state["before"], "after_sha256": state["after"],
        "revoked_status_exit": revoked["exit_code"], "restored_status_exit": restored["exit_code"],
        "note": "在写后最后一次真实控制器动作检查返回之后，仅为已消费 fact_packet.json 追加 LF；"
                "本次公开保存即拒绝，撤销 wrapper 后 status 1，恢复原件后仍因有效失败事实退出 1。"})

    # 4b：包装最后一次新记录摘要读取，改 initial_judgment.json
    batch2 = chain_to_fact_packet("g4_late_record", "C06b.xlsx")
    submission2 = submission_for(batch2, "EV-SIM-T17-LATE-2", "【模拟测试】暂不能判断",
                                "【模拟测试】需要补充证据")
    record_entry = record_api("g4_late_record_save", HOST.record_simulated_initial_judgment, batch2,
                              submission2, expect_exception=HOST.WorkflowHostBlocked)
    if record_entry["outcome"] != "returned":
        problems.append("4b 前置保存未成功")
        return problems
    record_path = batch2 / "workflow/initial_judgment/initial_judgment.json"
    backup2 = record_path.read_bytes()
    real_read = HOST._read_initial_judgment_outputs
    state2 = {"calls": 0, "injected": False, "before": None, "after": None}

    def wrapping_read(batch_dir, stage, _real=real_read, _state=state2, _target=record_path):
        result = _real(batch_dir, stage)
        _state["calls"] += 1
        if not _state["injected"] and Path(batch_dir).resolve() == batch2.resolve():
            _state["before"] = sha256(_target)
            with open(_target, "ab") as handle:
                handle.write(b"\n")
            _state["after"] = sha256(_target)
            _state["injected"] = True
        return result

    HOST._read_initial_judgment_outputs = wrapping_read
    try:
        status_entry = record_api("g4_late_record_status", HOST.inspect_dev_batch, batch2,
                                  expect_exception=HOST.WorkflowHostBlocked)
    finally:
        HOST._read_initial_judgment_outputs = real_read
    if status_entry["outcome"] != "raised":
        problems.append("4b 本次 status 未拒绝被改的 initial_judgment.json")
    if not state2["injected"]:
        problems.append("4b 注入未命中 status 的摘要读取")
    failure_path = batch2 / "workflow/initial_judgment/failure.json"
    if failure_path.exists():
        problems.append("4b 只读 status 不得写入新诊断")
    record_path.write_bytes(backup2)
    restored2 = run_cli("g4_late_record_restored", ["status", "--batch-dir", str(batch2)], 0)
    if restored2["exit_code"] != 0:
        problems.append("4b 撤销探针并恢复原件后 status 应成功")
    save_json(CONTAINER / "probe_records" / "g4_late_change_record.json", {
        "case": "g4_late_change_record", "save_api": record_entry, "status_api": status_entry,
        "summary_read_calls": state2["calls"], "injected": state2["injected"],
        "before_sha256": state2["before"], "after_sha256": state2["after"],
        "failure_written": failure_path.exists(),
        "restored_status_exit": restored2["exit_code"],
        "note": "包装最后一次新记录摘要读取，先返回原对象后单次更改 initial_judgment.json；"
                "本次 status 即拒绝且不写诊断，撤销探针并只恢复原件后 status 0。"})
    return problems


def group_binding_and_protocol() -> list:
    problems: list = []
    batch = chain_to_fact_packet("g5_binding", "C06b.xlsx")
    submission = submission_for(batch, "EV-SIM-T17-BIND5-1", "【模拟测试】暂不能判断",
                               "【模拟测试】需要补充证据")
    entry = record_api("g5_save", HOST.record_simulated_initial_judgment, batch, submission,
                       expect_exception=HOST.WorkflowHostBlocked)
    if entry["outcome"] != "returned":
        problems.append("g5 前置保存未成功")
        return problems
    manifest = json.loads((batch / "workflow/host_manifest.json").read_text(encoding="utf-8"))
    state = json.loads((batch / "workflow/checkpoints/0008.json")
                       .read_text(encoding="utf-8"))["workflow"]["state"]
    core_sha = manifest["bindings"]["host_code_sha256"]["initial_judgment_core"]
    if core_sha != FROZEN_HASHES["scripts/build_demo_initial_judgment.py"]:
        problems.append("批次未绑定冻结初判核心的实测哈希")
    before_bindings = HOST._measure_bindings(batch)
    after_bindings = HOST._measure_bindings(batch)
    if not same_json(before_bindings, after_bindings):
        problems.append("操作前后静态绑定实测不一致")
    record_path = batch / "workflow/initial_judgment/initial_judgment.json"
    backup = record_path.read_bytes()
    payload = json.loads(backup.decode("utf-8"))
    tampered = copy.deepcopy(payload)
    tampered["record"]["source"]["fact_packet_sha256"] = "0" * 64
    record_path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2), encoding="utf-8")
    status_entry = record_api("g5_tampered_source", HOST.inspect_dev_batch, batch,
                              expect_exception=HOST.WorkflowHostBlocked)
    if status_entry["outcome"] != "raised":
        problems.append("篡改 record.source 指纹后 status 未拒绝")
    record_path.write_bytes(backup)
    if (batch / "workflow/initial_judgment/failure.json").exists():
        problems.append("只读 status 篡改反例不得写诊断")
    artifacts_path = batch / "workflow/initial_judgment/artifacts.json"
    backup_artifacts = artifacts_path.read_bytes()
    artifacts = json.loads(backup_artifacts.decode("utf-8"))
    tampered_artifacts = copy.deepcopy(artifacts)
    tampered_artifacts["initial_judgment_status"] = "HUMAN_INITIAL_JUDGMENT_SAVED"
    artifacts_path.write_text(json.dumps(tampered_artifacts, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    status_entry2 = record_api("g5_tampered_artifacts", HOST.inspect_dev_batch, batch,
                               expect_exception=HOST.WorkflowHostBlocked)
    if status_entry2["outcome"] != "raised":
        problems.append("篡改 artifacts 状态字段后 status 未拒绝")
    artifacts_path.write_bytes(backup_artifacts)
    restored = run_cli("g5_restored", ["status", "--batch-dir", str(batch)], 0)
    if restored["exit_code"] != 0:
        problems.append("恢复原件后 status 未成功")
    if state["gate1_approval"] is not None:
        problems.append("真实批准被伪造")
    save_json(CONTAINER / "probe_records" / "g5_binding_and_protocol.json", {
        "case": "g5_binding_and_protocol", "core_sha256_binding": core_sha,
        "bindings_stable": same_json(before_bindings, after_bindings),
        "tampered_source_api": status_entry, "tampered_artifacts_api": status_entry2,
        "restored_status_exit": restored["exit_code"],
        "note": "本轮新批次的声明副本用于有限篡改；只撤销探针注入，不改真实核心/上游文件、"
                "不删有效失败事实。"})
    return problems


def group_readonly_status() -> list:
    problems: list = []
    batch = BATCH_ROOT / CONTAINER.name / "g6_readonly"
    if not (batch / "workflow/checkpoints/0008.json").is_file():
        batch = chain_to_fact_packet("g6_readonly", "C06b.xlsx")
        submission = submission_for(batch, "EV-SIM-T17-READONLY-1", "【模拟测试】暂不能判断",
                                   "【模拟测试】需要补充证据")
        entry = record_api("g6_save", HOST.record_simulated_initial_judgment, batch, submission,
                           expect_exception=HOST.WorkflowHostBlocked)
        if entry["outcome"] != "returned":
            problems.append("g6 前置保存未成功")
            return problems
    guards = {}
    hits = {name: 0 for name in DOWNSTREAM_GUARDS}
    modules = {
        "normalize_workbook": HOST.NORMALIZER_MODULE,
        "load_normalized_to_sqlite": HOST.STORE_MODULE,
        "screen_sqlite": HOST.SCREEN_MODULE,
        "verify_rule_facts": HOST.CROSSCHECK_MODULE,
        "build_fact_packet": HOST.FACT_PACKET_MODULE,
        "build_initial_judgment_record": HOST.INITIAL_JUDGMENT_MODULE,
    }
    for name, module in modules.items():
        guards[name] = (module, name, getattr(module, name))

        def forbidden(*args, _name=name, **kwargs):
            hits[_name] += 1
            raise AssertionError(f"status 不得调用下游核心 {_name}")

        setattr(module, name, forbidden)
    before_tree = tree_hashes(batch)
    db_hashes_before = {p.name: sha256(p) for p in
                        (SQLITE_ROOT / CONTAINER.name).rglob("*.sqlite3")}
    try:
        status_entry = record_api("g6_status", HOST.inspect_dev_batch, batch,
                                  expect_exception=HOST.WorkflowHostBlocked)
    finally:
        for name, (module, attr, original) in guards.items():
            setattr(module, attr, original)
    after_tree = tree_hashes(batch)
    db_hashes_after = {p.name: sha256(p) for p in (SQLITE_ROOT / CONTAINER.name).rglob("*.sqlite3")}
    if status_entry["outcome"] != "returned":
        problems.append(f"守卫下 status 未成功：{status_entry.get('message')}")
    if any(value != 0 for value in hits.values()):
        problems.append(f"守卫下 status 触达下游核心：{hits}")
    if before_tree != after_tree:
        problems.append("守卫下 status 改变了批次文件哈希集合")
    if db_hashes_before != db_hashes_after:
        problems.append("守卫下 status 改变了外置数据库字节")
    cli_status = run_cli("g6_cli_status", ["status", "--batch-dir", str(batch)], 0)
    if cli_status["payload"].get("initial_judgment_status") != \
            "SIMULATED_INITIAL_JUDGMENT_RECORDED":
        problems.append("新进程 CLI status 未恢复模拟初判状态")
    save_json(CONTAINER / "probe_records" / "g6_readonly_status.json", {
        "case": "g6_readonly_status", "guard_hits": hits, "api_record": status_entry,
        "tree_unchanged": before_tree == after_tree,
        "database_unchanged": db_hashes_before == db_hashes_after,
        "cli_status_exit": cli_status["exit_code"],
        "core_calls_observed": COUNTS["core_calls_observed"],
        "note": "六个真实下游函数被替换为计数后抛错守卫；status 成功且命中全 0，"
                "不调用新的初判纯核心。"})
    return problems


def audit_ledger(ledger: dict, *, container=None, registry_calls=None) -> list:
    problems: list = []
    for entry in ledger["file_ledger"]:
        target = (container or CONTAINER) / entry["path"] if container is not None \
            else artifact(entry["path"])
        if not target.is_file():
            problems.append(f"记录文件缺失：{entry['path']}")
        elif entry.get("sha256") is not None and sha256(target) != entry["sha256"]:
            problems.append(f"记录文件哈希不符：{entry['path']}")
    record_names = {f"{item['kind']}:{item['label']}" for item in
                    ledger["cli_records"] + ledger["api_records"]}
    ledger_names = {entry["record"] for entry in ledger["file_ledger"]}
    registry_names = {item["record"] for item in (
        registry_calls if registry_calls is not None else ledger["registry_calls"])}
    for name in sorted(record_names - ledger_names):
        problems.append(f"调用记录未登记进文件台账：{name}")
    for name in sorted(record_names - registry_names):
        problems.append(f"调用未登记进权威登记表：{name}")
    for name in sorted(registry_names - record_names):
        problems.append(f"登记表存在无对应记录的条目：{name}")
    return problems


def group_evidence_and_protection() -> list:
    problems: list = []
    ledger_entries = []
    for item in CLI_RECORDS:
        for key in ("stdout_path", "stderr_path"):
            target = artifact(item[key])
            ledger_entries.append({"record": f"cli:{item['label']}", "field": key,
                                   "path": item[key], "exists": target.is_file(),
                                   "sha256": sha256(target) if target.is_file() else None})
    for item in API_RECORDS:
        for key in ("return_path", "exception_path"):
            if not item.get(key):
                continue
            target = artifact(item[key])
            ledger_entries.append({"record": f"api:{item['label']}", "field": key,
                                   "path": item[key], "exists": target.is_file(),
                                   "sha256": sha256(target) if target.is_file() else None})
    registry_path = save_json(CONTAINER / "call_registry.json",
                              {"calls": CALL_REGISTRY, "cli": len(CLI_RECORDS),
                               "api": len(API_RECORDS)})
    ledger = {"cli_records": CLI_RECORDS, "api_records": API_RECORDS,
              "file_ledger": ledger_entries, "registry_calls": CALL_REGISTRY,
              "call_registry_path": rel(registry_path), "counts": COUNTS}
    ledger_path = save_json(CONTAINER / "evidence_ledger.json", ledger)
    ledger_problems = audit_ledger(ledger)
    COUNTS["missing_records"] = len(ledger_problems)
    COUNTS["unregistered_records"] = 0
    problems.extend(ledger_problems[:8])
    # 隔离自测：只删审核副本一条权威登记
    removed = list(ledger["registry_calls"][:1])
    trimmed = list(ledger["registry_calls"][1:])
    isolation_problems = audit_ledger(ledger, registry_calls=trimmed)
    if not isolation_problems:
        problems.append("隔离自测未失败：只删一条登记后审计仍通过")
    COUNTS["isolation_self_test"] = "failed_as_expected" if isolation_problems else "not_detected"
    save_json(CONTAINER / "isolation" / "isolation_result.json", {
        "method": "只从审核副本删除一条权威登记（registry），file_ledger 与真实文件不动",
        "removed_registry_entry": removed,
        "audit_problems_on_trimmed": isolation_problems,
        "audit_problems_on_original": ledger_problems,
        "note": "真实台账、登记表与文件未改；未因此再建业务链。"})
    # 现场计数（scope：本容器）
    batch_parent = BATCH_ROOT / CONTAINER.name
    physical = sorted(p.parent.parent.parent.name for p in
                      batch_parent.rglob("workflow/checkpoints/0008.json"))
    parseable = [name for name in physical
                 if load_json_if_parseable(batch_parent / name
                                           / "workflow/checkpoints/0008.json")[1]]
    half = [name for name in physical
            if (batch_parent / name / "workflow/initial_judgment/failure.json").is_file()
            and not load_json_if_parseable(batch_parent / name
                                           / "workflow/checkpoints/0008.json")[1]]
    COUNTS["voucher_0008_physical_total"] = len(physical)
    COUNTS["voucher_0008_parseable_total"] = len(parseable)
    COUNTS["voucher_0008_half_written_total"] = len(half)
    if COUNTS["voucher_0008_half_written_total"] != 1:
        problems.append("半写 0008 现场数不是 1")
    # receiver/checker（本容器现场）
    receiver = 0
    checker = 0
    checker_problems = []
    for batch_dir in sorted(item for item in batch_parent.iterdir() if item.is_dir()):
        host_manifest, ok = load_json_if_parseable(batch_dir / "workflow/host_manifest.json")
        invocation, inv_ok = load_json_if_parseable(batch_dir / "workflow/receive_invocation.json")
        if ok and inv_ok:
            receiver += 1
            if host_manifest.get("receive", {}).get("exit_code") != invocation.get("exit_code"):
                checker_problems.append(f"{batch_dir.name}: receiver 退出码不一致")
        manifest, man_ok = load_json_if_parseable(batch_dir / "batch_manifest.json")
        if man_ok and isinstance(manifest.get("checker_invocation"), dict):
            invocation = manifest["checker_invocation"]
            if invocation.get("started") is True and invocation.get("exit_code") == 0:
                checker += 1
            for key in ("report", "stdout_log", "stderr_log"):
                reference = invocation.get(key) or {}
                path = batch_dir / str(reference.get("path") or "")
                if not (path.is_file() and sha256(path) == reference.get("sha256")):
                    checker_problems.append(f"{batch_dir.name}: checker {key} 引用未验证")
    if checker_problems:
        problems.extend(checker_problems[:5])
    COUNTS["receiver_starts_recorded"] = receiver
    COUNTS["checker_started_by_receiver"] = checker
    COUNTS["direct_checker_cli_calls"] = 0
    COUNTS["scenes_total"] = len(physical)
    save_json(CONTAINER / "scene_outcomes.json", {
        "scope": "本容器现场", "batches": [item.name for item in batch_parent.iterdir()
                                          if item.is_dir()],
        "physical_0008": physical, "parseable_0008": parseable,
        "half_written_0008": half, "derived": {
            "scenes_total": COUNTS["scenes_total"],
            "voucher_0008_physical_total": COUNTS["voucher_0008_physical_total"],
            "voucher_0008_parseable_total": COUNTS["voucher_0008_parseable_total"],
            "voucher_0008_half_written_total": COUNTS["voucher_0008_half_written_total"],
            "recorded_failure_scenes": COUNTS["recorded_failure_scenes"],
            "recovered_success_total": COUNTS["recovered_success_total"],
            "receiver_starts_recorded": receiver,
            "checker_started_by_receiver": checker,
            "direct_checker_cli_calls": 0,
        },
        "note": "计数按 scope 分列物理/可解析 0008、有效失败与无失败恢复成功；"
                "有文件不等于成功；未观察的子进程内部核心次数为 null。"})
    # 保护比较
    protection_problems: list = []
    protection = {"executed": False}
    if not BASELINE.is_file():
        protection_problems.append(f"保护基线缺失：{BASELINE}")
    else:
        baseline_sha = sha256(BASELINE)
        if baseline_sha != BASELINE_SHA256:
            protection_problems.append(f"保护基线文件哈希不符：{baseline_sha}")
        baseline_raw = json.loads(BASELINE.read_text(encoding="utf-8"))
        if len(baseline_raw) != BASELINE_ENTRIES:
            protection_problems.append(f"保护基线条目数不符：{len(baseline_raw)}"
                                       f"（登记 {BASELINE_ENTRIES}）")
        baseline_map = {name.replace(chr(92), "/"): digest for name, digest in baseline_raw.items()}
        scan = {}
        read_errors = 0
        for candidate in PROJECT_ROOT.rglob("*"):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(PROJECT_ROOT).as_posix()
            if relative.split("/")[0] in SKIP_DIRS:
                continue
            try:
                scan[relative] = sha256(candidate)
            except OSError:
                read_errors += 1
        changed = sorted(name for name, digest in baseline_map.items()
                         if name in scan and scan[name] != digest)
        missing = sorted(name for name in baseline_map if name not in scan)
        unexpected = [name for name in changed if name not in ALLOWED_CHANGES]
        if unexpected:
            protection_problems.append(f"相对基线出现预期外变化：{unexpected[:5]}")
        if missing:
            protection_problems.append(f"相对基线缺失 {len(missing)} 项：{missing[:5]}")
        if read_errors:
            protection_problems.append(f"保护扫描读取错误 {read_errors} 个文件")
        frozen_mismatch = []
        for relative, want in FROZEN_HASHES.items():
            target = PROJECT_ROOT / relative
            got = sha256(target) if target.is_file() else None
            if got != want:
                frozen_mismatch.append(f"{relative}={got}")
        if frozen_mismatch:
            protection_problems.append(f"冻结哈希不符：{frozen_mismatch}")
        protection = {"executed": True, "baseline": rel(BASELINE), "baseline_sha256": baseline_sha,
                      "baseline_entries": len(baseline_raw), "scanned_entries": len(scan),
                      "changed": changed, "unexpected_changes": unexpected, "missing": missing,
                      "read_errors": read_errors, "frozen_mismatch": frozen_mismatch,
                      "allowed_changes": sorted(ALLOWED_CHANGES)}
        COUNTS["protection_executed"] = True
    save_json(CONTAINER / "probe_records" / "g7_protection.json", {
        "case": "g7_protection", "protection": protection,
        "protection_problems": protection_problems,
        "missing_records": COUNTS["missing_records"],
        "unregistered_records": COUNTS["unregistered_records"],
        "note": "保护比较真实执行并进入正式 failures；未执行的动作不填假 0。"})
    problems.extend(protection_problems[:5])
    # 停止点
    stop_problems = []
    no_0009 = True
    for batch_dir in sorted(item for item in batch_parent.iterdir() if item.is_dir()):
        names = sorted(p.name for p in (batch_dir / "workflow/checkpoints").iterdir()) \
            if (batch_dir / "workflow/checkpoints").is_dir() else []
        if "0009.json" in names:
            no_0009 = False
        for item in names:
            if item not in HOST.LEGAL_CHECKPOINT_NAMES:
                stop_problems.append(f"{batch_dir.name}: 非法 checkpoint {item}")
    for name in parseable:
        checkpoint8, _ = load_json_if_parseable(batch_parent / name
                                                / "workflow/checkpoints/0008.json")
        state = checkpoint8["workflow"]["state"]
        if state["phase"] != HOST.CONTROLLER_MODULE.PHASE_G2_APPROVED:
            stop_problems.append(f"{name}: phase 不是 DEV_GATE2_APPROVED")
        if state["gate1_approval"] is not None or state["gate2_approval"] is not None:
            stop_problems.append(f"{name}: 真实批准不是 null")
        if state["next_step_allowed"] is not False:
            stop_problems.append(f"{name}: next_step_allowed 不是 false")
        operation = checkpoint8["operation"]
        if operation["kind"] != "RECORD_SIMULATED_INITIAL_JUDGMENT":
            stop_problems.append(f"{name}: operation.kind 不符")
        if operation["initial_judgment_status"] != "SIMULATED_INITIAL_JUDGMENT_RECORDED":
            stop_problems.append(f"{name}: 状态字符串不符")
        for key in ("human_initial_judgment", "ai_suggestion", "final_judgment",
                    "gate1_approval", "gate2_approval"):
            if operation["artifacts"][key] is not None:
                stop_problems.append(f"{name}: artifacts.{key} 不是 null")
        if operation["artifacts"]["ai_action_simulation_allowed"] is not False:
            stop_problems.append(f"{name}: AI 真实许可不是 false")
    if not no_0009:
        stop_problems.append("出现了 0009")
    problems.extend(stop_problems[:5])
    save_json(CONTAINER / "probe_records" / "g7_stop_point.json", {
        "case": "g7_stop_point", "problems": stop_problems, "no_0009": no_0009})
    return problems


# ---------------------------------------------------------------------------
# TASK-017-R1 定点模式
# ---------------------------------------------------------------------------


NEW_LAYER_TARGETS = (("started.json", "started_file_sha256"),
                     ("submission.json", "submission_file_sha256"),
                     ("initial_judgment.json", "record_file_sha256"),
                     ("artifacts.json", "artifacts_file_sha256"))


def group_r1_targeted() -> list:
    """仅用一个新 C06b 批次完整建链至 0008，复用它做只读恢复与观察探针。"""
    problems: list = []
    batch = chain_to_fact_packet("r1_c06b", "C06b.xlsx")
    layer = batch / "workflow/initial_judgment"
    submission = submission_for(batch, "EV-SIM-T17R1-0001", "【模拟测试】暂不能判断",
                               "【模拟测试】需要补充证据后再判断。",
                               extra={"needed_evidence": ["【模拟测试】银行流水原件"]})
    submission_path = write_submission("r1", submission)

    # --- 1) 正常保存：真实核心 1 次、真实入参三时点、完整返回与落盘严格等值
    core_mark = CORE_OBSERVER.mark()
    save_entry = record_api("r1_save", HOST.record_simulated_initial_judgment, batch,
                            submission, expect_exception=HOST.WorkflowHostBlocked)
    observed = CORE_OBSERVER.window(core_mark)
    saved_calls = save_core_observations("r1_save")
    if save_entry["outcome"] != "returned":
        problems.append(f"r1 正常保存未成功：{save_entry.get('message')}")
        return problems
    if len(observed) != 1 or save_entry["core_calls_delta"] != 1:
        problems.append(f"真实纯核心调用不是 1 次：observed={len(observed)} "
                        f"delta={save_entry['core_calls_delta']}")
    if save_entry["host_api_delta"] != 1:
        problems.append("宿主 API 计数不是 1")
    call = observed[0]
    after_public = {"packet": canonical_sha256(call["packet_ref"]),
                    "submission": canonical_sha256(call["submission_ref"])}
    if not (call["before"] == call["after_core"] == after_public):
        problems.append(f"真实入参三时点指纹不一致：{call['before']} / {call['after_core']} / "
                        f"{after_public}")
    disk_payload, disk_ok = load_json_if_parseable(layer / "initial_judgment.json")
    if not disk_ok:
        problems.append("落盘 initial_judgment.json 不可解析")
    elif not same_json(disk_payload, call.get("complete_return")):
        problems.append("落盘 initial_judgment.json 与完整真实核心返回不严格相等")
    if not same_json(load_json_if_parseable(layer / "submission.json")[0], submission):
        problems.append("submission.json 快照与提交对象不严格相等")
    checkpoint8, ok8 = load_json_if_parseable(batch / "workflow/checkpoints/0008.json")
    checkpoint7, _ = load_json_if_parseable(batch / "workflow/checkpoints/0007.json")
    if not ok8:
        problems.append("0008 不可解析")
    else:
        if not same_json(checkpoint8["workflow"], checkpoint7["workflow"]):
            problems.append("0008 workflow 与 0007 不严格相等")
        if checkpoint8["previous_file_sha256"] != sha256(
                batch / "workflow/checkpoints/0007.json"):
            problems.append("0008 previous 与 0007 实读不符")
        state = checkpoint8["workflow"]["state"]
        if state["gate1_approval"] is not None or state["gate2_approval"] is not None:
            problems.append("真实批准不是 null")
        if state["next_step_allowed"] is not False:
            problems.append("next_step_allowed 不是 false")
        if checkpoint8["operation"]["artifacts"]["ai_action_simulation_allowed"] is not False:
            problems.append("AI 动作真实许可不是 false")
    host_manifest = json.loads((batch / "workflow/host_manifest.json").read_text(encoding="utf-8"))
    if host_manifest["bindings"]["host_code_sha256"]["initial_judgment_core"] != \
            FROZEN_HASHES["scripts/build_demo_initial_judgment.py"]:
        problems.append("start 绑定的初判核心哈希与冻结件不一致")
    bindings_before = HOST._measure_bindings(batch)
    bindings_after = HOST._measure_bindings(batch)
    if not same_json(bindings_before, bindings_after):
        problems.append("静态绑定实测前后不一致")
    # 重复提交：真实核心增量 0、旧文件不变
    tree_before = tree_hashes(batch / "workflow")
    repeat_mark = CORE_OBSERVER.mark()
    repeat_entry = record_api("r1_repeat", HOST.record_simulated_initial_judgment, batch,
                              submission, expect_exception=HOST.WorkflowHostBlocked)
    repeat_calls = CORE_OBSERVER.window(repeat_mark)
    tree_after = tree_hashes(batch / "workflow")
    if repeat_entry["outcome"] != "raised":
        problems.append("重复提交未被拒绝")
    if repeat_calls or repeat_entry["core_calls_delta"] != 0:
        problems.append(f"重复提交触达真实核心：{len(repeat_calls)}")
    if tree_before != tree_after:
        problems.append("重复提交改变了旧文件")

    # --- 2) 无注入观察真实读取位置
    read_sites = {"calls": []}
    real_read = HOST._read_initial_judgment_outputs

    def recording_read(batch_dir, stage, _real=real_read, _sites=read_sites):
        result = _real(batch_dir, stage)
        _sites["calls"].append({"seq": len(_sites["calls"]) + 1, "stage": stage,
                                "record_file_sha256": result["record_file_sha256"]})
        return result

    HOST._read_initial_judgment_outputs = recording_read
    try:
        baseline_status = record_api("r1_status_baseline", HOST.inspect_dev_batch, batch,
                                     expect_exception=HOST.WorkflowHostBlocked)
    finally:
        HOST._read_initial_judgment_outputs = real_read
    if baseline_status["outcome"] != "returned":
        problems.append("无注入 status 未成功")
    if baseline_status["core_calls_delta"] != 0:
        problems.append("只读 status 触达了真实纯核心")
    last_index = len(read_sites["calls"])
    save_json(CONTAINER / "probe_records" / "r1_status_read_sites.json",
              {"case": "r1_status_read_sites", "calls": read_sites["calls"],
               "last_index": last_index,
               "note": "无注入观察：定位该次 status 最后一次新层输出读取的真实位置。"})

    # --- 3) 四文件 LF 反例：只在最后一次新层输出读取返回原对象之后注入
    probe_detail = []
    real_read_for_probe = HOST._read_initial_judgment_outputs
    for filename, expected_key in NEW_LAYER_TARGETS:
        target_file = layer / filename
        backup = target_file.read_bytes()
        state = {"calls": 0, "injected": False, "before": None, "after": None,
                 "target_open": 0, "target_mode": None, "target_newline": None}

        def wrapping_read(batch_dir, stage, _real=real_read_for_probe, _state=state,
                          _file=target_file, _last=last_index):
            result = _real(batch_dir, stage)
            _state["calls"] += 1
            if _state["calls"] == _last and not _state["injected"]:
                _state["before"] = sha256(_file)
                with open(_file, "ab") as handle:
                    handle.write(b"\n")
                _state["after"] = sha256(_file)
                _state["injected"] = True
            return result

        HOST._read_initial_judgment_outputs = wrapping_read
        try:
            entry = record_api(f"r1_late_{filename}", HOST.inspect_dev_batch, batch,
                               expect_exception=HOST.WorkflowHostBlocked)
        finally:
            HOST._read_initial_judgment_outputs = real_read_for_probe
        message = entry.get("message") or ""
        if entry["outcome"] != "raised":
            problems.append(f"{filename}: 最后一次读取后改动未被本次 status 拒绝")
        if not state["injected"] or state["calls"] != last_index:
            problems.append(f"{filename}: 注入位置不符（calls={state['calls']} "
                            f"last={last_index}）")
        if filename not in message:
            problems.append(f"{filename}: 拒绝消息未指出目标文件")
        if (layer / "failure.json").exists():
            problems.append(f"{filename}: 只读 status 写入了失败诊断")
        revoked = run_cli(f"r1_late_{filename}_revoked", ["status", "--batch-dir", str(batch)], 1)
        target_file.write_bytes(backup)
        restored = run_cli(f"r1_late_{filename}_restored", ["status", "--batch-dir", str(batch)], 0)
        if revoked["exit_code"] != 1:
            problems.append(f"{filename}: 撤销 wrapper 保留变更后 status 未退出 1")
        if restored["exit_code"] != 0:
            problems.append(f"{filename}: 恢复原件后 status 未退出 0")
        probe_detail.append({"target": filename, "expected_field_key": expected_key,
                             "before_sha256": state["before"], "after_sha256": state["after"],
                             "read_calls": state["calls"], "last_index": last_index,
                             "api": entry, "message": message,
                             "revoked_status_exit": revoked["exit_code"],
                             "restored_status_exit": restored["exit_code"],
                             "failure_written": False})
    # 四场景全部恢复后：旧 0001—0008 与非故意注入文件不变
    for revision in range(1, 9):
        path = batch / f"workflow/checkpoints/{revision:04d}.json"
        if not path.is_file():
            problems.append(f"000{revision} 缺失")
    save_json(CONTAINER / "probe_records" / "r1_late_new_layer_files.json", {
        "case": "r1_late_new_layer_files", "detail": probe_detail,
        "note": "每次均在该次 status 最后一次新层输出读取返回原对象之后仅改目标文件；"
                "定位来自无注入真实调用位置，不硬编码全局第 N 次。"})

    # --- 4) 六下游守卫：status 成功、命中 0、真实核心增量 0
    guards = {}
    hits = {name: 0 for name in DOWNSTREAM_GUARDS}
    modules = {
        "normalize_workbook": HOST.NORMALIZER_MODULE,
        "load_normalized_to_sqlite": HOST.STORE_MODULE,
        "screen_sqlite": HOST.SCREEN_MODULE,
        "verify_rule_facts": HOST.CROSSCHECK_MODULE,
        "build_fact_packet": HOST.FACT_PACKET_MODULE,
        "build_initial_judgment_record": HOST.INITIAL_JUDGMENT_MODULE,
    }
    for name, module in modules.items():
        guards[name] = (module, name, getattr(module, name))

        def forbidden(*args, _name=name, **kwargs):
            hits[_name] += 1
            raise AssertionError(f"status 不得调用下游核心 {_name}")

        setattr(module, name, forbidden)
    tree_guard_before = tree_hashes(batch)
    db_before = {p.name: sha256(p) for p in (SQLITE_ROOT / CONTAINER.name).rglob("*.sqlite3")}
    try:
        guard_entry = record_api("r1_status_guard", HOST.inspect_dev_batch, batch,
                                 expect_exception=HOST.WorkflowHostBlocked)
    finally:
        for name, (module, attr, original) in guards.items():
            setattr(module, attr, original)
    tree_guard_after = tree_hashes(batch)
    db_after = {p.name: sha256(p) for p in (SQLITE_ROOT / CONTAINER.name).rglob("*.sqlite3")}
    if guard_entry["outcome"] != "returned":
        problems.append("守卫下 status 未成功")
    if any(value for value in hits.values()):
        problems.append(f"守卫下 status 触达下游核心：{hits}")
    if guard_entry["core_calls_delta"] != 0:
        problems.append("守卫下 status 的真实核心增量不是 0")
    if tree_guard_before != tree_guard_after:
        problems.append("守卫下 status 改变了批次文件")
    if db_before != db_after:
        problems.append("守卫下 status 改变了数据库字节")
    save_json(CONTAINER / "probe_records" / "r1_readonly_guard.json", {
        "case": "r1_readonly_guard", "guard_hits": hits, "api": guard_entry,
        "tree_unchanged": tree_guard_before == tree_guard_after,
        "database_unchanged": db_before == db_after,
        "note": "六个真实下游函数计数抛错守卫；该宿主 API 登记但真实初判核心增量为 0。"})

    # --- 5) 替身映射分列核对（纯映射函数，不建批次、不调用真实核心）
    core_calls_before_stub = CORE_OBSERVER.mark()
    stub_error = HOST.INITIAL_JUDGMENT_MODULE.InitialJudgmentError(
        "【测试替身】受控 InitialJudgmentError（仅核对宿主映射，不代表真实核心执行）")
    mapped = HOST._map_upstream_exception(stub_error, stage="initial_judgment")
    map_entry = {
        "label": "r1_stub_error_mapping", "kind": "api", "outcome": "mapped",
        "input_exception_class": type(stub_error).__name__,
        "mapped_exception_class": type(mapped).__name__,
        "mapped_stage": getattr(mapped, "stage", None),
        "host_api_delta": 0, "core_calls_delta": 0,
        "note": "替身映射按纯映射函数核对：不建批次、不调用真实核心，"
                "真实核心增量 0；完整 InitialJudgmentError→退出 2 的宿主路径已在"
                "TASK-017 原容器 task017_run_01 的 G2 实际执行，本轮不重复。",
    }
    if type(mapped).__name__ != "WorkflowHostError":
        problems.append(f"InitialJudgmentError 未映射为 WorkflowHostError："
                        f"{type(mapped).__name__}")
    if CORE_OBSERVER.mark() != core_calls_before_stub:
        problems.append("替身映射核对被计入真实核心次数")
    map_path = CONTAINER / "api_records" / "r1_stub_error_mapping.mapped.json"
    save_json(map_path, map_entry)
    map_entry["return_path"] = rel(map_path)
    map_entry["return_sha256"] = sha256(map_path)
    API_RECORDS.append(map_entry)
    CALL_REGISTRY.append({"record": "api:r1_stub_error_mapping", "kind": "api",
                          "detail": "mapped", "core_calls_delta": 0})
    save_json(CONTAINER / "probe_records" / "r1_stub_mapping.json", {
        "case": "r1_stub_mapping", "entry": map_entry})

    save_json(CONTAINER / "probe_records" / "r1_summary.json", {
        "case": "r1_summary", "batch_dir": str(batch), "batch_id": batch.name,
        "save_api": save_entry, "repeat_api": repeat_entry,
        "core_observation_saved_calls": saved_calls,
        "read_sites": read_sites, "late_probes": [item["target"] for item in probe_detail],
        "guard_api": guard_entry, "stub_mapping": map_entry,
        "note": "本定点仅用一个新 C06b 批次完整建链至 0008；未重跑完整七组、MAIN/零条建链、"
                "持久化场景或历史任务。"})
    return problems


def _finish(container: Path, failures: list) -> None:
    """保存最终 checks/summary 与全部计数（两种模式共用，不遗漏最后一项）。"""
    covered = sum(item.get("core_calls_delta") or 0 for item in API_RECORDS)
    if COUNTS.get("real_core_calls_observed", 0) != covered:
        failures.append(f"真实核心观察 {COUNTS.get('real_core_calls_observed', 0)} 次与各宿主 API "
                        f"记录的增量之和 {covered} 不一致")
    COUNTS["host_api_registered"] = len(API_RECORDS)
    COUNTS["covered_core_calls_by_api_delta"] = covered
    COUNTS["subprocess_internal_core_calls"] = None
    save_json(container / "checks.json", CHECKS)
    save_json(container / "counts.json", COUNTS)
    save_json(container / "cli_logs.json", CLI_RECORDS)
    save_json(container / "api_records.json", API_RECORDS)
    save_json(container / "core_observations.json", {
        "host_api_calls": len(API_RECORDS),
        "real_core_calls": COUNTS.get("real_core_calls_observed", 0),
        "covered_core_calls_by_api_delta": COUNTS.get("covered_core_calls_by_api_delta"),
        "per_api_call": {item["label"]: {"core_calls_delta": item.get("core_calls_delta"),
                                         "host_api_delta": item.get("host_api_delta"),
                                         "outcome": item["outcome"]}
                         for item in API_RECORDS},
        "note": "宿主公开 API 与真实纯核心次数分列，二者不要求相等；"
                "子进程内部核心次数未观察记 null。"})
    save_json(container / "summary.json", {"mode": "r1" if R1_MODE["value"] else "all",
                                           "checks": CHECKS, "failures": failures,
                                           "counts": COUNTS})
    passed = len([item for item in CHECKS if item["result"] == "PASS"])
    expected_exceptions = [item for item in API_RECORDS
                           if item["outcome"] in ("raised", "unexpected")]
    print(f"检查项 {len(CHECKS)}：{passed} PASS / {len(CHECKS) - passed} FAIL")
    print(f"CLI 调用 {COUNTS['cli_calls']}；宿主 API 登记 {len(API_RECORDS)}"
          f"（返回 {COUNTS['api_returned']}、预期/意外异常 {len(expected_exceptions)}"
          f"（预期协议阻断 {COUNTS['api_blocked']}、意外 {COUNTS['api_unexpected_errors']}））；"
          f"真实纯核心调用 {COUNTS.get('real_core_calls_observed', 0)}；子进程内部核心 null；"
          f"missing={COUNTS['missing_records']} unregistered={COUNTS['unregistered_records']}")
    print(f"0008 物理 {COUNTS['voucher_0008_physical_total']}／可解析 "
          f"{COUNTS['voucher_0008_parseable_total']}／半写 {COUNTS['voucher_0008_half_written_total']}；"
          f"有效失败 {COUNTS['recorded_failure_scenes']}；守卫命中 {COUNTS['guard_hits']}；"
          f"保护比较 executed={COUNTS['protection_executed']}")
    print(f"测试失败 {len(failures)}；汇总 {container / 'summary.json'}")


R1_MODE = {"value": False}


def group_r1_evidence_and_protection() -> list:
    """R1 定点证据与保护收尾（scope 限本定点）。"""
    problems: list = []
    ledger_entries = []
    for item in CLI_RECORDS:
        for key in ("stdout_path", "stderr_path"):
            target = artifact(item[key])
            ledger_entries.append({"record": f"cli:{item['label']}", "field": key,
                                   "path": item[key], "exists": target.is_file(),
                                   "sha256": sha256(target) if target.is_file() else None})
    for item in API_RECORDS:
        for key in ("return_path", "exception_path"):
            if not item.get(key):
                continue
            target = artifact(item[key])
            ledger_entries.append({"record": f"api:{item['label']}", "field": key,
                                   "path": item[key], "exists": target.is_file(),
                                   "sha256": sha256(target) if target.is_file() else None})
    # 完整异常链（预期异常必须带 traceback）
    for item in API_RECORDS:
        if item["outcome"] in ("raised", "unexpected"):
            if not item.get("traceback") or not item.get("exception_path"):
                problems.append(f"{item['label']}: 预期异常缺少完整 traceback/引用")
    registry_path = save_json(CONTAINER / "call_registry.json",
                              {"calls": CALL_REGISTRY, "cli": len(CLI_RECORDS),
                               "api": len(API_RECORDS)})
    ledger = {"cli_records": CLI_RECORDS, "api_records": API_RECORDS,
              "file_ledger": ledger_entries, "registry_calls": CALL_REGISTRY,
              "call_registry_path": rel(registry_path), "counts": COUNTS}
    ledger_path = save_json(CONTAINER / "evidence_ledger.json", ledger)
    ledger_problems = audit_ledger(ledger)
    COUNTS["missing_records"] = len(ledger_problems)
    COUNTS["unregistered_records"] = 0
    problems.extend(ledger_problems[:8])
    removed = list(ledger["registry_calls"][:1])
    isolation_problems = audit_ledger(ledger, registry_calls=list(ledger["registry_calls"][1:]))
    if not isolation_problems:
        problems.append("隔离自测未失败：只删一条登记后审计仍通过")
    COUNTS["isolation_self_test"] = ("failed_as_expected" if isolation_problems
                                     else "not_detected")
    save_json(CONTAINER / "isolation" / "isolation_result.json", {
        "method": "只从审核副本删除一条权威登记（registry），file_ledger 与真实文件不动",
        "removed_registry_entry": removed, "audit_problems_on_trimmed": isolation_problems,
        "audit_problems_on_original": ledger_problems})
    # 现场计数（scope：本定点容器）
    batch_parent = BATCH_ROOT / CONTAINER.name
    batches = sorted(item.name for item in batch_parent.iterdir() if item.is_dir())
    physical = [name for name in batches
                if (batch_parent / name / "workflow/checkpoints/0008.json").is_file()]
    parseable = [name for name in physical
                 if load_json_if_parseable(batch_parent / name
                                           / "workflow/checkpoints/0008.json")[1]]
    failures_scenes = [name for name in batches
                       if (batch_parent / name / "workflow/initial_judgment/failure.json").is_file()]
    success_no_failure = [name for name in parseable
                          if not (batch_parent / name
                                  / "workflow/initial_judgment/failure.json").is_file()]
    COUNTS["scenes_total"] = len(batches)
    COUNTS["voucher_0008_physical_total"] = len(physical)
    COUNTS["voucher_0008_parseable_total"] = len(parseable)
    COUNTS["voucher_0008_half_written_total"] = len(
        [name for name in physical
         if not load_json_if_parseable(batch_parent / name
                                       / "workflow/checkpoints/0008.json")[1]])
    COUNTS["recorded_failure_scenes"] = len(failures_scenes)
    COUNTS["recovered_success_total"] = len(success_no_failure)
    receiver = checker = 0
    for name in batches:
        host_manifest, ok = load_json_if_parseable(batch_parent / name / "workflow"
                                                  / "host_manifest.json")
        invocation, inv_ok = load_json_if_parseable(batch_parent / name / "workflow"
                                                    / "receive_invocation.json")
        if ok and inv_ok:
            receiver += 1
            if host_manifest.get("receive", {}).get("exit_code") != invocation.get("exit_code"):
                problems.append(f"{name}: receiver 退出码不一致")
        manifest, man_ok = load_json_if_parseable(batch_parent / name / "batch_manifest.json")
        if man_ok and isinstance(manifest.get("checker_invocation"), dict):
            checker_invocation = manifest["checker_invocation"]
            if checker_invocation.get("started") is True and                     checker_invocation.get("exit_code") == 0:
                checker += 1
            for key in ("report", "stdout_log", "stderr_log"):
                reference = checker_invocation.get(key) or {}
                path = batch_parent / name / str(reference.get("path") or "")
                if not (path.is_file() and sha256(path) == reference.get("sha256")):
                    problems.append(f"{name}: checker {key} 引用未验证")
    COUNTS["receiver_starts_recorded"] = receiver
    COUNTS["checker_started_by_receiver"] = checker
    COUNTS["direct_checker_cli_calls"] = 0
    save_json(CONTAINER / "scene_outcomes.json", {
        "scope": "本定点容器（仅一个新 C06b 批次）", "batches": batches,
        "physical_0008": physical, "parseable_0008": parseable,
        "failure_scenes": failures_scenes,
        "derived": {key: COUNTS[key] for key in (
            "scenes_total", "voucher_0008_physical_total", "voucher_0008_parseable_total",
            "voucher_0008_half_written_total", "recorded_failure_scenes",
            "recovered_success_total", "receiver_starts_recorded",
            "checker_started_by_receiver", "direct_checker_cli_calls")},
        "note": "计数按真实 scope 分列；有文件不等于成功；未观察项为 null。"})
    # 本轮正确保护基线
    protection_problems: list = []
    protection = {"executed": False}
    if not R1_BASELINE.is_file():
        protection_problems.append(f"保护基线缺失：{R1_BASELINE}")
    else:
        baseline_sha = sha256(R1_BASELINE)
        if baseline_sha != R1_BASELINE_SHA256:
            protection_problems.append(f"保护基线文件哈希不符：{baseline_sha}")
        baseline_raw = json.loads(R1_BASELINE.read_text(encoding="utf-8"))
        if len(baseline_raw) != R1_BASELINE_ENTRIES:
            protection_problems.append(f"保护基线条目数不符：{len(baseline_raw)}")
        baseline_map = {name.replace(chr(92), "/"): digest for name, digest in baseline_raw.items()}
        scan = {}
        read_errors = 0
        for candidate in PROJECT_ROOT.rglob("*"):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(PROJECT_ROOT).as_posix()
            if relative.split("/")[0] in SKIP_DIRS:
                continue
            try:
                scan[relative] = sha256(candidate)
            except OSError:
                read_errors += 1
        changed = sorted(name for name, digest in baseline_map.items()
                         if name in scan and scan[name] != digest)
        missing = sorted(name for name in baseline_map if name not in scan)
        unexpected = [name for name in changed if name not in R1_ALLOWED_CHANGES]
        if unexpected:
            protection_problems.append(f"相对基线出现预期外变化：{unexpected[:6]}")
        if missing:
            protection_problems.append(f"相对基线缺失 {len(missing)} 项：{missing[:5]}")
        if read_errors:
            protection_problems.append(f"保护扫描读取错误 {read_errors} 个文件")
        frozen_mismatch = []
        for relative, want in FROZEN_HASHES.items():
            target = PROJECT_ROOT / relative
            got = sha256(target) if target.is_file() else None
            if got != want:
                frozen_mismatch.append(f"{relative}={got}")
        if frozen_mismatch:
            protection_problems.append(f"冻结哈希不符：{frozen_mismatch}")
        protection = {"executed": True, "baseline": rel(R1_BASELINE),
                      "baseline_sha256": baseline_sha, "baseline_entries": len(baseline_raw),
                      "scanned_entries": len(scan), "changed": changed,
                      "unexpected_changes": unexpected, "missing": missing,
                      "read_errors": read_errors, "frozen_mismatch": frozen_mismatch,
                      "allowed_changes": sorted(R1_ALLOWED_CHANGES)}
        COUNTS["protection_executed"] = True
    save_json(CONTAINER / "probe_records" / "r1_protection.json", {
        "case": "r1_protection", "protection": protection,
        "protection_problems": protection_problems,
        "missing_records": COUNTS["missing_records"],
        "unregistered_records": COUNTS["unregistered_records"]})
    problems.extend(protection_problems[:5])
    # 停止点
    stop_problems = []
    for name in parseable:
        checkpoint8, _ = load_json_if_parseable(batch_parent / name
                                                / "workflow/checkpoints/0008.json")
        state = checkpoint8["workflow"]["state"]
        if state["phase"] != HOST.CONTROLLER_MODULE.PHASE_G2_APPROVED:
            stop_problems.append(f"{name}: phase 不是 DEV_GATE2_APPROVED")
        if state["gate1_approval"] is not None or state["gate2_approval"] is not None:
            stop_problems.append(f"{name}: 真实批准不是 null")
        if state["next_step_allowed"] is not False:
            stop_problems.append(f"{name}: next_step_allowed 不是 false")
        operation = checkpoint8["operation"]
        if operation["kind"] != "RECORD_SIMULATED_INITIAL_JUDGMENT":
            stop_problems.append(f"{name}: operation.kind 不符")
        for key in ("human_initial_judgment", "ai_suggestion", "final_judgment",
                    "gate1_approval", "gate2_approval"):
            if operation["artifacts"][key] is not None:
                stop_problems.append(f"{name}: artifacts.{key} 不是 null")
        if operation["artifacts"]["ai_action_simulation_allowed"] is not False:
            stop_problems.append(f"{name}: AI 真实许可不是 false")
        names = sorted(p.name for p in (batch_parent / name
                                        / "workflow/checkpoints").iterdir())
        if "0009.json" in names:
            stop_problems.append(f"{name}: 出现 0009")
    problems.extend(stop_problems[:5])
    save_json(CONTAINER / "probe_records" / "r1_stop_point.json", {
        "case": "r1_stop_point", "problems": stop_problems})
    return problems


def main() -> int:
    global CONTAINER
    parser = argparse.ArgumentParser(description="TASK-017 模拟初判宿主有界验证")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--only", default="all",
                        choices=["all", "r1", "main", "premise", "persistence", "late", "binding",
                                 "readonly", "evidence", "smoke"])
    args = parser.parse_args()
    container = Path(args.out_dir).resolve()
    try:
        container.relative_to(CONTAINER_ROOT)
    except ValueError:
        print(f"out-dir 必须位于 {CONTAINER_ROOT} 之下：{container}", file=sys.stderr)
        return 2
    if container == CONTAINER_ROOT or (container.exists() and any(container.iterdir())):
        print(f"out-dir 必须是全新或空目录：{container}", file=sys.stderr)
        return 2
    container.mkdir(parents=True, exist_ok=True)
    CONTAINER = container
    for name in ("cli_logs", "api_records", "probe_records", "isolation", "submissions",
                 "decisions"):
        (container / name).mkdir(parents=True, exist_ok=True)
    # 真实纯核心观察器全程激活：任何宿主 API 触达真实核心都会被独立记录
    CORE_OBSERVER.activate()
    print("== TASK-017 模拟初判宿主有界验证" +
          ("（R1 定点模式）" if args.only == "r1" else "（七组）"))
    print(f"   容器 {container}")
    failures: list = []
    if args.only == "r1":
        R1_MODE["value"] = True
        r1_problems = group_r1_targeted()
        check("R1_STATUS_TAIL_AND_REAL_CORE_OBSERVATION", "host", r1_problems,
              host_api_calls=len(API_RECORDS), real_core_calls=len(CORE_OBSERVER.calls))
        failures.extend(f"R1: {item}" for item in r1_problems)
        r1_evidence = group_r1_evidence_and_protection()
        check("R1_EVIDENCE_PROTECTION_AND_STOP", "evidence", r1_evidence)
        failures.extend(f"R1证据: {item}" for item in r1_evidence)
        _finish(container, failures)
        return 1 if failures else 0
    groups = [
        ("G1_MAIN_INITIAL_JUDGMENT", group_main),
        ("G2_PREMISE_AND_SAMPLES", group_premise_and_samples),
        ("G3_PERSISTENCE_FAULTS", group_persistence_faults),
        ("G4_LATE_CHANGE", group_late_change),
        ("G5_BINDING_AND_PROTOCOL", group_binding_and_protocol),
        ("G6_READONLY_STATUS", group_readonly_status),
    ]
    selected = {
        "main": ["G1_MAIN_INITIAL_JUDGMENT"],
        "premise": ["G2_PREMISE_AND_SAMPLES"],
        "persistence": ["G3_PERSISTENCE_FAULTS"],
        "late": ["G4_LATE_CHANGE"],
        "binding": ["G5_BINDING_AND_PROTOCOL"],
        "readonly": ["G6_READONLY_STATUS"],
    }.get(args.only)
    for name, func in groups:
        if selected is not None and name not in selected:
            continue
        problems = func()
        check(name, "host", problems)
        failures.extend(f"{name}: {item}" for item in problems)
    if args.only in ("all", "evidence", "smoke") or selected is None:
        evidence_problems = group_evidence_and_protection()
        check("G7_EVIDENCE_PROTECTION_AND_STOP", "evidence", evidence_problems)
        failures.extend(f"G7: {item}" for item in evidence_problems)
    else:
        COUNTS["missing_records"] = None
        COUNTS["unregistered_records"] = None
        COUNTS["protection_executed"] = None
    COUNTS["host_api_registered"] = len(API_RECORDS)
    COUNTS["real_core_calls_observed"] = len(CORE_OBSERVER.calls)
    COUNTS["coverd_core_calls_by_api_delta"] = sum(item.get("core_calls_delta") or 0
                                                   for item in API_RECORDS)
    COUNTS["subprocess_internal_core_calls"] = None
    COUNTS["core_calls_observed"] = len(CORE_OBSERVER.calls)
    save_json(container / "core_observations.json", {
        "host_api_calls": len(API_RECORDS), "real_core_calls": len(CORE_OBSERVER.calls),
        "covered_by_api_delta": COUNTS["coverd_core_calls_by_api_delta"],
        "per_api_call": {item["label"]: {"core_calls_delta": item.get("core_calls_delta"),
                                         "outcome": item["outcome"]}
                         for item in API_RECORDS},
        "note": "宿主公开 API 与真实纯核心次数分列，二者不要求相等；子进程内部核心次数未观察记 null。"})
    _finish(container, failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
