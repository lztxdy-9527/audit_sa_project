# TASK-027-R1 执行回执：Gate1 保存与核验闭合、复用可信测试收尾

日期：2026-10-15。任务卡 `docs/tasks/TASK-027-R1_DRAFT.md`（B 类：DSH 执行、GPT 验收）。
依据 `docs/reviews/REVIEW_TASK_027.md`（TASK-027 **NOT_ACCEPTED**）。这是原范围修正：
不建立新 Gate、不改契约、不改变动作许可、不推进 TASK-028。

## 1. 起点核对（只读实读）

| 对象 | 起点（卡内） | 实读 |
| --- | --- | --- |
| `scripts/runtime_gate1.py` | `e44743f9…d0371` / 98928 | 一致 |
| `tests/test_runtime_gate1_decision.py` | `5a1cb9e1…d5152` / 58236 | 一致 |
| `docs/RUNTIME_GATE1_DECISION_GUIDE.md` | `052d107f…e3340` / 9702 | 一致 |
| 新保护基线 | `data/reviews/task027_gpt_20261015_161614/source_hashes_after.json` | 存在、只读引用 |
| TASK-026 GPT 测试/指南 | `24ce783c…8ca2`、`01644cb1…bd94` | 未改动 |

## 2. 交付物

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py`（修改，补丁版本 `TASK-027-runtime-gate1-1.1`） | 110116 | `1d48ebdc1764561ff3893a703d41bfb4241e21efa4140bbe35f487e11e93013b` |
| `tests/test_runtime_gate1_decision.py`（修改） | 81062 | `6e325787236fa0680eed5a2032decf3b93c489fa372425d7ec73364fae65e1e6` |
| `docs/RUNTIME_GATE1_DECISION_GUIDE.md`（追加 §8） | 14182 | `9a6ff309686d87c26e354000063a1fe8d72f8659dd11fa3c2489364691aa8df8` |
| `docs/EXEC_REPORT_027_R1.md`（本回执） | 见交接消息 | 最终 SHA 见交接消息（避免自指） |
| `data/runtime_gate1_decision_tests/task027r1_run_04/`、`task027r1_ctrl2_{none,candidate-return,drop-call,checks-drift}/` | — | 见扫描与 §5 |
| 本轮其余现场：`task027r1_run_01..03`、`task027r1_control_*`、`task027r1_ctrl2_*`、`data/batches|runtime/task027r1_*`、记录根 `…gate1/task027r1_*_scope_*` | — | 保留为历史现场，逐条确切路径登记 |

## 3. 四组阻断的修正与最小反例

### B1 本次 store 输出绑定与最终集合

- 实现：调 store 前新增 `pre_store_recheck`；store 返回后新增 `_bind_store_snapshots`
  （manifest 字节 SHA ↔ 本次真实返回 → 封闭清单 → 五 payload 实际长度/SHA → 五对象与两键
  `decision_result` 与本次 submission/materials/expectations/显式空历史/返回指纹/批次 canonical 闭合）；
  末端确认补批次顶层 + 四固定子目录 + 登记叶恰二文件 + 无 failure。
- 反例实测（均为独立新 scope）：**6.1/6.2** 真实 store 返回后给 `snapshots/submission.json` 追加 LF
  → 本次 save 阻断并留五键诊断，随后只读 verify 拒绝；**6.3** 同一位置给登记叶新增 `failure.json`
  → 本次 save 阻断（登记叶 failure 探针与事件诊断均保留）；**6.4** 调用前末次来源变更
  → 本次拒绝、事件未建、**store 增量 0、P1 增量 0**。

### B2 封套形状、来源关系与写后错误

- 实现：封套**先验形状再消费**；`context.source_batch_relative`/`runtime_relative`/
  `registry_file_sha256` 与显式路径、实读登记、receipt 闭合；`context.store_result` 与本次
  `store.verify` 除 `status` 外稳定字段完整 canonical 闭合；`_write_exclusive` 把真实 writer 的
  非 OSError 异常映射为 `RuntimeGate1Error(stage)`；失败现场按 `event_path.is_dir()` 实际判断；
  主错误与解锁次错误都保留。
- 反例实测：**6.5** `boundaries=[]`（外层 SHA 同步）→ 可定位 `Blocked: context.boundaries`，
  无原生异常；**6.6** 三个来源字段各在独立可解析副本 + 外层 SHA 同步后仍定位拒绝；
  **6.7** `context.store_result.record_fingerprint` 矛盾（外层 SHA 同步）→
  `Blocked: store_verify.stable_fields`；**6.8** 真实 receipt writer **完整写入后**抛
  `ReviewReceiptSentinel` → 本层 `RuntimeGate1Error(write.receipt)`、原因链含 sentinel、
  `receipt.json` 坏候选保留、实际已有事件写出五键 `failure.json`；**6.9** 该事件只读 verify 拒绝
  且不写诊断。

### B3 锁身份与失败传播

- 实现：新增 `_path_identity`；取得时记录锁目录与锁文件身份与内容；释放前核对路径 reparse、
  集合、目录身份、锁文件身份与内容；只回收身份未变的自建目录；主/次错误都保留。
- 控制实测（**6.10/6.11**）：本轮新技术锁取得后，将原锁具名保全到本轮新根
  `data/runtime/task027r1_run_04/preserved_lock_b3`，于原路径建立**内容相同、身份不同**的替代锁
  （`st_ino` 不同）；真实 `_release_own_lock` 返回非空错误并**保留替代锁与保全锁两处现场**。
  正常自锁仍可释放（正常场景成功路径无锁残留）。

### B4 测试终审（移植已验收收尾原则）

- 定稿内存观察为独立预期、审核期间不刷新；磁盘 `expected_observations.json` 仅候选；
  审核为“独立预期 ↔ 磁盘候选”逐条 canonical 比较 + ID/条目/检查双向一致（缺失与多余都报）；
  台账由**本次待写缓冲**给出（含终审诊断缓冲）；末期有界字节确认。
- 观察：活动 `call_id` 在真实调用**之前**登记、嵌套记录绑定**当前**父调用（检查 5.4）；
  P1 通过 `store.load_frozen_p1_core()` 接在**实际使用**的核心模块上完整观察；
  单一 profile 按**代码对象身份**分列闭合（检查 5.2）：direct prepare 54 / save 内部 prepare 22 /
  冻结 prepare 76 / store.save 19 / store.verify 5 / P1 23，**不混加后强求总数相等**；
  禁止名单改为真实公开入口函数名，命中 **0**（检查 5.3）。
- 删除原测试移除探针的动作：unknown/failure 坏场景改为**独立新 scope**并保留现场。
- `--replay` 源只读且必须另给**从未存在**的新 out-dir（旧控制目录再次使用被正确拒绝，
  即该约束生效的旁证）。

## 4. 本轮实测

- `task027r1_run_04`：**80 项检查 0 失败**，顶层 **0/PASS/空 failures**，`problems=[]`、`drift=[]`
  （summary `59765076…` 之外的最终身份见交接消息）。覆盖正常 APPROVE 保存+只读核验、
  HOLD/REJECT 对照、BLOCKED+APPROVE 真实 P1 拒绝、错绑定/错 scope/第二事件/外来锁/未知项/failure/
  正文改写+外层摘要同步/来源晚变更/context 半写/receipt 写后漂移，以及 §3 的 B1/B2/B3 反例。
- 四个 closure-only 控制（各用从未存在的新目录）：`none` → **0/PASS**；`candidate-return`
  → **1/FAIL**（`api_records_mismatch:call_001`）；`drop-call` → **1/FAIL**
  （`api_count_mismatch`、`api_records_missing:call_091`）；`checks-drift` → **1/FAIL**
  （`drift:checks.json`）。四次复用的源目录字节全程未变（`src_unchanged=True`）。

## 5. 真实执行 / 注入 / 旧证据读取 / 未执行

- **真实执行**：冻结接收器 CLI 两轮×1 次（normal 0 / blocked 1）；真实公开 API 调用 91 次
  （build 26 / prepare 47 / read 1 / save 26 / verify 13）；冻结 store.save 19、store.verify 5、
  冻结 prepare 76、P1 23 次完整观察记录。
- **映射注入**（全部为受控测试接缝，注入后保留现场）：store 返回后改快照 1 次；store 返回后
  登记叶新增 failure 1 次；prepare 返回后改本轮来源字节 1 次（随后按原始字节还原以维持本轮批次可用）；
  context 真实独占句柄半写 1 次；receipt 写后追加字节 1 次；**真实 receipt writer 写后抛 sentinel 1 次**；
  context 篡改（boundaries/三来源字段/store_result）4 次；锁身份控制 1 次（含 1 次本轮自建锁的
  非递归具名保全重命名，源目录与目标均在本轮根内、目标从未存在）。
- **读取但未重跑**：`data/reviews/task027_gpt_20261015_161614/`（评审、基线、探针记录）、
  TASK-026 GPT 测试/指南、TASK-025 案例夹具与 §0.1 人类字段、139 项损失登记与 27 项恢复记录。
- **未执行（null + 原因）**：未跑 P1/store 历史大套件与 writer/loader 大组（本卡只要求定点覆盖）；
  未重跑 TASK-021—026 历史入口与原 54 项全套（评审明确不要求）；未重新征求 D1/D2/D3；
  未调用标准化/SQLite/Gate2/宿主/初判/AI/终判，未生成 0009，未新增 CLI；
  `subprocess_internal_counts=null`（子进程内部入口计数不在本进程观察范围）。

## 6. 对旧声明的更正（不回写旧回执）

1. 旧回执称“唯一删除动作是经身份核对释放本次自建技术锁”——**不准确**：原测试还在批准 scope 内
   删除了 `unknown_extra.txt` 与 `failure.json` 两个探针文件（属本轮新建探针的范围偏离）。
   本轮已取消该行为，坏场景改为独立新 scope 并保留；不追认、不要求重建已删除文件。
2. 旧回执称“receipt 完整写后 sentinel”——**实际是读回后追加 LF**，不能作为原卡该分支的证据。
   本轮分列：真实 writer 完整写后抛异常（6.8）与读回后字节漂移（既有 4.4）两个独立场景。
3. 旧回执的收尾通过范围**过宽**：旧审核可接受被替换的观察、缺失记录与部分字节漂移。
   本轮已按 TASK-026 已验收原则重做，并补四个 closure-only 控制，使失败/漂移实际支配顶层 1、
   磁盘 FAIL 与非空 failures。

## 7. 保护与收尾

- 一次最终全树扫描：当前基线内无新增 missing、无范围外变化、无范围外新增、无读取错误；
  **`historical_known_loss = 139` 单列**（不重建、不抹零）；27 项恢复文件与旧 R5 越界 326 项逐项保留；
  新增按**确切路径**登记（无目录前缀豁免）。扫描文件与摘要身份见交接消息。
- 本轮未对任何探针目标做递归删除、移动或清理；唯一删除是经身份/内容核对的本次自建技术锁释放；
  唯一重命名为本卡明确授权的锁身份控制（本轮自建锁、两路径均在本轮根内、目标从未存在）。

## 8. 边界与待裁决

真实批准 `null`；宿主开发态 `0008`；`next_step_allowed=false`、`ai_enabled=false`；
正式契约、生效登记与 TASK-026 交付未改。`effective=true` 只说明该记录在当前材料下满足 Gate1 前提，
**不构成执行许可**。待 GPT 技术验收；不推进 TASK-028。
