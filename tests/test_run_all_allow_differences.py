#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-059-R2：`run_all.py --allow-differences` 开关测试（真实 CLI 子进程）。

覆盖：
  1) 默认（不加开关）：账证差异包 → 第 3 步 demo 失败、exit 1、不发布 index.html；
  2) 加开关：同一包 → 七步全跑完、exit 0、overall=SUCCESS_WITH_DIFFERENCES、
     demo 步 tolerated=true、站点出现 >1 条 case（R02 线索 + 账证差异）；
  3) 加开关但失败发生在第 1 步（契约）→ 仍然失败即停；
  4) 加开关但失败发生在第 2 步（GL 契约）→ 仍然失败即停；
  5) 只读：差异输入包与账务库前后哈希不变。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
SCRIPT = ROOT / "scripts/run_all.py"
CANONICAL = ROOT / "data/evidence_inputs/task043_v1_1"
GL = ROOT / "data/evidence_inputs/gl_v1"
BATCH = ROOT / "data/batches/task027r1_run_04/batch_normal"
LEDGER = ROOT / "data/sqlite_tests/task042_dsh_01/normal/runtime.sqlite3"
EXPECTED_FILES = (
    "bank/transactions.json", "links/index.json", "reports/placeholders.json",
    "vouchers/approvals.json", "vouchers/bank_receipts.json",
    "vouchers/contracts.json", "vouchers/goods_receipts.json",
    "vouchers/invoices.json",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): [path.stat().st_size, sha(path.read_bytes())]
            for path in sorted(Path(root).rglob("*")) if path.is_file()}


def write_json(path: Path, payload) -> None:
    path.write_bytes(json.dumps(payload, ensure_ascii=False, indent=2,
                                sort_keys=True).encode("utf-8") + b"\n")


def make_diff_package(target: Path) -> None:
    """复制规范包，把发票金额 +1 分（算术仍自洽 → 契约过、账证差异）。"""
    shutil.copytree(CANONICAL, target)
    invoices_path = target / "vouchers/invoices.json"
    invoices = json.loads(invoices_path.read_bytes())
    invoices[0]["amount_cents"] += 1
    invoices[0]["total_cents"] += 1
    write_json(invoices_path, invoices)
    manifest_path = target / "input_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    entries = []
    for relative in sorted(EXPECTED_FILES):
        raw = (target / relative).read_bytes()
        entries.append({"relative": relative, "byte_size": len(raw),
                        "sha256": sha(raw)})
    manifest["files"] = entries
    write_json(manifest_path, manifest)


def make_config(path: Path, task043: Path, gl_root: Path) -> None:
    write_json(path, {
        "inputs": {"batch_dir": str(BATCH), "task043_input_root": str(task043),
                   "ledger_db": str(LEDGER), "gl_root": str(gl_root)},
        "output_root": str(path.parent / ("outputs_" + path.stem)),
        "open_browser": False, "review_notes": None,
    })


def run_all(args, log_dir: Path, name: str) -> int:
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / (name + "_stdout.txt")).open("wb") as out, \
            (log_dir / (name + "_stderr.txt")).open("wb") as err:
        return subprocess.run([sys.executable, "-B", str(SCRIPT)] + args,
                              cwd=str(ROOT), stdout=out, stderr=err).returncode


