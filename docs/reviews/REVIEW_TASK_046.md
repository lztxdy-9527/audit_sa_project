# TASK-046 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-17，DSH 架构/测试验收端对"四相符一条命令演示 + 校验器版本声明集 + 求职稿/最终入口更新"做最后一轮独立验收。四相符集成、版本集、负例传播与回归均成立；架构端自跑复现。此后项目达到**可演示完成态**：合成链至人类初判 + 账证 L1 + 账实交易级，一条命令可复演。

## 1. 改动身份（恰四件，实读同缓冲）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/input_contract_v1.py` | 36194 B | `622f47b9acb54a3c943bb4fbaa56923718cc88a0b7976a560685b59afad8b351` |
| `scripts/run_runtime_demo.py` | 34519 B | `8f264a2d9f06b7ea3d82f8f0ef51f343f6c126ba0f6affcf58babe3f162bf40a` |
| `docs/JOB_DEMO_PLAYBOOK_20261017.md` | 14339 B | `1b4c265d28c4e11341f81348ce658bb1b32acc8ca67803ce77fbaabfd93efe8f` |
| `docs/FINAL_ACCEPTANCE_ENTRY.md` | 11843 B | `34a621665e033a3bebd059021a0637d17acbaa81a9753c161f359248b901a7fd` |

新增回执 `docs/EXEC_REPORT_046.md` 6890 B / `cddde55a…20bd`；适配器、输入根 v1/v1.1、账证/账实核对器、既有测试与指南均未改。

## 2. 架构端独立运行（不复用执行端结论）

- **四相符一条命令**（架构端新目录 `task046_dsh_01`）：**exit 0**。`demo_summary.json.four_way` 实读：
  - 契约 `INPUT_V1_ACCEPTED`（凭证 8：回单 3 / 审批 2 / 其他 3；links 8；流水 3；`input_version=task043-input-1.1`）；
  - 账证 **8/8 MATCHED**，差异 0、账有证无 0、证有账无 0，R02 抽样 AP01/P01/P02/R01；
  - 账实 **3/3 MATCHED**（均 `REFERENCE_INDEX`），期间合计 OUT 1,000,000 == 已结算付款、IN 100,000 == 退款，差异 0；未达账项两侧 0；余额 `not_provided`；
  - `human_conclusion=null`；层级 `FIELD_LEVEL_L1_AND_TRANSACTION_LEVEL_L1`；记录 `VERIFIED`、九边界全 false、R01–R04=0/1/0/0。
- **负例传播**（架构端自跑 `--evidence-input task043_v1`）：契约通过（v1 合法）；账证 **6/8、2 条 `MISSING_VOUCHER`（P02）**、`DIFFERENCES_FOUND`；账实仍 3/3；演示 **exit 1**、`DemoFailure` 明确写出差异，summary 已写（差异未被吞掉）。
- **版本声明集**（架构端自跑校验器）：v1.1 原样 **exit 0**、回显 `task043-input-1.1`、凭证 8/links 8/bank 3；v1 原样 **exit 0**、回显 `task043-input-1.0`、凭证 6/links 6；未知版本副本（1.2）→ **exit 1、唯一 `MANIFEST_VERSION`**。TASK-043-R1 记录的残差**已关闭**。
- **既有四 CLI 回归**（架构端新根 `task046_dsh_regress_*`）：**0 / 1 / 1 / 1**。
- **只读**：我的演示/负例运行后，v1 manifest `5a9c3bb3…`、v1.1 manifest `151c35fc…`、normalized `f440f0cf…`、SQLite `4af23ebe…` 均与运行前一致。

## 3. 文档更新复核

`FINAL_ACCEPTANCE_ENTRY.md` 已更新任务链（039-R1→046，含 043/043-R1/044/045 接受基线）、交付身份与演示证据；`JOB_DEMO_PLAYBOOK` 已改为四相符口径（模块链、演示命令、产物路径、五分钟脚本、面试追问）。验收后架构端对两份文档做了**仅状态行**的收尾刷新（把"待验收"改为已验收、最后接受身份指向本轮 review_result），已在保护扫描中作为架构端变更登记。

## 4. 保护与历史

执行端一次全树扫描：基线 175890 项 / `b99e0cdc…`，**changed 恰四件**、missing 0、读取错误 0、新增 304 项全登记；架构端独立扫描复核（`data/reviews/task046_dsh_20261017_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 5. 边界

未做：账账/账表（需报表层输入与另行授权）、银行余额核对、影像/OCR、外部查验、函证/盘点、人类核对结论采集、AI 建议、人类终判、真实数据/强认证。四相符只做字段级/交易级 L1 + 期间合计；不证明凭证/流水真实，不构成审计结论。

## 6. 接受与项目状态

发布新接受基线 `data/reviews/task046_dsh_20261017_01/source_hashes_after.json` 与 `review_result.json`。**项目达到可演示完成态**：合成单批次 → 接收核验 → Gate1 → 标准化/SQLite → Gate2 → SQL 筛查 → 独立复算 → 事实底稿 → 人类初判保存/只读恢复 → 账证 L1 → 账实交易级，一条命令复演。后续账账/账表、AI 建议、终判、真实数据与强认证均需人类另行授权并新增协议/卡。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
