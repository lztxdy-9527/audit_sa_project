# TASK-025 执行回执：真实运行共享绑定与 Gate1→Gate2 材料接线设计（仅文档）

日期：2026-10-15。任务卡：`docs/tasks/TASK-025_DRAFT.md`（`8c93bbef6f9c401b531a77c379fbf1d7533cd5fd25f58e5941c93242bd1036fb`）。
依据：`docs/reviews/REVIEW_TASK_024_R8.md`（`48ac0358e2ae33f0504dbfe49c577dcab4b7135e7076194bb2fb11fd8cc57dde`，**ACCEPTED**，授权修复版）。
分类：C 类（GPT 架构约束 + DSH 文档落地），**仅文档**，交 GPT 验收。本回执不宣称任何验收通过，也不代表任何批次被批准。

## 1. 起点核对（只读实读）

| 文件 | 要求 SHA-256 | 实读 | 一致 |
| --- | --- | --- | --- |
| `tests/test_record_demo_human_gate1.py`（TASK-024 最终验收测试） | `fc38b82c694564bdc511573173d3d6ee9caf3aa7c421d7d95e4a0788cbdc87ff`（236681） | 同 | ✅ |
| `scripts/record_demo_human_gate1.py`（Gate1 适配器，冻结） | `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9` | 同 | ✅ |
| `docs/AUDIT_CONTRACT.md`（正式契约 V1 生效） | `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad` | 同 | ✅ |
| `docs/reviews/REVIEW_TASK_024_R8.md` | `48ac0358…7dde` | 同 | ✅ |
| `docs/tasks/TASK-025_DRAFT.md` | `8c93bbef…36fb` | 同 | ✅ |
| TASK-024-R8 最终 ACCEPTED 基线 `data/reviews/task024_r8_gpt_20261015_003349/source_hashes_after.json` | `86a41de068844b095fd777889ba36ec0ec2dc511b4a8a991821d895023439a27`（157238 项） | 同 | ✅ |

冻结准备器 `scripts/prepare_demo_human_gate1.py` 的 `FROZEN_PROJECT_SHA` 共 **21 项**，本轮逐项实读复核 **21/21 一致**（证据 `design_checks.json` 的 `frozen_registry_recheck`）。

## 2. 交付内容（仅新增两份设计文档 + 回执 + 证据根）

1. `docs/proposals/HUMAN_GATE_RUNTIME_INTEGRATION_V1_DRAFT.md`（首部标识 `DESIGN_DRAFT_NOT_IMPLEMENTED`）：
   现状与可复用边界、组件图与依赖顺序、候选 API 表、状态转换表、**共享运行绑定唯一来源与精确算法**、
   Gate1 新旧版本边界、输入/输出与持久目录、成功/失败顺序与末端规则、Gate2 材料白名单、
   冻结核心复用限制、分阶段实施切分与固定停止点、只读核验记录、设计自检清单。
2. `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md`（首部标识 `DESIGN_CASES_NOT_EXECUTED`）：
   统一夹具常量与规范指纹配方，以及任务卡要求的**十类**隔离案例（各含构造、预期结果、预期定位、
   “为何未被更早错误遮蔽”），并附未执行声明。
3. `data/human_gate_runtime_design_checks/task025_run_01/`：只读核验脚本与两份记录。
4. 本回执 `docs/EXEC_REPORT_025.md`。

## 3. 设计要点（对应任务卡 §3 的架构约束）

### 3.1 新运行层与旧开发链分开

- 只读实读确认 `scripts/control_demo_workflow.py` 的 `check_dev_action(workflow, action, *, current_bindings)`
  对 `ACTION_NORMALIZE` 的允许条件是 `phase == DEV_GATE1_APPROVED`，返回恒含
  `simulation_allowed`、`mode=DEVELOPMENT_TEST_ONLY`、`contract_status=DRAFT_NOT_IN_FORCE`、`next_step_allowed=False`；
  其真实批准键 `gate1_approval`/`gate2_approval` 恒为 `null`，且 `ACTION_AI` 分支恒不允许。
  **结论**：开发控制器没有真实放行接口，真实运行层必须自建判定，不得伪造模拟批准驱动它。
- 设计不修改 `0001—0008`，不规划旧链上的真实 `0009`；确定性核心按冻结字节复用，
  其 `DEVELOPMENT_TEST_ONLY`/`DEV_*` 原始标记如实保留。

### 3.2 同一批次从开始固定共享运行绑定

