# TASK-028 终审：未通过，转 TASK-028-R1 定点修正

日期：2026-10-15。评审以当前文件、实际运行和已保存证据为准。结论 **NOT_ACCEPTED**。不关闭 TASK-028，不制定 Gate2 实施卡。本次没有修改实现、测试、指南或旧证据，也没有调用子 Agent；上一轮对 TASK-027 的一次修复授权不外推成本轮实现授权。

## 1. 身份与复验范围

交付四件的 SHA/长度与交接一致：

- scripts/runtime_gate1.py：143031 B，`067e24161d62fc2f3883d844e0dfe716e30f2fe7dcf2fd22fcfedb0ff69fc4e1`。
- tests/test_runtime_approved_load.py：43922 B，`0f9d44d93d9695fb652809502b996099bae8a6ca606ce3bd15657fa8fd39c05c`。
- docs/RUNTIME_APPROVED_LOAD_GUIDE.md：8918 B，`498cc568712d4ae6988e174dd960097091a911588e6ca7a3fa2a31956e4f6c1b`。
- docs/EXEC_REPORT_028.md：9222 B，`582c3215c957954af1db46fc916d73c180a3410d9aab10dc585bc916e9d8fd92`。

证据根 `data/reviews/task028_gpt_20261015_182926/`。GPT 实际做了一个新正常登记/夹具事件/装载及只读恢复、同源隔离反例、三个错误映射场景、一个保存末端数据库变更场景和三个新进程收尾探针。未运行执行端原 42 项整套，未运行历史大入口，未接 Gate2/筛查/初判/AI。

正常 C06b 小样真实调用两冻结计算核心各一次，独立只读 SQL 行数 suppliers/payables/payments/allocations 为 2/1/3/3；inspect 正常返回 RT_NORMALIZED 且 normalize/loader 增量为零。冻结核心与源批次未改。这些正向事实不足以消除下面的反例。

## 2. B1：末端预期未绑定到本次已验证读数

`_confirm_approved_terminal` 对数据库及六快照采用 `_recheck_capture(_capture_file(...))`：新取当前值后与其自身比较，丢失已验证预期；context/receipt 没有字节复测，scope/快照固定集合及锁状态、批次顶层/四子目录集合也未全部覆盖。run 计算前亦未复确认八份 Gate1 事件字节。

实测 `probe_summary.json` / `api_records.json`：

- inspect 的真实 `_validate_load_report` 返回后给数据库加一个 LF：本次仍 RT_NORMALIZED，撤销 wrapper 后下一次 inspect 才拒绝。
- inspect 的真实 `_require_effective_gate1` 返回后分别给 context.json、snapshots/decision_result.json 加一个 LF：各命中一次，本次仍成功，下一次才拒绝。
- 保存端 `run_late_database.json`：真实 artifacts writer 写完返回后数据库加 LF，normalizer/loader 各真实一次，本次 run 仍成功、无 failure；后续 inspect 拒绝。坏数据库保留。

修复必须让数据库预期来自该次核心报告/已验证同缓冲读数，事件八文件来自操作开始时读数；所有必要消费后再做原始字节/集合/路径确认，不得在末端重新建立预期。详见修正卡 B1。

## 3. B2：恢复时身份、严格类型、核心结果及数据库关系未闭合

在 GPT 自建场景分别修改候选，必要时同步直接外层文件摘要，其他文件保持原件；坏候选各单独保存在本评审根，操作后原字节精确恢复。以下均被公开 inspect 接受：

- started.batch_id=OTHER-BATCH，重算 artifacts.started_file_sha256。
- artifacts.registry_file_sha256=64×0；artifacts.gate1_record_fingerprint=64×0。
- artifacts.database.byte_size 由整数改为同值浮点数。
- load_report.round_trip_exact=false，同步 artifacts.load_report_file_sha256。
- 实际 SQLite 删除一条 allocations，提交后同步报告 database_sha256 与 artifacts 的库 SHA/大小及报告文件 SHA：报告/normalized 仍说 3 行，实际只有 2 行，inspect 仍成功。

