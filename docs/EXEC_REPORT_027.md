# TASK-027 执行回执：运行层 Gate1 单事件保存与当前有效性核验

日期：2026-10-15。任务卡：`docs/tasks/TASK-027_DRAFT.md`（C 类：GPT 定接线与边界，DSH 执行）。
前置：TASK-026 当前实现经 GPT 修正复验通过（`data/reviews/task026_r3_gpt_20261015_043939/review_result.json`
= `ACCEPTED_CURRENT_IMPLEMENTATION_WITH_RECORDED_EVIDENCE_LOSS`）。**历史证据删除事故与 139 项未恢复损失
继续登记**，不视为原执行合规；本卡不引用这 139 项为现存阳性证据。

## 1. 起点核对（只读实读）

| 对象 | 要求（起点） | 实读 |
| --- | --- | --- |
| `scripts/runtime_gate1.py` | `b7dd3bcafb12b96d944bcedaa27b840de8c4d7e6b99ce69c4a72585f8f4b87ea` / 61205 | 一致 |
| `tests/test_runtime_gate1_registry.py` | GPT 修正版 `24ce783c…8ca2` / 38122 | 一致（本卡未改） |
| `docs/RUNTIME_GATE1_REGISTRY_GUIDE.md` | GPT 修正版 `01644cb1…bd94` / 11744 | 一致（本卡未改） |
| 基线 | `data/reviews/task026_r3_gpt_20261015_043939/`（`review_result.json`、`source_hashes_after.json`、`remaining_loss.json`、`restoration_journal.json`） | 存在、只读引用 |

