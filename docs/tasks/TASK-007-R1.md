# TASK-007-R1：修复误报一致与差异诊断

执行端 DeepSeek；验收 GPT；主理人转交。项目根目录：`D:\harness work\audit_sa_project`。

## 1. 当前状态与先读材料

依次读 `docs/reviews/REVIEW_TASK_007.md`、本卡、`docs/tasks/TASK-007_DRAFT.md`、`docs/RULE_CROSSCHECK_GUIDE.md`、`docs/EXEC_REPORT_007.md`。

GPT 已实测正常链路：29 输入、21 MATCHED、8 上游阻断；原 11 差异/5 前提检查通过；另复算 34 条线索、168 个实体均正确。问题在比较和报告边界，不是规则公式。9 个补充探针中有 5 个错误 MATCHED，另有分项状态及诊断值问题，详见验收单。

本卡完成原 TASK-007 尚未满足的要求，不增加业务规则。GPT 没有替你修改实现。不得把 GPT QA 脚本导入生产核心；可以阅读其探针输入和实际结果理解问题。

## 2. 允许修改和新增

只允许修改：

- `scripts/crosscheck_demo_rules.py`：限定为比较、前提核对及报告修复，版本升为 `TASK-007-crosscheck-1.1`。
- `tests/test_crosscheck_demo_rules.py`：增加本卡回归及结构化留痕。
- `docs/RULE_CROSSCHECK_GUIDE.md`：准确说明修复后的接口、比较、状态、差异及限制。

只新增 `docs/EXEC_REPORT_007_R1.md` 和 data/sqlite_tests 内全新测试容器。既有 EXEC_REPORT_007、所有任务卡/验收单/GPT 证据及其余历史文件不变。上游筛查核心、四份 SQL、装载/标准化/checker、规格和答案册均不得修改。不安装依赖，不初始化 Git。

## 3. F01：严格类型比较

凡规格声明为整数分的字段，只允许 int 且非 bool。观察报告中的等值 float、bool 必须产生对应维度的 MISMATCH，不转换或舍入后再比较。

覆盖所有金额：amounts_cents 标量及 R01 net_per_payment、退款摘要金额、statistics 中资金金额、overall_reconciliation 金额和明细。计数、原 Excel 行号、布尔计入标志也按各自类型比较。声明为字符串的 ID 保持原类型和值，不能用 map(str) 或 str(value) 将类型差异抹平。

保留原 AMOUNT_MISMATCH / STATISTIC_MISMATCH / REFUND_FACT_MISMATCH / RECONCILIATION_MISMATCH 等维度代码，必要时附 expected_type/actual_type。不能改成容差比较，也不能通过修改计算金额或把 float 转 int 让报告一致。

至少增加以下真实核心调用：MAIN 的 R02 overpayment 改成等值 float；R01 net_per_payment 的一个值改成等值 float；S6 的整笔付款金额统计 0 改为 false。均须 MISMATCH 并指到对应字段，不能 MATCHED。

## 4. F02：退款多重性和规则身份

### 4.1 退款摘要

先核对 related_refunds 元素结构、退款分摊 ID 和多重性，再建立索引比较。对同一 refund_allocation_id 重复出现不能静默覆盖后通过；不能过滤掉非法元素后假装列表完整。

重复可以使用 REFUND_FACT_MISMATCH 并记录 ID/实际次数，也可增加明确的 REFUND_FACT_DUPLICATE 代码并同步说明。记录原观察列表问题，不直接去重修复输入。

增加 C09b 原样追加退款摘要的调用，必须 MISMATCH。另验证把同一摘要复制后改动其中一份，也不能依赖“字典最后一条”遗漏差异或返回 MATCHED。

### 4.2 规则身份

finding.rule_id、hit_key.rule_id 以及该复算事实的规则必须一致。增加仅将 MAIN 一条 R01 finding 的外层 rule_id 改成 R04 的调用，必须明确 MISMATCH 或 CrossCheckBlocked，不能 MATCHED。说明固定的处理方式及代码；如果选择阻断，将其分类为结构/身份前提，不伪装成已执行差异比较。

保留原漏报/多报/命中重复逻辑。不要在规则身份比较中丢弃整个观察项或重写其 rule_id 来消除冲突。

## 5. F03：状态与诊断要能准确使用

分清“执行过检查”和“该维度一致”。不要继续把所有 comparison.checks 无条件写 true。可采用：

