#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-059：一键对账启动器（只读输入 → 七步机器核对 → 出 HTML 到 outputs/<run_id>）。

用法：
    python -B scripts/run_all.py --open
    python -B scripts/run_all.py --run-id task059_run_01 --no-open
    python -B scripts/run_all.py --run-id task059_diff_01 --no-open --allow-differences

步骤（依赖顺序）：
  1) task043 输入契约校验
  2) GL v1 契约校验
  3) 运行层演示（新运行根）
  4) GL 六类核对（索引 v1.2 的 gl 节依赖此报告）
  5) 证据链索引（含 gl）
  6) 站点（含借贷核对页）
  7) Excel 底稿（含借贷核对页）
  8) 可选：审阅合并（配置 review_notes 时）

`--allow-differences`（默认关闭）：当第 3 步仅因「账证/账实四相符存在差异」而失败时，
不中止，继续出站点/底稿，整体状态记为 `SUCCESS_WITH_DIFFERENCES`（exit 0），
并在 `run_summary.steps[].tolerated` 与 `tolerated_steps` 里显式登记。
其它任何失败（契约、索引、站点、只读漂移等）仍然“失败即停”。
不开这个开关时，行为与之前完全一致。

约束：只读输入（每步后校验哈希，漂移立即停止）；每次新目录；失败即停、不发布半成品
index.html；不联网、不安装依赖；只调用项目内脚本与标准库。状态与差异不构成审计结论。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
PY = sys.executable
UNPERFORMED = [
    "函证（银行/往来）", "监盘（存货）", "期后付款检查", "截止测试",
    "收入/成本截止与截止性分析", "关联方与舞弊专项程序",
]
BOUNDARIES = {
    "audit_conclusion": False, "real_approval": None, "batch_approved": False,
    "real_initial_judgment_saved": False, "development_checkpoint": "0008",
    "next_step_allowed": False, "ai_enabled": False, "identity_authenticated": False,
}
RUN_ID_PATTERN = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
STEPS = (
    ("input_contract", "输入契约校验"),
    ("gl_contract", "GL v1 契约校验"),
    ("demo", "运行层演示"),
    ("gl_reconcile", "GL 六类核对"),
    ("trace_index", "证据链索引（含 gl）"),
    ("site", "站点（含借贷核对页）"),
    ("workbook", "Excel 底稿（含借贷核对页）"),
)


