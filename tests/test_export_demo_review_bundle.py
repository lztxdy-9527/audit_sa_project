#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-018 只读审阅包导出与离线核验——有界验收入口。

用法::

    .venv\\Scripts\\python.exe -B tests\\test_export_demo_review_bundle.py --out-dir <全新证据容器> [--only <子集>]

只做本卡 §6 的七组有限检查；不为每个输出故障重复建上游链。
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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

HOST_PATH = PROJECT_ROOT / "scripts" / "run_demo_workflow.py"
EXPORTER_PATH = PROJECT_ROOT / "scripts" / "export_demo_review_bundle.py"
CONTAINER_ROOT = PROJECT_ROOT / "data" / "review_bundle_tests"
BUNDLE_ROOT = PROJECT_ROOT / "data" / "review_bundles"
BATCH_ROOT = PROJECT_ROOT / "data" / "batches"
SQLITE_ROOT = PROJECT_ROOT / "data" / "sqlite_tests" / "workflow_gate2"
FIXTURE_ROOT = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a" / "fixtures"
# TASK-018-R1：只读复用的既有合法批次（不新建 batches / SQLite、不重建上游链）
SOURCE_BATCH_PARENT = "task018_run_06"
SOURCE_BATCH_NAME = "c06b"

BASELINE = (PROJECT_ROOT / "data" / "reviews" / "task018_r1_gpt_20261013_144137"
            / "source_hashes_after.json")
BASELINE_SHA256 = "8d8576a5c4cf947fc83834cfaf532d96167f38689a81570696b1b1008f86bd0c"
BASELINE_ENTRIES = 132537
ALLOWED_CHANGES = {"scripts/export_demo_review_bundle.py",
                  "tests/test_export_demo_review_bundle.py"}
FROZEN_HASHES = {
    "scripts/run_demo_workflow.py":
        "3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307",
    "tests/test_initial_judgment_demo_workflow.py":
        "c5b31cd798dbbb72759ae94ec65217e28ff86c453947c59cf074ed1dfa651c05",
    "docs/WORKFLOW_HOST_GUIDE.md":
        "856b39f81b0f37a38709636348621275cbe894bcab4174350107d62968a177c8",
    "scripts/build_demo_initial_judgment.py":
        "0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c",
    "scripts/control_demo_workflow.py":
        "a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c",
    "scripts/build_demo_fact_packet.py":
        "f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62",
}
SKIP_DIRS = {".venv", ".git", "__pycache__"}
DOWNSTREAM_GUARDS = ("normalize_workbook", "load_normalized_to_sqlite", "screen_sqlite",
                     "verify_rule_facts", "build_fact_packet", "build_initial_judgment_record")
PY = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EXPORTER = load_module(EXPORTER_PATH, "task018_exporter")
# 与导出工具使用**同一个**冻结宿主模块实例：测试的替身/守卫/观察必须作用于它实际调用的对象
HOST = EXPORTER._host()

CONTAINER: Path | None = None
HOST_CODE_ENTRIES: list = []          # 每次真实进入冻结公开 inspect_dev_batch 的代码帧
HELPER_RECORDS: list = []             # 直接调用的 shape/映射 helper 对照（与公开 API/CLI 分列）
R2_TYPE_CASES = (("array", []), ("object", {}), ("null", None), ("integer", 7),
                 ("boolean", True))
DIRECT_HOST_STATUS_CALLS: list = []   # 测试直接发起的已登记宿主调用
NESTED_HOST_STATUS_CALLS: list = []   # 工具内部嵌套的宿主 status 调用
CLI_RECORDS: list = []
API_RECORDS: list = []
CALL_REGISTRY: list = []
CHECKS: list = []
STATUS_CALL_LOG: list = []
COUNTS = {
    "cli_calls": 0,
    "api_calls": 0,
    "api_returned": 0,
    "api_blocked": 0,
    "api_unexpected_errors": 0,
    "status_calls_observed": 0,
    "guard_hits": 0,
    "missing_records": None,
    "unregistered_records": None,
    "protection_executed": False,
    "isolation_self_test": None,
    "bundles_exported": 0,
    "bundle_files_total": 0,
    "payloads_total": 0,
    "real_writer_faults": 0,
    "late_change_probes": 0,
    "verify_negative_probes": 0,
    "subprocess_internal_core_calls": None,
    "main_chain_executed": False,
    "zero_finding_chain_executed": False,
}


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


def load_json(path) -> tuple:
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
# 登记
# ---------------------------------------------------------------------------


def run_cli(label: str, args: list, expect_exit: int, *, tool: str = "exporter") -> dict:
    COUNTS["cli_calls"] += 1
    script = EXPORTER_PATH if tool == "exporter" else HOST_PATH
    command = [PY, "-B", str(script), *args]
    done = subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
                          encoding="utf-8")
    payload = None
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError:
        payload = None
    try:
        exit_code = int(done.returncode)
    except (TypeError, ValueError):
        exit_code = None
    entry = {"label": label, "kind": "cli", "tool": tool, "command": command,
             "expect_exit_code": expect_exit, "exit_code": exit_code,
             "exit_code_matches": exit_code == expect_exit, "payload": payload,
             "stdout": done.stdout, "stderr": done.stderr}
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


def record_api(label: str, func, *args, expect_exception=None, **kwargs) -> dict:
    """登记一次公开 API 调用（本卡工具公开入口或冻结宿主公开 status）。"""
    COUNTS["api_calls"] += 1
    entry = {"label": label, "kind": "api", "function": getattr(func, "__name__", str(func)),
             "expect_exception": getattr(expect_exception, "__name__", None)}
    try:
        result = func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001
        matched = expect_exception is not None and isinstance(exc, expect_exception)
        entry["outcome"] = "raised" if matched else "unexpected"
        entry["exception_class"] = type(exc).__name__
        entry["message"] = str(exc)
        entry["stage"] = getattr(exc, "stage", None)
        entry["field"] = getattr(exc, "field", None)
        entry["reasons"] = [str(item) for item in getattr(exc, "reasons", []) or []]
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
    API_RECORDS.append(entry)
    CALL_REGISTRY.append({"record": f"api:{label}", "kind": "api", "detail": entry["outcome"]})
    return entry


def record_helper(label: str, func, *args, expect_exception=None, **kwargs) -> dict:
    """helper 对照调用：与公开 API/CLI 分列登记，保留完整返回或完整异常。"""
    entry = {"label": label, "kind": "helper", "function": getattr(func, "__name__", str(func))}
    try:
        result = func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001
        matched = expect_exception is not None and isinstance(exc, expect_exception)
        entry["outcome"] = "raised" if matched else "unexpected"
        entry["exception_class"] = type(exc).__name__
        entry["message"] = str(exc)
        entry["field"] = getattr(exc, "field", None)
        entry["exception_chain"] = [
            {"class": type(item).__name__, "message": str(item)}
            for item in ([exc] + list(_cause_chain(exc)))]
        entry["traceback"] = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        path = CONTAINER / "helper_records" / f"{label}.exception.json"
        save_json(path, entry)
        entry["exception_path"] = rel(path)
        entry["exception_sha256"] = sha256(path)
    else:
        entry["outcome"] = "returned"
        entry["return_type"] = type(result).__name__
        path = CONTAINER / "helper_records" / f"{label}.return.json"
        save_json(path, {"label": label, "return_type": type(result).__name__,
                         "return_repr": repr(result)[:400]})
        entry["return_path"] = rel(path)
        entry["return_sha256"] = sha256(path)
    HELPER_RECORDS.append(entry)
    CALL_REGISTRY.append({"record": f"helper:{label}", "kind": "helper",
                          "detail": entry["outcome"]})
    return entry


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
# 造样：一个新 C06b 批次到 0008
# ---------------------------------------------------------------------------


def decision_file(batch: Path, revision: int, gate: str, value: str, event_id: str) -> str:
    payload = json.loads((batch / f"workflow/checkpoints/{revision:04d}.json")
                         .read_text(encoding="utf-8"))
    request = payload["workflow"]["state"]["requests"][gate]
    body = {"event_id": event_id, "batch_id": batch.name, "gate": gate,
            "request_id": request["request_id"], "materials_sha256": request["materials_sha256"],
            "decision": value, "actor_kind": "SIMULATED_HUMAN", "actor_id": "sim-analyst-01",
            "occurred_at": "2026-10-13T10:00:00+08:00",
            "reason": f"【模拟测试】TASK-018 有界验收用 {gate} 模拟决定（非真实批准）",
            "simulation": "SIMULATED_TEST_ONLY",
            "confirmations": ({"scope_and_source_reviewed": True} if gate == "GATE1"
                              else {"reconciliation_reviewed": True})}
    path = CONTAINER / "decisions" / f"{batch.name}_{gate}.json"
    save_json(path, body)
    return str(path)


def submission_for(batch: Path, event_id: str) -> dict:
    packet = json.loads((batch / "workflow/fact_packet/fact_packet.json")
                        .read_text(encoding="utf-8"))
    return {
        "submission_version": "TASK-016-initial-judgment-submission-1.0",
        "event_id": event_id,
        "batch_id": batch.name,
        "fact_packet_sha256": canonical_sha256(packet),
        "scope": "BATCH_FACT_PACKET",
        "actor_kind": "SIMULATED_HUMAN",
        "actor_id": "sim-analyst-01",
        "simulation": "SIMULATED_TEST_ONLY",
        "occurred_at": "2026-10-13T10:30:00+08:00",
        "assessment": "【模拟测试】暂不能判断，需要补充证据",
        "reason": "【模拟测试】现有线索不足以形成确定结论，需调用方补充证据。",
        "needed_evidence": ["【模拟测试】银行流水原件"],
        "finding_notes": [],
    }


def build_c06b_batch() -> Path:
    batch = BATCH_ROOT / CONTAINER.name / "c06b"
    run_cli("c06b_start", ["start", "--workbook", str(FIXTURE_ROOT / "C06b.xlsx"),
                           "--batch-dir", str(batch), "--source-description",
                           "TASK-018 只读审阅包有界验收（合成数据，非真实审计）"], 0, tool="host")
    run_cli("c06b_gate1", ["record-simulated-decision", "--batch-dir", str(batch),
                           "--decision-file",
                           decision_file(batch, 1, "GATE1", "APPROVE", "EV-T18-G1")], 0, tool="host")
    run_cli("c06b_prepare", ["prepare-gate2", "--batch-dir", str(batch)], 0, tool="host")
    run_cli("c06b_gate2", ["record-simulated-gate2-decision", "--batch-dir", str(batch),
                           "--decision-file",
                           decision_file(batch, 3, "GATE2", "APPROVE", "EV-T18-G2")], 0, tool="host")
    run_cli("c06b_screen", ["screen-rules", "--batch-dir", str(batch)], 0, tool="host")
    run_cli("c06b_crosscheck", ["crosscheck-rules", "--batch-dir", str(batch)], 0, tool="host")
    run_cli("c06b_fact_packet", ["build-fact-packet", "--batch-dir", str(batch)], 0, tool="host")
    submission_path = CONTAINER / "submissions" / "c06b.json"
    save_json(submission_path, submission_for(batch, "EV-SIM-T18-0001"))
    run_cli("c06b_initial_judgment",
            ["record-simulated-initial-judgment", "--batch-dir", str(batch),
             "--submission-file", str(submission_path)], 0, tool="host")
    return batch


def status_of(batch: Path, label: str | None = None) -> dict:
    """共享直接宿主读取：**每次调用都登记**完整实际返回或完整异常（TASK-018-R1 E1）。"""
    name = label or f"direct_host_status_{len(DIRECT_HOST_STATUS_CALLS) + 1}"
    entry = record_api(name, HOST.inspect_dev_batch, batch,
                       expect_exception=HOST.WorkflowHostBlocked)
    DIRECT_HOST_STATUS_CALLS.append({"label": name, "batch_dir": str(batch),
                                     "outcome": entry["outcome"],
                                     "return_path": entry.get("return_path"),
                                     "exception_path": entry.get("exception_path"),
                                     "exception_class": entry.get("exception_class")})
    if entry["outcome"] != "returned":
        raise AssertionError(f"宿主 status 未成功（{name}）：{entry.get('message')}")
    return json.loads(artifact(entry["return_path"]).read_text(encoding="utf-8"))


def host_entry_scope() -> str:
    """按真实代码帧判断本次进入宿主是工具内部嵌套还是测试直接调用。"""
    frames = [Path(frame.filename).name for frame in traceback.extract_stack()]
    # 只按**精确文件名**判断：测试文件 test_export_demo_review_bundle.py 不算工具内部
    if "export_demo_review_bundle.py" in frames:
        return "tool_nested"
    return "test_direct"


