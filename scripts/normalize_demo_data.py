#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-004 开发态标准化核心：四表固定字段转换、逐单元格来源与转换勾稽。

本模块只提供 Python API，**不提供面向业务批次的 CLI**，也不写回工作簿、不创建批次、不代签批准：

    normalize_workbook(workbook_path: Path, quality_report: dict) -> dict

转换口径（与冻结 checker 一致，复用其解析函数与字段定义，不另造宽松解析）：
  - 非空文本原样保留（不去空格、不改大小写、不合并名称、不猜补前导零）；
  - ap_date / payment_date 标准值为 YYYY-MM-DD 字符串，原生日期与午夜日期时间可无损转换；
  - payable_amount / amount / allocated_amount 改为 *_cents，值为 Python int（非 bool），
    标准数据中不保留同名的“元”字段，原值保存在来源信息中；
  - 不排序、不重编号、不合并业务行、不补造主键或分摊；完全空白行单独记录原 Excel 行号。

异常类型：
  NormalizationBlocked  输入在“可转换”前提上不成立（报告不可用、质量未通过、报告与输入不匹配、
                        勾稽未评估等）——不转换、不产出标准数据；
  NormalizationError    运行／一致性错误（文件读取、字段解析失败、表头与报告列位置不一致、
                        转换后哈希变化、勾稽不成立等）——停止该输入，不返回成功结果。

开发边界：本模块是 DEVELOPMENT_TEST_ONLY，尚未接入任何业务批次，也不构成 Gate 1／Gate 2 批准。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CHECKER_PATH = SCRIPTS_DIR / "check_demo_data.py"
RECEIVER_PATH = SCRIPTS_DIR / "receive_demo_batch.py"
SPEC_PATH = PROJECT_ROOT / "docs" / "SPEC_V1.md"

NORMALIZATION_VERSION = "TASK-004-normalized-1.1"
MODE = "DEVELOPMENT_TEST_ONLY"

FIXED_SHEETS = ("suppliers", "payables", "payments", "allocations")
ROW_FIELDS = ("source_rows", "accepted_rows", "blocked_rows", "blank_rows")

SCOPE_LIMITS = [
    "本结果是开发态标准化测试产物，未接入任何业务批次，也不构成 Gate 1／Gate 2 批准。",
    "只转换四张固定工作表的固定字段；额外工作表与额外列只登记，不擅自映射。",
    "来源为 openpyxl 解码值；原始 Excel 字节副本仍是权威原始载体，JSON 不声称能完整还原工作簿。",
    "不宣称真实性、全部业务完整性或特定 ERP 模板兼容性已经验证。",
    "不计算规则命中、超付、重复足额或损失；完整业务质量核验仍由冻结 checker 承担。",
]


class NormalizationBlocked(Exception):
    """输入不满足可转换前提（质量未通过、报告不可用或与输入不匹配）。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


class NormalizationError(Exception):
    """运行或一致性错误（读取、解析、列位置、哈希、勾稽）。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


