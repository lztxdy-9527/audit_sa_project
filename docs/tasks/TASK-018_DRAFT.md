# TASK-018：开发态只读审阅包导出与离线核验

日期：2026-10-13。供人类转交DeepSeek。以前置验收 `docs/reviews/REVIEW_TASK_017_R1.md` 为准；GPT负责架构/验收，执行端实施本卡，人类负责真实判断、批准和DSH。

## 1. 目标与停止点

当前开发宿主已经走到0008，但审阅材料散落于批次目录。新增一个独立导出工具，将已核验的事实底稿、显式模拟初判及其来源凭证整理成可离线阅读、逐文件核对的开发演示审阅包，供人类审阅现有能力和后续真实流程的前提。

本卡是现有证据的只读导出，不推进工作流。**宿主与控制器冻结；无0009。** 保持真实批准null、next_step_allowed=false、AI不允许。模拟初判不等于真实人类独立初判；不得生成判断、AI建议、候选等级、终判、正式契约或真实Gate。无LLM、网络、UI、ERP、PDF/Office转换、压缩上传及新依赖。

导出包只包含选定审阅材料，不是完整批次备份、可恢复宿主目录、身份认证或独立审计保证。离线核验仅确认包内文件与清单一致，不证明原始业务真实性，也不重新批准批次。

## 2. 允许新增的路径与冻结

只新增：

- `scripts/export_demo_review_bundle.py`
- `tests/test_export_demo_review_bundle.py`
- `docs/DEV_REVIEW_BUNDLE_GUIDE.md`
- `docs/EXEC_REPORT_018.md`
- 本轮新证据根 `data/review_bundle_tests/task018_<唯一>/`
- 本轮新导出根 `data/review_bundles/task018_<唯一>/`，每次导出为其中一个从未存在的子目录。
- 仅为可控反例新建一个C06b批次：`data/batches/task018_<唯一>/c06b/` 及宿主推导的 `data/sqlite_tests/workflow_gate2/task018_<唯一>/c06b/`。允许失败过程使用另一个明确标注的全新容器，禁止回写、删除或覆盖历史。

所有既有文件冻结，包括本卡、旧测试/回执/评审/指南、SPEC/契约草案、控制器、宿主及所有纯核心/SQL/数据。重点冻结：

- 宿主 `scripts/run_demo_workflow.py` = `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`，版本TASK-017-workflow-host-1.1。
- TASK-017宿主测试 = `c5b31cd798dbbb72759ae94ec65217e28ff86c453947c59cf074ed1dfa651c05`。
- 宿主指南 = `856b39f81b0f37a38709636348621275cbe894bcab4174350107d62968a177c8`。
- 初判纯核心 = `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`。
- 控制器 = `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`。
- 事实底稿核心 = `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`。

保护基线：`data/reviews/task017_r1_gpt_20261013_041026/source_hashes_after.json`；哈希、实际项数和排除项以同目录review_result.json为准。本卡对既有文件必须changed=[]、missing=[]、读取错误0；单次完整扫描复用，不重复全树扫描。不得安装依赖、初始化Git、迁移/补签旧批次或清理现场。哈希记录不代替版本恢复点。

## 3. 独立接口与前提

使用标准库；独立脚本可按现有加载方式导入冻结宿主。公开入口：

`export_dev_review_bundle(batch_dir, out_dir) -> dict`

`verify_dev_review_bundle(bundle_dir) -> dict`

CLI：

`export --batch-dir <batch> --out-dir <new_bundle_dir>`

`verify --bundle-dir <bundle_dir>`

不增加宿主第十子命令，不调用宿主保存/标准化/装载/筛查/复算/底稿/初判核心，不导入旧测试、答案册或生成器作为实现依赖。异常分为 `DevReviewBundleBlocked`（协议/前提，退出1）与 `DevReviewBundleError`（运行/I-O，退出2，保留cause链）；成功退出0，失败不返回成功字典。

导出必须真实调用冻结公开 `inspect_dev_batch`，要求READY、恰合法0008、SIMULATED_INITIAL_JUDGMENT_RECORDED、FACT_PACKET_RECORDED、完整MATCHED、开发模式、真实批准0、next严格false、AI实际许可严格false。不得直接信任调用方提供的status字典，不能绕过宿主绑定/失败诊断/链核验，也不在新工具重写宿主协议。

`out_dir`解析后必须位于 `data/review_bundles/` 的本轮根下，是从未存在的目录；既有空目录同样拒绝，不覆盖。必须拒绝与源批次/外置DB相等、互为祖先、越出导出根的路径；检查后独占创建。输入源只允许宿主支持的批次路径。路径判断以解析后的绝对路径为准，不用字符串前缀。

