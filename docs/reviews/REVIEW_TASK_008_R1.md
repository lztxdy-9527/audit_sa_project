# TASK-008-R1 验收单

日期：2026-10-11；验收：GPT；结论：**通过开发验收，可以领取 TASK-009。**

本结论只验收事实底稿模块及本次三项修复，不批准业务批次的 Gate，不代表审计判断或正式契约生效。GPT 未修改实现、开发测试、指南或历史产物。

## 1. 本次复验结果

在全新容器 `data/fact_packet_tests/task008_r1_gpt_20261011_090417` 实际运行项目 Python 3.11 的验证入口，退出0、测试失败0。

- 21个输入生成21份底稿；34条线索、168个原来源实体出现项、11个退款摘要出现项不变。
- 正向14项；原负向9项全部阻断；新增必需字段6项全部阻断；格式化6项。入口记录构建API 41次，格式化helper 1184次，两者分开计数。
- GPT另调用构建API 6次复现旧缺口，六项均为 `FactPacketBlocked`，不是 READY，也不是意外运行错误。

GPT独立读取新产物与冻结的 normalized/screening 对象，核对命中键、整数分、相关ID、来源行、完整entities/cells与退款摘要，21份均精确一致；packet指纹亦一致。

## 2. 三项修复关闭

**F01关闭：逐笔收款对象。** 从 normalized 中独立关联每笔付款及其供应商，核对 `context.payments[*].payee_supplier` 的ID、data、source、cells，以及对应付款正文行。59个原付款出现项无错配、无缺项；不再存在旧组级单一收款对象。S3的R02内P01为S001（甲供应商），P02为S002（乙收款对象），与R04一致。

**F02关闭：中文金额及口径。** C06b同一R02事实卡明确显示应付5000.00元、付款分摊10000.00元、退款分摊1000.00元、净付款分摊9000.00元、超额4000.00元，并保留原字段名。新口径为“不能替代本条分摊口径；两者数值可以相等”；“净资金额”旧字样消失。上轮任务卡中“不等于”的不准确措辞也已澄清。

**F03关闭：必需字段阻断。** 删除退款摘要的original_payment_id/original_allocation_id、原付款的payment_date/bank_reference、supplier_name、被引用P01记录，均得到含字段或对象路径的明确阻断。GPT探针只同步新内存对象的绑定值以隔离消费层检查，没有重新复核，不能据此宣称不完整对象真实通过复核。合法R03空关联及台账外标识仍正常生成。

## 3. 文件保护

复验开始时13213项现存文件全部未变、未缺失。上轮TASK-008基线12867项，仅下列三项获准变动：

- `scripts/build_demo_fact_packet.py`：f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62。
- `tests/test_build_demo_fact_packet.py`：46d426e7c262f3b5c773ba6717e5b3e002c34783d11d24a5bd3c43b80effeb36。
- `docs/FACT_PACKET_GUIDE.md`：48c051be9bfca3659560c73e4693892ecd1a72629fba7401698eb87f8657ff9d。

12546、10236、8547、6511、4902、874项历史基线均0变化、0缺失。新回执和新测试目录作为新增产物保留。

非阻断文档记录：指南页首已为1.1，但第3节packet字段表仍写1.0；实测JSON及Markdown均为 `TASK-008-fact-packet-1.1`，以后者为当前接口。此处不要求单独修订轮次，不授权下一任务顺手修改冻结指南。

## 4. 证据和下一步

GPT证据：`data/reviews/task008_r1_20261011_090417/`。主要文件：regression_execution、facts_and_sources、payee_display_checks、payee_context_checks、required_field_probes、chinese_and_legal_missing_checks、protected_files_comparison、acceptance_summary，均为JSON；实际回归stdout/stderr完整保留。

独立核对与新增探针不替代上游整套测试；本轮未重跑任务二至七整套测试，没有生成AI建议或人类判断。

下一张卡为 `docs/tasks/TASK-009_DRAFT.md`：开发态Gate流程控制内核。先验证暂停、模拟决定、材料绑定及禁止越级，再另行接入真实批次入口。主理人本轮只需转交本验收单和任务九卡片，不需检测、签Gate或预填判断。
