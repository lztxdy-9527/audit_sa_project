# TASK-028-R2：只修 R1 残余，保留已关闭项

类型 B，DSH 定点执行，GPT 复验。依据 docs/reviews/REVIEW_TASK_028_R1.md。不得把本卡当成下一功能卡；完成全部交付再 in_review，done 仍由人类操作。

## 1. 起点与允许范围

先只读核对评审和 `data/reviews/task028_r1_gpt_20261015_185902/review_result.json` / 同根 source_hashes_after.json。NOT_ACCEPTED 不等于通过。只允许修改：

- scripts/runtime_gate1.py：151837 B / `d6c8b3a04003e527662b9dddf7ac9500331245e9fb84373b87a1804e791a4020`。
- tests/test_runtime_approved_load.py：57220 B / `fe33806303a5092b5b0bc69c1e4860b41ce152145f2a6b269c2e3cea1f729c06`。
- docs/RUNTIME_APPROVED_LOAD_GUIDE.md（必要时）：13765 B / `074e97c1c0e07621cf7e8d6a4ae886a6a11f98e12f6d189b376f4f926593c0ec`。

新增 docs/EXEC_REPORT_028_R2.md，仅在下列明示新根保存测试/运行/事件/数据库：data/runtime_approved_load_tests/task028r2_<轮次>/、data/runtime/task028r2_<轮次>/、data/human_gate_decision_records/gate1/task028r2_<轮次>/、data/sqlite_tests/task028r2_<轮次>/。scope 可在本轮记录根内设技术子目录。只读复用已有小样；不授权新接收、不写旧根或旧 harness、不清理现场。

冻结 TASK-026/027 测试/指南、准备器/P1/store/normalizer/SQLite/schema、契约/生效登记/配置/宿主及全部旧证据。按已知身份核对。139 损失、27 恢复、326 越界、旧偏差保持。禁止递归删除/移动。身份不符或必须改冻结件/扩大架构，停止升级。

补丁版本同步为 TASK-028-runtime-gate1-1.2；两个新 API/六键外层/四文件/六键 failure/八 false/单次模型保持，原五 API 前提不放宽。已关闭的 inspect 三处末端字节、SQLite 实查、mkdir 与基本异常分类保留；不重做通用框架。

## 2. B1 两个遗漏接线

1. 两次计算核心调用前复用已有 `_recheck_capture`，检查起始 Gate1 八文件、来源和登记读数；不得用新 capture 覆盖预期。最少：真实 started writer 返回后只给本次新事件 context 加 LF → 本次 Blocked，normalizer/loader 增量均 0、有效 failure、坏现场保留。可用正常加载后/loader 前同接缝一例证明第二调用前检查，不再遍历八文件。
2. load_report 写后 capture 与该次 report_buffer 必须字节精确相等，之后才准内嵌其 SHA。最少：包装真实 writer，完整写 load_report 后返回前把 round_trip_exact 改 false → 本次 Blocked/有效 failure，坏报告保留；实际核心返回仍是 true 并单份保存。不要改核心返回冒充磁盘变更。

一个新正常小样各核心一次+只读 inspect 0 计算调用作连带对照即可；不重跑已关闭终端大组。

## 3. B2 三处恢复值检查及封闭对象

- artifacts.database.byte_size 在比较前调用已有严格非负整数 helper；同值 float/bool 均拒绝。
- inspect 已有 batch_captures[WORKBOOK_RELATIVE]，将其传给 `_validate_load_report` 的 workbook_capture，不能保留 None 分支跳过本次输入绑定。
- net_checks 使用冻结实际返回的固定键集合，每值严格 true；不新增勾稽算法。normalized.source 使用冻结实际返回形状封闭键与字段类型，并核对已绑定 input/checker/spec 身份；不凭路径包含子串或 str() 强制转换认定来源。恢复不调用 normalize/loader；可复用冻结纯校验辅助，不复制全算法。

