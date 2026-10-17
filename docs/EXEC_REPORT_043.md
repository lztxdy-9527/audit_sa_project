# TASK-043 执行回执：输入契约 v1 + 合成凭证/银行数据 + 校验与整批拒收 + 输入登记

日期：2026-10-17。交付状态：输入契约、合成输入、校验器、测试与证据定稿，**交 Architect 独立验收**；
本回执不宣布验收通过，不做匹配、不出核对底稿、不改演示脚本、不改看板。
真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-043_DRAFT.md`、决策记录
`docs/decisions/DECISION_20261017_DSH_FOUR_MATCH_SCOPE.md`（`DSH-SCOPE-20261017-02`）。
起点接受快照：`data/reviews/project_smoke_gpt_20261017_183235/source_hashes_after.json`
（173950 项 / `6f8c2787…`）。本卡**纯新增**：未修改任何既有文件。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task043_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 校验器（唯一新增代码） | `scripts/input_contract_v1.py` | 35964 B | `f9462bc0d63755133d7aa57cd3a9ea02d4702de8e382157bfa570497c5d61c91` |
| 新测试 | `tests/test_input_contract_v1.py` | 16322 B | `7ea474ab872dbf834c85e6ab448a72238ab78059fe7faddc14c39274b38fc647` |
| 契约指南 | `docs/INPUT_CONTRACT_V1.md` | 6597 B | `0b3fa7b471c99e6a0f650b2bc8a8481cf261eae70eb5a3c85617b8c51ad32299` |
| 本回执 | `docs/EXEC_REPORT_043.md` | 见 delivery.json | 见 delivery.json |

合成输入根 `data/evidence_inputs/task043_v1/`：9 个文件（`input_manifest.json` + 八个数据文件）；
manifest 1268 B / `5a9c3bb3…2d54`；八文件逐文件长度/SHA 见 registry 与 manifest。

## 2. 命令与退出码（实测）

```
.venv\Scripts\python.exe -B tests\test_input_contract_v1.py --out-dir data\runtime_initial_judgment_recording_tests\task043_run_03
```

- 测试退出码 **0**；`test_report.json`：**18/18 cases PASS**（1 正常 + 17 负例），
  `read_only_ok=true`（规范输入根与 ledger 数据库前后字节不变）。
- 正常校验器调用（子进程，实测）：
  `scripts/input_contract_v1.py --input data/evidence_inputs/task043_v1 --out …/task043_run_03/normal/task043_normal --ledger-db data/sqlite_tests/task042_dsh_01/normal/runtime.sqlite3`
  → 退出码 **0**，写 `input_registry.json`（2305 B）与 `registry_readback.json`
  （`same_buffer_readback=true`）。
- 负例调用（每例独立输入副本与 out 根、真实子进程）：退出码均 **1**，`rejection.json` 精确 reason。
- 参数/环境错误控制（非契约违约）：退出码 **2**（本回执 §7 说明，未纳入 17 负例）。

## 3. 正常登记（实测值）

`input_registry.json`（`conclusion=INPUT_V1_ACCEPTED`）：

- `input_version=task043-input-1.0`、`batch_id=batch_normal`；
  `entity` = 澄明商贸有限公司 / CNY / 2026-09-01～2026-09-30 / 截至 2026-09-30。
- 逐文件 `byte_size`/`file_sha256` 与输入根实际字节一致（测试逐项复核）；manifest 无自哈希。
- 计数：`vouchers` = INVOICE 1、CONTRACT 1、BANK_RECEIPT 2、APPROVAL 1、GOODS_RECEIPT 1
  （合计 6）；`links` = 6；`bank_transactions` = 3；`reports_placeholders` = 0。
- `ledger_source` = `data/sqlite_tests/task042_dsh_01/normal/runtime.sqlite3`
  （102400 B / `4af23ebe…caa1d6`，只读 `mode=ro&immutable=1`）；账务 ID：AP01、P01、P02、R01。
- `checks` 十一项 PASS（文件集/UTF-8 JSON 数组/schema 类型枚举/整数分/日期/币种实体/发票算术/清单哈希/
  索引引用/ledger 存在/索引重复）；边界 `real_approval=null`、`ai_enabled=false` 等。

## 4. 整批拒收（17 类，逐类字段精确）

| # | 类别 | 实测 reason（code / field / voucher_id） |
| --- | --- | --- |
| 1 | 缺文件 | `MISSING_FILE` / `vouchers/contracts.json` |
| 2 | 多未知文件 | `UNKNOWN_FILE` / `vouchers/extra.json` |
| 3 | 哈希不符 | `HASH_MISMATCH` / `bank/transactions.json#byte_size`（`#sha256` 同报） |
| 4 | voucher_id 重复 | `ID_DUPLICATE` / `vouchers/invoices.json[1].voucher_id` |
| 5 | 缺必填 | `REQUIRED` / `vouchers/invoices.json[0].seller_name` |
| 6 | 金额非整数 | `TYPE` / `vouchers/invoices.json[0].amount_cents` |
| 7 | 金额非正 | `AMOUNT` / `vouchers/goods_receipts.json[0].amount_cents` |
| 8 | total≠amount+tax | `ARITHMETIC` / `vouchers/invoices.json[0].total_cents` / `V-INV-0001` |
| 9 | 日期越界 | `DATE_RANGE` / `vouchers/contracts.json[0].sign_date` |
| 10 | 币种错 | `CURRENCY` / `vouchers/invoices.json[0].currency` |
| 11 | 索引悬挂 | `LINK_VOUCHER` / `links/index.json[0].voucher_id` |
| 12 | 索引重复 | `LINK_DUPLICATE` / `links/index.json[6]` |
| 13 | ledger_id 不存在 | `LINK_LEDGER` / `links/index.json[0].ledger_id` |
| 14 | link_type/凭证类型不匹配 | `LINK_TYPE_MISMATCH` / `links/index.json[0].voucher_id` |
| 15 | 坏 JSON | `FILE_BAD_JSON` / `links/index.json` |
| 16 | 顶层非数组 | `FILE_NOT_ARRAY` / `reports/placeholders.json` |
| 17 | 账表占位非空 | `REPORTS_PLACEHOLDER` / `reports/placeholders.json` |

