# TASK-015 验收记录

日期：2026-10-13；验收端：GPT。

结论：**不通过，返回 TASK-015-R1 定点修正。** 已确认冻结事实底稿核心的真实接入、正常 JSON/Markdown 保存、0007 正常恢复及两类持久化故障恢复；但构建公开 API 在最后一次控制器检查后漏验 Gate2 磁盘材料，实际出现失败现场误报 READY，属于阻断。TASK-015 保持 in_review；本轮不制定或实施 TASK-016。

## 1. 交付身份与证据层级

实际文件哈希与交接一致，GPT 定点复验前后未变：

- 宿主 `707cd16ecf9ebeefba2e459f3e468ae3379459adc5cbf426bfb394173eedb75d`。
- 宿主指南 `ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8`。
- 新测试 `5f7dacfa07f54587dc835a0e5462470a6638178b5cb642c01af55d491cad9c0d`。
- 回执 `bed6d1bdb836bbe4bc9f0dcfdf503d945eb48de770bef20051c6d349dc724c27`。
- 原 TASK-015 卡 `c3477d4b5b062b49eef85711016d7630c0490083c44225854129ca1fbf33d9d3`；冻结核心/纯核心测试/指南及旧筛查、复算测试保持本卡冻结哈希。

执行端自报完整入口退出0；GPT只读核对 `task015_run_06/summary.json`，确为8项PASS、failures=[]。**GPT未重跑完整入口或MAIN，也未运行TASK-002—014历史入口或事实核心21组。** 不以保存的PASS替代以下独立复验。

## 2. 已实际复验通过的部分

GPT在全新批次 `data/batches/task015_gpt_20261013_001516/normal_c06b` 经公开API完成接收、两次显式模拟决定、标准化/SQLite、筛查、复算和事实底稿。真实冻结底稿核心直接观察调用1次，保留三个输入同一对象引用，调用前/核心返回后/公开返回后三时点规范指纹相等。完整实际核心返回单份保存，落盘packet严格规范JSON相等、packet指纹正确、Markdown字节精确等于返回字符串的UTF-8字节。0007与0006的workflow严格相等，previous引用正确，两处真实批准null、next_step_allowed=false。

同一新批次在五个真实下游函数被替换为“计数后抛错”的守卫时，公开inspect_dev_batch成功、命中全0、批次文件哈希集合不变；解除守卫后新进程status退出0。证据：`normal_core_and_readback.json`、`actual_core_return.json`、`readonly_status.json`和完整API/CLI记录。

GPT还实际执行交付入口 `--only persistence`，独立新容器 `task015_gpt_20261013_001516_persistence`：单组PASS、退出0，半写0007及完整写后sentinel均在新进程恢复退出2。实际异常traceback包含真实 `_write_exclusive_json` 写入/映射代码帧；半写方法使用真实独占句柄，不是替身writer。读取交付待写文件，partial 77998字节与现场前半38999字节一致，throw完整字节亦匹配；待写文件哈希和声明缓冲哈希一致。

本轮外部writer代码对象计数探针最初绑定了交付测试未使用的另一个加载模块，原记录 `{}` **不能用作实际调用次数**；保留该观察及其局限，不推导为“writer执行0次”。上述真实writer路径结论依据实际异常栈、执行的交付源码和实读缓冲/现场；不声称GPT额外量到了writer入口次数。

本轮GPT直接执行公开宿主API共17次、宿主CLI共17次（独立脚本15/3，加交付定点入口2/14）。未观察的子进程内部核心/控制器次数不作推导。

## 3. B1（P1）：最后控制器检查后Gate2文件已变化，构建仍报成功

实际位置：`scripts/run_demo_workflow.py:5766` 最后一次直接控制器动作检查；`5821`—`5825` 所谓Gate2收尾比较仍使用先前 `gate2_outputs` 中的三项哈希，未实读磁盘。之后的 `_verify_screen_tail` 只核对筛查/数据库等材料，不覆盖Gate2三份JSON。

