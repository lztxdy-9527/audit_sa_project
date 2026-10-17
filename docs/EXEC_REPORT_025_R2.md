# TASK-025-R2 执行回执：补正保存调用式与一份完整技术基样

日期：2026-10-15。任务卡：`docs/tasks/TASK-025-R2_DRAFT.md`。
依据：`docs/reviews/REVIEW_TASK_025_R1.md`。分类：C 类设计文档修正（DSH 落地、GPT 验收）。
**只处理三项残余**；此前已关闭项（人类字段来源、摘要方向、目录三角色、停止点、清单正文常量化、登记指纹无自指）**未重做**。
未实施代码、未新增框架、未重跑业务链。

## 1. 起点核对（只读实读）

| 文件 | 要求 SHA-256 | 实读 | 一致 |
| --- | --- | --- | --- |
| `docs/proposals/HUMAN_GATE_RUNTIME_INTEGRATION_V1_DRAFT.md` | `284d0a5233ef8704c8b973598ea80bef8b7563fb7abdfe2646fe3e9352d357be`（45697） | 同 | ✅ |
| `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md` | `b0b5da9448c1fabde5e9035bc7ae7028fbbcc1463b7b76510477bf95983ef3fd`（22755） | 同 | ✅ |
| 基线 `data/reviews/task025_r1_gpt_20261015_013855/source_hashes_after.json` | 见同根 `review_result.json`（157273 项） | 同 | ✅ |
| `tests/test_record_demo_human_gate1.py`（冻结） | `fc38b82c694564bdc511573173d3d6ee9caf3aa7c421d7d95e4a0788cbdc87ff`（236681） | 同 | ✅ |
| `scripts/record_demo_human_gate1.py`（冻结） | `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9`（85064） | 同 | ✅ |

## 2. B1 关闭依据：唯一保存调用式

### 2.1 只调用一次 store 并显式传历史

设计 §5.1 现在写出**完整保存步骤**（不留“已核验对象可直接信任”的假设）：

```text
1) 独占获取 scope 锁；从 scope_dir 实读既有事件，形成完整历史核验结果
2) 自己重新实读登记与当前批次来源：
   current_request = prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id)
3) 逐项比较 submission 绑定与本次独立预期；任一不符 → 拒绝且不建事件目录
4) 空历史也必须实际枚举后形成三键对象：
   verified_history = {"declared_complete": <bool>, "declared_scope": <str>, "records": [...]}
5) 唯一核心保存步骤——只调用一次 store，并显式传历史：
   store.save_human_gate_decision_snapshots(
       event_dir / "snapshots", submission,
       current_request["materials"], current_request["expectations"],
       prior_history=verified_history)
   —— 该函数内部自己校验并调用 P1 一次；删除此前独立的
   build_human_gate_decision_record(...) 预调用
6) 由本运行适配器独占写 context.json / receipt.json 并读回；全部消费后一次完整有界确认
```

- `prior_history` 在冻结 P1 与 store 中**都是关键字参数**，缺省/显式 `None` 都会在 P1 第 4 步被拒绝；
  设计明确“空历史也必须**实际枚举**成三键对象”，不允许省略该键或默认 `records=[]`。
- **删除**了独立 `build_human_gate_decision_record(...)` 预调用（store 内部本就调用一次 P1，重复验证已消除）。
- 核验断言只统计“编号保存步骤”内的 store 调用次数 = 1，且步骤内注明“P1 由该函数内部调用一次”。

### 2.2 save 自己重新实读当前来源

- 入口签名改为 `save_runtime_gate1_decision(batch_dir, runtime_dir, request_id, submission, event_dir, *, scope_dir)`：
  **不再**接收调用方旧 `request` 对象；第 2 步自己重跑 `prepare_runtime_gate1_request` 取得
  `current_request`，仅用于**本次独立预期比较**。
- 保存前来源变化 → 比较失败 → **拒绝旧 submission 且不建事件**；写入阶段失败保留现场。
- 有效批准核验同样改为按 `batch_dir` / `runtime_dir` **实读当前批次材料**后比较
  （§5.3 第 1 条已补写“不是只比较旧快照与旧登记”）；Gate2 的数据库定位与其 `runtime_dir` 一致，
  未知/越界路径拒绝、不跟随任意报告路径。

### 2.3 同段接口更正

- `boundaries` 改为**对象**：冻结 `BOUNDARY_KEYS` 七键、**七项严格 `false`**（不再是 `list[str]`）；
  请求封闭键恰为冻结 `REQUEST_KEYS` 六键，并补入 `evidence`（冻结 `EVIDENCE_KEYS` 七键）。
- **移除**生产请求中的固定 `outer_label`：测试标记 `PROTOCOL_TEST_FIXTURE_ONLY` 只留在测试证据外层。
- 写入方分清：`context.json` / `receipt.json` 由**本运行适配器**独占写；
  冻结 store **只写** `event_dir/snapshots/` 下六文件（`decision_result.json`、`expectations.json`、
  `manifest.json`、`materials.json`、`prior_history.json`、`submission.json`）；
  不再称 P1 有“七键失败协议”或能写封套。
