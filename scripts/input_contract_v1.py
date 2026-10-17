#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-043：输入契约 v1 校验与输入登记（账 / 证 / 银 / 表占位）。

只接受**已规整输入**：不解析非结构化原件、不做 OCR、不做银行格式适配、不做清洗。
任何一条契约不满足 → **整批拒收**：写 `rejection.json`、不生成登记、进程退出码非 0。
通过 → 写 `input_registry.json`（版本/批次/逐文件哈希/各类计数/校验结论），并做一次同缓冲读回。

边界：合成数据演示；不证明凭证真实、不构成审计证据或结论；`real_approval=null`、
真实独立初判未保存、`next_step_allowed=false`、`ai_enabled=false`。本工具不写批次、账务、
凭证或银行输入，不写 Gate/历史/演示现场。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"

INPUT_VERSION = "task043-input-1.0"
ACCEPTED_INPUT_VERSIONS = ("task043-input-1.0", "task043-input-1.1")
REGISTRY_VERSION = "task043-input-registry-1.0"
REJECTION_VERSION = "task043-input-rejection-1.0"
BATCH_ID = "batch_normal"
CURRENCY = "CNY"
COMPANY = "澄明商贸有限公司"
PERIOD_START = "2026-09-01"
PERIOD_END = "2026-09-30"
CUTOFF_DATE = "2026-09-30"
MANIFEST_FILE = "input_manifest.json"
EXPECTED_FILES = (
    "bank/transactions.json",
    "links/index.json",
    "reports/placeholders.json",
    "vouchers/approvals.json",
    "vouchers/bank_receipts.json",
    "vouchers/contracts.json",
    "vouchers/goods_receipts.json",
    "vouchers/invoices.json",
)
VOUCHER_FILES = {
    "vouchers/invoices.json": "INVOICE",
    "vouchers/contracts.json": "CONTRACT",
    "vouchers/bank_receipts.json": "BANK_RECEIPT",
    "vouchers/approvals.json": "APPROVAL",
    "vouchers/goods_receipts.json": "GOODS_RECEIPT",
}
LINK_TYPE_LEDGER = {
    "AP_INVOICE": ("AP", "INVOICE"),
    "AP_CONTRACT": ("AP", "CONTRACT"),
    "AP_GOODS_RECEIPT": ("AP", "GOODS_RECEIPT"),
    "PAYMENT_APPROVAL": ("PAYMENT", "APPROVAL"),
    "PAYMENT_BANK_RECEIPT": ("PAYMENT", "BANK_RECEIPT"),
    "REFUND_BANK_RECEIPT": ("REFUND", "BANK_RECEIPT"),
}
LEDGER_TYPES = ("AP", "PAYMENT", "REFUND")
DATE_PATTERN = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
HASH_PATTERN = re.compile(r"\A[0-9a-f]{64}\Z")

SCHEMAS = {
    "INVOICE": {
        "required": ("voucher_id", "invoice_no", "issue_date", "seller_supplier_id",
                     "seller_name", "buyer_name", "amount_cents", "tax_cents",
                     "total_cents", "currency"),
        "optional": ()},
    "CONTRACT": {
        "required": ("voucher_id", "contract_no", "sign_date",
                     "counterparty_supplier_id", "counterparty_name", "amount_cents",
                     "currency"),
        "optional": ()},
    "BANK_RECEIPT": {
        "required": ("voucher_id", "receipt_no", "bank_txn_id", "txn_date",
                     "amount_cents", "direction", "counterparty_name",
                     "counterparty_account", "currency"),
        "optional": ()},
    "APPROVAL": {
        "required": ("voucher_id", "approval_no", "approval_date", "payment_id",
                     "amount_cents", "status"),
        "optional": ()},
    "GOODS_RECEIPT": {
        "required": ("voucher_id", "gr_no", "accept_date", "supplier_id",
                     "amount_cents", "currency"),
        "optional": ()},
}
BANK_TXN_KEYS = ("bank_txn_id", "txn_date", "direction", "amount_cents",
                 "counterparty_name", "counterparty_account", "summary", "reference")
