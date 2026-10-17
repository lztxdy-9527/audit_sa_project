#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-048：证据链索引（线索 → 账务行 → 凭证 → 原始表行）。

命令行：
    python -B scripts/build_trace_index.py --run-root <已完成的演示运行根> --out-dir <新证据根>

只读合并一次已完成演示的既有报告（R02 线索 / 账证差异与缺失 / 账实差异与未达），生成
`trace_index.json`（cases / ledger / vouchers / source_rows / meta，供 TASK-049/050 读取）与
`trace_index_source.json`（输入身份与命令）。**数值只复制不重算**，**引用必须闭合**，
同一账务对象跨报告出现时合并为一条 case 的多个证据块，不重复计数。

边界：索引只是既有合成证据的导航数据；`real_approval=null`、真实独立初判未保存、
`next_step_allowed=false`、`ai_enabled=false`；不证明凭证/流水真实，不构成审计结论。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
LEDGER_NORMALIZED = ROOT / "data/runtime/task042_dsh_01/normal.load/normalized.json"
BATCH_DIR = ROOT / "data/batches/task027r1_run_04/batch_normal"
SOURCE_WORKBOOK = BATCH_DIR / "source/input.xlsx"
INDEX_VERSION = "TASK-048-trace-index-1.2"
GENERATOR = "scripts/build_trace_index.py"
CASES_PER_PAGE = 50
VOUCHER_FILES = (("vouchers/invoices.json", "INVOICE"),
                 ("vouchers/contracts.json", "CONTRACT"),
                 ("vouchers/bank_receipts.json", "BANK_RECEIPT"),
                 ("vouchers/approvals.json", "APPROVAL"),
                 ("vouchers/goods_receipts.json", "GOODS_RECEIPT"))
IMAGE_NOTE = "模拟数据，无真实图像"
BOUNDARY_NOTE = ("索引只读展示既有合成证据；不是批次批准、不是身份认证；"
                 "real_approval=null；不开放 AI/终判；核对结论由人填写。")


class ReportError(Exception):
    def __init__(self, kind, message, field=None):
        super().__init__(message)
        self.kind = kind  # "usage" → exit 2；"content" → exit 1
        self.field = field


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_bytes())


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def ident(path: Path) -> dict:
    raw = path.read_bytes()
    return {"relative": rel(path), "byte_size": len(raw), "sha256": sha_bytes(raw)}


def require(document, path, label):
    current = document
    for key in path:
        if type(current) is not dict or key not in current:
            raise ReportError("content", "缺少必需字段：%s" % ".".join((label,) + path),
                              field="%s.%s" % (label, ".".join(path)))
        current = current[key]
    return current


def money(cents) -> str:
    if type(cents) is not int:
        return "—"
    return "%.2f 元" % (cents / 100.0)


def load_inputs(run_root: Path, batch_dir: Path) -> dict:
    name = run_root.name
    source_workbook = batch_dir / "source/input.xlsx"
    files = {
        "demo_summary": run_root / "demo_summary.json",
        "input_registry": run_root / "task043_input_check" / "input_registry.json",
        "voucher_report": run_root / "task044_match" / "voucher_match_report.json",
        "reconcile_report": run_root / "task045_reconcile" / "bank_reconcile_report.json",
        "fact_packet": ROOT / "data/runtime" / name / "normal.facts" / "fact_packet.json",
        "judgment": (ROOT / "data/human_initial_judgment_records" / name / "bound"
                     / "rec_0001" / "judgment_result.json"),
        "record_manifest": (ROOT / "data/human_initial_judgment_records" / name / "bound"
                            / "rec_0001" / "manifest.json"),
        "normalized": LEDGER_NORMALIZED,
        "batch_manifest": batch_dir / "batch_manifest.json",
        "source_workbook": source_workbook,
    }
    missing = [label for label, path in files.items() if not path.is_file()]
    if missing:
        raise ReportError("usage", "缺少运行根/业务根/账务文件：%s" % ", ".join(missing),
                          field=missing[0])
    documents = {label: read_json(path) for label, path in files.items()
                 if label != "source_workbook"}
    manifest = documents["batch_manifest"]
    expected = ((manifest.get("hashes") or {}).get("source_before_copy")
                or (manifest.get("hashes") or {}).get("source_after_copy"))
    actual = sha_bytes(source_workbook.read_bytes())
    if type(expected) is not str or expected != actual:
        raise ReportError("content",
                          "source_drift：源工作簿哈希与批次接收身份不一致，拒绝生成",
                          field="source_drift")
    documents["source_identity"] = {
        "relative": rel(source_workbook),
        "byte_size": source_workbook.stat().st_size,
        "sha256": actual,
        "source_drift": {"status": "OK", "expected_sha256": expected,
                         "actual_sha256": actual},
    }
    return {"name": name, "documents": documents, "files": files}


