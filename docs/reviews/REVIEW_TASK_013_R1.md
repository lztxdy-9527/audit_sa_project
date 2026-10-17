# TASK-013-R1 独立验收：CHANGES_REQUIRED

日期：2026-10-12。验收：GPT。结论：**暂不通过，不推进 TASK-014**。新增 `docs/tasks/TASK-013-R2.md` 收窄修复；GPT 未修改宿主、测试或指南。

## 1. 已确认通过的部分

GPT 用项目 Python 3.11.1 在全新 `data/workflow_host_tests/task013r1_gpt_20261012_052724` 容器重跑交付入口；以 QA 内存包装独立观察真实入口，没有修改交付测试/生产文件。源文本编译通过，完整入口退出 0、failures=[]、10 条持久化检查全 PASS，独立的 FINAL_ARTIFACT_READBACK 成功。交付 final/verify 与 GPT 三容器的计数逐项一致。

独立实际入口计数为公开宿主 API 8、控制器 94（create 0 / prepare 10 / record 20 / check 64）、筛查核心 5；CLI screen-rules 19=成功 14+拒绝 5，接收/checker 22/22。CLI 子进程内部核心次数仍属未观测；未当成直接实测数。

MAIN 12 条线索（3/5/2/2），R02 超额 1,600,000 分；原退款、分摊、缺失关联口径不变。每容器 19 份 0005（18 可解析、1 故意半写），0 份 0006；可解析凭证前序等于 0004 实读字节 SHA、workflow 与 0004 严格相等，phase=DEV_GATE2_APPROVED、两条模拟决定、真实批准 null/null、next_step_allowed=false。

独立小样复现确认原 R1 的引用检查六项通过：固定 report_relative、manifest 字节哈希、artifacts/started 宿主版本、完整内嵌 artifacts 与磁盘一致及形状检查。失败记录身份四项通过，恢复合法完整后失败诊断仍退出 2、复现 sentinel。报告自身在**实际最后一次报告读取返回原缓冲之后**被改，本次能退出 1、后续拒绝、恢复后通过。

MAIN 宿主该次核心真实返回与落盘报告精确相等；5 份核心返回证据文件哈希可核验。真实 writer 完整待写文本、40 字节半文件、旧 0001—0004 调用前/句柄关闭后两组哈希、sentinel traceback 均已落盘；正式共用缺记录/未登记审计自测也已改善。以上均保留。

## 2. F01 [P1] 合法筛查前状态无法 status 恢复

位置：`scripts/run_demo_workflow.py:2510` 与 `:2566`（当前交付版）。`screen_expected` 仅在 revision >= 5 分支赋值，分支外无条件读取。

GPT 实际新建两条 C06b 小样链，在 0001、0002、0003、0004 各节点真实调用 inspect，8/8 均意外退出 2：

```text
[status] 意外运行失败：UnboundLocalError:
cannot access local variable 'screen_expected' where it is not associated with a value
```

另对交付 final 容器的 Gate1 pending、Gate2 pending、HELD、REJECTED 只读运行四次新进程 CLI，4/4 同样退出 2。这些是合法可查看状态，应 status=READY/退出 0 并报告真实动作允许值；停止态能读取不意味着可继续执行。

原 G3 只测“不允许筛查”，未测这些节点能否正常 status，故全套 PASS 未暴露回归。修复变量生命周期/分支，新增各节点正向恢复断言，保留非法输入的阻断分类。

证据：QA `stage_recovery_observations.json`、`independent_calls.json`、`supplemental_results.json`。

## 3. F02 [P1] 最终报告消费后，Gate2 材料与旧链仍能变化而本次成功

位置：`scripts/run_demo_workflow.py:2504`、`:2518`、`:2568`。全集 `_verify_gate2_tail` 位于最后一次报告消费之前；最后新增的 `_verify_screen_tail` 未包括 Gate2 JSON、manifest 与旧 checkpoint 等全集。

GPT 在新建专用小样第二次 `_read_screen_outputs` **返回原缓冲之后**分别注入一次，真实前后字节 SHA 不同：

- P09：给 `workflow/gate2/load_report.json` 追加一个换行，本次 status **READY/0**；撤销 wrapper 后再次 status 才退出 1，原因 `artifacts.json.load_report_file_sha256`。恢复原件后通过。
- P10：给 `workflow/checkpoints/0001.json` 追加一个换行，本次 status **READY/0**；下一次才因 `0002.json.previous_file_sha256` 退出 1。恢复原件后通过。

