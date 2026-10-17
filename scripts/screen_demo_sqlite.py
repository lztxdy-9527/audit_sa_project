#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-006 开发态只读 SQL 规则核心：R01—R04 确定性事实与逐条来源。

本模块只提供 Python API，**不提供 CLI、不写任何文件**，也不推进任何批次或 Gate 状态：

    screen_sqlite(database_path, load_report: dict, *, cutoff_date="2026-09-30") -> dict

只消费数据库与匹配的装载报告：不接收答案册、场景标签或期望命中数，不导入生成器，
不从答案册／旧筛查结果产生事实；SQL 不硬编码案例 ID、金额或种子。

每条线索的必需来源集合为：相关应付单、相关原付款主表与分摊、以及**每条相关退款分摊及其
引用的退款主表**（已结算与列入 related_refunds 的非结算退款都须可追溯）。退款来源同样读取
完整 cells；来源缺项或 cells JSON 非法即失败，不返回成功报告。

读取方式：以 SQLite URI `mode=ro` 打开，再启用并实测 `PRAGMA query_only=ON`；
只用固定 SELECT／CTE，不建临时表或视图，不执行 DDL／DML／executescript，不更新元数据；
查询前后核对数据库字节哈希相等。

异常类型：
  RuleScreenBlocked  前提／范围不成立（报告的开发态标识或版本不符、报告与数据库不匹配、
                     数据库缺失／越界／为未发布暂存库、截至日不支持、数据库与报告记录的
                     运行元数据不一致、业务日期超出本版范围）——不执行规则、不返回成功报告。
  RuleScreenError    文件、SQL、核对或来源读取等运行失败（含汇总溢出、来源缺项、
                     非法 cells JSON、只读保护失败、正常关闭失败）——保留阶段、路径与原原因。

开发边界：本模块是 DEVELOPMENT_TEST_ONLY。规则事实是待核实线索，不构成舞弊、损失、
控制缺陷或审计调整结论；不生成 AI 判断、严重等级或人类判断预填值。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SQL_DIR = PROJECT_ROOT / "sql"
RULES_SQL_DIR = SQL_DIR / "rules"
STORE_PATH = SCRIPTS_DIR / "store_demo_sqlite.py"
SCHEMA_PATH = SQL_DIR / "demo_schema.sql"
SQLITE_TESTS_ROOT = (PROJECT_ROOT / "data" / "sqlite_tests").resolve()

RULE_CORE_VERSION = "TASK-006-rule-core-1.1"
RULE_IDS = ("R01", "R02", "R03", "R04")
RULE_VERSIONS = {
    "R01": "TASK-006-R01-1.0",
    "R02": "TASK-006-R02-1.0",
    "R03": "TASK-006-R03-1.0",
    "R04": "TASK-006-R04-1.0",
}
PERIOD_START = "2026-09-01"
PERIOD_END = "2026-09-30"
SUPPORTED_CUTOFF_DATE = "2026-09-30"
MODE = "DEVELOPMENT_TEST_ONLY"
RULES_STATUS = "DEV_RULES_COMPUTED"
EXPECTED_LOAD_STATUS = "DEV_SQLITE_VERIFIED"
EXPECTED_STORE_VERSION = "TASK-005-sqlite-load-1.2"
EXPECTED_SCHEMA_VERSION = "demo-schema-1.0"
FROZEN_STORE_SHA256 = "1abfad898e18c54fd5dd81e44973d078187b2837838638c1a6f46e9c8c74a446"
FROZEN_SCHEMA_SHA256 = "7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205"
MAX_SQLITE_INTEGER = 2**63 - 1

R03_MISSING_KIND_LABEL = {
    "EMPTY_AP_ID": "未填写关联",
    "AP_NOT_IN_LEDGER": "填写的标识不在台账",
}
FACT_TEXT = {
    "R01": "该应付单在截至日存在至少两笔不同已结算原付款，每笔对该应付的退款后净额均精确等于应付金额，"
    "属现存重复足额付款线索；组内金额是符合条件付款的合计，不代表该应付的全部净付款。",
    "R02": "该应付单截至日已结算净付款（已结算付款分摊减有效退款分摊）严格大于应付金额，"
    "按唯一应付单汇总一次，属应付净付款超额线索；不自动形成会计调整或重要性判断。",
    "R03": "该已结算付款分摊在所提供的应付台账中未找到关联对象；分摊金额保留在总体勾稽中，"
    "不参加 R01、R02，也不改写为“无发票”“无真实采购”或“违法支付”。",
    "R04": "该已结算付款分摊的实际收款对象与应付单供应商不同；需核实是否为授权代收、主体映射问题"
    "或付款错误，不得仅凭对象差异判定违规。",
}
FIXED_PROMPTS = {
    "R03": "请补充应付关联依据或说明该分摊的业务背景；在取得证据前不作出性质判断。",
    "R04": "请核实授权代收材料、主体映射关系与银行回单；在取得证据前不作出性质判断。",
}
SCOPE_LIMITS = [
    "规则输出是待核实线索，不能直接认定舞弊、损失、控制缺陷或审计调整，也不代替审计人员职业判断。",
    "未生成 AI 判断、严重等级、自动审计结论或人类判断预填值。",
    "金额单位为整数分，精确比较；四条规则的涉及金额不相加称为损失，R01／R02 同时命中不重复累计 R02 超额。",
    "涉及的整笔付款总额是整笔资金口径，不能当作缺失关联分摊额或损失。",
    "本模块不写任何文件、不推进任何业务批次、不改变 Gate 1／Gate 2 状态。",
]


