#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-042 运行层演示入口（合成单批次，至人类初判保存 + 只读恢复）。

只通过已接受运行时层的**公开 API** 走完：
注册 → Gate1 请求/保存 → 装载 → Gate2 请求/保存 → 筛查 → 复算 → 事实 →
`prepare_runtime_initial_judgment_request` → `save_runtime_initial_judgment` →
`verify_runtime_initial_judgment`。

人类提交值只读已登记夹具（event2 六原文 / TASK-020 Gate 决定原文）；
不批准真实批次、不认证身份、不开放 AI 或终判、无真实数据。

一条命令跑完账-证-实（TASK-046）：在既有链之后，用 canonical 证据输入
--evidence-input（默认 data/evidence_inputs/task043_v1_1）只读调用已接受的
契约校验器、账证匹配器与账实勾对器，把四相符摘要写入 demo_summary.json/
demo_readme.md；任一步差异都不被吞掉（演示退出码非 0）。

只读扩展点模式：
    --inspect-record <初判记录目录> [--inspect-out <json 文件>]
独立进程只读消费该 VERIFIED 记录（六文件 + manifest），不导入运行时适配器、
不写记录命名域、不触发归一化/装载/筛查/复算/事实 build。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import stat
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "data/runtime_initial_judgment_recording_tests"
BATCH = ROOT / "data/batches/task027r1_run_04/batch_normal"
ADAPTER = ROOT / "scripts/runtime_gate1.py"
FROZEN_STORE = ROOT / "scripts/store_demo_human_initial_judgment.py"
GATE_FIXTURE = ROOT / "data/decision_protocol_checks/task020r2_run_01/fixture_values.json"
HUMAN_FIXTURE = (ROOT / "data/reviews/task036r1_gpt_20261016_193749/"
                 "human_history_fixture_supplement.json")
RECORDS_ROOT = ROOT / "data/human_initial_judgment_records"
EVIDENCE_INPUT_DEFAULT = ROOT / "data/evidence_inputs/task043_v1_1"
LEDGER_NORMALIZED = ROOT / "data/runtime/task042_dsh_01/normal.load/normalized.json"
LEDGER_DB = ROOT / "data/sqlite_tests/task042_dsh_01/normal/runtime.sqlite3"
CONTRACT = ROOT / "scripts/input_contract_v1.py"
MATCHER = ROOT / "scripts/voucher_match_v1.py"
RECONCILER = ROOT / "scripts/bank_reconcile_v1.py"
ACCEPTED_INPUT_VERSIONS = ("task043-input-1.0", "task043-input-1.1")
SCOPE = "TASK037-DECLARED-TECHNICAL-NAMESPACE"
HISTORY_EXPECTATIONS_VERSION = "TASK-037-human-initial-judgment-history-expectations-1.0"
SNAPSHOT_FILES = ("expectations.json", "judgment_result.json", "manifest.json",
                  "materials.json", "prior_history.json", "submission.json")
ENVELOPE_FILES = ("context.json", "receipt.json", "started.json")
BOUNDARY_KEYS = ("workflow_connected", "execution_allowed", "next_step_allowed", "ai_enabled",
                 "identity_authenticated", "source_authenticity_proven",
                 "audit_conclusion_formed", "final_judgment_recorded",
                 "global_history_completeness_proven")
BOUNDARY_NOTE = ("合成演示，不是批次批准、不是身份认证，不开放 AI/终判；"
                 "real_approval=null，next_step_allowed=false，ai_enabled=false。")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fp(value):
    return sha(canon(value))


def read(path):
    return json.loads(Path(path).read_bytes())


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


def identity(path):
    raw = Path(path).read_bytes()
    return {"byte_size": len(raw), "file_sha256": sha(raw)}


def snapshot(paths):
    result = {}
    for base in paths:
        base = Path(base)
        if not base.is_dir():
            continue
        for item in sorted(base.rglob("*")):
            if item.is_file():
                result[item.relative_to(ROOT).as_posix()] = identity(item)
    return result


class DemoFailure(Exception):
    pass


