# TASK-058 执行回执：数据投放指引与目录骨架

日期：2026-10-18。交付状态：`data/inbox/` 骨架、状态页生成器、测试与指引完成，**交独立验收**；
**既有 changed = 0**；不做一键启动器（TASK-059）、不改看板、不接 AI/终判。

依据：`docs/tasks/TASK-058_DRAFT.md`（`0992f440…`）、决策记录
`docs/decisions/DECISION_20261018_DSH_INTAKE_AND_ONECLICK.md`（`DSH-SCOPE-20261017-07`）。
接受基线：TASK-057 接受快照 `data/reviews/task057_dsh_20261018_01/source_hashes_after.json`
（**204412 项 / `97f8940f…`**）。

## 1. 新增身份（实测）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_intake_guide.py` | 见交付清单 | 见交付清单 |
| `tests/test_intake_guide.py` | 见交付清单 | 见交付清单 |
| `docs/INTAKE_GUIDE.md` | 见交付清单 | 见交付清单 |
| `docs/EXEC_REPORT_058.md` | 本文 | — |

`data/inbox/` 新增：`README.md`、四个类别目录、四份 `_放入说明.md`、四个 `放入此处.txt`；
证据根 `task058_evidence_01/`；种子状态页 `task058_status_01/`。

## 2. 目录骨架（实测）

`data/inbox/README.md`（四类数据/命名/示例/校验命令）+ `01_业务台账`、`02_凭证附件`、
`03_银行流水`、`04_总账账套`；每个目录含 `_放入说明.md`（放什么、命名、必填字段、
金额整数分、日期格式、示例、校验命令、"整包退回、不修数据"）与 `放入此处.txt`。

## 3. 状态页（实测）

`scripts/build_intake_guide.py --intake-root data/inbox --out-dir <task058_*>`：

- 输出 `intake_status.html`（纯静态、无脚本、纯审计语言、顶部边界横幅）与
  `intake_manifest.json`（逐目录/文件、状态、大小、SHA、更新时间；无时间戳注入）。
- 表格列：数据类别、应放目录、应放文件或模式、状态（**已提供/缺失/需校验**）、
  大小与更新时间、校验方式、说明链接。
- 规则：文件存在可读 → 已提供（GL 需 `gl_input_contract_v1.py` 通过）；不存在 → 缺失；
  格式/结构/哈希不符 → 需校验；只读扫描，不修改 inbox 内任何字节。
- 种子状态页：对空骨架 `data/inbox` 运行 → **四类均缺失**（`task058_status_01/`）。

## 4. 测试（实测 6/6 PASS）

`tests/test_intake_guide.py --out-dir …\task058_run_02`：

- 骨架：README、四个目录、四份 `_放入说明.md`、占位文件齐全；说明含“整数分”与校验命令。
- 空 inbox → 全部缺失；合法样例（xlsx + 凭证索引/文件 + 银行流水 + GL v1 十文件）→ 全部已提供；
  坏文件（非 xlsx、坏索引、缺字段流水、GL 篡改）→ 对应项需校验。
- 语言红线零命中、链接可解析、两次生成字节相同、inbox 前后快照一致（只读）。

## 5. 证据

`task058_evidence_01/command.json`：空/合法/坏三类状态页命令与退出码、状态汇总、状态页与
manifest 身份、inbox 只读快照；证据根内含三类 `intake_status.html`/`intake_manifest.json`；
测试根 `task058_run_02/`。

## 6. 保护安排与判据

定稿后**一次**全树扫描（`task058_finalization/protection_scan.py`），基线 = TASK-057 接受快照
（204412 项 / `97f8940f…`）：**既有 changed 必须为 0**；新增仅限本卡文件、`data/inbox/**`、
`task058_*/**` 与架构端已知增量（逐确切路径登记）；missing/读取错误/未登记新增 0；
139/27/326/19/TASK-030 41 B 锁继续冻结。

## 7. 边界

指引页只说明放置与校验，不构成审计结论；不复制/移动/修改 inbox 文件；不做数据清洗；
一键启动器（TASK-059）不在本卡。真实批准 `null`、真实初判未保存、0008、`next/AI=false`。
