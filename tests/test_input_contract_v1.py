#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-043：输入契约 v1 校验与整批拒收的动态测试（真实子进程、真实 CLI）。

- 正常：合法 v1 合成输入 → `input_registry.json`（版本/批次/逐文件哈希/计数/结论），退出码 0。
- 负例：逐类注入契约违约（复制输入副本，不改原输入根）→ 整批拒收、`rejection.json` 字段精确、退出码非 0。
- 只读纪律：规范输入根、ledger 数据库在测试前后字节不变；每例保留输入副本、命令、stdout/stderr、
  退出码与 rejection.json；测试命令一律 `-B`。

边界：合成演示；不批准真实批次、不认证身份、不开放 AI/终判；本测试不做匹配、不出核对底稿。
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
LEDGER_DB = ROOT / "data/sqlite_tests/task042_dsh_01/normal/runtime.sqlite3"
SCRIPT = ROOT / "scripts/input_contract_v1.py"
EXPECTED_FILES = (
    "bank/transactions.json",
    "links/index.json",
    "reports/placeholders.json",
    "vouchers/approvals.json",
    "vouchers/bank_receipts.json",
    "vouchers/contracts.json",
    "vouchers/goods_receipts.json",
    "vouchers/invoices.json",
)
MANIFEST = "input_manifest.json"


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
            result[item.relative_to(root).as_posix()] = {"byte_size": len(raw),
                                                         "sha256": sha_bytes(raw)}
    return result


def update_manifest(input_dir: Path) -> None:
    manifest = read_json(input_dir / MANIFEST)
    entries = []
    for relative in sorted(EXPECTED_FILES):
        raw = (input_dir / relative).read_bytes()
        entries.append({"relative": relative, "byte_size": len(raw),
                        "sha256": sha_bytes(raw)})
    manifest["files"] = entries
    write_json(input_dir / MANIFEST, manifest)


class CaseResult:
    def __init__(self, name, expected):
        self.name = name
        self.expected = expected
        self.exit_code = None
        self.status = "not-run"
        self.observed = None
        self.reasons = []
        self.detail = ""

    def to_dict(self):
        return {"case": self.name, "expected": self.expected,
                "exit_code": self.exit_code, "status": self.status,
                "observed": self.observed, "reasons": self.reasons,
                "detail": self.detail}


