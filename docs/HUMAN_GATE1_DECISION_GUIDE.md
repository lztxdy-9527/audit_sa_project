# Gate1 决定保存与限定历史核验指南（TASK-024）

版本：TASK-024（C 类，GPT 设计 + DSH 执行）；日期：2026-10-14。
实现：`scripts/record_demo_human_gate1.py`（新层适配器，无 CLI）；测试与证据：
`tests/test_record_demo_human_gate1.py`。

## 1. 它做什么、不做什么

把**已验收的材料准备**（冻结 `prepare_demo_human_gate1.py`）与**冻结快照存储**
（`store_demo_human_gate_decision.py`）连接起来：人类先取得当前 32 项材料请求，再明确提交 Gate1
决定；系统从当前文件重新生成独立预期、实读限定范围（scope）内的既有记录，保存并核验**这一次**提交。

**止于独立 Gate1 记录已保存/可核验**：不改宿主/控制器、不执行标准化/DB/筛查、不接 Gate2、不产生
`0009`/真实初判/AI/终判、不把 `APPROVE` 解释为执行许可。`execution_allowed`/`workflow_connected`/
`ai_enabled` 恒为 `false`。人类姓名/身份声明/事件 ID/时间/决定/原因只能来自 `submission`，程序不生成
或补造。

## 2. 三个公开 API（无 CLI）

| API | 说明 |
| --- | --- |
| `prepare_human_gate1_decision_request(batch_dir, request_id)` | 只读准备：返回**新 32 项材料请求**（六键） |
| `save_human_gate1_decision(batch_dir, request_id, submission, event_dir, *, scope_dir=None)` | 显式限定历史范围并保存（`scope_dir` 缺省/None → 结构化 Blocked） |
| `verify_human_gate1_decision(event_dir, batch_dir, *, scope_dir=None)` | 只读核验已保存记录及当前来源，不能重新批准 |

异常：`HumanGate1DecisionBlocked(field, reason)`（字段/路径/协议/前提拒绝）与
`HumanGate1DecisionError(stage, reason)`（运行/I/O/加载/意外错误，保留 cause/context 链）。下游冻结
prepare/store 的原 field/reason 与原因链原样透传（前缀 `prepare.`/`store.`），不泄漏原生类型。

prepare 返回六键：`request_version=TASK-024-human-gate1-decision-request-1.0`、
`status=HUMAN_GATE1_DECISION_REQUEST_PREPARED`、`materials`（七键）、`expectations`（八键）、
`evidence`（七键）、`boundaries`（沿用冻结准备的**原七项**严格 false）。**不生成 submission**。
`save`/`verify` 成功返回**恰九键**：`adapter_version=TASK-024-human-gate1-adapter-1.0`、
`status` = `HUMAN_GATE1_DECISION_RECORDED` / `..._VERIFIED`、
`scope=LOCAL_GATE1_DECISION_RECORDS_ONLY`、`identity{batch_id,event_id,decision}`、
`record_fingerprint`、`event_dir`/`scope_dir`（项目相对路径）、`store_result`（冻结存储完整八键）、
`boundaries`（六项严格 false）。没有 `approved_for_execution=true` 或 `next=true`。

## 3. 新层代码绑定：32 项材料、14 项代码

每次真实调用冻结 `prepare_human_gate1_request` 一次，只消费其经核验的返回；随后扩展本层副本：
`code_manifest.entries` 加入 `scripts/record_demo_human_gate1.py` 与其文件 SHA（UTF-8 升序唯一，
共 **14** 项）；`materials.files` 加入 `project/scripts/record_demo_human_gate1.py` 的实际长度/SHA
（共 **32** 项，其他 31 项不删改）；`run_binding.code.file_sha256` 指向**本层适配器**实际字节、
`manifest_fingerprint` 取 14 项规范指纹；`rules`/`config`/`input`/`contract` 保持原绑定；
`materials_fingerprint` 用冻结 P1 公开算法复算；八键 `expectations` 全部由本次实际读数重建。
这是**新请求版本**：旧准备器 API/31 项协议冻结不动，旧 31 项请求指纹不得用于保存本层决定。

## 4. scope、事件目录与独占锁

- `scope_dir` 必须由调用方**显式先建立**，且是 `data/human_gate_decision_records/gate1/` 的**严格后代**
  （首次可为空）；`event_dir` 必须是 scope 的**直接子目录**且**从未存在**（含空目录拒绝）。
- 原始绝对路径**逐级**检查符号链接/junction/reparse 再 `resolve()` 复核；文件必须是正常文件；
  不跟随 JSON 中的任意绝对路径。
- 保存期间 scope 内另有独占 `.gate1.lock`（`O_CREAT|O_EXCL`，内容固定
  `{lock_version=TASK-024-gate1-scope-lock-1.0, operation=SAVE}`，无人类时间/事件 ID）。已被占用即
  Blocked（不自动回收、不等候重试、不自动换 scope）；只清理**本次确实独占创建且路径/字节仍匹配**的自锁；
  未建立任何事件现场时（例如 P1 在建立叶目录前拒绝）清理自锁，已留下现场时保留锁由人类决定。
- `verify` 全程不创建/删除锁，存在锁即拒绝。

## 5. 历史：真实枚举、revision 与 prior_history

