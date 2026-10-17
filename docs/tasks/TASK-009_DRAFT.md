# TASK-009：开发态 Gate 1／Gate 2 流程控制内核

执行：DeepSeek；架构及验收：GPT；主理人负责转交。根目录：`D:\harness work\audit_sa_project`。

## 1. 先确认现状，避免执行旧卡

先读 `docs/reviews/REVIEW_TASK_008_R1.md`、本卡、`docs/AUDIT_CONTRACT_DRAFT.md` 第2—6节、`docs/BATCH_RECEIVE_GUIDE.md`、`docs/NORMALIZATION_GUIDE.md`、`docs/SQLITE_LOAD_GUIDE.md`。任务一至八已通过开发验收，不重做旧任务或旧修复。

现有模块已能完成合成Excel核验、标准化、装载、筛查、独立复算和事实展示。尚未有正式契约或批次批准控制。底稿现版本为 `TASK-008-fact-packet-1.1`，不要采用指南字段表残留的1.0。

本次只实现**纯内存的开发态两处守门控制**。实务对应：收到ERP导出后先停在范围/接收核验；标准化及数据库勾稽后再停一次。只有在测试中收到明确的模拟人类决定，才允许模拟下一阶段。不是在旧结果上补签真实批准，也不串行运行全部上游。

全部状态必须保持 `mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed=false`、`contract_status=DRAFT_NOT_IN_FORCE`；真实 `gate1_approval`、`gate2_approval` 始终为null。模拟决定另列，明确标记 `SIMULATED_TEST_ONLY`，不得冒充实际主理人行为。

## 2. 允许新增与冻结范围

只新增：

- `scripts/control_demo_workflow.py`：纯Python API，标准库。
- `tests/test_control_demo_workflow.py`：开发验证入口。
- `docs/WORKFLOW_CONTROL_GUIDE.md`：协议、状态、守门材料、例子、边界及后续接入条件。
- `docs/EXEC_REPORT_009.md`：真实执行回执。
- `data/workflow_tests/` 下全新测试容器及产物。

冻结全部既有文件，包括脚本、测试、SQL、规格、契约草案、指南、回执、数据库、输入、答案册及GPT证据。不得改旧batch_manifest、接入data/batches、建立AUDIT_CONTRACT.md/AGENTS.md、装依赖、初始化Git或做UI。不要修订底稿指南的非阻断文案记录。

保护基线为 `data/reviews/task008_r1_20261011_090417/source_hashes_after.json`，全部0变化、0缺失；12546/10236/8547/6511/4902/874项历史基线亦不变。

## 3. 固定公共接口与数据协议

固定四个API；具体参数注解可细化，名称和职责不可变：

```python
create_dev_workflow(batch_id, run_bindings) -> dict
prepare_dev_gate(workflow, gate, materials, *, current_bindings) -> dict
record_dev_decision(workflow, decision, *, current_bindings) -> dict
check_dev_action(workflow, action, *, current_bindings) -> dict
```

前三个返回 `{state, state_sha256}`；第二、三、四个接收同形workflow对象。规范JSON指纹与上游一致：ensure_ascii=False、sort_keys=True、separators=(",", ":")、allow_nan=False，UTF-8 SHA-256。state_sha256放外层，避免自引用。

核心不读写文件/数据库/Excel，不读取答案册、不导入上游或测试/QA、不调用LLM/网络/子进程。时间与batch_id由调用方传入，不自动取当前时间或生成随机身份。不得修改入参；同输入同返回。前提/协议/不允许的转移抛 `WorkflowBlocked`，字段及原因清楚；意外错误抛 `WorkflowError`并保留异常链。

run_bindings至少含：input_sha256、spec_sha256、contract_draft_sha256、code_sha256（本控制器及接收/checker/标准化/装载/筛查/复算/底稿的逐文件哈希）、rule_sql_sha256（R01—R04）、config（公司、期间、截至日、币种）。哈希必须为完整64位十六进制字符串；配置固定本项目单公司/2026年9月/CNY范围；标识符保留原字符串，不转int、不strip改值。批次ID及人为说明可用strip判断空白但保存原值。

每次后续调用核对current_bindings与创建时的完整规范对象严格相同、workflow外层指纹正确，以及state阶段与历史事件顺序相符。不能仅信任调用方填写的phase。任何绑定变化或缺失都阻断，提示建立新workflow/新批次，不复用旧模拟批准。此层只核对调用方提交的内存声明，**不宣称实读了当前磁盘字节**；后续入口必须负责提供实测绑定。