LINK_KEYS = ("link_id", "link_type", "ledger_type", "ledger_id", "voucher_id")
BOUNDARIES = {"real_approval": None, "batch_approved": False,
              "real_initial_judgment_saved": False, "next_step_allowed": False,
              "ai_enabled": False, "identity_authenticated": False,
              "audit_conclusion_formed": False}


class ContractUsageError(Exception):
    """参数/路径/环境错误（不是输入契约违约）。"""


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def is_strict_int(value) -> bool:
    return type(value) is int


def is_nonempty_text(value) -> bool:
    return type(value) is str and value != ""


def _reject_constant(text):
    raise ValueError("不接受的 JSON 常量：%s" % text)


def parse_strict_json(raw: bytes):
    text = raw.decode("utf-8")
    return json.loads(text, parse_constant=_reject_constant)


def parse_date(value):
    try:
        year, month, day = (int(part) for part in value.split("-"))
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def _reject_reparse(path: Path, field: str) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ContractUsageError("无法读取 %s：%s" % (field, exc))
    if getattr(info, "st_file_attributes", 0) & 0x400:
        raise ContractUsageError("%s 不得为 reparse/符号链接" % field)
    if path.is_symlink():
        raise ContractUsageError("%s 不得为符号链接" % field)


class Reasons:
    def __init__(self):
        self.items = []

    def add(self, code, field, detail, *, record=None, voucher_id=None,
            expected=None, actual=None):
        self.items.append({"code": code, "field": field, "record": record,
                           "voucher_id": voucher_id, "expected": expected,
                           "actual": actual, "detail": detail})

    def __bool__(self):
        return bool(self.items)


def add_reason(reasons: Reasons, code, field, detail, **kwargs):
    reasons.add(code, field, detail, **kwargs)


def check_closed_keys(reasons: Reasons, value, allowed, field):
    if type(value) is not dict:
        add_reason(reasons, "RECORD_NOT_OBJECT", field, "必须是严格对象",
                   actual=type(value).__name__)
        return False
    for key in sorted(value.keys(), key=lambda item: str(item).encode("utf-8")):
        if type(key) is not str or key not in allowed:
            add_reason(reasons, "UNKNOWN_FIELD", field + "." + str(key), "未允许的字段")
    ok = True
    for key in allowed:
        if key not in value:
            add_reason(reasons, "REQUIRED", field + "." + key, "缺少必需字段")
            ok = False
    return ok


def check_text(reasons: Reasons, value, field, *, allow_empty=False):
    if not is_nonempty_text(value) and not (allow_empty and value == ""):
        add_reason(reasons, "TYPE", field, "必须为非空原字符串",
                   actual=type(value).__name__)
        return False
    return True


def check_int(reasons: Reasons, value, field, *, minimum=1, code="TYPE"):
    if not is_strict_int(value):
        add_reason(reasons, code, field, "必须为严格整数（整数分）",
                   actual=type(value).__name__)
        return False
    if value < minimum:
        add_reason(reasons, "AMOUNT", field, "必须 >= %d" % minimum, actual=value)
        return False
    return True


def check_date(reasons: Reasons, value, field):
    if type(value) is not str or DATE_PATTERN.fullmatch(value) is None:
        add_reason(reasons, "DATE_FORMAT", field, "必须是 YYYY-MM-DD",
                   actual=value if isinstance(value, str) else type(value).__name__)
        return False
    parsed = parse_date(value)
    if parsed is None:
        add_reason(reasons, "DATE_FORMAT", field, "不是真实公历日期", actual=value)
        return False
    if value > CUTOFF_DATE:
        add_reason(reasons, "DATE_RANGE", field,
                   "不得晚于 %s" % CUTOFF_DATE, actual=value)
        return False
    return True


def check_currency(reasons: Reasons, value, field, manifest_currency):
    if type(value) is not str or value != CURRENCY or value != manifest_currency:
        add_reason(reasons, "CURRENCY", field,
                   "必须为 %s 且与 manifest 一致" % CURRENCY,
                   expected=manifest_currency, actual=value)
        return False
    return True


def read_input_root(input_root: Path) -> dict:
    if not input_root.is_dir():
        raise ContractUsageError("输入根不存在或不是目录：%s" % input_root)
    _reject_reparse(input_root, "input_root")
    files = {}
    for item in sorted(input_root.rglob("*")):
        if item.is_dir():
            continue
        if item.is_symlink():
            raise ContractUsageError("输入根内不得含符号链接：%s" % item)
        files[item.relative_to(input_root).as_posix()] = item
    return files


