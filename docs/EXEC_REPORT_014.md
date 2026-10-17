# TASK-014 执行回执（接入独立复算并保存 0006）

任务：把冻结的独立复算纯核心 `verify_rule_facts` 接入宿主，新增 `crosscheck_dev_batch` API 与 `crosscheck-rules` CLI，完成 crosscheck 四类产物协议与 `0006` 复算凭证；暂不接事实底稿或 AI。
日期：2026-10-12。执行端：DeepSeek。验收端：GPT。
依据：`docs/tasks/TASK-014_DRAFT.md`（唯一权威细则）、`docs/reviews/REVIEW_TASK_013_R4.md`、`docs/RULE_CROSSCHECK_GUIDE.md`、`docs/WORKFLOW_HOST_GUIDE.md`。
状态：完成并自检通过；停在 **`phase=DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED` + `RULE_CROSSCHECK_RECORDED`（0006）**；无 0007，真实批准 0，未执行事实底稿／LLM／网络／人类判断，未建正式契约，未推进 TASK-015。

---

## 1. 结论摘要

| 项 | 结果 |
| --- | --- |
| **真实接入** | `crosscheck_dev_batch(batch_dir)` 与 `crosscheck-rules --batch-dir` 真实调用冻结 `verify_rule_facts(normalized, screening_report)` **恰 1 次**，只传两个内存对象；不传数据库路径、不读答案册、不调用 SQL 筛查或生成器、不回写输入。`CrossCheckBlocked`→阻断（退出 1）、`CrossCheckError`→运行失败（退出 2），保留原因链。 |
| **八步顺序** | 共用恢复核验（要求当前恰为合法 `0005`）→ 控制器 `SCREEN_AND_BUILD_FACTS` 严格 `true` → 同次读取缓冲取对象与字节哈希 + 复算前实读数据库与既有声明一致 + 拒绝已有 `workflow/crosscheck/` → 独占创建目录与 `started.json` → 真实调用核心一次 → 独占保存并读回 `crosscheck_report.json`（逐项严格等于该次返回）→ MATCHED/MISMATCH/异常分开 → 最后一次控制器调用与数据消费后复测全部消费对象、旧 `0001`—`0005` 字节不变。 |
| **MATCHED 口径** | 不只看一个标志：`batch_status=DEV_CROSSCHECK_MATCHED`、`matched is True`、`differences=[]`、十维度齐备且 `executed is True`／`matched is True`／`difference_count` 为严格整数 0，`matched_dimensions`／`unmatched_dimensions` 与实际一致。满足才追加 `0006`。 |
| **0006** | `revision=6`、`kind=RUN_RULE_CROSSCHECK`、`previous_file_sha256` = 操作开始时实读 `0005` 字节哈希；`workflow` 与 `0005.workflow` **严格相等**（无新 history／请求／决定／阶段）；`operation` 绑定 started／report／artifacts 固定相对路径、实际文件字节哈希、报告规范指纹与 artifacts 内嵌完整副本；`artifacts.json` 另绑定批次、宿主／核心版本与核心哈希、运行绑定、宿主清单与 `0005` 哈希、normalized／screening 文件与规范指纹、Gate2 artifacts、固定数据库路径与实测字节哈希、截至日与 Gate2 决定正文指纹。 |
| **MISMATCH** | 核心正常返回：完整报告与全部差异落盘，`failure.json` 记 `result=BLOCKED_CROSSCHECK`／`kind=CROSSCHECK_MISMATCH` 与完整差异，退出 1，**无成功 0006**，不改筛查报告、不删差异、不继续事实底稿；新进程 `status` 同类拒绝（实测退出 1）。 |
| **失败与未完成协议** | 操作开始前的拒绝不创建现场；本次已创建后失败尽力独占保存 `failure.json`（固定版本、`batch_id`、`host_version`、严格整数目标退出码、类别、阶段、完整原因、已知产物引用），写后读回核验；**失败诊断优先于完整 0006**（已接入共用恢复入口），`started` 存在但无成功集合又无可用诊断＝未完成阻断。 |
| **链与恢复** | checkpoint 链扩展到连续 `0001`—`0006`；`0005` 语义仍按自身初始实读哈希核验，筛查摘要始终取 `0005` 自身操作摘要（不误用链尾 `0006`）；`status` 对 `0001`—`0006` 各合法阶段只读恢复，不重新调用复算／筛查／标准化／装载核心，不写文件。 |
| **验证** | 全新容器 `task014_run_02` 退出 **0**、**7/7 检查 PASS、failures=[]**。 |

