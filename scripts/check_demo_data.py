#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-002 数据质量校验器（只做数据质量与结构核验）。

边界（TASK-002 第 4.2 节）：
  - 只从实际落盘的 Excel 重新读取原值与类型，不校验生成器内存中的列表。
  - 不实现 R01—R04，不输出命中计数或审计等级，不读取答案册，也不导入生成器函数。
  - 允许空或未知 ap_id，允许收款对象与应付供应商不同，这两类不构成质量失败。
  - 结果只是数据质量结论，不代表业务审计结果正确，也不能替代人工判断。

退出码：0 数据质量检查通过；1 发现数据质量／范围问题；2 参数、路径或文件无法读取等运行问题。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()

PERIOD_START = date(2026, 9, 1)
PERIOD_END = date(2026, 9, 30)

SHEET_ORDER = ["suppliers", "payables", "payments", "allocations"]

TEXT_REQUIRED = "text_required"
TEXT_OPTIONAL = "text_optional"
TEXT_HANDLED = "text_handled"
DATE_REQUIRED = "date_required"
AMOUNT_REQUIRED = "amount_required"
CURRENCY_REQUIRED = "currency_required"
ENUM_REQUIRED = "enum_required"

ID_FIELDS = {
    "supplier_id",
    "ap_id",
    "ap_number",
    "payment_id",
    "payee_supplier_id",
    "original_payment_id",
    "allocation_id",
    "original_allocation_id",
    "bank_reference",
}

FIELD_SPEC: dict[str, dict[str, str]] = {
    "suppliers": {
        "supplier_id": TEXT_REQUIRED,
        "supplier_name": TEXT_REQUIRED,
    },
    "payables": {
        "ap_id": TEXT_REQUIRED,
        "ap_number": TEXT_REQUIRED,
        "supplier_id": TEXT_REQUIRED,
        "ap_date": DATE_REQUIRED,
        "payable_amount": AMOUNT_REQUIRED,
        "currency": CURRENCY_REQUIRED,
    },
    "payments": {
        "payment_id": TEXT_REQUIRED,
        "transaction_type": f"{ENUM_REQUIRED}:PAY|REFUND",
        "original_payment_id": TEXT_HANDLED,
        "payee_supplier_id": TEXT_REQUIRED,
        "payment_date": DATE_REQUIRED,
        "amount": AMOUNT_REQUIRED,
        "currency": CURRENCY_REQUIRED,
        "settlement_status": f"{ENUM_REQUIRED}:SETTLED|PENDING|FAILED|VOIDED",
        "bank_reference": TEXT_HANDLED,
    },
    "allocations": {
        "allocation_id": TEXT_REQUIRED,
        "payment_id": TEXT_REQUIRED,
        "ap_id": TEXT_OPTIONAL,
        "allocated_amount": AMOUNT_REQUIRED,
        "original_allocation_id": TEXT_HANDLED,
    },
}

PRIMARY_KEYS = {
    "suppliers": "supplier_id",
    "payables": "ap_id",
    "payments": "payment_id",
    "allocations": "allocation_id",
}

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_TIME_TEXT_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})[ T](?P<time>\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)$"
)
AMOUNT_PATTERN = re.compile(r"^\d+(\.\d+)?$")

DATE_ISSUE_DETAIL = {
    "FORMULA_NOT_ALLOWED": "日期列出现公式单元格",
    "MISSING_REQUIRED_VALUE": "必需日期为空（含纯空白文本）",
    "DATE_INVALID": "日期无效或表示有歧义（仅接受 YYYY-MM-DD 与可无损转换的原生日期）",
    "DATE_TIME_COMPONENT_PRESENT": "日期含非零时间成分，不允许直接截取日期，须报告后由输入方更正",
}

AMOUNT_ISSUE_DETAIL = {
    "FORMULA_NOT_ALLOWED": "金额列出现公式单元格",
    "MISSING_REQUIRED_VALUE": "必需金额为空（含纯空白文本）",
    "AMOUNT_INVALID": "金额无法解析（含货币符号、千分位、科学计数或文本 N/A 等）",
    "AMOUNT_SCALE_INVALID": "金额超过两位小数，禁止自动四舍五入修复",
    "AMOUNT_NOT_POSITIVE": "金额必须严格为正数",
}

AMOUNT_COLUMN_PAIRS = {
    "payables_payable_amount": ("payables", "payable_amount"),
    "payments_amount": ("payments", "amount"),
    "allocations_allocated_amount": ("allocations", "allocated_amount"),
}

LIMITS = [
    "本检查器只做结构与数据质量核验，不实现 R01—R04，不输出任何规则命中计数或审计等级。",
    "质量检查通过只代表数据可进入后续处理，不代表不存在业务线索，也不代表审计结论正确。",
    "空或未知 ap_id、收款对象与应付供应商不同，是允许保留的业务线索状态，不构成本检查的失败项。",
    "列名第一版逐字匹配：表头多余空格不被自动清理，未映射字段一律形成结构问题。",
    "标识保真：非空文本标识原样保留（不去空格、不改写）；布尔、数值、日期以及 Excel 错误单元格"
    "（cell.data_type = e，如 #N/A、#REF!）都不得当作合格标识；判断依据是单元格类型，不按内容黑名单匹配。",
    "日期第一版只接受原生日期、午夜原生日期时间与 YYYY-MM-DD 文本；带显式时间的文本一律报告，不截取。",
    "批次存在任何问题时，完整金额与勾稽统一为 NOT_ASSESSED（null），只给出明确命名的“已知有效小计”，不按零补齐。",
    "结论基于本次实际落盘的 Excel 原值与类型，未验证真实 ERP 导出、真实银行证据或性能。",
]


