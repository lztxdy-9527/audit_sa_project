#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-050：证据链底稿 .xlsx（可点击定位到原始表行单元格）。

命令行：
    python -B scripts/build_excel_workbook.py --index <trace_index.json> --out-dir <新证据根>

只读 TASK-048 已接受的 `trace_index.json`，用项目既有 openpyxl 生成《证据链底稿.xlsx》：
说明 / 问题清单 / 台账明细 / 原始表行 / 凭证 / 图像占位。问题清单与台账明细的金额/凭证号/查看原行
使用 Excel 内部定位语法 `#'Sheet'!Cell` 指向《原始表行》或《台账明细》对应单元格；仅"打开原始工作簿"
一个外部链接。数值只复制不重算（元 = 分/100，分保持整数）。

边界：只读展示既有合成证据；不是批次批准、不是身份认证；`real_approval=null`、
真实独立初判未保存、`next_step_allowed=false`、`ai_enabled=false`；不证明凭证/流水真实，
不构成审计结论；核对结论由审计人员填写。
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import time
import zipfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
ORIGINAL_WORKBOOK = ROOT / "data/batches/task027r1_run_04/batch_normal/source/input.xlsx"
WORKBOOK_NAME = "证据链底稿.xlsx"
GENERATOR = "scripts/build_excel_workbook.py"
BANNER = "合成数据；不是批次批准；不是审计结论；资料版本以资料接收记录为准。"
USAGE = ("单击带下划线的金额或凭证号可定位到《原始表行》对应单元格；"
         "双击是进入单元格编辑，不会触发链接。")
IMAGE_TEXT = "模拟数据，当前无对应真实凭证图像"
CONFIRM_TEXT = "由审计人员填写"
SHEET_NAMES = ("说明", "问题清单", "台账明细", "原始表行", "凭证", "图像占位")
GL_SHEET_NAMES = ("科目余额表", "记账凭证", "总账", "明细账", "账表核对", "银行调节", "核对结果")
LEDGER_TYPE_LABEL = {"AP": "应付单", "PAYMENT": "付款", "REFUND": "退款",
                     "ALLOCATION": "分摊"}
VOUCHER_TYPE_LABEL = {"INVOICE": "发票", "CONTRACT": "合同",
                      "BANK_RECEIPT": "银行回单", "APPROVAL": "审批单",
                      "GOODS_RECEIPT": "入库单"}
FIELD_LABEL = {
    "ap_id": "应付单编号", "ap_number": "应付单号", "supplier_id": "供应商编号",
    "ap_date": "应付日期", "payable_amount_cents": "应付金额（分）", "currency": "币种",
    "payment_id": "付款编号", "transaction_type": "交易类型",
    "original_payment_id": "原付款编号", "payee_supplier_id": "收款供应商",
    "payment_date": "日期", "amount_cents": "金额（分）",
    "settlement_status": "结算状态", "bank_reference": "银行参考号",
    "allocation_id": "分摊编号", "allocated_amount_cents": "分摊金额（分）",
    "original_allocation_id": "原分摊编号",
}
VOUCHER_FIELD_LABEL = {
    "voucher_id": "凭证编号", "invoice_no": "发票号", "issue_date": "开票日期",
    "seller_supplier_id": "销售方编号", "seller_name": "销售方",
    "buyer_name": "购买方", "amount_cents": "金额（分）", "tax_cents": "税额（分）",
    "total_cents": "价税合计（分）", "currency": "币种", "contract_no": "合同号",
    "sign_date": "签订日期", "counterparty_supplier_id": "对方编号",
    "counterparty_name": "对方", "receipt_no": "回单号", "bank_txn_id": "流水号",
    "txn_date": "回单日期", "direction": "方向", "counterparty_account": "对方账号",
    "approval_no": "审批单号", "approval_date": "审批日期", "payment_id": "付款编号",
    "status": "状态", "gr_no": "入库单号", "accept_date": "验收日期",
}
TXN_LABEL = {"PAY": "付款", "REFUND": "退款", "OUT": "付款", "IN": "收款"}
STATUS_LABEL = {"SETTLED": "已结算", "APPROVED": "已批准", "PENDING": "待结算"}
SEVERITY_LABEL = {"red": "差异", "yellow": "待核查", "green": "已核对"}
KIND_LABEL = {"RULE_FINDING": "待核查线索", "VOUCHER_DIFFERENCE": "凭证差异",
              "VOUCHER_MISSING": "未取得凭证", "BANK_DIFFERENCE": "银行流水差异",
              "BANK_UNMATCHED": "账有实无", "BANK_UNMATCHED_BANK": "实有账无",
              "MULTI_SOURCE": "多来源差异"}