---

## 2. 修改与新增文件（完整哈希）

| 文件 | SHA-256 | 说明 |
| --- | --- | --- |
| `scripts\run_demo_workflow.py` | `1c12f065cafbf0fb65a2036c51f086dd544b77abffc5aa237cd892950e11d083` | 本卡授权修改（起点 `ae5b7e24…cab4e2`）；实现版本 `TASK-014-workflow-host-1.0` |
| `docs\WORKFLOW_HOST_GUIDE.md` | `44718decb24e1a2319fab722a411100caa7f3a4b9cf33c774bb9a1f8b6034472` | 本卡授权修改（起点 `c7963c58…60cf5`） |
| `tests\test_crosscheck_demo_workflow.py` | `97b89bbc157abeb391a37143e8f87114cf161e73f37ee14f2c89bef823bd9675` | 新增本轮验证入口 |
| `docs\EXEC_REPORT_014.md` | 见交接消息给出的**写后最终哈希**（本文件含本行，哈希不写回自身以免自指；表内其余哈希均为对应文件当前字节哈希） | 本轮回执 |
| `scripts\crosscheck_demo_rules.py` | `8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2` | **冻结未改** |
| `tests\test_screen_demo_workflow.py` | `27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca` | **冻结未改**（TASK-013） |

三条完整产物路径：

- 测试容器 `D:\harness work\audit_sa_project\data\workflow_host_tests\task014_run_02`（192 文件；`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`cli_logs\` 65 份原始 stdout/stderr／`probe_records\` 14 份完整记录）
- 批次父目录 `D:\harness work\audit_sa_project\data\batches\task014_run_02`（282 文件；**8 份 `0006`、0 份 `0007`**）
- 外置数据库父目录 `D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task014_run_02`（11 文件）

过程现场（保留未回写）：`task014_smoke1`（宿主定向冒烟）、`task014_run_01`（测试入口过程现场，G3 差异路径断言修正前）。

---

## 3. 实际命令与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"        # 0
& $py -B -c "src = open(r'...\tests\test_crosscheck_demo_workflow.py', encoding='utf-8').read(); compile(src, 'y', 'exec'); print('compile OK')"  # 0
& $py -B '...\tests\test_crosscheck_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task014_run_02'                                          # 0
```

输出要点：`检查项 7：7 PASS / 0 FAIL`、`测试失败 0；受保护文件完整: True`、`全部预期成立。`

CLI 实际调用（本容器，`counts.json`）：start 11／record-simulated-decision 11／prepare-gate2 11／record-simulated-gate2-decision 11／screen-rules 8／crosscheck-rules 12／status 12。
进程内核心调用：`verify_rule_facts` **1**（G1 捕获真实返回）＋ `screen_sqlite` **1**（G3 造样包装真实核心后取得真实返回）。故障注入 4；MATCHED 批次 1；MISMATCH 批次 1；接收 11；模拟决定 22；**真实批准 0**；副本 0。

---

## 4. 七组有界验证（本轮实测）

### G1 `G1_MAIN_CROSSCHECK_MATCHED`（PASS）