class RuleScreenBlocked(Exception):
    """前提或范围不成立；不执行规则、不返回成功报告。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


class RuleScreenError(Exception):
    """文件、SQL、核对或来源读取等运行失败；保留阶段、路径与原始原因。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


# ---------------------------------------------------------------------------
# 文件与路径边界
# ---------------------------------------------------------------------------


def read_file_bytes(path: Path) -> bytes:
    """读取文件字节。单独成函数便于在内存中模拟读取失败。"""
    return path.read_bytes()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(read_file_bytes(path)).hexdigest()


def _file_error(stage: str, path: Path, exc: BaseException) -> RuleScreenError:
    return RuleScreenError(
        f"[{stage}] 无法读取文件 {path}：{type(exc).__name__}: {exc}",
        [f"阶段={stage}", f"路径={path}", f"原始异常={type(exc).__name__}: {exc}"],
    )


def resolve_database_path(database_path) -> Path:
    """只接受 data/sqlite_tests 内已存在的最终数据库文件；拒绝目录、缺失、越界与 .staging。"""
    raw = Path(database_path)
    target = raw.expanduser()
    target = target.resolve() if target.is_absolute() else (Path.cwd() / target).resolve()
    try:
        target.relative_to(SQLITE_TESTS_ROOT)
    except ValueError:
        raise RuleScreenBlocked(f"数据库路径必须位于 {SQLITE_TESTS_ROOT} 之内：{target}")
    if target == SQLITE_TESTS_ROOT:
        raise RuleScreenBlocked("数据库路径不能是 data/sqlite_tests 目录本身")
    if target.suffix == ".staging" or target.name.endswith(".staging"):
        raise RuleScreenBlocked(f"未发布的暂存库不能作为规则输入：{target}")
    if not target.exists():
        raise RuleScreenBlocked(f"数据库文件不存在，规则核心不会创建：{target}")
    if not target.is_file():
        raise RuleScreenBlocked(f"规则输入必须是数据库文件：{target}")
    return target


# ---------------------------------------------------------------------------
# 前提核对：装载报告、冻结版本、运行元数据、日期范围
# ---------------------------------------------------------------------------


def _require(condition: bool, path: str, reason: str) -> None:
    if not condition:
        raise RuleScreenBlocked(f"装载报告或数据库字段 {path} 不可用：{reason}")


def check_load_report(load_report, target: Path, database_sha256: str) -> dict:
    """核对本层消费的装载报告字段；不满足抛 RuleScreenBlocked。"""
    _require(isinstance(load_report, dict), "load_report", f"必须是对象，实际 {type(load_report).__name__}")
    _require(load_report.get("batch_status") == EXPECTED_LOAD_STATUS, "batch_status",
             f"必须是 {EXPECTED_LOAD_STATUS}，实际 {load_report.get('batch_status')!r}")
    _require(load_report.get("mode") == MODE, "mode", f"必须是 {MODE}")
    _require(load_report.get("next_step_allowed") is False, "next_step_allowed", "必须是 false")
    _require(load_report.get("store_version") == EXPECTED_STORE_VERSION, "store_version",
             f"必须是 {EXPECTED_STORE_VERSION}，实际 {load_report.get('store_version')!r}")
    _require(load_report.get("schema_version") == EXPECTED_SCHEMA_VERSION, "schema_version",
             f"必须是 {EXPECTED_SCHEMA_VERSION}，实际 {load_report.get('schema_version')!r}")
    reported_path = load_report.get("database_path")
    _require(isinstance(reported_path, str) and Path(reported_path).resolve() == target,
             "database_path", f"必须与实际输入一致：report={reported_path} actual={target}")
    reported_sha = load_report.get("database_sha256")
    _require(reported_sha == database_sha256, "database_sha256",
             f"必须与实际字节哈希相等：report={reported_sha} actual={database_sha256}")
    source = load_report.get("source")
    _require(isinstance(source, dict), "source", "必须是对象")
    input_sha = source.get("input_sha256")
    _require(isinstance(input_sha, str) and len(input_sha) == 64, "source.input_sha256", "必须是 64 位哈希")
    fingerprint = load_report.get("normalized_payload_sha256")
    _require(isinstance(fingerprint, str) and len(fingerprint) == 64, "normalized_payload_sha256",
             "必须是 64 位对象指纹")
    reconciliation = load_report.get("overall_reconciliation") if "overall_reconciliation" in load_report else load_report
    for key in ("master_net", "known_payable_link_net", "missing_payable_link_net"):
        _require(isinstance(load_report.get(key), int) and not isinstance(load_report.get(key), bool),
                 key, f"必须是整数分，实际 {load_report.get(key)!r}")
    _require(isinstance(reconciliation, dict), "load_report", "必须是对象")
    return load_report


