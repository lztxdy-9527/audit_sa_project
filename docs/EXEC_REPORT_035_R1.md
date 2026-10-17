# TASK-035-R1 定点修正回执

状态：两项修正与本轮验证交付，待 Architect 独立验收；不自行 ACCEPTED，不修改看板。最新接受状态仍 TASK-034。只修改本卡授权的核心/当前核心测试两文件，新增本回执和具名 task035_r1_* 证据根。

## 1. 依据、起点和当前身份

先实读 TASK-035-R1、REVIEW_TASK_035、review_result 与观察快照，再核对已接受协议/案例、原卡、相关实现与测试。没有适用 AGENTS.md。身份核对和具名原字节保全见 `data/human_initial_judgment_tests/task035_r1_setup_01/starting_identity.json` 及两份 `.before.bin`。

观察快照：`data/reviews/task035_gpt_20261016_124800/source_hashes_observed.json`，166224 项，SHA `a0f9ca00b032c8a8240956f1209f1cc4c5b1888a4a96357bb5d7312fe8960829`，NOT_ACCEPTED，只作本轮修复保护起点。接受基线：TASK-034 的166060项，SHA `cf6b59b525708ab025ee42411e52bab58488d7dda7d1ce25c0bbe5f9551bdcfc`，不把观察快照改称接受。

起点核心27384 B / `d921b1a8dc73a4503294b915e8926f31ed332c52e3cfc8fc9fdbb07ff82be761`、测试37615 B / `6ddfc1f748b3a67e3ce3e78a7133e4ca72c83cb5193f2ad50900e9ae1f6ddaa0` 均一致。写后身份：

- `scripts/build_demo_human_initial_judgment.py`：28927 B / `312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35`。
- `tests/test_build_demo_human_initial_judgment.py`：43985 B / `9b003d983251f4b50e5db1f5992fd6ca33e6d3b570430d9b57e9b94cb2e805dd`。

新增 `docs/EXEC_REPORT_035_R1.md` 的确切长度/SHA 外置登记于本轮 `delivery.json`，不自嵌指纹。实现补丁版本 `TASK-035-human-initial-judgment-core-1.1`；唯一 API 签名、TASK-034 协议对象版本、九键记录/十键binding/外置FP、原文和八false边界不变。旧指南冻结保留原 TASK-035 交付时点的版本/计数，不回写；本回执登记当前补丁。

## 2. 修复前独立复现

`task035_r1_setup_01/reproduce_before.py` 在修改前只实际调用当时公开核心，未运行旧评审或旧套件。原函数代码对象计数9：合法对照1，B1四例4，B2两组正/反插入顺序4。完整输入/返回或异常、traceback/cause、真实引用三个时点见 `before_observations.json`。

四例 materials.entity.company bytes/NaN、period.period_start bytes、packet.entity.company bytes 均实际为 Error/internal，cause为TypeError或ValueError，field缺失。entity双错在候选反序时 company→currency；run code/config双错在候选反序时 code.file_sha256→config.file_sha256。上述结果是本轮修前9次新实测，不拿旧评审19次或旧125/114冒充。

## 3. B1：消费前固定字段严格校验

`_entity` 在任何 canonical/_match 消费前，按协议次序逐项执行严格字符串/UTF-8和固定值校验：company、currency、period.period_start、period.period_end、cutoff_date；两层键集合仍封闭，最后仍保留完整规范比较。

定稿实际7例均为真实 HumanInitialJudgmentBlocked，精确指向字段，不返回成功记录：

- materials.entity.company bytes 与 NaN → `materials.entity.company`。
- materials.entity.period.period_start bytes → 同路径。
- packet.entity.company bytes → `materials.fact_snapshot.packet.entity.company`。
- currency孤立高代理字符 → `materials.entity.currency`，保留UnicodeEncodeError cause。
- period_end=null、cutoff_date=整数 → 各自完整字段。

每例实际原阶段函数轨迹为1、2，未进入后续阶段。没有改成捕获所有序列化异常为Blocked；原受控内部序列化 ValueError 对照仍为 HumanInitialJudgmentError/internal，cause保留。