- MAIN 完整建链至 `0005`（筛查 12 条线索、分布 3/5/2/2、R02 超额 1,600,000 分保持）→ 进程内 `host.crosscheck_dev_batch` 真实复算 → `phase=DEV_GATE2_APPROVED`、`crosscheck_status=RULE_CROSSCHECK_RECORDED`、`matched=True`、`next_step_allowed=false`、真实批准 0。
- 冻结核心**恰调用 1 次**；落盘 `crosscheck_report.json` 与该次真实返回**逐项严格相等**（规范指纹比对）；十维度全部 `executed/matched=true`、`difference_count=0`、`differences=[]`；复算计数与筛查分布一致。
- `0006`：`revision=6`、`kind=RUN_RULE_CROSSCHECK`、前序 = `0005` 实际字节哈希、`workflow` 与 `0005` 严格相等；已有 `0006` 时 CLI 再调 `crosscheck-rules` 退出 1 并说明只接受 `0005`。
- 证据：`probe_records\g1_main_crosscheck.json`。

### G2 `G2_SAMPLES_AND_PATH_BOUNDARIES`（PASS）

- C06b（退款／超额）、C03（无线索）、C07b（部分未匹配）三份小样各自：`crosscheck-rules` 退出 0、`DEV_CROSSCHECK_MATCHED`、`differences=[]`、重复复算退出 1、`status` 退出 0 且 `completed_actions` 恰含一次 `RULE_CROSSCHECK`。
- 过早调用：合法 `0004`（尚未筛查）批次退出 1、原因指向 `0005`，且**未创建** `workflow/crosscheck/`（`probe_records\g2a_early_rejection.json`）。
- 停止态对照：`HOLD` 的 `0004` 批次退出 1、未创建现场（`probe_records\g2b_hold_rejection.json`）。
- 证据：`probe_records\g2_{c06b_refund,c03_nohit,c07b_partial}.json`、`g2a_early_rejection.json`、`g2b_hold_rejection.json`。

### G3 `G3_REAL_MISMATCH`（PASS）

- 造样：进程内包装真实 `screen_sqlite`，**先取得真实返回**，再深拷贝只改一处已存在的整数分事实 `findings[0].amounts_cents.paid_total`：`1000000 → 1000001`（R02／AP01），由宿主把该测试报告保存到磁盘；造样来源记录 `probe_records\g3_mismatch_tamper_source.json` 保存真实返回规范指纹与改动点（明确标注为故障造样）。
- 复算**真实接收该磁盘报告**并返回 `DEV_CROSSCHECK_MISMATCH`：`matched=false`、`difference_count=1`、未一致维度 `['amounts_cents']`，差异 `code=AMOUNT_MISMATCH`、`field_path=amounts_cents.paid_total`、`expected=1000000`／`actual=1000001`（逐帧可核对）。
- CLI 退出 1、类别 `WorkflowHostBlocked`、消息含 `BLOCKED_CROSSCHECK`／`DEV_CROSSCHECK_MISMATCH` 与完整报告位置；**无 `0006`**；`failure.json` 记 `result=BLOCKED_CROSSCHECK`、`kind=CROSSCHECK_MISMATCH`、`target_exit_code=1` 与完整差异；新进程 `status` 退出 1（同类拒绝）。
- 证据：`probe_records\g3_real_mismatch.json`。

### G4 `G4_PERSISTENCE_FAULTS`（PASS）

- **半写**：进程内包装真实 `_write_exclusive_json`，`0006` 只写前半段后抛 `OSError` → 公开调用按运行失败收场（`WorkflowHostError`、目标退出码 2），半文件现场保留，`0001`—`0005` 前后字节不变（`old_files_changed=[]`），`failure.json` 已保存且新进程 `status` 拒绝（退出 1）。
- **完整后抛错**：`0006` 完整写入后抛 sentinel `SENTINEL-T14-THROW-0006` → 退出 2、旧文件不变、sentinel 出现在诊断中、新进程 `status` 拒绝（退出 2）。
- 两份记录保存待写完整文本的字节数与 SHA-256、实际命中数、前后哈希、完整异常与诊断：`probe_records\g4_{partial,throw}_persistence.json`。

