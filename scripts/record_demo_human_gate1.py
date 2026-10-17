# -*- coding: utf-8 -*-
"""TASK-024：Gate1 决定保存与限定历史核验适配器（唯一生产入口，无 CLI）。

本组件把**已验收的实际材料准备**（冻结 `prepare_demo_human_gate1.py`）与**冻结快照存储**
（`store_demo_human_gate_decision.py`）连接起来：人类先取得当前 32 项材料请求，再明确提交 Gate1
决定；系统从当前文件重新生成独立预期、实读限定范围（scope）内的既有记录，保存并核验**这一次**
提交。

停止点：止于独立 Gate1 记录已保存/可核验。不接宿主/控制器、不执行标准化/DB/筛查、不接 Gate2、
不产生 `0009`/真实初判/AI/终判、不把 `APPROVE` 解释为执行许可；`execution_allowed`/
`workflow_connected`/`ai_enabled` 严格 false。

三公开 API：
  * `prepare_human_gate1_decision_request(batch_dir, request_id)`：只读准备（32 项材料请求）。
  * `save_human_gate1_decision(batch_dir, request_id, submission, event_dir, *, scope_dir=None)`：
    显式限定历史范围并保存（`scope_dir` 缺省/None 结构化 Blocked，不默认空历史）。
  * `verify_human_gate1_decision(event_dir, batch_dir, *, scope_dir=None)`：只读核验。

新层绑定：`code_manifest` 14 项、`materials.files` 32 项（旧 31 项不删改）、
`run_binding.code.file_sha256` 指向**本文件**实际字节、`manifest_fingerprint` 取 14 项规范指纹。
"""

from __future__ import annotations

import hashlib
import importlib.util
import datetime
import json
import os
import stat as stat_module
import sys
import traceback
from pathlib import Path

MODULE_PATH = Path(__file__).resolve()
PROJECT_ROOT = MODULE_PATH.parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"
BATCH_ROOT = DATA_DIR / "batches"
RECORDS_ROOT = DATA_DIR / "human_gate_decision_records"
GATE1_ROOT = RECORDS_ROOT / "gate1"

PREPARE_PATH = SCRIPTS_DIR / "prepare_demo_human_gate1.py"
STORE_PATH = SCRIPTS_DIR / "store_demo_human_gate_decision.py"
ADAPTER_RELATIVE = "scripts/record_demo_human_gate1.py"
ADAPTER_MATERIAL_RELATIVE = "project/scripts/record_demo_human_gate1.py"

# --------------------------------------------------------------------------- 常量（新层协议）
ADAPTER_VERSION = "TASK-024-human-gate1-adapter-1.0"
REQUEST_VERSION = "TASK-024-human-gate1-decision-request-1.0"
STATUS_REQUEST_PREPARED = "HUMAN_GATE1_DECISION_REQUEST_PREPARED"
STATUS_RECORDED = "HUMAN_GATE1_DECISION_RECORDED"
STATUS_VERIFIED = "HUMAN_GATE1_DECISION_VERIFIED"
SCOPE = "LOCAL_GATE1_DECISION_RECORDS_ONLY"
CONTEXT_VERSION = "TASK-024-gate1-context-1.0"
RECEIPT_VERSION = "TASK-024-gate1-receipt-1.0"
RECEIPT_STATUS = "HUMAN_GATE1_EVENT_COMPLETE"
LOCK_VERSION = "TASK-024-gate1-scope-lock-1.0"
LOCK_OPERATION_SAVE = "SAVE"
LOCK_FILE = ".gate1.lock"
FAILURE_VERSION = "TASK-024-gate1-failure-1.0"
FAILURE_STATUS_BLOCKED = "BLOCKED"
FAILURE_STATUS_ERROR = "ERROR"
LOCAL_SCOPE_PREFIX = "GATE1_LOCAL_SCOPE:"

CONTEXT_FILE = "context.json"
RECEIPT_FILE = "receipt.json"
SNAPSHOTS_DIR = "snapshots"
FAILURE_FILE = "failure.json"
EVENT_FILES = (CONTEXT_FILE, RECEIPT_FILE, SNAPSHOTS_DIR)
# 冻结存储恰六文件（本层不添加、不改名）
SNAPSHOT_FILES = ("decision_result.json", "expectations.json", "manifest.json",
                  "materials.json", "prior_history.json", "submission.json")
WRAPPER_VERSION = "TASK-020-human-gate-decision-record-wrapper-1.1"

REQUEST_KEYS = ("request_version", "status", "materials", "expectations", "evidence",
                "boundaries")
MATERIALS_KEYS = ("gate", "batch_id", "run_binding", "contract_binding", "files", "quality",
                  "materials_fingerprint")
EXPECTATIONS_KEYS = ("expected_batch_id", "expected_gate", "expected_request_id",
                     "expected_materials_fingerprint", "expected_files", "expected_contract",
                     "expected_run_binding", "expected_prior_gate1")
EVIDENCE_KEYS = ("source_manifest_version", "source_batch_status", "source_receive_exit_code",
                 "source_description", "source_scope", "code_manifest", "rules_manifest")
QUALITY_KEYS_024 = ("status", "structural_blockers", "quality_blockers",
                    "verification_failures")
SOURCE_SCOPE_KEYS = ("company", "period_start", "period_end", "as_of_date", "currency",
                     "synthetic_declaration", "scope_source", "erp_export_at_utc")
BATCH_LAYOUT = {"batch_manifest.json": "file", "checks": "dir", "code_snapshot": "dir",
                "gate1_packet.md": "file", "logs": "dir", "source": "dir"}
BATCH_SUBDIR_FILES = {"checks": ("quality_report.json",),
                      "logs": ("checker.stderr.txt", "checker.stdout.txt"),
                      "source": ("input.xlsx",),
                      "code_snapshot": ("check_demo_data.py", "receive_demo_batch.py")}
CONFIG_RELATIVE = "config/human_flow_v1.json"
CONFIG_SCOPE_BINDING = (("company", "company"), ("currency", "currency"),
                        ("period_start", "period_start"), ("period_end", "period_end"),
                        ("as_of_date", "cutoff_date"))
RESULT_KEYS = ("adapter_version", "status", "scope", "identity", "record_fingerprint",
               "event_dir", "scope_dir", "store_result", "boundaries")
IDENTITY_KEYS = ("batch_id", "event_id", "decision")
CONTEXT_KEYS = ("context_version", "revision", "event_relative", "source_batch_relative",
                "request", "prior_scope", "snapshot_files", "store_result", "boundaries")
PRIOR_SCOPE_KEYS = ("scope_relative", "declared_scope", "prior_events",
                    "prior_history_fingerprint")
PRIOR_EVENT_KEYS = ("revision", "event_relative", "context_file_sha256",
                    "receipt_file_sha256", "snapshot_files")
SNAPSHOT_ENTRY_KEYS = ("relative", "byte_size", "file_sha256")
RECEIPT_KEYS = ("receipt_version", "status", "revision", "context_file_sha256",
                "snapshot_manifest_file_sha256", "record_fingerprint", "batch_id", "event_id",
                "decision", "boundaries")
LOCK_KEYS = ("lock_version", "operation")
FAILURE_KEYS = ("failure_version", "status", "stage", "field", "reason", "exception_chain",
                "boundaries")
BOUNDARY_KEYS = ("execution_allowed", "workflow_connected", "human_initial_judgment_saved",
                 "ai_enabled", "identity_authenticated", "source_authenticity_proven")
BOUNDARIES = {key: False for key in BOUNDARY_KEYS}
# 准备请求沿用冻结准备器的**原七项** false 边界（本层不删不改旧协议）
REQUEST_BOUNDARY_KEYS = ("request_persisted", "decision_recorded", "execution_allowed",
                         "workflow_connected", "ai_enabled", "identity_authenticated",
                         "source_authenticity_proven")
DECISIONS = ("APPROVE", "HOLD", "REJECT")

RECEIVER_PATH_RELATIVE = "scripts/receive_demo_batch.py"
CHECKER_PATH_RELATIVE = "scripts/check_demo_data.py"


class HumanGate1DecisionBlocked(Exception):
    """字段/路径/协议/前提拒绝（可定位到字段或文件）。"""

    def __init__(self, field, reason):
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


class HumanGate1DecisionError(Exception):
    """运行/I-O/加载/意外内部错误（保留原因链）。"""

    def __init__(self, stage, reason):
        super().__init__(f"{stage}: {reason}")
        self.stage = stage
        self.reason = reason


def _block(field, reason):
    raise HumanGate1DecisionBlocked(field, reason)


def _error(stage, reason):
    raise HumanGate1DecisionError(stage, reason)


# --------------------------------------------------------------------------- 基础工具
def canonical_json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def canonical_with_lf(obj) -> bytes:
    return canonical_json_bytes(obj) + b"\n"


def fingerprint(obj) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _deep(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False))


def _is_strict_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_hex64(value) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _is_nonempty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _require_key(obj, key, field):
    if key not in obj:
        _block(field, "缺失必需字段")
    return obj[key]


def _require_object(value, field):
    if not isinstance(value, dict):
        _block(field, f"必须是对象，实际 {type(value).__name__}")
    return value


def _check_closed_keys(obj, allowed, prefix):
    _require_object(obj, prefix)
    actual = sorted(obj)
    if actual != sorted(allowed):
        _block(prefix, f"键集合必须恰为 {sorted(allowed)}，实际 {actual}")
    return obj


def _require_const(obj, key, expected, prefix):
    value = _require_key(obj, key, f"{prefix}.{key}")
    if value != expected or isinstance(value, bool) is not isinstance(expected, bool):
        _block(f"{prefix}.{key}", f"必须是 {expected!r}，实际 {value!r}")
    return value


def _require_strict_int(obj, key, prefix):
    value = _require_key(obj, key, f"{prefix}.{key}")
    if not _is_strict_int(value):
        _block(f"{prefix}.{key}", f"必须是严格整数，实际 {type(value).__name__}")
    return value


