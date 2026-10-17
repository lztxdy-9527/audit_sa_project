# TASK-024-R8：经授权定点修复后的整体验收

日期：2026-10-15。GPT Architect / Reviewer。**最终结论：ACCEPTED（GPT 授权修复版）**。原 DSH R8 交付仍有两处遗漏；人类明确授权“这一轮还无法通过，直接调用一个子 Agent 修改”，GPT 已据此完成测试侧修复并独立复验。此结论对应下面的新文件身份，不能倒推原始交付已经通过。

## 1. 原交付与本次修复身份

- 原 R8 测试：`bb3a3c6fbf75e05322138fdf0efd97bd09199f05d7601dcbd064d0d0b26402d2`，236218 字节；保存只读原件于本轮评审根 `submitted_test_bb3a3c6f.py`。
- 原回执 `docs/EXEC_REPORT_024_R8.md`：`e230b5656002a87041e15b87fa99d2067dfaf9ed5991e06a2fb184f9dc16c640`，10851 字节，**未回写**。
- **最终测试** `tests/test_record_demo_human_gate1.py`：`fc38b82c694564bdc511573173d3d6ee9caf3aa7c421d7d95e4a0788cbdc87ff`，236681 字节。
- 生产适配器仍为 `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9`，85064 字节。指南、prepare/store/P1、契约/登记/配置、宿主/控制器、旧 harness 全部冻结。

本次只修改上述一个测试文件。完整差异在本轮根 `authorized_fix.diff`。未创建 R9 修复卡，不再要求人类转交 DSH 处理本残余。

## 2. 原 R8 的残余与实际修复

**外层失败没有落盘 failures。** 原 R8 确实修好了实际 CLI 返回 1，但外层 checks 晚加 LF 后，仅修改内存 FAILURES 与 summary，磁盘 `failures.json` 仍为空。DSH 自己的 `cli_probe_results.json` 记录了 failures_len=0，与回执的非空声明不符。GPT 新进程复现同样为 1/FAIL/磁盘 failures=0。

**外层只确认六载荷，漏掉台账。** 原 R8 在真实 `run_r5_entry` 正常返回后给 `evidence_ledger.json` 追加 LF，仍 0/PASS/空 failures，因为外层预期集合不含台账。

子 Agent 的小范围修复：

- 在既有同一次外层原始字节确认中加入台账，其期望取自本次 writer 已绑定的 `ledger_sha256/ledger_byte_size`，不从候选文件重建预期。
- 外层实际失败把非空 failures 真正写盘；summary FAIL、磁盘 failures、实际 main/进程返回一致。
- 内部返回已核验的内存 summary，外层失败直接采用它，删除对可能损坏的 summary 的重新读取。
- 保留坏 checks/台账与原台账预期，不重建台账消除漂移；正常正式七文件仍各只写一次。

没有改生产适配器、改变 Gate/批准/AI 语义、扩大负向豁免，或新建决定记录。主 Agent 未把子 Agent 自报直接当作验收结论。

## 3. GPT 主 Agent 独立实测

证据根：`data/reviews/task024_r8_gpt_20261015_003349/`。

`probe_entry.py` 明确只读复用 R8 旧业务观察，当前真实 `main()` → `--only r5` → `run_r5_only/run_r5_entry` 全部执行；没有重复接收或业务 prepare。最终修复后，主 Agent 启动五个新 Python 进程：两个正常（其中一个另观察外层读取）与三个故障。

- 正常：实际进程 **0**、summary **PASS**、磁盘 failures **0**；六载荷逐项与台账及写前 basis 的长度/SHA 一致，台账自身与 writer 绑定相符。
- 实际最后正常根审核：真实 `audit_ledger` 返回后映射一次非空问题，原始 ok=true 保留；实际进程 **1**、summary **FAIL**、磁盘 failures **1**。
- checks 晚变更：真实 entry 返回原 verdict 后只追加一个 LF，不同步哈希；实际进程 **1**、summary **FAIL**、磁盘 failures **1**，坏 checks 字节保留。
- 台账晚变更：相同接缝只给台账追加 LF；实际进程 **1**、summary **FAIL**、磁盘 failures **1**，坏台账字节保留。
- 正常写入观察：六载荷 + 台账，七文件各写一次；真正外层只读这七个候选各一次，无失败分支 summary 重读。内部终端确认后候选读取静态计数为 0。

