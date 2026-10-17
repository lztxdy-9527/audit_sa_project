# -*- coding: utf-8 -*-
"""真实人工 Gate 决定记录：独立纯内存校验与构建核心（P1 / TASK-021）。

实现依据为冻结协议 `docs/proposals/HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md`
（SHA-256 `68c931b33ac51bdc5634247748d20463816e1a3a2105202fdd43942db26a3e76`，39298 字节）
的 §3—§14。本文件**仅使用标准库**，是纯内存函数：

- 不读写文件/数据库/工作簿/网络，不调用子进程；
- 不依赖当前时间、随机数、环境变量或可变全局状态；
- 不导入宿主、控制器、上游核心、测试或答案册；
- 不保存、不恢复、不放行、不产生批次批准；返回内存记录不等于已保存或已批准执行。

唯一业务入口：`build_human_gate_decision_record(...)`。
成功返回外层**恰两键**：`{"record": <17 键 record>, "record_fingerprint": <64 位小写十六进制>}`。
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import re

__all__ = [
    "HumanGateDecisionBlocked",
    "HumanGateDecisionError",
    "build_human_gate_decision_record",
    "fingerprint",
    "materials_body",
    "SUBMISSION_VERSION",
    "RECORD_VERSION",
    "WRAPPER_VERSION",
    "RECORD_STATUS_MEMORY_VALIDATED",
    "DECISION_SOURCE_HUMAN",
    "ACTOR_KIND_HUMAN",
    "DECIDED_AT_SOURCE_HUMAN",
    "NOTE_CONSTANT",
]

# --------------------------------------------------------------------------- 常量（协议 §2.1/§14）
SUBMISSION_VERSION = "TASK-020-human-gate-decision-submission-1.1"
RECORD_VERSION = "TASK-020-human-gate-decision-record-1.1"
WRAPPER_VERSION = "TASK-020-human-gate-decision-record-wrapper-1.1"
RECORD_STATUS_MEMORY_VALIDATED = "HUMAN_GATE_DECISION_MEMORY_VALIDATED"
DECISION_SOURCE_HUMAN = "HUMAN_GATE_DECISION"
ACTOR_KIND_HUMAN = "HUMAN_DECLARED"
DECIDED_AT_SOURCE_HUMAN = "HUMAN_PROVIDED_RAW"
NOTE_CONSTANT = "内存校验通过；不表示已保存、已放行或已产生真实人类判断。"

GATES = ("GATE1", "GATE2")
DECISIONS = ("APPROVE", "HOLD", "REJECT")
QUALITY_STATUSES = ("OK", "BLOCKED", "FAILED")

SUBMISSION_KEYS = (
    "submission_version", "event_id", "batch_id", "gate", "request_binding", "decision",
    "decision_source", "actor", "decided_at_raw", "reason", "prior_decision_binding",
)
REQUEST_BINDING_KEYS = ("request_id", "materials_binding")
ACTOR_KEYS = ("actor_kind", "actor_id", "declaration_note")
MATERIALS_KEYS = ("gate", "batch_id", "run_binding", "contract_binding", "files", "quality",
                  "materials_fingerprint")
RUN_BINDING_KEYS = ("code", "rules", "config", "input")
RUN_CODE_KEYS = ("file_sha256", "manifest_fingerprint")
RUN_RULES_KEYS = ("version", "manifest_fingerprint")
RUN_SINGLE_KEYS = ("file_sha256",)
CONTRACT_BINDING_KEYS = ("contract_version", "contract_file_sha256", "contract_effective")
FILE_ITEM_KEYS = ("relative", "file_sha256", "byte_size")
QUALITY_KEYS = ("status", "structural_blockers", "quality_blockers", "verification_failures")
EXPECTATIONS_KEYS = (
    "expected_batch_id", "expected_gate", "expected_request_id",
    "expected_materials_fingerprint", "expected_files", "expected_contract",
    "expected_run_binding", "expected_prior_gate1",
)
EXPECTED_CONTRACT_KEYS = ("contract_version", "contract_file_sha256")
EXPECTED_PRIOR_KEYS = ("gate", "batch_id", "event_id", "record_fingerprint", "run_binding")
PRIOR_HISTORY_KEYS = ("declared_complete", "declared_scope", "records")
WRAPPER_KEYS = ("wrapper_version", "record_fingerprint", "record")
RECORD_KEYS = (
    "record_version", "record_status", "gate", "batch_id", "event_id", "decision",
    "decision_source", "reason", "decided_at_raw", "decided_at_source", "actor", "binding",
    "prior_gate1", "quality_summary", "execution_allowed", "boundaries", "note",
)
RECORD_BINDING_KEYS = ("request_id", "materials_fingerprint", "materials_files",
                       "contract_binding", "run_binding")
PRIOR_SUMMARY_KEYS = ("record_fingerprint", "event_id", "batch_id", "gate", "decision",
                      "actor_kind")
QUALITY_SUMMARY_KEYS = ("status", "structural_blockers_count", "quality_blockers_count",
                        "verification_failures_count")
BOUNDARY_KEYS = ("persisted", "approved_for_execution", "human_initial_judgment_saved",
                 "ai_enabled", "identity_authentication", "source_authenticity_proven")

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\Z")
_DATETIME_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})([+-])(\d{2}):(\d{2})\Z")


# --------------------------------------------------------------------------- 异常（协议 §2.1/§13)
class HumanGateDecisionBlocked(Exception):
    """协议、类型、绑定或前提拒绝：可定位的 field 与 reason。"""

    def __init__(self, field, reason):
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


class HumanGateDecisionError(Exception):
    """意外内部错误（保留原因链，不伪装为协议拒绝，不包装成成功）。"""

    def __init__(self, stage, reason):
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}: {reason}")


# --------------------------------------------------------------------------- canonical / 指纹
def canonical_json_bytes(obj) -> bytes:
    """协议 §13 的 canonical JSON：UTF-8 / ensure_ascii=False / sort_keys=True /
    separators=(",", ":") / allow_nan=False。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def fingerprint(obj) -> str:
    """规范指纹 = canonical JSON 字节串的 SHA-256（64 位小写十六进制）。"""
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def materials_body(materials: dict) -> dict:
    """协议 §4.1：仅删除【顶层】materials_fingerprint，其余内容与列表顺序原样保留。"""
    return {key: value for key, value in materials.items() if key != "materials_fingerprint"}


def _deep(obj):
    return copy.deepcopy(obj)


def _block(field, reason):
    raise HumanGateDecisionBlocked(field, reason)