## 4. 固定白名单与精确字节

成功包恰为 `manifest.json`、`README.md`、`host_status.json` 及 `evidence/` 下的以下22份来源文件，保留相对层级：

- `batch_manifest.json`、`checks/quality_report.json`、`gate1_packet.md`（3份）。
- `workflow/host_manifest.json`（1份）。
- `workflow/checkpoints/0001.json` 至 `0008.json`（8份）。
- `workflow/screening/screening_report.json`、`workflow/crosscheck/crosscheck_report.json`（2份）。
- `workflow/fact_packet/started.json`、`fact_packet.json`、`fact_packet.md`、`artifacts.json`（4份）。
- `workflow/initial_judgment/started.json`、`submission.json`、`initial_judgment.json`、`artifacts.json`（4份）。

不得扫描并复制任意目录，不额外复制输入Excel、normalized、数据库、代码、密钥或整个运行树。源文件内容中的路径、URL、指令样式字符串只作为数据，不执行、不据此追加复制项。每个来源路径由工具固定，不允许清单中的任意路径驱动源读取或输出写入。

每份源文件一次读取同一缓冲，从该缓冲取得长度、SHA-256和需要的JSON对象，输出复制该确切字节。JSON不重排，Markdown不换行转换、不加BOM、不改banner/判断原文。文件字节哈希与packet/record规范对象指纹分列，不相互冒充。

初始预期只能来自第一次真实合法status：其verified_files、host_manifest、checkpoints、screening/crosscheck/fact_packet/initial_judgment摘要已经给出上述22份的文件哈希。逐项明确映射、严格比较后才能复制；不能把自己后来读取的哈希作为“原已绑定预期”。所有哈希格式要求完整64位小写十六进制，不strip/截断/忽略后缀。

`host_status.json`保存实际第一次公开status完整返回对象；采用明确UTF-8无BOM/LF序列化。`README.md`由固定模板生成，UTF-8无BOM/LF，只展示批次/主体期间、R01—R04数量、事实包规范指纹、模拟记录规范指纹、相对材料链接及能力边界；事实数值直接取已核验返回，不重新筛查/计算金额，不自动推导“无问题”。不生成或改写assessment/reason，不提供候选结论/等级/取证意见。前部明确：合成数据、开发演示、模拟初判已保存、真实人类初判未保存、真实Gate未批准、AI未开放。保留原fact_packet.md中的既有banner。

## 5. 清单、有限收尾与失败现场

manifest版本固定 `TASK-018-dev-review-bundle-1.0`。包含batch_id、源批次身份、宿主版本及实测代码哈希、导出工具实测哈希、0008初始文件哈希、packet/record规范指纹、开发/模拟边界，以及24份payload（22份复制件+status+README）的固定相对路径、确切字节数、文件SHA-256；复制项另记原批次相对路径与初始绑定文件哈希。

manifest不内嵌自身哈希；返回值/CLI可给manifest实际文件哈希。不新增当前时间、随机ID、推断身份或业务判断；相同源和代码重复导出到不同新目录，24份payload与manifest字节应确定性相同（不把导出目标绝对路径写进内容）。真实批准null、human_initial_judgment=null、ai_suggestion=null、final_judgment=null、next/AI严格false的含义明确。

使用少量直接步骤，不建通用I/O/日志框架：

1. 检查路径与初始公开status；读取白名单，同缓冲校验初始预期；所有前提失败时不创建输出。
2. 独占创建输出，使用独占writer保存24份payload，读回与确切待写字节比较。
3. 末次真实公开status必须仍成功并与初始完整返回严格规范相等；不接受“最新读数替换初始预期”。
4. 在末次status/全部必要对象消费之后，实读22份源文件和status绑定的外置DB字节，与初始绑定预期比较，并复核输出24份payload；禁止用缓存自比。
5. 最后独占保存manifest，读回严格等值；返回成功前再核对payload/manifest实际字节、源22份/DB初始字节、包内固定文件集合及无failure。只做明确有限确认，不承诺阻止任意时点并发篡改。

输出创建后发生任何Blocked/Error均只在新输出目录留 `failure.json`（版本 `TASK-018-dev-review-bundle-failure-1.0`，stage/export、目标退出码、异常类型/原因/完整链、已完成步骤），不修改源批次、不向宿主写failure、不清理半写输出、不重试覆盖。如果诊断也写失败，如实保留原异常与诊断错误，不改报成功。前提阶段没有新输出时不写外部失败文件。

