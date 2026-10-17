#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-058：数据投放指引与状态页（只读扫描 data/inbox，生成状态页与清单）。

用法：
    python -B scripts/build_intake_guide.py --intake-root data/inbox \
        --out-dir data/runtime_initial_judgment_recording_tests/task058_status_01

输出：intake_status.html（纯静态、无脚本、纯审计语言）、intake_manifest.json
（逐目录/文件、状态、大小、SHA、更新时间）。只读：不复制、不移动、不修改 inbox。
状态：已提供 / 缺失 / 需校验（只读判断，不修数据）。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
GL_SCRIPT = ROOT / "scripts/gl_input_contract_v1.py"
GL_FILES = ("chart_of_accounts.json", "journal_entries.json", "trial_balance.json",
            "ledger_general.json", "ledger_subsidiary.json", "balance_sheet.json",
            "bank_statement.json", "bank_journal.json", "attachment_index.json",
            "gl_manifest.json")
BANNER = "原始数据收集区；本页只读扫描，不复制、不移动、不修改任何文件；不构成审计结论。"
STATUS_PROVIDED = "已提供"
STATUS_MISSING = "缺失"
STATUS_INVALID = "需校验"


class IntakeError(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_entry(path: Path) -> dict:
    stat = path.stat()
    mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return {"name": path.name, "byte_size": stat.st_size, "sha256": sha_file(path),
            "mtime": mtime}


def scan_dir(directory: Path) -> list:
    if not directory.is_dir():
        return []
    entries = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        try:
            entries.append(file_entry(path))
        except OSError:
            entries.append({"name": path.name, "byte_size": None, "sha256": None,
                            "mtime": None})
    return entries


def iso_date(value) -> bool:
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        datetime.datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def read_json_file(path: Path):
    """返回 (document, error)；任何解析/编码/IO 错误都转为 error，不抛出。"""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, "无法读取（%s）" % type(exc).__name__
    try:
        return json.loads(raw), None
    except (ValueError, UnicodeDecodeError):
        return None, "不是合法内容"


def validate_business(directory: Path, files: list) -> tuple:
    xlsx = [item for item in files if item["name"].lower().endswith(".xlsx")]
    if not xlsx:
        return STATUS_MISSING, "未发现 .xlsx 业务台账"
    for item in xlsx:
        try:
            raw = (directory / item["name"]).read_bytes()[:2]
        except OSError:
            return STATUS_INVALID, "无法读取 %s" % item["name"]
        if raw != b"PK":
            return STATUS_INVALID, "文件不是有效的 xlsx（%s）" % item["name"]
    return STATUS_PROVIDED, "已提供业务台账工作簿"


def validate_vouchers(directory: Path, files: list) -> tuple:
    index_path = directory / "index.json"
    if not index_path.is_file():
        return STATUS_MISSING, "缺少附件索引"
    index, error = read_json_file(index_path)
    if error:
        return STATUS_INVALID, "附件索引%s" % error
    if not isinstance(index, dict):
        return STATUS_INVALID, "附件索引顶层不是对象"
    entries = index.get("vouchers")
    if not isinstance(entries, list) or not entries:
        return STATUS_INVALID, "附件索引缺少 vouchers 列表"
    for entry in entries:
        if not isinstance(entry, dict):
            return STATUS_INVALID, "附件索引条目不是对象"
        voucher_id = entry.get("voucher_id")
        if not isinstance(voucher_id, str) or not voucher_id:
            return STATUS_INVALID, "附件索引凭证编号缺失"
        path = directory / (voucher_id + ".json")
        if not path.is_file():
            return STATUS_INVALID, "缺少凭证文件 %s.json" % voucher_id
        document, error = read_json_file(path)
        if error:
            return STATUS_INVALID, "%s.json %s" % (voucher_id, error)
        if not isinstance(document, dict):
            return STATUS_INVALID, "%s.json 顶层不是对象" % voucher_id
        if type(document.get("amount_cents")) is not int:
            return STATUS_INVALID, "%s.json 金额不是整数分" % voucher_id
        if "date" in document and not iso_date(document.get("date")):
            return STATUS_INVALID, "%s.json 日期不是 ISO 格式" % voucher_id
    return STATUS_PROVIDED, "附件索引与 %d 张凭证齐全" % len(entries)


def validate_bank(directory: Path, files: list) -> tuple:
    path = directory / "bank_transactions.json"
    if not path.is_file():
        return STATUS_MISSING, "缺少银行流水文件"
    document, error = read_json_file(path)
    if error:
        return STATUS_INVALID, "银行流水文件%s" % error
    if not isinstance(document, dict):
        return STATUS_INVALID, "银行流水文件顶层不是对象"
    transactions = document.get("transactions")
    if not isinstance(transactions, list) or not transactions:
        return STATUS_INVALID, "银行流水缺少 transactions 列表"
    for item in transactions:
        if not isinstance(item, dict):
            return STATUS_INVALID, "银行流水条目不是对象"
        if not iso_date(item.get("date")):
            return STATUS_INVALID, "银行流水日期不是 ISO 格式"
        if item.get("direction") not in ("IN", "OUT"):
            return STATUS_INVALID, "银行流水方向不是 IN/OUT"
        if type(item.get("amount_cents")) is not int:
            return STATUS_INVALID, "银行流水金额不是整数分"
        if not isinstance(item.get("reference"), str):
            return STATUS_INVALID, "银行流水参考号缺失"
    return STATUS_PROVIDED, "银行流水 %d 笔" % len(transactions)


def validate_gl(directory: Path) -> tuple:
    missing = [name for name in GL_FILES if not (directory / name).is_file()]
    if missing:
        return STATUS_MISSING, "缺少 %s" % "、".join(missing)
    for name in GL_FILES:
        document, error = read_json_file(directory / name)
        if error:
            return STATUS_INVALID, "%s %s" % (name, error)
        if not isinstance(document, dict):
            return STATUS_INVALID, "%s 顶层不是对象" % name
    try:
        completed = subprocess.run([sys.executable, "-B", str(GL_SCRIPT),
                                    "--gl-root", str(directory)],
                                   capture_output=True, text=True)
    except OSError:
        return STATUS_INVALID, "GL v1 校验命令无法执行"
    if completed.returncode == 0:
        return STATUS_PROVIDED, "GL v1 契约校验通过"
    return STATUS_INVALID, "GL v1 契约校验未通过（详见校验命令输出）"


CATEGORIES = (
    {"id": "business", "title": "业务台账", "dirname": "01_业务台账",
     "expected": "业务台账_<期间>.xlsx（suppliers/payables/payments/allocations 四表）",
     "validator": "input_contract_v1.py", "check": lambda d, f: validate_business(d, f)},
    {"id": "vouchers", "title": "凭证附件", "dirname": "02_凭证附件",
     "expected": "index.json + V-INV/CTR/BR/APR/GR-*.json",
     "validator": "附件索引结构 + 逐文件存在/金额整数分",
     "check": lambda d, f: validate_vouchers(d, f)},
    {"id": "bank", "title": "银行流水", "dirname": "03_银行流水",
     "expected": "bank_transactions.json（date/direction/amount_cents/reference）",
     "validator": "结构检查 + 字段格式", "check": lambda d, f: validate_bank(d, f)},
    {"id": "gl", "title": "总账账套", "dirname": "04_总账账套",
     "expected": "GL v1 十个文件（含 gl_manifest.json）",
     "validator": "gl_input_contract_v1.py", "check": lambda d, f: validate_gl(d)},
)


def rel_link(from_dir: Path, target: Path) -> str:
    try:
        return Path(target).resolve().relative_to(Path(from_dir).resolve()).as_posix()
    except ValueError:
        import os
        return os.path.relpath(str(target), str(from_dir)).replace("\\", "/")


def render_html(intake_root: Path, categories: list, out_dir: Path) -> bytes:
    parts = ["<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n",
             "<title>原始数据投放状态</title>\n<style>\n",
             "body { font-family: \"Microsoft YaHei\", \"PingFang SC\", \"SimSun\", serif;"
             " color: #1f2328; font-size: 10.5pt; line-height: 1.55; margin: 12mm; }\n",
             "h1 { font-size: 16pt; margin: 0 0 3mm 0; }\n",
             ".banner { border: 2px solid #b71c1c; background: #fff3cd; padding: 2.5mm 3.5mm;"
             " margin: 0 0 3mm 0; font-weight: 600; }\n",
             "table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm 0; font-size: 9.5pt; }\n",
             "th, td { border: 1px solid #d0d7de; padding: 1.6mm 2mm; text-align: left;"
             " vertical-align: top; }\n",
             "th { background: #f6f8fa; font-weight: 600; }\n",
             ".provided { background: #e6ffec; color: #1a7f37; font-weight: 600; }\n",
             ".missing { background: #fde8e8; color: #b71c1c; font-weight: 600; }\n",
             ".invalid { background: #fff8d6; color: #7a5b00; font-weight: 600; }\n",
             ".note { color: #57606a; font-size: 9.5pt; }\n",
             "h2 { font-size: 12pt; margin: 5mm 0 2mm 0; border-left: 4px solid #8a6d3b;"
             " padding-left: 2.5mm; }\n",
             "li { margin: 1mm 0; }\n</style>\n</head>\n<body>\n",
             "<div class=\"banner\">%s</div>\n" % BANNER,
             "<h1>原始数据投放状态</h1>\n",
             "<p class=\"note\">扫描目录：%s；状态规则：文件存在且可读 → 已提供；"
             "不存在 → 缺失；存在但格式/校验不符 → 需校验。只读判断，不修改任何文件。</p>\n"
             % esc(str(intake_root)),
             "<table><thead><tr><th>数据类别</th><th>应放目录</th><th>应放文件或模式</th>"
             "<th>状态</th><th>大小与更新时间</th><th>校验方式</th><th>说明</th>"
             "</tr></thead><tbody>\n"]
    for category in categories:
        status = category["status"]
        css = {"已提供": "provided", "缺失": "missing", "需校验": "invalid"}[status]
        files = category["files"]
        size_text = "；".join("%s：%s（%s）" % (item["name"], human_size(item["byte_size"]),
                                              item["mtime"]) for item in files) or "—"
        doc_path = intake_root / category["dirname"] / "_放入说明.md"
        if doc_path.is_file():
            link_html = "<a href=\"%s\">放入说明</a>" % esc(rel_link(out_dir, doc_path))
        else:
            link_html = "—"
        parts.append("<tr><td>%s</td><td>%s</td><td>%s</td>"
                     "<td class=\"%s\">%s</td><td>%s</td><td>%s</td>"
                     "<td>%s</td></tr>\n"
                     % (esc(category["title"]), esc(category["dirname"]),
                        esc(category["expected"]), css, esc(status), esc(size_text),
                        esc(category["validator"]), link_html))
    parts.append("</tbody></table>\n")
    for category in categories:
        parts.append("<h2>%s</h2>\n<ul>\n" % esc(category["title"]))
        parts.append("<li>应放目录：%s</li>\n" % esc(category["dirname"]))
        parts.append("<li>状态：%s（%s）</li>\n" % (esc(category["status"]),
                                                  esc(category["detail"])))
        if category["files"]:
            parts.append("<li>已发现文件：</li>\n<ul>\n")
            for item in category["files"]:
                parts.append("<li>%s（大小 %s，%s）</li>\n"
                             % (esc(item["name"]), item["byte_size"], esc(item["mtime"])))
            parts.append("</ul>\n")
        parts.append("</ul>\n")
    parts.append("<p class=\"note\">收集完成后，运行校验命令；格式不符或缺失的数据整包退回，"
                 "不修数据、不补默认值。状态页只读展示，不构成审计结论。</p>\n")
    parts.append("<p class=\"note\">真实批准为空；真实初判未保存；开发宿主 0008；"
                 "下一步不自动推进；不启用 AI。</p>\n")
    parts.append("</body>\n</html>\n")
    return "".join(parts).encode("utf-8")


def human_size(value: int) -> str:
    if value >= 1024 * 1024:
        return "%.1f MB" % (value / 1024.0 / 1024.0)
    if value >= 1024:
        return "%.1f KB" % (value / 1024.0)
    return "%d B" % value


def esc(value) -> str:
    import html
    return html.escape("" if value is None else str(value), quote=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-058 数据投放指引与状态页")
    parser.add_argument("--intake-root", dest="intake_root", required=True)
    parser.add_argument("--out-dir", dest="out_dir", required=True)
    args = parser.parse_args(argv)
    intake_root = Path(args.intake_root)
    if not intake_root.is_absolute():
        intake_root = (Path.cwd() / intake_root).resolve()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (Path.cwd() / out_dir).resolve()
    try:
        if not intake_root.is_dir():
            raise IntakeError("usage", "intake-root 不存在：%s" % intake_root)
        try:
            out_dir.resolve().relative_to(TEST_ROOT.resolve())
        except ValueError:
            raise IntakeError("usage", "--out-dir 必须位于 %s 之下" % TEST_ROOT)
        if not out_dir.name.startswith(("task058_", "task058r1_")):
            raise IntakeError("usage", "--out-dir 目录名必须以 task058_ 或 task058r1_ 开头")
        if out_dir.exists():
            raise IntakeError("usage", "--out-dir 必须从未存在：%s" % out_dir)
        categories = []
        for category in CATEGORIES:
            directory = intake_root / category["dirname"]
            files = scan_dir(directory)
            try:
                status, detail = category["check"](directory, files)
            except Exception as exc:  # 兜底：结构/类型异常 → 需校验，不中断页面
                status, detail = STATUS_INVALID, "校验异常：%s" % type(exc).__name__
            categories.append({"id": category["id"], "title": category["title"],
                               "dirname": category["dirname"],
                               "expected": category["expected"],
                               "validator": category["validator"],
                               "status": status, "detail": detail, "files": files})
        out_dir.mkdir(parents=True, exist_ok=False)
        html_bytes = render_html(intake_root, categories, out_dir)
        (out_dir / "intake_status.html").write_bytes(html_bytes)
        manifest = {
            "intake_root": str(intake_root),
            "categories": categories,
            "generated_by": "scripts/build_intake_guide.py",
            "note": "只读扫描；状态为已提供/缺失/需校验；不复制、不移动、不修改 inbox。",
        }
        (out_dir / "intake_manifest.json").write_bytes(
            json.dumps(manifest, ensure_ascii=False, indent=2,
                       sort_keys=True).encode("utf-8") + b"\n")
        print(json.dumps({"status": "PASS", "out": str(out_dir),
                          "statuses": {item["id"]: item["status"]
                                       for item in categories}},
                         ensure_ascii=False))
        return 0
    except IntakeError as exc:
        print(json.dumps({"status": "ERROR", "kind": exc.kind, "error": str(exc)},
                         ensure_ascii=False))
        return 1 if exc.kind == "content" else 2


if __name__ == "__main__":
    raise SystemExit(main())
