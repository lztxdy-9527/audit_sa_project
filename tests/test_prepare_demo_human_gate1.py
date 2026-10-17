# -*- coding: utf-8 -*-
"""TASK-023 测试与证据入口：Gate1 只读候审请求适配器。

运行：

    .venv\\Scripts\\python.exe -B tests\\test_prepare_demo_human_gate1.py \
        --out-dir data\\human_gate1_request_tests\\task023_<唯一名>

同轮批次根为 `data\\batches\\<同轮次名>\\`：用**冻结接收器 CLI** 在其中构造三个仅接收样本，
并放置负向/隔离副本。生产适配器不写任何文件；测试只写本轮的证据容器与批次根。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import traceback
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREPARE_PATH = PROJECT_ROOT / "scripts" / "prepare_demo_human_gate1.py"
RECEIVER_PATH = PROJECT_ROOT / "scripts" / "receive_demo_batch.py"
CHECKER_PATH = PROJECT_ROOT / "scripts" / "check_demo_data.py"
P1_PATH = PROJECT_ROOT / "scripts" / "build_demo_human_gate_decision.py"
CONFIG_PATH = PROJECT_ROOT / "config" / "human_flow_v1.json"
FIXTURE_XLSX = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a" / "fixtures" / "C06b.xlsx"
BATCH_ROOT = PROJECT_ROOT / "data" / "batches"
FIXTURE_TAG = "PROTOCOL_TEST_FIXTURE_ONLY"

PYTHON = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
if not Path(PYTHON).is_file():  # pragma: no cover - 回退到当前解释器
    PYTHON = sys.executable

PAYLOAD_FILES = (
    "helper_call_records.json","api_records.json", "p1_call_records.json", "sample_build_records.json",
                 "guard_records.json", "late_change_records.json", "isolation_self_tests.json",
                 "checks.json", "failures.json", "counts.json", "summary.json",
                 "prepare_registry.json", "observation_expectation_sha256.json")
LAYERED = ("evidence_ledger.json", "protection_result.json", "scan_protection.py",
           "final_audit_diagnostic.json")


# --------------------------------------------------------------------------- 独立基础
def canonical_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def fingerprint(obj) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(Path(path).read_bytes())


def deep(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- 守卫
class Guard:
    """观察真实 open/io.open/os.open/os.write/os.read/os.close，守卫网络/子进程/写文件。"""

    def __init__(self):
        self.log = []
        self.forbidden = []
        self.writes = []
        self._saved = {}

    def _wrap(self, module, name, label, access=None):
        original = getattr(module, name)

        def guarded(*args, **kwargs):
            mode = None
            for value in list(args) + list(kwargs.values()):
                if isinstance(value, str) and value and value[0] in "rwxa":
                    mode = value
                    break
            kind = access
            if kind is None and label in ("open", "io.open", "os.open"):
                kind = ("write" if mode and any(ch in mode for ch in "wxa")
                        else "read" if mode else "unknown")
            entry = {"op": label, "arg": str(args[0])[:300] if args else None, "mode": mode,
                     "access": kind}
            self.log.append(entry)
            if label in ("os.write", "os.open") and kind == "write":
                self.writes.append(entry)
            if label in ("os.open",) and mode is not None:
                pass
            return original(*args, **kwargs)

        self._saved[(module, name)] = original
        setattr(module, name, guarded)

    def _forbid(self, module, name, label):
        original = getattr(module, name)

        def guarded(*args, **kwargs):
            self.forbidden.append({"op": label})
            return original(*args, **kwargs)

        self._saved[(module, name)] = original
        setattr(module, name, guarded)

    def arm(self):
        import builtins
        self._wrap(builtins, "open", "open")
        self._wrap(io, "open", "io.open")
        self._wrap(os, "open", "os.open")
        self._wrap(os, "write", "os.write", access="write")
        self._wrap(os, "read", "os.read", access="read")
        self._wrap(os, "close", "os.close")
        self._forbid(socket, "socket", "socket.socket")
        self._forbid(subprocess, "Popen", "subprocess.Popen")

    def disarm(self):
        for (module, name), original in self._saved.items():
            setattr(module, name, original)
        self._saved = {}

    def reset(self):
        self.log = []
        self.forbidden = []
        self.writes = []


# --------------------------------------------------------------------------- 登记
def _exception_detail(exc):
    return {"type": type(exc).__name__,
            "field": getattr(exc, "field", None),
            "stage": getattr(exc, "stage", None),
            "reason": str(exc),
            "traceback": traceback.format_exc(),
            "cause_chain": _cause_chain(exc)}


def _cause_chain(exc):
    chain, current = [], exc
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append({"type": type(current).__name__, "reason": str(current)[:200]})
        current = current.__cause__ or current.__context__
    return chain


class PrepareRegistry:
    def __init__(self, module, guard):
        self.module = module
        self.guard = guard
        self.records = []

    def call(self, case_ids, batch_dir, request_id, *, scope="clean"):
        call_id = f"prepare-{len(self.records) + 1:03d}"
        before = _dir_snapshot(batch_dir)
        project_before = _project_snapshot()
        self.guard.reset()
        self.guard.arm()
        outcome = {"outcome": "unknown"}
        exception = None
        try:
            result = self.module.prepare_human_gate1_request(batch_dir, request_id)
            outcome = {"outcome": "prepared", "status": result.get("status"),
                       "keys": sorted(result.keys()),
                       "result": deep(result)}
        except self.module.HumanGate1RequestBlocked as exc:
            outcome = {"outcome": "blocked", "field": exc.field, "reason": exc.reason}
            exception = _exception_detail(exc)
        except self.module.HumanGate1RequestError as exc:
            outcome = {"outcome": "error", "stage": exc.stage, "reason": exc.reason}
            exception = _exception_detail(exc)
        except BaseException as exc:  # noqa: BLE001
            outcome = {"outcome": "unexpected", "type": type(exc).__name__, "reason": str(exc)}
            exception = _exception_detail(exc)
        finally:
            self.guard.disarm()
        after = _dir_snapshot(batch_dir)
        record = {"call_id": call_id, "case_ids": list(case_ids), "scope": scope,
                  "inputs": {"batch_dir": str(batch_dir), "request_id": request_id,
                             "request_id_verbatim": request_id,
                             "file_snapshot_before": before,
                             "project_snapshot_before": project_before,
                             "project_snapshot_after": _project_snapshot()},
                  "result": outcome, "exception": exception,
                  "file_snapshot_unchanged": before == after,
                  "project_files_unchanged": project_before == _project_snapshot(),
                  "scope": scope,
                  "guard": {"forbidden": list(self.guard.forbidden),
                            "write_ops": list(self.guard.writes),
                            "read_events": sum(1 for item in self.guard.log
                                               if item.get("access") == "read"),
                            "write_events": sum(1 for item in self.guard.log
                                                if item.get("access") == "write")},
                  "modules_after": sorted(name for name in sys.modules
                                          if name in FORBIDDEN_MODULES)}
        self.records.append(record)
        return record


# 只登记**下游业务核心**：冻结接收器仅为只读 validate_report 而加载，属本卡允许
FORBIDDEN_MODULES = ("normalize_demo_data", "screen_demo_sqlite", "build_demo_fact_packet",
                     "build_demo_initial_judgment", "store_demo_human_gate_decision",
                     "run_demo_workflow", "control_demo_workflow", "make_demo_data",
                     "export_demo_review_bundle", "receive_demo_batch")


def _project_snapshot():
    files = [PREPARE_PATH, CONFIG_PATH, RECEIVER_PATH, CHECKER_PATH, P1_PATH]
    return {str(path.relative_to(PROJECT_ROOT)): sha_file(path) for path in files}


# 合法接收批次的固定布局（E2：只按**已知八路径与有限目录项**检查，不做 rglob）
LEGAL_SNAPSHOT_LAYOUT = {
    "": ("batch_manifest.json", "checks", "code_snapshot", "gate1_packet.md", "logs", "source"),
    "checks": ("quality_report.json",),
    "code_snapshot": ("check_demo_data.py", "receive_demo_batch.py"),
    "logs": ("checker.stderr.txt", "checker.stdout.txt"),
    "source": ("input.xlsx",),
}
LEGAL_SNAPSHOT_FILES = ("batch_manifest.json", "gate1_packet.md", "source/input.xlsx",
                        "checks/quality_report.json", "logs/checker.stdout.txt",
                        "logs/checker.stderr.txt", "code_snapshot/receive_demo_batch.py",
                        "code_snapshot/check_demo_data.py")
SNAPSHOT_ENTRY_BUDGET = 24


def _dir_snapshot(root: Path):
    """**真正有界**的目录观察。

    - 只登记路径、存在性与**有限首层**观察（条目名，受 `SNAPSHOT_ENTRY_BUDGET` 约束）；
    - **绝不** `rglob`/递归哈希；对 `data/`、`data/batches/`、项目根或越界路径一律只做首层观察；
    - 仅当路径是**合法接收批次**（`data/batches` 严格后代 + 目录项集合恰为固定布局）时，
      按**已知八路径**逐文件记录字节/SHA（实际遍历条目 ≤ 固定布局条目数，受预算约束）。
    """
    snapshot = {}
    root = Path(root)
    snapshot["__path__"] = str(root)
    try:
        exists = root.exists()
        is_dir = root.is_dir()
    except OSError as exc:
        snapshot["__error__"] = f"{type(exc).__name__}: {exc}"
        return snapshot
    snapshot["__exists__"] = exists
    snapshot["__is_dir__"] = is_dir
    if not exists or not is_dir:
        snapshot["__mode__"] = "absent"
        return snapshot
    try:
        first = sorted(entry.name for entry in root.iterdir())
    except OSError as exc:
        snapshot["__error__"] = f"{type(exc).__name__}: {exc}"
        return snapshot
    snapshot["__top__"] = first[:SNAPSHOT_ENTRY_BUDGET]
    snapshot["__top_count__"] = len(first)
    legal = first == sorted(LEGAL_SNAPSHOT_LAYOUT[""])
    entries_seen = len(first)
    if legal:
        for sub_name, expected in LEGAL_SNAPSHOT_LAYOUT.items():
            if sub_name == "":
                continue
            try:
                actual = sorted(entry.name for entry in (root / sub_name).iterdir())
            except OSError as exc:
                snapshot["__error__"] = f"{type(exc).__name__}: {exc}"
                return snapshot
            entries_seen += len(actual)
            if actual != sorted(expected) or entries_seen > SNAPSHOT_ENTRY_BUDGET:
                legal = False
                break
    snapshot["__mode__"] = ("legal_batch_fixed_paths" if legal
                            else "bounded_first_level_only")
    snapshot["__entries_seen__"] = entries_seen
    snapshot["__recursive_hash_used__"] = False
    if not legal:
        return snapshot
    for relative in LEGAL_SNAPSHOT_FILES:
        target = root / relative
        data = target.read_bytes()
        snapshot[relative] = {"bytes": len(data), "sha256": sha_bytes(data)}
    return snapshot


# --------------------------------------------------------------------------- P1 观察
class HelperObserver:
    """观察适配器实际调用的冻结 `validate_report`：保存**完整真实输入快照/返回/异常**。"""

    def __init__(self):
        self.records = []
        self.original = None
        self.holder = None

    def install(self, module):
        self.holder = module
        self.original = getattr(module, "validate_report")
        observer = self

        def wrapper(report):
            entry = {"call_id": f"helper-{len(observer.records) + 1:03d}",
                     "function": "validate_report",
                     "input_type": type(report).__name__,
                     "inputs": {"report": deep(report)},
                     "inputs_fingerprint": {"report": fingerprint(report)}}
            try:
                result = observer.original(report)
            except BaseException as exc:  # noqa: BLE001
                entry.update({"outcome": "raised",
                              "result": None,
                              "result_fingerprint": None,
                              "exception": _exception_detail(exc),
                              "traceback": traceback.format_exc(),
                              "input_unchanged_after_call":
                                  fingerprint(report) == entry["inputs_fingerprint"]["report"]})
                observer.records.append(entry)
                raise
            entry.update({"outcome": "returned",
                          "result": deep(result),
                          "result_type": type(result).__name__,
                          "result_fingerprint": fingerprint(result),
                          "problems_count": len(result),
                          "input_unchanged_after_call":
                              fingerprint(report) == entry["inputs_fingerprint"]["report"]})
            observer.records.append(entry)
            return result

        module.validate_report = wrapper

    def uninstall(self):
        if self.holder is not None and self.original is not None:
            self.holder.validate_report = self.original

    def payload(self):
        return {"total": len(self.records), "records": deep(self.records),
                "source": "真实 validate_report 调用的完整输入/返回/异常观察（内存定稿后写入）"}


class P1Observer:
    def __init__(self, module):
        self.module = module
        self.original = module.build_human_gate_decision_record
        self.code = self.original.__code__
        self.records = []
        self.entry_count = 0
        self.extra_labels = {}
        self.extra_counts = {}

    def add_targets(self, targets):
        """注册额外真实入口目标（代码对象身份计数，不做路径解析、不改入参/返回）。"""
        for label, function in targets.items():
            code = function.__code__
            self.extra_labels[code] = label
            self.extra_counts[label] = 0

    def __call__(self, frame, event, arg):
        if event != "call":
            return
        if frame.f_code is self.code:
            self.entry_count += 1
            return
        label = self.extra_labels.get(frame.f_code)
        if label is not None:
            self.extra_counts[label] += 1

    def install(self):
        def wrapper(submission, materials, expectations, *, prior_history=None):
            entry = {"p1_call_id": f"p1-{len(self.records) + 1:03d}",
                     "inputs": {"submission": deep(submission), "materials": deep(materials),
                                "expectations": deep(expectations),
                                "prior_history": deep(prior_history)},
                     "input_fingerprints": {"submission": fingerprint(submission),
                                            "materials": fingerprint(materials),
                                            "expectations": fingerprint(expectations),
                                            "prior_history": fingerprint(prior_history)}}
            try:
                result = self.original(submission, materials, expectations,
                                       prior_history=prior_history)
            except BaseException as exc:  # noqa: BLE001
                entry.update({"outcome": "raised", "result": None,
                              "exception": _exception_detail(exc)})
                self.records.append(entry)
                raise
            entry.update({"outcome": "returned", "result": deep(result), "exception": None})
            self.records.append(entry)
            return result

        self.module.build_human_gate_decision_record = wrapper
        sys.setprofile(self)

    def uninstall(self):
        self.module.build_human_gate_decision_record = self.original
        sys.setprofile(None)


# --------------------------------------------------------------------------- 接收样本
def run_receiver(workbook: Path, out_dir: Path, description: str):
    argv = [PYTHON, "-B", str(RECEIVER_PATH), "--workbook", str(workbook),
            "--out-dir", str(out_dir), "--source-description", description]
    completed = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
    manifest_path = out_dir / "batch_manifest.json"
    manifest = (json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.is_file() else None)
    report_path = out_dir / "checks" / "quality_report.json"
    report = (json.loads(report_path.read_text(encoding="utf-8"))
              if report_path.is_file() else None)
    return {"argv": argv, "returncode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr,
            "out_dir": str(out_dir.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "batch_status": manifest.get("batch_status") if manifest else None,
            "receive_exit_code": manifest.get("receive_exit_code") if manifest else None,
            "checker_exit_code": (manifest.get("checker_invocation", {}).get("exit_code")
                                 if manifest else None),
            "report_result": report.get("result") if report else None,
            "issue_codes": sorted({item.get("code") for item in (report or {}).get("issues", [])}),
            "file_count": len(list(out_dir.rglob("*"))) if out_dir.is_dir() else 0}


def build_samples(round_root: Path, batch_root: Path):
    inputs = round_root / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    records = {}

    normal_xlsx = inputs / "C06b_normal.xlsx"
    shutil.copyfile(FIXTURE_XLSX, normal_xlsx)
    records["normal"] = run_receiver(
        normal_xlsx, batch_root / "C06b_normal",
        "TASK-023 测试样本（合成夹具 C06b 正常）：来源描述不构成业务范围确认")

    currency_xlsx = inputs / "C06b_currency_usd.xlsx"
    shutil.copyfile(FIXTURE_XLSX, currency_xlsx)
    from openpyxl import load_workbook
    workbook = load_workbook(currency_xlsx)
    sheet = workbook["payables"]
    header = [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
    column = header.index("currency") + 1
    sheet.cell(row=2, column=column).value = "USD"
    workbook.save(currency_xlsx)
    workbook.close()
    records["currency_usd"] = run_receiver(
        currency_xlsx, batch_root / "C06b_currency_usd",
        "TASK-023 测试样本（合成夹具 C06b，仅一个币种改为 USD）：来源描述不构成业务范围确认")

    no_alloc_xlsx = inputs / "C06b_no_allocations.xlsx"
    shutil.copyfile(FIXTURE_XLSX, no_alloc_xlsx)
    workbook = load_workbook(no_alloc_xlsx)
    del workbook["allocations"]
    workbook.save(no_alloc_xlsx)
    workbook.close()
    records["no_allocations"] = run_receiver(
        no_alloc_xlsx, batch_root / "C06b_no_allocations",
        "TASK-023 测试样本（合成夹具 C06b，仅删除 allocations 工作表）：来源描述不构成业务范围确认")

    late_xlsx = inputs / "C06b_late_change.xlsx"
    shutil.copyfile(FIXTURE_XLSX, late_xlsx)
    records["late_change"] = run_receiver(
        late_xlsx, batch_root / "late_change",
        "TASK-023 测试样本（合成夹具 C06b，用于真实源晚变更探针）：来源描述不构成业务范围确认")

    count_xlsx = inputs / "C06b_count_tamper.xlsx"
    shutil.copyfile(FIXTURE_XLSX, count_xlsx)
    records["count_tamper"] = run_receiver(
        count_xlsx, batch_root / "count_tamper",
        "TASK-023 测试样本（合成夹具 C06b，用于计数反例）：来源描述不构成业务范围确认")
    return records
    return records


# --------------------------------------------------------------------------- 断言
def check(checks, failures, name, condition, detail=""):
    ok = bool(condition)
    checks.append({"name": name, "ok": ok, "detail": detail})
    if not ok:
        failures.append({"name": name, "detail": detail})
    return ok


def _independent_files_expectation(result, batch_dir: Path):
    """测试侧独立复算 31 项材料字节与 SHA（不使用生产 helper）。"""
    expected = {}
    for item in result["materials"]["files"]:
        logical = item["relative"]
        if logical.startswith("batch/"):
            path = batch_dir / logical[len("batch/"):]
        else:
            path = PROJECT_ROOT / logical[len("project/"):]
        data = path.read_bytes()
        expected[logical] = {"file_sha256": sha_bytes(data), "byte_size": len(data)}
    return expected


# --------------------------------------------------------------------------- 主流程
def run_suite(out_dir: Path):
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"证据容器必须为新/空目录：{out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    round_name = out_dir.name
    batch_root = BATCH_ROOT / round_name
    batch_root.mkdir(parents=True, exist_ok=True)

    checks, failures = [], []
    prepare = load_module("prepare_demo_human_gate1", PREPARE_PATH)
    p1 = load_module("p1_core_for_task023", P1_PATH)
    observer = P1Observer(p1)
    observer.install()
    receiver_module = load_module("receive_demo_batch_frozen_for_task023", RECEIVER_PATH)
    helper_observer = HelperObserver()
    helper_observer.install(receiver_module)
    observer.add_targets({"prepare": prepare.prepare_human_gate1_request,
                          "helper": helper_observer.original})
    guard = Guard()
    registry = PrepareRegistry(prepare, guard)

    # ---------------------------------------------------------------- 样本构建
    samples = build_samples(out_dir, batch_root)
    for name, record in samples.items():
        check(checks, failures, f"S-{name} 冻结接收器真实运行并留下记录",
              record["returncode"] in (0, 1) and record["batch_status"] is not None,
              json.dumps({key: record[key] for key in ("returncode", "batch_status",
                                                       "checker_exit_code", "report_result",
                                                       "issue_codes")}, ensure_ascii=False))
    check(checks, failures, "S-normal 正常样本 READY（退出码 0/0、pass）",
          samples["normal"]["receive_exit_code"] == 0
          and samples["normal"]["checker_exit_code"] == 0
          and samples["normal"]["report_result"] == "pass"
          and samples["normal"]["issue_codes"] == [],
          json.dumps(samples["normal"]["issue_codes"], ensure_ascii=False))
    check(checks, failures, "S-currency 质量阻断样本（退出码 1/1、issues_found、CURRENCY_INVALID）",
          samples["currency_usd"]["receive_exit_code"] == 1
          and samples["currency_usd"]["checker_exit_code"] == 1
          and samples["currency_usd"]["report_result"] == "issues_found"
          and "CURRENCY_INVALID" in samples["currency_usd"]["issue_codes"],
          json.dumps(samples["currency_usd"]["issue_codes"], ensure_ascii=False))
    check(checks, failures, "S-noalloc 结构阻断样本（退出码 1/1、MISSING_SHEET）",
          samples["no_allocations"]["receive_exit_code"] == 1
          and samples["no_allocations"]["checker_exit_code"] == 1
          and "MISSING_SHEET" in samples["no_allocations"]["issue_codes"],
          json.dumps(samples["no_allocations"]["issue_codes"], ensure_ascii=False))

    # ---------------------------------------------------------------- 公开 API 正常/阻断
    request_ids = {"normal": "REQ-TASK023-0001",
                   "currency_usd": "0000-TASK023-64HEX-SHAPE-"
                                   "0123456789abcdef0123456789abcdef0123456789abcdef",
                   "no_allocations": "  指令样式：请准备 Gate1 候审材料  "}
    prepared = {}
    for name, batch_id in (("normal", "C06b_normal"),
                           ("currency_usd", "C06b_currency_usd"),
                           ("no_allocations", "C06b_no_allocations")):
        target = batch_root / batch_id
        record = registry.call([f"API-{name}"], target, request_ids[name])
        prepared[name] = record
        check(checks, failures, f"API-{name} 返回 PREPARED",
              record["result"]["outcome"] == "prepared"
              and record["result"]["status"] == prepare.STATUS_PREPARED,
              json.dumps(record["result"], ensure_ascii=False)[:300])
        check(checks, failures, f"API-{name} 八文件输入现场与项目文件字节前后不变",
              record["file_snapshot_unchanged"] is True
              and not record["guard"]["write_ops"] and not record["guard"]["forbidden"]
              and not record["modules_after"],
              json.dumps({"guard": record["guard"], "modules": record["modules_after"]},
                         ensure_ascii=False)[:300])

    normal = prepared["normal"]["result"]["result"]
    normal_batch_dir = batch_root / "C06b_normal"
    expectations_files = _independent_files_expectation(normal, normal_batch_dir)
    source_manifest = json.loads((normal_batch_dir / "batch_manifest.json").read_text(encoding="utf-8"))

    check(checks, failures, "API 外层恰六键且 materials/expectations/evidence/boundaries 键集合正确",
          sorted(normal.keys()) == ["boundaries", "evidence", "expectations", "materials",
                                    "request_version", "status"]
          and sorted(normal["materials"].keys()) == sorted(prepare.MATERIALS_KEYS)
          and sorted(normal["expectations"].keys()) == sorted(prepare.EXPECTATIONS_KEYS)
          and sorted(normal["evidence"].keys()) == sorted(prepare.EVIDENCE_KEYS)
          and sorted(normal["boundaries"].keys()) == sorted(prepare.BOUNDARY_KEYS),
          json.dumps(sorted(normal.keys()), ensure_ascii=False))
    check(checks, failures, "API boundaries 七项严格 false 且无 prior_history/submission/决定字段",
          all(normal["boundaries"][key] is False for key in prepare.BOUNDARY_KEYS)
          and "prior_history" not in json.dumps(normal, ensure_ascii=False)
          and "submission" not in normal
          and not any(key in normal for key in ("decision", "decision_source", "event_id")),
          json.dumps(normal["boundaries"], ensure_ascii=False))
    check(checks, failures, "API materials.files 恰 31 项且字节/SHA 与磁盘独立复算全等",
          len(normal["materials"]["files"]) == 31
          and all(item["relative"] in expectations_files
                  and item["file_sha256"] == expectations_files[item["relative"]]["file_sha256"]
                  and item["byte_size"] == expectations_files[item["relative"]]["byte_size"]
                  for item in normal["materials"]["files"])
          and len(expectations_files) == 31,
          f"files={len(normal['materials']['files'])} independent={len(expectations_files)}")
    check(checks, failures, "API materials_fingerprint 独立 canonical 复算一致",
          normal["materials"]["materials_fingerprint"]
          == fingerprint({key: value for key, value in normal["materials"].items()
                          if key != "materials_fingerprint"}),
          normal["materials"]["materials_fingerprint"])
    check(checks, failures, "API expectations 独立构造（request_id 原样、prior=null、期望名单一致）",
          normal["expectations"]["expected_request_id"] == request_ids["normal"]
          and normal["expectations"]["expected_prior_gate1"] is None
          and normal["expectations"]["expected_materials_fingerprint"]
          == normal["materials"]["materials_fingerprint"]
          and normal["expectations"]["expected_files"]
          == {item["relative"]: item["file_sha256"] for item in normal["materials"]["files"]},
          json.dumps(normal["expectations"]["expected_request_id"], ensure_ascii=False))
    check(checks, failures, "API 质量 OK 映射（三列表全空）",
          normal["materials"]["quality"] == {"status": "OK", "structural_blockers": [],
                                             "quality_blockers": [],
                                             "verification_failures": []},
          json.dumps(normal["materials"]["quality"], ensure_ascii=False)[:200])
    check(checks, failures, "API evidence 前五项来自同缓冲已核验 manifest（原文保留）",
          normal["evidence"]["source_manifest_version"]
          == source_manifest["manifest_version"]
          and normal["evidence"]["source_batch_status"] == source_manifest["batch_status"]
          and normal["evidence"]["source_receive_exit_code"]
          == source_manifest["receive_exit_code"]
          and normal["evidence"]["source_description"]
          == source_manifest["source"]["source_description"]
          and normal["evidence"]["source_scope"] == source_manifest["expected_scope"],
          json.dumps(normal["evidence"]["source_manifest_version"], ensure_ascii=False))

    for name, code_list in (("currency_usd", "quality_blockers"),
                            ("no_allocations", "structural_blockers")):
        quality = prepared[name]["result"]["result"]["materials"]["quality"]
        check(checks, failures, f"API-{name} BLOCKED 映射（{code_list}）",
              quality["status"] == "BLOCKED"
              and quality["verification_failures"] == []
              and quality[code_list]
              and all(isinstance(item, str) and item.startswith("issues[")
                      for item in quality["structural_blockers"] + quality["quality_blockers"]),
              json.dumps(quality, ensure_ascii=False)[:300])
    check(checks, failures, "API-noalloc MISSING_SHEET 进入 structural_blockers",
          any("MISSING_SHEET" in item for item in
              prepared["no_allocations"]["result"]["result"]["materials"]["quality"]
              ["structural_blockers"]),
          json.dumps(prepared["no_allocations"]["result"]["result"]["materials"]["quality"]
                     ["structural_blockers"], ensure_ascii=False)[:200])
    check(checks, failures, "API-currency CURRENCY_INVALID 进入 quality_blockers",
          any("CURRENCY_INVALID" in item for item in
              prepared["currency_usd"]["result"]["result"]["materials"]["quality"]
              ["quality_blockers"]),
          json.dumps(prepared["currency_usd"]["result"]["result"]["materials"]["quality"]
                     ["quality_blockers"], ensure_ascii=False)[:200])
    check(checks, failures, "API request_id 原样保存（含前导零/64hex 形状/指令样式文本）",
          prepared["currency_usd"]["result"]["result"]["expectations"]["expected_request_id"]
          == request_ids["currency_usd"]
          and prepared["no_allocations"]["result"]["result"]["expectations"]
          ["expected_request_id"] == request_ids["no_allocations"],
          "request_id 被改写")

    # 确定性与无别名
    repeat = registry.call(["API-normal-repeat"], batch_root / "C06b_normal", request_ids["normal"])
    check(checks, failures, "API 相同输入重复调用完整规范相等",
          canonical_bytes(repeat["result"]["result"]) == canonical_bytes(
              prepared["normal"]["result"]["result"]),
          "重复调用结果规范字节不一致")
    mutated = repeat["result"]["result"]
    mutated["materials"]["quality"]["status"] = "OK-MUTATED"
    mutated["boundaries"]["execution_allowed"] = True
    third = registry.call(["API-normal-third"], batch_root / "C06b_normal", request_ids["normal"])
    check(checks, failures, "API 返回深拷贝无别名（改返回不影响后续调用）",
          third["result"]["result"]["boundaries"]["execution_allowed"] is False
          and third["result"]["result"]["materials"]["quality"]["status"] == "OK",
          json.dumps(third["result"]["result"]["materials"]["quality"], ensure_ascii=False)[:200])

    # ---------------------------------------------------------------- P1 兼容性（测试直接调用）
    def build_submission(materials, expectations, request_id, decision):
        return {
            "submission_version": p1.SUBMISSION_VERSION,
            "event_id": "FIXTURE-EV-TASK023-0001",
            "batch_id": materials["batch_id"],
            "gate": "GATE1",
            "request_binding": {"request_id": request_id,
                                "materials_binding": materials["materials_fingerprint"]},
            "decision": decision,
            "decision_source": p1.DECISION_SOURCE_HUMAN,
            "actor": {"actor_kind": p1.ACTOR_KIND_HUMAN, "actor_id": "fixture-actor-0001",
                      "declaration_note": f"{FIXTURE_TAG} 合成测试身份声明（非人类真实提交）"},
            "decided_at_raw": "2026-10-14T10:00:00+08:00",
            "reason": f"{FIXTURE_TAG} 合成夹具：仅用于兼容性与协议校验，不具备任何批准效力",
            "prior_decision_binding": None,
        }

    def p1_call(case_ids, submission, materials, expectations, prior_history):
        entry = {"case_ids": list(case_ids)}
        try:
            result = p1.build_human_gate_decision_record(submission, materials, expectations,
                                                         prior_history=prior_history)
            entry.update({"outcome": "returned",
                          "record_status": result["record"]["record_status"],
                          "record_gate": result["record"]["gate"],
                          "record_decision": result["record"]["decision"],
                          "record_keys": sorted(result["record"].keys()),
                          "boundaries": deep(result["record"]["boundaries"]),
                          "quality_summary": deep(result["record"]["quality_summary"]),
                          "record_fingerprint": result["record_fingerprint"]})
        except p1.HumanGateDecisionBlocked as exc:
            entry.update({"outcome": "blocked", "field": exc.field, "reason": exc.reason})
        except p1.HumanGateDecisionError as exc:  # pragma: no cover
            entry.update({"outcome": "error", "stage": exc.stage, "reason": exc.reason})
        p1_records.append(entry)
        return entry

    p1_records = []
    history = {"declared_complete": True, "declared_scope": "FIXTURE-SCOPE-TASK023",
               "records": []}
    normal_materials = deep(prepared["normal"]["result"]["result"]["materials"])
    normal_expectations = deep(prepared["normal"]["result"]["result"]["expectations"])
    guard.reset()
    guard.arm()
    try:
        p1_call(["P1-normal-hold"], build_submission(normal_materials, normal_expectations,
                                                     request_ids["normal"], "HOLD"),
                normal_materials, normal_expectations, history)
        blocked_materials = deep(prepared["no_allocations"]["result"]["result"]["materials"])
        blocked_expectations = deep(
            prepared["no_allocations"]["result"]["result"]["expectations"])
        p1_call(["P1-blocked-hold"], build_submission(blocked_materials, blocked_expectations,
                                                      request_ids["no_allocations"], "HOLD"),
                blocked_materials, blocked_expectations, history)
        p1_call(["P1-blocked-approve"], build_submission(blocked_materials, blocked_expectations,
                                                         request_ids["no_allocations"],
                                                         "APPROVE"),
                blocked_materials, blocked_expectations, history)
    finally:
        p1_guard = {"write_ops": len(guard.writes), "forbidden": len(guard.forbidden),
                    "read_events": sum(1 for item in guard.log if item.get("access") == "read")}
        guard.disarm()
    check(checks, failures, "P1 兼容：正常材料 HOLD 由真实冻结 P1 VALIDATED",
          p1_records[0].get("outcome") == "returned"
          and p1_records[0].get("record_status") == "HUMAN_GATE_DECISION_MEMORY_VALIDATED"
          and p1_records[0].get("record_gate") == "GATE1",
          json.dumps(p1_records[0], ensure_ascii=False)[:300])
    check(checks, failures, "P1 兼容：BLOCKED 材料 HOLD 由真实冻结 P1 VALIDATED",
          p1_records[1].get("outcome") == "returned"
          and p1_records[1].get("quality_summary", {}).get("status") == "BLOCKED",
          json.dumps(p1_records[1], ensure_ascii=False)[:300])
    check(checks, failures, "P1 兼容：BLOCKED 材料 APPROVE 被真实冻结 P1 拒绝",
          p1_records[2].get("outcome") == "blocked"
          and p1_records[2].get("field") == "submission.decision",
          json.dumps(p1_records[2], ensure_ascii=False)[:300])
    check(checks, failures, "P1 调用与入口代码帧观察闭合、只读且不写文件",
          observer.entry_count == len(p1_records) == 3
          and p1_guard["write_ops"] == 0 and p1_guard["forbidden"] == 0,
          f"entry={observer.entry_count} records={len(p1_records)} guard={p1_guard}")
    check(checks, failures, "P1 记录 boundaries 原样不放行（execution_allowed 严格 false）",
          all(record.get("outcome") != "returned"
              or (record["boundaries"] == {"persisted": False, "approved_for_execution": False,
                                           "human_initial_judgment_saved": False,
                                           "ai_enabled": False,
                                           "identity_authentication": False,
                                           "source_authenticity_proven": False})
              for record in p1_records),
          json.dumps([record.get("boundaries") for record in p1_records],
                     ensure_ascii=False)[:250])

    # ---------------------------------------------------------------- 负向
    negatives = []

    def expect_negative(case_id, batch_dir, request_id, expect_field):
        record = registry.call([case_id], batch_dir, request_id)
        field = record["result"].get("field") or ""
        ok = (record["result"]["outcome"] in ("blocked", "error")
              and (expect_field in field or expect_field in
                   (record["exception"] or {}).get("reason", "")))
        negatives.append((case_id, record["result"], field))
        check(checks, failures, f"N-{case_id} 定点拒绝", ok,
              json.dumps(record["result"], ensure_ascii=False)[:300])
        return record

    expect_negative("N01-越界", PROJECT_ROOT / "data", request_ids["normal"], "batch_dir")
    expect_negative("N02-允许根自身", BATCH_ROOT, request_ids["normal"], "batch_dir")

    def copy_sample(name):
        """负向副本：保持叶目录名与 manifest.batch_id 一致，避免 batch_id 不匹配遮蔽目标检查。"""
        parent = batch_root / name
        target = parent / "C06b_normal"
        shutil.copytree(batch_root / "C06b_normal", target)
        return target

    workflow_dir = copy_sample("neg_workflow_products")
    (workflow_dir / "normalized").mkdir()
    (workflow_dir / "normalized" / "normalized.json").write_text("{}\n", encoding="utf-8")
    expect_negative("N03-含下游产物目录", workflow_dir, request_ids["normal"], "batch_dir")

    missing_dir = copy_sample("neg_missing_file")
    (missing_dir / "gate1_packet.md").unlink()
    expect_negative("N04-缺必需文件", missing_dir, request_ids["normal"], "batch_dir")

    object_dir = copy_sample("neg_non_object_json")
    (object_dir / "batch_manifest.json").write_text("[]\n", encoding="utf-8")
    expect_negative("N05-非对象 JSON", object_dir, request_ids["normal"], "batch_manifest.json")

    hash_dir = copy_sample("neg_tampered_packet")
    with (hash_dir / "gate1_packet.md").open("ab") as handle:
        handle.write(b"\n")
    expect_negative("N06-声明 SHA 与实际不符", hash_dir, request_ids["normal"],
                    "batch_manifest.json.gate1_packet.sha256")

    bool_dir = copy_sample("neg_bool_not_strict")
    manifest = json.loads((bool_dir / "batch_manifest.json").read_text(encoding="utf-8"))
    manifest["hashes"]["snapshot_written"] = 1
    (bool_dir / "batch_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    expect_negative("N07-严格布尔", bool_dir, request_ids["normal"],
                    "hashes.snapshot_written")

    count_dir = batch_root / "count_tamper"
    report = json.loads((count_dir / "checks" / "quality_report.json").read_text(encoding="utf-8"))
    report["issue_counts_by_code"] = {"FAKE": 1}
    report_path = count_dir / "checks" / "quality_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    count_manifest_path = count_dir / "batch_manifest.json"
    count_manifest = json.loads(count_manifest_path.read_text(encoding="utf-8"))
    count_manifest["checker_invocation"]["report"]["sha256"] = sha_file(report_path)
    count_manifest_path.write_text(json.dumps(count_manifest, ensure_ascii=False, indent=2)
                                   + "\n", encoding="utf-8")
    expect_negative("N08-计数与实际不符", count_dir, request_ids["normal"],
                    "checks/quality_report.json.issue_counts_by_code")

    snapshot_dir = copy_sample("neg_code_snapshot")
    with (snapshot_dir / "code_snapshot" / "check_demo_data.py").open("ab") as handle:
        handle.write(b"\n")
    expect_negative("N09-代码快照声明 SHA 与实际不符", snapshot_dir, request_ids["normal"],
                    "batch_manifest.json.code_snapshot.check_demo_data.py.sha256")

    expect_negative("N10-request_id 空白", batch_root / "C06b_normal", "   ",
                    "request_id")
    expect_negative("N11-request_id 非字符串", batch_root / "C06b_normal", 12345,
                    "request_id")

    junction = {"attempted": True}
    alias = batch_root / "neg_junction_alias"
    target_dir = batch_root / "C06b_normal"
    completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(target_dir)],
                               capture_output=True, text=True)
    created = alias.exists() and os.path.islink(str(alias)) is False
    junction.update({"returncode": completed.returncode, "stdout": completed.stdout.strip(),
                     "created": bool(created), "executed": bool(created)})
    if created:
        record = registry.call(["N12-真实junction"], alias, request_ids["normal"])
        junction["field"] = record["result"].get("field")
        junction["reason"] = record["result"].get("reason")
        check(checks, failures, "N12-真实 junction 拒绝",
              record["result"]["outcome"] == "blocked"
              and record["result"].get("field") == "batch_dir",
              json.dumps(record["result"], ensure_ascii=False)[:200])
    else:
        junction["executed"] = False
        junction["note"] = "执行环境未允许建立 junction，如实报告未执行"

    # ---------------------------------------------------------------- R1 定点反例（B1）
    def candidate_json(payload):
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"

    def controlled(mapping):
        """受控读缓冲映射：仅替换指定 label 的读缓冲，其余仍走真实读取通道。"""
        original = prepare._read_bytes

        def wrapper(path, stage, label):
            if label in mapping:
                return mapping[label]
            return original(path, stage, label)

        prepare._read_bytes = wrapper
        try:
            return registry.call([f"map:{sorted(mapping)[0]}"], batch_root / "C06b_normal",
                                 request_ids["normal"])
        finally:
            prepare._read_bytes = original

    def manifest_candidate(mutate):
        payload = json.loads((batch_root / "C06b_normal" / "batch_manifest.json")
                             .read_text(encoding="utf-8"))
        mutate(payload)
        return candidate_json(payload)

    b1_cases = []
    b1_cases.append(("B1-end-sha", {"batch_manifest.json": manifest_candidate(
        lambda m: m["hashes"]["receive_script"].__setitem__("sha256_at_end", "0" * 64))},
        "hashes.receive_script.sha256_at_end"))
    b1_cases.append(("B1-checker-stable", {"batch_manifest.json": manifest_candidate(
        lambda m: m["hashes"]["checker"].__setitem__("stable_during_run", False))},
        "hashes.checker.stable_during_run"))
    b1_cases.append(("B1-report-result", {"batch_manifest.json": manifest_candidate(
        lambda m: m["checker_invocation"].__setitem__("report_result", "issues_found"))},
        "quality_report.json.result"))
    b1_cases.append(("B1-report-checker-sha", {"batch_manifest.json": manifest_candidate(
        lambda m: m["checker_invocation"].__setitem__("report_checker_sha256", "0" * 64))},
        "checker_invocation.report_checker_sha256"))
    b1_cases.append(("B1-missing-approval", {"batch_manifest.json": manifest_candidate(
        lambda m: m.pop("gate1_approval"))}, "gate1_approval"))
    b1_cases.append(("B1-missing-read-error", {"batch_manifest.json": manifest_candidate(
        lambda m: m["checker_invocation"]["report"].pop("read_error"))},
        "report.read_error"))

    def with_lf(relative):
        return {relative: (PROJECT_ROOT / relative).read_bytes() + b"\n"}

    b1_cases.append(("B1-spec-bytes", with_lf("docs/SPEC_V1.md"), "docs/SPEC_V1.md"))
    b1_cases.append(("B1-draft-bytes", with_lf("docs/AUDIT_CONTRACT_DRAFT.md"),
                     "docs/AUDIT_CONTRACT_DRAFT.md"))
    b1_cases.append(("B1-schema-bytes", with_lf("sql/demo_schema.sql"), "sql/demo_schema.sql"))
    bad_config = {"company": "澄明商贸有限公司",
                  "config_version": "TASK-023-synthetic-human-flow-config-1.0",
                  "currency": "CNY", "cutoff_date": "2026-09-30", "period_end": "2026-09-30",
                  "period_start": "2026-09-01", "synthetic_data": 1}
    b1_cases.append(("B1-config-strict-bool", {"config/human_flow_v1.json":
                                               canonical_bytes(bad_config) + b"\n"},
                     "config/human_flow_v1.json.synthetic_data"))

    for case_id, mapping, expected_field in b1_cases:
        record = controlled(mapping)
        field = record["result"].get("field") or ""
        located = (record["result"]["outcome"] in ("blocked", "error")
                   and expected_field in field)
        negatives.append((case_id, record["result"], field))
        check(checks, failures, f"{case_id} 公开 API 定位拒绝", located,
              json.dumps(record["result"], ensure_ascii=False)[:250])

    # ---------------------------------------------------------------- R1 定点反例（B2）
    junction_sub = {"attempted": True}
    sub_sample = f"junction_subdir_{round_name}"[:60]
    sub_xlsx = out_dir / "inputs" / "C06b_junction_subdir.xlsx"
    shutil.copyfile(FIXTURE_XLSX, sub_xlsx)
    sub_record = run_receiver(sub_xlsx, batch_root / sub_sample,
                              "TASK-023-R1 子目录 junction 反例样本（合成夹具 C06b）")
    samples["junction_subdir"] = sub_record
    sub_batch = batch_root / sub_sample
    normal_control = registry.call(["B2-subdir-normal-control"], sub_batch,
                                   request_ids["normal"])
    check(checks, failures, "B2 子目录 junction 前正常对照 PREPARED",
          normal_control["result"]["outcome"] == "prepared",
          json.dumps(normal_control["result"], ensure_ascii=False)[:250])
    moved_checks = batch_root / f"moved_checks_{round_name}"[:60]
    shutil.move(str(sub_batch / "checks"), str(moved_checks))
    completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(sub_batch / "checks"),
                                str(moved_checks)], capture_output=True, text=True)
    sub_reparse = os.path.islink(str(sub_batch / "checks")) is False and (
        os.lstat(sub_batch / "checks").st_file_attributes & 0x400) != 0
    junction_sub.update({"returncode": completed.returncode,
                         "stdout": completed.stdout.strip(),
                         "created": bool(sub_batch.joinpath("checks").exists() and sub_reparse),
                         "executed": bool(sub_reparse)})
    if junction_sub["executed"]:
        source_before = _dir_snapshot(sub_batch)
        target_before = {"checks/quality_report.json":
                         sha_file(moved_checks / "quality_report.json")}
        record = registry.call(["B2-subdir-junction"], sub_batch, request_ids["normal"])
        junction_sub["field"] = record["result"].get("field")
        junction_sub["reason"] = record["result"].get("reason")
        junction_sub["source_unchanged"] = (source_before == _dir_snapshot(sub_batch))
        junction_sub["target_unchanged"] = (
            target_before["checks/quality_report.json"]
            == sha_file(moved_checks / "quality_report.json"))
        negatives.append(("B2-subdir-junction", record["result"],
                          record["result"].get("field") or ""))
        check(checks, failures, "B2 真实子目录 junction 被拒且指向路径",
              record["result"]["outcome"] == "blocked"
              and "batch_dir.checks" in (record["result"].get("field") or "")
              and junction_sub["source_unchanged"] and junction_sub["target_unchanged"],
              json.dumps({"result": record["result"], "junction": junction_sub},
                         ensure_ascii=False)[:300])
    else:
        junction_sub["note"] = "执行环境未允许建立子目录 junction，如实报告未执行"

    original_lstat = os.lstat
    lstat_state = {"hits": 0}

    def lstat_raising(path):
        if lstat_state["hits"] == 0:
            lstat_state["hits"] += 1
            raise OSError("injected lstat failure")
        return original_lstat(path)

    os.lstat = lstat_raising
    try:
        lstat_record = registry.call(["B2-lstat-oserror"], batch_root / "C06b_normal",
                                     request_ids["normal"])
    finally:
        os.lstat = original_lstat
    negatives.append(("B2-lstat-oserror", lstat_record["result"],
                      lstat_record["result"].get("stage") or ""))
    check(checks, failures, "B2 受控 lstat OSError → Error(lstat)+原因链（映射注入）",
          lstat_record["result"]["outcome"] == "error"
          and lstat_record["result"].get("stage") == "lstat"
          and lstat_state["hits"] == 1
          and any("OSError" in item["type"]
                  for item in (lstat_record["exception"] or {}).get("cause_chain", [])),
          json.dumps(lstat_record["result"], ensure_ascii=False)[:250])

    # ---------------------------------------------------------------- R1 定点反例（B3）
    legal_name = "decision_review"
    legal_xlsx = out_dir / "inputs" / "C06b_decision_review.xlsx"
    shutil.copyfile(FIXTURE_XLSX, legal_xlsx)
    samples["decision_review"] = run_receiver(
        legal_xlsx, batch_root / legal_name,
        "TASK-023-R1 合法批次名样本 decision_review（合成夹具 C06b）")
    legal_request = "REVIEW\nREQ-001"
    legal = registry.call(["B3-legal-name-and-id"], batch_root / legal_name, legal_request)
    check(checks, failures, "B3 合法批次名 decision_review 通过并精确绑定",
          legal["result"]["outcome"] == "prepared"
          and legal["result"]["result"]["materials"]["batch_id"] == legal_name
          and legal["result"]["result"]["expectations"]["expected_request_id"] == legal_request,
          json.dumps(legal["result"], ensure_ascii=False)[:250])
    tab_request = "\tREQ-002"
    tab = registry.call(["B3-tab-id"], batch_root / legal_name, tab_request)
    check(checks, failures, "B3 含内嵌 LF/首尾 tab 的普通 ID 原样通过",
          tab["result"]["outcome"] == "prepared"
          and tab["result"]["result"]["expectations"]["expected_request_id"] == tab_request,
          json.dumps(tab["result"], ensure_ascii=False)[:250])

    # ---------------------------------------------------------------- R1 定点对照（E2）
    data_snapshot = _dir_snapshot(PROJECT_ROOT / "data")
    legal_snapshot = _dir_snapshot(batch_root / "C06b_normal")
    check(checks, failures, "E2 data/ 只做有限首层观察（首层少于预算也不递归）",
          data_snapshot.get("__mode__") == "bounded_first_level_only"
          and data_snapshot.get("__recursive_hash_used__") is False
          and not any(not key.startswith("__") for key in data_snapshot),
          json.dumps({key: value for key, value in data_snapshot.items()
                      if key.startswith("__")}, ensure_ascii=False)[:250])
    check(checks, failures, "E2 合法八文件批次快照仍保真且按固定路径",
          legal_snapshot.get("__mode__") == "legal_batch_fixed_paths"
          and len([key for key in legal_snapshot if not key.startswith("__")]) == 8
          and legal_snapshot.get("__recursive_hash_used__") is False,
          json.dumps({key: value for key, value in legal_snapshot.items()
                      if key.startswith("__")}, ensure_ascii=False)[:250])

    # ---------------------------------------------------------------- 晚变更与 I/O 注入
    late_records = []
    late_dir = batch_root / "late_change"
    original_report = (late_dir / "checks" / "quality_report.json").read_bytes()

    probe = registry.call(["L0-无注入观察"], late_dir, request_ids["normal"])
    late_records.append({"phase": "observe_no_injection",
                         "outcome": probe["result"]["outcome"],
                         "read_events": probe["guard"]["read_events"],
                         "write_events": probe["guard"]["write_events"]})

    original_final_confirm = prepare._final_confirm

    def wrapped_final_confirm(target, batch_reads, project_reads):
        path = Path(target) / "checks" / "quality_report.json"
        with path.open("ab") as handle:
            handle.write(b"\n")
        return original_final_confirm(target, batch_reads, project_reads)

    prepare._final_confirm = wrapped_final_confirm
    try:
        injected = registry.call(["L1-最后消费后追加LF"], late_dir, request_ids["normal"],
                                 scope="deliberate_change")
    finally:
        prepare._final_confirm = original_final_confirm
    late_records.append({"phase": "late_change_at_final_confirmation",
                         "outcome": injected["result"]["outcome"],
                         "field": injected["result"].get("field")})
    check(checks, failures, "L1 最后必要消费后追加 LF → 本次拒绝并指向文件",
          injected["result"]["outcome"] == "blocked"
          and injected["result"].get("field") == "checks/quality_report.json",
          json.dumps(injected["result"], ensure_ascii=False)[:250])

    still = registry.call(["L2-撤销wrapper保留变更"], late_dir, request_ids["normal"])
    late_records.append({"phase": "kept_change_after_wrapper_removed",
                         "outcome": still["result"]["outcome"],
                         "field": still["result"].get("field")})
    check(checks, failures, "L2 撤销 wrapper 保留变更仍拒绝",
          still["result"]["outcome"] == "blocked",
          json.dumps(still["result"], ensure_ascii=False)[:250])

    (late_dir / "checks" / "quality_report.json").write_bytes(original_report)
    restored = registry.call(["L3-恢复原件"], late_dir, request_ids["normal"])
    late_records.append({"phase": "restored", "outcome": restored["result"]["outcome"]})
    check(checks, failures, "L3 恢复本轮原件后成功且只读（不写 failure）",
          restored["result"]["outcome"] == "prepared"
          and not (late_dir / "failure.json").exists(),
          json.dumps(restored["result"]["outcome"], ensure_ascii=False))

    original_path_read_bytes = Path.read_bytes
    injected_state = {"hits": 0}

    def path_read_bytes_raising(self):
        """在**真实 I/O 通道**上于末次确认阶段注入一次受控 OSError（映射注入，非真实磁盘故障）。"""
        if injected_state["hits"] == 0:
            injected_state["hits"] += 1
            raise OSError("injected final_read failure")
        return original_path_read_bytes(self)

    def final_confirm_with_channel_injection(target, batch_reads, project_reads):
        Path.read_bytes = path_read_bytes_raising
        try:
            return original_final_confirm(target, batch_reads, project_reads)
        finally:
            Path.read_bytes = original_path_read_bytes

    prepare._final_confirm = final_confirm_with_channel_injection
    try:
        oserror = registry.call(["L4-末次实读OSError"], batch_root / "C06b_normal",
                                request_ids["normal"])
    finally:
        prepare._final_confirm = original_final_confirm
        Path.read_bytes = original_path_read_bytes
    late_records.append({"phase": "final_read_oserror", "outcome": oserror["result"]["outcome"],
                         "stage": oserror["result"].get("stage"), "hits": injected_state["hits"]})
    check(checks, failures, "L4 末次实读受控 OSError → Error + OSError 原因链（映射注入）",
          oserror["result"]["outcome"] == "error"
          and oserror["result"].get("stage") == "final_read"
          and injected_state["hits"] == 1
          and any("OSError" in item["type"]
                  for item in (oserror["exception"] or {}).get("cause_chain", [])),
          json.dumps(oserror["result"], ensure_ascii=False)[:250])

    # ---------------------------------------------------------------- 收尾与证据
    guard_records = {"forbidden_total": sum(len(record["guard"]["forbidden"])
                                            for record in registry.records),
                     "write_ops_total": sum(len(record["guard"]["write_ops"])
                                            for record in registry.records),
                     "modules_after_total": sorted({name for record in registry.records
                                                    for name in record["modules_after"]}),
                     "source_bytes_unchanged_all_calls":
                         all(record["file_snapshot_unchanged"] for record in registry.records),
                     "project_files_unchanged_all_calls":
                         all(record["project_files_unchanged"] for record in registry.records),
                     "clean_calls": sum(1 for record in registry.records
                                        if record["scope"] == "clean"),
                     "deliberate_change_calls": sum(1 for record in registry.records
                                                    if record["scope"] == "deliberate_change"),
                     "clean_calls_files_unchanged": all(
                         record["file_snapshot_unchanged"] for record in registry.records
                         if record["scope"] == "clean"),
                     "clean_calls_project_unchanged": all(
                         record["project_files_unchanged"] for record in registry.records
                         if record["scope"] == "clean")}
    counts = {"prepare_calls": len(registry.records),
              "prepare_by_outcome": _outcome_counts(registry.records),
              "p1_calls": len(p1_records),
              "p1_entry_frame_observation": observer.entry_count,
              "receiver_runs": len(samples),
              "receiver_returncodes": {name: record["returncode"]
                                       for name, record in samples.items()},
              "checker_exit_codes": {name: record["checker_exit_code"]
                                     for name, record in samples.items()},
              "guard": guard_records,
              "helper_calls_saved": "helper_call_records.json",
              "not_executed": {"host_or_controller": None, "storage_save_verify": None,
                               "normalization_or_db": None, "gate2": None,
                               "real_initial_judgment": None, "ai_or_final_judgment": None,
                               "historical_enumeration": None,
                               "junction_case": None if junction.get("executed")
                               else "not_executed",
                               "checker_internal_function_counts": None}}
    helper_records = helper_observer.payload()
    helper_records["entry_frame_observation"] = observer.extra_counts["helper"]
    prepare_entry_observation = observer.extra_counts["prepare"]
    observer.uninstall()
    helper_observer.uninstall()
    counts["prepare_entry_frame_observation"] = prepare_entry_observation
    counts["helper_entry_frame_observation"] = helper_records["entry_frame_observation"]
    counts["helper_calls"] = {"entry_frame_observation": helper_records["entry_frame_observation"],
                             "declared_total": helper_records["total"],
                             "records_length": len(helper_records["records"]),
                             "saved_payload": "helper_call_records.json"}

    prepare_registry_payload = {
        "authoritative": True,
        "prepare_call_ids": [record["call_id"] for record in registry.records],
        "p1_call_ids": [f"p1-{index + 1:03d}" for index in range(len(p1_records))],
        "total_prepare_calls": len(registry.records),
        "total_p1_calls": len(p1_records),
        "p1_entry_frame_observation": observer.entry_count,
        "prepare_entry_frame_observation": prepare_entry_observation,
        "helper_entry_frame_observation": helper_records["entry_frame_observation"],
        "total_helper_calls": helper_records["total"],
        "helper_call_ids": [record["call_id"] for record in helper_records["records"]],
        "closure_ok": len(p1_records) == observer.entry_count,
    }
    expectation = {
        "source": "in_memory_real_observations_before_finalization",
        "prepare_registry": deep(prepare_registry_payload),
        "api_records": deep(registry.records),
        "p1_call_records": deep(p1_records),
        "helper_call_records": deep(helper_records),
        "prepare_entry_frame_observation": prepare_entry_observation,
        "helper_entry_frame_observation": helper_records["entry_frame_observation"],
    }
    expectation_sha = {"expectation_sha256": fingerprint(
        {key: value for key, value in expectation.items() if key != "source"}),
        "frozen_at": "all_observations_finalized_before_finalization"}

    summary = {"task": "TASK-023",
               "suite": "Gate1 只读候审请求适配器（材料来源、质量映射、路径/类型拒绝、晚变更与收尾）",
               "status": "PASS" if not failures else "FAIL",
               "checks_total": len(checks), "checks_failed": len(failures),
               "samples": {name: {key: record[key] for key in
                                  ("returncode", "batch_status", "checker_exit_code",
                                   "report_result", "issue_codes")}
                           for name, record in samples.items()},
               "counts": counts,
               "boundaries": {"request_persisted": False, "decision_recorded": False,
                              "execution_allowed": False, "workflow_connected": False,
                              "ai_enabled": False, "identity_authenticated": False,
                              "source_authenticity_proven": False},
               "not_executed": counts["not_executed"]}
    history_record = {"checks": deep(checks), "failures": deep(failures), "summary": deep(summary)}

    isolation = {"content_isolation": _content_isolation(expectation, registry.records),
                 "registry_isolation": _registry_isolation(prepare_registry_payload,
                                                           registry.records, p1_records,
                                                           helper_records,
                                                           observer.entry_count)}

    bodies = {
        "api_records.json": registry.records,
        "p1_call_records.json": p1_records,
        "sample_build_records.json": samples,
        "guard_records.json": guard_records,
        "late_change_records.json": {"junction": junction, "records": late_records,
                                     "negatives": [{"case": case, "result": result,
                                                    "field": field}
                                                   for case, result, field in negatives]},
        "counts.json": counts,
        "prepare_registry.json": prepare_registry_payload,
        "helper_call_records.json": helper_records,
        "isolation_self_tests.json": isolation,
        "observation_expectation_sha256.json": expectation_sha,
        "checks.json": checks,
        "failures.json": failures,
        "summary.json": summary,
    }

    def write_bodies():
        for name, payload in bodies.items():
            _write_json(out_dir / name, payload)

    # 1) 待写缓冲审核（**任何磁盘写入之前**）：canonical 内容比较 + 实际收尾登记审核 helper
    pending = {name: json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
               for name, payload in bodies.items()}
    pending_parsed = {name: {"bytes": len(data), "sha256": sha_bytes(data),
                             "parsed": json.loads(data.decode("utf-8"))}
                      for name, data in pending.items()}
    pending_content = _content_compare(expectation, pending_parsed)
    registry_audit = _final_registry_audit(prepare_registry_payload, registry.records,
                                           p1_records, helper_records,
                                           observer.entry_count,
                                           expected_helper=helper_records, source="pending_buffer")
    check(checks, failures, "A1 待写缓冲完整对象与定稿真实观察规范一致（canonical 字节主判据）",
          pending_content["ok"], json.dumps(pending_content, ensure_ascii=False)[:400])
    check(checks, failures, "A2 实际收尾登记审核 helper：prepare/P1/helper 完整登记与入口观察闭合",
          registry_audit["ok"], json.dumps(registry_audit, ensure_ascii=False)[:400])
    check(checks, failures, "A2b helper 完整载荷进入待写缓冲并逐条与真实观察一致",
          pending_content["ok"] and registry_audit["helper"]["complete_entries"] is True
          and registry_audit["helper"]["records_length"] == helper_records["total"],
          json.dumps(registry_audit["helper"], ensure_ascii=False)[:400])
    check(checks, failures, "A3 删一条权威登记由**同一审核 helper** 拒绝、原件通过",
          isolation["registry_isolation"]["audit_copy_fails"] is True
          and isolation["registry_isolation"]["original_passes"] is True,
          json.dumps(isolation["registry_isolation"], ensure_ascii=False)[:250])
    check(checks, failures, "A4 改一条真实观察载荷/一条 helper 返回由完整内容比较拒绝、原件通过",
          isolation["content_isolation"]["tampered_rejected"] is True
          and isolation["content_isolation"]["helper_return_mutation_rejected"] is True
          and bool(isolation["content_isolation"]["helper_return_mutation_located"])
          and isolation["content_isolation"]["original_ok"] is True,
          json.dumps(isolation["content_isolation"], ensure_ascii=False)[:250])
    check(checks, failures, "A5 同一审核 helper：删 helper entry/ID、重复、空壳、改返回均拒绝且定位",
          isolation["registry_isolation"]["helper_entry_removed_fails"] is True
          and isolation["registry_isolation"]["helper_id_removed_fails"] is True
          and isolation["registry_isolation"]["helper_entry_duplicated_fails"] is True
          and isolation["registry_isolation"]["helper_shell_entry_fails"] is True
          and isolation["registry_isolation"]["helper_return_mutated_fails"] is True
          and bool(isolation["registry_isolation"]["helper_entry_removed_located"])
          and bool(isolation["registry_isolation"]["helper_return_mutated_located"])
          and isolation["registry_isolation"]["legal_empty_result_present"] is True,
          json.dumps({key: value for key, value in isolation["registry_isolation"].items()
                      if key.endswith("fails") or key.endswith("located")},
                     ensure_ascii=False)[:400])

    # 2) 一次性写入最终载荷（此后只读；失败路径只允许写失败元数据，不覆盖被改载荷）
    summary["checks_total"] = len(checks)
    summary["checks_failed"] = len(failures)
    summary["status"] = "PASS" if not failures else "FAIL"
    write_bodies()

    # 3) 首轮终审读数 → 真实审核（同一读取缓冲取对象与 SHA）
    audited = _audited_read(out_dir, PAYLOAD_FILES)
    content_disk = _content_compare(expectation, audited)
    helper_disk_candidate = audited["helper_call_records.json"]["parsed"]
    registry_audit_disk = _final_registry_audit(
        audited["prepare_registry.json"]["parsed"],
        [audited_item["parsed"] for audited_item in ()] or registry.records,
        p1_records, helper_disk_candidate, observer.entry_count,
        expected_helper=helper_records, source="first_read_disk_candidate")

    # 4) **任何后续写入之前**的实际字节漂移确认
    drift = _byte_drift(out_dir, audited)
    audit_failed = (not content_disk["ok"] or not registry_audit_disk["ok"] or bool(drift))
    test_inputs = tuple(sorted("inputs/" + path.name
                               for path in (out_dir / "inputs").iterdir() if path.is_file()))
    ledger_entries = {name: {"exists": True, "bytes": audited[name]["bytes"],
                             "sha256": audited[name]["sha256"]} for name in PAYLOAD_FILES}
    validation = _ledger_validate(out_dir, ledger_entries, allowed_extra=test_inputs)
    if audit_failed or not validation["ok"]:
        failures.append({"name": "首轮终审读数/登记/字节漂移审核失败（终审失败支配结论）",
                         "detail": json.dumps({"content": content_disk,
                                               "registry_audit": registry_audit_disk,
                                               "byte_drift": drift,
                                               "ledger": validation},
                                              ensure_ascii=False)[:1200]})
        _write_json(out_dir / "failures.json", failures)
        failed_summary = dict(summary)
        failed_summary["checks_total"] = len(checks)
        failed_summary["checks_failed"] = len(failures)
        failed_summary["status"] = "FAIL"
        failed_summary["final_audit"] = {"content_ok": content_disk["ok"],
                                         "registry_audit_ok": registry_audit_disk["ok"],
                                         "byte_drift": drift, "ledger_ok": validation["ok"],
                                         "dominates_exit_code": True}
        _write_json(out_dir / "summary.json", failed_summary)
        _write_json(out_dir / "final_audit_diagnostic.json", {
            "detected": {"content": content_disk, "registry_audit": registry_audit_disk,
                         "byte_drift": drift, "ledger": validation},
            "post_audit_writes": ["failures.json", "summary.json",
                                  "final_audit_diagnostic.json"],
            "drifted_files_left_untouched": [item["name"] for item in drift],
            "note": ("首轮终审读数后立即做字节漂移确认；失败只写失败元数据，不覆盖被改载荷、"
                     "不重建台账、不把已漂移磁盘重新采为新期望"),
        })
        _write_json(out_dir / "evidence_ledger.json",
                    {"entries": ledger_entries, "entry_count": len(ledger_entries),
                     "covered_payloads": list(PAYLOAD_FILES),
                     "expectation_source": "首轮终审读数缓冲（失败现场保留）",
                     "validated": validation, "final_audit_failed": True,
                     "byte_drift": drift})
        print(f"TASK-023-R1 测试组：{len(checks)} 项检查，{len(failures)} 项失败（终审失败）")
        for item in failures[:10]:
            print(f"  - {item['name']}: {item['detail'][:200]}")
        return 1

    # 5) 干净路径：只写台账（期望来自首轮读数），不重写任何完整观察载荷
    _write_json(out_dir / "evidence_ledger.json",
                {"entries": ledger_entries, "entry_count": len(ledger_entries),
                 "covered_payloads": list(PAYLOAD_FILES),
                 "self_excluded": "evidence_ledger.json（不内嵌自身 SHA）",
                 "validated": validation,
                 "expectation_source": "首轮终审读数缓冲；审核前一次性写入，审核后未再改载荷",
                 "content_compare": content_disk,
                 "registry_audit": registry_audit_disk,
                 "disk_audit_source": registry_audit_disk["helper"]["source"],
                 "disk_candidate_records":
                     registry_audit_disk["helper"]["records_length"],
                 "disk_candidate_helper_sha256":
                     sha_bytes(canonical_bytes(helper_disk_candidate)),
                 "pending_buffer_audit": {"content_ok": pending_content["ok"],
                                          "registry_audit_ok": registry_audit["ok"]}})
    print(f"TASK-023-R1 测试组：{len(checks)} 项检查，{len(failures)} 项失败；"
          f"prepare 调用 {len(registry.records)}、真实 P1 调用 {len(p1_records)}、"
          f"接收器运行 {len(samples)}、helper 调用 {helper_records['total']}")
    for item in failures[:10]:
        print(f"  - {item['name']}: {item['detail'][:200]}")
    return 1 if failures else 0


# --------------------------------------------------------------------------- 证据工具
def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _outcome_counts(records):
    counts = {}
    for record in records:
        outcome = record["result"]["outcome"]
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def _audited_read(root: Path, names):
    audited = {}
    for name in names:
        data = (root / name).read_bytes()
        audited[name] = {"bytes": len(data), "sha256": sha_bytes(data),
                         "parsed": json.loads(data.decode("utf-8"))}
    return audited


def _field_diff(expected, candidate, prefix="", limit=40):
    if canonical_bytes(expected) == canonical_bytes(candidate):
        return []
    diffs = []
    if isinstance(expected, dict) and isinstance(candidate, dict):
        for key in sorted(set(expected.keys()) | set(candidate.keys())):
            path = f"{prefix}.{key}" if prefix else key
            if key not in candidate:
                diffs.append({"path": path, "difference": "missing"})
            elif key not in expected:
                diffs.append({"path": path, "difference": "extra"})
            else:
                diffs.extend(_field_diff(expected[key], candidate[key], path, limit))
    elif isinstance(expected, list) and isinstance(candidate, list):
        if len(expected) != len(candidate):
            diffs.append({"path": f"{prefix}[len]", "expected": len(expected),
                          "candidate": len(candidate)})
        for index, (left, right) in enumerate(zip(expected, candidate)):
            diffs.extend(_field_diff(left, right, f"{prefix}[{index}]", limit))
    else:
        diffs.append({"path": prefix or "(root)", "expected_type": type(expected).__name__,
                      "candidate_type": type(candidate).__name__,
                      "expected_sha256": sha_bytes(canonical_bytes(expected)),
                      "candidate_sha256": sha_bytes(canonical_bytes(candidate))})
    return diffs[:limit]


def _content_compare(expectation, audited):
    details, ok = {}, True
    for name, key in (("api_records.json", "api_records"),
                      ("p1_call_records.json", "p1_call_records"),
                      ("prepare_registry.json", "prepare_registry"),
                      ("helper_call_records.json", "helper_call_records")):
        want = expectation[key]
        candidate = audited[name]["parsed"]
        equal = canonical_bytes(want) == canonical_bytes(candidate)
        details[key] = {"file": name, "equal": equal,
                        "differences": [] if equal else _field_diff(want, candidate)}
        if key == "helper_call_records":
            details[key]["record_compare"] = _helper_records_compare(want, candidate)
            details[key]["located_call_ids"] = [
                item["call_id"] for item
                in details[key]["record_compare"]["problems"]]
        ok = ok and equal
    details["ok"] = ok
    return details


def _content_isolation(expectation, prepare_records):
    tampered = deep(prepare_records)
    for record in tampered:
        if record["result"]["outcome"] == "prepared":
            record["result"]["result"]["materials"]["quality"]["status"] = "OK-TAMPERED"
            break
    candidate = {"api_records": tampered, "p1_call_records": expectation["p1_call_records"],
                 "prepare_registry": expectation["prepare_registry"],
                 "helper_call_records": expectation["helper_call_records"]}
    mutated_helper = deep(expectation["helper_call_records"])
    mutated_helper["records"] = [dict(item) for item in mutated_helper["records"]]
    mutated_helper["records"][0]["result"] = ["合法字符串列表"]
    mutated_helper["records"][0]["result_fingerprint"] = fingerprint(
        mutated_helper["records"][0]["result"])
    compare = _content_compare(expectation, {
        "api_records.json": {"parsed": candidate["api_records"]},
        "p1_call_records.json": {"parsed": candidate["p1_call_records"]},
        "prepare_registry.json": {"parsed": candidate["prepare_registry"]},
        "helper_call_records.json": {"parsed": candidate["helper_call_records"]}})
    helper_mutation = _content_compare(expectation, {
        "api_records.json": {"parsed": expectation["api_records"]},
        "p1_call_records.json": {"parsed": expectation["p1_call_records"]},
        "prepare_registry.json": {"parsed": expectation["prepare_registry"]},
        "helper_call_records.json": {"parsed": mutated_helper}})
    return {"original_ok": _content_compare(expectation, {
        "api_records.json": {"parsed": expectation["api_records"]},
        "p1_call_records.json": {"parsed": expectation["p1_call_records"]},
        "prepare_registry.json": {"parsed": expectation["prepare_registry"]},
        "helper_call_records.json": {"parsed": expectation["helper_call_records"]}})["ok"],
        "tampered_rejected": not compare["ok"],
        "tampered_differences": compare["api_records"]["differences"][:3],
        "helper_return_mutation_rejected": not helper_mutation["ok"],
        "helper_return_mutation_located":
            helper_mutation["helper_call_records"]["located_call_ids"]}


def _helper_records_compare(expected, candidate):
    """按 helper `call_id` 定位的完整内容比较（canonical JSON 字节严格相等）。"""
    problems = []
    expected_records = {item["call_id"]: item for item in expected.get("records", [])}
    candidate_records = {item.get("call_id"): item for item in candidate.get("records", [])}
    if expected.get("total") != candidate.get("total"):
        problems.append({"call_id": None, "field": "total",
                         "expected": expected.get("total"), "actual": candidate.get("total")})
    for call_id in sorted(set(expected_records) - set(candidate_records)):
        problems.append({"call_id": call_id, "field": "records", "detail": "候选缺失该完整记录"})
    for call_id in sorted(set(candidate_records) - set(expected_records)):
        problems.append({"call_id": call_id, "field": "records", "detail": "候选多出未观察记录"})
    for call_id in sorted(set(expected_records) & set(candidate_records)):
        expected_bytes = canonical_bytes(expected_records[call_id])
        candidate_bytes = canonical_bytes(candidate_records[call_id])
        if expected_bytes != candidate_bytes:
            problems.append({"call_id": call_id, "field": "record",
                             "expected_sha256": sha_bytes(expected_bytes),
                             "actual_sha256": sha_bytes(candidate_bytes)})
    return {"ok": not problems, "problems": problems,
            "expected_total": expected.get("total"), "candidate_total": candidate.get("total"),
            "expected_records": len(expected_records),
            "candidate_records": len(candidate_records)}


def _final_registry_audit(payload, records, p1_records, helper_payload, entry_observation,
                          *, expected_helper=None, source="memory"):
    """**实际收尾使用的登记审核 helper**：核对 prepare/P1/helper 完整调用登记。

    - prepare：声明 ID 名单/总数 与 记录 ID 名单/条数 双向一致，且每条记录含输入现场与结果/异常；
    - P1：声明 ID 名单/总数 与 记录条数 一致，且与实际入口代码帧观察数闭合；
    - helper：声明总数 == 实际 helper 调用记录数。
    """
    detail = {}
    ok = True
    ids = list(payload.get("prepare_call_ids", []))
    keys = [record.get("call_id") for record in records]
    prepare_ok = (ids == keys and len(ids) == payload.get("total_prepare_calls")
                  == payload.get("prepare_entry_frame_observation")
                  and all(record.get("inputs") and record.get("result")
                          for record in records))
    detail["prepare"] = {"declared": len(ids), "records": len(keys),
                         "entry_frame_observation": payload.get("prepare_entry_frame_observation"),
                         "ids_match": ids == keys, "complete_records": all(
                             bool(record.get("inputs")) and bool(record.get("result"))
                             for record in records)}
    p1_ids = list(payload.get("p1_call_ids", []))
    p1_ok = (len(p1_ids) == payload.get("total_p1_calls") == len(p1_records)
             == entry_observation)
    detail["p1"] = {"declared": len(p1_ids), "total": payload.get("total_p1_calls"),
                    "records": len(p1_records), "entry_observation": entry_observation}
    records_list = list(helper_payload.get("records", []))
    declared_total = payload.get("total_helper_calls")
    record_ids = [item.get("call_id") for item in records_list]
    declared_ids = list(payload.get("helper_call_ids", []))
    entry_observed = payload.get("helper_entry_frame_observation")
    complete_entries = all(
        isinstance(item.get("inputs"), dict) and item["inputs"].get("report") is not None
        and item.get("outcome") in ("returned", "raised")
        and ("result" in item or "exception" in item)
        and item.get("input_unchanged_after_call") is True
        for item in records_list)
    helper_ok = (declared_total == len(records_list)
                 == entry_observed
                 == helper_payload.get("total")
                 and len(set(record_ids)) == len(record_ids)
                 and len(set(declared_ids)) == len(declared_ids)
                 and sorted(record_ids) == sorted(declared_ids)
                 and complete_entries
                 and bool(records_list))
    detail["helper"] = {"declared_total": declared_total, "payload_total": helper_payload.get("total"),
                        "records_length": len(records_list),
                        "entry_frame_observation": entry_observed,
                        "ids_bijective": sorted(record_ids) == sorted(declared_ids),
                        "unique_ids": len(set(record_ids)) == len(record_ids),
                        "complete_entries": complete_entries,
                        "source": source}
    if expected_helper is not None:
        helper_content = _helper_records_compare(expected_helper, helper_payload)
        helper_ok = helper_ok and helper_content["ok"]
        detail["helper"]["content_compare"] = helper_content
    detail["closure_ok"] = payload.get("closure_ok")
    ok = bool(prepare_ok and p1_ok and helper_ok and payload.get("closure_ok") is True)
    detail["ok"] = ok
    return detail


def _byte_drift(root: Path, audited):
    """首轮终审读数之后的实际字节漂移确认（与**该次读数**比较）。"""
    drift = []
    for name in PAYLOAD_FILES:
        try:
            data = (root / name).read_bytes()
        except OSError as exc:
            drift.append({"name": name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if len(data) != audited[name]["bytes"] or sha_bytes(data) != audited[name]["sha256"]:
            drift.append({"name": name, "bytes_now": len(data),
                          "sha256_now": sha_bytes(data),
                          "bytes_audited": audited[name]["bytes"],
                          "sha256_audited": audited[name]["sha256"]})
    return drift


def _registry_isolation(payload, records, p1_records, helper_records, entry_observation):
    """隔离审核：全部控制都由**同一** `_final_registry_audit` 判定（不手写替代比较）。

    控制：① 删一条 prepare 登记；② 删一条 helper 完整 entry（保留 total/ID/入口观察数）；
    ③ 删一个 helper ID；④ 重复一条 entry；⑤ 空壳 entry；⑥ 合法 `[]` 返回原件通过；
    ⑦ 一条返回改为合法字符串列表 → 由完整内容比较拒绝并按 call_id 定位。
    """
    original = _final_registry_audit(payload, records, p1_records, helper_records,
                                     entry_observation, expected_helper=helper_records)
    results = {}

    copy_payload = deep(payload)
    copy_payload["prepare_call_ids"] = list(payload["prepare_call_ids"])[:-1]
    results["prepare_registry_removed"] = _final_registry_audit(
        copy_payload, records, p1_records, helper_records, entry_observation,
        expected_helper=helper_records)

    cut = deep(helper_records)
    cut["records"] = cut["records"][:-1]
    results["helper_entry_removed_keep_total"] = _final_registry_audit(
        payload, records, p1_records, cut, entry_observation, expected_helper=helper_records)

    id_cut = deep(helper_records)
    id_cut["records"] = [dict(item) for item in id_cut["records"][:-1]]
    id_payload = deep(payload)
    id_payload["helper_call_ids"] = list(payload["helper_call_ids"])[:-1]
    id_cut["total"] = len(id_cut["records"])
    results["helper_id_removed"] = _final_registry_audit(
        id_payload, records, p1_records, id_cut, entry_observation, expected_helper=helper_records)

    dup = deep(helper_records)
    dup["records"] = dup["records"] + [deep(dup["records"][-1])]
    dup["total"] = len(dup["records"])
    results["helper_entry_duplicated"] = _final_registry_audit(
        payload, records, p1_records, dup, entry_observation, expected_helper=helper_records)

    shell = deep(helper_records)
    shell["records"] = [{"call_id": "helper-999", "outcome": "returned", "result": []}]
    shell["total"] = 1
    shell_payload = deep(payload)
    shell_payload["helper_call_ids"] = ["helper-999"]
    shell_payload["total_helper_calls"] = 1
    results["helper_shell_entry"] = _final_registry_audit(
        shell_payload, records, p1_records, shell, 1, expected_helper=helper_records)

    mutated = deep(helper_records)
    mutated["records"] = [dict(item) for item in mutated["records"]]
    mutated["records"][0]["result"] = ["合法字符串列表"]
    mutated["records"][0]["result_fingerprint"] = fingerprint(mutated["records"][0]["result"])
    results["helper_return_mutated"] = _final_registry_audit(
        payload, records, p1_records, mutated, entry_observation, expected_helper=helper_records)

    empty_ok = [item for item in helper_records["records"] if item.get("result") == []]
    original_ok = bool(original["ok"])
    return {"original_audit": original, "controls": results,
            "original_passes": original_ok,
            "removed_prepare_call_id": (payload["prepare_call_ids"][-1]
                                        if payload["prepare_call_ids"] else None),
            "audit_copy_fails": not results["prepare_registry_removed"]["ok"],
            "helper_entry_removed_fails": not results["helper_entry_removed_keep_total"]["ok"],
            "helper_entry_removed_located": [
                problem for problem
                in results["helper_entry_removed_keep_total"]["helper"].get(
                    "content_compare", {}).get("problems", [])],
            "helper_id_removed_fails": not results["helper_id_removed"]["ok"],
            "helper_entry_duplicated_fails": not results["helper_entry_duplicated"]["ok"],
            "helper_shell_entry_fails": not results["helper_shell_entry"]["ok"],
            "helper_return_mutated_fails": not results["helper_return_mutated"]["ok"],
            "helper_return_mutated_located": [
                problem for problem
                in results["helper_return_mutated"]["helper"].get(
                    "content_compare", {}).get("problems", [])],
            "legal_empty_result_present": bool(empty_ok)}


def _ledger_validate(root: Path, entries, allowed_extra=()):
    missing, unregistered = [], []
    for relative, entry in entries.items():
        target = root / relative
        if not target.is_file():
            missing.append(relative)
            continue
        if target.stat().st_size != entry["bytes"] or sha_file(target) != entry["sha256"]:
            missing.append(relative)
    for entry in sorted(root.rglob("*")):
        if entry.is_file():
            relative = entry.relative_to(root).as_posix()
            if relative not in entries and relative not in LAYERED \
                    and relative not in allowed_extra:
                unregistered.append(relative)
    return {"missing": missing, "unregistered": unregistered,
            "ok": not missing and not unregistered}


def main():
    parser = argparse.ArgumentParser(description="TASK-023 Gate1 候审请求适配器测试入口")
    parser.add_argument("--out-dir", required=True, help="全新空证据容器目录")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    return run_suite(out_dir)


if __name__ == "__main__":
    sys.exit(main())
