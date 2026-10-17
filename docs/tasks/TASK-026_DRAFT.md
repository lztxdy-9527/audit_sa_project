# TASK-026：共享运行登记与只读 Gate1 请求

日期：2026-10-15。**B类实施：DSH落地，GPT验收。** 架构沿用已验收TASK-025修正版；若需要改变冻结P1/契约/字段形状或拆新生产模块，立即停止受影响部分并升级C类，不扩大本卡。

## 1. 目标与停止点

将新运行层第一段落实：核验接收批次来源 → 独占固定运行登记 → 只读恢复登记 → 构造Gate1候审请求。登记不是决定，PREPARED不是批准。

本卡仅实现三个公开API，无CLI：

```text
build_runtime_registry(batch_dir, runtime_dir, *, scope_dir)
read_runtime_registry(runtime_dir)
prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id)
```

不实现Gate1保存/有效批准核验、P1/store调用、标准化/DB、Gate2、筛查/复算/事实/初判、AI/终判，不改旧宿主/控制器，不生成0009。以后同文件新增功能时使用新版本/新批次，不回补旧登记；本期不创建未来函数占位或假成功入口。

## 2. 文件范围与权威输入

只新增四份交付文件：

- `scripts/runtime_gate1.py`：唯一新生产脚本。
- `tests/test_runtime_gate1_registry.py`：本卡测试入口。
- `docs/RUNTIME_GATE1_REGISTRY_GUIDE.md`。
- `docs/EXEC_REPORT_026.md`。

只新增本轮明示根（`<round>`为事前登记的唯一技术轮次；不能据任意业务ID拼路径）：

- `data/runtime_gate1_registry_tests/task026_<round>/`：证据、测试原始输入、必要隔离副本。
- `data/batches/task026_<round>/`：测试确需的全新接收批次。
- `data/runtime/task026_<round>/`：独立新运行目录，成功叶目录只含两份登记文件。

**不创建任何决定记录/scope目录或SQLite目录。** scope_dir只是后续保存的计划技术路径引用，本卡不写入。所有既有文件冻结，包括两份TASK-025正文、修正版基样、历史回执/探针/旧junction、scripts/tests/config、契约/生效登记。

先读：`docs/reviews/REVIEW_TASK_025_R2.md`、两份运行设计正文、`data/reviews/task025_r2_gpt_20261015_020841/runtime_baseline_corrected.json`（SHA `84cdd60347ffccd8afbeccdce1372c572a1da7ab1a4a1ac97571fa1f71504a84`）、冻结准备器/指南。DSH原十三键基样仅作历史，**不能照抄其schema或重跑旧构造器**。

保护基线：`data/reviews/task025_r2_gpt_20261015_020841/source_hashes_after.json`，SHA/项数/两个确切自指排除见同根 `review_result.json`。正式契约SHA `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`；开发宿主 `38869681…a307`，准备器 `ce23671f…0ac4`，旧Gate1适配器 `d8ace42f…34d9`，P1 `5ccdd0f3…4e79`，store `594e42d0…48e7`；完整冻结值以基线逐项实读为准。

## 3. 固定协议，不留实施任选

### 3.1 API与异常

build成功外层恰 `registry/registry_sha256/registry_file_sha256` 三键；read恰 `registry/registry_file_sha256` 两键；prepare恰 `request/request_sha256` 两键。对象指纹用冻结canonical口径；文件SHA取确切字节，两类不互替。

`RuntimeGate1Blocked(field, reason)` 用于类型/协议/来源/路径/既有目标/不一致；`RuntimeGate1Error(stage, reason)` 用于I/O或运行故障，保留cause/context。冻结准备器的拒绝须保留其定位/原因，不变成成功请求；不靠广泛捕获AttributeError/TypeError掩盖缺少预检。无CLI，不自造退出码协议。

普通ID只要求协议规定的非空字符串并原文保留；允许前导零、换行、64hex外观，不strip/转数字/以目录名猜身份。SHA字段全串64位小写hex，bool不冒充整数。

### 3.2 registry和两份文件

registry恰设计的13键：`registry_version,batch_id,registered_at,scope_ref,batch_files,code_manifest,rules_manifest,config,input,contract,run_binding,run_binding_sha256,note`。版本 `TASK-025-runtime-registry-1.0`；note用设计常量。