- 冻结准备器自身来源材料为 **31 项**，加入本层新脚本后才是 **32 项**，两个层级计数**不混称**。

## 3. B2 关闭依据：物理归属固定，数量矛盾消除

- 本期**只新增一个脚本** `scripts/runtime_gate1.py`；运行登记、新 Gate1 请求/保存、有效批准核验、
  Gate2 材料准备**均为该文件内的逻辑函数分组**，**不是**四个新增模块。
- 因此代码清单**恰 14 项** = 冻结 13 项 `CODE_FILES` + 该新文件；材料**恰 32 项**。
- **不保留“13+N 任选”**：本期不得另建 `runtime_registry.py` 等文件却仍宣称 14 项；
  未来物理拆分或新增依赖属**新运行版本/新批次**并重算清单。
- 组件 SHA 仍只在未来文件实际存在时实读；本卡**未编造**真实文件 SHA（见 §4 的书面虚构标注）。

## 4. B3 关闭依据：一份真正可解析、可复算的完整基样

**落盘位置**：`data/human_gate_runtime_design_checks/task025r2_run_01/runtime_baseline.json`
**文件 SHA-256**：`716d898229bc3b27542d6ddeb2ed8aa02859188365c524cf157ab7adca26dcd8`（70032 B）

**内容**（键名与冻结常量一致）：`registry`（13 键，含 `run_binding` 与 `run_binding_sha256`）、
`gate1_request` / `gate2_request`（六键请求 + `batch_id`/`run_binding`/`run_binding_sha256`/`contract`/
`code_manifest`/`files`/`quality`）、两 Gate 的七键 `materials` 与八键 `expectations`、
`submission`（11 键）、`prior_history`（三键）、`record`（17 键）与 `wrapper`（三键）、
`source_real_values`（13 项冻结文件实读 SHA、来源批次 ID、既有证据路径）、`written_fictitious_labels`。

- **可解析**：文件为纯 UTF-8 JSON（`indent=2, sort_keys=True`），无省略号、无 `<...>`、无 `×64` 缩写；
  所有摘要字段都是**完整 64 位小写十六进制**。
- **真值 vs 书面虚构**：`[已存在]` 13 项代码、4 项规则、批次 8 文件的摘要为**实读真实值**；
  `[候选] scripts/runtime_gate1.py` 与 Gate2 抽象产物（`normalized.json` / 数据库 / `load_report.json`）
  的摘要为**明确标注的书面虚构 64hex 常量**（由标签 SHA-256 派生），
  **不声称**是真实组件文件哈希。
- **submission 与 record 分清**：`submission` 恰 11 键（`SUBMISSION_KEYS`），
  **不含** `decided_at_source`，且含 `submission_version`/`gate`/`request_binding`/`prior_decision_binding`；
  `decided_at_source = "HUMAN_PROVIDED_RAW"` **只出现在 `record`**（17 键 `RECORD_KEYS`）。
- **人类字段**逐字符取自 `FIXTURE-EV-G1-0001`（`event_id`/`decided_at_raw`/`reason`/`actor`，`HUMAN_DECLARED`），未新造。
- **关系可复算**：两 Gate `run_binding` 为**同一对象**（canonical 逐字符相等），
  两 Gate `materials_fingerprint` 各自复算且**不同**；`expected_files` 与 `materials.files` **双向相等**。

**正文引用**：集成设计 §3.2(4b) 与案例集 §0.3 **只引用**该 JSON 的路径与文件 SHA，
并删除原先各自维护的带省略号/占位写法的“完整对象”。

## 5. 定点核验（54 项全部通过）

脚本 `verify_baseline_r2.py`（只读）：**直接读取最终 `runtime_baseline.json`**，
并用 AST 实读冻结常量核对。记录 `design_checks_r2.json`：`passed=true`、`failures=[]`。

覆盖：JSON 可解析与文件身份；三份冻结脚本的键集常量 AST 实读一致；
无省略号/尖括号/`×64`；所有摘要全串合法；`code_manifest` 键集/计数/排序/唯一/指纹复算
（13 项真实值一致 + 第 14 项即新脚本）；`rules_manifest` 4 项与指纹；`run_binding` 形状、
指纹复算、`code` 与清单/单文件一致、**两 Gate 相等**；两请求封闭键、`boundaries` 为七键全 false 对象、
`evidence` 键集、**无 `outer_label`**；两 Gate `materials` 键集、`files` 形状/排序/唯一/计数
（32 / 3）、材料指纹复算、**两指纹不同**；两 `expectations` 八键与 `expected_files` 双向相等；
`submission` 11 键且**不含** `decided_at_source`、含四个易漏键、人类字段为已登记 `HUMAN_DECLARED`；
`prior_history` 三键且 `records` 为**显式空列表**；`record` 17 键、**含** `decided_at_source`、指纹复算；
`wrapper` 三键；正文引用基样路径与 SHA、正文无省略号占位；保存调用式与物理归属断言；
候选脚本**确实不存在**；`context/receipt` 与 snapshots 写入方分清。

