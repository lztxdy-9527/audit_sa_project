#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-045：账实相符（银行流水交易级勾对）与未达账项底稿。

只做**交易级 L1 + 期间合计**：以 TASK-043 输入（流水/索引/回单）与已接受账务（付款/退款）为基础，
按“引用优先 → 金额+日期+对方三元组”确定性勾对，1:1；输出逐条状态、差异清单、未达账项两侧、
期间合计与现金/分摊口径提示。不做格式适配、不做 OCR/影像、不做函证/盘点、不做银行余额核对；
不采集、不虚构人类核对结论。

边界：合成数据；`real_approval=null`、真实独立初判未保存、`next_step_allowed=false`、
`ai_enabled=false`；不写输入根/批次/账务/凭证/银行/Gate/历史。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
REPORT_VERSION = "task045-bank-reconcile-1.0"
CLASSES = ("MATCHED", "AMOUNT_MISMATCH", "DATE_MISMATCH", "COUNTERPARTY_MISMATCH",
           "DIRECTION_MISMATCH", "REFERENCE_CONFLICT", "DUPLICATE_BANK_LINE",
           "DUPLICATE_MATCH", "LEDGER_UNMATCHED", "BANK_UNMATCHED")
PRIORITY = {name: index for index, name in enumerate(CLASSES)}
CUTOFF = "2026-09-30"
PERIOD_START = "2026-09-01"
EXPECTED_BATCH = "batch_normal"
BOUNDARIES = {"real_approval": None, "batch_approved": False,
              "real_initial_judgment_saved": False, "next_step_allowed": False,
              "ai_enabled": False, "identity_authenticated": False,
              "audit_conclusion_formed": False, "final_judgment_recorded": False}


class ReconcileUsageError(Exception):
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


def load_input(input_root: Path) -> dict:
    if not input_root.is_dir():
        raise ReconcileUsageError("输入根不存在：%s" % input_root)
    manifest = read_json(input_root / "input_manifest.json")
    txns = read_json(input_root / "bank/transactions.json")
    receipts = read_json(input_root / "vouchers/bank_receipts.json")
    receipt_txn = {record["voucher_id"]: record.get("bank_txn_id") for record in receipts}
    declared = {}
    for link in read_json(input_root / "links/index.json"):
        if link["link_type"] in ("PAYMENT_BANK_RECEIPT", "REFUND_BANK_RECEIPT"):
            txn_id = receipt_txn.get(link["voucher_id"])
            if is_text(txn_id):
                declared.setdefault(link["ledger_id"], set()).add(txn_id)
    return {"manifest": manifest, "txns": txns, "receipt_txn": receipt_txn,
            "index_declared": {key: sorted(value) for key, value in declared.items()},
            "manifest_identity": identity(input_root / "input_manifest.json")}


