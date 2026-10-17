#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-049：证据链下钻 HTML（多页跳转版 + 单页比对版）。

命令行：
    python -B scripts/build_drilldown_site.py --index <trace_index.json> --out-dir <新证据根>

只读 TASK-048 已接受的 `trace_index.json`（含 cases / ledger / vouchers / source_rows / meta），生成：
- 多页跳转版：问题清单（50 条/页）、事项页、账务行页、凭证页、原始表行页、资料接收记录页；
- 单页比对版：每个事项一页（线索/账务/凭证/原始行同页，`<details>` 折叠，A4 可打印）。
全部离线、单文件无脚本、纯相对链接、无 http(s)/图片/外部字体；可见文本只用审计语言；
动态文本全部转义；核对结论固定"由审计人员填写"，不采集、不虚构。

边界：只读展示既有合成证据；不是批次批准、不是身份认证；`real_approval=null`、
真实独立初判未保存、`next_step_allowed=false`、`ai_enabled=false`；不证明凭证/流水真实，
不构成审计结论。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
SITE_VERSION = "TASK-049-drilldown-site-1.1"
GENERATOR = "scripts/build_drilldown_site.py"
CASES_PER_PAGE = 50
BANNER = "合成数据；不是批次批准；不是审计结论；资料版本以资料接收记录为准。"
CONFIRM_TEXT = "由审计人员填写"
IMAGE_TEXT = "模拟数据，当前无对应真实凭证图像"
SHEET_LABEL = {"payables": "应付明细", "payments": "付款/退款主表",
               "allocations": "分摊明细", "invoices": "发票", "contracts": "合同",
               "bank_receipts": "银行回单", "approvals": "审批单",
               "goods_receipts": "入库单"}
