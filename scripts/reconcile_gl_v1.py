#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-056：借贷记账法六类核对引擎（只读 GL v1，输出核对与差异报告，不做审计结论）。

用法：
    python -B scripts/reconcile_gl_v1.py --gl-root data/evidence_inputs/gl_v1 \
        --out-dir data/runtime_initial_judgment_recording_tests/task056_gl_01

六类：凭证平衡、试算平衡、账证、账账、账表、账实（银行）；另附附件核对（第 7 项附加）。
输出：gl_reconcile_report.json / .md、reconcile_source.json。退出码 0 全部 MATCHED；
1 存在 DIFFERENCES_FOUND / INCOMPLETE；2 参数/路径错误。只写 --out-dir，不写 GL 包与既有输入。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
VERSION = "TASK-056-gl-reconcile-1.1"
CHECK_TITLES = {
    "journal_balance": "凭证平衡",
    "trial_balance": "试算平衡",
    "ledger_to_voucher": "账证核对",
    "general_to_subsidiary": "账账核对",
    "ledger_to_report": "账表核对",
    "bank_reconcile": "账实核对（银行）",
    "attachments": "附件核对（附加）",
}
UNPERFORMED = [
    "函证（银行/往来）",
    "监盘（存货）",
    "期后付款检查",
    "截止测试",
    "收入/成本截止与截止性分析",
    "关联方与舞弊专项程序",
]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_gl(gl_root: Path):
    names = ("chart_of_accounts.json", "journal_entries.json", "trial_balance.json",
             "ledger_general.json", "ledger_subsidiary.json", "balance_sheet.json",
             "bank_statement.json", "bank_journal.json", "attachment_index.json",
             "gl_manifest.json")
    documents = {}
    inputs = []
    for name in names:
        path = gl_root / name
        if not path.is_file():
            raise FileNotFoundError("缺少 GL 文件：%s" % name)
        raw = path.read_bytes()
        try:
            documents[name] = json.loads(raw)
        except ValueError as exc:
            raise ValueError("GL 文件不可解析：%s（%s）" % (name, exc))
        inputs.append({"name": name, "byte_size": len(raw), "sha256": sha_bytes(raw)})
    return documents, inputs


def status_of(findings):
    return "MATCHED" if not findings else "DIFFERENCES"


def check_journal(entries):
    findings = []
    debit_total = credit_total = 0
    for entry in entries:
        entry_id = entry.get("entry_id")
        debit = sum(line.get("debit_cents", 0) for line in entry.get("lines") or [])
        credit = sum(line.get("credit_cents", 0) for line in entry.get("lines") or [])
        debit_total += debit
        credit_total += credit
        if debit != credit:
            findings.append({"entry_id": entry_id, "debit_total": debit,
                             "credit_total": credit})
    if debit_total != credit_total:
        findings.append({"entry_id": None, "debit_total": debit_total,
                         "credit_total": credit_total})
    return {"id": "journal_balance", "title": CHECK_TITLES["journal_balance"],
            "status": status_of(findings), "findings": findings,
            "summary": {"entries": len(entries), "debit_total": debit_total,
                        "credit_total": credit_total}}


def check_trial(trial):
    findings = []
    rows = trial.get("rows") or []
    totals = {"opening_debit": 0, "opening_credit": 0, "debit": 0, "credit": 0,
              "closing_debit": 0, "closing_credit": 0}
    for row in rows:
        account = row.get("account")
        opening = row.get("opening_debit", 0) - row.get("opening_credit", 0)
        closing = row.get("closing_debit", 0) - row.get("closing_credit", 0)
        expected = opening + row.get("debit_cents", 0) - row.get("credit_cents", 0)
        if expected != closing:
            findings.append({"account_code": account, "expected": expected,
                             "actual": closing})
        totals["opening_debit"] += row.get("opening_debit", 0)
        totals["opening_credit"] += row.get("opening_credit", 0)
        totals["debit"] += row.get("debit_cents", 0)
        totals["credit"] += row.get("credit_cents", 0)
        totals["closing_debit"] += row.get("closing_debit", 0)
        totals["closing_credit"] += row.get("closing_credit", 0)
    pairs = (("opening_debit", "opening_credit"), ("debit", "credit"),
             ("closing_debit", "closing_credit"))
    for left, right in pairs:
        if totals[left] != totals[right]:
            findings.append({"account_code": "TOTAL", "expected": totals[left],
                             "actual": totals[right], "pair": [left, right]})
    return {"id": "trial_balance", "title": CHECK_TITLES["trial_balance"],
            "status": status_of(findings), "findings": findings,
            "summary": {"rows": len(rows), **{key: totals[key] for key in totals}}}


