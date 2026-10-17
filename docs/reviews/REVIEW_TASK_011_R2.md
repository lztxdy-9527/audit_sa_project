# TASK-011-R2 独立验收：通过，TASK-011 功能缺口关闭

结论：**ACCEPTED。**F02 的 checkpoint 初始读取/哈希时点缺口已修复，F01/F03/F04 的已验收行为保留。可以领取 TASK-012，只实现 Gate2 模拟决定保存与状态恢复，不执行筛查。

## 实际复验

GPT 未修改宿主、执行端测试、指南或冻结上游。使用项目 Python 新容器实跑：

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_prepare_demo_gate2.py' --out-dir 'D:\harness work\audit_sa_project\data\workflow_host_tests\task011r2_gpt_20261011_150713'
```

退出 0；G1—G9 与 G10 共十组全部 PASS，failures 为空；summary/checks/cli_logs 一致，final_readback 和两项隔离自测通过。执行端 task011r2_02、其 verify 容器及 GPT 容器的组名、结果、入口登记计数一致。

R2 代码检查：新增 `_read_json_with_bytes` 从一次 read_bytes 得到同一缓冲的 JSON 和 SHA-256；链、前序引用、current 元数据和尾部预期均使用该初始 SHA。原来重放后的 `file_sha256(entry)` 已移除，循环后复测全部 checkpoint。实现版本 1.2，持久化形状未扩展，协议仍 1.1。

GPT 原反例在全新 QA 副本重新执行：正常 status 成功；真实 Gate2 重放返回后只一次改磁盘 0003.operation.materials_sha256，本次即 WorkflowHostBlocked/退出1，原因包含具体 checkpoint 路径、初始预期/实际哈希与字节变化；撤销后正常 status 仍按 materials_sha256 语义错误拒绝。已满足“本次拒绝”，不是只在下次发现。

原九项额外独立观察全部满足预期，prepare 第二次重放改报告的探针仍拒绝。共十一项额外观察，满足11、未满足0，独立于入口十组回归。

## 材料、计数与保护

按真实接收命令身份去重：宿主接收24，另直接接收1，共25；checker接收身份25，started均true，包含质量阻断和非ZIP运行失败。副本不重复计算。实际CLI退出记录与拒绝38相等；一一对应审计missing/unregistered为空。

入口登记值：CLI start/status/record/prepare=24/35/22/10；私有探针1；控制器造样/探针登记20；进程内normalize/load=11/10；CLI内部未观测null，推导7/7分列；副本16、故障注入28、模拟决定21、真实批准0。40字节writer故障的完整待写字节/哈希、sentinel异常链及旧0001/0002真正前后哈希逐项核验。

**非阻断统计注记**：入口的 `host_api_calls=16` 没有包含 `status_inproc` 进入 `inspect_dev_batch` 的5次调用，全部进程内公开API实际为**21次**。GPT另用新容器、运行时profile记录每次公开宿主API进入，该入口也退出0、十组全通过；逐次记录保存在 `public_api_count_audit.json`，CLI子进程不混入其中。此问题是开发测试汇总标签/计数范围遗漏，不影响决定协议、金额、材料或实际接收/checker核验；不再追加TASK-011修复轮。旧测试/回执冻结，在TASK-012新入口统一观察公共API（包括helper）并如实分类；不得继续把16当总数。

保护：相对task011_r1基线34813项仅宿主/测试/指南三项授权变化、缺失0；本轮GPT验收前已有文件零变化。相对task011原基线三项累计变化；task010_r4两项累计，更早task010各版本按历史三项累计；14691/13330/12546/10236/8547/6511/4902/874全零变化、零缺失。完整结果与文件SHA见 acceptance_summary.json / protected_files_comparison.json。

## 交接与停止边界

主证据：`D:\harness work\audit_sa_project\data\reviews\task011_r2_20261011_150713`。

- regression_execution.json：完整入口命令与退出码。
- independent_results.json / late_prepare_probe.json / checkpoint_timing_probe.json：独立探针及完整返回/异常、真正前后哈希。
- artifact_audit.json：执行端final/verify与GPT容器的计数、writer和最终输出核验。
- public_api_count_audit.json：额外测试侧运行观察，CLI子进程不混入进程内API次数。
- acceptance_summary.json / protected_files_comparison.json / source_hashes_after.json：验收与下一任务保护基线。

GPT额外定向探针单独统计：公开宿主API27、真实接收/checker各1、实际normalize/load各3、纯控制器副本重建8、副本10。计数观察容器是另一整套入口实跑，单列，不混入这些定向探针。

本阶段停在DEV_GATE2_PENDING：无0004、无Gate2决定接口、真实批准仍null、next_step_allowed=false。未建立正式契约、未执行规则/复算/底稿、未保存人类判断或生成AI建议；未重跑TASK-002—010整套历史入口。

下一卡：`docs/tasks/TASK-012_DRAFT.md`。主理人只转交本验收单和任务卡，无需手工检测或签署Gate。
