#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-003 开发态接收入口：单文件接收、原始快照、批次留痕与 Gate 1 候审材料。

本入口只做“接收与核验留痕”这一步：
  - 指定一份 .xlsx（不递归扫描目录），在 data/batches 下建立全新批次；
  - 逐字节保存原始快照（不用 openpyxl 重存），调用已验收的 scripts/check_demo_data.py 核验快照；
  - 保存版本、哈希、命令、退出码与日志，生成 batch_manifest.json 与 gate1_packet.md；
  - 不实现标准化、入库、R01—R04、AI 建议、正式契约或任何人工批准功能。

固定状态与退出码：
  DEV_GATE1_PACKET_READY  checker 退出 0、报告结构有效且一致性通过 → 本入口退出 0
  BLOCKED_QUALITY         checker 退出 1、报告结构有效且一致性通过 → 本入口退出 1
  FAILED_RUNTIME          路径／文件／执行／一致性／报告结构／材料写入问题 → 本入口退出 2

TASK-003-R1 起统一失败处理；R2 收口：
  - JSON 解析成功不等于结构有效：`null`、空对象、缺少必需内容一律 FAILED_RUNTIME；
  - execute_batch 与 finalize 内的读取、拼装、渲染、写入都不得抛出未捕获异常；
  - 清单原子提交（临时文件 + 替换），失败时改写为 FAILED_RUNTIME，不遗留可就绪的成功清单；
  - 最终清单在材料写入之后重建，对应最终现场；未知值记为 null，不用默认零或 None==None 冒充已验证事实。

注意：gate1_packet.md 只是**开发态候审材料**，不构成 Gate 1 批准，也不代表契约生效。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BATCHES_ROOT = (PROJECT_ROOT / "data" / "batches").resolve()
RECEIVER_PATH = Path(__file__).resolve()
CHECKER_PATH = PROJECT_ROOT / "scripts" / "check_demo_data.py"
SPEC_PATH = PROJECT_ROOT / "docs" / "SPEC_V1.md"
CONTRACT_PATH = PROJECT_ROOT / "docs" / "AUDIT_CONTRACT_DRAFT.md"

MANIFEST_VERSION = "TASK-003-R2-batch-manifest-1.2"
MODE = "DEVELOPMENT_ONLY"
CONTRACT_STATUS = "DRAFT_NOT_IN_FORCE"

STATUS_READY = "DEV_GATE1_PACKET_READY"
STATUS_BLOCKED = "BLOCKED_QUALITY"
STATUS_FAILED = "FAILED_RUNTIME"

PACKET_HEADER = "开发态候审材料，未批准，不代表可以进入标准化"

FIXED_SHEETS = ("suppliers", "payables", "payments", "allocations")
ROW_FIELDS = ("source_rows", "accepted_rows", "blocked_rows", "blank_rows")
AMOUNT_KEYS = ("payables_payable_amount", "payments_amount", "allocations_allocated_amount")
ISSUE_FIELDS = ("code", "sheet", "excel_row", "column", "value", "detail")

# SPEC_V1 四表字典的固定字段（共 22 个）：实际存在的固定表必须给出每个固定字段的映射键
FIXED_FIELDS = {
    "suppliers": ("supplier_id", "supplier_name"),
    "payables": ("ap_id", "ap_number", "supplier_id", "ap_date", "payable_amount", "currency"),
    "payments": (
        "payment_id",
        "transaction_type",
        "original_payment_id",
        "payee_supplier_id",
        "payment_date",
        "amount",
        "currency",
        "settlement_status",
        "bank_reference",
    ),
    "allocations": (
        "allocation_id",
        "payment_id",
        "ap_id",
        "allocated_amount",
        "original_allocation_id",
    ),
}

KNOWN_LIMITS = [
    "本批次为开发态接收，仅使用项目内合成数据与既有案例，不接收真实企业材料。",
    "来源描述按传入原字符串保存，是未经验证的声明，不构成主理人对范围或导出条件的确认。",
    "无法获知真实 ERP 导出时间，erp_export_at_utc 记为 null，不用接收时间冒充。",
    "预期公司、期间与截至日来自 docs/SPEC_V1.md 与任务卡设定，不能据四张表独立证明公司主体或全部业务历史完整性。",
    "原始快照逐字节保留原单元格值、类型与行号；本任务不另做转换后的数据表。",
    "本材料不构成 Gate 1 批准、不构成契约生效、不产生风险等级或任何审计结论。",
]

EXPECTED_SCOPE = {
    "company": "澄明商贸有限公司",
    "period_start": "2026-09-01",
    "period_end": "2026-09-30",
    "as_of_date": "2026-09-30",
    "currency": "CNY",
    "synthetic_declaration": "全部数据为合成数据，仅用于采购付款异常筛查与审计辅助的开发与验收演示。",
    "scope_source": "来自 docs/SPEC_V1.md 与 TASK-003_DRAFT.md 的任务设定与来源声明；"
    "不能据四表独立证明主体真实性或业务历史完整性。",
    "erp_export_at_utc": None,
}


# ---------------------------------------------------------------------------
# 可被验证替换的最小接缝：生产路径各自只有一种实现，不提供故障注入开关
# ---------------------------------------------------------------------------


def copy_snapshot_bytes(source: Path, target: Path) -> None:
    """逐字节复制原始输入。"""
    shutil.copyfile(source, target)


def copy_code_snapshot(source: Path, target: Path) -> None:
    """复制源码留档。"""
    shutil.copyfile(source, target)


def run_checker_subprocess(argv: list[str], stdout_handle, stderr_handle) -> int:
    """运行真实 checker CLI。"""
    return subprocess.run(argv, stdout=stdout_handle, stderr=stderr_handle).returncode


def write_text_artifact(path: Path, text: str) -> None:
    """写入文本产物（候审材料、日志）。"""
    path.write_text(text, encoding="utf-8")


def commit_manifest(path: Path, text: str) -> None:
    """原子提交批次清单：先写同目录临时文件，再替换正式文件。"""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def read_file_bytes(path: Path) -> bytes:
    """读取文件字节（哈希用）。单独成函数便于在内存中模拟“存在性已知、读取字节失败”。"""
    return path.read_bytes()


def safe_hash_file(path: Path) -> tuple[bool | None, str | None, str | None]:
    """读取文件哈希，返回 (是否存在, sha256 或 None, 读取错误或 None)；调用方负责兜住异常。

    存在性单独判定并保留：存在性确认为 true 后读取字节失败时仍返回 exists=True。
    """
    try:
        exists = path.exists()
    except OSError as exc:
        return None, None, f"存在性检查失败：{type(exc).__name__}: {exc}"
    if not exists:
        return False, None, None
    try:
        return True, hashlib.sha256(read_file_bytes(path)).hexdigest(), None
    except OSError as exc:
        return True, None, f"读取字节失败：{type(exc).__name__}: {exc}"


