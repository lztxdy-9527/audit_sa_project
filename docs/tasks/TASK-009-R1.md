# TASK-009-R1：补齐历史状态契约校验与验证留痕

执行：DeepSeek；架构/验收：GPT。项目：`D:\harness work\audit_sa_project`。

先读 `docs/reviews/REVIEW_TASK_009.md` 与本卡。原任务九正常流程回归已重复通过，本轮修复四项已复现的缺口，不重做上游，不执行TASK-010。

## 1. 修改边界

仅允许修改三个既有文件：

- `scripts/control_demo_workflow.py`
- `tests/test_control_demo_workflow.py`
- `docs/WORKFLOW_CONTROL_GUIDE.md`

新增 `docs/EXEC_REPORT_009_R1.md` 及data/workflow_tests内全新容器。核心升至 `TASK-009-workflow-control-1.1`，指南示例/字段表同步。四个公开API及纯内存边界不变。

全部其他文件冻结：原EXEC_REPORT_009、任务卡/验收单/GPT证据、上游模块/测试/SQL/schema/规格/契约/底稿指南、旧输入/数据库/运行现场。不得装依赖、初始化Git、做真实批准/正式契约/落盘入口、人类判断或AI建议。真实gate1_approval/gate2_approval仍恒null，next_step_allowed仍false。

主保护基线：`data/reviews/task009_20261011_092842/source_hashes_after.json`，只有上述三文件可以变化，其余0变化、0缺失。TASK-008-R1的13330及12546/10236/8547/6511/4902/874项基线全部不变。

## 2. F01：重放必须验证现有协议与所有消费指纹

历史状态来自调用方的对象，不能因外层指纹正确就跳过字段协议。将决定字段校验拆成可复用的纯校验逻辑，让首次record与replay共享同样的必需键、枚举、类型、时间、身份声明、模拟标志、说明、确认项和引用约束。

注意：首次record检查“event_id不能与此前历史重复”；replay检查“本事件与此前已重放事件不重复”，不能拿整段最终history检查而把当前合法事件自己判重复。合法保存记录额外含decision_sha256；明确剥离该派生字段再核验决定正文，不能放宽首次提交接口接受未知字段。

重放每个决定时，至少核对：

- 根据**不含decision_sha256的决定正文**计算实际规范指纹；决定内decision_sha256与事件顶层decision_sha256均必须等于实际值。
- 决定副本在simulated_decisions/history中严格一致；event_id、gate、request_id、materials_sha256及相关批次/绑定引用，与对应事件、当前请求和workflow一致。
- actor_kind仅SIMULATED_HUMAN、simulation仅SIMULATED_TEST_ONLY、身份/说明非空、occurred_at有时区、APPROVE的相应确认严格true；不得因它是历史条目而接受首次record会拒绝的内容。
- Gate2只绑定本workflow已验证的Gate1 APPROVE正文的实际指纹，不能继续使用未经核对的内嵌值。

请求重放亦应消费经过校验的对象：材料指纹与内容一致、材料的batch/gate/binding/scope/evidence仍符合原有prepare协议，request_id按原有确定性公式重新核对；事件与请求的相关引用一致。核对requests中不存在未在history出现的额外请求，决定集合与history逐项一致。不要增加新业务计算器或真实认证。

为控制范围，这些都是**既有协议在重放入口的一致应用**，不是要求证明历史真实或防御恶意重新编写所有对象/哈希。

## 3. F02：先检容器、条目和必需字段，再访问

对本层实际消费的state/history/request/decision/material等区段明确验证对象/列表、条目为对象、必需键存在、值类型及枚举。坏输入给WorkflowBlocked并指出完整路径。特别关闭：

- request缺request_id，不应变成KeyError→WorkflowError。
- simulated_decisions条目为整数，不应变成AttributeError→WorkflowError。

保留真正意外错误为WorkflowError及异常链；不要用except Exception全部改Blocked。对已知协议坏输入做前置检查即可，不需要无边界fuzz或支持任意Python对象。

## 4. F03：严格整数的数量与序号

四表row_counts在比较数值前验证为非负整数且非bool；history.seq验证为正整数且非bool，再校验连续序号。保存原观察类型，不转int、不补零。

新回归至少覆盖MAIN行数20→20.0、首事件seq=1→true；再用合法单行小样验证row_count=1可用而true不可用，用同一合法历史验证seq=1可用而1.0不可用。小样可读取已验收的C02等fixture结果，先确认其记录数确为1；不得靠删坏真实输入来制造“通过”。金额/确认项的原严格检查保持。

