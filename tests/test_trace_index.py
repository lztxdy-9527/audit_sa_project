#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-051：证据链索引 v1.1 测试（全量 + 状态 + 源漂移 + 审阅占位）。

覆盖：全量计数（台账 7 / 凭证 8 / 原表行 9 / 事项 1）、状态分布、source_identity 与
source_drift=OK、每案 review 占位；源漂移（复制批次源改 1 字节 → exit 1、source_drift、
原文件不变）；确定性；只读；负例（悬空引用 exit 1、缺 demo_summary exit 2）。
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
RUN_ROOT = TEST_ROOT / "task046_demo_01"
SCRIPT = ROOT / "scripts/build_trace_index.py"
BATCH = ROOT / "data/batches/task027r1_run_04/batch_normal"
BUSINESS_FACT = ROOT / "data/runtime/task046_demo_01/normal.facts/fact_packet.json"
BUSINESS_JUDGMENT = ROOT / "data/human_initial_judgment_records/task046_demo_01/bound/rec_0001/judgment_result.json"
BUSINESS_MANIFEST = ROOT / "data/human_initial_judgment_records/task046_demo_01/bound/rec_0001/manifest.json"
NORMALIZED = ROOT / "data/runtime/task042_dsh_01/normal.load/normalized.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    result = {}
    for item in sorted(Path(root).rglob("*")):
        if item.is_file():
            result[item.relative_to(root).as_posix()] = [item.stat().st_size,
                                                         sha(item.read_bytes())]
    return result


def file_snapshot(paths):
    return {str(path): [path.stat().st_size, sha(path.read_bytes())] for path in paths}


def copy_business(run_name):
    fact = ROOT / "data/runtime" / run_name / "normal.facts/fact_packet.json"
    record = ROOT / "data/human_initial_judgment_records" / run_name / "bound/rec_0001"
    fact.parent.mkdir(parents=True, exist_ok=True)
    record.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUSINESS_FACT, fact)
    shutil.copy2(BUSINESS_JUDGMENT, record / "judgment_result.json")
    shutil.copy2(BUSINESS_MANIFEST, record / "manifest.json")


