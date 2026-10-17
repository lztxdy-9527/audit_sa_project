# TASK-026-R1 复审：部分关闭，NOT_ACCEPTED

日期：2026-10-15。**R1仍未通过；不推进TASK-027。** 当前四份交付身份与交接一致。GPT不修改实现/测试，只在全新隔离副本复验，原现场保持。

## 已确认改善，不再重开

三个API正常控制成功；合法尚不存在scope可以build且未被创建。原空note、契约effective=false、空代码清单、错配置SHA、未知input键、float大小、内层SHA尾LF均已定位Blocked；registry=[]也不再泄漏AttributeError。旧登记输出晚变更反例本次被read定位拒绝。

GPT在真实生产独占句柄复验半写：xb，175/351字节，命中1，实际disk=175；传播RuntimeGate1Error(write.readback)，诊断保留RuntimeGate1Error→OSError链，read拒绝failure现场。**真实writer半写问题关闭**，不要求后卡再次重跑。

scope构建方向、prepare自身独立SHA预期、去除跨操作SELF_BYTES/生产INJECTION_HOOKS、常见schema与派生关系已有实质修正。本轮不按旧91或新71的数量重新定义协议。

## B1残余：read漏静态读数、来源集合未收尾

- `read_runtime_registry`调用`_require_current_static_identity`实读代码/规则/配置，但该函数丢弃capture；read收尾只复测registry/readback/self。GPT使用**字节一致的隔离项目材料副本**，真实capture返回配置原字节后给该副本加LF，read仍成功。未改生产配置/冻结文件。这是覆盖缺失的隔离复现，不声称篡改过真实项目文件。
- 另一真实只读prepare调用观察到：23份既有project材料，只有20份进入`_require_project_file`及末端project集合；缺 `docs/SPEC_V1.md`、`docs/AUDIT_CONTRACT_DRAFT.md`、`sql/demo_schema.sql`。只核对冻结准备器较早返回的摘要，不能替代这些实际消费材料的末次实读。
- GPT真实接收器运行一次建立合法新批次，正常build成功；第二次build在真实`_source_check`返回后，给该新批次`checks/`加unknown.json。**build仍成功**，目录中同时有quality_report.json和unknown.json。来源文件集合没有最终核验，固定八个文件内容未变并不能代替集合检查。
- read/静态读数和来源末端路径状态仍应统一纳入原卡的有界收尾；不要求无限追逐最终字节确认之后的并发修改。

定位：runtime `_require_current_static_identity`（762附近）、read（828附近）、build/prepare收尾（875/971附近）、`_recheck_capture`（282附近）。

## B2残余：少量严格类型与状态

三项隔离副本均同步所有外层摘要/内层run_binding指纹，避免提前遮蔽：

- rules_manifest.entries[0].rule_id=[]，read泄漏**原生TypeError: unhashable type: 'list'**，需在dict查询前判字符串。
- registered_at="not-a-time"，read接受。原卡是带时区合法ISO技术登记时间，非任意非空字符串。
- scope_ref改为已存在的旧空scope，read接受。构建已修，但read没有核验计划scope不存在，不能称三API共同闭合。

定位：`_validate_registry`的registered_at/scope和rule_id查询（626/674附近）。这是现有schema的局部漏项，不新增人类时间规则或批准机制。

## E1残余：记录/守卫/磁盘审核仍不闭合

**守卫并未装到实际入口。** `load_guard_target`依旧创建guard_p1_core/guard_p1_store/guard_sqlite三个独立模块；没有注册到实际加载链，install_guards只返回它们的文件名字符串。相同`__file__`不表示同一个module对象或函数；这些本地替换并不保护实际消费入口。此项依据源码，未调用被禁止核心去制造命中。

**完整观察缺失。** api_records只登记正常build/read/prepare三条，保存outer_keys/部分SHA，未保存完整返回；其余拒绝/错误/重复调用未统一登记。冻结prepare只计15次，不保存完整真实返回/异常。prepare所称before_after两份输入读数均在调用后取得。没有实际完整观察可供候选磁盘逐项比较；本轮不猜测原套件真实API总数。

**台账与出口问题已通过真实收尾复现。** GPT不重跑会在记录根临时mkdir/rmdir scope的业务组，而是只读重放DSH已保存观察，在三个新进程执行**真实测试main和audit_evidence/末次收尾代码**；这不是新业务回归，也不把旧71项称为GPT实跑通过。接收器与业务组在该控制中未重新执行，观察来源明确登记。

- 正常收尾：进程0，PASS，failures=[]，audit_ok=true。
- 末次正式audit读取前只将磁盘checks一条ok改false：真实audit检出三项矛盾、**进程1，但磁盘summary仍PASS、failures仍[]**。未落实失败事实落盘。
- 末次正式audit前只把API记录一处返回SHA改成64个0（ID/计数不变）：**audit_ok=true、进程0/PASS**。台账不含证据载荷，审核也不比较定稿实际观察；内容被替换仍获成功。

`--audit-fail`是在写盘前主动改内存检查，并且按flag直接return1，只能证明预先失败，不能替代以上末次磁盘审核故障。main在“最终字节确认”后又重写summary/checks/failures/audit，再无末次字节确认；文件台账实际四项是两个代码文件和两登记输出，没有覆盖证据文件。不能宣称已一次写定证据并完整覆盖最后字节。

测试仍在真实记录根创建并删除`<round>_existing_scope`，与原卡不创建scope矛盾；可使用已存在的旧scope做只读拒绝对照。out-dir仍用startswith，允许根的同前缀兄弟路径并非严格后代。上述不需要新测试框架即可定点修正。

## 实际执行及保护

GPT登记直接API调用**21次**（verify_current16、io_layout4、capture_coverage1，不含内部函数）；真实接收器CLI1次，未运行标准化/DB/历史链；另3个新进程仅执行main收尾重放（实际receiver/API为0）。原DSH71项/--audit-fail证据只读，不作GPT业务复验通过。原始完整API结果、异常、writer字节、隔离模型和三个main出口证据均在 `data/reviews/task026_r1_gpt_20261015_032227/`。

GPT一次最终全树文件扫描实读157655文件：changed恰三份允许修改文件，范围外变化/新增、missing、读取错误均0；旧R5越界326项不变且不追认。所有新增按确切路径登记，无前缀豁免；上轮两个确切自指元数据单列。文件级保护通过不追认测试在记录根临时建删scope。GPT未改实现、测试或旧证据；扫描后仅有限核对身份及定稿本轮元数据，无第二次全树扫描。

R1对TASK-026旧空scope来源的主动说明已登记：由执行端此前创建，保留不动，不追认。R1回执基线157436与实际157438、指南70项与最终71项属于辅助计数旧标注，非阻断；本报告按实际文件登记，不回写历史。

## 下一步

交 `docs/tasks/TASK-026-R2_DRAFT.md`，只修B1/B2残余与E1收尾。已关闭部分不做补偿回归；保持三个API、原schema/版本/边界，修复通过后再制定下一卡。真实批准null，开发宿主0008，next/AI false；看板由人类处理。