def _is_strict_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_hex64(value):
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _is_nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def _require_object(value, field):
    if not isinstance(value, dict):
        _block(field, f"必须是对象，实际 {type(value).__name__}")
    return value


def _check_closed_keys(obj, allowed, prefix):
    """封闭键集合：先报未知键，再报缺失键（均按 UTF-8 字节序确定唯一最早项）。"""
    for key in sorted(obj.keys(), key=lambda item: str(item).encode("utf-8")):
        if key not in allowed:
            _block(f"{prefix}.{key}" if prefix else str(key), "未知字段（封闭键集合不允许）")
    for key in allowed:
        if key not in obj:
            _block(f"{prefix}.{key}" if prefix else key, "缺失必需字段")
    return obj


def _require_nonempty_str(obj, key, prefix):
    value = obj[key]
    if not isinstance(value, str):
        _block(f"{prefix}.{key}", f"必须是字符串，实际 {type(value).__name__}")
    if value.strip() == "":
        _block(f"{prefix}.{key}", "不得为空或仅空白")
    return value


def _require_hex64(obj, key, prefix):
    value = obj[key]
    if not _is_hex64(value):
        _block(f"{prefix}.{key}",
               "必须是完整 64 位小写十六进制（不接受尾随 LF/CRLF/空格、大写或截断）")
    return value


def _require_const(obj, key, expected, prefix):
    value = obj[key]
    if not isinstance(value, str) or value != expected:
        _block(f"{prefix}.{key}", f"必须是常量 {expected!r}（实际 {value!r}）")
    return value


def _require_enum(obj, key, allowed, prefix):
    value = obj[key]
    if not isinstance(value, str) or value not in allowed:
        _block(f"{prefix}.{key}", f"必须是 {allowed} 之一（实际 {value!r}）")
    return value


def _require_strict_bool(obj, key, expected, prefix):
    value = obj[key]
    if value is not expected or not isinstance(value, bool):
        _block(f"{prefix}.{key}", f"必须是严格布尔 {expected}（实际 {value!r}）")
    return value


def _check_sorted_unique_list(items, keyfunc, field, label):
    values = [keyfunc(item) for item in items]
    for index in range(1, len(values)):
        if values[index] == values[index - 1]:
            _block(field, f"{label}存在重复项：{values[index]!r}")
        if values[index].encode("utf-8") < values[index - 1].encode("utf-8"):
            _block(field, f"{label}必须按 UTF-8 字节序升序（不允许无序输入）")
    return values


def _check_blocker_list(value, field):
    if not isinstance(value, list):
        _block(field, f"必须是列表，实际 {type(value).__name__}")
    for item in value:
        if not isinstance(item, str) or item.strip() == "":
            _block(field, "列表成员必须是非空字符串")
    _check_sorted_unique_list(value, lambda item: item, field, "阻断/失败列表")


# --------------------------------------------------------------------------- 第 1—4 步：形状/类型
def _step1_submission(submission):
    _require_object(submission, "submission")
    _check_closed_keys(submission, SUBMISSION_KEYS, "submission")
    _require_const(submission, "submission_version", SUBMISSION_VERSION, "submission")
    _require_nonempty_str(submission, "event_id", "submission")
    _require_nonempty_str(submission, "batch_id", "submission")
    gate = _require_enum(submission, "gate", GATES, "submission")

    request_binding = _require_object(submission["request_binding"], "submission.request_binding")
    _check_closed_keys(request_binding, REQUEST_BINDING_KEYS, "submission.request_binding")
    _require_nonempty_str(request_binding, "request_id", "submission.request_binding")
    _require_hex64(request_binding, "materials_binding", "submission.request_binding")

    _require_enum(submission, "decision", DECISIONS, "submission")
    _require_const(submission, "decision_source", DECISION_SOURCE_HUMAN, "submission")

    actor = _require_object(submission["actor"], "submission.actor")
    _check_closed_keys(actor, ACTOR_KEYS, "submission.actor")
    _require_enum(actor, "actor_kind", (ACTOR_KIND_HUMAN,), "submission.actor")
    _require_nonempty_str(actor, "actor_id", "submission.actor")
    _require_nonempty_str(actor, "declaration_note", "submission.actor")

    if not isinstance(submission["decided_at_raw"], str):
        _block("submission.decided_at_raw",
               f"必须是字符串（时间类型错误在第 1 步捕获），实际 "
               f"{type(submission['decided_at_raw']).__name__}")
    if submission["decided_at_raw"].strip() == "":
        _block("submission.decided_at_raw", "不得为空或仅空白")
    _require_nonempty_str(submission, "reason", "submission")

    prior = submission["prior_decision_binding"]
    if gate == "GATE1":
        if prior is not None:
            _block("submission.prior_decision_binding", "Gate1 必须为 null（不得携带前序绑定）")
    else:
        if not isinstance(prior, dict):
            _block("submission.prior_decision_binding",
                   "Gate2 必须是完整前序记录包装对象（字符串或摘要不能替代记录）")
        _check_closed_keys(prior, WRAPPER_KEYS, "submission.prior_decision_binding")
        if not isinstance(prior["record"], dict):
            _block("submission.prior_decision_binding.record", "必须是完整记录对象")
    return gate