def validate_manifest(reasons: Reasons, manifest, files):
    field = MANIFEST_FILE
    if not check_closed_keys(reasons, manifest, ("input_version", "batch_id", "entity",
                                                 "files"), field):
        return False
    if manifest.get("input_version") not in ACCEPTED_INPUT_VERSIONS:
        add_reason(reasons, "MANIFEST_VERSION", field + ".input_version",
                   "必须为 %s 之一" % " 或 ".join(ACCEPTED_INPUT_VERSIONS),
                   actual=manifest.get("input_version"))
    if manifest.get("batch_id") != BATCH_ID:
        add_reason(reasons, "MANIFEST_BATCH", field + ".batch_id",
                   "必须为 %s" % BATCH_ID, actual=manifest.get("batch_id"))
    entity = manifest.get("entity")
    expected_entity = {"company": COMPANY, "currency": CURRENCY,
                       "period_start": PERIOD_START, "period_end": PERIOD_END,
                       "cutoff_date": CUTOFF_DATE}
    if check_closed_keys(reasons, entity, tuple(expected_entity), field + ".entity"):
        for key, expected in expected_entity.items():
            if entity.get(key) != expected:
                add_reason(reasons, "MANIFEST_ENTITY", field + ".entity." + key,
                           "必须为 %r" % expected, expected=expected,
                           actual=entity.get(key))
    entries = manifest.get("files")
    if type(entries) is not list:
        add_reason(reasons, "MANIFEST_FILES_SHAPE", field + ".files", "必须是数组")
        return False
    seen = []
    matches = []
    for index, entry in enumerate(entries):
        at = "%s.files[%d]" % (field, index)
        if not check_closed_keys(reasons, entry,
                                 ("relative", "byte_size", "sha256"), at):
            continue
        relative = entry.get("relative")
        if type(relative) is not str:
            add_reason(reasons, "MANIFEST_FILE_ENTRY", at + ".relative", "必须是字符串")
            continue
        if relative in seen:
            add_reason(reasons, "MANIFEST_FILE_ENTRY", at + ".relative",
                       "清单内 relative 重复", actual=relative)
        seen.append(relative)
        if relative == MANIFEST_FILE:
            add_reason(reasons, "MANIFEST_FILE_ENTRY", at + ".relative",
                       "manifest 自身不得含自哈希")
        if relative not in EXPECTED_FILES:
            add_reason(reasons, "MANIFEST_FILE_ENTRY", at + ".relative",
                       "不在固定文件集内", actual=relative)
            continue
        matches.append(relative)
        if not check_int(reasons, entry.get("byte_size"), at + ".byte_size", minimum=0):
            pass
        hash_value = entry.get("sha256")
        if type(hash_value) is not str or HASH_PATTERN.fullmatch(hash_value) is None:
            add_reason(reasons, "MANIFEST_HASH_FORMAT", at + ".sha256",
                       "必须为 64 位小写十六进制", actual=hash_value)
    if sorted(seen) != sorted(EXPECTED_FILES):
        add_reason(reasons, "MANIFEST_FILE_SET", field + ".files",
                   "清单必须恰为固定八个数据文件",
                   expected=sorted(EXPECTED_FILES), actual=sorted(seen))
    return True