def load_vouchers(documents) -> dict:
    registry = documents["input_registry"]
    input_value = require(registry, ("input_root",), "input_registry")
    input_root = ROOT / input_value
    if not input_root.is_dir():
        raise ReportError("content", "input_registry.input_root 不存在：%s" % input_value,
                          field="input_registry.input_root")
    vouchers = {}
    for relative, voucher_type in VOUCHER_FILES:
        path = input_root / relative
        if not path.is_file():
            raise ReportError("usage", "缺少输入凭证文件：%s" % relative, field=relative)
        for index, record in enumerate(read_json(path)):
            voucher_id = record.get("voucher_id")
            if type(voucher_id) is not str:
                raise ReportError("content", "凭证记录缺 voucher_id：%s[%d]" % (relative, index),
                                  field="%s[%d].voucher_id" % (relative, index))
            vouchers[voucher_id] = {"voucher_type": voucher_type, "record": record,
                                    "source": {"relative": rel(path),
                                               "record_index": index}}
    links = read_json(input_root / "links/index.json") \
        if (input_root / "links/index.json").is_file() else []
    return {"input_root": input_root, "vouchers": vouchers, "links": links}


def load_ledger_rows(documents) -> dict:
    normalized = documents["normalized"]
    tables = require(normalized, ("tables",), "normalized")
    rows = {}
    for name in ("payables", "payments", "allocations", "suppliers"):
        records = require(tables, (name, "records"), "normalized")
        rows[name] = [item["data"] for item in records]
    sources = {}
    for name, id_field in (("payables", "ap_id"), ("payments", "payment_id"),
                           ("allocations", "allocation_id"),
                           ("suppliers", "supplier_id")):
        for item in tables[name]["records"]:
            sources[(name, item["data"].get(id_field))] = item["source"]["excel_row"]
    return rows, sources


def ledger_status(ledger_type, ledger_id, voucher_report, reconcile_report):
    states = []
    for item in voucher_report.get("items") or []:
        if item.get("ledger_type") == ledger_type and item.get("ledger_id") == ledger_id:
            status = item.get("status")
            if status == "MATCHED":
                states.append("已核对一致")
            elif status == "MISSING_VOUCHER":
                states.append("未取得")
            else:
                states.append("存在差异")
    for item in voucher_report.get("missing_vouchers") or []:
        if item.get("ledger_type") == ledger_type and item.get("ledger_id") == ledger_id:
            states.append("未取得")
    for item in reconcile_report.get("differences") or []:
        if item.get("ledger_id") == ledger_id:
            states.append("存在差异")
    for item in (reconcile_report.get("unmatched") or {}).get("ledger_unmatched") or []:
        if item.get("ledger_type") == ledger_type and item.get("ledger_id") == ledger_id:
            states.append("存在差异")
    for item in reconcile_report.get("matched") or []:
        if item.get("ledger_id") == ledger_id:
            states.append("已核对一致")
    if not states:
        return "未涉及"
    if "存在差异" in states:
        return "存在差异"
    if "未取得" in states:
        return "未取得"
    return "已核对一致"


def source_ref_from_cell(entry, field, sheet=None):
    cells = entry.get("cells") or {}
    cell = cells.get(field)
    if type(cell) is not dict:
        return None
    source = entry.get("source") or {}
    return {"sheet": sheet or source.get("sheet"),
            "excel_row": source.get("excel_row"),
            "column_letter": cell.get("column_letter"),
            "raw_value": cell.get("raw_value"),
            "standard_value": cell.get("standard_value")}


