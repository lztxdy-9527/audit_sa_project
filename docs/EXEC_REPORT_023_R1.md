# TASK-023-R1 执行回执（来源闭合、逐级路径和真实终审的定点修正）

任务：按 `docs/tasks/TASK-023-R1.md`（**B 类，DSH 处理**）关闭 `docs/reviews/REVIEW_TASK_023.md` 的四组阻断；
沿用已批准 TASK-023 设计，不改架构或冻结上游。
日期：2026-10-14。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与真实批准：人类主理人。

**范围声明**：本卡**只改** `scripts/prepare_demo_human_gate1.py`、`tests/test_prepare_demo_human_gate1.py`、
`docs/HUMAN_GATE1_REQUEST_GUIDE.md`，只新增 `docs/EXEC_REPORT_023_R1.md`、`data/human_gate1_request_tests/task023r1_*`
与同轮 `data/batches/task023r1_*`。配置与全部上游冻结未改；未接宿主/控制器、未调用存储 save/verify、
未生成真实批准/初判/`0009`、未开放 AI。`PREPARED` 或质量 OK **都不是批准**。

---

## 1. 起点与基线

| 项 | 值（实读） |
| --- | --- |
| 评审结论 | `data/reviews/task023_gpt_20261014_023810/review_result.json` → **NOT_ACCEPTED**（施工起点，不是验收） |
| 基线 | 同目录 `source_hashes_after.json` = `ffba9184f3f297bd6797bf1e510d33a4568f928b1088ea3ca93a3139fef14156`、**140867** 项、两个确切自指元数据排除 |
| adapter（起点 → 写后） | `5e8ed565cc6567b210c65c475ec16a8e2f271da49b4bcb6a745cad6cb329da02`（48689）→ `ce23671f4c19d60808f90755d4c8575b1b8ad018bfc7e0f3bcebee3b06de0ac4`（56069） |
| test（起点 → 写后） | `4e7662f599c665ea3ea43fc6809c2ae25c863c79cdc537ea73efed0ec3c9dcae`（59101）→ `e739df9b55de87ad758333def339cfc3838caae641b1eaf71b63467bf1afa518`（80889） |
| guide（起点 → 写后） | `0230ac8787743f002adbe27dab275d4697b60ab304cce335c06ffca1c3e6458f`（9433）→ 见 §7.1 |
| 冻结配置（未改） | `ae4caa38a4f029cf1eb8ccb023176712da5ad9cd969afe907d3d54fdfaedfb7c`（219） |

## 2. 逐组关闭证据

### B1 来源与独立冻结预期闭合

| 缺口 | 修正 | 实测（公开 API 定位拒绝） |
| --- | --- | --- |
| SPEC/旧 draft/schema 列入清单却未比较 | 新增 `_verify_frozen_project_files`：**全部既有项目材料**（13 代码 + 4 SQL + SPEC + 旧 draft + 正式契约 + 生效登记 + schema）逐项与独立冻结 SHA 比较 | `B1-spec-bytes`/`B1-draft-bytes`/`B1-schema-bytes` → Blocked `docs/SPEC_V1.md` / `docs/AUDIT_CONTRACT_DRAFT.md` / `sql/demo_schema.sql` |
| 接收器声明未与同次读数闭合 | 核对 `hashes.receive_script`/`checker` 的固定 path、`sha256_before_run`/`sha256_at_end`（hex64 且相等）与 `stable_during_run` 严格 true，并须等于冻结项目文件；`hashes.spec`/`contract_draft` 的 path/exists/read_error/SHA；`checker_invocation.report_result` 与报告 `result` 一致、`report_checker_sha256` 等于冻结 checker | `B1-end-sha` → `…receive_script.sha256_at_end`；`B1-checker-stable` → `…checker.stable_during_run`；`B1-report-result` → `checks/quality_report.json.result`（声明与报告矛盾）；`B1-report-checker-sha` → `…report_checker_sha256` |
| 缺键被当作合法 null | 新增 `_require_key`/`_require_present_none`，先确认键存在再查 null（`gate1_approval`/`gate2_approval`/`failure.stage`/各消费 `read_error`） | `B1-missing-approval` → `gate1_approval`（缺失必需字段）；`B1-missing-read-error` → `…report.read_error` |
| `synthetic_data` 宽松相等 | config 逐键按类型核对：布尔键必须**严格布尔**（整数 `1` 拒绝）、其余必须为固定字符串 | `B1-config-strict-bool` → `config/human_flow_v1.json.synthetic_data` |

