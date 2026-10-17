#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-015 验证入口：冻结事实底稿核心接入宿主（build-fact-packet / 0007）。

用法：
    .venv\\Scripts\\python.exe -B tests\\test_fact_packet_demo_workflow.py --out-dir data\\workflow_host_tests\\task015_<唯一名称>
    ... --only main|samples|premise|persistence|late|readonly|evidence|protection|smoke

八组（卡 §7）：MAIN 正常接入 / 小样与合法阶段 / 前提与接口拒绝 / 有限持久化故障 /
晚变更与固定引用 / 只读隔离与输入不变 / 证据登记与计数 / 保护与停止点。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOST_PATH = PROJECT_ROOT / "scripts" / "run_demo_workflow.py"
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
BATCHES_ROOT = PROJECT_ROOT / "data" / "batches"
GENERATED = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a"
SQLITE_ROOT = PROJECT_ROOT / "data" / "sqlite_tests" / "workflow_gate2"
BASELINE = (PROJECT_ROOT / "data" / "reviews" / "task014_r2_gpt_20261012_225658"
            / "source_hashes_after.json")
BASELINE_SHA = "19639176acb6dae72cdd0c2ede0df86c4f917d05971cba9da45da99080505e1b"
BASELINE_ENTRIES = 118788
R2_BASELINE = (PROJECT_ROOT / "data" / "reviews" / "task015_r1_gpt_20261013_004706"
               / "source_hashes_after.json")
R2_BASELINE_SHA = "a4a0e9b56be3baeba72a488e871466b4bc08cc5c62430c6245f38bfdfd95c48b"
R2_BASELINE_ENTRIES = 123108
R2_ALLOWED_CHANGES = {"tests/test_fact_packet_demo_workflow.py"}
R2_FROZEN = {
    "scripts/run_demo_workflow.py":
        "67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a",
    "docs/WORKFLOW_HOST_GUIDE.md":
        "ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8",
    "scripts/build_demo_fact_packet.py":
        "f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62",
    "tests/test_build_demo_fact_packet.py":
        "46d426e7c262f3b5c773ba6717e5b3e002c34783d11d24a5bd3c43b80effeb36",
    "docs/FACT_PACKET_GUIDE.md":
        "48c051be9bfca3659560c73e4693892ecd1a72629fba7401698eb87f8657ff9d",
    "scripts/crosscheck_demo_rules.py":
        "8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2",
    "tests/test_crosscheck_demo_workflow.py":
        "f34533833d0fa0ac41274f1c847f933ecaf8110de65e35acc43c8bf12393cf43",
    "tests/test_screen_demo_workflow.py":
        "27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca",
}
SKIP_DIRS = {".venv", ".git"}
ALLOWED_CHANGES = {"scripts/run_demo_workflow.py", "docs/WORKFLOW_HOST_GUIDE.md"}
FROZEN = {
    "scripts/build_demo_fact_packet.py":
        "f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62",
    "tests/test_build_demo_fact_packet.py":
        "46d426e7c262f3b5c773ba6717e5b3e002c34783d11d24a5bd3c43b80effeb36",
    "docs/FACT_PACKET_GUIDE.md":
        "48c051be9bfca3659560c73e4693892ecd1a72629fba7401698eb87f8657ff9d",
    "scripts/crosscheck_demo_rules.py":
        "8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2",
    "tests/test_crosscheck_demo_workflow.py":
        "f34533833d0fa0ac41274f1c847f933ecaf8110de65e35acc43c8bf12393cf43",
    "tests/test_screen_demo_workflow.py":
        "27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca",
}
DOWNSTREAM_GUARDS = ("normalize_workbook", "load_normalized_to_sqlite", "screen_sqlite",
                     "verify_rule_facts", "build_fact_packet")


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def canonical_sha256(payload) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def same_json(left, right) -> bool:
    return canonical_json(left) == canonical_json(right)


def load_host():
    spec = importlib.util.spec_from_file_location("task015_host", HOST_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load_host()


def tree_hashes(root: Path) -> dict:
    if not root.exists():
        return {}
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def load_json_if_parseable(path: Path) -> tuple:
    if not path.is_file():
        return {}, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}, False


