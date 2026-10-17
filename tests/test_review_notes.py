#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-052：审阅记录合并测试（真实 CLI 子进程）。

覆盖：正常合并（徽标/问题/建议/审阅人/日期、审阅记录.xlsx、合并索引、站点与底稿）；
版本绑定不符、未知记录、非法状态、非待审阅缺少必填、HTML 注入等负例（exit 1 精确字段）；
确定性（两次产物字节相同）；只读（原索引/审阅文件/批次/输入不变）；规模（200 条事项 + 20 条审阅）；
站点表单/导出/草稿键守卫。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
INDEX = TEST_ROOT / "task052_index_01/trace_index.json"
SCALE_RUN = TEST_ROOT / "task048_scale_run_task048_run_01"
SCRIPT = ROOT / "scripts/apply_review_notes.py"
TRACE_SCRIPT = ROOT / "scripts/build_trace_index.py"
SITE_SCRIPT = ROOT / "scripts/build_drilldown_site.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ident(path):
    raw = Path(path).read_bytes()
    return {"byte_size": len(raw), "sha256": sha(raw)}


def run_cli(index, review, out_dir, log_dir):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / "stdout.txt"
    stderr = log_dir / "stderr.txt"
    command = [sys.executable, "-B", str(SCRIPT), "--index", str(index),
               "--review-notes", str(review), "--out-dir", str(out_dir)]
    start = time.monotonic()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        completed = subprocess.run(command, cwd=str(ROOT), stdout=out, stderr=err)
    return completed.returncode, command, stdout, stderr, time.monotonic() - start


def index_meta(path):
    return json.loads(Path(path).read_bytes())["meta"]