最小隔离反例：同值 float byte_size；source.input_sha256 改另一合法 SHA，并同步 normalized 指纹、报告 source/metadata 指纹及直接外层 SHA；source 未知键并同步直接外层；net_checks 一项 false 并同步报告 SHA。每例开始前必须是干净正常可恢复基样，拒绝 field 须命中该例目标，不接受“任意异常”。正常 canonical 键序变化对照保持。

## 4. B3 原始 reasons 和有效诊断

实际模块类对象 `isinstance` 分类，不按相同类名字符串代替类型身份。`_core_reason`/原因链保留 `.reasons` 完整列表，可嵌入现有 reason/cause_chain，仍六键，不另造协议。failure 恢复逐项检查版本常量、kind、stage 非空字符串、field 为 null 或定位字符串、reason 非空字符串、cause_chain 为合法字符串列表；先验类型再消费，失败不写。

只需两个真实 Blocked 类各带两项不同 reasons 的受控映射控制，确认 API cause 与磁盘诊断均可追溯这两项；一个错误 failure_version 或字段类型恢复反例。不重跑已经关闭 mkdir/writer/发布后错误大组。

## 5. E1 收尾两漏点及反例/观察证据修正

不要再增加一个早期读取就宣称“末端确认”。将当前 finish 的最后确认明确覆盖七载荷（六证据+diagnostic）及 file_ledger 自身确切字节，预期来自本次 writer 缓冲。所有必要解析、内容审核、失败集合与输出对象构造前置；末端只读字节，随后不再读 failures/summary/ledger 构造成功输出。可参考已验收 TASK-027 finish 的次序直接小改，不新增一套框架。

新进程 actual main/CLI，复用同一次真实观察的新副本：normal 0/PASS；真实 audit_candidate 返回后 ledger LF → 1/磁盘FAIL/非空failures；原最后 failures 读取后 checks LF 的等价“实际最后必要消费后”接缝 → 1/FAIL；返回值替换 → 1/FAIL。若修复删除了旧读取，先无注入观察新的最后消费点再注入；不靠 mutate 标志直接返回。坏字节不回填，期望不刷新，不重建台账。

计算核心观察器补同一 quality_report/normalized 引用的调用前、真实返回后、所属 API 收尾指纹，以及完整输入快照/真实返回/完整异常 traceback+cause+reasons；工作簿字节前后另列。辨识度控制必须经实际观察器记录到的变化驱动同一正式 audit 拒绝，不能以生产 Blocked 代替观察器证明。只补本层两核心，不扩全项目监控。

修正 R1 假隔离证据的方式：新卡新场景，不回写 R1。可在本轮新自建正常场景上每次从保存的原始字节恢复干净基样（仅本轮新产物，恢复前核对路径归本轮、坏候选另存），避免重复建业务链；每例记录注入前干净对照/唯一变更/预期拒绝 field/坏候选身份。若需要“删 allocations”反例必须实际改 SQLite 表；原 R1 那条只改 normalized.records 如实更正。B1 原调用前改字节不称晚变更；同值 float 不得改成缺键。source/未知键/成功旗标反例同步其依赖摘要，排除更早错误遮蔽。

## 6. 最少运行与交付

提供 `--only r2` 或明确小入口，只跑本卡正向/上述残余与真实收尾；不重跑原 42、R1 31 或历史全套。所有实际额外调用如实登记，旧证据只读引用，未执行 null+原因。核心/profile/记录按真实 scope 分列闭合；replay 的旧观察数量不得称本轮真实调用。

代码/必要指南/新回执全部定稿、局部核对通过后一次最终全树保护；changed 仅允许三文件，未知新增/新 missing/读取错误/范围外变化零；新增按明示根展开确切路径，无前缀兜底。139/27/326/旧偏差分别登记。新回执逐条更正 R1 的“目标路径已测/未再读候选/三时点完整”等声明，不回写旧件。看板漏勾仅补证据引用，不为流程勾选重建业务链。

完成本卡停止实施，不推进 TASK-029/Gate2/筛查/事实/初判/AI/终判/0009，不改变真实批准 null、开发宿主0008、next/AI=false。
