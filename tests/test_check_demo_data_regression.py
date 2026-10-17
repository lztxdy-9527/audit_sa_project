#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-002-R1 回归验证：数据质量校验器返修后行为验证。

用法：

    & 'D:\\harness work\\audit_sa_project\\.venv\\Scripts\\python.exe' `
      'D:\\harness work\\audit_sa_project\\tests\\test_check_demo_data_regression.py' `
      --out-dir 'D:\\harness work\\audit_sa_project\\data\\generated\\task002_r1_01\\regressions'

本文件只做验证，不修改任何既有产物：
  - 通过命令行调用真实的 scripts/check_demo_data.py，读取其落盘报告，断言退出码与关键内容；
  - 每个负向案例从原 fixtures/C01.xlsx 的新副本开始，只改少量字段；
  - 预期值来自 docs/SPEC_V1.md 与 docs/tasks/TASK-002-R1.md，不读取答案册、不导入生成器，
    也不依据当前校验器的输出反向生成预期；
  - 输出目录必须位于 data/generated 内且尚不存在，拒绝覆盖旧证据。

退出码：0 全部通过；1 存在失败断言；2 参数、路径或环境问题。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_ROOT = (PROJECT_ROOT / "data" / "generated").resolve()
CHECKER = PROJECT_ROOT / "scripts" / "check_demo_data.py"
BASELINE_DIR = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a"
C01_SOURCE = BASELINE_DIR / "fixtures" / "C01.xlsx"
C07B_SOURCE = BASELINE_DIR / "fixtures" / "C07b.xlsx"
C14A_SOURCE = BASELINE_DIR / "fixtures" / "C14a.xlsx"
MAIN_INPUT = BASELINE_DIR / "input" / "erp_export.xlsx"

SHEET_COLUMNS = {
    "suppliers": ["supplier_id", "supplier_name"],
    "payables": ["ap_id", "ap_number", "supplier_id", "ap_date", "payable_amount", "currency"],
    "payments": [
        "payment_id",
        "transaction_type",
        "original_payment_id",
        "payee_supplier_id",
        "payment_date",
        "amount",
        "currency",
        "settlement_status",
        "bank_reference",
    ],
    "allocations": [
        "allocation_id",
        "payment_id",
        "ap_id",
        "allocated_amount",
        "original_allocation_id",
    ],
}

# 原 22 份 fixture 的预期（依据 SPEC_V1.md 第 6 节，独立于当前校验器输出）
FIXTURE_EXPECTED: dict[str, tuple[int, list[str]]] = {
    "C01": (0, []),
    "C02": (0, []),
    "C03": (0, []),
    "C04": (0, []),
    "C05": (0, []),
    "C06": (0, []),
    "C07": (0, []),
    "C08": (0, []),
    "C09": (0, []),
    "C10": (0, []),
    "C11": (1, ["SETTLED_BANK_REFERENCE_DUPLICATE"]),
    "C12": (1, ["ALLOCATION_SUM_MISMATCH"]),
    "C13": (1, ["REFUND_EXCEEDS_ORIGINAL"]),
    "C06b": (0, []),
    "C07b": (0, []),
    "C09b": (0, []),
    "C10b": (0, []),
    "C14a": (1, ["REQUIRED_COLUMN_MISSING"]),
    "C14b": (1, ["PRIMARY_KEY_DUPLICATE"]),
    "C14c": (1, ["AMOUNT_INVALID"]),
    "C14d": (1, ["DATE_INVALID"]),
    "C14e": (1, ["AMOUNT_SCALE_INVALID"]),
}

