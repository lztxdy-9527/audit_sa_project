# 真实运行共享绑定与 Gate1→Gate2 材料接线设计（V1 草案）

```
标识：DESIGN_DRAFT_NOT_IMPLEMENTED
任务：TASK-025（C 类：GPT 架构约束 + DSH 文档落地）
日期：2026-10-15
状态：设计草案。本文件不实现任何组件、不创建任何运行登记、不产生任何批准或凭证。
前提：docs/reviews/REVIEW_TASK_024_R8.md 的授权修复版 ACCEPTED（最终测试
      tests/test_record_demo_human_gate1.py = fc38b82c694564bdc511573173d3d6ee9caf3aa7c421d7d95e4a0788cbdc87ff）。
```

> 阅读须知
> - 文中所有以 **[候选]** 标注的名称、字段、目录均为**设计建议，当前不存在**，不表示已实现、已通过或已授权执行。
> - 文中 **[已存在]** 标注的对象来自本轮只读实读（确切路径与 SHA 见 §11），其行为与字节均未修改。
> - 本文件**不**赋予开发态控制器任何真实批准语义，**不**修改 `0001—0008`，**不**规划在旧开发链上追加真实 `0009`。
> - 真实批准仍为 `null`，宿主仍为开发态 `0008`，`next_step_allowed=false`，AI 未开放。
> - 本文件不构成批次批准，也不构成人类审计判断。

---

## 1. 本设计范围与停止点

- 本设计覆盖：同一新批次的**共享运行绑定**唯一来源，以及 **Gate1 → 标准化/入库 → Gate2 候审**的材料接线与顺序规则。
- 本设计**不**覆盖：真实计算放行、Gate2 决定保存、筛查/复算/事实底稿/真实初判/AI/终判的接口。
- **固定停止点（硬约束）**：后续第一阶段实现**最多到 Gate2 候审**（Gate2 材料请求固定并暂停）。
  **禁止的是 Gate2 决定保存与筛查运行**；运行登记与 Gate1 决定记录**属于阶段一必须产生的产物**
  （Gate1 决定记录保存在独立 Gate1 记录根，见 §6.2）。
- **本卡（TASK-025/R1）自身不创建任何产物**：不写运行登记、不写决定记录、不建数据库、不建运行 profile；
  阶段一才产生这些文件。明确区分“本设计卡不产生”与“阶段一必须产生”。

---

## 2. 现状与可复用边界（只读实读）

| 类别 | 内容 | 处置 |
| --- | --- | --- |
| **[已存在] 确定性计算核心** | `scripts/normalize_demo_data.py`、`scripts/store_demo_sqlite.py`、`scripts/check_demo_data.py`、`scripts/receive_demo_batch.py`、`scripts/crosscheck_demo_rules.py`、`scripts/screen_demo_sqlite.py`、`scripts/build_demo_fact_packet.py`、`scripts/build_demo_initial_judgment.py` | 可按冻结字节复用其函数；**不改**其行为、标记或状态常量 |
| **[已存在] Gate1 独立适配器** | `scripts/record_demo_human_gate1.py`（`d8ace42f…34d9`）与冻结准备器 `scripts/prepare_demo_human_gate1.py`、P1 存储 `scripts/store_demo_human_gate_decision.py` | 只读复用；其 32 项/14 项请求与保存协议保持不变（见 §6） |
| **[已存在] 开发态流程控制** | `scripts/control_demo_workflow.py`（`a6b7b8e1…3a8c`）：`create_dev_workflow` / `prepare_dev_gate` / `record_dev_decision` / `check_dev_action`，模式 `DEVELOPMENT_TEST_ONLY`，阶段名 `DEV_*`，`gate1_approval`/`gate2_approval` 恒为 `null` | **继续保留**为开发与对照样本；真实运行层**不得**把其 `simulation_allowed` 解释为放行 |
| **[已存在] 模拟产物** | `SIMULATED_HUMAN` / `SIMULATED_TEST_ONLY` / 模拟 APPROVE / 模拟初判 / 旧 checkpoint | 真实模式**一律拒绝**；不转换、不补签、不追认 |
| **[候选] 真实运行层** | 运行登记、Gate1/Gate2 请求与材料、有效批准核验、标准化/入库接线、Gate2 候审 | 本设计给出协议；实现属后续另卡 |

**开发控制器为什么不能承担真实放行（只读实读结论）**：`check_dev_action(workflow, action, *, current_bindings)`
对 `ACTION_NORMALIZE` 的允许条件是 `phase == PHASE_G1_APPROVED`（`DEV_GATE1_APPROVED`），
即**开发模拟阶段**；其返回值恒含 `"simulation_allowed"`、`"mode": "DEVELOPMENT_TEST_ONLY"`、
`"contract_status": "DRAFT_NOT_IN_FORCE"`、`"next_step_allowed": False`。
该函数**没有**真实放行接口，也不接受任何真实批准凭证。因此真实运行层必须自建判定，
**不得**伪造模拟批准去驱动它。

---

## 3. 组件图、依赖顺序与候选 API

### 3.1 依赖顺序（拟定，无环）

```
[已存在] receive_demo_batch        →  接收与来源核验（八文件批次封套）
[已存在] check_demo_data           →  质量/结构/勾稽核验，产出 quality_report
[候选]   runtime_registry          →  固定本批次共享运行绑定（六项，见 §4）
[候选]   runtime_gate1             →  **新版本** Gate1 请求/保存入口（§5.1；承载扩展清单）
[已存在] prepare_demo_human_gate1  →  仅复用其来源核验返回（八文件批次 + 质量 + 31 项来源）
[已存在] record_demo_human_gate1   →  **旧入口原样保留**，只服务其自身 14/32 项台账，不承载扩展清单
[已存在] store_demo_human_gate_decision → P1 决定记录纯内存核心与快照保存/读回（冻结，被复用）
[候选]   gate1_effective_approval  →  实读核验“当批有效 Gate1 APPROVE”（§5 S4）
[已存在] normalize_demo_data       →  四表标准化（§9）
[已存在] store_demo_sqlite         →  SQLite 装载与装载核验（§9）
[候选]   gate2_materials_request   →  固定 Gate2 候审材料请求并暂停（§8）
[已存在] (Gate2 之后才可用) screen_demo_sqlite / crosscheck_demo_rules /
         build_demo_fact_packet / build_demo_initial_judgment
```

**无环性**：`check_demo_data`（质量）→ `runtime_registry`（绑定）→ Gate1 → 有效批准核验 → 标准化 → 入库 →
Gate2 候审；筛查/复算/事实底稿/初判**全部位于 Gate2 之后**，不参与上述任何前置条件。
因此“Gate2 材料不得依赖筛查结果”在本设计中是**结构保证**，不是约定。

### 3.2 候选 API（全部为拟定，当前不存在）

最小字段表以**封闭键 + 严格类型 + 常量 + 来源**四列给出。全部候选入口**只校验与按原文记录**，
不生成人类字段、不推断批准、不补造时间或决定。`H` 表示 64 位小写十六进制字符串。

**（1）候选入口签名（唯一调用链，无“任选”）**