独立探针只作用于本轮第二个全新C06b批次 `late_gate2_bytes`：包装真实 `check_dev_action`，先调用原函数；仅在其直接调用方为build_dev_fact_packet且第二次（写后最后一次动作检查）真实返回之后，为 `workflow/gate2/normalized.json` 追加一个LF，原控制器返回对象原样交回。未改内存normalized、凭证、数据库、宿主实现或绑定，也未同步任何哈希。

实测：直接动作检查2次，注入命中1次；原控制器仍返回严格true。normalized文件SHA从 `9556a9f11f59bcf25ff675ffc3ac6e0d1ba27e6896a49a96509c0f2d610d80f5` 变为 `f326ddb172d9d17ae254b93eb4a809dd7d092f80e91db29ae24de78e1076c1c4`。**本次公开构建错误返回READY / FACT_PACKET_RECORDED。** 撤销wrapper、保留变更后新进程status退出1；只恢复normalized原件后退出0。

这不是要求抵御任意时点的并发篡改：注入点是卡中明确要求位于最终磁盘复测之前的必要控制器调用，缺口是把旧缓存同自身比较当作重新实读。依据TASK-015第4节第8步，必须本次即拒绝，不能由下一次status补救。

完整参数、原始控制器返回、文件前后哈希、当前API完整返回、撤销/恢复CLI原文均在 `late_gate2_controller_probe.json`、`api/late_gate2_build.return.json`、`late_gate2_*status.stdout.txt`。目标文件已恢复；历史交付未动。

## 4. 交付证据核对与非阻断记录

GPT独立读回交付文件台账全部引用、90条CLI原文、14条API完整返回/异常、权威registry；文件引用存在性与实际哈希一致，无引用错误。13批次receiver命令/退出码与receive_invocation一致，13次checker的report/stdout/stderr引用均一致。MAIN和三个小样的完整核心返回与packet/Markdown相等；逐卡完整金额、命中键、related_ids、source_rows、entities/cells及related_refunds与筛查输入一致。

实际现场导出：13批次、**10份复算MATCHED报告**、1份MISMATCH报告、**7份DEV_FACT_PACKET_READY事实包**、7份0007文件（6份可解析、1份半写不可解析）、其中5份可解析且无本层failure、5个本层失败现场。不能把“可解析且无failure”单独宣称为已恢复核验成功；正常恢复另有实际证据。

交付 `matched_reports_total=7` 来自packet_status，不是复算报告，属计数标签错误。`half_written_vouchers` 的最终导出用“可解析0007且存在failure”，实际选中完整写后throw，未选中partial；虽然总数恰好同为1，分类错误。这两项不推翻已直接核验的正常结果/半写现场，本页已独立补证，登记为非阻断；可在R1已获准触及测试时更正，不能仅靠旧字段继续声称正确。

交付隔离副本仍同时删除一条文件台账和一条registry；GPT直接执行交付源码中的实际audit helper，只删内存审核副本一条registry、其他台账完全不变，原副本无问题、修改副本明确报告未登记。性质已补证，不为辅助隔离记录单独增加修订阻断。证据：`single_registry_deletion.json`、`delivery_evidence_audit.json`。

## 5. 文件保护与修正边界

GPT只扫描当前树一次，共121952文件；与原卡指定的118788项基线比较，changed恰为宿主/宿主指南、missing=[]、unexpected_changes=[]。关键冻结件及原TASK-015卡哈希一致。完整保护扫描结果见本轮 `protected_files_comparison.json`；最终机器结论及R1保护读数见 `acceptance_summary.json`、`source_hashes_after.json`。最终读数由该次扫描加本轮已知新增评审文件最终哈希组成，只冻结当前现场，不表示TASK-015已验收，不是Git恢复点。

GPT未修改宿主、交付测试、指南、回执或历史产物；仅新增独立证据、本验收记录和 `docs/tasks/TASK-015-R1.md`。正常事实底稿及持久化部分已复验，R1只修B1并做受影响范围复验，无需再次完整跑MAIN/八组/历史入口。真实批准仍由人类作出，DSH看板由人类操作。

独立证据根：`D:\harness work\audit_sa_project\data\reviews\task015_gpt_20261013_001516`。
