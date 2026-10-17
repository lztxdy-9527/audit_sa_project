# TASK-009-R1 复验单

日期：2026-10-11；验收：GPT；结论：**暂不通过，仅继续修复F01及F04剩余部分；F02、F03关闭。暂不推进TASK-010。**

本轮修复已有明显进展：旧十项探针均按预期阻断，决定正文及内外指纹核验生效，错误分类和整数类型已纠正。仍有两项上轮明确要求未落实，不是扩展新的业务或安全目标。

## 1. 实际复验

新容器：`data/workflow_tests/task009_r1_gpt_20261011_095041`。项目Python 3.11实际运行验证入口，退出0、测试失败0；入口记录API 234次（42/81/49/62）、探针79条、流程12组、helper自测1条、主流程模拟决定2条、真实批准0。

GPT另运行原独立脚本，公开API共20次：P01—P10全部为带目标字段的WorkflowBlocked，五个正向阶段控制全部正确，入参未变。完整正常workflow序列化后可消费。F02错误分类及F03严格类型据此关闭；F01正文协议与指纹部分关闭。

GPT核对新容器全部89份内容对象，文件名指纹与内容均一致；五个关键workflow均完整、state指纹正确。helper原因不符自测确实返回类别正确/原因错误/总体false。F04这些部分已完成。

## 2. F01剩余：事件外层引用及集合核对未完成（阻断）

位置：`scripts/control_demo_workflow.py` 的 `_replay_history`（第309—453行）。上轮卡第2节要求事件引用与决定/请求/workflow一致，并拒绝没有history事件的额外请求。

GPT在合法Gate1 APPROVED的内存副本中，只改下面单个字段、再同步外层state指纹，均仍得到simulation_allowed=true：

- Q01：history[2].event_id与其decision.event_id不同。
- Q02：history[2].gate写成GATE2，但event_type和决定正文都是GATE1。
- Q03：history[2].request_id指向OTHER-REQUEST，正文仍指向真实请求。
- Q04：history[2].materials_sha256改全零，正文及真实材料指纹不变。
- Q05：创建事件batch_id写成OTHER-BATCH，workflow仍为原批次。
- Q06：Gate1请求事件run_bindings_sha256改全零，真实请求绑定不变。

Q07在Gate1已批准状态中放入一个形状和材料合法、但history中尚未出现的Gate2请求，也被接受。末尾比较的是重放局部requests与request_events，两者自然同步，未比较**state.requests实际保存的对象**，因此该检查不能发现多余请求。

Q08另观察到simulated_decisions顺序颠倒仍被接受，当前只排序比较ID。若保持上轮“与history逐项一致”的协议，应按history次序核对完整记录；不可把顺序改变误称为逐项精确一致。

上述八个公开API探针均未修改旧文件、源输入、决定正文或业务规则；仅同步新对象外层指纹以检查内部协议。不涉及证明历史真实性、身份认证或防同权限恶意篡改。

## 3. F04剩余：关键字实参没有保存，helper重复计数（阻断）

位置：测试入口 `_capture` 第157—160行、probe保存部分、helper自测清理部分。

capture只深拷贝位置参数，call_kwargs仅保存键名；probe产物连这些键名也未保留，更没有关键字的实际值。79条probe均无kwargs内容。

GPT尝试从五条S6_binding_change案例保存的对象还原调用，全部得到TypeError：缺少必需的keyword-only参数current_bindings。尤其这些案例的current_bindings正是被改变的关键输入，不能用workflow内旧bindings猜回去，否则会抹去测试变更。完整输入仍未真正可重建。

另外，helper预期失败的自测仍留在主checks中，导致“原探针64”实际包含原63条加helper1条，并同时另计helper自测1条。原因是checks追加了一个包装对象，而清理时用返回detail寻找，二者不相等。最终test_failures虽为0，但分类计数及主checks有一条预期自测FAIL，应按要求独立保存。

## 4. 证据与边界

GPT证据：`data/reviews/task009_r1_20261011_095041/`。包含原十项复验、五个正常控制、Q01—Q08完整输入与返回、remaining_results.json（对象核验/留痕结构/五条重放TypeError）、回归stdout/stderr和命令、保护对照及验收汇总。

当前三个交付文件哈希为4230d2b0…、614d9903…、0c5d196c…，与回执一致。TASK-009基线13395项只允许这三文件变化；13330/12546/10236/8547/6511/4902/874项历史基线全部不变，详见本轮protected_files_comparison.json。

GPT未修改实现、测试、指南或旧产物；未批准Gate、建立正式契约、保存人类判断或生成AI建议；未重跑任务二至八整套测试。

下一步只转交本单与 `docs/tasks/TASK-009-R2.md`。主理人不需要人工检测或模拟签字。
