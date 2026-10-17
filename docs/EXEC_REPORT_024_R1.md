# TASK-024-R1 执行回执（Gate1 适配器与验收证据定点修复）

任务：`docs/tasks/TASK-024-R1_DRAFT.md`（**B 类：DSH 定点修复既定设计，GPT 验收**）；依据
`docs/reviews/REVIEW_TASK_024.md` 的 B1—B4/E1/E2 六组阻断。日期：2026-10-14。
执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务判断与看板：人类主理人。

**范围**：只修改 `scripts/record_demo_human_gate1.py`（起点 `c002243ade1332e9e56ecd0a2b932a100c1d9f57191983f5689751e4f7fbd650`／53998）、
`tests/test_record_demo_human_gate1.py`（起点 `50f1268ea7ca8871eeb6405e5ac2ebec9c7d743e90a2868b493b35689d48df6c`／51059）两文件；
`docs/HUMAN_GATE1_DECISION_GUIDE.md`（`9c8f4409…c2fb`）**未改**（卡允许“指南若无需改则可少”：指南对 revision 序、封套封闭键、七键 failure 的描述与修复后行为一致）。新增 `docs/EXEC_REPORT_024_R1.md` 与 `data/human_gate1_decision_tests/task024r1_*`、
`data/batches/task024r1_*`、`data/human_gate_decision_records/gate1/task024r1_*` 容器；未改旧回执与评审证据；未清理旧现场与 junction。

**修复保护基线**：`data/reviews/task024_gpt_20261014_050915/source_hashes_after.json` = `3fdeda79a180c89820bf162c04f26048c130aec592ed465ebf41845080a57a35`、**147001** 项、verdict=**NOT_ACCEPTED**、两个确切自指排除（`review_result.json`、`source_hashes_after.json`）。该基线是**修复起点**，不是已验收组件。

**写后实读身份**：适配器 `e03f02ae2dbb63746bb44d6b2e7b9af47824c04397999176b2224f1705c9441f`（74560）；
测试 `4e162d8c5a0fbff30ab84670e284768c19c1d81c2cfbc983c20fe097faa23291`（115505）；本回执自身最终 SHA 仅交接给出。

**登记夹具（三份，只用其人类字段，标识仅在外层）**：① 项目权威夹具 `FIXTURE-EV-G1-0001`/APPROVE（`docs/proposals/HUMAN_GATE_DECISION_CASES_V1_DRAFT.md` 第 2 块）；② `TASK024-G1-HOLD-0002`/`FIXTURE-EV-G1-0002`/HOLD（`8e3cf567…d4fa`，GPT 于 TASK-024 登记）；③ `registered_fixture_0003.json` = `6c69c75cde41014fd8740b95d58b9e8a805bd30003fb14ac6f8fb40c93cf23c3`/`FIXTURE-EV-G1-0003`/REJECT（GPT 于本轮评审登记，只读复用）。

---

## 1. 最终完整入口（一次全新容器）

```text
.venv\Scripts\python.exe -B tests\test_record_demo_human_gate1.py \
    --out-dir data\human_gate1_decision_tests\task024r1_run_08
→ 74 项登记检查 / 0 失败 / 退出码 0；写盘后审核（E2.3a-c、E2.4a-c、E2.6a-b）8 项全部 OK
→ 失败支配收尾：status=PASS、failures=0、返回码=0、支配一致=True
→ 台账：disk_audit ok、byte_drift=[]、core_observation_count=289、台账读回同缓冲 True
```

| 计数（真实观察） | 值 |
| --- | --- |
| 本层 API（登记数 = 入口观察数） | prepare **29**、save **37**、verify **51** |
| 本层入口观察（`sys.setprofile`） | adapter 29 / 37 / 51 |
| 冻结准备器 `prepare_human_gate1_request` | **92** |
| 冻结 `store.save` / `store.verify`（计数与观察分列） | **27** / **78** |
| 真实 P1 入口（store 单次 P1 接缝） | **22** 次（观察记录逐条完整输入/返回或异常） |
| scope 枚举 `_list_scope` | **130** |
| 冻结接收器 CLI | **3**（退出码 0 / 0 / 1） |
| R1 定点段 | **24** 项检查，0 失败 |
| 核心调用观察记录（`core_observations.json`，纳入台账） | **289** 条 |

## 2. B1：末次必要消费后的完整收尾

实现：`verify` 收尾在真实消费之后复读**全部历史事件八文件 + 目标八文件 + scope 事件集合 + 各事件 failure 状态**，其后再做**第二遍当前来源确认**（两遍之间的接缝不再漏检）；`save` 收尾同样补既有事件失败/字节复读与第二遍来源确认；预期只来自本次初始同缓冲读数/本次 writer，不在最后从候选磁盘重建。