def step(log, label, function, *args, **kwargs):
    record = {"operation": label, "status": "pending"}
    log.append(record)
    try:
        value = function(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - 保留现场与真实异常
        record.update(status="exception", exception_type=type(exc).__name__,
                      message=str(exc), field=getattr(exc, "field", None),
                      stage=getattr(exc, "stage", None))
        raise
    record["status"] = "returned"
    return value


def write_json(path, value):
    Path(path).write_bytes(json.dumps(value, ensure_ascii=False, indent=2,
                                      sort_keys=True).encode("utf-8") + b"\n")


def demo_paths(out_dir):
    name = out_dir.name
    return {
        "runtime": ROOT / "data/runtime" / name,
        "gate1": ROOT / "data/human_gate_decision_records/gate1" / name,
        "gate2": ROOT / "data/human_gate_decision_records/gate2" / name,
        "sqlite": ROOT / "data/sqlite_tests" / name,
        "records": ROOT / "data/human_initial_judgment_records" / name,
    }


def prepare_roots(out_dir):
    paths = demo_paths(out_dir)
    for key, path in paths.items():
        if path.exists():
            raise DemoFailure("目标根已存在，拒绝复用：%s" % rel(path))
    for path in paths.values():
        path.mkdir(parents=True)
    leaf = paths["runtime"] / "normal"
    scope = paths["gate1"] / "normal"
    namespace = paths["records"] / "bound"
    namespace.mkdir()
    database = paths["sqlite"] / "normal/runtime.sqlite3"
    event1 = scope / "event_0001"
    event2 = paths["gate2"] / "normal/event_0001"
    params = {"scope_dir": scope, "event_relative": rel(event1),
              "database_path": database, "gate2_event_relative": rel(event2)}
    return paths, leaf, scope, event1, event2, namespace, database, params


def run_demo(out_dir, evidence_input=EVIDENCE_INPUT_DEFAULT):
    started = time.monotonic()
    evidence_input = Path(evidence_input)
    if not evidence_input.is_absolute():
        evidence_input = Path.cwd() / evidence_input
    rt = load(ADAPTER, "runtime_gate1_demo_public_api")
    paths, leaf, scope, event1, event2, namespace, database, params = prepare_roots(out_dir)
    log = []
    command = {"argv": sys.argv[1:], "cwd": os.getcwd(), "python": sys.version.split()[0],
               "out_dir": rel(out_dir), "evidence_input": rel(evidence_input),
               "started_at_note":
               "技术演示顺序；不记录人类决定时间，不取随机/身份"}
    registry = step(log, "build_runtime_registry", rt.build_runtime_registry, BATCH, leaf,
                    scope_dir=scope,
                    initial_judgment_history={"namespace_relative": rel(namespace),
                                              "declared_scope": SCOPE})["registry"]
    request1 = step(log, "prepare_runtime_gate1_request",
                    rt.prepare_runtime_gate1_request, BATCH, leaf, "DEMO-REQ-G1-0001")
    fields = read(GATE_FIXTURE)
    submission1 = copy.deepcopy(fields["BASE1"]["submission"])
    submission1["batch_id"] = registry["batch_id"]
    submission1["request_binding"] = {
        "request_id": "DEMO-REQ-G1-0001",
        "materials_binding": request1["request"]["materials"]["materials_fingerprint"]}
    decision1 = step(log, "save_runtime_gate1_decision", rt.save_runtime_gate1_decision, BATCH,
                     leaf, "DEMO-REQ-G1-0001", submission1, event1, scope_dir=scope)
    step(log, "run_gate1_approved_load", rt.run_gate1_approved_load, BATCH, leaf,
         scope_dir=scope, event_relative=rel(event1), database_path=database)
    request2 = step(log, "prepare_runtime_gate2_request",
                    rt.prepare_runtime_gate2_request, BATCH, leaf, "DEMO-REQ-G2-0001",
                    scope_dir=scope, event_relative=rel(event1), database_path=database)
    submission2 = copy.deepcopy(fields["BASE2"]["submission"])
    submission2["batch_id"] = registry["batch_id"]
    submission2["request_binding"] = {
        "request_id": "DEMO-REQ-G2-0001",
        "materials_binding": request2["request"]["materials"]["materials_fingerprint"]}
    submission2["prior_decision_binding"] = {
        "wrapper_version": rt.GATE2_WRAPPER_VERSION, "record": decision1["record"],
        "record_fingerprint": decision1["record_fingerprint"]}
    decision2 = step(log, "save_runtime_gate2_decision", rt.save_runtime_gate2_decision, BATCH,
                     leaf, "DEMO-REQ-G2-0001", submission2, event2, scope_dir=scope,
                     event_relative=rel(event1), database_path=database)
    step(log, "run_gate2_approved_screen", rt.run_gate2_approved_screen, BATCH, leaf, **params)
    step(log, "run_gate2_rule_crosscheck", rt.run_gate2_rule_crosscheck, BATCH, leaf, **params)
    step(log, "run_gate2_fact_packet", rt.run_gate2_fact_packet, BATCH, leaf, **params)
    human = read(HUMAN_FIXTURE)["human_values"]
    expectations0 = {"expectations_version": HISTORY_EXPECTATIONS_VERSION,
                     "expected_namespace_relative": rel(namespace),
                     "expected_declared_scope": SCOPE, "expected_entries": []}
    prepared = step(log, "prepare_runtime_initial_judgment_request",
                    rt.prepare_runtime_initial_judgment_request, BATCH, leaf,
                    "DEMO-REQ-IJ-0001", **params, history_expectations=expectations0)
    submission = {"submission_version": "TASK-034-human-initial-judgment-submission-1.0",
                  "event_id": human["event_id"], "batch_id": registry["batch_id"],
                  "request_binding": {
                      "request_id": "DEMO-REQ-IJ-0001",
                      "materials_fingerprint":
                          prepared["request"]["materials"]["materials_fingerprint"]},
                  "submission_source": "HUMAN_INITIAL_JUDGMENT",
                  "actor": {"actor_kind": "HUMAN_DECLARED", "actor_id": human["actor_id"],
                            "declaration_note": human["declaration_note"]},
                  "decided_at_raw": human["decided_at_raw"],
                  "assessment": human["assessment"], "reason": human["reason"]}
    record_relative = (namespace / "rec_0001").relative_to(ROOT).as_posix()
    saved = step(log, "save_runtime_initial_judgment", rt.save_runtime_initial_judgment, BATCH,
                 leaf, "DEMO-REQ-IJ-0001", submission, record_relative, **params,
                 history_expectations=expectations0)
    expectations1 = {"expectations_version": HISTORY_EXPECTATIONS_VERSION,
                     "expected_namespace_relative": rel(namespace),
                     "expected_declared_scope": SCOPE,
                     "expected_entries": [{"relative": "rec_0001",
                                           "manifest_file_sha256":
                                               saved["manifest_file_sha256"]}]}
    verified = step(log, "verify_runtime_initial_judgment", rt.verify_runtime_initial_judgment,
                    BATCH, leaf, **params, record_relative=record_relative,
                    history_expectations=expectations1)

    four = four_way(evidence_input, out_dir, log)
    record_dir = namespace / "rec_0001"
    envelope = leaf.parent / (leaf.name + ".initial")
    packet = read(leaf.parent / (leaf.name + ".facts") / "fact_packet.json")
    crosscheck = read(leaf.parent / (leaf.name + ".crosscheck") / "crosscheck_report.json")
    files = [{"relative": name,
              "byte_size": identity(record_dir / name)["byte_size"],
              "file_sha256": identity(record_dir / name)["file_sha256"]}
             for name in SNAPSHOT_FILES]
    envelopes = [{"relative": rel(envelope / name),
                  "byte_size": identity(envelope / name)["byte_size"],
                  "file_sha256": identity(envelope / name)["file_sha256"]}
                 for name in ENVELOPE_FILES]
    summary = {
        "demo_version": "TASK-046-four-way-demo-1.0",
        "generated_by": "scripts/run_runtime_demo.py",
        "batch": {"batch_id": registry["batch_id"], "source_batch_relative": rel(BATCH),
                  "entity": packet["entity"],
                  "period": packet["entity"]["period"],
                  "banner": packet.get("banner")},
        "gates": {
            "gate1": {"event_relative": rel(event1),
                      "decision": decision1["record"]["decision"],
                      "record_fingerprint": decision1["record_fingerprint"],
                      "actor_kind": decision1["record"]["actor"]["actor_kind"]},
            "gate2": {"event_relative": rel(event2),
                      "decision": decision2["record"]["decision"],
                      "record_fingerprint": decision2["record_fingerprint"],
                      "prior_gate1": decision2["record"]["prior_gate1"]["record_fingerprint"]}},
        "rules": {"counts": crosscheck["observed_summary"]["rule_hit_counts"],
                  "note": "R01—R04 是待核查线索，不是舞弊、损失或审计结论。",
                  "overpayment_total_cents":
                      crosscheck["observed_summary"].get("r02_overpayment_total_cents")},
        "fact_packet_relative": rel(leaf.parent / (leaf.name + ".facts") / "fact_packet.json"),
        "record": {
            "record_relative": record_relative,
            "status": verified["status"],
            "identity": verified["identity"],
            "record_fingerprint": verified["record_fingerprint"],
            "manifest_file_sha256": verified["manifest_file_sha256"],
            "six_files": files,
            "three_envelopes": envelopes,
            "prior_history_records": verified["history_verification"]["prior_history"]["records"]},
        "boundaries": verified["boundaries"],
        "boundary_note": BOUNDARY_NOTE,
        "real_approval": None,
        "next_step_allowed": False,
        "ai_enabled": False,
        "four_way": four,
        "duration_seconds": round(time.monotonic() - started, 2),
        "command": command,
        "steps": log,
    }
    summary["boundaries_all_false"] = all(value is False
                                          for value in verified["boundaries"].values())
    summary["rule_counts_r01_r04"] = [summary["rules"]["counts"].get(rule)
                                      for rule in ("R01", "R02", "R03", "R04")]
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "demo_summary.json", summary)
    (out_dir / "demo_readme.md").write_bytes(render_readme(summary).encode("utf-8"))
    if four["account_voucher"]["conclusion"] != "ALL_MATCHED" \
            or four["account_reality"]["conclusion"] != "ALL_MATCHED":
        raise DemoFailure("四相符存在差异：账证 %s / 账实 %s"
                          % (four["account_voucher"]["conclusion"],
                             four["account_reality"]["conclusion"]))
    return summary