反例一律通过**受控读缓冲映射**（包装真实 `_read_bytes`，初始与末次使用同一候选）构造，冻结磁盘未改、
其他字段保持合法；正常与合法 BLOCKED 对照保留（`C06b_normal`/`C06b_currency_usd`/`C06b_no_allocations`）。

### B2 逐级路径与 I/O 边界

- 新增 `_check_path_item`：对**原始路径逐级**（含允许根与全部中间目录）检查 link/junction/reparse →
  `resolve()` 复查 → 存在性/类型；应用于八个消费文件、四个固定子目录（`source`/`checks`/`logs`/
  `code_snapshot`）与**全部项目侧材料路径**，并在末次确认时对项目侧 31 路径复测。
- **真实子目录 junction**（本轮新接收样本 `junction_subdir_<round>`）：正常对照先 PREPARED；把 `checks`
  移至本轮新目标后以 `mklink /J` 在原 `checks` 路径建立真实 junction（returncode 0、reparse 成立）→
  公开 `prepare` **Blocked `batch_dir.checks`**，源目录快照与目标 `quality_report.json` 字节**不变**，
  junction 现场保留未改。
- `_is_reparse_point` 的 `lstat` `OSError` 不再吞成 false → `Error("lstat")` + 原 cause；
  `enumerate`/`stat`/`resolve` 同样映射。受控 `os.lstat` 注入一次 OSError → `Error("lstat")`、
  命中 1、原因链含 `OSError`（映射注入，非真实磁盘故障）；既有末次 `final_read` Error 例保留。

### B3 普通 ID 保真

- 删除 `request_id.isprintable()` 限制：只拒非字符串与空/纯空白；不 strip、不改大小写、不强制数字/前缀。
- 删除按批次叶目录名子串推断下游身份的限制；八文件/目录**严格集合**仍拒绝实际未知文件/目录与模拟凭证文件。
- 实测：真实接收器建立的合法批次 `decision_review` + 请求 `"REVIEW\nREQ-001"` → PREPARED 且
  `materials.batch_id == "decision_review"`、`expected_request_id` 原文一致；`"\tREQ-002"` 同样原文通过；
  既有 `[]`/`null`/`7`、64hex 形状、指令样式文本与前导零形态照旧。

### E1 真实终审、登记与观察时点

- 完整观察预期仍在全部观察完成后、**首轮终审读取之前**深拷贝定稿；canonical 字节相等为主判据。
- 收尾流程改为：**待写缓冲审核**（canonical 内容比较 + 实际收尾登记审核 helper，在任何磁盘写入之前）
  → 一次性写入最终载荷 → **首轮终审读数**（同缓冲取对象与 SHA）→ 真实审核 → **任何后续写入之前**
  的字节漂移确认 → 干净路径只写台账、不再重写完整观察载荷。
- 新增 `_final_registry_audit`（**实际收尾使用**的登记审核 helper）：核对 prepare 声明 ID/总数与记录
  双向一致且每条记录含完整输入与结果、P1 声明与实际入口代码帧观察闭合、helper 声明与实际 helper
  调用数一致。隔离自测 `_registry_isolation` 只删审核副本一条权威登记，**调用同一 helper** 判定失败、
  原件通过（不再手写 IDs 比较充当真实审核）。
- `project_snapshot_before` 移到 API 调用**之前**实读，调用后另测并核对；计数中
  `clean_calls=36` / `deliberate_change_calls=1` 分列，`clean_calls_files_unchanged=true`、
  `project_files_unchanged_all_calls=true`（不再把故意注入计入不变范围）。
