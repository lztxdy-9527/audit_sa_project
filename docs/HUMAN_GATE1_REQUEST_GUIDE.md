# Gate1 只读候审请求适配器指南（TASK-023）

版本：TASK-023（P2 材料来源接入）；日期：2026-10-14。实现：`scripts/prepare_demo_human_gate1.py`；
测试与证据：`tests/test_prepare_demo_human_gate1.py`；固定配置：`config/human_flow_v1.json`。

## 1. 它做什么、不做什么

唯一公开入口：

```python
prepare_human_gate1_request(batch_dir, request_id) -> dict
```

它从 `data/batches/` 下**仅接收阶段**目录实读八份接收材料，核验接收证据与质量报告，产出冻结 P1
协议可直接消费的 `materials` 与独立 `expectations`，并附 `evidence`/`boundaries`，使后续保存不必
相信提交方自报的哈希。

**不做**：不保存/恢复任何快照（不调用存储的 save/verify）、不提交或落盘任何 Gate 决定、不枚举历史记录、
不默认完整空历史、不接宿主/控制器、不执行标准化/装载/筛查、不打开 Excel 重算、不构造真实流程检查点或
`0009`、不处理 Gate2/真实初判/AI/终判、不生成姓名/身份/事件 ID/时间/决定/原因、不产出预填 submission、
不写任何文件（除读取外零副作用）。

## 2. 返回结构与边界

成功外层**恰六键**：

| 键 | 说明 |
| --- | --- |
| `request_version` | 常量 `TASK-023-human-gate1-request-1.0` |
| `status` | 常量 `HUMAN_GATE1_REQUEST_PREPARED` |
| `materials` | 冻结 P1 协议七键对象（`gate=GATE1`、`batch_id`、`run_binding`、`contract_binding`、`files`（恰 31 项）、`quality`、`materials_fingerprint`） |
| `expectations` | 冻结 P1 协议八键对象（`expected_gate=GATE1`、`expected_prior_gate1=null`、`expected_request_id` 为原输入、`expected_files` 为 31 项双向名单） |
| `evidence` | 恰七键：`source_manifest_version`、`source_batch_status`、`source_receive_exit_code`、`source_description`、`source_scope`、`code_manifest`、`rules_manifest` |
| `boundaries` | 恰七项**严格 false**：`request_persisted`、`decision_recorded`、`execution_allowed`、`workflow_connected`、`ai_enabled`、`identity_authenticated`、`source_authenticity_proven` |

返回为深拷贝，调用方改返回不影响保留输入与后续调用。成功可返回**质量 OK 或 BLOCKED** 的候审材料；
`FAILED_RUNTIME`、不完整报告、读数矛盾一律不返回 `PREPARED`。

边界：`status=PREPARED` 或质量 OK **都不是批准**。质量 OK ≠ 批次批准 ≠ 运行放行 ≠ 身份认证 ≠
来源真实性证明；`evidence.source_*` 只搬运接收器原始声明（原文保留），不构成已验证业务事实。

## 3. 异常

| 异常 | 含义 |
| --- | --- |
| `HumanGate1RequestBlocked(field, reason)` | 前提/协议/绑定/路径拒绝（可定位到字段或文件） |
| `HumanGate1RequestError(stage, reason)` | I/O、加载或意外内部错误；`raise ... from exc` 保留原因链 |

不泄漏原生 `AttributeError`/`TypeError`/`KeyError`；不以捕获一切或默认值替代结构检查。

## 4. 来源与路径规则

- 只接受 `data/batches/` 的**严格后代**目录；原始绝对路径逐级（含允许根）检查符号链接/junction/
  reparse，再 `resolve()` 复查；拒绝越界、允许根自身与任何链接。
- 目录条目集合必须**恰为**固定集合推导出的八文件：`batch_manifest.json`、`gate1_packet.md`、
  `source/input.xlsx`、`checks/quality_report.json`、`logs/checker.stdout.txt`、
  `logs/checker.stderr.txt`、`code_snapshot/receive_demo_batch.py`、`code_snapshot/check_demo_data.py`。
  多/少任何条目（含下游产物目录、未知文件或模拟凭证文件）都拒绝；**目录名本身不参与流程身份推断**
  （合法批次名如 `decision_review` 必须通过，下游阶段按实际产物判断）。
- **逐级路径检查（R1）**：八份消费文件、四个固定子目录（`source`/`checks`/`logs`/`code_snapshot`）
  与全部项目侧材料路径，都按**原始路径逐级**（含允许根与所有中间目录）检查符号链接/junction/reparse，
  再 `resolve()` 复查；文件必须是正常文件。只查批次根或叶文件不足以放行——子目录 junction 同样拒绝。
  `lstat`/枚举/`stat`/`resolve` 失败映射为 `HumanGate1RequestError(stage)` 并保留原 cause，
  不把 `OSError` 吞成“无链接”。
