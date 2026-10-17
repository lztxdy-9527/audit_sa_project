#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-044：账证相符 L1（凭证字段级核对）与抽样核对底稿。

只做**字段级 L1**：以输入提供的 `links/index.json` 为唯一关联基础，逐字段比对账务与凭证；
不查看影像、不做发票/回单外部查验、不做 OCR/清洗、不做无索引模糊匹配、不采集人类核对结论。
输出 `voucher_match_report.json` + `voucher_match_report.md`：全量逐项状态、差异清单
（账务 ID/凭证 ID/字段/实际/预期/分类）、账有证无/证有账无、R02 程序抽样底稿（核对结论列留空）。

边界：合成数据；`real_approval=null`、真实独立初判未保存、`next_step_allowed=false`、
`ai_enabled=false`；本工具不写账务/凭证/银行/批次，只写本次证据根。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
REPORT_VERSION = "task044-voucher-match-1.0"
CLASSES = ("MATCHED", "AMOUNT_MISMATCH", "TAX_TOTAL_MISMATCH", "DATE_MISMATCH",
           "COUNTERPARTY_MISMATCH", "STATUS_MISMATCH", "DIRECTION_MISMATCH",
           "SUM_MISMATCH", "MISSING_VOUCHER", "EXTRA_VOUCHER", "REFUND_LINK_MISMATCH")
PRIORITY = {name: index for index, name in enumerate(CLASSES)}
CUTOFF = "2026-09-30"
PERIOD_START = "2026-09-01"
EXPECTED_BATCH = "batch_normal"
R02_LEDGER_IDS = ("AP01", "P01", "P02", "R01")
BOUNDARIES = {"real_approval": None, "batch_approved": False,
              "real_initial_judgment_saved": False, "next_step_allowed": False,
              "ai_enabled": False, "identity_authenticated": False,
              "audit_conclusion_formed": False, "final_judgment_recorded": False}


class MatchUsageError(Exception):
    pass


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def read_json(path: Path):
    return json.loads(path.read_bytes())


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def identity(path: Path) -> dict:
    raw = path.read_bytes()
    return {"relative": rel(path), "byte_size": len(raw), "sha256": sha_bytes(raw)}


def is_int(value) -> bool:
    return type(value) is int


def is_text(value) -> bool:
    return type(value) is str and value != ""


def in_period(value) -> bool:
    return type(value) is str and PERIOD_START <= value <= CUTOFF


def date_lte(value, cutoff=CUTOFF) -> bool:
    return type(value) is str and value <= cutoff


class Findings:
    def __init__(self):
        self.differences = []
        self.missing = []
        self.extra = []

    def add(self, ledger_type, ledger_id, voucher_id, voucher_type, field, actual,
            expected, classification):
        if classification not in PRIORITY or classification == "MATCHED":
            raise MatchUsageError("非法差异分类：%r" % classification)
        self.differences.append({"ledger_type": ledger_type, "ledger_id": ledger_id,
                                 "voucher_id": voucher_id,
                                 "voucher_type": voucher_type, "field": field,
                                 "actual": actual, "expected": expected,
                                 "classification": classification})

    def mark_missing(self, ledger_type, ledger_id, voucher_type, detail):
        self.missing.append({"ledger_type": ledger_type, "ledger_id": ledger_id,
                             "voucher_type": voucher_type, "detail": detail,
                             "classification": "MISSING_VOUCHER"})

    def mark_extra(self, voucher_id, voucher_type, detail):
        self.extra.append({"voucher_id": voucher_id, "voucher_type": voucher_type,
                           "detail": detail, "classification": "EXTRA_VOUCHER"})


def load_input(input_root: Path) -> dict:
    if not input_root.is_dir():
        raise MatchUsageError("输入根不存在：%s" % input_root)
    manifest = read_json(input_root / "input_manifest.json")
    vouchers = {}
    by_type = {}
    for relative, voucher_type in (
            ("vouchers/invoices.json", "INVOICE"),
            ("vouchers/contracts.json", "CONTRACT"),
            ("vouchers/bank_receipts.json", "BANK_RECEIPT"),
            ("vouchers/approvals.json", "APPROVAL"),
            ("vouchers/goods_receipts.json", "GOODS_RECEIPT")):
        records = read_json(input_root / relative)
        by_type[voucher_type] = records
        for record in records:
            vouchers[record["voucher_id"]] = {"type": voucher_type, "record": record}
    links = read_json(input_root / "links/index.json")
    bank_txns = {record["bank_txn_id"]: record
                 for record in read_json(input_root / "bank/transactions.json")}
    return {"manifest": manifest, "vouchers": vouchers, "by_type": by_type,
            "links": links, "bank_txns": bank_txns,
            "manifest_identity": identity(input_root / "input_manifest.json")}