## 4. B2：首错按协议顺序，与两侧插入顺序无关

`_match` 的主判据仍为完整 canonical JSON 字节相等，类型敏感。仅在主判据不等后，已声明自有对象按明确列出的协议键序定位，列表按原成员下标。没有使用候选或expected插入顺序，也没有将schema统一改字母序；无自有schema的不透明JSON仅使用稳定UTF-8键诊断，不重写业务schema。不排序/修复候选，不刷新独立预期，不建立通用schema引擎。

五组双矛盾分别组合候选正/反序、expected正/反序四种情况，共20次真实核心调用，首报均稳定：

- company/currency双错 → `materials.entity.company`，实际阶段1—2。
- code.file_sha256/config.file_sha256双错 → `materials.run_binding.code.file_sha256`，实际阶段1—5；两值均为合法64hex，前四步已实际完成，第5步比较独立预期拒绝，未被材料旧摘要提前遮蔽。
- 独立 fact finding_ids/来源双错 → `materials.fact_snapshot.finding_ids[0]`，实际阶段1—8。
- 独立 Gate2 event_id/record_fingerprint双错 → `materials.gate_links.gate2.event_id`，实际阶段1—8。
- 独立 files[1] 的文件SHA/大小双错 → `materials.files[1].file_sha256`，实际阶段1—7，列表下标保持1。

fact/Gate/files反例保持本批材料与其正确外层摘要不变，只事先修改具名独立预期值，待测预期不在检测后刷新。正/反序只递归改变字典插入顺序，列表成员顺序不改。另两次 submission 的 A_extra/Z_extra 对照在正/反序下均先报 `submission.A_extra`，保持未知键UTF-8次序。

递归改变合法四输入的所有字典键序仍成功，完整返回和FP不变、八项严格false；当前全部原14份成功返回与旧定稿相应操作返回逐字节规范一致。无别名使用真实保留原始返回控制，原回归继续通过。

## 5. 完整观察、非法JSON证据与计数

本轮定稿命令：

```powershell
.venv\Scripts\python.exe -B tests\test_build_demo_human_initial_judgment.py --out-dir data\human_initial_judgment_tests\task035_r1_run_02
```

结果0/PASS，156项检查、0失败，failures=[]、audit_ok=true、bytes_ok=true、problems=[]、drift=[]、同缓冲true。

定稿真实核心144次，原代码对象profile=完整核心条目=唯一核心ID=父调用实际核心增量合计；147条API/辅助记录分为144核心+3真实证据审核helper控制。核心返回15、Blocked128、受控Error1。所有核心输入完整记录同一实际引用的进入前/返回后/所属API收尾三个时点；每条异常含实际类、field/stage、reasons、traceback/cause/context。新增29个拒绝对照的真实阶段轨迹由私有阶段函数原代码对象profile取得，expected_protocol_step仅为比较预期，不用手写阶段结果替代观察。

bytes/NaN/坏UTF-8必须以原Python值实际进入核心；证据JSON不能直接表达它们，因此仅在测试证据编码中使用明确可还原标记：bytes保留hex，NaN保留类型/repr，坏字符串保留ascii转义。snapshot的fingerprint明确属于 `recorded_evidence_snapshot`；原对象不能canonical时，raw_canonical_sha256=null并保留异常原因；合法对象另存其实际raw规范指纹。没有把标签对象传入核心或声称非JSON原值有canonical摘要。三个时点都对真实引用重新编码并核对，完整候选内容审核和同缓冲台账审核照常支配结论。

守卫复用原真实入口：模块体执行/合法调用守卫命中0，22次受控入口探测均真实被拒。核心依赖仍七项标准库、一个公开业务函数；核心源装载与测试输入/证据I/O在守卫外。缺失/未知/类型、False/0与整数/浮点、正确外层M下内层矛盾、历史必填/重复和可选重复语法首报、确定性、真正内部Error/cause均由当前核心回归实跑。