def validate_vouchers(reasons: Reasons, records, relative, voucher_type, manifest_currency,
                      vouchers, voucher_ids):
    schema = SCHEMAS[voucher_type]
    allowed = tuple(schema["required"]) + tuple(schema["optional"])
    for index, record in enumerate(records):
        at = "%s[%d]" % (relative, index)
        if not check_closed_keys(reasons, record, allowed, at):
            continue
        voucher_id = record.get("voucher_id")
        if check_text(reasons, voucher_id, at + ".voucher_id"):
            if voucher_id in voucher_ids:
                add_reason(reasons, "ID_DUPLICATE", at + ".voucher_id",
                           "voucher_id 必须全局唯一", actual=voucher_id)
            else:
                voucher_ids[voucher_id] = voucher_type
                vouchers[voucher_id] = {"type": voucher_type, "file": relative,
                                        "index": index, "record": record}
        body = dict(record)
        if voucher_type == "INVOICE":
            for key in ("invoice_no", "seller_supplier_id", "seller_name",
                        "buyer_name"):
                check_text(reasons, body.get(key), at + "." + key)
            if body.get("buyer_name") != COMPANY:
                add_reason(reasons, "ENTITY", at + ".buyer_name",
                           "发票购买方必须为 manifest 实体 %s" % COMPANY,
                           expected=COMPANY, actual=body.get("buyer_name"))
            check_date(reasons, body.get("issue_date"), at + ".issue_date")
            check_int(reasons, body.get("amount_cents"), at + ".amount_cents")
            check_int(reasons, body.get("tax_cents"), at + ".tax_cents", minimum=0)
            check_int(reasons, body.get("total_cents"), at + ".total_cents")
            if is_strict_int(body.get("amount_cents")) and is_strict_int(body.get("tax_cents")) \
                    and is_strict_int(body.get("total_cents")):
                if body["amount_cents"] > 0 and body["tax_cents"] >= 0 \
                        and body["total_cents"] != body["amount_cents"] + body["tax_cents"]:
                    add_reason(reasons, "ARITHMETIC", at + ".total_cents",
                               "total_cents 必须等于 amount_cents + tax_cents",
                               expected=body["amount_cents"] + body["tax_cents"],
                               actual=body["total_cents"], voucher_id=voucher_id)
            check_currency(reasons, body.get("currency"), at + ".currency",
                           manifest_currency)
        elif voucher_type == "CONTRACT":
            check_text(reasons, body.get("contract_no"), at + ".contract_no")
            check_text(reasons, body.get("counterparty_supplier_id"),
                       at + ".counterparty_supplier_id")
            check_text(reasons, body.get("counterparty_name"), at + ".counterparty_name")
            check_date(reasons, body.get("sign_date"), at + ".sign_date")
            check_int(reasons, body.get("amount_cents"), at + ".amount_cents")
            check_currency(reasons, body.get("currency"), at + ".currency",
                           manifest_currency)
        elif voucher_type == "BANK_RECEIPT":
            check_text(reasons, body.get("receipt_no"), at + ".receipt_no")
            check_text(reasons, body.get("bank_txn_id"), at + ".bank_txn_id")
            check_text(reasons, body.get("counterparty_name"),
                       at + ".counterparty_name")
            check_text(reasons, body.get("counterparty_account"),
                       at + ".counterparty_account")
            check_date(reasons, body.get("txn_date"), at + ".txn_date")
            check_int(reasons, body.get("amount_cents"), at + ".amount_cents")
            if body.get("direction") not in ("PAY", "REFUND"):
                add_reason(reasons, "ENUM", at + ".direction",
                           "必须为 PAY 或 REFUND", actual=body.get("direction"))
            check_currency(reasons, body.get("currency"), at + ".currency",
                           manifest_currency)
        elif voucher_type == "APPROVAL":
            check_text(reasons, body.get("approval_no"), at + ".approval_no")
            check_text(reasons, body.get("payment_id"), at + ".payment_id")
            check_date(reasons, body.get("approval_date"), at + ".approval_date")
            check_int(reasons, body.get("amount_cents"), at + ".amount_cents")
            if body.get("status") != "APPROVED":
                add_reason(reasons, "ENUM", at + ".status",
                           "必须为 APPROVED", actual=body.get("status"))
        elif voucher_type == "GOODS_RECEIPT":
            check_text(reasons, body.get("gr_no"), at + ".gr_no")
            check_text(reasons, body.get("supplier_id"), at + ".supplier_id")
            check_date(reasons, body.get("accept_date"), at + ".accept_date")
            check_int(reasons, body.get("amount_cents"), at + ".amount_cents")
            check_currency(reasons, body.get("currency"), at + ".currency",
                           manifest_currency)


