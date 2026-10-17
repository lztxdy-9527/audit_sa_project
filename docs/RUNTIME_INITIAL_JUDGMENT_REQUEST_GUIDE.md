# 新运行 profile 与只读初判请求（TASK-038）

本卡仅准备请求，不保存初判或开放 AI。真实批准null、真实初判未保存、开发宿主0008、next/AI=false。Gate/初判的测试人类字段仅用已登记合成夹具。

## 实施前固定的绑定与检查顺序

新 registry 恰14键，新增 initial_judgment_history 恰 namespace_relative/declared_scope。调用 build 时是必填关键字；相对 POSIX 路径和 UTF-8 scope 先验检查，原路径链先于resolve；域必须既存，记录根严格后代且不与runtime/Gate/SQLite交叠。本层不创建域、不在登记中保存会增长的名单。

新代码17项（旧13 + 已接受初判core/store/history + 适配器自身），新 CODE_MANIFEST_VERSION/REGISTRY_VERSION/RUNTIME_VERSION_028 分别为 TASK-038-code-manifest-1.0 / TASK-038-runtime-registry-1.0 / TASK-038-runtime-gate1-1.0。旧版本先明确拒绝，不迁移旧凭证。三新件、初判协议/案例均实读并与独立冻结 SHA 核对；自身 SHA 来自开始缓冲。

Gate1 材料38项：旧32 + 三新代码 + 初判协议/案例 + 本运行登记原文件。project项保留 project/ 前缀；登记项恰 runtime/runtime_registry.json，取已捕获确切原字节长度/FILE。prepare 与 verify 共用材料构造，不重新序列化 registry 对象假冒 FILE。换域即使同步合法readback，也不能保留原Gate1凭证。

新入口字段/调用次序固定如下，不以候选插入序首报：

1. request_id 类型/UTF-8，history_expectations 四键schema及其路径/scope与登记绑定；当前batch/runtime/scope/Gate/数据库显式路径与failure/锁/固定集合先验检查。
2. 固定开始缓冲：批次八件、登记二件、事件各八件、load四件/DB、screen三件、crosscheck三件、facts四件、静态件/SQL/自身，以及绑定域成员和每叶六件。不调用算法建立读数，不刷新预期。
3. 直接真实调用 Gate1 verify（完整十一键/effective严格true/APPROVE/HUMAN_DECLARED/reasons空）→ Gate2 verify（完整三键及APPROVE完整record）→ facts inspect（完整六键及真实artifacts）→ frozen history（完整十二键）。每次返回先与相应开始完整对象/FILE/FP闭合；错误实际类型映射、history Blocked 加 history. 前缀保留reason/cause，Error保留stage/reason/cause。
4. 历史正常返回后检查本批是否已有记录；有则在 prior_history.records 拒绝首版准备。未收到人类event，不凭空做提交去重。
5. 先从已核验独立来源固定12键expectations、三键prior_history和八角色文件；再组装10键materials，M为删除materials_fingerprint后的9键 FP。全材料与固定独立预期严格canonical相等，FILE/FP分列，False/0不等。六键request、七键evidence及十false边界精确封闭，不生成submission模板。
6. 深拷贝构造两键返回后，末次确认全部原始字节/路径/固定集合/failure/锁/历史成员与六文件/自身和17代码及2协议。之后直接return，不再解析候选、刷新history或写诊断。

## 实施前正常调用图预期

直接四个调用各1：verify_gate1_effective_approval、verify_runtime_gate2_decision、inspect_gate2_fact_packet、frozen history。

保留现有事实核验内部调用图：facts inspect → crosscheck inputs（screen inputs+screen inspect）及 crosscheck inspect（同一结构）；因此正常新入口 Gate2 verify 总5（直接1+facts内4），Gate1 verify总6（直接1+5次Gate2内部），load inspect5、screen inspect2、crosscheck inspect1、facts inspect1、facts render1。冻结 Gate store.verify/P1各11（Gate1六+Gate2五），冻结准备器6。历史含n个合法叶时 history1/store.verify n/初判核心n；空域n=0。本入口直接初判核心、任一save、normalize/load/SQL/crosscheck/facts build增量0。实际测试用原代码对象及父关系逐层确认；若调用图不符先定位原因，不以总量猜测。

