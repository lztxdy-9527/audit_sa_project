# -*- coding: utf-8 -*-
"""TASK-023：Gate1 真实文件材料与只读候审请求适配器（只读准备，不保存任何 Gate 决定）。

唯一公开入口：`prepare_human_gate1_request(batch_dir, request_id) -> dict`。

本组件只做**只读准备**：从 `data/batches/` 下**仅接收阶段**目录实读八份接收材料，核验接收证据与
质量报告，映射为冻结 P1 协议的 `materials`/`expectations`，并附 `evidence`/`boundaries` 供后续
Gate 决定保存使用。它**不**保存/恢复快照、不调用存储 save/verify、不接宿主/控制器、不执行标准化/
装载/筛查、不枚举历史、不写任何文件、不生成 submission 或决定字段。

边界：`status=HUMAN_GATE1_REQUEST_PREPARED` 与质量 OK **都不是批准**；运行绑定只描述本卡已实现的
准备范围，不声称未来组件已存在。质量 OK ≠ 批次批准 ≠ 运行放行 ≠ 身份认证 ≠ 来源真实性证明。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat as stat_module
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BATCH_ROOT = PROJECT_ROOT / "data" / "batches"
RECEIVER_PATH = PROJECT_ROOT / "scripts" / "receive_demo_batch.py"
CHECKER_PATH = PROJECT_ROOT / "scripts" / "check_demo_data.py"
CONFIG_PATH = PROJECT_ROOT / "config" / "human_flow_v1.json"
CONTRACT_PATH = PROJECT_ROOT / "docs" / "AUDIT_CONTRACT.md"
EFFECTIVE_RECORD_PATH = (PROJECT_ROOT / "docs" / "decisions"
                         / "AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md")
SPEC_PATH = PROJECT_ROOT / "docs" / "SPEC_V1.md"
DRAFT_PATH = PROJECT_ROOT / "docs" / "AUDIT_CONTRACT_DRAFT.md"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "demo_schema.sql"
SELF_PATH = Path(__file__).resolve()

REQUEST_VERSION = "TASK-023-human-gate1-request-1.0"
STATUS_PREPARED = "HUMAN_GATE1_REQUEST_PREPARED"
BATCH_MANIFEST_VERSION = "TASK-003-R2-batch-manifest-1.2"
BATCH_MODE = "DEVELOPMENT_ONLY"
BATCH_STATUS_READY = "DEV_GATE1_PACKET_READY"
BATCH_STATUS_BLOCKED = "BLOCKED_QUALITY"
RECEIVER_CONTRACT_STATUS = "DRAFT_NOT_IN_FORCE"
CONTRACT_VERSION = "V1"
RULES_MANIFEST_VERSION = "TASK-006-rule-core-1.1"
GATE1 = "GATE1"

REQUEST_KEYS = ("request_version", "status", "materials", "expectations", "evidence",
                "boundaries")
MATERIALS_KEYS = ("gate", "batch_id", "run_binding", "contract_binding", "files", "quality",
                  "materials_fingerprint")
EXPECTATIONS_KEYS = ("expected_batch_id", "expected_gate", "expected_request_id",
                     "expected_materials_fingerprint", "expected_files", "expected_contract",
                     "expected_run_binding", "expected_prior_gate1")
EVIDENCE_KEYS = ("source_manifest_version", "source_batch_status", "source_receive_exit_code",
                 "source_description", "source_scope", "code_manifest", "rules_manifest")
BOUNDARY_KEYS = ("request_persisted", "decision_recorded", "execution_allowed",
                 "workflow_connected", "ai_enabled", "identity_authenticated",
                 "source_authenticity_proven")
RUN_BINDING_KEYS = ("code", "rules", "config", "input")
RUN_CODE_KEYS = ("file_sha256", "manifest_fingerprint")
RUN_RULES_KEYS = ("version", "manifest_fingerprint")
RUN_SINGLE_KEYS = ("file_sha256",)
CONTRACT_BINDING_KEYS = ("contract_version", "contract_file_sha256", "contract_effective")
FILE_ITEM_KEYS = ("relative", "file_sha256", "byte_size")
QUALITY_KEYS = ("status", "structural_blockers", "quality_blockers", "verification_failures")
CODE_MANIFEST_KEYS = ("entries",)
CODE_ENTRY_KEYS = ("relative", "file_sha256")
RULES_MANIFEST_KEYS = ("version", "entries")
RULES_ENTRY_KEYS = ("rule_id", "rule_version", "relative", "file_sha256")
CONFIG_KEYS = ("config_version", "company", "period_start", "period_end", "cutoff_date",
               "currency", "synthetic_data")
CONFIG_EXPECTED = {
    "config_version": "TASK-023-synthetic-human-flow-config-1.0",
    "company": "澄明商贸有限公司",
    "period_start": "2026-09-01",
    "period_end": "2026-09-30",
    "cutoff_date": "2026-09-30",
    "currency": "CNY",
    "synthetic_data": True,
}

BATCH_FILES = ("batch_manifest.json", "gate1_packet.md", "source/input.xlsx",
               "checks/quality_report.json", "logs/checker.stdout.txt",
               "logs/checker.stderr.txt", "code_snapshot/receive_demo_batch.py",
               "code_snapshot/check_demo_data.py")
BATCH_DIR_ENTRIES = {
    "": ("batch_manifest.json", "checks", "code_snapshot", "gate1_packet.md", "logs", "source"),
    "checks": ("quality_report.json",),
    "code_snapshot": ("check_demo_data.py", "receive_demo_batch.py"),
    "logs": ("checker.stderr.txt", "checker.stdout.txt"),
    "source": ("input.xlsx",),
}
RECEIVER_PATH_RELATIVE = "scripts/receive_demo_batch.py"
CHECKER_PATH_RELATIVE = "scripts/check_demo_data.py"

CODE_FILES = ("scripts/build_demo_fact_packet.py",
              "scripts/build_demo_human_gate_decision.py",
              "scripts/build_demo_initial_judgment.py",
              "scripts/check_demo_data.py",
              "scripts/control_demo_workflow.py",
              "scripts/crosscheck_demo_rules.py",
              "scripts/normalize_demo_data.py",
              "scripts/prepare_demo_human_gate1.py",
              "scripts/receive_demo_batch.py",
              "scripts/run_demo_workflow.py",
              "scripts/screen_demo_sqlite.py",
              "scripts/store_demo_human_gate_decision.py",
              "scripts/store_demo_sqlite.py")
RULE_FILES = ("sql/rules/r01.sql", "sql/rules/r02.sql", "sql/rules/r03.sql", "sql/rules/r04.sql")
RULE_VERSIONS = ("TASK-006-R01-1.0", "TASK-006-R02-1.0", "TASK-006-R03-1.0",
                 "TASK-006-R04-1.0")
RULE_IDS = ("R01", "R02", "R03", "R04")
# 材料逻辑名：batch/ 前缀为八份接收文件；project/ 前缀为项目侧固定清单（共 31 项）
PROJECT_MATERIAL_FILES = tuple(
    [("project/" + rel, rel) for rel in CODE_FILES]
    + [("project/docs/SPEC_V1.md", "docs/SPEC_V1.md"),
       ("project/docs/AUDIT_CONTRACT_DRAFT.md", "docs/AUDIT_CONTRACT_DRAFT.md"),
       ("project/docs/AUDIT_CONTRACT.md", "docs/AUDIT_CONTRACT.md"),
       ("project/docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md",
        "docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md"),
       ("project/config/human_flow_v1.json", "config/human_flow_v1.json"),
       ("project/sql/demo_schema.sql", "sql/demo_schema.sql")]
    + [("project/" + rel, rel) for rel in RULE_FILES])

# 独立冻结预期：来自 TASK-022-R4 已验收基线清单（**不从候选提交生成**）。
# 本适配器自身与新增固定配置不在其中：它们取本次初始实读并在收尾复测。
FROZEN_PROJECT_SHA = {
    "scripts/build_demo_fact_packet.py":
        "f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62",
    "scripts/build_demo_human_gate_decision.py":
        "5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79",
    "scripts/build_demo_initial_judgment.py":
        "0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c",
    "scripts/check_demo_data.py":
        "a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8",
    "scripts/control_demo_workflow.py":
        "a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c",
    "scripts/crosscheck_demo_rules.py":
        "8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2",
    "scripts/normalize_demo_data.py":
        "a2bae49e3686c6bca012fd4207b6a39424e21515b82af8ce8e7c05b276b72310",
    "scripts/receive_demo_batch.py":
        "5219562017d15f1f3d4e19485225568f00929fbae8b31784205de618fe941df6",
    "scripts/run_demo_workflow.py":
        "3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307",
    "scripts/screen_demo_sqlite.py":
        "1b123766b57849c1d64a5a18cb504fbeb03f563bcd96b2de708586f19c9e71fe",
    "scripts/store_demo_human_gate_decision.py":
        "594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7",
    "scripts/store_demo_sqlite.py":
        "1abfad898e18c54fd5dd81e44973d078187b2837838638c1a6f46e9c8c74a446",
    "docs/SPEC_V1.md":
        "5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236",
    "docs/AUDIT_CONTRACT_DRAFT.md":
        "af405cb6e3c4eb103b967b9520bd221a03acd266c1cd666fe79a12fe9eedca27",
    "docs/AUDIT_CONTRACT.md":
        "174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad",
    "docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md":
        "042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d",
    "sql/demo_schema.sql":
        "7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205",
    "sql/rules/r01.sql":
        "7a19ff2faba088f0b498d9c5004f0a865aac4d59b6f8ed699869051ecbe5e882",
    "sql/rules/r02.sql":
        "58af03e634008fcc61426e15a7433b6370cae0180c0436136de226b8d87b08b3",
    "sql/rules/r03.sql":
        "8a4b84d9ba0ed201ea89a6d58ea5ea67deec9ab8dbe8908e246c79c76876525a",
    "sql/rules/r04.sql":
        "b60e4db078e6632c653adb4ec20f1280c7ef58c70d4496f7caa6cb5cf567ec2d",
}

STRUCTURAL_BLOCKER_CODES = ("MISSING_SHEET", "REQUIRED_COLUMN_MISSING", "DUPLICATE_COLUMN_NAME")
ISSUE_FIELDS = ("code", "severity", "sheet", "excel_row", "column", "value", "detail")
SHEETS = ("suppliers", "payables", "payments", "allocations")
ROW_FIELDS = ("source_rows", "accepted_rows", "blocked_rows", "blank_rows")


# --------------------------------------------------------------------------- 异常
class HumanGate1RequestBlocked(Exception):
    """前提/协议/绑定/路径拒绝：可定位的 field 与 reason。"""

    def __init__(self, field, reason):
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


class HumanGate1RequestError(Exception):
    """I/O、加载或意外内部错误（保留原因链，不伪装为协议拒绝）。"""

    def __init__(self, stage, reason):
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}: {reason}")


def _block(field, reason):
    raise HumanGate1RequestBlocked(field, reason)


def _error(stage, reason):
    raise HumanGate1RequestError(stage, reason)


# --------------------------------------------------------------------------- 基础
def canonical_json_bytes(obj) -> bytes:
    """既定 canonical JSON：UTF-8 / ensure_ascii=False / sort_keys / 固定 separators。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def fingerprint(obj) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def _deep(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False))