- 八份全部只读；生产 API 不启动接收器/checker、不打开 Excel、不导入生成器/答案册/宿主/控制器/下游核心。

## 5. 接收证据核验

八文件各**第一次读缓冲**同时取得字节长度、文件 SHA 与 JSON 对象（先类型检查再消费）。核对要点：

- manifest 版本 `TASK-003-R2-batch-manifest-1.2`、`batch_id` 与叶目录名精确一致、`mode=DEVELOPMENT_ONLY`、
  `contract_status=DRAFT_NOT_IN_FORCE`（接收器原始历史标签，不改写）、严格整数退出码；
  `failure.stage=null`、`exceptions`/`material_write_failures`/`failure_reasons` 为空；
  `report_validation.attempted/valid/report_readable` 严格 true 且 `problems=[]`；
  `snapshot_written`/`snapshot_matches_source` 严格 true；source/snapshot 各 SHA 与实际 input 字节全等、
  `size_bytes` 与实际长度一致；两项 approval 为 null、`next_step_allowed` 严格 false。
- checker：`attempted`/`started` 严格 true；`report`/`stdout_log`/`stderr_log`/`gate1_packet`/`code_snapshot`
  各路径为固定路径、`exists` 严格 true、`read_error=null`、声明 SHA 与本次初始实读字节全等；
  代码快照与项目冻结接收器/checker 字节一致且 `matches_source` 严格 true；
  `report_workbook_sha256`/`report_checker_sha256` 与本次 input/冻结 checker 一致、两个 `matches` 严格 true。
- 质量报告：调用冻结接收器只读 `validate_report(report)` 做结构验证（不执行其 CLI）；
  `workbook.sha256`/`size_bytes` 与本次 input 一致、`workbook.path` 精确指向本次批次快照；`checker.sha256`
  与冻结 checker 一致；四表行数勾稽 `source_rows == accepted_rows + blocked_rows`、类型严格；
  `issue_counts_by_code` 与实际 issues 按 code 统计严格相等（不补零、不筛除）。**不得用两个 null 相等
  代表已核验**；读取只走本卡白名单，不跟随 manifest 中的任意 `original_path`/`argv`。

## 6. 质量映射（只映射 checker 实际 issues，不另加规则）

| 接收状态 | 条件 | P1 质量 |
| --- | --- | --- |
| `READY` | 接收/checker 退出码 0、`result=pass`、`issues=[]`、`issue_counts_by_code={}`、四表 `structural_block` 严格 false 且 `blocked_rows` 严格整数 0 | `OK`，三列表全空 |
| `BLOCKED_QUALITY` | 接收/checker 退出码 1、`result=issues_found`、`issues` 非空 | `BLOCKED`：`MISSING_SHEET`/`REQUIRED_COLUMN_MISSING`/`DUPLICATE_COLUMN_NAME` 入 `structural_blockers`，其余实际 code 入 `quality_blockers`，`verification_failures=[]` |
| `FAILED_RUNTIME`/退出码 2/未知状态/报告不完整/矛盾 | — | **拒绝**，不伪造 FAILED 质量对象 |

每条 issue 保留原对象 canonical JSON，列表项编码为 `issues[<8 位十进制原索引>]:<canonical JSON>`，
按 UTF-8 排序、**不去重丢记录**；索引是事实位置，不是人类事件 ID。本适配器只映射 checker 实际
issues，**不**另加规则、不筛除记录、不计算 R01—R04。

## 7. 固定配置与运行绑定

- `config/human_flow_v1.json` 恰七键：`config_version=TASK-023-synthetic-human-flow-config-1.0`、
  `company`、`period_start`、`period_end`、`cutoff_date`、`currency=CNY`、`synthetic_data=true`；
  R1 起按**严格类型**核对（`synthetic_data` 必须严格布尔 true，整数 `1` 不得冒充，其余键必须为固定字符串），
  canonical JSON + 单 LF；API 实读并严格核对，`file_sha256` 取确切文件字节。**不得**增加 approval/
  执行开关/可覆写路径；生产 API 不接受调用方配置或期望哈希。
