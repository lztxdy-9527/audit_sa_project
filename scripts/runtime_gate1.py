#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-038：十七项共享运行身份、Gate绑定历史域及只读初判请求。

下列 TASK-026/R1 文字保留原阶段说明；当前十七业务API及边界见新TASK-038指南。

三个公开 API，无 CLI：

    build_runtime_registry(batch_dir, runtime_dir, *, scope_dir, initial_judgment_history)
    read_runtime_registry(runtime_dir)
    prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id)

边界：登记**不是**决定，`RUNTIME_GATE1_REQUEST_PREPARED`（PREPARED）**不是**批准；
本模块不生成 submission、不接受任何人类字段、不赋予任何执行许可。
只真实调用冻结准备器 `prepare_human_gate1_request` 复用其来源核验结果；不调用冻结 P1 公开入口、
store、标准化/DB、Gate2、筛查/复算/事实底稿/初判/AI/终判任何入口。

R1 修正要点（依据 docs/reviews/REVIEW_TASK_026.md）：

- 一切消费读数在**操作起始**以同缓冲字节固定；两份输出预期只来自本次待写缓冲与 writer 读回；
  三 API 末端都做**原始字节/集合/路径**确认，之后直接返回，不再解析候选决定成功。
- 恢复（read）完整核验 13 键及全部嵌套封闭键/严格类型/常量/排序/固定集合/派生关系与
  **本次**静态冻结字节；不接受外层摘要同步而内部不合法。
- 先确认解析值类型再消费，不让非对象输入产生原生 AttributeError/TypeError；
  I/O 失败统一映射为 `RuntimeGate1Error(stage, reason)` 并保留异常链。
- `scope_dir` 是 Gate1 记录根下**尚不存在**的计划技术路径：只登记/核验引用，不创建；
  **已存在即拒绝**。
- 按原始绝对路径**逐级**检查 reparse 后在 resolve 复查；`lstat` 的真实 OSError 不被吞成“非 reparse”。

不提供测试回调设施：需要观测接缝时由测试包装**真实 reader/writer**。
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- 常量

MODULE_PATH = Path(__file__).resolve()
PROJECT_ROOT = MODULE_PATH.parents[1]
SCRIPT_RELATIVE = "scripts/runtime_gate1.py"

REGISTRY_VERSION = "TASK-040-runtime-registry-1.0"
REGISTRY_FILE = "runtime_registry.json"
READBACK_FILE = "runtime_registry_readback.json"
READBACK_VERSION = "TASK-026-runtime-registry-readback-1.0"
FAILURE_FILE = "failure.json"
FAILURE_VERSION = "TASK-026-runtime-registry-failure-1.0"

CODE_MANIFEST_VERSION = "TASK-040-code-manifest-1.0"
RULES_MANIFEST_VERSION = "TASK-006-rule-core-1.1"
REQUEST_VERSION = "TASK-025-human-gate1-runtime-request-1.0"
REQUEST_STATUS = "RUNTIME_GATE1_REQUEST_PREPARED"
REGISTRY_NOTE = ("RUNTIME_REGISTRATION_ONLY: not a decision, not an approval, "
                 "not an execution permission")
REGISTRATION_SOURCE_CHECK_ID = "TASK-026-REGISTRATION-SOURCE-CHECK"

CONFIG_REF = "config/human_flow_v1.json"
CONTRACT_RELATIVE = "docs/AUDIT_CONTRACT.md"
CONTRACT_EFFECTIVE_RELATIVE = ("docs/decisions/"
                              "AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md")
INPUT_REF = "batch/source/input.xlsx"

DATA_ROOT = PROJECT_ROOT / "data"
RUNTIME_ROOT = DATA_ROOT / "runtime"
BATCH_ROOT = DATA_ROOT / "batches"
GATE1_RECORDS_ROOT = DATA_ROOT / "human_gate_decision_records" / "gate1"

REGISTRY_KEYS = ("registry_version", "batch_id", "registered_at", "scope_ref", "batch_files",
                 "code_manifest", "rules_manifest", "config", "input", "contract",
                 "run_binding", "run_binding_sha256", "note", "initial_judgment_history")
READBACK_KEYS = ("readback_version", "registry_sha256", "registry_file_sha256",
                 "registry_byte_size", "run_binding_sha256")
REQUEST_KEYS = ("request_version", "status", "materials", "expectations", "evidence",
                "boundaries")
MATERIALS_KEYS = ("gate", "batch_id", "run_binding", "contract_binding", "files", "quality",
                  "materials_fingerprint")
EXPECTATIONS_KEYS = ("expected_batch_id", "expected_gate", "expected_request_id",
                     "expected_materials_fingerprint", "expected_files", "expected_contract",
                     "expected_run_binding", "expected_prior_gate1")
EVIDENCE_KEYS = ("source_manifest_version", "source_batch_status", "source_receive_exit_code",
                 "source_description", "source_scope", "code_manifest", "rules_manifest")
BOUNDARY_KEYS = ("request_persisted", "decision_recorded", "execution_allowed",
                 "workflow_connected", "ai_enabled", "identity_authenticated",
                 "source_authenticity_proven")
FILE_ITEM_KEYS = ("relative", "file_sha256", "byte_size")
RUN_BINDING_KEYS = ("code", "rules", "config", "input")
RUN_CODE_KEYS = ("file_sha256", "manifest_fingerprint")
RUN_RULES_KEYS = ("version", "manifest_fingerprint")
RUN_SINGLE_KEYS = ("file_sha256",)
QUALITY_KEYS = ("status", "structural_blockers", "quality_blockers",
                "verification_failures")
BATCH_SUBDIR_FILES = {
    "checks": ("quality_report.json",),
    "code_snapshot": ("receive_demo_batch.py", "check_demo_data.py"),
    "logs": ("checker.stdout.txt", "checker.stderr.txt"),
    "source": ("input.xlsx",),
}
BATCH_FILES = (
    "batch_manifest.json", "gate1_packet.md", "source/input.xlsx",
    "checks/quality_report.json", "logs/checker.stdout.txt", "logs/checker.stderr.txt",
    "code_snapshot/receive_demo_batch.py", "code_snapshot/check_demo_data.py",
)
CODE_FILES = ("scripts/build_demo_fact_packet.py",
              "scripts/build_demo_human_gate_decision.py",
              "scripts/build_demo_initial_judgment.py",
              "scripts/check_demo_data.py",
              "scripts/control_demo_workflow.py",
              "scripts/crosscheck_demo_rules.py",
              "scripts/normalize_demo_data.py",
              "scripts/prepare_demo_human_gate1.py",
              "scripts/receive_demo_batch.py",
              "scripts/run_demo_workflow.py",
              "scripts/screen_demo_sqlite.py",
              "scripts/store_demo_human_gate_decision.py",
              "scripts/store_demo_sqlite.py",
              "scripts/build_demo_human_initial_judgment.py",
              "scripts/store_demo_human_initial_judgment.py",
              "scripts/inspect_demo_human_initial_judgment_history.py")
INITIAL_COMPONENT_SHA256 = {
    "scripts/build_demo_human_initial_judgment.py": "312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35",
    "scripts/store_demo_human_initial_judgment.py": "a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c",
    "scripts/inspect_demo_human_initial_judgment_history.py": "7276ddb704d27cec031ca3c2af4122a3c2c890d613bd4cfa90e6454d72000b22",
    "docs/proposals/HUMAN_INITIAL_JUDGMENT_PROTOCOL_V1_DRAFT.md": "df5dace5f8ec2dfca820f9c74db6f5fa1d3a947005610ad72b8e8d59d1c38cfe",
    "docs/proposals/HUMAN_INITIAL_JUDGMENT_CASES_V1_DRAFT.md": "e02e1f49e16ebff6a3b683e4c76ece6dd81697569e4876d090a4cccb67d07d46"}
# TASK-040：本次已接受（TASK-039-R1）的运行初判保存/恢复协议与案例两份独立固定身份。
# 只进入 Gate1 四十材料的 project/ 增量与读取核验，不进入代码清单、不改变既有十六项代码身份。
RECORDING_COMPONENT_SHA256 = {
    "docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_PROTOCOL_V1_DRAFT.md":
        "0b92e8629a9d8306a8fc9b383a835f393db028a4acdda6d91bde901de7a6b2db",
    "docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_CASES_V1_DRAFT.md":
        "177d58018071b7f87c74be04ce2f1a0d8a7600598e168e9396b8010cb735729b"}
RULE_IDS = ("R01", "R02", "R03", "R04")
RULE_FILES = {"R01": "sql/rules/r01.sql", "R02": "sql/rules/r02.sql",
              "R03": "sql/rules/r03.sql", "R04": "sql/rules/r04.sql"}
RULE_VERSIONS = {"R01": "TASK-006-R01-1.0", "R02": "TASK-006-R02-1.0",
                 "R03": "TASK-006-R03-1.0", "R04": "TASK-006-R04-1.0"}
EXPECTED_CONTRACT_SHA256 = "174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad"
EXPECTED_CONTRACT_VERSION = "V1"
# 冻结准备器自身不在其 FROZEN_PROJECT_SHA 中：本层对它给出**独立预期**（TASK-025 已验收身份）。
FROZEN_PREPARE_SHA256 = "ce23671f4c19d60808f90755d4c8575b1b8ad018bfc7e0f3bcebee3b06de0ac4"
HASH_PATTERN = re.compile(r"\A[0-9a-f]{64}\Z")
# 接收批次固定顶层集合：八文件中的顶层文件 + 四个固定子目录
TOP_LEVEL_MEMBERS = tuple(name for name in BATCH_FILES if "/" not in name) \
    + tuple(BATCH_SUBDIR_FILES)
# 技术登记时间：合法 ISO 8601、真实日期、必须带时区（不是人类决定时间协议）
ISO_TZ_PATTERN = re.compile(
    r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z")
# 旧契约草案、规格与 SQL schema：来源核验二十三项既有 project 材料中未被清单构造器
# 直接读取的三份，必须在末端一并复测。
PROJECT_MATERIAL_EXTRAS = ("docs/SPEC_V1.md", "docs/AUDIT_CONTRACT_DRAFT.md",
                           "sql/demo_schema.sql",
                           "docs/proposals/HUMAN_INITIAL_JUDGMENT_PROTOCOL_V1_DRAFT.md",
                           "docs/proposals/HUMAN_INITIAL_JUDGMENT_CASES_V1_DRAFT.md")


class RuntimeGate1Blocked(Exception):
    """类型/协议/来源/路径/既有目标/不一致：可定位的 field 与 reason。"""

    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


class RuntimeGate1Error(Exception):
    """I/O 或运行故障：保留 stage 与原因链。"""

    def __init__(self, stage: str, reason: str):
        self.stage = stage
        self.reason = reason
        super().__init__(f"[{stage}] {reason}")


# --------------------------------------------------------------------------- 基础工具


def canonical_json_bytes(obj) -> bytes:
    """冻结 canonical 口径：UTF-8、无 BOM、键排序、紧凑分隔。"""
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return text.encode("utf-8")


def fingerprint(obj) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def _payload_bytes(obj) -> bytes:
    return canonical_json_bytes(obj) + b"\n"


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _block(field: str, reason: str) -> None:
    raise RuntimeGate1Blocked(field, reason)


def _is_strict_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_nonempty_str(value, field: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        _block(field, f"必须是非空字符串（原文保留），实际 {type(value).__name__}")
    return value


def _require_hash(value, field: str) -> str:
    if not isinstance(value, str) or HASH_PATTERN.fullmatch(value) is None:
        _block(field, "必须是完整 64 位小写十六进制字符串")
    return value


def _require_iso_time(value, field: str) -> str:
    """技术登记时间：合法 ISO 8601、真实日期、必须带时区；不接受任意非空字符串。"""
    if not isinstance(value, str) or ISO_TZ_PATTERN.fullmatch(value) is None:
        _block(field, "必须是带时区的 ISO 8601 技术登记时间（例如 2026-10-15T00:00:00+00:00）")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        _block(field, f"不是合法 ISO 时间：{exc}")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _block(field, "必须带明确时区偏移")
    return value


def _require_object(value, field: str) -> dict:
    if not isinstance(value, dict):
        _block(field, f"必须是对象，实际 {type(value).__name__}")
    return value


def _require_list(value, field: str) -> list:
    if not isinstance(value, list):
        _block(field, f"必须是列表，实际 {type(value).__name__}")
    return value


def _require_bool_false(value, field: str) -> None:
    if value is not False:
        _block(field, f"必须是严格 false，实际 {value!r}")


def _require_closed_keys(obj, allowed, field: str) -> dict:
    value = _require_object(obj, field)
    for key in sorted(value.keys(), key=lambda item: str(item).encode("utf-8")):
        if key not in allowed:
            _block(field, f"含未允许的键 {key!r}")
    for key in allowed:
        if key not in value:
            _block(field, f"缺少必需键 {key!r}")
    return value


def _safe_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def _project_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except (ValueError, OSError) as exc:
        raise RuntimeGate1Blocked("path", f"路径不在项目内：{path}") from exc


def _is_reparse_point(path: Path, field: str) -> bool:
    """真实 lstat 判定；OSError 不吞成 False。"""
    try:
        stat = path.lstat()
    except OSError as exc:
        raise RuntimeGate1Error(f"lstat.{field}", f"无法读取路径状态：{path}：{exc}") from exc
    if os.name == "nt":
        return bool(getattr(stat, "st_file_attributes", 0) & 0x400)
    return path.is_symlink()


def _reject_reparse_chain(path: Path, field: str) -> None:
    """按**原始绝对路径**逐级检查 reparse，再 resolve 复查（不先 resolve 抹掉 alias）。"""
    current = path if path.is_absolute() else (Path.cwd() / path)
    parts = list(current.parts)
    for index in range(1, len(parts) + 1):
        candidate = Path(*parts[:index])
        try:
            exists = candidate.exists()
        except OSError as exc:
            raise RuntimeGate1Error(f"exists.{field}",
                                    f"无法判断路径存在性：{candidate}：{exc}") from exc
        if not exists:
            continue
        if _is_reparse_point(candidate, field):
            _block(field, f"路径含 link/junction/reparse：{candidate}")
    try:
        resolved = current.resolve()
    except OSError as exc:
        raise RuntimeGate1Error(f"resolve.{field}", f"{current}：{exc}") from exc
    if resolved != current and _is_reparse_point(resolved, field):
        _block(field, f"resolve 后仍为 reparse：{resolved}")


def _capture_file(path, stage: str) -> dict:
    """一次实读并固定：字节、长度、SHA。所有消费读数都经此函数。"""
    target = Path(path) if not isinstance(path, Path) else path
    try:
        data = target.read_bytes()
    except OSError as exc:
        raise RuntimeGate1Error(stage, f"读取失败：{target}：{exc}") from exc
    return {"path": str(target), "bytes": data, "byte_size": len(data),
            "file_sha256": _sha_bytes(data)}


def _recheck_capture(capture: dict, field: str) -> None:
    """末端确认：先对本次已消费路径做逐级 reparse 复查，再比较当前磁盘字节。"""
    path = Path(capture["path"])
    _reject_reparse_chain(path, field)
    current = _capture_file(path, f"final.{field}")
    if current["bytes"] != capture["bytes"]:
        _block(field, "末端确认时文件字节与本次绑定读数不一致")
    if current["file_sha256"] != capture["file_sha256"] \
            or current["byte_size"] != capture["byte_size"]:
        _block(field, "末端确认时长度/SHA 与本次绑定读数不一致")


def _write_exclusive(path: Path, buffer: bytes, stage: str) -> None:
    try:
        with open(path, "xb") as handle:
            handle.write(buffer)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RuntimeGate1Blocked(_safe_relative(path), "目标已存在，拒绝覆盖") from exc
    except OSError as exc:
        raise RuntimeGate1Error(stage, f"独占写失败：{path}：{exc}") from exc
    except Exception as exc:  # noqa: BLE001 - 真实 writer 写后异常必须映射为 Error 并保留原因
        raise RuntimeGate1Error(
            stage, f"独占写异常：{type(exc).__name__}: {exc}") from exc


def _iter_dir(path, stage: str) -> list:
    target = Path(path) if not isinstance(path, Path) else path
    try:
        return sorted(item.name for item in target.iterdir())
    except OSError as exc:
        raise RuntimeGate1Error(stage, f"无法枚举目录：{target}：{exc}") from exc


def _require_descendant(path: Path, root: Path, field: str, *, allow_equal: bool = False) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        _block(field, f"必须位于 {_safe_relative(root)} 之内：{_safe_relative(path)}")
    if not allow_equal and str(relative) in ("", "."):
        _block(field, f"不能是 {_safe_relative(root)} 本身")


def _parse_json_object(buffer: bytes, field: str) -> dict:
    try:
        parsed = json.loads(buffer.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _block(field, f"不是合法 UTF-8 JSON：{exc}")
    if not isinstance(parsed, dict):
        _block(field, f"顶层必须是对象，实际 {type(parsed).__name__}")
    return parsed


# --------------------------------------------------------------------------- 冻结准备器


def _load_frozen_prepare():
    """加载冻结准备器；加载/使用前以其**独立预期 SHA** 实读核验。"""
    path = PROJECT_ROOT / "scripts" / "prepare_demo_human_gate1.py"
    capture = _capture_file(path, "read.frozen_prepare")
    if capture["file_sha256"] != FROZEN_PREPARE_SHA256:
        _block("scripts/prepare_demo_human_gate1.py",
               f"冻结准备器字节与独立预期不一致：{capture['file_sha256']}")
    name = "frozen_prepare_human_gate1_runtime"
    module = sys.modules.get(name)
    if module is not None and getattr(module, "__frozen_sha256__", None) == FROZEN_PREPARE_SHA256:
        return module
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeGate1Error("prepare_load", f"无法建立 spec：{path}")
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
    except (RuntimeGate1Blocked, RuntimeGate1Error):
        raise
    except Exception as exc:  # noqa: BLE001 - 加载失败按运行错误分类
        raise RuntimeGate1Error("prepare_load", f"{type(exc).__name__}: {exc}") from exc
    loaded.__frozen_sha256__ = FROZEN_PREPARE_SHA256
    sys.modules[name] = loaded
    return loaded


def _call_frozen_prepare(batch_dir: Path, request_id: str) -> dict:
    prepare_module = _load_frozen_prepare()
    try:
        result = prepare_module.prepare_human_gate1_request(batch_dir, request_id)
    except Exception as exc:  # noqa: BLE001 - 保留冻结准备器的定位/原因
        field = getattr(exc, "field", None)
        reason = getattr(exc, "reason", None)
        if isinstance(field, str) and isinstance(reason, str):
            raise RuntimeGate1Blocked(f"prepare.{field}", reason) from exc
        stage = getattr(exc, "stage", None)
        if isinstance(stage, str):
            raise RuntimeGate1Error(f"prepare.{stage}",
                                    str(getattr(exc, "reason", exc))) from exc
        raise RuntimeGate1Error("prepare_call", f"{type(exc).__name__}: {exc}") from exc
    return _require_object(result, "prepare.result")


def _source_check(batch_dir: Path, request_id: str, captures: dict) -> dict:
    """真实调用冻结准备器一次，复用其来源核验结果；批次八文件读数已在 captures。"""
    result = _call_frozen_prepare(batch_dir, request_id)
    _require_closed_keys(result, ("request_version", "status", "materials", "expectations",
                                 "evidence", "boundaries"), "prepare.result")
    materials = _require_object(result["materials"], "prepare.materials")
    evidence = _require_object(result["evidence"], "prepare.evidence")
    boundaries = _require_object(result["boundaries"], "prepare.boundaries")
    _require_closed_keys(evidence, EVIDENCE_KEYS, "prepare.evidence")
    _require_closed_keys(boundaries, BOUNDARY_KEYS, "prepare.boundaries")
    for key, value in boundaries.items():
        _require_bool_false(value, f"prepare.boundaries.{key}")
    quality = _require_object(materials.get("quality"), "prepare.materials.quality")
    _require_closed_keys(quality, QUALITY_KEYS, "prepare.materials.quality")
    if quality["status"] not in ("OK", "BLOCKED"):
        _block("prepare.materials.quality.status",
               f"必须是 OK 或 BLOCKED，实际 {quality['status']!r}")
    batch_id = _require_nonempty_str(materials.get("batch_id"), "prepare.materials.batch_id")
    files = _require_list(materials.get("files"), "prepare.materials.files")
    if len(files) != 31:
        _block("prepare.materials.files", f"冻结准备器来源材料必须恰 31 项，实际 {len(files)}")
    batch_files, project_files = [], []
    for index, raw in enumerate(files):
        entry = _require_object(raw, f"prepare.materials.files[{index}]")
        _require_closed_keys(entry, FILE_ITEM_KEYS, f"prepare.materials.files[{index}]")
        relative = _require_nonempty_str(entry["relative"],
                                         f"prepare.materials.files[{index}].relative")
        _require_hash(entry["file_sha256"], f"prepare.materials.files[{index}].file_sha256")
        if not _is_strict_int(entry["byte_size"]) or entry["byte_size"] < 0:
            _block(f"prepare.materials.files[{index}].byte_size", "必须是非负严格整数")
        record = {"relative": relative, "file_sha256": entry["file_sha256"],
                  "byte_size": entry["byte_size"]}
        if relative.startswith("batch/"):
            batch_files.append(record)
        elif relative.startswith("project/"):
            project_files.append(record)
        else:
            _block(f"prepare.materials.files[{index}].relative",
                   f"来源材料必须使用 batch/ 或 project/ 前缀，实际 {relative!r}")
    batch_files.sort(key=lambda item: item["relative"].encode("utf-8"))
    project_files.sort(key=lambda item: item["relative"].encode("utf-8"))
    # 来源核验返回后：对全部 23 份既有 project 材料同缓冲实读，并与该次声明闭合
    captures.setdefault("project", {})
    for entry in project_files:
        relative = entry["relative"][len("project/"):]
        capture = _capture_file(PROJECT_ROOT / relative, f"read.{relative}")
        captures["project"][relative] = capture
        if capture["file_sha256"] != entry["file_sha256"] \
                or capture["byte_size"] != entry["byte_size"]:
            _block(f"project/{relative}", "实读字节与冻结准备器声明不一致")
    stale = sorted(set(captures["project"])
                   - {item["relative"][len("project/"):] for item in project_files})
    if stale:
        _block("prepare.materials.files", f"存在未被来源核验覆盖的 project 材料：{stale}")
    if len(batch_files) != 8 or len(project_files) != 23:
        _block("prepare.materials.files",
               f"来源材料必须恰为 8 项 batch/ + 23 项 project/，实际 "
               f"{len(batch_files)} + {len(project_files)}")
    if any(item["relative"] == "project/scripts/record_demo_human_gate1.py"
           for item in project_files):
        _block("prepare.materials.files",
               "来源材料不得含旧 Gate1 适配器（新运行层只用本脚本）")
    for item in batch_files:
        relative = item["relative"][len("batch/"):]
        capture = captures.get(relative)
        if capture is None:
            _block(f"batch/{relative}", "缺少本次批次八文件读数")
        if capture["file_sha256"] != item["file_sha256"] \
                or capture["byte_size"] != item["byte_size"]:
            _block(f"batch/{relative}", "实读字节与冻结准备器声明不一致")
    return {"batch_id": batch_id, "batch_files": batch_files,
            "project_files": project_files, "quality": copy.deepcopy(quality),
            "evidence": evidence}


# --------------------------------------------------------------------------- 路径检查


def _require_fixed_members(directory: Path, expected, field: str) -> None:
    """固定目录集合：成员必须恰为期望集合（多一项即拒绝）。"""
    _reject_reparse_chain(directory, field)
    if not directory.is_dir():
        _block(field, f"目录不存在：{_safe_relative(directory)}")
    actual = set(_iter_dir(directory, f"list.{field}"))
    expected_set = set(expected)
    if actual != expected_set:
        _block(field, "目录集合与固定期望不一致："
                      f"多出 {sorted(actual - expected_set)}、"
                      f"缺少 {sorted(expected_set - actual)}")


def _check_batch_dir(batch_dir, captures: dict) -> Path:
    if not isinstance(batch_dir, (str, os.PathLike)):
        _block("batch_dir", f"必须是路径，实际 {type(batch_dir).__name__}")
    raw = Path(batch_dir)
    _reject_reparse_chain(raw, "batch_dir")
    try:
        target = raw.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.batch_dir", f"{raw}：{exc}") from exc
    if not target.is_dir():
        _block("batch_dir", f"批次目录不存在：{_safe_relative(target)}")
    _require_descendant(target, BATCH_ROOT, "batch_dir")
    _require_fixed_members(target, TOP_LEVEL_MEMBERS, "batch_dir(顶层)")
    for name in BATCH_FILES:
        path = target / name
        _reject_reparse_chain(path, f"batch/{name}")
        if not path.is_file():
            _block("batch_dir", f"缺少接收批次文件：{name}")
        captures[name] = _capture_file(path, f"read.batch.{name}")
    for sub, leaves in BATCH_SUBDIR_FILES.items():
        subdir = target / sub
        _require_fixed_members(subdir, leaves, f"batch/{sub}")
        for leaf in leaves:
            path = subdir / leaf
            _reject_reparse_chain(path, f"batch/{sub}/{leaf}")
            if not path.is_file():
                _block("batch_dir", f"缺少接收批次文件：{sub}/{leaf}")
    return target


def _check_scope_dir(scope_dir) -> Path:
    """scope 是计划技术路径：必须**尚不存在**且位于 Gate1 记录根之下。"""
    if not isinstance(scope_dir, (str, os.PathLike)):
        _block("scope_dir", f"必须是路径，实际 {type(scope_dir).__name__}")
    raw = Path(scope_dir)
    _reject_reparse_chain(raw, "scope_dir")
    try:
        target = raw.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.scope_dir", f"{raw}：{exc}") from exc
    _require_descendant(target, GATE1_RECORDS_ROOT, "scope_dir")
    if target.exists():
        _block("scope_dir",
               f"scope 必须尚不存在（本层不创建、也不接受既有 scope）："
               f"{_safe_relative(target)}")
    if not target.parent.is_dir():
        _block("scope_dir", f"scope 的技术父目录不存在：{_safe_relative(target.parent)}")
    return target


def _check_runtime_parent(runtime_dir) -> Path:
    """runtime_dir 必须是 data/runtime/ 内从未存在的新叶（空目录也拒绝）。"""
    if not isinstance(runtime_dir, (str, os.PathLike)):
        _block("runtime_dir", f"必须是路径，实际 {type(runtime_dir).__name__}")
    raw = Path(runtime_dir)
    _reject_reparse_chain(raw, "runtime_dir")
    try:
        target = raw.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.runtime_dir", f"{raw}：{exc}") from exc
    _require_descendant(target, RUNTIME_ROOT, "runtime_dir")
    if target.exists():
        _block("runtime_dir",
               f"目标已存在（含空目录），拒绝复用：{_safe_relative(target)}")
    if not target.parent.is_dir():
        _block("runtime_dir", f"技术父目录不存在：{_safe_relative(target.parent)}")
    return target


def _reject_overlap(batch_dir: Path, runtime_dir: Path, scope_dir: Path) -> None:
    def _ancestor(ancestor: Path, node: Path) -> bool:
        return ancestor == node or ancestor in node.parents

    if _ancestor(batch_dir, runtime_dir) or _ancestor(runtime_dir, batch_dir):
        _block("runtime_dir", "runtime_dir 与 batch_dir 不得相等或互为祖先")
    if _ancestor(scope_dir, runtime_dir) or _ancestor(runtime_dir, scope_dir):
        _block("runtime_dir", "runtime_dir 与 scope_dir 不得相等或互为祖先")
    if _ancestor(scope_dir, batch_dir) or _ancestor(batch_dir, scope_dir):
        _block("scope_dir", "scope_dir 与 batch_dir 不得相等或互为祖先")


# --------------------------------------------------------------------------- 清单与绑定


def _require_project_file(relative: str, captures: dict) -> dict:
    path = PROJECT_ROOT / relative
    _reject_reparse_chain(path, relative)
    if not path.is_file():
        _block(relative, "项目文件不存在")
    captures.setdefault("project", {})[relative] = _capture_file(path, f"read.{relative}")
    frozen = INITIAL_COMPONENT_SHA256.get(relative) or RECORDING_COMPONENT_SHA256.get(relative)
    if frozen is not None and captures["project"][relative]["file_sha256"] != frozen:
        _block(relative, "与初判组件/协议独立冻结身份不一致")
    return captures["project"][relative]


def _build_code_manifest(captures: dict, self_capture: dict) -> dict:
    entries = []
    for relative in CODE_FILES:
        capture = _require_project_file(relative, captures)
        entries.append({"relative": relative, "file_sha256": capture["file_sha256"]})
    entries.append({"relative": SCRIPT_RELATIVE, "file_sha256": self_capture["file_sha256"]})
    for relative in INITIAL_COMPONENT_SHA256:
        if relative not in CODE_FILES:
            _require_project_file(relative, captures)
    entries.sort(key=lambda item: item["relative"].encode("utf-8"))
    if len(entries) != 17 or len({item["relative"] for item in entries}) != 17:
        _block("code_manifest", "必须恰 17 项且 relative 唯一")
    return {"entries": entries, "manifest_version": CODE_MANIFEST_VERSION}


def _build_rules_manifest(captures: dict) -> dict:
    entries = []
    for rule_id in RULE_IDS:
        relative = RULE_FILES[rule_id]
        capture = _require_project_file(relative, captures)
        entries.append({"rule_id": rule_id, "rule_version": RULE_VERSIONS[rule_id],
                        "relative": relative, "file_sha256": capture["file_sha256"]})
    entries.sort(key=lambda item: item["relative"].encode("utf-8"))
    if len(entries) != 4 or len({item["relative"] for item in entries}) != 4:
        _block("rules_manifest", "必须恰 4 项且 relative 唯一")
    return {"entries": entries, "version": RULES_MANIFEST_VERSION}


def _build_run_binding(code_manifest: dict, rules_manifest: dict, config_capture: dict,
                       input_capture: dict, self_capture: dict) -> dict:
    return {
        "code": {"file_sha256": self_capture["file_sha256"],
                 "manifest_fingerprint": fingerprint(code_manifest)},
        "rules": {"version": RULES_MANIFEST_VERSION,
                  "manifest_fingerprint": fingerprint(rules_manifest)},
        "config": {"file_sha256": config_capture["file_sha256"]},
        "input": {"file_sha256": input_capture["file_sha256"]},
    }


def _build_contract(captures: dict) -> dict:
    contract = _require_project_file(CONTRACT_RELATIVE, captures)
    _require_project_file(CONTRACT_EFFECTIVE_RELATIVE, captures)
    if contract["file_sha256"] != EXPECTED_CONTRACT_SHA256:
        _block(CONTRACT_RELATIVE, "与冻结正式契约字节 SHA 不一致")
    return {"contract_version": EXPECTED_CONTRACT_VERSION,
            "contract_file_sha256": contract["file_sha256"], "contract_effective": True}


# --------------------------------------------------------------------------- 校验


def _validate_run_binding(binding, field: str) -> dict:
    value = _require_closed_keys(binding, RUN_BINDING_KEYS, field)
    _require_closed_keys(value["code"], RUN_CODE_KEYS, f"{field}.code")
    _require_hash(value["code"]["file_sha256"], f"{field}.code.file_sha256")
    _require_hash(value["code"]["manifest_fingerprint"],
                  f"{field}.code.manifest_fingerprint")
    _require_closed_keys(value["rules"], RUN_RULES_KEYS, f"{field}.rules")
    if value["rules"]["version"] != RULES_MANIFEST_VERSION:
        _block(f"{field}.rules.version", f"必须是 {RULES_MANIFEST_VERSION}")
    _require_hash(value["rules"]["manifest_fingerprint"],
                  f"{field}.rules.manifest_fingerprint")
    _require_closed_keys(value["config"], RUN_SINGLE_KEYS, f"{field}.config")
    _require_hash(value["config"]["file_sha256"], f"{field}.config.file_sha256")
    _require_closed_keys(value["input"], RUN_SINGLE_KEYS, f"{field}.input")
    _require_hash(value["input"]["file_sha256"], f"{field}.input.file_sha256")
    return value


def _validate_manifest_entries(entries, allowed_keys, field: str, *, expected_count: int,
                               unique_key: str = "relative") -> list:
    items = _require_list(entries, field)
    if len(items) != expected_count:
        _block(field, f"必须恰 {expected_count} 项，实际 {len(items)}")
    seen = set()
    previous = None
    for index, raw in enumerate(items):
        item = _require_object(raw, f"{field}[{index}]")
        _require_closed_keys(item, allowed_keys, f"{field}[{index}]")
        _require_nonempty_str(item["relative"], f"{field}[{index}].relative")
        _require_hash(item["file_sha256"], f"{field}[{index}].file_sha256")
        key = item[unique_key]
        if key in seen:
            _block(field, f"{unique_key} 必须唯一，重复 {key!r}")
        seen.add(key)
        encoded = item["relative"].encode("utf-8")
        if previous is not None and encoded <= previous:
            _block(field, "必须按 relative UTF-8 字节升序排列")
        previous = encoded
    return items


def _validate_registry(registry, *, allow_existing_scope: bool = False) -> dict:
    value = _require_object(registry, "registry")
    if "registry_version" not in value or value["registry_version"] != REGISTRY_VERSION:
        _block("registry.registry_version", f"必须是 {REGISTRY_VERSION}")
    _require_closed_keys(value, REGISTRY_KEYS, "registry")
    _history_namespace_capture_038(value["initial_judgment_history"])
    _require_nonempty_str(value["batch_id"], "registry.batch_id")
    _require_iso_time(value["registered_at"], "registry.registered_at")
    scope_ref = _require_nonempty_str(value["scope_ref"], "registry.scope_ref")
    if not scope_ref.startswith("data/human_gate_decision_records/gate1/"):
        _block("registry.scope_ref", "必须是 Gate1 记录根下的项目相对路径")
    scope_path = PROJECT_ROOT / scope_ref
    _reject_reparse_chain(scope_path, "registry.scope_ref")
    _require_descendant(scope_path.resolve(), GATE1_RECORDS_ROOT, "registry.scope_ref")
    if scope_path.exists() and not allow_existing_scope:
        _block("registry.scope_ref",
               f"scope 计划路径必须尚不存在（不接受既有 scope）：{scope_ref}")
    if allow_existing_scope and not scope_path.is_dir():
        _block("registry.scope_ref", "该已核验分支要求登记 scope 确实存在")
    if value["note"] != REGISTRY_NOTE:
        _block("registry.note", "必须是设计常量")

    batch_files = _validate_manifest_entries(
        value["batch_files"], FILE_ITEM_KEYS, "registry.batch_files", expected_count=8)
    for index, item in enumerate(batch_files):
        if not item["relative"].startswith("batch/"):
            _block(f"registry.batch_files[{index}].relative", "必须使用 batch/ 前缀")
        if not _is_strict_int(item["byte_size"]) or item["byte_size"] < 0:
            _block(f"registry.batch_files[{index}].byte_size", "必须是非负严格整数")
    if {item["relative"] for item in batch_files} != {"batch/" + name for name in BATCH_FILES}:
        _block("registry.batch_files", "必须恰为接收批次八文件的 batch/ 逻辑集合")

    code_manifest = _require_object(value["code_manifest"], "registry.code_manifest")
    _require_closed_keys(code_manifest, ("entries", "manifest_version"),
                         "registry.code_manifest")
    if code_manifest["manifest_version"] != CODE_MANIFEST_VERSION:
        _block("registry.code_manifest.manifest_version", f"必须是 {CODE_MANIFEST_VERSION}")
    code_entries = _validate_manifest_entries(
        code_manifest["entries"], ("relative", "file_sha256"),
        "registry.code_manifest.entries", expected_count=17)
    expected_code = sorted([*CODE_FILES, SCRIPT_RELATIVE], key=lambda v: v.encode("utf-8"))
    if [item["relative"] for item in code_entries] != expected_code:
        _block("registry.code_manifest.entries", "必须恰为冻结 16 项代码 + 本脚本")

    rules_manifest = _require_object(value["rules_manifest"], "registry.rules_manifest")
    _require_closed_keys(rules_manifest, ("entries", "version"),
                         "registry.rules_manifest")
    if rules_manifest["version"] != RULES_MANIFEST_VERSION:
        _block("registry.rules_manifest.version", f"必须是 {RULES_MANIFEST_VERSION}")
    rules_entries = _validate_manifest_entries(
        rules_manifest["entries"], ("rule_id", "rule_version", "relative", "file_sha256"),
        "registry.rules_manifest.entries", expected_count=4)
    for index, item in enumerate(rules_entries):
        rule_id = item["rule_id"]
        if not isinstance(rule_id, str) or rule_id.strip() == "":
            _block(f"registry.rules_manifest.entries[{index}].rule_id",
                   f"必须是非空字符串，实际 {type(rule_id).__name__}")
        expected_relative = RULE_FILES.get(rule_id)
        if expected_relative is None:
            _block(f"registry.rules_manifest.entries[{index}].rule_id",
                   f"未知规则 ID {rule_id!r}")
        if item["relative"] != expected_relative:
            _block(f"registry.rules_manifest.entries[{index}].relative",
                   f"必须为 {expected_relative}")
        expected_version = RULE_VERSIONS[rule_id]
        if item["rule_version"] != expected_version:
            _block(f"registry.rules_manifest.entries[{index}].rule_version",
                   f"必须为 {expected_version}")

    config = _require_object(value["config"], "registry.config")
    _require_closed_keys(config, ("file_sha256", "config_ref"), "registry.config")
    if config["config_ref"] != CONFIG_REF:
        _block("registry.config.config_ref", f"必须是 {CONFIG_REF}")
    _require_hash(config["file_sha256"], "registry.config.file_sha256")

    input_block = _require_object(value["input"], "registry.input")
    _require_closed_keys(input_block, ("file_sha256", "byte_size", "input_ref"),
                         "registry.input")
    if input_block["input_ref"] != INPUT_REF:
        _block("registry.input.input_ref", f"必须是 {INPUT_REF}")
    _require_hash(input_block["file_sha256"], "registry.input.file_sha256")
    if not _is_strict_int(input_block["byte_size"]) or input_block["byte_size"] < 0:
        _block("registry.input.byte_size", "必须是非负严格整数")

    contract = _require_object(value["contract"], "registry.contract")
    _require_closed_keys(contract, ("contract_version", "contract_file_sha256",
                                    "contract_effective"), "registry.contract")
    if contract["contract_version"] != EXPECTED_CONTRACT_VERSION:
        _block("registry.contract.contract_version", f"必须是 {EXPECTED_CONTRACT_VERSION}")
    if contract["contract_file_sha256"] != EXPECTED_CONTRACT_SHA256:
        _block("registry.contract.contract_file_sha256", "与冻结正式契约不一致")
    if contract["contract_effective"] is not True:
        _block("registry.contract.contract_effective", "必须是严格 true")

    binding = _validate_run_binding(value["run_binding"], "registry.run_binding")
    _require_hash(value["run_binding_sha256"], "registry.run_binding_sha256")
    if value["run_binding_sha256"] != fingerprint(binding):
        _block("registry.run_binding_sha256", "必须等于内层 run_binding 的规范指纹")

    if binding["code"]["manifest_fingerprint"] != fingerprint(code_manifest):
        _block("registry.run_binding.code.manifest_fingerprint",
               "必须等于 code_manifest 正文的规范指纹")
    if binding["rules"]["manifest_fingerprint"] != fingerprint(rules_manifest):
        _block("registry.run_binding.rules.manifest_fingerprint",
               "必须等于 rules_manifest 正文的规范指纹")
    code_map = {item["relative"]: item["file_sha256"] for item in code_entries}
    if binding["code"]["file_sha256"] != code_map[SCRIPT_RELATIVE]:
        _block("registry.run_binding.code.file_sha256", "必须等于清单中本脚本条目的 SHA")
    if binding["config"]["file_sha256"] != config["file_sha256"]:
        _block("registry.run_binding.config.file_sha256", "必须与 registry.config 一致")
    if binding["input"]["file_sha256"] != input_block["file_sha256"]:
        _block("registry.run_binding.input.file_sha256", "必须与 registry.input 一致")
    input_entry = next((item for item in batch_files
                        if item["relative"] == "batch/source/input.xlsx"), None)
    if input_entry is None:
        _block("registry.batch_files", "缺少 batch/source/input.xlsx")
    if input_entry["file_sha256"] != input_block["file_sha256"] \
            or input_entry["byte_size"] != input_block["byte_size"]:
        _block("registry.batch_files[batch/source/input.xlsx]",
               "必须与 registry.input 的长度/SHA 一致")
    return value


def _validate_readback(readback, registry: dict, registry_buffer: bytes) -> dict:
    value = _require_closed_keys(readback, READBACK_KEYS, "readback")
    if value["readback_version"] != READBACK_VERSION:
        _block("readback.readback_version", f"必须是 {READBACK_VERSION}")
    _require_hash(value["registry_sha256"], "readback.registry_sha256")
    _require_hash(value["registry_file_sha256"], "readback.registry_file_sha256")
    _require_hash(value["run_binding_sha256"], "readback.run_binding_sha256")
    if not _is_strict_int(value["registry_byte_size"]) or value["registry_byte_size"] < 0:
        _block("readback.registry_byte_size", "必须是非负严格整数")
    if value["registry_sha256"] != fingerprint(registry):
        _block("readback.registry_sha256", "必须等于登记对象的规范指纹")
    if value["registry_file_sha256"] != _sha_bytes(registry_buffer):
        _block("readback.registry_file_sha256", "必须等于登记文件字节 SHA")
    if value["registry_byte_size"] != len(registry_buffer):
        _block("readback.registry_byte_size", "必须等于登记文件字节长度")
    if value["run_binding_sha256"] != registry["run_binding_sha256"]:
        _block("readback.run_binding_sha256", "必须等于登记内层 run_binding 指纹")
    return value


def _require_canonical_payload(buffer: bytes, obj, field: str) -> None:
    if _payload_bytes(obj) != buffer:
        _block(field, "不是 canonical JSON 加单个 LF")


def _require_current_static_identity(registry: dict, self_capture: dict,
                                     captures: dict) -> None:
    """read 也核对**本次**代码/静态冻结字节；消费的 capture 并入本次读数集合供末端复测。"""
    binding = registry["run_binding"]
    if binding["code"]["file_sha256"] != self_capture["file_sha256"]:
        _block("registry.run_binding.code.file_sha256",
               "与本次运行的脚本字节不一致（登记由旧版本写入）")
    entries = {item["relative"]: item["file_sha256"]
               for item in registry["code_manifest"]["entries"]}
    captures.setdefault("project", {})
    for relative in CODE_FILES:
        capture = _capture_file(PROJECT_ROOT / relative, f"read.{relative}")
        captures["project"][relative] = capture
        if relative in INITIAL_COMPONENT_SHA256 and capture["file_sha256"] != INITIAL_COMPONENT_SHA256[relative]:
            _block(relative, "与初判组件独立冻结身份不一致")
        if entries[relative] != capture["file_sha256"]:
            _block(f"registry.code_manifest.entries[{relative}]",
                   "与当前冻结文件字节不一致")
    for item in registry["rules_manifest"]["entries"]:
        relative = _require_nonempty_str(item["relative"],
                                         "registry.rules_manifest.entries.relative")
        capture = _capture_file(PROJECT_ROOT / relative, f"read.{relative}")
        captures["project"][relative] = capture
        if item["file_sha256"] != capture["file_sha256"]:
            _block(f"registry.rules_manifest.entries[{relative}]",
                   "与当前规则文件字节不一致")
    for extra in PROJECT_MATERIAL_EXTRAS:
        captures["project"][extra] = _capture_file(PROJECT_ROOT / extra, f"read.{extra}")
        if extra in INITIAL_COMPONENT_SHA256 and captures["project"][extra]["file_sha256"] != INITIAL_COMPONENT_SHA256[extra]:
            _block(extra, "与初判协议/案例独立冻结身份不一致")
    prepare_capture = _capture_file(PROJECT_ROOT / "scripts" / "prepare_demo_human_gate1.py",
                                    "read.frozen_prepare")
    captures["frozen_prepare"] = prepare_capture
    if prepare_capture["file_sha256"] != FROZEN_PREPARE_SHA256:
        _block("scripts/prepare_demo_human_gate1.py", "冻结准备器字节与独立预期不一致")
    config_capture = _capture_file(PROJECT_ROOT / CONFIG_REF, f"read.{CONFIG_REF}")
    captures["project"][CONFIG_REF] = config_capture
    if registry["config"]["file_sha256"] != config_capture["file_sha256"]:
        _block("registry.config.file_sha256", "与当前冻结配置字节不一致")
    contract_capture = _capture_file(PROJECT_ROOT / CONTRACT_RELATIVE,
                                     f"read.{CONTRACT_RELATIVE}")
    captures["project"][CONTRACT_RELATIVE] = contract_capture
    if contract_capture["file_sha256"] != EXPECTED_CONTRACT_SHA256:
        _block(CONTRACT_RELATIVE, "与冻结正式契约字节 SHA 不一致")
    captures["project"][CONTRACT_EFFECTIVE_RELATIVE] = _capture_file(
        PROJECT_ROOT / CONTRACT_EFFECTIVE_RELATIVE, f"read.{CONTRACT_EFFECTIVE_RELATIVE}")


def _read_registry_leaf(runtime_dir) -> Path:
    if not isinstance(runtime_dir, (str, os.PathLike)):
        _block("runtime_dir", f"必须是路径，实际 {type(runtime_dir).__name__}")
    raw = Path(runtime_dir)
    _reject_reparse_chain(raw, "runtime_dir")
    try:
        leaf = raw.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.runtime_dir", f"{raw}：{exc}") from exc
    _require_descendant(leaf, RUNTIME_ROOT, "runtime_dir")
    if not leaf.is_dir():
        _block("runtime_dir", f"登记叶目录不存在：{_safe_relative(leaf)}")
    return leaf


def _load_stored_registry(leaf: Path, *, allow_existing_scope: bool = False) -> tuple:
    """读取并完整核验两份登记文件；返回 (registry, readback, captures)。"""
    registry_path = leaf / REGISTRY_FILE
    readback_path = leaf / READBACK_FILE
    _reject_reparse_chain(registry_path, REGISTRY_FILE)
    _reject_reparse_chain(readback_path, READBACK_FILE)
    listing = _iter_dir(leaf, "list.runtime_dir")
    if FAILURE_FILE in listing:
        _block(f"{_safe_relative(leaf)}/{FAILURE_FILE}", "登记目录含失败诊断，拒绝读取")
    if listing != sorted([REGISTRY_FILE, READBACK_FILE]):
        _block(_safe_relative(leaf), f"登记叶目录只允许两份登记文件，实际 {listing}")
    registry_capture = _capture_file(registry_path, "read.registry")
    readback_capture = _capture_file(readback_path, "read.readback")
    registry = _parse_json_object(registry_capture["bytes"], _safe_relative(registry_path))
    readback = _parse_json_object(readback_capture["bytes"], _safe_relative(readback_path))
    _require_canonical_payload(registry_capture["bytes"], registry,
                               _safe_relative(registry_path))
    _require_canonical_payload(readback_capture["bytes"], readback,
                               _safe_relative(readback_path))
    registry = _validate_registry(registry, allow_existing_scope=allow_existing_scope)
    _validate_readback(readback, registry, registry_capture["bytes"])
    return registry, readback, {"registry": registry_capture, "readback": readback_capture,
        "history_namespace": _history_namespace_capture_038(registry["initial_judgment_history"])}


def read_runtime_registry(runtime_dir) -> dict:
    """只读核验已存储登记、readback 与**本次**运行代码/静态绑定。

    签名没有 batch_dir，因此**不宣称**已核验当前批次来源。
    成功外层恰两键：`registry` / `registry_file_sha256`。
    """
    leaf = _read_registry_leaf(runtime_dir)
    registry, _, captures = _load_stored_registry(leaf)
    self_capture = _capture_file(MODULE_PATH, "read.self")
    static_captures: dict = {}
    _require_current_static_identity(registry, self_capture, static_captures)
    # 末端确认：消费的两份登记 + 全部静态代码/规则/配置/契约 + 自身字节
    _recheck_capture(captures["registry"], REGISTRY_FILE)
    _recheck_capture(captures["readback"], READBACK_FILE)
    _recheck_capture(self_capture, "self")
    for relative, capture in sorted(static_captures.get("project", {}).items()):
        _recheck_capture(capture, relative)
    _recheck_capture(static_captures["frozen_prepare"], "scripts/prepare_demo_human_gate1.py")
    _require_fixed_members(leaf, [REGISTRY_FILE, READBACK_FILE], "runtime_dir(叶)")
    # 末端确认：计划 scope 仍必须是尚不存在的技术路径（本层不创建、也不复用）
    scope_path = PROJECT_ROOT / registry["scope_ref"]
    _reject_reparse_chain(scope_path, "registry.scope_ref")
    if scope_path.exists():
        _block("registry.scope_ref",
               "末端确认时计划 scope 已被创建（本次核验期间状态变化）")
    _confirm_history_namespace_038(captures["history_namespace"])
    return {"registry": copy.deepcopy(registry),
            "registry_file_sha256": captures["registry"]["file_sha256"]}


# --------------------------------------------------------------------------- 失败诊断


def _write_failure(leaf: Path, stage: str, field, reason: str, cause_chain) -> None:
    payload = {"failure_version": FAILURE_VERSION, "stage": stage, "field": field,
               "reason": reason, "cause_chain": list(cause_chain)}
    try:
        _write_exclusive(leaf / FAILURE_FILE, _payload_bytes(payload), "write.failure")
    except Exception as nested:  # noqa: BLE001 - 诊断自身失败保留两层错误
        raise RuntimeGate1Error(
            "write.failure",
            f"诊断写出失败：{type(nested).__name__}: {nested}；原始错误：{reason}",
        ) from nested


def _cause_chain(exc: BaseException) -> list:
    chain, node, seen = [], exc, set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        chain.append(f"{type(node).__name__}: {node}")
        node = node.__cause__ or node.__context__
    return chain


# --------------------------------------------------------------------------- 公开 API


def build_runtime_registry(batch_dir, runtime_dir, *, scope_dir, initial_judgment_history) -> dict:
    """核验来源 → 独占固定运行登记 → 写两份登记文件并读回。

    成功外层恰三键：`registry` / `registry_sha256` / `registry_file_sha256`。
    登记是技术动作，不是决定、不是批准、不赋予任何执行许可。
    """
    captures: dict = {}
    batch_path = _check_batch_dir(batch_dir, captures)
    scope_path = _check_scope_dir(scope_dir)
    leaf = _check_runtime_parent(runtime_dir)
    _reject_overlap(batch_path, leaf, scope_path)
    history_namespace = _history_namespace_capture_038(initial_judgment_history)
    created = False
    stage = "source_check"
    try:
        self_capture = _capture_file(MODULE_PATH, "read.self")
        source = _source_check(batch_path, REGISTRATION_SOURCE_CHECK_ID, captures)
        code_manifest = _build_code_manifest(captures, self_capture)
        rules_manifest = _build_rules_manifest(captures)
        config_capture = _require_project_file(CONFIG_REF, captures)
        input_capture = captures["source/input.xlsx"]
        binding = _build_run_binding(code_manifest, rules_manifest, config_capture,
                                     input_capture, self_capture)
        contract = _build_contract(captures)
        registry = {
            "registry_version": REGISTRY_VERSION,
            "batch_id": source["batch_id"],
            "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "scope_ref": _project_relative(scope_path),
            "batch_files": source["batch_files"],
            "code_manifest": code_manifest,
            "rules_manifest": rules_manifest,
            "config": {"file_sha256": config_capture["file_sha256"], "config_ref": CONFIG_REF},
            "input": {"file_sha256": input_capture["file_sha256"],
                      "byte_size": input_capture["byte_size"], "input_ref": INPUT_REF},
            "contract": contract,
            "run_binding": binding,
            "run_binding_sha256": fingerprint(binding),
            "note": REGISTRY_NOTE,
            "initial_judgment_history": copy.deepcopy(initial_judgment_history),
        }
        registry = _validate_registry(registry)
        registry_buffer = _payload_bytes(registry)
        readback = {"readback_version": READBACK_VERSION,
                    "registry_sha256": fingerprint(registry),
                    "registry_file_sha256": _sha_bytes(registry_buffer),
                    "registry_byte_size": len(registry_buffer),
                    "run_binding_sha256": registry["run_binding_sha256"]}
        _validate_readback(readback, registry, registry_buffer)
        readback_buffer = _payload_bytes(readback)
        stage = "create_leaf"
        try:
            leaf.mkdir()
        except FileExistsError as exc:
            raise RuntimeGate1Blocked(_safe_relative(leaf), "目标已存在，拒绝复用") from exc
        except OSError as exc:
            raise RuntimeGate1Error("create_leaf", f"无法创建叶目录：{leaf}：{exc}") from exc
        created = True
        stage = "write.registry"
        _write_exclusive(leaf / REGISTRY_FILE, registry_buffer, "write.registry")
        stage = "write.readback"
        _write_exclusive(leaf / READBACK_FILE, readback_buffer, "write.readback")
        stage = "readback"
        registry_after = _capture_file(leaf / REGISTRY_FILE, "readback.registry")
        readback_after = _capture_file(leaf / READBACK_FILE, "readback.readback")
        if registry_after["bytes"] != registry_buffer:
            _block(_safe_relative(leaf / REGISTRY_FILE), "读回字节与本次 writer 不一致")
        if readback_after["bytes"] != readback_buffer:
            _block(_safe_relative(leaf / READBACK_FILE), "读回字节与本次 writer 不一致")
        stage = "final_confirm"
        for name in BATCH_FILES:
            _recheck_capture(captures[name], f"batch.{name}")
        for relative, capture in sorted(captures.get("project", {}).items()):
            _recheck_capture(capture, relative)
        _recheck_capture(self_capture, "self")
        _recheck_capture(registry_after, REGISTRY_FILE)
        _recheck_capture(readback_after, READBACK_FILE)
        _require_fixed_members(batch_path, TOP_LEVEL_MEMBERS, "batch_dir(顶层)")
        for sub, leaves in BATCH_SUBDIR_FILES.items():
            _require_fixed_members(batch_path / sub, leaves, f"batch/{sub}")
        _require_fixed_members(leaf, [REGISTRY_FILE, READBACK_FILE], "runtime_dir(叶)")
        _reject_reparse_chain(leaf / REGISTRY_FILE, REGISTRY_FILE)
        _reject_reparse_chain(leaf / READBACK_FILE, READBACK_FILE)
        if scope_path.exists():
            _block("scope_dir", "末端确认时 scope 计划路径被创建")
        _confirm_history_namespace_038(history_namespace)
        return {"registry": copy.deepcopy(registry),
                "registry_sha256": fingerprint(registry),
                "registry_file_sha256": _sha_bytes(registry_buffer)}
    except (RuntimeGate1Blocked, RuntimeGate1Error) as exc:
        if created:
            field = getattr(exc, "field", None)
            reason = getattr(exc, "reason", str(exc))
            _write_failure(leaf, stage, field, reason, _cause_chain(exc))
        raise
    except OSError as exc:
        if created:
            _write_failure(leaf, stage, None, f"I/O 失败：{exc}", _cause_chain(exc))
        raise RuntimeGate1Error(stage, f"I/O 失败：{exc}") from exc


def prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id) -> dict:
    """只读构造 Gate1 候审请求（PREPARED 不是批准）。

    成功外层恰两键：`request` / `request_sha256`；调用方先取 `result["request"]`。
    不接受 decision 或任何人类字段、不生成 submission、不赋予动作许可。
    """
    _require_nonempty_str(request_id, "request_id")
    captures: dict = {}
    batch_path = _check_batch_dir(batch_dir, captures)
    leaf = _read_registry_leaf(runtime_dir)
    registry, _, leaf_captures = _load_stored_registry(leaf)
    self_capture = _capture_file(MODULE_PATH, "read.self")
    static_captures: dict = {}
    _require_current_static_identity(registry, self_capture, static_captures)

    request = _materialize_gate1_request(batch_path, registry, captures, self_capture,
                                         static_captures, request_id, leaf_captures["registry"])
    return _finish_prepare(request, captures, self_capture, static_captures, leaf,
                           leaf_captures, batch_path, registry,
                           enforce_scope_absent=True)


def _materialize_gate1_request(batch_path, registry, captures, self_capture,
                              static_captures, request_id, registry_capture) -> dict:
    """构造当前六键请求（材料/预期/证据/边界）；调用方负责末端有界确认与 scope 分支。

    这是 prepare 与 verify 私有分支**共享**的材料构造：不复制实现、不放宽既有 scope 前提。
    """
    source = _source_check(batch_path, request_id, captures)
    if source["batch_id"] != registry["batch_id"]:
        _block("batch_id", f"当前批次 {source['batch_id']!r} 与登记 "
                           f"{registry['batch_id']!r} 不一致")
    if source["batch_files"] != registry["batch_files"]:
        _block("batch_files", "当前批次 8 项来源文件与登记不一致（字节或名单变化）")
    code_manifest = _build_code_manifest(captures, self_capture)
    rules_manifest = _build_rules_manifest(captures)
    config_capture = _require_project_file(CONFIG_REF, captures)
    input_capture = captures["source/input.xlsx"]
    if canonical_json_bytes(code_manifest) != canonical_json_bytes(registry["code_manifest"]):
        _block("code_manifest", "本次实读代码清单与登记不一致，拒绝更新旧登记迎合新值")
    if canonical_json_bytes(rules_manifest) != canonical_json_bytes(registry["rules_manifest"]):
        _block("rules_manifest", "本次实读规则清单与登记不一致")
    binding = _build_run_binding(code_manifest, rules_manifest, config_capture,
                                 input_capture, self_capture)
    if canonical_json_bytes(binding) != canonical_json_bytes(registry["run_binding"]):
        _block("run_binding", "当前代码/规则/配置/输入与登记六项不一致")
    contract = _build_contract(captures)
    if canonical_json_bytes(contract) != canonical_json_bytes(registry["contract"]):
        _block("contract", "当前契约与登记不一致")

    prepare_files = list(source["project_files"] + source["batch_files"])
    prepare_files.append({"relative": "project/" + SCRIPT_RELATIVE,
                          "file_sha256": self_capture["file_sha256"],
                          "byte_size": self_capture["byte_size"]})
    for relative in (*INITIAL_COMPONENT_SHA256, *RECORDING_COMPONENT_SHA256):
        capture = _require_project_file(relative, captures)
        prepare_files.append({"relative": "project/" + relative,
                              "file_sha256": capture["file_sha256"], "byte_size": capture["byte_size"]})
    prepare_files.append({"relative": "runtime/runtime_registry.json",
                          "file_sha256": registry_capture["file_sha256"], "byte_size": registry_capture["byte_size"]})
    prepare_files.sort(key=lambda item: item["relative"].encode("utf-8"))
    if len(prepare_files) != 40 or len({item["relative"] for item in prepare_files}) != 40:
        _block("materials.files", "材料名单必须恰 40 项且 relative 唯一")
    for item in prepare_files:
        _require_hash(item["file_sha256"], f"materials.files[{item['relative']}].file_sha256")
        if not _is_strict_int(item["byte_size"]) or item["byte_size"] < 0:
            _block(f"materials.files[{item['relative']}].byte_size", "必须是非负严格整数")

    materials = {"gate": "GATE1", "batch_id": registry["batch_id"],
                 "run_binding": copy.deepcopy(binding),
                 "contract_binding": copy.deepcopy(contract),
                 "files": [copy.deepcopy(item) for item in prepare_files],
                 "quality": copy.deepcopy(source["quality"])}
    materials["materials_fingerprint"] = fingerprint(materials)
    _require_closed_keys(materials, MATERIALS_KEYS, "materials")

    expectations = {
        "expected_batch_id": registry["batch_id"],
        "expected_gate": "GATE1",
        "expected_request_id": request_id,
        "expected_materials_fingerprint": materials["materials_fingerprint"],
        "expected_files": {item["relative"]: item["file_sha256"] for item in prepare_files},
        "expected_contract": {"contract_version": contract["contract_version"],
                             "contract_file_sha256": contract["contract_file_sha256"]},
        "expected_run_binding": copy.deepcopy(binding),
        "expected_prior_gate1": None,
    }
    _require_closed_keys(expectations, EXPECTATIONS_KEYS, "expectations")

    source_evidence = source["evidence"]
    request = {
        "request_version": REQUEST_VERSION,
        "status": REQUEST_STATUS,
        "materials": materials,
        "expectations": expectations,
        "evidence": {"source_manifest_version":
                         _require_nonempty_str(source_evidence["source_manifest_version"],
                                               "evidence.source_manifest_version"),
                     "source_batch_status":
                         _require_nonempty_str(source_evidence["source_batch_status"],
                                               "evidence.source_batch_status"),
                     "source_receive_exit_code": source_evidence["source_receive_exit_code"],
                     "source_description":
                         _require_nonempty_str(source_evidence["source_description"],
                                               "evidence.source_description"),
                     "source_scope": copy.deepcopy(
                         _require_object(source_evidence["source_scope"],
                                         "evidence.source_scope")),
                     "code_manifest": copy.deepcopy(code_manifest),
                     "rules_manifest": copy.deepcopy(rules_manifest)},
        "boundaries": {key: False for key in BOUNDARY_KEYS},
    }
    if not _is_strict_int(request["evidence"]["source_receive_exit_code"]) \
            or request["evidence"]["source_receive_exit_code"] < 0:
        _block("evidence.source_receive_exit_code", "必须是非负严格整数")
    _require_closed_keys(request, REQUEST_KEYS, "request")
    _require_closed_keys(request["evidence"], EVIDENCE_KEYS, "evidence")
    return request


def _finish_prepare(request, captures, self_capture, static_captures, leaf,
                    leaf_captures, batch_path, registry, *, enforce_scope_absent: bool,
                    extra_captures=None) -> dict:
    """prepare / verify 共用的末端确认：全部来源、登记两文件、自身与输出字节、固定集合。

    ``enforce_scope_absent=False`` 只由 verify 的**私有分支**使用（该分支已独立核验事件
    恰为登记 scope 的唯一合法事件），公开三 API 仍一律要求计划 scope 尚不存在。
    """
    # 末端确认：本次消费的全部来源、两份输出、自身字节、目录集合与 scope 状态
    for name in BATCH_FILES:
        _recheck_capture(captures[name], f"batch.{name}")
    for relative, capture in sorted(captures.get("project", {}).items()):
        _recheck_capture(capture, relative)
    _recheck_capture(self_capture, "self")
    _recheck_capture(leaf_captures["registry"], REGISTRY_FILE)
    _recheck_capture(leaf_captures["readback"], READBACK_FILE)
    for relative, capture in sorted(static_captures.get("project", {}).items()):
        _recheck_capture(capture, relative)
    _recheck_capture(static_captures["frozen_prepare"], "scripts/prepare_demo_human_gate1.py")
    _require_fixed_members(batch_path, TOP_LEVEL_MEMBERS, "batch_dir(顶层)")
    for sub, leaves in BATCH_SUBDIR_FILES.items():
        _require_fixed_members(batch_path / sub, leaves, f"batch/{sub}")
    _require_fixed_members(leaf, [REGISTRY_FILE, READBACK_FILE], "runtime_dir(叶)")
    for capture, field in (extra_captures or ()):
        _recheck_capture(capture, field)
    scope_path = PROJECT_ROOT / registry["scope_ref"]
    if enforce_scope_absent and scope_path.exists():
        _block("registry.scope_ref", "末端确认时 scope 计划路径被创建")
    if not enforce_scope_absent:
        _reject_reparse_chain(scope_path, "registry.scope_ref")
    _confirm_history_namespace_038(leaf_captures["history_namespace"])
    return {"request": copy.deepcopy(request), "request_sha256": fingerprint(request)}


# --------------------------------------------------------------------------- TASK-027

RUNTIME_VERSION_027 = "TASK-027-runtime-gate1-1.0"
CONTEXT_VERSION = "TASK-027-runtime-gate1-context-1.0"
RECEIPT_VERSION = "TASK-027-runtime-gate1-receipt-1.0"
VERIFICATION_VERSION = "TASK-025-gate1-effective-approval-1.0"
FAILURE_VERSION_027 = "TASK-027-runtime-gate1-failure-1.0"
LOCK_VERSION = "TASK-027-runtime-gate1-lock-1.0"

LOCK_FILE = "lock.json"
SNAPSHOT_DIR = "snapshots"
CONTEXT_FILE = "context.json"
RECEIPT_FILE = "receipt.json"
DECISION_RESULT_FILE = "decision_result.json"
STORE_MANIFEST_FILE = "manifest.json"
SNAPSHOT_FILES = ("decision_result.json", "expectations.json", "materials.json",
                  "prior_history.json", "submission.json", "manifest.json")
EVENT_FILES = (CONTEXT_FILE, RECEIPT_FILE, SNAPSHOT_DIR)

CONTEXT_KEYS = ("context_version", "source_batch_relative", "runtime_relative",
                "scope_relative", "event_relative", "registry_file_sha256", "request",
                "prior_history", "store_result", "boundaries")
RECEIPT_KEYS = ("receipt_version", "batch_id", "event_relative", "scope_relative",
                "context_file_sha256", "snapshots_manifest_file_sha256",
                "record_fingerprint", "registry_file_sha256", "boundaries")
DECISION_BOUNDARY_KEYS = ("execution_allowed", "workflow_connected", "ai_enabled",
                          "identity_authenticated", "source_authenticity_proven")
# 冻结 P1 记录正文的 boundaries（六键，全部严格 false）
RECORD_BOUNDARY_KEYS_027 = ("persisted", "approved_for_execution",
                            "human_initial_judgment_saved", "ai_enabled",
                            "identity_authentication", "source_authenticity_proven")
VERIFY_KEYS = ("verification_version", "batch_id", "event_relative", "record_fingerprint",
               "record_file_sha256", "run_binding_sha256", "materials_fingerprint",
               "decision", "actor_kind", "effective", "reasons")
PRIOR_HISTORY_KEYS_027 = ("declared_complete", "declared_scope", "records")
SUBMISSION_KEYS_027 = ("submission_version", "event_id", "batch_id", "gate",
                       "request_binding", "decision", "decision_source", "actor",
                       "decided_at_raw", "reason", "prior_decision_binding")
REQUEST_BINDING_KEYS_027 = ("request_id", "materials_binding")
ACTOR_KEYS_027 = ("actor_kind", "actor_id", "declaration_note")
RECORD_KEYS_027 = ("record_version", "record_status", "gate", "batch_id", "event_id",
                   "decision", "decision_source", "reason", "decided_at_raw",
                   "decided_at_source", "actor", "binding", "prior_gate1",
                   "quality_summary", "execution_allowed", "boundaries", "note")
RECORD_BINDING_KEYS_027 = ("request_id", "materials_fingerprint", "materials_files",
                           "contract_binding", "run_binding")
STORE_RESULT_KEYS = ("status", "scope", "identity", "record_fingerprint",
                     "manifest_file_sha256", "execution_allowed", "workflow_connected",
                     "ai_enabled")
STORE_IDENTITY_KEYS = ("batch_id", "gate", "event_id")
STORE_STATUS_STORED = "HUMAN_GATE_DECISION_SNAPSHOTS_STORED"
STORE_STATUS_VERIFIED = "HUMAN_GATE_DECISION_SNAPSHOTS_VERIFIED"
STORE_RESULT_SCOPE = "STORED_SNAPSHOTS_ONLY"
ACTOR_KIND_HUMAN = "HUMAN_DECLARED"
DECISION_VALUES = ("APPROVE", "HOLD", "REJECT")
QUALITY_STATUSES = ("OK", "BLOCKED", "FAILED")
REASON_DECISION_NOT_APPROVE = "DECISION_NOT_APPROVE"
REASON_QUALITY_NOT_OK = "QUALITY_NOT_OK"
REASON_CURRENT_QUALITY_NOT_OK = "CURRENT_MATERIALS_QUALITY_NOT_OK"

MANIFEST_KEYS_027 = ("manifest_version", "store_status", "scope", "identity",
                     "component_bindings", "fingerprints", "payloads", "boundaries")
PAYLOAD_ENTRY_KEYS_027 = ("relative", "byte_size", "file_sha256")
FINGERPRINT_KEYS_027 = ("submission_fingerprint", "materials_snapshot_fingerprint",
                        "materials_body_fingerprint", "expectations_fingerprint",
                        "prior_history_fingerprint", "record_fingerprint")
PAYLOAD_FILES_027 = ("decision_result.json", "expectations.json", "materials.json",
                     "prior_history.json", "submission.json")

FROZEN_STORE_RELATIVE = "scripts/store_demo_human_gate_decision.py"
FROZEN_STORE_SHA256 = "594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7"


def _load_frozen_store():
    """加载冻结 store；加载前以**独立预期 SHA** 实读核验（复用既有读取口径）。"""
    path = PROJECT_ROOT / FROZEN_STORE_RELATIVE
    capture = _capture_file(path, "read.frozen_store")
    if capture["file_sha256"] != FROZEN_STORE_SHA256:
        _block(FROZEN_STORE_RELATIVE,
               f"冻结 store 字节与独立预期不一致：{capture['file_sha256']}")
    name = "frozen_gate_decision_store_runtime"
    module = sys.modules.get(name)
    if module is not None and getattr(module, "__frozen_sha256__", None) == FROZEN_STORE_SHA256:
        return module
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeGate1Error("store_load", f"无法建立 spec：{path}")
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
    except (RuntimeGate1Blocked, RuntimeGate1Error):
        raise
    except Exception as exc:  # noqa: BLE001 - 加载失败按运行错误分类
        raise RuntimeGate1Error("store_load", f"{type(exc).__name__}: {exc}") from exc
    loaded.__frozen_sha256__ = FROZEN_STORE_SHA256
    sys.modules[name] = loaded
    return loaded


def _call_frozen_store_save(event_dir, submission, materials, expectations,
                            prior_history) -> dict:
    store = _load_frozen_store()
    try:
        result = store.save_human_gate_decision_snapshots(
            event_dir, submission, materials, expectations, prior_history=prior_history)
    except Exception as exc:  # noqa: BLE001 - 保留冻结 store 的定位/原因
        field = getattr(exc, "field", None)
        reason = getattr(exc, "reason", None)
        if isinstance(field, str) and isinstance(reason, str):
            raise RuntimeGate1Blocked(f"store.{field}", reason) from exc
        stage = getattr(exc, "stage", None)
        if isinstance(stage, str):
            raise RuntimeGate1Error(f"store.{stage}",
                                    str(getattr(exc, "reason", exc))) from exc
        raise RuntimeGate1Error("store_call", f"{type(exc).__name__}: {exc}") from exc
    return _require_object(result, "store.result")


def _call_frozen_store_verify(snapshot_dir) -> dict:
    store = _load_frozen_store()
    try:
        result = store.verify_human_gate_decision_snapshots(snapshot_dir)
    except Exception as exc:  # noqa: BLE001
        field = getattr(exc, "field", None)
        reason = getattr(exc, "reason", None)
        if isinstance(field, str) and isinstance(reason, str):
            raise RuntimeGate1Blocked(f"store.{field}", reason) from exc
        stage = getattr(exc, "stage", None)
        if isinstance(stage, str):
            raise RuntimeGate1Error(f"store.{stage}",
                                    str(getattr(exc, "reason", exc))) from exc
        raise RuntimeGate1Error("store_verify", f"{type(exc).__name__}: {exc}") from exc
    return _require_object(result, "store.verify_result")


def _validate_store_result(result, *, expected_status: str) -> dict:
    value = _require_closed_keys(result, STORE_RESULT_KEYS, "store_result")
    if value["status"] != expected_status:
        _block("store_result.status", f"必须是 {expected_status}")
    if value["scope"] != STORE_RESULT_SCOPE:
        _block("store_result.scope", f"必须是 {STORE_RESULT_SCOPE}")
    identity = _require_closed_keys(value["identity"], STORE_IDENTITY_KEYS,
                                   "store_result.identity")
    _require_nonempty_str(identity["batch_id"], "store_result.identity.batch_id")
    _require_nonempty_str(identity["gate"], "store_result.identity.gate")
    _require_nonempty_str(identity["event_id"], "store_result.identity.event_id")
    _require_hash(value["record_fingerprint"], "store_result.record_fingerprint")
    _require_hash(value["manifest_file_sha256"], "store_result.manifest_file_sha256")
    for key in ("execution_allowed", "workflow_connected", "ai_enabled"):
        _require_bool_false(value[key], f"store_result.{key}")
    return value


def _lock_path_for(leaf: Path) -> Path:
    """技术锁与运行登记叶**同级**（不放进固定两文件登记叶）。"""
    return leaf.parent / (leaf.name + ".lock")


def _path_identity(path: Path, stage: str) -> dict:
    """取得时/释放前可核对的目录或文件身份（标准库 stat；不引入新依赖）。"""
    try:
        stat = path.lstat()
    except OSError as exc:
        raise RuntimeGate1Error(stage, f"无法读取路径身份：{path}：{exc}") from exc
    return {"st_dev": getattr(stat, "st_dev", None),
            "st_ino": getattr(stat, "st_ino", None),
            "st_ctime_ns": getattr(stat, "st_ctime_ns", None)}


def _acquire_lock(leaf: Path, event_relative: str, *, lock_path=None) -> dict:
    lock = _lock_path_for(leaf) if lock_path is None else lock_path
    _reject_reparse_chain(lock, "lock")
    if lock.exists():
        _block("lock", f"技术锁已存在，拒绝并发保存：{_safe_relative(lock)}")
    payload = {"lock_version": LOCK_VERSION,
               "runtime_relative": _project_relative(leaf),
               "event_relative": event_relative,
               "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        os.mkdir(lock)
    except FileExistsError as exc:
        raise RuntimeGate1Blocked("lock", "技术锁已存在（独占建立被拒绝）") from exc
    except OSError as exc:
        raise RuntimeGate1Error("lock", f"无法独占建立技术锁：{lock}：{exc}") from exc
    dir_identity = _path_identity(lock, "lock")
    lock_buffer = _payload_bytes(payload)
    try:
        _write_exclusive(lock / LOCK_FILE, lock_buffer, "write.lock")
    except Exception as exc:  # noqa: BLE001 - 取得锁写失败：保留锁与半写现场，不删除未知身份/内容
        if isinstance(exc, (RuntimeGate1Blocked, RuntimeGate1Error)):
            raise
        raise RuntimeGate1Error(
            "lock", f"取得技术锁写失败（保留现场）：{type(exc).__name__}: {exc}") from exc
    return {"path": lock, "buffer": lock_buffer, "payload": payload,
            "dir_identity": _path_identity(lock, "lock"),
            "file_identity": _path_identity(lock / LOCK_FILE, "lock")}


def _release_own_lock(lock: dict) -> str:
    """只释放本次自建且身份/内容未变化的锁；返回错误文本（None 表示成功）。"""
    path = lock["path"]
    try:
        if not path.is_dir():
            return f"技术锁目录不存在：{_safe_relative(path)}"
        _reject_reparse_chain(path, "lock")
        listing = sorted(item.name for item in path.iterdir())
        if listing != [LOCK_FILE]:
            return f"技术锁内容集合异常（保留现场）：{listing}"
        if _path_identity(path, "release.lock") != lock["dir_identity"]:
            return "技术锁目录身份已变化（替代锁，保留现场，不释放）"
        if _path_identity(path / LOCK_FILE, "release.lock") != lock["file_identity"]:
            return "技术锁文件身份已变化（替代锁，保留现场，不释放）"
        data = (path / LOCK_FILE).read_bytes()
        if data != lock["buffer"]:
            return "技术锁内容已变化（保留现场，不释放）"
        (path / LOCK_FILE).unlink()
        path.rmdir()
        return None
    except (OSError, RuntimeGate1Error) as exc:
        return f"释放技术锁失败：{type(exc).__name__}: {exc}"


def _note_secondary(primary, message: str, *, stage="release_lock") -> None:
    """把技术次错误追加进主错误（args/reason/属性），不覆盖原 field 与 reason 主体。"""
    if primary is None:
        return
    note = f"{stage}: {message}"
    try:
        args = list(primary.args)
        if args:
            args[0] = f"{args[0]}；{note}"
        else:
            args.append(note)
        primary.args = tuple(args)
        reason = getattr(primary, "reason", None)
        if isinstance(reason, str):
            primary.reason = f"{reason}；{note}"
        secondary = getattr(primary, "secondary_errors", None)
        if isinstance(secondary, list):
            secondary.append(note)
        else:
            primary.secondary_errors = [note]
    except Exception:  # noqa: BLE001 - 记录次错误不得影响主错误传播
        pass


def _check_submission_bindings(submission: dict, request: dict, request_id: str) -> None:
    """submission 的批次/请求/材料/前序绑定必须与本次独立预期一致；错绑定不建事件。"""
    value = _require_closed_keys(submission, SUBMISSION_KEYS_027, "submission")
    _require_nonempty_str(value["submission_version"], "submission.submission_version")
    _require_nonempty_str(value["event_id"], "submission.event_id")
    if value["gate"] != "GATE1":
        _block("submission.gate", f"本层只受理 GATE1，实际 {value['gate']!r}")
    if value["batch_id"] != request["materials"]["batch_id"]:
        _block("submission.batch_id", "与当前登记批次不一致")
    binding = _require_closed_keys(value["request_binding"], REQUEST_BINDING_KEYS_027,
                                   "submission.request_binding")
    expected_request_id = request["expectations"]["expected_request_id"]
    if binding["request_id"] != expected_request_id or binding["request_id"] != request_id:
        _block("submission.request_binding.request_id", "与本次请求 ID 不一致")
    if binding["materials_binding"] != request["materials"]["materials_fingerprint"]:
        _block("submission.request_binding.materials_binding", "与当前材料指纹不一致")
    if value["prior_decision_binding"] is not None:
        _block("submission.prior_decision_binding", "GATE1 必须为 null")
    if value["decision"] not in DECISION_VALUES:
        _block("submission.decision", f"必须是 {DECISION_VALUES} 之一")
    actor = _require_closed_keys(value["actor"], ACTOR_KEYS_027, "submission.actor")
    if actor["actor_kind"] != ACTOR_KIND_HUMAN:
        _block("submission.actor.actor_kind", f"唯一允许 {ACTOR_KIND_HUMAN}")
    _require_nonempty_str(actor["actor_id"], "submission.actor.actor_id")
    for key in ("decision_source", "decided_at_raw", "reason"):
        if not isinstance(value[key], str) or value[key].strip() == "":
            _block(f"submission.{key}", "人类字符串必须原文非空（本层不代填）")


def _bind_store_snapshots(snapshot_captures: dict, store_result: dict, submission: dict,
                          request: dict, prior_history: dict, *, gate="GATE1") -> tuple:
    """把本次真实 store 返回与实读 manifest 绑定，再用其封闭清单约束五 payload。

    顺序：manifest 字节 SHA ↔ 本次 store 返回 → manifest 封闭形状/指纹关系 → 五 payload
    的实际长度/SHA（由 manifest 清单约束）→ 五对象与本次输入/请求 canonical 闭合。
    """
    manifest_capture = snapshot_captures[STORE_MANIFEST_FILE]
    if manifest_capture["file_sha256"] != store_result["manifest_file_sha256"]:
        _block("store_result.manifest_file_sha256", "与本次真实 store 返回不一致")
    manifest = _require_closed_keys(
        _parse_json_object(manifest_capture["bytes"], STORE_MANIFEST_FILE),
        MANIFEST_KEYS_027, "snapshots.manifest")
    _require_nonempty_str(manifest["manifest_version"],
                          "snapshots.manifest.manifest_version")
    if manifest["store_status"] != STORE_STATUS_STORED:
        _block("snapshots.manifest.store_status", f"必须是 {STORE_STATUS_STORED}")
    if manifest["scope"] != STORE_RESULT_SCOPE:
        _block("snapshots.manifest.scope", f"必须是 {STORE_RESULT_SCOPE}")
    identity = _require_closed_keys(manifest["identity"], STORE_IDENTITY_KEYS,
                                    "snapshots.manifest.identity")
    if canonical_json_bytes(identity) != canonical_json_bytes(store_result["identity"]):
        _block("snapshots.manifest.identity", "与本次 store 返回身份不一致")
    boundaries = _require_closed_keys(manifest["boundaries"], DECISION_BOUNDARY_KEYS,
                                      "snapshots.manifest.boundaries")
    for key, value in boundaries.items():
        _require_bool_false(value, f"snapshots.manifest.boundaries.{key}")
    fingerprints = _require_closed_keys(manifest["fingerprints"], FINGERPRINT_KEYS_027,
                                        "snapshots.manifest.fingerprints")
    for key, value in fingerprints.items():
        _require_hash(value, f"snapshots.manifest.fingerprints.{key}")
    if fingerprints["record_fingerprint"] != store_result["record_fingerprint"]:
        _block("snapshots.manifest.fingerprints.record_fingerprint",
               "与本次 store 返回指纹不一致")
    materials_body = {key: value for key, value in request["materials"].items()
                      if key != "materials_fingerprint"}
    expectations_map = (("submission_fingerprint", submission),
                        ("expectations_fingerprint", request["expectations"]),
                        ("prior_history_fingerprint", prior_history),
                        ("materials_snapshot_fingerprint", request["materials"]),
                        ("materials_body_fingerprint", materials_body))
    for key, expected in expectations_map:
        if fingerprints[key] != fingerprint(expected):
            _block(f"snapshots.manifest.fingerprints.{key}", "与本次输入/请求不一致")

    entries = _require_list(manifest["payloads"], "snapshots.manifest.payloads")
    if len(entries) != len(PAYLOAD_FILES_027):
        _block("snapshots.manifest.payloads",
               f"必须恰 {len(PAYLOAD_FILES_027)} 项，实际 {len(entries)}")
    seen = set()
    for index, raw in enumerate(entries):
        field = f"snapshots.manifest.payloads[{index}]"
        item = _require_closed_keys(raw, PAYLOAD_ENTRY_KEYS_027, field)
        relative = _require_nonempty_str(item["relative"], f"{field}.relative")
        _require_hash(item["file_sha256"], f"{field}.file_sha256")
        if not _is_strict_int(item["byte_size"]) or item["byte_size"] < 0:
            _block(f"{field}.byte_size", "必须是非负严格整数")
        capture = snapshot_captures.get(relative)
        if capture is None:
            _block(field, f"清单含未知 payload {relative!r}")
        if seen and relative in seen:
            _block(field, f"payload 重复 {relative!r}")
        seen.add(relative)
        if capture["file_sha256"] != item["file_sha256"] \
                or capture["byte_size"] != item["byte_size"]:
            _block(f"snapshots.{relative}", "实读字节与该次 store manifest 声明不一致")
    if seen != set(PAYLOAD_FILES_027):
        _block("snapshots.manifest.payloads", f"必须恰为五 payload，实际 {sorted(seen)}")

    for name, expected in (("submission.json", submission),
                           ("materials.json", request["materials"]),
                           ("expectations.json", request["expectations"]),
                           ("prior_history.json", prior_history)):
        parsed = _parse_json_object(snapshot_captures[name]["bytes"], name)
        if canonical_json_bytes(parsed) != canonical_json_bytes(expected):
            _block(f"snapshots.{name}", "与本次输入/请求不一致")
    decision_result = _require_closed_keys(
        _parse_json_object(snapshot_captures[DECISION_RESULT_FILE]["bytes"],
                           DECISION_RESULT_FILE),
        ("record", "record_fingerprint"), DECISION_RESULT_FILE)
    record = _require_closed_keys(decision_result["record"], RECORD_KEYS_027, "record")
    record_fingerprint = _require_hash(decision_result["record_fingerprint"],
                                      "record_fingerprint")
    if fingerprint(record) != record_fingerprint:
        _block("record_fingerprint", "与 record 正文规范指纹不一致")
    if record_fingerprint != store_result["record_fingerprint"] \
            or record_fingerprint != fingerprints["record_fingerprint"]:
        _block("record_fingerprint", "与本次 store 返回/manifest 指纹不一致")
    if record["gate"] != gate or store_result["identity"]["gate"] != gate:
        _block("record.gate", f"必须为 {gate}")
    if record["batch_id"] != request["materials"]["batch_id"] \
            or store_result["identity"]["batch_id"] != request["materials"]["batch_id"]:
        _block("batch_id", "记录/store 身份与本次登记批次不一致")
    if record["event_id"] != submission["event_id"] \
            or store_result["identity"]["event_id"] != submission["event_id"]:
        _block("event_id", "记录/store 事件 ID 与 submission 不一致")
    if gate == "GATE1" and record["prior_gate1"] is not None:
        _block("record.prior_gate1", "GATE1 记录不得带前序正文")
    if gate == "GATE2":
        prior = prior_history["records"][0]
        expected_prior = {"record_fingerprint": prior["record_fingerprint"],
                          "event_id": prior["record"]["event_id"],
                          "batch_id": prior["record"]["batch_id"],
                          "gate": "GATE1", "decision": "APPROVE",
                          "actor_kind": ACTOR_KIND_HUMAN}
        _require_equivalent_030(record["prior_gate1"], expected_prior, "record.prior_gate1")
    binding = _require_closed_keys(record["binding"], RECORD_BINDING_KEYS_027,
                                   "record.binding")
    if binding["request_id"] != request["expectations"]["expected_request_id"]:
        _block("record.binding.request_id", "与本次请求 ID 不一致")
    if binding["materials_fingerprint"] != request["materials"]["materials_fingerprint"]:
        _block("record.binding.materials_fingerprint", "与本次材料指纹不一致")
    return record, record_fingerprint, manifest_capture


def _write_event_failure(event_path: Path, stage: str, field, reason: str,
                         cause_chain) -> None:
    payload = {"failure_version": FAILURE_VERSION_027, "stage": stage, "field": field,
               "reason": reason, "cause_chain": list(cause_chain)}
    try:
        _write_exclusive(event_path / FAILURE_FILE, _payload_bytes(payload),
                         "write.failure")
    except Exception as nested:  # noqa: BLE001 - 诊断自身失败保留两层错误
        raise RuntimeGate1Error(
            "write.failure",
            f"诊断写出失败：{type(nested).__name__}: {nested}；原始错误：{reason}",
        ) from nested


def save_runtime_gate1_decision(batch_dir, runtime_dir, request_id, submission,
                                event_dir, *, scope_dir) -> dict:
    """保存**单个** Gate1 事件（一次写定；不追加/不修改/不撤销/不跨 scope）。

    成功外层恰三键：`record` / `record_fingerprint` / `event_relative`；
    `record` 是真实冻结 P1 返回的 17 键正文。本 API **不赋予执行许可**。
    """
    _require_nonempty_str(request_id, "request_id")
    submission_value = _require_object(submission, "submission")
    if not isinstance(event_dir, (str, os.PathLike)):
        _block("event_dir", f"必须是路径，实际 {type(event_dir).__name__}")

    stage = "read_inputs"
    batch_captures: dict = {}
    batch_path = _check_batch_dir(batch_dir, batch_captures)
    leaf = _read_registry_leaf(runtime_dir)
    registry, _, leaf_captures = _load_stored_registry(leaf)
    self_capture = _capture_file(MODULE_PATH, "read.self")
    static_captures: dict = {}
    _require_current_static_identity(registry, self_capture, static_captures)

    scope_path = _check_scope_dir(scope_dir)
    scope_relative = _project_relative(scope_path)
    if registry["scope_ref"] != scope_relative:
        _block("scope_dir", f"与登记 scope_ref {registry['scope_ref']!r} 严格相符才可保存")
    raw_event = Path(event_dir)
    _reject_reparse_chain(raw_event, "event_dir")
    try:
        event_path = raw_event.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.event_dir", f"{raw_event}：{exc}") from exc
    _require_descendant(event_path, scope_path, "event_dir")
    if event_path.exists():
        _block("event_dir", f"事件路径必须从未存在：{_safe_relative(event_path)}")
    event_relative = _project_relative(event_path)
    if _lock_path_for(leaf).exists():
        _block("lock", f"技术锁已存在，拒绝保存：{_safe_relative(_lock_path_for(leaf))}")

    lock = _acquire_lock(leaf, event_relative)
    result = None
    primary = None
    pending = None
    try:
        stage = "prepare_request"
        prepared = prepare_runtime_gate1_request(batch_dir, leaf, request_id)
        request = prepared["request"]
        stage = "scope_recheck"
        if scope_path.exists():
            _block("scope_dir", "锁内确认时计划 scope 已存在（同批次已有事件）")
        prior_history = {"declared_complete": True, "declared_scope": scope_relative,
                         "records": []}
        stage = "bindings"
        _check_submission_bindings(submission_value, request, request_id)
        stage = "pre_store_recheck"
        for name in BATCH_FILES:
            _recheck_capture(batch_captures[name], f"batch.{name}")
        for relative, capture in sorted(static_captures.get("project", {}).items()):
            _recheck_capture(capture, relative)
        _recheck_capture(static_captures["frozen_prepare"],
                         "scripts/prepare_demo_human_gate1.py")
        _recheck_capture(self_capture, "self")
        _recheck_capture(leaf_captures["registry"], REGISTRY_FILE)
        _recheck_capture(leaf_captures["readback"], READBACK_FILE)
        _require_fixed_members(leaf, [REGISTRY_FILE, READBACK_FILE], "runtime_dir(叶)")
        if FAILURE_FILE in _iter_dir(leaf, "pre_store.leaf"):
            _block("runtime_dir(叶)", "登记叶已出现 failure 诊断，拒绝保存")
        stage = "store_save"
        store_result = _call_frozen_store_save(
            event_path / SNAPSHOT_DIR, submission_value,
            copy.deepcopy(request["materials"]), copy.deepcopy(request["expectations"]),
            prior_history)
        created_event = event_path.is_dir()
        store_result = _validate_store_result(store_result,
                                             expected_status=STORE_STATUS_STORED)
        stage = "bind_store_output"
        snapshot_captures = {}
        for name in SNAPSHOT_FILES:
            snapshot_captures[name] = _capture_file(event_path / SNAPSHOT_DIR / name,
                                                   f"read.snapshots.{name}")
        record, record_fingerprint, manifest_capture = _bind_store_snapshots(
            snapshot_captures, store_result, submission_value, request, prior_history)

        stage = "write_context"
        context = {
            "context_version": CONTEXT_VERSION,
            "source_batch_relative": _project_relative(batch_path),
            "runtime_relative": _project_relative(leaf),
            "scope_relative": scope_relative,
            "event_relative": event_relative,
            "registry_file_sha256": leaf_captures["registry"]["file_sha256"],
            "request": copy.deepcopy(request),
            "prior_history": copy.deepcopy(prior_history),
            "store_result": copy.deepcopy(store_result),
            "boundaries": {key: False for key in DECISION_BOUNDARY_KEYS},
        }
        _require_closed_keys(context, CONTEXT_KEYS, "context")
        context_buffer = _payload_bytes(context)
        _write_exclusive(event_path / CONTEXT_FILE, context_buffer, "write.context")
        context_after = _capture_file(event_path / CONTEXT_FILE, "readback.context")
        if context_after["bytes"] != context_buffer:
            _block(CONTEXT_FILE, "读回字节与本次 writer 缓冲不一致")

        stage = "write_receipt"
        if manifest_capture["file_sha256"] != store_result["manifest_file_sha256"]:
            _block("store_result.manifest_file_sha256", "与快照 manifest 实际字节不一致")
        receipt = {
            "receipt_version": RECEIPT_VERSION,
            "batch_id": registry["batch_id"],
            "event_relative": event_relative,
            "scope_relative": scope_relative,
            "context_file_sha256": _sha_bytes(context_buffer),
            "snapshots_manifest_file_sha256": manifest_capture["file_sha256"],
            "record_fingerprint": record_fingerprint,
            "registry_file_sha256": leaf_captures["registry"]["file_sha256"],
            "boundaries": {key: False for key in DECISION_BOUNDARY_KEYS},
        }
        _require_closed_keys(receipt, RECEIPT_KEYS, "receipt")
        receipt_buffer = _payload_bytes(receipt)
        _write_exclusive(event_path / RECEIPT_FILE, receipt_buffer, "write.receipt")
        receipt_after = _capture_file(event_path / RECEIPT_FILE, "readback.receipt")
        if receipt_after["bytes"] != receipt_buffer:
            _block(RECEIPT_FILE, "读回字节与本次 writer 缓冲不一致")

        stage = "final_confirm"
        for name in BATCH_FILES:
            _recheck_capture(batch_captures[name], f"batch.{name}")
        for relative, capture in sorted(static_captures.get("project", {}).items()):
            _recheck_capture(capture, relative)
        _recheck_capture(static_captures["frozen_prepare"],
                         "scripts/prepare_demo_human_gate1.py")
        _recheck_capture(self_capture, "self")
        _recheck_capture(leaf_captures["registry"], REGISTRY_FILE)
        _recheck_capture(leaf_captures["readback"], READBACK_FILE)
        _recheck_capture(context_after, CONTEXT_FILE)
        _recheck_capture(receipt_after, RECEIPT_FILE)
        for name in SNAPSHOT_FILES:
            _recheck_capture(snapshot_captures[name], f"snapshots.{name}")
        _require_fixed_members(batch_path, TOP_LEVEL_MEMBERS, "batch_dir(顶层)")
        for sub, leaves in BATCH_SUBDIR_FILES.items():
            _require_fixed_members(batch_path / sub, leaves, f"batch/{sub}")
        _require_fixed_members(leaf, [REGISTRY_FILE, READBACK_FILE], "runtime_dir(叶)")
        if FAILURE_FILE in _iter_dir(leaf, "final.leaf"):
            _block("runtime_dir(叶)", "登记叶出现 failure 诊断，拒绝成功")
        _require_fixed_members(scope_path, [event_path.name], "scope")
        _require_fixed_members(event_path, list(EVENT_FILES), "event")
        _require_fixed_members(event_path / SNAPSHOT_DIR, list(SNAPSHOT_FILES), "snapshots")
        if FAILURE_FILE in _iter_dir(event_path, "final.event"):
            _block("event", "成功路径不得残留 failure 诊断")
        if _lock_path_for(leaf).exists() is not True:
            _block("lock", "末端确认时技术锁不应仍在（本次自建）")
        result = {"record": copy.deepcopy(record),
                  "record_fingerprint": record_fingerprint,
                  "event_relative": event_relative}
    except (RuntimeGate1Blocked, RuntimeGate1Error) as exc:
        primary = exc
        pending = {"stage": stage, "field": getattr(exc, "field", None),
                   "reason": getattr(exc, "reason", str(exc)), "chain": _cause_chain(exc)}
        raise
    except Exception as exc:  # noqa: BLE001 - 写后真实异常按实际现场判断并映射为 Error
        mapped = RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}")
        primary = mapped
        pending = {"stage": stage, "field": None,
                   "reason": f"{type(exc).__name__}: {exc}", "chain": _cause_chain(exc)}
        raise mapped from exc
    finally:
        release_error = _release_own_lock(lock)
        event_exists = event_path.is_dir()
        if pending is None:
            if release_error is not None:
                if event_exists:
                    _write_event_failure(event_path, "release_lock", "lock", release_error,
                                         [release_error])
                raise RuntimeGate1Error("release_lock", release_error)
        else:
            if release_error is not None:
                # 主错误与解锁次错误都对调用方可见；诊断在两者已知后一次独占写定
                pending["chain"] = list(pending["chain"]) + [f"release_lock: {release_error}"]
                _note_secondary(primary, release_error)
            if event_exists:
                _write_event_failure(event_path, pending["stage"], pending["field"],
                                     pending["reason"], pending["chain"])
    return result


def verify_gate1_effective_approval(batch_dir, runtime_dir, *, scope_dir,
                                    event_relative) -> dict:
    """只读核验该 Gate1 事件在**当前材料**下是否满足 Gate1 前提（恰十一键）。

    effective 只描述该记录在本次材料下是否满足 Gate1 前提；本 API 没有任何执行动作或
    执行许可，也不写任何文件（失败不写诊断）。
    """
    _require_nonempty_str(event_relative, "event_relative")
    if event_relative.startswith("/") or ":" in event_relative:
        _block("event_relative", "必须是项目相对路径")
    batch_captures: dict = {}
    batch_path = _check_batch_dir(batch_dir, batch_captures)
    leaf = _read_registry_leaf(runtime_dir)
    registry, _, leaf_captures = _load_stored_registry(leaf,
                                                      allow_existing_scope=True)
    self_capture = _capture_file(MODULE_PATH, "read.self")
    static_captures: dict = {}
    _require_current_static_identity(registry, self_capture, static_captures)

    if not isinstance(scope_dir, (str, os.PathLike)):
        _block("scope_dir", f"必须是路径，实际 {type(scope_dir).__name__}")
    raw_scope = Path(scope_dir)
    _reject_reparse_chain(raw_scope, "scope_dir")
    try:
        scope_path = raw_scope.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.scope_dir", f"{raw_scope}：{exc}") from exc
    scope_relative = _project_relative(scope_path)
    if registry["scope_ref"] != scope_relative:
        _block("scope_dir", "只接受恰等于登记 scope_ref 的已核验 scope")
    if not scope_path.is_dir():
        _block("scope_dir", "计划 scope 尚不存在（该批次没有已保存事件）")
    if _lock_path_for(leaf).exists():
        _block("lock", "技术锁存在，核验拒绝")

    raw_event = PROJECT_ROOT / event_relative
    _reject_reparse_chain(raw_event, "event_relative")
    try:
        event_path = raw_event.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.event_relative", f"{raw_event}：{exc}") from exc
    if event_path != raw_event:
        _block("event_relative", "解析后与显式项目相对路径不一致")
    _require_descendant(event_path, scope_path, "event_relative")
    if not event_path.is_dir():
        _block("event_relative", f"事件目录不存在：{event_relative}")

    _require_fixed_members(scope_path, [event_path.name], "scope")
    if FAILURE_FILE in _iter_dir(event_path, "read.event"):
        _block(FAILURE_FILE, "事件含 failure 诊断，核验拒绝")
    _require_fixed_members(event_path, list(EVENT_FILES), "event")
    _require_fixed_members(event_path / SNAPSHOT_DIR, list(SNAPSHOT_FILES), "snapshots")

    context_capture = _capture_file(event_path / CONTEXT_FILE, "read.context")
    receipt_capture = _capture_file(event_path / RECEIPT_FILE, "read.receipt")
    context = _require_closed_keys(
        _parse_json_object(context_capture["bytes"], CONTEXT_FILE), CONTEXT_KEYS, "context")
    receipt = _require_closed_keys(
        _parse_json_object(receipt_capture["bytes"], RECEIPT_FILE), RECEIPT_KEYS, "receipt")
    if context["context_version"] != CONTEXT_VERSION:
        _block("context.context_version", f"必须是 {CONTEXT_VERSION}")
    if receipt["receipt_version"] != RECEIPT_VERSION:
        _block("receipt.receipt_version", f"必须是 {RECEIPT_VERSION}")
    context_boundaries = _require_closed_keys(
        _require_object(context["boundaries"], "context.boundaries"),
        DECISION_BOUNDARY_KEYS, "context.boundaries")
    for key, value in context_boundaries.items():
        _require_bool_false(value, f"context.boundaries.{key}")
    receipt_boundaries = _require_closed_keys(
        _require_object(receipt["boundaries"], "receipt.boundaries"),
        DECISION_BOUNDARY_KEYS, "receipt.boundaries")
    for key, value in receipt_boundaries.items():
        _require_bool_false(value, f"receipt.boundaries.{key}")
    if context["scope_relative"] != scope_relative or             context["event_relative"] != event_relative:
        _block("context.event_relative", "与显式参数不一致")
    if context["source_batch_relative"] != _project_relative(batch_path):
        _block("context.source_batch_relative", "与显式批次路径不一致")
    if context["runtime_relative"] != _project_relative(leaf):
        _block("context.runtime_relative", "与显式运行登记叶不一致")
    if not isinstance(context["registry_file_sha256"], str) \
            or not HASH_PATTERN.match(context["registry_file_sha256"]):
        _block("context.registry_file_sha256", "必须是 64 位小写十六进制")
    if context["registry_file_sha256"] != leaf_captures["registry"]["file_sha256"]:
        _block("context.registry_file_sha256", "与本次实读登记文件不一致")
    if receipt["scope_relative"] != scope_relative or             receipt["event_relative"] != event_relative:
        _block("receipt.event_relative", "与显式参数不一致")
    if receipt["batch_id"] != registry["batch_id"]:
        _block("receipt.batch_id", "与登记批次不一致")
    if receipt["registry_file_sha256"] != leaf_captures["registry"]["file_sha256"]:
        _block("receipt.registry_file_sha256", "与本次实读登记文件不一致")
    if receipt["context_file_sha256"] != _sha_bytes(context_capture["bytes"]):
        _block("receipt.context_file_sha256", "与 context 实际字节不一致")
    _require_closed_keys(context["request"], REQUEST_KEYS, "context.request")
    _require_closed_keys(context["prior_history"], PRIOR_HISTORY_KEYS_027,
                         "context.prior_history")
    if context["prior_history"]["declared_complete"] is not True or             context["prior_history"]["declared_scope"] != scope_relative or             context["prior_history"]["records"] != []:
        _block("context.prior_history", "必须是显式三键空历史（完整/本 scope/空记录）")
    stored_store_result = _validate_store_result(context["store_result"],
                                                 expected_status=STORE_STATUS_STORED)

    snapshot_captures = {}
    for name in SNAPSHOT_FILES:
        snapshot_captures[name] = _capture_file(event_path / SNAPSHOT_DIR / name,
                                               f"read.snapshots.{name}")
    if receipt["snapshots_manifest_file_sha256"] !=             snapshot_captures[STORE_MANIFEST_FILE]["file_sha256"]:
        _block("receipt.snapshots_manifest_file_sha256", "与快照 manifest 实际字节不一致")
    store_verify = _validate_store_result(
        _call_frozen_store_verify(event_path / SNAPSHOT_DIR),
        expected_status=STORE_STATUS_VERIFIED)
    if store_verify["record_fingerprint"] != receipt["record_fingerprint"]:
        _block("store_verify.record_fingerprint", "与 receipt 不一致")
    if store_verify["identity"] != stored_store_result["identity"]:
        _block("store_verify.identity", "与保存时冻结 store 身份不一致")
    if store_verify["manifest_file_sha256"] != stored_store_result["manifest_file_sha256"]:
        _block("store_verify.manifest_file_sha256", "与保存时 manifest 字节不一致")
    stable_saved = {key: value for key, value in stored_store_result.items()
                    if key != "status"}
    stable_now = {key: value for key, value in store_verify.items() if key != "status"}
    if canonical_json_bytes(stable_saved) != canonical_json_bytes(stable_now):
        differing = sorted(key for key in set(stable_saved) | set(stable_now)
                           if canonical_json_bytes(stable_saved.get(key)) !=
                           canonical_json_bytes(stable_now.get(key)))
        _block("store_verify.stable_fields",
               f"保存时 store_result 与本次 verify 稳定字段不一致：{differing}")

    decision_result = _parse_json_object(snapshot_captures[DECISION_RESULT_FILE]["bytes"],
                                        DECISION_RESULT_FILE)
    record = _require_closed_keys(decision_result.get("record"), RECORD_KEYS_027, "record")
    record_fingerprint = _require_hash(decision_result.get("record_fingerprint"),
                                      "record_fingerprint")
    if fingerprint(record) != record_fingerprint:
        _block("record_fingerprint", "与 record 正文规范指纹不一致")
    if record_fingerprint != store_verify["record_fingerprint"]:
        _block("record_fingerprint", "与冻结 store 核验结果不一致")
    if record["batch_id"] != registry["batch_id"] or             store_verify["identity"]["batch_id"] != registry["batch_id"]:
        _block("batch_id", "记录/冻结 store 身份与登记批次不一致")
    if record["gate"] != "GATE1" or store_verify["identity"]["gate"] != "GATE1":
        _block("gate", "只核验 GATE1 记录")
    binding = _require_closed_keys(record["binding"], RECORD_BINDING_KEYS_027,
                                   "record.binding")
    if binding["run_binding"] != registry["run_binding"]:
        _block("record.binding.run_binding", "与登记六项绑定不一致")
    if canonical_json_bytes(binding["contract_binding"]) !=             canonical_json_bytes(registry["contract"]):
        _block("record.binding.contract_binding", "与登记契约不一致")
    stored_materials = _parse_json_object(snapshot_captures["materials.json"]["bytes"],
                                          "materials.json")
    stored_expectations = _parse_json_object(snapshot_captures["expectations.json"]["bytes"],
                                             "expectations.json")
    _require_closed_keys(stored_materials, MATERIALS_KEYS, "snapshots.materials")
    _require_closed_keys(stored_expectations, EXPECTATIONS_KEYS, "snapshots.expectations")
    if canonical_json_bytes(stored_materials) !=             canonical_json_bytes(context["request"]["materials"]):
        _block("snapshots.materials", "与 context.request.materials 不一致")
    if canonical_json_bytes(stored_expectations) !=             canonical_json_bytes(context["request"]["expectations"]):
        _block("snapshots.expectations", "与 context.request.expectations 不一致")
    if binding["materials_fingerprint"] != stored_materials["materials_fingerprint"]:
        _block("record.binding.materials_fingerprint", "与保存材料指纹不一致")
    if binding["request_id"] != stored_expectations["expected_request_id"]:
        _block("record.binding.request_id", "与保存请求 ID 不一致")

    # 私有分支：基于本次已核验事件，从显式 runtime_dir 核验登记与**当前**材料
    current_request = _materialize_gate1_request(
        batch_path, registry, batch_captures, self_capture, static_captures,
        stored_expectations["expected_request_id"], leaf_captures["registry"])
    _finish_prepare(current_request, batch_captures, self_capture, static_captures, leaf,
                    leaf_captures, batch_path, registry, enforce_scope_absent=False,
                    extra_captures=[(context_capture, CONTEXT_FILE),
                                    (receipt_capture, RECEIPT_FILE)]
                                    + [(snapshot_captures[name], f"snapshots.{name}")
                                       for name in SNAPSHOT_FILES])
    if canonical_json_bytes(current_request) != canonical_json_bytes(context["request"]):
        _block("request", "当前独立构造请求与保存时 context.request 不一致（材料晚变更）")

    current_quality = _require_object(current_request["materials"]["quality"],
                                      "materials.quality")
    current_quality_status = current_quality.get("status")
    if current_quality_status not in QUALITY_STATUSES:
        _block("materials.quality.status", f"必须是 {QUALITY_STATUSES} 之一")
    record_quality = _require_object(record.get("quality_summary"),
                                     "record.quality_summary")
    record_quality_status = record_quality.get("status")
    if record_quality_status not in QUALITY_STATUSES:
        _block("record.quality_summary.status", f"必须是 {QUALITY_STATUSES} 之一")
    for key in ("execution_allowed",):
        _require_bool_false(record[key], f"record.{key}")
    _require_closed_keys(record["boundaries"], RECORD_BOUNDARY_KEYS_027,
                         "record.boundaries")
    for key, value in record["boundaries"].items():
        _require_bool_false(value, f"record.boundaries.{key}")
    if record["boundaries"]["approved_for_execution"] is not False:
        _block("record.boundaries.approved_for_execution", "必须严格 false（不放行执行）")

    reasons = []
    if record["decision"] != "APPROVE":
        reasons.append(REASON_DECISION_NOT_APPROVE)
    if record_quality_status != "OK":
        reasons.append(REASON_QUALITY_NOT_OK)
    if current_quality_status != "OK":
        reasons.append(REASON_CURRENT_QUALITY_NOT_OK)
    effective = not reasons
    result = {
        "verification_version": VERIFICATION_VERSION,
        "batch_id": registry["batch_id"],
        "event_relative": event_relative,
        "record_fingerprint": record_fingerprint,
        "record_file_sha256": snapshot_captures[DECISION_RESULT_FILE]["file_sha256"],
        "run_binding_sha256": fingerprint(binding["run_binding"]),
        "materials_fingerprint": stored_materials["materials_fingerprint"],
        "decision": record["decision"],
        "actor_kind": record["actor"]["actor_kind"],
        "effective": effective,
        "reasons": reasons,
    }
    _require_closed_keys(result, VERIFY_KEYS, "verification")
    if not isinstance(result["effective"], bool):
        _block("effective", "必须是严格布尔")
    if result["effective"] is False and not result["reasons"]:
        _block("reasons", "effective 为 false 时必须给出非空原因")
    if result["actor_kind"] != ACTOR_KIND_HUMAN:
        _block("actor_kind", f"唯一允许 {ACTOR_KIND_HUMAN}")
    # 末端确认：本次消费的登记/来源/事件字节、固定集合与锁状态
    for name in BATCH_FILES:
        _recheck_capture(batch_captures[name], f"batch.{name}")
    for relative, capture in sorted(static_captures.get("project", {}).items()):
        _recheck_capture(capture, relative)
    _recheck_capture(static_captures["frozen_prepare"],
                     "scripts/prepare_demo_human_gate1.py")
    _recheck_capture(self_capture, "self")
    _recheck_capture(leaf_captures["registry"], REGISTRY_FILE)
    _recheck_capture(leaf_captures["readback"], READBACK_FILE)
    _recheck_capture(context_capture, CONTEXT_FILE)
    _recheck_capture(receipt_capture, RECEIPT_FILE)
    for name in SNAPSHOT_FILES:
        _recheck_capture(snapshot_captures[name], f"snapshots.{name}")
    _require_fixed_members(batch_path, TOP_LEVEL_MEMBERS, "batch_dir(顶层)")
    for sub, leaves in BATCH_SUBDIR_FILES.items():
        _require_fixed_members(batch_path / sub, leaves, f"batch/{sub}")
    _require_fixed_members(leaf, [REGISTRY_FILE, READBACK_FILE], "runtime_dir(叶)")
    if FAILURE_FILE in _iter_dir(leaf, "final.leaf"):
        _block("runtime_dir(叶)", "登记叶出现 failure 诊断，核验拒绝")
    _require_fixed_members(scope_path, [event_path.name], "scope")
    _require_fixed_members(event_path, list(EVENT_FILES), "event")
    _require_fixed_members(event_path / SNAPSHOT_DIR, list(SNAPSHOT_FILES), "snapshots")
    if _lock_path_for(leaf).exists():
        _block("lock", "末端确认时出现技术锁")
    _confirm_history_namespace_038(leaf_captures["history_namespace"])
    return copy.deepcopy(result)


# --------------------------------------------------------------------------- TASK-028

RUNTIME_VERSION_028 = "TASK-040-runtime-gate1-1.0"
APPROVED_LOAD_STAGE_VERSION = "TASK-028-approved-load-1.0"
APPROVED_LOAD_STATUS = "RT_NORMALIZED"
STARTED_VERSION = "TASK-028-approved-load-start-1.0"
ARTIFACTS_VERSION = "TASK-028-approved-load-artifacts-1.0"
FAILURE_VERSION_028 = "TASK-028-approved-load-failure-1.0"

LOAD_DIR_SUFFIX = ".load"
STARTED_FILE = "started.json"
NORMALIZED_FILE = "normalized.json"
LOAD_REPORT_FILE = "load_report.json"
ARTIFACTS_FILE = "artifacts.json"
APPROVED_LOAD_FILES = (STARTED_FILE, NORMALIZED_FILE, LOAD_REPORT_FILE, ARTIFACTS_FILE)
DATABASE_NAME = "runtime.sqlite3"
QUALITY_RELATIVE = "checks/quality_report.json"
WORKBOOK_RELATIVE = "source/input.xlsx"

APPROVED_LOAD_KEYS = ("stage_version", "status", "batch_id", "run_binding_sha256",
                      "artifacts", "boundaries")
LOAD_BOUNDARY_KEYS = ("gate2_approved", "screening_allowed", "ai_enabled",
                      "initial_judgment_recorded", "audit_conclusion_formed",
                      "identity_authenticated", "source_authenticity_proven",
                      "next_step_allowed")
STARTED_KEYS = ("started_version", "batch_id", "source_batch_relative", "runtime_relative",
                "scope_relative", "event_relative", "database_relative", "bindings")
STARTED_BINDING_KEYS = ("registry_file_sha256", "gate1_record_file_sha256",
                        "gate1_record_fingerprint", "run_binding")
ARTIFACTS_KEYS = ("artifacts_version", "batch_id", "run_binding_sha256",
                  "started_file_sha256", "registry_file_sha256",
                  "gate1_record_file_sha256", "gate1_record_fingerprint",
                  "normalized_file_sha256", "normalized_payload_sha256",
                  "load_report_file_sha256", "database")
ARTIFACTS_DATABASE_KEYS = ("relative", "file_sha256", "byte_size")
FAILURE_KEYS_028 = ("failure_version", "kind", "stage", "field", "reason", "cause_chain")
FAILURE_KINDS = ("BLOCKED", "ERROR")
BUSINESS_TABLES_028 = ("suppliers", "payables", "payments", "allocations")
NORMALIZED_SOURCE_KEYS_028 = ("input_path", "input_sha256", "checker_path",
                              "checker_sha256", "spec_path", "spec_sha256", "path_note")
NET_CHECK_KEYS_028 = ("master_net_equals_known_plus_missing", "master_net_equals_normalized",
                      "known_net_equals_normalized", "missing_net_equals_normalized",
                      "empty_ap_id_equals_normalized", "unknown_ap_id_equals_normalized")

NORMALIZER_RELATIVE = "scripts/normalize_demo_data.py"
NORMALIZER_SHA256 = "a2bae49e3686c6bca012fd4207b6a39424e21515b82af8ce8e7c05b276b72310"
NORMALIZER_ENTRY = "normalize_workbook"
NORMALIZER_VERSION = "TASK-004-normalized-1.1"
SQLITE_CORE_RELATIVE = "scripts/store_demo_sqlite.py"
SQLITE_CORE_SHA256 = "1abfad898e18c54fd5dd81e44973d078187b2837838638c1a6f46e9c8c74a446"
SQLITE_ENTRY = "load_normalized_to_sqlite"
SQLITE_STORE_VERSION = "TASK-005-sqlite-load-1.2"
SQLITE_SCHEMA_VERSION = "demo-schema-1.0"
SQLITE_VERIFIED_STATUS = "DEV_SQLITE_VERIFIED"
SCHEMA_RELATIVE = "sql/demo_schema.sql"
SCHEMA_SHA256 = "7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205"

SQLITE_TESTS_ROOT = (PROJECT_ROOT / "data" / "sqlite_tests").resolve()


def _load_frozen_module(relative: str, expected_sha256: str, module_name: str):
    """加载冻结核心并以其**独立预期 SHA** 实读核验。"""
    path = PROJECT_ROOT / relative
    capture = _capture_file(path, f"read.{module_name}")
    if capture["file_sha256"] != expected_sha256:
        _block(relative, f"冻结核心字节与独立预期不一致：{capture['file_sha256']}")
    cached = sys.modules.get(module_name)
    if cached is not None and getattr(cached, "__frozen_sha256__", None) == expected_sha256:
        return cached
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RuntimeGate1Error(f"load.{module_name}", f"无法建立 spec：{path}")
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
    except (RuntimeGate1Blocked, RuntimeGate1Error):
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeGate1Error(f"load.{module_name}",
                                f"{type(exc).__name__}: {exc}") from exc
    loaded.__frozen_sha256__ = expected_sha256
    sys.modules[module_name] = loaded
    return loaded


def _load_frozen_normalizer():
    return _load_frozen_module(NORMALIZER_RELATIVE, NORMALIZER_SHA256,
                               "frozen_normalizer_runtime")


def _load_frozen_sqlite_core():
    return _load_frozen_module(SQLITE_CORE_RELATIVE, SQLITE_CORE_SHA256,
                               "frozen_sqlite_core_runtime")


def _load_dir_for(leaf: Path) -> Path:
    """计算输出目录：登记叶同级固定名（技术名来自已核验 runtime 路径）。"""
    return leaf.parent / (leaf.name + LOAD_DIR_SUFFIX)


def _approved_boundaries() -> dict:
    return {key: False for key in LOAD_BOUNDARY_KEYS}


def _resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative):
    """解析并核验参数路径，返回 (batch_path, leaf, scope_path, event_path)，全部只读。"""
    _require_nonempty_str(event_relative, "event_relative")
    if event_relative.startswith("/") or ":" in event_relative:
        _block("event_relative", "必须是项目相对路径")
    batch_captures: dict = {}
    batch_path = _check_batch_dir(batch_dir, batch_captures)
    leaf = _read_registry_leaf(runtime_dir)
    if not isinstance(scope_dir, (str, os.PathLike)):
        _block("scope_dir", f"必须是路径，实际 {type(scope_dir).__name__}")
    raw_scope = Path(scope_dir)
    _reject_reparse_chain(raw_scope, "scope_dir")
    try:
        scope_path = raw_scope.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.scope_dir", f"{raw_scope}：{exc}") from exc
    raw_event = PROJECT_ROOT / event_relative
    _reject_reparse_chain(raw_event, "event_relative")
    try:
        event_path = raw_event.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.event_relative", f"{raw_event}：{exc}") from exc
    if event_path != raw_event:
        _block("event_relative", "解析后与显式项目相对路径不一致")
    _require_descendant(event_path, scope_path, "event_relative")
    return batch_path, leaf, scope_path, event_path, batch_captures


def _check_database_target(database_path, *, batch_path: Path, leaf: Path, scope_path: Path,
                           event_path: Path, load_dir: Path,
                           require_new_leaf: bool = True) -> Path:
    """数据库目标：data/sqlite_tests 严格后代、固定文件名、所在叶从未存在、无祖先/相等关系。"""
    if not isinstance(database_path, (str, os.PathLike)):
        _block("database_path", f"必须是路径，实际 {type(database_path).__name__}")
    raw = Path(database_path)
    _reject_reparse_chain(raw, "database_path")
    try:
        resolved = raw.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.database_path", f"{raw}：{exc}") from exc
    if raw != resolved:
        _block("database_path", "解析后与显式路径不一致")
    _require_descendant(resolved, SQLITE_TESTS_ROOT, "database_path")
    if resolved.name != DATABASE_NAME:
        _block("database_path", f"固定文件名必须是 {DATABASE_NAME}")
    parent = resolved.parent
    if parent == SQLITE_TESTS_ROOT:
        _block("database_path", "数据库必须位于本轮新叶目录内，不接受根下直放")
    if require_new_leaf and parent.exists():
        _block("database_path", f"数据库所在叶必须从未存在：{_safe_relative(parent)}")
    if not require_new_leaf and not parent.is_dir():
        _block("database_path", f"数据库所在叶不存在：{_safe_relative(parent)}")
    for other, field in ((batch_path, "batch_dir"), (leaf, "runtime_dir"),
                         (scope_path, "scope_dir"), (event_path, "event_dir"),
                         (load_dir, "load_dir")):
        if resolved == other or _is_ancestor(resolved, other) or _is_ancestor(other, resolved):
            _block("database_path", f"与 {field} 相等或互为祖先")
    return resolved


def _is_ancestor(candidate: Path, other: Path) -> bool:
    try:
        other.relative_to(candidate)
    except ValueError:
        return False
    return candidate != other


def _write_approved_failure(load_dir: Path, kind: str, stage: str, field, reason: str,
                            chain) -> None:
    if kind not in FAILURE_KINDS:
        kind = "ERROR"
    payload = {"failure_version": FAILURE_VERSION_028, "kind": kind, "stage": stage,
               "field": field, "reason": reason, "cause_chain": list(chain)}
    _require_closed_keys(payload, FAILURE_KEYS_028, "failure")
    try:
        _write_exclusive(load_dir / FAILURE_FILE, _payload_bytes(payload), "write.failure")
    except Exception as nested:  # noqa: BLE001
        raise RuntimeGate1Error(
            "write.failure",
            f"诊断写出失败：{type(nested).__name__}: {nested}；原始错误：{reason}",
        ) from nested


def _require_effective_gate1(batch_path: Path, leaf: Path, scope_path: Path,
                             event_relative: str) -> dict:
    """真实调用既有 Gate1 核验，并要求当前批准确实有效。"""
    verification = verify_gate1_effective_approval(
        batch_path, leaf, scope_dir=scope_path, event_relative=event_relative)
    if verification["effective"] is not True:
        _block("gate1.effective", f"当前 Gate1 前提未通过：{verification['reasons']}")
    if verification["decision"] != "APPROVE":
        _block("gate1.decision", f"必须为 APPROVE，实际 {verification['decision']!r}")
    if verification["actor_kind"] != ACTOR_KIND_HUMAN:
        _block("gate1.actor_kind", f"必须为 {ACTOR_KIND_HUMAN}")
    if verification["reasons"] != []:
        _block("gate1.reasons", f"必须为空，实际 {verification['reasons']}")
    return verification


def _read_quality_report(batch_path: Path) -> dict:
    capture = _capture_file(batch_path / QUALITY_RELATIVE, "read.quality_report")
    return _require_object(_parse_json_object(capture["bytes"], QUALITY_RELATIVE),
                           QUALITY_RELATIVE), capture


def _check_quality_binding(quality_capture: dict, request: dict) -> None:
    """本次同缓冲质量报告必须与 Gate1 材料绑定一致。"""
    entries = _require_list(request["materials"]["files"], "materials.files")
    match = [item for item in entries if item.get("relative") == QUALITY_RELATIVE]
    if len(match) != 1:
        _block(QUALITY_RELATIVE, "Gate1 材料中必须恰有一项该相对路径")
    item = _require_object(match[0], f"materials.files[{QUALITY_RELATIVE}]")
    if item.get("file_sha256") != quality_capture["file_sha256"] \
            or item.get("byte_size") != quality_capture["byte_size"]:
        _block(QUALITY_RELATIVE, "本次实读字节与 Gate1 材料绑定不一致")


def _require_nonneg_int(value, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _block(field, f"必须是严格非负整数，实际 {type(value).__name__} {value!r}")
    return value


def _read_only_row_counts(database_path: Path) -> dict:
    """只读 SQLite 连接实际查询四业务表行数；结束关闭连接。"""
    import sqlite3 as _sqlite3
    try:
        connection = _sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeGate1Error("sqlite.read_only",
                                f"{type(exc).__name__}: {exc}") from exc
    try:
        counts = {}
        for table in BUSINESS_TABLES_028:
            try:
                row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            except Exception as exc:  # noqa: BLE001
                raise RuntimeGate1Error(
                    "sqlite.read_only", f"{table}: {type(exc).__name__}: {exc}") from exc
            counts[table] = _require_nonneg_int(int(row[0]), f"sqlite.counts.{table}")
        return counts
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass


def _validate_load_report(report: dict, normalized: dict, database_path: Path,
                          core, *, workbook_capture, project_captures) -> dict:
    """核对完整 load_report：状态/版本/next=false/摘要/数据库字节/四表行数。"""
    report = _require_object(report, "load_report")
    if report.get("batch_status") != SQLITE_VERIFIED_STATUS:
        _block("load_report.batch_status", f"必须是 {SQLITE_VERIFIED_STATUS}")
    if report.get("store_version") != SQLITE_STORE_VERSION:
        _block("load_report.store_version", f"必须是 {SQLITE_STORE_VERSION}")
    if report.get("schema_version") != SQLITE_SCHEMA_VERSION:
        _block("load_report.schema_version", f"必须是 {SQLITE_SCHEMA_VERSION}")
    if report.get("normalization_version") != NORMALIZER_VERSION:
        _block("load_report.normalization_version", f"必须是 {NORMALIZER_VERSION}")
    if report.get("next_step_allowed") is not False:
        _block("load_report.next_step_allowed", "必须严格 false")
    if report.get("mode") != "DEVELOPMENT_TEST_ONLY":
        _block("load_report.mode", "必须保留冻结核心的 DEVELOPMENT_TEST_ONLY 标记")
    if report.get("database_path") != str(database_path):
        _block("load_report.database_path", "与显式数据库路径不一致")
    payload_sha = core.payload_sha256(normalized)
    if report.get("normalized_payload_sha256") != payload_sha:
        _block("load_report.normalized_payload_sha256", "与本次标准化对象不一致")
    capture = _capture_file(database_path, "read.database")
    if report.get("database_sha256") != capture["file_sha256"]:
        _block("load_report.database_sha256", "与数据库实读字节不一致")
    if normalized.get("normalization_version") != NORMALIZER_VERSION:
        _block("normalized.normalization_version", f"必须是 {NORMALIZER_VERSION}")
    if normalized.get("mode") != "DEVELOPMENT_TEST_ONLY":
        _block("normalized.mode", "必须保留 DEVELOPMENT_TEST_ONLY 标记")
    if normalized.get("next_step_allowed") is not False:
        _block("normalized.next_step_allowed", "必须严格 false")

    row_counts = _require_object(report.get("row_counts"), "load_report.row_counts")
    tables = _require_object(normalized.get("tables"), "normalized.tables")
    for table in BUSINESS_TABLES_028:
        table_object = _require_object(tables.get(table), f"normalized.tables.{table}")
        records = _require_list(table_object.get("records"),
                               f"normalized.tables.{table}.records")
        reported = _require_nonneg_int(row_counts.get(table),
                                       f"load_report.row_counts.{table}")
        if reported != len(records):
            _block(f"load_report.row_counts.{table}",
                   f"报告 {reported!r} 与标准化记录数 {len(records)} 不一致")

    source = _require_closed_keys(normalized.get("source"), NORMALIZED_SOURCE_KEYS_028,
                                   "normalized.source")
    for key, value in source.items():
        _require_nonempty_str(value, f"normalized.source.{key}")
    for key in ("input_sha256", "checker_sha256", "spec_sha256"):
        _require_hash(source.get(key), f"normalized.source.{key}")
    if source["input_path"] != workbook_capture["path"]:
        _block("normalized.source.input_path", "与本次工作簿路径不一致")
    if source["input_sha256"] != workbook_capture["file_sha256"]:
        _block("normalized.source.input_sha256", "与本次已绑定工作簿字节不一致")
    for prefix, relative in (("checker", "scripts/check_demo_data.py"),
                              ("spec", "docs/SPEC_V1.md")):
        if source[f"{prefix}_path"] != relative:
            _block(f"normalized.source.{prefix}_path", "与冻结来源路径不一致")
        if source[f"{prefix}_sha256"] != project_captures[relative]["file_sha256"]:
            _block(f"normalized.source.{prefix}_sha256", "与本次已核验静态读数不一致")
    report_source = _require_object(report.get("source"), "load_report.source")
    if canonical_json_bytes(report_source) != canonical_json_bytes(source):
        _block("load_report.source", "与本次标准化对象 source 不一致")

    raw_metadata = report.get("run_metadata")
    if isinstance(raw_metadata, dict):
        pairs = {str(key): value for key, value in raw_metadata.items()}
    elif isinstance(raw_metadata, list):
        pairs = {}
        for index, item in enumerate(raw_metadata):
            entry = _require_list(item, f"load_report.run_metadata[{index}]")
            if len(entry) != 2:
                _block(f"load_report.run_metadata[{index}]", "必须是两元素键值对")
            pairs[str(entry[0])] = entry[1]
    else:
        _block("load_report.run_metadata", "必须是对象或键值对列表")
    for key in ("input_sha256", "normalized_payload_sha256"):
        if str(pairs.get(key)) != str(source.get("input_sha256")
                                      if key == "input_sha256" else payload_sha):
            _block(f"load_report.run_metadata.{key}", "与本次输入/标准化指纹不一致")
    for flag in ("round_trip_exact", "event_allocation_balanced"):
        if report.get(flag) is not True:
            _block(f"load_report.{flag}", "核心成功旗标必须严格 true")
    net_checks = _require_closed_keys(report.get("net_checks"), NET_CHECK_KEYS_028,
                                      "load_report.net_checks")
    for key, value in net_checks.items():
        if value is not True:
            _block(f"load_report.net_checks.{key}", "冻结成功旗标必须严格 true")

    actual = _read_only_row_counts(database_path)
    for table in BUSINESS_TABLES_028:
        if actual[table] != row_counts[table]:
            _block(f"sqlite.counts.{table}",
                   f"库内实际 {actual[table]} 与报告 {row_counts[table]} 不一致")
    return {"report": report, "database_capture": capture, "payload_sha256": payload_sha,
            "sqlite_row_counts": actual}


def _confirm_approved_terminal(batch_path: Path, batch_captures: dict, leaf: Path,
                               leaf_captures: dict, event_captures: dict,
                               scope_path: Path, event_path: Path, load_dir: Path,
                               database_capture: dict, started_capture: dict,
                               normalized_capture: dict, report_capture: dict,
                               artifacts_capture: dict, static_captures: dict,
                               self_capture: dict) -> None:
    """末端有界确认：只用**起始读数**与本次已绑定 capture，不做自比、不重新采集覆盖预期。"""
    _require_fixed_members(batch_path, TOP_LEVEL_MEMBERS, "batch_dir(顶层)")
    for sub, leaves in BATCH_SUBDIR_FILES.items():
        _require_fixed_members(batch_path / sub, leaves, f"batch/{sub}")
    for name in BATCH_FILES:
        _recheck_capture(batch_captures[name], f"batch.{name}")
    for relative, capture in sorted(static_captures.get("project", {}).items()):
        _recheck_capture(capture, relative)
    _recheck_capture(static_captures["frozen_prepare"],
                     "scripts/prepare_demo_human_gate1.py")
    _recheck_capture(static_captures["normalizer"], NORMALIZER_RELATIVE)
    _recheck_capture(static_captures["sqlite_core"], SQLITE_CORE_RELATIVE)
    _recheck_capture(static_captures["schema"], SCHEMA_RELATIVE)
    _recheck_capture(self_capture, "self")
    _recheck_capture(leaf_captures["registry"], REGISTRY_FILE)
    _recheck_capture(leaf_captures["readback"], READBACK_FILE)
    _require_fixed_members(leaf, [REGISTRY_FILE, READBACK_FILE], "runtime_dir(叶)")
    if FAILURE_FILE in _iter_dir(leaf, "final.leaf"):
        _block("runtime_dir(叶)", "登记叶出现 failure 诊断")
    _require_fixed_members(scope_path, [event_path.name], "scope")
    _require_fixed_members(event_path, list(EVENT_FILES), "event")
    _require_fixed_members(event_path / SNAPSHOT_DIR, list(SNAPSHOT_FILES), "snapshots")
    for name in (CONTEXT_FILE, RECEIPT_FILE):
        _recheck_capture(event_captures[name], name)
    for name in SNAPSHOT_FILES:
        _recheck_capture(event_captures[f"snapshots/{name}"], f"snapshots/{name}")
    if FAILURE_FILE in _iter_dir(event_path, "final.event"):
        _block("event", "成功路径不得残留 failure 诊断")
    _require_fixed_members(load_dir, list(APPROVED_LOAD_FILES), "load_dir")
    if FAILURE_FILE in _iter_dir(load_dir, "final.load"):
        _block("load_dir", "成功路径不得残留 failure 诊断")
    _recheck_capture(started_capture, STARTED_FILE)
    _recheck_capture(normalized_capture, NORMALIZED_FILE)
    _recheck_capture(report_capture, LOAD_REPORT_FILE)
    _recheck_capture(artifacts_capture, ARTIFACTS_FILE)
    _require_fixed_members(database_capture["path"] and Path(database_capture["path"]).parent,
                           [DATABASE_NAME], "database_dir")
    _recheck_capture(database_capture, DATABASE_NAME)
    if _lock_path_for(leaf).exists():
        _block("lock", "末端确认时出现技术锁")
    _confirm_history_namespace_038(leaf_captures["history_namespace"])


def _capture_event_028(event_path: Path, *, include_envelopes=True, reject_links=False) -> dict:
    """起始固定 Gate1 八文件（context/receipt/六快照）的同缓冲读数。"""
    if reject_links:
        names = ((CONTEXT_FILE, RECEIPT_FILE) if include_envelopes else ()) + tuple(
            f"{SNAPSHOT_DIR}/{name}" for name in SNAPSHOT_FILES)
        for relative in names:
            _reject_reparse_chain(event_path / relative, f"gate2.{relative}")
    captures = ({CONTEXT_FILE: _capture_file(event_path / CONTEXT_FILE, "read.event.context"),
                 RECEIPT_FILE: _capture_file(event_path / RECEIPT_FILE, "read.event.receipt")}
                if include_envelopes else {})
    for name in SNAPSHOT_FILES:
        captures[f"snapshots/{name}"] = _capture_file(
            event_path / SNAPSHOT_DIR / name, f"read.event.snapshots.{name}")
    return captures


def _capture_static_028() -> dict:
    captures = {}
    for key, relative in (("normalizer", NORMALIZER_RELATIVE),
                          ("sqlite_core", SQLITE_CORE_RELATIVE),
                          ("schema", SCHEMA_RELATIVE)):
        captures[key] = _capture_file(PROJECT_ROOT / relative, f"read.{key}")
    return captures


def _recheck_approved_inputs(batch_captures, leaf_captures, event_captures) -> None:
    """每个计算入口前确认起始来源、登记和事件读数；不更新预期。"""
    batch_path = Path(batch_captures["batch_manifest.json"]["path"]).parent
    leaf = Path(leaf_captures["registry"]["path"]).parent
    event_path = Path(event_captures[CONTEXT_FILE]["path"]).parent
    _require_fixed_members(batch_path, TOP_LEVEL_MEMBERS, "batch_dir(顶层)")
    for sub, members in BATCH_SUBDIR_FILES.items():
        _require_fixed_members(batch_path / sub, members, f"batch/{sub}")
    _require_fixed_members(leaf, [REGISTRY_FILE, READBACK_FILE], "runtime_dir(叶)")
    _require_fixed_members(event_path.parent, [event_path.name], "scope")
    _require_fixed_members(event_path, list(EVENT_FILES), "event")
    _require_fixed_members(event_path / SNAPSHOT_DIR, list(SNAPSHOT_FILES), "snapshots")
    if _lock_path_for(leaf).exists():
        _block("lock", "计算核心调用前出现技术锁")
    for name in BATCH_FILES:
        _recheck_capture(batch_captures[name], f"batch.{name}")
    _recheck_capture(leaf_captures["registry"], REGISTRY_FILE)
    _recheck_capture(leaf_captures["readback"], READBACK_FILE)
    for name, capture in event_captures.items():
        _recheck_capture(capture, f"gate1.{name}")


def run_gate1_approved_load(batch_dir, runtime_dir, *, scope_dir, event_relative,
                            database_path) -> dict:
    """有效 Gate1 批准之后执行一次标准化与 SQLite 装载；停在 RT_NORMALIZED。

    真正调用两个冻结计算核心各一次；不生成 Gate2 请求/决定，不做筛查/事实/初判/AI。
    """
    batch_path, leaf, scope_path, event_path, batch_captures = _resolve_approved_paths(
        batch_dir, runtime_dir, scope_dir, event_relative)
    load_dir = _load_dir_for(leaf)
    _reject_reparse_chain(load_dir, "load_dir")
    if load_dir.exists():
        _block("load_dir", f"计算输出目录必须从未存在：{_safe_relative(load_dir)}")
    database_target = _check_database_target(
        database_path, batch_path=batch_path, leaf=leaf, scope_path=scope_path,
        event_path=event_path, load_dir=load_dir)

    self_capture = _capture_file(MODULE_PATH, "read.self")
    registry, _, leaf_captures = _load_stored_registry(leaf, allow_existing_scope=True)
    static_captures: dict = {}
    _require_current_static_identity(registry, self_capture, static_captures)
    static_captures.update(_capture_static_028())
    quality_report, quality_capture = _read_quality_report(batch_path)
    event_captures = _capture_event_028(event_path)
    verification = _require_effective_gate1(batch_path, leaf, scope_path, event_relative)
    pre_binding, _, _ = _load_stored_registry(leaf, allow_existing_scope=True)
    run_binding = _require_object(pre_binding["run_binding"], "registry.run_binding")

    try:
        load_dir.mkdir()
    except OSError as exc:
        raise RuntimeGate1Error("mkdir.load_dir",
                                f"独占建立计算目录失败：{exc}") from exc
    try:
        database_target.parent.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        stage = "mkdir.database_dir"
        if load_dir.is_dir():
            _write_approved_failure(load_dir, "ERROR", stage, "database_path",
                                    f"数据库叶创建失败：{exc}", _cause_chain(exc))
        raise RuntimeGate1Error(stage, f"数据库叶创建失败：{exc}") from exc
    stage = "started"
    result = None
    try:
        started = {
            "started_version": STARTED_VERSION,
            "batch_id": verification["batch_id"],
            "source_batch_relative": _project_relative(batch_path),
            "runtime_relative": _project_relative(leaf),
            "scope_relative": _project_relative(scope_path),
            "event_relative": event_relative,
            "database_relative": _project_relative(database_target),
            "bindings": {
                "registry_file_sha256": leaf_captures["registry"]["file_sha256"],
                "gate1_record_file_sha256": verification["record_file_sha256"],
                "gate1_record_fingerprint": verification["record_fingerprint"],
                "run_binding": copy.deepcopy(run_binding),
            },
        }
        _require_closed_keys(started, STARTED_KEYS, "started")
        _require_closed_keys(started["bindings"], STARTED_BINDING_KEYS, "started.bindings")
        started_buffer = _payload_bytes(started)
        _write_exclusive(load_dir / STARTED_FILE, started_buffer, "write.started")
        started_capture = _capture_file(load_dir / STARTED_FILE, "readback.started")
        if started_capture["bytes"] != started_buffer:
            _block(STARTED_FILE, "读回字节与本次 writer 缓冲不一致")

        stage = "normalize"
        for name in BATCH_FILES:
            _recheck_capture(batch_captures[name], f"batch.{name}")
        _recheck_capture(quality_capture, QUALITY_RELATIVE)
        _recheck_capture(leaf_captures["registry"], REGISTRY_FILE)
        _recheck_capture(leaf_captures["readback"], READBACK_FILE)
        workbook_capture = _capture_file(batch_path / WORKBOOK_RELATIVE, "read.workbook")
        normalizer = _load_frozen_normalizer()
        quality_fingerprint = fingerprint(quality_report)
        _recheck_approved_inputs(batch_captures, leaf_captures, event_captures)
        normalized = _call_frozen_entry(normalizer, NORMALIZER_ENTRY,
                                        batch_path / WORKBOOK_RELATIVE, quality_report)
        if fingerprint(quality_report) != quality_fingerprint:
            _block("quality_report", "核心调用改写了本次内存输入（应保持原对象）")
        _recheck_capture(workbook_capture, WORKBOOK_RELATIVE)
        _require_object(normalized, "normalized")

        stage = "normalized_write"
        normalized_buffer = _payload_bytes(normalized)
        _write_exclusive(load_dir / NORMALIZED_FILE, normalized_buffer, "write.normalized")
        normalized_capture = _capture_file(load_dir / NORMALIZED_FILE, "readback.normalized")
        if normalized_capture["bytes"] != normalized_buffer:
            _block(NORMALIZED_FILE, "读回字节与本次 writer 缓冲不一致")

        stage = "load"
        for name in BATCH_FILES:
            _recheck_capture(batch_captures[name], f"batch.{name}")
        _recheck_capture(leaf_captures["registry"], REGISTRY_FILE)
        core = _load_frozen_sqlite_core()
        normalized_fingerprint = fingerprint(normalized)
        _recheck_approved_inputs(batch_captures, leaf_captures, event_captures)
        report = _call_frozen_entry(core, SQLITE_ENTRY, normalized, database_target)
        if fingerprint(normalized) != normalized_fingerprint:
            _block("normalized", "核心调用改写了本次内存标准化对象（应保持原对象）")
        report = _require_object(report, "load_report")
        checked = _validate_load_report(report, normalized, database_target, core,
                                        workbook_capture=workbook_capture,
                                        project_captures=static_captures["project"])
        report_buffer = _payload_bytes(checked["report"])
        _write_exclusive(load_dir / LOAD_REPORT_FILE, report_buffer, "write.load_report")
        report_capture = _capture_file(load_dir / LOAD_REPORT_FILE, "readback.load_report")
        if report_capture["bytes"] != report_buffer:
            _block(LOAD_REPORT_FILE, "读回字节与本次 writer 缓冲不一致")

        stage = "reverify"
        reverify = _require_effective_gate1(batch_path, leaf, scope_path, event_relative)
        if reverify["record_file_sha256"] != verification["record_file_sha256"] \
                or reverify["record_fingerprint"] != verification["record_fingerprint"]:
            _block("gate1.recheck", "复核时 Gate1 记录摘要与起始读数不一致")
        _, _, leaf_captures_after = _load_stored_registry(leaf, allow_existing_scope=True)
        if leaf_captures_after["registry"]["file_sha256"] \
                != leaf_captures["registry"]["file_sha256"]:
            _block("registry_file_sha256", "复核时登记文件字节已变化")

        stage = "artifacts"
        artifacts = {
            "artifacts_version": ARTIFACTS_VERSION,
            "batch_id": verification["batch_id"],
            "run_binding_sha256": verification["run_binding_sha256"],
            "started_file_sha256": started_capture["file_sha256"],
            "registry_file_sha256": leaf_captures["registry"]["file_sha256"],
            "gate1_record_file_sha256": verification["record_file_sha256"],
            "gate1_record_fingerprint": verification["record_fingerprint"],
            "normalized_file_sha256": normalized_capture["file_sha256"],
            "normalized_payload_sha256": checked["payload_sha256"],
            "load_report_file_sha256": report_capture["file_sha256"],
            "database": {"relative": _project_relative(database_target),
                         "file_sha256": checked["database_capture"]["file_sha256"],
                         "byte_size": checked["database_capture"]["byte_size"]},
        }
        _require_closed_keys(artifacts, ARTIFACTS_KEYS, "artifacts")
        _require_closed_keys(artifacts["database"], ARTIFACTS_DATABASE_KEYS,
                             "artifacts.database")
        artifacts_buffer = _payload_bytes(artifacts)
        _write_exclusive(load_dir / ARTIFACTS_FILE, artifacts_buffer, "write.artifacts")
        artifacts_capture = _capture_file(load_dir / ARTIFACTS_FILE, "readback.artifacts")
        if artifacts_capture["bytes"] != artifacts_buffer:
            _block(ARTIFACTS_FILE, "读回字节与本次 writer 缓冲不一致")

        stage = "final_confirm"
        if fingerprint(quality_report) != quality_fingerprint:
            _block("quality_report", "API 收尾时本次内存输入已变化")
        if fingerprint(normalized) != normalized_fingerprint:
            _block("normalized", "API 收尾时本次标准化对象已变化")
        result = {"stage_version": APPROVED_LOAD_STAGE_VERSION,
                  "status": APPROVED_LOAD_STATUS,
                  "batch_id": verification["batch_id"],
                  "run_binding_sha256": verification["run_binding_sha256"],
                  "artifacts": copy.deepcopy(artifacts),
                  "boundaries": _approved_boundaries()}
        _require_closed_keys(result, APPROVED_LOAD_KEYS, "approved_load")
        _confirm_approved_terminal(batch_path, batch_captures, leaf, leaf_captures_after,
                                   event_captures, scope_path, event_path, load_dir,
                                   checked["database_capture"], started_capture,
                                   normalized_capture, report_capture, artifacts_capture,
                                   static_captures, self_capture)
    except (RuntimeGate1Blocked, RuntimeGate1Error) as exc:
        if load_dir.is_dir() and not (load_dir / FAILURE_FILE).is_file():
            _write_approved_failure(
                load_dir, "BLOCKED" if isinstance(exc, RuntimeGate1Blocked) else "ERROR",
                stage, getattr(exc, "field", None), getattr(exc, "reason", str(exc)),
                _cause_chain(exc))
        raise
    except Exception as exc:  # noqa: BLE001
        mapped = RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}")
        if load_dir.is_dir() and not (load_dir / FAILURE_FILE).is_file():
            _write_approved_failure(load_dir, "ERROR", stage, None,
                                    f"{type(exc).__name__}: {exc}", _cause_chain(exc))
        raise mapped from exc
    return result


def _core_reason(exc) -> str:
    """保留原始说明及 reasons；不能用 str(exc) 丢弃完整原因列表。"""
    reason = getattr(exc, "reason", None)
    text = reason if isinstance(reason, str) and reason.strip() else str(exc)
    reasons = getattr(exc, "reasons", None)
    suffix = f"; reasons={reasons!r}" if reasons is not None else ""
    return f"{type(exc).__name__}: {text}{suffix}"


def _call_frozen_entry(module, entry_name: str, *args, **kwargs):
    """调用冻结入口一次；按**实际加载模块上的真实异常类型**分类映射。"""
    entry = getattr(module, entry_name, None)
    if entry is None:
        _block(entry_name, "冻结核心缺少入口")
    try:
        return entry(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        reason = _core_reason(exc)
        blocked_types = tuple(cls for cls in
                              (getattr(module, "NormalizationBlocked", None),
                               getattr(module, "SqliteLoadBlocked", None),
                               getattr(module, "RuleScreenBlocked", None),
                               getattr(module, "CrossCheckBlocked", None),
                               getattr(module, "FactPacketBlocked", None))
                              if isinstance(cls, type) and issubclass(cls, Exception))
        mapped = (RuntimeGate1Blocked(entry_name, reason) if isinstance(exc, blocked_types)
                  else RuntimeGate1Error(entry_name, reason))
        if hasattr(exc, "reasons"):
            mapped.reasons = copy.deepcopy(exc.reasons)
        raise mapped from exc


def _validate_report_shape(report: dict) -> dict:
    if not isinstance(report, dict):
        _block("load_report", "必须是对象")
    return report


def inspect_gate1_approved_load(batch_dir, runtime_dir, *, scope_dir, event_relative,
                                database_path) -> dict:
    """只读核验一次已完成的批准装载；先查有效 failure，再解析其余文件。"""
    batch_path, leaf, scope_path, event_path, batch_captures = _resolve_approved_paths(
        batch_dir, runtime_dir, scope_dir, event_relative)
    load_dir = _load_dir_for(leaf)
    _reject_reparse_chain(load_dir, "load_dir")
    if not load_dir.is_dir():
        _block("load_dir", f"计算输出目录不存在：{_safe_relative(load_dir)}")
    database_target = _check_database_target(
        database_path, batch_path=batch_path, leaf=leaf, scope_path=scope_path,
        event_path=event_path, load_dir=load_dir, require_new_leaf=False)
    failure_path = load_dir / FAILURE_FILE
    if failure_path.is_file():
        try:
            raw_failure = failure_path.read_bytes()
        except OSError as exc:
            raise RuntimeGate1Error("read.failure",
                                    f"读取诊断失败：{exc}") from exc
        payload = _parse_json_object(raw_failure, FAILURE_FILE)
        if not isinstance(payload, dict):
            _block("failure", "诊断必须是对象")
        kind = payload.get("kind")
        if kind not in FAILURE_KINDS:
            _block("failure.kind", f"必须是 {FAILURE_KINDS} 之一，实际 {kind!r}")
        failure = _require_closed_keys(payload, FAILURE_KEYS_028, "failure")
        if failure["failure_version"] != FAILURE_VERSION_028:
            _block("failure.failure_version", "诊断版本不符")
        _require_nonempty_str(failure["stage"], "failure.stage")
        if failure["field"] is not None:
            _require_nonempty_str(failure["field"], "failure.field")
        _require_nonempty_str(failure["reason"], "failure.reason")
        for index, item in enumerate(_require_list(failure["cause_chain"],
                                                   "failure.cause_chain")):
            _require_nonempty_str(item, f"failure.cause_chain[{index}]")
        if failure["kind"] == "BLOCKED":
            raise RuntimeGate1Blocked(f"failure.{failure['field']}", failure["reason"])
        raise RuntimeGate1Error(f"failure.{failure['stage']}", failure["reason"])

    self_capture = _capture_file(MODULE_PATH, "read.self")
    registry, _, leaf_captures = _load_stored_registry(leaf, allow_existing_scope=True)
    static_captures: dict = {}
    _require_current_static_identity(registry, self_capture, static_captures)
    static_captures.update(_capture_static_028())
    event_captures = _capture_event_028(event_path)
    _require_fixed_members(load_dir, list(APPROVED_LOAD_FILES), "load_dir")
    _require_fixed_members(database_target.parent, [DATABASE_NAME], "database_dir")
    verification = _require_effective_gate1(batch_path, leaf, scope_path, event_relative)

    started_capture = _capture_file(load_dir / STARTED_FILE, "read.started")
    normalized_capture = _capture_file(load_dir / NORMALIZED_FILE, "read.normalized")
    report_capture = _capture_file(load_dir / LOAD_REPORT_FILE, "read.load_report")
    artifacts_capture = _capture_file(load_dir / ARTIFACTS_FILE, "read.artifacts")
    started = _require_closed_keys(
        _parse_json_object(started_capture["bytes"], STARTED_FILE), STARTED_KEYS,
        "started")
    artifacts = _require_closed_keys(
        _parse_json_object(artifacts_capture["bytes"], ARTIFACTS_FILE), ARTIFACTS_KEYS,
        "artifacts")
    normalized = _require_object(
        _parse_json_object(normalized_capture["bytes"], NORMALIZED_FILE), NORMALIZED_FILE)
    report = _require_object(
        _parse_json_object(report_capture["bytes"], LOAD_REPORT_FILE), LOAD_REPORT_FILE)

    if started["started_version"] != STARTED_VERSION:
        _block("started.started_version", f"必须是 {STARTED_VERSION}")
    if started["batch_id"] != verification["batch_id"]:
        _block("started.batch_id", "与当前 Gate1 批次不一致")
    if artifacts["artifacts_version"] != ARTIFACTS_VERSION:
        _block("artifacts.artifacts_version", f"必须是 {ARTIFACTS_VERSION}")
    for key, value in (("source_batch_relative", _project_relative(batch_path)),
                       ("runtime_relative", _project_relative(leaf)),
                       ("scope_relative", _project_relative(scope_path)),
                       ("event_relative", event_relative),
                       ("database_relative", _project_relative(database_target))):
        if started[key] != value:
            _block(f"started.{key}", "与显式参数不一致")
    bindings = _require_closed_keys(started["bindings"], STARTED_BINDING_KEYS,
                                    "started.bindings")
    if bindings["registry_file_sha256"] != leaf_captures["registry"]["file_sha256"]:
        _block("started.bindings.registry_file_sha256", "与本次实读登记不一致")
    if bindings["gate1_record_file_sha256"] != verification["record_file_sha256"] \
            or bindings["gate1_record_fingerprint"] != verification["record_fingerprint"]:
        _block("started.bindings.gate1_record", "与当前 Gate1 记录不一致")
    if canonical_json_bytes(bindings["run_binding"]) != \
            canonical_json_bytes(registry["run_binding"]):
        _block("started.bindings.run_binding", "与登记六项绑定不一致")
    if artifacts["batch_id"] != verification["batch_id"]:
        _block("artifacts.batch_id", "与当前 Gate1 批次不一致")
    if artifacts["run_binding_sha256"] != verification["run_binding_sha256"]:
        _block("artifacts.run_binding_sha256", "与当前共享运行绑定不一致")
    if artifacts["registry_file_sha256"] != leaf_captures["registry"]["file_sha256"] \
            or artifacts["registry_file_sha256"] != bindings["registry_file_sha256"]:
        _block("artifacts.registry_file_sha256", "与本次实读登记/started 绑定不一致")
    if artifacts["gate1_record_file_sha256"] != verification["record_file_sha256"] \
            or artifacts["gate1_record_file_sha256"] \
            != bindings["gate1_record_file_sha256"]:
        _block("artifacts.gate1_record_file_sha256", "与当前 Gate1 记录不一致")
    if artifacts["gate1_record_fingerprint"] != verification["record_fingerprint"] \
            or artifacts["gate1_record_fingerprint"] \
            != bindings["gate1_record_fingerprint"]:
        _block("artifacts.gate1_record_fingerprint", "与当前 Gate1 指纹不一致")
    if artifacts["started_file_sha256"] != started_capture["file_sha256"]:
        _block("artifacts.started_file_sha256", "与实读 started.json 不一致")
    if artifacts["normalized_file_sha256"] != normalized_capture["file_sha256"]:
        _block("artifacts.normalized_file_sha256", "与实读 normalized.json 不一致")
    if artifacts["load_report_file_sha256"] != report_capture["file_sha256"]:
        _block("artifacts.load_report_file_sha256", "与实读 load_report.json 不一致")
    database = _require_closed_keys(artifacts["database"], ARTIFACTS_DATABASE_KEYS,
                                    "artifacts.database")
    if database["relative"] != _project_relative(database_target):
        _block("artifacts.database.relative", "与显式数据库路径不一致")
    _require_nonneg_int(database["byte_size"], "artifacts.database.byte_size")
    core = _load_frozen_sqlite_core()
    checked = _validate_load_report(report, normalized, database_target, core,
                                    workbook_capture=batch_captures[WORKBOOK_RELATIVE],
                                    project_captures=static_captures["project"])
    if database["file_sha256"] != checked["database_capture"]["file_sha256"] \
            or database["byte_size"] != checked["database_capture"]["byte_size"]:
        _block("artifacts.database", "与数据库实读字节不一致")
    if artifacts["normalized_payload_sha256"] != checked["payload_sha256"]:
        _block("artifacts.normalized_payload_sha256", "与本次标准化对象不一致")
    result = {"stage_version": APPROVED_LOAD_STAGE_VERSION,
              "status": APPROVED_LOAD_STATUS,
              "batch_id": verification["batch_id"],
              "run_binding_sha256": verification["run_binding_sha256"],
              "artifacts": copy.deepcopy(artifacts),
              "boundaries": _approved_boundaries()}
    _require_closed_keys(result, APPROVED_LOAD_KEYS, "approved_load")
    _confirm_approved_terminal(batch_path, batch_captures, leaf, leaf_captures,
                               event_captures, scope_path, event_path, load_dir,
                               checked["database_capture"], started_capture,
                               normalized_capture, report_capture, artifacts_capture,
                               static_captures, self_capture)
    return result


# --------------------------------------------------------------------------- TASK-029
GATE2_REQUEST_VERSION = "TASK-025-human-gate2-runtime-request-1.0"
GATE2_REQUEST_STATUS = "RUNTIME_GATE2_REQUEST_PREPARED"


def prepare_runtime_gate2_request(batch_dir, runtime_dir, request_id, *, scope_dir,
                                  event_relative, database_path) -> dict:
    """只读准备 Gate2 候审请求；复用一次真实 inspect，不保存决定或发布请求文件。"""
    result, _ = _prepare_runtime_gate2_captured(
        batch_dir, runtime_dir, request_id, scope_dir=scope_dir,
        event_relative=event_relative, database_path=database_path)
    return result


def _capture_approved_sources_031(batch_dir, runtime_dir, *, scope_dir, event_relative,
                                  database_path, initial_paths=None):
    """固定操作开始读数，供已批准装载的后续只读物化/动作共用；不调用核验或计算。"""
    batch_path, leaf, scope_path, event_path, batch_captures = (
        _resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative)
        if initial_paths is None else initial_paths)
    load_dir = _load_dir_for(leaf)
    _reject_reparse_chain(load_dir, "load_dir")
    if not load_dir.is_dir():
        _block("load_dir", "计算输出目录不存在")
    database_target = _check_database_target(
        database_path, batch_path=batch_path, leaf=leaf, scope_path=scope_path,
        event_path=event_path, load_dir=load_dir, require_new_leaf=False)

    # 在 inspect 之前固定全部消费对象；后续不以候选读数重建预期。
    self_capture = _capture_file(MODULE_PATH, "read.self")
    registry, _, leaf_captures = _load_stored_registry(leaf, allow_existing_scope=True)
    static_captures = {}
    _require_current_static_identity(registry, self_capture, static_captures)
    static_captures.update(_capture_static_028())
    event_captures = _capture_event_028(event_path)
    load_captures = {name: _capture_file(load_dir / name, f"read.gate2.{name}")
                     for name in APPROVED_LOAD_FILES}
    database_capture = _capture_file(database_target, "read.gate2.database")
    captures = dict(batch_path=batch_path, batch_captures=batch_captures, leaf=leaf,
                    leaf_captures=leaf_captures, event_captures=event_captures,
                    scope_path=scope_path, event_path=event_path, load_dir=load_dir,
                    database_capture=database_capture, started_capture=load_captures[STARTED_FILE],
                    normalized_capture=load_captures[NORMALIZED_FILE],
                    report_capture=load_captures[LOAD_REPORT_FILE],
                    artifacts_capture=load_captures[ARTIFACTS_FILE],
                    static_captures=static_captures, self_capture=self_capture)
    return registry, captures


def _prepare_runtime_gate2_captured(batch_dir, runtime_dir, request_id, *, scope_dir,
                                   event_relative, database_path, initial_paths=None):
    """共享物化和操作起始读数；内部调用方须以同一 captures 进行核心前及末端确认。"""
    _require_nonempty_str(request_id, "request_id")
    registry, captures = _capture_approved_sources_031(
        batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
        database_path=database_path, initial_paths=initial_paths)
    batch_path, leaf, scope_path, event_path = (captures[key] for key in
        ("batch_path", "leaf", "scope_path", "event_path"))
    batch_captures, leaf_captures = captures["batch_captures"], captures["leaf_captures"]
    event_captures = captures["event_captures"]
    load_dir, database_capture = captures["load_dir"], captures["database_capture"]
    database_target = Path(database_capture["path"])
    static_captures, self_capture = captures["static_captures"], captures["self_capture"]
    load_captures = {STARTED_FILE: captures["started_capture"],
                     NORMALIZED_FILE: captures["normalized_capture"],
                     LOAD_REPORT_FILE: captures["report_capture"],
                     ARTIFACTS_FILE: captures["artifacts_capture"]}
    inspected = inspect_gate1_approved_load(
        batch_path, leaf, scope_dir=scope_path, event_relative=event_relative,
        database_path=database_target)
    _require_closed_keys(inspected, APPROVED_LOAD_KEYS, "approved_load")
    if inspected["status"] != APPROVED_LOAD_STATUS:
        _block("approved_load.status", "必须是已核验的 RT_NORMALIZED")

    artifacts = _parse_json_object(load_captures[ARTIFACTS_FILE]["bytes"], ARTIFACTS_FILE)
    if canonical_json_bytes(artifacts) != canonical_json_bytes(inspected["artifacts"]):
        _block(ARTIFACTS_FILE, "起始对象与本次 inspect 实读核验结果不一致")
    # 把 inspect 的实际绑定闭合到本窗口起始字节，包括未列入十材料的 context。
    for key, capture in (
            ("registry_file_sha256", leaf_captures["registry"]),
            ("gate1_record_file_sha256", event_captures["snapshots/decision_result.json"]),
            ("started_file_sha256", load_captures[STARTED_FILE]),
            ("normalized_file_sha256", load_captures[NORMALIZED_FILE]),
            ("load_report_file_sha256", load_captures[LOAD_REPORT_FILE])):
        if artifacts[key] != capture["file_sha256"]:
            _block(key, "inspect 绑定与本窗口起始文件字节不一致")
    if artifacts["database"]["file_sha256"] != database_capture["file_sha256"] \
            or artifacts["database"]["byte_size"] != database_capture["byte_size"]:
        _block(DATABASE_NAME, "inspect 数据库绑定与起始字节不一致")
    context = _require_closed_keys(
        _parse_json_object(event_captures[CONTEXT_FILE]["bytes"], CONTEXT_FILE),
        CONTEXT_KEYS, "context")
    _require_closed_keys(context["request"], REQUEST_KEYS, "context.request")
    decision = _require_closed_keys(_parse_json_object(
        event_captures["snapshots/decision_result.json"]["bytes"], DECISION_RESULT_FILE),
        ("record", "record_fingerprint"), DECISION_RESULT_FILE)
    record = _require_closed_keys(decision["record"], RECORD_KEYS_027, "record")
    started = _require_closed_keys(
        _parse_json_object(load_captures[STARTED_FILE]["bytes"], STARTED_FILE),
        STARTED_KEYS, "started")
    _require_closed_keys(started["bindings"], STARTED_BINDING_KEYS, "started.bindings")
    binding = registry["run_binding"]
    if record["gate"] != "GATE1" or record["decision"] != "APPROVE" \
            or record["actor"]["actor_kind"] != ACTOR_KIND_HUMAN:
        _block("record", "必须是已核验的 HUMAN_DECLARED Gate1 APPROVE 完整记录")
    if record["batch_id"] != registry["batch_id"] \
            or inspected["batch_id"] != registry["batch_id"]:
        _block("record.batch_id", "Gate1/登记/装载批次不一致")
    for field, other in (("record.binding.run_binding", record["binding"]["run_binding"]),
                         ("started.bindings.run_binding", started["bindings"]["run_binding"])):
        if canonical_json_bytes(other) != canonical_json_bytes(binding):
            _block(field, "共享六项运行绑定不一致")
    if fingerprint(record) != artifacts["gate1_record_fingerprint"] \
            or decision["record_fingerprint"] != artifacts["gate1_record_fingerprint"]:
        _block("record_fingerprint", "完整 Gate1 记录与 inspect 实际绑定不一致")
    evidence = copy.deepcopy(context["request"]["evidence"])
    _require_closed_keys(evidence, EVIDENCE_KEYS, "evidence")
    evidence["code_manifest"] = copy.deepcopy(registry["code_manifest"])
    evidence["rules_manifest"] = copy.deepcopy(registry["rules_manifest"])

    mapping = {
        "registry/runtime_registry.json": leaf_captures["registry"],
        "registry/runtime_registry_readback.json": leaf_captures["readback"],
        "gate1/decision_result.json": event_captures["snapshots/decision_result.json"],
        "source/batch_manifest.json": batch_captures["batch_manifest.json"],
        "source/quality_report.json": batch_captures[QUALITY_RELATIVE],
        "load/started.json": load_captures[STARTED_FILE],
        "normalized/normalized.json": load_captures[NORMALIZED_FILE],
        "load/load_report.json": load_captures[LOAD_REPORT_FILE],
        "load/artifacts.json": load_captures[ARTIFACTS_FILE],
        "sqlite/runtime.sqlite3": database_capture,
    }
    files = [{"relative": relative, "file_sha256": capture["file_sha256"],
              "byte_size": capture["byte_size"]}
             for relative, capture in sorted(mapping.items(), key=lambda item: item[0].encode("utf-8"))]
    materials = {"gate": "GATE2", "batch_id": registry["batch_id"],
                 "run_binding": copy.deepcopy(binding),
                 "contract_binding": copy.deepcopy(registry["contract"]), "files": files,
                 "quality": {"status": "OK", "structural_blockers": [],
                             "quality_blockers": [], "verification_failures": []}}
    materials["materials_fingerprint"] = fingerprint(materials)
    expectations = {
        "expected_batch_id": registry["batch_id"], "expected_gate": "GATE2",
        "expected_request_id": request_id,
        "expected_materials_fingerprint": materials["materials_fingerprint"],
        "expected_files": {item["relative"]: item["file_sha256"] for item in files},
        "expected_contract": {key: registry["contract"][key] for key in
                              ("contract_version", "contract_file_sha256")},
        "expected_run_binding": copy.deepcopy(binding),
        "expected_prior_gate1": {"gate": record["gate"], "batch_id": record["batch_id"],
                                 "event_id": record["event_id"],
                                 "record_fingerprint": decision["record_fingerprint"],
                                 "run_binding": copy.deepcopy(binding)},
    }
    request = {"request_version": GATE2_REQUEST_VERSION, "status": GATE2_REQUEST_STATUS,
               "materials": materials, "expectations": expectations, "evidence": evidence,
               "boundaries": {key: False for key in BOUNDARY_KEYS}}
    result = copy.deepcopy({"request": request, "request_sha256": fingerprint(request)})
    _confirm_approved_terminal(**captures)
    return result, captures


# --------------------------------------------------------------------------- TASK-030
GATE2_RECORDS_ROOT = DATA_ROOT / "human_gate_decision_records" / "gate2"
GATE2_CONTEXT_VERSION = "TASK-030-runtime-gate2-context-1.0"
GATE2_RECEIPT_VERSION = "TASK-030-runtime-gate2-receipt-1.0"
GATE2_FAILURE_VERSION = "TASK-030-runtime-gate2-failure-1.0"
GATE2_WRAPPER_VERSION = "TASK-020-human-gate-decision-record-wrapper-1.1"
GATE2_CONTEXT_KEYS = ("context_version", "batch_id", "source_batch_relative", "runtime_relative",
                     "gate1_scope_relative", "gate1_event_relative", "gate2_scope_relative",
                     "event_relative", "database_relative", "registry_file_sha256", "request",
                     "prior_history", "store_result", "boundaries")
GATE2_RECEIPT_KEYS = ("receipt_version", "batch_id", "event_relative", "gate2_scope_relative",
                     "context_file_sha256", "snapshots_manifest_file_sha256", "record_fingerprint",
                     "registry_file_sha256", "boundaries")
GATE2_FAILURE_KEYS = ("failure_version", "stage", "field", "reason", "cause_chain")


def _require_equivalent_030(value, expected, field):
    try:
        equal = canonical_json_bytes(value) == canonical_json_bytes(expected)
    except (TypeError, ValueError) as exc:
        raise RuntimeGate1Blocked(field, f"不是合法规范 JSON：{exc}") from exc
    if not equal:
        _block(field, "与本次独立实读预期不一致")


def _gate2_paths_030(initial_paths, target, *, saving):
    batch_path, leaf, gate1_scope, gate1_event, _ = initial_paths
    _require_descendant(gate1_scope, GATE1_RECORDS_ROOT, "scope_dir")
    suffix = gate1_scope.relative_to(GATE1_RECORDS_ROOT)
    scope = GATE2_RECORDS_ROOT / suffix
    event = scope / "event_0001"
    field = "event_dir" if saving else "gate2_event_relative"
    if saving:
        if not isinstance(target, (str, os.PathLike)):
            _block(field, "必须是路径")
        raw = Path(target)
    else:
        _require_nonempty_str(target, field)
        if target.startswith("/") or ":" in target:
            _block(field, "必须是项目相对路径")
        raw = PROJECT_ROOT / target
    _reject_reparse_chain(raw, field)
    _reject_reparse_chain(scope, "gate2_scope")
    if raw.resolve() != event or (not saving and raw != event):
        _block(field, f"只接受固定 Gate2 事件 {_project_relative(event)}")
    _require_descendant(scope, GATE2_RECORDS_ROOT, "gate2_scope")
    if saving and scope.exists():
        _block("gate2_scope", "Gate2 scope 必须从未存在（含空目录）")
    lock_path = leaf.with_name(leaf.name + ".gate2.lock")
    _reject_reparse_chain(lock_path, "gate2_lock")
    if lock_path.exists():
        _block("gate2_lock", "Gate2 技术锁已存在，保持原件")
    return scope, event, lock_path


def _gate2_history_030(captures, scope):
    decision = _parse_json_object(
        captures["event_captures"]["snapshots/decision_result.json"]["bytes"],
        "gate1.decision_result")
    wrapper = {"wrapper_version": GATE2_WRAPPER_VERSION,
               "record_fingerprint": decision["record_fingerprint"],
               "record": copy.deepcopy(decision["record"])}
    return {"declared_complete": True,
            "declared_scope": (f"GATE2_SCOPE:{_project_relative(scope)}|BOUND_GATE1:"
                               f"{_project_relative(captures['event_path'])}"),
            "records": [wrapper]}


def _check_gate2_submission_030(submission, request, history):
    value = _require_closed_keys(submission, SUBMISSION_KEYS_027, "submission")
    if value["gate"] != "GATE2":
        _block("submission.gate", "必须为 GATE2")
    if value["batch_id"] != request["materials"]["batch_id"]:
        _block("submission.batch_id", "与当前批次不一致")
    binding = _require_closed_keys(value["request_binding"], REQUEST_BINDING_KEYS_027,
                                   "submission.request_binding")
    for key, expected in (("request_id", request["expectations"]["expected_request_id"]),
                          ("materials_binding", request["materials"]["materials_fingerprint"])):
        _require_equivalent_030(binding[key], expected, f"submission.request_binding.{key}")
    _require_equivalent_030(value["prior_decision_binding"], history["records"][0],
                            "submission.prior_decision_binding")
    # 人类字段的协议校验留给真实 P1；不替换提交、不预调用核心。


def _confirm_gate2_owned_lock_030(lock):
    path = lock["path"]
    _reject_reparse_chain(path, "gate2_lock")
    _require_fixed_members(path, [LOCK_FILE], "gate2_lock")
    if _path_identity(path, "gate2_lock") != lock["dir_identity"] \
            or _path_identity(path / LOCK_FILE, "gate2_lock") != lock["file_identity"]:
        _block("gate2_lock", "锁身份已变化，保留替代件")
    _recheck_capture({"path": str(path / LOCK_FILE), "bytes": lock["buffer"],
                      "file_sha256": _sha_bytes(lock["buffer"]),
                      "byte_size": len(lock["buffer"])}, "gate2_lock")


def _release_gate2_lock_030(lock):
    """释放边界不得让次错误遮蔽主错误；既有共享身份核验逻辑不变。"""
    try:
        return _release_own_lock(lock)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def _make_gate2_event_030(scope, event):
    missing, parent = [], scope.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for path in reversed(missing):
        _reject_reparse_chain(path, "gate2_scope.parent")
        try:
            os.mkdir(path)
        except FileExistsError:
            if not path.is_dir():
                _block("gate2_scope.parent", "父命名空间不是目录")
        _reject_reparse_chain(path, "gate2_scope.parent")
    _reject_reparse_chain(scope, "gate2_scope")
    try:
        os.mkdir(scope)
        os.mkdir(event)
    except FileExistsError as exc:
        raise RuntimeGate1Blocked("gate2_scope", "独占建立被拒绝；不覆盖既有目录") from exc


def _confirm_gate2_terminal_030(captures, scope, event, gate2_captures, lock_path):
    _confirm_approved_terminal(**captures)
    _reject_reparse_chain(scope, "gate2_scope")
    _reject_reparse_chain(event, "gate2_event")
    _require_fixed_members(scope, [event.name], "gate2_scope")
    _require_fixed_members(event, EVENT_FILES, "gate2_event")
    _require_fixed_members(event / SNAPSHOT_DIR, SNAPSHOT_FILES, "gate2_snapshots")
    for relative, capture in gate2_captures.items():
        _recheck_capture(capture, f"gate2.{relative}")
    _reject_reparse_chain(lock_path, "gate2_lock")
    if lock_path.exists():
        _block("gate2_lock", "末端出现技术锁")


def _write_gate2_failure_030(event, stage, primary):
    payload = {"failure_version": GATE2_FAILURE_VERSION, "stage": stage,
               "field": getattr(primary, "field", None),
               "reason": getattr(primary, "reason", str(primary)),
               "cause_chain": _cause_chain(primary) + list(getattr(primary, "secondary_errors", []))}
    _write_exclusive(event / FAILURE_FILE, _payload_bytes(payload), "write.gate2.failure")


def save_runtime_gate2_decision(batch_dir, runtime_dir, request_id, submission, event_dir, *,
                                scope_dir, event_relative, database_path) -> dict:
    """保存固定单个 Gate2 决定；APPROVE/HOLD 均不产生运行许可。"""
    stage, lock, release_attempted, event = "paths", None, False, None
    owned_event = False
    try:
        _require_nonempty_str(request_id, "request_id")
        value = copy.deepcopy(_require_object(submission, "submission"))
        initial = _resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative)
        scope, event, lock_path = _gate2_paths_030(initial, event_dir, saving=True)
        load_dir = _load_dir_for(initial[1])
        database = _check_database_target(database_path, batch_path=initial[0], leaf=initial[1],
            scope_path=initial[2], event_path=initial[3], load_dir=load_dir, require_new_leaf=False)
        for other in (initial[0], database.parent, initial[1], load_dir):
            if _is_ancestor(scope, other) or _is_ancestor(other, scope) or scope == other:
                _block("gate2_scope", "与来源/数据库/登记/装载重叠")
        stage = "gate2_lock"
        lock = _acquire_lock(initial[1], _project_relative(event), lock_path=lock_path)
        stage = "prepare_gate2"
        prepared, captures = _prepare_runtime_gate2_captured(
            batch_dir, runtime_dir, request_id, scope_dir=scope_dir,
            event_relative=event_relative, database_path=database, initial_paths=initial)
        request = prepared["request"]
        history = _gate2_history_030(captures, scope)
        stage = "bindings"
        _check_gate2_submission_030(value, request, history)
        members = _iter_dir(scope.parent, "gate2_scope.parent") if scope.parent.exists() else []
        if scope.name in members:
            _block("gate2_scope", "锁内枚举确认 scope 已存在")
        stage = "pre_store"
        _confirm_approved_terminal(**captures)
        _confirm_gate2_owned_lock_030(lock)
        stage = "event_create"
        _make_gate2_event_030(scope, event)
        owned_event = True
        stage = "store_save"
        consumed = [value, request["materials"], request["expectations"], history]
        before = [canonical_json_bytes(obj) for obj in consumed]
        store_result = _validate_store_result(_call_frozen_store_save(
            event / SNAPSHOT_DIR, *consumed), expected_status=STORE_STATUS_STORED)
        if before != [canonical_json_bytes(obj) for obj in consumed]:
            _block("inputs", "真实 store 调用修改了本次消费对象")
        stage = "bind_store"
        captured_snapshots = _capture_event_028(event, include_envelopes=False, reject_links=True)
        snapshots = {name: captured_snapshots[f"snapshots/{name}"] for name in SNAPSHOT_FILES}
        record, record_fp, manifest = _bind_store_snapshots(
            snapshots, store_result, value, request, history, gate="GATE2")
        context = {"context_version": GATE2_CONTEXT_VERSION, "batch_id": request["materials"]["batch_id"],
            "source_batch_relative": _project_relative(captures["batch_path"]),
            "runtime_relative": _project_relative(captures["leaf"]),
            "gate1_scope_relative": _project_relative(captures["scope_path"]),
            "gate1_event_relative": _project_relative(captures["event_path"]),
            "gate2_scope_relative": _project_relative(scope), "event_relative": _project_relative(event),
            "database_relative": _project_relative(database),
            "registry_file_sha256": captures["leaf_captures"]["registry"]["file_sha256"],
            "request": copy.deepcopy(request), "prior_history": copy.deepcopy(history),
            "store_result": copy.deepcopy(store_result),
            "boundaries": {key: False for key in DECISION_BOUNDARY_KEYS}}
        context_buffer = _payload_bytes(context)
        receipt = {"receipt_version": GATE2_RECEIPT_VERSION, "batch_id": context["batch_id"],
            "event_relative": context["event_relative"], "gate2_scope_relative": context["gate2_scope_relative"],
            "context_file_sha256": _sha_bytes(context_buffer),
            "snapshots_manifest_file_sha256": manifest["file_sha256"], "record_fingerprint": record_fp,
            "registry_file_sha256": context["registry_file_sha256"],
            "boundaries": {key: False for key in DECISION_BOUNDARY_KEYS}}
        gate2_captures = {f"snapshots/{name}": capture for name, capture in snapshots.items()}
        for name, buffer in ((CONTEXT_FILE, context_buffer), (RECEIPT_FILE, _payload_bytes(receipt))):
            stage = f"write.gate2.{name}"
            _write_exclusive(event / name, buffer, stage)
            readback = _capture_file(event / name, f"readback.gate2.{name}")
            if readback["bytes"] != buffer:
                _block(f"gate2.{name}", "读回与本次 writer 缓冲不一致")
            gate2_captures[name] = readback
        result = {"record": copy.deepcopy(record), "record_fingerprint": record_fp,
                  "event_relative": _project_relative(event)}
        stage = "release_gate2_lock"
        release_attempted = True
        release_error = _release_gate2_lock_030(lock)
        if release_error:
            raise RuntimeGate1Error(stage, release_error)
        stage = "final_gate2"
        _confirm_gate2_terminal_030(captures, scope, event, gate2_captures, lock_path)
        return result
    except Exception as exc:
        primary = exc
        if not isinstance(exc, (RuntimeGate1Blocked, RuntimeGate1Error)):
            primary = RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}")
            primary.__cause__ = exc
        if lock is not None and not release_attempted:
            release_error = _release_gate2_lock_030(lock)
            if release_error:
                _note_secondary(primary, release_error)
        try:
            if owned_event and event.is_dir():
                _write_gate2_failure_030(event, stage, primary)
        except Exception as diagnostic_error:
            _note_secondary(primary, f"{type(diagnostic_error).__name__}: {diagnostic_error}",
                            stage="failure_write")
        raise primary


def verify_runtime_gate2_decision(batch_dir, runtime_dir, *, scope_dir, event_relative,
                                  database_path, gate2_event_relative) -> dict:
    """只读恢复固定 Gate2 快照；不解释为 effective/allowed，也不写诊断。"""
    try:
        initial = _resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative)
        scope, event, lock_path = _gate2_paths_030(initial, gate2_event_relative, saving=False)
        if FAILURE_FILE in _iter_dir(event, "gate2_event"):
            failure = _require_closed_keys(_parse_json_object(
                _capture_file(event / FAILURE_FILE, "read.gate2.failure")["bytes"], "gate2.failure"),
                GATE2_FAILURE_KEYS, "gate2.failure")
            if failure["failure_version"] != GATE2_FAILURE_VERSION:
                _block("gate2.failure.failure_version", "失败诊断版本不符")
            for key in ("stage", "reason"):
                _require_nonempty_str(failure[key], f"gate2.failure.{key}")
            if failure["field"] is not None:
                _require_nonempty_str(failure["field"], "gate2.failure.field")
            for i, reason in enumerate(_require_list(failure["cause_chain"], "gate2.failure.cause_chain")):
                _require_nonempty_str(reason, f"gate2.failure.cause_chain[{i}]")
            _block("gate2.failure", failure["reason"])
        _require_fixed_members(scope, [event.name], "gate2_scope")
        _require_fixed_members(event, EVENT_FILES, "gate2_event")
        _require_fixed_members(event / SNAPSHOT_DIR, SNAPSHOT_FILES, "gate2_snapshots")
        gate2_captures = _capture_event_028(event, reject_links=True)
        context = _require_closed_keys(_parse_json_object(gate2_captures[CONTEXT_FILE]["bytes"],
            "gate2.context"), GATE2_CONTEXT_KEYS, "gate2.context")
        receipt = _require_closed_keys(_parse_json_object(gate2_captures[RECEIPT_FILE]["bytes"],
            "gate2.receipt"), GATE2_RECEIPT_KEYS, "gate2.receipt")
        _require_closed_keys(context["request"], REQUEST_KEYS, "gate2.context.request")
        _require_closed_keys(context["request"]["expectations"], EXPECTATIONS_KEYS,
                             "gate2.context.request.expectations")
        request_id = _require_nonempty_str(
            context["request"]["expectations"]["expected_request_id"], "gate2.request_id")
        prepared, captures = _prepare_runtime_gate2_captured(
            batch_dir, runtime_dir, request_id, scope_dir=scope_dir, event_relative=event_relative,
            database_path=database_path, initial_paths=initial)
        request, history = prepared["request"], _gate2_history_030(captures, scope)
        for payload, keys, prefix, version_key, version in (
                (context, GATE2_CONTEXT_KEYS, "gate2.context", "context_version", GATE2_CONTEXT_VERSION),
                (receipt, GATE2_RECEIPT_KEYS, "gate2.receipt", "receipt_version", GATE2_RECEIPT_VERSION)):
            _require_equivalent_030(payload[version_key], version, f"{prefix}.{version_key}")
            boundaries = _require_closed_keys(payload["boundaries"], DECISION_BOUNDARY_KEYS,
                                              f"{prefix}.boundaries")
            for key, value in boundaries.items():
                _require_bool_false(value, f"{prefix}.boundaries.{key}")
            for key, expected in (("batch_id", request["materials"]["batch_id"]),
                    ("event_relative", _project_relative(event)),
                    ("gate2_scope_relative", _project_relative(scope)),
                    ("registry_file_sha256", captures["leaf_captures"]["registry"]["file_sha256"])):
                _require_equivalent_030(payload[key], expected, f"{prefix}.{key}")
        for key, expected in (("source_batch_relative", _project_relative(captures["batch_path"])),
                ("runtime_relative", _project_relative(captures["leaf"])),
                ("gate1_scope_relative", _project_relative(captures["scope_path"])),
                ("gate1_event_relative", _project_relative(captures["event_path"])),
                ("database_relative", _project_relative(Path(captures["database_capture"]["path"])))):
            _require_equivalent_030(context[key], expected, f"gate2.context.{key}")
        _require_equivalent_030(context["request"], request, "gate2.context.request")
        _require_equivalent_030(context["prior_history"], history, "gate2.context.prior_history")
        _require_equivalent_030(receipt["context_file_sha256"],
                                gate2_captures[CONTEXT_FILE]["file_sha256"], "gate2.receipt.context_file_sha256")
        stored = _validate_store_result(context["store_result"], expected_status=STORE_STATUS_STORED)
        verified = _validate_store_result(_call_frozen_store_verify(event / SNAPSHOT_DIR),
                                          expected_status=STORE_STATUS_VERIFIED)
        _require_equivalent_030({k: v for k, v in stored.items() if k != "status"},
                                {k: v for k, v in verified.items() if k != "status"},
                                "gate2.store_result.stable_fields")
        snapshots = {name: gate2_captures[f"snapshots/{name}"] for name in SNAPSHOT_FILES}
        submission = _parse_json_object(snapshots["submission.json"]["bytes"], "gate2.submission")
        _check_gate2_submission_030(submission, request, history)
        record, record_fp, manifest = _bind_store_snapshots(
            snapshots, verified, submission, request, history, gate="GATE2")
        for key, expected in (("record_fingerprint", record_fp),
                               ("snapshots_manifest_file_sha256", manifest["file_sha256"])):
            _require_equivalent_030(receipt[key], expected, f"gate2.receipt.{key}")
        result = {"record": copy.deepcopy(record), "record_fingerprint": record_fp,
                  "event_relative": _project_relative(event)}
        _confirm_gate2_terminal_030(captures, scope, event, gate2_captures, lock_path)
        return result
    except OSError as exc:
        raise RuntimeGate1Error("verify.gate2", f"{type(exc).__name__}: {exc}") from exc


# --------------------------------------------------------------------------- TASK-031
SCREEN_CORE_RELATIVE = "scripts/screen_demo_sqlite.py"
SCREEN_CORE_SHA256 = "1b123766b57849c1d64a5a18cb504fbeb03f563bcd96b2de708586f19c9e71fe"
SCREEN_STAGE_VERSION = "TASK-031-approved-screen-1.0"
SCREEN_STARTED_VERSION = "TASK-031-approved-screen-start-1.0"
SCREEN_ARTIFACTS_VERSION = "TASK-031-approved-screen-artifacts-1.0"
SCREEN_FAILURE_VERSION = "TASK-031-approved-screen-failure-1.0"
SCREEN_REPORT_FILE = "screening_report.json"
SCREEN_FILES = (STARTED_FILE, SCREEN_REPORT_FILE, ARTIFACTS_FILE)
SCREEN_BOUNDARIES = ("crosscheck_recorded", "fact_packet_recorded", "human_initial_judgment_saved",
                     "ai_enabled", "audit_conclusion_formed", "identity_authenticated",
                     "source_authenticity_proven", "next_step_allowed")
SCREEN_STARTED_KEYS = ("started_version", "batch_id", "source_batch_relative", "runtime_relative",
                       "gate1_event_relative", "gate2_event_relative", "database_relative", "bindings")
SCREEN_BINDING_KEYS = ("registry_file_sha256", "gate2_record_file_sha256", "gate2_record_fingerprint",
                       "load_report_file_sha256", "run_binding")
SCREEN_ARTIFACTS_KEYS = ("artifacts_version", "batch_id", "run_binding_sha256", "registry_file_sha256",
                         "gate2_record_file_sha256", "gate2_record_fingerprint", "load_report_file_sha256",
                         "started_file_sha256", "report_file_sha256", "report_canonical_sha256", "database")
SCREEN_REPORT_KEYS = ("batch_status", "mode", "next_step_allowed", "rule_core_version", "rules",
                      "cutoff_date", "period", "database_path", "database_sha256_before",
                      "database_sha256_after", "database_unchanged", "read_only", "load_source",
                      "overall_reconciliation", "rule_hit_counts", "findings", "statistics", "limits")


def _load_frozen_screen_031():
    return _load_frozen_module(SCREEN_CORE_RELATIVE, SCREEN_CORE_SHA256, "frozen_screen_runtime_031")


def _screen_dir_031(leaf):
    path = leaf.with_name(leaf.name + ".screen")
    _reject_reparse_chain(path, "screen_dir")
    _require_descendant(path, RUNTIME_ROOT, "screen_dir")
    return path


def _screen_inputs_031(batch_dir, runtime_dir, *, scope_dir, event_relative, database_path,
                        gate2_event_relative, initial_paths=None):
    initial = (_resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative)
               if initial_paths is None else initial_paths)
    registry, sources = _capture_approved_sources_031(
        batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
        database_path=database_path, initial_paths=initial)
    scope, event, lock = _gate2_paths_030(initial, gate2_event_relative, saving=False)
    params = dict(scope_dir=scope_dir, event_relative=event_relative,
                  database_path=database_path, gate2_event_relative=gate2_event_relative)
    if FAILURE_FILE in _iter_dir(event, "gate2_event"):
        # 真实公共核验优先报告有效失败，避免半写封套遮蔽诊断。
        verify_runtime_gate2_decision(batch_dir, runtime_dir, **params)
        _block("gate2.failure", "失败现场不得作为筛查前提")
    _require_fixed_members(scope, [event.name], "gate2_scope")
    _require_fixed_members(event, EVENT_FILES, "gate2_event")
    _require_fixed_members(event / SNAPSHOT_DIR, SNAPSHOT_FILES, "gate2_snapshots")
    gate2_captures = _capture_event_028(event, reject_links=True)
    core_capture = sources["static_captures"]["project"][SCREEN_CORE_RELATIVE]
    if core_capture["file_sha256"] != SCREEN_CORE_SHA256:
        _block(SCREEN_CORE_RELATIVE, "与独立冻结预期不一致")
    verified = verify_runtime_gate2_decision(batch_dir, runtime_dir, **params)
    _require_closed_keys(verified, ("record", "record_fingerprint", "event_relative"), "gate2_verify")
    decision = _require_closed_keys(_parse_json_object(
        gate2_captures["snapshots/decision_result.json"]["bytes"], "gate2.decision_result"),
        ("record", "record_fingerprint"), "gate2.decision_result")
    _require_equivalent_030(decision, {k: verified[k] for k in ("record", "record_fingerprint")},
                            "gate2.decision_result")
    _require_equivalent_030(verified["event_relative"], _project_relative(event), "gate2.event_relative")
    record = _require_closed_keys(verified["record"], RECORD_KEYS_027, "gate2.record")
    for key, expected in (("gate", "GATE2"), ("decision", "APPROVE"),
                           ("batch_id", registry["batch_id"]), ("decision_source", "HUMAN_GATE_DECISION")):
        _require_equivalent_030(record[key], expected, f"gate2.record.{key}")
    actor = _require_closed_keys(record["actor"], ACTOR_KEYS_027, "gate2.record.actor")
    _require_equivalent_030(actor["actor_kind"], ACTOR_KIND_HUMAN, "gate2.record.actor.actor_kind")
    quality = _require_closed_keys(record["quality_summary"], ("status", "structural_blockers_count",
        "quality_blockers_count", "verification_failures_count"), "gate2.record.quality_summary")
    _require_equivalent_030(quality["status"], "OK", "gate2.record.quality_summary.status")
    for key in ("structural_blockers_count", "quality_blockers_count", "verification_failures_count"):
        if _require_nonneg_int(quality[key], f"gate2.record.quality_summary.{key}") != 0:
            _block(f"gate2.record.quality_summary.{key}", "本动作要求阻断/失败计数为0")
    binding = _require_closed_keys(record["binding"], RECORD_BINDING_KEYS_027, "gate2.record.binding")
    _require_equivalent_030(binding["run_binding"], registry["run_binding"], "gate2.record.run_binding")
    _require_equivalent_030(binding["contract_binding"], registry["contract"], "gate2.record.contract")
    prior = _parse_json_object(sources["event_captures"]["snapshots/decision_result.json"]["bytes"],
                               "gate1.decision_result")
    _require_equivalent_030(record["prior_gate1"], {"record_fingerprint": prior["record_fingerprint"],
        "event_id": prior["record"]["event_id"], "batch_id": registry["batch_id"], "gate": "GATE1",
        "decision": "APPROVE", "actor_kind": ACTOR_KIND_HUMAN}, "gate2.record.prior_gate1")
    report = _parse_json_object(sources["report_capture"]["bytes"], LOAD_REPORT_FILE)
    return dict(registry=registry, sources=sources, scope=scope, event=event, lock=lock,
                gate2_captures=gate2_captures, verified=verified, load_report=report)


def _confirm_screen_inputs_031(ctx):
    _confirm_gate2_terminal_030(ctx["sources"], ctx["scope"], ctx["event"],
                               ctx["gate2_captures"], ctx["lock"])


def _require_int_031(value, field):
    if type(value) is not int:
        _block(field, "必须是严格整数（bool/float不得冒充）")
    return value


def _screen_numbers_031(value, field, *, integers=False):
    """仅核对报告明确的金额/计数类型；不计算规则，不规范化来源原始cells。"""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "cells":
                continue
            child_field = f"{field}.{key}"
            is_amount = integers or key == "amounts_cents" or key.endswith("_cents")
            if key == "counts":
                for name, count in _require_object(child, child_field).items():
                    _require_nonneg_int(count, f"{child_field}.{name}")
            elif key == "count" or key.endswith("_count"):
                _require_nonneg_int(child, child_field)
            elif isinstance(child, (dict, list)):
                _screen_numbers_031(child, child_field, integers=is_amount)
            elif is_amount:
                _require_int_031(child, child_field)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _screen_numbers_031(child, f"{field}[{index}]", integers=integers)
    elif integers:
        _require_int_031(value, field)


def _validate_screen_report_031(report, ctx, core):
    value = _require_closed_keys(report, SCREEN_REPORT_KEYS, "screen_report")
    sources, load, registry = ctx["sources"], ctx["load_report"], ctx["registry"]
    database = sources["database_capture"]
    for key, expected in (("batch_status", "DEV_RULES_COMPUTED"), ("mode", "DEVELOPMENT_TEST_ONLY"),
        ("next_step_allowed", False), ("rule_core_version", "TASK-006-rule-core-1.1"),
        ("cutoff_date", "2026-09-30"), ("database_path", database["path"]),
        ("database_sha256_before", database["file_sha256"]),
        ("database_sha256_after", database["file_sha256"]), ("database_unchanged", True)):
        _require_equivalent_030(value[key], expected, f"screen_report.{key}")
    for key in ("database_sha256_before", "database_sha256_after"):
        _require_hash(value[key], f"screen_report.{key}")
    _require_equivalent_030(value["period"], {"period_start": "2026-09-01", "period_end": "2026-09-30",
                                             "range_ok": True}, "screen_report.period")
    _require_equivalent_030(value["read_only"], {"uri_mode": "ro", "query_only": 1}, "screen_report.read_only")
    metadata = {key: load["run_metadata"][key] for key in ("mode", "next_step_allowed", "batch_status",
        "store_version", "schema_version", "input_sha256", "normalized_payload_sha256", "created_at_utc")}
    metadata.update(store_script_sha256=sources["static_captures"]["sqlite_core"]["file_sha256"],
                    schema_sha256=sources["static_captures"]["schema"]["file_sha256"])
    expected_load = {key: load[key] for key in ("batch_status", "store_version", "schema_version",
                                               "normalized_payload_sha256")}
    expected_load.update(input_sha256=load["source"]["input_sha256"], database_sha256=database["file_sha256"],
                         run_metadata=metadata)
    _require_equivalent_030(value["load_source"], expected_load, "screen_report.load_source")
    reconciliation = _require_closed_keys(value["overall_reconciliation"], ("unit", "settled_pay_master_total",
        "settled_refund_master_total", "master_net", "known_payable_link_net", "missing_payable_link_net",
        "missing_payable_link_detail", "master_net_equals_known_plus_missing", "matches_load_report"),
        "screen_report.overall_reconciliation")
    for key in ("settled_pay_master_total", "settled_refund_master_total", "master_net",
                "known_payable_link_net", "missing_payable_link_net"):
        _require_int_031(reconciliation[key], f"screen_report.overall_reconciliation.{key}")
        _require_equivalent_030(reconciliation[key], load[key], f"screen_report.overall_reconciliation.{key}")
    detail = _require_closed_keys(reconciliation["missing_payable_link_detail"], ("empty_ap_id", "ap_id_not_in_ledger"),
                                  "screen_report.overall_reconciliation.missing_payable_link_detail")
    for key, amount in detail.items():
        _require_int_031(amount, f"screen_report.overall_reconciliation.missing_payable_link_detail.{key}")
    _require_equivalent_030(detail, load["missing_payable_link_detail"], "screen_report.missing_detail")
    for key in ("master_net_equals_known_plus_missing", "matches_load_report"):
        _require_equivalent_030(reconciliation[key], True, f"screen_report.overall_reconciliation.{key}")
    _require_equivalent_030(reconciliation["unit"], "cents", "screen_report.overall_reconciliation.unit")
    findings = _require_list(value["findings"], "screen_report.findings")
    counts, identifiers, r02 = {key: 0 for key in RULE_IDS}, set(), 0
    for index, finding in enumerate(findings):
        field = f"screen_report.findings[{index}]"
        finding = _require_object(finding, field)
        rule = _require_nonempty_str(finding.get("rule_id"), field + ".rule_id")
        if rule not in RULE_IDS:
            _block(field + ".rule_id", "未知规则")
        counts[rule] += 1
        key = _require_object(finding.get("hit_key"), field + ".hit_key")
        if key.get("rule_id") != rule:
            _block(field + ".hit_key.rule_id", "线索标识规则矛盾")
        marker = canonical_json_bytes(key)
        if marker in identifiers:
            _block(field + ".hit_key", "线索标识重复")
        identifiers.add(marker)
        amounts = _require_object(finding.get("amounts_cents"), field + ".amounts_cents")
        _screen_numbers_031(amounts, field + ".amounts_cents", integers=True)
        if rule == "R02":
            r02 += _require_int_031(amounts.get("overpayment"), field + ".amounts_cents.overpayment")
    rules = _require_closed_keys(value["rules"], RULE_IDS, "screen_report.rules")
    hit_counts = _require_closed_keys(value["rule_hit_counts"], (*RULE_IDS, "total"), "screen_report.rule_hit_counts")
    for declaration in registry["rules_manifest"]["entries"]:
        rule = declaration["rule_id"]
        entry = _require_closed_keys(rules[rule], ("rule_version", "sql_path", "sql_sha256", "hit_count"),
                                     f"screen_report.rules.{rule}")
        _require_hash(entry["sql_sha256"], f"screen_report.rules.{rule}.sql_sha256")
        _require_equivalent_030(entry["rule_version"], declaration["rule_version"], f"screen_report.rules.{rule}.rule_version")
        _require_equivalent_030(entry["sql_path"], str(PROJECT_ROOT / declaration["relative"]), f"screen_report.rules.{rule}.sql_path")
        _require_equivalent_030(entry["sql_sha256"], declaration["file_sha256"], f"screen_report.rules.{rule}.sql_sha256")
        for count, field in ((entry["hit_count"], f"screen_report.rules.{rule}.hit_count"),
                              (hit_counts[rule], f"screen_report.rule_hit_counts.{rule}")):
            if _require_nonneg_int(count, field) != counts[rule]:
                _block(field, "与实际findings条数不一致")
    if _require_nonneg_int(hit_counts["total"], "screen_report.rule_hit_counts.total") != len(findings):
        _block("screen_report.rule_hit_counts.total", "与线索总数不一致")
    stats = _require_closed_keys(value["statistics"], ("involved_payments", "r02_overpayment_total_cents",
        "r02_overpayment_basis", "rule_amounts_not_summed_as_loss"), "screen_report.statistics")
    _require_int_031(stats["r02_overpayment_total_cents"], "screen_report.statistics.r02_overpayment_total_cents")
    _require_equivalent_030(stats["r02_overpayment_total_cents"], r02, "screen_report.statistics.r02_overpayment_total_cents")
    involved = _require_closed_keys(stats["involved_payments"], ("count", "payment_ids", "settled_amount_cents", "note"),
                                    "screen_report.statistics.involved_payments")
    ids = _require_list(involved["payment_ids"], "screen_report.statistics.involved_payments.payment_ids")
    for index, item in enumerate(ids):
        _require_nonempty_str(item, f"screen_report.statistics.involved_payments.payment_ids[{index}]")
    if _require_nonneg_int(involved["count"], "screen_report.statistics.involved_payments.count") != len(ids) or len(set(ids)) != len(ids):
        _block("screen_report.statistics.involved_payments.count", "唯一付款标识和计数不一致")
    _require_equivalent_030(stats["rule_amounts_not_summed_as_loss"], True, "screen_report.statistics.rule_amounts_not_summed_as_loss")
    _screen_numbers_031(value, "screen_report")
    _require_equivalent_030(value["limits"], core.SCOPE_LIMITS, "screen_report.limits")
    return value


def _screen_result_031(ctx, artifacts):
    return {"stage_version": SCREEN_STAGE_VERSION, "status": "RT_RULE_SCREEN_RECORDED",
            "batch_id": ctx["registry"]["batch_id"], "run_binding_sha256": fingerprint(ctx["registry"]["run_binding"]),
            "artifacts": copy.deepcopy(artifacts), "boundaries": {key: False for key in SCREEN_BOUNDARIES}}


def _confirm_screen_terminal_031(ctx, output, captures):
    _confirm_screen_inputs_031(ctx)
    _reject_reparse_chain(output, "screen_dir")
    _require_fixed_members(output, SCREEN_FILES, "screen_dir")
    for name, capture in captures.items():
        _recheck_capture(capture, f"screen.{name}")


def run_gate2_approved_screen(batch_dir, runtime_dir, *, scope_dir, event_relative,
                              database_path, gate2_event_relative):
    """仅本次明确调用、当批已核验Gate2 APPROVE，单次执行冻结规则核心。"""
    output, created, stage = None, False, "screen.paths"
    try:
        initial = _resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative)
        output = _screen_dir_031(initial[1])
        if output.exists():
            _block("screen_dir", "输出目录必须从未存在（含空目录/文件）")
        ctx = _screen_inputs_031(batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
            database_path=database_path, gate2_event_relative=gate2_event_relative, initial_paths=initial)
        core = _load_frozen_screen_031()
        stage = "screen.pre_core"
        _confirm_screen_inputs_031(ctx)
        stage = "screen.mkdir"
        try:
            os.mkdir(output)
        except FileExistsError as exc:
            raise RuntimeGate1Blocked("screen_dir", "独占建立被拒绝") from exc
        created = True
        stage = "screen.core"
        before = fingerprint(ctx["load_report"])
        report = _call_frozen_entry(core, "screen_sqlite", ctx["sources"]["database_capture"]["path"],
                                    ctx["load_report"], cutoff_date="2026-09-30")
        if fingerprint(ctx["load_report"]) != before:
            _block("load_report", "真实筛查调用修改了同一消费引用")
        _recheck_capture(ctx["sources"]["database_capture"], DATABASE_NAME)
        stage = "screen.report"
        _validate_screen_report_031(report, ctx, core)
        sources = ctx["sources"]
        started = {"started_version": SCREEN_STARTED_VERSION, "batch_id": ctx["registry"]["batch_id"],
            "source_batch_relative": _project_relative(sources["batch_path"]), "runtime_relative": _project_relative(sources["leaf"]),
            "gate1_event_relative": _project_relative(sources["event_path"]), "gate2_event_relative": _project_relative(ctx["event"]),
            "database_relative": _project_relative(Path(sources["database_capture"]["path"])),
            "bindings": {"registry_file_sha256": sources["leaf_captures"]["registry"]["file_sha256"],
                "gate2_record_file_sha256": ctx["gate2_captures"]["snapshots/decision_result.json"]["file_sha256"],
                "gate2_record_fingerprint": ctx["verified"]["record_fingerprint"],
                "load_report_file_sha256": sources["report_capture"]["file_sha256"],
                "run_binding": copy.deepcopy(ctx["registry"]["run_binding"])}}
        buffers = {STARTED_FILE: _payload_bytes(started), SCREEN_REPORT_FILE: _payload_bytes(report)}
        artifacts = {"artifacts_version": SCREEN_ARTIFACTS_VERSION, "batch_id": started["batch_id"],
            "run_binding_sha256": fingerprint(ctx["registry"]["run_binding"]),
            **{key: value for key, value in started["bindings"].items() if key != "run_binding"},
            "started_file_sha256": _sha_bytes(buffers[STARTED_FILE]),
            "report_file_sha256": _sha_bytes(buffers[SCREEN_REPORT_FILE]), "report_canonical_sha256": fingerprint(report),
            "database": {"relative": started["database_relative"], "file_sha256": sources["database_capture"]["file_sha256"],
                          "byte_size": sources["database_capture"]["byte_size"]}}
        buffers[ARTIFACTS_FILE] = _payload_bytes(artifacts)
        captures = {}
        for name, buffer in buffers.items():
            stage = f"write.screen.{name}"
            _write_exclusive(output / name, buffer, stage)
            capture = _capture_file(output / name, f"readback.screen.{name}")
            if capture["bytes"] != buffer:
                _block(f"screen.{name}", "读回与本次writer缓冲不一致")
            captures[name] = capture
        result = _screen_result_031(ctx, artifacts)
        stage = "screen.final"
        _confirm_screen_terminal_031(ctx, output, captures)
        return result
    except Exception as exc:
        primary = exc
        if not isinstance(exc, (RuntimeGate1Blocked, RuntimeGate1Error)):
            primary = RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}")
            primary.__cause__ = exc
        if created:
            failure = {"failure_version": SCREEN_FAILURE_VERSION, "kind": "BLOCKED" if isinstance(primary, RuntimeGate1Blocked) else "ERROR",
                "stage": stage, "field": getattr(primary, "field", None), "reason": getattr(primary, "reason", str(primary)),
                "cause_chain": _cause_chain(primary)}
            try:
                _write_exclusive(output / FAILURE_FILE, _payload_bytes(failure), "write.screen.failure")
            except Exception as secondary:
                _note_secondary(primary, f"{type(secondary).__name__}: {secondary}", stage="failure_write")
        raise primary


def inspect_gate2_approved_screen(batch_dir, runtime_dir, *, scope_dir, event_relative,
                                  database_path, gate2_event_relative):
    """只读恢复报告和已核验绑定；绝不重新运行SQL规则或写诊断。"""
    try:
        initial = _resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative)
        output = _screen_dir_031(initial[1])
        if FAILURE_FILE in _iter_dir(output, "screen_dir"):
            failure = _require_closed_keys(_parse_json_object(_capture_file(output / FAILURE_FILE,
                "read.screen.failure")["bytes"], "screen.failure"), FAILURE_KEYS_028, "screen.failure")
            _require_equivalent_030(failure["failure_version"], SCREEN_FAILURE_VERSION, "screen.failure.failure_version")
            if failure["kind"] not in FAILURE_KINDS:
                _block("screen.failure.kind", "必须为BLOCKED/ERROR")
            for key in ("stage", "reason"):
                _require_nonempty_str(failure[key], f"screen.failure.{key}")
            if failure["field"] is not None:
                _require_nonempty_str(failure["field"], "screen.failure.field")
            for index, reason in enumerate(_require_list(failure["cause_chain"], "screen.failure.cause_chain")):
                _require_nonempty_str(reason, f"screen.failure.cause_chain[{index}]")
            if failure["kind"] == "BLOCKED":
                raise RuntimeGate1Blocked(f"screen.failure.{failure['field']}", failure["reason"])
            raise RuntimeGate1Error(f"screen.failure.{failure['stage']}", failure["reason"])
        _require_fixed_members(output, SCREEN_FILES, "screen_dir")
        captures = {}
        for name in SCREEN_FILES:
            _reject_reparse_chain(output / name, f"screen.{name}")
            captures[name] = _capture_file(output / name, f"read.screen.{name}")
        ctx = _screen_inputs_031(batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
            database_path=database_path, gate2_event_relative=gate2_event_relative, initial_paths=initial)
        started = _require_closed_keys(_parse_json_object(captures[STARTED_FILE]["bytes"], "screen.started"),
                                       SCREEN_STARTED_KEYS, "screen.started")
        artifacts = _require_closed_keys(_parse_json_object(captures[ARTIFACTS_FILE]["bytes"], "screen.artifacts"),
                                         SCREEN_ARTIFACTS_KEYS, "screen.artifacts")
        report = _parse_json_object(captures[SCREEN_REPORT_FILE]["bytes"], "screen.report")
        core = _load_frozen_screen_031()
        _validate_screen_report_031(report, ctx, core)
        sources = ctx["sources"]
        binding = _require_closed_keys(started["bindings"], SCREEN_BINDING_KEYS, "screen.started.bindings")
        expected_binding = {"registry_file_sha256": sources["leaf_captures"]["registry"]["file_sha256"],
            "gate2_record_file_sha256": ctx["gate2_captures"]["snapshots/decision_result.json"]["file_sha256"],
            "gate2_record_fingerprint": ctx["verified"]["record_fingerprint"],
            "load_report_file_sha256": sources["report_capture"]["file_sha256"], "run_binding": ctx["registry"]["run_binding"]}
        _require_equivalent_030(binding, expected_binding, "screen.started.bindings")
        for key, expected in (("started_version", SCREEN_STARTED_VERSION), ("batch_id", ctx["registry"]["batch_id"]),
            ("source_batch_relative", _project_relative(sources["batch_path"])), ("runtime_relative", _project_relative(sources["leaf"])),
            ("gate1_event_relative", _project_relative(sources["event_path"])), ("gate2_event_relative", _project_relative(ctx["event"])),
            ("database_relative", _project_relative(Path(sources["database_capture"]["path"])))):
            _require_equivalent_030(started[key], expected, f"screen.started.{key}")
        expected_artifacts = {"artifacts_version": SCREEN_ARTIFACTS_VERSION, "batch_id": started["batch_id"],
            "run_binding_sha256": fingerprint(ctx["registry"]["run_binding"]),
            **{key: value for key, value in expected_binding.items() if key != "run_binding"},
            "started_file_sha256": captures[STARTED_FILE]["file_sha256"],
            "report_file_sha256": captures[SCREEN_REPORT_FILE]["file_sha256"], "report_canonical_sha256": fingerprint(report),
            "database": {"relative": started["database_relative"], "file_sha256": sources["database_capture"]["file_sha256"],
                          "byte_size": sources["database_capture"]["byte_size"]}}
        database = _require_closed_keys(artifacts["database"], ARTIFACTS_DATABASE_KEYS, "screen.artifacts.database")
        _require_nonneg_int(database["byte_size"], "screen.artifacts.database.byte_size")
        for key in SCREEN_ARTIFACTS_KEYS:
            if key.endswith("sha256") or key.endswith("fingerprint"):
                _require_hash(artifacts[key], f"screen.artifacts.{key}")
        _require_equivalent_030(artifacts, expected_artifacts, "screen.artifacts")
        result = _screen_result_031(ctx, artifacts)
        _confirm_screen_terminal_031(ctx, output, captures)
        return result
    except OSError as exc:
        raise RuntimeGate1Error("inspect.screen", f"{type(exc).__name__}: {exc}") from exc


# --------------------------------------------------------------------------- TASK-032
CROSSCHECK_CORE_RELATIVE = "scripts/crosscheck_demo_rules.py"
CROSSCHECK_CORE_SHA256 = "8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2"
CROSSCHECK_STAGE_VERSION = "TASK-032-rule-crosscheck-1.0"
CROSSCHECK_STARTED_VERSION = "TASK-032-rule-crosscheck-start-1.0"
CROSSCHECK_ARTIFACTS_VERSION = "TASK-032-rule-crosscheck-artifacts-1.0"
CROSSCHECK_FAILURE_VERSION = "TASK-032-rule-crosscheck-failure-1.0"
CROSSCHECK_REPORT_FILE = "crosscheck_report.json"
CROSSCHECK_FILES = (STARTED_FILE, CROSSCHECK_REPORT_FILE, ARTIFACTS_FILE)
CROSSCHECK_BOUNDARIES = tuple(key for key in SCREEN_BOUNDARIES if key != "crosscheck_recorded")
CROSSCHECK_BINDING_KEYS = ("registry_file_sha256", "gate2_record_file_sha256", "gate2_record_fingerprint",
    "normalized_file_sha256", "normalized_payload_sha256", "screening_report_file_sha256",
    "screening_report_canonical_sha256", "screening_artifacts_file_sha256", "run_binding")
CROSSCHECK_ARTIFACTS_KEYS = ("artifacts_version", "batch_id", "run_binding_sha256",
    *CROSSCHECK_BINDING_KEYS[:-1], "started_file_sha256", "report_file_sha256", "report_canonical_sha256", "database")
CROSSCHECK_REPORT_KEYS = ("crosscheck_version", "batch_status", "matched", "mode", "next_step_allowed",
    "period", "cutoff_date", "input_source_sha256", "normalized_payload_sha256", "screening_report_sha256",
    "rule_core_version_checked", "rule_recomputed_counts", "recomputed_facts", "observed_summary",
    "comparison", "differences", "method", "limits")
CROSSCHECK_DIMENSIONS = ("hit_keys", "amounts_cents", "related_ids", "refund_facts", "rule_identity",
    "source_entities", "source_rows", "counts", "statistics", "overall_reconciliation")


def _load_frozen_crosscheck_032():
    return _load_frozen_module(CROSSCHECK_CORE_RELATIVE, CROSSCHECK_CORE_SHA256, "frozen_crosscheck_runtime_032")


def _crosscheck_dir_032(leaf):
    output = leaf.with_name(leaf.name + ".crosscheck")
    _reject_reparse_chain(output, "crosscheck_dir")
    _require_descendant(output, RUNTIME_ROOT, "crosscheck_dir")
    return output


def _crosscheck_inputs_032(batch_dir, runtime_dir, *, scope_dir, event_relative,
                           database_path, gate2_event_relative, initial_paths):
    ctx = _screen_inputs_031(batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
        database_path=database_path, gate2_event_relative=gate2_event_relative, initial_paths=initial_paths)
    screen = _screen_dir_031(ctx["sources"]["leaf"])
    if not screen.is_dir():
        _block("screen_dir", "必须存在已完成筛查目录")
    if FAILURE_FILE in _iter_dir(screen, "screen_dir"):
        inspect_gate2_approved_screen(batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
            database_path=database_path, gate2_event_relative=gate2_event_relative)
        _block("screen.failure", "失败现场不得复算")
    _require_fixed_members(screen, SCREEN_FILES, "screen_dir")
    captures = {}
    for name in SCREEN_FILES:
        _reject_reparse_chain(screen / name, f"screen.{name}")
        captures[name] = _capture_file(screen / name, f"read.crosscheck.screen.{name}")
    inspected = inspect_gate2_approved_screen(batch_dir, runtime_dir, scope_dir=scope_dir,
        event_relative=event_relative, database_path=database_path, gate2_event_relative=gate2_event_relative)
    _require_closed_keys(inspected, ("stage_version", "status", "batch_id", "run_binding_sha256", "artifacts", "boundaries"), "screen_inspect")
    _require_equivalent_030(inspected["stage_version"], SCREEN_STAGE_VERSION, "screen_inspect.stage_version")
    _require_equivalent_030(inspected["status"], "RT_RULE_SCREEN_RECORDED", "screen_inspect.status")
    artifacts = _parse_json_object(captures[ARTIFACTS_FILE]["bytes"], "screen.artifacts")
    report = _parse_json_object(captures[SCREEN_REPORT_FILE]["bytes"], "screen.report")
    _require_equivalent_030(artifacts, inspected["artifacts"], "screen.artifacts")
    for key, expected in (("report_file_sha256", captures[SCREEN_REPORT_FILE]["file_sha256"]),
            ("report_canonical_sha256", fingerprint(report)),
            ("database", {"relative": _project_relative(Path(ctx["sources"]["database_capture"]["path"])),
                "file_sha256": ctx["sources"]["database_capture"]["file_sha256"],
                "byte_size": ctx["sources"]["database_capture"]["byte_size"]})):
        _require_equivalent_030(artifacts[key], expected, f"screen.artifacts.{key}")
    frozen_capture = ctx["sources"]["static_captures"]["project"][CROSSCHECK_CORE_RELATIVE]
    _require_equivalent_030(frozen_capture["file_sha256"], CROSSCHECK_CORE_SHA256, CROSSCHECK_CORE_RELATIVE)
    normalized = _parse_json_object(ctx["sources"]["normalized_capture"]["bytes"], NORMALIZED_FILE)
    ctx.update(screen_output=screen, screen_captures=captures, normalized=normalized, screening_report=report)
    return ctx


def _confirm_crosscheck_inputs_032(ctx):
    _confirm_screen_terminal_031(ctx, ctx["screen_output"], ctx["screen_captures"])


def _crosscheck_started_032(ctx):
    sources = ctx["sources"]
    return {"started_version": CROSSCHECK_STARTED_VERSION, "batch_id": ctx["registry"]["batch_id"],
        "source_batch_relative": _project_relative(sources["batch_path"]), "runtime_relative": _project_relative(sources["leaf"]),
        "gate1_event_relative": _project_relative(sources["event_path"]), "gate2_event_relative": _project_relative(ctx["event"]),
        "database_relative": _project_relative(Path(sources["database_capture"]["path"])),
        "bindings": {"registry_file_sha256": sources["leaf_captures"]["registry"]["file_sha256"],
            "gate2_record_file_sha256": ctx["gate2_captures"]["snapshots/decision_result.json"]["file_sha256"],
            "gate2_record_fingerprint": ctx["verified"]["record_fingerprint"],
            "normalized_file_sha256": sources["normalized_capture"]["file_sha256"],
            "normalized_payload_sha256": fingerprint(ctx["normalized"]),
            "screening_report_file_sha256": ctx["screen_captures"][SCREEN_REPORT_FILE]["file_sha256"],
            "screening_report_canonical_sha256": fingerprint(ctx["screening_report"]),
            "screening_artifacts_file_sha256": ctx["screen_captures"][ARTIFACTS_FILE]["file_sha256"],
            "run_binding": copy.deepcopy(ctx["registry"]["run_binding"])}}


def _crosscheck_artifacts_032(ctx, started, captures, report):
    return {"artifacts_version": CROSSCHECK_ARTIFACTS_VERSION, "batch_id": started["batch_id"],
        "run_binding_sha256": fingerprint(ctx["registry"]["run_binding"]),
        **{key: value for key, value in started["bindings"].items() if key != "run_binding"},
        "started_file_sha256": captures[STARTED_FILE]["file_sha256"],
        "report_file_sha256": captures[CROSSCHECK_REPORT_FILE]["file_sha256"], "report_canonical_sha256": fingerprint(report),
        "database": {"relative": started["database_relative"], "file_sha256": ctx["sources"]["database_capture"]["file_sha256"],
                     "byte_size": ctx["sources"]["database_capture"]["byte_size"]}}


def _validate_crosscheck_report_032(report, ctx, core):
    value = _require_closed_keys(report, CROSSCHECK_REPORT_KEYS, "crosscheck.report")
    for key, expected in (("crosscheck_version", "TASK-007-crosscheck-1.2"), ("mode", "DEVELOPMENT_TEST_ONLY"),
            ("next_step_allowed", False), ("period", {"period_start": "2026-09-01", "period_end": "2026-09-30"}),
            ("cutoff_date", "2026-09-30"), ("rule_core_version_checked", "TASK-006-rule-core-1.1"),
            ("input_source_sha256", ctx["registry"]["input"]["file_sha256"]),
            ("normalized_payload_sha256", fingerprint(ctx["normalized"])),
            ("screening_report_sha256", fingerprint(ctx["screening_report"])),
            ("method", core.METHOD_NOTE), ("limits", core.LIMITS)):
        _require_equivalent_030(value[key], expected, f"crosscheck.report.{key}")
    for key in ("input_source_sha256", "normalized_payload_sha256", "screening_report_sha256"):
        _require_hash(value[key], f"crosscheck.report.{key}")
    comparison = _require_closed_keys(value["comparison"], ("dimensions", "difference_count", "matched_dimensions", "unmatched_dimensions"),
                                       "crosscheck.report.comparison")
    dimensions = _require_closed_keys(comparison["dimensions"], CROSSCHECK_DIMENSIONS, "crosscheck.report.comparison.dimensions")
    differences = _require_list(value["differences"], "crosscheck.report.differences")
    matched_names, unmatched_names, total = [], [], 0
    for name, item in dimensions.items():
        field = f"crosscheck.report.comparison.dimensions.{name}"
        item = _require_closed_keys(item, ("executed", "matched", "difference_count"), field)
        _require_equivalent_030(item["executed"], True, field + ".executed")
        if type(item["matched"]) is not bool:
            _block(field + ".matched", "必须为严格bool")
        count = _require_nonneg_int(item["difference_count"], field + ".difference_count")
        if item["matched"] is not (count == 0):
            _block(field + ".matched", "matched必须与该维度零差异等价")
        total += count
        (matched_names if item["matched"] else unmatched_names).append(name)
    if _require_nonneg_int(comparison["difference_count"], "crosscheck.report.comparison.difference_count") != total or total != len(differences):
        _block("crosscheck.report.comparison.difference_count", "必须等于差异列表长度和十维计数之和")
    _require_equivalent_030(comparison["matched_dimensions"], sorted(matched_names), "crosscheck.report.comparison.matched_dimensions")
    _require_equivalent_030(comparison["unmatched_dimensions"], sorted(unmatched_names), "crosscheck.report.comparison.unmatched_dimensions")
    if type(value["matched"]) is not bool:
        _block("crosscheck.report.matched", "必须为严格bool")
    matched = not differences and not unmatched_names
    _require_equivalent_030(value["matched"], matched, "crosscheck.report.matched")
    _require_equivalent_030(value["batch_status"], "DEV_CROSSCHECK_MATCHED" if matched else "DEV_CROSSCHECK_MISMATCH", "crosscheck.report.batch_status")
    facts = _require_closed_keys(value["recomputed_facts"], ("findings", "reconciliation", "statistics"), "crosscheck.report.recomputed_facts")
    findings = _require_list(facts["findings"], "crosscheck.report.recomputed_facts.findings")
    counts = {rule: 0 for rule in RULE_IDS}
    for index, finding in enumerate(findings):
        field = f"crosscheck.report.recomputed_facts.findings[{index}]"
        finding = _require_object(finding, field)
        rule = _require_nonempty_str(finding.get("rule_id"), field + ".rule_id")
        if rule not in RULE_IDS:
            _block(field + ".rule_id", "未知规则")
        counts[rule] += 1
    count_items = _require_closed_keys(value["rule_recomputed_counts"], (*RULE_IDS, "total"), "crosscheck.report.rule_recomputed_counts")
    for rule, expected in (*counts.items(), ("total", len(findings))):
        if _require_nonneg_int(count_items[rule], f"crosscheck.report.rule_recomputed_counts.{rule}") != expected:
            _block(f"crosscheck.report.rule_recomputed_counts.{rule}", "必须与实际findings数量相等")
    observed = {"rule_hit_counts": ctx["screening_report"]["rule_hit_counts"],
        "r02_overpayment_total_cents": ctx["screening_report"]["statistics"]["r02_overpayment_total_cents"],
        "overall_reconciliation": ctx["screening_report"]["overall_reconciliation"]}
    _require_equivalent_030(value["observed_summary"], observed, "crosscheck.report.observed_summary")
    return matched


def _require_crosscheck_matched_032(report):
    if report["matched"] is not True:
        comparison = report["comparison"]
        _block("crosscheck.report.matched", f"独立复算不一致：差异数={comparison['difference_count']}；维度={comparison['unmatched_dimensions']!r}")


def _crosscheck_result_032(ctx, artifacts):
    return {"stage_version": CROSSCHECK_STAGE_VERSION, "status": "RT_RULE_CROSSCHECK_RECORDED",
        "batch_id": ctx["registry"]["batch_id"], "run_binding_sha256": fingerprint(ctx["registry"]["run_binding"]),
        "artifacts": copy.deepcopy(artifacts), "boundaries": {key: False for key in CROSSCHECK_BOUNDARIES}}


def _confirm_crosscheck_terminal_032(ctx, output, captures):
    _confirm_crosscheck_inputs_032(ctx)
    _reject_reparse_chain(output, "crosscheck_dir")
    _require_fixed_members(output, CROSSCHECK_FILES, "crosscheck_dir")
    for name, capture in captures.items():
        _recheck_capture(capture, f"crosscheck.{name}")


def _write_crosscheck_file_032(output, name, buffer):
    _write_exclusive(output / name, buffer, f"write.crosscheck.{name}")
    capture = _capture_file(output / name, f"readback.crosscheck.{name}")
    if capture["bytes"] != buffer:
        _block(f"crosscheck.{name}", "读回与本次writer缓冲不一致")
    return capture


def run_gate2_rule_crosscheck(batch_dir, runtime_dir, *, scope_dir, event_relative,
                               database_path, gate2_event_relative):
    """对当批已核验筛查执行一次冻结内存复算；MISMATCH保存完整差异后阻断。"""
    output, created, stage = None, False, "crosscheck.paths"
    try:
        initial = _resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative)
        output = _crosscheck_dir_032(initial[1])
        if output.exists():
            _block("crosscheck_dir", "输出必须从未存在（含空目录/文件）")
        ctx = _crosscheck_inputs_032(batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
            database_path=database_path, gate2_event_relative=gate2_event_relative, initial_paths=initial)
        core = _load_frozen_crosscheck_032()
        _confirm_crosscheck_inputs_032(ctx)
        stage = "crosscheck.mkdir"
        try:
            os.mkdir(output)
        except FileExistsError as exc:
            raise RuntimeGate1Blocked("crosscheck_dir", "独占建立被拒绝") from exc
        created = True
        started = _crosscheck_started_032(ctx)
        stage = "write.crosscheck.started.json"
        captures = {STARTED_FILE: _write_crosscheck_file_032(output, STARTED_FILE, _payload_bytes(started))}
        stage = "crosscheck.pre_core"
        _confirm_crosscheck_inputs_032(ctx)
        before = [fingerprint(ctx[key]) for key in ("normalized", "screening_report")]
        stage = "crosscheck.core"
        report = _call_frozen_entry(core, "verify_rule_facts", ctx["normalized"], ctx["screening_report"])
        if before != [fingerprint(ctx[key]) for key in ("normalized", "screening_report")]:
            _block("crosscheck.inputs", "真实复算调用修改了消费对象引用")
        _recheck_capture(ctx["sources"]["database_capture"], DATABASE_NAME)
        stage = "write.crosscheck.crosscheck_report.json"
        captures[CROSSCHECK_REPORT_FILE] = _write_crosscheck_file_032(output, CROSSCHECK_REPORT_FILE, _payload_bytes(report))
        stage = "crosscheck.report"
        _validate_crosscheck_report_032(report, ctx, core)
        _require_crosscheck_matched_032(report)
        artifacts = _crosscheck_artifacts_032(ctx, started, captures, report)
        stage = "write.crosscheck.artifacts.json"
        captures[ARTIFACTS_FILE] = _write_crosscheck_file_032(output, ARTIFACTS_FILE, _payload_bytes(artifacts))
        result = _crosscheck_result_032(ctx, artifacts)
        stage = "crosscheck.final"
        if before != [fingerprint(ctx[key]) for key in ("normalized", "screening_report")]:
            _block("crosscheck.inputs", "API收尾时真实消费对象引用发生变化")
        _confirm_crosscheck_terminal_032(ctx, output, captures)
        return result
    except Exception as exc:
        primary = exc
        if not isinstance(exc, (RuntimeGate1Blocked, RuntimeGate1Error)):
            primary = RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}")
            primary.__cause__ = exc
        if created:
            failure = {"failure_version": CROSSCHECK_FAILURE_VERSION, "kind": "BLOCKED" if isinstance(primary, RuntimeGate1Blocked) else "ERROR",
                "stage": stage, "field": getattr(primary, "field", None), "reason": getattr(primary, "reason", str(primary)), "cause_chain": _cause_chain(primary)}
            try:
                _write_exclusive(output / FAILURE_FILE, _payload_bytes(failure), "write.crosscheck.failure")
            except Exception as secondary:
                _note_secondary(primary, f"{type(secondary).__name__}: {secondary}", stage="failure_write")
        raise primary


def inspect_gate2_rule_crosscheck(batch_dir, runtime_dir, *, scope_dir, event_relative,
                                   database_path, gate2_event_relative):
    """只读恢复完整MATCHED，不重新运行复算/SQL或保存；有效failure优先。"""
    try:
        initial = _resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative)
        output = _crosscheck_dir_032(initial[1])
        if not output.is_dir():
            _block("crosscheck_dir", "复算输出目录不存在")
        if FAILURE_FILE in _iter_dir(output, "crosscheck_dir"):
            _reject_reparse_chain(output / FAILURE_FILE, "crosscheck.failure")
            failure = _require_closed_keys(_parse_json_object(_capture_file(output / FAILURE_FILE,
                "read.crosscheck.failure")["bytes"], "crosscheck.failure"), FAILURE_KEYS_028, "crosscheck.failure")
            _require_equivalent_030(failure["failure_version"], CROSSCHECK_FAILURE_VERSION, "crosscheck.failure.failure_version")
            if failure["kind"] not in FAILURE_KINDS:
                _block("crosscheck.failure.kind", "必须为BLOCKED/ERROR")
            for key in ("stage", "reason"):
                _require_nonempty_str(failure[key], f"crosscheck.failure.{key}")
            if failure["field"] is not None:
                _require_nonempty_str(failure["field"], "crosscheck.failure.field")
            for index, reason in enumerate(_require_list(failure["cause_chain"], "crosscheck.failure.cause_chain")):
                _require_nonempty_str(reason, f"crosscheck.failure.cause_chain[{index}]")
            if failure["kind"] == "BLOCKED":
                raise RuntimeGate1Blocked(f"crosscheck.failure.{failure['field']}", failure["reason"])
            raise RuntimeGate1Error(f"crosscheck.failure.{failure['stage']}", failure["reason"])
        _require_fixed_members(output, CROSSCHECK_FILES, "crosscheck_dir")
        captures = {}
        for name in CROSSCHECK_FILES:
            _reject_reparse_chain(output / name, f"crosscheck.{name}")
            captures[name] = _capture_file(output / name, f"read.crosscheck.{name}")
        ctx = _crosscheck_inputs_032(batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
            database_path=database_path, gate2_event_relative=gate2_event_relative, initial_paths=initial)
        started = _require_closed_keys(_parse_json_object(captures[STARTED_FILE]["bytes"], "crosscheck.started"), SCREEN_STARTED_KEYS, "crosscheck.started")
        bindings = _require_closed_keys(started["bindings"], CROSSCHECK_BINDING_KEYS, "crosscheck.started.bindings")
        for key in CROSSCHECK_BINDING_KEYS[:-1]:
            _require_hash(bindings[key], f"crosscheck.started.bindings.{key}")
        _require_equivalent_030(started, _crosscheck_started_032(ctx), "crosscheck.started")
        report = _parse_json_object(captures[CROSSCHECK_REPORT_FILE]["bytes"], "crosscheck.report")
        core = _load_frozen_crosscheck_032()
        _validate_crosscheck_report_032(report, ctx, core)
        _require_crosscheck_matched_032(report)
        artifacts = _require_closed_keys(_parse_json_object(captures[ARTIFACTS_FILE]["bytes"], "crosscheck.artifacts"), CROSSCHECK_ARTIFACTS_KEYS, "crosscheck.artifacts")
        database = _require_closed_keys(artifacts["database"], ARTIFACTS_DATABASE_KEYS, "crosscheck.artifacts.database")
        _require_nonneg_int(database["byte_size"], "crosscheck.artifacts.database.byte_size")
        _require_hash(database["file_sha256"], "crosscheck.artifacts.database.file_sha256")
        for key in CROSSCHECK_ARTIFACTS_KEYS:
            if key.endswith("sha256") or key.endswith("fingerprint"):
                _require_hash(artifacts[key], f"crosscheck.artifacts.{key}")
        _require_equivalent_030(artifacts, _crosscheck_artifacts_032(ctx, started, captures, report), "crosscheck.artifacts")
        result = _crosscheck_result_032(ctx, artifacts)
        _confirm_crosscheck_terminal_032(ctx, output, captures)
        return result
    except OSError as exc:
        raise RuntimeGate1Error("inspect.crosscheck", f"{type(exc).__name__}: {exc}") from exc


# --------------------------------------------------------------------------- TASK-033
FACT_CORE_RELATIVE = "scripts/build_demo_fact_packet.py"
FACT_CORE_SHA256 = "f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62"
FACT_STAGE_VERSION = "TASK-033-fact-packet-1.0"
FACT_STARTED_VERSION = "TASK-033-fact-packet-start-1.0"
FACT_ARTIFACTS_VERSION = "TASK-033-fact-packet-artifacts-1.0"
FACT_FAILURE_VERSION = "TASK-033-fact-packet-failure-1.0"
FACT_PACKET_FILE, FACT_MARKDOWN_FILE = "fact_packet.json", "fact_packet.md"
FACT_FILES = (STARTED_FILE, FACT_PACKET_FILE, FACT_MARKDOWN_FILE, ARTIFACTS_FILE)
FACT_BOUNDARIES = tuple(key for key in CROSSCHECK_BOUNDARIES if key != "fact_packet_recorded")
FACT_STARTED_KEYS = (*SCREEN_STARTED_KEYS, "runtime_context")
FACT_BINDING_KEYS = (*CROSSCHECK_BINDING_KEYS[:-1], "crosscheck_started_file_sha256",
    "crosscheck_report_file_sha256", "crosscheck_report_canonical_sha256", "crosscheck_artifacts_file_sha256", "run_binding")
FACT_ARTIFACTS_KEYS = ("artifacts_version", "batch_id", "run_binding_sha256", "bindings", "started_file_sha256",
    "packet_file_sha256", "packet_canonical_sha256", "markdown_file_sha256", "markdown_byte_size", "database")
FACT_PACKET_KEYS = ("packet_version", "batch_status", "mode", "next_step_allowed", "entity", "banner",
    "bindings", "summary", "reconciliation", "findings", "amount_labels", "limits")
FACT_RUNTIME_CONTEXT = {"contract_version": "V1", "contract_file_sha256": EXPECTED_CONTRACT_SHA256,
    "core_notice_scope": "FROZEN_DEVELOPMENT_TEMPLATE",
    "notice": "冻结事实核心中的契约/批准未实施提示是该开发模板原文；本运行层另行核验已绑定正式V1契约及当批本地Gate记录。原文不代表本层未核验，也不表示已获真实批次批准、强身份认证或审计结论。人类初判未保存，AI未开放。"}


def _load_frozen_facts_033():
    return _load_frozen_module(FACT_CORE_RELATIVE, FACT_CORE_SHA256, "frozen_fact_packet_runtime_033")


def _facts_dir_033(leaf):
    output = leaf.with_name(leaf.name + ".facts")
    _reject_reparse_chain(output, "facts_dir")
    _require_descendant(output, RUNTIME_ROOT, "facts_dir")
    return output


def _fact_inputs_033(batch_dir, runtime_dir, *, scope_dir, event_relative,
                     database_path, gate2_event_relative, initial_paths):
    ctx = _crosscheck_inputs_032(batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
        database_path=database_path, gate2_event_relative=gate2_event_relative, initial_paths=initial_paths)
    output = _crosscheck_dir_032(ctx["sources"]["leaf"])
    if not output.is_dir():
        _block("crosscheck_dir", "必须存在已完成独立复算")
    params = dict(scope_dir=scope_dir, event_relative=event_relative, database_path=database_path,
                  gate2_event_relative=gate2_event_relative)
    if FAILURE_FILE in _iter_dir(output, "crosscheck_dir"):
        inspect_gate2_rule_crosscheck(batch_dir, runtime_dir, **params)
        _block("crosscheck.failure", "失败现场不得构建事实底稿")
    _require_fixed_members(output, CROSSCHECK_FILES, "crosscheck_dir")
    captures = {}
    for name in CROSSCHECK_FILES:
        _reject_reparse_chain(output / name, f"crosscheck.{name}")
        captures[name] = _capture_file(output / name, f"read.facts.crosscheck.{name}")
    inspected = inspect_gate2_rule_crosscheck(batch_dir, runtime_dir, **params)
    _require_closed_keys(inspected, ("stage_version", "status", "batch_id", "run_binding_sha256", "artifacts", "boundaries"), "crosscheck_inspect")
    _require_equivalent_030(inspected["stage_version"], CROSSCHECK_STAGE_VERSION, "crosscheck_inspect.stage_version")
    _require_equivalent_030(inspected["status"], "RT_RULE_CROSSCHECK_RECORDED", "crosscheck_inspect.status")
    started = _parse_json_object(captures[STARTED_FILE]["bytes"], "crosscheck.started")
    report = _parse_json_object(captures[CROSSCHECK_REPORT_FILE]["bytes"], "crosscheck.report")
    artifacts = _parse_json_object(captures[ARTIFACTS_FILE]["bytes"], "crosscheck.artifacts")
    _require_equivalent_030(started, _crosscheck_started_032(ctx), "crosscheck.started")
    _require_equivalent_030(artifacts, inspected["artifacts"], "crosscheck.artifacts")
    _require_equivalent_030(artifacts, _crosscheck_artifacts_032(ctx, started, captures, report), "crosscheck.artifacts.bindings")
    _require_crosscheck_matched_032(report)
    frozen = ctx["sources"]["static_captures"]["project"][FACT_CORE_RELATIVE]
    _require_equivalent_030(frozen["file_sha256"], FACT_CORE_SHA256, FACT_CORE_RELATIVE)
    _require_equivalent_030(ctx["registry"]["contract"]["contract_file_sha256"], EXPECTED_CONTRACT_SHA256, "facts.contract_file_sha256")
    ctx.update(crosscheck_output=output, crosscheck_captures=captures, crosscheck_report=report)
    return ctx


def _confirm_fact_inputs_033(ctx):
    _confirm_crosscheck_terminal_032(ctx, ctx["crosscheck_output"], ctx["crosscheck_captures"])


def _fact_started_033(ctx):
    started = _crosscheck_started_032(ctx)
    started["started_version"] = FACT_STARTED_VERSION
    binding = started["bindings"]
    binding.update(crosscheck_started_file_sha256=ctx["crosscheck_captures"][STARTED_FILE]["file_sha256"],
        crosscheck_report_file_sha256=ctx["crosscheck_captures"][CROSSCHECK_REPORT_FILE]["file_sha256"],
        crosscheck_report_canonical_sha256=fingerprint(ctx["crosscheck_report"]),
        crosscheck_artifacts_file_sha256=ctx["crosscheck_captures"][ARTIFACTS_FILE]["file_sha256"])
    started["runtime_context"] = copy.deepcopy(FACT_RUNTIME_CONTEXT)
    return started


def _fact_context_keys_033(value, keys, field):
    value = _require_object(value, field)
    for key in keys:
        if key not in value:
            _block(field + "." + key, "缺少必需展示字段")
    return _require_closed_keys(value, keys, field)


def _fact_context_index_033(normalized):
    """仅按原表、原字符串ID索引已有记录；不计算规则或组装事实卡。"""
    tables = _require_object(normalized.get("tables"), "facts.normalized.tables")
    indexes = {}
    for sheet, id_key in (("suppliers", "supplier_id"), ("payables", "ap_id"),
                          ("payments", "payment_id"), ("allocations", "allocation_id")):
        table = _require_object(tables.get(sheet), "facts.normalized.tables." + sheet)
        records = _require_list(table.get("records"), "facts.normalized.tables." + sheet + ".records")
        indexes[sheet] = {}
        for position, row in enumerate(records):
            field = f"facts.normalized.tables.{sheet}.records[{position}]"
            row = _require_object(row, field)
            data = _require_object(row.get("data"), field + ".data")
            record_id = _require_nonempty_str(data.get(id_key), field + ".data." + id_key)
            if record_id in indexes[sheet]:
                _block(field + ".data." + id_key, "对应表的原ID重复")
            indexes[sheet][record_id] = row
    return indexes


def _fact_context_entry_033(value, indexes, sheet, record_id, label, field, extra_keys=()):
    value = _require_object(value, field)
    for key in ("status", "label", "record_id"):
        if key not in value:
            _block(field + "." + key, "缺少必需展示字段")
    if type(value["status"]) is not str or value["status"] not in ("found", "not_found"):
        _block(field + ".status", "必须为found或not_found字符串")
    if record_id is not None and type(record_id) is not str:
        _block(field + ".record_id", "关联ID必须为原字符串或null")
    row = indexes[sheet].get(record_id) if record_id else None
    expected_status = "found" if row is not None else "not_found"
    if value["status"] != expected_status:
        _block(field + ".status", "必须与对应表中本条关联ID的实际存在状态一致")
    keys = ("label", "status", "record_id", *extra_keys)
    if row is not None:
        keys += ("data", "source", "cells")
    _fact_context_keys_033(value, keys, field)
    _require_equivalent_030(value["label"], label, field + ".label")
    _require_equivalent_030(value["record_id"], record_id, field + ".record_id")
    if row is not None:
        for key in ("data", "source", "cells"):
            _require_object(value[key], field + "." + key)
            _require_equivalent_030(value[key], row[key], field + "." + key)
    return row


def _validate_fact_payable_033(value, indexes, related, field):
    """共用应付角色核验；合法历史缺失关联可仅在内存核对，不迁移旧展示布局。"""
    payable_id = related.get("payable_id")
    if payable_id is not None and type(payable_id) is not str:
        _block(field + ".record_id", "关联ID必须为原字符串或null")
    row = indexes["payables"].get(payable_id) if payable_id else None
    missing_code = related.get("missing_kind_code")
    missing_keys = ("missing_kind_code", "missing_kind") if row is None and (missing_code or payable_id is None) else ()
    _fact_context_entry_033(value, indexes, "payables", payable_id, "相关应付单", field, missing_keys)
    if missing_keys:
        labels = {"EMPTY_AP_ID": "未填写关联", "AP_NOT_IN_LEDGER": "所填标识不在提供的台账"}
        _require_equivalent_030(value["missing_kind_code"], missing_code, field + ".missing_kind_code")
        _require_equivalent_030(value["missing_kind"], labels.get(missing_code, "台账中未找到该应付标识"), field + ".missing_kind")


def _validate_fact_context_033(context, normalized, finding, field):
    """按已知展示角色及当前finding关联，核对对应表的完整原记录。"""
    indexes = _fact_context_index_033(normalized)
    related = _require_object(finding.get("related_ids"), field + ".related_ids")
    payable_id = related.get("payable_id")
    if payable_id is not None and type(payable_id) is not str:
        _block(field + ".payable.record_id", "关联ID必须为原字符串或null")
    payable_row = indexes["payables"].get(payable_id) if payable_id else None
    keys = ("payable", "payments", "allocations", "refunds")
    if payable_row is not None:
        keys += ("payable_supplier",)
    context = _fact_context_keys_033(context, keys, field)
    _validate_fact_payable_033(context["payable"], indexes, related, field + ".payable")
    if payable_row is not None:
        _fact_context_entry_033(context["payable_supplier"], indexes, "suppliers", payable_row["data"].get("supplier_id"),
                                "应付单供应商", field + ".payable_supplier")
    for role, sheet, id_key, label in (("payments", "payments", "payment_ids", "相关原付款主表"),
                                      ("allocations", "allocations", "allocation_ids", "相关原付款分摊")):
        entries = _require_list(context[role], field + "." + role)
        record_ids = _require_list(related.get(id_key, []), field + ".related_ids." + id_key)
        if len(entries) != len(record_ids):
            _block(field + "." + role, "必须与本条finding的关联ID列表长度和顺序一致")
        for position, (entry, record_id) in enumerate(zip(entries, record_ids)):
            entry_field = f"{field}.{role}[{position}]"
            if type(record_id) is not str:
                _block(entry_field + ".record_id", "关联ID必须为原字符串")
            row = indexes[sheet].get(record_id) if record_id else None
            extra = ("payee_supplier",) if role == "payments" and row is not None else ()
            _fact_context_entry_033(entry, indexes, sheet, record_id, label, entry_field, extra)
            if extra:
                _fact_context_entry_033(entry["payee_supplier"], indexes, "suppliers", row["data"].get("payee_supplier_id"),
                                        "实际收款对象", entry_field + ".payee_supplier")
    refunds = _require_list(context["refunds"], field + ".refunds")
    evidence = _require_object(finding.get("evidence"), field + ".evidence")
    refund_refs = _require_list(evidence.get("related_refunds", []), field + ".evidence.related_refunds")
    if len(refunds) != len(refund_refs):
        _block(field + ".refunds", "必须与本条finding的退款关联列表长度和顺序一致")
    for position, (entries, reference) in enumerate(zip(refunds, refund_refs)):
        refund_field = f"{field}.refunds[{position}]"
        entries = _fact_context_keys_033(entries, ("refund", "refund_allocation"), refund_field)
        reference = _require_object(reference, refund_field + ".reference")
        for role, sheet, id_key, label in (("refund", "payments", "refund_payment_id", "相关退款主表"),
                                          ("refund_allocation", "allocations", "refund_allocation_id", "相关退款分摊")):
            _fact_context_entry_033(entries[role], indexes, sheet, reference.get(id_key), label, refund_field + "." + role)


def _validate_fact_packet_033(packet, ctx, core):
    packet = _require_closed_keys(packet, FACT_PACKET_KEYS, "facts.packet")
    for key, expected in (("packet_version", "TASK-008-fact-packet-1.1"), ("batch_status", "DEV_FACT_PACKET_READY"),
            ("mode", "DEVELOPMENT_TEST_ONLY"), ("next_step_allowed", False),
            ("entity", {"company": "澄明商贸有限公司", "currency": "人民币（CNY）", "cutoff_date": "2026-09-30",
                "period": {"period_start": "2026-09-01", "period_end": "2026-09-30"}}),
            ("banner", core.BANNER), ("limits", core.LIMITS),
            ("amount_labels", {"note": "正文字段名到业务中文标签的固定映射；不改变 amounts_cents 的原字段与数值",
                "mapping": core.AMOUNT_LABELS, "net_total_by_rule": core.NET_TOTAL_LABELS})):
        _require_equivalent_030(packet[key], expected, f"facts.packet.{key}")
    screen, cross, normalized = ctx["screening_report"], ctx["crosscheck_report"], ctx["normalized"]
    expected_bindings = {"workbook_sha256": ctx["registry"]["input"]["file_sha256"],
        "normalized_payload_sha256": fingerprint(normalized), "screening_report_sha256": fingerprint(screen),
        "crosscheck_report_sha256": fingerprint(cross),
        "upstream_versions": {"normalization": normalized["normalization_version"], "rule_core": screen["rule_core_version"],
            "crosscheck": cross["crosscheck_version"], "store": screen["load_source"]["store_version"], "schema": screen["load_source"]["schema_version"]},
        "upstream_declared_database": {"database_path": ctx["sources"]["database_capture"]["path"],
            "database_sha256_before": ctx["sources"]["database_capture"]["file_sha256"],
            "database_sha256_after": ctx["sources"]["database_capture"]["file_sha256"], "sha256_equal": True, "database_unchanged": True,
            "note": "仅为上游报告声明的数据库哈希；展示层未读取或重验数据库字节"}}
    bindings = _require_closed_keys(packet["bindings"], expected_bindings, "facts.packet.bindings")
    for key in ("workbook_sha256", "normalized_payload_sha256", "screening_report_sha256", "crosscheck_report_sha256"):
        _require_hash(bindings[key], f"facts.packet.bindings.{key}")
    _require_equivalent_030(bindings, expected_bindings, "facts.packet.bindings")
    findings = _require_list(packet["findings"], "facts.packet.findings")
    if len(findings) != len(screen["findings"]):
        _block("facts.packet.findings", "必须与已核验筛查线索数量一致")
    counts, identifiers = {key: 0 for key in RULE_IDS}, set()
    card_keys = ("finding_id", "rule_id", "rule_name", "rule_template", "hit_key", "amounts_cents", "amounts_display_cny",
                 "related_ids", "source_rows", "evidence", "context", "refund_summary")
    for index, (card, finding) in enumerate(zip(findings, screen["findings"])):
        field = f"facts.packet.findings[{index}]"
        card = _require_closed_keys(card, (*card_keys, "missing_kind") if finding["rule_id"] == "R03" else card_keys, field)
        for key in ("rule_id", "hit_key", "amounts_cents", "related_ids", "source_rows", "evidence"):
            _require_equivalent_030(card[key], finding[key], field + "." + key)
        rule = finding["rule_id"]
        counts[rule] += 1
        finding_id = _require_nonempty_str(card["finding_id"], field + ".finding_id")
        if finding_id in identifiers:
            _block(field + ".finding_id", "线索ID重复")
        identifiers.add(finding_id)
        _require_equivalent_030(card["rule_name"], core.RULE_NAMES[rule], field + ".rule_name")
        _require_equivalent_030(card["rule_template"], core.RULE_TEMPLATES[rule], field + ".rule_template")
        _require_object(card["amounts_display_cny"], field + ".amounts_display_cny")
        _require_object(card["context"], field + ".context")
        _validate_fact_context_033(card["context"], normalized, finding, field + ".context")
        if rule == "R03":
            _require_equivalent_030(card["missing_kind"], core.MISSING_KIND_LABEL.get(
                finding["related_ids"].get("missing_kind_code"), "台账中未找到该应付标识"), field + ".missing_kind")
    summary = _require_closed_keys(packet["summary"], ("rule_counts", "total_findings", "involved_payments", "r02_overpayment_total_cents", "r02_overpayment_basis"), "facts.packet.summary")
    rule_counts = _require_closed_keys(summary["rule_counts"], RULE_IDS, "facts.packet.summary.rule_counts")
    for rule, count in counts.items():
        if _require_nonneg_int(rule_counts[rule], f"facts.packet.summary.rule_counts.{rule}") != count:
            _block(f"facts.packet.summary.rule_counts.{rule}", "必须与实际findings数量一致")
    if _require_nonneg_int(summary["total_findings"], "facts.packet.summary.total_findings") != len(findings):
        _block("facts.packet.summary.total_findings", "必须等于实际findings总长")
    _require_equivalent_030(rule_counts, {rule: screen["rule_hit_counts"][rule] for rule in RULE_IDS}, "facts.packet.summary.rule_counts")
    expected_involved = dict(screen["statistics"]["involved_payments"], note="涉及的唯一原付款事件的整笔已结算总额；不能当作缺失关联分摊额或损失")
    _require_equivalent_030(summary["involved_payments"], expected_involved, "facts.packet.summary.involved_payments")
    for key in ("r02_overpayment_total_cents", "r02_overpayment_basis"):
        _require_equivalent_030(summary[key], screen["statistics"][key], "facts.packet.summary." + key)
    source_reconciliation = screen["overall_reconciliation"]
    expected_reconciliation = {key: source_reconciliation[key] for key in ("unit", "settled_pay_master_total",
        "settled_refund_master_total", "master_net", "known_payable_link_net", "missing_payable_link_net")}
    expected_reconciliation.update(source_reconciliation["missing_payable_link_detail"], note="资金主表口径与分摊口径分别列示，不相加")
    reconciliation = _require_closed_keys(packet["reconciliation"], expected_reconciliation, "facts.packet.reconciliation")
    for key in expected_reconciliation:
        if key not in ("unit", "note"):
            _require_int_031(reconciliation[key], "facts.packet.reconciliation." + key)
    _require_equivalent_030(reconciliation, expected_reconciliation, "facts.packet.reconciliation")
    _screen_numbers_031(packet, "facts.packet")
    return packet


def _fact_artifacts_033(ctx, started, captures, packet, markdown):
    return {"artifacts_version": FACT_ARTIFACTS_VERSION, "batch_id": started["batch_id"],
        "run_binding_sha256": fingerprint(ctx["registry"]["run_binding"]), "bindings": copy.deepcopy(started["bindings"]),
        "started_file_sha256": captures[STARTED_FILE]["file_sha256"], "packet_file_sha256": captures[FACT_PACKET_FILE]["file_sha256"],
        "packet_canonical_sha256": fingerprint(packet), "markdown_file_sha256": _sha_bytes(markdown), "markdown_byte_size": len(markdown),
        "database": {"relative": started["database_relative"], "file_sha256": ctx["sources"]["database_capture"]["file_sha256"],
                     "byte_size": ctx["sources"]["database_capture"]["byte_size"]}}


def _fact_result_033(ctx, artifacts):
    return {"stage_version": FACT_STAGE_VERSION, "status": "RT_FACT_PACKET_RECORDED", "batch_id": ctx["registry"]["batch_id"],
        "run_binding_sha256": fingerprint(ctx["registry"]["run_binding"]), "artifacts": copy.deepcopy(artifacts),
        "boundaries": {key: False for key in FACT_BOUNDARIES}}


def _confirm_fact_terminal_033(ctx, output, captures):
    _confirm_fact_inputs_033(ctx)
    _reject_reparse_chain(output, "facts_dir")
    _require_fixed_members(output, FACT_FILES, "facts_dir")
    for name, capture in captures.items():
        _recheck_capture(capture, f"facts.{name}")


def _write_fact_file_033(output, name, buffer):
    _write_exclusive(output / name, buffer, f"write.facts.{name}")
    capture = _capture_file(output / name, f"readback.facts.{name}")
    if capture["bytes"] != buffer:
        _block(f"facts.{name}", "读回与本次writer缓冲不一致")
    return capture


def run_gate2_fact_packet(batch_dir, runtime_dir, *, scope_dir, event_relative,
                           database_path, gate2_event_relative):
    """仅单次冻结build；保持模板原提示，并单列本运行上下文。"""
    output, created, stage = None, False, "facts.paths"
    try:
        initial = _resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative)
        output = _facts_dir_033(initial[1])
        if output.exists():
            _block("facts_dir", "输出必须从未存在（含空目录/文件）")
        ctx = _fact_inputs_033(batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
            database_path=database_path, gate2_event_relative=gate2_event_relative, initial_paths=initial)
        core = _load_frozen_facts_033()
        _confirm_fact_inputs_033(ctx)
        stage = "facts.mkdir"
        try:
            os.mkdir(output)
        except FileExistsError as exc:
            raise RuntimeGate1Blocked("facts_dir", "独占建立被拒绝") from exc
        created = True
        started = _fact_started_033(ctx)
        stage = "write.facts.started.json"
        captures = {STARTED_FILE: _write_fact_file_033(output, STARTED_FILE, _payload_bytes(started))}
        stage = "facts.pre_core"
        _confirm_fact_inputs_033(ctx)
        refs = [ctx[key] for key in ("normalized", "screening_report", "crosscheck_report")]
        before = [fingerprint(value) for value in refs]
        stage = "facts.build"
        built = _call_frozen_entry(core, "build_fact_packet", *refs)
        if before != [fingerprint(value) for value in refs]:
            _block("facts.inputs", "真实构建修改了消费引用")
        built = _require_closed_keys(built, ("packet", "packet_sha256", "markdown"), "facts.build_result")
        packet = _validate_fact_packet_033(built["packet"], ctx, core)
        _require_hash(built["packet_sha256"], "facts.build_result.packet_sha256")
        _require_equivalent_030(built["packet_sha256"], fingerprint(packet), "facts.build_result.packet_sha256")
        if type(built["markdown"]) is not str:
            _block("facts.build_result.markdown", "必须为严格str")
        markdown = built["markdown"].encode("utf-8")
        for name, buffer in ((FACT_PACKET_FILE, _payload_bytes(packet)), (FACT_MARKDOWN_FILE, markdown)):
            stage = "write.facts." + name
            captures[name] = _write_fact_file_033(output, name, buffer)
        artifacts = _fact_artifacts_033(ctx, started, captures, packet, markdown)
        stage = "write.facts.artifacts.json"
        captures[ARTIFACTS_FILE] = _write_fact_file_033(output, ARTIFACTS_FILE, _payload_bytes(artifacts))
        result = _fact_result_033(ctx, artifacts)
        stage = "facts.final"
        if before != [fingerprint(value) for value in refs]:
            _block("facts.inputs", "API收尾时真实消费引用变化")
        _confirm_fact_terminal_033(ctx, output, captures)
        return result
    except Exception as exc:
        primary = exc
        if not isinstance(exc, (RuntimeGate1Blocked, RuntimeGate1Error)):
            primary = RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}")
            primary.__cause__ = exc
        if created:
            failure = {"failure_version": FACT_FAILURE_VERSION, "kind": "BLOCKED" if isinstance(primary, RuntimeGate1Blocked) else "ERROR",
                "stage": stage, "field": getattr(primary, "field", None), "reason": getattr(primary, "reason", str(primary)), "cause_chain": _cause_chain(primary)}
            try:
                _write_exclusive(output / FAILURE_FILE, _payload_bytes(failure), "write.facts.failure")
            except Exception as secondary:
                _note_secondary(primary, f"{type(secondary).__name__}: {secondary}", stage="failure_write")
        raise primary


def inspect_gate2_fact_packet(batch_dir, runtime_dir, *, scope_dir, event_relative,
                               database_path, gate2_event_relative):
    """只读恢复；仅允许一次纯render核对，不重新build或计算。"""
    try:
        initial = _resolve_approved_paths(batch_dir, runtime_dir, scope_dir, event_relative)
        output = _facts_dir_033(initial[1])
        if not output.is_dir():
            _block("facts_dir", "事实底稿输出不存在")
        if FAILURE_FILE in _iter_dir(output, "facts_dir"):
            _reject_reparse_chain(output / FAILURE_FILE, "facts.failure")
            failure = _require_closed_keys(_parse_json_object(_capture_file(output / FAILURE_FILE,
                "read.facts.failure")["bytes"], "facts.failure"), FAILURE_KEYS_028, "facts.failure")
            _require_equivalent_030(failure["failure_version"], FACT_FAILURE_VERSION, "facts.failure.failure_version")
            if failure["kind"] not in FAILURE_KINDS:
                _block("facts.failure.kind", "必须为BLOCKED/ERROR")
            for key in ("stage", "reason"):
                _require_nonempty_str(failure[key], f"facts.failure.{key}")
            if failure["field"] is not None:
                _require_nonempty_str(failure["field"], "facts.failure.field")
            for index, reason in enumerate(_require_list(failure["cause_chain"], "facts.failure.cause_chain")):
                _require_nonempty_str(reason, f"facts.failure.cause_chain[{index}]")
            if failure["kind"] == "BLOCKED":
                raise RuntimeGate1Blocked(f"facts.failure.{failure['field']}", failure["reason"])
            raise RuntimeGate1Error(f"facts.failure.{failure['stage']}", failure["reason"])
        _require_fixed_members(output, FACT_FILES, "facts_dir")
        captures = {}
        for name in FACT_FILES:
            _reject_reparse_chain(output / name, f"facts.{name}")
            captures[name] = _capture_file(output / name, f"read.facts.{name}")
        ctx = _fact_inputs_033(batch_dir, runtime_dir, scope_dir=scope_dir, event_relative=event_relative,
            database_path=database_path, gate2_event_relative=gate2_event_relative, initial_paths=initial)
        core = _load_frozen_facts_033()
        started = _require_closed_keys(_parse_json_object(captures[STARTED_FILE]["bytes"], "facts.started"), FACT_STARTED_KEYS, "facts.started")
        bindings = _require_closed_keys(started["bindings"], FACT_BINDING_KEYS, "facts.started.bindings")
        for key in FACT_BINDING_KEYS[:-1]:
            _require_hash(bindings[key], f"facts.started.bindings.{key}")
        _require_equivalent_030(started, _fact_started_033(ctx), "facts.started")
        packet = _validate_fact_packet_033(_parse_json_object(captures[FACT_PACKET_FILE]["bytes"], "facts.packet"), ctx, core)
        before = fingerprint(packet)
        rendered = _call_frozen_entry(core, "render_markdown", packet)
        if type(rendered) is not str or rendered.encode("utf-8") != captures[FACT_MARKDOWN_FILE]["bytes"]:
            _block("facts.markdown.rendered_bytes", "Markdown与真实renderer完整返回UTF-8字节不一致")
        if fingerprint(packet) != before:
            _block("facts.render.input", "renderer修改了实际packet引用")
        artifacts = _require_closed_keys(_parse_json_object(captures[ARTIFACTS_FILE]["bytes"], "facts.artifacts"), FACT_ARTIFACTS_KEYS, "facts.artifacts")
        _require_nonneg_int(artifacts["markdown_byte_size"], "facts.artifacts.markdown_byte_size")
        database = _require_closed_keys(artifacts["database"], ARTIFACTS_DATABASE_KEYS, "facts.artifacts.database")
        _require_nonneg_int(database["byte_size"], "facts.artifacts.database.byte_size")
        _require_equivalent_030(artifacts, _fact_artifacts_033(ctx, started, captures, packet, captures[FACT_MARKDOWN_FILE]["bytes"]), "facts.artifacts")
        result = _fact_result_033(ctx, artifacts)
        if fingerprint(packet) != before:
            _block("facts.render.input", "API收尾时renderer消费packet引用变化")
        _confirm_fact_terminal_033(ctx, output, captures)
        return result
    except OSError as exc:
        raise RuntimeGate1Error("inspect.facts", f"{type(exc).__name__}: {exc}") from exc


# --------------------------------------------------------------------------- TASK-038
INITIAL_HISTORY_ROOT = DATA_ROOT / "human_initial_judgment_records"
INITIAL_HISTORY_RELATIVE = "scripts/inspect_demo_human_initial_judgment_history.py"
INITIAL_REQUEST_VERSION = "TASK-038-human-initial-judgment-request-1.0"
INITIAL_REQUEST_STATUS = "RUNTIME_HUMAN_INITIAL_JUDGMENT_REQUEST_PREPARED"
INITIAL_BOUNDARIES = ("request_persisted", "human_initial_judgment_saved", "execution_allowed",
    "next_step_allowed", "ai_enabled", "workflow_connected", "identity_authenticated",
    "source_authenticity_proven", "audit_conclusion_formed", "final_judgment_recorded")
INITIAL_HISTORY_KEYS = ("namespace_relative", "declared_scope")
INITIAL_HISTORY_RETURN_KEYS = ("history_version", "status", "scope", "namespace_relative", "prior_history",
    "prior_history_fingerprint", "inventory", "inventory_fingerprint", "component_bindings", "verified_snapshots", "boundaries", "note")


def _utf8_038(value, field):
    if type(value) is not str or not value.strip():
        _block(field, "必须为非空原字符串")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise RuntimeGate1Blocked(field, "必须为合法UTF-8") from exc
    return value


def _relative_038(value, field):
    _utf8_038(value, field)
    if "\\" in value or ":" in value or "\x00" in value or any(p in ("", ".", "..") for p in value.split("/")):
        _block(field, "必须为安全项目相对POSIX原字符串")
    return value


def _history_namespace_capture_038(binding):
    field = "initial_judgment_history"
    if type(binding) is not dict:
        _block(field, "必须为严格对象")
    _require_closed_keys(binding, INITIAL_HISTORY_KEYS, field)
    relative = _relative_038(binding["namespace_relative"], field + ".namespace_relative")
    _utf8_038(binding["declared_scope"], field + ".declared_scope")
    raw = PROJECT_ROOT / relative
    _reject_reparse_chain(raw, field + ".namespace_relative")
    try:
        path = raw.resolve()
        if not path.is_dir():
            _block(field + ".namespace_relative", "声明域必须为既存正常目录")
    except OSError as exc:
        raise RuntimeGate1Error("history.namespace", str(exc)) from exc
    _require_descendant(path, INITIAL_HISTORY_ROOT, field + ".namespace_relative")
    if _project_relative(path) != relative:
        _block(field + ".namespace_relative", "解析后必须与原项目相对路径精确相等")
    for other in (RUNTIME_ROOT, GATE1_RECORDS_ROOT, GATE2_RECORDS_ROOT, DATA_ROOT / "sqlite_tests"):
        if _is_ancestor(path, other) or _is_ancestor(other, path):
            _block(field + ".namespace_relative", "声明域不得与运行/Gate/SQLite根交叠")
    return {"path": str(path), "relative": relative, "identity": _path_identity(path, "history.namespace")}


def _confirm_history_namespace_038(capture):
    raw = PROJECT_ROOT / capture["relative"]
    _reject_reparse_chain(raw, "initial_judgment_history.namespace_relative")
    if not raw.is_dir() or str(raw.resolve()) != capture["path"] or _path_identity(raw, "history.namespace.final") != capture["identity"]:
        _block("initial_judgment_history.namespace_relative", "声明域原路径或目录身份较操作开始变化")


def _load_initial_history_038(capture):
    expected = INITIAL_COMPONENT_SHA256[INITIAL_HISTORY_RELATIVE]
    if capture["file_sha256"] != expected:
        _block(INITIAL_HISTORY_RELATIVE, "冻结history身份不符")
    # Execute exactly the already-bound source buffer, without a second loader read.
    import types
    module = types.ModuleType("_task038_frozen_initial_history")
    module.__file__ = capture["path"]
    try:
        exec(compile(capture["bytes"], capture["path"], "exec"), module.__dict__)
    except Exception as exc:
        raise RuntimeGate1Error("load.initial_history", f"{type(exc).__name__}: {exc}") from exc
    return module


def _history_call_038(module, function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except module.HumanInitialJudgmentHistoryBlocked as exc:
        error = RuntimeGate1Blocked("history." + exc.field, exc.reason)
        error.reasons = copy.deepcopy(exc.reasons)
        raise error from exc
    except module.HumanInitialJudgmentHistoryError as exc:
        error = RuntimeGate1Error(exc.stage, exc.reason)
        error.reasons = copy.deepcopy(exc.reasons)
        if hasattr(exc, "secondary_errors"):
            error.secondary_errors = copy.deepcopy(exc.secondary_errors)
        raise error from exc


def _capture_initial_history_038(registry, static, expectations):
    module = _load_initial_history_038(static["project"][INITIAL_HISTORY_RELATIVE])
    _history_call_038(module, module._expectations, expectations)
    binding = registry["initial_judgment_history"]
    for key, expected in (("expected_namespace_relative", binding["namespace_relative"]),
                          ("expected_declared_scope", binding["declared_scope"])):
        _require_equivalent_030(expectations[key], expected, "history_expectations." + key)
    namespace = _history_namespace_capture_038(binding)
    path = Path(namespace["path"])
    store, raw = _history_call_038(module, module._load_store)
    components = _history_call_038(module, module._store_call, store, "", store._capture_components)
    if components["store_file_sha256"]["bytes"] != raw:
        _block("history.component_bindings", "store与开始加载缓冲不符")
    names = _history_call_038(module, module._members, store, path, expectations["expected_entries"])
    buffers, objects = {}, {}
    for i, (name, entry) in enumerate(zip(names, expectations["expected_entries"])):
        buffers[name], objects[name] = _history_call_038(module, module._capture_leaf, store, path / name, f"entries[{i}]")
        _require_equivalent_030(_sha_bytes(buffers[name]["manifest.json"]), entry["manifest_file_sha256"], f"history.entries[{i}].manifest_file_sha256")
    return {"module": module, "store": store, "components": components, "namespace": namespace,
            "expectations": copy.deepcopy(expectations), "buffers": buffers, "objects": objects}


def _bind_initial_history_038(ctx, result, history_source):
    module, store = ctx["module"], ctx["store"]
    _require_closed_keys(result, INITIAL_HISTORY_RETURN_KEYS, "history.verification")
    expected_inventory = {"namespace_relative": ctx["namespace"]["relative"],
        "declared_scope": ctx["expectations"]["expected_declared_scope"],
        "entries": copy.deepcopy(ctx["expectations"]["expected_entries"])}
    _require_equivalent_030(result["inventory"], expected_inventory, "history.inventory")
    verified = _require_list(result["verified_snapshots"], "history.verified_snapshots")
    if len(verified) != len(expected_inventory["entries"]):
        _block("history.verified_snapshots", "必须覆盖全部开始叶")
    components = {k: _sha_bytes(v["bytes"]) for k, v in ctx["components"].items()}
    records, expected_verified = [], []
    for i, (entry, actual) in enumerate(zip(expected_inventory["entries"], verified)):
        field = f"history.verified_snapshots[{i}]"
        _require_closed_keys(actual, ("relative", "verification"), field)
        name = entry["relative"]
        _require_equivalent_030(actual["relative"], name, field + ".relative")
        buffers, objects = ctx["buffers"][name], ctx["objects"][name]
        record, _ = _history_call_038(module, module._bind_verification, store, actual["verification"], buffers, objects, components, f"entries[{i}]")
        # Source records are the captured complete objects, not the returned index.
        record = objects["judgment_result.json"]["record"]
        records.append({"event_id": record["human_initial_judgment"]["event_id"], "batch_id": record["binding"]["batch_id"],
                        "record_fingerprint": fingerprint(record), "binding_fingerprint": fingerprint(record["binding"])})
        expected_verified.append({"relative": name, "verification": store._build_return(store.VERIFIED, objects["manifest.json"], buffers, objects)})
    records.sort(key=lambda v: v["event_id"].encode("utf-8"))
    expected = module._build_return(ctx["namespace"]["relative"], expected_inventory["declared_scope"], expected_inventory["entries"],
        dict(components, history_file_sha256=history_source["file_sha256"]), expected_verified, records)
    _require_equivalent_030(result, expected, "history.verification")
    return copy.deepcopy(expected["prior_history"])


def _capture_initial_sources_038(batch_dir, runtime_dir, params, history_expectations):
    initial = _resolve_approved_paths(batch_dir, runtime_dir, params["scope_dir"], params["event_relative"])
    _, leaf, gate1_scope, gate1_event, _ = initial
    if _lock_path_for(leaf).exists():
        _block("lock", "Gate1技术锁存在")
    _require_fixed_members(gate1_scope, [gate1_event.name], "scope")
    if FAILURE_FILE in _iter_dir(gate1_event, "initial.gate1"):
        _block("gate1.failure", "事件含失败现场")
    _require_fixed_members(gate1_event, EVENT_FILES, "event")
    _require_fixed_members(gate1_event / SNAPSHOT_DIR, SNAPSHOT_FILES, "snapshots")
    load = _load_dir_for(leaf)
    if not load.is_dir():
        _block("load_dir", "计算输出目录不存在")
    if FAILURE_FILE in _iter_dir(load, "initial.load"):
        _block("load.failure", "输出含失败现场")
    _require_fixed_members(load, APPROVED_LOAD_FILES, "load_dir")
    registry, sources = _capture_approved_sources_031(batch_dir, runtime_dir,
        **{k: params[k] for k in ("scope_dir", "event_relative", "database_path")}, initial_paths=initial)
    scope2, event2, lock2 = _gate2_paths_030(initial, params["gate2_event_relative"], saving=False)
    if FAILURE_FILE in _iter_dir(event2, "initial.gate2"):
        _block("gate2.failure", "事件含失败现场")
    _require_fixed_members(scope2, [event2.name], "gate2_scope")
    _require_fixed_members(event2, EVENT_FILES, "gate2_event")
    _require_fixed_members(event2 / SNAPSHOT_DIR, SNAPSHOT_FILES, "gate2_snapshots")
    gate2 = _capture_event_028(event2, reject_links=True)
    outputs = {}
    for key, directory, files in (("screen", _screen_dir_031(sources["leaf"]), SCREEN_FILES),
            ("crosscheck", _crosscheck_dir_032(sources["leaf"]), CROSSCHECK_FILES),
            ("facts", _facts_dir_033(sources["leaf"]), FACT_FILES)):
        if FAILURE_FILE in _iter_dir(directory, "initial." + key):
            _block(key + ".failure", "输出含失败现场")
        _require_fixed_members(directory, files, key + "_dir")
        captures = {}
        for name in files:
            _reject_reparse_chain(directory / name, key + "." + name)
            captures[name] = _capture_file(directory / name, "initial." + key + "." + name)
        outputs[key] = (directory, files, captures)
    history = _capture_initial_history_038(registry, sources["static_captures"], history_expectations)
    return {"registry": registry, "sources": sources, "gate2_scope": scope2, "gate2_event": event2,
            "gate2_lock": lock2, "gate2_captures": gate2, "outputs": outputs, "history": history}


def _initial_gate_link_038(decision, capture, registry, gate):
    _require_closed_keys(decision, ("record", "record_fingerprint"), gate + ".decision_result")
    record = _require_closed_keys(decision["record"], RECORD_KEYS_027, gate + ".record")
    actor = _require_closed_keys(record["actor"], ACTOR_KEYS_027, gate + ".actor")
    binding = _require_closed_keys(record["binding"], RECORD_BINDING_KEYS_027, gate + ".binding")
    for key, expected in (("gate", gate), ("batch_id", registry["batch_id"]), ("decision", "APPROVE"), ("decision_source", "HUMAN_GATE_DECISION")):
        _require_equivalent_030(record[key], expected, gate + ".record." + key)
    _require_equivalent_030(actor["actor_kind"], "HUMAN_DECLARED", gate + ".actor.actor_kind")
    _require_equivalent_030(binding["run_binding"], registry["run_binding"], gate + ".run_binding")
    _require_equivalent_030(binding["contract_binding"], registry["contract"], gate + ".contract_binding")
    _require_equivalent_030(decision["record_fingerprint"], fingerprint(record), gate + ".record_fingerprint")
    result = {"gate": gate, "batch_id": record["batch_id"], "event_id": record["event_id"],
        "record_fingerprint": fingerprint(record), "record_file_sha256": capture["file_sha256"],
        "materials_fingerprint": binding["materials_fingerprint"], "contract_binding": copy.deepcopy(binding["contract_binding"]),
        "run_binding": copy.deepcopy(binding["run_binding"]), "decision": record["decision"], "actor_kind": actor["actor_kind"]}
    if gate == "GATE2":
        prior = _require_closed_keys(record["prior_gate1"], ("record_fingerprint", "event_id", "batch_id", "gate", "decision", "actor_kind"), "GATE2.prior_gate1")
        result["prior_gate1_fingerprint"] = prior["record_fingerprint"]
    return result


def _assemble_initial_request_038(basis, expectations, evidence):
    materials = copy.deepcopy(basis)
    materials["materials_fingerprint"] = fingerprint(basis)
    return {"request_version": INITIAL_REQUEST_VERSION, "status": INITIAL_REQUEST_STATUS,
        "materials": materials, "expectations": copy.deepcopy(expectations), "evidence": copy.deepcopy(evidence),
        "boundaries": {key: False for key in INITIAL_BOUNDARIES}}


def _confirm_initial_sources_038(ctx):
    sources = ctx["sources"]
    _confirm_gate2_terminal_030(sources, ctx["gate2_scope"], ctx["gate2_event"], ctx["gate2_captures"], ctx["gate2_lock"])
    for key, (directory, files, captures) in ctx["outputs"].items():
        _require_fixed_members(directory, files, key + "_dir")
        for name, capture in captures.items():
            _recheck_capture(capture, key + "." + name)
        _require_fixed_members(directory, files, key + "_dir")
    history = ctx["history"]
    _confirm_history_namespace_038(history["namespace"])
    module = history["module"]
    _history_call_038(module, module._terminal_confirm, history["store"], Path(history["namespace"]["path"]), Path(history["namespace"]["path"]),
        history["expectations"]["expected_entries"], history["buffers"], history["components"],
        sources["static_captures"]["project"][INITIAL_HISTORY_RELATIVE]["bytes"])


def prepare_runtime_initial_judgment_request(batch_dir, runtime_dir, request_id, *, scope_dir, event_relative,
        database_path, gate2_event_relative, history_expectations) -> dict:
    """Read-only bound first-judgment request; no human submission or save action."""
    stage = "initial.paths"
    try:
        _utf8_038(request_id, "request_id")
        before_history = copy.deepcopy(history_expectations)
        params = dict(scope_dir=scope_dir, event_relative=event_relative, database_path=database_path, gate2_event_relative=gate2_event_relative)
        ctx = _capture_initial_sources_038(batch_dir, runtime_dir, params, history_expectations)
        registry, sources = ctx["registry"], ctx["sources"]
        gate1, gate2, facts, link1, link2 = _verify_initial_gates_038(
            batch_dir, runtime_dir, params, ctx, registry)
        stage = "initial.history"
        history_ctx = ctx["history"]; history_module = history_ctx["module"]
        history = _history_call_038(history_module, history_module.inspect_human_initial_judgment_history,
            Path(history_ctx["namespace"]["path"]), expectations=history_ctx["expectations"])
        prior = _bind_initial_history_038(history_ctx, history, sources["static_captures"]["project"][INITIAL_HISTORY_RELATIVE])
        if any(r["batch_id"] == registry["batch_id"] for r in prior["records"]):
            _block("prior_history.records", "当前声明域已有本批记录，不准备首版覆盖/修订")
        stage = "initial.materials"
        material = _materialize_initial_basis_038(
            ctx, registry, gate1, gate2, facts, link1, link2, request_id,
            prior["declared_scope"], fingerprint(prior), history)
        request = material["request"]
        _require_equivalent_030(request, {"request_version": INITIAL_REQUEST_VERSION, "status": INITIAL_REQUEST_STATUS,
            "materials": material["materials"], "expectations": material["expectations"],
            "evidence": material["evidence"], "boundaries": {k: False for k in INITIAL_BOUNDARIES}}, "initial.request")
        result = copy.deepcopy({"request": request, "request_sha256": fingerprint(request)})
        _require_equivalent_030(history_expectations, before_history, "history_expectations")
        stage = "initial.final"; _confirm_initial_sources_038(ctx)
        return result
    except (RuntimeGate1Blocked, RuntimeGate1Error):
        raise
    except Exception as exc:
        raise RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}") from exc


def _verify_initial_gates_038(batch_dir, runtime_dir, params, ctx, registry):
    """共享只读核验：当前 Gate1 有效性、Gate2 决定、fact 记录各真实一次。

    返回 (gate1, gate2, facts, link1, link2)；不冒充保存/批准，也不做额外只读复核。
    """
    sources = ctx["sources"]
    stage = "initial.gate1"
    try:
        gate1 = verify_gate1_effective_approval(batch_dir, runtime_dir,
                                                scope_dir=params["scope_dir"],
                                                event_relative=params["event_relative"])
        _require_closed_keys(gate1, VERIFY_KEYS, "gate1.verification")
        if gate1["effective"] is not True or gate1["reasons"] != []:
            _block("gate1.effective", "必须为真实核验的有效APPROVE且reasons为空")
        d1 = _parse_json_object(sources["event_captures"]["snapshots/decision_result.json"]["bytes"],
                                "gate1.decision_result")
        link1 = _initial_gate_link_038(d1, sources["event_captures"]["snapshots/decision_result.json"],
                                       registry, "GATE1")
        expected_g1 = {"verification_version": VERIFICATION_VERSION,
                       "batch_id": registry["batch_id"], "event_relative": params["event_relative"],
                       "record_fingerprint": link1["record_fingerprint"],
                       "record_file_sha256": link1["record_file_sha256"],
                       "run_binding_sha256": fingerprint(registry["run_binding"]),
                       "materials_fingerprint": link1["materials_fingerprint"],
                       "decision": "APPROVE", "actor_kind": "HUMAN_DECLARED",
                       "effective": True, "reasons": []}
        _require_equivalent_030(gate1, expected_g1, "gate1.verification")
        stage = "initial.gate2"
        gate2 = verify_runtime_gate2_decision(batch_dir, runtime_dir, **params)
        d2 = _parse_json_object(ctx["gate2_captures"]["snapshots/decision_result.json"]["bytes"],
                                "gate2.decision_result")
        _require_equivalent_030(gate2, dict(copy.deepcopy(d2),
                                            event_relative=params["gate2_event_relative"]),
                                "gate2.verification")
        link2 = _initial_gate_link_038(d2, ctx["gate2_captures"]["snapshots/decision_result.json"],
                                       registry, "GATE2")
        _require_equivalent_030(d2["record"]["prior_gate1"], {
            "record_fingerprint": link1["record_fingerprint"], "event_id": link1["event_id"],
            "batch_id": registry["batch_id"], "gate": "GATE1", "decision": "APPROVE",
            "actor_kind": "HUMAN_DECLARED"}, "gate2.prior_gate1")
        stage = "initial.facts"
        facts = inspect_gate2_fact_packet(batch_dir, runtime_dir, **params)
        fact_caps = ctx["outputs"]["facts"][2]
        packet = _parse_json_object(fact_caps[FACT_PACKET_FILE]["bytes"], "facts.packet")
        artifacts = _parse_json_object(fact_caps[ARTIFACTS_FILE]["bytes"], "facts.artifacts")
        expected_facts = {"stage_version": FACT_STAGE_VERSION, "status": "RT_FACT_PACKET_RECORDED",
                          "batch_id": registry["batch_id"],
                          "run_binding_sha256": fingerprint(registry["run_binding"]),
                          "artifacts": artifacts,
                          "boundaries": {k: False for k in FACT_BOUNDARIES}}
        _require_equivalent_030(facts, expected_facts, "facts.verification")
        for key, expected in (("packet_file_sha256", fact_caps[FACT_PACKET_FILE]["file_sha256"]),
                              ("packet_canonical_sha256", fingerprint(packet)),
                              ("started_file_sha256", fact_caps[STARTED_FILE]["file_sha256"]),
                              ("markdown_file_sha256", fact_caps[FACT_MARKDOWN_FILE]["file_sha256"]),
                              ("markdown_byte_size", fact_caps[FACT_MARKDOWN_FILE]["byte_size"])):
            _require_equivalent_030(artifacts[key], expected, "facts.artifacts." + key)
        return gate1, gate2, facts, link1, link2
    except (RuntimeGate1Blocked, RuntimeGate1Error):
        raise
    except Exception as exc:
        raise RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}") from exc


def _materialize_initial_basis_038(ctx, registry, gate1, gate2, facts, link1, link2, request_id,
                                   history_scope, history_prior_fingerprint, history_verification):
    """由本次真实来源固定九键材料正文/十二键独立预期/七键证据；不读取人类判断正文。"""
    stage = "initial.materials"
    try:
        sources = ctx["sources"]
        fact_caps = ctx["outputs"]["facts"][2]
        packet = _parse_json_object(fact_caps[FACT_PACKET_FILE]["bytes"], "facts.packet")
        mapping = {"facts.started": fact_caps[STARTED_FILE],
                   "facts.packet": fact_caps[FACT_PACKET_FILE],
                   "facts.markdown": fact_caps[FACT_MARKDOWN_FILE],
                   "facts.artifacts": fact_caps[ARTIFACTS_FILE],
                   "runtime.registry": sources["leaf_captures"]["registry"],
                   "contract": sources["static_captures"]["project"][CONTRACT_RELATIVE],
                   "gate1.record": sources["event_captures"]["snapshots/decision_result.json"],
                   "gate2.record": ctx["gate2_captures"]["snapshots/decision_result.json"]}
        files = sorted([{"role": role, "relative": _project_relative(Path(c["path"])),
                         "file_sha256": c["file_sha256"], "byte_size": c["byte_size"]}
                        for role, c in mapping.items()],
                       key=lambda v: v["relative"].encode("utf-8"))
        fact_snapshot = {"inspect_binding": {k: facts[k] for k in ("stage_version", "status",
                                                                   "batch_id", "run_binding_sha256")},
                         "packet": copy.deepcopy(packet),
                         "packet_canonical_sha256": fingerprint(packet),
                         "finding_ids": [v["finding_id"] for v in packet["findings"]],
                         "source_fingerprints": {k: packet["bindings"][k] for k in
                             ("workbook_sha256", "normalized_payload_sha256",
                              "screening_report_sha256", "crosscheck_report_sha256")}}
        basis = {"materials_version": "TASK-034-human-initial-judgment-materials-1.0",
                 "batch_id": registry["batch_id"], "runtime_version": RUNTIME_VERSION_028,
                 "entity": copy.deepcopy(packet["entity"]),
                 "contract_binding": copy.deepcopy(registry["contract"]),
                 "run_binding": copy.deepcopy(registry["run_binding"]),
                 "fact_snapshot": fact_snapshot, "gate_links": {"gate1": link1, "gate2": link2},
                 "files": files}
        # 独立预期在构造候选之前由已核验来源固定。
        fixed_materials = dict(copy.deepcopy(basis), materials_fingerprint=fingerprint(basis))
        expectations = {"expectations_version": "TASK-034-human-initial-judgment-expectations-1.0",
                        "expected_batch_id": registry["batch_id"],
                        "expected_request_id": request_id,
                        "expected_materials_fingerprint": fingerprint(basis),
                        "expected_contract": copy.deepcopy(registry["contract"]),
                        "expected_runtime_version": RUNTIME_VERSION_028,
                        "expected_run_binding": copy.deepcopy(registry["run_binding"]),
                        "expected_fact_binding": {k: copy.deepcopy(v) for k, v in fact_snapshot.items()
                                                  if k != "packet"},
                        "expected_gate_links": copy.deepcopy(basis["gate_links"]),
                        "expected_files": copy.deepcopy(files),
                        "expected_history_scope": history_scope,
                        "expected_prior_history_fingerprint": history_prior_fingerprint}
        regcap = sources["leaf_captures"]["registry"]
        effective = sources["static_captures"]["project"][CONTRACT_EFFECTIVE_RELATIVE]
        evidence = {"gate1_verification": copy.deepcopy(gate1),
                    "gate2_verification": copy.deepcopy(gate2),
                    "fact_verification": copy.deepcopy(facts),
                    "history_verification": copy.deepcopy(history_verification),
                    "registry_binding": {"registry_version": registry["registry_version"],
                        "registry_file_sha256": regcap["file_sha256"],
                        "registry_byte_size": regcap["byte_size"],
                        "run_binding_sha256": registry["run_binding_sha256"],
                        "initial_judgment_history": copy.deepcopy(registry["initial_judgment_history"])},
                    "contract_effective_record": {"relative": CONTRACT_EFFECTIVE_RELATIVE,
                        "file_sha256": effective["file_sha256"], "byte_size": effective["byte_size"]},
                    "files": copy.deepcopy(files)}
        request = _assemble_initial_request_038(copy.deepcopy(basis), copy.deepcopy(expectations),
                                                copy.deepcopy(evidence))
        return {"request": request, "materials": fixed_materials, "expectations": expectations,
                "evidence": evidence, "files": files, "fact_snapshot": fact_snapshot,
                "packet": packet}
    except (RuntimeGate1Blocked, RuntimeGate1Error):
        raise
    except Exception as exc:
        raise RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}") from exc



# --------------------------------------------------------------------------- TASK-040
# 合成运行的人类独立初判保存/只读恢复。只增加两个公开入口；真实批准仍 null，
# 不认证身份、不证明来源真实性、不开放 AI 或终判。
# 设计/案例身份由 TASK-039-R1 独立接受（RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_*）。
# 统计口径：save 直接 prepare 1 次 + 冻结 store.save 1 次 + 保存后 history 1 次；
# verify 直接 history 1 次、Gate1/Gate2/fact 各 1 次，不调用公开 prepare/store.save。

INITIAL_RECORDING_NOTE = (
    "仅表示合成运行的人类声明初判快照及当前材料/声明历史的本地技术核验；"
    "不批准执行，不认证身份，不证明业务真实性，不形成审计结论，不开放AI或终判。")
INITIAL_RECORDING_STAGE_VERSION = "TASK-039-runtime-human-initial-judgment-1.0"
INITIAL_RECORDING_SCOPE = "RUNTIME_CURRENT_MATERIALS_AND_DECLARED_HISTORY_ONLY"
INITIAL_SAVE_STATUS = "RT_HUMAN_INITIAL_JUDGMENT_RECORDED"
INITIAL_VERIFY_STATUS = "RT_HUMAN_INITIAL_JUDGMENT_VERIFIED"
INITIAL_STARTED_VERSION = "TASK-039-initial-judgment-start-1.0"
INITIAL_CONTEXT_VERSION = "TASK-039-initial-judgment-context-1.0"
INITIAL_RECEIPT_VERSION = "TASK-039-initial-judgment-receipt-1.0"
INITIAL_FAILURE_VERSION = "TASK-039-initial-judgment-failure-1.0"
INITIAL_LOCK_VERSION = "TASK-039-initial-judgment-lock-1.0"
INITIAL_ENVELOPE_SUFFIX = ".initial"
INITIAL_LOCK_SUFFIX = ".initial_judgment.lock"
INITIAL_STARTED_FILE = "started.json"
INITIAL_CONTEXT_FILE = "context.json"
INITIAL_RECEIPT_FILE = "receipt.json"
INITIAL_ENVELOPE_FILES = (INITIAL_CONTEXT_FILE, INITIAL_RECEIPT_FILE, INITIAL_STARTED_FILE)
INITIAL_SNAPSHOT_FILES = ("expectations.json", "judgment_result.json", "manifest.json",
                          "materials.json", "prior_history.json", "submission.json")
INITIAL_BOUNDARY_KEYS = ("workflow_connected", "execution_allowed", "next_step_allowed",
                         "ai_enabled", "identity_authenticated", "source_authenticity_proven",
                         "audit_conclusion_formed", "final_judgment_recorded",
                         "global_history_completeness_proven")
INITIAL_IDENTITY_KEYS = ("batch_id", "event_id", "request_id")
INITIAL_SUCCESS_KEYS = ("stage_version", "status", "scope", "identity", "record_relative",
                        "record_fingerprint", "manifest_file_sha256", "storage_verification",
                        "envelope_binding", "history_verification", "boundaries", "note")
INITIAL_STARTED_KEYS = ("started_version", "batch_id", "request_id", "record_relative",
                        "source_binding", "pre_history_binding", "boundaries")
INITIAL_SOURCE_BINDING_KEYS = ("source_batch_relative", "runtime_relative", "gate1_event_relative",
                               "gate2_event_relative", "database_relative", "registry_binding",
                               "contract_effective_record")
INITIAL_REGISTRY_BINDING_KEYS = ("registry_version", "registry_file_sha256", "registry_byte_size",
                                 "run_binding_sha256", "initial_judgment_history")
INITIAL_CONTRACT_RECORD_KEYS = ("relative", "file_sha256", "byte_size")
INITIAL_PRE_HISTORY_KEYS = ("namespace_relative", "declared_scope",
                            "prior_history_fingerprint")
INITIAL_CONTEXT_KEYS = ("context_version", "started_binding", "prepared_request",
                        "submission_snapshot", "prior_history_verification", "store_save_result",
                        "snapshot_files", "post_history_expectations",
                        "post_history_verification", "boundaries")
INITIAL_RECEIPT_KEYS = ("receipt_version", "identity", "record_relative",
                        "started_file_sha256", "context_file_sha256",
                        "snapshot_manifest_file_sha256", "post_history_fingerprint", "boundaries")
INITIAL_FILE_DESCRIPTOR_KEYS = ("relative", "byte_size", "file_sha256", "object_fingerprint")
INITIAL_ENVELOPE_BINDING_KEYS = ("relative", "files")
INITIAL_LOCK_KEYS = ("lock_version", "namespace_relative", "runtime_relative",
                     "record_relative", "request_id")
INITIAL_FAILURE_KEYS = ("failure_version", "scope", "identity", "stage", "classification",
                        "field", "reason", "reasons", "exception_type", "cause_chain",
                        "secondary_errors")
INITIAL_CHAIN_ITEM_KEYS = ("exception_type", "message")
INITIAL_STORE_RESULT_KEYS = ("status", "scope", "identity", "record_fingerprint",
                             "manifest_file_sha256", "technical_registration",
                             "component_bindings", "files", "boundaries", "snapshots",
                             "judgment_result")
INITIAL_STORE_FAILURE_KEYS = ("failure_version", "scope", "identity", "stage",
                              "classification", "field", "reason", "exception_type",
                              "cause_chain", "technical_registration")


def _u040_obj(value, field) -> dict:
    if type(value) is not dict:
        _block(field, f"必须为严格对象，实际 {type(value).__name__}")
    return value


def _u040_keys(value, keys, field) -> dict:
    obj = _u040_obj(value, field)
    for key in sorted(obj.keys(), key=lambda item: str(item).encode("utf-8")):
        if type(key) is not str or key not in keys:
            _block(field, f"含未允许的键 {key!r}")
    for key in keys:
        if key not in obj:
            _block(field, f"缺少必需键 {key!r}")
    return obj


def _u040_text(value, field) -> str:
    if type(value) is not str or value.strip() == "":
        _block(field, f"必须为非空原字符串，实际 {type(value).__name__}")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise RuntimeGate1Blocked(field, "必须为合法UTF-8") from exc
    return value


def _u040_leaf_name(value, field) -> str:
    _u040_text(value, field)
    if "\\" in value or ":" in value or "\x00" in value or "/" in value \
            or value in (".", ".."):
        _block(field, "必须为安全直接叶名")
    return value


def _u040_relative(value, field) -> str:
    _u040_text(value, field)
    if value.startswith("/") or "\\" in value or ":" in value or "\x00" in value:
        _block(field, "必须为安全项目相对POSIX原字符串")
    if any(part in ("", ".", "..") for part in value.split("/")):
        _block(field, "必须为安全项目相对POSIX原字符串")
    return value


def _u040_hash(value, field) -> str:
    if type(value) is not str or HASH_PATTERN.fullmatch(value) is None:
        _block(field, "必须是完整64位小写十六进制字符串")
    return value


def _u040_nonneg(value, field) -> int:
    if type(value) is not int or value < 0:
        _block(field, "必须为非负严格整数")
    return value


def _u040_false(value, field) -> None:
    if value is not False:
        _block(field, f"必须是严格 false，实际 {value!r}")


def _u040_const(value, expected, field) -> None:
    if type(value) is not type(expected) or value != expected:
        _block(field, f"必须精确等于 {expected!r}")


def _u040_diff(expected, actual, base="") -> str:
    """返回首个差异的机器路径（完整 canonical 比较的第一步），无差异返回 None。"""
    if type(expected) is not type(actual):
        return base or "<type>"
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual), key=lambda item: str(item).encode("utf-8")):
            path = (base + "." + key) if base else str(key)
            if key not in expected or key not in actual:
                return path
            found = _u040_diff(expected[key], actual[key], path)
            if found is not None:
                return found
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return (base + ".length") if base else "length"
        for index, (left, right) in enumerate(zip(expected, actual)):
            found = _u040_diff(left, right, (base + "[%d]" % index) if base else "[%d]" % index)
            if found is not None:
                return found
        return None
    try:
        same = canonical_json_bytes(expected) == canonical_json_bytes(actual)
    except (TypeError, ValueError):
        same = False
    return None if same else (base or "<value>")


def _u040_descriptor(relative, buffer, obj) -> dict:
    return {"relative": relative, "byte_size": len(buffer),
            "file_sha256": _sha_bytes(buffer), "object_fingerprint": fingerprint(obj)}


def _u040_normal_file(path, field) -> None:
    _reject_reparse_chain(path, field)
    try:
        info = path.lstat()
    except OSError as exc:
        raise RuntimeGate1Error("path", f"无法读取文件状态：{_safe_relative(path)}：{exc}") from exc
    if not path.is_file():
        _block(field, f"必须为普通文件：{_safe_relative(path)}")
    if os.name == "nt" and getattr(info, "st_file_attributes", 0) & 0x400:
        _block(field, f"不得为 reparse：{_safe_relative(path)}")


def _u040_chain_items(exc) -> list:
    items, node, seen = [], exc, set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        items.append({"exception_type": type(node).__name__, "message": str(node)})
        node = node.__cause__ or node.__context__
    if not items:
        items = [{"exception_type": type(exc).__name__, "message": str(exc)}]
    return items


def _u040_secondary(exc) -> list:
    value = getattr(exc, "secondary_errors", None)
    if isinstance(value, list):
        return copy.deepcopy(value)
    return []


def _u040_reasons(exc) -> list:
    value = getattr(exc, "reasons", None)
    if isinstance(value, list) and value:
        return copy.deepcopy(value)
    return [str(getattr(exc, "reason", str(exc)))]


def _write_initial_failure(envelope: Path, stage: str, exc, identity) -> None:
    """本次独占封装创建后一次性写定失败诊断；不覆盖既有/半写，不新增时间字段。"""
    classification = "BLOCKED" if isinstance(exc, RuntimeGate1Blocked) else "ERROR"
    field = getattr(exc, "field", None) if classification == "BLOCKED" else None
    payload = {"failure_version": INITIAL_FAILURE_VERSION,
               "scope": INITIAL_RECORDING_SCOPE,
               "identity": copy.deepcopy(identity),
               "stage": stage,
               "classification": classification,
               "field": field,
               "reason": str(getattr(exc, "reason", str(exc))),
               "reasons": _u040_reasons(exc),
               "exception_type": type(exc).__name__,
               "cause_chain": _u040_chain_items(exc),
               "secondary_errors": _u040_secondary(exc)}
    try:
        _require_closed_keys(payload, INITIAL_FAILURE_KEYS, "failure")
        _write_exclusive(envelope / FAILURE_FILE, _payload_bytes(payload), "write.failure")
    except Exception as nested:  # noqa: BLE001 - 诊断故障不替换主异常
        try:
            details = [{"exception_type": type(exc).__name__, "message": str(exc)}]
            if isinstance(getattr(nested, "args", None), tuple):
                details.append({"exception_type": type(nested).__name__, "message": str(nested)})
            exc.secondary_errors = _u040_secondary(exc) + details
        except Exception:  # noqa: BLE001
            pass


# ---- Windows 真实独占句柄锁（标准库 ctypes；不使用路径盲删或创建即 DELETE_ON_CLOSE）

_U040_WIN: dict = {}


def _u040_win() -> dict:
    if _U040_WIN:
        return _U040_WIN
    import ctypes
    from ctypes import wintypes

    class FILE_ID_INFO(ctypes.Structure):
        _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong),
                    ("FileId", ctypes.c_ubyte * 16)]

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [("dwFileAttributes", wintypes.DWORD),
                    ("ftCreationTime", wintypes.FILETIME),
                    ("ftLastAccessTime", wintypes.FILETIME),
                    ("ftLastWriteTime", wintypes.FILETIME),
                    ("dwVolumeSerialNumber", wintypes.DWORD),
                    ("nFileSizeHigh", wintypes.DWORD),
                    ("nFileSizeLow", wintypes.DWORD),
                    ("nNumberOfLinks", wintypes.DWORD),
                    ("nFileIndexHigh", wintypes.DWORD),
                    ("nFileIndexLow", wintypes.DWORD)]

    class FILE_DISPOSITION_INFO(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOLEAN)]

    class FILE_DISPOSITION_INFO_EX(ctypes.Structure):
        _fields_ = [("Flags", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.HANDLE]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                                 ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel.WriteFile.restype = wintypes.BOOL
    kernel.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel.ReadFile.restype = wintypes.BOOL
    kernel.SetFilePointer.argtypes = [wintypes.HANDLE, wintypes.LONG, wintypes.LPVOID,
                                      wintypes.DWORD]
    kernel.SetFilePointer.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE,
                                                  ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                    wintypes.LPVOID, wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                  wintypes.LPVOID, wintypes.DWORD]
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    _U040_WIN.update({
        "ctypes": ctypes, "wintypes": wintypes, "kernel": kernel,
        "FILE_ID_INFO": FILE_ID_INFO, "BY_HANDLE_FILE_INFORMATION": BY_HANDLE_FILE_INFORMATION,
        "FILE_DISPOSITION_INFO": FILE_DISPOSITION_INFO,
        "FILE_DISPOSITION_INFO_EX": FILE_DISPOSITION_INFO_EX,
        "INVALID": ctypes.c_void_p(-1).value,
        "GENERIC_READ": 0x80000000, "GENERIC_WRITE": 0x40000000, "DELETE": 0x00010000,
        "FILE_SHARE_READ": 0x00000001, "FILE_SHARE_ALL": 0x00000007,
        "CREATE_NEW": 1, "OPEN_EXISTING": 3, "FILE_ATTRIBUTE_NORMAL": 0x00000080,
        "FILE_BEGIN": 0, "FILE_READ_ATTRIBUTES": 0x00000080,
        "FileIdInfo": 18, "FileDispositionInfo": 4, "FileDispositionInfoEx": 21,
        "FILE_DISPOSITION_FLAG_DELETE": 0x00000001,
        "FILE_DISPOSITION_FLAG_POSIX_SEMANTICS": 0x00000002,
    })
    return _U040_WIN


def _u040_open_handle(path: Path, *, create_new: bool) -> int:
    win = _u040_win()
    ctypes = win["ctypes"]
    access = win["GENERIC_READ"] | win["GENERIC_WRITE"] | win["DELETE"]
    share = win["FILE_SHARE_READ"]
    disposition = win["CREATE_NEW"] if create_new else win["OPEN_EXISTING"]
    handle = win["kernel"].CreateFileW(str(path), access, share, None, disposition,
                                       win["FILE_ATTRIBUTE_NORMAL"], None)
    if handle is None or handle == win["INVALID"]:
        code = ctypes.get_last_error()
        if create_new and code in (80, 183):
            _block("lock", f"技术锁已存在，拒绝并发保存：{_safe_relative(path)}")
        raise RuntimeGate1Error("lock.acquire",
                                f"无法取得独占句柄：{_safe_relative(path)}：WinError {code}")
    return handle


def _u040_close_handle(handle) -> None:
    if handle is None:
        return
    _u040_win()["kernel"].CloseHandle(handle)


def _u040_handle_write(handle, buffer: bytes) -> None:
    """对本次真实独占句柄写整份缓冲；失败抛 OSError（保留已出现半写）。"""
    win = _u040_win()
    ctypes = win["ctypes"]
    chunk = ctypes.create_string_buffer(buffer, len(buffer))
    written = win["wintypes"].DWORD(0)
    if not win["kernel"].WriteFile(handle, ctypes.cast(chunk, win["wintypes"].LPCVOID),
                                   len(buffer), ctypes.byref(written), None):
        raise OSError(ctypes.get_last_error(), "WriteFile 失败")
    if written.value != len(buffer):
        raise OSError(5, f"写入长度不符：{written.value}/{len(buffer)}")


def _u040_handle_readback(handle, size: int) -> bytes:
    win = _u040_win()
    ctypes = win["ctypes"]
    if win["kernel"].SetFilePointer(handle, 0, None, win["FILE_BEGIN"]) == 0xFFFFFFFF:
        code = ctypes.get_last_error()
        if code != 0:
            raise OSError(code, "SetFilePointer 失败")
    buffer = ctypes.create_string_buffer(max(size, 1))
    read = win["wintypes"].DWORD(0)
    if not win["kernel"].ReadFile(handle, ctypes.cast(buffer, win["wintypes"].LPVOID),
                                  size, ctypes.byref(read), None):
        raise OSError(ctypes.get_last_error(), "ReadFile 失败")
    return buffer.raw[:read.value]


def _u040_handle_stat(handle) -> dict:
    win = _u040_win()
    ctypes = win["ctypes"]
    info = win["BY_HANDLE_FILE_INFORMATION"]()
    if not win["kernel"].GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise OSError(ctypes.get_last_error(), "GetFileInformationByHandle 失败")
    return {"attributes": int(info.dwFileAttributes),
            "byte_size": (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow),
            "volume": int(info.dwVolumeSerialNumber),
            "file_index": (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow)}


def _u040_handle_file_id(handle) -> dict:
    win = _u040_win()
    ctypes = win["ctypes"]
    info = win["FILE_ID_INFO"]()
    if win["kernel"].GetFileInformationByHandleEx(
            handle, win["FileIdInfo"], ctypes.byref(info), ctypes.sizeof(info)):
        return {"volume": int(info.VolumeSerialNumber), "file_id": bytes(info.FileId).hex()}
    stat = _u040_handle_stat(handle)
    return {"volume": stat["volume"], "file_id": "%016x" % stat["file_index"]}


def _u040_path_file_id(path: Path) -> dict:
    win = _u040_win()
    ctypes = win["ctypes"]
    handle = win["kernel"].CreateFileW(
        str(path), win["FILE_READ_ATTRIBUTES"], win["FILE_SHARE_ALL"], None,
        win["OPEN_EXISTING"], win["FILE_ATTRIBUTE_NORMAL"], None)
    if handle is None or handle == win["INVALID"]:
        raise OSError(ctypes.get_last_error(), "无法打开技术锁路径核对身份")
    try:
        return _u040_handle_file_id(handle)
    finally:
        _u040_close_handle(handle)


def _u040_handle_delete(handle) -> None:
    """只对本次持有句柄设置删除标记（优先 POSIX 语义），不按路径 unlink。"""
    win = _u040_win()
    ctypes = win["ctypes"]
    flags = win["FILE_DISPOSITION_FLAG_DELETE"] | win["FILE_DISPOSITION_FLAG_POSIX_SEMANTICS"]
    extended = win["FILE_DISPOSITION_INFO_EX"](flags)
    if win["kernel"].SetFileInformationByHandle(
            handle, win["FileDispositionInfoEx"], ctypes.byref(extended), ctypes.sizeof(extended)):
        return
    plain = win["FILE_DISPOSITION_INFO"](1)
    if win["kernel"].SetFileInformationByHandle(
            handle, win["FileDispositionInfo"], ctypes.byref(plain), ctypes.sizeof(plain)):
        return
    raise OSError(ctypes.get_last_error(), "设置按句柄删除标记失败")


def _release_initial_lock(lock: dict):
    """成功路径释放：核对原父/路径file ID/句柄字节后，按句柄删除并确认；返回错误文本或 None。"""
    path, handle = lock["path"], lock.get("handle")
    try:
        _reject_reparse_chain(path, "release.lock")
        if not path.exists():
            return "技术锁原路径已不存在（保留实际状态，不伪造重建）"
        if _u040_path_file_id(path) != lock["file_id"]:
            return "技术锁路径文件身份已变化（替代锁，保留现场，不按路径删除）"
        if _path_identity(path.parent, "release.lock") != lock["parent_identity"]:
            return "技术锁父目录身份已变化（保留现场，不删除）"
        if _u040_handle_stat(handle)["attributes"] != lock["attributes"]:
            return "技术锁持柄属性已变化（保留现场，不删除）"
        if _u040_handle_readback(handle, lock["byte_size"]) != lock["buffer"]:
            return "技术锁持有句柄字节已变化（保留现场，不删除）"
        _u040_handle_delete(handle)
        _u040_close_handle(handle)
        lock["handle"] = None
        if path.exists():
            return "按句柄设置删除并关闭后技术锁仍存在（不视为已释放）"
        return None
    except Exception as exc:  # noqa: BLE001 - 释放失败保留实际剩余状态
        return f"{type(exc).__name__}: {exc}"
    finally:
        if lock.get("handle") is not None:
            _u040_close_handle(lock["handle"])
            lock["handle"] = None


def _abandon_initial_lock(lock: dict) -> None:
    """失败路径：不设置删除标记，保留现存锁/半写，仅关闭本次资源句柄。"""
    handle = lock.get("handle")
    if handle is not None:
        try:
            _u040_close_handle(handle)
        finally:
            lock["handle"] = None


def _acquire_initial_lock(lock_path: Path, *, namespace_relative: str, runtime_relative: str,
                          record_relative: str, request_id: str) -> dict:
    _reject_reparse_chain(lock_path, "lock")
    if lock_path.exists():
        _block("lock", f"技术锁已存在，拒绝并发保存：{_safe_relative(lock_path)}")
    parent_identity = _path_identity(lock_path.parent, "lock.acquire")
    payload = {"lock_version": INITIAL_LOCK_VERSION,
               "namespace_relative": namespace_relative,
               "runtime_relative": runtime_relative,
               "record_relative": record_relative,
               "request_id": request_id}
    buffer = _payload_bytes(payload)
    handle = _u040_open_handle(lock_path, create_new=True)
    lock = {"path": lock_path, "buffer": buffer, "handle": handle,
            "parent_identity": parent_identity, "payload": payload}
    confirmed = False
    try:
        stat = _u040_handle_stat(handle)
        lock.update(attributes=stat["attributes"], byte_size=len(buffer))
        lock["file_id"] = _u040_handle_file_id(handle)
        _u040_handle_write(handle, buffer)
        actual = _u040_handle_readback(handle, len(buffer))
        if actual != buffer:
            _block("lock", "技术锁读回字节与本次待写缓冲不一致")
        confirmed = True
        return lock
    except (RuntimeGate1Blocked, RuntimeGate1Error):
        raise
    except OSError as exc:
        raise RuntimeGate1Error("lock.acquire", f"技术锁写入/读回失败（保留现场）：{exc}") from exc
    finally:
        if not confirmed:
            _abandon_initial_lock(lock)


def _confirm_initial_lock(lock: dict, stage: str) -> None:
    path, handle = lock["path"], lock.get("handle")
    _reject_reparse_chain(path, stage)
    if handle is None or not path.exists():
        _block("lock", "本次持有的技术锁原文件或句柄已不存在")
    if _u040_path_file_id(path) != lock["file_id"]:
        _block("lock", "技术锁原路径 file ID 与本次持有句柄身份不一致")
    if _path_identity(path.parent, stage) != lock["parent_identity"]:
        _block("lock", "技术锁父目录身份较取得时变化")
    if _u040_handle_stat(handle)["attributes"] != lock["attributes"]:
        _block("lock", "技术锁持柄文件属性较取得时变化")
    if _u040_handle_readback(handle, lock["byte_size"]) != lock["buffer"]:
        _block("lock", "技术锁持柄字节与本次缓冲不一致")


def _initial_envelope_path(leaf: Path) -> Path:
    """运行封装固定在登记（runtime 叶）同级 `<登记叶名>.initial/`，不进入历史直接叶枚举。"""
    return leaf.parent / (leaf.name + INITIAL_ENVELOPE_SUFFIX)


def _initial_lock_path(namespace_path: Path) -> Path:
    """技术锁固定在 namespace 同级 `<namespace叶名>.initial_judgment.lock`。"""
    return namespace_path.parent / (namespace_path.name + INITIAL_LOCK_SUFFIX)


def _resolve_existing_scope_040(scope_dir, registry) -> Path:
    if not isinstance(scope_dir, (str, os.PathLike)):
        _block("scope_dir", f"必须是路径，实际 {type(scope_dir).__name__}")
    raw = Path(scope_dir)
    _reject_reparse_chain(raw, "scope_dir")
    try:
        scope = raw.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.scope_dir", f"{raw}：{exc}") from exc
    _require_descendant(scope, GATE1_RECORDS_ROOT, "scope_dir")
    if not scope.is_dir():
        _block("scope_dir", "Gate1 记录 scope 必须既存正常目录（该批次尚无已保存事件）")
    if registry["scope_ref"] != _project_relative(scope):
        _block("scope_dir", f"只接受恰等于登记 scope_ref {registry['scope_ref']!r} 的 scope")
    return scope


def _existing_gate1_event_040(scope: Path, event_relative) -> Path:
    _u040_text(event_relative, "event_relative")
    if event_relative.startswith("/") or ":" in event_relative or "\\" in event_relative:
        _block("event_relative", "必须是安全项目相对路径原串")
    raw = PROJECT_ROOT / event_relative
    _reject_reparse_chain(raw, "event_relative")
    try:
        event = raw.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.event_relative", f"{raw}：{exc}") from exc
    if event != raw:
        _block("event_relative", "解析后与显式项目相对路径不一致")
    _require_descendant(event, scope, "event_relative")
    if not event.is_dir():
        _block("event_relative", f"Gate1 事件目录不存在：{event_relative}")
    _require_fixed_members(scope, [event.name], "scope_dir")
    return event


def _initial_target_040(record_relative, namespace: dict, *, must_exist: bool) -> tuple:
    _u040_relative(record_relative, "record_relative")
    namespace_relative = namespace["relative"]
    prefix = namespace_relative + "/"
    if not record_relative.startswith(prefix):
        _block("record_relative", "必须恰为已绑定 namespace_relative 加一个安全直接叶段")
    leaf_name = _u040_leaf_name(record_relative[len(prefix):], "record_relative")
    raw = PROJECT_ROOT / record_relative
    _reject_reparse_chain(raw, "record_relative")
    try:
        leaf = raw.resolve()
    except OSError as exc:
        raise RuntimeGate1Error("resolve.record_relative", f"{raw}：{exc}") from exc
    if leaf != raw:
        _block("record_relative", "原路径链先于消段检查：解析后与显式项目相对路径不一致")
    if _project_relative(leaf) != record_relative:
        _block("record_relative", "必须为安全项目相对POSIX原串（不折叠/不改大小写）")
    if _project_relative(leaf.parent) != namespace_relative:
        _block("record_relative", "父域必须精确等于已绑定声明域")
    if not leaf.parent.is_dir():
        _block("record_relative", "声明域目录必须既存")
    exists = leaf.exists()
    if must_exist:
        if not exists or not leaf.is_dir():
            _block("record_relative", f"恢复目标叶必须存在：{record_relative}")
    elif exists:
        _block("record_relative", f"保存目标叶必须从未存在（含空目录）：{record_relative}")
    return leaf, leaf_name


def _expected_history_040(history_ctx, history_source, *, entries=None, extra=None) -> dict:
    """由本次开始同缓冲叶文件构造完整历史核验对象；不调用 history/store.verify。"""
    module, store = history_ctx["module"], history_ctx["store"]
    declared = copy.deepcopy(entries) if entries is not None else \
        copy.deepcopy(history_ctx["expectations"]["expected_entries"])
    verified, records = [], []
    for entry in declared:
        name = entry["relative"]
        if name not in history_ctx["buffers"]:
            _block("history.expected_entries", f"缺少本次开始叶缓冲：{name}")
        buffers, objects = history_ctx["buffers"][name], history_ctx["objects"][name]
        _require_closed_keys(entry, ("relative", "manifest_file_sha256"), "history.expected_entries[]")
        if _sha_bytes(buffers["manifest.json"]) != entry["manifest_file_sha256"]:
            _block("history.expected_entries[%s].manifest_file_sha256" % name,
                   "与本次开始同缓冲 manifest 字节不一致")
        verified.append({"relative": name, "verification": store._build_return(
            store.VERIFIED, objects["manifest.json"], buffers, objects)})
        record = objects["judgment_result.json"]["record"]
        records.append(_history_index_item_040(record))
    for name, verification, record in (extra or []):
        verified.append({"relative": name, "verification": copy.deepcopy(verification)})
        records.append(_history_index_item_040(record))
    verified.sort(key=lambda v: v["relative"].encode("utf-8"))
    records.sort(key=lambda v: v["event_id"].encode("utf-8"))
    components = {k: _sha_bytes(v["bytes"]) for k, v in history_ctx["components"].items()}
    return module._build_return(history_ctx["namespace"]["relative"],
                                history_ctx["expectations"]["expected_declared_scope"],
                                declared,
                                dict(components, history_file_sha256=history_source["file_sha256"]),
                                verified, records)


def _history_index_item_040(record: dict) -> dict:
    return {"event_id": record["human_initial_judgment"]["event_id"],
            "batch_id": record["binding"]["batch_id"],
            "record_fingerprint": fingerprint(record),
            "binding_fingerprint": fingerprint(record["binding"])}


def _expected_initial_request_040(ctx, registry, params, request_id) -> dict:
    """仅由本次开始同缓冲来源构造独立预期请求（不调用任何业务入口或核心）。"""
    stage = "audit.result"
    try:
        sources = ctx["sources"]
        d1 = _parse_json_object(sources["event_captures"]["snapshots/decision_result.json"]["bytes"],
                                "gate1.decision_result")
        link1 = _initial_gate_link_038(d1, sources["event_captures"]["snapshots/decision_result.json"],
                                       registry, "GATE1")
        gate1 = {"verification_version": VERIFICATION_VERSION, "batch_id": registry["batch_id"],
                 "event_relative": params["event_relative"],
                 "record_fingerprint": link1["record_fingerprint"],
                 "record_file_sha256": link1["record_file_sha256"],
                 "run_binding_sha256": fingerprint(registry["run_binding"]),
                 "materials_fingerprint": link1["materials_fingerprint"],
                 "decision": "APPROVE", "actor_kind": "HUMAN_DECLARED",
                 "effective": True, "reasons": []}
        d2 = _parse_json_object(ctx["gate2_captures"]["snapshots/decision_result.json"]["bytes"],
                                "gate2.decision_result")
        gate2 = dict(copy.deepcopy(d2), event_relative=params["gate2_event_relative"])
        link2 = _initial_gate_link_038(d2, ctx["gate2_captures"]["snapshots/decision_result.json"],
                                       registry, "GATE2")
        _require_equivalent_030(d2["record"]["prior_gate1"], {
            "record_fingerprint": link1["record_fingerprint"], "event_id": link1["event_id"],
            "batch_id": registry["batch_id"], "gate": "GATE1", "decision": "APPROVE",
            "actor_kind": "HUMAN_DECLARED"}, "gate2.prior_gate1")
        fact_caps = ctx["outputs"]["facts"][2]
        packet = _parse_json_object(fact_caps[FACT_PACKET_FILE]["bytes"], "facts.packet")
        artifacts = _parse_json_object(fact_caps[ARTIFACTS_FILE]["bytes"], "facts.artifacts")
        facts = {"stage_version": FACT_STAGE_VERSION, "status": "RT_FACT_PACKET_RECORDED",
                 "batch_id": registry["batch_id"],
                 "run_binding_sha256": fingerprint(registry["run_binding"]),
                 "artifacts": artifacts, "boundaries": {k: False for k in FACT_BOUNDARIES}}
        for key, expected in (("packet_file_sha256", fact_caps[FACT_PACKET_FILE]["file_sha256"]),
                              ("packet_canonical_sha256", fingerprint(packet)),
                              ("started_file_sha256", fact_caps[STARTED_FILE]["file_sha256"]),
                              ("markdown_file_sha256", fact_caps[FACT_MARKDOWN_FILE]["file_sha256"]),
                              ("markdown_byte_size", fact_caps[FACT_MARKDOWN_FILE]["byte_size"])):
            _require_equivalent_030(artifacts[key], expected, "facts.artifacts." + key)
        history = _expected_history_040(
            ctx["history"], sources["static_captures"]["project"][INITIAL_HISTORY_RELATIVE])
        prior = copy.deepcopy(history["prior_history"])
        material = _materialize_initial_basis_038(
            ctx, registry, gate1, gate2, facts, link1, link2, request_id,
            prior["declared_scope"], fingerprint(prior), history)
        request = material["request"]
        return {"request": request, "request_sha256": fingerprint(request), "gate1": gate1,
                "gate2": gate2, "facts": facts, "history": history, "material": material,
                "prior_history": prior}
    except (RuntimeGate1Blocked, RuntimeGate1Error):
        raise
    except Exception as exc:
        raise RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}") from exc


def _initial_store_components_040(history_ctx) -> dict:
    return {key: _sha_bytes(value["bytes"]) for key, value in history_ctx["components"].items()}


def _validate_initial_store_result_040(result, captures, prepared, prior_history, components) -> dict:
    """把本次真实冻结 store 十一键返回与本次实读六缓冲及输入闭合。"""
    value = _u040_keys(result, INITIAL_STORE_RESULT_KEYS, "store_result")
    _u040_const(value["status"], "HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_STORED", "store_result.status")
    _u040_const(value["scope"], "STORED_SNAPSHOTS_ONLY", "store_result.scope")
    identity = _u040_keys(value["identity"], INITIAL_IDENTITY_KEYS, "store_result.identity")
    for key in INITIAL_IDENTITY_KEYS:
        _u040_text(identity[key], "store_result.identity." + key)
    _u040_hash(value["record_fingerprint"], "store_result.record_fingerprint")
    _u040_hash(value["manifest_file_sha256"], "store_result.manifest_file_sha256")
    if value["manifest_file_sha256"] != captures["manifest.json"]["file_sha256"]:
        _block("store_result.manifest_file_sha256", "与本次实读 manifest 字节不一致")
    if type(value["files"]) is not list or len(value["files"]) != 6:
        _block("store_result.files", "必须恰六项")
    names = []
    for index, raw in enumerate(value["files"]):
        entry = _u040_keys(raw, INITIAL_FILE_DESCRIPTOR_KEYS, "store_result.files[%d]" % index)
        name = _u040_text(entry["relative"], "store_result.files[%d].relative" % index)
        names.append(name)
        capture = captures.get(name)
        if capture is None:
            _block("store_result.files[%d]" % index, f"未知 payload {name!r}")
        _u040_nonneg(entry["byte_size"], "store_result.files[%d].byte_size" % index)
        _u040_hash(entry["file_sha256"], "store_result.files[%d].file_sha256" % index)
        _u040_hash(entry["object_fingerprint"], "store_result.files[%d].object_fingerprint" % index)
        if entry["byte_size"] != capture["byte_size"] \
                or entry["file_sha256"] != capture["file_sha256"]:
            _block("store_result.files[%d]" % index, "与本次实读字节不一致")
        parsed = _parse_json_object(capture["bytes"], name)
        if entry["object_fingerprint"] != fingerprint(parsed):
            _block("store_result.files[%d].object_fingerprint" % index, "与同缓冲对象指纹不一致")
    if names != list(INITIAL_SNAPSHOT_FILES):
        _block("store_result.files", "必须恰为六快照固定名单")
    if _u040_diff(components, value["component_bindings"]) is not None:
        _block("store_result.component_bindings", "与本次实读冻结组件不一致")
    for key in sorted(value["boundaries"]):
        _u040_false(value["boundaries"][key], "store_result.boundaries." + key)
    if set(value["boundaries"]) != set(_frozen_store_boundaries_040()):
        _block("store_result.boundaries", "边界键集合不符")
    snapshots = _u040_keys(value["snapshots"], ("submission", "materials", "expectations",
                                                "prior_history"), "store_result.snapshots")
    for key, expected in (("submission", prepared["_submission"]),
                          ("materials", prepared["request"]["materials"]),
                          ("expectations", prepared["request"]["expectations"]),
                          ("prior_history", prior_history)):
        if _u040_diff(expected, snapshots[key]) is not None:
            _block("store_result.snapshots." + key, "与本次原输入/独立预期不一致")
    judgment = _u040_keys(value["judgment_result"], ("record", "record_fingerprint"),
                          "store_result.judgment_result")
    record = _u040_keys(judgment["record"], ("record_version", "record_status", "mode", "binding",
                                             "human_initial_judgment", "decided_at_source",
                                             "history_binding", "boundaries", "note"),
                        "store_result.judgment_result.record")
    _u040_hash(judgment["record_fingerprint"], "store_result.judgment_result.record_fingerprint")
    if judgment["record_fingerprint"] != fingerprint(record) \
            or judgment["record_fingerprint"] != value["record_fingerprint"]:
        _block("store_result.judgment_result.record_fingerprint", "与 record 正文规范指纹不一致")
    _u040_text(record["record_status"], "store_result.judgment_result.record.record_status")
    _u040_false(record["boundaries"].get("persisted"),
                "store_result.judgment_result.record.boundaries.persisted")
    human = record["human_initial_judgment"]
    binding = record["binding"]
    for key, expected in (("event_id", human["event_id"]),
                          ("batch_id", binding["batch_id"]),
                          ("request_id", binding["request_id"])):
        if identity[key] != expected:
            _block("store_result.identity." + key, "与记录正文不一致")
    return copy.deepcopy(value)


def _frozen_store_boundaries_040():
    return ("workflow_connected", "execution_allowed", "next_step_allowed", "ai_enabled",
            "identity_authenticated", "source_authenticity_proven", "audit_conclusion_formed",
            "final_judgment_recorded", "complete_history_verified")


def _audit_initial_success_040(candidate, expected, store_result, history_verification,
                               envelope_captures, envelope_files, expected_identity,
                               record_relative, envelope_relative, expected_status) -> None:
    """先封闭 schema/严格类型（Blocked `result.*`），再做完整 canonical 比较，
    最后做内部内容审核（非空问题 → Error `audit.result`，不把 false 审核硬填 true）。"""
    value = _u040_keys(candidate, INITIAL_SUCCESS_KEYS, "result")
    _u040_const(value["stage_version"], INITIAL_RECORDING_STAGE_VERSION, "result.stage_version")
    _u040_const(value["scope"], INITIAL_RECORDING_SCOPE, "result.scope")
    _u040_const(value["note"], INITIAL_RECORDING_NOTE, "result.note")
    _u040_const(value["status"], expected_status, "result.status")
    identity = _u040_keys(value["identity"], INITIAL_IDENTITY_KEYS, "result.identity")
    for key in INITIAL_IDENTITY_KEYS:
        _u040_text(identity[key], "result.identity." + key)
    _u040_relative(value["record_relative"], "result.record_relative")
    _u040_hash(value["record_fingerprint"], "result.record_fingerprint")
    _u040_hash(value["manifest_file_sha256"], "result.manifest_file_sha256")
    _u040_keys(value["storage_verification"], INITIAL_STORE_RESULT_KEYS,
               "result.storage_verification")
    _u040_keys(value["history_verification"], INITIAL_HISTORY_RETURN_KEYS,
               "result.history_verification")
    _u040_keys(value["boundaries"], INITIAL_BOUNDARY_KEYS, "result.boundaries")
    for key in INITIAL_BOUNDARY_KEYS:
        _u040_false(value["boundaries"][key], "result.boundaries." + key)
    envelope = _u040_keys(value["envelope_binding"], INITIAL_ENVELOPE_BINDING_KEYS,
                          "result.envelope_binding")
    _u040_relative(envelope["relative"], "result.envelope_binding.relative")
    if type(envelope["files"]) is not list or len(envelope["files"]) != 3:
        _block("result.envelope_binding.files", "必须恰三项描述")
    for index, item in enumerate(envelope["files"]):
        _validate_descriptor_040(item, "result.envelope_binding.files[%d]" % index)
    diff = _u040_diff(expected, candidate)
    if diff is not None:
        _block("result." + diff, "候选与本次独立构造的成功预期完整规范字节不一致")
    problems = []
    if canonical_json_bytes(identity) != canonical_json_bytes(expected_identity):
        problems.append("identity")
    if value["record_relative"] != record_relative:
        problems.append("record_relative")
    if value["record_fingerprint"] != store_result["record_fingerprint"]:
        problems.append("record_fingerprint")
    if value["manifest_file_sha256"] != store_result["manifest_file_sha256"]:
        problems.append("manifest_file_sha256")
    stable_saved = {key: item for key, item in store_result.items() if key != "status"}
    stable_now = {key: item for key, item in value["storage_verification"].items()
                  if key != "status"}
    if _u040_diff(stable_saved, stable_now) is not None:
        problems.append("storage_verification")
    if _u040_diff(history_verification, value["history_verification"]) is not None:
        problems.append("history_verification")
    if envelope["relative"] != envelope_relative:
        problems.append("envelope_binding.relative")
    if _u040_diff(envelope_files, envelope["files"]) is not None:
        problems.append("envelope_binding.files")
    actual_files = sorted(
        [_u040_descriptor(_project_relative(Path(capture["path"])), capture["bytes"],
                          _parse_json_object(capture["bytes"], Path(capture["path"]).name))
         for capture in envelope_captures.values()],
        key=lambda item: item["relative"].encode("utf-8"))
    if _u040_diff(actual_files, envelope["files"]) is not None:
        problems.append("envelope_binding.actual_files")
    for name, capture in envelope_captures.items():
        relative = _project_relative(Path(capture["path"]))
        entry = next((item for item in envelope["files"]
                      if item["relative"] == relative), None)
        if entry is None or entry["file_sha256"] != capture["file_sha256"] \
                or entry["byte_size"] != capture["byte_size"]:
            problems.append("envelope_binding." + name)
    if problems:
        error = RuntimeGate1Error("audit.result", "候选内部内容审核失败：" + ", ".join(problems))
        error.reasons = problems
        raise error


def _initial_started_040(registry, request_id, record_relative, batch_path, leaf,
                         event_relative, gate2_event_relative, sources, namespace,
                         prior_history) -> dict:
    """构造 started（S4）候选；不填未知人类 event/actor，不序列化非法 submission。"""
    return {"started_version": INITIAL_STARTED_VERSION,
            "batch_id": registry["batch_id"], "request_id": request_id,
            "record_relative": record_relative,
            "source_binding": {
                "source_batch_relative": _project_relative(batch_path),
                "runtime_relative": _project_relative(leaf),
                "gate1_event_relative": event_relative,
                "gate2_event_relative": gate2_event_relative,
                "database_relative": _project_relative(
                    Path(sources["database_capture"]["path"])),
                "registry_binding": {
                    "registry_version": registry["registry_version"],
                    "registry_file_sha256": sources["leaf_captures"]["registry"]["file_sha256"],
                    "registry_byte_size": sources["leaf_captures"]["registry"]["byte_size"],
                    "run_binding_sha256": registry["run_binding_sha256"],
                    "initial_judgment_history": copy.deepcopy(
                        registry["initial_judgment_history"])},
                "contract_effective_record": {
                    "relative": CONTRACT_EFFECTIVE_RELATIVE,
                    "file_sha256": sources["static_captures"]["project"][
                        CONTRACT_EFFECTIVE_RELATIVE]["file_sha256"],
                    "byte_size": sources["static_captures"]["project"][
                        CONTRACT_EFFECTIVE_RELATIVE]["byte_size"]}},
            "pre_history_binding": {"namespace_relative": namespace["relative"],
                "declared_scope": prior_history["declared_scope"],
                "prior_history_fingerprint": fingerprint(prior_history)},
            "boundaries": {key: False for key in INITIAL_BOUNDARY_KEYS}}


def _initial_context_040(prepared, submission, prior_history_verification, store_save,
                         target_leaf, snapshot_captures, e1, h1, envelope,
                         started_capture) -> dict:
    return {"context_version": INITIAL_CONTEXT_VERSION,
            "started_binding": _u040_descriptor(
                _project_relative(envelope / INITIAL_STARTED_FILE),
                started_capture["bytes"],
                _parse_json_object(started_capture["bytes"], INITIAL_STARTED_FILE)),
            "prepared_request": copy.deepcopy(prepared),
            "submission_snapshot": copy.deepcopy(submission),
            "prior_history_verification": copy.deepcopy(prior_history_verification),
            "store_save_result": copy.deepcopy(store_save),
            "snapshot_files": _initial_snapshot_descriptors_040(target_leaf, snapshot_captures),
            "post_history_expectations": copy.deepcopy(e1),
            "post_history_verification": copy.deepcopy(h1),
            "boundaries": {key: False for key in INITIAL_BOUNDARY_KEYS}}


def _initial_receipt_040(store_save, record_relative, started_capture, context_capture,
                         h1) -> dict:
    return {"receipt_version": INITIAL_RECEIPT_VERSION,
            "identity": copy.deepcopy(store_save["identity"]),
            "record_relative": record_relative,
            "started_file_sha256": started_capture["file_sha256"],
            "context_file_sha256": context_capture["file_sha256"],
            "snapshot_manifest_file_sha256": store_save["manifest_file_sha256"],
            "post_history_fingerprint": fingerprint(h1["prior_history"]),
            "boundaries": {key: False for key in INITIAL_BOUNDARY_KEYS}}


def _build_success_040(store_save, history_verification, target_name, record_relative,
                       envelope, envelope_files, status) -> dict:
    """由已核验目标完整返回/历史与本次 writer 缓冲独立构造成功十二键预期。"""
    target_verified = _target_verification_040(history_verification, target_name)
    return {"stage_version": INITIAL_RECORDING_STAGE_VERSION, "status": status,
            "scope": INITIAL_RECORDING_SCOPE,
            "identity": copy.deepcopy(store_save["identity"]),
            "record_relative": record_relative,
            "record_fingerprint": store_save["record_fingerprint"],
            "manifest_file_sha256": store_save["manifest_file_sha256"],
            "storage_verification": copy.deepcopy(target_verified),
            "envelope_binding": {"relative": _project_relative(envelope),
                                 "files": copy.deepcopy(envelope_files)},
            "history_verification": copy.deepcopy(history_verification),
            "boundaries": {key: False for key in INITIAL_BOUNDARY_KEYS},
            "note": INITIAL_RECORDING_NOTE}


def _descriptor_from_capture_040(capture, field) -> dict:
    """由本次同缓冲 capture 重建文件描述（不引用候选对象或其派生副本）。"""
    relative = _project_relative(Path(capture["path"]))
    obj = _parse_json_object(capture["bytes"], field)
    return {"relative": relative, "byte_size": len(capture["bytes"]),
            "file_sha256": _sha_bytes(capture["bytes"]),
            "object_fingerprint": fingerprint(obj)}


def _rebuild_storage_verification_040(store_module, leaf_captures) -> dict:
    """用目标叶六文件字节与 manifest 重建 `storage_verification` 十一键（独立于 store 返回）。"""
    buffers = {name: leaf_captures[name]["bytes"] for name in INITIAL_SNAPSHOT_FILES}
    objects = {name: _parse_json_object(buffers[name], name) for name in INITIAL_SNAPSHOT_FILES}
    return store_module._build_return(store_module.VERIFIED, objects["manifest.json"],
                                      buffers, objects)


def _rebuild_success_040(store_module, status, identity, record_relative, envelope_relative,
                         envelope_captures, storage_verification,
                         history_verification) -> dict:
    """S8 独立预期构造：只用已核验源、目标叶六文件字节、E1/H1 与本次 writer 缓冲重建十二键。"""
    files = sorted([_descriptor_from_capture_040(envelope_captures[name], name)
                    for name in INITIAL_ENVELOPE_FILES],
                   key=lambda item: item["relative"].encode("utf-8"))
    return {"stage_version": INITIAL_RECORDING_STAGE_VERSION,
            "status": status,
            "scope": INITIAL_RECORDING_SCOPE,
            "identity": copy.deepcopy(identity),
            "record_relative": record_relative,
            "record_fingerprint": storage_verification["record_fingerprint"],
            "manifest_file_sha256": storage_verification["manifest_file_sha256"],
            "storage_verification": copy.deepcopy(storage_verification),
            "envelope_binding": {"relative": envelope_relative, "files": files},
            "history_verification": copy.deepcopy(history_verification),
            "boundaries": {key: False for key in INITIAL_BOUNDARY_KEYS},
            "note": INITIAL_RECORDING_NOTE}


def _pre_store_confirm_040(ctx, target_leaf, envelope, lock, started_capture,
                           started_buffer, record_relative, namespace) -> None:
    """R1-B1：S5 在冻结 store/core 之前复确认 S3 开始依赖、H0 旧叶、原路径、自锁与 started。"""
    sources = ctx["sources"]
    batch_path = Path(sources["batch_path"])
    leaf = Path(sources["leaf"])
    scope_path = Path(sources["scope_path"])
    event_path = Path(sources["event_path"])
    load_dir = Path(sources["load_dir"])
    _require_fixed_members(batch_path, TOP_LEVEL_MEMBERS, "batch_dir(顶层)")
    for sub, leaves in BATCH_SUBDIR_FILES.items():
        _require_fixed_members(batch_path / sub, leaves, "batch/" + sub)
    for name in BATCH_FILES:
        _recheck_capture(sources["batch_captures"][name], "batch." + name)
    for relative, capture in sorted(sources["static_captures"].get("project", {}).items()):
        _recheck_capture(capture, relative)
    _recheck_capture(sources["static_captures"]["frozen_prepare"],
                     "scripts/prepare_demo_human_gate1.py")
    # R1-H3：S5 也复测静态 schema/归一化/装载核心（沿 _capture_static_028 口径）。
    for key, relative in (("normalizer", NORMALIZER_RELATIVE),
                          ("sqlite_core", SQLITE_CORE_RELATIVE),
                          ("schema", SCHEMA_RELATIVE)):
        _recheck_capture(sources["static_captures"][key], relative)
    _recheck_capture(sources["self_capture"], "self")
    _recheck_capture(sources["leaf_captures"]["registry"], REGISTRY_FILE)
    _recheck_capture(sources["leaf_captures"]["readback"], READBACK_FILE)
    _require_fixed_members(leaf, [REGISTRY_FILE, READBACK_FILE], "runtime_dir(叶)")
    if FAILURE_FILE in _iter_dir(leaf, "pre_store.leaf"):
        _block("runtime_dir(叶)", "登记叶出现 failure 诊断")
    for name, capture in sorted(sources["event_captures"].items()):
        _recheck_capture(capture, "gate1_event." + name)
    _require_fixed_members(scope_path, [event_path.name], "scope")
    _require_fixed_members(event_path, list(EVENT_FILES), "event")
    _require_fixed_members(event_path / SNAPSHOT_DIR, list(SNAPSHOT_FILES), "snapshots")
    if FAILURE_FILE in _iter_dir(event_path, "pre_store.gate1_event"):
        _block("event", "Gate1 事件含 failure 诊断")
    for name, capture in sorted(ctx["gate2_captures"].items()):
        _recheck_capture(capture, "gate2_event." + name)
    _require_fixed_members(Path(ctx["gate2_scope"]), [Path(ctx["gate2_event"]).name],
                           "gate2_scope")
    _require_fixed_members(Path(ctx["gate2_event"]), list(EVENT_FILES), "gate2_event")
    _require_fixed_members(Path(ctx["gate2_event"]) / SNAPSHOT_DIR, list(SNAPSHOT_FILES),
                           "gate2_snapshots")
    if FAILURE_FILE in _iter_dir(Path(ctx["gate2_event"]), "pre_store.gate2_event"):
        _block("gate2_event", "Gate2 事件含 failure 诊断")
    for name, capture in (("load.started", sources["started_capture"]),
                          ("load.normalized", sources["normalized_capture"]),
                          ("load.report", sources["report_capture"]),
                          ("load.artifacts", sources["artifacts_capture"]),
                          ("database", sources["database_capture"])):
        _recheck_capture(capture, name)
    _require_fixed_members(load_dir, list(APPROVED_LOAD_FILES), "load_dir")
    if FAILURE_FILE in _iter_dir(load_dir, "pre_store.load"):
        _block("load_dir", "输出含 failure 诊断")
    _require_fixed_members(Path(sources["database_capture"]["path"]).parent,
                           [DATABASE_NAME], "database_dir")
    if _lock_path_for(leaf).exists():
        _block("lock", "Gate1 技术锁存在")
    if Path(ctx["gate2_lock"]).exists():
        _block("gate2_lock", "Gate2 技术锁存在")
    for key, (directory, files, captures) in ctx["outputs"].items():
        _require_fixed_members(directory, files, key + "_dir")
        if FAILURE_FILE in _iter_dir(directory, "pre_store." + key):
            _block(key + "_dir", "输出含 failure 诊断")
        for name, capture in captures.items():
            _recheck_capture(capture, key + "." + name)
    _confirm_initial_history_040(ctx, ctx["history"]["expectations"]["expected_entries"])
    _reject_reparse_chain(target_leaf, "record_relative")
    if target_leaf.exists():
        _block("record_relative", "S5 复确认时目标叶已存在（不得覆盖）")
    if _project_relative(target_leaf) != record_relative:
        _block("record_relative", "原路径链较操作开始变化")
    if _project_relative(target_leaf.parent) != namespace["relative"]:
        _block("record_relative", "父域较操作开始变化")
    if envelope.exists() and not envelope.is_dir():
        _block("record_envelope", "运行封装类型较操作开始变化")
    _confirm_initial_lock(lock, "bind.store")
    current = _capture_file(envelope / INITIAL_STARTED_FILE, "pre_store.started")
    if current["bytes"] != started_buffer or current["bytes"] != started_capture["bytes"]:
        _block("started.json", "S5 复确认时 started 字节较本次 writer 缓冲变化")


def _initial_snapshot_descriptors_040(target_leaf: Path, captures) -> list:
    entries = []
    for name in INITIAL_SNAPSHOT_FILES:
        obj = _parse_json_object(captures[name]["bytes"], name)
        entries.append(_u040_descriptor(_project_relative(target_leaf / name),
                                        captures[name]["bytes"], obj))
    return entries


def _confirm_initial_sources_040(ctx, expected_entries=None, *, target_leaf=None,
                                 envelope=None, envelope_captures=None,
                                 target_captures=None, target_name=None) -> None:
    """R1-B2：复用冻结末次集合/failure/锁口径，再确认本次输出与历史域。

    `_confirm_approved_terminal`/`_confirm_gate2_terminal_030` 覆盖 batch 顶层与子目录集合、
    登记叶集合与 failure、Gate1/Gate2 scope/event/snapshot 集合与 failure、load 目录集合与
    failure、数据库目录集合、Gate1/Gate2 技术锁。
    """
    sources = ctx["sources"]
    _confirm_gate2_terminal_030(sources, ctx["gate2_scope"], ctx["gate2_event"],
                                ctx["gate2_captures"], ctx["gate2_lock"])
    for name, capture in sorted(sources["event_captures"].items()):
        _recheck_capture(capture, "gate1_event." + name)
    for key, (directory, files, captures) in ctx["outputs"].items():
        _require_fixed_members(directory, files, key + "_dir")
        if FAILURE_FILE in _iter_dir(directory, "final." + key):
            _block(key + "_dir", "成功路径不得残留 failure 诊断")
        for name, capture in captures.items():
            _recheck_capture(capture, key + "." + name)
    _confirm_initial_history_040(ctx, expected_entries, missing_allowed=target_name)
    if target_leaf is not None:
        _require_fixed_members(target_leaf, list(INITIAL_SNAPSHOT_FILES), "record_relative")
        if FAILURE_FILE in _iter_dir(target_leaf, "final.record"):
            _block("record_relative", "成功路径不得残留目标叶 failure 诊断")
        if target_captures:
            for name in INITIAL_SNAPSHOT_FILES:
                _recheck_capture(target_captures[name], "snapshots." + name)
    if envelope is not None:
        _require_fixed_members(envelope, list(INITIAL_ENVELOPE_FILES), "record_envelope")
        if FAILURE_FILE in _iter_dir(envelope, "final.envelope"):
            _block("record_envelope", "成功路径不得残留 failure 诊断")
        if envelope_captures:
            for name in INITIAL_ENVELOPE_FILES:
                _recheck_capture(envelope_captures[name], "envelopes." + name)


def _confirm_initial_history_040(ctx, expected_entries=None, *, missing_allowed=None) -> None:
    """按本次期望名单确认声明域成员、旧叶六字节与冻结组件；目标叶由调用方另行确认。"""
    history_ctx = ctx["history"]
    module, store = history_ctx["module"], history_ctx["store"]
    source = ctx["sources"]["static_captures"]["project"][INITIAL_HISTORY_RELATIVE]
    entries = copy.deepcopy(history_ctx["expectations"]["expected_entries"]) \
        if expected_entries is None else copy.deepcopy(expected_entries)
    _confirm_history_namespace_038(history_ctx["namespace"])
    target = Path(history_ctx["namespace"]["path"])
    _history_call_038(module, module._members, store, target, entries)
    for index, entry in enumerate(entries):
        name = entry["relative"]
        buffers = history_ctx["buffers"].get(name)
        field = "history.entries[%d]" % index
        if buffers is None:
            if missing_allowed is not None and name == missing_allowed:
                continue
            _block(field, "缺少本次开始叶缓冲且非本次目标")
        leaf = target / name
        _history_call_038(module, module._leaf_layout, store, leaf, field)
        for file_name, raw in buffers.items():
            current = _capture_file(leaf / file_name, field + "." + file_name)
            if current["bytes"] != raw:
                _block(field + "." + file_name, "末次字节与本次起始缓冲不符")
        _history_call_038(module, module._leaf_layout, store, leaf, field)
    _history_call_038(module, module._store_call, store, "", store._confirm_components,
                      history_ctx["components"])
    if _capture_file(PROJECT_ROOT / INITIAL_HISTORY_RELATIVE,
                     "read.history.final")["bytes"] != source["bytes"]:
        _block("history", "history 源码字节较操作开始变化")
    _history_call_038(module, module._members, store, target, entries)


def save_runtime_initial_judgment(batch_dir, runtime_dir, request_id, submission, record_relative, *,
        scope_dir, event_relative, database_path, gate2_event_relative,
        history_expectations) -> dict:
    """保存合成运行的人类声明独立初判快照；`RECORDED` 不是批准、不是执行许可。

    正常调用图：公开 prepare 1 次 + 冻结 store.save 1 次 + 保存后 history 1 次。
    """
    stage = "path"
    lock = None
    envelope = None
    created = False
    identity = None
    snapshot_captures: dict = {}
    try:
        # 参数按签名顺序检查类型，再做路径与关系检查（R1 非阻断项）。
        if not isinstance(batch_dir, (str, os.PathLike)):
            _block("batch_dir", f"必须是路径，实际 {type(batch_dir).__name__}")
        if not isinstance(runtime_dir, (str, os.PathLike)):
            _block("runtime_dir", f"必须是路径，实际 {type(runtime_dir).__name__}")
        _u040_text(request_id, "request_id")
        if type(submission) is not dict:
            _block("submission", f"必须为严格对象，实际 {type(submission).__name__}")
        _u040_text(record_relative, "record_relative")
        if not isinstance(scope_dir, (str, os.PathLike)):
            _block("scope_dir", f"必须是路径，实际 {type(scope_dir).__name__}")
        _u040_text(event_relative, "event_relative")
        if not isinstance(database_path, (str, os.PathLike)):
            _block("database_path", f"必须是路径，实际 {type(database_path).__name__}")
        _u040_text(gate2_event_relative, "gate2_event_relative")
        if type(history_expectations) is not dict:
            _block("history_expectations", "必须为严格对象")
        batch_caps: dict = {}
        batch_path = _check_batch_dir(batch_dir, batch_caps)
        leaf = _read_registry_leaf(runtime_dir)
        registry, _, leaf_captures = _load_stored_registry(leaf, allow_existing_scope=True)
        self_capture = _capture_file(MODULE_PATH, "read.self")
        static_captures: dict = {}
        _require_current_static_identity(registry, self_capture, static_captures)
        scope_path = _resolve_existing_scope_040(scope_dir, registry)
        event_path = _existing_gate1_event_040(scope_path, event_relative)
        _gate2_paths_030((batch_path, leaf, scope_path, event_path, batch_caps),
                         gate2_event_relative, saving=False)
        load_dir = _load_dir_for(leaf)
        _check_database_target(database_path, batch_path=batch_path, leaf=leaf,
                               scope_path=scope_path, event_path=event_path,
                               load_dir=load_dir, require_new_leaf=False)
        namespace = _history_namespace_capture_038(registry["initial_judgment_history"])
        # R1-B3：域/scope/名单形状与全部路径关系必须在取锁之前完成；
        # 参数错误不得产生本次锁、叶或运行封装（RC-12/RC-13）。
        history_module = _load_initial_history_038(
            static_captures["project"][INITIAL_HISTORY_RELATIVE])
        _history_call_038(history_module, history_module._expectations, history_expectations)
        _require_equivalent_030(history_expectations["expected_namespace_relative"],
                                namespace["relative"],
                                "history_expectations.expected_namespace_relative")
        _require_equivalent_030(history_expectations["expected_declared_scope"],
                                registry["initial_judgment_history"]["declared_scope"],
                                "history_expectations.expected_declared_scope")
        target_leaf, target_name = _initial_target_040(record_relative, namespace, must_exist=False)
        envelope = _initial_envelope_path(leaf)
        lock_path = _initial_lock_path(Path(namespace["path"]))
        if envelope.exists():
            _block("record_envelope", "运行封装必须从未存在（含空目录）")
        if lock_path.exists():
            _block("lock", f"技术锁已存在，拒绝保存：{_safe_relative(lock_path)}")
        before_submission = copy.deepcopy(submission)
        before_history = copy.deepcopy(history_expectations)

        stage = "lock.acquire"
        lock = _acquire_initial_lock(lock_path, namespace_relative=namespace["relative"],
                                     runtime_relative=_project_relative(leaf),
                                     record_relative=record_relative, request_id=request_id)
        stage = "lock.confirm"
        _confirm_initial_lock(lock, "lock.confirm")

        # S2/S3：持锁后重新实读全部依赖，并由同缓冲来源固定独立预期。
        params = dict(scope_dir=scope_path, event_relative=event_relative,
                      database_path=database_path, gate2_event_relative=gate2_event_relative)
        stage = "audit.result"
        ctx = _capture_initial_sources_038(batch_dir, leaf, params, history_expectations)
        registry_now, sources = ctx["registry"], ctx["sources"]
        if canonical_json_bytes(registry_now) != canonical_json_bytes(registry):
            _block("registry", "持锁后实读登记与锁前不一致")
        if _project_relative(Path(sources["event_path"])) != event_relative:
            _block("event_relative", "持锁后实读 Gate1 事件与显式参数不一致")
        expected = _expected_initial_request_040(ctx, registry_now, params, request_id)
        expected_envelope = {"request": expected["request"],
                             "request_sha256": expected["request_sha256"]}
        prepared = prepare_runtime_initial_judgment_request(
            batch_dir, leaf, request_id, **params, history_expectations=history_expectations)
        if _u040_diff(expected_envelope, prepared) is not None:
            _block("initial.request", "公开 prepare 返回与本次开始同缓冲独立预期不一致："
                   + str(_u040_diff(expected_envelope, prepared)))

        stage = "write.started"
        prior_history = copy.deepcopy(expected["prior_history"])
        started = _initial_started_040(registry_now, request_id, record_relative, batch_path,
                                       leaf, event_relative, gate2_event_relative, sources,
                                       namespace, prior_history)
        _u040_keys(started, INITIAL_STARTED_KEYS, "started")
        if started["source_binding"]["registry_binding"]["run_binding_sha256"] \
                != fingerprint(registry_now["run_binding"]):
            _block("started.source_binding.registry_binding.run_binding_sha256",
                   "必须为 run_binding 对象规范指纹（不是登记文件FILE）")
        started_buffer = _payload_bytes(started)
        try:
            envelope.mkdir()
        except FileExistsError as exc:
            raise RuntimeGate1Blocked("record_envelope", "运行封装已被占用") from exc
        except OSError as exc:
            raise RuntimeGate1Error("write.started", f"无法独占创建运行封装：{exc}") from exc
        created = True
        _write_exclusive(envelope / INITIAL_STARTED_FILE, started_buffer, "write.started")
        started_capture = _capture_file(envelope / INITIAL_STARTED_FILE, "readback.started")
        if started_capture["bytes"] != started_buffer:
            _block("started.json", "读回字节与本次 writer 缓冲不一致")

        stage = "bind.store"
        history_ctx = ctx["history"]
        store = history_ctx["store"]
        reference = dict(prepared, _submission=submission)
        # R1-B1：调用冻结 store 前按 S5 复确认开始依赖/H0旧叶/原路径/自锁/started 缓冲；
        # 复确认失败不建叶、不调用 store/core、不刷新独立预期。
        _pre_store_confirm_040(ctx, target_leaf, envelope, lock, started_capture,
                               started_buffer, record_relative, namespace)
        try:
            store_result = store.save_human_initial_judgment_snapshots(
                submission, prepared["request"]["materials"],
                prepared["request"]["expectations"],
                prior_history=prior_history, out_dir=str(target_leaf))
        except store.HumanInitialJudgmentStoreBlocked as exc:
            raise RuntimeGate1Blocked("store." + str(exc.field), exc.reason) from exc
        except store.HumanInitialJudgmentStoreError as exc:
            error = RuntimeGate1Error(exc.stage, exc.reason)
            error.reasons = copy.deepcopy(getattr(exc, "reasons", [exc.reason]))
            if hasattr(exc, "secondary_errors"):
                error.secondary_errors = copy.deepcopy(exc.secondary_errors)
            raise error from exc
        components = _initial_store_components_040(history_ctx)
        listing = _iter_dir(target_leaf, "list.record")
        if list(listing) != list(INITIAL_SNAPSHOT_FILES):
            _block("record_relative", f"保存目标叶必须恰六文件，实际 {listing}")
        for name in INITIAL_SNAPSHOT_FILES:
            _u040_normal_file(target_leaf / name, "snapshots." + name)
            snapshot_captures[name] = _capture_file(target_leaf / name, "read.snapshots." + name)
        store_save = _validate_initial_store_result_040(
            store_result, snapshot_captures, reference, prior_history, components)
        identity = copy.deepcopy(store_save["identity"])

        stage = "history.post"
        entries_e0 = copy.deepcopy(history_ctx["expectations"]["expected_entries"])
        entries_e1 = copy.deepcopy(entries_e0) + [
            {"relative": target_name, "manifest_file_sha256": store_save["manifest_file_sha256"]}]
        entries_e1.sort(key=lambda item: item["relative"].encode("utf-8"))
        e1 = {"expectations_version": history_ctx["expectations"]["expectations_version"],
              "expected_namespace_relative": namespace["relative"],
              "expected_declared_scope": history_ctx["expectations"]["expected_declared_scope"],
              "expected_entries": entries_e1}
        history_source = sources["static_captures"]["project"][INITIAL_HISTORY_RELATIVE]
        target_verification = dict(copy.deepcopy(store_save),
                                   status=store.VERIFIED)
        target_record = copy.deepcopy(store_save["judgment_result"]["record"])
        expected_h1 = _expected_history_040(
            history_ctx, history_source,
            entries=copy.deepcopy(history_ctx["expectations"]["expected_entries"]),
            extra=[(target_name, target_verification, target_record)])
        expected_h1["inventory"]["entries"] = entries_e1
        expected_h1["prior_history"]["records"] = sorted(
            copy.deepcopy(expected["history"]["prior_history"]["records"])
            + [_history_index_item_040(target_record)],
            key=lambda item: item["event_id"].encode("utf-8"))
        expected_h1["prior_history_fingerprint"] = fingerprint(expected_h1["prior_history"])
        expected_h1["inventory_fingerprint"] = fingerprint(expected_h1["inventory"])
        h1 = _history_call_038(history_ctx["module"],
                               history_ctx["module"].inspect_human_initial_judgment_history,
                               Path(namespace["path"]), expectations=copy.deepcopy(e1))
        if _u040_diff(expected_h1, h1) is not None:
            _block("history.verification", "保存后历史完整核验与独立E1/H1预期不一致："
                   + _u040_diff(expected_h1, h1))
        h1 = copy.deepcopy(h1)

        stage = "write.context"
        context = _initial_context_040(prepared, submission, expected["history"], store_save,
                                       target_leaf, snapshot_captures, e1, h1, envelope,
                                       started_capture)
        _u040_keys(context, INITIAL_CONTEXT_KEYS, "context")
        if context["prepared_request"]["request_sha256"] \
                != fingerprint(context["prepared_request"]["request"]):
            _block("context.prepared_request.request_sha256", "必须为 request 对象规范指纹")
        context_buffer = _payload_bytes(context)
        _write_exclusive(envelope / INITIAL_CONTEXT_FILE, context_buffer, "write.context")
        context_capture = _capture_file(envelope / INITIAL_CONTEXT_FILE, "readback.context")
        if context_capture["bytes"] != context_buffer:
            _block("context.json", "读回字节与本次 writer 缓冲不一致")

        stage = "write.receipt"
        receipt = _initial_receipt_040(store_save, record_relative, started_capture,
                                       context_capture, h1)
        _u040_keys(receipt, INITIAL_RECEIPT_KEYS, "receipt")
        if receipt["context_file_sha256"] != context_capture["file_sha256"]:
            _block("receipt.context_file_sha256", "必须为 context writer FILE（不是对象FP）")
        receipt_buffer = _payload_bytes(receipt)
        _write_exclusive(envelope / INITIAL_RECEIPT_FILE, receipt_buffer, "write.receipt")
        receipt_capture = _capture_file(envelope / INITIAL_RECEIPT_FILE, "readback.receipt")
        if receipt_capture["bytes"] != receipt_buffer:
            _block("receipt.json", "读回字节与本次 writer 缓冲不一致")

        stage = "audit.result"
        envelope_captures = {INITIAL_STARTED_FILE: started_capture,
                             INITIAL_CONTEXT_FILE: context_capture,
                             INITIAL_RECEIPT_FILE: receipt_capture}
        envelope_files = sorted(
            [_u040_descriptor(_project_relative(envelope / name),
                              envelope_captures[name]["bytes"],
                              _parse_json_object(envelope_captures[name]["bytes"], name))
             for name in INITIAL_ENVELOPE_FILES],
            key=lambda item: item["relative"].encode("utf-8"))
        # R1-H1：候选由真实 store/H1 返回与 writer 缓冲组装；预期只由目标叶六文件字节、
        # E1/H1 独立重建与本次 writer 缓冲重建。两条构造路径做完整 canonical 比较。
        rebuilt_storage = _rebuild_storage_verification_040(store, snapshot_captures)
        target_leaf_record = _parse_json_object(
            snapshot_captures["judgment_result.json"]["bytes"], "judgment_result.json")["record"]
        expected_history = _expected_history_040(
            history_ctx, history_source,
            entries=copy.deepcopy(history_ctx["expectations"]["expected_entries"]),
            extra=[(target_name, rebuilt_storage, target_leaf_record)])
        expected_history["inventory"]["entries"] = entries_e1
        expected_history["prior_history"]["records"] = sorted(
            copy.deepcopy(expected["history"]["prior_history"]["records"])
            + [_history_index_item_040(target_leaf_record)],
            key=lambda item: item["event_id"].encode("utf-8"))
        expected_history["prior_history_fingerprint"] = fingerprint(
            expected_history["prior_history"])
        expected_history["inventory_fingerprint"] = fingerprint(expected_history["inventory"])
        candidate_result = _build_success_040(store_save, h1, target_name, record_relative,
                                              envelope, envelope_files, INITIAL_SAVE_STATUS)
        expected_result = _rebuild_success_040(
            store, INITIAL_SAVE_STATUS,
            {"batch_id": registry_now["batch_id"], "event_id": submission["event_id"],
             "request_id": request_id},
            record_relative, _project_relative(envelope), envelope_captures,
            rebuilt_storage, expected_history)
        _audit_initial_success_040(candidate_result, expected_result, store_save, h1,
                                   envelope_captures, envelope_files,
                                   store_save["identity"], record_relative,
                                   _project_relative(envelope), INITIAL_SAVE_STATUS)
        success = candidate_result

        stage = "save.final"
        _confirm_initial_sources_040(ctx, entries_e1, target_leaf=target_leaf, envelope=envelope,
                                     envelope_captures=envelope_captures,
                                     target_captures=snapshot_captures, target_name=target_name)
        _confirm_initial_lock(lock, "save.final")
        if canonical_json_bytes(submission) != canonical_json_bytes(before_submission):
            _block("submission", "调用方原 submission 对象在保存期间被改变")
        if canonical_json_bytes(history_expectations) != canonical_json_bytes(before_history):
            _block("history_expectations", "调用方原 history_expectations 在保存期间被改变")

        stage = "release.lock"
        release_error = _release_initial_lock(lock)
        if release_error is not None:
            raise RuntimeGate1Error("release.lock", release_error)
        return copy.deepcopy(success)
    except (RuntimeGate1Blocked, RuntimeGate1Error) as exc:
        if created and envelope is not None:
            label = exc.stage if isinstance(exc, RuntimeGate1Error) else stage
            _write_initial_failure(envelope, label, exc, identity)
        if lock is not None:
            _abandon_initial_lock(lock)
        raise
    except Exception as exc:  # noqa: BLE001 - 未预期异常按当前阶段映射并保留原因
        error = RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}")
        error.__cause__ = exc
        if created and envelope is not None:
            _write_initial_failure(envelope, stage, error, identity)
        if lock is not None:
            _abandon_initial_lock(lock)
        raise error from exc


def _target_verification_040(history_verification: dict, target_name: str) -> dict:
    for item in history_verification["verified_snapshots"]:
        if item["relative"] == target_name:
            return copy.deepcopy(item["verification"])
    raise RuntimeGate1Blocked("history.verified_snapshots", f"缺少目标 {target_name}")


def _validate_descriptor_040(value, field) -> dict:
    entry = _u040_keys(value, INITIAL_FILE_DESCRIPTOR_KEYS, field)
    _u040_relative(entry["relative"], field + ".relative")
    _u040_nonneg(entry["byte_size"], field + ".byte_size")
    _u040_hash(entry["file_sha256"], field + ".file_sha256")
    _u040_hash(entry["object_fingerprint"], field + ".object_fingerprint")
    return entry


def _validate_boundaries_040(value, field) -> None:
    _u040_keys(value, INITIAL_BOUNDARY_KEYS, field)
    for key in INITIAL_BOUNDARY_KEYS:
        _u040_false(value[key], field + "." + key)


def _validate_initial_failure_040(value) -> None:
    if type(value) is not dict:
        _block("failure", f"必须为严格对象，实际 {type(value).__name__}")
    for key in sorted(value.keys(), key=lambda item: str(item).encode("utf-8")):
        if type(key) is not str or key not in INITIAL_FAILURE_KEYS:
            _block("failure." + str(key), "含未允许的键")
    for key in INITIAL_FAILURE_KEYS:
        if key not in value:
            _block("failure." + key, "缺少必需键")
    item = value
    _u040_const(item["failure_version"], INITIAL_FAILURE_VERSION, "failure.failure_version")
    _u040_const(item["scope"], INITIAL_RECORDING_SCOPE, "failure.scope")
    if item["identity"] is not None:
        identity = _u040_keys(item["identity"], INITIAL_IDENTITY_KEYS, "failure.identity")
        for key in INITIAL_IDENTITY_KEYS:
            _u040_text(identity[key], "failure.identity." + key)
    _u040_text(item["stage"], "failure.stage")
    if type(item["classification"]) is not str or item["classification"] not in ("BLOCKED", "ERROR"):
        _block("failure.classification", "必须为 BLOCKED 或 ERROR")
    _u040_text(item["reason"], "failure.reason")
    if item["classification"] == "BLOCKED":
        _u040_text(item["field"], "failure.field")
    elif item["field"] is not None:
        _block("failure.field", "ERROR 分类必须为 null")
    if type(item["reasons"]) is not list or not item["reasons"]:
        _block("failure.reasons", "必须为非空字符串列表")
    for index, reason in enumerate(item["reasons"]):
        _u040_text(reason, "failure.reasons[%d]" % index)
    _u040_text(item["exception_type"], "failure.exception_type")
    if type(item["cause_chain"]) is not list or not item["cause_chain"]:
        _block("failure.cause_chain", "必须为非空 chain_item 列表")
    for index, chain in enumerate(item["cause_chain"]):
        entry = _u040_keys(chain, INITIAL_CHAIN_ITEM_KEYS, "failure.cause_chain[%d]" % index)
        _u040_text(entry["exception_type"], "failure.cause_chain[%d].exception_type" % index)
        if type(entry["message"]) is not str:
            _block("failure.cause_chain[%d].message" % index, "必须为原字符串")
    if item["cause_chain"][0]["exception_type"] != item["exception_type"]:
        _block("failure.cause_chain[0].exception_type", "首项类型必须等于 exception_type")
    if type(item["secondary_errors"]) is not list:
        _block("failure.secondary_errors", "必须为列表")
    for index, note in enumerate(item["secondary_errors"]):
        field = "failure.secondary_errors[%d]" % index
        if type(note) is str:
            _u040_text(note, field)
            continue
        entry = _u040_keys(note, INITIAL_CHAIN_ITEM_KEYS, field)
        _u040_text(entry["exception_type"], field + ".exception_type")
        if type(entry["message"]) is not str:
            _block(field + ".message", "必须为原字符串")


def _raise_initial_failure_040(value, prefix: str) -> None:
    reasons = copy.deepcopy(value["reasons"])
    secondary = copy.deepcopy(value["secondary_errors"])
    if value["classification"] == "BLOCKED":
        error = RuntimeGate1Blocked(prefix + str(value["field"]), value["reason"])
    else:
        error = RuntimeGate1Error(value["stage"], value["reason"])
    error.reasons = reasons
    error.secondary_errors = secondary
    raise error


def _read_envelope_failure_040(envelope: Path) -> None:
    capture = _capture_file(envelope / FAILURE_FILE, "read.failure")
    value = _parse_json_object(capture["bytes"], "failure.json")
    try:
        _validate_initial_failure_040(value)
    except RuntimeGate1Blocked as exc:
        raise RuntimeGate1Blocked(str(exc.field), exc.reason) from exc
    _raise_initial_failure_040(value, "runtime.failure.")


def _read_store_failure_040(target_leaf: Path, store) -> None:
    capture = _capture_file(target_leaf / FAILURE_FILE, "read.failure")
    value = _parse_json_object(capture["bytes"], "failure.json")
    try:
        store._validate_failure(value)
    except store.HumanInitialJudgmentStoreBlocked as exc:
        raise RuntimeGate1Blocked("store." + str(exc.field), exc.reason) from exc
    except store.HumanInitialJudgmentStoreError as exc:
        raise RuntimeGate1Error(exc.stage, exc.reason) from exc
    reasons = [value["reason"]]
    if value["classification"] == "BLOCKED":
        error = RuntimeGate1Blocked("store.failure." + str(value["field"]), value["reason"])
    else:
        error = RuntimeGate1Error(value["stage"], value["reason"])
    error.reasons = reasons
    error.secondary_errors = []
    raise error


def verify_runtime_initial_judgment(batch_dir, runtime_dir, *, scope_dir, event_relative,
        database_path, gate2_event_relative, record_relative, history_expectations) -> dict:
    """只读恢复一次已保存的合成运行初判快照；`VERIFIED` 不是批准、不认证身份。

    正常调用图：直接 history 1 次；Gate1、Gate2、fact 核验各 1 次；公开 prepare/store.save 0。
    """
    stage = "path"
    try:
        if not isinstance(batch_dir, (str, os.PathLike)):
            _block("batch_dir", f"必须是路径，实际 {type(batch_dir).__name__}")
        if not isinstance(runtime_dir, (str, os.PathLike)):
            _block("runtime_dir", f"必须是路径，实际 {type(runtime_dir).__name__}")
        if not isinstance(scope_dir, (str, os.PathLike)):
            _block("scope_dir", f"必须是路径，实际 {type(scope_dir).__name__}")
        _u040_text(event_relative, "event_relative")
        if not isinstance(database_path, (str, os.PathLike)):
            _block("database_path", f"必须是路径，实际 {type(database_path).__name__}")
        _u040_text(gate2_event_relative, "gate2_event_relative")
        _u040_text(record_relative, "record_relative")
        if type(history_expectations) is not dict:
            _block("history_expectations", "必须为严格对象")
        batch_caps: dict = {}
        batch_path = _check_batch_dir(batch_dir, batch_caps)
        leaf = _read_registry_leaf(runtime_dir)
        registry, _, leaf_captures = _load_stored_registry(leaf, allow_existing_scope=True)
        self_capture = _capture_file(MODULE_PATH, "read.self")
        static_captures: dict = {}
        _require_current_static_identity(registry, self_capture, static_captures)
        scope_path = _resolve_existing_scope_040(scope_dir, registry)
        event_path = _existing_gate1_event_040(scope_path, event_relative)
        params = dict(scope_dir=scope_path, event_relative=event_relative,
                      database_path=database_path, gate2_event_relative=gate2_event_relative)
        _gate2_paths_030((batch_path, leaf, scope_path, event_path, batch_caps),
                         gate2_event_relative, saving=False)
        load_dir = _load_dir_for(leaf)
        _check_database_target(database_path, batch_path=batch_path, leaf=leaf,
                               scope_path=scope_path, event_path=event_path,
                               load_dir=load_dir, require_new_leaf=False)
        namespace = _history_namespace_capture_038(registry["initial_judgment_history"])
        history_module = _load_initial_history_038(
            static_captures["project"][INITIAL_HISTORY_RELATIVE])
        _history_call_038(history_module, history_module._expectations, history_expectations)
        _require_equivalent_030(history_expectations["expected_namespace_relative"],
                                namespace["relative"],
                                "history_expectations.expected_namespace_relative")
        _require_equivalent_030(history_expectations["expected_declared_scope"],
                                registry["initial_judgment_history"]["declared_scope"],
                                "history_expectations.expected_declared_scope")
        target_leaf, target_name = _initial_target_040(record_relative, namespace, must_exist=True)
        envelope = _initial_envelope_path(leaf)
        lock_path = _initial_lock_path(Path(namespace["path"]))
        if lock_path.exists():
            _block("lock", "技术锁存在，只读核验拒绝")
        if not envelope.is_dir():
            _block("record_envelope", f"运行封装不存在：{_safe_relative(envelope)}")
        store, _ = _history_call_038(history_module, history_module._load_store)
        if FAILURE_FILE in _iter_dir(envelope, "read.failure"):
            _read_envelope_failure_040(envelope)
        if FAILURE_FILE in _iter_dir(target_leaf, "read.failure"):
            _read_store_failure_040(target_leaf, store)
        _require_fixed_members(envelope, list(INITIAL_ENVELOPE_FILES), "record_envelope")
        _require_fixed_members(target_leaf, list(INITIAL_SNAPSHOT_FILES), "record_relative")

        stage = "read.envelope"
        envelope_captures = {name: _capture_file(envelope / name, "read.envelope." + name)
                             for name in INITIAL_ENVELOPE_FILES}
        snapshot_captures = {name: _capture_file(target_leaf / name, "read.snapshots." + name)
                             for name in INITIAL_SNAPSHOT_FILES}
        started = _u040_keys(_parse_json_object(
            envelope_captures[INITIAL_STARTED_FILE]["bytes"], INITIAL_STARTED_FILE),
            INITIAL_STARTED_KEYS, "started")
        context = _u040_keys(_parse_json_object(
            envelope_captures[INITIAL_CONTEXT_FILE]["bytes"], INITIAL_CONTEXT_FILE),
            INITIAL_CONTEXT_KEYS, "context")
        receipt = _u040_keys(_parse_json_object(
            envelope_captures[INITIAL_RECEIPT_FILE]["bytes"], INITIAL_RECEIPT_FILE),
            INITIAL_RECEIPT_KEYS, "receipt")

        stage = "path"
        ctx = _capture_initial_sources_038(batch_dir, leaf, params, history_expectations)
        sources = ctx["sources"]
        registry_now = ctx["registry"]
        if canonical_json_bytes(registry_now) != canonical_json_bytes(registry):
            _block("registry", "核验期间实读登记与操作开始不一致")

        stage = "audit.result"
        _validate_started_040(started, registry_now, ctx, namespace, record_relative)
        history_ctx = ctx["history"]
        history_source = sources["static_captures"]["project"][INITIAL_HISTORY_RELATIVE]
        expected_hc = _expected_history_040(history_ctx, history_source)
        hc = _history_call_038(history_ctx["module"],
                               history_ctx["module"].inspect_human_initial_judgment_history,
                               Path(namespace["path"]),
                               expectations=copy.deepcopy(history_ctx["expectations"]))
        if _u040_diff(expected_hc, hc) is not None:
            _block("history.verification", "当前声明域完整核验与本次开始缓冲不一致："
                   + _u040_diff(expected_hc, hc))
        hc = copy.deepcopy(hc)

        components = _initial_store_components_040(history_ctx)
        prepared_request = _u040_keys(context["prepared_request"],
                                      ("request", "request_sha256"),
                                      "context.prepared_request")
        _u040_hash(prepared_request["request_sha256"], "context.prepared_request.request_sha256")
        if prepared_request["request_sha256"] != fingerprint(prepared_request["request"]):
            _block("context.prepared_request.request_sha256",
                   "必须为 request 对象规范指纹（不是包含文件FILE）")
        request = _u040_keys(prepared_request["request"], REQUEST_KEYS, "context.prepared_request.request")
        stored_materials = _parse_json_object(snapshot_captures["materials.json"]["bytes"],
                                              "materials.json")
        stored_expectations = _parse_json_object(snapshot_captures["expectations.json"]["bytes"],
                                                 "expectations.json")
        stored_prior = _parse_json_object(snapshot_captures["prior_history.json"]["bytes"],
                                          "prior_history.json")
        stored_submission = _parse_json_object(snapshot_captures["submission.json"]["bytes"],
                                               "submission.json")
        if _u040_diff(request["materials"], stored_materials) is not None:
            _block("context.prepared_request.request.materials", "与目标快照 materials 不一致")
        if _u040_diff(request["expectations"], stored_expectations) is not None:
            _block("context.prepared_request.request.expectations", "与目标快照 expectations 不一致")
        if _u040_diff(context["submission_snapshot"], stored_submission) is not None:
            _block("context.submission_snapshot", "与目标快照 submission 不一致")
        reference = {"request": request, "_submission": context["submission_snapshot"]}
        store_save = _validate_initial_store_result_040(
            context["store_save_result"], snapshot_captures, reference, stored_prior, components)
        identity = copy.deepcopy(store_save["identity"])
        record = store_save["judgment_result"]["record"]

        stage = "audit.result"
        started_descriptor = _validate_descriptor_040(context["started_binding"],
                                                      "context.started_binding")
        _u040_const(context["context_version"], INITIAL_CONTEXT_VERSION, "context.context_version")
        _validate_boundaries_040(context["boundaries"], "context.boundaries")
        if _u040_diff(started_descriptor,
                      _u040_descriptor(_project_relative(envelope / INITIAL_STARTED_FILE),
                                       envelope_captures[INITIAL_STARTED_FILE]["bytes"], started)) is not None:
            _block("context.started_binding", "与本次开始 started writer 缓冲不一致")
        snapshot_files = _u040_keys_list_descriptors_040(context["snapshot_files"])
        expected_snapshot_files = _initial_snapshot_descriptors_040(target_leaf, snapshot_captures)
        if _u040_diff(expected_snapshot_files, snapshot_files) is not None:
            _block("context.snapshot_files", "与目标六快照同缓冲描述不一致")
        e1 = _u040_keys(context["post_history_expectations"],
                        ("expectations_version", "expected_namespace_relative",
                         "expected_declared_scope", "expected_entries"),
                        "context.post_history_expectations")
        e1_entries = e1["expected_entries"]
        if type(e1_entries) is not list:
            _block("context.post_history_expectations.expected_entries", "必须为列表")
        e0_entries = [copy.deepcopy(item) for item in e1_entries
                      if isinstance(item, dict) and item.get("relative") != target_name]
        expected_h0 = _expected_history_040(history_ctx, history_source,
                                            entries=copy.deepcopy(e0_entries))
        if _u040_diff(expected_h0, context["prior_history_verification"]) is not None:
            _block("context.prior_history_verification",
                   "与本次开始旧叶缓冲构造的H0不一致：" +
                   str(_u040_diff(expected_h0, context["prior_history_verification"])))
        target_verification = dict(copy.deepcopy(store_save),
                                   status=store.VERIFIED)
        expected_h1 = _expected_history_040(
            history_ctx, history_source,
            entries=copy.deepcopy(e0_entries),
            extra=[(target_name, target_verification, copy.deepcopy(record))])
        expected_h1["inventory"]["entries"] = _sorted_entries_040(
            copy.deepcopy(e0_entries) + [{"relative": target_name,
                "manifest_file_sha256": store_save["manifest_file_sha256"]}])
        expected_h1["inventory_fingerprint"] = fingerprint(expected_h1["inventory"])
        expected_h1["prior_history"]["records"] = _sorted_records_040(
            copy.deepcopy(context["prior_history_verification"]["prior_history"]["records"])
            + [_history_index_item_040(record)])
        expected_h1["prior_history_fingerprint"] = fingerprint(expected_h1["prior_history"])
        if _u040_diff(expected_h1, context["post_history_verification"]) is not None:
            _block("context.post_history_verification",
                   "与独立E1/旧叶缓冲区构造的H1不一致：" +
                   str(_u040_diff(expected_h1, context["post_history_verification"])))
        h1 = copy.deepcopy(context["post_history_verification"])
        if _u040_diff(target_verification, _target_verification_040(hc, target_name)) is not None:
            _block("storage_verification", "目标当前完整VERIFIED与保存时稳定字段不一致")
        if fingerprint(stored_prior) != stored_expectations["expected_prior_history_fingerprint"] \
                or fingerprint(stored_prior) != record["history_binding"]["prior_history_fingerprint"] \
                or fingerprint(stored_prior) != context["prior_history_verification"]["prior_history_fingerprint"]:
            _block("snapshot.prior_history", "P0与expectations/record/H0的旧历史指纹不闭合")
        if record["history_binding"]["declared_scope"] != stored_prior["declared_scope"]:
            _block("record.history_binding.declared_scope", "与保存时P0声明域不一致")

        stage = "audit.result"
        request_id = stored_expectations["expected_request_id"]
        if started["request_id"] != request_id:
            _block("started.request_id", "与目标请求原ID不一致")
        if receipt["identity"]["request_id"] != request_id:
            _block("receipt.identity.request_id", "与目标请求原ID不一致")
        gate1, gate2, facts, link1, link2 = _verify_initial_gates_038(
            batch_dir, leaf, params, ctx, registry_now)
        current = _materialize_initial_basis_038(
            ctx, registry_now, gate1, gate2, facts, link1, link2, request_id,
            stored_prior["declared_scope"], fingerprint(stored_prior), hc)
        if _u040_diff(current["materials"], stored_materials) is not None:
            _block("materials", "当前来源材料与目标快照不一致（材料漂移）："
                   + str(_u040_diff(current["materials"], stored_materials)))
        if _u040_diff(current["expectations"], stored_expectations) is not None:
            _block("expectations", "独立重建的十二键预期与目标快照不一致："
                   + str(_u040_diff(current["expectations"], stored_expectations)))

        stage = "audit.result"
        h0 = expected_h0
        if e1["expected_namespace_relative"] != namespace["relative"]:
            _block("context.post_history_expectations.expected_namespace_relative",
                   "必须等于已绑定声明域")
        if e1_entries != _sorted_entries_040(e1_entries):
            _block("context.post_history_expectations.expected_entries", "必须按UTF-8严格升序")
        rebuilt_e1 = _sorted_entries_040(
            copy.deepcopy(h0["inventory"]["entries"])
            + [{"relative": target_name, "manifest_file_sha256": store_save["manifest_file_sha256"]}])
        if _u040_diff(rebuilt_e1, e1_entries) is not None:
            _block("context.post_history_expectations",
                   "E1必须恰为H0旧名单加本次已核验manifest：" + str(_u040_diff(rebuilt_e1, e1_entries)))
        for index, reference_item in enumerate(stored_prior["records"]):
            found = [item for item in hc["prior_history"]["records"]
                     if item.get("event_id") == reference_item.get("event_id")]
            if not found:
                _block("snapshot.prior_history.records[%d].event_id" % index,
                       "旧引用不在当前完整域索引")
            if canonical_json_bytes(found[0]) != canonical_json_bytes(reference_item):
                _block("snapshot.prior_history.records[%d]" % index, "旧引用四字段与当前索引不一致")
        explained = {entry["relative"]: entry["manifest_file_sha256"]
                     for entry in hc["inventory"]["entries"]}
        for entry in e1_entries:
            if entry["relative"] not in explained \
                    or explained[entry["relative"]] != entry["manifest_file_sha256"]:
                _block("context.post_history_expectations.expected_entries",
                       f"E1条目不在当前完整域：{entry['relative']}")
        target_verified = _target_verification_040(hc, target_name)
        if canonical_json_bytes(identity) != canonical_json_bytes(target_verified["identity"]):
            _block("identity", "目标身份与当前完整核验身份不一致")
        envelope_files = sorted([
            _u040_descriptor(_project_relative(envelope / name), envelope_captures[name]["bytes"],
                             _parse_json_object(envelope_captures[name]["bytes"], name))
            for name in INITIAL_ENVELOPE_FILES], key=lambda item: item["relative"].encode("utf-8"))
        # R1-H1：恢复侧同样区分候选（真实 store/Hc 返回 + writer 缓冲）与
        # 预期（目标叶六文件字节 + 当前声明域重建的 Hc + writer 缓冲 + 叶内身份）。
        rebuilt_storage = _rebuild_storage_verification_040(store, snapshot_captures)
        target_leaf_record = _parse_json_object(
            snapshot_captures["judgment_result.json"]["bytes"], "judgment_result.json")["record"]
        leaf_identity = {"batch_id": target_leaf_record["binding"]["batch_id"],
                         "event_id": target_leaf_record["human_initial_judgment"]["event_id"],
                         "request_id": target_leaf_record["binding"]["request_id"]}
        candidate_result = _build_success_040(store_save, hc, target_name, record_relative,
                                              envelope, envelope_files, INITIAL_VERIFY_STATUS)
        expected_result = _rebuild_success_040(
            store, INITIAL_VERIFY_STATUS, leaf_identity, record_relative,
            _project_relative(envelope), envelope_captures, rebuilt_storage, expected_hc)
        _audit_initial_success_040(candidate_result, expected_result, store_save, hc,
                                   envelope_captures, envelope_files, identity, record_relative,
                                   _project_relative(envelope), INITIAL_VERIFY_STATUS)
        success = candidate_result
        _validate_receipt_040(receipt, store_save, h1, envelope_captures, record_relative)

        stage = "verify.final"
        _confirm_initial_sources_040(ctx, ctx["history"]["expectations"]["expected_entries"],
                                     target_leaf=target_leaf, target_captures=snapshot_captures,
                                     envelope=envelope, envelope_captures=envelope_captures)
        _confirm_initial_writers_040(snapshot_captures)
        if _initial_lock_path(Path(namespace["path"])).exists():
            _block("lock", "末端确认时出现技术锁")
        return copy.deepcopy(success)
    except (RuntimeGate1Blocked, RuntimeGate1Error):
        raise
    except Exception as exc:
        raise RuntimeGate1Error(stage, f"{type(exc).__name__}: {exc}") from exc


def _sorted_entries_040(entries):
    return sorted(entries, key=lambda item: item["relative"].encode("utf-8"))


def _sorted_records_040(records):
    return sorted(records, key=lambda item: item["event_id"].encode("utf-8"))


def _u040_keys_list_descriptors_040(value) -> list:
    if type(value) is not list or len(value) != 6:
        _block("context.snapshot_files", "必须恰六项")
    return [_validate_descriptor_040(raw, "context.snapshot_files[%d]" % index)
            for index, raw in enumerate(value)]


def _confirm_initial_writers_040(captures) -> None:
    for name in INITIAL_SNAPSHOT_FILES:
        _recheck_capture(captures[name], "snapshots." + name)


def _validate_started_040(started, registry, ctx, namespace, record_relative) -> None:
    sources = ctx["sources"]
    _u040_const(started["started_version"], INITIAL_STARTED_VERSION, "started.started_version")
    _u040_text(started["batch_id"], "started.batch_id")
    _u040_text(started["request_id"], "started.request_id")
    if started["batch_id"] != registry["batch_id"]:
        _block("started.batch_id", "与已核验登记批次不一致")
    if started["record_relative"] != record_relative:
        _block("started.record_relative", "与显式目标不一致")
    source = _u040_keys(started["source_binding"], INITIAL_SOURCE_BINDING_KEYS,
                        "started.source_binding")
    for key in ("source_batch_relative", "runtime_relative", "gate1_event_relative",
                "gate2_event_relative", "database_relative"):
        _u040_relative(source[key], "started.source_binding." + key)
    if source["runtime_relative"] != _project_relative(Path(sources["leaf"])):
        _block("started.source_binding.runtime_relative", "与当前运行登记叶不一致")
    if source["gate1_event_relative"] != _project_relative(Path(sources["event_path"])):
        _block("started.source_binding.gate1_event_relative", "与当前 Gate1 事件不一致")
    if source["gate2_event_relative"] != _project_relative(Path(ctx["gate2_event"])):
        _block("started.source_binding.gate2_event_relative", "与当前 Gate2 事件不一致")
    if source["database_relative"] != _project_relative(Path(sources["database_capture"]["path"])):
        _block("started.source_binding.database_relative", "与当前数据库目标不一致")
    binding = _u040_keys(source["registry_binding"], INITIAL_REGISTRY_BINDING_KEYS,
                         "started.source_binding.registry_binding")
    _u040_const(binding["registry_version"], registry["registry_version"],
                "started.source_binding.registry_binding.registry_version")
    _u040_hash(binding["registry_file_sha256"],
               "started.source_binding.registry_binding.registry_file_sha256")
    _u040_nonneg(binding["registry_byte_size"],
                 "started.source_binding.registry_binding.registry_byte_size")
    _u040_hash(binding["run_binding_sha256"],
               "started.source_binding.registry_binding.run_binding_sha256")
    capture = sources["leaf_captures"]["registry"]
    if binding["registry_file_sha256"] != capture["file_sha256"] \
            or binding["registry_byte_size"] != capture["byte_size"]:
        _block("started.source_binding.registry_binding.registry_file_sha256",
               "与本次实读登记文件长度/SHA不一致")
    if binding["run_binding_sha256"] != fingerprint(registry["run_binding"]):
        _block("started.source_binding.registry_binding.run_binding_sha256",
               "必须为 run_binding 对象规范指纹（不是登记文件FILE）")
    _u040_keys(binding["initial_judgment_history"], INITIAL_HISTORY_KEYS,
               "started.source_binding.registry_binding.initial_judgment_history")
    if canonical_json_bytes(binding["initial_judgment_history"]) \
            != canonical_json_bytes(registry["initial_judgment_history"]):
        _block("started.source_binding.registry_binding.initial_judgment_history",
               "与已核验登记声明域不一致")
    contract = _u040_keys(source["contract_effective_record"], INITIAL_CONTRACT_RECORD_KEYS,
                          "started.source_binding.contract_effective_record")
    effective = sources["static_captures"]["project"][CONTRACT_EFFECTIVE_RELATIVE]
    if contract["relative"] != CONTRACT_EFFECTIVE_RELATIVE \
            or contract["file_sha256"] != effective["file_sha256"] \
            or contract["byte_size"] != effective["byte_size"]:
        _block("started.source_binding.contract_effective_record",
               "与生效登记原件实读长度/SHA不一致")
    _u040_nonneg(contract["byte_size"],
                 "started.source_binding.contract_effective_record.byte_size")
    pre = _u040_keys(started["pre_history_binding"], INITIAL_PRE_HISTORY_KEYS,
                     "started.pre_history_binding")
    if pre["namespace_relative"] != namespace["relative"]:
        _block("started.pre_history_binding.namespace_relative", "与已绑定声明域不一致")
    _u040_text(pre["declared_scope"], "started.pre_history_binding.declared_scope")
    _u040_hash(pre["prior_history_fingerprint"],
               "started.pre_history_binding.prior_history_fingerprint")
    _validate_boundaries_040(started["boundaries"], "started.boundaries")


def _validate_receipt_040(receipt, store_save, h1, envelope_captures, record_relative) -> None:
    _u040_const(receipt["receipt_version"], INITIAL_RECEIPT_VERSION, "receipt.receipt_version")
    identity = _u040_keys(receipt["identity"], INITIAL_IDENTITY_KEYS, "receipt.identity")
    for key in INITIAL_IDENTITY_KEYS:
        _u040_text(identity[key], "receipt.identity." + key)
    if canonical_json_bytes(identity) != canonical_json_bytes(store_save["identity"]):
        _block("receipt.identity", "与目标完整核验身份不一致")
    if receipt["record_relative"] != record_relative:
        _block("receipt.record_relative", "与显式目标不一致")
    _u040_hash(receipt["started_file_sha256"], "receipt.started_file_sha256")
    _u040_hash(receipt["context_file_sha256"], "receipt.context_file_sha256")
    _u040_hash(receipt["snapshot_manifest_file_sha256"],
               "receipt.snapshot_manifest_file_sha256")
    _u040_hash(receipt["post_history_fingerprint"], "receipt.post_history_fingerprint")
    if receipt["started_file_sha256"] != envelope_captures[INITIAL_STARTED_FILE]["file_sha256"]:
        _block("receipt.started_file_sha256", "与 started writer FILE 不一致（不是对象FP）")
    if receipt["context_file_sha256"] != envelope_captures[INITIAL_CONTEXT_FILE]["file_sha256"]:
        _block("receipt.context_file_sha256", "与 context writer FILE 不一致（不是对象FP）")
    if receipt["snapshot_manifest_file_sha256"] != store_save["manifest_file_sha256"]:
        _block("receipt.snapshot_manifest_file_sha256", "与目标 manifest 实际字节不一致")
    if receipt["post_history_fingerprint"] != fingerprint(h1["prior_history"]):
        _block("receipt.post_history_fingerprint", "必须只绑定保存当时H1的prior_history")
    _validate_boundaries_040(receipt["boundaries"], "receipt.boundaries")


def self_sha256() -> str:
    """本脚本自身确切字节的 SHA-256（每次实读，不使用跨调用缓存）。"""
    return _capture_file(MODULE_PATH, "read.self")["file_sha256"]