## 返回与独立性

外层恰 request/request_sha256，后者FP(完整request)。request恰 request_version/status/materials/expectations/evidence/boundaries，版本 TASK-038-human-initial-judgment-request-1.0，状态 RUNTIME_HUMAN_INITIAL_JUDGMENT_REQUEST_PREPARED。materials/expectations沿冻结TASK-034十键/十二键；fact packet为开始JSON缓冲解析对象、原findings顺序、现有entity/模板/整数分不改。

evidence保留四个本次真实完整核验返回、五键registry_binding、三键contract_effective_record及八角色files独立副本。Gate record来自开始decision_result两键对象，record FP和该文件确切FILE分开；Gate2前序闭合到Gate1 FP。历史完整返回中的旧人类字段仅作为既有快照证据，不预填当前判断。

独立预期先于candidate固定，来源为本次开始缓冲及实际核验返回，不能由candidate/submission反推。声明域完整性仅现存成员和已声明引用闭合，不证明无引用历史从未删失/全时间完整/身份/来源真实。

## 复验和停止

测试入口：`.venv\Scripts\python.exe -B tests\test_runtime_initial_judgment_request.py --out-dir data\runtime_initial_judgment_request_tests\task038_<新名>`。仅一条新profile正常前提链，所有其余反例复用本轮场景/明确接缝，setup与生产窗口分列；不修改旧源或旧快照。生产只读/时钟/网络/子进程守卫，四个实际main replay 0/1/1/1且新增业务0。物理junction仍null+权限限制。交付后停止待Architect独立验收，不推进初判保存/下一卡，看板由人类办理。

本轮先发现 history 异常映射遗漏 reasons；在获得人类“允许小修并另建最终链，当前现场保留”后，仅补齐该属性深拷贝，保留原 field/stage/reason/cause/secondary_errors。task038_run_01 作为开发现场保留；task038_run_02 是修改后唯一最终运行身份，后续不修改生产代码。

run_02 的测试局部变量 capture 遮蔽缓冲采集函数，导致前半组已执行、在非空历史组前发生测试 TypeError。未重建链、未重写该现场。测试提供具名接续 `--resume-prefix data/runtime_initial_judgment_request_tests/task038_run_02`，在新 out-dir 中读取该段完整 API/嵌套观察，进行新的只读复核，并调用与常规入口同一个剩余历史组和同一个证据收尾 helper。它不恢复未保存的旧 checks、不把先前观察算成本进程新调用；summary 的 prior_segment/new_process_code_entries 分列来源，aggregate 只用于完整载荷登记闭合。默认完整入口同样使用这段已修正的共享历史组。

换域控制是在 Gate1 保存前，先让仅改域及相应 readback 的副本通过真实公开 read；保存 Gate1 后，使用实际 reader 返回副本读数的隔离接缝，证明原 Gate1 文件绑定拒绝该域。代码晚变更用本轮物理源码副本的实读缓冲替换 reader 视图，原冻结源码未改；合成 reparse 元数据仅证明检查分支，不声称建立物理 junction。真实返回的受控映射与真实磁盘晚变更分列。

既有 event 2 六快照只读复制到新声明域。其旧命名域曾用于重复批次反例，不宣称该旧域整体有效；本轮新域实际逐叶 store.verify/core 成功后才提取历史。随后测试 setup 使用登记 event 1 保存本轮合成同批快照一次，后续 FP 矛盾/缺引用/failure 现场全部保留，不能解释为真实独立初判已经保存。初判请求的运行层保存接口仍不在本卡范围。
