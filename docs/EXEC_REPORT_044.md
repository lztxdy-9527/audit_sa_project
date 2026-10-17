# TASK-044 执行回执：账证相符 L1（凭证字段级核对）与抽样核对底稿

日期：2026-10-17。交付状态：匹配器、测试、指南与证据定稿，**交 Architect 独立验收**；
本回执不宣布验收通过，不做账实（TASK-045）、不改演示脚本、不改看板。
真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-044_DRAFT.md`、`docs/decisions/DECISION_20261017_DSH_FOUR_MATCH_SCOPE.md`
（`DSH-SCOPE-20261017-02`）。前置：TASK-043 已接受。本卡**纯新增**：未修改任何既有文件。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task044_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 匹配器（唯一新增代码） | `scripts/voucher_match_v1.py` | 38985 B | `8daa8cd858fcf435797f8cb2ee19c4692c17d2285a2f4c696de9a9c3bb4cae84` |
| 新测试 | `tests/test_voucher_match_v1.py` | 19470 B | `e680bf9cf3604b5c4f2e326202d06d9bc945ed54a5c7567dec00d1f3316e113b` |
| 指南 | `docs/ACCOUNT_VOUCHER_MATCH_GUIDE.md` | 6858 B | `944a9917bb6249bab7e272aec979cf399bd35526c308a76916bf4dfa63b11c44` |
| 本回执 | `docs/EXEC_REPORT_044.md` | 见 delivery.json | 见 delivery.json |

账务侧只读复用 `data/runtime/task042_dsh_01/normal.load/normalized.json`
（18169 B / `f440f0cf…09e2`），并核对其绑定：`started.json`（`25737912…`）的 `batch_id=batch_normal`、
`source_batch_relative`、`run_binding.input.file_sha256` 与本批次工作簿 `8f6f2a98…` 一致；
`artifacts.json`（`51925a5b…`）的 `normalized_file_sha256`/`batch_id` 一致；`mode=DEVELOPMENT_TEST_ONLY`。

## 2. 命令与退出码（实测）

```
.venv\Scripts\python.exe -B tests\test_voucher_match_v1.py --out-dir data\runtime_initial_judgment_recording_tests\task044_run_02
```

- 测试退出码 **0**；`test_report.json`：**14/14 cases PASS**（1 正常 + 1 规范输入对照 + 12 负例），
  `read_only_ok=true`（原输入根与账务 normalized/started/artifacts 前后字节不变）。
- 匹配器调用（子进程，实测）：
  `scripts/voucher_match_v1.py --input <一致夹具> --ledger-normalized data/runtime/task042_dsh_01/normal.load/normalized.json --out …/normal_consistent/task044_normal`
  → 退出码 **0**，`conclusion=ALL_MATCHED`，`r02_sampling` 含 AP01/P01/P02/R01 且“核对结论”列为空。
- 负例调用：退出码均 **1**，报告照常输出，差异分类/字段精确。

## 3. 正常（一致夹具，全部 MATCHED）

- 逐项 **8/8 `MATCHED`**：AP01 × {INVOICE, CONTRACT, GOODS_RECEIPT}、P01 × {APPROVAL, BANK_RECEIPT}、
  P02 × {APPROVAL, BANK_RECEIPT}、R01 × {BANK_RECEIPT}；差异 0、账有证无 0、证有账无 0。
- R02 抽样底稿：程序选取 AP01/P01/P02/R01（非审计抽样方法学），逐条列出账务记录、凭证记录、
  核对状态与差异；**`human_conclusion` 恒为 null**，列名“核对结论”留空，注明“人类核对结论需另行授权与登记”。
- 结论写明：`L1_FIELD_LEVEL_NO_EXTERNAL_VERIFICATION`——“L1 字段级核对；未查看影像、
  未做发票/回单外部查验、不证明凭证真实”。

## 4. 规范输入对照（重要：P02 账有证无）

直接对 TASK-043 接受输入运行 → **2 条 `MISSING_VOUCHER`**（`PAYMENT P02` 缺 `APPROVAL` 与 `BANK_RECEIPT`），
退出码 1。原因：TASK-043 接受输入为契约校验而设计，凭证覆盖 AP01、P01、R01；**P02（R02 超付的重复付款）
在 TASK-043 输入中没有审批单与银行回单**。这是数据事实与“账有证无”线索，不是匹配器缺陷，也不是审计结论。

因此卡 §4 的“正常：全部 MATCHED（合成数据设计为一致）”以**一致夹具**演示：在证据根内复制接受输入并补齐
P02 审批单（V-APR-0002）、银行回单（V-BR-0003，引用既有流水 BT-2026-0002、方向 OUT）与两条索引，
更新 manifest 哈希；原输入根只读、不变。该夹具仅为本卡测试证据，不改变 TASK-043 接受输入。
若架构端认为应把 P02 凭证正式纳入 TASK-043 输入（而非测试夹具），请以 R1/补充卡明确，执行端再做。

## 5. 负例（12 类，逐类精确）

| # | 类别 | 注入 | 实测分类/字段 |
| --- | --- | --- | --- |
| 1 | 金额差 1 分 | 发票 total 499999 | `AMOUNT_MISMATCH` / `total_cents_sum` |
| 2 | 税额合计不符 | 发票 tax 100 而 total 不变 | `TAX_TOTAL_MISMATCH` / `tax_cents` |
| 3 | 日期越界 | 发票 issue_date 2026-10-01 | `DATE_MISMATCH` / `issue_date` |
| 4 | 错日 | 回单 txn_date 2026-09-11（付款日 09-10） | `DATE_MISMATCH` / `txn_date` |
| 5 | 对方名称不一致 | 回单 counterparty_name 乙收款对象 | `COUNTERPARTY_MISMATCH` / `counterparty_name` |
| 6 | 审批未通过 | 审批 status REJECTED | `STATUS_MISMATCH` / `status` |
| 7 | 方向错 | 付款回单 direction REFUND | `DIRECTION_MISMATCH` / `direction` |
| 8 | 多发票合计不符 | 追加发票 100000 并加索引 | `SUM_MISMATCH` / `total_cents_sum` |
| 9 | 账有证无 | 移除 AP_INVOICE 索引 | `MISSING_VOUCHER` / AP |
| 10 | 证有账无 | 追加未索引发票 V-INV-0009 | `EXTRA_VOUCHER` / V-INV-0009 |
| 11 | 退款原分摊错 | 复制账务把 AR01 original_allocation_id 改 A99 | `REFUND_LINK_MISMATCH` / `original_allocation_id` |
| 12 | 重复审批 | P01 追加第二张审批并加索引 | `EXTRA_VOUCHER` / V-APR-0009 |

每例保留：输入副本（`…/<case>/input/`）、命令、stdout/stderr、退出码、完整报告与差异；
第 11 类使用账务 normalized 的**副本**注入（原 normalized/started/artifacts 只读、字节不变）。

## 6. 只读与证据

- 只读：匹配器不写账务/凭证/银行/批次；测试前后对规范输入根、`normalized.json`、`started.json`、
  `artifacts.json` 做字节快照比较，`read_only_ok=true`。
- 证据根 `data/runtime_initial_judgment_recording_tests/task044_run_02/`：`test_report.json`、`test_stdout.txt`、
  `test_stderr.txt`、`command.json`、`normal_consistent/{input,task044_normal/…}`、
  `canonical_control/task044_canonical/…`、每负例 `<case>/{input,task044_out/…}` 与 stdout/stderr。
- 迭代保留：`task044_smoke_01`（首次冒烟）、`task044_run_01`（首轮通过）、`task044_run_02`（定稿证据）。

## 7. 保护安排与判据

定稿后**一次**全树扫描（`task044_finalization/protection_scan.py`），基线 = TASK-043 接受快照：
相对该基线**既有 changed 必须为 0**；新增仅限本卡四件与 `task044_*` 证据根、架构端已知增量
（决策记录与 TASK-043/044/045 卡逐确切路径登记）；新 missing/读取错误/未登记新增/身份漂移 0；
139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 8. 未执行与边界

未执行：影像/OCR、发票/回单外部查验、函证/盘点、无索引模糊匹配、人类核对结论（不采集、不虚构）、
账实相符（TASK-045，未获放行）、账账/账表、演示集成、AI、终判、真实数据/强认证/物理 junction/非合作篡改/
并发双进程竞态（`null` + 原因）。本卡不证明凭证真实、不构成审计证据或结论。
