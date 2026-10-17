#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-047：静态 HTML 演示报告生成器测试（真实 CLI 子进程）。

覆盖：正常（task046_demo_01）→ exit 0 且含 8/8、3/3、4000.00、九边界、无脚本/外链；
确定性（两次生成字节相同）；转义注入（批次名含 `<b>x</b>` → 不出现裸标签）；负例
（out-dir 已存在、run-root 不存在、缺 demo_summary → exit 2；内容缺 four_way → exit 1）；
P02 缺证运行根（task046_demo_v1_neg）→ 账证 6/8 与 MISSING_VOUCHER 高亮、生成器 exit 0；
只读：运行根/业务根/证据输入前后字节不变。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
RUN_ROOT = TEST_ROOT / "task046_demo_01"
V1_NEG_ROOT = TEST_ROOT / "task046_demo_v1_neg"
SCRIPT = ROOT / "scripts/build_demo_report_html.py"
BUSINESS_FACT = ROOT / "data/runtime/task046_demo_01/normal.facts/fact_packet.json"
BUSINESS_JUDGMENT = ROOT / "data/human_initial_judgment_records/task046_demo_01/bound/rec_0001/judgment_result.json"
BUSINESS_MANIFEST = ROOT / "data/human_initial_judgment_records/task046_demo_01/bound/rec_0001/manifest.json"


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


