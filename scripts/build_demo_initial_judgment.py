#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-016 开发态模拟初判记录纯核心。

唯一业务入口：

    build_initial_judgment_record(batch_id, fact_packet, submission, *,
                                  expected_packet_sha256) -> {"record": ..., "record_sha256": ...}

本模块是**纯内存确定性校验与事实绑定**核心：

- 只校验调用方明确提供的模拟初判文本并把它与已保存的事实包绑定；不推导、不生成、不预填任何判断，
  不计算候选等级/重要性/审计结论，不读取聊天倾向。
- 不读取或写入文件、数据库或 Excel；不导入或调用上游、控制器、宿主、测试、答案册、LLM、网络或子进程；
  不生成事件 ID、身份、时间或判断，导入本模块也不触发任何上述操作。
- 校验通过只代表**本次内存记录成立（VALIDATED）**，不代表已保存、已认证或已解锁 AI；
  它不改变事实包中“尚未保存人类判断”的冻结说明。

规范 JSON：UTF-8、``ensure_ascii=False``、``sort_keys=True``、``separators=(",", ":")``、``allow_nan=False``；
规范指纹 = 该字节串的 SHA-256。``record`` 不内嵌自身指纹。
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import re

RECORD_VERSION = "TASK-016-initial-judgment-record-1.0"
SUBMISSION_VERSION = "TASK-016-initial-judgment-submission-1.0"
RECORD_STATUS = "DEV_INITIAL_JUDGMENT_VALIDATED"
MODE = "DEVELOPMENT_TEST_ONLY"
CONTRACT_STATUS = "DRAFT_NOT_IN_FORCE"

EXPECTED_PACKET_VERSION = "TASK-008-fact-packet-1.1"
EXPECTED_PACKET_STATUS = "DEV_FACT_PACKET_READY"
EXPECTED_COMPANY = "澄明商贸有限公司"
EXPECTED_CURRENCY = "人民币（CNY）"
EXPECTED_PERIOD_START = "2026-09-01"
EXPECTED_PERIOD_END = "2026-09-30"
EXPECTED_CUTOFF_DATE = "2026-09-30"
RULE_IDS = ("R01", "R02", "R03", "R04")
SOURCE_FINGERPRINT_FIELDS = ("workbook_sha256", "normalized_payload_sha256",
                             "screening_report_sha256", "crosscheck_report_sha256")

SCOPE = "BATCH_FACT_PACKET"
ACTOR_KIND = "SIMULATED_HUMAN"
SIMULATION = "SIMULATED_TEST_ONLY"

SUBMISSION_REQUIRED_KEYS = ("submission_version", "event_id", "batch_id", "fact_packet_sha256",
                            "scope", "actor_kind", "actor_id", "simulation", "occurred_at",
                            "assessment", "reason")
SUBMISSION_OPTIONAL_KEYS = ("needed_evidence", "finding_notes")
SUBMISSION_ALLOWED_KEYS = SUBMISSION_REQUIRED_KEYS + SUBMISSION_OPTIONAL_KEYS
FINDING_NOTE_ALLOWED_KEYS = ("finding_id", "note")

BOUNDARIES = [
    "本记录是合成数据上的开发态模拟初判：身份为调用方显式声明的模拟身份，不代表任何真实人类、"
    "主理人或机构已经作出初判。",
    "本核心只在内存中完成校验与事实绑定；返回状态 VALIDATED 只表示本次输入成立，"
    "不代表记录已保存、已持久化或已获批准。",
    "调用方身份未经认证；本核心不校验 actor_id 的真实归属，也不声称能识别文本是否由人类独立完成。",
    "人类独立初判必须先于任何 AI 对照建议；本记录不生成、不预填、不采纳 AI 建议，"
    "ai_suggestion_allowed 恒为 false。",
    "真实人类初判、终判与真实 Gate 批准只能由主理人作出；本模块不建立正式契约、不提供真实批准接口。",
    "事实包中的规则命中仍是待核实线索；本记录不改变事实包内容，也不构成审计结论。",
]