def check_ledger_to_voucher(general, subsidiary, entries, journal_map):
    findings = []
    vouchers = {}
    for entry in entries:
        for line in entry.get("lines") or []:
            bucket = vouchers.setdefault(line.get("account"), {"debit": 0, "credit": 0})
            bucket["debit"] += line.get("debit_cents", 0)
            bucket["credit"] += line.get("credit_cents", 0)
    for row in general.get("accounts") or []:
        account = row.get("account")
        expected = vouchers.get(account, {"debit": 0, "credit": 0})
        if row.get("debit_cents") != expected["debit"] or \
                row.get("credit_cents") != expected["credit"]:
            findings.append({"account_code": account,
                             "ledger_debit": row.get("debit_cents"),
                             "ledger_credit": row.get("credit_cents"),
                             "voucher_debit": expected["debit"],
                             "voucher_credit": expected["credit"]})
    for item in subsidiary.get("subsidiaries") or []:
        name = item.get("name")
        for row in item.get("entries") or []:
            entry_id = row.get("entry_id")
            entry = journal_map.get(entry_id)
            if entry is None:
                findings.append({"account_code": item.get("account"),
                                 "entry_id": entry_id, "expected": "存在凭证",
                                 "actual": "未找到凭证"})
            elif row.get("date") != entry.get("date"):
                findings.append({"account_code": item.get("account"),
                                 "entry_id": entry_id,
                                 "expected": entry.get("date"),
                                 "actual": row.get("date")})
    for item in subsidiary.get("subsidiaries") or []:
        account = item.get("account")
        expected = vouchers.get(account, {"debit": 0, "credit": 0})
        debit = sum(row.get("debit_cents", 0) for row in item.get("entries") or [])
        credit = sum(row.get("credit_cents", 0) for row in item.get("entries") or [])
        if debit != expected["debit"] or credit != expected["credit"]:
            findings.append({"account_code": account, "source": "subsidiary",
                             "ledger_debit": debit, "ledger_credit": credit,
                             "voucher_debit": expected["debit"],
                             "voucher_credit": expected["credit"]})
    return {"id": "ledger_to_voucher", "title": CHECK_TITLES["ledger_to_voucher"],
            "status": status_of(findings), "findings": findings,
            "summary": {"accounts": len(general.get("accounts") or []),
                        "subsidiary_rows": len({row.get("entry_id")
                                                for item in subsidiary.get("subsidiaries") or []
                                                for row in item.get("entries") or []})}}


def check_general_to_subsidiary(general, subsidiary, trial):
    findings = []
    trial_rows = {row.get("account"): row for row in trial.get("rows") or []}
    for row in general.get("accounts") or []:
        account = row.get("account")
        trial_row = trial_rows.get(account) or {}
        general_signed = row.get("closing_debit", 0) - row.get("closing_credit", 0)
        trial_signed = trial_row.get("closing_debit", 0) - trial_row.get("closing_credit", 0)
        if general_signed != trial_signed:
            findings.append({"account_code": account,
                             "general_closing": general_signed,
                             "trial_closing": trial_signed})
    subsidiary_totals = {}
    for item in subsidiary.get("subsidiaries") or []:
        account = item.get("account")
        opening = item.get("opening_debit", 0) - item.get("opening_credit", 0)
        balance = opening
        for row in item.get("entries") or []:
            balance = balance + row.get("debit_cents", 0) - row.get("credit_cents", 0)
            declared = row.get("balance_debit", 0) - row.get("balance_credit", 0)
            if balance != declared:
                findings.append({"account_code": account,
                                 "entry_id": row.get("entry_id"),
                                 "expected": balance, "actual": declared})
        sub_closing = item.get("closing_debit", 0) - item.get("closing_credit", 0)
        bucket = subsidiary_totals.setdefault(account, 0)
        subsidiary_totals[account] = bucket + sub_closing
    for row in general.get("accounts") or []:
        account = row.get("account")
        if account not in subsidiary_totals:
            continue
        general_signed = row.get("closing_debit", 0) - row.get("closing_credit", 0)
        sub_signed = subsidiary_totals.get(account, 0)
        if general_signed != sub_signed:
            findings.append({"account_code": account, "general": general_signed,
                             "subsidiary": sub_signed})
    return {"id": "general_to_subsidiary",
            "title": CHECK_TITLES["general_to_subsidiary"],
            "status": status_of(findings), "findings": findings,
            "summary": {"accounts": len(general.get("accounts") or []),
                        "subsidiaries": len(subsidiary.get("subsidiaries") or [])}}