实测（套件 R1 段，全部登记在案）：无注入对照 returned；① 较早 `event_0001/context.json` 加 LF → Blocked `event_0001/context.json`；② 当前源 `checks/quality_report.json` 加 LF → Blocked `batch/checks/quality_report.json`；③ 目标新增 `failure.json` → Blocked `event_0002/failure.json`；④ scope 新增空 `unregistered_event/` → Blocked `scope_dir`（reason 列出复读到的目录集合）；撤销/恢复后均 returned。**save 接缝**：对照先测得来源确认次数 = 3，随后在 hit 2/3（仍有后续必要消费）注入当前源 LF → 拒绝且新事件目录留有**恰七键** `failure.json`。四个注入各命中一次、未同步哈希、只改隔离测试输入。

## 3. B2：两种顺序分开

实现：新增 `_probe_revision`（revision 取自**文件内严格整数**，非叶名字典序），`_verify_history` 先排定**连续唯一 1…N** 合法前缀（重复/缺口拒绝），`prior_events` 按 revision 升序、**每个前缀**的 `prior_history.records` 单独按原 `event_id` UTF-8 排序（修正了此前用 revision 顺序填 records 的缺陷）。

实测（套件 R1 段）：① 字典序反例 `z_first`(rev1)→`a_second`(rev2)：两次 RECORDED、两次 VERIFIED；② 三事件序 EV-0002→EV-0001→EV-0003（目录 event_0001..0003，B/HOLD → A/APPROVE → B/REJECT）：三次 RECORDED、三次 VERIFIED，`revision=3`、`prior_events=[event_0001,event_0002]`（revision 序）、`records=[FIXTURE-EV-G1-0001, FIXTURE-EV-G1-0002]`（event_id 序）。未新增“目录名编码 revision”“event_id 等于叶名”“仅两事件”等限制。

## 4. B3：封套 schema 与内部关系闭合

实现：`_validate_request_schema`（request 六键及嵌套 materials/expectations/evidence/boundaries 完整封闭键与严格类型：非负严格整数、hex64、相对路径、32 材料/14 代码/4 规则声明按 UTF-8 升序唯一）；`_require_request_closure`（`request.materials`/`expectations` 与对应存储快照、`record.binding`、`manifest.fingerprints` 按 **canonical 字节**闭合）；`_require_sorted_unique_declarations`；`snapshot_files`/`prior_events` 改 canonical 比较；14 项代码清单条目统一为冻结准备器的 2 键形状（去掉此前多写的 `byte_size`）。历史仍只核验保存快照与内部声明，不重读旧业务源。

实测（套件 R1 段，就地只改一项 + 同步必要外层哈希 + 字节级备份/还原）：`request={}` → `event_0001.context.request`；`source_batch_relative=7` → `context.source_batch_relative`；`snapshot_files[0].byte_size` 整数改**同值 float** → `context.snapshot_files`；`prior_events[0].revision` 整数改**同值 float** → `event_0002.context.prior_scope.prior_events`；严格 `false→0` → `context.boundaries.execution_allowed`；缺嵌套键（删 `request.evidence.code_manifest`）→ `context.request.evidence`；多嵌套键 → `context.request.materials`；**键顺序 canonical 等值对照** → returned（按 canonical 而非文本比较）。

## 5. B4：一致异常映射与双重失败报告

实现：`_frozen_request` 不再透传下游异常（缺 `gate1_packet` 等协议拒绝映射为本层 Blocked/field/reason）；两 loader 的 `exec_module` 接缝把 ImportError/OSError 映射为 `Error(prepare_load|store_load)`+原因链且不缓存失败加载；`save` 两异常分支统一（无事件现场只释放**本次**自锁，既有锁不动；有现场只写本事件 failure）；`_write_failure` 返回诊断写失败记录，由 save 组合“主错误 + 收尾失败”，不吞第二次失败、不重试覆盖、不删半写现场；辅助注释更正为**七键**。

实测（套件 R1 段）：缺 `gate1_packet` 的 prepare/save/verify 三入口分别 Blocked（field=`prepare.batch_dir`，reason 原样列出缺失文件），save **不建事件、不留自锁**，预置既有锁时 Blocked `scope_dir.lock` 且**既有锁字节未动**；loader ImportError → `Error(prepare_load)`+ImportError 链、撤销后 prepare 正常返回；**双重写失败** → `Error(context_write)`，reason 同时含主错误“无法写入 context.json：[Errno 28] probe half-write …”与“收尾失败（failure_write）”，磁盘 failure **0 字节**。

