#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-055：生成合成总账输入包 GL v1（`gl-1.0`，仅标准库，确定性）。

用法：
    python -B scripts/build_gl_demo_inputs.py --out-dir data/evidence_inputs/gl_v1

输入包内容（全部整数分；日期 ISO；无时间戳/随机数）：
科目表、4 张记账凭证、科目余额表、总账、明细账、报表摘录、银行对账单、银行日记账、
附件索引、gl_manifest.json（版本/期间/批次绑定/逐文件长度与 SHA/生成器版本）。

边界：GL v1 是**合成账套**，不证明真实账务，不构成审计结论；不做数据清洗；不规整整包退回。
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BATCH = ROOT / "data/batches/task027r1_run_04/batch_normal/batch_manifest.json"
GENERATOR_VERSION = "TASK-055-gl-demo-1.0"
PERIOD = {"period_start": "2026-09-01", "period_end": "2026-09-30",
          "cutoff_date": "2026-09-30"}
BATCH_ID = "task027r1_run_04"

ACCOUNTS = [
    {"code": "1001", "name": "库存商品", "type": "ASSET", "direction": "DEBIT"},
    {"code": "1002", "name": "银行存款", "type": "ASSET", "direction": "DEBIT"},
    {"code": "2202", "name": "应付账款", "type": "LIABILITY", "direction": "CREDIT"},
    {"code": "3001", "name": "实收资本", "type": "EQUITY", "direction": "CREDIT"},
]


def entry(entry_id, date, summary, lines, attachments):
    return {"entry_id": entry_id, "date": date, "summary": summary,
            "lines": lines, "attachments": attachments}


def line(account, debit=0, credit=0, description=""):
    return {"account": account, "debit_cents": debit, "credit_cents": credit,
            "description": description}


JOURNAL = [
    entry("记-001", "2026-09-05", "采购入库并确认应付",
          [line("1001", debit=500000, description="库存商品入库"),
           line("2202", credit=500000, description="确认应付 AP01")],
          ["V-INV-0001", "V-CTR-0001", "V-GR-0001"]),
    entry("记-002", "2026-09-10", "支付 P01 应付",
          [line("2202", debit=500000, description="核销应付 AP01"),
           line("1002", credit=500000, description="银行付款 P01")],
          ["V-APR-0001", "V-BR-0001"]),
    entry("记-003", "2026-09-10", "支付 P02 应付",
          [line("2202", debit=500000, description="核销应付 AP01"),
           line("1002", credit=500000, description="银行付款 P02")],
          ["V-APR-0002", "V-BR-0003"]),
    entry("记-004", "2026-09-20", "收到退款 R01",
          [line("1002", debit=100000, description="银行收款 R01"),
           line("2202", credit=100000, description="冲回应付 AP01")],
          ["V-BR-0002"]),
]

TRIAL_BALANCE = {
    "period": PERIOD,
    "rows": [
        {"account": "1001", "opening_debit": 0, "opening_credit": 0,
         "debit_cents": 500000, "credit_cents": 0, "closing_debit": 500000,
         "closing_credit": 0},
        {"account": "1002", "opening_debit": 2000000, "opening_credit": 0,
         "debit_cents": 100000, "credit_cents": 1000000, "closing_debit": 1100000,
         "closing_credit": 0},
        {"account": "2202", "opening_debit": 0, "opening_credit": 0,
         "debit_cents": 1000000, "credit_cents": 600000, "closing_debit": 400000,
         "closing_credit": 0},
        {"account": "3001", "opening_debit": 0, "opening_credit": 2000000,
         "debit_cents": 0, "credit_cents": 0, "closing_debit": 0,
         "closing_credit": 2000000},
    ],
    "totals": {
        "opening_debit": 2000000, "opening_credit": 2000000,
        "debit_cents": 1600000, "credit_cents": 1600000,
        "closing_debit": 2000000, "closing_credit": 2000000,
    },
}