def four_way(evidence_input, out_dir, log):
    """只读调用已接受契约/账证/账实核对器；差异不被吞掉。"""
    manifest_path = evidence_input / "input_manifest.json"
    if not manifest_path.is_file():
        raise DemoFailure("--evidence-input 缺少 input_manifest.json：%s" % evidence_input)
    manifest = read(manifest_path)
    version = manifest.get("input_version")
    contract = load(CONTRACT, "task046_input_contract_validator")
    code = step(log, "contract_validate_evidence_input", contract.run, evidence_input,
                out_dir / "task043_input_check", LEDGER_DB)
    if code != 0:
        rejection = read(out_dir / "task043_input_check" / "rejection.json")
        raise DemoFailure("证据输入契约拒收：%s"
                          % [reason["code"] for reason in rejection["reasons"]])
    if version not in ACCEPTED_INPUT_VERSIONS:
        raise DemoFailure("--evidence-input 版本不被接受：%r（接受 %s）"
                          % (version, ", ".join(ACCEPTED_INPUT_VERSIONS)))
    registry = read(out_dir / "task043_input_check" / "input_registry.json")
    matcher = load(MATCHER, "task046_voucher_match_v1")
    voucher = step(log, "account_voucher_match", matcher.build_report, evidence_input,
                   LEDGER_NORMALIZED, out_dir / "task044_match")
    reconciler = load(RECONCILER, "task046_bank_reconcile_v1")
    step(log, "account_reality_reconcile", reconciler.run, evidence_input,
         LEDGER_NORMALIZED, out_dir / "task045_reconcile")
    reality = read(out_dir / "task045_reconcile" / "bank_reconcile_report.json")
    vouchers = registry["counts"]["vouchers"]
    return {
        "evidence_input": {"root": rel(evidence_input), "input_version": version},
        "contract": {"conclusion": registry["conclusion"], "vouchers": vouchers,
                      "voucher_total": registry["counts"]["voucher_total"],
                      "links": registry["counts"]["links"],
                      "bank_transactions": registry["counts"]["bank_transactions"]},
        "account_voucher": {
            "conclusion": voucher["conclusion"],
            "items_total": voucher["summary"]["items_total"],
            "matched": voucher["summary"]["item_status"].get("MATCHED", 0),
            "differences_total": voucher["summary"]["differences_total"],
            "missing_total": voucher["summary"]["missing_total"],
            "extra_total": voucher["summary"]["extra_total"],
            "r02_sampling": [item["ledger_id"]
                              for item in voucher["r02_sampling"]["items"]],
            "human_conclusion": None},
        "account_reality": {
            "conclusion": reality["conclusion"],
            "matched": reality["summary"]["matched"],
            "ledger_records": reality["summary"]["ledger_records"],
            "bank_transactions": reality["summary"]["bank_transactions"],
            "basis": sorted({item["basis"] for item in reality["matched"]}),
            "period_totals": reality["period_totals"],
            "ledger_unmatched": reality["summary"]["ledger_unmatched"],
            "bank_unmatched": reality["summary"]["bank_unmatched"],
            "human_conclusion": None},
        "verification_level": "FIELD_LEVEL_L1_AND_TRANSACTION_LEVEL_L1",
        "note": "四相符摘要由已接受契约/账证/账实核对器只读计算；任一步非 ALL_MATCHED 则演示退出码非 0。"}


