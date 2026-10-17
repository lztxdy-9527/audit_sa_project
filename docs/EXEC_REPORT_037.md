# TASK-037 执行回执：声明命名域的只读历史核验与索引

状态：执行端交付，待 Architect 独立验收；未自行 ACCEPTED，未操作看板，未推进下一任务。scope=`DECLARED_NAMESPACE_CURRENT_SNAPSHOTS_ONLY`。回执先定稿，最后保护实测和四件身份由本轮 `protection_result.json` / `delivery.json` 有限发布；本回执不写自身哈希或尚未执行的扫描零值。

## 1. 依据、身份与授权范围

按 `docs/tasks/TASK-037_DRAFT.md`、`docs/reviews/REVIEW_TASK_036_R1.md`、同根 review_result / 新接受快照实施。适用 AGENTS.md 有限检查未发现。TASK-036-R1 接受基线167567项，SHA `84d572da1a88b3e651716eb6ea8a2ffe6a03418715b4085493827e53b6a9b103`；任务卡 SHA `79bf9746fd0681edb12be6e1a1ab43a657202c9b6468b185e50adcc480b4543f`。实施前实际核对12份起点文件及源夹具，保存 `task037_prepare_01/starting_identity.json`；人类夹具和技术四输入原字节均具名保全。

冻结 store 25787 B / `a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c`；其测试38400 B / `68c802e6ea1872acc67d4021bc1c3119039fa6298b248328a8576c5eefd3c66a`。初判核心28927 B / `312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35`，运行层264105 B / `65946ffd740771c3917297d5d566c147c641004547fbbbb71873d5b53898e78a`。契约/生效登记/协议/案例均核对接受身份，不修改。

仅新增四件交付物：

- `scripts/inspect_demo_human_initial_judgment_history.py`，15064 B，SHA `7276ddb704d27cec031ca3c2af4122a3c2c890d613bd4cfa90e6454d72000b22`。
- `tests/test_inspect_demo_human_initial_judgment_history.py`，31409 B，SHA `0ae7ae9d45ee4a8a443f0fb91893db24ecac69a6c77771fbf11280ec6ff817c5`。
- `docs/HUMAN_INITIAL_JUDGMENT_HISTORY_GUIDE.md`。
- 本回执 `docs/EXEC_REPORT_037.md`。

后两份及四件完整写后长度/SHA统一在 `data/human_initial_judgment_history_tests/task037_finalization_01/delivery.json` 登记。新增测试根仅 prepare_01、dev_01/02/03、run_01、finalization_01、cli_none / cli_candidate_return / cli_ledger_late / cli_checks_late（均加 task037_ 前缀）；记录根仅 dev_01/02/03、run_01 四个同名前缀根。所有新增展开为确切文件名单，不用目录前缀兜底。未修改任何既有源、指南、任务卡、回执、证据、快照或凭证。

## 2. 实现与检查次序

唯一公开 API 为 `inspect_human_initial_judgment_history(namespace_dir, *, expectations)`，无 CLI。全自有字段次序在实现前写入新指南：期望四键/安全路径/名单 → 冻结组件 → 原始 namespace 路径及成员 → 每叶 failure/布局/同缓冲字节 → 一次真实 store verify 和完整绑定 → 事件/批次唯一及 scope → 全域旧引用闭合 → 构造返回 → 末次字节/集合确认。顺序按 schema/叶 UTF-8/旧引用原列表，不受候选字典插入顺序影响。

只枚举显式既存 namespace 的直接子目录；不全项目递归搜索、不猜目录名决定忽略失败、不创建/补齐缺失域。expectations 恰四键，expected_entries 恰两字段成员，SHA 严格完整64hex、安全单段叶名、UTF-8升序唯一，与实际成员双向完整相等。failure（坏型也包括）在manifest消费之前拒绝，不能跳过凑空域。

固定 store 源原缓冲实读并核 SHA 后加载；直接复用其11个有限 helper，精确名称已在指南列出。调用方组件开始读数和 history 自身 SHA 真实实读，不跨调用缓存。每叶真实 store verify 恰一次，冻结 store 再嵌套核心；本层不直接调用核心或 store save。先把实际完整十一键返回与本次六缓冲/四快照/两键完整结果/manifest FILE、组件和元数据绑定，成功后才提取四字段索引。FILE 与对象 FP 分列，不用自报索引替代完整快照。

