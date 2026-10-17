# TASK-024-R3 执行回执（恢复旧 harness 与剩余验收闭环）

任务：`docs/tasks/TASK-024-R3_DRAFT.md`（**B 类：DSH 定点实施，GPT 验收**）；依据 `docs/reviews/REVIEW_TASK_024_R2.md`。日期：2026-10-14。
执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务判断与看板：人类主理人。

**范围**：只修改 `scripts/record_demo_human_gate1.py`（起点 `1fb60e60…c9441f`／79832）与 `tests/test_record_demo_human_gate1.py`（起点 `14f5e238…a23291`／131776）；`docs/HUMAN_GATE1_DECISION_GUIDE.md`（`9c8f4409…c2fb`）**未改**（卡允许“无需同步则不改”）。新增 `docs/EXEC_REPORT_024_R3.md` 与本轮 `task024r3_*` 容器；新 fault driver 只建在 `data/human_gate1_decision_tests/task024r3_fault_00/`，未在 `tests/` 另建文件、未修改旧 driver 的业务模式。

**唯一具名历史恢复**：`data/human_gate1_decision_tests/task024r1_fault_00/aux_fault_r1.py`（**不追认 R2 越界**）。

**写后实读身份**：适配器 `76e95b0de262a4e751c2b35431249094e25148efc20bc32d0ac82dee812b82f4`（85015）；测试 `a4ad793240bd7c8973c15b1620759426cf45cf7bbad908afd0f1ac37e9581fde`（156692）；本回执自身最终 SHA 仅交接给出。

**修复起点**：`data/reviews/task024_r2_gpt_20261014_164601/source_hashes_after.json`，实读 **151000** 项、verdict=**NOT_ACCEPTED**、两个确切自指排除（`review_result.json`、`source_hashes_after.json`）。

---

## 1. 具名历史恢复（先保全，后恢复，逐字节验证）

| 阶段 | 值 |
| --- | --- |
| 恢复前当前修改版（实读） | `c148abea44cdbcf8fef2156afed37ab1460355cad22e9a421661fef17e7a3b4d`／**6386** 字节（与卡预期一致，未出现未说明新变化） |
| 保全副本 | `data/human_gate1_decision_tests/task024r3_preserve_01/aux_fault_r1_modified_c148abea.py`（逐字节相同）＋ `preserve_and_restore_manifest.json` |
| 恢复材料（实读校验） | `data/reviews/task024_r2_gpt_20261014_164601/recovered_aux_fault_r1_verified.py` = `7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035`／**4248** 字节 |
| 恢复后目标（写后验证） | `data/human_gate1_decision_tests/task024r1_fault_00/aux_fault_r1.py` = `7506a64b…1035`／4248，逐字节等于恢复材料；保全副本 SHA 未变 |

未执行恢复材料或旧 driver、未运行会覆盖旧 R1 轮次的旧模式、未改任何旧故障结果或旧回执；未放开其他冻结文件。

## 2. B1：终端只补内部集合与路径，不增加消费循环

实现（适配器）：`_terminal_confirm` 增加 `_confirm_event_layout`（事件目录**只含** `context/receipt/snapshots`、`snapshots` **恰为冻结六文件**、`failure.json` 优先阻断）与 `_confirm_batch_layout`（批次顶层**恰为既定八文件/固定子目录**，`checks`/`logs`/`source`/`code_snapshot` 各自集合固定——未知项不会因未进入 32 文件清单被忽略）；已消费路径在终端逐级 `_check_path_item`（link/junction/reparse + 正常文件/目录）。终端**不新增**核心加载、业务 JSON 解析或材料语义复算；白名单与初始预期仍在语义阶段确定。

实测（套件 `R3-B1.*`，均在真实 `_source_snapshot` 返回之后注入、各命中一次）：较早事件新增 `event_0001/unknown.json` → 本次 verify **Blocked 并定位 `event_0001`**，**撤销 wrapper 保留现场仍拒**，移除注入项后 returned；当前批次新增 `checks/unknown.json` → **Blocked 并定位 `batch_dir/checks`**，撤销仍拒、移除后 returned，**verify 未写 failure**；save 阶段内部集合变化 → 本次 save 拒绝并留**恰七键** `failure.json`。真实 junction 复查沿用既有 `_check_path_item` 规则（本环境未新建 junction，如实记未执行）。

## 3. B3：scope 值与已有范围绑定，日期真实合法

