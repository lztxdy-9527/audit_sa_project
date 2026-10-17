#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-003 / R1 接收入口集成验证。

用法：

    & 'D:\\harness work\\audit_sa_project\\.venv\\Scripts\\python.exe' -B `
      'D:\\harness work\\audit_sa_project\\tests\\test_receive_demo_batch.py' `
      --out-dir 'D:\\harness work\\audit_sa_project\\data\\batches\\task003_r1_tests_01'

验证方式：
  - 通过命令行运行真实 scripts/receive_demo_batch.py，再读取新批次产物并断言；
  - 故障只在内存中替换接收器模块的函数（复制、代码留档、checker 子进程、材料写入）或写在新测试副本上，
    不修改真实 checker、项目原输入、既有批次或磁盘源码，也不提供生产故障注入开关；
  - 参数拒绝、质量阻断、运行失败属于**预期负向案例**，与脚本自身失败分开记录；
  - 每次调用（含内存模拟）单独保存 stdout／stderr，命令日志区分 CLI 与内存模拟；
  - 只读输入前后哈希不一致、任何断言失败或未预期异常，整个测试进程返回非零，且不打印总体成功。

退出码：0 全部预期成立；1 存在断言失败或完整性失败；2 参数或环境问题。
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BATCHES_ROOT = (PROJECT_ROOT / "data" / "batches").resolve()
RECEIVER = PROJECT_ROOT / "scripts" / "receive_demo_batch.py"
CHECKER = PROJECT_ROOT / "scripts" / "check_demo_data.py"
GENERATOR = PROJECT_ROOT / "scripts" / "make_demo_data.py"

DEMO_DIR = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a"
MAIN_INPUT = DEMO_DIR / "input" / "erp_export.xlsx"
C01_INPUT = DEMO_DIR / "fixtures" / "C01.xlsx"
C14A_INPUT = DEMO_DIR / "fixtures" / "C14a.xlsx"
C14C_INPUT = DEMO_DIR / "fixtures" / "C14c.xlsx"

READ_ONLY_INPUTS = [
    MAIN_INPUT,
    *sorted((DEMO_DIR / "fixtures").glob("*.xlsx")),
    CHECKER,
    GENERATOR,
    PROJECT_ROOT / "docs" / "SPEC_V1.md",
    PROJECT_ROOT / "docs" / "AUDIT_CONTRACT_DRAFT.md",
    PROJECT_ROOT / "docs" / "EXEC_REPORT_002.md",
    PROJECT_ROOT / "docs" / "EXEC_REPORT_002_R1.md",
    PROJECT_ROOT / "docs" / "EXEC_REPORT_002_R2.md",
    PROJECT_ROOT / "docs" / "EXEC_REPORT_003.md",
    PROJECT_ROOT / "docs" / "reviews" / "REVIEW_TASK_002_R2.md",
    PROJECT_ROOT / "docs" / "reviews" / "REVIEW_TASK_003.md",
    PROJECT_ROOT / "docs" / "reviews" / "REVIEW_TASK_003_R1.md",
    PROJECT_ROOT / "docs" / "tasks" / "TASK-003_DRAFT.md",
    PROJECT_ROOT / "docs" / "tasks" / "TASK-003-R1.md",
    PROJECT_ROOT / "docs" / "tasks" / "TASK-003-R2.md",
    PROJECT_ROOT / "docs" / "EXEC_REPORT_003.md",
    PROJECT_ROOT / "docs" / "EXEC_REPORT_003_R1.md",
]

PACKET_REQUIRED = "开发态候审材料，未批准，不代表可以进入标准化"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> "None":
    print(f"RUNTIME_ERROR: {message}", file=sys.stderr)
    sys.exit(2)


class Context:
    def __init__(self, exit_code: int, batch_dir: Path, stdout_log: Path, stderr_log: Path):
        self.exit_code = exit_code
        self.batch_dir = batch_dir
        self.stdout_log = stdout_log
        self.stderr_log = stderr_log
        self.manifest = None
        self.report = None
        self.packet_text = None
        manifest_path = batch_dir / "batch_manifest.json"
        if manifest_path.exists():
            self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report_path = batch_dir / "checks" / "quality_report.json"
        if report_path.exists():
            try:
                self.report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.report = None
        packet_path = batch_dir / "gate1_packet.md"
        if packet_path.exists():
            self.packet_text = packet_path.read_text(encoding="utf-8")