域内 event_id 唯一、batch_id 唯一，重复事件先于同批冲突定位第二叶。输出索引按 event_id UTF-8 升序，但 verified_snapshots 保持叶名单顺序。两处 scope 均与独立声明精确相等；全部叶完成后按原引用顺序查每个 event 并核对 batch/record FP/binding FP。不推断时间先后、不重建递归历史、不返回部分成功。

成功恰十二键、prior_history 三键与 inventory 三键及各自规范 FP、component_bindings 七项、完整 verified_snapshots 列表和九项严格 false 边界。核心八 false、store 九 false及原文本/业务状态不改。返回深拷贝在最后确认前构造；之后只比较开始组件/namespace/六文件/集合原字节，不再解析候选或保存索引/失败/日志。

Blocked 保留 field/reason，冻结拒绝加叶下标前缀并 `raise from`；Error 保留原 stage/reason/cause，不统称 Blocked。受控真实 read 边界 OSError 实测为 HistoryError(read) → StoreError(read) → OSError；主说明和异常链保留，未泄漏裸异常。

## 3. 夹具、独立预期与完整性限制

首份人类源1627 B / `81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560`；第二份1728 B / `e7bb88137e11e4db2b24aeaa05a4a488084f7d57fd424f25c2166de17696868a`。仅使用已登记 event_id="1"/"2"，其余五项沿登记原文；不自造第三人类事件/身份/时间/assessment/reason。PROTOCOL_TEST_FIXTURE_ONLY 标签放协议外。

技术 batch/request/材料关系在构造期独立定稿，M为去掉materials_fingerprint后正文的规范 FP；submission/expectations 相应摘要及历史 FP 在调用前同步固定，不称实际 Gate/fact 核验。第二份历史引用由较早一次实际 frozen store verify 的完整观察提取、固定在第二次 setup save 之前，见 `fixed_prior_reference_source.json`；不是从待测 history 索引刷新。其他反例每次是新场景，外层摘要正确闭合，保留原坏字节。

declared_complete=true 只证明当前明确域成员/独立名单、全部完整快照和已声明引用闭合且末次未变；不证明历史从未删失、不发现域外或无引用删失、不认证人类身份/业务来源，不证明旧提交当时完整枚举。空域同样核冻结组件，不能由空目录推断全球完整性。

## 4. 定稿入口与问题族

实际命令：

```text
.venv\Scripts\python.exe -B tests\test_inspect_demo_human_initial_judgment_history.py --out-dir data\human_initial_judgment_history_tests\task037_run_01
```

退出0；62项检查/0失败；audit_ok=true、bytes_ok=true、problems=[]、drift=[]。这是本任务新层有限入口；未重跑84项存储、156项纯核心或历史 Gate/SQL/事实/运行套件。

- 空域/一条/两条：完整十二键独立预期一致；verify/core分别0/0、1/1、2/2。反序叶名 a_second/z_first 对应事件2/1，输出事件仍1/2；返回无输入别名，实际原字节不改。
- 重复 event、同batch不同event：两个完整独立快照先真实 verify/core各2，再按优先关系拒绝。scope矛盾叶实际 verify/core各1。缺引用event、错batch/record FP/binding FP均保持该叶可核验、外层摘要闭合；错引用双叶先实际 verify/core各2，之后才在引用字段拒绝，未用早期错误遮蔽。
- 期望null/缺键/未知键/名单null/乱序、SHA尾LF、安全路径错误、namespace不存在/根自身/越界/错声明、实际成员缺多/根文件/子树均准确拒绝。缺payload从新目录只复制其余文件；截断场景保留六文件并只截断本轮 expectations 字节，称合成截断，不称执行了 writer 失败分支。
- 叶 failure=[] 先拒绝，生产窗口该次manifest读取0；错误组件经真实 store verify 拒绝、核心0。真实 verify 返回后改完整结果指纹的受控替换被完整同缓冲绑定拒绝（真实核验/core已各1），不只比较自报指纹。
- 原始 alias/.. 合成reparse元数据控制：实际 alias lstat命中1、history Blocked、store/core0。物理junction未执行，仍null+既有系统权限限制，不重试。
- 只改本轮副本的核心源：叶捕获返回后追加LF，调用store之前按开始组件读数拒绝，store/core0。冻结原件不改。
- 最后语义消费后修改本轮 judgment_result 字节：本次拒绝；撤销wrapper保留坏字节仍拒绝；具名保全坏缓冲后仅精确恢复本轮单文件，核验成功。namespace末端新增直接成员也本次拒绝，撤销后坏目录保留并继续拒绝。无failure写入、无清理。

完整问题定位、每次真实增量、参数/返回/异常、命中及现场见 `checks.json`、`api_records.json`、`core_records.json`、`controls.json`、`io_observations.json` 与坏字节保全。

