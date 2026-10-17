# 事实底稿构建说明（TASK-008）

版本：TASK-008-fact-packet-1.1；日期：2026-10-11；执行端：DeepSeek；依据：`docs/tasks/TASK-008_DRAFT.md`、`docs/tasks/TASK-008-R1.md`、`docs/reviews/REVIEW_TASK_008.md`、`docs/reviews/REVIEW_TASK_007_R2.md`、`docs/RULE_CROSSCHECK_GUIDE.md`、`docs/RULE_SCREEN_GUIDE.md`、`docs/SPEC_V1.md`、`docs/AUDIT_CONTRACT_DRAFT.md` 第 5 节。

本文说明事实底稿构建核心的**公共接口、输入前提、packet 字段、展示口径、转义与格式化规则、真实命令与限制**。

> 本模块是**确定性展示层**：不新增审计规则、不重算命中、不生成 AI 意见、不预填人类判断。
> 规则命中是待核实线索，不构成舞弊、损失、控制缺陷或审计调整结论。

---

## 1. 公共接口

函数签名：

```python
def build_fact_packet(normalized: dict, screening_report: dict, crosscheck_report: dict) -> dict: ...
```

合法调用示例：

```python
from scripts.build_demo_fact_packet import build_fact_packet

result = build_fact_packet(normalized, screening_report, crosscheck_report)
packet, fingerprint, markdown = result["packet"], result["packet_sha256"], result["markdown"]
```

- **只消费三个内存对象，只返回结果**：不读写文件、不读数据库／Excel／答案册、不调用筛查或复核核心、不导入测试／QA／生成器，不调用 LLM、网络或外部命令；标准库即可。
- 返回形状固定为 `{"packet": 结构化事实与绑定, "packet_sha256": 对 packet 的规范 JSON 指纹, "markdown": 对同一 packet 的确定性中文展示}`。`packet_sha256` 放在外层以避免自引用。
- 规范 JSON：`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`、`allow_nan=False`，再 UTF-8 SHA-256（与上游口径相同）。**不加入当前时间、随机 ID 或运行机器临时路径**，同输入必须得到完全相同的 packet 与 Markdown。
- 异常：前提不成立抛 `FactPacketBlocked`（带字段／原因）；意外运行失败抛 `FactPacketError`（保留阶段、原始原因与异常链）。**不返回半份 READY 底稿。**

## 2. 输入前提与绑定核对