def write_review(path, source_version, records):
    payload = {"review_version": "TASK-052-review-1.0",
               "source_version": source_version, "records": records}
    path.write_bytes(json.dumps(payload, ensure_ascii=False, indent=2,
                                sort_keys=True).encode("utf-8") + b"\n")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-052 审阅记录合并测试")
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
    if not out_root.name.startswith("task052_"):
        print(json.dumps({"status": "FAIL",
                          "reason": "out-dir 目录名必须以 task052_ 开头"}, ensure_ascii=False))
        return 1
    index_before = sha(INDEX.read_bytes())
    inputs_before = {
        "index": sha(INDEX.read_bytes()),
        "batch": {p.name: sha(p.read_bytes()) for p in
                  (ROOT / "data/batches/task027r1_run_04/batch_normal/source").glob("*")},
        "evidence_inputs": {p.relative_to(ROOT / "data/evidence_inputs").as_posix():
                            sha(p.read_bytes()) for p in
                            (ROOT / "data/evidence_inputs").rglob("*") if p.is_file()},
    }
    out_root.mkdir(parents=True)
    results = []
    meta = index_meta(INDEX)
    short = meta["source_identity"]["sha256"][:12]

    def record(name, exit_code, checks, observed=None):
        passed = all(checks.values())
        results.append({"case": name, "exit_code": exit_code, "checks": checks,
                        "status": "PASS" if passed else "FAIL", "observed": observed or {}})
        return passed

    # 1. 正常合并
    records = [
        {"record_type": "case", "record_id": "CASE-0001", "status": "已审阅-相符",
         "issue": "R02 超额线索已核对", "suggestion": "保留线索", "reviewer": "审计员甲",
         "date": "2026-10-18"},
        {"record_type": "voucher", "record_id": "V-INV-0001", "status": "需补充资料",
         "issue": "发票原件未取得", "suggestion": "要求补充", "reviewer": "审计员甲",
         "date": "2026-10-18"},
        {"record_type": "source", "record_id": "payables!2", "status": "已审阅-不符",
         "issue": "应付金额与合同不一致", "suggestion": "复核", "reviewer": "审计员甲",
         "date": "2026-10-18"},
        {"record_type": "ledger", "record_id": "A01", "status": "待审阅", "issue": None,
         "suggestion": None, "reviewer": None, "date": None},
    ]
    review = write_review(out_root / "review_normal.json", short, records)
    case = out_root / "normal"
    case.mkdir(parents=True)
    merge = out_root / "task052_merge"
    code, command, stdout, stderr, elapsed = run_cli(INDEX, review, merge, case)
    merged = json.loads((merge / "trace_index.json").read_bytes()) if merge.is_dir() else {}
    recs = {}
    for item in merged.get("cases") or []:
        recs[("case", item.get("case_id"))] = item
    for item in merged.get("ledger") or []:
        recs[("ledger", item.get("ledger_id"))] = item
    for item in merged.get("vouchers") or []:
        recs[("voucher", item.get("voucher_id"))] = item
    for item in merged.get("source_rows") or []:
        recs[("source", "%s!%s" % (item.get("sheet"), item.get("excel_row")))] = item
    site = merge / "task049_site"
    case_html = (site / "case-CASE-0001.html").read_text("utf-8") if site.is_dir() else ""
    xlsx = merge / "审阅记录.xlsx"
    wb = load_workbook(xlsx) if xlsx.is_file() else None
    ws = wb["审阅记录"] if wb is not None else None
    checks = {
        "exit_0": code == 0,
        "merged_index": (merge / "trace_index.json").is_file(),
        "reviews_merged": all(recs.get(key, {}).get("review", {}).get("status") == expected
                              for key, expected in ((("case", "CASE-0001"), "已审阅-相符"),
                                                    (("voucher", "V-INV-0001"), "需补充资料"),
                                                    (("source", "payables!2"), "已审阅-不符"),
                                                    (("ledger", "A01"), "待审阅"))),
        "site_badge": "已审阅-相符" in case_html and "R02 超额线索已核对" in case_html,
        "site_form": 'data-record-type="case"' in case_html,
        "site_version": 'data-review-version="%s"' % short in case_html,
        "site_filter_export": all(token in (site / "all-ledger.html").read_text("utf-8")
                                  for token in ("filter-review", "export-review")),
        "xlsx_columns": ws is not None and ws.max_column == 9 and ws.max_row == 26,
        "xlsx_status": ws is not None and any(
            ws.cell(row=r, column=3).value == "已审阅-相符" for r in range(2, ws.max_row + 1)),
        "workbook_generated": (merge / "task050_workbook/证据链底稿.xlsx").is_file(),
    }
    record("normal_merge", code, checks,
           {"records": len(records), "duration_seconds": round(elapsed, 3),
            "merged_index_bytes": (merge / "trace_index.json").stat().st_size
            if (merge / "trace_index.json").is_file() else None,
            "xlsx_bytes": xlsx.stat().st_size if xlsx.is_file() else None,
            "site_pages": len(list(site.glob("*.html"))) if site.is_dir() else None})

    # 2. 负例
    negatives = [
        ("version_mismatch", {"review_version": "TASK-052-review-1.0",
                              "source_version": "000000000000",
                              "records": []}, "review_notes.source_version"),
        ("unknown_record", {"review_version": "TASK-052-review-1.0", "source_version": short,
                            "records": [{"record_type": "case", "record_id": "CASE-9999",
                                         "status": "待审阅"}]}, "record_id"),
        ("bad_status", {"review_version": "TASK-052-review-1.0", "source_version": short,
                        "records": [{"record_type": "case", "record_id": "CASE-0001",
                                     "status": "已通过"}]}, ".status"),
        ("missing_required", {"review_version": "TASK-052-review-1.0", "source_version": short,
                              "records": [{"record_type": "case", "record_id": "CASE-0001",
                                           "status": "已审阅-相符"}]}, ".issue"),
        ("html_injection", {"review_version": "TASK-052-review-1.0", "source_version": short,
                            "records": [{"record_type": "case", "record_id": "CASE-0001",
                                         "status": "已审阅-相符", "issue": "<b>注入</b>",
                                         "reviewer": "审计员甲", "date": "2026-10-18"}]},
         ".issue"),
    ]
    for name, payload, field_part in negatives:
        neg_review = out_root / ("review_%s.json" % name)
        neg_review.write_bytes(json.dumps(payload, ensure_ascii=False, indent=2,
                                          sort_keys=True).encode("utf-8") + b"\n")
        neg_out = out_root / ("task052_neg_%s" % name)
        code, _, stdout, _, _ = run_cli(INDEX, neg_review, neg_out, out_root / ("neg_%s_logs" % name))
        observed = json.loads(stdout.read_bytes()) if stdout.is_file() else {}
        record("neg_" + name, code,
               {"exit_1": code == 1, "kind_content": observed.get("kind") == "content",
                "field_matches": field_part in str(observed.get("field"))})

    # 3. 确定性
    det_a = out_root / "task052_merge_det_a"
    det_b = out_root / "task052_merge_det_b"
    code_a, _, _, _, _ = run_cli(INDEX, review, det_a, out_root / "det_a_logs")
    code_b, _, _, _, _ = run_cli(INDEX, review, det_b, out_root / "det_b_logs")
    same_index = (det_a / "trace_index.json").read_bytes() == (det_b / "trace_index.json").read_bytes()
    same_xlsx = (det_a / "审阅记录.xlsx").read_bytes() == (det_b / "审阅记录.xlsx").read_bytes()
    names = sorted(p.name for p in (det_a / "task049_site").glob("*.html"))
    same_site = names == sorted(p.name for p in (det_b / "task049_site").glob("*.html")) \
        and all((det_a / "task049_site" / n).read_bytes()
                == (det_b / "task049_site" / n).read_bytes() for n in names)
    same_workbook = (det_a / "task050_workbook/证据链底稿.xlsx").read_bytes() \
        == (det_b / "task050_workbook/证据链底稿.xlsx").read_bytes()
    record("determinism", 0,
           {"both_exit_0": code_a == 0 and code_b == 0, "merged_index_identical": same_index,
            "review_xlsx_identical": same_xlsx, "site_identical": same_site,
            "workbook_identical": same_workbook})

    # 4. 规模：200 条事项 + 20 条审阅
    scale_index = out_root / "task052_scale_index"
    subprocess.run([sys.executable, "-B", str(TRACE_SCRIPT), "--run-root", str(SCALE_RUN),
                    "--out-dir", str(scale_index)], cwd=str(ROOT),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    scale_meta = index_meta(scale_index / "trace_index.json")
    scale_review = write_review(out_root / "review_scale.json",
                                scale_meta["source_identity"]["sha256"][:12],
                                [{"record_type": "case", "record_id": "CASE-%04d" % (i + 1),
                                  "status": "已审阅-相符", "issue": "规模审阅",
                                  "suggestion": "无", "reviewer": "审计员甲",
                                  "date": "2026-10-18"} for i in range(20)])
    scale_merge = out_root / "task052_merge_scale"
    code, _, _, _, elapsed = run_cli(scale_index / "trace_index.json", scale_review,
                                     scale_merge, out_root / "scale_logs")
    scale_site = scale_merge / "task049_site"
    bad_links = 0
    if scale_site.is_dir():
        for path in scale_site.glob("*.html"):
            text = path.read_text("utf-8")
            for part in text.split('href="')[1:]:
                href = part.split('"', 1)[0]
                if not href.startswith(("http:", "https:", "//")) \
                        and not (path.parent / href).resolve().exists():
                    bad_links += 1
    record("scale_200_20", code,
           {"exit_0": code == 0, "links_ok": bad_links == 0},
           {"duration_seconds": round(elapsed, 3),
            "site_pages": len(list(scale_site.glob("*.html"))) if scale_site.is_dir() else None,
            "xlsx_bytes": (scale_merge / "审阅记录.xlsx").stat().st_size
            if (scale_merge / "审阅记录.xlsx").is_file() else None})

    index_after = sha(INDEX.read_bytes())
    inputs_after = {
        "index": sha(INDEX.read_bytes()),
        "batch": {p.name: sha(p.read_bytes()) for p in
                  (ROOT / "data/batches/task027r1_run_04/batch_normal/source").glob("*")},
        "evidence_inputs": {p.relative_to(ROOT / "data/evidence_inputs").as_posix():
                            sha(p.read_bytes()) for p in
                            (ROOT / "data/evidence_inputs").rglob("*") if p.is_file()},
    }
    passed = sum(1 for item in results if item["status"] == "PASS")
    report = {
        "task": "TASK-052",
        "generated_by": "tests/test_review_notes.py",
        "index": INDEX.relative_to(ROOT).as_posix(),
        "read_only_ok": inputs_before == inputs_after,
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item["case"] for item in results if item["status"] != "PASS"],
        "status": "PASS" if passed == len(results) and inputs_before == inputs_after else "FAIL",
        "cases": results,
        "note": "合并/负例/确定性/规模均以真实 CLI 子进程验证；原索引与机器证据只读。",
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