def check_frozen_versions() -> dict:
    """核对当前冻结装载器／schema 文件与本卡冻结哈希相符。"""
    try:
        store_sha = sha256_file(STORE_PATH)
        schema_sha = sha256_file(SCHEMA_PATH)
    except Exception as exc:  # noqa: BLE001
        raise _file_error("read_frozen_versions", STORE_PATH, exc) from exc
    if store_sha != FROZEN_STORE_SHA256:
        raise RuleScreenBlocked(
            f"当前装载器哈希与冻结版本不符：actual={store_sha} frozen={FROZEN_STORE_SHA256}"
        )
    if schema_sha != FROZEN_SCHEMA_SHA256:
        raise RuleScreenBlocked(
            f"当前 schema 哈希与冻结版本不符：actual={schema_sha} frozen={FROZEN_SCHEMA_SHA256}"
        )
    return {"store_script_sha256": store_sha, "schema_sha256": schema_sha}


def open_readonly(path: Path) -> sqlite3.Connection:
    """以 URI mode=ro 打开（不提供可创建连接回退），并启用 query_only。"""
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _scalar(connection: sqlite3.Connection, sql: str, params: tuple = ()):
    row = connection.execute(sql, params).fetchone()
    return None if row is None else row[0]


def verify_run_metadata(connection: sqlite3.Connection, load_report: dict, frozen: dict) -> dict:
    """从数据库实际读取 run_metadata，与装载报告及冻结版本核对。"""
    try:
        actual = dict(connection.execute("SELECT metadata_key, metadata_value FROM run_metadata").fetchall())
    except sqlite3.Error as exc:
        raise RuleScreenBlocked(f"无法读取 run_metadata：{type(exc).__name__}: {exc}") from exc
    problems: list[str] = []
    expected_exact = {
        "mode": MODE,
        "next_step_allowed": "false",
        "batch_status": EXPECTED_LOAD_STATUS,
        "store_version": EXPECTED_STORE_VERSION,
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "input_sha256": load_report["source"]["input_sha256"],
        "normalized_payload_sha256": load_report["normalized_payload_sha256"],
        "store_script_sha256": frozen["store_script_sha256"],
        "schema_sha256": frozen["schema_sha256"],
    }
    for key, expected in expected_exact.items():
        actual_value = actual.get(key)
        if actual_value != expected:
            problems.append(f"run_metadata.{key} 实际 {actual_value!r} != 预期 {expected!r}")
    if problems:
        raise RuleScreenBlocked("数据库运行元数据与装载报告不一致，不能作为规则输入", problems)
    return {
        key: actual.get(key)
        for key in ("mode", "next_step_allowed", "batch_status", "store_version", "schema_version",
                    "input_sha256", "normalized_payload_sha256", "store_script_sha256", "schema_sha256",
                    "created_at_utc")
    }


def check_period_range(connection: sqlite3.Connection) -> dict:
    """核对业务日期都在本版范围内；范围不符须报告，不以 WHERE 静默过滤后出完整结果。"""
    problems: list[str] = []
    for table, column in (("payables", "ap_date"), ("payments", "payment_date")):
        outside = _scalar(
            connection,
            f"SELECT COUNT(*) FROM {table} WHERE {column} < ? OR {column} > ?",
            (PERIOD_START, PERIOD_END),
        )
        total = _scalar(connection, f"SELECT COUNT(*) FROM {table}")
        if outside:
            problems.append(f"{table}.{column} 有 {outside} 行超出 {PERIOD_START}—{PERIOD_END}（共 {total} 行）")
        if total is None:
            problems.append(f"无法统计 {table} 行数")
    if problems:
        raise RuleScreenBlocked("业务日期范围不符，未执行规则", problems)
    return {"period_start": PERIOD_START, "period_end": PERIOD_END, "range_ok": True}


# ---------------------------------------------------------------------------
# 总体勾稽（独立从 payments／allocations 粒度计算）
# ---------------------------------------------------------------------------