SEVERITY_FILL = {"red": PatternFill("solid", fgColor="FDE8E8"),
                 "yellow": PatternFill("solid", fgColor="FFF8D6"),
                 "green": PatternFill("solid", fgColor="E6FFEC")}
HEADER_FILL = PatternFill("solid", fgColor="F6F8FA")
HIGHLIGHT_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="D0D7DE")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
AMOUNT_FONT = Font(bold=True, underline="single", color="1F6FEB")
FORBIDDEN_WORDS = ("JSON", "hash", "SHA", "API", "script", "pipeline", "解析",
                   "字段类型", "字节", "编码", "版本号")


CORE_MODIFIED = re.compile(r"<dcterms:modified[^>]*>[^<]*</dcterms:modified>")


def normalize_workbook(path: Path) -> None:
    """以固定 zip 时间与固定核心属性重写工作簿，保证同输入字节一致。"""
    source = zipfile.ZipFile(path)
    entries = [(info.filename, source.read(info)) for info in source.infolist()]
    source.close()
    target = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            if name == "docProps/core.xml":
                replacement = ('<dcterms:modified xsi:type="dcterms:W3CDTF">'
                               '2026-10-17T00:00:00Z</dcterms:modified>')
                data = CORE_MODIFIED.sub(replacement,
                                         data.decode("utf-8")).encode("utf-8")
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, data)
    for attempt in range(20):
        try:
            if path.exists():
                path.unlink()
            target.rename(path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.2)


class WorkbookError(Exception):
    def __init__(self, kind, message, field=None):
        super().__init__(message)
        self.kind = kind
        self.field = field


def read_json(path: Path):
    return json.loads(path.read_bytes())


def load_index(path: Path) -> dict:
    if not path.is_file():
        raise WorkbookError("usage", "索引不存在：%s" % path)
    try:
        index = read_json(path)
    except ValueError as exc:
        raise WorkbookError("content", "索引不是合法内容：%s" % exc, field="trace_index.json")
    for key in ("cases", "ledger", "vouchers", "source_rows", "meta"):
        if key not in index:
            raise WorkbookError("content", "索引缺少必需部分：%s" % key,
                                field="trace_index.%s" % key)
    return index


def validate(index):
    ledger = {(row.get("ledger_type"), row.get("ledger_id")): row for row in index["ledger"]}
    vouchers = {row.get("voucher_id"): row for row in index["vouchers"]}
    sources = {(row.get("sheet"), row.get("excel_row")): row for row in index["source_rows"]}
    for case in index["cases"]:
        case_id = case.get("case_id")
        for ref in case.get("ledger_refs") or []:
            if (ref.get("ledger_type"), ref.get("ledger_id")) not in ledger:
                raise WorkbookError("content", "事项的账务引用无法展开：%s %s=%s"
                                    % (case_id, ref.get("ledger_type"), ref.get("ledger_id")),
                                    field="%s.ledger_refs.ledger_id=%s"
                                          % (case_id, ref.get("ledger_id")))
        for ref in case.get("voucher_refs") or []:
            if ref.get("voucher_id") and ref["voucher_id"] not in vouchers:
                raise WorkbookError("content", "事项的凭证引用无法展开：%s %s"
                                    % (case_id, ref["voucher_id"]),
                                    field="%s.voucher_refs.voucher_id=%s"
                                          % (case_id, ref["voucher_id"]))
        for ref in case.get("source_refs") or []:
            if (ref.get("sheet"), ref.get("excel_row")) not in sources:
                raise WorkbookError("content", "事项的原始表行无法展开：%s %s!%s"
                                    % (case_id, ref.get("sheet"), ref.get("excel_row")),
                                    field="%s.source_refs.sheet=%s"
                                          % (case_id, ref.get("sheet")))
    return ledger, vouchers, sources


def find_source_row(row, sources):
    sheet = (row.get("source") or {}).get("sheet")
    ledger_type = row.get("ledger_type")
    target = row.get("ledger_id")
    id_column = {"AP": "A", "PAYMENT": "A", "REFUND": "A", "ALLOCATION": "A"}.get(ledger_type)
    primary, fallback = [], []
    for key in sorted(sources):
        if key[0] != sheet or key[1] is None:
            continue
        cells = sources[key].get("cells") or {}
        if id_column and id_column in cells:
            value = cells[id_column].get("standard_value")
            if value is None:
                value = cells[id_column].get("raw_value")
            if str(value) == str(target):
                primary.append(sources[key])
                continue
        for cell in cells.values():
            if str(cell.get("standard_value")) == str(target) \
                    or str(cell.get("raw_value")) == str(target):
                fallback.append(sources[key])
                break
    if len(primary) == 1:
        return primary[0]
    if not primary and len(fallback) == 1:
        return fallback[0]
    return None


