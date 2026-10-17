# TASK-058：数据投放指引与目录骨架（原始数据放哪里）

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-057 ACCEPTED**。依据 `docs/decisions/DECISION_20261018_DSH_INTAKE_AND_ONECLICK.md`（`DSH-SCOPE-20261017-07`）：让审计人员知道每类原始数据放哪个文件夹、格式要求、是否已提供。

## 1. 允许写入

- 新增 `scripts/build_intake_guide.py`（仅标准库）、`tests/test_intake_guide.py`、`docs/INTAKE_GUIDE.md`、`docs/EXEC_REPORT_058.md`；
- 新增模板与状态页：`data/inbox/**`、证据根 `data/runtime_initial_judgment_recording_tests/task058_*/`。
- **不允许修改任何既有文件**（changed=0）。

## 2. 目录骨架（`data/inbox/`）

```
data/inbox/
├─ README.md                     总说明：四类数据、命名、示例、校验命令
├─ 01_业务台账/
│  ├─ _放入说明.md               suppliers/payables/payments/allocations（xlsx，四张表，字段清单）
│  └─ 放入此处.txt               占位
├─ 02_凭证附件/
│  ├─ _放入说明.md               vouchers/*.json + index.json（发票/合同/回单/审批/入库）
│  └─ 放入此处.txt
├─ 03_银行流水/
│  ├─ _放入说明.md               bank_transactions.json（日期、方向、金额分、参考号）
│  └─ 放入此处.txt
└─ 04_总账账套/
   ├─ _放入说明.md               GL v1 十个文件（科目表/凭证/余额表/总账/明细账/报表/对账单/日记账/附件索引/清单）
   └─ 放入此处.txt
```

每个 `_放入说明.md` 必须写明：**放什么文件、文件命名、必填字段、金额单位（整数分）、日期格式、示例、校验命令**（`gl_input_contract_v1.py` / `input_contract_v1.py`）以及"不规整整包退回、不修数据"。

## 3. 状态页 `intake_status.html`

- 生成：`python scripts/build_intake_guide.py --intake-root data/inbox --out-dir <task058_*>`
- 表格列：数据类别、应放目录、应放文件/模式、状态（**已提供 / 缺失 / 需校验**）、大小/更新时间（只读扫描）、校验方式、说明链接；
- 状态规则：文件存在且可读 → 已提供；不存在 → 缺失；存在但格式/哈希不符 → 需校验（只读判断，不修改）；
- 页面纯审计语言、无外链/无脚本（或仅静态），顶部边界横幅；另出 `intake_manifest.json`（逐目录/文件、状态、大小、SHA）。
- 只读：不复制、不移动、不改 `data/inbox/` 内任何文件。

## 4. 测试与证据

1. 骨架创建：四个目录、`_放入说明.md`、README 存在，内容含字段/命名/校验命令；
2. 状态页：空 inbox → 全部"缺失"；放入一个合法样例（测试夹具）→ 对应项"已提供"；放入坏文件 → "需校验"；
3. 语言/链接/转义/确定性（两次生成字节相同）；只读（前后 inbox 快照一致）；
4. 证据 `task058_evidence_01/`：命令、状态页、manifest、空/合法/坏三类输出。

## 5. 保护与停止

一次全树扫描，基线 = TASK-057 接受基线：既有 changed 必须为 0；新增仅限 §1 与架构端已知增量（决策记录与本卡逐确切路径登记）；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不做一键启动器（TASK-059）、不改看板。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；指引页只说明放置与校验，不构成审计结论。
