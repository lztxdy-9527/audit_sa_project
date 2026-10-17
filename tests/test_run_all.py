#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-059：一键对账启动器测试（真实 CLI 子进程）。

覆盖：正常七步成功并发布 index.html/gl/excel/logs/run_summary；输入缺文件、GL 契约坏两类失败
（exit 1、无 index.html、run_summary FAILED）；输出目录已存在拒绝（exit 2）；启动器与配置；
确定性（两个 run-id 的 index.html/gl/excel 字节相同）；只读（输入根/批次哈希不变）。
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
CONFIG = ROOT / "config/run_all.json"
GL = ROOT / "data/evidence_inputs/gl_v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    result = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = [path.stat().st_size,
                                                         sha(path.read_bytes())]
    return result


def run_all(args, log_dir, name):
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / (name + "_stdout.txt")).open("wb") as out, \
            (log_dir / (name + "_stderr.txt")).open("wb") as err:
        code = subprocess.run([sys.executable, "-B", str(SCRIPT)] + args, cwd=str(ROOT),
                              stdout=out, stderr=err).returncode
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-059 一键对账测试")
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
    if not out_root.name.startswith(("task059_", "task059r1_")):
        print(json.dumps({"status": "FAIL", "reason": "out-dir 前缀非法"}, ensure_ascii=False))
        return 1
    out_root.mkdir(parents=True)
    stamp = time.strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(3)
    run_normal = "normal_" + stamp
    run_bad_input = "bad_input_" + stamp
    run_bad_gl = "bad_gl_" + stamp
    run_det_a = "det_a_" + stamp
    run_det_b = "det_b_" + stamp
    results = []
    inputs_before = {
        "batch": snapshot(ROOT / "data/batches/task027r1_run_04/batch_normal"),
        "task043": snapshot(ROOT / "data/evidence_inputs/task043_v1_1"),
        "gl": snapshot(GL),
        "ledger": sha((ROOT / "data/sqlite_tests/task042_dsh_01/normal/runtime.sqlite3")
                      .read_bytes()),
    }

    def record(name, checks, observed=None):
        passed = all(checks.values())
        results.append({"case": name, "checks": checks,
                        "status": "PASS" if passed else "FAIL",
                        "observed": observed or {}})
        return passed

    outputs_root = out_root / ("outputs_" + stamp)
    code = run_all(["--config", str(CONFIG), "--out-root", str(outputs_root),
                    "--run-id", run_normal, "--no-open"], out_root / "logs", "normal")
    normal = outputs_root / run_normal
    summary = json.loads((normal / "run_summary.json").read_bytes()) \
        if (normal / "run_summary.json").is_file() else {}
    record("normal", {
        "exit_0": code == 0,
        "index": (normal / "index.html").is_file(),
        "gl_checks": (normal / "gl" / "gl-checks.html").is_file(),
        "excel": (normal / "excel" / "证据链底稿.xlsx").is_file(),
        "logs": (normal / "logs").is_dir() and any((normal / "logs").iterdir()),
        "summary_success": summary.get("overall") == "SUCCESS",
        "seven_steps": [item.get("id") for item in summary.get("steps") or []] ==
        ["input_contract", "gl_contract", "demo", "gl_reconcile",
         "trace_index", "site", "workbook"],
        "steps_zero": all(item.get("exit_code") == 0
                          for item in summary.get("steps") or []),
        "read_only": summary.get("read_only_ok") is True,
    }, {"outputs": summary.get("outputs")})

    # 输出目录已存在 → exit 2
    code_exists = run_all(["--config", str(CONFIG), "--out-root", str(outputs_root),
                           "--run-id", run_normal, "--no-open"], out_root / "logs", "exists")
    record("output_exists", {"exit_2": code_exists == 2})

    # task043 输入缺文件 → 第 1 步失败
    bad_task043 = out_root / "bad_task043"
    bad_task043.mkdir()
    (bad_task043 / "input_manifest.json").write_text("{}", encoding="utf-8")
    bad_config = json.loads(CONFIG.read_bytes())
    bad_config["inputs"]["task043_input_root"] = str(bad_task043)
    (out_root / "bad_input_config.json").write_bytes(
        json.dumps(bad_config, ensure_ascii=False, indent=2,
                   sort_keys=True).encode("utf-8") + b"\n")
    code_bad = run_all(["--config", str(out_root / "bad_input_config.json"),
                        "--out-root", str(outputs_root), "--run-id", run_bad_input,
                        "--no-open"], out_root / "logs", "bad_input")
    bad_input_dir = outputs_root / run_bad_input
    bad_summary = json.loads((bad_input_dir / "run_summary.json").read_bytes()) \
        if (bad_input_dir / "run_summary.json").is_file() else {}
    record("bad_input", {
        "exit_1": code_bad == 1,
        "no_index": not (bad_input_dir / "index.html").exists(),
        "failed_step": bad_summary.get("failed_step") == "input_contract",
        "overall_failed": bad_summary.get("overall") == "FAILED",
    })

    # GL 契约坏 → 第 2 步失败
    bad_gl = out_root / "bad_gl"
    shutil.copytree(GL, bad_gl)
    trial_path = bad_gl / "trial_balance.json"
    trial = json.loads(trial_path.read_bytes())
    trial["rows"][2]["closing_debit"] = 300000
    trial_path.write_bytes(json.dumps(trial, ensure_ascii=False, indent=2,
                                      sort_keys=True).encode("utf-8") + b"\n")
    bad_gl_config = json.loads(CONFIG.read_bytes())
    bad_gl_config["inputs"]["gl_root"] = str(bad_gl)
    (out_root / "bad_gl_config.json").write_bytes(
        json.dumps(bad_gl_config, ensure_ascii=False, indent=2,
                   sort_keys=True).encode("utf-8") + b"\n")
    code_gl = run_all(["--config", str(out_root / "bad_gl_config.json"),
                       "--out-root", str(outputs_root), "--run-id", run_bad_gl,
                       "--no-open"], out_root / "logs", "bad_gl")
    bad_gl_dir = outputs_root / run_bad_gl
    gl_summary = json.loads((bad_gl_dir / "run_summary.json").read_bytes()) \
        if (bad_gl_dir / "run_summary.json").is_file() else {}
    record("bad_gl", {
        "exit_1": code_gl == 1,
        "no_index": not (bad_gl_dir / "index.html").exists(),
        "failed_step": gl_summary.get("failed_step") == "gl_contract",
        "overall_failed": gl_summary.get("overall") == "FAILED",
    })

    # 启动器与配置
    launcher = ROOT / "一键对账.cmd"
    config = json.loads(CONFIG.read_bytes())
    launcher_text = launcher.read_text("utf-8", errors="replace") if launcher.is_file() else ""
    record("launcher", {
        "cmd_exists": launcher.is_file(),
        "calls_run_all": "run_all.py" in launcher_text,
        "has_pause": "pause" in launcher_text,
        "config_resolvable": all((ROOT / config["inputs"][key]).exists() for key in
                                 ("batch_dir", "task043_input_root", "ledger_db", "gl_root")),
    })

    # 确定性：两个 run-id，发布产物字节相同
    det_a = outputs_root / run_det_a
    det_b = outputs_root / run_det_b
    code_a = run_all(["--config", str(CONFIG), "--out-root", str(outputs_root),
                      "--run-id", run_det_a, "--no-open"], out_root / "logs", "det_a")
    code_b = run_all(["--config", str(CONFIG), "--out-root", str(outputs_root),
                      "--run-id", run_det_b, "--no-open"], out_root / "logs", "det_b")
    same = code_a == 0 and code_b == 0 and all(
        (det_a / name).read_bytes() == (det_b / name).read_bytes()
        for name in ("index.html", "gl/gl-checks.html", "excel/证据链底稿.xlsx"))
    record("determinism", {"both_exit_0": code_a == 0 and code_b == 0,
                           "identical": same})

    inputs_after = {
        "batch": snapshot(ROOT / "data/batches/task027r1_run_04/batch_normal"),
        "task043": snapshot(ROOT / "data/evidence_inputs/task043_v1_1"),
        "gl": snapshot(GL),
        "ledger": sha((ROOT / "data/sqlite_tests/task042_dsh_01/normal/runtime.sqlite3")
                      .read_bytes()),
    }
    passed = sum(1 for item in results if item["status"] == "PASS")
    report = {
        "task": "TASK-059",
        "generated_by": "tests/test_run_all.py",
        "read_only_ok": inputs_before == inputs_after,
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item["case"] for item in results if item["status"] != "PASS"],
        "status": "PASS" if passed == len(results) and inputs_before == inputs_after else "FAIL",
        "cases": results,
        "note": "七步成功/失败即停/拒绝覆盖/启动器/确定性/只读均以真实 CLI 验证。",
        "boundaries": {"audit_conclusion": False, "real_approval": None,
                       "real_initial_judgment_saved": False, "next_step_allowed": False,
                       "ai_enabled": False},
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