## 5. 三层观察和只读守卫

定稿原代码对象 profile 实测：history39、setup store.save9、嵌套 store.verify20、纯核心28。纯核心28分为setup9与history内部19；20次verify中1次在错误组件处先拒绝/核心0。API载荷48条=39+9，嵌套载荷48条=20+28（通用短收尾字段core_records在本卡表示两类嵌套，绝不把48称为纯核心调用数）。

每条记录完整入参/kwargs、实际父call_id；store verify与再嵌套核心还保留parent_nested_id。原代码对象按身份独立计数，与完整条目/实际增量闭合。内存原引用调用前/返回后/API收尾三时点，Path按不可变原路径对象及有界文件现场分别登记；普通history调用现场前后一致，故意晚变更由当前具名控制单列，不引入跨调用豁免集合。

写入/网络/子进程/当前时钟四个守卫先真实证明拒绝；生产窗口guard命中0、其他业务代码入口0。history窗口写文件事件0，os.open及目录/删除/移动等mutator同样禁止，setup允许写仅本轮新记录根。测试故意注入使用事前捕获真实I/O入口、确切本轮目标，单列测试行为，不放宽生产窗口权限。读取只本域/七组件，副本控制仅额外授权该一条具名本轮文件读取。

## 6. 独立本地审核及四个实际 main

`task037_finalization_01/verify_local.py` 退出0。只读复用已验收短helper，不执行旧run/main、不复制通用框架；另写的有限审核校验定稿预期与候选完整内容、七项台账实读、原引用三时点、父调用及分层计数。28份成功纯核心返回由独立协议构造器重建；19份成功store返回另按四快照/完整记录/独立manifest和六缓冲重建，完整十一键及路径现场大小/SHA一致；正常空/一/两域十二键与独立预期一致。

四个新进程真实执行当前main，只读replay定稿源：none→0/PASS/空failures；candidate-return→1/FAIL；ledger-late→1/FAIL；checks-late→1/FAIL。后两项均末次实际读取后追加一个LF、命中1、坏字节保留，失败由实际内容/字节确认支配，不按注入标志直接返回。

profile原代码帧四进程新增history/store/core/其他业务调用均0；源逐文件SHA不变；历史39/9/20/28只作回放载荷，不冒充新调用。实际命令、stdout/stderr原文/长度/SHA、返回码和探针位置见 `closure_controls.json` 及四个 task037_cli_* 根。审核失败不回填候选、不刷新预期、不重建正确台账掩盖漂移。

## 7. 保护与过程记录

代码、测试、指南、回执和局部证据定稿后，`finalize.py prepare` 有限登记身份，`scan`仅一次全树遍历，最后`publish`有限登记自身元数据。保护实际结果见 `task037_finalization_01/protection_result.json` / `delivery.json`：以167567接受项核查既有changed=[]，新missing/读取错误/未知新增/身份漂移；新增逐个确切路径，接受快照自身及review_result仅两条旧元数据单列，无前缀豁免。扫描后不重扫、不回写回执。

139历史损失与当前missing分列；27恢复、326越界、19命名偏差、TASK-030具名41B锁及所有旧失败现场按身份核对，未追认/恢复/补造/迁移/删除/移动/清理。全卡未执行递归删除、移动，未修改旧记录。

如实保留过程：dev_01为58检查/1失败（测试助手把显式null当成默认值，schema.null未按预期测试，其他结果不冒充定稿）；dev_02读取故障注入过早命中调用前取证，未完成收尾，不能称整套PASS；修正为真实_read_bytes代码边界；dev_03为61检查/0失败。最后固定引用来源为较早真实store verify，并补单独截断场景，定稿run_01为62检查/0失败。所有开发/异常/坏目录具名保留。只以run_01及finalization_01为正式交付，不混各轮计数。

未执行项null+原因：物理junction（既有权限拒绝）；额外闰日/±14人类正例（未提供）；全时间/域外/不可删历史保证、运行接线、真实初判业务保存、AI/终判及历史大套件（不在本卡范围）。未安装依赖、初始化Git、调用子Agent、跨会话发指令或修改看板。

## 8. 交付停止点

固定合成业务、整数分/原字符串ID、主表及分摊分别计量、线索不是结论的口径不变。真实批准null，真实独立初判未保存，开发宿主0008，next/AI=false。本卡技术索引不认证身份或来源、不批准批次、不形成审计结论。交付后停止，等待Architect独立验收，不自行实施运行接线或下一任务。