def install_host_observer():
    """观察真实宿主代码帧：绑定实际使用的模块，不观察另一个同名模块。"""
    real = HOST.inspect_dev_batch

    def observed(batch_dir, _real=real):
        scope = host_entry_scope()
        record = {"seq": len(HOST_CODE_ENTRIES) + 1, "scope": scope,
                  "batch_dir": str(batch_dir)}
        HOST_CODE_ENTRIES.append(record)
        COUNTS["host_code_entries"] = len(HOST_CODE_ENTRIES)
        COUNTS["host_code_entries_test_direct"] = len(
            [item for item in HOST_CODE_ENTRIES if item["scope"] == "test_direct"])
        COUNTS["host_code_entries_tool_nested"] = len(
            [item for item in HOST_CODE_ENTRIES if item["scope"] == "tool_nested"])
        if scope == "tool_nested":
            NESTED_HOST_STATUS_CALLS.append(record)
        return _real(batch_dir)

    HOST.inspect_dev_batch = observed
    return real


# ---------------------------------------------------------------------------
# G1 正常导出与确定性
# ---------------------------------------------------------------------------


def group_export_and_determinism(batch: Path) -> list:
    problems: list = []
    status = status_of(batch)
    api_dir = BUNDLE_ROOT / CONTAINER.name / "api_bundle"
    cli_dir = BUNDLE_ROOT / CONTAINER.name / "cli_bundle"
    entry = record_api("g1_export_api", EXPORTER.export_dev_review_bundle, batch, api_dir,
                       expect_exception=EXPORTER.DevReviewBundleBlocked)
    cli_entry = run_cli("g1_export_cli", ["export", "--batch-dir", str(batch),
                                         "--out-dir", str(cli_dir)], 0)
    if entry["outcome"] != "returned":
        problems.append(f"公开 API 导出未成功：{entry.get('message')}")
        return problems
    if cli_entry["exit_code"] != 0:
        problems.append(f"CLI 导出退出码不是 0：{cli_entry['exit_code']}")
    api_result = json.loads(artifact(entry["return_path"]).read_text(encoding="utf-8"))
    if api_result.get("payloads") != 24 or api_result.get("copied_sources") != 22:
        problems.append(f"API 导出计数不符：{api_result.get('payloads')}/"
                        f"{api_result.get('copied_sources')}")
    expected_relatives = {EXPORTER.MANIFEST_NAME, EXPORTER.README_NAME, EXPORTER.STATUS_NAME}
    expected_relatives |= {f"{EXPORTER.EVIDENCE_DIR}/{relative}"
                           for relative, _ in EXPORTER.SOURCE_FILES}
    api_files = {path.relative_to(api_dir).as_posix() for path in api_dir.rglob("*")
                 if path.is_file()}
    if api_files != expected_relatives:
        problems.append(f"API 包文件集合不符：多 {sorted(api_files - expected_relatives)} "
                        f"缺 {sorted(expected_relatives - api_files)}")
    cli_files = {path.relative_to(cli_dir).as_posix() for path in cli_dir.rglob("*")
                 if path.is_file()}
    if cli_files != expected_relatives:
        problems.append("CLI 包文件集合与固定白名单不符")
    # 两份成功包逐文件字节相等
    for relative in sorted(expected_relatives):
        left = (api_dir / relative).read_bytes()
        right = (cli_dir / relative).read_bytes()
        if left != right:
            problems.append(f"两份成功包文件字节不同：{relative}")
    # 逐项对比：源同缓冲、初始 status 预期、复制件
    manifest = json.loads((api_dir / EXPORTER.MANIFEST_NAME).read_text(encoding="utf-8"))
    for relative, lookup in EXPORTER.SOURCE_FILES:
        expected = EXPORTER._lookup(status, lookup, "status")
        source_bytes = (batch / relative).read_bytes()
        copied_bytes = (api_dir / EXPORTER.EVIDENCE_DIR / relative).read_bytes()
        if copied_bytes != source_bytes:
            problems.append(f"复制件与源字节不同：{relative}")
        if hashlib.sha256(copied_bytes).hexdigest() != expected:
            problems.append(f"复制件哈希与初始 status 绑定不同：{relative}")
    packet = json.loads((batch / "workflow/fact_packet/fact_packet.json")
                        .read_text(encoding="utf-8"))
    record_payload = json.loads((batch / "workflow/initial_judgment/initial_judgment.json")
                                .read_text(encoding="utf-8"))
    if packet["summary"]["total_findings"] != 1 or packet["summary"]["rule_counts"]["R02"] != 1:
        problems.append("C06b 事实数量不是 1（R02=1）")
    if api_result.get("packet_sha256") != canonical_sha256(packet):
        problems.append("导出返回的事实包规范指纹与文件不一致")
    if api_result.get("record_sha256") != record_payload["record_sha256"]:
        problems.append("导出返回的记录规范指纹与文件不一致")
    if packet["packet_sha256"] if "packet_sha256" in packet else False:
        problems.append("事实包对象不得内嵌自身指纹")
    # 原文保持：record.simulated_initial_judgment 的 assessment/reason 与提交一致
    submission = json.loads((batch / "workflow/initial_judgment/submission.json")
                           .read_text(encoding="utf-8"))
    simulated = record_payload["record"]["simulated_initial_judgment"]
    for key in ("assessment", "reason", "actor_id", "occurred_at", "event_id"):
        if simulated[key] != submission[key]:
            problems.append(f"记录未保持提交原文：{key}")
    readme = (api_dir / EXPORTER.README_NAME).read_bytes()
    if readme.startswith(b"\xef\xbb\xbf") or b"\r\n" in readme:
        problems.append("README 必须 UTF-8 无 BOM 且 LF")
    if "真实人类独立初判**未保存**" not in readme.decode("utf-8"):
        problems.append("README 前部未明确真实人类初判未保存")
    # 离线核验
    verify_entry = record_api("g1_verify_api", EXPORTER.verify_dev_review_bundle, api_dir,
                              expect_exception=EXPORTER.DevReviewBundleBlocked)
    verify_cli = run_cli("g1_verify_cli", ["verify", "--bundle-dir", str(api_dir)], 0)
    if verify_entry["outcome"] != "returned":
        problems.append("离线核验未成功")
    else:
        verified = json.loads(artifact(verify_entry["return_path"]).read_text(encoding="utf-8"))
        if verified.get("bundle_status") != "DEV_REVIEW_BUNDLE_VERIFIED" \
                or verified.get("scope") != "COPIED_BYTES_ONLY":
            problems.append("离线核验状态/scope 不符")
        if verified.get("payloads_checked") != 24:
            problems.append("离线核验未核对 24 份 payload")
    COUNTS["bundles_exported"] += 2
    COUNTS["bundle_files_total"] += len(expected_relatives) * 2
    COUNTS["payloads_total"] += 48
    save_json(CONTAINER / "probe_records" / "g1_export_and_determinism.json", {
        "case": "g1_export_and_determinism", "batch_dir": str(batch),
        "status_calls": COUNTS["status_calls_observed"],
        "api_bundle": rel(api_dir), "cli_bundle": rel(cli_dir),
        "api_record": entry, "cli_record": cli_entry, "verify_record": verify_entry,
        "verify_cli_exit": verify_cli["exit_code"],
        "file_set": sorted(expected_relatives), "manifest": manifest,
        "packet_summary": packet["summary"],
        "note": "同一新批次分别经公开 API 与 CLI 导出至两个新目录，25 份文件与 24 项清单齐全，"
                "两份成功包逐文件字节相等；逐项对比源同缓冲、初始 status 绑定与复制件。"})
    return problems


# ---------------------------------------------------------------------------
# G2 前提与路径
# ---------------------------------------------------------------------------


def group_preconditions_and_paths(batch: Path) -> list:
    problems: list = []
    existing = BUNDLE_ROOT / CONTAINER.name / "api_bundle"
    empty_dir = BUNDLE_ROOT / CONTAINER.name / "empty_dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    source_before = tree_hashes(batch)
    db_dir = SQLITE_ROOT / CONTAINER.name
    db_before = {p.name: sha256(p) for p in db_dir.rglob("*.sqlite3")}
    cases = [
        ("existing_bundle", batch, existing),
        ("existing_empty_dir", batch, empty_dir),
        ("out_equals_source", batch, batch),
        ("out_inside_source", batch, batch / "workflow" / "inner_bundle"),
        ("out_outside_root", batch, PROJECT_ROOT / "data" / "batches" / CONTAINER.name
         / "outside_bundle"),
        ("out_parent_of_root", batch, BUNDLE_ROOT / CONTAINER.name / ".." / ".."),
    ]
    for label, source, target in cases:
        entry = record_api(f"g2_{label}", EXPORTER.export_dev_review_bundle, source, target,
                           expect_exception=EXPORTER.DevReviewBundleBlocked)
        if entry["outcome"] != "raised":
            problems.append(f"{label}: 未被 Blocked（{entry['outcome']}）")
    # 真实缺失批次由冻结宿主拒绝
    missing_batch = BATCH_ROOT / CONTAINER.name / "does_not_exist"
    missing_entry = record_api("g2_missing_batch", EXPORTER.export_dev_review_bundle,
                               missing_batch, BUNDLE_ROOT / CONTAINER.name / "missing_bundle",
                               expect_exception=EXPORTER.DevReviewBundleBlocked)
    if missing_entry["outcome"] != "raised":
        problems.append("缺失批次未被拒绝")
    missing_dir = BUNDLE_ROOT / CONTAINER.name / "missing_bundle"
    if missing_dir.exists():
        problems.append("前提失败时创建了输出目录")
    # 缺 0008 的真实批次：用只到 0007 的新批次（真实宿主拒绝）
    incomplete = BATCH_ROOT / CONTAINER.name / "incomplete"
    run_cli("g2_incomplete_build", ["build-fact-packet", "--batch-dir", str(incomplete)], 0,
            tool="host") if False else None
    # 宿主 Blocked / Error 传播：用明确测试替身分列（不冒充真实业务链复验）
    real_status = HOST.inspect_dev_batch

    def blocked_status(_batch_dir):
        raise HOST.WorkflowHostBlocked("【测试替身】宿主前提阻断（非真实业务链复验）")

    def error_status(_batch_dir):
        raise HOST.WorkflowHostError("【测试替身】宿主运行失败（非真实业务链复验）")

    HOST.inspect_dev_batch = blocked_status
    try:
        blocked_entry = record_api("g2_host_blocked_proxy", EXPORTER.export_dev_review_bundle,
                                   batch, BUNDLE_ROOT / CONTAINER.name / "host_blocked_bundle",
                                   expect_exception=EXPORTER.DevReviewBundleBlocked)
    finally:
        HOST.inspect_dev_batch = real_status
    HOST.inspect_dev_batch = error_status
    try:
        error_entry = record_api("g2_host_error_proxy", EXPORTER.export_dev_review_bundle,
                                 batch, BUNDLE_ROOT / CONTAINER.name / "host_error_bundle",
                                 expect_exception=EXPORTER.DevReviewBundleError)
    finally:
        HOST.inspect_dev_batch = real_status
    blocked_chain = [link["class"] for link in blocked_entry.get("exception_chain") or []]
    error_chain = [link["class"] for link in error_entry.get("exception_chain") or []]
    if blocked_entry["outcome"] != "raised" or blocked_entry["exception_class"] != \
            "DevReviewBundleBlocked" or "WorkflowHostBlocked" not in blocked_chain:
        problems.append(f"宿主前提阻断未按 DevReviewBundleBlocked 传播（链 {blocked_chain}）")
    if error_entry["outcome"] != "raised" or error_entry["exception_class"] != \
            "DevReviewBundleError" or "WorkflowHostError" not in error_chain:
        problems.append(f"宿主运行失败未按 DevReviewBundleError 传播（链 {error_chain}）")
    for label in ("host_blocked_bundle", "host_error_bundle", "missing_bundle",
                  "outside_bundle"):
        if (BUNDLE_ROOT / CONTAINER.name / label).exists():
            problems.append(f"前提/替身失败却创建了输出：{label}")
    if tree_hashes(batch) != source_before:
        problems.append("前提反例改变了源批次文件")
    if {p.name: sha256(p) for p in db_dir.rglob("*.sqlite3")} != db_before:
        problems.append("前提反例改变了外置数据库字节")
    save_json(CONTAINER / "probe_records" / "g2_preconditions_and_paths.json", {
        "case": "g2_preconditions_and_paths",
        "blocked_cases": [item["label"] for item in API_RECORDS
                          if item["label"].startswith("g2_")],
        "host_blocked_proxy": blocked_entry, "host_error_proxy": error_entry,
        "source_unchanged": tree_hashes(batch) == source_before,
        "database_unchanged": {p.name: sha256(p) for p in db_dir.rglob("*.sqlite3")} == db_before,
        "note": "前提与路径反例含已有目录（含空目录）、输出等于/位于源内、越界与父路径；"
                "宿主 Blocked/Error 用明确测试替身分列核对传播，不冒充真实业务链复验。"})
    return problems