### G5 `G5_LATE_CHANGE_PROBES`（PASS）

- **晚变更**：在 `status` 内部真实 `_read_crosscheck_outputs` **返回原始对象之后**（`reader_returns=1`、`hits=1`）只改 `crosscheck_report.json` 一次并原样返回 → **本次调用即** `WorkflowHostBlocked`（消息指向该文件），撤销 wrapper、保留变更后新进程 CLI 退出 1，恢复原件后退出 0。用直接 wrapper 记录实际序号，无预读／seek、不靠下一次调用发现。
- **路径反例**：只改 `0006.operation.report_relative` 为不存在路径 → 退出 1 且消息指向该字段与该 `0006.json`；恢复后 `status` 退出 0（不误拒）。
- 证据：`probe_records\g5_late_report_change.json`、`probe_records\g5_path_field_rejection.json`。

### G6 `G6_CHAIN_READONLY_AND_INPUT_INTEGRITY`（PASS）

- 链恰为连续 `0001`—`0006`、无 `0007`；`phase` 仍 `DEV_GATE2_APPROVED`、`crosscheck_status=RULE_CROSSCHECK_RECORDED`；`0006.workflow.state` 两项真实批准均为 `null`、`next_step_allowed=false`、真实批准 0。
- `status` 只读：把 `verify_rule_facts`／`screen_sqlite`／标准化／装载四个下游核心临时替换为「被调用即抛错」后仍退出 0，且批次目录哈希集合前后完全一致（未写文件）。
- 输入不被修改：复算前后 `normalized`／`screening_report` 规范指纹不变；数据库字节与 `crosscheck/artifacts.json` 声明一致。
- 证据：`probe_records\g6_chain_and_readonly.json`。

### G7 `G7_PROTECTED_FILES`（PASS）

- 14 个受保护文件（冻结复核核心、筛查核心、控制器、接收器、checker、标准化、装载、底稿、schema、SPEC、契约草案、三个旧测试含 TASK-013 测试）存在且哈希已记；冻结核心 `8fe75bfe…3ad2`、TASK-013 测试 `27c432db…8eca` 与卡上冻结值一致。
- 证据：`probe_records\g7_protected_files.json`。

---

## 5. 保护比较

相对主基线 `data/reviews/task013_r4_20261012_201824/source_hashes_after.json`（115029 项；文件 SHA-256 `ff3bfc28ed89fceff18e27a871893257a42551a07d9a8e4b655c06dd1c3ed014`）：

- 实扫 116020 个文件（排除 `.venv`）后 **changed 恰为 `scripts\run_demo_workflow.py` 与 `docs\WORKFLOW_HOST_GUIDE.md`（本卡授权的两项）**，**missing = []**，无预期外变化。
- 容器内 G7 另核对 14 个受保护文件；旧回执不回写；未初始化 Git、未装依赖、未清理项目外文件。
- 本轮临时脚本按显式清单删除（`.t14_*.py`），无 `__pycache__` 残留。

---

## 6. 失败尝试与迭代（本轮真修，如实记录）

宿主侧（均由定向冒烟暴露后修正，不是放宽断言）：

