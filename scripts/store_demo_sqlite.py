#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-005 开发态 SQLite 装载核心：把标准化结果装入新数据库，往返核对并用 SQL 独立勾稽。

本模块只提供 Python API，**不提供面向业务批次的 CLI**，也不重跑标准化、不写回 Excel、不代签批准：

    load_normalized_to_sqlite(normalized: dict, database_path: Path) -> dict

流程：前提检查（装载阻断）→ 路径检查（只允许 data/sqlite_tests 下的新文件）→
在暂存库上建空 schema → 单事务装载业务表／来源记录／运行元数据 → 从数据库实际读取完成
数量、金额、逐笔分摊、已结算总额、净额、PRAGMA 检查与往返重建核对 → 提交、关闭、
更名为目标文件并记录最终字节哈希 → 只有全部成功才返回 DEV_SQLITE_VERIFIED。

异常类型：
  SqliteLoadBlocked  输入不满足装载前提（版本／模式／质量结果／结构／字段类型／来源契约），
                     或目标路径越界、已存在等**写入前**拒绝；不建库、不返回成功报告。
  SqliteLoadError    文件、数据库约束或一致性运行错误，保留阶段、路径与原始原因；
                     数据事务回滚，返回失败现场，不返回成功报告。

开发边界：本模块是 DEVELOPMENT_TEST_ONLY，不接入正式业务流程，不建立契约或批准命令，
入库通过不表示没有业务线索，也不是审计结论。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from openpyxl.utils import get_column_letter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = PROJECT_ROOT / "sql"
SCHEMA_PATH = SQL_DIR / "demo_schema.sql"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
NORMALIZER_PATH = SCRIPTS_DIR / "normalize_demo_data.py"
CHECKER_PATH = SCRIPTS_DIR / "check_demo_data.py"
RECEIVER_PATH = SCRIPTS_DIR / "receive_demo_batch.py"
SPEC_PATH = PROJECT_ROOT / "docs" / "SPEC_V1.md"
CONTRACT_PATH = PROJECT_ROOT / "docs" / "AUDIT_CONTRACT_DRAFT.md"
SQLITE_TESTS_ROOT = (PROJECT_ROOT / "data" / "sqlite_tests").resolve()

STORE_VERSION = "TASK-005-sqlite-load-1.2"
SCHEMA_VERSION = "demo-schema-1.0"
EXPECTED_NORMALIZATION_VERSION = "TASK-004-normalized-1.1"
VERIFIED_STATUS = "DEV_SQLITE_VERIFIED"
MODE = "DEVELOPMENT_TEST_ONLY"