## 2. 交付物

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py`（修改） | 98928 | `e44743f943cba02d46f45e2be6d0d049e7123a638c197183ad2a83ff24bd0371` |
| `tests/test_runtime_gate1_decision.py`（新增） | 58236 | `5a1cb9e17c355195d094cd98eb95124d3097da840ee86485f6abcdbdac2d5152` |
| `docs/RUNTIME_GATE1_DECISION_GUIDE.md`（新增） | 9702 | `052d107f78b904d5412a27a531c98b3a6d56f6f4bafcb0d90ca8e7126e5e3340` |
| `docs/EXEC_REPORT_027.md`（本回执） | 见交接消息 | 最终 SHA 见交接消息（避免自指反复改写） |
| `data/runtime_gate1_decision_tests/task027_run_04/`、`task027_control_{none,checks,payload,late-checks}/` | — | 见 §5 |
| `data/batches/task027_run_04/`、`data/runtime/task027_run_04/`、`.../gate1/task027_run_04_scope_*` | — | 逐条确切路径见扫描 |
| 开发性冒烟根 `task027_dev_smoke{,3,4}`（批次/运行/记录 scope） | — | 保留为历史现场，不删除 |

## 3. 实现概要（只改 `scripts/runtime_gate1.py`）

- 新增 `save_runtime_gate1_decision(...)`：外层恰三键 `record`（真实冻结 P1 的 17 键正文）/
  `record_fingerprint` / `event_relative`；**单个** Gate1 事件、一次写定。
- 新增 `verify_gate1_effective_approval(...)`：恰十一键（`TASK-025-gate1-effective-approval-1.0`）、
  `actor_kind` 唯一 `HUMAN_DECLARED`；只读、失败不写诊断。
- 共享而非复制：把原 prepare 的材料/预期/证据/边界构造抽为内部 `_materialize_gate1_request`，
  prepare 与 verify 私有分支共用；末端确认抽为 `_finish_prepare(..., enforce_scope_absent=)`，
  **公开三 API 恒为 True**（未放宽既有 scope 前提），verify 私有分支为 False 且要求
  `scope` 恰等于 `registry.scope_ref`、事件恰为该 scope 唯一合法事件。
- 同级技术锁 `<runtime 登记叶>.lock`（`lock.json`）；已存在即拒；只释放本次自建且字节未变者；
  成功路径无残留；不清理他人锁。
- 显式三键空历史；submission 绑定与本次独立预期比较（错绑定不建事件，人类字符串原文保留、不代填）。
- **只调用一次**冻结 `store.save`（其内部自己调用一次 P1，本层不直接预调用 P1）；
  context 十键 / receipt 九键（不含自身 SHA）/ 五键边界全 false / 快照恰六文件 /
  事件恰 context+receipt+snapshots / scope 恰一事件目录；失败五键
  `failure.json`（`TASK-027-runtime-gate1-failure-1.0`）仅在事件已建时写。
- 记录正文 `boundaries` 使用冻结 P1 的**六键**并全部要求严格 false，另显式要求
  `approved_for_execution is false`（不放行执行）。

## 4. 定点验收（54 项检查，0 失败）

- 正常 APPROVE：三键返回、record 17 键、指纹复算、事件/快照固定集合、scope 恰一事件、
  锁无残留、落盘 P1 返回与 save 返回正文相等、context/receipt 形状与全 false 边界、
  显式三键空历史。
- 公开 `read` 在计划 scope 尚不存在的叶上仍成功且恰两键（证明未放宽既有前提）。
- verify：恰十一键、`effective=true`、`reasons=[]`、`decision=APPROVE`、
  `actor_kind=HUMAN_DECLARED`、`run_binding_sha256`/`materials_fingerprint` 与登记一致。
- 重复保存被拒且旧字节不变（同 scope 已有事件）。
- 夹具原文 SHA 核对：0002 `8e3cf567…4fa`、0003 `6c69c75c…3c3`；0001 人类字段逐字符取自
  `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md` §0.1。**测试夹具不构成真实批准。**
- HOLD → 可保存但 `effective=false`、`reasons=["DECISION_NOT_APPROVE"]`；REJECT → `effective=false`。
- BLOCKED 批次 + APPROVE → 真实 P1 拒绝且**无成功事件**。
- 错批次绑定 / 错材料绑定 / 调用方 scope 与登记不符 / 越界 scope 未创建 / 同 scope 第二事件 /
  技术锁存在 / 事件含未知项 / 事件含 failure / 正文被改且外层摘要同步 / 内部矛盾 →
  全部定位拒绝；verify 失败不写诊断，移除探针后恢复成功。
- 真实接缝：来源晚变更（真实 store.save 返回后改本轮来源字节）→ 本次 save 拒绝并留五键诊断；
  `context.json` 真实独占句柄半写 → `RuntimeGate1Error(write.context)` + 诊断 + 坏字节保留；
  receipt 完整写后 sentinel → 末端确认拒绝并保留坏候选。
- 观察：`sys.setprofile` 按真实代码身份计数，公开 API（build 14 / prepare 24 / read 1 /
  save 15 / verify 7）、嵌套冻结 prepare **42**、store.save **9**、store.verify **5**，
  与完整记录数逐项闭合；**禁止下游入口命中 0**（normalize/sqlite/事实底稿/筛查/初判/工作流/控制器）。
- 收尾：写盘前冻结独立完整预期（`expected_observations.json`）；一次写定全部载荷；
  同一 helper 按 canonical 字节逐条比较完整记录（direct/nested/checks）、ID 双向与计数、
  台账 8 份载荷长度/SHA；末期有界字节确认。

## 5. 收尾控制（同一套 finish 代码；`--replay` 复用同一观察副本，业务调用增量 0）

| 控制 | 顶层 | 磁盘 status | failures | 审核问题 / 漂移 |
| --- | --- | --- | --- | --- |
| `none`（正常 task027_run_04 / control_none） | **0** | PASS | 0 | `problems=[]`、`drift=[]` |
| `checks`（写盘后改一项检查结果） | **1** | FAIL | 4 | `check_mismatch:0.1`、`checks_failed_mismatch`、`failures_list_mismatch` |
| `payload`（写盘后改一项完整返回内容） | **1** | FAIL | 1 | `api_record_mismatch:call_001` |
| `late-checks`（末次语义审核返回后追加字节） | **1** | FAIL | 1 | `drift:checks.json` |

失败路径：磁盘 `summary.status=FAIL`、`failures.json` 非空、顶层返回 1，坏候选保留、
不重建期望或台账。

## 6. 本轮真实执行 / 注入 / 旧证据读取 / 未执行

- **真实执行**：冻结接收器 CLI 两轮×2 次（normal 0 / blocked 1）；真实 `build_runtime_registry`
  14 次、`prepare_runtime_gate1_request` 24 次、`read_runtime_registry` 1 次、
  `save_runtime_gate1_decision` 15 次、`verify_gate1_effective_approval` 7 次；
  冻结 `store.save` 9 次、`store.verify` 5 次、嵌套冻结 prepare 42 次（其内部各调用一次 P1）。
- **注入（真实接缝/写盘后注入）**：来源晚变更 1 次；`context.json` 真实独占句柄半写 1 次；
  receipt 写后 sentinel 1 次；`checks`/`payload`/`late-checks` 三个收尾控制各 1 次；
  正文改写+外层摘要同步 1 次；未知项与 failure 现场探针各 1 次（随后移除，仅验证拒绝）。
- **读取旧证据**：TASK-026 R3 评审与事故登记、TASK-025 案例夹具 0002/0003 原文、0001 人类字段
  所在案例文档；均只读，未重跑历史入口、未用新证据覆盖旧位置。
- **未执行**：未调用标准化 / SQLite / Gate2 / 宿主 / 初判 / AI / 终判；未生成 0009；
  未重跑 P1/store 历史大套件与旧 writer 半写入口；未重新征求 D1/D2/D3；
  **未对任何探针目标做递归删除、移动或清理**（唯一删除动作是经身份核对释放本次自建技术锁）。

## 7. 保护与收尾

- 一次最终全树扫描（见交接消息中的扫描身份）：`changed` 恰为 `scripts/runtime_gate1.py`；
  新增按**确切路径逐条**登记（无前缀豁免）；**`historical missing = 139` 单列**（事故遗留，
  不重建、不追认，绝不写 `missing=0`）；当前基线内现存文件不得新增 missing；
  旧 R5 越界 326 项不变；旧 27 项已恢复文件与损失登记冻结。
- 开发性冒烟根 `task027_dev_smoke{,3,4}`（批次/运行/记录 scope，早期轮次因脚本字节变化而失效）
  按确切路径登记，保留为历史现场。

## 8. 边界与待裁决

- 真实批准 `null`；宿主开发态 `0008`；`next_step_allowed=false`、`ai_enabled=false`；
  正式契约与生效登记未修改。
- 待 GPT 裁决：① 保存顺序、锁语义与三键空历史口径；② `effective` 判定与 `reasons` 取值；
  ③ context/receipt 封套与私有只读分支的实现；④ 收尾四控制与证据台账是否满足原卡；
  ⑤ 是否认可开发性冒烟根按历史现场保留。