def finding_refs(finding, vouchers, links, rows):
    related = finding.get("related_ids") or {}
    ledger_refs = []
    for ap_id in [related.get("payable_id")] if related.get("payable_id") else []:
        payable = next((row for row in rows["payables"] if row.get("ap_id") == ap_id), None)
        if payable is None:
            raise ReportError("content", "R02 线索引用的应付不存在：%s" % ap_id,
                              field="finding.related_ids.payable_id=%s" % ap_id)
        ledger_refs.append({"ledger_type": "AP", "ledger_id": ap_id,
                            "amount_cents": payable.get("payable_amount_cents")})
    for payment_id in related.get("payment_ids") or []:
        payment = next((row for row in rows["payments"] if row.get("payment_id") == payment_id),
                       None)
        if payment is None:
            raise ReportError("content", "R02 线索引用的付款不存在：%s" % payment_id,
                              field="finding.related_ids.payment_ids=%s" % payment_id)
        ledger_refs.append({"ledger_type": "PAYMENT", "ledger_id": payment_id,
                            "amount_cents": payment.get("amount_cents")})
    for refund_id in related.get("refund_ids") or []:
        refund = next((row for row in rows["payments"] if row.get("payment_id") == refund_id),
                      None)
        if refund is None:
            raise ReportError("content", "R02 线索引用的退款不存在：%s" % refund_id,
                              field="finding.related_ids.refund_ids=%s" % refund_id)
        ledger_refs.append({"ledger_type": "REFUND", "ledger_id": refund_id,
                            "amount_cents": refund.get("amount_cents")})
    ledger_ids = {(item["ledger_type"], item["ledger_id"]) for item in ledger_refs}
    voucher_ids = []
    for link in links:
        if (link.get("ledger_type"), link.get("ledger_id")) in ledger_ids:
            voucher_ids.append(link.get("voucher_id"))
    voucher_refs = []
    for voucher_id in voucher_ids:
        entry = vouchers.get(voucher_id)
        if entry is None:
            raise ReportError("content", "索引引用的凭证不存在：%s" % voucher_id,
                              field="links.voucher_id=%s" % voucher_id)
        voucher_refs.append({"voucher_type": entry["voucher_type"],
                             "voucher_id": voucher_id,
                             "status": "已取得",
                             "fields": entry["record"]})
    source_refs = []
    amounts = finding.get("amounts_cents") or {}
    context = finding.get("context") or {}
    payable = context.get("payable")
    if isinstance(payable, dict):
        ref = source_ref_from_cell(payable, "payable_amount")
        if ref:
            source_refs.append(ref)
    for key in ("allocations", "payments", "refunds"):
        for entry in context.get(key) or []:
            for field in ("allocated_amount", "amount"):
                ref = source_ref_from_cell(entry, field)
                if ref:
                    source_refs.append(ref)
    placeholders = [{"label": "发票影像", "note": IMAGE_NOTE},
                    {"label": "银行回单影像", "note": IMAGE_NOTE}]
    return ledger_refs, voucher_refs, source_refs, placeholders, amounts