## 5. F04：原因断言和完整留痕

修复probe的判断：异常类别/返回分类满足预期**并且**指定的原因条件满足，才可PASS。使用独立自测证明：给helper一个预期WorkflowBlocked但说明不含指定sentinel的调用，helper必须识别为断言失败；这个“预期测试失败”的自测与最终测试失败数分开，不应使正常总流程误报失败。

各新增负向不只断言Blocked，要核对目标字段路径或稳定原因标识，证明进入了目标检查。若同步派生指纹以进入语义核验，保存同步路径/方法及说明；只同步新内存对象，不改任何旧证据。不声称它通过了真实上游重新计算，也不称为安全隔离测试。

原63项探针及9组流程均保留，不能删掉或放宽。补每个场景可复现的完整实参（workflow/current_bindings/decision/materials/action等对应实际调用）、完整返回或异常类别/消息、预期/实际、前后指纹及状态。正常流程的关键五个workflow保存完整 `{state,state_sha256}`，不要仅保存摘要或截取的final_state。

可以用JSON内容对象去重并在案例表中用明确路径+指纹引用，引用文件必须实际保存且能重建完整调用；不能只列一个无法还原内容的哈希。无需每次嵌套重复写相同的MAIN数据。批量负向可使用小型已验收fixture的开发结果，另保留MAIN缺失关联净额非零的正向控制，避免无意义放大文件；不得引入答案册或重新跑上游作为本层逻辑。

## 6. 必需新增回归与复验目标

GPT复现脚本和完整输入在 `data/reviews/task009_20261011_092842/`，可以阅读但不得导入到生产核心。将以下十项加入测试并保存完整结果：

1. P01：Gate1已记录决定的内嵌decision_sha256改全零，事件顶层实际指纹不变；check应WorkflowBlocked。
2. P02：同一错误对象prepare Gate2，也应WorkflowBlocked。
3. P03：历史决定actor_kind=AI，应WorkflowBlocked。
4. P04：历史APPROVE确认项false，应WorkflowBlocked。
5. P05：历史决定缺reason，应WorkflowBlocked。
6. P06：历史simulation=REAL，应WorkflowBlocked。
7. P07：待决定请求缺request_id，应WorkflowBlocked而非WorkflowError。
8. P08：simulated_decisions条目为1，应WorkflowBlocked而非WorkflowError。
9. P09：MAIN row_counts.suppliers=20.0，应WorkflowBlocked。
10. P10：首事件seq=true，应WorkflowBlocked。

P03—P06只改变一个逻辑决定正文及其历史/列表副本、派生指纹；P01—P10都可像GPT探针一样同步新对象的外层state指纹。不得以“同步了哈希”跳过协议检查或宣称需要抵御同权限攻击。

另加正向控制：合法序列化/反序列化的五个关键workflow继续可用；两个PENDING不允许对应动作、Gate1 APPROVED仅允许模拟标准化、Gate2 APPROVED仅允许模拟筛查、AI始终被拒。四停止态仍不能继续，真实批准0。重放时若因校验复用错误阻断所有合法历史，应修复，不得通过删除恢复检查规避。

请求校验补两项针对性检查：更改request_id及相应事件引用但保持材料不变，应因确定性请求ID不符阻断；改变请求材料的质量结果并同步材料指纹等派生引用，应因原材料协议不符阻断。保存所有同步操作，明确只是协议自相矛盾的内存输入，不是现实篡改防御。

一次完整新容器回归即可；没有新失败/修改无需反复重跑，也不要求任务二至八整套测试。分别统计原探针、新增探针、helper自测、正向流程、API次数、模拟决定与真实批准0，不先虚报调用总数。确定性、入参不变、运行期文件/网络隔离和静态依赖边界保持。

## 7. 回执与停止

指南解释修复后重放验证范围、决定指纹剥离口径、严格类型及留痕读取方式，版本统一1.1；明确没有真实身份认证/防恶意篡改能力。

新EXEC_REPORT_009_R1记录四项关闭证据、完整哈希、真实命令/退出码、分类计数、原因断言自测、保护对照、失败尝试和未做事项。旧回执不回写。

完成后提交回执、更新指南、新测试容器，停止等待GPT复验。不推进TASK-010，不接入data/batches或修改batch_manifest，不保存/预填人类判断、不生成AI建议。

主理人本轮只需转交验收单与本卡，无需人工检测或模拟签Gate。
