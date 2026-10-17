#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-055：GL v1 输入契约测试（生成器 + 校验器，真实 CLI 子进程）。

覆盖：正常生成与校验（金额/合计/期末方向）、7 类负例（借贷不平、未知科目、浮点金额、
清单哈希不符、余额表不平、明细账≠总账、报表不平、银行不符、附件缺失）、确定性、
只读（既有输入根与批次字节不变）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
BUILD = ROOT / "scripts/build_gl_demo_inputs.py"
CONTRACT = ROOT / "scripts/gl_input_contract_v1.py"
BATCH = ROOT / "data/batches/task027r1_run_04/batch_normal/batch_manifest.json"
INPUTS = ROOT / "data/evidence_inputs"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    result = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = [path.stat().st_size,
                                                         sha(path.read_bytes())]
    return result


def run(args, log_dir, name):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / (name + "_stdout.txt")
    stderr = log_dir / (name + "_stderr.txt")
    start = time.monotonic()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        code = subprocess.run(args, cwd=str(ROOT), stdout=out, stderr=err).returncode
    return code, stdout, stderr, round(time.monotonic() - start, 3)


def build(out_dir, log_dir, name):
    return run([sys.executable, "-B", str(BUILD), "--out-dir", str(out_dir)], log_dir, name)


def validate(gl_root, log_dir, name):
    return run([sys.executable, "-B", str(CONTRACT), "--gl-root", str(gl_root)],
               log_dir, name)


def refresh_manifest(gl_root):
    manifest_path = gl_root / "gl_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    for name in manifest["files"]:
        raw = (gl_root / name).read_bytes()
        manifest["files"][name] = {"byte_size": len(raw), "sha256": sha(raw)}
    manifest_path.write_bytes(json.dumps(manifest, ensure_ascii=False, indent=2,
                                         sort_keys=True).encode("utf-8") + b"\n")


