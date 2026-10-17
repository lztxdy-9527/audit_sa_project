# TASK-018验收记录

日期：2026-10-13；验收端：GPT。

结论：**暂不通过，TASK-018保持in_review。** 两项实现阻断B1/B2已经独立复现，另须闭合E1证据登记/观察。修正依据为 `docs/tasks/TASK-018-R1.md`，不推进TASK-019。GPT未修改实现、宿主、控制器、核心或旧现场，未访问看板或关闭卡片；DSH操作由人类负责。

## 1. 交付身份与有效部分

实读源文件SHA-256与交接一致：

- `scripts/export_demo_review_bundle.py`：`baea8fd1ff9c4092aca2e120233bbff960545fc9799d8b33156c46c10147dc44`。
- `tests/test_export_demo_review_bundle.py`：`7b385bd6ebffb5495b565be44ed818766427e1ba8c52297c8479bc7326ac88f1`。
- `docs/DEV_REVIEW_BUNDLE_GUIDE.md`：`08ba5545c6d66c03937e3e05bedbf56544b19935d2f762e0f1a3ad0bb91e1f91`。
- `docs/EXEC_REPORT_018.md`：`6ddad989fa951d81cd40a1c54aff22339ef01a5219c5609cfd8d765d08fc98d7`。

执行端最终容器task018_run_06记录7/7 PASS、退出0，属于执行端实测。GPT独立重读50个API/CLI文件引用、相应文件台账与registry双向对应，文件存在且SHA正确；引用完整不等于测试已覆盖下述缺口。

GPT另在新审阅目录 `data/reviews/task018_gpt_20261013_051328/` 实际执行run_targeted.py和audit_helpers.py，使用现有合法 `data/batches/task018_run_06/c06b` 作为只读源，不新建上游链。正常导出25文件/24 payload，22份复制件与源/初始绑定一致，六个真实下游函数抛错守卫命中0；正常离线verify与新进程CLI成功。原批次37文件、外置DB及正常包前后字节不变。

实际定点共10次公开工具API（run_targeted.py中9次，helper审计另1次缺失批次导出）、1次经交付status_of调用的真实宿主API、3次工具CLI；真实宿主status代码帧5次（导出内部4、独立helper1）。子进程内部核心未观察，记null。未运行交付完整七组入口，不称为GPT复跑7/7。

## 2. B1：最后输出消费后仍可能误报成功

原卡§5明确要求manifest写后、返回成功前再次核对payload/manifest实际字节。当前_export_inner在写manifest之前复核24份输出，manifest写后只重读来源/DB及目录文件集合，没有再次读取payload实际字节。文件存在与字节一致是不同条件。

GPT包装真实_write_exclusive，在manifest真实写入和内部读回完成、返回真实原结果之后，仅向本轮新输出README.md追加一个LF。命中1次，SHA由 `b280194a0acfb2f5ad84eb8d19673ef77c44b5e7c67c3d9778a058d42c8b4af3` 变为 `89af461045d288cc1e5f37de732178ab3648a93ce272a34954943c2fa17b1190`。**本次export仍返回DEV_REVIEW_BUNDLE_VERIFIED**且无failure；随后真实verify按README字节数不符拒绝，新进程CLI退出1。证据late_output_probe.json及完整API/CLI原文。

离线verify也存在同类缺口：先遍历24份payload校验字节，随后重新读取status/checkpoint/packet/record等JSON，但未将后来消费的字节与初始manifest对应哈希绑定，也无返回前最终确认。GPT仅在隔离副本中，真实_read_bundle_json最后读取initial_judgment.json返回原对象之后给该文件追加LF；本次verify仍成功，撤销wrapper后的新进程verify退出1。SHA `4644663a9e1d85384d48bc1fdc1fd5d1adf5a69ff4303c594bdf3777878e2db0` → `eed1a80bef648a9e1ec09b6bf3fb744f036b5ae7385d2dae38fc67419fe29e45`，命中1次。证据offline_late_probe.json。

要求有限且明确的最终确认；不是要求抵御任意时点的并发篡改。输出摘要宣称已经核验时，本次明确必要消费点之后的变化必须在本次被拒绝，不能等下次调用纠正。

## 3. B2：离线清单来源和批次身份未绑定

