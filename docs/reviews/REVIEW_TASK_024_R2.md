# TASK-024-R2 终审及 harness 处置：NOT_ACCEPTED

日期：2026-10-14。Architect / Reviewer：GPT。依据实际文件及原 TASK-024/R1/R2 任务卡。**仍有 B1/B3/E2 残余阻断，另须完成旧 harness 的精确恢复。** 不制定 TASK-025；三张原卡保持 in_review，看板由人类操作。

## 1. 交接身份与复验范围

实际交付身份与交接一致：适配器 `1fb60e603f6bae1d4f54df296199f363b728dd3f5f7b34b67680c4b5c281dbde`（79832）、测试 `14f5e23828a93fcef13480311bd9454c544c0321c29084a2e28371d61afa0cde`（131776）、新回执 `6373059c974a9f32aca50fcf01acfe998f4c0d4a4c279fd3a7eb989b27369706`（13213）；指南未改。

证据根 `data/reviews/task024_r2_gpt_20261014_164601/`：`finite_audit.json`/`reviewed_inputs/` 核对并保存 14 项输入身份；冻结 prepare/store/P1/正式契约及生效登记/配置/宿主/控制器未变。GPT 没有修改实现、测试、旧源或旧证据。

读取了执行端 `task024r2_run_02` 的 78 项/写后审核、核心条目，以及四个故障容器与修改过的 harness；**没有把这些既有结果称 GPT 重新运行**。发现必要反例后，没有再跑完整本卡入口或任何历史大套件。

GPT 实际运行：2 个新正常 receiver CLI（均 0、完整原文留证）；22 条有名称的公开 API 定点操作（含组装 prepare）；1 次真实 P1 观察器辨识度控制。所有故意修改/恢复限本轮新批次与记录，旧证据只读。见 `receiver_invocations.json`、`probe_records.json`、`verification_summary.json`、`evidence_probe.json`。

## 2. 对旧 harness 的明确裁决

历史路径：`data/human_gate1_decision_tests/task024r1_fault_00/aux_fault_r1.py`。

- R2 前基线 SHA：`7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035`。
- 当前修改版 SHA：`c148abea44cdbcf8fef2156afed37ab1460355cad22e9a421661fef17e7a3b4d`，6386 字节。

**不追认该越界修改。** “临时/非交付物”不豁免已登记、已冻结的证据文件；declared_deviations 只表明上报，不构成授权，也不能据此把扫描结果称范围合规。发现时点未独立验证，本评审不声称“立即停止升级”已被证明。

处置是可执行的，不需要再请求人类作业务决定：**保全当前修改版，精确恢复该一个历史脚本，新故障 driver 放到下一轮新证据容器。** 仅授权在 TASK-024-R3 下完成这一次具名恢复，不开放其他旧文件。

GPT 已保全修改版至本证据根 `modified_aux_fault_r1.py`，并在新根重建出 **`recovered_aux_fault_r1_verified.py`**：4248 字节，SHA **`7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035`**，与 R2 前基线逐字节哈希一致。它只是恢复材料，未执行，也没有回写历史原件。

恢复过程如实保留：首个候选/空白与换行变体没有匹配；原“两种模式”的 else 分支、空白及 LF 还原后精确匹配；一次内联 shell 引号错误产生 SyntaxError，未触及原件。对应脚本与每轮结果均在新评审根，不能把不匹配的早期候选当恢复文件。

## 3. 新两类故障证据实际上被另一处错误覆盖

修改版 harness 的 `core_missing`/`object_sha` 分支先把目标切换到 core_observations.json 并写核心候选；分支结束后，无条件 `path.write_bytes(json.dumps(calls...))` 又把 API 调用列表写进同一文件。

实读两个现场：

- `task024r2_fault_03/core_observations.json` 最终 **116 条 API 记录**，与该容器 calls.json 规范相等。harness 中间声明 407→406，但最终不是 406 条核心条目；它因 `116 < 407` 这个宽判据自报“候选保留”。
- `task024r2_fault_04/core_observations.json` 同样是 **116 条 API 记录**，并非“只改一个输入 snapshot 字段”。

第一项实际诊断都是“核心登记 116 与声明 407 不一致/逐层条目 0”，而不是所声明的单条遗漏或 SHA/value 矛盾。**两份 1/FAIL 本身真实，但不能证明指定故障被独立检出。** 现场保留，不回填、不改旧回执；仅在新容器修正 driver 并定点重做两类故障。

旧 R1 `fault_01/02` 的原 harness 结果实读为 **7/7**，不是新回执笼统的“四轮各 8/8”；本轮未重跑它们。以上均见 `evidence_probe.json.fault_harness_actual_disk` 与 `finite_audit.json`。

## 4. B1：末次组件读取窗口已修，终端集合/路径义务仍不完整

先确认已关闭部分：GPT 实际观察 adapter 读取降至 2 次；在最后一次真实组件读取后分别改较早 context、当前源、failure、scope 空目录，**四项本次均 Blocked 且定位正确，恢复后成功**。不再次派发这四个已通过探针，也不要求增加确认循环。

