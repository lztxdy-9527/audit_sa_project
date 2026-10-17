#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-056：GL 六类核对引擎测试（真实 CLI 子进程）。

覆盖：正常（ALL_MATCHED、六类 + 附件、数字与备注）、7 类负例（凭证/试算/账证/账账/账表/
银行/附件，均 exit 1 且字段精确）、确定性、只读（GL 包/ task043 输入/批次不变）、
规模（200 张凭证夹具，六类核对完成，登记耗时/大小）。
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
SCRIPT = ROOT / "scripts/reconcile_gl_v1.py"
GL = ROOT / "data/evidence_inputs/gl_v1"
GL_FILES = ("chart_of_accounts.json", "journal_entries.json", "trial_balance.json",
            "ledger_general.json", "ledger_subsidiary.json", "balance_sheet.json",
            "bank_statement.json", "bank_journal.json", "attachment_index.json",
            "gl_manifest.json")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    result = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = [path.stat().st_size,
                                                         sha(path.read_bytes())]
    return result


def run(gl_root, out_dir, log_dir, name):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / (name + "_stdout.txt")
    stderr = log_dir / (name + "_stderr.txt")
    start = time.monotonic()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        code = subprocess.run([sys.executable, "-B", str(SCRIPT), "--gl-root", str(gl_root),
                               "--out-dir", str(out_dir)], cwd=str(ROOT),
                              stdout=out, stderr=err).returncode
    return code, stdout, stderr, round(time.monotonic() - start, 3)


