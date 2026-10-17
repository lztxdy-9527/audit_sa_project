#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-055：GL v1 输入契约校验（只读，仅标准库）。

用法：
    python -B scripts/gl_input_contract_v1.py --gl-root data/evidence_inputs/gl_v1

退出码：0 通过；1 内容不合法（输出 {code, field, expected, actual}）；2 参数/路径错误。
校验：文件齐全与哈希、版本/期间/批次绑定、科目引用、金额整数分、借贷恰一非零、
逐张与期间借贷相等、余额表两两相等与逐科目等式、总账/明细账与凭证一致、报表平衡与
应付借方重分类、银行对账与日记账一致、附件存在且类型匹配。任一项不符即失败，不修复、不兜底。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BATCH = ROOT / "data/batches/task027r1_run_04/batch_normal/batch_manifest.json"
FILES = ("chart_of_accounts.json", "journal_entries.json", "trial_balance.json",
         "ledger_general.json", "ledger_subsidiary.json", "balance_sheet.json",
         "bank_statement.json", "bank_journal.json", "attachment_index.json")
ACCOUNT_TYPES = ("ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE")
DIRECTIONS = ("DEBIT", "CREDIT")
ATTACHMENT_TYPES = ("INVOICE", "CONTRACT", "GOODS_RECEIPT", "APPROVAL", "BANK_RECEIPT")


class ContractError(Exception):
    def __init__(self, code, field, message, expected=None, actual=None):
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message
        self.expected = expected
        self.actual = actual


def is_int(value):
    return type(value) is int


def load_json(path: Path, field):
    try:
        return json.loads(path.read_bytes())
    except (ValueError, OSError) as exc:
        raise ContractError("GL-JSON", field, "JSON 不可解析：%s" % exc,
                            "合法 JSON", str(exc))


def check_manifest(gl_root, manifest, batch_path):
    if manifest.get("version") != "gl-1.0":
        raise ContractError("GL-VERSION", "gl_manifest.version",
                            "版本不受支持", "gl-1.0", manifest.get("version"))
    period = manifest.get("period") or {}
    for key in ("period_start", "period_end", "cutoff_date"):
        if not isinstance(period.get(key), str):
            raise ContractError("GL-PERIOD", "gl_manifest.period.%s" % key, "期间字段缺失",
                                "ISO 日期", period.get(key))
    if not (period["period_start"] <= period["cutoff_date"] <= period["period_end"]):
        raise ContractError("GL-PERIOD", "gl_manifest.period", "截止日不在期间内",
                            "period_start ≤ cutoff ≤ period_end", period)
    batch = manifest.get("batch") or {}
    if batch.get("batch_id") != "task027r1_run_04":
        raise ContractError("GL-BATCH", "gl_manifest.batch.batch_id", "批次不一致",
                            "task027r1_run_04", batch.get("batch_id"))
    actual_batch_sha = hashlib.sha256(batch_path.read_bytes()).hexdigest()
    if batch.get("batch_manifest_sha256") != actual_batch_sha:
        raise ContractError("GL-BATCH", "gl_manifest.batch.batch_manifest_sha256",
                            "批次清单哈希不一致", actual_batch_sha,
                            batch.get("batch_manifest_sha256"))
    files = manifest.get("files") or {}
    for name in FILES:
        path = gl_root / name
        if not path.is_file():
            raise ContractError("GL-FILE-MISSING", "files.%s" % name, "文件缺失", "存在", "缺失")
        entry = files.get(name)
        if not isinstance(entry, dict):
            raise ContractError("GL-MANIFEST-SIZE", "gl_manifest.files.%s" % name,
                                "清单条目缺失", "长度/SHA", entry)
        raw = path.read_bytes()
        if entry.get("byte_size") != len(raw):
            raise ContractError("GL-MANIFEST-SIZE", "gl_manifest.files.%s.byte_size" % name,
                                "清单长度不符", len(raw), entry.get("byte_size"))
        if entry.get("sha256") != hashlib.sha256(raw).hexdigest():
            raise ContractError("GL-MANIFEST-SHA", "gl_manifest.files.%s.sha256" % name,
                                "清单哈希不符", hashlib.sha256(raw).hexdigest(),
                                entry.get("sha256"))