def collect_batch_outcome(batch_dir: Path) -> dict:
    screening, _ = load_json_if_parseable(batch_dir / "workflow/screening/screening_report.json")
    packet_path = batch_dir / "workflow/fact_packet/fact_packet.json"
    packet, packet_ok = load_json_if_parseable(packet_path)
    markdown_path = batch_dir / "workflow/fact_packet/fact_packet.md"
    failure_path = batch_dir / "workflow/fact_packet/failure.json"
    failure, failure_ok = load_json_if_parseable(failure_path)
    voucher, voucher_ok = load_json_if_parseable(batch_dir / "workflow/checkpoints/0007.json")
    return {
        "screening_status": screening.get("batch_status"),
        "screening_findings": len(screening.get("findings") or []),
        "packet_present": packet_path.is_file(),
        "packet_parseable": packet_ok,
        "packet_file_sha256": sha256(packet_path) if packet_path.is_file() else None,
        "packet_sha256": canonical_sha256(packet) if packet_ok else None,
        "packet_batch_status": packet.get("batch_status"),
        "markdown_present": markdown_path.is_file(),
        "markdown_bytes": markdown_path.stat().st_size if markdown_path.is_file() else None,
        "failure_present": failure_path.is_file(),
        "failure_parseable": failure_ok,
        "failure_target_exit_code": failure.get("target_exit_code"),
        "voucher_0007_present": voucher_ok,
        "voucher_revision": voucher.get("revision"),
        "voucher_kind": (voucher.get("operation") or {}).get("kind"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TASK-015 验证入口")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--only", default="all",
                        choices=["all", "main", "samples", "premise", "persistence", "late",
                                 "late-controller", "readonly", "evidence", "protection",
                                 "smoke"])
    args = parser.parse_args(argv)
    only = args.only

    container = Path(args.out_dir).resolve()
    if container.exists() and any(container.iterdir()):
        print(f"[拒绝] --out-dir 已存在且非空：{container}")
        return 2
    try:
        container.relative_to(PROJECT_ROOT / "data" / "workflow_host_tests")
    except ValueError:
        print(f"[拒绝] --out-dir 必须位于 data/workflow_host_tests 之下：{container}")
        return 2
    for sub in ("cli_logs", "probe_records", "core_returns", "api_records", "isolation"):
        (container / sub).mkdir(parents=True, exist_ok=True)
    batch_parent = BATCHES_ROOT / container.name
    batch_parent.mkdir(parents=True, exist_ok=True)
    sqlite_parent = SQLITE_ROOT / container.name
    sqlite_parent.mkdir(parents=True, exist_ok=True)

    checks: list = []
    failures: list = []
    cli_records: list = []
    api_records: list = []
    call_registry: list = []
    counts = {
        "cli_calls": {}, "api_calls": {},
        "core_observations": {"build_fact_packet_inprocess": 0,
                              "verify_rule_facts_inprocess": 0,
                              "screen_sqlite_inprocess": 0,
                              "cli_internal_core_calls": None},
        "fault_injections": 0, "copies": 0, "receiver_starts": 0, "simulated_decisions": 0,
        "real_approvals": 0, "facts_built_in_flow": 0, "fail_then_abandoned": 0,
        "fact_packet_failure_scenes": 0, "matched_reports_total": 0,
        "crosscheck_matched_reports_total": 0, "packet_ready_total": 0,
        "voucher_0007_physical_total": 0, "voucher_0007_parseable_total": 0,
        "voucher_0007_half_written_total": 0,
        "success_vouchers_0007_total": 0, "half_written_vouchers": 0,
        "checker_started_by_receiver": 0, "direct_checker_cli_calls": 0,
        "missing_records": 0, "unregistered_records": 0,
    }

    def record(name: str, kind: str, problems: list, **extra) -> None:
        entry = {"case": name, "kind": kind, "result": "PASS" if not problems else "FAIL",
                 "problems": problems, **extra}
        checks.append(entry)
        print(f"    [{'PASS' if not problems else 'FAIL'}] {name}"
              + ("" if not problems else f" | {problems[:2]}"))
        if problems:
            failures.append({"case": name, "problems": problems})

    def save_json(path: Path, payload) -> Path:
        path.write_text(canonical_indent(payload) + "\n", encoding="utf-8")
        return path

    def canonical_indent(payload) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)

    def rel(path: Path) -> str:
        return str(path.relative_to(container)).replace("\\", "/")

    def caller_names(depth: int, frame) -> list:
        names = []
        while frame is not None and len(names) < depth:
            names.append(frame.f_code.co_name)
            frame = frame.f_back
        return names

    def run_cli(label: str, sub_args: list, expect_exit) -> dict:
        command = [str(PYTHON), "-B", str(HOST_PATH), *sub_args]
        done = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True,
                              encoding="utf-8")
        stdout_path = container / "cli_logs" / f"{label}.stdout.txt"
        stderr_path = container / "cli_logs" / f"{label}.stderr.txt"
        stdout_path.write_text(done.stdout or "", encoding="utf-8")
        stderr_path.write_text(done.stderr or "", encoding="utf-8")
        try:
            payload = json.loads(done.stdout)
        except (json.JSONDecodeError, TypeError):
            payload = None
        subcommand = next((item for item in ("start", "status", "record-simulated-decision",
                                             "prepare-gate2", "record-simulated-gate2-decision",
                                             "screen-rules", "crosscheck-rules",
                                             "build-fact-packet")
                           if item in sub_args), "unknown")
        return_path = container / "cli_logs" / f"{label}.return.json"
        save_json(return_path, payload if payload is not None
                  else {"_non_json_stdout": True,
                        "_raw_sha256": hashlib.sha256((done.stdout or "").encode("utf-8")).hexdigest()})
        entry = {"record_kind": "cli", "label": label, "subcommand": subcommand,
                 "command": command, "cwd": str(PROJECT_ROOT), "exit_code": done.returncode,
                 "expected_exit": expect_exit,
                 "ok": (expect_exit is None or done.returncode == expect_exit),
                 "stdout_path": rel(stdout_path), "stderr_path": rel(stderr_path),
                 "stdout_sha256": sha256(stdout_path), "stderr_sha256": sha256(stderr_path),
                 "return_object_path": rel(return_path), "return_object_sha256": sha256(return_path),
                 "return_object": payload}
        cli_records.append(entry)
        call_registry.append({"record": f"cli:{label}", "record_kind": "cli",
                              "subcommand": subcommand, "exit_code": done.returncode})
        counts["cli_calls"][subcommand] = counts["cli_calls"].get(subcommand, 0) + 1
        if subcommand == "start":
            counts["receiver_starts"] += 1
        if subcommand in ("record-simulated-decision", "record-simulated-gate2-decision"):
            counts["simulated_decisions"] += 1
        return entry

    def record_api(label: str, func, *func_args, expect_exception=None, **func_kwargs) -> dict:
        result, error = None, None
        try:
            result = func(*func_args, **func_kwargs)
        except Exception as exc:  # noqa: BLE001
            error = exc
        return_path = container / "api_records" / f"{label}.return.json"
        error_path = container / "api_records" / f"{label}.exception.json"
        if result is not None:
            save_json(return_path, result)
        if error is not None:
            tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
            save_json(error_path, {"exception_class": type(error).__name__, "message": str(error),
                                   "stage": getattr(error, "stage", None),
                                   "reasons": [str(item) for item in
                                               getattr(error, "reasons", []) or []],
                                   "exception_chain": host._exception_chain(error),
                                   "traceback_source": "exception.__traceback__",
                                   "traceback": "".join(tb_lines)})
        entry = {"record_kind": "api", "label": label, "entry": getattr(func, "__name__", str(func)),
                 "args": [str(item) for item in func_args],
                 "outcome": ("returned" if error is None else "raised"),
                 "exception_class": type(error).__name__ if error else None,
                 "return_path": rel(return_path) if result is not None else None,
                 "return_sha256": sha256(return_path) if result is not None else None,
                 "exception_path": rel(error_path) if error is not None else None,
                 "exception_sha256": sha256(error_path) if error is not None else None,
                 "expected_exception": (expect_exception.__name__ if expect_exception else None)}
        api_records.append(entry)
        call_registry.append({"record": f"api:{label}", "record_kind": "api",
                              "entry": entry["entry"], "outcome": entry["outcome"]})
        counts["api_calls"][entry["entry"]] = counts["api_calls"].get(entry["entry"], 0) + 1
        if error is not None and expect_exception is not None \
                and not isinstance(error, expect_exception):
            failures.append({"case": f"api:{label}",
                             "problems": [f"期望 {expect_exception.__name__}，实际 "
                                          f"{type(error).__name__}: {error}"]})
        return entry

    def write_decision(batch_dir: Path, revision: int, gate: str, value: str, event_id: str) -> Path:
        payload = json.loads((batch_dir / f"workflow/checkpoints/{revision:04d}.json")
                             .read_text(encoding="utf-8"))
        request = payload["workflow"]["state"]["requests"][gate]
        body = {"event_id": event_id, "batch_id": batch_dir.name, "gate": gate,
                "request_id": request["request_id"],
                "materials_sha256": request["materials_sha256"],
                "decision": value, "actor_kind": "SIMULATED_HUMAN", "actor_id": "t15-tester",
                "occurred_at": "2026-10-13T09:00:00+08:00",
                "reason": "TASK-015 开发态验证（模拟，非真实批准）",
                "simulation": "SIMULATED_TEST_ONLY",
                "confirmations": ({"scope_and_source_reviewed": True} if gate == "GATE1"
                                  else {"reconciliation_reviewed": True})}
        path = container / f"decision_{batch_dir.name}_{gate}_{value}.json"
        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return path

    def chain_to_gate2_decision(name: str, fixture: str, value: str,
                               workbook: Path | None = None) -> Path:
        target = batch_parent / name
        run_cli(f"{name}_start", ["start", "--workbook",
                                  str(workbook or (GENERATED / "fixtures" / fixture)),
                                  "--batch-dir", str(target),
                                  "--source-description", f"TASK-015 {name}"], 0)
        run_cli(f"{name}_gate1", ["record-simulated-decision", "--batch-dir", str(target),
                                  "--decision-file",
                                  str(write_decision(target, 1, "GATE1", "APPROVE",
                                                     f"EVT-{name}-G1"))], 0)
        run_cli(f"{name}_prepare", ["prepare-gate2", "--batch-dir", str(target)], 0)
        run_cli(f"{name}_gate2", ["record-simulated-gate2-decision", "--batch-dir", str(target),
                                  "--decision-file",
                                  str(write_decision(target, 3, "GATE2", value,
                                                     f"EVT-{name}-G2"))], 0)
        return target

    def chain_to_screened(name: str, fixture: str, value: str = "APPROVE", *,
                          workbook: Path | None = None, tamper: bool = False) -> Path:
        target = chain_to_gate2_decision(name, fixture, value, workbook=workbook)
        if not tamper:
            run_cli(f"{name}_screen", ["screen-rules", "--batch-dir", str(target)], 0)
            return target
        real_core = host.SCREEN_MODULE.screen_sqlite
        captured = {"changed": None, "exception": None}

        def tampered_core(database, load_report, *, cutoff_date=None):
            result = real_core(database, load_report, cutoff_date=cutoff_date)
            counts["core_observations"]["screen_sqlite_inprocess"] += 1
            changed = copy.deepcopy(result)
            for finding in changed.get("findings") or []:
                amounts = finding.get("amounts_cents")
                if not isinstance(amounts, dict):
                    continue
                for field in ("paid_total", "overpayment", "refund_total", "net_total",
                              "payable_amount", "allocated_amount", "paid_amount"):
                    value_int = amounts.get(field)
                    if isinstance(value_int, int) and not isinstance(value_int, bool):
                        amounts[field] = value_int + 1
                        captured["changed"] = {"rule_id": finding.get("rule_id"), "field": field,
                                               "field_path": f"amounts_cents.{field}",
                                               "before": value_int, "after": value_int + 1}
                        break
                if captured["changed"]:
                    break
            assert captured["changed"] is not None, "真实 MISMATCH 造样未找到可改整数分事实"
            counts["fault_injections"] += 1
            return changed

        host.SCREEN_MODULE.screen_sqlite = tampered_core
        try:
            entry = record_api(f"{name}_screen_tampered", host.screen_dev_batch, target)
        finally:
            host.SCREEN_MODULE.screen_sqlite = real_core
        assert entry["outcome"] == "returned", f"造样筛查未成功：{entry['exception_class']}"
        captured["api_label"] = entry["label"]
        tamper_records.append(captured)
        return target

    def chain_to_crosschecked(name: str, fixture: str) -> Path:
        target = chain_to_screened(name, fixture)
        run_cli(f"{name}_crosscheck", ["crosscheck-rules", "--batch-dir", str(target)], 0)
        return target

    tamper_records: list = []

    def build_and_capture(name: str, target: Path, expect_exit: int,
                          expect_exception=None) -> dict:
        """真实调用一次公开 API（进程内），捕获核心完整真实返回与三输入三类时点指纹。"""
        real_core = host.FACT_PACKET_MODULE.build_fact_packet
        state = {"calls": 0, "return_path": None, "before": None, "after_core": None,
                 "after_public": None, "normalized_ref": None, "screening_ref": None,
                 "crosscheck_ref": None}

        def capturing(normalized, screening_report, crosscheck_report):
            state["normalized_ref"] = normalized
            state["screening_ref"] = screening_report
            state["crosscheck_ref"] = crosscheck_report
            state["before"] = {"normalized": canonical_sha256(normalized),
                               "screening_report": canonical_sha256(screening_report),
                               "crosscheck_report": canonical_sha256(crosscheck_report)}
            result = real_core(normalized, screening_report, crosscheck_report)
            state["calls"] += 1
            counts["core_observations"]["build_fact_packet_inprocess"] += 1
            path = save_json(container / "core_returns" / f"{name}_build_fact_packet_return.json",
                             result)
            state["return_path"] = rel(path)
            state["after_core"] = {"normalized": canonical_sha256(normalized),
                                   "screening_report": canonical_sha256(screening_report),
                                   "crosscheck_report": canonical_sha256(crosscheck_report)}
            return result

        host.FACT_PACKET_MODULE.build_fact_packet = capturing
        try:
            api_entry = record_api(f"{name}_build_fact_packet", host.build_dev_fact_packet, target,
                                   expect_exception=expect_exception)
        finally:
            host.FACT_PACKET_MODULE.build_fact_packet = real_core
        if state["normalized_ref"] is not None:
            state["after_public"] = {"normalized": canonical_sha256(state["normalized_ref"]),
                                     "screening_report": canonical_sha256(state["screening_ref"]),
                                     "crosscheck_report": canonical_sha256(state["crosscheck_ref"])}
        state["api_entry"] = api_entry
        return state

    def finalize_evidence(mode_label: str, scenes_for_counts: list) -> list:
        """定点入口的真实证据收尾：登记表/文件台账/现场计数/保护比较全部落盘并进入正式 failures。

        返回本次新增的 failures 文本列表；不执行的部分如实写 null／未执行，不填未测得的 0。
        """
        problems: list = []
        # --- 调用登记与文件台账 ---
        registry_path = save_json(container / "call_registry.json",
                                  {"calls": call_registry, "cli": len(cli_records),
                                   "api": len(api_records), "mode": mode_label})
        ledger_entries = []
        for item in cli_records:
            for key, digest_key in (("stdout_path", "stdout_sha256"),
                                    ("stderr_path", "stderr_sha256"),
                                    ("return_object_path", "return_object_sha256")):
                target_file = container / item[key]
                ledger_entries.append({"record": f"cli:{item['label']}", "field": key,
                                       "path": item[key], "exists": target_file.is_file(),
                                       "expected_sha256": item.get(digest_key),
                                       "actual_sha256": sha256(target_file)
                                       if target_file.is_file() else None})
        for item in api_records:
            for key, digest_key in (("return_path", "return_sha256"),
                                    ("exception_path", "exception_sha256")):
                if not item.get(key):
                    continue
                target_file = container / item[key]
                ledger_entries.append({"record": f"api:{item['label']}", "field": key,
                                       "path": item[key], "exists": target_file.is_file(),
                                       "expected_sha256": item.get(digest_key),
                                       "actual_sha256": sha256(target_file)
                                       if target_file.is_file() else None})

        def audit_ledger(payload) -> list:
            found = []
            for entry in payload["file_ledger"]:
                target_file = container / entry["path"]
                if not target_file.is_file():
                    found.append(f"记录文件缺失：{entry['path']}")
                elif entry.get("expected_sha256") is not None \
                        and sha256(target_file) != entry["expected_sha256"]:
                    found.append(f"记录哈希不符：{entry['path']}")
            return found

        def audit_registration(payload) -> list:
            found = []
            cli_names = {f"cli:{item['label']}" for item in payload["cli_records"]}
            api_names = {f"api:{item['label']}" for item in payload["api_records"]}
            record_names = cli_names | api_names
            ledger_names = {entry["record"] for entry in payload["file_ledger"]}
            registry_names = {item["record"] for item in payload.get("registry_calls", [])}
            for name in sorted(record_names - ledger_names):
                found.append(f"调用记录未登记进文件台账：{name}")
            for name in sorted(record_names - registry_names):
                found.append(f"调用未登记进权威登记表：{name}")
            for name in sorted(registry_names - record_names):
                found.append(f"登记表存在无对应记录的条目：{name}")
            return found

        ledger = {"mode": mode_label, "cli_records": cli_records, "api_records": api_records,
                  "file_ledger": ledger_entries, "counts": counts,
                  "call_registry_path": rel(registry_path), "registry_calls": call_registry}
        ledger_path = save_json(container / "evidence_ledger.json", ledger)
        ledger_problems = audit_ledger(ledger) + audit_registration(ledger)
        counts["missing_records"] = len(ledger_problems)
        stdout_files = sorted(item.name for item in (container / "cli_logs").glob("*.stdout.txt"))
        registered_cli = {item["label"] for item in cli_records}
        unregistered = [name for name in stdout_files
                        if name[: -len(".stdout.txt")] not in registered_cli]
        counts["unregistered_records"] = len(unregistered)
        if ledger_problems:
            problems.extend(ledger_problems[:5])
        if unregistered:
            problems.append(f"存在未登记 CLI 原文：{unregistered[:3]}")
        # 双向一致：CLI/API 记录数与文件数
        if len(stdout_files) != len(cli_records):
            problems.append(f"CLI stdout 文件数与记录数不符：{len(stdout_files)}/{len(cli_records)}")
        api_return_files = sorted(item.name for item in (container / "api_records").glob("*.json"))
        expected_api_files = len([item for item in api_records if item.get("return_path")]) \
            + len([item for item in api_records if item.get("exception_path")])
        if len(api_return_files) != expected_api_files:
            problems.append(f"API 记录文件数与登记数不符：{len(api_return_files)}/"
                            f"{expected_api_files}")

        # --- 现场计数与 receiver/checker ---
        scene_records_local: list = []
        checker_records_local: list = []
        for batch_dir in sorted((item for item in batch_parent.iterdir() if item.is_dir()),
                                key=lambda item: item.name):
            crosscheck_report, _cc = load_json_if_parseable(
                batch_dir / "workflow/crosscheck/crosscheck_report.json")
            manifest_path = batch_dir / "batch_manifest.json"
            manifest, _ = load_json_if_parseable(manifest_path)
            invocation = manifest.get("checker_invocation")
            host_manifest, _ = load_json_if_parseable(batch_dir / "workflow"
                                                      / "host_manifest.json")
            receive = host_manifest.get("receive") or {}
            inv_payload, _ = load_json_if_parseable(batch_dir / "workflow"
                                                    / "receive_invocation.json")
            entry = {"batch": batch_dir.name, "outcome": collect_batch_outcome(batch_dir),
                     "crosscheck": {"matched": crosscheck_report.get("matched"),
                                    "batch_status": crosscheck_report.get("batch_status")},
                     "checker": None, "receiver": {
                         "command_matches": receive.get("command") == inv_payload.get("command"),
                         "exit_code_matches": receive.get("exit_code")
                         == inv_payload.get("exit_code")}}
            if not entry["receiver"]["command_matches"] or not entry["receiver"]["exit_code_matches"]:
                problems.append(f"{batch_dir.name}: receiver 命令/退出码不一致")
            if isinstance(invocation, dict):
                entry["checker"] = {"argv": invocation.get("argv"),
                                    "started": invocation.get("started"),
                                    "exit_code": invocation.get("exit_code"),
                                    "report_result": invocation.get("report_result")}
                for key in ("report", "stdout_log", "stderr_log"):
                    reference = invocation.get(key) or {}
                    reference_path = batch_dir / str(reference.get("path") or "")
                    exists = reference_path.is_file()
                    actual = sha256(reference_path) if exists else None
                    verified = bool(exists and actual == reference.get("sha256")
                                    and reference.get("exists") is True)
                    entry[f"{key}_verified"] = verified
                    if not verified:
                        problems.append(f"{batch_dir.name}: checker {key} 引用未验证")
                if invocation.get("started") is True and invocation.get("exit_code") == 0:
                    checker_records_local.append({"batch": batch_dir.name})
            scene_records_local.append(entry)

        outcomes = [item["outcome"] for item in scene_records_local]
        packet_ready = [item for item in outcomes
                        if item["packet_batch_status"] == "DEV_FACT_PACKET_READY"]
        physical = [item for item in scene_records_local
                    if (batch_parent / item["batch"]
                        / "workflow/checkpoints/0007.json").is_file()]
        parseable = [item for item in physical
                     if load_json_if_parseable(batch_parent / item["batch"]
                                               / "workflow/checkpoints/0007.json")[1]]
        with_failure = [item for item in outcomes if item["failure_present"]]
        success_no_failure = [item for item in outcomes if item["voucher_0007_present"]
                              and item["packet_parseable"] and not item["failure_present"]]
        half = [item for item in physical
                if item["outcome"]["failure_present"]
                and not load_json_if_parseable(batch_parent / item["batch"]
                                               / "workflow/checkpoints/0007.json")[1]]
        crosscheck_matched = [item for item in scene_records_local
                              if (item.get("crosscheck") or {}).get("matched") is True]
        counts["mode"] = mode_label
        counts["scenes_total"] = len(scene_records_local)
        counts["voucher_0007_physical_total"] = len(physical)
        counts["voucher_0007_parseable_total"] = len(parseable)
        counts["voucher_0007_half_written_total"] = len(half)
        counts["packet_ready_total"] = len(packet_ready)
        counts["crosscheck_matched_reports_total"] = len(crosscheck_matched)
        counts["success_vouchers_0007_total"] = len(success_no_failure)
        counts["fact_packet_failure_scenes"] = len(with_failure)
        counts["receiver_starts_recorded"] = len(scene_records_local)
        counts["checker_started_by_receiver"] = len(checker_records_local)
        counts["direct_checker_cli_calls"] = 0
        counts["matched_reports_total"] = len(crosscheck_matched)
        save_json(container / "scene_outcomes.json",
                  {"mode": mode_label, "scenes": outcomes, "records": scene_records_local,
                   "derived": {key: counts[key] for key in (
                       "scenes_total", "crosscheck_matched_reports_total", "packet_ready_total",
                       "voucher_0007_physical_total", "voucher_0007_parseable_total",
                       "voucher_0007_half_written_total", "success_vouchers_0007_total",
                       "fact_packet_failure_scenes", "receiver_starts_recorded",
                       "checker_started_by_receiver", "direct_checker_cli_calls")},
                   "scope": ("本模式现场导出；进程内核心计数只覆盖本次实际包装的调用，"
                             "子进程内部次数未观察（null）")})

        # --- 隔离自测：只删审核副本一条权威登记 ---
        copy_path = container / "isolation" / "evidence_ledger_minus_one.json"
        trimmed = copy.deepcopy(ledger)
        removed = trimmed["file_ledger"].pop(0)
        removed_registry = trimmed["registry_calls"].pop(0)
        save_json(copy_path, trimmed)
        isolation_failures = audit_ledger(trimmed) + audit_registration(trimmed)
        if not isolation_failures:
            problems.append(f"隔离自测未失败（去掉 {removed['record']}／{removed['field']}、"
                            f"登记表 {removed_registry['record']}）")
        save_json(container / "isolation" / "isolation_result.json",
                  {"mode": mode_label, "removed_ledger_entry": removed,
                   "removed_registry_entry": removed_registry,
                   "audit_problems_on_trimmed": isolation_failures,
                   "audit_problems_on_original": ledger_problems,
                   "note": "只操作审核副本；真实日志、登记表与文件台账未改。"})

        # --- 保护比较（本轮正确基线） ---
        if not R2_BASELINE.is_file():
            problems.append(f"本轮保护基线缺失：{R2_BASELINE}")
            save_json(container / "probe_records" / "r2_protection.json",
                      {"baseline": str(R2_BASELINE), "executed": False,
                       "problems": problems[-1:]})
        else:
            if sha256(R2_BASELINE) != R2_BASELINE_SHA:
                problems.append("本轮保护基线文件哈希与验收记录登记不一致")
            baseline_raw = json.loads(R2_BASELINE.read_text(encoding="utf-8"))
            if len(baseline_raw) != R2_BASELINE_ENTRIES:
                problems.append(f"本轮保护基线条目数不是 {R2_BASELINE_ENTRIES}："
                                f"{len(baseline_raw)}")
            baseline = {name.replace("\\", "/"): digest
                        for name, digest in baseline_raw.items()}
            scan = {}
            read_errors = 0
            for path in PROJECT_ROOT.rglob("*"):
                if not path.is_file():
                    continue
                relative = path.relative_to(PROJECT_ROOT).as_posix()
                if relative.split("/")[0] in SKIP_DIRS:
                    continue
                try:
                    scan[relative] = sha256(path)
                except OSError:
                    read_errors += 1
            changed = sorted(name for name, digest in baseline.items()
                             if name in scan and scan[name] != digest)
            missing = sorted(name for name in baseline if name not in scan)
            unexpected = sorted(name for name in changed if name not in R2_ALLOWED_CHANGES)
            if missing:
                problems.append(f"本轮保护基线缺失 {len(missing)} 项：{missing[:5]}")
            if unexpected:
                problems.append(f"本轮保护预期外变化：{unexpected[:5]}")
            frozen_mismatch = []
            for rel_path, want in R2_FROZEN.items():
                path = PROJECT_ROOT / rel_path
                got = sha256(path) if path.is_file() else None
                if got != want:
                    frozen_mismatch.append(f"{rel_path}={got}")
            if frozen_mismatch:
                problems.append(f"冻结哈希不符：{frozen_mismatch[:3]}")
            if read_errors:
                problems.append(f"保护扫描读取错误 {read_errors} 个文件")
            scan_path = save_json(container / "protected_scan.json", scan)
            save_json(container / "probe_records" / "r2_protection.json", {
                "mode": mode_label, "executed": True, "baseline": str(R2_BASELINE),
                "baseline_sha256": R2_BASELINE_SHA, "baseline_entries": len(baseline_raw),
                "scanned_entries": len(scan), "scan_path": rel(scan_path),
                "changed": changed, "missing": missing, "unexpected_changes": unexpected,
                "allowed_changes": sorted(R2_ALLOWED_CHANGES), "frozen": R2_FROZEN,
                "read_errors": read_errors,
                "note": "本轮正确基线；changed 只能是本任务测试，宿主/指南/六件冻结哈希另核对。"})

        # --- 停止点（成功对照的 0007 与无 0008） ---
        stop_problems = []
        success_batches = [batch_parent / item["batch"] for item in scene_records_local
                           if (batch_parent / item["batch"]
                               / "workflow/checkpoints/0007.json").is_file()
                           and not (batch_parent / item["batch"]
                                    / "workflow/fact_packet/failure.json").is_file()]
        for batch_dir in sorted((item for item in batch_parent.iterdir() if item.is_dir())):
            names = sorted(p.name for p in (batch_dir / "workflow/checkpoints").iterdir()) \
                if (batch_dir / "workflow/checkpoints").is_dir() else []
            if "0008.json" in names:
                stop_problems.append(f"{batch_dir.name}: 不得存在 0008")
        for batch_dir in success_batches:
            checkpoint7, ok7 = load_json_if_parseable(batch_dir / "workflow/checkpoints/0007.json")
            checkpoint6, _ = load_json_if_parseable(batch_dir / "workflow/checkpoints/0006.json")
            if not ok7:
                stop_problems.append(f"{batch_dir.name}: 成功对照 0007 不可解析")
                continue
            state = (checkpoint7.get("workflow") or {}).get("state") or {}
            if checkpoint7.get("revision") != 7 or isinstance(checkpoint7.get("revision"), bool):
                stop_problems.append(f"{batch_dir.name}: 0007 revision 不是严格整数 7")
            if (checkpoint7.get("operation") or {}).get("kind") != "BUILD_FACT_PACKET":
                stop_problems.append(f"{batch_dir.name}: 0007 operation.kind 不是 BUILD_FACT_PACKET")
            if checkpoint7.get("previous_file_sha256") != sha256(
                    batch_dir / "workflow/checkpoints/0006.json"):
                stop_problems.append(f"{batch_dir.name}: previous_file_sha256 与 0006 实读不符")
            if not same_json(checkpoint7.get("workflow"), checkpoint6.get("workflow")):
                stop_problems.append(f"{batch_dir.name}: 0007 workflow 与 0006 不相等")
            if state.get("gate1_approval") is not None or state.get("gate2_approval") is not None:
                stop_problems.append(f"{batch_dir.name}: 真实批准必须为 null")
            if state.get("next_step_allowed") is not False:
                stop_problems.append(f"{batch_dir.name}: next_step_allowed 必须为 false")
        if stop_problems:
            problems.extend(stop_problems[:5])
        save_json(container / "probe_records" / "r2_stop_point.json", {
            "mode": mode_label, "success_batches": [item.name for item in success_batches],
            "problems": stop_problems})

        effective_failures = list(failures)
        if problems:
            effective_failures.append({"case": f"finalizer:{mode_label}",
                                       "problems": list(problems)})
        save_json(container / "checks.json", checks)
        save_json(container / "counts.json", counts)
        save_json(container / "cli_logs.json", cli_records)
        save_json(container / "api_records.json", api_records)
        save_json(container / "summary.json", {"mode": mode_label, "checks": checks,
                                               "failures": effective_failures,
                                               "counts": counts, "records": {
                                                   "cli": len(cli_records),
                                                   "api": len(api_records)},
                                               "ledger": rel(ledger_path),
                                               "registry": rel(registry_path)})
        return problems

    # ================================================================ R1 定点：最后一次控制器检查后 Gate2 磁盘变更
    if only == "late-controller":
        print("== R1 定点：最后一次直接控制器动作检查之后改 Gate2 磁盘字节（normalized 为主＋两项对照）")
        r1_problems: list = []
        r1_probes: list = []
        for target_rel in ("workflow/gate2/normalized.json", "workflow/gate2/load_report.json",
                           "workflow/gate2/artifacts.json"):
            tag = target_rel.split("/")[-1].replace(".json", "")
            name = f"r1_late_{tag}"
            target = chain_to_crosschecked(name, "C06b.xlsx")
            target_file = target / target_rel
            backup = target_file.read_bytes()
            before_tree = tree_hashes(target)
            real_action = host.CONTROLLER_MODULE.check_dev_action
            state = {"direct_calls": 0, "injected": False, "before": None, "after": None,
                     "controller_return_true": None, "tree_at_injection": None,
                     "tree_after_restore": None}

            def wrapped_action(workflow, action, *, current_bindings=None, _real=real_action,
                               _state=state, _file=target_file):
                result = _real(workflow, action, current_bindings=current_bindings)
                frame = sys._getframe(1)
                direct = (frame.f_code.co_name == "build_dev_fact_packet"
                          and action == host.CONTROLLER_MODULE.ACTION_SCREEN)
                if direct:
                    _state["direct_calls"] += 1
                if direct and _state["direct_calls"] == 2 and not _state["injected"]:
                    _state["controller_return_true"] = result.get("simulation_allowed") is True
                    _state["before"] = sha256(_file)
                    with open(_file, "ab") as handle:
                        handle.write(b"\n")
                    _state["after"] = sha256(_file)
                    _state["tree_at_injection"] = tree_hashes(target)
                    _state["injected"] = True
                return result

            host.CONTROLLER_MODULE.check_dev_action = wrapped_action
            counts["fault_injections"] += 1
            api_entry = record_api(f"{name}_build", host.build_dev_fact_packet, target,
                                   expect_exception=host.WorkflowHostBlocked)
            host.CONTROLLER_MODULE.check_dev_action = real_action
            failure, _ = load_json_if_parseable(target / "workflow/fact_packet/failure.json")
            revoked = run_cli(f"{name}_revoked_status", ["status", "--batch-dir", str(target)], 1)
            target_file.write_bytes(backup)
            after_restore = run_cli(f"{name}_restored_status", ["status", "--batch-dir", str(target)], 1)
            after_tree = tree_hashes(target)
            state["tree_after_restore"] = after_tree
            # 操作前已存在文件：注入期间只允许故意注入的目标变化
            injected_period_changed = sorted(
                path for path in before_tree
                if (state["tree_at_injection"] or {}).get(path) != before_tree.get(path))
            only_target_changed = injected_period_changed == [target_rel]
            # 恢复目标后：全部操作前文件必须不变（新 0007 与本层产物不属于操作前文件）
            restored_changed = sorted(path for path in before_tree
                                      if after_tree.get(path) != before_tree.get(path))
            untouched_ok = not restored_changed and only_target_changed
            ok = (api_entry["outcome"] == "raised"
                  and api_entry["exception_class"] == "WorkflowHostBlocked"
                  and state["direct_calls"] == 2
                  and state["injected"] is True
                  and state["controller_return_true"] is True
                  and state["before"] != state["after"]
                  and failure.get("target_exit_code") == 1
                  and failure.get("stage") == "fact_packet"
                  and target_rel in str(api_entry and (json.loads(
                      (container / api_entry["exception_path"]).read_text(encoding="utf-8"))
                      .get("message") or ""))
                  and revoked["exit_code"] == 1
                  and after_restore["exit_code"] == 1
                  and untouched_ok
                  and only_target_changed)
            if not ok:
                r1_problems.append(
                    f"{target_rel}: 不符 outcome={api_entry['outcome']} "
                    f"direct_calls={state['direct_calls']} injected={state['injected']} "
                    f"ctrl_true={state['controller_return_true']} "
                    f"failure_exit={failure.get('target_exit_code')} "
                    f"failure_stage={failure.get('stage')} revoked={revoked['exit_code']} "
                    f"restored={after_restore['exit_code']} untouched={untouched_ok}")
            message = ""
            if api_entry["exception_path"]:
                message = json.loads((container / api_entry["exception_path"])
                                     .read_text(encoding="utf-8"))["message"]
            save_json(container / "probe_records" / f"r1_late_{tag}.json", {
                "case": f"r1_late_{tag}", "batch_dir": str(target), "target_relative": target_rel,
                "injection": {"direct_controller_calls": state["direct_calls"],
                              "injected_at": 2 if state["injected"] else None,
                              "controller_returned_true": state["controller_return_true"],
                              "before_sha256": state["before"], "after_sha256": state["after"],
                              "only_change": target_rel},
                "api_record": api_entry, "message_untruncated": message,
                "failure": failure,
                "revoked_status_exit": revoked["exit_code"],
                "status_after_restore_exit": after_restore["exit_code"],
                "old_files_unchanged_after_restore": untouched_ok,
                "injected_period_changed_files": injected_period_changed,
                "restored_period_changed_files": restored_changed,
                "note": "只包装真实 check_dev_action：先调用原实现，在其直接调用方为 "
                        "build_dev_fact_packet 且第二次（写后最后一次动作检查）真实返回之后，"
                        "给目标 Gate2 文件追加一个 LF，原返回对象原样交回；不同步任何哈希。"
                        "只恢复原件不清除有效失败事实（仍退出 1）。"})
            r1_probes.append({"target": target_rel, "ok": ok,
                              "direct_calls": state["direct_calls"]})
        # 正常未注入对照（新批次）：公开构建与新进程 status 均成功
        normal = chain_to_crosschecked("r1_normal_control", "C06b.xlsx")
        normal_state = build_and_capture("r1_normal_control", normal, 0)
        normal_status = run_cli("r1_normal_control_status", ["status", "--batch-dir", str(normal)], 0)
        normal_return = (json.loads((container / normal_state["return_path"]).read_text(
            encoding="utf-8")) if normal_state["return_path"] else None)
        normal_packet_path = normal / "workflow/fact_packet/fact_packet.json"
        normal_markdown_path = normal / "workflow/fact_packet/fact_packet.md"
        normal_packet, normal_packet_ok = load_json_if_parseable(normal_packet_path)
        normal_markdown = normal_markdown_path.read_bytes() if normal_markdown_path.is_file() else b""
        if normal_state["api_entry"]["outcome"] != "returned" or normal_status["exit_code"] != 0:
            r1_problems.append("未注入的正常对照批次未成功")
        if normal_state["calls"] != 1:
            r1_problems.append(f"正常对照真实核心调用不是 1 次：{normal_state['calls']}")
        if normal_return is None or not normal_packet_ok \
                or not same_json(normal_packet, normal_return["packet"]):
            r1_problems.append("正常对照落盘 packet 与本次真实返回不严格规范 JSON 相等")
        if normal_return is not None:
            if canonical_sha256(normal_return["packet"]) != normal_return["packet_sha256"]:
                r1_problems.append("正常对照核心返回的 packet_sha256 不等于 packet 规范指纹")
            if normal_markdown != normal_return["markdown"].encode("utf-8"):
                r1_problems.append("正常对照 Markdown 字节不等于返回字符串的 UTF-8 字节")
        if normal_state["before"] != normal_state["after_core"] \
                or normal_state["before"] != normal_state["after_public"]:
            r1_problems.append("正常对照三输入在调用前/核心返回后/公开返回后指纹不一致")
        save_json(container / "probe_records" / "r2_normal_control.json", {
            "case": "r2_normal_control", "batch_dir": str(normal),
            "core_return_path": normal_state["return_path"], "core_calls": normal_state["calls"],
            "packet_file_sha256": sha256(normal_packet_path),
            "packet_sha256": canonical_sha256(normal_packet) if normal_packet_ok else None,
            "packet_sha256_from_core": (normal_return or {}).get("packet_sha256"),
            "markdown_file_sha256": sha256(normal_markdown_path),
            "markdown_bytes": len(normal_markdown),
            "markdown_equals_return_utf8": normal_return is not None
            and normal_markdown == normal_return["markdown"].encode("utf-8"),
            "input_fingerprints": {"before": normal_state["before"],
                                   "after_core": normal_state["after_core"],
                                   "after_public": normal_state["after_public"]},
            "status_exit": normal_status["exit_code"],
            "note": "正常对照：真实核心恰 1 次；完整返回单份保存并与落盘 packet 严格相等；"
                    "Markdown 精确等于返回字符串 UTF-8 字节；三输入三时点指纹一致。"})
        # 守卫下的只读 status 仍成功（五个下游函数命中 0）
        guard = {name: 0 for name in DOWNSTREAM_GUARDS}
        guards = {}
        for name in DOWNSTREAM_GUARDS:
            module = {"normalize_workbook": host.NORMALIZER_MODULE,
                      "load_normalized_to_sqlite": host.STORE_MODULE,
                      "screen_sqlite": host.SCREEN_MODULE,
                      "verify_rule_facts": host.CROSSCHECK_MODULE,
                      "build_fact_packet": host.FACT_PACKET_MODULE}[name]
            guards[name] = (module, name, getattr(module, name))

            def forbidden(*_args, _name=name, **_kwargs):
                guard[_name] += 1
                raise AssertionError(f"status 不得调用下游核心 {_name}")

            setattr(module, name, forbidden)
        readonly_api = record_api("r1_readonly_status", host.inspect_dev_batch, normal)
        for name, (module, attr, original) in guards.items():
            setattr(module, attr, original)
        if readonly_api["outcome"] != "returned" or any(value != 0 for value in guard.values()):
            r1_problems.append(f"守卫下只读 status 未成功或触达下游核心：{guard}")
        save_json(container / "probe_records" / "r1_late_controller_summary.json", {
            "case": "r1_late_controller_summary", "probes": r1_probes,
            "normal_control": {"batch_dir": str(normal),
                               "api_outcome": normal_state["api_entry"]["outcome"],
                               "core_calls": normal_state["calls"],
                               "status_exit": normal_status["exit_code"]},
            "readonly_guard": {"api_record": readonly_api, "guard_hits": guard},
            "note": "受影响范围定点：最后一次直接控制器动作检查之后的 Gate2 磁盘变更本次即拒绝；"
                    "另附未注入正常对照与守卫下只读 status。"})
        record("R1_LATE_CONTROLLER_GATE2_DISK_RECHECK", "host", r1_problems, probes=r1_probes)
        finalizer_problems = finalize_evidence("late-controller", r1_probes)
        record("R2_EVIDENCE_FINALIZER", "evidence", finalizer_problems,
               modes="late-controller", cli_records=len(cli_records),
               api_records=len(api_records))
        print(f"定点模式 only=late-controller：{len(checks)} 项检查、{len(failures)} 项失败；"
              f"missing={counts.get('missing_records')} "
              f"unregistered={counts.get('unregistered_records')}")
        return 1 if failures else 0

    # ================================================================ G1 MAIN
    if only in ("all", "main", "smoke"):
        print("== G1 MAIN 正常接入（真实建链至 0007）")
        g1_problems: list = []
        main_batch = chain_to_gate2_decision("main_01", "", "APPROVE",
                                            workbook=GENERATED / "input" / "erp_export.xlsx")
        run_cli("main_01_screen", ["screen-rules", "--batch-dir", str(main_batch)], 0)
        run_cli("main_01_crosscheck", ["crosscheck-rules", "--batch-dir", str(main_batch)], 0)
        screen_report = json.loads((main_batch / "workflow/screening/screening_report.json")
                                   .read_text(encoding="utf-8"))
        distribution = {rule: sum(1 for item in screen_report["findings"]
                                  if item.get("rule_id") == rule)
                        for rule in ("R01", "R02", "R03", "R04")}
        if distribution != {"R01": 3, "R02": 5, "R03": 2, "R04": 2}:
            g1_problems.append(f"MAIN 筛查分布不符：{distribution}")
        if screen_report["statistics"]["r02_overpayment_total_cents"] != 1600000:
            g1_problems.append("MAIN R02 超额不是 1,600,000 分")
        state = build_and_capture("main_01", main_batch, 0, expect_exception=None)
        api_return = (json.loads((container / state["api_entry"]["return_path"]).read_text(
            encoding="utf-8")) if state["api_entry"]["return_path"] else {})
        real_return = (json.loads((container / state["return_path"]).read_text(encoding="utf-8"))
                       if state["return_path"] else None)
        packet_path = main_batch / "workflow/fact_packet/fact_packet.json"
        markdown_path = main_batch / "workflow/fact_packet/fact_packet.md"
        packet_on_disk = json.loads(packet_path.read_text(encoding="utf-8"))
        if state["calls"] != 1:
            g1_problems.append(f"底稿核心必须恰调用 1 次，实际 {state['calls']}")
        if real_return is None or not same_json(packet_on_disk, real_return["packet"]):
            g1_problems.append("落盘 packet 与该次真实返回的 packet 不严格规范 JSON 相等")
        if state["before"] != state["after_core"] or state["before"] != state["after_public"]:
            g1_problems.append(f"三输入指纹在核心调用前／返回后／公开返回后不一致："
                               f"{state['before']} / {state['after_core']} / {state['after_public']}")
        if real_return is not None:
            if canonical_sha256(real_return["packet"]) != real_return["packet_sha256"]:
                g1_problems.append("核心返回的 packet_sha256 不等于 packet 规范指纹")
            if real_return["packet_sha256"] != api_return.get("fact_packet", {}).get("packet_sha256"):
                g1_problems.append("API 摘要的 packet 规范指纹不等于核心返回")
        if markdown_path.is_file() and real_return is not None:
            markdown_bytes = markdown_path.read_bytes()
            if markdown_bytes != real_return["markdown"].encode("utf-8"):
                g1_problems.append("Markdown 磁盘字节不等于核心返回 markdown 的 UTF-8 字节")
            if markdown_bytes.startswith(b"\xef\xbb\xbf"):
                g1_problems.append("Markdown 不得带 BOM")
            if b"\r\n" in markdown_bytes:
                g1_problems.append("Markdown 必须使用 LF 换行")
        if packet_on_disk.get("batch_status") != "DEV_FACT_PACKET_READY":
            g1_problems.append("packet.batch_status 不是 DEV_FACT_PACKET_READY")
        card_count = len(packet_on_disk.get("findings") or [])
        if card_count != 12:
            g1_problems.append(f"packet findings 条数不是 12：{card_count}")
        if packet_on_disk["summary"]["rule_counts"] != distribution:
            g1_problems.append(f"packet 规则分布与筛查不一致：{packet_on_disk['summary']['rule_counts']}")
        # 逐卡比对：命中键、整数分、related_ids、source_rows
        screen_by_key = {}
        for finding in screen_report["findings"]:
            key = canonical_json(finding["hit_key"])
            screen_by_key.setdefault(key, []).append(finding)
        for card in packet_on_disk.get("findings") or []:
            key = canonical_json(card.get("hit_key") or (card.get("evidence") or {}).get("hit_key"))
            source = screen_by_key.get(key)
            if not source:
                g1_problems.append(f"packet 卡片命中键在筛查报告中不存在：{key[:80]}")
                continue
            baseline = source[0]
            card_amounts = card.get("amounts_cents") or {}
            for field, value in (baseline.get("amounts_cents") or {}).items():
                if card_amounts.get(field) != value:
                    g1_problems.append(f"卡片 {key[:40]} 的 {field} 与筛查不一致："
                                       f"{card_amounts.get(field)!r} != {value!r}")
            for field in ("related_ids", "source_rows"):
                if field in baseline and card.get(field) != baseline.get(field):
                    g1_problems.append(f"卡片 {key[:40]} 的 {field} 与筛查不一致")
        checkpoint7 = json.loads((main_batch / "workflow/checkpoints/0007.json")
                                 .read_text(encoding="utf-8"))
        checkpoint6 = json.loads((main_batch / "workflow/checkpoints/0006.json")
                                 .read_text(encoding="utf-8"))
        if checkpoint7["revision"] != 7 or isinstance(checkpoint7["revision"], bool):
            g1_problems.append("0007 revision 必须是严格整数 7")
        if checkpoint7["operation"]["kind"] != "BUILD_FACT_PACKET":
            g1_problems.append("0007 operation.kind 不是 BUILD_FACT_PACKET")
        if checkpoint7["previous_file_sha256"] != sha256(
                main_batch / "workflow/checkpoints/0006.json"):
            g1_problems.append("0007 previous_file_sha256 不等于 0006 实读字节哈希")
        if not same_json(checkpoint7["workflow"], checkpoint6["workflow"]):
            g1_problems.append("0007 workflow 与 0006 不严格相等")
        if api_return.get("fact_packet_status") != "FACT_PACKET_RECORDED":
            g1_problems.append("API fact_packet_status 不是 FACT_PACKET_RECORDED")
        if api_return.get("phase") != "DEV_GATE2_APPROVED" or api_return.get("real_approvals") != 0:
            g1_problems.append("API phase／real_approvals 不符")
        counts["facts_built_in_flow"] += 1
        save_json(container / "probe_records" / "g1_main_fact_packet.json", {
            "case": "g1_main_fact_packet", "batch_dir": str(main_batch),
            "api_record": state["api_entry"], "core_return_path": state["return_path"],
            "core_calls": state["calls"], "distribution": distribution,
            "packet_file_sha256": sha256(packet_path),
            "packet_sha256": canonical_sha256(packet_on_disk),
            "packet_sha256_from_core": (real_return or {}).get("packet_sha256"),
            "markdown_file_sha256": sha256(markdown_path),
            "markdown_bytes": markdown_path.stat().st_size,
            "input_fingerprints": {"before": state["before"], "after_core": state["after_core"],
                                   "after_public": state["after_public"]},
            "findings_total": card_count, "rule_counts": packet_on_disk["summary"]["rule_counts"],
            "checkpoint7": {"revision": checkpoint7["revision"],
                            "kind": checkpoint7["operation"]["kind"],
                            "previous_file_sha256": checkpoint7["previous_file_sha256"]},
            "note": "底稿核心真实调用一次；落盘 packet 与该次真实返回严格规范 JSON 相等；"
                    "Markdown 精确等于返回 markdown 的 UTF-8 字节；三输入三类时点指纹一致。"})
        record("G1_MAIN_FACT_PACKET", "flow", g1_problems,
               distribution=distribution, core_calls=state["calls"])

    # ================================================================ G2 小样与合法阶段
    if only in ("all", "samples", "smoke"):
        print("== G2 小样与合法阶段")
        g2_problems: list = []
        samples = {}
        for name, fixture, expectations in (
                ("g2_c06b", "C06b.xlsx", {"findings": 1, "paid_total": 1000000,
                                          "refund_total": 100000, "net_total": 900000,
                                          "overpayment": 400000}),
                ("g2_c03", "C03.xlsx", {"findings": 0}),
                ("g2_c07b", "C07b.xlsx", {"has_r03": True})):
            target = chain_to_crosschecked(name, fixture)
            state = build_and_capture(name, target, 0)
            packet = json.loads((target / "workflow/fact_packet/fact_packet.json")
                                .read_text(encoding="utf-8"))
            markdown = (target / "workflow/fact_packet/fact_packet.md").read_text(encoding="utf-8")
            ok = state["api_entry"]["outcome"] == "returned" and state["calls"] == 1
            if expectations.get("findings") is not None:
                if len(packet["findings"]) != expectations["findings"]:
                    g2_problems.append(f"{name} findings 数 {len(packet['findings'])} != "
                                       f"{expectations['findings']}")
                    ok = False
                if expectations["findings"] == 0:
                    if "未命中" not in markdown:
                        g2_problems.append(f"{name} 无线索正文缺少固定未命中限制文案")
                        ok = False
            if expectations.get("paid_total"):
                amounts = (packet["findings"][0].get("amounts_cents") or {})
                for field in ("paid_total", "refund_total", "net_total", "overpayment"):
                    if amounts.get(field) != expectations[field]:
                        g2_problems.append(f"{name} {field} 不符：{amounts.get(field)} != "
                                           f"{expectations[field]}")
                        ok = False
            if expectations.get("has_r03"):
                rule_ids = {item.get("rule_id") for item in packet["findings"]}
                if "R03" not in rule_ids:
                    g2_problems.append(f"{name} 缺少 R03 线索")
                    ok = False
            samples[name] = {"batch_dir": str(target), "findings": len(packet["findings"]),
                             "rule_counts": packet["summary"]["rule_counts"],
                             "markdown_bytes": len(markdown.encode("utf-8")),
                             "outcome": state["api_entry"]["outcome"]}
            # 只读恢复 0001—0007
            status = run_cli(f"{name}_status", ["status", "--batch-dir", str(target)], 0)
            if (status["return_object"] or {}).get("fact_packet_status") != "FACT_PACKET_RECORDED":
                g2_problems.append(f"{name} status 未显示 FACT_PACKET_RECORDED")
            counts["facts_built_in_flow"] += 1
        # 0005 过早 build 拒绝（真实完整链但未复算）
        early_target = chain_to_screened("g2_early", "C06b.xlsx")
        early = run_cli("g2_early_build", ["build-fact-packet", "--batch-dir", str(early_target)], 1)
        if (early_target / "workflow/fact_packet").exists():
            g2_problems.append("0005 过早 build 产生了事实底稿现场")
        # 0007 重复拒绝
        repeat_target = batch_parent / "g2_c06b"
        repeat = run_cli("g2_repeat_build", ["build-fact-packet", "--batch-dir",
                                             str(repeat_target)], 1)
        # HOLD 对照
        hold_target = chain_to_gate2_decision("g2_hold", "C06b.xlsx", "HOLD")
        before_tree = tree_hashes(hold_target)
        hold = run_cli("g2_hold_build", ["build-fact-packet", "--batch-dir", str(hold_target)], 1)
        after_tree = tree_hashes(hold_target)
        if before_tree != after_tree or (hold_target / "workflow/fact_packet").exists():
            g2_problems.append("HOLD 对照现场发生变化或产生了事实底稿目录")
        save_json(container / "probe_records" / "g2_samples_and_stages.json", {
            "case": "g2_samples_and_stages", "samples": samples,
            "early": {"batch_dir": str(early_target), "exit_code": early["exit_code"],
                      "message": (early["return_object"] or {}).get("message")},
            "repeat": {"batch_dir": str(repeat_target), "exit_code": repeat["exit_code"],
                       "message": (repeat["return_object"] or {}).get("message")},
            "hold": {"batch_dir": str(hold_target), "exit_code": hold["exit_code"],
                     "tree_unchanged": before_tree == after_tree}})
        record("G2_SAMPLES_AND_LEGAL_STAGES", "flow", g2_problems, samples=list(samples))

    if only == "smoke":
        counts["ledger_audit_executed"] = None
        counts["protection_scan_executed"] = None
        save_json(container / "summary.json", {
            "mode": "smoke", "checks": checks, "failures": failures, "counts": counts,
            "not_executed": ["evidence_ledger_audit", "call_registry_save",
                             "scene_outcomes_export", "protection_comparison",
                             "isolation_self_test"],
            "note": "smoke 模式未执行证据收尾与保护比较；missing/unregistered/受保护结果均为 null，"
                    "不填未测得的 0。"})
        print(f"冒烟模式：{len(checks)} 项检查、{len(failures)} 项失败"
              "（未执行证据收尾与保护比较：missing/unregistered=null）")
        return 1 if failures else 0

    # ================================================================ G3 前提与接口拒绝
    if only in ("all", "premise"):
        print("== G3 前提与接口拒绝")
        g3_problems: list = []
        # 真实 MISMATCH 造样后 build 必须退出 1、底稿 0、无本层目录/0007
        mismatch_target = chain_to_screened("g3_mismatch", "C06b.xlsx", tamper=True)
        mismatch = run_cli("g3_mismatch_crosscheck",
                           ["crosscheck-rules", "--batch-dir", str(mismatch_target)], 1)
        tamper = tamper_records[-1]
        mismatch_build = run_cli("g3_mismatch_build",
                                 ["build-fact-packet", "--batch-dir", str(mismatch_target)], 1)
        if (mismatch_target / "workflow/fact_packet").exists():
            g3_problems.append("MISMATCH 批次产生了事实底稿现场")
        if (mismatch_target / "workflow/checkpoints/0007.json").exists():
            g3_problems.append("MISMATCH 批次产生了 0007")
        counts["core_observations"].setdefault("build_fact_packet_on_mismatch", 0)
        # 错误 packet_sha256 协议探针
        probe_target = chain_to_crosschecked("g3_probe", "C06b.xlsx")
        real_core = host.FACT_PACKET_MODULE.build_fact_packet
        polluted = {"changed": False}

        def polluted_core(normalized, screening_report, crosscheck_report):
            result = real_core(normalized, screening_report, crosscheck_report)
            counts["core_observations"]["build_fact_packet_inprocess"] += 1
            clone = copy.deepcopy(result)
            clone["packet_sha256"] = "0" * 64
            polluted["changed"] = True
            counts["fault_injections"] += 1
            return clone

        host.FACT_PACKET_MODULE.build_fact_packet = polluted_core
        try:
            probe_api = record_api("g3_probe_build_fact_packet", host.build_dev_fact_packet,
                                   probe_target, expect_exception=host.WorkflowHostBlocked)
        finally:
            host.FACT_PACKET_MODULE.build_fact_packet = real_core
        failure_path = probe_target / "workflow/fact_packet/failure.json"
        probe_failure, _ = load_json_if_parseable(failure_path)
        if probe_api["outcome"] != "raised":
            g3_problems.append("错误 packet_sha256 探针未被拒绝")
        if (probe_target / "workflow/checkpoints/0007.json").exists():
            g3_problems.append("协议探针产生了成功凭证 0007")
        if not probe_failure:
            g3_problems.append("协议探针未留下正确诊断")
        # FactPacketBlocked / FactPacketError 宿主映射注入
        for label, exc_class, expect_exit, expect_host in (
                ("blocked", "FactPacketBlocked", 1, "WorkflowHostBlocked"),
                ("error", "FactPacketError", 2, "WorkflowHostError")):
            inject_target = chain_to_crosschecked(f"g3_inject_{label}", "C06b.xlsx")
            real_core = host.FACT_PACKET_MODULE.build_fact_packet

            def raising_core(normalized, screening_report, crosscheck_report, _cls=exc_class,
                             _label=label):
                counts["fault_injections"] += 1
                core_exc = getattr(host.FACT_PACKET_MODULE, _cls)
                raise core_exc(f"T15 注入的 {_cls}（宿主映射探针，非真实核心业务失败）")

            host.FACT_PACKET_MODULE.build_fact_packet = raising_core
            try:
                inject_api = record_api(f"g3_inject_{label}_build", host.build_dev_fact_packet,
                                        inject_target,
                                        expect_exception=(host.WorkflowHostBlocked if expect_exit == 1
                                                          else host.WorkflowHostError))
            finally:
                host.FACT_PACKET_MODULE.build_fact_packet = real_core
            inject_failure, _ = load_json_if_parseable(
                inject_target / "workflow/fact_packet/failure.json")
            ok = (inject_api["outcome"] == "raised"
                  and inject_api["exception_class"] == expect_host
                  and inject_failure.get("target_exit_code") == expect_exit
                  and inject_failure.get("stage") == "fact_packet"
                  and any(link.get("class") == exc_class
                          for link in inject_failure.get("exception_chain") or []))
            if not ok:
                g3_problems.append(f"{label} 映射注入不符：{inject_api['exception_class']} "
                                   f"exit={(inject_failure or {}).get('target_exit_code')} "
                                   f"chain={[link.get('class') for link in (inject_failure or {}).get('exception_chain') or []]}")
            counts["fact_packet_failure_scenes"] += 1
        counts["fact_packet_failure_scenes"] += 1  # 协议探针现场
        save_json(container / "probe_records" / "g3_premise_and_protocol.json", {
            "case": "g3_premise_and_protocol",
            "mismatch": {"batch_dir": str(mismatch_target), "changed_fact": tamper["changed"],
                         "crosscheck_exit": mismatch["exit_code"],
                         "build_exit": mismatch_build["exit_code"],
                         "message": (mismatch_build["return_object"] or {}).get("message"),
                         "fact_packet_dir_created":
                             (mismatch_target / "workflow/fact_packet").exists()},
            "protocol_probe": {"batch_dir": str(probe_target),
                               "injection": "真实 builder 返回后复制并只改 packet_sha256（测试污染）",
                               "api_record": probe_api, "failure": probe_failure},
            "mapping_injection": "FactPacketBlocked／FactPacketError 由宿主映射注入，"
                                 "不冒称是假数据触发的真实核心业务失败"})
        record("G3_PREMISE_AND_PROTOCOL_REJECTION", "flow", g3_problems,
               changed_fact=tamper["changed"])

    # ================================================================ G4 有限持久化故障
    if only in ("all", "persistence"):
        print("== G4 有限持久化故障（0007 真实 writer）")
        g4_problems: list = []
        g4_probes: list = []
        for label, mode in (("partial", "partial"), ("throw", "throw")):
            target = chain_to_crosschecked(f"g4_{label}", "C06b.xlsx")
            before = tree_hashes(target)
            sentinel = f"SENTINEL-T15-{label.upper()}-0007"
            real_open = open
            state = {"target": (target / "workflow/checkpoints/0007.json").resolve(),
                     "open_calls": 0, "target_open": 0, "target_mode": None, "target_newline": None,
                     "write_hits": 0, "text": None, "text_bytes": None, "partial_bytes": None,
                     "written_sha256": None}

            if mode == "partial":
                class _ObservedHandle:
                    def __init__(self, handle, _state=state):
                        self._handle = handle

                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc, tb):
                        self._handle.close()
                        return False

                    def write(self, text_str, _state=state):
                        if Path(getattr(self._handle, "name", "")).resolve() == _state["target"]:
                            _state["write_hits"] += 1
                            encoded = text_str.encode("utf-8")
                            _state["text"] = text_str
                            _state["text_bytes"] = encoded
                            partial = encoded[: max(1, len(encoded) // 2)]
                            self._handle.write(partial.decode("utf-8"))
                            _state["partial_bytes"] = len(partial)
                            raise OSError("T15 注入的 0007 写入 I/O 故障（半写现场保留）")
                        return self._handle.write(text_str)

                    def __getattr__(self, name):
                        return getattr(self._handle, name)

                def observed_open(file, open_mode="r", *open_args, _state=state, _real=real_open,
                                  **open_kwargs):
                    _state["open_calls"] += 1
                    handle = _real(file, open_mode, *open_args, **open_kwargs)
                    try:
                        resolved = Path(getattr(handle, "name", file)).resolve()
                    except (OSError, TypeError):
                        return handle
                    if resolved != _state["target"]:
                        return handle
                    _state["target_open"] += 1
                    _state["target_mode"] = open_mode
                    _state["target_newline"] = open_kwargs.get("newline")
                    return _ObservedHandle(handle)

                host.__builtins__["open"] = observed_open
            else:
                real_writer = host._write_exclusive_json

                def writer_then_sentinel(path, payload, stage, _real=real_writer, _state=state,
                                         _sentinel=sentinel):
                    sha = _real(path, payload, stage)
                    if Path(path).resolve() == _state["target"]:
                        _state["written_sha256"] = sha
                        with real_open(path, "rb") as handle:
                            _state["text_bytes"] = handle.read()
                        _state["write_hits"] = 1
                        raise RuntimeError(_sentinel)
                    return sha

                host._write_exclusive_json = writer_then_sentinel

            counts["fault_injections"] += 1
            try:
                state_api = build_and_capture(f"g4_{label}", target, 2,
                                              expect_exception=host.WorkflowHostError)
            finally:
                host.__builtins__["open"] = real_open
                if mode == "throw":
                    host._write_exclusive_json = real_writer
            after = tree_hashes(target)
            old_changed = sorted(path for path in before if before[path] != after.get(path))
            old_unchanged = all(before.get(path) == after.get(path) for path in before
                                if path.startswith("workflow/checkpoints/")
                                and not path.endswith("0007.json"))
            failure, _ = load_json_if_parseable(target / "workflow/fact_packet/failure.json")
            recovery = run_cli(f"g4_{label}_recovery_status", ["status", "--batch-dir",
                                                               str(target)], 2)
            pending_path = container / "core_returns" / f"g4_{label}_pending_0007.json"
            if state["text_bytes"] is not None:
                with real_open(pending_path, "wb") as handle:
                    handle.write(state["text_bytes"])
            pending_readback = pending_path.read_bytes() if pending_path.is_file() else b""
            pending_matches = (state["text_bytes"] is not None
                               and pending_readback == state["text_bytes"])
            boundary = max(1, len(state["text_bytes"] or b"") // 2)
            expected_partial = (state["text_bytes"] or b"")[:boundary]
            actual_partial = state["target"].read_bytes() if state["target"].is_file() else b""
            partial_matches = (actual_partial == expected_partial) if mode == "partial" else None
            ok = (state_api["api_entry"]["outcome"] == "raised"
                  and state_api["api_entry"]["exception_class"] == "WorkflowHostError"
                  and recovery["exit_code"] == 2
                  and failure.get("target_exit_code") == 2
                  and failure.get("stage") == "fact_packet"
                  and state["write_hits"] == 1
                  and pending_matches
                  and old_unchanged
                  and any(link.get("class") in ("OSError", "RuntimeError")
                          for link in failure.get("exception_chain") or []))
            if mode == "partial":
                # 注意：必须是真实换行符 "\n"（一个字符），不能用两字符的 "\\n"
                ok = ok and state["target_open"] == 1 and state["target_mode"] == "x" \
                    and state["target_newline"] == "\n" and partial_matches
                if state["target"].is_file():
                    counts["half_written_vouchers"] += 1
            else:
                ok = ok and sentinel in canonical_json(failure)
            if not ok:
                g4_problems.append(
                    f"{label}: 诊断 outcome={state_api['api_entry']['outcome']} "
                    f"exc={state_api['api_entry']['exception_class']} "
                    f"recovery={recovery['exit_code']} fexit={failure.get('target_exit_code')} "
                    f"stage={failure.get('stage')} hits={state['write_hits']} "
                    f"pending={pending_matches} old={old_unchanged} partial={partial_matches} "
                    f"open={state['target_open']} mode={state['target_mode']!r} "
                    f"nl={state['target_newline']!r} "
                    f"chain={[l.get('class') for l in failure.get('exception_chain') or []]} :: "
                    f"orig outcome={state_api['api_entry']['outcome']} "
                    f"target_open={state['target_open']} mode={state['target_mode']!r} "
                    f"write_hits={state['write_hits']} pending={pending_matches} "
                    f"partial={partial_matches} recovery={recovery['exit_code']} "
                    f"failure_exit={failure.get('target_exit_code')} "
                    f"chain={[link.get('class') for link in failure.get('exception_chain') or []]}")
            save_json(container / "probe_records" / f"g4_{label}_persistence.json", {
                "case": f"g4_{label}", "batch_dir": str(target), "mode": mode,
                "real_writer": {"target_open_calls": state["target_open"],
                                "total_open_calls": state["open_calls"],
                                "open_mode": state["target_mode"],
                                "open_newline": state["target_newline"],
                                "write_hits": state["write_hits"],
                                "written_sha256": state["written_sha256"]},
                "pending_full_text": {"path": rel(pending_path),
                                      "file_bytes": pending_path.stat().st_size
                                      if pending_path.is_file() else None,
                                      "buffer_bytes": len(state["text_bytes"] or b""),
                                      "file_sha256": sha256(pending_path)
                                      if pending_path.is_file() else None,
                                      "buffer_sha256": hashlib.sha256(
                                          state["text_bytes"] or b"").hexdigest(),
                                      "reread_matches_buffer": pending_matches},
                "half_written": {"expected_partial_bytes": len(expected_partial),
                                 "actual_bytes_on_disk": len(actual_partial),
                                 "matches": partial_matches},
                "api_record": state_api["api_entry"], "failure": failure,
                "recovery_cli": {"exit_code": recovery["exit_code"],
                                 "payload": recovery["return_object"]},
                "old_files_changed": old_changed, "old_unchanged": old_unchanged,
                "sentinel": sentinel if mode == "throw" else None})
            g4_probes.append({"case": f"g4_{label}", "ok": ok,
                              "recovery_exit": recovery["exit_code"]})
            counts["fact_packet_failure_scenes"] += 1
        record("G4_PERSISTENCE_FAULTS", "flow", g4_problems, probes=g4_probes)

    # ================================================================ G5 晚变更与固定引用
    if only in ("all", "late"):
        print("== G5 晚变更与固定引用")
        g5_problems: list = []
        late_target = chain_to_crosschecked("g5_late", "C06b.xlsx")
        state = build_and_capture("g5_late", late_target, 0)
        markdown_path = late_target / "workflow/fact_packet/fact_packet.md"
        markdown_backup = markdown_path.read_bytes()
        real_reader = host._read_fact_packet_outputs
        read_index = {"n": 0}
        observed_sequence: list = []

        def tracing_reader(batch_dir, stage, _real=real_reader):
            outputs = _real(batch_dir, stage)
            read_index["n"] += 1
            observed_sequence.append({"return_index": read_index["n"], "stage": stage,
                                      "caller": caller_names(4, sys._getframe(1)),
                                      "markdown_file_sha256_at_return": sha256(markdown_path)})
            return outputs

        host._read_fact_packet_outputs = tracing_reader
        baseline_api = record_api("g5_baseline_status", host.inspect_dev_batch, late_target)
        host._read_fact_packet_outputs = real_reader
        last_index = read_index["n"]
        injected = {"done": False, "at": None, "before": None, "after": None,
                    "returned_object_sha256": None}
        current = {"n": 0}

        def injecting_reader(batch_dir, stage, _real=real_reader):
            outputs = _real(batch_dir, stage)
            current["n"] += 1
            if current["n"] == last_index and not injected["done"]:
                injected["returned_object_sha256"] = canonical_sha256(outputs["packet"])
                injected["before"] = sha256(markdown_path)
                if markdown_path.read_bytes().endswith(b"\n"):
                    markdown_path.write_bytes(markdown_path.read_bytes()[:-1] + b"X\n")
                else:
                    markdown_path.write_bytes(markdown_path.read_bytes() + b"X\n")
                injected["after"] = sha256(markdown_path)
                injected["done"] = True
                injected["at"] = current["n"]
            return outputs

        host._read_fact_packet_outputs = injecting_reader
        injection_api = record_api("g5_late_injection_status", host.inspect_dev_batch, late_target,
                                   expect_exception=host.WorkflowHostBlocked)
        host._read_fact_packet_outputs = real_reader
        revoked = run_cli("g5_revoked_status", ["status", "--batch-dir", str(late_target)], 1)
        markdown_path.write_bytes(markdown_backup)
        restored = run_cli("g5_restored_status", ["status", "--batch-dir", str(late_target)], 0)
        late_ok = (injection_api["outcome"] == "raised"
                   and injection_api["exception_class"] == "WorkflowHostBlocked"
                   and injected["done"] and injected["at"] == last_index
                   and injected["before"] != injected["after"]
                   and revoked["exit_code"] == 1 and restored["exit_code"] == 0)
        if not late_ok:
            g5_problems.append(f"晚变更未在本次调用被拒：outcome={injection_api['outcome']} "
                               f"at={injected['at']}/{last_index} revoked={revoked['exit_code']} "
                               f"restored={restored['exit_code']}")
        # 只改 0007.operation 的固定 Markdown 路径
        path_target = batch_parent / "g5_late"
        cp7 = path_target / "workflow/checkpoints/0007.json"
        backup7 = cp7.read_bytes()
        payload7 = json.loads(backup7.decode("utf-8"))
        original_relative = payload7["operation"]["markdown_relative"]
        payload7["operation"]["markdown_relative"] = "workflow/fact_packet/not_the_markdown.md"
        cp7.write_text(json.dumps(payload7, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts["fault_injections"] += 1
        path_status = run_cli("g5_path_status", ["status", "--batch-dir", str(path_target)], 1)
        path_message = (path_status["return_object"] or {}).get("message") or ""
        cp7.write_bytes(backup7)
        path_restored = run_cli("g5_path_restored", ["status", "--batch-dir", str(path_target)], 0)
        if "markdown_relative" not in path_message or path_restored["exit_code"] != 0:
            g5_problems.append(f"固定 Markdown 路径反例未指向字段：{path_message[:160]}")
        # 改 started 中的一个输入规范指纹
        started_path = path_target / "workflow/fact_packet/started.json"
        started_backup = started_path.read_bytes()
        started = json.loads(started_backup.decode("utf-8"))
        started["normalized_payload_sha256"] = "0" * 64
        started_path.write_text(json.dumps(started, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
        counts["fault_injections"] += 1
        started_status = run_cli("g5_started_status", ["status", "--batch-dir", str(path_target)], 1)
        started_message = (started_status["return_object"] or {}).get("message") or ""
        started_path.write_bytes(started_backup)
        started_restored = run_cli("g5_started_restored", ["status", "--batch-dir",
                                                           str(path_target)], 0)
        if "normalized_payload_sha256" not in started_message or started_restored["exit_code"] != 0:
            g5_problems.append(f"started 输入指纹反例未指向字段：{started_message[:160]}")
        save_json(container / "probe_records" / "g5_late_change_and_paths.json", {
            "case": "g5_late_change_and_paths", "batch_dir": str(path_target),
            "baseline_sequence": observed_sequence, "last_reader_index": last_index,
            "injection": injected, "injection_api": injection_api,
            "revoked_cli_exit": revoked["exit_code"], "restored_cli_exit": restored["exit_code"],
            "markdown_path_rejection": {"original_relative": original_relative,
                                        "changed_relative":
                                            payload7["operation"]["markdown_relative"],
                                        "exit_code": path_status["exit_code"],
                                        "message": path_message,
                                        "restored_exit": path_restored["exit_code"]},
            "started_fingerprint_rejection": {"exit_code": started_status["exit_code"],
                                              "message": started_message,
                                              "restored_exit": started_restored["exit_code"]},
            "note": "先无注入实测真实读取位置，再在最后一次用于底稿摘要的读取返回原对象后单次改 "
                    "fact_packet.md；本次 API 即拒绝，撤销后 CLI 仍拒绝，恢复原件后成功。"})
        record("G5_LATE_CHANGE_AND_FIXED_REFERENCES", "flow", g5_problems,
               last_reader_index=last_index)

    # ================================================================ G6 只读/隔离与输入不变
    if only in ("all", "readonly"):
        print("== G6 只读／隔离与输入不变")
        g6_problems: list = []
        readonly_target = batch_parent / "g5_late"
        guard = {name: 0 for name in DOWNSTREAM_GUARDS}
        guards = {}
        for name in DOWNSTREAM_GUARDS:
            module = {"normalize_workbook": host.NORMALIZER_MODULE,
                      "load_normalized_to_sqlite": host.STORE_MODULE,
                      "screen_sqlite": host.SCREEN_MODULE,
                      "verify_rule_facts": host.CROSSCHECK_MODULE,
                      "build_fact_packet": host.FACT_PACKET_MODULE}[name]
            if not hasattr(module, name):
                g6_problems.append(f"待禁用的下游函数不存在：{name}")
                continue
            guards[name] = (module, name, getattr(module, name))

            def forbidden(*_args, _name=name, **_kwargs):
                guard[_name] += 1
                raise AssertionError(f"status 不得调用下游核心 {_name}")

            setattr(module, name, forbidden)
        before_tree = tree_hashes(readonly_target)
        readonly_api = record_api("g6_readonly_status_inprocess", host.inspect_dev_batch,
                                  readonly_target)
        after_tree = tree_hashes(readonly_target)
        for name, (module, attr, original) in guards.items():
            setattr(module, attr, original)
        if readonly_api["outcome"] != "returned":
            g6_problems.append(f"同进程只读 status 未成功：{readonly_api['exception_class']}")
        if any(value != 0 for value in guard.values()):
            g6_problems.append(f"只读 status 触达了下游核心：{guard}")
        if before_tree != after_tree:
            g6_problems.append("只读 status 改写了批次文件")
        cli_readonly = run_cli("g6_readonly_status_cli", ["status", "--batch-dir",
                                                          str(readonly_target)], 0)
        if cli_readonly["exit_code"] != 0:
            g6_problems.append("新进程只读 CLI 恢复未成功")
        db_path = sqlite_parent / readonly_target.name / "audit.sqlite3"
        db_sha = sha256(db_path)
        save_json(container / "probe_records" / "g6_readonly_and_inputs.json", {
            "case": "g6_readonly_and_inputs", "batch_dir": str(readonly_target),
            "same_process_readonly": {"api_record": readonly_api, "guarded": sorted(guards),
                                      "guard_hits": guard,
                                      "tree_unchanged": before_tree == after_tree},
            "cli_readonly": {"exit_code": cli_readonly["exit_code"]},
            "database_sha256": db_sha,
            "note": "五个真实下游函数在同进程内被替换为计数后抛错，公开 status 仍成功且命中全 0；"
                    "另作新进程 CLI 对照；三输入引用在核心调用前／返回后／公开返回后三时点一致。"})
        record("G6_READONLY_ISOLATION_AND_INPUTS", "host", g6_problems, guard_hits=guard)

    # ================================================================ G7 证据登记与计数
    if only in ("all", "evidence"):
        print("== G7 证据登记与计数")
        g7_problems: list = []
        scene_problems: list = []
        scene_records: list = []
        checker_records: list = []
        for batch_dir in sorted((item for item in batch_parent.iterdir() if item.is_dir()),
                                key=lambda item: item.name):
            manifest_path = batch_dir / "batch_manifest.json"
            manifest, _ = load_json_if_parseable(manifest_path)
            invocation = manifest.get("checker_invocation")
            entry = {"batch": batch_dir.name, "outcome": collect_batch_outcome(batch_dir)}
            if isinstance(invocation, dict):
                entry["checker"] = {"argv": invocation.get("argv"),
                                    "started": invocation.get("started"),
                                    "exit_code": invocation.get("exit_code"),
                                    "report_result": invocation.get("report_result")}
                for key in ("report", "stdout_log", "stderr_log"):
                    reference = invocation.get(key) or {}
                    reference_path = batch_dir / str(reference.get("path") or "")
                    exists = reference_path.is_file()
                    actual = sha256(reference_path) if exists else None
                    verified = bool(exists and actual == reference.get("sha256")
                                    and reference.get("exists") is True)
                    entry[f"{key}_verified"] = verified
                    if not verified:
                        scene_problems.append(f"{batch_dir.name}: checker {key} 引用未验证")
                if invocation.get("started") is True and invocation.get("exit_code") == 0:
                    checker_records.append({"batch": batch_dir.name,
                                            "stdout_sha256":
                                                (invocation.get("stdout_log") or {}).get("sha256"),
                                            "stderr_sha256":
                                                (invocation.get("stderr_log") or {}).get("sha256")})
            host_manifest_path = batch_dir / "workflow" / "host_manifest.json"
            host_manifest, _ = load_json_if_parseable(host_manifest_path)
            receive = host_manifest.get("receive") or {}
            inv_payload, _ = load_json_if_parseable(batch_dir / "workflow"
                                                    / "receive_invocation.json")
            entry["receiver"] = {
                "command_matches": receive.get("command") == inv_payload.get("command"),
                "exit_code_matches": receive.get("exit_code") == inv_payload.get("exit_code")}
            if not entry["receiver"]["command_matches"] or not entry["receiver"]["exit_code_matches"]:
                scene_problems.append(f"{batch_dir.name}: receiver 命令/退出码不一致")
            scene_records.append(entry)
        counts["checker_started_by_receiver"] = len(checker_records)
        counts["receiver_starts_recorded"] = len(scene_records)
        scenes = [item["outcome"] for item in scene_records]
        packet_ready = [item for item in scenes
                        if item["packet_batch_status"] == "DEV_FACT_PACKET_READY"]
        vouchers = [item for item in scenes if item["voucher_0007_present"]
                    and item["packet_parseable"] and not item["failure_present"]]
        failures_scene = [item for item in scenes if item["failure_present"]]
        # 明确分列：复算 MATCHED 报告 / 事实包 READY / 0007 物理文件（可解析、半写）/ 有效失败
        crosscheck_reports = [item for item in scene_records
                              if (item.get("crosscheck") or {}).get("matched") is True]
        counts["crosscheck_matched_reports_total"] = len(crosscheck_reports)
        counts["packet_ready_total"] = len(packet_ready)
        # 物理文件用 is_file 判定；可解析另计；用真实 batch 标识（不再引用缺失字段）
        physical = [item for item in scene_records
                    if (batch_parent / item["batch"]
                        / "workflow/checkpoints/0007.json").is_file()]
        parseable = [item for item in physical
                     if load_json_if_parseable(batch_parent / item["batch"]
                                               / "workflow/checkpoints/0007.json")[1]]
        counts["voucher_0007_physical_total"] = len(physical)
        counts["voucher_0007_parseable_total"] = len(parseable)
        counts["voucher_0007_half_written_total"] = len([
            item for item in physical if item["outcome"]["failure_present"]
            and not load_json_if_parseable(batch_parent / item["batch"]
                                           / "workflow/checkpoints/0007.json")[1]])
        counts["matched_reports_total"] = counts["crosscheck_matched_reports_total"]
        counts["success_vouchers_0007_total"] = len(vouchers)
        counts["fact_packet_failure_scenes"] = len(failures_scene)
        counts["half_written_vouchers"] = len([item for item in scenes
                                               if item["voucher_0007_present"]
                                               and item["failure_present"]])
        # 文件台账
        ledger_entries = []
        for item in cli_records:
            for key, digest_key in (("stdout_path", "stdout_sha256"),
                                    ("stderr_path", "stderr_sha256"),
                                    ("return_object_path", "return_object_sha256")):
                target_file = container / item[key]
                ledger_entries.append({"record": f"cli:{item['label']}", "field": key,
                                       "path": item[key], "exists": target_file.is_file(),
                                       "expected_sha256": item.get(digest_key),
                                       "actual_sha256": sha256(target_file)
                                       if target_file.is_file() else None})
        for item in api_records:
            for key, digest_key in (("return_path", "return_sha256"),
                                    ("exception_path", "exception_sha256")):
                if not item.get(key):
                    continue
                target_file = container / item[key]
                ledger_entries.append({"record": f"api:{item['label']}", "field": key,
                                       "path": item[key], "exists": target_file.is_file(),
                                       "expected_sha256": item.get(digest_key),
                                       "actual_sha256": sha256(target_file)
                                       if target_file.is_file() else None})

        def audit_ledger(payload) -> list:
            problems = []
            for item in payload["file_ledger"]:
                target_file = container / item["path"]
                if not target_file.is_file():
                    problems.append(f"记录文件缺失：{item['path']}")
                elif item.get("expected_sha256") is not None \
                        and sha256(target_file) != item["expected_sha256"]:
                    problems.append(f"记录哈希不符：{item['path']}")
            return problems

        def audit_registration(payload) -> list:
            problems = []
            cli_names = {f"cli:{item['label']}" for item in payload["cli_records"]}
            api_names = {f"api:{item['label']}" for item in payload["api_records"]}
            record_names = cli_names | api_names
            ledger_names = {item["record"] for item in payload["file_ledger"]}
            registry_names = {item["record"] for item in payload.get("registry_calls", [])}
            for name in sorted(record_names - ledger_names):
                problems.append(f"调用记录未登记进文件台账：{name}")
            for name in sorted(record_names - registry_names):
                problems.append(f"调用未登记进权威登记表：{name}")
            for name in sorted(registry_names - record_names):
                problems.append(f"登记表存在无对应记录的条目：{name}")
            return problems

        registry_path = save_json(container / "call_registry.json",
                                  {"calls": call_registry, "cli": len(cli_records),
                                   "api": len(api_records)})
        ledger = {"cli_records": cli_records, "api_records": api_records,
                  "file_ledger": ledger_entries, "counts": counts,
                  "call_registry_path": rel(registry_path), "registry_calls": call_registry}
        ledger_path = save_json(container / "evidence_ledger.json", ledger)
        ledger_problems = audit_ledger(ledger) + audit_registration(ledger)
        counts["missing_records"] = len(ledger_problems)
        counts["unregistered_records"] = 0
        stdout_files = sorted(item.name for item in (container / "cli_logs").glob("*.stdout.txt"))
        registered_cli = {item["label"] for item in cli_records}
        unregistered = [name for name in stdout_files
                        if name[: -len(".stdout.txt")] not in registered_cli]
        counts["unregistered_records"] = len(unregistered)
        save_json(container / "scene_outcomes.json",
                  {"scenes": scenes, "records": scene_records,
                   "derived": {key: counts[key] for key in (
                       "matched_reports_total", "success_vouchers_0007_total",
                       "fact_packet_failure_scenes", "half_written_vouchers",
                       "receiver_starts_recorded", "checker_started_by_receiver")}})
        # 隔离自测：只删审核副本一条调用登记
        copy_path = container / "isolation" / "evidence_ledger_minus_one.json"
        trimmed = copy.deepcopy(ledger)
        removed = trimmed["file_ledger"].pop(0)
        removed_registry = trimmed["registry_calls"].pop(0)
        save_json(copy_path, trimmed)
        isolation_failures = audit_ledger(trimmed) + audit_registration(trimmed)
        if not isolation_failures:
            g7_problems.append(f"隔离自测未失败（去掉 {removed['record']}／{removed['field']}、"
                               f"登记表 {removed_registry['record']}）")
        save_json(container / "isolation" / "isolation_result.json",
                  {"removed_ledger_entry": removed, "removed_registry_entry": removed_registry,
                   "audit_problems_on_trimmed": isolation_failures,
                   "audit_problems_on_original": ledger_problems,
                   "note": "只操作审核副本；真实日志与登记表未改。"})
        if ledger_problems:
            g7_problems.extend(ledger_problems[:5])
        if unregistered:
            g7_problems.append(f"存在未登记 CLI 原文：{unregistered[:3]}")
        record("G7_EVIDENCE_LEDGER_AND_COUNTS", "evidence",
               g7_problems + scene_problems, ledger_path=rel(ledger_path),
               cli_records=len(cli_records), api_records=len(api_records))

    # ================================================================ G8 保护与停止点
    if only in ("all", "protection"):
        print("== G8 保护与停止点")
        g8_problems: list = []
        if not BASELINE.is_file():
            g8_problems.append(f"保护基线缺失：{BASELINE}")
        if sha256(BASELINE) != BASELINE_SHA:
            g8_problems.append("保护基线文件哈希与卡上登记不一致")
        baseline_raw = json.loads(BASELINE.read_text(encoding="utf-8")) \
            if BASELINE.is_file() else {}
        if len(baseline_raw) != BASELINE_ENTRIES:
            g8_problems.append(f"基线条目数不是 {BASELINE_ENTRIES}：{len(baseline_raw)}")
        baseline = {name.replace("\\", "/"): digest for name, digest in baseline_raw.items()}
        current_scan = {}
        for path in PROJECT_ROOT.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            if relative.split("/")[0] in SKIP_DIRS:
                continue
            try:
                current_scan[relative] = sha256(path)
            except OSError:
                continue
        changed = sorted(name for name, digest in baseline.items()
                         if name in current_scan and current_scan[name] != digest)
        missing = sorted(name for name in baseline if name not in current_scan)
        unexpected = sorted(name for name in changed if name not in ALLOWED_CHANGES)
        scan_path = save_json(container / "protected_scan.json", current_scan)
        if missing:
            g8_problems.append(f"基线缺失 {len(missing)} 项：{missing[:5]}")
        if unexpected:
            g8_problems.append(f"预期外变化：{unexpected[:5]}")
        for rel_path, want in FROZEN.items():
            path = PROJECT_ROOT / rel_path
            got = sha256(path) if path.is_file() else None
            if got != want:
                g8_problems.append(f"关键冻结件哈希不符：{rel_path} = {got}")
        # 最终链与停止点
        for batch_dir in sorted(item for item in batch_parent.iterdir() if item.is_dir()):
            checkpoints = sorted(p.name for p in (batch_dir / "workflow/checkpoints").iterdir()) \
                if (batch_dir / "workflow/checkpoints").is_dir() else []
            for name in checkpoints:
                if name not in host.LEGAL_CHECKPOINT_NAMES:
                    g8_problems.append(f"{batch_dir.name}: 未知 checkpoint {name}")
            if "0008.json" in checkpoints:
                g8_problems.append(f"{batch_dir.name}: 不得存在 0008")
        # 成功批次的 workflow／批准状态
        success = [item for item in sorted(batch_parent.iterdir()) if item.is_dir()
                   and (item / "workflow/checkpoints/0007.json").is_file()
                   and not (item / "workflow/fact_packet/failure.json").is_file()]
        for batch_dir in success:
            checkpoint7 = json.loads((batch_dir / "workflow/checkpoints/0007.json")
                                     .read_text(encoding="utf-8"))
            checkpoint6 = json.loads((batch_dir / "workflow/checkpoints/0006.json")
                                     .read_text(encoding="utf-8"))
            state = checkpoint7["workflow"]["state"]
            if not same_json(checkpoint7["workflow"], checkpoint6["workflow"]):
                g8_problems.append(f"{batch_dir.name}: 0007 workflow 与 0006 不相等")
            if state["gate1_approval"] is not None or state["gate2_approval"] is not None:
                g8_problems.append(f"{batch_dir.name}: 真实批准必须仍为 null")
            if state["next_step_allowed"] is not False:
                g8_problems.append(f"{batch_dir.name}: next_step_allowed 必须仍为 false")
        save_json(container / "probe_records" / "g8_protection_and_stop.json", {
            "case": "g8_protection_and_stop", "scan_path": rel(scan_path),
            "baseline": {"path": str(BASELINE), "sha256": BASELINE_SHA,
                         "entries": len(baseline_raw)},
            "scanned_entries": len(current_scan), "changed": changed, "missing": missing,
            "unexpected_changes": unexpected, "frozen": FROZEN,
            "success_batches": [item.name for item in success],
            "note": "仅宿主与宿主指南允许变化；关键冻结件哈希一致；成功批次链止于 0007、无 0008、"
                    "真实批准 null、next_step_allowed=false。"})
        record("G8_PROTECTION_AND_STOP_POINT", "host", g8_problems,
               changed=changed, missing=len(missing))

    # ================================================================ 汇总
    summary = {
        "host_version": host.HOST_VERSION,
        "checkpoint_version": host.CHECKPOINT_VERSION,
        "fact_packet_protocols": {"start": host.FACT_PACKET_START_VERSION,
                                  "artifacts": host.FACT_PACKET_ARTIFACTS_VERSION,
                                  "failure": host.FACT_PACKET_FAILURE_VERSION},
        "packet_version": host.FACT_PACKET_MODULE.PACKET_VERSION,
        "container": str(container), "batch_parent": str(batch_parent),
        "sqlite_parent": str(sqlite_parent),
        "checks": checks, "failures": failures, "counts": counts,
        "artifacts": {"host_sha256": sha256(HOST_PATH),
                      "guide_sha256": sha256(PROJECT_ROOT / "docs/WORKFLOW_HOST_GUIDE.md"),
                      "test_sha256": sha256(Path(__file__)),
                      "fact_packet_core_sha256": FROZEN["scripts/build_demo_fact_packet.py"]},
        "records": {"cli": len(cli_records), "api": len(api_records)},
    }
    save_json(container / "checks.json", checks)
    save_json(container / "counts.json", counts)
    save_json(container / "cli_logs.json", cli_records)
    save_json(container / "api_records.json", api_records)
    save_json(container / "summary.json", summary)

    print(f"检查项 {len(checks)}：{sum(1 for c in checks if c['result'] == 'PASS')} PASS / "
          f"{sum(1 for c in checks if c['result'] == 'FAIL')} FAIL")
    print(f"CLI 记录 {len(cli_records)} 条 / API 记录 {len(api_records)} 条；"
          f"missing={counts['missing_records']} unregistered={counts['unregistered_records']}")
    print(f"进程内观测：build_fact_packet "
          f"{counts['core_observations']['build_fact_packet_inprocess']} 次；"
          f"CLI 内部核心次数={counts['core_observations']['cli_internal_core_calls']}（不可观测，记 null）")
    print(f"总体：已建事实底稿 {counts['facts_built_in_flow']}；成功 0007 "
          f"{counts['success_vouchers_0007_total']}；失败现场 "
          f"{counts['fact_packet_failure_scenes']}；半写凭证 {counts['half_written_vouchers']}；"
          f"receiver {counts.get('receiver_starts_recorded')}；checker（receiver 启动）"
          f"{counts.get('checker_started_by_receiver')}；真实批准 {counts['real_approvals']}")
    print(f"测试失败 {len(failures)}；汇总 {container / 'summary.json'}")
    if failures or counts["missing_records"] or counts["unregistered_records"]:
        print("存在断言失败、保护失败或台账问题，返回非零退出码。")
        return 1
    print("全部预期成立。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