def runtime_fail(message: str) -> "None":
    print(f"RUNTIME_ERROR: {message}", file=sys.stderr)
    sys.exit(2)


class IssueCollector:
    def __init__(self) -> None:
        self.issues: list[dict] = []

    def add(
        self,
        code: str,
        sheet: str,
        row: int | None,
        column: str | None,
        value,
        detail: str,
    ) -> None:
        self.issues.append(
            {
                "code": code,
                "severity": "blocking",
                "sheet": sheet,
                "excel_row": row,
                "column": column,
                "value": None if value is None else str(value),
                "detail": detail,
            }
        )

    def counts(self) -> dict[str, int]:
        return dict(sorted(Counter(item["code"] for item in self.issues).items()))


def cell_is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def read_text(cell) -> tuple[str | None, list[str], bool]:
    """读取文本单元格，返回 (文本值或 None, 问题代码列表, 是否存在内容)。

    - 非空文本**原样返回**：不自动去前后空格、不转大小写、不补零、不做模糊匹配；
    - 纯空白（空字符串、纯空格）按空处理；
    - 布尔、数值、日期等非文本类型报告 TEXT_TYPE_INVALID，不得 str() 后当作合格标识；
    - Excel 错误单元格（cell.data_type == "e"，如 #N/A、#REF!、#DIV/0!）不是真实文本：
      值在 Python 中虽然是字符串，仍报告类型问题；调用方对标识字段细化为 ID_TYPE_INVALID。
      判断依据是单元格类型，不按显示内容做黑名单匹配，真正的文本 #N/A 仍属合法文本。
    """
    problems: list[str] = []
    value = cell.value
    if cell.data_type == "f":
        problems.append("FORMULA_NOT_ALLOWED")
        return None, problems, True
    if cell.data_type == "e":
        problems.append("TEXT_TYPE_INVALID")
        return None, problems, True
    if value is None:
        return None, problems, False
    if isinstance(value, str):
        if value.strip() == "":
            return None, problems, False
        return value, problems, True
    problems.append("TEXT_TYPE_INVALID")
    return None, problems, True


def parse_date_cell(cell) -> tuple[date | None, list[str], bool]:
    """读取日期单元格，返回 (日期或 None, 问题代码列表, 是否存在内容)。

    - 空单元格／纯空白文本 → MISSING_REQUIRED_VALUE；
    - 原生 datetime 含非零时分秒或微秒 → DATE_TIME_COMPONENT_PRESENT，不直接截取日期；
    - 原生 date、午夜 datetime 可无损转换；
    - 第一版日期文本**只接受 `YYYY-MM-DD`**；带显式时间的文本（无论时间是否全零、无论用空格还是 T 分隔）
      一律报告 DATE_TIME_COMPONENT_PRESENT，不截取、不扩展格式；
    - 其余无效或歧义表示 → DATE_INVALID。
    """
    problems: list[str] = []
    value = cell.value
    if cell.data_type == "f":
        problems.append("FORMULA_NOT_ALLOWED")
        return None, problems, True
    if cell_is_blank(value):
        problems.append("MISSING_REQUIRED_VALUE")
        return None, problems, False
    if isinstance(value, datetime):
        if value.hour or value.minute or value.second or value.microsecond:
            problems.append("DATE_TIME_COMPONENT_PRESENT")
            return None, problems, True
        return value.date(), problems, True
    if isinstance(value, date):
        return value, problems, True
    if isinstance(value, str):
        text = value.strip()
        if DATE_PATTERN.match(text):
            try:
                return date.fromisoformat(text), problems, True
            except ValueError:
                problems.append("DATE_INVALID")
                return None, problems, True
        matched = DATE_TIME_TEXT_PATTERN.match(text)
        if matched:
            # 第一版日期文本只接受 YYYY-MM-DD：带显式时间的文本一律报告，不截取、不扩展格式
            problems.append("DATE_TIME_COMPONENT_PRESENT")
            return None, problems, True
        problems.append("DATE_INVALID")
        return None, problems, True
    problems.append("DATE_INVALID")
    return None, problems, True


