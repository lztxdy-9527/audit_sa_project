#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-008 事实底稿构建核心：把已计算、已复核的事实整理为可阅读的 Markdown 与完整 JSON 证据包。

本模块只提供 Python API，**不读写文件、不读数据库／Excel／答案册**，也不调用筛查或复核核心：

    build_fact_packet(normalized: dict, screening_report: dict, crosscheck_report: dict) -> dict

返回 `{"packet": ..., "packet_sha256": ..., "markdown": ...}`；`packet_sha256` 是对 packet 的规范 JSON
指纹（放在外层以避免自引用）。同输入必须得到完全相同的 Markdown 与 packet。

这是确定性展示层：不新增审计规则、不重算命中、不生成 AI 意见、不预填人类判断，也不把输入中的
自由文本（`fact`／`verification_prompt`）当作叙述来源。所有输入文字只作数据展示并作必要转义。

异常类型：
  FactPacketBlocked  前提、绑定或展示所需字段不成立；带字段／原因，不返回半份 READY 底稿。
  FactPacketError    意外运行失败；保留阶段、原始原因与异常链。
"""

from __future__ import annotations

import hashlib
import json

PACKET_VERSION = "TASK-008-fact-packet-1.1"
PACKET_STATUS = "DEV_FACT_PACKET_READY"
MODE = "DEVELOPMENT_TEST_ONLY"
COMPANY = "澄明商贸有限公司"
CURRENCY = "人民币（CNY）"
PERIOD_START = "2026-09-01"
PERIOD_END = "2026-09-30"
CUTOFF_DATE = "2026-09-30"
EXPECTED_NORMALIZATION_VERSION = "TASK-004-normalized-1.1"
EXPECTED_RULES_STATUS = "DEV_RULES_COMPUTED"
EXPECTED_RULE_CORE_VERSION = "TASK-006-rule-core-1.1"
EXPECTED_CROSSCHECK_STATUS = "DEV_CROSSCHECK_MATCHED"
EXPECTED_CROSSCHECK_VERSION = "TASK-007-crosscheck-1.2"
EXPECTED_LOAD_STATUS = "DEV_SQLITE_VERIFIED"
RULE_IDS = ("R01", "R02", "R03", "R04")
RULE_NAMES = {
    "R01": "现存重复足额付款",
    "R02": "应付单净付款超额",
    "R03": "在提供的应付台账中未找到关联对象",
    "R04": "收款对象与应付供应商不同",
}
RULE_TEMPLATES = {
    "R01": "同一应付单与同一收款对象下，至少两笔不同原付款各自的退款后净额精确等于应付金额。",
    "R02": "同一应付单的已结算净付款（付款分摊减有效退款分摊）严格大于应付金额，按唯一应付单汇总一次。",
    "R03": "该已结算原付款分摊的应付关联为空，或所填标识在所提供台账中不存在；金额保留在总体勾稽中。",
    "R04": "该已结算原付款分摊的实际收款对象与应付单供应商不同；对象差异不能自动判错，可能有授权代收等合理解释。",
}
CROSSCHECK_DIMENSIONS = (
    "hit_keys",
    "amounts_cents",
    "related_ids",
    "refund_facts",
    "rule_identity",
    "source_entities",
    "source_rows",
    "counts",
    "statistics",
    "overall_reconciliation",
)
REQUIRED_AMOUNTS = {
    "R01": ("payable_amount", "net_per_payment", "net_total"),
    "R02": ("payable_amount", "paid_total", "refund_total", "net_total", "overpayment"),
    "R03": ("allocated_amount", "paid_amount", "refunded_amount", "net_amount"),
    "R04": ("allocated_amount", "payable_amount", "refunded_amount", "net_amount"),
}
BANNER = [
    "本文件为合成数据上的开发演示事实底稿，不代表任何真实企业、真实交易或真实审计发现。",
    "规则命中是待核实线索，不构成舞弊、损失、控制缺陷或审计调整结论。",
    "两种实现（SQL 筛查与独立复算）一致只说明对该输入的计算一致，不证明来源真实或业务合理。",
    "未实施正式契约与批准控制，未保存人类判断，未生成 AI 建议；本底稿不可作为已获批审计底稿。",
]
LIMITS = [
    "规则命中不是审计结论；跨规则的涉及金额不相加称为损失。",
    "资金主表口径与分摊口径分别列示，不相加；整笔付款金额不能当作分摊金额或缺失关联分摊额。",
    "复核一致不证明来源真实，也不抵御同权限篡改；数据库哈希仅为上游报告声明值，展示层未读取数据库字节。",
    "未实施正式契约／批准控制，未保存人类判断，未生成 AI 建议；后续须经人工核实与放行。",
]
MISSING_KIND_LABEL = {
    "EMPTY_AP_ID": "未填写关联",
    "AP_NOT_IN_LEDGER": "所填标识不在提供的台账",
}
AMOUNT_LABELS = {
    "payable_amount": "应付金额",
    "net_per_payment": "各笔原付款的分摊净额",
    "paid_total": "已结算付款分摊合计",
    "refund_total": "有效退款分摊合计",
    "overpayment": "净付款超额",
    "allocated_amount": "本条付款分摊金额",
    "paid_amount": "已结算原付款分摊额",
    "refunded_amount": "有效退款分摊额",
    "net_amount": "本条分摊净额",
}
NET_TOTAL_LABELS = {
    "R01": "本足额付款组的分摊净额合计",
    "R02": "该应付单的净付款分摊合计",
}
DISPLAY_PAYMENT_FIELDS = ("payment_id", "payment_date", "settlement_status", "bank_reference",
                          "amount_cents", "payee_supplier_id")
DISPLAY_PAYABLE_FIELDS = ("ap_id", "ap_number", "ap_date", "supplier_id", "payable_amount_cents")
DISPLAY_ALLOCATION_FIELDS = ("allocation_id", "payment_id", "allocated_amount_cents")
DISPLAY_REFUND_FIELDS = ("refund_allocation_id", "refund_payment_id", "original_payment_id",
                         "original_allocation_id", "allocated_amount_cents", "settlement_status",
                         "payment_date", "counted_in_net")
SPACE_MARK = "\u2420"  # 用于 Markdown 中显式显示首尾空格；JSON 保留原值


class FactPacketBlocked(Exception):
    """前提、绑定或展示所需字段不成立。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


