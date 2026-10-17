# 声明命名域的初判历史只读核验

TASK-037，scope=`DECLARED_NAMESPACE_CURRENT_SNAPSHOTS_ONLY`。唯一入口为 `inspect_human_initial_judgment_history(namespace_dir, *, expectations)`，无生产 CLI。调用方须在调用前独立固定域路径、声明 scope 和完整叶名单/manifest 文件 SHA，不从本函数的候选刷新预期。

## 实施前定稿的字段与检查顺序

以下顺序按 schema、叶 UTF-8 原序及旧引用原序执行，不随字典插入顺序改变。

1. `expectations` 必须为严格对象；按 expectations_version、expected_namespace_relative、expected_declared_scope、expected_entries 顺序查缺键，然后按 UTF-8 顺序拒绝未知键。版本固定 `TASK-037-human-initial-judgment-history-expectations-1.0`。相对路径/声明为合法 UTF-8 原串；项目相对 POSIX 路径不含空段、`.`、`..`、反斜杠、冒号或 NUL。名单为严格 list；各条恰 relative、manifest_file_sha256，relative 为安全单段、SHA 恰64位小写hex，名单唯一且 UTF-8 严格升序。
2. 真实实读冻结 store 源并核对 SHA；加载该缓冲，核对其六组件及新 history 自身开始字节。此时不调用业务 API/核心。空域同样核验组件。
3. namespace 原路径链（包括 alias/..）先检查，再解析严格记录根后代/既存正常目录。与 expected_namespace_relative 精确相等。枚举直接成员，先核对成员类型，再双向完整核对独立名单；根文件/子树/多缺成员不忽略。
4. 按叶名单逐项先查 failure（有效、坏型均拒绝，不先读 manifest），再固定六文件布局和同缓冲原字节/解析对象。manifest FILE 对固定预期不符先拒绝。调用 frozen store verify 恰一次，保留其 field/reason/cause 或 Error stage；成功返回先核验完整十一键和同缓冲六文件/四快照/两键完整结果、组件、manifest 关系。
5. 成功叶完整 record 提取四字段。按 event_id、batch_id、record_fingerprint、binding_fingerprint 顺序校验原字符串/指纹；重复 event 优先于同 batch 冲突，定位第二叶。随后核对 prior_history 与 record.history_binding 两处 scope。所有成功候选叶后，索引按 event_id UTF-8 顺序排列。
6. 按叶/原引用顺序将每个 prior_history.records 四字段与完整实际索引规范比较，先找 event_id，再按 batch_id、record_fingerprint、binding_fingerprint 定位矛盾。缺失引用不自动补齐，不按人类或技术时间推断先后。
7. 深拷贝构造完整十二键返回；检查输入 expectations 未改。此后只作末次组件/原路径/集合/各叶六文件字节确认，比较本次开始读数，不重采预期；确认后直接返回，不再解析候选或写盘。

冻结 store Blocked 的 field 加 `entries[i].` 前缀，reason 原文保留并 `raise from`。其 Error 保留原 stage/reason/cause，叶路径由调用参数与测试父调用记录定位，不改原 reason；secondary 信息若有也保留。自有 I/O Error 使用准确阶段（load_store、components、namespace、entries[i]、final_confirmation），协议拒绝不统转 Error。所有异常 reasons=[reason]；未捕获的真实内部错误为 Error 并保留 cause。

## 输入输出与边界

成功恰十二键：history_version、status、scope、namespace_relative、prior_history、prior_history_fingerprint、inventory、inventory_fingerprint、component_bindings、verified_snapshots、boundaries、note。history_version=`TASK-037-human-initial-judgment-history-1.0`；status=`HUMAN_INITIAL_JUDGMENT_NAMESPACE_INSPECTED`。

prior_history 恰 declared_complete/declared_scope/records；索引每条恰 event_id/batch_id/record_fingerprint/binding_fingerprint。inventory 恰 namespace_relative/declared_scope/entries；entries 为实际 manifest 同缓冲文件 SHA 两字段名单。FP 为既定 canonical JSON UTF-8（ensure_ascii=False、sort_keys=True、separators=(",",":")、allow_nan=False）的 SHA，不含自身摘要；文件 SHA 按确切文件字节，不与对象 FP 互替。

verified_snapshots 按叶顺序，每条恰 relative/verification，保存该次真实 store 十一键返回的独立深拷贝。component_bindings 为 store 六项加 history_file_sha256，自身 SHA 来自开始实读。九项 boundaries 全严格 false：workflow_connected、execution_allowed、next_step_allowed、ai_enabled、identity_authenticated、source_authenticity_proven、audit_conclusion_formed、final_judgment_recorded、global_history_completeness_proven。

note 固定为：`仅核验本次声明命名域的现存成功快照及已声明历史引用；不证明历史从未删失，不批准执行，不认证身份，不开放AI或终判。`

declared_complete=true 仅表示当前指定域的实际成员、独立名单、逐份完整快照和已声明引用闭合且末次确认未变；不证明域外/未登记/无引用历史从未删失，不认证身份/来源，不证明旧提交当时已完整枚举。

## 冻结复用与验证入口

store 源 SHA 固定 `a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c`；不修改它。直接有限复用其 `_equal/_resolve_leaf/_reject_chain/_normal_file/_read_bytes/_parse/_layout/_capture_components/_confirm_components/_validate_manifest/_validate_result`，只调用公开 verify，不调用 save 或直接核心。源码原缓冲加载，不缓存跨调用绑定。六组件核对包含 core/协议/案例/契约/生效登记，不接运行代码清单。

测试命令：`.venv\Scripts\python.exe -B tests\test_inspect_demo_human_initial_judgment_history.py --out-dir data\human_initial_judgment_history_tests\task037_<新名>`。所有测试输出和合成记录根须从未存在。setup store.save 只用于本轮新场景，计数与被测 history/store.verify/core 分层；生产窗口严格只读、禁当前时钟/网络/子进程。元数据 reparse 控制与物理 junction 分列，后者未获权限时 null，不重试绕过。

fixture 仅已登记 event1/2 及继承五个人类字段，标签放协议外；技术 batch/request/材料/历史关系在测试构造期固定，不冒称真实 Gate 核验。不迁移或重写旧快照，不清理失败现场。本组件和技术验收不批准真实批次，真实批准 null、真实初判未保存、开发宿主0008、next/AI=false。