def validate_bank_transactions(reasons: Reasons, records, relative):
    bank_txn_ids = set()
    for index, record in enumerate(records):
        at = "%s[%d]" % (relative, index)
        if not check_closed_keys(reasons, record, BANK_TXN_KEYS, at):
            continue
        txn_id = record.get("bank_txn_id")
        if check_text(reasons, txn_id, at + ".bank_txn_id"):
            if txn_id in bank_txn_ids:
                add_reason(reasons, "ID_DUPLICATE", at + ".bank_txn_id",
                           "bank_txn_id 必须唯一", actual=txn_id)
            bank_txn_ids.add(txn_id)
        check_date(reasons, record.get("txn_date"), at + ".txn_date")
        check_int(reasons, record.get("amount_cents"), at + ".amount_cents")
        if record.get("direction") not in ("OUT", "IN"):
            add_reason(reasons, "ENUM", at + ".direction",
                       "必须为 OUT 或 IN", actual=record.get("direction"))
        for key in ("counterparty_name", "counterparty_account", "summary"):
            check_text(reasons, record.get(key), at + "." + key)
        reference = record.get("reference")
        if reference is not None and not is_nonempty_text(reference):
            add_reason(reasons, "TYPE", at + ".reference",
                       "reference 必须为 null 或非空原字符串",
                       actual=type(reference).__name__)
    return bank_txn_ids


def validate_links(reasons: Reasons, records, relative, vouchers, ledger):
    link_ids = set()
    signatures = set()
    for index, record in enumerate(records):
        at = "%s[%d]" % (relative, index)
        if not check_closed_keys(reasons, record, LINK_KEYS, at):
            continue
        link_id = record.get("link_id")
        if check_text(reasons, link_id, at + ".link_id"):
            if link_id in link_ids:
                add_reason(reasons, "LINK_ID_DUPLICATE", at + ".link_id",
                           "link_id 必须唯一", actual=link_id)
            link_ids.add(link_id)
        link_type = record.get("link_type")
        ledger_type = record.get("ledger_type")
        ledger_id = record.get("ledger_id")
        voucher_id = record.get("voucher_id")
        if link_type not in LINK_TYPE_LEDGER:
            add_reason(reasons, "ENUM", at + ".link_type",
                       "必须为固定 link_type 之一", actual=link_type)
        if ledger_type not in LEDGER_TYPES:
            add_reason(reasons, "ENUM", at + ".ledger_type",
                       "必须为 AP/PAYMENT/REFUND", actual=ledger_type)
        if not check_text(reasons, ledger_id, at + ".ledger_id"):
            ledger_id = None
        if not check_text(reasons, voucher_id, at + ".voucher_id"):
            voucher_id = None
        if link_type in LINK_TYPE_LEDGER and ledger_type is not None:
            expected_ledger, expected_voucher = LINK_TYPE_LEDGER[link_type]
            if ledger_type != expected_ledger:
                add_reason(reasons, "LINK_TYPE_MISMATCH", at + ".ledger_type",
                           "link_type %s 对应 ledger_type %s" % (link_type, expected_ledger),
                           expected=expected_ledger, actual=ledger_type)
            if voucher_id is not None and voucher_id in vouchers:
                if vouchers[voucher_id]["type"] != expected_voucher:
                    add_reason(reasons, "LINK_TYPE_MISMATCH", at + ".voucher_id",
                               "link_type %s 需要 %s 凭证" % (link_type, expected_voucher),
                               expected=expected_voucher,
                               actual=vouchers[voucher_id]["type"])
            elif voucher_id is not None:
                add_reason(reasons, "LINK_VOUCHER", at + ".voucher_id",
                           "voucher_id 不存在", actual=voucher_id)
            if ledger_type in LEDGER_TYPES and ledger_id is not None:
                if ledger_id not in ledger[ledger_type]:
                    add_reason(reasons, "LINK_LEDGER", at + ".ledger_id",
                               "ledger_id 在批次 %s 账务中不存在" % ledger_type,
                               actual=ledger_id)
                signature = (link_type, ledger_id, voucher_id)
                if signature in signatures:
                    add_reason(reasons, "LINK_DUPLICATE", at,
                               "同一 (link_type, ledger_id, voucher_id) 不得重复",
                               actual=list(signature))
                signatures.add(signature)