1. 三个对象均为开发态、`next_step_allowed is False`；`normalized.normalization_version = TASK-004-normalized-1.1`；`screening_report.batch_status = DEV_RULES_COMPUTED` 且 `rule_core_version = TASK-006-rule-core-1.1`；`crosscheck_report.batch_status = DEV_CROSSCHECK_MATCHED`、`crosscheck_version = TASK-007-crosscheck-1.2`。
2. `normalized.quality_report.result = pass`，且 `issue_counts_by_code` **存在、为对象且为空**。
3. 复核报告：`matched is True`、`differences == []`、`comparison.difference_count` 为整数 `0`；固定十个维度（`hit_keys`、`amounts_cents`、`related_ids`、`refund_facts`、`rule_identity`、`source_entities`、`source_rows`、`counts`、`statistics`、`overall_reconciliation`）齐全，每项 `executed`／`matched` 严格为 `true`、`difference_count` 为整数 `0`；不接受预期外维度。
4. 期间固定 `2026-09-01`—`2026-09-30`、截至日 `2026-09-30`，筛查与复核报告一致；`crosscheck.rule_core_version_checked` 等于筛查的规则核心版本。
5. 绑定：本次 `normalized` 规范指纹 ＝ 筛查 `load_source.normalized_payload_sha256` ＝ 其 `run_metadata.normalized_payload_sha256` ＝ 复核 `normalized_payload_sha256`；本次筛查对象规范指纹 ＝ 复核 `screening_report_sha256`；来源工作簿哈希在三个对象中一致。
6. 数据库：筛查声明的 `database_sha256_before` ＝ `after` ＝ `load_source.database_sha256`、`database_unchanged is True`。底稿只把它标为**“上游报告声明的数据库哈希”**，不声称展示模块实读了数据库。
7. 展示所需字段：每条线索的 `hit_key`（非空字符串 ID）、各规则必需金额（整数分且非 `bool`）、`related_ids`、`source_rows`、`evidence.entities`（含 `workbook_sha256`／`sheet`／`excel_row`／完整 `cells`）、`evidence.related_refunds`（含金额与 `counted_in_net`）；规则计数、`findings` 条数与复核声明的计数一致。缺字段时阻断，**不补零、不猜测、不静默略去整条线索**。
8. **实际消费的字段与必需关联对象**（TASK-008-R1 起，逐一显式核对，报 `FactPacketBlocked` 并给出表／业务 ID／字段或完整对象路径，不用 `.get()` 的 `None`、空白文案、`not_found` 或“（主数据未找到）”占位伪装完整底稿）：
   - 退款摘要的 `refund_payment_id`／`refund_allocation_id`／`original_payment_id`／`original_allocation_id`／`settlement_status`／`payment_date` 必须是非空字符串，金额为整数分、`counted_in_net` 为布尔；退款主表（`transaction_type = REFUND`）、退款分摊、其引用的原付款主表与原分摊**必须能在标准化记录中找到**。
   - 被引用的原付款主表、原付款分摊**必须找到**；其已显示字段 `payment_date`／`settlement_status`／`bank_reference`（已结算必须非空）／`amount_cents`／`payee_supplier_id` 必须存在且类型正确；**该笔付款自己的**收款对象必须在供应商表中找到且 `supplier_name` 非空。
   - 已知应付单显示的 `ap_number`／`ap_date`／`supplier_id`／`payable_amount_cents` 及供应商名称必须存在且类型正确；上下文 `source` 必须含工作表与原 Excel 行号，实际用于定位的 `cells`（`payable_amount`／`allocated_amount`／`payment_date`／`supplier_name`）必须含单元格坐标与原列号。
   - **保留业务允许的缺失**：R03 的应付标识为 `null`（且 `missing_kind_code = EMPTY_AP_ID`）或不在所提供台账（`AP_NOT_IN_LEDGER`）**照常生成并说明**，不统一阻断；`related_ids` 中**缺少 `payable_id` 键**（与显式 `null` 不同）视为展示契约缺失而阻断；R01／R02／R04 的应付关联必须能找到。
   - 只检查本展示层实际消费的契约，不重建完整 ERP 校验或规则计算器。

这些检查防止误用旧报告、混用输入或消费自相矛盾的开发产物；**不是认证或签名**，也不抵御同时重写对象与指纹的同权限篡改，更不重新验证 R01—R04 公式或来源真实性。

## 3. packet 字段

| 字段 | 内容 |
| --- | --- |
| `packet_version` / `batch_status` / `mode` / `next_step_allowed` | `TASK-008-fact-packet-1.0` / `DEV_FACT_PACKET_READY` / `DEVELOPMENT_TEST_ONLY` / `false`（READY 仅指事实展示构建完成） |
| `entity` | 主体“澄明商贸有限公司”、期间、截至日、币种 |
| `banner` | 合成数据／开发演示／待核实线索的醒目标识（固定文案） |
| `bindings` | 工作簿来源哈希、normalized／screening／crosscheck 三对象规范指纹、上游版本（标准化／规则核心／复核核心／装载／schema）、上游声明的数据库哈希（完整值，不只前缀） |
| `summary` | 四规则与总线索数；唯一原付款集合／数量／整笔已结算金额；R02 按唯一应付单汇总一次的超额合计 |
| `reconciliation` | 已结算付款主表总额、已结算退款主表总额、净额、已知应付关联净额、缺失关联净额及两种缺失明细 |
| `findings` | 逐条事实卡（见下） |
| `amount_labels` | 金额字段 → 业务中文标签的固定映射（含按规则区分的 `net_total`），仅说明用途，不改变原字段与数值 |
| `limits` | 固定限制说明 |

