#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-044：账证相符 L1 的动态测试（真实 CLI 子进程）。

- 正常（一致夹具）：以 TASK-043 接受输入为基线复制一份"补齐 P02 审批/回单"的一致夹具，
  全部 MATCHED、R02 抽样底稿完整、退出码 0。
- 规范输入对照：直接对 TASK-043 接受输入运行——P02 在 TASK-043 合成数据中没有审批/回单，
  应如实报 2 条 MISSING_VOUCHER（账有证无）；这一对照检验匹配器不会把"未提供"当成"已匹配"。
- 负例（≥10 类，复制一致夹具注入，每类一条，精确字段/分类）：金额差、税额合计、日期、
  对方、审批状态、方向、多发票合计、账有证无、证有账无、退款原分摊、重复审批。
- 只读纪律：规范输入根、账务 normalized/started/artifacts 在测试前后字节不变；命令一律 `-B`。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_V1 = ROOT / "data/evidence_inputs/task043_v1"
EVIDENCE_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
LEDGER_DIR = ROOT / "data/runtime/task042_dsh_01/normal.load"
LEDGER = LEDGER_DIR / "normalized.json"
SCRIPT = ROOT / "scripts/voucher_match_v1.py"
EXPECTED_FILES = (
    "bank/transactions.json", "links/index.json", "reports/placeholders.json",
    "vouchers/approvals.json", "vouchers/bank_receipts.json",
    "vouchers/contracts.json", "vouchers/goods_receipts.json",
    "vouchers/invoices.json",
)


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def write_json(path, value):
    Path(path).write_bytes(canon(value))


def snapshot(root: Path) -> dict:
    result = {}
    for item in sorted(Path(root).rglob("*")):
        if item.is_file():
            raw = item.read_bytes()
            result[item.relative_to(root).as_posix()] = [len(raw), sha_bytes(raw)]
    return result


def file_identity(path: Path) -> dict:
    raw = Path(path).read_bytes()
    return {"byte_size": len(raw), "sha256": sha_bytes(raw)}


def update_manifest(input_dir: Path) -> None:
    manifest = read_json(input_dir / "input_manifest.json")
    entries = []
    for relative in sorted(EXPECTED_FILES):
        raw = (input_dir / relative).read_bytes()
        entries.append({"relative": relative, "byte_size": len(raw),
                        "sha256": sha_bytes(raw)})
    manifest["files"] = entries
    write_json(input_dir / "input_manifest.json", manifest)


def build_consistent_input(target: Path) -> None:
    """复制 TASK-043 接受输入并补齐 P02 的审批单/银行回单与索引（仅测试夹具）。"""
    shutil.copytree(INPUT_V1, target)
    approvals = read_json(target / "vouchers/approvals.json")
    approvals.append({"voucher_id": "V-APR-0002", "approval_no": "APR-2026-0002",
                      "approval_date": "2026-09-09", "payment_id": "P02",
                      "amount_cents": 500000, "status": "APPROVED"})
    write_json(target / "vouchers/approvals.json", approvals)
    receipts = read_json(target / "vouchers/bank_receipts.json")
    receipts.append({"voucher_id": "V-BR-0003", "receipt_no": "BR-2026-0003",
                     "bank_txn_id": "BT-2026-0002", "txn_date": "2026-09-10",
                     "amount_cents": 500000, "direction": "PAY",
                     "counterparty_name": "甲供应商",
                     "counterparty_account": "6222020200000001", "currency": "CNY"})
    write_json(target / "vouchers/bank_receipts.json", receipts)
    links = read_json(target / "links/index.json")
    links.append({"link_id": "L-0007", "link_type": "PAYMENT_APPROVAL",
                  "ledger_type": "PAYMENT", "ledger_id": "P02",
                  "voucher_id": "V-APR-0002"})
    links.append({"link_id": "L-0008", "link_type": "PAYMENT_BANK_RECEIPT",
                  "ledger_type": "PAYMENT", "ledger_id": "P02",
                  "voucher_id": "V-BR-0003"})
    write_json(target / "links/index.json", links)
    update_manifest(target)


class Case:
    def __init__(self, name, expected, *, fixture=True):
        self.name = name
        self.expected = expected
        self.fixture = fixture
        self.exit_code = None
        self.status = "not-run"
        self.observed = {}
        self.detail = ""

    def to_dict(self):
        return {"case": self.name, "expected": self.expected,
                "exit_code": self.exit_code, "status": self.status,
                "observed": self.observed, "detail": self.detail}