def load_ledger(normalized_path: Path) -> dict:
    if not normalized_path.is_file():
        raise ReconcileUsageError("账务 normalized.json 不存在：%s" % normalized_path)
    normalized = read_json(normalized_path)
    source = normalized.get("source") or {}
    batch_dir = ROOT / "data/batches/task027r1_run_04/batch_normal"
    workbook = batch_dir / "source/input.xlsx"
    if not workbook.is_file():
        raise ReconcileUsageError("批次工作簿不存在：%s" % workbook)
    workbook_sha = sha_bytes(workbook.read_bytes())
    if source.get("input_sha256") != workbook_sha:
        raise ReconcileUsageError("账务 normalized 的 source.input_sha256 与本批次工作簿不一致")
    if normalized.get("mode") != "DEVELOPMENT_TEST_ONLY":
        raise ReconcileUsageError("账务 normalized 必须为 DEVELOPMENT_TEST_ONLY")
    started_path = normalized_path.parent / "started.json"
    if started_path.is_file():
        started = read_json(started_path)
        if started.get("batch_id") != EXPECTED_BATCH:
            raise ReconcileUsageError("账务 started.json 的 batch_id 与本批次不一致")
        if started.get("source_batch_relative") != rel(batch_dir):
            raise ReconcileUsageError("账务 started.json 的 source_batch_relative 与本批次不一致")
        binding_input = ((started.get("bindings") or {}).get("run_binding") or {}).get("input") or {}
        if binding_input.get("file_sha256") != workbook_sha:
            raise ReconcileUsageError("账务 bindings.run_binding.input 与本批次工作簿不一致")
    artifacts_path = normalized_path.parent / "artifacts.json"
    if artifacts_path.is_file():
        artifacts = read_json(artifacts_path)
        if artifacts.get("normalized_file_sha256") != sha_bytes(normalized_path.read_bytes()):
            raise ReconcileUsageError("账务 artifacts 的 normalized_file_sha256 不一致")
        if artifacts.get("batch_id") != EXPECTED_BATCH:
            raise ReconcileUsageError("账务 artifacts 的 batch_id 与本批次不一致")
    tables = normalized["tables"]

    def rows(name):
        return [item["data"] for item in tables[name]["records"]]

    payments = [row for row in rows("payments")
                if row.get("transaction_type") in ("PAY", "REFUND")]
    suppliers = {row["supplier_id"]: row["supplier_name"] for row in rows("suppliers")}
    allocations = rows("allocations")
    for row in payments:
        if not in_period(row.get("payment_date")):
            raise ReconcileUsageError("账务日期不在期间内：%s" % row.get("payment_id"))
    return {"identity": identity(normalized_path),
            "started_identity": identity(started_path) if started_path.is_file() else None,
            "artifacts_identity": identity(artifacts_path) if artifacts_path.is_file() else None,
            "batch_relative": rel(batch_dir), "batch_id": EXPECTED_BATCH,
            "workbook_sha256": workbook_sha, "payments": payments,
            "suppliers": suppliers, "allocations": allocations}


class Reconcile:
    def __init__(self):
        self.matched = []
        self.differences = []
        self.ledger_unmatched = []
        self.bank_unmatched = []
        self.duplicates = []

    def add_difference(self, ledger_id, txn_id, field, actual, expected, classification):
        if classification not in PRIORITY or classification == "MATCHED":
            raise ReconcileUsageError("非法差异分类：%r" % classification)
        self.differences.append({"ledger_id": ledger_id, "bank_txn_id": txn_id,
                                 "field": field, "actual": actual,
                                 "expected": expected, "classification": classification})


def category_of(record) -> str:
    return "PAYMENT" if record.get("transaction_type") == "PAY" else "REFUND"


def expected_direction(record) -> str:
    return "OUT" if record.get("transaction_type") == "PAY" else "IN"