def build_cases(documents, vouchers, links, rows):
    cases = []
    fact = documents["fact_packet"]
    voucher_report = documents["voucher_report"]
    reconcile_report = documents["reconcile_report"]
    for finding in fact.get("findings") or []:
        ledger_refs, voucher_refs, source_refs, placeholders, amounts = finding_refs(
            finding, vouchers, links, rows)
        cases.append({
            "source_group": "fact_packet",
            "kind": "RULE_FINDING",
            "title": "R02 超额付款线索：净付款超过应付 %s，待核查"
                     % money(amounts.get("overpayment")),
            "severity": "yellow",
            "amounts": [{"label": "应付金额", "cents": amounts.get("payable_amount"),
                         "cny": money(amounts.get("payable_amount"))},
                        {"label": "已付合计", "cents": amounts.get("paid_total"),
                         "cny": money(amounts.get("paid_total"))},
                        {"label": "退款合计", "cents": amounts.get("refund_total"),
                         "cny": money(amounts.get("refund_total"))},
                        {"label": "净付款", "cents": amounts.get("net_total"),
                         "cny": money(amounts.get("net_total"))},
                        {"label": "超额", "cents": amounts.get("overpayment"),
                         "cny": money(amounts.get("overpayment"))}],
            "evidence_blocks": [{"source": "fact_packet",
                                 "finding_id": finding.get("finding_id")}],
            "ledger_refs": ledger_refs,
            "voucher_refs": voucher_refs,
            "source_refs": source_refs,
            "image_placeholders": placeholders,
        })
    for difference in voucher_report.get("differences") or []:
        voucher_id = difference.get("voucher_id")
        entry = vouchers.get(voucher_id) if type(voucher_id) is str else None
        if entry is None and type(voucher_id) is str:
            raise ReportError("content", "账证差异引用的凭证不存在：%s" % voucher_id,
                              field="voucher_report.differences.voucher_id=%s" % voucher_id)
        cases.append({
            "source_group": "voucher_match",
            "kind": "VOUCHER_DIFFERENCE",
            "title": "凭证字段差异：%s（%s）" % (
                {"AMOUNT_MISMATCH": "金额不一致", "DATE_MISMATCH": "日期不一致",
                 "COUNTERPARTY_MISMATCH": "对方不一致", "STATUS_MISMATCH": "状态不一致",
                 "DIRECTION_MISMATCH": "方向不一致", "SUM_MISMATCH": "合计不一致",
                 "TAX_TOTAL_MISMATCH": "税额合计不一致",
                 "REFERENCE_CONFLICT": "引用冲突"}.get(difference.get("classification"),
                                                       difference.get("classification")),
                difference.get("field")),
            "severity": "red",
            "amounts": [],
            "evidence_blocks": [{"source": "voucher_match",
                                 "classification": difference.get("classification"),
                                 "field": difference.get("field"),
                                 "actual": difference.get("actual"),
                                 "expected": difference.get("expected")}],
            "ledger_refs": [{"ledger_type": difference.get("ledger_type"),
                             "ledger_id": difference.get("ledger_id"),
                             "amount_cents": None}],
            "voucher_refs": [{"voucher_type": entry["voucher_type"] if entry else None,
                              "voucher_id": voucher_id,
                              "status": "已取得" if entry else "未取得",
                              "fields": entry["record"] if entry else {}}],
            "source_refs": [],
            "image_placeholders": [{"label": "凭证影像", "note": IMAGE_NOTE}],
        })
    for missing in voucher_report.get("missing_vouchers") or []:
        ledger_type = missing.get("ledger_type")
        ledger_id = missing.get("ledger_id")
        voucher_type = missing.get("voucher_type")
        amount = None
        if ledger_type == "AP":
            row = next((item for item in rows["payables"] if item.get("ap_id") == ledger_id), None)
            amount = row.get("payable_amount_cents") if row else None
        else:
            row = next((item for item in rows["payments"]
                        if item.get("payment_id") == ledger_id), None)
            amount = row.get("amount_cents") if row else None
        cases.append({
            "source_group": "voucher_match",
            "kind": "VOUCHER_MISSING",
            "title": "未取得%s：%s %s 缺少关联凭证，待核查"
                     % ({"APPROVAL": "审批单", "BANK_RECEIPT": "银行回单",
                         "INVOICE": "发票", "CONTRACT": "合同",
                         "GOODS_RECEIPT": "入库单"}.get(voucher_type, "凭证"),
                        ledger_type, ledger_id),
            "severity": "red",
            "amounts": [{"label": "账务金额", "cents": amount, "cny": money(amount)}],
            "evidence_blocks": [{"source": "voucher_match", "missing": True,
                                 "detail": missing.get("detail")}],
            "ledger_refs": [{"ledger_type": ledger_type, "ledger_id": ledger_id,
                             "amount_cents": amount}],
            "voucher_refs": [{"voucher_type": voucher_type, "voucher_id": None,
                              "status": "未取得", "fields": {}}],
            "source_refs": [],
            "image_placeholders": [{"label": "凭证影像（未取得）", "note": IMAGE_NOTE}],
        })
    for difference in reconcile_report.get("differences") or []:
        ledger_id = difference.get("ledger_id")
        ledger_type = "REFUND" if any(
            row.get("payment_id") == ledger_id and row.get("transaction_type") == "REFUND"
            for row in rows["payments"]) else "PAYMENT"
        cases.append({
            "source_group": "bank_reconcile",
            "kind": "BANK_DIFFERENCE",
            "title": "银行流水差异：%s（%s）" % (
                {"AMOUNT_MISMATCH": "金额不一致", "DATE_MISMATCH": "日期不一致",
                 "COUNTERPARTY_MISMATCH": "对方不一致", "DIRECTION_MISMATCH": "方向不一致",
                 "REFERENCE_CONFLICT": "引用冲突"}.get(difference.get("classification"),
                                                       difference.get("classification")),
                difference.get("field")),
            "severity": "red",
            "amounts": [],
            "evidence_blocks": [{"source": "bank_reconcile",
                                 "bank_txn_id": difference.get("bank_txn_id"),
                                 "classification": difference.get("classification"),
                                 "field": difference.get("field"),
                                 "actual": difference.get("actual"),
                                 "expected": difference.get("expected")}],
            "ledger_refs": [{"ledger_type": ledger_type, "ledger_id": ledger_id,
                             "amount_cents": None}],
            "voucher_refs": [],
            "source_refs": [],
            "image_placeholders": [],
        })
    unmatched = reconcile_report.get("unmatched") or {}
    for item in unmatched.get("ledger_unmatched") or []:
        cases.append({
            "source_group": "bank_reconcile",
            "kind": "BANK_UNMATCHED",
            "title": "账有实无：%s %s 未在银行流水中找到，待核查"
                     % (item.get("ledger_type"), item.get("ledger_id")),
            "severity": "red",
            "amounts": [{"label": "账务金额", "cents": item.get("amount_cents"),
                         "cny": money(item.get("amount_cents"))}],
            "evidence_blocks": [{"source": "bank_reconcile",
                                 "detail": "账有实无（未达账项候选）"}],
            "ledger_refs": [{"ledger_type": item.get("ledger_type"),
                             "ledger_id": item.get("ledger_id"),
                             "amount_cents": item.get("amount_cents")}],
            "voucher_refs": [],
            "source_refs": [],
            "image_placeholders": [],
        })
    for item in unmatched.get("bank_unmatched") or []:
        cases.append({
            "source_group": "bank_reconcile",
            "kind": "BANK_UNMATCHED_BANK",
            "title": "实有账无：银行流水 %s 未找到对应账务记录，待核查"
                     % item.get("bank_txn_id"),
            "severity": "red",
            "amounts": [{"label": "流水金额", "cents": item.get("amount_cents"),
                         "cny": money(item.get("amount_cents"))}],
            "evidence_blocks": [{"source": "bank_reconcile",
                                 "bank_txn_id": item.get("bank_txn_id"),
                                 "detail": "实有账无（未达账项候选）"}],
            "ledger_refs": [],
            "bank_refs": [{"bank_txn_id": item.get("bank_txn_id"),
                           "direction": item.get("direction"),
                           "txn_date": item.get("txn_date"),
                           "amount_cents": item.get("amount_cents")}],
            "voucher_refs": [],
            "source_refs": [],
            "image_placeholders": [],
        })
    # 跨报告合并：同一账务对象同时出现在账证与账实时合并为一条 case 的多个证据块；
    # 同一报告内的不同事项保持独立（不重复计数，也不吞掉不同事项）。
    merged = []
    by_key = {}
    for case in cases:
        key = None
        for ref in case["ledger_refs"]:
            key = (ref["ledger_type"], ref["ledger_id"])
            break
        group = case.get("source_group")
        merge_key = (key, "cross") if key is not None and group in (
            "voucher_match", "bank_reconcile") else None
        existing = by_key.get(merge_key) if merge_key is not None else None
        if existing is not None and existing.get("source_group") != group:
            existing["evidence_blocks"].extend(case["evidence_blocks"])
            existing["voucher_refs"].extend(
                [item for item in case["voucher_refs"] if item not in existing["voucher_refs"]])
            existing["source_refs"].extend(
                [item for item in case["source_refs"] if item not in existing["source_refs"]])
            existing["amounts"].extend(
                [item for item in case["amounts"] if item not in existing["amounts"]])
            existing["kind"] = "MULTI_SOURCE"
            if case["severity"] == "red":
                existing["severity"] = "red"
            continue
        if merge_key is not None and merge_key not in by_key:
            by_key[merge_key] = case
        merged.append(case)
    for index, case in enumerate(merged, start=1):
        case["case_id"] = "CASE-%04d" % index
    return merged