- **唯一来源**：[候选] 本批运行登记 `data/runtime/<batch_id>/runtime_registry.json`（当前不存在），
  在**接收与来源核验之后、第一次 Gate1 请求之前**固定，此后不再修改；变更即新运行版本/新批次。
- **六项逐一精确定义**（与 P1 冻结契约形状一致，只读实读确认
  `RUN_BINDING_KEYS = ("code","rules","config","input")`、`RUN_CODE_KEYS = ("file_sha256","manifest_fingerprint")`、
  `RUN_RULES_KEYS = ("version","manifest_fingerprint")`）：

| # | 字段 | 唯一来源 | 算法 |
| --- | --- | --- | --- |
| 1 | `code.file_sha256` | `scripts/record_demo_human_gate1.py` | 确切字节 SHA-256 |
| 2 | `code.manifest_fingerprint` | 本批代码清单（现行 14 项 = 13 项 `CODE_FILES` + Gate1 适配器） | `fingerprint({"entries": 按 UTF-8 升序, "manifest_version": 原文})` |
| 3 | `rules.manifest_fingerprint` | `sql/rules/r01..r04.sql` 清单 | `fingerprint({"version": …, "entries": 按 UTF-8 升序})` |
| 4 | `rules.version` | 规则清单 `version`（现行 `TASK-006-rule-core-1.1`） | 原样取用 |
| 5 | `config.file_sha256` | [候选] 本批运行配置（现行冻结配置 `config/human_flow_v1.json` 不改） | 确切字节 SHA-256 |
| 6 | `input.file_sha256` | 批次 `source/input.xlsx` | 确切字节 SHA-256 |

- `fingerprint(x) = sha256(canonical_json(x))`，`canonical_json` 口径与 [已存在]
  `scripts/build_demo_human_gate_decision.py::fingerprint` 一致（只读引用，不复制判据）。
- **Gate1/Gate2 `run_binding` 必须整体 canonical 相等**；**阶段材料集与 `materials_fingerprint` 可以不同、
  不要求相等**。文件 SHA-256 与对象规范指纹是两类值，分别登记、不互相替代。
- **新增组件处置无歧义**：本设计不创建占位文件；后续实现若新增运行层组件，必须在第一次 Gate1 请求前
  加入本批代码清单并重算 `manifest_fingerprint`；尚不存在的组件只列为未来构成要求，不编造 SHA。

### 3.3 Gate1 → 标准化/入库 → Gate2 候审顺序

设计给出的拟定顺序为：接收并核验来源 → 固定批次运行登记 → 展示 Gate1 材料并保存人类决定 →
实读核验当批有效 Gate1 APPROVE → 标准化与 SQLite 装载/核验 → 固定 Gate2 材料请求 → 暂停。
`HOLD`/`REJECT` 可保存但不得执行；质量/结构阻断、失败诊断、锁、缺凭证、错批/错指纹/错版本、
材料变化或不完整历史不得被 APPROVE 掩盖。只读检查点/状态恢复不调用标准化、装载或重新保存决定；
失败只在新运行输出目录留诊断并保留半成品现场。

### 3.4 复用核心的实际接口与路径（只读实读）

- `normalize_workbook(workbook_path, quality_report)`：前提由 `_require_convertible` 给出
  （报告结构有效、`result == "pass"`、`issues` 空、`workbook.sha256` 与当前输入相等、
  `checker.sha256` 与冻结 checker 相等、`reconciliation.status == "ASSESSED"` 且勾稽关系成立）；
  不满足抛 `NormalizationBlocked`，运行类错误抛 `NormalizationError`。
- `load_normalized_to_sqlite(normalized, database_path)`：前提 `normalization_version == "TASK-004-normalized-1.1"`、
  `mode == "DEVELOPMENT_TEST_ONLY"`、`next_step_allowed is False` 等；路径规则
  `SQLITE_TESTS_ROOT = (PROJECT_ROOT / "data" / "sqlite_tests").resolve()`，
  要求目标位于其内、非目录本身、**尚不存在**、父目录已存在；违反抛 `SqliteLoadBlocked`。
  成功报告含 `batch_status = "DEV_SQLITE_VERIFIED"`、`database_sha256`、`staging_sha256`、
  `normalized_payload_sha256` 等。提交前失败已回滚；**提交后失败（含关闭失败）不声称已回滚**。
- 本设计**不扩大核心路径权限**：新运行层在既有允许范围 `data/sqlite_tests/` 下使用独立新子目录，
  由新运行层自行创建该子目录；不改核心状态常量或标记。

### 3.5 确切协议与末端规则