**物理归属（本期固定）**：下列入口**全部位于同一个新脚本** `scripts/runtime_gate1.py`（**当前不存在**）内的**逻辑函数分组**，
不是四个新增模块。因此本批代码清单为**冻结 13 项 + 该新文件 = 14 项**（§4.3），材料 **32 项**；
**不保留“13+N 任选”分支**。未来若真拆出独立文件，属**新运行版本/新批次**并重算清单，不能在当前固定协议里选择 N。

| 候选入口（同属 `scripts/runtime_gate1.py`） | 实读来源（有据可取） | 返回外层键 | 失败 |
| --- | --- | --- | --- |
| `build_runtime_registry(batch_dir, runtime_dir, *, scope_dir)` | `batch_dir` 实读八文件；`code_manifest` 逐文件实读 §4.3 的 14 项；`rules_manifest` 实读 4 项 SQL；`config`/`input` 实读单文件；登记写到 `runtime_dir` | `{"registry": …, "registry_sha256": H, "registry_file_sha256": H}` | `RuntimeGate1Blocked`（越界/缺件/数量不符）；`RuntimeGate1Error`（I/O/解析） |
| `read_runtime_registry(runtime_dir)` | 实读 `runtime_dir/runtime_registry.json` 字节 | `{"registry": …, "registry_file_sha256": H}` | 同上 |
| `prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id)` | 从 `runtime_dir` 实读登记；复用冻结准备器来源核验返回；逐文件实读当前材料 | `{"request": …, "request_sha256": H}` | `RuntimeGate1Blocked` / `RuntimeGate1Error` |
| `save_runtime_gate1_decision(batch_dir, runtime_dir, request_id, submission, event_dir, *, scope_dir)` | **自己重新**实读登记与当前批次来源并**重跑 prepare**（§5.1）；从 `scope_dir` 实读完整历史 | `{"record": …, "record_fingerprint": H, "event_relative": …}` | 冻结 P1/store 拒绝按原样上抛 |
| `verify_gate1_effective_approval(batch_dir, runtime_dir, *, scope_dir, event_relative)` | 实读登记 + 实读该 scope 下事件目录快照与上下文/回执 + **当前批次材料** | 见下表（11 键） | 拒绝时 `effective=false` 并给 reasons；I/O 失败抛 Error |
| `prepare_gate2_materials_request(batch_dir, runtime_dir, normalized_relatives, load_report_relative, *, request_id, scope_dir)` | 从 `runtime_dir` 实读登记、标准化产物与装载报告，并**实读数据库文件本身**（§8 实读要求） | `{"request": …, "request_sha256": H}` | `Gate2RequestBlocked` / `Gate2RequestError` |

`runtime_dir` 是**由调用方显式给出的技术输出路径**（如 `data/runtime/<runtime_name>/`），
**不通过任意业务 ID 拼接目录**；运行输出在该路径内；来源只读，决定记录与数据库分别使用 §6 的独立允许根。

**（2）登记对象 `registry` 封闭键（13 项；来源全部为实读）**

| 键 | 类型 | 常量/取值 | 来源 |
| --- | --- | --- | --- |
| `registry_version` | str | `"TASK-025-runtime-registry-1.0"` | 常量 |
| `batch_id` | str 非空 | 原样（不做归一化） | 已核验批次/冻结准备器 materials.batch_id；不从 submission 或目录名推断 |
| `registered_at` | str ISO-8601 带时区 | **程序取当前时间**（登记动作本身不是决定/批准，**无人类手工录入**） | 运行时钟 |
| `scope_ref` | str 相对路径 | 本项目内相对路径（`runtime_dir` 之外的独立 Gate1 记录根下 scope） | 调用方显式提供 |
| `batch_files` | list[3 键] | 恰 8 项；键 `(relative, file_sha256, byte_size)`；`relative` 唯一且按 UTF-8 升序 | 批次目录实读 |
| `code_manifest` | 对象 | 键恰 `(manifest_version, entries)`；`manifest_version = "TASK-025-code-manifest-1.0"`；`entries` 恰 14 项，键恰 `(relative, file_sha256)`，排序见 §4.3 | 逐文件实读 |
| `rules_manifest` | 对象 | 键恰 `(version, entries)`；`version = "TASK-006-rule-core-1.1"`；`entries` 恰 4 项，键恰 `(rule_id, rule_version, relative, file_sha256)` | 逐文件实读 |
| `config` | 对象 | 键恰 `(file_sha256, config_ref)` | 实读单文件 |
| `input` | 对象 | 键恰 `(file_sha256, byte_size, input_ref)` | 实读单文件 |
| `contract` | 对象 | 键恰 `(contract_version, contract_file_sha256, contract_effective)`；`contract_file_sha256 = 174a021b…40ad`；`contract_effective = true`（逐字符等于冻结登记值） | 实读正式契约 |
| `run_binding` | 对象 | 见 §4.2 六项 | 由以上四项聚合 |
| `run_binding_sha256` | H | `canonical_sha256(run_binding)`（**只作用内层对象**） | 派生 |
| `note` | str 常量 | `"RUNTIME_REGISTRATION_ONLY: not a decision, not an approval, not an execution permission"` | 常量 |

**摘要正文（唯一）**：`registry_sha256 = fingerprint(registry)`，其中 `fingerprint(x) = sha256(canonical_json(x))`。
该值放在**外层返回**（以及登记文件旁的读回记录）中；**登记文件本身不写自身的文件 SHA-256**，
即**不存在需排除的自指键**。登记文件的**文件 SHA-256** 单独登记在 §6.1 的文件清单里。

**（3）Gate1 请求对象封闭键（恰六键）**

| 键 | 类型/常量 | 来源 |
| --- | --- | --- |
| `request_version` | str，`TASK-025-human-gate1-runtime-request-1.0` | 新层常量 |
| `status` | str，`RUNTIME_GATE1_REQUEST_PREPARED` | 新层常量 |
| `materials` | 冻结 P1 `MATERIALS_KEYS` 七键 | 本次实读；批次、运行绑定、契约、文件名单与质量均位于此对象内 |
| `expectations` | 冻结 P1 `EXPECTATIONS_KEYS` 八键 | 当前来源独立预期；不取自 submission |
| `evidence` | 冻结 `EVIDENCE_KEYS` 七键 | 五项来源说明取冻结准备器返回；code_manifest/rules_manifest 替换为本次登记的完整清单对象，与 registry 严格 canonical 相等 |
| `boundaries` | 冻结 `BOUNDARY_KEYS` 七键对象，七项严格 false | 固定边界 |

不再将 `batch_id/run_binding/run_binding_sha256/contract/code_manifest/files/quality` 冗余放入请求顶层。
批次与运行绑定取 `materials`；运行对象指纹取 registry；清单取 `evidence`；文件与质量取 `materials`。
生产对象没有 `outer_label`；夹具标记只在测试证据外层。prepare 的返回包装仍恰为
`{"request": request, "request_sha256": fingerprint(request)}`，调用方先解包再消费六键请求。

**材料计数（本设计新增，不是旧值复用）**：`code_manifest.entries` 恰 **14** 项
（13 项 `CODE_FILES` + 候选运行适配器自身 `relative`）；`materials.files` 恰 **32** 项
（同 14 项代码 + 4 项规则 SQL + `docs/SPEC_V1.md`、`docs/AUDIT_CONTRACT_DRAFT.md`、`docs/AUDIT_CONTRACT.md`、
`docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md`、`config/human_flow_v1.json`、`sql/demo_schema.sql`
共 6 项 + 批次 8 项）。**旧的 14/32 常数属于冻结旧实现**：新层即使计数偶然相同，集合构成也不同，
因此**不得**声称复用旧台账或旧摘要公式。