# ---------------------------------------------------------------------------
# 只读复用冻结脚本（不修改旧文件，只导入）
# ---------------------------------------------------------------------------


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - 环境异常
        raise NormalizationError(f"无法加载只读脚本：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = _load_module(CHECKER_PATH, "frozen_check_demo_data")
RECEIVER = _load_module(RECEIVER_PATH, "frozen_receive_demo_batch")

AMOUNT_FIELDS = {
    sheet: tuple(
        field for field, kind in CHECKER.FIELD_SPEC[sheet].items() if kind == CHECKER.AMOUNT_REQUIRED
    )
    for sheet in FIXED_SHEETS
}
DATE_FIELDS = {
    sheet: tuple(
        field for field, kind in CHECKER.FIELD_SPEC[sheet].items() if kind == CHECKER.DATE_REQUIRED
    )
    for sheet in FIXED_SHEETS
}
TARGET_AMOUNT_FIELD = {field: f"{field}_cents" for sheet in FIXED_SHEETS for field in AMOUNT_FIELDS[sheet]}


def read_file_bytes(path: Path) -> bytes:
    """读取文件字节。单独成函数便于在内存中模拟转换后的哈希读取失败。"""
    return path.read_bytes()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(read_file_bytes(path)).hexdigest()


def frozen_checker_sha256() -> str:
    return sha256_file(CHECKER_PATH)


def spec_sha256() -> str:
    return sha256_file(SPEC_PATH)


# ---------------------------------------------------------------------------
# 前提检查
# ---------------------------------------------------------------------------


def _get_required(mapping, key: str, path: str):
    if not isinstance(mapping, dict) or key not in mapping:
        raise NormalizationBlocked(f"报告字段 {path} 缺失或父级不是对象")
    return mapping[key]


def _as_object(value, path: str) -> dict:
    if not isinstance(value, dict):
        raise NormalizationBlocked(f"报告字段 {path} 必须是对象，实际 {type(value).__name__}")
    return value


def _as_int(value, path: str) -> int:
    """本次可转换前提下的整数校验；bool 不算整数，null 不接受。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise NormalizationBlocked(
            f"报告字段 {path} 必须是整数，实际 {type(value).__name__}（值 {value!r}）"
        )
    return value


def _check_consumed_report_fields(quality_report: dict) -> None:
    """补查接收器 validate_report 未覆盖、而本层实际消费的报告字段。

    只看本层用到的字段与嵌套类型；缺失或类型不符一律让 NormalizationBlocked 给出字段路径，
    不抛裸 KeyError／AttributeError，也不用默认空对象或默认零绕过核对。
    """
    amount_summary = _as_object(_get_required(quality_report, "amount_summary", "amount_summary"), "amount_summary")
    groups = _as_object(
        _get_required(amount_summary, "payments_by_type_and_status", "amount_summary.payments_by_type_and_status"),
        "amount_summary.payments_by_type_and_status",
    )
    for key, entry in groups.items():
        entry_path = f"amount_summary.payments_by_type_and_status[{key!r}]"
        entry = _as_object(entry, entry_path)
        for field in ("count", "known_valid_amount_cents", "complete_amount_cents"):
            _as_int(
                _get_required(entry, field, f"{entry_path}.{field}"),
                f"{entry_path}.{field}",
            )

    reconciliation = _as_object(
        _get_required(quality_report, "reconciliation", "reconciliation"), "reconciliation"
    )
    complete = _as_object(
        _get_required(reconciliation, "complete_totals_cents", "reconciliation.complete_totals_cents"),
        "reconciliation.complete_totals_cents",
    )
    for field in ("master_net", "known_payable_link_net", "missing_payable_link_net"):
        _as_int(
            _get_required(complete, field, f"reconciliation.complete_totals_cents.{field}"),
            f"reconciliation.complete_totals_cents.{field}",
        )

    diagnostics = _as_object(
        _get_required(
            reconciliation,
            "diagnostic_known_valid_subtotals_cents",
            "reconciliation.diagnostic_known_valid_subtotals_cents",
        ),
        "reconciliation.diagnostic_known_valid_subtotals_cents",
    )
    for field in ("known_payable_link_net", "missing_payable_link_net"):
        _as_int(
            _get_required(
                diagnostics, field, f"reconciliation.diagnostic_known_valid_subtotals_cents.{field}"
            ),
            f"reconciliation.diagnostic_known_valid_subtotals_cents.{field}",
        )
    detail = _as_object(
        _get_required(
            diagnostics,
            "missing_payable_link_detail",
            "reconciliation.diagnostic_known_valid_subtotals_cents.missing_payable_link_detail",
        ),
        "reconciliation.diagnostic_known_valid_subtotals_cents.missing_payable_link_detail",
    )
    for field in ("empty_ap_id", "ap_id_not_in_ledger"):
        _as_int(
            _get_required(
                detail,
                field,
                "reconciliation.diagnostic_known_valid_subtotals_cents.missing_payable_link_detail."
                f"{field}",
            ),
            "reconciliation.diagnostic_known_valid_subtotals_cents.missing_payable_link_detail."
            f"{field}",
        )


# ---------------------------------------------------------------------------
# 文件操作边界：统一转成 NormalizationError，并保留阶段、路径与原异常
# ---------------------------------------------------------------------------


def _file_error(stage: str, path: Path, exc: BaseException) -> NormalizationError:
    return NormalizationError(
        f"[{stage}] 无法读取文件 {path}：{type(exc).__name__}: {exc}",
        [f"阶段={stage}", f"路径={path}", f"原始异常={type(exc).__name__}: {exc}"],
    )


def _require_convertible(quality_report, workbook_sha256: str, checker_sha256: str) -> dict:
    """核对“可转换”前提；不满足则抛 NormalizationBlocked，并以 get 默认值兜底视为不合规。"""
    if not isinstance(quality_report, dict):
        raise NormalizationBlocked(
            f"质量报告必须是可用对象，实际 {type(quality_report).__name__}"
        )
    problems = RECEIVER.validate_report(quality_report)
    if problems:
        raise NormalizationBlocked("质量报告结构无效，不能作为转换依据", problems)

    if quality_report.get("result") != "pass":
        raise NormalizationBlocked(f"质量检查结果不是 pass：{quality_report.get('result')!r}")
    issues = quality_report.get("issues")
    if not isinstance(issues, list) or issues:
        raise NormalizationBlocked(f"报告存在 {len(issues or [])} 条问题，未标准化")

    report_workbook_sha = (quality_report.get("workbook") or {}).get("sha256")
    if report_workbook_sha != workbook_sha256:
        raise NormalizationBlocked(
            "报告与当前输入不匹配："
            f"report.workbook.sha256={report_workbook_sha} 实际输入={workbook_sha256}"
        )
    report_checker_sha = (quality_report.get("checker") or {}).get("sha256")
    if report_checker_sha != checker_sha256:
        raise NormalizationBlocked(
            f"报告记录的 checker 与冻结版本不一致：report={report_checker_sha} frozen={checker_sha256}"
        )

    reconciliation = quality_report.get("reconciliation")
    if not isinstance(reconciliation, dict) or reconciliation.get("status") != "ASSESSED":
        raise NormalizationBlocked(
            f"报告勾稽不是 ASSESSED：{(reconciliation or {}).get('status')!r}"
        )
    if reconciliation.get("known_plus_missing_equals_master") is not True:
        raise NormalizationBlocked("报告的 known_plus_missing_equals_master 不是 true")

    row_accounting = quality_report.get("row_accounting")
    for sheet in FIXED_SHEETS:
        accounting = row_accounting.get(sheet)
        if not isinstance(accounting, dict):
            raise NormalizationBlocked(f"报告缺少 {sheet} 的行数统计")
        if accounting.get("blocked_rows") not in (0, None):
            raise NormalizationBlocked(f"{sheet} 存在隔离行，未标准化")
        if accounting.get("structural_block") is True:
            raise NormalizationBlocked(f"{sheet} 存在结构阻断，未标准化")
        if accounting.get("accepted_rows") != accounting.get("source_rows"):
            raise NormalizationBlocked(f"{sheet} 接受行数不等于来源业务行数，未标准化")
    _check_consumed_report_fields(quality_report)
    return quality_report


def _mapping_positions(quality_report: dict, sheet: str) -> dict[str, int | None]:
    mapping = quality_report["structure"]["sheet_field_mapping"]
    fields = mapping.get(sheet)
    if not isinstance(fields, dict):
        raise NormalizationBlocked(f"报告缺少 {sheet} 的字段映射")
    return {name: fields.get(name) for name in CHECKER.FIELD_SPEC[sheet]}


# ---------------------------------------------------------------------------
# 单元格原值与来源编码
# ---------------------------------------------------------------------------


def encode_cell_value(cell) -> dict:
    """记录 openpyxl 解码值与可解释的编码方式；不声称是 Excel 原始 XML 字面值或显示格式。

    read_only 模式下空单元格是 EmptyCell，可能没有 number_format 等属性，因此一律用 getattr 兜底。
    """
    value = cell.value
    data_type = getattr(cell, "data_type", None)
    number_format = getattr(cell, "number_format", None)
    info: dict = {"excel_data_type": data_type}
    if value is None:
        info.update({"encoding": "empty", "raw_value": None, "python_type": "NoneType"})
    elif data_type == "e":
        info.update({"encoding": "excel_error", "raw_value": str(value), "python_type": type(value).__name__})
    elif data_type == "f":
        info.update({"encoding": "formula", "raw_value": str(value), "python_type": type(value).__name__})
    elif isinstance(value, bool):
        info.update({"encoding": "bool", "raw_value": value, "python_type": "bool"})
    elif isinstance(value, int):
        info.update({"encoding": "int", "raw_value": value, "python_type": "int"})
    elif isinstance(value, float):
        info.update(
            {
                "encoding": "float_repr",
                "raw_value": repr(value),
                "python_type": "float",
                "note": "float 以 repr 字符串记录，不代表 Excel 原始 XML 字面值或显示格式",
            }
        )
    elif isinstance(value, datetime):
        info.update({"encoding": "iso_datetime", "raw_value": value.isoformat(), "python_type": "datetime"})
    elif isinstance(value, date):
        info.update({"encoding": "iso_date", "raw_value": value.isoformat(), "python_type": "date"})
    elif isinstance(value, str):
        info.update({"encoding": "str", "raw_value": value, "python_type": "str"})
    else:  # pragma: no cover - 其余类型按可解释字符串记录
        info.update({"encoding": "other_str", "raw_value": str(value), "python_type": type(value).__name__})
    if isinstance(value, (int, float, date, datetime)) and not isinstance(value, bool):
        info["number_format"] = number_format
    return info


def _standard_value(
    sheet: str, field: str, cell, text: str | None, date_value: date | None, cents: int | None
) -> tuple[str, object]:
    """返回 (目标字段名, 标准值)；金额字段改名为 *_cents 并给出整数分。"""
    if field in AMOUNT_FIELDS[sheet]:
        if cents is None:
            raise NormalizationError(f"{sheet}.{field} 未得到整数分")
        if isinstance(cents, bool) or not isinstance(cents, int):
            raise NormalizationError(f"{sheet}.{field} 的整数分必须是 int（非 bool）")
        return TARGET_AMOUNT_FIELD[field], cents
    if field in DATE_FIELDS[sheet]:
        if date_value is None:
            raise NormalizationError(f"{sheet}.{field} 未得到有效日期")
        return field, date_value.isoformat()
    if text is None:
        return field, None
    return field, text


def _parse_cell(field: str, kind: str, cell) -> tuple[str | None, date | None, int | None]:
    """调用冻结 checker 的解析函数，并检查其错误返回（不无视问题继续）。"""
    if kind == CHECKER.DATE_REQUIRED:
        value, problems, present = CHECKER.parse_date_cell(cell)
        if problems:
            raise NormalizationError(f"日期字段 {field} 解析失败：{problems}")
        if not present:
            raise NormalizationError(f"日期字段 {field} 为空")
        return None, value, None
    if kind == CHECKER.AMOUNT_REQUIRED:
        amount, cents, problems = CHECKER.parse_amount_cell(cell)
        if problems:
            raise NormalizationError(f"金额字段 {field} 解析失败：{problems}")
        return None, None, cents
    text, problems, present = CHECKER.read_text(cell)
    if problems:
        raise NormalizationError(f"文本字段 {field} 读取失败：{problems}")
    if kind == CHECKER.CURRENCY_REQUIRED:
        if text is None:
            raise NormalizationError(f"币种字段 {field} 为空")
        if text != "CNY":
            raise NormalizationError(f"币种字段 {field} 超出本版范围：{text!r}")
    elif kind.startswith(CHECKER.ENUM_REQUIRED):
        allowed = kind.split(":", 1)[1].split("|")
        if text is None:
            raise NormalizationError(f"枚举字段 {field} 为空")
        if text not in allowed:
            raise NormalizationError(f"枚举字段 {field} 取值不在允许集合：{text!r}")
    elif kind == CHECKER.TEXT_REQUIRED and text is None:
        raise NormalizationError(f"必填字段 {field} 为空")
    return text, None, None


# ---------------------------------------------------------------------------
# 主转换
# ---------------------------------------------------------------------------


def _normalize_table(worksheet, sheet: str, quality_report: dict, workbook_sha: str) -> dict:
    header_cells = list(next(worksheet.iter_rows(min_row=1, max_row=1)))
    header_names = [None if CHECKER.cell_is_blank(c.value) else c.value for c in header_cells]
    index_by_column: dict[str, int] = {}
    for position, name in enumerate(header_names):
        if isinstance(name, str) and name not in index_by_column:
            index_by_column[name] = position
    extra_columns = [name for name in header_names if isinstance(name, str) and name not in CHECKER.FIELD_SPEC[sheet]]

    reported = _mapping_positions(quality_report, sheet)
    for field in CHECKER.FIELD_SPEC[sheet]:
        actual = index_by_column.get(field)
        actual_position = None if actual is None else actual + 1
        if actual_position != reported.get(field):
            raise NormalizationError(
                f"{sheet}.{field} 实际列位置 {actual_position} 与报告记录 {reported.get(field)} 不一致"
            )

    records: list[dict] = []
    blank_rows: list[int] = []
    row_number = 1  # 表头占第 1 行；read_only 模式下自行推算行号，不依赖空单元格对象属性
    for row_cells in worksheet.iter_rows(min_row=2):
        row_number += 1
        if all(CHECKER.cell_is_blank(cell.value) for cell in row_cells):
            blank_rows.append(row_number)
            continue
        data: dict = {}
        cells: dict = {}
        for field, kind in CHECKER.FIELD_SPEC[sheet].items():
            position = index_by_column.get(field)
            if position is None or position >= len(row_cells):
                raise NormalizationError(f"{sheet}.{field} 缺少映射列，无法转换")
            cell = row_cells[position]
            text, date_value, cents = _parse_cell(field, kind, cell)
            target_field, standard = _standard_value(sheet, field, cell, text, date_value, cents)
            data[target_field] = standard
            column_letter = get_column_letter(position + 1)
            provenance = encode_cell_value(cell)
            provenance.update(
                {
                    "input_field": field,
                    "column_index": position + 1,
                    "column_letter": column_letter,
                    "cell": f"{column_letter}{row_number}",
                    "target_field": target_field,
                    "standard_value": standard,
                }
            )
            cells[field] = provenance
        records.append(
            {
                "data": data,
                "source": {"workbook_sha256": workbook_sha, "sheet": sheet, "excel_row": row_number},
                "cells": cells,
            }
        )

    return {
        "records": records,
        "blank_rows": blank_rows,
        "extra_columns": extra_columns,
        "source_rows": len(records) + 0,
    }


def _sum_field(records: list[dict], field: str) -> int:
    total = 0
    for record in records:
        value = record["data"].get(field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise NormalizationError(f"{field} 的标准值必须是 int，实际 {type(value).__name__}")
        total += value
    return total


def _reconcile(tables: dict, quality_report: dict) -> dict:
    """从标准化记录独立汇总并与本批次 checker 报告对照；不一致即报错。"""
    differences: list[str] = []
    report_amounts = quality_report["amount_summary"]["complete_totals_cents"]
    diagnostics = quality_report["reconciliation"]["diagnostic_known_valid_subtotals_cents"]

    table_totals: dict[str, dict] = {}
    for sheet, field, report_key in (
        ("payables", "payable_amount_cents", "payables_payable_amount"),
        ("payments", "amount_cents", "payments_amount"),
        ("allocations", "allocated_amount_cents", "allocations_allocated_amount"),
    ):
        normalized = _sum_field(tables[sheet]["records"], field)
        reported = report_amounts.get(report_key)
        equal = normalized == reported
        table_totals[report_key] = {"normalized": normalized, "report": reported, "equal": equal}
        if not equal:
            differences.append(f"{report_key} 标准化 {normalized} 分 != 报告 {reported} 分")

    # 行数：来源业务行数 = 标准化行数 + 隔离行数（成功时隔离为 0），并与报告接受行数一致
    row_accounting: dict[str, dict] = {}
    for sheet in FIXED_SHEETS:
        accounting = quality_report["row_accounting"][sheet]
        normalized_rows = len(tables[sheet]["records"])
        blank_rows = len(tables[sheet]["blank_rows"])
        if normalized_rows != accounting.get("accepted_rows") or normalized_rows != accounting.get("source_rows"):
            differences.append(
                f"{sheet} 标准化行数 {normalized_rows} 与报告 source/accepted "
                f"{accounting.get('source_rows')}/{accounting.get('accepted_rows')} 不一致"
            )
        if blank_rows != accounting.get("blank_rows"):
            differences.append(f"{sheet} 空白行数 {blank_rows} != 报告 {accounting.get('blank_rows')}")
        row_accounting[sheet] = {
            "source_rows": accounting.get("source_rows"),
            "normalized_rows": normalized_rows,
            "quarantined_rows": 0,
            "blank_rows": blank_rows,
            "report_accepted_rows": accounting.get("accepted_rows"),
        }

    # 从标准化付款记录独立形成类型／状态分组
    payments_by_type_status: dict[str, dict] = {}
    for record in tables["payments"]["records"]:
        key = f"{record['data'].get('transaction_type')}/{record['data'].get('settlement_status')}"
        entry = payments_by_type_status.setdefault(key, {"count": 0, "amount_cents": 0})
        entry["count"] += 1
        entry["amount_cents"] += record["data"]["amount_cents"]

    # 付款／退款按类型与状态：与报告分组**双向**对照（含报告漏项与多项）
    report_groups = quality_report["amount_summary"]["payments_by_type_and_status"]
    missing_groups = sorted(set(payments_by_type_status) - set(report_groups))
    extra_groups = sorted(set(report_groups) - set(payments_by_type_status))
    if missing_groups:
        differences.append(f"报告漏掉实际付款分组：{missing_groups}")
    if extra_groups:
        differences.append(f"报告多出没有实际记录的分组：{extra_groups}")
    for key in sorted(set(payments_by_type_status) & set(report_groups)):
        normalized = payments_by_type_status[key]
        reported = report_groups[key]
        if normalized["count"] != reported["count"]:
            differences.append(f"分组 {key} 数量 {normalized['count']} != 报告 {reported['count']}")
        if normalized["amount_cents"] != reported["known_valid_amount_cents"]:
            differences.append(
                f"分组 {key} 已知金额 {normalized['amount_cents']} != 报告 {reported['known_valid_amount_cents']}"
            )
        if normalized["amount_cents"] != reported["complete_amount_cents"]:
            differences.append(
                f"分组 {key} 完整金额 {normalized['amount_cents']} != 报告 {reported['complete_amount_cents']}"
            )

    # 每笔主表金额 = 其全部分摊之和
    payment_by_id: dict[str, dict] = {}
    for record in tables["payments"]["records"]:
        payment_by_id[record["data"]["payment_id"]] = record
    allocations_by_payment: dict[str, int] = {}
    for record in tables["allocations"]["records"]:
        payment_id = record["data"]["payment_id"]
        allocations_by_payment[payment_id] = allocations_by_payment.get(payment_id, 0) + record["data"][
            "allocated_amount_cents"
        ]
    for payment_id, record in payment_by_id.items():
        total = allocations_by_payment.get(payment_id, 0)
        if total != record["data"]["amount_cents"]:
            differences.append(
                f"付款 {payment_id} 金额 {record['data']['amount_cents']} 分 != 分摊合计 {total} 分"
            )

    # 已结算主表总额 = 对应分摊总额
    settled_pay_total = 0
    settled_refund_total = 0
    settled_pay_allocation_total = 0
    settled_refund_allocation_total = 0
    known_net = 0
    missing_empty_net = 0
    missing_unknown_net = 0
    payable_ids = {record["data"]["ap_id"] for record in tables["payables"]["records"]}
    for record in tables["payments"]["records"]:
        data = record["data"]
        if data.get("settlement_status") != "SETTLED":
            continue
        if data.get("transaction_type") == "PAY":
            settled_pay_total += data["amount_cents"]
        else:
            settled_refund_total += data["amount_cents"]
    for record in tables["allocations"]["records"]:
        data = record["data"]
        payment = payment_by_id.get(data["payment_id"])
        if payment is None or payment["data"].get("settlement_status") != "SETTLED":
            continue
        sign = 1 if payment["data"].get("transaction_type") == "PAY" else -1
        if sign == 1:
            settled_pay_allocation_total += data["allocated_amount_cents"]
        else:
            settled_refund_allocation_total += data["allocated_amount_cents"]
        ap_id = data.get("ap_id")
        if not ap_id:
            missing_empty_net += sign * data["allocated_amount_cents"]
        elif ap_id not in payable_ids:
            missing_unknown_net += sign * data["allocated_amount_cents"]
        else:
            known_net += sign * data["allocated_amount_cents"]

    master_net = settled_pay_total - settled_refund_total
    missing_net = missing_empty_net + missing_unknown_net
    # 对照报告**完整净额**三项（不能只靠 known_plus_missing_equals_master 或诊断小计）
    complete_totals = quality_report["reconciliation"]["complete_totals_cents"]
    if master_net != complete_totals["master_net"]:
        differences.append(
            f"完整净额 master_net：标准化 {master_net} != 报告 {complete_totals['master_net']}"
        )
    if known_net != complete_totals["known_payable_link_net"]:
        differences.append(
            "完整净额 known_payable_link_net："
            f"标准化 {known_net} != 报告 {complete_totals['known_payable_link_net']}"
        )
    if missing_net != complete_totals["missing_payable_link_net"]:
        differences.append(
            "完整净额 missing_payable_link_net："
            f"标准化 {missing_net} != 报告 {complete_totals['missing_payable_link_net']}"
        )
    checks = {
        "settled_pay_master_equals_allocation": settled_pay_total == settled_pay_allocation_total,
        "settled_refund_master_equals_allocation": settled_refund_total == settled_refund_allocation_total,
        "master_net_equals_known_plus_missing": master_net == known_net + missing_net,
        "known_net_equals_report": known_net == diagnostics.get("known_payable_link_net"),
        "missing_net_equals_report": missing_net == diagnostics.get("missing_payable_link_net"),
        "empty_ap_id_net_equals_report": missing_empty_net
        == (diagnostics.get("missing_payable_link_detail") or {}).get("empty_ap_id"),
        "unknown_ap_id_net_equals_report": missing_unknown_net
        == (diagnostics.get("missing_payable_link_detail") or {}).get("ap_id_not_in_ledger"),
        "master_net_equals_report_complete": master_net == complete_totals["master_net"],
        "known_net_equals_report_complete": known_net == complete_totals["known_payable_link_net"],
        "missing_net_equals_report_complete": missing_net == complete_totals["missing_payable_link_net"],
        "payment_groups_match_report_keys": not missing_groups and not extra_groups,
    }
    for name, ok in checks.items():
        if not ok:
            differences.append(f"勾稽检查未通过：{name}")

    result = {
        "unit": "cents",
        "table_totals": table_totals,
        "payments_by_type_and_status": {
            key: {"count": value["count"], "amount_cents": value["amount_cents"]}
            for key, value in sorted(payments_by_type_status.items())
        },
        "settled_pay_master_total": settled_pay_total,
        "settled_pay_allocation_total": settled_pay_allocation_total,
        "settled_refund_master_total": settled_refund_total,
        "settled_refund_allocation_total": settled_refund_allocation_total,
        "master_net": master_net,
        "known_payable_link_net": known_net,
        "missing_payable_link_net": missing_net,
        "missing_payable_link_detail": {
            "empty_ap_id": missing_empty_net,
            "ap_id_not_in_ledger": missing_unknown_net,
        },
        "checks": checks,
        "normalized_equals_report": not differences,
    }
    if differences:
        raise NormalizationError("转换勾稽与 checker 报告不一致，未返回标准化结果", differences)
    return result, row_accounting


def normalize_workbook(workbook_path: Path, quality_report: dict) -> dict:
    """把一份合成工作簿的四张固定表转换为确定类型，并记录逐单元格来源与转换勾稽。

    返回 JSON 可序列化字典；不写回工作簿、不创建批次、不代签批准。
    前提不满足抛 NormalizationBlocked；运行或一致性错误抛 NormalizationError。
    """
    workbook_path = Path(workbook_path)
    if not workbook_path.is_file():
        raise NormalizationError(f"输入文件不存在：{workbook_path}")
    if workbook_path.suffix.lower() != ".xlsx":
        raise NormalizationError(f"输入必须是 .xlsx：{workbook_path}")

    input_sha = None
    try:
        input_sha = sha256_file(workbook_path)
    except Exception as exc:  # noqa: BLE001 - 文件操作边界统一分类，保留阶段与路径
        raise _file_error("read_input_hash", workbook_path, exc) from exc
    try:
        checker_sha = frozen_checker_sha256()
    except Exception as exc:  # noqa: BLE001
        raise _file_error("read_checker_hash", CHECKER_PATH, exc) from exc
    _require_convertible(quality_report, input_sha, checker_sha)
    try:
        spec_hash = spec_sha256()
    except Exception as exc:  # noqa: BLE001
        raise _file_error("read_spec_hash", SPEC_PATH, exc) from exc

    try:
        workbook = load_workbook(workbook_path, data_only=False, read_only=True)
    except Exception as exc:  # noqa: BLE001 - 打开工作簿失败按运行错误分类
        raise _file_error("open_workbook", workbook_path, exc) from exc
    tables: dict[str, dict] = {}
    try:
        sheets_found = list(workbook.sheetnames)
        for sheet in FIXED_SHEETS:
            if sheet not in sheets_found:
                raise NormalizationBlocked(f"输入缺少工作表：{sheet}")
            tables[sheet] = _normalize_table(workbook[sheet], sheet, quality_report, input_sha)
    finally:
        workbook.close()

    amount_reconciliation, row_accounting = _reconcile(tables, quality_report)

    # 转换结束后再核对输入哈希：读取失败、未知或变化都不能返回成功结果
    try:
        after_sha = sha256_file(workbook_path)
    except OSError as exc:
        raise NormalizationError(f"转换后无法读取输入哈希：{type(exc).__name__}: {exc}") from exc
    if after_sha != input_sha:
        raise NormalizationError(
            f"转换期间输入文件发生变化：before={input_sha} after={after_sha}"
        )

    result = {
        "normalization_version": NORMALIZATION_VERSION,
        "mode": MODE,
        "next_step_allowed": False,
        "source": {
            "input_path": str(workbook_path),
            "input_sha256": input_sha,
            "checker_path": "scripts/check_demo_data.py",
            "checker_sha256": checker_sha,
            "spec_path": "docs/SPEC_V1.md",
            "spec_sha256": spec_hash,
            "path_note": "路径只是附加信息，来源身份以字节哈希为准",
        },
        "quality_report": {
            "result": quality_report.get("result"),
            "issue_counts_by_code": quality_report.get("issue_counts_by_code", {}),
            "report_workbook_sha256": (quality_report.get("workbook") or {}).get("sha256"),
            "report_checker_sha256": (quality_report.get("checker") or {}).get("sha256"),
            "reconciliation_status": quality_report["reconciliation"].get("status"),
        },
        "tables": {
            sheet: {
                "records": tables[sheet]["records"],
                "blank_rows": tables[sheet]["blank_rows"],
                "extra_columns": tables[sheet]["extra_columns"],
            }
            for sheet in FIXED_SHEETS
        },
        "blank_rows": {sheet: tables[sheet]["blank_rows"] for sheet in FIXED_SHEETS},
        "row_accounting": row_accounting,
        "amount_reconciliation": amount_reconciliation,
        "extra_sheets": [name for name in sheets_found if name not in FIXED_SHEETS],
        "scope_limits": SCOPE_LIMITS,
    }

    # JSON 必须可序列化且不含 NaN／Infinity（不使用 default=str 兜底串化）
    try:
        json.dumps(result, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise NormalizationError(f"标准化结果不是合法 JSON：{type(exc).__name__}: {exc}") from exc
    return result