def _step2_materials(materials):
    _require_object(materials, "materials")
    _check_closed_keys(materials, MATERIALS_KEYS, "materials")
    _require_enum(materials, "gate", GATES, "materials")
    _require_nonempty_str(materials, "batch_id", "materials")

    run_binding = _require_object(materials["run_binding"], "materials.run_binding")
    _check_closed_keys(run_binding, RUN_BINDING_KEYS, "materials.run_binding")
    code = _require_object(run_binding["code"], "materials.run_binding.code")
    _check_closed_keys(code, RUN_CODE_KEYS, "materials.run_binding.code")
    _require_hex64(code, "file_sha256", "materials.run_binding.code")
    _require_hex64(code, "manifest_fingerprint", "materials.run_binding.code")
    rules = _require_object(run_binding["rules"], "materials.run_binding.rules")
    _check_closed_keys(rules, RUN_RULES_KEYS, "materials.run_binding.rules")
    _require_nonempty_str(rules, "version", "materials.run_binding.rules")
    _require_hex64(rules, "manifest_fingerprint", "materials.run_binding.rules")
    config = _require_object(run_binding["config"], "materials.run_binding.config")
    _check_closed_keys(config, RUN_SINGLE_KEYS, "materials.run_binding.config")
    _require_hex64(config, "file_sha256", "materials.run_binding.config")
    source = _require_object(run_binding["input"], "materials.run_binding.input")
    _check_closed_keys(source, RUN_SINGLE_KEYS, "materials.run_binding.input")
    _require_hex64(source, "file_sha256", "materials.run_binding.input")

    contract = _require_object(materials["contract_binding"], "materials.contract_binding")
    _check_closed_keys(contract, CONTRACT_BINDING_KEYS, "materials.contract_binding")
    _require_nonempty_str(contract, "contract_version", "materials.contract_binding")
    _require_hex64(contract, "contract_file_sha256", "materials.contract_binding")
    _require_strict_bool(contract, "contract_effective", True, "materials.contract_binding")

    files = materials["files"]
    if not isinstance(files, list):
        _block("materials.files", f"必须是列表，实际 {type(files).__name__}")
    if not files:
        _block("materials.files", "必须为非空材料名单")
    for item in files:
        _require_object(item, "materials.files[]")
        _check_closed_keys(item, FILE_ITEM_KEYS, "materials.files[]")
        relative = item["relative"]
        if not isinstance(relative, str):
            _block("materials.files[].relative", f"必须是字符串，实际 {type(relative).__name__}")
        _check_relative(relative, "materials.files[].relative")
        _require_hex64(item, "file_sha256", "materials.files[]")
        if not _is_strict_int(item["byte_size"]):
            _block("materials.files[].byte_size", "必须是严格整数（bool 不冒充 int）")
        if item["byte_size"] < 0:
            _block("materials.files[].byte_size", "范围必须 >= 0")
    _check_sorted_unique_list(files, lambda item: item["relative"], "materials.files",
                              "材料名单")

    quality = _require_object(materials["quality"], "materials.quality")
    _check_closed_keys(quality, QUALITY_KEYS, "materials.quality")
    status = _require_enum(quality, "status", QUALITY_STATUSES, "materials.quality")
    for key in ("structural_blockers", "quality_blockers", "verification_failures"):
        _check_blocker_list(quality[key], f"materials.quality.{key}")
    structural = quality["structural_blockers"]
    quality_list = quality["quality_blockers"]
    failures = quality["verification_failures"]
    if status == "OK" and (structural or quality_list or failures):
        _block("materials.quality.status", "status=OK 但存在非空阻断/失败列表（状态与列表矛盾）")
    if status == "BLOCKED" and (not structural and not quality_list):
        _block("materials.quality.status",
               "status=BLOCKED 但结构/质量列表均为空（状态与列表矛盾）")
    if status == "BLOCKED" and failures:
        _block("materials.quality.status",
               "status=BLOCKED 但 verification_failures 非空（状态与列表矛盾）")
    if status == "FAILED" and not failures:
        _block("materials.quality.status",
               "status=FAILED 但 verification_failures 为空（状态与列表矛盾）")

    _require_hex64(materials, "materials_fingerprint", "materials")
    return status


def _check_relative(relative, field):
    if relative == "" or relative.startswith("/") or "\\" in relative:
        _block(field, "必须是批次相对 POSIX 路径（不以 / 开头、不含反斜杠）")
    segments = relative.split("/")
    if any(segment == "" for segment in segments):
        _block(field, "不得含空段")
    if any(segment == ".." for segment in segments):
        _block(field, "不得含 .. 段")


def _step3_expectations(expectations, submission_gate):
    obj = _require_object(expectations, "expectations")
    _check_closed_keys(obj, EXPECTATIONS_KEYS, "expectations")
    _require_nonempty_str(obj, "expected_batch_id", "expectations")
    gate = _require_enum(obj, "expected_gate", GATES, "expectations")
    _require_nonempty_str(obj, "expected_request_id", "expectations")
    _require_hex64(obj, "expected_materials_fingerprint", "expectations")

    expected_files = _require_object(obj["expected_files"], "expectations.expected_files")
    if not expected_files:
        _block("expectations.expected_files", "必须为非空独立文件名单")
    for key, value in expected_files.items():
        if not isinstance(key, str) or key.strip() == "":
            _block("expectations.expected_files", "键必须为非空字符串")
        _check_relative(key, f"expectations.expected_files[{key}]")
        if not _is_hex64(value):
            _block(f"expectations.expected_files[{key}]",
                   "必须是完整 64 位小写十六进制")

    expected_contract = _require_object(obj["expected_contract"], "expectations.expected_contract")
    _check_closed_keys(expected_contract, EXPECTED_CONTRACT_KEYS, "expectations.expected_contract")
    _require_nonempty_str(expected_contract, "contract_version",
                          "expectations.expected_contract")
    _require_hex64(expected_contract, "contract_file_sha256", "expectations.expected_contract")

    expected_run = _require_object(obj["expected_run_binding"], "expectations.expected_run_binding")
    _check_closed_keys(expected_run, RUN_BINDING_KEYS, "expectations.expected_run_binding")
    code = _require_object(expected_run["code"], "expectations.expected_run_binding.code")
    _check_closed_keys(code, RUN_CODE_KEYS, "expectations.expected_run_binding.code")
    _require_hex64(code, "file_sha256", "expectations.expected_run_binding.code")
    _require_hex64(code, "manifest_fingerprint", "expectations.expected_run_binding.code")
    rules = _require_object(expected_run["rules"], "expectations.expected_run_binding.rules")
    _check_closed_keys(rules, RUN_RULES_KEYS, "expectations.expected_run_binding.rules")
    _require_nonempty_str(rules, "version", "expectations.expected_run_binding.rules")
    _require_hex64(rules, "manifest_fingerprint", "expectations.expected_run_binding.rules")
    config = _require_object(expected_run["config"], "expectations.expected_run_binding.config")
    _check_closed_keys(config, RUN_SINGLE_KEYS, "expectations.expected_run_binding.config")
    _require_hex64(config, "file_sha256", "expectations.expected_run_binding.config")
    source = _require_object(expected_run["input"], "expectations.expected_run_binding.input")
    _check_closed_keys(source, RUN_SINGLE_KEYS, "expectations.expected_run_binding.input")
    _require_hex64(source, "file_sha256", "expectations.expected_run_binding.input")

    prior = obj["expected_prior_gate1"]
    if submission_gate == "GATE1":
        if prior is not None:
            _block("expectations.expected_prior_gate1", "Gate1 必须为 null")
    else:
        if not isinstance(prior, dict):
            _block("expectations.expected_prior_gate1",
                   "Gate2 必须给出独立前序预期对象（不接受 null）")
        _check_closed_keys(prior, EXPECTED_PRIOR_KEYS, "expectations.expected_prior_gate1")
        _require_enum(prior, "gate", GATES, "expectations.expected_prior_gate1")
        _require_nonempty_str(prior, "batch_id", "expectations.expected_prior_gate1")
        _require_nonempty_str(prior, "event_id", "expectations.expected_prior_gate1")
        _require_hex64(prior, "record_fingerprint", "expectations.expected_prior_gate1")
        prior_run = _require_object(prior["run_binding"],
                                    "expectations.expected_prior_gate1.run_binding")
        _check_closed_keys(prior_run, RUN_BINDING_KEYS,
                           "expectations.expected_prior_gate1.run_binding")
        prior_code = _require_object(prior_run["code"],
                                     "expectations.expected_prior_gate1.run_binding.code")
        _check_closed_keys(prior_code, RUN_CODE_KEYS,
                           "expectations.expected_prior_gate1.run_binding.code")
        _require_hex64(prior_code, "file_sha256",
                       "expectations.expected_prior_gate1.run_binding.code")
        _require_hex64(prior_code, "manifest_fingerprint",
                       "expectations.expected_prior_gate1.run_binding.code")
        prior_rules = _require_object(prior_run["rules"],
                                      "expectations.expected_prior_gate1.run_binding.rules")
        _check_closed_keys(prior_rules, RUN_RULES_KEYS,
                           "expectations.expected_prior_gate1.run_binding.rules")
        _require_nonempty_str(prior_rules, "version",
                              "expectations.expected_prior_gate1.run_binding.rules")
        _require_hex64(prior_rules, "manifest_fingerprint",
                       "expectations.expected_prior_gate1.run_binding.rules")
        prior_config = _require_object(prior_run["config"],
                                       "expectations.expected_prior_gate1.run_binding.config")
        _check_closed_keys(prior_config, RUN_SINGLE_KEYS,
                           "expectations.expected_prior_gate1.run_binding.config")
        _require_hex64(prior_config, "file_sha256",
                       "expectations.expected_prior_gate1.run_binding.config")
        prior_input = _require_object(prior_run["input"],
                                      "expectations.expected_prior_gate1.run_binding.input")
        _check_closed_keys(prior_input, RUN_SINGLE_KEYS,
                           "expectations.expected_prior_gate1.run_binding.input")
        _require_hex64(prior_input, "file_sha256",
                       "expectations.expected_prior_gate1.run_binding.input")
    return gate


