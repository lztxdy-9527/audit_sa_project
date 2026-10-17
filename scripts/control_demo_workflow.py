#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-009 开发态 Gate 1／Gate 2 流程控制内核（纯内存、纯 API、标准库）。

固定四个接口：

    create_dev_workflow(batch_id, run_bindings) -> dict
    prepare_dev_gate(workflow, gate, materials, *, current_bindings) -> dict
    record_dev_decision(workflow, decision, *, current_bindings) -> dict
    check_dev_action(workflow, action, *, current_bindings) -> dict

前三个返回 `{"state": ..., "state_sha256": ...}`；第二、三、四个接收同形 workflow 对象。
`state_sha256` 是对 state 的规范 JSON 指纹（放在外层以避免自引用）。

本模块**不读写文件／数据库／Excel**，不读答案册，不导入上游或测试／QA，不调用 LLM／网络／子进程；
时间与 batch_id 由调用方传入，不自动取当前时间、不生成随机身份；不修改入参，同输入同返回。

所有状态保持 `mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed=false`、
`contract_status=DRAFT_NOT_IN_FORCE`，真实 `gate1_approval`／`gate2_approval` 恒为 `null`；
测试中的模拟决定另列于 `simulated_decisions`，并固定标记 `SIMULATED_TEST_ONLY`。
本模块只核对调用方提交的**内存声明**，不宣称实读了当前磁盘字节，也不提供真实人类认证。

异常：`WorkflowBlocked`（前提／协议／不允许的转移，含字段与原因）；`WorkflowError`（意外错误，保留异常链）。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime

WORKFLOW_VERSION = "TASK-009-workflow-control-1.2"
MODE = "DEVELOPMENT_TEST_ONLY"
CONTRACT_STATUS = "DRAFT_NOT_IN_FORCE"
SIMULATED_ACTOR_KIND = "SIMULATED_HUMAN"
SIMULATION_MARK = "SIMULATED_TEST_ONLY"

GATE1 = "GATE1"
GATE2 = "GATE2"
GATES = (GATE1, GATE2)
PHASE_CREATED = "DEV_CREATED"
PHASE_G1_PENDING = "DEV_GATE1_PENDING"
PHASE_G1_APPROVED = "DEV_GATE1_APPROVED"
PHASE_G2_PENDING = "DEV_GATE2_PENDING"
PHASE_G2_APPROVED = "DEV_GATE2_APPROVED"
HELD_PHASE = {GATE1: "DEV_GATE1_HELD", GATE2: "DEV_GATE2_HELD"}
REJECTED_PHASE = {GATE1: "DEV_GATE1_REJECTED", GATE2: "DEV_GATE2_REJECTED"}
PENDING_PHASE = {GATE1: PHASE_G1_PENDING, GATE2: PHASE_G2_PENDING}
APPROVED_PHASE = {GATE1: PHASE_G1_APPROVED, GATE2: PHASE_G2_APPROVED}
STOP_PHASES = (HELD_PHASE[GATE1], REJECTED_PHASE[GATE1], HELD_PHASE[GATE2], REJECTED_PHASE[GATE2])
KNOWN_PHASES = (PHASE_CREATED, PHASE_G1_PENDING, PHASE_G1_APPROVED, PHASE_G2_PENDING, PHASE_G2_APPROVED) + STOP_PHASES

ACTION_NORMALIZE = "NORMALIZE_AND_LOAD"
ACTION_SCREEN = "SCREEN_AND_BUILD_FACTS"
ACTION_AI = "GENERATE_AI_SUGGESTION"
ACTIONS = (ACTION_NORMALIZE, ACTION_SCREEN, ACTION_AI)
DECISION_APPROVE = "APPROVE"
DECISION_HOLD = "HOLD"
DECISION_REJECT = "REJECT"
DECISIONS = (DECISION_APPROVE, DECISION_HOLD, DECISION_REJECT)
EVENT_CREATED = "WORKFLOW_CREATED"
EVENT_REQUEST = {GATE1: "GATE1_REQUEST", GATE2: "GATE2_REQUEST"}
EVENT_DECISION = {GATE1: "GATE1_DECISION", GATE2: "GATE2_DECISION"}
KNOWN_EVENT_TYPES = (EVENT_CREATED, EVENT_REQUEST[GATE1], EVENT_REQUEST[GATE2],
                     EVENT_DECISION[GATE1], EVENT_DECISION[GATE2])

NET_CHECK_KEYS = (
    "master_net_equals_known_plus_missing",
    "master_net_equals_normalized",
    "known_net_equals_normalized",
    "missing_net_equals_normalized",
    "empty_ap_id_equals_normalized",
    "unknown_ap_id_equals_normalized",
)
REQUIRED_CODE_HASH_KEYS = (
    "control_demo_workflow",
    "receive_demo_batch",
    "check_demo_data",
    "normalize_demo_data",
    "store_demo_sqlite",
    "screen_demo_sqlite",
    "crosscheck_demo_rules",
    "build_demo_fact_packet",
)
REQUIRED_RULE_IDS = ("R01", "R02", "R03", "R04")
FIXED_CONFIG = {
    "company": "澄明商贸有限公司",
    "period_start": "2026-09-01",
    "period_end": "2026-09-30",
    "cutoff_date": "2026-09-30",
    "currency": "CNY",
}
CONFIRMATION_KEY = {GATE1: "scope_and_source_reviewed", GATE2: "reconciliation_reviewed"}
EXPECTED_NORMALIZATION_VERSION = "TASK-004-normalized-1.1"
EXPECTED_LOAD_STATUS = "DEV_SQLITE_VERIFIED"
EXPECTED_STORE_VERSION = "TASK-005-sqlite-load-1.2"
EXPECTED_SCHEMA_VERSION = "demo-schema-1.0"
MONEY_FIELDS = (
    "settled_pay_master_total",
    "settled_pay_allocation_total",
    "settled_refund_master_total",
    "settled_refund_allocation_total",
    "master_net",
    "known_payable_link_net",
    "missing_payable_link_net",
)
ROW_COUNT_TABLES = ("suppliers", "payables", "payments", "allocations")
REQUIRED_RUN_BINDING_KEYS = ("input_sha256", "spec_sha256", "contract_draft_sha256", "code_sha256",
                            "rule_sql_sha256", "config")
REQUIRED_MATERIAL_KEYS = ("batch_id", "gate", "run_bindings_sha256", "scope", "blocking_issues", "evidence")
REQUIRED_SCOPE_KEYS = ("company", "period_start", "period_end", "cutoff_date", "currency",
                       "synthetic_data", "source_description", "known_limitations")