def parse_amount_cell(cell) -> tuple[Decimal | None, int | None, list[str]]:
    """返回 (金额 Decimal 或 None, 整数分或 None, 问题代码列表)。"""
    problems: list[str] = []
    if cell.data_type == "f":
        problems.append("FORMULA_NOT_ALLOWED")
        return None, None, problems
    value = cell.value
    if cell_is_blank(value):
        problems.append("MISSING_REQUIRED_VALUE")
        return None, None, problems
    if isinstance(value, bool):
        problems.append("AMOUNT_INVALID")
        return None, None, problems
    if isinstance(value, (int, float, Decimal)):
        try:
            amount = Decimal(str(value))
        except InvalidOperation:
            problems.append("AMOUNT_INVALID")
            return None, None, problems
    elif isinstance(value, str):
        text = value.strip()
        if not AMOUNT_PATTERN.match(text):
            problems.append("AMOUNT_INVALID")
            return None, None, problems
        amount = Decimal(text)
    else:
        problems.append("AMOUNT_INVALID")
        return None, None, problems

    exponent = amount.as_tuple().exponent
    scale = -exponent if isinstance(exponent, int) and exponent < 0 else 0
    if scale > 2:
        problems.append("AMOUNT_SCALE_INVALID")
        return amount, None, problems
    if amount <= 0:
        problems.append("AMOUNT_NOT_POSITIVE")
        return amount, None, problems
    return amount, int(amount.scaleb(2)), problems