def _step4_prior_history(prior_history):
    if prior_history is None:
        _block("prior_history", "历史完整性声明缺失（语义必填；不默认空历史、不默认完整）")
    obj = _require_object(prior_history, "prior_history")
    _check_closed_keys(obj, PRIOR_HISTORY_KEYS, "prior_history")
    if not isinstance(obj["declared_complete"], bool):
        _block("prior_history.declared_complete",
               f"必须是严格布尔，实际 {type(obj['declared_complete']).__name__}")
    if obj["declared_complete"] is False:
        _block("prior_history.declared_complete",
               "调用方声明历史不完整，无法排除全局重复事件")
    scope = obj["declared_scope"]
    if not isinstance(scope, str):
        _block("prior_history.declared_scope", f"必须是字符串，实际 {type(scope).__name__}")
    if scope.strip() == "":
        _block("prior_history.declared_scope", "不得为空或仅空白")
    records = obj["records"]
    if not isinstance(records, list):
        _block("prior_history.records", f"必须是列表，实际 {type(records).__name__}")
    for index, member in enumerate(records):
        prefix = f"prior_history.records[{index}]"
        _require_object(member, prefix)
        _check_closed_keys(member, WRAPPER_KEYS, prefix)
        record = _require_object(member["record"], f"{prefix}.record")
        if "event_id" not in record:
            _block(f"{prefix}.record.event_id", "缺失必需字段")
        for key in ("gate", "batch_id", "event_id", "decision"):
            if key not in record:
                _block(f"{prefix}.record.{key}", "缺失必需字段")
        _require_enum(record, "gate", GATES, f"{prefix}.record")
        _require_nonempty_str(record, "batch_id", f"{prefix}.record")
        _require_nonempty_str(record, "event_id", f"{prefix}.record")
        _require_enum(record, "decision", DECISIONS, f"{prefix}.record")
        actor = _require_object(record.get("actor"), f"{prefix}.record.actor")
        if not isinstance(actor.get("actor_kind"), str):
            _block(f"{prefix}.record.actor.actor_kind", "必须是字符串")
    _check_sorted_unique_list(records, lambda member: member["record"]["event_id"],
                              "prior_history.records", "历史记录名单")
    return records


# --------------------------------------------------------------------------- 第 5—8 步：身份/时间/契约/运行
def _step5_identity(submission, materials, expectations):
    if materials["gate"] != submission["gate"]:
        _block("materials.gate", "必须与 submission.gate 一致")
    if materials["batch_id"] != submission["batch_id"]:
        _block("materials.batch_id", "必须与 submission.batch_id 精确一致")
    if expectations["expected_batch_id"] != submission["batch_id"]:
        _block("expectations.expected_batch_id", "必须与 submission.batch_id 精确一致")
    if expectations["expected_gate"] != submission["gate"]:
        _block("expectations.expected_gate", "必须与 submission.gate 一致")
    if expectations["expected_request_id"] != submission["request_binding"]["request_id"]:
        _block("expectations.expected_request_id",
               "必须与 submission.request_binding.request_id 精确一致")


def _step6_time(raw):
    _check_time_value(raw, "submission.decided_at_raw")


def _check_time_value(raw, field):
    """协议 §6 的时间规则（供 submission 与 record 复用；类型错误由调用方先行判定）。"""
    if not isinstance(raw, str):
        _block(field, f"必须是字符串，实际 {type(raw).__name__}")
    if raw.strip() == "":
        _block(field, "不得为空或仅空白")
    if _DATE_RE.fullmatch(raw):
        year, month, day = (int(part) for part in _DATE_RE.fullmatch(raw).groups())
        _check_calendar_date(year, month, day, field)
        return
    match = _DATETIME_RE.fullmatch(raw)
    if not match:
        _block(field, "时间形式必须为 YYYY-MM-DD 或 YYYY-MM-DDThh:mm:ss±hh:mm 且全串匹配"
                      "（不接受首尾空白、Z、小数秒、缺秒或其他分隔符）")
    year, month, day, hour, minute, second, sign, offset_hour, offset_minute = match.groups()
    _check_calendar_date(int(year), int(month), int(day), field)
    if int(hour) > 23:
        _block(field, "小时分量必须在 00–23")
    if int(minute) > 59:
        _block(field, "分钟分量必须在 00–59")
    if int(second) > 59:
        _block(field, "秒分量必须在 00–59（不接受闰秒）")
    if int(offset_hour) > 14:
        _block(field, "时区偏移小时必须在 00–14")
    if int(offset_minute) > 59:
        _block(field, "时区偏移分钟必须在 00–59")
    if int(offset_hour) == 14 and int(offset_minute) != 0:
        _block(field, "时区偏移最大为 ±14:00（hh==14 时 mm 必须为 00）")