def hash_info(path: Path, relative: str | None = None) -> dict:
    """安全取得文件存在状态与哈希；读不到时保留 exists=true、sha256=null 并记录读取错误。"""
    info: dict = {}
    if relative is not None:
        info["path"] = relative
    try:
        exists, digest, error = safe_hash_file(path)
        info["exists"] = exists
        info["sha256"] = digest
        info["read_error"] = error
    except Exception as exc:  # noqa: BLE001 - 读取失败不能中断在生成失败清单
        info["exists"] = None
        info["sha256"] = None
        info["read_error"] = f"{type(exc).__name__}: {exc}"
    return info


def stability(before: str | None, after: str | None) -> bool | None:
    """两端都有有效哈希才能判断稳定；任一端未知即返回 None。"""
    if before is None or after is None:
        return None
    return before == after


# ---------------------------------------------------------------------------
# 报告结构校验：解析成功不等于结构有效
# ---------------------------------------------------------------------------


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_report(report) -> list[str]:
    """只核验入口要消费的报告内容是否存在且类型正确；缺什么报什么，不用默认值补。"""
    problems: list[str] = []
    if not isinstance(report, dict):
        return [f"报告顶层必须是对象，实际 {type(report).__name__}"]

    if report.get("result") not in ("pass", "issues_found"):
        problems.append(f"result 必须为 pass 或 issues_found，实际 {report.get('result')!r}")

    for key in ("workbook", "checker"):
        section = report.get(key)
        if not isinstance(section, dict):
            problems.append(f"{key} 必须是对象")
        elif not isinstance(section.get("sha256"), str) or not section["sha256"]:
            problems.append(f"{key}.sha256 必须是非空字符串")

    structure = report.get("structure")
    if not isinstance(structure, dict):
        problems.append("structure 必须是对象")
    else:
        sheets_found = structure.get("sheets_found")
        if not isinstance(sheets_found, list) or not all(isinstance(item, str) for item in sheets_found):
            problems.append("structure.sheets_found 必须是字符串数组")
            sheets_found = []
        mapping = structure.get("sheet_field_mapping")
        if not isinstance(mapping, dict):
            problems.append("structure.sheet_field_mapping 必须是对象")
        else:
            # 只对实际存在的固定表要求映射；缺失表不要求条目，也不能因此判成运行失败
            for sheet in FIXED_SHEETS:
                if sheet not in sheets_found:
                    continue
                fields = mapping.get(sheet)
                if not isinstance(fields, dict):
                    problems.append(f"structure.sheet_field_mapping.{sheet} 必须是对象（该表实际存在）")
                    continue
                if not fields:
                    problems.append(f"structure.sheet_field_mapping.{sheet} 不能为空对象（该表实际存在）")
                for name in FIXED_FIELDS[sheet]:
                    if name not in fields:
                        problems.append(
                            f"structure.sheet_field_mapping.{sheet} 缺少固定字段 {name}"
                        )
                        continue
                    index = fields[name]
                    if index is None:
                        continue
                    if not _is_int(index) or index < 1:
                        problems.append(
                            f"structure.sheet_field_mapping.{sheet}.{name} 必须是正整数或 null"
                        )

    row_accounting = report.get("row_accounting")
    if not isinstance(row_accounting, dict):
        problems.append("row_accounting 必须是对象")
    else:
        for sheet in FIXED_SHEETS:
            accounting = row_accounting.get(sheet)
            if not isinstance(accounting, dict):
                problems.append(f"row_accounting.{sheet} 必须存在且为对象")
                continue
            for field in ROW_FIELDS:
                if field not in accounting:
                    problems.append(f"row_accounting.{sheet} 缺少 {field}")
                    continue
                value = accounting.get(field)
                if not _is_int(value) or value < 0:
                    problems.append(f"row_accounting.{sheet}.{field} 必须是非负整数")

    issues = report.get("issues")
    if not isinstance(issues, list):
        problems.append("issues 必须是数组")
    else:
        for index, item in enumerate(issues):
            if not isinstance(item, dict):
                problems.append(f"issues[{index}] 必须是对象")
                continue
            for field in ISSUE_FIELDS:
                if field not in item:
                    problems.append(f"issues[{index}] 缺少字段 {field}")

    counts = report.get("issue_counts_by_code")
    if not isinstance(counts, dict):
        problems.append("issue_counts_by_code 必须是对象")
    else:
        for code, value in counts.items():
            if not _is_int(value):
                problems.append(f"issue_counts_by_code.{code} 必须是整数")

    amount_summary = report.get("amount_summary")
    if not isinstance(amount_summary, dict):
        problems.append("amount_summary 必须是对象")
    else:
        for field in ("known_valid_subtotals_cents", "complete_totals_cents"):
            section = amount_summary.get(field)
            if not isinstance(section, dict):
                problems.append(f"amount_summary.{field} 必须存在且为对象（不允许 null 或缺失）")
                continue
            for key in AMOUNT_KEYS:
                if key not in section:
                    problems.append(f"amount_summary.{field} 缺少 {key}")
                    continue
                value = section.get(key)
                if value is not None and not _is_int(value):
                    problems.append(f"amount_summary.{field}.{key} 必须是整数或 null")
        unusable = amount_summary.get("unusable_amount_cells")
        if not isinstance(unusable, dict):
            problems.append("amount_summary.unusable_amount_cells 必须存在且为对象")
        else:
            if not _is_int(unusable.get("total")):
                problems.append("amount_summary.unusable_amount_cells.total 必须是整数")
            if not isinstance(unusable.get("by_reason"), dict):
                problems.append("amount_summary.unusable_amount_cells.by_reason 必须是对象")
            if not isinstance(unusable.get("sources"), list):
                problems.append("amount_summary.unusable_amount_cells.sources 必须是数组")
        unmapped = amount_summary.get("unmapped_amount_columns")
        if unmapped is not None and not isinstance(unmapped, list):
            problems.append("amount_summary.unmapped_amount_columns 必须是数组")

    reconciliation = report.get("reconciliation")
    if not isinstance(reconciliation, dict):
        problems.append("reconciliation 必须是对象")
    else:
        if "status" not in reconciliation:
            problems.append("reconciliation 缺少 status")
        elif reconciliation.get("status") not in ("ASSESSED", "NOT_ASSESSED"):
            problems.append(
                f"reconciliation.status 必须为 ASSESSED 或 NOT_ASSESSED，实际 {reconciliation.get('status')!r}"
            )
        if "known_plus_missing_equals_master" not in reconciliation:
            problems.append("reconciliation 缺少 known_plus_missing_equals_master")
        else:
            comparison = reconciliation.get("known_plus_missing_equals_master")
            if comparison is not None and not isinstance(comparison, bool):
                problems.append("reconciliation.known_plus_missing_equals_master 必须是布尔或 null")
        if not isinstance(reconciliation.get("diagnostic_known_valid_subtotals_cents"), dict):
            problems.append("reconciliation.diagnostic_known_valid_subtotals_cents 必须是对象")

    return problems