**（4）Gate2 请求对象封闭键**：与 (3) 同构，但

- `request_version = "TASK-025-human-gate2-runtime-request-1.0"`，`status = "RUNTIME_GATE2_REQUEST_PREPARED"`；
- `materials.files` 为 §8 白名单材料集（含标准化产物、数据库文件、装载核验报告原文），
  **计数与摘要与 Gate1 不同**，但 `run_binding` 六项与 Gate1 **整体 canonical 相等**；
- `expectations.expected_prior_gate1` 指向 Gate1 记录外层指纹与其 `run_binding`。

**（4b）完整书面基样（可直接解析与复算）**

上述 (2)(3)(4) 的**完整展开对象**（`run_binding` 六项、14 项 `code_manifest`、4 项 `rules_manifest`、
32 项材料名单、七键 `materials`、八键 `expectations`、11 键 `submission`、三键 `prior_history`，
以及 Gate2 材料/独立预期与 17 键书面 `record`）已写入本轮证据根的一**个** JSON 文件：

```
路径：data/reviews/task025_r2_gpt_20261015_020841/runtime_baseline_corrected.json
文件 SHA-256：84cdd60347ffccd8afbeccdce1372c572a1da7ab1a4a1ac97571fa1f71504a84
```

该文件**不含**省略号、尖括号伪值或 `×64` 缩写：全部摘要字段都是**完整 64 位小写十六进制**；
其中 `[已存在]` 文件的摘要为**实读真实值**，`[候选]` 组件
（`scripts/runtime_gate1.py`）与 Gate2 抽象产物的摘要为**明确标注的书面虚构常量**
（`written_fictitious_labels`），**不声称**是真实组件文件哈希。
正文与案例集只**引用**该文件，不再各自维护一份带省略号的“完整对象”。

**（5）有效 Gate1 核验返回（11 键封闭；全部来自实读）**

| 键 | 类型 | 取值 | 来源 |
| --- | --- | --- | --- |
| `verification_version` | str | `"TASK-025-gate1-effective-approval-1.0"` | 常量 |
| `batch_id` | str | 与登记逐字符相等 | 登记 |
| `event_relative` | str | 事件相对路径 | 调用方 |
| `record_fingerprint` | H | 记录外层规范指纹 | 实读 `decision_result.json` 复算 |
| `record_file_sha256` | H | 记录文件字节 SHA | 实读该文件字节 |
| `run_binding_sha256` | H | 与登记相等 | 实读记录内 `binding.run_binding` 复算 |
| `materials_fingerprint` | H | 与当批材料相等 | 实读记录内 `binding.materials_fingerprint` |
| `decision` | str 枚举 | `("APPROVE","HOLD","REJECT")` | 实读记录 |
| `actor_kind` | str 常量 | `"HUMAN_DECLARED"`（**唯一接受值**；`SIMULATED_HUMAN` 等一律拒绝） | 实读记录，冻结 P1 `ACTOR_KIND_HUMAN` |
| `effective` | bool | 仅当**全部**条件成立才为 `true` | 派生 |
| `reasons` | list[str] | 拒绝原因逐条（`effective=true` 时为 `[]`） | 派生 |

`effective=true` 只表示**该具体动作的必要前提成立**；不表示保存成功、不表示放行任何后续动作。

### 3.3 状态转换表（拟定）

| 状态 | 含义 | 允许的下一状态 | 不允许 |
| --- | --- | --- | --- |
| `RT_RECEIVED` | 批次已接收并核验来源，尚未固定运行绑定 | `RT_REGISTERED` | 直接进入 Gate1/标准化 |
| `RT_REGISTERED` | 本批共享运行绑定六项已固定并写入登记文件 | `RT_G1_PENDING` | 修改登记（改动即新批次/新运行版本） |
| `RT_G1_PENDING` | Gate1 材料请求已固定，等待人类决定 | `RT_G1_DECIDED` | 用开发模拟 phase 放行 |
| `RT_G1_DECIDED` | Gate1 决定已保存（APPROVE/HOLD/REJECT） | `RT_G1_EFFECTIVE`（仅 APPROVE 且实读核验通过） | 未经核验即标准化 |
| `RT_G1_EFFECTIVE` | 当批有效 APPROVE 已实读核验 | `RT_NORMALIZED` | 材料/版本变化后继续沿用 |
| `RT_NORMALIZED` | 标准化产物与装载核验报告已登记 | `RT_G2_PENDING` | 装载核验失败仍进 Gate2 |
| `RT_G2_PENDING` | Gate2 候审材料请求已固定并暂停（**本阶段终点**） | `RT_G2_DECIDED`（**不在本阶段**） | 运行筛查、保存 Gate2 决定 |
| `RT_STOPPED` | 任一阻断（质量/凭证/绑定/失败诊断/锁） | 人工处置后**新批次** | 自动重试、换批次掩盖 |

`HOLD`/`REJECT` 只进入 `RT_G1_DECIDED` 并**停止**，不得进入标准化。

---

## 4. 共享运行绑定：唯一来源与精确算法

### 4.1 唯一来源（本设计的核心约束）

同一批次的 `run_binding` **只在一个地方**确定：**[候选]** 本批运行登记文件
`<runtime_dir>/runtime_registry.json`（**当前不存在**，路径为拟定；封闭键与摘要正文见 §3.2(2)）。
Gate1 材料与 Gate2 材料中的 `run_binding` 均**引用同一份登记**，不得各自重新计算。
登记写入后，**Gate1/Gate2 两侧都只从该文件实读六项**（`read_runtime_registry`），
不各自重算、不接受调用方内存注入。

- **登记时点**：接收与来源核验通过之后、**第一次 Gate1 请求之前**。此后不再修改。
- **变更即新批次**：代码/规则/配置/输入的任一变化 → 新运行版本、新批次、新登记；
  旧登记与其决定记录只读保留，**不补签、不追认、不静默迁移**。
- **阶段自有组件**（Gate1/Gate2 各自新增的适配器与请求组件）也必须纳入**本批代码清单**
  （见 §4.2 manifest 算法），不能因为共享摘要而漏掉实际执行者。

### 4.2 六项逐一精确定义

P1 冻结契约的 `RUN_BINDING_KEYS = ("code", "rules", "config", "input")`，其形状为
`RUN_CODE_KEYS = ("file_sha256", "manifest_fingerprint")`、
`RUN_RULES_KEYS = ("version", "manifest_fingerprint")`、`RUN_SINGLE_KEYS = ("file_sha256",)`。
因此“共享运行绑定六项”是以下**六个具体字段**：