- batch_id从已核验批次/冻结准备器materials取得；batch_files恰8项，使用`batch/`前缀的逻辑相对路径（与materials中的8项一致），逐项长度/文件SHA同缓冲取得。
- code_manifest恰`manifest_version/entries`，版本`TASK-025-code-manifest-1.0`；冻结CODE_FILES十三项加本脚本自身，恰14项。每项恰`relative/file_sha256`，项目相对路径无`project/`前缀，按relative UTF-8升序且唯一。所有冻结代码逐文件与验收基线比较；新脚本自身取操作起始真实字节并收尾复测，不能硬编码自身SHA造成自指。
- rules_manifest恰`version/entries`；版本`TASK-006-rule-core-1.1`，四规则的版本/路径按冻结规则。每项恰`rule_id/rule_version/relative/file_sha256`，项目路径无`project/`前缀，唯一升序。
- config恰`file_sha256/config_ref`，固定实读`config/human_flow_v1.json`，不建新配置。input恰`file_sha256/byte_size/input_ref`，input_ref固定`batch/source/input.xlsx`。contract恰冻结三键，V1文件/生效登记均独立核验；不规范化人类已确认的生效时间。
- run_binding六字段按设计正文唯一算法构造；code.file_sha256为本脚本，code/rules对象摘要分别取其完整清单正文。run_binding_sha256仅取内层对象。登记对象不含自身指纹；registry_sha256=指纹(完整registry)。
- registered_at由程序登记时钟取带时区时间；这是技术动作时间，不是人类决定时间。重复prepare对同一登记确定；两个新登记的当前时间可不同，不宣称跨登记字节确定。

`runtime_registry.json`为registry本体，canonical UTF-8无BOM加单LF；`runtime_registry_readback.json`恰五键：`readback_version,registry_sha256,registry_file_sha256,registry_byte_size,run_binding_sha256`。readback_version固定`TASK-026-runtime-registry-readback-1.0`；长度为严格非负整数，其余摘要与本次writer读回/对象复算一致。readback不含自己的哈希。两文件都独占写并读回，不覆盖/不自动重试。

read只核验存储登记、readback的封闭结构/字节/内部关系及本次运行代码/静态绑定；**其签名没有batch_dir，不能宣称已核验当前批次**。当前来源核验由build和prepare完成，prepare不得把read的成功视为来源未变证明。

### 3.3 六键请求

request恰`request_version,status,materials,expectations,evidence,boundaries`。版本 `TASK-025-human-gate1-runtime-request-1.0`；status `RUNTIME_GATE1_REQUEST_PREPARED`。返回包装两键，调用方先取`result["request"]`。

materials为冻结P1七键，expectations为八键，expected_prior_gate1=null，expected_request_id原样绑定request_id。材料32项=冻结准备器31项+本脚本；不能加入旧Gate1适配器替代本脚本，不能修改原31项文件。项目材料relative用`project/`前缀，与code/rules清单通过固定前缀映射。expected_files从本次独立实读构造，双向完整相等；材料正文删除且仅删除顶层materials_fingerprint后复算。

evidence恰冻结七键：五项来源说明取真实准备器返回；code_manifest/rules_manifest使用本次registry完整对象，canonical严格相等，**不残留旧adapter/旧摘要**。boundaries恰冻结七键且全部严格false。批次/run_binding/contract/files/quality不重复放请求顶层，夹具标记不放生产对象。

质量由真实冻结准备器映射：OK和自洽BLOCKED均可形成候审请求；保留结构/质量阻断列表，BLOCKED不伪装为OK。FAILED、来源无法核验或材料不完整不能产生成功请求。这个API不接受decision或人类字段，不生成submission，不赋予APPROVE或动作许可。

## 4. 路径、调用与最终确认

runtime_dir为`data/runtime/`严格后代中的显式技术路径，build只接受从未存在的新叶（空目录也拒绝），独占建叶；其上本轮技术父目录可以创建。batch_dir是冻结接收器认可的新接收批次，源与runtime不得相等或互为祖先。

scope_dir须为`data/human_gate_decision_records/gate1/`的严格后代项目路径，非根/越界/来源或runtime重叠；本卡只登记规范项目相对引用，不创建scope/记录、不枚举并声称全局历史完整。已存在的scope拒绝，避免把旧历史绑定到新的运行版本。read/prepare校验scope路径约束，仍不写它。

对原始绝对路径逐级检查link/junction/reparse后resolve复查，覆盖允许根、源固定子目录/文件、项目材料和运行文件；拒绝未知文件/失败现场。不要先resolve把alias抹掉。枚举有界，仅固定集合；测试不得对越界路径递归全树快照。

