#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-047：离线静态 HTML 演示报告（四相符 + 线索 + 初判，只读渲染）。

命令行：
    python -B scripts/build_demo_report_html.py --run-root <已完成的演示运行根> --out-dir <新证据根>

只读读取一次已完成的四相符演示证据（demo_summary / 契约登记 / 账证 / 账实 / 事实底稿 / 初判），
生成**单文件** `index.html`（内联 CSS、无脚本、无外链、A4 可打印、全部动态文本转义）与
`report_source.json`（逐输入文件长度/SHA-256、运行根名、生成器版本、命令；确定性输出，
不含时间戳/随机数）。不启动服务、不装依赖、不写输入/业务/批次/账务/Gate/历史。

边界：合成数据只读展示；不是批次批准、不是身份认证；`real_approval=null`、
真实独立初判未保存、`next_step_allowed=false`、`ai_enabled=false`；不证明凭证/流水真实，
不构成审计结论；核对结论由人填写。
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
EVIDENCE_INPUTS = ROOT / "data/evidence_inputs"
REPORT_VERSION = "TASK-047-demo-report-1.0"
GENERATOR = "scripts/build_demo_report_html.py"
EVIDENCE_SUBDIRS = ("task043_input_check", "task044_match", "task045_reconcile")
BOUNDARY_KEYS = ("workflow_connected", "execution_allowed", "next_step_allowed", "ai_enabled",
                 "identity_authenticated", "source_authenticity_proven",
                 "audit_conclusion_formed", "final_judgment_recorded",
                 "complete_history_verified")
NOT_EXECUTED = ("账表/账账（需报表层输入与另行授权）", "影像/OCR", "发票/回单外部查验",
                "函证/盘点", "AI 建议", "人类终判", "真实数据/真实批次批准/强认证")


class ReportError(Exception):
    def __init__(self, kind, message, field=None):
        super().__init__(message)
        self.kind = kind  # "usage" → exit 2；"content" → exit 1
        self.field = field


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_bytes())


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def ident(path: Path) -> dict:
    raw = path.read_bytes()
    return {"relative": rel(path), "byte_size": len(raw), "sha256": sha_bytes(raw)}


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def money(cents) -> str:
    if type(cents) is not int:
        return "—"
    return "%d 分（%.2f 元）" % (cents, cents / 100.0)


def require(document, path, label):
    current = document
    for key in path:
        if type(current) is not dict or key not in current:
            raise ReportError("content", "缺少必需字段：%s" % ".".join((label,) + path),
                              field="%s.%s" % (label, ".".join(path)))
        current = current[key]
    return current


def load_evidence(run_root: Path):
    name = run_root.name
    files = {
        "demo_summary": run_root / "demo_summary.json",
        "input_registry": run_root / "task043_input_check" / "input_registry.json",
        "voucher_report": run_root / "task044_match" / "voucher_match_report.json",
        "reconcile_report": run_root / "task045_reconcile" / "bank_reconcile_report.json",
        "fact_packet": ROOT / "data/runtime" / name / "normal.facts" / "fact_packet.json",
        "judgment": (ROOT / "data/human_initial_judgment_records" / name / "bound"
                     / "rec_0001" / "judgment_result.json"),
        "record_manifest": (ROOT / "data/human_initial_judgment_records" / name / "bound"
                            / "rec_0001" / "manifest.json"),
    }
    missing = [label for label, path in files.items() if not path.is_file()]
    if missing:
        raise ReportError("usage", "缺少运行根/业务根文件：%s" % ", ".join(missing),
                          field=missing[0])
    documents = {label: read_json(path) for label, path in files.items()}
    return name, documents, files


def build_source(run_root: Path, out_dir: Path, files) -> dict:
    return {
        "report_version": REPORT_VERSION,
        "generator": GENERATOR,
        "run_root": run_root.name,
        "command": {"argv": [GENERATOR, "--run-root", rel(run_root),
                             "--out-dir", "<out-dir>"]},
        "inputs": [ident(files[label]) for label in
                   ("demo_summary", "input_registry", "voucher_report",
                    "reconcile_report", "fact_packet", "judgment", "record_manifest")],
        "outputs": ["index.html"],
        "note": "确定性输出；不含时间戳、随机数或外部链接；只读读取既有合成证据。",
    }