残余位置：`_terminal_confirm` 794—817。它只枚举 scope 总集合，未核对每个事件/快照目录与当前接收批次的固定内部集合；来源/事件的终端字节读取也没有完整复查路径属性。

两个实际反例：包装真实 `_source_snapshot` 返回原缓冲后，只新增一项，不改任何已消费文件：

- 较早事件 `event_0001/unknown.json`；
- 当前接收批次 `checks/unknown.json`。

**两例本次 verify 都 VERIFIED**；撤销 wrapper 保留未知文件后分别因事件/批次布局被拒，删除本轮故意新增文件后成功。终端应确认各层集合/路径，这在原 R1/R2 卡已明确要求，不是新增全局发现或原子快照要求。

## 5. B3：schema 类型已有修复，scope 值与既有绑定仍不闭合

`source_scope=7`/description 数组等类型检查已补，不重复列为阻断。残余是 source_scope 的关系与实际日期合法性：`_is_iso_date` 只检查数字和连字符，evidence.scope 的币种等也未与既有声明/配置绑定核对。

在合法两事件中，各独立改变较早历史 scope 的一项，并同步 context/receipt/后继 prior_events 的必要哈希；六份快照、材料、期望和其 CNY 配置绑定不变：

- `source_scope.currency="USD"`；
- `source_scope.period_start="2026-09-00"`。

**两例公开 verify 都成功**。第一例与仍绑定的冻结 CNY 范围矛盾，第二例不是有效 ISO 日历日期。历史仍无需实读旧业务源，但已有内部来源声明不能与保存材料/独立配置范围相互矛盾。见 `historical_scope_*`。

## 6. E2：路径现场、第三时点、真实层计数仍有缺口

### 6.1 目录被记作不存在

`describe_input`/`object_fingerprint` 仅在 Path.is_file() 时读内容，目录一律得到 data=None/exists=false。实际成功的 store.verify 输入是存在的六文件 snapshots 目录，却被记为不存在。GPT 以本轮真实目录控制，给 submission.json 追加 LF，**目录指纹完全不变**。目录现场与文件现场需按真实参数角色分开，不能把目录当不存在。

### 6.2 “三时点”实际上仍只有 before/after

407 条正式观察都只有 `input_fingerprints_before/after`；实际消费引用在 observe_core 返回后未保留到所属 API 收尾。新独立快照修复了此前 alias 问题，但没有第三时点。

GPT 控制：真实 P1 一次正常返回，observe_core 已记录 before==after；在其返回后、逻辑父 API 收尾前，测试改变内存 submission.reason。真正收尾 SHA 已变，条目仍 `input_unchanged=true`，实际 evidence_audit 仍 `ok=true`。只说明观察器不能检测第三时点，不声称冻结 P1 或生产适配器会自行改输入。完整观察和实际前/收尾值见 `API_tail_control`。

### 6.3 store.save 的 +1 已定位为重复归类包装层

执行端核心真实 P1 105/105、冻结 prepare 91/91、store.verify 78/78 已闭合，保留这些已修复项。store.save 实际帧 27/条目 28 的差异并非仅“计数偏差”：其中 **core-store_save::83** 观察的是测试文件 `run_suite_main.<locals>.injecting_save`，其余 27 条才是冻结 `save_human_gate_decision_snapshots`。同一实际调用被外层测试 wrapper 与内层真实函数各记一次。

现有 closed 判据只把这些重叠窗口的 frame_delta 相加（28），没有强制与独立聚合入口 27 相等，仍 `closed=true`。应把测试注入包装单独归类或不纳入业务层，真实层完整条目与真实入口闭合；不能固定减 1 或把非零 cross_check_delta 仅登记后通过。

## 7. 保留修复与保护结论

原末次组件窗口、历史排序、既有类型检查、真实 writer 方法、输入/输出独立快照、完整返回与台账读回等修复保留。本轮没重跑完整 78 项、writer/loader 历史故障、旧 API 缺项/内容故障或 TASK-021/022/023 入口；不把引用读数混为新实测。

GPT一次最终全树扫描：基线149660项，实扫150998文件；**changed为适配器/测试两项以及旧R1 harness一项；旧harness仍明确列为越界，scope_compliant=false**。没有其他未申报变化，missing/读取错误/范围外新增均0。允许新增按确切执行端文件/明确根、本轮评审/两个新批次/新记录根和前轮两个自指元数据逐项登记，没有目录前缀兜底；旧现场/junction保留，旧harness未由GPT回写。扫描后仅有限登记评审/元数据，未再扫描。NOT_ACCEPTED修复基线完整SHA/项数/两个确切自指排除见同目录review_result.json；新卡单独授权具名恢复，不能把负基线中的修改状态当已接受。

结论：**NOT_ACCEPTED**。下一步仅 `docs/tasks/TASK-024-R3_DRAFT.md`：具名恢复旧 harness、新 driver 两类有效故障、B1 内部集合/路径、B3 内部关系/日期、E2 目录与 API 收尾/层归类。B 类 DSH 实施，不推进 Gate2 或 TASK-025。

真实批准 null、宿主开发态 0008、next=false、AI=false；没有真实初判/0009/执行放行，所有新记录是已登记合成测试夹具。
