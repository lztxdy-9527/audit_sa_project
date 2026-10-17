#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-053：修复下钻站点筛选/导出测试（语法、静态守卫、Node 伪 DOM 冒烟、回归）。

覆盖：全站 `<script>` 逐个 `node --check`；`lines.join('\\n')` 转义；状态/审阅选项与行类；
`.filter-bar` 页面有脚本、`.review` 页面有导出按钮、compare 页无死控件；Node 伪 DOM 冒烟
（状态下拉/关键词/审阅下拉/导出 JSON+CSV）；链接、语言、P02、确定性、规模、只读、负例。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
RUN_ROOT = TEST_ROOT / "task046_demo_01"
V1_NEG_RUN = TEST_ROOT / "task046_demo_v1_neg"
SCALE_RUN = TEST_ROOT / "task048_scale_run_task048_run_01"
TRACE_SCRIPT = ROOT / "scripts/build_trace_index.py"
SCRIPT = ROOT / "scripts/build_drilldown_site.py"
BANNED = ("JSON", "hash", "SHA", "API", "script", "pipeline", "解析",
          "字段类型", "字节", "编码", "版本号")
FORBIDDEN_SCRIPT_TOKENS = ("fetch(", "XMLHttpRequest", "eval(", "WebSocket",
                           "http://", "https://")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(args, log_dir, name):
    log_dir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with (log_dir / (name + "_stdout.txt")).open("wb") as out, \
            (log_dir / (name + "_stderr.txt")).open("wb") as err:
        code = subprocess.run(args, cwd=str(ROOT), stdout=out, stderr=err).returncode
    return code, round(time.monotonic() - start, 3)


def build_index(run_root, out_dir, log_dir, name):
    return run([sys.executable, "-B", str(TRACE_SCRIPT), "--run-root", str(run_root),
                "--out-dir", str(out_dir)], log_dir, name)


def build_site(index_path, out_dir, log_dir, name):
    return run([sys.executable, "-B", str(SCRIPT), "--index", str(index_path),
                "--out-dir", str(out_dir)], log_dir, name)


def node_check(site, work_dir):
    errors = []
    work_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(site.glob("*.html")):
        text = path.read_text("utf-8")
        for index, script in enumerate(re.findall(r"<script>(.*?)</script>", text, re.S)):
            script_path = work_dir / ("%s_%d.js" % (path.stem, index))
            script_path.write_text(script, "utf-8")
            result = subprocess.run(["node", "--check", str(script_path)],
                                    capture_output=True, text=True)
            if result.returncode != 0:
                errors.append({"page": path.name, "error": result.stderr[:300]})
    return errors