def r02_details(fact_packet):
    findings = fact_packet.get("findings") or []
    rows = []
    for finding in findings:
        amounts = finding.get("amounts_cents") or {}
        display = finding.get("amounts_display_cny") or {}
        sources = []
        context = finding.get("context") or {}
        for key in ("payable", "allocations", "payments", "refunds"):
            entries = context.get(key)
            if type(entries) is dict:
                entries = [entries]
            if type(entries) is not list:
                continue
            for entry in entries:
                if type(entry) is not dict:
                    continue
                sheet = (entry.get("source") or {}).get("sheet")
                cells = entry.get("cells") or {}
                for field, cell in cells.items():
                    if type(cell) is not dict:
                        continue
                    if str(cell.get("target_field", "")).endswith("_cents") \
                            and sheet and cell.get("cell"):
                        token = "%s!%s" % (sheet, cell["cell"])
                        if token not in sources:
                            sources.append(token)
        rows.append({
            "finding_id": finding.get("finding_id"),
            "related_ids": finding.get("related_ids") or {},
            "amounts_cents": amounts,
            "amounts_display": display,
            "sources": sources,
            "refund_summary": finding.get("refund_summary") or {},
        })
    return rows


def render_html(documents, source, run_root_name) -> bytes:
    demo = documents["demo_summary"]
    registry = documents["input_registry"]
    voucher = documents["voucher_report"]
    reality = documents["reconcile_report"]
    facts = documents["fact_packet"]
    judgment = documents["judgment"]
    manifest = documents["record_manifest"]
    batch = require(demo, ("batch",), "demo_summary")
    rules = require(demo, ("rules",), "demo_summary")
    record = require(demo, ("record",), "demo_summary")
    four = require(demo, ("four_way",), "demo_summary")
    counts = require(registry, ("counts",), "input_registry")
    vsum = require(voucher, ("summary",), "voucher_report")
    rsum = require(reality, ("summary",), "reconcile_report")
    totals = require(reality, ("period_totals",), "reconcile_report")
    items = voucher.get("items") or []
    matched = reality.get("matched") or []
    human = require(judgment, ("record", "human_initial_judgment"), "judgment")
    fingerprints = manifest.get("fingerprints") or {}
    boundaries = demo.get("boundaries") or {}
    entity = batch.get("entity") or {}
    period = entity.get("period") or {}
    finding_rows = r02_details(facts)
    rules_counts = rules.get("counts") or {}
    balances = totals.get("balances") or {}
    v_item_status = (vsum.get("item_status") or {})

    parts = []
    parts.append("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n")
    parts.append("<title>合成 CAAT 演示报告（四相符 + 线索 + 初判）</title>\n")
    parts.append("<style>\n")
    parts.append("""
@page { size: A4; margin: 12mm 12mm 14mm 12mm; }
body { font-family: "Microsoft YaHei", "PingFang SC", "SimSun", serif; color: #1f2328;
       font-size: 10.5pt; line-height: 1.5; margin: 0; padding: 0; background: #ffffff; }
h1 { font-size: 18pt; margin: 0 0 4mm 0; }
h2 { font-size: 12.5pt; margin: 6mm 0 2mm 0; border-left: 4px solid #8a6d3b;
     padding-left: 2.5mm; }
h3 { font-size: 11pt; margin: 4mm 0 1.5mm 0; }
.banner { border: 2px solid #b71c1c; background: #fff3cd; padding: 3mm 4mm; margin: 0 0 4mm 0; }
.banner strong { color: #b71c1c; }
.meta { color: #57606a; font-size: 9.5pt; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 3mm 0; font-size: 9.5pt; }
th, td { border: 1px solid #d0d7de; padding: 1.6mm 2mm; text-align: left; vertical-align: top; }
th { background: #f6f8fa; font-weight: 600; }
tr.red td { background: #fde8e8; }
tr.yellow td { background: #fff8d6; }
.cards { display: flex; flex-wrap: wrap; gap: 3mm; margin: 2mm 0 3mm 0; }
.card { border: 1px solid #d0d7de; border-left: 4px solid #1f6feb; padding: 2.5mm 3mm;
        flex: 1 1 45%; min-width: 55mm; }
.card h3 { margin: 0 0 1.5mm 0; }
.card p { margin: 0.8mm 0; }
.ok { color: #1a7f37; font-weight: 600; }
.warn { color: #9a6700; font-weight: 600; }
.bad { color: #b71c1c; font-weight: 600; }
.note { color: #57606a; font-size: 9.5pt; }
.empty { color: #8b949e; }
.foot { margin-top: 8mm; border-top: 1px solid #d0d7de; padding-top: 3mm; }
ul { margin: 1mm 0 2mm 0; padding-left: 6mm; }
li { margin: 0.6mm 0; }
""")
    parts.append("</style>\n</head>\n<body>\n")

    # 1. 边界横幅
    parts.append("<div class=\"banner\"><strong>边界：合成数据只读演示报告</strong><br>")
    parts.append("本报告不是批次批准、不是身份认证；<code>real_approval=null</code>、")
    parts.append("真实独立初判未保存、不开放 AI 建议与人类终判；")
    parts.append("<strong>核对结论由人填写，工具不采集、不虚构</strong>；")
    parts.append("不证明凭证/流水真实，不构成审计证据或结论。</div>\n")

    # 2. 身份
    parts.append("<h1>合成采购付款 CAAT 演示报告</h1>\n")
    parts.append("<p class=\"meta\">批次 <strong>%s</strong> · 实体 %s · %s · 期间 %s 至 %s · 截至 %s"
                 " · 金额单位：整数分（1 元 = 100 分） · 运行根 <code>%s</code></p>\n"
                 % (esc(batch.get("batch_id")), esc(entity.get("company")),
                    esc(entity.get("currency")),
                    esc(period.get("period_start")), esc(period.get("period_end")),
                    esc(entity.get("cutoff_date")), esc(run_root_name)))

    # 3. 四相符卡片
    parts.append("<h2>四相符摘要</h2>\n<div class=\"cards\">\n")
    contract_ok = registry.get("conclusion") == "INPUT_V1_ACCEPTED"
    parts.append("<div class=\"card\"><h3>契约（输入登记）</h3>")
    parts.append("<p class=\"%s\">%s</p>" % ("ok" if contract_ok else "bad",
                                            esc(registry.get("conclusion"))))
    vouchers = counts.get("vouchers") or {}
    parts.append("<p>凭证 %s（回单 %s / 审批 %s / 其他 %s）；links %s；流水 %s</p>" % (
        esc(counts.get("voucher_total")), esc(vouchers.get("BANK_RECEIPT")),
        esc(vouchers.get("APPROVAL")),
        esc((vouchers.get("INVOICE") or 0) + (vouchers.get("CONTRACT") or 0)
            + (vouchers.get("GOODS_RECEIPT") or 0)),
        esc(counts.get("links")), esc(counts.get("bank_transactions"))))
    parts.append("<p class=\"note\">input_version=%s</p></div>\n"
                 % esc(registry.get("input_version")))
    v_ok = voucher.get("conclusion") == "ALL_MATCHED"
    parts.append("<div class=\"card\"><h3>账证相符（字段级 L1）</h3>")
    parts.append("<p class=\"%s\">%s</p>" % ("ok" if v_ok else "bad",
                                            esc(voucher.get("conclusion"))))
    parts.append("<p>%s / %s 项 MATCHED；差异 %s；账有证无 %s；证有账无 %s</p>" % (
        esc(v_item_status.get("MATCHED")), esc(vsum.get("items_total")),
        esc(vsum.get("differences_total")), esc(vsum.get("missing_total")),
        esc(vsum.get("extra_total"))))
    parts.append("<p class=\"note\">R02 抽样：%s；层级 %s</p></div>\n" % (
        esc("、".join(item.get("ledger_id", "") for item in
                     (voucher.get("r02_sampling") or {}).get("items") or [])),
        esc(voucher.get("verification_level"))))
    r_ok = reality.get("conclusion") == "ALL_MATCHED"
    parts.append("<div class=\"card\"><h3>账实相符（银行交易级）</h3>")
    parts.append("<p class=\"%s\">%s</p>" % ("ok" if r_ok else "bad",
                                            esc(reality.get("conclusion"))))
    parts.append("<p>%s / %s 匹配；依据 %s</p>" % (
        esc(rsum.get("matched")), esc(rsum.get("ledger_records")),
        esc("、".join(sorted({item.get("basis", "") for item in matched})))))
    parts.append("<p>OUT %s vs 已结算付款 %s（差 %s）；IN %s vs 退款 %s（差 %s）</p>" % (
        esc(totals.get("out_total_cents")), esc(totals.get("settled_payments_total_cents")),
        esc(totals.get("out_difference_cents")), esc(totals.get("in_total_cents")),
        esc(totals.get("refunds_total_cents")), esc(totals.get("in_difference_cents"))))
    parts.append("<p>未达账项：账有实无 %s / 实有账无 %s；余额状态 %s</p>" % (
        esc(rsum.get("ledger_unmatched")), esc(rsum.get("bank_unmatched")),
        esc(balances.get("status"))))
    parts.append("<p class=\"note\">未达账项≠差错，需人类核查。</p></div>\n")
    status_ok = record.get("status") == "RT_HUMAN_INITIAL_JUDGMENT_VERIFIED"
    parts.append("<div class=\"card\"><h3>人类初判（只读恢复）</h3>")
    parts.append("<p class=\"%s\">%s</p>" % ("ok" if status_ok else "warn",
                                            esc(record.get("status"))))
    parts.append("<p>记录指纹 <code>%s</code></p>" % esc(record.get("record_fingerprint")))
    parts.append("<p>材料指纹 <code>%s</code></p>" % esc(
        fingerprints.get("materials_snapshot_fingerprint")))
    parts.append("<p class=\"note\">合成夹具回放，非真人审批。</p></div>\n</div>\n")

    # 4. 线索区
    parts.append("<h2>待核查线索（R01–R04，不是舞弊/损失/审计结论）</h2>\n")
    parts.append("<ul><li>R01 %s 条</li><li>R02 %s 条（超额合计 %s）</li>"
                 "<li>R03 %s 条</li><li>R04 %s 条</li></ul>\n" % (
                     esc(rules_counts.get("R01")), esc(rules_counts.get("R02")),
                     esc(money(rules.get("overpayment_total_cents"))),
                     esc(rules_counts.get("R03")), esc(rules_counts.get("R04"))))
    parts.append("<h3>R02 明细</h3>\n")
    if finding_rows:
        parts.append("<table><thead><tr><th>线索</th><th>应付</th><th>已付</th>"
                     "<th>退款</th><th>净额</th><th>超额</th><th>来源工作表与单元格</th></tr>"
                     "</thead><tbody>\n")
        for finding in finding_rows:
            amounts = finding["amounts_cents"]
            parts.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                         "<td class=\"bad\">%s</td><td>%s</td></tr>\n" % (
                             esc(finding["finding_id"]),
                             esc(money(amounts.get("payable_amount"))),
                             esc(money(amounts.get("paid_total"))),
                             esc(money(amounts.get("refund_total"))),
                             esc(money(amounts.get("net_total"))),
                             esc(money(amounts.get("overpayment"))),
                             esc("、".join(finding["sources"]))))
        parts.append("</tbody></table>\n")
    else:
        parts.append("<p class=\"empty\">（无 R02 明细）</p>\n")
    parts.append("<p class=\"note\">线索是待核查项，不构成舞弊、损失、控制缺陷或审计调整结论。</p>\n")

    # 5. 账证明细
    parts.append("<h2>账证明细</h2>\n")
    parts.append("<table><thead><tr><th>账务类型</th><th>账务 ID</th><th>金额（分）</th>"
                 "<th>凭证类型</th><th>凭证 ID</th><th>状态</th><th>核对结论</th></tr>"
                 "</thead><tbody>\n")
    for item in items:
        status = item.get("status")
        css_class = "red" if status in ("MISSING_VOUCHER", "EXTRA_VOUCHER") else (
            "yellow" if status and status != "MATCHED" else "")
        parts.append("<tr class=\"%s\"><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                     "<td>%s</td><td>%s</td><td class=\"empty\">（由人填写）</td></tr>\n" % (
                         css_class, esc(item.get("ledger_type")),
                         esc(item.get("ledger_id")), esc(item.get("ledger_amount_cents")),
                         esc(item.get("voucher_type")),
                         esc("、".join(item.get("voucher_ids") or []) or "—"),
                         esc(status)))
    parts.append("</tbody></table>\n")
    parts.append("<p class=\"note\">差异与账有证无/证有账无用红黄高亮；核对结论列留空，"
                 "由人填写，工具不采集、不虚构。</p>\n")

    # 6. 账实明细
    parts.append("<h2>账实明细</h2>\n")
    parts.append("<table><thead><tr><th>账务 ID</th><th>类型</th><th>流水 ID</th>"
                 "<th>依据</th></tr></thead><tbody>\n")
    for item in matched:
        parts.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>\n" % (
            esc(item.get("ledger_id")), esc(item.get("ledger_type")),
            esc(item.get("bank_txn_id")), esc(item.get("basis"))))
    parts.append("</tbody></table>\n")
    parts.append("<p>期间合计：OUT %s 分 vs 已结算付款 %s 分（差 %s）；"
                 "IN %s 分 vs 退款 %s 分（差 %s）。余额状态：%s（%s）</p>\n" % (
                     esc(totals.get("out_total_cents")),
                     esc(totals.get("settled_payments_total_cents")),
                     esc(totals.get("out_difference_cents")),
                     esc(totals.get("in_total_cents")),
                     esc(totals.get("refunds_total_cents")),
                     esc(totals.get("in_difference_cents")),
                     esc(balances.get("status")), esc(balances.get("note"))))
    unmatched = reality.get("unmatched") or {}
    rows = unmatched.get("ledger_unmatched") or []
    parts.append("<h3>未达账项（两侧分列，≠差错）</h3>\n")
    if rows:
        parts.append("<table><thead><tr><th>账务 ID</th><th>类型</th><th>金额（分）</th>"
                     "<th>日期</th></tr></thead><tbody>\n")
        for item in rows:
            parts.append("<tr class=\"yellow\"><td>%s</td><td>%s</td><td>%s</td>"
                         "<td>%s</td></tr>\n" % (
                             esc(item.get("ledger_id")), esc(item.get("ledger_type")),
                             esc(item.get("amount_cents")), esc(item.get("payment_date"))))
        parts.append("</tbody></table>\n")
    else:
        parts.append("<p class=\"ok\">账有实无：0</p>\n")
    rows = unmatched.get("bank_unmatched") or []
    if rows:
        parts.append("<table><thead><tr><th>流水 ID</th><th>方向</th><th>日期</th>"
                     "<th>金额（分）</th><th>对方</th></tr></thead><tbody>\n")
        for item in rows:
            parts.append("<tr class=\"yellow\"><td>%s</td><td>%s</td><td>%s</td>"
                         "<td>%s</td><td>%s</td></tr>\n" % (
                             esc(item.get("bank_txn_id")), esc(item.get("direction")),
                             esc(item.get("txn_date")), esc(item.get("amount_cents")),
                             esc(item.get("counterparty_name"))))
        parts.append("</tbody></table>\n")
    else:
        parts.append("<p class=\"ok\">实有账无：0</p>\n")

    # 7. 初判原文
    parts.append("<h2>人类初判原文（只读恢复，合成夹具回放）</h2>\n")
    actor = human.get("actor") or {}
    fields = [("event_id", human.get("event_id")),
              ("actor_id", actor.get("actor_id")),
              ("declaration_note", actor.get("declaration_note")),
              ("decided_at_raw", human.get("decided_at_raw")),
              ("assessment", human.get("assessment")),
              ("reason", human.get("reason"))]
    parts.append("<table><thead><tr><th>字段</th><th>原文</th></tr></thead><tbody>\n")
    for key, value in fields:
        parts.append("<tr><td>%s</td><td>%s</td></tr>\n" % (esc(key), esc(value)))
    parts.append("</tbody></table>\n")
    parts.append("<p>记录指纹 <code>%s</code>；材料指纹 <code>%s</code>；记录状态 %s</p>\n" % (
        esc(record.get("record_fingerprint")),
        esc(fingerprints.get("materials_snapshot_fingerprint")),
        esc(record.get("status"))))
    parts.append("<p class=\"note\">本初判为已登记合成夹具回放，不是现场真人点击审批；"
                 "人类核对结论由人填写，工具不采集、不虚构。</p>\n")

    # 8. 追溯链路
    parts.append("<h2>追溯链路</h2>\n<ol>\n")
    for step in ("Excel 四表（suppliers / payables / payments / allocations）",
                 "标准化（保留逐格来源）与 SQLite 装载",
                 "SQL 线索（R01–R04）与独立 Python 复算",
                 "事实底稿（可回到原始行与退款记录）",
                 "人类初判保存与只读恢复（VERIFIED）",
                 "账证相符（字段级 L1，以输入索引为基础）",
                 "账实相符（银行交易级，引用优先 + 三元组回退）"):
        parts.append("<li>%s</li>\n" % esc(step))
    parts.append("</ol>\n")

    # 9. 边界与未执行项
    parts.append("<h2>九权限边界（全部 false）与未执行项</h2>\n")
    parts.append("<table><thead><tr><th>边界</th><th>值</th></tr></thead><tbody>\n")
    for key in BOUNDARY_KEYS:
        value = boundaries.get(key)
        parts.append("<tr><td>%s</td><td>%s</td></tr>\n" % (esc(key),
                                                            esc("false" if value is False else value)))
    parts.append("</tbody></table>\n")
    parts.append("<p class=\"note\">未执行：%s。</p>\n" % esc("；".join(NOT_EXECUTED)))

    # 10. 页脚
    parts.append("<div class=\"foot\">\n")
    parts.append("<p class=\"meta\">生成命令：<code>%s</code></p>\n"
                 % esc(" ".join(source["command"]["argv"])))
    parts.append("<p class=\"meta\">输入证据身份摘要：%d 个输入文件（逐文件长度/SHA-256 见 "
                 "<code>report_source.json</code>）；生成器 %s；运行根 %s。</p>\n" % (
                     len(source["inputs"]), esc(source["report_version"]),
                     esc(source["run_root"])))
    parts.append("<p class=\"meta\">本报告不是审计结论，不证明凭证/流水真实；"
                 "核对结论由人填写。</p>\n")
    parts.append("</div>\n</body>\n</html>\n")
    return "".join(parts).encode("utf-8")