def _require_nonempty_str(obj, key, prefix):
    value = _require_key(obj, key, f"{prefix}.{key}")
    if not _is_nonempty_str(value):
        _block(f"{prefix}.{key}", "必须是非空字符串（原样保存，不归一化）")
    return value


def _require_hex64(obj, key, prefix):
    value = _require_key(obj, key, f"{prefix}.{key}")
    if not _is_hex64(value):
        _block(f"{prefix}.{key}", "必须是完整 64 位小写 hex SHA")
    return value


def _require_boundaries(boundaries, prefix):
    _check_closed_keys(boundaries, BOUNDARY_KEYS, prefix)
    for key in BOUNDARY_KEYS:
        if boundaries[key] is not False:
            _block(f"{prefix}.{key}", f"必须是严格 false，实际 {boundaries[key]!r}")
    return boundaries


def _require_nonneg_int(value, field):
    if not _is_strict_int(value) or value < 0:
        _block(field, f"必须是非负严格整数（非 bool/float），实际 {value!r}")
    return value


def _require_relative_str(obj, key, prefix):
    value = _require_nonempty_str(obj, key, prefix)
    if value.startswith(("/", "\\")) or ".." in value.replace("\\", "/").split("/"):
        _block(f"{prefix}.{key}", "必须是项目相对路径（不以根开头、不含 .. 段）")
    if "\\" in value:
        _block(f"{prefix}.{key}", "相对路径必须使用正斜杠")
    return value


def _require_sorted_unique_files(files, prefix, expected_count):
    if not isinstance(files, list):
        _block(prefix, f"必须是列表，实际 {type(files).__name__}")
    seen = set()
    for index, item in enumerate(files):
        member_prefix = f"{prefix}[{index}]"
        _check_closed_keys(item, SNAPSHOT_ENTRY_KEYS, member_prefix)
        relative = _require_relative_str(item, "relative", member_prefix)
        _require_nonneg_int(item["byte_size"], f"{member_prefix}.byte_size")
        _require_hex64(item, "file_sha256", member_prefix)
        seen.add(relative)
    relatives = [item["relative"] for item in files]
    if relatives != sorted(relatives, key=lambda value: value.encode("utf-8")):
        _block(prefix, "成员必须按 relative UTF-8 升序")
    if len(seen) != len(files):
        _block(prefix, "成员 relative 必须唯一")
    if expected_count is not None and len(files) != expected_count:
        _block(prefix, f"成员数必须恰为 {expected_count}，实际 {len(files)}")
    return files


def _require_sorted_unique_declarations(entries, prefix, member_keys, expected_count):
    if not isinstance(entries, list):
        _block(prefix, f"必须是列表，实际 {type(entries).__name__}")
    relatives = []
    for index, item in enumerate(entries):
        member_prefix = f"{prefix}[{index}]"
        _check_closed_keys(item, member_keys, member_prefix)
        relatives.append(_require_nonempty_str(item, "relative", member_prefix))
        _require_hex64(item, "file_sha256", member_prefix)
        for key in ("rule_id", "rule_version"):
            if key in member_keys:
                _require_nonempty_str(item, key, member_prefix)
    if relatives != sorted(relatives, key=lambda value: value.encode("utf-8")):
        _block(prefix, "成员必须按 relative UTF-8 升序")
    if len(set(relatives)) != len(relatives):
        _block(prefix, "成员 relative 必须唯一")
    if len(entries) != expected_count:
        _block(prefix, f"成员数必须恰为 {expected_count}，实际 {len(entries)}")
    return entries


def _validate_request_schema(request, prefix):
    """B3：请求对象的完整封闭键 / 严格类型 / 嵌套 schema 核验（结构先于比较）。"""
    _check_closed_keys(request, REQUEST_KEYS, prefix)
    _require_const(request, "request_version", REQUEST_VERSION, prefix)
    _require_const(request, "status", STATUS_REQUEST_PREPARED, prefix)
    materials = _check_closed_keys(request["materials"], MATERIALS_KEYS, f"{prefix}.materials")
    expectations = _check_closed_keys(request["expectations"], EXPECTATIONS_KEYS,
                                      f"{prefix}.expectations")
    evidence = _check_closed_keys(request["evidence"], EVIDENCE_KEYS, f"{prefix}.evidence")
    _check_closed_keys(request["boundaries"], REQUEST_BOUNDARY_KEYS, f"{prefix}.boundaries")
    for key in REQUEST_BOUNDARY_KEYS:
        if request["boundaries"][key] is not False:
            _block(f"{prefix}.boundaries.{key}", "必须是严格 false")

    _require_const(materials, "gate", "GATE1", f"{prefix}.materials")
    _require_nonempty_str(materials, "batch_id", f"{prefix}.materials")
    _require_hex64(materials, "materials_fingerprint", f"{prefix}.materials")
    run_binding = _check_closed_keys(materials["run_binding"],
                                     ("code", "rules", "config", "input"),
                                     f"{prefix}.materials.run_binding")
    code = _check_closed_keys(run_binding["code"], ("file_sha256", "manifest_fingerprint"),
                              f"{prefix}.materials.run_binding.code")
    _require_hex64(code, "file_sha256", f"{prefix}.materials.run_binding.code")
    _require_hex64(code, "manifest_fingerprint", f"{prefix}.materials.run_binding.code")
    rules = _check_closed_keys(run_binding["rules"], ("version", "manifest_fingerprint"),
                               f"{prefix}.materials.run_binding.rules")
    _require_nonempty_str(rules, "version", f"{prefix}.materials.run_binding.rules")
    _require_hex64(rules, "manifest_fingerprint", f"{prefix}.materials.run_binding.rules")
    for key in ("config", "input"):
        section = _check_closed_keys(run_binding[key], ("file_sha256",),
                                     f"{prefix}.materials.run_binding.{key}")
        _require_hex64(section, "file_sha256", f"{prefix}.materials.run_binding.{key}")
    contract = _check_closed_keys(materials["contract_binding"],
                                  ("contract_version", "contract_file_sha256",
                                   "contract_effective"),
                                  f"{prefix}.materials.contract_binding")
    _require_nonempty_str(contract, "contract_version",
                          f"{prefix}.materials.contract_binding")
    _require_hex64(contract, "contract_file_sha256", f"{prefix}.materials.contract_binding")
    if contract["contract_effective"] is not True:
        _block(f"{prefix}.materials.contract_binding.contract_effective", "必须是严格 true")
    _require_sorted_unique_files(materials["files"], f"{prefix}.materials.files", 32)
    quality = _check_closed_keys(materials["quality"], QUALITY_KEYS_024,
                                 f"{prefix}.materials.quality")
    if quality["status"] not in ("OK", "BLOCKED", "FAILED"):
        _block(f"{prefix}.materials.quality.status", "必须是 OK/BLOCKED/FAILED")
    for key in ("structural_blockers", "quality_blockers", "verification_failures"):
        value = quality[key]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            _block(f"{prefix}.materials.quality.{key}", "必须是字符串列表")

    _require_const(expectations, "expected_gate", "GATE1", f"{prefix}.expectations")
    _require_nonempty_str(expectations, "expected_batch_id", f"{prefix}.expectations")
    _require_nonempty_str(expectations, "expected_request_id", f"{prefix}.expectations")
    _require_hex64(expectations, "expected_materials_fingerprint", f"{prefix}.expectations")
    if expectations["expected_prior_gate1"] is not None:
        _block(f"{prefix}.expectations.expected_prior_gate1", "必须是 null")
    if expectations["expected_batch_id"] != materials["batch_id"]:
        _block(f"{prefix}.expectations.expected_batch_id", "必须等于 materials.batch_id")
    if expectations["expected_materials_fingerprint"] != materials["materials_fingerprint"]:
        _block(f"{prefix}.expectations.expected_materials_fingerprint",
               "必须等于 materials.materials_fingerprint")
    expected_contract = _check_closed_keys(
        expectations["expected_contract"], ("contract_version", "contract_file_sha256"),
        f"{prefix}.expectations.expected_contract")
    if expected_contract["contract_version"] != contract["contract_version"] or \
            expected_contract["contract_file_sha256"] != contract["contract_file_sha256"]:
        _block(f"{prefix}.expectations.expected_contract",
               "必须与 materials.contract_binding 的版本与文件 SHA 一致")
    if canonical_json_bytes(expectations["expected_run_binding"]) != canonical_json_bytes(
            run_binding):
        _block(f"{prefix}.expectations.expected_run_binding",
               "必须与 materials.run_binding 一致")
    expected_files = expectations["expected_files"]
    if not isinstance(expected_files, dict) or len(expected_files) != 32:
        _block(f"{prefix}.expectations.expected_files", "必须是 32 项映射")
    for key, value in expected_files.items():
        if not _is_nonempty_str(key) or not _is_hex64(value):
            _block(f"{prefix}.expectations.expected_files[{key}]", "必须是相对路径→hex64")
    if expected_files != {item["relative"]: item["file_sha256"]
                          for item in materials["files"]}:
        _block(f"{prefix}.expectations.expected_files", "必须与 materials.files 双向一致")

    _require_nonempty_str(evidence, "source_manifest_version", f"{prefix}.evidence")
    _require_nonempty_str(evidence, "source_batch_status", f"{prefix}.evidence")
    _require_nonempty_str(evidence, "source_description", f"{prefix}.evidence")
    _require_nonneg_int(evidence["source_receive_exit_code"],
                        f"{prefix}.evidence.source_receive_exit_code")
    source_scope = _check_closed_keys(evidence["source_scope"], SOURCE_SCOPE_KEYS,
                                      f"{prefix}.evidence.source_scope")
    for key in ("company", "period_start", "period_end", "as_of_date", "currency",
                "synthetic_declaration", "scope_source"):
        _require_nonempty_str(source_scope, key, f"{prefix}.evidence.source_scope")
    exported = source_scope["erp_export_at_utc"]
    if exported is not None and not _is_nonempty_str(exported):
        _block(f"{prefix}.evidence.source_scope.erp_export_at_utc", "必须是 null 或非空字符串")
    for key in ("period_start", "period_end", "as_of_date"):
        _require_calendar_date(source_scope[key],
                               f"{prefix}.evidence.source_scope.{key}")
    if source_scope["period_start"] > source_scope["period_end"]:
        _block(f"{prefix}.evidence.source_scope.period_end", "不得早于 period_start")
    if not (source_scope["period_start"] <= source_scope["as_of_date"]
            <= source_scope["period_end"]):
        _block(f"{prefix}.evidence.source_scope.as_of_date", "必须落在申报期间内")
    config = _load_frozen_config()
    for scope_key, config_key in CONFIG_SCOPE_BINDING:
        bound = config.get(config_key)
        if bound is None:
            _block(f"{prefix}.evidence.source_scope.{scope_key}",
                   f"冻结配置缺少绑定字段 {config_key}")
        if source_scope[scope_key] != bound:
            _block(f"{prefix}.evidence.source_scope.{scope_key}",
                   f"必须与冻结配置 {config_key} 一致（配置 {bound!r}，实际 "
                   f"{source_scope[scope_key]!r}）")
    if config.get("synthetic_data") is not True:
        _block(f"{prefix}.evidence.source_scope", "冻结配置的合成数据声明必须为 true")
    code_manifest = _check_closed_keys(
        evidence["code_manifest"], ("entries", "manifest_fingerprint"),
        f"{prefix}.evidence.code_manifest")
    entries = _require_sorted_unique_declarations(
        code_manifest["entries"], f"{prefix}.evidence.code_manifest.entries",
        ("file_sha256", "relative"), 14)
    _require_hex64(code_manifest, "manifest_fingerprint",
                   f"{prefix}.evidence.code_manifest")
    if code_manifest["manifest_fingerprint"] != fingerprint(
            {"entries": entries, "manifest_version": None}):
        _block(f"{prefix}.evidence.code_manifest.manifest_fingerprint",
               "必须等于本层 14 项清单的规范指纹")
    if code_manifest["manifest_fingerprint"] != code["manifest_fingerprint"]:
        _block(f"{prefix}.evidence.code_manifest.manifest_fingerprint",
               "必须与 run_binding.code.manifest_fingerprint 一致")
    rules_manifest = _check_closed_keys(evidence["rules_manifest"], ("entries", "version"),
                                        f"{prefix}.evidence.rules_manifest")
    _require_nonempty_str(rules_manifest, "version", f"{prefix}.evidence.rules_manifest")
    _require_sorted_unique_declarations(
        rules_manifest["entries"], f"{prefix}.evidence.rules_manifest.entries",
        ("file_sha256", "relative", "rule_id", "rule_version"), 4)
    if fingerprint(rules_manifest) != rules["manifest_fingerprint"]:
        _block(f"{prefix}.evidence.rules_manifest",
               "run_binding.rules.manifest_fingerprint 必须等于 rules_manifest 规范指纹")
    declared = {item["relative"]: item["file_sha256"] for item in entries}
    material_code = {item["relative"]: item["file_sha256"] for item in materials["files"]
                     if item["relative"].startswith("project/")}
    for relative, digest in declared.items():
        key = relative if relative.startswith("project/") else f"project/{relative}"
        if key not in material_code:
            _block(f"{prefix}.evidence.code_manifest.entries[{relative}]",
                   "14 项代码声明必须在 materials.files 中逐项存在")
        if material_code[key] != digest:
            _block(f"{prefix}.evidence.code_manifest.entries[{relative}]",
                   "代码声明 SHA 必须与 materials.files 的实际读数一致")
    adapter_material = material_code.get(ADAPTER_MATERIAL_RELATIVE)
    if adapter_material is None or adapter_material != code["file_sha256"]:
        _block(f"{prefix}.materials.run_binding.code.file_sha256",
               "必须等于 materials.files 中本层适配器条目的实际字节 SHA")
    return materials, expectations