- prepare 与冻结 `validate_report` 实际调用分列：`helper_records` 观察真实函数（入参类型/指纹、返回
  problems、异常），本轮正常入口 helper 调用 **14** 次，未包装宿主 API 冒充 helper 次数。

### E2 快照真正有界

- `_dir_snapshot` 重写为：只登记路径/存在性与**有限首层**观察（条目名受 `SNAPSHOT_ENTRY_BUDGET=24`
  约束，`__recursive_hash_used__=false`）；**绝不 rglob/递归哈希**；仅当路径是**合法接收批次**
  （`data/batches` 严格后代 + 目录项集合恰为固定布局）时按**已知八路径**逐文件记录字节/SHA。
- 隔离对照：`data/`（首层 17 项，少于预算）→ `__mode__="bounded_first_level_only"`、无任何非 `__` 键、
  未读取历史内容；合法批次 → `__mode__="legal_batch_fixed_paths"` 且恰 8 项文件记录。

## 3. 实际运行与计数

```text
.venv\Scripts\python.exe -B tests\test_prepare_demo_human_gate1.py \
    --out-dir data\human_gate1_request_tests\task023r1_run_01
→ TASK-023-R1 测试组：70 项检查，0 项失败；prepare 调用 37、真实 P1 调用 3、
   接收器运行 7、helper 调用 14
→ 退出码 0
```

| 作用域 | 实测 |
| --- | --- |
| prepare 调用 | **37**（含 12 个新反例/对照；clean 36 / deliberate_change 1） |
| 真实冻结 P1 调用 | **3**（= 入口代码帧观察 3，闭合） |
| 冻结接收器 CLI 真实运行 | **7**（3 主样本 + 晚变更 + 计数反例 + 子目录 junction + `decision_review`） |
| helper（只读 `validate_report`） | **14**（分列登记，含完整入参指纹与返回） |
| 生产 prepare 的 P1/存储调用 | **0** |
| 写文件/网络/子进程守卫 | **0** |
| 台账 | **12 项**逐文件实读一致；`content_compare.ok=true`、`registry_audit.ok=true` |

## 4. 分离轮次的真实终审故障

`data/human_gate1_request_tests/task023r1_fault_01/final_audit_fault.py` → 套件运行到
`task023r1_fault_02/`：包装真实 `_audited_read`，在**首轮**真实读回返回原缓冲之后仅给 `checks.json`
追加一个 LF（prepare/写入分支/审核分支均未替换）。实测：

| 项 | 值 |
| --- | --- |
| 套件返回码 / summary / failures | **1 / FAIL / 非空** |
| 注入 | 命中 **1**；`checks.json` 字节变化并**保留**（最终 SHA == 注入后 SHA） |
| 漂移确认 | 检出 `checks.json`（`byte_drift`） |
| 覆盖行为 | **未**覆盖被改文件；只写 `failures.json`/`summary.json`/`final_audit_diagnostic.json`（已在诊断中列明） |
| harness 断言 | 6/6 全真（`ok=true`） |

## 5. 过程问题与未执行（如实登记）

1. 本轮局部运行两次失败后定点修正：`audit_failed` 初版误把“普通检查失败”也当作终审失败而走了失败分支
   （已改为只由内容/登记/漂移决定）；`B1-report-result` 的期望字段过窄（实际定位
   `checks/quality_report.json.result`，已按实际定位登记）。过程容器 `task023r1_dev_01`/`dev_02` 保留。
2. 回执身份更正（按要求只在新回执说明、**不改旧回执**）：TASK-023 回执交接为 12890 字节/`7b29f7ad…`，
   实际实读 **13438 字节 / `fb01538fadfcc93949a188a5a5f83c548cab17137835edd60208b81c8554e44a`**（评审与本节一致）。
