# Gate2 决定快照保存与只读核验

实现 `scripts/runtime_gate1.py`，版本 `TASK-030-runtime-gate1-1.0`。本阶段固定一个 Gate2 事件，不连接筛查或执行放行；没有生产 CLI。

## 两个接口

```python
save_runtime_gate2_decision(
    batch_dir, runtime_dir, request_id, submission, event_dir, *,
    scope_dir, event_relative, database_path
)
verify_runtime_gate2_decision(
    batch_dir, runtime_dir, *, scope_dir, event_relative,
    database_path, gate2_event_relative
)
```

scope_dir/event_relative 始终描述 Gate1 来源，event_dir/gate2_event_relative 描述 Gate2 输出。两个成功返回均恰 record/record_fingerprint/event_relative 三键，最后一项为 Gate2 事件项目相对路径。record 是真实冻结 P1 的17键正文，不添加 effective/allowed。APPROVE 保存、HOLD 保存和只读核验均不授权执行。

复用 RuntimeGate1Blocked(field,reason) / RuntimeGate1Error(stage,reason)；保留 cause/context、原始 field/reason 和主次错误。公共请求 prepare_runtime_gate2_request 仍只读、原签名/两键外层不变。已有七个更早的公共 API 协议与前提保持。

## 唯一路径、锁和历史

Gate1 scope 为 gate1 根下经核验的严格后代，其相对 suffix 唯一映射到 `data/human_gate_decision_records/gate2/<suffix>/event_0001`。Gate2 scope 保存前必须从未存在，已有空目录也拒绝；不追加、替换或撤销。路径逐级拒绝 reparse/链接，resolve 后与固定映射精确比较；Gate1 单事件 scope、登记叶两文件和 load 叶四文件规则不变。

技术锁在登记叶同级 `<登记叶名>.gate2.lock`，与 Gate1 锁分开。复用独占取得与身份/内容核验，仅释放本次自建且身份未变的锁。取得半写、替代锁和旧锁保留；失败不能盲删锁。成功路径先完成全部语义消费和返回对象构造，按身份释放自锁后才做最终原始字节确认；之后不再读取锁或候选生成成功。

前序来自本次真实核验的完整 Gate1 记录，wrapper恰三键，版本 `TASK-020-human-gate-decision-record-wrapper-1.1`。submission.prior_decision_binding 必须与它 canonical 全等，适配器不悄悄替换错误提交。Gate1须同批次APPROVE/HUMAN_DECLARED，与登记、装载和Gate2共享六项运行绑定。

prior_history 是三键对象，declared_complete 严格true，records恰一个完整 Gate1 wrapper；declared_scope 固定为：

```text
GATE2_SCOPE:<Gate2 scope项目相对路径>|BOUND_GATE1:<Gate1事件项目相对路径>
```

完整性只覆盖本次实读证明尚不存在的 Gate2 scope 及绑定的 Gate1 事件。没有全局历史发现或空历史默认值。

## 保存与恢复

保存按以下顺序执行：

1. 参数、确定路径、已有现场检查；独占 Gate2 锁。
2. 共享 TASK-029 内部物化逻辑，自行重新真实准备请求，并保留操作起始同缓冲 captures。
3. 对照独立 expectations 核验 submission 技术绑定与完整 wrapper，实际枚举 scope 不存在。
4. 核心前复确认来源/登记/Gate1/装载/DB集合和字节，并核验本次锁身份/内容。
5. 独占建立 Gate2 scope/event；冻结 store.save 恰一次，其内部新决定 P1 恰一次。没有独立 P1 预调用。
6. manifest 实读SHA必须等于该次真实 store 返回；五payload按它核对长度/SHA，四输入快照与本次消费对象规范相等，decision_result 与真实返回指纹闭合。
7. 独占写 context，读回与本次缓冲精确相等，再最后写 receipt 并同样读回；构造成功三键结果。
8. 释放自锁；以起始captures和本次已绑定writer读数作最后有界字节/集合/路径/failure/锁确认，直接返回。

只读 verify 先检查锁/failure/固定集合，同缓冲读取八文件，重新准备当前请求并核验绑定 Gate1，调用一次冻结 store.verify。除status外所有store稳定字段、封套schema、身份/路径、完整request/history、材料/运行绑定、manifest与记录指纹均闭合；构造结果后只做末端原始字节确认。verify不写任何诊断或保存决定。

正常事件仅 context.json、receipt.json、snapshots/；snapshots恰冻结store六文件（共八文件）。context14键，receipt9键，版本分别 `TASK-030-runtime-gate2-context-1.0` 和 `TASK-030-runtime-gate2-receipt-1.0`。封套五项边界全部严格false；不改变P1六项false边界或persisted=false。

context.request 是真实准备时六键请求的不可变快照，其中 request_persisted=false 说明准备时状态。该快照就是本次决定的持久材料；不另建 gate2_request.json，不写登记叶。TASK-025的旧提案位置不回写，不宣称旧位置已实现。

失败仅在本次已建立事件后独占写 failure_version/stage/field/reason/cause_chain 五键，版本 `TASK-030-runtime-gate2-failure-1.0`。无事件不造事件；主次错误已知后一次写定。诊断失败仍向调用者报告原错误及次错误。半写和已建目录保留，不覆盖、不重试、不宣称回滚。

人类字符串按原文保存。JSON对象快照不承诺原始输入文件排版/BOM；文件SHA取确切字节，对象指纹取既定canonical JSON，二者不互替。普通ID不作语义黑名单判断。

## 验证与边界

```text
.venv\Scripts\python.exe -B tests\test_runtime_gate2_decision.py --out-dir data\runtime_gate2_decision_tests\task030_<新名>
... --out-dir data\runtime_gate2_decision_tests\task030_<新收尾根> --replay <本轮正常证据根> --mutate none|candidate-return|ledger-late|checks-late
```

测试先核对任务卡所列 BASE2.submission 和 HOLD0002 来源 SHA，仅技术批次/请求/当前完整前序按实际材料构造。外层测试证据标 PROTOCOL_TEST_FIXTURE_ONLY；没有新增人类事件ID、身份、时间或原因的正常夹具。

四组覆盖正常APPROVE/HOLD、独立十材料与完整前序/history、错误绑定/路径/已有scope/锁/P1拒绝、真实准备后DB变化、真实store返回后候选manifest变化、末次语义核对返回后context变化、真实独占句柄半写和真实receipt writer完整写后sentinel。需要恢复时先保存本轮原字节和坏候选，逐个文件精确恢复；既有锁对照使用独立场景，保持原路径不动，不清理目录。

完整API与嵌套返回/异常、真实消费引用三时点、原始code对象profile分列。P1观察额外记实际所在store.save或store.verify原函数代码帧，区分新决定构建与只读复算。准备用的Gate1核验、store.verify内部P1允许；准备/保存/恢复窗口内normalizer/loader命中0。计算只用于建立当前版本前提小样。

只读复用冻结TASK-029观察器和TASK-028短证据收尾，不改旧测试或新建审计框架。replay四个新进程应为0/1/1/1；坏候选保留、期望不刷新，真实审核/字节漂移支配FAIL、非空failures和非零返回。replay中的载荷是历史观察，不计为新业务调用。

真实链接本卡未另建；历史大套件、执行放行、筛查/复算/事实/真实独立初判/AI/终判均未执行。真实批准仍null、开发宿主0008、next/AI=false，不生成0009。