## 6. 分清各类陈述

- **设计建议（[候选]）**：`scripts/runtime_gate1.py` 内的四组逻辑函数、`RT_*` 状态、运行目录与登记。
- **已冻结现状（[已存在]，本轮零改动）**：旧 Gate1 适配器与冻结准备器、冻结 P1 纯内存核心与 store、
  正式契约、冻结配置与规则、标准化/SQLite/checker/接收器/核心、开发态流程控制与 `0001—0008`。
- **书面计算**：基样中的摘要派生（`fingerprint` 复算）与推导顺序；`[候选]`/抽象产物的**书面虚构常量**。
- **真实执行（本轮实际发生）**：只读读取与 AST 核对、SHA-256 实读复核、基样生成与 54 项定点核验、
  两份正文的定点修改、本回执与证据根写入。
- **未执行**：未导入或调用 `build_human_gate_decision_record`、`save_human_gate_decision_snapshots`、
  `prepare_human_gate1_request`、`normalize_workbook`、`load_normalized_to_sqlite`、`check_dev_action`
  或任何业务接口；未创建运行登记、批准凭证、接收批次、决定记录、数据库、运行 profile、宿主检查点；
  未重跑 R1 的 36 项自检与旧扫描（只读引用其记录）；未制定 TASK-026。
- 基样**不冒充**实际标准化、真实 SQLite 核验或已执行的端到端流程。

## 7. 交付物与最终哈希

**本次修改（恰两份允许正文）**：

| 路径 | 起点 | 最终 |
| --- | --- | --- |
| `docs/proposals/HUMAN_GATE_RUNTIME_INTEGRATION_V1_DRAFT.md` | `284d0a52…57be`（45697） | `a313e64777cff77a835d985e4af71b50dbeb3b2aae71e6963c89f683e5f69718`（53069） |
| `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md` | `b0b5da94…f3fd`（22755） | `e8327246b83309d1989157d2eeb7688964b3dcd3f07705e248480a445c019771`（22994） |

**本次新增**：

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `data/human_gate_runtime_design_checks/task025r2_run_01/runtime_baseline.json` | 70032 | `716d898229bc3b27542d6ddeb2ed8aa02859188365c524cf157ab7adca26dcd8` |
| 同目录 `build_baseline_fixture.py` | 18898 | `9c1516b4465b1e8af960b540a55a7962e4d2a621a2beb2777718f16e45a5e290` |
| 同目录 `verify_baseline_r2.py` | 23025 | `4185c707dab36f132d5081b27c62b48cfaf96fbc30abcc2615843cc6b22fcc1a` |
| 同目录 `design_checks_r2.json` | 12636 | `b393e77c26f49d26cd246784b0e850af256deb6438cf731dab0b13479a568fd2` |
| 同目录 `protection_scan_025r2.py` | 7333 | `083c0857523ac60b8b17cf3fe4d026d9536c935cb0ef3ba509f1126505fe66ae` |
| 同目录 `protection_scan_025r2.json` | 5513 | `e359f613daae8e5c1a38e5ff38283edd4131c482cc655102296d4e85fc92d209` |
| `docs/EXEC_REPORT_025_R2.md`（本回执） | 12717 | 最终 SHA 见交接消息（避免自指） |

## 8. 保护与历史留证

- 最终一次全树扫描（`protection_scan_025r2.py` / `protection_scan_025r2.json`，`e359f613…d209`）：
  基线 `data/reviews/task025_r1_gpt_20261015_013855/source_hashes_after.json`（157273 项，实读 157276 项）；
  实读结果 `changed = 2`，**恰为两份允许正文**；`out_of_scope_changed = 0`；
  `added = 6`，**全部为新文件**（本回执 + 证据根 5 文件：`runtime_baseline.json`、
  `build_baseline_fixture.py`、`verify_baseline_r2.py`、`design_checks_r2.json`、`protection_scan_025r2.py`）；
  `out_of_scope_added = 0`、`missing = 0`、`read_errors = 0`；
  两份被修改正文只出现在 `changed` 中、未重复登记为新增；
  R5 越界 326 文件逐项不变（`drifted = 0`、`gone = 0`）；`scope_compliant = true`。
- 旧 R5 越界 326 文件不变且不追认；旧回执、旧自检记录、旧扫描结果**不覆盖、不重跑**。

## 9. 边界与待裁决

- 真实批准仍 `null`，宿主仍开发态 `0008`，`next_step_allowed=false`，AI 未开放；技术验收不批准任何批次。
- 待 GPT 裁决：① §5.1 的唯一保存调用式（一次 store + 显式 `prior_history` + save 自己重读来源）；
  ② 物理归属固定为一个新脚本（13+1=14，材料 32）并删除 `13+N` 分支；
  ③ 基样文件 `runtime_baseline.json` 的完整性与可复算性（54 项定点核验）。
- 若后续发现必须改变冻结 P1/契约/业务规则或需要人类新业务决定，将停止受影响设计并升级。
  完成本卡后停止交 GPT；不自行制定或实施 TASK-026。