# ---------------------------------------------------------------------------
# 批次状态
# ---------------------------------------------------------------------------


class BatchState:
    def __init__(self, out_dir: Path, workbook: Path, source_description: str, received_at: str):
        self.out_dir = out_dir
        self.workbook = workbook
        self.source_description = source_description
        self.received_at = received_at
        self.current_stage = "init"
        self.first_failure_stage: str | None = None
        self.failure_reasons: list[str] = []
        self.exceptions: list[dict] = []
        self.material_write_failures: list[dict] = []
        self.report = None
        self.report_validation = {
            "attempted": False,
            "valid": None,
            "problems": [],
            "report_readable": None,
        }
        self.report_result: str | None = None
        self.report_workbook_hash: str | None = None
        self.report_checker_hash: str | None = None
        self.report_matches_snapshot: bool | None = None
        self.report_matches_checker: bool | None = None
        self.checker_argv: list[str] | None = None
        self.checker_exit_code: int | None = None
        self.checker_attempted = False
        # 未尝试启动时确定“未启动”；尝试后无法判断的情况记 None，成功完成子进程调用才记 True
        self.checker_started: bool | None = False
        self.source_size: int | None = None
        self.source_info: dict = {}
        self.receiver_info: dict = {}
        self.checker_info: dict = {}
        self.hashes: dict = {}
        self.snapshot_written = False
        self.snapshot_trustworthy: bool | None = None
        self.code_snapshot_results: dict = {}
        self.artifact_infos: dict[str, dict] = {}
        self.logs_expected = False
        self.code_copies_expected = False

    # ---------- 路径 ----------
    @property
    def source_dir(self) -> Path:
        return self.out_dir / "source"

    @property
    def checks_dir(self) -> Path:
        return self.out_dir / "checks"

    @property
    def logs_dir(self) -> Path:
        return self.out_dir / "logs"

    @property
    def code_dir(self) -> Path:
        return self.out_dir / "code_snapshot"

    @property
    def snapshot_path(self) -> Path:
        return self.source_dir / "input.xlsx"

    @property
    def report_path(self) -> Path:
        return self.checks_dir / "quality_report.json"

    @property
    def stdout_log(self) -> Path:
        return self.logs_dir / "checker.stdout.txt"

    @property
    def stderr_log(self) -> Path:
        return self.logs_dir / "checker.stderr.txt"

    @property
    def manifest_path(self) -> Path:
        return self.out_dir / "batch_manifest.json"

    @property
    def packet_path(self) -> Path:
        return self.out_dir / "gate1_packet.md"

    # ---------- 失败记录 ----------
    def set_stage(self, stage: str) -> None:
        self.current_stage = stage

    def fail(self, stage: str, message: str) -> None:
        self.current_stage = stage
        if self.first_failure_stage is None:
            self.first_failure_stage = stage
        self.failure_reasons.append(f"[{stage}] {message}")

    def record_exception(self, stage: str, exc: BaseException) -> None:
        self.current_stage = stage
        if self.first_failure_stage is None:
            self.first_failure_stage = stage
        self.exceptions.append({"stage": stage, "type": type(exc).__name__, "message": str(exc)})
        self.failure_reasons.append(f"[{stage}] 运行错误：{type(exc).__name__}: {exc}")

    def record_material_write_failure(self, name: str, exc: BaseException | str) -> None:
        detail = str(exc) if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
        self.material_write_failures.append({"artifact": name, "error": detail})
        self.fail(self.current_stage, f"{name} 保存失败：{detail}")

    def decide_status(self) -> tuple[str, int]:
        if self.failure_reasons:
            return STATUS_FAILED, 2
        if self.checker_exit_code == 0:
            return STATUS_READY, 0
        if self.checker_exit_code == 1:
            return STATUS_BLOCKED, 1
        return STATUS_FAILED, 2


def require_hash(
    state: "BatchState",
    label: str,
    info: dict,
    stage: str,
    expected: str | None = None,
) -> str | None:
    """要求该项哈希可用且（如给出预期）一致；未知或读取失败必须判为运行失败。"""
    digest = info.get("sha256")
    if digest is None:
        reason = info.get("read_error") or "未取得有效哈希（文件可能已消失或不可读）"
        state.fail(stage, f"{label}的哈希未知或不可读：{reason}（exists={info.get('exists')}）")
        return None
    if expected is not None and digest != expected:
        state.fail(stage, f"{label}与预期不一致：actual={digest} expected={expected}")
    return digest


def resolve_out_dir(raw: str) -> Path | None:
    target = Path(raw).expanduser()
    target = target.resolve() if target.is_absolute() else (Path.cwd() / target).resolve()
    try:
        target.relative_to(BATCHES_ROOT)
    except ValueError:
        print(f"ERROR: 输出目录必须位于 {BATCHES_ROOT} 之内：{target}", file=sys.stderr)
        return None
    if target == BATCHES_ROOT:
        print("ERROR: 输出目录不能是 data/batches 本身", file=sys.stderr)
        return None
    if target.exists():
        print(f"ERROR: 输出目录已存在，不覆盖任何内容：{target}", file=sys.stderr)
        return None
    return target


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TASK-003 开发态单文件接收入口")
    parser.add_argument("--workbook", required=True, help="待接收的单个 .xlsx 文件（不递归扫描目录）")
    parser.add_argument("--out-dir", required=True, help="data/batches 内尚不存在的批次子目录")
    parser.add_argument("--source-description", required=True, help="来源描述，原样保存为声明")
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# 接收主流程（execute_batch 内任何异常都由 main 统一归为运行失败）
# ---------------------------------------------------------------------------