LEDGER_FIELD_LABEL = {
    "ap_id": "应付单编号", "ap_number": "应付单号", "supplier_id": "供应商编号",
    "ap_date": "应付日期", "payable_amount_cents": "应付金额（分）", "currency": "币种",
    "payment_id": "付款编号", "transaction_type": "交易类型",
    "original_payment_id": "原付款编号", "payee_supplier_id": "收款供应商",
    "payment_date": "日期", "amount_cents": "金额（分）",
    "settlement_status": "结算状态", "bank_reference": "银行参考号",
    "allocation_id": "分摊编号", "ap_id ": "应付单编号",
    "allocated_amount_cents": "分摊金额（分）", "original_allocation_id": "原分摊编号",
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
KIND_LABEL = {"RULE_FINDING": "待核查线索", "VOUCHER_DIFFERENCE": "凭证差异",
              "VOUCHER_MISSING": "未取得凭证", "BANK_DIFFERENCE": "银行流水差异",
              "BANK_UNMATCHED": "账有实无", "BANK_UNMATCHED_BANK": "实有账无",
              "MULTI_SOURCE": "多来源差异"}
SEVERITY_LABEL = {"red": "差异", "yellow": "待核查", "green": "已核对"}
MACHINE_RESULT = "机器核对结果（程序）"
HUMAN_REVIEW = "人工审阅状态"
HUMAN_ENTRY = "人工审阅录入"
NOT_INCLUDED = "未纳入逐项核对（仅金额勾稽）"
MACHINE_LEGEND = ("机器核对结果（程序）：已核对一致 / 存在差异 / 未取得凭证 / "
                  "未纳入逐项核对（仅金额勾稽）")
REVIEW_LEGEND = ("人工审阅状态：待审阅 / 已审阅-相符 / 已审阅-不符 / 需补充资料；"
                 "默认待审阅；程序不会替人写“已审阅”。")
GUIDE_LINK = "<a href=\"guide.html\">口径与对账指引</a>"
GL_LINK = "<a href=\"gl-trial-balance.html\">借贷核对</a>"
GL_PRESENT = False


def display_status(status):
    status = status or NOT_INCLUDED
    if status == "未取得":
        return "未取得凭证"
    if status == "未涉及":
        return NOT_INCLUDED
    return status


def legend_html():
    return ("<p class=\"note legend\">%s<br>%s</p>\n"
            % (esc(MACHINE_LEGEND), esc(REVIEW_LEGEND)))


def money2(cents):
    if type(cents) is not int:
        return "—"
    return "{:,.2f} 元".format(cents / 100.0)
LEDGER_TYPE_LABEL = {"AP": "应付单", "PAYMENT": "付款", "REFUND": "退款",
                     "ALLOCATION": "分摊"}
VOUCHER_TYPE_LABEL = {"INVOICE": "发票", "CONTRACT": "合同",
                      "BANK_RECEIPT": "银行回单", "APPROVAL": "审批单",
                      "GOODS_RECEIPT": "入库单"}
FORBIDDEN_WORDS = ("JSON", "hash", "SHA", "API", "script", "pipeline", "解析",
                   "字段类型", "字节", "编码", "版本号")


class SiteError(Exception):
    def __init__(self, kind, message, field=None):
        super().__init__(message)
        self.kind = kind
        self.field = field


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def read_json(path: Path):
    return json.loads(path.read_bytes())


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def money(cents) -> str:
    if type(cents) is not int:
        return "—"
    return "%d 分（%.2f 元）" % (cents, cents / 100.0)


def value_text(field, value):
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if field.endswith("_cents") and type(value) is int:
        return money(value)
    if field == "direction" or field == "transaction_type":
        return TXN_LABEL.get(str(value), str(value))
    if field == "settlement_status" or field == "status":
        return STATUS_LABEL.get(str(value), str(value))
    return str(value)


def field_label(field, labels):
    return labels.get(field, "补充信息")


REVIEW_STATUSES = ("待审阅", "已审阅-相符", "已审阅-不符", "需补充资料")
REVIEW_TOKEN = {"待审阅": "pending", "已审阅-相符": "match",
                "已审阅-不符": "mismatch", "需补充资料": "needmore"}
FILTER_BAR = ('''<div class="filter-bar">状态
<select class="filter-status"><option value="all">全部</option>
<option value="abnormal">仅异常</option><option value="ok">仅合规</option>
<option value="neutral">未纳入逐项核对</option></select>
审阅状态 <select class="filter-review"><option value="all">全部</option>
<option value="pending">待审阅</option><option value="match">已审阅-相符</option>
<option value="mismatch">已审阅-不符</option><option value="needmore">需补充资料</option></select>
关键词 <input class="filter-keyword" type="text" placeholder="输入关键词"></div>''')


def review_badge(review):
    review = review or {}
    status = review.get("status") or "待审阅"
    token = REVIEW_TOKEN.get(status, "pending")
    return ('<span class="badge rv-%s">%s</span>' % (esc(token), esc(status)))


def review_block(record_id, record_type, review):
    review = review or {}
    status = review.get("status") or "待审阅"
    options = "".join('<option value="%s"%s>%s</option>'
                      % (esc(item), " selected" if item == status else "", esc(item))
                      for item in REVIEW_STATUSES)
    return ('''<div class="review" data-record-id="%s" data-record-type="%s">
<div class="review-head">人工审阅状态：%s</div>
<label>人工审阅状态 <select class="rv-status">%s</select></label>
<label>审阅人 <input class="rv-reviewer" value="%s"></label>
<label>审阅日期 <input class="rv-date" value="%s"></label>
<label>审计问题描述 <textarea class="rv-issue" rows="2">%s</textarea></label>
<label>建议处理 <textarea class="rv-suggestion" rows="2">%s</textarea></label>
<button class="export-review" type="button">导出审阅记录</button>
</div>''' % (esc(record_id), esc(record_type), review_badge(review), options,
                              esc(review.get("reviewer") or ""),
                              esc(review.get("date") or ""),
                              esc(review.get("issue") or ""),
                              esc(review.get("suggestion") or "")))
FILTER_SCRIPT = ('''<script>
(function () {
  var version = (document.body && document.body.getAttribute('data-review-version')) || '';
  var bar = document.querySelector('.filter-bar');
  function apply() {
    var mode = bar ? bar.querySelector('.filter-status') : null;
    var reviewMode = bar ? bar.querySelector('.filter-review') : null;
    var keyword = bar ? bar.querySelector('.filter-keyword') : null;
    var classes = [];
    if (mode) { classes.push('filter-' + mode.value); }
    if (reviewMode) { classes.push('rvf-' + reviewMode.value); }
    var query = keyword ? (keyword.value || '').toLowerCase() : '';
    if (query) { classes.push('filter-keyword'); }
    document.body.className = classes.join(' ');
    var rows = document.querySelectorAll('tr.row');
    for (var i = 0; i < rows.length; i += 1) {
      var text = (rows[i].textContent || '').toLowerCase();
      if (query && text.indexOf(query) < 0) { rows[i].classList.remove('match'); }
      else { rows[i].classList.add('match'); }
    }
  }
  function collect() {
    var records = [];
    var blocks = document.querySelectorAll('.review');
    for (var i = 0; i < blocks.length; i += 1) {
      var block = blocks[i];
      var item = {
        record_id: block.getAttribute('data-record-id'),
        record_type: block.getAttribute('data-record-type'),
        status: block.querySelector('.rv-status').value,
        issue: block.querySelector('.rv-issue').value,
        suggestion: block.querySelector('.rv-suggestion').value,
        reviewer: block.querySelector('.rv-reviewer').value,
        date: block.querySelector('.rv-date').value
      };
      records.push(item);
    }
    return { review_version: 'TASK-052-review-1.0', source_version: version,
             records: records };
  }
  function download(name, content, type) {
    var blob = new Blob([content], { type: type });
    var url = URL.createObjectURL(blob);
    var anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = name;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }
  function exportRecords() {
    var data = collect();
    download('审阅记录.json', JSON.stringify(data, null, 2), 'application/json');
    var lines = ['record_id,record_type,status,issue,suggestion,reviewer,date'];
    for (var i = 0; i < data.records.length; i += 1) {
      var record = data.records[i];
      var fields = [record.record_id, record.record_type, record.status, record.issue,
                    record.suggestion, record.reviewer, record.date];
      for (var j = 0; j < fields.length; j += 1) {
        fields[j] = '"' + String(fields[j] || '').replace(/"/g, '""') + '"';
      }
      lines.push(fields.join(','));
    }
    download('审阅记录.csv', lines.join('\\n'), 'text/csv');
  }
  function storageKey(block) {
    return 'review:' + version + ':' + block.getAttribute('data-record-type') + ':'
      + block.getAttribute('data-record-id');
  }
  function restore() {
    var blocks = document.querySelectorAll('.review');
    for (var i = 0; i < blocks.length; i += 1) {
      var block = blocks[i];
      var raw = null;
      try { raw = window.localStorage.getItem(storageKey(block)); } catch (e) { raw = null; }
      if (!raw) { continue; }
      var value = null;
      try { value = JSON.parse(raw); } catch (e) { value = null; }
      if (!value) { continue; }
      if (value.status) { block.querySelector('.rv-status').value = value.status; }
      if (value.issue) { block.querySelector('.rv-issue').value = value.issue; }
      if (value.suggestion) { block.querySelector('.rv-suggestion').value = value.suggestion; }
      if (value.reviewer) { block.querySelector('.rv-reviewer').value = value.reviewer; }
      if (value.date) { block.querySelector('.rv-date').value = value.date; }
    }
  }
  function save(block) {
    var value = {
      status: block.querySelector('.rv-status').value,
      issue: block.querySelector('.rv-issue').value,
      suggestion: block.querySelector('.rv-suggestion').value,
      reviewer: block.querySelector('.rv-reviewer').value,
      date: block.querySelector('.rv-date').value
    };
    try { window.localStorage.setItem(storageKey(block), JSON.stringify(value)); }
    catch (e) { return; }
  }
  function bindDrafts() {
    var blocks = document.querySelectorAll('.review');
    for (var i = 0; i < blocks.length; i += 1) {
      (function (block) {
        var inputs = block.querySelectorAll('select, input, textarea');
        for (var j = 0; j < inputs.length; j += 1) {
          inputs[j].addEventListener('change', function () { save(block); apply(); });
          inputs[j].addEventListener('input', function () { save(block); });
        }
      })(blocks[i]);
    }
  }
  if (bar) {
    bar.querySelector('.filter-status').addEventListener('change', apply);
    bar.querySelector('.filter-review').addEventListener('change', apply);
    bar.querySelector('.filter-keyword').addEventListener('input', apply);
    apply();
  }
  var exportButtons = document.querySelectorAll('.export-review');
  for (var buttonIndex = 0; buttonIndex < exportButtons.length; buttonIndex += 1) {
    exportButtons[buttonIndex].addEventListener('click', exportRecords);
  }
  restore();
  bindDrafts();
})();
</script>''')


def page(title, body, *, breadcrumb="", back=None, filter_bar=False,
         review_version=""):
    parts = ["<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"]
    parts.append("<title>%s</title>\n" % esc(title))
    parts.append("<style>\n")
    parts.append("""
@page { size: A4; margin: 12mm; }
body { font-family: "Microsoft YaHei", "PingFang SC", "SimSun", serif; color: #1f2328;
       font-size: 10.5pt; line-height: 1.55; margin: 0; padding: 0; background: #ffffff; }
h1 { font-size: 16pt; margin: 0 0 3mm 0; }
h2 { font-size: 12pt; margin: 5mm 0 2mm 0; border-left: 4px solid #8a6d3b; padding-left: 2.5mm; }
h3 { font-size: 11pt; margin: 3mm 0 1.5mm 0; }
.banner { border: 2px solid #b71c1c; background: #fff3cd; padding: 2.5mm 3.5mm; margin: 0 0 3mm 0; font-weight: 600; }
.crumbs { color: #57606a; font-size: 9.5pt; margin: 0 0 3mm 0; }
.crumbs a { color: #1f6feb; text-decoration: none; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 3mm 0; font-size: 9.5pt; }
th, td { border: 1px solid #d0d7de; padding: 1.6mm 2mm; text-align: left; vertical-align: top; }
th { background: #f6f8fa; font-weight: 600; }
tr.red td { background: #fde8e8; }
tr.yellow td { background: #fff8d6; }
tr.green td { background: #e6ffec; }
.badge { display: inline-block; padding: 0.4mm 2mm; border-radius: 2mm; font-size: 9pt; font-weight: 600; }
.badge.red { background: #fde8e8; color: #b71c1c; border: 1px solid #b71c1c; }
.badge.yellow { background: #fff8d6; color: #7a5b00; border: 1px solid #b58a00; }
.badge.green { background: #e6ffec; color: #1a7f37; border: 1px solid #1a7f37; }
.note { color: #57606a; font-size: 9.5pt; }
.placeholder { border: 2px dashed #8b949e; background: #f6f8fa; padding: 6mm 4mm; text-align: center; color: #57606a; margin: 2mm 0 3mm 0; }
.confirm { border: 1px solid #d0d7de; background: #fffdf3; padding: 3mm; margin: 3mm 0; }
details { margin: 2mm 0; }
summary { cursor: default; font-weight: 600; }
a { color: #1f6feb; }
.foot { margin-top: 6mm; border-top: 1px solid #d0d7de; padding-top: 2.5mm; font-size: 9pt; color: #57606a; }
.filter-bar { margin: 0 0 3mm 0; padding: 2mm 3mm; background: #f6f8fa; border: 1px solid #d0d7de; font-size: 9.5pt; }
.filter-bar select { margin-right: 4mm; }
.filter-bar input { width: 40mm; }
body.filter-abnormal tr.row:not(.abnormal) { display: none; }
body.filter-ok tr.row:not(.ok) { display: none; }
body.filter-neutral tr.row:not(.neutral) { display: none; }
body.filter-keyword tr.row:not(.match) { display: none; }
body.rvf-pending tr.row:not(.rv-pending) { display: none; }
body.rvf-match tr.row:not(.rv-match) { display: none; }
body.rvf-mismatch tr.row:not(.rv-mismatch) { display: none; }
body.rvf-needmore tr.row:not(.rv-needmore) { display: none; }
.badge.rv-match { background: #e6ffec; color: #1a7f37; border: 1px solid #1a7f37; }
.badge.rv-mismatch { background: #fde8e8; color: #b71c1c; border: 1px solid #b71c1c; }
.badge.rv-needmore { background: #fff8d6; color: #7a5b00; border: 1px solid #b58a00; }
.badge.rv-pending { background: #f6f8fa; color: #57606a; border: 1px solid #8b949e; }
.review { border: 1px solid #d0d7de; background: #fbfcfd; padding: 2.5mm 3mm; margin: 2mm 0; font-size: 9.5pt; }
.review-head { font-weight: 600; margin-bottom: 1.5mm; }
.review label { display: block; margin: 1mm 0; }
.review select, .review input { margin-left: 2mm; }
.review textarea { width: 95%; vertical-align: top; }
@media print {
  .filter-bar { display: none; }
  body.filter-abnormal tr.row, body.filter-ok tr.row, body.filter-neutral tr.row,
  body.filter-keyword tr.row,
  body.rvf-pending tr.row, body.rvf-match tr.row, body.rvf-mismatch tr.row,
  body.rvf-needmore tr.row { display: table-row !important; }
}
""")
    parts.append("</style>\n</head>\n<body data-review-version=\"%s\">\n"
                 % esc(review_version))
    parts.append("<div class=\"banner\">%s</div>\n" % esc(BANNER))
    nav_extra = (" · " + GL_LINK) if GL_PRESENT else ""
    parts.append("<p class=\"note\">%s · <a href=\"index.html\">问题清单</a> · "
                 "<a href=\"all-ledger.html\">全量台账</a>%s</p>\n"
                 % (GUIDE_LINK, nav_extra))
    if breadcrumb:
        parts.append("<div class=\"crumbs\">%s</div>\n" % breadcrumb)
    if back:
        parts.append("<p><a href=\"%s\">返回上一层</a></p>\n" % esc(back))
    if filter_bar:
        parts.append(FILTER_BAR + "\n")
    parts.append(body)
    if filter_bar:
        parts.append("\n<p class=\"note\">打印为全量视图，筛选仅屏幕生效。</p>\n")
    if filter_bar or review_version:
        parts.append(FILTER_SCRIPT)
    return "".join(parts).encode("utf-8")


def load_index(path: Path) -> dict:
    if not path.is_file():
        raise SiteError("usage", "索引不存在：%s" % path)
    try:
        index = read_json(path)
    except ValueError as exc:
        raise SiteError("content", "索引不是合法内容：%s" % exc, field="trace_index.json")
    for key in ("cases", "ledger", "vouchers", "source_rows", "meta"):
        if key not in index:
            raise SiteError("content", "索引缺少必需部分：%s" % key, field="trace_index.%s" % key)
    return index


def validate(index):
    ledger = {(row.get("ledger_type"), row.get("ledger_id")): row for row in index["ledger"]}
    vouchers = {row.get("voucher_id"): row for row in index["vouchers"]}
    sources = {(row.get("sheet"), row.get("excel_row")): row for row in index["source_rows"]}
    for case in index["cases"]:
        case_id = case.get("case_id")
        for ref in case.get("ledger_refs") or []:
            if (ref.get("ledger_type"), ref.get("ledger_id")) not in ledger:
                raise SiteError("content", "事项的账务引用无法展开：%s %s=%s"
                                % (case_id, ref.get("ledger_type"), ref.get("ledger_id")),
                                field="%s.ledger_refs.ledger_id=%s"
                                      % (case_id, ref.get("ledger_id")))
        for ref in case.get("voucher_refs") or []:
            if ref.get("voucher_id") and ref["voucher_id"] not in vouchers:
                raise SiteError("content", "事项的凭证引用无法展开：%s %s"
                                % (case_id, ref["voucher_id"]),
                                field="%s.voucher_refs.voucher_id=%s"
                                      % (case_id, ref["voucher_id"]))
        for ref in case.get("source_refs") or []:
            if (ref.get("sheet"), ref.get("excel_row")) not in sources:
                raise SiteError("content", "事项的原始表行无法展开：%s %s!%s"
                                % (case_id, ref.get("sheet"), ref.get("excel_row")),
                                field="%s.source_refs.sheet=%s"
                                      % (case_id, ref.get("sheet")))
    return ledger, vouchers, sources


def case_ledger_links(case):
    return "、".join("<a href=\"ledger-%s-%s.html\">%s %s</a>"
                    % (esc(item["ledger_type"]), esc(item["ledger_id"]),
                       esc(LEDGER_TYPE_LABEL.get(item["ledger_type"], "账务")),
                       esc(item["ledger_id"]))
                    for item in case.get("ledger_refs") or []) or "—"


def case_voucher_links(case):
    items = []
    for ref in case.get("voucher_refs") or []:
        if ref.get("voucher_id"):
            items.append("<a href=\"voucher-%s.html\">%s %s</a>"
                         % (esc(ref["voucher_id"]),
                            esc(VOUCHER_TYPE_LABEL.get(ref.get("voucher_type"), "凭证")),
                            esc(ref["voucher_id"])))
        else:
            items.append("<span class=\"badge red\">未取得</span> %s"
                         % esc(VOUCHER_TYPE_LABEL.get(ref.get("voucher_type"), "凭证")))
    return "、".join(items) or "—"


def list_status_class(status):
    if status in ("存在差异", "未取得", "未取得凭证"):
        return "abnormal"
    if status == "已核对一致":
        return "ok"
    return "neutral"


def render_list_page(title, headers, rows, page_index, total_pages, base_name, note,
                     review_version=""):
    chunk = rows[page_index * CASES_PER_PAGE:(page_index + 1) * CASES_PER_PAGE]
    name = base_name + ".html" if page_index == 0 else base_name + "-%d.html" % (page_index + 1)
    body = ["<h1>%s</h1>\n" % esc(title)]
    body.append("<p class=\"note\">%s；共 %d 行，本页 %d 行。</p>\n"
                % (esc(note), len(rows), len(chunk)))
    body.append(legend_html())
    all_headers = list(headers) + [HUMAN_REVIEW, HUMAN_ENTRY]
    body.append("<table><thead><tr>%s</tr></thead><tbody>\n"
                % "".join("<th>%s</th>" % esc(item) for item in all_headers))
    for row in chunk:
        cells = row.get("cells") or []
        classes = "row " + row.get("class", "")
        review = row.get("review") or {}
        token = REVIEW_TOKEN.get(review.get("status") or "待审阅", "pending")
        classes = classes + " rv-" + token
        query = row.get("text", "")
        detail = ("<details><summary>人工审阅录入</summary>%s</details>"
                  % review_block(row.get("record_id", ""),
                                 row.get("record_type", "case"), review))
        body.append("<tr class=\"%s\" data-text=\"%s\">%s%s%s</tr>\n"
                    % (classes, esc(query),
                       "".join("<td>%s</td>" % cell for cell in cells),
                       "<td>%s</td>" % review_badge(review),
                       "<td>%s</td>" % detail))
    body.append("</tbody></table>\n")
    nav = []
    if page_index > 0:
        nav.append("<a href=\"%s\">上一页</a>"
                   % (base_name + ".html" if page_index == 1
                      else base_name + "-%d.html" % page_index))
    for number in range(1, total_pages + 1):
        label = base_name + ".html" if number == 1 else base_name + "-%d.html" % number
        nav.append("<a href=\"%s\">%d</a>" % (label, number))
    if page_index + 1 < total_pages:
        nav.append("<a href=\"%s-%d.html\">下一页</a>" % (base_name, page_index + 2))
    nav.append("<a href=\"index.html\">问题清单</a>")
    body.append("<p class=\"foot\">%s</p>\n" % " · ".join(nav))
    return name, page(title, "".join(body),
                      breadcrumb="<a href=\"index.html\">问题清单</a> › %s" % esc(title),
                      back="index.html", filter_bar=True,
                      review_version=review_version)


def render_index_pages(index):
    cases = index["cases"]
    pages = []
    total_pages = max(1, (len(cases) + CASES_PER_PAGE - 1) // CASES_PER_PAGE)
    for page_index in range(total_pages):
        chunk = cases[page_index * CASES_PER_PAGE:(page_index + 1) * CASES_PER_PAGE]
        name = "index.html" if page_index == 0 else "index-%d.html" % (page_index + 1)
        rows = []
        for case in chunk:
            case_id = case["case_id"]
            severity = case.get("severity", "yellow")
            amounts = case.get("amounts") or []
            primary = amounts[-1] if amounts else None
            amount_html = "<a href=\"case-%s.html\">%s</a>" % (
                esc(case_id), esc(money(primary.get("cents")))) if primary else "—"
            filter_class = "ok" if severity == "green" else "abnormal"
            rv_status = (case.get("review") or {}).get("status") or "待审阅"
            rv_class = "rv-" + REVIEW_TOKEN.get(rv_status, "pending")
            rows.append(
                "<tr class=\"row %s %s %s\" data-text=\"%s\"><td>%s</td>"
                "<td><a href=\"case-%s.html\">%s</a></td>"
                "<td><span class=\"badge %s\">%s</span></td><td>%s</td>"
                "<td>%s</td><td><a href=\"compare-%s.html\">逐格比对</a></td></tr>\n" % (
                    esc(severity), filter_class, rv_class,
                    esc("%s %s" % (case_id, case.get("title", ""))),
                    esc(case_id), esc(case_id), esc(case.get("title")),
                    esc(severity), esc(SEVERITY_LABEL.get(severity, "差异")),
                    amount_html, review_badge(case.get("review")), esc(case_id)))
        body = ["<h1>问题清单</h1>\n"]
        body.append("<p class=\"note\">全量清单：<a href=\"all-ledger.html\">台账</a> · "
                    "<a href=\"all-vouchers.html\">凭证</a> · "
                    "<a href=\"all-source.html\">原始表行</a></p>\n")
        ap_ids = sorted({row.get("ledger_id") for row in index.get("ledger") or []
                         if row.get("ledger_type") == "AP"})
        if ap_ids:
            links = "、".join("<a href=\"business-%s.html\">%s</a>" % (esc(ap_id), esc(ap_id))
                              for ap_id in ap_ids)
            body.append("<p class=\"note\">业务勾稽底稿（管理口径）：%s · "
                        "<a href=\"guide.html\">口径与对账指引</a></p>\n" % links)
        body.append("<p class=\"note\">共 %d 条事项，本页 %d 条；红=差异/未取得，黄=待核查线索，绿=已核对一致。</p>\n"
                    % (len(cases), len(chunk)))
        body.append(legend_html())
        body.append("<table><thead><tr><th>编号</th><th>事项</th><th>%s</th>"
                    "<th>金额</th><th>%s</th><th>查看</th></tr></thead><tbody>\n"
                    % (esc(MACHINE_RESULT), esc(HUMAN_REVIEW)))
        body.extend(rows)
        body.append("</tbody></table>\n")
        nav = []
        if page_index > 0:
            nav.append("<a href=\"%s\">上一页</a>"
                       % ("index.html" if page_index == 1 else "index-%d.html" % page_index))
        for number in range(1, total_pages + 1):
            label = "index.html" if number == 1 else "index-%d.html" % number
            nav.append("<a href=\"%s\">%d</a>" % (label, number))
        if page_index + 1 < total_pages:
            nav.append("<a href=\"index-%d.html\">下一页</a>" % (page_index + 2))
        body.append("<p class=\"foot\">%s</p>\n" % " · ".join(nav))
        pages.append((name, page("问题清单", "".join(body), back=None,
                                 filter_bar=True,
                                 review_version=(index["meta"].get("source_identity") or {})
                                 .get("sha256", "")[:12])))
    return pages, total_pages


def render_case_page(case, prev_case, next_case, review_version=""):
    case_id = case["case_id"]
    severity = case.get("severity", "yellow")
    body = ["<h1>%s</h1>\n" % esc(case.get("title"))]
    body.append("<p>标记：<span class=\"badge %s\">%s</span></p>\n"
                % (esc(severity), esc(SEVERITY_LABEL.get(severity, "差异"))))
    if case.get("amounts"):
        body.append("<h2>金额</h2>\n<table><thead><tr><th>项目</th><th>金额</th></tr></thead><tbody>\n")
        for item in case["amounts"]:
            body.append("<tr><td>%s</td><td>%s</td></tr>\n"
                        % (esc(item.get("label")), esc(money(item.get("cents")))))
        body.append("</tbody></table>\n")
    if case.get("evidence_blocks"):
        body.append("<h2>差异原因</h2>\n<ul>\n")
        for block in case["evidence_blocks"]:
            detail = []
            for key in ("field", "actual", "expected", "classification"):
                if key in block:
                    detail.append("%s=%s" % (key, json.dumps(block[key], ensure_ascii=False)))
            body.append("<li>%s：%s</li>\n" % (esc(block.get("source")),
                                               esc("；".join(detail)) if detail else "—"))
        body.append("</ul>\n")
    body.append("<h2>涉及账务</h2>\n<p>%s</p>\n" % case_ledger_links(case))
    body.append("<h2>凭证清单</h2>\n<p>%s</p>\n" % case_voucher_links(case))
    if case.get("source_refs"):
        items = []
        for ref in case["source_refs"]:
            items.append("<a href=\"source-%s-%s.html\">%s!%s</a>"
                         % (esc(ref.get("sheet")), esc(ref.get("excel_row")),
                            esc(SHEET_LABEL.get(ref.get("sheet"), "原表")),
                            esc(ref.get("excel_row"))))
        body.append("<h2>原始表行</h2>\n<p>%s</p>\n" % "、".join(items))
    if case.get("image_placeholders"):
        body.append("<h2>凭证影像</h2>\n")
        for placeholder in case["image_placeholders"]:
            body.append("<div class=\"placeholder\">%s<br>预留：单号 / 日期 / 金额<br>%s</div>\n"
                        % (esc(IMAGE_TEXT), esc(placeholder.get("label"))))
    body.append("<h2>下一步</h2>\n<p>请审计人员核对差异原因、取得或补正相关凭证，并填写核对结论。</p>\n")
    body.append("<div class=\"confirm\"><strong>核对结论：%s</strong></div>\n" % esc(CONFIRM_TEXT))
    body.append(review_block(case["case_id"], "case", case.get("review")))
    nav = []
    if prev_case:
        nav.append("<a href=\"case-%s.html\">上一事项</a>" % esc(prev_case["case_id"]))
    nav.append("<a href=\"index.html\">问题清单</a>")
    if next_case:
        nav.append("<a href=\"case-%s.html\">下一事项</a>" % esc(next_case["case_id"]))
    body.append("<p class=\"foot\">%s · <a href=\"compare-%s.html\">逐格比对版</a></p>\n"
                % (" · ".join(nav), esc(case_id)))
    breadcrumb = "<a href=\"index.html\">问题清单</a> › 事项 %s" % esc(case_id)
    return page(case.get("title", "事项"), "".join(body), breadcrumb=breadcrumb,
                back="index.html", review_version=review_version)


def render_compare_page(case, ledger, vouchers, sources):
    case_id = case["case_id"]
    body = ["<h1>逐格比对：%s</h1>\n" % esc(case.get("title"))]
    body.append("<div><strong>核对结论：%s</strong></div>\n" % esc(CONFIRM_TEXT))
    body.append("<h2>线索</h2>\n<details open><summary>金额与差异原因</summary>\n")
    if case.get("amounts"):
        body.append("<table><thead><tr><th>项目</th><th>金额</th></tr></thead><tbody>\n")
        for item in case["amounts"]:
            body.append("<tr><td>%s</td><td>%s</td></tr>\n"
                        % (esc(item.get("label")), esc(money(item.get("cents")))))
        body.append("</tbody></table>\n")
    body.append("<p>%s</p>\n</details>\n" % esc(case.get("title")))
    body.append("<h2>账务行</h2>\n")
    for ref in case.get("ledger_refs") or []:
        row = ledger.get((ref.get("ledger_type"), ref.get("ledger_id")))
        if row is None:
            continue
        body.append("<details open><summary>%s %s</summary>\n"
                    % (esc(LEDGER_TYPE_LABEL.get(ref.get("ledger_type"), "账务")),
                       esc(ref.get("ledger_id"))))
        body.append(ledger_fields_table(row))
        body.append("</details>\n")
    body.append("<h2>凭证字段</h2>\n")
    for ref in case.get("voucher_refs") or []:
        if ref.get("voucher_id") and ref["voucher_id"] in vouchers:
            entry = vouchers[ref["voucher_id"]]
            body.append("<details open><summary>%s %s</summary>\n"
                        % (esc(VOUCHER_TYPE_LABEL.get(ref.get("voucher_type"), "凭证")),
                           esc(ref["voucher_id"])))
            body.append(voucher_fields_table(entry))
            body.append("</details>\n")
        else:
            body.append("<details open><summary>未取得 %s</summary>\n"
                        "<div class=\"placeholder\">%s<br>预留：单号 / 日期 / 金额</div>\n</details>\n"
                        % (esc(ref.get("voucher_type")), esc(IMAGE_TEXT)))
    body.append("<h2>原始表行</h2>\n")
    for ref in case.get("source_refs") or []:
        row = sources.get((ref.get("sheet"), ref.get("excel_row")))
        if row is None:
            continue
        body.append("<details open><summary>%s 第 %s 行</summary>\n"
                    % (esc(SHEET_LABEL.get(ref.get("sheet"), "原表")),
                       esc(ref.get("excel_row"))))
        body.append(source_cells_table(row))
        body.append("</details>\n")
    body.append("<p class=\"foot\"><a href=\"case-%s.html\">返回事项</a> · "
                "<a href=\"index.html\">问题清单</a></p>\n" % esc(case_id))
    return page("逐格比对 %s" % case_id, "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 事项 %s › 逐格比对"
                           % esc(case_id), back="case-%s.html" % esc(case_id))


def ledger_fields_table(row):
    parts = ["<table><thead><tr><th>项目</th><th>值</th></tr></thead><tbody>\n"]
    for field, value in row.get("fields", {}).items():
        parts.append("<tr><td>%s</td><td>%s</td></tr>\n"
                     % (esc(field_label(field, LEDGER_FIELD_LABEL)),
                        esc(value_text(field, value))))
    parts.append("</tbody></table>\n")
    source = row.get("source") or {}
    parts.append("<p class=\"note\">来源工作表：%s</p>\n"
                 % esc(SHEET_LABEL.get(source.get("sheet"), "原表")))
    return "".join(parts)


def voucher_fields_table(entry):
    parts = ["<table><thead><tr><th>项目</th><th>值</th></tr></thead><tbody>\n"]
    for field, value in entry.get("fields", {}).items():
        parts.append("<tr><td>%s</td><td>%s</td></tr>\n"
                     % (esc(field_label(field, VOUCHER_FIELD_LABEL)),
                        esc(value_text(field, value))))
    parts.append("</tbody></table>\n")
    parts.append("<div class=\"placeholder\">%s<br>预留：单号 / 日期 / 金额</div>\n"
                 % esc(IMAGE_TEXT))
    parts.append("<p class=\"note\">来源：<a href=\"records.html\">资料接收记录</a></p>\n")
    return "".join(parts)


def source_cells_table(row):
    columns = sorted((row.get("cells") or {}).keys())
    parts = ["<table><thead><tr><th>列</th><th>原值</th><th>整理值</th></tr></thead><tbody>\n"]
    for column in columns:
        cell = row["cells"][column]
        parts.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>\n"
                     % (esc(column), esc(cell.get("raw_value")),
                        esc(cell.get("standard_value"))))
    parts.append("</tbody></table>\n")
    return "".join(parts)


def find_source_row(row, sources):
    sheet = (row.get("source") or {}).get("sheet")
    ledger_type = row.get("ledger_type")
    target = row.get("ledger_id")
    id_column = {"AP": "A", "PAYMENT": "A", "REFUND": "A",
                 "ALLOCATION": "A"}.get(ledger_type)
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


def render_ledger_page(row, sources, review_version="", business_id=None):
    body = ["<h1>账务行 %s</h1>\n" % esc(row.get("ledger_id"))]
    body.append("<p>类型：%s；机器核对结果（程序）：%s</p>\n"
                % (esc(LEDGER_TYPE_LABEL.get(row.get("ledger_type"), "账务")),
                   esc(display_status(row.get("status")))))
    body.append(legend_html())
    body.append(review_block(row.get("ledger_id"), "ledger", row.get("review")))
    if business_id:
        body.append("<p><a href=\"business-%s.html\">业务勾稽底稿（管理口径）</a></p>\n"
                    % esc(business_id))
    body.append(ledger_fields_table(row))
    source_row = find_source_row(row, sources)
    if source_row is not None:
        body.append("<h2>来源</h2>\n")
        body.append(source_cells_table(source_row))
        body.append("<p><a href=\"source-%s-%s.html\">查看原始表行（%s 第 %s 行）</a></p>\n"
                    % (esc(source_row.get("sheet")), esc(source_row.get("excel_row")),
                       esc(SHEET_LABEL.get(source_row.get("sheet"), "原表")),
                       esc(source_row.get("excel_row"))))
    else:
        source = row.get("source") or {}
        body.append("<p class=\"note\">来源工作表：%s；逐行逐列原值见原始表行页。</p>\n"
                    % esc(SHEET_LABEL.get(source.get("sheet"), "原表")))
    body.append("<p class=\"foot\"><a href=\"index.html\">问题清单</a></p>\n")
    return page("账务行 %s" % row.get("ledger_id"), "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 账务行 %s"
                           % esc(row.get("ledger_id")), back="index.html",
                review_version=review_version)


def render_voucher_page(entry, review_version=""):
    body = ["<h1>凭证 %s</h1>\n" % esc(entry.get("voucher_id"))]
    body.append("<p>类型：%s；机器核对结果（程序）：%s</p>\n"
                % (esc(VOUCHER_TYPE_LABEL.get(entry.get("voucher_type"), "凭证")),
                   esc(entry.get("status", "已取得"))))
    body.append(legend_html())
    body.append(review_block(entry.get("voucher_id"), "voucher", entry.get("review")))
    body.append(voucher_fields_table(entry))
    body.append("<p class=\"foot\"><a href=\"records.html\">资料接收记录</a> · "
                "<a href=\"index.html\">问题清单</a></p>\n")
    return page("凭证 %s" % entry.get("voucher_id"), "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 凭证 %s"
                           % esc(entry.get("voucher_id")), back="index.html",
                review_version=review_version)


def render_source_page(row, involved=False, review_version=""):
    body = ["<h1>原始表行 %s 第 %s 行</h1>\n"
            % (esc(SHEET_LABEL.get(row.get("sheet"), "原表")), esc(row.get("excel_row")))]
    body.append("<p>机器核对结果（程序）：%s</p>\n"
                % esc("已涉及（已纳入逐项核对）" if involved else NOT_INCLUDED))
    record_id = "%s!%s" % (row.get("sheet"), row.get("excel_row"))
    body.append(review_block(record_id, "source", row.get("review")))
    body.append(source_cells_table(row))
    body.append("<p><a href=\"records.html\">打开原始 Excel 文件（见资料接收记录）</a></p>\n")
    body.append("<p class=\"foot\"><a href=\"index.html\">问题清单</a></p>\n")
    return page("原始表行 %s!%s" % (row.get("sheet"), row.get("excel_row")), "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 原始表行 %s 第 %s 行"
                           % (esc(SHEET_LABEL.get(row.get("sheet"), "原表")),
                              esc(row.get("excel_row"))), back="index.html",
                review_version=review_version)


def render_records_page(index):
    meta = index.get("meta") or {}
    body = ["<h1>资料接收记录</h1>\n"]
    body.append("<table><thead><tr><th>项目</th><th>内容</th></tr></thead><tbody>\n")
    body.append("<tr><td>批次</td><td>%s</td></tr>\n" % esc(meta.get("batch_id")))
    entity = meta.get("entity") or {}
    period = entity.get("period") or {}
    body.append("<tr><td>实体</td><td>%s</td></tr>\n" % esc(entity.get("company")))
    body.append("<tr><td>期间</td><td>%s 至 %s</td></tr>\n"
                % (esc(period.get("period_start")), esc(period.get("period_end"))))
    body.append("<tr><td>截止日</td><td>%s</td></tr>\n" % esc(entity.get("cutoff_date")))
    body.append("<tr><td>资料名称</td><td>合成采购付款数据（应付、付款/退款、分摊及凭证）</td></tr>\n")
    body.append("<tr><td>份数</td><td>账务四类、凭证五类（发票、合同、银行回单、审批单、入库单）</td></tr>\n")
    body.append("<tr><td>事项总数</td><td>%s</td></tr>\n" % esc(meta.get("cases_total")))
    body.append("<tr><td>接收日期</td><td>见资料接收记录</td></tr>\n")
    body.append("</tbody></table>\n")
    body.append("<p class=\"note\">资料版本以资料接收记录为准；本页只作演示说明，不替代原始资料。</p>\n")
    body.append("<p class=\"foot\"><a href=\"index.html\">问题清单</a></p>\n")
    return page("资料接收记录", "".join(body), breadcrumb="<a href=\"index.html\">问题清单</a> › 资料接收记录",
                back="index.html")




MANAGEMENT_DECL = ("本页为管理口径的业务勾稽，不是会计分录；借贷方向仅用于说明余额方向，"
                   "未做试算平衡。")
GAP_DECL = ("本样本没有记账凭证的借贷分录、总账/明细账（三栏式发生额与余额）、科目余额表，"
            "因此不做“有借必有贷、借贷必相等”、试算平衡、总账↔明细账、科目余额表↔报表等"
            "账账/账表核对；这些需要新增输入后另卡实施。")


def supplier_name(supplier_id, sources):
    for key in sorted(sources):
        if key[0] != "suppliers":
            continue
        cells = sources[key].get("cells") or {}
        first = cells.get("A") or {}
        value = first.get("standard_value")
        if value is None:
            value = first.get("raw_value")
        if str(value) == str(supplier_id):
            second = cells.get("B") or {}
            name = second.get("standard_value")
            if name is None:
                name = second.get("raw_value")
            return str(name) if name else ""
    return ""


def pick_voucher(vouchers, voucher_type, amount, used=None):
    used = used if used is not None else set()
    for voucher_id in sorted(vouchers):
        if voucher_id in used:
            continue
        entry = vouchers[voucher_id]
        if entry.get("voucher_type") != voucher_type:
            continue
        fields = entry.get("fields") or {}
        value = fields.get("total_cents")
        if value is None:
            value = fields.get("amount_cents")
        if amount is None or value == amount:
            return entry
    return None


def voucher_row(label, entry, expected, link=True):
    if entry is None:
        return ("<tr class=\"abnormal\"><td>%s</td><td>未取得</td>"
                "<td>未取得凭证</td><td>—</td><td>—</td></tr>\n" % esc(label))
    fields = entry.get("fields") or {}
    value = fields.get("total_cents")
    if value is None:
        value = fields.get("amount_cents")
    match = "一致" if value == expected else "不一致"
    voucher_id = entry.get("voucher_id")
    link_html = ("<a href=\"voucher-%s.html\">%s</a>" % (esc(voucher_id), esc(voucher_id))
                 if link else esc(voucher_id))
    return ("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>\n"
            % (esc(label), link_html, esc(entry.get("status", "已取得")), esc(match),
               "<a href=\"voucher-%s.html\">查看</a>" % esc(voucher_id)))


def render_guide_page():
    body = ["<h1>口径与对账指引</h1>\n"]
    body.append("<p class=\"note\">本页说明本样本对什么、怎么对，以及哪些没有做。"
                "页面只读展示既有合成证据，不构成审计结论。</p>\n")
    body.append("<h2>业务链条</h2>\n<ol>\n")
    for step in ("供应商", "应付单", "发票 / 合同 / 入库单（凭证）", "付款", "分摊（核销到应付单）",
                 "退款", "银行流水"):
        body.append("<li>%s</li>\n" % esc(step))
    body.append("</ol>\n")
    body.append("<h2>对账路径</h2>\n")
    body.append("<table><thead><tr><th>对账关系</th><th>对应资料</th><th>本样本状态</th></tr></thead><tbody>\n")
    for relation, materials, status in (
            ("应付 ↔ 发票 / 合同 / 入库单", "应付单、发票、合同、入库单", "已做逐项核对"),
            ("付款 ↔ 审批单 / 回单", "付款主表、审批单、银行回单", "已做逐项核对"),
            ("退款 ↔ 回单", "退款主表、银行回单", "已做逐项核对"),
            ("付款 / 退款 ↔ 银行流水", "付款/退款主表、银行回单", "已做账实核对"),
            ("分摊 = 付款与应付之间的核销桥", "分摊明细", "仅金额勾稽（未纳入逐项核对）")):
        body.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>\n"
                    % (esc(relation), esc(materials), esc(status)))
    body.append("</tbody></table>\n")
    body.append("<h2>三步走</h2>\n<ol>\n")
    for step in ("先看问题清单，确认待核查事项与金额。",
                 "看事实底稿（业务勾稽底稿与全量清单）的来源行，核对原始表行与凭证。",
                 "对账证（凭证是否取得、金额是否一致）与账实（付款/退款与银行流水）。"):
        body.append("<li>%s</li>\n" % esc(step))
    body.append("</ol>\n")
    body.append("<h2>“未纳入逐项核对（仅金额勾稽）”是什么意思</h2>\n")
    body.append("<p>分摊行是付款与应付之间的核销桥梁。当前账证/账实逐项核对"
                "<strong>不单独覆盖</strong>分摊行，只用它做金额勾稽；"
                "这既不是“没问题”，也不是“有问题”，需要审计人员结合业务判断。</p>\n")
    body.append("<h2>缺口声明</h2>\n<p>%s</p>\n" % esc(GAP_DECL))
    body.append("<h2>入口</h2>\n<p><a href=\"index.html\">问题清单</a> · "
                "<a href=\"all-ledger.html\">全量台账</a> · "
                "<a href=\"all-vouchers.html\">全量凭证</a> · "
                "<a href=\"all-source.html\">全量原始表行</a> · "
                "<a href=\"records.html\">资料接收记录</a></p>\n")
    body.append("<p class=\"foot\"><a href=\"index.html\">返回问题清单</a></p>\n")
    return page("口径与对账指引", "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 口径与对账指引",
                back="index.html")