def check_ledger_to_report(trial, sheet):
    findings = []
    rows = {row.get("account"): row for row in trial.get("rows") or []}
    def signed(account):
        row = rows.get(account) or {}
        return row.get("closing_debit", 0) - row.get("closing_credit", 0)
    expected = {
        "货币资金": signed("1002"),
        "存货": signed("1001"),
        "预付账款": max(0, signed("2202")),
        "应付账款": max(0, -signed("2202")),
        "实收资本": max(0, -signed("3001")),
    }
    actual = {}
    for group in ("assets", "liabilities", "equity"):
        for item in sheet.get(group) or []:
            actual[item.get("item")] = item.get("amount_cents", 0)
    for item, value in expected.items():
        if actual.get(item) != value:
            findings.append({"report_item": item, "ledger_value": value,
                             "report_value": actual.get(item)})
    assets = sum(item.get("amount_cents", 0) for item in sheet.get("assets") or [])
    other = sum(item.get("amount_cents", 0) for item in sheet.get("liabilities") or []) + \
        sum(item.get("amount_cents", 0) for item in sheet.get("equity") or [])
    if assets != other:
        findings.append({"report_item": "asset_liability_equity",
                         "expected_total": assets, "actual_total": other})
    declared_assets = sheet.get("total_assets_cents")
    if declared_assets != assets:
        findings.append({"report_item": "total_assets_cents",
                         "expected_total": assets, "actual_total": declared_assets})
    declared_other = sheet.get("total_liabilities_equity_cents")
    if declared_other != other:
        findings.append({"report_item": "total_liabilities_equity_cents",
                         "expected_total": other, "actual_total": declared_other})
    return {"id": "ledger_to_report", "title": CHECK_TITLES["ledger_to_report"],
            "status": status_of(findings), "findings": findings,
            "summary": {"assets": assets, "liabilities_equity": other,
                        "reclass_prepaid": expected["预付账款"]}}


def check_bank(statement, journal):
    findings = []
    opening = statement.get("opening_balance_cents")
    entries = statement.get("entries") or []
    inflow = sum(item.get("amount_cents", 0) for item in entries
                 if item.get("direction") == "IN")
    outflow = sum(item.get("amount_cents", 0) for item in entries
                  if item.get("direction") == "OUT")
    computed = opening + inflow - outflow
    closing = statement.get("closing_balance_cents")
    if computed != closing:
        findings.append({"date": None, "amount": None,
                         "journal_balance": computed, "statement_balance": closing})
    if journal.get("closing_balance_cents") != closing:
        findings.append({"date": None, "amount": None,
                         "journal_balance": journal.get("closing_balance_cents"),
                         "statement_balance": closing})
    journal_entries = journal.get("entries") or []
    key = lambda item: (item.get("date"), item.get("direction"), item.get("amount_cents"),
                        item.get("reference"))
    journal_keys = [key(item) for item in journal_entries]
    statement_keys = [key(item) for item in entries]
    for item in journal_entries:
        if key(item) not in statement_keys:
            findings.append({"date": item.get("date"), "amount": item.get("amount_cents"),
                             "journal_balance": journal.get("closing_balance_cents"),
                             "statement_balance": closing, "side": "账有实无"})
    for item in entries:
        if key(item) not in journal_keys:
            findings.append({"date": item.get("date"), "amount": item.get("amount_cents"),
                             "journal_balance": journal.get("closing_balance_cents"),
                             "statement_balance": closing, "side": "实有账无"})
    return {"id": "bank_reconcile", "title": CHECK_TITLES["bank_reconcile"],
            "status": status_of(findings), "findings": findings,
            "summary": {"opening": opening, "inflow": inflow, "outflow": outflow,
                        "statement_closing": closing,
                        "journal_closing": journal.get("closing_balance_cents")}}