def execute_batch(state: BatchState) -> None:
    state.set_stage("hash_source_before")
    state.source_info = hash_info(state.workbook, "input.xlsx")
    state.receiver_info = hash_info(RECEIVER_PATH, "scripts/receive_demo_batch.py")
    state.checker_info = hash_info(CHECKER_PATH, "scripts/check_demo_data.py")
    state.hashes["source_before_copy"] = state.source_info.get("sha256")
    state.hashes["receiver_sha256_before_run"] = state.receiver_info.get("sha256")
    state.hashes["checker_sha256_before_run"] = state.checker_info.get("sha256")
    if state.source_info.get("sha256") is None:
        state.fail(
            "hash_source_before",
            "无法取得输入文件哈希，未继续复制与核验："
            f"{state.source_info.get('read_error') or '文件不可读或不存在'}",
        )
        return
    if state.checker_info.get("sha256") is None or state.receiver_info.get("sha256") is None:
        state.fail("hash_code_before", "无法取得入口或 checker 的源码哈希，未继续核验")
        return

    state.set_stage("read_source_size")
    try:
        state.source_size = state.workbook.stat().st_size
    except OSError as exc:
        state.source_size = None
        state.fail("read_source_size", f"无法读取输入文件大小：{type(exc).__name__}: {exc}")

    state.set_stage("create_dirs")
    for directory in (state.source_dir, state.checks_dir, state.logs_dir, state.code_dir):
        directory.mkdir(parents=True, exist_ok=True)

    state.set_stage("copy_snapshot")
    copy_snapshot_bytes(state.workbook, state.snapshot_path)
    state.snapshot_written = state.snapshot_path.exists()
    source_after_copy = hash_info(state.workbook)
    snapshot_after_copy = hash_info(state.snapshot_path)
    state.hashes["source_after_copy"] = source_after_copy.get("sha256")
    state.hashes["snapshot_after_copy"] = snapshot_after_copy.get("sha256")
    state.snapshot_trustworthy = (
        state.hashes["snapshot_after_copy"] is not None
        and state.hashes["snapshot_after_copy"] == state.hashes["source_before_copy"]
        and state.hashes["source_after_copy"] == state.hashes["source_before_copy"]
    )
    if not state.snapshot_trustworthy:
        state.fail(
            "verify_snapshot",
            "原始快照与源文件字节不一致或无法核对："
            f"source_before_copy={state.hashes['source_before_copy']} "
            f"snapshot_after_copy={state.hashes['snapshot_after_copy']}",
        )

    state.set_stage("copy_code_snapshot")
    state.code_copies_expected = True
    receiver_copy = state.code_dir / RECEIVER_PATH.name
    checker_copy = state.code_dir / CHECKER_PATH.name
    copy_code_snapshot(RECEIVER_PATH, receiver_copy)
    copy_code_snapshot(CHECKER_PATH, checker_copy)
    for label, target, expected in (
        ("receive_demo_batch.py", receiver_copy, state.hashes["receiver_sha256_before_run"]),
        ("check_demo_data.py", checker_copy, state.hashes["checker_sha256_before_run"]),
    ):
        info = hash_info(target)
        actual = info.get("sha256")
        matches = actual is not None and actual == expected
        state.code_snapshot_results[label] = {
            "exists": info.get("exists"),
            "sha256": actual,
            "expected_sha256": expected,
            "matches_source": matches,
            "read_error": info.get("read_error"),
        }
        if not info.get("exists"):
            state.fail("verify_code_snapshot", f"源码留档缺失：code_snapshot/{label}")
        elif not matches:
            state.fail(
                "verify_code_snapshot",
                f"源码留档与执行版本不一致或不可读：code_snapshot/{label} sha256={actual} expected={expected}",
            )

    stdout_log = state.stdout_log
    stderr_log = state.stderr_log
    state.logs_expected = True
    if not state.snapshot_trustworthy:
        state.set_stage("skip_checker")
        write_text_artifact(
            stdout_log,
            "核验未执行：原始快照与源文件字节不一致，按 FAILED_RUNTIME 处理，未生成质量报告。\n",
        )
        write_text_artifact(stderr_log, "")
    else:
        state.set_stage("run_checker")
        state.checker_argv = [
            sys.executable,
            str(CHECKER_PATH),
            "--workbook",
            str(state.snapshot_path),
            "--report",
            str(state.report_path),
        ]
        state.checker_attempted = True
        with stdout_log.open("w", encoding="utf-8") as out_handle, stderr_log.open(
            "w", encoding="utf-8"
        ) as err_handle:
            try:
                state.checker_exit_code = run_checker_subprocess(
                    state.checker_argv, out_handle, err_handle
                )
                state.checker_started = True
            except OSError as exc:
                state.checker_started = False
                state.record_exception("run_checker", exc)
            except Exception as exc:  # noqa: BLE001 - 无法确定是否真正启动
                state.checker_started = None
                state.record_exception("run_checker", exc)
        if state.checker_exit_code == 2:
            state.fail("run_checker", "checker 退出码 2：输入或运行问题，核验未完成")
        elif state.checker_exit_code is not None and state.checker_exit_code not in (0, 1):
            state.fail("run_checker", f"checker 退出码异常：{state.checker_exit_code}")

    state.set_stage("read_report")
    if state.report_path.exists():
        state.report_validation["report_readable"] = False
        raw_report = None
        parsed = False
        try:
            raw_report = json.loads(state.report_path.read_text(encoding="utf-8"))
            parsed = True
            state.report_validation["report_readable"] = True
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            state.record_exception("read_report", exc)
        if parsed:
            # JSON 解析成功即无条件做结构校验：null、空对象、缺内容都不算有效报告
            state.report_validation["attempted"] = True
            problems = validate_report(raw_report)
            state.report_validation["problems"] = problems
            state.report_validation["valid"] = not problems
            if problems:
                state.fail(
                    "validate_report",
                    "质量报告结构无效，不能作为可用质量结果：" + "；".join(problems[:5]),
                )
            else:
                state.report = raw_report
                state.report_result = raw_report.get("result")
                state.report_workbook_hash = (raw_report.get("workbook") or {}).get("sha256")
                state.report_checker_hash = (raw_report.get("checker") or {}).get("sha256")
                state.report_matches_snapshot = (
                    state.report_workbook_hash == state.hashes.get("snapshot_after_copy")
                )
                state.report_matches_checker = state.report_checker_hash == state.hashes.get(
                    "checker_sha256_before_run"
                )
                if not state.report_matches_snapshot:
                    state.fail(
                        "validate_report",
                        "报告核验的工作簿哈希与本批次快照不一致："
                        f"report={state.report_workbook_hash} snapshot={state.hashes.get('snapshot_after_copy')}",
                    )
                if not state.report_matches_checker:
                    state.fail(
                        "validate_report",
                        "报告记录的 checker 哈希与本次执行版本不一致："
                        f"report={state.report_checker_hash} expected={state.hashes.get('checker_sha256_before_run')}",
                    )
                if state.checker_exit_code == 0 and state.report_result != "pass":
                    state.fail(
                        "validate_report",
                        f"checker 退出 0 但报告 result={state.report_result!r}，退出码与内容矛盾",
                    )
                if state.checker_exit_code == 1 and state.report_result != "issues_found":
                    state.fail(
                        "validate_report",
                        f"checker 退出 1 但报告 result={state.report_result!r}，退出码与内容矛盾",
                    )
    elif state.checker_exit_code in (0, 1):
        state.report_validation["attempted"] = True
        state.report_validation["valid"] = False
        state.fail("read_report", "checker 退出码为 0 或 1 但未生成质量报告")

    state.set_stage("hash_source_after")
    source_after_check = hash_info(state.workbook)
    snapshot_after_check = hash_info(state.snapshot_path)
    receiver_at_end = hash_info(RECEIVER_PATH)
    checker_at_end = hash_info(CHECKER_PATH)
    state.hashes["source_after_check"] = source_after_check.get("sha256")
    state.hashes["snapshot_after_check"] = snapshot_after_check.get("sha256")
    state.hashes["receiver_sha256_at_end"] = receiver_at_end.get("sha256")
    state.hashes["checker_sha256_at_end"] = checker_at_end.get("sha256")

    # 结束阶段这四项哈希都是成功条件：未知（null）同样必须判为运行失败，不能跳过比较。
    # 该检查对 checker 退出 1 的批次同样生效：质量问题之外出现一致性读取错误即升级为运行失败。
    require_hash(
        state,
        "原输入（核验结束）",
        source_after_check,
        "verify_source",
        expected=state.hashes["source_before_copy"],
    )
    if state.snapshot_written:
        require_hash(
            state,
            "原始快照（核验结束）",
            snapshot_after_check,
            "verify_snapshot",
            expected=state.hashes.get("snapshot_after_copy"),
        )
    require_hash(
        state,
        "接收入口源码（核验结束）",
        receiver_at_end,
        "verify_code",
        expected=state.hashes["receiver_sha256_before_run"],
    )
    require_hash(
        state,
        "checker 源码（核验结束）",
        checker_at_end,
        "verify_code",
        expected=state.hashes["checker_sha256_before_run"],
    )


