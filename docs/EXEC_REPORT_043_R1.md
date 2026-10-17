# TASK-043-R1 执行回执：输入补充 v1.1（补齐 P02 审批单与银行回单）

日期：2026-10-17。交付状态：v1.1 输入根、回执与证据定稿，**交 Architect 小验收**；
本回执不宣布验收通过，不改任何代码/测试/指南/卡、不改 v1、不改演示脚本、不推进 TASK-045。

前置：TASK-044 ACCEPTED。起点接受快照：`data/reviews/task044_dsh_20261017_01/source_hashes_after.json`
（175375 项 / `849d2202…`）。本卡**纯数据新增**：`task043_v1` 逐字节未动。

## 1. 交付

| 交付 | 身份 |
| --- | --- |
| 新输入根 `data/evidence_inputs/task043_v1_1/` | 10 文件（manifest + 8 数据文件 + `input_manifest.json`），manifest 1268 B / `151c35fc…` |
| 新回执 | `docs/EXEC_REPORT_043_R1.md`（本文件） |
| 证据根 | `data/runtime_initial_judgment_recording_tests/task043r1_run_01/` |

**追加内容（与卡 §3 逐字一致）**：
- `vouchers/approvals.json`：`V-APR-0002`（APR-2026-0002 / 2026-09-09 / P02 / 500000 / APPROVED）；
- `vouchers/bank_receipts.json`：`V-BR-0003`（BR-2026-0003 / BT-2026-0002 / 2026-09-10 / 500000 / PAY / 甲供应商 / 6222020200000001 / CNY）；
- `links/index.json`：`L-0007`（PAYMENT_APPROVAL, PAYMENT, P02, V-APR-0002）、`L-0008`（PAYMENT_BANK_RECEIPT, PAYMENT, P02, V-BR-0003）；
- `input_manifest.json`：`input_version="task043-input-1.1"`，八数据文件长度/SHA-256 重算；实体/期间/批次不变。

## 2. 验收证据（实测）

1. **v1 未动**：`task043_v1` 9 个文件逐文件 SHA 与 TASK-043 接受快照
   （`data/reviews/task043_dsh_20261017_01/source_hashes_after.json`）全部一致，登记于
   `task043r1_run_01/v1_identity.json`（`all_unchanged=true`）；构建前后 v1 字节快照一致。
   未触碰的五件（发票/合同/入库/流水/账表占位）与 v1 逐字节相同。
2. **匹配器（复用已接受 `scripts/voucher_match_v1.py`，未修改）对 v1.1**：退出码 **0**、
   `conclusion=ALL_MATCHED`、**8/8 `MATCHED`**、差异/账有证无/证有账无 0；
   R02 抽样底稿含 AP01/P01/P02/R01（P02 证据 V-APR-0002、V-BR-0003），`human_conclusion` 恒 null。
3. **契约校验（复用已接受 `scripts/input_contract_v1.py`，未修改）——存在卡级冲突，如实报告**：
   - 对 **v1.1 原样**运行：退出码 1，**唯一** reason 为 `MANIFEST_VERSION`
     （`input_manifest.json.input_version`，实际 `task043-input-1.1`，期望 `task043-input-1.0`）。
     原因：已接受校验器把 `INPUT_VERSION` 固定为 `task043-input-1.0`，而本卡 §3 要求 manifest 升为 1.1；
     除版本元数据外，v1.1 的全部内容检查（文件集/哈希/schema/金额/日期/索引/账务引用）均未报差异。
   - 对**内容等价副本**（`task043r1_run_01/contract_content_v1_0/input_v1_0/`：v1.1 全量复制，仅把
     `input_version` 回落为 1.0，其余字节一致）运行：退出码 **0**、`conclusion=INPUT_V1_ACCEPTED`、
     计数 **INVOICE 1 / CONTRACT 1 / BANK_RECEIPT 3 / APPROVAL 2 / GOODS_RECEIPT 1（合计 8）、links 8、bank 3**，
     与卡 §4.1 期望完全一致。
4. **只读**：校验器/匹配器均只读输入根与账务；v1.1 与 v1 在运行前后字节不变（`read_only_ok=true`）。
5. 证据根内容：`command.json`（三条命令/退出码）、`contract_stdout|stderr.txt`（as-is 拒绝）、
   `contract_content_stdout|stderr.txt`（内容副本通过）、`task043_contract/rejection.json`、
   `task043_contract_content/input_registry.json`、`match_stdout|stderr.txt`、`task044_match/…`、
   `v1_identity.json`、`v1_1_identity.json`。

## 3. 需你裁决的一点（卡级冲突）

卡 §4.1 要求“对 v1.1 运行 → `INPUT_V1_ACCEPTED`”，但已接受校验器把 `input_version` 固定为 1.0，
且本卡禁止修改校验器。两种可接受的解决方式，请你选一（执行端未擅自改卡或改校验器）：

- **A（推荐，保持本回执交付）**：接受 v1.1 的版本元数据为 1.1，以本回执的“内容等价副本通过 +
  as-is 仅版本一条被拒”作为契约证据；校验器待后续卡升级为接受 1.0/1.1 两个版本（不改本卡输入）。
- **B（改卡）**：把 v1.1 manifest 的 `input_version` 保持 `task043-input-1.0`（内容仍补齐 P02），
  这样已接受校验器 as-is 通过；v1.1 与 v1 的差异仅在数据记录，不在版本号。需你确认后执行端再改。
- C：新卡修改校验器（不推荐，会改已接受代码与 19 API 边界）。

## 4. 保护安排与判据

定稿后**一次**全树扫描（`task043r1_finalization/protection_scan.py`），基线 = TASK-044 接受快照
（175375 项 / `849d2202…`）：既有 changed 必须为 0；新增仅限本卡 §2（新输入根、回执、`task043r1_*`
证据根）与架构端已知增量（`TASK-043-R1_DRAFT.md`、`REVIEW_TASK_044.md` 逐确切路径登记）；
new missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 5. 未执行与边界

未执行：任何代码/测试/指南修改、v1 修改、演示集成、TASK-045（未放行）、账账/账表、AI、终判、
真实数据/强认证。本卡只补输入数据，不证明凭证真实，不构成审计证据或结论。
`real_approval=null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