def _validate_run_binding(run_binding, prefix):
    """run_binding 逐层封闭键/严格类型/哈希格式（协议 §3.2/§7.3）。"""
    obj = _require_object(run_binding, prefix)
    _check_closed_keys(obj, RUN_BINDING_KEYS, prefix)
    code = _require_object(obj["code"], f"{prefix}.code")
    _check_closed_keys(code, RUN_CODE_KEYS, f"{prefix}.code")
    _require_hex64(code, "file_sha256", f"{prefix}.code")
    _require_hex64(code, "manifest_fingerprint", f"{prefix}.code")
    rules = _require_object(obj["rules"], f"{prefix}.rules")
    _check_closed_keys(rules, RUN_RULES_KEYS, f"{prefix}.rules")
    _require_nonempty_str(rules, "version", f"{prefix}.rules")
    _require_hex64(rules, "manifest_fingerprint", f"{prefix}.rules")
    config = _require_object(obj["config"], f"{prefix}.config")
    _check_closed_keys(config, RUN_SINGLE_KEYS, f"{prefix}.config")
    _require_hex64(config, "file_sha256", f"{prefix}.config")
    source = _require_object(obj["input"], f"{prefix}.input")
    _check_closed_keys(source, RUN_SINGLE_KEYS, f"{prefix}.input")
    _require_hex64(source, "file_sha256", f"{prefix}.input")
    return obj


def _check_calendar_date(year, month, day, field):
    if not 1 <= month <= 12:
        _block(field, "月份必须是 01–12")
    try:
        datetime.date(year, month, day)
    except ValueError as exc:
        _block(field, f"日期不是真实日历日期（{exc}）")


def _step7_contract(materials, expectations):
    actual = materials["contract_binding"]
    expected = expectations["expected_contract"]
    if actual["contract_version"] != expected["contract_version"]:
        _block("expectations.expected_contract.contract_version",
               "必须与 materials.contract_binding.contract_version 精确一致")
    if actual["contract_file_sha256"] != expected["contract_file_sha256"]:
        _block("expectations.expected_contract.contract_file_sha256",
               "必须与 materials.contract_binding.contract_file_sha256 精确一致")


def _step8_run_binding(materials, expectations):
    actual = materials["run_binding"]
    expected = expectations["expected_run_binding"]
    comparisons = (
        ("code", "file_sha256"),
        ("code", "manifest_fingerprint"),
        ("rules", "version"),
        ("rules", "manifest_fingerprint"),
        ("config", "file_sha256"),
        ("input", "file_sha256"),
    )
    for path in comparisons:
        node_a, node_e = actual, expected
        for key in path:
            node_a, node_e = node_a[key], node_e[key]
        if node_a != node_e:
            joined = ".".join(path)
            _block(f"expectations.expected_run_binding.{joined}",
                   f"必须与 materials.run_binding.{joined} 逐字段严格相等")


# --------------------------------------------------------------------------- 第 9—10 步：材料与名单
def _step9_materials_fingerprint(submission, materials, expectations):
    recomputed = fingerprint(materials_body(materials))
    if materials["materials_fingerprint"] != recomputed:
        _block("materials.materials_fingerprint",
               "必须等于材料正文（仅删除顶层 materials_fingerprint）的规范指纹")
    if submission["request_binding"]["materials_binding"] != recomputed:
        _block("submission.request_binding.materials_binding",
               "必须等于材料正文的规范指纹")
    if expectations["expected_materials_fingerprint"] != recomputed:
        _block("expectations.expected_materials_fingerprint",
               "必须等于材料正文的规范指纹")
    return recomputed


def _step10_files(materials, expectations):
    actual = {item["relative"]: item["file_sha256"] for item in materials["files"]}
    expected = expectations["expected_files"]
    for relative in sorted(expected.keys(), key=lambda item: item.encode("utf-8")):
        if relative not in actual:
            _block(f"expectations.expected_files[{relative}]",
                   "独立名单中的文件在 materials.files 中缺失")
    for relative in sorted(actual.keys(), key=lambda item: item.encode("utf-8")):
        if relative not in expected:
            _block(f"materials.files[{relative}]", "材料名单中的文件在独立名单中缺失（额外项）")
    for relative in sorted(expected.keys(), key=lambda item: item.encode("utf-8")):
        if actual[relative] != expected[relative]:
            _block(f"expectations.expected_files[{relative}]",
                   "文件字节 SHA 必须与独立名单逐项精确相等")


# --------------------------------------------------------------------------- 第 11 步：前序闭合
def _prior_check(condition, field, reason):
    if not condition:
        _block(field, reason)


# --- 记录对象的完整 schema 校验（协议 §3.6/§14；供当前前序 11b—11h 与已提供历史复用）
def _validate_record_header(record, prefix, *, current_gate1=False):
    """11b：记录顶层封闭键集合、常量、枚举、来源、说明、时间、身份与 prior_gate1。"""
    _require_object(record, prefix)
    _check_closed_keys(record, RECORD_KEYS, prefix)
    _require_const(record, "record_version", RECORD_VERSION, prefix)
    _require_const(record, "record_status", RECORD_STATUS_MEMORY_VALIDATED, prefix)
    gate = _require_enum(record, "gate", GATES, prefix)
    _require_nonempty_str(record, "batch_id", prefix)
    _require_nonempty_str(record, "event_id", prefix)
    _require_enum(record, "decision", DECISIONS, prefix)
    _require_const(record, "decision_source", DECISION_SOURCE_HUMAN, prefix)
    _require_nonempty_str(record, "reason", prefix)
    _check_time_value(record["decided_at_raw"], f"{prefix}.decided_at_raw")
    _require_const(record, "decided_at_source", DECIDED_AT_SOURCE_HUMAN, prefix)
    actor = _require_object(record["actor"], f"{prefix}.actor")
    _check_closed_keys(actor, ACTOR_KEYS, f"{prefix}.actor")
    _require_enum(actor, "actor_kind", (ACTOR_KIND_HUMAN,), f"{prefix}.actor")
    _require_nonempty_str(actor, "actor_id", f"{prefix}.actor")
    _require_nonempty_str(actor, "declaration_note", f"{prefix}.actor")
    prior = record["prior_gate1"]
    if gate == "GATE1":
        if prior is not None:
            _block(f"{prefix}.prior_gate1", "Gate1 记录的 prior_gate1 必须为 null")
    else:
        if not isinstance(prior, dict):
            _block(f"{prefix}.prior_gate1", "Gate2 记录的 prior_gate1 必须是前序摘要对象")
        _check_closed_keys(prior, PRIOR_SUMMARY_KEYS, f"{prefix}.prior_gate1")
        _require_hex64(prior, "record_fingerprint", f"{prefix}.prior_gate1")
        _require_nonempty_str(prior, "event_id", f"{prefix}.prior_gate1")
        _require_nonempty_str(prior, "batch_id", f"{prefix}.prior_gate1")
        _require_enum(prior, "gate", GATES, f"{prefix}.prior_gate1")
        _require_enum(prior, "decision", DECISIONS, f"{prefix}.prior_gate1")
        _require_enum(prior, "actor_kind", (ACTOR_KIND_HUMAN,), f"{prefix}.prior_gate1")
    _require_const(record, "note", NOTE_CONSTANT, prefix)
    return gate