def render_business_page(ap_row, ledger, vouchers, sources, review_version=""):
    fields = ap_row.get("fields") or {}
    ap_id = ap_row.get("ledger_id")
    supplier_id = fields.get("supplier_id")
    name = supplier_name(supplier_id, sources)
    supplier_text = "%s%s" % (supplier_id, "（%s）" % name if name else "")
    amount = fields.get("payable_amount_cents")
    body = ["<h1>业务勾稽底稿（管理口径）：应付单 %s</h1>\n" % esc(ap_id)]
    body.append("<p class=\"note\">%s</p>\n" % esc(MANAGEMENT_DECL))
    body.append("<h2>应付单</h2>\n")
    body.append("<table><thead><tr><th>供应商</th><th>日期</th><th>金额</th></tr></thead><tbody>\n")
    body.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>\n"
                % (esc(supplier_text), esc(fields.get("ap_date")), esc(money2(amount))))
    body.append("</tbody></table>\n")
    allocations = [row for key, row in sorted(ledger.items())
                   if row.get("ledger_type") == "ALLOCATION"
                   and (row.get("fields") or {}).get("ap_id") == ap_id]
    payment_ids = []
    for row in allocations:
        payment_id = (row.get("fields") or {}).get("payment_id")
        if payment_id and payment_id not in payment_ids:
            payment_ids.append(payment_id)
    payments = []
    for payment_id in payment_ids:
        row = ledger.get(("PAYMENT", payment_id)) or ledger.get(("REFUND", payment_id))
        if row is not None:
            payments.append(row)
    paid_rows = [row for row in payments
                 if (row.get("fields") or {}).get("transaction_type") == "PAY"]
    refund_rows = [row for row in payments
                   if (row.get("fields") or {}).get("transaction_type") == "REFUND"]
    paid_total = sum((row.get("fields") or {}).get("amount_cents") or 0 for row in paid_rows)
    refund_total = sum((row.get("fields") or {}).get("amount_cents") or 0 for row in refund_rows)
    payable_total = amount or 0
    balance = paid_total - payable_total - refund_total
    used = set()
    invoice = pick_voucher(vouchers, "INVOICE", amount)
    if invoice:
        used.add(invoice["voucher_id"])
    contract = pick_voucher(vouchers, "CONTRACT", amount)
    if contract:
        used.add(contract["voucher_id"])
    goods = pick_voucher(vouchers, "GOODS_RECEIPT", amount)
    if goods:
        used.add(goods["voucher_id"])
    approvals = []
    for row in paid_rows:
        payment_id = (row.get("fields") or {}).get("payment_id")
        for voucher_id in sorted(vouchers):
            entry = vouchers[voucher_id]
            if entry.get("voucher_type") == "APPROVAL" \
                    and (entry.get("fields") or {}).get("payment_id") == payment_id:
                approvals.append(entry)
                break
    receipts = []
    for row in payments:
        value = (row.get("fields") or {}).get("amount_cents")
        entry = pick_voucher(vouchers, "BANK_RECEIPT", value, used)
        if entry is not None:
            used.add(entry["voucher_id"])
        receipts.append((row, entry))
    body.append("<h2>关联凭证</h2>\n")
    body.append("<table><thead><tr><th>凭证类型</th><th>凭证编号</th><th>状态</th>"
                "<th>金额是否一致</th><th>查看</th></tr></thead><tbody>\n")
    body.append(voucher_row("发票（应付单 %s）" % ap_id, invoice, amount))
    body.append(voucher_row("合同（应付单 %s）" % ap_id, contract, amount))
    body.append(voucher_row("入库单（应付单 %s）" % ap_id, goods, amount))
    body.append("</tbody></table>\n")
    body.append("<h2>付款与退款</h2>\n")
    body.append("<table><thead><tr><th>类型</th><th>编号</th><th>日期</th><th>金额</th>"
                "<th>说明（这笔是什么）</th><th>查看</th></tr></thead><tbody>\n")
    for row in payments:
        row_fields = row.get("fields") or {}
        row_type = row.get("ledger_type")
        label = "付款" if row_type == "PAYMENT" else "退款"
        body.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                    "<td>%s</td><td><a href=\"ledger-%s-%s.html\">查看</a></td></tr>\n"
                    % (esc(label), esc(row.get("ledger_id")), esc(row_fields.get("payment_date")),
                       esc(money2(row_fields.get("amount_cents"))),
                       esc("%s %s 对应应付单 %s" % (label, row.get("ledger_id"), ap_id)),
                       esc(row_type), esc(row.get("ledger_id"))))
    body.append("</tbody></table>\n")
    body.append("<h2>分摊（核销）</h2>\n")
    body.append("<table><thead><tr><th>分摊编号</th><th>付款/退款</th><th>应付单</th>"
                "<th>金额</th><th>说明（这笔是什么）</th><th>查看</th></tr></thead><tbody>\n")
    for row in allocations:
        row_fields = row.get("fields") or {}
        body.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                    "<td>%s</td><td><a href=\"ledger-ALLOCATION-%s.html\">查看</a></td></tr>\n"
                    % (esc(row.get("ledger_id")), esc(row_fields.get("payment_id")),
                       esc(row_fields.get("ap_id")),
                       esc(money2(row_fields.get("allocated_amount_cents"))),
                       esc("%s %s 核销应付 %s" % ("退款" if str(row_fields.get("payment_id", "")).startswith("R") else "付款",
                                                 row_fields.get("payment_id"), ap_id)),
                       esc(row.get("ledger_id"))))
    body.append("</tbody></table>\n")
    body.append("<p class=\"note\">分摊行是付款与应付之间的核销桥梁，当前账证/账实逐项核对不单独覆盖它，只用它做金额勾稽（未纳入逐项核对，仅金额勾稽）。</p>\n")
    body.append("<h2>三栏式勾稽（管理口径，数取自索引）</h2>\n")
    body.append("<table><thead><tr><th>项目</th><th>方向</th><th>金额</th></tr></thead><tbody>\n")
    body.append("<tr><td>应付确认</td><td>贷方</td><td>%s</td></tr>\n" % esc(money2(payable_total)))
    body.append("<tr><td>付款</td><td>借方</td><td>%s</td></tr>\n" % esc(money2(paid_total)))
    body.append("<tr><td>退款</td><td>贷方</td><td>%s</td></tr>\n" % esc(money2(refund_total)))
    body.append("<tr><td>余额</td><td>%s</td><td>%s</td></tr>\n"
                % (esc("借方" if balance >= 0 else "贷方"), esc(money2(abs(balance)))))
    body.append("</tbody></table>\n")
    body.append("<p class=\"note\">%s</p>\n" % esc(MANAGEMENT_DECL))
    by_supplier = {}
    for key, row in sorted(ledger.items()):
        row_fields = row.get("fields") or {}
        row_type = row.get("ledger_type")
        if row_type == "AP":
            target = row_fields.get("supplier_id")
        elif row_type in ("PAYMENT", "REFUND"):
            target = row_fields.get("payee_supplier_id")
        else:
            continue
        bucket = by_supplier.setdefault(target, {"payable": 0, "paid": 0, "refund": 0})
        value = row_fields.get("amount_cents") or 0
        if row_type == "AP":
            value = row_fields.get("payable_amount_cents") or 0
            bucket["payable"] += value
        elif row_fields.get("transaction_type") == "REFUND":
            bucket["refund"] += value
        else:
            bucket["paid"] += value
    body.append("<h2>明细表（按供应商）</h2>\n")
    body.append("<table><thead><tr><th>供应商</th><th>应付</th><th>已付</th><th>退款</th>"
                "<th>净付</th><th>余额</th></tr></thead><tbody>\n")
    debit_hint = False
    for target in sorted(by_supplier, key=lambda item: str(item)):
        bucket = by_supplier[target]
        net = bucket["paid"] - bucket["refund"]
        residual = bucket["paid"] - bucket["payable"] - bucket["refund"]
        direction = "借方" if residual >= 0 else "贷方"
        if residual > 0:
            debit_hint = True
        label = "%s%s" % (target, "（%s）" % supplier_name(target, sources)
                          if supplier_name(target, sources) else "")
        body.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                    "<td>%s %s</td></tr>\n"
                    % (esc(label), esc(money2(bucket["payable"])), esc(money2(bucket["paid"])),
                       esc(money2(bucket["refund"])), esc(money2(net)),
                       esc(direction), esc(money2(abs(residual)))))
    body.append("</tbody></table>\n")
    if debit_hint:
        body.append("<p class=\"note\">审计提示：应付出现借方余额，通常意味着多付或预付，"
                    "需查明原因并考虑重分类（审计实务对应付账款明细表借方余额的分析）。</p>\n")
    body.append("<h2>凭证抽查（账证底稿）</h2>\n")
    body.append("<table><thead><tr><th>抽查对象</th><th>凭证编号</th><th>状态</th>"
                "<th>金额是否一致</th><th>查看</th></tr></thead><tbody>\n")
    for row in paid_rows:
        payment_id = (row.get("fields") or {}).get("payment_id")
        value = (row.get("fields") or {}).get("amount_cents")
        entry = None
        for candidate in approvals:
            if (candidate.get("fields") or {}).get("payment_id") == payment_id:
                entry = candidate
                break
        body.append(voucher_row("审批单（付款 %s）" % payment_id, entry, value))
    for row, entry in receipts:
        value = (row.get("fields") or {}).get("amount_cents")
        label = "%s（%s %s）" % ("回单", "退款" if row.get("ledger_type") == "REFUND" else "付款",
                                row.get("ledger_id"))
        body.append(voucher_row(label, entry, value))
    body.append("</tbody></table>\n")
    body.append("<h2>缺口声明</h2>\n<p>%s</p>\n" % esc(GAP_DECL))
    if GL_PRESENT:
        body.append("<p><a href=\"gl-journal.html\">查看记账凭证</a> · "
                    "<a href=\"gl-trial-balance.html\">借贷核对</a></p>\n")
    body.append("<p class=\"foot\"><a href=\"all-ledger.html\">全量台账</a> · "
                "<a href=\"all-vouchers.html\">全量凭证</a> · "
                "<a href=\"all-source.html\">全量原始表行</a> · "
                "<a href=\"index.html\">问题清单</a> · "
                "<a href=\"guide.html\">口径与对账指引</a></p>\n")
    return page("业务勾稽底稿 %s" % ap_id, "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 业务勾稽底稿 %s" % esc(ap_id),
                back="index.html", review_version=review_version)