| # | 字段 | 含义 | 唯一来源 | 算法 |
| --- | --- | --- | --- | --- |
| 1 | `code.file_sha256` | 本批**主执行单文件**的确切字节 SHA-256（与清单第 14 项为**同一文件**） | [候选] 运行适配器单文件 `scripts/runtime_gate1.py`（**当前不存在**；存在后取实读值） | `sha256(文件确切字节)` |
| 2 | `code.manifest_fingerprint` | **完整代码清单**的规范对象指纹 | 本批 `code_manifest`（§3.2(2)，恰 14 项） | `fingerprint({"entries": entries, "manifest_version": "TASK-025-code-manifest-1.0"})` |
| 3 | `rules.manifest_fingerprint` | 规则清单的规范对象指纹 | 本批 `rules_manifest`（恰 4 项） | `fingerprint({"entries": entries, "version": "TASK-006-rule-core-1.1"})` |
| 4 | `rules.version` | 规则清单版本 | `rules_manifest.version` | 常量为 `"TASK-006-rule-core-1.1"`，**不接受其他值** |
| 5 | `config.file_sha256` | 本批配置**确切文件字节** SHA-256 | 冻结 `config/human_flow_v1.json`（§4.4） | `sha256(文件确切字节)` |
| 6 | `input.file_sha256` | 本批输入工作簿**确切文件字节** SHA-256 | 批次内 `source/input.xlsx` | `sha256(文件确切字节)` |

**清单正文只此一种结构**（不得有“字段可含可不含”的余地）：

```
code_manifest   = {"entries": [{"relative": <str>, "file_sha256": <H>}, ...],
                   "manifest_version": "TASK-025-code-manifest-1.0"}
rules_manifest  = {"entries": [{"rule_id": "R01".."R04", "rule_version": <str>,
                                "relative": <str>, "file_sha256": <H>}, ...],
                   "version": "TASK-006-rule-core-1.1"}
```

- `entries` **逐项恰为上述封闭键**（多一键/少一键即拒绝）；`relative` 唯一且按 **UTF-8 字节升序**；
  条目内**不出现** `byte_size`（旧实现 14 项为 2 键形状，新层沿用 2 键，避免“可含可不含”）。
- `manifest_version` 是**常量**，没有 `<原文>` 占位，也没有 null 分支。
- **历史事实（只读记录，不复用）**：旧 TASK-024 实现的实际正文为
  `{"entries": …, "manifest_version": null}`（冻结准备器只返回 `entries`），
  其指纹为 `bb286a4938477e3a81bc5e034e2ca4de6cb8f07f47b1f7bff0579af5a7cec323`。
  这只是**旧算法的历史取值**；新层改用常量版本，**不得**把新值说成旧指纹、也不得用旧值校验新清单。

- `fingerprint(x) = sha256(canonical_json(x))`，`canonical_json` 为
  `json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)` 的 UTF-8 字节。
  该口径与 **[已存在]** `scripts/build_demo_human_gate_decision.py::fingerprint` 一致（只读引用，不复制判据）。
- **清单唯一排序与去重**：按 `relative` 的 **UTF-8 字节升序**排序，`relative` 必须唯一；
  算法与现行冻结实现一致（见 §6）。清单**不含** `byte_size` 时指纹为对象指纹；
  材料名单另含 `byte_size`，其字段参与 materials 正文；不得把材料条目与两键 code 清单混用。

### 4.3 [候选] 本批代码清单的构成（14 项）

**[已存在]** 冻结准备器已确定 13 项 `CODE_FILES`（见 §11.3），其文件 SHA 全部逐文件实读，并与验收基线比较；`FROZEN_PROJECT_SHA` 21 项只覆盖其中一部分，
不能代替全部 13 项实读或声称包含准备器自身。

**本批代码清单的构成规则（唯一）**：14 项 = **13 项 [已存在] `CODE_FILES`** +
**1 项本批主执行单文件**（[候选] 运行适配器 `scripts/runtime_gate1.py`，**当前不存在**）。
其中 13 项的真实 SHA 逐文件实读并与验收基线比较；第 14 项的 SHA **只能在该文件真实存在时实读取得**，
本设计**不给出、也不编造**其值。

**冻结旧清单的归属（防止误用）**：旧实现的 14 项 = 13 项 `CODE_FILES` + **旧 Gate1 适配器自身**
（`scripts/record_demo_human_gate1.py`），其文件 SHA 为 `d8ace42f…34d9`；
旧清单指纹为 `bb286a4938477e3a81bc5e034e2ca4de6cb8f07f47b1f7bff0579af5a7cec323`。
新层清单与旧清单**成员不同**（第 14 项不同），因此**指纹必然不同**。

**新增组件的处置（明确、无歧义，本期已固定为“一个文件”）**：
- 本期只新增**一个**运行脚本 `scripts/runtime_gate1.py`；运行登记、新 Gate1 请求/保存、有效批准核验、
  Gate2 材料准备**都是该文件内的逻辑函数分组**，**不是**四个新增模块。
  因此清单**恰为 14 项**（13 项 [已存在] + 该新文件），材料**恰为 32 项**。
- **不保留“13+N 任选”**：本期不得另建 `runtime_registry.py` 等文件却仍宣称 14 项。
- 未来若物理拆分或新增依赖 → **新运行版本/新批次**并重算 `manifest_fingerprint`，
  不能在当前固定协议里把 N 变成可选项；旧批次登记与决定只读保留。
- 本设计**不**创建任何占位组件文件；新组件**尚未存在**时，清单只列 [已存在] 13 项 + 该候选文件，
  **不编造**其 SHA（其值只能在该文件真实存在时实读取得，见 §11.3 与本轮基样 §0.3 的书面虚构标注）。
- **主执行单文件**与**清单内全部组件**都必须在清单内（不能因共享摘要而漏掉实际执行者）；
  清单内出现项目外路径或未登记新增文件即拒绝。

### 4.4 `rules` 与 `config` 的来源

- **[已存在] 规则清单**：`sql/rules/r01.sql`…`r04.sql`，`RULE_IDS = ("R01","R02","R03","R04")`，
  `RULE_VERSIONS = ("TASK-006-R01-1.0", …, "TASK-006-R04-1.0")`，`RULES_MANIFEST_VERSION = "TASK-006-rule-core-1.1"`。
  四项 SHA 见 §11.3。
- **[已存在] 开发配置** `config/human_flow_v1.json`（`ae4caa38…fb7c`，219 B，canonical JSON + 单个 LF）。
  该文件已冻结，**本设计不改动它**。
- 本版运行绑定的 config 固定复用 `config/human_flow_v1.json` 的确切字节；材料中同一路径与
  registry.config/run_binding.config 必须相等。不新建另一个运行配置文件；未来确需新增配置属另卡新版本/新批次。
- code/rules 清单的 relative 均为项目相对路径（不带 `project/`）；materials 中项目文件统一加 `project/`，
  两者通过这一个固定前缀映射逐项核对，不把旧清单或旧指纹带入新层。

### 4.5 独立读取与冻结时点

| 项 | 读取方 | 时点 | 冻结方式 |
| --- | --- | --- | --- |
| code 清单（13 项 [已存在] + 1 项候选主文件） | [候选] runtime_registry | 登记时 | 逐文件实读字节 → 逐项 SHA → 清单指纹 |
| code.file_sha256 | 同上 | 登记时 | 单文件实读字节 SHA |
| rules 4 项 | 同上 | 登记时 | 逐文件实读字节 → 清单指纹 |
| config | 同上 | 登记时 | 实读字节 SHA + 规范形状校验 |
| input | 同上 | 登记时 | 实读字节 SHA + `byte_size` |
| 六项相等核对 | [候选] Gate1/Gate2 请求 | 每次请求前 | 与登记对象**整体 canonical 相等**（见 §4.6） |