def check_attachments(entries, attachments):
    findings = []
    index = {item.get("voucher_id"): item for item in attachments.get("attachments") or []}
    for entry in entries:
        entry_id = entry.get("entry_id")
        debit_accounts = {line.get("account") for line in entry.get("lines") or []
                          if line.get("debit_cents", 0) > 0}
        credit_accounts = {line.get("account") for line in entry.get("lines") or []
                           if line.get("credit_cents", 0) > 0}
        required = set()
        if "1001" in debit_accounts:
            required |= {"INVOICE", "CONTRACT", "GOODS_RECEIPT"}
        if "1002" in credit_accounts:
            required |= {"APPROVAL", "BANK_RECEIPT"}
        if "1002" in debit_accounts:
            required.add("BANK_RECEIPT")
        amount = sum(line.get("debit_cents", 0) for line in entry.get("lines") or [])
        seen = set()
        for voucher_id in entry.get("attachments") or []:
            item = index.get(voucher_id)
            if item is None:
                findings.append({"entry_id": entry_id, "voucher_id": voucher_id,
                                 "expected": "附件存在", "actual": "缺失"})
                continue
            if item.get("voucher_type") not in required:
                findings.append({"entry_id": entry_id, "voucher_id": voucher_id,
                                 "expected": sorted(required),
                                 "actual": item.get("voucher_type")})
            if item.get("amount_cents") != amount:
                findings.append({"entry_id": entry_id, "voucher_id": voucher_id,
                                 "expected": amount, "actual": item.get("amount_cents")})
            seen.add(item.get("voucher_type"))
        if not required <= seen:
            findings.append({"entry_id": entry_id, "expected": sorted(required),
                             "actual": sorted(seen)})
    return {"id": "attachments", "title": CHECK_TITLES["attachments"],
            "status": status_of(findings), "findings": findings,
            "summary": {"entries": len(entries), "attachments": len(index)}}


def build_report(gl_root, documents, inputs, argv):
    entries = documents["journal_entries.json"].get("entries") or []
    journal_map = {entry.get("entry_id"): entry for entry in entries}
    checks = [
        check_journal(entries),
        check_trial(documents["trial_balance.json"]),
        check_ledger_to_voucher(documents["ledger_general.json"],
                                documents["ledger_subsidiary.json"], entries, journal_map),
        check_general_to_subsidiary(documents["ledger_general.json"],
                                    documents["ledger_subsidiary.json"],
                                    documents["trial_balance.json"]),
        check_ledger_to_report(documents["trial_balance.json"],
                               documents["balance_sheet.json"]),
        check_bank(documents["bank_statement.json"], documents["bank_journal.json"]),
        check_attachments(entries, documents["attachment_index.json"]),
    ]
    six = [item for item in checks if item["id"] != "attachments"]
    statuses = {item["id"]: item["status"] for item in checks}
    overall = "ALL_MATCHED" if all(item["status"] == "MATCHED" for item in checks) \
        else "DIFFERENCES_FOUND"
    trial_rows = {row.get("account"): row
                  for row in documents["trial_balance.json"].get("rows") or []}
    notes = []
    ap = trial_rows.get("2202") or {}
    if ap.get("closing_debit", 0) > ap.get("closing_credit", 0):
        notes.append("应付账款借方余额 %s 已重分类为预付账款，需人类判断是否为多付/预付。"
                     % format_money(ap.get("closing_debit") - ap.get("closing_credit")))
    notes.append("六类核对仅为数字与凭证/报表/银行的勾稽，不能替代函证、监盘、期后付款等实质性程序。")
    meta = documents["gl_manifest.json"]
    report = {
        "version": VERSION,
        "period": meta.get("period"),
        "batch_id": (meta.get("batch") or {}).get("batch_id"),
        "checks_performed": len(checks),
        "unperformed": UNPERFORMED,
        "checks": checks,
        "summary": {
            "six": {item["id"]: item["status"] for item in six},
            "statuses": statuses,
            "overall": overall,
            "notes": notes,
        },
        "boundaries": {"audit_conclusion": False, "real_approval": None,
                       "final_judgment": False},
    }
    return report


def format_money(cents):
    if type(cents) is not int:
        return "—"
    return "{:,.2f} 元".format(cents / 100.0)