def load_ledger(normalized_path: Path, input_root: Path) -> dict:
    if not normalized_path.is_file():
        raise MatchUsageError("账务 normalized.json 不存在：%s" % normalized_path)
    normalized = read_json(normalized_path)
    source = normalized.get("source") or {}
    batch_dir = ROOT / "data/batches/task027r1_run_04/batch_normal"
    workbook = batch_dir / "source/input.xlsx"
    if not workbook.is_file():
        raise MatchUsageError("批次工作簿不存在：%s" % workbook)
    workbook_sha = sha_bytes(workbook.read_bytes())
    if source.get("input_sha256") != workbook_sha:
        raise MatchUsageError("账务 normalized 的 source.input_sha256 与本批次工作簿不一致")
    if normalized.get("mode") != "DEVELOPMENT_TEST_ONLY":
        raise MatchUsageError("账务 normalized 必须为 DEVELOPMENT_TEST_ONLY")
    started = {}
    started_path = normalized_path.parent / "started.json"
    if started_path.is_file():
        started = read_json(started_path)
        if started.get("batch_id") != EXPECTED_BATCH:
            raise MatchUsageError("账务 started.json 的 batch_id 与本批次不一致")
        if started.get("source_batch_relative") != rel(batch_dir):
            raise MatchUsageError("账务 started.json 的 source_batch_relative 与本批次不一致")
        binding_input = ((started.get("bindings") or {}).get("run_binding") or {}).get("input") or {}
        if binding_input.get("file_sha256") != workbook_sha:
            raise MatchUsageError("账务 bindings.run_binding.input 与本批次工作簿不一致")
    artifacts = {}
    artifacts_path = normalized_path.parent / "artifacts.json"
    if artifacts_path.is_file():
        artifacts = read_json(artifacts_path)
        normalized_sha = sha_bytes(normalized_path.read_bytes())
        if artifacts.get("normalized_file_sha256") != normalized_sha:
            raise MatchUsageError("账务 artifacts 的 normalized_file_sha256 不一致")
        if artifacts.get("batch_id") != EXPECTED_BATCH:
            raise MatchUsageError("账务 artifacts 的 batch_id 与本批次不一致")
    tables = normalized["tables"]

    def rows(name):
        return [item["data"] for item in tables[name]["records"]]

    payables = {row["ap_id"]: row for row in rows("payables")}
    payments = {row["payment_id"]: row for row in rows("payments")}
    allocations = {row["allocation_id"]: row for row in rows("allocations")}
    suppliers = {row["supplier_id"]: row["supplier_name"] for row in rows("suppliers")}
    for row in payables.values():
        if not in_period(row.get("ap_date")):
            raise MatchUsageError("账务应付日期不在期间内：%s" % row.get("ap_id"))
    for row in payments.values():
        if not in_period(row.get("payment_date")):
            raise MatchUsageError("账务付款/退款日期不在期间内：%s" % row.get("payment_id"))
    return {"normalized_identity": identity(normalized_path),
            "started_identity": identity(started_path) if started_path.is_file() else None,
            "artifacts_identity": identity(artifacts_path) if artifacts_path.is_file() else None,
            "batch_relative": rel(batch_dir), "batch_id": EXPECTED_BATCH,
            "workbook_sha256": workbook_sha,
            "payables": payables, "payments": payments, "allocations": allocations,
            "suppliers": suppliers}


def index_links(links):
    grouped = {}
    for link in links:
        grouped.setdefault((link["ledger_type"], link["ledger_id"]), []) \
            .append(link)
    return grouped


def voucher_ids_for(links_by_key, ledger_type, ledger_id, link_type):
    return [link["voucher_id"] for link in
            links_by_key.get((ledger_type, ledger_id), [])
            if link["link_type"] == link_type]


def declared_types(links):
    types = {link["link_type"] for link in links}
    return types


def add_field_check(findings, ledger_type, ledger_id, voucher_id, voucher_type, field,
                    actual, expected, classification):
    if canon(actual) != canon(expected):
        findings.add(ledger_type, ledger_id, voucher_id, voucher_type, field,
                     actual, expected, classification)
        return False
    return True