def run_cli(run_root, out_dir, log_dir):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / "stdout.txt"
    stderr = log_dir / "stderr.txt"
    command = [sys.executable, "-B", str(SCRIPT), "--run-root", str(run_root),
               "--out-dir", str(out_dir)]
    with stdout.open("wb") as out, stderr.open("wb") as err:
        completed = subprocess.run(command, cwd=str(ROOT), stdout=out, stderr=err)
    return completed.returncode, command, stdout, stderr


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-047 静态 HTML 报告测试")
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
    if not out_root.name.startswith("task047_"):
        print(json.dumps({"status": "FAIL",
                          "reason": "out-dir 目录名必须以 task047_ 开头"}, ensure_ascii=False))
        return 1
    inputs_before = {
        "run_root": snapshot(RUN_ROOT),
        "business": file_snapshot((BUSINESS_FACT, BUSINESS_JUDGMENT, BUSINESS_MANIFEST)),
        "evidence_inputs": snapshot(ROOT / "data/evidence_inputs"),
    }
    out_root.mkdir(parents=True)
    results = []

    def record(name, exit_code, checks, observed=None, detail=""):
        passed = all(checks.values())
        results.append({"case": name, "exit_code": exit_code,
                        "checks": checks, "status": "PASS" if passed else "FAIL",
                        "observed": observed or {}, "detail": detail})
        return passed

    # 1. 正常
    case_dir = out_root / "normal"
    case_dir.mkdir(parents=True)
    report_dir = out_root / "task047_report_01"
    code, command, stdout, stderr = run_cli(RUN_ROOT, report_dir, case_dir)
    html = (report_dir / "index.html").read_bytes().decode("utf-8") if report_dir.is_dir() else ""
    checks = {
        "exit_0": code == 0,
        "html_exists": bool(html),
        "has_8_8": "8 / 8" in html,
        "has_3_3": "3 / 3" in html,
        "has_4000": "4000.00" in html,
        "has_filter": "INPUT_V1_ACCEPTED" in html,
        "has_verified": "RT_HUMAN_INITIAL_JUDGMENT_VERIFIED" in html,
        "has_unmatched_zero": "账有实无：0" in html and "实有账无：0" in html,
        "no_script": "<script" not in html,
        "no_http": "http://" not in html and "https://" not in html,
        "no_link_img": "<link" not in html and "<img" not in html,
    }
    record("normal", code, checks,
           {"command": [str(item) for item in command], "html_bytes": len(html)})

    # 2. 确定性
    det_a = out_root / "task047_det_a"
    det_b = out_root / "task047_det_b"
    code_a, _, _, _ = run_cli(RUN_ROOT, det_a, out_root / "det_a_logs")
    code_b, _, _, _ = run_cli(RUN_ROOT, det_b, out_root / "det_b_logs")
    same_html = (det_a / "index.html").read_bytes() == (det_b / "index.html").read_bytes()
    same_source = (det_a / "report_source.json").read_bytes() \
        == (det_b / "report_source.json").read_bytes()
    record("determinism", 0,
           {"both_exit_0": code_a == 0 and code_b == 0,
            "html_identical": same_html, "source_identical": same_source})

    # 3. 转义注入
    escape_root = TEST_ROOT / ("task047_escape_input_" + out_root.name)
    if escape_root.exists():
        print(json.dumps({"status": "FAIL", "reason": "fixture exists"}, ensure_ascii=False))
        return 1
    shutil.copytree(RUN_ROOT, escape_root)
    summary = json.loads((escape_root / "demo_summary.json").read_bytes())
    summary["batch"]["batch_id"] = "<b>x</b>"
    (escape_root / "demo_summary.json").write_bytes(
        json.dumps(summary, ensure_ascii=False, indent=2,
                   sort_keys=True).encode("utf-8") + b"\n")
    copy_business(escape_root.name)
    escape_report = out_root / "task047_escape_report"
    code, _, _, _ = run_cli(escape_root, escape_report,
                            out_root / "escape_logs")
    escaped_html = (escape_report / "index.html").read_bytes().decode("utf-8") \
        if escape_report.is_dir() else ""
    record("escape", code,
           {"exit_0": code == 0,
            "escaped_present": "&lt;b&gt;x&lt;/b&gt;" in escaped_html,
            "raw_absent": "<b>x</b>" not in escaped_html})

    # 4. 负例
    code, _, _, _ = run_cli(RUN_ROOT, report_dir, out_root / "neg_exists_logs")
    record("neg_out_exists", code, {"exit_2": code == 2})
    code, _, _, _ = run_cli(TEST_ROOT / "task047_no_such_run", out_root / "task047_neg_out",
                            out_root / "neg_run_missing_logs")
    record("neg_run_missing", code, {"exit_2": code == 2})
    missing_root = TEST_ROOT / ("task047_missing_summary_" + out_root.name)
    if missing_root.exists():
        print(json.dumps({"status": "FAIL", "reason": "fixture exists"}, ensure_ascii=False))
        return 1
    shutil.copytree(RUN_ROOT, missing_root)
    (missing_root / "demo_summary.json").unlink()
    code, _, stdout, _ = run_cli(missing_root, out_root / "task047_neg_out2",
                                 out_root / "neg_summary_missing_logs")
    observed = json.loads(stdout.read_bytes()) if stdout.is_file() else {}
    record("neg_summary_missing", code,
           {"exit_2": code == 2, "field_demo_summary": observed.get("field") == "demo_summary"})
    content_root = TEST_ROOT / ("task047_content_input_" + out_root.name)
    if content_root.exists():
        print(json.dumps({"status": "FAIL", "reason": "fixture exists"}, ensure_ascii=False))
        return 1
    shutil.copytree(RUN_ROOT, content_root)
    content_summary = json.loads((content_root / "demo_summary.json").read_bytes())
    content_summary.pop("four_way", None)
    (content_root / "demo_summary.json").write_bytes(
        json.dumps(content_summary, ensure_ascii=False, indent=2,
                   sort_keys=True).encode("utf-8") + b"\n")
    copy_business(content_root.name)
    code, _, stdout, _ = run_cli(content_root, out_root / "task047_neg_out3",
                                 out_root / "neg_content_logs")
    observed = json.loads(stdout.read_bytes()) if stdout.is_file() else {}
    record("neg_content_four_way", code,
           {"exit_1": code == 1, "field_four_way": "four_way" in str(observed.get("field")),
            "kind_content": observed.get("kind") == "content"})

    # 5. P02 缺证运行根
    neg_report = out_root / "task047_report_v1_neg"
    code, _, _, _ = run_cli(V1_NEG_ROOT, neg_report, out_root / "v1_neg_logs")
    neg_html = (neg_report / "index.html").read_bytes().decode("utf-8") \
        if neg_report.is_dir() else ""
    record("v1_neg_report", code,
           {"exit_0": code == 0, "has_6_8": "6 / 8" in neg_html,
            "has_missing": neg_html.count("MISSING_VOUCHER") >= 2,
            "no_script": "<script" not in neg_html,
            "no_http": "http://" not in neg_html and "https://" not in neg_html})

    # 只读
    inputs_after = {
        "run_root": snapshot(RUN_ROOT),
        "business": file_snapshot((BUSINESS_FACT, BUSINESS_JUDGMENT, BUSINESS_MANIFEST)),
        "evidence_inputs": snapshot(ROOT / "data/evidence_inputs"),
    }
    passed = sum(1 for item in results if item["status"] == "PASS")
    report = {
        "task": "TASK-047",
        "generated_by": "tests/test_demo_report_html.py",
        "run_root": RUN_ROOT.relative_to(ROOT).as_posix(),
        "v1_neg_root": V1_NEG_ROOT.relative_to(ROOT).as_posix(),
        "read_only_ok": inputs_before == inputs_after,
        "read_only_detail": {"run_root": inputs_before["run_root"] == inputs_after["run_root"],
                             "business": inputs_before["business"] == inputs_after["business"],
                             "evidence_inputs": inputs_before["evidence_inputs"]
                             == inputs_after["evidence_inputs"]},
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item["case"] for item in results if item["status"] != "PASS"],
        "status": "PASS" if passed == len(results) and inputs_before == inputs_after else "FAIL",
        "cases": results,
        "note": ("正常/确定性/转义/负例/P02 缺证展示均以真实 CLI 子进程验证；"
                 "夹具复制于 task047_* 名下，原运行根与证据输入只读。"),
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
                      "passed": passed, "read_only_ok": report["read_only_ok"],
                      "report": str(report_path)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
