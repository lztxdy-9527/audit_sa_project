# TASK-048 执行回执：证据链索引（线索 → 账务行 → 凭证 → 原始表行）

日期：2026-10-17。交付状态：索引生成器、测试、指南与证据定稿，**交独立验收**；
本回执不宣布验收通过，不生成页面/工作簿、不改看板、不推进账表/账账或 AI/终判。
真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-048_DRAFT.md`（`d69d1951…`）、决策记录
`docs/decisions/DECISION_20261017_DSH_DRILLDOWN_UI_V2.md`（`15e0b8d4…`，`DSH-SCOPE-20261017-04`）。
前置：TASK-047 ACCEPTED。起点接受快照 `data/reviews/task047_dsh_20261017_01/source_hashes_after.json`
（**176686 项 / `276bb699…`**）。本卡**纯新增**：未修改任何既有文件。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task048_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 索引生成器（唯一新增代码，仅标准库） | `scripts/build_trace_index.py` | 31680 B | `5c8992a1a82eccd2…` |
| 新测试 | `tests/test_trace_index.py` | 14256 B | `d01030efe71eac65…` |
| 指南 | `docs/EVIDENCE_CHAIN_INDEX_GUIDE.md` | 5709 B | `9c6be02cf3595ab4…` |
| 本回执 | `docs/EXEC_REPORT_048.md` | 见 delivery.json | 见 delivery.json |

## 2. 命令与退出码（实测）

```
.venv\Scripts\python.exe -B scripts\build_trace_index.py `
  --run-root data\runtime_initial_judgment_recording_tests\task046_demo_01 `
  --out-dir  data\runtime_initial_judgment_recording_tests\task048_index_01
```

- 正常：**exit 0**；`trace_index.json` 20466 B / `bf44f968…`；`trace_index_source.json` 2530 B；
  1 条 R02 线索（yellow）、无 red、引用闭合；耗时约 0.2 秒（本机，非性能结论）。
- P02 缺证（`task046_demo_v1_neg`）→ `task048_index_v1_neg`：**exit 0**；`trace_index.json` 20428 B /
  `1d1741e5…`；**3 条事项**（1 yellow R02 + **2 red**：未取得审批单、未取得银行回单，均指向付款 P02），
  影像占位存在。
- 测试：`tests/test_trace_index.py --out-dir …\task048_run_01` → **exit 0、6/6 cases PASS、
  `read_only_ok=true`**。

## 3. 输出结构（实测）

- `cases[]`：正常 1 条（R02 超额 4000.00 元，yellow；账务引用 AP01/P01/P02/R01；凭证引用 8 张——
  发票/合同/入库/审批/回单；原始行引用 payables!E2、allocations!D2/D3、payments!F2/F3、refunds!F4）；
  v1_neg 3 条（R02 + P02 缺审批单 + P02 缺回单）。
- `ledger[]`：事项涉及行切片——AP01、P01、P02、R01 与分摊 A01/A02/AR01；每字段带
  `source{sheet, excel_row, column_letter, raw_value, standard_value}`（取自 `normalized.json`）。
- `vouchers[]`：8 张凭证切片（发票/合同/入库/审批 2 张/回单 3 张），字段 + 输入文件相对路径 + 记录序号 +
  影像占位。
- `source_rows[]`：7 行原表副本（payables 1 行、payments 3 行、allocations 3 行）。
- `meta`：运行根、批次/实体/期间、`cases_total`、`cases_per_page=50`、`pages`、分类/严重度计数、行数、
  生成器版本、边界说明；无时间戳/随机数。
- `trace_index_source.json`：8 个输入文件（路径/长度/SHA-256）、canonical 输入根 manifest、命令、版本。

## 4. 规模与确定性（实测）

- 规模：复制运行根构造 **200 条事项**夹具（空 findings + 200 条 missing）→ **exit 0、`cases_total=200`、
  `pages=4`（per_page=50）、无悬空引用**；`trace_index.json` 218887 B、耗时约 0.14 秒（本机，非性能结论）。
- 确定性：同一 `--run-root` 两次生成（`task048_det_a`/`task048_det_b`），`trace_index.json` 与
  `trace_index_source.json` **字节相同**（实测 + 测试双证）。

## 5. 负例与只读（实测）

- 悬空账务引用（复制运行根注入 `ledger_id=AP99` 差异）→ **exit 1**、`kind=content`、字段含
  `CASE-0002.ledger_refs[0].ledger_id=AP99`。
- 缺 `demo_summary.json` → **exit 2**、字段 `demo_summary`。
- 只读：生成/测试前后 `task046_demo_01`、`task046_demo_v1_neg` 运行根、对应业务根、`data/evidence_inputs/`、
  账务 `normalized.json` 字节快照完全一致（`read_only_ok=true`）。

## 6. 保护安排与判据

定稿后**一次**全树扫描（`task048_finalization/protection_scan.py`），基线 = TASK-047 接受快照
（176686 项 / `276bb699…`）：既有 changed 必须为 0；新增仅限本卡四件与 `task048_*` 证据/夹具根
（含 `data/runtime/task048_*`、`data/human_initial_judgment_records/task048_*` 夹具）、架构端已知增量
（本卡与 DRILLDOWN_UI_V2 决策记录逐确切路径登记）；missing/读取错误/未登记新增/身份漂移 0；
139/27/326/19/TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 7. 未执行与边界

未执行：页面/工作簿生成（TASK-049/050）、账表/账账、影像/OCR、外部查验、函证/盘点、AI、终判、
真实数据/强认证/物理 junction/非合作篡改/并发双进程竞态（`null` + 原因）。索引只是既有合成证据的导航数据，
不证明凭证/流水真实，不构成审计结论。