每例保留：输入副本（`…/<case>/input/`）、`stdout.txt`/`stderr.txt`、退出码、`rejection.json`
（`rejection_version`、`batch_id`、`input_root`、`ledger_source`、`reason_count`、`reasons[]`、边界）。
原合成输入根不被修改，用复制副本注入。

## 5. 只读与证据

- 校验器只读输入根与 ledger 数据库：测试前后对规范输入根全部文件与 ledger 数据库做字节快照比较，
  `read_only_ok=true`；不写批次、账务、凭证、银行输入、Gate/历史现场。
- 证据根 `data/runtime_initial_judgment_recording_tests/task043_run_03/`：`test_report.json`（18 例完整记录）、
  `test_stdout.txt`/`test_stderr.txt`、`command.json`、`normal/task043_normal/{input_registry.json,
  registry_readback.json, stdout.txt, stderr.txt}`、每负例 `<case>/task043_out/rejection.json` +
  `input/` + `stdout.txt`/`stderr.txt`。
- 过程迭代保留：`task043_smoke_01`（首次手工冒烟）、`task043_run_01`（`duplicate_index` 首报索引不符，
  已修正）、`task043_run_02`（通过）与 `task043_run_03`（定稿证据）。

## 6. 保护安排与判据

定稿后**一次**全树扫描（`task043_finalization/protection_scan.py`），基线 = 本卡起点接受快照
（173950 项 / `6f8c2787…`）：相对该基线**既有 changed 必须为 0**；新增仅限本卡四件、
`data/evidence_inputs/task043_v1/`、`task043_*` 证据根与架构端已知增量
（`DECISION_20261017_DSH_FOUR_MATCH_SCOPE.md`、`TASK-043/044/045_DRAFT.md` 逐确切路径登记）；
新 missing/读取错误/未登记新增/身份漂移 0；139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结。
扫描后只做有限自身元数据读回。

## 7. 未执行与边界

- 未做：数据清洗、OCR、银行对账单格式适配、外部查验、函证/盘点、无索引模糊匹配、账证/账实匹配
  （分别由 TASK-044/045 承担）、人类核对结论（不采集、不虚构）。
- 未执行：真实数据、真实批次批准、强认证、AI、终判、物理 junction、非合作篡改证明、并发双进程竞态
  （`null` + 原因）。
- 本卡不证明凭证真实、不构成审计证据或结论；`real_approval=null`、真实独立初判未保存、`next_step_allowed=false`、`ai_enabled=false`。