def run_cli(run_root, out_dir, log_dir, batch_dir=None, gl_root=None, gl_report=None):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / "stdout.txt"
    stderr = log_dir / "stderr.txt"
    command = [sys.executable, "-B", str(SCRIPT), "--run-root", str(run_root),
               "--out-dir", str(out_dir)]
    if batch_dir is not None:
        command.extend(["--batch-dir", str(batch_dir)])
    if gl_root is not None:
        command.extend(["--gl-root", str(gl_root)])
    if gl_report is not None:
        command.extend(["--gl-report", str(gl_report)])
    start = time.monotonic()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        completed = subprocess.run(command, cwd=str(ROOT), stdout=out, stderr=err)
    return completed.returncode, command, stdout, stderr, time.monotonic() - start


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-051 证据链索引 v1.1 测试")
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
        print(json.dumps({"status": "FAIL",
                          "reason": "out-dir 必须位于 %s 之下" % TEST_ROOT},
                         ensure_ascii=False))
        return 1
    if not out_root.name.startswith(("task048_", "task051_", "task052_", "task057_")):
        print(json.dumps({"status": "FAIL",
                          "reason": "out-dir 目录名必须以 task048_、task051_ 或 task052_ 开头"},
                         ensure_ascii=False))
        return 1
    suffix = out_root.name
    inputs_before = {
        "run_root": snapshot(RUN_ROOT),
        "business": file_snapshot((BUSINESS_FACT, BUSINESS_JUDGMENT, BUSINESS_MANIFEST)),
        "evidence_inputs": snapshot(ROOT / "data/evidence_inputs"),
        "batch": snapshot(BATCH),
        "normalized": file_snapshot((NORMALIZED,)),
    }
    out_root.mkdir(parents=True)
    results = []

    def record(name, exit_code, checks, observed=None):
        passed = all(checks.values())
        results.append({"case": name, "exit_code": exit_code, "checks": checks,
                        "status": "PASS" if passed else "FAIL",
                        "observed": observed or {}})
        return passed

    # 1. 正常（全量索引 v1.1）
    case = out_root / "normal"
    case.mkdir(parents=True)
    report = out_root / "task051_index_01"
    code, command, stdout, stderr, elapsed = run_cli(RUN_ROOT, report, case)
    data = json.loads((report / "trace_index.json").read_bytes()) if report.is_dir() else {}
    meta = data.get("meta") or {}
    cases = data.get("cases") or []
    ledger = data.get("ledger") or []
    statuses = {}
    for row in ledger:
        statuses[row.get("status")] = statuses.get(row.get("status"), 0) + 1
    checks = {
        "exit_0": code == 0,
        "version_1_2": meta.get("index_version") == "TASK-048-trace-index-1.2",
        "cases_1": meta.get("cases_total") == 1 and len(cases) == 1,
        "ledger_full_7": meta.get("ledger_total") == 7 and len(ledger) == 7,
        "vouchers_full_8": meta.get("voucher_total") == 8
        and len(data.get("vouchers") or []) == 8,
        "source_rows_full_9": meta.get("source_rows_total") == 9
        and len(data.get("source_rows") or []) == 9,
        "status_distribution": statuses.get("已核对一致") == 4
        and statuses.get("未涉及") == 3,
        "source_drift_ok": ((meta.get("source_identity") or {}).get("source_drift")
                            or {}).get("status") == "OK",
        "source_sha_matches": ((meta.get("source_identity") or {}).get("sha256")
                               == sha(BATCH.joinpath("source/input.xlsx").read_bytes())),
        "review_placeholder": all((case.get("review") or {}).get("status") == "待审阅"
                                  for case in cases)
        and all((row.get("review") or {}).get("status") == "待审阅" for row in ledger)
        and all((row.get("review") or {}).get("status") == "待审阅"
                for row in data.get("vouchers") or [])
        and all((row.get("review") or {}).get("status") == "待审阅"
                for row in data.get("source_rows") or []),
        "voucher_status": all(v.get("status") == "已取得"
                              for v in data.get("vouchers") or []),
    }
    record("normal_v1_1", code, checks,
           {"command": [str(item) for item in command],
            "index_bytes": (report / "trace_index.json").stat().st_size
            if report.is_dir() else None,
            "duration_seconds": round(elapsed, 3),
            "status_counts": statuses})

    # 1b. GL 节（TASK-057）：含 gl 时只读复制，checks 与核对报告一致
    gl_report = TEST_ROOT / "task056r1_gl_01/gl_reconcile_report.json"
    gl_root = ROOT / "data/evidence_inputs/gl_v1"
    if gl_root.is_dir() and gl_report.is_file():
        gl_index = out_root / "task057_index_gl"
        code, _, _, _, _ = run_cli(RUN_ROOT, gl_index, out_root / "gl_logs",
                                   gl_root=gl_root, gl_report=gl_report)
        gl_data = json.loads((gl_index / "trace_index.json").read_bytes()) \
            if gl_index.is_dir() else {}
        gl = gl_data.get("gl") or {}
        report = json.loads(gl_report.read_bytes())
        entries = {entry.get("entry_id"): entry for entry in gl.get("journal_entries") or []}
        checks = {
            "exit_0": code == 0,
            "gl_present": bool(gl),
            "checks_match": [item.get("status") for item in gl.get("checks") or []]
            == [item.get("status") for item in report.get("checks") or []],
            "seven_checks": len(gl.get("checks") or []) == 7,
            "overall": (gl.get("summary") or {}).get("overall") == "ALL_MATCHED",
            "entry_links": all(entries.get(entry_id, {}).get("ledger_refs", [{}])[0].get("ledger_id") == ledger_id
                               for entry_id, ledger_id in (("记-001", "AP01"), ("记-002", "P01"),
                                                           ("记-003", "P02"), ("记-004", "R01"))),
            "case_links": all("CASE-0001" in entries.get(entry_id, {}).get("case_refs", [])
                              for entry_id in ("记-001", "记-002", "记-003", "记-004")),
            "trial_totals": (gl.get("trial_balance") or {}).get("totals", {}).get(
                "closing_debit") == 2000000,
            "source_files": len((gl.get("source") or {}).get("files") or []) == 9,
        }
        record("gl_section", code, checks,
               {"gl_files": len((gl.get("source") or {}).get("files") or [])})
    else:
        record("gl_section", 1, {"missing_inputs": False})

    # 2. 源漂移：复制批次源、改 1 字节 → exit 1、source_drift、原文件不变
    drift_batch = TEST_ROOT / ("task051_drift_batch_" + suffix)
    if drift_batch.exists():
        print(json.dumps({"status": "FAIL", "reason": "fixture exists"}, ensure_ascii=False))
        return 1
    shutil.copytree(BATCH, drift_batch)
    source = drift_batch / "source/input.xlsx"
    raw = bytearray(source.read_bytes())
    raw[-1] = (raw[-1] + 1) % 256
    source.write_bytes(bytes(raw))
    code, _, stdout, _, _ = run_cli(RUN_ROOT, out_root / "task051_index_drift",
                                    out_root / "drift_logs", drift_batch)
    observed = json.loads(stdout.read_bytes()) if stdout.is_file() else {}
    record("source_drift", code,
           {"exit_1": code == 1, "kind_content": observed.get("kind") == "content",
            "source_drift_reported": "source_drift" in str(observed.get("error")),
            "no_index_written": not (out_root / "task051_index_drift/trace_index.json").is_file()})

    # 3. 确定性
    det_a = out_root / "task051_index_det_a"
    det_b = out_root / "task051_index_det_b"
    code_a, _, _, _, _ = run_cli(RUN_ROOT, det_a, out_root / "det_a_logs")
    code_b, _, _, _, _ = run_cli(RUN_ROOT, det_b, out_root / "det_b_logs")
    record("determinism", 0,
           {"both_exit_0": code_a == 0 and code_b == 0,
            "index_identical": (det_a / "trace_index.json").read_bytes()
            == (det_b / "trace_index.json").read_bytes()})

    # 4. 负例：悬空引用
    dangling_root = TEST_ROOT / ("task051_dangling_run_" + suffix)
    if dangling_root.exists():
        print(json.dumps({"status": "FAIL", "reason": "fixture exists"}, ensure_ascii=False))
        return 1
    shutil.copytree(RUN_ROOT, dangling_root)
    copy_business(dangling_root.name)
    dpath = dangling_root / "task044_match/voucher_match_report.json"
    droot = json.loads(dpath.read_bytes())
    droot["differences"] = [{"ledger_type": "AP", "ledger_id": "AP99",
                             "voucher_id": "V-INV-0001", "voucher_type": "INVOICE",
                             "field": "amount_cents", "actual": 1, "expected": 2,
                             "classification": "AMOUNT_MISMATCH"}]
    droot["summary"]["differences_total"] = 1
    droot["conclusion"] = "DIFFERENCES_FOUND"
    dpath.write_bytes(json.dumps(droot, ensure_ascii=False, indent=2,
                                 sort_keys=True).encode("utf-8") + b"\n")
    code, _, stdout, _, _ = run_cli(dangling_root, out_root / "task051_index_dangling",
                                    out_root / "dangling_logs")
    observed = json.loads(stdout.read_bytes()) if stdout.is_file() else {}
    record("neg_dangling", code,
           {"exit_1": code == 1, "kind_content": observed.get("kind") == "content",
            "field_ap99": "AP99" in str(observed.get("field"))})

    # 5. 负例：缺 demo_summary
    missing_root = TEST_ROOT / ("task051_missing_run_" + suffix)
    if missing_root.exists():
        print(json.dumps({"status": "FAIL", "reason": "fixture exists"}, ensure_ascii=False))
        return 1
    shutil.copytree(RUN_ROOT, missing_root)
    (missing_root / "demo_summary.json").unlink()
    code, _, stdout, _, _ = run_cli(missing_root, out_root / "task051_index_missing",
                                    out_root / "missing_logs")
    observed = json.loads(stdout.read_bytes()) if stdout.is_file() else {}
    record("neg_missing_summary", code,
           {"exit_2": code == 2, "field_demo_summary": observed.get("field") == "demo_summary"})

    inputs_after = {
        "run_root": snapshot(RUN_ROOT),
        "business": file_snapshot((BUSINESS_FACT, BUSINESS_JUDGMENT, BUSINESS_MANIFEST)),
        "evidence_inputs": snapshot(ROOT / "data/evidence_inputs"),
        "batch": snapshot(BATCH),
        "normalized": file_snapshot((NORMALIZED,)),
    }
    passed = sum(1 for item in results if item["status"] == "PASS")
    report_data = {
        "task": "TASK-051",
        "generated_by": "tests/test_trace_index.py",
        "run_root": RUN_ROOT.relative_to(ROOT).as_posix(),
        "read_only_ok": inputs_before == inputs_after,
        "read_only_detail": {key: inputs_before[key] == inputs_after[key]
                             for key in inputs_before},
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item["case"] for item in results if item["status"] != "PASS"],
        "status": "PASS" if passed == len(results) and inputs_before == inputs_after else "FAIL",
        "cases": results,
        "note": "v1.1 全量索引、状态、源漂移、确定性、负例均以真实 CLI 子进程验证；批次源只读。",
        "boundaries": {"real_approval": None, "batch_approved": False,
                       "real_initial_judgment_saved": False,
                       "next_step_allowed": False, "ai_enabled": False,
                       "identity_authenticated": False,
                       "audit_conclusion_formed": False},
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