实现：保留七字段/八键封闭 schema 与类型检查；`_require_calendar_date` 用 `datetime.date.fromisoformat` 判**真实日历合法**（拒绝 `2026-09-00`、`2026-13-01` 等，保持原文、不补值）；`_load_frozen_config` 只读冻结 `config/human_flow_v1.json`（逐级无链接复核）并与 `source_scope` 逐项绑定 `company/currency/period_start/period_end`、`as_of_date↔cutoff_date`，另校验 `synthetic_data=true`；不读历史业务源、不新增业务阈值、不改变 CNY／2026 年 9 月范围。

实测（套件 `R3-B3-*`，就地改一项 + 同步外层哈希，六快照/材料/期望不动）：`currency→USD`（配置绑定仍 CNY）→ Blocked `…evidence.source_scope.currency`；`period_start=2026-09-00` → Blocked `…source_scope.period_start`；`company` 与配置矛盾 → Blocked `…source_scope.company`；三例前后对照均 returned。

## 4. E2.1：路径参数按角色记真实有界现场

实现（测试观察层）：`bounded_dir_scene` 只读目录**首层（≤32 项）**逐项记类型/大小/SHA/子目录首层条目（不 rglob 项目或历史根）；`PATH_ROLES` 分列角色——冻结 prepare `arg[0]`=输入目录、`store.verify` `arg[0]`=输入目录、**`store.save` `arg[0]`=输出目标**；输出目标记“建立前不存在”，写后记六份快照（`output_scene_after`），**早拒绝路径要求不产生输出目录**；`object_fingerprint` 对目录按有界场景取指纹。

实测：**E2.1e** 路径输入按角色记真实有界现场（目录记存在性与集合，不再 `exists=false`；文件输入记 SHA；30 个目录场景）通过；**E2.1f** `out_dir` 单列输出角色（建立前不存在、写后六快照；拒绝路径不产目录）通过。

## 5. E2.2：消费对象三时点（到所属公开 API 收尾）

实现：`RETAINED` 注册表在记录时保留**实际消费对象引用**（private，不写 JSON）；`finalize_api_time_point()` 在**所属公开 API（prepare/save/verify）的 `finally`** 中执行，对同一引用再取独立规范指纹，写入 `input_unchanged_through_api` 与 `three_time_points_equal`；正式审核对“第三时点不一致 / 三时点不一致”直接失败，且“预期变更”标记仅在**窗口内确有注入且三时点确实检出差异**时成立（否则按控制失效失败）。

实测：**E2.2f** 全部核心观察三时点逐条一致通过；**辨识度控制 `R3-E2.2-third-point`** 在 `observe_core` 已返回、父 API 未收尾的窗口内改写保留引用 → **第三时点检出**，移除“预期变更”标记后同一正式规则拒绝该条记录。函数代码指纹仍只标注 `scope="function_code_only"`，不代替对象不变性；不重复调用核心凑对照。

## 6. E2.3：包装层分列与独立入口闭合

实现：观察安装绑定**首次见到的真实函数**为内层、不重复包装；测试文件内的注入 wrapper（如 S9 探针）**保留在调用链上**且其条目记入 `test_wrapper_entries`（**不计入业务层**）；闭合判据为**独立聚合（`sys.settrace`）== 完整条目 == 唯一调用 ID == 声明 total**，`sys.setprofile` 作第二通道交叉核对，非零即失败、不放行（`frame_delta` 仅作交叉信息）。

最终入口逐层结果：冻结 prepare **110/110/110**、真实 P1 **132/132/132**、`store.save` **31/31/31**、`store.verify` **101/101/101**；四层 `cross_check_delta=0`、`test_wrapper_entries=[]`（R2 的 30/31 差 1 已定位为内层误绑测试 wrapper，修正后归零，非硬编码减 1）。

## 7. 新 fault driver（只建本轮新根，走同一实际收尾路径）

`data/human_gate1_decision_tests/task024r3_fault_00/aux_fault_r3.py`，输出目录运行前均不存在；两模式均在**首轮终审读取前**改写磁盘候选，其余全部走真实 `run_suite_main`：