实读枚举 scope 全部事件目录（未知项/失败/半写/缺 receipt/版本不符**一律阻断不跳过**）；每个事件只用
本层封套与冻结 `store.verify` 核验其六份快照，**不读历史业务源文件**、不把历史 `APPROVE` 当作当前材料
仍有效。完整事件按技术 `revision` **严格 1…N 连续唯一**；每条 `prior_scope.prior_events` 必须精确引用
全部更早 revision 的实际封套/六快照文件（不得漏掉较早 HOLD/REJECT）。P1 `prior_history` =
`{declared_complete: true（仅表示本次实际枚举该 scope）, declared_scope: GATE1_LOCAL_SCOPE:<相对路径>,
records: [wrapper…]}`，wrapper 三键 `{wrapper_version=TASK-020-human-gate-decision-record-wrapper-1.1,
record_fingerprint, record}`，按原 `event_id` UTF-8 排序唯一；空根经实际检查才 `records=[]`。
`prior_history_fingerprint` 为完整历史对象的 canonical 指纹，须与 `snapshots/prior_history.json` 闭合。
保存新提交由冻结 `store.save` 内部 P1 **恰一次**决定；历史核验的每次 `store.verify` P1 复算另计
（本层不先直接调 P1 再让 store 调第二次）。相同 `event_id`、同批次 Gate1 已有 `APPROVE` 均拒绝；
合法 HOLD/REJECT 前序不能一律拒绝。本范围不是全局历史发现/身份认证，不证明其他 scope 无记录。

## 6. 封套

每个成功 `event_dir` 恰为 `context.json`、`receipt.json`、`snapshots/`；`snapshots/` 内仍是冻结存储
**恰六文件**（`decision_result/expectations/manifest/materials/prior_history/submission.json`），
不添加字段/文件、不改 `record.persisted`。

- `context.json` **恰九键**：`context_version=TASK-024-gate1-context-1.0`、`revision`（严格整数 N+1）、
  `event_relative`、`source_batch_relative`、`request`（完整六键新请求）、`prior_scope`、`snapshot_files`、
  `store_result`、`boundaries`。
- `prior_scope` **恰四键**：`scope_relative`、`declared_scope`、`prior_events`、`prior_history_fingerprint`；
  `prior_events` 按 revision 升序，每项恰 `{revision,event_relative,context_file_sha256,
  receipt_file_sha256,snapshot_files}`；`snapshot_files` 恰六项、按文件名升序，成员
  `{relative,byte_size,file_sha256}` 且 `relative` 只能是冻结六文件名。
- `receipt.json` **恰十键**：`receipt_version=TASK-024-gate1-receipt-1.0`、
  `status=HUMAN_GATE1_EVENT_COMPLETE`、`revision`、`context_file_sha256`、
  `snapshot_manifest_file_sha256`、`record_fingerprint`、`batch_id`、`event_id`、`decision`、`boundaries`；
  **最后**独占写、不内嵌自身 SHA。
- 封套与 API 的 `boundaries` **恰六项严格 false**：`execution_allowed`、`workflow_connected`、
  `human_initial_judgment_saved`、`ai_enabled`、`identity_authenticated`、`source_authenticity_proven`。
- `context.store_result.status` 为冻结 `STORED`；公开 `verify` 的 `store_result.status` 为 `VERIFIED`；
  两者各按自身常量校验、**其余七键严格一致**（不要求两状态完整相等，也不任意忽略其他字段）。

## 7. 保存顺序、失败诊断与只读核验

**save 固定顺序**：轻量参数/路径核验 → 独占 scope 锁 → 同缓冲读取并核验历史（保留全部旧文件初始读数）
→ 真实准备 32 项当前请求 → 冻结 `store.save` 到 `event_dir/snapshots` → 核验完整返回与六文件真实读数
→ 独占写 `context.json` 并读回 → **最后**独占写 `receipt.json` 并读回 → 全部必要消费后的最终确认
（32 当前来源、旧事件八文件字节、scope 成员集合、本次八文件与实际待写/读回预期、代码/路径/失败存在性）
→ 释放自锁 → 返回。`store.save` 在 P1 通过前不建目标/父目录，因此错提交/质量 APPROVE 等 P1 拒绝
**不建事件目录**；进入 store 创建阶段后的错误保留现场并只在本事件写独占 `failure.json`。

**失败诊断**恰为协议字段集合 `{failure_version=TASK-024-gate1-failure-1.0, status=BLOCKED|ERROR,
stage, field（无适用值为 null）, reason, exception_chain, boundaries}`（7 项，见卡 §92）；failure 优先于
解析任何半写封套/receipt；写诊断失败保留原错误链、不吞掉失败。晚变更即使已有完整 store/receipt 仍必须
失败，本层 failure 使恢复拒绝，恢复原业务字节不能抹掉已保存失败事实。**verify 不写 failure**、不修复/
迁移历史；当前 32 材料与已保存请求不一致时只读核验拒绝（不得称旧 APPROVE 仍可执行）。

## 8. 使用边界

本层只把“人类明确提交的这一次 Gate1 决定”保存为可核验的独立记录；`RECORDED`/`VERIFIED` 都不是批准、
不是执行许可、不是身份认证或来源真实性证明。真实批准仍为 `null`、宿主停开发态 `0008`、`next=false`、
AI 未开放；Gate2、真实初判、标准化/装载/DB/筛查均属后续卡片。

## 9. 测试与证据

入口：`.venv\Scripts\python.exe -B tests\test_record_demo_human_gate1.py --out-dir
data\human_gate1_decision_tests\task024_<轮次>`。测试的人类字段只来自**登记夹具**（项目权威夹具
`FIXTURE-EV-G1-0001` 与 GPT 登记夹具 `TASK024-G1-HOLD-0002`/`FIXTURE-EV-G1-0002`），外层标
`PROTOCOL_TEST_FIXTURE_ONLY`（不写进 P1 封闭 submission）。证据载荷 `calls/samples/checks/failures/
summary` 在终审前由真实观察定稿、一次性写入、同缓冲读回，登记审核核对总数/case_id 唯一/记录完整；
任一漂移或登记缺失支配返回码（分离故障轮次实测：删一条完整登记 → 返回 1 / FAIL）。