def run_validator(input_dir: Path, out_dir: Path, log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "stdout.txt"
    stderr_path = log_dir / "stderr.txt"
    command = [sys.executable, "-B", str(SCRIPT), "--input", str(input_dir),
               "--out", str(out_dir), "--ledger-db", str(LEDGER_DB)]
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        completed = subprocess.run(command, cwd=str(ROOT), stdout=out, stderr=err)
    return completed.returncode, command, stdout_path, stderr_path


def reason_codes(rejection):
    return [(reason.get("code"), reason.get("field"), reason.get("voucher_id"))
            for reason in rejection.get("reasons", [])]


def expectations_pass(case: CaseResult) -> bool:
    if case.exit_code is None or case.exit_code == 0:
        case.status = "FAIL"
        case.detail = "退出码必须非 0（整批拒收），实际 %r" % case.exit_code
        return False
    rejection_path = case.out_dir / "rejection.json"
    if not rejection_path.is_file():
        case.status = "FAIL"
        case.detail = "缺少 rejection.json"
        return False
    rejection = read_json(rejection_path)
    case.observed = {"rejection_version": rejection.get("rejection_version"),
                     "reason_count": rejection.get("reason_count"),
                     "conclusion": rejection.get("summary", {}).get("note")}
    case.reasons = reason_codes(rejection)
    code, field_prefix = case.expected
    for observed_code, observed_field, _ in case.reasons:
        if observed_code == code and str(observed_field).startswith(field_prefix):
            case.status = "PASS"
            return True
    case.status = "FAIL"
    case.detail = "未找到期望 reason：code=%r field 前缀=%r" % (code, field_prefix)
    return False


def prepare_case(root: Path, name: str) -> Path:
    case_dir = root / name
    case_dir.mkdir(parents=True, exist_ok=False)
    input_dir = case_dir / "input"
    shutil.copytree(INPUT_V1, input_dir)
    return case_dir


def inject(name: str, input_dir: Path, case_dir: Path) -> None:
    if name == "missing_file":
        (input_dir / "vouchers/contracts.json").unlink()
    elif name == "unknown_file":
        (input_dir / "vouchers/extra.json").write_bytes(b"[]\n")
    elif name == "hash_mismatch":
        path = input_dir / "bank/transactions.json"
        path.write_bytes(path.read_bytes() + b"\n")
    elif name == "duplicate_voucher_id":
        records = read_json(input_dir / "vouchers/invoices.json")
        records.append(copy.deepcopy(records[0]))
        write_json(input_dir / "vouchers/invoices.json", records)
        update_manifest(input_dir)
    elif name == "missing_required":
        records = read_json(input_dir / "vouchers/invoices.json")
        records[0].pop("seller_name")
        write_json(input_dir / "vouchers/invoices.json", records)
        update_manifest(input_dir)
    elif name == "amount_not_integer":
        records = read_json(input_dir / "vouchers/invoices.json")
        records[0]["amount_cents"] = 500000.5
        write_json(input_dir / "vouchers/invoices.json", records)
        update_manifest(input_dir)
    elif name == "amount_not_positive":
        records = read_json(input_dir / "vouchers/goods_receipts.json")
        records[0]["amount_cents"] = 0
        write_json(input_dir / "vouchers/goods_receipts.json", records)
        update_manifest(input_dir)
    elif name == "total_mismatch":
        records = read_json(input_dir / "vouchers/invoices.json")
        records[0]["total_cents"] = 500001
        write_json(input_dir / "vouchers/invoices.json", records)
        update_manifest(input_dir)
    elif name == "date_out_of_range":
        records = read_json(input_dir / "vouchers/contracts.json")
        records[0]["sign_date"] = "2026-10-01"
        write_json(input_dir / "vouchers/contracts.json", records)
        update_manifest(input_dir)
    elif name == "wrong_currency":
        records = read_json(input_dir / "vouchers/invoices.json")
        records[0]["currency"] = "USD"
        write_json(input_dir / "vouchers/invoices.json", records)
        update_manifest(input_dir)
    elif name == "dangling_index":
        records = read_json(input_dir / "links/index.json")
        records[0]["voucher_id"] = "V-NOPE"
        write_json(input_dir / "links/index.json", records)
        update_manifest(input_dir)
    elif name == "duplicate_index":
        records = read_json(input_dir / "links/index.json")
        duplicate = copy.deepcopy(records[0])
        duplicate["link_id"] = "L-DUP-0001"
        records.append(duplicate)
        write_json(input_dir / "links/index.json", records)
        update_manifest(input_dir)
    elif name == "nonexistent_ledger_id":
        records = read_json(input_dir / "links/index.json")
        records[0]["ledger_id"] = "AP99"
        write_json(input_dir / "links/index.json", records)
        update_manifest(input_dir)
    elif name == "link_type_mismatch":
        records = read_json(input_dir / "links/index.json")
        records[0]["voucher_id"] = "V-BR-0001"
        write_json(input_dir / "links/index.json", records)
        update_manifest(input_dir)
    elif name == "bad_json":
        (input_dir / "links/index.json").write_bytes(b"{not-json")
        update_manifest(input_dir)
    elif name == "non_array":
        (input_dir / "reports/placeholders.json").write_bytes(b"{}")
        update_manifest(input_dir)
    elif name == "reports_nonempty":
        write_json(input_dir / "reports/placeholders.json", [{"placeholder": "x"}])
        update_manifest(input_dir)
    else:
        raise SystemExit("unknown case: %s" % name)


CASES = (
    ("missing_file", ("MISSING_FILE", "vouchers/contracts.json")),
    ("unknown_file", ("UNKNOWN_FILE", "vouchers/extra.json")),
    ("hash_mismatch", ("HASH_MISMATCH", "bank/transactions.json")),
    ("duplicate_voucher_id", ("ID_DUPLICATE", "vouchers/invoices.json[1].voucher_id")),
    ("missing_required", ("REQUIRED", "vouchers/invoices.json[0].seller_name")),
    ("amount_not_integer", ("TYPE", "vouchers/invoices.json[0].amount_cents")),
    ("amount_not_positive", ("AMOUNT", "vouchers/goods_receipts.json[0].amount_cents")),
    ("total_mismatch", ("ARITHMETIC", "vouchers/invoices.json[0].total_cents")),
    ("date_out_of_range", ("DATE_RANGE", "vouchers/contracts.json[0].sign_date")),
    ("wrong_currency", ("CURRENCY", "vouchers/invoices.json[0].currency")),
    ("dangling_index", ("LINK_VOUCHER", "links/index.json[0].voucher_id")),
    ("duplicate_index", ("LINK_DUPLICATE", "links/index.json[6]")),
    ("nonexistent_ledger_id", ("LINK_LEDGER", "links/index.json[0].ledger_id")),
    ("link_type_mismatch", ("LINK_TYPE_MISMATCH", "links/index.json[0].voucher_id")),
    ("bad_json", ("FILE_BAD_JSON", "links/index.json")),
    ("non_array", ("FILE_NOT_ARRAY", "reports/placeholders.json")),
    ("reports_nonempty", ("REPORTS_PLACEHOLDER", "reports/placeholders.json")),
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-043 输入契约 v1 测试")
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
    if not out_root.name.startswith("task043_"):
        print(json.dumps({"status": "FAIL",
                          "reason": "out-dir 目录名必须以 task043_ 开头"}, ensure_ascii=False))
        return 1
    if not INPUT_V1.is_dir() or not LEDGER_DB.is_file() or not SCRIPT.is_file():
        print(json.dumps({"status": "FAIL", "reason": "缺少输入根/ledger/脚本"}, ensure_ascii=False))
        return 1
    input_before = snapshot(INPUT_V1)
    ledger_before = inode_bytes(LEDGER_DB)
    out_root.mkdir(parents=True)

    results = []

    # 正常
    normal = CaseResult("normal", ("ACCEPTED", "input_registry.json"))
    normal.case_dir = out_root / "normal"
    normal.case_dir.mkdir(parents=True)
    normal.out_dir = normal.case_dir / "task043_normal"
    normal.exit_code, command, stdout, stderr = run_validator(
        INPUT_V1, normal.out_dir, normal.case_dir)
    normal.observed = {"command": command}
    registry_path = normal.out_dir / "input_registry.json"
    if normal.exit_code == 0 and registry_path.is_file():
        registry = read_json(registry_path)
        files = registry.get("files", [])
        actual_mismatch = []
        for entry in files:
            raw = (INPUT_V1 / entry["relative"]).read_bytes()
            if entry["byte_size"] != len(raw) or entry["file_sha256"] != sha_bytes(raw):
                actual_mismatch.append(entry["relative"])
        counts = registry.get("counts", {})
        normal.status = "PASS" if (not actual_mismatch
                                   and registry.get("conclusion") == "INPUT_V1_ACCEPTED"
                                   and counts.get("links") == 6
                                   and counts.get("bank_transactions") == 3
                                   and counts.get("voucher_total") == 6
                                   and counts.get("vouchers") == {"INVOICE": 1, "CONTRACT": 1,
                                                                  "BANK_RECEIPT": 2,
                                                                  "APPROVAL": 1,
                                                                  "GOODS_RECEIPT": 1}) else "FAIL"
        normal.observed.update({"counts": counts,
                                "conclusion": registry.get("conclusion"),
                                "file_count": len(files),
                                "hash_mismatch": actual_mismatch})
        normal.detail = "registry 与输入字节一致" if normal.status == "PASS" else "计数/哈希/结论不符"
    else:
        normal.status = "FAIL"
        normal.detail = "正常输入未生成 registry（exit %r）" % normal.exit_code
    results.append(normal)

    # 负例
    for name, expected in CASES:
        case = CaseResult(name, expected)
        case_dir = prepare_case(out_root, name)
        case.case_dir = case_dir
        case.input_dir = case_dir / "input"
        inject(name, case.input_dir, case_dir)
        case.out_dir = case_dir / "task043_out"
        case.exit_code, command, stdout, stderr = run_validator(
            case.input_dir, case.out_dir, case_dir)
        case.observed = {"command": command}
        expectations_pass(case)
        results.append(case)

    # 只读纪律：规范输入根与 ledger 数据库字节不变
    input_after = snapshot(INPUT_V1)
    ledger_after = inode_bytes(LEDGER_DB)
    read_only_ok = input_before == input_after and ledger_before == ledger_after

    passed = sum(1 for item in results if item.status == "PASS")
    report = {
        "task": "TASK-043",
        "generated_by": "tests/test_input_contract_v1.py",
        "input_version": "task043-input-1.0",
        "canonical_input_root": INPUT_V1.relative_to(ROOT).as_posix(),
        "ledger_db": {"relative": LEDGER_DB.relative_to(ROOT).as_posix(),
                      "byte_size": len(ledger_before), "sha256": sha_bytes(ledger_before)},
        "read_only_ok": read_only_ok,
        "input_root_unchanged": input_before == input_after,
        "ledger_db_unchanged": ledger_before == ledger_after,
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item.name for item in results if item.status != "PASS"],
        "status": "PASS" if passed == len(results) and read_only_ok else "FAIL",
        "cases": [item.to_dict() for item in results],
        "boundaries": {"real_approval": None, "batch_approved": False,
                       "real_initial_judgment_saved": False,
                       "next_step_allowed": False, "ai_enabled": False,
                       "identity_authenticated": False,
                       "audit_conclusion_formed": False},
        "note": "合成数据契约校验；不做匹配、不出核对底稿；不批准真实批次、不认证身份。",
    }
    report_path = out_root / "test_report.json"
    report_path.write_bytes(json.dumps(report, ensure_ascii=False, indent=2,
                                       sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({"status": report["status"], "cases": len(results),
                      "passed": passed, "read_only_ok": read_only_ok,
                      "report": str(report_path)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


def inode_bytes(path: Path) -> bytes:
    return path.read_bytes()


if __name__ == "__main__":
    raise SystemExit(main())