def gl_accounts(gl):
    return {item.get("code"): item for item in
            (gl.get("chart_of_accounts") or {}).get("accounts") or []}


def gl_money(cents):
    return money2(cents)


def render_gl_trial_page(gl, version):
    accounts = gl_accounts(gl)
    trial = gl.get("trial_balance") or {}
    body = ["<h1>科目余额表</h1>\n"]
    body.append("<p class=\"note\">数字取自索引的 GL 节，不重算；借贷分列，应付借方余额高亮。</p>\n")
    body.append("<table><thead><tr><th>科目</th><th>期初借</th><th>期初贷</th>"
                "<th>本期借</th><th>本期贷</th><th>期末借</th><th>期末贷</th></tr></thead><tbody>\n")
    for row in trial.get("rows") or []:
        code = row.get("account")
        name = (accounts.get(code) or {}).get("name", "")
        highlight = ' class="yellow"' if code == "2202" and row.get("closing_debit") else ""
        body.append("<tr%s><td>%s %s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                    "<td>%s</td><td>%s</td></tr>\n"
                    % (highlight, esc(code), esc(name),
                       esc(gl_money(row.get("opening_debit"))),
                       esc(gl_money(row.get("opening_credit"))),
                       esc(gl_money(row.get("debit_cents"))),
                       esc(gl_money(row.get("credit_cents"))),
                       esc(gl_money(row.get("closing_debit"))),
                       esc(gl_money(row.get("closing_credit")))))
    totals = trial.get("totals") or {}
    body.append("<tr><td>合计</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                "<td>%s</td><td>%s</td></tr>\n"
                % (esc(gl_money(totals.get("opening_debit"))),
                   esc(gl_money(totals.get("opening_credit"))),
                   esc(gl_money(totals.get("debit_cents"))),
                   esc(gl_money(totals.get("credit_cents"))),
                   esc(gl_money(totals.get("closing_debit"))),
                   esc(gl_money(totals.get("closing_credit")))))
    body.append("</tbody></table>\n")
    body.append("<p class=\"note\">期末借方合计 %s = 期末贷方合计 %s。</p>\n"
                % (esc(gl_money(totals.get("closing_debit"))),
                   esc(gl_money(totals.get("closing_credit")))))
    body.append("<p class=\"foot\"><a href=\"gl-journal.html\">记账凭证</a> · "
                "<a href=\"gl-ledger.html\">总账与明细账</a> · "
                "<a href=\"gl-report.html\">账表核对</a> · "
                "<a href=\"gl-bank.html\">银行调节</a> · "
                "<a href=\"gl-checks.html\">核对结果</a></p>\n")
    return page("科目余额表", "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 借贷核对 › 科目余额表",
                back="index.html", review_version=version)


