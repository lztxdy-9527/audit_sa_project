# TASK-004 验收：转换正确，需局部补齐报告核对和错误接口

日期：2026-10-11（北京时间）。验收端：GPT。结论：CHANGES_REQUIRED。执行 TASK-004-R1，不推进任务五或 SQLite。

标准化主体已完成：本轮未发现有效输入的金额转换、文本保真、业务行保留或单元格来源错误。返修集中在两个边界：报告对照不完整，以及部分运行错误未按公共 API 的异常约定返回。无需重写转换器或重做合成数据。

## 1. 已通过的实际验证

GPT 在新容器执行：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py' --out-dir 'D:\harness work\audit_sa_project\data\standardization_tests\task004_gpt_20261011_051202'

实际退出 0：32 个输入，18 个转换成功、12 个预期阻断、2 个预期运行错误，测试失败 0；32 次真实 checker CLI。主文件及 22 份 fixture 的结果与任务卡一致。

GPT 对新容器内全部 18 份成功输出另行读取原 Excel，按实际表头、原行号和原单元格核对，而不是仅信任 normalized_equals_report：共 3130 条业务行、20621 个固定字段，标准值、金额 int 类型、目标字段、原值类型／编码、来源坐标及工作簿哈希全部吻合。

主文件仍为 20／993／1000／1005 行；主表净额 267249329 分 = 已知关联 266249329 分 + 缺失关联 1000000 分。小额 0.10 + 0.20 精确为 30 分；未知关联、收款对象差异、退款和非结算记录均保留。开发模式及 next_step_allowed=false 未改变。

## 2. 问题 A：报告对照遗漏，可错误宣称一致（P2，阻断验收）

主要位置：scripts/normalize_demo_data.py 第 127、365—509 行，尤其第 412 行分组循环及第 475 行附近的勾稽对照。

接收器 validate_report 检查的是接收入口所消费的字段。标准化层新增消费的付款分组和嵌套金额，需要在新模块中补齐检查；不能要求修改已冻结的接收器。

GPT 在每个新案例中真实运行 checker，对新报告的内存副本进行明确故障注入，原始 checker_report.json 保留：

- P01：删除 amount_summary.payments_by_type_and_status，实际抛 KeyError，未形成约定的明确阻断错误。
- P02：将该分组对象置为空，而 C01 实际有一笔已结算 PAY，函数仍返回成功且 normalized_equals_report=true。原因是只遍历报告里存在的分组，报告漏项时没有反向比较。
- P03：仅将 reconciliation.complete_totals_cents.master_net 从 500000 改成 500001 分，函数仍返回成功、计算净额为 500000、normalized_equals_report=true。程序核对了部分诊断小计，没有对照报告的完整净额。
- P04：将 diagnostic_known_valid_subtotals_cents.missing_payable_link_detail 换成非空数组，实际抛 AttributeError。

P02、P03 不表示正常数据金额算错，而是“已经与报告核对一致”的声明不成立。后续入库不能依赖这个未经完整对照的成功标记。

修复应限于标准化层实际消费的报告字段和对照：分组双向覆盖、相关嵌套类型、完整净额三个字段的比较。真实无资金事件时分组为空可以合法，不能一律禁止空对象。

## 3. 问题 B：公共 API 的文件错误分类不完整（P2，阻断验收）

主要位置：normalize_workbook 第 526—530、563 行；sha256_file／spec_sha256 等调用边界。

回执和说明承诺运行／文件读取错误为 NormalizationError。四个独立模拟的实际结果为：

- P05：输入初次字节读取失败，裸 OSError。
- P06：初次哈希成功后，打开工作簿失败，裸 PermissionError。
- P07：读取 SPEC 哈希失败，裸 OSError。
- P08：读取冻结 checker 哈希失败，裸 OSError。

这些情况没有错误返回标准数据，问题是调用方无法按已约定的异常类型记录和处理，当前测试驱动也会被这种未分类异常直接打断。应在本 API 的文件操作边界保留阶段、路径和原始异常原因，再转为 NormalizationError；不隐藏程序错误，不返回默认成功结果。

## 4. 说明的顺手修正项（非独立阻断）

- NORMALIZATION_GUIDE.md 第 1 节调用示例把类型注解和返回注解放进调用表达式，不能作为 Python 执行。函数签名与实际 result = normalize_workbook(workbook_path, quality_report) 调用须分开。
- 第 6 节“8 个开发小样”应为实际 9 个：23 个主文件／fixture 输入 + 9 个小样 = 32。旧 EXEC_REPORT_004.md 不回写，在新回执说明修正。

## 5. 版本、证据与文件保护

当前被验收版本 SHA-256：

- scripts/normalize_demo_data.py：a1c4aa23ac88df77f4bc8736ba3989128ea95e537bf019062a364853d399fde4
- tests/test_normalize_demo_data.py：4bf41b3d9581760d2ef2c1df2b70e9515bcf0c47e4cc54b7eb78c4c14e724b64
- docs/NORMALIZATION_GUIDE.md：9e6ae4d8e0cc88afc05c946878bed3dee5595ebc2d4f8e47e96e271825ee87b1
- docs/EXEC_REPORT_004.md：0a2c21072506f2955a59ffbc3a0f508ae89ce587b912eb15c7fdb1dcb4dd9b36

证据目录：

    D:\harness work\audit_sa_project\data\reviews\task004_20261011_051202

包含回归命令及输出、independent_positive_checks.json、独立 probe_normalizer.py、independent_command_log.json、文件保护对照及 acceptance_summary.json。独立故障现场在新测试容器的 independent_probes：8 次新 checker CLI，逐案保存真实报告、注入后报告、调用日志和实际结果，不计入原 32 例。

probe 驱动退出 0 仅表示观察已收集；每案 requirement_met=false 明确记录验收失败，不能把驱动退出码当作产品通过。

本轮开始前 5819 个已有文件均未变；R3 基线 4902 个、任务二基线 874 个均无变化或缺失。GPT 未改实现代码，只新增验收证据和两份评审／修复文档。

## 6. 下一步

把本记录和 docs/tasks/TASK-004-R1.md 全文转交 DeepSeek。只补上述两类边界与相关验证，保存新回执 EXEC_REPORT_004_R1.md 后停住。主理人无需技术复测，也无需现在批准 Gate 1／Gate 2；暂不出任务五。