def run_matcher(input_dir: Path, out_dir: Path, log_dir: Path, ledger_path: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / "stdout.txt"
    stderr = log_dir / "stderr.txt"
    command = [sys.executable, "-B", str(SCRIPT), "--input", str(input_dir),
               "--ledger-normalized", str(ledger_path), "--out", str(out_dir)]
    with stdout.open("wb") as out, stderr.open("wb") as err:
        completed = subprocess.run(command, cwd=str(ROOT), stdout=out, stderr=err)
    return completed.returncode, command


def injection(name, input_dir: Path, case_dir: Path) -> Path:
    """对一致夹具副本注入违约；返回本次使用的账务 normalized 路径。"""
    ledger = LEDGER
    if name == "amount_minus_one":
        invoices = read_json(input_dir / "vouchers/invoices.json")
        invoices[0]["amount_cents"] = 499999
        invoices[0]["total_cents"] = 499999
        write_json(input_dir / "vouchers/invoices.json", invoices)
    elif name == "tax_total_mismatch":
        invoices = read_json(input_dir / "vouchers/invoices.json")
        invoices[0]["tax_cents"] = 100
        invoices[0]["total_cents"] = 500000
        write_json(input_dir / "vouchers/invoices.json", invoices)
    elif name == "date_out_of_range":
        invoices = read_json(input_dir / "vouchers/invoices.json")
        invoices[0]["issue_date"] = "2026-10-01"
        write_json(input_dir / "vouchers/invoices.json", invoices)
    elif name == "date_wrong":
        receipts = read_json(input_dir / "vouchers/bank_receipts.json")
        receipts[0]["txn_date"] = "2026-09-11"
        write_json(input_dir / "vouchers/bank_receipts.json", receipts)
    elif name == "counterparty_name":
        receipts = read_json(input_dir / "vouchers/bank_receipts.json")
        receipts[0]["counterparty_name"] = "乙收款对象"
        write_json(input_dir / "vouchers/bank_receipts.json", receipts)
    elif name == "approval_not_approved":
        approvals = read_json(input_dir / "vouchers/approvals.json")
        approvals[0]["status"] = "REJECTED"
        write_json(input_dir / "vouchers/approvals.json", approvals)
    elif name == "direction_wrong":
        receipts = read_json(input_dir / "vouchers/bank_receipts.json")
        receipts[0]["direction"] = "REFUND"
        write_json(input_dir / "vouchers/bank_receipts.json", receipts)
    elif name == "multi_invoice_sum":
        invoices = read_json(input_dir / "vouchers/invoices.json")
        invoices.append({"voucher_id": "V-INV-0002", "invoice_no": "INV-2026-0002",
                         "issue_date": "2026-09-06", "seller_supplier_id": "S001",
                         "seller_name": "甲供应商", "buyer_name": "澄明商贸有限公司",
                         "amount_cents": 100000, "tax_cents": 0, "total_cents": 100000,
                         "currency": "CNY"})
        write_json(input_dir / "vouchers/invoices.json", invoices)
        links = read_json(input_dir / "links/index.json")
        links.append({"link_id": "L-0009", "link_type": "AP_INVOICE",
                      "ledger_type": "AP", "ledger_id": "AP01",
                      "voucher_id": "V-INV-0002"})
        write_json(input_dir / "links/index.json", links)
    elif name == "missing_voucher":
        links = [link for link in read_json(input_dir / "links/index.json")
                 if link["link_type"] != "AP_INVOICE"]
        write_json(input_dir / "links/index.json", links)
    elif name == "extra_voucher":
        invoices = read_json(input_dir / "vouchers/invoices.json")
        invoices.append({"voucher_id": "V-INV-0009", "invoice_no": "INV-2026-0009",
                         "issue_date": "2026-09-07", "seller_supplier_id": "S001",
                         "seller_name": "甲供应商", "buyer_name": "澄明商贸有限公司",
                         "amount_cents": 10000, "tax_cents": 0, "total_cents": 10000,
                         "currency": "CNY"})
        write_json(input_dir / "vouchers/invoices.json", invoices)
    elif name == "refund_link_mismatch":
        normalized = read_json(LEDGER)
        tables = normalized["tables"]["allocations"]["records"]
        for record in tables:
            if record["data"]["allocation_id"] == "AR01":
                record["data"]["original_allocation_id"] = "A99"
        case_dir.mkdir(parents=True, exist_ok=True)
        ledger = case_dir / "normalized.json"
        ledger.write_bytes(canon(normalized))
    elif name == "approval_extra":
        approvals = read_json(input_dir / "vouchers/approvals.json")
        approvals.append({"voucher_id": "V-APR-0009", "approval_no": "APR-2026-0009",
                          "approval_date": "2026-09-08", "payment_id": "P01",
                          "amount_cents": 500000, "status": "APPROVED"})
        write_json(input_dir / "vouchers/approvals.json", approvals)
        links = read_json(input_dir / "links/index.json")
        links.append({"link_id": "L-0010", "link_type": "PAYMENT_APPROVAL",
                      "ledger_type": "PAYMENT", "ledger_id": "P01",
                      "voucher_id": "V-APR-0009"})
        write_json(input_dir / "links/index.json", links)
    else:
        raise SystemExit("unknown case: %s" % name)
    update_manifest(input_dir)
    return ledger


def check_case(case: Case, report_path: Path, *, expect_all_matched=False,
               expect_missing=0) -> bool:
    if case.exit_code is None:
        case.status = "FAIL"
        case.detail = "未运行"
        return False
    if not report_path.is_file():
        case.status = "FAIL"
        case.detail = "缺少 voucher_match_report.json"
        return False
    report = read_json(report_path)
    case.observed = {"conclusion": report.get("conclusion"),
                     "counts": report["summary"]["classification_counts"],
                     "missing": len(report["missing_vouchers"]),
                     "extra": len(report["extra_vouchers"])}
    if expect_all_matched:
        ok = case.exit_code == 0 and report.get("conclusion") == "ALL_MATCHED" \
            and report["summary"]["differences_total"] == 0 \
            and report["summary"]["item_status"].get("MATCHED") \
            == report["summary"]["items_total"]
        case.status = "PASS" if ok else "FAIL"
        case.detail = "" if ok else "期望全部 MATCHED 且退出码 0"
        return ok
    if expect_missing:
        ok = case.exit_code == 1 and report["summary"]["missing_total"] == expect_missing \
            and report["summary"]["differences_total"] == expect_missing
        case.status = "PASS" if ok else "FAIL"
        case.detail = "" if ok else "期望 %d 条 MISSING_VOUCHER" % expect_missing
        return ok
    classification, field_prefix = case.expected
    ok = case.exit_code == 1 and report.get("conclusion") == "DIFFERENCES_FOUND"
    found = None
    for difference in report.get("differences", []):
        if difference["classification"] == classification \
                and str(difference["field"]).startswith(field_prefix):
            found = difference
            break
    if found is None:
        for extra in report.get("extra_vouchers", []):
            if classification == "EXTRA_VOUCHER" and str(field_prefix) in (
                    str(extra.get("voucher_id")), str(extra.get("detail"))):
                found = extra
                break
    if found is None:
        for missing in report.get("missing_vouchers", []):
            if classification == "MISSING_VOUCHER" and str(field_prefix) in (
                    missing.get("ledger_type", ""), missing.get("voucher_type", "")):
                found = missing
                break
    ok = ok and found is not None
    case.status = "PASS" if ok else "FAIL"
    case.detail = "" if ok else "未找到期望差异：%s / %s" % (classification, field_prefix)
    if found is not None:
        case.observed["matched_reason"] = found
    return ok


CASES = (
    ("amount_minus_one", ("AMOUNT_MISMATCH", "total_cents_sum")),
    ("tax_total_mismatch", ("TAX_TOTAL_MISMATCH", "tax_cents")),
    ("date_out_of_range", ("DATE_MISMATCH", "issue_date")),
    ("date_wrong", ("DATE_MISMATCH", "txn_date")),
    ("counterparty_name", ("COUNTERPARTY_MISMATCH", "counterparty_name")),
    ("approval_not_approved", ("STATUS_MISMATCH", "status")),
    ("direction_wrong", ("DIRECTION_MISMATCH", "direction")),
    ("multi_invoice_sum", ("SUM_MISMATCH", "total_cents_sum")),
    ("missing_voucher", ("MISSING_VOUCHER", "AP")),
    ("extra_voucher", ("EXTRA_VOUCHER", "V-INV-0009")),
    ("refund_link_mismatch", ("REFUND_LINK_MISMATCH", "original_allocation_id")),
    ("approval_extra", ("EXTRA_VOUCHER", "V-APR-0009")),
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-044 账证相符 L1 测试")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    out_root = Path(args.out_dir)
    if not out_root.is_absolute():
        out_root = (Path.cwd() / out_root).resolve()
    if out_root.exists():
        print(json.dumps({"status": "FAIL", "reason": "out-dir 必须从未存在"}, ensure_ascii=False))
        return 1
    try:
        out_root.relative_to(EVIDENCE_ROOT.resolve())
    except ValueError:
        print(json.dumps({"status": "FAIL",
                          "reason": "out-dir 必须位于 %s 之下" % EVIDENCE_ROOT},
                         ensure_ascii=False))
        return 1
    if not out_root.name.startswith("task044_"):
        print(json.dumps({"status": "FAIL",
                          "reason": "out-dir 目录名必须以 task044_ 开头"}, ensure_ascii=False))
        return 1
    input_before = snapshot(INPUT_V1)
    ledger_before = file_identity(LEDGER)
    started_before = file_identity(LEDGER_DIR / "started.json")
    artifacts_before = file_identity(LEDGER_DIR / "artifacts.json")
    out_root.mkdir(parents=True)

    results = []
    # 一致夹具正常
    consistent = Case("normal_consistent", ("ALL_MATCHED", "—"))
    consistent.dir = out_root / "normal_consistent"
    consistent.input = consistent.dir / "input"
    consistent.dir.mkdir(parents=True)
    build_consistent_input(consistent.input)
    consistent.out = consistent.dir / "task044_normal"
    consistent.exit_code, command = run_matcher(consistent.input, consistent.out,
                                                consistent.dir, LEDGER)
    consistent.observed = {"command": command,
                           "input": consistent.input.relative_to(ROOT).as_posix()}
    check_case(consistent, consistent.out / "voucher_match_report.json",
               expect_all_matched=True)
    results.append(consistent)

    # 规范输入对照（P02 无审批/回单 → 2 条 MISSING）
    canonical = Case("canonical_control", ("MISSING_VOUCHER", "P02"))
    canonical.dir = out_root / "canonical_control"
    canonical.dir.mkdir(parents=True)
    canonical.out = canonical.dir / "task044_canonical"
    canonical.exit_code, command = run_matcher(INPUT_V1, canonical.out, canonical.dir, LEDGER)
    canonical.observed = {"command": command}
    check_case(canonical, canonical.out / "voucher_match_report.json", expect_missing=2)
    results.append(canonical)

    # 负例（一致夹具副本注入）
    for name, expected in CASES:
        case = Case(name, expected)
        case.dir = out_root / name
        case.dir.mkdir(parents=True)
        case.input = case.dir / "input"
        shutil.copytree(consistent.input, case.input)
        ledger = injection(name, case.input, case.dir)
        try:
            ledger_path = ledger
            if not Path(ledger_path).is_absolute():
                ledger_path = ROOT / ledger_path
            case.out = case.dir / "task044_out"
            case.exit_code, command = run_matcher(case.input, case.out, case.dir, ledger_path)
            case.observed = {"command": [str(item) for item in command],
                             "ledger": str(ledger_path)}
            check_case(case, case.out / "voucher_match_report.json")
        finally:
            pass
        results.append(case)

    input_after = snapshot(INPUT_V1)
    ledger_after = file_identity(LEDGER)
    started_after = file_identity(LEDGER_DIR / "started.json")
    artifacts_after = file_identity(LEDGER_DIR / "artifacts.json")
    read_only_ok = (input_before == input_after and ledger_before == ledger_after
                    and started_before == started_after
                    and artifacts_before == artifacts_after)
    passed = sum(1 for item in results if item.status == "PASS")
    report = {
        "task": "TASK-044",
        "generated_by": "tests/test_voucher_match_v1.py",
        "canonical_input_root": INPUT_V1.relative_to(ROOT).as_posix(),
        "canonical_ledger": LEDGER.relative_to(ROOT).as_posix(),
        "read_only_ok": read_only_ok,
        "input_root_unchanged": input_before == input_after,
        "ledger_unchanged": ledger_before == ledger_after and started_before == started_after
                            and artifacts_before == artifacts_after,
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item.name for item in results if item.status != "PASS"],
        "status": "PASS" if passed == len(results) and read_only_ok else "FAIL",
        "cases": [item.to_dict() for item in results],
        "note": ("正常一致夹具由 TASK-043 接受输入复制并补齐 P02 审批单/回单与索引（仅测试夹具）；"
                 "规范输入对照如实暴露 TASK-043 合成数据中 P02 无凭证的账有证无；"
                 "负例均复制夹具注入，原输入与既有证据只读。"),
        "boundaries": {"real_approval": None, "batch_approved": False,
                       "real_initial_judgment_saved": False,
                       "next_step_allowed": False, "ai_enabled": False,
                       "identity_authenticated": False,
                       "audit_conclusion_formed": False},
    }
    report_path = out_root / "test_report.json"
    report_path.write_bytes(json.dumps(report, ensure_ascii=False, indent=2,
                                       sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({"status": report["status"], "cases": len(results),
                      "passed": passed, "read_only_ok": read_only_ok,
                      "report": str(report_path)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