def _require_request_closure(materials, expectations, snapshots, record, prefix):
    """B3：request 与其存储快照、record/manifest 既定绑定按 **canonical 字节** 严格相等。"""
    if canonical_json_bytes(snapshots["materials.json"]) != canonical_json_bytes(materials):
        _block(f"{prefix}.snapshots/materials.json", "必须与 request.materials 规范字节相等")
    if canonical_json_bytes(snapshots["expectations.json"]) != canonical_json_bytes(expectations):
        _block(f"{prefix}.snapshots/expectations.json",
               "必须与 request.expectations 规范字节相等")
    binding = _require_object(_require_key(record, "binding", f"{prefix}.record.binding"),
                              f"{prefix}.record.binding")
    if binding.get("materials_fingerprint") != materials["materials_fingerprint"]:
        _block(f"{prefix}.record.binding.materials_fingerprint",
               "必须等于 request.materials.materials_fingerprint")
    if binding.get("request_id") != expectations["expected_request_id"]:
        _block(f"{prefix}.record.binding.request_id",
               "必须等于 request.expectations.expected_request_id")
    if "materials_files" in binding and canonical_json_bytes(
            binding["materials_files"]) != canonical_json_bytes(materials["files"]):
        _block(f"{prefix}.record.binding.materials_files", "必须与 request.materials.files 相等")
    manifest = snapshots["manifest.json"]
    fingerprints = manifest.get("fingerprints")
    if isinstance(fingerprints, dict):
        for key, value in fingerprints.items():
            if not _is_hex64(value):
                _block(f"{prefix}.snapshots/manifest.json.fingerprints.{key}",
                       "必须是 hex64")
    return True


def _require_request_boundaries(boundaries, prefix):
    _check_closed_keys(boundaries, REQUEST_BOUNDARY_KEYS, prefix)
    for key in REQUEST_BOUNDARY_KEYS:
        if boundaries[key] is not False:
            _block(f"{prefix}.{key}", f"必须是严格 false，实际 {boundaries[key]!r}")
    return boundaries


def _path_chain(path: Path):
    chain = [path]
    node = path
    while True:
        parent = node.parent
        if parent == node:
            break
        chain.append(parent)
        node = parent
    return chain