```text
comparison.dimensions.<维度> = {executed: true, matched: false, difference_count: N}
```

也可采用同等明确结构，但必须在说明中固定；该维度存在差异时 matched 为 false。整体 matched=true 仅限所有已要求维度一致且 differences 为空。已有 checks 若保留，必须明确其含义，不能继续造成“金额差异但金额检查通过”的表达。

差异 code/hit_key/field_path/expected/actual 保留并准确：

- 缺失使用明确可序列化的标记或 present=false 元数据；显式 null 仍为 null，0 仍为 0。删除字段和将字段设 null 必须得到可区分的记录。
- 完整 cells 不同时，要保存可定位的实际值。可以逐叶字段输出差异，也可以在 cells 路径保存完整 expected/actual 对象；不可再写 expected="完整 cells" / actual="与标准化记录不一致" 等替代值。
- 所有差异稳定排序并保存完整内容，不能只存第一条或在结构化结果中静默截掉差异。

验证：原 M4 金额加 1 分时金额维度不一致、无差异的其他维度正确；删 overpayment 与设 null 分别保存并证明记录不同；原 M7 cells.raw_value 改动时，新差异可读出原值和改后值；同一报告同时有两处不同维度改动时，两处都留痕、分项状态都不一致。

复核器继续只输出确定性事实和差异，不生成审计结论、等级或判断预填。

## 6. F04：质量前提不能自相矛盾

冻结标准化契约的 quality_report 必须是 pass 且没有未解决问题。当前合法输出的 issue_counts_by_code 为 `{}`；本版明确要求该字段存在、为对象且为空。不把缺失、非对象、含问题计数当作无问题。

增加至少一个隔离该前提的用例：normalized 保持 result=pass，将 issue_counts_by_code 改为 `{"FOREIGN_KEY_MISSING":1}`；测试侧同步 screening_report.load_source 和 run_metadata 的 normalized_payload_sha256，使之不在指纹层提前阻断。必须 CrossCheckBlocked，原因指向质量前提。

指纹同步仅作用于新内存测试对象，保存设置和结果；不得修改原文件或声称实现防恶意篡改。此次不重建完整 ERP checker，不放宽既有绑定和范围检查。

## 7. 完整验证与保护

全新容器完整重跑原 29 工作簿、原 11 差异、原 5 前提、确定性和隔离，再运行本卡新增检查。正常 21 输入仍 MATCHED，8 输入仍上游阻断；34 条线索和 168 个完整实体保持原事实；主文件仍 12 键和 R02 超额合计 1600000 分。

保持生产核心只有两个内存入参，不读数据库/Excel/规则 SQL/答案册、不调用上游算法、不修改入参或旧报告。原“所有初次结果保存后才读取答案册”的顺序不变。金额测试修改报告，不重新制造工作簿质量问题来回避比较。

新增调用与原 40 次复核调用、29 个工作簿分开统计；预期 MISMATCH/Blocked 不算测试失败，不写成 MATCHED；表明每项实际进入的比较或前提阶段。入口退出 0 只表示所有断言符合预期。

每个被修改的报告/标准化对象、完整复核报告或阻断原因、预期/实际代码、分项状态、入参指纹/数据库保护结果均保存新结构化文件；stdout/stderr 全量捕获。summary 与明细互相可核对，不用局部变量存在或口头说明代替留痕。

扩充保护基线：

`data/reviews/task007_20261011_074219/source_hashes_after.json`

除本卡允许的三个既有文件外，其余变化/缺失均为 0；任务六 R1 的 10236 文件冻结基线必须全部不变。GPT 证据目录也保持原字节。无需重跑上游整套历史测试，新链路调用冻结 API 并核对哈希。

新 EXEC_REPORT_007_R1 写明四项缺口、改动范围/完整哈希、真实命令/退出码、分类计数、各项新旧回归和分项状态、历史保护、所有失败尝试及未执行内容。旧 EXEC_REPORT_007 不回写。若发现新的规格矛盾，明确记录并停止受影响部分，不调整规则或答案消除差异。

## 8. 停止

完成后返回 EXEC_REPORT_007_R1.md、更新后的 RULE_CROSSCHECK_GUIDE.md 和新容器路径，立即停止等待 GPT 复验。

不推进任务八、不接入 data/batches、不改 batch_manifest、不建立正式契约/批准控制、不批准 Gate、不生成事实展示 UI/判断表/AI 建议。主理人只负责转交验收单与本卡，无需手工检测或模拟批准。