只在正常包的四份独立隔离副本改动，每个都是格式合法、可解析、文件集合齐全的包。四项均错误返回DEV_REVIEW_BUNDLE_VERIFIED：

1. 仅把manifest.canonical_fingerprints.packet_file_sha256改为64个0，实际packet文件及其payload清单/历史status未改。
2. 仅把首份复制件source_initial_file_sha256改为64个0，实际复制件/file_sha256/历史status初始绑定未改。
3. 仅把manifest.checkpoint_0008.previous_file_sha256改为64个0，实际0008及0007未改。
4. 把manifest和host_status的batch_id及manifest.source_batch.batch_id改为OTHER-BATCH，仅更新host_status的payload大小/SHA以排除外层文件哈希拒绝；0008、record.source及保存submission仍属于c06b。返回结果却称batch_id=OTHER-BATCH。

证据identity_probes.json和逐次完整返回。前三个只改manifest、不动payload，因此不涉及外部可信性问题；第四个刻意保持部分声明一致，用于验证必要跨文件身份绑定，而非只测一个字段与自身相等。

COPIED_BYTES_ONLY限定不证明原始业务真实性、不认证身份，这是正确边界；但不能据此忽略包内已经声明的来源指纹与批次自相矛盾。原卡要求必要status/0008/packet/record身份一致，应使用包内同缓冲对象和实际字节核对这些关系，不读取原批次/DB、不重跑宿主或冻结纯核心。

## 4. E1：登记和观察仍需闭合

交付测试status_of直接调用HOST.inspect_dev_batch，G1/G6使用它，却没有经过record_api或保存完整实际返回。GPT直接执行交付status_of：实际宿主代码帧1次、API_RECORDS增量0、CALL_REGISTRY增量0。现有ledger只审已登记列表，因而其missing/unregistered=0不能证明所有实际直接调用完整。证据helper_audit.json与status_helper_actual_return.json。

原“真实缺失批次由真实宿主拒绝”也不准确：_resolve_source_batch先检查is_dir，g2_missing_batch在进入_call_status之前就被工具拒绝。GPT实际调用该缺失批次导出，观察真实宿主代码帧0。此结果可作为工具前置拒绝，不可当作真实宿主观察；R1补一个独立、已登记的真实宿主缺失批次调用即可，不需建新业务链。

E1要求R1定点入口及共享直接status读取实际登记、完整返回/异常可追溯，分清公开调用与工具内部嵌套status，计数不要求两者相等。未测项null，证据/保护收尾真实执行并进入failures。

## 5. 不单独阻断的记录问题

- 原API“21条预期协议阻断”实际是18条DevReviewBundleBlocked与3条DevReviewBundleError；完整异常文件已经保留，分类文案错误不影响B1/B2的复现。新回执分列，不回写旧回执。
- failure_only_bundles意指3个失败现场，不是“只有failure.json”。实际late目录还保留24份payload，partial目录保留半写文件，manifest_throw保留24份payload及完整manifest，符合失败保留原则；旧计数标签和文案应在新回执澄清，不清理现场。
- duplicate_path测试通过追加第25项触发条目数拒绝，尚未单独命中重复路径分支；若后续触及该反例，应保持24项只替换一个路径，避免提前拒绝。无需为此重跑旧七组。
- 执行端文档后又复扫全树，超出原卡“单次扫描复用”；新卡只进行一次完整扫描，再对本轮新增产物作有限刷新。

## 6. 保护、修正范围与当前边界

GPT实际执行一次完整保护扫描，与TASK-017-R1最终128451项基线比较；结果/实际扫描数记录在同目录protection_result.json和review_result.json。最新source_hashes_after.json用于下一修正卡冻结当前未通过交付，不是TASK-018通过声明或Git恢复点。

R1只修独立工具/本任务测试，指南按受影响说明必要修改；宿主、控制器、全部核心、原任务卡/回执/历史产物冻结。使用同一现有批次只读生成一个新正常包，其他反例仅新输出/隔离副本；不新建batches/SQLite、不跑MAIN/零条/旧七组/持久化故障/历史入口。原writer真实句柄故障的既有证据保留引用，未触及writer时不重跑。

当前仍到宿主开发态0008：真实人类初判未保存、真实Gate未批准、next=false、AI未开放。不推进0009/AI/正式契约/真实流程，TASK-019待本卡通过后制定。