def slices(rows, row_sources, vouchers, voucher_report, reconcile_report):
    ledger_rows = []
    for row in rows["payables"]:
        ledger_id = row.get("ap_id")
        ledger_rows.append({"ledger_type": "AP", "ledger_id": ledger_id,
                            "status": ledger_status("AP", ledger_id, voucher_report,
                                                    reconcile_report),
                            "review": {"status": "待审阅", "issue": None,
                                       "suggestion": None, "reviewer": None,
                                       "date": None},
                            "fields": row,
                            "source": {"sheet": "payables",
                                       "excel_row": row_sources.get(("payables", ledger_id))}})
    for row in rows["payments"]:
        ledger_type = "REFUND" if row.get("transaction_type") == "REFUND" else "PAYMENT"
        ledger_id = row.get("payment_id")
        ledger_rows.append({"ledger_type": ledger_type, "ledger_id": ledger_id,
                            "status": ledger_status(ledger_type, ledger_id, voucher_report,
                                                    reconcile_report),
                            "review": {"status": "待审阅", "issue": None,
                                       "suggestion": None, "reviewer": None,
                                       "date": None},
                            "fields": row,
                            "source": {"sheet": "payments",
                                       "excel_row": row_sources.get(("payments", ledger_id))}})
    for row in rows["allocations"]:
        ledger_id = row.get("allocation_id")
        ledger_rows.append({"ledger_type": "ALLOCATION", "ledger_id": ledger_id,
                            "status": "未涉及",
                            "review": {"status": "待审阅", "issue": None,
                                       "suggestion": None, "reviewer": None,
                                       "date": None},
                            "fields": row,
                            "source": {"sheet": "allocations",
                                       "excel_row": row_sources.get(("allocations", ledger_id))}})
    voucher_rows = []
    for voucher_id in sorted(vouchers):
        entry = vouchers[voucher_id]
        voucher_rows.append({"voucher_id": voucher_id,
                             "voucher_type": entry["voucher_type"],
                             "status": "已取得",
                             "review": {"status": "待审阅", "issue": None,
                                        "suggestion": None, "reviewer": None,
                                        "date": None},
                             "fields": entry["record"],
                             "source": entry["source"],
                             "image_placeholder": {"label": "凭证影像",
                                                   "note": IMAGE_NOTE}})
    return ledger_rows, voucher_rows


