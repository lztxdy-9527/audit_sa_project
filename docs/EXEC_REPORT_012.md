# TASK-012 执行回执（保存 Gate2 模拟决定，恢复状态后停住）

任务：新增 `record_simulated_gate2_decision` 与 CLI `record-simulated-gate2-decision`，在合法 `0003 / DEV_GATE2_PENDING` 批次上保存**一次**显式 Gate2 模拟决定（`APPROVE`／`HOLD`／`REJECT`），独占写 `0004.json`，并由新进程 `status` 恢复状态后停住。
日期：2026-10-11。执行端：DeepSeek。
依据：`docs/tasks/TASK-012_DRAFT.md`、`docs/reviews/REVIEW_TASK_011_R2.md`。
状态：完成并自检通过（最终容器退出 0、8 组全 PASS、failures 空），**停在决定后的状态**；未执行筛查／复算／底稿／AI，未建立契约、未签真实 Gate、未保存人类判断、未推进 TASK-013。

---

## 1. 交付物与产物

| 类型 | 路径 | SHA-256 |
| --- | --- | --- |
| 宿主（改，版本 → **TASK-012-workflow-host-1.0**） | `scripts/run_demo_workflow.py` | `0e1a95dfe7c65dad9c5c54cb043fbe3dc7756632f2f3962bfab6df55f29b0e76` |
| 指南（改） | `docs/WORKFLOW_HOST_GUIDE.md` | `2396be82cae2e19378367c16fe21faacaf9ac8c84e05b179e2fb7ecd3c992fdb` |
| 新验证入口（新增） | `tests/test_record_demo_gate2_decision.py` | `84dfac91c66c8ad33b9a2441a4c72ba6b1ab022f02744f0ac1d6b816e0877c7b` |
| 本回执（新增） | `docs/EXEC_REPORT_012.md` | 见文件本身 |

**三条新产物路径**（供复验）：

| 项目 | 路径 | 规模 |
| --- | --- | --- |
| 测试容器 | `data\workflow_host_tests\task012_final_04` | 211 文件 / 1 目录 |
| 批次父目录 | `data\batches\task012_final_04` | 261 文件 / 118 目录；**10 份 `0003`、9 份 `0004`、0 份 `0005`**、2 份 `workflow/gate2/failure.json` |
| 外置开发数据库 | `data\sqlite_tests\workflow_gate2\task012_final_04` | 10 文件 / 11 目录（各批次 `audit.sqlite3`） |

过程现场保留：`task012_01`～`task012_10`、`task012_smoke` 及其对应批次与数据库目录（未回写、未删除）。

