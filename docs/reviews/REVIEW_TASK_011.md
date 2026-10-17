# TASK-011 验收：需要修复，暂不推进 TASK-012

验收：GPT；日期：2026-10-11；项目根目录：D:\harness work\audit_sa_project。

**结论：CHANGES_REQUIRED。**独立重跑现有入口，9 组全 PASS、退出 0、failures=[]；但新增的有界探针复现了三类恢复缺口，另发现调用计数漏报。现有测试通过不能关闭这些缺口。本轮没有修改交付的宿主、测试或指南。

## 1. 已确认成立的内容

- 宿主/指南/新测试完整哈希与回执一致；冻结上游及旧测试保持原字节。
- GPT 新容器 data/workflow_host_tests/task011_gpt_20261011_133022，真实执行项目 Python -B tests/test_prepare_demo_gate2.py --out-dir <该新容器>，退出 0。
- MAIN/C02/C07b 正常流程、缺失关联保留、Gate1 授权后实际标准化/装载、Gate2 pending 与真实批准 null 均有正常证据。
- 两份 writer 现场（DeepSeek 最终容器及 GPT 新容器）的完整文本字节数/哈希、40 字节前缀、sentinel OSError、旧 0001/0002 前后哈希均独立核对成立。
- 最终 summary/checks/cli_logs/读回、自测在本次正常验证中一致。没有执行规则、复算、底稿、AI 或真实批准。
- 相对 task010_r4 的 26215 项基线，只有宿主与指南两项变化、缺失 0；其余保护结果见 QA 的逐项文件。

## 2. F01：记录为失败的 prepare 仍恢复为 READY（P1）

位置：scripts/run_demo_workflow.py 的 _save_gate2_failure、inspect_dev_batch（尤其 gate2_started 且 revision < 3 的分支）与 prepare_dev_gate2 异常处理。

复现：新 C02 Gate1-approved 前缀副本上，wrapper 先调用真实 writer 保存完整 0003，再抛 WorkflowHostError，原因为 sentinel OSError。prepare 确实返回运行失败，且保存了 failure.json。此后移除测试 wrapper，以正常 inspect_dev_batch 恢复，却返回 READY / DEV_GATE2_PENDING，并称 NORMALIZE_AND_LOAD 已完成。

这与指南“failure.json 仅失败时存在，与成功不共存”冲突。当前只有 revision < 3 才处理失败记录，完整 0003 路径会忽略它。必须在共同恢复协议中处理可观察到的失败，不能因文件碰巧完整把失败收尾改成成功。

证据：
data/reviews/task011_20261011_133022/F01_prepare_fault.call.json
data/reviews/task011_20261011_133022/F01_restore_after_failed_prepare.call.json
现场：data/batches/task011_independent_20261011_133022/F01_post_write_failure/c02。

## 3. F02：操作末尾的新产物变化未被检出（P1）

位置：inspect_dev_batch 的结束核验，以及 prepare_dev_gate2 的 post_write_verify 收尾。

两种 status 反例：在初次核验材料/数据库之后、冻结 prepare_dev_gate 用于纯重放返回时，仅给本次数据库或 load_report.json 追加一个换行；注入命中各 1 次。该次 status 均返回 READY；恢复正常依赖后再调用 status 才被拒绝。第一次读取结束时已经是与报告声明不一致的现场。

另一个实际 prepare 反例：真实标准化、装载、写 0003 后，在第二次纯 prepare_dev_gate 重放（post-write 核验中）给 load_report.json 追加换行。该次 prepare 返回成功 0，紧接着正常 status 返回阻断 1。

现有结束核验重测输入/代码、manifest/checkpoint；prepare 另检查数据库，但没有统一重测全部 Gate2 消费产物。应在最后的控制器调用之后、返回成功之前，对本次消费的 normalized/load/artifacts/数据库及相关状态文件做一致性收尾。只要求有界普通变化检测，不声称实现原子快照或同权限安全隔离。

