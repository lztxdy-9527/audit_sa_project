# TASK-027-R2 执行回执：仅修三个残余收尾问题

日期：2026-10-15。任务卡 `docs/tasks/TASK-027-R2_DRAFT.md`（B 类：DSH 定点实施、GPT 验收）。
依据 `docs/reviews/REVIEW_TASK_027_R1.md`（R1 部分通过、整体未通过）。已关闭项（快照绑定、封套闭合、
receipt 异常映射、正常锁身份、候选替换/缺调用/早期漂移拒绝）保持，未重新派发。

## 1. 起点核对（只读实读）

| 对象 | 起点（卡内） | 实读 |
| --- | --- | --- |
| `scripts/runtime_gate1.py` | `1d48ebdc…013b` / 110116 | 一致 |
| `tests/test_runtime_gate1_decision.py` | `6e325787…5e1e6` / 81062 | 一致 |
| `docs/RUNTIME_GATE1_DECISION_GUIDE.md` | `9a6ff309…a8df8` / 14182 | 一致 |
| 基线 | `data/reviews/task027_r1_gpt_20261015_165854/source_hashes_after.json`（160448 项） | 存在、只读引用；同根 `review_result.json` = `a0161f5bd11eaf5c925b426c8ff28a1e19284ad2012ca2617d3e471f868f81f1` |
| TASK-026 已验收测试/指南 | `24ce783c…8ca2`、`01644cb1…bd94` | 未改动 |

