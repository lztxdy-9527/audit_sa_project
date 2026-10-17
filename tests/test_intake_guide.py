#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-058：数据投放指引与状态页测试（真实 CLI 子进程）。

覆盖：目录骨架（README/四个 _放入说明.md/占位）；空 inbox 全缺失；合法样例全已提供；
坏文件对应项需校验；语言/链接/确定性/只读（inbox 前后快照一致）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
SCRIPT = ROOT / "scripts/build_intake_guide.py"
INBOX = ROOT / "data/inbox"
GL = ROOT / "data/evidence_inputs/gl_v1"
GL_FILES = ("chart_of_accounts.json", "journal_entries.json", "trial_balance.json",
            "ledger_general.json", "ledger_subsidiary.json", "balance_sheet.json",
            "bank_statement.json", "bank_journal.json", "attachment_index.json",
            "gl_manifest.json")
BANNED = ("JSON", "hash", "SHA", "API", "script", "pipeline", "解析",
          "字段类型", "字节", "编码", "版本号")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    result = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = [path.stat().st_size,
                                                         sha(path.read_bytes())]
    return result


def run(intake_root, out_dir, log_dir, name):
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / (name + "_stdout.txt")
    stderr = log_dir / (name + "_stderr.txt")
    with stdout.open("wb") as out, stderr.open("wb") as err:
        code = subprocess.run([sys.executable, "-B", str(SCRIPT),
                               "--intake-root", str(intake_root),
                               "--out-dir", str(out_dir)], cwd=str(ROOT),
                              stdout=out, stderr=err).returncode
    return code, stdout


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_bytes(json.dumps(payload, ensure_ascii=False, indent=2,
                                    sort_keys=True).encode("utf-8") + b"\n")


def make_valid_inbox(root: Path) -> None:
    (root / "01_业务台账").mkdir(parents=True)
    (root / "01_业务台账" / "业务台账_2026-09.xlsx").write_bytes(b"PK\x03\x04" + b"0" * 32)
    (root / "02_凭证附件").mkdir(parents=True)
    write(root / "02_凭证附件" / "index.json",
          {"vouchers": [{"voucher_id": "V-INV-0001", "voucher_type": "INVOICE",
                         "amount_cents": 500000, "date": "2026-09-05"}]})
    write(root / "02_凭证附件" / "V-INV-0001.json",
          {"voucher_id": "V-INV-0001", "voucher_type": "INVOICE",
           "amount_cents": 500000, "date": "2026-09-05",
           "invoice_no": "INV-2026-0001"})
    (root / "03_银行流水").mkdir(parents=True)
    write(root / "03_银行流水" / "bank_transactions.json",
          {"period": {"period_start": "2026-09-01", "period_end": "2026-09-30"},
           "account": "基本户", "opening_balance_cents": 2000000,
           "transactions": [{"date": "2026-09-10", "direction": "OUT",
                             "amount_cents": 500000, "reference": "B001"}]})
    (root / "04_总账账套").mkdir(parents=True)
    for name in GL_FILES:
        shutil.copy2(GL / name, root / "04_总账账套" / name)


def make_bad_inbox(root: Path) -> None:
    (root / "01_业务台账").mkdir(parents=True)
    (root / "01_业务台账" / "业务台账_2026-09.xlsx").write_bytes(b"XX" + b"0" * 16)
    (root / "02_凭证附件").mkdir(parents=True)
    (root / "02_凭证附件" / "index.json").write_bytes(b"{not-json")
    (root / "03_银行流水").mkdir(parents=True)
    write(root / "03_银行流水" / "bank_transactions.json",
          {"transactions": [{"date": "2026-09-10", "direction": "OUT"}]})
    (root / "04_总账账套").mkdir(parents=True)
    for name in GL_FILES:
        shutil.copy2(GL / name, root / "04_总账账套" / name)
    trial_path = root / "04_总账账套" / "trial_balance.json"
    trial = json.loads(trial_path.read_bytes())
    trial["rows"][2]["closing_debit"] = 300000
    write(trial_path, trial)


