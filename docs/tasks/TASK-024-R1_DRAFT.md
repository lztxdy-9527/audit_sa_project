# TASK-024-R1：Gate1 适配器与验收证据定点修复

日期：2026-10-14。**B 类：DSH 实施，GPT 验收**。原 TASK-024 为 C 类设计，本轮只修既定设计的实现与证据，不改变协议/边界。前提：阅读 `docs/reviews/REVIEW_TASK_024.md` 的 B1—B4/E1/E2 及对应实测记录；实施前建卡。TASK-024 尚未通过，不实施 TASK-025。

## 1. 范围、起点、冻结与升级

只允许修改：

- `scripts/record_demo_human_gate1.py`：起点 SHA `c002243ade1332e9e56ecd0a2b932a100c1d9f57191983f5689751e4f7fbd650`。
- `tests/test_record_demo_human_gate1.py`：`50f1268ea7ca8871eeb6405e5ac2ebec9c7d743e90a2868b493b35689d48df6c`。
- `docs/HUMAN_GATE1_DECISION_GUIDE.md`：`9c8f4409a1c964a65fe64139424795e635ecdf33a55f1724fec683fe9998c2fb`。

只新增 `docs/EXEC_REPORT_024_R1.md`、本轮 `data/human_gate1_decision_tests/task024r1_<唯一轮次>/`、`data/batches/task024r1_<同轮次>/`、`data/human_gate_decision_records/gate1/task024r1_<同轮次或明确场景后缀>/`。允许必要父目录，不清理旧现场/junction，不改旧回执或评审证据。

修复保护基线：`data/reviews/task024_gpt_20261014_050915/source_hashes_after.json`，完整 SHA/项数/两个确切自指排除以同目录 `review_result.json` 为准，verdict=NOT_ACCEPTED。它是修复起点，不能宣称为已验收组件。所有新增按确切路径/明确本轮根枚举登记，不按 reviews/gate1 前缀豁免。

冻结 prepare/store/P1、契约及生效登记、配置、宿主/控制器和其他既有文件；32 项/14 代码绑定、三 API/无 CLI、请求/封套版本名称、六/七项 false 边界、store 六文件、锁及限定历史语义保持既定口径。允许适配器实现版本补丁标注，但不得把改协议当修复。

若需要扩大文件范围、改变 Gate/证据链/权限边界或改冻结组件，立即停止受影响处理、保留现场并报告 GPT 升级，不静默扩大实施。D1/D2/D3 与 V1 生效不重问；测试不产生人类业务批准。

## 2. B1：末次必要消费后的完整收尾

save/verify 的最终确认必须覆盖本次全部已消费的 32 来源、全部历史事件八文件、本次/目标八文件，以及各层固定文件/目录集合、路径无 reparse、失败/锁状态。预期只来自本次初始同缓冲读数或本次 writer/readback，不在最后从候选磁盘重建预期。对象解析/核心/组件等必要消费完成后再做有界确认；不能复测一个缓存与自身后称磁盘确认，也不能只测目标而漏历史。

最小独立反例：先观察真实接缝并保留无注入成功对照，然后只改一项：较早 context 加 LF、当前 source quality_report 加 LF、目标新增 failure、scope 新增空事件目录。注入须在原核验读取返回原值之后，各命中一次，本次 verify 即本层 Blocked，定位对应文件/目录；verify 只读不写诊断，撤销/恢复隔离原件后正常。另验证 save 在最后来源确认之后、仍有后续必要消费的接缝遭同类变更时本次拒绝，并保留有效本层 failure。不要只重复原来的“store 返回后、第一次来源收尾前”已能被捕获的探针。

不承诺返回以后不再发生并发变化。锁 release 是协调收尾，仍不得删除非本次/已变化的锁；不改变锁回收业务边界。

## 3. B2：两种顺序分开