## 2. 交付物

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py`（修改，补丁版本 `TASK-027-runtime-gate1-1.2`） | 111301 | `8b0bec33` 之外的最终身份见交接消息 |
| `tests/test_runtime_gate1_decision.py`（修改） | 91846 | 见交接消息 |
| `docs/RUNTIME_GATE1_DECISION_GUIDE.md`（追加 §9） | 17156 | `73ab1a1275f9bb0fba81ee879b0686c200d5c79a9df9726c95867c26785b54b0` |
| `docs/EXEC_REPORT_027_R2.md`（本回执） | 见交接消息 | 最终 SHA 见交接消息（避免自指） |
| `data/runtime_gate1_decision_tests/task027r2_run_01/`、`task027r2_ctrl_{none,ledger-replaced,diagnostic-drift,candidate-return,drop-call,checks-drift}/` | — | 见扫描与 §5 |
| 本轮运行/记录根：`data/runtime/task027r2_run_01/`、`data/human_gate_decision_records/gate1/task027r2_run_01_scope_*` | — | 逐条确切路径登记 |

本轮**未新增 `data/batches/task027r2_*`**：只读复用 `data/batches/task027r1_run_04/{batch_normal,batch_blocked}`
的既有接收产物与既有登记夹具人类字段，为新版本建立**新的运行登记与事件**（不复用旧运行登记）。

## 3. 三组残余的修正与最小控制

### R2-B1 verify 末次确认的固定集合

实现：verify 在全部材料/结果消费之后的最后有界确认中，新增批次顶层与四固定子目录集合、
登记叶恰二文件、**登记叶无 failure/未知项**（复用既有 helper，未重新实现材料构造，未放宽旧三 API
的计划 scope 前提，verify 仍只读）。

控制 **7.1–7.3** 实测：新正常事件先无注入 verify 成功（`effective=true`）；包装真实
`_finish_prepare`，返回原值后仅在本次新登记叶新增 `failure.json` → 本次 verify
`Blocked: runtime_dir(叶)`；撤销 wrapper 后仍拒绝，未写事件 failure、注入保留未清理。

### R2-B3 失败锁保留与主次错误

实现：取得锁写 `lock.json` 失败**取消自动回收**，保留锁与半写现场并传播
`RuntimeGate1Error("lock", …)`（`Blocked` 原样传播）；次错误以 `release_lock: …` 追加进主错误的
args/`reason` 与 `secondary_errors`，原 field/reason 保留；已有事件的五键诊断在**主次错误已知后一次
独占写定**，不再事后覆写；无事件不造事件；诊断自身再失败保留主次原因与坏候选；有效自锁正常释放不退化。

控制实测：
- **7.4** 真实独占锁句柄**写部分后抛 OSError** → `RuntimeGate1Error(lock …)`，锁目录与半写
  `lock.json` 保留，事件未创建（不自动回收）。
- **7.5** 将该锁文件具名保全到本轮新根（同一新根、目标从未存在），原路径安装**同内容替代文件**后
  再次取得 → `Blocked: lock`，替代文件与保全件均未被删除。
- **7.6** 错批次绑定拒绝前扰动本轮锁内容 → 事件未建；主 `Blocked: submission.batch_id` 保留，
  真实释放次错误经 `secondary_errors` 可见，锁保留。
- **7.7** 已有事件主错误 + 释放次错误 → 五键诊断**恰一次**写入（计数 1），原因链含
  `release_lock`，主原因（登记叶 failure 导致的最终确认 Blocked）可见。
  受控映射与真实 I/O 分列（7.4 为真实句柄半写+OSError；7.6/7.7 为受控映射注入）。

### R2-B4 台账审核与诊断后末次确认

实现：`file_ledger.json` 候选**实读回核**（对象与字节同一次读取），其预期字节来自本次**待写缓冲**，
清单覆盖全部正式载荷含最终诊断（9 项，不内嵌自身 SHA）；正常成功路径先定稿诊断（状态由定稿内存
预期决定），再一次写定诊断与台账；末次实读覆盖正式载荷与台账；之后不再读候选 summary/failures
生成成功输出，改用已核验内存对象。任一审核/字节失败实际支配顶层 1／磁盘 FAIL／非空 failures，
保留坏目标，失败元数据可在失败路径如实落盘但不再报成功。

真实 CLI 控制实测（各自从未存在的新 out-dir，复用同一次观察，源目录只读且 SHA 未变：
`src_unchanged=True`）：

| 控制 | 顶层 | 磁盘 | failures | 定位 |
| --- | --- | --- | --- | --- |
| `none` | **0** | PASS | 0 | problems=[] drift=[] |
| `ledger-replaced`（写后磁盘台账改为 `[]`） | **1** | FAIL | 1 | `ledger_mismatch` |
| `diagnostic-drift`（最后一次诊断 writer 完成后 checks 加 LF） | **1** | FAIL | 1 | `drift:checks.json` |
| `candidate-return` | **1** | FAIL | 1 | `api_records_mismatch:call_001` |
| `drop-call` | **1** | FAIL | 2 | `api_count_mismatch`、`api_records_missing:call_107` |
| `checks-drift` | **1** | FAIL | 1 | `drift:checks.json` |

失败均**不是**由 mutate 标志直接返回，而是由台账/字节/预期审核实际判定；坏字节保留。

## 4. 本轮实测

- `task027r2_run_01`：**91 项检查 0 失败**，顶层 **0/PASS/空 failures**，`problems=[]`、`drift=[]`，
  台账 9 项；含 R1 全部场景（重跑一次同轮业务链）与 R2 新增 7.1–7.7。
- 观察计数（按真实函数与 wrapper 角色分列，不混加）：公开 API `build_runtime_registry` 30 /
  `prepare_runtime_gate1_request` 54 / `read_runtime_registry` 1 /
  `save_runtime_gate1_decision` 31 / `verify_gate1_effective_approval` 16（合计 132 次真实调用）；
  冻结准备模块函数计数 89（**含 save 内部调用，不是公开 API 调用数**），wrapper 调用同为 89；
  其中原始 code 对象计数：来自测试直接调用 64、来自 save 内部 25；
  store.save 21 / store.verify 7 / P1 27；禁止下游入口命中 **0**；`subprocess_internal_counts=null`
  （子进程内部不可见）。

## 5. 实际 API / 真实 I/O / 映射注入 / 只读重放 / 引用旧证据 / 未执行

- **实际 API**：公开五类共 132 次调用（30+54+1+31+16，上列分列）；均经真实 `finish`/CLI 路径。
- **真实 I/O**：接收产物只读复用（本轮 0 次新接收）；真实锁目录/锁文件独占创建与释放、
  真实 receipt/context 独占写、真实冻结 store 写盘（21 次 save、7 次 verify、27 次 P1）。
- **映射注入**（受控测试接缝，保留现场）：R1 既有 12 项（快照 LF、登记叶 failure、调用前来源变更、
  context 半写、receipt 写后追加、真实 receipt writer 抛 sentinel、boundaries/三来源/store_result
  篡改、未知项与 failure 探针、锁身份控制）；R2 新增：登记叶 late failure（7.2）、
  真实锁句柄半写+OSError（7.4）、替代锁安装（7.5）、取得锁写失败、锁内容扰动（7.6/7.7）、
  台账替换与诊断后漂移（CLI 控制）。
- **只读重放**：六个控制均复用 `task027r2_run_01` 的一次观察，源目录全程只读。
- **引用旧证据**：R1/R2 评审与基线、TASK-026 GPT 测试/指南、TASK-025 夹具与 §0.1 人类字段、
  139 项损失登记、27 项恢复记录、R1 三处 smoke 命名偏差现场。
- **未执行（null + 原因）**：未重跑 80 项/原 54 项/TASK-021—026 入口与 receipt/context/store/loader
  大组（卡明确不要求）；未重新接收（只读复用）；未重新征求 D1/D2/D3；未调用标准化/SQLite/Gate2/
  宿主/初判/AI/终判，未生成 0009，未新增 CLI；`subprocess_internal_counts=null`。

## 6. 对 R1 口径的更正（不改旧回执）

1. R1 回执把“收尾通过范围”表述为已完整审核台账与末次确认——**不准确**：R1 未审核磁盘台账，
   且诊断写入后不再做末次确认，诊断后漂移可误报 PASS。本轮已按 §3 R2-B4 实现并给出 CLI 控制。
2. R1 回执 `observed` 中把冻结准备模块的函数计数与公开 API 计数并列，易被读作公开 API 调用数；
   本轮已改名并按 wrapper 角色与原始 code 对象分列（§4），并注明冻结准备模块计数**含** save 内部调用。
3. R1 期间产生三处命名范围偏差新根（`task027_r1_smoke1` 与 R1 早期控制目录等），
   已由评审登记为**非阻断事项**；本轮保留不追认/不重建/不迁移，且本卡不再新建
   `task027_r1_smoke` 类额外根（本轮只用 `task027r2_*` 明示根）。

## 7. 保护与收尾

- 一次最终全树扫描：当前基线内新增 missing = 0、范围外变化 = 0、范围外新增 = 0、读取错误 = 0；
  **`historical_known_loss = 139` 单列**；27 项恢复文件、旧 R5 越界 326 项与 R1 偏差旧文件逐项不变；
  新增按本卡明示根展开为**确切路径**（无目录前缀兜底）。
- 本轮未对任何探针目标做递归删除、移动或清理；唯一删除是经身份/内容核对的本次有效自锁正常释放；
  唯一重命名为本卡明确授权的本轮自建锁文件具名保全（预先核对两解析路径在同一新根、目标从未存在）。

## 8. 边界

真实批准 `null`；宿主开发态 `0008`；`next_step_allowed=false`、`ai_enabled=false`；
正式契约、生效登记与 TASK-026 交付未改；`effective=true` 不构成执行许可。不实施 TASK-028。