def render_readme(summary):
    batch = summary["batch"]
    gates = summary["gates"]
    rules = summary["rules"]["counts"]
    record = summary["record"]
    four = summary["four_way"]
    six = "\n".join("  - `%s` (%d B, `%s`)" % (item["relative"], item["byte_size"],
                                              item["file_sha256"][:16])
                    for item in record["six_files"])
    envelopes = "\n".join("  - `%s` (%d B)" % (item["relative"], item["byte_size"])
                          for item in record["three_envelopes"])
    boundaries = "\n".join("  - `%s`: %s" % (key, "false")
                           for key in BOUNDARY_KEYS)
    return (
        "# 运行层演示说明（合成单批次，至人类初判）\n\n"
        "> %s\n\n"
        "本演示由 `scripts/run_runtime_demo.py` 通过已接受运行时层的公开 API 生成；"
        "不使用真实数据、不批准任何真实批次、不做身份认证、不实施 AI 建议或人类终判。\n\n"
        "## 批次与实体\n\n"
        "- 批次：`%s`（源批次只读复用 `%s`）\n"
        "- 实体：%s；币种：%s；期间：%s 至 %s；截至：%s；金额单位：整数分\n\n"
        "## Gate 决定（合成）\n\n"
        "- Gate1：`%s`，决定 `%s`，记录指纹 `%s`\n"
        "- Gate2：`%s`，决定 `%s`，记录指纹 `%s`\n\n"
        "## 待核查线索（不是舞弊/损失/审计结论）\n\n"
        "- R01：%s，R02：%s，R03：%s，R04：%s\n"
        "- R02 超额合计：%s 分\n\n"
        "## 事实底稿与人类初判\n\n"
        "- 事实包：`%s`\n"
        "- 初判记录：`%s`（状态 `%s`）\n"
        "- 记录指纹：`%s`；manifest FILE：`%s`\n"
        "- 身份：批次 `%s` / 人类事件 `%s` / 技术请求 `%s`\n\n"
        "## 四相符（账-证-实一条命令）\n\n"
        "- 证据输入：%s（input_version=%s）\n"
        "- 契约校验：%s；凭证 %s（回单 %s / 审批 %s / 其他 %s）/ links %s / 流水 %s\n"
        "- 账证相符：%s，%s/%s 项 MATCHED，差异 %s / 账有证无 %s / 证有账无 %s；R02 抽样 %s\n"
        "- 账实相符：%s，%s/%s 匹配（依据 %s）；期间合计差异 OUT %s / IN %s；"
        "未达账项 账有实无 %s / 实有账无 %s\n"
        "- 人类核对结论：留空（不采集、不虚构）；任一步非 ALL_MATCHED 演示退出码非 0。\n\n"
        "## 六文件与三封装\n\n"
        "历史直接叶（恰六文件）：\n%s\n\n"
        "运行封装（恰三件）：\n%s\n\n"
        "## 九权限边界（全部 false）\n\n%s\n\n"
        "## 边界声明\n\n"
        "合成演示，不是批次批准、不是身份认证，不开放 AI/终判；`real_approval=null`、"
        "`next_step_allowed=false`、`ai_enabled=false`。真实批准仍为 null，真实独立初判未保存。\n"
        "未来 AI 层只能在**只读**消费本记录与材料/事实、分域存放、另行授权的约束下接入。\n"
        % (BOUNDARY_NOTE,
           batch["batch_id"], batch["source_batch_relative"],
           batch["entity"]["company"], batch["entity"]["currency"],
           batch["period"]["period_start"], batch["period"]["period_end"],
           batch["entity"]["cutoff_date"],
           gates["gate1"]["event_relative"], gates["gate1"]["decision"],
           gates["gate1"]["record_fingerprint"][:16],
           gates["gate2"]["event_relative"], gates["gate2"]["decision"],
           gates["gate2"]["record_fingerprint"][:16],
           rules.get("R01"), rules.get("R02"), rules.get("R03"), rules.get("R04"),
           summary["rules"].get("overpayment_total_cents"),
           summary["fact_packet_relative"], record["record_relative"], record["status"],
           record["record_fingerprint"], record["manifest_file_sha256"],
           record["identity"]["batch_id"], record["identity"]["event_id"],
           record["identity"]["request_id"],
           four["evidence_input"]["root"], four["evidence_input"]["input_version"],
           four["contract"]["conclusion"], four["contract"]["voucher_total"],
           four["contract"]["vouchers"].get("BANK_RECEIPT"),
           four["contract"]["vouchers"].get("APPROVAL"),
           four["contract"]["vouchers"].get("INVOICE", 0)
           + four["contract"]["vouchers"].get("CONTRACT", 0)
           + four["contract"]["vouchers"].get("GOODS_RECEIPT", 0),
           four["contract"]["links"], four["contract"]["bank_transactions"],
           four["account_voucher"]["conclusion"], four["account_voucher"]["matched"],
           four["account_voucher"]["items_total"],
           four["account_voucher"]["differences_total"],
           four["account_voucher"]["missing_total"],
           four["account_voucher"]["extra_total"],
           ", ".join(four["account_voucher"]["r02_sampling"]),
           four["account_reality"]["conclusion"], four["account_reality"]["matched"],
           four["account_reality"]["ledger_records"],
           ", ".join(four["account_reality"]["basis"]),
           four["account_reality"]["period_totals"]["out_difference_cents"],
           four["account_reality"]["period_totals"]["in_difference_cents"],
           four["account_reality"]["ledger_unmatched"],
           four["account_reality"]["bank_unmatched"],
           six, envelopes, boundaries)
    )