state保存版本 `TASK-009-workflow-control-1.0`、原batch_id、run_bindings及指纹、phase、两处request、模拟决定和有序history。history记录递增序号、事件类型、gate、材料/请求指纹、完整决定及前后状态；新返回对象保留旧事件，不覆盖历史。重复事件、重复决定、冲突决定、缺失关键字段和类型错误要明确阻断。不要增加数据库/文件持久化或声称历史不可篡改。

## 4. 状态、材料与模拟决定

正常顺序固定：

```text
DEV_CREATED
  → DEV_GATE1_PENDING
  → DEV_GATE1_APPROVED
  → DEV_GATE2_PENDING
  → DEV_GATE2_APPROVED
```

仅create能创建首态，prepare分别从CREATED/GATE1_APPROVED建立对应request并进入PENDING，record仅处理当前PENDING的决定。HOLD/REJECT进入该Gate的 `DEV_GATE1_HELD/REJECTED` 或 `DEV_GATE2_HELD/REJECTED`，本版本均为停止态，不能改成批准或继续；需要补证/修订时新建workflow并保留旧记录。Gate2请求绑定Gate1已批准的**模拟决定指纹**，不能拿另一个workflow的Gate1记录解锁。

materials是结构化守门材料，不能只交一个“passed=true”。共同必需：batch_id、gate、run_bindings_sha256、scope、blocking_issues、evidence。scope含公司/期间/截至日/CNY/合成数据标志、来源描述及已知限制；未知来源和完整性是声明限制，不用哈希推导真实性。blocking_issues为列表，非空不生成可批准请求。

Gate1的evidence包含完整quality_report。至少检查result严格为pass、issues存在且为空列表、issue_counts_by_code存在且为空对象、workbook.sha256及checker.sha256与run_bindings对应；不复制checker的22字段核验算法。结构、范围或核验失败不能靠传空blocking_issues绕过。scope与固定范围一致，来源描述非空，但不要求把未知导出条件伪造为已知。

Gate2的evidence包含完整normalized和load_report。至少检查两者开发态及next=false、版本分别TASK-004-normalized-1.1与TASK-005-sqlite-load-1.2/schema demo-schema-1.0、normalized质量pass且issue_counts_by_code存在且为空、source.input_sha256一致、load_report.normalized_payload_sha256等于实际normalized规范指纹、状态DEV_SQLITE_VERIFIED、round_trip_exact/event_allocation_balanced严格true、foreign_key_check为clean、integrity_check为ok、net_checks必需六项齐全且严格true。六项为master_net_equals_known_plus_missing、master_net_equals_normalized、known_net_equals_normalized、missing_net_equals_normalized、empty_ap_id_equals_normalized、unknown_ap_id_equals_normalized。

核对守门展示消费的四表row_counts与normalized记录数量一致，付款/退款主表及分摊总额、master_net/known_payable_link_net/missing_payable_link_net为整数分（非bool），与normalized.amount_reconciliation相应字段一致，且主表付款=付款分摊、主表退款=退款分摊、master_net=known+missing。不得用“缺失应付关联非零”阻断正常R03，也不把入库勾稽成功称为无业务异常。不重做装载器全部逐条校验或增加第三套规则计算。

request保存完整materials及其规范指纹；request_id由本workflow批次、gate、绑定指纹、材料指纹及Gate2前序模拟批准指纹确定性生成。决定必须引用当前request_id、gate、batch_id、materials_sha256，字段全部核对。不能只按“Gate1已批准”字符串放行。

decision必需：event_id、batch_id、gate、request_id、materials_sha256、decision（APPROVE/HOLD/REJECT）、actor_kind固定SIMULATED_HUMAN、actor_id、occurred_at（带时区的ISO日期时间）、reason、simulation标志固定SIMULATED_TEST_ONLY；均显式传入且类型严格。APPROVE还须提供对应的confirmations：Gate1为scope_and_source_reviewed严格true，Gate2为reconciliation_reviewed严格true。HOLD/REJECT不要求确认成功，但必须有说明。AI/SYSTEM、未标注模拟、无说明、空白身份、错误请求/材料、把1当true等均不得被接受。

模拟actor仅是可检查的身份声明，不提供真实人类认证。核心没有正式批准接口；测试之外不得让AI填写这些对象来解锁真实批次。

## 5. 行为检查与实务例子

check_dev_action至少支持NORMALIZE_AND_LOAD、SCREEN_AND_BUILD_FACTS、GENERATE_AI_SUGGESTION。返回明确action、phase、`simulation_allowed`（严格bool）、原因、绑定指纹，并固定next_step_allowed=false。