| 模式 | 轮次 | 注入 | 套件结果 | 最小差异与候选保全 |
| --- | --- | --- | --- | --- |
| `core_missing` | `task024r3_fault_01` | 从 **506** 条完整真实 core 观察仅删 1 条（`core-prepare::533`） | **1 / FAIL / failures 非空** | 磁盘仍 **505 条核心结构**；**其余条目与原始候选逐条 canonical SHA 相等**；`candidate_sha == on_disk_sha` |
| `one_field` | `task024r3_fault_02` | 只改一条输入 snapshot 的一个字段（`core-p1::8` / `actor`），**保留原 SHA/长度描述** | **1 / FAIL / failures 非空** | 磁盘仍 **506 条核心结构**；**差异恰为该 `call_id`**；正式审核定位“输入描述与完整值不自洽”；`candidate_sha == on_disk_sha` |

两模式各 11 项断言全部通过（`ok:true`）：`injected_once / return_code_nonzero / summary_is_fail / failures_nonempty / located / minimal_diff / candidate_structure_preserved / candidate_bytes_equal_final / remaining_core_entries_identical / expectation_not_rebuilt`。旧 `fault_03/04` 现场与原回执保留未改，本回执仅作纠正（其最终 core 文件是 116 条 API 记录，**不再称 407→406 或单字段异常已完成**；旧 R1 两个故障是 7/7 证据）。

## 8. 最终入口与保护扫描

最终完整入口（全新容器 `task024r3_run_07`）：**88 项检查 / 0 失败 / 退出码 0**；写盘后审核 8 项全 OK；失败支配 `status=PASS、failures=0、返回码=0`；登记计数 prepare 32 / save 41 / verify 66、冻结接收器 3（退出码 0/0/1）、核心条目 **506**；逐层闭合见 §6。**未执行项**（记 `null`+原因）：宿主/控制器、标准化/装载/DB/筛查、Gate2、真实初判、`0009`、AI/终判、网络/UI/ERP、强身份认证、真实批次批准、跨 scope 历史发现、直接 checker CLI（0 次并记原因）、**新建真实 junction**（环境未建立，路径规则沿用既有控制）。

最终保护扫描（`data/human_gate1_decision_tests/task024r3_run_07/scan_protection_r3.py` + `protection_result.json`）：基线 `task024_r2_gpt_20261014_164601/source_hashes_after.json`（**151000** 项、NOT_ACCEPTED、两确切自指排除、无前缀兜底）→ 实扫 **154041** 文件：
- **普通 changed** = `scripts/record_demo_human_gate1.py`、`tests/test_record_demo_human_gate1.py`（允许修改的两个实现文件；指南未改）——**范围外变化 0**；
- **单列授权历史恢复** = `data/human_gate1_decision_tests/task024r1_fault_00/aux_fault_r1.py`，实读 SHA = `7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035`／4248 → **达到更早原始 SHA，ok=true**；
- `missing=0`、`read_errors=0`、**范围外新增 0**、按确切路径与本轮 `task024r3_*` 根登记允许新增 3041 项、`prefix_exemption_used=false`；扫描退出码 0。
- 扫描后动作：仅有限登记本回执身份与本节结果（不再改实现/测试、不再遍历全树）。

## 9. 过程偏差与未重跑范围（如实登记）

1. R2 越界修改（旧 harness）**未被追认**：本轮按裁决先保全后恢复，未以“非交付物”为由豁免。
2. 本轮为定位 `store.save` 30/31 差异多次迭代（先后尝试按文件基名过滤、双通道计数、真实内层绑定），最终定位为内层误绑测试 wrapper 并在 §6 修正；期间未改动旧结果/旧回执。
3. E2.2 控制项前两次尝试以包装 store/P1 内部接缝注入未进入调用路径（已如实记录），最终改为在收尾窗口直接改写保留引用这一确定性接缝。
4. 因 14 项代码清单形状在 R1 统一，TASK-024 旧 `task024_*` 事件在新 schema 下不再通过核验（预期影响；旧现场与 junction 均保留未清理）。
5. 未重跑 TASK-021/022/023 历史入口、核心大套件、宿主或数据库链（按卡）；B2 小正向控制与既有 B4/E1 修复随最终入口执行并通过。

## 10. 停止点

完成本修复后停止实施交 GPT 终审；**验收通过前不制定/实施 TASK-025 或 Gate2/真实初判**；不生成真实批准、`0009` 或 AI 决定；真实批准 `null`、宿主开发态 `0008`、`next=false`、AI=false；`APPROVE` 保存不等于执行许可；业务判断与看板归人类。若需扩大范围或改冻结组件，先停并升级。