def style_header(ws, row=1):
    for cell in ws[row]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"


def style_body(ws, width=None):
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    if width:
        for index, value in enumerate(width, start=1):
            ws.column_dimensions[get_column_letter(index)].width = value


def value_text(field, value):
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if field.endswith("_cents") and type(value) is int:
        return "%d 分（%.2f 元）" % (value, value / 100.0)
    if field in ("direction", "transaction_type"):
        return TXN_LABEL.get(str(value), str(value))
    if field in ("settlement_status", "status"):
        return STATUS_LABEL.get(str(value), str(value))
    return str(value)


def set_hyperlink(cell, target):
    cell.hyperlink = target
    cell.font = AMOUNT_FONT


def build_original_sheet(wb, sources, involved):
    ws = wb.create_sheet("原始表行")
    max_index = 1
    for row in sources.values():
        for column in (row.get("cells") or {}):
            if len(column) == 1:
                max_index = max(max_index, ord(column) - ord("A") + 1)
    letters = [get_column_letter(index) for index in range(1, max_index + 1)]
    header = ["工作表", "行号"] + letters + ["状态"]
    ws.append(header)
    style_header(ws)
    involved_rows = {(sheet, excel_row) for (sheet, excel_row, _column) in involved}
    row_map = {}
    for position, key in enumerate(sorted(sources), start=2):
        row = sources[key]
        values = [row.get("sheet"), row.get("excel_row")]
        cells = row.get("cells") or {}
        for index, letter in enumerate(letters, start=3):
            cell = cells.get(letter) or {}
            values.append(cell.get("raw_value"))
        values.append("已涉及" if (row.get("sheet"), row.get("excel_row")) in involved_rows
                     else "未涉及")
        ws.append(values)
        row_map[(row.get("sheet"), row.get("excel_row"))] = position
    for (sheet, excel_row, column) in involved:
        position = row_map.get((sheet, excel_row))
        if position is None or column not in letters:
            continue
        ws.cell(row=position, column=letters.index(column) + 3).fill = HIGHLIGHT_FILL
    style_body(ws, [14, 7] + [12] * len(letters) + [10])
    ws.auto_filter.ref = ("A1:%s%d" % (get_column_letter(ws.max_column), ws.max_row))
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return ws, row_map, letters


def target_address(sheet, excel_row, column, row_map, letters):
    position = row_map.get((sheet, excel_row))
    if position is None or column not in letters:
        return None
    column_index = letters.index(column) + 3
    return "'原始表行'!%s%d" % (get_column_letter(column_index), position)




def gl_accounts(gl):
    return {item.get("code"): item for item in
            (gl.get("chart_of_accounts") or {}).get("accounts") or []}


def gl_amount(ws, row, cents_columns, yuan_columns):
    for column in cents_columns:
        ws.cell(row=row, column=column).number_format = '#,##0'
    for column in yuan_columns:
        ws.cell(row=row, column=column).number_format = '#,##0.00'


