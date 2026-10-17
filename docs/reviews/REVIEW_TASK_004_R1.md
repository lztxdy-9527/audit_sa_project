# TASK-004-R1 复验通过：标准化核心冻结

日期：2026-10-11（北京时间）。验收端：GPT。结论：ACCEPTED_DEVELOPMENT_SCOPE。

任务四在当前开发范围内通过，不再要求 TASK-004-R2。报告分组对照、完整净额比较和本轮指定的文件错误分类均已补齐；有效数据转换和来源追溯保持正确。

本结论不构成 Gate 1／Gate 2 批准。正式契约仍为草案，现有接收批次没有被推进。本轮未执行 SQLite。

## 1. 实际回归与独立复现

GPT 在新容器执行：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py' --out-dir 'D:\harness work\audit_sa_project\data\standardization_tests\task004_r1_gpt_20261011_052856'

实际退出 0：47 个输入，19 个转换成功、16 个预期阻断、12 个预期运行错误，测试失败 0；47 次真实 checker CLI。原 32 个输入及本轮 15 个新增案例全部符合预期。

另行复用上轮只读 probe_normalizer.py，对当前版本运行 P01—P08，共 8 次新 checker CLI，不计入上述 47 例：

- P01、P04：缺失状态分组栏目、错误嵌套类型，均明确抛 NormalizationBlocked，并给出字段路径。
- P02：报告分组为空而实际有付款，抛 NormalizationError，指出报告漏掉 PAY/SETTLED。
- P03：完整主表净额差 1 分，抛 NormalizationError，指出 master_net 的实际差异，不再错误返回一致。
- P05—P08：初始输入读取、工作簿打开、SPEC 读取、checker 读取失败，全部为 NormalizationError，保留阶段、路径及原始异常原因。

原始 checker 报告与故障副本分开保存；所有故障仅影响新测试数据或内存，未改真实源码。8 项 requirement_met 均为 true。

## 2. 转换与来源的独立核对

GPT 重新读取新容器全部 19 份成功结果对应的 Excel：共 3133 条业务行、20631 个固定字段。标准值、金额整数类型、目标字段、原值／类型、实际列号、单元格坐标、原行号及工作簿哈希全部吻合。

主文件四表仍为 20／993／1000／1005 行；主表净额 267249329 分 = 已知关联 266249329 分 + 缺失关联 1000000 分。三项完整净额、类型／状态分组、逐笔分摊及已有诊断小计均通过对照。

真实空付款正例仍可转换：保留供应商及 500000 分应付，付款／分摊为空，资金净额为 0。没有将“分组对象不能为空”作为修复办法，也没有强求应付总额等于资金净额。

所有成功结果为 TASK-004-normalized-1.1、DEVELOPMENT_TEST_ONLY、next_step_allowed=false。未删除未知关联、收款对象差异、退款或非结算事件。

## 3. 通过版本与文件保护

SHA-256：

- scripts/normalize_demo_data.py：a2bae49e3686c6bca012fd4207b6a39424e21515b82af8ce8e7c05b276b72310
- tests/test_normalize_demo_data.py：afb1ea647cb3a1b70f847e94f50e78ef1b09464cd8834bfeac708cee6344a7ed
- docs/NORMALIZATION_GUIDE.md：ecd85127f77bea04ac12898cd04ba2385a321ae58890b26e754f95c915f86217
- docs/EXEC_REPORT_004_R1.md：363fe528e50a4735c89d9b91b287ecf38fc7f32eaf22d05af602240b8f38261b

本轮开始前 6511 个已有文件全部未变。相对任务四原验收 5819 文件基线，只有修复卡授权的标准化器、标准化测试及说明三个文件变化；R3 的 4902 文件基线全部未变。无缺失文件。

证据目录：

    D:\harness work\audit_sa_project\data\reviews\task004_r1_20261011_052856

其中 command_log.json 与回归输出记录完整执行；independent_command_log.json 及新测试容器 independent_probes 保存 8 项复现；independent_positive_checks.json、protected_files_comparison.json、acceptance_summary.json 保存转换核对、文件保护和最终结论。

GPT 没有改实现代码，只新增验收证据、本记录及下一张任务草案。

## 4. 验收边界与下一步

报告检查覆盖当前标准化层消费的字段，不宣称完整通用 schema 验证或真实 ERP 适配。原始 Excel 字节仍是原始载体；标准 JSON 是可追溯的开发产物。标准化核心尚未接入正式批次、契约或批准指纹控制。

下一张 docs/tasks/TASK-005_DRAFT.md 只开发 SQLite 装载、往返核对和 SQL 数量／金额勾稽。测试从合成输入制作新副本，重新调用冻结 checker 与标准化器，不推进旧批次，不做 R01—R04。

主理人当前只需转交本验收记录与任务五草案，无需技术复测或模拟批准。