def _is_strict_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_strict_bool(value):
    return isinstance(value, bool)


def _is_hex64(value):
    return (isinstance(value, str) and len(value) == 64
            and all(ch in "0123456789abcdef" for ch in value))


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_object(value, field):
    if not isinstance(value, dict):
        _block(field, f"必须是对象，实际 {type(value).__name__}")
    return value


def _require_str(value, field, *, nonempty=True):
    if not isinstance(value, str):
        _block(field, f"必须是字符串，实际 {type(value).__name__}")
    if nonempty and value.strip() == "":
        _block(field, "不得为空或仅空白")
    return value


def _require_strict_int(value, field, *, minimum=None):
    if not _is_strict_int(value):
        _block(field, f"必须是严格整数（bool 不冒充 int），实际 {type(value).__name__}")
    if minimum is not None and value < minimum:
        _block(field, f"必须 >= {minimum}")
    return value


def _require_strict_true(value, field):
    if value is not True:
        _block(field, f"必须是严格布尔 true（实际 {value!r}）")
    return value


def _require_key(obj, key, field):
    """必须存在的消费字段：缺键不得被 .get(None) 当成合法 null。"""
    if key not in obj:
        _block(field, "缺失必需字段（缺键不能当作合法 null）")
    return obj[key]


def _require_present_none(obj, key, field):
    _require_key(obj, key, field)
    return _require_is_none(obj[key], field)


def _require_is_none(value, field):
    if value is not None:
        _block(field, f"必须为 null（实际 {value!r}）")
    return value


def _require_hex64(value, field):
    if not _is_hex64(value):
        _block(field, "必须是完整 64 位小写十六进制")
    return value