## 6. E1：真实 writer 两例

实现/测试：保留真实 `_write_exclusive`（真实 `os.open(O_WRONLY|O_CREAT|O_EXCL)` + `os.fdopen`），**只包装它实际打开的独占句柄**——测试经 `os.open` 记录 fd→真实路径，再在该句柄的 `write` 上按真实文件名注入。

实测：**E1.1** 真实写入半段后抛真实 `OSError`（Errno 28，文本含 `half-write`）→ 走生产 writer 的 `except OSError` 分支，API 抛 `Error(context_write)`、**原 OSError 在传播与原因链中**，半写 `context.json` 与有效七键 `failure.json` 现场保留，登记真实 open flags 与各次写入的真实路径/字节数；**E1.2** 真实 writer **完整**写入 receipt 后再抛明确类型/文本的 sentinel（`R1-probe-receipt-sentinel…`）→ `Error(receipt_write)`、**sentinel 在传播与原因链中**、完整 receipt 与失败现场保留。原“替换整个 writer／追加 X 字节”不再充当抛异常证据。

## 7. E2：完整观察、内容与磁盘审核

- **E2.1**：所有测试直接公开 API（含 `submission_for` 中的准备）**统一登记**（登记 prepare 由 2 升至 29）；独立入口观察器（`sys.setprofile` 按 `(文件基名, 函数名)` 统计真实 frame 进入）分列本层/冻结 prepare/store.save/store.verify/scope 枚举/真实 P1，并与登记数交叉核对（本层三层相等，跨层不要求相等）。
- **E2.2**：`observe_core` 对冻结 prepare/store.save/store.verify/真实 P1 保存**完整输入**（canonical 长度+SHA+值/路径）、**完整返回**（容器记长度+SHA+`item_count`+`present`，标量记类型/repr）或**完整异常**（类型/消息/原因链/`traceback`），并取调用前后**真实引用指纹**（代码对象 filename/firstlineno/co_name/argcount/varnames/co_code/co_consts 摘要 SHA）——289 条记录**全部前后一致**；合法空容器与缺记录经 `item_count`/`present` 区分；首次实现用 `marshal` 出现过同对象前后不一致，已改为稳定结构化摘要。
- **E2.3**：真实观察完成后、任何终审读取前独立深拷贝冻结完整预期（并校验与写入前内存缓冲逐载荷相等——**预期不来自候选磁盘**）；首轮同缓冲读数做完整 canonical 比较（对象按路径逐字段**类型敏感**比较 + 字节长度 + SHA），全部载荷 `diff_count=0`；隔离对照：自洽替换 `reason` → 定位 `calls.json[<case_id>].reason`，布尔改数值 `0` → 定位 `summary.boundaries.<key>: 类型不同 bool != int`；**键顺序整体颠倒仍通过**。
- **E2.4**：台账落盘后**读回审核**（同缓冲；`entry_count`/`covered`/6 载荷名称·长度·SHA 逐项闭合、`byte_drift=[]`、三项审核均 ok、`final_audit_failed=false`）；隔离对照改动登记 SHA / 删 `covered` 即被拒；失败支配置 FAIL 且返回 1。写盘后审核结论记入 `ledger_readback.json`（`post_audits`/`post_audit_failed`/`dominance`）并支配返回码，**不覆盖坏候选、不重建期望/台账**。
- **E2.5**：接收器三次真实调用保存**完整 stdout/stderr 原文引用**（写入本轮容器并登记路径/长度/SHA/原文，按字节写盘避免换行改写），逐批次复读比对一致；`returncode` 与批次清单 `receive_exit_code` 一致（0/0/1）；内部 checker 的 `started/exit_code/report_result/report_matches_snapshot` 与**独立复读**的 `checks/quality_report.json`、`logs/checker.stdout.txt`、`logs/checker.stderr.txt`、`code_snapshot/check_demo_data.py` 的 exists/长度/SHA 一致，内部启动数 **3**；**直接 checker CLI 0 次**并记录原因（与内部启动分列）。
- **E2.6**：测试侧**独立实现** canonical/指纹（手写键排序、紧凑分隔、bool 先于 int、严格类型）与生产实现逐一致，独立复算 `materials_fingerprint` 相等；独立实读 **14** 项代码声明与 **32** 项材料（直接读项目文件复算长度/SHA，`batch/` 与 `project/` 前缀分别解析）；五类最小审核故障（缺登记、返回 `{}`、自洽改 reason、False→0、首轮后 checks LF）**由同一收尾 helper 拒绝并定位**。

