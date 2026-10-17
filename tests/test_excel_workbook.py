#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-050：证据链底稿 .xlsx 测试（真实 CLI 子进程）。

覆盖：正常（说明/问题清单/台账明细/原始表行/凭证/图像占位六页、R02、双击说明、打开原始工作簿）；
链接校验（内部 `#` 目标全部可解析，外部仅原始工作簿）；数值校验（元=分/100、差额=应为−实为）；
语言红线；P02 缺证（红色行、未取得、占位）；确定性（语义比较）；规模（200 条事项）；
负例（悬空引用 exit 1、缺索引 exit 2）；只读（索引与原始工作簿字节不变）。
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

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
INDEX = TEST_ROOT / "task048_index_01/trace_index.json"
V1_NEG_INDEX = TEST_ROOT / "task048_index_v1_neg/trace_index.json"
SCALE_INDEX = TEST_ROOT / "task048_run_01/task048_index_scale/trace_index.json"
SCRIPT = ROOT / "scripts/build_excel_workbook.py"
TRACE_SCRIPT = ROOT / "scripts/build_trace_index.py"
V1_NEG_RUN = TEST_ROOT / "task046_demo_v1_neg"
SCALE_RUN = TEST_ROOT / "task048_scale_run_task048_run_01"
ORIGINAL = ROOT / "data/batches/task027r1_run_04/batch_normal/source/input.xlsx"
BANNED = ("JSON", "hash", "SHA", "API", "script", "pipeline", "解析",
          "字段类型", "字节", "编码", "版本号")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build_index(run_root, out_dir, log_dir):
    log_dir.mkdir(parents=True, exist_ok=True)
    if not run_root.is_dir():
        return 1
    command = [sys.executable, "-B", str(TRACE_SCRIPT), "--run-root", str(run_root),
               "--out-dir", str(out_dir)]
    with (log_dir / "stdout.txt").open("wb") as out, (log_dir / "stderr.txt").open("wb") as err:
        return subprocess.run(command, cwd=str(ROOT), stdout=out, stderr=err).returncode


def run_cli(index, out_dir, log_dir):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / "stdout.txt"
    stderr = log_dir / "stderr.txt"
    command = [sys.executable, "-B", str(SCRIPT), "--index", str(index),
               "--out-dir", str(out_dir)]
    start = time.monotonic()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        completed = subprocess.run(command, cwd=str(ROOT), stdout=out, stderr=err)
    return completed.returncode, command, stdout, stderr, time.monotonic() - start


def workbook_path(out_dir):
    return Path(out_dir) / "证据链底稿.xlsx"


def link_validation(wb):
    internal = 0
    external = []
    bad = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.hyperlink is None:
                    continue
                target = cell.hyperlink.target or ""
                if "#" in target:
                    internal += 1
                    sheet_part, cell_part = target.split("#", 1)[1].split("!", 1)
                    sheet_name = sheet_part.strip("'")
                    address = cell_part.replace("$", "")
                    if sheet_name not in wb.sheetnames:
                        bad.append((ws.title, cell.coordinate, target))
                        continue
                    sheet = wb[sheet_name]
                    try:
                        ref = sheet[address]
                    except Exception:
                        bad.append((ws.title, cell.coordinate, target))
                        continue
                    if ref is None:
                        bad.append((ws.title, cell.coordinate, target))
                else:
                    external.append((ws.title, cell.coordinate, target))
    return internal, external, bad


