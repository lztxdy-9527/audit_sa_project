#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-007 独立复算核心：用另一套 Python 整数实现复算规则事实，并与 SQL 筛查报告逐项比对。

本模块只提供 Python API，**不写文件、不修改传入对象**：

    verify_rule_facts(normalized: dict, screening_report: dict) -> dict

只接收两个内存对象：不读取数据库、Excel、答案册或历史复核结果，不执行 SQL、不调用筛查核心、
不导入生成器或旧测试／QA 脚本；标准库仅用 json／hashlib。

复算来源是 `normalized.tables.*.records[*].data` 的原始标准化记录，**不从 `findings` 反推应有结果**，
也不使用 `normalized.amount_reconciliation` 的汇总值作为计算答案。观察事实来自 SQL 筛查报告。
两者一致只说明两种实现对该输入一致，不证明数据真实、业务合理或审计结论正确。

异常类型：
  CrossCheckBlocked  前提、结构、来源绑定或支持范围不成立；说明字段／原因，不返回成功复核。
  CrossCheckError    运行失败；保留阶段、原始原因与异常链。金额全程整数分，不转浮点、不用容差。
"""

from __future__ import annotations

import hashlib
import json

CROSSCHECK_VERSION = "TASK-007-crosscheck-1.2"
MODE = "DEVELOPMENT_TEST_ONLY"
MATCHED_STATUS = "DEV_CROSSCHECK_MATCHED"
MISMATCH_STATUS = "DEV_CROSSCHECK_MISMATCH"
EXPECTED_NORMALIZATION_VERSION = "TASK-004-normalized-1.1"
EXPECTED_RULE_CORE_VERSION = "TASK-006-rule-core-1.1"
EXPECTED_LOAD_STATUS = "DEV_SQLITE_VERIFIED"
EXPECTED_RULES_STATUS = "DEV_RULES_COMPUTED"
EXPECTED_STORE_VERSION = "TASK-005-sqlite-load-1.2"
EXPECTED_SCHEMA_VERSION = "demo-schema-1.0"
PERIOD_START = "2026-09-01"
PERIOD_END = "2026-09-30"
SUPPORTED_CUTOFF_DATE = "2026-09-30"
RULE_IDS = ("R01", "R02", "R03", "R04")
FROZEN_RULE_VERSIONS = {
    "R01": "TASK-006-R01-1.0",
    "R02": "TASK-006-R02-1.0",
    "R03": "TASK-006-R03-1.0",
    "R04": "TASK-006-R04-1.0",
}
FROZEN_SQL_SHA256 = {
    "R01": "7a19ff2faba088f0b498d9c5004f0a865aac4d59b6f8ed699869051ecbe5e882",
    "R02": "58af03e634008fcc61426e15a7433b6370cae0180c0436136de226b8d87b08b3",
    "R03": "8a4b84d9ba0ed201ea89a6d58ea5ea67deec9ab8dbe8908e246c79c76876525a",
    "R04": "b60e4db078e6632c653adb4ec20f1280c7ef58c70d4496f7caa6cb5cf567ec2d",
}
R03_MISSING_KIND_LABEL = {"EMPTY_AP_ID": "未填写关联", "AP_NOT_IN_LEDGER": "填写的标识不在台账"}
METHOD_NOTE = [
    "复算以标准化记录的 data 为输入，用字典分组与整数循环实现；不使用 SQL、不读取答案册、不解码数据库或 Excel。",
    "R01 组内金额只含满足足额条件的原付款；R02 按唯一应付单汇总一次；R03／R04 逐原分摊一条，不以净额大于 0 过滤。",
    "退款按 original_allocation_id 汇总后抵减；非结算退款展示但不抵减；主表与分摊两种口径分别计算，不相加。",
    "所有声明为整数分的字段按严格类型比较（int 且非 bool）：等值 float／bool 均判为不一致，不转换、不舍入。",
    "比较分维度记录 executed／matched／difference_count；matched 仅在全部维度一致且差异为空时为 true。",
    "命中键的 ID 字段属于事实身份：字符串 `\"1\"` 与整数 `1`（以及 `\"True\"`／`True`、`\"None\"`／`None`）"
    "是不同身份，不做 str() 归一化；类型错误报 HIT_KEY_TYPE_MISMATCH 并保留原值、类型与字段路径。",
]
LIMITS = [
    "两种实现一致只证明对该输入的计算一致，不证明数据真实、业务合理，也不构成审计结论。",
    "本模块只比较报告内部声明与绑定，不实际读取或重验数据库字节；数据库实读由上游加载器与规则核心负责。",
    "复核不一致是有意义的复核结果，不是自动修复指令；差异保留，不回写或修复任何报告与数据库。",
    "不生成 AI 候选结论、严重等级或人类判断预填值。",
]


class CrossCheckBlocked(Exception):
    """前提、结构、来源绑定或支持范围不成立。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