build/prepare各真实调用冻结`prepare_human_gate1_request`一次，用其返回核验来源；build使用固定技术request_id `TASK-026-REGISTRATION-SOURCE-CHECK`，只作来源核验，不能生成人类请求/决定。准备器之外不调用P1公开入口、store或任何下游核心。只复用其来源核验结果，新层自身14项/32项和当前运行绑定由本层断言。

build先完成路径与来源/静态身份核验、同缓冲读数、registry对象与待写缓冲，再独占写两文件并读回。prepare先实读登记和当前31项来源，逐项与registry绑定/冻结基线比较，再新增自身材料和独立预期。代码/规则/配置/输入/批次任何字节变化均阻断，不更新旧登记迎合新值。

所有对象消费/摘要复算/来源核验/返回对象构造在最终确认前完成。最后有界实读全部消费文件与初始同缓冲/本次writer已绑定读数比较，核对集合、路径和failure；不刷新预期。此后直接返回，不再读取候选决定成功。可接受普通本地变更检测的能力边界，不建设同权限攻击防御框架。

build创建新叶后失败才在本次新叶独占写`failure.json`，五键`failure_version/stage/field/reason/cause_chain`，版本`TASK-026-runtime-registry-failure-1.0`；链保留主要原因，诊断自身失败也传播并保留两层错误，不覆盖/不删除坏文件。创建前拒绝不留输出。read/prepare全程只读，发现failure即拒绝，不写诊断。成功叶恰两文件。

## 5. 最小验收，先局部后收尾

使用全新容器，先一份C06b正常原始工作簿经冻结接收器真实接收；再一份可被真实准备器映射BLOCKED的已验收原始夹具。可以复制原始xlsx，不复用旧批次封套、旧登记、旧批准。接收器/其内部checker启动与直接CLI分别登记。

1. 正常build/read/prepare：三API外层键、13键登记、14/4清单、8批次/32材料、6/7/8/7请求形状、完整真实返回与落盘严格canonical/字节关系准确；scope/决定记录未创建，所有权限false。准备相同请求两次结果规范相同、源与目录不变；普通ID含换行/前导零/64hex仍原样。
2. BLOCKED来源：保留真实阻断分类和原文，能候审；FAILED/协议坏来源拒绝。未知/缺字段、bool/整数混淆、SHA尾LF、错绑定各选最小隔离例，不穷举已经冻结P1的大矩阵。
3. 路径/持久化：已有新叶含空目录、越界/根、源重叠、reparse拒绝且旧字节不变；若环境可建立真实junction至少一例，不能建立则记录实际原因，勿冒充真实路径执行。独占writer保留真实实现，仅在其真实句柄注入一次半写OSError；诊断/原因链/残留正确，恢复拒绝。
4. 晚变更：最后必要读取返回后分别改变一项来源字节及一项新登记输出字节，本次API立即拒绝并指向目标；verify类路径只读。观察实际接缝后注入，不猜第N次调用、不替换整writer冒充分支。无注入对照通过。
5. 范围/证据：实际观察冻结prepare调用与完整返回，P1/store/下游入口守卫命中0；计数分列，未观察子进程内部次数null+原因。API结果/异常/cause/关键前后源字节有小型完整记录；按call_id核对实际调用与登记，不编写新泛化审核框架。summary/checks/failures/台账落盘后真实读回审核，最终失败必须支配公开测试入口的非零和FAIL；一个同次观察的隔离副本删登记或改载荷须检出，无需为审核反例再建业务链。

完成上述必要验证即收尾，不重跑TASK-002—024历史入口或加无关案例数。测试独立canonical/字段/文件SHA与实际输出比较，不调用被测helper计算期望；小型记录足以复验，不重复保存每次整个项目树。

## 6. 交付纪律

实施前建卡/登记起点。全部代码/指南/回执与定点验证完成后，一次最终全树保护：changed=[]、missing/读取错误/范围外变化/新增0；新增按四文件和本轮确切根逐项登记，无目录前缀兜底。旧R5越界326项逐项不变，不追认、不删改；旧harness不列恢复例外。

回执分清真实调用、替身注入、读取旧证据和未执行项；列最终SHA、计数、失败现场与完整路径。最终扫描后仅有限登记自指元数据/最终身份，别为旧文案补偿重跑。不得静默改冻结文件；发现分类错误立即停止受影响处理并升级。

**本卡必要工作全部完成后再交终审**，不要把已授权的扫描/回执留作要求人类重复催促的下一轮。没有真实阻断时持续完成；确有阻断则报告具体文件/原因及已完成证据。执行端完成后停止实施，不制定TASK-027，不把候审登记当批准；验收后GPT按持续授权制定下一卡，真实决定与看板done由人类作出。