def check_ap(findings, ledger, data, links_by_key, declared):
    ap_id = data["ap_id"]
    supplier_id = data["supplier_id"]
    amount = data["payable_amount_cents"]
    invoice_ids = voucher_ids_for(links_by_key, "AP", ap_id, "AP_INVOICE")
    contract_ids = voucher_ids_for(links_by_key, "AP", ap_id, "AP_CONTRACT")
    goods_ids = voucher_ids_for(links_by_key, "AP", ap_id, "AP_GOODS_RECEIPT")
    items = []
    # 应付 ↔ 发票（≥1，合计 == 应付金额）
    if not invoice_ids:
        findings.mark_missing("AP", ap_id, "INVOICE", "应付单无任何关联发票（账有证无）")
        items.append({"voucher_type": "INVOICE", "voucher_ids": []})
    else:
        totals = []
        for voucher_id in invoice_ids:
            record = ledger["vouchers"][voucher_id]["record"]
            add_field_check(findings, "AP", ap_id, voucher_id, "INVOICE",
                            "seller_supplier_id", record.get("seller_supplier_id"),
                            supplier_id, "COUNTERPARTY_MISMATCH")
            if not date_lte(record.get("issue_date")):
                findings.add("AP", ap_id, voucher_id, "INVOICE", "issue_date",
                             record.get("issue_date"), "<= " + CUTOFF, "DATE_MISMATCH")
            if is_int(record.get("amount_cents")) and is_int(record.get("tax_cents")) \
                    and is_int(record.get("total_cents")) \
                    and record["total_cents"] != record["amount_cents"] + record["tax_cents"]:
                findings.add("AP", ap_id, voucher_id, "INVOICE", "tax_cents",
                             record["tax_cents"],
                             record["total_cents"] - record["amount_cents"],
                             "TAX_TOTAL_MISMATCH")
            if is_int(record.get("total_cents")):
                totals.append(record["total_cents"])
        if len(totals) == len(invoice_ids):
            classification = "AMOUNT_MISMATCH" if len(totals) == 1 else "SUM_MISMATCH"
            if sum(totals) != amount:
                findings.add("AP", ap_id, ", ".join(invoice_ids), "INVOICE",
                             "total_cents_sum", sum(totals), amount, classification)
        items.append({"voucher_type": "INVOICE", "voucher_ids": invoice_ids})
    # 应付 ↔ 合同（可选：仅当全局声明该凭证类型时要求）
    if contract_ids:
        for voucher_id in contract_ids:
            record = ledger["vouchers"][voucher_id]["record"]
            add_field_check(findings, "AP", ap_id, voucher_id, "CONTRACT",
                            "amount_cents", record.get("amount_cents"), amount,
                            "AMOUNT_MISMATCH")
            add_field_check(findings, "AP", ap_id, voucher_id, "CONTRACT",
                            "counterparty_supplier_id",
                            record.get("counterparty_supplier_id"), supplier_id,
                            "COUNTERPARTY_MISMATCH")
        items.append({"voucher_type": "CONTRACT", "voucher_ids": contract_ids})
    elif "AP_CONTRACT" in declared:
        findings.mark_missing("AP", ap_id, "CONTRACT", "应付单无关联合同（账有证无）")
        items.append({"voucher_type": "CONTRACT", "voucher_ids": []})
    # 应付 ↔ 入库单（多张合计）
    if goods_ids:
        amounts = []
        for voucher_id in goods_ids:
            record = ledger["vouchers"][voucher_id]["record"]
            add_field_check(findings, "AP", ap_id, voucher_id, "GOODS_RECEIPT",
                            "supplier_id", record.get("supplier_id"), supplier_id,
                            "COUNTERPARTY_MISMATCH")
            if is_int(record.get("amount_cents")):
                amounts.append(record["amount_cents"])
        if len(amounts) == len(goods_ids):
            classification = "AMOUNT_MISMATCH" if len(amounts) == 1 else "SUM_MISMATCH"
            if sum(amounts) != amount:
                findings.add("AP", ap_id, ", ".join(goods_ids), "GOODS_RECEIPT",
                             "amount_cents_sum", sum(amounts), amount, classification)
        items.append({"voucher_type": "GOODS_RECEIPT", "voucher_ids": goods_ids})
    elif "AP_GOODS_RECEIPT" in declared:
        findings.mark_missing("AP", ap_id, "GOODS_RECEIPT", "应付单无关联入库单（账有证无）")
        items.append({"voucher_type": "GOODS_RECEIPT", "voucher_ids": []})
    extra = _extras_for(links_by_key, "AP", ap_id,
                        {"AP_INVOICE": "INVOICE", "AP_CONTRACT": "CONTRACT",
                         "AP_GOODS_RECEIPT": "GOODS_RECEIPT"})
    for voucher_id, voucher_type in extra:
        findings.mark_extra(voucher_id, voucher_type, "索引指向未使用的凭证")
    return items, amount