### 4.6 相等关系与“两类指纹不互替”

- **Gate1/Gate2 的 `run_binding` 必须逐字段相等**：比较方式为
  `canonical_json(gate2_run_binding) == canonical_json(gate1_run_binding)`；
  不接受“就近匹配”“字段补齐”“忽略顺序”之外的任何放宽。字符串原样比较，不做大小写或数字归一化。
- **阶段材料集与摘要可以不同**：`materials.files`（32 项 vs Gate2 材料集）与
  `materials_fingerprint` 分别计算、**不要求相等**；只有 `run_binding` 六项要求相等。
- **文件 SHA-256 与对象规范指纹是两类值，不互相替代**：
  - **文件 SHA-256**：取自**确切原始字节**（工作簿、数据库、JSON、Markdown、SQL 均如此）；
    同一对象的两种排版会产生两个不同的文件 SHA。
  - **对象规范指纹**：只取自**约定 canonical JSON 字节**（如 `manifest_fingerprint`、`materials_fingerprint`、`registry_sha256`）。
  - 报告中必须分别标注两类值，不得用一类替代另一类。

---

## 5. Gate1：新旧版本边界、唯一接线与顺序

### 5.1 唯一接线与唯一保存调用（**不允许“旧接口或新版本任选”**）

只读实读结论（决定本节唯一性）：冻结入口 `scripts/record_demo_human_gate1.py` 的 `_extend_request`
严格要求**恰 14 项代码 / 32 项材料**，且公开保存 API `save_human_gate1_decision(batch_dir, request_id,
submission, event_dir, *, scope_dir=None)` **自身重新真实准备**、**不接受调用方注入** registry/run_binding；
冻结 P1 纯内存核心 `build_human_gate_decision_record(submission, materials, expectations, *, prior_history=None)`
与快照保存 `save_human_gate_decision_snapshots(out_dir, submission, materials, expectations, *, prior_history=None)`
的 `prior_history` **均为关键字参数**，且缺省/显式 `None` 都会在 P1 第 4 步被**拒绝**（不接受默认空历史）。
`save_human_gate_decision_snapshots` **内部自己调用一次 P1**（`_core()` → `build_human_gate_decision_record`
等价路径），因此**外部不得再次预调用 P1**。

**唯一入口（全部位于 `scripts/runtime_gate1.py`，当前不存在）**：

```text
build_runtime_registry(batch_dir, runtime_dir, *, scope_dir)
prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id)
save_runtime_gate1_decision(batch_dir, runtime_dir, request_id,
                           submission, event_dir, *, scope_dir)
```

**`save_runtime_gate1_decision` 的唯一核心保存步骤（完整写出，不留“已核验对象可直接信任”的假设）**：

```text
1) 独占获取 scope 锁；从 scope_dir 实读既有事件，形成完整历史核验结果
2) 自己重新实读登记与**当前批次来源**：current_result = prepare_runtime_gate1_request(
       batch_dir, runtime_dir, request_id)
   current_request = current_result["request"]
   —— current_request 只用于**本次独立预期比较**，不把上一次返回对象或 submission 自报状态当来源
3) 逐项比较 submission 的绑定与本次独立预期（batch_id / request_id / materials_fingerprint /
   prior_decision_binding）；请求自身 run_binding 六项与登记相等，不能声称 submission 有这些字段；
   任一不符 → 拒绝，**不建事件目录**
4) 空历史也必须**实际枚举**后形成三键对象：
   verified_history = {"declared_complete": <bool>, "declared_scope": <str>,
                       "records": [<既有事件 wrapper，按 event_id UTF-8 升序>]}
   （`records` 为空列表时也必须是**显式枚举得到的空列表**，不允许省略该键、不允许 `None`）
5) 唯一核心保存步骤——**只调用一次 store**，并显式传历史：
   store.save_human_gate_decision_snapshots(
       event_dir / "snapshots", submission,
       current_request["materials"], current_request["expectations"],
       prior_history=verified_history)
   —— 该函数内部自己校验并调用 P1 一次；**删除**此前独立的
   `build_human_gate_decision_record(...)` 预调用（那会造成重复验证）
6) 快照写好后，由**本运行适配器**独占写 `context.json` 与 `receipt.json` 并读回；
   全部必要消费后做一次完整有界确认（§7.2）
```

**类型与归属更正（同段）**：

- `boundaries` 是**对象**（冻结 `BOUNDARY_KEYS` 七键、七项严格 `false`），**不是** `list[str]`。
- 生产请求**不含**固定 `outer_label`：`PROTOCOL_TEST_FIXTURE_ONLY` 只留在**测试证据外层**。
- `context.json` / `receipt.json` 由**本运行适配器**独占写出；冻结 store **只负责快照六文件**
  （写在 `event_dir/snapshots/` 下：`decision_result.json`、`expectations.json`、`manifest.json`、
  `materials.json`、`prior_history.json`、`submission.json`）。
  **不得**称 P1 有“七键失败协议”或能写封套：P1/store 是纯内存核心与快照保存，
  失败诊断文件的写出属适配层职责（§6.1）。
- **来源变化必须拒绝旧 submission**：第 3 步比较失败时不建事件；写入阶段失败则保留已建/半写现场；
  **不**用旧批准、旧摘要或旧请求对象“补齐”当前来源。

**旧入口保持原样**：`prepare_human_gate1_decision_request` / `save_human_gate1_decision` /
`verify_human_gate1_decision` **零字节改动**，继续只服务其自身 14/32 项台账；
禁止把扩展清单塞进旧入口、禁止给旧记录换摘要、禁止复制旧批准作为新决定；**不改**冻结 P1/store/契约。

**scope 与封套关系**：新层事件写在**同一个独立 Gate1 记录根**（§6.2）下的**新 scope**，
与旧 TASK-024 scope 只读并存；`context_version` 取新版本常量，旧事件不转换、不补签、不追认。

**冻结数量限制的归属**：`14 项/32 项` 的硬性断言属于**冻结旧实现**（`_extend_request`）；
新层清单由 §3.2(3) 与 §4.3 定义（13 冻结项 + `scripts/runtime_gate1.py` = 14 项；材料 32 项），
其计数与排序**由新层自己断言**，不得引用旧实现的断言结果。
冻结准备器自身的来源材料为 **31 项**，加入本层新脚本后才是 **32 项**——两个层级的计数不得混称。

**兼容边界与唯一允许修改位置**：新版本请求/保存必须在**新增脚本** `scripts/runtime_gate1.py`
（**当前不存在**）中实现；对冻结文件的唯一“改动”是**零改动**。
旧版本号 `TASK-024-human-gate1-decision-request-1.0` 不得复用。

### 5.2 拟定顺序（Gate1 段）

```
S0 RT_RECEIVED   接收器运行（八文件批次封套）→ 质量报告通过来源/协议核验（可为 OK 或自洽 BLOCKED）
S1 RT_REGISTERED 固定本批共享运行绑定六项 → 独占写 runtime_registry.json（§6.1）
S2 RT_G1_PENDING prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id) 固定 Gate1 请求（§3.2(3)）→ 展示给人类
S3 RT_G1_DECIDED 人类显式提交决定 → save_runtime_gate1_decision(batch_dir, runtime_dir, request_id, submission, event_dir, *, scope_dir)（经冻结 store 内部一次 P1）→ 独立记录根
S4 RT_G1_EFFECTIVE 实读核验“当批有效 APPROVE”（§5.3）
```