- 六项绑定、清单排序/唯一性、canonical 算法、两类指纹含义均已逐项写明，无“实现任选”。
- 末端规则：全部必要语义消费在终端确认之前完成；**一次完整有界原始字节/集合/路径确认**覆盖
  登记、Gate1 材料、决定记录、标准化产物、数据库、装载报告、Gate2 请求与本轮台账；
  期望取自初始同缓冲或本次 writer 已绑定读数，**不从候选文件重建期望**；
  终端确认之后**不再读取候选文件**决定成功；任一真实审核/确认失败必须支配**真实公开出口**的
  非零返回、失败状态与非空失败记录，并在新输出目录落盘失败元数据、保留坏候选；台账不内嵌自身 SHA。
- 人类姓名/身份声明/事件 ID/时间/决定/原因仅来自显式提交，程序不生成或预填；
  不承诺本地哈希可抵御同权限全面重写。

## 4. 十类案例（书面，未执行）

案例集覆盖任务卡 §4 要求的十类：同批次同绑定合法 APPROVE 正常依赖；HOLD/REJECT 已保存但不得进入标准化；
阻断材料下 APPROVE 不得放行且 FAILED 不产生成功运行；共享六项任一不符则先前 Gate1 不可复用
（含“材料摘要不同但六项相同”的正向对照）；新阶段代码未纳入登记或后来添加组件则拒绝沿用旧批准；
模拟批准/开发 phase/D2 许可/聊天倾向/离线包冒充有效 Gate1；来源晚变更、失败诊断/锁/缺凭证、
重复执行或既有输出分别拒绝；装载提交前与提交后失败不混称回滚、数据库与报告不一致阻断 Gate2 候审；
Gate2 准备不依赖筛查且零线索不是本阶段结论；只读恢复不执行下游、末次失败支配真实出口且确认覆盖完整集合。

每类均给出：构造、预期结果、**预期定位**（具体字段/文件路径）、以及**“为何未被更早错误遮蔽”**的论证。
十类**全部未执行**、未捕获任何异常；涉及人类字段只引用既有 `PROTOCOL_TEST_FIXTURE_ONLY` 文本；
候选组件自身 SHA 一律未给出（组件不存在）。

## 5. 只读核验记录（25 项全部通过）

脚本：`data/human_gate_runtime_design_checks/task025_run_01/runtime_design_checks.py`（只读；仅读文件 + AST 解析，
**未导入任何业务模块、未调用任何业务函数**）。
记录：同目录 `design_checks.json`、`frozen_identity.json`。

| 核验组 | 结果 |
| --- | --- |
| 冻结身份与 21 项冻结登记逐项复核 | 21/21 一致；13 项代码清单中 12 项在登记内一致、1 项为该登记自身（如实分列） |
| 接口真实来源（AST 解析真实签名） | `normalize_workbook(workbook_path, quality_report)`、`load_normalized_to_sqlite(normalized, database_path)`、`check_dev_action(workflow, action, *, current_bindings)`、`resolve_database_path(database_path)` 全部匹配 |
| 核心允许范围与开发标记 | `SQLITE_TESTS_ROOT = (PROJECT_ROOT / "data" / "sqlite_tests").resolve()`；已存在目标拒绝覆盖分支存在；`MODE = "DEVELOPMENT_TEST_ONLY"` 保留；AI 动作恒不允许 |
| 依赖无环 | 13 项代码清单的代码级 import 边无环（`cycles: []`）；筛查位于 Gate2 之后由设计声明保证 |
| P1 六项相等口径 | `RUN_BINDING_KEYS`/`RUN_CODE_KEYS`/`RUN_RULES_KEYS` 实读匹配；设计正文六项齐备 |
| 状态不越界 | 状态名全部在封闭集合内，无未知名；固定停止点声明存在 |
| 候选标记 | `data/runtime`、三个候选模块均**不存在**；正文 `[候选]` 标记 16 处；两份首部标识齐备 |
| Gate2 材料白名单 | 排除子句存在（筛查结果/规则命中/复算/事实底稿/初判/AI/终判均排除） |
| 十类案例可核验性 | 1—10 编号齐备，每类“预期结果/预期定位/遮蔽论证”三者齐备；未执行声明存在 |

`design_checks.json` 记录 `"passed": true`，`failures: []`。

## 6. 分清五类陈述（设计建议 / 已冻结现状 / 书面计算 / 真实执行 / 未执行）

- **设计建议（[候选]，当前不存在）**：真实运行层组件、候选 API、状态名 `RT_*`、运行登记与持久目录、
  Gate2 材料请求组件、新运行配置。