def check_accounts(chart):
    accounts = chart.get("accounts")
    if type(accounts) is not list or not accounts:
        raise ContractError("GL-ACCOUNT-UNKNOWN", "chart_of_accounts.accounts",
                            "科目表为空", "非空数组", accounts)
    by_code = {}
    for account in accounts:
        code = account.get("code")
        if not isinstance(code, str) or not code:
            raise ContractError("GL-ACCOUNT-UNKNOWN", "chart_of_accounts.accounts.code",
                                "科目编码非法", "非空字符串", code)
        if account.get("type") not in ACCOUNT_TYPES:
            raise ContractError("GL-ACCOUNT-UNKNOWN", "chart_of_accounts.accounts.%s.type" % code,
                                "科目类型非法", ACCOUNT_TYPES, account.get("type"))
        if account.get("direction") not in DIRECTIONS:
            raise ContractError("GL-ACCOUNT-UNKNOWN",
                                "chart_of_accounts.accounts.%s.direction" % code,
                                "科目方向非法", DIRECTIONS, account.get("direction"))
        if code in by_code:
            raise ContractError("GL-ACCOUNT-UNKNOWN", "chart_of_accounts.accounts.%s" % code,
                                "科目重复", "唯一编码", code)
        by_code[code] = account
    return by_code


def check_journal(journal, accounts):
    entries = journal.get("entries")
    if type(entries) is not list or not entries:
        raise ContractError("GL-ENTRY-UNBALANCED", "journal_entries.entries",
                            "凭证为空", "非空数组", entries)
    totals = {}
    for entry in entries:
        entry_id = entry.get("entry_id")
        lines = entry.get("lines")
        if type(lines) is not list or not lines:
            raise ContractError("GL-ENTRY-UNBALANCED", "journal_entries.%s.lines" % entry_id,
                                "分录为空", "非空数组", lines)
        entry_debit = entry_credit = 0
        for index, row in enumerate(lines):
            field = "journal_entries.%s.lines[%d]" % (entry_id, index)
            account = row.get("account")
            if account not in accounts:
                raise ContractError("GL-ACCOUNT-UNKNOWN", field + ".account",
                                    "未知科目", sorted(accounts), account)
            debit = row.get("debit_cents")
            credit = row.get("credit_cents")
            if not is_int(debit) or not is_int(credit):
                raise ContractError("GL-AMOUNT-TYPE", field, "金额必须是整数分",
                                    "int", [type(debit).__name__, type(credit).__name__])
            if debit < 0 or credit < 0:
                raise ContractError("GL-AMOUNT-TYPE", field, "金额不得为负", "≥0",
                                    [debit, credit])
            if (debit > 0) == (credit > 0):
                raise ContractError("GL-DEBIT-CREDIT", field,
                                    "借方/贷方必须恰一个大于零",
                                    "恰一非零", {"debit": debit, "credit": credit})
            entry_debit += debit
            entry_credit += credit
            bucket = totals.setdefault(account, {"debit": 0, "credit": 0})
            bucket["debit"] += debit
            bucket["credit"] += credit
        if entry_debit != entry_credit:
            raise ContractError("GL-ENTRY-UNBALANCED", "journal_entries.%s" % entry_id,
                                "凭证借贷不平", entry_debit, entry_credit)
    period_debit = sum(value["debit"] for value in totals.values())
    period_credit = sum(value["credit"] for value in totals.values())
    if period_debit != period_credit:
        raise ContractError("GL-PERIOD-UNBALANCED", "journal_entries",
                            "期间借贷合计不等", period_debit, period_credit)
    return totals


def signed(row, debit_key, credit_key):
    return row.get(debit_key) - row.get(credit_key)


