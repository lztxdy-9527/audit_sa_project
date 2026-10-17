# -*- coding: utf-8 -*-
"""P2-S1：独立 Gate 决定快照保存与只读恢复核验（TASK-022）。

范围 **STORED_SNAPSHOTS_ONLY**：本组件接收四个内存对象，真实调用已冻结验收的 P1 纯内存核心，
把收到的对象快照与 P1 的完整两键返回**独占保存**为六份固定文件，并可只读恢复、复算与核验。

- 不做全局历史发现；不实读业务材料/工作簿/DB；不证明材料清单完备或来源真实。
- 不加 CLI；不接宿主/控制器/网络/UI/ERP；不含真实初判、`0009`、AI 或终判。
- 保存的是**内存对象快照**（P1 canonical JSON 字节 + 一个 LF），不宣称保存原始 JSON 文件的
  排版/BOM/换行；所有人类字符串原文保留，不生成身份、时间、事件、原因或决定。
- 物理保存事实由本组件外层 status 与 manifest 表达；P1 record 原样保存（含
  `boundaries.persisted=false`），不改写成批准或放行标志。
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

__all__ = [
    "save_human_gate_decision_snapshots",
    "verify_human_gate_decision_snapshots",
    "HumanGateDecisionStoreBlocked",
    "HumanGateDecisionStoreError",
    "MANIFEST_VERSION",
    "FAILURE_VERSION",
    "STORE_STATUS_STORED",
    "STORE_STATUS_VERIFIED",
    "SCOPE",
    "PAYLOAD_FILES",
    "MANIFEST_FILE",
    "FAILURE_FILE",
]

# --------------------------------------------------------------------------- 固定路径与冻结身份
MODULE_PATH = Path(__file__).resolve()
PROJECT_ROOT = MODULE_PATH.parents[1]
RECORDS_ROOT = PROJECT_ROOT / "data" / "human_gate_decision_records"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
P1_CORE_PATH = SCRIPTS_DIR / "build_demo_human_gate_decision.py"
STORE_PATH = MODULE_PATH
CONTRACT_PATH = PROJECT_ROOT / "docs" / "AUDIT_CONTRACT.md"
EFFECTIVE_RECORD_PATH = (PROJECT_ROOT / "docs" / "decisions"
                         / "AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md")
PROTOCOL_PATH = PROJECT_ROOT / "docs" / "proposals" / "HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md"
CASES_PATH = PROJECT_ROOT / "docs" / "proposals" / "HUMAN_GATE_DECISION_CASES_V1_DRAFT.md"
HOST_PATH = SCRIPTS_DIR / "run_demo_workflow.py"
CONTROLLER_PATH = SCRIPTS_DIR / "control_demo_workflow.py"

FROZEN_IDENTITIES = {
    "core_file_sha256": "5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79",
    "contract_file_sha256": "174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad",
    "contract_effective_record_file_sha256":
        "042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d",
}

MANIFEST_VERSION = "TASK-022-human-gate-decision-store-manifest-1.0"
FAILURE_VERSION = "TASK-022-human-gate-decision-store-failure-1.0"
STORE_STATUS_STORED = "HUMAN_GATE_DECISION_SNAPSHOTS_STORED"
STORE_STATUS_VERIFIED = "HUMAN_GATE_DECISION_SNAPSHOTS_VERIFIED"
SCOPE = "STORED_SNAPSHOTS_ONLY"

# 五份 payload 按 relative 的 UTF-8 字节序升序（decision < expectations < materials <
# prior_history < submission）
PAYLOAD_FILES = ("decision_result.json", "expectations.json", "materials.json",
                 "prior_history.json", "submission.json")
MANIFEST_FILE = "manifest.json"
FAILURE_FILE = "failure.json"
FIXED_FILES = PAYLOAD_FILES + (MANIFEST_FILE,)
_SNAPSHOT_FILES = {"submission.json": "submission", "materials.json": "materials",
                   "expectations.json": "expectations", "prior_history.json": "prior_history"}

MANIFEST_KEYS = ("manifest_version", "store_status", "scope", "identity",
                 "component_bindings", "fingerprints", "payloads", "boundaries")
IDENTITY_KEYS = ("batch_id", "gate", "event_id")
COMPONENT_BINDING_KEYS = ("core_file_sha256", "store_file_sha256", "contract_file_sha256",
                          "contract_effective_record_file_sha256")
FINGERPRINT_KEYS = ("submission_fingerprint", "materials_snapshot_fingerprint",
                    "materials_body_fingerprint", "expectations_fingerprint",
                    "prior_history_fingerprint", "record_fingerprint")
PAYLOAD_ENTRY_KEYS = ("relative", "byte_size", "file_sha256")
BOUNDARY_KEYS = ("workflow_connected", "execution_allowed", "identity_authenticated",
                 "source_authenticity_proven", "ai_enabled")
RESULT_KEYS = ("status", "scope", "identity", "record_fingerprint", "manifest_file_sha256",
               "execution_allowed", "workflow_connected", "ai_enabled")


# --------------------------------------------------------------------------- 异常
class HumanGateDecisionStoreBlocked(Exception):
    """协议/路径/前提/不一致拒绝：可定位 field 与 reason。"""

    def __init__(self, field, reason):
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


class HumanGateDecisionStoreError(Exception):
    """运行/I-O 错误（保留 cause/context 链，不伪装为协议拒绝、不包装成成功）。"""

    def __init__(self, stage, reason):
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}: {reason}")


def _block(field, reason):
    raise HumanGateDecisionStoreBlocked(field, reason)


def _error(stage, reason):
    raise HumanGateDecisionStoreError(stage, reason)


# --------------------------------------------------------------------------- 受控注入接缝
def _hook_after_manifest_readback():
    """保存路径：manifest 完整写入并读回之后、组件绑定复测之前。默认无操作。

    仅供测试做受控注入（例如真实写入完成后抛 sentinel），不改变生产语义。
    """
    return None


def _hook_after_last_consumption(stage):
    """**最后必要消费**（保存：末次组件绑定读取；核验：唯一一次纯核心复算）返回原值之后、
    最终六文件字节确认之前。默认无操作；仅供测试做受控注入（sentinel 或对已保存文件追加字节）。
    """
    return None


def _reject_reparse_in_path_chain(path: Path, field):
    """在 `resolve()` 消去链接**之前**，逐级检查原始绝对路径（含允许根）是否含链接/reparse。"""
    parts = path.parts
    if not parts:
        return
    current = Path(parts[0])
    candidates = [current]
    for part in parts[1:]:
        current = current / part
        candidates.append(current)
    for node in candidates:
        try:
            exists = node.exists() or node.is_symlink()
        except OSError as exc:
            raise HumanGateDecisionStoreError(
                "path", f"无法检查路径 {node}：{exc}") from exc
        if exists and _is_reparse_point(node):
            _block(field, f"原始路径包含符号链接/reparse 点：{node.name or node}")


# --------------------------------------------------------------------------- P1 核心与基础工具
def load_frozen_p1_core():
    """加载已冻结验收的 P1 纯内存核心（唯一算法来源；本组件不复写 P1 算法）。

    R2：**首次加载的运行/I-O 错误**统一映射为 `StoreError("p1_load", reason)` 并保留 cause；
    加载未完整执行的模块**不作为正常缓存复用**（从 `sys.modules` 清理且不写入 `_CORE`）。
    协议 Blocked 仍为 Blocked，不捕获 AttributeError 等程序错误来掩盖缺陷。
    """
    name = "build_demo_human_gate_decision"
    module = sys.modules.get(name)
    if module is not None and Path(getattr(module, "__file__", "")).resolve() == P1_CORE_PATH:
        return module
    module = None
    try:
        spec = importlib.util.spec_from_file_location(name, P1_CORE_PATH)
        if spec is None or spec.loader is None:
            _error("p1_load", f"无法为冻结 P1 核心建立 spec：{P1_CORE_PATH}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    except (OSError, ImportError) as exc:
        # 未完整加载：清理缓存，避免把半执行的模块当作正常缓存复用
        if module is None or sys.modules.get(name) is module:
            sys.modules.pop(name, None)
        raise HumanGateDecisionStoreError(
            "p1_load", f"加载冻结 P1 核心失败（{type(exc).__name__}: {exc}）") from exc
    return module


_CORE = None


def _core():
    global _CORE
    if _CORE is None:
        _CORE = load_frozen_p1_core()
    return _CORE


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _fingerprint(obj) -> str:
    return _core().fingerprint(obj)


def _canonical_with_lf(obj) -> bytes:
    return _core().canonical_json_bytes(obj) + b"\n"


def _deep(obj):
    return copy.deepcopy(obj)


def _is_hex64(value) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(char in "0123456789abcdef" for char in value)


def _is_reparse_point(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _require_closed_keys(obj, allowed, prefix):
    if not isinstance(obj, dict):
        _block(prefix, f"必须是对象，实际 {type(obj).__name__}")
    for key in obj:
        if key not in allowed:
            _block(f"{prefix}.{key}", "未知字段（封闭协议不允许）")
    for key in allowed:
        if key not in obj:
            _block(f"{prefix}.{key}", "缺失必需字段")
    return obj


def _require_const(obj, key, expected, prefix):
    if obj[key] != expected or not isinstance(obj[key], str):
        _block(f"{prefix}.{key}", f"必须是常量 {expected!r}")


def _require_hex64(obj, key, prefix):
    if not _is_hex64(obj[key]):
        _block(f"{prefix}.{key}",
               "必须是全串匹配的 64 位小写十六进制（不 strip/不截断/不改大小写）")


def _require_strict_false(obj, key, prefix):
    if obj[key] is not False:
        _block(f"{prefix}.{key}", "必须是严格布尔 False")


def _require_nonempty_str(obj, key, prefix):
    value = obj[key]
    if not isinstance(value, str) or value.strip() == "":
        _block(f"{prefix}.{key}", "必须是非空字符串")


# --------------------------------------------------------------------------- 路径与独占 I/O
def _resolve_leaf(target, *, must_exist):
    """解析并校验记录叶目录：允许根 `data/human_gate_decision_records/` 的严格后代。

    先按调用方**原始路径**（含允许根）逐级拒绝链接/reparse，再以解析后绝对路径核对严格后代范围。
    """
    if target is None:
        _block("out_dir", "必须显式提供记录目录路径（不从 ID 拼目录）")
    try:
        raw_abs = Path(os.path.abspath(str(target)))
    except (OSError, ValueError) as exc:
        raise HumanGateDecisionStoreError(
            "path", f"无法解析目标路径：{target!r}（{exc}）") from exc
    _reject_reparse_in_path_chain(raw_abs, "out_dir")
    try:
        resolved = raw_abs.resolve()
    except (OSError, ValueError) as exc:
        raise HumanGateDecisionStoreError(
            "path", f"无法解析目标路径：{target!r}（{exc}）") from exc
    root = RECORDS_ROOT.resolve()
    if resolved == root:
        _block("out_dir", "目标不得等于允许根 data/human_gate_decision_records/")
    if root not in resolved.parents:
        _block("out_dir", "目标必须是允许根 data/human_gate_decision_records/ 的严格后代目录")
    # 解析后链路同样不得包含链接/reparse（防御原始链路之外的别名）
    _reject_reparse_in_path_chain(resolved, "out_dir")
    if must_exist:
        if not resolved.exists():
            _block("record_dir", "记录目录不存在")
        if not resolved.is_dir():
            _block("record_dir", "记录目录必须是目录")
    else:
        if resolved.exists() or resolved.is_symlink():
            _block("out_dir", "目标已存在（含空目录）；本组件不覆盖既有对象")
    return resolved


def _open_exclusive(path: Path):
    """独占创建（失败即拒绝，不覆盖）：真实 `xb` 语义（O_CREAT|O_EXCL）。"""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    return os.open(str(path), flags, 0o600)


def _write_exclusive_bytes(path: Path, buffer: bytes) -> None:
    fd = _open_exclusive(path)
    written = 0
    try:
        view = memoryview(buffer)
        while written < len(buffer):
            written += os.write(fd, view[written:])
    finally:
        os.close(fd)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _readback_check(path: Path, buffer: bytes, *, compare_object, expected_object, stage):
    """按确切待写缓冲逐文件读回验证长度、SHA 与对象相等。"""
    actual = _read_bytes(path)
    if len(actual) != len(buffer):
        _block(path.name, f"实际字节长度 {len(actual)} 与待写缓冲 {len(buffer)} 不一致")
    if _sha256_bytes(actual) != _sha256_bytes(buffer):
        _block(path.name, "实际字节 SHA 与待写缓冲不一致")
    if actual != buffer:
        _block(path.name, "实际字节与待写缓冲不逐字节相等")
    if compare_object:
        try:
            parsed = json.loads(actual.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HumanGateDecisionStoreError(stage, f"读回解析失败：{exc}") from exc
        if _canonical_with_lf(parsed) != _canonical_with_lf(expected_object):
            _block(path.name, "读回解析对象与本次快照对象不等")
    return actual


# --------------------------------------------------------------------------- 组件绑定
def _read_component(path: Path, field, stage):
    try:
        return _read_bytes(path)
    except OSError as exc:
        raise HumanGateDecisionStoreError(stage, f"无法实读组件文件 {field}：{exc}") from exc


def _check_frozen(name, buffer, path):
    expected = FROZEN_IDENTITIES[name]
    actual = _sha256_bytes(buffer)
    if actual != expected:
        _block(f"component_bindings.{name}",
               f"冻结身份不符：{path.name} 实读 {actual} != 冻结 {expected}")


def component_bindings():
    """固定项目路径的真实文件实读 + 冻结核对（恰四项：P1 模块、本存储模块、正式 V1、生效登记）。

    协议/案例/宿主/控制器等额外冻结身份**不在生产运行中核对**（避免后续宿主接线改变代码后
    阻断新快照）；它们由测试/保护层独立核对，不改变本卡的四项 manifest schema。
    """
    core = _read_component(P1_CORE_PATH, "core", "bindings")
    store = _read_component(STORE_PATH, "store", "bindings")
    contract = _read_component(CONTRACT_PATH, "contract", "bindings")
    effective = _read_component(EFFECTIVE_RECORD_PATH, "contract_effective_record", "bindings")
    _check_frozen("core_file_sha256", core, P1_CORE_PATH)
    _check_frozen("contract_file_sha256", contract, CONTRACT_PATH)
    _check_frozen("contract_effective_record_file_sha256", effective, EFFECTIVE_RECORD_PATH)
    return {
        "core_file_sha256": _sha256_bytes(core),
        "store_file_sha256": _sha256_bytes(store),
        "contract_file_sha256": _sha256_bytes(contract),
        "contract_effective_record_file_sha256": _sha256_bytes(effective),
    }


def _check_contract_binding(expected_contract_sha, materials, expectations):
    """输入材料与独立契约预期必须指向同一正式 V1 SHA。"""
    formal = FROZEN_IDENTITIES["contract_file_sha256"]
    if expected_contract_sha != formal:
        _block("component_bindings.contract_file_sha256",
               "本次运行实读的正式契约 SHA 与冻结值不一致")
    if not isinstance(materials, dict) or not isinstance(expectations, dict):
        return
    contract_binding = materials.get("contract_binding")
    if isinstance(contract_binding, dict) and isinstance(
            contract_binding.get("contract_file_sha256"), str):
        if contract_binding["contract_file_sha256"] != formal:
            _block("materials.contract_binding.contract_file_sha256",
                   "输入材料契约 SHA 与正式 V1 不一致")
    expected_contract = expectations.get("expected_contract")
    if isinstance(expected_contract, dict) and isinstance(
            expected_contract.get("contract_file_sha256"), str):
        if expected_contract["contract_file_sha256"] != formal:
            _block("expectations.expected_contract.contract_file_sha256",
                   "独立契约预期 SHA 与正式 V1 不一致")


# --------------------------------------------------------------------------- 快照与 manifest 构造
def _call_p1_once(submission, materials, expectations, prior_history):
    """恰一次调用真实冻结 P1 核心（不重写 P1 schema/矩阵/历史算法；不默认空历史）。"""
    core = _core()
    try:
        return core.build_human_gate_decision_record(
            submission, materials, expectations, prior_history=prior_history)
    except core.HumanGateDecisionBlocked as exc:
        raise HumanGateDecisionStoreBlocked(exc.field, exc.reason) from exc
    except core.HumanGateDecisionError as exc:
        raise HumanGateDecisionStoreError("p1_core", f"{exc.stage}: {exc.reason}") from exc


def _validate_p1_result(result):
    if not isinstance(result, dict):
        _block("decision_result", "P1 返回必须是对象")
    if set(result.keys()) != {"record", "record_fingerprint"}:
        _block("decision_result", "P1 完整返回必须恰为 record 与 record_fingerprint 两键")
    record = result["record"]
    core = _core()
    if not isinstance(record, dict) or set(record.keys()) != set(core.RECORD_KEYS):
        _block("decision_result.record", "P1 记录必须是协议 §14 的 17 键对象")
    if result["record_fingerprint"] != _fingerprint(record):
        _block("decision_result.record_fingerprint", "P1 返回的记录指纹与记录正文复算不一致")
    return record


def _payload_buffers(snapshots, result):
    buffers = {
        "submission.json": _canonical_with_lf(snapshots["submission"]),
        "materials.json": _canonical_with_lf(snapshots["materials"]),
        "expectations.json": _canonical_with_lf(snapshots["expectations"]),
        "prior_history.json": _canonical_with_lf(snapshots["prior_history"]),
        "decision_result.json": _canonical_with_lf(result),
    }
    return buffers


def _materials_body(materials):
    """材料正文（协议 §4.1）：沿用 P1 已验收实现，不在本组件重写算法。"""
    return _core().materials_body(materials)


def _build_manifest(snapshots, result, bindings, buffers):
    record = result["record"]
    identity = {"batch_id": record["batch_id"], "gate": record["gate"],
                "event_id": record["event_id"]}
    fingerprints = {
        "submission_fingerprint": _fingerprint(snapshots["submission"]),
        "materials_snapshot_fingerprint": _fingerprint(snapshots["materials"]),
        "materials_body_fingerprint": _fingerprint(_materials_body(snapshots["materials"])),
        "expectations_fingerprint": _fingerprint(snapshots["expectations"]),
        "prior_history_fingerprint": _fingerprint(snapshots["prior_history"]),
        "record_fingerprint": result["record_fingerprint"],
    }
    payloads = [{"relative": name, "byte_size": len(buffers[name]),
                 "file_sha256": _sha256_bytes(buffers[name])}
                for name in sorted(PAYLOAD_FILES, key=lambda item: item.encode("utf-8"))]
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "store_status": STORE_STATUS_STORED,
        "scope": SCOPE,
        "identity": identity,
        "component_bindings": dict(bindings),
        "fingerprints": fingerprints,
        "payloads": payloads,
        "boundaries": {"workflow_connected": False, "execution_allowed": False,
                       "identity_authenticated": False, "source_authenticity_proven": False,
                       "ai_enabled": False},
    }
    return manifest


def _result_payload(status, manifest, manifest_bytes, record_fingerprint, identity):
    return {
        "status": status,
        "scope": SCOPE,
        "identity": {"batch_id": identity["batch_id"], "gate": identity["gate"],
                     "event_id": identity["event_id"]},
        "record_fingerprint": record_fingerprint,
        "manifest_file_sha256": _sha256_bytes(manifest_bytes),
        "execution_allowed": False,
        "workflow_connected": False,
        "ai_enabled": False,
    }


# --------------------------------------------------------------------------- 失败诊断
def _exception_chain(exc):
    chain = []
    for label, first in (("cause", exc.__cause__), ("context", exc.__context__)):
        current = first
        seen = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            chain.append({"link": label, "type": type(current).__name__,
                          "reason": str(current)})
            current = current.__cause__ or current.__context__
    return chain


def _write_failure(leaf: Path, stage, exc):
    """叶目录建立后的失败：只在该新目录独占写 failure.json，不覆盖既有诊断。"""
    if isinstance(exc, HumanGateDecisionStoreBlocked):
        classification, field, reason = "Blocked", exc.field, exc.reason
    elif isinstance(exc, HumanGateDecisionStoreError):
        classification, field, reason = "Error", None, exc.reason
    else:
        classification, field, reason = "Error", None, f"{type(exc).__name__}: {exc}"
    payload = {
        "failure_version": FAILURE_VERSION,
        "stage": stage,
        "classification": classification,
        "field": field,
        "reason": reason,
        "cause_chain": _exception_chain(exc),
    }
    target = leaf / FAILURE_FILE
    try:
        _write_exclusive_bytes(target, _canonical_with_lf(payload))
    except OSError as diagnostic_error:
        if hasattr(exc, "add_note"):
            exc.add_note(f"失败诊断写入失败：{diagnostic_error}")
        setattr(exc, "diagnostic_error", str(diagnostic_error))
    return payload


# --------------------------------------------------------------------------- 保存
def save_human_gate_decision_snapshots(
    out_dir,
    submission: dict,
    materials: dict,
    expectations: dict,
    *,
    prior_history: dict | None = None,
) -> dict:
    """保存四个内存对象快照 + P1 完整两键返回为六份固定文件（独占、不覆盖）。

    成功返回恰八键（status=`HUMAN_GATE_DECISION_SNAPSHOTS_STORED`）。协议/路径/前提/不一致
    拒绝抛 `HumanGateDecisionStoreBlocked(field, reason)`；运行/I-O 失败抛
    `HumanGateDecisionStoreError(stage, reason)`，叶目录建立后的失败另写 `failure.json`。
    """
    leaf = None
    stage = "p1_load"
    try:
        _core()  # 首次加载的运行/I-O 错误在错误边界内映射为 StoreError("p1_load")
        stage = "path"
        target = _resolve_leaf(out_dir, must_exist=False)
        stage = "bindings"
        bindings = component_bindings()
        _check_contract_binding(bindings["contract_file_sha256"], materials, expectations)

        # 独立快照；保留对真实消费对象的引用
        stage = "snapshot"
        snapshots = {"submission": _deep(submission), "materials": _deep(materials),
                     "expectations": _deep(expectations), "prior_history": _deep(prior_history)}
        consumed = {name: id(snapshots[name]) for name in snapshots}
        before = {name: (None if snapshots[name] is None else _fingerprint(snapshots[name]))
                  for name in snapshots}

        # 恰一次真实 P1 调用（只传四个内存快照；None 由真实 P1 拒绝）
        stage = "p1_call"
        result = _call_p1_once(snapshots["submission"], snapshots["materials"],
                               snapshots["expectations"], snapshots["prior_history"])
        record = _validate_p1_result(result)

        # 真实消费引用调用前后指纹不变
        stage = "input_fidelity"
        after = {name: (None if snapshots[name] is None else _fingerprint(snapshots[name]))
                 for name in snapshots}
        if after != before or {name: id(snapshots[name]) for name in snapshots} != consumed:
            _block("inputs", "四个输入快照在核心调用前后发生变化或被替换")

        # 确定待写缓冲（先明确构造字节）
        stage = "buffer"
        buffers = _payload_buffers(snapshots, result)
        manifest = _build_manifest(snapshots, result, bindings, buffers)
        manifest_buffer = _canonical_with_lf(manifest)

        # 独占建立叶目录（此后失败写 failure.json）
        stage = "leaf"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.mkdir(target)
        except FileExistsError as exc:
            raise HumanGateDecisionStoreBlocked(
                "out_dir", "目标已存在（含空目录）；独占建立被拒绝") from exc
        except OSError as exc:
            raise HumanGateDecisionStoreError("leaf", f"无法独占建立叶目录：{exc}") from exc
        leaf = target

        # 独占保存五份 payload 并读回精确核对
        stage = "payload_write"
        for name in PAYLOAD_FILES:
            _write_exclusive_bytes(leaf / name, buffers[name])
            _readback_check(leaf / name, buffers[name], compare_object=True,
                            expected_object=json.loads(buffers[name].decode("utf-8")),
                            stage="payload_readback")
        # manifest 最后写入并读回（不内嵌自身文件哈希）
        stage = "manifest_write"
        _write_exclusive_bytes(leaf / MANIFEST_FILE, manifest_buffer)
        _readback_check(leaf / MANIFEST_FILE, manifest_buffer, compare_object=True,
                        expected_object=manifest, stage="manifest_readback")

        _hook_after_manifest_readback()

        # 组件绑定复测（**末次必要消费**：此后只有字节确认，不再消费数据）
        stage = "final_confirmation"
        bindings_again = component_bindings()
        if bindings_again != bindings:
            _block("component_bindings", "组件绑定在保存期间发生变化")

        _hook_after_last_consumption("save")

        # 最终六文件字节确认
        present = sorted(entry.name for entry in leaf.iterdir())
        if present != sorted(FIXED_FILES):
            _block("files", f"叶目录文件集合必须恰为六份，实际 {present}")
        for name in FIXED_FILES:
            expected = manifest_buffer if name == MANIFEST_FILE else buffers[name]
            actual = _read_bytes(leaf / name)
            if actual != expected:
                _block(name, "最终字节确认与本次待写缓冲不一致")
        return _result_payload(STORE_STATUS_STORED, manifest, manifest_buffer,
                               result["record_fingerprint"], manifest["identity"])
    except (HumanGateDecisionStoreBlocked, HumanGateDecisionStoreError) as exc:
        if leaf is not None:
            _write_failure(leaf, stage, exc)
        raise
    except OSError as exc:
        wrapped = HumanGateDecisionStoreError(stage, f"I/O 失败：{exc}")
        wrapped.__cause__ = exc
        if leaf is not None:
            _write_failure(leaf, stage, wrapped)
        raise wrapped from exc
    except Exception as exc:  # noqa: BLE001 - 意外内部错误保留原因链，不伪装为协议拒绝
        wrapped = HumanGateDecisionStoreError(
            stage, f"意外内部错误：{type(exc).__name__}: {exc}")
        # 关键：**先绑定原因链**，再写失败诊断，保证 failure.json 的 cause_chain 与实际异常一致
        wrapped.__cause__ = exc
        if leaf is not None:
            _write_failure(leaf, stage, wrapped)
        raise wrapped from exc


# --------------------------------------------------------------------------- 只读恢复核验
def _validate_manifest_schema(manifest):
    _require_closed_keys(manifest, MANIFEST_KEYS, "manifest")
    _require_const(manifest, "manifest_version", MANIFEST_VERSION, "manifest")
    _require_const(manifest, "store_status", STORE_STATUS_STORED, "manifest")
    _require_const(manifest, "scope", SCOPE, "manifest")

    identity = _require_closed_keys(manifest["identity"], IDENTITY_KEYS, "manifest.identity")
    _require_nonempty_str(identity, "batch_id", "manifest.identity")
    _require_nonempty_str(identity, "event_id", "manifest.identity")
    if identity["gate"] not in ("GATE1", "GATE2"):
        _block("manifest.identity.gate", "必须是 GATE1/GATE2")

    bindings = _require_closed_keys(manifest["component_bindings"], COMPONENT_BINDING_KEYS,
                                    "manifest.component_bindings")
    for key in COMPONENT_BINDING_KEYS:
        _require_hex64(bindings, key, "manifest.component_bindings")

    fingerprints = _require_closed_keys(manifest["fingerprints"], FINGERPRINT_KEYS,
                                        "manifest.fingerprints")
    for key in FINGERPRINT_KEYS:
        _require_hex64(fingerprints, key, "manifest.fingerprints")

    payloads = manifest["payloads"]
    if not isinstance(payloads, list):
        _block("manifest.payloads", "必须是列表")
    if len(payloads) != len(PAYLOAD_FILES):
        _block("manifest.payloads", f"必须恰为五份 payload，实际 {len(payloads)}")
    relatives = []
    for index, entry in enumerate(payloads):
        prefix = f"manifest.payloads[{index}]"
        _require_closed_keys(entry, PAYLOAD_ENTRY_KEYS, prefix)
        relative = entry["relative"]
        if not isinstance(relative, str) or relative not in PAYLOAD_FILES:
            _block(f"{prefix}.relative",
                   "只能是五个固定字面文件名，拒绝重复/遗漏/绝对路径/分隔符/..")
        relatives.append(relative)
        if not isinstance(entry["byte_size"], int) or isinstance(entry["byte_size"], bool):
            _block(f"{prefix}.byte_size", "必须是非负整数（bool 不冒充）")
        if entry["byte_size"] < 0:
            _block(f"{prefix}.byte_size", "必须是非负整数")
        _require_hex64(entry, "file_sha256", prefix)
    if len(set(relatives)) != len(relatives):
        _block("manifest.payloads", "payload 名单不得重复")
    ordered = sorted(relatives, key=lambda item: item.encode("utf-8"))
    if relatives != ordered:
        _block("manifest.payloads", "payload 名单必须按 relative 的 UTF-8 字节序严格升序")
    if set(relatives) != set(PAYLOAD_FILES):
        _block("manifest.payloads", "payload 名单必须恰为五个固定文件")

    boundaries = _require_closed_keys(manifest["boundaries"], BOUNDARY_KEYS, "manifest.boundaries")
    for key in BOUNDARY_KEYS:
        _require_strict_false(boundaries, key, "manifest.boundaries")
    return manifest


def _verify_enumeration(target: Path):
    try:
        entries = sorted(target.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        raise HumanGateDecisionStoreError("enumerate", f"无法枚举记录目录：{exc}") from exc
    return entries


def _verify_file_state(target: Path, name: str):
    """六份载荷必须是**正常文件**：未知项/目录/链接不得被当作合法载荷读取。"""
    path = target / name
    if _is_reparse_point(path):
        _block(name, "载荷不得是符号链接/junction/reparse 点")
    try:
        if not path.is_file():
            _block(name, "载荷必须是正常文件")
    except OSError as exc:
        raise HumanGateDecisionStoreError("stat", f"无法检查 {name}：{exc}") from exc


def _precheck_parsed_objects(parsed):
    """在 `.get`/`.items`/摘要派生/嵌套消费**之前**做封闭类型与形状检查（错类型 → Blocked）。"""
    for name in FIXED_FILES:
        if not isinstance(parsed[name], dict):
            _block(name, f"顶层必须是 JSON 对象，实际 {type(parsed[name]).__name__}")
    decision_result = parsed["decision_result.json"]
    if set(decision_result.keys()) != {"record", "record_fingerprint"}:
        _block("decision_result.json", "必须是完整两键对象（record 与 record_fingerprint）")
    if not isinstance(decision_result["record"], dict):
        _block("decision_result.json.record",
               f"必须是对象，实际 {type(decision_result['record']).__name__}")
    return decision_result


def verify_human_gate_decision_snapshots(record_dir) -> dict:
    """从六份固定文件只读恢复、复算与核验（恰一次纯核心复算；不写任何文件）。"""
    _core()  # 首次加载的运行/I-O 错误映射为 StoreError("p1_load")，不写任何文件
    target = _resolve_leaf(record_dir, must_exist=True)

    entries = _verify_enumeration(target)
    for entry in entries:
        if entry.is_dir() and not _is_reparse_point(entry):
            _block(entry.name, "记录目录不得包含子目录")
    present = sorted(entry.name for entry in _verify_enumeration(target))
    if FAILURE_FILE in present:
        _block(FAILURE_FILE, "记录目录含 failure 诊断，核验拒绝")
    if present != sorted(FIXED_FILES):
        missing = sorted(set(FIXED_FILES) - set(present))
        unknown = sorted(set(present) - set(FIXED_FILES))
        _block("files", f"文件集合必须恰为六份；缺失={missing} 未知={unknown}")

    # 同一缓冲绑定长度/SHA 与解析对象（不先 hash 一次再另读 JSON）
    buffers, parsed = {}, {}
    for name in FIXED_FILES:
        _verify_file_state(target, name)
        try:
            data = _read_bytes(target / name)
        except OSError as exc:
            raise HumanGateDecisionStoreError("read", f"无法读取 {name}：{exc}") from exc
        buffers[name] = data
        try:
            parsed[name] = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HumanGateDecisionStoreError("parse", f"{name} 解析失败：{exc}") from exc

    # 先做类型/形状检查，再做任何 `.get`/`.items`/摘要派生消费
    decision_result = _precheck_parsed_objects(parsed)

    manifest = _validate_manifest_schema(parsed[MANIFEST_FILE])

    # payloads 与实际字节闭合
    for index, entry in enumerate(manifest["payloads"]):
        relative = entry["relative"]
        actual = buffers[relative]
        if entry["byte_size"] != len(actual):
            _block(f"manifest.payloads[{index}].byte_size",
                   f"{relative} 实际长度 {len(actual)} 与 manifest 声明不一致")
        if entry["file_sha256"] != _sha256_bytes(actual):
            _block(f"manifest.payloads[{index}].file_sha256",
                   f"{relative} 实际字节 SHA 与 manifest 声明不一致")

    # 六项对象指纹复算
    submission = parsed["submission.json"]
    materials = parsed["materials.json"]
    expectations = parsed["expectations.json"]
    prior_history = parsed["prior_history.json"]
    decision_result = parsed["decision_result.json"]
    recomputed = {
        "submission_fingerprint": _fingerprint(submission),
        "materials_snapshot_fingerprint": _fingerprint(materials),
        "materials_body_fingerprint": _fingerprint(_materials_body(materials)),
        "expectations_fingerprint": _fingerprint(expectations),
        "prior_history_fingerprint": _fingerprint(prior_history),
        "record_fingerprint": _fingerprint(decision_result.get("record")),
    }
    for key in FINGERPRINT_KEYS:
        if manifest["fingerprints"][key] != recomputed[key]:
            _block(f"manifest.fingerprints.{key}", "与从已绑定快照复算的规范指纹不一致")

    # 材料正文闭合（P1 §4.3 唯一相等关系）
    body = recomputed["materials_body_fingerprint"]
    if isinstance(materials, dict) and materials.get("materials_fingerprint") != body:
        _block("materials.json.materials_fingerprint", "与材料正文复算指纹不一致")
    request_binding = submission.get("request_binding") if isinstance(submission, dict) else None
    if isinstance(request_binding, dict) and request_binding.get("materials_binding") != body:
        _block("submission.json.request_binding.materials_binding",
               "与材料正文复算指纹不一致")
    if (isinstance(expectations, dict)
            and expectations.get("expected_materials_fingerprint") != body):
        _block("expectations.json.expected_materials_fingerprint",
               "与材料正文复算指纹不一致")

    # 身份闭合
    record = decision_result.get("record") if isinstance(decision_result, dict) else None
    if not isinstance(record, dict):
        _block("decision_result.json.record", "必须是记录对象")
    identity = manifest["identity"]
    for key in IDENTITY_KEYS:
        if identity[key] != record.get(key):
            _block(f"manifest.identity.{key}", "必须与 decision_result.record 精确闭合")
    if isinstance(submission, dict) and submission.get("batch_id") != identity["batch_id"]:
        _block("submission.json.batch_id", "必须与 manifest.identity.batch_id 精确闭合")
    if isinstance(materials, dict) and materials.get("batch_id") != identity["batch_id"]:
        _block("materials.json.batch_id", "必须与 manifest.identity.batch_id 精确闭合")
    if (isinstance(expectations, dict)
            and expectations.get("expected_batch_id") != identity["batch_id"]):
        _block("expectations.json.expected_batch_id",
               "必须与 manifest.identity.batch_id 精确闭合")
    if isinstance(submission, dict) and submission.get("gate") != identity["gate"]:
        _block("submission.json.gate", "必须与 manifest.identity.gate 精确闭合")
    if isinstance(materials, dict) and materials.get("gate") != identity["gate"]:
        _block("materials.json.gate", "必须与 manifest.identity.gate 精确闭合")
    if (isinstance(expectations, dict)
            and expectations.get("expected_gate") != identity["gate"]):
        _block("expectations.json.expected_gate", "必须与 manifest.identity.gate 精确闭合")
    if isinstance(submission, dict) and submission.get("event_id") != identity["event_id"]:
        _block("submission.json.event_id", "必须与 manifest.identity.event_id 精确闭合")

    # 组件绑定与当前真实组件/契约文件匹配
    current_bindings = component_bindings()
    for key in COMPONENT_BINDING_KEYS:
        if manifest["component_bindings"][key] != current_bindings[key]:
            _block(f"manifest.component_bindings.{key}",
                   "与当前真实组件/契约文件实读 SHA 不一致（版本变化不迁移、不补签）")
    _check_contract_binding(current_bindings["contract_file_sha256"], materials, expectations)

    # 恰一次纯核心复算（同一冻结核心），严格比较完整返回
    before = {"submission": _fingerprint(submission), "materials": _fingerprint(materials),
              "expectations": _fingerprint(expectations),
              "prior_history": _fingerprint(prior_history)}
    recomputed_result = _call_p1_once(submission, materials, expectations, prior_history)
    after = {"submission": _fingerprint(submission), "materials": _fingerprint(materials),
             "expectations": _fingerprint(expectations),
             "prior_history": _fingerprint(prior_history)}
    if after != before:
        _block("inputs", "核验输入在核心复算前后发生变化")
    if _canonical_with_lf(recomputed_result) != _canonical_with_lf(decision_result):
        _block("decision_result.json",
               "与本次真实 P1 完整返回不逐字段相等（两键对象不一致）")
    if recomputed_result.get("record_fingerprint") != manifest["fingerprints"]["record_fingerprint"]:
        _block("manifest.fingerprints.record_fingerprint", "与真实 P1 返回指纹不一致")

    _hook_after_last_consumption("verify")

    # 返回成功前再次实读六文件字节并与初始缓冲比较，确认固定集合/无 failure
    for name in FIXED_FILES:
        try:
            actual = _read_bytes(target / name)
        except OSError as exc:
            raise HumanGateDecisionStoreError(
                "final_read", f"无法再次实读 {name}：{exc}") from exc
        if actual != buffers[name]:
            _block(name, "核验期间文件字节发生变化（只读核验检测到不一致）")
    present_after = sorted(entry.name for entry in _verify_enumeration(target))
    if present_after != sorted(FIXED_FILES):
        _block("files", f"核验期间文件集合发生变化：{present_after}")

    return _result_payload(STORE_STATUS_VERIFIED, manifest, buffers[MANIFEST_FILE],
                           manifest["fingerprints"]["record_fingerprint"], manifest["identity"])
