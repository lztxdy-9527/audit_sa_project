# TASK-059 执行回执：一键对账启动器

日期：2026-10-18。交付状态：一键启动器、编排器、配置、测试与指南完成，**交独立验收**；
**既有 changed = 0**；不改看板、不接 AI/终判。

依据：`docs/tasks/TASK-059_DRAFT.md`（`5aa79d0c…`）、决策记录 `DSH-SCOPE-20261017-07` D-IO-2/3。
接受基线：TASK-058-R1 接受快照 `data/reviews/task058r1_dsh_20261018_01/source_hashes_after.json`
（**205561 项 / `0dbdaa6a…`**）。

## 1. 新增身份（实测）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/run_all.py` | 12872 B | `c77dbca978dc74ac…` |
| `tests/test_run_all.py` | 10080 B | `2f18cd6f8e86bbdb…` |
| `docs/RUN_ALL_GUIDE.md` | 4011 B | `cc998289b312a4cf…` |
| `config/run_all.json` | 344 B | `890f9d9cdd09f3b0…` |
| `一键对账.cmd` | 262 B | `6cf58c4d3cdcbf11…` |
| `docs/EXEC_REPORT_059.md` | 本文 | — |

输出根 `outputs/`（本卡运行产物）、证据根 `task059_evidence_01/`、测试根 `task059_run_02/`。

## 2. 使用方式（实测）

双击 `一键对账.cmd` → `.venv\Scripts\python.exe -B scripts\run_all.py --open` →
依次执行七步；成功输出 `outputs/<run_id>/`：

```
index.html · gl/（六页 + gl_reconcile_report.json/.md）· excel/证据链底稿.xlsx
· logs/（每步 stdout/stderr）· run_summary.json
```

- 配置 `config/run_all.json`：批次、task043 输入、账务库、GL 根、输出根、是否打开浏览器、可选审阅记录；
- `--run-id` 可指定（缺省 `run_YYYYmmdd_HHMMSS`）；`--out-root` 可覆盖；`--open/--no-open` 控制浏览器。
- 步骤依赖：索引 v1.2 的 `gl` 节需要核对报告，故实际顺序为 **核对 → 索引**（其余同卡）。

## 3. 实测结果

- 正常：`outputs/task059_run_01` **exit 0、overall=SUCCESS**，七步全 0：
  input_contract / gl_contract / demo / gl_reconcile / trace_index / site / workbook；
  `index.html`、`gl/gl-checks.html`、`excel/证据链底稿.xlsx`、`logs/`、`run_summary.json` 齐全；
  `read_only_ok=true`。
- 失败即停：task043 输入缺文件 → **第 1 步失败、exit 1**、`failed_step=input_contract`、无 `index.html`；
  GL 契约坏 → **第 2 步失败、exit 1**、`failed_step=gl_contract`、无 `index.html`。
- 输出目录已存在 → **exit 2**（拒绝覆盖）。
- 启动器：`.cmd` 含 `run_all.py`、`chcp 65001`、`pause`；配置路径全部可解析。
- 确定性：两个 run-id 的 `index.html`、`gl/gl-checks.html`、`excel/证据链底稿.xlsx` **字节相同**。
- 只读：批次/task043/GL 根/账务库前后哈希一致。

## 4. 测试（实测 6/6 PASS）

`tests/test_run_all.py --out-dir …\task059_run_02`：正常、输出已存在、输入缺文件、GL 契约坏、
启动器/配置、确定性、只读。

## 5. 证据

`task059_evidence_01/command.json` + `success/`（成功 run_summary 与七步日志）+ `failure/`
（bad_input、bad_gl 的 run_summary 与日志）+ 输入哈希快照；测试根 `task059_run_02/`。

## 6. 保护安排与判据

定稿后**一次**全树扫描（`task059_finalization/protection_scan.py`），基线 = TASK-058-R1 接受快照
（205561 项 / `0dbdaa6a…`）：**既有 changed 必须为 0**；新增仅限本卡文件、`outputs/**`、
`task059_*/**` 与架构端已知增量（逐路径登记）；missing/读取错误/未登记新增 0；
139/27/326/19/TASK-030 41 B 锁继续冻结。

## 7. 边界

一键运行只做机器核对与出页，**不构成审计结论或终判**；不做函证/监盘/期后付款；不联网、不安装依赖。
真实批准 `null`、真实初判未保存、0008、`next/AI=false`。