def render_gl_journal_page(gl, version):
    accounts = gl_accounts(gl)
    body = ["<h1>记账凭证分录</h1>\n"]
    body.append("<p class=\"note\">逐张列示借贷科目、金额、附件与对应业务单据；金额取自索引。</p>\n")
    body.append("<table><thead><tr><th>凭证号</th><th>日期</th><th>摘要</th><th>行</th>"
                "<th>科目</th><th>借方</th><th>贷方</th><th>附件</th>"
                "<th>关联账务</th><th>关联事项</th></tr></thead><tbody>\n")
    for entry in gl.get("journal_entries") or []:
        lines = entry.get("lines") or []
        for index, line in enumerate(lines, start=1):
            code = line.get("account")
            name = (accounts.get(code) or {}).get("name", "")
            attachments = "、".join("<a href=\"voucher-%s.html\">%s</a>"
                                   % (esc(item), esc(item))
                                   for item in entry.get("attachments") or [])
            links = "、".join("<a href=\"ledger-%s-%s.html\">%s</a>"
                             % (esc(ref.get("ledger_type")), esc(ref.get("ledger_id")),
                                esc(ref.get("ledger_id")))
                             for ref in entry.get("ledger_refs") or [])
            case_links = "、".join("<a href=\"case-%s.html\">%s</a>"
                                  % (esc(item), esc(item))
                                  for item in entry.get("case_refs") or [])
            body.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%d</td>"
                        "<td>%s %s</td><td>%s</td><td>%s</td><td>%s</td>"
                        "<td>%s</td><td>%s</td></tr>\n"
                        % (esc(entry.get("entry_id")), esc(entry.get("date")),
                           esc(entry.get("summary")), index, esc(code), esc(name),
                           esc(gl_money(line.get("debit_cents"))),
                           esc(gl_money(line.get("credit_cents"))),
                           attachments or "—", links or "—", case_links or "—"))
    body.append("</tbody></table>\n")
    body.append("<p class=\"foot\"><a href=\"gl-trial-balance.html\">科目余额表</a> · "
                "<a href=\"gl-ledger.html\">总账与明细账</a> · "
                "<a href=\"business-AP01.html\">业务勾稽底稿</a></p>\n")
    return page("记账凭证分录", "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 借贷核对 › 记账凭证",
                back="index.html", review_version=version)