def overall_reconciliation(connection: sqlite3.Connection, load_report: dict) -> dict:
    """从数据库独立计算总体资金与净额，对照装载报告；不一致抛 RuleScreenError。"""
    settled_pay = _scalar(
        connection,
        "SELECT COALESCE(SUM(amount_cents), 0) FROM payments "
        "WHERE transaction_type = 'PAY' AND settlement_status = 'SETTLED' "
        "AND payment_date >= ? AND payment_date <= ?",
        (PERIOD_START, PERIOD_END),
    )
    settled_refund = _scalar(
        connection,
        "SELECT COALESCE(SUM(amount_cents), 0) FROM payments "
        "WHERE transaction_type = 'REFUND' AND settlement_status = 'SETTLED' "
        "AND payment_date >= ? AND payment_date <= ?",
        (PERIOD_START, PERIOD_END),
    )
    sign = "CASE WHEN p.transaction_type = 'PAY' THEN 1 ELSE -1 END"
    classification = (
        "CASE WHEN a.ap_id IS NULL OR a.ap_id = '' THEN 'empty_ap_id' "
        "WHEN NOT EXISTS (SELECT 1 FROM payables pa WHERE pa.ap_id = a.ap_id) THEN 'ap_id_not_in_ledger' "
        "ELSE 'known' END"
    )
    base_sql = (
        f"SELECT COALESCE(SUM({sign} * a.allocated_amount_cents), 0) FROM allocations a "
        "JOIN payments p ON p.payment_id = a.payment_id "
        "WHERE p.settlement_status = 'SETTLED' AND p.payment_date >= ? AND p.payment_date <= ? "
        f"AND {classification} = ?"
    )
    empty_net = _scalar(connection, base_sql, (PERIOD_START, PERIOD_END, "empty_ap_id"))
    unknown_net = _scalar(connection, base_sql, (PERIOD_START, PERIOD_END, "ap_id_not_in_ledger"))
    known_net = _scalar(connection, base_sql, (PERIOD_START, PERIOD_END, "known"))
    missing_net = empty_net + unknown_net
    master_net = settled_pay - settled_refund

    differences: list[str] = []
    comparisons = {
        "settled_pay_master_total": (settled_pay, load_report["settled_pay_master_total"]),
        "settled_refund_master_total": (settled_refund, load_report["settled_refund_master_total"]),
        "master_net": (master_net, load_report["master_net"]),
        "known_payable_link_net": (known_net, load_report["known_payable_link_net"]),
        "missing_payable_link_net": (missing_net, load_report["missing_payable_link_net"]),
        "empty_ap_id": (empty_net, load_report["missing_payable_link_detail"]["empty_ap_id"]),
        "ap_id_not_in_ledger": (unknown_net, load_report["missing_payable_link_detail"]["ap_id_not_in_ledger"]),
    }
    for name, (actual, reported) in comparisons.items():
        if actual != reported:
            differences.append(f"{name} 数据库 {actual} != 装载报告 {reported}")
    if master_net != known_net + missing_net:
        differences.append(f"master_net {master_net} != known {known_net} + missing {missing_net}")
    if differences:
        raise RuleScreenError("总体勾稽与装载报告不一致，未出规则结果", differences)
    return {
        "unit": "cents",
        "settled_pay_master_total": settled_pay,
        "settled_refund_master_total": settled_refund,
        "master_net": master_net,
        "known_payable_link_net": known_net,
        "missing_payable_link_net": missing_net,
        "missing_payable_link_detail": {"empty_ap_id": empty_net, "ap_id_not_in_ledger": unknown_net},
        "master_net_equals_known_plus_missing": True,
        "matches_load_report": True,
    }


# ---------------------------------------------------------------------------
# 规则 SQL 与证据
# ---------------------------------------------------------------------------


def load_rule_sql(rule_id: str) -> tuple[str, Path, str]:
    path = RULES_SQL_DIR / f"{rule_id.lower()}.sql"
    if rule_id not in RULE_IDS:
        raise RuleScreenError(f"未知规则：{rule_id}")
    try:
        text = read_file_bytes(path).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise _file_error(f"read_rule_sql:{rule_id}", path, exc) from exc
    if not text.strip().upper().lstrip().startswith(("--", "WITH", "SELECT")):
        raise RuleScreenError(f"[read_rule_sql:{rule_id}] 规则 SQL 必须是只读 SELECT／CTE：{path}")
    return text, path, hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_rule(connection: sqlite3.Connection, rule_id: str, sql_text: str, params: dict) -> list[dict]:
    try:
        cursor = connection.execute(sql_text, params)
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except sqlite3.Error as exc:
        raise RuleScreenError(
            f"[run_rule:{rule_id}] 规则查询失败：{type(exc).__name__}: {exc}",
            [f"阶段=run_rule:{rule_id}", f"原始异常={type(exc).__name__}: {exc}"],
        ) from exc