REQUIRED_DECISION_KEYS = ("event_id", "batch_id", "gate", "request_id", "materials_sha256", "decision",
                          "actor_kind", "actor_id", "occurred_at", "reason", "simulation")
REQUEST_KEYS = ("request_id", "gate", "batch_id", "run_bindings_sha256", "materials_sha256", "materials",
                "prior_simulated_decision_sha256", "created_at", "simulation_mark")
DECISION_STORED_KEYS = set(REQUIRED_DECISION_KEYS) | {"confirmations", "decision_sha256"}
HISTORY_REQUIRED_KEYS = ("seq", "event_id", "event_type", "phase_before", "phase_after")
EVENT_COMMON_KEYS = {"seq", "event_id", "event_type", "phase_before", "phase_after"}
EVENT_EXTRA_KEYS = {
    EVENT_CREATED: ("gate", "batch_id", "run_bindings_sha256"),
    EVENT_REQUEST[GATE1]: ("gate", "request_id", "materials_sha256", "run_bindings_sha256",
                           "gate1_decision_sha256"),
    EVENT_REQUEST[GATE2]: ("gate", "request_id", "materials_sha256", "run_bindings_sha256",
                           "gate1_decision_sha256"),
    EVENT_DECISION[GATE1]: ("gate", "request_id", "materials_sha256", "decision", "decision_sha256"),
    EVENT_DECISION[GATE2]: ("gate", "request_id", "materials_sha256", "decision", "decision_sha256"),
}
BOUNDARIES = [
    "本模块是开发态流程控制内核，不构成正式契约，也不构成任何 Gate 的真实批准。",
    "simulated_decisions 中的条目固定标记 SIMULATED_TEST_ONLY，只是可检查的身份声明，不是真实人类认证。",
    "真实 gate1_approval／gate2_approval 恒为 null；本模块没有正式批准接口。",
    "本层只核对调用方提交的内存声明，不宣称实读了当前磁盘字节，也不抵御同权限篡改。",
    "history 是本次调用链的有序记录，不做持久化，也不声称不可篡改。",
]
HASH_PATTERN = re.compile(r"\A[0-9a-f]{64}\Z")