def render_gl_ledger_page(gl, version):
    accounts = gl_accounts(gl)
    body = ["<h1>总账与明细账</h1>\n"]
    body.append("<p class=\"note\">总账按科目；明细账按 AP01 / 基本户逐笔滚动，余额方向按借贷列示。</p>\n")
    body.append("<h2>总账</h2>\n<table><thead><tr><th>科目</th><th>本期借</th>"
                "<th>本期贷</th><th>期末借</th><th>期末贷</th></tr></thead><tbody>\n")
    for row in (gl.get("ledger_general") or {}).get("accounts") or []:
        code = row.get("account")
        body.append("<tr><td>%s %s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>\n"
                    % (esc(code), esc((accounts.get(code) or {}).get("name", "")),
                       esc(gl_money(row.get("debit_cents"))),
                       esc(gl_money(row.get("credit_cents"))),
                       esc(gl_money(row.get("closing_debit"))),
                       esc(gl_money(row.get("closing_credit")))))
    body.append("</tbody></table>\n")
    for item in (gl.get("ledger_subsidiary") or {}).get("subsidiaries") or []:
        body.append("<h2>%s（对象：%s）</h2>\n" % (esc(item.get("name")),
                                                   esc(item.get("object"))))
        body.append("<table><thead><tr><th>日期</th><th>凭证号</th><th>借方</th>"
                    "<th>贷方</th><th>余额方向</th><th>余额</th></tr></thead><tbody>\n")
        for row in item.get("entries") or []:
            direction = "借" if row.get("balance_debit") else "贷"
            amount = row.get("balance_debit") or row.get("balance_credit")
            body.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                        "<td>%s</td><td>%s</td></tr>\n"
                        % (esc(row.get("date")), esc(row.get("entry_id")),
                           esc(gl_money(row.get("debit_cents"))),
                           esc(gl_money(row.get("credit_cents"))),
                           esc(direction), esc(gl_money(amount))))
        body.append("</tbody></table>\n")
    body.append("<p class=\"foot\"><a href=\"gl-trial-balance.html\">科目余额表</a> · "
                "<a href=\"gl-journal.html\">记账凭证</a> · "
                "<a href=\"gl-report.html\">账表核对</a></p>\n")
    return page("总账与明细账", "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 借贷核对 › 总账与明细账",
                back="index.html", review_version=version)