HARNESS = r'''const fs = require('fs');
const vm = require('vm');
const [pagePath, scriptPath] = process.argv.slice(2);
const html = fs.readFileSync(pagePath, 'utf8');
const script = fs.readFileSync(scriptPath, 'utf8');

function parse(htmlText) {
  const root = { tag: '#root', attrs: {}, children: [] };
  const stack = [root];
  let position = 0;
  const tagRe = /<(\/?)([a-zA-Z0-9]+)((?:\s+[^<>]*?)?)(\/?)>/g;
  let match;
  function addText(value) {
    if (value) { stack[stack.length - 1].children.push({ tag: '#text', text: value, attrs: {}, children: [] }); }
  }
  while ((match = tagRe.exec(htmlText))) {
    addText(htmlText.slice(position, match.index));
    position = match.index + match[0].length;
    const closing = match[1] === '/';
    const tag = match[2].toLowerCase();
    const attrs = {};
    const attrRe = /([a-zA-Z0-9_:-]+)(?:="([^"]*)")?/g;
    let attr;
    while ((attr = attrRe.exec(match[3] || ''))) {
      if (attr[1]) { attrs[attr[1]] = attr[2] === undefined ? '' : attr[2]; }
    }
    if (closing) {
      for (let k = stack.length - 1; k > 0; k -= 1) {
        if (stack[k].tag === tag) { stack.length = k; break; }
      }
      continue;
    }
    const node = { tag, attrs, children: [], parent: stack[stack.length - 1] };
    stack[stack.length - 1].children.push(node);
    if (!(match[4] === '/' || ['meta', 'link', 'br', 'img', 'input', 'hr'].includes(tag))) {
      stack.push(node);
    }
  }
  addText(htmlText.slice(position));
  return root;
}

function classes(node) { return (node.attrs.class || '').split(/\s+/).filter(Boolean); }
function text(node) { return node.tag === '#text' ? node.text : node.children.map(text).join(''); }
function walk(node, fn) { fn(node); for (const child of node.children) { walk(child, fn); } }
function all(node) { const out = []; walk(node, (item) => out.push(item)); return out; }
function matches(node, selector) {
  selector = selector.trim();
  if (!selector || node.tag === '#root') { return false; }
  const parts = selector.split('.');
  const tag = parts[0];
  if (tag && node.tag !== tag.toLowerCase()) { return false; }
  for (let index = 1; index < parts.length; index += 1) {
    if (!classes(node).includes(parts[index])) { return false; }
  }
  return true;
}
function queryAll(root, selector) {
  const out = [];
  for (const part of selector.split(',')) {
    const clean = part.trim();
    for (const node of all(root)) {
      if (matches(node, clean) && !out.includes(node)) { out.push(node); }
    }
  }
  return out;
}

const storage = new Map();
const downloads = [];
const blobContents = new Map();
let blobId = 0;
class BlobStub {
  constructor(parts, options) { this.parts = parts; this.type = (options || {}).type; }
}
const URLStub = {
  createObjectURL(blob) { blobId += 1; const id = 'blob:' + blobId; blobContents.set(id, blob); return id; },
  revokeObjectURL() {}
};

const root = parse(html);
for (const node of all(root)) {
  Object.defineProperty(node, 'className', {
    get() { return node.attrs.class || ''; },
    set(value) { node.attrs.class = value; }
  });
  Object.defineProperty(node, 'textContent', {
    get() { return text(node); }
  });
  node.classList = {
    add(name) { const list = classes(node); if (!list.includes(name)) { list.push(name); node.attrs.class = list.join(' '); } },
    remove(name) { node.attrs.class = classes(node).filter((item) => item !== name).join(' '); },
    contains(name) { return classes(node).includes(name); }
  };
  node.getAttribute = (key) => (node.attrs[key] === undefined ? null : node.attrs[key]);
  node.querySelector = (selector) => queryAll(node, selector)[0] || null;
  node.querySelectorAll = (selector) => queryAll(node, selector);
  node.addEventListener = function (type, fn) { this._listeners = this._listeners || {}; (this._listeners[type] = this._listeners[type] || []).push(fn); };
  node.dispatch = function (type) { for (const fn of ((this._listeners || {})[type] || [])) { fn({ type }); } };
  node.appendChild = function () {};
  node.removeChild = function () {};
  node.click = function () { node.dispatch('click'); };
  node.value = node.attrs.value || '';
}
const body = all(root).find((node) => node.tag === 'body');
const document = {
  body,
  querySelector: (selector) => queryAll(root, selector)[0] || null,
  querySelectorAll: (selector) => queryAll(root, selector),
  createElement(tag) {
    const node = {
      tag, attrs: {}, children: [], _listeners: {},
      click() {
        downloads.push({ download: this.download || '', content: blobContents.get(this.href) || null });
      },
      addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); }
    };
    return node;
  }
};
const sandbox = {
  document,
  window: { localStorage: { getItem: (key) => storage.get(key) || null, setItem: (key, value) => storage.set(key, String(value)) } },
  Blob: BlobStub, URL: URLStub, console
};
vm.runInNewContext(script, sandbox);

function visible(row) {
  const bodyClasses = (document.body.attrs.class || '').split(/\s+/);
  const filters = ['filter-abnormal', 'filter-ok', 'filter-neutral', 'filter-keyword',
                   'rvf-pending', 'rvf-match', 'rvf-mismatch', 'rvf-needmore'];
  const map = { 'filter-abnormal': 'abnormal', 'filter-ok': 'ok', 'filter-neutral': 'neutral',
                'filter-keyword': 'match', 'rvf-pending': 'rv-pending',
                'rvf-match': 'rv-match', 'rvf-mismatch': 'rv-mismatch',
                'rvf-needmore': 'rv-needmore' };
  for (const filter of filters) {
    if (bodyClasses.includes(filter) && !classes(row).includes(map[filter])) { return false; }
  }
  return true;
}

const checks = {};
const bar = document.querySelector('.filter-bar');
const rows = document.querySelectorAll('tr.row');
const reviewBlocks = document.querySelectorAll('.review');
const exportButtons = document.querySelectorAll('.export-review');
checks.source_version = (document.body.getAttribute('data-review-version') || '').length > 0;
checks.has_rows = rows.length > 0;
checks.export_buttons = exportButtons.length > 0 || reviewBlocks.length === 0;
if (bar) {
  const status = bar.querySelector('.filter-status');
  const review = bar.querySelector('.filter-review');
  const keyword = bar.querySelector('.filter-keyword');
  status.value = 'abnormal'; status.dispatch('change');
  checks.status_abnormal = (document.body.attrs.class || '').includes('filter-abnormal');
  if (rows.some((row) => classes(row).includes('abnormal'))) { checks.abnormal_visible = visible(rows.find((row) => classes(row).includes('abnormal'))); }
  if (rows.some((row) => classes(row).includes('ok'))) { checks.ok_hidden = visible(rows.find((row) => classes(row).includes('ok'))) === false; }
  status.value = 'ok'; status.dispatch('change');
  checks.status_ok = (document.body.attrs.class || '').includes('filter-ok');
  review.value = 'mismatch'; review.dispatch('change');
  checks.rvf_mismatch = (document.body.attrs.class || '').includes('rvf-mismatch');
  keyword.value = 'P01'; keyword.dispatch('input');
  checks.filter_keyword = (document.body.attrs.class || '').includes('filter-keyword');
  const matched = rows.filter((row) => classes(row).includes('match'));
  checks.keyword_matches = matched.length > 0;
  const unmatched = rows.find((row) => !classes(row).includes('match'));
  checks.keyword_hides = unmatched ? visible(unmatched) === false : true;
}
if (reviewBlocks.length) {
  const first = reviewBlocks[0];
  first.querySelector('.rv-status').value = '已审阅-相符';
  first.querySelector('.rv-issue').value = '冒烟问题';
  first.querySelector('.rv-reviewer').value = '审计员';
  first.querySelector('.rv-date').value = '2026-10-18';
  exportButtons[exportButtons.length - 1].click();
  checks.downloads = downloads.length;
  const jsonDownload = downloads.find((item) => item.download.indexOf('.json') >= 0);
  const csvDownload = downloads.find((item) => item.download.indexOf('.csv') >= 0);
  checks.json_export = !!(jsonDownload && jsonDownload.content && jsonDownload.content.parts);
  if (checks.json_export) {
    const parsed = JSON.parse(jsonDownload.content.parts[0]);
    checks.json_review_version = parsed.review_version === 'TASK-052-review-1.0';
    checks.json_source_version = typeof parsed.source_version === 'string' && parsed.source_version.length > 0;
    checks.json_records = Array.isArray(parsed.records) && parsed.records.length === reviewBlocks.length;
    checks.json_fields = parsed.records.every((record) =>
      typeof record.record_id === 'string' && typeof record.record_type === 'string'
      && typeof record.status === 'string');
  }
  checks.csv_export = !!(csvDownload && csvDownload.content && csvDownload.content.parts);
  if (checks.csv_export) {
    const lines = csvDownload.content.parts[0].split('\n');
    checks.csv_lines = lines.length === reviewBlocks.length + 1;
    checks.csv_quotes = lines[0].indexOf('record_id') === 0 && lines[1].charAt(0) === '"';
  }
}
process.stdout.write(JSON.stringify(checks) + '\n');
'''