def build_source_rows(documents):
    source_rows = {}
    normalized = documents["normalized"]
    for name in ("suppliers", "payables", "payments", "allocations"):
        for item in normalized["tables"][name]["records"]:
            key = (name, item["source"]["excel_row"])
            cells = {}
            for column, cell in (item.get("cells") or {}).items():
                if type(cell) is not dict:
                    continue
                cells[cell.get("column_letter")] = {
                    "raw_value": cell.get("raw_value"),
                    "standard_value": cell.get("standard_value")}
            source_rows[key[0] + "!%d" % key[1]] = {
                "sheet": name, "excel_row": item["source"]["excel_row"],
                "cells": cells,
                "review": {"status": "待审阅", "issue": None, "suggestion": None,
                           "reviewer": None, "date": None},
            }
    return [source_rows[key] for key in sorted(source_rows)]


GL_ENTRY_LINKS = {"记-001": ("AP", "AP01"), "记-002": ("PAYMENT", "P01"),
                  "记-003": ("PAYMENT", "P02"), "记-004": ("REFUND", "R01")}
GL_FILES = ("chart_of_accounts.json", "journal_entries.json", "trial_balance.json",
            "ledger_general.json", "ledger_subsidiary.json", "balance_sheet.json",
            "bank_statement.json", "bank_journal.json", "attachment_index.json")


def load_gl(gl_root: Path, gl_report_path: Path, index: dict) -> dict:
    if not gl_root.is_dir():
        raise ReportError("usage", "--gl-root 不存在：%s" % gl_root)
    if not gl_report_path.is_file():
        raise ReportError("usage", "--gl-report 不存在：%s" % gl_report_path)
    documents = {}
    files = []
    for name in GL_FILES:
        path = gl_root / name
        if not path.is_file():
            raise ReportError("content", "GL 文件缺失：%s" % name,
                              field="gl.%s" % name)
        documents[name] = read_json(path)
        files.append(ident(path))
    manifest = ident(gl_root / "gl_manifest.json")
    report = read_json(gl_report_path)
    checks = report.get("checks") or []
    summary = report.get("summary") or {}
    cases = index.get("cases") or []
    entries = []
    for entry in documents["journal_entries.json"].get("entries") or []:
        item = dict(entry)
        ledger_ref = GL_ENTRY_LINKS.get(entry.get("entry_id"))
        item["ledger_refs"] = ([{"ledger_type": ledger_ref[0],
                                 "ledger_id": ledger_ref[1]}] if ledger_ref else [])
        case_refs = []
        if ledger_ref:
            for case in cases:
                for ref in case.get("ledger_refs") or []:
                    if (ref.get("ledger_type"), ref.get("ledger_id")) == ledger_ref:
                        case_refs.append(case.get("case_id"))
        item["case_refs"] = sorted(set(case_refs))
        entries.append(item)
    gl = {
        "gl_root": rel(gl_root),
        "chart_of_accounts": documents["chart_of_accounts.json"],
        "journal_entries": entries,
        "trial_balance": documents["trial_balance.json"],
        "ledger_general": documents["ledger_general.json"],
        "ledger_subsidiary": documents["ledger_subsidiary.json"],
        "balance_sheet": documents["balance_sheet.json"],
        "bank_statement": documents["bank_statement.json"],
        "bank_journal": documents["bank_journal.json"],
        "attachment_index": documents["attachment_index.json"],
        "checks": checks,
        "summary": {"six": summary.get("six"), "overall": summary.get("overall"),
                    "notes": summary.get("notes") or []},
        "unperformed": report.get("unperformed") or [],
        "period": report.get("period"),
        "batch_id": report.get("batch_id"),
        "source": {"files": files, "manifest": manifest,
                   "report": ident(gl_report_path)},
        "note": "只读复制 GL 包与核对报告；数字不重算；无时间戳/随机数。",
    }
    return gl


