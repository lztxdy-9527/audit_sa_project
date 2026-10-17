# TASK-009 验收单

日期：2026-10-11；验收：GPT；结论：**暂不通过，按 TASK-009-R1 修复后复验；不领取 TASK-010。**

原有正常流程、暂停及HOLD/REJECT控制已经有效，但历史状态消费的协议校验和测试证据仍有缺口。GPT未修改生产核心、测试入口、指南或任何旧产物；没有批准真实Gate。

## 1. 实际验证

新容器：`data/workflow_tests/task009_gpt_20261011_092842`。使用项目Python 3.11运行原入口，实际退出0：API 162次，探针63项、流程9组、测试失败0；主流程模拟决定2条、真实批准0条。这个结果确认原回归可重复，不代表新发现的缺口已被覆盖。

GPT另通过公开API调用20次（create 1、prepare 4、record 2、check 13），验证五个正向控制及十个负向消费层探针。正常的两处等待/批准阶段与AI禁止均符合预期；十个负向均未达到要求，其中八个返回结果、两个误报WorkflowError。所有探针入参保持不变。

## 2. F01：历史决定重放没有完整验证决定协议与指纹（阻断）

位置：`scripts/control_demo_workflow.py` 第221—318行，尤其历史决定分支及Gate2前序决定引用。

- P01只把Gate1已记录决定内的decision_sha256改为全零（同步其两个存放位置及外层state指纹，事件顶层真实决定指纹保持原值），check仍返回simulation_allowed=true。
- P02用同一对象prepare Gate2，仍返回DEV_GATE2_PENDING，并把这个错误的内嵌指纹作为前序批准指纹使用。
- P03—P06分别将一个逻辑历史决定改为actor_kind=AI、确认项false、缺reason、simulation=REAL，并同步该决定的副本及派生指纹。四项仍返回允许模拟标准化。

当前replay只检查部分副本与引用一致，未对已存决定执行与首次record等价的字段约束；事件顶层指纹与决定内指纹也未同时核对。这样一个符合外层JSON指纹、但内部协议错误的workflow仍能被消费。

这些是**内存对象的一致性与契约校验**，不是要求抵御能重写整个历史的同权限攻击者，也不提供真实人类认证。同步派生哈希是为了进入语义核验，不能据此声称历史真实。修复应复用字段协议，不增加身份认证系统。

## 3. F02：缺字段/错类型的workflow被归为意外运行失败（阻断）

位置：同一replay分支及其调用边界。

- P07删除待决定request的request_id并同步外层指纹：得到WorkflowError，原因为KeyError。
- P08把simulated_decisions条目改为整数1并同步外层指纹：得到WorkflowError，原因为int没有get。

这是调用方提交的协议对象不完整，应为带路径的WorkflowBlocked。不能用大范围吞异常或统一改成Blocked掩盖真正的程序错误；应先验证实际消费的容器、条目、必需字段及枚举再访问。

## 4. F03：计数及序号接受数值等价的错误类型（阻断）

位置：Gate2 row_counts比较（第519—521行）、history.seq比较（第233—234行）。

- P09将MAIN供应商行数20改成20.0，Gate2请求仍建立。
- P10将首事件seq=1改成true，workflow仍被接受。

计数和序号必须为整数且非bool；行数非负，序号从1连续递增。不能只用Python的数值相等判定。金额和布尔确认项已有严格校验，保持这些行为。

## 5. F04：负向原因断言及完整输入留痕不足（阻断）

位置：`tests/test_control_demo_workflow.py` 第275—303行及末尾产物保存。

probe在expect=blocked时不会执行contains条件。GPT提取原probe函数做独立小样：实际抛出的说明不含指定TARGET_REASON_SENTINEL，helper仍报ok=true。这会把“被另一前提拦住”误当作目标字段校验已验证；不能仅凭日志人工推测原因。

新测试容器仍只有6个文件，63条probe均未保存完整实参和完整返回/异常现场；final_state.json也只保存phase/history等子集，缺requests、bindings及完整state，不能作为可重载workflow。任务卡第6节要求的逐场景留痕没有完成。应补结构化可重现输入与实际结果，允许去重引用，但不能只留哈希和摘要。

## 6. 证据、保护及停止

GPT证据目录：`data/reviews/task009_20261011_092842/`，包含完整正常workflow、P01—P10输入与实际返回/异常、independent_results.json、test_evidence_review.json、原回归stdout/stderr与命令退出码、保护对照和验收汇总。

TASK-008-R1的13330项及12546/10236/8547/6511/4902/874项历史基线必须保持不变，实际核对结果见protected_files_comparison.json。新修复只授权核心、测试、指南三个既有文件及新回执/新测试容器。

本轮未重跑任务二至八整套测试，未接入真实入口、落盘状态机或正式契约。下一步仅转交本验收单与 `docs/tasks/TASK-009-R1.md` 给DeepSeek；主理人不需人工检测或模拟批准。
