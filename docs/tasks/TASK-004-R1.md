# TASK-004-R1：局部补齐报告对照与 API 错误分类

日期：2026-10-11。执行端：DeepSeek；GPT 负责验收；主理人负责转交。

## 1. 当前结论和边界

任务四主体转换已得到实际验证：原 32 个输入全部符合预期，另行核对 18 份成功结果的 20621 个字段，金额、类型、原值和来源坐标均吻合。不要重写标准化器，不重做合成数据。

当前只有两类验收缺口：报告漏分组／完整净额不一致仍能成功；部分文件错误没有转成公共 API 约定的 NormalizationError。先读取 docs/reviews/REVIEW_TASK_004.md，再按本卡局部修复。

项目：D:\harness work\audit_sa_project

解释器：D:\harness work\audit_sa_project\.venv\Scripts\python.exe

只允许修改：

- scripts/normalize_demo_data.py
- tests/test_normalize_demo_data.py
- docs/NORMALIZATION_GUIDE.md

只允许新增：

- docs/EXEC_REPORT_004_R1.md
- data/standardization_tests 下全新测试容器及其输入副本、报告、日志、结果。

其余全部只读：包括 checker、接收器、生成器、旧测试、规格、契约草案、任务卡、全部旧回执／评审／证据、既有数据及批次。不要修改旧 EXEC_REPORT_004.md 来覆盖问题，不修改 GPT 的 probe。

不安装依赖、不初始化 Git、不接入 data/batches、不做 SQLite 或筛查、不建立正式契约、不批准守门点、不推进任务五。

## 2. 修复 A：只补本层消费的报告核对

继续复用接收器 validate_report，在新标准化模块中补充它没有覆盖、而本层需要的字段。无需改冻结接收器，也无需设计完整通用 schema 框架。

### 2.1 缺失和类型错误须明确阻断

在使用前检查以下内容：

- amount_summary.payments_by_type_and_status 必须存在且为对象。每个实际分组条目必须为对象；本层核对的 count、known_valid_amount_cents、complete_amount_cents 必须存在且为整数，bool 不算整数；质量通过时完整金额不可为 null。
- reconciliation.complete_totals_cents 必须为对象，包含 master_net、known_payable_link_net、missing_payable_link_net；本次可转换前提下三项均为整数，不能为 null 或 bool。
- diagnostic_known_valid_subtotals_cents 中本层比较的已知／缺失净额，以及 missing_payable_link_detail 对象内 empty_ap_id、ap_id_not_in_ledger，都须存在且类型可用。

问题报告用 NormalizationBlocked 明确给出字段路径和原因；不能抛裸 KeyError／AttributeError，也不能用默认空对象、默认零绕过核对。只补实际消费字段，不扩展到无关报告栏目。

### 2.2 分组必须双向对照

从标准化付款记录独立形成类型／状态分组，比较它与报告分组的键集合。既检查报告多项，也检查报告漏项；分别核对每组数量、已知金额及完整金额。

报告字段齐全但分组集合或数值与实际数据不一致时，抛 NormalizationError，列出具体分组和差异，不能返回 normalized_equals_report=true。

注意：空分组对象本身不是错误。真实没有任何付款／退款事件且 checker 通过时，实际分组和报告都为空，应正常转换。禁止用“分组必须非空”修复 P02。

### 2.3 对照完整净额

将独立算出的主表净额、已知应付关联净额、缺失关联净额，分别与 reconciliation.complete_totals_cents 的三项对照，同时保留已有诊断小计及缺失分类的对照。

某项差 1 分也必须抛 NormalizationError；不能仅因 known_plus_missing_equals_master=true 或诊断小计一致就略过完整净额。不要自动修补报告数字，不能把原报告数字复制成计算结果。

保留金额单位、逐笔主表／分摊勾稽和原先的标准数据结构。可新增明确的比较项，无需改动既有字段含义。

## 3. 修复 B：文件操作错误遵守 API 约定

normalize_workbook 的运行错误统一按已承诺的 NormalizationError 对外返回，至少覆盖本轮实测的四个位置：