def validate_cross_references(reasons: Reasons, vouchers, payments_by_type, bank_txns):
    for voucher_id, entry in sorted(vouchers.items()):
        record = entry["record"]
        at = "%s[%d]" % (entry["file"], entry["index"])
        if entry["type"] == "APPROVAL":
            payment_id = record.get("payment_id")
            if is_nonempty_text(payment_id) and payment_id not in payments_by_type["PAY"]:
                add_reason(reasons, "APPROVAL_PAYMENT", at + ".payment_id",
                           "payment_id 在批次 PAY 付款中不存在",
                           actual=payment_id, voucher_id=voucher_id)
        elif entry["type"] == "BANK_RECEIPT":
            bank_txn_id = record.get("bank_txn_id")
            direction = record.get("direction")
            if is_nonempty_text(bank_txn_id):
                txn = bank_txns.get(bank_txn_id)
                if txn is None:
                    add_reason(reasons, "BANK_TXN_REFERENCE", at + ".bank_txn_id",
                               "bank_txn_id 在银行流水中不存在",
                               actual=bank_txn_id, voucher_id=voucher_id)
                else:
                    expected = "OUT" if direction == "PAY" else "IN"
                    if txn.get("direction") != expected:
                        add_reason(reasons, "BANK_TXN_REFERENCE", at + ".bank_txn_id",
                                   "回单方向与银行流水方向不匹配",
                                   expected=expected, actual=txn.get("direction"),
                                   voucher_id=voucher_id)


def load_ledger(db_path: Path) -> dict:
    if not db_path.is_file():
        raise ContractUsageError("ledger 数据库不存在：%s" % db_path)
    _reject_reparse(db_path, "ledger_db")
    uri = "file:%s?mode=ro&immutable=1" % db_path.resolve().as_posix()
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise ContractUsageError("无法只读打开 ledger 数据库：%s" % exc)
    try:
        cursor = connection.cursor()
        ap_ids = {row[0] for row in cursor.execute("SELECT ap_id FROM payables")}
        payments = {}
        for payment_id, transaction_type in cursor.execute(
                "SELECT payment_id, transaction_type FROM payments"):
            payments.setdefault(transaction_type, set()).add(payment_id)
        return {"AP": ap_ids, "PAYMENT": payments.get("PAY", set()),
                "REFUND": payments.get("REFUND", set()),
                "payments_by_type": {"PAY": payments.get("PAY", set()),
                                     "REFUND": payments.get("REFUND", set())}}
    except sqlite3.Error as exc:
        raise ContractUsageError("ledger 数据库结构不符合预期：%s" % exc)
    finally:
        connection.close()


def expected_file_set(files):
    actual = set(files)
    expected = set(EXPECTED_FILES) | {MANIFEST_FILE}
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    return missing, unknown