def semantic(wb):
    data = {}
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None or cell.hyperlink is not None:
                    fill = cell.fill.fgColor.rgb if cell.fill and cell.fill.fgColor else None
                    rows.append((cell.coordinate, cell.value,
                                 cell.hyperlink.target if cell.hyperlink else None,
                                 fill))
        data[ws.title] = rows
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-050 证据链底稿测试")
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
    if not out_root.name.startswith(("task050_", "task051_", "task052_", "task057_")):
        print(json.dumps({"status": "FAIL",
                          "reason": "out-dir 目录名必须以 task050_、task051_ 或 task052_ 开头"},
                         ensure_ascii=False))
        return 1
    index_before = sha(INDEX.read_bytes())
    original_before = sha(ORIGINAL.read_bytes())
    out_root.mkdir(parents=True)
    results = []

    def record(name, exit_code, checks, observed=None):
        passed = all(checks.values())
        results.append({"case": name, "exit_code": exit_code, "checks": checks,
                        "status": "PASS" if passed else "FAIL",
                        "observed": observed or {}})
        return passed

    index_root = out_root / "task051_index_for_workbook"
    build_index(ROOT / "data/runtime_initial_judgment_recording_tests/task046_demo_01",
                index_root, out_root / "index_logs")
    index_path = index_root / "trace_index.json"
    v1_neg_index_root = out_root / "task051_index_v1_neg"
    build_index(V1_NEG_RUN, v1_neg_index_root, out_root / "index_v1neg_logs")
    scale_index_root = out_root / "task051_index_scale"
    if SCALE_RUN.is_dir():
        build_index(SCALE_RUN, scale_index_root, out_root / "index_scale_logs")

    # 1. 正常
    case = out_root / "normal"
    case.mkdir(parents=True)
    build = out_root / "task050_workbook"
    code, command, stdout, stderr, elapsed = run_cli(index_path, build, case)
    path = workbook_path(build)
    wb = load_workbook(path) if path.is_file() else None
    internal, external, bad_links = link_validation(wb) if wb else (0, [], [("missing", "x", "x")])
    issues = wb["问题清单"] if wb else None
    checks = {
        "exit_0": code == 0,
        "sheets_order": wb is not None and wb.sheetnames == ["说明", "问题清单", "台账明细",
                                                            "原始表行", "凭证", "图像占位"],
        "info_banner": wb is not None and "合成数据" in str(wb["说明"]["A1"].value),
        "info_double_click": wb is not None and "双击是进入单元格编辑" in str(wb["说明"]["A3"].value),
        "open_original": wb is not None and wb["说明"]["A4"].hyperlink is not None
        and wb["说明"]["A4"].hyperlink.target.endswith("input.xlsx"),
        "has_r02_row": wb is not None and any(
            issues.cell(row=r, column=2).value and "R02" in str(issues.cell(row=r, column=2).value)
            for r in range(2, issues.max_row + 1)),
        "amount_values": wb is not None and issues["E2"].value == 4000
        and issues["F2"].value == 400000,
        "severity_fill": wb is not None and issues["D2"].fill.fgColor.rgb == "00FFF8D6",
        "amount_links": wb is not None and issues["E2"].hyperlink is not None
        and issues["F2"].hyperlink is not None
        and issues["M2"].hyperlink is not None,
        "ledger_link": wb is not None and issues["J2"].hyperlink is not None,
        "voucher_link": wb is not None and issues["K2"].hyperlink is not None,
        "internal_links_ok": not bad_links,
        "external_only_original": all(item[2].endswith("input.xlsx") for item in external),
        "has_ledger_rows": wb is not None and wb["台账明细"].max_row > 2,
        "has_voucher_rows": wb is not None and wb["凭证"].max_row > 2,
        "has_image_rows": wb is not None and wb["图像占位"].max_row > 2,
        "backup_note": wb is not None and "备份纪律" in str(wb["说明"]["A10"].value),
        "autofilter_ledger": wb is not None and wb["台账明细"].auto_filter.ref is not None,
        "autofilter_voucher": wb is not None and wb["凭证"].auto_filter.ref is not None,
        "autofilter_source": wb is not None and wb["原始表行"].auto_filter.ref is not None,
        "status_columns": wb is not None and wb["台账明细"].cell(row=2, column=3).value
        in ("已核对一致", "存在差异", "未取得", "未涉及")
        and wb["凭证"].cell(row=2, column=3).value in ("已取得", "未取得")
        and wb["原始表行"].cell(row=2, column=12).value in ("已涉及", "未涉及"),
        "has_highlight": wb is not None and any(
            cell.fill.fgColor.rgb == "00FFF2CC"
            for row in wb["原始表行"].iter_rows() for cell in row),
    }
    record("normal", code, checks,
           {"pages": 0, "internal_links": internal, "external_links": len(external),
            "duration_seconds": round(elapsed, 3), "bytes": path.stat().st_size if path.is_file() else None,
            "command": [str(item) for item in command]})

    # 2. 数值校验
    numeric_ok = True
    checked = 0
    if wb is not None:
        for sheet_name, cents_column, yuan_column, start_row in (
                ("问题清单", 6, 5, 2), ("台账明细", 6, 7, 2), ("图像占位", 5, 6, 2)):
            ws = wb[sheet_name]
            for r in range(start_row, ws.max_row + 1):
                cents = ws.cell(row=r, column=cents_column).value
                yuan = ws.cell(row=r, column=yuan_column).value
                if type(cents) is int and type(yuan) in (int, float):
                    checked += 1
                    if abs(yuan - cents / 100.0) > 1e-9:
                        numeric_ok = False
    record("numeric", 0, {"yuan_equals_cents": numeric_ok, "checked_pairs": checked > 0},
           {"checked": checked})

    # 3. 语言红线
    banned_hits = []
    if wb is not None:
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        for word in BANNED:
                            if word in cell.value:
                                banned_hits.append((ws.title, cell.coordinate, word))
    record("language", 0, {"banned_zero": not banned_hits}, {"hits": banned_hits[:5]})

    # 4. P02 缺证
    case = out_root / "v1_neg"
    case.mkdir(parents=True)
    neg = out_root / "task050_workbook_v1_neg"
    code, _, _, _, _ = run_cli(v1_neg_index_root / "trace_index.json", neg, case)
    neg_path = workbook_path(neg)
    neg_wb = load_workbook(neg_path) if neg_path.is_file() else None
    red_rows = []
    if neg_wb is not None:
        ws = neg_wb["问题清单"]
        for r in range(2, ws.max_row + 1):
            if ws.cell(row=r, column=4).fill.fgColor.rgb == "00FDE8E8":
                red_rows.append(r)
    vouchers_tail = []
    images_tail = []
    if neg_wb is not None:
        for r in range(2, neg_wb["凭证"].max_row + 1):
            if "未取得" in str(neg_wb["凭证"].cell(row=r, column=7).value):
                vouchers_tail.append(r)
        for r in range(2, neg_wb["图像占位"].max_row + 1):
            if "未取得" in str(neg_wb["图像占位"].cell(row=r, column=7).value):
                images_tail.append(r)
    neg_internal, neg_external, neg_bad = link_validation(neg_wb) if neg_wb else (0, [], [("x", "x", "x")])
    record("p02_missing", code,
           {"exit_0": code == 0, "red_rows": len(red_rows) == 2,
            "voucher_undrawn": bool(vouchers_tail), "image_undrawn": bool(images_tail),
            "links_ok": not neg_bad})

    # 5. 确定性（语义比较）
    det_a = out_root / "task050_det_a"
    det_b = out_root / "task050_det_b"
    code_a, _, _, _, _ = run_cli(index_path, det_a, out_root / "det_a_logs")
    code_b, _, _, _, _ = run_cli(index_path, det_b, out_root / "det_b_logs")
    wb_a = load_workbook(workbook_path(det_a)) if workbook_path(det_a).is_file() else None
    wb_b = load_workbook(workbook_path(det_b)) if workbook_path(det_b).is_file() else None
    same_semantic = (wb_a is not None and wb_b is not None
                     and semantic(wb_a) == semantic(wb_b))
    same_bytes = (workbook_path(det_a).read_bytes() == workbook_path(det_b).read_bytes()) \
        if workbook_path(det_a).is_file() and workbook_path(det_b).is_file() else False
    record("determinism", 0, {"both_exit_0": code_a == 0 and code_b == 0,
                              "semantic_identical": same_semantic},
           {"bytes_identical": same_bytes})

    # 6. 规模（200 条事项）
    case = out_root / "scale"
    case.mkdir(parents=True)
    scale = out_root / "task050_workbook_scale"
    code, _, _, _, elapsed = run_cli(scale_index_root / "trace_index.json", scale, case)
    scale_path = workbook_path(scale)
    scale_wb = load_workbook(scale_path) if scale_path.is_file() else None
    scale_rows = scale_wb["问题清单"].max_row if scale_wb else 0
    scale_ledger = scale_wb["台账明细"].max_row if scale_wb else 0
    scale_internal, scale_external, scale_bad = link_validation(scale_wb) if scale_wb else (0, [], [("x", "x", "x")])
    record("scale_200", code,
           {"exit_0": code == 0, "issue_rows_201": scale_rows == 201,
            "links_ok": not scale_bad},
           {"bytes": scale_path.stat().st_size if scale_path.is_file() else None,
            "duration_seconds": round(elapsed, 3),
            "internal_links": scale_internal})

    # 7. 负例
    dangling = json.loads(index_path.read_bytes())
    dangling["cases"][0]["ledger_refs"][0]["ledger_id"] = "AP99"
    dangling_path = out_root / "dangling_index.json"
    dangling_path.write_bytes(json.dumps(dangling, ensure_ascii=False, indent=2,
                                         sort_keys=True).encode("utf-8") + b"\n")
    code, _, stdout, _, _ = run_cli(dangling_path, out_root / "task050_neg_dangling",
                                    out_root / "dangling_logs")
    observed = json.loads(stdout.read_bytes()) if stdout.is_file() else {}
    record("neg_dangling", code,
           {"exit_1": code == 1, "kind_content": observed.get("kind") == "content",
            "field_ap99": "AP99" in str(observed.get("field"))})
    code, _, _, _, _ = run_cli(out_root / "no_such_index.json",
                               out_root / "task050_neg_missing", out_root / "missing_logs")
    record("neg_missing_index", code, {"exit_2": code == 2})

    index_after = sha(INDEX.read_bytes())
    original_after = sha(ORIGINAL.read_bytes())
    # TASK-057：GL 七页（科目余额表/记账凭证/总账/明细账/账表核对/银行调节/核对结果）
    gl_root = ROOT / "data/evidence_inputs/gl_v1"
    gl_report = TEST_ROOT / "task056r1_gl_01/gl_reconcile_report.json"
    if gl_root.is_dir() and gl_report.is_file():
        gl_index = out_root / "task051_index_gl"
        gl_code = subprocess.run(
            [sys.executable, "-B", str(TRACE_SCRIPT), "--run-root",
             str(ROOT / "data/runtime_initial_judgment_recording_tests/task046_demo_01"),
             "--out-dir", str(gl_index), "--gl-root", str(gl_root),
             "--gl-report", str(gl_report)], cwd=str(ROOT),
            capture_output=True, text=True).returncode
        gl_workbook = out_root / "task057_workbook_gl"
        gl_work_code = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--index", str(gl_index / "trace_index.json"),
             "--out-dir", str(gl_workbook)], cwd=str(ROOT),
            capture_output=True, text=True).returncode
        gl_wb = load_workbook(gl_workbook / "证据链底稿.xlsx") \
            if (gl_workbook / "证据链底稿.xlsx").is_file() else None
        names = ("科目余额表", "记账凭证", "总账", "明细账", "账表核对", "银行调节", "核对结果")
        checks = {
            "index_exit_0": gl_code == 0,
            "workbook_exit_0": gl_work_code == 0,
            "seven_sheets": gl_wb is not None and all(name in gl_wb.sheetnames for name in names),
            "autofilters": gl_wb is not None and all(
                gl_wb[name].auto_filter.ref is not None for name in names),
            "trial_totals": gl_wb is not None and gl_wb["科目余额表"].cell(
                row=gl_wb["科目余额表"].max_row, column=8).value == 2000000,
            "checks_matched": gl_wb is not None and sum(
                1 for row in range(2, gl_wb["核对结果"].max_row + 1)
                if gl_wb["核对结果"].cell(row=row, column=2).value == "MATCHED") == 7,
            "cover_line": gl_wb is not None and "合成账套演示" in str(
                gl_wb["说明"]["B11"].value),
        }
        record("gl_sheets", gl_work_code, checks,
               {"sheets": len(gl_wb.sheetnames) if gl_wb else None})
    else:
        record("gl_sheets", 1, {"missing_inputs": False})

    passed = sum(1 for item in results if item["status"] == "PASS")
    report = {
        "task": "TASK-050",
        "generated_by": "tests/test_excel_workbook.py",
        "index": INDEX.relative_to(ROOT).as_posix(),
        "v1_neg_index": V1_NEG_INDEX.relative_to(ROOT).as_posix(),
        "scale_index": SCALE_INDEX.relative_to(ROOT).as_posix(),
        "read_only_ok": index_before == index_after and original_before == original_after,
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item["case"] for item in results if item["status"] != "PASS"],
        "status": "PASS" if passed == len(results) and index_before == index_after
        and original_before == original_after else "FAIL",
        "cases": results,
        "note": "正常/P02 缺证/链接/数值/语言/确定性/200 条规模/负例均以真实 CLI 子进程验证；索引与原始工作簿只读。",
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