def source_provenance(connection: sqlite3.Connection, sheet: str, record_ids: list[str]) -> dict:
    """从 source_records 读取来源；缺项或非法 JSON 明确失败，不默默省略。"""
    result: dict[str, dict] = {}
    for record_id in record_ids:
        row = connection.execute(
            "SELECT workbook_sha256, sheet, excel_row, cells_json FROM source_records "
            "WHERE table_name = ? AND record_id = ?",
            (sheet, record_id),
        ).fetchone()
        if row is None:
            raise RuleScreenError(
                f"[source_provenance] {sheet} {record_id} 缺少来源记录，不能返回“证据完整”",
                [f"阶段=source_provenance", f"表={sheet}", f"业务 ID={record_id}"],
            )
        try:
            cells = json.loads(row[3])
        except json.JSONDecodeError as exc:
            raise RuleScreenError(
                f"[source_provenance] {sheet} {record_id} 的 cells JSON 非法：{exc}",
                [f"阶段=source_provenance", f"表={sheet}", f"业务 ID={record_id}"],
            ) from exc
        result[record_id] = {
            "workbook_sha256": row[0],
            "sheet": row[1],
            "excel_row": row[2],
            "cells": cells,
        }
    return result


def _refunds_for_allocations(connection: sqlite3.Connection, allocation_ids: list[str]) -> list[dict]:
    """相关退款摘要：退款分摊 + 其引用的退款主表；已结算与非结算都返回，标明是否计入净额。"""
    if not allocation_ids:
        return []
    placeholders = ", ".join("?" for _ in allocation_ids)
    rows = connection.execute(
        "SELECT r.allocation_id, r.payment_id, r.original_allocation_id, r.allocated_amount_cents, "
        "rp.settlement_status, rp.original_payment_id, rp.payment_date "
        "FROM allocations r JOIN payments rp ON rp.payment_id = r.payment_id "
        f"WHERE r.original_allocation_id IN ({placeholders}) "
        "ORDER BY r.payment_id, r.allocation_id",
        tuple(allocation_ids),
    ).fetchall()
    return [
        {
            "refund_allocation_id": row[0],
            "refund_payment_id": row[1],
            "original_allocation_id": row[2],
            "allocated_amount_cents": row[3],
            "settlement_status": row[4],
            "original_payment_id": row[5],
            "payment_date": row[6],
            "counted_in_net": row[4] == "SETTLED" and PERIOD_START <= row[6] <= PERIOD_END,
        }
        for row in rows
    ]


def _payments_for_allocations(connection: sqlite3.Connection, allocation_ids: list[str], ap_id: str | None) -> list[dict]:
    if not allocation_ids:
        return []
    placeholders = ", ".join("?" for _ in allocation_ids)
    params: list = list(allocation_ids)
    sql = (
        "SELECT a.payment_id, a.allocation_id, a.allocated_amount_cents, p.transaction_type, "
        "p.settlement_status, p.payee_supplier_id, p.amount_cents "
        "FROM allocations a JOIN payments p ON p.payment_id = a.payment_id "
        f"WHERE a.allocation_id IN ({placeholders}) "
        "ORDER BY a.payment_id, a.allocation_id"
    )
    rows = connection.execute(sql, tuple(params)).fetchall()
    return [
        {
            "payment_id": row[0],
            "allocation_id": row[1],
            "allocated_amount_cents": row[2],
            "transaction_type": row[3],
            "settlement_status": row[4],
            "payee_supplier_id": row[5],
            "payment_amount_cents": row[6],
        }
        for row in rows
    ]


def _allocations_for_payable_payments(
    connection: sqlite3.Connection, ap_id: str, payment_ids: list[str]
) -> list[str]:
    if not payment_ids:
        return []
    placeholders = ", ".join("?" for _ in payment_ids)
    rows = connection.execute(
        "SELECT a.allocation_id FROM allocations a JOIN payments p ON p.payment_id = a.payment_id "
        f"WHERE a.ap_id = ? AND a.payment_id IN ({placeholders}) "
        "AND p.transaction_type = 'PAY' AND p.settlement_status = 'SETTLED' "
        "AND p.payment_date >= ? AND p.payment_date <= ? "
        "ORDER BY a.allocation_id",
        (ap_id, *payment_ids, PERIOD_START, PERIOD_END),
    ).fetchall()
    return [row[0] for row in rows]