def build_gl_sheets(wb, gl):
    accounts = gl_accounts(gl)
    trial = gl.get("trial_balance") or {}
    trial_rows = []
    trial_sheet = wb.create_sheet("科目余额表")
    trial_sheet.append(["科目编码", "科目名称", "类型", "期初借（分）", "期初贷（分）",
                        "本期借（分）", "本期贷（分）", "期末借（分）", "期末贷（分）",
                        "期末方向"])
    style_header(trial_sheet)
    for row in trial.get("rows") or []:
        code = row.get("account")
        info = accounts.get(code) or {}
        direction = "借" if row.get("closing_debit") else "贷"
        trial_sheet.append([code, info.get("name"), info.get("type"),
                            row.get("opening_debit"), row.get("opening_credit"),
                            row.get("debit_cents"), row.get("credit_cents"),
                            row.get("closing_debit"), row.get("closing_credit"),
                            direction])
        gl_amount(trial_sheet, trial_sheet.max_row, [4, 5, 6, 7, 8, 9], [])
        if code == "2202" and row.get("closing_debit"):
            for cell in trial_sheet[trial_sheet.max_row]:
                cell.fill = PatternFill("solid", fgColor="FFF8D6")
    totals = trial.get("totals") or {}
    trial_sheet.append(["合计", None, None, totals.get("opening_debit"),
                        totals.get("opening_credit"), totals.get("debit_cents"),
                        totals.get("credit_cents"), totals.get("closing_debit"),
                        totals.get("closing_credit"), None])
    gl_amount(trial_sheet, trial_sheet.max_row, [4, 5, 6, 7, 8, 9], [])
    style_body(trial_sheet, [10, 16, 10, 12, 12, 12, 12, 12, 12, 8])
    trial_sheet.freeze_panes = "A2"
    trial_sheet.auto_filter.ref = ("A1:%s%d" % (get_column_letter(trial_sheet.max_column),
                                               trial_sheet.max_row))
    trial_sheet.sheet_view.showGridLines = False
    trial_rows = {row.get("account"): row for row in trial.get("rows") or []}

    journal = wb.create_sheet("记账凭证")
    journal.append(["凭证号", "日期", "摘要", "行", "科目编码", "科目名称", "借方（分）",
                    "借方（元）", "贷方（分）", "贷方（元）", "附件", "关联账务"])
    style_header(journal)
    for entry in gl.get("journal_entries") or []:
        for index, line in enumerate(entry.get("lines") or [], start=1):
            code = line.get("account")
            info = accounts.get(code) or {}
            journal.append([entry.get("entry_id"), entry.get("date"),
                            entry.get("summary"), index, code, info.get("name"),
                            line.get("debit_cents"),
                            round(line.get("debit_cents", 0) / 100.0, 2),
                            line.get("credit_cents"),
                            round(line.get("credit_cents", 0) / 100.0, 2),
                            "、".join(entry.get("attachments") or []),
                            "、".join(ref.get("ledger_id") for ref in
                                     entry.get("ledger_refs") or [])])
            gl_amount(journal, journal.max_row, [7, 9], [8, 10])
    style_body(journal, [10, 11, 24, 5, 9, 14, 12, 12, 12, 12, 26, 12])
    journal.freeze_panes = "A2"
    journal.auto_filter.ref = ("A1:%s%d" % (get_column_letter(journal.max_column),
                                            journal.max_row))
    journal.sheet_view.showGridLines = False

    general = wb.create_sheet("总账")
    general.append(["科目编码", "科目名称", "本期借（分）", "本期贷（分）", "期末借（分）",
                    "期末贷（分）", "期末方向"])
    style_header(general)
    for row in (gl.get("ledger_general") or {}).get("accounts") or []:
        code = row.get("account")
        general.append([code, (accounts.get(code) or {}).get("name"),
                        row.get("debit_cents"), row.get("credit_cents"),
                        row.get("closing_debit"), row.get("closing_credit"),
                        "借" if row.get("closing_debit") else "贷"])
        gl_amount(general, general.max_row, [3, 4, 5, 6], [])
    style_body(general, [10, 16, 12, 12, 12, 12, 8])
    general.freeze_panes = "A2"
    general.auto_filter.ref = ("A1:%s%d" % (get_column_letter(general.max_column),
                                            general.max_row))
    general.sheet_view.showGridLines = False

    subsidiary = wb.create_sheet("明细账")
    subsidiary.append(["明细名称", "科目", "对象", "日期", "凭证号", "借方（分）",
                       "贷方（分）", "余额方向", "余额（分）"])
    style_header(subsidiary)
    for item in (gl.get("ledger_subsidiary") or {}).get("subsidiaries") or []:
        for row in item.get("entries") or []:
            direction = "借" if row.get("balance_debit") else "贷"
            amount = row.get("balance_debit") or row.get("balance_credit")
            subsidiary.append([item.get("name"), item.get("account"),
                               item.get("object"), row.get("date"),
                               row.get("entry_id"), row.get("debit_cents"),
                               row.get("credit_cents"), direction, amount])
            gl_amount(subsidiary, subsidiary.max_row, [6, 7, 9], [])
    style_body(subsidiary, [22, 9, 10, 11, 10, 12, 12, 8, 12])
    subsidiary.freeze_panes = "A2"
    subsidiary.auto_filter.ref = ("A1:%s%d" % (get_column_letter(subsidiary.max_column),
                                               subsidiary.max_row))
    subsidiary.sheet_view.showGridLines = False

    report_sheet = wb.create_sheet("账表核对")
    report_sheet.append(["报表项目", "科目余额表（分）", "报表金额（分）", "差异（分）", "说明"])
    style_header(report_sheet)
    sheet = gl.get("balance_sheet") or {}
    def signed(code):
        row = trial_rows.get(code) or {}
        return row.get("closing_debit", 0) - row.get("closing_credit", 0)
    mapping = [("货币资金", "1002", signed("1002")),
               ("存货", "1001", signed("1001")),
               ("预付账款", "2202 借方", max(0, signed("2202"))),
               ("应付账款", "2202 贷方", max(0, -signed("2202"))),
               ("实收资本", "3001", max(0, -signed("3001")))]
    actual = {}
    for group in ("assets", "liabilities", "equity"):
        for item in sheet.get(group) or []:
            actual[item.get("item")] = item.get("amount_cents")
    for item, source, value in mapping:
        reported = actual.get(item)
        diff = value - reported if type(reported) is int else None
        report_sheet.append([item, value, reported, diff,
                             "应付借方余额重分类" if item == "预付账款" else None])
        gl_amount(report_sheet, report_sheet.max_row, [2, 3, 4], [])
    assets = sum(item.get("amount_cents", 0) for item in sheet.get("assets") or [])
    other = sum(item.get("amount_cents", 0) for item in sheet.get("liabilities") or []) + \
        sum(item.get("amount_cents", 0) for item in sheet.get("equity") or [])
    report_sheet.append(["资产合计", sheet.get("total_assets_cents"), assets,
                         (sheet.get("total_assets_cents") or 0) - assets, None])
    report_sheet.append(["负债 + 权益合计", sheet.get("total_liabilities_equity_cents"),
                         other, (sheet.get("total_liabilities_equity_cents") or 0) - other,
                         "资产 = 负债 + 权益"])
    gl_amount(report_sheet, report_sheet.max_row - 1, [2, 3, 4], [])
    gl_amount(report_sheet, report_sheet.max_row, [2, 3, 4], [])
    style_body(report_sheet, [16, 16, 14, 10, 26])
    report_sheet.freeze_panes = "A2"
    report_sheet.auto_filter.ref = ("A1:%s%d" % (get_column_letter(report_sheet.max_column),
                                                 report_sheet.max_row))
    report_sheet.sheet_view.showGridLines = False

    bank = wb.create_sheet("银行调节")
    statement = gl.get("bank_statement") or {}
    journal_data = gl.get("bank_journal") or {}
    entries = statement.get("entries") or []
    inflow = sum(item.get("amount_cents", 0) for item in entries
                 if item.get("direction") == "IN")
    outflow = sum(item.get("amount_cents", 0) for item in entries
                  if item.get("direction") == "OUT")
    bank.append(["项目", "金额（分）", "金额（元）"])
    style_header(bank)
    for label, cents in (("期初余额", statement.get("opening_balance_cents")),
                         ("加：收入", inflow), ("减：支出", outflow),
                         ("期末余额（对账单）", statement.get("closing_balance_cents")),
                         ("期末余额（日记账）", journal_data.get("closing_balance_cents"))):
        bank.append([label, cents, round(cents / 100.0, 2) if type(cents) is int else None])
        gl_amount(bank, bank.max_row, [2], [3])
    bank_check = next((item for item in gl.get("checks") or []
                       if item.get("id") == "bank_reconcile"), {})
    journal_only = sum(1 for finding in bank_check.get("findings") or []
                       if finding.get("side") == "账有实无")
    statement_only = sum(1 for finding in bank_check.get("findings") or []
                         if finding.get("side") == "实有账无")
    bank.append(["账有实无（笔）", journal_only, None])
    bank.append(["实有账无（笔）", statement_only, None])
    style_body(bank, [22, 14, 14])
    bank.freeze_panes = "A2"
    bank.auto_filter.ref = ("A1:%s%d" % (get_column_letter(bank.max_column),
                                         bank.max_row))
    bank.sheet_view.showGridLines = False

    checks = wb.create_sheet("核对结果")
    checks.append(["检查项", "状态", "差异数", "备注"])
    style_header(checks)
    for check in gl.get("checks") or []:
        checks.append([check.get("title"), check.get("status"),
                       len(check.get("findings") or []), None])
    for note in (gl.get("summary") or {}).get("notes") or []:
        checks.append(["备注", None, None, note])
    for item in gl.get("unperformed") or []:
        checks.append(["未执行", None, None, item])
    style_body(checks, [20, 12, 8, 60])
    checks.freeze_panes = "A2"
    checks.auto_filter.ref = ("A1:%s%d" % (get_column_letter(checks.max_column),
                                           checks.max_row))
    checks.sheet_view.showGridLines = False
    return list(GL_SHEET_NAMES)