def render_markdown(report, gl_root):
    lines = ["# GL 核对报告（六类 + 附件）", "",
             "合成账套；本报告只展示核对与差异，不构成审计结论。", "",
             "批次：%s；期间：%s 至 %s；总体：**%s**"
             % (report["batch_id"], (report["period"] or {}).get("period_start"),
                (report["period"] or {}).get("period_end"),
                report["summary"]["overall"]), ""]
    for check in report["checks"]:
        lines.append("## %s（%s）" % (check["title"], check["status"]))
        lines.append("")
        summary = check.get("summary") or {}
        if summary:
            lines.append("- 摘要：" + "；".join("%s=%s" % (key, value)
                                               for key, value in sorted(summary.items())))
        if check["findings"]:
            lines.append("")
            lines.append("| 差异 | 字段 |")
            lines.append("| --- | --- |")
            for finding in check["findings"]:
                lines.append("| %s | %s |" % (json.dumps(finding, ensure_ascii=False,
                                                         sort_keys=True), ""))
        else:
            lines.append("- 无差异。")
        lines.append("")
    lines.append("## 备注")
    for note in report["summary"]["notes"]:
        lines.append("- %s" % note)
    lines.append("")
    lines.append("## 未执行")
    for item in report["unperformed"]:
        lines.append("- %s" % item)
    lines.append("")
    lines.append("## 边界")
    lines.append("真实批准 `null`；真实初判未保存；0008；`next/AI=false`；")
    lines.append("核对结果只展示证据与差异，不构成审计结论或终判。")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-056 GL 六类核对引擎")
    parser.add_argument("--gl-root", dest="gl_root", required=True)
    parser.add_argument("--out-dir", dest="out_dir", required=True)
    args = parser.parse_args(argv)
    gl_root = Path(args.gl_root)
    out_dir = Path(args.out_dir)
    if not gl_root.is_absolute():
        gl_root = (Path.cwd() / gl_root).resolve()
    if not out_dir.is_absolute():
        out_dir = (Path.cwd() / out_dir).resolve()
    try:
        out_dir.resolve().relative_to(TEST_ROOT.resolve())
    except ValueError:
        print(json.dumps({"status": "ERROR", "kind": "usage",
                          "error": "--out-dir 必须位于测试根下"}, ensure_ascii=False))
        return 2
    if not out_dir.name.startswith(("task056_", "task056r1_")):
        print(json.dumps({"status": "ERROR", "kind": "usage",
                          "error": "--out-dir 目录名必须以 task056_ 或 task056r1_ 开头"},
                         ensure_ascii=False))
        return 2
    if out_dir.exists():
        print(json.dumps({"status": "ERROR", "kind": "usage",
                          "error": "--out-dir 必须从未存在"}, ensure_ascii=False))
        return 2
    try:
        documents, inputs = load_gl(gl_root)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "kind": "usage", "error": str(exc)},
                         ensure_ascii=False))
        return 2
    report = build_report(gl_root, documents, inputs, [sys.executable, "-B",
                                                       "scripts/reconcile_gl_v1.py",
                                                       "--gl-root", str(gl_root),
                                                       "--out-dir", str(out_dir)])
    out_dir.mkdir(parents=True, exist_ok=True)
    json_bytes = json.dumps(report, ensure_ascii=False, indent=2,
                            sort_keys=True).encode("utf-8") + b"\n"
    (out_dir / "gl_reconcile_report.json").write_bytes(json_bytes)
    (out_dir / "gl_reconcile_report.md").write_text(render_markdown(report, gl_root),
                                                    "utf-8")
    source = {
        "version": VERSION,
        "gl_root": str(gl_root),
        "inputs": inputs,
        "command": [sys.executable, "-B", "scripts/reconcile_gl_v1.py",
                    "--gl-root", str(gl_root), "--out-dir", str(out_dir)],
        "note": "只读 GL 包；报告为核对与差异，不含审计结论。",
    }
    (out_dir / "reconcile_source.json").write_bytes(
        json.dumps(source, ensure_ascii=False, indent=2,
                   sort_keys=True).encode("utf-8") + b"\n")
    overall = report["summary"]["overall"]
    print(json.dumps({"status": "PASS" if overall == "ALL_MATCHED" else "DIFFERENCES",
                      "overall": overall,
                      "checks": {item["id"]: item["status"] for item in report["checks"]},
                      "out": str(out_dir)}, ensure_ascii=False))
    return 0 if overall == "ALL_MATCHED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