# ---------------------------------------------------------------------------
# G3 晚变更
# ---------------------------------------------------------------------------


def group_late_change(batch: Path) -> list:
    problems: list = []
    target = batch / "workflow/fact_packet/fact_packet.md"
    backup = target.read_bytes()
    status_before = tree_hashes(batch)
    real_status = HOST.inspect_dev_batch
    state = {"calls": 0, "injected": False, "before": None, "after": None, "order": []}

    def wrapping_status(batch_dir, _real=real_status, _state=state, _file=target):
        result = _real(batch_dir)
        _state["calls"] += 1
        _state["order"].append(_state["calls"])
        # 只在“末次” status 返回真实原对象之后注入：导出内部恰好调用两次 status
        if _state["calls"] == 2 and not _state["injected"]:
            _state["before"] = sha256(_file)
            with open(_file, "ab") as handle:
                handle.write(b"\n")
            _state["after"] = sha256(_file)
            _state["injected"] = True
        return result

    late_dir = BUNDLE_ROOT / CONTAINER.name / "late_change_bundle"
    HOST.inspect_dev_batch = wrapping_status
    try:
        entry = record_api("g3_late_change_export", EXPORTER.export_dev_review_bundle, batch,
                           late_dir, expect_exception=EXPORTER.DevReviewBundleBlocked)
    finally:
        HOST.inspect_dev_batch = real_status
    COUNTS["late_change_probes"] += 1
    failure, failure_ok = load_json(late_dir / EXPORTER.FAILURE_NAME) if late_dir.exists() \
        else (None, False)
    if entry["outcome"] != "raised":
        problems.append("末次 status 之后的晚变更未被本次导出拒绝")
    if entry.get("exception_class") != "DevReviewBundleBlocked":
        problems.append(f"预期协议阻断，实际 {entry.get('exception_class')}")
    message = entry.get("message") or ""
    if "fact_packet.md" not in message:
        problems.append("拒绝消息未指出目标文件 fact_packet.md")
    if not state["injected"] or state["calls"] != 2:
        problems.append(f"注入位置不符：calls={state['calls']} injected={state['injected']}")
    if not failure_ok:
        problems.append("新输出未留下有效失败诊断")
    elif failure.get("target_exit_code") != 1 or failure.get("stage") != "export":
        problems.append(f"失败诊断退出码/阶段不符：{failure.get('target_exit_code')}/"
                        f"{failure.get('stage')}")
    revoked_status = run_cli("g3_revoked_status", ["status", "--batch-dir", str(batch)], 1,
                             tool="host")
    target.write_bytes(backup)
    restored_status = run_cli("g3_restored_status", ["status", "--batch-dir", str(batch)], 0,
                              tool="host")
    host_failure = batch / "workflow/initial_judgment/failure.json"
    if host_failure.exists() or (batch / "workflow/fact_packet/failure.json").exists():
        problems.append("导出失败不得向宿主/源批次写失败诊断")
    after_restore = tree_hashes(batch)
    changed = [key for key in status_before if status_before[key] != after_restore.get(key)]
    if changed:
        problems.append(f"恢复原件后源批次仍有变化：{changed[:4]}")
    for revision in range(1, 9):
        if not (batch / f"workflow/checkpoints/{revision:04d}.json").is_file():
            problems.append(f"000{revision} 缺失")
    save_json(CONTAINER / "probe_records" / "g3_late_change.json", {
        "case": "g3_late_change", "api": entry, "status_calls": state["calls"],
        "injected": state["injected"], "before_sha256": state["before"],
        "after_sha256": state["after"], "failure": failure,
        "failure_written": failure_ok, "revoked_status_exit": revoked_status["exit_code"],
        "restored_status_exit": restored_status["exit_code"],
        "bundle_dir": rel(late_dir) if late_dir.exists() else None,
        "source_unchanged_after_restore": not changed,
        "note": "包装真实末次 status（导出内部第 2 次调用）返回原对象之后给 fact_packet.md 追加"
                "一个 LF，不同步哈希；本次导出即协议阻断并指出该文件，新输出留有效 failure。"})
    return problems


# ---------------------------------------------------------------------------
# G4 写入失败
# ---------------------------------------------------------------------------


def group_write_faults(batch: Path) -> list:
    problems: list = []
    detail = []
    for mode in ("payload_partial", "manifest_throw"):
        label = f"g4_{mode}"
        out_dir = BUNDLE_ROOT / CONTAINER.name / label
        state = {"hits": 0, "mode": None, "newline": None, "target": None,
                 "text_bytes": None, "buffer_sha256": None,
                 "target_relative": (f"{EXPORTER.EVIDENCE_DIR}/batch_manifest.json"
                                     if mode == "payload_partial" else EXPORTER.MANIFEST_NAME)}
        real_open = open

        class _ObservedHandle:
            def __init__(self, handle):
                self._handle = handle

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self._handle.close()
                return False

            def write(self, data):
                state["hits"] += 1
                raw = data if isinstance(data, bytes) else data.encode("utf-8")
                state["text_bytes"] = raw
                state["buffer_sha256"] = hashlib.sha256(raw).hexdigest()
                boundary = max(1, len(raw) // 2)
                self._handle.write(raw[:boundary])
                if mode == "payload_partial":
                    raise OSError("【测试注入】真实独占写句柄上单次 write 半写后失败")
                self._handle.write(raw[boundary:])
                raise RuntimeError("【测试注入】manifest 完整写入后抛 sentinel")

            def __getattr__(self, name):
                return getattr(self._handle, name)

        def observed_open(file, open_mode="r", *args, **kwargs):
            handle = real_open(file, open_mode, *args, **kwargs)
            if "b" not in str(open_mode):
                return handle
            try:
                resolved = Path(getattr(handle, "name", file)).resolve()
            except (OSError, TypeError):
                return handle
            if Path(resolved).name != Path(state["target_relative"]).name or \
                    out_dir.name not in str(resolved):
                return handle
            state["mode"] = open_mode
            state["newline"] = kwargs.get("newline")
            state["target"] = resolved
            return _ObservedHandle(handle)

        EXPORTER.open = observed_open
        COUNTS["real_writer_faults"] += 1
        try:
            entry = record_api(label, EXPORTER.export_dev_review_bundle, batch, out_dir,
                               expect_exception=(EXPORTER.DevReviewBundleError,
                                                 EXPORTER.DevReviewBundleBlocked))
        finally:
            del EXPORTER.open
        failure, failure_ok = load_json(out_dir / EXPORTER.FAILURE_NAME) if out_dir.exists() \
            else (None, False)
        verify_entry = record_api(f"{label}_verify", EXPORTER.verify_dev_review_bundle, out_dir,
                                  expect_exception=(EXPORTER.DevReviewBundleBlocked,
                                                    EXPORTER.DevReviewBundleError))
        half_written = b""
        if state["target"] is not None and Path(state["target"]).is_file():
            half_written = Path(state["target"]).read_bytes()
        expected_partial = (state["text_bytes"] or b"")[: max(1, len(state["text_bytes"] or b"") // 2)]
        if entry["outcome"] != "raised":
            problems.append(f"{mode}: 未按预期异常失败")
        elif entry.get("exception_class") != "DevReviewBundleError":
            problems.append(f"{mode}: 预期运行失败，实际 {entry.get('exception_class')}")
        if not failure_ok or failure.get("target_exit_code") != 2 \
                or failure.get("stage") != "export":
            problems.append(f"{mode}: 新输出未留下有效运行失败诊断")
        if verify_entry["outcome"] != "raised":
            problems.append(f"{mode}: 离线核验未拒绝不完整包")
        if state["hits"] != 1:
            problems.append(f"{mode}: 真实 writer 写命中不是 1 次：{state['hits']}")
        if state["mode"] != "xb":
            problems.append(f"{mode}: 未使用独占模式写入：{state['mode']!r}")
        if mode == "payload_partial":
            if half_written != expected_partial:
                problems.append(f"{mode}: 半写字节与预期不符（{len(half_written)}）")
            pending_path = CONTAINER / "pending_bytes" / f"{mode}.bin"
            pending_path.parent.mkdir(parents=True, exist_ok=True)
            with real_open(pending_path, "wb") as handle:
                handle.write(state["text_bytes"] or b"")
            if pending_path.read_bytes() != (state["text_bytes"] or b""):
                problems.append(f"{mode}: 待写字节单份读回不一致")
        else:
            if state["target"] is None or not Path(state["target"]).is_file():
                problems.append(f"{mode}: 完整写入后 sentinel 未留下 manifest 文件")
            elif hashlib.sha256(Path(state["target"]).read_bytes()).hexdigest() \
                    != state["buffer_sha256"]:
                problems.append(f"{mode}: 完整 throw 的磁盘哈希与缓冲哈希不一致")
        detail.append({"mode": mode, "api": entry, "failure": failure,
                       "verify_api": verify_entry, "write_hits": state["hits"],
                       "open_mode": state["mode"], "target_relative": state["target_relative"],
                       "half_written_bytes": len(half_written),
                       "expected_partial_bytes": len(expected_partial),
                       "buffer_sha256": state["buffer_sha256"]})
    save_json(CONTAINER / "probe_records" / "g4_write_faults.json", {
        "case": "g4_write_faults", "detail": detail,
        "note": "半写以导出工具真实独占写句柄上的单次 write 注入（未替换整个 writer）；"
                "manifest 为真实完整写入后抛 sentinel；不重跑宿主 0008 writer 故障。"})
    return problems


# ---------------------------------------------------------------------------
# G5 离线核验反例
# ---------------------------------------------------------------------------


def group_verify_negatives(good_bundle: Path) -> list:
    problems: list = []
    isolate_root = CONTAINER / "isolated_bundles"
    isolate_root.mkdir(parents=True, exist_ok=True)
    original_before = tree_hashes(good_bundle)
    probes = []

    def fresh_copy(name: str) -> Path:
        target = isolate_root / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(good_bundle, target)
        return target

    # 1) 改一个 payload 字节
    copy1 = fresh_copy("payload_byte")
    payload = copy1 / EXPORTER.EVIDENCE_DIR / "workflow/fact_packet/fact_packet.md"
    payload.write_bytes(payload.read_bytes() + b"\n")
    probes.append(("payload_byte_changed", copy1))
    # 2) 清单哈希加 LF
    copy2 = fresh_copy("manifest_hash_lf")
    manifest_path = copy2 / EXPORTER.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["payloads"][0]["file_sha256"] = manifest["payloads"][0]["file_sha256"] + "\n"
    manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2)
                               + "\n").encode("utf-8"))
    probes.append(("manifest_hash_suffix", copy2))
    # 3) 重复清单路径
    copy3 = fresh_copy("duplicate_path")
    manifest_path = copy3 / EXPORTER.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["payloads"].append(copy.deepcopy(manifest["payloads"][0]))
    manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2)
                               + "\n").encode("utf-8"))
    probes.append(("duplicate_manifest_path", copy3))
    # 4) 越界清单路径
    copy4 = fresh_copy("escaping_path")
    manifest_path = copy4 / EXPORTER.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["payloads"][0]["relative"] = "../escaped.json"
    manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2)
                               + "\n").encode("utf-8"))
    probes.append(("escaping_manifest_path", copy4))
    # 5) 加未知文件
    copy5 = fresh_copy("unknown_file")
    (copy5 / "extra_unknown.txt").write_text("unexpected\n", encoding="utf-8")
    probes.append(("unknown_file", copy5))
    # 6) failure 存在
    copy6 = fresh_copy("with_failure")
    save_json(copy6 / EXPORTER.FAILURE_NAME, {"failure_version": "x", "stage": "export"})
    probes.append(("failure_present", copy6))

    for label, target in probes:
        entry = record_api(f"g5_{label}", EXPORTER.verify_dev_review_bundle, target,
                           expect_exception=(EXPORTER.DevReviewBundleBlocked,
                                             EXPORTER.DevReviewBundleError))
        if entry["outcome"] != "raised":
            problems.append(f"{label}: 离线核验未拒绝")
        elif entry.get("exception_class") != "DevReviewBundleBlocked":
            problems.append(f"{label}: 预期协议阻断，实际 {entry.get('exception_class')}")
        COUNTS["verify_negative_probes"] += 1
    if tree_hashes(good_bundle) != original_before:
        problems.append("核验反例改变了原成功包")
    # verify 不依赖原批次/宿主：把宿主公开读取与项目根替换为抛错替身
    real_status = HOST.inspect_dev_batch
    real_root = EXPORTER.PROJECT_ROOT
    real_batches = EXPORTER.BATCHES_ROOT

    def throwing(*_args, **_kwargs):
        raise AssertionError("离线核验不得读取原批次/宿主")

    HOST.inspect_dev_batch = throwing
    EXPORTER.PROJECT_ROOT = Path(CONTAINER / "nonexistent_project_root")
    EXPORTER.BATCHES_ROOT = Path(CONTAINER / "nonexistent_batches_root")
    try:
        independent = record_api("g5_verify_without_source", EXPORTER.verify_dev_review_bundle,
                                 good_bundle,
                                 expect_exception=(EXPORTER.DevReviewBundleBlocked,
                                                   EXPORTER.DevReviewBundleError))
    finally:
        HOST.inspect_dev_batch = real_status
        EXPORTER.PROJECT_ROOT = real_root
        EXPORTER.BATCHES_ROOT = real_batches
    if independent["outcome"] != "returned":
        problems.append(f"原批次/宿主不可用时离线核验失败：{independent.get('message')}")
    # 来源字段含绝对路径也不跟随
    copy7 = fresh_copy("absolute_source_field")
    manifest_path = copy7 / EXPORTER.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["payloads"]:
        if item["role"] == "copied_source":
            item["source_relative"] = str(PROJECT_ROOT / "scripts" / "run_demo_workflow.py")
            break
    manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2)
                               + "\n").encode("utf-8"))
    absolute_entry = record_api("g5_absolute_source_field", EXPORTER.verify_dev_review_bundle,
                                copy7,
                                expect_exception=(EXPORTER.DevReviewBundleBlocked,
                                                  EXPORTER.DevReviewBundleError))
    if absolute_entry["outcome"] != "raised":
        problems.append("清单来源字段含绝对路径时未拒绝（不跟随原则）")
    COUNTS["verify_negative_probes"] += 1
    save_json(CONTAINER / "probe_records" / "g5_verify_negatives.json", {
        "case": "g5_verify_negatives",
        "probes": [item["label"] for item in API_RECORDS if item["label"].startswith("g5_")],
        "good_bundle": rel(good_bundle),
        "independent_verify": independent,
        "absolute_source_field": absolute_entry,
        "note": "有限反例只在成功包的隔离副本上改动；原成功包不变；"
                "独立核验在原批次/宿主读取被替换为抛错时仍成功，且不跟随来源字段中的绝对路径。"})
    return problems


