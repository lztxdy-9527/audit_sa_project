# TASK-013 独立验收：需要定向修复

验收方：GPT；日期：2026-10-12（Asia/Shanghai）。本轮没有修改宿主、测试、指南或冻结核心。

**结论：暂不通过，不推进 TASK-014。**正常筛查链可以运行；剩余缺口集中在恢复协议与测试证据，不要求改写 R01—R04 或上游模块。修复范围见 `docs/tasks/TASK-013-R1.md`。

## 1. 已确认的正常行为

GPT 新建容器 `data/workflow_host_tests/task013_gpt_20261011_194832` 运行原始测试，并用仅内存 wrapper 观测实际入口。**原始测试退出 0、failures=[]；8 组业务检查与 INTEGRITY 共 9 条保存为 PASS，另有 FINAL_ARTIFACT_READBACK 打印 PASS。**执行端最终、执行端复验和 GPT 容器的计数及读回结果一致，完整证据见 QA `artifact_audit.json` / `regression_execution.json`；不以执行端自报代替复验。

独立另建 C06b 小样批次，实际接收、Gate1 模拟决定、标准化/SQLite、Gate2 模拟决定、筛查均成功，0005 保留完整 0004.workflow。MAIN 的交付报告为 12 条（3/5/2/2），R02 超额 1,600,000 分；冻结核心没有改变。真实批准仍为 0，没有复算、事实底稿或 AI 调用。

正常流程通过不能覆盖以下反例。GPT 的定向探针仅修改**自己本轮新建的专用批次**，逐案保存完整实参与返回/异常、前后哈希，并恢复正向对照；没有修改执行端容器或旧证据。

## 2. F01：status 在最终检查后重新消费未验证的报告（P1）

位置：`scripts/run_demo_workflow.py` 的 `inspect_dev_batch`，约 2463—2483 行。

`_verify_screen_tail` 已检查报告字节，但紧接着再次 `_read_screen_outputs`，将这次读取的报告哈希与 findings 用于返回摘要，未与初始已验证哈希比较，也未在这个读取之后再完成筛查产物最终复测。

GPT 的 P06 只在第二次读取之前修改专用批次报告，把 findings 从 1 条改为 0 条，其他 checkpoint 和引用保持不变。结果：

- **本次 status 退出 0 / READY，findings_total=0**。
- 返回的 report_file_sha256 来自新文件，report_canonical_sha256 仍来自旧 0005，形成相互矛盾的展示。
- 撤销 wrapper 后再 status 才因报告文件哈希不符而拒绝。
- 恢复原报告后正向 status 正常。

要求当前调用即拒绝，不能依赖下一次发现。复用已验证缓冲或给后续读取做严格绑定，再在最后一次消费后按初始/真实 writer 值完成最终复测。不要以重新读取的新哈希覆盖预期值。

## 3. F02：筛查引用和元数据语义核验不完整（P1）

位置：`_verify_screen_operation`（约 2216—2382 行），以及 status 对 `operation` 内嵌 artifacts 的使用。

P01—P05 均从同一份合法新小样出发；必要时仅在新现场同步文件引用哈希，进入目标语义核验。全部实际返回 **0 / READY**：

1. P01：仅改 `0005.operation.report_relative` 为不存在的文件，status 宣称报告路径为该不存在文件。
2. P02：把 `artifacts.host_manifest_file_sha256` 改成 **bindings 对象指纹**，同步 artifacts 文件引用后仍接受。源码用 `等于 bindings_sha256 OR 等于 manifest 文件 SHA`，混淆了两种不同口径。
3. P03：artifacts.host_version 改为 WRONG-HOST-VERSION，仍接受。
4. P04：started.host_version 改为 WRONG-HOST-VERSION，同步其文件引用后仍接受。
5. P05：仅改 `0005.operation.artifacts.cutoff_date` 为 1900-01-01，真实 artifacts/报告仍是 2026-09-30；status 返回 READY 并展示 1900-01-01。

要求对齐本卡已有协议：固定路径、版本/类型、初始实读 manifest **文件**哈希、operation 完整内嵌 artifacts 与实际 artifacts 严格一致。所有已消费的必需字段先验形状再访问，缺失/错类型为带路径的 WorkflowHostBlocked；不允许错误路径/声明被保存为“已核验”。这不是防恶意篡改测试，而是拒绝协议对象自身矛盾。

## 4. F03：实际失败诊断没有本批次身份字段（P2）

位置：`_save_screen_failure` / `_load_screen_failure`（约 1934—1980 行）。