def check_trial_balance(tb, accounts):
    rows = tb.get("rows")
    if type(rows) is not list:
        raise ContractError("GL-TB-EQUATION", "trial_balance.rows", "余额表行缺失",
                            "数组", rows)
    seen = set()
    total = {"opening_debit": 0, "opening_credit": 0, "debit_cents": 0,
             "credit_cents": 0, "closing_debit": 0, "closing_credit": 0}
    for row in rows:
        account = row.get("account")
        if account not in accounts:
            raise ContractError("GL-ACCOUNT-UNKNOWN", "trial_balance.rows.account",
                                "未知科目", sorted(accounts), account)
        seen.add(account)
        for key in total:
            if not is_int(row.get(key)):
                raise ContractError("GL-AMOUNT-TYPE", "trial_balance.rows.%s.%s" % (account, key),
                                    "金额必须是整数分", "int", row.get(key))
            total[key] += row[key]
        opening = signed(row, "opening_debit", "opening_credit")
        closing = signed(row, "closing_debit", "closing_credit")
        if opening + row["debit_cents"] - row["credit_cents"] != closing:
            raise ContractError("GL-TB-EQUATION", "trial_balance.rows.%s" % account,
                                "期初+借−贷≠期末", opening + row["debit_cents"] - row["credit_cents"],
                                closing)
        if row["closing_debit"] > 0 and row["closing_credit"] > 0:
            raise ContractError("GL-TB-CLOSING", "trial_balance.rows.%s" % account,
                                "期末不能同时有借/贷", "恰一方", row)
    if seen != set(accounts):
        raise ContractError("GL-TB-CLOSING", "trial_balance.rows",
                            "科目不全", sorted(accounts), sorted(seen))
    if total["opening_debit"] != total["opening_credit"]:
        raise ContractError("GL-TB-TOTALS", "trial_balance.totals.opening",
                            "期初借贷不等", total["opening_debit"], total["opening_credit"])
    if total["debit_cents"] != total["credit_cents"]:
        raise ContractError("GL-TB-TOTALS", "trial_balance.totals.period",
                            "本期借贷不等", total["debit_cents"], total["credit_cents"])
    if total["closing_debit"] != total["closing_credit"]:
        raise ContractError("GL-TB-TOTALS", "trial_balance.totals.closing",
                            "期末借贷不等", total["closing_debit"], total["closing_credit"])
    declared = tb.get("totals") or {}
    for key, value in total.items():
        if declared.get(key) != value:
            raise ContractError("GL-TB-TOTALS", "trial_balance.totals.%s" % key,
                                "合计与明细不符", value, declared.get(key))
    return {row["account"]: row for row in rows}


def check_general(general, accounts, vouchers, trial):
    rows = general.get("accounts")
    if type(rows) is not list:
        raise ContractError("GL-GL-AMOUNT", "ledger_general.accounts", "总账行缺失",
                            "数组", rows)
    by_account = {}
    for row in rows:
        account = row.get("account")
        if account not in accounts:
            raise ContractError("GL-ACCOUNT-UNKNOWN", "ledger_general.accounts.account",
                                "未知科目", sorted(accounts), account)
        by_account[account] = row
        expected = vouchers.get(account, {"debit": 0, "credit": 0})
        if row.get("debit_cents") != expected["debit"]:
            raise ContractError("GL-GL-AMOUNT", "ledger_general.accounts.%s.debit_cents" % account,
                                "总账借方发生额与凭证不符", expected["debit"], row.get("debit_cents"))
        if row.get("credit_cents") != expected["credit"]:
            raise ContractError("GL-GL-AMOUNT", "ledger_general.accounts.%s.credit_cents" % account,
                                "总账贷方发生额与凭证不符", expected["credit"], row.get("credit_cents"))
        trial_row = trial[account]
        if (row.get("closing_debit"), row.get("closing_credit")) != (
                trial_row.get("closing_debit"), trial_row.get("closing_credit")):
            raise ContractError("GL-GL-CLOSING", "ledger_general.accounts.%s" % account,
                                "总账期末与余额表不符",
                                [trial_row.get("closing_debit"), trial_row.get("closing_credit")],
                                [row.get("closing_debit"), row.get("closing_credit")])
    if set(by_account) != set(accounts):
        raise ContractError("GL-GL-CLOSING", "ledger_general.accounts",
                            "科目不全", sorted(accounts), sorted(by_account))
    return by_account