def check_payment(findings, ledger, data, links_by_key, declared):
    payment_id = data["payment_id"]
    amount = data["amount_cents"]
    payee = data["payee_supplier_id"]
    supplier_name = ledger["suppliers"].get(payee)
    items = []
    approvals = voucher_ids_for(links_by_key, "PAYMENT", payment_id, "PAYMENT_APPROVAL")
    if not approvals:
        findings.mark_missing("PAYMENT", payment_id, "APPROVAL", "付款无关联审批单（账有证无）")
        items.append({"voucher_type": "APPROVAL", "voucher_ids": []})
    else:
        for index, voucher_id in enumerate(approvals):
            record = ledger["vouchers"][voucher_id]["record"]
            if index > 0:
                findings.mark_extra(voucher_id, "APPROVAL", "1:1 关联下多余的审批单")
                continue
            add_field_check(findings, "PAYMENT", payment_id, voucher_id, "APPROVAL",
                            "amount_cents", record.get("amount_cents"), amount,
                            "AMOUNT_MISMATCH")
            if record.get("status") != "APPROVED":
                findings.add("PAYMENT", payment_id, voucher_id, "APPROVAL", "status",
                             record.get("status"), "APPROVED", "STATUS_MISMATCH")
            add_field_check(findings, "PAYMENT", payment_id, voucher_id, "APPROVAL",
                            "payment_id", record.get("payment_id"), payment_id,
                            "MISSING_VOUCHER")
        items.append({"voucher_type": "APPROVAL", "voucher_ids": approvals})
    receipts = voucher_ids_for(links_by_key, "PAYMENT", payment_id,
                               "PAYMENT_BANK_RECEIPT")
    if not receipts:
        findings.mark_missing("PAYMENT", payment_id, "BANK_RECEIPT",
                              "付款无关联银行回单（账有证无）")
        items.append({"voucher_type": "BANK_RECEIPT", "voucher_ids": []})
    else:
        for index, voucher_id in enumerate(receipts):
            record = ledger["vouchers"][voucher_id]["record"]
            if index > 0:
                findings.mark_extra(voucher_id, "BANK_RECEIPT", "1:1 关联下多余的回单")
                continue
            add_field_check(findings, "PAYMENT", payment_id, voucher_id, "BANK_RECEIPT",
                            "amount_cents", record.get("amount_cents"), amount,
                            "AMOUNT_MISMATCH")
            add_field_check(findings, "PAYMENT", payment_id, voucher_id, "BANK_RECEIPT",
                            "txn_date", record.get("txn_date"), data.get("payment_date"),
                            "DATE_MISMATCH")
            if supplier_name is not None:
                add_field_check(findings, "PAYMENT", payment_id, voucher_id,
                                "BANK_RECEIPT", "counterparty_name",
                                record.get("counterparty_name"), supplier_name,
                                "COUNTERPARTY_MISMATCH")
            if record.get("direction") != "PAY":
                findings.add("PAYMENT", payment_id, voucher_id, "BANK_RECEIPT",
                             "direction", record.get("direction"), "PAY",
                             "DIRECTION_MISMATCH")
        items.append({"voucher_type": "BANK_RECEIPT", "voucher_ids": receipts})
    extra = _extras_for(links_by_key, "PAYMENT", payment_id,
                        {"PAYMENT_APPROVAL": "APPROVAL",
                         "PAYMENT_BANK_RECEIPT": "BANK_RECEIPT"})
    for voucher_id, voucher_type in extra:
        findings.mark_extra(voucher_id, voucher_type, "索引指向未使用的凭证")
    return items, amount