# 只读输入：整轮回归前后必须逐字节不变
PROTECTED_INPUTS = [
    MAIN_INPUT,
    *sorted((BASELINE_DIR / "fixtures").glob("*.xlsx")),
    PROJECT_ROOT / "docs" / "SPEC_V1.md",
    PROJECT_ROOT / "docs" / "tasks" / "TASK-002-R1.md",
    PROJECT_ROOT / "docs" / "reviews" / "REVIEW_TASK_002.md",
    PROJECT_ROOT / "docs" / "EXEC_REPORT_002.md",
    PROJECT_ROOT / "scripts" / "make_demo_data.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def column_letter(sheet: str, field: str) -> str:
    return get_column_letter(SHEET_COLUMNS[sheet].index(field) + 1)


def fail(message: str) -> "None":
    print(f"RUNTIME_ERROR: {message}", file=sys.stderr)
    sys.exit(2)


class Regression:
    def __init__(self, out_dir: Path) -> None:
        self.out = out_dir
        self.inputs = out_dir / "inputs"
        self.reports = out_dir / "reports"
        self.logs = out_dir / "logs"
        self.baseline_reports = out_dir / "baseline_reports"
        for directory in (self.inputs, self.reports, self.logs, self.baseline_reports):
            directory.mkdir(parents=True, exist_ok=True)
        self.results: list[dict] = []
        self.failures: list[dict] = []
        self.command_log: list[dict] = []
        self.calls = 0

    def observe_types(self, workbook_path: Path, targets: list[tuple[str, str, int]]) -> list[dict]:
        """重新读取落盘副本，返回目标单元格的实际值与单元格类型（用于区分 e 与 s）。"""
        workbook = load_workbook(workbook_path)
        observations = []
        for sheet, field, row in targets:
            reference = f"{column_letter(sheet, field)}{row}"
            cell = workbook[sheet][reference]
            observations.append(
                {
                    "sheet": sheet,
                    "field": field,
                    "cell": reference,
                    "value": None if cell.value is None else str(cell.value),
                    "data_type": cell.data_type,
                }
            )
        workbook.close()
        return observations

    # ---------- 造副本 ----------
    def make_case(
        self,
        name: str,
        source: Path,
        edits: list[tuple[str, str, object]] | None = None,
        header_edits: list[tuple[str, str, object]] | None = None,
    ) -> Path:
        """复制源工作簿并按 (表, 字段, 值) 修改；edits 改第 2 行数据，header_edits 改第 1 行表头。"""
        target = self.inputs / f"{name}.xlsx"
        shutil.copyfile(source, target)
        workbook = load_workbook(target)
        for sheet, field, value in edits or []:
            workbook[sheet][f"{column_letter(sheet, field)}2"] = value
        for sheet, field, value in header_edits or []:
            workbook[sheet][f"{column_letter(sheet, field)}1"] = value
        workbook.save(target)
        return target

    def copy_case(self, name: str, source: Path) -> Path:
        target = self.inputs / f"{name}.xlsx"
        shutil.copyfile(source, target)
        return target

    def make_forced_text_case(
        self, name: str, source: Path, edits: list[tuple[str, str, object]]
    ) -> Path:
        """写入字符串后强制 data_type='s'，用于构造“真文本但内容像错误码”的正向控制。"""
        target = self.inputs / f"{name}.xlsx"
        shutil.copyfile(source, target)
        workbook = load_workbook(target)
        for sheet, field, value in edits:
            cell = workbook[sheet][f"{column_letter(sheet, field)}2"]
            cell.value = value
            cell.data_type = "s"
        workbook.save(target)
        return target

    # ---------- 运行真实校验器 ----------
    def run_checker(
        self,
        case: str,
        workbook: Path,
        report_name: str | None = None,
        baseline: bool = False,
    ) -> tuple[int, dict | None, Path, Path]:
        directory = self.baseline_reports if baseline else self.reports
        report = directory / f"{report_name or case}.json"
        self.calls += 1
        # 每次调用使用唯一日志文件名，任何一次输出都不会被后续调用覆盖
        log = self.logs / f"{self.calls:02d}_{report_name or case}.stdout.txt"
        command = [
            sys.executable,
            str(CHECKER),
            "--workbook",
            str(workbook),
            "--report",
            str(report),
        ]
        with log.open("w", encoding="utf-8") as handle:
            completed = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT)
        payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else None
        self.command_log.append(
            {
                "call_index": self.calls,
                "case": case,
                "command": command,
                "exit_code": completed.returncode,
                "report": str(report),
                "stdout_log": str(log),
            }
        )
        return completed.returncode, payload, report, log

    def expect(
        self,
        case: str,
        workbook: Path,
        *,
        exit_code: int,
        codes: list[str] | None = None,
        checks: dict | None = None,
        report_name: str | None = None,
        baseline: bool = False,
        type_check: list[tuple[str, str, int, str]] | None = None,
    ) -> None:
        problems: list[str] = []
        observed_types: list[dict] = []
        if type_check:
            targets = [(sheet, field, row) for sheet, field, row, _ in type_check]
            observed_types = self.observe_types(workbook, targets)
            for observed, (sheet, field, row, expected_type) in zip(observed_types, type_check):
                if observed["data_type"] != expected_type:
                    problems.append(
                        f"造数后单元格类型不符：{sheet}.{field}（第 {row} 行）期望 {expected_type}，"
                        f"实际 {observed['data_type']}"
                    )
        actual_code, payload, report, log = self.run_checker(case, workbook, report_name, baseline)
        if actual_code != exit_code:
            problems.append(f"退出码期望 {exit_code}，实际 {actual_code}")
        if codes:
            actual_codes = set((payload or {}).get("issue_counts_by_code", {}))
            missing = sorted(set(codes) - actual_codes)
            if missing:
                problems.append(f"缺少问题代码 {missing}（实际 {sorted(actual_codes)}）")
        for label, predicate in (checks or {}).items():
            try:
                satisfied = bool(predicate(payload))
            except Exception as exc:  # noqa: BLE001 - 报告结构异常也算失败
                satisfied = False
                problems.append(f"{label} 读取报告时异常：{exc!r}")
            if not satisfied:
                problems.append(f"断言失败：{label}")
        record = {
            "case": case,
            "kind": "boundary" if report_name is None else "baseline",
            "workbook": str(workbook),
            "exit_code": actual_code,
            "expected_exit_code": exit_code,
            "issue_counts_by_code": (payload or {}).get("issue_counts_by_code", {}),
            "reconciliation_status": (payload or {}).get("reconciliation", {}).get("status"),
            "observed_types": observed_types,
            "report": str(report),
            "stdout_log": str(log),
            "result": "PASS" if not problems else "FAIL",
            "problems": problems,
        }
        self.results.append(record)
        if problems:
            self.failures.append(record)
        print(f"[{'PASS' if not problems else 'FAIL'}] {case} exit={actual_code}"
              + ("" if not problems else "  | " + " ; ".join(problems)))