def _evidence_block(
    connection: sqlite3.Connection,
    payable_ids: list[str],
    payment_ids: list[str],
    allocation_ids: list[str],
) -> tuple[dict, dict, list[dict], list[dict]]:
    """必需来源集合：相关应付、原付款主表、原付款分摊、每条退款分摊及其退款主表。

    退款主表与退款分摊同样经 source_provenance 读取完整 cells；缺项或非法 JSON 直接失败。
    """
    refunds = _refunds_for_allocations(connection, allocation_ids)
    refund_payment_ids = sorted({item["refund_payment_id"] for item in refunds})
    refund_allocation_ids = sorted({item["refund_allocation_id"] for item in refunds})

    payables = source_provenance(connection, "payables", payable_ids)
    payments = source_provenance(connection, "payments", payment_ids)
    allocations = source_provenance(connection, "allocations", allocation_ids)
    refund_payments = source_provenance(connection, "payments", refund_payment_ids)
    refund_allocations = source_provenance(connection, "allocations", refund_allocation_ids)

    # 同一退款主表涉及多条相关退款分摊时只出现一次；原付款与退款共用唯一编号空间，不重复
    merged_payments = {**refund_payments, **payments}
    merged_allocations = {**refund_allocations, **allocations}
    source_rows = {
        "payables": {key: value["excel_row"] for key, value in sorted(payables.items())},
        "payments": {key: value["excel_row"] for key, value in sorted(merged_payments.items())},
        "allocations": {key: value["excel_row"] for key, value in sorted(merged_allocations.items())},
    }
    entities = [
        {"table_name": sheet, "record_id": record_id, **provenance}
        for sheet, block in (
            ("payables", payables),
            ("payments", merged_payments),
            ("allocations", merged_allocations),
        )
        for record_id, provenance in sorted(block.items())
    ]
    related = _payments_for_allocations(connection, allocation_ids, None)
    return source_rows, {"entities": entities}, refunds, related


