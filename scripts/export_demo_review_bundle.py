#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-018 开发态只读审阅包导出与离线核验（独立工具）。

公开入口::

    export_dev_review_bundle(batch_dir, out_dir) -> dict
    verify_dev_review_bundle(bundle_dir) -> dict

CLI::

    export --batch-dir <batch> --out-dir <new_bundle_dir>
    verify --bundle-dir <bundle_dir>

本工具是**现有证据的只读导出**：

- 导出前真实调用冻结宿主的公开 ``inspect_dev_batch``，要求该批次处于 READY 的开发态
  ``0008`` 停止点；不信任调用方传入的 status 字典，也不重写宿主协议。
- 只复制固定白名单里的 22 份来源文件（确切字节），另加 ``host_status.json`` 与 ``README.md``，
  共 24 份 payload，最后写 ``manifest.json``。
- 离线核验只读包内固定文件，不读取原批次、数据库或运行宿主/核心。
- 不推进工作流、不生成判断/AI 建议、不建立正式契约或真实 Gate、不增加 ``0009``。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOST_PATH = PROJECT_ROOT / "scripts" / "run_demo_workflow.py"
EXPORTER_PATH = Path(__file__).resolve()
BATCHES_ROOT = PROJECT_ROOT / "data" / "batches"
BUNDLE_ROOT = PROJECT_ROOT / "data" / "review_bundles"

MANIFEST_NAME = "manifest.json"
README_NAME = "README.md"
STATUS_NAME = "host_status.json"
FAILURE_NAME = "failure.json"
EVIDENCE_DIR = "evidence"
MANIFEST_VERSION = "TASK-018-dev-review-bundle-1.0"
FAILURE_VERSION = "TASK-018-dev-review-bundle-failure-1.0"
VERIFIED_STATUS = "DEV_REVIEW_BUNDLE_VERIFIED"
VERIFY_SCOPE = "COPIED_BYTES_ONLY"
OPERATION_RECORD_INITIAL_JUDGMENT = "RECORD_SIMULATED_INITIAL_JUDGMENT"
RECORDED_STATUS = "SIMULATED_INITIAL_JUDGMENT_RECORDED"
FACT_PACKET_STATUS = "FACT_PACKET_RECORDED"
HASH_PATTERN = re.compile(r"\A[0-9a-f]{64}\Z")
PACKET_CANONICAL_FIELDS = ("fact_packet_sha256",)
COPIES = 22
PAYLOADS = 24
EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_ERROR = 2

# 固定白名单：包内相对路径 → status 中的初始绑定读数（逐项明确映射，不由清单驱动源读取）
SOURCE_FILES = (
    ("batch_manifest.json", ("verified_files", "receive_manifest")),
    ("checks/quality_report.json", ("verified_files", "quality_report")),
    ("gate1_packet.md", ("verified_files", "gate1_packet")),
    ("workflow/host_manifest.json", ("host_manifest", "file_sha256")),
    ("workflow/checkpoints/0001.json", ("checkpoints", 0, "file_sha256")),
    ("workflow/checkpoints/0002.json", ("checkpoints", 1, "file_sha256")),
    ("workflow/checkpoints/0003.json", ("checkpoints", 2, "file_sha256")),
    ("workflow/checkpoints/0004.json", ("checkpoints", 3, "file_sha256")),
    ("workflow/checkpoints/0005.json", ("checkpoints", 4, "file_sha256")),
    ("workflow/checkpoints/0006.json", ("checkpoints", 5, "file_sha256")),
    ("workflow/checkpoints/0007.json", ("checkpoints", 6, "file_sha256")),
    ("workflow/checkpoints/0008.json", ("checkpoints", 7, "file_sha256")),
    ("workflow/screening/screening_report.json", ("screening", "report_file_sha256")),
    ("workflow/crosscheck/crosscheck_report.json", ("crosscheck", "report_file_sha256")),
    ("workflow/fact_packet/started.json", ("fact_packet", "started_file_sha256")),
    ("workflow/fact_packet/fact_packet.json", ("fact_packet", "packet_file_sha256")),
    ("workflow/fact_packet/fact_packet.md", ("fact_packet", "markdown_file_sha256")),
    ("workflow/fact_packet/artifacts.json", ("fact_packet", "artifacts_file_sha256")),
    ("workflow/initial_judgment/started.json", ("initial_judgment", "started_file_sha256")),
    ("workflow/initial_judgment/submission.json", ("initial_judgment", "submission_file_sha256")),
    ("workflow/initial_judgment/initial_judgment.json",
     ("initial_judgment", "initial_judgment_file_sha256")),
    ("workflow/initial_judgment/artifacts.json", ("initial_judgment", "artifacts_file_sha256")),
)
# status 中声明这些来源的相对路径；用于确认映射指向的确实是同一个固定文件
STATUS_PATH_FIELDS = (
    ("workflow/host_manifest.json", ("host_manifest", "path")),
    ("workflow/screening/screening_report.json", ("screening", "report_path")),
    ("workflow/crosscheck/crosscheck_report.json", ("crosscheck", "report_path")),
    ("workflow/fact_packet/started.json", ("fact_packet", "started_path")),
    ("workflow/fact_packet/fact_packet.json", ("fact_packet", "packet_path")),
    ("workflow/fact_packet/fact_packet.md", ("fact_packet", "markdown_path")),
    ("workflow/fact_packet/artifacts.json", ("fact_packet", "artifacts_path")),
    ("workflow/initial_judgment/started.json", ("initial_judgment", "started_path")),
    ("workflow/initial_judgment/submission.json", ("initial_judgment", "submission_path")),
    ("workflow/initial_judgment/initial_judgment.json",
     ("initial_judgment", "initial_judgment_path")),
    ("workflow/initial_judgment/artifacts.json", ("initial_judgment", "artifacts_path")),
)


class DevReviewBundleBlocked(Exception):
    """协议、前提或路径不符（退出码 1）。"""

    def __init__(self, message: str, field: str = "", reasons: list | None = None):
        super().__init__(message)
        self.field = field
        self.reasons = reasons or [message]


class DevReviewBundleError(Exception):
    """运行或 I/O 失败（退出码 2，保留 cause 链）。"""

    def __init__(self, message: str, reasons: list | None = None, stage: str = ""):
        super().__init__(message)
        self.reasons = reasons or [message]
        self.stage = stage


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def canonical_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def canonical_sha256(payload) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def json_bytes(payload) -> bytes:
    """明确 UTF-8 无 BOM / LF 序列化。"""
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _blocked(field: str, reason: str) -> None:
    raise DevReviewBundleBlocked(f"字段 {field} 不可用：{reason}", field=field)


def _require(condition: bool, field: str, reason: str) -> None:
    if not condition:
        _blocked(field, reason)


def _is_hash(value) -> bool:
    return isinstance(value, str) and bool(HASH_PATTERN.match(value))


def _lookup(payload: dict, path: tuple, label: str):
    current = payload
    for key in path:
        if isinstance(key, int):
            _require(isinstance(current, list) and len(current) > key, label,
                     f"缺少 {path} 对应的条目")
            current = current[key]
        else:
            _require(isinstance(current, dict) and key in current, label,
                     f"缺少 {path} 对应的字段")
            current = current[key]
    return current


_host_module = None