def build(run_root: Path, out_dir: Path, batch_dir: Path = BATCH_DIR,
          gl_root: Path = None, gl_report: Path = None) -> int:
    loaded = load_inputs(run_root, batch_dir)
    documents = loaded["documents"]
    name = loaded["name"]
    voucher_data = load_vouchers(documents)
    rows, row_sources = load_ledger_rows(documents)
    cases = build_cases(documents, voucher_data["vouchers"], voucher_data["links"], rows)
    for case in cases:
        case.setdefault("review", {"status": "待审阅", "issue": None,
                                   "suggestion": None, "reviewer": None,
                                   "date": None})
    ledger_rows, voucher_rows = slices(rows, row_sources, voucher_data["vouchers"],
                                       documents["voucher_report"],
                                       documents["reconcile_report"])
    source_rows = build_source_rows(documents)
    # 引用闭合校验
    ledger_keys = {(row["ledger_type"], row["ledger_id"]) for row in ledger_rows}
    for case in cases:
        if not case["ledger_refs"] and case["kind"] != "BANK_UNMATCHED_BANK":
            raise ReportError("content", "case 缺少账务引用：%s" % case["case_id"],
                              field="%s.ledger_refs" % case["case_id"])
        for ref in case["ledger_refs"]:
            key = (ref["ledger_type"], ref["ledger_id"])
            if key not in ledger_keys:
                raise ReportError("content", "case 账务引用悬空：%s %s=%s"
                                  % (case["case_id"], ref["ledger_type"], ref["ledger_id"]),
                                  field="%s.ledger_refs[0].ledger_id=%s"
                                        % (case["case_id"], ref["ledger_id"]))
        for ref in case["voucher_refs"]:
            if ref.get("voucher_id") and ref["voucher_id"] not in voucher_data["vouchers"]:
                raise ReportError("content", "case 凭证引用悬空：%s %s"
                                  % (case["case_id"], ref["voucher_id"]),
                                  field="%s.voucher_refs.voucher_id=%s"
                                        % (case["case_id"], ref["voucher_id"]))
        for ref in case["source_refs"]:
            key = (ref.get("sheet"), ref.get("excel_row"), ref.get("column_letter"))
            if key not in {(row["sheet"], row["excel_row"], None) for row in source_rows}:
                pass  # 原表行以 sheet+excel_row 解析，列由页面展开；行缺失才算悬空
            sheet_row = (ref.get("sheet"), ref.get("excel_row"))
            if sheet_row not in {(row["sheet"], row["excel_row"]) for row in source_rows}:
                raise ReportError("content", "case 原始行引用悬空：%s %s!%s"
                                  % (case["case_id"], ref.get("sheet"), ref.get("excel_row")),
                                  field="%s.source_refs.sheet=%s"
                                        % (case["case_id"], ref.get("sheet")))
    counts = {}
    severities = {"red": 0, "yellow": 0, "green": 0}
    for case in cases:
        counts[case["kind"]] = counts.get(case["kind"], 0) + 1
        severities[case["severity"]] += 1
    status_counts = {}
    for row in ledger_rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    meta = {
        "index_version": INDEX_VERSION,
        "run_root": name,
        "batch_id": (documents["demo_summary"].get("batch") or {}).get("batch_id"),
        "entity": (documents["demo_summary"].get("batch") or {}).get("entity"),
        "cases_total": len(cases),
        "cases_per_page": CASES_PER_PAGE,
        "pages": int(math.ceil(len(cases) / float(CASES_PER_PAGE))),
        "case_counts": counts,
        "severity_counts": severities,
        "ledger_total": len(ledger_rows),
        "voucher_total": len(voucher_rows),
        "source_rows_total": len(source_rows),
        "status_counts": status_counts,
        "source_identity": documents["source_identity"],
        "review": {"status": "待审阅",
                   "note": "本卡不采集审阅；问题/建议/审阅人/日期为 null，供 TASK-052 合并。"},
        "generator": GENERATOR,
        "boundary_note": BOUNDARY_NOTE,
    }
    index = {"cases": cases, "ledger": ledger_rows, "vouchers": voucher_rows,
             "source_rows": source_rows, "meta": meta}
    if gl_root is not None and gl_report is not None:
        index["gl"] = load_gl(gl_root, gl_report, index)
        meta["gl"] = {"present": True,
                      "checks": len(index["gl"].get("checks") or []),
                      "overall": (index["gl"].get("summary") or {}).get("overall")}
    payload = json.dumps(index, ensure_ascii=False, indent=2,
                         sort_keys=True).encode("utf-8") + b"\n"
    out_dir.mkdir(parents=True, exist_ok=False)
    target = out_dir / "trace_index.json"
    target.write_bytes(payload)
    if target.read_bytes() != payload:
        raise ReportError("usage", "trace_index.json 写后读回不一致")
    source = {
        "index_version": INDEX_VERSION,
        "generator": GENERATOR,
        "run_root": name,
        "command": {"argv": [GENERATOR, "--run-root", rel(run_root),
                             "--out-dir", "<out-dir>"]},
        "gl_inputs": ([ident(gl_root / name) for name in GL_FILES]
                      + [ident(gl_root / "gl_manifest.json"), ident(gl_report)]
                      if gl_root is not None and gl_report is not None else []),
        "inputs": [ident(loaded["files"][label]) for label in
                   ("demo_summary", "input_registry", "voucher_report",
                    "reconcile_report", "fact_packet", "judgment",
                    "record_manifest", "normalized", "batch_manifest",
                    "source_workbook")],
        "input_root_manifest": ident(voucher_data["input_root"] / "input_manifest.json"),
        "outputs": ["trace_index.json"],
        "note": "确定性输出；不含时间戳、随机数或外部链接；只读读取既有合成证据。",
    }
    source_path = out_dir / "trace_index_source.json"
    source_path.write_bytes(json.dumps(source, ensure_ascii=False, indent=2,
                                       sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({"status": "PASS", "run_root": name, "cases": len(cases),
                      "pages": meta["pages"], "index_bytes": len(payload),
                      "out": str(out_dir)}, ensure_ascii=False))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-048 证据链索引")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--batch-dir", default=str(BATCH_DIR),
                        help="批次源目录（默认固定批次；仅测试漂移时指向副本）")
    parser.add_argument("--gl-root", default=None,
                        help="可选：GL v1 输入包（与 --gl-report 同时提供时生成 gl 节）")
    parser.add_argument("--gl-report", default=None,
                        help="可选：六类核对报告路径")
    args = parser.parse_args(argv)
    run_root = Path(args.run_root)
    out_dir = Path(args.out_dir)
    batch_dir = Path(args.batch_dir)
    gl_root = Path(args.gl_root) if args.gl_root else None
    gl_report = Path(args.gl_report) if args.gl_report else None
    try:
        if (gl_root is None) != (gl_report is None):
            raise ReportError("usage", "--gl-root 与 --gl-report 必须同时提供或同时省略")
        if not run_root.is_dir():
            raise ReportError("usage", "--run-root 不存在：%s" % run_root)
        try:
            run_root.resolve().relative_to(TEST_ROOT.resolve())
        except ValueError:
            raise ReportError("usage", "--run-root 必须位于 %s 之下" % TEST_ROOT)
        if out_dir.exists():
            raise ReportError("usage", "--out-dir 必须从未存在：%s" % out_dir)
        try:
            out_dir.resolve().relative_to(TEST_ROOT.resolve())
        except ValueError:
            raise ReportError("usage", "--out-dir 必须位于 %s 之下" % TEST_ROOT)
        if not out_dir.name.startswith(("task048_", "task051_", "task052_",
                                        "task057_")):
            raise ReportError("usage", "--out-dir 目录名必须以 task048_、task051_、task052_ 或 task057_ 开头")
        return build(run_root, out_dir, batch_dir, gl_root, gl_report)
    except ReportError as exc:
        print(json.dumps({"status": "ERROR", "kind": exc.kind, "error": str(exc),
                          "field": exc.field}, ensure_ascii=False))
        return 1 if exc.kind == "content" else 2


if __name__ == "__main__":
    raise SystemExit(main())