def _check_closed_keys(obj, allowed, prefix):
    for key in sorted(obj.keys(), key=lambda item: str(item).encode("utf-8")):
        if key not in allowed:
            _block(f"{prefix}.{key}" if prefix else str(key), "未知字段（封闭键集合不允许）")
    for key in allowed:
        if key not in obj:
            _block(f"{prefix}.{key}" if prefix else key, "缺失必需字段")
    return obj


def _check_sorted_unique(items, keyfunc, field, label):
    values = [keyfunc(item) for item in items]
    for index in range(1, len(values)):
        if values[index] == values[index - 1]:
            _block(field, f"{label}存在重复项：{values[index]!r}")
        if values[index].encode("utf-8") < values[index - 1].encode("utf-8"):
            _block(field, f"{label}必须按 UTF-8 字节序升序")
    return values


# --------------------------------------------------------------------------- 路径
def _path_chain(path: Path):
    parts = path.parts
    if not parts:
        return []
    current = Path(parts[0])
    chain = [current]
    for part in parts[1:]:
        current = current / part
        chain.append(current)
    return chain


def _is_reparse_point(path: Path) -> bool:
    """lstat 检查链接/reparse；**OSError 不得被吞成 false**（映射为 Error+cause）。"""
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise HumanGate1RequestError(
            "lstat", f"无法检查路径属性 {path}：{type(exc).__name__}: {exc}") from exc
    if stat_module.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _check_path_item(raw_path: Path, field, *, must_be_file):
    """**逐级**路径检查：原始路径（含允许根与全部中间目录）无链接/reparse → resolve 复查 →
    存在性/类型。固定目录与文件的中间层级同样受检（不只批次根与叶文件）。
    """
    _reject_reparse_in_chain(raw_path, field)
    try:
        resolved = raw_path.resolve()
    except (OSError, ValueError) as exc:
        raise HumanGate1RequestError(
            "resolve", f"无法解析路径 {raw_path}：{type(exc).__name__}: {exc}") from exc
    _reject_reparse_in_chain(resolved, field)
    try:
        exists = resolved.exists()
    except OSError as exc:
        raise HumanGate1RequestError(
            "stat", f"无法检查路径是否存在 {field}：{type(exc).__name__}: {exc}") from exc
    if not exists:
        _block(field, "路径不存在")
    if must_be_file:
        try:
            is_file = resolved.is_file()
        except OSError as exc:
            raise HumanGate1RequestError(
                "stat", f"无法检查是否为正常文件 {field}：{type(exc).__name__}: {exc}") from exc
        if not is_file:
            _block(field, "必须是正常文件")
    else:
        try:
            is_dir = resolved.is_dir()
        except OSError as exc:
            raise HumanGate1RequestError(
                "stat", f"无法检查是否为目录 {field}：{type(exc).__name__}: {exc}") from exc
        if not is_dir:
            _block(field, "必须是目录")
    return resolved


def _reject_reparse_in_chain(path: Path, field):
    for node in _path_chain(path):
        try:
            exists = node.exists() or node.is_symlink()
        except OSError as exc:
            raise HumanGate1RequestError(
                "stat", f"无法检查路径 {node}：{type(exc).__name__}: {exc}") from exc
        if exists and _is_reparse_point(node):
            _block(field, f"原始路径包含符号链接/junction/reparse 点：{node.name or node}")


def _resolve_batch_dir(batch_dir) -> Path:
    """解析并校验**仅接收阶段**批次目录：`data/batches/` 的严格后代，无链接。"""
    if not isinstance(batch_dir, (str, os.PathLike)):
        _block("batch_dir", f"必须是路径字符串或 PathLike，实际 {type(batch_dir).__name__}")
    try:
        raw_abs = Path(os.path.abspath(os.fspath(batch_dir)))
    except (OSError, ValueError) as exc:
        raise HumanGate1RequestError("path", f"无法解析批次路径：{exc}") from exc
    _reject_reparse_in_chain(raw_abs, "batch_dir")
    try:
        resolved = raw_abs.resolve()
    except (OSError, ValueError) as exc:
        raise HumanGate1RequestError("path", f"无法解析批次路径：{exc}") from exc
    root = BATCH_ROOT.resolve()
    if resolved == root:
        _block("batch_dir", "批次目录不得等于允许根 data/batches/")
    if root not in resolved.parents:
        _block("batch_dir", "批次目录必须是允许根 data/batches/ 的严格后代")
    _reject_reparse_in_chain(resolved, "batch_dir")
    if not resolved.exists():
        _block("batch_dir", "批次目录不存在")
    if not resolved.is_dir():
        _block("batch_dir", "批次目录必须是目录")
    return resolved