def run(run_root: Path, out_dir: Path) -> int:
    if not run_root.is_dir():
        raise ReportError("usage", "--run-root 不存在：%s" % run_root)
    try:
        run_root.resolve().relative_to(TEST_ROOT.resolve())
    except ValueError:
        raise ReportError("usage", "--run-root 必须位于 %s 之下" % TEST_ROOT)
    if out_dir.exists():
        raise ReportError("usage", "--out-dir 必须从未存在：%s" % out_dir)
    try:
        out_dir.resolve().relative_to(TEST_ROOT.resolve())
    except ValueError:
        raise ReportError("usage", "--out-dir 必须位于 %s 之下" % TEST_ROOT)
    if not out_dir.name.startswith("task047_"):
        raise ReportError("usage", "--out-dir 目录名必须以 task047_ 开头")
    name, documents, files = load_evidence(run_root)
    source = build_source(run_root, out_dir, files)
    payload = render_html(documents, source, name)
    out_dir.mkdir(parents=True)
    target = out_dir / "index.html"
    target.write_bytes(payload)
    if target.read_bytes() != payload:
        raise ReportError("usage", "index.html 写后读回不一致")
    source_path = out_dir / "report_source.json"
    source_path.write_bytes(json.dumps(source, ensure_ascii=False, indent=2,
                                       sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({"status": "PASS", "run_root": name,
                      "out": str(out_dir), "html_bytes": len(payload),
                      "inputs": len(source["inputs"])}, ensure_ascii=False))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-047 离线静态 HTML 演示报告")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    try:
        return run(Path(args.run_root), Path(args.out_dir))
    except ReportError as exc:
        print(json.dumps({"status": "ERROR", "kind": exc.kind, "error": str(exc),
                          "field": exc.field}, ensure_ascii=False))
        return 1 if exc.kind == "content" else 2


if __name__ == "__main__":
    raise SystemExit(main())