# ---------------------------------------------------------------------------
# 清单拼装与候审材料
# ---------------------------------------------------------------------------


def _info(state: "BatchState", name: str, relative: str) -> dict:
    """取已采集的产物信息；未采集时存在状态为 null，不用默认值冒充已验证事实。"""
    info = state.artifact_infos.get(name)
    if info is None:
        return {"path": relative, "exists": None, "sha256": None, "read_error": "尚未采集该产物信息"}
    return info


def build_manifest(state: BatchState, status: str, exit_code: int) -> dict:
    hashes = state.hashes
    return {
        "manifest_version": MANIFEST_VERSION,
        "batch_id": state.out_dir.name,
        "received_at_utc": state.received_at,
        "mode": MODE,
        "batch_status": status,
        "receive_exit_code": exit_code,
        "failure_reasons": list(state.failure_reasons),
        "failure": {
            "stage": state.first_failure_stage,
            "current_stage": state.current_stage,
            "exceptions": list(state.exceptions),
            "material_write_failures": list(state.material_write_failures),
            "scene_path": str(state.out_dir),
            "note": "批次已创建后发生运行错误时保留现场：不删除、不覆盖、不自动换目录重跑。"
            "未知值记为 null，未启动 checker 时不虚构命令、退出码或质量报告。",
        },
        "source": {
            "original_path": str(state.workbook),
            "file_name": state.workbook.name,
            "size_bytes": state.source_size,
            "size_note": "无法取得真实大小时为 null，不用 0 代替未知。",
            "source_description": state.source_description,
            "source_description_is_verified_fact": False,
            "source_description_note": "按传入原字符串保存（含首尾空格与换行）；仅用 strip 判断是否全为空白。",
            "erp_export_at_utc": None,
            "erp_export_at_note": "无法获知真实 ERP 导出时间，未使用接收时间冒充导出时间",
        },
        "expected_scope": EXPECTED_SCOPE,
        "hashes": {
            "source_before_copy": hashes.get("source_before_copy"),
            "source_after_copy": hashes.get("source_after_copy"),
            "source_after_check": hashes.get("source_after_check"),
            "snapshot_after_copy": hashes.get("snapshot_after_copy"),
            "snapshot_after_check": hashes.get("snapshot_after_check"),
            "snapshot_matches_source": state.snapshot_trustworthy,
            "snapshot_written": state.snapshot_written,
            "snapshot_note": "快照不可信或写入未完成时，不能当作完整快照使用；null 表示未知。",
            "source_reading": state.source_info,
            "receive_script": {
                "path": "scripts/receive_demo_batch.py",
                "sha256_before_run": hashes.get("receiver_sha256_before_run"),
                "sha256_at_end": hashes.get("receiver_sha256_at_end"),
                "stable_during_run": stability(
                    hashes.get("receiver_sha256_before_run"), hashes.get("receiver_sha256_at_end")
                ),
            },
            "checker": {
                "path": "scripts/check_demo_data.py",
                "sha256_before_run": hashes.get("checker_sha256_before_run"),
                "sha256_at_end": hashes.get("checker_sha256_at_end"),
                "stable_during_run": stability(
                    hashes.get("checker_sha256_before_run"), hashes.get("checker_sha256_at_end")
                ),
            },
            "spec": _info(state, "spec", "docs/SPEC_V1.md"),
            "contract_draft": _info(state, "contract", "docs/AUDIT_CONTRACT_DRAFT.md"),
        },
        "checker_invocation": {
            "argv": state.checker_argv,
            "attempted": state.checker_attempted,
            "started": state.checker_started,
            "exit_code": state.checker_exit_code,
            "report": _info(state, "report", "checks/quality_report.json"),
            "stdout_log": _info(state, "stdout_log", "logs/checker.stdout.txt"),
            "stderr_log": _info(state, "stderr_log", "logs/checker.stderr.txt"),
            "report_result": state.report_result,
            "report_workbook_sha256": state.report_workbook_hash,
            "report_checker_sha256": state.report_checker_hash,
            "report_matches_snapshot": state.report_matches_snapshot,
            "report_matches_checker": state.report_matches_checker,
        },
        "report_validation": state.report_validation,
        "code_snapshot": {
            label: {"path": f"code_snapshot/{label}", **result}
            for label, result in state.code_snapshot_results.items()
        },
        "contract_status": CONTRACT_STATUS,
        "gate1_approval": None,
        "gate2_approval": None,
        "next_step_allowed": False,
        "gate1_packet": _info(state, "packet", "gate1_packet.md"),
        "reuse_of_prior_artifacts": {
            "checker": "复用已验收的 scripts/check_demo_data.py CLI，未复制其校验逻辑，未修改该文件",
            "generator_imported": False,
            "answer_book_read": False,
            "old_checks_or_evaluation_used_as_result": False,
        },
        "known_limits": KNOWN_LIMITS,
    }