def _validate_record_binding_materials(record, prefix):
    """11c：binding 顶层、request_id、材料指纹格式与 materials_files 名单规则。"""
    binding = _require_object(record["binding"], f"{prefix}.binding")
    _check_closed_keys(binding, RECORD_BINDING_KEYS, f"{prefix}.binding")
    _require_nonempty_str(binding, "request_id", f"{prefix}.binding")
    _require_hex64(binding, "materials_fingerprint", f"{prefix}.binding")
    files = binding["materials_files"]
    if not isinstance(files, list) or not files:
        _block(f"{prefix}.binding.materials_files", "必须为非空材料文件名单")
    for item in files:
        _require_object(item, f"{prefix}.binding.materials_files[]")
        _check_closed_keys(item, FILE_ITEM_KEYS, f"{prefix}.binding.materials_files[]")
        if not isinstance(item["relative"], str):
            _block(f"{prefix}.binding.materials_files[].relative", "必须是字符串")
        _check_relative(item["relative"], f"{prefix}.binding.materials_files[].relative")
        _require_hex64(item, "file_sha256", f"{prefix}.binding.materials_files[]")
        if not _is_strict_int(item["byte_size"]):
            _block(f"{prefix}.binding.materials_files[].byte_size", "必须是严格整数")
        if item["byte_size"] < 0:
            _block(f"{prefix}.binding.materials_files[].byte_size", "范围必须 >= 0")
    _check_sorted_unique_list(files, lambda item: item["relative"],
                              f"{prefix}.binding.materials_files", "记录内材料文件名单")
    return binding


def _validate_record_contract(binding, prefix):
    """11f：contract_binding 完整键/版本/SHA/严格 true。"""
    contract = _require_object(binding["contract_binding"], f"{prefix}.binding.contract_binding")
    _check_closed_keys(contract, CONTRACT_BINDING_KEYS, f"{prefix}.binding.contract_binding")
    _require_nonempty_str(contract, "contract_version", f"{prefix}.binding.contract_binding")
    _require_hex64(contract, "contract_file_sha256", f"{prefix}.binding.contract_binding")
    _require_strict_bool(contract, "contract_effective", True,
                         f"{prefix}.binding.contract_binding")
    return contract


def _validate_record_run_binding(binding, prefix):
    """11g：run_binding 逐层封闭键/严格类型/哈希。"""
    return _validate_run_binding(binding["run_binding"], f"{prefix}.binding.run_binding")


def _validate_record_quality_boundaries(record, prefix):
    """11h：quality_summary 完整键/状态/严格派生计数语义 + execution_allowed + boundaries。"""
    summary = _require_object(record["quality_summary"], f"{prefix}.quality_summary")
    _check_closed_keys(summary, QUALITY_SUMMARY_KEYS, f"{prefix}.quality_summary")
    status = _require_enum(summary, "status", QUALITY_STATUSES, f"{prefix}.quality_summary")
    counts = {}
    for key in ("structural_blockers_count", "quality_blockers_count",
                "verification_failures_count"):
        value = summary[key]
        if not _is_strict_int(value):
            _block(f"{prefix}.quality_summary.{key}", "必须是严格整数（bool 不冒充 int）")
        if value < 0:
            _block(f"{prefix}.quality_summary.{key}", "范围必须 >= 0")
        counts[key] = value
    blockers = counts["structural_blockers_count"] + counts["quality_blockers_count"]
    failures = counts["verification_failures_count"]
    field = f"{prefix}.quality_summary.status"
    if status == "OK" and (blockers or failures):
        _block(field, "status=OK 但计数非零（状态与派生计数矛盾）")
    if status == "BLOCKED" and (blockers == 0 or failures):
        _block(field, "status=BLOCKED 要求阻断计数≥1 且失败计数为 0（状态与派生计数矛盾）")
    if status == "FAILED" and failures == 0:
        _block(field, "status=FAILED 要求失败计数≥1（状态与派生计数矛盾）")
    _require_strict_bool(record, "execution_allowed", False, prefix)
    boundaries = _require_object(record["boundaries"], f"{prefix}.boundaries")
    _check_closed_keys(boundaries, BOUNDARY_KEYS, f"{prefix}.boundaries")
    for key in BOUNDARY_KEYS:
        _require_strict_bool(boundaries, key, False, f"{prefix}.boundaries")
    return summary


def _validate_record_decision_matrix(record, prefix):
    """已提供历史记录也必须满足协议 §12 决定矩阵（与合法输出一致）。

    - `OK`：三种决定均可为合法历史；
    - `BLOCKED`：HOLD/REJECT 可接受，**APPROVE 拒绝**；
    - `FAILED`：三种决定均不得作为成功历史记录。
    """
    status = record["quality_summary"]["status"]
    decision = record["decision"]
    if status == "FAILED":
        _block(f"{prefix}.quality_summary.status",
               "核验失败/材料不完整，不能作为成功历史记录（§12 矩阵：FAILED 不产生成功记录）")
    if status == "BLOCKED" and decision == "APPROVE":
        _block(f"{prefix}.decision",
               "存在未解决阻断时 APPROVE 不能作为成功历史记录（§12 矩阵）")