def render_gl_report_page(gl, version):
    trial = {row.get("account"): row for row in
             (gl.get("trial_balance") or {}).get("rows") or []}
    sheet = gl.get("balance_sheet") or {}
    def signed(code):
        row = trial.get(code) or {}
        return row.get("closing_debit", 0) - row.get("closing_credit", 0)
    mapping = [
        ("货币资金", "1002", signed("1002")), ("存货", "1001", signed("1001")),
        ("预付账款", "2202 借方", max(0, signed("2202"))),
        ("应付账款", "2202 贷方", max(0, -signed("2202"))),
        ("实收资本", "3001", max(0, -signed("3001"))),
    ]
    actual = {}
    for group in ("assets", "liabilities", "equity"):
        for item in sheet.get(group) or []:
            actual[item.get("item")] = item.get("amount_cents")
    body = ["<h1>账表核对</h1>\n"]
    body.append("<p class=\"note\">科目余额表期末与报表项目逐项对照；应付借方余额 4,000.00 重分类为预付账款。</p>\n")
    body.append("<table><thead><tr><th>报表项目</th><th>科目余额表</th>"
                "<th>报表金额</th><th>差异</th></tr></thead><tbody>\n")
    for item, source, value in mapping:
        reported = actual.get(item)
        diff = (value - reported) if type(reported) is int else None
        body.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>\n"
                    % (esc(item), esc(gl_money(value)), esc(gl_money(reported)),
                       esc(gl_money(diff) if diff is not None else "—")))
    assets = sum(item.get("amount_cents", 0) for item in sheet.get("assets") or [])
    other = sum(item.get("amount_cents", 0) for item in sheet.get("liabilities") or []) + \
        sum(item.get("amount_cents", 0) for item in sheet.get("equity") or [])
    body.append("<tr><td>资产合计</td><td>%s</td><td>%s</td><td>%s</td></tr>\n"
                % (esc(gl_money(sheet.get("total_assets_cents"))),
                   esc(gl_money(assets)),
                   esc(gl_money((sheet.get("total_assets_cents") or 0) - assets))))
    body.append("<tr><td>负债 + 权益合计</td><td>%s</td><td>%s</td><td>%s</td></tr>\n"
                % (esc(gl_money(sheet.get("total_liabilities_equity_cents"))),
                   esc(gl_money(other)),
                   esc(gl_money((sheet.get("total_liabilities_equity_cents") or 0) - other))))
    body.append("</tbody></table>\n")
    body.append("<p class=\"note\">资产 %s = 负债 + 权益 %s。</p>\n"
                % (esc(gl_money(assets)), esc(gl_money(other))))
    body.append("<p class=\"foot\"><a href=\"gl-trial-balance.html\">科目余额表</a> · "
                "<a href=\"gl-checks.html\">核对结果</a></p>\n")
    return page("账表核对", "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 借贷核对 › 账表核对",
                back="index.html", review_version=version)


def render_gl_bank_page(gl, version):
    statement = gl.get("bank_statement") or {}
    journal = gl.get("bank_journal") or {}
    entries = statement.get("entries") or []
    inflow = sum(item.get("amount_cents", 0) for item in entries
                 if item.get("direction") == "IN")
    outflow = sum(item.get("amount_cents", 0) for item in entries
                  if item.get("direction") == "OUT")
    bank_check = next((item for item in gl.get("checks") or []
                       if item.get("id") == "bank_reconcile"), {})
    journal_only = sum(1 for finding in bank_check.get("findings") or []
                       if finding.get("side") == "账有实无")
    statement_only = sum(1 for finding in bank_check.get("findings") or []
                         if finding.get("side") == "实有账无")
    body = ["<h1>银行余额调节表</h1>\n"]
    body.append("<p class=\"note\">期初 + 收入 − 支出 = 期末；未达账项分列账有实无 / 实有账无。</p>\n")
    body.append("<table><thead><tr><th>项目</th><th>金额</th></tr></thead><tbody>\n")
    body.append("<tr><td>期初余额</td><td>%s</td></tr>\n"
                % esc(gl_money(statement.get("opening_balance_cents"))))
    body.append("<tr><td>加：收入</td><td>%s</td></tr>\n" % esc(gl_money(inflow)))
    body.append("<tr><td>减：支出</td><td>%s</td></tr>\n" % esc(gl_money(outflow)))
    body.append("<tr><td>期末余额（对账单）</td><td>%s</td></tr>\n"
                % esc(gl_money(statement.get("closing_balance_cents"))))
    body.append("<tr><td>期末余额（日记账）</td><td>%s</td></tr>\n"
                % esc(gl_money(journal.get("closing_balance_cents"))))
    body.append("<tr><td>账有实无</td><td>%d 笔</td></tr>\n" % journal_only)
    body.append("<tr><td>实有账无</td><td>%d 笔</td></tr>\n" % statement_only)
    body.append("</tbody></table>\n")
    body.append("<p class=\"note\">期初 %s + 收入 %s − 支出 %s = 期末 %s。</p>\n"
                % (esc(gl_money(statement.get("opening_balance_cents"))),
                   esc(gl_money(inflow)), esc(gl_money(outflow)),
                   esc(gl_money(statement.get("closing_balance_cents")))))
    body.append("<p class=\"foot\"><a href=\"gl-checks.html\">核对结果</a> · "
                "<a href=\"gl-trial-balance.html\">科目余额表</a></p>\n")
    return page("银行余额调节表", "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 借贷核对 › 银行调节",
                back="index.html", review_version=version)