GPT P08 真实 writer 写完完整 0005 后抛 sentinel OSError。原命令及后续恢复均退出 2，失败优先于完整 0005 的行为有效；但实际生成的 failure.json **没有 batch_id、host_version**，读取协议也不要求或核对两者。原 TASK-013 卡 §6 明确要求失败记录绑定本批次与宿主版本，尚未满足。

补齐生成与恢复约束；失败身份缺失/不符、target_exit_code 非严格 int 1/2 等协议不完整应退出 1 并指向字段。合法诊断继续恢复原阶段/类别/原因/退出码，不得降成 READY，不覆盖既有失败现场。

## 5. F04：有界回归证据未证明其声称的检查点（P2）

本组是测试与回执问题，不能通过放宽宿主断言解决：

- G6 的 wrapper 递增的是**全部动作调用数**，只用 `>= trigger_at`；status 还未到最后一次 SCREEN 返回就可能注入。它没有证明“最后一次动作检查之后”。GPT 另外按第二次真正 SCREEN 返回注入快照变化，当前宿主能拒绝（P07 对照通过），因此这项是既有探针时点不实，不要求重写已有效的静态绑定检查。
- G6a 的 `before` 在 0005 尚未创建时取得，为 null；`null != after` 不能证明已写出 0005 的字节真的被改变。应在真实 writer 关闭后、注入修改前取实际哈希，再与注入后哈希比较。
- writer 捕获完整 text 只留在局部内存，未保存原始待写文件及其 SHA-256；旧 0001—0004 前后实际哈希、完整实参/异常链也没有完整落盘。summary.probes 为空，G6 消息又截为 200 字符，不能替代任务卡要求的完整故障证据。
- 隔离“缺记录”自测删除的是**启动登记**，保留全部调用记录，实际检查了 unregistered；其 `removed_one_missing=[]`。需要删掉一条已登记记录对应的实际记录，明确验证 missing，并让共用正式判定失败/入口非零。
- CLI screen-rules **13 次 = 成功 8 + 前提拒绝 5**。回执把 13 写作 CLI 内筛查成功次数的推导值，不成立。CLI 内部未观测仍须 null；派生值必须从真实成功日志导出，不能以命令数替代核心执行数。
- 测试计入 controller_events 的只有 check_dev_action/record_dev_decision，未覆盖 prepare_dev_gate 等入口。GPT 实测 **64=check 43+record 14+prepare 7**，测试只报前两项合计 **57**；宿主 6、筛查核心 4 则与实际入口相符。完整按函数观测见 `entry_count_audit.json` / `artifact_audit.json`，修复不能把一个子集称为全部控制器重放。
- G1 对照报告是同一输入的**第二次直接核心调用**，不是被保存的那一次宿主调用返回值。业务对照有用，但“该次真实返回”证明需在宿主实际调用处捕获并核对，或者准确说明现有方法的边界。
- checks 持久化为 8 组业务检查 + INTEGRITY 共 9 条，FINAL_ARTIFACT_READBACK 只另行打印；可以分开报告，不把仅打印的检查混称已入 checks。最终入口事件、命令日志和计数也需读回核验。

这些要求均来自 TASK-013 原卡的 §7/§8，不是新增业务范围。保留正常 MAIN、三个小样、阶段拒绝、完整失败优先与只读行为；有限新增反例可复用本轮新建小样逐案恢复，避免重复生成大量 MAIN 现场。

## 6. 证据、保护与交接

本轮 QA：`data/reviews/task013_20261011_194832/`。

- `independent_review.py`、`independent_calls.json`、`independent_results.json`：8 个独立观察，7 个未满足、1 个实际最后 SCREEN 返回控制通过。这里的“未满足”是产品/契约反例，不是假称整套测试失败。
- `regression_execution.json`、`regression.stdout.txt`、`regression.stderr.txt`、`entry_count_audit.json`：全新原始测试复跑与独立实际入口观测。
- `artifact_audit.json`：交付、执行端复验与 GPT 容器的产物和计数核对。
- `protected_files_comparison.json` / `acceptance_summary.json`：完整哈希、保护差异与最终判定。

主基线 TASK-012-R2（53983 项）只允许并核对到宿主、指南两项累计变化；本轮运行前基线要求 0 变化、0 缺失。冻结规则 SQL、核心、SPEC/契约、旧测试、旧批次及旧证据不改。详细数字以 QA 最终记录为准。

回执披露的项目外 `.tmp_t13_host_backup.py` 删除不属于本次交付，项目内基线不能证明该外部临时文件被保护；不推测其内容或重建所谓备份。后续禁止用通配符做收尾清理，保留失败现场并只在授权的新目录内操作。

请主理人将本验收单与 TASK-013-R1 全文转交执行端。无需主理人手工测试或签 Gate；修复完成后交 GPT 复验，不推进任务十四。