1. `screen_expected` 的 Gate2 `artifacts_file_sha256` 与筛查 `artifacts.json` 键名冲突 → 统一加 `gate2_` 前缀（`gate2_normalized/load_report/artifacts/database_*`），`_verify_screen_tail` 兼容两种键名。
2. `_verify_crosscheck_operation` 内把 `paths` 从 Gate2 路径改指 crosscheck 路径后仍读 `paths["database_path"]` → 改用独立的 `gate2_paths`。
3. `_verify_screen_operation` 未回传核验读数（`0006` 依赖它做筛查核验）→ 返回 started／report／artifacts／数据库／normalized／load_report／Gate2 artifacts 读数。
4. `crosscheck_dev_batch` 预检误从 `gate2_expected["database_path"]`（不存在）取路径 → 改为从 `_gate2_paths()` 实读推导。
5. `status` 在链尾为 `0006` 时误取链尾 `operation` 当筛查摘要（`started/report/artifacts` 同名不同物）→ 筛查摘要固定取 `0005` 自身操作摘要，复算收尾预期固定取 `0006` 自身操作摘要。
6. 恢复入口未接复算失败协议 → `_load_host_context` 增加「复算失败诊断优先于完整 0006」与「有 started 无成功集合＝未完成阻断」。
7. MISMATCH 未留诊断导致新进程 `status` 通过 → MISMATCH 分支保存 `failure.json`（`result=BLOCKED_CROSSCHECK`）；失败诊断的 `observed_outputs` 补严格整数目标退出码与类别（读回核验要求）。

测试侧：

8. 首版在**宿主 CLI 子进程**执行筛查造样／writer 故障注入 → 测试进程的补丁不影响子进程，造样与故障均未生效 → 改为**本进程内**调用 `host.screen_dev_batch`／`host.crosscheck_dev_batch`（CLI 子进程仅用于 CLI 行为对照）。
9. G1 首版用 CLI 捕获核心真实返回 → 子进程内补丁不可见；改为进程内 API 捕获真实返回，CLI 作为「已有 0006 时拒绝」对照。
10. 造样目标字段错误（改 `finding["paid_total"]` 而实际在 `amounts_cents` 下）→ 改为按 `amounts_cents` 内已存在的整数字段改一处。
11. G4 半写场景只写半文件未报错 → 宿主按「协议无效 JSON」退出 1；改为半写后抛 `OSError`（运行失败口径、退出 2），并在记录中保留半文件现场。
12. G3 差异字段比对用了带 `findings[0].` 前缀的路径 → 改为比对 `field_path`（`amounts_cents.paid_total`）。
13. MISMATCH 结果标记在宿主消息与测试断言间不一致（`BLOCKED_CROSSCHECK`）→ 宿主消息与失败诊断统一带该标记，测试按同一标记校验。

过程容器 `task014_run_01`（上述第 12 项修正前）保留未回写。

---

## 7. 未执行与边界

- 未执行：事实底稿（`build_demo_fact_packet`）、LLM／网络调用、人类判断保存、正式契约、真实 Gate 批准、UI／真实 ERP／OCR／RAG、并发锁／断电试验、无边界 fuzz、`0007`、TASK-015。
- 未重跑 TASK-002—013 整套历史入口；本卡只要求一次全新容器最终入口（已满足）。`tests/test_screen_demo_workflow.py` 未改未跑（本卡冻结）。
- 边界：本地哈希只证明字节一致；不声称断电持久性、并发锁、身份认证或同权限防篡改。复核一致只表示两套确定性实现的事实核对一致，**不证明来源真实性**，也不构成审计结论。`0006` 是宿主**复算完成凭证**，不是新批准、新阶段或项目完成；`phase` 仍为 `DEV_GATE2_APPROVED`，`gate1_approval`／`gate2_approval` 恒为 `null`，`next_step_allowed=false`，真实批准 0。

---

## 8. 完成前自查（逐项）

- 成功 MATCHED 才有 `0006`：是（G1／G2）。MISMATCH／失败不伪装成功：是（G3 无 `0006` 且留诊断；G4 退出 2 且旧文件不变）。
- 完整 `0006` 后失败仍恢复失败：是（G4 throw：退出 2、`status` 拒绝）。
- `0005` 与 `0006` 各自哈希不混用：是（链核验按各自 `previous_file_sha256`，摘要分别取各自 `operation`）。
- 晚变更本次即拒绝：是（G5）。合法恢复不误拒：是（G5 恢复后 0、G6 只读 0）。旧文件不覆盖：是（G4 与 G6）。
- 无 `0007`、无事实底稿／AI／人类判断／真实批准：是。
