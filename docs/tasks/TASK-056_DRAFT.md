# TASK-056：借贷记账法六类核对引擎（凭证平衡/试算/账证/账账/账表/账实）

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-055 ACCEPTED**（`gl_v1` 已接受）。依据 `DSH-SCOPE-20261017-06` D-GL-2：按《会计基础工作规范》第63条与试算平衡、应付账款实质性程序口径，只做**核对与差异报告**，不做审计结论。

## 1. 允许写入

- 新增 `scripts/reconcile_gl_v1.py`（仅标准库）；
- 新增 `tests/test_gl_reconcile.py`、`docs/GL_RECONCILE_GUIDE.md`、`docs/EXEC_REPORT_056.md`；
- 新增证据根 `data/runtime_initial_judgment_recording_tests/task056_*/`。
- **不允许修改任何既有文件**（changed=0），包括 GL 输入包与 task043 输入。

## 2. 命令

```powershell
.venv\Scripts\python.exe -B scripts\reconcile_gl_v1.py `
  --gl-root data\evidence_inputs\gl_v1 `
  --out-dir data\runtime_initial_judgment_recording_tests\task056_gl_01
```

退出码：`0` 全部 `MATCHED`（允许备注）；`1` 存在 `DIFFERENCES_FOUND` 或 `INCOMPLETE`；`2` 参数/路径错误。

## 3. 六类核对（每类输出 status + findings）

1. **凭证平衡 `journal_balance`**：逐张凭证借贷相等；期间借贷合计相等。差异字段：`entry_id / debit_total / credit_total`。
2. **试算平衡 `trial_balance`**：期初/本期/期末借贷两两相等；逐科目 `期初 + 借方发生 − 贷方发生 = 期末`（按方向，借方余额与贷方余额分别汇总）。差异字段：`account_code / expected / actual`。
3. **账证 `ledger_to_voucher`**：总账、明细账按科目发生额 = 凭证按科目汇总（借贷分列）；日期/凭证号可追溯。差异字段：`account_code / ledger_debit|credit / voucher_debit|credit`。
4. **账账 `general_to_subsidiary`**：总账余额 = 明细账合计（按科目，含方向）；明细账内部逐笔余额滚动正确（上笔余额 ± 发生 = 本笔余额）。差异字段：`account_code / general / subsidiary`。
5. **账表 `ledger_to_report`**：科目余额表 = 报表项目（含**应付借方余额 4,000 重分类为预付账款 4,000**）；资产合计 = 负债 + 权益。差异字段：`report_item / ledger_value / report_value`。
6. **账实 `bank_reconcile`**：银行日记账余额 = 对账单期末；`期初 + 收入 − 支出 = 期末`；逐笔一致；未达账项分别列示（账有实无 / 实有账无）。差异字段：`date / amount / journal_balance / statement_balance`。

另附 **附件核对 `attachments`**（凭证附件引用存在、类型匹配：应付确认需发票/合同/入库；付款需审批/回单；退款需回单）——作为第 7 项附加检查，不改变六类主口径。

## 4. 输出

1. `gl_reconcile_report.json`：
   - `checks[]`：`{id, title, status, findings[], summary{...}}`；
   - `summary`：六类状态、`overall`（`ALL_MATCHED` / `DIFFERENCES_FOUND`）、`notes[]`（如"应付账款借方余额 4,000 已重分类为预付账款，需人类判断是否为多付/预付"）；
   - `period`、`batch_id`、`checks_performed`、`unperformed[]`（函证、监盘、期后付款、截止测试等未做，写明）。
2. `gl_reconcile_report.md`：审计人员可读版（六类分节、差异表、未执行项、边界横幅）。
3. `reconcile_source.json`：读取的每个 GL 文件路径/长度/SHA、命令、版本；无时间戳。
4. 只读：不写 GL 包与 task043 输入；只写 `--out-dir`。

## 5. 测试与证据

- **正常**：`gl_v1` → `exit 0`、`overall=ALL_MATCHED`、六类全 MATCHED；报告数字与手算一致（借贷合计 16000=16000；期末库存 5000 借、应付 4000 借、银行 11000 借、实收 20000 贷；试算 20000=20000；报表 20000=20000；银行 11000=11000）；`notes` 含应付借方余额提示（不是差异）。
- **负例（每类至少一个，全部 `exit 1` 且字段精确）**：
  1. 改一张凭证贷方 1 分 → `journal_balance`；
  2. 改科目余额表某科目期末 1 分 → `trial_balance`；
  3. 改明细账发生额 1 分 → `ledger_to_voucher`；
  4. 改总账余额 1 分 → `general_to_subsidiary`；
  5. 改报表项目 1 分 → `ledger_to_report`；
  6. 改对账单期末 1 分 → `bank_reconcile`；
  7. 删附件引用 → `attachments`。
- **确定性**：同输入两次运行，JSON/MD 字节相同。
- **只读**：运行前后 GL 包、task043 输入、批次字节不变。
- **规模**：复制 GL 包构造 **200 张凭证**的合成夹具（仅本卡测试用）→ 六类核对完成，登记耗时/文件大小；不做性能承诺。
- 证据根 `task056_evidence_01/`：正常报告、7 个负例输出、命令与退出码、输入快照。

## 6. 保护与停止

一次全树扫描，基线 = TASK-055 接受基线：**既有 changed 必须为 0**；新增仅限 §1 与架构端已知增量（决策记录与本卡逐确切路径登记）；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不接 UI/Excel（TASK-057）、不做函证/监盘/期后付款、不改看板。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；核对结果只展示证据与差异，不构成审计结论。