def _read_bytes(path: Path, stage: str, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise HumanGate1RequestError(
            stage, f"无法读取 {label}：{type(exc).__name__}: {exc}") from exc


def _check_batch_layout(target: Path):
    """固定恰八文件：目录条目集合必须**仅由这些路径推导**；每个消费路径**逐级**无链接。"""
    for sub, expected in BATCH_DIR_ENTRIES.items():
        directory = target if sub == "" else target / sub
        if sub != "":
            _check_path_item(directory, f"batch_dir.{sub}", must_be_file=False)
        try:
            actual = sorted(entry.name for entry in directory.iterdir())
        except OSError as exc:
            raise HumanGate1RequestError(
                "enumerate", f"无法枚举 {sub or '.'}：{type(exc).__name__}: {exc}") from exc
        if actual != sorted(expected):
            extra = sorted(set(actual) - set(expected))
            missing = sorted(set(expected) - set(actual))
            _block("batch_dir",
                   f"{sub or '.'} 条目集合必须恰为固定集合；多余={extra} 缺失={missing}")
    for relative in BATCH_FILES:
        _check_path_item(target / relative, relative, must_be_file=True)


# --------------------------------------------------------------------------- 冻结接收器 helper
_RECEIVER_CACHE = {"module": None}


def _load_receiver_module():
    """只加载冻结接收器模块以复用只读 `validate_report`；不执行其 CLI、不导入下游核心。"""
    cached = _RECEIVER_CACHE["module"]
    if cached is not None:
        return cached
    name = "receive_demo_batch_frozen_for_task023"
    module = sys.modules.get(name)
    if module is not None:
        _RECEIVER_CACHE["module"] = module
        return module
    try:
        spec = importlib.util.spec_from_file_location(name, RECEIVER_PATH)
        if spec is None or spec.loader is None:
            _error("receiver_load", f"无法为冻结接收器建立 spec：{RECEIVER_PATH}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    except (OSError, ImportError) as exc:
        sys.modules.pop(name, None)
        raise HumanGate1RequestError(
            "receiver_load", f"加载冻结接收器失败（{type(exc).__name__}: {exc}）") from exc
    _RECEIVER_CACHE["module"] = module
    return module


def _validate_report(report):
    """调用冻结接收器的只读结构验证；返回其原样 problems 列表（不执行其 CLI）。"""
    module = _load_receiver_module()
    helper = getattr(module, "validate_report", None)
    if not callable(helper):
        _error("receiver_load", "冻结接收器未提供可调用的 validate_report")
    try:
        problems = helper(report)
    except Exception as exc:  # noqa: BLE001 - 加载/结构异常按运行错误保留原因链
        raise HumanGate1RequestError(
            "validate_report", f"冻结接收器 validate_report 抛出异常："
                               f"{type(exc).__name__}: {exc}") from exc
    if not isinstance(problems, list):
        _error("validate_report", f"validate_report 必须返回列表，实际 {type(problems).__name__}")
    return problems


# --------------------------------------------------------------------------- 批次证据核验
def _verify_manifest(manifest, batch_id, input_bytes, input_sha, snapshot_shas):
    _require_object(manifest, "batch_manifest.json")
    if manifest.get("manifest_version") != BATCH_MANIFEST_VERSION:
        _block("batch_manifest.json.manifest_version",
               f"必须是 {BATCH_MANIFEST_VERSION!r}（实际 {manifest.get('manifest_version')!r}）")
    if manifest.get("batch_id") != batch_id:
        _block("batch_manifest.json.batch_id", "必须与批次叶目录名精确一致")
    if manifest.get("mode") != BATCH_MODE:
        _block("batch_manifest.json.mode", f"必须是 {BATCH_MODE!r}")
    if manifest.get("contract_status") != RECEIVER_CONTRACT_STATUS:
        _block("batch_manifest.json.contract_status",
               f"必须是接收器原始标签 {RECEIVER_CONTRACT_STATUS!r}")
    receive_exit = _require_strict_int(manifest.get("receive_exit_code"),
                                       "batch_manifest.json.receive_exit_code", minimum=0)
    _require_present_none(manifest, "gate1_approval", "batch_manifest.json.gate1_approval")
    _require_present_none(manifest, "gate2_approval", "batch_manifest.json.gate2_approval")
    if manifest.get("next_step_allowed") is not False:
        _block("batch_manifest.json.next_step_allowed", "必须是严格布尔 false")

    failure = _require_object(manifest.get("failure"), "batch_manifest.json.failure")
    _require_present_none(failure, "stage", "batch_manifest.json.failure.stage")
    for key in ("exceptions", "material_write_failures"):
        if failure.get(key) != []:
            _block(f"batch_manifest.json.failure.{key}", "必须为空列表")
    if manifest.get("failure_reasons") != []:
        _block("batch_manifest.json.failure_reasons", "必须为空列表")

    report_validation = _require_object(manifest.get("report_validation"),
                                        "batch_manifest.json.report_validation")
    _require_strict_true(report_validation.get("attempted"),
                         "batch_manifest.json.report_validation.attempted")
    _require_strict_true(report_validation.get("valid"),
                         "batch_manifest.json.report_validation.valid")
    _require_strict_true(report_validation.get("report_readable"),
                         "batch_manifest.json.report_validation.report_readable")
    if report_validation.get("problems") != []:
        _block("batch_manifest.json.report_validation.problems", "必须为空列表")

    hashes = _require_object(manifest.get("hashes"), "batch_manifest.json.hashes")
    _require_strict_true(hashes.get("snapshot_written"),
                         "batch_manifest.json.hashes.snapshot_written")
    _require_strict_true(hashes.get("snapshot_matches_source"),
                         "batch_manifest.json.hashes.snapshot_matches_source")
    for key in ("source_before_copy", "source_after_copy", "source_after_check",
                "snapshot_after_copy", "snapshot_after_check"):
        if hashes.get(key) != input_sha:
            _block(f"batch_manifest.json.hashes.{key}",
                   "必须与实际 input 字节 SHA-256 全等")
    # B1.2 接收器/材料声明必须与**同次真实读数**及冻结项目文件闭合
    for label, relative, frozen_key in (
            ("receive_script", RECEIVER_PATH_RELATIVE, "scripts/receive_demo_batch.py"),
            ("checker", CHECKER_PATH_RELATIVE, "scripts/check_demo_data.py")):
        section = _require_object(hashes.get(label), f"batch_manifest.json.hashes.{label}")
        if section.get("path") != relative:
            _block(f"batch_manifest.json.hashes.{label}.path",
                   f"必须是固定相对路径 {relative!r}（实际 {section.get('path')!r}）")
        before = _require_key(section, "sha256_before_run",
                              f"batch_manifest.json.hashes.{label}.sha256_before_run")
        end = _require_key(section, "sha256_at_end",
                           f"batch_manifest.json.hashes.{label}.sha256_at_end")
        _require_hex64(before, f"batch_manifest.json.hashes.{label}.sha256_before_run")
        _require_hex64(end, f"batch_manifest.json.hashes.{label}.sha256_at_end")
        if before != end:
            _block(f"batch_manifest.json.hashes.{label}.sha256_at_end",
                   "运行前后 SHA 必须一致（声明自相矛盾）")
        _require_strict_true(_require_key(section, "stable_during_run",
                                          f"batch_manifest.json.hashes.{label}.stable_during_run"),
                             f"batch_manifest.json.hashes.{label}.stable_during_run")
        if end != FROZEN_PROJECT_SHA[frozen_key]:
            _block(f"batch_manifest.json.hashes.{label}.sha256_at_end",
                   "必须与独立冻结的项目接收器/checker 字节 SHA 一致")
    for label, relative, frozen_key in (
            ("spec", "docs/SPEC_V1.md", "docs/SPEC_V1.md"),
            ("contract_draft", "docs/AUDIT_CONTRACT_DRAFT.md", "docs/AUDIT_CONTRACT_DRAFT.md")):
        section = _require_object(hashes.get(label), f"batch_manifest.json.hashes.{label}")
        if section.get("path") != relative:
            _block(f"batch_manifest.json.hashes.{label}.path",
                   f"必须是固定相对路径 {relative!r}（实际 {section.get('path')!r}）")
        _require_strict_true(_require_key(section, "exists",
                                          f"batch_manifest.json.hashes.{label}.exists"),
                             f"batch_manifest.json.hashes.{label}.exists")
        _require_present_none(section, "read_error",
                              f"batch_manifest.json.hashes.{label}.read_error")
        if section.get("sha256") != FROZEN_PROJECT_SHA[frozen_key]:
            _block(f"batch_manifest.json.hashes.{label}.sha256",
                   "必须与独立冻结的项目文件字节 SHA 一致")

    source_reading = _require_object(hashes.get("source_reading"),
                                     "batch_manifest.json.hashes.source_reading")
    if source_reading.get("sha256") != input_sha:
        _block("batch_manifest.json.hashes.source_reading.sha256", "必须与实际 input 字节 SHA 一致")
    _require_strict_true(source_reading.get("exists"),
                         "batch_manifest.json.hashes.source_reading.exists")
    _require_present_none(source_reading, "read_error",
                          "batch_manifest.json.hashes.source_reading.read_error")

    source = _require_object(manifest.get("source"), "batch_manifest.json.source")
    size = source.get("size_bytes")
    if not _is_strict_int(size) or size != len(input_bytes):
        _block("batch_manifest.json.source.size_bytes", "必须与实际 input 字节长度一致（严格整数）")
    _require_str(source.get("source_description"),
                 "batch_manifest.json.source.source_description", nonempty=False)

    invocation = _require_object(manifest.get("checker_invocation"),
                                 "batch_manifest.json.checker_invocation")
    _require_strict_true(invocation.get("attempted"),
                         "batch_manifest.json.checker_invocation.attempted")
    _require_strict_true(invocation.get("started"),
                         "batch_manifest.json.checker_invocation.started")
    checker_exit = _require_strict_int(invocation.get("exit_code"),
                                       "batch_manifest.json.checker_invocation.exit_code",
                                       minimum=0)
    for key, relative in (("report", "checks/quality_report.json"),
                          ("stdout_log", "logs/checker.stdout.txt"),
                          ("stderr_log", "logs/checker.stderr.txt")):
        section = _require_object(invocation.get(key), f"batch_manifest.json.checker_invocation.{key}")
        if section.get("path") != relative:
            _block(f"batch_manifest.json.checker_invocation.{key}.path",
                   f"必须是固定相对路径 {relative!r}（实际 {section.get('path')!r}）")
        _require_strict_true(section.get("exists"),
                             f"batch_manifest.json.checker_invocation.{key}.exists")
        _require_present_none(section, "read_error",
                             f"batch_manifest.json.checker_invocation.{key}.read_error")
        if section.get("sha256") != snapshot_shas[relative]:
            _block(f"batch_manifest.json.checker_invocation.{key}.sha256",
                   "必须与本次初始实读字节 SHA-256 全等")
    report_section = invocation["report"]
    if report_section.get("sha256") != snapshot_shas["checks/quality_report.json"]:
        _block("batch_manifest.json.checker_invocation.report.sha256", "与本次报告字节不一致")
    if invocation.get("report_workbook_sha256") != input_sha:
        _block("batch_manifest.json.checker_invocation.report_workbook_sha256",
               "必须与本次 input 字节 SHA 一致")
    report_result = _require_key(invocation, "report_result",
                                 "batch_manifest.json.checker_invocation.report_result")
    if report_result not in ("pass", "issues_found"):
        _block("batch_manifest.json.checker_invocation.report_result",
               f"必须为 'pass' 或 'issues_found'（实际 {report_result!r}）")
    report_checker_sha = _require_key(
        invocation, "report_checker_sha256",
        "batch_manifest.json.checker_invocation.report_checker_sha256")
    _require_hex64(report_checker_sha,
                   "batch_manifest.json.checker_invocation.report_checker_sha256")
    if report_checker_sha != FROZEN_PROJECT_SHA["scripts/check_demo_data.py"]:
        _block("batch_manifest.json.checker_invocation.report_checker_sha256",
               "必须与独立冻结的 checker 字节 SHA 一致")
    if invocation.get("report_matches_snapshot") is not True:
        _block("batch_manifest.json.checker_invocation.report_matches_snapshot",
               "必须是严格布尔 true")
    if invocation.get("report_matches_checker") is not True:
        _block("batch_manifest.json.checker_invocation.report_matches_checker",
               "必须是严格布尔 true")

    packet = _require_object(manifest.get("gate1_packet"), "batch_manifest.json.gate1_packet")
    if packet.get("path") != "gate1_packet.md":
        _block("batch_manifest.json.gate1_packet.path", "必须是固定相对路径 'gate1_packet.md'")
    _require_strict_true(packet.get("exists"), "batch_manifest.json.gate1_packet.exists")
    _require_present_none(packet, "read_error", "batch_manifest.json.gate1_packet.read_error")
    if packet.get("sha256") != snapshot_shas["gate1_packet.md"]:
        _block("batch_manifest.json.gate1_packet.sha256", "必须与本次初始实读字节 SHA 全等")

    code_snapshot = _require_object(manifest.get("code_snapshot"),
                                    "batch_manifest.json.code_snapshot")
    for name, expected_path in (("receive_demo_batch.py", "code_snapshot/receive_demo_batch.py"),
                                ("check_demo_data.py", "code_snapshot/check_demo_data.py")):
        entry = _require_object(code_snapshot.get(name),
                                f"batch_manifest.json.code_snapshot.{name}")
        if entry.get("path") != expected_path:
            _block(f"batch_manifest.json.code_snapshot.{name}.path",
                   f"必须是固定相对路径 {expected_path!r}")
        _require_strict_true(entry.get("exists"),
                             f"batch_manifest.json.code_snapshot.{name}.exists")
        _require_present_none(entry, "read_error",
                             f"batch_manifest.json.code_snapshot.{name}.read_error")
        actual = snapshot_shas[expected_path]
        for key in ("sha256", "expected_sha256"):
            if entry.get(key) != actual:
                _block(f"batch_manifest.json.code_snapshot.{name}.{key}",
                       "必须与本次快照字节 SHA-256 全等")
        if entry.get("matches_source") is not True:
            _block(f"batch_manifest.json.code_snapshot.{name}.matches_source",
                   "必须是严格布尔 true")

    scope = _require_object(manifest.get("expected_scope"), "batch_manifest.json.expected_scope")
    return {"receive_exit_code": receive_exit, "checker_exit_code": checker_exit,
            "report_result": report_result,
            "batch_status": manifest.get("batch_status"), "scope": scope,
            "source_description": source.get("source_description"),
            "manifest_version": manifest.get("manifest_version")}


def _verify_scope_against_config(scope, config):
    for key in ("company", "period_start", "period_end", "currency"):
        if scope.get(key) != config[key]:
            _block(f"batch_manifest.json.expected_scope.{key}",
                   f"必须与固定配置一致（配置 {config[key]!r}，实际 {scope.get(key)!r}）")
    if scope.get("as_of_date") != config["cutoff_date"]:
        _block("batch_manifest.json.expected_scope.as_of_date",
               "必须与固定配置 cutoff_date 一致")


def _verify_quality_report(report, meta, input_sha, checker_sha):
    """核验质量报告并映射为 P1 质量对象（只映射 checker 实际 issues，不另加规则）。"""
    _require_object(report, "checks/quality_report.json")
    problems = _validate_report(report)
    if problems:
        _block("checks/quality_report.json", f"冻结 validate_report 报告结构问题：{problems[:3]}")

    result = _require_key(report, "result", "checks/quality_report.json.result")
    declared = meta.get("report_result")
    if declared is not None and result != declared:
        _block("checks/quality_report.json.result",
               f"必须与 manifest 声明 report_result 一致（声明 {declared!r}，报告 {result!r}）")
    if result not in ("pass", "issues_found"):
        _block("checks/quality_report.json.result",
               f"必须为 'pass' 或 'issues_found'（实际 {result!r}）")

    workbook = _require_object(report.get("workbook"), "checks/quality_report.json.workbook")
    if workbook.get("sha256") != input_sha:
        _block("checks/quality_report.json.workbook.sha256", "必须与本次 input 字节 SHA 一致")
    size = workbook.get("size_bytes")
    if not _is_strict_int(size) or size != meta["input_size"]:
        _block("checks/quality_report.json.workbook.size_bytes",
               "必须与本次 input 字节长度一致（严格整数）")
    workbook_path = workbook.get("path")
    if not isinstance(workbook_path, str):
        _block("checks/quality_report.json.workbook.path", "必须是字符串")
    try:
        resolved_workbook = Path(os.path.abspath(workbook_path)).resolve()
    except (OSError, ValueError) as exc:
        raise HumanGate1RequestError(
            "quality", f"无法解析 workbook.path：{exc}") from exc
    if resolved_workbook != meta["input_path"]:
        _block("checks/quality_report.json.workbook.path",
               "必须精确指向本次批次快照 source/input.xlsx")

    checker = _require_object(report.get("checker"), "checks/quality_report.json.checker")
    if checker.get("sha256") != checker_sha:
        _block("checks/quality_report.json.checker.sha256",
               "必须与本次冻结 checker 字节 SHA 一致")

    row_accounting = _require_object(report.get("row_accounting"),
                                     "checks/quality_report.json.row_accounting")
    for sheet in SHEETS:
        accounting = _require_object(row_accounting.get(sheet),
                                     f"checks/quality_report.json.row_accounting.{sheet}")
        for field in ROW_FIELDS:
            _require_strict_int(accounting.get(field),
                                f"checks/quality_report.json.row_accounting.{sheet}.{field}",
                                minimum=0)
        if not _is_strict_bool(accounting.get("structural_block")):
            _block(f"checks/quality_report.json.row_accounting.{sheet}.structural_block",
                   f"必须是严格布尔（实际 {accounting.get('structural_block')!r}）")
        if accounting["source_rows"] != accounting["accepted_rows"] + accounting["blocked_rows"]:
            _block(f"checks/quality_report.json.row_accounting.{sheet}",
                   "来源业务行数必须等于接受行数加隔离行数（勾稽不符，不补零）")

    issues = report.get("issues")
    if not isinstance(issues, list):
        _block("checks/quality_report.json.issues",
               f"必须是数组（实际 {type(issues).__name__}）")
    counts = report.get("issue_counts_by_code")
    if not isinstance(counts, dict):
        _block("checks/quality_report.json.issue_counts_by_code",
               f"必须是对象（实际 {type(counts).__name__}）")

    if result == "pass":
        if meta["receive_exit_code"] != 0 or meta["checker_exit_code"] != 0:
            _block("checks/quality_report.json.result",
                   "result=pass 但接收/检查退出码不是 0（状态矛盾）")
        if meta["batch_status"] != BATCH_STATUS_READY:
            _block("batch_manifest.json.batch_status",
                   f"result=pass 时批次状态必须是 {BATCH_STATUS_READY!r}")
        if issues:
            _block("checks/quality_report.json.issues", "result=pass 时 issues 必须为空")
        if counts != {}:
            _block("checks/quality_report.json.issue_counts_by_code",
                   "result=pass 时 issue_counts_by_code 必须为空对象")
        for sheet in SHEETS:
            accounting = row_accounting[sheet]
            if accounting["structural_block"] is not False:
                _block(f"checks/quality_report.json.row_accounting.{sheet}.structural_block",
                       "质量 OK 时四表 structural_block 必须严格 false")
            if accounting["blocked_rows"] != 0:
                _block(f"checks/quality_report.json.row_accounting.{sheet}.blocked_rows",
                       "质量 OK 时 blocked_rows 必须严格整数 0")
        return dict(meta, quality={"status": "OK", "structural_blockers": [],
                                   "quality_blockers": [], "verification_failures": []},
                    mapped_codes={})

    # issues_found：合法质量问题（供未来 HOLD/REJECT），映射为 P1 BLOCKED
    if meta["receive_exit_code"] != 1 or meta["checker_exit_code"] != 1:
        _block("checks/quality_report.json.result",
               "result=issues_found 但接收/检查退出码不是 1（状态矛盾，不把运行失败当质量问题）")
    if meta["batch_status"] != BATCH_STATUS_BLOCKED:
        _block("batch_manifest.json.batch_status",
               f"result=issues_found 时批次状态必须是 {BATCH_STATUS_BLOCKED!r}")
    if not issues:
        _block("checks/quality_report.json.issues", "result=issues_found 时 issues 不得为空")

    encoded, structural, quality_blockers, actual_counts = [], [], [], {}
    for index, issue in enumerate(issues):
        _require_object(issue, f"checks/quality_report.json.issues[{index}]")
        _check_closed_keys(issue, ISSUE_FIELDS, f"checks/quality_report.json.issues[{index}]")
        code = _require_str(issue["code"], f"checks/quality_report.json.issues[{index}].code")
        _require_str(issue["detail"], f"checks/quality_report.json.issues[{index}].detail")
        canonical = canonical_json_bytes(issue).decode("utf-8")
        encoded.append(f"issues[{index:08d}]:{canonical}")
        actual_counts[code] = actual_counts.get(code, 0) + 1
        if code in STRUCTURAL_BLOCKER_CODES:
            structural.append(encoded[-1])
        else:
            quality_blockers.append(encoded[-1])

    if counts != actual_counts:
        _block("checks/quality_report.json.issue_counts_by_code",
               "必须与实际 issues 按 code 的统计严格相等（不补零、不筛除）")
    for code, value in counts.items():
        _require_strict_int(value, f"checks/quality_report.json.issue_counts_by_code.{code}",
                            minimum=1)
    structural.sort(key=lambda item: item.encode("utf-8"))
    quality_blockers.sort(key=lambda item: item.encode("utf-8"))
    return dict(meta, quality={"status": "BLOCKED", "structural_blockers": structural,
                              "quality_blockers": quality_blockers,
                              "verification_failures": []},
                mapped_codes=dict(actual_counts))


# --------------------------------------------------------------------------- 清单与配置
def _verify_frozen_project_files(project_reads):
    """B1.1：**所有既有项目材料**逐项与独立冻结 SHA 比较（统一小范围校验）。"""
    for relative, expected in sorted(FROZEN_PROJECT_SHA.items()):
        if relative not in project_reads:
            _error("frozen_check", f"冻结清单中的 {relative} 未被实读")
        actual = _sha_bytes(project_reads[relative])
        if actual != expected:
            _block(relative, "与独立冻结预期不一致（既有文件不得变化）")
    return True


def _build_code_manifest(initial_reads):
    entries = []
    for relative in CODE_FILES:
        data = initial_reads[relative]
        actual = _sha_bytes(data)
        expected = FROZEN_PROJECT_SHA.get(relative)
        if expected is not None and actual != expected:
            _block(relative, "与已验收基线冻结 SHA 不一致（既有文件不得变化）")
        entries.append({"relative": relative, "file_sha256": actual})
    _check_sorted_unique(entries, lambda item: item["relative"], "code_manifest.entries",
                         "代码清单")
    return {"entries": entries}


def _build_rules_manifest(initial_reads):
    entries = []
    for index, relative in enumerate(RULE_FILES):
        data = initial_reads[relative]
        actual = _sha_bytes(data)
        expected = FROZEN_PROJECT_SHA.get(relative)
        if expected is not None and actual != expected:
            _block(relative, "与已验收基线冻结 SHA 不一致（规则文件不得变化）")
        entries.append({"rule_id": RULE_IDS[index], "rule_version": RULE_VERSIONS[index],
                        "relative": relative, "file_sha256": actual})
    _check_sorted_unique(entries, lambda item: item["rule_id"], "rules_manifest.entries",
                         "规则清单")
    _check_sorted_unique(entries, lambda item: item["relative"], "rules_manifest.entries",
                         "规则清单")
    return {"version": RULES_MANIFEST_VERSION, "entries": entries}


def _verify_config(config_bytes):
    try:
        config = json.loads(config_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _block("config/human_flow_v1.json",
               f"必须是可解析的 UTF-8 JSON：{type(exc).__name__}: {exc}")
    _require_object(config, "config/human_flow_v1.json")
    _check_closed_keys(config, CONFIG_KEYS, "config/human_flow_v1.json")
    for key in CONFIG_KEYS:
        expected = CONFIG_EXPECTED[key]
        actual = config[key]
        if isinstance(expected, bool):
            if actual is not expected:
                _block(f"config/human_flow_v1.json.{key}",
                       f"必须是严格布尔 {expected}（实际 {actual!r}，整数不得冒充）")
        elif not isinstance(actual, str) or actual != expected:
            _block(f"config/human_flow_v1.json.{key}",
                   f"必须是固定字符串 {expected!r}（实际 {actual!r}）")
    if config_bytes != canonical_json_bytes(config) + b"\n":
        _block("config/human_flow_v1.json", "必须是 canonical JSON 加单个 LF（不得有多余空白）")
    return config


# --------------------------------------------------------------------------- 组装
def _material_relative(logical):
    if logical.startswith("batch/"):
        return logical
    return logical


def _build_files_entries(batch_reads, project_reads, batch_relatives):
    items = []
    for relative in batch_relatives:
        items.append({"relative": "batch/" + relative,
                      "file_sha256": _sha_bytes(batch_reads[relative]),
                      "byte_size": len(batch_reads[relative])})
    for logical, project_relative in PROJECT_MATERIAL_FILES:
        data = project_reads[project_relative]
        items.append({"relative": logical, "file_sha256": _sha_bytes(data),
                      "byte_size": len(data)})
    items.sort(key=lambda item: item["relative"].encode("utf-8"))
    _check_sorted_unique(items, lambda item: item["relative"], "materials.files", "材料名单")
    if len(items) != 31:
        _error("assemble", f"材料名单必须恰 31 项，实际 {len(items)}")
    return items


def _assemble_request(request_id, batch_id, code_manifest, rules_manifest, config,
                      config_sha, files_entries, quality, input_sha, adapter_sha,
                      evidence):
    run_binding = {
        "code": {"file_sha256": adapter_sha,
                 "manifest_fingerprint": fingerprint(code_manifest)},
        "rules": {"version": RULES_MANIFEST_VERSION,
                  "manifest_fingerprint": fingerprint(rules_manifest)},
        "config": {"file_sha256": config_sha},
        "input": {"file_sha256": input_sha},
    }
    contract_binding = {"contract_version": CONTRACT_VERSION,
                        "contract_file_sha256": FROZEN_PROJECT_SHA["docs/AUDIT_CONTRACT.md"],
                        "contract_effective": True}
    materials = {"gate": GATE1, "batch_id": batch_id, "run_binding": run_binding,
                 "contract_binding": contract_binding, "files": files_entries,
                 "quality": quality, "materials_fingerprint": ""}
    materials["materials_fingerprint"] = fingerprint(
        {key: value for key, value in materials.items() if key != "materials_fingerprint"})
    expectations = {
        "expected_batch_id": batch_id,
        "expected_gate": GATE1,
        "expected_request_id": request_id,
        "expected_materials_fingerprint": materials["materials_fingerprint"],
        "expected_files": {item["relative"]: item["file_sha256"] for item in files_entries},
        "expected_contract": {"contract_version": CONTRACT_VERSION,
                              "contract_file_sha256": contract_binding["contract_file_sha256"]},
        "expected_run_binding": _deep(run_binding),
        "expected_prior_gate1": None,
    }
    boundaries = {key: False for key in BOUNDARY_KEYS}
    return {"request_version": REQUEST_VERSION, "status": STATUS_PREPARED,
            "materials": materials, "expectations": expectations,
            "evidence": evidence, "boundaries": boundaries}


# --------------------------------------------------------------------------- 公开入口
def prepare_human_gate1_request(batch_dir, request_id) -> dict:
    """从**仅接收阶段**批次目录只读准备 Gate1 候审请求（材料 + 独立预期）。

    不写任何文件、不保存/恢复快照、不调用冻结 P1 或存储、不接宿主/控制器。
    """
    stage = "request_id"
    if not isinstance(request_id, str):
        _block("request_id", f"必须是字符串，实际 {type(request_id).__name__}")
    if request_id.strip() == "":
        _block("request_id", "不得为空或仅空白")

    stage = "path"
    target = _resolve_batch_dir(batch_dir)
    batch_id = target.name
    _check_batch_layout(target)

    stage = "read_batch"
    batch_reads, batch_parsed = {}, {}
    for relative in BATCH_FILES:
        data = _read_bytes(target / relative, "read_batch", relative)
        batch_reads[relative] = data
        if relative.endswith(".json"):
            try:
                batch_parsed[relative] = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                _block(relative, f"必须是可解析的 UTF-8 JSON：{type(exc).__name__}: {exc}")
    input_bytes = batch_reads["source/input.xlsx"]
    input_sha = _sha_bytes(input_bytes)
    input_path = (target / "source/input.xlsx").resolve()
    snapshot_shas = {relative: _sha_bytes(batch_reads[relative]) for relative in BATCH_FILES}

    stage = "manifest"
    meta = _verify_manifest(batch_parsed["batch_manifest.json"], batch_id, input_bytes,
                            input_sha, snapshot_shas)
    meta["input_size"] = len(input_bytes)
    meta["input_path"] = input_path

    stage = "project_reads"
    project_reads = {}
    plan = [("config/human_flow_v1.json", CONFIG_PATH),
            ("docs/SPEC_V1.md", SPEC_PATH),
            ("docs/AUDIT_CONTRACT_DRAFT.md", DRAFT_PATH),
            ("docs/AUDIT_CONTRACT.md", CONTRACT_PATH),
            ("docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md",
             EFFECTIVE_RECORD_PATH),
            ("sql/demo_schema.sql", SCHEMA_PATH)]
    plan += [(relative, PROJECT_ROOT / relative) for relative in CODE_FILES]
    plan += [(relative, PROJECT_ROOT / relative) for relative in RULE_FILES]
    for relative, path in plan:
        _check_path_item(path, relative, must_be_file=True)
        project_reads[relative] = _read_bytes(path, "project_reads", relative)
    adapter_sha = _sha_bytes(project_reads["scripts/prepare_demo_human_gate1.py"])

    stage = "config"
    config = _verify_config(project_reads["config/human_flow_v1.json"])
    config_sha = _sha_bytes(project_reads["config/human_flow_v1.json"])

    stage = "scope"
    _verify_scope_against_config(meta["scope"], config)

    stage = "contract"
    if _sha_bytes(project_reads["docs/AUDIT_CONTRACT.md"]) != FROZEN_PROJECT_SHA[
            "docs/AUDIT_CONTRACT.md"]:
        _block("docs/AUDIT_CONTRACT.md", "与独立冻结预期不一致（正式契约不得变化）")
    if _sha_bytes(project_reads[
            "docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md"]) != \
            FROZEN_PROJECT_SHA["docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md"]:
        _block("docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md",
               "与独立冻结预期不一致（生效登记不得变化）")

    stage = "frozen_expected"
    _verify_frozen_project_files(project_reads)

    stage = "manifests"
    code_manifest = _build_code_manifest(project_reads)
    rules_manifest = _build_rules_manifest(project_reads)

    stage = "quality"
    checker_sha = _sha_bytes(project_reads["scripts/check_demo_data.py"])
    if snapshot_shas["code_snapshot/check_demo_data.py"] != checker_sha:
        _block("code_snapshot/check_demo_data.py",
               "快照必须与项目冻结 checker 字节 SHA-256 一致")
    if snapshot_shas["code_snapshot/receive_demo_batch.py"] != _sha_bytes(
            project_reads["scripts/receive_demo_batch.py"]):
        _block("code_snapshot/receive_demo_batch.py",
               "快照必须与项目冻结接收器字节 SHA-256 一致")
    quality_meta = _verify_quality_report(batch_parsed["checks/quality_report.json"], meta,
                                          input_sha, checker_sha)
    quality = quality_meta["quality"]

    stage = "assemble"
    files_entries = _build_files_entries(batch_reads, project_reads, BATCH_FILES)
    evidence = {"source_manifest_version": meta["manifest_version"],
                "source_batch_status": meta["batch_status"],
                "source_receive_exit_code": meta["receive_exit_code"],
                "source_description": meta["source_description"],
                "source_scope": _deep(meta["scope"]),
                "code_manifest": _deep(code_manifest),
                "rules_manifest": _deep(rules_manifest)}
    _check_closed_keys(evidence, EVIDENCE_KEYS, "evidence")
    request = _assemble_request(request_id, batch_id, code_manifest, rules_manifest, config,
                                config_sha, files_entries, quality, input_sha, adapter_sha,
                                evidence)
    _check_closed_keys(request, REQUEST_KEYS, "request")
    _check_closed_keys(request["materials"], MATERIALS_KEYS, "materials")
    _check_closed_keys(request["expectations"], EXPECTATIONS_KEYS, "expectations")
    _check_closed_keys(request["boundaries"], BOUNDARY_KEYS, "boundaries")
    for key in BOUNDARY_KEYS:
        if request["boundaries"][key] is not False:
            _block(f"boundaries.{key}", "必须是严格布尔 false")

    # 全部必要消费完成后、返回成功前：再实读 31 文件并逐项比较，复查路径集合与无链接
    stage = "final_confirmation"
    _final_confirm(target, batch_reads, project_reads)
    stage = "deepcopy"
    return _deep(request)


def _final_confirm(target: Path, batch_reads, project_reads):
    _check_batch_layout(target)
    for _logical, project_relative in PROJECT_MATERIAL_FILES:
        _check_path_item(PROJECT_ROOT / project_relative, _logical, must_be_file=True)
    for relative in BATCH_FILES:
        data = _read_bytes(target / relative, "final_read", relative)
        if _sha_bytes(data) != _sha_bytes(batch_reads[relative]) or len(data) != len(
                batch_reads[relative]):
            _block(relative, "全部必要消费后字节发生变化（本次准备即拒绝）")
    for logical, project_relative in PROJECT_MATERIAL_FILES:
        data = _read_bytes(PROJECT_ROOT / project_relative, "final_read", logical)
        if _sha_bytes(data) != _sha_bytes(project_reads[project_relative]):
            _block(logical, "全部必要消费后字节发生变化（本次准备即拒绝）")


__all__ = ["prepare_human_gate1_request", "HumanGate1RequestBlocked",
           "HumanGate1RequestError", "fingerprint", "canonical_json_bytes"]
