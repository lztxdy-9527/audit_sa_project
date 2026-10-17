# GL v1 输入契约（合成账套）

标识：`gl-1.0`。实现：`scripts/build_gl_demo_inputs.py`（生成）、`scripts/gl_input_contract_v1.py`（校验）。
依据：`docs/decisions/DECISION_20261018_DSH_GL_DOUBLE_ENTRY.md`（`DSH-SCOPE-20261017-06`）。
边界：GL v1 是**合成账套**，不证明真实账务，不构成审计结论；**不做数据清洗**，不规整整包退回。

## 1. 目录与文件

`data/evidence_inputs/gl_v1/`：

| 文件 | 内容 |
| --- | --- |
| `chart_of_accounts.json` | 科目表：`1001 库存商品`（资产/借）、`1002 银行存款`（资产/借）、`2202 应付账款`（负债/贷）、`3001 实收资本`（权益/贷） |
| `journal_entries.json` | 4 张记账凭证（记-001～记-004），每行借/贷恰一非零，凭证借贷相等 |
| `trial_balance.json` | 科目余额表：期初/本期借/本期贷/期末（借或贷）+ 合计 |
| `ledger_general.json` | 总账：4 科目本期发生额与期末 |
| `ledger_subsidiary.json` | 明细账（三栏式）：应付按 AP01、银行存款按基本户逐笔发生额与余额 |
| `balance_sheet.json` | 报表摘录：货币资金、存货、预付账款、应付账款、实收资本；资产=负债+权益 |
| `bank_statement.json` | 银行对账单：期初、三笔收支、期末 |
| `bank_journal.json` | 银行日记账：与对账单同三笔，期初/期末一致 |
| `attachment_index.json` | 已知附件（发票/合同/入库单/审批单/回单），类型/金额/日期 |
| `gl_manifest.json` | 版本、期间、批次绑定、逐文件长度/SHA、生成器版本；无时间戳/随机数 |

金额一律**整数分**（`int`，禁止浮点）；日期 ISO（`YYYY-MM-DD`）；科目引用必须存在。

## 2. 关键数据结构

```json
// journal_entries.json（节选）
{"entry_id": "记-002", "date": "2026-09-10", "summary": "支付 P01 应付",
 "lines": [{"account": "2202", "debit_cents": 500000, "credit_cents": 0},
           {"account": "1002", "debit_cents": 0, "credit_cents": 500000}],
 "attachments": ["V-APR-0001", "V-BR-0001"]}
```

```json
// trial_balance.json 行（节选）
{"account": "2202", "opening_debit": 0, "opening_credit": 0,
 "debit_cents": 1000000, "credit_cents": 600000,
 "closing_debit": 400000, "closing_credit": 0}
```

```json
// gl_manifest.json（节选）
{"version": "gl-1.0", "period": {"period_start": "2026-09-01",
  "period_end": "2026-09-30", "cutoff_date": "2026-09-30"},
 "batch": {"batch_id": "task027r1_run_04", "batch_manifest_sha256": "…",
           "source_workbook": "source/input.xlsx"},
 "files": {"chart_of_accounts.json": {"byte_size": 513, "sha256": "…"}},
 "generator_version": "TASK-055-gl-demo-1.0"}
```

## 3. 校验规则与错误码

CLI：

```powershell
.venv\Scripts\python.exe -B scripts\gl_input_contract_v1.py --gl-root data\evidence_inputs\gl_v1
```

退出码：`0` 通过；`1` 内容不合法（`{code, field, expected, actual}`）；`2` 参数/路径错误。
校验顺序与错误码：

| 顺序 | 规则 | 错误码 |
| --- | --- | --- |
| 1 | 文件齐全、JSON 可解析、版本 `gl-1.0`、期间/截止日、批次绑定（批次清单 SHA） | `GL-VERSION` / `GL-PERIOD` / `GL-BATCH` / `GL-FILE-MISSING` / `GL-JSON` |
| 2 | manifest 逐文件长度/SHA 与实际一致（自身除外） | `GL-MANIFEST-SIZE` / `GL-MANIFEST-SHA` |
| 3 | 科目引用存在；金额整数分；借/贷恰一非零 | `GL-ACCOUNT-UNKNOWN` / `GL-AMOUNT-TYPE` / `GL-DEBIT-CREDIT` |
| 4 | 逐张凭证借贷相等；期间借贷合计相等 | `GL-ENTRY-UNBALANCED` / `GL-PERIOD-UNBALANCED` |
| 5 | 余额表期初/本期/期末两两相等；逐科目 `期初+借−贷=期末`（方向） | `GL-TB-EQUATION` / `GL-TB-CLOSING` / `GL-TB-TOTALS` |
| 6 | 总账发生额 = 凭证按科目汇总；明细合计/期末 = 总账 | `GL-GL-AMOUNT` / `GL-GL-CLOSING` / `GL-SUB-TOTAL` / `GL-SUB-CLOSING` / `GL-SUB-GL` |
| 7 | 资产 = 负债+权益；应付借方 4,000.00 重分类为预付 4,000.00 | `GL-BS-EQUATION` / `GL-BS-RECLASS` |
| 8 | 对账单期末 = 期初+收入−支出；日记账与对账单三笔一致；附件存在且类型/金额匹配 | `GL-BANK-END` / `GL-BANK-JOURNAL` / `GL-ATTACH-MISSING` / `GL-ATTACH-TYPE` / `GL-ATTACH-AMOUNT` |

任一项不符即失败，**不修复、不兜底**。

## 4. 生成器与确定性

```powershell
.venv\Scripts\python.exe -B scripts\build_gl_demo_inputs.py --out-dir data\evidence_inputs\gl_v1
```

- 输出目录必须为空或不存在；写入 10 个文件（含 manifest）。
- 无时间戳/随机数；同一批次清单两次生成全部文件字节相同（测试与证据均验证）。
- manifest 的 `batch_manifest_sha256` 绑定 `data/batches/task027r1_run_04/batch_normal/batch_manifest.json`。

## 5. 测试

`.venv\Scripts\python.exe -B tests\test_gl_input_contract.py --out-dir data\runtime_initial_judgment_recording_tests\task055_run_02`

- 正常：生成 → 校验 exit 0；4 张凭证、期末试算 20,000.00 = 20,000.00（本期借/贷各 16,000.00）、期末库存 5,000.00 借 /
  银行 11,000.00 借 / 应付 4,000.00 借 / 实收 20,000.00 贷、对账单期末 11,000.00、附件 8 项。
- 负例（8 类）：借贷不平、未知科目、浮点金额、清单哈希不符、余额表不平、明细账≠总账、
  报表不平、银行不符、附件缺失 → 均 exit 1 且错误码/字段精确。
- 确定性：两次生成字节相同；只读：既有输入根与批次不变。

## 6. 边界

GL v1 是合成账套，不证明真实账务；不做数据清洗；不做六类核对（TASK-056）、不接 UI、不改看板。
真实批准 `null`、真实初判未保存、0008、`next/AI=false`；不构成审计结论。