- **已冻结现状（[已存在]，本轮未改动）**：Gate1 适配器与冻结准备器/P1 存储、正式契约、冻结配置与规则、
  标准化/SQLite/checker/接收器/跨核/筛查/事实底稿/初判核心、开发态流程控制与 `0001—0008`。
- **书面计算（仅夹具常量与配方）**：案例集中标注为“夹具常量”的抽象值；
  规范指纹配方 `fingerprint(x) = sha256(canonical_json(x))`（与既有实现同口径的书面引用）。
- **真实执行（本轮实际发生的）**：只读文件读取、AST 解析、SHA-256 计算、
  21 项冻结登记逐项复算、25 项设计核验，以及本回执与证据根的写入。
- **未执行**：未调用 `normalize_workbook` / `load_normalized_to_sqlite` / `check_dev_action` /
  任何 Gate1、P1、store 接口；未创建运行 profile、批准凭证、新接收批次、决定记录、数据库或宿主检查点；
  未安装依赖、未初始化 Git、未运行历史入口或计算核心；未重跑完整 98/93 项套件、writer/loader 或已关闭保存反例；
  未制定后续实现卡，未接 Gate2、宿主、真实初判、0009、AI/终判。

未观察项如实为“未执行”，不以默认零冒充观察。

## 7. 交付物与最终哈希

本轮**仅新增**下列文件，**未修改任何既有文件**（`changed=[]`，见 §8）：

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `docs/proposals/HUMAN_GATE_RUNTIME_INTEGRATION_V1_DRAFT.md` | 29236 | `342d2d75f7b3439bb4703496ed0b910409220f39ef4af2e21b2e7ba991c5123d` |
| `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md` | 13454 | `ee394833a680e350bad7e4cc1e8a56996c1db1d6441a122f2458202d15fd476a` |
| `data/human_gate_runtime_design_checks/task025_run_01/runtime_design_checks.py` | 18979 | `03d58b4b4a6985c1c36288e900a2418f0014a83b365954a619b6f9c09cc245a4` |
| 同目录 `design_checks.json` | 9330 | `d630ef35861176b905ddc0493174a32ac740e664fef62236c0a43e370f28f4da` |
| 同目录 `frozen_identity.json` | 8882 | `ce69aea7a9202792116980f1692b7854ca724377556e63fda1d92b6d64c9ac64` |
| `docs/EXEC_REPORT_025.md`（本回执） | 15626 | 最终 SHA-256 见交接消息（避免自指反复改写） |
| 同目录 `protection_scan_025.py` / `protection_scan_025.json` | 7309 / 4784 | `05cefa03…` / 见 §8 结果 |

## 8. 保护与历史留证

- 最终一次全树扫描（`protection_scan_025.py` / `protection_scan_025.json`）：以 TASK-024-R8 最终 ACCEPTED 基线
  （157238 项）为比对基线，实读结果 `changed = 0`（本卡**未修改任何既有文件**）、`missing = 0`、
  `read_errors = 0`、`out_of_scope_added = 0`、`out_of_scope_changed = 0`；
  `added = 7` 全部落在本卡明示文件与新根（两份设计文档、本回执、证据根 4 文件）；
  R5 越界 326 项逐项不变（`drifted = 0`、`gone = 0`）；`scope_compliant = true`。
- R5 越界 37 目录/326 文件继续固定留证、不追认、不动；旧 harness 不变，无恢复例外。
- 自指口径：基线快照自身与本轮扫描结果文件单列；基线漏登的既有文件按确切路径单列（不使用 reviews/data 大前缀豁免）。

## 9. 边界与待裁决

- 真实批准仍为 `null`，宿主仍为开发态 `0008`，`next_step_allowed=false`，AI 未开放；
  `APPROVE` 记录不等于执行许可；本设计不批准任何批次。
- 固定停止点：后续第一阶段实现**最多到 Gate2 候审**，不保存 Gate2 决定、不运行筛查。
- 待 GPT 裁决的口径：
  1. 共享运行绑定“唯一来源”采用 [候选] 单一批次运行登记文件（登记后不可修改）的方案；
  2. “Gate1/Gate2 `run_binding` 整体 canonical 相等、阶段材料集与摘要不要求相等”的相等口径；
  3. 阶段一固定停止点与阶段切分（阶段二起另行授权）。
- 若后续发现必须改变冻结 P1/契约/业务规则或需要人类新业务决定，将停止受影响设计并升级，
  不以扩大本卡范围继续实现。