主要记录：`verified_normal_result.json`、`verified_audit_result.json`、`verified_checks_result.json`、`verified_ledger_result.json`、`verified_terminal_normal_result.json`，汇总与断言在 `independent_verification.json`。失败元数据与旧成功候选哈希不同是保留失败现场的结果，不被称为成功台账一致。

主 Agent 实际业务 prepare/接收器/P1/store 调用均为 **0**；证据中的 9 条 prepare 是读取的 R8 既有观察，不计为本轮重新调用。主 Agent 另用当前真实审核 helper 核对原始核心 9 / 正向 6 / 隔离负向 3：正向通过，三条负向各自拒绝，范围未扩大。

子 Agent 自测单列：`agent_fix/verification.json`，37/37 PASS；包含损坏 summary 仍 1/FAIL/非空 failures 的控制。该结果作为补充，不冒称主 Agent 重跑。未重跑完整 98/93 项、历史业务入口、writer/loader 大组或已关闭生产路径。

## 4. 对 R8 回执三项口径的裁决

1. **正常末次结论单列：接受。** 载荷内只保存已经完成的检查/控制结论，当前共 9 项；末次正常根结果另存 `r8_entry_checks.json`，不为自指再写台账。最终成功仍由实际 main 的 verdict 与磁盘确认决定。
2. **外层一次线性确认：修复后接受。** 已覆盖完整七文件，期望来自写前/本次 writer 的绑定；之后不再读取候选决定成功。它不是无界重试或多轮循环，也不自动恢复被改字节。
3. **expect_failure：沿用此前限定接受。** 只表示既有失败是否如实登记，不是把最终失败改成成功；三条具名负向之外的实际失败均支配非零。台账中反向的旧 `content_audit.ok` 信息字段仍不作为通过判据，真实内容比较结果才是依据；该旧信息文案登记为非阻断，未扩大修复范围。

原回执晚变更 failures 非空的声明由本报告更正，旧回执不改。本次最终哈希由本报告和新验收基线登记，不要求执行端补一轮回执或测试。

## 5. 保护、历史与关闭口径

GPT 一次最终完整扫描实读 157235 文件，changed 仅测试文件；missing、读取错误、范围外变化/新增全部为 0，scope_compliant=true。全部生产/契约/配置/指南/旧 harness 冻结身份一致，旧 R5 越界 326 文件逐项不变且不追认。前轮两个自指元数据按确切路径单列，没有 data/reviews 前缀豁免。扫描后仅有限身份核对和本轮评审元数据定稿，没有第二次全树扫描。新 ACCEPTED 基线身份与两个确切自指排除见同根 review_result.json。

TASK-024 及 R1—R8 的功能阻断到本授权修复版全部关闭，可由人类关闭对应看板卡。保留历史 NOT_ACCEPTED 与故障现场，不把最终验收追认成旧代码已经通过。R5 越界生成的 37 目录/326 文件继续留证、不追认；R2 旧 harness 越界及 R3 具名恢复也不改历史结论。

真实批准仍 null，宿主仍为开发态 0008，next/AI false，真实人类初判未保存。`APPROVE` 记录仍不等于执行许可，技术验收不批准任何批次。

按持续授权，下一张为 `docs/tasks/TASK-025_DRAFT.md`：只设计真实运行层的共享绑定及 Gate1→Gate2 材料接线，避免把开发控制器或各阶段不同的代码指纹误作真实放行。下一卡不直接实施计算/批准/宿主接线。