def check_refund(findings, ledger, data, links_by_key, declared):
    refund_id = data["payment_id"]
    amount = data["amount_cents"]
    items = []
    link_mark = len(findings.differences)
    # 退款链路（账内）：原付款与原分摊必须存在且互相一致
    original_payment_id = data.get("original_payment_id")
    original = ledger["payments"].get(original_payment_id) \
        if is_text(original_payment_id) else None
    if original is None:
        findings.add("REFUND", refund_id, None, "REFUND", "original_payment_id",
                     original_payment_id, "既有 PAY 付款", "REFUND_LINK_MISMATCH")
    elif original.get("transaction_type") != "PAY":
        findings.add("REFUND", refund_id, None, "REFUND", "original_payment_id",
                     original_payment_id, "既有 PAY 付款", "REFUND_LINK_MISMATCH")
    refund_allocations = [row for row in ledger["allocations"].values()
                          if row.get("payment_id") == refund_id]
    if len(refund_allocations) != 1:
        findings.add("REFUND", refund_id, None, "REFUND", "allocations",
                     len(refund_allocations), 1, "REFUND_LINK_MISMATCH")
    else:
        allocation = refund_allocations[0]
        original_allocation_id = allocation.get("original_allocation_id")
        original_allocation = ledger["allocations"].get(original_allocation_id) \
            if is_text(original_allocation_id) else None
        if original_allocation is None:
            findings.add("REFUND", refund_id, None, "REFUND",
                         "original_allocation_id", original_allocation_id,
                         "既有分摊", "REFUND_LINK_MISMATCH")
        else:
            if original_allocation.get("payment_id") != original_payment_id:
                findings.add("REFUND", refund_id, None, "REFUND",
                             "original_allocation.payment_id",
                             original_allocation.get("payment_id"),
                             original_payment_id, "REFUND_LINK_MISMATCH")
            if original_allocation.get("ap_id") != allocation.get("ap_id"):
                findings.add("REFUND", refund_id, None, "REFUND",
                             "original_allocation.ap_id",
                             original_allocation.get("ap_id"), allocation.get("ap_id"),
                             "REFUND_LINK_MISMATCH")
        if is_int(allocation.get("allocated_amount_cents")) \
                and allocation["allocated_amount_cents"] != amount:
            findings.add("REFUND", refund_id, None, "REFUND",
                         "allocated_amount_cents", allocation["allocated_amount_cents"],
                         amount, "REFUND_LINK_MISMATCH")
    if len(findings.differences) > link_mark:
        items.append({"voucher_type": "REFUND", "voucher_ids": []})
    supplier_name = ledger["suppliers"].get(data.get("payee_supplier_id"))
    receipts = voucher_ids_for(links_by_key, "REFUND", refund_id,
                               "REFUND_BANK_RECEIPT")
    if not receipts:
        findings.mark_missing("REFUND", refund_id, "BANK_RECEIPT",
                              "退款无关联银行回单（账有证无）")
    else:
        for index, voucher_id in enumerate(receipts):
            record = ledger["vouchers"][voucher_id]["record"]
            if index > 0:
                findings.mark_extra(voucher_id, "BANK_RECEIPT", "1:1 关联下多余的回单")
                continue
            add_field_check(findings, "REFUND", refund_id, voucher_id, "BANK_RECEIPT",
                            "amount_cents", record.get("amount_cents"), amount,
                            "AMOUNT_MISMATCH")
            add_field_check(findings, "REFUND", refund_id, voucher_id, "BANK_RECEIPT",
                            "txn_date", record.get("txn_date"), data.get("payment_date"),
                            "DATE_MISMATCH")
            if supplier_name is not None:
                add_field_check(findings, "REFUND", refund_id, voucher_id,
                                "BANK_RECEIPT", "counterparty_name",
                                record.get("counterparty_name"), supplier_name,
                                "COUNTERPARTY_MISMATCH")
            if record.get("direction") != "REFUND":
                findings.add("REFUND", refund_id, voucher_id, "BANK_RECEIPT",
                             "direction", record.get("direction"), "REFUND",
                             "DIRECTION_MISMATCH")
        items.append({"voucher_type": "BANK_RECEIPT", "voucher_ids": receipts})
    extra = _extras_for(links_by_key, "REFUND", refund_id,
                        {"REFUND_BANK_RECEIPT": "BANK_RECEIPT"})
    for voucher_id, voucher_type in extra:
        findings.mark_extra(voucher_id, voucher_type, "索引指向未使用的凭证")
    return items, amount


def _extras_for(links_by_key, ledger_type, ledger_id, type_map):
    """同一凭证被同一账务对象重复引用时登记 EXTRA_VOUCHER。"""
    seen = {}
    result = []
    for link in links_by_key.get((ledger_type, ledger_id), []):
        link_type = link["link_type"]
        if link_type not in type_map:
            continue
        key = (link["voucher_id"], type_map[link_type])
        seen[key] = seen.get(key, 0) + 1
    for (voucher_id, voucher_type), count in seen.items():
        if count > 1:
            result.append((voucher_id, voucher_type))
    return result