实际枚举全部事件后，按文件内严格整数 revision 建立连续唯一 1…N 的合法前缀，不按叶名字典序推定 revision。按 revision 构造 `prior_events`；对每个前缀的 P1 `prior_history.records` 单独按原 event_id UTF-8 排序唯一。未知/失败/半写/缺 receipt/缺快照/重复或缺口均拒绝，不跳过、不补写。

必须实测：先 z_first(rev1) 再 a_second(rev2) 均可保存和恢复；三个事件按 EV-0002、EV-0001、EV-0003 的顺序保存，第三个可恢复，前两事件仍可恢复，全部旧文件不变。修复不能新增目录名编码 revision、event_id 等于叶名、仅两事件等限制。

第三份已登记合成夹具可只读复用：`data/reviews/task024_gpt_20261014_050915/registered_fixture_0003.json`，SHA `6c69c75cde41014fd8740b95d58b9e8a805bd30003fb14ac6f8fb40c93cf23c3`；固定 EV-0003/REJECT 的人类字段已在使用前登记。其他两份沿用原登记。绑定字段来自本次真实请求，标识只在证据外层，不加入 P1 schema。三事件最小安排：B/HOLD(EV2) → A/APPROVE(EV1) → B/REJECT(EV3)。不要求人类提供真实决定，不转用 Gate2 夹具。

## 4. B3：封套 schema 与内部关系闭合

对实际消费的每个事件核验完整封闭键/严格类型/值，包含 request 的六键及嵌套材料、期望、证据、边界，source_batch_relative 的项目相对路径声明，snapshot_files/prior_events 所有成员。整数不接受 bool/float，大小非负，SHA 完整小写 64hex，ID 原样不归一化。结构检查先于比较/摘要/成员访问，不泄漏原生类型异常。

request.materials/expectations 与相应存储快照、record/manifest 的既定绑定按 canonical 字节严格相等；14 代码/规则声明与实际保存绑定闭合。前缀/快照列表规范比较不能用 Python 容器相等掩盖类型差异。历史只核验保存快照与内部声明，不重新读取旧业务源、不新增历史路径任意跟随。

逐例从合法副本只改一个目标并同步必要外层哈希，保证不被更早旧哈希遮蔽：历史 request={}、历史 source_batch_relative=7、snapshot byte_size 同值 float、prior_events.revision 同值 float；补严格 false→0 和缺/多嵌套键控制。必须本层 Blocked 且定位实际字段。原件、合法键顺序不同的 canonical 等值对照和普通字符串 ID 仍成功。不要重跑所有历史协议案例。

## 5. B4：一致异常映射与双重失败报告

三公开 API 均只传播本层 Blocked/Error，已知下游拒绝保留 field/reason + cause；运行/I/O/加载失败为 Error + 原因链。真实缺 gate1_packet 的 prepare/save/verify 都应正确映射；无事件现场时只释放本次仍一致的自锁，既有锁不动。缓存只保存完整成功加载模块；实际 exec_module 的 ImportError/OSError 都结构化报告，撤销后可正常运行。

真实写 context 失败后，failure 诊断写入再失败：保留原主错误及第二个写诊断错误并明确报告；不吞第二次失败、不伪造有效诊断、不重试覆盖、不删除半写现场。沿用既定七键 failure，纠正辅助注释，不为诊断扩展成功 schema。

最小实测：真实缺文件协议拒绝（含无事件/锁收尾）、真实 loader 接缝 ImportError/OSError（注入和撤销对照）、真实双重写失败（两处各命中一次，主/次原因可追溯）。不以替身成功绕开冻结模块，也不把任意异常统称协议拒绝。

## 6. E1：真实 writer 两例

context 半写：保留真实 `_write_exclusive`，只包装它实际打开的独占句柄；在真实 write 写半段后抛 OSError，走生产 writer 的 except 分支。登记 open flags/命中/完整待写字节的单份引用与 SHA/部分实际大小；API/磁盘 failure 链必须包含原 OSError，旧事件不变。