LEDGER_GENERAL = {
    "period": PERIOD,
    "accounts": [
        {"account": "1001", "debit_cents": 500000, "credit_cents": 0,
         "closing_debit": 500000, "closing_credit": 0},
        {"account": "1002", "debit_cents": 100000, "credit_cents": 1000000,
         "closing_debit": 1100000, "closing_credit": 0},
        {"account": "2202", "debit_cents": 1000000, "credit_cents": 600000,
         "closing_debit": 400000, "closing_credit": 0},
        {"account": "3001", "debit_cents": 0, "credit_cents": 0,
         "closing_debit": 0, "closing_credit": 2000000},
    ],
}

LEDGER_SUBSIDIARY = {
    "period": PERIOD,
    "subsidiaries": [
        {"name": "应付账款—AP01", "account": "2202", "object": "AP01",
         "opening_debit": 0, "opening_credit": 0,
         "entries": [
             {"entry_id": "记-001", "date": "2026-09-05", "debit_cents": 0,
              "credit_cents": 500000, "balance_debit": 0, "balance_credit": 500000},
             {"entry_id": "记-002", "date": "2026-09-10", "debit_cents": 500000,
              "credit_cents": 0, "balance_debit": 0, "balance_credit": 0},
             {"entry_id": "记-003", "date": "2026-09-10", "debit_cents": 500000,
              "credit_cents": 0, "balance_debit": 500000, "balance_credit": 0},
             {"entry_id": "记-004", "date": "2026-09-20", "debit_cents": 0,
              "credit_cents": 100000, "balance_debit": 400000, "balance_credit": 0},
         ],
         "total_debit_cents": 1000000, "total_credit_cents": 600000,
         "closing_debit": 400000, "closing_credit": 0},
        {"name": "银行存款—基本户", "account": "1002", "object": "基本户",
         "opening_debit": 2000000, "opening_credit": 0,
         "entries": [
             {"entry_id": "记-002", "date": "2026-09-10", "debit_cents": 0,
              "credit_cents": 500000, "balance_debit": 1500000, "balance_credit": 0},
             {"entry_id": "记-003", "date": "2026-09-10", "debit_cents": 0,
              "credit_cents": 500000, "balance_debit": 1000000, "balance_credit": 0},
             {"entry_id": "记-004", "date": "2026-09-20", "debit_cents": 100000,
              "credit_cents": 0, "balance_debit": 1100000, "balance_credit": 0},
         ],
         "total_debit_cents": 100000, "total_credit_cents": 1000000,
         "closing_debit": 1100000, "closing_credit": 0},
    ],
}

BALANCE_SHEET = {
    "period": PERIOD,
    "assets": [
        {"item": "货币资金", "amount_cents": 1100000},
        {"item": "存货", "amount_cents": 500000},
        {"item": "预付账款", "amount_cents": 400000},
    ],
    "liabilities": [
        {"item": "应付账款", "amount_cents": 0},
    ],
    "equity": [
        {"item": "实收资本", "amount_cents": 2000000},
    ],
    "total_assets_cents": 2000000,
    "total_liabilities_equity_cents": 2000000,
}

BANK_STATEMENT = {
    "period": PERIOD,
    "account": "基本户",
    "opening_balance_cents": 2000000,
    "entries": [
        {"date": "2026-09-10", "direction": "OUT", "amount_cents": 500000,
         "reference": "B001"},
        {"date": "2026-09-10", "direction": "OUT", "amount_cents": 500000,
         "reference": "B002"},
        {"date": "2026-09-20", "direction": "IN", "amount_cents": 100000,
         "reference": "BR001"},
    ],
    "closing_balance_cents": 1100000,
}

BANK_JOURNAL = {
    "period": PERIOD,
    "account": "基本户",
    "opening_balance_cents": 2000000,
    "entries": [
        {"date": "2026-09-10", "direction": "OUT", "amount_cents": 500000,
         "reference": "B001"},
        {"date": "2026-09-10", "direction": "OUT", "amount_cents": 500000,
         "reference": "B002"},
        {"date": "2026-09-20", "direction": "IN", "amount_cents": 100000,
         "reference": "BR001"},
    ],
    "closing_balance_cents": 1100000,
}