class Suite:
    def __init__(self, container: Path) -> None:
        self.container = container
        self.inputs = container / "inputs"
        self.batches = container / "batches"
        self.logs = container / "logs"
        for directory in (self.inputs, self.batches, self.logs):
            directory.mkdir(parents=True, exist_ok=True)
        self.calls = 0
        self.cli_calls = 0
        self.memory_calls = 0
        self.results: list[dict] = []
        self.failures: list[dict] = []
        self.expected_negatives: list[dict] = []
        self.command_log: list[dict] = []

    def _log_paths(self, case: str, suffix: str) -> tuple[Path, Path]:
        return (
            self.logs / f"{self.calls:02d}_{case}{suffix}.stdout.txt",
            self.logs / f"{self.calls:02d}_{case}{suffix}.stderr.txt",
        )

    def run_receiver(self, case: str, args: list[str]) -> Context:
        self.calls += 1
        self.cli_calls += 1
        stdout_log, stderr_log = self._log_paths(case, "")
        command = [sys.executable, str(RECEIVER), *args]
        with stdout_log.open("w", encoding="utf-8") as out, stderr_log.open("w", encoding="utf-8") as err:
            exit_code = subprocess.run(command, stdout=out, stderr=err).returncode
        batch_dir = Path(args[args.index("--out-dir") + 1])
        self.command_log.append(
            {
                "call_index": self.calls,
                "mode": "cli",
                "case": case,
                "command": command,
                "exit_code": exit_code,
                "stdout_log": str(stdout_log),
                "stderr_log": str(stderr_log),
            }
        )
        return Context(exit_code, batch_dir, stdout_log, stderr_log)

    def run_simulated(self, case: str, args: list[str], patches: dict) -> Context:
        """在内存中加载接收器模块并替换指定函数，不改动磁盘源码。"""
        self.calls += 1
        self.memory_calls += 1
        stdout_log, stderr_log = self._log_paths(case, ".sim")
        spec = importlib.util.spec_from_file_location(f"receiver_sim_{self.calls}", RECEIVER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        originals = {}
        for name, factory in patches.items():
            originals[name] = getattr(module, name)
            setattr(module, name, factory(originals[name]))
        try:
            with stdout_log.open("w", encoding="utf-8") as out, stderr_log.open(
                "w", encoding="utf-8"
            ) as err, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                exit_code = module.main(args)
        finally:
            for name, original in originals.items():
                setattr(module, name, original)
        batch_dir = Path(args[args.index("--out-dir") + 1])
        self.command_log.append(
            {
                "call_index": self.calls,
                "mode": "in_memory_simulation",
                "case": case,
                "patched": sorted(patches),
                "command": ["<in_memory>", str(RECEIVER), *args],
                "exit_code": exit_code,
                "stdout_log": str(stdout_log),
                "stderr_log": str(stderr_log),
                "note": "仅替换内存中的模块函数，磁盘源码与真实输入未改动",
            }
        )
        return Context(exit_code, batch_dir, stdout_log, stderr_log)

    def _judge(self, case: str, context: Context, exit_code: int, checks: dict, negative: bool, note: str = "") -> Context:
        problems: list[str] = []
        if context.exit_code != exit_code:
            problems.append(f"接收入口退出码期望 {exit_code}，实际 {context.exit_code}")
        for label, predicate in (checks or {}).items():
            try:
                ok = bool(predicate(context))
            except Exception as exc:  # noqa: BLE001
                ok = False
                problems.append(f"{label} 读取产物时异常：{exc!r}")
            if not ok:
                problems.append(f"断言失败：{label}")
        record = {
            "case": case,
            "kind": "expected_negative" if negative else "positive",
            "batch_dir": str(context.batch_dir),
            "exit_code": context.exit_code,
            "expected_exit_code": exit_code,
            "batch_status": (context.manifest or {}).get("batch_status"),
            "failure_reasons": (context.manifest or {}).get("failure_reasons", []),
            "failure_stage": ((context.manifest or {}).get("failure") or {}).get("stage"),
            "stdout_log": str(context.stdout_log),
            "stderr_log": str(context.stderr_log),
            "result": "PASS" if not problems else "FAIL",
            "problems": problems,
            "note": note,
        }
        self.results.append(record)
        if problems:
            self.failures.append(record)
        elif negative:
            self.expected_negatives.append({"case": case, "exit_code": context.exit_code})
        print(f"[{'PASS' if not problems else 'FAIL'}] {case} exit={context.exit_code}"
              + ("" if not problems else "  | " + " ; ".join(problems)))
        return context

    def expect(self, case: str, args: list[str], *, exit_code: int, checks: dict | None = None,
               negative: bool = False) -> Context:
        return self._judge(case, self.run_receiver(case, args), exit_code, checks or {}, negative)

    def expect_simulated(self, case: str, args: list[str], patches: dict, *, exit_code: int,
                         checks: dict | None = None, negative: bool = False) -> Context:
        return self._judge(
            case, self.run_simulated(case, args, patches), exit_code, checks or {}, negative,
            note="内存模拟",
        )


# ---------- 通用断言 ----------
def manifest_status(ctx: Context, status: str) -> bool:
    return (ctx.manifest or {}).get("batch_status") == status


def no_approvals(ctx: Context) -> bool:
    m = ctx.manifest or {}
    return (
        m.get("gate1_approval") is None
        and m.get("gate2_approval") is None
        and m.get("next_step_allowed") is False
        and m.get("contract_status") == "DRAFT_NOT_IN_FORCE"
    )


def snapshot_matches_source(ctx: Context) -> bool:
    h = (ctx.manifest or {}).get("hashes", {})
    return (
        h.get("snapshot_matches_source") is True
        and h.get("source_before_copy") == h.get("source_after_copy") == h.get("source_after_check")
        and h.get("snapshot_after_copy") == h.get("snapshot_after_check")
        and h.get("checker", {}).get("stable_during_run") is True
        and h.get("receive_script", {}).get("stable_during_run") is True
    )


def report_checked_snapshot(ctx: Context) -> bool:
    ci = (ctx.manifest or {}).get("checker_invocation", {})
    h = (ctx.manifest or {}).get("hashes", {})
    return (
        ci.get("report_matches_snapshot") is True
        and ci.get("report_matches_checker") is True
        and (ctx.report or {}).get("workbook", {}).get("sha256") == h.get("snapshot_after_copy")
    )


def code_snapshots_match(ctx: Context) -> bool:
    snapshot = (ctx.manifest or {}).get("code_snapshot", {})
    return bool(snapshot) and all(item.get("matches_source") is True for item in snapshot.values())


def packet_ok(ctx: Context) -> bool:
    return ctx.packet_text is not None and PACKET_REQUIRED in ctx.packet_text


def packet_not_success_looking(ctx: Context) -> bool:
    text = ctx.packet_text or ""
    return (
        "核验未完成" in text
        and "问题总数：0" not in text
        and "未记录数据质量或范围问题" not in text
    )


def amount(ctx: Context, group: str, label: str):
    return ((ctx.report or {}).get("amount_summary", {}).get(group, {}) or {}).get(label)


def row_counts(ctx: Context) -> dict:
    return {
        sheet: value.get("source_rows")
        for sheet, value in (ctx.report or {}).get("row_accounting", {}).items()
    }


def packet_manifest_consistent(ctx: Context) -> bool:
    """候审材料必须真实存在，且清单里的状态与哈希对应磁盘现场。"""
    info = (ctx.manifest or {}).get("gate1_packet", {})
    path = ctx.batch_dir / "gate1_packet.md"
    if not path.exists():
        return False
    return info.get("exists") is True and info.get("sha256") == sha256(path)


def artifacts_complete(ctx: Context) -> bool:
    expected = [
        "source/input.xlsx",
        "checks/quality_report.json",
        "logs/checker.stdout.txt",
        "logs/checker.stderr.txt",
        "code_snapshot/receive_demo_batch.py",
        "code_snapshot/check_demo_data.py",
        "batch_manifest.json",
        "gate1_packet.md",
    ]
    return all((ctx.batch_dir / rel).exists() for rel in expected)


# 22 份既有 fixture 经真实接收入口运行的预期退出码（依据 SPEC_V1.md 第 6 节）
FIXTURE_EXPECTED_EXIT = {
    "C01": 0, "C02": 0, "C03": 0, "C04": 0, "C05": 0, "C06": 0, "C07": 0, "C08": 0, "C09": 0, "C10": 0,
    "C11": 1, "C12": 1, "C13": 1, "C06b": 0, "C07b": 0, "C09b": 0, "C10b": 0,
    "C14a": 1, "C14b": 1, "C14c": 1, "C14d": 1, "C14e": 1,
}


# ---------- 内存故障注入构造器 ----------
def partial_copy_failure(_original):
    def patched(source, target):
        target.write_bytes(source.read_bytes()[:32])
        raise OSError("模拟：快照写入部分字节后失败")
    return patched


def tampered_copy_success(_original):
    """复制成功但字节与源不同，用于验证“快照与源不一致”的失败分支。"""

    def patched(source, target):
        target.write_bytes(source.read_bytes() + b"\n")
    return patched


def fake_report_runner(payload_builder, exit_code: int):
    """payload_builder(report_path, workbook_path) 负责写报告；返回替换 run_checker_subprocess 的工厂。"""

    def factory(_original):
        def patched(argv, stdout_handle, stderr_handle):
            report_path = Path(argv[argv.index("--report") + 1])
            workbook_path = Path(argv[argv.index("--workbook") + 1])
            stdout_handle.write("[模拟] checker 子进程被替换，只写测试报告\n")
            stderr_handle.write("")
            payload_builder(report_path, workbook_path)
            return exit_code
        return patched

    return factory


def corrupt_code_snapshot(target_name: str):
    def factory(original):
        def patched(source, target):
            original(source, target)
            if target.name == target_name:
                target.write_bytes(target.read_bytes() + b"x")
        return patched

    return factory


def packet_write_fails(times: int | None):
    """times=None 表示每次都失败；否则只让前 times 次失败。"""

    def factory(original):
        state = {"count": 0}

        def patched(path, text):
            if path.name == "gate1_packet.md":
                state["count"] += 1
                if times is None or state["count"] <= times:
                    raise OSError("模拟：候审材料写入失败")
            return original(path, text)

        return patched

    return factory


def hash_read_fails_for(target_name: str):
    """让指定文件名的哈希读取抛 OSError，其它文件照常。"""

    def factory(original):
        def patched(path):
            if path.name == target_name:
                raise OSError(f"模拟：{target_name} 哈希读取失败")
            return original(path)

        return patched

    return factory


def manifest_commit_fails_once(original):
    """首次提交先落盘完整字节再报错，模拟可恢复的写入／关闭失败。"""
    state = {"count": 0}

    def patched(path, text):
        state["count"] += 1
        if state["count"] == 1:
            path.write_text(text, encoding="utf-8")
            raise OSError("模拟：清单写入／关闭失败（字节已落盘）")
        return original(path, text)

    return patched


def checker_launch_fails(_original):
    def patched(argv, stdout_handle, stderr_handle):
        raise FileNotFoundError("模拟：checker 子进程无法启动")

    return patched


def read_bytes_fails_for_path(target_path: str, call_number: int):
    """只在该路径第 N 次读取字节时抛 OSError（存在性检查仍成功），用于进入结束哈希分支。"""

    def factory(original):
        counts = {"n": 0}

        def patched(path):
            if str(path) == target_path:
                counts["n"] += 1
                if counts["n"] == call_number:
                    raise OSError(
                        f"模拟：第 {call_number} 次读取 {Path(target_path).name} 字节失败"
                    )
            return original(path)

        return patched

    return factory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TASK-003 / R1 接收入口集成验证")
    parser.add_argument("--out-dir", required=True, help="data/batches 内尚不存在的测试容器目录")
    args = parser.parse_args(argv)

    container = Path(args.out_dir)
    container = container.resolve() if container.is_absolute() else (Path.cwd() / container).resolve()
    try:
        container.relative_to(BATCHES_ROOT)
    except ValueError:
        fail(f"测试容器必须位于 {BATCHES_ROOT} 之内：{container}")
    if container == BATCHES_ROOT:
        fail("测试容器不能是 data/batches 本身")
    if container.exists():
        fail(f"测试容器已存在，拒绝覆盖历史：{container}")
    for required in (RECEIVER, CHECKER, GENERATOR, MAIN_INPUT, C01_INPUT, C14A_INPUT, C14C_INPUT):
        if not required.exists():
            fail(f"缺少必需输入：{required}")

    hashes_before = {str(p): sha256(p) for p in READ_ONLY_INPUTS}
    real_checker_hash_before = sha256(CHECKER)
    real_receiver_hash_before = sha256(RECEIVER)
    batches_children_before = sorted(p.name for p in BATCHES_ROOT.iterdir())

    container.mkdir(parents=True)
    suite = Suite(container)
    print(f"测试容器: {container}")
    print(f"被验证入口: {RECEIVER}")
    print()

    c01_copy = suite.inputs / "C01_input.xlsx"
    c14a_copy = suite.inputs / "C14a_input.xlsx"
    c14c_copy = suite.inputs / "C14c_input.xlsx"
    shutil.copyfile(C01_INPUT, c01_copy)
    shutil.copyfile(C14A_INPUT, c14a_copy)
    shutil.copyfile(C14C_INPUT, c14c_copy)
    corrupt_copy = suite.inputs / "not_a_workbook.xlsx"
    corrupt_copy.write_bytes("这只是一个纯文本文件，不是有效的 xlsx 工作簿。\n".encode("utf-8"))
    input_copies = (c01_copy, c14a_copy, c14c_copy, corrupt_copy)
    source_hashes_of_copies = {str(p): sha256(p) for p in input_copies}

    def batch(name: str) -> str:
        return str(suite.batches / name)

    raw_description = "  原始来源说明：C01 合成数据  \n第二行保留原样  "

    # ---------- 1. 原 10 个案例 ----------
    c01_ctx = suite.expect(
        "C01_valid",
        ["--workbook", str(c01_copy), "--out-dir", batch("C01_valid"),
         "--source-description", "开发验证：C01 单笔足额付款案例副本"],
        exit_code=0,
        checks={
            "状态为 DEV_GATE1_PACKET_READY": lambda c: manifest_status(c, "DEV_GATE1_PACKET_READY"),
            "无失败原因": lambda c: (c.manifest or {}).get("failure_reasons") == [],
            "快照与源字节一致且版本稳定": snapshot_matches_source,
            "两份源码留档与执行版本一致": code_snapshots_match,
            "报告核验的是本批次快照": report_checked_snapshot,
            "未伪造成批准": no_approvals,
            "完整金额 500000 分": lambda c: amount(c, "complete_totals_cents", "payments_amount") == 500000
            and amount(c, "complete_totals_cents", "allocations_allocated_amount") == 500000,
            "候审材料含固定声明": packet_ok,
            "材料存在且清单哈希与磁盘一致": packet_manifest_consistent,
            "8 项产物齐全": artifacts_complete,
            "快照文件存在": lambda c: (c.batch_dir / "source" / "input.xlsx").exists(),
            "代码副本齐全": lambda c: all(
                (c.batch_dir / "code_snapshot" / name).exists()
                for name in ("receive_demo_batch.py", "check_demo_data.py")
            ),
        },
    )
    template_report_path = Path(c01_ctx.batch_dir) / "checks" / "quality_report.json"
    template_report = json.loads(template_report_path.read_text(encoding="utf-8"))

    suite.expect(
        "MAIN_demo",
        ["--workbook", str(MAIN_INPUT), "--out-dir", batch("MAIN_demo"),
         "--source-description", "开发验证：现有合成 ERP 导出演示文件主工作簿"],
        exit_code=0,
        checks={
            "状态为 DEV_GATE1_PACKET_READY": lambda c: manifest_status(c, "DEV_GATE1_PACKET_READY"),
            "四表行数 20/993/1000/1005": lambda c: row_counts(c) == {
                "suppliers": 20, "payables": 993, "payments": 1000, "allocations": 1005,
            },
            "保留未知 AP 的资金部分（缺失关联净额 1000000 分）": lambda c: (
                (c.report or {}).get("reconciliation", {}).get(
                    "diagnostic_known_valid_subtotals_cents", {}
                ).get("missing_payable_link_net") == 1000000
            ),
            "勾稽正常评估且相等": lambda c: (c.report or {}).get("reconciliation", {}).get("status") == "ASSESSED"
            and (c.report or {}).get("reconciliation", {}).get("known_plus_missing_equals_master") is True,
            "未伪造成批准": no_approvals,
            "候选审材料含固定声明": packet_ok,
            "材料存在且清单哈希与磁盘一致": packet_manifest_consistent,
            "8 项产物齐全": artifacts_complete,
        },
    )
    suite.expect(
        "C14a_missing_column",
        ["--workbook", str(c14a_copy), "--out-dir", batch("C14a_missing_column"),
         "--source-description", "开发验证：C14a 缺 payable_amount 列的负向案例"],
        exit_code=1,
        negative=True,
        checks={
            "状态为 BLOCKED_QUALITY": lambda c: manifest_status(c, "BLOCKED_QUALITY"),
            "无失败原因（属质量阻断而非运行失败）": lambda c: (c.manifest or {}).get("failure_reasons") == [],
            "报告结构校验通过": lambda c: (c.manifest or {}).get("report_validation", {}).get("valid") is True,
            "报告记录了 REQUIRED_COLUMN_MISSING": lambda c: "REQUIRED_COLUMN_MISSING"
            in (c.report or {}).get("issue_counts_by_code", {}),
            "payables 完整金额为 null 且已知小计也为 null": lambda c: amount(
                c, "complete_totals_cents", "payables_payable_amount"
            ) is None and amount(c, "known_valid_subtotals_cents", "payables_payable_amount") is None,
            "快照已保留": lambda c: (c.batch_dir / "source" / "input.xlsx").exists(),
            "未变成候审就绪": lambda c: (c.manifest or {}).get("batch_status") != "DEV_GATE1_PACKET_READY",
            "材料存在且清单哈希与磁盘一致": packet_manifest_consistent,
            "8 项产物齐全": artifacts_complete,
            "未伪造成批准": no_approvals,
        },
    )
    suite.expect(
        "C14c_amount_invalid",
        ["--workbook", str(c14c_copy), "--out-dir", batch("C14c_amount_invalid"),
         "--source-description", "开发验证：C14c 关键金额无法解析的负向案例"],
        exit_code=1,
        negative=True,
        checks={
            "状态为 BLOCKED_QUALITY": lambda c: manifest_status(c, "BLOCKED_QUALITY"),
            "报告记录了 AMOUNT_INVALID": lambda c: "AMOUNT_INVALID"
            in (c.report or {}).get("issue_counts_by_code", {}),
            "payments 完整金额为 null": lambda c: amount(c, "complete_totals_cents", "payments_amount") is None,
            "不可用金额单元格已计数": lambda c: (
                (c.report or {}).get("amount_summary", {}).get("unusable_amount_cells", {}).get("total", 0) >= 1
            ),
            "未伪造成批准": no_approvals,
        },
    )
    suite.expect(
        "unreadable_xlsx",
        ["--workbook", str(corrupt_copy), "--out-dir", batch("unreadable_xlsx"),
         "--source-description", "开发验证：非工作簿文件，用于运行失败路径"],
        exit_code=2,
        negative=True,
        checks={
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "失败原因非空": lambda c: bool((c.manifest or {}).get("failure_reasons")),
            "没有质量报告": lambda c: not (c.batch_dir / "checks" / "quality_report.json").exists(),
            "清单记录报告不存在": lambda c: (c.manifest or {}).get("checker_invocation", {}).get("report", {}).get("exists") is False,
            "快照仍保留（不删除现场）": lambda c: (c.batch_dir / "source" / "input.xlsx").exists(),
            "候审材料写明核验未完成且不填零": packet_not_success_looking,
            "未伪造成批准": no_approvals,
        },
    )
    before_hashes = {
        str(p): sha256(p) for p in sorted(Path(c01_ctx.batch_dir).rglob("*")) if p.is_file()
    }
    suite.expect(
        "RERUN_same_out_dir",
        ["--workbook", str(c01_copy), "--out-dir", batch("C01_valid"),
         "--source-description", "重复调用应被拒绝"],
        exit_code=2,
        negative=True,
        checks={
            "原有批次文件全部未变": lambda c: {
                str(p): sha256(p) for p in sorted(Path(c01_ctx.batch_dir).rglob("*")) if p.is_file()
            } == before_hashes,
        },
    )
    out_of_bounds = PROJECT_ROOT / "data" / "task003_oob_probe_outside_batches"
    suite.expect(
        "PARAM_out_of_bounds",
        ["--workbook", str(c01_copy), "--out-dir", str(out_of_bounds),
         "--source-description", "越界输出目录应被拒绝"],
        exit_code=2,
        negative=True,
        checks={"越界目录未被创建": lambda c: not out_of_bounds.exists()},
    )
    suite.expect(
        "PARAM_batches_root_itself",
        ["--workbook", str(c01_copy), "--out-dir", str(BATCHES_ROOT),
         "--source-description", "指向 data/batches 本身应被拒绝"],
        exit_code=2,
        negative=True,
        checks={
            "data/batches 仍存在": lambda c: BATCHES_ROOT.is_dir(),
            "未新增其他批次目录": lambda c: sorted(p.name for p in BATCHES_ROOT.iterdir())
            == sorted(batches_children_before + [container.name]),
        },
    )
    suite.expect(
        "PARAM_missing_input",
        ["--workbook", str(suite.inputs / "does_not_exist.xlsx"), "--out-dir", batch("PARAM_missing_input"),
         "--source-description", "输入不存在应被拒绝"],
        exit_code=2,
        negative=True,
        checks={"批次目录未被创建": lambda c: not (suite.batches / "PARAM_missing_input").exists()},
    )
    suite.expect_simulated(
        "SNAPSHOT_mismatch_simulated",
        ["--workbook", str(c01_copy), "--out-dir", batch("SNAPSHOT_mismatch"),
         "--source-description", "内存模拟：复制出的快照与源字节不一致"],
        {"copy_snapshot_bytes": tampered_copy_success},
        exit_code=2,
        negative=True,
        checks={
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "清单未把快照当作完整": lambda c: (c.manifest or {}).get("hashes", {}).get("snapshot_matches_source") is False,
            "失败原因含快照不一致": lambda c: "快照" in " ".join((c.manifest or {}).get("failure_reasons", [])),
            "未生成质量报告": lambda c: not (c.batch_dir / "checks" / "quality_report.json").exists(),
            "next_step_allowed=false": lambda c: (c.manifest or {}).get("next_step_allowed") is False,
        },
    )

    # ---------- 2. R1 新增：来源声明保真 ----------
    raw_ctx = suite.expect(
        "R1_source_description_raw",
        ["--workbook", str(c01_copy), "--out-dir", batch("R1_source_description_raw"),
         "--source-description", raw_description],
        exit_code=0,
        checks={
            "清单逐字符等于传入原字符串": lambda c: (c.manifest or {}).get("source", {}).get("source_description")
            == raw_description,
            "状态为 DEV_GATE1_PACKET_READY": lambda c: manifest_status(c, "DEV_GATE1_PACKET_READY"),
            "候审材料含固定声明": packet_ok,
        },
    )
    print(f"     来源声明原字符串长度 {len(raw_description)}，清单保存长度 "
          f"{len((raw_ctx.manifest or {}).get('source', {}).get('source_description', ''))}")
    suite.expect(
        "R1_source_description_blank",
        ["--workbook", str(c01_copy), "--out-dir", batch("R1_source_description_blank"),
         "--source-description", "   \n\t  "],
        exit_code=2,
        negative=True,
        checks={"批次目录未被创建": lambda c: not (suite.batches / "R1_source_description_blank").exists()},
    )

    # ---------- 3. R1 新增：复制阶段 OSError ----------
    suite.expect_simulated(
        "R1_copy_io_failure",
        ["--workbook", str(c01_copy), "--out-dir", batch("R1_copy_io_failure"),
         "--source-description", "内存模拟：快照写入部分字节后抛 OSError"],
        {"copy_snapshot_bytes": partial_copy_failure},
        exit_code=2,
        negative=True,
        checks={
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "留在可写目录里且有失败清单": lambda c: (c.batch_dir / "batch_manifest.json").exists(),
            "失败阶段为 copy_snapshot": lambda c: ((c.manifest or {}).get("failure") or {}).get("stage") == "copy_snapshot",
            "部分现场保留（快照不完整）": lambda c: (c.batch_dir / "source" / "input.xlsx").exists()
            and (c.batch_dir / "source" / "input.xlsx").stat().st_size < MAIN_INPUT.stat().st_size,
            "没有伪造质量报告": lambda c: not (c.batch_dir / "checks" / "quality_report.json").exists(),
            "checker 未启动且不虚构退出码": lambda c: (c.manifest or {}).get("checker_invocation", {}).get("started") is False
            and (c.manifest or {}).get("checker_invocation", {}).get("exit_code") is None,
            "未伪造成批准": no_approvals,
        },
    )

    # ---------- 4. R1 新增：报告结构与类型 ----------
    def build_valid_payload(report_path: Path, workbook_path: Path, mutate) -> None:
        payload = copy.deepcopy(template_report)
        payload["workbook"]["sha256"] = sha256(workbook_path)
        payload["checker"]["sha256"] = real_checker_hash_before
        mutate(payload)
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_array(report_path: Path, workbook_path: Path) -> None:
        report_path.write_text("[]\n", encoding="utf-8")

    def write_missing_sections(report_path: Path, workbook_path: Path) -> None:
        payload = {
            "result": "pass",
            "workbook": {"sha256": sha256(workbook_path)},
            "checker": {"sha256": real_checker_hash_before},
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_invalid_json(report_path: Path, workbook_path: Path) -> None:
        report_path.write_text('{ "result": "pass", "structure":\n', encoding="utf-8")

    for case, builder, label, extra_checks in (
        ("R1_report_array", write_array, "报告为合法 JSON 数组", {}),
        ("R1_report_structure_array",
         lambda rp, wp: build_valid_payload(rp, wp, lambda p: p.__setitem__("structure", [])),
         "structure 为数组", {}),
        ("R1_report_missing_sections", write_missing_sections, "缺少必需区段", {}),
        ("R1_report_invalid_json", write_invalid_json, "JSON 语法错误",
         {"记录了报告解析异常": lambda c: any(
             item.get("stage") == "read_report"
             for item in ((c.manifest or {}).get("failure") or {}).get("exceptions", [])
         )}),
    ):
        checks = {
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "不产生候审就绪清单": lambda c: (c.manifest or {}).get("batch_status") != "DEV_GATE1_PACKET_READY",
            "报告未被判为有效": lambda c: (c.manifest or {}).get("report_validation", {}).get("valid") is not True,
            "失败原因非空": lambda c: bool((c.manifest or {}).get("failure_reasons")),
            "报告原文件保留未被改写": lambda c: (c.batch_dir / "checks" / "quality_report.json").exists(),
            "材料说明核验未完成且不显示零问题": packet_not_success_looking,
            "未伪造成批准": no_approvals,
        }
        checks.update(extra_checks)
        suite.expect_simulated(
            case,
            ["--workbook", str(c01_copy), "--out-dir", batch(case),
             "--source-description", f"内存模拟：{label}"],
            {"run_checker_subprocess": fake_report_runner(builder, 0)},
            exit_code=2,
            negative=True,
            checks=checks,
        )

    # ---------- 5. R1 新增：代码留档一致性 ----------
    for target, label in (("check_demo_data.py", "checker 留档"), ("receive_demo_batch.py", "接收器留档")):
        suite.expect_simulated(
            f"R1_code_snapshot_mismatch_{target}",
            ["--workbook", str(c01_copy), "--out-dir", batch(f"R1_code_snapshot_mismatch_{target}"),
             "--source-description", f"内存模拟：{label}副本被追加字节"],
            {"copy_code_snapshot": corrupt_code_snapshot(target)},
            exit_code=2,
            negative=True,
            checks={
                "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
                "清单记录副本与执行版本不一致": lambda c: any(
                    item.get("matches_source") is False
                    for item in (c.manifest or {}).get("code_snapshot", {}).values()
                ),
                "失败原因含留档不一致": lambda c: "源码留档" in " ".join((c.manifest or {}).get("failure_reasons", [])),
                "未伪造成批准": no_approvals,
            },
        )

    # ---------- 6. R1 新增：候审材料写入失败 ----------
    suite.expect_simulated(
        "R1_packet_write_failure_once",
        ["--workbook", str(c01_copy), "--out-dir", batch("R1_packet_write_failure_once"),
         "--source-description", "内存模拟：候审材料第一次写入抛 OSError"],
        {"write_text_artifact": packet_write_fails(1)},
        exit_code=2,
        negative=True,
        checks={
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "receive_exit_code 不是 0": lambda c: (c.manifest or {}).get("receive_exit_code") == 2,
            "没有遗留候审就绪状态": lambda c: (c.manifest or {}).get("batch_status") != "DEV_GATE1_PACKET_READY",
            "记录材料写入失败": lambda c: bool(((c.manifest or {}).get("failure") or {}).get("material_write_failures")),
            "材料已保存且显示失败状态": lambda c: (c.batch_dir / "gate1_packet.md").exists()
            and "FAILED_RUNTIME" in (c.packet_text or "")
            and "DEV_GATE1_PACKET_READY" not in (c.packet_text or ""),
            "材料记录了失败原因": lambda c: "失败原因" in (c.packet_text or ""),
            "未伪造成批准": no_approvals,
        },
    )
    suite.expect_simulated(
        "R1_packet_write_failure_always",
        ["--workbook", str(c01_copy), "--out-dir", batch("R1_packet_write_failure_always"),
         "--source-description", "内存模拟：候审材料始终无法写入"],
        {"write_text_artifact": packet_write_fails(None)},
        exit_code=2,
        negative=True,
        checks={
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "清单仍保存并记录实际缺失": lambda c: (c.batch_dir / "batch_manifest.json").exists()
            and (c.manifest or {}).get("gate1_packet", {}).get("exists") is False
            and bool(((c.manifest or {}).get("failure") or {}).get("material_write_failures")),
            "没有遗留候审就绪状态": lambda c: (c.manifest or {}).get("batch_status") != "DEV_GATE1_PACKET_READY",
            "未伪造成批准": no_approvals,
        },
    )

    # ---------- 7. R2 新增：报告 null 与必需内容缺失 ----------
    def write_null(report_path: Path, workbook_path: Path) -> None:
        report_path.write_text("null\n", encoding="utf-8")

    def write_row_accounting_empty(report_path: Path, workbook_path: Path) -> None:
        build_valid_payload(report_path, workbook_path, lambda p: p.__setitem__("row_accounting", {}))

    def write_amount_keys_missing(report_path: Path, workbook_path: Path) -> None:
        def mutate(payload):
            for field in ("known_valid_subtotals_cents", "complete_totals_cents"):
                for key in ("payables_payable_amount", "payments_amount", "allocations_allocated_amount"):
                    payload["amount_summary"][field].pop(key, None)

        build_valid_payload(report_path, workbook_path, mutate)

    def write_amount_parent_null(report_path: Path, workbook_path: Path) -> None:
        build_valid_payload(
            report_path,
            workbook_path,
            lambda p: p["amount_summary"].__setitem__("known_valid_subtotals_cents", None),
        )

    for case, builder, label in (
        ("R2_report_null", write_null, "报告为合法 JSON null"),
        ("R2_report_row_accounting_empty", write_row_accounting_empty, "row_accounting 为空对象"),
        ("R2_report_amount_keys_missing", write_amount_keys_missing, "金额三项必需键缺失"),
        ("R2_report_amount_parent_null", write_amount_parent_null, "金额父区段为 null"),
    ):
        suite.expect_simulated(
            case,
            ["--workbook", str(c01_copy), "--out-dir", batch(case), "--source-description", f"内存模拟：{label}"],
            {"run_checker_subprocess": fake_report_runner(builder, 0)},
            exit_code=2,
            negative=True,
            checks={
                "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
                "不产生候审就绪清单": lambda c: (c.manifest or {}).get("batch_status") != "DEV_GATE1_PACKET_READY",
                "报告未被判为有效": lambda c: (c.manifest or {}).get("report_validation", {}).get("valid") is not True,
                "材料写明核验未完成且不显示零问题": packet_not_success_looking,
                "未伪造成批准": no_approvals,
            },
        )

    # ---------- 8. R2 新增：收尾阶段读写失败 ----------
    suite.expect_simulated(
        "R2_spec_hash_read_failure",
        ["--workbook", str(c01_copy), "--out-dir", batch("R2_spec_hash_read_failure"),
         "--source-description", "内存模拟：最终清单阶段读取 SPEC 哈希失败"],
        {"safe_hash_file": hash_read_fails_for("SPEC_V1.md")},
        exit_code=2,
        negative=True,
        checks={
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "清单仍保存": lambda c: (c.batch_dir / "batch_manifest.json").exists(),
            "规格哈希未知并记录读取错误": lambda c: (c.manifest or {}).get("hashes", {}).get("spec", {}).get("sha256") is None
            and bool((c.manifest or {}).get("hashes", {}).get("spec", {}).get("read_error")),
            "未把存在的文件写成不存在": lambda c: (c.manifest or {}).get("hashes", {}).get("spec", {}).get("exists") is None,
            "未伪造成批准": no_approvals,
        },
    )
    suite.expect_simulated(
        "R2_report_hash_read_failure",
        ["--workbook", str(c01_copy), "--out-dir", batch("R2_report_hash_read_failure"),
         "--source-description", "内存模拟：最终报告哈希读取失败"],
        {"safe_hash_file": hash_read_fails_for("quality_report.json")},
        exit_code=2,
        negative=True,
        checks={
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "原报告保留且未崩溃": lambda c: (c.batch_dir / "checks" / "quality_report.json").exists()
            and (c.batch_dir / "batch_manifest.json").exists(),
            "报告存在状态未知": lambda c: (c.manifest or {}).get("checker_invocation", {}).get("report", {}).get("exists") is None,
            "未伪造成批准": no_approvals,
        },
    )
    suite.expect_simulated(
        "R2_manifest_commit_failure_once",
        ["--workbook", str(c01_copy), "--out-dir", batch("R2_manifest_commit_failure_once"),
         "--source-description", "内存模拟：清单首次提交落盘字节后报错"],
        {"commit_manifest": manifest_commit_fails_once},
        exit_code=2,
        negative=True,
        checks={
            "最终清单为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "receive_exit_code=2": lambda c: (c.manifest or {}).get("receive_exit_code") == 2,
            "记录了清单写入失败": lambda c: bool(((c.manifest or {}).get("failure") or {}).get("material_write_failures")),
            "材料不残留成功状态": lambda c: "DEV_GATE1_PACKET_READY" not in (c.packet_text or ""),
            "未伪造成批准": no_approvals,
        },
    )
    suite.expect_simulated(
        "R2_initial_source_hash_failure",
        ["--workbook", str(c01_copy), "--out-dir", batch("R2_initial_source_hash_failure"),
         "--source-description", "内存模拟：输入初次哈希失败"],
        {"safe_hash_file": hash_read_fails_for(c01_copy.name)},
        exit_code=2,
        negative=True,
        checks={
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "清单仍保存": lambda c: (c.batch_dir / "batch_manifest.json").exists(),
            "大小未知不填零": lambda c: (c.manifest or {}).get("source", {}).get("size_bytes") is None,
            "稳定性未知不写 true": lambda c: (c.manifest or {}).get("hashes", {}).get("checker", {}).get("stable_during_run") is None
            and (c.manifest or {}).get("hashes", {}).get("receive_script", {}).get("stable_during_run") is None,
            "checker 未启动且退出码为 null": lambda c: (c.manifest or {}).get("checker_invocation", {}).get("started") is not True
            and (c.manifest or {}).get("checker_invocation", {}).get("exit_code") is None,
            "未伪造成批准": no_approvals,
        },
    )
    suite.expect_simulated(
        "R2_checker_launch_failure",
        ["--workbook", str(c01_copy), "--out-dir", batch("R2_checker_launch_failure"),
         "--source-description", "内存模拟：checker 子进程无法启动"],
        {"run_checker_subprocess": checker_launch_fails},
        exit_code=2,
        negative=True,
        checks={
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "started 为 false": lambda c: (c.manifest or {}).get("checker_invocation", {}).get("started") is False,
            "attempted=true 且保留尝试参数": lambda c: (c.manifest or {}).get("checker_invocation", {}).get("attempted") is True
            and isinstance((c.manifest or {}).get("checker_invocation", {}).get("argv"), list),
            "退出码为 null": lambda c: (c.manifest or {}).get("checker_invocation", {}).get("exit_code") is None,
            "没有虚构质量报告": lambda c: not (c.batch_dir / "checks" / "quality_report.json").exists(),
            "未伪造成批准": no_approvals,
        },
    )

    # ---------- 9. 22 份既有 fixture 经真实接收入口运行（兼容性回归） ----------
    print()
    print("=== 22 份既有 fixture 经真实接收器运行 ===")
    for case_id in sorted(FIXTURE_EXPECTED_EXIT):
        expected_exit = FIXTURE_EXPECTED_EXIT[case_id]
        expected_status = "DEV_GATE1_PACKET_READY" if expected_exit == 0 else "BLOCKED_QUALITY"
        suite.expect(
            f"FIXTURE_{case_id}",
            [
                "--workbook", str(DEMO_DIR / "fixtures" / f"{case_id}.xlsx"),
                "--out-dir", batch(f"fixture_sweep/{case_id}"),
                "--source-description", f"R2 兼容性回归：既有 fixture {case_id}",
            ],
            exit_code=expected_exit,
            negative=expected_exit == 1,
            checks={
                "状态与预期一致": lambda c, s=expected_status: manifest_status(c, s),
                "报告结构校验通过": lambda c: (c.manifest or {}).get("report_validation", {}).get("valid") is True,
                "材料存在且清单哈希与磁盘一致": packet_manifest_consistent,
                "未伪造成批准": no_approvals,
            },
        )

    # ---------- 10. R3 新增：结束阶段必需哈希未知必须阻断 ----------
    c14a_end_hash_copy = suite.inputs / "C14a_end_hash.xlsx"
    shutil.copyfile(C14A_INPUT, c14a_end_hash_copy)
    missing_sheet_copy = suite.inputs / "C01_missing_payables.xlsx"
    shutil.copyfile(C01_INPUT, missing_sheet_copy)
    missing_sheet_workbook = load_workbook(missing_sheet_copy)
    del missing_sheet_workbook["payables"]
    missing_sheet_workbook.save(missing_sheet_copy)
    for extra in (c14a_end_hash_copy, missing_sheet_copy):
        source_hashes_of_copies[str(extra)] = sha256(extra)

    end_hash_cases = (
        ("R3_source_end_hash_unreadable", str(c01_copy), 3, "原输入（核验结束）",
         lambda c: (c.manifest or {}).get("hashes", {}).get("source_after_check") is None,
         lambda c: (c.manifest or {}).get("hashes", {}).get("source_before_copy")
         == (c.manifest or {}).get("hashes", {}).get("source_after_copy")),
        ("R3_snapshot_end_hash_unreadable",
         str(suite.batches / "R3_snapshot_end_hash_unreadable" / "source" / "input.xlsx"), 2,
         "原始快照（核验结束）",
         lambda c: (c.manifest or {}).get("hashes", {}).get("snapshot_after_check") is None,
         lambda c: (c.manifest or {}).get("hashes", {}).get("snapshot_matches_source") is True),
        ("R3_receiver_end_hash_unreadable", str(RECEIVER), 2, "接收入口源码（核验结束）",
         lambda c: (c.manifest or {}).get("hashes", {}).get("receive_script", {}).get("sha256_at_end") is None,
         lambda c: (c.manifest or {}).get("hashes", {}).get("receive_script", {}).get("stable_during_run") is not True),
        ("R3_checker_end_hash_unreadable", str(CHECKER), 2, "checker 源码（核验结束）",
         lambda c: (c.manifest or {}).get("hashes", {}).get("checker", {}).get("sha256_at_end") is None,
         lambda c: (c.manifest or {}).get("hashes", {}).get("checker", {}).get("stable_during_run") is not True),
    )
    for case, target_path, call_number, label, null_check, extra_check in end_hash_cases:
        checks = {
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "不能候审就绪": lambda c: (c.manifest or {}).get("batch_status") != "DEV_GATE1_PACKET_READY",
            "失败原因指明该次读取": lambda c, s=label: any(
                s in reason for reason in (c.manifest or {}).get("failure_reasons", [])
            ),
            "未知值诚实保留为 null": null_check,
            "该项未被当成已验证": extra_check,
            "清单与材料仍保存": lambda c: (c.batch_dir / "batch_manifest.json").exists()
            and (c.batch_dir / "gate1_packet.md").exists(),
            "未伪造成批准": no_approvals,
        }
        suite.expect_simulated(
            case,
            ["--workbook", str(c01_copy), "--out-dir", batch(case), "--source-description", f"内存模拟：{label}读取失败"],
            {"read_file_bytes": read_bytes_fails_for_path(target_path, call_number)},
            exit_code=2,
            negative=True,
            checks=checks,
        )

    suite.expect_simulated(
        "R3_c14a_end_hash_failure_upgrades_to_2",
        ["--workbook", str(c14a_end_hash_copy), "--out-dir", batch("R3_c14a_end_hash_failure_upgrades_to_2"),
         "--source-description", "内存模拟：质量阻断输入叠加结束哈希读取失败"],
        {"read_file_bytes": read_bytes_fails_for_path(str(c14a_end_hash_copy), 3)},
        exit_code=2,
        negative=True,
        checks={
            "由质量阻断升级为运行失败": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "退出码不是 1": lambda c: (c.manifest or {}).get("receive_exit_code") == 2,
            "checker 本身退出 1": lambda c: (c.manifest or {}).get("checker_invocation", {}).get("exit_code") == 1,
            "未伪造成批准": no_approvals,
        },
    )

    # ---------- 11. R3 新增：固定字段映射必须含必需键 ----------
    def mapping_key_missing(report_path: Path, workbook_path: Path) -> None:
        build_valid_payload(
            report_path,
            workbook_path,
            lambda p: p["structure"]["sheet_field_mapping"]["payables"].pop("payable_amount", None),
        )

    def mapping_entry_empty(report_path: Path, workbook_path: Path) -> None:
        build_valid_payload(
            report_path, workbook_path, lambda p: p["structure"]["sheet_field_mapping"].__setitem__("payables", {})
        )

    for case, builder, label in (
        ("R3_mapping_key_missing", mapping_key_missing, "删除 payables.payable_amount 映射键"),
        ("R3_mapping_entry_empty", mapping_entry_empty, "payables 映射对象为空"),
    ):
        suite.expect_simulated(
            case,
            ["--workbook", str(c01_copy), "--out-dir", batch(case), "--source-description", f"内存模拟：{label}"],
            {"run_checker_subprocess": fake_report_runner(builder, 0)},
            exit_code=2,
            negative=True,
            checks={
                "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
                "报告未被判为有效": lambda c: (c.manifest or {}).get("report_validation", {}).get("valid") is not True,
                "失败原因含固定字段映射": lambda c: any(
                    "固定字段" in reason or "为空对象" in reason
                    for reason in (c.manifest or {}).get("failure_reasons", [])
                ),
                "不产生候审就绪清单": lambda c: (c.manifest or {}).get("batch_status") != "DEV_GATE1_PACKET_READY",
                "未伪造成批准": no_approvals,
            },
        )

    # 正例：C14a 的 payable_amount 键存在且值为 null，仍是质量阻断（真实检查在 fixture 扫描中）
    # 正例：实际缺表时，不因缺失表的映射条目被判运行失败
    suite.expect(
        "R3_missing_sheet_still_blocked",
        ["--workbook", str(missing_sheet_copy), "--out-dir", batch("R3_missing_sheet_still_blocked"),
         "--source-description", "R3：删除 payables 表的副本，应为质量阻断"],
        exit_code=1,
        negative=True,
        checks={
            "状态为 BLOCKED_QUALITY": lambda c: manifest_status(c, "BLOCKED_QUALITY"),
            "报告结构仍有效": lambda c: (c.manifest or {}).get("report_validation", {}).get("valid") is True,
            "未因缺失表被判运行失败": lambda c: (c.manifest or {}).get("failure_reasons") == [],
            "缺失表不在 sheets_found 中": lambda c: "payables"
            not in (c.report or {}).get("structure", {}).get("sheets_found", []),
            "未伪造成批准": no_approvals,
        },
    )

    # ---------- 12. R3 新增：存在性已知、读取字节失败必须保留 exists=true ----------
    suite.expect_simulated(
        "R3_spec_read_bytes_failure_keeps_exists_true",
        ["--workbook", str(c01_copy), "--out-dir", batch("R3_spec_read_bytes_failure_keeps_exists_true"),
         "--source-description", "内存模拟：SPEC 存在性已知但读取字节失败"],
        {"read_file_bytes": read_bytes_fails_for_path(str(PROJECT_ROOT / "docs" / "SPEC_V1.md"), 1)},
        exit_code=2,
        negative=True,
        checks={
            "状态为 FAILED_RUNTIME": lambda c: manifest_status(c, "FAILED_RUNTIME"),
            "存在性保留为 true": lambda c: (c.manifest or {}).get("hashes", {}).get("spec", {}).get("exists") is True,
            "哈希为 null 且有读取错误": lambda c: (c.manifest or {}).get("hashes", {}).get("spec", {}).get("sha256") is None
            and bool((c.manifest or {}).get("hashes", {}).get("spec", {}).get("read_error")),
            "清单仍保存": lambda c: (c.batch_dir / "batch_manifest.json").exists(),
            "未伪造成批准": no_approvals,
        },
    )

    # ---------- 13. 只读输入保护 ----------
    hashes_after = {str(p): sha256(p) for p in READ_ONLY_INPUTS}
    changed_readonly = [p for p, digest in hashes_before.items() if hashes_after.get(p) != digest]
    changed_copies = [p for p, digest in source_hashes_of_copies.items() if sha256(Path(p)) != digest]
    real_sources_ok = (
        sha256(CHECKER) == real_checker_hash_before and sha256(RECEIVER) == real_receiver_hash_before
    )
    integrity_problems = changed_readonly + changed_copies
    if not real_sources_ok:
        integrity_problems.append("真实 checker 或接收器磁盘源码在测试期间发生变化")
    if integrity_problems:
        suite.failures.append(
            {
                "case": "INTEGRITY_readonly_inputs",
                "kind": "integrity",
                "batch_dir": None,
                "exit_code": None,
                "expected_exit_code": None,
                "result": "FAIL",
                "problems": [f"只读输入或输入副本在测试前后哈希不一致：{p}" for p in integrity_problems],
            }
        )
        print("[FAIL] INTEGRITY_readonly_inputs 哈希不一致：")
        for path in integrity_problems:
            print(f"        - {path}")
    else:
        print("[PASS] INTEGRITY_readonly_inputs 只读输入、输入副本与磁盘源码哈希一致")

    summary = {
        "task": "TASK-003-R1",
        "out_dir": str(container),
        "receiver": {"path": str(RECEIVER), "sha256": sha256(RECEIVER)},
        "checker": {"path": str(CHECKER), "sha256": sha256(CHECKER)},
        "totals": {
            "cases": len(suite.results),
            "passed": sum(1 for item in suite.results if item["result"] == "PASS"),
            "failed": len(suite.failures),
            "entry_invocations": suite.calls,
            "cli_invocations": suite.cli_calls,
            "in_memory_simulations": suite.memory_calls,
        },
        "results": suite.results,
        "failures": suite.failures,
        "expected_negative_cases": suite.expected_negatives,
        "readonly_inputs_count": len(READ_ONLY_INPUTS),
        "readonly_inputs_unchanged": not integrity_problems,
        "readonly_inputs_changed": integrity_problems,
        "notes": [
            "参数拒绝、质量阻断、运行失败是预期负向案例，与脚本自身失败分开记录。",
            "故障只在内存中替换接收器模块函数或写在新测试副本上，未修改真实 checker、原输入或既有批次。",
            "每次调用（含内存模拟）单独保存 stdout／stderr，command_log.json 区分 cli 与 in_memory_simulation。",
        ],
    }
    (container / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (container / "command_log.json").write_text(
        json.dumps(suite.command_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print()
    print(
        f"用例总数 {summary['totals']['cases']}，通过 {summary['totals']['passed']}，"
        f"失败 {summary['totals']['failed']}"
    )
    print(
        f"入口调用 {summary['totals']['entry_invocations']} 次"
        f"（真实 CLI {summary['totals']['cli_invocations']} 次 + 内存模拟 "
        f"{summary['totals']['in_memory_simulations']} 次）"
    )
    print(f"预期负向案例 {len(suite.expected_negatives)} 个：{', '.join(item['case'] for item in suite.expected_negatives)}")
    print(f"只读输入前后哈希一致: {summary['readonly_inputs_unchanged']}（受保护 {summary['readonly_inputs_count']} 个）")
    print(f"汇总: {container / 'summary.json'}")
    if suite.failures:
        print("存在断言失败或完整性失败，返回非零退出码（不输出总体成功结论）。")
        return 1
    print("全部预期成立。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