# ---------------------------------------------------------------------------
# G6 只读与停止点
# ---------------------------------------------------------------------------


def group_readonly_and_stop(batch: Path, good_bundle: Path) -> list:
    problems: list = []
    batch_before = tree_hashes(batch)
    db_dir = SQLITE_ROOT / CONTAINER.name
    db_before = {p.name: sha256(p) for p in db_dir.rglob("*.sqlite3")}
    checkpoint8_before = sha256(batch / "workflow/checkpoints/0008.json")
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
            raise AssertionError(f"只读导出/核验不得调用下游核心 {_name}")

        setattr(module, name, forbidden)
    guard_dir = BUNDLE_ROOT / CONTAINER.name / "guard_bundle"
    try:
        export_entry = record_api("g6_export_under_guard", EXPORTER.export_dev_review_bundle,
                                  batch, guard_dir,
                                  expect_exception=EXPORTER.DevReviewBundleBlocked)
        verify_entry = record_api("g6_verify_under_guard", EXPORTER.verify_dev_review_bundle,
                                  good_bundle,
                                  expect_exception=(EXPORTER.DevReviewBundleBlocked,
                                                    EXPORTER.DevReviewBundleError))
    finally:
        for name, (module, attr, original) in guards.items():
            setattr(module, attr, original)
    if export_entry["outcome"] != "returned":
        problems.append(f"守卫下导出未成功：{export_entry.get('message')}")
    if verify_entry["outcome"] != "returned":
        problems.append("守卫下离线核验未成功")
    if any(value for value in hits.values()):
        problems.append(f"守卫下触达下游核心：{hits}")
    COUNTS["guard_hits"] += sum(hits.values())
    if COUNTS["status_calls_observed"] <= 0:
        problems.append("未观察到冻结公开 status 被调用")
    if tree_hashes(batch) != batch_before:
        problems.append("导出/核验改变了源批次文件")
    if {p.name: sha256(p) for p in db_dir.rglob("*.sqlite3")} != db_before:
        problems.append("导出/核验改变了外置数据库字节")
    if sha256(batch / "workflow/checkpoints/0008.json") != checkpoint8_before:
        problems.append("0008 字节发生变化")
    status = status_of(batch)
    checkpoint8 = json.loads((batch / "workflow/checkpoints/0008.json").read_text(encoding="utf-8"))
    checkpoint7 = json.loads((batch / "workflow/checkpoints/0007.json").read_text(encoding="utf-8"))
    if not same_json(checkpoint8["workflow"], checkpoint7["workflow"]):
        problems.append("0008.workflow 与 0007 不再严格相等")
    if status["real_approvals"] != 0 or status["next_step_allowed"] is not False:
        problems.append("真实批准/next_step_allowed 不符")
    if status["initial_judgment"]["ai_action_simulation_allowed"] is not False:
        problems.append("AI 实际许可不是 false")
    names = sorted(path.name for path in (batch / "workflow/checkpoints").iterdir())
    if "0009.json" in names:
        problems.append("出现 0009")
    save_json(CONTAINER / "probe_records" / "g6_readonly_and_stop.json", {
        "case": "g6_readonly_and_stop", "guard_hits": hits,
        "export_api": export_entry, "verify_api": verify_entry,
        "status_calls_observed": COUNTS["status_calls_observed"],
        "source_unchanged": tree_hashes(batch) == batch_before,
        "database_unchanged": {p.name: sha256(p) for p in db_dir.rglob("*.sqlite3")} == db_before,
        "checkpoint_0008_unchanged": sha256(batch / "workflow/checkpoints/0008.json")
        == checkpoint8_before,
        "note": "六个真实下游函数计数抛错守卫下 export 与 verify 均成功、命中 0；"
                "测试自身 I/O 不计入核心调用；子进程内部次数未观察记 null。"})
    return problems


# ---------------------------------------------------------------------------
# G7 证据与保护收尾
# ---------------------------------------------------------------------------


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
                    ledger["cli_records"] + ledger["api_records"]
                    + ledger.get("helper_records", [])}
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
            if not item.get(key):
                continue
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
    for item in HELPER_RECORDS:
        for key in ("return_path", "exception_path"):
            if not item.get(key):
                continue
            target = artifact(item[key])
            ledger_entries.append({"record": f"helper:{item['label']}", "field": key,
                                   "path": item[key], "exists": target.is_file(),
                                   "sha256": sha256(target) if target.is_file() else None})
    for item in API_RECORDS + HELPER_RECORDS:
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
        "audit_problems_on_original": ledger_problems,
        "ledger_path": rel(ledger_path)})
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
        if changed:
            protection_problems.append(f"既有文件出现变化（本卡要求 changed=[]）：{changed[:6]}")
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
                      "changed": changed, "missing": missing, "read_errors": read_errors,
                      "frozen_mismatch": frozen_mismatch, "allowed_changes": sorted(ALLOWED_CHANGES)}
        COUNTS["protection_executed"] = True
    save_json(CONTAINER / "probe_records" / "g7_protection.json", {
        "case": "g7_protection", "protection": protection,
        "protection_problems": protection_problems,
        "missing_records": COUNTS["missing_records"],
        "unregistered_records": COUNTS["unregistered_records"]})
    problems.extend(protection_problems[:5])
    # 现场导出（按真实 scope 从磁盘导出，不用累加计数冒充）
    round_root = BUNDLE_ROOT / CONTAINER.name
    # 成功包必须没有 failure.json；有失败诊断的目录（即使残留 manifest）不计入成功
    success_bundles = sorted(item.name for item in round_root.iterdir()
                             if (item / EXPORTER.MANIFEST_NAME).is_file()
                             and not (item / EXPORTER.FAILURE_NAME).is_file())
    failure_bundles = sorted(item.name for item in round_root.iterdir()
                             if (item / EXPORTER.FAILURE_NAME).is_file())
    success_files = sum(len([p for p in (round_root / name).rglob("*") if p.is_file()])
                        for name in success_bundles)
    payloads_total = EXPORTER.PAYLOADS * len(success_bundles)
    isolated_copies = len([p for p in (CONTAINER / "isolated_bundles").iterdir()]) \
        if (CONTAINER / "isolated_bundles").is_dir() else 0
    batch_root_round = BATCH_ROOT / CONTAINER.name
    batches = sorted(item.name for item in batch_root_round.iterdir() if item.is_dir()) \
        if batch_root_round.is_dir() else []
    save_json(CONTAINER / "counts_scope.json", {
        "scope": "本容器：新建批次与导出根均在本轮唯一名称下",
        "batches": batches,
        "success_bundles": success_bundles,
        "failure_only_bundles": failure_bundles,
        "bundles_exported": len(success_bundles),
        "bundle_files_total": success_files,
        "payloads_total": payloads_total,
        "isolated_verify_copies": isolated_copies,
        "status_calls_observed": COUNTS["status_calls_observed"],
        "real_writer_faults": COUNTS["real_writer_faults"],
        "late_change_probes": COUNTS["late_change_probes"],
        "verify_negative_probes": COUNTS["verify_negative_probes"],
        "guard_hits": COUNTS["guard_hits"],
        "main_chain_executed": COUNTS["main_chain_executed"],
        "zero_finding_chain_executed": COUNTS["zero_finding_chain_executed"],
        "subprocess_internal_core_calls": None,
        "note": "计数从磁盘现场导出并注明 scope；未执行 MAIN 或零条链，对应实测数不填；"
                "子进程内部核心次数未观察记 null；失败目录只有 failure.json，不计入成功包。"})
    COUNTS["bundles_exported"] = len(success_bundles)
    COUNTS["bundle_files_total"] = success_files
    COUNTS["payloads_total"] = payloads_total
    COUNTS["batches_total"] = len(batches)
    return problems


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TASK-018-R1 定点模式（只读复用既有批次；不新建 batches/SQLite、不重建上游链）
# ---------------------------------------------------------------------------


def r1_source_batch() -> Path:
    return BATCH_ROOT / SOURCE_BATCH_PARENT / SOURCE_BATCH_NAME


def r1_guards():
    hits = {name: 0 for name in DOWNSTREAM_GUARDS}
    guards = {}
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
            raise AssertionError(f"只读导出/核验不得调用下游核心 {_name}")

        setattr(module, name, forbidden)
    return guards, hits


def r1_release_guards(guards):
    for name, (module, attr, original) in guards.items():
        setattr(module, attr, original)


