# TASK-027-R1：Gate1 保存与核验闭合、复用可信测试收尾

类型：B，DSH 执行。依据 `docs/reviews/REVIEW_TASK_027.md`。这是原范围修正，不建立新 Gate、不改变契约或动作许可。先建任务卡再实施；全部收尾完成再 in_review，done 由人类处理。完成后停止本卡实施。

## 1. 起点与冻结

先只读核对本卡、评审、工作区与新保护基线：
`data/reviews/task027_gpt_20261015_161614/source_hashes_after.json`，身份以同根 `review_result.json`/`finalization.json` 登记为准。基线是 NOT_ACCEPTED 的当前状态，不代表追认实现或历史删除。

允许修改且仅允许修改：

- `scripts/runtime_gate1.py`，起点 `e44743f943cba02d46f45e2be6d0d049e7123a638c197183ad2a83ff24bd0371`，98928 B。
- `tests/test_runtime_gate1_decision.py`，起点 `5a1cb9e17c355195d094cd98eb95124d3097da840ee86485f6abcdbdac2d5152`，58236 B。
- `docs/RUNTIME_GATE1_DECISION_GUIDE.md`，必要时更新；起点 `052d107f78b904d5412a27a531c98b3a6d56f6f4bafcb0d90ca8e7126e5e3340`，9702 B。

新增 `docs/EXEC_REPORT_027_R1.md`，以及四类新根下本轮 `task027r1_<明确轮次>/`：runtime_gate1_decision_tests、batches、runtime、human_gate_decision_records/gate1。禁止额外根、旧树内加 harness。生产补丁版本 TASK-027-runtime-gate1-1.1；保持原协议名和公共接口。

冻结 TASK-026 GPT 测试 `24ce783cfd199d942ffbd857c901208a535db414e94b1a70c4af6d1f4a258ca2`、指南 `01644cb1a21f349617a182b37df868ac0321f1a5206126fe8e7bb1d11e16bd94`，及准备器/P1/store/契约/生效登记/配置/控制器/宿主/全部上游核心与历史现场。不能为复制收尾修改 TASK-026 文件。

139项历史损失不重建、不抹零；27项恢复及旧R5越界326项逐项保留。评审首轮自身新过程现场也冻结，不清理。开始时身份不符即停并报告，不自行扩大授权。需要改架构/契约/放宽权限立即停止升级 C 类。

## 2. B1：本次 store 输出绑定与最终集合

保留 save 内恰一次公开 prepare、恰一次冻结 store.save（内部 P1一次），不增加直接 P1 预调用或 store.verify 作为替代正确写后验证。

- 调 store 前确认本次已消费来源/登记仍与起始读数一致；拒绝不得建事件。
- store 返回后先将实读 manifest 确切字节 SHA 绑定该次真实返回，再核验其冻结封闭清单及五 payload 的实际长度/SHA；不得把 store 返回后第一份已被改的 payload 直接当正确期望。
- 五个对象/完整两键 decision_result 与本次 submission、materials、expectations、显式空历史、真实返回指纹及批次关系闭合；使用严格 canonical 比较。后续 byte 预期只来自操作起始读数、本次 writer 缓冲或已被返回 manifest 绑定的快照清单。
- 最终收尾补登记叶恰二文件、无 failure/未知项，以及批次顶层和四固定子目录集合；save/verify 均按各自全部必要消费之后执行。复用已有 helper，不加通用 I/O 框架。

最小反例：真实 store.save 返回原值之后给 submission 快照追加 LF；另一个新 scope 在该位置新增登记叶 failure。均本次 save 阻断并保留现场；有事件时本层有效 failure，新进程 verify 拒绝。一个未注入正常对照成功。再用一个调用前末次来源变更对照证明 store/P1 增量0，无须遍历全部路径。

## 3. B2：封套先验形状、所有来源关系与写后错误

先核验类型、封闭键、严格常量/类型/哈希，再消费对象。context/receipt 全部字段均有实际关系：source_batch_relative/runtime_relative/scope/event 与显式规范项目相对路径相等；context.registry_file_sha256 与实读登记/receipt一致。context.store_result 与该次 store.verify 除 status 的冻结差异外稳定字段完整 canonical 闭合，含 record_fingerprint/manifest SHA/identity/scope/false边界。不能只验证键存在。

真实 writer 完整写 receipt 后抛 sentinel，应为本层 Error（保存当前 stage），保留 cause/坏字节，并在实际已存在事件写五键 failure。冻结 store 自身写后失败同理以实际现场判断，不因 created_event 置位滞后漏诊断；没有事件不为诊断造事件。主错误及诊断/解锁次错误都须保留；不得捕获一切并包装成成功或伪装协议拒绝。

