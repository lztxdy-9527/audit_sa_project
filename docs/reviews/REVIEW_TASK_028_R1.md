# TASK-028-R1 复审：部分关闭，残余未通过

日期：2026-10-15。结论 **NOT_ACCEPTED**，TASK-028/R1 暂不关闭，不推进 Gate2。仅复验本卡边界，未修改实现/测试/指南，未调用子 Agent，未重跑执行端 31 项或原 42 项完整入口。

证据根 `data/reviews/task028_r1_gpt_20261015_185902/`。四份交付身份与交接一致：runtime_gate1.py 151837 B / `d6c8b3a04003e527662b9dddf7ac9500331245e9fb84373b87a1804e791a4020`；新测试 57220 B / `fe33806303a5092b5b0bc69c1e4860b41ce152145f2a6b269c2e3cea1f729c06`；指南 13765 B / `074e97c1c0e07621cf7e8d6a4ae886a6a11f98e12f6d189b376f4f926593c0ec`；R1 回执 7671 B / `222103bb76a6aac3d14273b6d1a988f6be7de51c377142570ff7e4df9bcf1e01`。

## 1. 已独立关闭的项

新正常登记/已登记 APPROVE 夹具事件，真实标准化/装载各一次；只读 inspect 成功，四表实查 2/1/3/3。干净隔离场景中：

- inspect 实际最后必要消费后数据库 LF、context LF、decision_result LF，本次均定位拒绝，撤销 wrapper 后保留变更仍拒绝。此前“末端重新取值与自身比较”的三反例关闭。
- started 错批次、artifacts 错登记 SHA/错 Gate1 指纹、报告 round_trip_exact=false、实际数据库删 allocations 后只同步外层 SHA，均被各自目标校验拒绝。SQLite 实查及这些身份关系关闭。
- 实际 mkdir OSError 被映射为 RuntimeGate1Error，已建 load_dir 留 failure，数据库叶未建。真实 NormalizationBlocked/SqliteLoadBlocked 已分为本层 Blocked + kind=BLOCKED；分类基本路径关闭。

以上来自 GPT 实际调用，不用执行端自报追认。下一卡不重做已关闭大组。

## 2. B1 残余：核心前事件复确认、报告 writer 缓冲绑定

`pre_event.json`：真实 started writer 返回后，只给本次新事件 context.json 加一个 LF。当前 run 在校验不再有效的事件字节下，仍实际调用 normalize 和 loader 各一次，直到后续 reverify 才 Blocked。原卡要求每个计算核心调用前复确认已消费 Gate1/来源/登记；代码只复确认部分批次与登记，漏掉事件八文件。

`report_readback.json`：真实 load_report writer 写完返回后，将落盘报告 round_trip_exact 从 true 改为 false；两核心真实返回保持原值。run 仍返回 RT_NORMALIZED，无失败诊断；下一次 inspect 才拒绝。report_capture 未与本次 report_buffer 相等比较，artifacts 接受了较晚被改写文件的 SHA。

这两项是上一卡明确要求的残余。末端发现无效材料不代替“调用前阻断”；较晚 capture 不代替真实 writer 缓冲绑定。

## 3. B2 残余：helper 未用于目标字段，恢复未绑定输入

`probe_summary.json` / `api_records.json` 的干净隔离反例仍被 inspect 接受：

- artifacts.database.byte_size 整数→同值 float。新增 `_require_nonneg_int` 没有用于该字段，仍以 Python 数值相等判定。
- normalized.source.input_sha256 改为另一合法 64hex，同步 report.source、run_metadata 两摘要、normalized 文件 SHA/规范指纹及报告文件 SHA。inspect 调 `_validate_load_report` 未传已有 workbook_capture，输入字节绑定分支被跳过。
- normalized.source 增未知键，同步直接外层指纹/报告 source，仍成功。当前没有该对象封闭键核验。
- load_report.net_checks.master_net_equals_normalized=false，同步报告文件 SHA，仍成功。目前只要求 net_checks 是 dict，没有要求冻结成功旗标齐备且严格 true。

恢复需复用本次已有工作簿 capture；修复只做字段/类型/冻结成功旗标核验，不要求重写数据库金额勾稽。上述库内实际行数核验已经通过，不重复派发。

## 4. B3 残余：reasons 未保存、诊断未完整校验

`error_summary.json`：两个真实冻结 Blocked 异常均带两项不同原始 reasons。API 的原异常对象仍有列表，但 failure.reason/cause_chain 只留 str(exc)，两项 reasons 全部丢失。R1 卡明确要求原因完整可追溯，不能只检查类名出现。

静态核对：`_call_frozen_entry` 按类型名称字符串分类，与注释所称“实际模块真实类型”不一致；failure 恢复只检查 kind/键集，没有核验 failure_version、stage/field/reason/cause_chain 的类型。此为同一错误处理小尾项，不需重跑 writer/loader 大组。

## 5. E1 残余：实际终端仍漏台账，反例与观察证据被遮蔽

三个真实新进程调用 actual main 的 replay 分支，源文件未变，未重复业务链：normal 0/PASS；真实 audit_candidate 返回后台账加 LF，仍 0/PASS；最后一次 failures 读取返回原值后 checks 加 LF，仍 0/PASS。见 `cli_post_audit_ledger.json`、`cli_post_terminal_checks.json`。R1 的 ledger-lf 在初次读取前注入只能证明早期检查；当前终端循环仍未包含台账，打印前仍读取 failures。因此交接“末次确认后不再读候选”与实际代码不符。

读取 R1 既有 checks/API 证据（未重跑）：B2 场景连续累积篡改，后续反例没有恢复干净基样。

- “错 artifacts.registry”被 started.batch_id 拒绝。
- “错 Gate1 指纹”被 artifacts.registry_file_sha256 拒绝。
- 后续 round_trip/删 allocations/source 错 SHA/未知键均被 artifacts 缺键提前拒绝。
- 所谓“删 allocations”改的是 normalized.records，不是数据库表；所谓“同值 float”实际上删除了 Gate1 指纹键。
- B1 inspect 三项在调用前就改盘，不是原卡要求的“该次最后消费之后”注入；晚未知项也改为调用前移走 normalized 文件。

所以 31 项 PASS 不能代表这些目标路径已经执行。GPT 本轮用真正隔离反例证明了部分实现已修，但执行端证据需定点更正，不能回写旧结果凑一致。

计算核心观察器仍只记录工作簿 input_before/after，未记录同一 quality_report/normalized 引用的前后与 API 收尾规范指纹，核心异常也无完整 traceback/reasons。生产拒绝同引用改写是有效实现控制；它不能代替测试观察器自身对三时点变化的辨识度证据。

## 6. 流程、保护与下一步

版本常量仍为 TASK-028-runtime-gate1-1.0，与交接 1.1 不符，登记为非阻断标注问题，下一卡顺手同步。看板未逐项勾选仍为非阻断流程事项；不要求为勾选重建业务链。

一次最终保护比较见同根 protection_result.json：技术判定与文件范围分开。139 历史损失单列，27 恢复、326 越界和旧偏差保留。NOT_ACCEPTED 基线只用于后续定点起点。

下一步仅 docs/tasks/TASK-028-R2_DRAFT.md。不推进 TASK-029/Gate2；真实批准 null、开发宿主 0008、next/AI=false，夹具记录不批准任何批次。