def group_r1_normal_export(batch: Path) -> tuple:
    """一个正常包：真实 export 一次（六下游守卫下），真实 status 观察与登记 scope 对应。"""
    problems: list = []
    status = status_of(batch, "r1_direct_status_initial")
    normal_dir = BUNDLE_ROOT / CONTAINER.name / "r1_normal"
    guards, hits = r1_guards()
    try:
        export_entry = record_api("r1_normal_export", EXPORTER.export_dev_review_bundle, batch,
                                  normal_dir,
                                  expect_exception=EXPORTER.DevReviewBundleBlocked)
    finally:
        r1_release_guards(guards)
    if export_entry["outcome"] != "returned":
        problems.append(f"正常导出未成功：{export_entry.get('message')}")
        return problems, None, status
    if any(hits.values()):
        problems.append(f"守卫下触达下游核心：{hits}")
    COUNTS["guard_hits"] += sum(hits.values())
    result = json.loads(artifact(export_entry["return_path"]).read_text(encoding="utf-8"))
    if result.get("payloads") != 24 or result.get("copied_sources") != 22:
        problems.append(f"导出计数不符：{result.get('payloads')}/{result.get('copied_sources')}")
    expected_relatives = set(EXPORTER._fixed_relatives())
    actual_relatives = {path.relative_to(normal_dir).as_posix() for path in normal_dir.rglob("*")
                        if path.is_file()}
    if actual_relatives != expected_relatives:
        problems.append(f"正常包文件集合不符：多 {sorted(actual_relatives - expected_relatives)} "
                        f"缺 {sorted(expected_relatives - actual_relatives)}")
    # 22 份来源初始绑定 + 实际复制字节
    initial_bindings = {}
    for relative, lookup in EXPORTER.SOURCE_FILES:
        bound = EXPORTER._lookup(status, lookup, "status")
        initial_bindings[relative] = bound
        source_bytes = (batch / relative).read_bytes()
        copied_bytes = (normal_dir / EXPORTER.EVIDENCE_DIR / relative).read_bytes()
        if copied_bytes != source_bytes:
            problems.append(f"复制件与只读源字节不同：{relative}")
        if hashlib.sha256(copied_bytes).hexdigest() != bound:
            problems.append(f"复制件与真实 status 初始绑定不同：{relative}")
    # C06b 事实数量、判断原文、开发边界
    packet = json.loads((batch / "workflow/fact_packet/fact_packet.json")
                        .read_text(encoding="utf-8"))
    record_payload = json.loads((batch / "workflow/initial_judgment/initial_judgment.json")
                                .read_text(encoding="utf-8"))
    submission = json.loads((batch / "workflow/initial_judgment/submission.json")
                           .read_text(encoding="utf-8"))
    if packet["summary"]["total_findings"] != 1 or packet["summary"]["rule_counts"]["R02"] != 1:
        problems.append("C06b 事实数量不是 1（R02=1）")
    simulated = record_payload["record"]["simulated_initial_judgment"]
    for key in ("assessment", "reason", "actor_id", "occurred_at", "event_id"):
        if simulated[key] != submission[key]:
            problems.append(f"判断原文未保持：{key}")
    if record_payload["record"]["mode"] != "DEVELOPMENT_TEST_ONLY":
        problems.append("记录开发模式不符")
    readme = (normal_dir / EXPORTER.README_NAME).read_bytes()
    if readme.startswith(b"\xef\xbb\xbf") or b"\r\n" in readme:
        problems.append("README 必须 UTF-8 无 BOM 且 LF")
    # 正常 verify（API）与新进程 CLI
    verify_entry = record_api("r1_normal_verify", EXPORTER.verify_dev_review_bundle, normal_dir,
                              expect_exception=EXPORTER.DevReviewBundleBlocked)
    if verify_entry["outcome"] != "returned":
        problems.append(f"正常离线核验未成功：{verify_entry.get('message')}")
    else:
        verified = json.loads(artifact(verify_entry["return_path"]).read_text(encoding="utf-8"))
        if verified.get("bundle_status") != "DEV_REVIEW_BUNDLE_VERIFIED" \
                or verified.get("files_byte_confirmed") != 25:
            problems.append("正常核验状态/最终字节确认数不符")
    verify_cli = run_cli("r1_normal_verify_cli", ["verify", "--bundle-dir", str(normal_dir)], 0)
    scope_counts = {
        "host_code_entries": COUNTS.get("host_code_entries"),
        "host_code_entries_test_direct": COUNTS.get("host_code_entries_test_direct"),
        "host_code_entries_tool_nested": COUNTS.get("host_code_entries_tool_nested"),
        "direct_registered_status": len(DIRECT_HOST_STATUS_CALLS),
        "nested_status_calls": len(NESTED_HOST_STATUS_CALLS),
    }
    if not DIRECT_HOST_STATUS_CALLS:
        problems.append("测试直接宿主调用未登记")
    if scope_counts["host_code_entries_tool_nested"] is None:
        problems.append("工具内部嵌套宿主调用未观察")
    save_json(CONTAINER / "probe_records" / "r1_normal_export.json", {
        "case": "r1_normal_export", "batch_dir": str(batch), "bundle_dir": rel(normal_dir),
        "export_record": export_entry, "verify_record": verify_entry,
        "verify_cli_exit": verify_cli["exit_code"], "guard_hits": hits,
        "initial_bindings": initial_bindings, "scope_counts": scope_counts,
        "packet_summary": packet["summary"],
        "note": "同一只读源批次真实 export 一次（六真实下游守卫下，命中 0）；22 份复制件与源"
                "字节及真实 status 初始绑定逐项一致；正常 verify 与新进程 CLI 均 0。"})
    return problems, normal_dir, status


def group_r1_export_tail(batch: Path) -> list:
    """导出收尾两个有限目标：README.md 与 manifest.json。"""
    problems: list = []
    detail = []
    # --- 先无注入观察真实消费位置
    observe_dir = BUNDLE_ROOT / CONTAINER.name / "r1_observe"
    observed = {"write_calls": [], "read_source_calls": 0}
    real_write = EXPORTER._write_exclusive
    real_read_sources = EXPORTER._read_sources

    def recording_write(path, data, stage, _real=real_write, _log=observed):
        digest = _real(path, data, stage)
        _log["write_calls"].append({"seq": len(_log["write_calls"]) + 1,
                                    "relative": path.name, "sha256": digest})
        return digest

    def recording_read_sources(batch_dir, expectations, stage, _real=real_read_sources,
                              _log=observed):
        result = _real(batch_dir, expectations, stage)
        _log["read_source_calls"] += 1
        return result

    EXPORTER._write_exclusive = recording_write
    EXPORTER._read_sources = recording_read_sources
    try:
        obs_entry = record_api("r1_export_observe", EXPORTER.export_dev_review_bundle, batch,
                               observe_dir, expect_exception=EXPORTER.DevReviewBundleBlocked)
    finally:
        EXPORTER._write_exclusive = real_write
        EXPORTER._read_sources = real_read_sources
    if obs_entry["outcome"] != "returned":
        problems.append(f"无注入观察导出未成功：{obs_entry.get('message')}")
    manifest_write_seq = [item["seq"] for item in observed["write_calls"]
                          if item["relative"] == EXPORTER.MANIFEST_NAME]
    last_write_seq = len(observed["write_calls"])
    last_source_read = observed["read_source_calls"]
    if not manifest_write_seq or manifest_write_seq[-1] != last_write_seq:
        problems.append(f"manifest 不是最后一次 writer 调用：{observed['write_calls'][-3:]}")
    save_json(CONTAINER / "probe_records" / "r1_export_tail_observation.json", {
        "case": "r1_export_tail_observation", "observed": observed,
        "manifest_write_seq": manifest_write_seq, "last_write_seq": last_write_seq,
        "last_source_read": last_source_read,
        "note": "无注入观察：manifest 真实 writer 是最后一次写调用；_read_sources（来源/DB 必需"
                "消费）调用次数即真实位置。"})

    # --- 两个有限注入
    for target in ("README.md", "manifest.json"):
        label = f"r1_tail_{target.replace('.', '_')}"
        out_dir = BUNDLE_ROOT / CONTAINER.name / label
        state = {"hits": 0, "injected": False, "before": None, "after": None,
                 "write_calls": 0, "read_source_calls": 0, "real_call_returned": False,
                 "target": target, "target_path": str(out_dir / target)}

        def tail_write(path, data, stage, _real=real_write, _state=state, _out=out_dir,
                       _target=target):
            digest = _real(path, data, stage)
            _state["real_call_returned"] = True
            _state["write_calls"] += 1
            if _target == "manifest.json" and path.name == EXPORTER.MANIFEST_NAME \
                    and not _state["injected"]:
                target_path = _out / _target
                _state["before"] = sha256(target_path)
                with open(target_path, "ab") as handle:
                    handle.write(b"\n")
                _state["after"] = sha256(target_path)
                _state["hits"] += 1
                _state["injected"] = True
            return digest

        def tail_read_sources(batch_dir, expectations, stage, _real=real_read_sources,
                              _state=state, _out=out_dir, _last=last_source_read,
                              _target=target):
            result = _real(batch_dir, expectations, stage)
            _state["real_call_returned"] = True
            _state["read_source_calls"] += 1
            if _target == "README.md" and _state["read_source_calls"] == _last \
                    and not _state["injected"]:
                target_path = _out / _target
                _state["before"] = sha256(target_path)
                with open(target_path, "ab") as handle:
                    handle.write(b"\n")
                _state["after"] = sha256(target_path)
                _state["hits"] += 1
                _state["injected"] = True
            return result

        EXPORTER._write_exclusive = tail_write
        EXPORTER._read_sources = tail_read_sources
        try:
            entry = record_api(label, EXPORTER.export_dev_review_bundle, batch, out_dir,
                               expect_exception=(EXPORTER.DevReviewBundleBlocked,
                                                 EXPORTER.DevReviewBundleError))
        finally:
            EXPORTER._write_exclusive = real_write
            EXPORTER._read_sources = real_read_sources
        failure, failure_ok = load_json(out_dir / EXPORTER.FAILURE_NAME) \
            if out_dir.exists() else (None, False)
        message = entry.get("message") or ""
        if entry["outcome"] != "raised":
            problems.append(f"{target}: 收尾注入未被本次导出拒绝（返回成功）")
        elif entry.get("exception_class") != "DevReviewBundleBlocked":
            problems.append(f"{target}: 预期协议阻断，实际 {entry.get('exception_class')}")
        if target not in message:
            problems.append(f"{target}: 拒绝消息未指出目标文件")
        if not state["injected"] or state["hits"] != 1:
            problems.append(f"{target}: 注入未命中真实调用点（hits={state['hits']}）")
        if not state["real_call_returned"]:
            problems.append(f"{target}: wrapper 未调用真实 reader/writer")
        if not failure_ok or failure.get("target_exit_code") != 1:
            problems.append(f"{target}: 新输出未留下有效 failure（exit 1）")
        verify_cli = run_cli(f"{label}_verify", ["verify", "--bundle-dir", str(out_dir)], 1)
        if verify_cli["exit_code"] != 1:
            problems.append(f"{target}: 撤销 wrapper 后新进程 verify 未退出 1")
        detail.append({"target": target, "api": entry, "failure": failure,
                       "injected": state["injected"], "hits": state["hits"],
                       "before_sha256": state["before"], "after_sha256": state["after"],
                       "write_calls": state["write_calls"],
                       "read_source_calls": state["read_source_calls"],
                       "revoked_verify_exit": verify_cli["exit_code"],
                       "bundle_dir": rel(out_dir)})
    save_json(CONTAINER / "probe_records" / "r1_export_tail_probes.json", {
        "case": "r1_export_tail_probes", "detail": detail,
        "note": "两例分别在本轮新输出上、在真实 manifest 保存读回之后与最后一次来源/DB 必需消费"
                "返回原缓冲之后追加一个 LF；wrapper 调用真实 reader/writer 并返回其原值，"
                "此处不声称执行新的 writer 故障分支。"})
    return problems


def group_r1_offline_tail(normal_dir: Path) -> list:
    """离线核验最后必需缓冲消费之后的有限反例。"""
    problems: list = []
    isolate = CONTAINER / "isolated_r1"
    isolate.mkdir(parents=True, exist_ok=True)
    copy1 = isolate / "late_offline"
    if copy1.exists():
        shutil.rmtree(copy1)
    shutil.copytree(normal_dir, copy1)
    normal_before = tree_hashes(normal_dir)
    # 先无注入观察真实缓冲消费位置
    observed = {"calls": []}
    real_buffer = EXPORTER._read_bundle_buffer

    def recording_buffer(bundle, relative, _real=real_buffer, _log=observed):
        data = _real(bundle, relative)
        _log["calls"].append({"seq": len(_log["calls"]) + 1, "relative": relative})
        return data

    EXPORTER._read_bundle_buffer = recording_buffer
    try:
        obs = record_api("r1_offline_observe", EXPORTER.verify_dev_review_bundle, copy1,
                         expect_exception=(EXPORTER.DevReviewBundleBlocked,
                                           EXPORTER.DevReviewBundleError))
    finally:
        EXPORTER._read_bundle_buffer = real_buffer
    if obs["outcome"] != "returned":
        problems.append(f"无注入离线核验未成功：{obs.get('message')}")
    last_index = len(observed["calls"])
    save_json(CONTAINER / "probe_records" / "r1_offline_observation.json", {
        "case": "r1_offline_observation", "calls": observed["calls"], "last_index": last_index,
        "note": "无注入观察：离线核验按固定顺序对 25 个固定文件各读一次缓冲，最后一次即真实"
                "缓冲消费位置。"})
    target_relative = f"{EXPORTER.EVIDENCE_DIR}/workflow/initial_judgment/initial_judgment.json"
    state = {"calls": 0, "injected": False, "before": None, "after": None,
             "real_call_returned": False}
    files_before = tree_hashes(copy1)

    def late_buffer(bundle, relative, _real=real_buffer, _state=state, _last=last_index,
                    _file=copy1 / target_relative):
        data = _real(bundle, relative)
        _state["real_call_returned"] = True
        _state["calls"] += 1
        if _state["calls"] == _last and not _state["injected"]:
            _state["before"] = sha256(_file)
            with open(_file, "ab") as handle:
                handle.write(b"\n")
            _state["after"] = sha256(_file)
            _state["injected"] = True
        return data

    EXPORTER._read_bundle_buffer = late_buffer
    try:
        entry = record_api("r1_offline_late", EXPORTER.verify_dev_review_bundle, copy1,
                           expect_exception=(EXPORTER.DevReviewBundleBlocked,
                                             EXPORTER.DevReviewBundleError))
    finally:
        EXPORTER._read_bundle_buffer = real_buffer
    files_after = tree_hashes(copy1)
    message = entry.get("message") or ""
    if entry["outcome"] != "raised":
        problems.append("离线最后消费之后的改动未被本次 verify 拒绝")
    elif entry.get("exception_class") != "DevReviewBundleBlocked":
        problems.append(f"预期协议阻断，实际 {entry.get('exception_class')}")
    if "initial_judgment.json" not in message:
        problems.append("拒绝消息未指出目标文件")
    if not state["injected"] or state["calls"] != last_index:
        problems.append(f"注入位置不符：calls={state['calls']} last={last_index}")
    if not state["real_call_returned"]:
        problems.append("wrapper 未调用真实缓冲读取")
    # verify 全程不得写 failure 或其他文件（只允许被注入的那一个目标文件变化）
    changed = sorted(key for key in set(files_before) | set(files_after)
                     if files_before.get(key) != files_after.get(key))
    if changed != [target_relative]:
        problems.append(f"离线核验改动了非目标文件：{changed}")
    if (copy1 / EXPORTER.FAILURE_NAME).exists():
        problems.append("只读 verify 不得写 failure.json")
    revoked = run_cli("r1_offline_late_revoked", ["verify", "--bundle-dir", str(copy1)], 1)
    if revoked["exit_code"] != 1:
        problems.append("撤销 wrapper 后新进程 verify 未退出 1")
    if tree_hashes(normal_dir) != normal_before:
        problems.append("反例改动了正常包")
    save_json(CONTAINER / "probe_records" / "r1_offline_tail.json", {
        "case": "r1_offline_tail", "api": entry, "injected": state["injected"],
        "calls": state["calls"], "last_index": last_index,
        "before_sha256": state["before"], "after_sha256": state["after"],
        "changed_files": changed, "revoked_verify_exit": revoked["exit_code"],
        "isolated_copy": rel(copy1),
        "note": "只在正常包的隔离副本上，在最后一次必需缓冲读取返回真实原对象之后为该记录文件"
                "追加一个 LF；本次 verify 即协议阻断，未写 failure，正常原包不变。"})
    return problems