# ------------------------------------------------------------------ 只读扩展点

def inspect_output_path(raw):
    """只允许既有普通证据目录中的全新文件；先检查原始路径，再规范化。"""
    value = os.fspath(raw)
    if not isinstance(value, str) or not value or value.startswith(("\\\\", "//")):
        raise DemoFailure("--inspect-out 必须是普通本地证据文件路径")
    parts = value.replace("/", "\\").split("\\")
    if len(parts[0]) == 2 and parts[0][1] == ":":
        if len(parts) == 1:
            raise DemoFailure("--inspect-out 不允许盘符相对路径")
        parts = parts[1:]
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update("COM%d" % item for item in range(1, 10))
    reserved.update("LPT%d" % item for item in range(1, 10))
    for part in parts:
        if (not part or part in (".", "..") or part.endswith((".", " "))
                or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
                or part.split(".", 1)[0].upper() in reserved):
            raise DemoFailure("--inspect-out 含不允许的路径组件")
    candidate = Path(value)
    if candidate.drive and not candidate.is_absolute():
        raise DemoFailure("--inspect-out 不允许盘符相对路径")
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    allowed = (ROOT / "data/reviews", TEST_ROOT)
    if not any(candidate.is_relative_to(base) for base in allowed):
        raise DemoFailure("--inspect-out 必须位于 data/reviews 或 "
                          "data/runtime_initial_judgment_recording_tests 内")
    if candidate.suffix.lower() != ".json":
        raise DemoFailure("--inspect-out 必须是全新 JSON 文件")
    # 不 follow resolve 后才检查：原链中的 junction/symlink 也必须拒绝。
    for item in (*reversed(candidate.parents), candidate):
        try:
            info = item.lstat()
        except FileNotFoundError:
            if item != candidate:
                raise DemoFailure("--inspect-out 的父目录必须预先存在")
            continue
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise DemoFailure("--inspect-out 原始路径链不得含重解析点")
        if item == candidate:
            raise DemoFailure("--inspect-out 文件必须从未存在")
        if not stat.S_ISDIR(info.st_mode):
            raise DemoFailure("--inspect-out 的父路径必须是普通目录")
    return candidate