def statuses(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_bytes())
    return {item["id"]: item["status"] for item in manifest["categories"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-058 数据投放指引测试")
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
    if not out_root.name.startswith(("task058_", "task058r1_")):
        print(json.dumps({"status": "FAIL", "reason": "out-dir 前缀非法"}, ensure_ascii=False))
        return 1
    out_root.mkdir(parents=True)
    results = []

    def record(name, checks, observed=None):
        passed = all(checks.values())
        results.append({"case": name, "checks": checks,
                        "status": "PASS" if passed else "FAIL",
                        "observed": observed or {}})
        return passed

    # 1. 目录骨架
    skeleton_checks = {
        "readme": (INBOX / "README.md").is_file(),
        "four_dirs": all((INBOX / name).is_dir() for name in
                         ("01_业务台账", "02_凭证附件", "03_银行流水", "04_总账账套")),
        "four_notes": all((INBOX / name / "_放入说明.md").is_file() for name in
                          ("01_业务台账", "02_凭证附件", "03_银行流水", "04_总账账套")),
        "placeholders": all((INBOX / name / "放入此处.txt").is_file() for name in
                            ("01_业务台账", "02_凭证附件", "03_银行流水", "04_总账账套")),
        "notes_have_fields": all("整数分" in (INBOX / name / "_放入说明.md").read_text("utf-8")
                                 for name in ("01_业务台账", "02_凭证附件",
                                              "03_银行流水", "04_总账账套")),
        "notes_have_command": all("校验" in (INBOX / name / "_放入说明.md").read_text("utf-8")
                                  for name in ("01_业务台账", "02_凭证附件",
                                               "03_银行流水", "04_总账账套")),
    }
    record("skeleton", skeleton_checks)

    empty = out_root / "inbox_empty"
    empty.mkdir(parents=True)
    (empty / "01_业务台账").mkdir()
    (empty / "02_凭证附件").mkdir()
    (empty / "03_银行流水").mkdir()
    (empty / "04_总账账套").mkdir()
    valid = out_root / "inbox_valid"
    make_valid_inbox(valid)
    bad = out_root / "inbox_bad"
    make_bad_inbox(bad)
    before = {"empty": snapshot(empty), "valid": snapshot(valid), "bad": snapshot(bad)}

    empty_code, _ = run(empty, out_root / "task058_status_empty", out_root / "logs", "empty")
    empty_status = statuses(out_root / "task058_status_empty/intake_manifest.json")
    valid_code, _ = run(valid, out_root / "task058_status_valid", out_root / "logs", "valid")
    valid_status = statuses(out_root / "task058_status_valid/intake_manifest.json")
    bad_code, _ = run(bad, out_root / "task058_status_bad", out_root / "logs", "bad")
    bad_status = statuses(out_root / "task058_status_bad/intake_manifest.json")
    record("status_empty", {
        "exit_0": empty_code == 0,
        "all_missing": set(empty_status.values()) == {"缺失"},
        "html": (out_root / "task058_status_empty/intake_status.html").is_file(),
    }, empty_status)
    record("status_valid", {
        "exit_0": valid_code == 0,
        "all_provided": set(valid_status.values()) == {"已提供"},
    }, valid_status)
    record("status_bad", {
        "exit_0": bad_code == 0,
        "all_invalid": set(bad_status.values()) == {"需校验"},
    }, bad_status)

    # 1b. 结构异常兜底（TASK-058-R1）：均 exit 0、页面照常、目标类需校验、其他类不受影响
    def structure_case(name, prepare, expected_id):
        root = out_root / ("inbox_struct_" + name)
        (root / "01_业务台账").mkdir(parents=True)
        (root / "02_凭证附件").mkdir()
        (root / "03_银行流水").mkdir()
        (root / "04_总账账套").mkdir()
        prepare(root)
        out_dir = out_root / ("task058r1_status_" + name)
        code, _ = run(root, out_dir, out_root / "logs", "struct_" + name)
        manifest = json.loads((out_dir / "intake_manifest.json").read_bytes()) \
            if (out_dir / "intake_manifest.json").is_file() else {}
        statuses = {item["id"]: item["status"] for item in manifest.get("categories") or []}
        details = {item["id"]: item["detail"] for item in manifest.get("categories") or []}
        record("struct_" + name, {
            "exit_0": code == 0,
            "html": (out_dir / "intake_status.html").is_file(),
            "target_invalid": statuses.get(expected_id) == "需校验",
            "others_missing": all(statuses.get(other) == "缺失" for other in
                                  ("business", "vouchers", "bank", "gl")
                                  if other != expected_id),
        }, {"statuses": statuses, "detail": details.get(expected_id)})

    structure_case("bank_array", lambda root: (root / "03_银行流水/bank_transactions.json")
                   .write_text("[1, 2]", encoding="utf-8"), "bank")
    structure_case("vouchers_missing_key", lambda root: (root / "02_凭证附件/index.json")
                   .write_text('{"items": []}', encoding="utf-8"), "vouchers")
    def gl_array(root):
        for name in GL_FILES:
            shutil.copy2(GL / name, root / "04_总账账套" / name)
        (root / "04_总账账套/chart_of_accounts.json").write_text("[]", encoding="utf-8")
    structure_case("gl_array", gl_array, "gl")
    def gl_bad_json(root):
        for name in GL_FILES:
            shutil.copy2(GL / name, root / "04_总账账套" / name)
        (root / "04_总账账套/journal_entries.json").write_text("{bad", encoding="utf-8")
    structure_case("gl_bad_json", gl_bad_json, "gl")
    structure_case("xlsx_text", lambda root: (root / "01_业务台账/业务台账.xlsx")
                   .write_text("not an xlsx", encoding="utf-8"), "business")

    # 2. 语言/链接
    page = out_root / "task058_status_valid/intake_status.html"
    text = page.read_text("utf-8")
    visible = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    visible = re.sub(r"<[^>]+>", "", visible)
    banned = [word for word in BANNED if word in visible]
    bad_links = []
    for match in re.finditer(r'href="([^"]+)"', text):
        href = match.group(1)
        if href.startswith(("http:", "https:", "//")):
            bad_links.append(href)
        elif not (page.parent / href).resolve().is_file():
            bad_links.append(href)
    record("language_links", {"banned_zero": not banned, "links_ok": not bad_links},
           {"banned": banned, "bad_links": bad_links})

    # 3. 确定性
    det_a = out_root / "task058_status_det_a"
    det_b = out_root / "task058_status_det_b"
    run(valid, det_a, out_root / "logs", "det_a")
    run(valid, det_b, out_root / "logs", "det_b")
    same = all((det_a / name).read_bytes() == (det_b / name).read_bytes()
               for name in ("intake_status.html", "intake_manifest.json"))
    record("determinism", {"identical": same})

    after = {"empty": snapshot(empty), "valid": snapshot(valid), "bad": snapshot(bad)}
    passed = sum(1 for item in results if item["status"] == "PASS")
    report = {
        "task": "TASK-058",
        "generated_by": "tests/test_intake_guide.py",
        "read_only_ok": before == after,
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item["case"] for item in results if item["status"] != "PASS"],
        "status": "PASS" if passed == len(results) and before == after else "FAIL",
        "cases": results,
        "note": "空/合法/坏三类 inbox 与骨架、语言、链接、确定性、只读均以真实 CLI 验证。",
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