def run(input_root: Path, out_dir: Path, ledger_db: Path) -> int:
    if out_dir.exists():
        raise ContractUsageError("--out 必须从未存在：%s" % out_dir)
    if out_dir == input_root or input_root in out_dir.parents:
        raise ContractUsageError("--out 不得位于输入根内")
    try:
        out_dir.resolve().relative_to(EVIDENCE_ROOT.resolve())
    except ValueError:
        raise ContractUsageError("--out 必须位于 %s 之下" % EVIDENCE_ROOT)
    if not out_dir.name.startswith("task043_"):
        raise ContractUsageError("--out 目录名必须以 task043_ 开头")

    ledger = load_ledger(ledger_db)
    ledger_identity = {"relative": _relative(ledger_db),
                       "byte_size": ledger_db.stat().st_size,
                       "sha256": sha_bytes(ledger_db.read_bytes())}
    files = read_input_root(input_root)
    reasons = Reasons()

    manifest = None
    missing, unknown = expected_file_set(files)
    for relative in missing:
        add_reason(reasons, "MISSING_FILE", relative, "缺少固定输入文件")
    for relative in unknown:
        add_reason(reasons, "UNKNOWN_FILE", relative, "固定文件集之外的未知文件")
    manifest_entry = files.get(MANIFEST_FILE)
    if manifest_entry is None:
        add_reason(reasons, "MANIFEST_MISSING", MANIFEST_FILE, "缺少输入清单")
    else:
        manifest_raw = _read_bytes(manifest_entry)
        try:
            manifest = parse_strict_json(manifest_raw)
        except (UnicodeDecodeError, ValueError) as exc:
            add_reason(reasons, "MANIFEST_INVALID", MANIFEST_FILE,
                       "清单不是合法 UTF-8 JSON：%s" % exc)
        if manifest is not None:
            validate_manifest(reasons, manifest, files)

    manifest_files = {}
    if type(manifest) is dict and type(manifest.get("files")) is list:
        for entry in manifest["files"]:
            if type(entry) is dict and type(entry.get("relative")) is str:
                manifest_files[entry["relative"]] = entry

    voucher_ids = {}
    vouchers = {}
    bank_txns = {}
    for relative, voucher_type in VOUCHER_FILES.items():
        path = files.get(relative)
        if path is None:
            continue
        raw = _read_bytes(path, reasons, relative)
        if raw is None:
            continue
        records = _parse_records(reasons, raw, relative)
        if records is None:
            continue
        validate_file_hash(reasons, relative, raw, manifest_files.get(relative))
        validate_vouchers(reasons, records, relative, voucher_type,
                          (manifest or {}).get("entity", {}).get("currency")
                          if type((manifest or {}).get("entity")) is dict else None,
                          vouchers, voucher_ids)
    bank_relative = "bank/transactions.json"
    if bank_relative in files:
        raw = _read_bytes(files[bank_relative], reasons, bank_relative)
        if raw is not None:
            records = _parse_records(reasons, raw, bank_relative)
            if records is not None:
                validate_file_hash(reasons, bank_relative, raw,
                                   manifest_files.get(bank_relative))
                validate_bank_transactions(reasons, records, bank_relative)
                for record in records:
                    txn_id = record.get("bank_txn_id")
                    if is_nonempty_text(txn_id):
                        bank_txns.setdefault(txn_id, record)
    links_relative = "links/index.json"
    if links_relative in files:
        raw = _read_bytes(files[links_relative], reasons, links_relative)
        if raw is not None:
            records = _parse_records(reasons, raw, links_relative)
            if records is not None:
                validate_file_hash(reasons, links_relative, raw,
                                   manifest_files.get(links_relative))
                validate_links(reasons, records, links_relative, vouchers, ledger)
    reports_relative = "reports/placeholders.json"
    if reports_relative in files:
        raw = _read_bytes(files[reports_relative], reasons, reports_relative)
        if raw is not None:
            records = _parse_records(reasons, raw, reports_relative)
            if records is not None:
                validate_file_hash(reasons, reports_relative, raw,
                                   manifest_files.get(reports_relative))
                if records:
                    add_reason(reasons, "REPORTS_PLACEHOLDER", reports_relative,
                               "本卡不做账表，占位文件必须为空数组",
                               actual=len(records))
    validate_cross_references(reasons, vouchers, ledger["payments_by_type"], bank_txns)

    if reasons:
        out_dir.mkdir(parents=True, exist_ok=False)
        payload = {
            "rejection_version": REJECTION_VERSION,
            "input_version": (manifest.get("input_version")
                               if type(manifest) is dict else None),
            "batch_id": BATCH_ID,
            "input_root": _relative(input_root),
            "ledger_source": ledger_identity,
            "reason_count": len(reasons.items),
            "reasons": reasons.items,
            "summary": {"first": reasons.items[0] if reasons.items else None,
                        "note": "整批拒收：不修、不补、不猜；未生成 input_registry.json"},
            "boundaries": dict(BOUNDARIES),
        }
        _write_json(out_dir / "rejection.json", payload)
        print(json.dumps({"status": "REJECTED", "reason_count": len(reasons.items),
                          "first": reasons.items[0],
                          "out": str(out_dir)}, ensure_ascii=False))
        return 1

    counts = {}
    for relative, voucher_type in VOUCHER_FILES.items():
        path = files.get(relative)
        records = json.loads(path.read_bytes().decode("utf-8")) if path else []
        counts[voucher_type] = len(records)
    link_records = json.loads(files[links_relative].read_bytes().decode("utf-8"))
    bank_records = json.loads(files[bank_relative].read_bytes().decode("utf-8"))
    report_records = json.loads(files[reports_relative].read_bytes().decode("utf-8"))
    file_entries = []
    for relative in sorted(EXPECTED_FILES):
        raw = files[relative].read_bytes()
        file_entries.append({"relative": relative, "byte_size": len(raw),
                             "file_sha256": sha_bytes(raw)})
    registry = {
        "registry_version": REGISTRY_VERSION,
        "input_version": manifest["input_version"],
        "batch_id": BATCH_ID,
        "entity": manifest["entity"],
        "input_root": _relative(input_root),
        "ledger_source": ledger_identity,
        "files": file_entries,
        "counts": {"vouchers": counts, "voucher_total": sum(counts.values()),
                   "links": len(link_records), "bank_transactions": len(bank_records),
                   "reports_placeholders": len(report_records)},
        "checks": {"file_set": "PASS", "utf8_json_arrays": "PASS",
                   "record_schema_types_enums": "PASS", "amounts_integer_cents": "PASS",
                   "dates_within_contract": "PASS", "currency_and_entity": "PASS",
                   "invoice_arithmetic": "PASS", "manifest_hashes": "PASS",
                   "index_references": "PASS", "ledger_ids_exist": "PASS",
                   "index_duplicates": "PASS"},
        "conclusion": "INPUT_V1_ACCEPTED",
        "boundaries": dict(BOUNDARIES),
    }
    out_dir.mkdir(parents=True, exist_ok=False)
    payload = canon(registry) + b"\n"
    target = out_dir / "input_registry.json"
    target.write_bytes(payload)
    readback = target.read_bytes()
    if readback != payload:
        raise ContractUsageError("input_registry.json 同缓冲读回不一致")
    _write_json(out_dir / "registry_readback.json",
                {"same_buffer_readback": True, "byte_size": len(payload),
                 "file_sha256": sha_bytes(payload),
                 "registry_relative": _relative(target)})
    print(json.dumps({"status": "ACCEPTED", "registry": str(target),
                      "registry_sha256": sha_bytes(payload),
                      "counts": registry["counts"],
                      "ledger_source": ledger_identity["relative"]},
                     ensure_ascii=False))
    return 0


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def _read_bytes(path: Path, reasons=None, field=None):
    try:
        return path.read_bytes()
    except OSError as exc:
        if reasons is None:
            raise ContractUsageError("无法读取 %s：%s" % (path, exc))
        add_reason(reasons, "FILE_READ_ERROR", field or str(path),
                   "无法读取文件字节：%s" % exc)
        return None


