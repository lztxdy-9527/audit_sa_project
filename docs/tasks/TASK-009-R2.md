# TASK-009-R2：只补事件引用一致性与可重放留痕

执行：DeepSeek；架构/验收：GPT。根目录：`D:\harness work\audit_sa_project`。

先读 `docs/reviews/REVIEW_TASK_009_R1.md` 和本卡。旧P01—P10均通过复验；F02和F03已关闭。保留这些修复，本轮仅完成F01、F04尚缺的要求，不扩大业务范围，不推进TASK-010。

## 1. 修改边界

仅允许修改control_demo_workflow.py、test_control_demo_workflow.py、WORKFLOW_CONTROL_GUIDE.md三个既有文件，分别位于scripts/tests/docs。新增docs/EXEC_REPORT_009_R2.md及data/workflow_tests内全新容器。核心版本统一为 `TASK-009-workflow-control-1.2`，四API及开发态边界不变。

主保护基线：`data/reviews/task009_r1_20261011_095041/source_hashes_after.json`，只授权上述三文件变化；其余0变化、0缺失。13330/12546/10236/8547/6511/4902/874项历史基线亦全部不变。旧回执、指南以外的文档、任务卡、验收单、GPT证据、上游脚本/测试/SQL/schema/契约/输入/数据库/旧容器不改写。

不得装依赖、初始化Git、建立正式契约或真实批准接口、落盘状态机、接入data/batches、人类判断或AI建议。真实批准恒null，next_step_allowed恒false。

## 2. F01：核对事件中已经存在的引用字段

不要只根据event_type决定状态而忽略同一事件的gate和其他引用。根据当前事件种类，核验**该种类原本生成的字段**与权威state/request/decision一致；不要强迫所有事件具有相同字段集。

- 创建事件：batch_id与state.batch_id一致，gate为null，run_bindings_sha256与创建绑定一致；保留首事件及seq严格校验。
- 请求事件：gate与event_type所指Gate一致；request_id、materials_sha256、run_bindings_sha256与对应已验证请求一致；Gate1前序决定为null，Gate2前序决定为已验证Gate1批准正文的实际指纹。保留请求材料协议和确定性request_id复核。
- 决定事件：event_id、gate、request_id、materials_sha256与已验证决定正文、当前Gate请求一致；保留决定正文协议、内嵌/事件顶层实际指纹、两个存放副本一致性。

不转换、补填或忽略错误引用；缺必需字段或不一致均为带路径的WorkflowBlocked。只是核验既有对象内部一致，不新增身份认证或防恶意篡改宣称。

结束重放时，把**state.requests真正存放的对象**与按history重放得到的requests比较，拒绝无history事件的额外请求或缺少实际请求。不能继续只比较两个都来自同一次重放的局部集合。决定列表按history次序核对完整记录，满足既定“逐项一致”，不再排序ID后就结束。

新增Q01—Q08真实公开API回归，GPT完整小样在 `data/reviews/task009_r1_20261011_095041/`：

1. Gate1已批准的history[2].event_id改为OTHER-EVENT-ID。
2. 同事件gate改为GATE2。
3. 同事件request_id改为OTHER-REQUEST。
4. 同事件materials_sha256改全零。
5. 创建事件batch_id改为OTHER-BATCH。
6. Gate1请求事件run_bindings_sha256改全零。
7. Gate1已批准的state.requests.GATE2放入一个来自同批次合法Gate2 pending状态的请求，但不添加history事件。
8. 完整Gate2已批准状态的simulated_decisions顺序颠倒。

均仅对新内存对象同步外层state_sha256，预期WorkflowBlocked且原因指向目标引用/集合。分别保存唯一变更路径（Q07为新增整个请求，Q08为列表顺序）、指纹同步说明及完整调用。Q01—Q06不要顺手修改决定正文、请求或相关指纹来消除矛盾。

## 3. F04：保存完整kwargs及隔离helper自测

_capture深拷贝实际call_args和call_kwargs的**值**。probe保存调用函数、全部args、全部kwargs的内容对象引用；current_bindings是keyword-only参数，必须真实保存。继续使用内容寻址去重，无需重复嵌套大对象，也不能从workflow旧bindings猜测当次实参。

args/kwargs的记录形状在指南固定，能明确还原为：

```python
getattr(controller, saved_function)(*restored_args, **restored_kwargs)
```

全部引用须能解析、内容指纹正确；保存完整返回或异常类别/消息/原因。阻断没有返回新state时，明确这是“无返回状态”，另记录实际输入workflow调用后指纹以证实未修改，不能把null当成输入丢失。

修复helper自测清理/隔离逻辑。建议用明确开关避免把预期失败的helper自测写入主checks/failures，而不是依赖字典内容相等去删除另一个包装对象。helper自测单列保存、单独计数；其真实API调用可计入总API次数，但不能同时充当原探针。保留“类别正确、原因不符→helper判失败”的自测。

原63条合法业务/协议探针、R1新增15条、12组流程保留；helper1条独立。按实际case/kind分类，不硬编码预设总数。此前回执的“原64”含helper，R2需如实解释这一计数修正，不改旧回执。

## 4. 必需的证据重放验收

在测试入口保存完对象后，用公共API从**保存的args/kwargs文件**重放五条S6_binding_change案例（input/code/rule_sql/config/contract）。不使用闭包里的原变量，不从workflow推断缺少的关键字值，不修改保存对象。

每条重放必须再次得到WorkflowBlocked且原因指向绑定变化；保存恢复的函数/参数引用、实际分类/原因、与初次结果是否一致、实参前后指纹。重放API次数另列并纳入真实总次数，不能把重放当成新工作簿输入。

另重放至少一条成功API调用，完整返回与首次结果精确相等，以证明记录格式同时支持成功与阻断。对所有probe引用做离线存在性/指纹/参数完整性核对；不要求重复跑每条大对象调用，五个绑定负向和一个成功调用已足够验证本缺口。

保留五个完整关键workflow、内容对象全部哈希自检、入参不变、阶段正向控制、四停止态、旧P01—P10、R1类型及请求协议探针、金额/布尔严格检查、静态和运行期无IO边界。不重跑任务二至八整套测试。

## 5. 回执与停止

一次全新容器完整回归，真实记录命令/退出码、旧/新/重放/helper分类、API次数、模拟决定和真实批准0、文件保护及失败尝试。更新指南版本1.2、事件字段核对表述、kwargs还原方式和helper计数边界；不把内部引用核验称为身份认证。

新EXEC_REPORT_009_R2给出Q01—Q08阻断路径、五负一正保存文件重放证据、全部引用核对、helper不再混入主checks的证据；旧回执不回写。

完成后交回执、指南和新容器路径并停止，等待GPT复验。不推进TASK-010。主理人仅转交本复验单及本卡，无需人工检测或模拟批准。
