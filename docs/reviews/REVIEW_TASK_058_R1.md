# TASK-058-R1 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-18，DSH 架构/测试验收端对"投放状态页异常兜底"独立复验。B1（结构异常导致崩溃）已关闭：四类结构错误均 **exit 0、页面照常生成、目标类别标为需校验、其他类别不受影响**。状态页只说明放置与校验，不构成审计结论。

## 1. 改动身份（恰三件 + 回执）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_intake_guide.py` | 17009 B | `118c605ec0d92fe0f86dccd71e195f3c0814f979729ad042a4a281302e0290a3` |
| `tests/test_intake_guide.py` | 13789 B | `267174d1c8f016c91c03c7026206224c6f2591ac3590096964693c4cc92e9406` |
| `docs/INTAKE_GUIDE.md` | 4793 B | `473ed3f0d02b7dcab15a5037cd186f63987744fa0d3f28f6689c241cd2d594a7` |
| `docs/EXEC_REPORT_058_R1.md` | 3521 B | `93110c9c3b6d5c40655a233c10ac54e16c95bac8a738bb7ea02bed0a0f29ce8a` |

## 2. 架构端独立复验（25 项检查全过）

- **空 inbox**：exit 0、四类全 **缺失**。
- **合法样例**（我自建：xlsx + `{"vouchers":[...]}` 索引与凭证 + `{"transactions":[...]}` 流水 + GL 十文件）：四类全 **已提供**。
- **坏样例**：坏 xlsx、缺凭证、银行缺字段、GL 非法 JSON → 四类全 **需校验**。
- **B1 定向验证（结构异常不再崩溃）**：
  - 银行流水存成 **JSON 数组** → **exit 0**、银行 **需校验**、detail "顶层不是对象"、其余三类仍 **缺失**；
  - 索引对象缺 `vouchers` 键 → 凭证附件 **需校验**，其余不受影响；
  - GL 文件为数组 / GL 文件非法内容 → 总账账套 **需校验**；
  - xlsx 为文本 → 业务台账 **需校验**。
- **状态页**：无脚本、有"不构成审计结论"横幅、链接无断裂、无外链、可见文本技术词零命中（文件名不计）。
- **确定性**：同输入两次，页面与 manifest 字节相同；**只读**：`data/inbox` 前后字节不变。
- **测试复跑**：11/11 PASS。

## 3. 保护与历史

执行端一次全树扫描：基线 204412 项 / `97f8940f…`，**既有 changed = 0**、missing 0、读取错误 0、新增 261 项全登记；架构端独立扫描复核（`data/reviews/task058r1_dsh_20261018_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 4. 缺陷关闭与下一卡

- `REVIEW_TASK_058.md` 的 B1 关闭；TASK-058 的 NOT_ACCEPTED 由本 R1 取代。
- 发布新接受基线 `data/reviews/task058r1_dsh_20261018_01/source_hashes_after.json` 与 `review_result.json`。**放行 TASK-059（一键对账启动器）**，卡身份 `5aa79d0c…dd6d0e`。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