_HEX64 = re.compile(r"[0-9a-f]{64}")
_ISO8601_TZ = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
                         r"(?:Z|[+-]\d{2}:\d{2})$")


class InitialJudgmentBlocked(Exception):
    """输入、协议或事实绑定不符（指出字段与原因），不返回成功记录。"""

    def __init__(self, message: str, reasons: list | None = None, field: str = ""):
        super().__init__(message)
        self.reasons = reasons or [message]
        self.field = field


class InitialJudgmentError(Exception):
    """意外内部错误（保留原始 cause 链）。"""

    def __init__(self, message: str, reasons: list | None = None, stage: str = ""):
        super().__init__(message)
        self.reasons = reasons or [message]
        self.stage = stage


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def canonical_json(payload) -> str:
    """约定规范 JSON（UTF-8 字节串即此字符串的 UTF-8 编码）。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def canonical_json_sha256(payload) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _require(condition: bool, field: str, reason: str) -> None:
    if not condition:
        raise InitialJudgmentBlocked(f"字段 {field} 不可用：{reason}", field=field)


def _is_non_empty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_hex64(value) -> bool:
    # 必须整个字符串完整匹配：恰 64 位小写十六进制。
    # 用 fullmatch 而非 match/`$` 锚点——`$` 允许在末尾换行前匹配，会让 65 字符的
    # 「64 位十六进制 + LF」被当成合法指纹；这里不做 strip/截断/转小写等静默修正。
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _require_plain_string(value, field: str, label: str) -> str:
    _require(isinstance(value, str), field,
             f"{label}必须是字符串（不接受 bool 或数字），实际 {type(value).__name__}")
    return value


# ---------------------------------------------------------------------------
# 事实包核验与绑定
# ---------------------------------------------------------------------------


def _check_packet(fact_packet: dict, expected_packet_sha256: str) -> dict:
    _require(isinstance(fact_packet, dict), "fact_packet",
             f"必须是对象，实际 {type(fact_packet).__name__}")
    _require(_is_hex64(expected_packet_sha256), "expected_packet_sha256",
             "必须是 64 位小写十六进制字符串")
    try:
        packet_fingerprint = canonical_json_sha256(fact_packet)
    except (TypeError, ValueError) as exc:
        raise InitialJudgmentBlocked(f"字段 fact_packet 不可用：无法按约定规范 JSON 编码（{exc}）",
                                     field="fact_packet") from exc
    _require(packet_fingerprint == expected_packet_sha256, "expected_packet_sha256",
             f"必须等于本次 fact_packet 对象的规范指纹 {packet_fingerprint}，"
             f"实际 {expected_packet_sha256}")
    _require(fact_packet.get("packet_version") == EXPECTED_PACKET_VERSION, "fact_packet.packet_version",
             f"必须是 {EXPECTED_PACKET_VERSION}，实际 {fact_packet.get('packet_version')!r}")
    _require(fact_packet.get("batch_status") == EXPECTED_PACKET_STATUS, "fact_packet.batch_status",
             f"必须是 {EXPECTED_PACKET_STATUS}，实际 {fact_packet.get('batch_status')!r}")
    _require(fact_packet.get("mode") == MODE, "fact_packet.mode", f"必须是 {MODE}")
    _require(fact_packet.get("next_step_allowed") is False, "fact_packet.next_step_allowed",
             f"必须是严格 false，实际 {fact_packet.get('next_step_allowed')!r}")
    entity = fact_packet.get("entity")
    _require(isinstance(entity, dict), "fact_packet.entity",
             f"必须是对象，实际 {type(entity).__name__}")
    _require(entity.get("company") == EXPECTED_COMPANY, "fact_packet.entity.company",
             f"必须是 {EXPECTED_COMPANY}，实际 {entity.get('company')!r}")
    period = entity.get("period")
    _require(isinstance(period, dict), "fact_packet.entity.period",
             f"必须是对象，实际 {type(period).__name__}")
    _require(period.get("period_start") == EXPECTED_PERIOD_START
             and period.get("period_end") == EXPECTED_PERIOD_END, "fact_packet.entity.period",
             f"必须覆盖 {EXPECTED_PERIOD_START}—{EXPECTED_PERIOD_END}，实际 {period!r}")
    _require(entity.get("cutoff_date") == EXPECTED_CUTOFF_DATE, "fact_packet.entity.cutoff_date",
             f"必须是 {EXPECTED_CUTOFF_DATE}，实际 {entity.get('cutoff_date')!r}")
    _require(entity.get("currency") == EXPECTED_CURRENCY, "fact_packet.entity.currency",
             f"必须是 {EXPECTED_CURRENCY}，实际 {entity.get('currency')!r}")
    bindings = fact_packet.get("bindings")
    _require(isinstance(bindings, dict), "fact_packet.bindings",
             f"必须是对象，实际 {type(bindings).__name__}")
    for field in SOURCE_FINGERPRINT_FIELDS:
        _require(field in bindings, f"fact_packet.bindings.{field}", "字段必须存在")
        _require(_is_hex64(bindings[field]), f"fact_packet.bindings.{field}",
                 f"必须是 64 位小写十六进制指纹，实际 {bindings[field]!r}")
    findings = fact_packet.get("findings")
    _require(isinstance(findings, list), "fact_packet.findings",
             f"必须是列表，实际 {type(findings).__name__}")
    finding_ids: list = []
    for index, finding in enumerate(findings):
        _require(isinstance(finding, dict), f"fact_packet.findings[{index}]",
                 f"必须是对象，实际 {type(finding).__name__}")
        finding_id = finding.get("finding_id")
        _require(_is_non_empty_str(finding_id), f"fact_packet.findings[{index}].finding_id",
                 f"必须是非空字符串，实际 {finding_id!r}")
        _require(finding_id not in finding_ids, f"fact_packet.findings[{index}].finding_id",
                 f"线索 ID 必须唯一，重复 {finding_id!r}")
        finding_ids.append(finding_id)
        _require(finding.get("rule_id") in RULE_IDS, f"fact_packet.findings[{index}].rule_id",
                 f"必须是 {list(RULE_IDS)} 之一，实际 {finding.get('rule_id')!r}")
    return {"packet_fingerprint": packet_fingerprint, "entity": entity,
            "bindings": bindings, "finding_ids": finding_ids}


# ---------------------------------------------------------------------------
# 提交协议核验与规范化
# ---------------------------------------------------------------------------


def _check_submission(submission: dict, batch_id: str, packet_info: dict,
                      expected_packet_sha256: str) -> dict:
    _require(isinstance(submission, dict), "submission",
             f"必须是对象，实际 {type(submission).__name__}")
    unknown = sorted(set(submission) - set(SUBMISSION_ALLOWED_KEYS))
    _require(not unknown, "submission",
             f"存在不允许的键 {unknown}；本卡只接受必填键 {list(SUBMISSION_REQUIRED_KEYS)} "
             f"与可选键 {list(SUBMISSION_OPTIONAL_KEYS)}（越界字段不静默忽略）")
    missing = [key for key in SUBMISSION_REQUIRED_KEYS if key not in submission]
    _require(not missing, "submission", f"缺少必填键 {missing}")
    _require(submission["submission_version"] == SUBMISSION_VERSION,
             "submission.submission_version",
             f"必须是 {SUBMISSION_VERSION}，实际 {submission['submission_version']!r}")
    _require(_is_non_empty_str(submission["event_id"]), "submission.event_id",
             f"必须是非空字符串（本核心不生成事件 ID），实际 {submission['event_id']!r}")
    _require(_is_non_empty_str(submission["batch_id"]), "submission.batch_id",
             f"必须是非空字符串，实际 {submission['batch_id']!r}")
    _require(submission["batch_id"] == batch_id, "submission.batch_id",
             f"必须等于本次 API 的 batch_id {batch_id!r}，实际 {submission['batch_id']!r}")
    _require(_is_hex64(submission["fact_packet_sha256"]), "submission.fact_packet_sha256",
             f"必须是 64 位小写十六进制指纹（整个字符串完整匹配、不接受尾随 LF），"
             f"实际 {submission['fact_packet_sha256']!r}")
    _require(submission["fact_packet_sha256"] == expected_packet_sha256,
             "submission.fact_packet_sha256",
             f"必须等于本次已验证的 packet 规范指纹 {expected_packet_sha256}，"
             f"实际 {submission['fact_packet_sha256']!r}")
    _require(submission["scope"] == SCOPE, "submission.scope",
             f"必须是 {SCOPE}，实际 {submission['scope']!r}")
    _require(submission["actor_kind"] == ACTOR_KIND, "submission.actor_kind",
             f"必须是 {ACTOR_KIND}（本卡只支持显式模拟身份，不接受真实 HUMAN/AI 身份），"
             f"实际 {submission['actor_kind']!r}")
    _require(_is_non_empty_str(submission["actor_id"]), "submission.actor_id",
             f"必须是非空字符串，实际 {submission['actor_id']!r}")
    _require(submission["simulation"] == SIMULATION, "submission.simulation",
             f"必须是 {SIMULATION}，实际 {submission['simulation']!r}")
    occurred_at = _require_plain_string(submission["occurred_at"], "submission.occurred_at",
                                        "发生时间")
    _require(bool(_ISO8601_TZ.match(occurred_at.strip())), "submission.occurred_at",
             f"必须是含时区的 ISO8601 日期时间（不接受无时区），实际 {occurred_at!r}")
    normalized_time = occurred_at.strip()
    try:
        parsed = datetime.datetime.fromisoformat(
            normalized_time[:-1] + "+00:00" if normalized_time.endswith("Z") else normalized_time)
    except ValueError as exc:
        raise InitialJudgmentBlocked(
            f"字段 submission.occurred_at 不可用：不是有效的 ISO8601 日期时间（{exc}），"
            f"实际 {occurred_at!r}", field="submission.occurred_at") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
             "submission.occurred_at", f"必须显式携带时区偏移，实际 {occurred_at!r}")
    assessment = _require_plain_string(submission["assessment"], "submission.assessment",
                                       "初判文本")
    _require(assessment.strip() != "", "submission.assessment",
             "去空白后必须非空（不允许只写空白）")
    reason = _require_plain_string(submission["reason"], "submission.reason", "原因文本")
    _require(reason.strip() != "", "submission.reason",
             "去空白后必须非空（“暂不能判断”也必须给出调用方原因）")

    needed = submission.get("needed_evidence", [])
    _require(isinstance(needed, list), "submission.needed_evidence",
             f"必须是列表，实际 {type(needed).__name__}")
    needed_clean = []
    for index, item in enumerate(needed):
        _require(_is_non_empty_str(item), f"submission.needed_evidence[{index}]",
                 f"必须是非空字符串，实际 {item!r}")
        needed_clean.append(item)

    notes = submission.get("finding_notes", [])
    _require(isinstance(notes, list), "submission.finding_notes",
             f"必须是列表，实际 {type(notes).__name__}")
    notes_clean = []
    seen_ids: list = []
    for index, note in enumerate(notes):
        _require(isinstance(note, dict), f"submission.finding_notes[{index}]",
                 f"必须是对象，实际 {type(note).__name__}")
        unknown_note = sorted(set(note) - set(FINDING_NOTE_ALLOWED_KEYS))
        _require(not unknown_note, f"submission.finding_notes[{index}]",
                 f"只允许 {list(FINDING_NOTE_ALLOWED_KEYS)}，实际多出 {unknown_note}")
        for key in FINDING_NOTE_ALLOWED_KEYS:
            _require(key in note, f"submission.finding_notes[{index}].{key}", "缺少必需键")
        finding_id = note["finding_id"]
        _require(_is_non_empty_str(finding_id), f"submission.finding_notes[{index}].finding_id",
                 f"必须是非空字符串，实际 {finding_id!r}")
        _require(finding_id in packet_info["finding_ids"],
                 f"submission.finding_notes[{index}].finding_id",
                 f"必须存在于当前 packet 的线索中，实际 {finding_id!r}")
        _require(finding_id not in seen_ids, f"submission.finding_notes[{index}].finding_id",
                 f"不得重复备注同一线索，重复 {finding_id!r}")
        seen_ids.append(finding_id)
        text = _require_plain_string(note["note"], f"submission.finding_notes[{index}].note",
                                     "备注")
        _require(text.strip() != "", f"submission.finding_notes[{index}].note",
                 "去空白后必须非空")
        notes_clean.append({"finding_id": finding_id, "note": text})

    # 确定性规范化：两可选键省略即写空列表；其余文字按原字符串完整保留
    normalized = {
        "submission_version": submission["submission_version"],
        "event_id": submission["event_id"],
        "batch_id": submission["batch_id"],
        "fact_packet_sha256": submission["fact_packet_sha256"],
        "scope": submission["scope"],
        "actor_kind": submission["actor_kind"],
        "actor_id": submission["actor_id"],
        "simulation": submission["simulation"],
        "occurred_at": occurred_at,
        "assessment": assessment,
        "reason": reason,
        "needed_evidence": needed_clean,
        "finding_notes": notes_clean,
    }
    return normalized


# ---------------------------------------------------------------------------
# 业务入口
# ---------------------------------------------------------------------------


def build_initial_judgment_record(batch_id, fact_packet, submission, *,
                                  expected_packet_sha256) -> dict:
    """校验调用方提供的模拟初判并绑定事实包，返回 {record, record_sha256}（纯内存，不保存）。"""
    try:
        _require(_is_non_empty_str(batch_id), "batch_id",
                 f"必须是非空字符串，实际 {batch_id!r}")
        packet_info = _check_packet(fact_packet, expected_packet_sha256)
        normalized = _check_submission(submission, batch_id, packet_info,
                                       expected_packet_sha256)
        record = {
            "record_version": RECORD_VERSION,
            "batch_status": RECORD_STATUS,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "next_step_allowed": False,
            "ai_suggestion_allowed": False,
            "gate1_approval": None,
            "gate2_approval": None,
            "human_initial_judgment": None,
            "ai_suggestion": None,
            "final_judgment": None,
            "source": {
                "batch_id": batch_id,
                "fact_packet_sha256": packet_info["packet_fingerprint"],
                "packet_version": fact_packet["packet_version"],
                "entity": copy.deepcopy(packet_info["entity"]),
                "workbook_sha256": packet_info["bindings"]["workbook_sha256"],
                "normalized_payload_sha256":
                    packet_info["bindings"]["normalized_payload_sha256"],
                "screening_report_sha256": packet_info["bindings"]["screening_report_sha256"],
                "crosscheck_report_sha256": packet_info["bindings"]["crosscheck_report_sha256"],
                "finding_ids": list(packet_info["finding_ids"]),
            },
            "simulated_initial_judgment": copy.deepcopy(normalized),
            "boundaries": list(BOUNDARIES),
        }
        record_sha256 = canonical_json_sha256(record)
    except InitialJudgmentBlocked:
        raise
    except InitialJudgmentError:
        raise
    except Exception as exc:  # noqa: BLE001 - 统一保留阶段与异常链
        raise InitialJudgmentError(
            f"[initial_judgment] 校验或绑定失败：{type(exc).__name__}: {exc}",
            [f"阶段=initial_judgment", f"原始异常={type(exc).__name__}: {exc}"],
        ) from exc
    return {"record": record, "record_sha256": record_sha256}