- **独立冻结来源闭合（R1）**：全部既有项目材料（13 份代码、四份规则 SQL、`SPEC_V1.md`、
  旧 `AUDIT_CONTRACT_DRAFT.md`、`sql/demo_schema.sql`、正式契约与生效登记）逐项与**独立冻结 SHA**
  比较，不只比较候选的初始/末次读数；接收器声明同样闭合：`hashes.receive_script`/`checker` 的固定
  path、运行前后 SHA 与 `stable_during_run` 必须与冻结项目文件一致；`hashes.spec`/`contract_draft` 的
  path/exists/read_error/SHA 必须与冻结文件一致；`checker_invocation.report_result` 必须与报告实际
  `result` 一致、`report_checker_sha256` 必须与冻结 checker 及报告一致。
- **必需键存在性（R1）**：`gate1_approval`、`gate2_approval`、`failure.stage` 与各消费
  `read_error` 先确认**键存在**再检查 `null`；缺键不得被 `.get(None)` 当作合法凭证。
- `run_binding.code.file_sha256` 为**本适配器单文件**字节 SHA；`manifest_fingerprint` 为 `code_manifest`
  （13 项 UTF-8 升序唯一，只实读不导入）的规范指纹，两值不可互换。`run_binding.rules` 的
  `version=TASK-006-rule-core-1.1`、`manifest_fingerprint` 取 `rules_manifest`（R01—R04 升序）规范指纹。
  `run_binding.config`/`input` 各取对应文件确切字节 SHA。
- `materials.files` 固定 **31 项**：`batch/` 前缀八份接收文件 + `project/` 前缀 13 份代码、`SPEC_V1.md`、
  旧 `AUDIT_CONTRACT_DRAFT.md`、正式 `AUDIT_CONTRACT.md`、生效登记、新配置、`sql/demo_schema.sql`
  与四份规则 SQL；成员三键 `relative`/`file_sha256`/`byte_size`（严格整数、可为 0），按 UTF-8 升序唯一，
  `relative` 只用逻辑名、不存绝对路径。`materials_fingerprint` 仅对**删除顶层自身字段**的正文 canonical
  JSON 计算；`expectations` 八键由本次实际读数与固定请求 ID/契约/运行绑定独立构造，不从 submission、
  调用方材料、status 或候选记录取预期。
- 运行绑定只描述 TASK-023 已实现的准备范围，**不声称**未来组件已存在；未来代码/清单/规则/配置/范围变化
  必须新批次、新请求；不保证未来宿主兼容、不静默更新旧请求。

## 8. 固定消费与最终确认

路径与文件集合 → 31 份同缓冲初始读数 → 结构与来源关系/helper 验证 → 质量映射/契约/运行核验 →
组装完整输出与独立预期 → **全部必要消费后、返回成功前**再实读 31 文件并逐项与初始长度/字节 SHA 比较，
重新确认路径集合与无链接。任何变化本次即拒绝并指向文件；预期**不得**刷新为晚读值。读取/枚举/stat/
helper 失败各明确 `stage` 并保留原因；末次确认的 `OSError` 同样是 `Error`。全程无落盘、无 failure 写入、
源目录不变。

**终审（测试侧证据收尾，R1/R2）**：完整观察预期在全部观察完成后、**首轮终审读取之前**深拷贝定稿；
首轮终审读数必须在**任何后续写入之前**完成实际字节漂移确认（与该次读数逐文件比较），失败时只写
失败元数据（`failures`/`summary`/独立诊断），**不覆盖被改载荷、不重建台账、不把已漂移磁盘重新采为
新期望**；成功路径只写台账，不重写完整观察载荷。

R2 起，冻结 `validate_report` 的**完整真实观察**（每条的完整输入快照与规范指纹、真实完整返回或异常
+ traceback/cause、调用前后输入指纹不变）作为固定测试载荷 `helper_call_records.json` 落盘，并纳入
待写缓冲、文件台账、首轮同缓冲读回、字节漂移确认与 canonical 内容比较（按 `call_id` 定位差异）。
实际收尾登记审核 helper 同时核对：独立入口代码对象观察数、声明 total、`records` 长度、
`registry.helper_call_ids` 与 `record.call_id` 双向唯一集合、每条完整（`result: []` 亦为合法完整结果，
不得用真值判断判缺失）；缺/额外/重复 ID、缺 entry、空壳 entry、声明与实际不符均拒绝。名为
disk 的审核消费首轮 `_audited_read` 得到的**实际候选对象**（内存真实观察与磁盘候选两类来源分列）。

## 9. 使用边界

候审请求只供**后续** Gate1 决定保存使用：保存决定、限定历史范围、宿主接线与 Gate2 分别由后续卡负责，
本组件不推进任何执行或批准。真实批准仍是 `null`、真实初判未保存、宿主停开发态 `0008`、`next=false`、
AI 未开放。
