# TASK-008-R1 执行回执（修复收款对象展示、金额业务标签与必需字段检查）

任务：修复 TASK-008 验收发现的两处展示层正确性缺口（F01 多收款对象线索复用第一笔付款主体、F03 展示必需信息缺失仍返回 READY），并完成业务中文金额标签与口径措辞澄清（F02）。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-008-R1.md`、`docs/reviews/REVIEW_TASK_008.md`、`docs/tasks/TASK-008_DRAFT.md`、`docs/EXEC_REPORT_008.md`、`docs/FACT_PACKET_GUIDE.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务九，未建立契约／审批／状态机／Gate，未接入 `data/batches`，未生成 AI 建议或人类判断表。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。旧 `docs/EXEC_REPORT_008.md` 保持原字节，未回写。

---

## 1. 结论摘要

| 缺口 | 修复 |
| --- | --- |
| **F01 多收款对象** | `_build_context` 改为**逐付款**用该笔记录自己的 `payee_supplier_id` 关联供应商，并把收款对象上下文挂在该笔付款元素内部（`context.payments[*].payee_supplier`）；移除组级单一 `payee_supplier`。正文每笔付款行使用**本笔**收款对象，JSON 上下文完整表达全部付款的收款对象 |
| **F02 中文标签与口径** | 正文金额改为业务中文标签（`payable_amount`→应付金额、`paid_total`→已结算付款分摊合计、`refund_total`→有效退款分摊合计、`overpayment`→净付款超额、`net_total` 按规则区分、`allocated_amount`→本条付款分摊金额等，并在正文附原字段名以便回查）；JSON 保留原英文字段与整数分，packet 增 `amount_labels` 映射说明。口径句改为“整笔付款金额为主表整笔口径，**不能替代**本条分摊口径；两者数值可以相等”；“净资金额”统一为“资金净额” |
| **F03 必需字段** | 新增 `_check_consumed_fields()`：对本层实际消费的字段与必需关联对象显式核对，缺失即 `FactPacketBlocked` 并给出表／业务 ID／字段或完整对象路径；不再用 `.get()` 的 `None`、空白文案、`not_found` 或“（主数据未找到）”占位渲染。**保留业务允许的缺失**：R03 应付为 `null`（`EMPTY_AP_ID`）或不在台账（`AP_NOT_IN_LEDGER`）照常生成；`related_ids` 缺少 `payable_id` 键（与显式 `null` 不同）阻断 |
| **版本** | 底稿核心版本升为 `TASK-008-fact-packet-1.1`；四条规则、金额计算、上游模块与契约**均未改动** |
| **开发验证** | 21 组正常输入全部生成，**测试失败 0，退出 0**：线索 34 条、来源实体出现项 168、退款出现项 11 仍精确保留；正向检查 **14** 项、负向阻断 **15** 项（原 9 + 新增必需字段 6，全部按预期阻断）、格式化检查 6 项；构建 API 调用 41 次、金额格式化 helper 调用 1184 次（分开统计） |
| **逐付款核验** | **59 个原付款出现项**全部与独立从 normalized 推导的收款对象一致（ID／`data`／`source`／`cells` 及该付款正文行） |
| **历史保护** | TASK-008 验收基线（12867 项）**变化 3、缺失 0**（恰为本卡授权三个既有文件）；TASK-007-R2 的 12546、任务六 R1 的 10236、8547、6511、4902、874 基线均 **0 变化、0 缺失**；旧 `EXEC_REPORT_008` 与全部 GPT 证据保持原字节 |

---