def render_gl_checks_page(gl, version):
    body = ["<h1>核对结果</h1>\n"]
    body.append("<p class=\"note\">六类 + 附件核对状态、差异数与备注；数字取自核对报告。</p>\n")
    body.append("<table><thead><tr><th>检查项</th><th>状态</th><th>差异数</th></tr></thead><tbody>\n")
    for check in gl.get("checks") or []:
        body.append("<tr><td>%s</td><td>%s</td><td>%d</td></tr>\n"
                    % (esc(check.get("title")), esc(check.get("status")),
                       len(check.get("findings") or [])))
    body.append("</tbody></table>\n")
    summary = gl.get("summary") or {}
    body.append("<h2>备注</h2>\n<ul>\n")
    for note in summary.get("notes") or []:
        body.append("<li>%s</li>\n" % esc(note))
    body.append("</ul>\n")
    body.append("<h2>未执行</h2>\n<ul>\n")
    for item in gl.get("unperformed") or []:
        body.append("<li>%s</li>\n" % esc(item))
    body.append("</ul>\n")
    body.append("<p class=\"note\">核对结果只展示证据与差异，不构成审计结论。</p>\n")
    body.append("<p class=\"foot\"><a href=\"gl-trial-balance.html\">科目余额表</a> · "
                "<a href=\"gl-journal.html\">记账凭证</a> · "
                "<a href=\"gl-ledger.html\">总账与明细账</a> · "
                "<a href=\"gl-report.html\">账表核对</a> · "
                "<a href=\"gl-bank.html\">银行调节</a></p>\n")
    return page("核对结果", "".join(body),
                breadcrumb="<a href=\"index.html\">问题清单</a> › 借贷核对 › 核对结果",
                back="index.html", review_version=version)

def build(index_path: Path, out_dir: Path) -> int:
    index = load_index(index_path)
    ledger, vouchers, sources = validate(index)
    global GL_PRESENT
    GL_PRESENT = "gl" in index
    pages = {}
    index_pages, total_pages = render_index_pages(index)
    for name, payload in index_pages:
        pages[name] = payload
    version = ((index.get("meta") or {}).get("source_identity") or {}).get("sha256") or ""
    version = version[:12]
    cases = index["cases"]
    for position, case in enumerate(cases):
        prev_case = cases[position - 1] if position > 0 else None
        next_case = cases[position + 1] if position + 1 < len(cases) else None
        pages["case-%s.html" % case["case_id"]] = render_case_page(
            case, prev_case, next_case, version)
        pages["compare-%s.html" % case["case_id"]] = render_compare_page(
            case, ledger, vouchers, sources)
    for key in sorted(ledger, key=lambda item: (item[0] or "", item[1] or "")):
        row = ledger[key]
        pages["ledger-%s-%s.html" % (key[0], key[1])] = render_ledger_page(
            row, sources, version, key[1] if key[0] == "AP" else None)
    for voucher_id in sorted(vouchers):
        pages["voucher-%s.html" % voucher_id] = render_voucher_page(
            vouchers[voucher_id], version)
    involved_sources = {(ref.get("sheet"), ref.get("excel_row"))
                        for case in cases for ref in case.get("source_refs") or []}
    for key in sorted(ledger, key=lambda item: (item[0] or "", item[1] or "")):
        found = find_source_row(ledger[key], sources)
        if found is not None:
            involved_sources.add((found.get("sheet"), found.get("excel_row")))
    for key in sorted(sources, key=lambda item: (item[0] or "", item[1] or 0)):
        row = sources[key]
        pages["source-%s-%s.html" % (key[0], key[1])] = render_source_page(
            row, key in involved_sources, version)
    # 全量清单页（50 行/页）
    def add_list(title, headers, rows, base_name, note):
        count = max(1, (len(rows) + CASES_PER_PAGE - 1) // CASES_PER_PAGE)
        for page_index in range(count):
            name, payload = render_list_page(title, headers, rows, page_index, count,
                                             base_name, note, version)
            pages[name] = payload

    ledger_list = []
    for key in sorted(ledger, key=lambda item: (item[0] or "", item[1] or "")):
        row = ledger[key]
        fields = row.get("fields") or {}
        cents = fields.get("payable_amount_cents")
        if cents is None:
            cents = fields.get("amount_cents")
        if cents is None:
            cents = fields.get("allocated_amount_cents")
        source = row.get("source") or {}
        source_link = ("<a href=\"source-%s-%s.html\">查看</a>"
                       % (esc(source.get("sheet")), esc(source.get("excel_row")))
                       if source.get("excel_row") is not None else "—")
        status = display_status(row.get("status"))
        cells = [esc(LEDGER_TYPE_LABEL.get(row.get("ledger_type"), "账务")),
                 "<a href=\"ledger-%s-%s.html\">%s</a>"
                 % (esc(key[0]), esc(key[1]), esc(key[1])),
                 esc(status), esc(cents if cents is not None else "—"),
                 esc(SHEET_LABEL.get(source.get("sheet"), "原表")), source_link]
        ledger_list.append({"cells": cells,
                            "class": list_status_class(status),
                            "review": row.get("review"),
                            "record_id": key[1], "record_type": "ledger",
                            "text": "%s %s %s" % (key[0], key[1], status)})
    add_list("全量台账", ["账务类型", "编号", MACHINE_RESULT, "金额（分）", "来源工作表", "查看"],
             ledger_list, "all-ledger", "全量账务行（含机器核对结果与来源）")
    voucher_list = []
    for voucher_id in sorted(vouchers):
        entry = vouchers[voucher_id]
        status = entry.get("status", "已取得")
        cells = [esc(VOUCHER_TYPE_LABEL.get(entry.get("voucher_type"), "凭证")),
                 "<a href=\"voucher-%s.html\">%s</a>" % (esc(voucher_id), esc(voucher_id)),
                 esc(status),
                 "<a href=\"voucher-%s.html\">查看</a>" % esc(voucher_id)]
        voucher_list.append({"cells": cells, "class": "ok" if status == "已取得" else "neutral",
                             "review": entry.get("review"),
                             "record_id": voucher_id, "record_type": "voucher",
                             "text": "%s %s" % (voucher_id, status)})
    add_list("全量凭证", ["凭证类型", "凭证编号", "机器核对结果（程序）", "查看"], voucher_list,
             "all-vouchers", "全量凭证（含机器核对结果）")
    source_list = []
    for key in sorted(sources, key=lambda item: (item[0] or "", item[1] or 0)):
        row = sources[key]
        status = "已涉及" if key in involved_sources else NOT_INCLUDED
        cells = [esc(SHEET_LABEL.get(row.get("sheet"), "原表")),
                 esc(row.get("excel_row")), esc(status),
                 "<a href=\"source-%s-%s.html\">查看</a>" % (esc(key[0]), esc(key[1]))]
        source_list.append({"cells": cells,
                            "class": "ok" if key in involved_sources else "neutral",
                            "review": row.get("review"),
                            "record_id": "%s!%s" % (row.get("sheet"), row.get("excel_row")),
                            "record_type": "source",
                            "text": "%s %s %s" % (row.get("sheet"), row.get("excel_row"), status)})
    add_list("全量原始表行", ["工作表", "行号", "机器核对结果（程序）", "查看"], source_list,
             "all-source", "四张表全部数据行（含机器核对结果）")
    pages["records.html"] = render_records_page(index)
    pages["guide.html"] = render_guide_page()
    if GL_PRESENT:
        pages["gl-trial-balance.html"] = render_gl_trial_page(index["gl"], version)
        pages["gl-journal.html"] = render_gl_journal_page(index["gl"], version)
        pages["gl-ledger.html"] = render_gl_ledger_page(index["gl"], version)
        pages["gl-report.html"] = render_gl_report_page(index["gl"], version)
        pages["gl-bank.html"] = render_gl_bank_page(index["gl"], version)
        pages["gl-checks.html"] = render_gl_checks_page(index["gl"], version)
    for key in sorted(ledger, key=lambda item: (item[0] or "", item[1] or "")):
        if key[0] == "AP":
            pages["business-%s.html" % key[1]] = render_business_page(
                ledger[key], ledger, vouchers, sources, version)
    out_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for name in sorted(pages):
        payload = pages[name]
        (out_dir / name).write_bytes(payload)
        total_bytes += len(payload)
    for name in ("trace_index.json",):
        if (out_dir / name).exists():
            raise SiteError("usage", "输出目录已含同名文件：%s" % name)
    print(json.dumps({"status": "PASS", "cases": len(cases), "pages": len(pages),
                      "index_pages": total_pages, "bytes": total_bytes,
                      "out": str(out_dir)}, ensure_ascii=False))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-049 证据链下钻 HTML")
    parser.add_argument("--index", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    index_path = Path(args.index)
    out_dir = Path(args.out_dir)
    try:
        if not index_path.is_file():
            raise SiteError("usage", "索引不存在：%s" % index_path)
        try:
            out_dir.resolve().relative_to(TEST_ROOT.resolve())
        except ValueError:
            raise SiteError("usage", "--out-dir 必须位于 %s 之下" % TEST_ROOT)
        if out_dir.exists():
            raise SiteError("usage", "--out-dir 必须从未存在：%s" % out_dir)
        if not out_dir.name.startswith(("task049_", "task051_", "task052_", "task053_", "task054_", "task057_")):
            raise SiteError("usage", "--out-dir 目录名必须以 task049_、task051_、task052_、task053_、task054_ 或 task057_ 开头")
        return build(index_path, out_dir)
    except SiteError as exc:
        print(json.dumps({"status": "ERROR", "kind": exc.kind, "error": str(exc),
                          "field": exc.field}, ensure_ascii=False))
        return 1 if exc.kind == "content" else 2


if __name__ == "__main__":
    raise SystemExit(main())
