# TASK-043 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-17，DSH 架构/测试验收端对"输入契约 v1 + 合成凭证/银行数据 + 校验与整批拒收 + 输入登记"独立复验。契约、拒收、只读与登记均成立，架构端自跑复现。本接受只覆盖**输入契约层**：不做匹配、不出核对底稿、不证明凭证真实；`real_approval=null`。

## 1. 交付身份（实读同缓冲）

| 交付 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/input_contract_v1.py` | 35964 B | `f9462bc0d63755133d7aa57cd3a9ea02d4702de8e382157bfa570497c5d61c91` |
| `tests/test_input_contract_v1.py` | 16322 B | `7ea474ab872dbf834c85e6ab448a72238ab78059fe7faddc14c39274b38fc647` |
| `docs/INPUT_CONTRACT_V1.md` | 6597 B | `0b3fa7b471c99e6a0f650b2bc8a8481cf261eae70eb5a3c85617b8c51ad32299` |
| `docs/EXEC_REPORT_043.md` | 7629 B | `8866752dccb36f97d3221c6ee7aff1a2c9058d37ccb575937b80f95992ba3e60` |

合成输入根 `data/evidence_inputs/task043_v1/`：9 文件（manifest + 8 数据文件），manifest 1268 B / `5a9c3bb3…2d54`；账务只读源 `data/sqlite_tests/task042_dsh_01/normal/runtime.sqlite3` 102400 B / `4af23ebe7283bcaa5db318d40e5ae1d4d67c810f034dd20f021a0b9fffcaa1d6`（已接受运行证据，只读 `mode=ro&immutable=1`）。

## 2. 架构端独立实际运行

- **测试复跑**（新目录 `data/runtime_initial_judgment_recording_tests/task043_dsh_01`）：`test_input_contract_v1.py` → **exit 0、18/18 cases PASS、read_only_ok=true**。
- **输入根独立重算**（`verify_inputs.py`，20/20 PASS）：9 文件集合精确；逐文件长度/SHA 与 manifest 相等；凭证计数 INVOICE 1 / CONTRACT 1 / BANK_RECEIPT 2 / APPROVAL 1 / GOODS_RECEIPT 1（合计 6）、links 6、bank 3、reports 占位空；发票 `total=amount+tax`；币种全 CNY；ID 唯一；索引引用存在且类型匹配、ledger 引用真实存在（AP01/P01/P02/R01）、审批 `payment_id` 为 PAY、回单方向与流水方向匹配。
- **只读复核**：测试前后规范输入根字节不变（仍与 manifest 声明哈希一致）、ledger 数据库哈希前后均为 `4af23ebe…caa1d6`；测试以复制副本注入负例，原输入根未被修改。
- **拒收抽样实读**：`amount_not_integer` 等 rejections 含 `code/field/expected/actual/detail`（如 `TYPE / vouchers/invoices.json[0].amount_cents / actual=float`），退出码 1、不生成登记；17 类覆盖卡要求（缺文件、未知文件、哈希、重复 ID、缺必填、非整数、非正、算术、日期、币种、索引悬挂/重复、ledger 不存在、类型不匹配、坏 JSON、顶层非数组、占位非空）。

## 3. 契约与边界复核

- 契约明示：只接受**已规整输入**；不做清洗/OCR/银行格式适配；不符契约**整批拒收**、不修不补不猜；`--out` 必须位于证据根且以 `task043_` 开头；退出码 0/1/2 分义正确（2 为参数/环境错误，不混同为契约拒收）。
- 输入版本与逐文件哈希进入登记（`input_registry.json` + 同缓冲读回 `registry_readback.json`），满足后续"核对底稿绑定当时输入版本"的前提。
- 实现选择记录（不影响接受）：银行流水的 `reference` 存放的是付款/退款 ID（P01/P02/R01），与付款主表 `bank_reference`（B001/B002/BR001）通过回单凭证 `bank_txn_id` 关联；契约未约束该字段取值，TASK-045 匹配时按"引用优先 + 三元组"处理。

## 4. 保护与历史

执行端一次全树扫描：基线 173950 项 / `6f8c2787…`，`changed=0`、missing 0、读取错误 0、新增 650 项全登记；架构端独立扫描复核同级口径（`data/reviews/task043_dsh_20261017_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 5. 未执行与边界

未做：数据清洗、OCR、银行格式适配、外部查验、函证/盘点、无索引模糊匹配、账证/账实匹配（TASK-044/045 承担）、人类核对结论（不采集、不虚构）、AI/终判、真实数据/强认证。本卡不证明凭证真实，不构成审计证据或结论。

## 6. 接受与下一卡

发布新接受基线 `data/reviews/task043_dsh_20261017_01/source_hashes_after.json` 与 `review_result.json`，接受输入契约 v1 及其证据。按 `DSH-SCOPE-20261017-02` 优先顺序，**放行 TASK-044（账证相符 L1）**；TASK-045（银行账实）待 044 验收后放行。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