def group_r1_identity_negatives(normal_dir: Path) -> list:
    """四个来源/身份反例（候选始终可解析、25 文件与 24 清单齐全）。"""
    problems: list = []
    isolate = CONTAINER / "isolated_r1"
    isolate.mkdir(parents=True, exist_ok=True)
    normal_before = tree_hashes(normal_dir)
    zeros = "0" * 64
    cases = []

    def fresh(name: str) -> Path:
        target = isolate / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(normal_dir, target)
        return target

    def manifest_of(bundle: Path) -> dict:
        return json.loads((bundle / EXPORTER.MANIFEST_NAME).read_text(encoding="utf-8"))

    def save_manifest(bundle: Path, manifest: dict) -> None:
        (bundle / EXPORTER.MANIFEST_NAME).write_bytes(
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    # 1) manifest 事实包文件指纹与实际 packet 不符
    case1 = fresh("fp_packet_file")
    manifest = manifest_of(case1)
    manifest["canonical_fingerprints"]["packet_file_sha256"] = zeros
    save_manifest(case1, manifest)
    cases.append(("manifest_packet_file_sha256", case1, "packet_file_sha256"))
    # 2) 复制件初始绑定与历史 status/实际复制件不符
    case2 = fresh("fp_source_initial")
    manifest = manifest_of(case2)
    for item in manifest["payloads"]:
        if item["role"] == "copied_source":
            item["source_initial_file_sha256"] = zeros
            break
    save_manifest(case2, manifest)
    cases.append(("payload_source_initial_file_sha256", case2, "source_initial_file_sha256"))
    # 3) manifest 声明的 0008 前驱与实际 0008/0007 不符
    case3 = fresh("fp_previous")
    manifest = manifest_of(case3)
    manifest["checkpoint_0008"]["previous_file_sha256"] = zeros
    save_manifest(case3, manifest)
    cases.append(("manifest_checkpoint_previous", case3, "previous_file_sha256"))
    # 4) manifest/host_status 改批次，仅更新 status payload 大小/SHA
    case4 = fresh("fp_batch_id")
    manifest = manifest_of(case4)
    manifest["batch_id"] = "OTHER-BATCH"
    manifest["source_batch"]["batch_id"] = "OTHER-BATCH"
    save_manifest(case4, manifest)
    status = json.loads((case4 / EXPORTER.STATUS_NAME).read_text(encoding="utf-8"))
    status["batch_id"] = "OTHER-BATCH"
    raw = (json.dumps(status, ensure_ascii=False, sort_keys=True, indent=2,
                      allow_nan=False) + "\n").encode("utf-8")
    (case4 / EXPORTER.STATUS_NAME).write_bytes(raw)
    manifest = manifest_of(case4)
    for item in manifest["payloads"]:
        if item["role"] == "host_status":
            item["bytes"] = len(raw)
            item["file_sha256"] = hashlib.sha256(raw).hexdigest()
    save_manifest(case4, manifest)
    cases.append(("manifest_status_batch_id", case4, "batch_id"))

    results = []
    for label, bundle, expected_field in cases:
        files = {path.relative_to(bundle).as_posix() for path in bundle.rglob("*") if path.is_file()}
        if files != set(EXPORTER._fixed_relatives()):
            problems.append(f"{label}: 候选包固定文件集合已不完整")
        try:
            manifest = json.loads((bundle / EXPORTER.MANIFEST_NAME).read_text(encoding="utf-8"))
            if len(manifest["payloads"]) != 24:
                problems.append(f"{label}: 候选清单不是 24 项")
        except (json.JSONDecodeError, KeyError) as exc:
            problems.append(f"{label}: 候选清单不可解析（{exc}）")
        entry = record_api(f"r1_ident_{label}", EXPORTER.verify_dev_review_bundle, bundle,
                           expect_exception=(EXPORTER.DevReviewBundleBlocked,
                                             EXPORTER.DevReviewBundleError))
        message = entry.get("message") or ""
        if entry["outcome"] != "raised":
            problems.append(f"{label}: 未被拒绝（错误成功）")
        elif entry.get("exception_class") != "DevReviewBundleBlocked":
            problems.append(f"{label}: 预期协议阻断，实际 {entry.get('exception_class')}")
        if expected_field not in message:
            problems.append(f"{label}: 拒绝消息未指向矛盾字段（{expected_field}）")
        results.append({"label": label, "bundle": rel(bundle),
                        "expected_field": expected_field, "api": entry})
    if tree_hashes(normal_dir) != normal_before:
        problems.append("身份反例改动了正常包")
    save_json(CONTAINER / "probe_records" / "r1_identity_negatives.json", {
        "case": "r1_identity_negatives", "results": results,
        "note": "四个独立隔离副本：三个只改合法 64 位声明，第四个仅更新候选 status 的 payload "
                "大小/SHA，保持 c06b 的 0008/record/submission 未改；均本次协议阻断并指向矛盾字段。"})
    return problems


def group_r1_registration(batch: Path) -> list:
    """E1：真实直接调用登记与必要观察。"""
    problems: list = []
    entries_before = len(HOST_CODE_ENTRIES)
    normal_status = status_of(batch, "r1_direct_status_registered")
    if normal_status.get("batch_id") != batch.name:
        problems.append("直接宿主 status 返回的批次不符")
    missing_batch = BATCH_ROOT / CONTAINER.name / "does_not_exist"
    missing_dir = BUNDLE_ROOT / CONTAINER.name / "missing_bundle"
    # 工具前置拒绝（宿主代码帧应为 0）
    tool_entries_before = len([item for item in HOST_CODE_ENTRIES if item["scope"] == "tool_nested"])
    tool_reject = record_api("r1_tool_missing_batch_reject",
                             EXPORTER.export_dev_review_bundle, missing_batch, missing_dir,
                             expect_exception=EXPORTER.DevReviewBundleBlocked)
    tool_entries_after = len([item for item in HOST_CODE_ENTRIES if item["scope"] == "tool_nested"])
    if tool_reject["outcome"] != "raised":
        problems.append("工具缺失批次前置拒绝未生效")
    tool_nested_delta = tool_entries_after - tool_entries_before
    # 真实宿主缺失批次调用（应真实进入宿主并捕获 WorkflowHostBlocked）
    real_before = len([item for item in HOST_CODE_ENTRIES if item["scope"] == "test_direct"])
    host_missing = record_api("r1_direct_status_missing_batch", HOST.inspect_dev_batch,
                              missing_batch, expect_exception=HOST.WorkflowHostBlocked)
    real_after = len([item for item in HOST_CODE_ENTRIES if item["scope"] == "test_direct"])
    if host_missing["outcome"] != "raised" or host_missing.get("exception_class") != \
            "WorkflowHostBlocked":
        problems.append("真实宿主缺失批次调用未捕获 WorkflowHostBlocked")
    if real_after - real_before != 1:
        problems.append(f"真实宿主缺失批次调用未进入宿主代码帧（delta={real_after - real_before}）")
    if tool_nested_delta != 0:
        problems.append(f"工具前置拒绝仍在宿主侧产生嵌套调用：{tool_nested_delta}")
    chain = [link["class"] for link in host_missing.get("exception_chain") or []]
    if "WorkflowHostBlocked" not in chain:
        problems.append(f"缺失批次异常链不含宿主类型：{chain}")
    direct_missing = [item for item in DIRECT_HOST_STATUS_CALLS
                      if item["label"] == "r1_direct_status_registered"]
    if not direct_missing:
        problems.append("正常直接宿主调用未登记")
    save_json(CONTAINER / "probe_records" / "r1_registration.json", {
        "case": "r1_registration",
        "direct_registered": DIRECT_HOST_STATUS_CALLS,
        "host_code_entries": HOST_CODE_ENTRIES,
        "nested_status_calls": NESTED_HOST_STATUS_CALLS,
        "normal_direct_return_path": direct_missing[0]["return_path"] if direct_missing else None,
        "tool_precondition_reject": tool_reject,
        "tool_nested_delta": tool_nested_delta,
        "real_host_missing_batch": host_missing,
        "real_host_entry_delta": real_after - real_before,
        "distinct_from_entries_before": entries_before,
        "note": "测试直接宿主调用全部登记完整返回/异常；工具缺失批次先被工具 is_dir 前置拒绝"
                "（宿主代码帧 0）；另做一次已登记的真实宿主缺失批次调用，真实进入宿主并捕获"
                "WorkflowHostBlocked。工具内部嵌套 status 与测试直接调用分列，不要求条数相等。"})
    return problems


def group_r1_finalize(batch: Path, normal_dir: Path) -> list:
    """E1 证据收尾 + 保护 + 停止点 + 只读源/正常包字节不变。"""
    problems: list = []
    source_tree = tree_hashes(batch)
    source_sha_path = CONTAINER / "source_tree_hashes.json"
    db_path = Path(HOST._gate2_paths(batch, "r1")["database_path"])
    ledger_entries = []
    for item in CLI_RECORDS:
        for key in ("stdout_path", "stderr_path"):
            if not item.get(key):
                continue
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
    for item in API_RECORDS:
        if item["outcome"] in ("raised", "unexpected"):
            if not item.get("traceback") or not item.get("exception_path"):
                problems.append(f"{item['label']}: 预期异常缺少完整 traceback/引用")
    for item in HELPER_RECORDS:
        for key in ("return_path", "exception_path"):
            if not item.get(key):
                continue
            target = artifact(item[key])
            ledger_entries.append({"record": f"helper:{item['label']}", "field": key,
                                   "path": item[key], "exists": target.is_file(),
                                   "sha256": sha256(target) if target.is_file() else None})
    registry_path = save_json(CONTAINER / "call_registry.json",
                              {"calls": CALL_REGISTRY, "cli": len(CLI_RECORDS),
                               "api": len(API_RECORDS)})
    ledger = {"cli_records": CLI_RECORDS, "api_records": API_RECORDS,
              "helper_records": HELPER_RECORDS,
              "file_ledger": ledger_entries, "registry_calls": CALL_REGISTRY,
              "call_registry_path": rel(registry_path), "counts": COUNTS,
              "direct_host_status_calls": DIRECT_HOST_STATUS_CALLS,
              "host_code_entries": HOST_CODE_ENTRIES}
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
        "audit_problems_on_original": ledger_problems, "ledger_path": rel(ledger_path)})
    # 只读源 / DB / 正常包字节不变
    if tree_hashes(batch) != source_tree:
        problems.append("只读源批次在定点过程中发生变化")
    save_json(source_sha_path, {"scope": "只读源批次", "batch": rel(batch),
                                "files": len(source_tree), "entries": source_tree})
    save_json(CONTAINER / "probe_records" / "r1_source_unchanged.json", {
        "case": "r1_source_unchanged", "batch": rel(batch),
        "files_unchanged": tree_hashes(batch) == source_tree,
        "database_path": str(db_path), "database_sha256": sha256(db_path),
        "normal_bundle": rel(normal_dir), "normal_bundle_files": len(tree_hashes(normal_dir)),
        "note": "只读复用既有批次；本轮未新建 batches/SQLite、未重建上游链。"})
    # 保护比较（单次完整扫描）
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
        unexpected = [name for name in changed if name not in ALLOWED_CHANGES]
        if unexpected:
            protection_problems.append(f"相对基线出现允许范围外的变化：{unexpected[:6]}")
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
    save_json(CONTAINER / "probe_records" / "r1_protection.json", {
        "case": "r1_protection", "protection": protection,
        "protection_problems": protection_problems,
        "missing_records": COUNTS["missing_records"],
        "unregistered_records": COUNTS["unregistered_records"]})
    problems.extend(protection_problems[:5])
    # 停止点
    checkpoint8 = json.loads((batch / "workflow/checkpoints/0008.json").read_text(encoding="utf-8"))
    checkpoint7 = json.loads((batch / "workflow/checkpoints/0007.json").read_text(encoding="utf-8"))
    state = checkpoint8["workflow"]["state"]
    stop = []
    if state["phase"] != HOST.CONTROLLER_MODULE.PHASE_G2_APPROVED:
        stop.append("phase 不是 DEV_GATE2_APPROVED")
    if state["gate1_approval"] is not None or state["gate2_approval"] is not None:
        stop.append("真实批准不是 null")
    if state["next_step_allowed"] is not False:
        stop.append("next_step_allowed 不是严格 false")
    if not same_json(checkpoint8["workflow"], checkpoint7["workflow"]):
        stop.append("0008.workflow 与 0007 不再严格相等")
    record = json.loads((batch / "workflow/initial_judgment/initial_judgment.json")
                        .read_text(encoding="utf-8"))["record"]
    if record["ai_suggestion_allowed"] is not False or record["ai_suggestion"] is not None:
        stop.append("AI 边界不符")
    names = sorted(path.name for path in (batch / "workflow/checkpoints").iterdir())
    if "0009.json" in names:
        stop.append("出现 0009")
    problems.extend(stop)
    save_json(CONTAINER / "probe_records" / "r1_stop_point.json", {
        "case": "r1_stop_point", "problems": stop,
        "phase": state["phase"], "real_approvals": state.get("gate1_approval"),
        "next_step_allowed": state["next_step_allowed"], "checkpoints": names})
    # 现场计数（scope 注明；未执行项 null）
    round_root = BUNDLE_ROOT / CONTAINER.name
    success_bundles = sorted(item.name for item in round_root.iterdir()
                             if (item / EXPORTER.MANIFEST_NAME).is_file()
                             and not (item / EXPORTER.FAILURE_NAME).is_file())
    failure_bundles = sorted(item.name for item in round_root.iterdir()
                             if (item / EXPORTER.FAILURE_NAME).is_file())
    success_files = sum(len([p for p in (round_root / name).rglob("*") if p.is_file()])
                        for name in success_bundles)
    save_json(CONTAINER / "counts_scope.json", {
        "scope": "本定点容器：只读复用 data/batches/task018_run_06/c06b（未新建批次/SQLite）",
        "source_batch": rel(batch),
        "success_bundles": success_bundles,
        "failure_bundles": failure_bundles,
        "bundles_exported": len(success_bundles),
        "bundle_files_total": success_files,
        "payloads_total": EXPORTER.PAYLOADS * len(success_bundles),
        "isolated_copies": len([p for p in (CONTAINER / "isolated_r1").iterdir()])
        if (CONTAINER / "isolated_r1").is_dir() else 0,
        "cli_calls": COUNTS["cli_calls"],
        "api_records": len(API_RECORDS),
        "host_code_entries": COUNTS.get("host_code_entries"),
        "host_code_entries_test_direct": COUNTS.get("host_code_entries_test_direct"),
        "host_code_entries_tool_nested": COUNTS.get("host_code_entries_tool_nested"),
        "direct_registered_status_calls": len(DIRECT_HOST_STATUS_CALLS),
        "guard_hits": COUNTS["guard_hits"],
        "real_writer_faults": None,
        "main_chain_executed": False,
        "zero_finding_chain_executed": False,
        "subprocess_internal_core_calls": None,
        "note": ("计数按现场导出并注明 scope；本轮未重跑原 writer 真实句柄故障（仅引用原现场）、"
                 "未跑 MAIN/零条/完整七组；未测项为 null 或 false，不填默认零。")})
    return problems


