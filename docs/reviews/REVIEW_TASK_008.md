# TASK-008 验收：证据保留正确，展示及必需字段检查需修复

日期：2026-10-11。验收端：GPT。结论：**CHANGES_REQUIRED**。暂不推进任务九。

21组输入的原始命中事实、金额、完整来源和退款摘要均准确保留。但一条正常 R02 底稿显示了错误的收款对象，部分展示必需信息缺失后仍返回 READY。两处属于展示层正确性问题，上游计算无需改动。另随修复统一中文金额标签，并澄清 GPT 上张卡中的不准确措辞。

本轮 GPT 只新增 QA、验收单和修复卡，没有修改实现代码或旧产物。

## 1. 已实际通过的检查

全新容器：`data/fact_packet_tests/task008_gpt_20261011_083855`。重跑提交入口退出0：21组全部生成、34条线索、168个来源实体出现项、11个退款摘要出现项；原10项正向、9项负向及6项格式化检查均符合其断言，测试失败0。

GPT 独立逐条核对新 packet 与冻结筛查输入：hit_key、amounts_cents、related_ids、source_rows、完整 evidence 规范 JSON 精确相等；21份 packet 指纹均正确；以上34/168/11的事实保留差异为0。MAIN 数量和资金勾稽保持原值。

本轮开始时12765个既有文件变化0、缺失0。TASK-007-R2 的12546项基线及10236/8547/6511/4902/874项历史基线全部变化0、缺失0。未重跑任务二至七的独立整套历史测试；本次展示入口只消费冻结输入。

## 2. F01：多收款对象线索复用了第一笔付款的主体（P2，阻断）

`scripts/build_demo_fact_packet.py` 的 `_build_context` 只用 payments[0] 构建一个 payee_supplier；`render_markdown` 对所有原付款复用它。

正常输入 S3_payee_diff_with_overpay 的 R02-0001 中：

- P01 的 payee_supplier_id 为 S001，名称“甲供应商”。
- P02 的 payee_supplier_id 为 S002，名称“乙收款对象”。
- 实际 Markdown 却将 P02 也写成“实际收款对象 S001（甲供应商）”。同一底稿稍后的 R04 又将 P02 正确写成 S002，正文自相矛盾。

GPT 检查了全部正常输出中的59个原付款出现项，发现上述1处错误；该 R02 的 JSON 主体上下文也只覆盖 S001，没有完整表达两笔付款各自的收款对象。原付款 data 和筛查证据本身正确，问题是新增上下文和渲染的关联方式。

必须逐付款按其自己的 payee_supplier_id 关联供应商上下文与来源，不能把第一笔的主体推广到整个 R02 组。测试应从 normalized 独立推导预期主体和名称，检查每条事实卡里的对应付款，而不是只确认 context 具有 data/source/cells。

## 3. F02：中文业务标签及金额措辞澄清（配套修正）

规则金额目前主要显示为 paid_total/refund_total/net_total/overpayment 等代码字段。面向本项目的初学者和业务读者，应改为“已结算付款分摊合计／有效退款分摊合计／净付款分摊合计／超额”等中文名称；原字段继续在 JSON 和指南中保留，不改变金额。

“主表整笔口径，不等于本条分摊金额”会在整笔与分摊都是5000.00元时造成错误的字面含义。此句来自 GPT 上张卡的示例，原卡措辞不准确；本轮明确改为“整笔口径，不能替代分摊口径”，两者数值可以相等。这项澄清不单独否定执行端按原卡实现的工作。总览“净资金额”也统一为“资金净额”。

## 4. F03：必需信息缺失被显示为空白或跳过，仍返回 READY（P2，阻断）

原卡要求缺展示必需字段时 FactPacketBlocked、不补零/猜测/略去线索。当前使用 `.get()`、空字符串和 not_found 继续渲染，消费字段检查未覆盖实际读取的所有关键值。

GPT 在 C06b 的新内存副本上，分别测试六项单独缺失：

1. 退款摘要的 original_payment_id：底稿显示“关联原付款  / 原分摊 A02”。
2. 退款摘要的 original_allocation_id：显示“关联原付款 P02 / 原分摊 ”。
3. 原付款 P01 的 payment_date：显示“日期 ”。
4. 原付款 P01 的 bank_reference：显示“银行流水标识 ”。
5. 供应商 S001 的 supplier_name：显示“S001（）”。
6. 删除必需的原付款 P01 标准化记录：显示“未在标准化记录中找到”，然后继续出 READY。

六项均返回 DEV_FACT_PACKET_READY，应为 FactPacketBlocked，指出缺失字段或必需关联对象。与合法 R03“应付未填写／不在台账”不同，已引用原付款、分摊、退款及所需主数据不能静默缺失。

这些测试与提交入口的 N8/N9 一样，为隔离消费字段核验，仅同步测试内存对象的绑定值；没有重新执行复核，也不声称不完整对象真实通过了上游核验，更不声称抵御恶意篡改。所有旧对象、工作簿和数据库均未修改。本层只需检查实际消费的字段/上下文，不要求重建规则计算器或完整 ERP checker。

## 5. 证据和命令

证据目录：`D:\harness work\audit_sa_project\data\reviews\task008_20261011_083855`。

- regression_execution/stdout/stderr：真实回归命令、退出码、完整输出。
- facts_and_sources.json：独立核对21/34/168/11及指纹。
- payee_display_checks.json、payee_context_checks.json：59个付款出现项的预期/实际及缺失上下文。
- required_field_probes.json、P01—P06.input/result.json：六个完整缺字段输入与实际 READY 返回，包括完整 Markdown。
- protected_files_comparison.json、acceptance_summary.json、source_hashes_after.json：保护结果、机器结论与 R1 冻结基线。

实际回归命令：

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_build_demo_fact_packet.py' --out-dir 'D:\harness work\audit_sa_project\data\fact_packet_tests\task008_gpt_20261011_083855'
```

GPT 实际运行新的 run_review.py、independent_review.py、finalize_evidence.py，退出均0；独立脚本额外调用构建核心6次。QA退出0表示证据采集/核验完成，不能解释为六个缺字段案例通过了验收。

## 6. 下一步

将本验收单与 `docs/tasks/TASK-008-R1.md` 一起交给 DeepSeek。只修展示层上下文、中文口径和消费前提，保留原证据及上游代码。修复后 GPT 复验。

主理人本轮无需手工测试、填写判断或批准 Gate；任务九、正式契约/状态机、人工判断保存和 AI 建议仍未开始。