ATTACHMENTS = {
    "attachments": [
        {"voucher_id": "V-INV-0001", "voucher_type": "INVOICE", "amount_cents": 500000,
         "date": "2026-09-05"},
        {"voucher_id": "V-CTR-0001", "voucher_type": "CONTRACT", "amount_cents": 500000,
         "date": "2026-09-01"},
        {"voucher_id": "V-GR-0001", "voucher_type": "GOODS_RECEIPT", "amount_cents": 500000,
         "date": "2026-09-04"},
        {"voucher_id": "V-APR-0001", "voucher_type": "APPROVAL", "amount_cents": 500000,
         "date": "2026-09-10"},
        {"voucher_id": "V-BR-0001", "voucher_type": "BANK_RECEIPT", "amount_cents": 500000,
         "date": "2026-09-10"},
        {"voucher_id": "V-APR-0002", "voucher_type": "APPROVAL", "amount_cents": 500000,
         "date": "2026-09-10"},
        {"voucher_id": "V-BR-0003", "voucher_type": "BANK_RECEIPT", "amount_cents": 500000,
         "date": "2026-09-10"},
        {"voucher_id": "V-BR-0002", "voucher_type": "BANK_RECEIPT", "amount_cents": 100000,
         "date": "2026-09-20"},
    ],
}

FILES = [
    ("chart_of_accounts.json", {"version": "gl-1.0", "accounts": ACCOUNTS}),
    ("journal_entries.json", {"version": "gl-1.0", "period": PERIOD, "entries": JOURNAL}),
    ("trial_balance.json", {"version": "gl-1.0", **TRIAL_BALANCE}),
    ("ledger_general.json", {"version": "gl-1.0", **LEDGER_GENERAL}),
    ("ledger_subsidiary.json", {"version": "gl-1.0", **LEDGER_SUBSIDIARY}),
    ("balance_sheet.json", {"version": "gl-1.0", **BALANCE_SHEET}),
    ("bank_statement.json", {"version": "gl-1.0", **BANK_STATEMENT}),
    ("bank_journal.json", {"version": "gl-1.0", **BANK_JOURNAL}),
    ("attachment_index.json", {"version": "gl-1.0", **ATTACHMENTS}),
]


def dump(path: Path, payload: dict) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, indent=2,
                     sort_keys=True).encode("utf-8") + b"\n"
    path.write_bytes(raw)
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-055 生成合成总账输入包 GL v1")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--batch", default=str(DEFAULT_BATCH))
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (Path.cwd() / out_dir).resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        print(json.dumps({"status": "ERROR", "kind": "usage",
                          "error": "输出目录必须为空或不存在"}, ensure_ascii=False))
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_path = Path(args.batch)
    if not batch_path.is_file():
        print(json.dumps({"status": "ERROR", "kind": "usage",
                          "error": "批次清单不存在：%s" % batch_path}, ensure_ascii=False))
        return 2
    batch_sha = hashlib.sha256(batch_path.read_bytes()).hexdigest()
    files = {}
    for name, payload in FILES:
        raw = dump(out_dir / name, payload)
        files[name] = {"byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    manifest = {
        "version": "gl-1.0",
        "period": PERIOD,
        "batch": {"batch_id": BATCH_ID, "batch_manifest_sha256": batch_sha,
                  "source_workbook": "source/input.xlsx"},
        "files": files,
        "generator_version": GENERATOR_VERSION,
    }
    dump(out_dir / "gl_manifest.json", manifest)
    total = len(list(out_dir.iterdir()))
    print(json.dumps({"status": "PASS", "out": str(out_dir), "files": total,
                      "manifest_sha256": hashlib.sha256(
                          (out_dir / "gl_manifest.json").read_bytes()).hexdigest()},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