def classify_items(findings, items):
    by_item = {}
    for difference in findings.differences:
        key = (difference["ledger_type"], difference["ledger_id"],
               difference["voucher_type"])
        by_item.setdefault(key, []).append(difference)
    for item in items:
        key = (item["ledger_type"], item["ledger_id"], item["voucher_type"])
        differences = by_item.get(key, [])
        if differences:
            item["status"] = min((d["classification"] for d in differences),
                                 key=lambda name: PRIORITY[name])
        elif item["voucher_ids"]:
            item["status"] = "MATCHED"
        else:
            item["status"] = "MISSING_VOUCHER"
        item["differences"] = differences


def build_report(input_root, ledger_path, out_dir):
    input_data = load_input(input_root)
    ledger_data = load_ledger(ledger_path, input_root)
    ledger = dict(ledger_data)
    ledger.update({"vouchers": input_data["vouchers"]})
    links_by_key = index_links(input_data["links"])
    declared = declared_types(input_data["links"])
    findings = Findings()
    items = []
    for ap_id in sorted(ledger_data["payables"]):
        data = ledger_data["payables"][ap_id]
        ap_items, amount = check_ap(findings, ledger, data, links_by_key, declared)
        for item in ap_items:
            items.append({"ledger_type": "AP", "ledger_id": ap_id,
                          "ledger_amount_cents": amount, **item})
    for payment_id in sorted(ledger_data["payments"]):
        data = ledger_data["payments"][payment_id]
        if data.get("transaction_type") == "PAY":
            pay_items, amount = check_payment(findings, ledger, data, links_by_key,
                                              declared)
            for item in pay_items:
                items.append({"ledger_type": "PAYMENT", "ledger_id": payment_id,
                              "ledger_amount_cents": amount, **item})
        elif data.get("transaction_type") == "REFUND":
            refund_items, amount = check_refund(findings, ledger, data, links_by_key,
                                                declared)
            for item in refund_items:
                items.append({"ledger_type": "REFUND", "ledger_id": payment_id,
                              "ledger_amount_cents": amount, **item})
    classify_items(findings, items)
    # 证有账无：未被任何 link 引用的凭证
    linked_vouchers = {link["voucher_id"] for link in input_data["links"]}
    linked_vouchers |= {item["voucher_id"] for item in findings.extra}
    for voucher_id in sorted(input_data["vouchers"]):
        if voucher_id not in linked_vouchers:
            entry = input_data["vouchers"][voucher_id]
            findings.mark_extra(voucher_id, entry["type"], "凭证未被任何索引引用（证有账无）")
    counts = {name: 0 for name in CLASSES}
    counts["MATCHED"] = sum(1 for item in items if item["status"] == "MATCHED")
    for difference in findings.differences:
        counts[difference["classification"]] += 1
    counts["MISSING_VOUCHER"] += len(findings.missing)
    counts["EXTRA_VOUCHER"] += len(findings.extra)
    sampling = build_sampling(items, findings, ledger_data, input_data)

    def item_status_summary():
        summary = {}
        for item in items:
            summary[item["status"]] = summary.get(item["status"], 0) + 1
        return summary

    differences_total = len(findings.differences) + len(findings.missing) \
        + len(findings.extra)
    report = {
        "report_version": REPORT_VERSION,
        "generated_by": "scripts/voucher_match_v1.py",
        "input": {"root": rel(input_root),
                  "input_version": input_data["manifest"].get("input_version"),
                  "manifest": input_data["manifest_identity"],
                  "entity": input_data["manifest"].get("entity")},
        "ledger": {"normalized": ledger_data["normalized_identity"],
                   "started": ledger_data["started_identity"],
                   "artifacts": ledger_data["artifacts_identity"],
                   "batch_relative": ledger_data["batch_relative"],
                   "batch_id": ledger_data["batch_id"],
                   "workbook_sha256": ledger_data["workbook_sha256"],
                   "bindings_checked": {"batch_id": True,
                                        "source_batch_relative": True,
                                        "run_binding_input": True,
                                        "normalized_file_sha256": True,
                                        "mode": "DEVELOPMENT_TEST_ONLY"}},
        "items": items,
        "differences": findings.differences,
        "missing_vouchers": findings.missing,
        "extra_vouchers": findings.extra,
        "summary": {"items_total": len(items), "item_status": item_status_summary(),
                    "classification_counts": counts,
                    "differences_total": differences_total,
                    "missing_total": len(findings.missing),
                    "extra_total": len(findings.extra)},
        "r02_sampling": sampling,
        "conclusion": "ALL_MATCHED" if differences_total == 0 else "DIFFERENCES_FOUND",
        "verification_level": "L1_FIELD_LEVEL_NO_EXTERNAL_VERIFICATION",
        "boundaries": dict(BOUNDARIES),
        "note": ("L1 字段级核对；未查看影像、未做发票/回单外部查验、不证明凭证真实；"
                 "R01—R04 是待核查线索，不是舞弊/损失/审计结论；"
                 "人类核对结论未采集、不虚构，需另行授权与登记。"),
    }
    out_dir.mkdir(parents=True, exist_ok=False)
    _write_json(out_dir / "voucher_match_report.json", report)
    (out_dir / "voucher_match_report.md").write_bytes(render_markdown(report).encode("utf-8"))
    return report


