# TASK-058-R1：投放状态页异常兜底（结构错误/解析错误 → 需校验，不崩溃）

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-057 ACCEPTED**（204412 / `97f8940f…`）；TASK-058 为 **NOT_ACCEPTED**（`docs/reviews/REVIEW_TASK_058.md`）。本卡只修复生成器健壮性并补测试。

## 1. 允许修改/新增

**允许修改（changed 恰三件）**：`scripts/build_intake_guide.py`、`tests/test_intake_guide.py`、`docs/INTAKE_GUIDE.md`。
**允许新增**：`docs/EXEC_REPORT_058_R1.md`、证据根 `data/runtime_initial_judgment_recording_tests/task058r1_*/`。
**禁止**：改 inbox 骨架/README/说明文件、任何既有输入、生成器/核对器、既有卡/评审/证据、看板。

## 2. 必须修复（B1）

每个类别校验（business / vouchers / bank / gl）必须**异常安全**：

1. JSON 语法错误、编码错误、IO 错误；
2. **顶层形状错误**（应为对象却为数组/字符串/数字/null；应为数组却为对象）；
3. 必需键缺失（如 `bank` 缺 `transactions`、`vouchers` 缺 `vouchers` 键）；
4. 字段类型错误（金额非整数、方向非枚举、日期非 ISO）。

以上任一情况 → 该类别状态 **需校验**，`detail` 写清原因（如 `bank_transactions.json 顶层不是对象`），**exit 0 且状态页/清单照常生成**；不得出现 traceback、不得中断其他类别。

## 3. 测试（必须覆盖）

在现有空/合法/坏三类之外，新增：
1. `bank_transactions.json` 为数组 → 银行流水 **需校验**，页面正常；
2. `index.json` 为对象但无 `vouchers` 键 → 凭证附件 **需校验**；
3. GL 某文件为数组 / 非法 JSON → 总账账套 **需校验**；
4. xlsx 为文本/损坏 → 业务台账 **需校验**；
5. 上述情况下其他类别仍正确判定（互不影响）；
6. 空/合法/坏回归、确定性、只读、语言/链接不变。

## 4. 证据

`task058r1_evidence_01/`：四类结构异常的状态页/manifest、退出码（均 0）、detail 文本；正常/合法/坏回归输出；inbox 前后哈希快照。

## 5. 保护与停止

一次全树扫描，基线 = TASK-057 接受基线（204412 / `97f8940f…`）：**既有 changed = 0**（本卡只改 TASK-058 未接受的三个新文件）；其余全新增并逐路径登记；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不做一键启动器（TASK-059）、不改看板。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；指引页只说明放置与校验，不构成审计结论。