BUSINESS_TABLES = ("suppliers", "payables", "payments", "allocations")
# 标准化 data 的固定字段（金额字段已改名并统一为整数分）
BUSINESS_FIELDS = {
    "suppliers": ("supplier_id", "supplier_name"),
    "payables": ("ap_id", "ap_number", "supplier_id", "ap_date", "payable_amount_cents", "currency"),
    "payments": (
        "payment_id", "transaction_type", "original_payment_id", "payee_supplier_id",
        "payment_date", "amount_cents", "currency", "settlement_status", "bank_reference",
    ),
    "allocations": ("allocation_id", "payment_id", "ap_id", "allocated_amount_cents", "original_allocation_id"),
}
# 标准化 cells 的固定输入字段（与 BUSINESS_FIELDS 的目标字段对应）
INPUT_FIELDS = {
    "suppliers": ("supplier_id", "supplier_name"),
    "payables": ("ap_id", "ap_number", "supplier_id", "ap_date", "payable_amount", "currency"),
    "payments": (
        "payment_id", "transaction_type", "original_payment_id", "payee_supplier_id",
        "payment_date", "amount", "currency", "settlement_status", "bank_reference",
    ),
    "allocations": ("allocation_id", "payment_id", "ap_id", "allocated_amount", "original_allocation_id"),
}
TARGET_FIELD = {
    "payable_amount": "payable_amount_cents",
    "amount": "amount_cents",
    "allocated_amount": "allocated_amount_cents",
}
PRIMARY_KEY = {
    "suppliers": "supplier_id",
    "payables": "ap_id",
    "payments": "payment_id",
    "allocations": "allocation_id",
}
AMOUNT_FIELDS = {
    "suppliers": (),
    "payables": "payable_amount_cents",
    "payments": "amount_cents",
    "allocations": "allocated_amount_cents",
}
DATE_FIELDS = {"suppliers": (), "payables": "ap_date", "payments": "payment_date", "allocations": ()}
NULLABLE_TEXT = {"original_payment_id", "bank_reference", "ap_id", "original_allocation_id"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_SQLITE_INTEGER = 2**63 - 1
# 冻结标准化格式中每个固定字段的 cells 至少包含这些键（raw_value 必须存在，合法空原值 None 与缺键不同）
CELL_REQUIRED_KEYS = (
    "excel_data_type",
    "encoding",
    "raw_value",
    "python_type",
    "input_field",
    "column_index",
    "column_letter",
    "cell",
    "target_field",
    "standard_value",
)
ALLOWED_EXCEL_DATA_TYPES = ("s", "n", "d", "b", "e", "f")
ALLOWED_ENCODINGS = (
    "empty",
    "str",
    "int",
    "float_repr",
    "iso_date",
    "iso_datetime",
    "bool",
    "excel_error",
    "formula",
    "other_str",
)


class SqliteLoadBlocked(Exception):
    """输入不满足装载前提，或目标路径在写入前被拒绝。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


class SqliteLoadError(Exception):
    """文件、数据库约束或一致性运行错误，保留阶段、路径与原始异常。

    是否已回滚**取决于失败发生的时点**：提交前失败（建 schema／写入／同一事务内核对）
    数据事务已回滚，暂存库保留空 schema；提交后失败（关闭／暂存哈希／发布／最终哈希）
    **不表示已回滚**，暂存库可能保留已提交数据，目标文件状态以实际磁盘为准。
    """

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


# ---------------------------------------------------------------------------
# 文件与路径边界
# ---------------------------------------------------------------------------


def read_file_bytes(path: Path) -> bytes:
    """读取文件字节。单独成函数便于在内存中模拟文件读取失败。"""
    return path.read_bytes()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(read_file_bytes(path)).hexdigest()


def _file_error(stage: str, path: Path, exc: BaseException) -> SqliteLoadError:
    return SqliteLoadError(
        f"[{stage}] 无法读取文件 {path}：{type(exc).__name__}: {exc}",
        [f"阶段={stage}", f"路径={path}", f"原始异常={type(exc).__name__}: {exc}"],
    )


def resolve_database_path(database_path) -> Path:
    """只接受 data/sqlite_tests 内**尚不存在**的新文件；拒绝越界、目录本身与已存在目标。"""
    raw = Path(database_path)
    target = raw.expanduser()
    target = target.resolve() if target.is_absolute() else (Path.cwd() / target).resolve()
    try:
        target.relative_to(SQLITE_TESTS_ROOT)
    except ValueError:
        raise SqliteLoadBlocked(f"数据库路径必须位于 {SQLITE_TESTS_ROOT} 之内：{target}")
    if target == SQLITE_TESTS_ROOT:
        raise SqliteLoadBlocked("数据库路径不能是 data/sqlite_tests 目录本身")
    if target.exists():
        raise SqliteLoadBlocked(f"数据库路径已存在，拒绝覆盖：{target}")
    if not target.parent.is_dir():
        raise SqliteLoadBlocked(f"数据库父目录不存在：{target.parent}")
    return target


# ---------------------------------------------------------------------------
# 前提检查：装载所需的标准数据契约
# ---------------------------------------------------------------------------


def _require(condition: bool, path: str, reason: str) -> None:
    if not condition:
        raise SqliteLoadBlocked(f"标准化结果字段 {path} 不可用：{reason}")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def payload_sha256(normalized: dict) -> str:
    """对完整传入对象按固定 JSON 规则序列化后求哈希（对象规范化指纹，不是某个 JSON 文件的字节哈希）。"""
    try:
        canonical = json.dumps(
            normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise SqliteLoadBlocked(f"标准化结果不是合法 JSON：{type(exc).__name__}: {exc}")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_record(sheet: str, index: int, record: dict, input_sha: str) -> None:
    path = f"tables.{sheet}.records[{index}]"
    _require(isinstance(record, dict), path, f"必须是对象，实际 {type(record).__name__}")
    for part in ("data", "source", "cells"):
        _require(isinstance(record.get(part), dict), f"{path}.{part}", "必须是对象")

    data = record["data"]
    expected = BUSINESS_FIELDS[sheet]
    _require(
        set(data) == set(expected),
        f"{path}.data",
        f"业务字段必须与本版固定字段一致，实际 {sorted(data)}",
    )
    for field in expected:
        value = data[field]
        field_path = f"{path}.data.{field}"
        if field in AMOUNT_FIELDS[sheet]:
            _require(_is_int(value), field_path, f"金额必须是整数分（非 bool），实际 {type(value).__name__}")
            _require(value > 0, field_path, f"金额必须严格为正，实际 {value}")
            _require(value <= MAX_SQLITE_INTEGER, field_path, "整数分超出 SQLite 整数能力")
        elif field in DATE_FIELDS.get(sheet, ()):
            _require(isinstance(value, str) and bool(ISO_DATE.match(value)), field_path,
                     f"日期必须是 ISO 日期字符串，实际 {value!r}")
        elif field in NULLABLE_TEXT:
            _require(value is None or isinstance(value, str), field_path,
                     f"可空文本只接受 str 或 None，实际 {type(value).__name__}")
        else:
            _require(isinstance(value, str), field_path, f"文本必须是 str，实际 {type(value).__name__}")
            _require(value != "", field_path, "必填文本不能为空字符串")

    source = record["source"]
    _require(source.get("workbook_sha256") == input_sha, f"{path}.source.workbook_sha256",
             f"必须与本结果来源哈希一致：{source.get('workbook_sha256')} != {input_sha}")
    _require(source.get("sheet") == sheet, f"{path}.source.sheet", f"必须是 {sheet}")
    _require(_is_int(source.get("excel_row")) and source["excel_row"] >= 2, f"{path}.source.excel_row",
             f"原 Excel 行号必须是 >=2 的整数，实际 {source.get('excel_row')!r}")

    cells = record["cells"]
    excel_row = source["excel_row"]
    for field in INPUT_FIELDS[sheet]:
        target = TARGET_FIELD.get(field, field)
        cell_path = f"{path}.cells.{field}"
        cell = cells.get(field)
        _require(isinstance(cell, dict), cell_path, "缺少该固定字段的单元格来源")
        # 必需来源字段：raw_value 的键必须存在（值可以是 None），缺键与合法空原值不同
        missing_keys = [key for key in CELL_REQUIRED_KEYS if key not in cell]
        _require(not missing_keys, cell_path, f"缺少必需来源字段：{missing_keys}")
        _require(cell["input_field"] == field, f"{cell_path}.input_field", f"必须是 {field}")
        _require(cell["target_field"] == target, f"{cell_path}.target_field", f"必须是 {target}")
        _require(cell["standard_value"] == data[target], f"{cell_path}.standard_value",
                 f"必须与 data.{target} 一致")
        _require(
            isinstance(cell["column_index"], int) and not isinstance(cell["column_index"], bool)
            and cell["column_index"] >= 1,
            f"{cell_path}.column_index",
            f"必须是 >=1 的整数（非 bool），实际 {cell['column_index']!r}",
        )
        require_letter = get_column_letter(cell["column_index"])
        _require(cell["column_letter"] == require_letter, f"{cell_path}.column_letter",
                 f"必须与列号 {cell['column_index']} 对应（应为 {require_letter}），实际 {cell['column_letter']!r}")
        expected_coordinate = f"{require_letter}{excel_row}"
        _require(cell["cell"] == expected_coordinate, f"{cell_path}.cell",
                 f"必须与本行坐标一致（应为 {expected_coordinate}），实际 {cell['cell']!r}")
        _require(isinstance(cell["python_type"], str) and cell["python_type"] != "",
                 f"{cell_path}.python_type", f"必须是非空字符串，实际 {cell['python_type']!r}")
        _require(cell["encoding"] in ALLOWED_ENCODINGS, f"{cell_path}.encoding",
                 f"必须是已验收编码之一，实际 {cell['encoding']!r}")
        _require(cell["excel_data_type"] in ALLOWED_EXCEL_DATA_TYPES, f"{cell_path}.excel_data_type",
                 f"必须是已验收 data_type 之一，实际 {cell['excel_data_type']!r}")


def require_loadable(normalized) -> dict:
    """检查本层装载所需的标准数据契约；不满足抛 SqliteLoadBlocked。"""
    _require(isinstance(normalized, dict), "normalized", f"必须是对象，实际 {type(normalized).__name__}")
    _require(normalized.get("normalization_version") == EXPECTED_NORMALIZATION_VERSION,
             "normalization_version", f"必须是 {EXPECTED_NORMALIZATION_VERSION}，实际 "
             f"{normalized.get('normalization_version')!r}")
    _require(normalized.get("mode") == MODE, "mode", f"必须是 {MODE}")
    _require(normalized.get("next_step_allowed") is False, "next_step_allowed", "必须是 false")

    quality = normalized.get("quality_report")
    _require(isinstance(quality, dict), "quality_report", "必须是对象")
    _require(quality.get("result") == "pass", "quality_report.result", f"必须是 pass，实际 {quality.get('result')!r}")

    source = normalized.get("source")
    _require(isinstance(source, dict), "source", "必须是对象")
    input_sha = source.get("input_sha256")
    _require(isinstance(input_sha, str) and len(input_sha) == 64, "source.input_sha256", "必须是 64 位哈希")

    reconciliation = normalized.get("amount_reconciliation")
    _require(isinstance(reconciliation, dict), "amount_reconciliation", "必须是对象")
    _require(reconciliation.get("normalized_equals_report") is True,
             "amount_reconciliation.normalized_equals_report", "必须是 true")
    checks = reconciliation.get("checks")
    _require(isinstance(checks, dict) and checks, "amount_reconciliation.checks", "必须是非空对象")
    failed = sorted(name for name, ok in checks.items() if ok is not True)
    _require(not failed, "amount_reconciliation.checks", f"存在未通过项：{failed}")

    tables = normalized.get("tables")
    _require(isinstance(tables, dict), "tables", "必须是对象")
    row_accounting = normalized.get("row_accounting")
    _require(isinstance(row_accounting, dict), "row_accounting", "必须是对象")
    for sheet in BUSINESS_TABLES:
        table = tables.get(sheet)
        _require(isinstance(table, dict), f"tables.{sheet}", "必须是对象")
        records = table.get("records")
        _require(isinstance(records, list), f"tables.{sheet}.records", "必须是列表（缺失不等于空表）")
        _require(isinstance(table.get("blank_rows"), list), f"tables.{sheet}.blank_rows", "必须是列表")
        _require(isinstance(table.get("extra_columns"), list), f"tables.{sheet}.extra_columns", "必须是列表")
        accounting = row_accounting.get(sheet)
        _require(isinstance(accounting, dict), f"row_accounting.{sheet}", "必须是对象")
        _require(accounting.get("normalized_rows") == len(records), f"row_accounting.{sheet}.normalized_rows",
                 f"必须与记录数 {len(records)} 相等")
        for index, record in enumerate(records):
            _check_record(sheet, index, record, input_sha)
    return normalized


# ---------------------------------------------------------------------------
# 数据库写入
# ---------------------------------------------------------------------------


def connect_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path), isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def execute_schema(connection: sqlite3.Connection, schema_sql: str) -> None:
    """建空 schema。executescript 可能提交已有事务，因此在数据事务之前调用。"""
    connection.executescript(schema_sql)


def insert_business_rows(connection: sqlite3.Connection, sheet: str, records: list[dict]) -> None:
    fields = BUSINESS_FIELDS[sheet]
    placeholders = ", ".join("?" for _ in fields)
    columns = ", ".join(fields)
    sql = f"INSERT INTO {sheet} ({columns}) VALUES ({placeholders})"
    for record in records:
        data = record["data"]
        connection.execute(sql, tuple(data[field] for field in fields))


def insert_source_records(connection: sqlite3.Connection, sheet: str, records: list[dict]) -> None:
    sql = (
        "INSERT INTO source_records (table_name, record_id, workbook_sha256, sheet, excel_row, cells_json) "
        "VALUES (?, ?, ?, ?, ?, ?)"
    )
    for record in records:
        source = record["source"]
        record_id = record["data"][PRIMARY_KEY[sheet]]
        cells_json = json.dumps(record["cells"], ensure_ascii=False, sort_keys=True, allow_nan=False)
        connection.execute(
            sql,
            (sheet, record_id, source["workbook_sha256"], source["sheet"], source["excel_row"], cells_json),
        )


def insert_run_metadata(connection: sqlite3.Connection, rows: list[tuple[str, str]]) -> None:
    connection.executemany("INSERT INTO run_metadata (metadata_key, metadata_value) VALUES (?, ?)", rows)


def _json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _metadata_rows(normalized: dict, payload_sha: str, schema_sha: str, store_sha: str) -> list[tuple[str, str]]:
    reconciliation = normalized["amount_reconciliation"]
    context = {
        "normalization_version": normalized["normalization_version"],
        "source": normalized["source"],
        "quality_report": normalized["quality_report"],
        "row_accounting": normalized["row_accounting"],
        "amount_reconciliation": reconciliation,
        "blank_rows": normalized.get("blank_rows", {}),
        "extra_sheets": normalized.get("extra_sheets", []),
        "extra_columns": {
            sheet: normalized["tables"][sheet].get("extra_columns", []) for sheet in BUSINESS_TABLES
        },
        "scope_limits": normalized.get("scope_limits", []),
    }
    return [
        ("schema_version", SCHEMA_VERSION),
        ("store_version", STORE_VERSION),
        ("mode", MODE),
        ("next_step_allowed", "false"),
        ("batch_status", VERIFIED_STATUS),
        ("created_at_utc", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        ("input_sha256", normalized["source"]["input_sha256"]),
        ("normalized_payload_sha256", payload_sha),
        ("normalizer_sha256", sha256_file(NORMALIZER_PATH)),
        ("checker_sha256", sha256_file(CHECKER_PATH)),
        ("receive_script_sha256", sha256_file(RECEIVER_PATH)),
        ("spec_sha256", sha256_file(SPEC_PATH)),
        ("contract_draft_sha256", sha256_file(CONTRACT_PATH)),
        ("store_script_sha256", store_sha),
        ("schema_sha256", schema_sha),
        ("table_row_counts_json", _json_text(
            {sheet: len(normalized["tables"][sheet]["records"]) for sheet in BUSINESS_TABLES}
        )),
        ("normalization_context_json", _json_text(context)),
    ]


# ---------------------------------------------------------------------------
# 独立 SQL 核对与往返
# ---------------------------------------------------------------------------


def _scalar(connection: sqlite3.Connection, sql: str, params: tuple = ()):
    cursor = connection.execute(sql, params)
    row = cursor.fetchone()
    return None if row is None else row[0]


def _business_rows(connection: sqlite3.Connection, sheet: str) -> list[dict]:
    fields = BUSINESS_FIELDS[sheet]
    sql = (
        f"SELECT {', '.join(fields)} FROM {sheet} b "
        "JOIN source_records s ON s.table_name = ? AND s.record_id = "
        f"b.{PRIMARY_KEY[sheet]} ORDER BY s.excel_row"
    )
    cursor = connection.execute(sql, (sheet,))
    return [dict(zip(fields, row)) for row in cursor.fetchall()]


def verify_database(
    connection: sqlite3.Connection, normalized: dict, expected_metadata: list[tuple[str, str]]
) -> dict:
    """从数据库实际读取，完成数量、金额、元数据与往返核对；任何差异抛 SqliteLoadError。

    在**同一未提交事务**内调用：本连接可以读到本事务尚未提交的记录，因此核对失败时仍可回滚。
    """
    differences: list[str] = []

    # 1. 行数与来源记录覆盖
    counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for sheet in BUSINESS_TABLES:
        expected_rows = len(normalized["tables"][sheet]["records"])
        counts[sheet] = _scalar(connection, f"SELECT COUNT(*) FROM {sheet}")
        source_counts[sheet] = _scalar(
            connection, "SELECT COUNT(*) FROM source_records WHERE table_name = ?", (sheet,)
        )
        if counts[sheet] != expected_rows:
            differences.append(f"{sheet} 数据库行数 {counts[sheet]} != 标准化 {expected_rows}")
        if source_counts[sheet] != expected_rows:
            differences.append(f"{sheet} 来源记录数 {source_counts[sheet]} != 标准化 {expected_rows}")
        orphan = _scalar(
            connection,
            f"SELECT COUNT(*) FROM {sheet} b LEFT JOIN source_records s "
            f"ON s.table_name = ? AND s.record_id = b.{PRIMARY_KEY[sheet]} WHERE s.record_id IS NULL",
            (sheet,),
        )
        if orphan:
            differences.append(f"{sheet} 有 {orphan} 行业务数据没有对应来源记录")

    # 2. 三张金额表 SQL 汇总，并与标准化完整金额逐项对照
    reconciliation = normalized["amount_reconciliation"]
    table_totals: dict[str, dict] = {}
    for sheet in ("payables", "payments", "allocations"):
        field = AMOUNT_FIELDS[sheet]
        sql_total = _scalar(connection, f"SELECT SUM({field}) FROM {sheet}")
        sql_total = 0 if sql_total is None else sql_total
        expected = reconciliation["table_totals"][
            {
                "payables": "payables_payable_amount",
                "payments": "payments_amount",
                "allocations": "allocations_allocated_amount",
            }[sheet]
        ]["normalized"]
        table_totals[sheet] = {"sql_sum": sql_total, "normalized": expected, "equal": sql_total == expected}
        if sql_total != expected:
            differences.append(f"{sheet} SQL 合计 {sql_total} 分 != 标准化 {expected} 分")

    # 付款按类型／状态：SQL 分组与标准化分组**双向**比较
    sql_groups = {
        f"{transaction_type}/{settlement_status}": {"count": count, "amount_cents": total}
        for transaction_type, settlement_status, count, total in connection.execute(
            "SELECT transaction_type, settlement_status, COUNT(*), SUM(amount_cents) FROM payments "
            "GROUP BY transaction_type, settlement_status"
        )
    }
    expected_groups = reconciliation["payments_by_type_and_status"]
    for key in sorted(set(sql_groups) | set(expected_groups)):
        sql_group = sql_groups.get(key)
        expected_group = expected_groups.get(key)
        if sql_group is None:
            differences.append(f"SQL 分组缺少实际分组 {key}")
        elif expected_group is None:
            differences.append(f"SQL 分组多出标准化没有的分组 {key}")
        elif sql_group["count"] != expected_group["count"] or sql_group["amount_cents"] != expected_group["amount_cents"]:
            differences.append(f"分组 {key} SQL {sql_group} != 标准化 {expected_group}")

    # 3. 每笔资金事件金额 = 其全部分摊金额之和
    unbalanced = connection.execute(
        "SELECT p.payment_id, p.amount_cents, COALESCE(SUM(a.allocated_amount_cents), 0) "
        "FROM payments p LEFT JOIN allocations a ON a.payment_id = p.payment_id "
        "GROUP BY p.payment_id HAVING p.amount_cents <> COALESCE(SUM(a.allocated_amount_cents), 0)"
    ).fetchall()
    if unbalanced:
        differences.append(f"存在金额与分摊合计不一致的资金事件：{unbalanced}")
    event_balanced = not unbalanced

    # 4. 已结算 PAY／REFUND 主表总额分别等于对应分摊总额
    settled_pay = _scalar(
        connection,
        "SELECT COALESCE(SUM(amount_cents), 0) FROM payments "
        "WHERE settlement_status = 'SETTLED' AND transaction_type = 'PAY'",
    )
    settled_refund = _scalar(
        connection,
        "SELECT COALESCE(SUM(amount_cents), 0) FROM payments "
        "WHERE settlement_status = 'SETTLED' AND transaction_type = 'REFUND'",
    )
    settled_pay_alloc = _scalar(
        connection,
        "SELECT COALESCE(SUM(a.allocated_amount_cents), 0) FROM allocations a "
        "JOIN payments p ON p.payment_id = a.payment_id "
        "WHERE p.settlement_status = 'SETTLED' AND p.transaction_type = 'PAY'",
    )
    settled_refund_alloc = _scalar(
        connection,
        "SELECT COALESCE(SUM(a.allocated_amount_cents), 0) FROM allocations a "
        "JOIN payments p ON p.payment_id = a.payment_id "
        "WHERE p.settlement_status = 'SETTLED' AND p.transaction_type = 'REFUND'",
    )
    if settled_pay != reconciliation["settled_pay_master_total"]:
        differences.append(f"已结算 PAY 总额 SQL {settled_pay} != 标准化 {reconciliation['settled_pay_master_total']}")
    if settled_refund != reconciliation["settled_refund_master_total"]:
        differences.append(
            f"已结算 REFUND 总额 SQL {settled_refund} != 标准化 {reconciliation['settled_refund_master_total']}"
        )
    if settled_pay != settled_pay_alloc:
        differences.append(f"已结算 PAY 主表 {settled_pay} != 分摊 {settled_pay_alloc}")
    if settled_refund != settled_refund_alloc:
        differences.append(f"已结算 REFUND 主表 {settled_refund} != 分摊 {settled_refund_alloc}")

    # 5. 主表净额 = 已知应付关联净额 + 缺失应付关联净额（缺失再分空 ap_id／台账未找到）
    #    主表资金总额单独从 payments 计算；分摊总额按 allocations 粒度计算，两者不相加
    sign_sql = "CASE WHEN p.transaction_type = 'PAY' THEN 1 ELSE -1 END"
    classification = (
        "CASE WHEN a.ap_id IS NULL OR a.ap_id = '' THEN 'empty_ap_id' "
        "WHEN NOT EXISTS (SELECT 1 FROM payables pa WHERE pa.ap_id = a.ap_id) THEN 'ap_id_not_in_ledger' "
        "ELSE 'known' END"
    )
    net_rows = {
        name: _scalar(
            connection,
            f"SELECT COALESCE(SUM({sign_sql} * a.allocated_amount_cents), 0) FROM allocations a "
            "JOIN payments p ON p.payment_id = a.payment_id "
            f"WHERE p.settlement_status = 'SETTLED' AND {classification} = ?",
            (name,),
        )
        for name in ("empty_ap_id", "ap_id_not_in_ledger", "known")
    }
    empty_ap_net = net_rows["empty_ap_id"]
    unknown_ap_net = net_rows["ap_id_not_in_ledger"]
    known_net = net_rows["known"]
    missing_net = empty_ap_net + unknown_ap_net
    master_net = settled_pay - settled_refund
    net_checks = {
        "master_net_equals_known_plus_missing": master_net == known_net + missing_net,
        "master_net_equals_normalized": master_net == reconciliation["master_net"],
        "known_net_equals_normalized": known_net == reconciliation["known_payable_link_net"],
        "missing_net_equals_normalized": missing_net == reconciliation["missing_payable_link_net"],
        "empty_ap_id_equals_normalized": empty_ap_net == reconciliation["missing_payable_link_detail"]["empty_ap_id"],
        "unknown_ap_id_equals_normalized": unknown_ap_net
        == reconciliation["missing_payable_link_detail"]["ap_id_not_in_ledger"],
    }
    for name, ok in net_checks.items():
        if not ok:
            differences.append(f"净额检查未通过：{name}")

    # 6. PRAGMA 检查（不是审计结论检查）
    foreign_key_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
    integrity = _scalar(connection, "PRAGMA integrity_check")
    if foreign_key_issues:
        differences.append(f"PRAGMA foreign_key_check 报告 {len(foreign_key_issues)} 个问题")
    if integrity != "ok":
        differences.append(f"PRAGMA integrity_check 返回 {integrity!r}")

    # 7. 从业务表与来源记录重建 data／source／cells，逐项与传入记录精确相等
    round_trip_mismatches: list[str] = []
    rebuilt_counts: dict[str, int] = {}
    for sheet in BUSINESS_TABLES:
        rows = _business_rows(connection, sheet)
        rebuilt_counts[sheet] = len(rows)
        expected_records = normalized["tables"][sheet]["records"]
        if len(rows) != len(expected_records):
            round_trip_mismatches.append(f"{sheet} 往返记录数 {len(rows)} != {len(expected_records)}")
            continue
        for expected_record, row in zip(expected_records, rows):
            if row != expected_record["data"]:
                round_trip_mismatches.append(
                    f"{sheet} 第 {expected_record['source']['excel_row']} 行 data 不一致：{row} != {expected_record['data']}"
                )
            source = connection.execute(
                "SELECT workbook_sha256, sheet, excel_row, cells_json FROM source_records "
                "WHERE table_name = ? AND record_id = ?",
                (sheet, expected_record["data"][PRIMARY_KEY[sheet]]),
            ).fetchone()
            if source is None:
                round_trip_mismatches.append(f"{sheet} {expected_record['data'][PRIMARY_KEY[sheet]]} 缺少来源记录")
                continue
            if [source[0], source[1], source[2]] != [
                expected_record["source"]["workbook_sha256"],
                expected_record["source"]["sheet"],
                expected_record["source"]["excel_row"],
            ]:
                round_trip_mismatches.append(
                    f"{sheet} {expected_record['data'][PRIMARY_KEY[sheet]]} 来源字段不一致"
                )
            if json.loads(source[3]) != expected_record["cells"]:
                round_trip_mismatches.append(
                    f"{sheet} {expected_record['data'][PRIMARY_KEY[sheet]]} cells 内容不一致"
                )
    if round_trip_mismatches:
        differences.extend(round_trip_mismatches[:10])

    # 8. 运行元数据：实际查询数据库，并与本次预期（生成一次，不在核对时重新生成）逐项比较
    actual_metadata = dict(
        connection.execute("SELECT metadata_key, metadata_value FROM run_metadata").fetchall()
    )
    expected = dict(expected_metadata)
    missing_keys = sorted(set(expected) - set(actual_metadata))
    extra_keys = sorted(set(actual_metadata) - set(expected))
    if missing_keys:
        differences.append(f"run_metadata 缺少必需键：{missing_keys}")
    if extra_keys:
        differences.append(f"run_metadata 多出预期外的键：{extra_keys}")
    metadata_mismatches: list[str] = []
    for key in sorted(set(expected) & set(actual_metadata)):
        if actual_metadata[key] != expected[key]:
            metadata_mismatches.append(key)
    if metadata_mismatches:
        differences.append(f"run_metadata 实际值与本次预期不一致：{metadata_mismatches[:10]}")
    for key in ("schema_version", "store_version", "mode", "next_step_allowed", "batch_status",
                "input_sha256", "normalized_payload_sha256"):
        if actual_metadata.get(key) != expected.get(key):
            differences.append(
                f"run_metadata.{key} 实际 {actual_metadata.get(key)!r} != 预期 {expected.get(key)!r}"
            )
    context_problems: list[str] = []
    for key in ("table_row_counts_json", "normalization_context_json"):
        raw = actual_metadata.get(key)
        if raw is None:
            context_problems.append(f"{key} 缺失")
            continue
        try:
            actual_value = json.loads(raw)
        except json.JSONDecodeError as exc:
            context_problems.append(f"{key} 不是合法 JSON：{exc}")
            continue
        expected_value = json.loads(expected.get(key, "null"))
        if actual_value != expected_value:
            context_problems.append(f"{key} 结构与本次预期不相等")
    if context_problems:
        differences.extend(f"run_metadata 上下文核验未通过：{item}" for item in context_problems)
    metadata_state = {
        key: actual_metadata.get(key)
        for key in ("schema_version", "store_version", "mode", "next_step_allowed", "batch_status",
                    "input_sha256", "normalized_payload_sha256", "created_at_utc")
    }
    metadata_state["row_count"] = _scalar(connection, "SELECT COUNT(*) FROM run_metadata")

    if differences:
        raise SqliteLoadError("数据库独立核对未通过，装载不成立", differences)

    return {
        "row_counts": counts,
        "source_record_counts": source_counts,
        "table_totals": table_totals,
        "payment_groups": sql_groups,
        "event_allocation_balanced": event_balanced,
        "settled_pay_master_total": settled_pay,
        "settled_pay_allocation_total": settled_pay_alloc,
        "settled_refund_master_total": settled_refund,
        "settled_refund_allocation_total": settled_refund_alloc,
        "master_net": master_net,
        "known_payable_link_net": known_net,
        "missing_payable_link_net": missing_net,
        "missing_payable_link_detail": {
            "empty_ap_id": empty_ap_net,
            "ap_id_not_in_ledger": unknown_ap_net,
        },
        "net_checks": net_checks,
        "foreign_key_check": "clean",
        "integrity_check": integrity,
        "round_trip_records": rebuilt_counts,
        "round_trip_exact": True,
        "run_metadata": metadata_state,
    }


# ---------------------------------------------------------------------------
# 无覆盖发布与失败现场取证
# ---------------------------------------------------------------------------


def pre_publish_hook(target: Path) -> None:
    """发布前钩子（默认无操作）。仅供测试在“核对成功、发布之前”注入故障。"""
    return None


def _publish_conflict(staging: Path, target: Path, exc: BaseException) -> SqliteLoadError:
    return SqliteLoadError(
        f"[publish_database] 目标文件已存在，拒绝覆盖：{target}",
        [
            "阶段=publish_database",
            f"目标路径={target}",
            f"暂存路径={staging}",
            "原因=发布时目标已存在（未覆盖、未删除目标字节）",
            f"原始异常={type(exc).__name__}: {exc}",
        ],
    )


def _copy_no_clobber(staging: Path, target: Path, original: BaseException) -> None:
    try:
        with open(target, "xb") as destination, open(staging, "rb") as source:
            shutil.copyfileobj(source, destination)
    except FileExistsError as exc:
        raise _publish_conflict(staging, target, exc) from exc
    except OSError as exc:
        raise SqliteLoadError(
            f"[publish_database] 无法发布数据库：{type(exc).__name__}: {exc}",
            [
                "阶段=publish_database",
                f"目标路径={target}",
                f"暂存路径={staging}",
                f"硬链接不可用原因={type(original).__name__}: {original}",
                f"原始异常={type(exc).__name__}: {exc}",
            ],
        ) from exc
    os.unlink(staging)


def publish_database(staging: Path, target: Path) -> None:
    """无覆盖发布：遇到已有目标必须失败；绝不覆盖，也绝不先删除目标。

    首选硬链接（Windows NTFS 支持）：目标已存在时抛 FileExistsError，原子且不覆盖既有字节；
    硬链接不可用时回退为独占创建（`open(..., 'xb')`）后复制字节，同样不覆盖。
    """
    pre_publish_hook(target)
    try:
        os.link(staging, target)
    except FileExistsError as exc:
        raise _publish_conflict(staging, target, exc) from exc
    except OSError as exc:
        _copy_no_clobber(staging, target, exc)
        return
    os.unlink(staging)


def row_state(path: Path) -> dict:
    """读取指定数据库六张表的实际数据行数，用于失败现场如实报告。"""
    tables = (*BUSINESS_TABLES, "source_records", "run_metadata")
    if not path.exists():
        return {"exists": False}
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:  # pragma: no cover - 环境异常
        return {"exists": True, "read_error": f"{type(exc).__name__}: {exc}"}
    try:
        return {"exists": True, **{table: _scalar(connection, f"SELECT COUNT(*) FROM {table}") for table in tables}}
    except sqlite3.Error as exc:
        return {"exists": True, "read_error": f"{type(exc).__name__}: {exc}"}
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def load_normalized_to_sqlite(normalized: dict, database_path) -> dict:
    """把标准化结果装入全新 SQLite 数据库并返回本次装载核对报告。

    流程：前提检查 → 路径检查 → 建空 schema → BEGIN → 写入业务／来源／元数据 →
    **在同一未提交事务内**完成数量、金额、元数据与外键／往返核对 → COMMIT →
    **严格关闭（关闭失败即装载失败，不继续哈希或发布）** → 无覆盖发布（目标已存在即失败）
    → 最终文件哈希 → 返回成功报告。

    前提不满足或目标路径越界／已存在抛 SqliteLoadBlocked（写入前拒绝）；
    文件、数据库约束或一致性错误抛 SqliteLoadError，并带上真实失败状态：
    提交前失败时数据事务已回滚（暂存库六表 0 行）；
    提交后失败（含关闭失败）时**不声称已回滚**，如实说明暂存库已含提交数据与目标文件是否存在。
    """
    require_loadable(normalized)
    target = resolve_database_path(database_path)
    try:
        schema_sql = read_file_bytes(SCHEMA_PATH).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise _file_error("read_schema", SCHEMA_PATH, exc) from exc
    try:
        store_sha = sha256_file(Path(__file__).resolve())
        schema_sha = sha256_file(SCHEMA_PATH)
        payload_sha = payload_sha256(normalized)
        metadata_rows = _metadata_rows(normalized, payload_sha, schema_sha, store_sha)
    except SqliteLoadBlocked:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _file_error("compute_hashes", Path(__file__).resolve(), exc) from exc

    staging = target.with_name(target.name + ".staging")
    if staging.exists():
        raise SqliteLoadError(
            f"[prepare_staging] 暂存库已存在，拒绝覆盖：{staging}",
            [f"阶段=prepare_staging", f"路径={staging}", "原因=上一次失败现场仍在"],
        )

    connection = None
    stage = "open_database"
    committed = False
    published = False
    staging_sha = None
    final_sha = None
    rollback_note = None
    close_notes: list[str] = []

    def _close_quietly() -> None:
        """已有错误后的尽力清理：关闭失败只作附记，绝不覆盖最初错误。

        关闭失败时保留连接引用（不丢弃仍需清理的连接），也不把失败说成已成功关闭。
        """
        nonlocal connection
        if connection is None:
            return
        try:
            connection.close()
            connection = None
        except Exception as exc:  # noqa: BLE001 - 只作附记
            close_notes.append(f"清理时关闭连接失败：{type(exc).__name__}: {exc}")

    def _close_strict() -> None:
        """正常流程的关闭必须成功；失败立即中止成功流程，不继续哈希或发布。"""
        nonlocal connection
        if connection is None:
            return
        try:
            connection.close()
        except Exception as exc:  # noqa: BLE001 - 关闭失败即装载失败
            raise SqliteLoadError(
                f"[close_database] 关闭数据库失败：{type(exc).__name__}: {exc}",
                [
                    "阶段=close_database",
                    f"目标路径={target}",
                    f"暂存路径={staging}",
                    f"原始异常={type(exc).__name__}: {exc}",
                ],
            ) from exc
        connection = None

    def _state_notes(extra: list[str]) -> list[str]:
        notes = [
            f"阶段={stage}",
            f"目标路径={target}",
            f"暂存路径={staging}",
            f"数据事务已提交={committed}",
            f"目标文件已发布={published}",
            f"暂存库六表行数={json.dumps(row_state(staging), ensure_ascii=False)}",
            f"目标文件存在={target.exists()}",
        ]
        if committed:
            notes.append("说明=提交后的失败不声称已回滚；暂存库保留已提交数据，目标文件状态以上为准")
        else:
            notes.append("说明=提交前失败，数据事务已回滚，暂存库应保留空 schema（六表 0 行）")
        if rollback_note:
            notes.append(f"回滚异常={rollback_note}")
        notes.extend(close_notes)
        return notes + extra

    try:
        connection = connect_database(staging)
        if _scalar(connection, "PRAGMA foreign_keys") != 1:
            raise SqliteLoadError("[enable_foreign_keys] PRAGMA foreign_keys 未生效", ["阶段=enable_foreign_keys"])
        stage = "create_schema"
        execute_schema(connection, schema_sql)
        stage = "begin_transaction"
        connection.execute("BEGIN")
        try:
            for sheet in BUSINESS_TABLES:
                stage = f"insert_business_rows:{sheet}"
                insert_business_rows(connection, sheet, normalized["tables"][sheet]["records"])
            for sheet in BUSINESS_TABLES:
                stage = f"insert_source_records:{sheet}"
                insert_source_records(connection, sheet, normalized["tables"][sheet]["records"])
            stage = "insert_run_metadata"
            insert_run_metadata(connection, metadata_rows)
            # 同一未提交事务内完成全部独立核对，全部通过才提交
            stage = "verify_database"
            verification = verify_database(connection, normalized, metadata_rows)
            stage = "commit"
            connection.execute("COMMIT")
            committed = True
        except Exception:
            if not committed:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.Error as exc:
                    rollback_note = f"{type(exc).__name__}: {exc}"
            raise
        stage = "close_database"
        _close_strict()
        stage = "hash_staging"
        staging_sha = sha256_file(staging)
        stage = "publish_database"
        publish_database(staging, target)
        published = True
        stage = "final_hash"
        final_sha = sha256_file(target)
    except (SqliteLoadBlocked, SqliteLoadError) as exc:
        _close_quietly()
        if isinstance(exc, SqliteLoadError):
            exc.reasons.extend(_state_notes([]))
        raise
    except Exception as exc:  # noqa: BLE001 - 数据库／文件边界统一分类
        _close_quietly()
        raise SqliteLoadError(
            f"[{stage}] 装载过程失败：{type(exc).__name__}: {exc}",
            _state_notes([f"原始异常={type(exc).__name__}: {exc}"]),
        ) from exc

    return {
        "batch_status": VERIFIED_STATUS,
        "store_version": STORE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "next_step_allowed": False,
        "database_path": str(target),
        "database_sha256": final_sha,
        "staging_sha256": staging_sha,
        "normalized_payload_sha256": payload_sha,
        "normalization_version": normalized["normalization_version"],
        "source": normalized["source"],
        "row_counts": verification["row_counts"],
        "source_record_counts": verification["source_record_counts"],
        "table_totals": verification["table_totals"],
        "payment_groups": verification["payment_groups"],
        "settled_pay_master_total": verification["settled_pay_master_total"],
        "settled_pay_allocation_total": verification["settled_pay_allocation_total"],
        "settled_refund_master_total": verification["settled_refund_master_total"],
        "settled_refund_allocation_total": verification["settled_refund_allocation_total"],
        "master_net": verification["master_net"],
        "known_payable_link_net": verification["known_payable_link_net"],
        "missing_payable_link_net": verification["missing_payable_link_net"],
        "missing_payable_link_detail": verification["missing_payable_link_detail"],
        "net_checks": verification["net_checks"],
        "event_allocation_balanced": verification["event_allocation_balanced"],
        "foreign_key_check": verification["foreign_key_check"],
        "integrity_check": verification["integrity_check"],
        "round_trip_records": verification["round_trip_records"],
        "round_trip_exact": verification["round_trip_exact"],
        "run_metadata": verification["run_metadata"],
        "scope_limits": [
            "本报告只表示开发数据库装载已核对，不表示没有业务线索，也不是审计结论。",
            "PRAGMA foreign_key_check／integrity_check 不是审计结论检查。",
            "本地哈希不证明来源真实性，也不抵御同权限篡改。",
            "不计算超付、重复付款、风险等级或损失；规则筛查须经人工放行后另行开展。",
        ],
    }


def sqlite_version() -> str:
    return sqlite3.sqlite_version