- 初次读取输入字节／哈希。
- 初次读取冻结 checker 哈希。
- 打开工作簿。
- 读取 SPEC 哈希。

继续保留转换结束输入哈希失败／变化的已有处理，不放宽原断言。检查该 API 内的其他同类文件操作，采用一致的局部边界处理；不扩展成新的流程框架。

已知 I/O／工作簿读取错误须保留操作阶段、文件路径和原始异常类型／原因，可用异常链保留原错误。不要直接吞掉所有 Exception 后返回空结果，不将文件读取失败伪装成质量检查通过，也不要把报告内容错误混成文件错误。

本卡针对公共 API 调用内的文件操作，不扩展到部署、插件、并发控制或安全隔离。结果仍是内存返回，失败时不返回成功结果，调用方不得落盘 normalized.json。

## 4. 定点验证和正例

在新容器重跑原 32 个输入，保留已有断言，不再运行任务二／三整套测试。

新增本轮 8 项独立复现的回归案例，可只读参考：

    D:\harness work\audit_sa_project\data\reviews\task004_20261011_051202\probe_normalizer.py

- P01：新有效报告删除 payments_by_type_and_status → 明确 NormalizationBlocked。
- P02：C01 的该对象置为空 → NormalizationError，原因包含报告漏掉实际分组。
- P03：仅将完整 master_net 加 1 分 → NormalizationError，原因包含完整净额差异。
- P04：missing_payable_link_detail 为非空数组 → 明确 NormalizationBlocked。
- P05—P08：分别模拟初始输入读取、工作簿打开、SPEC 读取、checker 读取失败 → 全部为 NormalizationError；保留阶段、路径与原原因，没有标准化结果。

再补少量相邻防回归检查，可复用新输入与新报告的内存副本，不要求重复跑大量 CLI：

1. 主文件报告仅删除 PAY/PENDING 分组，其余分组保留：必须发现漏项；不要只测试整个分组对象为空。
2. 分别把完整 known_payable_link_net、missing_payable_link_net 加 1 分，均须发现；报告完整净额字段缺失／null 也不能成功。可用参数化断言，实际调用数如实统计。
3. 某付款分组只改 complete_amount_cents，使其与实际相差 1 分，必须发现；结构缺失和错误类型可用针对性前提检查验证。
4. 正例：从新 C01 副本移除 payments、allocations 的业务行，保留四表表头、供应商及应付。真实 checker 通过、付款分组为空时仍能正常转换；资金净额为 0，应付金额保留，不强求应付总额等于付款总额。

故障只在内存或新测试副本注入；每份 checker 原始报告留存，故障副本另存或清楚记录修改内容，不能冒称 checker 自己生成了不一致报告。

预期阻断、预期运行错误、测试自身失败分开统计。任何未预期异常、断言失败或文件保护失败使整个测试进程非零。不能靠只断言“抛了任意异常”通过本次检查，须断言约定的具体异常类及差异原因。

输入副本、报告、日志和输出都放在新容器；成功才保存 normalized.json。前后核验冻结文件及本轮原输入，保留基线和结果，不覆盖任何旧现场。

建议命令（已存在换新后缀）：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py' --out-dir 'D:\harness work\audit_sa_project\data\standardization_tests\task004_r1_01'

## 5. 说明、回执及停止

更新 NORMALIZATION_GUIDE.md：补充实际报告对照及错误处理语义；将函数签名和合法调用示例分开；将原“8 个开发小样”改为实际 9 个，并另列本次新增验证，数量按实际结果写。

新增 EXEC_REPORT_004_R1.md：说明两类局部修复、最终哈希、真实命令／日志、原 32 输入及新增案例的实际统计、具体异常类型和对照结果、失败尝试、获准修改和只读保护结果、未解决问题。旧回执保留，不回写。

完成后返回新回执与标准化说明完整路径及简短摘要，等待 GPT 复验。若同一问题三次仍失败或上下文不足，保存实际进度、错误与下一条命令后停止，不自行扩大修改。

主理人当前只负责转交，无需技术复测或模拟批准。修复完成前后均不做 SQLite，不推进任务五。