receipt：调用真实 writer 完整写入后再抛有明确类型/文本的 sentinel 异常；必须 Error、完整 receipt 与失败现场保留，sentinel 在传播及 failure 链中。原“追加 X”只可另列字节污染，不得冒充抛异常。无须重跑 TASK-022 六文件 writer 故障，不另造 I/O 框架。

## 7. E2：完整观察、内容与磁盘审核

1. 所有测试直接公开 API（包括 submission_for 中准备）进入同一完整登记；冻结 prepare、store.save/verify、真实 P1、scope 枚举和实际审核 helper 的入口观察/计数分列。按真实代码对象/帧或等效独立观察，不用包装次数冒充 P1，不要求不同层数量相等；区分新提交与历史复算。
2. 真实 P1/存储/准备调用保存完整输入或实际文件现场、完整真实返回/异常 + traceback/cause/field/stage。在核心调用前取得真实引用指纹，返回后和 API 收尾核对，不重复调用核心凑对照。合法空列表结果与缺记录分开。
3. 真实观察完成后、任何终审读取前，独立深拷贝冻结完整预期。首轮同缓冲读对象/大小/SHA；完整 canonical 比较输入/返回与预期，按 call_id/字段定位差异，再做 ID/条目/声明数/独立入口关系审核。False/0、0/0.0 不能相等；键顺序 canonical 等值应通过；预期不从候选磁盘生成/刷新。
4. 经审核的那次真实字节作为漂移与台账预期，完成有界字节确认、台账落盘并读回审核。失败支配 failures/summary/非零返回，不覆盖坏候选、不重建期望/台账掩盖现场。无需台账内嵌自身 SHA。
5. receiver 保存完整 stdout/stderr 原文引用；receive 与 invocation 逐批次一致，内部 checker report/stdout/stderr 真实 exists/SHA/started/退出分别核对；直接 checker CLI 0 与内部启动数分列。下游/网络守卫和读取范围按真实观测写，未知/未执行记 null+原因，不能默认 0。
6. 测试自行实现 canonical/指纹，实读 14 项代码、32 项材料、封套/来源/完整真实返回作独立比较；调用生产 helper 的一致性检查不能独占“独立复算”标签。

最小审核故障：缺一条真实 API/P1 登记、返回替换 {}、合法形状自洽改 reason+同步 record 指纹、False→0、首轮读数后 checks LF。原件通过、每类由实际收尾 helper 拒绝且定位；至少一个内容替换故障和一个缺登记故障经当前真实套件的收尾路径返回 1/FAIL。可复用本轮定稿观察驱动分离的收尾测试，避免为证据故障反复建业务链；不得只跑一个未接入套件的影子审核器。

## 8. 实施顺序与最终交付

先做最小正常/必要负向；B1—B4 与 E1/E2 按组定点，局部问题不重跑整套建链。允许增加明确的定点测试模式，保留完整入口，逐模式如实标未执行项。所有修正完成后，仅一次全新容器完整本卡入口；真实 junction 若环境不允许须说明，不能默默少一例仍声称原全量验收全部通过。保护扫描在实现/测试/指南/回执定稿及最终入口后最后做一次，changed 恰为三个允许修改文件（指南若无需改则可少），missing/读取错误/范围外新增为 0；扫描后只有限登记本轮元数据，不反复遍历全树。

新回执给出 B1—B4/E1/E2 对应证据、真实计数/范围、正常与故障返回、合法排序控制、三份夹具引用、主/次异常链、保护及全部过程偏差。原回执旧路径/八键注释/junction 标签只在新回执更正，旧回执不回写。自身最终 SHA 仅交接给出。

完成本修复后停止实施交 GPT。仍不接宿主/控制器/标准化/DB/Gate2/真实初判/0009/AI/终判；APPROVE 保存仍不等于执行许可。真实批准保持 null，真实业务判断及看板仍由人类负责。
