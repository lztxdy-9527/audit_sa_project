# TASK-010-R3 复验：宿主功能通过，剩 writer 测试证据

整体结论：**CHANGES_REQUIRED，仅剩 F05 的 writer 证据**。宿主开发功能本轮通过，冻结 `scripts/run_demo_workflow.py`（v1.3，SHA-256 `d42aeec3a4450d630507821e103e5b923c052e91e790644df143f5311e9475d0`）。F03 关闭，F01/F02/F04 不重开；暂不推进 TASK-011。

主理人无需手测或批准 Gate，转交本单及 TASK-010-R4 即可。下一轮只修改测试文件，不再修改宿主核心或指南。

## 1. 本次已通过的部分

交付测试/指南哈希前缀 `e9554ca7 / 2c164eff`。GPT 未修改交付文件，在 `data/workflow_host_tests/task010r3_gpt_20261011_123002` 完整重跑入口：退出 0，十组 PASS，失败 0。

另外实际执行 20 个独立观察，**全部满足**：合法 pending/模拟批准及恢复；接收命令长度、值、类型三种矛盾的 status/record 拒绝；H01 质量报告读失败、H02 接收清单读失败均保留实际 receiver=0，status 恢复宿主运行失败 2；H03 清单声明矛盾保留原观察值，status 恢复协议诊断 1；失败批次不能保存决定；真实 writer 部分写入/OSError、旧 0001 字节不变、半文件恢复拒绝。

最终 summary/checks/cli_logs/count_audit 读回一致；计数缺留痕自测与故障类别/原因自测均通过。当前可读取清单确认 checker 16 次，H02 保留的原清单还能确认 1 次，实际启动共 17 次；receiver 17、测试副本 17。回执中的 16 应理解为当前可读清单的可见数，在新回执区分可见数与实际总数即可，不单独阻断。

## 2. 唯一剩余组：writer 的前后保护证明仍有假阳性

交付测试 `tests/test_run_demo_workflow.py`：

- 第 1134 行先调用 `record_simulated_gate1_decision`。
- 第 1160、1161 行随后连续读取 `old_0001_before`、`old_0001_after`。

两次都是操作结束后的取值，无法证明操作前后字节未变。

GPT 使用**全新 QA 文件副本**执行交付测试的原始赋值/判断 AST：先保存真正操作前哈希，再改变该新副本，随后运行上述两次事后取值。真实前后哈希不同，交付 `real_fault_ok` 却仍为 true。这一反例只验证测试判断逻辑；独立生产调用已确认宿主未改旧 0001。

同一块中 `expected_checkpoint_text` 使用 `workflow={}` 和不完整 operation，实际只算了 368 字符的简化对象下界，不能充当该次完整预期 checkpoint 的字节大小。真实部分写入 40 字节已证实，仍需按上轮要求保存该次真实完整待写内容的字节数。

这两项都属于原定 F05 证据要求：把前哈希移到故障调用前，捕获实际 write 收到的完整文本及 UTF-8 字节数，移除占位对象，再做一次有限回归即可。不重写已通过的宿主逻辑。

## 3. 证据、保护和停止

GPT 目录：`data/reviews/task010_r3_20261011_123002/`。

- `regression_execution.json`、stdout/stderr：完整入口重跑。
- `independent_results.json`：20 个观察、16 次公开宿主 CLI、4 次宿主 API；额外真实接收 3 次、五份测试副本，全部满足。逐案完整输入/变更/输出/异常链同目录保存。
- `artifact_audit.json`：最终文件一致性、自测、原始清单与保留备份去重核对。
- `writer_proof_counterexample.json`、`before_after_counterexample/`：真正前后哈希、交付事后取值、交付判据错误地通过；全部是新的 QA 文件。
- `acceptance_summary.json`、`protected_files_comparison.json`、`source_hashes_after.json`：本轮结论与下轮保护基线。

本次验收前后既有文件 0 变化、0 缺失；相对 21691/18533/16340 基线仅交付核心/测试/指南三项累计变化，14691/13330/12546/10236/8547/6511/4902/874 基线全部不变。GPT 仅新增验收脚本/证据/本单与任务卡。

GPT 适配新探针时曾将转义换行误写为源码换行，执行前检查发现并修正，错误版本未运行，交付文件未受影响。

未建立契约、未批准真实 Gate、未预填人类判断、未运行标准化/SQLite/规则/底稿/AI、未重跑上游整套测试或做无边界 fuzz。TASK-011 等唯一剩余测试证据补齐后再出卡。