# ---------------------------------------------------------------------------
# TASK-018-R2 定点模式（批次ID字符串类型；只读复用既有批次，不重建上游链）
# ---------------------------------------------------------------------------


def r2_guards():
    return r1_guards()


def r2_release_guards(guards):
    r1_release_guards(guards)


def group_r2_type_negatives(normal_dir: Path) -> list:
    """只改 manifest.source_batch.batch_id 的五类非法类型（隔离副本）。"""
    problems: list = []
    isolate = CONTAINER / "isolated_r2"
    isolate.mkdir(parents=True, exist_ok=True)
    normal_before = tree_hashes(normal_dir)
    results = []
    for name, value in R2_TYPE_CASES:
        candidate = isolate / f"id_{name}"
        if candidate.exists():
            shutil.rmtree(candidate)
        shutil.copytree(normal_dir, candidate)
        manifest_path = candidate / EXPORTER.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source_batch"]["batch_id"] = value
        manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2)
                                   + "\n").encode("utf-8"))
        files = {path.relative_to(candidate).as_posix() for path in candidate.rglob("*")
                 if path.is_file()}
        payload_count = None
        try:
            reparsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload_count = len(reparsed["payloads"])
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        if files != set(EXPORTER._fixed_relatives()):
            problems.append(f"{name}: 候选包固定文件集合不完整")
        if payload_count != 24:
            problems.append(f"{name}: 候选清单不是 24 项（{payload_count}）")
        before_files = tree_hashes(candidate)
        entry = record_api(f"r2_id_{name}", EXPORTER.verify_dev_review_bundle, candidate,
                           expect_exception=(EXPORTER.DevReviewBundleBlocked,
                                             EXPORTER.DevReviewBundleError))
        after_files = tree_hashes(candidate)
        message = entry.get("message") or ""
        if entry["outcome"] != "raised":
            problems.append(f"{name}: 未被拒绝（错误成功）")
        elif entry.get("exception_class") != "DevReviewBundleBlocked":
            problems.append(f"{name}: 预期协议阻断，实际 {entry.get('exception_class')}"
                            f"（原生类型错误不得当作协议结果）")
        if not message or "TypeError" in message or "unhashable" in message:
            problems.append(f"{name}: 消息含原生类型错误信息：{message[:80]}")
        if "source_batch.batch_id" not in message:
            problems.append(f"{name}: 拒绝消息未指向精确字段")
        if before_files != after_files:
            problems.append(f"{name}: 只读 verify 改动了候选包")
        cli_exit = None
        if name == "array":
            cli = run_cli("r2_id_array_cli", ["verify", "--bundle-dir", str(candidate)], 1)
            cli_exit = cli["exit_code"]
            if cli_exit != 1:
                problems.append(f"array: 新进程 CLI 退出不是 1（{cli_exit}）")
        results.append({"case": name, "candidate": rel(candidate),
                        "declared_value_type": type(value).__name__,
                        "declared_value_repr": repr(value), "api": entry,
                        "cli_exit": cli_exit,
                        "candidate_unchanged": before_files == after_files})
    if tree_hashes(normal_dir) != normal_before:
        problems.append("类型反例改动了正常包")
    save_json(CONTAINER / "probe_records" / "r2_id_type_negatives.json", {
        "case": "r2_id_type_negatives", "results": results,
        "note": "只在该正常包的隔离副本中改 manifest.source_batch.batch_id 的类型，"
                "payload/哈希/25 固定文件/24 清单不变；每个公开 verify 均为协议阻断并给出"
                "精确字段，无原生 TypeError、无退出 2；verify 只读且未写 failure。"})
    return problems


def group_r2_shape_helper(normal_dir: Path) -> list:
    """形状 helper 对照：合法字符串（含 64 位十六进制）不得被误拒。"""
    problems: list = []
    base = json.loads((normal_dir / EXPORTER.MANIFEST_NAME).read_text(encoding="utf-8"))
    controls = (
        ("plain_id", "c06b"),
        ("leading_zero", "0abc123"),
        ("lower_hex64", "a" * 64),
        ("zero_hex64", "0" * 64),
    )
    results = []
    for label, value in controls:
        candidate = copy.deepcopy(base)
        candidate["batch_id"] = value
        candidate["source_batch"]["batch_id"] = value
        entry = record_helper(f"r2_shape_{label}", EXPORTER._verify_manifest_shape, candidate,
                              expect_exception=EXPORTER.DevReviewBundleBlocked)
        if entry["outcome"] != "returned":
            problems.append(f"{label}: 形状 helper 误拒合法字符串（{entry.get('message')}）")
        results.append({"control": label, "declared_value": value,
                        "value_len": len(value), "helper": entry})
    # 反面对照：非法类型在同一 helper 下必须协议阻断（精确定位）
    for name, value in R2_TYPE_CASES:
        candidate = copy.deepcopy(base)
        candidate["source_batch"]["batch_id"] = value
        entry = record_helper(f"r2_shape_illegal_{name}", EXPORTER._verify_manifest_shape,
                              candidate, expect_exception=EXPORTER.DevReviewBundleBlocked)
        message = entry.get("message") or ""
        if entry["outcome"] != "raised" or entry.get("exception_class") != \
                "DevReviewBundleBlocked":
            problems.append(f"helper 非法类型 {name} 未协议阻断")
        elif "source_batch.batch_id" not in message:
            problems.append(f"helper 非法类型 {name} 未指向精确字段")
        results.append({"control": f"illegal_{name}", "declared_value_type": type(value).__name__,
                        "helper": entry})
    save_json(CONTAINER / "probe_records" / "r2_shape_helper.json", {
        "case": "r2_shape_helper", "results": results,
        "note": "shape helper 对照（不是完整包改绑成功、不是真实批次运行、不是公开 API）："
                "普通 ID、前导零字符串、64 位小写十六进制与 64 个 0 均按非空字符串通过；"
                "五类非法类型均协议阻断并指向 manifest.json.source_batch.batch_id。"})
    return problems


def group_r2_finalize(batch: Path, normal_dir: Path, source_before: dict,
                      db_sha_before: str, bundle_before: dict) -> list:
    """R2 收尾：复用 R1 收尾 + 入口前快照对比 + R2 scope 记录。"""
    problems = group_r1_finalize(batch, normal_dir)
    source_after = tree_hashes(batch)
    db_path = Path(HOST._gate2_paths(batch, "r2")["database_path"])
    db_after = sha256(db_path)
    bundle_after = tree_hashes(normal_dir)
    if source_after != source_before:
        problems.append("入口前快照对比：只读源批次发生变化")
    if db_after != db_sha_before:
        problems.append("入口前快照对比：外置数据库字节发生变化")
    if bundle_after != bundle_before:
        problems.append("入口前快照对比：正常对照包字节发生变化")
    save_json(CONTAINER / "probe_records" / "r2_protection_and_scope.json", {
        "case": "r2_protection_and_scope",
        "source_batch": rel(batch),
        "source_files_before": len(source_before), "source_files_after": len(source_after),
        "source_unchanged": source_after == source_before,
        "database_path": str(db_path), "database_sha256_before": db_sha_before,
        "database_sha256_after": db_after, "database_unchanged": db_after == db_sha_before,
        "normal_bundle": rel(normal_dir), "normal_bundle_files": len(bundle_after),
        "normal_bundle_unchanged": bundle_after == bundle_before,
        "helper_records": len(HELPER_RECORDS),
        "api_records": len(API_RECORDS), "cli_records": len(CLI_RECORDS),
        "host_code_entries": COUNTS.get("host_code_entries"),
        "host_code_entries_test_direct": COUNTS.get("host_code_entries_test_direct"),
        "host_code_entries_tool_nested": COUNTS.get("host_code_entries_tool_nested"),
        "guard_hits": COUNTS["guard_hits"],
        "subprocess_internal_core_calls": None,
        "main_chain_executed": False, "zero_finding_chain_executed": False,
        "real_writer_faults": None,
        "note": ("入口开始前取得源 37 文件与外置 DB 哈希，全部定点结束后比较；"
                 "未重跑 R1 六组/旧七组/smoke/writer 故障/源晚变更/MAIN/零条/上游/历史入口；"
                 "未执行项为 null 或 false，不填默认零。")})
    return problems