最后一例证明当前只比较“报告计数 vs normalized 长度”，没有原卡明确要求的只读 SQL 实查。不能以外层哈希更新后的自洽代替材料/数据库关系正确。当前 started/artifacts 的遗漏字段、数值类型及 load_report 成功不变量须成组闭合；复用冻结 `require_loadable` 等纯校验可行，不要复制完整转换或勾稽算法。

## 4. B3：创建目录 I/O 与核心 Blocked 分类不正确

`error_summary.json` / `error_api_records_run2.json`：

- 真实 Path.mkdir 接缝在数据库父叶创建时抛 OSError，命中一次：run 泄漏原生 OSError，已建 load_dir 为空且无诊断。两个 mkdir 位于错误边界之外。
- 使用真实冻结异常类作受控分类注入：NormalizationBlocked、SqliteLoadBlocked 均被本层映射成 RuntimeGate1Error，failure.kind=ERROR；诊断没有保存两项原始 reasons。此为宿主映射测试，未声称真实核心自行发现业务问题。

新层 I/O 应映射 RuntimeGate1Error(stage)+cause，按本次实际已建目录独占留诊断；Blocked/Error 按真实冻结异常类型区分。有效 failure 的六键、版本、kind、字段类型和原因链也须先核验再消费，读取错误不得泄漏原生异常。

评审首个错误探针缺少 scope 的技术父目录，准备阶段即被已有正确前提拒绝，随后脚本自身 TypeError；`error_api_records.json` 保留该失败尝试。补齐新技术父目录后在全新 errors2 根完成上述实测，未据首轮作实现结论。

## 5. E1：测试收尾再次退化，输入不变观察不完整

三个真实新进程运行测试 `main` 的 replay 分支，复用原观察，源证据未改，不重复业务链：

- normal：0/PASS。
- 真实 `audit_candidate` 返回后给 file_ledger.json 加 LF：命中一次，仍 0/PASS（`cli_post_audit_ledger.json`）。
- 打印结果所需的最后一次 failures.json 读取返回原字节后给 checks.json 加 LF：命中一次，仍 0/PASS（`cli_post_terminal_checks.json`）。

finish 未将台账自身确切字节纳入最终确认，且确认后再次读取候选 failures。前一任务已验收的原则在本新测试中未保留；修复限现有小收尾，不重新造审核框架。

另：normalizer 观察只比较工作簿文件前后，没有同一 quality_report 引用前后规范指纹；loader 未取得同一 normalized 引用的调用后指纹。生产端也缺该检查。核心异常观察未含完整 traceback。原“输入前后指纹未变”只能证明已测工作簿字节，不能概括所有内存输入。修正卡只要求补两计算核心的实际消费对象观察，不扩成全项目监控。

## 6. 保护、流程与停止点

一次最终全树比较见同根 protection_result.json；允许实现变化仅 runtime_gate1.py，执行端新增逐项对照其已保存允许名单，评审新增逐项登记。139 历史损失单列，27 精确恢复、R5 326 和旧命名偏差保持；范围校验与技术验收分开。最终基线见同根 source_hashes_after.json/review_result.json。NOT_ACCEPTED 快照只是本轮起点，不是验收或追认历史偏差。

看板清单未勾选是非阻断流程事项：真实证据足够时无需为此重建链；本轮拒绝原因是上述实测技术反例。执行端回执中历史损失说明误写为 TASK-027 事故，真实事故为 TASK-026-R3；在新回执更正，不回写旧件。

真实批准仍 null，开发宿主仍 0008，next/AI=false。本次 Gate1 APPROVE 均为已登记合成夹具，不构成人类本批次批准。下一步仅 TASK-028-R1；不实施 Gate2 或 TASK-029。