class WorkflowBlocked(Exception):
    """前提、协议或不允许的转移；带字段与原因。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


class WorkflowError(Exception):
    """意外运行失败；保留阶段、原始原因与异常链。"""

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or [message]


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def canonical_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(payload) -> str:
    try:
        text = canonical_json(payload)
    except (TypeError, ValueError) as exc:
        raise WorkflowBlocked(f"对象无法按规范 JSON 序列化：{type(exc).__name__}: {exc}") from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require(condition: bool, path: str, reason: str) -> None:
    if not condition:
        raise WorkflowBlocked(f"字段 {path} 不可用：{reason}")


def _require_str(value, path: str, label: str = "必须是非空字符串") -> str:
    _require(isinstance(value, str), path, f"{label}，实际 {type(value).__name__}")
    _require(value.strip() != "", path, "不能为空白")
    return value


def _require_hash(value, path: str) -> str:
    _require(isinstance(value, str) and bool(HASH_PATTERN.fullmatch(value)), path,
             "必须是完整 64 位十六进制哈希")
    return value


def _require_bool_true(value, path: str, label: str) -> None:
    _require(value is True, path, f"{label}必须严格为 true（不接受真值等价）")


def _require_plain_object(value, path: str) -> dict:
    _require(isinstance(value, dict), path, f"必须是对象，实际 {type(value).__name__}")
    return value


# ---------------------------------------------------------------------------
# run_bindings
# ---------------------------------------------------------------------------


def _check_run_bindings(run_bindings) -> dict:
    _require_plain_object(run_bindings, "run_bindings")
    for key in REQUIRED_RUN_BINDING_KEYS:
        _require(key in run_bindings, f"run_bindings.{key}", "缺少必需键")
    for key in ("input_sha256", "spec_sha256", "contract_draft_sha256"):
        _require_hash(run_bindings[key], f"run_bindings.{key}")
    code_sha256 = _require_plain_object(run_bindings["code_sha256"], "run_bindings.code_sha256")
    for key in REQUIRED_CODE_HASH_KEYS:
        _require(key in code_sha256, f"run_bindings.code_sha256.{key}", "缺少必需代码哈希")
        _require_hash(code_sha256[key], f"run_bindings.code_sha256.{key}")
    rule_sql = _require_plain_object(run_bindings["rule_sql_sha256"], "run_bindings.rule_sql_sha256")
    for rule_id in REQUIRED_RULE_IDS:
        _require(rule_id in rule_sql, f"run_bindings.rule_sql_sha256.{rule_id}", "缺少规则 SQL 哈希")
        _require_hash(rule_sql[rule_id], f"run_bindings.rule_sql_sha256.{rule_id}")
    config = _require_plain_object(run_bindings["config"], "run_bindings.config")
    for key, expected in FIXED_CONFIG.items():
        _require(config.get(key) == expected, f"run_bindings.config.{key}",
                 f"必须是本项目固定值 {expected!r}，实际 {config.get(key)!r}")
    return copy.deepcopy(run_bindings)


# ---------------------------------------------------------------------------
# workflow 校验与重放
# ---------------------------------------------------------------------------


def _decision_body(recorded: dict) -> dict:
    """剥离派生字段 decision_sha256，得到用于核验与计算指纹的决定正文。"""
    return {key: value for key, value in recorded.items() if key != "decision_sha256"}


def _check_decision_fields(decision, *, gate: str, batch_id: str, request: dict,
                           known_event_ids, path: str) -> dict:
    """决定正文协议校验；首次 record 与 replay 复用同一套约束。"""
    _require(isinstance(decision, dict), path, f"必须是对象，实际 {type(decision).__name__}")
    unknown = sorted(set(decision.keys()) - set(REQUIRED_DECISION_KEYS) - {"confirmations"})
    _require(not unknown, path, f"含未知字段 {unknown}")
    for key in REQUIRED_DECISION_KEYS:
        _require(key in decision, f"{path}.{key}", "缺少必需字段")
    event_id = _require_str(decision["event_id"], f"{path}.event_id")
    _require(event_id not in known_event_ids, f"{path}.event_id", "事件标识与既有历史重复")
    _require(decision["batch_id"] == batch_id, f"{path}.batch_id", "必须与 workflow 批次一致")
    _require(decision["gate"] == gate, f"{path}.gate", f"必须是当前待决定的 {gate}")
    _require(decision["request_id"] == request["request_id"], f"{path}.request_id", "必须引用当前请求")
    _require(decision["materials_sha256"] == request["materials_sha256"], f"{path}.materials_sha256",
             "必须引用当前请求材料指纹")
    _require(decision["decision"] in DECISIONS, f"{path}.decision",
             f"必须是 {list(DECISIONS)}，实际 {decision['decision']!r}")
    _require(decision["actor_kind"] == SIMULATED_ACTOR_KIND, f"{path}.actor_kind",
             f"必须是 {SIMULATED_ACTOR_KIND}（AI／SYSTEM 等不被接受），实际 {decision['actor_kind']!r}")
    _require_str(decision["actor_id"], f"{path}.actor_id", "模拟身份必须是非空白字符串")
    occurred_at = _require_str(decision["occurred_at"], f"{path}.occurred_at",
                               "必须是非空白字符串（带时区 ISO 日期时间）")
    try:
        moment = datetime.fromisoformat(occurred_at)
    except ValueError as exc:
        raise WorkflowBlocked(f"字段 {path}.occurred_at 不可用：必须是 ISO 日期时间（{exc}）") from exc
    _require(moment.tzinfo is not None and moment.utcoffset() is not None, f"{path}.occurred_at",
             "必须带时区信息")
    _require_str(decision["reason"], f"{path}.reason", "决定说明必须是非空白字符串")
    _require(decision["simulation"] == SIMULATION_MARK, f"{path}.simulation",
             f"必须固定标记 {SIMULATION_MARK}，实际 {decision['simulation']!r}")
    confirmations = decision.get("confirmations")
    if decision["decision"] == DECISION_APPROVE:
        _require(isinstance(confirmations, dict), f"{path}.confirmations", "APPROVE 必须提供确认项")
        key = CONFIRMATION_KEY[gate]
        _require(key in confirmations, f"{path}.confirmations.{key}", "缺少必需的确认项")
        _require_bool_true(confirmations[key], f"{path}.confirmations.{key}", f"确认项 {key}")
    elif confirmations is not None:
        _require(isinstance(confirmations, dict), f"{path}.confirmations",
                 f"必须是对象，实际 {type(confirmations).__name__}")
    return copy.deepcopy(decision)


def _check_request_shape(request, path: str) -> None:
    """请求容器与必需字段的形状校验（先检后用，避免 KeyError／AttributeError）。"""
    _require(isinstance(request, dict), path, f"必须是对象，实际 {type(request).__name__}")
    unknown = sorted(set(request.keys()) - set(REQUEST_KEYS))
    _require(not unknown, path, f"含未知字段 {unknown}")
    for key in REQUEST_KEYS:
        _require(key in request, f"{path}.{key}", "缺少必需键")
    _require_str(request["request_id"], f"{path}.request_id")
    _require(request["gate"] in GATES, f"{path}.gate", f"必须是 {list(GATES)}，实际 {request['gate']!r}")
    _require_str(request["batch_id"], f"{path}.batch_id")
    _require_hash(request["run_bindings_sha256"], f"{path}.run_bindings_sha256")
    _require_hash(request["materials_sha256"], f"{path}.materials_sha256")
    _require(isinstance(request["materials"], dict), f"{path}.materials",
             f"必须是对象，实际 {type(request['materials']).__name__}")
    prior = request["prior_simulated_decision_sha256"]
    if prior is not None:
        _require_hash(prior, f"{path}.prior_simulated_decision_sha256")
    _require(request["simulation_mark"] == SIMULATION_MARK, f"{path}.simulation_mark",
             f"必须固定标记 {SIMULATION_MARK}")
    created_at = request["created_at"]
    _require(created_at is None or isinstance(created_at, str), f"{path}.created_at",
             "必须是字符串或 null")


def _request_id_for(state: dict, gate: str, materials_sha256: str, prior_decision_sha256) -> str:
    """按原有确定性公式重算 request_id。"""
    digest = canonical_sha256({
        "batch_id": state["batch_id"],
        "gate": gate,
        "run_bindings_sha256": state["run_bindings_sha256"],
        "materials_sha256": materials_sha256,
        "prior_decision_sha256": prior_decision_sha256,
    })
    return f"{gate}/{state['batch_id']}/{digest[:24]}"


def _replay_history(state: dict) -> tuple:
    """按 history 重放，校验容器形状、事件顺序与既有协议，返回权威 (phase, requests, decisions)。"""
    history = state["history"]
    _require(isinstance(history, list) and history, "state.history", "必须是非空列表")
    stored_decisions = state["simulated_decisions"]
    _require(isinstance(stored_decisions, list), "state.simulated_decisions", "必须是列表")
    for position, item in enumerate(stored_decisions):
        path = f"state.simulated_decisions[{position}]"
        _require(isinstance(item, dict), path, f"条目必须是对象，实际 {type(item).__name__}")
        for key in (*REQUIRED_DECISION_KEYS, "decision_sha256"):
            _require(key in item, f"{path}.{key}", "缺少必需键")
        unknown = sorted(set(item.keys()) - DECISION_STORED_KEYS)
        _require(not unknown, path, f"含未知字段 {unknown}")
        _require_hash(item["decision_sha256"], f"{path}.decision_sha256")
    _require_plain_object(state["requests"], "state.requests")
    _require(set(state["requests"].keys()) == set(GATES), "state.requests",
             f"必须恰含 {sorted(GATES)}")
    for gate in GATES:
        placeholder = state["requests"][gate]
        if placeholder is not None:
            _check_request_shape(placeholder, f"state.requests.{gate}")

    phase = PHASE_CREATED
    requests: dict = {GATE1: None, GATE2: None}
    decisions: list = []
    recorded_decisions_in_order: list = []
    seen_event_ids: set = set()
    seen_gate_decision: set = set()
    for position, event in enumerate(history):
        path = f"state.history[{position}]"
        _require(isinstance(event, dict), path, f"条目必须是对象，实际 {type(event).__name__}")
        for key in HISTORY_REQUIRED_KEYS:
            _require(key in event, f"{path}.{key}", "缺少必需键")
        seq = event["seq"]
        _require(_is_int(seq), f"{path}.seq",
                 f"必须是整数（不接受 bool／浮点等数值等价类型），实际 {type(seq).__name__}={seq!r}")
        _require(seq == position + 1, f"{path}.seq", f"必须是从 1 递增的连续序号，实际 {seq!r}")
        event_id = _require_str(event["event_id"], f"{path}.event_id")
        _require(event_id not in seen_event_ids, f"{path}.event_id", "事件标识与既有历史重复")
        prior_event_ids = set(seen_event_ids)
        seen_event_ids.add(event_id)
        event_type = event.get("event_type")
        _require(event_type in KNOWN_EVENT_TYPES, f"{path}.event_type", f"未知事件类型 {event_type!r}")
        for key in EVENT_EXTRA_KEYS[event_type]:
            _require(key in event, f"{path}.{key}", "缺少该事件类型必需字段")
        unexpected = sorted(set(event.keys()) - EVENT_COMMON_KEYS - set(EVENT_EXTRA_KEYS[event_type]))
        _require(not unexpected, path, f"含该事件类型不应有的字段 {unexpected}")
        if event_type == EVENT_CREATED:
            _require(event.get("phase_before") is None, f"{path}.phase_before", "首个事件之前没有状态")
            _require(position == 0, path, "WORKFLOW_CREATED 只能是第一个事件")
            _require(event.get("gate") is None, f"{path}.gate", "创建事件的 gate 必须是 null")
            _require(event.get("batch_id") == state["batch_id"], f"{path}.batch_id",
                     f"必须与 state.batch_id 一致：{event.get('batch_id')!r} != {state['batch_id']!r}")
            _require(event.get("run_bindings_sha256") == state["run_bindings_sha256"],
                     f"{path}.run_bindings_sha256", "必须与 state.run_bindings_sha256 一致")
            phase_after = PHASE_CREATED
        elif event_type in (EVENT_REQUEST[GATE1], EVENT_REQUEST[GATE2]):
            _require(event.get("phase_before") == phase, f"{path}.phase_before",
                     f"与重放状态不符：期望 {phase}，实际 {event.get('phase_before')!r}")
            gate = GATE1 if event_type == EVENT_REQUEST[GATE1] else GATE2
            _require(event.get("gate") == gate, f"{path}.gate",
                     f"必须与 event_type 所指的 {gate} 一致，实际 {event.get('gate')!r}")
            expected_phase = PHASE_CREATED if gate == GATE1 else PHASE_G1_APPROVED
            _require(phase == expected_phase, f"{path}.event_type",
                     f"{gate} 请求只能从 {expected_phase} 建立，当前 {phase}")
            _require(requests[gate] is None, f"{path}.event_type", f"{gate} 请求重复")
            request = requests[gate] if requests[gate] is not None else state["requests"].get(gate)
            _check_request_shape(request, f"state.requests.{gate}")
            _require(event.get("request_id") == request["request_id"], f"{path}.request_id",
                     "必须与 state.requests 中的请求一致")
            _require(event.get("materials_sha256") == request["materials_sha256"],
                     f"{path}.materials_sha256", "必须与请求材料指纹一致")
            _require(event.get("run_bindings_sha256") == request["run_bindings_sha256"],
                     f"{path}.run_bindings_sha256",
                     "必须与对应已验证请求的运行绑定指纹一致")
            _require(canonical_sha256(request["materials"]) == request["materials_sha256"],
                     f"state.requests.{gate}.materials_sha256", "必须等于请求内材料的规范指纹")
            _require(request["gate"] == gate, f"state.requests.{gate}.gate", f"必须是 {gate}")
            _require(request["batch_id"] == state["batch_id"], f"state.requests.{gate}.batch_id",
                     "必须与 workflow 批次一致")
            _require(request["run_bindings_sha256"] == state["run_bindings_sha256"],
                     f"state.requests.{gate}.run_bindings_sha256", "必须与创建时绑定指纹一致")
            _check_materials(request["materials"], gate, state)
            if gate == GATE2:
                approved = next((item for item in decisions
                                 if item["gate"] == GATE1 and item["decision"] == DECISION_APPROVE), None)
                _require(approved is not None, f"{path}.gate1_decision_sha256",
                         "Gate2 请求必须绑定 Gate1 已批准的模拟决定")
                approved_fingerprint = canonical_sha256(approved)
                _require(event.get("gate1_decision_sha256") == approved_fingerprint,
                         f"{path}.gate1_decision_sha256",
                         "必须绑定本 workflow Gate1 已批准决定正文的实际指纹")
                _require(request["prior_simulated_decision_sha256"] == approved_fingerprint,
                         f"state.requests.{gate}.prior_simulated_decision_sha256",
                         "必须等于本 workflow Gate1 已批准决定正文的实际指纹")
            else:
                _require(request["prior_simulated_decision_sha256"] is None,
                         f"state.requests.{gate}.prior_simulated_decision_sha256",
                         "Gate1 请求不应有前序决定")
            expected_request_id = _request_id_for(state, gate, request["materials_sha256"],
                                                  request["prior_simulated_decision_sha256"])
            _require(request["request_id"] == expected_request_id, f"state.requests.{gate}.request_id",
                     f"必须等于按原公式重算的确定性请求 ID：{expected_request_id}")
            requests[gate] = request
            phase_after = PENDING_PHASE[gate]
        else:
            _require(event.get("phase_before") == phase, f"{path}.phase_before",
                     f"与重放状态不符：期望 {phase}，实际 {event.get('phase_before')!r}")
            gate = GATE1 if event_type == EVENT_DECISION[GATE1] else GATE2
            _require(event.get("gate") == gate, f"{path}.gate",
                     f"必须与 event_type 所指的 {gate} 一致，实际 {event.get('gate')!r}")
            _require(phase == PENDING_PHASE[gate], f"{path}.event_type",
                     f"{gate} 决定只能在 {PENDING_PHASE[gate]} 记录，当前 {phase}")
            _require(gate not in seen_gate_decision, f"{path}.event_type", f"{gate} 已有决定")
            request = requests[gate]
            _require(isinstance(request, dict), f"state.requests.{gate}", "当前请求缺失")
            _require(event.get("request_id") == request["request_id"], f"{path}.request_id",
                     "必须与对应已验证请求一致")
            _require(event.get("materials_sha256") == request["materials_sha256"],
                     f"{path}.materials_sha256", "必须与对应已验证请求的材料指纹一致")
            recorded = event.get("decision")
            _require(isinstance(recorded, dict), f"{path}.decision",
                     f"必须是对象，实际 {type(recorded).__name__}")
            unknown = sorted(set(recorded.keys()) - DECISION_STORED_KEYS)
            _require(not unknown, f"{path}.decision", f"含未知字段 {unknown}")
            for key in (*REQUIRED_DECISION_KEYS, "decision_sha256"):
                _require(key in recorded, f"{path}.decision.{key}", "缺少必需键")
            body = _decision_body(recorded)
            _require(event.get("event_id") == body.get("event_id"), f"{path}.event_id",
                     f"事件顶层 event_id 必须与决定正文一致：{event.get('event_id')!r} != {body.get('event_id')!r}")
            _require(body.get("gate") == gate, f"{path}.decision.gate",
                     f"决定正文 gate 必须与事件一致：{body.get('gate')!r} != {gate!r}")
            _require(body.get("request_id") == request["request_id"], f"{path}.decision.request_id",
                     "决定正文必须引用对应已验证请求")
            _require(body.get("materials_sha256") == request["materials_sha256"],
                     f"{path}.decision.materials_sha256", "决定正文必须引用对应请求材料指纹")
            actual_fingerprint = canonical_sha256(body)
            _require(recorded["decision_sha256"] == actual_fingerprint, f"{path}.decision.decision_sha256",
                     "必须等于决定正文（不含该派生字段）的实际规范指纹")
            _require_hash(event.get("decision_sha256"), f"{path}.decision_sha256")
            _require(event["decision_sha256"] == actual_fingerprint, f"{path}.decision_sha256",
                     "事件顶层决定指纹必须等于决定正文的实际规范指纹")
            _check_decision_fields(body, gate=gate, batch_id=state["batch_id"], request=request,
                                   known_event_ids=prior_event_ids, path=f"{path}.decision")
            matched = next((item for item in stored_decisions
                            if item.get("event_id") == body["event_id"]), None)
            _require(matched is not None, f"{path}.decision",
                     "必须在 state.simulated_decisions 中有对应记录")
            consumed_decision_ids_matched = matched is not None
            _require(consumed_decision_ids_matched, f"{path}.decision",
                     "必须在 state.simulated_decisions 中有对应记录")
            _require(canonical_json(matched) == canonical_json(recorded), f"{path}.decision",
                     "必须与 state.simulated_decisions 中的记录严格一致")
            recorded_decisions_in_order.append(recorded)
            decisions.append(body)
            seen_gate_decision.add(gate)
            chosen = body["decision"]
            phase_after = (APPROVED_PHASE[gate] if chosen == DECISION_APPROVE
                           else HELD_PHASE[gate] if chosen == DECISION_HOLD else REJECTED_PHASE[gate])
        _require(event.get("phase_after") == phase_after, f"{path}.phase_after",
                 f"与重放结果不符：期望 {phase_after}，实际 {event.get('phase_after')!r}")
        _require(phase_after not in STOP_PHASES or position == len(history) - 1, path,
                 "停止态不能有后续事件")
        phase = phase_after
    _require(len(decisions) == len(stored_decisions), "state.simulated_decisions",
             f"决定数量与 history 不一致：{len(stored_decisions)} vs {len(decisions)}")
    for position, expected_record in enumerate(recorded_decisions_in_order):
        _require(canonical_json(stored_decisions[position]) == canonical_json(expected_record),
                 f"state.simulated_decisions[{position}]",
                 "必须按 history 次序与决定事件记录的完整记录逐项一致（不得重排）")
    for gate in GATES:
        stored_request = state["requests"][gate]
        replayed_request = requests[gate]
        _require((stored_request is None) == (replayed_request is None), f"state.requests.{gate}",
                 "必须与 history 重放结果一一对应：不得存在无 history 事件的额外请求或缺少实际请求")
        if stored_request is not None:
            _require(canonical_json(stored_request) == canonical_json(replayed_request),
                     f"state.requests.{gate}",
                     "state.requests 实际保存的对象必须与按 history 重放得到的请求逐项一致")
    return phase, requests, decisions


def _validate_workflow(workflow, current_bindings) -> tuple:
    _require_plain_object(workflow, "workflow")
    _require(set(workflow.keys()) == {"state", "state_sha256"}, "workflow",
             f"只接受 state／state_sha256 两个键，实际 {sorted(workflow.keys())}")
    state = _require_plain_object(workflow["state"], "workflow.state")
    _require(workflow["state_sha256"] == canonical_sha256(state), "workflow.state_sha256",
             "外层的 state_sha256 必须等于 state 的规范指纹")
    for key in ("workflow_version", "mode", "contract_status", "next_step_allowed", "batch_id",
                "run_bindings", "run_bindings_sha256", "phase", "requests", "simulated_decisions",
                "history", "gate1_approval", "gate2_approval"):
        _require(key in state, f"workflow.state.{key}", "缺少必需键")
    _require(state["workflow_version"] == WORKFLOW_VERSION, "workflow.state.workflow_version",
             f"必须是 {WORKFLOW_VERSION}，实际 {state['workflow_version']!r}")
    _require(state["mode"] == MODE, "workflow.state.mode", f"必须是 {MODE}，实际 {state['mode']!r}")
    _require(state["contract_status"] == CONTRACT_STATUS, "workflow.state.contract_status",
             f"必须是 {CONTRACT_STATUS}，实际 {state['contract_status']!r}")
    _require(state["next_step_allowed"] is False, "workflow.state.next_step_allowed", "必须严格为 false")
    _require(state["gate1_approval"] is None, "workflow.state.gate1_approval", "真实批准必须恒为 null")
    _require(state["gate2_approval"] is None, "workflow.state.gate2_approval", "真实批准必须恒为 null")
    _require_str(state["batch_id"], "workflow.state.batch_id", "必须是非空白字符串（保留原值）")
    _check_run_bindings(state["run_bindings"])
    _require(state["run_bindings_sha256"] == canonical_sha256(state["run_bindings"]),
             "workflow.state.run_bindings_sha256", "必须等于 run_bindings 的规范指纹")
    _require_plain_object(state["requests"], "workflow.state.requests")
    _require(set(state["requests"].keys()) == set(GATES), "workflow.state.requests",
             f"必须恰含 {sorted(GATES)}")
    _require(isinstance(state["simulated_decisions"], list), "workflow.state.simulated_decisions", "必须是列表")
    _require(state["phase"] in KNOWN_PHASES, "workflow.state.phase",
             f"未知状态 {state['phase']!r}")
    replay_phase, requests, decisions = _replay_history(state)
    _require(state["phase"] == replay_phase, "workflow.state.phase",
             f"与 history 重放不符：state 写 {state['phase']}，重放为 {replay_phase}")

    _require_plain_object(current_bindings, "current_bindings")
    if canonical_json(current_bindings) != canonical_json(state["run_bindings"]):
        raise WorkflowBlocked(
            "字段 current_bindings 不可用：与创建时绑定的 run_bindings 不一致；"
            "绑定变化后不得复用旧 workflow／旧模拟批准，请建立新 workflow／新批次",
            ["绑定差异路径需由调用方比对；本层只做完整规范对象比较"],
        )
    return copy.deepcopy(state), replay_phase, requests, decisions


def _build_state(state: dict, phase: str, history_event: dict) -> dict:
    new_state = copy.deepcopy(state)
    new_state["history"] = list(state["history"]) + [history_event]
    new_state["phase"] = phase
    return new_state


def _result(state: dict) -> dict:
    return {"state": copy.deepcopy(state), "state_sha256": canonical_sha256(state)}


# ---------------------------------------------------------------------------
# 1. create_dev_workflow
# ---------------------------------------------------------------------------


def create_dev_workflow(batch_id, run_bindings) -> dict:
    """创建首个状态 DEV_CREATED（仅本接口能创建首态）。"""
    try:
        _require_str(batch_id, "batch_id", "必须是非空白字符串（保留原值，不做数值化）")
        bindings = _check_run_bindings(run_bindings)
        state = {
            "workflow_version": WORKFLOW_VERSION,
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "next_step_allowed": False,
            "batch_id": batch_id,
            "run_bindings": bindings,
            "run_bindings_sha256": canonical_sha256(bindings),
            "phase": PHASE_CREATED,
            "requests": {GATE1: None, GATE2: None},
            "simulated_decisions": [],
            "gate1_approval": None,
            "gate2_approval": None,
            "boundaries": list(BOUNDARIES),
            "history": [],
        }
        event = {
            "seq": 1,
            "event_id": f"EVT-{canonical_sha256({'batch_id': batch_id, 'phase': PHASE_CREATED})[:24]}",
            "event_type": EVENT_CREATED,
            "gate": None,
            "batch_id": batch_id,
            "run_bindings_sha256": state["run_bindings_sha256"],
            "phase_before": None,
            "phase_after": PHASE_CREATED,
        }
        state["history"] = [event]
        return _result(state)
    except WorkflowBlocked:
        raise
    except Exception as exc:  # noqa: BLE001 - 统一保留阶段与异常链
        raise WorkflowError(f"[create] 创建 workflow 失败：{type(exc).__name__}: {exc}",
                            ["阶段=create", f"原始异常={type(exc).__name__}: {exc}"]) from exc


# ---------------------------------------------------------------------------
# 2. prepare_dev_gate
# ---------------------------------------------------------------------------


def _check_scope(scope, path: str) -> None:
    _require_plain_object(scope, path)
    for key in REQUIRED_SCOPE_KEYS:
        _require(key in scope, f"{path}.{key}", "缺少必需键")
    for key, expected in FIXED_CONFIG.items():
        _require(scope[key] == expected, f"{path}.{key}",
                 f"必须是本项目固定范围 {expected!r}，实际 {scope[key]!r}")
    _require_bool_true(scope["synthetic_data"], f"{path}.synthetic_data", "合成数据标志")
    _require_str(scope["source_description"], f"{path}.source_description", "来源描述必须是非空字符串")
    limitations = scope["known_limitations"]
    _require(isinstance(limitations, list), f"{path}.known_limitations", "必须是列表")
    for position, item in enumerate(limitations):
        _require_str(item, f"{path}.known_limitations[{position}]", "限制说明必须是非空字符串")


def _check_quality_report(quality, path: str, bindings: dict) -> None:
    _require_plain_object(quality, path)
    _require(quality.get("result") == "pass", f"{path}.result",
             f"必须严格为 pass，实际 {quality.get('result')!r}")
    issues = quality.get("issues")
    _require(isinstance(issues, list), f"{path}.issues", "必须存在且为列表")
    _require(not issues, f"{path}.issues", f"必须为空列表，实际 {issues!r}")
    counts = quality.get("issue_counts_by_code")
    _require(isinstance(counts, dict), f"{path}.issue_counts_by_code", "必须存在且为对象")
    _require(not counts, f"{path}.issue_counts_by_code", f"必须为空对象，实际 {counts!r}")
    workbook = _require_plain_object(quality.get("workbook"), f"{path}.workbook")
    _require(workbook.get("sha256") == bindings["input_sha256"], f"{path}.workbook.sha256",
             "必须与 run_bindings.input_sha256 一致")
    checker = _require_plain_object(quality.get("checker"), f"{path}.checker")
    _require(checker.get("sha256") == bindings["code_sha256"]["check_demo_data"],
             f"{path}.checker.sha256", "必须与 run_bindings.code_sha256.check_demo_data 一致")


def _check_gate2_evidence(evidence: dict, bindings: dict) -> None:
    normalized = _require_plain_object(evidence.get("normalized"), "materials.evidence.normalized")
    load_report = _require_plain_object(evidence.get("load_report"), "materials.evidence.load_report")
    _require(normalized.get("mode") == MODE, "materials.evidence.normalized.mode",
             f"必须是 {MODE}，实际 {normalized.get('mode')!r}")
    _require(normalized.get("next_step_allowed") is False, "materials.evidence.normalized.next_step_allowed",
             "必须严格为 false")
    _require(normalized.get("normalization_version") == EXPECTED_NORMALIZATION_VERSION,
             "materials.evidence.normalized.normalization_version",
             f"必须是 {EXPECTED_NORMALIZATION_VERSION}，实际 {normalized.get('normalization_version')!r}")
    quality = _require_plain_object(normalized.get("quality_report"), "materials.evidence.normalized.quality_report")
    _require(quality.get("result") == "pass", "materials.evidence.normalized.quality_report.result",
             f"必须严格为 pass，实际 {quality.get('result')!r}")
    counts = quality.get("issue_counts_by_code")
    _require(isinstance(counts, dict), "materials.evidence.normalized.quality_report.issue_counts_by_code",
             "必须存在且为对象")
    _require(not counts, "materials.evidence.normalized.quality_report.issue_counts_by_code",
             f"必须为空对象，实际 {counts!r}")

    _require(load_report.get("mode") == MODE, "materials.evidence.load_report.mode",
             f"必须是 {MODE}，实际 {load_report.get('mode')!r}")
    _require(load_report.get("next_step_allowed") is False, "materials.evidence.load_report.next_step_allowed",
             "必须严格为 false")
    _require(load_report.get("batch_status") == EXPECTED_LOAD_STATUS, "materials.evidence.load_report.batch_status",
             f"必须是 {EXPECTED_LOAD_STATUS}，实际 {load_report.get('batch_status')!r}")
    _require(load_report.get("store_version") == EXPECTED_STORE_VERSION,
             "materials.evidence.load_report.store_version",
             f"必须是 {EXPECTED_STORE_VERSION}，实际 {load_report.get('store_version')!r}")
    _require(load_report.get("schema_version") == EXPECTED_SCHEMA_VERSION,
             "materials.evidence.load_report.schema_version",
             f"必须是 {EXPECTED_SCHEMA_VERSION}，实际 {load_report.get('schema_version')!r}")
    _require_bool_true(load_report.get("round_trip_exact"), "materials.evidence.load_report.round_trip_exact",
                       "往返一致性标志")
    _require_bool_true(load_report.get("event_allocation_balanced"),
                       "materials.evidence.load_report.event_allocation_balanced", "事件分摊平衡标志")
    _require(load_report.get("foreign_key_check") == "clean", "materials.evidence.load_report.foreign_key_check",
             f"必须是 clean，实际 {load_report.get('foreign_key_check')!r}")
    _require(load_report.get("integrity_check") == "ok", "materials.evidence.load_report.integrity_check",
             f"必须是 ok，实际 {load_report.get('integrity_check')!r}")
    net_checks = _require_plain_object(load_report.get("net_checks"), "materials.evidence.load_report.net_checks")
    for key in NET_CHECK_KEYS:
        _require(key in net_checks, f"materials.evidence.load_report.net_checks.{key}", "缺少必需勾稽项")
        _require_bool_true(net_checks[key], f"materials.evidence.load_report.net_checks.{key}", f"勾稽项 {key}")

    expected_fingerprint = canonical_sha256(normalized)
    _require(load_report.get("normalized_payload_sha256") == expected_fingerprint,
             "materials.evidence.load_report.normalized_payload_sha256",
             "必须等于本次 normalized 对象的规范指纹")
    normalized_source = _require_plain_object(normalized.get("source"), "materials.evidence.normalized.source")
    load_source = _require_plain_object(load_report.get("source"), "materials.evidence.load_report.source")
    _require(normalized_source.get("input_sha256") == bindings["input_sha256"],
             "materials.evidence.normalized.source.input_sha256", "必须与 run_bindings.input_sha256 一致")
    _require(load_source.get("input_sha256") == normalized_source.get("input_sha256"),
             "materials.evidence.load_report.source.input_sha256", "必须与 normalized 来源哈希一致")

    tables = _require_plain_object(normalized.get("tables"), "materials.evidence.normalized.tables")
    row_counts = _require_plain_object(load_report.get("row_counts"), "materials.evidence.load_report.row_counts")
    for table in ROW_COUNT_TABLES:
        table_payload = _require_plain_object(tables.get(table), f"materials.evidence.normalized.tables.{table}")
        records = table_payload.get("records")
        _require(isinstance(records, list), f"materials.evidence.normalized.tables.{table}.records", "必须是列表")
        observed = row_counts.get(table)
        _require(_is_int(observed), f"materials.evidence.load_report.row_counts.{table}",
                 f"必须是非负整数（不接受 bool／浮点等数值等价类型），实际 "
                 f"{type(observed).__name__}={observed!r}")
        _require(observed >= 0, f"materials.evidence.load_report.row_counts.{table}",
                 f"必须是非负整数，实际 {observed!r}")
        _require(observed == len(records), f"materials.evidence.load_report.row_counts.{table}",
                 f"必须等于 normalized 记录数 {len(records)}，实际 {observed!r}")

    reconciliation = _require_plain_object(normalized.get("amount_reconciliation"),
                                           "materials.evidence.normalized.amount_reconciliation")
    for field in MONEY_FIELDS:
        _require(field in load_report, f"materials.evidence.load_report.{field}", "缺少必需金额字段")
        _require(_is_int(load_report[field]), f"materials.evidence.load_report.{field}",
                 f"必须是整数分（非 bool），实际 {type(load_report[field]).__name__}")
        _require(field in reconciliation, f"materials.evidence.normalized.amount_reconciliation.{field}",
                 "缺少必需金额字段")
        _require(_is_int(reconciliation[field]), f"materials.evidence.normalized.amount_reconciliation.{field}",
                 f"必须是整数分（非 bool），实际 {type(reconciliation[field]).__name__}")
        _require(load_report[field] == reconciliation[field],
                 f"materials.evidence.load_report.{field}", "必须与 normalized.amount_reconciliation 一致")
    _require(load_report["settled_pay_master_total"] == load_report["settled_pay_allocation_total"],
             "materials.evidence.load_report.settled_pay_master_total", "主表付款必须等于付款分摊合计")
    _require(load_report["settled_refund_master_total"] == load_report["settled_refund_allocation_total"],
             "materials.evidence.load_report.settled_refund_master_total", "主表退款必须等于退款分摊合计")
    _require(load_report["master_net"] == load_report["known_payable_link_net"] + load_report["missing_payable_link_net"],
             "materials.evidence.load_report.master_net", "资金净额必须等于已知加缺失关联净额")


def _check_materials(materials, gate: str, state: dict) -> dict:
    path = "materials"
    _require_plain_object(materials, path)
    for key in REQUIRED_MATERIAL_KEYS:
        _require(key in materials, f"{path}.{key}", "缺少必需键")
    _require(materials["batch_id"] == state["batch_id"], f"{path}.batch_id", "必须与 workflow 批次一致")
    _require(materials["gate"] == gate, f"{path}.gate", f"必须是 {gate}")
    _require(materials["run_bindings_sha256"] == state["run_bindings_sha256"],
             f"{path}.run_bindings_sha256", "必须与创建时绑定指纹一致")
    _check_scope(materials["scope"], f"{path}.scope")
    blocking = materials["blocking_issues"]
    _require(isinstance(blocking, list), f"{path}.blocking_issues", "必须是列表")
    _require(not blocking, f"{path}.blocking_issues",
             f"存在阻断问题，不能生成可批准请求：{blocking!r}")
    evidence = _require_plain_object(materials["evidence"], f"{path}.evidence")
    bindings = state["run_bindings"]
    if gate == GATE1:
        _check_quality_report(evidence.get("quality_report"), f"{path}.evidence.quality_report", bindings)
    else:
        _check_gate2_evidence(evidence, bindings)
    return copy.deepcopy(materials)


def prepare_dev_gate(workflow, gate, materials, *, current_bindings) -> dict:
    """建立某个 Gate 的守门请求并进入对应 PENDING（CREATED→Gate1；GATE1_APPROVED→Gate2）。"""
    try:
        state, phase, requests, decisions = _validate_workflow(workflow, current_bindings)
        _require(gate in GATES, "gate", f"必须是 {list(GATES)}，实际 {gate!r}")
        expected_phase = PHASE_CREATED if gate == GATE1 else PHASE_G1_APPROVED
        _require(phase == expected_phase, "workflow.state.phase",
                 f"{gate} 只能从 {expected_phase} 建立请求，当前 {phase}")
        checked_materials = _check_materials(materials, gate, state)
        materials_sha256 = canonical_sha256(checked_materials)
        prior_decision_sha256 = None
        if gate == GATE2:
            approved = next((item for item in decisions
                             if item["gate"] == GATE1 and item["decision"] == DECISION_APPROVE), None)
            _require(approved is not None, "workflow.simulated_decisions",
                     "Gate2 请求必须绑定 Gate1 已批准的模拟决定")
            prior_decision_sha256 = canonical_sha256(approved)
        digest = canonical_sha256({
            "batch_id": state["batch_id"],
            "gate": gate,
            "run_bindings_sha256": state["run_bindings_sha256"],
            "materials_sha256": materials_sha256,
            "prior_decision_sha256": prior_decision_sha256,
        })
        request = {
            "request_id": f"{gate}/{state['batch_id']}/{digest[:24]}",
            "gate": gate,
            "batch_id": state["batch_id"],
            "run_bindings_sha256": state["run_bindings_sha256"],
            "materials_sha256": materials_sha256,
            "materials": checked_materials,
            "prior_simulated_decision_sha256": prior_decision_sha256,
            "created_at": checked_materials.get("created_at"),
            "simulation_mark": SIMULATION_MARK,
        }
        _require(request["request_id"]
                 == _request_id_for(state, gate, materials_sha256, prior_decision_sha256),
                 "request.request_id", "必须等于按确定性公式重算的请求 ID")
        requests = copy.deepcopy(state["requests"])
        requests[gate] = request
        event = {
            "seq": len(state["history"]) + 1,
            "event_id": f"EVT-{digest[:24]}",
            "event_type": EVENT_REQUEST[gate],
            "gate": gate,
            "request_id": request["request_id"],
            "materials_sha256": materials_sha256,
            "run_bindings_sha256": state["run_bindings_sha256"],
            "gate1_decision_sha256": prior_decision_sha256,
            "phase_before": phase,
            "phase_after": PENDING_PHASE[gate],
        }
        new_state = _build_state(state, PENDING_PHASE[gate], event)
        new_state["requests"] = requests
        return _result(new_state)
    except WorkflowBlocked:
        raise
    except Exception as exc:  # noqa: BLE001
        raise WorkflowError(f"[prepare] 建立 {gate} 请求失败：{type(exc).__name__}: {exc}",
                            ["阶段=prepare", f"原始异常={type(exc).__name__}: {exc}"]) from exc


# ---------------------------------------------------------------------------
# 3. record_dev_decision
# ---------------------------------------------------------------------------


def _check_decision(decision, state: dict, gate: str, request: dict) -> dict:
    """首次 record 的决定校验：与 replay 复用同一套协议约束。"""
    prior_event_ids = {event.get("event_id") for event in state["history"]}
    _check_request_shape(request, f"state.requests.{gate}")
    return _check_decision_fields(decision, gate=gate, batch_id=state["batch_id"], request=request,
                                  known_event_ids=prior_event_ids, path="decision")


def record_dev_decision(workflow, decision, *, current_bindings) -> dict:
    """记录一次模拟决定；只处理当前 PENDING 的 Gate。"""
    try:
        state, phase, requests, decisions = _validate_workflow(workflow, current_bindings)
        pending_gate = next((candidate for candidate in GATES if phase == PENDING_PHASE[candidate]), None)
        if pending_gate is None:
            raise WorkflowBlocked(
                f"字段 workflow.state.phase 不可用：当前 {phase} 没有待决定的请求"
                "（停止态不能改签，需补证／修订时请新建 workflow 并保留旧记录）"
            )
        request = requests[pending_gate]
        _require(isinstance(request, dict), f"workflow.state.requests.{pending_gate}", "当前请求缺失")
        checked = _check_decision(decision, state, pending_gate, request)
        chosen = checked["decision"]
        phase_after = (APPROVED_PHASE[pending_gate] if chosen == DECISION_APPROVE
                       else HELD_PHASE[pending_gate] if chosen == DECISION_HOLD
                       else REJECTED_PHASE[pending_gate])
        recorded = dict(checked)
        recorded["decision_sha256"] = canonical_sha256(checked)
        event = {
            "seq": len(state["history"]) + 1,
            "event_id": checked["event_id"],
            "event_type": EVENT_DECISION[pending_gate],
            "gate": pending_gate,
            "request_id": request["request_id"],
            "materials_sha256": request["materials_sha256"],
            "decision": recorded,
            "decision_sha256": recorded["decision_sha256"],
            "phase_before": phase,
            "phase_after": phase_after,
        }
        new_state = _build_state(state, phase_after, event)
        new_state["simulated_decisions"] = list(state["simulated_decisions"]) + [copy.deepcopy(recorded)]
        return _result(new_state)
    except WorkflowBlocked:
        raise
    except Exception as exc:  # noqa: BLE001
        raise WorkflowError(f"[record] 记录模拟决定失败：{type(exc).__name__}: {exc}",
                            ["阶段=record", f"原始异常={type(exc).__name__}: {exc}"]) from exc


# ---------------------------------------------------------------------------
# 4. check_dev_action
# ---------------------------------------------------------------------------


def check_dev_action(workflow, action, *, current_bindings) -> dict:
    """行为检查：返回是否允许**模拟**该动作；不默认放行，也不产生任何真实放行。"""
    try:
        state, phase, _, _ = _validate_workflow(workflow, current_bindings)
        _require(action in ACTIONS, "action", f"必须是 {list(ACTIONS)}，实际 {action!r}")
        allowed = False
        if action == ACTION_NORMALIZE:
            allowed = phase == PHASE_G1_APPROVED
            reason = ("Gate1 模拟批准后允许模拟标准化与装载" if allowed else
                      f"当前 {phase} 不允许模拟标准化与装载；需先在 Gate1 请求上记录模拟 APPROVE")
        elif action == ACTION_SCREEN:
            allowed = phase == PHASE_G2_APPROVED
            reason = ("Gate2 模拟批准后允许模拟筛查与事实底稿构建" if allowed else
                      f"当前 {phase} 不允许模拟筛查与事实底稿构建；需先在 Gate2 请求上记录模拟 APPROVE")
        else:
            allowed = False
            reason = "本版本始终不允许生成 AI 建议：尚无人类独立初步判断保存组件"
        return {
            "action": action,
            "phase": phase,
            "simulation_allowed": bool(allowed),
            "reason": reason,
            "run_bindings_sha256": state["run_bindings_sha256"],
            "state_sha256": canonical_sha256(state),
            "batch_id": state["batch_id"],
            "mode": MODE,
            "contract_status": CONTRACT_STATUS,
            "next_step_allowed": False,
            "simulation_mark": SIMULATION_MARK,
        }
    except WorkflowBlocked:
        raise
    except Exception as exc:  # noqa: BLE001
        raise WorkflowError(f"[check] 行为检查失败：{type(exc).__name__}: {exc}",
                            ["阶段=check", f"原始异常={type(exc).__name__}: {exc}"]) from exc