def _parse_records(reasons, raw, relative):
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        add_reason(reasons, "FILE_NOT_UTF8", relative, "必须是合法 UTF-8：%s" % exc)
        return None
    try:
        value = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        add_reason(reasons, "FILE_BAD_JSON", relative, "必须是合法 JSON：%s" % exc)
        return None
    if type(value) is not list:
        add_reason(reasons, "FILE_NOT_ARRAY", relative,
                   "顶层必须是记录数组", actual=type(value).__name__)
        return None
    return value


def validate_file_hash(reasons, relative, raw, manifest_entry):
    if manifest_entry is None:
        return
    if type(manifest_entry.get("byte_size")) is int \
            and manifest_entry["byte_size"] != len(raw):
        add_reason(reasons, "HASH_MISMATCH", relative + "#byte_size",
                   "实际字节数与清单不一致",
                   expected=manifest_entry.get("byte_size"), actual=len(raw))
    if type(manifest_entry.get("sha256")) is str \
            and manifest_entry["sha256"] != sha_bytes(raw):
        add_reason(reasons, "HASH_MISMATCH", relative + "#sha256",
                   "实际字节 SHA-256 与清单不一致",
                   expected=manifest_entry.get("sha256"),
                   actual=sha_bytes(raw))


def _write_json(path: Path, value) -> bytes:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    path.write_bytes(payload)
    readback = path.read_bytes()
    if readback != payload:
        raise ContractUsageError("写后读回不一致：%s" % path)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-043 输入契约 v1 校验与输入登记")
    parser.add_argument("--input", required=True, help="输入根（只读）")
    parser.add_argument("--out", required=True, help="证据根（必须从未存在）")
    parser.add_argument("--ledger-db", dest="ledger_db", required=True,
                        help="既有批次账务只读 SQLite 路径")
    args = parser.parse_args(argv)
    try:
        return run(Path(args.input), Path(args.out), Path(args.ledger_db))
    except ContractUsageError as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