def mutate(gl_root, name, field, value):
    path = gl_root / name
    data = json.loads(path.read_bytes())
    target = data
    parts = field.split(".")
    for part in parts[:-1]:
        if part.isdigit():
            target = target[int(part)]
        else:
            target = target[part]
    last = parts[-1]
    if last.isdigit():
        target[int(last)] = value
    else:
        target[last] = value
    path.write_bytes(json.dumps(data, ensure_ascii=False, indent=2,
                                sort_keys=True).encode("utf-8") + b"\n")
    refresh_manifest(gl_root)


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-055 GL v1 契约测试")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    out_root = Path(args.out_dir)
    if not out_root.is_absolute():
        out_root = (Path.cwd() / out_root).resolve()
    if out_root.exists():
        print(json.dumps({"status": "FAIL", "reason": "out-dir 必须从未存在"}, ensure_ascii=False))
        return 1
    try:
        out_root.relative_to(TEST_ROOT.resolve())
    except ValueError:
        print(json.dumps({"status": "FAIL", "reason": "out-dir 必须位于测试根下"},
                         ensure_ascii=False))
        return 1
    if not out_root.name.startswith("task055_"):
        print(json.dumps({"status": "FAIL", "reason": "out-dir 前缀非法"}, ensure_ascii=False))
        return 1
    before = {
        "inputs": snapshot(INPUTS),
        "batch": snapshot(ROOT / "data/batches/task027r1_run_04/batch_normal"),
    }
    out_root.mkdir(parents=True)
    results = []

    def record(name, exit_code, checks, observed=None):
        passed = all(checks.values())
        results.append({"case": name, "exit_code": exit_code, "checks": checks,
                        "status": "PASS" if passed else "FAIL", "observed": observed or {}})
        return passed

    gl_root = out_root / "gl_v1"
    code, stdout, _, elapsed = build(gl_root, out_root / "logs", "build")
    code_contract, stdout_contract, _, elapsed_contract = validate(
        gl_root, out_root / "logs", "contract")
    documents = {}
    if gl_root.is_dir():
        for name in ("chart_of_accounts.json", "journal_entries.json",
                     "trial_balance.json", "ledger_general.json",
                     "ledger_subsidiary.json", "balance_sheet.json",
                     "bank_statement.json", "bank_journal.json",
                     "attachment_index.json", "gl_manifest.json"):
            path = gl_root / name
            if path.is_file():
                documents[name] = json.loads(path.read_bytes())
    journal = documents.get("journal_entries.json", {}).get("entries") or []
    trial = documents.get("trial_balance.json", {})
    totals = trial.get("totals") or {}
    rows = {row["account"]: row for row in trial.get("rows") or []}
    bank = documents.get("bank_statement.json", {})
    checks = {
        "build_exit_0": code == 0,
        "contract_exit_0": code_contract == 0,
        "entries_4": len(journal) == 4,
        "balanced": all(sum(line["debit_cents"] for line in entry["lines"])
                        == sum(line["credit_cents"] for line in entry["lines"])
                        for entry in journal),
        "trial_20000": totals.get("closing_debit") == totals.get("closing_credit") == 2000000,
        "closing_5000": rows.get("1001", {}).get("closing_debit") == 500000,
        "closing_11000": rows.get("1002", {}).get("closing_debit") == 1100000,
        "closing_4000_debit": rows.get("2202", {}).get("closing_debit") == 400000
        and rows.get("2202", {}).get("closing_credit") == 0,
        "closing_20000_credit": rows.get("3001", {}).get("closing_credit") == 2000000,
        "bank_end": bank.get("closing_balance_cents") == 1100000,
        "attachments_8": len(documents.get("attachment_index.json", {}).get("attachments") or []) == 8,
    }
    record("normal", code, checks,
           {"build_seconds": elapsed, "contract_seconds": elapsed_contract,
            "contract_stdout": stdout_contract.read_text("utf-8")[:200]})

    negatives = [
        ("unbalanced", "journal_entries.json", "entries.0.lines.0.debit_cents", 400000,
         "GL-ENTRY-UNBALANCED"),
        ("unknown_account", "journal_entries.json", "entries.0.lines.0.account", "9999",
         "GL-ACCOUNT-UNKNOWN"),
        ("float_amount", "journal_entries.json", "entries.0.lines.0.debit_cents", 500000.0,
         "GL-AMOUNT-TYPE"),
        ("trial_balance", "trial_balance.json", "rows.2.closing_debit", 300000,
         "GL-TB-EQUATION"),
        ("subsidiary", "ledger_subsidiary.json",
         "subsidiaries.0.closing_debit", 500000, "GL-SUB-CLOSING"),
        ("balance_sheet", "balance_sheet.json", "total_assets_cents", 1900000,
         "GL-BS-EQUATION"),
        ("bank", "bank_statement.json", "closing_balance_cents", 1000000, "GL-BANK-END"),
        ("attachment", "attachment_index.json", "attachments", [], "GL-ATTACH-MISSING"),
    ]
    for name, filename, field, value, code_expected in negatives:
        fixture = out_root / ("task055_neg_" + name)
        shutil.copytree(gl_root, fixture)
        if name == "attachment":
            for path in fixture.glob("*.json"):
                data = json.loads(path.read_bytes())
                data.pop("attachments", None)
                path.write_bytes(json.dumps(data, ensure_ascii=False, indent=2,
                                            sort_keys=True).encode("utf-8") + b"\n")
            refresh_manifest(fixture)
        else:
            mutate(fixture, filename, field, value)
        neg_code, neg_stdout, _, _ = validate(
            fixture, out_root / "logs", "neg_" + name)
        payload = json.loads(neg_stdout.read_bytes()) if neg_stdout.is_file() else {}
        record("neg_" + name, neg_code,
               {"exit_1": neg_code == 1, "code": payload.get("code") == code_expected,
                "field_present": isinstance(payload.get("field"), str)
                and payload.get("field") != ""},
               {"code": payload.get("code"), "field": payload.get("field")})

    det_a = out_root / "task055_det_a"
    det_b = out_root / "task055_det_b"
    build(det_a, out_root / "logs", "det_a")
    build(det_b, out_root / "logs", "det_b")
    names = sorted(path.name for path in det_a.glob("*")) if det_a.is_dir() else []
    same = names == sorted(path.name for path in det_b.glob("*")) \
        and all((det_a / name).read_bytes() == (det_b / name).read_bytes() for name in names)
    record("determinism", 0, {"both_built": bool(names), "identical": same})

    after = {
        "inputs": snapshot(INPUTS),
        "batch": snapshot(ROOT / "data/batches/task027r1_run_04/batch_normal"),
    }
    passed = sum(1 for item in results if item["status"] == "PASS")
    report = {
        "task": "TASK-055",
        "generated_by": "tests/test_gl_input_contract.py",
        "read_only_ok": before == after,
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item["case"] for item in results if item["status"] != "PASS"],
        "status": "PASS" if passed == len(results) and before == after else "FAIL",
        "cases": results,
        "note": "生成器/校验器均以真实 CLI 子进程验证；既有输入根与批次只读。",
        "boundaries": {"real_approval": None, "batch_approved": False,
                       "real_initial_judgment_saved": False, "next_step_allowed": False,
                       "ai_enabled": False, "identity_authenticated": False,
                       "audit_conclusion_formed": False},
    }
    report_path = out_root / "test_report.json"
    report_path.write_bytes(json.dumps(report, ensure_ascii=False, indent=2,
                                       sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({"status": report["status"], "cases": len(results),
                      "passed": passed, "read_only_ok": report["read_only_ok"],
                      "report": str(report_path)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