## 2. 修改与新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\build_demo_fact_packet.py` | `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62` |
| `D:\harness work\audit_sa_project\tests\test_build_demo_fact_packet.py` | `46d426e7c262f3b5c773ba6717e5b3e002c34783d11d24a5bd3c43b80effeb36` |
| `D:\harness work\audit_sa_project\docs\FACT_PACKET_GUIDE.md` | `48c051be9bfca3659560c73e4693892ecd1a72629fba7401698eb87f8657ff9d` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_008_R1.md` | 本文件（新增） |

**未改动**：旧 `docs/EXEC_REPORT_008.md`、任务卡与验收单、复核核心 `8fe75bfe…`、筛查核心 `1b123766…`、装载器 `1abfad89…`、标准化器 `a2bae49e…`、checker `a7e5eb67…`、schema `7e0c6463…`、四份规则 SQL、`docs/SPEC_V1.md`、契约草案、原工作簿、答案册、数据库与 GPT 证据；`task008_03` 等既有容器未覆盖、未回写。

新增测试容器（`data\fact_packet_tests\`）：`task008_r1_04`（**最终**，93 个文件）、`task008_r1_03`／`task008_r1_02`／`task008_r1_01`（断言口径修正过程现场）。

### 2.1 主要产物路径

- MAIN 可读底稿：`data\fact_packet_tests\task008_r1_04\cases\MAIN\fact_packet.md`
- S3 可读底稿（F01 修复点）：`data\fact_packet_tests\task008_r1_04\cases\S3_payee_diff_with_overpay\fact_packet.md`
- 完整 JSON 证据包（含逐付款收款对象上下文）：`data\fact_packet_tests\task008_r1_04\cases\*\fact_packet.json`
- 逐付款核对明细：`payee_display_checks.json`；必需字段六项：`required_field_probes.json` 与 `mutations\P1*—P6*`
- 留痕：`summary.json`、`check_details.json`、`negative_checks.json`、`input_manifest.json`、`command_log.json`、`stdout.txt`、`stderr.txt`

## 3. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
```

### 3.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\build_demo_fact_packet.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_build_demo_fact_packet.py'
```

退出码均 **0**。

### 3.2 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_build_demo_fact_packet.py' --out-dir 'D:\harness work\audit_sa_project\data\fact_packet_tests\task008_r1_04'
```

退出码 **0**；输出：

```text
输入 21 组：生成底稿 21 份；线索 34 条、来源实体出现项 168、退款出现项 11
正向检查 14 项、负向检查 9 项（预期阻断 9）、展示必需字段检查 6 项（预期阻断 6）、负向合计 15 项、格式化检查 6 项
构建 API 调用 41 次、金额格式化 helper 调用 1184 次（分开统计）、测试失败 0
[PASS] ALL_21_CASES_BUILT / FACTS_AND_SOURCES_PRESERVED / EXPECTED_SCALE_34_FINDINGS_168_ENTITIES
[PASS] MAIN_EXPECTATIONS / SCENARIO_EXPECTATIONS / MASTER_DATA_CONTEXT
[PASS] PAYEE_PER_PAYMENT / S3_PAYEE_PAIRS / CN_AMOUNT_LABELS
[PASS] DETERMINISM_AND_CONSISTENCY / N1—N9 / P1—P6
[PASS] LAWFUL_MISSING_PAYABLE_STILL_READY / FORMATTING_BOUNDARY / UNTRUSTED_TEXT_SAMPLE / ISOLATION
受保护文件前后哈希一致: True（16 个）
```

### 3.3 其他核验

```powershell
& $py -c "import sys; print(sys.version.split()[0])"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\build_demo_fact_packet.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_build_demo_fact_packet.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\FACT_PACKET_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\EXEC_REPORT_008.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与显示片段核对；未新增 `.py` 文件。

---

## 4. 分类计数

| 项目 | 数量 |
| --- | --- |
| 输入案例 | **21**（三份报告齐备；其余 8 个上游阻断目录不处理） |
| 生成底稿 | **21** |
| 线索 | **34** |
| 来源实体出现项（原证据，按线索计数） | **168** |
| 退款摘要出现项 | **11** |
| 原付款出现项（逐付款核验） | **59**，全部与独立预期一致 |
| 正向检查 | **14** 项 |
| 负向检查（原 N1—N9） | **9** 项，预期阻断 **9** |
| 展示必需字段检查（新 P1—P6） | **6** 项，预期阻断 **6** |
| 负向合计 | **15** 项 |
| 格式化检查 | **6** 项 |
| 构建 API 调用 | **41** 次（含 21 组正常 + 确定性复调用 + 合法缺失对照 + 15 项负向 + 自由文字 + 隔离调用） |
| 金额格式化 helper 调用 | **1184** 次（与构建调用分开统计） |
| 测试失败 | **0** |

## 5. F01 逐付款收款对象（实际显示与核验）

S3_payee_diff_with_overpay 的 `R02-0001`（修复前把 P02 也写成 S001）：

```text
- 原付款主表：P01，日期 2026-09-10，状态 SETTLED，银行流水标识 B001，实际收款对象 S001（甲供应商）
  - 整笔付款金额：3000.00 元（整笔口径）
  - 付款日期来源：E2（第 5 列）