**S3 的人类字段**只来自**已登记夹具或人类显式提交**（§5.4），程序不生成、不预填、不推断。

### 5.3 “当批有效 APPROVE”的实读核验条件（拟定，全部必须成立）

`verify_gate1_effective_approval` 逐条实读并核对；任一条不成立即 `effective=false`：

1. 记录 `gate == "GATE1"`、`batch_id` 与当前批次**逐字符相等**；
   且该核验按 `batch_dir` / `runtime_dir` **实读当前批次材料**后比较，
   **不是**只比较旧快照与旧登记（旧快照自洽不能证明当前材料未变）；
2. `decision == "APPROVE"`，且 `actor_kind == "HUMAN_DECLARED"`（`SIMULATED_HUMAN` 等一律拒绝）；
3. 记录内 `binding.run_binding` 与本批登记**整体 canonical 相等**（六项逐字段）；
4. 记录内 `binding.materials_fingerprint` 与**当批材料**规范指纹相等；
5. `prior_gate1` 按冻结 P1 原规则核验（本设计不放松）；
6. `quality` 无阻断，且**记录所在事件目录不含 `failure.json`**；scope 无锁残留、凭证完整；
7. 记录文件**确切字节 SHA** 与记录内规范化对象指纹**分别登记**且自洽。

核验通过仅表示**“该具体动作的必要前提成立”**，不表示所有后续权限开放；
`next_step_allowed` 一类默认值**不得**解锁任何真实动作。

### 5.4 人类字段的来源（程序不生成）

| 字段 | 唯一来源 | 允许值 |
| --- | --- | --- |
| `actor.actor_kind` | 已登记夹具或人类显式提交 | 恰为 `"HUMAN_DECLARED"`（冻结 P1 `ACTOR_KIND_HUMAN`） |
| `actor.actor_id` / `actor.declaration_note` | 同上 | 人类原文，不改写、不归一化 |
| `decided_at_raw` | 同上 | 人类原文；record-only 的 `decided_at_source` 为协议常量 `HUMAN_PROVIDED_RAW`，不进入 submission |
| `reason` | 同上 | 人类原文（允许“暂不能判断”+原因，属后续初判范围，不在本卡） |
| `event_id` | 同上 | 人类原文，保持前导零等原样 |

已登记夹具（**只读引用，仅取人类字段**）：`FIXTURE-EV-G1-0001`（APPROVE）、
`FIXTURE-EV-G1-0002`（HOLD）、`FIXTURE-EV-G1-0003`（REJECT）；路径与 SHA 见案例集 §0.1。

---

## 6. 输入/输出与持久目录（三类角色分开列清）

**§6 不再统称“所有写路径都在一个目录”。**三类目录角色、来源只读边界与实际允许根如下。

### 6.1 角色一：运行输出目录（**本批新建**，[候选]）

**路径规则**：`runtime_dir` 由调用方**显式给出**（如 `data/runtime/<runtime_name>/`，
其中 `runtime_name` 是**调用方指定的技术名**，**不由任意业务 ID 拼接**）。
`<runtime_dir>` 一旦确定，运行产物在该目录内；决定记录写 §6.2 独立记录根，数据库写 §6.3 允许根，来源始终只读。

| 产物 | 候选路径 | 写入方 | 写入方式 | 登记内容 |
| --- | --- | --- | --- | --- |
| 运行登记 | `<runtime_dir>/runtime_registry.json` | 本运行适配器 | 独占新文件；目录不存在则先建**本批新目录** | 文件 SHA + `registry_sha256`（§3.2(2)） |
| 运行登记读回 | `<runtime_dir>/runtime_registry_readback.json` | 本运行适配器 | 独占新文件 | 读回同缓冲结论 + 外层指纹 |
| 标准化产物 | `<runtime_dir>/normalized.json` | 本运行适配器 | 独占新文件 | 文件 SHA + 记录内对象指纹 |
| 装载核验报告 | `<runtime_dir>/load_report.json` | 本运行适配器 | 独占新文件 | 文件 SHA |
| Gate2 材料请求 | `<runtime_dir>/gate2_request.json` | 本运行适配器 | 独占新文件 | 文件 SHA + `request_sha256` |
| 失败诊断 | `<runtime_dir>/failure.json` | **适配层**（不是 P1；P1 不写文件） | 独占新文件（失败时） | 阶段/字段/原因/异常链等 |

**来源只读边界**：`batch_dir`（批次八文件）与项目侧 21 项冻结材料**只读**，
本层从不写回源材料；运行目录内**禁止**出现源材料的副本除外的改写。

### 6.2 角色二：独立 Gate1 记录根（**[已存在] 冻结布局，只增不改**）

- 根：`data/human_gate_decision_records/gate1/<scope>/<event>/`（[已存在] 现行布局）。
- 每个事件目录包含：**适配层独占写**的 `context.json` 与 `receipt.json`，
  以及 **snapshots 子目录** `event_dir/snapshots/` 下的六文件
  `(decision_result.json, expectations.json, manifest.json, materials.json, prior_history.json, submission.json)`。
  六文件由**冻结 `save_human_gate_decision_snapshots(out_dir, ...)`** 写出（`out_dir` 即该 snapshots 目录），
  新层不自造字段；失败诊断由适配层在该事件目录写独占 `failure.json`。
- **新层只在该根下写自己的新 scope/新事件**；旧 scope 与其事件**只读**，
  不转换、不补签、不追认、不更换绑定，**不因新层需要而改动旧字节**。
- **普通业务 ID 不直接作为任意文件路径**：`batch_id`/`event_id` 是**数据字段**；
  事件目录用本层确定的固定叶名（如 `event_000N`），与 `event_id` 字段解耦（沿用现行做法）。

### 6.3 角色三：SQLite 独立子目录（**[已存在] 核心允许根之内**）

- 根：`data/sqlite_tests/`（[已存在] 核心 `SQLITE_TESTS_ROOT` 的**唯一**允许根）。
- 新运行层在其中使用**本批新子目录** `data/sqlite_tests/runtime_<batch_id>/`，
  数据库文件名候选为 `runtime.sqlite`；该子目录由新层在装载前创建。
- **不扩大核心路径权限、不改核心状态常量或开发标记**；核心仍拒绝已存在目标与越界路径（§9.1）。

### 6.4 三类角色的共同规则

- **失败与诊断**：运行操作失败在**本批运行输出目录**（角色一）留诊断；决定保存失败在本次新事件目录留诊断，保留已提交/半写现场；
  **不修改源材料、不改写历史、不重试覆盖、不自动换批次或 scope**；诊断自身失败时如实保留原异常。
- **越界**：任何写路径必须落在上述三类角色之一；越界即阻断。
- **独占**：所有新文件均独占创建，目标已存在即拒绝。

---

---

## 7. 成功与失败顺序、末端规则

### 7.1 拟定顺序与最后成功提交点