class CrossCheckError(Exception):
    """运行失败；保留阶段、原始原因与异常链。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def canonical_json_sha256(payload) -> str:
    """按固定 JSON 规范序列化后求 SHA-256（对象指纹，不是文件字节哈希）。"""
    try:
        text = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise CrossCheckBlocked(f"对象无法按规范 JSON 序列化：{type(exc).__name__}: {exc}") from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _require(condition: bool, path: str, reason: str) -> None:
    if not condition:
        raise CrossCheckBlocked(f"输入字段 {path} 不可用：{reason}")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _key_tuple(hit_key: dict) -> tuple:
    """身份键：字段名 + 值类型 + repr(值)。

    不做 `str(value)` 归一化：字符串 `"1"` 与整数 `1`（以及 `"True"`／`True`、`"None"`／`None`）
    是**不同身份**，因此命中键中的类型错误不会被抹平成同一键。
    """
    return tuple(sorted((str(key), _type_name(value), repr(value)) for key, value in hit_key.items()))


def _key_render(hit_key: dict) -> tuple:
    """仅用于差异诊断配对（把渲染相同的键配起来说明类型不同），不承担身份归一化。"""
    return tuple(sorted((str(key), str(value)) for key, value in hit_key.items()))


HIT_KEY_FIELDS = {
    "R01": ("rule_id", "ap_id", "payee_supplier_id"),
    "R02": ("rule_id", "ap_id"),
    "R03": ("rule_id", "allocation_id"),
    "R04": ("rule_id", "allocation_id"),
}


def _in_period(date_text: str) -> bool:
    return isinstance(date_text, str) and PERIOD_START <= date_text <= PERIOD_END


# ---------------------------------------------------------------------------
# 输入前提
# ---------------------------------------------------------------------------


def _check_inputs(normalized, screening_report) -> dict:
    _require(isinstance(normalized, dict), "normalized", f"必须是对象，实际 {type(normalized).__name__}")
    _require(isinstance(screening_report, dict), "screening_report",
             f"必须是对象，实际 {type(screening_report).__name__}")

    _require(normalized.get("normalization_version") == EXPECTED_NORMALIZATION_VERSION,
             "normalized.normalization_version",
             f"必须是 {EXPECTED_NORMALIZATION_VERSION}，实际 {normalized.get('normalization_version')!r}")
    _require(normalized.get("mode") == MODE, "normalized.mode", f"必须是 {MODE}")
    _require(normalized.get("next_step_allowed") is False, "normalized.next_step_allowed", "必须是 false")

    quality = normalized.get("quality_report")
    _require(isinstance(quality, dict), "normalized.quality_report", "必须是对象")
    _require(quality.get("result") == "pass", "normalized.quality_report.result",
             f"必须是 pass，实际 {quality.get('result')!r}")
    issue_counts = quality.get("issue_counts_by_code")
    _require(isinstance(issue_counts, dict), "normalized.quality_report.issue_counts_by_code",
             f"必须存在且为对象，实际 {type(issue_counts).__name__}")
    _require(not issue_counts, "normalized.quality_report.issue_counts_by_code",
             f"质量通过必须无未解决问题，实际 {issue_counts!r}")

    source = normalized.get("source")
    _require(isinstance(source, dict), "normalized.source", "必须是对象")
    input_sha = source.get("input_sha256")
    _require(isinstance(input_sha, str) and len(input_sha) == 64, "normalized.source.input_sha256",
             "必须是 64 位哈希")

    _require(screening_report.get("batch_status") == EXPECTED_RULES_STATUS, "screening_report.batch_status",
             f"必须是 {EXPECTED_RULES_STATUS}，实际 {screening_report.get('batch_status')!r}")
    _require(screening_report.get("mode") == MODE, "screening_report.mode", f"必须是 {MODE}")
    _require(screening_report.get("next_step_allowed") is False, "screening_report.next_step_allowed",
             "必须是 false")
    _require(screening_report.get("rule_core_version") == EXPECTED_RULE_CORE_VERSION,
             "screening_report.rule_core_version",
             f"必须是 {EXPECTED_RULE_CORE_VERSION}，实际 {screening_report.get('rule_core_version')!r}")
    _require(screening_report.get("cutoff_date") == SUPPORTED_CUTOFF_DATE, "screening_report.cutoff_date",
             f"本版只支持 {SUPPORTED_CUTOFF_DATE}，实际 {screening_report.get('cutoff_date')!r}")
    period = screening_report.get("period")
    _require(isinstance(period, dict) and period.get("period_start") == PERIOD_START
             and period.get("period_end") == PERIOD_END, "screening_report.period",
             f"必须是 {PERIOD_START}—{PERIOD_END}")

    load_source = screening_report.get("load_source")
    _require(isinstance(load_source, dict), "screening_report.load_source", "必须是对象")
    _require(load_source.get("batch_status") == EXPECTED_LOAD_STATUS, "screening_report.load_source.batch_status",
             f"必须是 {EXPECTED_LOAD_STATUS}")
    _require(load_source.get("store_version") == EXPECTED_STORE_VERSION,
             "screening_report.load_source.store_version", f"必须是 {EXPECTED_STORE_VERSION}")
    _require(load_source.get("schema_version") == EXPECTED_SCHEMA_VERSION,
             "screening_report.load_source.schema_version", f"必须是 {EXPECTED_SCHEMA_VERSION}")
    _require(load_source.get("input_sha256") == input_sha, "screening_report.load_source.input_sha256",
             f"必须与 normalized.source.input_sha256 相等：{load_source.get('input_sha256')} != {input_sha}")
    run_metadata = load_source.get("run_metadata")
    _require(isinstance(run_metadata, dict), "screening_report.load_source.run_metadata", "必须是对象")
    _require(run_metadata.get("input_sha256") == input_sha, "load_source.run_metadata.input_sha256",
             "必须与 normalized 来源哈希相等")
    _require(run_metadata.get("mode") == MODE and run_metadata.get("next_step_allowed") == "false",
             "load_source.run_metadata", "开发态标识不符")

    fingerprint = canonical_json_sha256(normalized)
    for path, actual in (
        ("screening_report.load_source.normalized_payload_sha256", load_source.get("normalized_payload_sha256")),
        ("load_source.run_metadata.normalized_payload_sha256", run_metadata.get("normalized_payload_sha256")),
    ):
        _require(actual == fingerprint, path,
                 f"必须等于本次对象指纹：{actual} != {fingerprint}")

    before = screening_report.get("database_sha256_before")
    after = screening_report.get("database_sha256_after")
    _require(before == after == load_source.get("database_sha256"), "screening_report.database_sha256",
             f"before／after／load_source 必须相等：{before} / {after} / {load_source.get('database_sha256')}")
    _require(screening_report.get("database_unchanged") is True, "screening_report.database_unchanged",
             "必须是 true")
    read_only = screening_report.get("read_only")
    _require(isinstance(read_only, dict) and read_only.get("uri_mode") == "ro"
             and read_only.get("query_only") == 1, "screening_report.read_only",
             f"必须是 {{'uri_mode': 'ro', 'query_only': 1}}，实际 {read_only!r}")

    rules = screening_report.get("rules")
    _require(isinstance(rules, dict), "screening_report.rules", "必须是对象")
    for rule_id in RULE_IDS:
        entry = rules.get(rule_id)
        _require(isinstance(entry, dict), f"screening_report.rules.{rule_id}", "必须是对象")
        _require(entry.get("rule_version") == FROZEN_RULE_VERSIONS[rule_id],
                 f"screening_report.rules.{rule_id}.rule_version",
                 f"必须是冻结版本 {FROZEN_RULE_VERSIONS[rule_id]}，实际 {entry.get('rule_version')!r}")
        _require(entry.get("sql_sha256") == FROZEN_SQL_SHA256[rule_id],
                 f"screening_report.rules.{rule_id}.sql_sha256",
                 f"必须是冻结 SQL 哈希 {FROZEN_SQL_SHA256[rule_id]}，实际 {entry.get('sql_sha256')!r}")

    findings = screening_report.get("findings")
    _require(isinstance(findings, list), "screening_report.findings", "必须是列表")
    for index, finding in enumerate(findings):
        path = f"screening_report.findings[{index}]"
        _require(isinstance(finding, dict), path, "必须是对象")
        for part in ("hit_key", "amounts_cents", "related_ids", "source_rows", "evidence"):
            _require(isinstance(finding.get(part), dict), f"{path}.{part}", "必须是对象")
    for field in ("rule_hit_counts", "statistics", "overall_reconciliation"):
        _require(isinstance(screening_report.get(field), dict), f"screening_report.{field}", "必须是对象")
    return {"input_sha256": input_sha, "normalized_payload_sha256": fingerprint,
            "screening_report_sha256": canonical_json_sha256(screening_report)}


def _check_normalized_records(normalized) -> dict:
    tables = normalized.get("tables")
    _require(isinstance(tables, dict), "normalized.tables", "必须是对象")
    index: dict[str, dict] = {}
    for sheet in ("suppliers", "payables", "payments", "allocations"):
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
            key_field = {"suppliers": "supplier_id", "payables": "ap_id", "payments": "payment_id",
                         "allocations": "allocation_id"}[sheet]
            record_id = data.get(key_field)
            _require(isinstance(record_id, str) and record_id != "", f"{path}.data.{key_field}",
                     f"必须是原字符串，实际 {record_id!r}")
            _require(record_id not in by_id, f"{path}.data.{key_field}", f"主键重复：{record_id}")
            by_id[record_id] = record
        index[sheet] = by_id

    for record in index["payables"].values():
        data = record["data"]
        _require(_is_int(data.get("payable_amount_cents")) and not isinstance(data.get("payable_amount_cents"), bool),
                 "normalized.payables.payable_amount_cents", "必须是整数分（非 bool）")
        _require(_in_period(data.get("ap_date")), "normalized.payables.ap_date",
                 f"必须在 {PERIOD_START}—{PERIOD_END} 内：{data.get('ap_date')!r}")
    for record in index["payments"].values():
        data = record["data"]
        for field in ("amount_cents",):
            _require(_is_int(data.get(field)) and not isinstance(data.get(field), bool),
                     f"normalized.payments.{field}", "必须是整数分（非 bool）")
        _require(_in_period(data.get("payment_date")), "normalized.payments.payment_date",
                 f"必须在 {PERIOD_START}—{PERIOD_END} 内：{data.get('payment_date')!r}")
        _require(data.get("transaction_type") in ("PAY", "REFUND"), "normalized.payments.transaction_type",
                 f"必须是 PAY／REFUND，实际 {data.get('transaction_type')!r}")
        _require(data.get("settlement_status") in ("SETTLED", "PENDING", "FAILED", "VOIDED"),
                 "normalized.payments.settlement_status", "枚举超出本版范围")
    for record in index["allocations"].values():
        data = record["data"]
        _require(_is_int(data.get("allocated_amount_cents")) and not isinstance(data.get("allocated_amount_cents"), bool),
                 "normalized.allocations.allocated_amount_cents", "必须是整数分（非 bool）")
        _require(data.get("payment_id") in index["payments"], "normalized.allocations.payment_id",
                 f"资金事件不存在：{data.get('payment_id')!r}")
    return index


# ---------------------------------------------------------------------------
# 独立复算（纯 Python 整数循环）
# ---------------------------------------------------------------------------


def _refund_index(index: dict) -> tuple[dict, dict]:
    """按 original_allocation_id 汇总已结算退款；同时给出每个退款分摊的摘要。"""
    refunded: dict[str, int] = {}
    refund_facts: dict[str, list[dict]] = {}
    for record in index["allocations"].values():
        data = record["data"]
        original = data.get("original_allocation_id")
        if not original:
            continue
        payment = index["payments"][data["payment_id"]]["data"]
        if payment["transaction_type"] != "REFUND":
            continue
        counted = payment["settlement_status"] == "SETTLED" and _in_period(payment["payment_date"])
        fact = {
            "refund_allocation_id": data["allocation_id"],
            "refund_payment_id": payment["payment_id"],
            "original_allocation_id": original,
            "allocated_amount_cents": data["allocated_amount_cents"],
            "settlement_status": payment["settlement_status"],
            "original_payment_id": payment.get("original_payment_id"),
            "payment_date": payment["payment_date"],
            "counted_in_net": counted,
        }
        refund_facts.setdefault(original, []).append(fact)
        if counted:
            refunded[original] = refunded.get(original, 0) + data["allocated_amount_cents"]
    for facts in refund_facts.values():
        facts.sort(key=lambda item: (item["refund_payment_id"], item["refund_allocation_id"]))
    return refunded, refund_facts


def _base_records(index: dict, refunded: dict) -> list[dict]:
    """每条截至日已结算 PAY 分摊：分摊额、已退回额、净额与其主表信息。"""
    base: list[dict] = []
    for record in index["allocations"].values():
        data = record["data"]
        payment = index["payments"][data["payment_id"]]["data"]
        if payment["transaction_type"] != "PAY" or payment["settlement_status"] != "SETTLED":
            continue
        if not _in_period(payment["payment_date"]):
            continue
        refunded_cents = refunded.get(data["allocation_id"], 0)
        base.append(
            {
                "allocation_id": data["allocation_id"],
                "payment_id": payment["payment_id"],
                "ap_id": data.get("ap_id"),
                "allocated_amount_cents": data["allocated_amount_cents"],
                "refunded_cents": refunded_cents,
                "net_cents": data["allocated_amount_cents"] - refunded_cents,
                "payee_supplier_id": payment.get("payee_supplier_id"),
                "payment_amount_cents": payment["amount_cents"],
            }
        )
    base.sort(key=lambda item: item["allocation_id"])
    return base


def _entities_for(index: dict, workbook: str, payable_ids: list[str], payment_ids: list[str],
                  allocation_ids: list[str], refund_facts: dict) -> tuple[dict, list[dict], dict]:
    """从 normalized 记录推导必需来源实体与来源行号（不以 SQL 输出的 entities 为应有集合）。"""
    refund_allocation_ids = sorted(
        {fact["refund_allocation_id"] for allocation_id in allocation_ids
         for fact in refund_facts.get(allocation_id, [])}
    )
    refund_payment_ids = sorted(
        {fact["refund_payment_id"] for allocation_id in allocation_ids
         for fact in refund_facts.get(allocation_id, [])}
    )
    entities: list[dict] = []
    source_rows: dict[str, dict] = {"payables": {}, "payments": {}, "allocations": {}}
    for sheet, ids in (
        ("payables", sorted(set(payable_ids))),
        ("payments", sorted(set(payment_ids) | set(refund_payment_ids))),
        ("allocations", sorted(set(allocation_ids) | set(refund_allocation_ids))),
    ):
        for record_id in ids:
            record = index[sheet].get(record_id)
            if record is None:
                continue
            entities.append(
                {
                    "table_name": sheet,
                    "record_id": record_id,
                    "workbook_sha256": workbook,
                    "sheet": record["source"].get("sheet"),
                    "excel_row": record["source"].get("excel_row"),
                    "cells": record["cells"],
                }
            )
            source_rows[sheet][record_id] = record["source"].get("excel_row")
    return source_rows, entities, {"refund_allocation_ids": refund_allocation_ids,
                                   "refund_payment_ids": refund_payment_ids}


def recompute_facts(normalized: dict, index: dict) -> dict:
    """从标准化记录独立复算四规则事实与总体勾稽。"""
    workbook = normalized.get("source", {}).get("input_sha256", "")
    refunded, refund_facts = _refund_index(index)
    base = _base_records(index, refunded)
    payables = index["payables"]

    findings: list[dict] = []
    # R01
    groups: dict[tuple, dict] = {}
    for item in base:
        ap_id = item["ap_id"]
        if ap_id not in payables:
            continue
        payable = payables[ap_id]["data"]
        key = (ap_id, item["payee_supplier_id"])
        entry = groups.setdefault(key, {"payable_amount": payable["payable_amount_cents"], "payments": {}})
        entry["payments"][item["payment_id"]] = entry["payments"].get(item["payment_id"], 0) + item["net_cents"]
    for (ap_id, payee), entry in groups.items():
        qualifying = {pid: cents for pid, cents in entry["payments"].items() if cents == entry["payable_amount"]}
        if len(qualifying) < 2:
            continue
        allocation_ids = sorted(
            item["allocation_id"] for item in base
            if item["ap_id"] == ap_id and item["payee_supplier_id"] == payee
            and item["payment_id"] in qualifying
        )
        source_rows, entities, refund_ids = _entities_for(index, workbook, [ap_id], sorted(qualifying), allocation_ids,
                                                          refund_facts)
        findings.append(
            {
                "rule_id": "R01",
                "hit_key": {"rule_id": "R01", "ap_id": ap_id, "payee_supplier_id": payee},
                "amounts_cents": {
                    "payable_amount": entry["payable_amount"],
                    "net_per_payment": {pid: qualifying[pid] for pid in sorted(qualifying)},
                    "net_total": sum(qualifying.values()),
                },
                "related_ids": {
                    "payable_id": ap_id,
                    "payment_ids": sorted(qualifying),
                    "allocation_ids": allocation_ids,
                    "refund_ids": refund_ids["refund_payment_ids"],
                },
                "source_rows": source_rows,
                "entities": entities,
                "refunds": [fact for allocation_id in allocation_ids
                            for fact in refund_facts.get(allocation_id, [])],
                "counts": {"qualifier_payment_count": len(qualifying)},
            }
        )
    # R02
    per_payable: dict[str, dict] = {}
    for item in base:
        if item["ap_id"] not in payables:
            continue
        entry = per_payable.setdefault(item["ap_id"], {"paid": 0, "refund": 0, "net": 0})
        entry["paid"] += item["allocated_amount_cents"]
        entry["refund"] += item["refunded_cents"]
        entry["net"] += item["net_cents"]
    for ap_id, entry in per_payable.items():
        payable = payables[ap_id]["data"]
        if entry["net"] <= payable["payable_amount_cents"]:
            continue
        allocation_ids = sorted(item["allocation_id"] for item in base if item["ap_id"] == ap_id)
        payment_ids = sorted({item["payment_id"] for item in base if item["ap_id"] == ap_id})
        source_rows, entities, refund_ids = _entities_for(index, workbook, [ap_id], payment_ids, allocation_ids, refund_facts)
        findings.append(
            {
                "rule_id": "R02",
                "hit_key": {"rule_id": "R02", "ap_id": ap_id},
                "amounts_cents": {
                    "payable_amount": payable["payable_amount_cents"],
                    "paid_total": entry["paid"],
                    "refund_total": entry["refund"],
                    "net_total": entry["net"],
                    "overpayment": entry["net"] - payable["payable_amount_cents"],
                },
                "related_ids": {
                    "payable_id": ap_id,
                    "payment_ids": payment_ids,
                    "allocation_ids": allocation_ids,
                    "refund_ids": refund_ids["refund_payment_ids"],
                },
                "source_rows": source_rows,
                "entities": entities,
                "refunds": [fact for allocation_id in allocation_ids for fact in refund_facts.get(allocation_id, [])],
            }
        )
    # R03 / R04
    for item in base:
        ap_id = item["ap_id"]
        known = ap_id in payables
        if not known:
            missing_kind = "AP_NOT_IN_LEDGER" if ap_id else "EMPTY_AP_ID"
            payable_ids: list[str] = []
        else:
            payable = payables[ap_id]["data"]
            if item["payee_supplier_id"] == payable["supplier_id"]:
                continue
            missing_kind = None
            payable_ids = [ap_id]
        rule_id = "R03" if not known else "R04"
        source_rows, entities, refund_ids = _entities_for(index, workbook, payable_ids, [item["payment_id"]],
                                                          [item["allocation_id"]], refund_facts)
        amounts = {
            "allocated_amount": item["allocated_amount_cents"],
            "paid_amount": item["allocated_amount_cents"],
            "refunded_amount": item["refunded_cents"],
            "net_amount": item["net_cents"],
        }
        related = {
            "payable_id": item["ap_id"] if known else (item["ap_id"] or None),
            "payment_ids": [item["payment_id"]],
            "allocation_ids": [item["allocation_id"]],
            "refund_ids": refund_ids["refund_payment_ids"],
        }
        if not known:
            related["missing_kind_code"] = missing_kind
            related["missing_kind"] = R03_MISSING_KIND_LABEL[missing_kind]
        else:
            related["payable_supplier_id"] = payable["supplier_id"]
            related["payee_supplier_id"] = item["payee_supplier_id"]
            amounts["payable_amount"] = payable["payable_amount_cents"]
        findings.append(
            {
                "rule_id": rule_id,
                "hit_key": {"rule_id": rule_id, "allocation_id": item["allocation_id"]},
                "amounts_cents": amounts,
                "related_ids": related,
                "source_rows": source_rows,
                "entities": entities,
                "refunds": refund_facts.get(item["allocation_id"], []),
            }
        )

    findings.sort(key=lambda item: (item["rule_id"], canonical_json(item["hit_key"])))

    # 两种口径的资金勾稽（主表按整笔、分摊按明细）
    settled_pay_master = 0
    settled_refund_master = 0
    for record in index["payments"].values():
        data = record["data"]
        if data["settlement_status"] != "SETTLED" or not _in_period(data["payment_date"]):
            continue
        if data["transaction_type"] == "PAY":
            settled_pay_master += data["amount_cents"]
        else:
            settled_refund_master += data["amount_cents"]
    pay_allocation_total = sum(item["allocated_amount_cents"] for item in base)
    refund_allocation_total = sum(
        fact["allocated_amount_cents"] for facts in refund_facts.values() for fact in facts if fact["counted_in_net"]
    )
    empty_net = sum(item["net_cents"] for item in base if not item["ap_id"])
    unknown_net = sum(item["net_cents"] for item in base if item["ap_id"] and item["ap_id"] not in payables)
    known_net = sum(item["net_cents"] for item in base if item["ap_id"] in payables)
    master_net = settled_pay_master - settled_refund_master
    involved_payment_ids = sorted({pid for finding in findings for pid in finding["related_ids"]["payment_ids"]})
    involved_settled = sum(
        index["payments"][pid]["data"]["amount_cents"]
        for pid in involved_payment_ids
        if index["payments"][pid]["data"]["transaction_type"] == "PAY"
        and index["payments"][pid]["data"]["settlement_status"] == "SETTLED"
    )
    reconciliation = {
        "settled_pay_master_total": settled_pay_master,
        "settled_refund_master_total": settled_refund_master,
        "pay_allocation_total": pay_allocation_total,
        "refund_allocation_total": refund_allocation_total,
        "master_net": master_net,
        "known_payable_link_net": known_net,
        "missing_payable_link_net": empty_net + unknown_net,
        "missing_payable_link_detail": {"empty_ap_id": empty_net, "ap_id_not_in_ledger": unknown_net},
        "master_pay_equals_allocation": settled_pay_master == pay_allocation_total,
        "master_refund_equals_allocation": settled_refund_master == refund_allocation_total,
        "master_net_equals_known_plus_missing": master_net == known_net + empty_net + unknown_net,
    }
    statistics = {
        "involved_payment_ids": involved_payment_ids,
        "involved_payment_count": len(involved_payment_ids),
        "involved_payment_settled_amount_cents": involved_settled,
        "r02_overpayment_total_cents": sum(
            finding["amounts_cents"]["overpayment"] for finding in findings if finding["rule_id"] == "R02"
        ),
    }
    counts = {rule_id: sum(1 for finding in findings if finding["rule_id"] == rule_id) for rule_id in RULE_IDS}
    counts["total"] = len(findings)
    return {"findings": findings, "counts": counts, "reconciliation": reconciliation, "statistics": statistics}


# ---------------------------------------------------------------------------
# 逐项比较
# ---------------------------------------------------------------------------


def _type_name(value) -> str:
    if value is None:
        return "null"
    return type(value).__name__


def _typed_equal(expected, actual) -> bool:
    """严格类型比较：类型不同即不同；不做数值等价、不用 str() 抹平类型差异。"""
    return type(expected) is type(actual) and expected == actual


def _sort_key(value):
    return (_type_name(value), str(value))


def _list_equal(expected: list, actual) -> bool:
    if not isinstance(actual, list) or len(actual) != len(expected):
        return False
    return all(
        _typed_equal(left, right)
        for left, right in zip(sorted(expected, key=_sort_key), sorted(actual, key=_sort_key))
    )


DIMENSIONS = (
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
REFUND_REQUIRED_KEYS = (
    "refund_allocation_id",
    "refund_payment_id",
    "original_allocation_id",
    "allocated_amount_cents",
    "settlement_status",
    "original_payment_id",
    "payment_date",
    "counted_in_net",
)


class _Tracker:
    """记录差异并维护各比较维度的一致状态（executed／matched／difference_count）。"""

    def __init__(self):
        self.dimensions = {
            name: {"executed": True, "matched": True, "difference_count": 0} for name in DIMENSIONS
        }
        self.differences: list[dict] = []

    def record(self, dimension: str, code: str, hit_key, field_path: str, expected, actual,
               expected_present: bool = True, actual_present: bool = True) -> None:
        self.differences.append(
            {
                "code": code,
                "hit_key": hit_key,
                "field_path": field_path,
                "expected": expected,
                "expected_present": expected_present,
                "expected_type": _type_name(expected) if expected_present else None,
                "actual": actual,
                "actual_present": actual_present,
                "actual_type": _type_name(actual) if actual_present else None,
            }
        )
        self.dimensions[dimension]["matched"] = False
        self.dimensions[dimension]["difference_count"] += 1

    def compare(self, dimension: str, code: str, hit_key, field_path: str, expected, actual,
                expected_present: bool = True, actual_present: bool = True) -> None:
        if expected_present != actual_present:
            self.record(dimension, code, hit_key, field_path, expected, actual,
                        expected_present, actual_present)
            return
        if not expected_present:
            return
        if not _typed_equal(expected, actual):
            self.record(dimension, code, hit_key, field_path, expected, actual)

    def result(self) -> dict:
        return {
            "dimensions": self.dimensions,
            "difference_count": len(self.differences),
            "matched_dimensions": sorted(name for name, item in self.dimensions.items() if item["matched"]),
            "unmatched_dimensions": sorted(name for name, item in self.dimensions.items() if not item["matched"]),
        }


def _compare_amounts(tracker: _Tracker, recomputed: dict, observed: dict, hit_key, prefix: str = "amounts_cents") -> None:
    for key, expected in recomputed.items():
        path = f"{prefix}.{key}"
        if key not in observed:
            tracker.record("amounts_cents", "AMOUNT_MISMATCH", hit_key, path, expected, None, True, False)
            continue
        actual = observed[key]
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                tracker.record("amounts_cents", "AMOUNT_MISMATCH", hit_key, path, expected, actual)
                continue
            for sub_key, sub_expected in expected.items():
                if sub_key not in actual:
                    tracker.record("amounts_cents", "AMOUNT_MISMATCH", hit_key, f"{path}.{sub_key}",
                                   sub_expected, None, True, False)
                else:
                    tracker.compare("amounts_cents", "AMOUNT_MISMATCH", hit_key, f"{path}.{sub_key}",
                                    sub_expected, actual[sub_key])
            for sub_key in sorted(set(actual) - set(expected)):
                tracker.record("amounts_cents", "AMOUNT_MISMATCH", hit_key, f"{path}.{sub_key}",
                               None, actual[sub_key], False, True)
            continue
        tracker.compare("amounts_cents", "AMOUNT_MISMATCH", hit_key, path, expected, actual)


def _compare_related(tracker: _Tracker, recomputed: dict, observed: dict, hit_key) -> None:
    for key, expected in recomputed.items():
        path = f"related_ids.{key}"
        if key not in observed:
            tracker.record("related_ids", "RELATED_IDS_MISMATCH", hit_key, path, expected, None, True, False)
            continue
        actual = observed[key]
        if isinstance(expected, list):
            if not _list_equal(expected, actual):
                tracker.record("related_ids", "RELATED_IDS_MISMATCH", hit_key, path, expected, actual)
        else:
            tracker.compare("related_ids", "RELATED_IDS_MISMATCH", hit_key, path, expected, actual)


def _compare_refunds(tracker: _Tracker, recomputed: list, observed, hit_key) -> None:
    if not isinstance(observed, list):
        tracker.record("refund_facts", "REFUND_FACT_MISMATCH", hit_key, "evidence.related_refunds",
                       "列表", observed)
        return
    by_id_expected: dict = {}
    by_id_actual: dict = {}
    for item in recomputed:
        by_id_expected.setdefault(item["refund_allocation_id"], []).append(item)
    for position, item in enumerate(observed):
        path = f"evidence.related_refunds[{position}]"
        if not isinstance(item, dict):
            tracker.record("refund_facts", "REFUND_FACT_MISMATCH", hit_key, path, "对象", item)
            continue
        missing = [key for key in REFUND_REQUIRED_KEYS if key not in item]
        if missing:
            tracker.record("refund_facts", "REFUND_FACT_MISMATCH", hit_key, path,
                           f"含必需键 {list(REFUND_REQUIRED_KEYS)}", f"缺少 {missing}")
            continue
        by_id_actual.setdefault(item["refund_allocation_id"], []).append(item)
    for refund_id, items in sorted(by_id_actual.items(), key=lambda pair: str(pair[0])):
        if len(items) > 1:
            tracker.record("refund_facts", "REFUND_FACT_DUPLICATE", hit_key,
                           f"evidence.related_refunds[{refund_id}].出现次数", 1, len(items))
    for refund_id in sorted(set(by_id_expected) - set(by_id_actual), key=str):
        tracker.record("refund_facts", "REFUND_FACT_MISMATCH", hit_key,
                       f"evidence.related_refunds[{refund_id}]", refund_id, None, True, False)
    for refund_id in sorted(set(by_id_actual) - set(by_id_expected), key=str):
        tracker.record("refund_facts", "REFUND_FACT_MISMATCH", hit_key,
                       f"evidence.related_refunds[{refund_id}]", None, refund_id, False, True)
    for refund_id in sorted(set(by_id_expected) & set(by_id_actual), key=str):
        expected = by_id_expected[refund_id][0]
        actual = by_id_actual[refund_id][0]
        for field, expected_value in expected.items():
            path = f"evidence.related_refunds[{refund_id}].{field}"
            if field not in actual:
                tracker.record("refund_facts", "REFUND_FACT_MISMATCH", hit_key, path,
                               expected_value, None, True, False)
            else:
                tracker.compare("refund_facts", "REFUND_FACT_MISMATCH", hit_key, path,
                                expected_value, actual[field])


def _leaf_differences(tracker: _Tracker, expected, actual, path: str, hit_key) -> None:
    """逐叶比较 cells 等结构，差异保存可定位路径与实际预期／实际值。"""
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            sub_path = f"{path}.{key}"
            if key not in actual:
                tracker.record("source_entities", "SOURCE_VALUE_MISMATCH", hit_key, sub_path,
                               expected[key], None, True, False)
            elif key not in expected:
                tracker.record("source_entities", "SOURCE_VALUE_MISMATCH", hit_key, sub_path,
                               None, actual[key], False, True)
            else:
                _leaf_differences(tracker, expected[key], actual[key], sub_path, hit_key)
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if not _list_equal(expected, actual):
            tracker.record("source_entities", "SOURCE_VALUE_MISMATCH", hit_key, path, expected, actual)
        return
    tracker.compare("source_entities", "SOURCE_VALUE_MISMATCH", hit_key, path, expected, actual)


def _compare_entities(tracker: _Tracker, recomputed: list, observed, source_rows_recomputed: dict,
                      source_rows_observed, hit_key) -> None:
    if not isinstance(observed, list):
        tracker.record("source_entities", "SOURCE_VALUE_MISMATCH", hit_key, "evidence.entities",
                       "列表", observed)
        return
    pairs_expected = [(item["table_name"], item["record_id"]) for item in recomputed]
    pairs_actual = [
        (item.get("table_name"), item.get("record_id")) if isinstance(item, dict) else (None, None)
        for item in observed
    ]
    counted_actual: dict = {}
    for pair in pairs_actual:
        counted_actual[pair] = counted_actual.get(pair, 0) + 1
    for pair, count in sorted(counted_actual.items(), key=lambda item: str(item[0])):
        if count > 1:
            tracker.record("source_entities", "SOURCE_ENTITY_DUPLICATE", hit_key,
                           f"evidence.entities[{pair[0]}:{pair[1]}].出现次数", 1, count)
    for pair in sorted(set(pairs_expected) - set(pairs_actual), key=str):
        tracker.record("source_entities", "SOURCE_ENTITY_MISSING", hit_key,
                       f"evidence.entities[{pair[0]}:{pair[1]}]", list(pair), None, True, False)
    for pair in sorted(set(pairs_actual) - set(pairs_expected), key=str):
        tracker.record("source_entities", "SOURCE_ENTITY_EXTRA", hit_key,
                       f"evidence.entities[{pair[0]}:{pair[1]}]", None, list(pair), False, True)
    for pair in sorted(set(pairs_expected) & set(pairs_actual), key=str):
        expected = next(item for item in recomputed
                        if (item["table_name"], item["record_id"]) == pair)
        actual = next(item for item in observed
                      if isinstance(item, dict) and (item.get("table_name"), item.get("record_id")) == pair)
        base = f"evidence.entities[{pair[0]}:{pair[1]}]"
        for field in ("workbook_sha256", "sheet", "excel_row"):
            if field not in actual:
                tracker.record("source_entities", "SOURCE_VALUE_MISMATCH", hit_key, f"{base}.{field}",
                               expected.get(field), None, True, False)
            else:
                tracker.compare("source_entities", "SOURCE_VALUE_MISMATCH", hit_key, f"{base}.{field}",
                                expected.get(field), actual[field])
        if "cells" not in actual:
            tracker.record("source_entities", "SOURCE_VALUE_MISMATCH", hit_key, f"{base}.cells",
                           "cells 对象", None, True, False)
        else:
            _leaf_differences(tracker, expected.get("cells"), actual["cells"], f"{base}.cells", hit_key)

    if not isinstance(source_rows_observed, dict):
        tracker.record("source_rows", "SOURCE_ROW_MISMATCH", hit_key, "source_rows", "对象", source_rows_observed)
        return
    for sheet in ("payables", "payments", "allocations"):
        expected_rows = source_rows_recomputed.get(sheet, {})
        actual_rows = source_rows_observed.get(sheet, {})
        if not isinstance(actual_rows, dict):
            tracker.record("source_rows", "SOURCE_ROW_MISMATCH", hit_key, f"source_rows.{sheet}",
                           "对象", actual_rows)
            continue
        for record_id, expected_row in expected_rows.items():
            path = f"source_rows.{sheet}.{record_id}"
            if record_id not in actual_rows:
                tracker.record("source_rows", "SOURCE_ROW_MISMATCH", hit_key, path,
                               expected_row, None, True, False)
            else:
                tracker.compare("source_rows", "SOURCE_ROW_MISMATCH", hit_key, path,
                                expected_row, actual_rows[record_id])
        for record_id in sorted(set(actual_rows) - set(expected_rows)):
            tracker.record("source_rows", "SOURCE_ROW_MISMATCH", hit_key, f"source_rows.{sheet}.{record_id}",
                           None, actual_rows[record_id], False, True)


def _compare_counts(tracker: _Tracker, recomputed: dict, screening_report: dict) -> None:
    observed_counts = screening_report.get("rule_hit_counts")
    if not isinstance(observed_counts, dict):
        tracker.record("counts", "COUNT_MISMATCH", None, "rule_hit_counts", "对象", observed_counts)
    else:
        for rule_id in RULE_IDS + ("total",):
            path = f"rule_hit_counts.{rule_id}"
            if rule_id not in observed_counts:
                tracker.record("counts", "COUNT_MISMATCH", None, path,
                               recomputed["counts"].get(rule_id), None, True, False)
            else:
                tracker.compare("counts", "COUNT_MISMATCH", None, path,
                                recomputed["counts"].get(rule_id), observed_counts[rule_id])
    observed_rules = screening_report.get("rules")
    if not isinstance(observed_rules, dict):
        tracker.record("counts", "COUNT_MISMATCH", None, "rules", "对象", observed_rules)
        return
    for rule_id in RULE_IDS:
        entry = observed_rules.get(rule_id)
        path = f"rules.{rule_id}.hit_count"
        if not isinstance(entry, dict) or "hit_count" not in entry:
            tracker.record("counts", "COUNT_MISMATCH", None, path, recomputed["counts"].get(rule_id), None, True, False)
        else:
            tracker.compare("counts", "COUNT_MISMATCH", None, path,
                            recomputed["counts"].get(rule_id), entry["hit_count"])


def _compare_statistics(tracker: _Tracker, recomputed: dict, screening_report: dict) -> None:
    observed = screening_report.get("statistics")
    if not isinstance(observed, dict):
        tracker.record("statistics", "STATISTIC_MISMATCH", None, "statistics", "对象", observed)
        return
    involved = observed.get("involved_payments")
    for path, expected in (
        ("statistics.r02_overpayment_total_cents", recomputed["r02_overpayment_total_cents"]),
    ):
        if path.split(".")[-1] not in observed:
            tracker.record("statistics", "STATISTIC_MISMATCH", None, path, expected, None, True, False)
        else:
            tracker.compare("statistics", "STATISTIC_MISMATCH", None, path, expected, observed[path.split(".")[-1]])
    if not isinstance(involved, dict):
        tracker.record("statistics", "STATISTIC_MISMATCH", None, "statistics.involved_payments", "对象", involved)
        return
    for key, expected in (
        ("count", recomputed["involved_payment_count"]),
        ("settled_amount_cents", recomputed["involved_payment_settled_amount_cents"]),
    ):
        path = f"statistics.involved_payments.{key}"
        if key not in involved:
            tracker.record("statistics", "STATISTIC_MISMATCH", None, path, expected, None, True, False)
        else:
            tracker.compare("statistics", "STATISTIC_MISMATCH", None, path, expected, involved[key])
    expected_ids = recomputed["involved_payment_ids"]
    if "payment_ids" not in involved:
        tracker.record("statistics", "STATISTIC_MISMATCH", None, "statistics.involved_payments.payment_ids",
                       expected_ids, None, True, False)
    elif not _list_equal(expected_ids, involved["payment_ids"]):
        tracker.record("statistics", "STATISTIC_MISMATCH", None, "statistics.involved_payments.payment_ids",
                       expected_ids, involved["payment_ids"])


def _compare_reconciliation(tracker: _Tracker, recomputed: dict, screening_report: dict) -> None:
    observed = screening_report.get("overall_reconciliation")
    if not isinstance(observed, dict):
        tracker.record("overall_reconciliation", "RECONCILIATION_MISMATCH", None,
                       "overall_reconciliation", "对象", observed)
        return
    for key in ("settled_pay_master_total", "settled_refund_master_total", "master_net",
                "known_payable_link_net", "missing_payable_link_net"):
        path = f"overall_reconciliation.{key}"
        if key not in observed:
            tracker.record("overall_reconciliation", "RECONCILIATION_MISMATCH", None, path,
                           recomputed[key], None, True, False)
        else:
            tracker.compare("overall_reconciliation", "RECONCILIATION_MISMATCH", None, path,
                            recomputed[key], observed[key])
    detail = observed.get("missing_payable_link_detail")
    if not isinstance(detail, dict):
        tracker.record("overall_reconciliation", "RECONCILIATION_MISMATCH", None,
                       "overall_reconciliation.missing_payable_link_detail", "对象", detail)
        return
    for key in ("empty_ap_id", "ap_id_not_in_ledger"):
        path = f"overall_reconciliation.missing_payable_link_detail.{key}"
        if key not in detail:
            tracker.record("overall_reconciliation", "RECONCILIATION_MISMATCH", None, path,
                           recomputed["missing_payable_link_detail"][key], None, True, False)
        else:
            tracker.compare("overall_reconciliation", "RECONCILIATION_MISMATCH", None, path,
                            recomputed["missing_payable_link_detail"][key], detail[key])


def _validate_hit_key(tracker: "_Tracker", hit_key, origin: str) -> None:
    """命中键的 ID 字段必须是字符串：`rule_id` 与各规则规定的 ID 字段保持原类型和值。"""
    if not isinstance(hit_key, dict):
        tracker.record("hit_keys", "HIT_KEY_TYPE_MISMATCH", None, f"hit_key（{origin}）", "对象", hit_key)
        return
    for field, value in sorted(hit_key.items()):
        if not isinstance(value, str) or value == "":
            tracker.record(
                "hit_keys", "HIT_KEY_TYPE_MISMATCH", dict(hit_key), f"hit_key.{field}",
                value if isinstance(value, str) else str(value), value, True, True,
            )
    rule_id = hit_key.get("rule_id")
    if isinstance(rule_id, str) and rule_id in HIT_KEY_FIELDS:
        expected_fields = HIT_KEY_FIELDS[rule_id]
        missing = [field for field in expected_fields if field not in hit_key]
        extra = [field for field in hit_key if field not in expected_fields]
        if missing or extra:
            tracker.record(
                "hit_keys", "HIT_KEY_TYPE_MISMATCH", dict(hit_key), f"hit_key（{origin}）字段集合",
                list(expected_fields), {"missing": missing, "extra": extra},
            )


def compare_facts(recomputed: dict, screening_report: dict) -> dict:
    """逐项比较复算事实与 SQL 报告；返回差异列表与各维度一致状态。"""
    tracker = _Tracker()
    recomputed_list = recomputed["findings"]
    observed_list = screening_report["findings"]
    recomputed_lookup = {_key_tuple(item["hit_key"]): (item["hit_key"], item) for item in recomputed_list}
    observed_lookup = {_key_tuple(item["hit_key"]): (item["hit_key"], item) for item in observed_list}
    recomputed_keys = list(recomputed_lookup)
    observed_keys = [_key_tuple(item["hit_key"]) for item in observed_list]

    for hit_key, _ in recomputed_lookup.values():
        _validate_hit_key(tracker, hit_key, "复算")
    for hit_key, _ in observed_lookup.values():
        _validate_hit_key(tracker, hit_key, "观察")

    for key in recomputed_keys:
        if recomputed_keys.count(key) > 1:
            tracker.record("hit_keys", "DUPLICATE_HIT", dict(recomputed_lookup[key][0]), "findings",
                           "复算结果内部重复", key)
            break
    observed_counts: dict = {}
    for key in observed_keys:
        observed_counts[key] = observed_counts.get(key, 0) + 1
    for key, count in sorted(observed_counts.items(), key=lambda item: str(item[0])):
        if count > 1:
            tracker.record("hit_keys", "DUPLICATE_HIT", dict(observed_lookup[key][0]), "findings", 1, count)
    recomputed_set = set(recomputed_keys)
    observed_set = set(observed_keys)
    for key in sorted(recomputed_set - observed_set, key=str):
        tracker.record("hit_keys", "MISSING_HIT", dict(recomputed_lookup[key][0]), "findings",
                       "复算命中", None, True, False)
    for key in sorted(observed_set - recomputed_set, key=str):
        tracker.record("hit_keys", "EXTRA_HIT", dict(observed_lookup[key][0]), "findings",
                       None, "报告多出命中", False, True)

    # 渲染相同但类型不同的键：给出逐字段的类型差异（身份仍是不同的两个键）
    for missing_key in sorted(recomputed_set - observed_set, key=str):
        missing_hit_key = recomputed_lookup[missing_key][0]
        for extra_key in sorted(observed_set - recomputed_set, key=str):
            extra_hit_key = observed_lookup[extra_key][0]
            if _key_render(missing_hit_key) != _key_render(extra_hit_key):
                continue
            for field in sorted(set(missing_hit_key) & set(extra_hit_key)):
                if not _typed_equal(missing_hit_key[field], extra_hit_key[field]):
                    tracker.record(
                        "hit_keys", "HIT_KEY_TYPE_MISMATCH", dict(extra_hit_key), f"hit_key.{field}",
                        missing_hit_key[field], extra_hit_key[field],
                    )

    observed_by_key = {key: item for key, (_, item) in observed_lookup.items()}
    for key, (hit_key, item) in recomputed_lookup.items():
        if key not in observed_by_key:
            continue
        observed = observed_by_key[key]
        if observed.get("rule_id") != item["rule_id"]:
            tracker.record("rule_identity", "RULE_ID_MISMATCH", hit_key, "rule_id",
                           item["rule_id"], observed.get("rule_id"))
        key_rule = (observed.get("hit_key") or {}).get("rule_id")
        if key_rule != item["rule_id"]:
            tracker.record("rule_identity", "RULE_ID_MISMATCH", hit_key, "hit_key.rule_id",
                           item["rule_id"], key_rule)
        _compare_amounts(tracker, item["amounts_cents"], observed.get("amounts_cents") or {}, hit_key)
        _compare_related(tracker, item["related_ids"], observed.get("related_ids") or {}, hit_key)
        evidence = observed.get("evidence") if isinstance(observed.get("evidence"), dict) else {}
        _compare_refunds(tracker, item["refunds"], evidence.get("related_refunds", []), hit_key)
        _compare_entities(tracker, item["entities"], evidence.get("entities", []),
                          item["source_rows"], observed.get("source_rows") or {}, hit_key)
        if "counts" in item:
            observed_count = (observed.get("counts") or {}).get("qualifier_payment_count")
            path = "counts.qualifier_payment_count"
            if not isinstance(observed.get("counts"), dict) or "qualifier_payment_count" not in observed["counts"]:
                tracker.record("counts", "COUNT_MISMATCH", hit_key, path,
                               item["counts"]["qualifier_payment_count"], None, True, False)
            else:
                tracker.compare("counts", "COUNT_MISMATCH", hit_key, path,
                                item["counts"]["qualifier_payment_count"], observed_count)

    _compare_counts(tracker, recomputed, screening_report)
    _compare_statistics(tracker, recomputed["statistics"], screening_report)
    _compare_reconciliation(tracker, recomputed["reconciliation"], screening_report)

    for key in ("amounts_cents", "related_ids", "refund_facts", "rule_identity", "source_entities",
                "source_rows", "counts", "statistics", "overall_reconciliation", "hit_keys"):
        tracker.dimensions[key]["executed"] = True
    tracker.differences.sort(
        key=lambda item: (item["code"], canonical_json(item["hit_key"]), item["field_path"])
    )
    return {"differences": tracker.differences, **tracker.result()}


def verify_rule_facts(normalized: dict, screening_report: dict) -> dict:
    """独立复算规则事实并与 SQL 筛查报告逐项比较，返回复核报告（不写文件、不修改入参）。"""
    bindings = _check_inputs(normalized, screening_report)
    index = _check_normalized_records(normalized)
    try:
        recomputed = recompute_facts(normalized, index)
        comparison = compare_facts(recomputed, screening_report)
    except CrossCheckBlocked:
        raise
    except CrossCheckError:
        raise
    except Exception as exc:  # noqa: BLE001 - 统一保留阶段与异常链
        raise CrossCheckError(
            f"[compare] 复算或比较失败：{type(exc).__name__}: {exc}",
            [f"阶段=compare", f"原始异常={type(exc).__name__}: {exc}"],
        ) from exc

    differences = comparison["differences"]
    dimensions = comparison["dimensions"]
    matched = not differences and all(item["matched"] for item in dimensions.values())
    return {
        "crosscheck_version": CROSSCHECK_VERSION,
        "batch_status": MATCHED_STATUS if matched else MISMATCH_STATUS,
        "matched": matched,
        "mode": MODE,
        "next_step_allowed": False,
        "period": {"period_start": PERIOD_START, "period_end": PERIOD_END},
        "cutoff_date": SUPPORTED_CUTOFF_DATE,
        "input_source_sha256": bindings["input_sha256"],
        "normalized_payload_sha256": bindings["normalized_payload_sha256"],
        "screening_report_sha256": bindings["screening_report_sha256"],
        "rule_core_version_checked": EXPECTED_RULE_CORE_VERSION,
        "rule_recomputed_counts": recomputed["counts"],
        "recomputed_facts": {
            "findings": recomputed["findings"],
            "reconciliation": recomputed["reconciliation"],
            "statistics": recomputed["statistics"],
        },
        "observed_summary": {
            "rule_hit_counts": screening_report.get("rule_hit_counts"),
            "r02_overpayment_total_cents": screening_report.get("statistics", {}).get(
                "r02_overpayment_total_cents"
            ),
            "overall_reconciliation": screening_report.get("overall_reconciliation"),
        },
        "comparison": {
            "dimensions": dimensions,
            "difference_count": len(differences),
            "matched_dimensions": comparison["matched_dimensions"],
            "unmatched_dimensions": comparison["unmatched_dimensions"],
        },
        "differences": differences,
        "method": METHOD_NOTE,
        "limits": LIMITS,
    }