## 2. 命令与结果

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "compile(open(r'...\scripts\run_demo_workflow.py',encoding='utf-8').read(),'x','exec'); compile(open(r'...\tests\test_record_demo_gate2_decision.py',encoding='utf-8').read(),'x','exec'); print('compile OK')"   # 0
& $py -B 'D:\harness work\audit_sa_project\tests\test_record_demo_gate2_decision.py' --out-dir 'D:\harness work\audit_sa_project\data\workflow_host_tests\task012_final_04'   # 0
```

八组全部 PASS、failures 为空：`G1_MAIN_FULL_FLOW`、`G2_STOP_STATES_AND_MISSING_LINK`、`G3_REJECTION_SURFACE`、`G4_DECISION_LOCK_AND_LEGACY`、`G5_CHECKPOINT_TAMPERING`、`G6_WRITER_AND_POST_WRITE_ERROR`、`G7_BOUNDED_TAIL_CHANGES`、`G8_GUARDS_AND_COUNTS`；另有 `INTEGRITY_protected_files`（13 个受保护文件前后一致）与 `TASK012_FINAL_READBACK`（最终对象一次落盘并读回一致）。

## 3. 三种决定与重启恢复（真实独立进程 + 真实 API）

| 批次 | 决定 | phase | `NORMALIZE_AND_LOAD` | `SCREEN_AND_BUILD_FACTS` | 真实批准 | `next_step_allowed` | 决定总数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `main_01`（MAIN，20/993/1000/1005） | Gate2 `APPROVE` | `DEV_GATE2_APPROVED` | `false` | **`true`** | `null`／`null` | `false` | 2 |
| `c02_hold` | Gate2 `HOLD` | `DEV_GATE2_HELD` | `false` | `false` | `null`／`null` | `false` | 2 |
| `c02_reject` | Gate2 `REJECT` | `DEV_GATE2_REJECTED` | `false` | `false` | `null`／`null` | `false` | 2 |
| `c07b_missing` | Gate2 `APPROVE` | `DEV_GATE2_APPROVED` | `false` | `true` | `null`／`null` | `false` | 2 |

- MAIN 全流程各步独立进程：`start` → `status`(pending) → `record-simulated-decision`(Gate1 `APPROVE`) → `prepare-gate2` → `record-simulated-gate2-decision` → `status`（新进程恢复 `DEV_GATE2_APPROVED`）。
- MAIN 真实核对值（本次实测，未硬编码为批准条件）：行数 **20/993/1000/1005**；已结算付款主表 **267949329** 分；退款 **700000** 分；资金净额 **267249329** = 已知关联 **266249329** + 缺失关联 **1000000**；`round_trip_exact=true`、`foreign_key_check=clean`、`integrity_check=ok`。
- C07b 合法未匹配关联批次：`missing_payable_link_net=200000`（非零）仍可模拟 `APPROVE`，未改判为质量问题；MAIN 金额未用作通过条件。
- 决定调用前后：`0001`／`0002`／`0003` 字节哈希相等、Gate2 三份产物与数据库字节相等（`checkpoints_unchanged=true`、`materials_unchanged=true`）；`0004.previous_file_sha256` 等于**初始实读**的 `0003` 字节哈希。

## 4. 本卡探针（目标命中，均同时核验类别与具体原因）

| 探针 | 结果 |
| --- | --- |
| **G3 早期/停止态/失败准备拒绝** | Gate1 pending、Gate1 APPROVED 未 prepare、Gate1 HOLD 均按早期阶段阻断；字段用例（`gate`／`request_id`／`materials_sha256`／AI 身份／`simulation=REAL`／缺 `reason`／确认项 `false`／确认项数字 `1`／重复 `event_id`）各命中目标字段，且未写 `0004`／`0005`，基准批次仍是 `DEV_GATE2_PENDING` |
| **G3 上游失败两项** | 包装真实上游（先真实调用再抛）：`NormalizationError` → `WorkflowHostError`＋`failure.json`＋无 `0003`＋恢复 exit 2（命中 1）；`SqliteLoadError` → 同上，且重复 `prepare-gate2` 按现场阻断（命中 1） |
| **G4 决定锁定** | 三种决定后重复／冲突提交（CLI 与 API）、Gate1 再提交、`prepare-gate2` 再执行全部拒绝；四份 checkpoint 字节不变、无 `0005`；旧纯接收批次拒绝 |
| **G5 `0004` 篡改（9 项＋副本对照）** | 错前序、操作摘要决定、`phase_after`、`operation.kind`、`decision_sha256`、`revision`、数据库字节、装载报告字节、未知 `0005` 各命中目标字段；每项**即时恢复原位**并复核恢复后 `status` 重新通过；另加路径派生不一致的副本现场必须拒绝（`artifacts.json.database_path`） |
| **G6 真实 writer** | `0004` 部分写入：打开／写入／抛错各 **1**、部分 **40** 字节 < 完整 **14221566** UTF-8 字节、`__cause__=OSError(sentinel)`、旧 `0001`—`0003` 字节不变、后续 `status` 拒绝；另做**完整 `0004` 写后抛错**对照：原命令失败但 `0004` 已落盘，独立新进程 `status` 按磁盘事实恢复 `DEV_GATE2_APPROVED`（**不宣称原命令成功**） |
| **G7 有界收尾变化** | 决定纯重放返回时改 `0004` 字节 → **本次即拒绝**（`WorkflowHostBlocked`，指向 `0004.json`），恢复后重新通过；写后重放时改 `load_report` 字节 → 本次即拒绝且改动保留时恢复也拒绝，恢复原位后重新通过；未变化正向不误拒 |
| **G8 只读与静态守卫** | `status` 进程内调用：子进程 0、标准化 0、装载 0、网络 0，批次树与数据库字节前后一致；AST 化检查：导入仅标准库、上游模块句柄恰为 `CONTROLLER_MODULE`／`NORMALIZER_MODULE`／`STORE_MODULE`、未导入或调用筛查／复算／底稿／生成器；仅一个 `subprocess.run` 调用点（冻结接收器） |
| **隔离自测** | matcher 自测（类别+目标原因相符→通过、类别正确原因不符→**判失败**、类别不符→失败）与计数自测（内存副本去掉一条调用记录→判不一致）均通过，单列于 `self_tests.json`，未向正式 failures 塞假失败 |

## 5. 计数（本轮实际留痕导出，未照抄旧次数）

| 分项 | 值 |
| --- | --- |
| CLI 子进程 | `start` **14**／`status` **33**／`record-simulated-decision` **14**／`prepare-gate2` **9**／`record-simulated-gate2-decision` **13** |
| 公开宿主 API（含经 `status` helper 进入的 `inspect_dev_batch`） | **21** |
| 测试侧私有探针调用（直接 `_run_receiver`） | **0** |
| 控制器造样（测试直接调用） | **0**；宿主内部控制器重放（进程内可观测）**113**；CLI 子进程内重放 **null（未观测）** |
| 真实接收 | **14**（宿主 14 ＋ 直接 0，逐条 `receive_invocation.json` 去重）／checker **14**（各接收身份 `checker_invocation.started`） |
| 进程内真实标准化／装载 | **3／2**（含故障探针里抛错前的真实调用）；CLI 子进程内 **null**，按成功 CLI `prepare-gate2` 推导 **8／8** 分列 |
| 副本 | **1**（登记来源；不计真实接收／标准化／装载） |
| 故障注入 | **15**；负向拒绝 **23**；`0004` 决定总数 **9**（与实际 `0004` 文件一致） |
| 模拟决定／**真实批准** | Gate2 决定 9 ＋ Gate1 决定（各批次 1）／**0** |

一一对应审计：`expected_starts` 与实际调用记录无缺失（`missing_records` 为空）；隔离计数自测通过。

## 6. 保护结果

- 主基线 `data/reviews/task011_r2_20261011_150713/source_hashes_after.json`（39831 项）：变化 **2**（本卡授权的宿主与指南）、缺失 **0**。
- 更早基线按各自起点累计：`task011_r1`(34813) 3 项、`task011`(28489) 3 项、`task010`(16340) 3 项（历史授权含旧测试）；`task009_r2`(14691) 及 `13330`／`12546`／`10236`／`8547`／`6511`／`4902`／`874` 全部 **0 变化、0 缺失**。
- 冻结上游逐项未变：控制器 `a6b7b8e1…`、接收器 `52195620…`、checker `a7e5eb67…`、标准化 `a2bae49e…`、装载器 `1abfad89…`、schema `7e0c6463…`、筛查 `1b123766…`、复算 `8fe75bfe…`、底稿 `f4998d92…`、SPEC `5df632ed…`、契约草案 `af405cb6…`；旧入口 `tests/test_run_demo_workflow.py` = `852bf336…`、TASK-011 入口 `tests/test_prepare_demo_gate2.py` = `11d4fe57…` 均未变（未被修改、未被运行）。
- 未安装依赖、未建 Git、未加生产测试开关；四份交付文件 UTF-8 无 BOM；临时补丁脚本已删除、无 `__pycache__` 残留。

## 7. 未执行（不写通过）

筛查／R01—R04、独立复算、事实底稿、AI 建议、正式契约、真实 Gate 批准、人类判断保存、UI、真实 ERP、并发／锁／断电试验、无边界 fuzz、TASK-013；未重跑 TASK-002—011 历史入口（只在新入口内覆盖本卡要求的完整流程与关键回归）。

## 8. 失败尝试与偏离说明

1. **副本无法自洽**：`artifacts.database_path`／`output_relative`／`materials`／`request_id` 都由**批次相对路径**与冻结控制器状态派生，复制批次后重算它们就等于**冒称上游重算**。因此 G5 的 9 项篡改改在**专供探针的真实批次**上造样并**即时恢复原位**（逐项记录恢复前后并复核正向），另保留一项“副本现场必须被拒绝”的对照探针（说明副本为何不能照单接收）。这与卡文“0004 有限副本”的形式不同，但证据更强且不伪造上游结论。
2. **CLI 子进程内的调用不可观测**：`prepare-gate2` 经 CLI 运行时，进程内包装看不到标准化／装载次数（写 `null` 并另列按成功 CLI 推导值），不把推导值冒充真实观测；进程内 API 路径另用 C07b 与故障探针取得真实观测（3／2）。
3. **首次运行的测试缺陷**：`c07b_probes` 未定义、CLI 内计数被误当可观测、副本缺推导数据库、G3 字段探针误落在已有 `0004` 的批次上、G5 恢复判定把“新建文件被删除”写成“必须仍存在”、G8 静态检查把绑定路径常量误报为调用——均已修正为实现缺陷而非放宽断言。
4. **`0004` 已存在的阻断原因**：初版只说“已有第 4 份 checkpoint”，已补上 `workflow/checkpoints/0004.json` 文件路径，便于负向探针精确匹配。

## 9. 停止声明

停在**决定后的状态**（`DEV_GATE2_APPROVED`／`DEV_GATE2_HELD`／`DEV_GATE2_REJECTED`），**不是** Gate2 已放行；未新增筛查／复算／底稿命令，未执行任何下游动作，未建立正式契约，未签真实 Gate，未保存人类判断，未生成 AI 建议，未推进 TASK-013，未宣布项目完成。模拟 `APPROVE` 仅表示冻结控制器声明筛查可行，宿主没有执行筛查的命令。