def run(input_root: Path, normalized_path: Path, out_dir: Path) -> int:
    if out_dir.exists():
        raise ReconcileUsageError("--out 必须从未存在：%s" % out_dir)
    try:
        out_dir.resolve().relative_to(EVIDENCE_ROOT.resolve())
    except ValueError:
        raise ReconcileUsageError("--out 必须位于 %s 之下" % EVIDENCE_ROOT)
    if not out_dir.name.startswith("task045_"):
        raise ReconcileUsageError("--out 目录名必须以 task045_ 开头")
    input_data = load_input(input_root)
    ledger = load_ledger(normalized_path)
    txns = [txn for txn in input_data["txns"] if type(txn) is dict]
    txn_by_id = {}
    duplicates_ids = set()
    for txn in txns:
        txn_id = txn.get("bank_txn_id")
        if is_text(txn_id):
            if txn_id in txn_by_id:
                duplicates_ids.add(txn_id)
            txn_by_id.setdefault(txn_id, txn)
    records = sorted(ledger["payments"], key=lambda row: row.get("payment_id") or "")
    suppliers = ledger["suppliers"]
    state = Reconcile()
    used_txns = {}
    matched_records = {}

    def candidate_txns(record):
        payment_id = record["payment_id"]
        candidates = {}
        for txn_id in input_data["index_declared"].get(payment_id, []):
            txn = txn_by_id.get(txn_id)
            if txn is not None:
                candidates[txn_id] = ("REFERENCE_INDEX", txn)
        bank_reference = record.get("bank_reference")
        if is_text(bank_reference):
            for txn in txns:
                txn_id = txn.get("bank_txn_id")
                if txn.get("reference") == bank_reference or txn_id == bank_reference:
                    candidates.setdefault(txn_id, ("REFERENCE_BANK_REFERENCE", txn))
        return candidates

    def match(record, txn, basis):
        used_txns[txn["bank_txn_id"]] = record["payment_id"]
        matched_records[record["payment_id"]] = txn["bank_txn_id"]
        state.matched.append({"ledger_id": record["payment_id"],
                              "ledger_type": category_of(record),
                              "bank_txn_id": txn["bank_txn_id"], "basis": basis})

    for record in records:
        if record["payment_id"] in matched_records:
            continue
        candidates = candidate_txns(record)
        distinct = sorted(candidates)
        if len(distinct) > 1:
            used = [txn_id for txn_id in distinct if txn_id in used_txns
                    and used_txns[txn_id] != record["payment_id"]]
            if used:
                state.add_difference(record["payment_id"], used[0], "bank_reference",
                                     used[0], "唯一未占用流水", "DUPLICATE_MATCH")
                state.duplicates.append({"ledger_id": record["payment_id"],
                                         "bank_txn_id": used[0],
                                         "classification": "DUPLICATE_MATCH"})
                continue
            state.add_difference(record["payment_id"], distinct[0], "bank_reference",
                                 distinct, "唯一引用", "REFERENCE_CONFLICT")
            continue
        if not distinct:
            continue
        txn_id = distinct[0]
        txn = candidates[txn_id][1]
        if txn_id in used_txns:
            state.add_difference(record["payment_id"], txn_id, "bank_reference",
                                 txn_id, "唯一未占用流水", "DUPLICATE_MATCH")
            state.duplicates.append({"ledger_id": record["payment_id"],
                                     "bank_txn_id": txn_id,
                                     "classification": "DUPLICATE_MATCH"})
            continue
        match(record, txn, candidates[txn_id][0])

    # 无引用：三元组（金额整数分 + 日期 + 对方户名），仅在未匹配双方之间做，要求唯一
    triple_index = {}
    for txn in txns:
        if txn.get("bank_txn_id") in used_txns:
            continue
        key = (txn.get("amount_cents"), txn.get("txn_date"), txn.get("counterparty_name"))
        triple_index.setdefault(key, []).append(txn)
    for record in records:
        if record["payment_id"] in matched_records:
            continue
        supplier_name = suppliers.get(record.get("payee_supplier_id"))
        key = (record.get("amount_cents"), record.get("payment_date"), supplier_name)
        candidates = [txn for txn in triple_index.get(key, [])
                      if txn.get("bank_txn_id") not in used_txns]
        if not candidates:
            continue
        if len(candidates) > 1:
            for txn in candidates:
                state.add_difference(record["payment_id"], txn.get("bank_txn_id"),
                                     "amount_cents/date/counterparty", key, "唯一三元组",
                                     "DUPLICATE_BANK_LINE")
                state.duplicates.append({"ledger_id": record["payment_id"],
                                         "bank_txn_id": txn.get("bank_txn_id"),
                                         "classification": "DUPLICATE_BANK_LINE"})
            continue
        match(record, candidates[0], "TRIPLE")

    # 字段核对（匹配对）
    for record in records:
        txn_id = matched_records.get(record["payment_id"])
        if txn_id is None:
            continue
        txn = txn_by_id[txn_id]
        used_txns[txn_id] = record["payment_id"]
        ledger_id = record["payment_id"]
        if txn.get("amount_cents") != record.get("amount_cents"):
            state.add_difference(ledger_id, txn_id, "amount_cents",
                                 txn.get("amount_cents"), record.get("amount_cents"),
                                 "AMOUNT_MISMATCH")
        if txn.get("txn_date") != record.get("payment_date"):
            state.add_difference(ledger_id, txn_id, "txn_date",
                                 txn.get("txn_date"), record.get("payment_date"),
                                 "DATE_MISMATCH")
        if not in_period(txn.get("txn_date")):
            state.add_difference(ledger_id, txn_id, "txn_date_period",
                                 txn.get("txn_date"), "<= " + CUTOFF, "DATE_MISMATCH")
        if txn.get("direction") != expected_direction(record):
            state.add_difference(ledger_id, txn_id, "direction",
                                 txn.get("direction"), expected_direction(record),
                                 "DIRECTION_MISMATCH")
        supplier_name = suppliers.get(record.get("payee_supplier_id"))
        if supplier_name is not None and txn.get("counterparty_name") != supplier_name:
            state.add_difference(ledger_id, txn_id, "counterparty_name",
                                 txn.get("counterparty_name"), supplier_name,
                                 "COUNTERPARTY_MISMATCH")
        reference = txn.get("reference")
        if is_text(reference) and reference not in (ledger_id,
                                                    record.get("bank_reference")):
            state.add_difference(ledger_id, txn_id, "reference", reference,
                                 ledger_id, "REFERENCE_CONFLICT")
        if txn_id in duplicates_ids:
            state.add_difference(ledger_id, txn_id, "bank_txn_id", txn_id,
                                 "唯一 bank_txn_id", "DUPLICATE_BANK_LINE")

    for record in records:
        if record["payment_id"] not in matched_records:
            state.ledger_unmatched.append({"ledger_id": record["payment_id"],
                                           "ledger_type": category_of(record),
                                           "amount_cents": record.get("amount_cents"),
                                           "payment_date": record.get("payment_date"),
                                           "classification": "LEDGER_UNMATCHED"})
    for txn in txns:
        txn_id = txn.get("bank_txn_id")
        if txn_id in matched_records.values():
            continue
        state.bank_unmatched.append({"bank_txn_id": txn_id,
                                     "txn_date": txn.get("txn_date"),
                                     "direction": txn.get("direction"),
                                     "amount_cents": txn.get("amount_cents"),
                                     "counterparty_name": txn.get("counterparty_name"),
                                     "reference": txn.get("reference"),
                                     "classification": "BANK_UNMATCHED"})
    out_sum = sum(txn.get("amount_cents") for txn in txns
                  if txn.get("direction") == "OUT" and is_int(txn.get("amount_cents")))
    in_sum = sum(txn.get("amount_cents") for txn in txns
                 if txn.get("direction") == "IN" and is_int(txn.get("amount_cents")))
    settled_pay = sum(record.get("amount_cents") for record in records
                      if record.get("transaction_type") == "PAY"
                      and record.get("settlement_status") == "SETTLED"
                      and is_int(record.get("amount_cents")))
    refund_total = sum(record.get("amount_cents") for record in records
                       if record.get("transaction_type") == "REFUND"
                       and is_int(record.get("amount_cents")))
    allocations_by_payment = {}
    for allocation in ledger["allocations"]:
        allocations_by_payment.setdefault(allocation.get("payment_id"), []).append(
            allocation.get("allocated_amount_cents"))
    cash_note = []
    for record in records:
        payment_id = record["payment_id"]
        cash_note.append({"ledger_id": payment_id,
                          "whole_payment_cents": record.get("amount_cents"),
                          "allocations": allocations_by_payment.get(payment_id, []),
                          "note": "整笔付款金额为资金口径，与分摊金额分别列示，不相加"})
    matched_count = len(state.matched)
    differences_total = len(state.differences) + len(state.ledger_unmatched) \
        + len(state.bank_unmatched)
    total_ok = out_sum == settled_pay and in_sum == refund_total
    report = {
        "report_version": REPORT_VERSION,
        "generated_by": "scripts/bank_reconcile_v1.py",
        "input": {"root": rel(input_root),
                  "input_version": input_data["manifest"].get("input_version"),
                  "manifest": input_data["manifest_identity"],
                  "entity": input_data["manifest"].get("entity")},
        "ledger": {"normalized": ledger["identity"],
                   "started": ledger["started_identity"],
                   "artifacts": ledger["artifacts_identity"],
                   "batch_relative": ledger["batch_relative"],
                   "batch_id": ledger["batch_id"],
                   "workbook_sha256": ledger["workbook_sha256"],
                   "bindings_checked": {"batch_id": True,
                                        "source_batch_relative": True,
                                        "run_binding_input": True,
                                        "normalized_file_sha256": True,
                                        "mode": "DEVELOPMENT_TEST_ONLY"}},
        "matched": state.matched,
        "differences": state.differences,
        "duplicates": state.duplicates,
        "unmatched": {"ledger_unmatched": state.ledger_unmatched,
                      "bank_unmatched": state.bank_unmatched,
                      "note": "未达账项≠差错，需人类核查；两侧分列，不强行配对。"},
        "period_totals": {"out_total_cents": out_sum,
                          "settled_payments_total_cents": settled_pay,
                          "out_difference_cents": out_sum - settled_pay,
                          "in_total_cents": in_sum,
                          "refunds_total_cents": refund_total,
                          "in_difference_cents": in_sum - refund_total,
                          "balances": {"status": "not_provided",
                                       "note": "流水未提供期初/期末余额，无法做余额算术自洽，更不与账面存款科目比较"}},
        "cash_fund_note": cash_note,
        "summary": {"ledger_records": len(records), "bank_transactions": len(txns),
                    "matched": matched_count,
                    "differences": len(state.differences),
                    "ledger_unmatched": len(state.ledger_unmatched),
                    "bank_unmatched": len(state.bank_unmatched),
                    "duplicates": len(state.duplicates),
                    "classification_counts": _counts(state)},
        "conclusion": ("ALL_MATCHED" if differences_total == 0 and total_ok
                       else "DIFFERENCES_FOUND"),
        "verification_level": "TRANSACTION_LEVEL_L1_PLUS_PERIOD_TOTALS",
        "human_conclusion": None,
        "human_conclusion_note": "人类核对结论未采集、不虚构；需另行授权与登记。",
        "boundaries": dict(BOUNDARIES),
        "note": ("交易级 L1 + 期间合计；未做银行对账单格式适配、未看回单影像、未函证、"
                 "未做银行余额核对（需报表层输入另行授权）；未达账项≠差错，需人类核查；"
                 "本结果不证明来源真实，不构成审计证据或结论。"),
    }
    out_dir.mkdir(parents=True, exist_ok=False)
    payload = json.dumps(report, ensure_ascii=False, indent=2,
                         sort_keys=True).encode("utf-8") + b"\n"
    (out_dir / "bank_reconcile_report.json").write_bytes(payload)
    if (out_dir / "bank_reconcile_report.json").read_bytes() != payload:
        raise ReconcileUsageError("报告写后读回不一致")
    (out_dir / "bank_reconcile_report.md").write_bytes(
        render_markdown(report).encode("utf-8"))
    return 0 if report["conclusion"] == "ALL_MATCHED" else 1