def write_inspect_output(path, value):
    # 复核原链后用独占创建；即使校验后出现同名文件也不能覆盖。
    path = inspect_output_path(path)
    raw = json.dumps(value, ensure_ascii=False, indent=2,
                     sort_keys=True).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    stream = os.fdopen(descriptor, "wb")
    try:
        stream.write(raw)
        stream.flush()
    except Exception:
        stream.close()
        raise
    return stream


def inspect_record(record_arg, out_file=None):
    """只读消费一条 VERIFIED 初判记录；不导入运行时适配器，不写记录命名域。"""
    record = Path(record_arg)
    if not record.is_absolute():
        record = (Path.cwd() / record)
    record = record.resolve()
    if not record.is_dir():
        raise DemoFailure("初判记录目录不存在：%s" % record)
    try:
        record.relative_to(RECORDS_ROOT.resolve())
    except ValueError:
        raise DemoFailure("初判记录必须位于 %s 之内" % RECORDS_ROOT)
    namespace = record.parent
    name = namespace.parent.name if namespace.parent != RECORDS_ROOT else namespace.name
    envelope = ROOT / "data/runtime" / name / "normal.initial"
    watched = [record, namespace]
    if envelope.is_dir():
        watched.append(envelope)
    before = snapshot(watched)
    out_path = None
    if out_file is not None:
        out_path = inspect_output_path(out_file)
    store = load(FROZEN_STORE, "store_demo_human_initial_judgment_read_only")
    verification = store.verify_human_initial_judgment_snapshots(str(record))
    manifest = read(record / "manifest.json")
    materials = read(record / "materials.json")
    judgment = read(record / "judgment_result.json")
    record_body = judgment["record"]
    files = [{"relative": item, "byte_size": identity(record / item)["byte_size"],
              "file_sha256": identity(record / item)["file_sha256"]}
             for item in SNAPSHOT_FILES]
    packet_entry = next((item for item in materials["files"] if item.get("role") == "facts.packet"),
                        None)
    after = snapshot(watched)
    algorithm_modules = [name for name in
                         ("normalize_demo_data", "screen_demo_sqlite",
                          "crosscheck_demo_rules", "build_demo_fact_packet",
                          "store_demo_sqlite")
                         if any(mod == name or mod.endswith("_" + name)
                                for mod in sys.modules)]
    summary = {
        "mode": "read_only_inspect",
        "runtime_adapter_imported": False,
        "new_public_api_required": False,
        "algorithm_modules_imported": algorithm_modules,
        "algorithm_builds": 0,
        "status": verification["status"],
        "identity": verification["identity"],
        "record_fingerprint": verification["record_fingerprint"],
        "manifest_file_sha256": verification["manifest_file_sha256"],
        "record_relative": rel(record),
        "six_files": files,
        "boundaries": verification["boundaries"],
        "boundaries_all_false": all(value is False
                                    for value in verification["boundaries"].values()),
        "fact_packet_relative": None if packet_entry is None else packet_entry["relative"],
        "history_binding": record_body["history_binding"],
        "watch_snapshot_before": before,
        "watch_snapshot_after": after,
        "zero_write": before == after,
        "note": "只读消费一条 VERIFIED 人类初判记录；不写记录命名域或运行封装，"
                "不导入运行时适配器，不触发任何算法/装载/SQL/复算/事实 build。",
    }
    output_stream = None
    try:
        if out_path is not None:
            output_stream = write_inspect_output(out_path, summary)
        # 必须在实际独占写出之后消费保护读数，不能提前宣称 zero_write。
        final_after = snapshot(watched)
        summary["watch_snapshot_after"] = final_after
        summary["zero_write"] = before == final_after
        if not summary["zero_write"]:
            if output_stream is not None:
                # 只更新本次独占创建且仍持有的文件，不按路径重开既有文件。
                output_stream.seek(0)
                output_stream.write(json.dumps(summary, ensure_ascii=False, indent=2,
                                                sort_keys=True).encode("utf-8") + b"\n")
                output_stream.truncate()
                output_stream.flush()
            raise DemoFailure("只读核验期间保护文件发生变化；拒绝成功返回")
    finally:
        if output_stream is not None:
            output_stream.close()
    return summary