这两项是 R1 卡“最后一次控制器调用与最后一次数据消费之后核验全部已消费材料”的剩余缺口。报告自身已能拒绝，不能代表所有已消费材料已覆盖。

只需统一收尾时点/全集覆盖；保留初始读数和真实 writer 哈希，不事后替换预期，不增加自动重试。按 R2 卡用一个小样串行恢复三个方向即可，不要求原子快照、并发隔离或无边界 fuzz。

证据：QA `independent_results.json` 的 P09/P10，完整实参/返回/原因见 `independent_calls.json`；报告本身的真正后缓冲正向修复证据见 `supplemental_results.json`。

## 4. F03 [P2] 报告边界探针时点与完整故障记录仍不准确

当前测试 `:1044` 起的 F01 wrapper 包装首次 `_verify_screen_tail` 返回，宿主在此之后才执行第二次 `_read_screen_outputs`。记录却声称“最后一次报告读取原缓冲返回之后”。实际异常来自后续读取指纹比较，尚未在该测试中证明最后一次消费后的检查。GPT 用真正读取返回处另行包装，已确认报告自身能拒绝；应修正探针，不能继续依赖错误时点文字。

`probe_records/g6_tail_0005_change.json`、数据库/快照方向及报告方向仍主要是 helper 名称、消息、哈希，缺实际公开宿主调用的 args/kwargs 与完整异常链/traceback。数据库/快照方向也未把撤销后新进程及恢复原位正向闭环存入对应记录。17 个文件的数量不等于完整现场；本轮只补这些现有 G6 与新增有限探针，不要求重写全套测试。

summary 对完整记录的引用补文件字节 SHA，保持消息摘要有可核验全文来源。控制器分列、正式缺记录自测、writer 完整文本和旧凭证前后哈希已改善，保留。

两项交付元数据需在**新**回执更正，旧回执不回写：

- 旧回执正文宿主哈希为 `95b2a2…`；实际宿主、用户交接消息和 final/verify 容器绑定均为 `115253…`，因此未据此认定代码与测试版本失配。
- final 容器 writer 文件实际为 14,223,740 字节，SHA-256 `bd287093d53bd2fe6b869f97d70ba9e5e101ee3721fc9637b5bf46618f9b1a32`；旧回执/消息的 14,223,730 / `092938f5…` 与最终现场不符。verify 容器路径长度不同，实际字节数也不同，不要求跨容器 writer 字节数相同。

## 5. 保护、证据与交接

主基线 `data/reviews/task013_20261011_194832/source_hashes_after.json`（58748）恰有宿主、当前测试、指南三项授权变化、缺失 0；TASK-012-R2 累计两项、TASK-012-R1 累计三项，其余按原累计授权集合逐条核验，所有不应变化的历史基线与冻结上游保持。完整差异记录在本轮 QA `protected_files_comparison.json`。

当前实际交付哈希：宿主 `115253956e4fbcccbc096af3d673b081f42b9d0fe9bc587f536151297bd9eec4`；测试 `14e96b7567ea6cab0ba9fd13d48a25b2f928fefb80517155f245a30e3c44c000`；指南 `f2bbb6faae16647023abf789a2e611012023ff73b856fa096ddcf5a475f47345`；回执 `a1ee993dbd421674758c19eda7cc08a093e8a283a0a57578e105b7efc10fd2ec`。

本轮 GPT QA 根目录：`D:\harness work\audit_sa_project\data\reviews\task013_r1_20261012_052724`。独立有限收集器 23 项中 13 符合预期、10 不符合（8 个合法节点恢复+2 个晚变更），另有真实后缓冲报告检查通过和四次合法节点 CLI 失败复现；53 次独立 API 与四次 CLI 分开记录，不混入交付全套计数。收集器退出 0 仅表示证据保存成功，不表示验收通过。

修复交接为 `docs/tasks/TASK-013-R2.md`，仅三个既有文件+新回执与新现场；新主保护基线为本轮 QA `source_hashes_after.json`。修完等待 GPT 再验收。

真实批准 0；未执行独立规则复算、事实底稿、人类判断、AI、正式契约或 TASK-014，未重跑 TASK-002—012 整套旧入口。保持当前开发状态和 0005 边界，不新增 0006。