def _counts(state):
    counts = {name: 0 for name in CLASSES}
    counts["MATCHED"] = len(state.matched)
    for difference in state.differences:
        counts[difference["classification"]] += 1
    counts["LEDGER_UNMATCHED"] = len(state.ledger_unmatched)
    counts["BANK_UNMATCHED"] = len(state.bank_unmatched)
    counts["DUPLICATE_MATCH"] = sum(
        1 for item in state.duplicates if item["classification"] == "DUPLICATE_MATCH")
    counts["DUPLICATE_BANK_LINE"] = sum(
        1 for item in state.duplicates
        if item["classification"] == "DUPLICATE_BANK_LINE")
    return counts


def render_markdown(report):
    summary = report["summary"]
    totals = report["period_totals"]
    lines = ["# 账实相符（银行流水交易级）核对报告（合成）", "",
             "> 交易级 L1 + 期间合计；未做银行对账单格式适配、未看回单影像、未函证、"
             "未做银行余额核对；未达账项≠差错，需人类核查。", "",
             "## 输入与账务身份", "",
             "- 输入根：`%s`（input_version=%s）" % (
                 report["input"]["root"], report["input"]["input_version"]),
             "- 输入清单：%s（%d B / `%s`）" % (
                 report["input"]["manifest"]["relative"],
                 report["input"]["manifest"]["byte_size"],
                 report["input"]["manifest"]["sha256"][:16]),
             "- 账务 normalized：`%s`（%d B / `%s`）" % (
                 report["ledger"]["normalized"]["relative"],
                 report["ledger"]["normalized"]["byte_size"],
                 report["ledger"]["normalized"]["sha256"][:16]),
             "- 批次：`%s`；绑定核对：batch_id / source_batch_relative / "
             "run_binding.input / normalized_file_sha256 / mode" % report["ledger"]["batch_id"],
             "", "## 汇总", "",
             "- 账务记录 %d 条、银行流水 %d 条；匹配 %d 条；差异 %d；账有实无 %d；实有账无 %d；重复 %d" % (
                 summary["ledger_records"], summary["bank_transactions"],
                 summary["matched"], summary["differences"],
                 summary["ledger_unmatched"], summary["bank_unmatched"],
                 summary["duplicates"]),
             "- 期间合计：OUT %d 分 vs 已结算付款 %d 分（差 %d）；IN %d 分 vs 退款 %d 分（差 %d）" % (
                 totals["out_total_cents"], totals["settled_payments_total_cents"],
                 totals["out_difference_cents"], totals["in_total_cents"],
                 totals["refunds_total_cents"], totals["in_difference_cents"]),
             "- 余额：%s（%s）" % (totals["balances"]["status"], totals["balances"]["note"]),
             "- 结论：`%s`" % report["conclusion"], "",
             "## 逐条匹配", "",
             "| 账务ID | 类型 | 流水ID | 依据 |", "| --- | --- | --- | --- |"]
    for item in report["matched"]:
        lines.append("| %s | %s | %s | %s |" % (item["ledger_id"], item["ledger_type"],
                                               item["bank_txn_id"], item["basis"]))
    lines += ["", "## 差异清单", ""]
    if report["differences"]:
        lines += ["| 账务ID | 流水ID | 字段 | 实际 | 预期 | 分类 |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for difference in report["differences"]:
            lines.append("| %s | %s | %s | %s | %s | %s |" % (
                difference["ledger_id"], difference["bank_txn_id"],
                difference["field"],
                json.dumps(difference["actual"], ensure_ascii=False),
                json.dumps(difference["expected"], ensure_ascii=False),
                difference["classification"]))
    else:
        lines.append("（无）")
    lines += ["", "## 未达账项（两侧分列，≠差错）", "",
              "账有实无：%d" % len(report["unmatched"]["ledger_unmatched"])]
    for item in report["unmatched"]["ledger_unmatched"]:
        lines.append("  - %s（%s）：%d 分 / %s" % (
            item["ledger_id"], item["ledger_type"], item["amount_cents"],
            item["payment_date"]))
    lines.append("实有账无：%d" % len(report["unmatched"]["bank_unmatched"]))
    for item in report["unmatched"]["bank_unmatched"]:
        lines.append("  - %s：%s / %s / %d 分 / %s" % (
            item["bank_txn_id"], item["direction"], item["txn_date"],
            item["amount_cents"], item["counterparty_name"]))
    lines += ["", "> %s" % report["unmatched"]["note"], "",
              "## 现金/资金口径提示", ""]
    for item in report["cash_fund_note"]:
        lines.append("- %s：整笔 %s 分；分摊 %s；%s" % (
            item["ledger_id"], item["whole_payment_cents"],
            item["allocations"], item["note"]))
    lines += ["", "## 人类核对结论", "",
              "- 留空：%s" % report["human_conclusion_note"], "",
              "## 边界", "",
              "- 合成数据；`real_approval=null`、真实独立初判未保存、`next_step_allowed=false`、"
              "`ai_enabled=false`。",
              "- %s" % report["note"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-045 账实相符（银行流水交易级勾对）")
    parser.add_argument("--input", required=True)
    parser.add_argument("--ledger-normalized", dest="ledger_normalized", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        out_dir = Path(args.out)
        code = run(Path(args.input), Path(args.ledger_normalized), out_dir)
        report = read_json(out_dir / "bank_reconcile_report.json")
        print(json.dumps({"status": report["conclusion"],
                          "matched": report["summary"]["matched"],
                          "differences": report["summary"]["differences"],
                          "ledger_unmatched": report["summary"]["ledger_unmatched"],
                          "bank_unmatched": report["summary"]["bank_unmatched"],
                          "period_totals": report["period_totals"],
                          "out": str(out_dir)}, ensure_ascii=False))
        return code
    except ReconcileUsageError as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