`verify_dev_review_bundle`只读包内固定文件，不读取原批次、DB或运行宿主/核心；严格检查manifest协议/类型/固定边界、固定文件集、24项逐项大小与SHA、必要的status/0008/packet/record身份一致。存在failure、缺件、未知文件、重复/越界清单路径、指纹后缀、内容变化、半写manifest等均拒绝。成功状态为 `DEV_REVIEW_BUNDLE_VERIFIED`，scope明确 `COPIED_BYTES_ONLY`；输出历史宿主status不能当作当前宿主状态或真实批准。

## 6. 有界验收组

仅用最终代码创建一个新C06b到0008，显式提供模拟提交；测试造样的宿主CLI/API逐次登记。该新批次供反例使用，禁止改冻结历史或重跑旧任务入口。不要为每个输出故障重复建上游链。

1. **正常导出与确定性**：同一新批次分别经公开API和CLI导出至两个新目录；25份文件及24项清单齐全，两份成功包逐文件字节相等；逐项对比源同缓冲/初始status预期/复制件。实际公开status调用次数可观察；离线verify成功。C06b事实数量1（R02=1）、事实包/记录指纹和原文保持。未执行MAIN或零条时不填对应实测数。
2. **前提与路径**：已有输出（包括空目录）拒绝且原件不变；输出等于/位于源内、越界/父路径等有限反例拒绝；缺0008/宿主Blocked或Error通过明确测试替身分列核对传播，不冒充真实业务链复验。至少一个实际缺失批次由真实宿主拒绝。源/DB无写入。
3. **晚变更**：仅在本轮新批次，包装真实末次status，在其返回真实原对象之后给fact_packet.md追加一个LF，不同步哈希；本次导出即Blocked/退出1且指出文件，新输出failure有效、无成功返回；撤销wrapper保留变更后真实status1、只恢复目标原件后status0。源恢复后全部原字节相等，0001—0008始终不变，不写宿主failure。保留注入点、真实返回、前后哈希和CLI原文。
4. **写入失败**：复用同一合法源、分别用两个全新输出，包装导出工具真实writer打开的句柄，让一次真实write半写后抛OSError；再做manifest真实完整写后抛sentinel。记录真实open模式/命中、确切待写UTF-8字节单份保存读回、半写实际字节与完整throw哈希；导出运行失败2，离线verify拒绝有failure/不完整包。不能替换整个writer来宣称其真实分支执行；源/DB/旧包不变。不要重跑宿主0008 writer故障。
5. **离线核验反例**：只在成功包的隔离副本改一个payload字节、清单哈希加LF、重复/越界清单路径、加未知文件等有限反例均Blocked1；verify在原批次/宿主读取被替换为“调用即抛错”时仍成功，证明不依赖原路径。来源字段即使含绝对路径，verify也不跟随。原成功包不变。
6. **只读与停止点**：六个真实下游函数计数抛错守卫下export和verify成功、命中0；观察冻结公开status确实被调用。源批次/DB前后SHA不变、0008.workflow不变、无0009、真实批准null、next/AI=false。测试I/O不算核心调用；子进程内部次数未观察则null。
7. **证据与保护收尾**：所有实际公开API/CLI/替身映射分列登记，每条完整返回或异常+traceback/链/字段，CLI原文；权威registry与记录双向比较、文件台账逐项实读exists+sha；仅删审核副本一条登记的隔离自测须失败。missing/unregistered为实际执行值并进入failures，不用默认零。一次扫描保护基线，既有文件changed=[]/missing=[]/读取错误0，冻结重点另核对。输出counts注明scope、未执行项null。

最终入口固定 `tests/test_export_demo_review_bundle.py --out-dir data/review_bundle_tests/task018_<全新>`，7组结果及完整failures落盘。先正常小样，再必要负向与最终入口；局部失败定点修正，不反复全套建链。允许实现必要定点模式，但成功返回前对应证据/保护收尾须实际执行；未执行收尾明确null/not_executed。

## 7. 交付与后续

回执给源文件写后完整SHA-256、实际入口/退出、七组证据路径、真实调用与替身/子进程scope、22份源和24份payload逐项比对、原文/确定性/晚变更/真实writer/离线verify证明、保护基线身份及结果、过程失败/未解决项，列测试/导出/新批次/SQLite四条绝对根路径。自身哈希只在交接给出，不写回自身。

完成后停止本卡实施，交GPT验收。不得借导出工具解锁AI、保存真实初判、建立正式契约/真实Gate或推进0009；真实流程的业务前提由人类决定。验收通过后GPT按持续授权制定下一卡，DSH关闭仍由人类操作。