def _is_reparse_point(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise HumanGate1DecisionError(
            "lstat", f"无法检查路径属性 {path}：{type(exc).__name__}: {exc}") from exc
    if stat_module.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _reject_reparse_in_chain(path: Path, field):
    for node in _path_chain(path):
        try:
            exists = node.exists() or node.is_symlink()
        except OSError as exc:
            raise HumanGate1DecisionError(
                "stat", f"无法检查路径 {node}：{type(exc).__name__}: {exc}") from exc
        if exists and _is_reparse_point(node):
            _block(field, f"原始路径包含符号链接/junction/reparse 点：{node.name or node}")


def _check_path_item(raw_path: Path, field, *, must_be_file):
    _reject_reparse_in_chain(raw_path, field)
    try:
        resolved = raw_path.resolve()
    except (OSError, ValueError) as exc:
        raise HumanGate1DecisionError(
            "resolve", f"无法解析路径 {raw_path}：{type(exc).__name__}: {exc}") from exc
    _reject_reparse_in_chain(resolved, field)
    try:
        exists = resolved.exists()
    except OSError as exc:
        raise HumanGate1DecisionError(
            "stat", f"无法检查路径是否存在 {field}：{type(exc).__name__}: {exc}") from exc
    if not exists:
        _block(field, "路径不存在")
    probe = resolved.is_file() if must_be_file else resolved.is_dir()
    if not probe:
        _block(field, "必须是正常文件" if must_be_file else "必须是目录")
    return resolved


def _project_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise HumanGate1DecisionError(
            "relative", f"路径不在项目内：{path}") from exc


def _read_bytes(path: Path, stage, field) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise HumanGate1DecisionError(
            stage, f"无法读取 {field}：{type(exc).__name__}: {exc}") from exc


def _write_exclusive(path: Path, buffer: bytes, stage, field) -> None:
    try:
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise HumanGate1DecisionBlocked(field, "目标已存在；独占写被拒绝") from exc
    except OSError as exc:
        raise HumanGate1DecisionError(stage, f"无法独占创建 {field}：{exc}") from exc
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(buffer)
    except OSError as exc:
        raise HumanGate1DecisionError(stage, f"无法写入 {field}：{exc}") from exc


def _readback(path: Path, buffer: bytes, stage, field):
    actual = _read_bytes(path, stage, field)
    if actual != buffer:
        _block(field, "读回字节与本次待写缓冲不一致")
    try:
        return json.loads(actual.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HumanGate1DecisionError(stage, f"读回对象无法解析：{exc}") from exc


def _exception_detail(exc) -> dict:
    chain = []
    node = exc
    seen = 0
    while node is not None and seen < 12:
        chain.append({"type": f"{type(node).__module__}.{type(node).__name__}",
                      "message": str(node)})
        node = node.__cause__ if node.__cause__ is not None else node.__context__
        seen += 1
    return {"type": f"{type(exc).__module__}.{type(exc).__name__}", "message": str(exc),
            "cause_chain": chain, "traceback": traceback.format_exc()}


# --------------------------------------------------------------------------- 冻结上游加载
_PREPARE_CACHE = {"module": None}
_STORE_CACHE = {"module": None}


def load_frozen_prepare():
    """加载冻结准备器模块（只读复用其公开 API）。"""
    name = "prepare_demo_human_gate1"
    module = sys.modules.get(name)
    if module is not None and Path(getattr(module, "__file__", "")).resolve() == PREPARE_PATH:
        _PREPARE_CACHE["module"] = module
        return module
    if _PREPARE_CACHE["module"] is not None:
        return _PREPARE_CACHE["module"]
    try:
        spec = importlib.util.spec_from_file_location(name, PREPARE_PATH)
        if spec is None or spec.loader is None:
            _error("prepare_load", f"无法为冻结准备器建立 spec：{PREPARE_PATH}")
        candidate = importlib.util.module_from_spec(spec)
        sys.modules[name] = candidate
        try:
            spec.loader.exec_module(candidate)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    except (HumanGate1DecisionBlocked, HumanGate1DecisionError):
        raise
    except OSError as exc:
        raise HumanGate1DecisionError(
            "prepare_load", f"加载冻结准备器 I/O 失败：{exc}") from exc
    except BaseException as exc:  # noqa: BLE001 - 加载接缝（含 ImportError）结构化报告
        sys.modules.pop(name, None)
        _PREPARE_CACHE["module"] = None
        raise HumanGate1DecisionError(
            "prepare_load",
            f"加载冻结准备器失败：{type(exc).__name__}: {exc}") from exc
    _PREPARE_CACHE["module"] = candidate
    return candidate


def load_frozen_store():
    name = "store_demo_human_gate_decision"
    module = sys.modules.get(name)
    if module is not None and Path(getattr(module, "__file__", "")).resolve() == STORE_PATH:
        _STORE_CACHE["module"] = module
        return module
    if _STORE_CACHE["module"] is not None:
        return _STORE_CACHE["module"]
    try:
        spec = importlib.util.spec_from_file_location(name, STORE_PATH)
        if spec is None or spec.loader is None:
            _error("store_load", f"无法为冻结存储建立 spec：{STORE_PATH}")
        candidate = importlib.util.module_from_spec(spec)
        sys.modules[name] = candidate
        try:
            spec.loader.exec_module(candidate)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    except (HumanGate1DecisionBlocked, HumanGate1DecisionError):
        raise
    except OSError as exc:
        raise HumanGate1DecisionError("store_load", f"加载冻结存储 I/O 失败：{exc}") from exc
    except BaseException as exc:  # noqa: BLE001 - 加载接缝（含 ImportError）结构化报告
        sys.modules.pop(name, None)
        _STORE_CACHE["module"] = None
        raise HumanGate1DecisionError(
            "store_load", f"加载冻结存储失败：{type(exc).__name__}: {exc}") from exc
    _STORE_CACHE["module"] = candidate
    return candidate


def _map_downstream(exc, stage):
    """下游 Blocked/Error 原样透传（保留 field/reason 与 cause 链），其他异常映射为 Error。"""
    store = _STORE_CACHE["module"]
    if store is not None:
        if isinstance(exc, store.HumanGateDecisionStoreBlocked):
            raise HumanGate1DecisionBlocked(f"store.{exc.field}", exc.reason) from exc
        if isinstance(exc, store.HumanGateDecisionStoreError):
            raise HumanGate1DecisionError(f"store.{exc.stage}", exc.reason) from exc
    prepare = _PREPARE_CACHE["module"]
    if prepare is not None:
        if isinstance(exc, prepare.HumanGate1RequestBlocked):
            raise HumanGate1DecisionBlocked(f"prepare.{exc.field}", exc.reason) from exc
        if isinstance(exc, prepare.HumanGate1RequestError):
            raise HumanGate1DecisionError(f"prepare.{exc.stage}", exc.reason) from exc
    if isinstance(exc, OSError):
        raise HumanGate1DecisionError(stage, f"I/O 失败：{exc}") from exc
    raise HumanGate1DecisionError(
        stage, f"意外内部错误：{type(exc).__name__}: {exc}") from exc


# --------------------------------------------------------------------------- 32 项材料请求
def _frozen_request(batch_dir, request_id):
    """真实调用冻结准备器一次，只消费其经核验的完整返回。"""
    prepare = load_frozen_prepare()
    try:
        base = prepare.prepare_human_gate1_request(batch_dir, request_id)
    except BaseException as exc:  # noqa: BLE001 - 统一映射到本层边界（含下游协议拒绝）
        _map_downstream(exc, "prepare_call")
    _check_closed_keys(base, REQUEST_KEYS, "prepare.request")
    _check_closed_keys(_require_object(base["materials"], "prepare.materials"), MATERIALS_KEYS,
                       "prepare.materials")
    _check_closed_keys(_require_object(base["expectations"], "prepare.expectations"),
                       EXPECTATIONS_KEYS, "prepare.expectations")
    _check_closed_keys(_require_object(base["evidence"], "prepare.evidence"), EVIDENCE_KEYS,
                       "prepare.evidence")
    _require_request_boundaries(base["boundaries"], "prepare.boundaries")
    return base


def _adapter_bytes():
    return _read_bytes(MODULE_PATH, "adapter_read", ADAPTER_RELATIVE)


def _extend_request(base, adapter_buffer):
    """在本层扩展冻结准备的返回：14 项代码、32 项材料、新运行绑定与独立八键期望。"""
    materials = _deep(base["materials"])
    expectations = _deep(base["expectations"])
    evidence = _deep(base["evidence"])

    code_manifest = _require_object(evidence["code_manifest"], "prepare.evidence.code_manifest")
    entries = list(_require_key(code_manifest, "entries", "code_manifest.entries"))
    adapter_sha = sha256_bytes(adapter_buffer)
    entries.append({"relative": ADAPTER_RELATIVE, "file_sha256": adapter_sha})
    entries.sort(key=lambda item: item["relative"].encode("utf-8"))
    if len(entries) != 14 or len({item["relative"] for item in entries}) != 14:
        _block("code_manifest.entries", "扩展后必须恰为 14 项且相对路径唯一")
    code_manifest["entries"] = entries
    code_manifest["manifest_fingerprint"] = fingerprint(
        {"entries": entries, "manifest_version": code_manifest.get("manifest_version")})
    evidence["code_manifest"] = code_manifest

    files = list(_require_key(materials, "files", "materials.files"))
    files.append({"relative": ADAPTER_MATERIAL_RELATIVE, "file_sha256": adapter_sha,
                  "byte_size": len(adapter_buffer)})
    files.sort(key=lambda item: item["relative"].encode("utf-8"))
    if len(files) != 32 or len({item["relative"] for item in files}) != 32:
        _block("materials.files", "扩展后必须恰为 32 项且相对路径唯一")
    materials["files"] = files

    run_binding = _require_object(materials["run_binding"], "materials.run_binding")
    code_binding = _require_object(run_binding["code"], "materials.run_binding.code")
    code_binding["file_sha256"] = adapter_sha
    code_binding["manifest_fingerprint"] = code_manifest["manifest_fingerprint"]
    run_binding["code"] = code_binding
    materials["run_binding"] = run_binding

    store = load_frozen_store()
    core = store.load_frozen_p1_core()
    body = core.materials_body({key: value for key, value in materials.items()
                                if key != "materials_fingerprint"})
    materials["materials_fingerprint"] = core.fingerprint(body)

    expectations["expected_files"] = {item["relative"]: item["file_sha256"]
                                      for item in files}
    expectations["expected_materials_fingerprint"] = materials["materials_fingerprint"]
    expectations["expected_run_binding"] = _deep(run_binding)
    request = {"request_version": REQUEST_VERSION, "status": STATUS_REQUEST_PREPARED,
               "materials": materials, "expectations": expectations, "evidence": evidence,
               "boundaries": _deep(base["boundaries"])}
    return request


def prepare_human_gate1_decision_request(batch_dir, request_id):
    """只读准备：冻结准备的 31 项请求 + 本层自身绑定 = 32 项决定请求（不生成 submission）。"""
    base = _frozen_request(batch_dir, request_id)
    adapter_buffer = _adapter_bytes()
    request = _extend_request(base, adapter_buffer)
    _final_confirm_decision_request(request, batch_dir, adapter_buffer)
    return request


def _is_iso_date(value):
    if not isinstance(value, str) or len(value) != 10 or value[4] != "-" or value[7] != "-":
        return False
    digits = value.replace("-", "")
    return digits.isdigit()


def _require_calendar_date(value, field):
    """真实日历合法（拒绝 2026-09-00 / 2026-13-01 等），保持原文、不补值。"""
    if not _is_iso_date(value):
        _block(field, "必须是 YYYY-MM-DD 形式")
    try:
        datetime.date.fromisoformat(value)
    except ValueError as exc:
        _block(field, f"不是真实日历日期：{exc}")


def _load_frozen_config():
    """只读冻结项目配置（逐级无链接复核），不实读历史业务源。"""
    path = PROJECT_ROOT / CONFIG_RELATIVE
    _check_path_item(path, CONFIG_RELATIVE, must_be_file=True)
    try:
        return json.loads(_read_bytes(path, "config_read", CONFIG_RELATIVE).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HumanGate1DecisionError("config_read", f"配置无法解析：{exc}") from exc


def _confirm_batch_layout(batch_dir):
    """当前接收批次必须是既定八文件与固定子目录集合（未知项不能被忽略）。"""
    batch_dir = Path(batch_dir)
    try:
        entries = {entry.name: entry.is_dir() for entry in os.scandir(batch_dir)}
    except OSError as exc:
        raise HumanGate1DecisionError("terminal_read", f"无法枚举批次目录：{exc}") from exc
    expected = set(BATCH_LAYOUT)
    if set(entries) != expected:
        _block("batch_dir",
               f"终端确认：批次顶层集合必须恰为 {sorted(expected)}，实际 {sorted(entries)}")
    for name, kind in BATCH_LAYOUT.items():
        is_dir = entries[name]
        if (kind == "dir") is not is_dir:
            _block(f"batch_dir/{name}", f"终端确认：必须是{'目录' if kind == 'dir' else '文件'}")
    for subdir, allowed in BATCH_SUBDIR_FILES.items():
        path = batch_dir / subdir
        _check_path_item(path, f"{subdir}", must_be_file=False)
        try:
            actual = {entry.name for entry in os.scandir(path)}
        except OSError as exc:
            raise HumanGate1DecisionError("terminal_read", f"无法枚举 {subdir}：{exc}") from exc
        if actual != set(allowed):
            _block(f"batch_dir/{subdir}",
                   f"终端确认：集合必须恰为 {sorted(allowed)}，实际 {sorted(actual)}")


def _confirm_event_layout(event_dir):
    """事件目录只含 context/receipt/snapshots，snapshots 恰为冻结六文件；failure 优先阻断。"""
    event_dir = Path(event_dir)
    if (event_dir / FAILURE_FILE).exists():
        _block(f"{event_dir.name}/{FAILURE_FILE}", "终端确认：出现失败诊断")
    try:
        top = {entry.name: entry.is_dir() for entry in os.scandir(event_dir)}
    except OSError as exc:
        raise HumanGate1DecisionError("terminal_read", f"无法枚举事件目录：{exc}") from exc
    if set(top) != {CONTEXT_FILE, RECEIPT_FILE, SNAPSHOTS_DIR}:
        _block(event_dir.name,
               f"终端确认：事件目录必须恰为 {sorted({CONTEXT_FILE, RECEIPT_FILE, SNAPSHOTS_DIR})}，"
               f"实际 {sorted(top)}")
    snapshots = event_dir / SNAPSHOTS_DIR
    _check_path_item(snapshots, f"{event_dir.name}/{SNAPSHOTS_DIR}", must_be_file=False)
    try:
        actual = {entry.name for entry in os.scandir(snapshots)}
    except OSError as exc:
        raise HumanGate1DecisionError("terminal_read", f"无法枚举 snapshots：{exc}") from exc
    if actual != set(SNAPSHOT_FILES):
        _block(f"{event_dir.name}/{SNAPSHOTS_DIR}",
               f"终端确认：快照集合必须恰为 {sorted(SNAPSHOT_FILES)}，实际 {sorted(actual)}")


def _source_paths(materials, batch_dir):
    """32 项白名单材料的真实路径（语义确认与终端确认共用同一套路径解析）。"""
    files = materials["files"]
    if len(files) != 32:
        _block("materials.files", "要求恰 32 项材料")
    resolved = []
    for item in files:
        relative = item["relative"]
        if relative == ADAPTER_MATERIAL_RELATIVE:
            target = MODULE_PATH
        elif relative.startswith("batch/"):
            target = Path(batch_dir) / relative[len("batch/"):]
        elif relative.startswith("project/"):
            target = PROJECT_ROOT / relative[len("project/"):]
        else:
            _block(f"materials.files[{relative}]", "未知的材料前缀")
        resolved.append((relative, Path(target), item))
    return resolved


def _source_snapshot(request, batch_dir):
    """语义阶段的来源同缓冲读数：其缓冲成为终端确认的唯一预期（不来自候选重建）。"""
    snapshot = []
    for relative, path, item in _source_paths(request["materials"], batch_dir):
        _check_path_item(path, relative, must_be_file=True)
        data = _read_bytes(path, "source_snapshot", relative)
        if len(data) != item["byte_size"] or sha256_bytes(data) != item["file_sha256"]:
            _block(relative, "来源快照与请求声明不一致（字节或 SHA 变化）")
        snapshot.append((path, data))
    return snapshot


def _terminal_confirm(sources, events, target_dir, target_buffers, scope, expected_names,
                      batch_dir=None):
    """有界终端确认：只做字节/集合/路径/失败/锁确认，不再读 adapter、不加载核心、不解析业务 JSON。"""
    for path, buffer in sources:
        _check_path_item(path, _project_relative(path), must_be_file=True)
        if _read_bytes(path, "terminal_read", _project_relative(path)) != buffer:
            _block(_project_relative(path), "终端确认：当前来源字节发生变化")
    if batch_dir is not None:
        _confirm_batch_layout(batch_dir)
    for item in events:
        _confirm_event_layout(item["event_dir"])
        for name, buffer in item["buffers"].items():
            if _read_bytes(item["event_dir"] / name, "terminal_read", name) != buffer:
                _block(f"{item['event_relative']}/{name}", "终端确认：事件字节发生变化")
    if target_dir is not None:
        _confirm_event_layout(Path(target_dir))
        for name, buffer in target_buffers.items():
            if _read_bytes(Path(target_dir) / name, "terminal_read", name) != buffer:
                _block(f"{Path(target_dir).name}/{name}", "终端确认：目标字节发生变化")
        if (Path(target_dir) / FAILURE_FILE).exists():
            _block(FAILURE_FILE, "终端确认：本次事件存在失败诊断")
    listing = _list_scope(scope)
    if listing["names"] != sorted(expected_names):
        _block("scope_dir", "终端确认：scope 成员集合发生变化")
    if listing["lock_present"] and listing["names"].count(LOCK_FILE) and \
            scope not in (None,):
        pass


def _final_confirm_decision_request(request, batch_dir, adapter_buffer):
    """全部必要消费之后的最终确认：32 份当前来源字节与集合、本 adapter 字节。"""
    materials = request["materials"]
    files = materials["files"]
    if len(files) != 32:
        _block("materials.files", "最终确认要求恰 32 项材料")
    for item in files:
        relative = item["relative"]
        if relative == ADAPTER_MATERIAL_RELATIVE:
            target = MODULE_PATH
        elif relative.startswith("batch/"):
            target = Path(batch_dir) / relative[len("batch/"):]
        elif relative.startswith("project/"):
            target = PROJECT_ROOT / relative[len("project/"):]
        else:
            _block(f"materials.files[{relative}]", "未知的材料前缀")
        _check_path_item(Path(target), relative, must_be_file=True)
        data = _read_bytes(target, "final_read", relative)
        if len(data) != item["byte_size"] or sha256_bytes(data) != item["file_sha256"]:
            _block(relative, "最终确认与本次初始读数不一致（字节或 SHA 变化）")
    if sha256_bytes(adapter_buffer) != sha256_bytes(_adapter_bytes()):
        _block(ADAPTER_RELATIVE, "本层适配器文件在准备期间发生变化")
    store = load_frozen_store()
    core = store.load_frozen_p1_core()
    recomputed = core.fingerprint(core.materials_body(
        {key: value for key, value in materials.items() if key != "materials_fingerprint"}))
    if recomputed != materials["materials_fingerprint"]:
        _block("materials.materials_fingerprint", "最终确认复算与请求不一致")


# --------------------------------------------------------------------------- scope / event / 锁
def _gate1_root_resolved():
    return GATE1_ROOT.resolve() if GATE1_ROOT.exists() else GATE1_ROOT


def _resolve_scope_dir(scope_dir):
    if scope_dir is None:
        _block("scope_dir", "必须由调用方显式提供并先建立（不默认空历史、不自动换 scope）")
    if not isinstance(scope_dir, (str, os.PathLike)):
        _block("scope_dir", f"必须是路径，实际 {type(scope_dir).__name__}")
    resolved = _check_path_item(Path(scope_dir), "scope_dir", must_be_file=False)
    root = _gate1_root_resolved()
    if resolved == root or root not in resolved.parents:
        _block("scope_dir", "必须是 data/human_gate_decision_records/gate1 的严格后代")
    return resolved


def _resolve_event_dir(event_dir, scope):
    if not isinstance(event_dir, (str, os.PathLike)):
        _block("event_dir", f"必须是路径，实际 {type(event_dir).__name__}")
    raw = Path(event_dir)
    _reject_reparse_in_chain(raw, "event_dir")
    try:
        resolved = raw.resolve()
    except (OSError, ValueError) as exc:
        raise HumanGate1DecisionError("resolve", f"无法解析 event_dir：{exc}") from exc
    _reject_reparse_in_chain(resolved, "event_dir")
    if resolved.parent != scope:
        _block("event_dir", "必须是 scope_dir 的直接子目录")
    if resolved.exists():
        _block("event_dir", "目标事件目录已存在（含空目录）；独占建立被拒绝")
    return resolved


def _acquire_scope_lock(scope):
    path = scope / LOCK_FILE
    buffer = canonical_with_lf({"lock_version": LOCK_VERSION,
                                "operation": LOCK_OPERATION_SAVE})
    try:
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise HumanGate1DecisionBlocked(
            "scope_dir.lock",
            "scope 已被占用（存在 .gate1.lock）；不自动回收、不等候重试") from exc
    except OSError as exc:
        raise HumanGate1DecisionError("lock", f"无法独占创建锁：{exc}") from exc
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(buffer)
    except OSError as exc:
        raise HumanGate1DecisionError("lock", f"无法写入锁：{exc}") from exc
    return {"path": path, "buffer": buffer}


def _release_scope_lock(lock):
    path = lock["path"]
    data = _read_bytes(path, "lock_release", LOCK_FILE)
    if data != lock["buffer"]:
        _error("lock_release", "锁字节与本次写入不一致；拒绝删除非本次锁")
    try:
        os.unlink(path)
    except OSError as exc:
        raise HumanGate1DecisionError("lock_release", f"无法释放锁：{exc}") from exc


def _list_scope(scope):
    """实读枚举 scope 首层：只允许本层事件目录与 `.gate1.lock`；未知项阻断。"""
    try:
        names = sorted(entry.name for entry in os.scandir(scope))
    except OSError as exc:
        raise HumanGate1DecisionError("enumerate", f"无法枚举 scope：{exc}") from exc
    events, lock_present = [], False
    for name in names:
        path = scope / name
        _reject_reparse_in_chain(path, name)
        if name == LOCK_FILE:
            if not path.is_file():
                _block(LOCK_FILE, "锁必须是正常文件")
            lock_present = True
            continue
        if not path.is_dir():
            _block(name, "scope 只允许本层事件目录与锁；未知项拒绝")
        events.append(path)
    return {"names": names, "events": events, "lock_present": lock_present}


# --------------------------------------------------------------------------- 封套与历史核验
def _snapshot_entries(snapshot_dir):
    """实读六份冻结快照文件，返回按文件名 UTF-8 升序的条目与解析对象。"""
    entries, parsed, buffers = [], {}, {}
    for name in SNAPSHOT_FILES:
        path = snapshot_dir / name
        if not path.is_file():
            _block(f"{SNAPSHOTS_DIR}/{name}", "缺少冻结六文件之一")
        data = _read_bytes(path, "snapshot_read", f"{SNAPSHOTS_DIR}/{name}")
        buffers[name] = data
        entries.append({"relative": name, "byte_size": len(data),
                        "file_sha256": sha256_bytes(data)})
        try:
            parsed[name] = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HumanGate1DecisionError(
                "snapshot_parse", f"{name} 无法解析：{exc}") from exc
    entries.sort(key=lambda item: item["relative"].encode("utf-8"))
    return {"entries": entries, "parsed": parsed, "buffers": buffers}


def _store_result_keys():
    return ("status", "scope", "identity", "record_fingerprint", "manifest_file_sha256",
            "execution_allowed", "workflow_connected", "ai_enabled")


def _validate_store_result(store_result, expected_status, prefix):
    store = load_frozen_store()
    _check_closed_keys(store_result, _store_result_keys(), prefix)
    if store_result["status"] != expected_status:
        _block(f"{prefix}.status", f"必须是 {expected_status!r}")
    _require_const(store_result, "scope", store.SCOPE, prefix)
    identity = _check_closed_keys(store_result["identity"], ("batch_id", "gate", "event_id"),
                                 f"{prefix}.identity")
    _require_nonempty_str(identity, "batch_id", f"{prefix}.identity")
    _require_nonempty_str(identity, "event_id", f"{prefix}.identity")
    _require_const(identity, "gate", "GATE1", f"{prefix}.identity")
    _require_hex64(store_result, "record_fingerprint", prefix)
    _require_hex64(store_result, "manifest_file_sha256", prefix)
    for key in ("execution_allowed", "workflow_connected", "ai_enabled"):
        if store_result[key] is not False:
            _block(f"{prefix}.{key}", "必须是严格 false")
    return store_result


def _store_status(kind):
    store = load_frozen_store()
    return store.STORE_STATUS_STORED if kind == "STORED" else store.STORE_STATUS_VERIFIED


def _read_event(event_dir, scope_relative, revision_expected, prior_events, prior_wrappers,
                *, verify_store=True):
    """核验一个事件目录的封套 + 冻结快照 + 历史前缀引用；返回该事件的核验结果。"""
    event_relative = event_dir.name
    try:
        names = sorted(entry.name for entry in os.scandir(event_dir))
    except OSError as exc:
        raise HumanGate1DecisionError("enumerate", f"无法枚举事件目录：{exc}") from exc
    if FAILURE_FILE in names:
        _block(f"{event_relative}/{FAILURE_FILE}", "事件目录含本层失败诊断，核验拒绝")
    if names != sorted(EVENT_FILES):
        _block(event_relative, f"事件目录条目必须恰为 {sorted(EVENT_FILES)}，实际 {names}")
    context_buffer = _read_bytes(event_dir / CONTEXT_FILE, "context_read", CONTEXT_FILE)
    receipt_buffer = _read_bytes(event_dir / RECEIPT_FILE, "receipt_read", RECEIPT_FILE)
    try:
        context = json.loads(context_buffer.decode("utf-8"))
        receipt = json.loads(receipt_buffer.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HumanGate1DecisionError("envelope_parse", f"封套无法解析：{exc}") from exc
    _check_closed_keys(context, CONTEXT_KEYS, f"{event_relative}.context")
    _check_closed_keys(receipt, RECEIPT_KEYS, f"{event_relative}.receipt")
    _require_const(context, "context_version", CONTEXT_VERSION, f"{event_relative}.context")
    _require_const(receipt, "receipt_version", RECEIPT_VERSION, f"{event_relative}.receipt")
    _require_const(receipt, "status", RECEIPT_STATUS, f"{event_relative}.receipt")
    _require_boundaries(context["boundaries"], f"{event_relative}.context.boundaries")
    _require_boundaries(receipt["boundaries"], f"{event_relative}.receipt.boundaries")
    _require_relative_str(context, "source_batch_relative",
                          f"{event_relative}.context")
    _validate_request_schema(context["request"], f"{event_relative}.context.request")
    if context["event_relative"] != event_relative:
        _block(f"{event_relative}.context.event_relative", "必须等于本事件目录叶名")
    revision = _require_strict_int(context, "revision", f"{event_relative}.context")
    if revision != revision_expected:
        _block(f"{event_relative}.context.revision",
               f"必须按技术序号严格为 {revision_expected}（实际 {revision}）")
    _require_strict_int(receipt, "revision", f"{event_relative}.receipt")
    if receipt["revision"] != revision:
        _block(f"{event_relative}.receipt.revision", "必须与 context.revision 一致")
    if receipt["context_file_sha256"] != sha256_bytes(context_buffer):
        _block(f"{event_relative}.receipt.context_file_sha256",
               "必须等于实际 context.json 字节 SHA")
    snapshots = _snapshot_entries(event_dir / SNAPSHOTS_DIR)
    if receipt["snapshot_manifest_file_sha256"] != sha256_bytes(
            snapshots["buffers"]["manifest.json"]):
        _block(f"{event_relative}.receipt.snapshot_manifest_file_sha256",
               "必须等于实际 snapshots/manifest.json 字节 SHA")
    if canonical_json_bytes(context["snapshot_files"]) != canonical_json_bytes(
            snapshots["entries"]):
        _block(f"{event_relative}.context.snapshot_files",
               "必须精确等于本事件六份快照的实际长度与 SHA（按文件名升序，规范比较）")
    request_materials, request_expectations = _validate_request_schema(
        context["request"], f"{event_relative}.context.request")
    decision_result = snapshots["parsed"]["decision_result.json"]
    _check_closed_keys(decision_result, ("record", "record_fingerprint"),
                       f"{event_relative}.decision_result")
    record = _require_object(decision_result["record"],
                             f"{event_relative}.decision_result.record")
    _require_hex64(decision_result, "record_fingerprint", f"{event_relative}.decision_result")
    for key in ("gate", "batch_id", "event_id", "decision"):
        _require_nonempty_str(record, key, f"{event_relative}.record")
    _require_const(record, "gate", "GATE1", f"{event_relative}.record")
    if record["decision"] not in DECISIONS:
        _block(f"{event_relative}.record.decision", f"必须是 {DECISIONS} 之一")
    if receipt["record_fingerprint"] != decision_result["record_fingerprint"]:
        _block(f"{event_relative}.receipt.record_fingerprint", "必须等于快照记录指纹")
    for key in ("batch_id", "event_id", "decision"):
        if receipt[key] != record[key]:
            _block(f"{event_relative}.receipt.{key}", "必须与快照记录一致")

    store_result = _validate_store_result(context["store_result"], _store_status("STORED"),
                                          f"{event_relative}.context.store_result")
    for key in ("batch_id", "event_id"):
        if store_result["identity"][key] != record[key]:
            _block(f"{event_relative}.context.store_result.identity.{key}",
                   "必须与快照记录一致")
    if store_result["record_fingerprint"] != decision_result["record_fingerprint"]:
        _block(f"{event_relative}.context.store_result.record_fingerprint", "必须等于记录指纹")
    if store_result["manifest_file_sha256"] != sha256_bytes(
            snapshots["buffers"]["manifest.json"]):
        _block(f"{event_relative}.context.store_result.manifest_file_sha256",
               "必须等于实际 manifest 字节 SHA")

    prior_scope = _check_closed_keys(context["prior_scope"], PRIOR_SCOPE_KEYS,
                                     f"{event_relative}.context.prior_scope")
    if prior_scope["scope_relative"] != scope_relative:
        _block(f"{event_relative}.context.prior_scope.scope_relative",
               "必须等于本 scope 的项目相对路径")
    if prior_scope["declared_scope"] != f"{LOCAL_SCOPE_PREFIX}{scope_relative}":
        _block(f"{event_relative}.context.prior_scope.declared_scope", "必须是本层 scope 声明")
    if canonical_json_bytes(prior_scope["prior_events"]) != canonical_json_bytes(prior_events):
        _block(f"{event_relative}.context.prior_scope.prior_events",
               "必须准确引用全部更早 revision 的实际封套与六快照（规范比较，不得遗漏）")
    _require_request_closure(request_materials, request_expectations, snapshots["parsed"],
                             record, event_relative)
    expected_history = {"declared_complete": True,
                        "declared_scope": f"{LOCAL_SCOPE_PREFIX}{scope_relative}",
                        "records": prior_wrappers}
    if canonical_json_bytes(snapshots["parsed"]["prior_history.json"]) != canonical_json_bytes(
            expected_history):
        _block(f"{event_relative}.snapshots/prior_history.json",
               "必须与本层实际枚举的历史记录一致")
    if prior_scope["prior_history_fingerprint"] != fingerprint(expected_history):
        _block(f"{event_relative}.context.prior_scope.prior_history_fingerprint",
               "必须等于完整 P1 历史对象的规范指纹")
    if verify_store:
        store = load_frozen_store()
        try:
            verified = store.verify_human_gate_decision_snapshots(event_dir / SNAPSHOTS_DIR)
        except BaseException as exc:  # noqa: BLE001
            _map_downstream(exc, "store_verify")
        _validate_store_result(verified, _store_status("VERIFIED"),
                               f"{event_relative}.store_verify")
        if verified["record_fingerprint"] != decision_result["record_fingerprint"]:
            _block(f"{event_relative}.store_verify.record_fingerprint", "与快照不一致")
    else:
        verified = None
    wrapper = {"wrapper_version": WRAPPER_VERSION,
               "record_fingerprint": decision_result["record_fingerprint"],
               "record": record}
    buffers = {"context.json": context_buffer, "receipt.json": receipt_buffer}
    for name, data in snapshots["buffers"].items():
        buffers[f"{SNAPSHOTS_DIR}/{name}"] = data
    return {"revision": revision, "event_relative": event_relative, "event_dir": event_dir,
            "context_file_sha256": sha256_bytes(context_buffer),
            "receipt_file_sha256": sha256_bytes(receipt_buffer),
            "snapshot_files": snapshots["entries"], "record": record, "wrapper": wrapper,
            "store_result": store_result, "context": context, "receipt": receipt,
            "verified_result": verified, "buffers": buffers}


def _probe_revision(event_dir):
    """只读探测单个事件的技术 revision（B2：来自**文件内严格整数**，不按叶名字典序推定）。"""
    try:
        names = sorted(entry.name for entry in os.scandir(event_dir))
    except OSError as exc:
        raise HumanGate1DecisionError("enumerate", f"无法枚举事件目录：{exc}") from exc
    if FAILURE_FILE in names:
        _block(f"{event_dir.name}/{FAILURE_FILE}", "事件目录含本层失败诊断，核验拒绝")
    if names != sorted(EVENT_FILES):
        _block(event_dir.name,
               f"事件目录条目必须恰为 {sorted(EVENT_FILES)}，实际 {names}")
    buffer = _read_bytes(event_dir / CONTEXT_FILE, "context_read", CONTEXT_FILE)
    try:
        context = json.loads(buffer.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HumanGate1DecisionError("envelope_parse",
                                      f"{event_dir.name}/context.json 无法解析：{exc}") from exc
    _require_object(context, f"{event_dir.name}.context")
    revision = _require_key(context, "revision", f"{event_dir.name}.context.revision")
    if not _is_strict_int(revision) or revision < 1:
        _block(f"{event_dir.name}.context.revision",
               f"必须是严格正整数（非 bool/float），实际 {revision!r}")
    if context.get("event_relative") != event_dir.name:
        _block(f"{event_dir.name}.context.event_relative", "必须等于本事件目录叶名")
    return revision


def _verify_history(scope, scope_relative, *, require_no_lock=False, verify_store=True):
    """实读核验本 scope 全部事件：按**文件内 revision** 建立连续唯一 1…N 合法前缀。

    枚举（含未知/失败/半写/缺 receipt/缺快照）不跳过；revision 不按叶名字典序推定；
    `prior_events` 按 revision 升序，每个前缀的 P1 records 单独按原 `event_id` UTF-8 排序唯一。
    """
    listing = _list_scope(scope)
    if require_no_lock and listing["lock_present"]:
        _block(LOCK_FILE, "scope 存在锁；只读核验拒绝")
    probed = [(_probe_revision(event_dir), event_dir) for event_dir in listing["events"]]
    revisions = sorted(item[0] for item in probed)
    if revisions != list(range(1, len(probed) + 1)):
        _block("scope_dir.revision",
               f"事件 revision 必须是连续唯一 1…N，实际 {revisions}")
    ordered = [event_dir for _revision, event_dir in sorted(probed, key=lambda item: item[0])]
    prior_events, wrappers, events = [], [], []
    for revision, event_dir in enumerate(ordered, start=1):
        record = _read_event(event_dir, scope_relative, revision, _deep(prior_events),
                             _deep(wrappers), verify_store=verify_store)
        events.append(record)
        prior_events.append({"revision": record["revision"],
                             "event_relative": record["event_relative"],
                             "context_file_sha256": record["context_file_sha256"],
                             "receipt_file_sha256": record["receipt_file_sha256"],
                             "snapshot_files": record["snapshot_files"]})
        wrappers.append(record["wrapper"])
        # 每个前缀独立按原 event_id UTF-8 排序（与保存端 prior_history.json 的写法一致）
        wrappers.sort(key=lambda item: item["record"]["event_id"].encode("utf-8"))
    ordered_wrappers = wrappers
    if len({item["record"]["event_id"] for item in ordered_wrappers}) != len(ordered_wrappers):
        _block("prior_history.records", "历史 event_id 必须唯一（相同 event_id 拒绝）")
    return {"listing": listing, "events": events, "prior_events": prior_events,
            "wrappers": ordered_wrappers,
            "prior_history": {"declared_complete": True,
                              "declared_scope": f"{LOCAL_SCOPE_PREFIX}{scope_relative}",
                              "records": ordered_wrappers}}


# --------------------------------------------------------------------------- 失败诊断
def _write_failure(event_dir, status, stage, field, reason, exc):
    """新事件失败诊断（既定七键，独占；不覆盖已有失败事实）。

    返回 `None` 表示诊断已落盘或无需落盘；返回问题记录表示**诊断写入本身失败**——
    由调用方把主错误与第二个失败一并报告，不吞掉第二次失败、不重试覆盖、不删半写现场。
    """
    path = Path(event_dir) / FAILURE_FILE
    if path.exists():
        return None
    payload = {"failure_version": FAILURE_VERSION, "status": status, "stage": stage,
               "field": field if field is not None else None, "reason": reason,
               "exception_chain": (_exception_detail(exc)["cause_chain"]
                                   if exc is not None else []),
               "boundaries": dict(BOUNDARIES)}
    try:
        _write_exclusive(path, canonical_with_lf(payload), "failure", FAILURE_FILE)
    except (HumanGate1DecisionBlocked, HumanGate1DecisionError) as write_exc:
        return {"stage": "failure_write", "type": type(write_exc).__name__,
                "message": str(write_exc), "path": _project_relative(path)}
    return None


# --------------------------------------------------------------------------- 人类提交核验
def _validate_submission(submission):
    obj = _require_object(_deep(submission), "submission")
    for key in ("event_id", "batch_id", "decision"):
        _require_nonempty_str(obj, key, "submission")
    if "gate" in obj:
        _require_const(obj, "gate", "GATE1", "submission")
    if obj["decision"] not in DECISIONS:
        _block("submission.decision", f"必须是 {DECISIONS} 之一")
    return obj


def _result(status, scope_relative, event_relative, identity, record_fingerprint, store_result):
    return {"adapter_version": ADAPTER_VERSION, "status": status, "scope": SCOPE,
            "identity": {"batch_id": identity["batch_id"], "event_id": identity["event_id"],
                         "decision": identity["decision"]},
            "record_fingerprint": record_fingerprint,
            "event_dir": f"{scope_relative}/{event_relative}",
            "scope_dir": scope_relative, "store_result": store_result,
            "boundaries": dict(BOUNDARIES)}


# --------------------------------------------------------------------------- 保存
def save_human_gate1_decision(batch_dir, request_id, submission, event_dir, *,
                              scope_dir=None):
    """显式限定历史范围（scope）并保存**这一次** Gate1 决定；止于独立记录已保存。"""
    stage = "params"
    event_target = None
    lock = None
    store_started = False
    try:
        if scope_dir is None:
            _block("scope_dir",
                   "必须由调用方显式提供并先建立（不默认空历史、不自动换 scope）")
        sub = _validate_submission(submission)
        scope = _resolve_scope_dir(scope_dir)
        scope_relative = _project_relative(scope)
        event_target = _resolve_event_dir(event_dir, scope)
        batch_path = Path(batch_dir)
        _check_path_item(batch_path, "batch_dir", must_be_file=False)
        source_batch_relative = _project_relative(batch_path)
        if not _is_nonempty_str(request_id):
            _block("request_id", "必须是非空字符串（原样保存，不归一化）")

        stage = "lock"
        lock = _acquire_scope_lock(scope)

        stage = "history"
        history = _verify_history(scope, scope_relative, verify_store=True)

        stage = "prepare"
        adapter_buffer = _adapter_bytes()
        request = _extend_request(_frozen_request(batch_path, request_id), adapter_buffer)
        if request["materials"]["batch_id"] != sub["batch_id"]:
            _block("submission.batch_id", "必须与本次实际材料批次一致")
        if any(item["record"]["event_id"] == sub["event_id"]
               for item in history["events"]):
            _block("submission.event_id", "本 scope 历史中已存在相同 event_id")

        stage = "store_save"
        store = load_frozen_store()
        store_started = True
        try:
            stored = store.save_human_gate_decision_snapshots(
                event_target / SNAPSHOTS_DIR, submission, request["materials"],
                request["expectations"], prior_history=history["prior_history"])
        except BaseException as exc:  # noqa: BLE001
            _map_downstream(exc, "store_save")
        _validate_store_result(stored, _store_status("STORED"),
                               "store_result")
        for key in ("batch_id", "event_id"):
            if stored["identity"][key] != sub[key]:
                _block(f"store_result.identity.{key}", "必须与本次提交一致")

        stage = "snapshot_readback"
        snapshots = _snapshot_entries(event_target / SNAPSHOTS_DIR)
        decision_result = snapshots["parsed"]["decision_result.json"]
        if decision_result["record_fingerprint"] != stored["record_fingerprint"]:
            _block("store_result.record_fingerprint", "必须等于实际 decision_result 记录指纹")
        if stored["manifest_file_sha256"] != sha256_bytes(
                snapshots["buffers"]["manifest.json"]):
            _block("store_result.manifest_file_sha256", "必须等于实际 manifest 字节 SHA")

        stage = "context_write"
        revision = len(history["events"]) + 1
        context = {"context_version": CONTEXT_VERSION, "revision": revision,
                   "event_relative": event_target.name,
                   "source_batch_relative": source_batch_relative, "request": request,
                   "prior_scope": {"scope_relative": scope_relative,
                                   "declared_scope": f"{LOCAL_SCOPE_PREFIX}{scope_relative}",
                                   "prior_events": history["prior_events"],
                                   "prior_history_fingerprint":
                                       fingerprint(history["prior_history"])},
                   "snapshot_files": snapshots["entries"], "store_result": stored,
                   "boundaries": dict(BOUNDARIES)}
        context_buffer = canonical_with_lf(context)
        _write_exclusive(event_target / CONTEXT_FILE, context_buffer, "context_write",
                         CONTEXT_FILE)
        if _readback(event_target / CONTEXT_FILE, context_buffer, "context_readback",
                     CONTEXT_FILE) != context:
            _block(CONTEXT_FILE, "读回对象与本次待写上下文不一致")

        stage = "receipt_write"
        receipt = {"receipt_version": RECEIPT_VERSION, "status": RECEIPT_STATUS,
                   "revision": revision,
                   "context_file_sha256": sha256_bytes(context_buffer),
                   "snapshot_manifest_file_sha256": sha256_bytes(
                       snapshots["buffers"]["manifest.json"]),
                   "record_fingerprint": stored["record_fingerprint"],
                   "batch_id": sub["batch_id"], "event_id": sub["event_id"],
                   "decision": sub["decision"], "boundaries": dict(BOUNDARIES)}
        receipt_buffer = canonical_with_lf(receipt)
        _write_exclusive(event_target / RECEIPT_FILE, receipt_buffer, "receipt_write",
                         RECEIPT_FILE)
        if _readback(event_target / RECEIPT_FILE, receipt_buffer, "receipt_readback",
                     RECEIPT_FILE) != receipt:
            _block(RECEIPT_FILE, "读回对象与本次待写回执不一致")

        stage = "final_confirmation"
        _final_confirm_decision_request(request, batch_path, adapter_buffer)
        source_snapshot = _source_snapshot(request, batch_path)
        _final_confirm_history(scope, history["events"])
        listing = _list_scope(scope)
        expected_names = sorted(history["listing"]["names"] + [event_target.name])
        if listing["names"] != expected_names:
            _block("scope_dir", "scope 成员集合只允许本次新增事件与本次锁")
        for item in history["events"]:
            if (item["event_dir"] / FAILURE_FILE).exists():
                _block(f"{item['event_relative']}/{FAILURE_FILE}",
                       "保存期间既有事件出现失败诊断")
            for name, buffer in item["buffers"].items():
                if _read_bytes(item["event_dir"] / name, "final_read", name) != buffer:
                    _block(f"{item['event_relative']}/{name}",
                           "旧事件字节在最终确认时发生变化")
        for name, buffer in {"context.json": context_buffer,
                             "receipt.json": receipt_buffer,
                             **{f"{SNAPSHOTS_DIR}/{key}": value
                                for key, value in snapshots["buffers"].items()}}.items():
            if _read_bytes(event_target / name, "final_read", name) != buffer:
                _block(f"{event_target.name}/{name}", "最终字节确认与本次待写缓冲不一致")
        if (event_target / FAILURE_FILE).exists():
            _block(FAILURE_FILE, "本次事件存在失败诊断，不能返回成功")
        # 有界终端确认：不再读 adapter/加载核心/复算语义，只做字节/集合/失败确认
        target_buffers = {"context.json": context_buffer, "receipt.json": receipt_buffer,
                          **{f"{SNAPSHOTS_DIR}/{key}": value
                             for key, value in snapshots["buffers"].items()}}
        _terminal_confirm(source_snapshot, history["events"], event_target, target_buffers,
                          scope, expected_names, batch_dir=batch_path)

        stage = "lock_release"
        _release_scope_lock(lock)
        identity = {"batch_id": sub["batch_id"], "event_id": sub["event_id"],
                    "decision": sub["decision"]}
        return _result(STATUS_RECORDED, scope_relative, event_target.name, identity,
                       stored["record_fingerprint"], stored)
    except (HumanGate1DecisionBlocked, HumanGate1DecisionError) as exc:
        problem = None
        if event_target is not None and Path(event_target).exists():
            problem = _write_failure(
                event_target,
                FAILURE_STATUS_BLOCKED if isinstance(
                    exc, HumanGate1DecisionBlocked) else FAILURE_STATUS_ERROR,
                stage, getattr(exc, "field", None), str(exc), exc)
        elif lock is not None:
            # 未创建任何事件现场（例如 P1 在建立叶目录前拒绝）：清理本次自锁；
            # 已留下现场（event_dir 存在）时保留锁，由人类决定。
            try:
                _release_scope_lock(lock)
            except (HumanGate1DecisionBlocked, HumanGate1DecisionError) as release_exc:
                problem = {"stage": "lock_release", "type": type(release_exc).__name__,
                           "message": str(release_exc), "path": _project_relative(lock["path"])}
        if problem is not None:
            combined = HumanGate1DecisionError(
                getattr(exc, "stage", stage),
                f"{exc}；收尾失败（{problem['stage']}）：{problem['type']}: "
                f"{problem['message']}（半写现场保留，未重试、未覆盖）")
            combined.__cause__ = exc
            raise combined from exc
        raise
    except BaseException as exc:  # noqa: BLE001
        wrapped = HumanGate1DecisionError(
            stage, f"意外内部错误：{type(exc).__name__}: {exc}")
        wrapped.__cause__ = exc
        problem = None
        if event_target is not None and Path(event_target).exists():
            problem = _write_failure(event_target, FAILURE_STATUS_ERROR, stage, None,
                                     str(wrapped), wrapped)
        elif lock is not None:
            try:
                _release_scope_lock(lock)
            except (HumanGate1DecisionBlocked, HumanGate1DecisionError) as release_exc:
                problem = {"stage": "lock_release", "type": type(release_exc).__name__,
                           "message": str(release_exc), "path": _project_relative(lock["path"])}
        if problem is not None:
            combined = HumanGate1DecisionError(
                stage, f"{wrapped}；收尾失败（{problem['stage']}）：{problem['type']}: "
                       f"{problem['message']}（半写现场保留，未重试、未覆盖）")
            combined.__cause__ = wrapped
            raise combined from exc
        raise wrapped from exc


def _final_confirm_history(scope, events):
    """最终确认：全部旧事件八文件字节与初始读数逐一比较（不重读业务源）。"""
    for record in events:
        for name, buffer in record["buffers"].items():
            path = record["event_dir"] / name
            if _read_bytes(path, "final_read", name) != buffer:
                _block(f"{record['event_relative']}/{name}",
                       "旧事件字节在本次保存期间发生变化")


# --------------------------------------------------------------------------- 只读核验
def verify_human_gate1_decision(event_dir, batch_dir, *, scope_dir=None):
    """只读核验已保存记录及当前来源；不写 failure、不修复/迁移历史、不能重新批准。"""
    stage = "params"
    try:
        scope = _resolve_scope_dir(scope_dir)
        scope_relative = _project_relative(scope)
        raw = Path(event_dir) if isinstance(event_dir, (str, os.PathLike)) else None
        if raw is None:
            _block("event_dir", f"必须是路径，实际 {type(event_dir).__name__}")
        _reject_reparse_in_chain(raw, "event_dir")
        target_path = raw.resolve() if raw.exists() else None
        if target_path is None or not target_path.is_dir():
            _block("event_dir", "目标事件目录必须已存在且为目录")
        if target_path.parent != scope:
            _block("event_dir", "必须是 scope_dir 的直接子目录")
        _check_path_item(Path(batch_dir), "batch_dir", must_be_file=False)

        stage = "history"
        history = _verify_history(scope, scope_relative, require_no_lock=True,
                                  verify_store=True)
        target = next((item for item in history["events"]
                       if item["event_dir"] == target_path), None)
        if target is None:
            _block("event_dir", "目标事件不在本 scope 的核验历史中")
        if target["verified_result"] is None:
            _block("store_result", "目标事件缺少冻结存储核验结果")

        stage = "current_source"
        request_id = target["context"]["request"]["expectations"]["expected_request_id"]
        adapter_buffer = _adapter_bytes()
        current = _extend_request(_frozen_request(Path(batch_dir), request_id),
                                  adapter_buffer)
        if canonical_json_bytes(current) != canonical_json_bytes(target["context"]["request"]):
            _block("current_source",
                   "当前 32 项材料/预期与已保存请求不一致；不得称旧材料决定仍可执行")
        record = target["record"]
        binding = _require_object(_require_key(record, "binding", "record.binding"),
                                  "record.binding")
        if binding.get("materials_fingerprint") != \
                current["materials"]["materials_fingerprint"]:
            _block("current_source.materials_fingerprint",
                   "当前材料指纹与已保存记录绑定不一致")

        stage = "final_confirmation"
        _final_confirm_decision_request(current, Path(batch_dir), adapter_buffer)
        source_snapshot = _source_snapshot(current, Path(batch_dir))
        listing = _list_scope(scope)
        if listing["lock_present"]:
            _block(LOCK_FILE, "scope 在核验期间出现锁")
        expected_names = sorted(name for name in history["listing"]["names"]
                                if name != LOCK_FILE)
        actual_names = sorted(item.name for item in listing["events"])
        if actual_names != expected_names:
            _block("scope_dir",
                   f"scope 事件集合在核验期间发生变化：本次枚举 {expected_names}，"
                   f"收尾复读 {actual_names}")
        for item in history["events"]:
            if (item["event_dir"] / FAILURE_FILE).exists():
                _block(f"{item['event_relative']}/{FAILURE_FILE}",
                       "核验期间出现失败诊断")
            for name, buffer in item["buffers"].items():
                if _read_bytes(item["event_dir"] / name, "final_read", name) != buffer:
                    _block(f"{item['event_relative']}/{name}", "核验期间字节发生变化")
        # 有界终端确认：在全部必要语义消费之后，只做字节/集合/失败/锁确认
        target_buffers = {name: buffer for name, buffer in target["buffers"].items()}
        _terminal_confirm(source_snapshot, history["events"], target_path,
                          target_buffers, scope, expected_names,
                          batch_dir=Path(batch_dir))

        identity = {"batch_id": record["batch_id"], "event_id": record["event_id"],
                    "decision": record["decision"]}
        return _result(STATUS_VERIFIED, scope_relative, target["event_relative"], identity,
                       target["verified_result"]["record_fingerprint"],
                       target["verified_result"])
    except (HumanGate1DecisionBlocked, HumanGate1DecisionError):
        raise
    except BaseException as exc:  # noqa: BLE001
        raise HumanGate1DecisionError(
            stage, f"意外内部错误：{type(exc).__name__}: {exc}") from exc
