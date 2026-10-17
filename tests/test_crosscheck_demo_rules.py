#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TASK-007 独立复算与 SQL 事实一致性复核：开发验证入口。

用法：

    & 'D:\\harness work\\audit_sa_project\\.venv\\Scripts\\python.exe' -B `
      'D:\\harness work\\audit_sa_project\\tests\\test_crosscheck_demo_rules.py' `
      --out-dir 'D:\\harness work\\audit_sa_project\\data\\sqlite_tests\\task007_01'

每个输入：新副本 → 真实 checker CLI（独立 stdout／stderr）→ 冻结标准化 API → 冻结装载 API →
冻结 SQL 筛查 API → 独立复核 API；分别保存 normalized／load_report／demo.sqlite／
screening_report／crosscheck_report。全部初次结果保存后才读取答案册做额外已知案例验证。

本入口把自身 stdout／stderr 完整捕获到容器，并把每项检查的结构化详情直接写入 JSON 文件。
退出码：0 全部符合预期；1 断言或保护失败；2 参数或环境问题。
"""

from __future__ import annotations

import argparse
import builtins
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQLITE_TESTS_ROOT = (PROJECT_ROOT / "data" / "sqlite_tests").resolve()
CHECKER = PROJECT_ROOT / "scripts" / "check_demo_data.py"
NORMALIZER = PROJECT_ROOT / "scripts" / "normalize_demo_data.py"
STORE = PROJECT_ROOT / "scripts" / "store_demo_sqlite.py"
SCREEN = PROJECT_ROOT / "scripts" / "screen_demo_sqlite.py"
CROSSCHECK = PROJECT_ROOT / "scripts" / "crosscheck_demo_rules.py"
RULES_SQL_DIR = (PROJECT_ROOT / "sql" / "rules").resolve()

DEMO_DIR = PROJECT_ROOT / "data" / "generated" / "demo_20260930_a"
MAIN_INPUT = DEMO_DIR / "input" / "erp_export.xlsx"
FIXTURE_DIR = DEMO_DIR / "fixtures"
EVALUATION_DIR = (DEMO_DIR / "evaluation").resolve()
GROUND_TRUTH = EVALUATION_DIR / "ground_truth.json"
FIXTURE_EXPECTATIONS = EVALUATION_DIR / "fixture_expectations.json"
GPT_CASES_DIR = (SQLITE_TESTS_ROOT / "task006_r1_gpt_20261011_072212" / "cases").resolve()

SAMPLES = (
    "S1_full_refund_keeps_r03",
    "S2_three_full_payments",
    "S3_payee_diff_with_overpay",
    "S4_non_settled_refunds",
    "S5_key_collision_guard",
    "S6_no_funds",
)
BLOCKED_FIXTURES = ("C11", "C12", "C13", "C14a", "C14b", "C14c", "C14d", "C14e")

PROTECTED_FILES = [
    CHECKER,
    NORMALIZER,
    STORE,
    SCREEN,
    PROJECT_ROOT / "sql" / "demo_schema.sql",
    *[PROJECT_ROOT / "sql" / "rules" / f"r0{index}.sql" for index in (1, 2, 3, 4)],
    PROJECT_ROOT / "docs" / "SPEC_V1.md",
    PROJECT_ROOT / "docs" / "AUDIT_CONTRACT_DRAFT.md",
    PROJECT_ROOT / "docs" / "EXEC_REPORT_006_R1.md",
    PROJECT_ROOT / "docs" / "RULE_SCREEN_GUIDE.md",
    PROJECT_ROOT / "tests" / "test_screen_demo_sqlite.py",
    MAIN_INPUT,
    *sorted(FIXTURE_DIR.glob("*.xlsx")),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    print(f"RUNTIME_ERROR: {message}", file=sys.stderr)
    sys.exit(2)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def hit_key_tuple(hit_key: dict) -> tuple:
    """身份键（与复核核心同规则）：字段名 + 值类型 + repr(值)，不做 str() 归一化。"""
    return tuple(sorted((str(key), type(value).__name__ if value is not None else "null", repr(value))
                        for key, value in hit_key.items()))


class Tee:
    """把本入口的 stdout／stderr 同时写入容器文件。"""

    def __init__(self, stream, path: Path):
        self._stream = stream
        self._file = path.open("w", encoding="utf-8")

    def write(self, data):
        self._stream.write(data)
        self._file.write(data)
        return len(data)

    def flush(self):
        self._stream.flush()
        self._file.flush()

    def close(self):
        try:
            self._file.close()
        finally:
            pass


class Case:
    def __init__(self, name: str, case_dir: Path, input_path: Path):
        self.name = name
        self.case_dir = case_dir
        self.input_path = input_path
        self.checker_exit: int | None = None
        self.normalize_outcome: str | None = None
        self.normalize_message = ""
        self.normalized: dict | None = None
        self.load_report: dict | None = None
        self.screening: dict | None = None
        self.crosscheck: dict | None = None
        self.crosscheck_outcome: str | None = None
        self.crosscheck_message = ""
        self.db_path: Path | None = None


class Suite:
    def __init__(self, container: Path, normalizer, store, screen, crosscheck):
        self.container = container
        self.normalizer = normalizer
        self.store = store
        self.screen = screen
        self.crosscheck = crosscheck
        self.cases_dir = container / "cases"
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        self.cli_calls = 0
        self.screen_calls = 0
        self.crosscheck_calls = 0
        self.cases: list[Case] = []
        self.failures: list[dict] = []
        self.command_log: list[dict] = []
        self.crosscheck_details: list[dict] = []
        self.mismatch_checks: list[dict] = []
        self.precondition_checks: list[dict] = []
        self.isolation_checks: list[dict] = []
        self.outputs_saved = 0
        self.answer_book_first_read_at_outputs: int | None = None

    # ---------- 运行链路 ----------
    def checker_call(self, name: str, workbook: Path, case_dir: Path) -> tuple[int, dict | None]:
        self.cli_calls += 1
        report_path = case_dir / "checker_report.json"
        stdout_log = case_dir / f"{self.cli_calls:03d}_{name}.checker.stdout.txt"
        stderr_log = case_dir / f"{self.cli_calls:03d}_{name}.checker.stderr.txt"
        command = [sys.executable, "-B", str(CHECKER), "--workbook", str(workbook), "--report", str(report_path)]
        with stdout_log.open("w", encoding="utf-8") as out, stderr_log.open("w", encoding="utf-8") as err:
            exit_code = subprocess.run(command, stdout=out, stderr=err).returncode
        payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
        self.command_log.append({
            "call_index": self.cli_calls, "case": name, "command": command, "exit_code": exit_code,
            "report": str(report_path), "stdout_log": str(stdout_log), "stderr_log": str(stderr_log),
        })
        return exit_code, payload

    def prepare(self, name: str, source: Path) -> Case:
        case_dir = self.cases_dir / name
        case_dir.mkdir(parents=True, exist_ok=True)
        case = Case(name, case_dir, case_dir / "input.xlsx")
        shutil.copyfile(source, case.input_path)
        exit_code, report = self.checker_call(name, case.input_path, case_dir)
        case.checker_exit = exit_code
        case.checker_report = report
        self.cases.append(case)
        return case

    def run_pipeline(self, case: Case) -> Case:
        if case.checker_report is None or case.checker_report.get("result") != "pass":
            case.normalize_outcome = "upstream_blocked"
            case.normalize_message = "checker 未通过，未进入标准化／规则／复核"
            return case
        try:
            normalized = self.normalizer.normalize_workbook(case.input_path, case.checker_report)
            case.normalize_outcome = "normalized"
        except self.normalizer.NormalizationBlocked as exc:
            case.normalize_outcome = "upstream_blocked"
            case.normalize_message = str(exc)
            return case
        except self.normalizer.NormalizationError as exc:
            case.normalize_outcome = "normalization_error"
            case.normalize_message = str(exc)
            return case
        case.normalized = normalized
        (case.case_dir / "normalized.json").write_text(
            json.dumps(normalized, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
        )
        try:
            load_report = self.store.load_normalized_to_sqlite(normalized, case.case_dir / "demo.sqlite")
        except (self.store.SqliteLoadBlocked, self.store.SqliteLoadError) as exc:
            case.normalize_outcome = "load_failed"
            case.normalize_message = str(exc)
            return case
        case.load_report = load_report
        case.db_path = case.case_dir / "demo.sqlite"
        (case.case_dir / "load_report.json").write_text(
            json.dumps(load_report, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
        )
        self.screen_calls += 1
        try:
            screening = self.screen.screen_sqlite(case.db_path, load_report)
        except (self.screen.RuleScreenBlocked, self.screen.RuleScreenError) as exc:
            case.normalize_outcome = "screen_failed"
            case.normalize_message = str(exc)
            return case
        case.screening = screening
        (case.case_dir / "screening_report.json").write_text(
            json.dumps(screening, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        self.outputs_saved += 1
        self.run_crosscheck(case, save=True)
        return case

    def run_crosscheck(self, case: Case, *, save: bool, normalized=None, screening=None) -> Case:
        self.crosscheck_calls += 1
        payload_normalized = normalized if normalized is not None else case.normalized
        payload_screening = screening if screening is not None else case.screening
        try:
            result = self.crosscheck.verify_rule_facts(payload_normalized, payload_screening)
            case.crosscheck = result
            case.crosscheck_outcome = "matched" if result["matched"] else "mismatch"
            if save:
                (case.case_dir / "crosscheck_report.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
                )
        except self.crosscheck.CrossCheckBlocked as exc:
            case.crosscheck_outcome = "blocked"
            case.crosscheck_message = str(exc)
        except self.crosscheck.CrossCheckError as exc:
            case.crosscheck_outcome = "error"
            case.crosscheck_message = str(exc)
        return case

    def judge(self, case: Case, *, outcome: str, kind: str, checks: dict) -> Case:
        problems: list[str] = []
        if case.crosscheck_outcome != outcome:
            problems.append(f"复核结果期望 {outcome}，实际 {case.crosscheck_outcome}（{case.crosscheck_message}）")
        for label, predicate in checks.items():
            try:
                ok = bool(predicate(case))
            except Exception as exc:  # noqa: BLE001
                ok = False
                problems.append(f"{label} 断言时异常：{exc!r}")
            if not ok:
                problems.append(f"断言失败：{label}")
        detail = {
            "case": case.name, "kind": kind, "checker_exit": case.checker_exit,
            "normalize_outcome": case.normalize_outcome, "crosscheck_outcome": case.crosscheck_outcome,
            "matched": (case.crosscheck or {}).get("matched"),
            "difference_count": len((case.crosscheck or {}).get("differences", [])),
            "differences": (case.crosscheck or {}).get("differences", []),
            "recomputed_counts": (case.crosscheck or {}).get("rule_recomputed_counts"),
            "message": case.crosscheck_message,
            "problems": problems,
        }
        for index, existing in enumerate(self.crosscheck_details):
            if existing["case"] == case.name and existing["kind"] == kind:
                self.crosscheck_details[index] = detail
                break
        else:
            self.crosscheck_details.append(detail)
        if problems:
            self.failures.append({"case": case.name, "kind": kind, "result": "FAIL", "problems": problems})
        print(f"[{'PASS' if not problems else 'FAIL'}] {case.name} crosscheck={case.crosscheck_outcome}"
              + ("" if not problems else "  | " + " ; ".join(problems)))
        return case


def compare_hit_keys(expected_hits: list[dict], case: Case, label: str) -> list[str]:
    """答案册对照（只在全部初次结果保存后使用）。"""
    problems: list[str] = []
    actual = case.crosscheck["recomputed_facts"]["findings"]
    expected_by_key = {hit_key_tuple(item["hit_key"]): item for item in expected_hits}
    actual_by_key = {hit_key_tuple(item["hit_key"]): item for item in actual}
    if len(actual_by_key) != len(actual):
        problems.append(f"{label} 复算结果存在重复键")
    missing = sorted(set(expected_by_key) - set(actual_by_key))
    extra = sorted(set(actual_by_key) - set(expected_by_key))
    if missing:
        problems.append(f"{label} 缺少答案册登记键：{missing}")
    if extra:
        problems.append(f"{label} 多出答案册未登记键：{extra}")
    for key in sorted(set(expected_by_key) & set(actual_by_key)):
        expected = expected_by_key[key]
        observed = actual_by_key[key]
        for amount_key, amount_value in expected.get("expected_amounts_cents", {}).items():
            if amount_key not in observed["amounts_cents"]:
                problems.append(f"{label}:{dict(key)} 缺少金额 {amount_key}")
            elif isinstance(amount_value, dict):
                for sub_key, sub_value in amount_value.items():
                    if observed["amounts_cents"][amount_key].get(sub_key) != sub_value:
                        problems.append(f"{label}:{dict(key)} {amount_key}.{sub_key} 与答案册不一致")
            elif observed["amounts_cents"][amount_key] != amount_value:
                problems.append(f"{label}:{dict(key)} {amount_key} 与答案册不一致")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TASK-007 独立复算与 SQL 事实一致性复核")
    parser.add_argument("--out-dir", required=True, help="data/sqlite_tests 下尚不存在的测试容器")
    args = parser.parse_args(argv)

    container = Path(args.out_dir)
    container = container.resolve() if container.is_absolute() else (Path.cwd() / container).resolve()
    try:
        container.relative_to(SQLITE_TESTS_ROOT)
    except ValueError:
        fail(f"测试容器必须位于 {SQLITE_TESTS_ROOT} 之内：{container}")
    if container == SQLITE_TESTS_ROOT:
        fail("测试容器不能是 data/sqlite_tests 本身")
    if container.exists():
        fail(f"测试容器已存在，拒绝覆盖历史：{container}")
    for required in (CHECKER, NORMALIZER, STORE, SCREEN, CROSSCHECK, MAIN_INPUT, GROUND_TRUTH, GPT_CASES_DIR):
        if not required.exists():
            fail(f"缺少必需输入：{required}")

    hashes_before = {str(path): sha256(path) for path in PROTECTED_FILES}
    container.mkdir(parents=True)
    original_stdout, original_stderr = sys.stdout, sys.stderr
    stdout_tee = Tee(original_stdout, container / "stdout.txt")
    stderr_tee = Tee(original_stderr, container / "stderr.txt")
    sys.stdout, sys.stderr = stdout_tee, stderr_tee

    normalizer = load_module(NORMALIZER, "normalizer_under_test")
    store = load_module(STORE, "store_under_test")
    screen = load_module(SCREEN, "screen_under_test")
    crosscheck = load_module(CROSSCHECK, "crosscheck_under_test")
    suite = Suite(container, normalizer, store, screen, crosscheck)
    print(f"测试容器: {container}")
    print(f"Python {sys.version.split()[0]} / SQLite {sqlite3.sqlite_version} / 复核版本 {crosscheck.CROSSCHECK_VERSION}")
    print()

    # ---------- 1. 29 个工作簿输入 ----------
    inputs = [("MAIN", MAIN_INPUT)] + [(path.stem, path) for path in sorted(FIXTURE_DIR.glob("*.xlsx"))]
    inputs += [(name, GPT_CASES_DIR / name / "input.xlsx") for name in SAMPLES]
    for name, source in inputs:
        suite.run_pipeline(suite.prepare(name, source))

    def case_of(name: str) -> Case:
        return next(item for item in suite.cases if item.name == name)

    main_case = case_of("MAIN")
    suite.judge(
        main_case, outcome="matched", kind="expected_matched",
        checks={
            "状态与开发态边界": lambda c: c.crosscheck["batch_status"] == "DEV_CROSSCHECK_MATCHED"
            and c.crosscheck["matched"] is True and c.crosscheck["mode"] == "DEVELOPMENT_TEST_ONLY"
            and c.crosscheck["next_step_allowed"] is False,
            "复算命中 3/5/2/2": lambda c: c.crosscheck["rule_recomputed_counts"]
            == {"R01": 3, "R02": 5, "R03": 2, "R04": 2, "total": 12},
            "无差异": lambda c: c.crosscheck["differences"] == [],
            "报告含方法与限制": lambda c: bool(c.crosscheck["method"]) and bool(c.crosscheck["limits"]),
        },
    )

    # ---------- 2. 全部初次结果保存后才读取答案册 ----------
    for name in sorted(SAMPLES):
        case = case_of(name)
        suite.judge(
            case, outcome="matched", kind="expected_matched",
            checks={
                "复核一致": lambda c: c.crosscheck["differences"] == [],
                "上游质量通过": lambda c: c.checker_exit == 0,
            },
        )

    suite.answer_book_first_read_at_outputs = suite.outputs_saved
    ground_truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    fixture_expectations = json.loads(FIXTURE_EXPECTATIONS.read_text(encoding="utf-8"))
    fixtures_by_id = {item["case_id"]: item for item in fixture_expectations["fixtures"]}

    for name in sorted(fixtures_by_id):
        case = case_of(name)
        expectation = fixtures_by_id[name]
        if expectation["expected_quality_status"] == "blocked":
            problems = []
            if case.normalize_outcome != "upstream_blocked":
                problems.append(f"上游应阻断，实际 {case.normalize_outcome}")
            if case.crosscheck is not None or case.crosscheck_outcome is not None:
                problems.append("上游阻断时不得调用复核器")
            if case.checker_exit != 1 or not (case.checker_report and case.checker_report.get("issue_counts_by_code")):
                problems.append("未保留真实 checker 问题")
            if not (case.case_dir / "checker_report.json").exists():
                problems.append("缺少 checker 报告")
            if problems:
                suite.failures.append({"case": name, "kind": "expected_upstream_block", "result": "FAIL",
                                       "problems": problems})
            suite.crosscheck_details.append({"case": name, "kind": "expected_upstream_block",
                                             "crosscheck_outcome": None, "problems": problems,
                                             "note": "上游阻断：SQL／复核未执行"})
            print(f"[{'PASS' if not problems else 'FAIL'}] {name} upstream_blocked"
                  + ("" if not problems else "  | " + " ; ".join(problems)))
            continue
        problems = compare_hit_keys(expectation["expected_rule_findings"], case, name)
        problems += [f"{name} 复算与 SQL 报告存在差异" for _ in [0] if case.crosscheck["differences"]]
        suite.judge(
            case, outcome="matched", kind="expected_matched",
            checks={"逐条对照 fixture 期望": lambda c, p=problems: not p},
        )
        if problems:
            suite.failures[-1]["problems"].extend(problems)

    main_problems = compare_hit_keys(ground_truth["hits"], main_case, "MAIN")
    recomputed_overpayment = main_case.crosscheck["recomputed_facts"]["statistics"]["r02_overpayment_total_cents"]
    if recomputed_overpayment != ground_truth["expected_overpayment_total_cents"]:
        main_problems.append(f"MAIN R02 超额合计 {recomputed_overpayment} != 答案册 "
                             f"{ground_truth['expected_overpayment_total_cents']}")
    suite.judge(
        main_case, outcome="matched", kind="expected_matched",
        checks={"逐条对照答案册（键／金额）": lambda c: not main_problems},
    )
    if main_problems:
        suite.failures[-1]["problems"].extend(main_problems)

    # ---------- 3. 故意改错 SQL 报告 ----------
    def mutated_reports(case_name: str, mutate, label: str, expected_code: str,
                        extra_assert=None, normalized_mutate=None) -> dict:
        base_case = case_of(case_name)
        payload = copy.deepcopy(base_case.screening)
        mutate(payload)
        payload_normalized = copy.deepcopy(base_case.normalized)
        if normalized_mutate is not None:
            normalized_mutate(payload_normalized)
        (container / "mutations").mkdir(exist_ok=True)
        (container / "mutations" / f"{label}.json").write_text(
            json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
        )
        result = suite.crosscheck.verify_rule_facts(payload_normalized, payload)
        suite.crosscheck_calls += 1
        codes = sorted({item["code"] for item in result["differences"]})
        extra_ok = True
        extra_problems: list[str] = []
        if extra_assert is not None:
            try:
                extra_assert(result)
            except AssertionError as exc:
                extra_ok = False
                extra_problems.append(str(exc))
            except Exception as exc:  # noqa: BLE001
                extra_ok = False
                extra_problems.append(f"{type(exc).__name__}: {exc}")
        ok = (result["matched"] is False and result["batch_status"] == "DEV_CROSSCHECK_MISMATCH"
              and expected_code in codes and extra_ok)
        (container / "mutations" / f"{label}.report.json").write_text(
            json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
        )
        record = {
            "case": label, "target": case_name, "expected_code": expected_code, "actual_codes": codes,
            "matched": result["matched"], "status": result["batch_status"],
            "difference_count": len(result["differences"]),
            "unmatched_dimensions": result["comparison"]["unmatched_dimensions"],
            "dimensions": result["comparison"]["dimensions"],
            "differences": result["differences"],
            "extra_problems": extra_problems,
            "differences_truncated": False,
            "ok": ok,
        }
        suite.mismatch_checks.append(record)
        print(f"[{'PASS' if ok else 'FAIL'}] {label} 期望 {expected_code} 实际 {codes}"
              + ("" if extra_ok else f"  附加断言：{extra_problems}"))
        if not ok:
            suite.failures.append({"case": label, "kind": "expected_mismatch", "result": "FAIL",
                                   "problems": [f"matched={result['matched']} codes={codes}",
                                                *extra_problems]})
        return result

    def r01_index(payload):
        return next(i for i, item in enumerate(payload["findings"]) if item["rule_id"] == "R01")

    def r02_index(payload):
        return next(i for i, item in enumerate(payload["findings"]) if item["rule_id"] == "R02")

    def r03_index(payload):
        return next(i for i, item in enumerate(payload["findings"]) if item["rule_id"] == "R03")

    def r04_index(payload):
        return next(i for i, item in enumerate(payload["findings"]) if item["rule_id"] == "R04")

    mutated_reports("MAIN", lambda p: p["findings"].pop(r03_index(p)), "M1_missing_hit", "MISSING_HIT")
    mutated_reports(
        "MAIN",
        lambda p: p["findings"].append({**copy.deepcopy(p["findings"][r02_index(p)]),
                                        "hit_key": {"rule_id": "R02", "ap_id": "AP_NOT_EXIST"}}),
        "M2_extra_hit", "EXTRA_HIT",
    )
    mutated_reports("MAIN", lambda p: p["findings"].append(copy.deepcopy(p["findings"][r01_index(p)])),
                    "M3_duplicate_hit", "DUPLICATE_HIT")
    mutated_reports(
        "MAIN",
        lambda p: p["findings"][r02_index(p)]["amounts_cents"].__setitem__(
            "overpayment", p["findings"][r02_index(p)]["amounts_cents"]["overpayment"] + 1),
        "M4_amount_mismatch", "AMOUNT_MISMATCH",
    )
    mutated_reports(
        "MAIN",
        lambda p: p["statistics"].__setitem__(
            "r02_overpayment_total_cents", p["statistics"]["r02_overpayment_total_cents"] + 1),
        "M5_statistic_mismatch", "STATISTIC_MISMATCH",
    )
    mutated_reports(
        "C09b",
        lambda p: p["findings"][0]["evidence"]["entities"].__delitem__(
            next(i for i, item in enumerate(p["findings"][0]["evidence"]["entities"])
                 if item["table_name"] == "payments" and item["record_id"] == "R01")),
        "M6_source_entity_missing", "SOURCE_ENTITY_MISSING",
    )
    mutated_reports(
        "C09b",
        lambda p: p["findings"][0]["evidence"]["entities"][0]["cells"].__setitem__(
            next(iter(p["findings"][0]["evidence"]["entities"][0]["cells"])),
            {**p["findings"][0]["evidence"]["entities"][0]["cells"][
                next(iter(p["findings"][0]["evidence"]["entities"][0]["cells"]))], "raw_value": "被改动的原值"}),
        "M7_source_value_mismatch", "SOURCE_VALUE_MISMATCH",
    )
    mutated_reports(
        "C09b",
        lambda p: p["findings"][0]["evidence"]["related_refunds"][0].__setitem__("counted_in_net", False),
        "M8_refund_fact_mismatch", "REFUND_FACT_MISMATCH",
    )
    mutated_reports(
        "MAIN",
        lambda p: p["findings"][r04_index(p)]["related_ids"].__setitem__(
            "payee_supplier_id", p["findings"][r04_index(p)]["related_ids"]["payable_supplier_id"]),
        "M9_related_ids_mismatch", "RELATED_IDS_MISMATCH",
    )
    mutated_reports(
        "MAIN",
        lambda p: p["overall_reconciliation"].__setitem__(
            "missing_payable_link_net", p["overall_reconciliation"]["missing_payable_link_net"] + 1),
        "M10_reconciliation_mismatch", "RECONCILIATION_MISMATCH",
    )

    def bump_row(payload):
        finding = payload["findings"][r01_index(payload)]
        sheet = "payments"
        record_id = sorted(finding["source_rows"][sheet])[0]
        finding["source_rows"][sheet][record_id] = finding["source_rows"][sheet][record_id] + 1000

    mutated_reports("MAIN", bump_row, "M11_source_row_mismatch", "SOURCE_ROW_MISMATCH")

    # ---------- 3b. R1 新增：严格类型、退款多重性、规则身份、状态与诊断 ----------
    def dimension_assert(**expectations):
        def check(result):
            dimensions = result["comparison"]["dimensions"]
            for name, expected in expectations.items():
                actual = dimensions[name]["matched"]
                assert actual is expected, f"维度 {name} matched 期望 {expected} 实际 {actual}"

        return check

    def dict_dimension_assert(dimension: str):
        def check(result):
            hits = [item for item in result["differences"] if item["field_path"].startswith(
                "amounts_cents" if dimension == "amounts_cents" else dimension)]
            assert hits, f"维度 {dimension} 未记录差异"
            assert all(item["expected_type"] is not None or not item["expected_present"]
                       for item in hits), "差异缺少 expected_type 元数据"

        return check

    mutated_reports(
        "MAIN",
        lambda p: p["findings"][r02_index(p)]["amounts_cents"].__setitem__(
            "overpayment", float(p["findings"][r02_index(p)]["amounts_cents"]["overpayment"])),
        "M12_amount_float_overpayment", "AMOUNT_MISMATCH",
        extra_assert=dimension_assert(amounts_cents=False, source_entities=True, source_rows=True),
    )
    mutated_reports(
        "MAIN",
        lambda p: p["findings"][r01_index(p)]["amounts_cents"]["net_per_payment"].__setitem__(
            sorted(p["findings"][r01_index(p)]["amounts_cents"]["net_per_payment"])[0],
            float(sorted(p["findings"][r01_index(p)]["amounts_cents"]["net_per_payment"].values())[0]),
        ),
        "M13_net_per_payment_float", "AMOUNT_MISMATCH",
        extra_assert=dimension_assert(amounts_cents=False),
    )
    mutated_reports(
        "S6_no_funds",
        lambda p: p["statistics"]["involved_payments"].__setitem__("settled_amount_cents", False),
        "M14_statistics_bool_zero", "STATISTIC_MISMATCH",
        extra_assert=dimension_assert(statistics=False, amounts_cents=True),
    )
    mutated_reports(
        "C09b",
        lambda p: p["findings"][0]["evidence"]["related_refunds"].append(
            copy.deepcopy(p["findings"][0]["evidence"]["related_refunds"][0])),
        "M15_refund_digest_duplicate", "REFUND_FACT_DUPLICATE",
        extra_assert=dimension_assert(refund_facts=False),
    )
    mutated_reports(
        "C09b",
        lambda p: (
            p["findings"][0]["evidence"]["related_refunds"].append(
                {**copy.deepcopy(p["findings"][0]["evidence"]["related_refunds"][0]),
                 "allocated_amount_cents": 1}),
        ),
        "M16_refund_digest_duplicate_modified", "REFUND_FACT_DUPLICATE",
        extra_assert=dimension_assert(refund_facts=False),
    )
    mutated_reports(
        "MAIN",
        lambda p: p["findings"][r01_index(p)].__setitem__("rule_id", "R04"),
        "M17_rule_identity_conflict", "RULE_ID_MISMATCH",
        extra_assert=dimension_assert(rule_identity=False, amounts_cents=True),
    )

    missing_result = mutated_reports(
        "MAIN",
        lambda p: p["findings"][r02_index(p)]["amounts_cents"].pop("overpayment"),
        "M18_amount_field_missing", "AMOUNT_MISMATCH",
        extra_assert=dimension_assert(amounts_cents=False),
    )
    null_result = mutated_reports(
        "MAIN",
        lambda p: p["findings"][r02_index(p)]["amounts_cents"].__setitem__("overpayment", None),
        "M19_amount_field_null", "AMOUNT_MISMATCH",
        extra_assert=dimension_assert(amounts_cents=False),
    )
    missing_difference = next(item for item in missing_result["differences"]
                              if item["field_path"] == "amounts_cents.overpayment")
    null_difference = next(item for item in null_result["differences"]
                           if item["field_path"] == "amounts_cents.overpayment")
    presence_ok = (missing_difference["actual_present"] is False
                   and missing_difference["actual_type"] is None
                   and null_difference["actual_present"] is True
                   and null_difference["actual_type"] == "null"
                   and missing_difference != null_difference)
    print(f"[{'PASS' if presence_ok else 'FAIL'}] M18_vs_M19 缺失与 null 记录可区分"
          f"（actual_present={missing_difference['actual_present']}/{null_difference['actual_present']}、"
          f"type={missing_difference['actual_type']}/{null_difference['actual_type']}）")
    if not presence_ok:
        suite.failures.append({"case": "M18_vs_M19", "kind": "diagnostics", "result": "FAIL",
                               "problems": ["缺失与 null 的差异记录不可区分"]})

    def two_dimensions(payload):
        finding = payload["findings"][r02_index(payload)]
        finding["amounts_cents"]["overpayment"] = finding["amounts_cents"]["overpayment"] + 1
        rows = finding["source_rows"]["payments"]
        record_id = sorted(rows)[0]
        rows[record_id] = rows[record_id] + 1000

    two_dim_result = mutated_reports(
        "MAIN", two_dimensions, "M20_two_dimensions", "AMOUNT_MISMATCH",
        extra_assert=dimension_assert(amounts_cents=False, source_rows=False),
    )
    both_traced = (
        any(item["code"] == "AMOUNT_MISMATCH" for item in two_dim_result["differences"])
        and any(item["code"] == "SOURCE_ROW_MISMATCH" for item in two_dim_result["differences"])
    )
    print(f"[{'PASS' if both_traced else 'FAIL'}] M20 两处不同维度改动均留痕（金额与行号）")
    if not both_traced:
        suite.failures.append({"case": "M20_two_dimensions", "kind": "diagnostics", "result": "FAIL",
                               "problems": ["未同时记录两处差异"]})

    cells_result = next(item for item in suite.mismatch_checks if item["case"] == "M7_source_value_mismatch")
    cells_difference = next(item for item in cells_result["differences"] if item["code"] == "SOURCE_VALUE_MISMATCH")
    cells_values_ok = (cells_difference["expected"] not in ("完整 cells", None)
                       and cells_difference["actual"] not in ("与标准化记录不一致", None)
                       and ".cells." in cells_difference["field_path"])
    print(f"[{'PASS' if cells_values_ok else 'FAIL'}] M7_cells_diagnostics 差异含可定位路径与实际值"
          f"（{cells_difference['field_path']}）")
    if not cells_values_ok:
        suite.failures.append({"case": "M7_cells_diagnostics", "kind": "diagnostics", "result": "FAIL",
                               "problems": [f"expected={cells_difference['expected']!r} "
                                            f"actual={cells_difference['actual']!r}"]})

    m4_record = next(item for item in suite.mismatch_checks if item["case"] == "M4_amount_mismatch")
    m4_dimensions = m4_record["dimensions"]
    m4_ok = (m4_dimensions["amounts_cents"]["matched"] is False
             and m4_dimensions["amounts_cents"]["difference_count"] >= 1
             and all(m4_dimensions[name]["matched"] is True
                     for name in ("source_entities", "source_rows", "counts", "overall_reconciliation")))
    print(f"[{'PASS' if m4_ok else 'FAIL'}] M4_dimensions 金额维度 matched=False 且其他维度 matched=True")
    if not m4_ok:
        suite.failures.append({"case": "M4_dimensions", "kind": "diagnostics", "result": "FAIL",
                               "problems": [json.dumps(m4_dimensions, ensure_ascii=False)]})

    # ---------- 3c. R2 新增：命中键字符串类型（C04 配对回归） ----------
    def rename_ap_id(normalized: dict, report: dict, new_id: str) -> None:
        old = "AP01"
        for record in normalized["tables"]["payables"]["records"]:
            if record["data"]["ap_id"] == old:
                record["data"]["ap_id"] = new_id
        for record in normalized["tables"]["allocations"]["records"]:
            if record["data"]["ap_id"] == old:
                record["data"]["ap_id"] = new_id
        for finding in report["findings"]:
            if finding["hit_key"].get("ap_id") == old:
                finding["hit_key"]["ap_id"] = new_id
            if finding["related_ids"].get("payable_id") == old:
                finding["related_ids"]["payable_id"] = new_id
            for entity in finding["evidence"]["entities"]:
                if entity["table_name"] == "payables" and entity["record_id"] == old:
                    entity["record_id"] = new_id
            rows = finding["source_rows"].get("payables", {})
            if old in rows:
                rows[new_id] = rows.pop(old)

    def rename_payee(normalized: dict, report: dict, new_id: str) -> None:
        old = "S001"
        for record in normalized["tables"]["suppliers"]["records"]:
            if record["data"]["supplier_id"] == old:
                record["data"]["supplier_id"] = new_id
        for record in normalized["tables"]["payables"]["records"]:
            if record["data"]["supplier_id"] == old:
                record["data"]["supplier_id"] = new_id
        for record in normalized["tables"]["payments"]["records"]:
            if record["data"]["payee_supplier_id"] == old:
                record["data"]["payee_supplier_id"] = new_id
        for finding in report["findings"]:
            for key in ("payee_supplier_id", "payable_supplier_id"):
                if finding["hit_key"].get(key) == old:
                    finding["hit_key"][key] = new_id
                if finding["related_ids"].get(key) == old:
                    finding["related_ids"][key] = new_id
            for entity in finding["evidence"]["entities"]:
                if entity["table_name"] == "suppliers" and entity["record_id"] == old:
                    entity["record_id"] = new_id
            rows = finding["source_rows"].get("suppliers", {})
            if old in rows:
                rows[new_id] = rows.pop(old)

    def sync_fingerprint(report: dict, normalized: dict) -> str:
        fingerprint = crosscheck.canonical_json_sha256(normalized)
        report["load_source"]["normalized_payload_sha256"] = fingerprint
        report["load_source"]["run_metadata"]["normalized_payload_sha256"] = fingerprint
        return fingerprint

    def diff_paths(left, right, prefix: str = "") -> list[str]:
        if isinstance(left, dict) and isinstance(right, dict):
            paths: list[str] = []
            for key in sorted(set(left) | set(right)):
                sub = f"{prefix}.{key}" if prefix else str(key)
                if key not in left or key not in right:
                    paths.append(sub)
                else:
                    paths.extend(diff_paths(left[key], right[key], sub))
            return paths
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                return [f"{prefix}.长度"]
            paths = []
            for index, (left_item, right_item) in enumerate(zip(left, right)):
                paths.extend(diff_paths(left_item, right_item, f"{prefix}[{index}]"))
            return paths
        return [] if left == right else [prefix]

    c04_case = case_of("C04")
    hit_key_checks: list[dict] = []
    for label, renamer, new_id, rule_id, field, mutated_value, expected_type in (
        ("K01_ap_id_int", rename_ap_id, "1", "R02", "ap_id", 1, "int"),
        ("K02_ap_id_bool", rename_ap_id, "True", "R02", "ap_id", True, "bool"),
        ("K03_ap_id_null", rename_ap_id, "None", "R02", "ap_id", None, "null"),
        ("K04_payee_int", rename_payee, "1", "R01", "payee_supplier_id", 1, "int"),
    ):
        control_normalized = copy.deepcopy(c04_case.normalized)
        control_report = copy.deepcopy(c04_case.screening)
        renamer(control_normalized, control_report, new_id)
        fingerprint = sync_fingerprint(control_report, control_normalized)
        suite.crosscheck_calls += 1
        control_result = crosscheck.verify_rule_facts(control_normalized, control_report)
        control_ok = control_result["matched"] is True

        mutated_report = copy.deepcopy(control_report)
        target_index = next(index for index, finding in enumerate(mutated_report["findings"])
                            if finding["rule_id"] == rule_id)
        mutated_report["findings"][target_index]["hit_key"][field] = mutated_value
        changed_paths = diff_paths(control_report, mutated_report)
        expected_path = f"findings[{target_index}].hit_key.{field}"
        only_one_change = changed_paths == [expected_path]

        suite.crosscheck_calls += 1
        result = crosscheck.verify_rule_facts(control_normalized, mutated_report)
        codes = sorted({item["code"] for item in result["differences"]})
        type_difference = next((item for item in result["differences"]
                                if item["code"] == "HIT_KEY_TYPE_MISMATCH"
                                and item["field_path"] == f"hit_key.{field}"), None)
        ok = (
            control_ok
            and only_one_change
            and result["matched"] is False
            and result["batch_status"] == "DEV_CROSSCHECK_MISMATCH"
            and "HIT_KEY_TYPE_MISMATCH" in codes
            and result["comparison"]["dimensions"]["hit_keys"]["matched"] is False
            and type_difference is not None
            and type_difference["expected_type"] == "str"
            and type_difference["actual_type"] == expected_type
        )
        (container / "mutations").mkdir(exist_ok=True)
        (container / "mutations" / f"{label}.control.normalized.json").write_text(
            json.dumps(control_normalized, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        (container / "mutations" / f"{label}.control.report.json").write_text(
            json.dumps(control_report, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        (container / "mutations" / f"{label}.mutated.report.json").write_text(
            json.dumps(mutated_report, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        (container / "mutations" / f"{label}.negative.report.json").write_text(
            json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        hit_key_checks.append({
            "case": label, "rule_id": rule_id, "field": field, "renamed_id": new_id,
            "synced_fingerprint": fingerprint,
            "control_status": control_result["batch_status"], "control_matched": control_ok,
            "mutated_value": mutated_value, "mutated_type": expected_type,
            "changed_paths": changed_paths, "only_one_change": only_one_change,
            "negative_status": result["batch_status"], "negative_codes": codes,
            "hit_keys_dimension": result["comparison"]["dimensions"]["hit_keys"],
            "type_difference": type_difference, "ok": ok,
        })
        print(f"[{'PASS' if ok else 'FAIL'}] {label} 正向={control_result['batch_status']} "
              f"负向={result['batch_status']} 代码={codes} 单点变更={only_one_change}")
        if not ok:
            suite.failures.append({"case": label, "kind": "hit_key_type", "result": "FAIL",
                                   "problems": [f"control={control_result['batch_status']} "
                                                f"negative={result['batch_status']} codes={codes} "
                                                f"changed_paths={changed_paths}"]})

    # ---------- 4. 前提阻断 ----------
    def precondition_check(label: str, normalized_mutate, report_mutate, expect_text: str) -> None:
        payload_normalized = copy.deepcopy(main_case.normalized)
        payload_report = copy.deepcopy(main_case.screening)
        if normalized_mutate:
            normalized_mutate(payload_normalized)
        if report_mutate:
            report_mutate(payload_report)
        suite.crosscheck_calls += 1
        try:
            result = suite.crosscheck.verify_rule_facts(payload_normalized, payload_report)
            outcome, message = result["batch_status"], ""
        except suite.crosscheck.CrossCheckBlocked as exc:
            outcome, message = "blocked", str(exc)
        except suite.crosscheck.CrossCheckError as exc:
            outcome, message = "error", str(exc)
        ok = outcome == "blocked" and expect_text in message
        suite.precondition_checks.append({"case": label, "outcome": outcome, "message": message, "ok": ok})
        print(f"[{'PASS' if ok else 'FAIL'}] {label} outcome={outcome} | {message[:80]}")
        if not ok:
            suite.failures.append({"case": label, "kind": "expected_block", "result": "FAIL",
                                   "problems": [f"outcome={outcome} message={message}"]})

    precondition_check(
        "P1_source_hash_mismatch", None,
        lambda p: (p["load_source"].__setitem__("input_sha256", "0" * 64),
                   p["load_source"]["run_metadata"].__setitem__("input_sha256", "0" * 64)),
        "input_sha256",
    )
    precondition_check(
        "P2_object_fingerprint_mismatch",
        lambda p: p["tables"]["payments"]["records"][0]["data"].__setitem__(
            "amount_cents", p["tables"]["payments"]["records"][0]["data"]["amount_cents"] + 1),
        None, "normalized_payload_sha256",
    )
    precondition_check("P3_mode_not_development", None,
                       lambda p: p.__setitem__("mode", "PRODUCTION"), "mode")
    precondition_check("P4_unsupported_cutoff", None,
                       lambda p: p.__setitem__("cutoff_date", "2026-09-29"), "cutoff_date")
    precondition_check("P5_quality_not_pass", lambda p: p["quality_report"].__setitem__("result", "issues_found"),
                       None, "quality_report")

    # P6：质量结果仍为 pass，但问题计数非空（同步两处指纹以隔离质量前提检查）
    p6_normalized = copy.deepcopy(main_case.normalized)
    p6_normalized["quality_report"]["issue_counts_by_code"] = {"FOREIGN_KEY_MISSING": 1}
    p6_report = copy.deepcopy(main_case.screening)
    synced_fingerprint = crosscheck.canonical_json_sha256(p6_normalized)
    p6_report["load_source"]["normalized_payload_sha256"] = synced_fingerprint
    p6_report["load_source"]["run_metadata"]["normalized_payload_sha256"] = synced_fingerprint
    (container / "mutations").mkdir(exist_ok=True)
    (container / "mutations" / "P6_quality_issue_counts.normalized.json").write_text(
        json.dumps(p6_normalized, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    (container / "mutations" / "P6_quality_issue_counts.report.json").write_text(
        json.dumps(p6_report, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    suite.crosscheck_calls += 1
    try:
        p6_result = crosscheck.verify_rule_facts(p6_normalized, p6_report)
        p6_outcome, p6_message = p6_result["batch_status"], ""
    except crosscheck.CrossCheckBlocked as exc:
        p6_outcome, p6_message = "blocked", str(exc)
    except crosscheck.CrossCheckError as exc:
        p6_outcome, p6_message = "error", str(exc)
    p6_ok = p6_outcome == "blocked" and "issue_counts_by_code" in p6_message
    suite.precondition_checks.append({
        "case": "P6_quality_issue_counts", "outcome": p6_outcome, "message": p6_message,
        "synced_fingerprint": synced_fingerprint, "ok": p6_ok,
    })
    print(f"[{'PASS' if p6_ok else 'FAIL'}] P6_quality_issue_counts outcome={p6_outcome} | {p6_message[:90]}")
    if not p6_ok:
        suite.failures.append({"case": "P6_quality_issue_counts", "kind": "expected_block", "result": "FAIL",
                               "problems": [f"outcome={p6_outcome} message={p6_message}"]})

    # ---------- 5. 确定性与隔离 ----------
    fingerprint_before = crosscheck.canonical_json_sha256(main_case.normalized)
    report_fingerprint_before = crosscheck.canonical_json_sha256(main_case.screening)
    db_hash_before = sha256(main_case.db_path)
    first = crosscheck.verify_rule_facts(main_case.normalized, main_case.screening)
    second = crosscheck.verify_rule_facts(main_case.normalized, main_case.screening)
    suite.crosscheck_calls += 2
    deterministic = crosscheck.canonical_json(first) == crosscheck.canonical_json(second)
    inputs_unchanged = (
        crosscheck.canonical_json_sha256(main_case.normalized) == fingerprint_before
        and crosscheck.canonical_json_sha256(main_case.screening) == report_fingerprint_before
    )
    db_unchanged = sha256(main_case.db_path) == db_hash_before
    print(f"[{'PASS' if deterministic and inputs_unchanged and db_unchanged else 'FAIL'}] "
          f"D1_determinism 复调用一致={deterministic} 入参指纹不变={inputs_unchanged} 数据库字节不变={db_unchanged}")
    if not (deterministic and inputs_unchanged and db_unchanged):
        suite.failures.append({"case": "D1_determinism", "kind": "determinism", "result": "FAIL",
                               "problems": [f"deterministic={deterministic} inputs={inputs_unchanged} db={db_unchanged}"]})

    core_source = CROSSCHECK.read_text(encoding="utf-8")
    forbidden_tokens = ("import sqlite3", "openpyxl", "normalize_demo_data", "store_demo_sqlite",
                        "screen_demo_sqlite", "make_demo_data", "ground_truth", "fixture_expectations",
                        "evaluation", "sql/rules", "subprocess", "independent_review", "run_review")
    static_hits = [token for token in forbidden_tokens if token in core_source]
    print(f"[{'PASS' if not static_hits else 'FAIL'}] I1_static_imports 独立核心未引用数据库/上游核心/答案册"
          + ("" if not static_hits else f"  违规：{static_hits}"))
    suite.isolation_checks.append({"case": "I1_static_imports", "forbidden_hits": static_hits,
                                   "ok": not static_hits})
    if static_hits:
        suite.failures.append({"case": "I1_static_imports", "kind": "isolation", "result": "FAIL",
                               "problems": static_hits})

    real_open = builtins.open
    real_io_open = io.open
    opened: list[str] = []

    def guarded_open(file, *open_args, **open_kwargs):
        try:
            candidate = Path(file).resolve()
        except Exception:  # noqa: BLE001
            candidate = None
        if candidate is not None:
            opened.append(str(candidate))
            for forbidden in (RULES_SQL_DIR, EVALUATION_DIR, GPT_CASES_DIR):
                try:
                    candidate.relative_to(forbidden)
                    raise RuntimeError(f"独立复核核心在运行期尝试读取受限路径：{candidate}")
                except ValueError:
                    pass
        return real_open(file, *open_args, **open_kwargs)

    builtins.open = guarded_open
    io.open = guarded_open
    try:
        probe = CROSSCHECK.read_bytes()
        probe_ok = len(probe) > 0
        guarded_result = crosscheck.verify_rule_facts(main_case.normalized, main_case.screening)
        guard_ok = guarded_result["matched"] is True
        guard_message = ""
    except Exception as exc:  # noqa: BLE001
        probe_ok, guard_ok = False, False
        guard_message = f"{type(exc).__name__}: {exc}"
    finally:
        builtins.open = real_open
        io.open = real_io_open
    suite.crosscheck_calls += 1
    forbidden_reads = [path for path in opened if path.startswith(str(RULES_SQL_DIR))
                       or path.startswith(str(EVALUATION_DIR)) or path.startswith(str(GPT_CASES_DIR))]
    runtime_ok = probe_ok and guard_ok and not forbidden_reads
    print(f"[{'PASS' if runtime_ok else 'FAIL'}] I2_runtime_guard 守卫生效={probe_ok} 核心成功={guard_ok} "
          f"受限读取={len(forbidden_reads)} 受控探测读取={len(opened)} {guard_message[:60]}")
    suite.isolation_checks.append({"case": "I2_runtime_guard", "guard_live": probe_ok, "core_ok": guard_ok,
                                   "forbidden_reads": forbidden_reads, "opened_count": len(opened),
                                   "ok": runtime_ok})
    if not runtime_ok:
        suite.failures.append({"case": "I2_runtime_guard", "kind": "isolation", "result": "FAIL",
                               "problems": [guard_message, f"forbidden={forbidden_reads}"]})

    # ---------- 6. 保护核对 ----------
    hashes_after = {str(path): sha256(path) for path in PROTECTED_FILES}
    changed = [path for path, digest in hashes_before.items() if hashes_after.get(path) != digest]
    if changed:
        suite.failures.append({"case": "INTEGRITY_protected_files", "kind": "integrity", "result": "FAIL",
                               "problems": [f"受保护文件在测试前后哈希不一致：{path}" for path in changed]})
        print("[FAIL] INTEGRITY_protected_files 哈希不一致：")
        for path in changed:
            print(f"        - {path}")
    else:
        print("[PASS] INTEGRITY_protected_files 受保护文件哈希一致")

    counts = {
        "workbook_inputs": len(suite.cases),
        "matched_first": sum(1 for item in suite.cases if item.crosscheck_outcome == "matched"),
        "mismatch_first": sum(1 for item in suite.cases if item.crosscheck_outcome == "mismatch"),
        "upstream_blocked": sum(1 for item in suite.cases if item.normalize_outcome == "upstream_blocked"),
        "crosscheck_blocked": sum(1 for item in suite.cases if item.crosscheck_outcome == "blocked"),
        "unexpected_runtime_errors": sum(1 for item in suite.cases if item.crosscheck_outcome == "error"),
        "checker_cli_calls": suite.cli_calls,
        "screen_calls": suite.screen_calls,
        "crosscheck_calls": suite.crosscheck_calls,
        "expected_mismatch_checks": len(suite.mismatch_checks),
        "hit_key_pairing_checks": len(hit_key_checks),
        "hit_key_pairing_calls": len(hit_key_checks) * 2,
        "precondition_block_checks": len(suite.precondition_checks),
        "determinism_and_isolation_checks": 3,
        "test_failures": len(suite.failures),
    }
    summary = {
        "task": "TASK-007",
        "out_dir": str(container),
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "crosscheck_core": {"path": str(CROSSCHECK), "sha256": sha256(CROSSCHECK),
                            "version": crosscheck.CROSSCHECK_VERSION},
        "counts": counts,
        "cases": [
            {"case": item.name, "checker_exit": item.checker_exit, "normalize_outcome": item.normalize_outcome,
             "crosscheck_outcome": item.crosscheck_outcome,
             "matched": (item.crosscheck or {}).get("matched"),
             "difference_count": len((item.crosscheck or {}).get("differences", [])),
             "recomputed_counts": (item.crosscheck or {}).get("rule_recomputed_counts")}
            for item in suite.cases
        ],
        "failures": suite.failures,
        "protected_files_count": len(PROTECTED_FILES),
        "protected_files_unchanged": not changed,
        "answer_book_read": {
            "first_read_after_outputs_saved": suite.answer_book_first_read_at_outputs,
            "outputs_saved": suite.outputs_saved,
        },
    }
    (container / "crosscheck_results.json").write_text(
        json.dumps(suite.crosscheck_details, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    (container / "mismatch_checks.json").write_text(
        json.dumps(suite.mismatch_checks, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (container / "precondition_checks.json").write_text(
        json.dumps(suite.precondition_checks, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    (container / "isolation_checks.json").write_text(
        json.dumps(suite.isolation_checks, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (container / "hit_key_checks.json").write_text(
        json.dumps(hit_key_checks, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (container / "command_log.json").write_text(
        json.dumps(suite.command_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (container / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"工作簿输入 {counts['workbook_inputs']} 个：初次一致 {counts['matched_first']}、"
          f"上游阻断 {counts['upstream_blocked']}、初次不一致 {counts['mismatch_first']}、"
          f"前提阻断 {counts['crosscheck_blocked']}、意外运行错误 {counts['unexpected_runtime_errors']}")
    print(f"checker CLI {counts['checker_cli_calls']} 次、SQL 核心调用 {counts['screen_calls']} 次、"
          f"复核调用 {counts['crosscheck_calls']} 次、预期不一致检查 {counts['expected_mismatch_checks']} 项、"
          f"前提阻断检查 {counts['precondition_block_checks']} 项")
    print(f"受保护文件前后哈希一致: {summary['protected_files_unchanged']}（{summary['protected_files_count']} 个）")
    print(f"汇总: {container / 'summary.json'}")
    result_code = 0
    if suite.failures:
        print("存在断言失败或保护失败，返回非零退出码（不输出总体成功结论）。")
        result_code = 1
    else:
        print("全部预期成立。")
    sys.stdout, sys.stderr = original_stdout, original_stderr
    stdout_tee.close()
    stderr_tee.close()
    return result_code


if __name__ == "__main__":
    sys.exit(main())
