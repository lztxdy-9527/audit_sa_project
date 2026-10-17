# TASK-014-R1 执行回执（修正复算恢复收尾与验收证据）

任务：按唯一权威细则 `docs/tasks/TASK-014-R1.md` 修正 TASK-014 验收不通过的四项阻断 B1—B4（依据 `docs/reviews/REVIEW_TASK_014.md`）。
日期：2026-10-12。执行端：DeepSeek。验收端：GPT。
状态：B1—B4 全部关闭并有实测证据；一次全新容器最终入口退出 **0**、**10/10 检查 PASS、failures=[]**；停在 `phase=DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED` + `RULE_CROSSCHECK_RECORDED`（`0006`），无 `0007`、真实批准 `null`、`next_step_allowed=false`；未接事实底稿／AI／人类判断／正式契约／真实 Gate／TASK-015。

---

## 1. 三项起点与写后哈希

| 文件 | 起点 SHA-256 | 写后 SHA-256 |
| --- | --- | --- |
| `scripts\run_demo_workflow.py` | `1c12f065…d083` | `8cf41ca8da12c77f5fc2a9827c936971aeeafd93a963746cc778a9c1d72031f7` |
| `docs\WORKFLOW_HOST_GUIDE.md` | `44718dec…4472` | `322c333a21b73719edee7d74814e422d5ea88bd16bf834244bb7d95ec37fb2ad` |
| `tests\test_crosscheck_demo_workflow.py` | `97b89bbc…9675` | `54f71aeaa49e7dfe2bde5abd8810266f5cc0656dceb8fc409855587441316f18` |
| `docs\EXEC_REPORT_014_R1.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

冻结未改：`scripts/crosscheck_demo_rules.py` = `8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2`；`tests/test_screen_demo_workflow.py` = `27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca`。原 `EXEC_REPORT_014.md`、`docs/reviews/REVIEW_TASK_014.md`、原任务卡与全部历史产物未回写。

---

## 2. B1：真正最后一次摘要消费之后复测（关闭）

**实现**：`inspect_dev_batch` 在最后一次复算输出读取（摘要、报告规范指纹、内嵌 artifacts 比较）与最后一次控制器动作检查之后、`return` 成功之前，新增收尾块，按**初始同缓冲读取或本次真实 writer 返回**给出的预期复测：

- `crosscheck/` 三份产物的磁盘字节（`report`／`started`／`artifacts`）、报告文件字节哈希与报告对象规范指纹；
- `artifacts` 与 `0006` 内嵌副本严格相等；成功批次不得出现 `crosscheck/failure.json`；
- 筛查产物与数据库字节、宿主清单、静态绑定（`_recheck_static_bindings`）与链上全部 `0001`—`0006` 字节。

不重跑核心、不做预读／seek、不新增 I/O 观察框架。

**实测（`probe_records/b1_late_final_reader.json`）**：

- 未注入的合法调用实测读取顺序：第 1 次 `_read_crosscheck_outputs` 来自 `_verify_crosscheck_operation`（链核验），第 2 次来自 `inspect_dev_batch` 摘要读取；**第 2 次之后存在收尾磁盘复测**（`tail_checks_after_last_read=1`）。
- 只在第 2 次（= 最后一次用于摘要）读取完整返回原始对象之后单次改 `workflow/crosscheck/crosscheck_report.json`（唯一变更路径），wrapper 原样返回（注入前记录返回对象规范指纹）。
- 结果：本次 API `WorkflowHostBlocked`，消息指向 `workflow/crosscheck/crosscheck_report.json`，`期望 5fbdf837…` vs `实际 7eb17a74…`；撤销 wrapper 并保留变更 → 新进程 CLI 退出 **1**；仅恢复原件 → 退出 **0**，目录哈希集合恢复一致。

---

## 3. B2：失败诊断优先与真实 writer 故障（关闭）

**实现**：

- `_load_host_context` 把 Gate2／筛查／复算三类失败诊断的读取与核验**移到解析 checkpoint 链之前**，半写或损坏的 `0006` 不再以协议解析错误遮蔽有效失败诊断；诊断本身仍按固定版本、必需键与严格类型核验（协议非法诊断仍退出 1）；缺失／未知 checkpoint／非法失败记录不会降级为 READY，运行绑定核验仍执行。
- `_map_upstream_exception(exc, stage=...)` 由调用方给出阶段；复算通用处理器传 `stage="crosscheck"`，不再出现 `prepare_gate2`。
- 失败诊断新增 `exception_chain`（逐环 `class`／`message`／`stage`／`reasons`，覆盖 `__cause__`／`__context__`）并在读回时核验非空与形状；复算诊断的 `stage` 必须属于 `crosscheck` 阶段。失败诊断自身保存失败仍如实按运行失败返回。

**实测（`probe_records/b2_partial_persistence.json`、`b2_throw_persistence.json`）**：

| 场景 | 真实 writer 故障 | 现场 | 新进程 `status` | 诊断 |
| --- | --- | --- | --- | --- |
| 半写 I/O | `0006` 写入 38222／76445 字节后抛 `OSError`（真实 `_write_exclusive_json` 路径） | 半文件保留 | **退出 2**，`exception_class=WorkflowHostError` | `target_exit_code=2`、`stage=crosscheck`、`exception_chain=[OSError]` |
| 完整后 sentinel | `0006` 完整写入（76445 字节）后抛 `RuntimeError: SENTINEL-T14R1-THROW-0006` | sentinel 留在诊断内 | **退出 2**，`exception_class=WorkflowHostError` | `target_exit_code=2`、`stage=crosscheck`、`exception_chain=[RuntimeError]` |

两场景均：`0001`—`0005` 字节前后不变、writer 实际命中 1 次、待写完整 UTF-8 文本单份保存并给出字节数与 SHA-256（`core_returns/b2_*_pending_0006.json`）。MISMATCH 仍退出 1（见 §5 G3）；协议非法诊断退出 1（`b4_started_fingerprint_tampered` 同口径）。

---

## 4. B3：证据与计数（关闭）

- **G6 观察有效**：四个下游函数用宿主真实存在的名称（`verify_rule_facts`／`screen_sqlite`／`normalize_workbook`／`load_normalized_to_sqlite`），在**同一进程**内替换为「被调用即抛错」，随后直接调用公开 `inspect_dev_batch` → 返回成功、四个补丁命中计数全为 0、批次目录哈希集合前后一致（`probe_records/g6_chain_readonly_and_input.json`）；另保留普通 CLI `status` 恢复对照（退出 0）。
- **G1 完整真实返回**：冻结核心本次完整返回单份保存 `core_returns/main_01_verify_rule_facts_return.json`，与落盘 `crosscheck_report.json` **严格 JSON 相等**；两个输入完整对象已有文件，以相对路径与字节哈希引用；输入对象指纹为**调用前快照 vs 调用后快照**（复算不修改输入）。
- **调用记录**：本轮 CLI 记录 **76** 条、公开 API 记录 **6** 条，各含完整 `command`／`cwd`／`exit_code`／期望码／stdout 与 stderr 路径及哈希／返回对象单份文件（API 另含完整异常与异常链单份文件）。`call_registry.json` 为权威登记表，`evidence_ledger.json` 为文件台账；审计含 `missing_records=0`、`unregistered_records=0` 并要求每条调用都登记进权威表。
- **receiver／checker 双向对应**：`start` 11 次均为真实接收子进程（记录含实际 command 与退出码，原文在 `cli_logs/`）；checker 调用 0（本卡不调用 checker）。
- **分列与 null**：筛查入口（`screen-rules` 8）与复算入口（`crosscheck-rules` 11）分列；进程内观测复算核心 1 次、筛查核心 1 次；**CLI 子进程内部核心次数不可观测 → 记 `null`**，未把推导值冒充实测。
- **计数含义分开**：`matched_crosscheck_reports=4`（G1＋G2 三小样）、`mismatch_crosscheck_reports=1`、`crosscheck_success_vouchers_0006=4`、`crosscheck_failure_scenes=3`、`fault_injections=5`、`simulated_decisions=22`、`receiver_starts=11`、`real_approvals=0`、`copies=0`。
- **隔离自测**：只从审核副本 `isolation/evidence_ledger_minus_one.json` 去掉一条登记（`cli:b1_chain_start`／`stdout_path`）即失败（`调用未登记进权威登记表：cli:b1_chain_start`），真实日志、登记表与历史容器未改动。
- **G7 真实保护比较**：单次扫描 117196 文件复用两组基线（见 §6），预期外变化为空；G7 的 PASS 由比较结果（changed／missing／unexpected）约束，不再只检查文件存在。
- **指南/回执只描述实际测量**；原回执中「65 份 CLI 原文」等错误说明由本回执更正，原件保留。

---

## 5. 最终入口实测（`data\workflow_host_tests\task014r1_run_03`）

```powershell
$py='D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src=open(r'...\scripts\run_demo_workflow.py',encoding='utf-8').read();compile(src,'x','exec');print('compile OK')"                     # 0
& $py -B -c "src=open(r'...\tests\test_crosscheck_demo_workflow.py',encoding='utf-8').read();compile(src,'y','exec');print('compile OK')"           # 0
& $py -B '...\tests\test_crosscheck_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task014r1_run_03'                                     # 0
```

输出要点：`检查项 10：10 PASS / 0 FAIL`、`CLI 记录 76 条 / API 记录 6 条；missing=0 unregistered=0`、`全部预期成立。`

| 检查 | 结果 | 关键实测 |
| --- | --- | --- |
| B1 最后一次读取后变更 | PASS | 注入于第 2 次返回；本次即阻断；撤销 1／恢复 0 |
| B2 失败诊断优先 | PASS | 半写与 sentinel 均恢复退出 2、`stage=crosscheck`；旧 checkpoint 不变 |
| B4 同缓冲与 started 指纹 | PASS | started 含两项对象指纹；篡改后恢复退出 1、还原 0 |
| G1 MAIN | PASS | 12 条 3/5/2/2、R02 1,600,000 分、一次 MATCHED、十维度全 0、`0006` 与 `0005` workflow 严格相等 |
| G2 小样与边界 | PASS | C06b／C03／C07b MATCHED＋重复拒绝；过早与 HOLD 拒绝且不建现场 |
| G3 真实 MISMATCH | PASS | 造样 `paid_total 1000000→1000001`；差异 `AMOUNT_MISMATCH` 落在 `amounts_cents.paid_total`；退出 1、无 `0006`、新进程 status 退出 1 |
| G5 路径反例 | PASS | 只改 `0006.operation.report_relative` → 字段阻断；恢复后 0 |
| G6 链与只读 | PASS | 连续 `0001`—`0006`、无 `0007`、同进程只读命中 0、目录哈希不变 |
| G7 保护比较 | PASS | 两组基线均 missing 0／unexpected 0 |
| 记录审计与隔离 | PASS | missing 0、unregistered 0、缺一条登记即失败 |

---

## 6. 保护比较（单次扫描复用两组）

单次扫描 117196 个文件（排除 `.venv`／`.git`），结果存 `probe_records/g7_protected_comparison.json` 与 `protected_scan.json`：

| 基线 | 条目 | changed | missing | unexpected |
| --- | --- | --- | --- | --- |
| R1 `data/reviews/task014_gpt_20261012_213445/source_hashes_after.json`（sha `…`） | 116059 | `docs/WORKFLOW_HOST_GUIDE.md`、`scripts/run_demo_workflow.py`、`tests/test_crosscheck_demo_workflow.py` | 0 | 0 |
| 原主基线 `data/reviews/task013_r4_20261012_201824/source_hashes_after.json` | 115029 | `docs/WORKFLOW_HOST_GUIDE.md`、`scripts/run_demo_workflow.py` | 0 | 0 |

两组比较的 changed 均**恰为本卡授权的三项／两项既有文件**，无预期外变化；`docs/reviews/REVIEW_TASK_014.md`、`docs/tasks/TASK-014-R1.md` 与全部历史产物保留。基线键为 Windows 反斜杠形式，比较前归一为 POSIX 分隔符（R1 首轮曾因未归一闪报全量缺失，已修正并记录于 §7）。

---

## 7. 失败尝试与迭代（如实记录）

1. **B1 收尾块首次插入位置错误**：插入锚点（`status: STATUS_READY` 的返回字典）在宿主中出现 6 次，脚本匹配到了 `start_dev_batch` 的返回，导致块落在错误函数内且 B1 未生效（注入后仍 READY）。改为按「`inspect_dev_batch` 内、状态返回之前」精确定位后 B1 生效（实测收尾复测从 0 次变为 1 次）。
2. **B2 缺少目标退出码字段**：失败诊断的 `observed_outputs` 未带严格整数退出码，读回核验失败；补 `target_exit_code`／`exception_class` 后一致。
3. **B4 首轮以文件字节哈希冒充对象指纹**：`gate2_artifacts_file_sha256` 误取了筛查 `artifacts.json` 的值；改为统一 `gate2_*` 前缀读数并区分 screening／Gate2 artifacts。
4. **测试侧子进程补丁无效（TASK-014 已发现，本轮沿用修正）**：造样与 writer 故障必须在**本进程**调用公开 API，CLI 仅作行为对照。
5. **保护比较分隔符**：R1 基线键为 `data\batches\...`，首轮比较未归一，误报缺失 116056／115026；归一后 missing 均为 0。
6. **隔离自测首版无效**：只从文件台账去掉一条不会失败（台账并不要求覆盖全部调用）；改为以 `call_registry.json` 权威登记表为判据，去掉一条即失败。
7. **`started` 追加字段导致旧容器恢复不兼容**：本卡要求 started 必须含两项对象指纹且恢复严格校验，因此 R1 之前创建的容器按协议阻断（如实拒绝，不迁移旧凭证）；本轮全部演示使用新批次。

过程容器 `task014r1_run_01`（保护比较分隔符修正前）与 `task014r1_run_02`（指南 R1 段落成形前）保留未回写。

---

## 8. 三条完整产物路径

- `D:\harness work\audit_sa_project\data\workflow_host_tests\task014r1_run_03`（280 文件：`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`api_records.json`／`evidence_ledger.json`／`call_registry.json`／`protected_scan.json`；`cli_logs\` 228、`api_records\` 6、`core_returns\` 4、`probe_records\` 10、`isolation\` 2）
- `D:\harness work\audit_sa_project\data\batches\task014r1_run_03`（282 文件；8 份 `0006`、0 份 `0007`）
- `D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task014r1_run_03`（11 文件）

---

## 9. 未执行与边界

- 未执行：事实底稿、LLM／网络、人类判断保存、正式契约、真实 Gate、UI／真实 ERP／OCR／RAG、并发锁／断电试验、无边界 fuzz、`0007`、TASK-015。
- 未运行 TASK-013 冻结测试与 TASK-002—013 历史整套入口（本卡不要求）。未装依赖、未初始化 Git、未清理历史目录。
- 边界：本地哈希只证明字节一致；不声称断电持久性、并发锁、身份认证或同权限防篡改。复核一致只表示两套确定性实现的事实核对一致，不证明来源真实性，也不构成审计结论。`0006` 是宿主**复算完成凭证**，不是新批准、新阶段或项目完成。