def smoke(page, script_path, harness_path, work_dir):
    script_file = work_dir / "smoke_script.js"
    script_file.write_text(script_path.read_text("utf-8"), "utf-8")
    result = subprocess.run(["node", str(harness_path), str(page), str(script_file)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        return {"error": result.stderr[:500]}
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": "invalid smoke output", "raw": result.stdout[:300]}


def visible_text(path):
    text = Path(path).read_text("utf-8")
    text = re.sub(r"<script.*?</script>", "", text, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-053 站点筛选/导出修复测试")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    out_root = Path(args.out_dir)
    if not out_root.is_absolute():
        out_root = (Path.cwd() / out_root).resolve()
    if out_root.exists():
        print(json.dumps({"status": "FAIL", "reason": "out-dir 必须从未存在"}, ensure_ascii=False))
        return 1
    try:
        out_root.relative_to(TEST_ROOT.resolve())
    except ValueError:
        print(json.dumps({"status": "FAIL", "reason": "out-dir 必须位于测试根下"},
                         ensure_ascii=False))
        return 1
    if not out_root.name.startswith(("task049_", "task053_", "task054_", "task057_")):
        print(json.dumps({"status": "FAIL", "reason": "out-dir 前缀非法"}, ensure_ascii=False))
        return 1
    out_root.mkdir(parents=True)
    results = []

    def record(name, exit_code, checks, observed=None):
        passed = all(checks.values())
        results.append({"case": name, "exit_code": exit_code, "checks": checks,
                        "status": "PASS" if passed else "FAIL", "observed": observed or {}})
        return passed

    normal_index = out_root / "task051_index_normal"
    neg_index = out_root / "task051_index_v1neg"
    scale_index = out_root / "task051_index_scale"
    normal_code, normal_time = build_index(RUN_ROOT, normal_index, out_root / "normal_logs", "index")
    build_index(V1_NEG_RUN, neg_index, out_root / "neg_logs", "index")
    if SCALE_RUN.is_dir():
        build_index(SCALE_RUN, scale_index, out_root / "scale_logs", "index")
    site = out_root / "task053_site"
    neg_site = out_root / "task053_site_v1neg"
    scale_site = out_root / "task053_site_scale"
    site_code, site_time = build_site(normal_index / "trace_index.json", site,
                                      out_root / "site_logs", "site")
    build_site(neg_index / "trace_index.json", neg_site,
               out_root / "neg_site_logs", "site")
    scale_site_code, scale_time = build_site(scale_index / "trace_index.json", scale_site,
                                             out_root / "scale_site_logs", "site") \
        if SCALE_RUN.is_dir() else (1, 0)
    pages = sorted(path.name for path in site.glob("*.html")) if site.is_dir() else []
    scripts = {}
    for path in sorted(site.glob("*.html")):
        scripts[path.name] = re.findall(r"<script>(.*?)</script>",
                                        path.read_text("utf-8"), re.S)
    node_errors = node_check(site, out_root / "node_check_normal") if site.is_dir() else ["missing"]
    neg_errors = node_check(neg_site, out_root / "node_check_neg") if neg_site.is_dir() else ["missing"]
    checks = {
        "exit_0": site_code == 0 and normal_code == 0,
        "pages": len(pages) >= 30,
        "node_check_normal": not node_errors,
        "node_check_neg": not neg_errors,
        "join_escaped": any(re.search(r"lines\.join\('\\n'\)", value)
                            for found in scripts.values() for value in found),
        "no_real_newline_in_join": not any(re.search(r"lines\.join\('[\r\n]", value)
                                           for found in scripts.values() for value in found),
        "status_options": all(
            {"all", "abnormal", "ok", "neutral"} <= set(
                re.findall(r'<option value="(all|abnormal|ok|neutral)"',
                           (site / name).read_text("utf-8")))
            for name in pages if 'class="filter-status"' in (site / name).read_text("utf-8")),
        "no_review_in_status": not any('<option value="review">待审阅</option>'
                                       in (site / name).read_text("utf-8") for name in pages),
        "keyword_class": any("classes.push('filter-keyword')"
                             in (site / name).read_text("utf-8") for name in pages),
        "bar_pages_have_script": all(
            "<script>" in (site / name).read_text("utf-8")
            for name in pages if '<div class="filter-bar">' in (site / name).read_text("utf-8")),
        "review_pages_have_export": all(
            'class="export-review"' in (site / name).read_text("utf-8")
            for name in pages if '<div class="review"' in (site / name).read_text("utf-8")),
        "compare_no_dead_controls": all(
            '<div class="filter-bar">' not in (site / name).read_text("utf-8")
            and "<script>" not in (site / name).read_text("utf-8")
            for name in pages if name.startswith("compare-")),
        "script_guard": all(
            not any(token in value for token in FORBIDDEN_SCRIPT_TOKENS)
            for found in scripts.values() for value in found),
    }
    record("static_and_syntax", site_code, checks,
           {"pages": len(pages), "node_errors": node_errors[:3],
            "duration_seconds": site_time})

    harness_path = out_root / "smoke_harness.js"
    harness_path.write_text(HARNESS, "utf-8")
    work = out_root / "smoke_work"
    work.mkdir(parents=True, exist_ok=True)
    smoke_results = {}
    for label, page_name, page_site in (
            ("normal_list", "all-ledger.html", site),
            ("neg_list", "all-ledger.html", neg_site),
            ("case", "case-CASE-0001.html", site)):
        page_path = page_site / page_name
        found = re.findall(r"<script>(.*?)</script>", page_path.read_text("utf-8"), re.S)
        if not found:
            smoke_results[label] = {"error": "no script"}
            continue
        script_file = work / (label + ".js")
        script_file.write_text(found[0], "utf-8")
        smoke_results[label] = smoke(page_path, script_file, harness_path, work)
    checks = {
        "run_ok": all("error" not in smoke_results[key] for key in smoke_results),
        "normal_status": smoke_results.get("normal_list", {}).get("status_abnormal") is True,
        "normal_status_ok": smoke_results.get("normal_list", {}).get("status_ok") is True,
        "neg_abnormal_visible": smoke_results.get("neg_list", {}).get("abnormal_visible") is True,
        "neg_ok_hidden": smoke_results.get("neg_list", {}).get("ok_hidden") is not False,
        "keyword": smoke_results.get("normal_list", {}).get("filter_keyword") is True
        and smoke_results.get("normal_list", {}).get("keyword_matches") is True,
        "keyword_hides": smoke_results.get("normal_list", {}).get("keyword_hides") is not False,
        "review_filter": smoke_results.get("normal_list", {}).get("rvf_mismatch") is True,
        "export_json": smoke_results.get("case", {}).get("json_export") is True,
        "json_version": smoke_results.get("case", {}).get("json_review_version") is True,
        "json_source_version": smoke_results.get("case", {}).get("json_source_version") is True,
        "json_records": smoke_results.get("case", {}).get("json_records") is True,
        "json_fields": smoke_results.get("case", {}).get("json_fields") is True,
        "csv": smoke_results.get("case", {}).get("csv_export") is True
        and smoke_results.get("case", {}).get("csv_lines") is True,
    }
    record("node_smoke", 0, checks, smoke_results)

    bad_links = []
    for name in pages:
        text = (site / name).read_text("utf-8")
        for match in re.finditer(r'href="([^"]+)"', text):
            href = match.group(1)
            if href.startswith(("http:", "https:", "//")):
                bad_links.append((name, href))
            elif not (site / href).resolve().exists():
                bad_links.append((name, href))
    banned_hits = []
    for name in pages:
        text = visible_text(site / name)
        for word in BANNED:
            if word in text:
                banned_hits.append((name, word))
    record("regression", 0,
           {"links_ok": not bad_links, "banned_zero": not banned_hits,
            "p02_red": "未取得" in (neg_site / "case-CASE-0002.html").read_text("utf-8")},
           {"bad_links": bad_links[:3], "banned": banned_hits[:3]})

    det_site = out_root / "task053_site_det"
    det_code, _ = build_site(normal_index / "trace_index.json", det_site,
                             out_root / "det_logs", "site")
    names = sorted(path.name for path in det_site.glob("*.html")) if det_site.is_dir() else []
    same = names == pages and all((det_site / name).read_bytes() == (site / name).read_bytes()
                                  for name in names)
    scale_pages = len(list(scale_site.glob("*.html"))) if scale_site.is_dir() else 0
    record("determinism_scale", 0,
           {"det_exit_0": det_code == 0, "identical": same,
            "scale_exit_0": scale_site_code == 0 and scale_pages > 100},
           {"scale_pages": scale_pages, "scale_seconds": scale_time})

    # TASK-057：GL 借贷核对页（科目余额表/凭证/总账明细/账表/银行/核对结果）
    gl_root = ROOT / "data/evidence_inputs/gl_v1"
    gl_report = TEST_ROOT / "task056r1_gl_01/gl_reconcile_report.json"
    if gl_root.is_dir() and gl_report.is_file():
        gl_index = out_root / "task051_index_gl"
        build_index(RUN_ROOT, gl_index, out_root / "gl_index_logs") if False else None
        gl_code, _, _, _ = subprocess.run(
            [sys.executable, "-B", str(TRACE_SCRIPT), "--run-root", str(RUN_ROOT),
             "--out-dir", str(gl_index), "--gl-root", str(gl_root),
             "--gl-report", str(gl_report)], cwd=str(ROOT),
            capture_output=True, text=True).returncode, None, None, None
        gl_site = out_root / "task057_site_gl"
        gl_site_code, _, _, _ = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--index", str(gl_index / "trace_index.json"),
             "--out-dir", str(gl_site)], cwd=str(ROOT),
            capture_output=True, text=True).returncode, None, None, None
        gl_pages = ("gl-trial-balance.html", "gl-journal.html", "gl-ledger.html",
                    "gl-report.html", "gl-bank.html", "gl-checks.html")
        page_names = sorted(p.name for p in gl_site.glob("*.html")) if gl_site.is_dir() else []
        trial = (gl_site / "gl-trial-balance.html").read_text("utf-8") \
            if (gl_site / "gl-trial-balance.html").is_file() else ""
        checks_page = (gl_site / "gl-checks.html").read_text("utf-8") \
            if (gl_site / "gl-checks.html").is_file() else ""
        gl_errors = node_check(gl_site, out_root / "node_check_gl") if gl_site.is_dir() else ["missing"]
        gl_links = []
        for name in page_names:
            text = (gl_site / name).read_text("utf-8")
            for match in re.finditer(r'href="([^"]+)"', text):
                href = match.group(1)
                if not href.startswith(("http:", "https:", "//")) \
                        and not (gl_site / href).resolve().exists():
                    gl_links.append((name, href))
        checks = {
            "index_exit_0": gl_code == 0,
            "site_exit_0": gl_site_code == 0,
            "six_pages": all(name in page_names for name in gl_pages),
            "nav_every_page": all('href="gl-trial-balance.html"' in
                                  (gl_site / name).read_text("utf-8") for name in page_names),
            "numbers": all(token in trial for token in
                           ("16,000.00 元", "20,000.00 元", "4,000.00 元")),
            "checks_status": checks_page.count("MATCHED") == 7,
            "node_check": not gl_errors,
            "links_ok": not gl_links,
        }
        record("gl_site", gl_site_code, checks,
               {"pages": len(page_names), "node_errors": gl_errors[:2],
                "bad_links": gl_links[:3]})
    else:
        record("gl_site", 1, {"missing_inputs": False})

    # TASK-054：口径命名、图例、指引起页、业务勾稽底稿（管理口径）
    index_data = json.loads((normal_index / "trace_index.json").read_bytes())
    ap = next(row for row in index_data["ledger"] if row["ledger_type"] == "AP")
    fields = ap.get("fields") or {}
    payable = fields.get("payable_amount_cents")
    allocations = [row for row in index_data["ledger"]
                   if row["ledger_type"] == "ALLOCATION"
                   and (row.get("fields") or {}).get("ap_id") == fields.get("ap_id")]
    payment_ids = {(row.get("fields") or {}).get("payment_id") for row in allocations}
    rows_by_id = {row.get("ledger_id"): row for row in index_data["ledger"]}
    paid = sum((rows_by_id[pid].get("fields") or {}).get("amount_cents") or 0
               for pid in payment_ids
               if pid in rows_by_id and rows_by_id[pid].get("ledger_type") == "PAYMENT")
    refund = sum((rows_by_id[pid].get("fields") or {}).get("amount_cents") or 0
                 for pid in payment_ids
                 if pid in rows_by_id and rows_by_id[pid].get("ledger_type") == "REFUND")
    balance = paid - payable - refund
    business = site / ("business-%s.html" % ap["ledger_id"])
    business_text = business.read_text("utf-8") if business.is_file() else ""
    guide = site / "guide.html"
    guide_text = guide.read_text("utf-8") if guide.is_file() else ""
    def amount_text(cents):
        return "{:,.2f} 元".format(cents / 100.0)
    checks = {
        "business_page": business.is_file(),
        "guide_page": guide.is_file(),
        "guide_linked_everywhere": all('href="guide.html"' in (site / name).read_text("utf-8")
                                       for name in pages),
        "guide_content": all(token in guide_text for token in
                             ("业务链条", "对账路径", "三步走", "未纳入逐项核对",
                              "缺口声明", "试算平衡")),
        "naming": all(token in (site / "index.html").read_text("utf-8")
                      for token in ("机器核对结果（程序）", "人工审阅状态")) and \
        "人工审阅录入" in (site / "all-ledger.html").read_text("utf-8"),
        "legend_guard": "程序不会替人写" in (site / "index.html").read_text("utf-8"),
        "no_bare_not_involved": not any("未涉及" in visible_text(site / name) for name in pages),
        "management_decl": "管理口径的业务勾稽，不是会计分录" in business_text
        and "未做试算平衡" in business_text,
        "three_column": all(token in business_text for token in
                            ("应付确认", "贷方", amount_text(payable), amount_text(paid),
                             amount_text(refund), amount_text(abs(balance)),
                             "借方" if balance >= 0 else "贷方")),
        "detail_hint": "借方余额" in business_text and "重分类" in business_text,
        "sampling": all(token in business_text for token in
                        ("发票（应付单 %s）" % ap["ledger_id"],
                         "合同（应付单 %s）" % ap["ledger_id"],
                         "入库单（应付单 %s）" % ap["ledger_id"],
                         "审批单（付款 P01）", "回单（退款 R01）")),
        "gap": "有借必有贷" in business_text and "科目余额表" in business_text,
        "index_business_link": ("business-%s.html" % ap["ledger_id"])
        in (site / "index.html").read_text("utf-8"),
    }
    record("task054_content", 0, checks,
           {"payable": payable, "paid": paid, "refund": refund, "balance": balance})

    passed = sum(1 for item in results if item["status"] == "PASS")
    report = {
        "task": "TASK-053",
        "generated_by": "tests/test_drilldown_site.py",
        "site": site.relative_to(ROOT).as_posix(),
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": [item["case"] for item in results if item["status"] != "PASS"],
        "status": "PASS" if passed == len(results) else "FAIL",
        "cases": results,
        "note": ("全站脚本 node --check、静态守卫、Node 伪 DOM 冒烟（筛选/关键词/审阅/导出）"
                 "与回归均以真实 CLI/Node 执行。"),
        "boundaries": {"real_approval": None, "batch_approved": False,
                       "real_initial_judgment_saved": False, "next_step_allowed": False,
                       "ai_enabled": False, "identity_authenticated": False,
                       "audit_conclusion_formed": False},
    }
    report_path = out_root / "test_report.json"
    report_path.write_bytes(json.dumps(report, ensure_ascii=False, indent=2,
                                       sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({"status": report["status"], "cases": len(results),
                      "passed": passed, "report": str(report_path)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