def mutate(gl_dir, name, field, value, remove=False):
    path = gl_dir / name
    data = json.loads(path.read_bytes())
    parts = field.split(".")
    target = data
    for part in parts[:-1]:
        target = target[int(part)] if part.isdigit() else target[part]
    last = parts[-1]
    if last.isdigit():
        target[int(last)] = value
    else:
        target[last] = value
    path.write_bytes(json.dumps(data, ensure_ascii=False, indent=2,
                                sort_keys=True).encode("utf-8") + b"\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-056 GL 核对引擎测试")
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
    if not out_root.name.startswith(("task056_", "task056r1_")):
        print(json.dumps({"status": "FAIL", "reason": "out-dir 前缀非法"}, ensure_ascii=False))
        return 1
    before = {"gl": snapshot(GL)}
    if (ROOT / "data/evidence_inputs/task043_v1_1").is_dir():
        before["task043"] = snapshot(ROOT / "data/evidence_inputs/task043_v1_1")
    before["batch"] = snapshot(ROOT / "data/batches/task027r1_run_04/batch_normal")
    out_root.mkdir(parents=True)
    results = []

    def record(name, exit_code, checks, observed=None):
        passed = all(checks.values())
        results.append({"case": name, "exit_code": exit_code, "checks": checks,
                        "status": "PASS" if passed else "FAIL", "observed": observed or {}})
        return passed

    normal = out_root / "task056_normal"
    code, stdout, _, elapsed = run(GL, normal, out_root / "logs", "normal")
    report = json.loads((normal / "gl_reconcile_report.json").read_bytes()) \
        if (normal / "gl_reconcile_report.json").is_file() else {}
    by_id = {item["id"]: item for item in report.get("checks") or []}
    checks = {
        "exit_0": code == 0,
        "overall_matched": report.get("summary", {}).get("overall") == "ALL_MATCHED",
        "six_matched": all(by_id.get(name, {}).get("status") == "MATCHED"
                           for name in ("journal_balance", "trial_balance",
                                        "ledger_to_voucher", "general_to_subsidiary",
                                        "ledger_to_report", "bank_reconcile")),
        "attachments_matched": by_id.get("attachments", {}).get("status") == "MATCHED",
        "journal_totals": by_id.get("journal_balance", {}).get("summary", {}).get(
            "debit_total") == 1600000,
        "trial_closing": by_id.get("trial_balance", {}).get("summary", {}).get(
            "closing_debit") == 2000000,
        "report_balanced": by_id.get("ledger_to_report", {}).get("summary", {}).get(
            "assets") == 2000000,
        "bank_closing": by_id.get("bank_reconcile", {}).get("summary", {}).get(
            "statement_closing") == 1100000,
        "notes_reclass": any("应付账款借方余额" in note
                             for note in report.get("summary", {}).get("notes") or []),
        "markdown": (normal / "gl_reconcile_report.md").is_file(),
        "source": (normal / "reconcile_source.json").is_file(),
    }
    record("normal", code, checks,
           {"duration_seconds": elapsed,
            "report_bytes": (normal / "gl_reconcile_report.json").stat().st_size
            if (normal / "gl_reconcile_report.json").is_file() else None})

    negatives = [
        ("journal", "journal_entries.json", "entries.1.lines.1.credit_cents", 500001,
         "journal_balance"),
        ("trial", "trial_balance.json", "rows.1.closing_debit", 1100001, "trial_balance"),
        ("ledger_voucher", "ledger_general.json", "accounts.0.debit_cents", 500001,
         "ledger_to_voucher"),
        ("general_subsidiary", "ledger_general.json", "accounts.2.closing_debit", 400001,
         "general_to_subsidiary"),
        ("report", "balance_sheet.json", "assets.0.amount_cents", 1100001,
         "ledger_to_report"),
        ("bank", "bank_statement.json", "closing_balance_cents", 1100001, "bank_reconcile"),
        ("attachments", "journal_entries.json", "entries.0.attachments", None,
         "attachments"),
        # TASK-056-R1：B1 无明细账科目的总账期末 vs 科目余额表
        ("b1_general_no_subsidiary", "ledger_general.json",
         "accounts.0.closing_debit", 500001, "general_to_subsidiary"),
        # TASK-056-R1：B2 报表合计与分项/资产=负债+权益
        ("b2_report_total", "balance_sheet.json", "total_assets_cents", 2000001,
         "ledger_to_report"),
        # TASK-056-R1：B3 明细账发生额 vs 凭证（账证覆盖明细账）
        ("b3_subsidiary_amount", "ledger_subsidiary.json",
         "subsidiaries.0.entries.0.credit_cents", 500001, "ledger_to_voucher"),
    ]
    for name, filename, field, value, expected_check in negatives:
        fixture = out_root / ("task056_neg_" + name)
        shutil.copytree(GL, fixture)
        if name == "attachments":
            mutate(fixture, "journal_entries.json", "entries.0.attachments",
                   ["V-CTR-0001", "V-GR-0001"])
        else:
            mutate(fixture, filename, field, value)
        neg_out = out_root / ("task056_neg_out_" + name)
        neg_code, neg_stdout, _, _ = run(fixture, neg_out, out_root / "logs", "neg_" + name)
        neg_report = json.loads((neg_out / "gl_reconcile_report.json").read_bytes()) \
            if (neg_out / "gl_reconcile_report.json").is_file() else {}
        neg_checks = {item["id"]: item for item in neg_report.get("checks") or []}
        target = neg_checks.get(expected_check, {})
        findings = target.get("findings") or []
        record("neg_" + name, neg_code,
               {"exit_1": neg_code == 1,
                "differences": neg_report.get("summary", {}).get("overall")
                == "DIFFERENCES_FOUND",
                "check_differences": target.get("status") == "DIFFERENCES",
                "findings_present": bool(findings),
                "field_present": bool(findings and any(
                    key in findings[0] for key in
                    ("entry_id", "account_code", "report_item", "date", "expected",
                     "general_closing", "trial_closing", "expected_total",
                     "actual_total", "ledger_debit")))},
               {"check": expected_check, "findings": findings[:1]})

    det_a = out_root / "task056_det_a"
    det_b = out_root / "task056_det_b"
    code_a, _, _, _ = run(GL, det_a, out_root / "logs", "det_a")
    code_b, _, _, _ = run(GL, det_b, out_root / "logs", "det_b")
    names = ["gl_reconcile_report.json", "gl_reconcile_report.md"]
    same = code_a == 0 and code_b == 0 and all(
        (det_a / name).read_bytes() == (det_b / name).read_bytes() for name in names)
    record("determinism", 0, {"both_exit_0": code_a == 0 and code_b == 0,
                              "identical": same})

    # 规模：200 张凭证夹具（复制 GL 包，仅测试用）
    scale = out_root / "task056_scale_gl"
    shutil.copytree(GL, scale)
    journal = json.loads((scale / "journal_entries.json").read_bytes())
    base = journal["entries"]
    entries = []
    for index in range(200):
        source = base[index % len(base)]
        entries.append({"entry_id": "记-%03d" % (index + 1),
                        "date": source["date"], "summary": source["summary"],
                        "lines": source["lines"], "attachments": source["attachments"]})
    journal["entries"] = entries
    (scale / "journal_entries.json").write_bytes(
        json.dumps(journal, ensure_ascii=False, indent=2,
                   sort_keys=True).encode("utf-8") + b"\n")
    scale_out = out_root / "task056_scale_out"
    scale_code, _, _, scale_time = run(scale, scale_out, out_root / "logs", "scale")
    scale_report = json.loads((scale_out / "gl_reconcile_report.json").read_bytes()) \
        if (scale_out / "gl_reconcile_report.json").is_file() else {}
    record("scale_200", scale_code,
           {"completed": scale_code in (0, 1),
            "seven_checks": len(scale_report.get("checks") or []) == 7},
           {"duration_seconds": scale_time,
            "report_bytes": (scale_out / "gl_reconcile_report.json").stat().st_size
            if (scale_out / "gl_reconcile_report.json").is_file() else None})

    after = {"gl": snapshot(GL)}
    if (ROOT / "data/evidence_inputs/task043_v1_1").is_dir():
        after["task043"] = snapshot(ROOT / "data/evidence_inputs/task043_v1_1")
    after["batch"] = snapshot(ROOT / "data/batches/task027r1_run_04/batch_normal")
    passed = sum(1 for item in results if item["status"] == "PASS")
    report_data = {
        "task": "TASK-056",
        "generated_by": "tests/test_gl_reconcile.py",
        "read_only_ok": before == after,
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item["case"] for item in results if item["status"] != "PASS"],
        "status": "PASS" if passed == len(results) and before == after else "FAIL",
        "cases": results,
        "note": "六类核对 + 附件；负例逐一精确字段；200 张凭证规模完成；只读 GL/ task043/批次。",
        "boundaries": {"audit_conclusion": False, "real_approval": None,
                       "real_initial_judgment_saved": False, "next_step_allowed": False,
                       "ai_enabled": False},
    }
    report_path = out_root / "test_report.json"
    report_path.write_bytes(json.dumps(report_data, ensure_ascii=False, indent=2,
                                       sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({"status": report_data["status"], "cases": len(results),
                      "passed": passed, "read_only_ok": report_data["read_only_ok"],
                      "report": str(report_path)}, ensure_ascii=False))
    return 0 if report_data["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