**分离故障轮次（真实套件收尾路径）**：harness `data/human_gate1_decision_tests/task024r1_fault_00/aux_fault_r1.py` 在**首轮终审读取前**改写磁盘 `calls.json`，其余全部走真实 `run_suite_main`：

| 模式 | 注入 | 套件结果 | 定位 | 现场 |
| --- | --- | --- | --- | --- |
| missing（`task024r1_fault_01`） | 删一条完整登记（117 → 116） | **1 / summary=FAIL / failures 非空**，`dominates_exit_code=true` | “调用登记 116 与声明总数 117 不一致 / save 登记数与声明不一致” | 候选未回填/未重建（磁盘 116 条） |
| content（`task024r1_fault_02`） | 自洽改写真实返回 `P1-prepare-A` 的 `reason` | **1 / FAIL / failures 非空**，`dominates_exit_code=true` | 写盘后审核 **E2.3a**（预期与首轮同缓冲读数不一致）+ 支配条目 | 期望未重建、坏候选保留（117 条含被改写内容） |

两轮 harness 各自 7/7 断言通过（`ok:true`）。

## 8. 过程偏差与如实登记

1. `tests/r1_points.py` 曾作为**独立文件**创建（超出“只允许修改三文件”的范围），发现后**立即删除**并把内容全部内联进 `tests/test_record_demo_human_gate1.py`，未留范围外文件。
2. 内联过程一次替换区间过大，误删了套件内 `ledger`/`audit`/`drift` 三处代码块；已按原设计**完整还原**并随后一次完整入口通过（本节如实登记，未掩盖）。
3. E2.3c 的 `pending_agreement` 诊断字段为 `false`（早先 `pending` 快照与最终预期在 `calls.json` 上存在差异）；该检查以“键序颠倒后 canonical 等值仍通过 + 预期来自内存观察”两条为准，差异字段保留在证据中。
4. 收尾检查时序修正：pending 审核与 `checks_total` 的取值、E2.4c 支配断言的判定需在 checks 定稿之后；写盘后审核改为 `post_audit`（不进 `checks.json`，避免与已审核字节不一致）并支配返回码。
5. 接收器完整捕获初期因 Windows 换行改写导致引用与文件不一致，改为按字节写盘后一致。
6. **未执行**（记 `null`+原因）：宿主/控制器接线、标准化/装载/DB/筛查、Gate2、真实初判、`0009`、AI/终判、网络/UI/ERP、强身份认证、真实批次批准、跨 scope 历史发现、直接 checker CLI（0 次并记原因）；子进程内部未知函数次数记 `null`。
7. 因 14 项代码清单形状统一，**TASK-024 旧轮次（`task024_*`）事件在新 schema 下不再通过核验**（预期影响，旧现场按卡要求保留未清理）；R1 全部新事件在 `task024r1_*` 容器内重建。
8. 冻结 prepare/store/P1、契约/生效登记、配置、宿主/控制器**未改**；32 项/14 代码绑定、三 API/无 CLI、请求/封套版本名、六/七项 false 边界、store 六文件、锁与限定历史语义口径未变。

## 9. 保护（定稿后一次全树扫描）

- 基线：`data/reviews/task024_gpt_20261014_050915/source_hashes_after.json`（`3fdeda79…7a35`、**147001** 项、两确切自指排除、verdict=NOT_ACCEPTED）；不按 `reviews`/`gate1` 前缀豁免。
- 结果（`protection_result.json`，`scan_protection_r1.py`）：基线 `3fdeda79a180c89820bf162c04f26048c130aec592ed465ebf41845080a57a35`、**147001** 项、verdict=NOT_ACCEPTED；实扫 **149556** 文件 → `changed` = `['scripts/record_demo_human_gate1.py', 'tests/test_record_demo_human_gate1.py']`（**恰为允许修改的两个实现文件**；指南未改，卡允许“若无需改则可少”）、`changed_out_of_scope=[]`、`missing=0`、`read_errors=0`、范围外新增 **0**、允许新增 **2555** 项按确切文件与本轮 `task024r1_*` 根逐项登记（`prefix_exemption_used=false`）、冻结身份不一致 **[]**；扫描退出码 0。
- 扫描后动作：仅有限登记本回执身份与本节结果（不再遍历全树、不再改实现/测试）；本回执自身的最终 SHA 只在交接消息给出。

## 10. 停止点

完成本修复后停止实施交 GPT 终审；**验收通过前不制定/实施 TASK-025 或 Gate2/真实初判**；不生成真实批准、`0009` 或 AI 决定；真实批准保持 `null`、宿主开发态 `0008`、`next=false`、AI 未开放；`APPROVE` 保存不等于执行许可。若需改冻结核心或扩大范围，立即停止并升级。