def build_report(workbook_path: Path, issues: IssueCollector, extra) -> dict:
    return {
        "checker": {
            "path": "scripts/check_demo_data.py",
            "sha256": hashlib.sha256(SELF_PATH.read_bytes()).hexdigest(),
            "purpose": "只做数据质量与结构核验，不实现 R01—R04",
        },
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workbook": {
            "path": str(workbook_path),
            "sha256": hashlib.sha256(workbook_path.read_bytes()).hexdigest(),
            "size_bytes": workbook_path.stat().st_size,
        },
        "structure": extra["structure"],
        "row_accounting": extra["row_accounting"],
        "amount_summary": extra["amount_summary"],
        "reconciliation": extra["reconciliation"],
        "issues": issues.issues,
        "issue_counts_by_code": issues.counts(),
        "result": "issues_found" if issues.issues else "pass",
        "limits": LIMITS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TASK-002 数据质量校验器（只做质量核验）")
    parser.add_argument("--workbook", required=True, help="待校验的 .xlsx 输入工作簿")
    parser.add_argument("--report", required=True, help="校验报告输出路径（必须是新文件）")
    args = parser.parse_args(argv)

    workbook_path = Path(args.workbook)
    report_path = Path(args.report)

    if workbook_path.suffix.lower() != ".xlsx":
        runtime_fail(f"--workbook 必须是 .xlsx 文件：{workbook_path}")
    if not workbook_path.is_file():
        runtime_fail(f"工作簿不存在或不是文件：{workbook_path}")
    if report_path.resolve() == workbook_path.resolve():
        runtime_fail("报告路径不能与输入工作簿相同")
    if report_path.exists():
        runtime_fail(f"报告路径已存在，不覆盖：{report_path}")
    try:
        workbook = load_workbook(workbook_path, data_only=False)
    except Exception as exc:  # noqa: BLE001 - 运行问题统一出口
        runtime_fail(f"无法读取工作簿：{exc}")

    issues = IssueCollector()
    structure = {
        "sheets_found": list(workbook.sheetnames),
        "notes": [],
        "sheet_headers": {},
        "sheet_field_mapping": {},
    }
    unusable_amount_cells: list[dict] = []
    for required_sheet in SHEET_ORDER:
        if required_sheet not in workbook.sheetnames:
            issues.add("MISSING_SHEET", required_sheet, None, None, None, "缺少必需工作表")
    for name in workbook.sheetnames:
        if name not in SHEET_ORDER:
            structure["notes"].append(f"额外工作表（先登记，不自动纳入检查）：{name}")

    records_by_sheet: dict[str, list[dict]] = {}
    blank_rows_by_sheet: dict[str, int] = {}
    fields_by_sheet: dict[str, dict[str, object]] = {}
    structural_block: dict[str, bool] = {}

    for sheet in SHEET_ORDER:
        if sheet not in workbook.sheetnames:
            records_by_sheet[sheet] = []
            blank_rows_by_sheet[sheet] = 0
            fields_by_sheet[sheet] = {}
            structural_block[sheet] = True
            continue
        worksheet = workbook[sheet]
        header_cells = list(next(worksheet.iter_rows(min_row=1, max_row=1)))
        header = [cell.value for cell in header_cells]
        structure["sheet_headers"][sheet] = [None if cell_is_blank(v) else str(v) for v in header]
        # 第一版列名逐字匹配：不 strip、不改写，表头末尾空格版标识不是固定列名
        names = [None if cell_is_blank(v) else (v if isinstance(v, str) else str(v)) for v in header]
        present_names = [name for name in names if name is not None]
        if not present_names:
            issues.add("REQUIRED_COLUMN_MISSING", sheet, 1, None, None, "表头为空，无法识别任何必需列")
        duplicates = [name for name, count in Counter(present_names).items() if count > 1]
        for name in duplicates:
            issues.add("DUPLICATE_COLUMN_NAME", sheet, 1, name, name, "表头出现重复列名")
        required_fields = FIELD_SPEC[sheet]
        missing_columns = [name for name in required_fields if name not in present_names]
        for name in missing_columns:
            issues.add(
                "REQUIRED_COLUMN_MISSING",
                sheet,
                1,
                name,
                None,
                f"{sheet} 缺少必需列 {name}（第一版逐字匹配列名，不自动去除表头空格）",
            )
        for name in present_names:
            if name not in required_fields:
                structure["notes"].append(f"额外列（先登记，不自动纳入检查）：{sheet}.{name}")
        structural_block[sheet] = bool(missing_columns) or bool(duplicates) or not present_names

        index_by_column: dict[str, int] = {}
        for position, name in enumerate(names):
            if name is not None and name not in index_by_column:
                index_by_column[name] = position
        structure["sheet_field_mapping"][sheet] = {
            name: (index_by_column[name] + 1 if name in index_by_column else None)
            for name in required_fields
        }

        records: list[dict] = []
        blank_rows = 0
        for row_cells in worksheet.iter_rows(min_row=2):
            # 完全空白行按原始整行单元格判断：数据只落在未识别列也不能当空白行丢弃
            if all(cell_is_blank(cell.value) for cell in row_cells):
                blank_rows += 1
                continue
            mapped_cells: dict[str, object] = {}
            for name in required_fields:
                position = index_by_column.get(name)
                if position is not None and position < len(row_cells):
                    mapped_cells[name] = row_cells[position]
            records.append(
                {
                    "excel_row": row_cells[0].row,
                    "cells": mapped_cells,
                    "unmapped_fields": [name for name in required_fields if name not in mapped_cells],
                }
            )
        records_by_sheet[sheet] = records
        blank_rows_by_sheet[sheet] = blank_rows

        parsed_rows: list[dict] = []
        for record in records:
            parsed = {"excel_row": record["excel_row"]}
            if record["unmapped_fields"]:
                parsed["unmapped_fields"] = list(record["unmapped_fields"])
            for name, kind in required_fields.items():
                cell = record["cells"].get(name)
                if cell is None:
                    # 未映射字段已按结构问题报告，这里不得静默假装该字段已核验
                    parsed[name] = None
                    continue
                if kind == DATE_REQUIRED:
                    value, problems, present = parse_date_cell(cell)
                    parsed[name] = value
                    for code in problems:
                        issues.add(
                            code,
                            sheet,
                            record["excel_row"],
                            name,
                            cell.value,
                            DATE_ISSUE_DETAIL[code],
                        )
                    if value is not None and not (PERIOD_START <= value <= PERIOD_END):
                        issues.add(
                            "DATE_OUT_OF_RANGE",
                            sheet,
                            record["excel_row"],
                            name,
                            cell.value,
                            f"日期不在本版范围 {PERIOD_START} 至 {PERIOD_END} 内（范围外业务须报告，不静默过滤）",
                        )
                elif kind == AMOUNT_REQUIRED:
                    amount, cents, problems = parse_amount_cell(cell)
                    parsed[name] = amount
                    parsed[f"{name}__cents"] = cents
                    for code in problems:
                        issues.add(
                            code,
                            sheet,
                            record["excel_row"],
                            name,
                            cell.value,
                            AMOUNT_ISSUE_DETAIL[code],
                        )
                        unusable_amount_cells.append(
                            {
                                "sheet": sheet,
                                "excel_row": record["excel_row"],
                                "column": name,
                                "value": None if cell.value is None else str(cell.value),
                                "reason": code,
                            }
                        )
                elif kind == CURRENCY_REQUIRED:
                    text, problems, present = read_text(cell)
                    parsed[name] = text
                    for code in problems:
                        issues.add(code, sheet, record["excel_row"], name, cell.value, "币种列格式不符")
                    if text is None and not problems:
                        issues.add(
                            "MISSING_REQUIRED_VALUE",
                            sheet,
                            record["excel_row"],
                            name,
                            cell.value,
                            "币种为空（含纯空白文本）",
                        )
                        parsed[name] = None
                    elif text is not None and text != "CNY":
                        issues.add(
                            "CURRENCY_INVALID",
                            sheet,
                            record["excel_row"],
                            name,
                            cell.value,
                            "非人民币业务明确超出本版范围",
                        )
                elif kind.startswith(ENUM_REQUIRED):
                    allowed = kind.split(":", 1)[1].split("|")
                    text, problems, present = read_text(cell)
                    parsed[name] = text
                    for code in problems:
                        issues.add(code, sheet, record["excel_row"], name, cell.value, "枚举列格式不符")
                    if text is None and not problems:
                        issues.add(
                            "MISSING_REQUIRED_VALUE",
                            sheet,
                            record["excel_row"],
                            name,
                            cell.value,
                            "枚举值为空（含纯空白文本）",
                        )
                        parsed[name] = None
                    elif text is not None and text not in allowed:
                        issues.add(
                            "ENUM_INVALID",
                            sheet,
                            record["excel_row"],
                            name,
                            cell.value,
                            f"取值不在允许集合 {allowed} 内",
                        )
                elif kind == TEXT_REQUIRED:
                    text, problems, present = read_text(cell)
                    parsed[name] = text
                    for code in problems:
                        if code == "TEXT_TYPE_INVALID" and name in ID_FIELDS:
                            code = "ID_TYPE_INVALID"
                        detail = (
                            "标识必须以文本提供并保留前导零，不能凭显示格式猜补，也不接受布尔或数值类型"
                            if code == "ID_TYPE_INVALID"
                            else "文本列格式不符"
                        )
                        issues.add(code, sheet, record["excel_row"], name, cell.value, detail)
                    if text is None and not problems:
                        issues.add(
                            "MISSING_REQUIRED_VALUE",
                            sheet,
                            record["excel_row"],
                            name,
                            cell.value,
                            "必填标识为空（不得用空白代替）",
                        )
                else:  # TEXT_OPTIONAL / TEXT_HANDLED
                    text, problems, present = read_text(cell)
                    parsed[name] = text
                    for code in problems:
                        if code == "TEXT_TYPE_INVALID" and name in ID_FIELDS:
                            code = "ID_TYPE_INVALID"
                        detail = (
                            "可空标识一旦有值也必须是真实文本；允许为空不等于允许布尔、数值或日期类型"
                            if code == "ID_TYPE_INVALID"
                            else "文本列格式不符"
                        )
                        issues.add(code, sheet, record["excel_row"], name, cell.value, detail)
            parsed_rows.append(parsed)
        fields_by_sheet[sheet] = {"records": parsed_rows}

    # 主键唯一
    for sheet in SHEET_ORDER:
        key = PRIMARY_KEYS[sheet]
        seen: dict[str, int] = {}
        for record in fields_by_sheet.get(sheet, {}).get("records", []):
            value = record.get(key)
            if value is None:
                continue
            if value in seen:
                issues.add(
                    "PRIMARY_KEY_DUPLICATE",
                    sheet,
                    record["excel_row"],
                    key,
                    value,
                    f"主键 {key}={value} 在 {sheet} 内重复（首次出现在第 {seen[value]} 行），不得自动去重",
                )
            else:
                seen[value] = record["excel_row"]

    supplier_ids = {
        record["supplier_id"]
        for record in fields_by_sheet.get("suppliers", {}).get("records", [])
        if record.get("supplier_id")
    }
    payable_ids = {
        record["ap_id"]
        for record in fields_by_sheet.get("payables", {}).get("records", [])
        if record.get("ap_id")
    }
    payment_records = fields_by_sheet.get("payments", {}).get("records", [])
    payment_by_id: dict[str, dict] = {}
    for record in payment_records:
        if record.get("payment_id") and record["payment_id"] not in payment_by_id:
            payment_by_id[record["payment_id"]] = record
    allocation_records = fields_by_sheet.get("allocations", {}).get("records", [])
    allocation_by_id: dict[str, dict] = {}
    for record in allocation_records:
        if record.get("allocation_id") and record["allocation_id"] not in allocation_by_id:
            allocation_by_id[record["allocation_id"]] = record

    # 强制关系
    for record in fields_by_sheet.get("payables", {}).get("records", []):
        value = record.get("supplier_id")
        if value and value not in supplier_ids:
            issues.add(
                "FOREIGN_KEY_MISSING",
                "payables",
                record["excel_row"],
                "supplier_id",
                value,
                "应付单供应商不在主数据中，无法确定主体",
            )
    for record in payment_records:
        value = record.get("payee_supplier_id")
        if value and value not in supplier_ids:
            issues.add(
                "FOREIGN_KEY_MISSING",
                "payments",
                record["excel_row"],
                "payee_supplier_id",
                value,
                "收款对象不在主数据中，无法确定主体",
            )
    for record in allocation_records:
        value = record.get("payment_id")
        if value and value not in payment_by_id:
            issues.add(
                "FOREIGN_KEY_MISSING",
                "allocations",
                record["excel_row"],
                "payment_id",
                value,
                "分摊引用的资金事件不存在，无法确定资金事件",
            )

    # 已结算银行流水：必填且唯一；退款关联校验
    settled_bank_seen: dict[str, int] = {}
    for record in payment_records:
        status = record.get("settlement_status")
        transaction_type = record.get("transaction_type")
        if status == "SETTLED":
            reference = record.get("bank_reference")
            if not reference:
                issues.add(
                    "BANK_REFERENCE_MISSING",
                    "payments",
                    record["excel_row"],
                    "bank_reference",
                    None,
                    "已结算事件的银行流水标识必填",
                )
            elif reference in settled_bank_seen:
                issues.add(
                    "SETTLED_BANK_REFERENCE_DUPLICATE",
                    "payments",
                    record["excel_row"],
                    "bank_reference",
                    reference,
                    f"已结算流水标识与第 {settled_bank_seen[reference]} 行重复；"
                    "不能认定有两笔真实付款，也不能自动删除一条",
                )
            else:
                settled_bank_seen[reference] = record["excel_row"]
        if transaction_type == "PAY":
            if record.get("original_payment_id"):
                issues.add(
                    "ORIGINAL_PAYMENT_NOT_ALLOWED",
                    "payments",
                    record["excel_row"],
                    "original_payment_id",
                    record.get("original_payment_id"),
                    "付款事件不得填写原付款标识",
                )
            continue
        if transaction_type != "REFUND":
            continue
        original_id = record.get("original_payment_id")
        if not original_id:
            issues.add(
                "MISSING_REQUIRED_VALUE",
                "payments",
                record["excel_row"],
                "original_payment_id",
                None,
                "退款事件必须指向原付款主表记录",
            )
            continue
        original = payment_by_id.get(original_id)
        if original is None:
            issues.add(
                "REFUND_LINK_INVALID",
                "payments",
                record["excel_row"],
                "original_payment_id",
                original_id,
                "退款指向的原付款不存在",
            )
            continue
        if original.get("transaction_type") != "PAY":
            issues.add(
                "REFUND_LINK_INVALID",
                "payments",
                record["excel_row"],
                "original_payment_id",
                original_id,
                "退款必须指向 PAY 类型事件",
            )
        if original.get("settlement_status") != "SETTLED":
            issues.add(
                "REFUND_LINK_INVALID",
                "payments",
                record["excel_row"],
                "original_payment_id",
                original_id,
                "退款必须关联一个已结算的原付款",
            )
        if original.get("currency") != record.get("currency"):
            issues.add(
                "REFUND_LINK_INVALID",
                "payments",
                record["excel_row"],
                "currency",
                record.get("currency"),
                "退款币种与原付款不一致",
            )
        if original.get("payee_supplier_id") != record.get("payee_supplier_id"):
            issues.add(
                "REFUND_PAYEE_MISMATCH",
                "payments",
                record["excel_row"],
                "payee_supplier_id",
                record.get("payee_supplier_id"),
                "退款对象必须与原付款收款对象一致",
            )
        original_date = original.get("payment_date")
        refund_date = record.get("payment_date")
        if isinstance(original_date, date) and isinstance(refund_date, date) and refund_date < original_date:
            issues.add(
                "REFUND_DATE_BEFORE_ORIGINAL",
                "payments",
                record["excel_row"],
                "payment_date",
                refund_date,
                f"退款日期早于原付款日期 {original_date}",
            )

    # 分摊：原分摊指向、重复目标、主表与分摊平衡、退款累计上限
    allocations_by_payment: dict[str, list[dict]] = defaultdict(list)
    refund_cumulative: dict[str, int] = defaultdict(int)
    for record in allocation_records:
        payment_id = record.get("payment_id")
        if payment_id:
            allocations_by_payment[payment_id].append(record)
        payment = payment_by_id.get(payment_id)
        if payment is None:
            continue
        if payment.get("transaction_type") == "PAY":
            if record.get("original_allocation_id"):
                issues.add(
                    "ORIGINAL_ALLOCATION_NOT_ALLOWED",
                    "allocations",
                    record["excel_row"],
                    "original_allocation_id",
                    record.get("original_allocation_id"),
                    "付款分摊不得填写原分摊标识",
                )
        elif payment.get("transaction_type") == "REFUND":
            original_allocation_id = record.get("original_allocation_id")
            if not original_allocation_id:
                issues.add(
                    "MISSING_REQUIRED_VALUE",
                    "allocations",
                    record["excel_row"],
                    "original_allocation_id",
                    None,
                    "退款分摊必须指向原付款分摊明细",
                )
                continue
            original_allocation = allocation_by_id.get(original_allocation_id)
            if original_allocation is None:
                issues.add(
                    "REFUND_ALLOCATION_TARGET_MISMATCH",
                    "allocations",
                    record["excel_row"],
                    "original_allocation_id",
                    original_allocation_id,
                    "退款分摊指向的原分摊不存在",
                )
                continue
            if original_allocation.get("payment_id") != payment.get("original_payment_id"):
                issues.add(
                    "REFUND_ALLOCATION_TARGET_MISMATCH",
                    "allocations",
                    record["excel_row"],
                    "original_allocation_id",
                    original_allocation_id,
                    "原分摊所属事件与退款主表指向的原付款不一致",
                )
            if (original_allocation.get("ap_id") or None) != (record.get("ap_id") or None):
                issues.add(
                    "REFUND_ALLOCATION_TARGET_MISMATCH",
                    "allocations",
                    record["excel_row"],
                    "ap_id",
                    record.get("ap_id"),
                    "退款分摊的应付对象必须与原分摊完全一致（包括同时为空）",
                )
            if (
                payment.get("settlement_status") == "SETTLED"
                and record.get("allocated_amount__cents") is not None
            ):
                refund_cumulative[original_allocation_id] += record["allocated_amount__cents"]

    for original_allocation_id, cumulative in refund_cumulative.items():
        original_allocation = allocation_by_id.get(original_allocation_id)
        if original_allocation is None:
            continue
        original_cents = original_allocation.get("allocated_amount__cents")
        if original_cents is None:
            continue
        if cumulative > original_cents:
            issues.add(
                "REFUND_EXCEEDS_ORIGINAL",
                "allocations",
                original_allocation["excel_row"],
                "allocated_amount",
                original_allocation.get("allocated_amount"),
                f"截至日累计已结算退款分摊 {cumulative / 100:.2f} 元超过原分摊金额 "
                f"{original_cents / 100:.2f} 元；不能算成正常负净付款",
            )

    duplicate_target_checked: dict[str, dict[str, int]] = defaultdict(dict)
    for record in allocation_records:
        payment_id = record.get("payment_id")
        if not payment_id:
            continue
        target = record.get("ap_id") or ""
        seen = duplicate_target_checked[payment_id]
        if target in seen:
            issues.add(
                "DUPLICATE_ALLOCATION_TARGET",
                "allocations",
                record["excel_row"],
                "ap_id",
                record.get("ap_id"),
                f"同一资金事件对同一应付对象重复出现（首次出现在第 {seen[target]} 行）；"
                "本版不允许同一事件对同一应付对象出现重复分摊",
            )
        else:
            seen[target] = record["excel_row"]

    for payment_id, payment in payment_by_id.items():
        records = allocations_by_payment.get(payment_id, [])
        if not records:
            issues.add(
                "ALLOCATION_MISSING",
                "payments",
                payment["excel_row"],
                "payment_id",
                payment_id,
                "每笔主表事件至少应有一条分摊",
            )
            continue
        payment_cents = payment.get("amount__cents")
        if payment_cents is None:
            continue
        if any(record.get("allocated_amount__cents") is None for record in records):
            continue
        allocation_total = sum(record["allocated_amount__cents"] for record in records)
        if allocation_total != payment_cents:
            issues.add(
                "ALLOCATION_SUM_MISMATCH",
                "payments",
                payment["excel_row"],
                "amount",
                payment.get("amount"),
                f"主表金额 {payment_cents / 100:.2f} 元与分摊合计 {allocation_total / 100:.2f} 元不相等；"
                "不能只分析残余部分或补造分摊",
            )

    # 行数对账、金额小计与勾稽
    row_accounting: dict[str, dict] = {}
    rows_with_issues: dict[str, set[int]] = defaultdict(set)
    for item in issues.issues:
        if item["excel_row"] is not None and item["sheet"] in SHEET_ORDER:
            rows_with_issues[item["sheet"]].add(item["excel_row"])
    for sheet in SHEET_ORDER:
        source_rows = len(fields_by_sheet.get(sheet, {}).get("records", []))
        blocked = len(rows_with_issues.get(sheet, set()))
        if structural_block.get(sheet):
            accepted = 0
        else:
            accepted = source_rows - blocked
        row_accounting[sheet] = {
            "source_rows": source_rows,
            "accepted_rows": accepted,
            "blocked_rows": source_rows - accepted,
            "blank_rows": blank_rows_by_sheet.get(sheet, 0),
            "structural_block": bool(structural_block.get(sheet)),
            "note": "来源业务行数 = 接受行数 + 隔离行数；空白行单独计数，不算业务明细",
        }

    # ---------------- 金额报告：区分“已知有效小计”与“完整总额” ----------------
    amount_columns_mapped = {
        label: structure["sheet_field_mapping"].get(sheet, {}).get(column) is not None
        for label, (sheet, column) in AMOUNT_COLUMN_PAIRS.items()
    }
    table_records = {
        "payables": fields_by_sheet.get("payables", {}).get("records", []),
        "payments": payment_records,
        "allocations": allocation_records,
    }

    # 不可用金额单元格：按 (表, 行, 列) 去重，同一单元格只计一次
    unusable_deduped: dict[tuple, dict] = {}
    for item in unusable_amount_cells:
        unusable_deduped.setdefault((item["sheet"], item["excel_row"], item["column"]), item)
    unusable_list = [unusable_deduped[key] for key in sorted(unusable_deduped)]
    unusable_by_reason = Counter(item["reason"] for item in unusable_list)

    known_valid_subtotals: dict[str, int | None] = {}
    complete_totals: dict[str, int | None] = {}
    for label, (sheet, column) in AMOUNT_COLUMN_PAIRS.items():
        records = table_records[sheet]
        unusable_here = sum(
            1 for item in unusable_list if item["sheet"] == sheet and item["column"] == column
        )
        if not amount_columns_mapped[label]:
            # 列未映射时连已知小计都不可得，不得用 0 冒充
            known_valid_subtotals[label] = None
            complete_totals[label] = None
            continue
        known_valid_subtotals[label] = sum(record.get(f"{column}__cents") or 0 for record in records)
        complete_totals[label] = known_valid_subtotals[label] if unusable_here == 0 else None

    by_type_status: dict[str, dict] = {}
    for record in payment_records:
        key = f"{record.get('transaction_type')}/{record.get('settlement_status')}"
        entry = by_type_status.setdefault(
            key,
            {
                "count": 0,
                "known_valid_amount_cents": 0,
                "complete_amount_cents": None,
                "unusable_amount_cells": 0,
            },
        )
        entry["count"] += 1
        if record.get("amount__cents") is None:
            entry["unusable_amount_cells"] += 1
        else:
            entry["known_valid_amount_cents"] += record["amount__cents"]
    for entry in by_type_status.values():
        entry["complete_amount_cents"] = (
            entry["known_valid_amount_cents"] if entry["unusable_amount_cells"] == 0 else None
        )

    reconciliation_amounts_available = (
        amount_columns_mapped["payments_amount"] and amount_columns_mapped["allocations_allocated_amount"]
    )
    settled_pay_total = 0
    settled_refund_total = 0
    settled_pay_allocation_total = 0
    settled_refund_allocation_total = 0
    known_net = 0
    missing_empty_net = 0
    missing_unknown_net = 0
    if reconciliation_amounts_available:
        for record in payment_records:
            if record.get("settlement_status") != "SETTLED":
                continue
            cents = record.get("amount__cents") or 0
            if record.get("transaction_type") == "PAY":
                settled_pay_total += cents
            else:
                settled_refund_total += cents
        for record in allocation_records:
            payment = payment_by_id.get(record.get("payment_id"))
            if payment is None or payment.get("settlement_status") != "SETTLED":
                continue
            cents = record.get("allocated_amount__cents") or 0
            sign = 1 if payment.get("transaction_type") == "PAY" else -1
            if payment.get("transaction_type") == "PAY":
                settled_pay_allocation_total += cents
            else:
                settled_refund_allocation_total += cents
            ap_id = record.get("ap_id")
            if not ap_id:
                missing_empty_net += sign * cents
            elif ap_id not in payable_ids:
                missing_unknown_net += sign * cents
            else:
                known_net += sign * cents

    # 保守方案：批次只要存在任何问题，完整勾稽一律 NOT_ASSESSED，比较结果不得为 true
    reconciliation_assessed = not issues.issues and reconciliation_amounts_available
    if reconciliation_assessed:
        complete_totals_cents = {
            "master_net": settled_pay_total - settled_refund_total,
            "known_payable_link_net": known_net,
            "missing_payable_link_net": missing_empty_net + missing_unknown_net,
        }
        known_plus_missing_equals_master = (
            known_net + missing_empty_net + missing_unknown_net
            == settled_pay_total - settled_refund_total
        )
    else:
        complete_totals_cents = {
            "master_net": None,
            "known_payable_link_net": None,
            "missing_payable_link_net": None,
        }
        known_plus_missing_equals_master = None

    if reconciliation_amounts_available:
        diagnostic_subtotals = {
            "settled_pay_total": settled_pay_total,
            "settled_refund_total": settled_refund_total,
            "settled_pay_allocation_total": settled_pay_allocation_total,
            "settled_refund_allocation_total": settled_refund_allocation_total,
            "known_payable_link_net": known_net,
            "missing_payable_link_net": missing_empty_net + missing_unknown_net,
            "missing_payable_link_detail": {
                "empty_ap_id": missing_empty_net,
                "ap_id_not_in_ledger": missing_unknown_net,
            },
        }
    else:
        diagnostic_subtotals = {
            "settled_pay_total": None,
            "settled_refund_total": None,
            "settled_pay_allocation_total": None,
            "settled_refund_allocation_total": None,
            "known_payable_link_net": None,
            "missing_payable_link_net": None,
            "missing_payable_link_detail": None,
        }

    reconciliation = {
        "status": "ASSESSED" if reconciliation_assessed else "NOT_ASSESSED",
        "diagnostic_known_valid_subtotals_cents": diagnostic_subtotals,
        "complete_totals_cents": complete_totals_cents,
        "known_plus_missing_equals_master": known_plus_missing_equals_master,
        "payable_total_cents": complete_totals["payables_payable_amount"],
        "allocation_total_cents": complete_totals["allocations_allocated_amount"],
        "note": "主表与分摊是两种观察粒度，不加总；应付总额按唯一 ap_id 汇总，不要求等于付款总额。"
        "存在不可用金额单元格或缺失金额列时，完整金额为 null、勾稽为 NOT_ASSESSED，"
        "不得按零补齐，也不得宣称全表勾稽通过。",
    }

    extra = {
        "structure": structure,
        "row_accounting": row_accounting,
        "amount_summary": {
            "known_valid_subtotals_cents": known_valid_subtotals,
            "complete_totals_cents": complete_totals,
            "complete_totals_note": "完整总额仅在对应金额列已映射且该列没有任何不可用单元格时给出，否则为 null。",
            "unusable_amount_cells": {
                "total": len(unusable_list),
                "by_reason": dict(sorted(unusable_by_reason.items())),
                "sources": unusable_list,
                "note": "同一单元格只计一次；覆盖空值、无法解析、超两位小数、公式与非正金额。",
            },
            "unmapped_amount_columns": [
                label for label, mapped in amount_columns_mapped.items() if not mapped
            ],
            "payments_by_type_and_status": by_type_status,
        },
        "reconciliation": reconciliation,
    }

    report = build_report(workbook_path, issues, extra)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"工作簿: {workbook_path}")
    print("四表来源行数: " + ", ".join(
        f"{name}={row_accounting[name]['source_rows']}" for name in SHEET_ORDER
    ))
    print("问题数量: " + str(len(issues.issues)))
    if issues.issues:
        print("问题代码计数: " + json.dumps(issues.counts(), ensure_ascii=False))
    print(
        "不可用金额单元格: "
        + str(report["amount_summary"]["unusable_amount_cells"]["total"])
        + "  完整金额: "
        + json.dumps(report["amount_summary"]["complete_totals_cents"], ensure_ascii=False)
    )
    print(f"金额勾稽状态: {report['reconciliation']['status']}")
    print(f"结果: {report['result']}")
    print(f"报告: {report_path}")
    return 1 if issues.issues else 0


if __name__ == "__main__":
    sys.exit(main())