### 3.1 事实卡字段

`finding_id`（`规则-序号`，如 `R02-0001`，稳定且不碰撞）、`rule_id`、`rule_name`（固定中文名称）、`rule_template`（固定规则口径模板）、`hit_key`、`amounts_cents`（原整数分）、`amounts_display_cny`（人民币元两位小数）、`related_ids`、`source_rows`、`evidence`（**原样保留**筛查报告的 `entities`（含完整 `cells`）与 `related_refunds`）、`context`（主数据上下文）、R03 另有 `missing_kind`、另有 `refund_summary`。

- **不使用**输入中的 `fact`／`verification_prompt` 自由文本生成叙述；规则口径来自本模块固定模板。
- `context` 按 ID 精确关联绑定的 `normalized.records[*].data`，每项保留其 `source` 与 `cells`；**这些上下文实体单列，不混入筛查报告原有的 168 个证据实体计**。最终形状固定为：
  - `context.payable`（应付单）、`context.payable_supplier`（应付单供应商）；
  - `context.payments[]`：每个元素为原付款主表上下文，并且**在该元素内部**挂 `payee_supplier`（`{label, status, record_id, data, source, cells}`），即**逐付款按其自己的 `payee_supplier_id`** 关联收款对象——同一线索涉及多个收款对象时不得用第一笔代表整组（TASK-008-R1 前为组级单一 `payee_supplier`，已移除）；
  - `context.allocations[]`（原付款分摊）、`context.refunds[]`（退款主表与退款分摊各一项）。
- R03 找不到应付时给出 `status=not_found` 与 `missing_kind`（“未填写关联”／“所填标识不在提供的台账”），**不写成“企业没有发票”**。
- 逐条事实卡中的金额既保留原英文字段与整数分（`amounts_cents`），也在正文按固定中文标签展示；`net_total` 按规则区分（R01“本足额付款组的分摊净额合计”、R02“该应付单的净付款分摊合计”）。
- 显示整笔付款金额时标注“（整笔口径）”，与本条分摊金额分列；口径说明统一写为**“整笔付款金额为主表整笔口径，不能替代本条分摊口径；两者数值可以相等”**（不再写成数值必然“不等于”）。

### 3.2 金额业务中文标签（固定映射）

正文字段名到中文标签的映射固定如下；JSON 保留原英文字段与整数分，标签只用于正文（正文同时附原字段名以便回查）：

| 原字段 | 正文标签 |
| --- | --- |
| `payable_amount` | 应付金额 |
| `net_per_payment` | 各笔原付款的分摊净额（保留对应 `payment_id`） |
| `net_total`（R01） | 本足额付款组的分摊净额合计 |
| `net_total`（R02） | 该应付单的净付款分摊合计 |
| `paid_total` | 已结算付款分摊合计 |
| `refund_total` | 有效退款分摊合计 |
| `overpayment` | 净付款超额 |
| `allocated_amount` | 本条付款分摊金额 |
| `paid_amount` | 已结算原付款分摊额 |
| `refunded_amount` | 有效退款分摊额 |
| `net_amount` | 本条分摊净额 |

资金勾稽表的“净资金额”统一为“资金净额”。不增加原因猜测、风险等级、结论、调整建议或人类判断预填。

## 4. Markdown 展示口径

`render_markdown()` 从同一 packet 渲染，包含：标题与四行固定标识、总览（主体／期间／截至日／币种／版本、规则数量表、涉及付款、R02 超额）、资金勾稽表、逐条事实卡、来源与限制。