def check_subsidiary(subsidiary, accounts, general):
    subsidiaries = subsidiary.get("subsidiaries")
    if type(subsidiaries) is not list:
        raise ContractError("GL-SUB-TOTAL", "ledger_subsidiary.subsidiaries", "明细账缺失",
                            "数组", subsidiaries)
    totals = {}
    for item in subsidiaries:
        name = item.get("name")
        account = item.get("account")
        if account not in accounts:
            raise ContractError("GL-ACCOUNT-UNKNOWN", "ledger_subsidiary.%s.account" % name,
                                "未知科目", sorted(accounts), account)
        entries = item.get("entries") or []
        debit = sum(entry.get("debit_cents", 0) for entry in entries)
        credit = sum(entry.get("credit_cents", 0) for entry in entries)
        if debit != item.get("total_debit_cents") or credit != item.get("total_credit_cents"):
            raise ContractError("GL-SUB-TOTAL", "ledger_subsidiary.%s.totals" % name,
                                "明细合计与逐笔不符", [debit, credit],
                                [item.get("total_debit_cents"), item.get("total_credit_cents")])
        opening = item.get("opening_debit", 0) - item.get("opening_credit", 0)
        closing = opening + debit - credit
        declared = item.get("closing_debit", 0) - item.get("closing_credit", 0)
        if closing != declared:
            raise ContractError("GL-SUB-CLOSING", "ledger_subsidiary.%s.closing" % name,
                                "明细期末不等于期初+发生额", closing, declared)
        bucket = totals.setdefault(account, {"debit": 0, "credit": 0,
                                             "closing": 0})
        bucket["debit"] += debit
        bucket["credit"] += credit
        bucket["closing"] += declared
    for account, bucket in totals.items():
        row = general[account]
        if bucket["debit"] != row.get("debit_cents") or bucket["credit"] != row.get("credit_cents"):
            raise ContractError("GL-SUB-TOTAL", "ledger_subsidiary.%s.totals" % account,
                                "明细合计≠总账发生额",
                                [row.get("debit_cents"), row.get("credit_cents")],
                                [bucket["debit"], bucket["credit"]])
        declared = row.get("closing_debit", 0) - row.get("closing_credit", 0)
        if bucket["closing"] != declared:
            raise ContractError("GL-SUB-GL", "ledger_subsidiary.%s.closing" % account,
                                "明细期末≠总账期末", declared, bucket["closing"])


def check_balance_sheet(sheet, accounts, trial):
    assets = sheet.get("assets") or []
    liabilities = sheet.get("liabilities") or []
    equity = sheet.get("equity") or []
    total_assets = sum(item.get("amount_cents", 0) for item in assets)
    total_other = sum(item.get("amount_cents", 0) for item in liabilities) + \
        sum(item.get("amount_cents", 0) for item in equity)
    if total_assets != sheet.get("total_assets_cents"):
        raise ContractError("GL-BS-EQUATION", "balance_sheet.total_assets_cents",
                            "资产合计与明细不符", total_assets,
                            sheet.get("total_assets_cents"))
    if total_other != sheet.get("total_liabilities_equity_cents"):
        raise ContractError("GL-BS-EQUATION", "balance_sheet.total_liabilities_equity_cents",
                            "负债+权益与明细不符", total_other,
                            sheet.get("total_liabilities_equity_cents"))
    if total_assets != total_other:
        raise ContractError("GL-BS-EQUATION", "balance_sheet",
                            "资产≠负债+权益", total_assets, total_other)
    ap = trial.get("2202") or {}
    ap_signed = ap.get("closing_debit", 0) - ap.get("closing_credit", 0)
    expected_ap = max(0, -ap_signed)
    expected_prepaid = max(0, ap_signed)
    actual_ap = next((item.get("amount_cents") for item in liabilities
                      if item.get("item") == "应付账款"), None)
    actual_prepaid = next((item.get("amount_cents") for item in assets
                           if item.get("item") == "预付账款"), None)
    if actual_ap != expected_ap or actual_prepaid != expected_prepaid:
        raise ContractError("GL-BS-RECLASS", "balance_sheet",
                            "应付借方余额未正确重分类为预付",
                            {"应付": expected_ap, "预付": expected_prepaid},
                            {"应付": actual_ap, "预付": actual_prepaid})