def resolve_out_dir(raw, *, must_exist=False):
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(TEST_ROOT.resolve())
    except ValueError:
        raise DemoFailure("--out-dir 必须位于 %s 之内" % TEST_ROOT)
    if must_exist and not resolved.is_dir():
        raise DemoFailure("目录不存在：%s" % resolved)
    if not must_exist and resolved.exists():
        raise DemoFailure("--out-dir 必须从未存在：%s" % resolved)
    return resolved


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASK-046 四相符演示（账-证-实一条命令）/ 只读扩展点")
    parser.add_argument("--out-dir")
    parser.add_argument("--inspect-record", dest="inspect_record")
    parser.add_argument("--inspect-out", dest="inspect_out")
    parser.add_argument("--evidence-input", dest="evidence_input",
                        default=str(EVIDENCE_INPUT_DEFAULT))
    args = parser.parse_args(argv)
    if args.inspect_record:
        if args.out_dir:
            raise SystemExit("--inspect-record 与 --out-dir 不能同时使用")
        summary = inspect_record(args.inspect_record, args.inspect_out)
        print(json.dumps({"mode": summary["mode"], "status": summary["status"],
                          "record_relative": summary["record_relative"],
                          "record_fingerprint": summary["record_fingerprint"],
                          "manifest_file_sha256": summary["manifest_file_sha256"],
                          "zero_write": summary["zero_write"],
                          "algorithm_builds": summary["algorithm_builds"]},
                         ensure_ascii=False))
        return 0 if summary["zero_write"] else 1
    if not args.out_dir:
        raise SystemExit("--out-dir 必填（或使用 --inspect-record）")
    out_dir = resolve_out_dir(args.out_dir)
    try:
        summary = run_demo(out_dir, args.evidence_input)
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        print(json.dumps({"status": "FAIL", "out_dir": str(out_dir),
                          "note": "失败保留现场，不清理；请用新 --out-dir 重试"},
                         ensure_ascii=False))
        return 1
    print(json.dumps({"status": "PASS", "out_dir": rel(out_dir),
                      "batch_id": summary["batch"]["batch_id"],
                      "record_relative": summary["record"]["record_relative"],
                      "record_fingerprint": summary["record"]["record_fingerprint"],
                      "status_verified": summary["record"]["status"],
                      "boundaries_all_false": summary["boundaries_all_false"],
                      "rule_counts_r01_r04": summary["rule_counts_r01_r04"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