3. 未执行：宿主/控制器接线与调用、存储 save/verify、标准化/装载/DB/筛查链、Gate2、真实初判、`0009`、
   AI/终判、网络/UI/ERP、强身份认证、真实批次批准、历史枚举、R01—R04 计算、子进程内部未知函数次数（`null`）；
   未重跑 TASK-021/022 套件或宿主/历史入口；未新增 Gate2/DB 链；未删除/迁移任何旧现场或 junction。
4. 未发现需扩大到配置/冻结上游/P1 schema/31 材料/允许根/Gate 时序/历史/执行边界的事项。

## 6. 保护（定稿后一次全树比较）

- 基线：`data/reviews/task023_gpt_20261014_023810/source_hashes_after.json`
  （`ffba9184…4156`、**140867** 项、NOT_ACCEPTED）；仅两个确切自指路径排除，`prefix_exemption_used=false`。

### 6.1 结果与最终身份

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **141407** |
| `changed` | **恰为本卡修改的三项**：adapter `ce23671f4c19d60808f90755d4c8575b1b8ad018bfc7e0f3bcebee3b06de0ac4`、test `e739df9b55de87ad758333def339cfc3838caae641b1eaf71b63467bf1afa518`、guide `025b2241a8e6d5ab0347b6993f80a09ef47937c5ef407477305414d713cd007f` |
| `missing` / 读取错误 / 范围外变化 / 范围外新增 | **0 / 0 / 0 / 0** |
| 新增登记 | **540** 项：本回执 + 本轮五个 `task023r1_*` 证据/故障容器 + 四个 `task023r1_*` 批次根（逐确切路径登记，`prefix_exemption_used=false`） |
| 冻结身份 | 配置 `ae4caa38…fb7c`、P1、存储、接收器、checker、宿主、控制器、正式契约、生效登记**全部一致**（`mismatch=[]`） |
| 扫描后动作 | 仅有限登记本回执与 guide 身份（本节与 §7.1）；**未再改实现/测试**、未重复全树扫描；旧现场与 junction 保留未删除 |

## 7. 交付文件（写后实读）

| 文件 | SHA-256 | 字节 |
| --- | --- | --- |
| `scripts\prepare_demo_human_gate1.py` | `ce23671f4c19d60808f90755d4c8575b1b8ad018bfc7e0f3bcebee3b06de0ac4` | 56069 |
| `tests\test_prepare_demo_human_gate1.py` | `e739df9b55de87ad758333def339cfc3838caae641b1eaf71b63467bf1afa518` | 80889 |
| `docs\HUMAN_GATE1_REQUEST_GUIDE.md` | `025b2241a8e6d5ab0347b6993f80a09ef47937c5ef407477305414d713cd007f` | 11629 |
| `docs\EXEC_REPORT_023_R1.md` | 自身最终 SHA **只在交接消息给出** | — |

### 7.1 保护扫描登记（扫描后仅登记身份）

| 项 | 值 |
| --- | --- |
| guide 写后 SHA | `025b2241a8e6d5ab0347b6993f80a09ef47937c5ef407477305414d713cd007f`（11629） |
| 实扫 / changed / 缺失 / 读取错误 / 范围外新增 | **141407 / 恰三项（adapter+test+guide）/ 0 / 0 / 0** |

## 8. 绝对路径

- `D:\harness work\audit_sa_project\scripts\prepare_demo_human_gate1.py`
- `D:\harness work\audit_sa_project\tests\test_prepare_demo_human_gate1.py`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE1_REQUEST_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_023_R1.md`
- `D:\harness work\audit_sa_project\data\human_gate1_request_tests\task023r1_run_01\`
- `D:\harness work\audit_sa_project\data\batches\task023r1_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate1_request_tests\task023r1_fault_01\`

## 9. 停止点

完成本卡后执行端停止实施并交 GPT 验收；**不推进 TASK-024 或任何 Gate 接线**；不生成真实批准、初判或
`0009`，不开放 AI。人类操作看板并作出业务决定，技术验收不能代签。若发现需扩大到配置/冻结上游/
P1 schema/31 材料/允许根/Gate 时序/历史/执行边界，**立即停止受影响处理、保留现场并报告重新定界升级**。