class FactPacketError(Exception):
    """意外运行失败；保留阶段、原始原因与异常链。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def canonical_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(payload) -> str:
    try:
        text = canonical_json(payload)
    except (TypeError, ValueError) as exc:
        raise FactPacketBlocked(f"对象无法按规范 JSON 序列化：{type(exc).__name__}: {exc}") from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def format_cents(cents: int) -> str:
    """整数分 → 人民币元两位小数；只用整数运算，不做浮点除法或四舍五入。"""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise FactPacketError(f"[format_cents] 金额必须是整数分（非 bool），实际 {type(cents).__name__}")
    sign = "-" if cents < 0 else ""
    value = abs(cents)
    return f"{sign}{value // 100}.{value % 100:02d}"


def money(cents: int) -> str:
    return f"{format_cents(cents)} 元"


def escape_markdown(value) -> str:
    """Markdown 安全展示：转义 HTML、反引号、竖线、链接语法与换行；首尾空格显式标记。"""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("`", "\\`").replace("|", "\\|")
    text = text.replace("[", "\\[").replace("]", "\\]")
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    if text != text.strip():
        leading = len(text) - len(text.lstrip(" "))
        trailing = len(text) - len(text.rstrip(" "))
        core = text.strip(" ")
        text = f"{SPACE_MARK * leading}{core}{SPACE_MARK * trailing}"
    return text


def _require(condition: bool, path: str, reason: str) -> None:
    if not condition:
        raise FactPacketBlocked(f"输入字段 {path} 不可用：{reason}")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# 前提与绑定核对
# ---------------------------------------------------------------------------


def _check_inputs(normalized, screening_report, crosscheck_report) -> dict:
    for name, payload in (("normalized", normalized), ("screening_report", screening_report),
                          ("crosscheck_report", crosscheck_report)):
        _require(isinstance(payload, dict), name, f"必须是对象，实际 {type(payload).__name__}")

    for name, payload in (("normalized", normalized), ("screening_report", screening_report),
                          ("crosscheck_report", crosscheck_report)):
        _require(payload.get("mode") == MODE, f"{name}.mode", f"必须是 {MODE}，实际 {payload.get('mode')!r}")
        _require(payload.get("next_step_allowed") is False, f"{name}.next_step_allowed", "必须是 false")

    _require(normalized.get("normalization_version") == EXPECTED_NORMALIZATION_VERSION,
             "normalized.normalization_version",
             f"必须是 {EXPECTED_NORMALIZATION_VERSION}，实际 {normalized.get('normalization_version')!r}")
    quality = normalized.get("quality_report")
    _require(isinstance(quality, dict), "normalized.quality_report", "必须是对象")
    _require(quality.get("result") == "pass", "normalized.quality_report.result",
             f"必须是 pass，实际 {quality.get('result')!r}")
    issue_counts = quality.get("issue_counts_by_code")
    _require(isinstance(issue_counts, dict), "normalized.quality_report.issue_counts_by_code",
             f"必须存在且为对象，实际 {type(issue_counts).__name__}")
    _require(not issue_counts, "normalized.quality_report.issue_counts_by_code",
             f"质量通过必须无未解决问题，实际 {issue_counts!r}")

    _require(screening_report.get("batch_status") == EXPECTED_RULES_STATUS, "screening_report.batch_status",
             f"必须是 {EXPECTED_RULES_STATUS}，实际 {screening_report.get('batch_status')!r}")
    _require(screening_report.get("rule_core_version") == EXPECTED_RULE_CORE_VERSION,
             "screening_report.rule_core_version",
             f"必须是 {EXPECTED_RULE_CORE_VERSION}，实际 {screening_report.get('rule_core_version')!r}")

    _require(crosscheck_report.get("batch_status") == EXPECTED_CROSSCHECK_STATUS,
             "crosscheck_report.batch_status",
             f"必须是 {EXPECTED_CROSSCHECK_STATUS}，实际 {crosscheck_report.get('batch_status')!r}")
    _require(crosscheck_report.get("crosscheck_version") == EXPECTED_CROSSCHECK_VERSION,
             "crosscheck_report.crosscheck_version",
             f"必须是 {EXPECTED_CROSSCHECK_VERSION}，实际 {crosscheck_report.get('crosscheck_version')!r}")
    _require(crosscheck_report.get("matched") is True, "crosscheck_report.matched", "必须严格为 true")
    _require(crosscheck_report.get("differences") == [], "crosscheck_report.differences", "必须为空列表")
    comparison = crosscheck_report.get("comparison")
    _require(isinstance(comparison, dict), "crosscheck_report.comparison", "必须是对象")
    _require(_is_int(comparison.get("difference_count")) and comparison["difference_count"] == 0,
             "crosscheck_report.comparison.difference_count", "必须是整数 0")
    dimensions = comparison.get("dimensions")
    _require(isinstance(dimensions, dict), "crosscheck_report.comparison.dimensions", "必须是对象")
    for name in CROSSCHECK_DIMENSIONS:
        entry = dimensions.get(name)
        _require(isinstance(entry, dict), f"comparison.dimensions.{name}", "必须是对象")
        _require(entry.get("executed") is True, f"comparison.dimensions.{name}.executed", "必须严格为 true")
        _require(entry.get("matched") is True, f"comparison.dimensions.{name}.matched", "必须严格为 true")
        _require(_is_int(entry.get("difference_count")) and entry["difference_count"] == 0,
                 f"comparison.dimensions.{name}.difference_count", "必须是整数 0")
    for name in dimensions:
        _require(name in CROSSCHECK_DIMENSIONS, f"comparison.dimensions.{name}", "不是本版固定维度")

    for name, payload in (("screening_report", screening_report), ("crosscheck_report", crosscheck_report)):
        period = payload.get("period")
        _require(isinstance(period, dict), f"{name}.period", "必须是对象")
        _require(period.get("period_start") == PERIOD_START and period.get("period_end") == PERIOD_END,
                 f"{name}.period", f"必须是 {PERIOD_START}—{PERIOD_END}，实际 {period!r}")
        _require(payload.get("cutoff_date") == CUTOFF_DATE, f"{name}.cutoff_date",
                 f"必须是 {CUTOFF_DATE}，实际 {payload.get('cutoff_date')!r}")
    _require(crosscheck_report.get("rule_core_version_checked") == screening_report.get("rule_core_version"),
             "crosscheck_report.rule_core_version_checked", "必须与筛查报告的规则核心版本一致")

    load_source = screening_report.get("load_source")
    _require(isinstance(load_source, dict), "screening_report.load_source", "必须是对象")
    run_metadata = load_source.get("run_metadata")
    _require(isinstance(run_metadata, dict), "screening_report.load_source.run_metadata", "必须是对象")
    source = normalized.get("source")
    _require(isinstance(source, dict), "normalized.source", "必须是对象")
    input_sha = source.get("input_sha256")
    _require(isinstance(input_sha, str) and len(input_sha) == 64, "normalized.source.input_sha256",
             "必须是 64 位哈希")

    fingerprint = canonical_sha256(normalized)
    for path, actual in (
        ("screening_report.load_source.normalized_payload_sha256", load_source.get("normalized_payload_sha256")),
        ("load_source.run_metadata.normalized_payload_sha256", run_metadata.get("normalized_payload_sha256")),
        ("crosscheck_report.normalized_payload_sha256", crosscheck_report.get("normalized_payload_sha256")),
    ):
        _require(actual == fingerprint, path, f"必须等于本次 normalized 规范指纹：{actual} != {fingerprint}")
    screening_fingerprint = canonical_sha256(screening_report)
    _require(crosscheck_report.get("screening_report_sha256") == screening_fingerprint,
             "crosscheck_report.screening_report_sha256",
             f"必须等于本次筛查对象规范指纹：{crosscheck_report.get('screening_report_sha256')} "
             f"!= {screening_fingerprint}")
    for path, actual in (
        ("screening_report.load_source.input_sha256", load_source.get("input_sha256")),
        ("load_source.run_metadata.input_sha256", run_metadata.get("input_sha256")),
        ("crosscheck_report.input_source_sha256", crosscheck_report.get("input_source_sha256")),
    ):
        _require(actual == input_sha, path, f"必须与 normalized 来源哈希一致：{actual} != {input_sha}")

    before = screening_report.get("database_sha256_before")
    after = screening_report.get("database_sha256_after")
    _require(before == after == load_source.get("database_sha256"), "screening_report.database_sha256",
             f"before／after／load_source 必须相等：{before} / {after} / {load_source.get('database_sha256')}")
    _require(screening_report.get("database_unchanged") is True, "screening_report.database_unchanged",
             "必须是 true")

    findings = screening_report.get("findings")
    _require(isinstance(findings, list), "screening_report.findings", "必须是列表")
    rule_counts = screening_report.get("rule_hit_counts")
    _require(isinstance(rule_counts, dict), "screening_report.rule_hit_counts", "必须是对象")
    statistics = screening_report.get("statistics")
    _require(isinstance(statistics, dict), "screening_report.statistics", "必须是对象")
    reconciliation = screening_report.get("overall_reconciliation")
    _require(isinstance(reconciliation, dict), "screening_report.overall_reconciliation", "必须是对象")
    rules = screening_report.get("rules")
    _require(isinstance(rules, dict), "screening_report.rules", "必须是对象")

    derived_counts: dict[str, int] = {rule_id: 0 for rule_id in RULE_IDS}
    for index, finding in enumerate(findings):
        path = f"screening_report.findings[{index}]"
        _require(isinstance(finding, dict), path, "必须是对象")
        rule_id = finding.get("rule_id")
        _require(rule_id in RULE_IDS, f"{path}.rule_id", f"必须是 R01—R04，实际 {rule_id!r}")
        derived_counts[rule_id] += 1
        hit_key = finding.get("hit_key")
        _require(isinstance(hit_key, dict), f"{path}.hit_key", "必须是对象")
        _require(hit_key.get("rule_id") == rule_id, f"{path}.hit_key.rule_id", "必须与 finding.rule_id 一致")
        for field, value in sorted(hit_key.items()):
            _require(isinstance(value, str) and value != "", f"{path}.hit_key.{field}",
                     f"必须是非空字符串，实际 {type(value).__name__}")
        amounts = finding.get("amounts_cents")
        _require(isinstance(amounts, dict), f"{path}.amounts_cents", "必须是对象")
        for key in REQUIRED_AMOUNTS[rule_id]:
            _require(key in amounts, f"{path}.amounts_cents.{key}", "缺少展示所需的规则金额")
            value = amounts[key]
            if key == "net_per_payment":
                _require(isinstance(value, dict) and value, f"{path}.amounts_cents.{key}", "必须是非空对象")
                for payment_id, cents in value.items():
                    _require(isinstance(payment_id, str) and payment_id != "",
                             f"{path}.amounts_cents.{key}.键", "必须是原字符串付款 ID")
                    _require(_is_int(cents), f"{path}.amounts_cents.{key}.{payment_id}",
                             f"必须是整数分（非 bool），实际 {type(cents).__name__}")
            else:
                _require(_is_int(value), f"{path}.amounts_cents.{key}",
                         f"必须是整数分（非 bool），实际 {type(value).__name__}")
        related = finding.get("related_ids")
        _require(isinstance(related, dict), f"{path}.related_ids", "必须是对象")
        for key in ("payment_ids", "allocation_ids", "refund_ids"):
            value = related.get(key)
            _require(isinstance(value, list), f"{path}.related_ids.{key}", "必须是列表")
            for item in value:
                _require(isinstance(item, str) and item != "", f"{path}.related_ids.{key}",
                         f"ID 必须是原字符串，实际 {type(item).__name__}")
        source_rows = finding.get("source_rows")
        _require(isinstance(source_rows, dict), f"{path}.source_rows", "必须是对象")
        evidence = finding.get("evidence")
        _require(isinstance(evidence, dict), f"{path}.evidence", "必须是对象")
        entities = evidence.get("entities")
        _require(isinstance(entities, list) and entities, f"{path}.evidence.entities", "必须是非空列表")
        for position, entity in enumerate(entities):
            entity_path = f"{path}.evidence.entities[{position}]"
            _require(isinstance(entity, dict), entity_path, "必须是对象")
            for key in ("table_name", "record_id", "workbook_sha256", "sheet", "excel_row", "cells"):
                _require(key in entity, f"{entity_path}.{key}", "缺少展示与追溯所需的来源字段")
            _require(_is_int(entity["excel_row"]), f"{entity_path}.excel_row", "必须是整数行号")
            _require(isinstance(entity["cells"], dict) and entity["cells"], f"{entity_path}.cells",
                     "必须是完整 cells 对象")
        refunds = evidence.get("related_refunds")
        _require(isinstance(refunds, list), f"{path}.evidence.related_refunds", "必须是列表")
        for position, refund in enumerate(refunds):
            refund_path = f"{path}.evidence.related_refunds[{position}]"
            _require(isinstance(refund, dict), refund_path, "必须是对象")
            for key in ("refund_allocation_id", "refund_payment_id", "allocated_amount_cents",
                        "settlement_status", "payment_date", "counted_in_net"):
                _require(key in refund, f"{refund_path}.{key}", "缺少展示所需的退款字段")
            _require(_is_int(refund["allocated_amount_cents"]), f"{refund_path}.allocated_amount_cents",
                     "必须是整数分（非 bool）")
            _require(isinstance(refund["counted_in_net"], bool), f"{refund_path}.counted_in_net",
                     "必须是布尔值")

    derived_total = sum(derived_counts.values())
    for rule_id in RULE_IDS:
        _require(rule_counts.get(rule_id) == derived_counts[rule_id], f"screening_report.rule_hit_counts.{rule_id}",
                 f"必须与 findings 条数一致：{rule_counts.get(rule_id)} != {derived_counts[rule_id]}")
        entry = rules.get(rule_id)
        _require(isinstance(entry, dict), f"screening_report.rules.{rule_id}", "必须是对象")
        _require(entry.get("hit_count") == derived_counts[rule_id], f"screening_report.rules.{rule_id}.hit_count",
                 "必须与 findings 条数一致")
    _require(rule_counts.get("total") == derived_total, "screening_report.rule_hit_counts.total",
             f"必须等于 findings 条数 {derived_total}，实际 {rule_counts.get('total')!r}")
    recomputed_counts = crosscheck_report.get("rule_recomputed_counts")
    _require(isinstance(recomputed_counts, dict), "crosscheck_report.rule_recomputed_counts", "必须是对象")
    for key in (*RULE_IDS, "total"):
        _require(recomputed_counts.get(key) == (derived_total if key == "total" else derived_counts[key]),
                 f"crosscheck_report.rule_recomputed_counts.{key}", "必须与筛查 findings 条数一致")

    return {
        "normalized_fingerprint": fingerprint,
        "screening_fingerprint": screening_fingerprint,
        "crosscheck_fingerprint": canonical_sha256(crosscheck_report),
        "input_sha256": input_sha,
        "derived_counts": derived_counts,
    }


# ---------------------------------------------------------------------------
# 上下文与事实卡
# ---------------------------------------------------------------------------


def _index_records(normalized: dict) -> dict:
    tables = normalized.get("tables")
    _require(isinstance(tables, dict), "normalized.tables", "必须是对象")
    index: dict[str, dict] = {}
    for sheet, key_field in (("suppliers", "supplier_id"), ("payables", "ap_id"),
                             ("payments", "payment_id"), ("allocations", "allocation_id")):
        table = tables.get(sheet)
        _require(isinstance(table, dict), f"normalized.tables.{sheet}", "必须是对象")
        records = table.get("records")
        _require(isinstance(records, list), f"normalized.tables.{sheet}.records", "必须是列表")
        by_id: dict[str, dict] = {}
        for position, record in enumerate(records):
            path = f"normalized.tables.{sheet}.records[{position}]"
            _require(isinstance(record, dict), path, "必须是对象")
            data = record.get("data")
            source = record.get("source")
            cells = record.get("cells")
            _require(isinstance(data, dict), f"{path}.data", "必须是对象")
            _require(isinstance(source, dict), f"{path}.source", "必须是对象")
            _require(isinstance(cells, dict), f"{path}.cells", "必须是对象")
            record_id = data.get(key_field)
            _require(isinstance(record_id, str) and record_id != "", f"{path}.data.{key_field}",
                     "必须是原字符串 ID")
            by_id[record_id] = record
        index[sheet] = by_id
    return index


def _context_entry(index: dict, sheet: str, record_id: str | None, label: str) -> dict:
    """按 ID 精确关联主数据上下文（含 source 与 cells），不从自然语言文案解析。"""
    if record_id is None or record_id not in index[sheet]:
        return {"label": label, "status": "not_found", "record_id": record_id}
    record = index[sheet][record_id]
    return {
        "label": label,
        "status": "found",
        "record_id": record_id,
        "data": record["data"],
        "source": record["source"],
        "cells": record["cells"],
    }


def _require_text(value, path: str, label: str) -> None:
    if not isinstance(value, str) or value == "":
        raise FactPacketBlocked(f"展示所需字段 {path} 不可用：{label} 必须是非空字符串，实际 {value!r}")


def _require_key(mapping, key: str, path: str) -> None:
    if not isinstance(mapping, dict) or key not in mapping:
        raise FactPacketBlocked(f"展示所需字段 {path} 不可用：缺少 {key}")


def _require_object(index: dict, sheet: str, record_id, path: str, label: str) -> dict:
    if not isinstance(record_id, str) or record_id == "":
        raise FactPacketBlocked(f"展示所需字段 {path} 不可用：{label} 必须是非空字符串，实际 {record_id!r}")
    if record_id not in index[sheet]:
        raise FactPacketBlocked(f"展示所需对象 {path} 不可用：{label} {record_id} 未在标准化记录中找到")
    return index[sheet][record_id]


def _check_source(record: dict, path: str, used_cells: tuple) -> None:
    source = record.get("source")
    cells = record.get("cells")
    if (not isinstance(source, dict) or not isinstance(source.get("sheet"), str)
            or not _is_int(source.get("excel_row"))):
        raise FactPacketBlocked(f"展示所需字段 {path}.source 不可用：必须含工作表名与原 Excel 行号")
    if not isinstance(cells, dict):
        raise FactPacketBlocked(f"展示所需字段 {path}.cells 不可用：必须是对象")
    for field in used_cells:
        cell = cells.get(field)
        if (not isinstance(cell, dict) or not isinstance(cell.get("cell"), str)
                or not _is_int(cell.get("column_index"))):
            raise FactPacketBlocked(
                f"展示所需来源定位 {path}.cells.{field} 不可用：必须含单元格坐标与原列号"
            )


def _check_consumed_fields(index: dict, findings: list) -> None:
    """核对本展示层实际消费的字段与必需关联对象；缺失即阻断，不静默显示空白或跳过线索。"""
    for position, finding in enumerate(findings):
        path = f"screening_report.findings[{position}]"
        rule_id = finding["rule_id"]
        related = finding["related_ids"]
        _require_key(related, "payable_id", f"{path}.related_ids")
        payable_id = related["payable_id"]
        payable = None
        if payable_id is None:
            _require(rule_id == "R03", f"{path}.related_ids.payable_id",
                     "只有 R03 允许空的应付关联（未填写关联）")
            _require(related.get("missing_kind_code") == "EMPTY_AP_ID",
                     f"{path}.related_ids.missing_kind_code", "空应付关联必须标明“未填写关联”")
        elif not isinstance(payable_id, str) or payable_id == "":
            raise FactPacketBlocked(
                f"展示所需字段 {path}.related_ids.payable_id 不可用：必须是非空字符串或 null"
            )
        elif payable_id not in index["payables"]:
            _require(rule_id == "R03", f"{path}.related_ids.payable_id",
                     "只有 R03 允许所填应付标识不在所提供台账")
            _require(related.get("missing_kind_code") == "AP_NOT_IN_LEDGER",
                     f"{path}.related_ids.missing_kind_code", "台账外标识必须标明“不在提供的台账”")
        else:
            payable = index["payables"][payable_id]
        if rule_id == "R03":
            _require(related.get("missing_kind_code") in MISSING_KIND_LABEL,
                     f"{path}.related_ids.missing_kind_code", "R03 必须给出缺失种类")
        if payable is not None:
            for field in DISPLAY_PAYABLE_FIELDS:
                _require_key(payable["data"], field, f"{path}.context.payable.data")
            _require_text(payable["data"]["ap_number"], f"{path}.context.payable.data.ap_number", "应付单据编号")
            _require_text(payable["data"]["ap_date"], f"{path}.context.payable.data.ap_date", "应付日期")
            _require(_is_int(payable["data"]["payable_amount_cents"]),
                     f"{path}.context.payable.data.payable_amount_cents", "应付金额必须是整数分（非 bool）")
            _check_source(payable, f"{path}.context.payable", ("payable_amount",))
            supplier = _require_object(index, "suppliers", payable["data"].get("supplier_id"),
                                       f"{path}.context.payable_supplier", "应付单供应商")
            _require_text(supplier["data"].get("supplier_name"), f"{path}.context.payable_supplier.data.supplier_name",
                          "应付单供应商名称")
            _check_source(supplier, f"{path}.context.payable_supplier", ("supplier_name",))
        for payment_id in related.get("payment_ids", []):
            payment = _require_object(index, "payments", payment_id, f"{path}.context.payments", "已引用的原付款主表")
            for field in DISPLAY_PAYMENT_FIELDS:
                _require_key(payment["data"], field, f"{path}.context.payments[{payment_id}].data")
            _require_text(payment["data"]["payment_date"],
                          f"{path}.context.payments[{payment_id}].data.payment_date", "原付款日期")
            _require_text(payment["data"]["settlement_status"],
                          f"{path}.context.payments[{payment_id}].data.settlement_status", "原付款结算状态")
            if payment["data"]["settlement_status"] == "SETTLED":
                _require_text(payment["data"]["bank_reference"],
                              f"{path}.context.payments[{payment_id}].data.bank_reference", "已结算银行流水标识")
            elif payment["data"]["bank_reference"] is not None and not isinstance(
                    payment["data"]["bank_reference"], str):
                raise FactPacketBlocked(
                    f"展示所需字段 {path}.context.payments[{payment_id}].data.bank_reference 不可用："
                    "必须是字符串或 null"
                )
            _require(_is_int(payment["data"]["amount_cents"]),
                     f"{path}.context.payments[{payment_id}].data.amount_cents", "整笔付款金额必须是整数分（非 bool）")
            _check_source(payment, f"{path}.context.payments[{payment_id}]", ("payment_date",))
            payee = _require_object(index, "suppliers", payment["data"]["payee_supplier_id"],
                                    f"{path}.context.payments[{payment_id}].payee_supplier", "实际收款对象")
            _require_text(payee["data"].get("supplier_name"),
                          f"{path}.context.payments[{payment_id}].payee_supplier.data.supplier_name",
                          "实际收款对象名称")
            _check_source(payee, f"{path}.context.payments[{payment_id}].payee_supplier", ("supplier_name",))
        for allocation_id in related.get("allocation_ids", []):
            allocation = _require_object(index, "allocations", allocation_id,
                                         f"{path}.context.allocations", "已引用的原付款分摊")
            for field in DISPLAY_ALLOCATION_FIELDS:
                _require_key(allocation["data"], field, f"{path}.context.allocations[{allocation_id}].data")
            _require(_is_int(allocation["data"]["allocated_amount_cents"]),
                     f"{path}.context.allocations[{allocation_id}].data.allocated_amount_cents",
                     "分摊金额必须是整数分（非 bool）")
            _require_object(index, "payments", allocation["data"].get("payment_id"),
                            f"{path}.context.allocations[{allocation_id}]", "分摊对应的原付款主表")
            _check_source(allocation, f"{path}.context.allocations[{allocation_id}]", ("allocated_amount",))
        for refund_position, refund in enumerate(finding["evidence"].get("related_refunds", [])):
            refund_path = f"{path}.evidence.related_refunds[{refund_position}]"
            for field in DISPLAY_REFUND_FIELDS:
                _require_key(refund, field, refund_path)
            for field in ("refund_allocation_id", "refund_payment_id", "original_payment_id",
                          "original_allocation_id", "settlement_status", "payment_date"):
                _require_text(refund[field], f"{refund_path}.{field}", "退款关联字段")
            _require(_is_int(refund["allocated_amount_cents"]),
                     f"{refund_path}.allocated_amount_cents", "退款金额必须是整数分（非 bool）")
            _require(isinstance(refund["counted_in_net"], bool), f"{refund_path}.counted_in_net",
                     "计入净额标志必须是布尔值")
            refund_payment = _require_object(index, "payments", refund["refund_payment_id"], refund_path, "退款主表")
            _require(refund_payment["data"].get("transaction_type") == "REFUND", f"{refund_path}.refund_payment_id",
                     "退款主表的 transaction_type 必须是 REFUND")
            _require_object(index, "allocations", refund["refund_allocation_id"], refund_path, "退款分摊")
            _require_object(index, "payments", refund["original_payment_id"], refund_path, "退款引用的原付款主表")
            _require_object(index, "allocations", refund["original_allocation_id"], refund_path,
                            "退款引用的原分摊")


def _build_context(index: dict, finding: dict) -> dict:
    related = finding["related_ids"]
    payable_id = related.get("payable_id")
    context: dict = {
        "payable": _context_entry(index, "payables", payable_id, "相关应付单"),
        "payments": [],
        "allocations": [
            _context_entry(index, "allocations", allocation_id, "相关原付款分摊")
            for allocation_id in related.get("allocation_ids", [])
        ],
        "refunds": [
            {
                "refund": _context_entry(index, "payments", refund.get("refund_payment_id"), "相关退款主表"),
                "refund_allocation": _context_entry(index, "allocations", refund.get("refund_allocation_id"),
                                                    "相关退款分摊"),
            }
            for refund in finding["evidence"].get("related_refunds", [])
        ],
    }
    # 逐付款按其自己的 payee_supplier_id 关联收款对象，不用第一笔代表整组
    for payment_id in related.get("payment_ids", []):
        entry = _context_entry(index, "payments", payment_id, "相关原付款主表")
        if entry["status"] == "found":
            entry["payee_supplier"] = _context_entry(index, "suppliers",
                                                     entry["data"].get("payee_supplier_id"), "实际收款对象")
        context["payments"].append(entry)
    if context["payable"]["status"] == "not_found":
        missing_kind_code = related.get("missing_kind_code")
        if missing_kind_code or payable_id is None:
            context["payable"]["missing_kind_code"] = missing_kind_code
            context["payable"]["missing_kind"] = MISSING_KIND_LABEL.get(
                missing_kind_code, "台账中未找到该应付标识"
            )
    if context["payable"]["status"] == "found":
        context["payable_supplier"] = _context_entry(index, "suppliers",
                                                     context["payable"]["data"].get("supplier_id"),
                                                     "应付单供应商")
    return context


def _build_finding(index: dict, finding: dict, sequence: int) -> dict:
    rule_id = finding["rule_id"]
    amounts = finding["amounts_cents"]
    related = finding["related_ids"]
    card = {
        "finding_id": f"{rule_id}-{sequence:04d}",
        "rule_id": rule_id,
        "rule_name": RULE_NAMES[rule_id],
        "rule_template": RULE_TEMPLATES[rule_id],
        "hit_key": finding["hit_key"],
        "amounts_cents": amounts,
        "amounts_display_cny": {
            key: ({payment_id: money(cents) for payment_id, cents in value.items()}
                  if isinstance(value, dict) else money(value))
            for key, value in amounts.items()
        },
        "related_ids": related,
        "source_rows": finding["source_rows"],
        "evidence": finding["evidence"],
        "context": _build_context(index, finding),
    }
    if rule_id == "R03":
        card["missing_kind"] = MISSING_KIND_LABEL.get(related.get("missing_kind_code"), "台账中未找到该应付标识")
    refunds = finding["evidence"].get("related_refunds", [])
    card["refund_summary"] = {
        "count": len(refunds),
        "counted_count": sum(1 for item in refunds if item["counted_in_net"]),
        "not_counted_count": sum(1 for item in refunds if not item["counted_in_net"]),
        "note": "非结算退款按关联记录展示但不抵减净额" if refunds else "本线索无相关退款",
    }
    return card


# ---------------------------------------------------------------------------
# Markdown 渲染
# ---------------------------------------------------------------------------


def _source_index_lines(card: dict) -> list[str]:
    lines: list[str] = []
    for entity in card["evidence"]["entities"]:
        lines.append(
            f"- {escape_markdown(entity['table_name'])} / {escape_markdown(entity['record_id'])}："
            f"工作表 {escape_markdown(entity['sheet'])}，原 Excel 行 {entity['excel_row']}，"
            f"工作簿哈希 {entity['workbook_sha256']}"
        )
    for refund in card["evidence"].get("related_refunds", []):
        lines.append(
            f"- 退款主表 / {escape_markdown(refund['refund_payment_id'])}，退款分摊 / "
            f"{escape_markdown(refund['refund_allocation_id'])}：日期 {escape_markdown(refund['payment_date'])}，"
            f"状态 {escape_markdown(refund['settlement_status'])}，金额 {money(refund['allocated_amount_cents'])}，"
            f"计入净额 {'是' if refund['counted_in_net'] else '否（未抵减）'}"
        )
    return lines


def amount_label(rule_id: str, key: str) -> str:
    """业务中文金额标签（JSON 保留原英文字段与整数分）。"""
    if key == "net_total":
        return NET_TOTAL_LABELS.get(rule_id, "净额合计")
    return AMOUNT_LABELS.get(key, key)


def _cell_location(entity: dict, field: str) -> str:
    cells = entity.get("cells")
    if not isinstance(cells, dict):
        return ""
    cell = cells.get(field)
    if not isinstance(cell, dict):
        return ""
    return f"{cell.get('cell')}（第 {cell.get('column_index')} 列）"


def render_markdown(packet: dict) -> str:
    """从 packet 渲染确定性中文底稿。"""
    lines: list[str] = []
    lines.append("# 采购付款异常筛查事实底稿（开发态）")
    lines.append("")
    for item in packet["banner"]:
        lines.append(f"> {escape_markdown(item)}")
    lines.append("")
    lines.append("## 1. 总览")
    lines.append("")
    entity = packet["entity"]
    lines.append(f"- 主体：{escape_markdown(entity['company'])}")
    lines.append(f"- 期间：{entity['period']['period_start']} 至 {entity['period']['period_end']}（含当日）")
    lines.append(f"- 截至日：{entity['cutoff_date']}")
    lines.append(f"- 币种：{escape_markdown(entity['currency'])}")
    lines.append(f"- 底稿版本：{packet['packet_version']}；状态：{packet['batch_status']}；"
                 f"模式：{packet['mode']}（next_step_allowed=false）")
    lines.append("")
    summary = packet["summary"]
    lines.append("### 规则命中数量")
    lines.append("")
    lines.append("| 规则 | 名称 | 线索数 |")
    lines.append("| --- | --- | --- |")
    for rule_id in RULE_IDS:
        lines.append(f"| {rule_id} | {escape_markdown(RULE_NAMES[rule_id])} | {summary['rule_counts'][rule_id]} |")
    lines.append(f"| 合计 | — | {summary['total_findings']} |")
    lines.append("")
    if summary["total_findings"] == 0:
        lines.append("本四条规则未命中；这不表示“无异常”，也不构成审计通过。")
        lines.append("")
    involved = summary["involved_payments"]
    lines.append(f"- 涉及的唯一原付款事件：{involved['count']} 笔，"
                 f"整笔已结算金额 {money(involved['settled_amount_cents'])}"
                 f"（整笔资金口径，不能当作缺失关联分摊额或损失）")
    lines.append(f"- R02 按唯一应付单汇总一次的超额合计：{money(summary['r02_overpayment_total_cents'])}")
    lines.append("")
    lines.append("## 2. 资金勾稽")
    lines.append("")
    reconciliation = packet["reconciliation"]
    lines.append("| 项目 | 整数分 | 人民币元 |")
    lines.append("| --- | --- | --- |")
    rows = [
        ("已结算付款主表总额", "settled_pay_master_total"),
        ("已结算退款主表总额", "settled_refund_master_total"),
        ("资金净额", "master_net"),
        ("已知应付关联净额", "known_payable_link_net"),
        ("缺失应付关联净额", "missing_payable_link_net"),
        ("其中：空应付关联", "empty_ap_id"),
        ("其中：台账外应付标识", "ap_id_not_in_ledger"),
    ]
    for label, key in rows:
        cents = reconciliation[key]
        lines.append(f"| {escape_markdown(label)} | {cents} | {money(cents)} |")
    lines.append("")
    lines.append("资金主表口径与分摊口径分别列示，不相加。")
    lines.append("整笔付款金额为主表整笔口径，不能替代本条分摊口径；两者数值可以相等。")
    lines.append("")
    lines.append(f"## 3. 逐条事实（{len(packet['findings'])} 条）")
    lines.append("")
    if not packet["findings"]:
        lines.append("本四条规则未命中；总览与资金勾稽仍按上述口径列示。")
        lines.append("")
    for card in packet["findings"]:
        lines.append(f"### {card['finding_id']} · {card['rule_id']} {escape_markdown(card['rule_name'])}")
        lines.append("")
        lines.append(f"- 命中键：`{escape_markdown(canonical_json(card['hit_key']))}`")
        lines.append(f"- 规则口径：{escape_markdown(card['rule_template'])}")
        hit_key = card["hit_key"]
        context = card["context"]
        payable = context["payable"]
        if payable["status"] == "found":
            data = payable["data"]
            supplier = context["payable_supplier"]
            supplier_text = (f"{escape_markdown(supplier['record_id'])}"
                             f"（{escape_markdown(supplier['data']['supplier_name'])}）")
            lines.append(f"- 相关应付单：{escape_markdown(data['ap_id'])}，单据编号 "
                         f"{escape_markdown(data['ap_number'])}，日期 {escape_markdown(data['ap_date'])}，"
                         f"供应商 {supplier_text}，应付金额 {money(data['payable_amount_cents'])}")
            location = _cell_location(payable, "payable_amount")
            if location:
                lines.append(f"  - 应付金额来源：{escape_markdown(location)}")
        else:
            missing = payable.get("missing_kind", "台账中未找到该应付标识")
            lines.append(f"- 相关应付单：未找到（{escape_markdown(missing)}）；"
                         f"所填标识 {escape_markdown(payable.get('record_id') or '（空）')}；"
                         f"该金额保留在总体勾稽中，不参加 R01、R02")
        for payment in context["payments"]:
            data = payment["data"]
            payee = payment["payee_supplier"]
            payee_text = (f"{escape_markdown(payee['record_id'])}"
                          f"（{escape_markdown(payee['data']['supplier_name'])}）")
            bank_reference = data["bank_reference"]
            if not isinstance(bank_reference, str) or bank_reference == "":
                bank_reference = "（空）"
            lines.append(f"- 原付款主表：{escape_markdown(data['payment_id'])}，"
                         f"日期 {escape_markdown(data['payment_date'])}，"
                         f"状态 {escape_markdown(data['settlement_status'])}，"
                         f"银行流水标识 {escape_markdown(bank_reference)}，"
                         f"实际收款对象 {payee_text}")
            lines.append(f"  - 整笔付款金额：{money(data['amount_cents'])}（整笔口径）")
            location = _cell_location(payment, "payment_date")
            if location:
                lines.append(f"  - 付款日期来源：{escape_markdown(location)}")
        for allocation in context["allocations"]:
            data = allocation["data"]
            lines.append(f"- 本条分摊：{escape_markdown(data['allocation_id'])}，"
                         f"分摊金额 {money(data['allocated_amount_cents'])}，"
                         f"应付关联 {escape_markdown(data['ap_id']) if data['ap_id'] else '（空）'}")
            location = _cell_location(allocation, "allocated_amount")
            if location:
                lines.append(f"  - 分摊金额来源：{escape_markdown(location)}")
        amounts = card["amounts_cents"]
        lines.append("- 规则金额（业务中文标签 / 原字段，整数分 = 人民币元）：")
        for key in sorted(amounts):
            label = amount_label(card["rule_id"], key)
            value = amounts[key]
            if isinstance(value, dict):
                for payment_id in sorted(value):
                    lines.append(f"  - {escape_markdown(label)}（{escape_markdown(key)} / "
                                 f"{escape_markdown(payment_id)}）：{value[payment_id]} 分 = "
                                 f"{money(value[payment_id])}")
            else:
                lines.append(f"  - {escape_markdown(label)}（{escape_markdown(key)}）：{value} 分 = "
                             f"{money(value)}")
        refunds = card["evidence"].get("related_refunds", [])
        if refunds:
            lines.append(f"- 相关退款（{card['refund_summary']['count']} 条，"
                         f"计入净额 {card['refund_summary']['counted_count']} 条）：")
            for refund in refunds:
                lines.append(f"  - 退款 {escape_markdown(refund['refund_payment_id'])} / 分摊 "
                             f"{escape_markdown(refund['refund_allocation_id'])}，关联原付款 "
                             f"{escape_markdown(refund['original_payment_id'])} / 原分摊 "
                             f"{escape_markdown(refund['original_allocation_id'])}，"
                             f"日期 {escape_markdown(refund['payment_date'])}，"
                             f"状态 {escape_markdown(refund['settlement_status'])}，"
                             f"金额 {money(refund['allocated_amount_cents'])}，"
                             f"计入净额：{'是' if refund['counted_in_net'] else '否（未抵减）'}")
        else:
            lines.append("- 相关退款：无")
        lines.append("- 来源索引：")
        lines.extend(_source_index_lines(card))
        lines.append("")
    lines.append("## 4. 来源与限制")
    lines.append("")
    bindings = packet["bindings"]
    lines.append(f"- 工作簿来源哈希：{bindings['workbook_sha256']}")
    lines.append(f"- normalized 对象指纹：{bindings['normalized_payload_sha256']}")
    lines.append(f"- 筛查对象指纹：{bindings['screening_report_sha256']}")
    lines.append(f"- 复核对象指纹：{bindings['crosscheck_report_sha256']}")
    lines.append(f"- 上游版本：标准化 {bindings['upstream_versions']['normalization']}、"
                 f"规则核心 {bindings['upstream_versions']['rule_core']}、"
                 f"复核核心 {bindings['upstream_versions']['crosscheck']}")
    database = bindings["upstream_declared_database"]
    lines.append(f"- 上游报告声明的数据库哈希：{database['database_sha256_before']}"
                 f"（before=after={database['sha256_equal']}）；展示层未读取数据库字节")
    lines.append("")
    for item in packet["limits"]:
        lines.append(f"- {escape_markdown(item)}")
    lines.append("- 完整来源单元格（cells）见同目录 fact_packet.json。")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def build_fact_packet(normalized: dict, screening_report: dict, crosscheck_report: dict) -> dict:
    """把已计算、已复核的事实整理为 JSON 证据包与确定性 Markdown 底稿。"""
    bindings = _check_inputs(normalized, screening_report, crosscheck_report)
    try:
        index = _index_records(normalized)
        findings = screening_report["findings"]
        _check_consumed_fields(index, findings)
        counters: dict[str, int] = {rule_id: 0 for rule_id in RULE_IDS}
        cards: list[dict] = []
        for finding in findings:
            rule_id = finding["rule_id"]
            counters[rule_id] += 1
            cards.append(_build_finding(index, finding, counters[rule_id]))
        statistics = screening_report["statistics"]
        involved = statistics.get("involved_payments") or {}
        reconciliation = screening_report["overall_reconciliation"]
        missing_detail = reconciliation.get("missing_payable_link_detail") or {}
        packet = {
            "packet_version": PACKET_VERSION,
            "batch_status": PACKET_STATUS,
            "mode": MODE,
            "next_step_allowed": False,
            "entity": {
                "company": COMPANY,
                "period": {"period_start": PERIOD_START, "period_end": PERIOD_END},
                "cutoff_date": CUTOFF_DATE,
                "currency": CURRENCY,
            },
            "banner": BANNER,
            "bindings": {
                "workbook_sha256": bindings["input_sha256"],
                "normalized_payload_sha256": bindings["normalized_fingerprint"],
                "screening_report_sha256": bindings["screening_fingerprint"],
                "crosscheck_report_sha256": bindings["crosscheck_fingerprint"],
                "upstream_versions": {
                    "normalization": normalized["normalization_version"],
                    "rule_core": screening_report["rule_core_version"],
                    "crosscheck": crosscheck_report["crosscheck_version"],
                    "store": screening_report["load_source"]["store_version"],
                    "schema": screening_report["load_source"]["schema_version"],
                },
                "upstream_declared_database": {
                    "database_path": screening_report.get("database_path"),
                    "database_sha256_before": screening_report.get("database_sha256_before"),
                    "database_sha256_after": screening_report.get("database_sha256_after"),
                    "sha256_equal": screening_report.get("database_sha256_before")
                    == screening_report.get("database_sha256_after"),
                    "database_unchanged": screening_report.get("database_unchanged"),
                    "note": "仅为上游报告声明的数据库哈希；展示层未读取或重验数据库字节",
                },
            },
            "summary": {
                "rule_counts": {rule_id: bindings["derived_counts"][rule_id] for rule_id in RULE_IDS},
                "total_findings": len(cards),
                "involved_payments": {
                    "count": involved.get("count"),
                    "payment_ids": involved.get("payment_ids"),
                    "settled_amount_cents": involved.get("settled_amount_cents"),
                    "note": "涉及的唯一原付款事件的整笔已结算总额；不能当作缺失关联分摊额或损失",
                },
                "r02_overpayment_total_cents": statistics.get("r02_overpayment_total_cents"),
                "r02_overpayment_basis": statistics.get("r02_overpayment_basis"),
            },
            "reconciliation": {
                "unit": "cents",
                "settled_pay_master_total": reconciliation["settled_pay_master_total"],
                "settled_refund_master_total": reconciliation["settled_refund_master_total"],
                "master_net": reconciliation["master_net"],
                "known_payable_link_net": reconciliation["known_payable_link_net"],
                "missing_payable_link_net": reconciliation["missing_payable_link_net"],
                "empty_ap_id": missing_detail.get("empty_ap_id"),
                "ap_id_not_in_ledger": missing_detail.get("ap_id_not_in_ledger"),
                "note": "资金主表口径与分摊口径分别列示，不相加",
            },
            "findings": cards,
            "amount_labels": {
                "note": "正文字段名到业务中文标签的固定映射；不改变 amounts_cents 的原字段与数值",
                "mapping": dict(AMOUNT_LABELS),
                "net_total_by_rule": dict(NET_TOTAL_LABELS),
            },
            "limits": LIMITS,
        }
        markdown = render_markdown(packet)
    except FactPacketBlocked:
        raise
    except FactPacketError:
        raise
    except Exception as exc:  # noqa: BLE001 - 统一保留阶段与异常链
        raise FactPacketError(
            f"[build] 构建事实底稿失败：{type(exc).__name__}: {exc}",
            ["阶段=build", f"原始异常={type(exc).__name__}: {exc}"],
        ) from exc
    return {"packet": packet, "packet_sha256": canonical_sha256(packet), "markdown": markdown}