def _host():
    """按现有加载方式导入冻结宿主（仅导出路径使用；离线核验不依赖它）。"""
    global _host_module
    if _host_module is None:
        spec = importlib.util.spec_from_file_location("dev_review_bundle_host", HOST_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules["dev_review_bundle_host"] = module
        spec.loader.exec_module(module)
        _host_module = module
    return _host_module


def _exception_chain(exc: BaseException) -> list:
    chain = []
    current: BaseException | None = exc
    while current is not None and len(chain) < 12:
        chain.append({"class": type(current).__name__, "message": str(current)})
        current = current.__cause__ or current.__context__
    return chain


def _write_exclusive(path: Path, data: bytes, stage: str) -> str:
    """独占创建并写入确切字节，写后读回比较。"""
    try:
        with open(path, "xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise DevReviewBundleBlocked(f"文件已存在，不覆盖：{path}", field=str(path)) from exc
    except OSError as exc:
        raise DevReviewBundleError(f"写入失败（不宣称成功）：{path}（{exc}）", stage=stage) from exc
    try:
        readback = path.read_bytes()
    except OSError as exc:
        raise DevReviewBundleError(f"写后读回失败（不宣称成功）：{path}（{exc}）",
                                   stage=stage) from exc
    if readback != data:
        raise DevReviewBundleError(
            f"写后读回字节不一致（不宣称成功）：{path}"
            f"（写 {len(data)} 字节，读回 {len(readback)} 字节）", stage=stage)
    return hashlib.sha256(readback).hexdigest()


# ---------------------------------------------------------------------------
# 路径检查
# ---------------------------------------------------------------------------


def _resolve_source_batch(batch_dir) -> Path:
    target = Path(batch_dir)
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
    else:
        target = target.resolve()
    _require(target.is_dir(), "batch_dir", f"必须是已存在的批次目录，实际 {target}")
    try:
        relative = target.relative_to(BATCHES_ROOT.resolve())
    except ValueError:
        _blocked("batch_dir", f"必须是宿主支持的批次路径（位于 {BATCHES_ROOT} 之下），实际 {target}")
    _require(len(relative.parts) == 2, "batch_dir",
             f"必须是 data/batches/<父目录>/<批次> 形式，实际 {relative.as_posix()}")
    return target


def _resolve_bundle_out(out_dir, source_batch: Path, *, root: Path | None = None) -> Path:
    root = (root or BUNDLE_ROOT)
    root_resolved = root.resolve()
    target = Path(out_dir)
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
    else:
        target = target.resolve()
    try:
        relative = target.relative_to(root_resolved)
    except ValueError:
        _blocked("out_dir", f"必须位于 {root_resolved} 之下，实际 {target}")
    _require(len(relative.parts) >= 1 and bool(relative.parts[0]), "out_dir",
             f"必须是 {root_resolved} 下的具名子目录，实际 {target}")
    _require(not target.exists(), "out_dir",
             f"必须是从未存在的目录（既有目录与空目录一并拒绝）：{target}")
    # 与源批次、外置数据库的关系
    source_resolved = source_batch.resolve()
    _require(target != source_resolved, "out_dir", "不得等于源批次目录")
    _require(source_resolved not in target.parents and target not in source_resolved.parents,
             "out_dir", f"不得与源批次互为祖先或后代：{target} 与 {source_resolved}")
    try:
        database_path = _host()._gate2_paths(source_batch, "export_bundle")["database_path"]
    except Exception:  # noqa: BLE001 - 路径推导失败按运行错误处理
        database_path = None
    if database_path is not None:
        database_path = Path(database_path).resolve()
        _require(target != database_path, "out_dir", "不得等于外置数据库路径")
        _require(database_path not in target.parents and target not in database_path.parents,
                 "out_dir", f"不得与外置数据库互为祖先或后代：{target} 与 {database_path}")
    return target


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------


def _status_requirement(status: dict, stage: str) -> None:
    _require(isinstance(status, dict), "status", f"必须是对象，实际 {type(status).__name__}")
    _require(status.get("status") == "READY", "status.status",
             f"必须是 READY，实际 {status.get('status')!r}")
    _require(status.get("mode") == "DEVELOPMENT_TEST_ONLY", "status.mode",
             f"必须是 DEVELOPMENT_TEST_ONLY，实际 {status.get('mode')!r}")
    _require(status.get("initial_judgment_status") == RECORDED_STATUS,
             "status.initial_judgment_status",
             f"必须是 {RECORDED_STATUS}，实际 {status.get('initial_judgment_status')!r}")
    _require(status.get("fact_packet_status") == FACT_PACKET_STATUS, "status.fact_packet_status",
             f"必须是 {FACT_PACKET_STATUS}，实际 {status.get('fact_packet_status')!r}")
    _require(status.get("crosscheck_status") == "RULE_CROSSCHECK_RECORDED",
             "status.crosscheck_status", "必须是 RULE_CROSSCHECK_RECORDED")
    _require((status.get("crosscheck") or {}).get("matched") is True, "status.crosscheck.matched",
             "必须是完整 MATCHED 的复算报告")
    _require(((status.get("crosscheck") or {}).get("difference_count")) == 0,
             "status.crosscheck.difference_count", "MATCHED 要求差异数为 0")
    _require((status.get("crosscheck") or {}).get("unmatched_dimensions") == [],
             "status.crosscheck.unmatched_dimensions", "MATCHED 要求无未匹配维度")
    checkpoints = status.get("checkpoints")
    _require(isinstance(checkpoints, list) and [item.get("revision") for item in checkpoints]
             == list(range(1, 9)), "status.checkpoints",
             f"必须恰为合法 0001—0008，实际 "
             f"{[item.get('revision') for item in checkpoints] if isinstance(checkpoints, list) else checkpoints!r}")
    _require(status.get("real_approvals") == 0, "status.real_approvals",
             f"真实批准数必须为 0，实际 {status.get('real_approvals')!r}")
    _require(status.get("next_step_allowed") is False, "status.next_step_allowed",
             "必须是严格 false")
    state_approvals = [
        _lookup(status, ("checkpoints", 7, "file_sha256"), "status.checkpoints"), ]
    del state_approvals
    _require((status.get("initial_judgment") or {}).get("ai_action_simulation_allowed") is False,
             "status.initial_judgment.ai_action_simulation_allowed",
             "AI 动作的实际许可必须严格 false（AI 未开放）")
    _require(status.get("host_version"), "status.host_version", "必须给出宿主版本")
    _require(isinstance(status.get("checkpoint_0008") if False else True, bool), "status", "")
    # 0008 与模拟边界
    initial = status.get("initial_judgment") or {}
    for key in ("record_sha256", "initial_judgment_file_sha256", "submission_file_sha256",
                "artifacts_file_sha256", "started_file_sha256"):
        _require(_is_hash(initial.get(key)), f"status.initial_judgment.{key}",
                 f"必须是完整 64 位小写十六进制指纹，实际 {initial.get(key)!r}")
    _require(initial.get("record_version") == "TASK-016-initial-judgment-record-1.0",
             "status.initial_judgment.record_version", "必须是冻结初判记录协议版本")
    _require(initial.get("actor_kind") == "SIMULATED_HUMAN", "status.initial_judgment.actor_kind",
             "必须是 SIMULATED_HUMAN")
    _require(initial.get("simulation") == "SIMULATED_TEST_ONLY",
             "status.initial_judgment.simulation", "必须是 SIMULATED_TEST_ONLY")
    fact = status.get("fact_packet") or {}
    for key in ("packet_sha256", "packet_file_sha256", "markdown_file_sha256",
                "artifacts_file_sha256", "started_file_sha256"):
        _require(_is_hash(fact.get(key)), f"status.fact_packet.{key}",
                 f"必须是完整 64 位小写十六进制指纹，实际 {fact.get(key)!r}")


def _collect_expectations(status: dict, batch_dir: Path, stage: str) -> dict:
    """从第一次真实 status 收集 22 份来源的初始绑定与身份读数（唯一预期来源）。"""
    expectations: dict = {}
    for relative, lookup in SOURCE_FILES:
        value = _lookup(status, lookup, "status")
        _require(_is_hash(value), f"status[{'.'.join(str(item) for item in lookup)}]",
                 f"必须是完整 64 位小写十六进制文件哈希，实际 {value!r}")
        expectations[relative] = value
    for relative, lookup in STATUS_PATH_FIELDS:
        declared = _lookup(status, lookup, "status")
        _require(isinstance(declared, str), f"status[{'.'.join(str(item) for item in lookup)}]",
                 f"必须是字符串相对路径，实际 {declared!r}")
        _require(declared.replace("\\", "/") == relative,
                 f"status[{'.'.join(str(item) for item in lookup)}]",
                 f"必须指向固定来源 {relative}，实际 {declared!r}")
    checkpoints = status["checkpoints"]
    for index, (relative, _lookup_path) in enumerate(SOURCE_FILES[4:12], start=1):
        declared = checkpoints[index - 1].get("path")
        _require(isinstance(declared, str) and declared.replace("\\", "/") == relative,
                 f"status.checkpoints[{index - 1}].path",
                 f"必须指向 {relative}，实际 {declared!r}")
    gate2_tail = status.get("gate2_tail") or {}
    _require(_is_hash(gate2_tail.get("database_sha256")), "status.gate2_tail.database_sha256",
             f"必须是数据库初始字节哈希，实际 {gate2_tail.get('database_sha256')!r}")
    host_manifest = status.get("host_manifest") or {}
    _require(_is_hash(host_manifest.get("file_sha256")), "status.host_manifest.file_sha256",
             "必须是宿主清单初始文件哈希")
    expectations["__database_sha256__"] = gate2_tail["database_sha256"]
    return expectations


def _read_sources(batch_dir: Path, expectations: dict, stage: str) -> dict:
    """每份来源一次读取同一缓冲：从该缓冲取长度、SHA-256 与 JSON 对象。"""
    sources: dict = {}
    for relative, _lookup_path in SOURCE_FILES:
        path = batch_dir / relative
        _require(path.is_file(), relative, f"缺少来源文件（{path}）")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise DevReviewBundleError(f"读取来源失败：{path}（{exc}）", stage=stage) from exc
        digest = hashlib.sha256(data).hexdigest()
        _require(expectations[relative] == digest, relative,
                 f"来源字节与第一次真实 status 的初始绑定不一致："
                 f"期望 {expectations[relative]!r}，实际 {digest!r}")
        entry = {"relative": relative, "data": data, "bytes": len(data), "file_sha256": digest,
                 "path": path}
        if relative.endswith(".json"):
            try:
                entry["object"] = json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise DevReviewBundleBlocked(f"来源不是可解析 JSON：{relative}（{exc}）",
                                             field=relative) from exc
        sources[relative] = entry
    database_path = _host()._gate2_paths(batch_dir, stage)["database_path"]
    try:
        database_data = Path(database_path).read_bytes()
    except OSError as exc:
        raise DevReviewBundleError(f"读取外置数据库失败：{database_path}（{exc}）",
                                   stage=stage) from exc
    database_sha = hashlib.sha256(database_data).hexdigest()
    _require(expectations["__database_sha256__"] == database_sha, str(database_path),
             f"数据库字节与第一次真实 status 的初始绑定不一致："
             f"期望 {expectations['__database_sha256__']!r}，实际 {database_sha!r}")
    sources["__database__"] = {"path": Path(database_path), "data": database_data,
                               "file_sha256": database_sha}
    return sources


def _readme_bytes(status: dict, sources: dict) -> bytes:
    packet = sources["workflow/fact_packet/fact_packet.json"]["object"]
    initial = sources["workflow/initial_judgment/initial_judgment.json"]["object"]
    summary = packet["summary"]
    entity = packet["entity"]
    rule_counts = summary["rule_counts"]
    record = initial["record"]
    lines = [
        "# 开发演示审阅包（TASK-018）",
        "",
        "> 合成数据、开发演示；本包不是真实审计底稿、不是正式契约、不是真实 Gate 批准。",
        "> 模拟初判**已保存**（SIMULATED_HUMAN / SIMULATED_TEST_ONLY）；真实人类独立初判**未保存**；",
        "> 真实 Gate **未批准**（gate1_approval=null、gate2_approval=null、real_approvals=0）；AI **未开放**。",
        "> 本包只包含选定审阅材料，不是完整批次备份、不是可恢复宿主目录，不构成身份认证或独立审计保证。",
        "",
        "## 批次与主体",
        f"- 批次：{status['batch_id']}",
        f"- 主体：{entity['company']}",
        f"- 期间：{entity['period']['period_start']}—{entity['period']['period_end']}"
        f"（截至 {entity['cutoff_date']}）",
        f"- 币种：{entity['currency']}",
        f"- 宿主版本：{status['host_version']}；事实包协议：{packet['packet_version']}",
        "",
        "## 已核验事实摘要（直接取自已核验 status 与事实包，未重新筛查或计算）",
        f"- 线索总数：{summary['total_findings']}",
        f"- R01：{rule_counts.get('R01')}；R02：{rule_counts.get('R02')}；"
        f"R03：{rule_counts.get('R03')}；R04：{rule_counts.get('R04')}",
        f"- R02 应付单净付款超额合计（分）：{summary.get('r02_overpayment_total_cents')}",
        "",
        "## 指纹（文件字节哈希与对象规范指纹分列）",
        f"- 事实包对象规范指纹（packet_sha256）：{status['fact_packet']['packet_sha256']}",
        f"- 事实包文件字节哈希：{status['fact_packet']['packet_file_sha256']}",
        f"- 模拟初判记录对象规范指纹（record_sha256）："
        f"{status['initial_judgment']['record_sha256']}",
        f"- 模拟初判记录文件字节哈希："
        f"{status['initial_judgment']['initial_judgment_file_sha256']}",
        f"- 提交事件 ID：{status['initial_judgment']['submission_event_id']}",
        "",
        "## 材料（包内相对链接，均在 evidence/ 下）",
    ]
    for relative, _lookup_path in SOURCE_FILES:
        lines.append(f"- [evidence/{relative}](evidence/{relative})")
    lines += [
        "- [host_status.json](host_status.json)（导出时冻结宿主公开 status 的完整返回）",
        "",
        "## 能力边界",
        "- 模拟初判不等于真实人类独立初判；调用方身份未经认证。",
        "- 不含 0009、不生成 AI 建议、无候选等级与终判、无正式契约与真实 Gate。",
        "- 离线核验只确认包内文件与清单一致，不证明原始业务真实性，也不重新批准批次。",
        f"- 原事实底稿的既有 banner 保留在 evidence/workflow/fact_packet/fact_packet.md。",
        f"- 记录内的初判原文（assessment/reason）按原字符串保留，未被本工具改写。",
        f"- 记录边界：next_step_allowed="
        f"{json.dumps(record['next_step_allowed'])}, ai_suggestion_allowed="
        f"{json.dumps(record['ai_suggestion_allowed'])}, human_initial_judgment="
        f"{json.dumps(record['human_initial_judgment'])}。",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _call_status(host, batch_dir: Path, step: str, state: dict) -> dict:
    """真实调用冻结公开 status，并把宿主异常按前提/运行分列映射（保留原因链）。"""
    try:
        status = host.inspect_dev_batch(batch_dir)
    except host.WorkflowHostBlocked as exc:
        raise DevReviewBundleBlocked(
            f"冻结宿主前提/协议阻断（不导出）：{exc}", field="host_status",
            reasons=[str(exc)] + [str(item) for item in getattr(exc, "reasons", []) or []]) from exc
    except host.WorkflowHostError as exc:
        raise DevReviewBundleError(
            f"冻结宿主运行失败（不导出）：{exc}",
            reasons=[str(exc)] + [str(item) for item in getattr(exc, "reasons", []) or []],
            stage="export") from exc
    except (DevReviewBundleBlocked, DevReviewBundleError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise DevReviewBundleError(f"调用冻结宿主 status 出现意外错误：{type(exc).__name__}: {exc}",
                                   ["阶段=export"], "export") from exc
    state["steps"].append(step)
    return status


def _export_inner(batch_dir, out_dir, state: dict) -> dict:
    stage = "export"
    source_batch = _resolve_source_batch(batch_dir)
    target_out = _resolve_bundle_out(out_dir, source_batch)
    host = _host()
    status = _call_status(host, source_batch, "initial_status", state)
    state["initial_status"] = status
    _status_requirement(status, stage)
    expectations = _collect_expectations(status, source_batch, stage)
    state["steps"].append("expectations_collected")
    sources = _read_sources(source_batch, expectations, stage)
    state["steps"].append("sources_read")

    status_bytes = json_bytes(status)
    readme_bytes = _readme_bytes(status, sources)
    payloads = [{"role": "copied_source", "bundle_relative": f"{EVIDENCE_DIR}/{relative}",
                 "source_relative": relative, "data": sources[relative]["data"],
                 "initial_file_sha256": expectations[relative]}
                for relative, _lookup_path in SOURCE_FILES]
    payloads.append({"role": "host_status", "bundle_relative": STATUS_NAME, "data": status_bytes,
                     "initial_file_sha256": None})
    payloads.append({"role": "readme", "bundle_relative": README_NAME, "data": readme_bytes,
                     "initial_file_sha256": None})

    try:
        target_out.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise DevReviewBundleBlocked(f"输出目录已存在，不接管、不覆盖：{target_out}",
                                     field="out_dir") from exc
    except OSError as exc:
        raise DevReviewBundleError(f"无法创建输出目录 {target_out}：{exc}", stage=stage) from exc
    state["out_dir"] = target_out
    state["created"] = True

    for payload in payloads:
        path = target_out / payload["bundle_relative"]
        path.parent.mkdir(parents=True, exist_ok=True)
        payload["file_sha256"] = _write_exclusive(path, payload["data"], stage)
        payload["bytes"] = len(payload["data"])
        payload["bundle_path"] = path
    state["steps"].append("payloads_written")

    status_last = _call_status(host, source_batch, "final_status", state)
    _require(canonical_json(status_last) == canonical_json(status), "final_status",
             "末次真实公开 status 必须与第一次完整返回严格规范相等"
             "（不接受用最新读数替换初始预期）")

    sources_again = _read_sources(source_batch, expectations, stage)
    state["steps"].append("sources_rechecked")
    for payload in payloads:
        path = payload["bundle_path"]
        readback = path.read_bytes()
        _require(readback == payload["data"], payload["bundle_relative"],
                 "复核发现输出字节与待写字节不一致")
    state["steps"].append("payloads_rechecked")

    host_manifest = sources["workflow/host_manifest.json"]["object"]
    packet = sources["workflow/fact_packet/fact_packet.json"]["object"]
    initial = sources["workflow/initial_judgment/initial_judgment.json"]["object"]
    checkpoint8 = sources["workflow/checkpoints/0008.json"]["object"]
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "bundle_kind": "DEV_REVIEW_BUNDLE",
        "batch_id": status["batch_id"],
        "source_batch": {
            "relative": source_batch.relative_to(PROJECT_ROOT).as_posix(),
            "batch_id": status["batch_id"],
            "checkpoints_total": len(status["checkpoints"]),
        },
        "host_version": status["host_version"],
        "host_code_sha256": {
            "host_code": host_manifest["bindings"]["host_code_sha256"]["host_code"],
            "initial_judgment_core":
                host_manifest["bindings"]["host_code_sha256"]["initial_judgment_core"],
            "run_bindings_sha256": status["bindings_sha256"],
        },
        "exporter": {"path": "scripts/export_demo_review_bundle.py",
                     "sha256": file_sha256(EXPORTER_PATH)},
        "canonical_fingerprints": {
            "packet_sha256": status["fact_packet"]["packet_sha256"],
            "packet_file_sha256": status["fact_packet"]["packet_file_sha256"],
            "record_sha256": status["initial_judgment"]["record_sha256"],
            "record_file_sha256":
                status["initial_judgment"]["initial_judgment_file_sha256"],
            "checkpoint_0008_file_sha256": expectations["workflow/checkpoints/0008.json"],
            "database_sha256": expectations["__database_sha256__"],
        },
        "boundaries": {
            "mode": status["mode"],
            "simulation": status["initial_judgment"]["simulation"],
            "actor_kind": status["initial_judgment"]["actor_kind"],
            "contract_status": status["contract_status"],
            "real_approvals": status["real_approvals"],
            "gate1_approval": initial["record"]["gate1_approval"],
            "gate2_approval": initial["record"]["gate2_approval"],
            "human_initial_judgment": initial["record"]["human_initial_judgment"],
            "ai_suggestion": initial["record"]["ai_suggestion"],
            "final_judgment": initial["record"]["final_judgment"],
            "next_step_allowed": status["next_step_allowed"],
            "ai_suggestion_allowed": initial["record"]["ai_suggestion_allowed"],
            "note": ("模拟初判已保存；真实人类独立初判未保存，真实 Gate 未批准，AI 未开放；"
                     "database 字节只做初始绑定哈希记录，不复制数据库文件"),
        },
        "checkpoint_0008": {
            "revision": checkpoint8["revision"],
            "operation_kind": checkpoint8["operation"]["kind"],
            "record_sha256": checkpoint8["operation"]["record_sha256"],
            "packet_sha256": checkpoint8["operation"]["packet_sha256"],
            "previous_file_sha256": checkpoint8["previous_file_sha256"],
        },
        "payloads": [
            {"role": payload["role"], "relative": payload["bundle_relative"],
             "bytes": payload["bytes"], "file_sha256": payload["file_sha256"],
             **({"source_relative": payload["source_relative"],
                 "source_initial_file_sha256": payload["initial_file_sha256"]}
                if payload["role"] == "copied_source" else {})}
            for payload in payloads
        ],
        "counts": {"copied_sources": COPIES, "payloads": PAYLOADS},
        "note": ("本清单只描述本包内容；不内嵌自身哈希，不记录导出目标绝对路径，"
                 "不新增当前时间、随机 ID、推断身份或业务判断。"),
    }
    manifest_bytes = json_bytes(manifest)
    manifest_path = target_out / MANIFEST_NAME
    manifest_sha = _write_exclusive(manifest_path, manifest_bytes, stage)
    readback = manifest_path.read_bytes()
    _require(readback == manifest_bytes, MANIFEST_NAME, "写后读回的 manifest 字节与写入结果不一致")
    state["steps"].append("manifest_written")

    # 返回成功前的最后确认：源 22 份 + DB 初始字节、包内固定文件集合、无 failure
    _read_sources(source_batch, expectations, stage)
    expected_relatives = {MANIFEST_NAME, README_NAME, STATUS_NAME}
    expected_relatives |= {f"{EVIDENCE_DIR}/{relative}" for relative, _ in SOURCE_FILES}
    actual_relatives = {path.relative_to(target_out).as_posix()
                        for path in target_out.rglob("*") if path.is_file()}
    _require(actual_relatives == expected_relatives, "bundle.files",
             f"包内固定文件集合不符：多出 {sorted(actual_relatives - expected_relatives)}，"
             f"缺少 {sorted(expected_relatives - actual_relatives)}")
    _require(not (target_out / FAILURE_NAME).exists(), FAILURE_NAME,
             "成功导出不得存在失败诊断")
    # TASK-018-R1 B1：manifest 保存/读回、末次公开 status、来源/DB 复测等**全部必要消费**之后，
    # 返回成功前实读 24 份 payload 与 manifest 的确切字节，与初始待写缓冲比较。
    # 预期来自本次确切待写字节（manifest 自身回报其 writer 返回的读回哈希，不内嵌自身哈希）。
    for payload in payloads:
        readback_final = payload["bundle_path"].read_bytes()
        _require(readback_final == payload["data"], payload["bundle_relative"],
                 "最终字节确认发现输出与待写字节不一致："
                 f"期望 {len(payload['data'])} 字节/{payload['file_sha256']!r}，"
                 f"实际 {len(readback_final)} 字节/"
                 f"{hashlib.sha256(readback_final).hexdigest()!r}")
    manifest_readback_final = manifest_path.read_bytes()
    _require(manifest_readback_final == manifest_bytes, MANIFEST_NAME,
             "最终字节确认发现 manifest 与该次确切待写字节不一致："
             f"期望 {len(manifest_bytes)} 字节/{manifest_sha!r}，"
             f"实际 {len(manifest_readback_final)} 字节/"
             f"{hashlib.sha256(manifest_readback_final).hexdigest()!r}")
    _require(not (target_out / FAILURE_NAME).exists(), FAILURE_NAME,
             "最终字节确认发现成功导出目录出现失败诊断")
    state["steps"].append("final_byte_confirmation")
    state["steps"].append("final_checks")
    return {
        "bundle_status": VERIFIED_STATUS,
        "bundle_dir": str(target_out),
        "manifest_path": str(manifest_path),
        "manifest_file_sha256": manifest_sha,
        "payloads": PAYLOADS,
        "copied_sources": COPIES,
        "batch_id": status["batch_id"],
        "packet_sha256": status["fact_packet"]["packet_sha256"],
        "record_sha256": status["initial_judgment"]["record_sha256"],
        "status_calls": 2,
        "steps": list(state["steps"]),
    }


def _save_failure(state: dict, exc: Exception) -> None:
    out_dir = state.get("out_dir")
    if out_dir is None or not state.get("created"):
        return
    failure_path = Path(out_dir) / FAILURE_NAME
    if failure_path.exists():
        return
    target_exit_code = EXIT_ERROR if isinstance(exc, DevReviewBundleError) else EXIT_BLOCKED
    payload = {
        "failure_version": FAILURE_VERSION,
        "stage": "export",
        "target_exit_code": target_exit_code,
        "exception_class": type(exc).__name__,
        "message": str(exc),
        "reasons": list(getattr(exc, "reasons", []) or [str(exc)]),
        "field": getattr(exc, "field", None),
        "exception_chain": _exception_chain(exc),
        "completed_steps": list(state.get("steps", [])),
        "note": ("导出失败诊断：只写在新输出目录；不修改源批次、不向宿主写失败诊断、"
                 "不清理半写输出、不重试覆盖。"),
    }
    try:
        _write_exclusive(failure_path, json_bytes(payload), "export_failure")
    except (DevReviewBundleBlocked, DevReviewBundleError) as save_exc:
        raise DevReviewBundleError(
            f"导出失败且失败诊断也未能保存：{exc}（保存失败：{save_exc}）",
            reasons=[str(exc), f"保存失败：{save_exc}"], stage="export_failure") from exc


def export_dev_review_bundle(batch_dir, out_dir) -> dict:
    """把已核验的 0008 批次导出为只读审阅包（成功返回字典，失败抛异常）。"""
    state: dict = {"steps": [], "out_dir": None, "created": False}
    try:
        return _export_inner(batch_dir, out_dir, state)
    except (DevReviewBundleBlocked, DevReviewBundleError) as exc:
        try:
            _save_failure(state, exc)
        except DevReviewBundleError as save_exc:
            raise save_exc from exc
        raise
    except Exception as exc:  # noqa: BLE001
        mapped = DevReviewBundleError(f"意外运行失败：{type(exc).__name__}: {exc}",
                                      ["阶段=export", f"原始异常={type(exc).__name__}: {exc}"],
                                      "export")
        mapped.__cause__ = exc
        try:
            _save_failure(state, mapped)
        except DevReviewBundleError as save_exc:
            raise save_exc from exc
        raise mapped from exc


# ---------------------------------------------------------------------------
# 离线核验（只读包内固定文件；不读取原批次/DB/宿主/核心）
# ---------------------------------------------------------------------------


def _verify_manifest_shape(manifest: dict) -> None:
    label = MANIFEST_NAME
    _require(isinstance(manifest, dict), label, f"必须是对象，实际 {type(manifest).__name__}")
    for key in ("manifest_version", "bundle_kind", "batch_id", "source_batch", "host_version",
                "host_code_sha256", "exporter", "canonical_fingerprints", "boundaries",
                "checkpoint_0008", "payloads", "counts", "note"):
        _require(key in manifest, f"{label}.{key}", "缺少必需字段")
    _require(manifest["manifest_version"] == MANIFEST_VERSION, f"{label}.manifest_version",
             f"必须是 {MANIFEST_VERSION}，实际 {manifest['manifest_version']!r}")
    _require(manifest["bundle_kind"] == "DEV_REVIEW_BUNDLE", f"{label}.bundle_kind",
             "必须是 DEV_REVIEW_BUNDLE")
    _require(isinstance(manifest["batch_id"], str) and manifest["batch_id"], f"{label}.batch_id",
             f"必须是非空字符串，实际 {manifest['batch_id']!r}")
    _require("manifest_file_sha256" not in manifest and "manifest_sha256" not in manifest,
             label, "manifest 不得内嵌自身哈希")
    source_batch = manifest["source_batch"]
    _require(isinstance(source_batch, dict), f"{label}.source_batch", "必须是对象")
    _require(isinstance(source_batch.get("relative"), str) and source_batch["relative"],
             f"{label}.source_batch.relative", "必须是非空相对路径字符串")
    _require(_is_strict_int(source_batch.get("checkpoints_total"))
             and source_batch["checkpoints_total"] == 8,
             f"{label}.source_batch.checkpoints_total", "必须是严格整数 8")
    # TASK-018-R2 B3：批次ID是原字符串身份，只做非空字符串检查；
    # 不因其内容“像 64 位十六进制”而拒绝，也不做 strip／截断／大小写／数字转换。
    _require(isinstance(source_batch.get("batch_id"), str) and source_batch["batch_id"] != "",
             f"{label}.source_batch.batch_id",
             "必须是非空批次ID字符串，实际 "
             f"{type(source_batch.get('batch_id')).__name__}: {source_batch.get('batch_id')!r}")
    exporter = manifest["exporter"]
    _require(isinstance(exporter, dict) and _is_hash(exporter.get("sha256")),
             f"{label}.exporter", "必须给出导出工具实测哈希")
    _require(exporter.get("path") == "scripts/export_demo_review_bundle.py",
             f"{label}.exporter.path", "必须是固定工具相对路径")
    _require(isinstance(manifest["host_code_sha256"], dict), f"{label}.host_code_sha256",
             "必须是对象")
    for key in ("host_code", "initial_judgment_core", "run_bindings_sha256"):
        _require(_is_hash(manifest["host_code_sha256"].get(key)),
                 f"{label}.host_code_sha256.{key}", "必须是完整 64 位小写十六进制")
    fingerprints = manifest["canonical_fingerprints"]
    _require(isinstance(fingerprints, dict), f"{label}.canonical_fingerprints", "必须是对象")
    for key in ("packet_sha256", "packet_file_sha256", "record_sha256", "record_file_sha256",
                "checkpoint_0008_file_sha256", "database_sha256"):
        _require(_is_hash(fingerprints.get(key)), f"{label}.canonical_fingerprints.{key}",
                 "必须是完整 64 位小写十六进制（不接受后缀）")
    boundaries = manifest["boundaries"]
    _require(isinstance(boundaries, dict), f"{label}.boundaries", "必须是对象")
    _require(_is_strict_int(boundaries.get("real_approvals"))
             and boundaries["real_approvals"] == 0, f"{label}.boundaries.real_approvals",
             f"必须是严格整数 0，实际 {boundaries.get('real_approvals')!r}")
    for key in ("gate1_approval", "gate2_approval", "human_initial_judgment", "ai_suggestion",
                "final_judgment"):
        _require(boundaries.get(key) is None, f"{label}.boundaries.{key}", "必须是 null")
    _require(boundaries.get("next_step_allowed") is False, f"{label}.boundaries.next_step_allowed",
             "必须是严格 false")
    _require(boundaries.get("ai_suggestion_allowed") is False,
             f"{label}.boundaries.ai_suggestion_allowed", "必须是严格 false")
    _require(boundaries.get("actor_kind") == "SIMULATED_HUMAN", f"{label}.boundaries.actor_kind",
             "必须是 SIMULATED_HUMAN")
    _require(boundaries.get("simulation") == "SIMULATED_TEST_ONLY",
             f"{label}.boundaries.simulation", "必须是 SIMULATED_TEST_ONLY")
    _require(boundaries.get("mode") == "DEVELOPMENT_TEST_ONLY", f"{label}.boundaries.mode",
             "必须是 DEVELOPMENT_TEST_ONLY")
    _require(boundaries.get("contract_status") == "DRAFT_NOT_IN_FORCE",
             f"{label}.boundaries.contract_status", "必须是 DRAFT_NOT_IN_FORCE")
    checkpoint8 = manifest["checkpoint_0008"]
    _require(isinstance(checkpoint8, dict), f"{label}.checkpoint_0008", "必须是对象")
    _require(_is_strict_int(checkpoint8.get("revision")) and checkpoint8["revision"] == 8,
             f"{label}.checkpoint_0008.revision", "必须是严格整数 8")
    _require(checkpoint8.get("operation_kind") == OPERATION_RECORD_INITIAL_JUDGMENT,
             f"{label}.checkpoint_0008.operation_kind",
             f"必须是 {OPERATION_RECORD_INITIAL_JUDGMENT}")
    _require(checkpoint8.get("record_sha256") == fingerprints["record_sha256"],
             f"{label}.checkpoint_0008.record_sha256", "必须等于记录规范指纹")
    _require(checkpoint8.get("packet_sha256") == fingerprints["packet_sha256"],
             f"{label}.checkpoint_0008.packet_sha256", "必须等于事实包规范指纹")
    _require(_is_hash(checkpoint8.get("previous_file_sha256")),
             f"{label}.checkpoint_0008.previous_file_sha256",
             "必须是完整 64 位小写十六进制")
    _require(isinstance(manifest["host_version"], str) and manifest["host_version"] != "",
             f"{label}.host_version", "必须是非空版本身份字符串")
    counts = manifest["counts"]
    _require(isinstance(counts, dict) and _is_strict_int(counts.get("copied_sources"))
             and counts["copied_sources"] == COPIES and _is_strict_int(counts.get("payloads"))
             and counts["payloads"] == PAYLOADS, f"{label}.counts",
             f"必须是严格整数 {COPIES} 份复制件与 {PAYLOADS} 份 payload")
    payloads = manifest["payloads"]
    _require(isinstance(payloads, list) and len(payloads) == PAYLOADS, f"{label}.payloads",
             f"必须恰为 {PAYLOADS} 项，实际 "
             f"{len(payloads) if isinstance(payloads, list) else type(payloads).__name__}")
    seen: set = set()
    copied = 0
    for index, item in enumerate(payloads):
        item_label = f"{label}.payloads[{index}]"
        _require(isinstance(item, dict), item_label, "必须是对象")
        for key in ("role", "relative", "bytes", "file_sha256"):
            _require(key in item, f"{item_label}.{key}", "缺少必需字段")
        role = item["role"]
        _require(role in ("copied_source", "host_status", "readme"), f"{item_label}.role",
                 f"必须是 copied_source/host_status/readme，实际 {role!r}")
        relative = item["relative"]
        _require(isinstance(relative, str) and relative and not relative.startswith("/")
                 and ".." not in Path(relative).parts and "\\" not in relative,
                 f"{item_label}.relative",
                 f"必须是包内固定相对路径（不使用绝对路径、不含 ..）：{relative!r}")
        _require(relative not in seen, f"{item_label}.relative",
                 f"清单路径不得重复：{relative!r}")
        seen.add(relative)
        _require(_is_strict_int(item["bytes"]) and item["bytes"] >= 0, f"{item_label}.bytes",
                 "必须是非负整数")
        _require(_is_hash(item["file_sha256"]), f"{item_label}.file_sha256",
                 "必须是完整 64 位小写十六进制（不接受后缀）")
        if role == "copied_source":
            copied += 1
            _require(isinstance(item.get("source_relative"), str)
                     and item["source_relative"] in dict(SOURCE_FILES),
                     f"{item_label}.source_relative", "必须是白名单内的固定来源相对路径")
            _require(relative == f"{EVIDENCE_DIR}/{item['source_relative']}",
                     f"{item_label}.relative", "复制件必须位于 evidence/ 下并保留相对层级")
            _require(_is_hash(item.get("source_initial_file_sha256")),
                     f"{item_label}.source_initial_file_sha256",
                     "必须记录初始绑定文件哈希")
    _require(copied == COPIES, f"{label}.payloads", f"复制件必须恰为 {COPIES} 份，实际 {copied}")
    expected = {STATUS_NAME, README_NAME}
    expected |= {f"{EVIDENCE_DIR}/{relative}" for relative, _ in SOURCE_FILES}
    _require(seen == expected, f"{label}.payloads",
             f"清单路径集合必须恰为固定白名单：多出 {sorted(seen - expected)}，"
             f"缺少 {sorted(expected - seen)}")


def _fixed_relatives() -> tuple:
    return ((MANIFEST_NAME, README_NAME, STATUS_NAME)
            + tuple(f"{EVIDENCE_DIR}/{relative}" for relative, _ in SOURCE_FILES))


def _is_strict_int(value) -> bool:
    """严格整数：布尔与浮点均不算（避免 True==1、1.0==1 通过相等比较）。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _read_bundle_buffer(bundle: Path, relative: str) -> bytes:
    """包内固定文件的一次缓冲读取：长度/哈希/JSON 对象都从同一个缓冲取得。"""
    path = bundle / relative
    _require(path.is_file(), relative, f"缺少固定文件（{path}）")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise DevReviewBundleError(f"读取包内文件失败：{path}（{exc}）", stage="verify") from exc


def _parse_buffer(data: bytes, label: str):
    _require(not data.startswith(b"\xef\xbb\xbf"), label, "不得带 UTF-8 BOM")
    try:
        return json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DevReviewBundleBlocked(f"不是可解析 JSON：{label}（{exc}）", field=label) from exc


def _require_payload_relations(manifest: dict, buffers: dict) -> None:
    """22 复制件的 actual SHA / payload.file_sha256 / source_initial_file_sha256 / 历史 status 映射一致。"""
    status = _parse_buffer(buffers[STATUS_NAME], STATUS_NAME)
    for item in manifest["payloads"]:
        if item["role"] != "copied_source":
            continue
        relative = item["source_relative"]
        _require(relative in dict(SOURCE_FILES), f"payloads.source_relative",
                 f"必须是白名单内的固定来源：{relative!r}")
        expected_lookup = dict(SOURCE_FILES)[relative]
        status_bound = _lookup(status, expected_lookup, "status")
        _require(_is_hash(status_bound),
                 f"status[{'.'.join(str(part) for part in expected_lookup)}]",
                 f"历史 status 的固定映射必须是完整 64 位小写十六进制，实际 {status_bound!r}")
        bundle_relative = f"{EVIDENCE_DIR}/{relative}"
        _require(bundle_relative in buffers, bundle_relative, "缺少复制件缓冲")
        actual = hashlib.sha256(buffers[bundle_relative]).hexdigest()
        _require(item["file_sha256"] == actual, f"payloads[{relative}].file_sha256",
                 f"清单哈希与实际复制件不一致：清单 {item['file_sha256']!r}，实际 {actual!r}")
        _require(item["source_initial_file_sha256"] == actual,
                 f"payloads[{relative}].source_initial_file_sha256",
                 f"初始绑定哈希与实际复制件不一致：声明 "
                 f"{item['source_initial_file_sha256']!r}，实际 {actual!r}")
        _require(status_bound == actual,
                 f"payloads[{relative}].source_initial_file_sha256",
                 f"历史 status 绑定与实际复制件不一致：status {status_bound!r}，实际 {actual!r}")


def _require_identity_relations(manifest: dict, buffers: dict) -> dict:
    """包内必要来源/身份关系（数据只来自本包同缓冲对象与实际字节，不调用冻结核心复算）。"""
    fingerprints = manifest["canonical_fingerprints"]
    boundaries = manifest["boundaries"]
    status = _parse_buffer(buffers[STATUS_NAME], STATUS_NAME)
    host_manifest = _parse_buffer(buffers[f"{EVIDENCE_DIR}/workflow/host_manifest.json"],
                                  f"{EVIDENCE_DIR}/workflow/host_manifest.json")
    checkpoint7 = _parse_buffer(buffers[f"{EVIDENCE_DIR}/workflow/checkpoints/0007.json"],
                                f"{EVIDENCE_DIR}/workflow/checkpoints/0007.json")
    checkpoint8 = _parse_buffer(buffers[f"{EVIDENCE_DIR}/workflow/checkpoints/0008.json"],
                                f"{EVIDENCE_DIR}/workflow/checkpoints/0008.json")
    packet = _parse_buffer(buffers[f"{EVIDENCE_DIR}/workflow/fact_packet/fact_packet.json"],
                           f"{EVIDENCE_DIR}/workflow/fact_packet/fact_packet.json")
    initial = _parse_buffer(
        buffers[f"{EVIDENCE_DIR}/workflow/initial_judgment/initial_judgment.json"],
        f"{EVIDENCE_DIR}/workflow/initial_judgment/initial_judgment.json")
    submission = _parse_buffer(
        buffers[f"{EVIDENCE_DIR}/workflow/initial_judgment/submission.json"],
        f"{EVIDENCE_DIR}/workflow/initial_judgment/submission.json")
    batch_manifest = _parse_buffer(buffers[f"{EVIDENCE_DIR}/batch_manifest.json"],
                                   f"{EVIDENCE_DIR}/batch_manifest.json")

    def _bytes(relative: str) -> bytes:
        return buffers[f"{EVIDENCE_DIR}/{relative}"]

    def _sha(relative: str) -> str:
        return hashlib.sha256(_bytes(relative)).hexdigest()

    # --- 1) 文件字节哈希字段 ↔ 实际 payload 字节 ↔ 历史 status 声明
    status_fact = status.get("fact_packet") or {}
    status_initial = status.get("initial_judgment") or {}
    status_gate2 = status.get("gate2_tail") or {}
    status_checkpoints = status.get("checkpoints") or []
    _require(fingerprints["packet_file_sha256"] == _sha("workflow/fact_packet/fact_packet.json"),
             "canonical_fingerprints.packet_file_sha256",
             "必须等于实际事实包文件字节哈希")
    _require(fingerprints["record_file_sha256"]
             == _sha("workflow/initial_judgment/initial_judgment.json"),
             "canonical_fingerprints.record_file_sha256",
             "必须等于实际记录文件字节哈希")
    _require(fingerprints["checkpoint_0008_file_sha256"] == _sha("workflow/checkpoints/0008.json"),
             "canonical_fingerprints.checkpoint_0008_file_sha256",
             "必须等于实际 0008 文件字节哈希")
    _require(fingerprints["packet_file_sha256"] == status_fact.get("packet_file_sha256"),
             "canonical_fingerprints.packet_file_sha256",
             f"必须等于历史 status 声明 {status_fact.get('packet_file_sha256')!r}")
    _require(fingerprints["record_file_sha256"] == status_initial.get("initial_judgment_file_sha256"),
             "canonical_fingerprints.record_file_sha256",
             f"必须等于历史 status 声明 "
             f"{status_initial.get('initial_judgment_file_sha256')!r}")
    _require(_is_hash(fingerprints["database_sha256"])
             and fingerprints["database_sha256"] == status_gate2.get("database_sha256"),
             "canonical_fingerprints.database_sha256",
             f"必须等于历史 status 的数据库字节声明 {status_gate2.get('database_sha256')!r}")
    _require(len(status_checkpoints) == 8
             and status_checkpoints[7].get("file_sha256")
             == fingerprints["checkpoint_0008_file_sha256"],
             "canonical_fingerprints.checkpoint_0008_file_sha256",
             "必须等于历史 status 的 0008 文件哈希声明")

    # --- 2) 对象规范指纹 ↔ 实际对象 ↔ status/0008 声明
    _require(canonical_sha256(packet) == fingerprints["packet_sha256"],
             "canonical_fingerprints.packet_sha256",
             "必须等于实际事实包对象的规范指纹")
    _require(fingerprints["packet_sha256"] == status_fact.get("packet_sha256"),
             "canonical_fingerprints.packet_sha256",
             f"必须等于历史 status 声明 {status_fact.get('packet_sha256')!r}")
    _require(isinstance(initial, dict) and set(initial.keys()) == {"record", "record_sha256"},
             f"{EVIDENCE_DIR}/workflow/initial_judgment/initial_judgment.json",
             "记录外层必须恰为 record/record_sha256")
    record = initial["record"]
    _require(canonical_sha256(record) == fingerprints["record_sha256"],
             "canonical_fingerprints.record_sha256",
             "必须等于实际 record 对象的规范指纹")
    _require(initial["record_sha256"] == fingerprints["record_sha256"],
             f"{EVIDENCE_DIR}/workflow/initial_judgment/initial_judgment.json",
             "记录声明的规范指纹必须与清单/实际对象一致")
    _require(fingerprints["record_sha256"] == status_initial.get("record_sha256"),
             "canonical_fingerprints.record_sha256",
             f"必须等于历史 status 声明 {status_initial.get('record_sha256')!r}")

    # --- 3) 批次身份在包内各文件间闭合
    operation = checkpoint8.get("operation") or {}
    state = (checkpoint8.get("workflow") or {}).get("state") or {}
    record_source = record.get("source") or {}
    simulated = record.get("simulated_initial_judgment") or {}
    # TASK-018-R2 B3：先逐项确认批次ID为非空字符串（可定位的协议阻断），
    # 再构造集合做同批次判定；不全局捕获 TypeError，不把非字符串强制 str。
    batch_id_fields = (
        ("manifest.batch_id", manifest["batch_id"]),
        ("manifest.source_batch.batch_id", (manifest["source_batch"] or {}).get("batch_id")),
        ("host_status.batch_id", status.get("batch_id")),
        ("host_manifest.batch_id", host_manifest.get("batch_id")),
        ("batch_manifest.batch_id", batch_manifest.get("batch_id")),
        ("checkpoint_0008.batch_id", checkpoint8.get("batch_id")),
        ("checkpoint_0008.workflow.state.batch_id", state.get("batch_id")),
        ("record.source.batch_id", record_source.get("batch_id")),
        ("record.simulated_initial_judgment.batch_id", simulated.get("batch_id")),
        ("submission.batch_id", submission.get("batch_id")),
    )
    for field_label, value in batch_id_fields:
        _require(isinstance(value, str) and value != "", field_label,
                 "批次ID必须是非空字符串（保留原字符串精确比较，不 strip／不转换／"
                 f"不按哈希格式排除），实际 {type(value).__name__}: {value!r}")
    batch_ids = dict(batch_id_fields)
    distinct = {value for value in batch_ids.values()}
    _require(len(distinct) == 1 and None not in distinct, "batch_id",
             f"包内批次身份必须同属一批次，实际 {json.dumps(batch_ids, ensure_ascii=False)}")
    _require((manifest["source_batch"] or {}).get("checkpoints_total") == 8,
             "manifest.source_batch.checkpoints_total", "必须是严格整数 8")
    # packet/record 指纹在各声明处一致
    _require(record_source.get("fact_packet_sha256") == fingerprints["packet_sha256"],
             "record.source.fact_packet_sha256", "必须等于实际事实包规范指纹")
    _require(simulated.get("fact_packet_sha256") == fingerprints["packet_sha256"],
             "record.simulated_initial_judgment.fact_packet_sha256",
             "必须等于实际事实包规范指纹")
    _require(submission.get("fact_packet_sha256") == fingerprints["packet_sha256"],
             "submission.fact_packet_sha256", "必须等于实际事实包规范指纹")
    _require(operation.get("packet_sha256") == fingerprints["packet_sha256"],
             "checkpoint_0008.operation.packet_sha256", "必须等于实际事实包规范指纹")
    _require(operation.get("packet_file_sha256") == fingerprints["packet_file_sha256"],
             "checkpoint_0008.operation.packet_file_sha256",
             "必须等于实际事实包文件字节哈希")
    _require(operation.get("record_sha256") == fingerprints["record_sha256"],
             "checkpoint_0008.operation.record_sha256", "必须等于实际记录规范指纹")
    _require(operation.get("initial_judgment_file_sha256") == fingerprints["record_file_sha256"],
             "checkpoint_0008.operation.initial_judgment_file_sha256",
             "必须等于实际记录文件字节哈希")
    _require(operation.get("submission_file_sha256")
             == _sha("workflow/initial_judgment/submission.json"),
             "checkpoint_0008.operation.submission_file_sha256",
             "必须等于实际提交快照文件字节哈希")
    _require(operation.get("artifacts_file_sha256")
             == _sha("workflow/initial_judgment/artifacts.json"),
             "checkpoint_0008.operation.artifacts_file_sha256",
             "必须等于实际初判 artifacts 文件字节哈希")
    _require(operation.get("started_file_sha256")
             == _sha("workflow/initial_judgment/started.json"),
             "checkpoint_0008.operation.started_file_sha256",
             "必须等于实际初判 started 文件字节哈希")
    _require(operation.get("database_sha256") == fingerprints["database_sha256"],
             "checkpoint_0008.operation.database_sha256",
             "必须等于清单与 status 的数据库字节声明")

    # --- 4) 0008 前驱与 workflow 与包内实际材料一致
    _require(operation.get("kind") == OPERATION_RECORD_INITIAL_JUDGMENT,
             "checkpoint_0008.operation.kind", f"必须是 {OPERATION_RECORD_INITIAL_JUDGMENT}")
    _require(_is_strict_int(checkpoint8.get("revision")) and checkpoint8["revision"] == 8,
             "checkpoint_0008.revision", "必须是严格整数 8")
    _require(_is_strict_int((manifest["checkpoint_0008"] or {}).get("revision"))
             and manifest["checkpoint_0008"]["revision"] == 8,
             "manifest.checkpoint_0008.revision", "必须是严格整数 8")
    checkpoint7_sha = _sha("workflow/checkpoints/0007.json")
    actual_previous = checkpoint8.get("previous_file_sha256")
    _require(actual_previous == checkpoint7_sha, "checkpoint_0008.previous_file_sha256",
             f"必须等于包内 0007 实际文件哈希 {checkpoint7_sha!r}，实际 {actual_previous!r}")
    _require((manifest["checkpoint_0008"] or {}).get("previous_file_sha256") == checkpoint7_sha,
             "manifest.checkpoint_0008.previous_file_sha256",
             f"必须等于包内 0007 实际文件哈希 {checkpoint7_sha!r}，实际 "
             f"{(manifest['checkpoint_0008'] or {}).get('previous_file_sha256')!r}")
    if operation.get("previous_checkpoint_file_sha256") is not None:
        _require(operation["previous_checkpoint_file_sha256"] == checkpoint7_sha,
                 "checkpoint_0008.operation.previous_checkpoint_file_sha256",
                 "必须等于包内 0007 实际文件哈希")
    _require(canonical_json(checkpoint8.get("workflow"))
             == canonical_json(checkpoint7.get("workflow")),
             "checkpoint_0008.workflow", "0008 的 workflow 必须与 0007 严格规范相等")

    # --- 5) 宿主/工具/版本/绑定身份 ↔ 包内已有声明
    _require(manifest["host_version"] == status.get("host_version")
             == host_manifest.get("host_version"),
             "host_version", "manifest、host_status 与 host_manifest 的宿主版本必须一致")
    host_codes = manifest["host_code_sha256"]
    bindings = (host_manifest.get("bindings") or {}).get("host_code_sha256") or {}
    _require(host_codes["host_code"] == bindings.get("host_code"),
             "host_code_sha256.host_code", "必须等于包内 host_manifest 实测宿主代码哈希")
    _require(host_codes["initial_judgment_core"] == bindings.get("initial_judgment_core"),
             "host_code_sha256.initial_judgment_core",
             "必须等于包内 host_manifest 实测初判核心哈希")
    _require(host_codes["run_bindings_sha256"] == status.get("bindings_sha256"),
             "host_code_sha256.run_bindings_sha256", "必须等于历史 status 的绑定摘要")
    _require(host_codes["run_bindings_sha256"] == state.get("run_bindings_sha256"),
             "host_code_sha256.run_bindings_sha256", "必须等于 0008 的绑定摘要")
    _require(operation.get("bindings_sha256") == host_codes["run_bindings_sha256"],
             "checkpoint_0008.operation.bindings_sha256", "必须等于包内绑定摘要")
    _require(bindings.get("initial_judgment_core") == operation.get("core_sha256"),
             "checkpoint_0008.operation.core_sha256",
             "必须等于包内 host_manifest 的初判核心哈希")

    # --- 6) 开发/模拟/契约/批准/next/AI 边界在各处一致
    for label, value in (("host_status.mode", status.get("mode")),
                         ("host_manifest.mode", host_manifest.get("mode")),
                         ("checkpoint_0008.workflow.state.mode", state.get("mode")),
                         ("record.mode", record.get("mode"))):
        _require(value == "DEVELOPMENT_TEST_ONLY", label,
                 f"必须是 DEVELOPMENT_TEST_ONLY，实际 {value!r}")
    for label, value in (("record.contract_status", record.get("contract_status")),
                         ("checkpoint_0008.workflow.state.contract_status",
                          state.get("contract_status"))):
        _require(value == boundaries.get("contract_status"), label,
                 f"必须与 manifest 契约状态一致，实际 {value!r}")
    _require(boundaries.get("contract_status") == "DRAFT_NOT_IN_FORCE",
             "manifest.boundaries.contract_status", "必须是 DRAFT_NOT_IN_FORCE（正式契约未建立）")
    _require(_is_strict_int(status.get("real_approvals")) and status["real_approvals"] == 0,
             "host_status.real_approvals", "必须是严格整数 0")
    _require(boundaries.get("real_approvals") == 0, "manifest.boundaries.real_approvals",
             "必须是严格整数 0")
    for label, value in (("record.gate1_approval", record.get("gate1_approval")),
                         ("record.gate2_approval", record.get("gate2_approval")),
                         ("checkpoint_0008.workflow.state.gate1_approval",
                          state.get("gate1_approval")),
                         ("checkpoint_0008.workflow.state.gate2_approval",
                          state.get("gate2_approval")),
                         ("record.human_initial_judgment", record.get("human_initial_judgment")),
                         ("record.ai_suggestion", record.get("ai_suggestion")),
                         ("record.final_judgment", record.get("final_judgment"))):
        _require(value is None, label, f"必须是 null，实际 {value!r}")
    for label, value in (("host_status.next_step_allowed", status.get("next_step_allowed")),
                         ("record.next_step_allowed", record.get("next_step_allowed")),
                         ("checkpoint_0008.workflow.state.next_step_allowed",
                          state.get("next_step_allowed"))):
        _require(value is False, label, f"必须是严格 false，实际 {value!r}")
    _require(record.get("ai_suggestion_allowed") is False, "record.ai_suggestion_allowed",
             "必须是严格 false（AI 未开放）")
    _require((status.get("initial_judgment") or {}).get("ai_action_simulation_allowed") is False,
             "host_status.initial_judgment.ai_action_simulation_allowed",
             "AI 动作真实许可必须是严格 false")
    _require(simulated.get("actor_kind") == boundaries.get("actor_kind") == "SIMULATED_HUMAN",
             "actor_kind", "必须是 SIMULATED_HUMAN")
    _require(simulated.get("simulation") == boundaries.get("simulation")
             == "SIMULATED_TEST_ONLY", "simulation", "必须是 SIMULATED_TEST_ONLY")
    _require(status.get("initial_judgment_status") == RECORDED_STATUS,
             "host_status.initial_judgment_status", f"必须是 {RECORDED_STATUS}")
    _require(status.get("fact_packet_status") == FACT_PACKET_STATUS,
             "host_status.fact_packet_status", f"必须是 {FACT_PACKET_STATUS}")
    _require(status.get("status") == "READY", "host_status.status", "必须是 READY")
    return {"status": status, "checkpoint8": checkpoint8, "record": record,
            "packet": packet, "batch_ids": batch_ids}


def verify_dev_review_bundle(bundle_dir) -> dict:
    """只读核验包内固定文件与清单一致（不读取原批次、数据库或宿主）。

    TASK-018-R1：所有必要 JSON 对象都与**通过清单哈希检查的同一字节缓冲**绑定；
    返回成功前在全部必要身份/对象消费之后做一次有限最终字节确认。
    """
    bundle = Path(bundle_dir)
    bundle = (Path.cwd() / bundle).resolve() if not bundle.is_absolute() else bundle.resolve()
    _require(bundle.is_dir(), "bundle_dir", f"必须是已存在的包目录，实际 {bundle}")
    _require(not (bundle / FAILURE_NAME).exists(), FAILURE_NAME,
             "包内存在失败诊断：本包不是成功导出")
    # 1) 每个固定文件各读一次缓冲；长度/哈希/对象都从该缓冲取得
    buffers = {}
    for relative in _fixed_relatives():
        buffers[relative] = _read_bundle_buffer(bundle, relative)
    manifest = _parse_buffer(buffers[MANIFEST_NAME], MANIFEST_NAME)
    _verify_manifest_shape(manifest)
    expected_relatives = set(_fixed_relatives())
    actual_relatives = {path.relative_to(bundle).as_posix()
                        for path in bundle.rglob("*") if path.is_file()}
    _require(actual_relatives == expected_relatives, "bundle.files",
             f"固定文件集合不符：多出 {sorted(actual_relatives - expected_relatives)}，"
             f"缺少 {sorted(expected_relatives - actual_relatives)}")
    for item in manifest["payloads"]:
        data = buffers[item["relative"]]
        _require(_is_strict_int(item["bytes"]) and len(data) == item["bytes"], item["relative"],
                 f"字节数不符：清单 {item['bytes']}，实际 {len(data)}")
        digest = hashlib.sha256(data).hexdigest()
        _require(digest == item["file_sha256"], item["relative"],
                 f"文件哈希不符：清单 {item['file_sha256']!r}，实际 {digest!r}")
    _require(not buffers[MANIFEST_NAME].startswith(b"\xef\xbb\xbf"), MANIFEST_NAME,
             "不得带 UTF-8 BOM")
    readme_data = buffers[README_NAME]
    _require(not readme_data.startswith(b"\xef\xbb\xbf"), README_NAME, "不得带 UTF-8 BOM")
    _require(b"\r\n" not in readme_data, README_NAME, "必须使用 LF 换行")
    # 2) 来源/身份关系闭合（同缓冲对象 + 实际字节）
    _require_payload_relations(manifest, buffers)
    parsed = _require_identity_relations(manifest, buffers)
    checked = len(manifest["payloads"])
    # 3) 返回成功前的最终纯字节确认：实读全部 25 个固定文件，与初次缓冲预期比较
    for relative in sorted(expected_relatives):
        try:
            fresh = (bundle / relative).read_bytes()
        except OSError as exc:
            raise DevReviewBundleError(f"最终字节确认读取失败：{relative}（{exc}）",
                                       stage="verify") from exc
        _require(fresh == buffers[relative], relative,
                 "最终字节确认发现包内文件在本次必要消费之后发生变化："
                 f"期望 {len(buffers[relative])} 字节/"
                 f"{hashlib.sha256(buffers[relative]).hexdigest()!r}，实际 {len(fresh)} 字节/"
                 f"{hashlib.sha256(fresh).hexdigest()!r}")
    _require(not (bundle / FAILURE_NAME).exists(), FAILURE_NAME,
             "最终字节确认发现包内出现失败诊断")
    final_relatives = {path.relative_to(bundle).as_posix()
                       for path in bundle.rglob("*") if path.is_file()}
    _require(final_relatives == expected_relatives, "bundle.files",
             f"最终字节确认发现包内文件集合变化：多出 "
             f"{sorted(final_relatives - expected_relatives)}，缺少 "
             f"{sorted(expected_relatives - final_relatives)}")
    fingerprints = manifest["canonical_fingerprints"]
    return {
        "bundle_status": VERIFIED_STATUS,
        "scope": VERIFY_SCOPE,
        "bundle_dir": str(bundle),
        "manifest_version": manifest["manifest_version"],
        "batch_id": manifest["batch_id"],
        "batch_ids_consistent": parsed["batch_ids"],
        "payloads_checked": checked,
        "copied_sources_checked": COPIES,
        "files_byte_confirmed": len(expected_relatives),
        "packet_sha256": fingerprints["packet_sha256"],
        "record_sha256": fingerprints["record_sha256"],
        "embedded_status_is_historical": True,
        "note": ("离线核验只确认包内文件与清单一致（COPIED_BYTES_ONLY）；"
                 "不读取原批次/数据库/宿主，不证明原始业务真实性，也不重新批准批次；"
                 "包内 status 是导出时的历史快照，不能当作当前宿主状态或真实批准；"
                 "包内来源指纹与批次身份已相互闭合，但不构成身份认证。"),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


def _emit_failure(exc: Exception, command: str) -> int:
    blocked = isinstance(exc, DevReviewBundleBlocked)
    payload = {
        "result": "blocked" if blocked else "error",
        "exception_class": type(exc).__name__,
        "stage": getattr(exc, "stage", "") or command,
        "message": str(exc),
        "reasons": list(getattr(exc, "reasons", []) or [str(exc)]),
        "field": getattr(exc, "field", None),
        "note": ("协议／前提／路径不符，未建立审阅包。" if blocked
                 else "运行或 I/O 失败（保留原因链）。"),
    }
    _emit(payload)
    print(f"DIAGNOSTIC: {type(exc).__name__} @ {payload['stage']}: {exc}", file=sys.stderr)
    return EXIT_BLOCKED if blocked else EXIT_ERROR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TASK-018 开发态只读审阅包导出与离线核验（独立工具；不推进工作流）")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export", help="把已核验的 0008 批次导出为只读审阅包")
    export.add_argument("--batch-dir", required=True)
    export.add_argument("--out-dir", required=True)
    verify = subparsers.add_parser("verify", help="离线核验审阅包内固定文件与清单")
    verify.add_argument("--bundle-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "export":
            _emit(export_dev_review_bundle(args.batch_dir, args.out_dir))
            return EXIT_OK
        _emit(verify_dev_review_bundle(args.bundle_dir))
        return EXIT_OK
    except (DevReviewBundleBlocked, DevReviewBundleError) as exc:
        return _emit_failure(exc, args.command)
    except Exception as exc:  # noqa: BLE001
        mapped = DevReviewBundleError(f"意外程序错误：{type(exc).__name__}: {exc}",
                                      ["阶段=" + args.command,
                                       f"原始异常={type(exc).__name__}: {exc}"], args.command)
        print(traceback.format_exc(), file=sys.stderr)
        return _emit_failure(mapped, args.command)


if __name__ == "__main__":
    sys.exit(main())