def build_sampling(items, findings, ledger_data, input_data):
    sampled = []
    for ledger_type, ledger_id in (("AP", "AP01"), ("PAYMENT", "P01"),
                                   ("PAYMENT", "P02"), ("REFUND", "R01")):
        evidence = []
        for item in items:
            if item["ledger_type"] != ledger_type or item["ledger_id"] != ledger_id:
                continue
            for voucher_id in item["voucher_ids"]:
                entry = input_data["vouchers"][voucher_id]
                differences = [difference for difference in findings.differences
                               if difference["voucher_id"] == voucher_id
                               or (difference["voucher_id"] or "").find(voucher_id) >= 0]
                evidence.append({"voucher_id": voucher_id,
                                 "voucher_type": entry["type"],
                                 "record": entry["record"],
                                 "status": item["status"],
                                 "differences": differences})
            for missing in findings.missing:
                if missing["ledger_type"] == ledger_type \
                        and missing["ledger_id"] == ledger_id:
                    evidence.append({"voucher_id": None,
                                     "voucher_type": missing["voucher_type"],
                                     "record": None, "status": "MISSING_VOUCHER",
                                     "differences": [missing]})
        ledger_record = (ledger_data["payables"].get(ledger_id)
                         or ledger_data["payments"].get(ledger_id))
        sampled.append({"ledger_type": ledger_type, "ledger_id": ledger_id,
                        "ledger_record": ledger_record, "evidence": evidence,
                        "human_conclusion": None,
                        "note": "人类核对结论需另行授权与登记；本列留空"})
    return {"selection": "程序选取（R02 线索涉及 AP01/P01/P02/R01；非审计抽样方法学）",
            "items": sampled,
            "human_conclusion_note": "核对结论列必须为空——不采集、不虚构人类字段。"}