def _check_amount(value, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuleScreenError(f"[amounts] {path} 必须是整数分，实际 {type(value).__name__}")
    if abs(value) > MAX_SQLITE_INTEGER:
        raise RuleScreenError(f"[amounts] {path} 超出 SQLite 整数能力，拒绝改用浮点容差")
    return value


def build_findings(connection: sqlite3.Connection, rule_id: str, rows: list[dict]) -> list[dict]:
    findings: list[dict] = []
    if rule_id == "R01":
        grouped: dict[tuple, dict] = {}
        for row in rows:
            key = (row["ap_id"], row["payee_supplier_id"])
            entry = grouped.setdefault(
                key,
                {
                    "payable_amount": row["payable_amount"],
                    "net_total": row["net_total"],
                    "qualifier_count": row["qualifier_count"],
                    "net_per_payment": {},
                },
            )
            entry["net_per_payment"][row["payment_id"]] = row["net_per_payment"]
        for (ap_id, payee), entry in grouped.items():
            payment_ids = sorted(entry["net_per_payment"])
            allocation_ids = _allocations_for_payable_payments(connection, ap_id, payment_ids)
            source_rows, evidence, refunds, _ = _evidence_block(connection, [ap_id], payment_ids, allocation_ids)
            amounts = {
                "payable_amount": _check_amount(entry["payable_amount"], "R01.payable_amount"),
                "net_per_payment": {
                    pid: _check_amount(cents, f"R01.net_per_payment[{pid}]")
                    for pid, cents in sorted(entry["net_per_payment"].items())
                },
                "net_total": _check_amount(entry["net_total"], "R01.net_total"),
            }
            findings.append(
                {
                    "rule_id": "R01",
                    "hit_key": {"rule_id": "R01", "ap_id": ap_id, "payee_supplier_id": payee},
                    "amounts_cents": amounts,
                    "related_ids": {
                        "payable_id": ap_id,
                        "payment_ids": payment_ids,
                        "allocation_ids": allocation_ids,
                        "refund_ids": sorted({item["refund_payment_id"] for item in refunds}),
                    },
                    "source_rows": source_rows,
                    "counts": {"qualifier_payment_count": entry["qualifier_count"]},
                    "evidence": {**evidence, "related_refunds": refunds},
                    "fact": FACT_TEXT["R01"],
                }
            )
    elif rule_id == "R02":
        for row in rows:
            ap_id = row["ap_id"]
            allocations = connection.execute(
                "SELECT a.allocation_id, a.payment_id FROM allocations a "
                "JOIN payments p ON p.payment_id = a.payment_id "
                "WHERE a.ap_id = ? AND p.transaction_type = 'PAY' AND p.settlement_status = 'SETTLED' "
                "AND p.payment_date >= ? AND p.payment_date <= ? ORDER BY a.allocation_id",
                (ap_id, PERIOD_START, PERIOD_END),
            ).fetchall()
            allocation_ids = [item[0] for item in allocations]
            payment_ids = sorted({item[1] for item in allocations})
            source_rows, evidence, refunds, _ = _evidence_block(connection, [ap_id], payment_ids, allocation_ids)
            findings.append(
                {
                    "rule_id": "R02",
                    "hit_key": {"rule_id": "R02", "ap_id": ap_id},
                    "amounts_cents": {
                        "payable_amount": _check_amount(row["payable_amount"], "R02.payable_amount"),
                        "paid_total": _check_amount(row["paid_total"], "R02.paid_total"),
                        "refund_total": _check_amount(row["refund_total"], "R02.refund_total"),
                        "net_total": _check_amount(row["net_total"], "R02.net_total"),
                        "overpayment": _check_amount(row["overpayment"], "R02.overpayment"),
                    },
                    "related_ids": {
                        "payable_id": ap_id,
                        "payment_ids": payment_ids,
                        "allocation_ids": allocation_ids,
                        "refund_ids": sorted({item["refund_payment_id"] for item in refunds}),
                    },
                    "source_rows": source_rows,
                    "evidence": {**evidence, "related_refunds": refunds},
                    "fact": FACT_TEXT["R02"],
                }
            )
    elif rule_id in ("R03", "R04"):
        for row in rows:
            allocation_id = row["allocation_id"]
            ap_id = row["ap_id"]
            known_ap = rule_id == "R04"
            payable_ids = [ap_id] if known_ap else []
            source_rows, evidence, refunds, _ = _evidence_block(
                connection, payable_ids, [row["payment_id"]], [allocation_id]
            )
            amounts = {
                "allocated_amount": _check_amount(row["allocated_amount"], f"{rule_id}.allocated_amount"),
                "paid_amount": _check_amount(row["allocated_amount"], f"{rule_id}.paid_amount"),
                "refunded_amount": _check_amount(row["refunded_amount"], f"{rule_id}.refunded_amount"),
                "net_amount": _check_amount(row["net_amount"], f"{rule_id}.net_amount"),
            }
            if known_ap:
                amounts["payable_amount"] = _check_amount(row["payable_amount"], "R04.payable_amount")
            related = {
                "payable_id": ap_id if known_ap else (None if not ap_id else ap_id),
                "payment_ids": [row["payment_id"]],
                "allocation_ids": [allocation_id],
                "refund_ids": sorted({item["refund_payment_id"] for item in refunds}),
            }
            if rule_id == "R03":
                related["missing_kind_code"] = row["missing_kind_code"]
                related["missing_kind"] = R03_MISSING_KIND_LABEL[row["missing_kind_code"]]
            else:
                related["payable_supplier_id"] = row["payable_supplier_id"]
                related["payee_supplier_id"] = row["payee_supplier_id"]
            finding = {
                "rule_id": rule_id,
                "hit_key": {"rule_id": rule_id, "allocation_id": allocation_id},
                "amounts_cents": amounts,
                "related_ids": related,
                "source_rows": source_rows,
                "evidence": {**evidence, "related_refunds": refunds},
                "fact": FACT_TEXT[rule_id],
                "verification_prompt": FIXED_PROMPTS[rule_id],
            }
            if rule_id == "R03" and not known_ap:
                finding["evidence"]["missing"] = (
                    "所提供的应付台账中不存在该应付记录"
                    if row["missing_kind_code"] == "AP_NOT_IN_LEDGER"
                    else "该分摊未填写应付关联"
                )
            findings.append(finding)

    findings.sort(key=lambda item: (item["rule_id"], json.dumps(item["hit_key"], ensure_ascii=False, sort_keys=True)))
    keys = [json.dumps(item["hit_key"], ensure_ascii=False, sort_keys=True) for item in findings]
    if len(keys) != len(set(keys)):
        raise RuleScreenError(f"[{rule_id}] 结构化命中键存在重复，拒绝输出")
    return findings


def _involved_payments(connection: sqlite3.Connection, findings: list[dict]) -> dict:
    payment_ids = sorted(
        {pid for finding in findings for pid in finding["related_ids"].get("payment_ids", [])}
    )
    if not payment_ids:
        return {"count": 0, "payment_ids": [], "settled_amount_cents": 0, "note": "整笔资金口径，未涉及原付款事件"}
    placeholders = ", ".join("?" for _ in payment_ids)
    total = _scalar(
        connection,
        f"SELECT COALESCE(SUM(amount_cents), 0) FROM payments WHERE payment_id IN ({placeholders}) "
        "AND transaction_type = 'PAY' AND settlement_status = 'SETTLED'",
        tuple(payment_ids),
    )
    return {
        "count": len(payment_ids),
        "payment_ids": payment_ids,
        "settled_amount_cents": total,
        "note": "涉及的唯一原付款事件的整笔已结算总额；整笔资金口径，不能当作缺失关联分摊额或损失。",
    }


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def screen_sqlite(database_path, load_report: dict, *, cutoff_date: str = SUPPORTED_CUTOFF_DATE) -> dict:
    """对已核对数据库执行 R01—R04 只读规则，返回事实报告；不写任何文件。"""
    if cutoff_date != SUPPORTED_CUTOFF_DATE:
        raise RuleScreenBlocked(
            f"本版只支持截至日 {SUPPORTED_CUTOFF_DATE}，实际 {cutoff_date!r}；不静默改用其他日期"
        )
    target = resolve_database_path(database_path)
    try:
        database_sha256 = sha256_file(target)
    except Exception as exc:  # noqa: BLE001
        raise _file_error("read_database_hash", target, exc) from exc
    check_load_report(load_report, target, database_sha256)
    frozen = check_frozen_versions()

    connection = None
    stage = "open_readonly"
    close_notes: list[str] = []

    def _close_strict() -> None:
        nonlocal connection
        if connection is None:
            return
        try:
            connection.close()
        except Exception as exc:  # noqa: BLE001
            raise RuleScreenError(
                f"[close_database] 关闭数据库失败：{type(exc).__name__}: {exc}",
                ["阶段=close_database", f"数据库路径={target}", f"原始异常={type(exc).__name__}: {exc}"],
            ) from exc
        connection = None

    def _close_quietly() -> None:
        nonlocal connection
        if connection is None:
            return
        try:
            connection.close()
            connection = None
        except Exception as exc:  # noqa: BLE001
            close_notes.append(f"清理时关闭连接失败：{type(exc).__name__}: {exc}")

    try:
        connection = open_readonly(target)
        stage = "enable_query_only"
        connection.execute("PRAGMA query_only = ON")
        query_only = _scalar(connection, "PRAGMA query_only")
        if query_only != 1:
            raise RuleScreenError(
                f"[enable_query_only] PRAGMA query_only 未生效：{query_only!r}",
                ["阶段=enable_query_only", f"数据库路径={target}"],
            )
        stage = "verify_run_metadata"
        metadata = verify_run_metadata(connection, load_report, frozen)
        stage = "check_period_range"
        period = check_period_range(connection)
        stage = "overall_reconciliation"
        reconciliation = overall_reconciliation(connection, load_report)

        rules_meta: dict[str, dict] = {}
        findings: list[dict] = []
        for rule_id in RULE_IDS:
            stage = f"rule:{rule_id}"
            sql_text, sql_path, sql_sha = load_rule_sql(rule_id)
            params = {"cutoff_start": PERIOD_START, "cutoff_end": SUPPORTED_CUTOFF_DATE}
            rows = run_rule(connection, rule_id, sql_text, params)
            findings.extend(build_findings(connection, rule_id, rows))
            rules_meta[rule_id] = {
                "rule_version": RULE_VERSIONS[rule_id],
                "sql_path": str(sql_path),
                "sql_sha256": sql_sha,
                "hit_count": sum(1 for item in findings if item["rule_id"] == rule_id),
            }

        stage = "statistics"
        hit_counts = {rule_id: rules_meta[rule_id]["hit_count"] for rule_id in RULE_IDS}
        hit_counts["total"] = sum(hit_counts[rule_id] for rule_id in RULE_IDS)
        statistics = {
            "involved_payments": _involved_payments(connection, findings),
            "r02_overpayment_total_cents": sum(
                item["amounts_cents"]["overpayment"] for item in findings if item["rule_id"] == "R02"
            ),
            "r02_overpayment_basis": "按唯一应付单汇总一次；不乘以付款行数或其他规则命中数",
            "rule_amounts_not_summed_as_loss": True,
        }
        stage = "close_database"
        _close_strict()
        stage = "verify_readonly"
        after_sha = sha256_file(target)
        if after_sha != database_sha256:
            raise RuleScreenError(
                "[verify_readonly] 规则执行前后数据库字节哈希不一致",
                [f"阶段=verify_readonly", f"前={database_sha256}", f"后={after_sha}"],
            )
    except (RuleScreenBlocked, RuleScreenError) as exc:
        _close_quietly()
        if isinstance(exc, RuleScreenError):
            exc.reasons.extend([f"阶段={stage}", f"数据库路径={target}"] + close_notes)
        raise
    except Exception as exc:  # noqa: BLE001
        _close_quietly()
        raise RuleScreenError(
            f"[{stage}] 规则执行失败：{type(exc).__name__}: {exc}",
            [f"阶段={stage}", f"数据库路径={target}", f"原始异常={type(exc).__name__}: {exc}"] + close_notes,
        ) from exc

    return {
        "batch_status": RULES_STATUS,
        "mode": MODE,
        "next_step_allowed": False,
        "rule_core_version": RULE_CORE_VERSION,
        "rules": rules_meta,
        "cutoff_date": SUPPORTED_CUTOFF_DATE,
        "period": period,
        "database_path": str(target),
        "database_sha256_before": database_sha256,
        "database_sha256_after": after_sha,
        "database_unchanged": True,
        "read_only": {"uri_mode": "ro", "query_only": 1},
        "load_source": {
            "batch_status": load_report["batch_status"],
            "store_version": load_report["store_version"],
            "schema_version": load_report["schema_version"],
            "input_sha256": load_report["source"]["input_sha256"],
            "normalized_payload_sha256": load_report["normalized_payload_sha256"],
            "database_sha256": load_report["database_sha256"],
            "run_metadata": metadata,
        },
        "overall_reconciliation": reconciliation,
        "rule_hit_counts": hit_counts,
        "findings": findings,
        "statistics": statistics,
        "limits": SCOPE_LIMITS,
    }