def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-050 证据链底稿 .xlsx")
    parser.add_argument("--index", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    index_path = Path(args.index)
    out_dir = Path(args.out_dir)
    try:
        if not index_path.is_file():
            raise WorkbookError("usage", "索引不存在：%s" % index_path)
        try:
            out_dir.resolve().relative_to(TEST_ROOT.resolve())
        except ValueError:
            raise WorkbookError("usage", "--out-dir 必须位于 %s 之下" % TEST_ROOT)
        if out_dir.exists():
            raise WorkbookError("usage", "--out-dir 必须从未存在：%s" % out_dir)
        if not out_dir.name.startswith(("task050_", "task051_", "task052_",
                                        "task057_")):
            raise WorkbookError("usage", "--out-dir 目录名必须以 task050_、task051_ 或 task052_ 开头")
        index = load_index(index_path)
        ledger, vouchers, sources = validate(index)
        involved = {(ref.get("sheet"), ref.get("excel_row"), ref.get("column_letter"))
                    for case in index["cases"] for ref in case.get("source_refs") or []}
        wb = Workbook()
        wb.properties.created = datetime.datetime(2026, 10, 17)
        wb.properties.modified = datetime.datetime(2026, 10, 17)
        wb.remove(wb.active)
        info = wb.create_sheet("说明")
        info["A1"] = BANNER
        info["A1"].font = Font(bold=True, color="B71C1C")
        info["A1"].fill = PatternFill("solid", fgColor="FFF3CD")
        info["A2"] = "使用说明"
        info["A2"].font = Font(bold=True)
        info["A3"] = USAGE
        info["A4"] = "打开原始工作簿"
        set_hyperlink(info["A4"], ORIGINAL_WORKBOOK.as_posix())
        info["A5"] = "资料接收记录"
        info["A5"].font = Font(bold=True)
        info["A6"] = "接收日期"
        info["B6"] = "以资料接收记录为准"
        info["A7"] = "资料名称"
        info["B7"] = "合成采购付款数据（应付、付款/退款、分摊及凭证）"
        info["A8"] = "份数"
        info["B8"] = "账务四类、凭证五类（发票、合同、银行回单、审批单、入库单）"
        info["A9"] = "核对结论"
        info["B9"] = CONFIRM_TEXT
        info["A10"] = "备份纪律"
        info["B10"] = ("源文件只在接收时留存一份，生成不复制源；每次生成只新增小文件；"
                       "项目内不删除旧证据。")
        for row in info.iter_rows(min_row=2, max_row=9):
            for cell in row:
                cell.border = BORDER
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        info.column_dimensions["A"].width = 18
        info.column_dimensions["B"].width = 80
        info.sheet_view.showGridLines = False

        original, row_map, letters = build_original_sheet(wb, sources, involved)

        issues = wb.create_sheet("问题清单")
        headers = ["编号", "事项", "类别", "严重程度", "金额（元）", "金额（分）",
                   "应为", "实为", "差额", "涉及账务", "凭证", "状态", "定位链接"]
        issues.append(headers)
        style_header(issues)
        issue_row_map = {}
        for position, case in enumerate(index["cases"], start=2):
            amounts = case.get("amounts") or []
            primary = amounts[-1] if amounts else {}
            cents = primary.get("cents")
            expected = actual = None
            for block in case.get("evidence_blocks") or []:
                if type(block.get("expected")) is int:
                    expected = block["expected"]
                if type(block.get("actual")) is int:
                    actual = block["actual"]
            expected_display = value_text("x_cents", expected) if expected is not None else ""
            actual_display = value_text("x_cents", actual) if actual is not None else ""
            difference = expected - actual if expected is not None and actual is not None else None
            ledger_text = "、".join("%s %s" % (LEDGER_TYPE_LABEL.get(ref.get("ledger_type"), "账务"),
                                              ref.get("ledger_id"))
                                    for ref in case.get("ledger_refs") or [])
            voucher_text = "、".join(
                "%s %s" % (VOUCHER_TYPE_LABEL.get(ref.get("voucher_type"), "凭证"),
                           ref.get("voucher_id") or "（未取得）")
                for ref in case.get("voucher_refs") or [])
            source = (case.get("source_refs") or [None])[0]
            target = None
            if source:
                target = target_address(source.get("sheet"), source.get("excel_row"),
                                        source.get("column_letter"), row_map, letters)
            if target is None and (case.get("ledger_refs") or []):
                ref = case["ledger_refs"][0]
                ledger_row = ledger.get((ref.get("ledger_type"), ref.get("ledger_id")))
                if ledger_row is not None:
                    target = "'台账明细'!A%d" % 2
            issues.append([case.get("case_id"), case.get("title"),
                           KIND_LABEL.get(case.get("kind"), "待核查"),
                           SEVERITY_LABEL.get(case.get("severity"), "差异"),
                           round(cents / 100.0, 2) if type(cents) is int else None,
                           cents, expected_display, actual_display,
                           round(difference / 100.0, 2) if type(difference) is int else None,
                           ledger_text, voucher_text,
                           SEVERITY_LABEL.get(case.get("severity"), "差异"),
                           "定位"])
            row_cells = issues[issues.max_row]
            row_cells[3].fill = SEVERITY_FILL.get(case.get("severity"), SEVERITY_FILL["yellow"])
            for column in (4, 5):
                row_cells[column].font = AMOUNT_FONT
            row_cells[4].number_format = '#,##0.00'
            row_cells[5].number_format = '#,##0'
            row_cells[8].number_format = '#,##0.00'
            if target:
                set_hyperlink(row_cells[12], "#" + target)
                set_hyperlink(row_cells[4], "#" + target)
                set_hyperlink(row_cells[5], "#" + target)
            issue_row_map[case.get("case_id")] = issue_row_map.get(case.get("case_id"), position)
        style_body(issues, [10, 46, 16, 9, 12, 12, 12, 12, 10, 22, 26, 9, 9])
        issues.sheet_view.showGridLines = False
        issues.page_setup.orientation = "landscape"
        issues.page_setup.paperSize = issues.PAPERSIZE_A4
        issues.page_setup.fitToWidth = 1
        issues.sheet_properties.pageSetUpPr.fitToPage = True

        detail = wb.create_sheet("台账明细")
        detail.append(["账务类型", "编号", "状态", "字段", "值", "金额（分）",
                       "金额（元）", "来源工作表", "来源行", "来源列", "原值", "查看原行"])
        style_header(detail)
        ledger_row_map = {}
        for key in sorted(ledger, key=lambda item: (item[0] or "", item[1] or "")):
            row = ledger[key]
            source_row = find_source_row(row, sources)
            id_column = "A"
            ledger_row_map.setdefault(key, detail.max_row + 1)
            for field, value in (row.get("fields") or {}).items():
                detail.append([LEDGER_TYPE_LABEL.get(row.get("ledger_type"), "账务"),
                               row.get("ledger_id"), row.get("status", "未涉及"),
                               FIELD_LABEL.get(field, "补充信息"),
                               value_text(field, value),
                               value if field.endswith("_cents") and type(value) is int else None,
                               round(value / 100.0, 2)
                               if field.endswith("_cents") and type(value) is int else None,
                               source_row.get("sheet") if source_row else None,
                               source_row.get("excel_row") if source_row else None,
                               id_column if source_row else None,
                               (source_row.get("cells") or {}).get(id_column, {})
                               .get("raw_value") if source_row else None,
                               "查看" if source_row else None])
                row_cells = detail[detail.max_row]
                row_cells[5].number_format = '#,##0'
                row_cells[6].number_format = '#,##0.00'
                if source_row:
                    target = target_address(source_row.get("sheet"),
                                            source_row.get("excel_row"),
                                            id_column, row_map, letters)
                    if target:
                        set_hyperlink(row_cells[11], "#" + target)
        style_body(detail, [10, 14, 10, 20, 28, 12, 12, 12, 8, 8, 14, 9])
        detail.auto_filter.ref = ("A1:%s%d" % (get_column_letter(detail.max_column),
                                               detail.max_row))
        detail.sheet_view.showGridLines = False
        detail.page_setup.orientation = "landscape"
        detail.page_setup.paperSize = detail.PAPERSIZE_A4
        detail.page_setup.fitToWidth = 1
        detail.sheet_properties.pageSetUpPr.fitToPage = True
        voucher_row_map = {}
        row_cursor = 2
        for voucher_id in sorted(vouchers):
            voucher_row_map[voucher_id] = row_cursor
            row_cursor += len((vouchers[voucher_id].get("fields") or {}))
        for position, case in enumerate(index["cases"], start=2):
            row_cells = issues[position]
            for ref in case.get("ledger_refs") or []:
                target_row = ledger_row_map.get((ref.get("ledger_type"), ref.get("ledger_id")))
                if target_row:
                    set_hyperlink(row_cells[9], "#'台账明细'!A%d" % target_row)
                    break
            for ref in case.get("voucher_refs") or []:
                target_row = voucher_row_map.get(ref.get("voucher_id"))
                if target_row:
                    set_hyperlink(row_cells[10], "#'凭证'!A%d" % target_row)
                    break

        voucher_sheet = wb.create_sheet("凭证")
        voucher_sheet.append(["凭证类型", "凭证编号", "状态", "字段", "值",
                              "来源记录", "图像占位"])
        style_header(voucher_sheet)
        for voucher_id in sorted(vouchers):
            entry = vouchers[voucher_id]
            first = True
            for field, value in (entry.get("fields") or {}).items():
                voucher_sheet.append([VOUCHER_TYPE_LABEL.get(entry.get("voucher_type"), "凭证"),
                                      voucher_id, entry.get("status", "已取得"),
                                      VOUCHER_FIELD_LABEL.get(field, "补充信息"),
                                      value_text(field, value), "见资料接收记录",
                                      IMAGE_TEXT if first
                                      and entry.get("voucher_type") in ("INVOICE", "BANK_RECEIPT")
                                      else None])
                first = False
        missing_vouchers = sorted({(ref.get("voucher_type"))
                                   for case in index["cases"]
                                   for ref in case.get("voucher_refs") or []
                                   if not ref.get("voucher_id")})
        for voucher_type in missing_vouchers:
            voucher_sheet.append([VOUCHER_TYPE_LABEL.get(voucher_type, "凭证"),
                                  "（未取得）", "未取得", "—", "—", "—", "未取得"])
        style_body(voucher_sheet, [10, 16, 9, 18, 30, 16, 34])
        voucher_sheet.auto_filter.ref = ("A1:%s%d"
                                         % (get_column_letter(voucher_sheet.max_column),
                                            voucher_sheet.max_row))
        voucher_sheet.sheet_view.showGridLines = False
        voucher_sheet.page_setup.orientation = "landscape"
        voucher_sheet.page_setup.paperSize = voucher_sheet.PAPERSIZE_A4
        voucher_sheet.page_setup.fitToWidth = 1
        voucher_sheet.sheet_properties.pageSetUpPr.fitToPage = True

        image_sheet = wb.create_sheet("图像占位")
        image_sheet.append(["凭证类型", "凭证编号", "单号", "日期", "金额（分）",
                            "金额（元）", "占位说明", "预留放置位置"])
        style_header(image_sheet)
        for voucher_id in sorted(vouchers):
            entry = vouchers[voucher_id]
            if entry.get("voucher_type") not in ("INVOICE", "BANK_RECEIPT"):
                continue
            fields = entry.get("fields") or {}
            number = fields.get("invoice_no") or fields.get("receipt_no")
            date_value = fields.get("issue_date") or fields.get("txn_date")
            cents = fields.get("total_cents") or fields.get("amount_cents")
            image_sheet.append([VOUCHER_TYPE_LABEL.get(entry.get("voucher_type"), "凭证"),
                                voucher_id, number, date_value, cents,
                                round(cents / 100.0, 2) if type(cents) is int else None,
                                IMAGE_TEXT, None])
            row_cells = image_sheet[image_sheet.max_row]
            row_cells[4].number_format = '#,##0'
            row_cells[5].number_format = '#,##0.00'
        for voucher_type in missing_vouchers:
            if voucher_type in ("INVOICE", "BANK_RECEIPT"):
                image_sheet.append([VOUCHER_TYPE_LABEL.get(voucher_type, "凭证"),
                                    "（未取得）", None, None, None, None,
                                    IMAGE_TEXT + "（未取得）", None])
        style_body(image_sheet, [10, 16, 16, 12, 12, 12, 34, 40])
        image_sheet.sheet_view.showGridLines = False
        image_sheet.page_setup.orientation = "landscape"
        image_sheet.page_setup.paperSize = image_sheet.PAPERSIZE_A4
        image_sheet.page_setup.fitToWidth = 1
        image_sheet.sheet_properties.pageSetUpPr.fitToPage = True

        gl = index.get("gl")
        if gl:
            build_gl_sheets(wb, gl)
            info["A11"] = "借贷核对"
            info["B11"] = "借贷核对为合成账套演示；核对结果只展示证据与差异，不构成审计结论。"
            for row in info.iter_rows(min_row=10, max_row=11):
                for cell in row:
                    cell.border = BORDER
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
            sheet_order = SHEET_NAMES + GL_SHEET_NAMES
        else:
            sheet_order = SHEET_NAMES
        wb._sheets = [wb[name] for name in sheet_order]
        out_dir.mkdir(parents=True, exist_ok=False)
        target_path = out_dir / WORKBOOK_NAME
        wb.save(target_path)
        normalize_workbook(target_path)
        if not target_path.is_file():
            raise WorkbookError("usage", "工作簿未生成：%s" % target_path)
        print(json.dumps({"status": "PASS", "workbook": str(target_path),
                          "bytes": target_path.stat().st_size,
                          "cases": len(index["cases"]),
                          "ledger_rows": len(ledger), "vouchers": len(vouchers),
                          "gl": "gl" in index, "sheets": len(sheet_order)},
                         ensure_ascii=False))
        return 0
    except WorkbookError as exc:
        print(json.dumps({"status": "ERROR", "kind": exc.kind, "error": str(exc),
                          "field": exc.field}, ensure_ascii=False))
        return 1 if exc.kind == "content" else 2


if __name__ == "__main__":
    raise SystemExit(main())