class RunAllError(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshots(paths):
    result = {}
    for path in paths:
        path = Path(path)
        if path.is_file():
            result[str(path)] = sha_file(path)
        elif path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file():
                    result[str(item)] = sha_file(item)
    return result


def resolve(value) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (ROOT / path)


def load_config(path: Path) -> dict:
    if not path.is_file():
        raise RunAllError("usage", "配置不存在：%s" % path)
    try:
        config = json.loads(path.read_bytes())
    except ValueError as exc:
        raise RunAllError("usage", "配置不是合法内容：%s" % exc)
    inputs = config.get("inputs") or {}
    for key in ("batch_dir", "task043_input_root", "ledger_db", "gl_root"):
        if key not in inputs:
            raise RunAllError("usage", "配置缺少 inputs.%s" % key)
    return config


def default_run_id() -> str:
    import datetime
    return "run_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def demo_four_way_differences(demo_dir: Path) -> bool:
    """第 3 步是否「仅因四相符差异」失败：demo_summary 已写且账证/账实任一非 ALL_MATCHED。

    运行层演示在抛 DemoFailure 之前已经写下 demo_summary.json 与三份报告；因此
    「demo_summary 存在 + 结论非 ALL_MATCHED」可以把它与契约拒收等更早的失败区分开。
    """
    summary_path = Path(demo_dir) / "demo_summary.json"
    if not summary_path.is_file():
        return False
    try:
        summary = json.loads(summary_path.read_bytes())
    except (ValueError, OSError):
        return False
    four = summary.get("four_way") or {}
    conclusions = []
    for key in ("account_voucher", "account_reality"):
        section = four.get(key) or {}
        if "conclusion" in section:
            conclusions.append(section["conclusion"])
    return any(item != "ALL_MATCHED" for item in conclusions)


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-059 一键对账启动器")
    parser.add_argument("--config", default=str(ROOT / "config/run_all.json"))
    parser.add_argument("--run-id", dest="run_id", default=None)
    parser.add_argument("--out-root", dest="out_root", default=None)
    parser.add_argument("--open", dest="open_browser", action="store_true", default=None)
    parser.add_argument("--no-open", dest="open_browser", action="store_false")
    parser.add_argument("--allow-differences", dest="allow_differences",
                        action="store_true", default=False,
                        help="第 3 步仅因账证/账实四相符差异失败时继续出站点，"
                             "整体记为 SUCCESS_WITH_DIFFERENCES（默认关闭）")
    args = parser.parse_args(argv)
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    try:
        config = load_config(config_path)
        inputs = config.get("inputs") or {}
        batch_dir = resolve(inputs["batch_dir"])
        task043 = resolve(inputs["task043_input_root"])
        ledger_db = resolve(inputs["ledger_db"])
        gl_root = resolve(inputs["gl_root"])
        review_notes = config.get("review_notes")
        review_path = resolve(review_notes) if review_notes else None
        out_root = resolve(args.out_root or config.get("output_root") or "outputs")
        run_id = args.run_id or default_run_id()
        if not RUN_ID_PATTERN.match(run_id):
            raise RunAllError("usage", "run-id 只能包含字母/数字/下划线/点/连字符")
        open_browser = config.get("open_browser", True) \
            if args.open_browser is None else args.open_browser
        allow_differences = bool(args.allow_differences)
        for label, path in (("batch_dir", batch_dir), ("task043_input_root", task043),
                            ("ledger_db", ledger_db), ("gl_root", gl_root)):
            if not path.exists():
                raise RunAllError("usage", "配置输入不存在：%s（%s）" % (label, path))
        out_dir = out_root / run_id
        if out_dir.exists():
            raise RunAllError("usage", "输出目录已存在，拒绝覆盖：%s" % out_dir)
        guard_paths = (batch_dir, task043, gl_root, ledger_db)
        before = snapshots(guard_paths)
        logs_dir = out_dir / "logs"
        logs_dir.mkdir(parents=True)
        step_dirs = {
            "input_contract": TEST_ROOT / ("task043_runall_" + run_id),
            "gl_contract": None,
            "demo": TEST_ROOT / ("task059_demo_" + run_id),
            "gl_reconcile": TEST_ROOT / ("task056r1_runall_" + run_id),
            "trace_index": TEST_ROOT / ("task057_index_runall_" + run_id),
            "site": TEST_ROOT / ("task057_site_runall_" + run_id),
            "workbook": TEST_ROOT / ("task057_workbook_runall_" + run_id),
        }
        for key in ("input_contract", "demo", "gl_reconcile", "trace_index",
                    "site", "workbook"):
            if step_dirs[key].exists():
                raise RunAllError("usage", "中间目录已存在，拒绝覆盖：%s" % step_dirs[key])
        commands = {
            "input_contract": [PY, "-B", str(ROOT / "scripts/input_contract_v1.py"),
                               "--input", str(task043),
                               "--out", str(step_dirs["input_contract"]),
                               "--ledger-db", str(ledger_db)],
            "gl_contract": [PY, "-B", str(ROOT / "scripts/gl_input_contract_v1.py"),
                            "--gl-root", str(gl_root)],
            "demo": [PY, "-B", str(ROOT / "scripts/run_runtime_demo.py"),
                     "--out-dir", str(step_dirs["demo"]),
                     "--evidence-input", str(task043)],
            "gl_reconcile": [PY, "-B", str(ROOT / "scripts/reconcile_gl_v1.py"),
                             "--gl-root", str(gl_root),
                             "--out-dir", str(step_dirs["gl_reconcile"])],
            "trace_index": [PY, "-B", str(ROOT / "scripts/build_trace_index.py"),
                            "--run-root", str(step_dirs["demo"]),
                            "--out-dir", str(step_dirs["trace_index"]),
                            "--gl-root", str(gl_root),
                            "--gl-report", str(step_dirs["gl_reconcile"]
                                               / "gl_reconcile_report.json")],
            "site": [PY, "-B", str(ROOT / "scripts/build_drilldown_site.py"),
                     "--index", str(step_dirs["trace_index"] / "trace_index.json"),
                     "--out-dir", str(step_dirs["site"])],
            "workbook": [PY, "-B", str(ROOT / "scripts/build_excel_workbook.py"),
                         "--index", str(step_dirs["trace_index"] / "trace_index.json"),
                         "--out-dir", str(step_dirs["workbook"])],
        }
        steps = []
        overall = "SUCCESS"
        failed_step = None
        tolerated_steps = []
        for index, (step_id, name) in enumerate(STEPS, start=1):
            command = commands[step_id]
            stdout_path = logs_dir / ("%02d_%s_stdout.txt" % (index, step_id))
            stderr_path = logs_dir / ("%02d_%s_stderr.txt" % (index, step_id))
            with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
                completed = subprocess.run(command, cwd=str(ROOT), stdout=out, stderr=err)
            error_field = None
            tolerated = False
            if completed.returncode != 0:
                if allow_differences and step_id == "demo" \
                        and demo_four_way_differences(step_dirs["demo"]):
                    tolerated = True
                    tolerated_steps.append(step_id)
                    error_field = "four_way_differences"
                else:
                    overall = "FAILED"
                    failed_step = step_id
                    try:
                        payload = json.loads(stdout_path.read_bytes())
                        error_field = payload.get("field") or payload.get("error")
                    except (ValueError, OSError):
                        error_field = None
            steps.append({"id": step_id, "name": name, "exit_code": completed.returncode,
                          "command": [str(item) for item in command],
                          "stdout": str(stdout_path.relative_to(out_dir)),
                          "stderr": str(stderr_path.relative_to(out_dir)),
                          "error_field": error_field,
                          "tolerated": tolerated})
            after = snapshots(guard_paths)
            if after != before and overall == "SUCCESS":
                overall = "FAILED"
                failed_step = "read_only_guard"
                steps.append({"id": "read_only_guard", "name": "输入只读校验",
                              "exit_code": 1, "command": [], "stdout": None,
                              "stderr": None, "error_field": "input_drift",
                              "tolerated": False})
            if failed_step:
                break
        if overall == "SUCCESS" and tolerated_steps:
            overall = "SUCCESS_WITH_DIFFERENCES"
        outputs = None
        if overall in ("SUCCESS", "SUCCESS_WITH_DIFFERENCES"):
            site_dir = step_dirs["site"]
            workbook_dir = step_dirs["workbook"]
            reconcile_dir = step_dirs["gl_reconcile"]
            for path in sorted(site_dir.glob("*.html")):
                shutil.copy2(path, out_dir / path.name)
            gl_dir = out_dir / "gl"
            gl_dir.mkdir(parents=True, exist_ok=True)
            for path in sorted(site_dir.glob("gl-*.html")):
                shutil.copy2(path, gl_dir / path.name)
            for path in (reconcile_dir / "gl_reconcile_report.json",
                         reconcile_dir / "gl_reconcile_report.md"):
                if path.is_file():
                    shutil.copy2(path, gl_dir / path.name)
            excel_dir = out_dir / "excel"
            excel_dir.mkdir(parents=True, exist_ok=True)
            workbook_path = workbook_dir / "证据链底稿.xlsx"
            if workbook_path.is_file():
                shutil.copy2(workbook_path, excel_dir / workbook_path.name)
            outputs = {
                "index": (out_dir / "index.html").relative_to(out_dir).as_posix(),
                "gl": "gl/",
                "excel": "excel/" + workbook_path.name,
                "logs": "logs/",
            }
            if not (out_dir / "index.html").is_file() or not workbook_path.is_file():
                overall = "FAILED"
                failed_step = "publish"
        summary = {
            "run_id": run_id,
            "overall": overall,
            "failed_step": failed_step,
            "allow_differences": bool(allow_differences),
            "tolerated_steps": tolerated_steps,
            "differences_tolerated": bool(tolerated_steps),
            "steps": steps,
            "outputs": outputs,
            "unperformed": UNPERFORMED,
            "read_only_ok": snapshots(guard_paths) == before,
            "inputs": {
                "batch_dir": str(batch_dir), "task043_input_root": str(task043),
                "ledger_db": str(ledger_db), "gl_root": str(gl_root),
                "review_notes": str(review_path) if review_path else None,
            },
            "boundaries": BOUNDARIES,
            "note": ("一键运行只做机器核对与出页；状态与差异不构成审计结论。"
                     + ("本次启用 --allow-differences：demo 步的四相符差异被显式容忍，"
                        "站点照常发布，差异以红色事项呈现。" if tolerated_steps else "")),
        }
        (out_dir / "run_summary.json").write_bytes(
            json.dumps(summary, ensure_ascii=False, indent=2,
                       sort_keys=True).encode("utf-8") + b"\n")
        print(json.dumps({"status": overall, "run_id": run_id,
                          "outputs": str(out_dir), "failed_step": failed_step,
                          "differences_tolerated": bool(tolerated_steps)},
                         ensure_ascii=False))
        if overall in ("SUCCESS", "SUCCESS_WITH_DIFFERENCES") and open_browser:
            index_path = out_dir / "index.html"
            try:
                os.startfile(str(index_path))  # type: ignore[attr-defined]
            except (AttributeError, OSError):
                pass
        return 0 if overall in ("SUCCESS", "SUCCESS_WITH_DIFFERENCES") else 1
    except RunAllError as exc:
        print(json.dumps({"status": "ERROR", "kind": exc.kind, "error": str(exc)},
                         ensure_ascii=False))
        return 1 if exc.kind == "content" else 2


if __name__ == "__main__":
    raise SystemExit(main())