- 原付款主表：P02，日期 2026-09-10，状态 SETTLED，银行流水标识 B002，实际收款对象 S002（乙收款对象）
  - 整笔付款金额：2500.00 元（整笔口径）
  - 付款日期来源：E3（第 5 列）
```

- 同一底稿的 `R04-0001` 中 `P02` 同为 **S002（乙收款对象）**，前后不再矛盾。
- **核验方式**：测试侧不从 context 反推，而是独立从 `normalized.tables.payments.records[*].data.payee_supplier_id` 取该笔付款的供应商 ID，再从 `normalized.tables.suppliers.records` 取完整预期主数据（`data`／`source`／`cells`），与 packet 中该付款的 `payee_supplier` **逐项规范 JSON 比较**，并检查**该付款自己那一行**正文含本笔收款对象（按 Markdown 转义口径，JSON 侧为原值核对）。
- 覆盖 21 组全部事实卡的 **59 个原付款出现项**，`payee_display_checks.json` 保存每项的预期／实际 ID 与名称。

## 6. F02 中文金额标签、口径措辞（实际显示）

C06b 正文可直接读出：

```text
- 规则金额（业务中文标签 / 原字段，整数分 = 人民币元）：
  - 该应付单的净付款分摊合计（net_total）：900000 分 = 9000.00 元
  - 净付款超额（overpayment）：400000 分 = 4000.00 元
  - 已结算付款分摊合计（paid_total）：1000000 分 = 10000.00 元
  - 应付金额（payable_amount）：500000 分 = 5000.00 元
  - 有效退款分摊合计（refund_total）：100000 分 = 1000.00 元