def _validate_record_prior_summary_relations(record, prefix):
    """Gate2 历史记录的 `prior_gate1` 摘要必须符合 §14 派生关系（只核现有字段自身关系）。"""
    prior = record["prior_gate1"]
    _prior_check(prior["gate"] == "GATE1", f"{prefix}.prior_gate1.gate",
                 "前序摘要必须来自 Gate1 记录")
    _prior_check(prior["decision"] == "APPROVE", f"{prefix}.prior_gate1.decision",
                 "前序摘要必须是 APPROVE")
    _prior_check(prior["batch_id"] == record["batch_id"], f"{prefix}.prior_gate1.batch_id",
                 "前序摘要批次必须与该历史记录批次一致")
    _prior_check(prior["event_id"] != record["event_id"],
                 f"{prefix}.prior_gate1.event_id",
                 "前序摘要 event_id 不得与该记录自身 event_id 相同（事件不能自我充当前序）")


def _validate_record_full(record, prefix, *, current_gate1=False):
    """对任一 record 执行自洽的完整 schema 校验（不要求批次/运行/APPROVE 等于当前批次）。"""
    gate = _validate_record_header(record, prefix, current_gate1=current_gate1)
    binding = _validate_record_binding_materials(record, prefix)
    _validate_record_contract(binding, prefix)
    _validate_record_run_binding(binding, prefix)
    _validate_record_quality_boundaries(record, prefix)
    _validate_record_decision_matrix(record, prefix)
    if gate == "GATE2":
        _validate_record_prior_summary_relations(record, prefix)
    return gate, binding


def _step11_prior(submission, materials, expectations, records):
    prior = submission["prior_decision_binding"]
    expected_prior = expectations["expected_prior_gate1"]
    if prior is None:
        return None
    prefix = "submission.prior_decision_binding"

    # 11a wrapper 形状（封闭键集合与 record 对象性已在第 1 步保证）
    _prior_check(prior["wrapper_version"] == WRAPPER_VERSION, f"{prefix}.wrapper_version",
                 f"必须是常量 {WRAPPER_VERSION!r}")
    _prior_check(_is_hex64(prior["record_fingerprint"]), f"{prefix}.record_fingerprint",
                 "必须是完整 64 位小写十六进制")

    record = prior["record"]
    # 11b 记录顶层封闭键/常量/枚举/来源/说明/时间/身份/prior_gate1/note
    _validate_record_header(record, f"{prefix}.record", current_gate1=True)
    # 11c binding 与材料文件成员
    binding = _validate_record_binding_materials(record, f"{prefix}.record")
    # 11d 记录正文复算
    _prior_check(prior["record_fingerprint"] == fingerprint(record),
                 f"{prefix}.record_fingerprint", "必须等于记录对象的规范指纹（复算不符）")
    # 11e 记录身份
    _prior_check(record.get("gate") == "GATE1", f"{prefix}.record.gate", "前序记录必须是 Gate1")
    _prior_check(record.get("batch_id") == submission["batch_id"],
                 f"{prefix}.record.batch_id", "前序记录批次必须与本批次一致")
    _prior_check(record.get("decision") == "APPROVE", f"{prefix}.record.decision",
                 "前序记录必须是 APPROVE")
    actor = record.get("actor")
    _prior_check(isinstance(actor, dict)
                 and actor.get("actor_kind") == ACTOR_KIND_HUMAN,
                 f"{prefix}.record.actor.actor_kind",
                 f"前序记录身份声明必须是 {ACTOR_KIND_HUMAN!r}")

    # 11f 契约一致（含 contract_binding 完整 schema 与严格 true）
    contract = _validate_record_contract(binding, f"{prefix}.record")
    _prior_check(contract["contract_version"]
                 == expectations["expected_contract"]["contract_version"],
                 f"{prefix}.record.binding.contract_binding.contract_version",
                 "前序记录契约版本必须等于本次独立契约预期")
    _prior_check(contract["contract_file_sha256"]
                 == expectations["expected_contract"]["contract_file_sha256"],
                 f"{prefix}.record.binding.contract_binding.contract_file_sha256",
                 "前序记录契约文件 SHA 必须等于本次独立契约预期")

    # 11g 运行绑定（逐层 schema + 六字段 + 独立预期）
    run_binding = _validate_record_run_binding(binding, f"{prefix}.record")
    field_pairs = (
        ("code", "file_sha256"),
        ("code", "manifest_fingerprint"),
        ("rules", "version"),
        ("rules", "manifest_fingerprint"),
        ("config", "file_sha256"),
        ("input", "file_sha256"),
    )
    prior_expected_run = expected_prior["run_binding"]
    for group, key in field_pairs:
        prior_value = run_binding[group][key]
        current = materials["run_binding"][group][key]
        expected = expectations["expected_run_binding"][group][key]
        independent = prior_expected_run[group][key]
        _prior_check(prior_value == current,
                     f"{prefix}.record.binding.run_binding.{group}.{key}",
                     "前序记录运行绑定必须与本次 materials.run_binding 逐字段严格相等")
        _prior_check(prior_value == expected,
                     f"{prefix}.record.binding.run_binding.{group}.{key}",
                     "前序记录运行绑定必须与本次独立运行预期逐字段严格相等")
        _prior_check(prior_value == independent,
                     f"expectations.expected_prior_gate1.run_binding.{group}.{key}",
                     "独立前序运行预期必须等于前序记录的运行绑定")

    # 11h 质量与边界
    summary = _validate_record_quality_boundaries(record, f"{prefix}.record")
    _prior_check(summary["status"] == "OK", f"{prefix}.record.quality_summary.status",
                 "前序记录质量必须为 OK")
    for key in ("structural_blockers_count", "quality_blockers_count",
                "verification_failures_count"):
        _prior_check(summary[key] == 0, f"{prefix}.record.quality_summary.{key}",
                     "前序记录计数必须为 0")

    # 11i 三处指纹闭合与历史一致
    _prior_check(expected_prior["record_fingerprint"] == prior["record_fingerprint"],
                 "expectations.expected_prior_gate1.record_fingerprint",
                 "独立前序预期与本提交 wrapper 的指纹必须一致")
    _prior_check(expected_prior["gate"] == record.get("gate"),
                 "expectations.expected_prior_gate1.gate", "必须与前序记录 gate 一致")
    _prior_check(expected_prior["batch_id"] == record.get("batch_id"),
                 "expectations.expected_prior_gate1.batch_id", "必须与前序记录 batch_id 一致")
    _prior_check(expected_prior["event_id"] == record.get("event_id"),
                 "expectations.expected_prior_gate1.event_id", "必须与前序记录 event_id 一致")
    _prior_check(any(_canonical_equal(member, prior) for member in records),
                 "prior_history.records",
                 "历史必须包含与提交 wrapper 规范相等的同一前序记录")

    return {
        "record_fingerprint": prior["record_fingerprint"],
        "event_id": record.get("event_id"),
        "batch_id": record.get("batch_id"),
        "gate": record.get("gate"),
        "decision": record.get("decision"),
        "actor_kind": actor.get("actor_kind"),
    }