```
S5 RT_NORMALIZED  标准化（核心只读调用）→ 写 normalized.json（独占新文件）
S6 RT_NORMALIZED  SQLite 装载（核心只读调用）→ 无覆盖发布 → 装载核验报告
S7 RT_G2_PENDING  固定 Gate2 材料请求（§8）→ 暂停
```

**最后成功提交点（拟定）**：`S7` 中 Gate2 材料请求文件发布成功，且**全部必要语义消费与审核完成**，
并在**一次完整有界原始字节/集合/路径确认**通过之后，才可对外声明“Gate2 候补已就绪”。
此前任何阶段均不得声明整体成功。

### 7.2 末端规则（沿用并强化 TASK-024 的教训）

1. **全部必要语义消费在终端确认之前完成**：需要读取的对象（登记、材料、决定记录、标准化产物、
   装载报告、数据库）必须在确认前读完；终端确认之后**不再读取候选文件**来决定成功。
   **失败必须落盘**：出口非零时，本批运行目录内必须存在**非空**失败记录（不得只改内存、
   不得只写“诊断副本”而让失败记录为空），且坏候选字节保留。
2. **一次完整有界确认**：对**完整集合**（登记、Gate1 材料、决定记录、标准化产物、数据库、装载报告、
   Gate2 请求，以及本轮证据台账）逐项做原始字节确认；期望取自**初始同缓冲**或**本次 writer 已绑定**的
   长度/SHA，**不从候选文件重建期望**。
3. **失败支配出口**：任一确认失败、任一真实审核失败、任一阻断，都必须支配**真实公开出口**的
   非零返回、失败状态与非空失败记录；不得只写入诊断文件或只在内存标记失败。
4. **失败元数据落盘**：失败时在**新运行输出目录**写入失败元数据与诊断，保留被判坏的候选字节；
   **不重建台账消除漂移、不自动恢复被改字节、不刷新期望**。
5. **避免自指**：台账**不内嵌自身 SHA**；需要时把自身哈希另存读回诊断或交接消息。
6. **契约拒绝与运行失败分开**：协议/前提拒绝（Blocked）与 I/O、运行失败（Error）分开并保留
   cause/context，不互相伪装。
7. **不声明超出能力**：本地哈希不承诺抵御同权限的全面重写；身份声明非强认证，如实标注。

---

## 8. Gate2 材料白名单（批准前已经可得，不含筛查）

**允许纳入（拟定）**：

1. 本批共享运行登记（六项）与其登记文件身份；
2. 有效 Gate1 APPROVE 的记录身份与核验结果；
3. 来源批次封套与质量报告（含结构/质量/勾稽结论原文）；
4. 标准化产物（文件 SHA + 记录内对象指纹 + 规范版本）；
5. SQLite 数据库文件 SHA 与装载核验报告原文（含 `DEV_SQLITE_VERIFIED` 状态、表行数、金额与勾稽核对项）；
6. 必要的失败诊断/锁定状态**如实存在性声明**（若存在则阻断，不作为材料优点）。

**明确排除**：筛查结果、规则命中、复算结果、事实底稿、初判、AI 建议、终判。
Gate2 请求**不得**以“筛查为空/零线索”作为前置或结论。

**依赖方向**：Gate2 材料**不依赖**筛查；筛查在 Gate2 之后运行。
因此本设计不存在“筛查结果作为 Gate2 前置”的依赖环。

**实读要求**：Gate2 候审必须**实读数据库文件与对应报告**并核对（文件 SHA、报告字段、表行数与金额），
不以内存声明替代。

---

## 9. 冻结核心复用限制（只读实读确认）

### 9.1 SQLite 核心（`scripts/store_demo_sqlite.py`，`1abfad89…8e18`）

- 入口：`load_normalized_to_sqlite(normalized: dict, database_path) -> dict`。
- **路径规则**：`resolve_database_path` 要求目标位于 `data/sqlite_tests` **之内**、
  不能是该目录本身、**目标必须尚不存在**、**其父目录必须已存在**。越界/已存在/父目录缺失均抛 `SqliteLoadBlocked`。
- **本设计处置**：新运行层在该**既有允许范围**内使用**独立新子目录**
  `data/sqlite_tests/[候选名] runtime_<batch_id>/`，数据库文件名为候选名（如 `runtime.sqlite`）；
  该子目录由新运行层在装载前创建（不修改核心、不扩大核心路径权限）。
- **前提**：`require_loadable` 要求 `normalization_version == "TASK-004-normalized-1.1"`、
  `mode == "DEVELOPMENT_TEST_ONLY"`、`next_step_allowed is False`、`quality_report` 结构合规等。
  新运行层必须提供满足这些要求的标准化对象；**不得**为通过前提而改写核心状态常量或标记。
- **成功报告**：返回 JSON 含 `batch_status = "DEV_SQLITE_VERIFIED"`（[已存在] `EXPECTED_LOAD_STATUS`）、
  `store_version`、`schema_version`、`database_path`、`database_sha256`、`staging_sha256`、
  `normalized_payload_sha256`、`normalization_version`、`source` 等（形状见现行 `load_report.json`）。
  新运行层以**新建封套**关联该报告，不改核心字段语义。
- **失败语义**：提交前失败→数据事务已回滚；**提交后失败（含关闭失败）→ 不声称已回滚**，
  如实说明暂存库已含提交数据与目标文件是否存在。新运行层不得把两类混称“回滚”。
- **开发标记**：核心的 `DEVELOPMENT_TEST_ONLY` / `DEV_*` 原始标记**如实保留**；
  新运行层须另行说明其复用与边界，**不得**改标签冒充身份认证或职业审计保证。

### 9.2 标准化核心（`scripts/normalize_demo_data.py`，`a2bae49e…3686`）

- 入口：`normalize_workbook(workbook_path: Path, quality_report: dict) -> dict`。
- **前提**（`_require_convertible`，只读实读）：`quality_report` 通过
  `receiver.validate_report`；`result == "pass"`；`issues` 为空列表；
  `workbook.sha256` 与当前输入文件 SHA 相等；`checker.sha256` 与冻结 checker SHA 相等；
  `reconciliation.status == "ASSESSED"` 且 `known_plus_missing` 等关系成立。
  不满足 → `NormalizationBlocked`（**不转换、不产出标准数据**）。
- **运行错误** → `NormalizationError`（输入不存在/非 `.xlsx`、列位置不一致、转换后哈希变化等）。
- 输出为 JSON 可序列化字典，含 `normalization_version = "TASK-004-normalized-1.1"`、
  `mode`、`next_step_allowed`、`quality_report` 与四表标准数据；**不写回工作簿、不创建批次、不代签批准**。

---

## 10. 分阶段实施切分与停止点

| 阶段 | 范围 | 交付 | 停止点 |
| --- | --- | --- | --- |
| 阶段一（后续另卡） | [候选] 运行登记 + **新版本 Gate1 请求/保存接线（§5.1）** + 有效批准实读核验 + 标准化/入库接线 + **Gate2 材料请求** | 新运行层脚本 + 运行输出目录 + **Gate1 决定记录（写独立记录根）** + SQLite 新子目录 | **停在 Gate2 候审**：**禁止**保存 Gate2 决定与运行筛查；运行登记与 Gate1 决定记录**必须**产生 |
| 阶段二（另行授权） | Gate2 决定保存与规则执行 | 另行设计 | 需人类显式批准当批动作 |
| 阶段三（另行授权） | 筛查/复算/事实底稿 | 沿用冻结核心 | 需单独任务卡 |
| 阶段四（另行授权） | 真实初判保存 | 另行设计 | D3 粒度已定；AI 仍不开放 |
| 未开放 | AI 建议、终判 | — | 无单独授权不启动 |