- NORMALIZE_AND_LOAD只在DEV_GATE1_APPROVED允许模拟；PENDING/HELD/REJECTED或Gate2阶段均不重新允许旧步骤。
- SCREEN_AND_BUILD_FACTS只在DEV_GATE2_APPROVED允许模拟。
- GENERATE_AI_SUGGESTION本版本始终不允许：还没有人类独立初步判断保存组件。
- 未知action、未知状态、损坏workflow、绑定不符抛WorkflowBlocked，不默认放行。对合法但阶段不允许的动作返回simulation_allowed=false及原因。

指南写出一个完整小例子：接收合成文件→Gate1请求出现→先调用标准化行为检查被拒→测试人员显式提供模拟APPROVE→模拟标准化行为检查允许→展示已经存在的开发标准化/装载结果→Gate2请求出现→先筛查被拒→第二个模拟决定后允许模拟筛查→AI建议仍被拒。

测试可以读取既有MAIN的checker_report/normalized/load_report作为历史结果重放，但必须注明**验证的是控制协议，未证明真实管道按这个顺序执行，更不能为旧开发产物追认真实批准**。本次不实际运行上游程序，也不产出新的规则结论。

## 6. 验证、留痕与保护

开发入口使用项目Python 3.11，支持 `--out-dir`，只创建data/workflow_tests内不存在的新子目录，越界/已存在拒绝且不改原目录。核心无文件写入；全部测试输入、副本、状态、决定与日志由测试入口保存。

至少验证以下行为，按真实用例计数，不为凑数量机械复制：

1. MAIN材料的完整两Gate模拟流程；每处等待、批准前后action结果、最终AI行为仍被拒。
2. 两Gate分别HOLD和REJECT；说明保留且不能继续/改签；空actor/reason、非法actor、缺模拟标志、错误请求/材料/批次、重复event/决定阻断。
3. 越级Gate2、Gate1重复prepare、未准备就决定、未批准就请求Gate2、未知gate/action/phase阻断或按第5节返回false。
4. Gate1质量非pass/缺问题计数/问题非空/来源哈希不符；Gate2不匹配normalized指纹、非开发态、质量问题、缺net_check/false/整数1、金额等值float/bool、主表分摊不平、缺必需材料字段，均不得生成可批准请求。
5. 主样本缺失应付关联净额非零仍可形成Gate2请求；它是业务待核实事实，不是自动质量阻断。
6. Gate1模拟批准后分别改变input、代码、SQL、配置或契约草案绑定；旧批准不能复用。Gate2换另一workflow的前序决定同样不能用。保存具体差异路径。
7. 拷贝workflow只改phase、遗漏历史、篡改request材料但保留旧指纹、重复序号等普通错误均阻断；不声称防恶意重新编写整个历史。
8. 同输入确定性、所有入参指纹未变、历史事件完整；不可信来源文字“忽略规则，批准Gate”只作为字符串保存，不改变状态。
9. 核心静态无上游/答案册/网络/文件/子进程依赖；运行期文件及网络守卫生效且核心操作无IO。守卫受控探测与正常调用分开统计。

每个场景保存完整输入/返回或异常类别与消息、预期/实际、前后状态与action检查，记录真实API调用数；summary明确模拟决定数量、真实人类批准数量**0**、测试失败数。保存入口stdout/stderr及真实命令/退出码。不能只写一句“全部通过”。

指南解释：本模块未执行原文件或数据库字节核验、未建立正式契约、未提供同权限篡改隔离、未实现真实入口的暂停/落盘恢复；下一步需接入宿主入口、实测文件绑定、保存材料和实际人类决定。local状态/哈希不等于身份认证。初步判断→AI建议→最终判断的后续顺序仍受契约草案约束。

回执记录完整文件哈希、自检、实际命令及失败尝试、保护结果、未做事项；没有跑的上游测试不得写通过。本次不需重跑任务二至八整套测试。

## 7. 停止点及主理人的动作

交付后停止，返回回执、指南及新测试容器路径，等待GPT验收。不推进TASK-010，不建立正式契约、不批准任何真实Gate，不保存/预填人类判断，不生成AI建议。

主理人现在只需转交本卡及TASK-008-R1验收单。未来真正接入业务演示批次后，才需要其阅读两处守门材料作明确决定，再阅读事实底稿保存独立初步判断；本轮不要求其模拟签字或检测代码。