def _validate_history_records(records):
    """第 11 步之后、第 12 步语义判定之前的**已提供历史**合法性核验。

    每个 wrapper 必须：封闭键集合与版本常量、指纹格式正确且与记录正文复算一致、
    record 为完整合法记录（自身协议合法，**不**要求 Gate1/APPROVE/同批次/同运行绑定）。
    一般历史允许合法 HOLD/REJECT、其他批次或 Gate2 记录。
    """
    for index, member in enumerate(records):
        prefix = f"prior_history.records[{index}]"
        _require_object(member, prefix)
        _check_closed_keys(member, WRAPPER_KEYS, prefix)
        _require_const(member, "wrapper_version", WRAPPER_VERSION, prefix)
        _require_hex64(member, "record_fingerprint", prefix)
        record = _require_object(member["record"], f"{prefix}.record")
        _prior_check(member["record_fingerprint"] == fingerprint(record),
                     f"{prefix}.record_fingerprint",
                     "历史 wrapper 的记录指纹必须等于记录正文的规范指纹（复算不符）")
        _validate_record_full(record, f"{prefix}.record")


def _canonical_equal(left, right) -> bool:
    try:
        return canonical_json_bytes(left) == canonical_json_bytes(right)
    except (TypeError, ValueError) as exc:
        raise HumanGateDecisionBlocked("prior_history.records",
                                       f"成员无法按 canonical JSON 比较：{exc}") from exc


# --------------------------------------------------------------------------- 第 12 步：历史与重复事件
def _step12_history(submission, records):
    for member in records:
        if member["record"]["event_id"] == submission["event_id"]:
            _block("submission.event_id", "该 event_id 已出现在历史快照中（重复事件）")
    for member in records:
        record = member["record"]
        if (record["gate"] == submission["gate"]
                and record["batch_id"] == submission["batch_id"]
                and record["decision"] == "APPROVE"):
            _block("prior_history.records",
                   "同批次同 Gate 已存在成功 APPROVE 记录（不可覆盖、不复用旧决定）")


# --------------------------------------------------------------------------- 第 13—14 步：矩阵与构建
def _step13_matrix(status, decision):
    if status == "FAILED":
        _block("materials.quality.status", "核验失败/材料不完整，不产生成功记录")
    if status == "BLOCKED" and decision == "APPROVE":
        _block("submission.decision", "完整核验报告存在未解决阻断时 APPROVE 必须被拒绝")


def _build_record(submission, materials, prior_summary):
    quality = materials["quality"]
    record = {
        "record_version": RECORD_VERSION,
        "record_status": RECORD_STATUS_MEMORY_VALIDATED,
        "gate": submission["gate"],
        "batch_id": submission["batch_id"],
        "event_id": submission["event_id"],
        "decision": submission["decision"],
        "decision_source": submission["decision_source"],
        "reason": submission["reason"],
        "decided_at_raw": submission["decided_at_raw"],
        "decided_at_source": DECIDED_AT_SOURCE_HUMAN,
        "actor": _deep(submission["actor"]),
        "binding": {
            "request_id": submission["request_binding"]["request_id"],
            "materials_fingerprint": materials["materials_fingerprint"],
            "materials_files": [_deep(item) for item in materials["files"]],
            "contract_binding": _deep(materials["contract_binding"]),
            "run_binding": _deep(materials["run_binding"]),
        },
        "prior_gate1": _deep(prior_summary),
        "quality_summary": {
            "status": quality["status"],
            "structural_blockers_count": len(quality["structural_blockers"]),
            "quality_blockers_count": len(quality["quality_blockers"]),
            "verification_failures_count": len(quality["verification_failures"]),
        },
        "execution_allowed": False,
        "boundaries": {key: False for key in BOUNDARY_KEYS},
        "note": NOTE_CONSTANT,
    }
    return record


def _build_and_validate(submission, materials, expectations, prior_history):
    gate = _step1_submission(submission)
    status = _step2_materials(materials)
    expected_gate = _step3_expectations(expectations, gate)
    records = _step4_prior_history(prior_history)

    _step5_identity(submission, materials, expectations)
    _step6_time(submission["decided_at_raw"])
    _step7_contract(materials, expectations)
    _step8_run_binding(materials, expectations)
    _step9_materials_fingerprint(submission, materials, expectations)
    _step10_files(materials, expectations)

    if gate != expected_gate:
        _block("expectations.expected_gate", "必须与 submission.gate 一致")
    prior_summary = _step11_prior(submission, materials, expectations, records)
    # 第 11 步之后、第 12 步语义判定之前：已提供历史的 wrapper/record 合法性核验
    _validate_history_records(records)
    _step12_history(submission, records)
    _step13_matrix(status, submission["decision"])

    record = _build_record(submission, materials, prior_summary)
    result = {"record": record, "record_fingerprint": fingerprint(record)}
    return result


def build_human_gate_decision_record(
    submission: dict,
    materials: dict,
    expectations: dict,
    *,
    prior_history: dict | None = None,
) -> dict:
    """校验并构建真实人工 Gate 决定记录（纯内存；协议 §2.1 的拟定公开接口）。

    成功返回恰好两键：``{"record": <17 键 record>, "record_fingerprint": <64hex>}``。
    协议/类型/绑定拒绝抛 `HumanGateDecisionBlocked(field, reason)`；
    意外内部错误抛 `HumanGateDecisionError(stage, reason)` 并保留 ``__cause__``。
    不读写文件/库/网络，不修改入参，返回与入参无共享可变别名。``prior_history``
    形参默认 ``None`` 只让缺省调用进入函数体——缺省或显式 ``None`` 都在第 4 步被拒绝。
    """
    try:
        return _build_and_validate(submission, materials, expectations, prior_history)
    except (HumanGateDecisionBlocked, HumanGateDecisionError):
        raise
    except Exception as exc:  # noqa: BLE001 - 意外内部错误必须保留原因链、不伪装为协议拒绝
        raise HumanGateDecisionError(
            "internal", f"核心内部意外错误：{type(exc).__name__}: {exc}") from exc