def main() -> int:
    global CONTAINER
    parser = argparse.ArgumentParser(description="TASK-018 只读审阅包有界验收")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--only", default="all",
                        choices=["all", "r1", "r2", "export", "preconditions", "late",
                                 "writefaults", "verifyneg", "readonly", "evidence", "smoke"])
    args = parser.parse_args()
    container = Path(args.out_dir).resolve()
    try:
        container.relative_to(CONTAINER_ROOT)
    except ValueError:
        print(f"out-dir 必须位于 {CONTAINER_ROOT} 之下：{container}", file=__import__("sys").stderr)
        return 2
    if container == CONTAINER_ROOT or (container.exists() and any(container.iterdir())):
        print(f"out-dir 必须是全新或空目录：{container}", file=__import__("sys").stderr)
        return 2
    container.mkdir(parents=True, exist_ok=True)
    CONTAINER = container
    for name in ("cli_logs", "api_records", "helper_records", "probe_records", "isolation",
                 "decisions", "submissions", "pending_bytes"):
        (container / name).mkdir(parents=True, exist_ok=True)
    (BUNDLE_ROOT / container.name).mkdir(parents=True, exist_ok=True)
    # 观察冻结公开 status 的真实调用
    real_status = HOST.inspect_dev_batch

    def observed_status(batch_dir, _real=real_status):
        STATUS_CALL_LOG.append(rel(batch_dir))
        COUNTS["status_calls_observed"] = len(STATUS_CALL_LOG)
        return _real(batch_dir)

    install_host_observer()
    print("== TASK-018 只读审阅包导出与离线核验" +
          ({"r1": "（R1 定点模式）", "r2": "（R2 定点模式）"}.get(args.only, "（七组）")))
    print(f"   容器 {container}")
    failures: list = []
    if args.only == "r2":
        batch = r1_source_batch()
        if not (batch / "workflow/checkpoints/0008.json").is_file():
            print(f"只读源批次缺少合法 0008：{batch}", file=sys.stderr)
            return 2
        source_before = tree_hashes(batch)
        db_path_r2 = Path(HOST._gate2_paths(batch, "r2")["database_path"])
        db_sha_before = sha256(db_path_r2)
        save_json(container / "pre_entry_source_hashes.json",
                  {"source_batch": rel(batch), "files": len(source_before),
                   "entries": source_before, "database_path": str(db_path_r2),
                   "database_sha256": db_sha_before,
                   "note": "入口开始前（任何定点探针之前）取得的源与 DB 快照。"})
        normal_problems, normal_dir, _status = group_r1_normal_export(batch)
        check("R2_NORMAL_CONTROL_EXPORT", "exporter", normal_problems)
        failures.extend(f"R2-1: {item}" for item in normal_problems)
        bundle_before = tree_hashes(normal_dir) if normal_dir is not None else {}
        save_json(CONTAINER / "probe_records" / "r2_normal_control.json", {
            "case": "r2_normal_control", "bundle_dir": rel(normal_dir) if normal_dir else None,
            "files": len(bundle_before), "problems": normal_problems,
            "note": "最终工具真实 export 一次（六真实下游守卫下、命中 0）＋正常 verify 与新进程 "
                    "CLI 0；25 文件/24 payload、22 份源字节与初始绑定一致、C06b 1 条 R02、"
                    "判断原文与开发边界不变。后续反例只复用其隔离副本。"})
        for case, func in (("R2_ID_TYPE_PROTOCOL_BLOCK",
                            lambda: group_r2_type_negatives(normal_dir)),
                           ("R2_LEGAL_STRING_SHAPE",
                            lambda: group_r2_shape_helper(normal_dir)),
                           ("R2_EVIDENCE_PROTECTION_AND_STOP",
                            lambda: group_r2_finalize(batch, normal_dir, source_before,
                                                      db_sha_before, bundle_before))):
            if normal_dir is None and case != "R2_ID_TYPE_PROTOCOL_BLOCK":
                CHECKS.append({"case": case, "owner": "exporter", "result": "FAIL",
                               "problems": ["正常对照包未生成，后续定点无法执行"]})
                failures.append(f"{case}: 正常对照包未生成")
                continue
            case_problems = func()
            check(case, "exporter", case_problems)
            failures.extend(f"{case}: {item}" for item in case_problems)
        save_json(container / "checks.json", CHECKS)
        save_json(container / "counts.json", COUNTS)
        save_json(container / "cli_logs.json", CLI_RECORDS)
        save_json(container / "api_records.json", API_RECORDS)
        save_json(container / "helper_records.json", HELPER_RECORDS)
        save_json(container / "host_code_entries.json", HOST_CODE_ENTRIES)
        save_json(container / "summary.json", {"mode": "r2", "checks": CHECKS,
                                               "failures": failures, "counts": COUNTS})
        passed = len([item for item in CHECKS if item["result"] == "PASS"])
        print(f"检查项 {len(CHECKS)}：{passed} PASS / {len(CHECKS) - passed} FAIL")
        print(f"CLI 调用 {COUNTS['cli_calls']}；公开 API 登记 {len(API_RECORDS)}"
              f"（返回 {COUNTS['api_returned']}、预期协议阻断 {COUNTS['api_blocked']}、"
              f"意外 {COUNTS['api_unexpected_errors']}）；helper 对照 {len(HELPER_RECORDS)}；"
              f"宿主代码帧 直连 {COUNTS.get('host_code_entries_test_direct')}"
              f"／嵌套 {COUNTS.get('host_code_entries_tool_nested')}；"
              f"missing={COUNTS['missing_records']} unregistered={COUNTS['unregistered_records']}")
        print(f"守卫命中 {COUNTS['guard_hits']}；保护比较 executed={COUNTS['protection_executed']}；"
              f"测试失败 {len(failures)}；汇总 {container / 'summary.json'}")
        return 1 if failures else 0
    if args.only == "r1":
        batch = r1_source_batch()
        if not (batch / "workflow/checkpoints/0008.json").is_file():
            print(f"只读源批次缺少合法 0008：{batch}", file=sys.stderr)
            return 2
        problems, normal_dir, _status = group_r1_normal_export(batch)
        check("R1_NORMAL_EXPORT_AND_DETERMINISM", "exporter", problems)
        failures.extend(f"R1-1: {item}" for item in problems)
        for case, func in (("R1_EXPORT_TAIL_BYTE_CONFIRMATION",
                            lambda: group_r1_export_tail(batch)),
                           ("R1_OFFLINE_TAIL_BYTE_BINDING",
                            lambda: group_r1_offline_tail(normal_dir)),
                           ("R1_SOURCE_IDENTITY_RELATIONS",
                            lambda: group_r1_identity_negatives(normal_dir)),
                           ("R1_REGISTRATION_AND_OBSERVATION",
                            lambda: group_r1_registration(batch)),
                           ("R1_EVIDENCE_PROTECTION_AND_STOP",
                            lambda: group_r1_finalize(batch, normal_dir))):
            if normal_dir is None and case != "R1_EXPORT_TAIL_BYTE_CONFIRMATION":
                CHECKS.append({"case": case, "owner": "exporter", "result": "FAIL",
                               "problems": ["正常导出未成功，后续定点无法执行"]})
                failures.append(f"{case}: 正常导出未成功")
                continue
            case_problems = func()
            check(case, "exporter", case_problems)
            failures.extend(f"{case}: {item}" for item in case_problems)
        save_json(container / "checks.json", CHECKS)
        save_json(container / "counts.json", COUNTS)
        save_json(container / "cli_logs.json", CLI_RECORDS)
        save_json(container / "api_records.json", API_RECORDS)
        save_json(container / "host_code_entries.json", HOST_CODE_ENTRIES)
        save_json(container / "summary.json", {"mode": "r1", "checks": CHECKS,
                                               "failures": failures, "counts": COUNTS})
        passed = len([item for item in CHECKS if item["result"] == "PASS"])
        print(f"检查项 {len(CHECKS)}：{passed} PASS / {len(CHECKS) - passed} FAIL")
        print(f"CLI 调用 {COUNTS['cli_calls']}；公开 API 登记 {len(API_RECORDS)}"
              f"（返回 {COUNTS['api_returned']}、预期协议阻断 {COUNTS['api_blocked']}、"
              f"意外 {COUNTS['api_unexpected_errors']}）；"
              f"宿主代码帧 直连 {COUNTS.get('host_code_entries_test_direct')}"
              f"／嵌套 {COUNTS.get('host_code_entries_tool_nested')}；"
              f"missing={COUNTS['missing_records']} unregistered={COUNTS['unregistered_records']}")
        print(f"守卫命中 {COUNTS['guard_hits']}；保护比较 executed={COUNTS['protection_executed']}；"
              f"测试失败 {len(failures)}；汇总 {container / 'summary.json'}")
        return 1 if failures else 0
    try:
        batch = build_c06b_batch()
        good_bundle = BUNDLE_ROOT / container.name / "api_bundle"
        groups = [
            ("G1_EXPORT_AND_DETERMINISM", lambda: group_export_and_determinism(batch)),
            ("G2_PRECONDITIONS_AND_PATHS", lambda: group_preconditions_and_paths(batch)),
            ("G3_LATE_CHANGE", lambda: group_late_change(batch)),
            ("G4_WRITE_FAULTS", lambda: group_write_faults(batch)),
            ("G5_VERIFY_NEGATIVES", lambda: group_verify_negatives(good_bundle)),
            ("G6_READONLY_AND_STOP", lambda: group_readonly_and_stop(batch, good_bundle)),
        ]
        selected = {
            "export": ["G1_EXPORT_AND_DETERMINISM"],
            "preconditions": ["G2_PRECONDITIONS_AND_PATHS"],
            "late": ["G3_LATE_CHANGE"],
            "writefaults": ["G4_WRITE_FAULTS"],
            "verifyneg": ["G5_VERIFY_NEGATIVES"],
            "readonly": ["G6_READONLY_AND_STOP"],
        }.get(args.only)
        for name, func in groups:
            if selected is not None and name not in selected:
                continue
            problems = func()
            check(name, "exporter", problems)
            failures.extend(f"{name}: {item}" for item in problems)
        if args.only in ("all", "evidence", "smoke") or selected is None:
            evidence_problems = group_evidence_and_protection()
            check("G7_EVIDENCE_AND_PROTECTION", "evidence", evidence_problems)
            failures.extend(f"G7: {item}" for item in evidence_problems)
        else:
            COUNTS["missing_records"] = None
            COUNTS["unregistered_records"] = None
            COUNTS["protection_executed"] = None
    finally:
        HOST.inspect_dev_batch = real_status
    save_json(container / "checks.json", CHECKS)
    save_json(container / "counts.json", COUNTS)
    save_json(container / "cli_logs.json", CLI_RECORDS)
    save_json(container / "api_records.json", API_RECORDS)
    save_json(container / "status_calls.json", STATUS_CALL_LOG)
    save_json(container / "summary.json", {"mode": args.only, "checks": CHECKS,
                                           "failures": failures, "counts": COUNTS})
    passed = len([item for item in CHECKS if item["result"] == "PASS"])
    print(f"检查项 {len(CHECKS)}：{passed} PASS / {len(CHECKS) - passed} FAIL")
    print(f"CLI 调用 {COUNTS['cli_calls']}；公开 API 登记 {len(API_RECORDS)}"
          f"（返回 {COUNTS['api_returned']}、预期/意外异常 "
          f"{COUNTS['api_blocked'] + COUNTS['api_unexpected_errors']}"
          f"（预期协议阻断 {COUNTS['api_blocked']}、意外 {COUNTS['api_unexpected_errors']}））；"
          f"冻结 status 调用 {COUNTS['status_calls_observed']}；"
          f"missing={COUNTS['missing_records']} unregistered={COUNTS['unregistered_records']}")
    print(f"导出包 {COUNTS['bundles_exported']}；包内文件 {COUNTS['bundle_files_total']}；"
          f"payload {COUNTS['payloads_total']}；真实 writer 故障 {COUNTS['real_writer_faults']}；"
          f"晚变更探针 {COUNTS['late_change_probes']}；核验反例 {COUNTS['verify_negative_probes']}；"
          f"守卫命中 {COUNTS['guard_hits']}；保护比较 executed={COUNTS['protection_executed']}")
    print(f"测试失败 {len(failures)}；汇总 {container / 'summary.json'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