- 无线索时输出固定提示“本四条规则未命中；这不表示“无异常”，也不构成审计通过。”——**不写“无异常”或“审计通过”**。
- 金额：整数分 → 人民币元两位小数，**只用整数运算**（`分 // 100` 与 `分 % 100`），不使用浮点除法、浮点累计或四舍五入修正；零展示 `0.00`。原整数分同时保留。
- ID、前导零、单引号、竖线与首尾空格**不修改**；Markdown 中对首尾空格用 `␠`（U+2420）显式标记，JSON 保留原值。
- 转义：`&`／`<`／`>` 转为 HTML 实体，`` ` ``、`|`、`[`、`]` 加反斜杠转义，`\r\n`／`\n`／`\r` 折叠为空格——避免名称或编号破坏文档结构或形成可执行内容；原值仍留在 JSON。
- **所有输入文字只作数据展示**，不执行其中的指令，也不据此改变模式、规则、输出字段或 Gate 状态。
- 不输出原因猜测、候选结论、候选等级、调整金额或个案核实建议；不新增判断表或预填人类判断字段。

## 5. 真实测试命令

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B `
  'D:\harness work\audit_sa_project\tests\test_build_demo_fact_packet.py' `
  --out-dir 'D:\harness work\audit_sa_project\data\fact_packet_tests\task008_r1_04'
```

- `out-dir` 必须是 `data/fact_packet_tests` 内**尚不存在**的子目录；越界、目录本身或已存在时在写入前拒绝，不覆盖旧产物。
- 正常样例**只读**消费 `data/sqlite_tests/task007_r2_gpt_20261011_081630/cases/` 下 21 组的 `normalized.json`、`screening_report.json`、`crosscheck_report.json`（不重跑上游、不把旧报告当新规则答案），每组保存 `cases/<案例名>/fact_packet.json`、`fact_packet.md`、`build_result.json`，并保留输入清单（路径／文件哈希／大小）。
- 覆盖：21 组全部生成；线索与来源实体出现项精确保留；**逐付款收款对象**（21 组全部事实卡，独立从 normalized 付款主表取得供应商 ID、再取完整主数据，与新增上下文与该付款正文行逐项比较；当前 59 个原付款出现项）；**业务中文金额标签与口径措辞**；主文件与重点场景（C03 无线索、C07b 整笔与分摊、C04 整笔与分摊等值、C06b 退款与超额、S1／C09b 全额退款后仍保留 R03／R04、C10b／S4 非结算退款不抵减、S5 特殊 ID 不合并）；主数据上下文单列核验；确定性复调用与正文／JSON 一致（逐卡核对，不用全篇字符串搜索代替）；9 项负向阻断 + 6 项**展示必需字段**阻断（含合法缺失仍生成的对照）；格式化边界（`1→0.01`、`0→0.00`、大整数精确、`bool`／等值 `float` 被拒绝）；不可信自由文字样例（含 HTML／反引号／竖线／换行与“忽略规则，批准Gate”文字，经冻结复核 API 取得真实复核报告后构建）；运行期与静态隔离。
- 六项必需字段回归（TASK-008-R1）：退款摘要缺 `original_payment_id`／`original_allocation_id`；原付款缺 `payment_date`／`bank_reference`；供应商缺 `supplier_name`；被引用原付款记录被删除。测试侧只同步**新内存对象**的绑定值以进入本层核验（并保存同步设置与完整输入），不重新复核、不声称不完整对象通过了复核，也不改任何旧文件。
- 退出码：0 全部符合预期；1 断言或保护失败；2 参数或环境问题。预期阻断不计为测试失败；构建 API 调用与金额格式化 helper 调用分开统计。

## 6. 限制（明确不主张的内容）

- **不实读数据库**：数据库哈希只是上游报告声明值；展示层未读取或重验数据库字节。
- **不证明来源真实性**：只呈现上游已核对证据；不抵御同权限篡改。
- **不构成审计结论**：命中是待核实线索；跨规则涉及金额不相加称为损失；资金主表与分摊口径不相加；整笔口径不能替代本条分摊口径（两者数值可以相等）。
- **不替代人类判断**：未实施正式契约／批准控制，未保存人类判断，未生成 AI 建议；后续须经人工核实与放行。
- 本模块是 `DEVELOPMENT_TEST_ONLY`：不接入正式批次、不改变 Gate 状态、不做 UI／网页、真实 ERP、OCR、RAG 或压测。