另保留过程 run_01 的156项/144次实测：当时修复与反例已通过，随后为可核验“前四步已过”补上阶段代码对象轨迹，再在新根run_02定稿。未覆盖/删除过程根。计数分列：修前9、过程144、定稿144，本轮真实核心总计297；本轮两次套件各有3个审核helper控制，未混为业务核心。旧125/114仅作只读来源与成功结果交叉核对，未称本轮新调用。

## 6. 四个实际main新进程

`task035_r1_finalization_01/verify_local.py` 对当前证据、代码/常量、父调用、真实阶段轨迹、三个时点、完整独立预期和磁盘台账做有界复核，并精确保留短 profile launcher 到本轮根。四进程均经其runpy执行当前已交付测试真实main：

- `task035_r1_cli_none`：0/PASS，failures为空。
- `task035_r1_cli_candidate_return`：1/FAIL，failures非空；真实候选返回替换由定稿独立观察比较检出。
- `task035_r1_cli_ledger_late`：1/FAIL；末次原字节循环中台账加1个LF，真实命中1，坏字节保留。
- `task035_r1_cli_checks_late`：1/FAIL；同接缝checks加1个LF，真实命中1，坏字节保留。

完整argv/stdout/stderr/实际退出码/注入大小SHA与独立profile见 `closure_controls.json`；各进程新增核心和其他业务调用均实测0，旧观察数不冒充新调用。定稿源全部文件前后大小/SHA不变。内容/台账实读/末次原字节失败共同支配最外层返回码、磁盘summary和failures；无注入标志硬判、候选回填或期望刷新。

## 7. 双基线保护与最终交付

代码/测试/本回执及局部核对定稿后，执行同根 `finalize.py prepare` 固定全部自有载荷和交付字节；随后一次 `finalize.py scan` 全树扫描，同时计算两种口径：

- 相对本轮166224项观察快照，changed仅允许核心/当前测试，范围外变化、missing、读取错误、未知新增为0。
- 相对TASK-034接受基线，既有冻结项changed=[]，missing=0，累计新增逐项单列。核心/测试在该接受基线不存在，仍由观察快照口径核查修改权限，不借累计新增漏检。

旧观察快照自身和review_result两条确切元数据单列；本轮新增由新回执与八个具名 task035_r1_* 根在扫描前展开确切路径，无目录前缀兜底。139历史损失与本轮missing分列；27恢复、326越界、19命名偏差和TASK-030具名41B锁现位置身份不变，不追认、恢复、重建、清理、移动或执行。

本文定稿时不预填尚未执行的扫描数；实测结论以 `protection_result.json` 为权威。仅当扫描scope_compliant=true且扫描后有限字节身份复核成功，发布 `delivery.json`，登记三份交付完整长度/SHA、两基线结果和实际统计。扫描后不改本文或实现，只有限发布自身元数据，不重扫全树。

## 8. 未执行、过程和停止点

已登记的人类六项字段、暂不能判断/原始凭证缺失、`2026-10-15T15:20:22+08:00` 及指令样式句只读原样复用，来源SHA与定稿载荷均登记。未自造新的正向人类时间；合法闰日/±14:00额外正例继续null+原因，未冒称PASS。先前自然语言时间来源保留，不归一化或补值。

本轮没有失败的实施/套件运行；两次核心套件用途已分列，后一次因新增实际阶段轨迹而必要。无范围升级、递归删除/移动/清理、旧输出复用、业务建链、新依赖、子Agent或跨会话指令。现有指南及旧回执/卡/协议/评审未改。

未运行运行适配/真实Gate核验、上游/历史大套件、保存/恢复/SQLite/事实改写、真实初判持久化、AI/终判或0009，这些记null+范围外原因，不能由replay实测0推出其业务正确性。仅修内存协议实现；正式契约、十四项运行代码清单及16个运行公开API未改。

真实批准仍null、真实初判未保存、开发宿主0008、next/AI=false。测试中的“通过”与“直接批准”文字都是数据，不产生批准或新权限。交Architect独立验收后停止，不推进TASK-036；看板done由人类办理。