最小反例：boundaries=[] → Blocked精准字段而无原生异常；三个来源字段各在独立可解析新副本与外层 SHA 同步后仍拒绝；store_result.record_fingerprint 矛盾拒绝。真实 receipt writer 完整返回后抛明确 sentinel → Error+原因链+已有事件 failure，随后只读 verify 拒绝。context 真实句柄半写沿用当前方法只做受影响必要检查，不重跑冻结 store 故障组。

## 4. B3：本次锁身份与失败传播

维持原同级技术锁设计。取得时保存可核对的目录/锁文件身份与确切内容，释放前检查身份、集合、路径/reparse及内容。相同内容的替代目录/文件也不得释放；未知/变化锁保留。取得失败不能盲删未核验现场；主错误后释放失败不能吞掉次错误。只使用标准库，无分布式锁、自动重试或锁恢复机制。

最小控制：本轮新技术锁取得后，将原锁具名保全到本轮新根内（仅此控制授权对该本轮自建锁做非递归 rename，先核对解析后两路径均在本轮根且目标从未存在），于原路径建立内容相同但身份不同的替代锁；真实释放拒绝、两现场保留。正常自锁可释放；主/次错误同时可见。不得移动或删除任何旧路径。除核验过的本次自锁释放，禁止删除/清理探针目标。

## 5. B4：移植已验收收尾原则，不再扩建框架

参考当前已验收 TASK-026 GPT 测试，复用其小收尾原则而非旧版本：

- 定稿完整内存观察为独立预期，写盘前固定且审核期间不刷新；磁盘 expected 文件也只是候选，不能成为其自身的可信来源。
- 同一次实读绑定对象与字节，完整 canonical 类型敏感比较；预期与候选 ID/条目/检查双向一致。台账期望来自本次待写缓冲，包含终审诊断的实际稳定缓冲；不得从被改磁盘重建正确台账。
- 正常成功的已登记载荷/台账一次写定并读回，最后有界确认；审核失败或漂移实际支配顶层返回1、磁盘FAIL、非空failures，保留坏候选，不覆写成通过。不要添加多轮收敛、影子判定器或大观察系统。
- 当前 API 在真实调用前登记活动 call_id；nested 完整记录绑定当前父调用，实际输入引用调用前/后指纹与独立快照，返回保持原对象。P1在实际加载模块上完整观察；单一 profile 按代码对象身份计数，直接API、save内部prepare、冻结prepare/store/P1各自分列闭合，禁止混加后强求总数相等。修正真实禁止函数身份；子进程不可见次数 null。
- replay 源全程只读，必须显式指定从未存在的新 out-dir。原根/越界/既有目录反例只核对拒绝和未写入，不清理目标。删除原测试移除 unknown/failure 探针的动作，改独立坏场景保留。

至少四个 closure-only 控制，复用一次实际观察且不再接收/建链：正常0/PASS；候选返回及候选expected同步替换但独立预期不变→1/FAIL；少一条API而独立预期不变→1/FAIL；待写缓冲之后checks字节LF漂移→1/FAIL。坏候选保留并指出目标。原已失败检查继续支配失败。真实 CLI须消费实际最终 verdict，不能只在内部 helper 失败。

## 6. 执行顺序、最少回归与交付

先 B1/B2/B3 定点通过，再修 B4；正常/BLOCKED真实接收小样各一次供本轮全部场景复用，夹具只取既有登记人类字段。补丁改字节即新运行版本，不迁移旧登记。允许一个有明确检查集合的定点入口覆盖本卡与正常APPROVE/HOLD/BLOCKED+APPROVE、既有三API scope前提；不用跑 TASK-021—026 历史入口、原54项全套或 writer/loader大组。

所有代码/指南/新回执定稿后一次全树保护扫描；当前基线内无新增 missing/范围外变化/范围外新增/读取错误。139项历史损失单列，27恢复和326越界产物不变，新增按确切路径登记，无目录前缀豁免。扫描后只允许有限自有元数据身份登记，不反复全树重扫。

回执必须分列：真实本轮调用与异常、映射注入、读取但未重跑的旧证据、未执行项null及原因；更正旧“receipt sentinel”“唯一删除锁”及收尾通过范围的声明，不回写旧回执。全程不调用标准化/SQLite/Gate2/宿主/初判/AI/终判，不生成0009；真实批准null、宿主0008、next/AI false不变。

交付检查清单：起点冻结；B1两写后反例及调用前拒绝；B2形状与来源/稳定字段闭合；真实receipt异常；锁身份/主次错误；独立观察和计数；四类收尾控制；只读新输出与无清理；一次最终保护；新回执全齐。技术验收由GPT作出，业务批准由人类作出。
