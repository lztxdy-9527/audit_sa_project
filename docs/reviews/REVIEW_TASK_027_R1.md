# TASK-027-R1 复审：NOT_ACCEPTED（保留已关闭项）

2026-10-15。交付身份逐项实读一致：runtime 110116 B / `1d48ebdc1764561ff3893a703d41bfb4241e21efa4140bbe35f487e11e93013b`；测试81062 B / `6e325787236fa0680eed5a2032decf3b93c489fa372425d7ec73364fae65e1e6`；指南14182 B / `9a6ff309686d87c26e354000063a1fe8d72f8659dd11fa3c2489364691aa8df8`；回执10340 B / `72b9201672769e2639ca4c9be0cfade0a71f639f2983cae6f587e381a68ccdc8`。GPT没有修改这些文件。

本轮证据根 `data/reviews/task027_r1_gpt_20261015_165854/`。完整调用见 api_records.json、readonly_results.json；结果见 probe_summary.json、lock_acquire_refined.json；独立收尾坏候选保留在同根 closure_*。GPT未运行完整80项或历史入口。

## 已通过的修复不重开

GPT真实新建登记/事件，正常save/verify成功；真实store.save返回后改submission快照，本次save已拒绝 `snapshots.submission.json` 并留failure；同位置给登记叶新增failure，save已拒绝 `runtime_dir(叶)` 并留failure。

现存R1事件经当前公开verify复验：APPROVE为true、HOLD/REJECT为false；boundaries数组、三个context来源字段及store返回指纹矛盾均按对应字段拒绝。8次调用相关文件前后不变。B2形状/来源/稳定字段可关闭；真实receipt句柄异常的实现映射及R1留存现场已读取，GPT本轮没有重跑该故障或冻结writer大组。

GPT另以真实新进程CLI只读重放同一R1观察，四个新输出目录：none为0/PASS，candidate-return、drop-call、checks-drift均1/FAIL。旧候选替换、缺API、早期字节漂移问题已修；这四项不因下面残余而一概作废。

## B1残余：verify最后阶段不复查来源/登记集合

在本轮正常事件的verify内包装真实 `_finish_prepare`：其完成全部当前材料确认并返回原值之后，只给本轮登记叶新增failure.json，命中一次。该次verify仍返回effective=true，且没有写事件诊断。撤销wrapper保留现场，下一次verify才拒绝登记叶failure。

原因：verify最后一段只复查已消费文件字节与scope/事件/快照集合，遗漏登记叶固定二文件、批次顶层和四固定子目录。较早 `_finish_prepare` 的集合确认不能替代该次最后确认。save的同类修复已通过，不要求重写save。

## B3残余：取得失败回收仍盲删；无事件时丢次错误

1. 真实lock writer的独占句柄先写全原锁字节、flush并close；在本轮新根内具名保全原文件，于原路径创建另一内容的替代文件，随后抛受控OSError。真实writer映射Error(write.lock)，但 `_acquire_lock` 的异常回收仅检查目录身份，删除了替代lock.json及目录。原锁文件已保全，注入命中1，详见lock_acquire_refined.json。不能因目录仍属本次取得就删除身份/内容未核验的文件。最小修正可以取消取得失败时的自动回收，保留坏锁现场。
2. 错批次submission在绑定预检被拒，事件尚未建立；同次调用先使本次锁内容变化，真实释放检查因此拒绝。API只传播原 `Blocked(submission.batch_id)`，无cause/context/信息带出释放失败，坏锁保留。当前finally仅在event已存在时处理次错误，未满足无事件时也保留主次错误的义务。

成功释放的身份检查已补上。此处只修失败路径，不设计新锁系统。源码还在已有事件失败时重新write failure.json追加次错误；应将主/次错误在最终传播及一次诊断中合并，避免覆盖失败事实。

## B4残余：台账未审核；诊断写入晚于末次确认

GPT仅加载已保存观察到独立内存，调用当前真实finish，新副本不运行任何业务核心：

- 正常副本0/PASS。
- 真实写入file_ledger.json时将候选替换为 `[]`，命中1；仍0/PASS/空failures。finish读取了候选ledger，却未审核它，也未比较其磁盘字节与待写缓冲，最终循环使用内存ledger。
- 在真实第二次audit_failure.json写入完成之后，只给checks.json追加LF，命中1；仍0/PASS/空failures。诊断在最后字节检查之后重写，后续又读取summary/failures作输出，缺少覆盖全部必要消费的终端确认。

修正应让诊断先定稿，正常成功时载荷/台账一次写定，最后实读覆盖全部载荷和台账，预期来自独立内存/待写缓冲。最后确认之后不要再读取候选构造成功输出。无须增加多轮收敛框架。

## 范围与过程记录

保护结果以同根protection_result.json为准，旧损失139项单列，27恢复及旧R5越界326项逐项保护。开发现场允许作为不可回写历史保留。

执行端另将 `data/batches/task027_r1_smoke1`、`data/runtime/task027_r1_smoke1`、`data/human_gate_decision_records/gate1/task027_r1_smoke1_scope` 纳入允许新增。这三根不符合R1卡明示的task027r1命名；本评审按确切路径登记为已披露范围偏差，不追认、不删除、不为改名搬迁。它们未改变旧文件，仅命名偏离作为非阻断过程事项；原“范围外新增0”须在后续回执按严格授权范围更正。

GPT第一个锁控制因Windows不允许重命名仍打开的句柄，在替代文件安装前失败（hits=0）。该记录不作为盲删替代锁的证据；精化控制先关闭本次真实句柄，再安装替代文件，hits=1，原失败脚本/现场保留，不覆盖旧结果。

计数口径辅助事项：R1的direct_prepare=54表示冻结准备器中非save路径调用，并非公开prepare API条数；观察器在安装wrapper之后捕获其代码，profile字段不能称为已独立观察真实P1函数帧。观察wrapper会无条件调用冻结真函数，因此本轮不据此否定已证明的业务结果；后续修正文案并直接保存原函数代码对象计数即可，不扩建观察系统或补跑历史核心。

结论：R1部分关闭，整体验收仍NOT_ACCEPTED。下发限定三个残余的TASK-027-R2，不推进TASK-028。技术核验不批准任何批次，宿主0008、真实批准null、next/AI false。
