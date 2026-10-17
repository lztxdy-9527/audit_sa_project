#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-045：账实相符（银行流水交易级勾对）动态测试（真实 CLI 子进程）。

- 正常（v1.1 canonical）：付款/退款全部匹配（引用或三元组）、期间合计一致、未达账项为空。
- v1 对照：以卡 §1 原文的 task043_v1 运行，验证同为 ALL_MATCHED（P02 走三元组）。
- 负例（10 类，复制输入副本注入；重复匹配用账务副本注入）：金额差 1 分、日期不符、对方户名不符、
  方向错、引用冲突、同一流水重复行、同一流水重复匹配、账有实无、实有账无、期间外流水。
- 只读：规范输入根、账务 normalized/started/artifacts 前后字节不变；命令一律 `-B`。
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
INPUT_V11 = ROOT / "data/evidence_inputs/task043_v1_1"
INPUT_V1 = ROOT / "data/evidence_inputs/task043_v1"
EVIDENCE_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
LEDGER_DIR = ROOT / "data/runtime/task042_dsh_01/normal.load"
LEDGER = LEDGER_DIR / "normalized.json"
SCRIPT = ROOT / "scripts/bank_reconcile_v1.py"
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


def run_reconcile(input_dir: Path, out_dir: Path, log_dir: Path, ledger_path: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / "stdout.txt"
    stderr = log_dir / "stderr.txt"
    command = [sys.executable, "-B", str(SCRIPT), "--input", str(input_dir),
               "--ledger-normalized", str(ledger_path), "--out", str(out_dir)]
    with stdout.open("wb") as out, stderr.open("wb") as errs:
        completed = subprocess.run(command, cwd=str(ROOT), stdout=out, stderr=errs)
    return completed.returncode, command


def injection(name, input_dir: Path, case_dir: Path) -> Path:
    ledger = LEDGER
    txns = read_json(input_dir / "bank/transactions.json")
    if name == "amount_minus_one":
        txns[0]["amount_cents"] = 499999
        write_json(input_dir / "bank/transactions.json", txns)
    elif name == "date_mismatch":
        txns[0]["txn_date"] = "2026-09-11"
        write_json(input_dir / "bank/transactions.json", txns)
    elif name == "counterparty":
        txns[0]["counterparty_name"] = "乙收款对象"
        write_json(input_dir / "bank/transactions.json", txns)
    elif name == "direction":
        txns[0]["direction"] = "IN"
        write_json(input_dir / "bank/transactions.json", txns)
    elif name == "reference_conflict":
        txns[0]["reference"] = "P02"
        write_json(input_dir / "bank/transactions.json", txns)
    elif name == "duplicate_bank_line":
        txns.append(copy.deepcopy(txns[0]))
        write_json(input_dir / "bank/transactions.json", txns)
    elif name == "duplicate_match":
        normalized = read_json(LEDGER)
        for record in normalized["tables"]["payments"]["records"]:
            if record["data"]["payment_id"] == "P02":
                record["data"]["bank_reference"] = "P01"
        case_dir.mkdir(parents=True, exist_ok=True)
        ledger = case_dir / "normalized.json"
        ledger.write_bytes(canon(normalized))
    elif name == "ledger_unmatched":
        keep = [txn for txn in txns if txn.get("bank_txn_id") != "BT-2026-0002"]
        write_json(input_dir / "bank/transactions.json", keep)
    elif name == "bank_unmatched":
        txns.append({"bank_txn_id": "BT-2026-9999", "txn_date": "2026-09-25",
                     "direction": "OUT", "amount_cents": 100000,
                     "counterparty_name": "甲供应商",
                     "counterparty_account": "6222020200000001",
                     "summary": "未达账项候选", "reference": None})
        write_json(input_dir / "bank/transactions.json", txns)
    elif name == "period_out":
        txns[0]["txn_date"] = "2026-10-01"
        write_json(input_dir / "bank/transactions.json", txns)
    else:
        raise SystemExit("unknown case: %s" % name)
    update_manifest(input_dir)
    return ledger


def check_report(case: Case, report_path: Path, *, expect_all_matched=False,
                 expect_missing=None) -> bool:
    if case.exit_code is None:
        case.status = "FAIL"
        case.detail = "未运行"
        return False
    if not report_path.is_file():
        case.status = "FAIL"
        case.detail = "缺少 bank_reconcile_report.json"
        return False
    report = read_json(report_path)
    case.observed = {"conclusion": report.get("conclusion"),
                     "counts": report["summary"]["classification_counts"],
                     "matched": report["summary"]["matched"],
                     "ledger_unmatched": report["summary"]["ledger_unmatched"],
                     "bank_unmatched": report["summary"]["bank_unmatched"],
                     "duplicates": report["summary"]["duplicates"]}
    if expect_all_matched:
        ok = case.exit_code == 0 and report.get("conclusion") == "ALL_MATCHED" \
            and report["summary"]["matched"] == 3 \
            and report["summary"]["differences"] == 0 \
            and report["summary"]["ledger_unmatched"] == 0 \
            and report["summary"]["bank_unmatched"] == 0 \
            and report["period_totals"]["out_difference_cents"] == 0 \
            and report["period_totals"]["in_difference_cents"] == 0
        case.status = "PASS" if ok else "FAIL"
        case.detail = "" if ok else "期望全部匹配且期间合计 0 差异"
        return ok
    classification, field_prefix = case.expected
    if callable(field_prefix):
        found = field_prefix(report)
    else:
        found = None
        for difference in report.get("differences", []):
            if difference["classification"] == classification \
                    and str(difference["field"]).startswith(field_prefix):
                found = difference
                break
        if found is None:
            for item in report.get("duplicates", []):
                if item["classification"] == classification:
                    found = item
                    break
        if found is None:
            for item in report["unmatched"]["ledger_unmatched"]:
                if classification == "LEDGER_UNMATCHED":
                    found = item
                    break
        if found is None:
            for item in report["unmatched"]["bank_unmatched"]:
                if classification == "BANK_UNMATCHED":
                    found = item
                    break
    ok = case.exit_code == 1 and report.get("conclusion") == "DIFFERENCES_FOUND" \
        and found is not None
    case.status = "PASS" if ok else "FAIL"
    case.detail = "" if ok else "未找到期望差异：%s / %s" % (classification, field_prefix)
    if found is not None:
        case.observed["matched_reason"] = found if isinstance(found, dict) else str(found)
    return ok


CASES = (
    ("amount_minus_one", ("AMOUNT_MISMATCH", "amount_cents")),
    ("date_mismatch", ("DATE_MISMATCH", "txn_date")),
    ("counterparty", ("COUNTERPARTY_MISMATCH", "counterparty_name")),
    ("direction", ("DIRECTION_MISMATCH", "direction")),
    ("reference_conflict", ("REFERENCE_CONFLICT", "reference")),
    ("duplicate_bank_line", ("DUPLICATE_BANK_LINE", "")),
    ("duplicate_match", ("DUPLICATE_MATCH", "")),
    ("ledger_unmatched", ("LEDGER_UNMATCHED", "")),
    ("bank_unmatched", ("BANK_UNMATCHED", "")),
    ("period_out", ("DATE_MISMATCH", "txn_date")),
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-045 账实相符测试")
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
    if not out_root.name.startswith("task045_"):
        print(json.dumps({"status": "FAIL",
                          "reason": "out-dir 目录名必须以 task045_ 开头"}, ensure_ascii=False))
        return 1
    input_v11_before = snapshot(INPUT_V11)
    input_v1_before = snapshot(INPUT_V1)
    ledger_before = file_identity(LEDGER)
    started_before = file_identity(LEDGER_DIR / "started.json")
    artifacts_before = file_identity(LEDGER_DIR / "artifacts.json")
    out_root.mkdir(parents=True)
    results = []

    # 正常 v1.1
    normal = Case("normal_v1_1", ("ALL_MATCHED", "—"))
    normal.dir = out_root / "normal_v1_1"
    normal.dir.mkdir(parents=True)
    normal.out = normal.dir / "task045_normal"
    normal.exit_code, command = run_reconcile(INPUT_V11, normal.out, normal.dir, LEDGER)
    normal.observed = {"command": command}
    check_report(normal, normal.out / "bank_reconcile_report.json", expect_all_matched=True)
    results.append(normal)

    # v1 对照
    control = Case("control_v1", ("ALL_MATCHED", "—"))
    control.dir = out_root / "control_v1"
    control.dir.mkdir(parents=True)
    control.out = control.dir / "task045_v1"
    control.exit_code, command = run_reconcile(INPUT_V1, control.out, control.dir, LEDGER)
    control.observed = {"command": command}
    check_report(control, control.out / "bank_reconcile_report.json", expect_all_matched=True)
    if control.status == "PASS":
        report = read_json(control.out / "bank_reconcile_report.json")
        basis = {item["ledger_id"]: item["basis"] for item in report["matched"]}
        control.observed["basis"] = basis
        control.status = "PASS" if basis.get("P02") == "TRIPLE" else "FAIL"
        control.detail = "" if control.status == "PASS" else "v1 下 P02 应走三元组"
    results.append(control)

    for name, expected in CASES:
        case = Case(name, expected)
        case.dir = out_root / name
        case.dir.mkdir(parents=True)
        case.input = case.dir / "input"
        shutil.copytree(INPUT_V11, case.input)
        ledger = injection(name, case.input, case.dir)
        ledger_path = Path(ledger)
        if not ledger_path.is_absolute():
            ledger_path = ROOT / ledger_path
        case.out = case.dir / "task045_out"
        case.exit_code, command = run_reconcile(case.input, case.out, case.dir, ledger_path)
        case.observed = {"command": [str(item) for item in command],
                         "ledger": str(ledger_path)}
        check_report(case, case.out / "bank_reconcile_report.json")
        results.append(case)

    input_v11_after = snapshot(INPUT_V11)
    input_v1_after = snapshot(INPUT_V1)
    ledger_after = file_identity(LEDGER)
    started_after = file_identity(LEDGER_DIR / "started.json")
    artifacts_after = file_identity(LEDGER_DIR / "artifacts.json")
    read_only_ok = (input_v11_before == input_v11_after
                    and input_v1_before == input_v1_after
                    and ledger_before == ledger_after
                    and started_before == started_after
                    and artifacts_before == artifacts_after)
    passed = sum(1 for item in results if item.status == "PASS")
    report = {
        "task": "TASK-045",
        "generated_by": "tests/test_bank_reconcile_v1.py",
        "canonical_input_root": INPUT_V11.relative_to(ROOT).as_posix(),
        "v1_control_root": INPUT_V1.relative_to(ROOT).as_posix(),
        "canonical_ledger": LEDGER.relative_to(ROOT).as_posix(),
        "read_only_ok": read_only_ok,
        "input_v11_unchanged": input_v11_before == input_v11_after,
        "input_v1_unchanged": input_v1_before == input_v1_after,
        "ledger_unchanged": ledger_before == ledger_after and started_before == started_after
                            and artifacts_before == artifacts_after,
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item.name for item in results if item.status != "PASS"],
        "status": "PASS" if passed == len(results) and read_only_ok else "FAIL",
        "cases": [item.to_dict() for item in results],
        "note": ("正常以 v1.1 canonical 输入运行；v1 对照验证同为 ALL_MATCHED（P02 走三元组）；"
                 "负例复制输入副本注入，重复匹配用账务 normalized 副本注入；原输入与既有证据只读。"),
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