证据：
F02_status_database_change.call.json、F02_status_report_change.call.json
各自 *_later.call.json
late_prepare_probe.json
均位于 data/reviews/task011_20261011_133022。

## 4. F03：artifacts 的字节引用与内部声明未核全（P2）

位置：_read_gate2_outputs、_verify_prepare_operation 与新 0003.operation 构造。

复现五项，全都错误返回 READY：

1. 只给 artifacts.json 追加换行，语义不变。0003 没有保存并校验该文件的实际字节哈希，任务卡要求的文件绑定缺失。
2. 只把 artifacts.database_sha256 改为 64 个 0，同时同步 0003.operation.artifacts 这一份副本；独立 operation.database_sha256、实际数据库、load_report 都不改。
3. 同样只改 artifacts.normalized_payload_sha256 为全 0，并同步摘要副本。
4. 同样只改 artifacts.gate1_decision_sha256 为全 0，并同步摘要副本。
5. 把 artifacts_version 改为 UNSUPPORTED-VERSION，并同步摘要副本。

这些探针没有修改 workflow、normalized、load_report 或数据库事实。摘要两处相等，不代表摘要声明与被引用事实相等。补齐 artifact 文件字节引用，并按本版本实际生成的固定字段逐项验证版本、前序、Gate1 决定、数据库、normalized、host_manifest 等声明，不能只修一个探针字段。

证据：data/reviews/task011_20261011_133022/F03_*.call.json。
副本路径与同步步骤完整记录在 independent_results.json；它们是新 QA 造样，不宣称重新通过真实上游计算。

## 5. F04：调用计数漏报（P2，测试/回执）

已直接从本次所有接收清单去重确认：

- 带宿主 receive_invocation.json 的接收：14 次。
- G4 的 plain_receive 另外通过真实 _run_receiver 启动一次，没有宿主调用记录；测试先加 1，随后用宿主记录扫描的 14 覆盖了总数。因此该入口实际 receiver 共 15 次。
- 15 个不同接收身份的 checker_invocation.started 全部是 true，包括非 ZIP 的 runtime_failed 和 plain_receive。checker 实际启动共 15，汇总却为 13。失败不等于没有启动。
- 进程内 normalize/load 的 3/2 也漏掉了 G6 wrapper 直接调用 real_normalize/real_load 的各一次；该口径下至少应为 4/3。CLI 进程内次数未观测可以明确列未知，但不能用“可观测”解释已在本进程发生却绕过计数器的调用。
- 私有 _run_receiver 不应计为“公开宿主 API”；blocked_rejections=0 是未维护字段，不能冒充没有阻断。

对应 tests/test_prepare_demo_gate2.py 的 G4、G6、audit_starts 与最终覆盖计数的代码。补齐测试侧逐调用记录与一一对应核对，不改变生产接收器或上游以迁就计数。旧回执保留，新回执纠正。

## 6. 独立验证范围与保护

GPT QA：data/reviews/task011_20261011_133022。

额外有界观察 10 项：正常小样 1 项成立、9 项未满足（分属 F01/F02/F03）；另有 F04 的独立清单审计。额外公开宿主 API 调用 24 次、真实 receiver/checker 各 1、真实标准化/装载各 3；这些与交付回归的计数分开。脚本退出 0 表示成功保存观察结果，接受与否由 requirement_satisfied/unmet_cases 记录，不能把探针脚本退出 0 写成要求全部成立。

全部反例只作用于本轮全新批次/数据库副本或测试内依赖 wrapper；生产文件、上游、历史证据未修改。这是协议自洽与普通变化检测，不是防恶意篡改测试。没有重跑 TASK-002—010 整套历史测试。

## 7. 下一步

主理人无需手工测试或批准 Gate。转交本单与 docs/tasks/TASK-011-R1.md，DeepSeek 只修本轮四组缺口，回执后停住。TASK-012 暂不下发。

