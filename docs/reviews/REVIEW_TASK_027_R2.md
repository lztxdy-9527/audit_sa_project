# TASK-027-R2 终审：当前 GPT 授权修复版验收通过

日期2026-10-15。正式结论以 `data/reviews/task027_r2_gpt_20261015_173156/review_result.json` 最终登记为准。原DSH提交仍有测试收尾阻断；本次按人类明确授权调用子Agent直接修复，并经GPT主审独立复验。不是将原交付追认为通过。TASK-027系列可由人类按本评审与最终身份关闭；本评审不批准任何业务批次。

## 最终冻结身份

- 生产 `scripts/runtime_gate1.py`：111301 B，`336cf30e791a2f325f50fdef3a63dde94c70baf5f7546f0035ec0d6759dac79f`。GPT/子Agent均未修改。
- 测试 `tests/test_runtime_gate1_decision.py`：92940 B，`66b82df9888efa499eee44f3af071aa75955680f8573f4386e5973e714afc4d4`。
- 指南 `docs/RUNTIME_GATE1_DECISION_GUIDE.md`：18105 B，`b6759e6f5a7de4c625a09cb43f8173d522a6dc5585ad940a8e0321437283e88b`。
- 原回执 `docs/EXEC_REPORT_027_R2.md` 保持10175 B / `26ac4dfb55aa48b65b5f8712e0de3777262a95ace72b16ae2058c325c1c684be`，不回写。

证据根 `data/reviews/task027_r2_gpt_20261015_173156/`。提交前测试及指南在preservation.json所列具名副本中保全；修复后函数变化审计在authorized_change_audit.json。

## 生产残余实际关闭

GPT独立脚本verify_production.py真实调用当前生产API：

- 新正常APPROVE事件save成功；该次冻结prepare/store.save/P1各1次，store.verify为0；正常verify effective=true，该次store.verify/P1各1次且不调用store.save。计数由实际原函数code对象的单一profile取得，不把包装次数当核心次数。
- 旧三个公开API仍拒绝已有scope；末次共享材料确认返回后新增登记叶failure，本次verify已拒绝runtime_dir(叶)，撤销wrapper后仍拒绝，未写事件failure。
- 无事件时主Blocked与真实解锁次错误均可见，事件未造、锁保留、store/P1增量0。
- 已有事件时主/次错误都保留，五键诊断真实写入1次。
- 真实锁独占句柄写全并关闭后保全原件、安装替代件再抛OSError，生产映射Error(write.lock)并保留两件，未删除替代件。

完整调用与前后计数见production_api_records.json，摘要见production_summary.json。来源批次字节不变，生产身份未变。原已关闭快照绑定/封套/receipt等没有重新派发或重跑大套件。

## 原DSH交付仍有的两个测试问题及授权修复

原提交仅比较台账canonical对象，台账追加LF仍0/PASS；末次确认后print仍读取failures.json，包装该真实后置读取返回原字节后改checks也仍0/PASS。实测在closure_before.json及post_terminal_before.json。首个晚变更控制处于确认循环内，另用第三次failures读取明确定位确认后的必要语义读取，二者未混称。

子Agent仅改测试和指南：台账对象/字节来自同一读取，严格与本次待写ledger_buffer比较；终端确认覆盖9份载荷及台账自身；输出使用已核验内存值，确认后不再读候选。辅助修正为安装spy前保存真实函数code对象，原函数与wrapper角色分列，不扩建框架。AST比较仅5个函数变化，无函数新增/删除；build_candidate仅将wrapper次数改为完整记录条数。

子Agent实际9个新进程closure-only控制：正常0/PASS；台账LF、审核后台账LF、台账替换、checks漂移、候选替换、缺调用、语义审核后checks LF、诊断后漂移全部1/FAIL，均保留坏候选。另原生CLI正常重放0。见agent_fix/verification_result.json。真实函数code身份的隔离核对见agent_fix/observer_code_verification.json，无额外业务调用。

GPT主审另用独立driver直接进入当前main，新进程正常0；台账LF、真实audit_candidate返回后checks LF、返回后台账LF均1/FAIL，分别定位ledger_bytes_mismatch/drift。主审确认全部10文件末次实读、成功各写1次、确认后候选读取0、源观察只读不变。见parent_cli_*.json及新输出根。9份台账不内嵌自身SHA；台账本身的完整字节在外部待写缓冲中确认。

本轮没有重新运行91项业务入口、历史TASK-021—026、标准化/SQLite/筛查/事实/初判/AI。重放中的107条API、89条冻结准备器、28条store、27条P1、91项检查来自既有观察，不能称为本轮新业务执行次数。主审新生产调用计数另列，重放增量0。两层证据明确分开。

## 执行端回执的有限更正与过程偏差

原回执称“未新增task027r2批次、0次新接收、未重跑80项场景”，与现存证据不符：原R2现场实际新增18份批次文件、接收CLI两次（0/1），完整91项包含原业务组。summary内命令、stdout及批次manifest均已读取；见delivery_statement_audit.json。仅登记，不改旧回执、不清理/移动现场，也不为这些过程偏差补跑。没有发现旧受保护文件因此丢失或被覆盖；不据此推翻主审的新独立技术复验。

主审的局部AST范围断言首次遗漏build_candidate的一行计数修正，已在仅文本核对中纠正，未修改代码或重复全树扫描。

## 保护与停止点

一次最终全树保护以证据根的protection_result.json为准，终审依据该次实际范围核对而非执行端自报。旧139项损失单列，27项确切恢复、R5越界326项、R1命名偏差19文件继续保护。原有过程偏差不追认，当前授权修复不改历史证据。

通过范围是当前单事件Gate1记录保存与有效性核验、以及可信测试收尾。有效性不等于执行许可；宿主仍0008、真实批准null、next/AI false。正式契约与人类D1/D2/D3未更改。

在最终保护通过后发布TASK-028：仅把已核验Gate1作为本次合成数据标准化/SQLite装载的实际前提，停在RT_NORMALIZED。Gate2候审/决定、筛查、真实初判、AI/终判均留后卡，不在本次实施。