def render_markdown(report):
    counts = report["summary"]["classification_counts"]
    lines = ["# 账证相符 L1 核对报告（合成）", "",
             "> L1 字段级核对；未查看影像、未做发票/回单外部查验、不证明凭证真实。"
             "R01—R04 是待核查线索，不是舞弊/损失/审计结论。", "",
             "## 输入与账务身份", "",
             "- 输入根：`%s`（input_version=%s）" % (report["input"]["root"],
                                                  report["input"]["input_version"]),
             "- 输入清单：%s（%d B / `%s`）" % (
                 report["input"]["manifest"]["relative"],
                 report["input"]["manifest"]["byte_size"],
                 report["input"]["manifest"]["sha256"][:16]),
             "- 账务 normalized：`%s`（%d B / `%s`）" % (
                 report["ledger"]["normalized"]["relative"],
                 report["ledger"]["normalized"]["byte_size"],
                 report["ledger"]["normalized"]["sha256"][:16]),
             "- 批次：`%s`；账务绑定核对：batch_id / source_batch_relative / "
             "run_binding.input / normalized_file_sha256 / mode" % report["ledger"]["batch_id"],
             "", "## 汇总", "",
             "- 逐项：共 %d 项；状态 %s" % (report["summary"]["items_total"],
                                        json.dumps(report["summary"]["item_status"],
                                                   ensure_ascii=False)),
             "- 分类计数：%s" % json.dumps({k: v for k, v in counts.items() if v},
                                          ensure_ascii=False),
             "- 差异合计：%d（差异 %d / 账有证无 %d / 证有账无 %d）" % (
                 report["summary"]["differences_total"],
                 len(report["differences"]), len(report["missing_vouchers"]),
                 len(report["extra_vouchers"])),
             "- 结论：`%s`" % report["conclusion"], "",
             "## 逐项状态", "",
             "| 账务类型 | 账务ID | 金额(分) | 凭证类型 | 凭证ID | 状态 |",
             "| --- | --- | --- | --- | --- | --- |"]
    for item in report["items"]:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            item["ledger_type"], item["ledger_id"], item["ledger_amount_cents"],
            item["voucher_type"],
            ", ".join(item["voucher_ids"]) or "—", item["status"]))
    lines += ["", "## 差异清单", ""]
    if report["differences"]:
        lines += ["| 账务类型 | 账务ID | 凭证ID | 凭证类型 | 字段 | 实际 | 预期 | 分类 |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for difference in report["differences"]:
            lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                difference["ledger_type"], difference["ledger_id"],
                difference["voucher_id"], difference["voucher_type"],
                difference["field"],
                json.dumps(difference["actual"], ensure_ascii=False),
                json.dumps(difference["expected"], ensure_ascii=False),
                difference["classification"]))
    else:
        lines.append("（无）")
    lines += ["", "## 账有证无 / 证有账无", ""]
    lines.append("- 账有证无：%d" % len(report["missing_vouchers"]))
    for missing in report["missing_vouchers"]:
        lines.append("  - %s %s 缺 %s（%s）" % (missing["ledger_type"],
                                              missing["ledger_id"],
                                              missing["voucher_type"],
                                              missing["detail"]))
    lines.append("- 证有账无：%d" % len(report["extra_vouchers"]))
    for extra in report["extra_vouchers"]:
        lines.append("  - %s（%s）：%s" % (extra["voucher_id"], extra["voucher_type"],
                                         extra["detail"]))
    lines += ["", "## 抽样底稿（程序选取，非审计抽样方法学）", "",
              "- %s" % report["r02_sampling"]["selection"], "",
              "| 账务类型 | 账务ID | 凭证ID | 核对状态 | 关键证据 | 核对结论 |",
              "| --- | --- | --- | --- | --- | --- |"]
    for sample in report["r02_sampling"]["items"]:
        if not sample["evidence"]:
            lines.append("| %s | %s | — | MISSING_VOUCHER | — |  |" % (
                sample["ledger_type"], sample["ledger_id"]))
            continue
        for evidence in sample["evidence"]:
            record = evidence["record"] or {}
            key_fields = {key: record.get(key) for key in
                          ("total_cents", "amount_cents", "tax_cents", "issue_date",
                           "txn_date", "direction", "status", "payment_id")
                          if key in record}
            lines.append("| %s | %s | %s | %s | %s |  |" % (
                sample["ledger_type"], sample["ledger_id"],
                evidence["voucher_id"] or "—", evidence["status"],
                json.dumps(key_fields, ensure_ascii=False)))
    lines += ["", "> 核对结论列为空：不采集、不虚构人类字段；人类核对结论需另行授权与登记。",
              "", "## 边界", "",
              "- 合成数据；`real_approval=null`、真实独立初判未保存、`next_step_allowed=false`、"
              "`ai_enabled=false`。",
              "- %s" % report["note"]]
    return "\n".join(lines) + "\n"


def _write_json(path, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2,
                         sort_keys=True).encode("utf-8") + b"\n"
    path.write_bytes(payload)
    if path.read_bytes() != payload:
        raise MatchUsageError("写后读回不一致：%s" % path)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-044 账证相符 L1 核对")
    parser.add_argument("--input", required=True, help="TASK-043 v1 输入根（只读）")
    parser.add_argument("--ledger-normalized", dest="ledger_normalized", required=True,
                        help="已接受运行证据的 normal.load/normalized.json（只读）")
    parser.add_argument("--out", required=True, help="证据根（必须从未存在）")
    args = parser.parse_args(argv)
    try:
        input_root = Path(args.input)
        ledger_path = Path(args.ledger_normalized)
        out_dir = Path(args.out)
        if out_dir.exists():
            raise MatchUsageError("--out 必须从未存在：%s" % out_dir)
        try:
            out_dir.resolve().relative_to(EVIDENCE_ROOT.resolve())
        except ValueError:
            raise MatchUsageError("--out 必须位于 %s 之下" % EVIDENCE_ROOT)
        if not out_dir.name.startswith("task044_"):
            raise MatchUsageError("--out 目录名必须以 task044_ 开头")
        report = build_report(input_root, ledger_path, out_dir)
        print(json.dumps({"status": report["conclusion"],
                          "items": report["summary"]["items_total"],
                          "differences_total": report["summary"]["differences_total"],
                          "missing": report["summary"]["missing_total"],
                          "extra": report["summary"]["extra_total"],
                          "out": str(out_dir)}, ensure_ascii=False))
        return 0 if report["conclusion"] == "ALL_MATCHED" else 1
    except MatchUsageError as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