```

- 口径澄清句：“整笔付款金额为主表整笔口径，不能替代本条分摊口径；两者数值可以相等。”——旧措辞“不等于本条分摊金额”在 21 份正文中**不再出现**。
- 勾稽表“净资金额”→“**资金净额**”（旧标签不再出现）。
- C04（整笔与分摊均为 5000.00 元）与 C07b（整笔 5000.00 元、本条未匹配分摊 2000.00 元）均正确展示；JSON 保留 `amounts_cents` 原字段与整数分，packet 增 `amount_labels` 固定映射。

## 7. F03 展示必需信息缺失（六项均阻断）

| 检查 | 注入（C06b 新内存副本） | 实际阻断原因 |
| --- | --- | --- |
| P1 | 退款摘要删除 `original_payment_id` | `screening_report.findings[0].evidence.related_refunds[0] 不可用：缺少 original_payment_id` |
| P2 | 同一摘要删除 `original_allocation_id` | 同上路径，缺少 `original_allocation_id` |
| P3 | 原付款 P01 `data` 删除 `payment_date` | `findings[0].context.payments[P01].data 不可用：缺少 payment_date` |
| P4 | 原付款 P01 `data` 删除 `bank_reference` | `findings[0].context.payments[P01].data 不可用：缺少 bank_reference` |
| P5 | 供应商 S001 `data` 删除 `supplier_name` | `findings[0].context.payable_supplier.data.supplier_name 不可用：应付单供应商名称 必须是非空字符串，实际 None` |
| P6 | normalized 付款表删除被引用的 P01 记录 | `findings[0].context.payments 不可用：已引用的原付款主表 P01 未在标准化记录中找到` |

- 六项均返回 `FactPacketBlocked`，**不再**出现“日期 ”、“银行流水标识 ”、“S001（）”、“关联原付款  / 原分摊 ”或“未在标准化记录中找到”后继续 READY 的情形。
- 对照：MAIN 中 R03 的两种**合法**缺失（未填写关联／所填标识不在提供的台账）仍照常生成底稿（`LAWFUL_MISSING_PAYABLE_STILL_READY`），未统一阻断。
- 隔离方式与原 N8／N9 一致：仅同步**新内存对象**的绑定值（保存同步后的 normalized 指纹）以进入本层字段核验；**不重新复核**，不声称不完整对象真实通过了复核，也不声称抵御篡改；不改任何旧文件。

## 8. 原有回归保持

- 21 组正常输入、34 条线索、168 个来源实体出现项、11 个退款出现项、MAIN 12 条与全部金额口径不变；`hit_key`／`amounts_cents`／`related_ids`／`source_rows`／完整 `evidence` 与筛查报告仍逐项精确相等。
- 原 9 项负向（含复核不一致、复核后改动筛查／标准化、维度 false、缺维度、非开发态、不支持截至日、缺必需金额、缺来源 `cells`）与 6 项格式化检查全部保留并通过；6 项必需字段检查为**新增**，原负向未删除或放宽。
- 确定性（同输入两次返回对象相等、三入参指纹不变）、正文／JSON 逐卡一致、不可信文字仅作数据展示、运行期守卫下文件读取 0 次与静态无上游／答案册／LLM／QA 引用均保持。

## 9. 历史保护对照

- TASK-008 验收基线（`data/reviews/task008_20261011_083855/source_hashes_after.json`）：记录项 **12867**、变化 **3**（`scripts\build_demo_fact_packet.py`、`tests\test_build_demo_fact_packet.py`、`docs\FACT_PACKET_GUIDE.md`）、缺失 **0**。
- TASK-007-R2 的 **12546**、任务六 R1 的 **10236**、任务五 R2 的 **8547**、任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874**：均 **0 变化、0 缺失**；TASK-008 的既有容器与 GPT 证据逐文件核对未变。
- 测试内建核验的 **16 个受保护文件**前后哈希一致。
- 依赖未变（Python 3.11.1、SQLite 3.39.4、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 10. 失败尝试与修正过程

1. **`record` 再次被循环变量覆盖**：F01 检查里 `record = payments_index.get(payment_id)` 覆盖了报告函数 `record()`，运行到 `PAYEE_PER_PAYMENT` 报 `TypeError: 'dict' object is not callable` → 改名 `payment_record`（并复查全文件仅此一处同名赋值）。
2. **付款行断言写法**：最初用“`- 原付款主表：{id}，实际收款对象 …`”整行前缀匹配，但真实行中间还有日期／状态／流水标识 → 改为**先取该付款那一行**再在该行内断言收款对象（避免全篇字符串搜索）。
3. **S5 特殊 ID 转义**：`0003`／`0004` 等用例的收款对象 ID 在正文按 Markdown 转义口径显示，原始子串匹配失败 → 预期文本改用同一转义口径；JSON 侧的独立原值比对不受影响。
4. **六项必需字段探针一度被指纹拦下**：同步 normalized 指纹会改变筛查对象指纹，`crosscheck.screening_report_sha256` 未同步，导致 P3—P6 先被绑定检查阻断而非字段检查 → 同步顺序改为“改对象 → 写 normalized 指纹 → 重算筛查指纹 → 写回复核声明”，六项均落到字段核验。
5. **合法缺失对照的中文排序**：`sorted()` 按码位排序（“所填标识不在提供的台账”在“未填写关联”之前），原断言顺序写反 → 按实际排序修正。
6. 未通过放宽断言、删除原负向、改写观察报告或修改上游数据让样例通过；未导入 GPT QA 到生产核心。

## 11. 偏差、未解决问题与停止状态

- **偏差**：`context.payments[*].payee_supplier` 取代原组级 `payee_supplier`（形状已在指南 §3.1 固定）；正文金额标签为中文并附原字段名（指南 §3.2 固定映射）；`net_total` 按规则区分标签；packet 增 `amount_labels` 说明字段（不改动任何既有字段与数值）。
- **未执行（不主张通过）**：任务九、正式契约／审批／状态机／Gate、人类判断保存、后置 AI 建议、UI／网页、真实 ERP、OCR、RAG、压力测试；未重跑任务二至七整套历史测试。
- **已知限制**：数据库哈希只是上游报告声明值，展示层未读取或重验数据库字节；不证明来源真实性，不抵御同权限篡改；命中是待核实线索，跨规则金额不相加称为损失，整笔口径不能替代本条分摊口径；两套实现一致不构成审计结论，也不替代人类独立判断。
- **停止状态**：未接入 `data/batches`、未修改 `batch_manifest.json`、未建立契约或批准控制、未批准 Gate、未生成 AI 建议、未替人类填写判断、未推进任务九。
- 等待主理人把本回执与 `docs\FACT_PACKET_GUIDE.md`、`data\fact_packet_tests\task008_r1_04\cases\MAIN\fact_packet.md`、`data\fact_packet_tests\task008_r1_04\cases\S3_payee_diff_with_overpay\fact_packet.md`、`data\fact_packet_tests\task008_r1_04` 转交总架构师复验。