def display_escape(value: str) -> str:
    """仅用于 Markdown 展示；清单里始终保存原字符串。"""
    return (
        value.replace("|", "\\|")
        .replace("\r\n", "<br>")
        .replace("\n", "<br>")
        .replace("\r", "<br>")
    )


def _fmt(value) -> str:
    if value is None:
        return "null（不可得，不得填零）"
    return str(value)


def render_gate1_packet(manifest: dict, report: dict | None) -> str:
    lines: list[str] = []
    lines.append("# Gate 1 候审材料（开发态）")
    lines.append("")
    lines.append(f"> **{PACKET_HEADER}**")
    lines.append(">")
    lines.append("> 本材料不由 AI 批准、不含风险等级或审计结论，也不构成主理人对范围或质量的确认。")
    lines.append("")

    lines.append("## 1. 批次、来源与已知限制")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("| --- | --- |")
    lines.append(f"| 批次 ID | `{manifest['batch_id']}` |")
    lines.append(f"| 接收时间（UTC） | {manifest['received_at_utc']} |")
    lines.append(f"| 运行模式 | `{manifest['mode']}` |")
    lines.append(f"| 批次状态 | `{manifest['batch_status']}` |")
    lines.append(f"| 原输入 | `{manifest['source']['original_path']}` |")
    lines.append(
        f"| 文件名／大小 | {manifest['source']['file_name']}／{_fmt(manifest['source']['size_bytes'])} 字节 |"
    )
    lines.append(
        f"| 来源描述（声明，未验证；展示已转义） | {display_escape(manifest['source']['source_description'])} |"
    )
    lines.append(f"| ERP 导出时间 | {_fmt(manifest['source']['erp_export_at_utc'])} |")
    lines.append(f"| 原始快照 | `source/input.xlsx`，SHA-256 {_fmt(manifest['hashes']['snapshot_after_copy'])} |")
    lines.append(f"| 快照已写入 | {manifest['hashes']['snapshot_written']} |")
    lines.append(f"| 快照与源字节一致 | {_fmt(manifest['hashes']['snapshot_matches_source'])} |")
    scope = manifest["expected_scope"]
    lines.append(
        f"| 预期公司与期间 | {scope['company']}／{scope['period_start']} 至 {scope['period_end']}"
        f"（截至日 {scope['as_of_date']}，币种 {scope['currency']}） |"
    )
    lines.append(f"| 合成声明 | {scope['synthetic_declaration']} |")
    lines.append(f"| 范围依据 | {scope['scope_source']} |")
    lines.append("")
    lines.append("已知限制：")
    lines.append("")
    for limit in manifest["known_limits"]:
        lines.append(f"- {limit}")
    lines.append("")
    if manifest["failure_reasons"]:
        lines.append("失败原因：")
        lines.append("")
        for reason in manifest["failure_reasons"]:
            lines.append(f"- {reason}")
        lines.append("")
    if manifest["failure"]["material_write_failures"]:
        lines.append("未能保存的材料：")
        lines.append("")
        for item in manifest["failure"]["material_write_failures"]:
            lines.append(f"- {item['artifact']}：{item['error']}")
        lines.append("")
    lines.append(
        f"失败阶段：`{_fmt(manifest['failure']['stage'])}`；现场目录：`{manifest['failure']['scene_path']}`"
        "（已创建批次后不删除、不覆盖、不换目录重跑）。"
    )
    lines.append("")

    lines.append("## 2. 工作表、字段映射与行数")
    lines.append("")
    if report is None:
        lines.append("**核验未完成**：本批次没有可用的质量报告，工作表结构、字段映射与行数均为未知，不填零。")
        lines.append("")
    else:
        structure = report["structure"]
        lines.append(f"实际工作表：{', '.join(str(item) for item in structure.get('sheets_found', []))}")
        lines.append("")
        lines.append("| 工作表 | 字段映射（列号或 null） |")
        lines.append("| --- | --- |")
        for sheet, fields in structure.get("sheet_field_mapping", {}).items():
            rendered = ", ".join(
                f"{name}={'null' if index is None else index}" for name, index in fields.items()
            )
            lines.append(f"| {sheet} | {rendered} |")
        lines.append("")
        lines.append("| 工作表 | 来源行数 | 接受行数 | 隔离行数 | 空白行数 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for sheet, accounting in report.get("row_accounting", {}).items():
            lines.append(
                f"| {sheet} | {accounting.get('source_rows')} | {accounting.get('accepted_rows')} | "
                f"{accounting.get('blocked_rows')} | {accounting.get('blank_rows')} |"
            )
        lines.append("")
        lines.append("以上数量引用本批次 `checks/quality_report.json`，未编造缺失值。")
        lines.append("")

    lines.append("## 3. 数据质量结果")
    lines.append("")
    if report is None:
        lines.append("**核验未完成**：无可用质量报告，问题数与问题清单未知，不填零，也不生成零问题的伪报告。")
        lines.append("")
        lines.append(f"- checker 是否尝试启动：{manifest['checker_invocation']['attempted']}")
        lines.append(f"- checker 是否已启动：{_fmt(manifest['checker_invocation']['started'])}")
        lines.append(f"- checker 退出码：{_fmt(manifest['checker_invocation']['exit_code'])}")
        lines.append(f"- 报告校验：{json.dumps(manifest['report_validation'], ensure_ascii=False)}")
        lines.append(
            f"- stdout 日志：`logs/checker.stdout.txt`（存在：{manifest['checker_invocation']['stdout_log']['exists']}）"
        )
        lines.append(
            f"- stderr 日志：`logs/checker.stderr.txt`（存在：{manifest['checker_invocation']['stderr_log']['exists']}）"
        )
        lines.append("")
    else:
        lines.append(f"- 质量检查结果：`{report.get('result')}`")
        lines.append(f"- 问题总数：{len(report.get('issues', []))}")
        lines.append(f"- 按代码计数：{json.dumps(report.get('issue_counts_by_code', {}), ensure_ascii=False)}")
        lines.append("")
        issues = report.get("issues", [])
        if issues:
            lines.append("主要问题（带来源定位，最多列 20 条）：")
            lines.append("")
            lines.append("| # | 代码 | 工作表 | 行 | 列 | 原值 | 说明 |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")
            for index, item in enumerate(issues[:20], start=1):
                lines.append(
                    f"| {index} | {item.get('code')} | {item.get('sheet')} | {item.get('excel_row')} | "
                    f"{item.get('column')} | {item.get('value')} | {display_escape(str(item.get('detail')))} |"
                )
            if len(issues) > 20:
                lines.append(f"| … | 其余 {len(issues) - 20} 条见完整报告 | | | | | |")
            lines.append("")
        else:
            lines.append("本批次报告未记录数据质量或范围问题。")
            lines.append("")
        lines.append(
            f"- 完整报告：`checks/quality_report.json`（SHA-256 "
            f"{_fmt(manifest['checker_invocation']['report']['sha256'])}）"
        )
        lines.append("- 核验器 stdout／stderr：`logs/checker.stdout.txt`、`logs/checker.stderr.txt`")
        lines.append("")

    lines.append("## 4. 金额与勾稽（来自本批次报告）")
    lines.append("")
    if report is None:
        lines.append("**核验未完成**：金额小计、完整金额与勾稽状态均为未知，不填零，也不宣称勾稽通过。")
        lines.append("")
    else:
        amount_summary = report["amount_summary"]
        reconciliation = report["reconciliation"]
        lines.append("| 项目 | 值 |")
        lines.append("| --- | --- |")
        for label, value in amount_summary.get("known_valid_subtotals_cents", {}).items():
            lines.append(f"| 已知有效小计（{label}，整数分） | {_fmt(value)} |")
        for label, value in amount_summary.get("complete_totals_cents", {}).items():
            lines.append(f"| 完整总额（{label}，整数分） | {_fmt(value)} |")
        unusable = amount_summary.get("unusable_amount_cells", {})
        lines.append(f"| 不可用金额单元格数 | {_fmt(unusable.get('total'))} |")
        lines.append(f"| 不可用原因计数 | {json.dumps(unusable.get('by_reason', {}), ensure_ascii=False)} |")
        lines.append(f"| 勾稽状态 | `{reconciliation.get('status')}` |")
        lines.append(
            f"| 已知＋缺失＝主表净额 | {_fmt(reconciliation.get('known_plus_missing_equals_master'))} |"
        )
        lines.append("")
        lines.append("说明：主表与分摊是两种观察粒度，金额不相加；null 表示不可得，不得按零补齐。")
        lines.append("")

    lines.append("## 5. 下一步（本卡未执行）")
    lines.append("")
    lines.append("- 拟进行的下一阶段是**标准化与入库**，本卡不执行，也没有为此准备数据表或数据库。")
    lines.append(f"- 契约状态：`{manifest['contract_status']}`（正式契约尚未建立）。")
    lines.append(
        f"- Gate 1 批准：{_fmt(manifest['gate1_approval'])}；Gate 2 批准：{_fmt(manifest['gate2_approval'])}。"
    )
    lines.append(f"- 是否允许进入下一步：`{manifest['next_step_allowed']}`。")
    lines.append("- 本材料不含风险等级、AI 审计结论或规则命中，也不含任何批准入口或自动继续命令。")
    lines.append("- 批准动作只能由主理人在后续正式流程中执行；本材料不是批准记录。")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_packet_failure_notice(state: BatchState, error: str) -> str:
    return (
        "# Gate 1 候审材料（开发态）\n\n"
        f"> **{PACKET_HEADER}**\n\n"
        "**核验未完成**：本批次在生成候审材料时发生运行错误，材料内容不可用。\n\n"
        f"- 批次：`{state.out_dir.name}`\n"
        f"- 失败阶段：`{state.first_failure_stage}`\n"
        f"- 错误：{error}\n"
        f"- 现场目录：`{state.out_dir}`（保留现场，不删除、不覆盖、不换目录重跑）\n"
        "- 数量、金额与问题清单均为未知，不填零。\n"
        "- 本材料不含任何批准入口或自动继续命令；批准动作只能由主理人在后续正式流程中执行。\n"
    )


# ---------------------------------------------------------------------------
# 收尾：渲染、写入、按最终现场重建并提交清单
# ---------------------------------------------------------------------------


def _require_artifact(state: BatchState, info: dict, relative: str, required: bool) -> None:
    """要求的产物必须存在且可读；缺失或读不到哈希都算运行失败，未知不当作已满足。"""
    if not required:
        return
    if info.get("exists") is not True:
        state.fail(
            "verify_artifacts",
            f"要求的产物不存在或存在状态未知：{relative}（exists={info.get('exists')}）",
        )
    elif info.get("sha256") is None:
        state.fail(
            "verify_artifacts",
            f"产物存在但无法读取哈希：{relative}（{info.get('read_error')}）",
        )


def gather_static_infos(state: BatchState) -> None:
    """采集不依赖本次写入的产物信息：质量报告、规格、契约草案。"""
    state.set_stage("gather_static_infos")
    state.artifact_infos["report"] = hash_info(state.report_path, "checks/quality_report.json")
    _require_artifact(
        state,
        state.artifact_infos["report"],
        "checks/quality_report.json",
        required=state.checker_exit_code in (0, 1),
    )
    state.artifact_infos["spec"] = hash_info(SPEC_PATH, "docs/SPEC_V1.md")
    _require_artifact(state, state.artifact_infos["spec"], "docs/SPEC_V1.md", required=True)
    state.artifact_infos["contract"] = hash_info(CONTRACT_PATH, "docs/AUDIT_CONTRACT_DRAFT.md")
    _require_artifact(
        state, state.artifact_infos["contract"], "docs/AUDIT_CONTRACT_DRAFT.md", required=True
    )


def gather_final_infos(state: BatchState) -> None:
    """采集最终现场信息：日志、快照、两份代码副本、候审材料本身。"""
    state.set_stage("gather_final_infos")
    for name, path, relative, required in (
        ("stdout_log", state.stdout_log, "logs/checker.stdout.txt", state.logs_expected),
        ("stderr_log", state.stderr_log, "logs/checker.stderr.txt", state.logs_expected),
        ("snapshot", state.snapshot_path, "source/input.xlsx", state.snapshot_written),
        (
            "receiver_copy",
            state.code_dir / RECEIVER_PATH.name,
            "code_snapshot/receive_demo_batch.py",
            state.code_copies_expected,
        ),
        (
            "checker_copy",
            state.code_dir / CHECKER_PATH.name,
            "code_snapshot/check_demo_data.py",
            state.code_copies_expected,
        ),
        ("packet", state.packet_path, "gate1_packet.md", True),
    ):
        info = hash_info(path, relative)
        state.artifact_infos[name] = info
        _require_artifact(state, info, relative, required=required)


def write_packet(state: BatchState, status: str, exit_code: int) -> bool:
    """渲染并写入候审材料；渲染或写入失败都记录为运行失败。"""
    state.set_stage("render_packet")
    try:
        text = render_gate1_packet(build_manifest(state, status, exit_code), state.report)
    except Exception as exc:  # noqa: BLE001
        state.record_exception("render_packet", exc)
        text = render_packet_failure_notice(state, f"{type(exc).__name__}: {exc}")
    state.set_stage("write_packet")
    try:
        write_text_artifact(state.packet_path, text)
        return True
    except Exception as exc:  # noqa: BLE001
        state.record_material_write_failure("gate1_packet.md", exc)
        try:
            write_text_artifact(
                state.packet_path, render_packet_failure_notice(state, f"{type(exc).__name__}: {exc}")
            )
        except Exception as retry_exc:  # noqa: BLE001
            state.record_material_write_failure("gate1_packet.md（重试）", retry_exc)
        return False


def finalize(state: BatchState) -> int:
    # 1. 先采集静态产物信息（读取失败即运行失败，但不中断留痕）
    gather_static_infos(state)
    status, exit_code = state.decide_status()

    # 2. 写候审材料，再按最终现场采集全部产物信息
    packet_written = write_packet(state, status, exit_code)
    gather_final_infos(state)
    final_status, final_exit = state.decide_status()

    # 3. 状态变化或材料写入失败时，用最终状态重写材料，避免材料残留成功状态
    if (final_status, final_exit) != (status, exit_code) or not packet_written:
        write_packet(state, final_status, final_exit)
        state.artifact_infos["packet"] = hash_info(state.packet_path, "gate1_packet.md")
        final_status, final_exit = state.decide_status()

    # 4. 原子提交最终清单；提交失败时同步材料为失败态并改写清单后重试
    state.set_stage("write_manifest")
    manifest = build_manifest(state, final_status, final_exit)
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    try:
        commit_manifest(state.manifest_path, text)
    except Exception as exc:  # noqa: BLE001
        state.record_material_write_failure("batch_manifest.json", exc)
        state.set_stage("write_manifest_retry")
        write_packet(state, STATUS_FAILED, 2)
        state.artifact_infos["packet"] = hash_info(state.packet_path, "gate1_packet.md")
        retry_manifest = build_manifest(state, STATUS_FAILED, 2)
        retry_text = json.dumps(retry_manifest, ensure_ascii=False, indent=2) + "\n"
        try:
            commit_manifest(state.manifest_path, retry_text)
        except Exception as retry_exc:  # noqa: BLE001
            state.record_material_write_failure("batch_manifest.json（重试）", retry_exc)
            print(f"ERROR: 批次清单保存失败：{state.manifest_path}", file=sys.stderr)
            print("ERROR: 无法保存的文件：batch_manifest.json", file=sys.stderr)
            print(f"ERROR: 现场目录：{state.out_dir}", file=sys.stderr)
            for reason in state.failure_reasons:
                print(f"ERROR: {reason}", file=sys.stderr)
            print(
                "ERROR: 请保留现场并报告主理人；此次运行按 FAILED_RUNTIME 处理（退出 2）。",
                file=sys.stderr,
            )
            return 2
        manifest = retry_manifest

    print(f"批次目录: {state.out_dir}")
    print(f"批次状态: {manifest['batch_status']}")
    print(
        f"checker 尝试启动: {state.checker_attempted}；已启动: {state.checker_started}；"
        f"退出码: {state.checker_exit_code}"
    )
    print(f"接收入口退出码: {manifest['receive_exit_code']}")
    for reason in state.failure_reasons:
        print(f"  失败原因: {reason}")
    for item in state.material_write_failures:
        print(f"  材料保存失败: {item['artifact']} - {item['error']}")
    print(f"批次清单: {state.manifest_path}")
    print(f"Gate 1 候审材料: {state.packet_path}（存在: {manifest['gate1_packet']['exists']}）")
    print(f"提示: {PACKET_HEADER}")
    return manifest["receive_exit_code"]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    workbook = Path(args.workbook).expanduser()
    workbook = workbook.resolve() if workbook.is_absolute() else (Path.cwd() / workbook).resolve()
    if workbook.suffix.lower() != ".xlsx":
        print(f"ERROR: --workbook 必须是 .xlsx 文件：{workbook}", file=sys.stderr)
        return 2
    if not workbook.is_file():
        print(f"ERROR: 输入文件不存在或不是文件：{workbook}", file=sys.stderr)
        return 2
    # 仅用 strip 判断是否全为空白；保存的仍是传入原字符串
    source_description = args.source_description
    if not source_description.strip():
        print("ERROR: --source-description 不能为空或全为空白", file=sys.stderr)
        return 2
    out_dir = resolve_out_dir(args.out_dir)
    if out_dir is None:
        return 2
    for required in (CHECKER_PATH, SPEC_PATH, CONTRACT_PATH):
        if not required.is_file():
            print(f"ERROR: 缺少必需依赖文件：{required}", file=sys.stderr)
            return 2

    received_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        out_dir.mkdir(parents=True)
    except OSError as exc:
        print(f"ERROR: 无法创建批次目录：{out_dir}（{type(exc).__name__}: {exc}）", file=sys.stderr)
        return 2

    state = BatchState(out_dir, workbook, source_description, received_at)
    try:
        execute_batch(state)
    except Exception as exc:  # noqa: BLE001 - 运行／文件错误统一归为 FAILED_RUNTIME
        state.record_exception(state.current_stage, exc)
    try:
        return finalize(state)
    except Exception as exc:  # noqa: BLE001 - finalize 自身也不得抛出未捕获异常
        state.record_exception("finalize", exc)
        try:
            fallback = build_manifest(state, STATUS_FAILED, 2)
            commit_manifest(
                state.manifest_path, json.dumps(fallback, ensure_ascii=False, indent=2) + "\n"
            )
        except Exception as retry_exc:  # noqa: BLE001
            print(f"ERROR: 收尾阶段失败且无法保存失败清单：{type(retry_exc).__name__}: {retry_exc}", file=sys.stderr)
            print(f"ERROR: 现场目录：{state.out_dir}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