---

## 11. 只读核验记录与身份来源

### 11.1 本轮核验脚本与记录

- 脚本：`data/human_gate_runtime_design_checks/task025r1_run_01/runtime_design_checks_r1.py`（只读）。
- 记录：同目录 `design_checks_r1.json`、`frozen_identity_r1.json`。
- 覆盖：字段闭合（登记/两个请求/核验返回）、摘要可推导（唯一配方复算）、冻结接口数量限制实读、
  新保存路径与三类目录角色、**合法已登记人类字段**（`HUMAN_DECLARED` + 夹具原文）、阶段/目录一致、
  依赖无环、候选标记。
- **TASK-025-R2 新增**（同一类只读核验，针对 R2 三项残余）：
  - `data/reviews/task025_r2_gpt_20261015_020841/runtime_baseline_corrected.json`
    （完整书面基样，`84cdd60347ffccd8afbeccdce1372c572a1da7ab1a4a1ac97571fa1f71504a84`）；
  - 同目录 `build_baseline_fixture.py`（基样生成器，只读参考值 + 纯内存计算）；
  - 同目录 `verify_baseline_r2.py` 与 `design_checks_r2.json`
    （**直接读取该 JSON**核对：可解析、键集与冻结 AST 常量一致、摘要全串合法、
    名单排序/唯一/计数、`expected_files` 双向相等、材料正文复算一致、两 Gate `run_binding` 相等而材料摘要不同）。
- 历史记录（只读引用，不重跑）：`data/human_gate_runtime_design_checks/task025_run_01/design_checks.json`
  是 TASK-025 首轮的 25 项自检、`task025r1_run_01/design_checks_r1.json` 是 R1 的 36 项自检；
  按评审结论，它们**不等于**新协议合法性证明，本卡另行给出上面的针对性核验（R2 共 54 项）。

### 11.2 冻结身份（本轮只读实读）

| 对象 | SHA-256 | 字节 |
| --- | --- | --- |
| `tests/test_record_demo_human_gate1.py`（TASK-024 最终验收测试） | `fc38b82c694564bdc511573173d3d6ee9caf3aa7c421d7d95e4a0788cbdc87ff` | 236681 |
| `scripts/record_demo_human_gate1.py`（Gate1 生产适配器） | `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9` | 85064 |
| `scripts/prepare_demo_human_gate1.py`（冻结准备器，不在 21 项冻结登记内） | `ce23671f4c19d60808f90755d4c8575b1b8ad018bfc7e0f3bcebee3b06de0ac4` | 56069 |
| `scripts/store_demo_human_gate_decision.py` | `594e42d0cf8b…` | — |
| `scripts/normalize_demo_data.py` | `a2bae49e3686…` | — |
| `scripts/store_demo_sqlite.py` | `1abfad898e18…` | — |
| `scripts/control_demo_workflow.py` | `a6b7b8e18249…` | — |
| `docs/AUDIT_CONTRACT.md`（正式契约 V1） | `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad` | 13289 |
| `config/human_flow_v1.json` | `ae4caa38a4f029cf1eb8ccb023176712da5ad9cd969afe907d3d54fdfaedfb7c` | 219 |
| `sql/demo_schema.sql` | `7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205` | 4091 |
| `sql/rules/r01.sql`…`r04.sql` | `7a19ff2f…` / `58af03e6…` / `8a4b84d9…` / `b60e4db0…` | 2825/2245/2148/2195 |
| 批次输入工作簿（夹具 `C06b.xlsx`，本设计引用其字节身份） | `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341` | 7177 |

完整 64 位值与全部 21 项冻结登记见同目录 `frozen_identity.json`；本节只列关键项，避免手抄错误。

### 11.3 冻结登记的逐项复核

**[已存在]** `scripts/prepare_demo_human_gate1.py` 的 `FROZEN_PROJECT_SHA` 共 **21 项**；
本轮逐项实读复核 **21/21 一致**（见 `design_checks.json` 的 `frozen_registry_recheck`）。
`CODE_FILES` 另列 13 项；它与这 21 项名单交叉但不互相包含，全部代码仍须逐项实读。

---

## 12. 本设计的自检清单（供评审定点核对）

1. 是否明确“候选名当前不存在”，且未创建任何占位文件/占位 SHA；
2. 共享运行绑定六项是否各有**唯一来源**与**精确算法**；
3. 是否明确 Gate1/Gate2 `run_binding` 逐字段相等、而阶段材料集与摘要**不要求相等**；
4. 是否明确文件 SHA 与对象规范指纹是两类值且不互相替代；
5. 是否明确 Gate1 新旧版本边界与“旧事件只读保留”；
6. 是否明确 Gate2 材料白名单且**排除筛查**，并给出无环性结构论证；
7. 是否明确“最后成功提交点”在一次完整有界确认之后；
8. 是否明确失败支配真实公开出口、失败元数据落盘、坏候选保留；
9. 是否明确核心复用限制（SQLite 允许范围、标准化前提、开发标记保留）；
10. 是否明确固定停止点（阶段一最多到 Gate2 候审，且区分“本卡不产生”与“阶段一必须产生”）；
11. 是否选定**唯一**接线（新版本 Gate1 请求/保存入口，旧入口原样），并说明冻结 14/32 项限制的归属；
12. 是否给出登记/两个请求/核验返回的**封闭键 + 类型 + 常量 + 来源**与**唯一摘要公式**（无 `<原文>`、无“可含可不含”）；
13. 是否给出**实读入口有据可取**（哪些路径、哪些固定文件），而非只信调用方内存对象；
14. 是否把运行输出 / 独立 Gate1 记录根 / SQLite 新子目录**三类角色**分开列清；
15. 保存是否**只调用一次** store 且**显式传** `prior_history`（空历史也实际枚举成三键对象），
    且**没有**独立的 P1 预调用；
16. `save` 是否**自己重新实读**登记与当前批次来源做独立预期比较（不接受调用方旧对象/自报状态）；
17. 物理归属是否固定为**一个** `scripts/runtime_gate1.py`（13 冻结项 + 1 = 14 项；材料 32 项），
    且**不保留** `13+N` 任选分支；
18. `boundaries` 是否为七键严格 false 的**对象**、生产请求是否**不含**固定 `outer_label`、
    `context/receipt` 与 snapshots 六文件的**写入方**是否分清。

配对案例见 `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md`。


## GPT 定点校正登记（2026-10-15，A 类）

DSH R2 的原始基样、自检脚本/54 项结果与回执原样保留。GPT 只同步已定六键 schema、prepare 返回包装解包、
同一次登记清单/配置/技术 scope 的引用关系，重新计算受影响摘要；未改人类字段、冻结实现或业务范围。
本正文当前引用的修正版及实际独立复核见 `docs/reviews/REVIEW_TASK_025_R2.md`；旧54项自检没有覆盖这些残余，不能作修正版通过证据。