# ---------- 报告断言小工具 ----------
def issues_include(payload: dict, code: str) -> bool:
    return code in payload["issue_counts_by_code"]


def issue_located_at(payload: dict, code: str, sheet: str, column: str) -> bool:
    return any(
        item["code"] == code and item["sheet"] == sheet and item["column"] == column
        for item in payload["issues"]
    )


def unusable_total(payload: dict) -> int:
    return payload["amount_summary"]["unusable_amount_cells"]["total"]


def unusable_reason(payload: dict, reason: str) -> int:
    return payload["amount_summary"]["unusable_amount_cells"]["by_reason"].get(reason, 0)


def known_subtotal(payload: dict, label: str):
    return payload["amount_summary"]["known_valid_subtotals_cents"][label]


def complete_total(payload: dict, label: str):
    return payload["amount_summary"]["complete_totals_cents"][label]


def diagnostic(payload: dict, field: str):
    return payload["reconciliation"]["diagnostic_known_valid_subtotals_cents"][field]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TASK-002-R1 校验器回归验证")
    parser.add_argument("--out-dir", required=True, help="输出目录，必须位于 data/generated 内且不存在")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir = out_dir.resolve() if out_dir.is_absolute() else (Path.cwd() / out_dir).resolve()
    try:
        out_dir.relative_to(GENERATED_ROOT)
    except ValueError:
        fail(f"输出目录必须位于 {GENERATED_ROOT} 之内：{out_dir}")
    if out_dir == GENERATED_ROOT:
        fail("输出目录不能是 data/generated 本身")
    if out_dir.exists():
        fail(f"输出目录已存在，拒绝覆盖旧证据：{out_dir}")
    for required in (CHECKER, C01_SOURCE, C07B_SOURCE, C14A_SOURCE, MAIN_INPUT):
        if not required.exists():
            fail(f"缺少必需输入：{required}")

    hashes_before = {str(path): sha256(path) for path in PROTECTED_INPUTS if path.exists()}
    out_dir.mkdir(parents=True)
    regression = Regression(out_dir)
    print(f"回归输出目录: {out_dir}")
    print(f"被验证校验器: {CHECKER}")
    print()

    # ---------- 1. 必填日期为空 ----------
    regression.expect(
        "B01_payment_date_blank",
        regression.make_case("B01_payment_date_blank", C01_SOURCE, [("payments", "payment_date", None)]),
        exit_code=1,
        codes=["MISSING_REQUIRED_VALUE"],
        checks={
            "缺失定位到 payments.payment_date": lambda p: issue_located_at(p, "MISSING_REQUIRED_VALUE", "payments", "payment_date"),
            "完整勾稽标为 NOT_ASSESSED": lambda p: p["reconciliation"]["status"] == "NOT_ASSESSED",
            "known_plus_missing_equals_master 为 null": lambda p: p["reconciliation"]["known_plus_missing_equals_master"] is None,
        },
    )
    regression.expect(
        "B02_ap_date_blank",
        regression.make_case("B02_ap_date_blank", C01_SOURCE, [("payables", "ap_date", None)]),
        exit_code=1,
        codes=["MISSING_REQUIRED_VALUE"],
        checks={"缺失定位到 payables.ap_date": lambda p: issue_located_at(p, "MISSING_REQUIRED_VALUE", "payables", "ap_date")},
    )

    # ---------- 2. 日期时间成分与正向控制 ----------
    regression.expect(
        "B03_payment_date_nonmidnight_datetime",
        regression.make_case(
            "B03_payment_date_nonmidnight_datetime",
            C01_SOURCE,
            [("payments", "payment_date", datetime(2026, 9, 10, 12, 34, 56))],
        ),
        exit_code=1,
        codes=["DATE_TIME_COMPONENT_PRESENT"],
        checks={"时间成分定位到 payments.payment_date": lambda p: issue_located_at(p, "DATE_TIME_COMPONENT_PRESENT", "payments", "payment_date")},
    )
    regression.expect(
        "P04_midnight_datetime_is_accepted",
        regression.make_case(
            "P04_midnight_datetime_is_accepted",
            C01_SOURCE,
            [("payments", "payment_date", datetime(2026, 9, 10, 0, 0, 0))],
        ),
        exit_code=0,
        checks={
            "午夜原生日期不被误拦": lambda p: p["result"] == "pass",
            "完整金额仍为 500000 分": lambda p: complete_total(p, "payments_amount") == 500000,
            "勾稽正常评估且相等": lambda p: p["reconciliation"]["status"] == "ASSESSED"
            and p["reconciliation"]["known_plus_missing_equals_master"] is True,
        },
    )

    # ---------- 3. 表头逐字匹配 ----------
    regression.expect(
        "B04_ap_id_header_trailing_space",
        regression.make_case(
            "B04_ap_id_header_trailing_space",
            C01_SOURCE,
            header_edits=[("payables", "ap_id", "ap_id ")],
        ),
        exit_code=1,
        codes=["REQUIRED_COLUMN_MISSING"],
        checks={
            "定位到 payables.ap_id 缺列": lambda p: issue_located_at(p, "REQUIRED_COLUMN_MISSING", "payables", "ap_id"),
            "字段映射显示 ap_id 未映射": lambda p: p["structure"]["sheet_field_mapping"]["payables"]["ap_id"] is None,
            "该行未被当作空白行丢弃": lambda p: p["row_accounting"]["payables"]["source_rows"] == 1
            and p["row_accounting"]["payables"]["blank_rows"] == 0,
        },
    )

    # ---------- 4. 标识保真（值内空格不得被吞掉） ----------
    regression.expect(
        "B05_ap_id_value_leading_space",
        regression.make_case("B05_ap_id_value_leading_space", C01_SOURCE, [("allocations", "ap_id", " AP01")]),
        exit_code=0,
        checks={
            "质量检查仍可通过": lambda p: p["result"] == "pass",
            "已知应付关联净额为 0": lambda p: diagnostic(p, "known_payable_link_net") == 0,
            "缺失应付关联净额为 500000 分": lambda p: diagnostic(p, "missing_payable_link_net") == 500000,
            "台账外标识明细计入 ap_id_not_in_ledger": lambda p: diagnostic(p, "missing_payable_link_detail")["ap_id_not_in_ledger"] == 500000,
        },
    )

    # ---------- 5. 布尔与非文本标识 ----------
    regression.expect(
        "B09_boolean_payment_ids",
        regression.make_case(
            "B09_boolean_payment_ids",
            C01_SOURCE,
            [("payments", "payment_id", True), ("allocations", "payment_id", True)],
        ),
        exit_code=1,
        codes=["ID_TYPE_INVALID"],
        checks={
            "主键列布尔值定位到 payments.payment_id": lambda p: issue_located_at(p, "ID_TYPE_INVALID", "payments", "payment_id"),
            "分摊引用列布尔值也报告": lambda p: issue_located_at(p, "ID_TYPE_INVALID", "allocations", "payment_id"),
            "布尔值不再被当成合法文本": lambda p: p["issue_counts_by_code"].get("ID_TYPE_INVALID", 0) >= 2,
        },
    )
    regression.expect(
        "B10_boolean_nullable_id",
        regression.make_case(
            "B10_boolean_nullable_id", C01_SOURCE, [("allocations", "original_allocation_id", True)]
        ),
        exit_code=1,
        codes=["ID_TYPE_INVALID"],
        checks={"可空标识的非文本类型同样阻断": lambda p: issue_located_at(p, "ID_TYPE_INVALID", "allocations", "original_allocation_id")},
    )

    # ---------- 6. 文本前导零与数值 ID 的正负控制 ----------
    regression.expect(
        "P05_leading_zero_text_ids_accepted",
        regression.make_case(
            "P05_leading_zero_text_ids_accepted",
            C01_SOURCE,
            [("payments", "payment_id", "0001"), ("allocations", "payment_id", "0001")],
        ),
        exit_code=0,
        checks={
            "真实文本 0001 正常通过": lambda p: p["result"] == "pass",
            "金额勾稽相等": lambda p: p["reconciliation"]["known_plus_missing_equals_master"] is True,
        },
    )
    regression.expect(
        "B11_numeric_ids_rejected",
        regression.make_case(
            "B11_numeric_ids_rejected", C01_SOURCE, [("payments", "payment_id", 1), ("allocations", "payment_id", 1)]
        ),
        exit_code=1,
        codes=["ID_TYPE_INVALID"],
        checks={"数值标识不能靠显示格式通过": lambda p: p["issue_counts_by_code"].get("ID_TYPE_INVALID", 0) >= 2},
    )

    # ---------- 7. 金额不可用：N/A、空值、公式 ----------
    for name, value, reason in [
        ("B06_both_amounts_NA", "N/A", "AMOUNT_INVALID"),
        ("B07_both_amounts_blank", None, "MISSING_REQUIRED_VALUE"),
        ("B08_both_amounts_formula", "=5000", "FORMULA_NOT_ALLOWED"),
    ]:
        regression.expect(
            name,
            regression.make_case(
                name,
                C01_SOURCE,
                [("payments", "amount", value), ("allocations", "allocated_amount", value)],
            ),
            exit_code=1,
            codes=[reason],
            checks={
                "不可用金额单元格数为 2": lambda p: unusable_total(p) == 2,
                f"{reason} 计数为 2": lambda p, r=reason: unusable_reason(p, r) == 2,
                "payments 完整总额为 null": lambda p: complete_total(p, "payments_amount") is None,
                "allocations 完整总额为 null": lambda p: complete_total(p, "allocations_allocated_amount") is None,
                "已知有效小计为 0（不等于真实金额零）": lambda p: known_subtotal(p, "payments_amount") == 0,
                "完整勾稽 NOT_ASSESSED": lambda p: p["reconciliation"]["status"] == "NOT_ASSESSED",
                "known_plus_missing_equals_master 为 null 而非 true": lambda p: p["reconciliation"]["known_plus_missing_equals_master"] is None,
                "完整 master_net 为 null": lambda p: p["reconciliation"]["complete_totals_cents"]["master_net"] is None,
            },
        )

    # ---------- 8. 非正金额 ----------
    regression.expect(
        "B12_zero_amounts",
        regression.make_case(
            "B12_zero_amounts", C01_SOURCE, [("payments", "amount", "0.00"), ("allocations", "allocated_amount", "0.00")]
        ),
        exit_code=1,
        codes=["AMOUNT_NOT_POSITIVE"],
        checks={
            "零金额计入不可用单元格": lambda p: unusable_total(p) == 2,
            "AMOUNT_NOT_POSITIVE 计数为 2": lambda p: unusable_reason(p, "AMOUNT_NOT_POSITIVE") == 2,
            "完整总额为 null": lambda p: complete_total(p, "payments_amount") is None,
        },
    )
    regression.expect(
        "B13_negative_amounts",
        regression.make_case(
            "B13_negative_amounts", C01_SOURCE, [("payments", "amount", -100), ("allocations", "allocated_amount", -100)]
        ),
        exit_code=1,
        codes=["AMOUNT_NOT_POSITIVE"],
        checks={
            "负金额计入不可用单元格": lambda p: unusable_total(p) == 2,
            "勾稽 NOT_ASSESSED": lambda p: p["reconciliation"]["status"] == "NOT_ASSESSED",
        },
    )

    # ---------- 9. 正向控制 ----------
    regression.expect(
        "P01_intact_c01",
        regression.copy_case("P01_intact_c01", C01_SOURCE),
        exit_code=0,
        checks={
            "无问题": lambda p: p["issues"] == [],
            "三表完整金额均为 500000 分": lambda p: complete_total(p, "payments_amount") == 500000
            and complete_total(p, "allocations_allocated_amount") == 500000
            and complete_total(p, "payables_payable_amount") == 500000,
            "无不可用金额单元格": lambda p: unusable_total(p) == 0,
            "勾稽相等": lambda p: p["reconciliation"]["status"] == "ASSESSED"
            and p["reconciliation"]["known_plus_missing_equals_master"] is True,
        },
    )
    regression.expect(
        "P02_intact_c07b",
        regression.copy_case("P02_intact_c07b", C07B_SOURCE),
        exit_code=0,
        checks={
            "总体资金 500000 分": lambda p: diagnostic(p, "settled_pay_total") == 500000,
            "已知应付关联 300000 分": lambda p: diagnostic(p, "known_payable_link_net") == 300000,
            "缺失应付关联 200000 分": lambda p: diagnostic(p, "missing_payable_link_net") == 200000,
            "空 ap_id 计入 empty_ap_id": lambda p: diagnostic(p, "missing_payable_link_detail")["empty_ap_id"] == 200000,
            "勾稽相等": lambda p: p["reconciliation"]["known_plus_missing_equals_master"] is True,
        },
    )
    regression.expect(
        "B14_c14a_missing_amount_column",
        regression.copy_case("B14_c14a_missing_amount_column", C14A_SOURCE),
        exit_code=1,
        codes=["REQUIRED_COLUMN_MISSING"],
        checks={
            "缺少 payable_amount 列": lambda p: issue_located_at(p, "REQUIRED_COLUMN_MISSING", "payables", "payable_amount"),
            "payables 完整总额为 null": lambda p: complete_total(p, "payables_payable_amount") is None,
            "payables 已知小计也为 null": lambda p: known_subtotal(p, "payables_payable_amount") is None,
            "未映射金额列已登记": lambda p: "payables_payable_amount" in p["amount_summary"]["unmapped_amount_columns"],
            "金额报告不伪装完整": lambda p: p["reconciliation"]["status"] == "NOT_ASSESSED",
        },
    )

    # ---------- 10. Excel 错误单元格与真文本对照（TASK-002-R2） ----------
    regression.expect(
        "E01_error_cell_payment_ids",
        regression.make_case(
            "E01_error_cell_payment_ids",
            C01_SOURCE,
            [("payments", "payment_id", "#N/A"), ("allocations", "payment_id", "#N/A")],
        ),
        exit_code=1,
        codes=["ID_TYPE_INVALID"],
        type_check=[("payments", "payment_id", 2, "e"), ("allocations", "payment_id", 2, "e")],
        checks={
            "错误单元格定位到 payments.payment_id": lambda p: issue_located_at(p, "ID_TYPE_INVALID", "payments", "payment_id"),
            "错误单元格定位到 allocations.payment_id": lambda p: issue_located_at(p, "ID_TYPE_INVALID", "allocations", "payment_id"),
        },
    )
    regression.expect(
        "E02_error_cell_bank_reference",
        regression.make_case(
            "E02_error_cell_bank_reference", C01_SOURCE, [("payments", "bank_reference", "#REF!")]
        ),
        exit_code=1,
        codes=["ID_TYPE_INVALID"],
        type_check=[("payments", "bank_reference", 2, "e")],
        checks={
            "已结算银行流水的错误单元格被报告": lambda p: issue_located_at(p, "ID_TYPE_INVALID", "payments", "bank_reference")
        },
    )
    regression.expect(
        "E03_error_cell_nullable_ap_id",
        regression.make_case("E03_error_cell_nullable_ap_id", C01_SOURCE, [("allocations", "ap_id", "#N/A")]),
        exit_code=1,
        codes=["ID_TYPE_INVALID"],
        type_check=[("allocations", "ap_id", 2, "e")],
        checks={
            "可空标识的错误单元格仍阻断": lambda p: issue_located_at(p, "ID_TYPE_INVALID", "allocations", "ap_id")
        },
    )
    regression.expect(
        "E04_true_text_error_looking_ids",
        regression.make_forced_text_case(
            "E04_true_text_error_looking_ids",
            C01_SOURCE,
            [("payments", "payment_id", "#N/A"), ("allocations", "payment_id", "#N/A")],
        ),
        exit_code=0,
        type_check=[("payments", "payment_id", 2, "s"), ("allocations", "payment_id", 2, "s")],
        checks={
            "真文本 #N/A 不被按内容黑名单禁止": lambda p: p["result"] == "pass",
            "两份文本一致，勾稽仍相等": lambda p: p["reconciliation"]["known_plus_missing_equals_master"] is True,
        },
    )

    # ---------- 11. 带显式时间的文本日期一律阻断（R2 收回 R1 的额外格式） ----------
    regression.expect(
        "E05_text_date_zero_time_space",
        regression.make_case(
            "E05_text_date_zero_time_space", C01_SOURCE, [("payments", "payment_date", "2026-09-10 00:00:00")]
        ),
        exit_code=1,
        codes=["DATE_TIME_COMPONENT_PRESENT"],
        type_check=[("payments", "payment_date", 2, "s")],
        checks={
            "带时间的文本日期不再被接受": lambda p: issue_located_at(p, "DATE_TIME_COMPONENT_PRESENT", "payments", "payment_date")
        },
    )
    regression.expect(
        "E06_text_date_zero_time_T_separator",
        regression.make_case(
            "E06_text_date_zero_time_T_separator", C01_SOURCE, [("payments", "payment_date", "2026-09-10T00:00:00")]
        ),
        exit_code=1,
        codes=["DATE_TIME_COMPONENT_PRESENT"],
        type_check=[("payments", "payment_date", 2, "s")],
    )
    regression.expect(
        "E07_text_date_nonzero_time",
        regression.make_case(
            "E07_text_date_nonzero_time", C01_SOURCE, [("payments", "payment_date", "2026-09-10 12:34:56")]
        ),
        exit_code=1,
        codes=["DATE_TIME_COMPONENT_PRESENT"],
        type_check=[("payments", "payment_date", 2, "s")],
    )

    # ---------- 12. 文本形式的负金额（R2 补充；R1 当时只测了数值负数） ----------
    regression.expect(
        "E08_text_negative_amounts",
        regression.make_case(
            "E08_text_negative_amounts",
            C01_SOURCE,
            [("payments", "amount", "-1.00"), ("allocations", "allocated_amount", "-1.00")],
        ),
        exit_code=1,
        codes=["AMOUNT_INVALID"],
        type_check=[("payments", "amount", 2, "s"), ("allocations", "allocated_amount", 2, "s")],
        checks={
            "文本负金额两处计入不可用": lambda p: unusable_total(p) == 2,
            "完整总额为 null": lambda p: complete_total(p, "payments_amount") is None,
            "勾稽 NOT_ASSESSED": lambda p: p["reconciliation"]["status"] == "NOT_ASSESSED",
        },
    )

    # ---------- 13. 报告路径拒绝覆盖 ----------
    same_report_input = regression.copy_case("R16_report_overwrite_guard", C01_SOURCE)
    first_code, _, first_report, first_log = regression.run_checker(
        "R16_report_overwrite_guard", same_report_input, "R16_report_overwrite_guard"
    )
    first_report_hash = sha256(first_report) if first_report.exists() else None
    second_code, _, _, second_log = regression.run_checker(
        "R16_report_overwrite_guard", same_report_input, "R16_report_overwrite_guard"
    )
    second_report_hash = sha256(first_report) if first_report.exists() else None
    guard_problems = []
    if first_code != 0:
        guard_problems.append(f"首次校验期望 0，实际 {first_code}")
    if second_code != 2:
        guard_problems.append(f"报告已存在时期望退出码 2，实际 {second_code}")
    if first_report_hash is None:
        guard_problems.append("首次报告未生成")
    elif first_report_hash != second_report_hash:
        guard_problems.append("第二次调用改动了第一份报告（拒绝覆盖失效）")
    if first_log == second_log:
        guard_problems.append("两次调用使用了同一 stdout 日志名，前一次输出会被覆盖")
    else:
        if not first_log.exists():
            guard_problems.append(f"第一次调用 stdout 未独立保存：{first_log}")
        if not second_log.exists():
            guard_problems.append(f"第二次调用 stdout 未独立保存：{second_log}")
    if first_report_hash is None or first_report_hash != second_report_hash:
        guard_problems.append("拒绝覆盖未通过前后哈希比较")
    regression.results.append(
        {
            "case": "R16_report_overwrite_guard",
            "kind": "boundary",
            "workbook": str(same_report_input),
            "exit_code": second_code,
            "expected_exit_code": 2,
            "first_call_exit_code": first_code,
            "first_report_sha256": first_report_hash,
            "second_report_sha256": second_report_hash,
            "report": str(first_report),
            "stdout_logs": [str(first_log), str(second_log)],
            "result": "PASS" if not guard_problems else "FAIL",
            "problems": guard_problems,
        }
    )
    if guard_problems:
        regression.failures.append(regression.results[-1])
    print(f"[{'PASS' if not guard_problems else 'FAIL'}] R16_report_overwrite_guard exit={second_code}"
          + ("" if not guard_problems else "  | " + " ; ".join(guard_problems)))

    # ---------- 11. 基线复跑：主文件 ----------
    print()
    print("=== 基线复跑（主文件与 22 份原 fixture） ===")
    regression.expect(
        "MAIN_erp_export",
        MAIN_INPUT,
        exit_code=0,
        checks={
            "四表行数不变": lambda p: [
                p["row_accounting"][s]["source_rows"] for s in ("suppliers", "payables", "payments", "allocations")
            ] == [20, 993, 1000, 1005],
            "无不可用金额单元格": lambda p: unusable_total(p) == 0,
            "三表完整金额均非 null": lambda p: all(
                complete_total(p, label) is not None
                for label in ("payables_payable_amount", "payments_amount", "allocations_allocated_amount")
            ),
            "勾稽正常评估且相等": lambda p: p["reconciliation"]["status"] == "ASSESSED"
            and p["reconciliation"]["known_plus_missing_equals_master"] is True,
            "已结算 PAY 267949329 分": lambda p: diagnostic(p, "settled_pay_total") == 267949329,
            "已结算退款 700000 分": lambda p: diagnostic(p, "settled_refund_total") == 700000,
            "缺失应付关联净额 1000000 分": lambda p: diagnostic(p, "missing_payable_link_net") == 1000000,
        },
        report_name="baseline_reports_main",
        baseline=True,
    )
    for case_id, (expected_exit, expected_codes) in FIXTURE_EXPECTED.items():
        regression.expect(
            f"FIXTURE_{case_id}",
            BASELINE_DIR / "fixtures" / f"{case_id}.xlsx",
            exit_code=expected_exit,
            codes=expected_codes or None,
            report_name=f"baseline_reports_fixture_{case_id}",
            baseline=True,
        )

    # ---------- 14. 只读输入保护（哈希失败必须使整个验证失败） ----------
    hashes_after = {str(path): sha256(path) for path in PROTECTED_INPUTS if path.exists()}
    hash_problems = [
        str(path) for path, digest in hashes_before.items() if hashes_after.get(path) != digest
    ]
    if hash_problems:
        regression.failures.append(
            {
                "case": "INTEGRITY_readonly_inputs",
                "kind": "integrity",
                "workbook": None,
                "exit_code": None,
                "expected_exit_code": None,
                "result": "FAIL",
                "problems": [f"只读输入在回归前后哈希不一致：{path}" for path in hash_problems],
            }
        )
        print("[FAIL] INTEGRITY_readonly_inputs 只读输入在回归前后哈希不一致：")
        for path in hash_problems:
            print(f"        - {path}")
    else:
        print("[PASS] INTEGRITY_readonly_inputs 只读输入前后哈希一致")

    summary = {
        "task": "TASK-002-R1" if not (out_dir.name.startswith("task002_r2")) else "TASK-002-R2",
        "generated_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "out_dir": str(out_dir),
        "checker": {"path": str(CHECKER), "sha256": sha256(CHECKER)},
        "totals": {
            "cases": len(regression.results),
            "passed": sum(1 for item in regression.results if item["result"] == "PASS"),
            "failed": len(regression.failures),
            "checker_invocations": regression.calls,
        },
        "results": regression.results,
        "failures": regression.failures,
        "protected_inputs_count": len(hashes_before),
        "protected_inputs_unchanged": not hash_problems,
        "protected_inputs_changed": hash_problems,
        "protected_input_hashes": hashes_after,
        "notes": [
            "预期值来自 SPEC_V1.md 与 TASK-002-R2.md，不读取答案册，不导入生成器。",
            "所有断言基于命令行运行真实校验器后落盘的报告内容与退出码。",
            "新增类型用例在造数后会重新读取副本并核对单元格实际 data_type（e 与 s 必须区分）。",
            "每次校验调用使用唯一 stdout 日志名，command_log.json 登记对应日志路径。",
            "只读输入哈希不一致会使整个验证返回非零，并记为完整性失败。",
            "失败案例的输入副本、报告与日志一律保留，不自动删除。",
        ],
    }
    (out_dir / "regression_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "command_log.json").write_text(
        json.dumps(regression.command_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print()
    print(
        f"用例总数 {summary['totals']['cases']}，通过 {summary['totals']['passed']}，"
        f"失败 {summary['totals']['failed']}，checker 调用 {summary['totals']['checker_invocations']} 次"
    )
    print(
        f"只读输入前后哈希一致: {summary['protected_inputs_unchanged']}"
        f"（受保护输入 {summary['protected_inputs_count']} 个）"
    )
    print(f"汇总: {out_dir / 'regression_summary.json'}")
    print(f"命令日志: {out_dir / 'command_log.json'}")
    if regression.failures:
        print("存在失败用例或完整性失败，返回非零退出码（不输出总体成功结论）。")
        return 1
    print("全部回归用例通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