def check_bank(statement, journal, attachments, journal_entries):
    opening = statement.get("opening_balance_cents")
    entries = statement.get("entries") or []
    inflow = sum(item.get("amount_cents", 0) for item in entries
                 if item.get("direction") == "IN")
    outflow = sum(item.get("amount_cents", 0) for item in entries
                  if item.get("direction") == "OUT")
    computed = opening + inflow - outflow
    if computed != statement.get("closing_balance_cents"):
        raise ContractError("GL-BANK-END", "bank_statement.closing_balance_cents",
                            "对账单期末≠期初+收入−支出", computed,
                            statement.get("closing_balance_cents"))
    bank_entries = journal.get("entries") or []
    if bank_entries != entries:
        raise ContractError("GL-BANK-JOURNAL", "bank_journal.entries",
                            "日记账与对账单三笔不一致", entries, bank_entries)
    if journal.get("opening_balance_cents") != opening \
            or journal.get("closing_balance_cents") != statement.get("closing_balance_cents"):
        raise ContractError("GL-BANK-JOURNAL", "bank_journal",
                            "日记账期初/期末与对账单不符",
                            [opening, statement.get("closing_balance_cents")],
                            [journal.get("opening_balance_cents"),
                             journal.get("closing_balance_cents")])
    index = {item.get("voucher_id"): item for item in attachments.get("attachments") or []}
    required = {"记-001": {"INVOICE", "CONTRACT", "GOODS_RECEIPT"},
                "记-002": {"APPROVAL", "BANK_RECEIPT"},
                "记-003": {"APPROVAL", "BANK_RECEIPT"},
                "记-004": {"BANK_RECEIPT"}}
    journal_entries_by_id = {item.get("entry_id"): item for item in journal_entries}
    for entry_id, types in required.items():
        entry = journal_entries_by_id.get(entry_id)
        if entry is None:
            continue
        amount = sum(line.get("debit_cents", 0) for line in entry.get("lines") or [])
        seen = set()
        for voucher_id in entry.get("attachments") or []:
            item = index.get(voucher_id)
            if item is None:
                raise ContractError("GL-ATTACH-MISSING", "journal_entries.%s.attachments" % entry_id,
                                    "附件不存在", voucher_id, "缺失")
            if item.get("voucher_type") not in ATTACHMENT_TYPES:
                raise ContractError("GL-ATTACH-TYPE", "attachment_index.%s.voucher_type" % voucher_id,
                                    "附件类型非法", ATTACHMENT_TYPES, item.get("voucher_type"))
            if item.get("amount_cents") != amount:
                raise ContractError("GL-ATTACH-AMOUNT", "attachment_index.%s.amount_cents" % voucher_id,
                                    "附件金额与凭证金额不符", amount, item.get("amount_cents"))
            seen.add(item.get("voucher_type"))
        if not types <= seen:
            raise ContractError("GL-ATTACH-TYPE", "journal_entries.%s.attachments" % entry_id,
                                "附件类型不匹配", sorted(types), sorted(seen))


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-055 GL v1 契约校验")
    parser.add_argument("--gl-root", dest="gl_root", required=True)
    parser.add_argument("--batch", default=str(DEFAULT_BATCH))
    args = parser.parse_args(argv)
    gl_root = Path(args.gl_root)
    if not gl_root.is_absolute():
        gl_root = (Path.cwd() / gl_root).resolve()
    batch_path = Path(args.batch)
    try:
        if not gl_root.is_dir():
            raise ContractError("GL-PATH", "gl_root", "输入根不存在", "目录", str(gl_root))
        if not batch_path.is_file():
            raise ContractError("GL-PATH", "batch", "批次清单不存在", "文件", str(batch_path))
        manifest = load_json(gl_root / "gl_manifest.json", "gl_manifest")
        check_manifest(gl_root, manifest, batch_path)
        documents = {name: load_json(gl_root / name, "files.%s" % name) for name in FILES}
        for name, document in documents.items():
            if document.get("version") != "gl-1.0":
                raise ContractError("GL-VERSION", "files.%s.version" % name,
                                    "文件版本不受支持", "gl-1.0", document.get("version"))
        accounts = check_accounts(documents["chart_of_accounts.json"])
        vouchers = check_journal(documents["journal_entries.json"], accounts)
        trial = check_trial_balance(documents["trial_balance.json"], accounts)
        general = check_general(documents["ledger_general.json"], accounts, vouchers, trial)
        check_subsidiary(documents["ledger_subsidiary.json"], accounts, general)
        check_balance_sheet(documents["balance_sheet.json"], accounts, trial)
        check_bank(documents["bank_statement.json"], documents["bank_journal.json"],
                   documents["attachment_index.json"],
                   documents["journal_entries.json"].get("entries") or [])
        print(json.dumps({"status": "PASS", "gl_root": str(gl_root),
                          "version": manifest.get("version"),
                          "checks": ["files", "manifest_hashes", "accounts", "journal",
                                     "trial_balance", "ledger_general", "ledger_subsidiary",
                                     "balance_sheet", "bank", "attachments"]},
                         ensure_ascii=False))
        return 0
    except ContractError as exc:
        payload = {"status": "ERROR", "code": exc.code, "field": exc.field,
                   "error": exc.message, "expected": exc.expected, "actual": exc.actual}
        print(json.dumps(payload, ensure_ascii=False, default=str))
        return 1 if exc.code != "GL-PATH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