def summary_of(output_root: Path, run_id: str) -> dict:
    path = output_root / run_id / "run_summary.json"
    return json.loads(path.read_bytes()) if path.is_file() else {}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TASK-059-R2 允许差异开关测试")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    out_root = Path(args.out_dir)
    if not out_root.is_absolute():
        out_root = (Path.cwd() / out_root).resolve()
    if out_root.exists():
        print(json.dumps({"status": "FAIL", "reason": "out-dir 必须从未存在"},
                         ensure_ascii=False))
        return 1
    try:
        out_root.relative_to(TEST_ROOT.resolve())
    except ValueError:
        print(json.dumps({"status": "FAIL", "reason": "out-dir 必须位于测试根下"},
                         ensure_ascii=False))
        return 1
    if not out_root.name.startswith(("task059_", "task059r1_", "task059r2_")):
        print(json.dumps({"status": "FAIL", "reason": "out-dir 前缀非法"}, ensure_ascii=False))
        return 1
    out_root.mkdir(parents=True)
    stamp = time.strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(3)

    diff_input = out_root / "diff_input"
    make_diff_package(diff_input)
    diff_snapshot_before = snapshot(diff_input)
    ledger_before = sha(LEDGER.read_bytes())

    diff_config = out_root / "diff_config.json"
    make_config(diff_config, diff_input, GL)
    outputs_root = out_root / ("outputs_" + stamp)
    logs = out_root / "logs"

    bad_input = out_root / "bad_input"
    bad_input.mkdir()
    (bad_input / "input_manifest.json").write_text("{}", encoding="utf-8")
    bad_input_config = out_root / "bad_input_config.json"
    make_config(bad_input_config, bad_input, GL)

    bad_gl = out_root / "bad_gl"
    shutil.copytree(GL, bad_gl)
    trial_path = bad_gl / "trial_balance.json"
    trial = json.loads(trial_path.read_bytes())
    trial["rows"][0]["closing_debit"] = 1
    write_json(trial_path, trial)
    bad_gl_config = out_root / "bad_gl_config.json"
    make_config(bad_gl_config, diff_input, bad_gl)

    results = []

    def record(name: str, checks: dict, observed=None) -> None:
        passed = all(checks.values())
        results.append({"case": name, "checks": checks,
                        "status": "PASS" if passed else "FAIL",
                        "observed": observed or {}})

    # 1) 默认：差异 → demo 失败、无 index
    run_id = "diff_off_" + stamp
    code = run_all(["--config", str(diff_config), "--out-root", str(outputs_root),
                    "--run-id", run_id, "--no-open"], logs, "diff_off")
    summary = summary_of(outputs_root, run_id)
    record("diff_without_flag", {
        "exit_1": code == 1,
        "failed_step_demo": summary.get("failed_step") == "demo",
        "overall_failed": summary.get("overall") == "FAILED",
        "no_index": not (outputs_root / run_id / "index.html").exists(),
        "not_tolerated": summary.get("differences_tolerated") is False,
    }, {"failed_step": summary.get("failed_step")})

    # 2) 加开关：同一包 → 跑完并出站点，多 case
    run_id = "diff_on_" + stamp
    code = run_all(["--config", str(diff_config), "--out-root", str(outputs_root),
                    "--run-id", run_id, "--no-open", "--allow-differences"],
                   logs, "diff_on")
    summary = summary_of(outputs_root, run_id)
    index_dir = TEST_ROOT / ("task057_index_runall_" + run_id)
    trace_path = index_dir / "trace_index.json"
    trace = json.loads(trace_path.read_bytes()) if trace_path.is_file() else {}
    cases = trace.get("cases") or []
    kinds = sorted({case.get("kind") for case in cases})
    site_dir = TEST_ROOT / ("task057_site_runall_" + run_id)
    demo_step = next((step for step in summary.get("steps") or []
                      if step.get("id") == "demo"), {})
    record("diff_with_flag", {
        "exit_0": code == 0,
        "overall_swd": summary.get("overall") == "SUCCESS_WITH_DIFFERENCES",
        "failed_step_none": summary.get("failed_step") is None,
        "tolerated_true": summary.get("differences_tolerated") is True,
        "tolerated_steps_demo": summary.get("tolerated_steps") == ["demo"],
        "demo_step_tolerated": demo_step.get("tolerated") is True,
        "index_published": (outputs_root / run_id / "index.html").is_file(),
        "seven_steps": [step.get("id") for step in summary.get("steps") or []] == [
            "input_contract", "gl_contract", "demo", "gl_reconcile",
            "trace_index", "site", "workbook"],
        "case_pages_gt_1": len(list((outputs_root / run_id).glob("case-*.html"))) > 1,
        "has_voucher_difference": "VOUCHER_DIFFERENCE" in kinds,
        "site_pages": len(list(site_dir.glob("*.html"))) > 1,
        "read_only": summary.get("read_only_ok") is True,
    }, {"cases": len(cases), "kinds": kinds,
        "case_pages": len(list((outputs_root / run_id).glob("case-*.html")))})

    # 3) 加开关但第 1 步失败
    run_id = "bad_input_on_" + stamp
    code = run_all(["--config", str(bad_input_config), "--out-root", str(outputs_root),
                    "--run-id", run_id, "--no-open", "--allow-differences"],
                   logs, "bad_input_on")
    summary = summary_of(outputs_root, run_id)
    record("flag_does_not_mask_input_contract", {
        "exit_1": code == 1,
        "failed_step_input": summary.get("failed_step") == "input_contract",
        "overall_failed": summary.get("overall") == "FAILED",
        "no_index": not (outputs_root / run_id / "index.html").exists(),
    })

    # 4) 加开关但第 2 步失败
    run_id = "bad_gl_on_" + stamp
    code = run_all(["--config", str(bad_gl_config), "--out-root", str(outputs_root),
                    "--run-id", run_id, "--no-open", "--allow-differences"],
                   logs, "bad_gl_on")
    summary = summary_of(outputs_root, run_id)
    record("flag_does_not_mask_gl_contract", {
        "exit_1": code == 1,
        "failed_step_gl": summary.get("failed_step") == "gl_contract",
        "overall_failed": summary.get("overall") == "FAILED",
        "no_index": not (outputs_root / run_id / "index.html").exists(),
    })

    read_only_ok = (snapshot(diff_input) == diff_snapshot_before
                    and sha(LEDGER.read_bytes()) == ledger_before)
    passed = sum(1 for item in results if item["status"] == "PASS")
    report = {
        "task": "TASK-059-R2",
        "generated_by": "tests/test_run_all_allow_differences.py",
        "read_only_ok": read_only_ok,
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item["case"] for item in results if item["status"] != "PASS"],
        "status": "PASS" if passed == len(results) and read_only_ok else "FAIL",
        "cases": results,
        "note": "开关只容忍第 3 步的四相符差异；契约/GL/索引/站点失败仍然失败即停。",
    }
    report_path = out_root / "test_report.json"
    write_json(report_path, report)
    print(json.dumps({"status": report["status"], "cases": len(results),
                      "passed": passed, "read_only_ok": read_only_ok,
                      "report": str(report_path)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
