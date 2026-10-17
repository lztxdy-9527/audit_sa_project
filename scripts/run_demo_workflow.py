#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-015 开发态接收宿主：真实接收、Gate1 决定、标准化装载（Gate2 材料）、Gate2 模拟决定、
只读规则筛查、独立复算（复核凭证）与事实底稿（JSON＋Markdown＋0007），以及重启恢复。

固定对外接口（核心与 CLI 共用实现）：

    start_dev_batch(workbook_path, batch_dir, source_description) -> dict
    inspect_dev_batch(batch_dir) -> dict
    record_simulated_gate1_decision(batch_dir, decision) -> dict
    prepare_dev_gate2(batch_dir) -> dict
    record_simulated_gate2_decision(batch_dir, decision) -> dict
    screen_dev_batch(batch_dir) -> dict
    crosscheck_dev_batch(batch_dir) -> dict
    build_dev_fact_packet(batch_dir) -> dict

CLI 子命令（共八个）：

    run_demo_workflow.py start --workbook <xlsx> --batch-dir <new-dir> --source-description <原声明>
    run_demo_workflow.py status --batch-dir <existing-host-batch>
    run_demo_workflow.py record-simulated-decision --batch-dir <existing-host-batch> --decision-file <json>
    run_demo_workflow.py prepare-gate2 --batch-dir <existing-host-batch>
    run_demo_workflow.py record-simulated-gate2-decision --batch-dir <existing-host-batch> --decision-file <json>
    run_demo_workflow.py screen-rules --batch-dir <existing-host-batch>
    run_demo_workflow.py crosscheck-rules --batch-dir <existing-host-batch>
    run_demo_workflow.py build-fact-packet --batch-dir <existing-host-batch>

本宿主做开发态的**接收 → Gate1 决定 → 真实标准化与装载 → Gate2 决定 → 只读规则筛查 → 独立复算 →
事实底稿（JSON＋Markdown）**落盘与重启恢复：筛查真实调用冻结 `screen_sqlite`，复算真实调用冻结
`verify_rule_facts`，事实底稿真实调用冻结 `build_fact_packet`。
它不生成 AI 建议、不保存或预填人类判断，也不建立正式契约、不提供真实批准接口。
真实 `gate1_approval`／`gate2_approval` 恒为 null，`next_step_allowed=false`，
`mode=DEVELOPMENT_TEST_ONLY`，`contract_status=DRAFT_NOT_IN_FORCE`。

`build-fact-packet` 显式触发一次事实底稿构建（`screen-rules`／`crosscheck-rules`／`status` 都不会自动接着生成底稿）。
`start` 与 `prepare_dev_gate2` 分别通过子进程／直接 API 真实调用冻结的接收器、标准化器与装载器；
磁盘绑定由**宿主实测**，冻结控制器只负责比较与状态机。成功、质量阻断与运行失败都会保存宿主记录
（失败记录不含绑定与可批准请求）。模拟 Gate2 APPROVE 允许控制器声明筛查与复算可行，
但是否执行只由显式命令决定，宿主不会自动接着跑；`0007` 只表示事实底稿已持久化，
不表示审计完成、审计通过或底稿已批准。
异常：`WorkflowHostBlocked`（质量／协议／绑定／转移，退出码 1）与 `WorkflowHostError`（文件 I/O、
子进程或意外程序错误，退出码 2）。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BATCHES_ROOT = (PROJECT_ROOT / "data" / "batches").resolve()
HOST_VERSION = "TASK-017-workflow-host-1.1"
CHECKPOINT_VERSION = "TASK-012-checkpoint-1.0"
HOST_MANIFEST_VERSION = "TASK-012-host-manifest-1.0"
MODE = "DEVELOPMENT_TEST_ONLY"
RECEIVER_MODE = "DEVELOPMENT_ONLY"  # 冻结接收器自身声明的模式，不改上游
CONTRACT_STATUS = "DRAFT_NOT_IN_FORCE"
STATUS_READY = "READY"
STATUS_BLOCKED_QUALITY = "BLOCKED_QUALITY"
STATUS_FAILED_RUNTIME = "FAILED_RUNTIME"
STATUS_BLOCKED_PROTOCOL = "BLOCKED_PROTOCOL"
DECLARATION_ACQUIRED = "ACQUIRED"
DECLARATION_NOT_ACQUIRED = "NOT_ACQUIRED"
DECLARATION_CONTRADICTORY = "ACQUIRED_CONTRADICTORY"
RECEIVER_READY = "DEV_GATE1_PACKET_READY"
RECEIVER_BLOCKED = "BLOCKED_QUALITY"
RECEIVER_FAILED = "FAILED_RUNTIME"
RECEIVER = PROJECT_ROOT / "scripts" / "receive_demo_batch.py"
CONTROLLER = PROJECT_ROOT / "scripts" / "control_demo_workflow.py"
WORKFLOW_DIR = "workflow"
HOST_MANIFEST_NAME = "host_manifest.json"
CHECKPOINTS_DIR = "checkpoints"
RECEIVER_STDOUT = "receive.stdout.txt"
RECEIVER_STDERR = "receive.stderr.txt"
RECEIVE_INVOCATION = "receive_invocation.json"
GATE2_DIR = "gate2"
GATE2_NORMALIZED = "normalized.json"
GATE2_LOAD_REPORT = "load_report.json"
GATE2_ARTIFACTS = "artifacts.json"
GATE2_FAILURE = "failure.json"
GATE2_DATABASE_NAME = "audit.sqlite3"
GATE2_SQLITE_SUBDIR = "workflow_gate2"
GATE2_STAGING_SUFFIX = ".staging"
SCREEN_DIR = "screening"
SCREEN_START = "started.json"
SCREEN_REPORT = "screening_report.json"
SCREEN_ARTIFACTS = "artifacts.json"
SCREEN_FAILURE = "failure.json"
SCREEN_START_VERSION = "TASK-013-screen-start-1.0"
SCREEN_ARTIFACTS_VERSION = "TASK-013-screen-artifacts-1.0"
SCREEN_FAILURE_VERSION = "TASK-013-screen-failure-1.0"
SCREEN_STATUS_RECORDED = "RULE_SCREEN_RECORDED"
SCREEN_REPORT_REQUIRED_KEYS = ("batch_status", "mode", "next_step_allowed", "rule_core_version",
                               "rules", "cutoff_date", "period", "database_path",
                               "database_sha256_before", "database_sha256_after",
                               "database_unchanged", "read_only", "load_source",
                               "overall_reconciliation", "rule_hit_counts", "findings",
                               "statistics", "limits")
SCREEN_RUNTIME_FAILURE_CLASSES = ("WorkflowHostError", "RuleScreenError", "OSError")
CROSSCHECK_DIR = "crosscheck"
CROSSCHECK_START = "started.json"
CROSSCHECK_REPORT = "crosscheck_report.json"
CROSSCHECK_ARTIFACTS = "artifacts.json"
CROSSCHECK_FAILURE = "failure.json"
CROSSCHECK_START_VERSION = "TASK-014-crosscheck-start-1.0"
CROSSCHECK_ARTIFACTS_VERSION = "TASK-014-crosscheck-artifacts-1.0"
CROSSCHECK_FAILURE_VERSION = "TASK-014-crosscheck-failure-1.0"
CROSSCHECK_MATCHED_STATUS = "DEV_CROSSCHECK_MATCHED"
CROSSCHECK_MISMATCH_STATUS = "DEV_CROSSCHECK_MISMATCH"
CROSSCHECK_STATUS_RECORDED = "RULE_CROSSCHECK_RECORDED"
CROSSCHECK_MISMATCH_RESULT = "BLOCKED_CROSSCHECK"
CROSSCHECK_DIMENSIONS = ("hit_keys", "amounts_cents", "related_ids", "refund_facts", "rule_identity",
                         "source_entities", "source_rows", "counts", "statistics",
                         "overall_reconciliation")
CROSSCHECK_REPORT_REQUIRED_KEYS = ("crosscheck_version", "batch_status", "matched", "mode",
                                   "next_step_allowed", "period", "cutoff_date",
                                   "input_source_sha256", "normalized_payload_sha256",
                                   "screening_report_sha256", "rule_core_version_checked",
                                   "rule_recomputed_counts", "recomputed_facts", "observed_summary",
                                   "comparison", "differences", "method", "limits")
CROSSCHECK_RUNTIME_FAILURE_CLASSES = ("WorkflowHostError", "CrossCheckError", "OSError")
FACT_PACKET_DIR = "fact_packet"
FACT_PACKET_START = "started.json"
FACT_PACKET_JSON = "fact_packet.json"
FACT_PACKET_MARKDOWN = "fact_packet.md"
FACT_PACKET_ARTIFACTS = "artifacts.json"
FACT_PACKET_FAILURE = "failure.json"
FACT_PACKET_START_VERSION = "TASK-015-fact-packet-start-1.0"
FACT_PACKET_ARTIFACTS_VERSION = "TASK-015-fact-packet-artifacts-1.0"
FACT_PACKET_FAILURE_VERSION = "TASK-015-fact-packet-failure-1.0"
FACT_PACKET_STATUS_RECORDED = "FACT_PACKET_RECORDED"
FACT_PACKET_RUNTIME_FAILURE_CLASSES = ("WorkflowHostError", "FactPacketError", "OSError")
INITIAL_JUDGMENT_DIR = "initial_judgment"
INITIAL_JUDGMENT_START = "started.json"
INITIAL_JUDGMENT_SUBMISSION = "submission.json"
INITIAL_JUDGMENT_RECORD = "initial_judgment.json"
INITIAL_JUDGMENT_ARTIFACTS = "artifacts.json"
INITIAL_JUDGMENT_FAILURE = "failure.json"
INITIAL_JUDGMENT_START_VERSION = "TASK-017-initial-judgment-start-1.0"
INITIAL_JUDGMENT_ARTIFACTS_VERSION = "TASK-017-initial-judgment-artifacts-1.0"
INITIAL_JUDGMENT_FAILURE_VERSION = "TASK-017-initial-judgment-failure-1.0"
INITIAL_JUDGMENT_STATUS_RECORDED = "SIMULATED_INITIAL_JUDGMENT_RECORDED"
INITIAL_JUDGMENT_STAGE = "initial_judgment"
INITIAL_JUDGMENT_RUNTIME_FAILURE_CLASSES = ("WorkflowHostError", "InitialJudgmentError", "OSError")
INITIAL_JUDGMENT_START_REQUIRED_KEYS = (
    "start_version", "batch_id", "host_version", "operation_kind", "at_utc",
    "source_checkpoint_file_sha256", "host_manifest_file_sha256", "run_bindings_sha256",
    "core_path", "core_sha256", "core_version", "packet_file_sha256", "packet_sha256",
    "submission_file_sha256", "submission_canonical_sha256", "submission_event_id",
    "actor_kind", "simulation", "database_path", "database_sha256")
INITIAL_JUDGMENT_ARTIFACTS_REQUIRED_KEYS = (
    "artifacts_version", "batch_id", "host_version", "operation_kind", "core_path", "core_sha256",
    "core_version", "record_version", "initial_judgment_status", "record_sha256",
    "run_bindings_sha256", "host_manifest_file_sha256", "previous_checkpoint_file_sha256",
    "previous_checkpoint_relative", "packet_file_sha256", "packet_sha256",
    "submission_file_sha256", "submission_canonical_sha256", "submission_event_id",
    "actor_kind", "simulation", "database_path", "database_sha256",
    "started_relative", "started_file_sha256", "submission_relative",
    "initial_judgment_relative", "initial_judgment_file_sha256", "artifacts_relative",
    "findings_total", "next_step_allowed", "ai_suggestion_allowed",
    "ai_action_simulation_allowed", "gate1_approval", "gate2_approval",
    "human_initial_judgment", "ai_suggestion", "final_judgment", "created_at_utc")
FACT_PACKET_START_REQUIRED_KEYS = ("start_version", "batch_id", "host_version", "operation_kind",
                                   "at_utc", "source_checkpoint_file_sha256",
                                   "host_manifest_file_sha256", "run_bindings_sha256",
                                   "core_path", "core_sha256", "core_version",
                                   "normalized_file_sha256", "normalized_payload_sha256",
                                   "screening_report_file_sha256",
                                   "screening_report_canonical_sha256",
                                   "crosscheck_report_file_sha256",
                                   "crosscheck_report_canonical_sha256",
                                   "database_path", "database_sha256")
FACT_PACKET_ARTIFACTS_REQUIRED_KEYS = ("artifacts_version", "batch_id", "host_version",
                                       "operation_kind", "core_path", "core_sha256", "core_version",
                                       "packet_version", "fact_packet_status", "matched",
                                       "run_bindings_sha256", "host_manifest_file_sha256",
                                       "previous_checkpoint_file_sha256",
                                       "previous_checkpoint_relative",
                                       "normalized_file_sha256", "normalized_payload_sha256",
                                       "screening_report_file_sha256",
                                       "screening_report_canonical_sha256",
                                       "crosscheck_report_file_sha256",
                                       "crosscheck_report_canonical_sha256",
                                       "screening_artifacts_file_sha256",
                                       "crosscheck_artifacts_file_sha256",
                                       "gate2_normalized_file_sha256",
                                       "gate2_load_report_file_sha256",
                                       "gate2_artifacts_file_sha256",
                                       "database_path", "database_sha256",
                                       "gate2_decision_sha256", "period", "cutoff_date",
                                       "started_relative", "started_file_sha256",
                                       "packet_relative", "packet_file_sha256", "packet_sha256",
                                       "markdown_relative", "markdown_file_sha256",
                                       "findings_total", "rule_counts", "created_at_utc")
ARTIFACTS_VERSION = "TASK-012-gate2-artifacts-1.0"
FAILURE_VERSION = "TASK-012-gate2-failure-1.0"
RUNTIME_FAILURE_CLASSES = ("WorkflowHostError", "NormalizationError", "SqliteLoadError", "OSError")
OPERATION_START = "START_GATE1_REQUEST"
OPERATION_GATE1_DECISION = "SIMULATED_GATE1_DECISION"
OPERATION_PREPARE_GATE2 = "PREPARE_GATE2"
OPERATION_GATE2_DECISION = "SIMULATED_GATE2_DECISION"
OPERATION_RUN_RULE_SCREEN = "RUN_RULE_SCREEN"
OPERATION_RUN_RULE_CROSSCHECK = "RUN_RULE_CROSSCHECK"
OPERATION_BUILD_FACT_PACKET = "BUILD_FACT_PACKET"
OPERATION_RECORD_SIMULATED_INITIAL_JUDGMENT = "RECORD_SIMULATED_INITIAL_JUDGMENT"
LEGACY_MANIFEST_PREFIX = "TASK-010-"
NORMALIZER = PROJECT_ROOT / "scripts" / "normalize_demo_data.py"
STORE = PROJECT_ROOT / "scripts" / "store_demo_sqlite.py"
RECEIVER_TIMEOUT_SECONDS = 600
LEGAL_CHECKPOINT_NAMES = ("0001.json", "0002.json", "0003.json", "0004.json", "0005.json",
                          "0006.json", "0007.json", "0008.json")
HASH_PATTERN = re.compile(r"\A[0-9a-f]{64}\Z")

RECEIVER_MATERIALS = (
    ("snapshot", "source/input.xlsx"),
    ("quality_report", "checks/quality_report.json"),
    ("checker_stdout", "logs/checker.stdout.txt"),
    ("checker_stderr", "logs/checker.stderr.txt"),
    ("receiver_code", "code_snapshot/receive_demo_batch.py"),
    ("checker_code", "code_snapshot/check_demo_data.py"),
    ("receive_manifest", "batch_manifest.json"),
    ("gate1_packet", "gate1_packet.md"),
)
OPTIONAL_FAILURE_MATERIALS = ("snapshot", "quality_report", "checker_stdout", "checker_stderr",
                             "receive_manifest")
CONTROLLER_CODE_KEYS = (
    "control_demo_workflow", "receive_demo_batch", "check_demo_data", "normalize_demo_data",
    "store_demo_sqlite", "screen_demo_sqlite", "crosscheck_demo_rules", "build_demo_fact_packet",
)
CONTROLLER_CODE_PATHS = {
    "control_demo_workflow": "scripts/control_demo_workflow.py",
    "receive_demo_batch": "scripts/receive_demo_batch.py",
    "check_demo_data": "scripts/check_demo_data.py",
    "normalize_demo_data": "scripts/normalize_demo_data.py",
    "store_demo_sqlite": "scripts/store_demo_sqlite.py",
    "screen_demo_sqlite": "scripts/screen_demo_sqlite.py",
    "crosscheck_demo_rules": "scripts/crosscheck_demo_rules.py",
    "build_demo_fact_packet": "scripts/build_demo_fact_packet.py",
}
RULE_SQL_PATHS = {rule_id: f"sql/rules/{rule_id.lower()}.sql" for rule_id in ("R01", "R02", "R03", "R04")}
HOST_BOUND_PATHS = {
    "host_code": "scripts/run_demo_workflow.py",
    "schema": "sql/demo_schema.sql",
    "initial_judgment_core": "scripts/build_demo_initial_judgment.py",
}
DOC_BOUND_PATHS = {
    "spec_sha256": "docs/SPEC_V1.md",
    "contract_draft_sha256": "docs/AUDIT_CONTRACT_DRAFT.md",
}
GATE1_SCOPE_FIXED = {
    "company": "澄明商贸有限公司",
    "period_start": "2026-09-01",
    "period_end": "2026-09-30",
    "cutoff_date": "2026-09-30",
    "currency": "CNY",
    "synthetic_data": True,
}
RECEIVER_EXPECTED_SCOPE = {
    "company": "澄明商贸有限公司",
    "period_start": "2026-09-01",
    "period_end": "2026-09-30",
    "as_of_date": "2026-09-30",
    "currency": "CNY",
}
GATE1_LIMITATIONS = [
    "来源真实性与完整性未知：来源描述只是调用方声明，未被验证为事实。",
    "原 ERP 导出时间未知，未使用接收时间冒充导出时间。",
    "本地哈希只证明字节一致，不证明来源真实，也不抵御同权限篡改。",
    "本批次仅供开发态接收与 Gate1 暂停／恢复演示，不构成审计结论或 Gate 批准。",
]
EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_ERROR = 2


class WorkflowHostBlocked(Exception):
    """质量、协议、绑定或状态转移阻断（退出码 1）。"""

    def __init__(self, message: str, reasons: list | None = None, stage: str = ""):
        super().__init__(message)
        self.reasons = reasons or [message]
        self.stage = stage


class WorkflowHostError(Exception):
    """文件 I/O、子进程或意外程序错误（退出码 2）。"""

    def __init__(self, message: str, reasons: list | None = None, stage: str = ""):
        super().__init__(message)
        self.reasons = reasons or [message]
        self.stage = stage


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def canonical_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(payload) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_controller():
    spec = importlib.util.spec_from_file_location("host_frozen_controller", CONTROLLER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CONTROLLER_MODULE = _load_controller()


def _load_upstream_module(path: Path, name: str):
    """按文件路径加载冻结上游模块（不修改其代码，不复制其逻辑）。"""
    import importlib.util as _importlib_util

    spec = _importlib_util.spec_from_file_location(name, path)
    module = _importlib_util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


NORMALIZER_MODULE = _load_upstream_module(NORMALIZER, "host_frozen_normalizer")
STORE_MODULE = _load_upstream_module(STORE, "host_frozen_store")
SCREEN = PROJECT_ROOT / "scripts" / "screen_demo_sqlite.py"
SQLITE_TESTS_ROOT = Path(STORE_MODULE.SQLITE_TESTS_ROOT).resolve()
SCREEN_MODULE = _load_upstream_module(SCREEN, "host_frozen_screen")
SCREENING_CORE_PATH = PROJECT_ROOT / "scripts" / "screen_demo_sqlite.py"
SCREEN_CUTOFF_DATE = SCREEN_MODULE.SUPPORTED_CUTOFF_DATE
CROSSCHECK = PROJECT_ROOT / "scripts" / "crosscheck_demo_rules.py"
CROSSCHECK_MODULE = _load_upstream_module(CROSSCHECK, "host_frozen_crosscheck")
CROSSCHECK_CORE_PATH = PROJECT_ROOT / "scripts" / "crosscheck_demo_rules.py"
FACT_PACKET_CORE_PATH = PROJECT_ROOT / "scripts" / "build_demo_fact_packet.py"
FACT_PACKET_MODULE = _load_upstream_module(FACT_PACKET_CORE_PATH, "host_frozen_fact_packet")
INITIAL_JUDGMENT_CORE_PATH = PROJECT_ROOT / "scripts" / "build_demo_initial_judgment.py"
INITIAL_JUDGMENT_MODULE = _load_upstream_module(INITIAL_JUDGMENT_CORE_PATH,
                                                "host_frozen_initial_judgment")


def _require(condition: bool, path: str, reason: str, stage: str = "") -> None:
    if not condition:
        raise WorkflowHostBlocked(f"字段 {path} 不可用：{reason}", stage=stage)


def _require_str(value, path: str, stage: str = "") -> str:
    _require(isinstance(value, str), path, f"必须是字符串，实际 {type(value).__name__}", stage)
    _require(value.strip() != "", path, "不能为空白", stage)
    return value


def _require_hash(value, path: str, stage: str = "") -> str:
    _require(isinstance(value, str) and bool(HASH_PATTERN.fullmatch(value)), path,
             f"必须是完整 64 位十六进制哈希，实际 {value!r}", stage)
    return value


def _require_keys(payload: dict, keys, label: str, stage: str = "") -> None:
    for key in keys:
        _require(key in payload, f"{label}.{key}", "缺少必需键", stage)


def _read_json(path: Path, path_label: str, stage: str = "") -> dict:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise WorkflowHostError(f"读取失败 {path_label}：{exc}", stage=stage) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowHostBlocked(f"协议无效 {path_label}：JSON 无法解析（{exc}）", stage=stage) from exc
    _require(isinstance(payload, dict), path_label, f"必须是 JSON 对象，实际 {type(payload).__name__}", stage)
    return payload


def _read_json_with_bytes(path: Path, path_label: str, stage: str = "") -> tuple:
    """一次读取文件字节：用同一缓冲解析 JSON 并计算 SHA-256（二者绑定同一次读取）。

    异常类别、字段路径与异常链与 `_read_json` 保持一致。
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise WorkflowHostError(f"读取失败 {path_label}：{exc}", stage=stage) from exc
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowHostBlocked(f"协议无效 {path_label}：JSON 无法解析（{exc}）", stage=stage) from exc
    _require(isinstance(payload, dict), path_label,
             f"必须是 JSON 对象，实际 {type(payload).__name__}", stage)
    return payload, digest


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_batch_dir(raw, *, must_exist: bool, stage: str) -> Path:
    if isinstance(raw, Path):
        candidate = raw
    elif isinstance(raw, str):
        candidate = Path(raw).expanduser()
    else:
        raise WorkflowHostBlocked(f"字段 batch_dir 不可用：必须是字符串或 Path，实际 {type(raw).__name__}", stage=stage)
    candidate = candidate.resolve() if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
    try:
        candidate.relative_to(BATCHES_ROOT)
    except ValueError as exc:
        raise WorkflowHostBlocked(
            f"字段 batch_dir 不可用：批次必须位于 {BATCHES_ROOT} 之内（含重定向后），实际 {candidate}",
            stage=stage) from exc
    if candidate == BATCHES_ROOT:
        raise WorkflowHostBlocked(f"字段 batch_dir 不可用：不能是 data/batches 本身（{candidate}）", stage=stage)
    if must_exist:
        if not candidate.exists():
            raise WorkflowHostBlocked(f"字段 batch_dir 不可用：批次目录不存在（{candidate}）", stage=stage)
        if not candidate.is_dir():
            raise WorkflowHostBlocked(f"字段 batch_dir 不可用：不是目录（{candidate}）", stage=stage)
    elif candidate.exists():
        raise WorkflowHostBlocked(
            f"字段 batch_dir 不可用：目标已存在，不覆盖、不清空、不递归删除（{candidate}）", stage=stage)
    return candidate


# ---------------------------------------------------------------------------
# 磁盘绑定（宿主实测）
# ---------------------------------------------------------------------------


def _measure_bindings(batch_dir: Path) -> dict:
    """重新读取磁盘字节并计算哈希；宿主负责实测，控制器负责比较。"""
    bindings: dict = {}
    batch_snapshot = batch_dir / "source" / "input.xlsx"
    if not batch_snapshot.exists():
        raise WorkflowHostBlocked("绑定文件缺失：source/input.xlsx（批次快照）", stage="measure_bindings")
    try:
        bindings["input_sha256"] = file_sha256(batch_snapshot)
    except OSError as exc:
        raise WorkflowHostError(f"绑定文件不可读：source/input.xlsx（{exc}）", stage="measure_bindings") from exc
    for label, relative in DOC_BOUND_PATHS.items():
        path = PROJECT_ROOT / relative
        if not path.exists():
            raise WorkflowHostBlocked(f"绑定文件缺失：{relative}（{path}）", stage="measure_bindings")
        try:
            bindings[label] = file_sha256(path)
        except OSError as exc:
            raise WorkflowHostError(f"绑定文件不可读：{relative}（{exc}）", stage="measure_bindings") from exc
    code_sha256 = {}
    for key in CONTROLLER_CODE_KEYS:
        path = PROJECT_ROOT / CONTROLLER_CODE_PATHS[key]
        if not path.exists():
            raise WorkflowHostBlocked(f"绑定文件缺失：{CONTROLLER_CODE_PATHS[key]}", stage="measure_bindings")
        code_sha256[key] = file_sha256(path)
    bindings["code_sha256"] = code_sha256
    rule_sql = {}
    for rule_id, relative in RULE_SQL_PATHS.items():
        path = PROJECT_ROOT / relative
        if not path.exists():
            raise WorkflowHostBlocked(f"绑定文件缺失：{relative}", stage="measure_bindings")
        rule_sql[rule_id] = file_sha256(path)
    bindings["rule_sql_sha256"] = rule_sql
    bindings["config"] = copy.deepcopy(CONTROLLER_MODULE.FIXED_CONFIG)
    host_hashes = {}
    for key, relative in HOST_BOUND_PATHS.items():
        path = PROJECT_ROOT / relative
        if not path.exists():
            raise WorkflowHostBlocked(f"绑定文件缺失：{relative}", stage="measure_bindings")
        host_hashes[key] = file_sha256(path)
    bindings["host_code_sha256"] = host_hashes
    materials = {}
    for label, relative in RECEIVER_MATERIALS:
        path = batch_dir / relative
        if not path.exists():
            raise WorkflowHostBlocked(f"接收材料缺失：{relative}", stage="measure_bindings")
        materials[label] = {"path": relative, "sha256": file_sha256(path)}
    bindings["receive_materials"] = materials
    return bindings


def _material_infos(batch_dir: Path, labels=None, *, raise_on_unreadable: bool = True) -> dict:
    """按固定批次内路径读取材料声明；缺失时如实记为不存在，不补造。

    `raise_on_unreadable=False` 用于失败留痕：路径异常时如实记录，不因留痕本身失败而丢现场。
    """
    infos = {}
    for label, relative in RECEIVER_MATERIALS:
        if labels is not None and label not in labels:
            continue
        path = batch_dir / relative
        if path.exists() and path.is_file():
            try:
                infos[label] = {"path": relative, "exists": True, "sha256": file_sha256(path)}
            except OSError as exc:
                raise WorkflowHostError(
                    f"读取接收材料失败：{relative}（{type(exc).__name__}: {exc}）",
                    reasons=[f"path={relative}", f"{type(exc).__name__}: {exc}"],
                    stage="verify_receive") from exc
        else:
            if path.exists():
                note = f"{relative} 存在但不是普通文件（可能是目录），无法读取字节"
                if raise_on_unreadable:
                    raise WorkflowHostError(f"读取接收材料失败：{note}",
                                            reasons=[f"path={relative}", "路径不是普通文件"],
                                            stage="verify_receive")
                infos[label] = {"path": relative, "exists": False, "sha256": None, "note": note}
            else:
                infos[label] = {"path": relative, "exists": False, "sha256": None, "note": "路径不存在"}
    return infos


# ---------------------------------------------------------------------------
# 落盘：host_manifest 与 checkpoint
# ---------------------------------------------------------------------------


def _host_workflow_dir(batch_dir: Path) -> Path:
    return batch_dir / WORKFLOW_DIR


def _host_manifest_path(batch_dir: Path) -> Path:
    return _host_workflow_dir(batch_dir) / HOST_MANIFEST_NAME


def _checkpoints_dir(batch_dir: Path) -> Path:
    return _host_workflow_dir(batch_dir) / CHECKPOINTS_DIR


def _checkpoint_path(batch_dir: Path, revision: int) -> Path:
    return _checkpoints_dir(batch_dir) / f"{revision:04d}.json"


def _ensure_dir(path: Path, stage: str) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkflowHostError(f"无法创建目录 {path}：{exc}", stage=stage) from exc


def _write_exclusive_json(path: Path, payload: dict, stage: str) -> str:
    """独占创建、不覆盖；写完关闭后重新读回核验，才返回实际字节哈希。"""
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    try:
        with open(path, "x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except FileExistsError as exc:
        raise WorkflowHostBlocked(f"文件已存在，不覆盖：{path}", stage=stage) from exc
    except OSError as exc:
        raise WorkflowHostError(f"写入失败 {path}：{exc}", stage=stage) from exc
    try:
        readback = path.read_bytes()
    except OSError as exc:
        raise WorkflowHostError(f"写后读回失败（不宣称保存成功）：{path}（{exc}）", stage=stage) from exc
    if readback.decode("utf-8") != text:
        raise WorkflowHostError(f"写后读回内容不一致（不宣称保存成功）：{path}", stage=stage)
    parsed = json.loads(readback.decode("utf-8"))
    if canonical_json(parsed) != canonical_json(payload):
        raise WorkflowHostError(f"写后读回规范内容不一致（不宣称保存成功）：{path}", stage=stage)
    return hashlib.sha256(readback).hexdigest()


# ---------------------------------------------------------------------------
# 宿主恢复核验（status／record 共用）
# ---------------------------------------------------------------------------


def _require_success_manifest(manifest: dict, batch_dir: Path, stage: str) -> None:
    label = HOST_MANIFEST_NAME
    _require_keys(manifest, ("manifest_version", "host_version", "mode", "contract_status", "status",
                             "next_step_allowed", "gate1_approval", "gate2_approval", "batch_id",
                             "source", "receive", "bindings", "bindings_sha256", "gate1_request"),
                  label, stage)
    _require(manifest["manifest_version"] == HOST_MANIFEST_VERSION, f"{label}.manifest_version",
             f"必须是 {HOST_MANIFEST_VERSION}，实际 {manifest['manifest_version']!r}", stage)
    _require(manifest["host_version"] == HOST_VERSION, f"{label}.host_version",
             f"必须是 {HOST_VERSION}，实际 {manifest['host_version']!r}", stage)
    _require(manifest["mode"] == MODE, f"{label}.mode", f"必须是 {MODE}，实际 {manifest['mode']!r}", stage)
    _require(manifest["contract_status"] == CONTRACT_STATUS, f"{label}.contract_status",
             f"必须是 {CONTRACT_STATUS}，实际 {manifest['contract_status']!r}", stage)
    _require(manifest["status"] == STATUS_READY, f"{label}.status",
             f"必须是 {STATUS_READY}，实际 {manifest['status']!r}", stage)
    _require(manifest["next_step_allowed"] is False, f"{label}.next_step_allowed", "必须严格为 false", stage)
    _require(manifest["gate1_approval"] is None and manifest["gate2_approval"] is None, label,
             "真实批准字段必须存在且为 null", stage)
    _require(manifest["batch_id"] == batch_dir.name, f"{label}.batch_id",
             f"必须与批次目录叶子一致：{manifest['batch_id']!r} != {batch_dir.name!r}", stage)

    source = manifest["source"]
    _require(isinstance(source, dict), f"{label}.source", "必须是对象", stage)
    _require_keys(source, ("original_path", "file_name", "source_description"), f"{label}.source", stage)
    _require_str(source["source_description"], f"{label}.source.source_description", stage)
    receive = manifest["receive"]
    _require(isinstance(receive, dict), f"{label}.receive", "必须是对象", stage)
    _require_keys(receive, ("command", "exit_code", "batch_status", "invocation_record", "stdout_log",
                            "stderr_log", "materials"), f"{label}.receive", stage)
    _require(isinstance(receive["invocation_record"], dict), f"{label}.receive.invocation_record",
             "必须是对象", stage)
    invocation_path = batch_dir / WORKFLOW_DIR / RECEIVE_INVOCATION
    _require(receive["invocation_record"].get("path") == f"{WORKFLOW_DIR}/{RECEIVE_INVOCATION}",
             f"{label}.receive.invocation_record.path",
             f"必须是固定路径 {WORKFLOW_DIR}/{RECEIVE_INVOCATION}", stage)
    _require(invocation_path.exists(), f"{label}.receive.invocation_record",
             "调用记录文件必须存在", stage)
    _require(receive["invocation_record"].get("sha256") == file_sha256(invocation_path),
             f"{label}.receive.invocation_record.sha256", "必须等于调用记录文件实际字节哈希", stage)
    invocation = _read_invocation_record(batch_dir, stage)
    _require(invocation["command"] == receive["command"], f"{label}.receive.command",
             "必须与独立调用记录的真实命令完全一致", stage)
    _require(invocation["exit_code"] == receive["exit_code"], f"{label}.receive.exit_code",
             "必须与独立调用记录的真实退出码一致", stage)
    _require(receive["exit_code"] == 0, f"{label}.receive.exit_code",
             f"成功批次必须记录退出码 0，实际 {receive['exit_code']!r}", stage)
    _require(receive["batch_status"] == RECEIVER_READY, f"{label}.receive.batch_status",
             f"必须是 {RECEIVER_READY}，实际 {receive['batch_status']!r}", stage)
    command = receive["command"]
    _require(isinstance(command, list) and len(command) >= 3 and command[2] == str(RECEIVER),
             f"{label}.receive.command", "必须记录真实接收入口命令", stage)
    _require(isinstance(receive["materials"], dict), f"{label}.receive.materials", "必须是对象", stage)
    for material_label, relative in RECEIVER_MATERIALS:
        declared = receive["materials"].get(material_label)
        _require(isinstance(declared, dict), f"{label}.receive.materials.{material_label}", "必须是对象", stage)
        _require(declared.get("path") == relative, f"{label}.receive.materials.{material_label}.path",
                 f"必须是固定批次内路径 {relative}，实际 {declared.get('path')!r}", stage)
        actual = batch_dir / relative
        _require(actual.exists(), f"{label}.receive.materials.{material_label}",
                 f"声明的接收材料必须存在（{relative}）", stage)
        _require(_require_hash(declared.get("sha256"), f"{label}.receive.materials.{material_label}.sha256", stage)
                 == file_sha256(actual), f"{label}.receive.materials.{material_label}.sha256",
                 "必须与本批次实际字节一致", stage)
    bindings = manifest["bindings"]
    _require(isinstance(bindings, dict), f"{label}.bindings", "必须是对象", stage)
    _require_hash(manifest["bindings_sha256"], f"{label}.bindings_sha256", stage)
    _require(manifest["bindings_sha256"] == canonical_sha256(bindings), f"{label}.bindings_sha256",
             "必须等于清单实际 bindings 对象的规范指纹", stage)
    gate1_request = manifest["gate1_request"]
    _require(isinstance(gate1_request, dict), f"{label}.gate1_request", "必须是对象", stage)
    _require_keys(gate1_request, ("request_id", "materials_sha256", "scope"), f"{label}.gate1_request", stage)
    _require_str(gate1_request["request_id"], f"{label}.gate1_request.request_id", stage)
    _require_hash(gate1_request["materials_sha256"], f"{label}.gate1_request.materials_sha256", stage)
    _require(isinstance(gate1_request["scope"], dict), f"{label}.gate1_request.scope", "必须是对象", stage)
    _require(gate1_request["scope"].get("source_description") == source["source_description"],
             f"{label}.gate1_request.scope.source_description", "必须与来源声明一致", stage)


def _require_failure_manifest(manifest: dict, batch_dir: Path, stage: str) -> str:
    """失败清单核验：分别表达 receiver 实际结果与宿主自身结果。"""
    label = HOST_MANIFEST_NAME
    _require_keys(manifest, ("manifest_version", "host_version", "mode", "contract_status", "status",
                             "next_step_allowed", "gate1_approval", "gate2_approval", "batch_id",
                             "source", "receive", "host_result", "failure", "checkpoints"), label, stage)
    _require(manifest["manifest_version"] == HOST_MANIFEST_VERSION, f"{label}.manifest_version",
             f"必须是 {HOST_MANIFEST_VERSION}，实际 {manifest['manifest_version']!r}", stage)
    _require(manifest["host_version"] == HOST_VERSION, f"{label}.host_version",
             f"必须是 {HOST_VERSION}，实际 {manifest['host_version']!r}", stage)
    _require(manifest["mode"] == MODE, f"{label}.mode", f"必须是 {MODE}", stage)
    _require(manifest["contract_status"] == CONTRACT_STATUS, f"{label}.contract_status",
             f"必须是 {CONTRACT_STATUS}", stage)
    allowed_statuses = (STATUS_BLOCKED_QUALITY, STATUS_FAILED_RUNTIME, STATUS_BLOCKED_PROTOCOL)
    _require(manifest["status"] in allowed_statuses, f"{label}.status",
             f"必须是 {list(allowed_statuses)} 之一，实际 {manifest['status']!r}", stage)
    _require(manifest["next_step_allowed"] is False, f"{label}.next_step_allowed", "必须严格为 false", stage)
    _require(manifest["gate1_approval"] is None and manifest["gate2_approval"] is None, label,
             "真实批准字段必须存在且为 null", stage)
    _require(manifest["batch_id"] == batch_dir.name, f"{label}.batch_id",
             "必须与批次目录叶子一致", stage)
    _require("bindings" not in manifest, f"{label}.bindings",
             "失败批次不得含绑定或可批准请求", stage)
    _require(isinstance(manifest["checkpoints"], list) and not manifest["checkpoints"],
             f"{label}.checkpoints", "失败批次不得声明任何 checkpoint", stage)
    _require(not (batch_dir / WORKFLOW_DIR / CHECKPOINTS_DIR).exists(),
             f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}", "失败批次不得存在 checkpoint 目录", stage)

    receive = manifest["receive"]
    _require(isinstance(receive, dict), f"{label}.receive", "必须是对象", stage)
    _require_keys(receive, ("command", "exit_code", "batch_status", "invocation_record", "stdout_log",
                            "stderr_log", "materials"), f"{label}.receive", stage)
    _require(receive["exit_code"] in (0, 1, 2), f"{label}.receive.exit_code",
             f"必须记录 receiver 实际退出码 0／1／2，实际 {receive['exit_code']!r}", stage)
    _require_keys(receive, ("declaration_status", "declared_batch_status", "declared_exit_code",
                            "declaration_read_error"), f"{label}.receive", stage)
    declaration_status = receive["declaration_status"]
    _require(declaration_status in (DECLARATION_ACQUIRED, DECLARATION_NOT_ACQUIRED,
                                    DECLARATION_CONTRADICTORY), f"{label}.receive.declaration_status",
             f"必须是取得／未取得／已取得但矛盾之一，实际 {declaration_status!r}", stage)
    expected_pair = {0: RECEIVER_READY, 1: RECEIVER_BLOCKED, 2: RECEIVER_FAILED}[receive["exit_code"]]
    if declaration_status == DECLARATION_ACQUIRED:
        _require(receive["batch_status"] == expected_pair, f"{label}.receive.batch_status",
                 f"已取得声明时 receiver 退出码 {receive['exit_code']} 必须对应状态 {expected_pair}，"
                 f"实际 {receive['batch_status']!r}", stage)
        _require(receive["declared_exit_code"] == receive["exit_code"],
                 f"{label}.receive.declared_exit_code", "已取得声明必须与真实退出码一致", stage)
    elif declaration_status == DECLARATION_NOT_ACQUIRED:
        _require(receive["batch_status"] is None and receive["declared_batch_status"] is None,
                 f"{label}.receive.batch_status",
                 "未取得声明时必须如实记为 null（不得按退出码补造 READY）", stage)
        _require(isinstance(receive["declaration_read_error"], str)
                 and receive["declaration_read_error"] != "",
                 f"{label}.receive.declaration_read_error", "必须保存具体读取错误", stage)
    else:
        _require(receive["declared_batch_status"] is not None,
                 f"{label}.receive.declared_batch_status", "必须保留原样观察到的矛盾声明", stage)
        _require(receive["declared_batch_status"] != expected_pair
                 or receive["declared_exit_code"] != receive["exit_code"],
                 f"{label}.receive.declared_batch_status", "矛盾声明必须确实与真实结果不一致", stage)
        _require(manifest["host_result"]["layer"] == "RECEIVER"
                 or manifest["status"] == STATUS_BLOCKED_PROTOCOL,
                 f"{label}.receive.declaration_status",
                 "已取得但矛盾的声明必须归为宿主协议失败或接收器失败", stage)
    invocation = _read_invocation_record(batch_dir, stage)
    _require(invocation["exit_code"] == receive["exit_code"], f"{label}.receive.exit_code",
             "必须与调用记录的真实退出码一致（不得为表达宿主失败而篡写 receiver 结果）", stage)
    _require(invocation["command"] == receive["command"], f"{label}.receive.command",
             "必须与调用记录的真实命令完全一致", stage)
    _require(receive["invocation_record"]["sha256"] == file_sha256(
        batch_dir / WORKFLOW_DIR / RECEIVE_INVOCATION), f"{label}.receive.invocation_record.sha256",
             "必须等于调用记录文件实际字节哈希", stage)

    host_result = manifest["host_result"]
    _require(isinstance(host_result, dict), f"{label}.host_result", "必须是对象", stage)
    _require_keys(host_result, ("exit_code", "stage", "exception_class", "reasons", "layer"),
                  f"{label}.host_result", stage)
    _require(host_result["exit_code"] in (1, 2), f"{label}.host_result.exit_code",
             f"宿主结果必须是退出码 1 或 2，实际 {host_result['exit_code']!r}", stage)
    _require(host_result["layer"] in ("HOST", "RECEIVER"), f"{label}.host_result.layer",
             f"必须标明失败发生在 HOST 还是 RECEIVER 层，实际 {host_result['layer']!r}", stage)
    if host_result["layer"] == "RECEIVER":
        _require(host_result["exit_code"] == receive["exit_code"], f"{label}.host_result.exit_code",
                 "接收器层失败时宿主结果必须等于 receiver 实际退出码", stage)
        _require(manifest["status"] == (STATUS_BLOCKED_QUALITY if receive["exit_code"] == 1
                                        else STATUS_FAILED_RUNTIME), f"{label}.status",
                 "接收器层失败的宿主状态必须与 receiver 结果对应", stage)
    else:
        _require(receive["exit_code"] == 0, f"{label}.receive.exit_code",
                 "宿主层失败必须记录 receiver 实际退出码 0", stage)
        expected_status = (STATUS_FAILED_RUNTIME if host_result["exit_code"] == 2
                           else STATUS_BLOCKED_PROTOCOL)
        _require(manifest["status"] == expected_status, f"{label}.status",
                 f"宿主层退出码 {host_result['exit_code']} 必须对应状态 {expected_status}，"
                 f"实际 {manifest['status']!r}", stage)
    failure = manifest["failure"]
    _require(isinstance(failure, dict), f"{label}.failure", "必须是对象", stage)
    _require_keys(failure, ("stage", "reasons"), f"{label}.failure", stage)
    _require(isinstance(failure["reasons"], list) and failure["reasons"], f"{label}.failure.reasons",
             "必须保存实际失败原因", stage)
    return manifest["status"]


def _reject_legacy_version(manifest: dict, stage: str) -> None:
    version = manifest.get("manifest_version")
    if isinstance(version, str) and version.startswith(LEGACY_MANIFEST_PREFIX):
        raise WorkflowHostBlocked(
            f"该批次由旧宿主版本创建（manifest_version={version!r}）：本版本只接收自己创建的新批次，"
            "不修改、不迁移、不重签，也不替旧产物补建批准；请用本版本新建批次。", stage=stage)


def _load_host_manifest(batch_dir: Path, stage: str) -> tuple:
    path = _host_manifest_path(batch_dir)
    if not path.exists():
        raise WorkflowHostBlocked(
            f"该批次不是本宿主创建的：缺少 {WORKFLOW_DIR}/{HOST_MANIFEST_NAME}"
            "（不接管旧接收批次，也不为历史产物追认批准）", stage=stage)
    manifest = _read_json(path, f"{WORKFLOW_DIR}/{HOST_MANIFEST_NAME}", stage)
    _reject_legacy_version(manifest, stage)
    _require("status" in manifest, f"{HOST_MANIFEST_NAME}.status",
             "缺少宿主状态字段（本版本必须显式声明成功或失败）", stage)
    return manifest, file_sha256(path)


def _load_checkpoint_chain(batch_dir: Path, manifest: dict, manifest_file_sha256: str,
                           measured_bindings: dict, stage: str) -> dict:
    """读取并核验完整 checkpoint 链：枚举、形状、序号、前序哈希、操作协议与状态延续。"""
    directory = _checkpoints_dir(batch_dir)
    if not directory.exists():
        raise WorkflowHostBlocked(f"缺少 checkpoint 目录：{WORKFLOW_DIR}/{CHECKPOINTS_DIR}", stage=stage)
    entries = sorted(directory.iterdir(), key=lambda item: item.name)
    names = [entry.name for entry in entries]
    for entry in entries:
        _require(entry.is_file() and entry.name in LEGAL_CHECKPOINT_NAMES,
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{entry.name}",
                 f"本宿主只接受 {list(LEGAL_CHECKPOINT_NAMES)}，拒绝未知项（含半文件与目录）", stage)
    _require(names == list(LEGAL_CHECKPOINT_NAMES[:len(names)]), f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}",
             f"checkpoint 必须从 0001.json 起连续，实际 {names}", stage)
    _require(1 <= len(names) <= 8, f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}",
             f"成功批次的 checkpoint 只能是 0001 起的连续 1—8 份（最多 0008），实际 {names}", stage)

    checkpoints: list = []
    previous_hash = None
    previous_payload = None
    gate2_expected = None
    screen_expected = None
    crosscheck_expected_chain = None
    fact_packet_expected_chain = None
    initial_judgment_expected_chain = None
    for index, entry in enumerate(entries, start=1):
        label = f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{entry.name}"
        # 初始字节与哈希来自同一次读取；后续全部以该初始 SHA 为预期值
        payload, initial_file_sha256 = _read_json_with_bytes(entry, label, stage)
        _require_keys(payload, ("checkpoint_version", "revision", "previous_file_sha256", "batch_id",
                               "host_manifest_file_sha256", "workflow", "operation"), label, stage)
        _require(payload["checkpoint_version"] == CHECKPOINT_VERSION, f"{label}.checkpoint_version",
                 f"必须是 {CHECKPOINT_VERSION}，实际 {payload['checkpoint_version']!r}", stage)
        revision = payload["revision"]
        _require(isinstance(revision, int) and not isinstance(revision, bool), f"{label}.revision",
                 f"必须是整数，实际 {type(revision).__name__}", stage)
        _require(revision == index, f"{label}.revision", f"必须等于文件序号 {index}", stage)
        _require(payload["previous_file_sha256"] == previous_hash, f"{label}.previous_file_sha256",
                 f"必须等于前一份 checkpoint 的实际字节哈希：{payload['previous_file_sha256']!r} != "
                 f"{previous_hash!r}", stage)
        _require(payload["batch_id"] == batch_dir.name, f"{label}.batch_id",
                 f"必须与批次目录叶子一致，实际 {payload['batch_id']!r}", stage)
        _require(payload["host_manifest_file_sha256"] == manifest_file_sha256,
                 f"{label}.host_manifest_file_sha256",
                 "必须等于宿主清单的实际文件字节哈希", stage)
        workflow = payload["workflow"]
        _require(isinstance(workflow, dict) and set(workflow.keys()) == {"state", "state_sha256"},
                 f"{label}.workflow", "必须是 {state, state_sha256}", stage)
        state = workflow["state"]
        _require(isinstance(state, dict), f"{label}.workflow.state",
                 f"必须是对象，实际 {type(state).__name__}", stage)
        _require_keys(state, ("batch_id", "run_bindings", "run_bindings_sha256", "phase", "requests",
                             "simulated_decisions", "history", "gate1_approval", "gate2_approval",
                             "next_step_allowed", "mode"), f"{label}.workflow.state", stage)
        _require(canonical_sha256(state) == workflow["state_sha256"], f"{label}.workflow.state_sha256",
                 "必须等于 state 的规范指纹", stage)
        try:
            CONTROLLER_MODULE.check_dev_action(workflow, "NORMALIZE_AND_LOAD",
                                               current_bindings=state["run_bindings"])
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"checkpoint {entry.name} 未通过冻结控制器历史校验：{exc}",
                                      stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"checkpoint {entry.name} 校验出现意外错误：{exc}", stage=stage) from exc
        operation = payload["operation"]
        _require(isinstance(operation, dict), f"{label}.operation", "必须是对象", stage)
        _require_keys(operation, ("kind", "at_utc"), f"{label}.operation", stage)
        if index == 1:
            _verify_start_operation(payload, manifest, state, label, stage, batch_dir)
        elif index == 2:
            _verify_decision_operation(payload, previous_payload, state, measured_bindings, label, stage)
        elif index == 3:
            gate2_expected = _verify_prepare_operation(
                payload, previous_payload, state, measured_bindings, label, stage,
                batch_dir, manifest, previous_file_sha256=previous_hash)
        elif index == 4:
            _verify_gate2_decision_operation(
                payload, previous_payload, state, measured_bindings, label, stage,
                batch_dir, manifest, previous_file_sha256=previous_hash, gate2_expected=gate2_expected)
        elif index == 5:
            screen_expected = _verify_screen_operation(
                payload, previous_payload, state, label, stage, batch_dir, manifest,
                previous_file_sha256=previous_hash, gate2_expected=gate2_expected,
                host_manifest_file_sha256=manifest_file_sha256)
        elif index == 6:
            # 0006：复算凭证。0005 的语义仍按它自己的初始哈希核验（不得误用链尾 0007 的哈希）。
            crosscheck_expected_chain = _verify_crosscheck_operation(
                payload, previous_payload, state, label, stage, batch_dir, manifest,
                previous_file_sha256=previous_hash, screen_expected=screen_expected,
                host_manifest_file_sha256=manifest_file_sha256)
        elif index == 7:
            # 0007：事实底稿凭证。0006 的语义仍按它自己的初始哈希核验。
            fact_packet_expected_chain = _verify_fact_packet_operation(
                payload, previous_payload, state, label, stage, batch_dir, manifest,
                previous_file_sha256=previous_hash,
                upstream_expected=crosscheck_expected_chain,
                host_manifest_file_sha256=manifest_file_sha256)
        else:
            # 0008：模拟初判凭证。0007 的语义仍按它自己的初始哈希与 operation 核验。
            initial_judgment_expected_chain = _verify_initial_judgment_operation(
                payload, previous_payload, state, label, stage, batch_dir, manifest,
                previous_file_sha256=previous_hash,
                upstream_expected=fact_packet_expected_chain,
                host_manifest_file_sha256=manifest_file_sha256)
        checkpoints.append({"name": entry.name, "revision": revision, "payload": payload,
                            "file_sha256": initial_file_sha256})
        previous_hash = checkpoints[-1]["file_sha256"]
        previous_payload = payload
    # 收尾复测：所有控制器调用结束后，逐份复测 checkpoint 磁盘字节必须仍等于初始读取值
    for item in checkpoints:
        path = _checkpoint_path(batch_dir, item["revision"])
        label = f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}"
        try:
            actual = file_sha256(path)
        except OSError as exc:
            raise WorkflowHostBlocked(
                f"字段 {label} 不可用：收尾复测无法读取 checkpoint 字节（{exc}）；"
                f"预期 {item['file_sha256']}", stage=stage) from exc
        _require(actual == item["file_sha256"], label,
                 f"收尾复测发现 checkpoint 字节在本次读取之后发生变化："
                 f"预期（初始读取）{item['file_sha256']}，实际 {actual}", stage)
    current = checkpoints[-1]
    return {"checkpoints": checkpoints, "current": current,
            "current_path": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{current['name']}",
            "current_file_sha256": current["file_sha256"], "names": names,
            "gate2_expected": gate2_expected, "screen_expected": screen_expected,
            "crosscheck_expected": crosscheck_expected_chain,
            "fact_packet_expected": fact_packet_expected_chain,
            "initial_judgment_expected": initial_judgment_expected_chain}


def _verify_start_operation(payload: dict, manifest: dict, state: dict, label: str, stage: str,
                            batch_dir: Path) -> None:
    operation = payload["operation"]
    _require(operation.get("kind") == "START_GATE1_REQUEST", f"{label}.operation.kind",
             f"0001 必须是 START_GATE1_REQUEST，实际 {operation.get('kind')!r}", stage)
    _require_keys(operation, ("receiver_exit_code", "receiver_command", "bindings_sha256", "request_id"),
                  f"{label}.operation", stage)
    _require(operation["receiver_exit_code"] == 0, f"{label}.operation.receiver_exit_code",
             "成功批次必须记录接收退出码 0", stage)
    invocation = _read_invocation_record(batch_dir, stage)
    saved_command = invocation["command"]
    recorded_command = operation["receiver_command"]
    _require(isinstance(recorded_command, list), f"{label}.operation.receiver_command",
             f"必须是完整命令参数列表，实际 {type(recorded_command).__name__}", stage)
    _require(len(recorded_command) == len(saved_command), f"{label}.operation.receiver_command",
             f"参数个数必须与真实调用记录一致：{len(recorded_command)} != {len(saved_command)}", stage)
    for index, (recorded, saved) in enumerate(zip(recorded_command, saved_command)):
        _require(type(recorded) is type(saved), f"{label}.operation.receiver_command[{index}]",
                 f"参数类型必须与真实调用记录一致：{type(recorded).__name__} != {type(saved).__name__}",
                 stage)
        _require(recorded == saved, f"{label}.operation.receiver_command[{index}]",
                 f"参数必须与真实调用记录逐项一致（不转换、不 strip）：{recorded!r} != {saved!r}", stage)
    _require(operation["receiver_command"] == manifest["receive"]["command"],
             f"{label}.operation.receiver_command", "必须与宿主清单保存的真实接收命令一致", stage)
    _require(operation["bindings_sha256"] == manifest["bindings_sha256"],
             f"{label}.operation.bindings_sha256", "必须与宿主清单绑定指纹一致", stage)
    _require(state["phase"] == CONTROLLER_MODULE.PHASE_G1_PENDING, f"{label}.workflow.state.phase",
             f"0001 必须是 Gate1 pending，实际 {state['phase']!r}", stage)
    _require(state["simulated_decisions"] == [], f"{label}.workflow.state.simulated_decisions",
             "0001 不得含模拟决定", stage)
    _require(state["requests"][CONTROLLER_MODULE.GATE2] is None, f"{label}.workflow.state.requests.GATE2",
             "0001 不得含 Gate2 请求", stage)
    _require(state["batch_id"] == payload["batch_id"], f"{label}.workflow.state.batch_id",
             "workflow 批次必须与 checkpoint 一致", stage)
    _require(state["run_bindings_sha256"] == manifest["bindings_sha256"],
             f"{label}.workflow.state.run_bindings_sha256", "workflow 绑定必须与宿主清单一致", stage)
    _require(state["run_bindings"] == manifest["bindings"], f"{label}.workflow.state.run_bindings",
             "workflow 创建绑定必须与宿主清单绑定逐项一致", stage)
    request = state["requests"][CONTROLLER_MODULE.GATE1]
    _require(isinstance(request, dict), f"{label}.workflow.state.requests.GATE1", "必须是对象", stage)
    _require(operation["request_id"] == request["request_id"], f"{label}.operation.request_id",
             "操作摘要的请求必须与 workflow 实际请求一致", stage)
    declared = manifest["gate1_request"]
    _require(declared["request_id"] == request["request_id"], f"{HOST_MANIFEST_NAME}.gate1_request.request_id",
             f"必须与 0001 实际请求一致：{declared['request_id']!r} != {request['request_id']!r}", stage)
    _require(declared["materials_sha256"] == request["materials_sha256"],
             f"{HOST_MANIFEST_NAME}.gate1_request.materials_sha256",
             "必须与 0001 实际请求材料指纹一致", stage)
    _require(canonical_json(declared["scope"]) == canonical_json(request["materials"]["scope"]),
             f"{HOST_MANIFEST_NAME}.gate1_request.scope", "必须与 0001 实际请求范围一致", stage)


def _verify_decision_operation(payload: dict, previous_payload: dict, state: dict,
                               measured_bindings: dict, label: str, stage: str) -> None:
    operation = payload["operation"]
    _require(operation.get("kind") == "SIMULATED_GATE1_DECISION", f"{label}.operation.kind",
             f"0002 必须是 SIMULATED_GATE1_DECISION，实际 {operation.get('kind')!r}", stage)
    _require_keys(operation, ("decision", "decision_sha256", "phase_after", "bindings_sha256"),
                  f"{label}.operation", stage)
    recorded = operation["decision"]
    _require(isinstance(recorded, dict), f"{label}.operation.decision", "必须是对象", stage)
    _require_keys(recorded, (*CONTROLLER_MODULE.REQUIRED_DECISION_KEYS, "decision_sha256"),
                  f"{label}.operation.decision", stage)
    body = {key: value for key, value in recorded.items() if key != "decision_sha256"}
    actual_body_sha = canonical_sha256(body)
    _require(recorded["decision_sha256"] == actual_body_sha, f"{label}.operation.decision.decision_sha256",
             "必须等于决定正文（剥离派生字段）的实际规范指纹", stage)
    _require(operation["decision_sha256"] == actual_body_sha, f"{label}.operation.decision_sha256",
             "必须等于决定正文的实际规范指纹", stage)
    stored = state["simulated_decisions"]
    _require(isinstance(stored, list) and len(stored) == 1, f"{label}.workflow.state.simulated_decisions",
             f"0002 必须恰含本次一个决定，实际 {len(stored) if isinstance(stored, list) else stored!r}", stage)
    _require(canonical_json(stored[0]) == canonical_json(recorded), f"{label}.workflow.state.simulated_decisions",
             "workflow 存放的决定必须与操作摘要完整决定一致", stage)
    _require(state["phase"] in (CONTROLLER_MODULE.APPROVED_PHASE[CONTROLLER_MODULE.GATE1],
                               CONTROLLER_MODULE.HELD_PHASE[CONTROLLER_MODULE.GATE1],
                               CONTROLLER_MODULE.REJECTED_PHASE[CONTROLLER_MODULE.GATE1]),
             f"{label}.workflow.state.phase",
             f"0002 只允许 Gate1 APPROVED／HELD／REJECTED，实际 {state['phase']!r}", stage)
    _require(operation["phase_after"] == state["phase"], f"{label}.operation.phase_after",
             "操作摘要的 phase 必须与实际状态一致", stage)
    _require(state["requests"][CONTROLLER_MODULE.GATE2] is None, f"{label}.workflow.state.requests.GATE2",
             "0002 不得进入 Gate2", stage)
    _require(operation["bindings_sha256"] == state["run_bindings_sha256"],
             f"{label}.operation.bindings_sha256", "必须与 workflow 绑定一致", stage)
    # 0002 必须是 0001 的合法延续：用冻结控制器复算完整预期返回
    base_workflow = previous_payload["workflow"]
    try:
        expected = CONTROLLER_MODULE.record_dev_decision(base_workflow, copy.deepcopy(body),
                                                        current_bindings=measured_bindings)
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        raise WorkflowHostBlocked(
            f"checkpoint {label} 不是 0001 的合法延续：冻结控制器阻断该决定（{exc}）", stage=stage) from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        raise WorkflowHostError(f"checkpoint {label} 延续复算出现意外错误：{exc}", stage=stage) from exc
    _require(canonical_json(expected["state"]) == canonical_json(state), f"{label}.workflow.state",
             "0002 的 state 必须等于由 0001 与本次决定复算得到的完整预期结果", stage)
    base_history = base_workflow["state"]["history"]
    _require(state["history"][:len(base_history)] == base_history, f"{label}.workflow.state.history",
             "0002 必须保留 0001 的全部历史前缀", stage)
    _require(canonical_json(state["requests"][CONTROLLER_MODULE.GATE1])
             == canonical_json(base_workflow["state"]["requests"][CONTROLLER_MODULE.GATE1]),
             f"{label}.workflow.state.requests.GATE1", "0002 必须保留 0001 的 Gate1 请求", stage)


def _gate2_dir(batch_dir: Path) -> Path:
    return _host_workflow_dir(batch_dir) / GATE2_DIR


def _gate2_paths(batch_dir: Path, stage: str) -> dict:
    """由批次推导固定数据库路径；不允许调用者指定任意路径。"""
    relative = batch_dir.relative_to(BATCHES_ROOT)
    output_dir = (SQLITE_TESTS_ROOT / GATE2_SQLITE_SUBDIR / relative).resolve()
    try:
        output_dir.relative_to(SQLITE_TESTS_ROOT)
    except ValueError as exc:
        raise WorkflowHostBlocked(
            f"推导出的输出目录越出 {SQLITE_TESTS_ROOT}：{output_dir}", stage=stage) from exc
    database_path = output_dir / GATE2_DATABASE_NAME
    return {"relative": str(relative).replace(os.sep, "/"), "output_dir": output_dir,
            "database_path": database_path,
            "staging_path": database_path.with_name(database_path.name + GATE2_STAGING_SUFFIX),
            "root": SQLITE_TESTS_ROOT}


def _gate2_materials(batch_dir: Path, context: dict, normalized: dict, load_report: dict) -> dict:
    """按 Gate2 协议构造本次守门材料（scope 延续本批次合法范围与来源声明）。"""
    source_description = context["manifest"]["source"]["source_description"]
    return {
        "batch_id": batch_dir.name,
        "gate": CONTROLLER_MODULE.GATE2,
        "run_bindings_sha256": context["manifest"]["bindings_sha256"],
        "scope": {**copy.deepcopy(GATE1_SCOPE_FIXED), "source_description": source_description,
                  "known_limitations": list(GATE1_LIMITATIONS)},
        "blocking_issues": [],
        "evidence": {"normalized": normalized, "load_report": load_report},
    }


def _read_gate2_outputs(batch_dir: Path, stage: str) -> dict:
    """从固定路径实读本次产物（不跟随清单访问任意路径）。"""
    gate2 = _gate2_dir(batch_dir)
    normalized_path = gate2 / GATE2_NORMALIZED
    report_path = gate2 / GATE2_LOAD_REPORT
    artifacts_path = gate2 / GATE2_ARTIFACTS
    for path, label in ((normalized_path, GATE2_NORMALIZED), (report_path, GATE2_LOAD_REPORT),
                        (artifacts_path, GATE2_ARTIFACTS)):
        _require(path.is_file(), f"{WORKFLOW_DIR}/{GATE2_DIR}/{label}",
                 f"缺少本次产物文件（{path}）", stage)
    # 对象与文件字节哈希必须来自**同一次读取缓冲**（不得先解析再另读一次算哈希）
    normalized, normalized_file_sha256 = _read_json_with_bytes(
        normalized_path, f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}", stage)
    load_report, load_report_file_sha256 = _read_json_with_bytes(
        report_path, f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}", stage)
    artifacts, artifacts_file_sha256 = _read_json_with_bytes(
        artifacts_path, f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}", stage)
    return {"normalized": normalized, "load_report": load_report, "artifacts": artifacts,
            "normalized_file_sha256": normalized_file_sha256,
            "load_report_file_sha256": load_report_file_sha256,
            "artifacts_file_sha256": artifacts_file_sha256,
            "normalized_path": normalized_path, "load_report_path": report_path,
            "artifacts_path": artifacts_path}


def _save_gate2_failure(batch_dir: Path, stage_label: str, exc: Exception, observed: dict) -> str:
    """尽力独占保存本次失败诊断；写不成时如实抛出，不宣称已保存。"""
    payload = {
        "failure_version": FAILURE_VERSION,
        "recorded_at_utc": _now_utc(),
        "stage": stage_label,
        "exception_class": type(exc).__name__,
        "message": str(exc),
        "reasons": [str(item) for item in getattr(exc, "reasons", []) or [str(exc)]],
        "observed_outputs": observed,
        "note": ("本次 prepare-gate2 未完成：保留已产生的文件与 staging，不自动删除、不重试；"
                 "需继续时新建批次。"),
    }
    path = _gate2_dir(batch_dir) / GATE2_FAILURE
    if path.exists():
        raise WorkflowHostError(f"失败诊断已存在，不覆盖：{path}", stage=stage_label)
    return _write_exclusive_json(path, payload, stage_label)


def _load_gate2_failure(batch_dir: Path, stage: str):
    """读取并校验本次失败诊断；不存在返回 None；非法／不完整一律协议阻断。"""
    path = _gate2_dir(batch_dir) / GATE2_FAILURE
    label = f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_FAILURE}"
    if not path.exists():
        return None
    _require(path.is_file(), label, f"必须是非目录的普通文件（实际 {path}）", stage)
    failure = _read_json(path, label, stage)
    _require_keys(failure, ("failure_version", "recorded_at_utc", "stage", "exception_class",
                            "message", "reasons"), label, stage)
    _require(failure["failure_version"] == FAILURE_VERSION, f"{label}.failure_version",
             f"必须是受支持的固定值 {FAILURE_VERSION}，实际 {failure['failure_version']!r}", stage)
    _require_str(failure["recorded_at_utc"], f"{label}.recorded_at_utc", stage)
    _require_str(failure["stage"], f"{label}.stage", stage)
    _require_str(failure["exception_class"], f"{label}.exception_class", stage)
    _require_str(failure["message"], f"{label}.message", stage)
    _require(isinstance(failure["reasons"], list) and failure["reasons"], f"{label}.reasons",
             f"必须是非空原因列表，实际 {failure['reasons']!r}", stage)
    for index, item in enumerate(failure["reasons"]):
        _require_str(item, f"{label}.reasons[{index}]", stage)
    _require(isinstance(failure.get("observed_outputs"), dict), f"{label}.observed_outputs",
             "必须是对象（如实记录已观察到的输出状态）", stage)
    return failure


def _gate2_failure_exception(failure: dict) -> Exception:
    """失败类别按语义映射：运行失败 exit 2，其余协议阻断 exit 1。"""
    reasons = [str(item) for item in failure["reasons"]]
    message = (f"该批次的 {WORKFLOW_DIR}/{GATE2_DIR}/ 记录了未完成的准备尝试："
               f"stage={failure['stage']!r}；异常类别={failure['exception_class']!r}；原因={reasons!r}。"
               "即使存在可解析的完整 0003，也不得宣告本次准备成功；不重试、不复用、不自动删除，"
               "需继续时新建批次。")
    if failure["exception_class"] in RUNTIME_FAILURE_CLASSES:
        return WorkflowHostError(message, reasons=reasons, stage=failure["stage"])
    return WorkflowHostBlocked(message, reasons=reasons, stage=failure["stage"])


def _verify_gate2_tail(batch_dir: Path, expected: dict, stage: str) -> dict:
    """收尾一致性：复测本次消费的全部产物（固定路径，不跟随清单）。"""
    paths = _gate2_paths(batch_dir, stage)
    gate2 = _gate2_dir(batch_dir)
    actual = {
        "normalized_file_sha256": file_sha256(gate2 / GATE2_NORMALIZED),
        "load_report_file_sha256": file_sha256(gate2 / GATE2_LOAD_REPORT),
        "artifacts_file_sha256": file_sha256(gate2 / GATE2_ARTIFACTS),
        "database_sha256": file_sha256(paths["database_path"]),
        "host_manifest_file_sha256": file_sha256(_host_manifest_path(batch_dir)),
    }
    for key, value in actual.items():
        label = {"normalized_file_sha256": f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}",
                 "load_report_file_sha256": f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}",
                 "artifacts_file_sha256": f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}",
                 "database_sha256": str(paths["database_path"]),
                 "host_manifest_file_sha256": f"{WORKFLOW_DIR}/{HOST_MANIFEST_NAME}"}[key]
        _require(expected.get(key) == value, label,
                 f"收尾复测发现本次已消费的产物发生变化：期望 {expected.get(key)!r}，实际 {value!r}", stage)
    for revision, want in sorted((expected.get("checkpoints") or {}).items()):
        path = _checkpoint_path(batch_dir, revision)
        _require(path.is_file(), f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{revision:04d}.json",
                 "收尾复测时 checkpoint 缺失", stage)
        got = file_sha256(path)
        _require(got == want, f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{revision:04d}.json",
                 f"收尾复测发现 checkpoint 字节变化：期望 {want!r}，实际 {got!r}", stage)
    failure_path = _gate2_dir(batch_dir) / GATE2_FAILURE
    _require(not failure_path.exists(), f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_FAILURE}",
             "成功收尾不得存在失败诊断", stage)
    return actual


def _verify_prepare_operation(payload: dict, previous_payload: dict, state: dict,
                              measured_bindings: dict, label: str, stage: str,
                              batch_dir: Path, manifest: dict, *,
                              previous_file_sha256: str) -> None:
    """0003 只允许从合法 Gate1 APPROVE 的 0002 延续；重放时用本次实际材料复算完整预期返回。"""
    operation = payload["operation"]
    _require(operation.get("kind") == OPERATION_PREPARE_GATE2, f"{label}.operation.kind",
             f"0003 必须是 {OPERATION_PREPARE_GATE2}，实际 {operation.get('kind')!r}", stage)
    _require_keys(operation, ("artifacts", "artifacts_file_sha256", "materials_sha256", "phase_after",
                              "bindings_sha256", "gate1_decision_sha256", "database_sha256",
                              "normalized_payload_sha256", "database_path", "output_relative"),
                  f"{label}.operation", stage)
    _require_hash(operation["artifacts_file_sha256"], f"{label}.operation.artifacts_file_sha256", stage)
    previous_workflow = previous_payload["workflow"]
    previous_state = previous_workflow["state"]
    _require(previous_state["phase"] == CONTROLLER_MODULE.PHASE_G1_APPROVED, f"{label}.previous.phase",
             f"0003 只能从 Gate1 APPROVED 的 0002 延续，实际 {previous_state['phase']!r}", stage)
    decisions = previous_state["simulated_decisions"]
    _require(isinstance(decisions, list) and len(decisions) == 1, f"{label}.previous.simulated_decisions",
             "0002 必须恰含一个 Gate1 决定", stage)
    body_sha = canonical_sha256({key: value for key, value in decisions[0].items()
                                if key != "decision_sha256"})
    _require(operation["gate1_decision_sha256"] == body_sha, f"{label}.operation.gate1_decision_sha256",
             "必须等于本 workflow 已验证 Gate1 APPROVE 正文的实际规范指纹", stage)

    outputs = _read_gate2_outputs(batch_dir, stage)
    artifacts = outputs["artifacts"]
    artifacts_label = f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"
    _require(isinstance(artifacts, dict), artifacts_label,
             f"必须是 JSON 对象，实际 {type(artifacts).__name__}", stage)
    _require_keys(artifacts, ("artifacts_version", "batch_id", "database_path", "output_relative",
                             "database_sha256", "normalized_payload_sha256",
                             "normalized_file_sha256", "load_report_file_sha256",
                             "previous_checkpoint_file_sha256", "host_manifest_file_sha256",
                             "gate1_decision_sha256", "prepare_version", "checkpoint_version",
                             "created_at_utc"), artifacts_label, stage)
    # a) 三个版本固定值
    _require_str(artifacts["artifacts_version"], f"{GATE2_ARTIFACTS}.artifacts_version", stage)
    _require(artifacts["artifacts_version"] == ARTIFACTS_VERSION, f"{GATE2_ARTIFACTS}.artifacts_version",
             f"必须是受支持的固定值 {ARTIFACTS_VERSION}，实际 {artifacts['artifacts_version']!r}", stage)
    _require(artifacts["prepare_version"] == HOST_VERSION, f"{GATE2_ARTIFACTS}.prepare_version",
             f"必须是当前宿主版本 {HOST_VERSION}，实际 {artifacts['prepare_version']!r}", stage)
    _require(artifacts["checkpoint_version"] == CHECKPOINT_VERSION,
             f"{GATE2_ARTIFACTS}.checkpoint_version",
             f"必须是 {CHECKPOINT_VERSION}，实际 {artifacts['checkpoint_version']!r}", stage)
    _require_str(artifacts["created_at_utc"], f"{GATE2_ARTIFACTS}.created_at_utc", stage)
    # b) 批次与推导路径
    _require_str(artifacts["batch_id"], f"{GATE2_ARTIFACTS}.batch_id", stage)
    _require(artifacts["batch_id"] == batch_dir.name, f"{GATE2_ARTIFACTS}.batch_id",
             "必须与批次目录叶子一致", stage)
    for key in ("database_path", "output_relative", "database_sha256", "normalized_payload_sha256",
                "normalized_file_sha256", "load_report_file_sha256",
                "previous_checkpoint_file_sha256", "host_manifest_file_sha256", "gate1_decision_sha256"):
        _require_str(artifacts[key], f"{GATE2_ARTIFACTS}.{key}", stage)
    # c) 前序与清单字节哈希
    _require(artifacts["previous_checkpoint_file_sha256"] == previous_file_sha256,
             f"{GATE2_ARTIFACTS}.previous_checkpoint_file_sha256",
             "必须等于 0002 的实际字节哈希", stage)
    _require_hash(artifacts["host_manifest_file_sha256"], f"{GATE2_ARTIFACTS}.host_manifest_file_sha256",
                  stage)
    _require(artifacts["host_manifest_file_sha256"] == file_sha256(_host_manifest_path(batch_dir)),
             f"{GATE2_ARTIFACTS}.host_manifest_file_sha256",
             "必须等于宿主清单的实际文件字节哈希", stage)
    # d) 两个材料文件字节哈希
    _require_hash(artifacts["normalized_file_sha256"], f"{GATE2_ARTIFACTS}.normalized_file_sha256", stage)
    _require(artifacts["normalized_file_sha256"] == outputs["normalized_file_sha256"],
             f"{GATE2_ARTIFACTS}.normalized_file_sha256", "必须等于 normalized.json 实际字节哈希", stage)
    _require_hash(artifacts["load_report_file_sha256"], f"{GATE2_ARTIFACTS}.load_report_file_sha256", stage)
    _require(artifacts["load_report_file_sha256"] == outputs["load_report_file_sha256"],
             f"{GATE2_ARTIFACTS}.load_report_file_sha256", "必须等于 load_report.json 实际字节哈希", stage)
    # 0003 必须保存 artifacts.json 的实际文件字节哈希（与对象规范指纹分开）
    _require(operation["artifacts_file_sha256"] == outputs["artifacts_file_sha256"],
             f"{label}.operation.artifacts_file_sha256",
             "必须等于 artifacts.json 的实际文件字节哈希", stage)
    _require(canonical_json(artifacts) == canonical_json(operation["artifacts"]),
             f"{label}.operation.artifacts", "操作摘要必须与磁盘实际 artifacts.json 完全一致", stage)

    normalized = outputs["normalized"]
    load_report = outputs["load_report"]
    _require(isinstance(load_report, dict), f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}",
             f"必须是对象，实际 {type(load_report).__name__}", stage)
    normalized_sha = canonical_sha256(normalized)
    _require(normalized_sha == operation["normalized_payload_sha256"],
             f"{label}.operation.normalized_payload_sha256", "必须等于本次 normalized 对象的规范指纹", stage)
    _require(artifacts["normalized_payload_sha256"] == normalized_sha,
             f"{GATE2_ARTIFACTS}.normalized_payload_sha256",
             "必须等于实际 normalized 对象的规范指纹", stage)
    _require(load_report.get("normalized_payload_sha256") == normalized_sha,
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}.normalized_payload_sha256",
             "必须等于本次 normalized 对象的规范指纹", stage)

    paths = _gate2_paths(batch_dir, stage)
    database_path = paths["database_path"]
    _require(Path(artifacts["database_path"]) == database_path, f"{GATE2_ARTIFACTS}.database_path",
             f"必须等于宿主推导的固定路径 {database_path}", stage)
    _require(artifacts["output_relative"] == paths["relative"], f"{GATE2_ARTIFACTS}.output_relative",
             "必须等于批次相对 data/batches 的路径", stage)
    _require(operation["database_path"] == str(database_path), f"{label}.operation.database_path",
             "操作摘要数据库路径必须等于宿主推导的固定路径", stage)
    _require(operation["output_relative"] == paths["relative"], f"{label}.operation.output_relative",
             "操作摘要输出相对路径必须与批次一致", stage)
    _require(database_path.is_file(), f"{WORKFLOW_DIR}/{GATE2_DIR}", f"数据库文件必须存在（{database_path}）",
             stage)
    actual_database_sha = file_sha256(database_path)
    _require(actual_database_sha == operation["database_sha256"], f"{label}.operation.database_sha256",
             "必须等于数据库实际字节哈希", stage)
    _require(artifacts["database_sha256"] == actual_database_sha, f"{GATE2_ARTIFACTS}.database_sha256",
             "必须等于数据库实际字节哈希", stage)
    _require(load_report.get("database_sha256") == actual_database_sha,
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}.database_sha256",
             "装载报告的数据库哈希必须等于实际字节哈希", stage)
    _require(load_report.get("database_path") == str(database_path),
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}.database_path",
             "装载报告路径必须等于宿主推导的固定路径", stage)
    _require(load_report.get("source", {}).get("input_sha256") == manifest["bindings"]["input_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}.source.input_sha256",
             "装载报告来源必须与批次绑定一致", stage)
    _require(normalized.get("source", {}).get("input_sha256") == manifest["bindings"]["input_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}.source.input_sha256",
             "标准化来源必须与批次绑定一致", stage)

    materials = _gate2_materials(batch_dir, {"manifest": manifest}, normalized, load_report)
    materials_sha = canonical_sha256(materials)
    _require(materials_sha == operation["materials_sha256"], f"{label}.operation.materials_sha256",
             "必须等于本次实际材料对象的规范指纹", stage)
    _require(state["phase"] == CONTROLLER_MODULE.PHASE_G2_PENDING, f"{label}.workflow.state.phase",
             f"0003 必须停在 {CONTROLLER_MODULE.PHASE_G2_PENDING}，实际 {state['phase']!r}", stage)
    _require(operation["phase_after"] == state["phase"], f"{label}.operation.phase_after",
             "操作摘要 phase 必须与实际状态一致", stage)
    _require(operation["bindings_sha256"] == state["run_bindings_sha256"],
             f"{label}.operation.bindings_sha256", "必须与 workflow 绑定一致", stage)
    _require(artifacts["gate1_decision_sha256"] == body_sha, f"{GATE2_ARTIFACTS}.gate1_decision_sha256",
             "必须等于本 workflow 已验证 Gate1 APPROVE 正文的实际规范指纹", stage)
    request = state["requests"][CONTROLLER_MODULE.GATE2]
    _require(isinstance(request, dict), f"{label}.workflow.state.requests.GATE2", "必须是对象", stage)
    _require(request.get("prior_simulated_decision_sha256") == body_sha,
             f"{label}.workflow.state.requests.GATE2.prior_simulated_decision_sha256",
             "Gate2 前序决定指纹必须等于本 workflow 已验证 Gate1 APPROVE 正文指纹", stage)
    _require(canonical_sha256(request.get("materials")) == materials_sha,
             f"{label}.workflow.state.requests.GATE2.materials",
             "Gate2 请求内的材料必须等于本次实际材料", stage)
    try:
        expected = CONTROLLER_MODULE.prepare_dev_gate(previous_workflow, CONTROLLER_MODULE.GATE2,
                                                     copy.deepcopy(materials),
                                                     current_bindings=measured_bindings)
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        raise WorkflowHostBlocked(
            f"checkpoint {label} 不是 0002 的合法 Gate2 延续：冻结控制器阻断（{exc}）", stage=stage) from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        raise WorkflowHostError(f"checkpoint {label} 延续复算出现意外错误：{exc}", stage=stage) from exc
    _require(canonical_json(expected["state"]) == canonical_json(state), f"{label}.workflow.state",
             "0003 的 state 必须等于由 0002 与本次实际材料复算得到的完整预期结果", stage)
    base_history = previous_state["history"]
    _require(state["history"][:len(base_history)] == base_history, f"{label}.workflow.state.history",
             "0003 必须保留 0001／0002 的全部历史前缀", stage)
    _require(canonical_json(state["requests"][CONTROLLER_MODULE.GATE1])
             == canonical_json(previous_state["requests"][CONTROLLER_MODULE.GATE1]),
             f"{label}.workflow.state.requests.GATE1", "0003 必须完整保留 0002 的 Gate1 请求", stage)
    _require(previous_state["requests"][CONTROLLER_MODULE.GATE2] is None,
             f"{label}.previous.requests.GATE2", "0002 不得已含 Gate2 请求", stage)
    return {
        "normalized_file_sha256": outputs["normalized_file_sha256"],
        "load_report_file_sha256": outputs["load_report_file_sha256"],
        "artifacts_file_sha256": outputs["artifacts_file_sha256"],
        "database_sha256": actual_database_sha,
        "host_manifest_file_sha256": file_sha256(_host_manifest_path(batch_dir)),
    }


def _verify_gate2_decision_operation(payload: dict, previous_payload: dict, state: dict,
                                     measured_bindings: dict, label: str, stage: str,
                                     batch_dir: Path, manifest: dict, *,
                                     previous_file_sha256: str, gate2_expected) -> None:
    """0004 只允许从合法 DEV_GATE2_PENDING 的 0003 延续一次 Gate2 决定。"""
    operation = payload["operation"]
    _require(operation.get("kind") == OPERATION_GATE2_DECISION, f"{label}.operation.kind",
             f"0004 必须是 {OPERATION_GATE2_DECISION}，实际 {operation.get('kind')!r}", stage)
    _require_keys(operation, ("decision", "decision_sha256", "phase_after", "bindings_sha256"),
                  f"{label}.operation", stage)
    recorded = operation["decision"]
    _require(isinstance(recorded, dict), f"{label}.operation.decision", "必须是对象", stage)
    _require_keys(recorded, (*CONTROLLER_MODULE.REQUIRED_DECISION_KEYS, "decision_sha256"),
                  f"{label}.operation.decision", stage)
    body = {key: value for key, value in recorded.items() if key != "decision_sha256"}
    actual_body_sha = canonical_sha256(body)
    _require(recorded["decision_sha256"] == actual_body_sha, f"{label}.operation.decision.decision_sha256",
             "必须等于决定正文（剥离派生字段）的实际规范指纹", stage)
    _require(operation["decision_sha256"] == actual_body_sha, f"{label}.operation.decision_sha256",
             "必须等于决定正文的实际规范指纹", stage)

    stored = state["simulated_decisions"]
    _require(isinstance(stored, list) and len(stored) == 2, f"{label}.workflow.state.simulated_decisions",
             f"0004 必须恰含 Gate1 与本次 Gate2 两个决定，实际 "
             f"{len(stored) if isinstance(stored, list) else stored!r}", stage)
    _require(canonical_json(stored[-1]) == canonical_json(recorded),
             f"{label}.workflow.state.simulated_decisions",
             "workflow 存放的 Gate2 决定必须与操作摘要完整决定一致", stage)
    _require(state["phase"] in (CONTROLLER_MODULE.APPROVED_PHASE[CONTROLLER_MODULE.GATE2],
                               CONTROLLER_MODULE.HELD_PHASE[CONTROLLER_MODULE.GATE2],
                               CONTROLLER_MODULE.REJECTED_PHASE[CONTROLLER_MODULE.GATE2]),
             f"{label}.workflow.state.phase",
             f"0004 只允许 Gate2 APPROVED／HELD／REJECTED，实际 {state['phase']!r}", stage)
    _require(operation["phase_after"] == state["phase"], f"{label}.operation.phase_after",
             "操作摘要的 phase 必须与实际状态一致", stage)
    _require(operation["bindings_sha256"] == state["run_bindings_sha256"],
             f"{label}.operation.bindings_sha256", "必须与 workflow 绑定一致", stage)
    _require(state["batch_id"] == payload["batch_id"], f"{label}.workflow.state.batch_id",
             "workflow 批次必须与 checkpoint 一致", stage)

    previous_workflow = previous_payload["workflow"]
    previous_state = previous_workflow["state"]
    _require(previous_state["phase"] == CONTROLLER_MODULE.PHASE_G2_PENDING, f"{label}.previous.phase",
             f"0004 只能从 {CONTROLLER_MODULE.PHASE_G2_PENDING} 的 0003 延续，实际 "
             f"{previous_state['phase']!r}", stage)
    previous_decisions = previous_state["simulated_decisions"]
    _require(isinstance(previous_decisions, list) and len(previous_decisions) == 1,
             f"{label}.previous.simulated_decisions", "0003 必须恰含一个 Gate1 决定", stage)
    _require(canonical_json(stored[0]) == canonical_json(previous_decisions[0]),
             f"{label}.workflow.state.simulated_decisions[0]",
             "0004 必须完整保留 0003 的 Gate1 决定（决定总数恰为 2）", stage)
    _require(canonical_json(state["requests"][CONTROLLER_MODULE.GATE1])
             == canonical_json(previous_state["requests"][CONTROLLER_MODULE.GATE1]),
             f"{label}.workflow.state.requests.GATE1", "0004 必须完整保留 0003 的 Gate1 请求", stage)
    request = state["requests"][CONTROLLER_MODULE.GATE2]
    _require(isinstance(request, dict), f"{label}.workflow.state.requests.GATE2", "必须是对象", stage)
    _require(canonical_json(request) == canonical_json(previous_state["requests"][CONTROLLER_MODULE.GATE2]),
             f"{label}.workflow.state.requests.GATE2", "0004 必须完整保留 0003 的 Gate2 请求", stage)
    _require(operation["decision"]["request_id"] == request["request_id"],
             f"{label}.operation.decision.request_id", "决定必须指向本批次实际的 Gate2 请求", stage)

    # 0003 的材料核验与 gate2_expected 保留到 0004 恢复：不因当前是决定事件而跳过数据库核验
    _require(isinstance(gate2_expected, dict) and bool(gate2_expected), f"{label}.gate2_expected",
             "0004 恢复必须带出 0003 的初次材料核验读数（不得跳过数据库与产物核验）", stage)
    outputs = _read_gate2_outputs(batch_dir, stage)
    paths = _gate2_paths(batch_dir, stage)
    actual_database_sha = file_sha256(paths["database_path"])
    for key, value, field in (
        ("normalized_file_sha256", outputs["normalized_file_sha256"], f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}"),
        ("load_report_file_sha256", outputs["load_report_file_sha256"], f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}"),
        ("artifacts_file_sha256", outputs["artifacts_file_sha256"], f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"),
        ("database_sha256", actual_database_sha, str(paths["database_path"])),
    ):
        _require(gate2_expected.get(key) == value, field,
                 f"Gate2 材料在决定恢复时发生了变化：期望 {gate2_expected.get(key)!r}，实际 {value!r}", stage)
    materials = _gate2_materials(batch_dir, {"manifest": manifest}, outputs["normalized"], outputs["load_report"])
    materials_sha = canonical_sha256(materials)
    _require(request.get("materials_sha256") == materials_sha,
             f"{label}.workflow.state.requests.GATE2.materials_sha256",
             "Gate2 请求材料指纹必须等于本次实际材料对象的规范指纹", stage)
    _require(canonical_sha256(request.get("materials")) == materials_sha,
             f"{label}.workflow.state.requests.GATE2.materials",
             "Gate2 请求内的材料必须等于本次实际材料", stage)
    gate1_body_sha = canonical_sha256({key: value for key, value in stored[0].items()
                                      if key != "decision_sha256"})
    _require(request.get("prior_simulated_decision_sha256") == gate1_body_sha,
             f"{label}.workflow.state.requests.GATE2.prior_simulated_decision_sha256",
             "Gate2 前序决定指纹必须等于本 workflow 已验证 Gate1 APPROVE 正文指纹", stage)

    try:
        expected = CONTROLLER_MODULE.record_dev_decision(previous_workflow, copy.deepcopy(body),
                                                        current_bindings=measured_bindings)
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        raise WorkflowHostBlocked(
            f"checkpoint {label} 不是 0003 的合法 Gate2 延续：冻结控制器阻断该决定（{exc}）",
            stage=stage) from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        raise WorkflowHostError(f"checkpoint {label} 延续复算出现意外错误：{exc}", stage=stage) from exc
    _require(canonical_json(expected["state"]) == canonical_json(state), f"{label}.workflow.state",
             "0004 的 state 必须等于由 0003 与本次决定复算得到的完整预期结果", stage)
    base_history = previous_state["history"]
    _require(state["history"][:len(base_history)] == base_history, f"{label}.workflow.state.history",
             "0004 必须保留 0001—0003 的全部历史前缀", stage)
    _require(len(state["history"]) == len(base_history) + 1, f"{label}.workflow.state.history",
             "0004 必须恰好新增一个历史事件", stage)


def _recheck_static_bindings(batch_dir: Path, expected: dict, stage: str, *, when: str) -> dict:
    """收尾复测：从磁盘重新读取实际字节计算静态绑定，与本次操作开始时的读数逐项比较。

    必须在最后一次必要控制器调用之后调用；不得用先前保存的内存读数代替。差异给
    WorkflowHostBlocked，并给出固定路径、差异字段与预期/实际哈希。
    """
    actual = _measure_bindings(batch_dir)
    if canonical_json(actual) != canonical_json(expected):
        diff_keys = sorted({key for key in set(actual) | set(expected)
                            if actual.get(key) != expected.get(key)})
        snapshot_expected = (expected or {}).get("input_sha256")
        snapshot_actual = actual.get("input_sha256")
        raise WorkflowHostBlocked(
            f"{when}重新从磁盘实测的静态绑定与本次操作开始时不一致（差异字段 {diff_keys}）："
            f"source/input.xlsx 预期（操作开始）{snapshot_expected!r}，实际 {snapshot_actual!r}",
            stage=stage)
    return actual


def _load_host_context(batch_dir: Path, *, stage: str) -> dict:
    """status／record 共用的完整宿主恢复核验。"""
    manifest, manifest_file_sha256 = _load_host_manifest(batch_dir, stage)
    if manifest.get("status") != STATUS_READY:
        status = _require_failure_manifest(manifest, batch_dir, stage)
        failure = manifest["failure"]
        host_result = manifest["host_result"]
        reasons = [str(item) for item in failure["reasons"]]
        reasons.append(f"receiver 实际退出码={manifest['receive']['exit_code']!r}"
                       f"（状态 {manifest['receive']['batch_status']!r}）")
        if host_result["exit_code"] == 2:
            raise WorkflowHostError(
                f"该批次是宿主记录的运行失败批次（state={status}，失败层={host_result['layer']}）："
                f"stage={host_result.get('stage')!r}；异常类别={host_result.get('exception_class')!r}；"
                f"原因={reasons!r}", reasons=reasons, stage=stage)
        raise WorkflowHostBlocked(
            f"该批次是宿主记录的阻断批次（state={status}，失败层={host_result['layer']}）："
            f"stage={host_result.get('stage')!r}；原因={reasons!r}", reasons=reasons, stage=stage)
    _require_success_manifest(manifest, batch_dir, stage)
    measured = _measure_bindings(batch_dir)
    _require(canonical_sha256(manifest["bindings"]) == canonical_sha256(measured),
             f"{HOST_MANIFEST_NAME}.bindings",
             "清单绑定、当前实测绑定必须逐项一致（只允许一次操作内不发生变化的现场）", stage)
    # B2：四类失败诊断必须在**解析 checkpoint 链之前**读取并核验。否则半写／损坏的
    # checkpoint 会先触发协议解析错误，把有效的复算失败诊断（含退出码 2）遮蔽成协议阻断。
    # 诊断本身仍按各自固定版本、必需键与严格类型核验；非法诊断仍按协议阻断（退出 1）。
    gate2_failure = _load_gate2_failure(batch_dir, stage)
    if gate2_failure is not None:
        raise _gate2_failure_exception(gate2_failure)
    screen_failure = _load_screen_failure(batch_dir, stage)
    if screen_failure is not None:
        raise _screen_failure_exception(screen_failure)
    crosscheck_failure = _load_crosscheck_failure(batch_dir, stage)
    if crosscheck_failure is not None:
        raise _crosscheck_failure_exception(crosscheck_failure)
    fact_packet_failure = _load_fact_packet_failure(batch_dir, stage)
    if fact_packet_failure is not None:
        raise _fact_packet_failure_exception(fact_packet_failure)
    initial_judgment_failure = _load_initial_judgment_failure(batch_dir, stage)
    if initial_judgment_failure is not None:
        raise _initial_judgment_failure_exception(initial_judgment_failure)
    chain = _load_checkpoint_chain(batch_dir, manifest, manifest_file_sha256, measured, stage)
    for item in chain["checkpoints"]:
        _require(item["payload"]["workflow"]["state"]["run_bindings"] == manifest["bindings"],
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}.workflow.state.run_bindings",
                 "workflow 创建绑定必须与宿主清单绑定逐项一致", stage)
    # started 存在但没有完整成功集合时为未完成阻断（诊断缺失/非法时的兜底）
    if _screen_dir(batch_dir).exists() and chain["current"]["revision"] < 5:
        _raise_incomplete_screen(batch_dir, chain)
    if _crosscheck_dir(batch_dir).exists() and chain["current"]["revision"] < 6:
        _raise_incomplete_crosscheck(batch_dir, chain)
    if _fact_packet_dir(batch_dir).exists() and chain["current"]["revision"] < 7:
        _raise_incomplete_fact_packet(batch_dir, chain)
    if _initial_judgment_dir(batch_dir).exists() and chain["current"]["revision"] < 8:
        _raise_incomplete_initial_judgment(batch_dir, chain)
    return {"manifest": manifest, "manifest_file_sha256": manifest_file_sha256,
            "measured_bindings": measured, "chain": chain, "status": STATUS_READY}


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


def _run_receiver(workbook: Path, batch_dir: Path, source_description: str) -> dict:
    command = [sys.executable, "-B", str(RECEIVER), "--workbook", str(workbook),
               "--out-dir", str(batch_dir), "--source-description", source_description]
    try:
        completed = subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
                                   timeout=RECEIVER_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired as exc:
        raise WorkflowHostError(f"接收入口超时（{RECEIVER_TIMEOUT_SECONDS}s）：{RECEIVER}",
                                stage="run_receiver") from exc
    except OSError as exc:
        raise WorkflowHostError(f"无法启动接收入口 {RECEIVER}：{exc}", stage="run_receiver") from exc
    return {"command": command, "exit_code": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr}


def _save_receiver_logs(batch_dir: Path, receive_result: dict) -> dict:
    """接收器返回后立即保存真实完整命令/退出码/stdout/stderr 与独占的结构化调用记录。"""
    workflow_dir = _host_workflow_dir(batch_dir)
    _ensure_dir(workflow_dir, "start")
    logs = {}
    for name, text in ((RECEIVER_STDOUT, receive_result["stdout"]), (RECEIVER_STDERR, receive_result["stderr"])):
        path = workflow_dir / name
        try:
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            raise WorkflowHostError(f"接收入口已运行，但诊断日志写入失败：{path}（{exc}）（不宣称已保存）",
                                    stage="start") from exc
        logs[name] = {"path": f"{WORKFLOW_DIR}/{name}", "exists": True, "sha256": file_sha256(path)}
    record = {
        "invocation_version": "TASK-010-receive-invocation-1.0",
        "recorded_at_utc": _now_utc(),
        "command": receive_result["command"],
        "exit_code": receive_result["exit_code"],
        "stdout_log": logs[RECEIVER_STDOUT],
        "stderr_log": logs[RECEIVER_STDERR],
        "note": "接收器实际调用记录：由宿主在子进程返回后立即独占写入；成功／质量阻断／运行失败都保存。",
    }
    record_path = workflow_dir / RECEIVE_INVOCATION
    record_hash = _write_exclusive_json(record_path, record, "start")
    logs[RECEIVE_INVOCATION] = {"path": f"{WORKFLOW_DIR}/{RECEIVE_INVOCATION}", "exists": True,
                                "sha256": record_hash}
    return logs


def _read_invocation_record(batch_dir: Path, stage: str) -> dict:
    path = _host_workflow_dir(batch_dir) / RECEIVE_INVOCATION
    if not path.exists():
        raise WorkflowHostBlocked(
            f"缺少接收器调用记录：{WORKFLOW_DIR}/{RECEIVE_INVOCATION}（本版本要求独立留痕）", stage=stage)
    payload = _read_json(path, f"{WORKFLOW_DIR}/{RECEIVE_INVOCATION}", stage)
    _require_keys(payload, ("invocation_version", "recorded_at_utc", "command", "exit_code",
                            "stdout_log", "stderr_log"), f"{WORKFLOW_DIR}/{RECEIVE_INVOCATION}", stage)
    _require(isinstance(payload["command"], list) and len(payload["command"]) >= 3,
             f"{WORKFLOW_DIR}/{RECEIVE_INVOCATION}.command", "必须是完整命令参数列表", stage)
    for index, item in enumerate(payload["command"]):
        _require(isinstance(item, str), f"{WORKFLOW_DIR}/{RECEIVE_INVOCATION}.command[{index}]",
                 f"命令参数必须都是原始字符串，实际 {type(item).__name__}", stage)
    _require(payload["command"][2] == str(RECEIVER), f"{WORKFLOW_DIR}/{RECEIVE_INVOCATION}.command[2]",
             "第 3 个参数必须是冻结接收器脚本路径", stage)
    _require(isinstance(payload["exit_code"], int) and not isinstance(payload["exit_code"], bool),
             f"{WORKFLOW_DIR}/{RECEIVE_INVOCATION}.exit_code", "必须是整数退出码", stage)
    return payload


def _declaration_state(batch_dir: Path, receive_result: dict) -> dict:
    """区分：取得声明、未取得声明、已取得但协议矛盾（不按退出码补造声明）。"""
    path = batch_dir / "batch_manifest.json"
    if not path.exists() or not path.is_file():
        return {"declaration_status": DECLARATION_NOT_ACQUIRED, "declared_batch_status": None,
                "read_error": (f"{path} 存在但不是普通文件（可能是目录），无法读取"
                               if path.exists() else "batch_manifest.json 不存在"),
                "declared_exit_code": None}
    try:
        manifest = _read_json(path, "batch_manifest.json", "verify_receive")
    except (WorkflowHostBlocked, WorkflowHostError) as exc:
        return {"declaration_status": DECLARATION_NOT_ACQUIRED, "declared_batch_status": None,
                "read_error": f"{type(exc).__name__}: {exc}", "declared_exit_code": None}
    declared_status = manifest.get("batch_status")
    declared_exit = manifest.get("receive_exit_code")
    expected_pair = {0: RECEIVER_READY, 1: RECEIVER_BLOCKED, 2: RECEIVER_FAILED}.get(
        receive_result["exit_code"])
    if declared_status != expected_pair or declared_exit != receive_result["exit_code"]:
        return {"declaration_status": DECLARATION_CONTRADICTORY,
                "declared_batch_status": declared_status, "declared_exit_code": declared_exit,
                "read_error": None}
    return {"declaration_status": DECLARATION_ACQUIRED, "declared_batch_status": declared_status,
            "declared_exit_code": declared_exit, "read_error": None}


def _read_receive_manifest(batch_dir: Path) -> dict | None:
    path = batch_dir / "batch_manifest.json"
    if not path.exists():
        return None
    return _read_json(path, "batch_manifest.json", "verify_receive")


def _classify_receive(batch_dir: Path, receive_result: dict, manifest: dict | None, logs: dict) -> dict:
    """先识别实际接收结果，再按分支检查；协议矛盾与 I/O／执行失败分开。"""
    exit_code = receive_result["exit_code"]
    status = (manifest or {}).get("batch_status")
    if manifest is None:
        raise WorkflowHostError(
            f"接收入口未留下 batch_manifest.json（退出码 {exit_code}）：无法核验接收结果，保留实际现场",
            reasons=[f"exit_code={exit_code}", f"stderr={receive_result['stderr'][:300]}"], stage="verify_receive")
    _require(manifest.get("batch_id") == batch_dir.name, "batch_manifest.batch_id",
             f"必须与批次目录叶子一致：{manifest.get('batch_id')!r} != {batch_dir.name!r}", "verify_receive")
    _require(manifest.get("mode") == RECEIVER_MODE, "batch_manifest.mode",
             f"必须是冻结接收器声明的 {RECEIVER_MODE}，实际 {manifest.get('mode')!r}", "verify_receive")
    _require(manifest.get("contract_status") == CONTRACT_STATUS, "batch_manifest.contract_status",
             f"必须是 {CONTRACT_STATUS}", "verify_receive")
    _require(manifest.get("gate1_approval") is None and manifest.get("gate2_approval") is None,
             "batch_manifest", "接收器不得给出真实批准", "verify_receive")
    _require(manifest.get("next_step_allowed") is False, "batch_manifest.next_step_allowed",
             "必须严格为 false", "verify_receive")
    _require(manifest.get("receive_exit_code") == exit_code, "batch_manifest.receive_exit_code",
             f"必须与实际退出码一致：{manifest.get('receive_exit_code')!r} != {exit_code!r}", "verify_receive")
    scope = manifest.get("expected_scope") or {}
    for key, expected in RECEIVER_EXPECTED_SCOPE.items():
        _require(scope.get(key) == expected, f"batch_manifest.expected_scope.{key}",
                 f"必须是固定业务范围 {expected!r}，实际 {scope.get(key)!r}", "verify_receive")
    expected_pair = {0: RECEIVER_READY, 1: RECEIVER_BLOCKED, 2: RECEIVER_FAILED}.get(exit_code)
    _require(expected_pair is not None, "接收退出码", f"必须是 0／1／2，实际 {exit_code!r}", "verify_receive")
    _require(status == expected_pair, "batch_manifest.batch_status",
             f"退出码 {exit_code} 必须对应状态 {expected_pair}，实际 {status!r}（清单与返回码矛盾）",
             "verify_receive")
    declaration = _declaration_state(batch_dir, receive_result)
    if exit_code == 0:
        return {"branch": "ready", "manifest": manifest, "logs": logs, "declaration": declaration}
    reasons = [str(item) for item in (manifest.get("failure_reasons") or [])]
    if not reasons:
        checker_invocation = manifest.get("checker_invocation") or {}
        reasons.append(f"checker 退出码={checker_invocation.get('exit_code')!r}、"
                       f"report_result={checker_invocation.get('report_result')!r}")
        report_path = batch_dir / "checks" / "quality_report.json"
        if report_path.exists():
            try:
                report = _read_json(report_path, "checks/quality_report.json", "verify_receive")
                counts = report.get("issue_counts_by_code")
                issues = report.get("issues")
                reasons.append(f"质量报告 result={report.get('result')!r}、"
                               f"issue_counts_by_code={counts!r}")
                if isinstance(issues, list) and issues:
                    reasons.append(f"问题条目示例={issues[:3]!r}")
            except (WorkflowHostBlocked, WorkflowHostError) as exc:
                reasons.append(f"质量报告无法解析：{exc}")
        else:
            reasons.append("缺少 checks/quality_report.json")
    if exit_code == 2:
        reasons.extend(str(item) for item in ((manifest.get("failure") or {}).get("exceptions") or []))
        reasons.append(f"receiver stderr 摘要={receive_result['stderr'][:200]!r}")
    return {"branch": "blocked_quality" if exit_code == 1 else "failed_runtime",
            "manifest": manifest, "logs": logs, "reasons": reasons, "declaration": declaration}


def _verify_ready_outputs(batch_dir: Path, verified: dict) -> dict:
    manifest = verified["manifest"]
    materials = _material_infos(batch_dir)
    for label, relative in RECEIVER_MATERIALS:
        _require(materials[label]["exists"], f"batch_manifest（{relative}）",
                 "成功批次八份材料必须齐备", "verify_receive")
    snapshot_hash = materials["snapshot"]["sha256"]
    hashes = manifest.get("hashes") or {}
    _require(hashes.get("snapshot_after_copy") == snapshot_hash, "batch_manifest.hashes.snapshot_after_copy",
             "必须与批次快照实际哈希一致", "verify_receive")
    _require(hashes.get("snapshot_written") is True, "batch_manifest.hashes.snapshot_written",
             "快照必须写入完成", "verify_receive")
    _require(hashes.get("snapshot_matches_source") is True, "batch_manifest.hashes.snapshot_matches_source",
             "快照必须与来源一致", "verify_receive")
    receive_script = hashes.get("receive_script") or {}
    checker_hash = hashes.get("checker") or {}
    _require(receive_script.get("sha256_at_end") == file_sha256(RECEIVER),
             "batch_manifest.hashes.receive_script.sha256_at_end", "必须与当前接收器字节一致",
             "verify_receive")
    _require(receive_script.get("stable_during_run") is True,
             "batch_manifest.hashes.receive_script.stable_during_run", "接收器运行期间必须字节稳定",
             "verify_receive")
    _require(checker_hash.get("sha256_at_end") == file_sha256(PROJECT_ROOT / "scripts" / "check_demo_data.py"),
             "batch_manifest.hashes.checker.sha256_at_end", "必须与当前 checker 字节一致", "verify_receive")
    _require(checker_hash.get("stable_during_run") is True,
             "batch_manifest.hashes.checker.stable_during_run", "checker 运行期间必须字节稳定",
             "verify_receive")
    for key, relative in (("spec", "docs/SPEC_V1.md"), ("contract_draft", "docs/AUDIT_CONTRACT_DRAFT.md")):
        declared = hashes.get(key)
        if declared is not None:
            _require(declared.get("sha256") == file_sha256(PROJECT_ROOT / relative),
                     f"batch_manifest.hashes.{key}.sha256", f"必须与当前 {relative} 字节一致", "verify_receive")
    invocation = manifest.get("checker_invocation") or {}
    _require(invocation.get("attempted") is True and invocation.get("started") is True,
             "batch_manifest.checker_invocation", "必须实际启动过 checker", "verify_receive")
    for label, key in (("quality_report", "report"), ("checker_stdout", "stdout_log"),
                       ("checker_stderr", "stderr_log")):
        declared = invocation.get(key) or {}
        expected_relative = dict(RECEIVER_MATERIALS)[label]
        _require(declared.get("exists") is True, f"batch_manifest.checker_invocation.{key}.exists",
                 "清单声明的产物必须存在", "verify_receive")
        _require(declared.get("path") == expected_relative, f"batch_manifest.checker_invocation.{key}.path",
                 f"清单声明路径必须是固定路径 {expected_relative}，实际 {declared.get('path')!r}",
                 "verify_receive")
        _require(declared.get("sha256") == materials[label]["sha256"],
                 f"batch_manifest.checker_invocation.{key}.sha256", "必须与本批次实际字节一致",
                 "verify_receive")
    declared_packet = manifest.get("gate1_packet")
    if isinstance(declared_packet, str):
        _require(declared_packet == "gate1_packet.md", "batch_manifest.gate1_packet",
                 f"必须是 gate1_packet.md，实际 {declared_packet!r}", "verify_receive")
    else:
        _require(isinstance(declared_packet, dict), "batch_manifest.gate1_packet",
                 f"必须是字符串或对象，实际 {type(declared_packet).__name__}", "verify_receive")
        _require(declared_packet.get("path") == "gate1_packet.md", "batch_manifest.gate1_packet.path",
                 "必须是固定路径 gate1_packet.md", "verify_receive")
        _require(declared_packet.get("exists") is True, "batch_manifest.gate1_packet.exists",
                 "声明的候审材料必须存在", "verify_receive")
        _require(declared_packet.get("sha256") == materials["gate1_packet"]["sha256"],
                 "batch_manifest.gate1_packet.sha256", "必须与本批次实际字节一致", "verify_receive")
    code_snapshot = manifest.get("code_snapshot") or {}
    for label, relative in (("receiver_code", "code_snapshot/receive_demo_batch.py"),
                            ("checker_code", "code_snapshot/check_demo_data.py")):
        declared = code_snapshot.get(os.path.basename(relative)) or {}
        _require(declared.get("path") == relative,
                 f"batch_manifest.code_snapshot.{os.path.basename(relative)}.path", f"必须是 {relative}",
                 "verify_receive")
        _require(declared.get("sha256") == materials[label]["sha256"],
                 f"batch_manifest.code_snapshot.{os.path.basename(relative)}.sha256",
                 "必须与本批次实际留档字节一致", "verify_receive")

    quality_report = _read_json(batch_dir / "checks" / "quality_report.json", "checks/quality_report.json",
                               "verify_receive")
    _require(quality_report.get("result") == "pass", "checks/quality_report.json.result",
             f"必须是严格 pass，实际 {quality_report.get('result')!r}", "verify_receive")
    _require(isinstance(quality_report.get("issues"), list) and not quality_report["issues"],
             "checks/quality_report.json.issues", "必须存在且为空列表", "verify_receive")
    counts = quality_report.get("issue_counts_by_code")
    _require(isinstance(counts, dict) and not counts, "checks/quality_report.json.issue_counts_by_code",
             "必须存在且为空对象", "verify_receive")
    _require((quality_report.get("workbook") or {}).get("sha256") == snapshot_hash,
             "checks/quality_report.json.workbook.sha256", "必须与本批次快照实际哈希一致", "verify_receive")
    _require((quality_report.get("checker") or {}).get("sha256") == materials["checker_code"]["sha256"],
             "checks/quality_report.json.checker.sha256", "必须与本批次 checker 源码留档一致", "verify_receive")
    return {"manifest": manifest, "materials": materials, "quality_report": quality_report}


def _write_failure_manifest(batch_dir: Path, *, receive_result: dict, logs: dict, status: str,
                            stage: str, reasons: list, source_text: str, workbook: Path,
                            receive_manifest: dict | None, host_result: dict,
                            declaration: dict, extra: dict | None = None) -> str:
    payload = {
        "manifest_version": HOST_MANIFEST_VERSION,
        "host_version": HOST_VERSION,
        "mode": MODE,
        "contract_status": CONTRACT_STATUS,
        "status": status,
        "next_step_allowed": False,
        "gate1_approval": None,
        "gate2_approval": None,
        "batch_id": batch_dir.name,
        "created_at_utc": _now_utc(),
        "source": {"original_path": str(workbook), "file_name": workbook.name,
                   "source_description": source_text,
                   "source_description_note": "按调用方原字符串保存（含首尾空格与换行）。",
                   "source_identity_note": "接收后恢复读取批次快照，不再切回外部路径。"},
        "receive": {
            "command": receive_result["command"],
            "exit_code": receive_result["exit_code"],
            "batch_status": (receive_manifest or {}).get("batch_status"),
            "declaration_status": declaration["declaration_status"],
            "declared_batch_status": declaration["declared_batch_status"],
            "declared_exit_code": declaration["declared_exit_code"],
            "declaration_read_error": declaration["read_error"],
            "invocation_record": {
                "path": f"{WORKFLOW_DIR}/{RECEIVE_INVOCATION}",
                "sha256": logs[RECEIVE_INVOCATION]["sha256"],
            },
            "stdout_log": f"{WORKFLOW_DIR}/{RECEIVER_STDOUT}",
            "stderr_log": f"{WORKFLOW_DIR}/{RECEIVER_STDERR}",
            "material_logs": logs,
            "materials": _material_infos(batch_dir, raise_on_unreadable=False),
            "receive_exit_code_declared": (receive_manifest or {}).get("receive_exit_code"),
        },
        "host_result": host_result,
        "failure": {
            "stage": stage,
            "reasons": reasons,
            "diagnostics": {
                "failure_reasons": (receive_manifest or {}).get("failure_reasons"),
                "failure": (receive_manifest or {}).get("failure"),
                "checker_invocation": (receive_manifest or {}).get("checker_invocation"),
                "quality_report_exists": (batch_dir / "checks" / "quality_report.json").exists(),
                **(extra or {}),
            },
            "note": ("质量阻断：保留真实报告与原因，未建立可批准请求。" if status == STATUS_BLOCKED_QUALITY
                     else "运行失败：保留真实现场与诊断，未建立可批准请求。"),
        },
        "checkpoints": [],
        "boundaries": [
            "本宿主只做开发态接收与 Gate1 暂停／恢复，不构成正式契约或 Gate 批准。",
            "失败批次没有绑定与可批准请求；恢复时按保存的真实原因返回退出码 1 或 2。",
            "本地哈希只证明字节一致，不证明来源真实。",
        ],
    }
    path = _host_manifest_path(batch_dir)
    if path.exists():
        raise WorkflowHostError(f"宿主清单已存在，不覆盖：{path}", stage=stage)
    return _write_exclusive_json(path, payload, stage)


def _save_host_layer_failure(batch_dir: Path, receive_result: dict, logs: dict, receive_manifest,
                             source_text: str, workbook: Path, exc: Exception) -> str:
    """receiver 实际成功、宿主在读取／核验期间失败时，保存可恢复的宿主失败记录。"""
    if receive_result is None or logs is None:
        raise WorkflowHostError(
            f"宿主自身失败发生在接收调用留痕建立之前，无法保存失败记录：{type(exc).__name__}: {exc}",
            reasons=[str(exc)], stage=getattr(exc, "stage", "") or "start") from exc
    if _host_manifest_path(batch_dir).exists():
        raise
    from_error = isinstance(exc, WorkflowHostError)
    status = STATUS_FAILED_RUNTIME if from_error else STATUS_BLOCKED_PROTOCOL
    host_exit = 2 if from_error else 1
    stage_label = getattr(exc, "stage", "") or "start"
    reasons = [str(item) for item in getattr(exc, "reasons", []) or [str(exc)]]
    reasons.append(f"宿主自身失败（receiver 实际退出码 {receive_result['exit_code']}）："
                   f"{type(exc).__name__} @ {stage_label}")
    try:
        try:
            declaration = _declaration_state(batch_dir, receive_result)
        except (WorkflowHostBlocked, WorkflowHostError) as decl_exc:
            declaration = {"declaration_status": DECLARATION_NOT_ACQUIRED,
                           "declared_batch_status": None, "declared_exit_code": None,
                           "read_error": f"{type(decl_exc).__name__}: {decl_exc}"}
        return _write_failure_manifest(
            batch_dir, receive_result=receive_result, logs=logs, status=status, stage=stage_label,
            reasons=reasons, source_text=source_text or "", workbook=workbook,
            receive_manifest=receive_manifest, declaration=declaration,
            host_result={"exit_code": host_exit, "layer": "HOST", "stage": stage_label,
                         "exception_class": type(exc).__name__, "reasons": reasons},
            extra={"host_failure": {"message": str(exc), "stage": stage_label}})
    except (WorkflowHostBlocked, WorkflowHostError) as save_exc:
        raise WorkflowHostError(
            f"宿主自身失败且失败记录也未能保存：{type(exc).__name__}: {exc}（保存失败：{save_exc}）",
            reasons=reasons + [f"保存失败：{save_exc}"], stage=stage_label) from exc


def start_dev_batch(workbook_path, batch_dir, source_description) -> dict:
    """实际接收一次，形成 Gate1 请求并落盘，停在 DEV_GATE1_PENDING。"""
    progress = {"receive_result": None, "logs": None, "receive_manifest": None}
    try:
        if isinstance(workbook_path, Path):
            workbook = workbook_path
        elif isinstance(workbook_path, str):
            workbook = Path(workbook_path)
        else:
            raise WorkflowHostBlocked(
                f"字段 workbook_path 不可用：必须是字符串或 Path，实际 {type(workbook_path).__name__}",
                stage="start")
        workbook = workbook.resolve() if workbook.is_absolute() else (Path.cwd() / workbook).resolve()
        if not workbook.exists():
            raise WorkflowHostBlocked(f"字段 workbook_path 不可用：文件不存在（{workbook}）", stage="start")
        if not workbook.is_file():
            raise WorkflowHostBlocked(f"字段 workbook_path 不可用：不是文件（{workbook}）", stage="start")
        if workbook.suffix.lower() != ".xlsx":
            raise WorkflowHostBlocked(f"字段 workbook_path 不可用：必须是 .xlsx（{workbook.name}）", stage="start")
        source_text = _require_str(source_description, "source_description", "start")
        target = _resolve_batch_dir(batch_dir, must_exist=False, stage="start")

        receive_result = _run_receiver(workbook, target, source_text)
        progress["receive_result"] = receive_result
        if not (target.exists() and target.is_dir()):
            raise WorkflowHostError(
                "接收入口未创建批次目录，宿主无法保存诊断日志（不宣称已保存）；"
                f"receiver 退出码={receive_result['exit_code']}，stderr={receive_result['stderr'][:400]!r}",
                stage="start")
        logs = _save_receiver_logs(target, receive_result)
        progress["logs"] = logs
        receive_manifest = _read_receive_manifest(target)
        progress["receive_manifest"] = receive_manifest
        classified = _classify_receive(target, receive_result, receive_manifest, logs)
        branch = classified["branch"]

        if branch != "ready":
            status = STATUS_BLOCKED_QUALITY if branch == "blocked_quality" else STATUS_FAILED_RUNTIME
            host_exit = 1 if status == STATUS_BLOCKED_QUALITY else 2
            manifest_file_hash = _write_failure_manifest(
                target, receive_result=receive_result, logs=logs, status=status, stage="verify_receive",
                reasons=classified["reasons"], source_text=source_text, workbook=workbook,
                receive_manifest=receive_manifest,
                declaration=classified.get("declaration") or _declaration_state(target, receive_result),
                host_result={"exit_code": host_exit, "layer": "RECEIVER", "stage": "verify_receive",
                             "exception_class": ("WorkflowHostBlocked" if host_exit == 1
                                                 else "WorkflowHostError"),
                             "reasons": list(classified["reasons"])})
            message = (
                f"接收入口{'质量阻断' if status == STATUS_BLOCKED_QUALITY else '运行失败'}"
                f"（exit {receive_result['exit_code']}，状态 {classified['manifest'].get('batch_status')!r}）："
                f"未建立可批准请求，已保存宿主失败记录（{HOST_MANIFEST_NAME} "
                f"{manifest_file_hash[:16]}…）；原因={classified['reasons']!r}")
            if status == STATUS_BLOCKED_QUALITY:
                raise WorkflowHostBlocked(message, reasons=classified["reasons"], stage="verify_receive")
            raise WorkflowHostError(message, reasons=classified["reasons"], stage="verify_receive")

        verified = _verify_ready_outputs(target, classified)
        bindings = _measure_bindings(target)
        _require(bindings["input_sha256"] == verified["materials"]["snapshot"]["sha256"],
                 "bindings.input_sha256", "必须与本批次快照一致", "measure_bindings")
        workflow = CONTROLLER_MODULE.create_dev_workflow(target.name, bindings)
        materials = {
            "batch_id": target.name,
            "gate": "GATE1",
            "run_bindings_sha256": CONTROLLER_MODULE.canonical_sha256(bindings),
            "scope": {**copy.deepcopy(GATE1_SCOPE_FIXED), "source_description": source_text,
                      "known_limitations": list(GATE1_LIMITATIONS)},
            "blocking_issues": [],
            "evidence": {
                "quality_report": verified["quality_report"],
                "workbook": {"path": "source/input.xlsx",
                             "sha256": verified["materials"]["snapshot"]["sha256"]},
                "checker": {"path": "code_snapshot/check_demo_data.py",
                            "sha256": verified["materials"]["checker_code"]["sha256"]},
            },
        }
        workflow = CONTROLLER_MODULE.prepare_dev_gate(workflow, "GATE1", materials, current_bindings=bindings)
        _require(workflow["state"]["phase"] == CONTROLLER_MODULE.PHASE_G1_PENDING, "workflow.state.phase",
                 "start 必须停在 DEV_GATE1_PENDING", "start")
        _require(not workflow["state"]["simulated_decisions"], "workflow.state.simulated_decisions",
                 "start 不得提交任何模拟决定", "start")

        host_manifest = {
            "manifest_version": HOST_MANIFEST_VERSION,
            "host_version": HOST_VERSION,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "status": STATUS_READY,
            "next_step_allowed": False,
            "gate1_approval": None,
            "gate2_approval": None,
            "batch_id": target.name,
            "created_at_utc": _now_utc(),
            "source": {
                "original_path": str(workbook),
                "file_name": workbook.name,
                "source_description": source_text,
                "source_description_note": "按调用方原字符串保存（含首尾空格与换行）；仅用 strip 判断空白。",
                "source_identity_note": "接收后恢复读取批次快照，不再切回外部路径。",
            },
            "receive": {
                "command": receive_result["command"],
                "exit_code": receive_result["exit_code"],
                "batch_status": verified["manifest"].get("batch_status"),
                "received_at_utc": verified["manifest"].get("received_at_utc"),
                "invocation_record": {
                    "path": f"{WORKFLOW_DIR}/{RECEIVE_INVOCATION}",
                    "sha256": logs[RECEIVE_INVOCATION]["sha256"],
                },
                "stdout_log": f"{WORKFLOW_DIR}/{RECEIVER_STDOUT}",
                "stderr_log": f"{WORKFLOW_DIR}/{RECEIVER_STDERR}",
                "material_logs": logs,
                "materials": verified["materials"],
            },
            "bindings": bindings,
            "bindings_sha256": CONTROLLER_MODULE.canonical_sha256(bindings),
            "gate1_request": {
                "request_id": workflow["state"]["requests"]["GATE1"]["request_id"],
                "materials_sha256": workflow["state"]["requests"]["GATE1"]["materials_sha256"],
                "scope": materials["scope"],
            },
            "checkpoints": [],
            "boundaries": [
                "本宿主只做开发态接收与 Gate1 暂停／恢复，不构成正式契约或 Gate 批准。",
                "真实 gate1_approval／gate2_approval 恒为 null；模拟决定另存并标记 SIMULATED_TEST_ONLY。",
                "本地哈希只证明字节一致，不证明来源真实，也不抵御同权限篡改。",
                "单一进程、单一操作者；不宣称断电持久性或多进程并发安全。",
            ],
        }
        manifest_file_hash = _write_exclusive_json(_host_manifest_path(target), host_manifest, "start")

        _ensure_dir(_checkpoints_dir(target), "start")
        checkpoint = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "revision": 1,
            "previous_file_sha256": None,
            "batch_id": target.name,
            "host_manifest_file_sha256": manifest_file_hash,
            "workflow": workflow,
            "operation": {
                "kind": "START_GATE1_REQUEST",
                "at_utc": _now_utc(),
                "receiver_exit_code": receive_result["exit_code"],
                "receiver_command": receive_result["command"],
                "bindings_sha256": host_manifest["bindings_sha256"],
                "request_id": workflow["state"]["requests"]["GATE1"]["request_id"],
            },
        }
        checkpoint_file_hash = _write_exclusive_json(_checkpoint_path(target, 1), checkpoint, "start")

        # 写后收尾：重新核验 checkpoint 协议与文件，并重新实测绑定
        context = _load_host_context(target, stage="start")
        _require(context["chain"]["current_file_sha256"] == checkpoint_file_hash, "checkpoint",
                 "写后读回的当前 checkpoint 字节哈希与写入结果不一致", "start")
        _require(canonical_json(context["measured_bindings"]) == canonical_json(bindings), "bindings",
                 "提交后重新实测的绑定与操作前不一致（保存现场并拒绝成功宣告）", "start")

        return {
            "host_version": HOST_VERSION,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "status": STATUS_READY,
            "next_step_allowed": False,
            "batch_id": target.name,
            "batch_dir": str(target),
            "phase": workflow["state"]["phase"],
            "state_sha256": workflow["state_sha256"],
            "receive": {"command": receive_result["command"], "exit_code": receive_result["exit_code"],
                        "batch_status": verified["manifest"].get("batch_status")},
            "verified_files": {label: info["sha256"] for label, info in verified["materials"].items()},
            "bindings_sha256": host_manifest["bindings_sha256"],
            "host_manifest": {"path": f"{WORKFLOW_DIR}/{HOST_MANIFEST_NAME}",
                              "file_sha256": manifest_file_hash},
            "checkpoint": {"path": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0001.json",
                           "file_sha256": checkpoint_file_hash, "revision": 1},
            "simulated_decisions": 0,
            "real_approvals": 0,
        }
    except WorkflowHostBlocked as exc:
        if progress["receive_result"] is not None and progress["receive_result"]["exit_code"] == 0:
            _save_host_layer_failure(target, progress["receive_result"], progress["logs"],
                                     progress["receive_manifest"], source_text, workbook, exc)
        raise
    except WorkflowHostError as exc:
        if progress["receive_result"] is not None and progress["receive_result"]["exit_code"] == 0:
            _save_host_layer_failure(target, progress["receive_result"], progress["logs"],
                                     progress["receive_manifest"], source_text, workbook, exc)
        raise
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        raise WorkflowHostBlocked(f"[start] 冻结控制器阻断：{exc}", stage="start") from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        raise WorkflowHostError(f"[start] 冻结控制器意外错误：{exc}", stage="start") from exc
    except Exception as exc:  # noqa: BLE001
        wrapped = WorkflowHostError(f"[start] 意外运行失败：{type(exc).__name__}: {exc}",
                                    ["阶段=start", f"原始异常={type(exc).__name__}: {exc}"], "start")
        if progress["receive_result"] is not None and progress["receive_result"]["exit_code"] == 0:
            try:
                _save_host_layer_failure(target, progress["receive_result"], progress["logs"],
                                         progress["receive_manifest"], source_text, workbook, wrapped)
            except Exception:  # noqa: BLE001 - 保存失败已在内部报告
                pass
        raise wrapped from exc


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def _screen_dir(batch_dir: Path) -> Path:
    return _host_workflow_dir(batch_dir) / SCREEN_DIR


def _screen_paths(batch_dir: Path) -> dict:
    directory = _screen_dir(batch_dir)
    return {"dir": directory, "relative": f"{WORKFLOW_DIR}/{SCREEN_DIR}",
            "started_path": directory / SCREEN_START,
            "report_path": directory / SCREEN_REPORT,
            "artifacts_path": directory / SCREEN_ARTIFACTS,
            "failure_path": directory / SCREEN_FAILURE}


def _screen_observed_state(batch_dir: Path) -> dict:
    """如实记录本次筛查尝试已产生的输出状态（不补造成功信息）。"""
    directory = _screen_dir(batch_dir)
    observed = {"screening_dir_exists": directory.exists(), "files": {}}
    if directory.exists():
        for item in sorted(directory.iterdir(), key=lambda entry: entry.name):
            observed["files"][item.name] = ({"exists": True, "is_file": item.is_file(),
                                             "bytes": item.stat().st_size} if item.is_file()
                                            else {"exists": True, "is_file": False})
    return observed


def _save_screen_failure(batch_dir: Path, stage_label: str, exc: Exception, observed: dict) -> str:
    """尽力独占保存本次筛查失败诊断；写不成时如实抛出，不宣称已保存。"""
    payload = {
        "failure_version": SCREEN_FAILURE_VERSION,
        "batch_id": batch_dir.name,
        "host_version": HOST_VERSION,
        "recorded_at_utc": _now_utc(),
        "stage": stage_label,
        "exception_class": type(exc).__name__,
        "message": str(exc),
        "reasons": [str(item) for item in getattr(exc, "reasons", []) or [str(exc)]],
        "target_exit_code": (EXIT_ERROR if type(exc).__name__ in SCREEN_RUNTIME_FAILURE_CLASSES
                             else EXIT_BLOCKED),
        "observed_outputs": observed,
        "note": ("本次规则筛查未完成：保留已产生的文件，不自动删除、不重试、不补造成功报告；"
                 "需继续时新建批次。"),
    }
    path = _screen_dir(batch_dir) / SCREEN_FAILURE
    if path.exists():
        raise WorkflowHostError(f"失败诊断已存在，不覆盖：{path}", stage=stage_label)
    return _write_exclusive_json(path, payload, stage_label)


def _load_screen_failure(batch_dir: Path, stage: str):
    """读取并校验筛查失败诊断；不存在返回 None；非法／不完整一律协议阻断。"""
    path = _screen_dir(batch_dir) / SCREEN_FAILURE
    label = f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_FAILURE}"
    if not path.exists():
        return None
    _require(path.is_file(), label, f"必须是非目录的普通文件（实际 {path}）", stage)
    failure = _read_json(path, label, stage)
    _require_keys(failure, ("failure_version", "batch_id", "host_version", "recorded_at_utc",
                            "stage", "exception_class", "message", "reasons", "target_exit_code"),
                  label, stage)
    _require(failure["failure_version"] == SCREEN_FAILURE_VERSION, f"{label}.failure_version",
             f"必须是受支持的固定值 {SCREEN_FAILURE_VERSION}，实际 {failure['failure_version']!r}",
             stage)
    _require_str(failure["batch_id"], f"{label}.batch_id", stage)
    _require(failure["batch_id"] == batch_dir.name, f"{label}.batch_id",
             f"必须等于当前批次叶子 {batch_dir.name!r}，实际 {failure['batch_id']!r}", stage)
    _require_str(failure["host_version"], f"{label}.host_version", stage)
    _require(failure["host_version"] == HOST_VERSION, f"{label}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}，实际 {failure['host_version']!r}", stage)
    _require_str(failure["recorded_at_utc"], f"{label}.recorded_at_utc", stage)
    _require_str(failure["stage"], f"{label}.stage", stage)
    _require_str(failure["exception_class"], f"{label}.exception_class", stage)
    _require_str(failure["message"], f"{label}.message", stage)
    _require(isinstance(failure["target_exit_code"], int)
             and not isinstance(failure["target_exit_code"], bool),
             f"{label}.target_exit_code",
             f"必须是严格整数（排除 bool/float），实际 {type(failure['target_exit_code']).__name__}",
             stage)
    _require(failure["target_exit_code"] in (EXIT_BLOCKED, EXIT_ERROR), f"{label}.target_exit_code",
             f"必须是 1 或 2，实际 {failure['target_exit_code']!r}", stage)
    _require(isinstance(failure["reasons"], list) and failure["reasons"], f"{label}.reasons",
             f"必须是非空原因列表，实际 {failure['reasons']!r}", stage)
    for index, item in enumerate(failure["reasons"]):
        _require_str(item, f"{label}.reasons[{index}]", stage)
    _require(isinstance(failure.get("observed_outputs"), dict), f"{label}.observed_outputs",
             "必须是对象（如实记录已观察到的输出状态）", stage)
    return failure


def _screen_failure_exception(failure: dict) -> Exception:
    """失败类别按语义映射：运行失败 exit 2，其余协议阻断 exit 1；不得恢复 READY。"""
    reasons = [str(item) for item in failure["reasons"]]
    message = (f"该批次的 {WORKFLOW_DIR}/{SCREEN_DIR}/ 记录了未完成的筛查尝试："
               f"stage={failure['stage']!r}；异常类别={failure['exception_class']!r}；原因={reasons!r}。"
               "即使存在可解析的完整 0005，也不得宣告本次筛查成功；不重试、不复用、不自动删除，"
               "需继续时新建批次。")
    if failure["target_exit_code"] == EXIT_ERROR:
        return WorkflowHostError(message, reasons=reasons, stage=failure["stage"])
    return WorkflowHostBlocked(message, reasons=reasons, stage=failure["stage"])


def _raise_incomplete_screen(batch_dir: Path, chain: dict) -> None:
    """workflow/screening/ 已开始但没有完整有效的 0005：说明筛查未完成并拒绝继续。"""
    revision = chain["current"]["revision"]
    raise WorkflowHostBlocked(
        f"该批次的 {WORKFLOW_DIR}/{SCREEN_DIR}/ 已开始但没有完整有效的 0005"
        f"（当前为第 {revision} 份 checkpoint）：筛查未完成。不重试、不复用、不自动删除，"
        "不猜测成功、不退回旧状态，需继续时新建批次。", stage="status")


def _read_screen_outputs(batch_dir: Path, stage: str) -> dict:
    """从固定路径实读本次筛查产物（不跟随清单访问任意路径）。"""
    paths = _screen_paths(batch_dir)
    for path, label in ((paths["started_path"], SCREEN_START),
                        (paths["report_path"], SCREEN_REPORT),
                        (paths["artifacts_path"], SCREEN_ARTIFACTS)):
        _require(path.is_file(), f"{paths['relative']}/{label}",
                 f"缺少本次筛查产物文件（{path}）", stage)
    started, started_sha = _read_json_with_bytes(paths["started_path"],
                                                 f"{paths['relative']}/{SCREEN_START}", stage)
    report, report_sha = _read_json_with_bytes(paths["report_path"],
                                               f"{paths['relative']}/{SCREEN_REPORT}", stage)
    artifacts, artifacts_sha = _read_json_with_bytes(paths["artifacts_path"],
                                                     f"{paths['relative']}/{SCREEN_ARTIFACTS}", stage)
    return {"started": started, "report": report, "artifacts": artifacts,
            "started_file_sha256": started_sha, "report_file_sha256": report_sha,
            "artifacts_file_sha256": artifacts_sha}


def _require_int_cents(value, path: str, stage: str) -> None:
    """金额字段允许按实体嵌套，但每个叶子都必须是整数分（严格 int，排除 bool）。"""
    if isinstance(value, dict):
        for key in value:
            _require(isinstance(key, str), f"{path}.<key>",
                     f"金额映射的键必须是字符串，实际 {type(key).__name__}", stage)
            _require_int_cents(value[key], f"{path}.{key}", stage)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _require_int_cents(item, f"{path}[{index}]", stage)
        return
    _require(isinstance(value, int) and not isinstance(value, bool), path,
             f"必须是整数分（不允许 float／str／bool），实际 {type(value).__name__}: {value!r}", stage)


def _screen_report_protocol(report: dict, load_report: dict, database_path: Path,
                            manifest: dict, stage: str, label: str) -> str:
    """只核验筛查核心接口协议与来源绑定；不重新实现 R01—R04，也不独立复算。"""
    _require(isinstance(report, dict), label, f"必须是对象，实际 {type(report).__name__}", stage)
    _require_keys(report, SCREEN_REPORT_REQUIRED_KEYS, label, stage)
    _require(report["batch_status"] == SCREEN_MODULE.RULES_STATUS, f"{label}.batch_status",
             f"必须是 {SCREEN_MODULE.RULES_STATUS}，实际 {report['batch_status']!r}", stage)
    _require(report["mode"] == MODE, f"{label}.mode", f"必须是 {MODE}", stage)
    _require(report["next_step_allowed"] is False, f"{label}.next_step_allowed",
             "必须是严格 false", stage)
    _require(report["rule_core_version"] == SCREEN_MODULE.RULE_CORE_VERSION,
             f"{label}.rule_core_version",
             f"必须是 {SCREEN_MODULE.RULE_CORE_VERSION}，实际 {report['rule_core_version']!r}", stage)
    _require(report["cutoff_date"] == SCREEN_CUTOFF_DATE, f"{label}.cutoff_date",
             f"必须是 {SCREEN_CUTOFF_DATE}，实际 {report['cutoff_date']!r}", stage)
    _require(report["database_path"] == str(database_path), f"{label}.database_path",
             f"必须等于宿主推导的固定路径 {database_path}", stage)
    database_sha = file_sha256(database_path)
    _require(report["database_sha256_before"] == database_sha, f"{label}.database_sha256_before",
             "必须等于宿主本次实读数据库字节哈希", stage)
    _require(report["database_sha256_after"] == database_sha, f"{label}.database_sha256_after",
             "必须等于宿主本次实读数据库字节哈希（前后一致）", stage)
    _require(report["database_unchanged"] is True, f"{label}.database_unchanged",
             "必须是 true（只读筛查不得改写数据库）", stage)
    read_only = report["read_only"]
    _require(isinstance(read_only, dict) and read_only.get("uri_mode") == "ro"
             and read_only.get("query_only") == 1, f"{label}.read_only",
             f"必须是只读模式（uri_mode=ro、query_only=1），实际 {read_only!r}", stage)
    period = report["period"]
    _require(isinstance(period, dict), f"{label}.period", "必须是对象", stage)
    _require(period.get("period_start") == SCREEN_MODULE.PERIOD_START
             and period.get("period_end") == SCREEN_MODULE.PERIOD_END
             and period.get("range_ok") is True, f"{label}.period",
             f"必须覆盖 {SCREEN_MODULE.PERIOD_START}—{SCREEN_MODULE.PERIOD_END} 且 range_ok=true，"
             f"实际 {period!r}", stage)
    load_source = report["load_source"]
    _require(isinstance(load_source, dict), f"{label}.load_source", "必须是对象", stage)
    for key, expected in (("batch_status", load_report.get("batch_status")),
                          ("store_version", load_report.get("store_version")),
                          ("schema_version", load_report.get("schema_version"))):
        _require(load_source.get(key) == expected, f"{label}.load_source.{key}",
                 f"必须与本批次装载报告一致：期望 {expected!r}，实际 {load_source.get(key)!r}", stage)
    source = load_report.get("source") or {}
    _require(load_source.get("input_sha256") == source.get("input_sha256"),
             f"{label}.load_source.input_sha256", "必须与本批次来源哈希一致", stage)
    _require(load_source.get("input_sha256") == manifest["bindings"]["input_sha256"],
             f"{label}.load_source.input_sha256", "必须与批次绑定来源哈希一致", stage)
    _require(load_source.get("normalized_payload_sha256") == load_report.get("normalized_payload_sha256"),
             f"{label}.load_source.normalized_payload_sha256", "必须与本批次 normalized 指纹一致", stage)
    _require(load_source.get("database_sha256") == database_sha,
             f"{label}.load_source.database_sha256", "必须等于宿主本次实读数据库字节哈希", stage)
    _require(isinstance(load_source.get("run_metadata"), dict), f"{label}.load_source.run_metadata",
             "必须是对象", stage)
    # 四份规则 SQL 的哈希与版本必须与冻结文件一致
    reconciliation = report["overall_reconciliation"]
    _require(isinstance(reconciliation, dict), f"{label}.overall_reconciliation", "必须是对象", stage)
    _require(reconciliation.get("unit") == "cents", f"{label}.overall_reconciliation.unit",
             f"必须是 cents，实际 {reconciliation.get('unit')!r}", stage)
    for key in ("settled_pay_master_total", "settled_refund_master_total", "master_net",
                "known_payable_link_net", "missing_payable_link_net"):
        _require(isinstance(reconciliation.get(key), int)
                 and not isinstance(reconciliation.get(key), bool),
                 f"{label}.overall_reconciliation.{key}",
                 f"必须是整数分，实际 {reconciliation.get(key)!r}", stage)
    _require(isinstance(reconciliation.get("missing_payable_link_detail"), dict),
             f"{label}.overall_reconciliation.missing_payable_link_detail", "必须是对象", stage)
    _require(reconciliation.get("master_net_equals_known_plus_missing") is True,
             f"{label}.overall_reconciliation.master_net_equals_known_plus_missing",
             "必须是 true（只读声明，宿主不重算规则）", stage)
    _require(reconciliation.get("matches_load_report") is True,
             f"{label}.overall_reconciliation.matches_load_report",
             "必须是 true（与装载报告勾稽一致）", stage)

    rules = report["rules"]
    _require(isinstance(rules, dict), f"{label}.rules", "必须是对象", stage)
    for rule_id in SCREEN_MODULE.RULE_IDS:
        entry = rules.get(rule_id)
        _require(isinstance(entry, dict), f"{label}.rules.{rule_id}", "必须是对象", stage)
        _require_keys(entry, ("rule_version", "sql_path", "sql_sha256", "hit_count"),
                      f"{label}.rules.{rule_id}", stage)
        expected_sql = PROJECT_ROOT / "sql" / "rules" / f"{rule_id.lower()}.sql"
        _require(entry["sql_path"] == str(expected_sql), f"{label}.rules.{rule_id}.sql_path",
                 f"必须是固定路径 {expected_sql}", stage)
        _require(entry["sql_sha256"] == manifest["bindings"]["rule_sql_sha256"][rule_id],
                 f"{label}.rules.{rule_id}.sql_sha256",
                 "必须与本次实测的规则 SQL 哈希一致（不得使用与本次无关的 SQL）", stage)
        _require(entry["rule_version"] == SCREEN_MODULE.RULE_VERSIONS[rule_id],
                 f"{label}.rules.{rule_id}.rule_version",
                 f"必须是 {SCREEN_MODULE.RULE_VERSIONS[rule_id]}", stage)
    hit_counts = report["rule_hit_counts"]
    _require(isinstance(hit_counts, dict), f"{label}.rule_hit_counts", "必须是对象", stage)
    total = 0
    for rule_id in SCREEN_MODULE.RULE_IDS:
        value = hit_counts.get(rule_id)
        _require(isinstance(value, int) and not isinstance(value, bool), f"{label}.rule_hit_counts.{rule_id}",
                 f"必须是非负整数，实际 {value!r}", stage)
        _require(value >= 0, f"{label}.rule_hit_counts.{rule_id}", "必须非负", stage)
        _require(rules[rule_id]["hit_count"] == value, f"{label}.rules.{rule_id}.hit_count",
                 "必须与 rule_hit_counts 一致", stage)
        total += value
    _require(hit_counts.get("total") == total, f"{label}.rule_hit_counts.total",
             f"必须等于四规则命中数之和 {total}", stage)
    findings = report["findings"]
    _require(isinstance(findings, list), f"{label}.findings", "必须是列表", stage)
    _require(len(findings) == total, f"{label}.findings",
             f"条数必须等于命中总数 {total}，实际 {len(findings)}", stage)
    for index, item in enumerate(findings):
        _require(isinstance(item, dict), f"{label}.findings[{index}]", "必须是对象", stage)
        _require(item.get("rule_id") in SCREEN_MODULE.RULE_IDS, f"{label}.findings[{index}].rule_id",
                 f"必须是 {list(SCREEN_MODULE.RULE_IDS)} 之一，实际 {item.get('rule_id')!r}", stage)
        _require(isinstance(item.get("amounts_cents"), dict), f"{label}.findings[{index}].amounts_cents",
                 "必须是对象（金额为整数分）", stage)
        _require_int_cents(item["amounts_cents"], f"{label}.findings[{index}].amounts_cents", stage)
    statistics = report["statistics"]
    _require(isinstance(statistics, dict), f"{label}.statistics", "必须是对象", stage)
    _require(statistics.get("rule_amounts_not_summed_as_loss") is True,
             f"{label}.statistics.rule_amounts_not_summed_as_loss",
             "必须是 true（跨规则金额不相加）", stage)
    involved = statistics.get("involved_payments")
    _require(isinstance(involved, dict), f"{label}.statistics.involved_payments", "必须是对象", stage)
    _require(isinstance(involved.get("count"), int) and not isinstance(involved.get("count"), bool)
             and involved["count"] >= 0, f"{label}.statistics.involved_payments.count",
             f"必须是非负整数，实际 {involved.get('count')!r}", stage)
    _require(isinstance(involved.get("payment_ids"), list)
             and all(isinstance(item, str) for item in involved["payment_ids"]),
             f"{label}.statistics.involved_payments.payment_ids", "必须是字符串列表", stage)
    _require(isinstance(involved.get("settled_amount_cents"), int)
             and not isinstance(involved.get("settled_amount_cents"), bool),
             f"{label}.statistics.involved_payments.settled_amount_cents",
             f"必须是整数分，实际 {involved.get('settled_amount_cents')!r}", stage)
    _require(isinstance(involved.get("note"), str) and involved["note"],
             f"{label}.statistics.involved_payments.note", "必须是非空口径说明", stage)
    overpayment = statistics.get("r02_overpayment_total_cents")
    _require(isinstance(overpayment, int) and not isinstance(overpayment, bool),
             f"{label}.statistics.r02_overpayment_total_cents",
             f"必须是整数分，实际 {overpayment!r}", stage)
    _require(statistics.get("r02_overpayment_basis"), f"{label}.statistics.r02_overpayment_basis",
             "必须存在（避免重复计算的口径说明）", stage)
    expected_overpayment = sum(item["amounts_cents"].get("overpayment", 0)
                               for item in findings if item["rule_id"] == "R02")
    _require(overpayment == expected_overpayment, f"{label}.statistics.r02_overpayment_total_cents",
             f"必须等于 R02 命中金额合计 {expected_overpayment}", stage)
    _require(isinstance(report["limits"], list) and report["limits"], f"{label}.limits",
             "必须是非空范围限制列表", stage)
    return canonical_sha256(report)


def _verify_screen_tail(batch_dir: Path, expected: dict, stage: str) -> dict:
    """筛查收尾一致性：复测 screening 产物与本次引用（固定路径，不跟随清单）。"""
    paths = _screen_paths(batch_dir)
    actual = {
        "started_file_sha256": file_sha256(paths["started_path"]),
        "report_file_sha256": file_sha256(paths["report_path"]),
        "artifacts_file_sha256": file_sha256(paths["artifacts_path"]),
    }
    for key, value in actual.items():
        label = {"started_file_sha256": f"{paths['relative']}/{SCREEN_START}",
                 "report_file_sha256": f"{paths['relative']}/{SCREEN_REPORT}",
                 "artifacts_file_sha256": f"{paths['relative']}/{SCREEN_ARTIFACTS}"}[key]
        _require(expected.get(key) == value, label,
                 f"收尾复测发现本次筛查产物发生变化：期望 {expected.get(key)!r}，实际 {value!r}", stage)
    database_path = expected.get("database_path") or expected.get("gate2_database_path")
    database_sha = expected.get("database_sha256") or expected.get("gate2_database_sha256")
    _require(isinstance(database_path, str), "screening.expected.database_path",
             "收尾复测必须带出固定数据库路径", stage)
    _require(isinstance(database_sha, str), "screening.expected.database_sha256",
             "收尾复测必须带出数据库字节哈希预期", stage)
    got_db = file_sha256(Path(database_path))
    _require(database_sha == got_db, str(database_path),
             f"收尾复测发现数据库字节变化：期望 {database_sha!r}，实际 {got_db!r}",
             stage)
    failure_path = paths["failure_path"]
    _require(not failure_path.exists(), f"{paths['relative']}/{SCREEN_FAILURE}",
             "成功收尾不得存在失败诊断", stage)
    for name in sorted(item.name for item in paths["dir"].iterdir()):
        _require(name in (SCREEN_START, SCREEN_REPORT, SCREEN_ARTIFACTS),
                 f"{paths['relative']}/{name}", "成功批次的筛查目录只允许既定产物文件", stage)
    return actual


def _verify_screen_operation(payload: dict, previous_payload: dict, state: dict, label: str,
                             stage: str, batch_dir: Path, manifest: dict, *,
                             previous_file_sha256: str, gate2_expected,
                             host_manifest_file_sha256: str) -> None:
    """0005 只允许从合法 DEV_GATE2_APPROVED 的 0004 延续一次只读规则筛查。"""
    operation = payload["operation"]
    _require(operation.get("kind") == OPERATION_RUN_RULE_SCREEN, f"{label}.operation.kind",
             f"0005 必须是 {OPERATION_RUN_RULE_SCREEN}，实际 {operation.get('kind')!r}", stage)
    _require_keys(operation, ("at_utc", "artifacts", "artifacts_file_sha256",
                              "report_file_sha256", "report_canonical_sha256", "database_sha256",
                              "started_file_sha256", "phase_after", "bindings_sha256",
                              "report_relative", "artifacts_relative"), f"{label}.operation", stage)
    previous_workflow = previous_payload["workflow"]
    previous_state = previous_workflow["state"]
    _require(previous_state["phase"] == CONTROLLER_MODULE.PHASE_G2_APPROVED, f"{label}.previous.phase",
             f"0005 只能从 {CONTROLLER_MODULE.PHASE_G2_APPROVED} 的 0004 延续，实际 "
             f"{previous_state['phase']!r}", stage)
    _require(canonical_json(state) == canonical_json(previous_state), f"{label}.workflow.state",
             "0005 的 workflow 必须与 0004 严格相等（筛查不改变控制器状态、不新增决定或请求）",
             stage)
    _require(canonical_json(payload["workflow"]) == canonical_json(previous_workflow),
             f"{label}.workflow", "0005 的完整 workflow 必须与 0004 严格相等", stage)
    decisions = state["simulated_decisions"]
    _require(isinstance(decisions, list) and len(decisions) == 2, f"{label}.state.simulated_decisions",
             f"模拟决定必须恰为 Gate1 与 Gate2 两条，实际 {len(decisions) if isinstance(decisions, list) else decisions!r}",
             stage)
    _require(operation["phase_after"] == state["phase"], f"{label}.operation.phase_after",
             "操作摘要的 phase 必须与实际状态一致", stage)
    _require(operation["bindings_sha256"] == state["run_bindings_sha256"],
             f"{label}.operation.bindings_sha256", "必须与 workflow 绑定一致", stage)
    _require(state["batch_id"] == payload["batch_id"], f"{label}.workflow.state.batch_id",
             "workflow 批次必须与 checkpoint 一致", stage)

    # 0003 的材料核验保留到 0005 恢复：不跳过 Gate2 产物与数据库核验
    _require(isinstance(gate2_expected, dict) and bool(gate2_expected), f"{label}.gate2_expected",
             "0005 恢复必须带出 0003 的初次材料核验读数（不得跳过数据库与产物核验）", stage)
    outputs = _read_gate2_outputs(batch_dir, stage)
    paths = _gate2_paths(batch_dir, stage)
    actual_database_sha = file_sha256(paths["database_path"])
    for key, value, field in (
        ("normalized_file_sha256", outputs["normalized_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}"),
        ("load_report_file_sha256", outputs["load_report_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}"),
        ("artifacts_file_sha256", outputs["artifacts_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"),
        ("database_sha256", actual_database_sha, str(paths["database_path"])),
    ):
        _require(gate2_expected.get(key) == value, field,
                 f"Gate2 材料在筛查恢复时发生了变化：期望 {gate2_expected.get(key)!r}，实际 {value!r}",
                 stage)

    screen = _read_screen_outputs(batch_dir, stage)
    started = screen["started"]
    _require_keys(started, ("start_version", "batch_id", "host_version", "operation_kind",
                            "at_utc", "source_checkpoint_file_sha256", "run_bindings_sha256"),
                  f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}", stage)
    _require(started["start_version"] == SCREEN_START_VERSION,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}.start_version",
             f"必须是 {SCREEN_START_VERSION}，实际 {started['start_version']!r}", stage)
    _require(started["batch_id"] == batch_dir.name,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}.batch_id",
             "必须与批次目录叶子一致", stage)
    _require(isinstance(started["host_version"], str),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}.host_version",
             f"必须是字符串，实际 {type(started['host_version']).__name__}", stage)
    _require(started["host_version"] == HOST_VERSION,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}，实际 {started['host_version']!r}", stage)
    _require(started["operation_kind"] == OPERATION_RUN_RULE_SCREEN,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}.operation_kind",
             f"必须是 {OPERATION_RUN_RULE_SCREEN}", stage)
    _require(started["source_checkpoint_file_sha256"] == previous_file_sha256,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}.source_checkpoint_file_sha256",
             "必须等于 0004 的初始实读字节哈希", stage)
    _require(started["run_bindings_sha256"] == state["run_bindings_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}.run_bindings_sha256",
             "必须等于 workflow 创建绑定指纹", stage)

    artifacts = screen["artifacts"]
    _require_keys(artifacts, ("artifacts_version", "batch_id", "host_version",
                             "report_relative", "report_file_sha256", "report_canonical_sha256",
                             "started_file_sha256", "previous_checkpoint_file_sha256",
                             "host_manifest_file_sha256", "normalized_file_sha256",
                             "load_report_file_sha256", "gate2_artifacts_file_sha256",
                             "normalized_payload_sha256", "database_path", "database_sha256",
                             "rule_core_path", "rule_core_sha256", "rule_core_version",
                             "rule_sql_sha256", "cutoff_date", "run_bindings_sha256",
                             "gate2_decision_sha256", "created_at_utc"),
                  f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}", stage)
    _require(artifacts["artifacts_version"] == SCREEN_ARTIFACTS_VERSION,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.artifacts_version",
             f"必须是 {SCREEN_ARTIFACTS_VERSION}", stage)
    for key, fixed in (("report_relative", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}"),
                       ("artifacts_relative", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}")):
        _require(isinstance(operation[key], str), f"{label}.operation.{key}",
                 f"必须是固定相对路径字符串，实际 {type(operation[key]).__name__}", stage)
        _require(operation[key] == fixed, f"{label}.operation.{key}",
                 f"必须是固定相对路径 {fixed!r}，实际 {operation[key]!r}", stage)
    _require(isinstance(operation["artifacts"], dict), f"{label}.operation.artifacts",
             f"必须是对象（内嵌 artifacts 完整副本），实际 {type(operation['artifacts']).__name__}",
             stage)
    _require(artifacts["batch_id"] == batch_dir.name,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.batch_id", "必须与批次一致", stage)
    _require(isinstance(artifacts["host_version"], str),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.host_version",
             f"必须是字符串，实际 {type(artifacts['host_version']).__name__}", stage)
    _require(artifacts["host_version"] == HOST_VERSION,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}，实际 {artifacts['host_version']!r}", stage)
    _require(artifacts["previous_checkpoint_file_sha256"] == previous_file_sha256,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.previous_checkpoint_file_sha256",
             "必须等于 0004 的初始实读字节哈希", stage)
    _require(isinstance(host_manifest_file_sha256, str) and bool(host_manifest_file_sha256),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.host_manifest_file_sha256",
             "恢复时必须带出初始实读的宿主清单文件字节哈希（不得用 bindings 内容指纹替代）", stage)
    _require(artifacts["host_manifest_file_sha256"] == host_manifest_file_sha256,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.host_manifest_file_sha256",
             f"必须等于初始实读宿主清单文件字节哈希 {host_manifest_file_sha256!r}，"
             f"实际 {artifacts['host_manifest_file_sha256']!r}", stage)

    # 报告：只核协议与来源绑定（不重新实现 R01—R04）
    report_sha = _screen_report_protocol(screen["report"], outputs["load_report"],
                                         paths["database_path"], manifest, stage,
                                         f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}")
    _require(operation["report_file_sha256"] == screen["report_file_sha256"],
             f"{label}.operation.report_file_sha256", "必须等于报告文件实际字节哈希", stage)
    _require(operation["report_canonical_sha256"] == report_sha,
             f"{label}.operation.report_canonical_sha256", "必须等于报告对象实际规范指纹", stage)
    _require(artifacts["report_file_sha256"] == screen["report_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.report_file_sha256",
             "必须等于报告文件实际字节哈希", stage)
    _require(artifacts["report_canonical_sha256"] == report_sha,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.report_canonical_sha256",
             "必须等于报告对象实际规范指纹", stage)
    _require(artifacts["report_relative"] == f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}",
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.report_relative",
             "必须是固定相对路径", stage)
    _require(artifacts["started_file_sha256"] == screen["started_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.started_file_sha256",
             "必须等于 started 文件实际字节哈希", stage)
    _require(operation["started_file_sha256"] == screen["started_file_sha256"],
             f"{label}.operation.started_file_sha256", "必须等于 started 文件实际字节哈希", stage)
    _require(operation["artifacts_file_sha256"] == screen["artifacts_file_sha256"],
             f"{label}.operation.artifacts_file_sha256", "必须等于 artifacts 文件实际字节哈希", stage)
    _require(operation["database_sha256"] == actual_database_sha, f"{label}.operation.database_sha256",
             "必须等于数据库实际字节哈希", stage)
    _require(artifacts["database_path"] == str(paths["database_path"]),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.database_path",
             "必须是宿主推导的固定数据库路径", stage)
    _require(artifacts["database_sha256"] == actual_database_sha,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.database_sha256",
             "必须等于数据库实际字节哈希", stage)
    _require(artifacts["normalized_file_sha256"] == outputs["normalized_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.normalized_file_sha256",
             "必须等于本次实读 normalized 文件字节哈希", stage)
    _require(artifacts["load_report_file_sha256"] == outputs["load_report_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.load_report_file_sha256",
             "必须等于本次实读装载报告文件字节哈希", stage)
    _require(artifacts["gate2_artifacts_file_sha256"] == outputs["artifacts_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.gate2_artifacts_file_sha256",
             "必须等于本次实读 Gate2 artifacts 文件字节哈希", stage)
    _require(artifacts["normalized_payload_sha256"] == outputs["load_report"].get("normalized_payload_sha256"),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.normalized_payload_sha256",
             "必须等于本批次 normalized 对象指纹", stage)
    _require(artifacts["rule_core_path"] == str(SCREENING_CORE_PATH),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.rule_core_path",
             "必须是冻结筛查核心固定路径", stage)
    _require(artifacts["rule_core_sha256"] == manifest["bindings"]["code_sha256"]["screen_demo_sqlite"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.rule_core_sha256",
             "必须等于冻结筛查核心实际字节哈希（不得使用与本次无关的核心）", stage)
    _require(artifacts["rule_core_version"] == SCREEN_MODULE.RULE_CORE_VERSION,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.rule_core_version",
             f"必须是 {SCREEN_MODULE.RULE_CORE_VERSION}", stage)
    _require(artifacts["rule_sql_sha256"] == manifest["bindings"]["rule_sql_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.rule_sql_sha256",
             "必须逐份等于本次实测的四份规则 SQL 哈希", stage)
    _require(artifacts["cutoff_date"] == SCREEN_CUTOFF_DATE,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.cutoff_date",
             f"必须是 {SCREEN_CUTOFF_DATE}", stage)
    _require(artifacts["run_bindings_sha256"] == state["run_bindings_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.run_bindings_sha256",
             "必须等于 workflow 创建绑定指纹", stage)
    gate2_body_sha = canonical_sha256({key: value for key, value in decisions[-1].items()
                                       if key != "decision_sha256"})
    _require(artifacts["gate2_decision_sha256"] == gate2_body_sha,
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}.gate2_decision_sha256",
             "必须等于本 workflow 已验证 Gate2 APPROVE 正文指纹（剥离派生字段）", stage)
    _require(decisions[-1].get("decision") == CONTROLLER_MODULE.DECISION_APPROVE,
             f"{label}.state.simulated_decisions[-1].decision",
             f"只允许在显式模拟 {CONTROLLER_MODULE.DECISION_APPROVE} 后筛查，实际 "
             f"{decisions[-1].get('decision')!r}", stage)
    # 内嵌副本先验形状，再与实际已验证 artifacts 完整严格相等（不得作为第二套矛盾来源）
    embedded = operation["artifacts"]
    _require_keys(embedded, ("artifacts_version", "batch_id", "host_version", "report_relative",
                            "report_file_sha256", "report_canonical_sha256", "started_file_sha256",
                            "previous_checkpoint_file_sha256", "host_manifest_file_sha256",
                            "normalized_file_sha256", "load_report_file_sha256",
                            "gate2_artifacts_file_sha256", "normalized_payload_sha256",
                            "database_path", "database_sha256", "rule_core_path", "rule_core_sha256",
                            "rule_core_version", "rule_sql_sha256", "cutoff_date",
                            "run_bindings_sha256", "gate2_decision_sha256", "created_at_utc"),
                  f"{label}.operation.artifacts", stage)
    _require(canonical_json(embedded) == canonical_json(artifacts), f"{label}.operation.artifacts",
             "内嵌 artifacts 副本必须与磁盘实际 artifacts 对象完整严格相等（不得留两套矛盾来源）",
             stage)
    # 0005 自己的核验读数交给 0006 使用（不得用链尾 0006 的哈希代替）。
    # 注意键名：artifacts 指 screening/artifacts.json；Gate2 的 artifacts.json 才是 gate2_artifacts。
    return {
        "started_file_sha256": screen["started_file_sha256"],
        "report_file_sha256": screen["report_file_sha256"],
        "artifacts_file_sha256": screen["artifacts_file_sha256"],
        "gate2_database_path": str(paths["database_path"]),
        "gate2_database_sha256": actual_database_sha,
        "gate2_normalized_file_sha256": outputs["normalized_file_sha256"],
        "gate2_load_report_file_sha256": outputs["load_report_file_sha256"],
        "gate2_artifacts_file_sha256": outputs["artifacts_file_sha256"],
    }
    


def _crosscheck_dir(batch_dir: Path) -> Path:
    return _host_workflow_dir(batch_dir) / CROSSCHECK_DIR


def _crosscheck_paths(batch_dir: Path) -> dict:
    directory = _crosscheck_dir(batch_dir)
    return {"directory": directory, "dir": directory,
            "relative": f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}",
            "started_path": directory / CROSSCHECK_START,
            "report_path": directory / CROSSCHECK_REPORT,
            "artifacts_path": directory / CROSSCHECK_ARTIFACTS,
            "failure_path": directory / CROSSCHECK_FAILURE}


def _crosscheck_observed_state(batch_dir: Path) -> dict:
    """尽力采集失败现场的已知产物引用（只读、不存在即记 null）。"""
    paths = _crosscheck_paths(batch_dir)
    observed = {"directory_exists": paths["directory"].exists()}
    for key, path in (("started", paths["started_path"]), ("report", paths["report_path"]),
                      ("artifacts", paths["artifacts_path"]), ("failure", paths["failure_path"])):
        observed[f"{key}_present"] = path.is_file()
        try:
            observed[f"{key}_file_sha256"] = file_sha256(path) if path.is_file() else None
        except OSError:
            observed[f"{key}_file_sha256"] = None
    return observed


def _save_crosscheck_failure(batch_dir: Path, stage_label: str, exc: Exception,
                             observed: dict) -> str:
    """本次真正创建了 crosscheck 目录之后才写失败诊断（独占创建，不覆盖、不留半文件）。"""
    paths = _crosscheck_paths(batch_dir)
    _ensure_dir(paths["directory"], stage_label)
    target_exit_code = (EXIT_ERROR if type(exc).__name__ in CROSSCHECK_RUNTIME_FAILURE_CLASSES
                        else EXIT_BLOCKED)
    observed = dict(observed or {})
    # 读回核验要求 observed_outputs 内也带严格整数目标退出码（与顶层一致）
    observed["target_exit_code"] = target_exit_code
    observed["exception_class"] = type(exc).__name__
    exception_chain = getattr(exc, "original_exception_chain", None) or _exception_chain(exc)
    payload = {
        "failure_version": CROSSCHECK_FAILURE_VERSION,
        "batch_id": batch_dir.name,
        "host_version": HOST_VERSION,
        "recorded_at_utc": _now_utc(),
        "stage": stage_label,
        "exception_class": type(exc).__name__,
        "target_exit_code": target_exit_code,
        "message": str(exc),
        "reasons": list(getattr(exc, "reasons", []) or [str(exc)]),
        "exception_chain": exception_chain,
        "observed_outputs": observed,
    }
    path = paths["failure_path"]
    if path.exists():
        raise WorkflowHostBlocked(f"失败诊断已存在，不覆盖：{paths['relative']}/{CROSSCHECK_FAILURE}",
                                  stage=stage_label)
    sha = _write_exclusive_json(path, payload, stage_label)
    readback, readback_sha = _read_json_with_bytes(path, f"{paths['relative']}/{CROSSCHECK_FAILURE}",
                                                   stage_label)
    _require(readback_sha == sha, f"{paths['relative']}/{CROSSCHECK_FAILURE}",
             "写后读回的失败诊断字节哈希与写入结果不一致", stage_label)
    _require(canonical_json(readback) == canonical_json(payload), f"{paths['relative']}/{CROSSCHECK_FAILURE}",
             "写后读回的失败诊断内容与写入结果不一致", stage_label)
    return sha


def _load_crosscheck_failure(batch_dir: Path, stage: str):
    """读取并严格核验失败诊断；不存在返回 None。"""
    paths = _crosscheck_paths(batch_dir)
    path = paths["failure_path"]
    if not path.exists():
        return None
    label = f"{paths['relative']}/{CROSSCHECK_FAILURE}"
    _require(path.is_file(), label, "失败诊断必须是普通文件", stage)
    payload = _read_json(path, label, stage)
    _require_keys(payload, ("failure_version", "batch_id", "host_version", "recorded_at_utc", "stage",
                            "exception_class", "target_exit_code", "message", "reasons",
                            "exception_chain", "observed_outputs"), label, stage)
    _require(isinstance(payload["exception_chain"], list) and bool(payload["exception_chain"]),
             f"{label}.exception_chain",
             "必须保存非空完整异常链（含原始 cause／context 的类别、消息与阶段）", stage)
    for link_index, link in enumerate(payload["exception_chain"]):
        _require(isinstance(link, dict) and isinstance(link.get("class"), str)
                 and isinstance(link.get("message"), str),
                 f"{label}.exception_chain[{link_index}]",
                 "每一环必须是含 class 与 message 字符串的对象", stage)
    _require(payload["failure_version"] == CROSSCHECK_FAILURE_VERSION, f"{label}.failure_version",
             f"必须是 {CROSSCHECK_FAILURE_VERSION}，实际 {payload['failure_version']!r}", stage)
    _require(payload["batch_id"] == batch_dir.name, f"{label}.batch_id",
             "必须与本批次一致", stage)
    _require(payload["host_version"] == HOST_VERSION, f"{label}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}，实际 {payload['host_version']!r}", stage)
    _require(isinstance(payload["target_exit_code"], int)
             and not isinstance(payload["target_exit_code"], bool)
             and payload["target_exit_code"] in (EXIT_BLOCKED, EXIT_ERROR),
             f"{label}.target_exit_code",
             f"必须是严格整数 1／2，实际 {payload['target_exit_code']!r}", stage)
    _require(isinstance(payload["reasons"], list) and bool(payload["reasons"]), f"{label}.reasons",
             "必须是非空原因列表", stage)
    _require(isinstance(payload["stage"], str) and payload["stage"].startswith("crosscheck"),
             f"{label}.stage",
             f"复算失败诊断的阶段必须是 crosscheck 阶段，实际 {payload['stage']!r}"
             "（不得把复算错误记成 prepare_gate2 等其他操作）", stage)
    return payload


def _crosscheck_failure_exception(failure: dict) -> Exception:
    reasons = [str(item) for item in failure["reasons"]]
    message = (f"该批次的 {WORKFLOW_DIR}/{CROSSCHECK_DIR}/ 记录了未完成的复算尝试："
               f"stage={failure['stage']!r}；异常类别={failure['exception_class']!r}；原因={reasons!r}。"
               "即使存在可解析的完整 0006，也不得宣告本次复算成功；不重试、不复用、不自动删除，"
               "需继续时新建批次。")
    if failure["target_exit_code"] == EXIT_ERROR:
        return WorkflowHostError(message, reasons=reasons, stage=failure["stage"])
    return WorkflowHostBlocked(message, reasons=reasons, stage=failure["stage"])


def _raise_incomplete_crosscheck(batch_dir: Path, chain: dict) -> None:
    revision = chain["current"]["revision"]
    raise WorkflowHostBlocked(
        f"该批次的 {WORKFLOW_DIR}/{CROSSCHECK_DIR}/ 已开始但没有完整有效的 0006"
        f"（当前为第 {revision} 份 checkpoint）：复算未完成。不重试、不复用、不自动删除，"
        "不猜测成功、不退回旧状态，需继续时新建批次。", stage="status")


def _read_crosscheck_outputs(batch_dir: Path, stage: str) -> dict:
    """从固定路径实读本次复算产物（不跟随清单访问任意路径）。"""
    paths = _crosscheck_paths(batch_dir)
    for path, label in ((paths["started_path"], CROSSCHECK_START),
                        (paths["report_path"], CROSSCHECK_REPORT),
                        (paths["artifacts_path"], CROSSCHECK_ARTIFACTS)):
        _require(path.is_file(), f"{paths['relative']}/{label}",
                 f"缺少本次复算产物文件（{path}）", stage)
    started, started_sha = _read_json_with_bytes(paths["started_path"],
                                                 f"{paths['relative']}/{CROSSCHECK_START}", stage)
    report, report_sha = _read_json_with_bytes(paths["report_path"],
                                               f"{paths['relative']}/{CROSSCHECK_REPORT}", stage)
    artifacts, artifacts_sha = _read_json_with_bytes(paths["artifacts_path"],
                                                     f"{paths['relative']}/{CROSSCHECK_ARTIFACTS}", stage)
    return {"started": started, "report": report, "artifacts": artifacts,
            "started_file_sha256": started_sha, "report_file_sha256": report_sha,
            "artifacts_file_sha256": artifacts_sha}


def _crosscheck_report_protocol(report: dict, normalized: dict, screening_report: dict,
                                stage: str, label: str) -> str:
    """只核验复算核心接口协议与来源绑定；不重新实现规则，也不重跑复算。"""
    _require(isinstance(report, dict), label, f"必须是对象，实际 {type(report).__name__}", stage)
    _require_keys(report, CROSSCHECK_REPORT_REQUIRED_KEYS, label, stage)
    _require(report["crosscheck_version"] == CROSSCHECK_MODULE.CROSSCHECK_VERSION,
             f"{label}.crosscheck_version",
             f"必须是 {CROSSCHECK_MODULE.CROSSCHECK_VERSION}，实际 {report['crosscheck_version']!r}",
             stage)
    _require(isinstance(report["matched"], bool), f"{label}.matched",
             f"必须是严格布尔，实际 {type(report['matched']).__name__}", stage)
    expected_status = (CROSSCHECK_MODULE.MATCHED_STATUS if report["matched"]
                       else CROSSCHECK_MODULE.MISMATCH_STATUS)
    _require(report["batch_status"] == expected_status, f"{label}.batch_status",
             f"must be {expected_status!r} when matched={report['matched']!r}，"
             f"实际 {report['batch_status']!r}", stage)
    _require(report["mode"] == MODE, f"{label}.mode", f"必须是 {MODE}", stage)
    _require(report["next_step_allowed"] is False, f"{label}.next_step_allowed",
             "必须是严格 false", stage)
    _require(report["cutoff_date"] == SCREEN_CUTOFF_DATE, f"{label}.cutoff_date",
             f"必须是 {SCREEN_CUTOFF_DATE}", stage)
    period = report["period"]
    _require(isinstance(period, dict) and period.get("period_start") == CROSSCHECK_MODULE.PERIOD_START
             and period.get("period_end") == CROSSCHECK_MODULE.PERIOD_END, f"{label}.period",
             f"必须覆盖 {CROSSCHECK_MODULE.PERIOD_START}—{CROSSCHECK_MODULE.PERIOD_END}，"
             f"实际 {period!r}", stage)
    _require(report["rule_core_version_checked"] == SCREEN_MODULE.RULE_CORE_VERSION,
             f"{label}.rule_core_version_checked",
             f"必须是 {SCREEN_MODULE.RULE_CORE_VERSION}，实际 {report['rule_core_version_checked']!r}",
             stage)
    # 来源绑定：必须等于本批次本次实读的两个输入
    _require(canonical_sha256(normalized) == report["normalized_payload_sha256"],
             f"{label}.normalized_payload_sha256",
             "必须等于本批次 normalized 对象实际规范指纹", stage)
    _require(canonical_sha256(screening_report) == report["screening_report_sha256"],
             f"{label}.screening_report_sha256",
             "必须等于本批次筛查报告对象实际规范指纹", stage)
    source = (screening_report.get("load_source") or {})
    input_sha = ((normalized.get("source") or {}).get("input_sha256")
                 or source.get("input_sha256"))
    _require(report["input_source_sha256"] == input_sha, f"{label}.input_source_sha256",
             f"必须等于本次输入来源哈希，期望 {input_sha!r}，实际 {report['input_source_sha256']!r}",
             stage)
    # 十个维度必须齐备、类型严格
    comparison = report["comparison"]
    _require(isinstance(comparison, dict), f"{label}.comparison", "必须是对象", stage)
    _require_keys(comparison, ("dimensions", "difference_count", "matched_dimensions",
                               "unmatched_dimensions"), f"{label}.comparison", stage)
    dimensions = comparison["dimensions"]
    _require(isinstance(dimensions, dict), f"{label}.comparison.dimensions", "必须是对象", stage)
    _require(set(dimensions) == set(CROSSCHECK_DIMENSIONS), f"{label}.comparison.dimensions",
             f"必须恰为 {list(CROSSCHECK_DIMENSIONS)}，实际 {sorted(dimensions)}", stage)
    for name in CROSSCHECK_DIMENSIONS:
        item = dimensions[name]
        _require(isinstance(item, dict), f"{label}.comparison.dimensions.{name}", "必须是对象", stage)
        _require_keys(item, ("executed", "matched", "difference_count"),
                      f"{label}.comparison.dimensions.{name}", stage)
        _require(item["executed"] is True, f"{label}.comparison.dimensions.{name}.executed",
                 f"必须是严格 true，实际 {item['executed']!r}", stage)
        _require(isinstance(item["matched"], bool),
                 f"{label}.comparison.dimensions.{name}.matched",
                 f"必须是严格布尔，实际 {type(item['matched']).__name__}", stage)
        _require(isinstance(item["difference_count"], int)
                 and not isinstance(item["difference_count"], bool)
                 and item["difference_count"] >= 0,
                 f"{label}.comparison.dimensions.{name}.difference_count",
                 f"必须是非负整数（排除 bool/float），实际 {item['difference_count']!r}", stage)
    differences = report["differences"]
    _require(isinstance(differences, list), f"{label}.differences", "必须是列表", stage)
    _require(isinstance(comparison["difference_count"], int)
             and not isinstance(comparison["difference_count"], bool),
             f"{label}.comparison.difference_count", "必须是严格整数", stage)
    _require(comparison["difference_count"] == len(differences), f"{label}.comparison.difference_count",
             f"必须等于 differences 条数 {len(differences)}，实际 {comparison['difference_count']}",
             stage)
    matched_dimensions = sorted(name for name in CROSSCHECK_DIMENSIONS if dimensions[name]["matched"])
    unmatched_dimensions = sorted(name for name in CROSSCHECK_DIMENSIONS
                                  if not dimensions[name]["matched"])
    _require(sorted(comparison["matched_dimensions"]) == matched_dimensions,
             f"{label}.comparison.matched_dimensions",
             f"必须等于实际 matched 维度 {matched_dimensions}，实际 {comparison['matched_dimensions']}",
             stage)
    _require(sorted(comparison["unmatched_dimensions"]) == unmatched_dimensions,
             f"{label}.comparison.unmatched_dimensions",
             f"必须等于实际 unmatched 维度 {unmatched_dimensions}，"
             f"实际 {comparison['unmatched_dimensions']}", stage)
    # 成功口径：不仅看一个 matched 标志
    if report["matched"]:
        _require(not differences, f"{label}.differences", "matched=true 时差异必须为空", stage)
        _require(comparison["difference_count"] == 0, f"{label}.comparison.difference_count",
                 "matched=true 时差异数必须为 0", stage)
        for name in CROSSCHECK_DIMENSIONS:
            _require(dimensions[name]["matched"] is True,
                     f"{label}.comparison.dimensions.{name}.matched",
                     "matched=true 时每个维度都必须 matched=true", stage)
            _require(dimensions[name]["difference_count"] == 0,
                     f"{label}.comparison.dimensions.{name}.difference_count",
                     "matched=true 时每个维度差异数都必须为 0", stage)
        _require(not unmatched_dimensions, f"{label}.comparison.unmatched_dimensions",
                 "matched=true 时不得有未一致维度", stage)
    else:
        _require(bool(differences) or bool(unmatched_dimensions), f"{label}.differences",
                 "matched=false 时必须给出差异或未一致维度", stage)
    _require(isinstance(report["recomputed_facts"], dict), f"{label}.recomputed_facts",
             "必须是对象（复算事实）", stage)
    _require(isinstance(report["observed_summary"], dict), f"{label}.observed_summary",
             "必须是对象（观察事实）", stage)
    _require(isinstance(report["rule_recomputed_counts"], dict), f"{label}.rule_recomputed_counts",
             "必须是对象", stage)
    _require(isinstance(report["limits"], list) and bool(report["limits"]), f"{label}.limits",
             "必须是非空限制列表", stage)
    return canonical_sha256(report)


def _verify_crosscheck_tail(batch_dir: Path, expected: dict, stage: str) -> dict:
    """复算收尾一致性：复测 crosscheck 产物与实际文件字节（固定路径）。"""
    paths = _crosscheck_paths(batch_dir)
    actual = {
        "started_file_sha256": file_sha256(paths["started_path"]),
        "report_file_sha256": file_sha256(paths["report_path"]),
        "artifacts_file_sha256": file_sha256(paths["artifacts_path"]),
    }
    labels = {"started_file_sha256": f"{paths['relative']}/{CROSSCHECK_START}",
              "report_file_sha256": f"{paths['relative']}/{CROSSCHECK_REPORT}",
              "artifacts_file_sha256": f"{paths['relative']}/{CROSSCHECK_ARTIFACTS}"}
    for key, value in actual.items():
        _require(expected.get(key) == value, labels[key],
                 f"收尾复测发现本次复算产物发生变化：期望 {expected.get(key)!r}，实际 {value!r}",
                 stage)
    database_path = expected.get("database_path")
    _require(isinstance(database_path, str), "crosscheck.expected.database_path",
             "收尾复测必须带出固定数据库路径", stage)
    _require(expected.get("database_sha256") == file_sha256(Path(database_path)),
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_DATABASE_NAME}",
             "收尾复测发现数据库字节变化", stage)
    failure_path = paths["failure_path"]
    _require(not failure_path.exists(), f"{paths['relative']}/{CROSSCHECK_FAILURE}",
             "成功收尾不得存在失败诊断", stage)
    for name in sorted(item.name for item in paths["directory"].iterdir()):
        _require(name in (CROSSCHECK_START, CROSSCHECK_REPORT, CROSSCHECK_ARTIFACTS),
                 f"{paths['relative']}/{name}", "成功批次的复算目录只允许既定产物文件", stage)
    return actual


def _verify_crosscheck_operation(payload: dict, previous_payload: dict, state: dict, label: str,
                                 stage: str, batch_dir: Path, manifest: dict, *,
                                 previous_file_sha256: str, screen_expected: dict,
                                 host_manifest_file_sha256: str) -> None:
    """0006 只允许从合法 0005 的 DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED 延续一次独立复算。"""
    operation = payload["operation"]
    _require(operation.get("kind") == OPERATION_RUN_RULE_CROSSCHECK, f"{label}.operation.kind",
             f"0006 必须是 {OPERATION_RUN_RULE_CROSSCHECK}，实际 {operation.get('kind')!r}", stage)
    _require_keys(operation, ("at_utc", "artifacts", "artifacts_file_sha256", "report_file_sha256",
                              "report_canonical_sha256", "started_file_sha256", "database_sha256",
                              "phase_after", "bindings_sha256", "crosscheck_status",
                              "report_relative", "artifacts_relative", "started_relative",
                              "core_path", "core_sha256", "core_version",
                              "normalized_file_sha256", "screening_report_file_sha256",
                              "screening_artifacts_file_sha256"),
                  f"{label}.operation", stage)
    previous_workflow = previous_payload["workflow"]
    previous_state = previous_workflow["state"]
    _require(previous_state["phase"] == CONTROLLER_MODULE.PHASE_G2_APPROVED, f"{label}.previous.phase",
             f"0006 只能从 {CONTROLLER_MODULE.PHASE_G2_APPROVED} 的 0005 延续，实际 "
             f"{previous_state['phase']!r}", stage)
    _require(canonical_json(payload["workflow"]) == canonical_json(previous_workflow),
             f"{label}.workflow", "0006 的完整 workflow 必须与 0005 严格相等"
             "（复算不改变控制器状态、不新增决定或请求）", stage)
    decisions = state["simulated_decisions"]
    _require(isinstance(decisions, list) and len(decisions) == 2, f"{label}.state.simulated_decisions",
             f"模拟决定必须恰为 Gate1 与 Gate2 两条，实际 "
             f"{len(decisions) if isinstance(decisions, list) else decisions!r}", stage)
    _require(operation["phase_after"] == state["phase"], f"{label}.operation.phase_after",
             "操作摘要的 phase 必须与实际状态一致", stage)
    _require(operation["bindings_sha256"] == state["run_bindings_sha256"],
             f"{label}.operation.bindings_sha256", "必须与 workflow 绑定一致", stage)
    _require(operation["crosscheck_status"] == CROSSCHECK_STATUS_RECORDED,
             f"{label}.operation.crosscheck_status",
             f"必须是 {CROSSCHECK_STATUS_RECORDED}，实际 {operation['crosscheck_status']!r}", stage)
    _require(state["batch_id"] == payload["batch_id"], f"{label}.workflow.state.batch_id",
             "workflow 批次必须与 checkpoint 一致", stage)

    # 0005 的筛查材料核验保留到 0006 恢复：不跳过筛查产物与数据库核验
    _require(isinstance(screen_expected, dict) and bool(screen_expected),
             f"{label}.screen_expected",
             "0006 恢复必须带出 0005 的初次筛查核验读数（不得跳过数据库与筛查产物核验）", stage)
    screen = _read_screen_outputs(batch_dir, stage)
    for key, field in (("started_file_sha256", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}"),
                       ("report_file_sha256", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}"),
                       ("artifacts_file_sha256", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}")):
        _require(screen_expected.get(key) == screen[key], field,
                 f"筛查产物在复算恢复时发生了变化：期望 {screen_expected.get(key)!r}，"
                 f"实际 {screen[key]!r}", stage)
    outputs = _read_gate2_outputs(batch_dir, stage)
    gate2_paths = _gate2_paths(batch_dir, stage)
    actual_database_sha = file_sha256(gate2_paths["database_path"])
    for key, value, field in (
        ("gate2_normalized_file_sha256", outputs["normalized_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}"),
        ("gate2_load_report_file_sha256", outputs["load_report_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}"),
        ("gate2_artifacts_file_sha256", outputs["artifacts_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"),
        ("gate2_database_sha256", actual_database_sha, str(gate2_paths["database_path"])),
    ):
        _require(screen_expected.get(key) == value, field,
                 f"Gate2 材料在复算恢复时发生了变化：期望 {screen_expected.get(key)!r}，"
                 f"实际 {value!r}", stage)

    paths = _crosscheck_paths(batch_dir)
    actual = _read_crosscheck_outputs(batch_dir, stage)
    started = actual["started"]
    started_label = f"{paths['relative']}/{CROSSCHECK_START}"
    _require_keys(started, ("start_version", "batch_id", "host_version", "operation_kind", "at_utc",
                            "source_checkpoint_file_sha256", "run_bindings_sha256",
                            "normalized_file_sha256", "screening_report_file_sha256",
                            "screening_artifacts_file_sha256",
                            "normalized_payload_sha256", "screening_report_canonical_sha256"),
                  started_label, stage)
    _require(started["start_version"] == CROSSCHECK_START_VERSION, f"{started_label}.start_version",
             f"必须是 {CROSSCHECK_START_VERSION}，实际 {started['start_version']!r}", stage)
    _require(started["batch_id"] == batch_dir.name, f"{started_label}.batch_id",
             "必须与批次目录叶子一致", stage)
    _require(started["host_version"] == HOST_VERSION, f"{started_label}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}，实际 {started['host_version']!r}", stage)
    _require(started["operation_kind"] == OPERATION_RUN_RULE_CROSSCHECK,
             f"{started_label}.operation_kind", f"必须是 {OPERATION_RUN_RULE_CROSSCHECK}", stage)
    _require(started["source_checkpoint_file_sha256"] == previous_file_sha256,
             f"{started_label}.source_checkpoint_file_sha256",
             "必须等于 0005 的初始实读字节哈希", stage)
    _require(started["run_bindings_sha256"] == state["run_bindings_sha256"],
             f"{started_label}.run_bindings_sha256", "必须等于 workflow 创建绑定指纹", stage)
    _require(started["normalized_file_sha256"] == outputs["normalized_file_sha256"],
             f"{started_label}.normalized_file_sha256",
             "必须等于本批次本次实读 normalized 文件字节哈希", stage)
    _require(started["screening_report_file_sha256"] == screen["report_file_sha256"],
             f"{started_label}.screening_report_file_sha256",
             "必须等于本批次本次实读筛查报告文件字节哈希", stage)
    _require(started["screening_artifacts_file_sha256"] == screen["artifacts_file_sha256"],
             f"{started_label}.screening_artifacts_file_sha256",
             "必须等于本批次本次实读筛查 artifacts 文件字节哈希", stage)
    # 文件字节哈希与规范对象指纹必须分开保存并分别核验（不得互相替代）
    _require(started["normalized_payload_sha256"] == canonical_sha256(outputs["normalized"]),
             f"{started_label}.normalized_payload_sha256",
             "必须等于本批次本次实读 normalized 对象的规范指纹（不得用文件字节哈希替代）", stage)
    _require(started["normalized_payload_sha256"] == outputs["load_report"]["normalized_payload_sha256"],
             f"{started_label}.normalized_payload_sha256",
             "必须等于本批次装载报告声明的 normalized 对象指纹", stage)
    _require(started["screening_report_canonical_sha256"] == canonical_sha256(screen["report"]),
             f"{started_label}.screening_report_canonical_sha256",
             "必须等于本批次本次实读筛查报告对象的规范指纹（不得用文件字节哈希替代）", stage)
    _require(actual["report"]["screening_report_sha256"]
             == started["screening_report_canonical_sha256"],
             f"{started_label}.screening_report_canonical_sha256",
             "必须等于本次复算报告声明的筛查报告规范指纹（来源绑定不得被事后指纹替换）", stage)

    artifacts = actual["artifacts"]
    artifacts_label = f"{paths['relative']}/{CROSSCHECK_ARTIFACTS}"
    _require_keys(artifacts, ("artifacts_version", "batch_id", "host_version", "operation_kind",
                              "core_path", "core_sha256", "core_version",
                              "report_relative", "report_file_sha256", "report_canonical_sha256",
                              "crosscheck_status", "matched",
                              "started_file_sha256", "previous_checkpoint_file_sha256",
                              "host_manifest_file_sha256", "normalized_file_sha256",
                              "normalized_payload_sha256", "screening_report_file_sha256",
                              "screening_report_canonical_sha256", "screening_artifacts_file_sha256",
                              "gate2_artifacts_file_sha256", "database_path", "database_sha256",
                              "cutoff_date", "rule_core_version_checked", "run_bindings_sha256",
                              "gate2_decision_sha256", "created_at_utc"), artifacts_label, stage)
    _require(artifacts["artifacts_version"] == CROSSCHECK_ARTIFACTS_VERSION,
             f"{artifacts_label}.artifacts_version",
             f"必须是 {CROSSCHECK_ARTIFACTS_VERSION}，实际 {artifacts['artifacts_version']!r}", stage)
    _require(artifacts["batch_id"] == batch_dir.name, f"{artifacts_label}.batch_id",
             "必须与批次目录叶子一致", stage)
    _require(artifacts["host_version"] == HOST_VERSION, f"{artifacts_label}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}", stage)
    _require(artifacts["operation_kind"] == OPERATION_RUN_RULE_CROSSCHECK,
             f"{artifacts_label}.operation_kind", f"必须是 {OPERATION_RUN_RULE_CROSSCHECK}", stage)
    _require(artifacts["core_path"] == str(CROSSCHECK_CORE_PATH), f"{artifacts_label}.core_path",
             f"必须是冻结复算核心固定路径 {CROSSCHECK_CORE_PATH}", stage)
    _require(artifacts["core_sha256"] == manifest["bindings"]["code_sha256"]["crosscheck_demo_rules"],
             f"{artifacts_label}.core_sha256",
             "必须等于冻结复算核心实际字节哈希（不得使用与本次无关的核心）", stage)
    _require(artifacts["core_version"] == CROSSCHECK_MODULE.CROSSCHECK_VERSION,
             f"{artifacts_label}.core_version",
             f"必须是 {CROSSCHECK_MODULE.CROSSCHECK_VERSION}", stage)
    _require(artifacts["crosscheck_status"] == CROSSCHECK_STATUS_RECORDED,
             f"{artifacts_label}.crosscheck_status", f"必须是 {CROSSCHECK_STATUS_RECORDED}", stage)
    _require(isinstance(artifacts["matched"], bool), f"{artifacts_label}.matched",
             f"必须是严格布尔，实际 {type(artifacts['matched']).__name__}", stage)
    _require(artifacts["report_relative"] == f"{paths['relative']}/{CROSSCHECK_REPORT}",
             f"{artifacts_label}.report_relative", "必须是固定相对路径", stage)
    _require(artifacts["report_file_sha256"] == actual["report_file_sha256"],
             f"{artifacts_label}.report_file_sha256", "必须等于报告文件实际字节哈希", stage)
    _require(artifacts["report_canonical_sha256"] == operation["report_canonical_sha256"],
             f"{artifacts_label}.report_canonical_sha256",
             "必须等于本次复算报告对象的实际规范指纹", stage)
    _require(artifacts["started_file_sha256"] == actual["started_file_sha256"],
             f"{artifacts_label}.started_file_sha256", "必须等于 started 文件实际字节哈希", stage)
    _require(artifacts["previous_checkpoint_file_sha256"] == previous_file_sha256,
             f"{artifacts_label}.previous_checkpoint_file_sha256",
             "必须等于 0005 的初始实读字节哈希", stage)
    _require(artifacts["host_manifest_file_sha256"] == host_manifest_file_sha256,
             f"{artifacts_label}.host_manifest_file_sha256",
             "必须等于初始实读宿主清单文件字节哈希", stage)
    _require(artifacts["normalized_file_sha256"] == outputs["normalized_file_sha256"],
             f"{artifacts_label}.normalized_file_sha256",
             "必须等于本次实读 normalized 文件字节哈希", stage)
    _require(artifacts["normalized_payload_sha256"]
             == outputs["load_report"].get("normalized_payload_sha256"),
             f"{artifacts_label}.normalized_payload_sha256",
             "必须等于本批次 normalized 对象指纹", stage)
    _require(artifacts["screening_report_file_sha256"] == screen["report_file_sha256"],
             f"{artifacts_label}.screening_report_file_sha256",
             "必须等于本次实读筛查报告文件字节哈希", stage)
    _require(artifacts["screening_artifacts_file_sha256"] == screen["artifacts_file_sha256"],
             f"{artifacts_label}.screening_artifacts_file_sha256",
             "必须等于本次实读筛查 artifacts 文件字节哈希", stage)
    _require(artifacts["gate2_artifacts_file_sha256"] == outputs["artifacts_file_sha256"],
             f"{artifacts_label}.gate2_artifacts_file_sha256",
             "必须等于本次实读 Gate2 artifacts 文件字节哈希", stage)
    _require(artifacts["database_path"] == str(gate2_paths["database_path"]),
             f"{artifacts_label}.database_path", "必须是宿主推导的固定数据库路径", stage)
    _require(artifacts["database_sha256"] == actual_database_sha,
             f"{artifacts_label}.database_sha256", "必须等于数据库实际字节哈希", stage)
    _require(artifacts["cutoff_date"] == SCREEN_CUTOFF_DATE, f"{artifacts_label}.cutoff_date",
             f"必须是 {SCREEN_CUTOFF_DATE}", stage)
    _require(artifacts["rule_core_version_checked"] == SCREEN_MODULE.RULE_CORE_VERSION,
             f"{artifacts_label}.rule_core_version_checked",
             f"必须是 {SCREEN_MODULE.RULE_CORE_VERSION}", stage)
    _require(artifacts["run_bindings_sha256"] == state["run_bindings_sha256"],
             f"{artifacts_label}.run_bindings_sha256", "必须等于 workflow 创建绑定指纹", stage)
    gate2_body_sha = canonical_sha256({key: value for key, value in decisions[-1].items()
                                       if key != "decision_sha256"})
    _require(artifacts["gate2_decision_sha256"] == gate2_body_sha,
             f"{artifacts_label}.gate2_decision_sha256",
             "必须等于本 workflow 已验证 Gate2 APPROVE 正文指纹", stage)

    _require(operation["report_file_sha256"] == actual["report_file_sha256"],
             f"{label}.operation.report_file_sha256", "必须等于报告文件实际字节哈希", stage)
    _require(operation["started_file_sha256"] == actual["started_file_sha256"],
             f"{label}.operation.started_file_sha256", "必须等于 started 文件实际字节哈希", stage)
    _require(operation["artifacts_file_sha256"] == actual["artifacts_file_sha256"],
             f"{label}.operation.artifacts_file_sha256", "必须等于 artifacts 文件实际字节哈希", stage)
    _require(operation["database_sha256"] == actual_database_sha, f"{label}.operation.database_sha256",
             "必须等于数据库实际字节哈希", stage)
    _require(operation["report_relative"] == f"{paths['relative']}/{CROSSCHECK_REPORT}",
             f"{label}.operation.report_relative", "必须是固定相对路径", stage)
    _require(operation["artifacts_relative"] == f"{paths['relative']}/{CROSSCHECK_ARTIFACTS}",
             f"{label}.operation.artifacts_relative", "必须是固定相对路径", stage)
    _require(operation["started_relative"] == f"{paths['relative']}/{CROSSCHECK_START}",
             f"{label}.operation.started_relative", "必须是固定相对路径", stage)
    _require(operation["core_path"] == str(CROSSCHECK_CORE_PATH), f"{label}.operation.core_path",
             "必须是冻结复算核心固定路径", stage)
    _require(operation["core_sha256"] == manifest["bindings"]["code_sha256"]["crosscheck_demo_rules"],
             f"{label}.operation.core_sha256", "必须等于冻结复算核心实际字节哈希", stage)
    _require(operation["core_version"] == CROSSCHECK_MODULE.CROSSCHECK_VERSION,
             f"{label}.operation.core_version", f"必须是 {CROSSCHECK_MODULE.CROSSCHECK_VERSION}", stage)
    _require(operation["normalized_file_sha256"] == outputs["normalized_file_sha256"],
             f"{label}.operation.normalized_file_sha256",
             "必须等于本次实读 normalized 文件字节哈希", stage)
    _require(operation["screening_report_file_sha256"] == screen["report_file_sha256"],
             f"{label}.operation.screening_report_file_sha256",
             "必须等于本次实读筛查报告文件字节哈希", stage)
    _require(operation["screening_artifacts_file_sha256"] == screen["artifacts_file_sha256"],
             f"{label}.operation.screening_artifacts_file_sha256",
             "必须等于本次实读筛查 artifacts 文件字节哈希", stage)
    # 报告对象本身：协议与来源绑定（不重跑复算）
    _require(artifacts["matched"] is actual["report"]["matched"], f"{artifacts_label}.matched",
             "必须等于报告对象的 matched 标志", stage)
    report_canonical_sha = _crosscheck_report_protocol(actual["report"], outputs["normalized"],
                                                       screen["report"], stage,
                                                       f"{paths['relative']}/{CROSSCHECK_REPORT}")
    _require(operation["report_canonical_sha256"] == report_canonical_sha,
             f"{label}.operation.report_canonical_sha256",
             "必须等于报告对象的实际规范指纹（不得用事后指纹替换）", stage)
    _require(artifacts["screening_report_canonical_sha256"]
             == actual["report"]["screening_report_sha256"],
             f"{artifacts_label}.screening_report_canonical_sha256",
             "必须等于报告对象声明的筛查报告规范指纹", stage)
    # 内嵌副本先验形状，再与实际已验证 artifacts 完整严格相等
    embedded = operation["artifacts"]
    _require(isinstance(embedded, dict), f"{label}.operation.artifacts",
             f"必须是对象（内嵌 artifacts 完整副本），实际 {type(embedded).__name__}", stage)
    _require_keys(embedded, ("artifacts_version", "batch_id", "host_version", "operation_kind",
                             "core_path", "core_sha256", "core_version", "report_relative",
                             "report_file_sha256", "report_canonical_sha256", "crosscheck_status",
                             "matched", "started_file_sha256", "previous_checkpoint_file_sha256",
                             "host_manifest_file_sha256", "normalized_file_sha256",
                             "normalized_payload_sha256", "screening_report_file_sha256",
                             "screening_report_canonical_sha256", "screening_artifacts_file_sha256",
                             "gate2_artifacts_file_sha256", "database_path", "database_sha256",
                             "cutoff_date", "rule_core_version_checked", "run_bindings_sha256",
                             "gate2_decision_sha256", "created_at_utc"),
                  f"{label}.operation.artifacts", stage)
    _require(canonical_json(embedded) == canonical_json(artifacts), f"{label}.operation.artifacts",
             "内嵌 artifacts 副本必须与磁盘实际 artifacts 对象完整严格相等"
             "（不得留两套矛盾来源）", stage)
    # 0006 自己的核验读数交给 0007 使用（不得用链尾 0007 的哈希代替）
    return {
        "screening_started_file_sha256": screen["started_file_sha256"],
        "screening_report_file_sha256": screen["report_file_sha256"],
        "screening_artifacts_file_sha256": screen["artifacts_file_sha256"],
        "crosscheck_started_file_sha256": actual["started_file_sha256"],
        "crosscheck_report_file_sha256": actual["report_file_sha256"],
        "crosscheck_artifacts_file_sha256": actual["artifacts_file_sha256"],
        "gate2_normalized_file_sha256": outputs["normalized_file_sha256"],
        "gate2_load_report_file_sha256": outputs["load_report_file_sha256"],
        "gate2_artifacts_file_sha256": outputs["artifacts_file_sha256"],
        "gate2_database_path": str(gate2_paths["database_path"]),
        "gate2_database_sha256": actual_database_sha,
        "database_path": str(gate2_paths["database_path"]),
        "database_sha256": actual_database_sha,
    }



def _fact_packet_dir(batch_dir: Path) -> Path:
    return _host_workflow_dir(batch_dir) / FACT_PACKET_DIR


def _fact_packet_paths(batch_dir: Path) -> dict:
    directory = _fact_packet_dir(batch_dir)
    return {"directory": directory, "dir": directory,
            "relative": f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}",
            "started_path": directory / FACT_PACKET_START,
            "packet_path": directory / FACT_PACKET_JSON,
            "markdown_path": directory / FACT_PACKET_MARKDOWN,
            "artifacts_path": directory / FACT_PACKET_ARTIFACTS,
            "failure_path": directory / FACT_PACKET_FAILURE}


def _fact_packet_observed_state(batch_dir: Path) -> dict:
    """尽力采集失败现场的已知产物引用（只读、不存在即记 null）。"""
    paths = _fact_packet_paths(batch_dir)
    observed = {"directory_exists": paths["directory"].exists()}
    for key, path in (("started", paths["started_path"]), ("packet", paths["packet_path"]),
                      ("markdown", paths["markdown_path"]),
                      ("artifacts", paths["artifacts_path"]),
                      ("failure", paths["failure_path"])):
        observed[f"{key}_present"] = path.is_file()
        try:
            observed[f"{key}_file_sha256"] = file_sha256(path) if path.is_file() else None
        except OSError:
            observed[f"{key}_file_sha256"] = None
    return observed


def _write_exclusive_markdown(path: Path, markdown: str, stage: str) -> str:
    """独占创建 Markdown：UTF-8 无 BOM、明确 LF、按确切 UTF-8 字节写入，不 strip、不额外增删换行。"""
    _require(isinstance(markdown, str), "fact_packet.markdown",
             f"核心返回的 markdown 必须是字符串，实际 {type(markdown).__name__}", stage)
    data = markdown.encode("utf-8")
    try:
        with open(path, "xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise WorkflowHostBlocked(f"文件已存在，不覆盖：{path}", stage=stage) from exc
    except OSError as exc:
        raise WorkflowHostError(f"Markdown 写入失败 {path}：{exc}", stage=stage) from exc
    try:
        readback = path.read_bytes()
    except OSError as exc:
        raise WorkflowHostError(f"Markdown 写后读回失败（不宣称保存成功）：{path}（{exc}）",
                               stage=stage) from exc
    if readback != data:
        raise WorkflowHostError(
            f"Markdown 写后读回字节不一致（不宣称保存成功）：{path}"
            f"（写 {len(data)} 字节，读回 {len(readback)} 字节）", stage=stage)
    if readback.startswith(b"\xef\xbb\xbf"):
        raise WorkflowHostError(f"Markdown 不得带 UTF-8 BOM：{path}", stage=stage)
    _require(b"\r\n" not in readback, f"{path.name}",
             "Markdown 必须使用 LF 换行（不得出现 CRLF）", stage)
    return hashlib.sha256(readback).hexdigest()


def _save_fact_packet_failure(batch_dir: Path, stage_label: str, exc: Exception,
                              observed: dict) -> str:
    """本次真正创建了 fact_packet 目录之后才写失败诊断（独占创建，不覆盖、不留半文件）。"""
    paths = _fact_packet_paths(batch_dir)
    _ensure_dir(paths["directory"], stage_label)
    target_exit_code = (EXIT_ERROR
                        if type(exc).__name__ in FACT_PACKET_RUNTIME_FAILURE_CLASSES
                        else EXIT_BLOCKED)
    observed = dict(observed or {})
    observed["target_exit_code"] = target_exit_code
    observed["exception_class"] = type(exc).__name__
    exception_chain = getattr(exc, "original_exception_chain", None) or _exception_chain(exc)
    payload = {
        "failure_version": FACT_PACKET_FAILURE_VERSION,
        "batch_id": batch_dir.name,
        "host_version": HOST_VERSION,
        "recorded_at_utc": _now_utc(),
        "stage": stage_label,
        "exception_class": type(exc).__name__,
        "target_exit_code": target_exit_code,
        "message": str(exc),
        "reasons": list(getattr(exc, "reasons", []) or [str(exc)]),
        "exception_chain": exception_chain,
        "observed_outputs": observed,
    }
    path = paths["failure_path"]
    if path.exists():
        raise WorkflowHostBlocked(
            f"失败诊断已存在，不覆盖：{paths['relative']}/{FACT_PACKET_FAILURE}", stage=stage_label)
    sha = _write_exclusive_json(path, payload, stage_label)
    readback, readback_sha = _read_json_with_bytes(
        path, f"{paths['relative']}/{FACT_PACKET_FAILURE}", stage_label)
    _require(readback_sha == sha, f"{paths['relative']}/{FACT_PACKET_FAILURE}",
             "写后读回的失败诊断字节哈希与写入结果不一致", stage_label)
    _require(canonical_json(readback) == canonical_json(payload),
             f"{paths['relative']}/{FACT_PACKET_FAILURE}",
             "写后读回的失败诊断内容与写入结果不一致", stage_label)
    return sha


def _load_fact_packet_failure(batch_dir: Path, stage: str):
    """读取并严格核验事实底稿失败诊断；不存在返回 None。"""
    paths = _fact_packet_paths(batch_dir)
    path = paths["failure_path"]
    if not path.exists():
        return None
    label = f"{paths['relative']}/{FACT_PACKET_FAILURE}"
    _require(path.is_file(), label, "失败诊断必须是普通文件", stage)
    payload = _read_json(path, label, stage)
    _require_keys(payload, ("failure_version", "batch_id", "host_version", "recorded_at_utc",
                            "stage", "exception_class", "target_exit_code", "message", "reasons",
                            "exception_chain", "observed_outputs"), label, stage)
    _require(payload["failure_version"] == FACT_PACKET_FAILURE_VERSION, f"{label}.failure_version",
             f"必须是 {FACT_PACKET_FAILURE_VERSION}，实际 {payload['failure_version']!r}", stage)
    _require(payload["batch_id"] == batch_dir.name, f"{label}.batch_id", "必须与本批次一致", stage)
    _require(payload["host_version"] == HOST_VERSION, f"{label}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}，实际 {payload['host_version']!r}", stage)
    _require(isinstance(payload["target_exit_code"], int)
             and not isinstance(payload["target_exit_code"], bool)
             and payload["target_exit_code"] in (EXIT_BLOCKED, EXIT_ERROR),
             f"{label}.target_exit_code",
             f"必须是严格整数 1／2，实际 {payload['target_exit_code']!r}", stage)
    _require(isinstance(payload["reasons"], list) and bool(payload["reasons"]), f"{label}.reasons",
             "必须是非空原因列表", stage)
    _require(isinstance(payload["exception_chain"], list) and bool(payload["exception_chain"]),
             f"{label}.exception_chain",
             "必须保存非空完整异常链（含原始 cause／context 的类别、消息与阶段）", stage)
    for link_index, link in enumerate(payload["exception_chain"]):
        _require(isinstance(link, dict) and isinstance(link.get("class"), str)
                 and isinstance(link.get("message"), str), f"{label}.exception_chain[{link_index}]",
                 "每一环必须是含 class 与 message 字符串的对象", stage)
    _require(isinstance(payload["stage"], str) and payload["stage"].startswith("fact_packet"),
             f"{label}.stage",
             f"事实底稿失败诊断的阶段必须是 fact_packet 阶段，实际 {payload['stage']!r}", stage)
    return payload


def _fact_packet_failure_exception(failure: dict) -> Exception:
    reasons = [str(item) for item in failure["reasons"]]
    message = (f"该批次的 {WORKFLOW_DIR}/{FACT_PACKET_DIR}/ 记录了未完成的事实底稿尝试："
               f"stage={failure['stage']!r}；异常类别={failure['exception_class']!r}；原因={reasons!r}。"
               "即使存在可解析的完整 0007，也不得宣告本次底稿成功；不重试、不复用、不自动删除，"
               "需继续时新建批次。")
    if failure["target_exit_code"] == EXIT_ERROR:
        return WorkflowHostError(message, reasons=reasons, stage=failure["stage"])
    return WorkflowHostBlocked(message, reasons=reasons, stage=failure["stage"])


def _raise_incomplete_fact_packet(batch_dir: Path, chain: dict) -> None:
    revision = chain["current"]["revision"]
    raise WorkflowHostBlocked(
        f"该批次的 {WORKFLOW_DIR}/{FACT_PACKET_DIR}/ 已开始但没有完整有效的 0007"
        f"（当前为第 {revision} 份 checkpoint）：事实底稿构建未完成。不重试、不复用、不自动删除，"
        "不猜测成功、不退回旧状态，需继续时新建批次。", stage="status")


def _read_fact_packet_outputs(batch_dir: Path, stage: str) -> dict:
    """从固定路径实读本次事实底稿产物；JSON 与对象指纹同缓冲，Markdown 记字节哈希。"""
    paths = _fact_packet_paths(batch_dir)
    for path, label in ((paths["started_path"], FACT_PACKET_START),
                        (paths["packet_path"], FACT_PACKET_JSON),
                        (paths["markdown_path"], FACT_PACKET_MARKDOWN),
                        (paths["artifacts_path"], FACT_PACKET_ARTIFACTS)):
        _require(path.is_file(), f"{paths['relative']}/{label}",
                 f"缺少本次事实底稿产物文件（{path}）", stage)
    started, started_sha = _read_json_with_bytes(
        paths["started_path"], f"{paths['relative']}/{FACT_PACKET_START}", stage)
    packet, packet_sha = _read_json_with_bytes(
        paths["packet_path"], f"{paths['relative']}/{FACT_PACKET_JSON}", stage)
    artifacts, artifacts_sha = _read_json_with_bytes(
        paths["artifacts_path"], f"{paths['relative']}/{FACT_PACKET_ARTIFACTS}", stage)
    markdown_bytes = paths["markdown_path"].read_bytes()
    return {"started": started, "packet": packet, "artifacts": artifacts,
            "markdown_bytes": markdown_bytes,
            "started_file_sha256": started_sha, "packet_file_sha256": packet_sha,
            "artifacts_file_sha256": artifacts_sha,
            "markdown_file_sha256": hashlib.sha256(markdown_bytes).hexdigest(),
            "markdown_path": paths["markdown_path"], "packet_path": paths["packet_path"],
            "artifacts_path": paths["artifacts_path"], "started_path": paths["started_path"]}


def _verify_fact_packet_tail(batch_dir: Path, expected: dict, stage: str) -> dict:
    """事实底稿收尾一致性：复测 4 份产物与实际文件字节（固定路径）+ 数据库。"""
    paths = _fact_packet_paths(batch_dir)
    actual = {
        "started_file_sha256": file_sha256(paths["started_path"]),
        "packet_file_sha256": file_sha256(paths["packet_path"]),
        "artifacts_file_sha256": file_sha256(paths["artifacts_path"]),
        "markdown_file_sha256": file_sha256(paths["markdown_path"]),
    }
    labels = {"started_file_sha256": f"{paths['relative']}/{FACT_PACKET_START}",
              "packet_file_sha256": f"{paths['relative']}/{FACT_PACKET_JSON}",
              "artifacts_file_sha256": f"{paths['relative']}/{FACT_PACKET_ARTIFACTS}",
              "markdown_file_sha256": f"{paths['relative']}/{FACT_PACKET_MARKDOWN}"}
    for key, value in actual.items():
        _require(expected.get(key) == value, labels[key],
                 f"收尾复测发现本次事实底稿产物发生变化：期望 {expected.get(key)!r}，实际 {value!r}",
                 stage)
    database_path = expected.get("database_path")
    _require(isinstance(database_path, str), "fact_packet.expected.database_path",
             "收尾复测必须带出固定数据库路径", stage)
    _require(expected.get("database_sha256") == file_sha256(Path(database_path)),
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_DATABASE_NAME}",
             "收尾复测发现数据库字节变化", stage)
    failure_path = paths["failure_path"]
    _require(not failure_path.exists(), f"{paths['relative']}/{FACT_PACKET_FAILURE}",
             "成功收尾不得存在失败诊断", stage)
    for name in sorted(item.name for item in paths["directory"].iterdir()):
        _require(name in (FACT_PACKET_START, FACT_PACKET_JSON, FACT_PACKET_MARKDOWN,
                          FACT_PACKET_ARTIFACTS),
                 f"{paths['relative']}/{name}", "成功批次的事实底稿目录只允许既定产物文件", stage)
    return actual


def _packet_protocol_report(packet: dict, expected: dict, stage: str, label: str) -> dict:
    """核验事实底稿 packet 的协议形状与来源绑定（不复制业务公式、不重新渲染）。"""
    _require(isinstance(packet, dict), label, f"必须是对象，实际 {type(packet).__name__}", stage)
    core = FACT_PACKET_MODULE
    _require(packet.get("packet_version") == core.PACKET_VERSION, f"{label}.packet_version",
             f"必须是 {core.PACKET_VERSION}，实际 {packet.get('packet_version')!r}", stage)
    _require(packet.get("batch_status") == core.PACKET_STATUS, f"{label}.batch_status",
             f"必须是 {core.PACKET_STATUS}，实际 {packet.get('batch_status')!r}", stage)
    _require(packet.get("mode") == MODE, f"{label}.mode", f"必须是 {MODE}", stage)
    _require(packet.get("next_step_allowed") is False, f"{label}.next_step_allowed",
             "必须是严格 false", stage)
    entity = packet.get("entity")
    _require(isinstance(entity, dict), f"{label}.entity", "必须是对象", stage)
    _require_keys(entity, ("company", "period", "cutoff_date", "currency"), f"{label}.entity", stage)
    _require(entity["company"] == core.COMPANY, f"{label}.entity.company",
             f"必须是 {core.COMPANY}", stage)
    period = entity["period"]
    _require(isinstance(period, dict) and period.get("period_start") == core.PERIOD_START
             and period.get("period_end") == core.PERIOD_END, f"{label}.entity.period",
             f"必须覆盖 {core.PERIOD_START}—{core.PERIOD_END}，实际 {period!r}", stage)
    _require(entity["cutoff_date"] == core.CUTOFF_DATE, f"{label}.entity.cutoff_date",
             f"必须是 {core.CUTOFF_DATE}", stage)
    _require(entity["currency"] == core.CURRENCY, f"{label}.entity.currency",
             f"必须是 {core.CURRENCY}", stage)
    _require(isinstance(packet.get("banner"), list) and bool(packet["banner"]),
             f"{label}.banner", "必须是非空列表", stage)
    _require(isinstance(packet.get("limits"), list) and bool(packet["limits"]),
             f"{label}.limits", "必须是非空限制列表", stage)
    bindings = packet.get("bindings")
    _require(isinstance(bindings, dict), f"{label}.bindings", "必须是对象", stage)
    _require_keys(bindings, ("workbook_sha256", "normalized_payload_sha256",
                             "screening_report_sha256", "crosscheck_report_sha256",
                             "upstream_versions", "upstream_declared_database"),
                  f"{label}.bindings", stage)
    # 三对象与工作簿绑定：必须是对象规范指纹，不得与文件字节哈希混用
    _require(bindings["normalized_payload_sha256"] == expected["normalized_payload_sha256"],
             f"{label}.bindings.normalized_payload_sha256",
             "必须等于本批次 normalized 对象的规范指纹", stage)
    _require(bindings["screening_report_sha256"] == expected["screening_report_canonical_sha256"],
             f"{label}.bindings.screening_report_sha256",
             "必须等于本批次筛查报告对象的规范指纹", stage)
    _require(bindings["crosscheck_report_sha256"] == expected["crosscheck_report_canonical_sha256"],
             f"{label}.bindings.crosscheck_report_sha256",
             "必须等于本批次复算报告对象的规范指纹", stage)
    _require(bindings["workbook_sha256"] == expected["workbook_sha256"],
             f"{label}.bindings.workbook_sha256", "必须等于本批次输入工作簿的原始哈希", stage)
    versions = bindings["upstream_versions"]
    _require(isinstance(versions, dict), f"{label}.bindings.upstream_versions", "必须是对象", stage)
    _require(versions.get("normalization") == NORMALIZER_MODULE.NORMALIZATION_VERSION,
             f"{label}.bindings.upstream_versions.normalization",
             f"必须是 {NORMALIZER_MODULE.NORMALIZATION_VERSION}", stage)
    _require(versions.get("rule_core") == SCREEN_MODULE.RULE_CORE_VERSION,
             f"{label}.bindings.upstream_versions.rule_core",
             f"必须是 {SCREEN_MODULE.RULE_CORE_VERSION}", stage)
    _require(versions.get("crosscheck") == CROSSCHECK_MODULE.CROSSCHECK_VERSION,
             f"{label}.bindings.upstream_versions.crosscheck",
             f"必须是 {CROSSCHECK_MODULE.CROSSCHECK_VERSION}", stage)
    summary = packet.get("summary")
    _require(isinstance(summary, dict), f"{label}.summary", "必须是对象", stage)
    _require_keys(summary, ("rule_counts", "total_findings", "involved_payments",
                            "r02_overpayment_total_cents", "r02_overpayment_basis"),
                  f"{label}.summary", stage)
    rule_counts = summary["rule_counts"]
    _require(isinstance(rule_counts, dict) and set(rule_counts) == set(core.RULE_IDS),
             f"{label}.summary.rule_counts",
             f"必须恰为 {list(core.RULE_IDS)}，实际 {sorted(rule_counts) if isinstance(rule_counts, dict) else rule_counts!r}",
             stage)
    for rule_id in core.RULE_IDS:
        _require(isinstance(rule_counts[rule_id], int) and not isinstance(rule_counts[rule_id], bool),
                 f"{label}.summary.rule_counts.{rule_id}", "必须是严格整数", stage)
    _require(isinstance(summary["total_findings"], int)
             and not isinstance(summary["total_findings"], bool),
             f"{label}.summary.total_findings", "必须是严格整数", stage)
    findings = packet.get("findings")
    _require(isinstance(findings, list), f"{label}.findings", "必须是列表", stage)
    _require(summary["total_findings"] == len(findings), f"{label}.summary.total_findings",
             f"必须等于 findings 条数 {len(findings)}，实际 {summary['total_findings']}", stage)
    _require(isinstance(packet.get("reconciliation"), dict), f"{label}.reconciliation",
             "必须是对象", stage)
    _require(isinstance(packet.get("amount_labels"), dict), f"{label}.amount_labels",
             "必须是对象", stage)
    return {"rule_counts": dict(rule_counts), "total_findings": len(findings),
            "r02_overpayment_total_cents": summary.get("r02_overpayment_total_cents"),
            "findings": findings}


def _verify_fact_packet_operation(payload: dict, previous_payload: dict, state: dict,
                                   label: str, stage: str, batch_dir: Path, manifest: dict, *,
                                   previous_file_sha256: str, upstream_expected: dict,
                                   host_manifest_file_sha256: str) -> dict:
    """0007 只允许从合法 0006 的 DEV_GATE2_APPROVED + RULE_CROSSCHECK_RECORDED 延续一次底稿构建。"""
    operation = payload["operation"]
    _require(operation.get("kind") == OPERATION_BUILD_FACT_PACKET, f"{label}.operation.kind",
             f"0007 必须是 {OPERATION_BUILD_FACT_PACKET}，实际 {operation.get('kind')!r}", stage)
    _require_keys(operation, ("at_utc", "artifacts", "artifacts_file_sha256",
                              "packet_file_sha256", "packet_sha256", "markdown_file_sha256",
                              "started_file_sha256", "database_sha256", "phase_after",
                              "bindings_sha256", "fact_packet_status", "packet_relative",
                              "markdown_relative", "artifacts_relative", "started_relative",
                              "core_path", "core_sha256", "core_version", "packet_version",
                              "normalized_file_sha256", "screening_report_file_sha256",
                              "crosscheck_report_file_sha256",
                              "previous_checkpoint_file_sha256"),
                  f"{label}.operation", stage)
    previous_workflow = previous_payload["workflow"]
    previous_state = previous_workflow["state"]
    _require(previous_state["phase"] == CONTROLLER_MODULE.PHASE_G2_APPROVED, f"{label}.previous.phase",
             f"0007 只能从 {CONTROLLER_MODULE.PHASE_G2_APPROVED} 的 0006 延续，实际 "
             f"{previous_state['phase']!r}", stage)
    _require(previous_payload["operation"].get("kind") == OPERATION_RUN_RULE_CROSSCHECK,
             f"{label}.previous.operation.kind",
             "0007 的前序必须是 0006 的复算凭证", stage)
    _require(canonical_json(payload["workflow"]) == canonical_json(previous_workflow),
             f"{label}.workflow",
             "0007 的完整 workflow 必须与 0006 严格相等（底稿构建不改变控制器状态、不新增决定或请求）",
             stage)
    decisions = state["simulated_decisions"]
    _require(isinstance(decisions, list) and len(decisions) == 2, f"{label}.state.simulated_decisions",
             "模拟决定必须恰为 Gate1 与 Gate2 两条", stage)
    _require(operation["phase_after"] == state["phase"], f"{label}.operation.phase_after",
             "操作摘要的 phase 必须与实际状态一致", stage)
    _require(operation["bindings_sha256"] == state["run_bindings_sha256"],
             f"{label}.operation.bindings_sha256", "必须与 workflow 绑定一致", stage)
    _require(operation["fact_packet_status"] == FACT_PACKET_STATUS_RECORDED,
             f"{label}.operation.fact_packet_status",
             f"必须是 {FACT_PACKET_STATUS_RECORDED}，实际 {operation['fact_packet_status']!r}", stage)
    _require(state["batch_id"] == payload["batch_id"], f"{label}.workflow.state.batch_id",
             "workflow 批次必须与 checkpoint 一致", stage)
    _require(operation["previous_checkpoint_file_sha256"] == previous_file_sha256,
             f"{label}.operation.previous_checkpoint_file_sha256",
             "必须等于 0006 的初始实读字节哈希", stage)

    # 0006 的复算材料核验保留到 0007 恢复：不跳过筛查/复算产物与数据库核验
    _require(isinstance(upstream_expected, dict) and bool(upstream_expected),
             f"{label}.upstream_expected",
             "0007 恢复必须带出 0006 的初次核验读数（不得跳过数据库与上游产物核验）", stage)
    screen = _read_screen_outputs(batch_dir, stage)
    crosscheck = _read_crosscheck_outputs(batch_dir, stage)
    gate2_outputs = _read_gate2_outputs(batch_dir, stage)
    gate2_paths = _gate2_paths(batch_dir, stage)
    actual_database_sha = file_sha256(gate2_paths["database_path"])
    for key, value, field in (
        ("screening_started_file_sha256", screen["started_file_sha256"],
         f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}"),
        ("screening_report_file_sha256", screen["report_file_sha256"],
         f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}"),
        ("screening_artifacts_file_sha256", screen["artifacts_file_sha256"],
         f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}"),
        ("crosscheck_started_file_sha256", crosscheck["started_file_sha256"],
         f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_START}"),
        ("crosscheck_report_file_sha256", crosscheck["report_file_sha256"],
         f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}"),
        ("crosscheck_artifacts_file_sha256", crosscheck["artifacts_file_sha256"],
         f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}"),
        ("gate2_normalized_file_sha256", gate2_outputs["normalized_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}"),
        ("gate2_load_report_file_sha256", gate2_outputs["load_report_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}"),
        ("gate2_artifacts_file_sha256", gate2_outputs["artifacts_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"),
        ("database_sha256", actual_database_sha, str(gate2_paths["database_path"])),
    ):
        _require(upstream_expected.get(key) == value, field,
                 f"上游材料在底稿恢复时发生了变化：期望 {upstream_expected.get(key)!r}，"
                 f"实际 {value!r}", stage)

    paths = _fact_packet_paths(batch_dir)
    actual = _read_fact_packet_outputs(batch_dir, stage)
    started = actual["started"]
    started_label = f"{paths['relative']}/{FACT_PACKET_START}"
    _require_keys(started, FACT_PACKET_START_REQUIRED_KEYS, started_label, stage)
    _require(started["start_version"] == FACT_PACKET_START_VERSION, f"{started_label}.start_version",
             f"必须是 {FACT_PACKET_START_VERSION}，实际 {started['start_version']!r}", stage)
    _require(started["batch_id"] == batch_dir.name, f"{started_label}.batch_id",
             "必须与批次目录叶子一致", stage)
    _require(started["host_version"] == HOST_VERSION, f"{started_label}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}，实际 {started['host_version']!r}", stage)
    _require(started["operation_kind"] == OPERATION_BUILD_FACT_PACKET,
             f"{started_label}.operation_kind", f"必须是 {OPERATION_BUILD_FACT_PACKET}", stage)
    _require(started["source_checkpoint_file_sha256"] == previous_file_sha256,
             f"{started_label}.source_checkpoint_file_sha256",
             "必须等于 0006 的初始实读字节哈希", stage)
    _require(started["host_manifest_file_sha256"] == host_manifest_file_sha256,
             f"{started_label}.host_manifest_file_sha256",
             "必须等于初始实读宿主清单文件字节哈希", stage)
    _require(started["run_bindings_sha256"] == state["run_bindings_sha256"],
             f"{started_label}.run_bindings_sha256", "必须等于 workflow 创建绑定指纹", stage)
    _require(started["core_path"] == str(FACT_PACKET_CORE_PATH), f"{started_label}.core_path",
             "必须是冻结事实底稿核心固定路径", stage)
    _require(started["core_sha256"] == manifest["bindings"]["code_sha256"]["build_demo_fact_packet"],
             f"{started_label}.core_sha256", "必须等于冻结事实底稿核心实际字节哈希", stage)
    _require(started["core_version"] == FACT_PACKET_MODULE.PACKET_VERSION,
             f"{started_label}.core_version",
             f"必须是 {FACT_PACKET_MODULE.PACKET_VERSION}", stage)
    for key, value, field in (
        ("normalized_file_sha256", gate2_outputs["normalized_file_sha256"],
         f"{started_label}.normalized_file_sha256"),
        ("screening_report_file_sha256", screen["report_file_sha256"],
         f"{started_label}.screening_report_file_sha256"),
        ("crosscheck_report_file_sha256", crosscheck["report_file_sha256"],
         f"{started_label}.crosscheck_report_file_sha256"),
    ):
        _require(started[key] == value, field, "必须等于本批次本次实读对应文件字节哈希", stage)
    _require(started["normalized_payload_sha256"] == canonical_sha256(gate2_outputs["normalized"]),
             f"{started_label}.normalized_payload_sha256",
             "必须等于本批次 normalized 对象的规范指纹", stage)
    _require(started["screening_report_canonical_sha256"] == canonical_sha256(screen["report"]),
             f"{started_label}.screening_report_canonical_sha256",
             "必须等于本批次筛查报告对象的规范指纹", stage)
    _require(started["crosscheck_report_canonical_sha256"] == canonical_sha256(crosscheck["report"]),
             f"{started_label}.crosscheck_report_canonical_sha256",
             "必须等于本批次复算报告对象的规范指纹", stage)
    _require(started["database_path"] == str(gate2_paths["database_path"]),
             f"{started_label}.database_path", "必须是宿主推导的固定数据库路径", stage)
    _require(started["database_sha256"] == actual_database_sha, f"{started_label}.database_sha256",
             "必须等于数据库实际字节哈希", stage)

    artifacts = actual["artifacts"]
    artifacts_label = f"{paths['relative']}/{FACT_PACKET_ARTIFACTS}"
    _require_keys(artifacts, FACT_PACKET_ARTIFACTS_REQUIRED_KEYS, artifacts_label, stage)
    _require(artifacts["artifacts_version"] == FACT_PACKET_ARTIFACTS_VERSION,
             f"{artifacts_label}.artifacts_version",
             f"必须是 {FACT_PACKET_ARTIFACTS_VERSION}，实际 {artifacts['artifacts_version']!r}", stage)
    _require(artifacts["batch_id"] == batch_dir.name, f"{artifacts_label}.batch_id",
             "必须与批次目录叶子一致", stage)
    _require(artifacts["host_version"] == HOST_VERSION, f"{artifacts_label}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}", stage)
    _require(artifacts["operation_kind"] == OPERATION_BUILD_FACT_PACKET,
             f"{artifacts_label}.operation_kind", f"必须是 {OPERATION_BUILD_FACT_PACKET}", stage)
    _require(artifacts["core_path"] == str(FACT_PACKET_CORE_PATH), f"{artifacts_label}.core_path",
             "必须是冻结事实底稿核心固定路径", stage)
    _require(artifacts["core_sha256"] == manifest["bindings"]["code_sha256"]["build_demo_fact_packet"],
             f"{artifacts_label}.core_sha256", "必须等于冻结事实底稿核心实际字节哈希", stage)
    _require(artifacts["core_version"] == FACT_PACKET_MODULE.PACKET_VERSION,
             f"{artifacts_label}.core_version",
             f"必须是 {FACT_PACKET_MODULE.PACKET_VERSION}", stage)
    _require(artifacts["fact_packet_status"] == FACT_PACKET_STATUS_RECORDED,
             f"{artifacts_label}.fact_packet_status",
             f"必须是 {FACT_PACKET_STATUS_RECORDED}", stage)
    _require(isinstance(artifacts["matched"], bool), f"{artifacts_label}.matched",
             f"必须是严格布尔，实际 {type(artifacts['matched']).__name__}", stage)
    _require(artifacts["started_file_sha256"] == actual["started_file_sha256"],
             f"{artifacts_label}.started_file_sha256", "必须等于 started 文件实际字节哈希", stage)
    _require(artifacts["previous_checkpoint_file_sha256"] == previous_file_sha256,
             f"{artifacts_label}.previous_checkpoint_file_sha256",
             "必须等于 0006 的初始实读字节哈希", stage)
    _require(artifacts["previous_checkpoint_relative"]
             == f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0006.json",
             f"{artifacts_label}.previous_checkpoint_relative", "必须是固定相对路径", stage)
    _require(artifacts["host_manifest_file_sha256"] == host_manifest_file_sha256,
             f"{artifacts_label}.host_manifest_file_sha256",
             "必须等于初始实读宿主清单文件字节哈希", stage)
    _require(artifacts["run_bindings_sha256"] == state["run_bindings_sha256"],
             f"{artifacts_label}.run_bindings_sha256", "必须等于 workflow 创建绑定指纹", stage)
    _require(artifacts["packet_relative"] == f"{paths['relative']}/{FACT_PACKET_JSON}",
             f"{artifacts_label}.packet_relative", "必须是固定相对路径", stage)
    _require(artifacts["markdown_relative"] == f"{paths['relative']}/{FACT_PACKET_MARKDOWN}",
             f"{artifacts_label}.markdown_relative", "必须是固定相对路径", stage)
    _require(artifacts["started_relative"] == f"{paths['relative']}/{FACT_PACKET_START}",
             f"{artifacts_label}.started_relative", "必须是固定相对路径", stage)
    _require(artifacts["packet_file_sha256"] == actual["packet_file_sha256"],
             f"{artifacts_label}.packet_file_sha256", "必须等于 packet JSON 实际文件字节哈希", stage)
    _require(artifacts["markdown_file_sha256"] == actual["markdown_file_sha256"],
             f"{artifacts_label}.markdown_file_sha256",
             "必须等于 Markdown 实际文件字节哈希", stage)
    _require(artifacts["packet_sha256"] == canonical_sha256(actual["packet"]),
             f"{artifacts_label}.packet_sha256",
             "必须等于 packet 对象的实际规范指纹（不得与文件字节哈希混用）", stage)
    _require(artifacts["database_path"] == str(gate2_paths["database_path"]),
             f"{artifacts_label}.database_path", "必须是宿主推导的固定数据库路径", stage)
    _require(artifacts["database_sha256"] == actual_database_sha,
             f"{artifacts_label}.database_sha256", "必须等于数据库实际字节哈希", stage)
    _require(artifacts["cutoff_date"] == SCREEN_CUTOFF_DATE, f"{artifacts_label}.cutoff_date",
             f"必须是 {SCREEN_CUTOFF_DATE}", stage)
    gate2_body_sha = canonical_sha256({key: value for key, value in decisions[-1].items()
                                       if key != "decision_sha256"})
    _require(artifacts["gate2_decision_sha256"] == gate2_body_sha,
             f"{artifacts_label}.gate2_decision_sha256",
             "必须等于本 workflow 已验证 Gate2 APPROVE 正文指纹", stage)
    for key, value in (("normalized_file_sha256", gate2_outputs["normalized_file_sha256"]),
                       ("screening_report_file_sha256", screen["report_file_sha256"]),
                       ("crosscheck_report_file_sha256", crosscheck["report_file_sha256"]),
                       ("screening_artifacts_file_sha256", screen["artifacts_file_sha256"]),
                       ("crosscheck_artifacts_file_sha256", crosscheck["artifacts_file_sha256"]),
                       ("gate2_normalized_file_sha256", gate2_outputs["normalized_file_sha256"]),
                       ("gate2_load_report_file_sha256", gate2_outputs["load_report_file_sha256"]),
                       ("gate2_artifacts_file_sha256", gate2_outputs["artifacts_file_sha256"])):
        _require(artifacts[key] == value, f"{artifacts_label}.{key}",
                 "必须等于本批次本次实读对应文件字节哈希", stage)
    _require(artifacts["normalized_payload_sha256"] == canonical_sha256(gate2_outputs["normalized"]),
             f"{artifacts_label}.normalized_payload_sha256",
             "必须等于本批次 normalized 对象的规范指纹", stage)
    _require(artifacts["screening_report_canonical_sha256"] == canonical_sha256(screen["report"]),
             f"{artifacts_label}.screening_report_canonical_sha256",
             "必须等于本批次筛查报告对象的规范指纹", stage)
    _require(artifacts["crosscheck_report_canonical_sha256"]
             == canonical_sha256(crosscheck["report"]),
             f"{artifacts_label}.crosscheck_report_canonical_sha256",
             "必须等于本批次复算报告对象的规范指纹", stage)

    # 报告对象本身：协议与来源绑定（不重新构建、不重新渲染）
    _require(artifacts["packet_version"] == actual["packet"].get("packet_version"),
             f"{artifacts_label}.packet_version", "必须等于 packet 对象的版本", stage)
    protocol = _packet_protocol_report(actual["packet"], {
        "normalized_payload_sha256": canonical_sha256(gate2_outputs["normalized"]),
        "screening_report_canonical_sha256": canonical_sha256(screen["report"]),
        "crosscheck_report_canonical_sha256": canonical_sha256(crosscheck["report"]),
        "workbook_sha256": ((gate2_outputs["normalized"].get("source") or {}).get("input_sha256")
                            or (gate2_outputs["load_report"].get("run_metadata") or {}).get(
                                "input_sha256")),
    }, stage, f"{paths['relative']}/{FACT_PACKET_JSON}")
    _require(artifacts["findings_total"] == protocol["total_findings"],
             f"{artifacts_label}.findings_total", "必须等于 packet 实际 findings 条数", stage)
    _require(canonical_json(artifacts["rule_counts"]) == canonical_json(protocol["rule_counts"]),
             f"{artifacts_label}.rule_counts", "必须等于 packet 实际规则计数", stage)
    _require(canonical_json(artifacts["period"]) == canonical_json(
        {"period_start": FACT_PACKET_MODULE.PERIOD_START,
         "period_end": FACT_PACKET_MODULE.PERIOD_END}),
        f"{artifacts_label}.period", "必须是固定期间", stage)

    _require(operation["packet_file_sha256"] == actual["packet_file_sha256"],
             f"{label}.operation.packet_file_sha256", "必须等于 packet 文件实际字节哈希", stage)
    _require(operation["markdown_file_sha256"] == actual["markdown_file_sha256"],
             f"{label}.operation.markdown_file_sha256", "必须等于 Markdown 实际字节哈希", stage)
    _require(operation["packet_sha256"] == canonical_sha256(actual["packet"]),
             f"{label}.operation.packet_sha256", "必须等于 packet 对象实际规范指纹", stage)
    _require(operation["artifacts_file_sha256"] == actual["artifacts_file_sha256"],
             f"{label}.operation.artifacts_file_sha256", "必须等于 artifacts 文件实际字节哈希", stage)
    _require(operation["started_file_sha256"] == actual["started_file_sha256"],
             f"{label}.operation.started_file_sha256", "必须等于 started 文件实际字节哈希", stage)
    _require(operation["database_sha256"] == actual_database_sha,
             f"{label}.operation.database_sha256", "必须等于数据库实际字节哈希", stage)
    _require(operation["packet_relative"] == f"{paths['relative']}/{FACT_PACKET_JSON}",
             f"{label}.operation.packet_relative", "必须是固定相对路径", stage)
    _require(operation["markdown_relative"] == f"{paths['relative']}/{FACT_PACKET_MARKDOWN}",
             f"{label}.operation.markdown_relative", "必须是固定相对路径", stage)
    _require(operation["artifacts_relative"] == f"{paths['relative']}/{FACT_PACKET_ARTIFACTS}",
             f"{label}.operation.artifacts_relative", "必须是固定相对路径", stage)
    _require(operation["started_relative"] == f"{paths['relative']}/{FACT_PACKET_START}",
             f"{label}.operation.started_relative", "必须是固定相对路径", stage)
    _require(operation["core_path"] == str(FACT_PACKET_CORE_PATH), f"{label}.operation.core_path",
             "必须是冻结事实底稿核心固定路径", stage)
    _require(operation["core_sha256"]
             == manifest["bindings"]["code_sha256"]["build_demo_fact_packet"],
             f"{label}.operation.core_sha256", "必须等于冻结事实底稿核心实际字节哈希", stage)
    _require(operation["core_version"] == FACT_PACKET_MODULE.PACKET_VERSION,
             f"{label}.operation.core_version",
             f"必须是 {FACT_PACKET_MODULE.PACKET_VERSION}", stage)
    _require(operation["packet_version"] == actual["packet"].get("packet_version"),
             f"{label}.operation.packet_version", "必须等于 packet 对象的版本", stage)
    _require(operation["normalized_file_sha256"] == gate2_outputs["normalized_file_sha256"],
             f"{label}.operation.normalized_file_sha256",
             "必须等于本次实读 normalized 文件字节哈希", stage)
    _require(operation["screening_report_file_sha256"] == screen["report_file_sha256"],
             f"{label}.operation.screening_report_file_sha256",
             "必须等于本次实读筛查报告文件字节哈希", stage)
    _require(operation["crosscheck_report_file_sha256"] == crosscheck["report_file_sha256"],
             f"{label}.operation.crosscheck_report_file_sha256",
             "必须等于本次实读复算报告文件字节哈希", stage)
    # 内嵌副本先验形状，再与实际已验证 artifacts 完整严格相等
    embedded = operation["artifacts"]
    _require(isinstance(embedded, dict), f"{label}.operation.artifacts",
             f"必须是对象（内嵌 artifacts 完整副本），实际 {type(embedded).__name__}", stage)
    _require_keys(embedded, FACT_PACKET_ARTIFACTS_REQUIRED_KEYS, f"{label}.operation.artifacts",
                  stage)
    _require(canonical_json(embedded) == canonical_json(artifacts), f"{label}.operation.artifacts",
             "内嵌 artifacts 副本必须与磁盘实际 artifacts 对象完整严格相等"
             "（不得留两套矛盾来源）", stage)
    return {
        "started_file_sha256": actual["started_file_sha256"],
        "packet_file_sha256": actual["packet_file_sha256"],
        "markdown_file_sha256": actual["markdown_file_sha256"],
        "artifacts_file_sha256": actual["artifacts_file_sha256"],
        "packet_sha256": canonical_sha256(actual["packet"]),
        "database_path": str(gate2_paths["database_path"]),
        "database_sha256": actual_database_sha,
        "screening_started_file_sha256": screen["started_file_sha256"],
        "screening_report_file_sha256": screen["report_file_sha256"],
        "screening_artifacts_file_sha256": screen["artifacts_file_sha256"],
        "crosscheck_started_file_sha256": crosscheck["started_file_sha256"],
        "crosscheck_report_file_sha256": crosscheck["report_file_sha256"],
        "crosscheck_artifacts_file_sha256": crosscheck["artifacts_file_sha256"],
        "gate2_normalized_file_sha256": gate2_outputs["normalized_file_sha256"],
        "gate2_load_report_file_sha256": gate2_outputs["load_report_file_sha256"],
        "gate2_artifacts_file_sha256": gate2_outputs["artifacts_file_sha256"],
        "packet_protocol": {key: value for key, value in protocol.items() if key != "findings"},
    }


# ---------------------------------------------------------------------------
# TASK-017 模拟独立初判层
# ---------------------------------------------------------------------------


def _initial_judgment_dir(batch_dir: Path) -> Path:
    return _host_workflow_dir(batch_dir) / INITIAL_JUDGMENT_DIR


def _initial_judgment_paths(batch_dir: Path) -> dict:
    directory = _initial_judgment_dir(batch_dir)
    return {"directory": directory, "dir": directory,
            "relative": f"{WORKFLOW_DIR}/{INITIAL_JUDGMENT_DIR}",
            "started_path": directory / INITIAL_JUDGMENT_START,
            "submission_path": directory / INITIAL_JUDGMENT_SUBMISSION,
            "record_path": directory / INITIAL_JUDGMENT_RECORD,
            "artifacts_path": directory / INITIAL_JUDGMENT_ARTIFACTS,
            "failure_path": directory / INITIAL_JUDGMENT_FAILURE}


def _initial_judgment_observed_state(batch_dir: Path) -> dict:
    """尽力采集失败现场的已知产物引用（只读、不存在即记 null）。"""
    paths = _initial_judgment_paths(batch_dir)
    observed = {"directory_exists": paths["directory"].exists()}
    for key, path in (("started", paths["started_path"]),
                      ("submission", paths["submission_path"]),
                      ("record", paths["record_path"]),
                      ("artifacts", paths["artifacts_path"]),
                      ("failure", paths["failure_path"])):
        observed[f"{key}_present"] = path.is_file()
        try:
            observed[f"{key}_file_sha256"] = file_sha256(path) if path.is_file() else None
        except OSError:
            observed[f"{key}_file_sha256"] = None
    checkpoint8 = _checkpoint_path(batch_dir, 8)
    observed["checkpoint_0008_present"] = checkpoint8.is_file()
    try:
        observed["checkpoint_0008_file_sha256"] = (file_sha256(checkpoint8)
                                                  if checkpoint8.is_file() else None)
    except OSError:
        observed["checkpoint_0008_file_sha256"] = None
    return observed


def _save_initial_judgment_failure(batch_dir: Path, stage_label: str, exc: Exception,
                                   observed: dict) -> str:
    """本次真正创建了 initial_judgment 目录之后才写失败诊断（独占创建，不覆盖）。"""
    paths = _initial_judgment_paths(batch_dir)
    _ensure_dir(paths["directory"], stage_label)
    target_exit_code = (EXIT_ERROR
                        if type(exc).__name__ in INITIAL_JUDGMENT_RUNTIME_FAILURE_CLASSES
                        else EXIT_BLOCKED)
    observed = dict(observed or {})
    observed["target_exit_code"] = target_exit_code
    observed["exception_class"] = type(exc).__name__
    exception_chain = getattr(exc, "original_exception_chain", None) or _exception_chain(exc)
    payload = {
        "failure_version": INITIAL_JUDGMENT_FAILURE_VERSION,
        "batch_id": batch_dir.name,
        "host_version": HOST_VERSION,
        "recorded_at_utc": _now_utc(),
        "stage": stage_label,
        "exception_class": type(exc).__name__,
        "target_exit_code": target_exit_code,
        "message": str(exc),
        "reasons": list(getattr(exc, "reasons", []) or [str(exc)]),
        "exception_chain": exception_chain,
        "observed_outputs": observed,
    }
    path = paths["failure_path"]
    if path.exists():
        raise WorkflowHostBlocked(
            f"失败诊断已存在，不覆盖：{paths['relative']}/{INITIAL_JUDGMENT_FAILURE}",
            stage=stage_label)
    sha = _write_exclusive_json(path, payload, stage_label)
    readback, readback_sha = _read_json_with_bytes(
        path, f"{paths['relative']}/{INITIAL_JUDGMENT_FAILURE}", stage_label)
    _require(readback_sha == sha, f"{paths['relative']}/{INITIAL_JUDGMENT_FAILURE}",
             "写后读回的失败诊断字节哈希与写入结果不一致", stage_label)
    _require(canonical_json(readback) == canonical_json(payload),
             f"{paths['relative']}/{INITIAL_JUDGMENT_FAILURE}",
             "写后读回的失败诊断内容与写入结果不一致", stage_label)
    return sha


def _load_initial_judgment_failure(batch_dir: Path, stage: str):
    """读取并严格核验模拟初判失败诊断；不存在返回 None。"""
    paths = _initial_judgment_paths(batch_dir)
    path = paths["failure_path"]
    if not path.exists():
        return None
    label = f"{paths['relative']}/{INITIAL_JUDGMENT_FAILURE}"
    _require(path.is_file(), label, "失败诊断必须是普通文件", stage)
    payload = _read_json(path, label, stage)
    _require_keys(payload, ("failure_version", "batch_id", "host_version", "recorded_at_utc",
                            "stage", "exception_class", "target_exit_code", "message", "reasons",
                            "exception_chain", "observed_outputs"), label, stage)
    _require(payload["failure_version"] == INITIAL_JUDGMENT_FAILURE_VERSION,
             f"{label}.failure_version",
             f"必须是 {INITIAL_JUDGMENT_FAILURE_VERSION}，实际 {payload['failure_version']!r}",
             stage)
    _require(payload["batch_id"] == batch_dir.name, f"{label}.batch_id", "必须与本批次一致", stage)
    _require(payload["host_version"] == HOST_VERSION, f"{label}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}，实际 {payload['host_version']!r}", stage)
    _require(isinstance(payload["target_exit_code"], int)
             and not isinstance(payload["target_exit_code"], bool)
             and payload["target_exit_code"] in (EXIT_BLOCKED, EXIT_ERROR),
             f"{label}.target_exit_code",
             f"必须是严格整数 1／2，实际 {payload['target_exit_code']!r}", stage)
    _require(isinstance(payload["reasons"], list) and bool(payload["reasons"]), f"{label}.reasons",
             "必须是非空原因列表", stage)
    _require(isinstance(payload["exception_chain"], list) and bool(payload["exception_chain"]),
             f"{label}.exception_chain", "必须保存非空完整异常链（含原始 cause／context）", stage)
    for link_index, link in enumerate(payload["exception_chain"]):
        _require(isinstance(link, dict) and isinstance(link.get("class"), str)
                 and isinstance(link.get("message"), str), f"{label}.exception_chain[{link_index}]",
                 "每一环必须是含 class 与 message 字符串的对象", stage)
    _require(isinstance(payload["stage"], str) and payload["stage"].startswith(INITIAL_JUDGMENT_STAGE),
             f"{label}.stage",
             f"模拟初判失败诊断的阶段必须是 {INITIAL_JUDGMENT_STAGE} 阶段，"
             f"实际 {payload['stage']!r}", stage)
    return payload


def _initial_judgment_failure_exception(failure: dict) -> Exception:
    reasons = [str(item) for item in failure["reasons"]]
    message = (f"该批次的 {WORKFLOW_DIR}/{INITIAL_JUDGMENT_DIR}/ 记录了未完成的模拟初判保存尝试："
               f"stage={failure['stage']!r}；异常类别={failure['exception_class']!r}；原因={reasons!r}。"
               "即使存在可解析的完整 0008，也不得宣告本次保存成功；不重试、不复用、不自动删除，"
               "需继续时新建批次。")
    if failure["target_exit_code"] == EXIT_ERROR:
        return WorkflowHostError(message, reasons=reasons, stage=failure["stage"])
    return WorkflowHostBlocked(message, reasons=reasons, stage=failure["stage"])


def _raise_incomplete_initial_judgment(batch_dir: Path, chain: dict) -> None:
    revision = chain["current"]["revision"]
    raise WorkflowHostBlocked(
        f"该批次的 {WORKFLOW_DIR}/{INITIAL_JUDGMENT_DIR}/ 已开始但没有完整有效的 0008"
        f"（当前为第 {revision} 份 checkpoint）：模拟初判保存未完成。不重试、不复用、不自动删除，"
        "不猜测成功、不退回旧状态，需续写时新建批次。", stage="status")


def _read_initial_judgment_outputs(batch_dir: Path, stage: str) -> dict:
    """从固定路径实读本次模拟初判产物；JSON 对象与文件字节哈希来自同一次读取缓冲。"""
    paths = _initial_judgment_paths(batch_dir)
    for path, label in ((paths["started_path"], INITIAL_JUDGMENT_START),
                        (paths["submission_path"], INITIAL_JUDGMENT_SUBMISSION),
                        (paths["record_path"], INITIAL_JUDGMENT_RECORD),
                        (paths["artifacts_path"], INITIAL_JUDGMENT_ARTIFACTS)):
        _require(path.is_file(), f"{paths['relative']}/{label}",
                 f"缺少本次模拟初判产物文件（{path}）", stage)
    started, started_sha = _read_json_with_bytes(
        paths["started_path"], f"{paths['relative']}/{INITIAL_JUDGMENT_START}", stage)
    submission, submission_sha = _read_json_with_bytes(
        paths["submission_path"], f"{paths['relative']}/{INITIAL_JUDGMENT_SUBMISSION}", stage)
    record, record_sha = _read_json_with_bytes(
        paths["record_path"], f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}", stage)
    artifacts, artifacts_sha = _read_json_with_bytes(
        paths["artifacts_path"], f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}", stage)
    return {"started": started, "submission": submission, "record_payload": record,
            "artifacts": artifacts,
            "started_file_sha256": started_sha, "submission_file_sha256": submission_sha,
            "record_file_sha256": record_sha, "artifacts_file_sha256": artifacts_sha,
            "started_path": paths["started_path"], "submission_path": paths["submission_path"],
            "record_path": paths["record_path"], "artifacts_path": paths["artifacts_path"]}


def _verify_initial_judgment_tail(batch_dir: Path, expected: dict, stage: str) -> dict:
    """模拟初判收尾一致性：复测 4 份产物实际文件字节（固定路径）+ 数据库 + 目录白名单。"""
    paths = _initial_judgment_paths(batch_dir)
    actual = {
        "started_file_sha256": file_sha256(paths["started_path"]),
        "submission_file_sha256": file_sha256(paths["submission_path"]),
        "record_file_sha256": file_sha256(paths["record_path"]),
        "artifacts_file_sha256": file_sha256(paths["artifacts_path"]),
    }
    labels = {"started_file_sha256": f"{paths['relative']}/{INITIAL_JUDGMENT_START}",
              "submission_file_sha256": f"{paths['relative']}/{INITIAL_JUDGMENT_SUBMISSION}",
              "record_file_sha256": f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}",
              "artifacts_file_sha256": f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}"}
    for key, value in actual.items():
        _require(expected.get(key) == value, labels[key],
                 f"收尾复测发现本次模拟初判产物发生变化：期望 {expected.get(key)!r}，实际 {value!r}",
                 stage)
    database_path = expected.get("database_path")
    _require(isinstance(database_path, str), "initial_judgment.expected.database_path",
             "收尾复测必须带出固定数据库路径", stage)
    _require(expected.get("database_sha256") == file_sha256(Path(database_path)),
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_DATABASE_NAME}",
             "收尾复测发现数据库字节变化", stage)
    _require(not paths["failure_path"].exists(), f"{paths['relative']}/{INITIAL_JUDGMENT_FAILURE}",
             "成功收尾不得存在失败诊断", stage)
    for name in sorted(item.name for item in paths["directory"].iterdir()):
        _require(name in (INITIAL_JUDGMENT_START, INITIAL_JUDGMENT_SUBMISSION,
                          INITIAL_JUDGMENT_RECORD, INITIAL_JUDGMENT_ARTIFACTS),
                 f"{paths['relative']}/{name}",
                 "成功批次的模拟初判目录只允许既定产物文件", stage)
    return actual


def _initial_judgment_record_report(record_payload: dict, packet: dict, submission: dict,
                                    stage: str, label: str) -> dict:
    """核验冻结核心完整返回的协议形状与来源绑定（不重写判断算法、不重新判分）。"""
    core = INITIAL_JUDGMENT_MODULE
    _require(isinstance(record_payload, dict), label, "必须是对象", stage)
    _require(set(record_payload.keys()) == {"record", "record_sha256"}, label,
             f"核心返回外层必须恰为 record/record_sha256，实际 {sorted(record_payload)}", stage)
    record = record_payload["record"]
    record_sha256 = record_payload["record_sha256"]
    _require(isinstance(record, dict), f"{label}.record",
             f"必须是对象，实际 {type(record).__name__}", stage)
    _require(isinstance(record_sha256, str) and bool(HASH_PATTERN.match(record_sha256)),
             f"{label}.record_sha256", f"必须是 64 位小写十六进制字符串，实际 {record_sha256!r}",
             stage)
    _require(record_sha256 == canonical_sha256(record), f"{label}.record_sha256",
             "必须等于 record 对象的规范 JSON SHA-256（不得是文件字节哈希）", stage)
    _require(record.get("record_version") == core.RECORD_VERSION, f"{label}.record.record_version",
             f"必须是 {core.RECORD_VERSION}，实际 {record.get('record_version')!r}", stage)
    _require(record.get("batch_status") == core.RECORD_STATUS, f"{label}.record.batch_status",
             f"必须是 {core.RECORD_STATUS}，实际 {record.get('batch_status')!r}", stage)
    _require(record.get("mode") == MODE, f"{label}.record.mode", f"必须是 {MODE}", stage)
    _require(record.get("contract_status") == CONTRACT_STATUS,
             f"{label}.record.contract_status", f"必须是 {CONTRACT_STATUS}", stage)
    for key in ("next_step_allowed", "ai_suggestion_allowed"):
        _require(record.get(key) is False, f"{label}.record.{key}", "必须是严格 false", stage)
    for key in ("gate1_approval", "gate2_approval", "human_initial_judgment", "ai_suggestion",
                "final_judgment"):
        _require(record.get(key) is None, f"{label}.record.{key}", "必须是 null", stage)
    _require(isinstance(record.get("boundaries"), list) and bool(record["boundaries"]),
             f"{label}.record.boundaries", "必须是非空边界说明列表", stage)

    source = record.get("source")
    _require(isinstance(source, dict), f"{label}.record.source", "必须是对象", stage)
    _require_keys(source, ("batch_id", "fact_packet_sha256", "packet_version", "entity",
                           "workbook_sha256", "normalized_payload_sha256",
                           "screening_report_sha256", "crosscheck_report_sha256", "finding_ids"),
                  f"{label}.record.source", stage)
    _require(submission.get("batch_id") == source["batch_id"], f"{label}.record.source.batch_id",
             "记录绑定的批次必须与已保存提交对象声明的批次一致", stage)
    _require(source["batch_id"] == packet_batch_id(packet, submission),
             f"{label}.record.source.batch_id", "必须等于本次提交绑定的批次", stage)
    _require(source["fact_packet_sha256"] == canonical_sha256(packet),
             f"{label}.record.source.fact_packet_sha256",
             "必须等于本次消费事实包对象的规范指纹", stage)
    _require(source["packet_version"] == packet.get("packet_version"),
             f"{label}.record.source.packet_version", "必须等于事实包版本", stage)
    _require(canonical_json(source["entity"]) == canonical_json(_require_packet_entity(packet,
                                                                                       stage)),
             f"{label}.record.source.entity", "必须与事实包主体/期间/币种严格相等", stage)
    for key in ("workbook_sha256", "normalized_payload_sha256", "screening_report_sha256",
                "crosscheck_report_sha256"):
        _require(source[key] == packet["bindings"][key], f"{label}.record.source.{key}",
                 "必须等于事实包内对应来源指纹", stage)
    expected_ids = [item["finding_id"] for item in packet["findings"]]
    _require(source["finding_ids"] == expected_ids, f"{label}.record.source.finding_ids",
             "必须按事实包原序完整列出线索 ID", stage)

    simulated = record.get("simulated_initial_judgment")
    _require(isinstance(simulated, dict), f"{label}.record.simulated_initial_judgment",
             "必须是对象", stage)
    _require_keys(simulated, ("submission_version", "event_id", "batch_id", "fact_packet_sha256",
                              "scope", "actor_kind", "actor_id", "simulation", "occurred_at",
                              "assessment", "reason", "needed_evidence", "finding_notes"),
                  f"{label}.record.simulated_initial_judgment", stage)
    for key in ("event_id", "batch_id", "scope", "actor_kind", "actor_id", "simulation",
                "occurred_at", "assessment", "reason"):
        _require(canonical_json(simulated[key]) == canonical_json(submission.get(key)),
                 f"{label}.record.simulated_initial_judgment.{key}",
                 "必须与本次提交对象按原字符串严格一致（不得改写、不得补默认值）", stage)
    _require(simulated["fact_packet_sha256"] == source["fact_packet_sha256"],
             f"{label}.record.simulated_initial_judgment.fact_packet_sha256",
             "必须等于本次事实包规范指纹", stage)
    _require(simulated["needed_evidence"] == submission.get("needed_evidence", []),
             f"{label}.record.simulated_initial_judgment.needed_evidence",
             "必须与提交一致（省略即空列表）", stage)
    _require(canonical_json(simulated["finding_notes"]) == canonical_json(
        submission.get("finding_notes", [])),
        f"{label}.record.simulated_initial_judgment.finding_notes",
        "必须与提交一致（省略即空列表）", stage)
    return {"record": record, "record_sha256": record_sha256,
            "finding_ids": list(expected_ids)}


def packet_batch_id(packet: dict, submission: dict) -> str:
    """记录绑定的批次：以本次提交声明为准（核心已核验其与 API 批次相等）。"""
    return submission["batch_id"]


def _require_packet_entity(packet: dict, stage: str) -> dict:
    entity = packet.get("entity")
    _require(isinstance(entity, dict), "fact_packet.entity", "必须是对象", stage)
    return entity


def _verify_initial_judgment_operation(payload: dict, previous_payload: dict, state: dict,
                                       label: str, stage: str, batch_dir: Path, manifest: dict, *,
                                       previous_file_sha256: str, upstream_expected: dict,
                                       host_manifest_file_sha256: str) -> dict:
    """0008 只允许从合法 0007 的 FACT_PACKET_RECORDED 延续一次模拟初判保存。"""
    operation = payload["operation"]
    _require(operation.get("kind") == OPERATION_RECORD_SIMULATED_INITIAL_JUDGMENT,
             f"{label}.operation.kind",
             f"0008 必须是 {OPERATION_RECORD_SIMULATED_INITIAL_JUDGMENT}，"
             f"实际 {operation.get('kind')!r}", stage)
    _require_keys(operation, ("at_utc", "artifacts", "artifacts_file_sha256",
                              "initial_judgment_file_sha256", "record_sha256",
                              "started_file_sha256", "submission_file_sha256", "database_sha256",
                              "phase_after", "bindings_sha256", "initial_judgment_status",
                              "artifacts_relative", "initial_judgment_relative",
                              "started_relative", "submission_relative", "core_path", "core_sha256",
                              "core_version", "record_version", "packet_file_sha256",
                              "packet_sha256", "submission_canonical_sha256",
                              "submission_event_id", "previous_checkpoint_file_sha256"),
                  f"{label}.operation", stage)
    previous_workflow = previous_payload["workflow"]
    previous_state = previous_workflow["state"]
    _require(previous_state["phase"] == CONTROLLER_MODULE.PHASE_G2_APPROVED, f"{label}.previous.phase",
             f"0008 只能从 {CONTROLLER_MODULE.PHASE_G2_APPROVED} 的 0007 延续，实际 "
             f"{previous_state['phase']!r}", stage)
    _require(previous_payload["operation"].get("kind") == OPERATION_BUILD_FACT_PACKET,
             f"{label}.previous.operation.kind", "0008 的前序必须是 0007 的事实底稿凭证", stage)
    _require(canonical_json(payload["workflow"]) == canonical_json(previous_workflow),
             f"{label}.workflow",
             "0008 的完整 workflow 必须与 0007 严格相等（不追加控制器 history、决定、请求或新 phase）",
             stage)
    decisions = state["simulated_decisions"]
    _require(isinstance(decisions, list) and len(decisions) == 2,
             f"{label}.state.simulated_decisions", "模拟决定必须恰为 Gate1 与 Gate2 两条", stage)
    _require(operation["phase_after"] == state["phase"], f"{label}.operation.phase_after",
             "操作摘要的 phase 必须与实际状态一致", stage)
    _require(operation["bindings_sha256"] == state["run_bindings_sha256"],
             f"{label}.operation.bindings_sha256", "必须与 workflow 绑定一致", stage)
    _require(operation["initial_judgment_status"] == INITIAL_JUDGMENT_STATUS_RECORDED,
             f"{label}.operation.initial_judgment_status",
             f"必须是 {INITIAL_JUDGMENT_STATUS_RECORDED}，"
             f"实际 {operation['initial_judgment_status']!r}", stage)
    _require(state["batch_id"] == payload["batch_id"], f"{label}.workflow.state.batch_id",
             "workflow 批次必须与 checkpoint 一致", stage)
    _require(operation["previous_checkpoint_file_sha256"] == previous_file_sha256,
             f"{label}.operation.previous_checkpoint_file_sha256",
             "必须等于 0007 的初始实读字节哈希", stage)

    # 0007 的事实底稿材料核验保留到 0008 恢复：不跳过底稿产物、Gate2、筛查、复算与数据库
    _require(isinstance(upstream_expected, dict) and bool(upstream_expected),
             f"{label}.upstream_expected",
             "0008 恢复必须带出 0007 的初次核验读数（不得跳过上游产物与数据库核验）", stage)
    screen = _read_screen_outputs(batch_dir, stage)
    crosscheck = _read_crosscheck_outputs(batch_dir, stage)
    gate2_outputs = _read_gate2_outputs(batch_dir, stage)
    gate2_paths = _gate2_paths(batch_dir, stage)
    actual_database_sha = file_sha256(gate2_paths["database_path"])
    for key, value, field in (
        ("screening_started_file_sha256", screen["started_file_sha256"],
         f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}"),
        ("screening_report_file_sha256", screen["report_file_sha256"],
         f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}"),
        ("screening_artifacts_file_sha256", screen["artifacts_file_sha256"],
         f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}"),
        ("crosscheck_started_file_sha256", crosscheck["started_file_sha256"],
         f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_START}"),
        ("crosscheck_report_file_sha256", crosscheck["report_file_sha256"],
         f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}"),
        ("crosscheck_artifacts_file_sha256", crosscheck["artifacts_file_sha256"],
         f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}"),
        ("gate2_normalized_file_sha256", gate2_outputs["normalized_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}"),
        ("gate2_load_report_file_sha256", gate2_outputs["load_report_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}"),
        ("gate2_artifacts_file_sha256", gate2_outputs["artifacts_file_sha256"],
         f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"),
        ("database_sha256", actual_database_sha, str(gate2_paths["database_path"])),
    ):
        _require(upstream_expected.get(key) == value, field,
                 f"上游材料在模拟初判恢复时发生了变化：期望 {upstream_expected.get(key)!r}，"
                 f"实际 {value!r}", stage)
    _verify_fact_packet_tail(batch_dir, upstream_expected, stage)
    _require(file_sha256(_checkpoint_path(batch_dir, 7)) == previous_file_sha256,
             f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0007.json",
             "0007 字节在本次恢复时发生变化（不覆盖、不改签）", stage)
    fact_outputs = _read_fact_packet_outputs(batch_dir, stage)
    packet = fact_outputs["packet"]

    paths = _initial_judgment_paths(batch_dir)
    actual = _read_initial_judgment_outputs(batch_dir, stage)
    started = actual["started"]
    started_label = f"{paths['relative']}/{INITIAL_JUDGMENT_START}"
    _require_keys(started, INITIAL_JUDGMENT_START_REQUIRED_KEYS, started_label, stage)
    _require(started["start_version"] == INITIAL_JUDGMENT_START_VERSION,
             f"{started_label}.start_version",
             f"必须是 {INITIAL_JUDGMENT_START_VERSION}，实际 {started['start_version']!r}", stage)
    _require(started["batch_id"] == batch_dir.name, f"{started_label}.batch_id",
             "必须与批次目录叶子一致", stage)
    _require(started["host_version"] == HOST_VERSION, f"{started_label}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}，实际 {started['host_version']!r}", stage)
    _require(started["operation_kind"] == OPERATION_RECORD_SIMULATED_INITIAL_JUDGMENT,
             f"{started_label}.operation_kind",
             f"必须是 {OPERATION_RECORD_SIMULATED_INITIAL_JUDGMENT}", stage)
    _require(started["source_checkpoint_file_sha256"] == previous_file_sha256,
             f"{started_label}.source_checkpoint_file_sha256",
             "必须等于 0007 的初始实读字节哈希", stage)
    _require(started["host_manifest_file_sha256"] == host_manifest_file_sha256,
             f"{started_label}.host_manifest_file_sha256",
             "必须等于初始实读宿主清单文件字节哈希", stage)
    _require(started["run_bindings_sha256"] == state["run_bindings_sha256"],
             f"{started_label}.run_bindings_sha256", "必须等于 workflow 创建绑定指纹", stage)
    _require(started["core_path"] == str(INITIAL_JUDGMENT_CORE_PATH), f"{started_label}.core_path",
             "必须是冻结初判核心固定路径", stage)
    _require(started["core_sha256"]
             == manifest["bindings"]["host_code_sha256"]["initial_judgment_core"],
             f"{started_label}.core_sha256", "必须等于冻结初判核心实际字节哈希（宿主扩展绑定）",
             stage)
    _require(started["core_version"] == INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
             f"{started_label}.core_version", f"必须是 {INITIAL_JUDGMENT_MODULE.RECORD_VERSION}",
             stage)
    _require(started["packet_file_sha256"] == fact_outputs["packet_file_sha256"],
             f"{started_label}.packet_file_sha256", "必须等于本次实读事实包文件字节哈希", stage)
    _require(started["packet_sha256"] == canonical_sha256(packet), f"{started_label}.packet_sha256",
             "必须等于本次实读事实包对象的规范指纹", stage)
    _require(started["submission_file_sha256"] == actual["submission_file_sha256"],
             f"{started_label}.submission_file_sha256", "必须等于 submission 快照文件字节哈希",
             stage)
    _require(started["submission_canonical_sha256"]
             == canonical_sha256(actual["submission"]),
             f"{started_label}.submission_canonical_sha256",
             "必须等于本次消费提交对象的规范指纹", stage)
    _require(started["submission_event_id"] == actual["submission"].get("event_id"),
             f"{started_label}.submission_event_id", "必须等于提交事件 ID", stage)
    _require(started["actor_kind"] == INITIAL_JUDGMENT_MODULE.ACTOR_KIND,
             f"{started_label}.actor_kind", f"必须是 {INITIAL_JUDGMENT_MODULE.ACTOR_KIND}", stage)
    _require(started["simulation"] == INITIAL_JUDGMENT_MODULE.SIMULATION,
             f"{started_label}.simulation", f"必须是 {INITIAL_JUDGMENT_MODULE.SIMULATION}", stage)
    _require(started["database_path"] == str(gate2_paths["database_path"]),
             f"{started_label}.database_path", "必须是宿主推导的固定数据库路径", stage)
    _require(started["database_sha256"] == actual_database_sha, f"{started_label}.database_sha256",
             "必须等于数据库实际字节哈希", stage)

    artifacts = actual["artifacts"]
    artifacts_label = f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}"
    _require_keys(artifacts, INITIAL_JUDGMENT_ARTIFACTS_REQUIRED_KEYS, artifacts_label, stage)
    _require(artifacts["artifacts_version"] == INITIAL_JUDGMENT_ARTIFACTS_VERSION,
             f"{artifacts_label}.artifacts_version",
             f"必须是 {INITIAL_JUDGMENT_ARTIFACTS_VERSION}，"
             f"实际 {artifacts['artifacts_version']!r}", stage)
    _require(artifacts["batch_id"] == batch_dir.name, f"{artifacts_label}.batch_id",
             "必须与批次目录叶子一致", stage)
    _require(artifacts["host_version"] == HOST_VERSION, f"{artifacts_label}.host_version",
             f"必须等于当前实现版本 {HOST_VERSION!r}", stage)
    _require(artifacts["operation_kind"] == OPERATION_RECORD_SIMULATED_INITIAL_JUDGMENT,
             f"{artifacts_label}.operation_kind",
             f"必须是 {OPERATION_RECORD_SIMULATED_INITIAL_JUDGMENT}", stage)
    _require(artifacts["core_path"] == str(INITIAL_JUDGMENT_CORE_PATH),
             f"{artifacts_label}.core_path", "必须是冻结初判核心固定路径", stage)
    _require(artifacts["core_sha256"]
             == manifest["bindings"]["host_code_sha256"]["initial_judgment_core"],
             f"{artifacts_label}.core_sha256", "必须等于冻结初判核心实际字节哈希", stage)
    _require(artifacts["core_version"] == INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
             f"{artifacts_label}.core_version",
             f"必须是 {INITIAL_JUDGMENT_MODULE.RECORD_VERSION}", stage)
    _require(artifacts["record_version"] == INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
             f"{artifacts_label}.record_version",
             f"必须是 {INITIAL_JUDGMENT_MODULE.RECORD_VERSION}", stage)
    _require(artifacts["initial_judgment_status"] == INITIAL_JUDGMENT_STATUS_RECORDED,
             f"{artifacts_label}.initial_judgment_status",
             f"必须是 {INITIAL_JUDGMENT_STATUS_RECORDED}", stage)
    _require(artifacts["run_bindings_sha256"] == state["run_bindings_sha256"],
             f"{artifacts_label}.run_bindings_sha256", "必须等于 workflow 创建绑定指纹", stage)
    _require(artifacts["host_manifest_file_sha256"] == host_manifest_file_sha256,
             f"{artifacts_label}.host_manifest_file_sha256",
             "必须等于初始实读宿主清单文件字节哈希", stage)
    _require(artifacts["previous_checkpoint_file_sha256"] == previous_file_sha256,
             f"{artifacts_label}.previous_checkpoint_file_sha256",
             "必须等于 0007 的初始实读字节哈希", stage)
    _require(artifacts["previous_checkpoint_relative"]
             == f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0007.json",
             f"{artifacts_label}.previous_checkpoint_relative", "必须是固定相对路径", stage)
    _require(artifacts["database_path"] == str(gate2_paths["database_path"]),
             f"{artifacts_label}.database_path", "必须是宿主推导的固定数据库路径", stage)
    _require(artifacts["database_sha256"] == actual_database_sha,
             f"{artifacts_label}.database_sha256", "必须等于数据库实际字节哈希", stage)
    for key, relative, artifacts_field, actual_field in (
        ("started_relative", f"{paths['relative']}/{INITIAL_JUDGMENT_START}",
         "started_file_sha256", "started_file_sha256"),
        ("submission_relative", f"{paths['relative']}/{INITIAL_JUDGMENT_SUBMISSION}",
         "submission_file_sha256", "submission_file_sha256"),
        ("initial_judgment_relative", f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}",
         "initial_judgment_file_sha256", "record_file_sha256"),
        # artifacts 自身不内嵌自哈希（文件字节哈希记在 0008.operation），只核验固定相对路径
        ("artifacts_relative", f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}", None, None),
    ):
        _require(artifacts[key] == relative, f"{artifacts_label}.{key}", "必须是固定相对路径",
                 stage)
        if artifacts_field is not None:
            _require(artifacts[artifacts_field] == actual[actual_field],
                     f"{artifacts_label}.{artifacts_field}",
                     "必须等于对应文件实际字节哈希", stage)
    _require(artifacts["packet_file_sha256"] == fact_outputs["packet_file_sha256"],
             f"{artifacts_label}.packet_file_sha256", "必须等于事实包文件字节哈希", stage)
    _require(artifacts["packet_sha256"] == canonical_sha256(packet),
             f"{artifacts_label}.packet_sha256", "必须等于事实包对象规范指纹", stage)
    _require(artifacts["submission_file_sha256"] == actual["submission_file_sha256"],
             f"{artifacts_label}.submission_file_sha256", "必须等于 submission 快照文件字节哈希",
             stage)
    _require(artifacts["submission_canonical_sha256"] == canonical_sha256(actual["submission"]),
             f"{artifacts_label}.submission_canonical_sha256",
             "必须等于本次消费提交对象的规范指纹", stage)
    _require(artifacts["submission_event_id"] == actual["submission"].get("event_id"),
             f"{artifacts_label}.submission_event_id", "必须等于提交事件 ID", stage)
    _require(artifacts["actor_kind"] == INITIAL_JUDGMENT_MODULE.ACTOR_KIND,
             f"{artifacts_label}.actor_kind", "必须是模拟身份", stage)
    _require(artifacts["simulation"] == INITIAL_JUDGMENT_MODULE.SIMULATION,
             f"{artifacts_label}.simulation", "必须是显式模拟标记", stage)
    for key in ("next_step_allowed", "ai_suggestion_allowed"):
        _require(artifacts[key] is False, f"{artifacts_label}.{key}", "必须是严格 false", stage)
    _require(artifacts["ai_action_simulation_allowed"] is False,
             f"{artifacts_label}.ai_action_simulation_allowed",
             "AI 动作的真实许可必须严格 false（AI 未开放）", stage)
    for key in ("gate1_approval", "gate2_approval", "human_initial_judgment", "ai_suggestion",
                "final_judgment"):
        _require(artifacts[key] is None, f"{artifacts_label}.{key}", "必须是 null", stage)

    report = _initial_judgment_record_report(actual["record_payload"], packet,
                                             actual["submission"], stage,
                                             f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}")
    _require(artifacts["record_sha256"] == report["record_sha256"],
             f"{artifacts_label}.record_sha256", "必须等于核心返回的 record_sha256", stage)
    _require(artifacts["findings_total"] == len(report["finding_ids"]),
             f"{artifacts_label}.findings_total", "必须等于事实包线索条数", stage)

    _require(operation["artifacts_file_sha256"] == actual["artifacts_file_sha256"],
             f"{label}.operation.artifacts_file_sha256", "必须等于 artifacts 文件实际字节哈希",
             stage)
    _require(operation["initial_judgment_file_sha256"] == actual["record_file_sha256"],
             f"{label}.operation.initial_judgment_file_sha256",
             "必须等于 initial_judgment 文件实际字节哈希", stage)
    _require(operation["started_file_sha256"] == actual["started_file_sha256"],
             f"{label}.operation.started_file_sha256", "必须等于 started 文件实际字节哈希", stage)
    _require(operation["submission_file_sha256"] == actual["submission_file_sha256"],
             f"{label}.operation.submission_file_sha256", "必须等于 submission 文件实际字节哈希",
             stage)
    _require(operation["submission_canonical_sha256"] == canonical_sha256(actual["submission"]),
             f"{label}.operation.submission_canonical_sha256",
             "必须等于本次消费提交对象的规范指纹", stage)
    _require(operation["record_sha256"] == report["record_sha256"],
             f"{label}.operation.record_sha256", "必须等于核心返回的 record_sha256", stage)
    _require(operation["record_version"] == INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
             f"{label}.operation.record_version",
             f"必须是 {INITIAL_JUDGMENT_MODULE.RECORD_VERSION}", stage)
    _require(operation["packet_file_sha256"] == fact_outputs["packet_file_sha256"],
             f"{label}.operation.packet_file_sha256", "必须等于事实包文件字节哈希", stage)
    _require(operation["packet_sha256"] == canonical_sha256(packet),
             f"{label}.operation.packet_sha256", "必须等于事实包对象规范指纹", stage)
    _require(operation["database_sha256"] == actual_database_sha,
             f"{label}.operation.database_sha256", "必须等于数据库实际字节哈希", stage)
    for key, relative in (("artifacts_relative", f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}"),
                          ("initial_judgment_relative",
                           f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}"),
                          ("started_relative", f"{paths['relative']}/{INITIAL_JUDGMENT_START}"),
                          ("submission_relative",
                           f"{paths['relative']}/{INITIAL_JUDGMENT_SUBMISSION}")):
        _require(operation[key] == relative, f"{label}.operation.{key}", "必须是固定相对路径",
                 stage)
    _require(operation["core_path"] == str(INITIAL_JUDGMENT_CORE_PATH),
             f"{label}.operation.core_path", "必须是冻结初判核心固定路径", stage)
    _require(operation["core_sha256"]
             == manifest["bindings"]["host_code_sha256"]["initial_judgment_core"],
             f"{label}.operation.core_sha256", "必须等于冻结初判核心实际字节哈希", stage)
    _require(operation["core_version"] == INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
             f"{label}.operation.core_version",
             f"必须是 {INITIAL_JUDGMENT_MODULE.RECORD_VERSION}", stage)
    embedded = operation["artifacts"]
    _require(isinstance(embedded, dict), f"{label}.operation.artifacts",
             f"必须是对象（内嵌 artifacts 完整副本），实际 {type(embedded).__name__}", stage)
    _require_keys(embedded, INITIAL_JUDGMENT_ARTIFACTS_REQUIRED_KEYS, f"{label}.operation.artifacts",
                  stage)
    _require(canonical_json(embedded) == canonical_json(artifacts), f"{label}.operation.artifacts",
             "内嵌 artifacts 副本必须与磁盘实际 artifacts 对象完整严格相等", stage)
    return {
        "started_file_sha256": actual["started_file_sha256"],
        "submission_file_sha256": actual["submission_file_sha256"],
        "submission_canonical_sha256": canonical_sha256(actual["submission"]),
        "record_file_sha256": actual["record_file_sha256"],
        "artifacts_file_sha256": actual["artifacts_file_sha256"],
        "record_sha256": report["record_sha256"],
        "packet_file_sha256": fact_outputs["packet_file_sha256"],
        "packet_sha256": canonical_sha256(packet),
        "database_path": str(gate2_paths["database_path"]),
        "database_sha256": actual_database_sha,
        "initial_judgment_summary": {
            "started_path": operation["started_relative"],
            "started_file_sha256": actual["started_file_sha256"],
            "submission_path": operation["submission_relative"],
            "submission_file_sha256": actual["submission_file_sha256"],
            "initial_judgment_path": operation["initial_judgment_relative"],
            "initial_judgment_file_sha256": actual["record_file_sha256"],
            "artifacts_path": operation["artifacts_relative"],
            "artifacts_file_sha256": actual["artifacts_file_sha256"],
            "record_sha256": report["record_sha256"],
            "record_version": INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
            "submission_event_id": actual["submission"].get("event_id"),
            "actor_kind": actual["submission"].get("actor_kind"),
            "simulation": actual["submission"].get("simulation"),
            "findings_total": len(report["finding_ids"]),
            "ai_action_simulation_allowed": artifacts["ai_action_simulation_allowed"],
        },
    }


def _raise_incomplete_gate2(batch_dir: Path, chain: dict) -> None:
    """workflow/gate2/ 已开始但没有完整有效的 0003：说明准备未完成／失败并拒绝继续。"""
    revision = chain["current"]["revision"]
    failure_path = _gate2_dir(batch_dir) / GATE2_FAILURE
    if failure_path.is_file():
        failure = _read_json(failure_path, f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_FAILURE}", "status")
        reasons = [str(item) for item in failure.get("reasons") or []]
        message = (f"该批次的 {WORKFLOW_DIR}/{GATE2_DIR}/ 已开始但未形成完整有效的 0003"
                   f"（当前为第 {revision} 份 checkpoint）：准备未完成／失败。"
                   f"stage={failure.get('stage')!r}；异常类别={failure.get('exception_class')!r}；"
                   f"原因={reasons!r}。不重试、不复用、不自动删除，需继续时新建批次。")
        if failure.get("exception_class") in ("WorkflowHostError", "NormalizationError",
                                             "SqliteLoadError", "OSError"):
            raise WorkflowHostError(message, reasons=reasons, stage="status")
        raise WorkflowHostBlocked(message, reasons=reasons, stage="status")
    raise WorkflowHostBlocked(
        f"该批次的 {WORKFLOW_DIR}/{GATE2_DIR}/ 已开始但没有完整有效的 0003，也没有可读的失败诊断"
        f"（当前为第 {revision} 份 checkpoint）：现场不完整，按协议阻断，不猜测成功、不退回旧状态。",
        stage="status")


def inspect_dev_batch(batch_dir) -> dict:
    """读取宿主清单、完整 checkpoint 链并实测绑定，交给冻结控制器验证后输出实际 phase。"""
    try:
        target = _resolve_batch_dir(batch_dir, must_exist=True, stage="status")
        context = _load_host_context(target, stage="status")
        measured = context["measured_bindings"]
        chain = context["chain"]
        current = chain["current"]["payload"]["workflow"]
        gate2_started = _gate2_dir(target).exists()
        if gate2_started and chain["current"]["revision"] < 3:
            _raise_incomplete_gate2(target, chain)
        gate2_expected = None
        if chain["current"]["revision"] >= 3:
            # 初次材料核验（发生在冻结 prepare_dev_gate 纯重放之前）带出的期望值
            gate2_expected = dict(chain["gate2_expected"] or {})
            _require(bool(gate2_expected), "chain.gate2_expected",
                     "0003 恢复必须带出初次材料核验读数", "status")
            gate2_expected["checkpoints"] = {item["revision"]: item["file_sha256"]
                                             for item in chain["checkpoints"]}
        action_name = ("SCREEN_AND_BUILD_FACTS" if chain["current"]["revision"] >= 3
                       else "NORMALIZE_AND_LOAD")
        try:
            action = CONTROLLER_MODULE.check_dev_action(current, action_name, current_bindings=measured)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"实测绑定或 workflow 未被冻结控制器接受：{exc}", stage="status") from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"冻结控制器意外错误：{exc}", stage="status") from exc
        # 读取结束后再核验一次所消费的不可变文件（避免混合读取不同现场）
        measured_after = _measure_bindings(target)
        _require(canonical_json(measured_after) == canonical_json(measured), "bindings",
                 "读取期间所消费的不可变文件发生变化（拒绝返回混合现场）", "status")
        _require(file_sha256(_host_manifest_path(target)) == context["manifest_file_sha256"],
                 f"{WORKFLOW_DIR}/{HOST_MANIFEST_NAME}", "读取期间宿主清单发生变化", "status")
        _require(file_sha256(_checkpoint_path(target, chain["current"]["revision"]))
                 == chain["current_file_sha256"], "checkpoint", "读取期间 checkpoint 发生变化", "status")
        other_actions = {}
        for name in ("NORMALIZE_AND_LOAD", "SCREEN_AND_BUILD_FACTS"):
            try:
                other_actions[name] = CONTROLLER_MODULE.check_dev_action(
                    current, name, current_bindings=measured)["simulation_allowed"]
            except (CONTROLLER_MODULE.WorkflowBlocked, CONTROLLER_MODULE.WorkflowError):
                other_actions[name] = False
        gate2_tail_actual = None
        if gate2_expected is not None:
            # 最后一次控制器调用之后、返回成功之前：复测本次消费的全部产物
            gate2_tail_actual = _verify_gate2_tail(target, gate2_expected, "status")
        screen_tail_actual = None
        screen_summary = None
        # F01：筛查专属收尾只在合法筛查状态执行；变量必须在分支外初始化，
        # 否则 0001—0004 各合法阶段恢复会因 UnboundLocalError 退化为运行错误。
        screen_expected = None
        if chain["current"]["revision"] >= 5:
            # 关键：筛查摘要（started/report/artifacts/报告指纹）必须始终取 0005 自身的操作摘要，
            # 不能因为链尾是 0006 就去读 0006 的 operation（0006 只描述复算）。
            operation = None
            for item in chain["checkpoints"]:
                if item["revision"] == 5:
                    operation = item["payload"]["operation"]
            _require(operation is not None, f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0005.json",
                     "链中必须存在 0005", "status")
            screen_expected = {
                "started_file_sha256": operation["started_file_sha256"],
                "report_file_sha256": operation["report_file_sha256"],
                "artifacts_file_sha256": operation["artifacts_file_sha256"],
                "database_path": operation["artifacts"]["database_path"],
                "database_sha256": operation["database_sha256"],
            }
            screen_tail_actual = _verify_screen_tail(target, screen_expected, "status")
            screen_outputs = _read_screen_outputs(target, "status")
            # 本次摘要所消费的读数必须与 0005 初始声明逐项一致（不得用事后新读数替换预期值）
            for key, label_txt in (
                ("report_file_sha256", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}"),
                ("started_file_sha256", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}"),
                ("artifacts_file_sha256", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}"),
            ):
                _require(screen_outputs[key] == screen_expected[key], label_txt,
                         f"本次 status 摘要所消费的文件字节与 0005 初始声明不一致："
                         f"期望 {screen_expected[key]!r}，实际 {screen_outputs[key]!r}", "status")
            report_now = screen_outputs["report"]
            _require(isinstance(report_now.get("findings"), list),
                     f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}.findings",
                     "报告 findings 必须是列表（形状先检后用）", "status")
            _require(canonical_sha256(report_now) == operation["report_canonical_sha256"],
                     f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}",
                     "本次 status 摘要所消费的报告对象规范指纹必须等于 0005 初始声明："
                     f"期望 {operation['report_canonical_sha256']!r}，"
                     f"实际 {canonical_sha256(report_now)!r}", "status")
            artifacts_now = screen_outputs["artifacts"]
            _require(canonical_json(artifacts_now) == canonical_json(operation["artifacts"]),
                     f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}",
                     "本次 status 摘要所消费的 artifacts 必须与 0005 内嵌副本完整严格相等", "status")
            screen_summary = {
                "report_path": operation["report_relative"],
                "report_file_sha256": screen_expected["report_file_sha256"],
                "report_canonical_sha256": operation["report_canonical_sha256"],
                "artifacts_path": operation["artifacts_relative"],
                "artifacts_file_sha256": screen_expected["artifacts_file_sha256"],
                "started_file_sha256": screen_expected["started_file_sha256"],
                "database_path": artifacts_now["database_path"],
                "database_sha256": screen_expected["database_sha256"],
                "cutoff_date": artifacts_now["cutoff_date"],
                "rule_core_version": artifacts_now["rule_core_version"],
                "findings_total": len(report_now["findings"]),
                "findings_by_rule": {
                    rule_id: sum(1 for item in report_now["findings"]
                                 if isinstance(item, dict) and item.get("rule_id") == rule_id)
                    for rule_id in SCREEN_MODULE.RULE_IDS},
            }
            checkpoint5_want = next(item["file_sha256"] for item in chain["checkpoints"]
                                    if item["revision"] == 5)
            _require(file_sha256(_checkpoint_path(target, 5)) == checkpoint5_want,
                     f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0005.json",
                     "收尾复测发现 0005 字节在本次读取之后发生变化："
                     f"期望（初始读取）{checkpoint5_want!r}，"
                     f"实际 {file_sha256(_checkpoint_path(target, 5))!r}", "status")
        # F02：最后一次动作检查（含 other_actions 循环）之后，从磁盘重新实测静态绑定
        bindings_final = _recheck_static_bindings(
            target, measured, "status", when="Gate2 恢复收尾（最后一次动作检查之后）")
        crosscheck_summary = None
        crosscheck_expected = None
        if chain["current"]["revision"] >= 5:
            # 0005／0006 都要按 0005 自己的初始字节哈希核验筛查收尾（不误用链尾 0006 的哈希）
            operation5 = None
            for item in chain["checkpoints"]:
                if item["revision"] == 5:
                    operation5 = item["payload"]["operation"]
                    checkpoint5_file_sha256 = item["file_sha256"]
            _require(operation5 is not None, f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0005.json",
                     "链中必须存在 0005", "status")
            # 最后一次控制器调用与最后一次数据消费之后，复测筛查产物、数据库与 0005 字节
            _verify_screen_tail(target, screen_expected, "status")
            _require(file_sha256(_checkpoint_path(target, 5)) == checkpoint5_file_sha256,
                     f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0005.json",
                     "最终复测发现 0005 字节发生变化："
                     f"期望（初始读取）{checkpoint5_file_sha256!r}，"
                     f"实际 {file_sha256(_checkpoint_path(target, 5))!r}", "status")
        if chain["current"]["revision"] >= 6:
            operation6 = None
            for item in chain["checkpoints"]:
                if item["revision"] == 6:
                    operation6 = item["payload"]["operation"]
            _require(operation6 is not None, f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0006.json",
                     "链中必须存在 0006", "status")
            # 复算产物的收尾预期必须取 0006 自己的操作摘要（0005 的 started/report/artifacts
            # 是筛查产物，两者同名但完全不同）
            crosscheck_expected = {
                "started_file_sha256": operation6["started_file_sha256"],
                "report_file_sha256": operation6["report_file_sha256"],
                "artifacts_file_sha256": operation6["artifacts_file_sha256"],
                "database_path": operation6["artifacts"]["database_path"],
                "database_sha256": operation6["artifacts"]["database_sha256"],
            }
            crosscheck_tail_actual = _verify_crosscheck_tail(target, crosscheck_expected, "status")
            crosscheck_outputs = _read_crosscheck_outputs(target, "status")
            for key, label_txt in (
                ("report_file_sha256", f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}"),
                ("started_file_sha256", f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_START}"),
                ("artifacts_file_sha256", f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}"),
            ):
                _require(crosscheck_outputs[key] == crosscheck_expected[key], label_txt,
                         f"本次 status 摘要所消费的文件字节与 0006 初始声明不一致："
                         f"期望 {crosscheck_expected[key]!r}，实际 {crosscheck_outputs[key]!r}",
                         "status")
            report_now = crosscheck_outputs["report"]
            _require(canonical_sha256(report_now) == operation6["report_canonical_sha256"],
                     f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}",
                     "本次 status 摘要所消费的报告对象规范指纹必须等于 0006 初始声明", "status")
            artifacts_now = crosscheck_outputs["artifacts"]
            _require(canonical_json(artifacts_now) == canonical_json(operation6["artifacts"]),
                     f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}",
                     "本次 status 摘要所消费的 artifacts 必须与 0006 内嵌副本完整严格相等", "status")
            crosscheck_summary = {
                "report_path": operation6["report_relative"],
                "report_file_sha256": crosscheck_expected["report_file_sha256"],
                "report_canonical_sha256": operation6["report_canonical_sha256"],
                "artifacts_path": operation6["artifacts_relative"],
                "artifacts_file_sha256": crosscheck_expected["artifacts_file_sha256"],
                "started_file_sha256": crosscheck_expected["started_file_sha256"],
                "core_path": operation6["core_path"],
                "core_version": operation6["core_version"],
                "matched": artifacts_now["matched"],
                "difference_count": report_now["comparison"]["difference_count"],
                "unmatched_dimensions": report_now["comparison"]["unmatched_dimensions"],
                "dimensions": report_now["comparison"]["dimensions"],
                "rule_recomputed_counts": report_now["rule_recomputed_counts"],
                "report_relative": operation6["report_relative"],
                "artifacts_relative": operation6["artifacts_relative"],
                "started_relative": operation6["started_relative"],
            }
        if gate2_expected is not None:
            # F02：最后一次控制器调用与最后一次数据消费之后，继续覆盖本次已消费的 Gate2 材料、
            # 宿主清单与 0001—0005 全部 checkpoint（预期值只来自初始同缓冲读取或本次 writer 结果）
            _verify_gate2_tail(target, gate2_expected, "status")
            for revision, want in sorted(gate2_expected["checkpoints"].items()):
                got = file_sha256(_checkpoint_path(target, revision))
                _require(got == want, f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{revision:04d}.json",
                         f"最终复测发现 checkpoint 字节在本次数据消费之后发生变化："
                         f"期望（初始读取）{want!r}，实际 {got!r}", "status")
            _require(file_sha256(_host_manifest_path(target)) == context["manifest_file_sha256"],
                     f"{WORKFLOW_DIR}/{HOST_MANIFEST_NAME}",
                     "最终复测发现宿主清单字节在本次数据消费之后发生变化："
                     f"期望（初始读取）{context['manifest_file_sha256']!r}，"
                     f"实际 {file_sha256(_host_manifest_path(target))!r}", "status")
        fact_packet_summary = None
        fact_packet_expected = None
        if chain["current"]["revision"] >= 7:
            operation7 = None
            for item in chain["checkpoints"]:
                if item["revision"] == 7:
                    operation7 = item["payload"]["operation"]
            _require(operation7 is not None, f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0007.json",
                     "链中必须存在 0007", "status")
            fact_packet_expected = {
                "started_file_sha256": operation7["started_file_sha256"],
                "packet_file_sha256": operation7["packet_file_sha256"],
                "markdown_file_sha256": operation7["markdown_file_sha256"],
                "artifacts_file_sha256": operation7["artifacts_file_sha256"],
                "database_path": operation7["artifacts"]["database_path"],
                "database_sha256": operation7["artifacts"]["database_sha256"],
            }
            paths_fp = _fact_packet_paths(target)
            fact_tail_actual = _verify_fact_packet_tail(target, fact_packet_expected, "status")
            fact_outputs = _read_fact_packet_outputs(target, "status")
            packet_now = fact_outputs["packet"]
            artifacts_now = fact_outputs["artifacts"]
            _require(canonical_json(artifacts_now) == canonical_json(operation7["artifacts"]),
                     f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_ARTIFACTS}",
                     "本次 status 摘要所消费的 artifacts 必须与 0007 内嵌副本完整严格相等", "status")
            _require(canonical_sha256(packet_now) == operation7["packet_sha256"],
                     f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_JSON}",
                     "本次 status 摘要所消费的 packet 规范指纹必须等于 0007 声明", "status")
            _require(fact_outputs["packet_file_sha256"] == fact_packet_expected["packet_file_sha256"],
                     f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_JSON}",
                     "packet 文件字节哈希必须与 0007 声明一致", "status")
            _require(fact_outputs["markdown_file_sha256"]
                     == fact_packet_expected["markdown_file_sha256"],
                     f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_MARKDOWN}",
                     "Markdown 文件字节哈希必须与 0007 声明一致", "status")
            protocol_now = _packet_protocol_report(packet_now, {
                "normalized_payload_sha256": artifacts_now["normalized_payload_sha256"],
                "screening_report_canonical_sha256": artifacts_now[
                    "screening_report_canonical_sha256"],
                "crosscheck_report_canonical_sha256": artifacts_now[
                    "crosscheck_report_canonical_sha256"],
                "workbook_sha256": packet_now["bindings"]["workbook_sha256"],
            }, "status", f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_JSON}")
            fact_packet_summary = {
                "packet_path": operation7["packet_relative"],
                "packet_file_sha256": fact_packet_expected["packet_file_sha256"],
                "packet_sha256": operation7["packet_sha256"],
                "markdown_path": operation7["markdown_relative"],
                "markdown_file_sha256": fact_packet_expected["markdown_file_sha256"],
                "markdown_bytes": len(fact_outputs["markdown_bytes"]),
                "artifacts_path": operation7["artifacts_relative"],
                "artifacts_file_sha256": fact_packet_expected["artifacts_file_sha256"],
                "started_path": operation7["started_relative"],
                "started_file_sha256": fact_packet_expected["started_file_sha256"],
                "core_path": operation7["core_path"],
                "core_version": operation7["core_version"],
                "packet_version": packet_now["packet_version"],
                "findings_total": protocol_now["total_findings"],
                "rule_counts": protocol_now["rule_counts"],
                "r02_overpayment_total_cents": protocol_now["r02_overpayment_total_cents"],
                "fact_packet_tail_verified": sorted(fact_tail_actual.keys()),
            }
            entry7 = next(item for item in chain["checkpoints"] if item["revision"] == 7)
            _require(file_sha256(_checkpoint_path(target, 7)) == entry7["file_sha256"],
                     f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0007.json",
                     "最终复测发现 0007 字节发生变化："
                     f"期望（初始读取）{entry7['file_sha256']!r}，"
                     f"实际 {file_sha256(_checkpoint_path(target, 7))!r}", "status")
        initial_judgment_summary = None
        initial_judgment_expected = None
        if chain["current"]["revision"] >= 8:
            operation8 = None
            for item in chain["checkpoints"]:
                if item["revision"] == 8:
                    operation8 = item["payload"]["operation"]
            _require(operation8 is not None, f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0008.json",
                     "链中必须存在 0008", "status")
            expected8 = chain.get("initial_judgment_expected") or {}
            _require(bool(expected8), "chain.initial_judgment_expected",
                     "0008 恢复必须带出本次核验读数", "status")
            initial_judgment_expected = {
                "started_file_sha256": expected8["started_file_sha256"],
                "submission_file_sha256": expected8["submission_file_sha256"],
                "submission_canonical_sha256": expected8["submission_canonical_sha256"],
                "record_file_sha256": expected8["record_file_sha256"],
                "record_sha256": expected8["record_sha256"],
                "artifacts_file_sha256": expected8["artifacts_file_sha256"],
                "database_path": expected8["database_path"],
                "database_sha256": expected8["database_sha256"],
            }
            _verify_initial_judgment_tail(target, initial_judgment_expected, "status")
            initial_judgment_summary = dict(expected8["initial_judgment_summary"])
            initial_judgment_summary["tail_verified"] = sorted(initial_judgment_expected.keys())
            entry8 = next(item for item in chain["checkpoints"] if item["revision"] == 8)
            _require(file_sha256(_checkpoint_path(target, 8)) == entry8["file_sha256"],
                     f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0008.json",
                     "最终复测发现 0008 字节发生变化："
                     f"期望（初始读取）{entry8['file_sha256']!r}，"
                     f"实际 {file_sha256(_checkpoint_path(target, 8))!r}", "status")
        completed_actions = []
        revision_now = chain["current"]["revision"]
        if revision_now >= 2:
            completed_actions.append("GATE1_SIMULATED_DECISION")
        if revision_now >= 3:
            completed_actions.append("NORMALIZE_AND_LOAD")
        if revision_now >= 4:
            completed_actions.append("GATE2_SIMULATED_DECISION")
        if revision_now >= 5:
            completed_actions.append("RULE_SCREEN")
        if revision_now >= 6:
            completed_actions.append("RULE_CROSSCHECK")
        if revision_now >= 7:
            completed_actions.append("FACT_PACKET")
        if revision_now >= 8:
            completed_actions.append("SIMULATED_INITIAL_JUDGMENT")
        gate2_decision_summary = None
        if revision_now >= 4:
            last_decision = current["state"]["simulated_decisions"][-1]
            gate2_decision_summary = {
                "event_id": last_decision.get("event_id"),
                "decision": last_decision.get("decision"),
                "actor_kind": last_decision.get("actor_kind"),
                "simulation": last_decision.get("simulation"),
                "decision_sha256": last_decision.get("decision_sha256"),
            }
        # ---------------------------------------------------------------- B1 收尾
        # 真正最后一次复算输出读取（摘要、报告指纹、内嵌 artifacts 比较）与最后一次控制器
        # 动作检查之后、返回成功之前：再核验本次消费文件的磁盘字节、复算失败状态、静态绑定、
        # 数据库、宿主清单与全部 checkpoint。预期只来自初始同缓冲读取或本次真实 writer 返回。
        if initial_judgment_summary is not None:
            _verify_initial_judgment_tail(target, initial_judgment_expected, "status")
            initial_judgment_db = Path(initial_judgment_expected["database_path"])
            _require(file_sha256(initial_judgment_db)
                     == initial_judgment_expected["database_sha256"], str(initial_judgment_db),
                     "B1 收尾复测发现数据库字节与 0008 声明不一致", "status")
            initial_outputs_final = _read_initial_judgment_outputs(target, "status")
            _require(initial_outputs_final["record_file_sha256"]
                     == initial_judgment_expected["record_file_sha256"],
                     f"{WORKFLOW_DIR}/{INITIAL_JUDGMENT_DIR}/{INITIAL_JUDGMENT_RECORD}",
                     "B1 收尾复测发现 initial_judgment 文件字节在本次消费之后发生变化", "status")
            _require(canonical_json(initial_outputs_final["artifacts"])
                     == canonical_json(operation8["artifacts"]),
                     f"{WORKFLOW_DIR}/{INITIAL_JUDGMENT_DIR}/{INITIAL_JUDGMENT_ARTIFACTS}",
                     "B1 收尾复测发现 artifacts 与 0008 内嵌副本不再严格相等", "status")
            _require(canonical_sha256(initial_outputs_final["record_payload"]["record"])
                     == operation8["record_sha256"],
                     f"{WORKFLOW_DIR}/{INITIAL_JUDGMENT_DIR}/{INITIAL_JUDGMENT_RECORD}",
                     "B1 收尾复测发现 record 规范指纹与 0008 声明不一致", "status")
            _require(not _initial_judgment_paths(target)["failure_path"].exists(),
                     f"{WORKFLOW_DIR}/{INITIAL_JUDGMENT_DIR}/{INITIAL_JUDGMENT_FAILURE}",
                     "B1 收尾复测发现成功批次出现了模拟初判失败诊断", "status")
        if fact_packet_summary is not None:
            _verify_fact_packet_tail(target, fact_packet_expected, "status")
            fact_db = Path(fact_packet_expected["database_path"])
            _require(file_sha256(fact_db) == fact_packet_expected["database_sha256"], str(fact_db),
                     "B1 收尾复测发现数据库字节与 0007 声明不一致", "status")
            # 只读恢复不做“再次消费新版本生成摘要”：这里只是把本次已核验的预期再与磁盘对一次；
            # 该读取返回之后必须再做一次**最终**磁盘复测（否则最后一次读取之后的改动不会被本次调用发现）。
            refreshed = _read_fact_packet_outputs(target, "status")
            _require(refreshed["packet_file_sha256"] == fact_packet_expected["packet_file_sha256"]
                     and refreshed["markdown_file_sha256"]
                     == fact_packet_expected["markdown_file_sha256"]
                     and refreshed["artifacts_file_sha256"]
                     == fact_packet_expected["artifacts_file_sha256"],
                     f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}",
                     "收尾复测发现本次摘要所消费的事实底稿产物磁盘字节发生变化", "status")
            _verify_fact_packet_tail(target, fact_packet_expected, "status")
            for key, label_txt in (
                ("packet_file_sha256", f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_JSON}"),
                ("markdown_file_sha256",
                 f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_MARKDOWN}"),
                ("artifacts_file_sha256",
                 f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_ARTIFACTS}"),
                ("started_file_sha256", f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_START}"),
            ):
                got = file_sha256(target / operation7[{"packet_file_sha256": "packet_relative",
                                                       "markdown_file_sha256": "markdown_relative",
                                                       "artifacts_file_sha256":
                                                           "artifacts_relative",
                                                       "started_file_sha256":
                                                           "started_relative"}[key]])
                _require(got == fact_packet_expected[key], label_txt,
                         "最终复测发现本次摘要所消费的事实底稿产物磁盘字节发生变化："
                         f"期望（初始读取）{fact_packet_expected[key]!r}，实际 {got!r}", "status")
            packet_final = _read_json(target / operation7["packet_relative"],
                                      f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_JSON}",
                                      "status")
            _require(canonical_sha256(packet_final) == operation7["packet_sha256"],
                     f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_JSON}",
                     "最终复测发现 packet 对象的规范指纹发生变化", "status")
            artifacts_final = _read_json(target / operation7["artifacts_relative"],
                                         f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_ARTIFACTS}",
                                         "status")
            _require(canonical_json(artifacts_final) == canonical_json(operation7["artifacts"]),
                     f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_ARTIFACTS}",
                     "最终复测发现 artifacts 与 0007 内嵌副本不再严格相等", "status")
            started_final, started_final_sha = _read_json_with_bytes(
                paths_fp["started_path"], f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_START}",
                "status")
            _require(started_final_sha == fact_packet_expected["started_file_sha256"],
                     f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_START}",
                     "最终复测发现 started 文件字节哈希发生变化", "status")
            _require(
                started_final["normalized_payload_sha256"] == artifacts_final[
                    "normalized_payload_sha256"]
                and started_final["screening_report_canonical_sha256"] == artifacts_final[
                    "screening_report_canonical_sha256"]
                and started_final["crosscheck_report_canonical_sha256"] == artifacts_final[
                    "crosscheck_report_canonical_sha256"],
                f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_START}",
                "最终复测发现 started 的输入规范指纹与 artifacts 不再一致", "status")
        if crosscheck_summary is not None:
            crosscheck_tail_final = _verify_crosscheck_tail(target, crosscheck_expected, "status")
            _verify_screen_tail(target, screen_expected, "status")
            db_path_final = Path(crosscheck_expected["database_path"])
            db_sha_final = file_sha256(db_path_final)
            _require(crosscheck_expected["database_sha256"] == db_sha_final, str(db_path_final),
                     "B1 收尾复测发现数据库字节与 0006 声明不一致："
                     f"期望 {crosscheck_expected['database_sha256']!r}，实际 {db_sha_final!r}",
                     "status")
            for key, label_txt in (
                ("report_file_sha256", f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}"),
                ("started_file_sha256", f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_START}"),
                ("artifacts_file_sha256", f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}"),
            ):
                got = file_sha256(target / crosscheck_summary[{"report_file_sha256": "report_relative",
                                                               "started_file_sha256": "started_relative",
                                                               "artifacts_file_sha256":
                                                                   "artifacts_relative"}[key]])
                _require(got == crosscheck_expected[key], label_txt,
                         "B1 收尾复测发现本次摘要所消费的复算产物磁盘字节发生变化："
                         f"期望（初始读取）{crosscheck_expected[key]!r}，实际 {got!r}", "status")
            report_bytes_final = (target / crosscheck_summary["report_relative"]).read_bytes()
            _require(hashlib.sha256(report_bytes_final).hexdigest()
                     == crosscheck_expected["report_file_sha256"],
                     f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}",
                     "B1 收尾复测发现报告文件字节哈希在本次消费之后发生变化", "status")
            report_object_final = _read_json(target / crosscheck_summary["report_relative"],
                                             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}",
                                             "status")
            _require(canonical_sha256(report_object_final) == operation6["report_canonical_sha256"],
                     f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}",
                     "B1 收尾复测发现报告对象的规范指纹在本次消费之后发生变化", "status")
            artifacts_object_final = _read_json(
                target / crosscheck_summary["artifacts_relative"],
                f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}", "status")
            _require(canonical_json(artifacts_object_final) == canonical_json(operation6["artifacts"]),
                     f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}",
                     "B1 收尾复测发现 artifacts 与 0006 内嵌副本不再严格相等", "status")
            _require(not _crosscheck_paths(target)["failure_path"].exists(),
                     f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_FAILURE}",
                     "B1 收尾复测发现成功批次出现了复算失败诊断", "status")
        if _screen_dir(target).exists():
            _verify_screen_tail(target, screen_expected, "status")
        if gate2_expected is not None:
            _verify_gate2_tail(target, gate2_expected, "status")
            _require(file_sha256(_host_manifest_path(target)) == context["manifest_file_sha256"],
                     f"{WORKFLOW_DIR}/{HOST_MANIFEST_NAME}",
                     "B1 收尾复测发现宿主清单字节在本次消费之后发生变化："
                     f"期望（初始读取）{context['manifest_file_sha256']!r}，"
                     f"实际 {file_sha256(_host_manifest_path(target))!r}", "status")
        for item in chain["checkpoints"]:
            got = file_sha256(_checkpoint_path(target, item["revision"]))
            _require(got == item["file_sha256"], f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                     "B1 收尾复测发现 checkpoint 字节在本次消费之后发生变化："
                     f"期望（初始读取）{item['file_sha256']!r}，实际 {got!r}", "status")
        bindings_b1 = _recheck_static_bindings(
            target, measured, "status", when="B1 收尾（最后一次复算输出消费与动作检查之后）")
        _require(canonical_json(bindings_b1) == canonical_json(current["state"]["run_bindings"]),
                 "bindings", "B1 收尾实测的静态绑定必须与本 workflow 创建绑定逐项一致", "status")

        # ---------------------------------------------------------------- 本层最终实读复测
        # TASK-017-R1 B1：这是 status 的最后一次数据消费点（其后只构造内存返回值）。
        # 本次消费的本层四份产物必须在此**重新实读磁盘**并与 0008 的初始核验读数比较：
        # 不得与本次摘要读取的旧缓冲自比，也不得用新读数替换初始预期。
        if initial_judgment_summary is not None:
            paths_ij = _initial_judgment_paths(target)
            _verify_initial_judgment_tail(target, initial_judgment_expected, "status")
            direct_hashes = {
                "started_file_sha256": file_sha256(paths_ij["started_path"]),
                "submission_file_sha256": file_sha256(paths_ij["submission_path"]),
                "record_file_sha256": file_sha256(paths_ij["record_path"]),
                "artifacts_file_sha256": file_sha256(paths_ij["artifacts_path"]),
            }
            direct_labels = {
                "started_file_sha256": f"{paths_ij['relative']}/{INITIAL_JUDGMENT_START}",
                "submission_file_sha256": f"{paths_ij['relative']}/{INITIAL_JUDGMENT_SUBMISSION}",
                "record_file_sha256": f"{paths_ij['relative']}/{INITIAL_JUDGMENT_RECORD}",
                "artifacts_file_sha256": f"{paths_ij['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}",
            }
            for key, value in direct_hashes.items():
                _require(initial_judgment_expected[key] == value, direct_labels[key],
                         "本层最后一次读取之后实读复测发现产物字节发生变化："
                         f"期望（0008 初始核验读数）{initial_judgment_expected[key]!r}，"
                         f"实际 {value!r}", "status")
            record_disk = _read_json(paths_ij["record_path"], direct_labels["record_file_sha256"],
                                     "status")
            _require(isinstance(record_disk, dict)
                     and set(record_disk.keys()) == {"record", "record_sha256"},
                     direct_labels["record_file_sha256"],
                     f"本层记录外层必须恰为 record/record_sha256，实际 "
                     f"{sorted(record_disk) if isinstance(record_disk, dict) else type(record_disk).__name__}",
                     "status")
            _require(canonical_sha256(record_disk["record"]) == operation8["record_sha256"],
                     direct_labels["record_file_sha256"],
                     "本层最后一次读取之后实读复测发现 record 规范指纹与 0008 声明不一致："
                     f"期望 {operation8['record_sha256']!r}，"
                     f"实际 {canonical_sha256(record_disk['record'])!r}", "status")
            artifacts_disk = _read_json(paths_ij["artifacts_path"],
                                        direct_labels["artifacts_file_sha256"], "status")
            _require(canonical_json(artifacts_disk) == canonical_json(operation8["artifacts"]),
                     direct_labels["artifacts_file_sha256"],
                     "本层最后一次读取之后实读复测发现 artifacts 与 0008 内嵌副本不再严格相等",
                     "status")
            submission_disk = _read_json(paths_ij["submission_path"],
                                         direct_labels["submission_file_sha256"], "status")
            _require(canonical_sha256(submission_disk)
                     == initial_judgment_expected["submission_canonical_sha256"],
                     direct_labels["submission_file_sha256"],
                     "本层最后一次读取之后实读复测发现 submission 快照规范指纹发生变化", "status")
            started_disk = _read_json(paths_ij["started_path"],
                                      direct_labels["started_file_sha256"], "status")
            _require(started_disk.get("submission_canonical_sha256")
                     == initial_judgment_expected["submission_canonical_sha256"],
                     direct_labels["started_file_sha256"],
                     "本层最后一次读取之后实读复测发现 started 记录的提交指纹与快照不一致",
                     "status")
            entry8_final = next(item for item in chain["checkpoints"] if item["revision"] == 8)
            _require(file_sha256(_checkpoint_path(target, 8)) == entry8_final["file_sha256"],
                     f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0008.json",
                     "本层最后一次读取之后实读复测发现 0008 字节发生变化："
                     f"期望（初始读取）{entry8_final['file_sha256']!r}，"
                     f"实际 {file_sha256(_checkpoint_path(target, 8))!r}", "status")
            # 再走一次字节级确认：覆盖“最后一次对象读取返回之后”的改动
            for key, value in (
                ("started_file_sha256", file_sha256(paths_ij["started_path"])),
                ("submission_file_sha256", file_sha256(paths_ij["submission_path"])),
                ("record_file_sha256", file_sha256(paths_ij["record_path"])),
                ("artifacts_file_sha256", file_sha256(paths_ij["artifacts_path"])),
            ):
                _require(initial_judgment_expected[key] == value, direct_labels[key],
                         "本层最终字节复测发现产物字节发生变化："
                         f"期望（0008 初始核验读数）{initial_judgment_expected[key]!r}，"
                         f"实际 {value!r}", "status")
            _require(not paths_ij["failure_path"].exists(),
                     f"{paths_ij['relative']}/{INITIAL_JUDGMENT_FAILURE}",
                     "本层最后一次读取之后实读复测发现成功批次出现失败诊断", "status")

        return {
            "host_version": HOST_VERSION,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "status": STATUS_READY,
            "next_step_allowed": False,
            "batch_id": target.name,
            "batch_dir": str(target),
            "phase": action["phase"],
            "state_sha256": current["state_sha256"],
            "simulated_action_allowed": action["simulation_allowed"],
            "action_checked": action_name,
            "action_reason": action["reason"],
            "actions_simulated_allowed": other_actions,
            "completed_actions": completed_actions,
            "screening_status": ("RULE_SCREEN_RECORDED" if revision_now >= 5 else None),
            "screening": screen_summary,
            "screen_tail": (None if screen_tail_actual is None else sorted(screen_tail_actual.keys())),
            "crosscheck_status": (CROSSCHECK_STATUS_RECORDED if revision_now >= 6 else None),
            "crosscheck": crosscheck_summary,
            "fact_packet_status": (FACT_PACKET_STATUS_RECORDED if revision_now >= 7 else None),
            "fact_packet": fact_packet_summary,
            "initial_judgment_status": (INITIAL_JUDGMENT_STATUS_RECORDED
                                        if revision_now >= 8 else None),
            "initial_judgment": initial_judgment_summary,
            "gate2_decision": gate2_decision_summary,
            "gate2_pending_request": (None if revision_now < 3 else
                                      {"request_id": current["state"]["requests"][
                                          CONTROLLER_MODULE.GATE2]["request_id"],
                                       "materials_sha256": current["state"]["requests"][
                                          CONTROLLER_MODULE.GATE2]["materials_sha256"]}),
            "checkpoints": [{"path": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                             "revision": item["revision"], "file_sha256": item["file_sha256"]}
                            for item in chain["checkpoints"]],
            "current_checkpoint": chain["current_path"],
            "current_checkpoint_file_sha256": chain["current_file_sha256"],
            "bindings_sha256": CONTROLLER_MODULE.canonical_sha256(bindings_final),
            "simulated_decisions": len(current["state"]["simulated_decisions"]),
            "real_approvals": int(current["state"]["gate1_approval"] is not None)
            + int(current["state"]["gate2_approval"] is not None),
            "verified_files": {label: info["sha256"]
                               for label, info in context["manifest"]["receive"]["materials"].items()},
            "host_manifest": {"path": f"{WORKFLOW_DIR}/{HOST_MANIFEST_NAME}",
                              "file_sha256": context["manifest_file_sha256"]},
            "gate2_tail": (None if gate2_tail_actual is None else
                           {"verified": sorted(gate2_tail_actual.keys()),
                            "artifacts_file_sha256": gate2_tail_actual["artifacts_file_sha256"],
                            "database_sha256": gate2_tail_actual["database_sha256"]}),
            "note": ("status 只读取与验证，不写入任何文件；本次 status 调用没有执行标准化、装载、"
                     "规则、底稿或 AI。" + ("该批次已完成的动作：" + "、".join(completed_actions)
                                        + "（历史事实，不是本次 status 执行的）。"
                                        if completed_actions else "")),
        }
    except WorkflowHostBlocked:
        raise
    except WorkflowHostError:
        raise
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        raise WorkflowHostBlocked(f"[status] 冻结控制器阻断：{exc}", stage="status") from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        raise WorkflowHostError(f"[status] 冻结控制器意外错误：{exc}", stage="status") from exc
    except Exception as exc:  # noqa: BLE001
        raise WorkflowHostError(f"[status] 意外运行失败：{type(exc).__name__}: {exc}",
                                ["阶段=status", f"原始异常={type(exc).__name__}: {exc}"], "status") from exc


# ---------------------------------------------------------------------------
# prepare-gate2
# ---------------------------------------------------------------------------


def _exception_chain(exc: BaseException) -> list:
    """完整异常链（含 cause／context），用于失败诊断如实保存原始原因。"""
    chain: list = []
    seen: set = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append({"class": type(current).__name__, "message": str(current),
                      "stage": getattr(current, "stage", None),
                      "reasons": [str(item) for item in getattr(current, "reasons", []) or []]})
        current = current.__cause__ if current.__cause__ is not None else current.__context__
    return chain


def _map_upstream_exception(exc: Exception, stage: str = "prepare_gate2") -> Exception:
    """上游 Blocked 与 Error 按各自语义映射，不笼统叫质量不通过；阶段必须由调用方给出。"""
    if isinstance(exc, (WorkflowHostBlocked, WorkflowHostError)):
        return exc
    if isinstance(exc, (NORMALIZER_MODULE.NormalizationBlocked, STORE_MODULE.SqliteLoadBlocked)):
        return WorkflowHostBlocked(f"上游拒绝（{type(exc).__name__}）：{exc}",
                                   reasons=[str(exc)], stage="upstream_blocked")
    if isinstance(exc, (NORMALIZER_MODULE.NormalizationError, STORE_MODULE.SqliteLoadError)):
        return WorkflowHostError(f"上游运行失败（{type(exc).__name__}）：{exc}",
                                 reasons=[str(exc)], stage="upstream_error")
    return WorkflowHostError(f"意外运行失败：{type(exc).__name__}: {exc}",
                             reasons=[str(exc)], stage=stage)


def _gate2_observed_state(batch_dir: Path) -> dict:
    """如实记录本次尝试已产生的输出状态（不补造成功信息）。"""
    gate2 = _gate2_dir(batch_dir)
    observed = {"gate2_dir_exists": gate2.exists(), "files": {}, "database_exists": None,
                "staging_exists": None}
    if gate2.exists():
        for name in sorted(item.name for item in gate2.iterdir()):
            path = gate2 / name
            observed["files"][name] = ({"exists": True, "is_file": path.is_file(),
                                        "bytes": path.stat().st_size} if path.is_file()
                                       else {"exists": True, "is_file": False})
    try:
        paths = _gate2_paths(batch_dir, "prepare_gate2")
    except WorkflowHostBlocked:
        return observed
    observed["database_exists"] = paths["database_path"].exists()
    observed["staging_exists"] = paths["staging_path"].exists()
    observed["output_dir_exists"] = paths["output_dir"].exists()
    return observed


def prepare_dev_gate2(batch_dir) -> dict:
    """真实标准化 + 真实装载 + 保存材料，形成 Gate2 待确认请求并停在 DEV_GATE2_PENDING。"""
    try:
        target = _resolve_batch_dir(batch_dir, must_exist=True, stage="prepare_gate2")
        gate2 = _gate2_dir(target)
        if gate2.exists():
            raise WorkflowHostBlocked(
                f"{WORKFLOW_DIR}/{GATE2_DIR}/ 已开始存在：同一批次不重试、不复用、不自动删除已产生的文件；"
                "需继续时新建批次", stage="prepare_gate2")

        context = _load_host_context(target, stage="prepare_gate2")
        measured = context["measured_bindings"]
        manifest = context["manifest"]
        chain = context["chain"]
        _require(chain["current"]["revision"] == 2, "checkpoint",
                 f"prepare-gate2 只接受合法 Gate1 APPROVE 的 0002，实际第 {chain['current']['revision']} 份",
                 "prepare_gate2")
        current_workflow = chain["current"]["payload"]["workflow"]
        state = current_workflow["state"]
        _require(state["phase"] == CONTROLLER_MODULE.PHASE_G1_APPROVED, "workflow.state.phase",
                 f"只接受 {CONTROLLER_MODULE.PHASE_G1_APPROVED}，实际 {state['phase']!r}", "prepare_gate2")
        decisions = state["simulated_decisions"]
        _require(isinstance(decisions, list) and len(decisions) == 1, "workflow.state.simulated_decisions",
                 "0002 必须恰含一个 Gate1 决定", "prepare_gate2")
        gate1_decision = decisions[0]
        _require(gate1_decision.get("decision") == CONTROLLER_MODULE.DECISION_APPROVE,
                 "workflow.state.simulated_decisions[0].decision",
                 f"只接受显式模拟 {CONTROLLER_MODULE.DECISION_APPROVE}，实际 {gate1_decision.get('decision')!r}",
                 "prepare_gate2")
        gate1_body_sha = canonical_sha256({key: value for key, value in gate1_decision.items()
                                          if key != "decision_sha256"})

        # 授权来自冻结控制器的行为检查，不从 phase 字符串推导
        try:
            action = CONTROLLER_MODULE.check_dev_action(current_workflow, "NORMALIZE_AND_LOAD",
                                                       current_bindings=measured)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"冻结控制器阻断本次动作检查：{exc}", stage="prepare_gate2") from exc
        _require(action["simulation_allowed"] is True, "check_dev_action.simulation_allowed",
                 f"必须严格为 true，实际 {action['simulation_allowed']!r}", "prepare_gate2")

        paths = _gate2_paths(target, "prepare_gate2")
        for label, path in (("目标数据库", paths["database_path"]),
                            (".staging", paths["staging_path"]),
                            ("本次输出目录", paths["output_dir"])):
            _require(not path.exists(), label,
                     f"{label}已存在，拒绝覆盖、删除或换名续跑：{path}", "prepare_gate2")

        stage_label = "prepare_gate2"
        try:
            try:
                os.mkdir(gate2)
            except FileExistsError as exc:
                raise WorkflowHostBlocked(f"{WORKFLOW_DIR}/{GATE2_DIR}/ 已存在：本批次已有尝试",
                                          stage=stage_label) from exc
            try:
                paths["output_dir"].mkdir(parents=True)
            except FileExistsError as exc:
                raise WorkflowHostBlocked(f"输出目录已存在：{paths['output_dir']}", stage=stage_label) from exc
            except OSError as exc:
                raise WorkflowHostError(f"无法创建输出目录 {paths['output_dir']}：{exc}",
                                        stage=stage_label) from exc

            workbook = target / "source" / "input.xlsx"
            quality_report = _read_json(target / "checks" / "quality_report.json",
                                        "checks/quality_report.json", stage_label)
            stage_label = "normalize"
            normalized = NORMALIZER_MODULE.normalize_workbook(workbook, quality_report)
            _require(isinstance(normalized, dict), "normalize_workbook",
                     f"必须返回对象，实际 {type(normalized).__name__}", stage_label)
            normalized_path = gate2 / GATE2_NORMALIZED
            normalized_file_sha = _write_exclusive_json(normalized_path, normalized, stage_label)
            normalized_readback = _read_json(normalized_path, f"{WORKFLOW_DIR}/{GATE2_DIR}/"
                                                              f"{GATE2_NORMALIZED}", stage_label)
            _require(canonical_json(normalized_readback) == canonical_json(normalized),
                     f"{GATE2_NORMALIZED}", "读回内容必须与本次标准化对象一致", stage_label)
            normalized_sha = canonical_sha256(normalized)
            _require(normalized_readback.get("source", {}).get("input_sha256")
                     == manifest["bindings"]["input_sha256"], f"{GATE2_NORMALIZED}.source.input_sha256",
                     "标准化来源必须与批次绑定一致", stage_label)

            stage_label = "load"
            load_report = STORE_MODULE.load_normalized_to_sqlite(normalized, paths["database_path"])
            _require(isinstance(load_report, dict), "load_normalized_to_sqlite",
                     f"必须返回对象，实际 {type(load_report).__name__}", stage_label)
            report_path = gate2 / GATE2_LOAD_REPORT
            report_file_sha = _write_exclusive_json(report_path, load_report, stage_label)
            report_readback = _read_json(report_path, f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}",
                                         stage_label)
            _require(canonical_json(report_readback) == canonical_json(load_report),
                     f"{GATE2_LOAD_REPORT}", "读回内容必须与本次装载报告一致", stage_label)

            stage_label = "verify_artifacts"
            _require(paths["database_path"].is_file(), "database",
                     f"装载成功必须留下数据库文件：{paths['database_path']}", stage_label)
            database_sha = file_sha256(paths["database_path"])
            _require(load_report.get("database_sha256") == database_sha, "load_report.database_sha256",
                     "必须等于数据库实际字节哈希", stage_label)
            _require(load_report.get("normalized_payload_sha256") == normalized_sha,
                     "load_report.normalized_payload_sha256",
                     "必须等于本次 normalized 对象的规范指纹", stage_label)
            _require(load_report.get("database_path") == str(paths["database_path"]),
                     "load_report.database_path", "必须等于宿主推导的固定路径", stage_label)
            _require(load_report.get("source", {}).get("input_sha256")
                     == manifest["bindings"]["input_sha256"], "load_report.source.input_sha256",
                     "装载报告来源必须与批次绑定一致", stage_label)

            stage_label = "write_artifacts"
            artifacts = {
                "artifacts_version": ARTIFACTS_VERSION,
                "batch_id": target.name,
                "output_relative": paths["relative"],
                "database_path": str(paths["database_path"]),
                "database_sha256": database_sha,
                "normalized_payload_sha256": normalized_sha,
                "normalized_file_sha256": normalized_file_sha,
                "load_report_file_sha256": report_file_sha,
                "previous_checkpoint_file_sha256": chain["current_file_sha256"],
                "gate1_decision_sha256": gate1_body_sha,
                "prepare_version": HOST_VERSION,
                "checkpoint_version": CHECKPOINT_VERSION,
                "host_manifest_file_sha256": context["manifest_file_sha256"],
                "created_at_utc": _now_utc(),
                "note": ("本次产物由宿主实际调用冻结标准化与装载器得到；"
                         "删除这些文件会使恢复核验失败。"),
            }
            artifacts_path = gate2 / GATE2_ARTIFACTS
            artifacts_file_sha = _write_exclusive_json(artifacts_path, artifacts, stage_label)
            artifacts_readback = _read_json(artifacts_path, f"{WORKFLOW_DIR}/{GATE2_DIR}/"
                                                            f"{GATE2_ARTIFACTS}", stage_label)
            _require(canonical_json(artifacts_readback) == canonical_json(artifacts),
                     f"{GATE2_ARTIFACTS}", "读回内容必须与本次产物摘要一致", stage_label)

            stage_label = "prepare_gate2_request"
            materials = _gate2_materials(target, context, normalized, load_report)
            materials_sha = canonical_sha256(materials)
            try:
                workflow = CONTROLLER_MODULE.prepare_dev_gate(current_workflow, CONTROLLER_MODULE.GATE2,
                                                             materials, current_bindings=measured)
            except CONTROLLER_MODULE.WorkflowBlocked as exc:
                raise WorkflowHostBlocked(f"冻结控制器阻断 Gate2 请求：{exc}",
                                          stage=stage_label) from exc
            except CONTROLLER_MODULE.WorkflowError as exc:
                raise WorkflowHostError(f"冻结控制器意外错误：{exc}", stage=stage_label) from exc
            _require(workflow["state"]["phase"] == CONTROLLER_MODULE.PHASE_G2_PENDING,
                     "workflow.state.phase",
                     f"必须停在 {CONTROLLER_MODULE.PHASE_G2_PENDING}", stage_label)

            stage_label = "write_checkpoint"
            checkpoint = {
                "checkpoint_version": CHECKPOINT_VERSION,
                "revision": 3,
                "previous_file_sha256": chain["current_file_sha256"],
                "batch_id": target.name,
                "host_manifest_file_sha256": context["manifest_file_sha256"],
                "workflow": workflow,
                "operation": {
                    "kind": OPERATION_PREPARE_GATE2,
                    "at_utc": _now_utc(),
                    "artifacts": copy.deepcopy(artifacts),
                    "artifacts_file_sha256": artifacts_file_sha,
                    "materials_sha256": materials_sha,
                    "phase_after": workflow["state"]["phase"],
                    "bindings_sha256": workflow["state"]["run_bindings_sha256"],
                    "gate1_decision_sha256": gate1_body_sha,
                    "database_sha256": database_sha,
                    "normalized_payload_sha256": normalized_sha,
                    "database_path": str(paths["database_path"]),
                    "output_relative": paths["relative"],
                },
            }
            checkpoint_file_hash = _write_exclusive_json(_checkpoint_path(target, 3), checkpoint,
                                                        stage_label)

            stage_label = "post_write_verify"
            context_after = _load_host_context(target, stage="prepare_gate2")
            _require(context_after["chain"]["current_file_sha256"] == checkpoint_file_hash, "checkpoint",
                     "写后读回的当前 checkpoint 字节哈希与写入结果不一致", stage_label)
            _require(context_after["chain"]["current"]["revision"] == 3, "checkpoint",
                     "写后当前 checkpoint 必须为 0003", stage_label)
            _require(canonical_json(context_after["measured_bindings"]) == canonical_json(measured),
                     "bindings", "提交后重新实测的绑定与操作前不一致（保存现场并拒绝成功宣告）",
                     stage_label)
            # 最后一次控制器调用之后：统一复测本次消费的全部产物
            tail_expected = {
                "normalized_file_sha256": normalized_file_sha,
                "load_report_file_sha256": report_file_sha,
                "artifacts_file_sha256": artifacts_file_sha,
                "database_sha256": database_sha,
                "host_manifest_file_sha256": context["manifest_file_sha256"],
                "checkpoints": {1: chain["checkpoints"][0]["file_sha256"],
                                2: chain["checkpoints"][1]["file_sha256"],
                                3: checkpoint_file_hash},
            }
            tail_actual = _verify_gate2_tail(target, tail_expected, stage_label)
        except (WorkflowHostBlocked, WorkflowHostError, NORMALIZER_MODULE.NormalizationBlocked,
                NORMALIZER_MODULE.NormalizationError, STORE_MODULE.SqliteLoadBlocked,
                STORE_MODULE.SqliteLoadError) as exc:
            mapped = _map_upstream_exception(exc)
            observed = _gate2_observed_state(target)
            try:
                _save_gate2_failure(target, getattr(mapped, "stage", "") or "prepare_gate2", mapped, observed)
            except (WorkflowHostBlocked, WorkflowHostError) as save_exc:
                raise WorkflowHostError(
                    f"本次 prepare-gate2 失败且失败诊断也未能保存：{mapped}（保存失败：{save_exc}）",
                    reasons=[str(mapped), f"保存失败：{save_exc}"],
                    stage=getattr(mapped, "stage", "") or "prepare_gate2") from exc
            if mapped is exc:
                raise  # 保留原始异常链（不把同对象自引用成 __cause__）
            raise mapped from exc

        return {
            "host_version": HOST_VERSION,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "status": STATUS_READY,
            "next_step_allowed": False,
            "batch_id": target.name,
            "batch_dir": str(target),
            "phase": workflow["state"]["phase"],
            "state_sha256": workflow["state_sha256"],
            "gate1_decision": {"event_id": gate1_decision["event_id"],
                               "decision": gate1_decision["decision"],
                               "decision_sha256": gate1_body_sha},
            "artifacts": {"path": f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}",
                          "file_sha256": artifacts_file_sha,
                          "database_path": str(paths["database_path"]),
                          "database_sha256": database_sha,
                          "normalized_payload_sha256": normalized_sha,
                          "output_relative": paths["relative"]},
            "materials_sha256": materials_sha,
            "checkpoints": [{"path": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                             "revision": item["revision"], "file_sha256": item["file_sha256"]}
                            for item in context_after["chain"]["checkpoints"]],
            "current_checkpoint": context_after["chain"]["current_path"],
            "current_checkpoint_file_sha256": checkpoint_file_hash,
            "previous_checkpoint_file_sha256": chain["current_file_sha256"],
            "bindings_sha256": CONTROLLER_MODULE.canonical_sha256(measured),
            "real_approvals": 0,
            "note": ("本次实际运行了标准化与 SQLite 装载，并停在 Gate2 待确认；"
                     "未执行筛查、复算、底稿或 AI，未提交任何 Gate2 决定。"),
        }
    except WorkflowHostBlocked:
        raise
    except WorkflowHostError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise WorkflowHostError(f"[prepare_gate2] 意外运行失败：{type(exc).__name__}: {exc}",
                                ["阶段=prepare_gate2", f"原始异常={type(exc).__name__}: {exc}"],
                                "prepare_gate2") from exc


# ---------------------------------------------------------------------------
# record-simulated-decision
# ---------------------------------------------------------------------------


def record_simulated_gate1_decision(batch_dir, decision) -> dict:
    """把完整模拟决定正文交给冻结控制器；只处理当前 Gate1 pending，然后停住。"""
    try:
        target = _resolve_batch_dir(batch_dir, must_exist=True, stage="record")
        context = _load_host_context(target, stage="record")
        measured = context["measured_bindings"]
        chain = context["chain"]
        if _gate2_dir(target).exists():
            if chain["current"]["revision"] < 3:
                _raise_incomplete_gate2(target, chain)
            raise WorkflowHostBlocked(
                "该批次已进入 Gate2（0003 或更后）：Gate1 决定不可重复提交、不可改签；"
                "Gate2 决定请使用 record-simulated-gate2-decision（本命令只处理 Gate1）", stage="record")
        if chain["current"]["revision"] != 1:
            raise WorkflowHostBlocked(
                f"已有第 {chain['current']['revision']} 份 checkpoint：重复或冲突决定不得覆盖或继续追加，"
                "需补证／修订时新建批次", stage="record")
        current = chain["current"]["payload"]["workflow"]
        _require(current["state"]["phase"] == CONTROLLER_MODULE.PHASE_G1_PENDING, "workflow.state.phase",
                 f"只接受当前 DEV_GATE1_PENDING，实际 {current['state']['phase']!r}", "record")
        try:
            workflow = CONTROLLER_MODULE.record_dev_decision(current, decision, current_bindings=measured)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"冻结控制器阻断该决定：{exc}", stage="record") from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"冻结控制器意外错误：{exc}", stage="record") from exc
        recorded = workflow["state"]["simulated_decisions"][-1]
        checkpoint = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "revision": 2,
            "previous_file_sha256": chain["current_file_sha256"],
            "batch_id": target.name,
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "workflow": workflow,
            "operation": {
                "kind": "SIMULATED_GATE1_DECISION",
                "at_utc": _now_utc(),
                "decision": copy.deepcopy(recorded),
                "decision_sha256": CONTROLLER_MODULE.canonical_sha256(
                    {key: value for key, value in recorded.items() if key != "decision_sha256"}),
                "phase_after": workflow["state"]["phase"],
                "bindings_sha256": workflow["state"]["run_bindings_sha256"],
            },
        }
        checkpoint_file_hash = _write_exclusive_json(_checkpoint_path(target, 2), checkpoint, "record")

        # 写后收尾：重核 checkpoint 协议／链，并重新实测绑定
        context_after = _load_host_context(target, stage="record")
        _require(context_after["chain"]["current_file_sha256"] == checkpoint_file_hash, "checkpoint",
                 "写后读回的当前 checkpoint 字节哈希与写入结果不一致", "record")
        _require(canonical_json(context_after["measured_bindings"]) == canonical_json(measured), "bindings",
                 "提交后重新实测的绑定与操作前不一致（保存现场并拒绝成功宣告）", "record")
        _require(file_sha256(_checkpoint_path(target, 1)) == chain["current_file_sha256"],
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0001.json", "提交后 0001 字节发生变化", "record")
        return {
            "host_version": HOST_VERSION,
            "mode": MODE,
            "contract_status": CONTROLLER_MODULE.CONTRACT_STATUS,
            "status": STATUS_READY,
            "next_step_allowed": False,
            "batch_id": target.name,
            "batch_dir": str(target),
            "phase": workflow["state"]["phase"],
            "state_sha256": workflow["state_sha256"],
            "decision": {"event_id": recorded["event_id"], "decision": recorded["decision"],
                         "actor_kind": recorded["actor_kind"], "simulation": recorded["simulation"],
                         "decision_sha256": recorded["decision_sha256"]},
            "checkpoints": [{"path": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                             "revision": item["revision"], "file_sha256": item["file_sha256"]}
                            for item in context_after["chain"]["checkpoints"]],
            "current_checkpoint": context_after["chain"]["current_path"],
            "current_checkpoint_file_sha256": checkpoint_file_hash,
            "previous_checkpoint_file_sha256": chain["current_file_sha256"],
            "bindings_sha256": CONTROLLER_MODULE.canonical_sha256(context_after["measured_bindings"]),
            "real_approvals": 0,
            "note": "三种决定后都停住：不执行标准化、不 prepare Gate2、不生成 AI 建议。",
        }
    except WorkflowHostBlocked:
        raise
    except WorkflowHostError:
        raise
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        raise WorkflowHostBlocked(f"[record] 冻结控制器阻断：{exc}", stage="record") from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        raise WorkflowHostError(f"[record] 冻结控制器意外错误：{exc}", stage="record") from exc
    except Exception as exc:  # noqa: BLE001
        raise WorkflowHostError(f"[record] 意外运行失败：{type(exc).__name__}: {exc}",
                                ["阶段=record", f"原始异常={type(exc).__name__}: {exc}"], "record") from exc


def record_simulated_gate2_decision(batch_dir, decision) -> dict:
    """把完整模拟决定正文交给冻结控制器；只处理当前 Gate2 pending 的 0003，然后停住。"""
    stage = "record_gate2"
    try:
        target = _resolve_batch_dir(batch_dir, must_exist=True, stage=stage)
        context = _load_host_context(target, stage=stage)
        measured = context["measured_bindings"]
        chain = context["chain"]
        revision = chain["current"]["revision"]
        if _gate2_dir(target).exists() and revision < 3:
            _raise_incomplete_gate2(target, chain)
        if revision < 3:
            raise WorkflowHostBlocked(
                f"当前只有第 {revision} 份 checkpoint：Gate2 决定只能在合法的 0003／"
                f"{CONTROLLER_MODULE.PHASE_G2_PENDING} 上记录，需先真实完成 prepare-gate2"
                "（早期阶段与停止态一律拒绝，不从 phase 字符串推导批准）", stage=stage)
        if revision >= 4:
            raise WorkflowHostBlocked(
                f"已有第 {revision} 份 checkpoint（{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/"
                f"{revision:04d}.json）：重复或冲突的 Gate2 决定不得覆盖、改签或继续追加，"
                "需补证／修订时新建批次", stage=stage)
        current_workflow = chain["current"]["payload"]["workflow"]
        state = current_workflow["state"]
        _require(state["phase"] == CONTROLLER_MODULE.PHASE_G2_PENDING, "workflow.state.phase",
                 f"只接受当前 {CONTROLLER_MODULE.PHASE_G2_PENDING}，实际 {state['phase']!r}", stage)
        gate2_expected = dict(chain["gate2_expected"] or {})
        _require(bool(gate2_expected), "chain.gate2_expected",
                 "0003 恢复必须带出初次材料核验读数（后续收尾复测以它为预期）", stage)
        gate2_expected["checkpoints"] = {item["revision"]: item["file_sha256"]
                                         for item in chain["checkpoints"]}
        try:
            workflow = CONTROLLER_MODULE.record_dev_decision(current_workflow, decision,
                                                            current_bindings=measured)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"冻结控制器阻断该决定：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"冻结控制器意外错误：{exc}", stage=stage) from exc
        recorded = workflow["state"]["simulated_decisions"][-1]
        checkpoint = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "revision": 4,
            "previous_file_sha256": chain["current_file_sha256"],
            "batch_id": target.name,
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "workflow": workflow,
            "operation": {
                "kind": OPERATION_GATE2_DECISION,
                "at_utc": _now_utc(),
                "decision": copy.deepcopy(recorded),
                "decision_sha256": CONTROLLER_MODULE.canonical_sha256(
                    {key: value for key, value in recorded.items() if key != "decision_sha256"}),
                "phase_after": workflow["state"]["phase"],
                "bindings_sha256": workflow["state"]["run_bindings_sha256"],
            },
        }
        checkpoint_file_hash = _write_exclusive_json(_checkpoint_path(target, 4), checkpoint, stage)
        # 收尾预期补齐：旧三份仍用本次初始同缓冲读取的哈希，0004 用本次真实 writer 返回的文件字节哈希
        gate2_expected["checkpoints"] = {
            **{item["revision"]: item["file_sha256"] for item in chain["checkpoints"]},
            4: checkpoint_file_hash,
        }

        # 写后收尾：共用恢复协议重放完整链，再在最后一次控制器调用之后复测全部已消费产物
        context_after = _load_host_context(target, stage=stage)
        measured_after = context_after["measured_bindings"]
        _require(context_after["chain"]["current_file_sha256"] == checkpoint_file_hash, "checkpoint",
                 "写后读回的当前 checkpoint 字节哈希与写入结果不一致（不宣告成功）", stage)
        try:
            action = CONTROLLER_MODULE.check_dev_action(workflow, CONTROLLER_MODULE.ACTION_SCREEN,
                                                       current_bindings=measured_after)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"写后动作复核被冻结控制器阻断：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"写后动作复核出现意外错误：{exc}", stage=stage) from exc
        gate2_tail_actual = _verify_gate2_tail(target, gate2_expected, stage)
        # F02：最后一次必要控制器调用（写后 SCREEN 动作检查）之后，从磁盘重新实测静态绑定
        bindings_final = _recheck_static_bindings(
            target, measured, stage, when="Gate2 决定提交收尾（最后一次控制器动作检查之后）")
        _require(canonical_json(bindings_final) == canonical_json(workflow["state"]["run_bindings"]),
                 "bindings", "收尾实测的静态绑定必须与本 workflow 创建绑定逐项一致", stage)
        for item in chain["checkpoints"]:
            _require(file_sha256(_checkpoint_path(target, item["revision"])) == item["file_sha256"],
                     f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                     "提交后旧 checkpoint 字节发生变化（不覆盖、不改签）", stage)
        return {
            "host_version": HOST_VERSION,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "status": STATUS_READY,
            "next_step_allowed": False,
            "batch_id": target.name,
            "batch_dir": str(target),
            "phase": workflow["state"]["phase"],
            "state_sha256": workflow["state_sha256"],
            "decision": {"event_id": recorded["event_id"], "decision": recorded["decision"],
                         "actor_kind": recorded["actor_kind"], "simulation": recorded["simulation"],
                         "decision_sha256": recorded["decision_sha256"]},
            "checkpoints": [{"path": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                             "revision": item["revision"], "file_sha256": item["file_sha256"]}
                            for item in context_after["chain"]["checkpoints"]],
            "current_checkpoint": context_after["chain"]["current_path"],
            "current_checkpoint_file_sha256": checkpoint_file_hash,
            "previous_checkpoint_file_sha256": chain["current_file_sha256"],
            "bindings_sha256": CONTROLLER_MODULE.canonical_sha256(bindings_final),
            "simulated_action_allowed": action["simulation_allowed"],
            "action_checked": CONTROLLER_MODULE.ACTION_SCREEN,
            "action_reason": action["reason"],
            "simulated_decisions": len(workflow["state"]["simulated_decisions"]),
            "real_approvals": int(workflow["state"]["gate1_approval"] is not None)
            + int(workflow["state"]["gate2_approval"] is not None),
            "gate2_tail": {"verified": sorted(gate2_tail_actual.keys()),
                           "artifacts_file_sha256": gate2_tail_actual["artifacts_file_sha256"],
                           "database_sha256": gate2_tail_actual["database_sha256"]},
            "note": ("三种 Gate2 决定后都停住：不执行筛查、复算、底稿或 AI，不触发下一步；"
                     "模拟 APPROVE 只表示控制器声明筛查可行，宿主没有执行筛查的命令。"),
        }
    except WorkflowHostBlocked:
        raise
    except WorkflowHostError:
        raise
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        raise WorkflowHostBlocked(f"[record_gate2] 冻结控制器阻断：{exc}", stage=stage) from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        raise WorkflowHostError(f"[record_gate2] 冻结控制器意外错误：{exc}", stage=stage) from exc
    except Exception as exc:  # noqa: BLE001
        raise WorkflowHostError(f"[record_gate2] 意外运行失败：{type(exc).__name__}: {exc}",
                                ["阶段=record_gate2", f"原始异常={type(exc).__name__}: {exc}"], stage) from exc


# ---------------------------------------------------------------------------
# screen-rules
# ---------------------------------------------------------------------------


def screen_dev_batch(batch_dir) -> dict:
    """在合法 Gate2 模拟 APPROVE 的批次上真正执行一次只读 R01—R04 筛查，保存产物与 0005。"""
    stage = "screen"
    screen_paths = None
    target = None
    screen_started = {"value": False}

    def _save_screen_failure_if_started(exc: Exception) -> None:
        """只有本次真正创建了 screening 目录之后才留痕；操作开始前的拒绝与已有现场都不写。"""
        if target is None or screen_paths is None or not screen_started["value"]:
            return
        if (screen_paths["failure_path"]).exists():
            return
        try:
            _save_screen_failure(target, getattr(exc, "stage", "") or stage, exc,
                                 _screen_observed_state(target))
        except (WorkflowHostBlocked, WorkflowHostError) as save_exc:
            raise WorkflowHostError(
                f"本次筛查失败且失败诊断也未能保存：{exc}（保存失败：{save_exc}）",
                reasons=[str(exc), f"保存失败：{save_exc}"],
                stage=getattr(exc, "stage", "") or stage) from exc

    try:
        target = _resolve_batch_dir(batch_dir, must_exist=True, stage=stage)
        context = _load_host_context(target, stage=stage)
        measured = context["measured_bindings"]
        manifest = context["manifest"]
        chain = context["chain"]
        revision = chain["current"]["revision"]
        screen_paths = _screen_paths(target)
        if screen_paths["dir"].exists():
            raise WorkflowHostBlocked(
                f"已有筛查现场 {WORKFLOW_DIR}/{SCREEN_DIR}/：本宿主不接管、不覆盖、不清空、"
                "不自动重试；如需重新筛查请新建批次", stage=stage)
        if revision < 4:
            raise WorkflowHostBlocked(
                f"当前只有第 {revision} 份 checkpoint：只读规则筛查只能在合法的 0004／"
                f"{CONTROLLER_MODULE.PHASE_G2_APPROVED} 上执行（早期阶段与停止态一律拒绝，"
                "不从 phase 字符串推导批准）", stage=stage)
        if revision >= 5:
            raise WorkflowHostBlocked(
                f"已有第 {revision} 份 checkpoint（{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/"
                f"{revision:04d}.json）：本批次已完成筛查，重复筛查不得覆盖、改签或追加 0006",
                stage=stage)
        current_workflow = chain["current"]["payload"]["workflow"]
        state = current_workflow["state"]
        _require(state["phase"] == CONTROLLER_MODULE.PHASE_G2_APPROVED, "workflow.state.phase",
                 f"只接受当前 {CONTROLLER_MODULE.PHASE_G2_APPROVED}（HOLD／REJECT／pending 一律不筛查），"
                 f"实际 {state['phase']!r}", stage)
        gate2_expected = dict(chain["gate2_expected"] or {})
        _require(bool(gate2_expected), "chain.gate2_expected",
                 "0004 恢复必须带出初次材料核验读数（筛查收尾以它为预期）", stage)
        gate2_expected["checkpoints"] = {item["revision"]: item["file_sha256"]
                                        for item in chain["checkpoints"]}

        # 步骤 2：动作允许来自冻结控制器，且必须是严格 bool true
        try:
            action = CONTROLLER_MODULE.check_dev_action(current_workflow, CONTROLLER_MODULE.ACTION_SCREEN,
                                                        current_bindings=measured)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"冻结控制器不允许本次筛查动作：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"筛查动作检查出现意外错误：{exc}", stage=stage) from exc
        _require(action.get("simulation_allowed") is True, "action.simulation_allowed",
                 f"必须严格为 true（模拟允许，不等于真实批准），实际 {action.get('simulation_allowed')!r}",
                 stage)

        # 步骤 3：保存操作开始时读数；独占创建筛查目录与 started.json
        outputs = _read_gate2_outputs(target, stage)
        paths = _gate2_paths(target, stage)
        database_path = paths["database_path"]
        database_sha = file_sha256(database_path)
        previous_file_sha256 = chain["current_file_sha256"]
        try:
            screen_paths["dir"].mkdir(exist_ok=False)
        except FileExistsError as exc:
            raise WorkflowHostBlocked(
                f"筛查现场目录已存在，不接管：{screen_paths['relative']}", stage=stage) from exc
        except OSError as exc:
            raise WorkflowHostError(f"无法创建筛查现场目录 {screen_paths['directory']!r}：{exc}",
                                    stage=stage) from exc
        screen_started["value"] = True
        started = {
            "start_version": SCREEN_START_VERSION,
            "batch_id": target.name,
            "host_version": HOST_VERSION,
            "operation_kind": OPERATION_RUN_RULE_SCREEN,
            "at_utc": _now_utc(),
            "source_checkpoint_file_sha256": previous_file_sha256,
            "run_bindings_sha256": state["run_bindings_sha256"],
        }
        started_sha = _write_exclusive_json(screen_paths["started_path"], started, stage)

        # 步骤 4：真正调用冻结筛查核心一次（不自行实现规则、不读答案册或测试预期）
        try:
            report = SCREEN_MODULE.screen_sqlite(str(database_path), outputs["load_report"],
                                                 cutoff_date=SCREEN_CUTOFF_DATE)
        except SCREEN_MODULE.RuleScreenBlocked as exc:
            raise WorkflowHostBlocked(f"冻结筛查核心阻断：{exc}", stage=stage) from exc
        except SCREEN_MODULE.RuleScreenError as exc:
            raise WorkflowHostError(f"冻结筛查核心运行失败：{exc}", stage=stage) from exc

        # 步骤 5：独占保存报告并读回，严格等于核心本次实际返回
        report_file_sha = _write_exclusive_json(screen_paths["report_path"], report, stage)
        readback, readback_sha = _read_json_with_bytes(
            screen_paths["report_path"], f"{screen_paths['relative']}/{SCREEN_REPORT}", stage)
        _require(readback_sha == report_file_sha, "screening.report",
                 "写后读回的报告文件哈希与写入结果不一致", stage)
        _require(canonical_json(readback) == canonical_json(report), "screening.report",
                 "写后读回的报告对象与冻结核心本次实际返回不一致", stage)
        report_canonical_sha = canonical_sha256(report)

        # 步骤 6：只核接口协议与来源绑定（不重新实现 R01—R04、不做独立复算）
        _screen_report_protocol(report, outputs["load_report"], database_path, manifest, stage,
                                f"{screen_paths['relative']}/{SCREEN_REPORT}")
        _require(file_sha256(database_path) == database_sha, str(database_path),
                 "只读筛查期间数据库字节发生变化（筛查不得写库）", stage)

        # 步骤 7：artifacts.json 再写 0005.json
        gate2_decision_body_sha = canonical_sha256(
            {key: value for key, value in state["simulated_decisions"][-1].items()
             if key != "decision_sha256"})
        artifacts = {
            "artifacts_version": SCREEN_ARTIFACTS_VERSION,
            "batch_id": target.name,
            "host_version": HOST_VERSION,
            "report_relative": f"{screen_paths['relative']}/{SCREEN_REPORT}",
            "report_file_sha256": report_file_sha,
            "report_canonical_sha256": report_canonical_sha,
            "started_file_sha256": started_sha,
            "previous_checkpoint_file_sha256": previous_file_sha256,
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "normalized_file_sha256": outputs["normalized_file_sha256"],
            "load_report_file_sha256": outputs["load_report_file_sha256"],
            "gate2_artifacts_file_sha256": outputs["artifacts_file_sha256"],
            "normalized_payload_sha256": outputs["load_report"]["normalized_payload_sha256"],
            "database_path": str(database_path),
            "database_sha256": database_sha,
            "rule_core_path": str(SCREENING_CORE_PATH),
            "rule_core_sha256": manifest["bindings"]["code_sha256"]["screen_demo_sqlite"],
            "rule_core_version": SCREEN_MODULE.RULE_CORE_VERSION,
            "rule_sql_sha256": copy.deepcopy(manifest["bindings"]["rule_sql_sha256"]),
            "cutoff_date": SCREEN_CUTOFF_DATE,
            "run_bindings_sha256": state["run_bindings_sha256"],
            "gate2_decision_sha256": gate2_decision_body_sha,
            "created_at_utc": _now_utc(),
        }
        artifacts_sha = _write_exclusive_json(screen_paths["artifacts_path"], artifacts, stage)
        artifacts_readback, artifacts_readback_sha = _read_json_with_bytes(
            screen_paths["artifacts_path"], f"{screen_paths['relative']}/{SCREEN_ARTIFACTS}", stage)
        _require(artifacts_readback_sha == artifacts_sha, "screening.artifacts",
                 "写后读回的 artifacts 文件哈希与写入结果不一致", stage)

        checkpoint = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "revision": 5,
            "previous_file_sha256": previous_file_sha256,
            "batch_id": target.name,
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "workflow": current_workflow,
            "operation": {
                "kind": OPERATION_RUN_RULE_SCREEN,
                "at_utc": _now_utc(),
                "artifacts": copy.deepcopy(artifacts_readback),
                "artifacts_file_sha256": artifacts_sha,
                "report_file_sha256": report_file_sha,
                "report_canonical_sha256": report_canonical_sha,
                "database_sha256": database_sha,
                "started_file_sha256": started_sha,
                "phase_after": state["phase"],
                "bindings_sha256": state["run_bindings_sha256"],
                "report_relative": f"{screen_paths['relative']}/{SCREEN_REPORT}",
                "artifacts_relative": f"{screen_paths['relative']}/{SCREEN_ARTIFACTS}",
            },
        }
        checkpoint_file_hash = _write_exclusive_json(_checkpoint_path(target, 5), checkpoint, stage)

        # 步骤 8：最后一次必要控制器调用之后做最终复测
        context_after = _load_host_context(target, stage=stage)
        measured_after = context_after["measured_bindings"]
        _require(context_after["chain"]["current_file_sha256"] == checkpoint_file_hash, "checkpoint",
                 "写后读回的当前 checkpoint 字节哈希与写入结果不一致（不宣告成功）", stage)
        _require(context_after["chain"]["current"]["revision"] == 5, "checkpoint",
                 "写后当前 checkpoint 必须为 0005", stage)
        try:
            action_after = CONTROLLER_MODULE.check_dev_action(current_workflow,
                                                             CONTROLLER_MODULE.ACTION_SCREEN,
                                                             current_bindings=measured_after)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"写后动作复核被冻结控制器阻断：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"写后动作复核出现意外错误：{exc}", stage=stage) from exc
        gate2_tail_actual = _verify_gate2_tail(target, gate2_expected, stage)
        screen_tail_expected = {
            "started_file_sha256": started_sha,
            "report_file_sha256": report_file_sha,
            "artifacts_file_sha256": artifacts_sha,
            "database_path": str(database_path),
            "database_sha256": database_sha,
        }
        screen_tail_actual = _verify_screen_tail(target, screen_tail_expected, stage)
        # 最终复测必须包含本次写入的 0005 自身字节（预期为本次真实 writer 返回值）
        _require(file_sha256(_checkpoint_path(target, 5)) == checkpoint_file_hash,
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0005.json",
                 f"收尾复测发现 0005 字节在本次写入之后发生变化：期望 {checkpoint_file_hash!r}，"
                 f"实际 {file_sha256(_checkpoint_path(target, 5))!r}", stage)
        bindings_final = _recheck_static_bindings(
            target, measured, stage, when="规则筛查收尾（最后一次控制器动作检查之后）")
        _require(canonical_json(bindings_final) == canonical_json(state["run_bindings"]), "bindings",
                 "收尾实测的静态绑定必须与本 workflow 创建绑定逐项一致", stage)
        for item in chain["checkpoints"]:
            _require(file_sha256(_checkpoint_path(target, item["revision"])) == item["file_sha256"],
                     f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                     "筛查后旧 checkpoint 字节发生变化（不覆盖、不改签）", stage)
        hit_counts = {rule_id: sum(1 for item in report["findings"]
                                   if isinstance(item, dict) and item.get("rule_id") == rule_id)
                      for rule_id in SCREEN_MODULE.RULE_IDS}
        return {
            "host_version": HOST_VERSION,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "status": STATUS_READY,
            "next_step_allowed": False,
            "batch_id": target.name,
            "batch_dir": str(target),
            "phase": state["phase"],
            "state_sha256": current_workflow["state_sha256"],
            "screening_status": "RULE_SCREEN_RECORDED",
            "completed_actions": ["RULE_SCREEN"],
            "action_checked": CONTROLLER_MODULE.ACTION_SCREEN,
            "simulated_action_allowed": action_after["simulation_allowed"],
            "action_reason": action_after["reason"],
            "screening": {
                "report_path": f"{screen_paths['relative']}/{SCREEN_REPORT}",
                "report_file_sha256": report_file_sha,
                "report_canonical_sha256": report_canonical_sha,
                "artifacts_path": f"{screen_paths['relative']}/{SCREEN_ARTIFACTS}",
                "artifacts_file_sha256": artifacts_sha,
                "started_path": f"{screen_paths['relative']}/{SCREEN_START}",
                "started_file_sha256": started_sha,
                "database_path": str(database_path),
                "database_sha256": database_sha,
                "cutoff_date": SCREEN_CUTOFF_DATE,
                "rule_core_version": SCREEN_MODULE.RULE_CORE_VERSION,
                "findings_total": len(report["findings"]),
                "findings_by_rule": hit_counts,
            },
            "checkpoints": [{"path": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                             "revision": item["revision"], "file_sha256": item["file_sha256"]}
                            for item in context_after["chain"]["checkpoints"]],
            "current_checkpoint": context_after["chain"]["current_path"],
            "current_checkpoint_file_sha256": checkpoint_file_hash,
            "previous_checkpoint_file_sha256": previous_file_sha256,
            "bindings_sha256": CONTROLLER_MODULE.canonical_sha256(bindings_final),
            "gate2_tail": {"verified": sorted(gate2_tail_actual.keys()),
                           "artifacts_file_sha256": gate2_tail_actual["artifacts_file_sha256"],
                           "database_sha256": gate2_tail_actual["database_sha256"]},
            "screen_tail": {"verified": sorted(screen_tail_actual.keys())},
            "simulated_decisions": len(state["simulated_decisions"]),
            "real_approvals": 0,
            "note": ("本次实际执行了只读 R01—R04 规则筛查并保存完整线索报告；"
                     "0005 是宿主筛查完成凭证，不是新的控制器批准或新阶段；"
                     "未执行独立复算、事实底稿、AI 或任何真实批准，不自动触发下一步。"),
        }
    except WorkflowHostBlocked as exc:
        _save_screen_failure_if_started(exc)
        raise
    except WorkflowHostError as exc:
        _save_screen_failure_if_started(exc)
        raise
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        mapped = WorkflowHostBlocked(f"[screen] 冻结控制器阻断：{exc}", stage=stage)
        _save_screen_failure_if_started(mapped)
        raise mapped from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        raise WorkflowHostError(f"[screen] 冻结控制器意外错误：{exc}", stage=stage) from exc
    except Exception as exc:  # noqa: BLE001
        mapped = _map_upstream_exception(exc)
        _save_screen_failure_if_started(mapped)
        if mapped is exc:
            raise
        raise mapped from exc


def crosscheck_dev_batch(batch_dir) -> dict:
    """对合法 0005 批次真实运行一次冻结独立复算核心，保存报告与复算凭证 0006。"""
    stage = "crosscheck"
    paths = None
    target = None
    crosscheck_started = {"value": False}

    def _save_failure_if_started(exc: Exception) -> None:
        if target is None or paths is None or not crosscheck_started["value"]:
            return
        if paths["failure_path"].exists():
            return
        try:
            _save_crosscheck_failure(target, getattr(exc, "stage", "") or stage, exc,
                                     _crosscheck_observed_state(target))
        except (WorkflowHostBlocked, WorkflowHostError) as save_exc:
            raise WorkflowHostError(
                f"本次复算失败且失败诊断也未能保存：{exc}（保存失败：{save_exc}）",
                reasons=[str(exc), f"保存失败：{save_exc}"],
                stage=getattr(exc, "stage", "") or stage) from exc

    try:
        target = _resolve_batch_dir(batch_dir, must_exist=True, stage=stage)
        context = _load_host_context(target, stage=stage)
        measured = context["measured_bindings"]
        manifest = context["manifest"]
        chain = context["chain"]
        revision = chain["current"]["revision"]
        if revision != 5:
            raise WorkflowHostBlocked(
                f"当前是第 {revision} 份 checkpoint：独立复算只能在合法的 0005／"
                f"{CROSSCHECK_STATUS_RECORDED} 上执行（早期阶段、停止态与已有 0006 一律拒绝，"
                "不从 phase 字符串推导批准）", stage=stage)
        current_workflow = chain["current"]["payload"]["workflow"]
        state = current_workflow["state"]
        _require(state["phase"] == CONTROLLER_MODULE.PHASE_G2_APPROVED, "workflow.state.phase",
                 f"只接受当前 {CONTROLLER_MODULE.PHASE_G2_APPROVED}，实际 {state['phase']!r}", stage)
        previous_file_sha256 = chain["current_file_sha256"]
        operation = chain["current"]["payload"]["operation"]
        screen_expected = {
            "started_file_sha256": operation["started_file_sha256"],
            "report_file_sha256": operation["report_file_sha256"],
            "artifacts_file_sha256": operation["artifacts_file_sha256"],
        }
        # 0003 的初次材料核验读数保留到复算：不跳过数据库与 Gate2 产物核验
        gate2_expected = dict(chain["gate2_expected"] or {})
        _require(bool(gate2_expected), "chain.gate2_expected",
                 "0005 恢复必须带出初次材料核验读数（复算收尾以它为预期）", stage)
        paths = _crosscheck_paths(target)
        if paths["directory"].exists():
            raise WorkflowHostBlocked(
                f"已有复算现场 {WORKFLOW_DIR}/{CROSSCHECK_DIR}/：本宿主不接管、不覆盖、不清空、"
                "不自动重试；如需重新复算请新建批次", stage=stage)

        try:
            action = CONTROLLER_MODULE.check_dev_action(current_workflow,
                                                        CONTROLLER_MODULE.ACTION_SCREEN,
                                                        current_bindings=measured)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"冻结控制器不允许本次复算动作：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"复算动作检查出现意外错误：{exc}", stage=stage) from exc
        _require(action.get("simulation_allowed") is True, "action.simulation_allowed",
                 f"必须严格为 true（开发态模拟允许，不等于真实批准），"
                 f"实际 {action.get('simulation_allowed')!r}", stage)

        outputs = _read_gate2_outputs(target, stage)
        screen = _read_screen_outputs(target, stage)
        gate2_paths = _gate2_paths(target, stage)
        database_path = gate2_paths["database_path"]
        database_sha = file_sha256(database_path)
        # 本次实读的 Gate2 读数（以 0003 初次核验为预期，键名与 0005 自身的筛查产物分开）
        screen_expected["gate2_normalized_file_sha256"] = outputs["normalized_file_sha256"]
        screen_expected["gate2_load_report_file_sha256"] = outputs["load_report_file_sha256"]
        screen_expected["gate2_artifacts_file_sha256"] = outputs["artifacts_file_sha256"]
        screen_expected["gate2_database_sha256"] = database_sha
        screen_expected["gate2_database_path"] = str(database_path)
        _require(database_sha == outputs["load_report"].get("database_sha256"),
                 f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}.database_sha256",
                 "复算前实读数据库字节必须与既有装载报告声明一致", stage)
        for key, value, field in (
            ("normalized_file_sha256", outputs["normalized_file_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}"),
            ("load_report_file_sha256", outputs["load_report_file_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}"),
            ("artifacts_file_sha256", outputs["artifacts_file_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"),
            ("database_sha256", database_sha, str(database_path)),
        ):
            _require(gate2_expected.get(key) == value, field,
                     f"复算前复测发现本次消费的产物与 0003 初次读数不一致："
                     f"期望 {gate2_expected.get(key)!r}，实际 {value!r}", stage)
        for key, field in (("report_file_sha256", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}"),
                           ("started_file_sha256", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}"),
                           ("artifacts_file_sha256", f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}")):
            _require(screen_expected.get(key) == screen[key], field,
                     f"复算前复测发现筛查产物与 0005 初始声明不一致："
                     f"期望 {screen_expected.get(key)!r}，实际 {screen[key]!r}", stage)
        normalized = outputs["normalized"]
        screening_report = screen["report"]

        try:
            paths["directory"].mkdir(exist_ok=False)
        except FileExistsError as exc:
            raise WorkflowHostBlocked(
                f"复算现场目录已存在，不接管：{paths['relative']}", stage=stage) from exc
        except OSError as exc:
            raise WorkflowHostError(f"无法创建复算现场目录 {paths['directory']!r}：{exc}",
                                    stage=stage) from exc
        crosscheck_started["value"] = True
        started = {
            "start_version": CROSSCHECK_START_VERSION,
            "batch_id": target.name,
            "host_version": HOST_VERSION,
            "operation_kind": OPERATION_RUN_RULE_CROSSCHECK,
            "at_utc": _now_utc(),
            "source_checkpoint_file_sha256": previous_file_sha256,
            "run_bindings_sha256": state["run_bindings_sha256"],
            "normalized_file_sha256": outputs["normalized_file_sha256"],
            "normalized_payload_sha256": canonical_sha256(normalized),
            "screening_report_file_sha256": screen["report_file_sha256"],
            "screening_report_canonical_sha256": canonical_sha256(screening_report),
            "screening_artifacts_file_sha256": screen["artifacts_file_sha256"],
        }
        started_sha = _write_exclusive_json(paths["started_path"], started, stage)

        # 真实调用一次冻结复算核心（只传两个内存对象；不传数据库路径、不读答案册）
        try:
            report = CROSSCHECK_MODULE.verify_rule_facts(normalized, screening_report)
        except CROSSCHECK_MODULE.CrossCheckBlocked as exc:
            raise WorkflowHostBlocked(f"冻结复算核心阻断：{exc}", stage=stage) from exc
        except CROSSCHECK_MODULE.CrossCheckError as exc:
            raise WorkflowHostError(f"冻结复算核心运行失败：{exc}", stage=stage) from exc
        report_file_sha = _write_exclusive_json(paths["report_path"], report, stage)
        readback, readback_sha = _read_json_with_bytes(
            paths["report_path"], f"{paths['relative']}/{CROSSCHECK_REPORT}", stage)
        _require(readback_sha == report_file_sha, "crosscheck.report",
                 "写后读回的报告文件哈希与写入结果不一致", stage)
        _require(canonical_json(readback) == canonical_json(report), "crosscheck.report",
                 "写后读回的报告对象与冻结核心本次实际返回不一致", stage)
        report_canonical_sha = _crosscheck_report_protocol(
            report, normalized, screening_report, stage, f"{paths['relative']}/{CROSSCHECK_REPORT}")
        _require(file_sha256(database_path) == database_sha, str(database_path),
                 "复算期间数据库字节发生变化（复算只能读、不得写库）", stage)
        gate2_decision_body_sha = canonical_sha256(
            {key: value for key, value in state["simulated_decisions"][-1].items()
             if key != "decision_sha256"})
        artifacts = {
            "artifacts_version": CROSSCHECK_ARTIFACTS_VERSION,
            "batch_id": target.name,
            "host_version": HOST_VERSION,
            "operation_kind": OPERATION_RUN_RULE_CROSSCHECK,
            "core_path": str(CROSSCHECK_CORE_PATH),
            "core_sha256": manifest["bindings"]["code_sha256"]["crosscheck_demo_rules"],
            "core_version": CROSSCHECK_MODULE.CROSSCHECK_VERSION,
            "report_relative": f"{paths['relative']}/{CROSSCHECK_REPORT}",
            "report_file_sha256": report_file_sha,
            "report_canonical_sha256": report_canonical_sha,
            "crosscheck_status": CROSSCHECK_STATUS_RECORDED,
            "matched": bool(report["matched"]),
            "started_file_sha256": started_sha,
            "previous_checkpoint_file_sha256": previous_file_sha256,
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "normalized_file_sha256": outputs["normalized_file_sha256"],
            "normalized_payload_sha256": outputs["load_report"]["normalized_payload_sha256"],
            "screening_report_file_sha256": screen["report_file_sha256"],
            "screening_report_canonical_sha256": report["screening_report_sha256"],
            "screening_artifacts_file_sha256": screen["artifacts_file_sha256"],
            "gate2_artifacts_file_sha256": outputs["artifacts_file_sha256"],
            "database_path": str(database_path),
            "database_sha256": database_sha,
            "cutoff_date": SCREEN_CUTOFF_DATE,
            "rule_core_version_checked": SCREEN_MODULE.RULE_CORE_VERSION,
            "run_bindings_sha256": state["run_bindings_sha256"],
            "gate2_decision_sha256": gate2_decision_body_sha,
            "created_at_utc": _now_utc(),
        }
        _require(canonical_sha256(screening_report) == report["screening_report_sha256"],
                 f"{paths['relative']}/{CROSSCHECK_REPORT}.screening_report_sha256",
                 "复算报告声明的筛查报告规范指纹必须等于本次实读筛查报告对象的实际指纹", stage)
        _require(started["screening_report_canonical_sha256"] == report["screening_report_sha256"],
                 f"{paths['relative']}/{CROSSCHECK_START}.screening_report_canonical_sha256",
                 "开始标记的筛查报告规范指纹必须等于本次复算实际消费的报告对象指纹", stage)
        _require(started["normalized_payload_sha256"] == canonical_sha256(normalized),
                 f"{paths['relative']}/{CROSSCHECK_START}.normalized_payload_sha256",
                 "开始标记的 normalized 规范指纹必须等于本次复算实际消费的 normalized 对象指纹",
                 stage)
        if not report["matched"]:
            # MISMATCH 是核心的正常返回：完整报告与差异已保存；保存失败诊断（退出码 1）并使用例
            # 与新进程 status 都能同类拒绝，但不写成功 0006、不修改筛查报告、不继续事实底稿。
            mismatch_exc = WorkflowHostBlocked(
                f"独立复算给出不一致结果（{CROSSCHECK_MISMATCH_RESULT}／"
                f"{CROSSCHECK_MODULE.MISMATCH_STATUS}）："
                f"差异 {report['comparison']['difference_count']} 条，"
                f"未一致维度 {report['comparison']['unmatched_dimensions']!r}；"
                f"完整报告已保存于 {paths['relative']}/{CROSSCHECK_REPORT}。"
                "不自动修改筛查报告、不静默删除差异、不继续事实底稿。", stage=stage)
            report_relative = f"{paths['relative']}/{CROSSCHECK_REPORT}"
            _save_crosscheck_failure(target, stage, mismatch_exc, {
                "kind": "CROSSCHECK_MISMATCH",
                "result": CROSSCHECK_MISMATCH_RESULT,
                "report_relative": report_relative,
                "report_file_sha256": report_file_sha,
                "report_canonical_sha256": report_canonical_sha,
                "batch_status": report["batch_status"],
                "matched": report["matched"],
                "difference_count": report["comparison"]["difference_count"],
                "unmatched_dimensions": report["comparison"]["unmatched_dimensions"],
                "differences": report["differences"],
                "started_file_sha256": started_sha,
                "database_sha256": database_sha,
            })
            raise mismatch_exc

        artifacts_sha = _write_exclusive_json(paths["artifacts_path"], artifacts, stage)
        artifacts_readback, artifacts_readback_sha = _read_json_with_bytes(
            paths["artifacts_path"], f"{paths['relative']}/{CROSSCHECK_ARTIFACTS}", stage)
        _require(artifacts_readback_sha == artifacts_sha, "crosscheck.artifacts",
                 "写后读回的 artifacts 文件哈希与写入结果不一致", stage)

        checkpoint = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "revision": 6,
            "previous_file_sha256": previous_file_sha256,
            "batch_id": target.name,
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "workflow": current_workflow,
            "operation": {
                "kind": OPERATION_RUN_RULE_CROSSCHECK,
                "at_utc": _now_utc(),
                "artifacts": copy.deepcopy(artifacts_readback),
                "artifacts_file_sha256": artifacts_sha,
                "report_file_sha256": report_file_sha,
                "report_canonical_sha256": report_canonical_sha,
                "started_file_sha256": started_sha,
                "database_sha256": database_sha,
                "phase_after": state["phase"],
                "bindings_sha256": state["run_bindings_sha256"],
                "crosscheck_status": CROSSCHECK_STATUS_RECORDED,
                "report_relative": f"{paths['relative']}/{CROSSCHECK_REPORT}",
                "artifacts_relative": f"{paths['relative']}/{CROSSCHECK_ARTIFACTS}",
                "started_relative": f"{paths['relative']}/{CROSSCHECK_START}",
                "core_path": str(CROSSCHECK_CORE_PATH),
                "core_sha256": manifest["bindings"]["code_sha256"]["crosscheck_demo_rules"],
                "core_version": CROSSCHECK_MODULE.CROSSCHECK_VERSION,
                "normalized_file_sha256": outputs["normalized_file_sha256"],
                "screening_report_file_sha256": screen["report_file_sha256"],
                "screening_artifacts_file_sha256": screen["artifacts_file_sha256"],
            },
        }
        checkpoint_file_hash = _write_exclusive_json(_checkpoint_path(target, 6), checkpoint, stage)

        # 最后一次必要控制器调用之后：复测本次消费的全部对象
        context_after = _load_host_context(target, stage=stage)
        measured_after = context_after["measured_bindings"]
        _require(context_after["chain"]["current_file_sha256"] == checkpoint_file_hash, "checkpoint",
                 "写后读回的当前 checkpoint 字节哈希与写入结果不一致（不宣告成功）", stage)
        _require(context_after["chain"]["current"]["revision"] == 6, "checkpoint",
                 "写后当前 checkpoint 必须为 0006", stage)
        try:
            action_after = CONTROLLER_MODULE.check_dev_action(current_workflow,
                                                             CONTROLLER_MODULE.ACTION_SCREEN,
                                                             current_bindings=measured_after)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"写后动作复核被冻结控制器阻断：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"写后动作复核出现意外错误：{exc}", stage=stage) from exc
        _require(file_sha256(_checkpoint_path(target, 5)) == previous_file_sha256,
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0005.json",
                 "复算后 0005 字节发生变化（不覆盖、不改签）", stage)
        crosscheck_tail_expected = {
            "started_file_sha256": started_sha,
            "report_file_sha256": report_file_sha,
            "artifacts_file_sha256": artifacts_sha,
            "database_path": str(database_path),
            "database_sha256": database_sha,
        }
        crosscheck_tail_actual = _verify_crosscheck_tail(target, crosscheck_tail_expected, stage)
        _require(file_sha256(_checkpoint_path(target, 6)) == checkpoint_file_hash,
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0006.json",
                 f"收尾复测发现 0006 字节在本次写入之后发生变化：期望 {checkpoint_file_hash!r}，"
                 f"实际 {file_sha256(_checkpoint_path(target, 6))!r}", stage)
        _verify_gate2_tail(target, gate2_expected, stage)
        _verify_screen_tail(target, screen_expected, stage)
        bindings_final = _recheck_static_bindings(
            target, measured, stage, when="独立复算收尾（最后一次控制器动作检查之后）")
        _require(canonical_json(bindings_final) == canonical_json(state["run_bindings"]), "bindings",
                 "收尾实测的静态绑定必须与本 workflow 创建绑定逐项一致", stage)
        for item in chain["checkpoints"]:
            _require(file_sha256(_checkpoint_path(target, item["revision"])) == item["file_sha256"],
                     f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                     "复算后旧 checkpoint 字节发生变化（不覆盖、不改签）", stage)
        return {
            "host_version": HOST_VERSION,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "status": STATUS_READY,
            "next_step_allowed": False,
            "batch_id": target.name,
            "batch_dir": str(target),
            "phase": state["phase"],
            "state_sha256": current_workflow["state_sha256"],
            "crosscheck_status": CROSSCHECK_STATUS_RECORDED,
            "crosscheck_matched": bool(report["matched"]),
            "completed_actions": ["RULE_SCREEN", "RULE_CROSSCHECK"],
            "action_checked": CONTROLLER_MODULE.ACTION_SCREEN,
            "simulated_action_allowed": action_after["simulation_allowed"],
            "action_reason": action_after["reason"],
            "crosscheck": {
                "report_path": f"{paths['relative']}/{CROSSCHECK_REPORT}",
                "report_file_sha256": report_file_sha,
                "report_canonical_sha256": report_canonical_sha,
                "artifacts_path": f"{paths['relative']}/{CROSSCHECK_ARTIFACTS}",
                "artifacts_file_sha256": artifacts_sha,
                "started_path": f"{paths['relative']}/{CROSSCHECK_START}",
                "started_file_sha256": started_sha,
                "core_path": str(CROSSCHECK_CORE_PATH),
                "core_version": CROSSCHECK_MODULE.CROSSCHECK_VERSION,
                "rule_recomputed_counts": report["rule_recomputed_counts"],
                "difference_count": report["comparison"]["difference_count"],
                "dimensions": {name: report["comparison"]["dimensions"][name]
                               for name in CROSSCHECK_DIMENSIONS},
            },
            "checkpoints": [{"path": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                             "revision": item["revision"], "file_sha256": item["file_sha256"]}
                            for item in context_after["chain"]["checkpoints"]],
            "current_checkpoint": context_after["chain"]["current_path"],
            "current_checkpoint_file_sha256": checkpoint_file_hash,
            "previous_checkpoint_file_sha256": previous_file_sha256,
            "bindings_sha256": CONTROLLER_MODULE.canonical_sha256(bindings_final),
            "crosscheck_tail": {"verified": sorted(crosscheck_tail_actual.keys())},
            "simulated_decisions": len(state["simulated_decisions"]),
            "real_approvals": 0,
            "note": ("本次实际执行了冻结独立复算核心 verify_rule_facts 并保存完整复核报告；"
                     "0006 是宿主复算完成凭证，不是新的控制器批准或新阶段，"
                     "也不代表整个 SCREEN_AND_BUILD_FACTS 完成；未执行事实底稿、AI 或任何真实批准。"),
        }
    except WorkflowHostBlocked as exc:
        _save_failure_if_started(exc)
        raise
    except WorkflowHostError as exc:
        _save_failure_if_started(exc)
        raise
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        mapped = WorkflowHostBlocked(f"[crosscheck] 冻结控制器阻断：{exc}", stage=stage)
        _save_failure_if_started(mapped)
        raise mapped from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        raise WorkflowHostError(f"[crosscheck] 冻结控制器意外错误：{exc}", stage=stage) from exc
    except Exception as exc:  # noqa: BLE001
        mapped = _map_upstream_exception(exc, stage=stage)
        if not hasattr(mapped, "original_exception_chain"):
            mapped.original_exception_chain = _exception_chain(exc)  # type: ignore[attr-defined]
        _save_failure_if_started(mapped)
        if mapped is exc:
            raise
        raise mapped from exc


def build_dev_fact_packet(batch_dir) -> dict:
    """对合法 0006 批次真实运行一次冻结事实底稿核心，保存 JSON＋Markdown 并追加复算后的 0007。"""
    stage = "fact_packet"
    paths = None
    target = None
    fact_started = {"value": False}

    def _save_failure_if_started(exc: Exception) -> None:
        if target is None or paths is None or not fact_started["value"]:
            return
        if paths["failure_path"].exists():
            return
        try:
            _save_fact_packet_failure(target, getattr(exc, "stage", "") or stage, exc,
                                      _fact_packet_observed_state(target))
        except (WorkflowHostBlocked, WorkflowHostError) as save_exc:
            raise WorkflowHostError(
                f"本次事实底稿失败且失败诊断也未能保存：{exc}（保存失败：{save_exc}）",
                reasons=[str(exc), f"保存失败：{save_exc}"],
                stage=getattr(exc, "stage", "") or stage) from exc

    try:
        target = _resolve_batch_dir(batch_dir, must_exist=True, stage=stage)
        context = _load_host_context(target, stage=stage)
        measured = context["measured_bindings"]
        manifest = context["manifest"]
        chain = context["chain"]
        revision = chain["current"]["revision"]
        if revision != 6:
            raise WorkflowHostBlocked(
                f"当前是第 {revision} 份 checkpoint：事实底稿只能在合法的 0006／"
                f"{CROSSCHECK_STATUS_RECORDED} 上构建（早期阶段、停止态与已有 0007 一律拒绝，"
                "不从 phase 字符串推导批准）", stage=stage)
        current_workflow = chain["current"]["payload"]["workflow"]
        state = current_workflow["state"]
        _require(state["phase"] == CONTROLLER_MODULE.PHASE_G2_APPROVED, "workflow.state.phase",
                 f"只接受当前 {CONTROLLER_MODULE.PHASE_G2_APPROVED}，实际 {state['phase']!r}", stage)
        previous_file_sha256 = chain["current_file_sha256"]
        screen_expected = dict(chain["screen_expected"] or {})
        upstream = dict(chain["crosscheck_expected"] or {})
        _require(bool(screen_expected) and bool(upstream), "chain.expected",
                 "0006 恢复必须带出筛查／复算的初次核验读数（事实底稿以它为上游预期）", stage)
        paths = _fact_packet_paths(target)
        if paths["directory"].exists():
            raise WorkflowHostBlocked(
                f"已有事实底稿现场 {WORKFLOW_DIR}/{FACT_PACKET_DIR}/：本宿主不接管、不覆盖、不清空、"
                "不自动重试；如需重新构建请新建批次", stage=stage)

        try:
            action = CONTROLLER_MODULE.check_dev_action(current_workflow,
                                                        CONTROLLER_MODULE.ACTION_SCREEN,
                                                        current_bindings=measured)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"冻结控制器不允许本次事实底稿动作：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"事实底稿动作检查出现意外错误：{exc}", stage=stage) from exc
        _require(action.get("simulation_allowed") is True, "action.simulation_allowed",
                 f"必须严格为 true（开发态模拟允许，不等于真实批准），"
                 f"实际 {action.get('simulation_allowed')!r}", stage)

        # 三个输入：对象与文件字节哈希来自同一次读取缓冲
        gate2_outputs = _read_gate2_outputs(target, stage)
        screen = _read_screen_outputs(target, stage)
        crosscheck = _read_crosscheck_outputs(target, stage)
        gate2_paths = _gate2_paths(target, stage)
        database_path = gate2_paths["database_path"]
        database_sha = file_sha256(database_path)
        _require(database_sha == gate2_outputs["load_report"].get("database_sha256"),
                 f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}.database_sha256",
                 "构建前实读数据库字节必须与既有装载报告声明一致", stage)
        # 与已核验的前序凭证比较（不用后来读到的不同版本替换初始预期）
        for key, value, field in (
            ("gate2_normalized_file_sha256", gate2_outputs["normalized_file_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}"),
            ("gate2_load_report_file_sha256", gate2_outputs["load_report_file_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}"),
            ("gate2_artifacts_file_sha256", gate2_outputs["artifacts_file_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"),
            ("gate2_database_sha256", database_sha, str(database_path)),
        ):
            _require(screen_expected.get(key) == value, field,
                     f"构建前复测发现本次消费的产物与 0003 初次读数不一致："
                     f"期望 {screen_expected.get(key)!r}，实际 {value!r}", stage)
        for key, value, field in (
            ("screening_started_file_sha256", screen["started_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}"),
            ("screening_report_file_sha256", screen["report_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}"),
            ("screening_artifacts_file_sha256", screen["artifacts_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}"),
        ):
            _require(upstream.get(key) == value, field,
                     f"构建前复测发现筛查产物与 0005 初始声明不一致："
                     f"期望 {upstream.get(key)!r}，实际 {value!r}", stage)
        for key, value, field in (
            ("crosscheck_started_file_sha256", crosscheck["started_file_sha256"],
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_START}"),
            ("crosscheck_report_file_sha256", crosscheck["report_file_sha256"],
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}"),
            ("crosscheck_artifacts_file_sha256", crosscheck["artifacts_file_sha256"],
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}"),
        ):
            _require(upstream.get(key) == value, field,
                     f"构建前复测发现复算产物与 0006 初始声明不一致："
                     f"期望 {upstream.get(key)!r}，实际 {value!r}", stage)
        # 完整 MATCHED 十维度前提：不能只看 matched 标志
        crosscheck_report = crosscheck["report"]
        _require(crosscheck_report.get("matched") is True, "crosscheck_report.matched",
                 f"事实底稿前提要求复算为 MATCHED，实际 {crosscheck_report.get('matched')!r}", stage)
        _require(crosscheck_report.get("batch_status") == CROSSCHECK_MODULE.MATCHED_STATUS,
                 "crosscheck_report.batch_status",
                 f"必须是 {CROSSCHECK_MODULE.MATCHED_STATUS}", stage)
        _require(crosscheck_report.get("differences") == [], "crosscheck_report.differences",
                 "MATCHED 前提要求差异为空", stage)
        dimensions = (crosscheck_report.get("comparison") or {}).get("dimensions") or {}
        _require(set(dimensions) == set(CROSSCHECK_DIMENSIONS), "crosscheck_report.comparison.dimensions",
                 f"十维度必须齐备，实际 {sorted(dimensions)}", stage)
        for name in CROSSCHECK_DIMENSIONS:
            item = dimensions[name]
            _require(item.get("executed") is True and item.get("matched") is True
                     and isinstance(item.get("difference_count"), int)
                     and not isinstance(item.get("difference_count"), bool)
                     and item.get("difference_count") == 0,
                     f"crosscheck_report.comparison.dimensions.{name}",
                     f"前提要求每个维度 executed/matched 严格 true 且差异数为严格整数 0，实际 {item}",
                     stage)
        _require((crosscheck_report.get("comparison") or {}).get("difference_count") == 0,
                 "crosscheck_report.comparison.difference_count", "前提要求差异数为 0", stage)

        normalized = gate2_outputs["normalized"]
        screening_report = screen["report"]

        try:
            paths["directory"].mkdir(exist_ok=False)
        except FileExistsError as exc:
            raise WorkflowHostBlocked(
                f"事实底稿现场目录已存在，不接管：{paths['relative']}", stage=stage) from exc
        except OSError as exc:
            raise WorkflowHostError(f"无法创建事实底稿现场目录 {paths['directory']!r}：{exc}",
                                    stage=stage) from exc
        fact_started["value"] = True
        started = {
            "start_version": FACT_PACKET_START_VERSION,
            "batch_id": target.name,
            "host_version": HOST_VERSION,
            "operation_kind": OPERATION_BUILD_FACT_PACKET,
            "at_utc": _now_utc(),
            "source_checkpoint_file_sha256": previous_file_sha256,
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "run_bindings_sha256": state["run_bindings_sha256"],
            "core_path": str(FACT_PACKET_CORE_PATH),
            "core_sha256": manifest["bindings"]["code_sha256"]["build_demo_fact_packet"],
            "core_version": FACT_PACKET_MODULE.PACKET_VERSION,
            "normalized_file_sha256": gate2_outputs["normalized_file_sha256"],
            "normalized_payload_sha256": canonical_sha256(normalized),
            "screening_report_file_sha256": screen["report_file_sha256"],
            "screening_report_canonical_sha256": canonical_sha256(screening_report),
            "crosscheck_report_file_sha256": crosscheck["report_file_sha256"],
            "crosscheck_report_canonical_sha256": canonical_sha256(crosscheck_report),
            "database_path": str(database_path),
            "database_sha256": database_sha,
        }
        started_sha = _write_exclusive_json(paths["started_path"], started, stage)

        # 调用前保留三个真实输入的经典指纹（调用后与公开返回前按同一对象引用核对）
        input_fingerprints_before = {
            "normalized": canonical_sha256(normalized),
            "screening_report": canonical_sha256(screening_report),
            "crosscheck_report": canonical_sha256(crosscheck_report),
        }

        # 真实调用一次冻结事实底稿核心（只传三个内存对象）
        try:
            result = FACT_PACKET_MODULE.build_fact_packet(normalized, screening_report,
                                                          crosscheck_report)
        except FACT_PACKET_MODULE.FactPacketBlocked as exc:
            raise WorkflowHostBlocked(f"冻结事实底稿核心阻断：{exc}", stage=stage) from exc
        except FACT_PACKET_MODULE.FactPacketError as exc:
            raise WorkflowHostError(f"冻结事实底稿核心运行失败：{exc}", stage=stage) from exc
        _require(isinstance(result, dict) and set(result.keys()) == {"packet", "packet_sha256",
                                                                    "markdown"},
                 "fact_packet.result",
                 f"核心必须恰返回 packet/packet_sha256/markdown，实际 {sorted(result) if isinstance(result, dict) else type(result).__name__}",
                 stage)
        packet = result["packet"]
        packet_sha256 = result["packet_sha256"]
        markdown = result["markdown"]
        _require(isinstance(packet, dict), "fact_packet.packet",
                 f"packet 必须是对象，实际 {type(packet).__name__}", stage)
        _require(isinstance(packet_sha256, str) and len(packet_sha256) == 64,
                 "fact_packet.packet_sha256",
                 f"必须是 64 位十六进制字符串，实际 {packet_sha256!r}", stage)
        _require(packet_sha256 == canonical_sha256(packet), "fact_packet.packet_sha256",
                 "必须等于 packet 对象的规范 JSON SHA-256（不得是文件字节哈希）", stage)
        input_fingerprints_after = {
            "normalized": canonical_sha256(normalized),
            "screening_report": canonical_sha256(screening_report),
            "crosscheck_report": canonical_sha256(crosscheck_report),
        }
        _require(canonical_json(input_fingerprints_before) == canonical_json(input_fingerprints_after),
                 "fact_packet.inputs",
                 "事实底稿核心不得修改传入的三个输入对象（调用前后规范指纹必须一致）", stage)

        upstream_expected = {
            "normalized_payload_sha256": canonical_sha256(normalized),
            "screening_report_canonical_sha256": canonical_sha256(screening_report),
            "crosscheck_report_canonical_sha256": canonical_sha256(crosscheck_report),
            "workbook_sha256": ((normalized.get("source") or {}).get("input_sha256")
                                or (gate2_outputs["load_report"].get("run_metadata") or {}).get(
                                    "input_sha256")),
        }
        protocol = _packet_protocol_report(packet, upstream_expected, stage,
                                           f"{paths['relative']}/{FACT_PACKET_JSON}")
        # summary 形状与数量必须符合已核验的筛查报告
        expected_counts = {rule: sum(1 for item in screening_report["findings"]
                                     if item.get("rule_id") == rule)
                           for rule in FACT_PACKET_MODULE.RULE_IDS}
        _require(canonical_json(protocol["rule_counts"]) == canonical_json(expected_counts),
                 f"{paths['relative']}/{FACT_PACKET_JSON}.summary.rule_counts",
                 f"规则分布必须符合已核验筛查报告 {expected_counts}，实际 {protocol['rule_counts']}",
                 stage)
        _require(protocol["total_findings"] == len(screening_report["findings"]),
                 f"{paths['relative']}/{FACT_PACKET_JSON}.summary.total_findings",
                 "线索总数必须等于已核验筛查报告的 findings 条数", stage)
        _require(protocol["r02_overpayment_total_cents"]
                 == screening_report["statistics"].get("r02_overpayment_total_cents"),
                 f"{paths['relative']}/{FACT_PACKET_JSON}.summary.r02_overpayment_total_cents",
                 "R02 超额合计必须与已核验筛查报告一致", stage)

        # 独占保存 JSON 与 Markdown，并实读验证
        packet_file_sha = _write_exclusive_json(paths["packet_path"], packet, stage)
        packet_readback, packet_readback_sha = _read_json_with_bytes(
            paths["packet_path"], f"{paths['relative']}/{FACT_PACKET_JSON}", stage)
        _require(packet_readback_sha == packet_file_sha, f"{paths['relative']}/{FACT_PACKET_JSON}",
                 "写后读回的 packet 文件哈希与写入结果不一致", stage)
        _require(canonical_json(packet_readback) == canonical_json(packet),
                 f"{paths['relative']}/{FACT_PACKET_JSON}",
                 "写后读回的 packet 与该次真实返回的 packet 不严格规范 JSON 相等", stage)
        _require(canonical_sha256(packet_readback) == packet_sha256,
                 f"{paths['relative']}/{FACT_PACKET_JSON}",
                 "写后读回 packet 的规范指纹必须等于核心返回的 packet_sha256", stage)
        markdown_file_sha = _write_exclusive_markdown(paths["markdown_path"], markdown, stage)
        markdown_size = paths["markdown_path"].stat().st_size
        _require(file_sha256(database_path) == database_sha, str(database_path),
                 "事实底稿构建期间数据库字节发生变化（本层只能读、不得写库）", stage)

        gate2_decision_body_sha = canonical_sha256(
            {key: value for key, value in state["simulated_decisions"][-1].items()
             if key != "decision_sha256"})
        artifacts = {
            "artifacts_version": FACT_PACKET_ARTIFACTS_VERSION,
            "batch_id": target.name,
            "host_version": HOST_VERSION,
            "operation_kind": OPERATION_BUILD_FACT_PACKET,
            "core_path": str(FACT_PACKET_CORE_PATH),
            "core_sha256": manifest["bindings"]["code_sha256"]["build_demo_fact_packet"],
            "core_version": FACT_PACKET_MODULE.PACKET_VERSION,
            "packet_version": packet["packet_version"],
            "fact_packet_status": FACT_PACKET_STATUS_RECORDED,
            "matched": True,
            "run_bindings_sha256": state["run_bindings_sha256"],
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "previous_checkpoint_file_sha256": previous_file_sha256,
            "previous_checkpoint_relative": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0006.json",
            "normalized_file_sha256": gate2_outputs["normalized_file_sha256"],
            "normalized_payload_sha256": canonical_sha256(normalized),
            "screening_report_file_sha256": screen["report_file_sha256"],
            "screening_report_canonical_sha256": canonical_sha256(screening_report),
            "crosscheck_report_file_sha256": crosscheck["report_file_sha256"],
            "crosscheck_report_canonical_sha256": canonical_sha256(crosscheck_report),
            "screening_started_file_sha256": screen["started_file_sha256"],
            "screening_artifacts_file_sha256": screen["artifacts_file_sha256"],
            "crosscheck_started_file_sha256": crosscheck["started_file_sha256"],
            "crosscheck_artifacts_file_sha256": crosscheck["artifacts_file_sha256"],
            "gate2_normalized_file_sha256": gate2_outputs["normalized_file_sha256"],
            "gate2_load_report_file_sha256": gate2_outputs["load_report_file_sha256"],
            "gate2_artifacts_file_sha256": gate2_outputs["artifacts_file_sha256"],
            "database_path": str(database_path),
            "database_sha256": database_sha,
            "gate2_decision_sha256": gate2_decision_body_sha,
            "period": {"period_start": FACT_PACKET_MODULE.PERIOD_START,
                       "period_end": FACT_PACKET_MODULE.PERIOD_END},
            "cutoff_date": FACT_PACKET_MODULE.CUTOFF_DATE,
            "started_relative": f"{paths['relative']}/{FACT_PACKET_START}",
            "started_file_sha256": started_sha,
            "packet_relative": f"{paths['relative']}/{FACT_PACKET_JSON}",
            "packet_file_sha256": packet_file_sha,
            "packet_sha256": packet_sha256,
            "markdown_relative": f"{paths['relative']}/{FACT_PACKET_MARKDOWN}",
            "markdown_file_sha256": markdown_file_sha,
            "findings_total": protocol["total_findings"],
            "rule_counts": protocol["rule_counts"],
            "markdown_bytes": markdown_size,
            "created_at_utc": _now_utc(),
        }
        artifacts_sha = _write_exclusive_json(paths["artifacts_path"], artifacts, stage)
        artifacts_readback, artifacts_readback_sha = _read_json_with_bytes(
            paths["artifacts_path"], f"{paths['relative']}/{FACT_PACKET_ARTIFACTS}", stage)
        _require(artifacts_readback_sha == artifacts_sha,
                 f"{paths['relative']}/{FACT_PACKET_ARTIFACTS}",
                 "写后读回的 artifacts 文件哈希与写入结果不一致", stage)

        checkpoint = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "revision": 7,
            "previous_file_sha256": previous_file_sha256,
            "batch_id": target.name,
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "workflow": current_workflow,
            "operation": {
                "kind": OPERATION_BUILD_FACT_PACKET,
                "at_utc": _now_utc(),
                "artifacts": copy.deepcopy(artifacts_readback),
                "artifacts_file_sha256": artifacts_sha,
                "packet_file_sha256": packet_file_sha,
                "packet_sha256": packet_sha256,
                "markdown_file_sha256": markdown_file_sha,
                "started_file_sha256": started_sha,
                "database_sha256": database_sha,
                "phase_after": state["phase"],
                "bindings_sha256": state["run_bindings_sha256"],
                "fact_packet_status": FACT_PACKET_STATUS_RECORDED,
                "packet_relative": f"{paths['relative']}/{FACT_PACKET_JSON}",
                "markdown_relative": f"{paths['relative']}/{FACT_PACKET_MARKDOWN}",
                "artifacts_relative": f"{paths['relative']}/{FACT_PACKET_ARTIFACTS}",
                "started_relative": f"{paths['relative']}/{FACT_PACKET_START}",
                "core_path": str(FACT_PACKET_CORE_PATH),
                "core_sha256": manifest["bindings"]["code_sha256"]["build_demo_fact_packet"],
                "core_version": FACT_PACKET_MODULE.PACKET_VERSION,
                "packet_version": packet["packet_version"],
                "normalized_file_sha256": gate2_outputs["normalized_file_sha256"],
                "screening_report_file_sha256": screen["report_file_sha256"],
                "crosscheck_report_file_sha256": crosscheck["report_file_sha256"],
                "previous_checkpoint_file_sha256": previous_file_sha256,
            },
        }
        checkpoint_file_hash = _write_exclusive_json(_checkpoint_path(target, 7), checkpoint, stage)

        # 最后一次必要控制器调用与最后一次数据消费之后：复测全部本次消费对象
        context_after = _load_host_context(target, stage=stage)
        measured_after = context_after["measured_bindings"]
        _require(context_after["chain"]["current_file_sha256"] == checkpoint_file_hash, "checkpoint",
                 "写后读回的当前 checkpoint 字节哈希与写入结果不一致（不宣告成功）", stage)
        _require(context_after["chain"]["current"]["revision"] == 7, "checkpoint",
                 "写后当前 checkpoint 必须为 0007", stage)
        try:
            action_after = CONTROLLER_MODULE.check_dev_action(current_workflow,
                                                             CONTROLLER_MODULE.ACTION_SCREEN,
                                                             current_bindings=measured_after)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"写后动作复核被冻结控制器阻断：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"写后动作复核出现意外错误：{exc}", stage=stage) from exc
        _require(file_sha256(_checkpoint_path(target, 6)) == previous_file_sha256,
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0006.json",
                 "底稿构建后 0006 字节发生变化（不覆盖、不改签）", stage)
        fact_tail_expected = {
            "started_file_sha256": started_sha,
            "packet_file_sha256": packet_file_sha,
            "markdown_file_sha256": markdown_file_sha,
            "artifacts_file_sha256": artifacts_sha,
            "database_path": str(database_path),
            "database_sha256": database_sha,
        }
        fact_tail_actual = _verify_fact_packet_tail(target, fact_tail_expected, stage)
        _require(file_sha256(_checkpoint_path(target, 7)) == checkpoint_file_hash,
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0007.json",
                 f"收尾复测发现 0007 字节在本次写入之后发生变化：期望 {checkpoint_file_hash!r}，"
                 f"实际 {file_sha256(_checkpoint_path(target, 7))!r}", stage)
        upstream_tail_expected = {
            "screening_started_file_sha256": screen["started_file_sha256"],
            "screening_report_file_sha256": screen["report_file_sha256"],
            "screening_artifacts_file_sha256": screen["artifacts_file_sha256"],
            "crosscheck_started_file_sha256": crosscheck["started_file_sha256"],
            "crosscheck_report_file_sha256": crosscheck["report_file_sha256"],
            "crosscheck_artifacts_file_sha256": crosscheck["artifacts_file_sha256"],
            "gate2_normalized_file_sha256": gate2_outputs["normalized_file_sha256"],
            "gate2_load_report_file_sha256": gate2_outputs["load_report_file_sha256"],
            "gate2_artifacts_file_sha256": gate2_outputs["artifacts_file_sha256"],
            "database_sha256": database_sha,
        }
        # 三输入与上游产物在收尾时复测（不消费新版本生成摘要）
        for key, value, field in (
            ("screening_started_file_sha256", file_sha256(target / "workflow" / SCREEN_DIR
                                                          / SCREEN_START),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}"),
            ("screening_report_file_sha256", file_sha256(target / "workflow" / SCREEN_DIR
                                                         / SCREEN_REPORT),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}"),
            ("screening_artifacts_file_sha256", file_sha256(target / "workflow" / SCREEN_DIR
                                                            / SCREEN_ARTIFACTS),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}"),
            ("crosscheck_started_file_sha256", file_sha256(target / "workflow" / CROSSCHECK_DIR
                                                           / CROSSCHECK_START),
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_START}"),
            ("crosscheck_report_file_sha256", file_sha256(target / "workflow" / CROSSCHECK_DIR
                                                          / CROSSCHECK_REPORT),
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}"),
            ("crosscheck_artifacts_file_sha256", file_sha256(target / "workflow" / CROSSCHECK_DIR
                                                             / CROSSCHECK_ARTIFACTS),
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}"),
            # Gate2 三份 JSON 与数据库必须**实读磁盘**后与操作开始时绑定的同缓冲读数比较；
            # 不得用先前的 gate2_outputs 缓存值同它自身相等充当复测。
            ("gate2_normalized_file_sha256",
             file_sha256(_gate2_dir(target) / GATE2_NORMALIZED),
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}"),
            ("gate2_load_report_file_sha256",
             file_sha256(_gate2_dir(target) / GATE2_LOAD_REPORT),
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}"),
            ("gate2_artifacts_file_sha256",
             file_sha256(_gate2_dir(target) / GATE2_ARTIFACTS),
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"),
            ("database_sha256", file_sha256(database_path), str(database_path)),
        ):
            _require(upstream_tail_expected[key] == value, field,
                     f"收尾复测发现上游材料发生变化：期望（操作开始时同缓冲读取）"
                     f"{upstream_tail_expected[key]!r}，实际 {value!r}", stage)
        # Gate2 三份 JSON 的对象级复测：实读后必须与本次消费的对象同值（同缓冲来源）
        gate2_after = _read_gate2_outputs(target, stage)
        for key, expected_value in (
            ("normalized_file_sha256", gate2_outputs["normalized_file_sha256"]),
            ("load_report_file_sha256", gate2_outputs["load_report_file_sha256"]),
            ("artifacts_file_sha256", gate2_outputs["artifacts_file_sha256"]),
        ):
            _require(gate2_after[key] == expected_value, f"{WORKFLOW_DIR}/{GATE2_DIR}",
                     f"收尾实读发现 Gate2 材料文件字节与本次消费读数不一致（{key}）："
                     f"期望 {expected_value!r}，实际 {gate2_after[key]!r}", stage)
        _require(canonical_json(gate2_after["normalized"])
                 == canonical_json(gate2_outputs["normalized"]),
                 f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}",
                 "收尾实读发现 normalized 对象与本次消费对象不一致", stage)
        _require(canonical_json(gate2_after["load_report"])
                 == canonical_json(gate2_outputs["load_report"]),
                 f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}",
                 "收尾实读发现 load_report 对象与本次消费对象不一致", stage)
        _require(canonical_json(gate2_after["artifacts"])
                 == canonical_json(gate2_outputs["artifacts"]),
                 f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}",
                 "收尾实读发现 Gate2 artifacts 对象与本次消费对象不一致", stage)
        _require(file_sha256(_host_manifest_path(target)) == context["manifest_file_sha256"],
                 f"{WORKFLOW_DIR}/{HOST_MANIFEST_NAME}",
                 "收尾复测发现宿主清单字节发生变化："
                 f"期望（初始读取）{context['manifest_file_sha256']!r}，"
                 f"实际 {file_sha256(_host_manifest_path(target))!r}", stage)
        _verify_screen_tail(target, {
            "started_file_sha256": screen["started_file_sha256"],
            "report_file_sha256": screen["report_file_sha256"],
            "artifacts_file_sha256": screen["artifacts_file_sha256"],
            "database_path": str(database_path),
            "database_sha256": database_sha,
        }, stage)
        bindings_final = _recheck_static_bindings(
            target, measured, stage, when="事实底稿收尾（最后一次控制器动作检查之后）")
        _require(canonical_json(bindings_final) == canonical_json(state["run_bindings"]), "bindings",
                 "收尾实测的静态绑定必须与本 workflow 创建绑定逐项一致", stage)
        for item in chain["checkpoints"]:
            _require(file_sha256(_checkpoint_path(target, item["revision"])) == item["file_sha256"],
                     f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                     "底稿构建后旧 checkpoint 字节发生变化（不覆盖、不改签）", stage)
        _require(canonical_json(input_fingerprints_before)
                 == canonical_json({"normalized": canonical_sha256(normalized),
                                    "screening_report": canonical_sha256(screening_report),
                                    "crosscheck_report": canonical_sha256(crosscheck_report)}),
                 "fact_packet.inputs",
                 "公开操作返回前复核：三个输入对象的规范指纹必须与调用前一致", stage)
        return {
            "host_version": HOST_VERSION,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "status": STATUS_READY,
            "next_step_allowed": False,
            "batch_id": target.name,
            "batch_dir": str(target),
            "phase": state["phase"],
            "state_sha256": current_workflow["state_sha256"],
            "screening_status": SCREEN_STATUS_RECORDED,
            "crosscheck_status": CROSSCHECK_STATUS_RECORDED,
            "fact_packet_status": FACT_PACKET_STATUS_RECORDED,
            "completed_actions": ["RULE_SCREEN", "RULE_CROSSCHECK", "FACT_PACKET"],
            "action_checked": CONTROLLER_MODULE.ACTION_SCREEN,
            "simulated_action_allowed": action_after["simulation_allowed"],
            "action_reason": action_after["reason"],
            "fact_packet": {
                "packet_path": f"{paths['relative']}/{FACT_PACKET_JSON}",
                "packet_file_sha256": packet_file_sha,
                "packet_sha256": packet_sha256,
                "markdown_path": f"{paths['relative']}/{FACT_PACKET_MARKDOWN}",
                "markdown_file_sha256": markdown_file_sha,
                "markdown_bytes": markdown_size,
                "artifacts_path": f"{paths['relative']}/{FACT_PACKET_ARTIFACTS}",
                "artifacts_file_sha256": artifacts_sha,
                "started_path": f"{paths['relative']}/{FACT_PACKET_START}",
                "started_file_sha256": started_sha,
                "core_path": str(FACT_PACKET_CORE_PATH),
                "core_version": FACT_PACKET_MODULE.PACKET_VERSION,
                "packet_version": packet["packet_version"],
                "findings_total": protocol["total_findings"],
                "rule_counts": protocol["rule_counts"],
                "r02_overpayment_total_cents": protocol["r02_overpayment_total_cents"],
                "input_fingerprints_before": input_fingerprints_before,
                "input_fingerprints_after": input_fingerprints_after,
            },
            "checkpoints": [{"path": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                             "revision": item["revision"], "file_sha256": item["file_sha256"]}
                            for item in context_after["chain"]["checkpoints"]],
            "current_checkpoint": context_after["chain"]["current_path"],
            "current_checkpoint_file_sha256": checkpoint_file_hash,
            "previous_checkpoint_file_sha256": previous_file_sha256,
            "bindings_sha256": CONTROLLER_MODULE.canonical_sha256(bindings_final),
            "fact_packet_tail": {"verified": sorted(fact_tail_actual.keys())},
            "simulated_decisions": len(state["simulated_decisions"]),
            "real_approvals": 0,
            "note": ("本次实际执行了冻结事实底稿核心 build_fact_packet 并保存完整 JSON 事实包与对应 "
                     "Markdown；0007 只表示事实底稿已持久化，不代表审计完成、审计通过或底稿已批准；"
                     "未执行 AI、未保存或预填人类判断、未建立正式契约或真实批准。"),
        }
    except WorkflowHostBlocked as exc:
        _save_failure_if_started(exc)
        raise
    except WorkflowHostError as exc:
        _save_failure_if_started(exc)
        raise
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        mapped = WorkflowHostBlocked(f"[fact_packet] 冻结控制器阻断：{exc}", stage=stage)
        _save_failure_if_started(mapped)
        raise mapped from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        raise WorkflowHostError(f"[fact_packet] 冻结控制器意外错误：{exc}", stage=stage) from exc
    except Exception as exc:  # noqa: BLE001
        mapped = _map_upstream_exception(exc, stage=stage)
        if not hasattr(mapped, "original_exception_chain"):
            mapped.original_exception_chain = _exception_chain(exc)  # type: ignore[attr-defined]
        _save_failure_if_started(mapped)
        if mapped is exc:
            raise
        raise mapped from exc


# ---------------------------------------------------------------------------
# record-simulated-initial-judgment
# ---------------------------------------------------------------------------


def _initial_judgment_preflight(submission, batch_id: str, packet_sha256: str,
                               state: dict, stage: str) -> None:
    """建目录前的轻量预检：只查本层能独立判断的绑定与身份/事件唯一性。

    文本、备注、时间与协议细节仍由冻结纯核心负责，宿主不重写判断校验算法、不补默认字段。
    """
    _require(isinstance(submission, dict), "submission",
             f"必须是对象，实际 {type(submission).__name__}", stage)
    _require(isinstance(submission.get("batch_id"), str) and submission.get("batch_id") == batch_id,
             "submission.batch_id",
             f"必须等于本次批次 {batch_id!r}，实际 {submission.get('batch_id')!r}", stage)
    _require(submission.get("fact_packet_sha256") == packet_sha256,
             "submission.fact_packet_sha256",
             f"必须等于 0007 已核验的事实包规范指纹 {packet_sha256!r}，"
             f"实际 {submission.get('fact_packet_sha256')!r}", stage)
    _require(submission.get("actor_kind") == INITIAL_JUDGMENT_MODULE.ACTOR_KIND,
             "submission.actor_kind",
             f"必须是 {INITIAL_JUDGMENT_MODULE.ACTOR_KIND}（本层只支持显式模拟身份，"
             f"不接受真实 HUMAN/AI 身份），实际 {submission.get('actor_kind')!r}", stage)
    _require(submission.get("simulation") == INITIAL_JUDGMENT_MODULE.SIMULATION,
             "submission.simulation",
             f"必须是 {INITIAL_JUDGMENT_MODULE.SIMULATION}，实际 {submission.get('simulation')!r}",
             stage)
    event_id = submission.get("event_id")
    _require(isinstance(event_id, str) and event_id.strip() != "", "submission.event_id",
             f"必须是非空字符串（本层不生成事件 ID），实际 {event_id!r}", stage)
    used = {item.get("event_id") for item in state.get("history") or []}
    used |= {item.get("event_id") for item in state.get("simulated_decisions") or []}
    _require(event_id not in used, "submission.event_id",
             f"事件 ID {event_id!r} 已被本 workflow 的历史或既有模拟决定使用；"
             "初判事件不得复用 Gate 决定事件 ID", stage)


def record_simulated_initial_judgment(batch_dir, submission) -> dict:
    """在合法 0007 批次上真实调用一次冻结初判核心，独占保存模拟记录并追加 0008。"""
    stage = INITIAL_JUDGMENT_STAGE
    paths = None
    target = None
    scene_started = {"value": False}

    def _save_failure_if_started(exc: Exception) -> None:
        if target is None or paths is None or not scene_started["value"]:
            return
        if paths["failure_path"].exists():
            return
        try:
            _save_initial_judgment_failure(target, getattr(exc, "stage", "") or stage, exc,
                                           _initial_judgment_observed_state(target))
        except (WorkflowHostBlocked, WorkflowHostError) as save_exc:
            raise WorkflowHostError(
                f"本次模拟初判保存失败且失败诊断也未能保存：{exc}（保存失败：{save_exc}）",
                reasons=[str(exc), f"保存失败：{save_exc}"],
                stage=getattr(exc, "stage", "") or stage) from exc

    try:
        target = _resolve_batch_dir(batch_dir, must_exist=True, stage=stage)
        context = _load_host_context(target, stage=stage)
        measured = context["measured_bindings"]
        manifest = context["manifest"]
        chain = context["chain"]
        revision = chain["current"]["revision"]
        if revision != 7:
            raise WorkflowHostBlocked(
                f"当前是第 {revision} 份 checkpoint：模拟初判只能在合法的 0007／"
                f"{FACT_PACKET_STATUS_RECORDED} 上保存一次（早期阶段、停止态与已有 0008 一律拒绝，"
                "不从 phase 字符串推导批准）", stage=stage)
        current_workflow = chain["current"]["payload"]["workflow"]
        state = current_workflow["state"]
        _require(state["phase"] == CONTROLLER_MODULE.PHASE_G2_APPROVED, "workflow.state.phase",
                 f"只接受当前 {CONTROLLER_MODULE.PHASE_G2_APPROVED}，实际 {state['phase']!r}", stage)
        previous_file_sha256 = chain["current_file_sha256"]
        fact_expected = dict(chain.get("fact_packet_expected") or {})
        _require(bool(fact_expected), "chain.fact_packet_expected",
                 "0007 恢复必须带出事实底稿的初次核验读数（模拟初判以它为上游预期）", stage)
        paths = _initial_judgment_paths(target)
        if paths["directory"].exists():
            raise WorkflowHostBlocked(
                f"已有模拟初判现场 {paths['relative']}/：本宿主不接管、不覆盖、不清空、不自动重试；"
                "本卡不支持修订、撤销、合并或多份初判，如需重新提交请新建批次", stage=stage)
        if _checkpoint_path(target, 8).exists():
            raise WorkflowHostBlocked(
                f"该批次已有 0008：不得再次提交模拟初判（即使换 event_id 也不覆盖）", stage=stage)

        # 步骤 2：冻结控制器继续验证当前 workflow/bindings；显式读取 AI 动作的真实许可
        try:
            action = CONTROLLER_MODULE.check_dev_action(current_workflow,
                                                        CONTROLLER_MODULE.ACTION_SCREEN,
                                                        current_bindings=measured)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"冻结控制器不允许本次动作：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"动作检查出现意外错误：{exc}", stage=stage) from exc
        _require(action.get("simulation_allowed") is True, "action.simulation_allowed",
                 f"开发态模拟动作必须严格允许，实际 {action.get('simulation_allowed')!r}", stage)
        try:
            ai_action = CONTROLLER_MODULE.check_dev_action(current_workflow,
                                                           CONTROLLER_MODULE.ACTION_AI,
                                                           current_bindings=measured)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"冻结控制器 AI 动作检查被阻断：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"AI 动作检查出现意外错误：{exc}", stage=stage) from exc
        _require(ai_action.get("simulation_allowed") is False, "ai_action.simulation_allowed",
                 f"AI 动作的真实许可必须严格 false（AI 未开放；该 false 不是对本次保存的授权结论），"
                 f"实际 {ai_action.get('simulation_allowed')!r}", stage)
        ai_allowed_real = ai_action["simulation_allowed"]

        # 步骤 3：同缓冲读取本次消费的事实包与其上游读数
        fact_outputs = _read_fact_packet_outputs(target, stage)
        packet = fact_outputs["packet"]
        packet_file_sha256 = fact_outputs["packet_file_sha256"]
        packet_sha256 = canonical_sha256(packet)
        _require(packet_sha256 == fact_expected.get("packet_sha256"), "fact_packet.packet_sha256",
                 f"本次消费事实包对象的规范指纹必须等于 0007 声明：期望 "
                 f"{fact_expected.get('packet_sha256')!r}，实际 {packet_sha256!r}", stage)
        _require(packet_file_sha256 == fact_expected.get("packet_file_sha256"),
                 f"{paths['relative']}/../{FACT_PACKET_DIR}/{FACT_PACKET_JSON}",
                 "本次消费事实包文件字节哈希必须等于 0007 声明", stage)
        artifacts7 = fact_outputs["artifacts"]
        _require(canonical_json(artifacts7) == canonical_json(
            chain["current"]["payload"]["operation"]["artifacts"]),
            f"{WORKFLOW_DIR}/{FACT_PACKET_DIR}/{FACT_PACKET_ARTIFACTS}",
            "事实底稿 artifacts 必须与 0007 内嵌副本完整严格相等", stage)
        gate2_outputs = _read_gate2_outputs(target, stage)
        screen = _read_screen_outputs(target, stage)
        crosscheck = _read_crosscheck_outputs(target, stage)
        gate2_paths = _gate2_paths(target, stage)
        database_path = gate2_paths["database_path"]
        database_sha = file_sha256(database_path)
        for key, value, field in (
            ("screening_started_file_sha256", screen["started_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}"),
            ("screening_report_file_sha256", screen["report_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}"),
            ("screening_artifacts_file_sha256", screen["artifacts_file_sha256"],
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}"),
            ("crosscheck_started_file_sha256", crosscheck["started_file_sha256"],
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_START}"),
            ("crosscheck_report_file_sha256", crosscheck["report_file_sha256"],
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}"),
            ("crosscheck_artifacts_file_sha256", crosscheck["artifacts_file_sha256"],
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}"),
            ("gate2_normalized_file_sha256", gate2_outputs["normalized_file_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}"),
            ("gate2_load_report_file_sha256", gate2_outputs["load_report_file_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}"),
            ("gate2_artifacts_file_sha256", gate2_outputs["artifacts_file_sha256"],
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"),
            ("database_sha256", database_sha, str(database_path)),
        ):
            _require(fact_expected.get(key) == value, field,
                     f"保存前复测发现本次消费的产物与初始读数不一致："
                     f"期望 {fact_expected.get(key)!r}，实际 {value!r}", stage)
        _verify_fact_packet_tail(target, fact_expected, stage)
        _require(packet.get("next_step_allowed") is False, "fact_packet.next_step_allowed",
                 "事实包必须仍是 next_step_allowed=false", stage)

        submission_ref = submission
        submission_canonical_before = canonical_sha256(submission_ref)
        _initial_judgment_preflight(submission_ref, target.name, packet_sha256, state, stage)

        try:
            paths["directory"].mkdir(exist_ok=False)
        except FileExistsError as exc:
            raise WorkflowHostBlocked(f"模拟初判现场目录已存在，不接管：{paths['relative']}",
                                      stage=stage) from exc
        except OSError as exc:
            raise WorkflowHostError(f"无法创建模拟初判现场目录 {paths['directory']!r}：{exc}",
                                    stage=stage) from exc
        scene_started["value"] = True
        started = {
            "start_version": INITIAL_JUDGMENT_START_VERSION,
            "batch_id": target.name,
            "host_version": HOST_VERSION,
            "operation_kind": OPERATION_RECORD_SIMULATED_INITIAL_JUDGMENT,
            "at_utc": _now_utc(),
            "source_checkpoint_file_sha256": previous_file_sha256,
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "run_bindings_sha256": state["run_bindings_sha256"],
            "core_path": str(INITIAL_JUDGMENT_CORE_PATH),
            "core_sha256": manifest["bindings"]["host_code_sha256"]["initial_judgment_core"],
            "core_version": INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
            "packet_file_sha256": packet_file_sha256,
            "packet_sha256": packet_sha256,
            "submission_file_sha256": None,
            "submission_canonical_sha256": submission_canonical_before,
            "submission_event_id": submission_ref.get("event_id"),
            "actor_kind": INITIAL_JUDGMENT_MODULE.ACTOR_KIND,
            "simulation": INITIAL_JUDGMENT_MODULE.SIMULATION,
            "database_path": str(database_path),
            "database_sha256": database_sha,
        }
        submission_file_sha = _write_exclusive_json(paths["submission_path"], submission_ref,
                                                   stage)
        submission_readback, submission_readback_sha = _read_json_with_bytes(
            paths["submission_path"], f"{paths['relative']}/{INITIAL_JUDGMENT_SUBMISSION}", stage)
        _require(submission_readback_sha == submission_file_sha,
                 f"{paths['relative']}/{INITIAL_JUDGMENT_SUBMISSION}",
                 "写后读回的 submission 文件哈希与写入结果不一致", stage)
        _require(canonical_json(submission_readback) == canonical_json(submission_ref),
                 f"{paths['relative']}/{INITIAL_JUDGMENT_SUBMISSION}",
                 "写后读回的 submission 快照必须与本次消费对象规范等值", stage)
        started["submission_file_sha256"] = submission_file_sha
        started_sha = _write_exclusive_json(paths["started_path"], started, stage)

        input_fingerprints_before = {"packet": canonical_sha256(packet),
                                    "submission": canonical_sha256(submission_ref)}
        try:
            result = INITIAL_JUDGMENT_MODULE.build_initial_judgment_record(
                target.name, packet, submission_ref, expected_packet_sha256=packet_sha256)
        except INITIAL_JUDGMENT_MODULE.InitialJudgmentBlocked as exc:
            raise WorkflowHostBlocked(f"冻结初判核心阻断：{exc}", stage=stage) from exc
        except INITIAL_JUDGMENT_MODULE.InitialJudgmentError as exc:
            raise WorkflowHostError(f"冻结初判核心运行失败：{exc}", stage=stage) from exc
        input_fingerprints_after_core = {"packet": canonical_sha256(packet),
                                         "submission": canonical_sha256(submission_ref)}
        _require(canonical_json(input_fingerprints_before)
                 == canonical_json(input_fingerprints_after_core), "initial_judgment.inputs",
                 "冻结初判核心不得修改传入的事实包/提交对象（调用前后规范指纹必须一致）", stage)

        report = _initial_judgment_record_report(result, packet, submission_ref, stage,
                                                 f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}")
        record_file_sha = _write_exclusive_json(paths["record_path"], result, stage)
        record_readback, record_readback_sha = _read_json_with_bytes(
            paths["record_path"], f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}", stage)
        _require(record_readback_sha == record_file_sha,
                 f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}",
                 "写后读回的 initial_judgment 文件哈希与写入结果不一致", stage)
        _require(canonical_json(record_readback) == canonical_json(result),
                 f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}",
                 "写后读回的 initial_judgment 必须与本次真实返回严格规范 JSON 相等", stage)
        _require(canonical_sha256(record_readback["record"]) == report["record_sha256"],
                 f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}",
                 "写后读回的 record 规范指纹必须等于核心返回的 record_sha256", stage)

        artifacts = {
            "artifacts_version": INITIAL_JUDGMENT_ARTIFACTS_VERSION,
            "batch_id": target.name,
            "host_version": HOST_VERSION,
            "operation_kind": OPERATION_RECORD_SIMULATED_INITIAL_JUDGMENT,
            "core_path": str(INITIAL_JUDGMENT_CORE_PATH),
            "core_sha256": manifest["bindings"]["host_code_sha256"]["initial_judgment_core"],
            "core_version": INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
            "record_version": INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
            "initial_judgment_status": INITIAL_JUDGMENT_STATUS_RECORDED,
            "record_sha256": report["record_sha256"],
            "run_bindings_sha256": state["run_bindings_sha256"],
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "previous_checkpoint_file_sha256": previous_file_sha256,
            "previous_checkpoint_relative": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0007.json",
            "packet_file_sha256": packet_file_sha256,
            "packet_sha256": packet_sha256,
            "submission_file_sha256": submission_file_sha,
            "submission_canonical_sha256": submission_canonical_before,
            "submission_event_id": submission_ref.get("event_id"),
            "actor_kind": INITIAL_JUDGMENT_MODULE.ACTOR_KIND,
            "simulation": INITIAL_JUDGMENT_MODULE.SIMULATION,
            "database_path": str(database_path),
            "database_sha256": database_sha,
            "started_relative": f"{paths['relative']}/{INITIAL_JUDGMENT_START}",
            "started_file_sha256": started_sha,
            "submission_relative": f"{paths['relative']}/{INITIAL_JUDGMENT_SUBMISSION}",
            "initial_judgment_relative": f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}",
            "initial_judgment_file_sha256": record_file_sha,
            "artifacts_relative": f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}",
            "findings_total": len(report["finding_ids"]),
            "next_step_allowed": False,
            "ai_suggestion_allowed": False,
            "ai_action_simulation_allowed": ai_allowed_real,
            "gate1_approval": None,
            "gate2_approval": None,
            "human_initial_judgment": None,
            "ai_suggestion": None,
            "final_judgment": None,
            "created_at_utc": _now_utc(),
        }
        artifacts_sha = _write_exclusive_json(paths["artifacts_path"], artifacts, stage)
        artifacts_readback, artifacts_readback_sha = _read_json_with_bytes(
            paths["artifacts_path"], f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}", stage)
        _require(artifacts_readback_sha == artifacts_sha,
                 f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}",
                 "写后读回的 artifacts 文件哈希与写入结果不一致", stage)
        _require(canonical_json(artifacts_readback) == canonical_json(artifacts),
                 f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}",
                 "写后读回的 artifacts 与本次写入对象不一致", stage)

        checkpoint = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "revision": 8,
            "previous_file_sha256": previous_file_sha256,
            "batch_id": target.name,
            "host_manifest_file_sha256": context["manifest_file_sha256"],
            "workflow": current_workflow,
            "operation": {
                "kind": OPERATION_RECORD_SIMULATED_INITIAL_JUDGMENT,
                "at_utc": _now_utc(),
                "artifacts": copy.deepcopy(artifacts_readback),
                "artifacts_file_sha256": artifacts_sha,
                "initial_judgment_file_sha256": record_file_sha,
                "record_sha256": report["record_sha256"],
                "record_version": INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
                "started_file_sha256": started_sha,
                "submission_file_sha256": submission_file_sha,
                "submission_canonical_sha256": submission_canonical_before,
                "submission_event_id": submission_ref.get("event_id"),
                "database_sha256": database_sha,
                "phase_after": state["phase"],
                "bindings_sha256": state["run_bindings_sha256"],
                "initial_judgment_status": INITIAL_JUDGMENT_STATUS_RECORDED,
                "artifacts_relative": f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}",
                "initial_judgment_relative": f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}",
                "started_relative": f"{paths['relative']}/{INITIAL_JUDGMENT_START}",
                "submission_relative": f"{paths['relative']}/{INITIAL_JUDGMENT_SUBMISSION}",
                "core_path": str(INITIAL_JUDGMENT_CORE_PATH),
                "core_sha256": manifest["bindings"]["host_code_sha256"]["initial_judgment_core"],
                "core_version": INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
                "packet_file_sha256": packet_file_sha256,
                "packet_sha256": packet_sha256,
                "previous_checkpoint_file_sha256": previous_file_sha256,
            },
        }
        checkpoint_file_hash = _write_exclusive_json(_checkpoint_path(target, 8), checkpoint, stage)

        # 步骤 8：最后一次必要控制器检查与数据消费之后，实读磁盘复测本次消费的全部材料
        context_after = _load_host_context(target, stage=stage)
        measured_after = context_after["measured_bindings"]
        _require(context_after["chain"]["current_file_sha256"] == checkpoint_file_hash,
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0008.json",
                 "写后读回的当前 checkpoint 字节哈希与写入结果不一致（不宣告成功）", stage)
        _require(context_after["chain"]["current"]["revision"] == 8, "checkpoint",
                 "写后当前 checkpoint 必须为 0008", stage)
        try:
            action_after = CONTROLLER_MODULE.check_dev_action(current_workflow,
                                                              CONTROLLER_MODULE.ACTION_SCREEN,
                                                              current_bindings=measured_after)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"写后动作复核被冻结控制器阻断：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"写后动作复核出现意外错误：{exc}", stage=stage) from exc
        try:
            ai_after = CONTROLLER_MODULE.check_dev_action(current_workflow,
                                                          CONTROLLER_MODULE.ACTION_AI,
                                                          current_bindings=measured_after)
        except CONTROLLER_MODULE.WorkflowBlocked as exc:
            raise WorkflowHostBlocked(f"写后 AI 动作复核被冻结控制器阻断：{exc}", stage=stage) from exc
        except CONTROLLER_MODULE.WorkflowError as exc:
            raise WorkflowHostError(f"写后 AI 动作复核出现意外错误：{exc}", stage=stage) from exc
        _require(ai_after.get("simulation_allowed") is False, "ai_action.simulation_allowed",
                 "写后复核：AI 动作许可必须仍严格 false", stage)
        _require(file_sha256(_checkpoint_path(target, 7)) == previous_file_sha256,
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0007.json",
                 "保存后 0007 字节发生变化（不覆盖、不改签）", stage)
        tail_expected = {
            "started_file_sha256": started_sha,
            "submission_file_sha256": submission_file_sha,
            "record_file_sha256": record_file_sha,
            "artifacts_file_sha256": artifacts_sha,
            "database_path": str(database_path),
            "database_sha256": database_sha,
        }
        tail_actual = _verify_initial_judgment_tail(target, tail_expected, stage)
        _require(file_sha256(_checkpoint_path(target, 8)) == checkpoint_file_hash,
                 f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/0008.json",
                 f"收尾复测发现 0008 字节在本次写入之后发生变化：期望 {checkpoint_file_hash!r}，"
                 f"实际 {file_sha256(_checkpoint_path(target, 8))!r}", stage)
        # 上游产物、数据库与宿主清单实读复测（预期来自初始读数，不用缓存自比）
        for key, value, field in (
            ("screening_started_file_sha256", file_sha256(target / WORKFLOW_DIR / SCREEN_DIR
                                                          / SCREEN_START),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_START}"),
            ("screening_report_file_sha256", file_sha256(target / WORKFLOW_DIR / SCREEN_DIR
                                                         / SCREEN_REPORT),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_REPORT}"),
            ("screening_artifacts_file_sha256", file_sha256(target / WORKFLOW_DIR / SCREEN_DIR
                                                            / SCREEN_ARTIFACTS),
             f"{WORKFLOW_DIR}/{SCREEN_DIR}/{SCREEN_ARTIFACTS}"),
            ("crosscheck_started_file_sha256", file_sha256(target / WORKFLOW_DIR / CROSSCHECK_DIR
                                                           / CROSSCHECK_START),
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_START}"),
            ("crosscheck_report_file_sha256", file_sha256(target / WORKFLOW_DIR / CROSSCHECK_DIR
                                                          / CROSSCHECK_REPORT),
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_REPORT}"),
            ("crosscheck_artifacts_file_sha256", file_sha256(target / WORKFLOW_DIR / CROSSCHECK_DIR
                                                             / CROSSCHECK_ARTIFACTS),
             f"{WORKFLOW_DIR}/{CROSSCHECK_DIR}/{CROSSCHECK_ARTIFACTS}"),
            ("gate2_normalized_file_sha256", file_sha256(target / WORKFLOW_DIR / GATE2_DIR
                                                         / GATE2_NORMALIZED),
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_NORMALIZED}"),
            ("gate2_load_report_file_sha256", file_sha256(target / WORKFLOW_DIR / GATE2_DIR
                                                          / GATE2_LOAD_REPORT),
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_LOAD_REPORT}"),
            ("gate2_artifacts_file_sha256", file_sha256(target / WORKFLOW_DIR / GATE2_DIR
                                                        / GATE2_ARTIFACTS),
             f"{WORKFLOW_DIR}/{GATE2_DIR}/{GATE2_ARTIFACTS}"),
            ("database_sha256", file_sha256(database_path), str(database_path)),
        ):
            _require(fact_expected.get(key) == value, field,
                     f"收尾复测发现上游材料发生变化：期望（初始读取）{fact_expected.get(key)!r}，"
                     f"实际 {value!r}", stage)
        _verify_fact_packet_tail(target, fact_expected, stage)
        for key, path, expected_value in (
            ("gate2_normalized_file_sha256", _gate2_dir(target) / GATE2_NORMALIZED,
             gate2_outputs["normalized_file_sha256"]),
            ("gate2_load_report_file_sha256", _gate2_dir(target) / GATE2_LOAD_REPORT,
             gate2_outputs["load_report_file_sha256"]),
            ("gate2_artifacts_file_sha256", _gate2_dir(target) / GATE2_ARTIFACTS,
             gate2_outputs["artifacts_file_sha256"]),
        ):
            actual_now = file_sha256(path)
            _require(expected_value == actual_now, f"{WORKFLOW_DIR}/{GATE2_DIR}/{path.name}",
                     f"收尾实读发现 Gate2 材料字节变化：期望 {expected_value!r}，"
                     f"实际 {actual_now!r}", stage)
        _require(file_sha256(_host_manifest_path(target)) == context["manifest_file_sha256"],
                 f"{WORKFLOW_DIR}/{HOST_MANIFEST_NAME}",
                 "收尾复测发现宿主清单字节发生变化："
                 f"期望（初始读取）{context['manifest_file_sha256']!r}，"
                 f"实际 {file_sha256(_host_manifest_path(target))!r}", stage)
        _verify_screen_tail(target, {
            "started_file_sha256": screen["started_file_sha256"],
            "report_file_sha256": screen["report_file_sha256"],
            "artifacts_file_sha256": screen["artifacts_file_sha256"],
            "database_path": str(database_path),
            "database_sha256": database_sha,
        }, stage)
        bindings_final = _recheck_static_bindings(
            target, measured, stage, when="模拟初判收尾（最后一次控制器动作检查之后）")
        _require(canonical_json(bindings_final) == canonical_json(state["run_bindings"]), "bindings",
                 "收尾实测的静态绑定必须与本 workflow 创建绑定逐项一致", stage)
        for item in context_after["chain"]["checkpoints"]:
            _require(file_sha256(_checkpoint_path(target, item["revision"])) == item["file_sha256"],
                     f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                     "模拟初判保存后旧 checkpoint 字节发生变化（不覆盖、不改签）", stage)
        _require(canonical_json(input_fingerprints_before)
                 == canonical_json({"packet": canonical_sha256(packet),
                                    "submission": canonical_sha256(submission_ref)}),
                 "initial_judgment.inputs",
                 "公开操作返回前复核：事实包与提交对象的规范指纹必须与调用前一致", stage)
        return {
            "host_version": HOST_VERSION,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "status": STATUS_READY,
            "next_step_allowed": False,
            "batch_id": target.name,
            "batch_dir": str(target),
            "phase": state["phase"],
            "state_sha256": current_workflow["state_sha256"],
            "screening_status": SCREEN_STATUS_RECORDED,
            "crosscheck_status": CROSSCHECK_STATUS_RECORDED,
            "fact_packet_status": FACT_PACKET_STATUS_RECORDED,
            "initial_judgment_status": INITIAL_JUDGMENT_STATUS_RECORDED,
            "completed_actions": ["RULE_SCREEN", "RULE_CROSSCHECK", "FACT_PACKET",
                                  "SIMULATED_INITIAL_JUDGMENT"],
            "action_checked": CONTROLLER_MODULE.ACTION_SCREEN,
            "simulated_action_allowed": action_after["simulation_allowed"],
            "action_reason": action_after["reason"],
            "ai_action_checked": CONTROLLER_MODULE.ACTION_AI,
            "ai_action_simulation_allowed": ai_after["simulation_allowed"],
            "ai_action_reason": ai_after["reason"],
            "initial_judgment": {
                "started_path": f"{paths['relative']}/{INITIAL_JUDGMENT_START}",
                "started_file_sha256": started_sha,
                "submission_path": f"{paths['relative']}/{INITIAL_JUDGMENT_SUBMISSION}",
                "submission_file_sha256": submission_file_sha,
                "submission_canonical_sha256": submission_canonical_before,
                "initial_judgment_path": f"{paths['relative']}/{INITIAL_JUDGMENT_RECORD}",
                "initial_judgment_file_sha256": record_file_sha,
                "record_sha256": report["record_sha256"],
                "record_version": INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
                "artifacts_path": f"{paths['relative']}/{INITIAL_JUDGMENT_ARTIFACTS}",
                "artifacts_file_sha256": artifacts_sha,
                "core_path": str(INITIAL_JUDGMENT_CORE_PATH),
                "core_version": INITIAL_JUDGMENT_MODULE.RECORD_VERSION,
                "submission_event_id": submission_ref.get("event_id"),
                "actor_kind": INITIAL_JUDGMENT_MODULE.ACTOR_KIND,
                "simulation": INITIAL_JUDGMENT_MODULE.SIMULATION,
                "findings_total": len(report["finding_ids"]),
                "input_fingerprints_before": input_fingerprints_before,
                "input_fingerprints_after_core": input_fingerprints_after_core,
            },
            "checkpoints": [{"path": f"{WORKFLOW_DIR}/{CHECKPOINTS_DIR}/{item['name']}",
                             "revision": item["revision"], "file_sha256": item["file_sha256"]}
                            for item in context_after["chain"]["checkpoints"]],
            "current_checkpoint": context_after["chain"]["current_path"],
            "current_checkpoint_file_sha256": checkpoint_file_hash,
            "previous_checkpoint_file_sha256": previous_file_sha256,
            "bindings_sha256": CONTROLLER_MODULE.canonical_sha256(bindings_final),
            "initial_judgment_tail": {"verified": sorted(tail_actual.keys())},
            "simulated_decisions": len(state["simulated_decisions"]),
            "real_approvals": 0,
            "note": ("本次实际执行了冻结初判核心 build_initial_judgment_record 并独占保存了调用方显式"
                     "提供的模拟初判快照；0008 只表示模拟记录已持久化，不等于真实人类独立初判已保存，"
                     "也不表示身份认证、审计完成或真实批准；AI 动作的真实许可仍为 false，"
                     "未生成 AI 建议、未接网络/UI/ERP。"),
        }
    except WorkflowHostBlocked as exc:
        _save_failure_if_started(exc)
        raise
    except WorkflowHostError as exc:
        _save_failure_if_started(exc)
        raise
    except CONTROLLER_MODULE.WorkflowBlocked as exc:
        mapped = WorkflowHostBlocked(f"[initial_judgment] 冻结控制器阻断：{exc}", stage=stage)
        _save_failure_if_started(mapped)
        raise mapped from exc
    except CONTROLLER_MODULE.WorkflowError as exc:
        mapped = WorkflowHostError(f"[initial_judgment] 冻结控制器意外错误：{exc}", stage=stage)
        _save_failure_if_started(mapped)
        raise mapped from exc
    except Exception as exc:  # noqa: BLE001
        mapped = _map_upstream_exception(exc, stage=stage)
        if not hasattr(mapped, "original_exception_chain"):
            mapped.original_exception_chain = _exception_chain(exc)  # type: ignore[attr-defined]
        _save_failure_if_started(mapped)
        if mapped is exc:
            raise
        raise mapped from exc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


def _emit_failure(exc: Exception, stage: str) -> int:
    blocked = isinstance(exc, WorkflowHostBlocked)
    payload = {
        "host_version": HOST_VERSION,
        "mode": MODE,
        "contract_status": CONTRACT_STATUS,
        "next_step_allowed": False,
        "result": "blocked" if blocked else "error",
        "exception_class": "WorkflowHostBlocked" if blocked else "WorkflowHostError",
        "stage": getattr(exc, "stage", "") or stage,
        "message": str(exc),
        "reasons": list(getattr(exc, "reasons", []) or [str(exc)]),
        "note": ("质量／协议／绑定／转移阻断，未建立可批准请求。" if blocked
                 else "文件 I/O、子进程或意外程序错误。"),
    }
    _emit(payload)
    print(f"DIAGNOSTIC: {type(exc).__name__} @ {payload['stage']}: {exc}", file=sys.stderr)
    for item in payload["reasons"]:
        print(f"  - {item}", file=sys.stderr)
    return EXIT_BLOCKED if blocked else EXIT_ERROR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TASK-013 开发态接收宿主"
                    "（接收 → Gate1 决定 → 真实标准化／装载 → Gate2 决定 → 只读 R01—R04 筛查）")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("start", help="实际接收一次并形成 Gate1 请求")
    start.add_argument("--workbook", required=True)
    start.add_argument("--batch-dir", required=True)
    start.add_argument("--source-description", required=True)
    status = subparsers.add_parser("status", help="读取并验证开发态当前状态")
    status.add_argument("--batch-dir", required=True)
    record = subparsers.add_parser("record-simulated-decision", help="提交一份完整的模拟 Gate1 决定")
    record.add_argument("--batch-dir", required=True)
    record.add_argument("--decision-file", required=True)
    prepare = subparsers.add_parser("prepare-gate2",
                                    help="真实标准化与装载，形成 Gate2 待确认请求")
    prepare.add_argument("--batch-dir", required=True)
    gate2_record = subparsers.add_parser("record-simulated-gate2-decision",
                                         help="在 Gate2 待确认批次上提交一份完整的模拟 Gate2 决定")
    gate2_record.add_argument("--batch-dir", required=True)
    gate2_record.add_argument("--decision-file", required=True)
    build_fact_packet = subparsers.add_parser(
        "build-fact-packet",
        help="在合法 0006 批次上真实运行一次冻结事实底稿核心并保存 0007")
    build_fact_packet.add_argument("--batch-dir", required=True)
    crosscheck = subparsers.add_parser("crosscheck-rules",
                                        help="在合法 0005 批次上真实运行一次冻结独立复算并保存 0006")
    crosscheck.add_argument("--batch-dir", required=True)
    initial_judgment = subparsers.add_parser(
        "record-simulated-initial-judgment",
        help="在合法 0007 批次上保存调用方提供的模拟初判并生成 0008")
    initial_judgment.add_argument("--batch-dir", required=True)
    initial_judgment.add_argument("--submission-file", required=True)
    screen = subparsers.add_parser("screen-rules",
                                   help="在 Gate2 模拟 APPROVE 的批次上执行只读 R01—R04 规则筛查")
    screen.add_argument("--batch-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "start":
            _emit(start_dev_batch(args.workbook, args.batch_dir, args.source_description))
            return EXIT_OK
        if args.command == "status":
            _emit(inspect_dev_batch(args.batch_dir))
            return EXIT_OK
        if args.command == "prepare-gate2":
            _emit(prepare_dev_gate2(args.batch_dir))
            return EXIT_OK
        if args.command == "build-fact-packet":
            return _emit(build_dev_fact_packet(args.batch_dir))
        if args.command == "record-simulated-initial-judgment":
            submission_path = Path(args.submission_file)
            if not submission_path.is_absolute():
                submission_path = (Path.cwd() / submission_path).resolve()
            submission = _read_json(submission_path, str(submission_path),
                                    "record_simulated_initial_judgment")
            _emit(record_simulated_initial_judgment(args.batch_dir, submission))
            return EXIT_OK
        if args.command == "crosscheck-rules":
            return _emit(crosscheck_dev_batch(args.batch_dir))
        if args.command == "screen-rules":
            _emit(screen_dev_batch(args.batch_dir))
            return EXIT_OK
        if args.command == "record-simulated-gate2-decision":
            decision_path = Path(args.decision_file)
            if not decision_path.is_absolute():
                decision_path = (Path.cwd() / decision_path).resolve()
            decision = _read_json(decision_path, str(decision_path), "record_gate2")
            _emit(record_simulated_gate2_decision(args.batch_dir, decision))
            return EXIT_OK
        decision_path = Path(args.decision_file)
        if not decision_path.is_absolute():
            decision_path = (Path.cwd() / decision_path).resolve()
        decision = _read_json(decision_path, str(decision_path), "record")
        _emit(record_simulated_gate1_decision(args.batch_dir, decision))
        return EXIT_OK
    except (WorkflowHostBlocked, WorkflowHostError) as exc:
        return _emit_failure(exc, args.command)
    except Exception as exc:  # noqa: BLE001
        return _emit_failure(WorkflowHostError(f"意外程序错误：{type(exc).__name__}: {exc}", stage=args.command),
                             args.command)


if __name__ == "__main__":
    sys.exit(main())
