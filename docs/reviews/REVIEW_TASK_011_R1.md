# TASK-011-R1 独立验收：仅 F02 剩余一项

结论：**CHANGES_REQUIRED，暂不通过。**F01、F03、F04 关闭；F02 仅剩 checkpoint 初始读取与预期字节哈希未绑定的问题。不推进 TASK-012，不增加新功能。

## 已确认的修复与复跑

GPT 未修改宿主、测试、指南或上游代码。使用项目 Python 实际执行：

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_prepare_demo_gate2.py' --out-dir 'D:\harness work\audit_sa_project\data\workflow_host_tests\task011r1_gpt_20261011_142537'
```

退出 0；原 G1—G9 与 G10 共 10 组全部 PASS，failures 为空；summary/checks/cli_logs 内容一致，final_readback 与两项隔离自测通过。GPT 新容器和执行端 final、verify 容器的检查名称、结果与计数一致。

计数独立核对：CLI start/status/record/prepare 为 23/34/21/9；公开宿主 API 16、私有探针 1、控制器 19；按真实命令身份去重得到宿主接收 23，另有 plain_receive 直接接收 1，共 24；按 batch_id/received_at_utc 区分接收身份得到 checker started 24，包含 C12 与非 ZIP 运行失败样本。进程内 normalize/load 11/10；CLI 内未观测值为 null，推导 6/6 分列。副本 16、故障注入 27、模拟决定 20、真实批准 0。拒绝 37 与实际 CLI 非零退出记录相等，审计 missing/unregistered 均为空。

原 40 字节 writer 故障的完整待写字节、哈希、sentinel 异常链和旧 0001/0002 前后哈希，在三组容器中逐项核验一致。

额外独立探针共 11 项：10 项满足预期，1 项暴露以下剩余缺口。这些观察独立于入口的十组回归，不把探针脚本退出 0 当成产品通过。

- F01：真实 writer 写完完整 0003 后抛错，正常恢复返回 2，并复现失败诊断；畸形 failure 与半文件回归也保留。关闭。
- F03：artifacts 文件字节引用、数据库/标准化/Gate1 指纹与版本等目标语义检查生效。关闭。
- F04：真实启动、失败调用、副本排除及不可观测次数分列已修正。关闭。
- F02：原数据库/报告晚变更以及 prepare 第二次重放改报告的独立探针均已拒绝；checkpoint 的预期哈希取值时点仍需修复。

## 唯一阻断项：F02 checkpoint 读取对象与哈希不是同一初始字节

定位：scripts/run_demo_workflow.py 的 `_load_checkpoint_chain()`，当前第 642 行先 `_read_json(entry, …)`，第 687 行重放 Gate2 操作，至第 691 行才重新读取文件计算 `file_sha256(entry)`。

状态恢复消费的是第一次读取的旧对象，但链和收尾使用重放后的新文件哈希作为“预期值”。因此发生一次普通文件变化时，会把变化后的哈希当成基线。

GPT 精确复现（仅在新 QA 副本）：

1. 从新 C02 成功批次建立路径重绑定副本；复制数据库并用冻结控制器重建材料引用，不宣称重新接收/标准化/入库。未变化正向 status 返回 READY。
2. 包装冻结控制器 `prepare_dev_gate`：先执行真实重放，在返回后仅一次将磁盘 `0003.operation.materials_sha256` 改成 64 个 0。此时宿主已解析旧 0003，尚未保存该文件的预期字节哈希。
3. 本次 `inspect_dev_batch` **返回 0、READY**，仍返回旧有效 workflow，却报告变化后的 checkpoint 哈希。
4. 撤销 wrapper 后，正常 status 返回 1，明确指向 `workflow/checkpoints/0003.json.operation.materials_sha256`。

before = `289ed646fca3f9080c95ed6ef778edc50feafd2a589e5a5f1c1347a2ab1be88d`；after = `8e0de6863ccdc04a40347d5523acdcc7834bf7df570d8a7c6def0c074dae12af`；注入命中 1。

这属于 R1 卡 §3 已要求的“相关 checkpoint 与本次初始读取值一致才能返回成功”，没有增加安全隔离、并发锁或无边界 race/fuzz 要求。READY 在此只代表宿主恢复成功，**并未发生 Gate2 放行**；真实批准仍为 null。

最小修复：每份 checkpoint 从同一次初始 `read_bytes` 得到 JSON 对象及该字节缓冲的 SHA-256，链引用与收尾均保持这一初始哈希。不得在控制器重放之后重新取值覆盖预期。尾部继续重测磁盘并拒绝变化。

## 非阻断文案记录

旧回执两处引用 `count_audit.json`，final/verify/GPT 新容器均无该独立文件。实际审计位于 `summary.json` 与 `checks.json` 的 `G9_SELF_TESTS_AND_COUNTS.count_audit`。数值可核验，因此不重新打开 F04；下一份回执引用真实位置，旧回执不回写。

## 证据与边界

GPT QA：`D:\harness work\audit_sa_project\data\reviews\task011_r1_20261011_142537`。

- regression_execution.json / regression.stdout.txt / regression.stderr.txt：新入口实跑。
- independent_results.json：原九项独立观察，unmet 为空。
- late_prepare_probe.json：原 prepare 晚变更探针通过。
- checkpoint_timing_probe.py / checkpoint_timing_probe.json：唯一剩余反例、正向、完整本次返回、后续拒绝、注入时点与真实前后哈希。
- artifact_audit.json：三容器计数与 writer 逐项核对。
- protected_files_comparison.json / acceptance_summary.json：完整保护结果及交付物哈希。

主基线 task011_20261011_133022 的 28489 项仅三项授权变化、缺失 0；本轮 GPT 验收前已有文件零变化。旧 test_run_demo_workflow.py、冻结上游、旧批次和 GPT 证据保持不变；更早基线按各自起点报告累计授权变化。

本轮 GPT 额外探针公开宿主 API 27 次、真实接收/checker 各 1 次、实际 normalize/load 各 3 次、纯控制器副本重建 8 次、副本 10 份，单独统计，不并入执行端回归计数。

未重跑 TASK-002—010 整套历史测试；未实现 Gate2 决定，未执行规则/复算/底稿，未建立正式契约、真实审批、人类判断或 AI 建议。执行端只领取 TASK-011-R2，主理人无需手工测试或批准 Gate。
