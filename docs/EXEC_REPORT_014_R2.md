# TASK-014-R2 执行回执（只修剩余测试方法与证据）

任务：按唯一权威细则 `docs/tasks/TASK-014-R2.md` 修正 `docs/reviews/REVIEW_TASK_014_R1.md` 列出的剩余问题（R1-B2-E 失败现场引用、R1-B3 输入观察与计数/登记）。
日期：2026-10-12。执行端：DeepSeek。验收端：GPT。
**宿主本轮冻结未改**（`8cf41ca8da12c77f5fc2a9827c936971aeeafd93a963746cc778a9c1d72031f7`，与起点一致）。
状态：剩余两类问题全部关闭并有可读回验证的证据；一次全新容器最终入口退出 **0**、**11/11 检查 PASS、failures=[]**；停在 `DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED` + `RULE_CROSSCHECK_RECORDED`（`0006`），无 `0007`、真实批准 `null`、`next_step_allowed=false`；未接事实底稿／AI／人类判断／正式契约／真实 Gate／TASK-015。

---

## 1. 起点与写后哈希

| 文件 | 起点 SHA-256 | 写后 SHA-256 |
| --- | --- | --- |
| `scripts\run_demo_workflow.py` | `8cf41ca8…31f7`（冻结，本卡不得修改） | `8cf41ca8da12c77f5fc2a9827c936971aeeafd93a963746cc778a9c1d72031f7`（**未变**） |
| `tests\test_crosscheck_demo_workflow.py` | `54f71aea…6f18` | `f34533833d0fa0ac41274f1c847f933ecaf8110de65e35acc43c8bf12393cf43` |
| `docs\WORKFLOW_HOST_GUIDE.md` | `322c333a…b2ad` | `5ce64aee26986a1ace88ac5ef64a016799077ff10ac0d1d933c87fc455bdbb68` |
| `docs\EXEC_REPORT_014_R2.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

冻结未改：`scripts/crosscheck_demo_rules.py` = `8fe75bfe…3ad2`；`tests/test_screen_demo_workflow.py` = `27c432db…8eca`。原 `EXEC_REPORT_014.md`、`EXEC_REPORT_014_R1.md`、两份评审、原任务卡与全部历史产物未回写。

---

## 2. 剩余 R1-B2-E：失败现场引用与真实 writer（关闭）

**半写进入真实 writer（不再是替身）**：不再替换 `_write_exclusive_json`，也不自行 `json.dumps`／`open(path,'wb')`；改为在**真实 writer 自己** `open(path, "x", encoding="utf-8", newline="\n")` 得到的写句柄上包装一次 `write`，写入前半段后抛 `OSError`。writer 的 `except OSError` 分支把它映射为 `WorkflowHostError`（运行失败口径）。

实测（`probe_records/b2_partial_persistence.json`）：

- 真实 writer 目标文件 `open` 调用 **1** 次、模式 `'x'`、`newline='\n'`、该句柄 `write` 命中 **1** 次（序列化未改：待写文本由真实 writer 生成）；
- 磁盘半写 **38222** 字节 = 预期前半段字节数（`matches: true`）；
- 异常链 `['WorkflowHostError', 'OSError']`；失败诊断 `stage=crosscheck`、`target_exit_code=2`；新进程 `status` 退出 **2**、`exception_class=WorkflowHostError`；`0001`—`0005` 字节不变。

**完整后 sentinel**：保留真实 writer 函数，先让它完整写入并读回核验（返回真实字节哈希），随后抛 `RuntimeError("SENTINEL-T14R2-THROW-0006")`。实测：待写 76375 字节完整落盘、异常链 `['RuntimeError']`、新进程退出 **2**、sentinel 留在诊断内。

**待写文本引用真实可验证**：两场景均按确切 UTF-8 字节写单份文件（`core_returns/b2_{partial,throw}_pending_0006.json`），保存后**重新读取该文件**计算大小与哈希：

| 场景 | 文件字节 | 内存缓冲字节 | 文件 SHA-256 = 缓冲 SHA-256 | 读回一致 |
| --- | --- | --- | --- | --- |
| partial | 76445 | 76445 | 是 | 是 |
| throw | 76375 | 76375 | 是 | 是 |

> 说明：R1 记录的 76445／76375 是**内存缓冲**字节数（`\n` 计数为 1 字节），而 `Path.write_text` 的默认换行转换使落盘文件变成 78012／77942。R2 改为 `open(..., "wb")` 写确切字节并读回验证，文件大小/哈希与缓冲一致，不再把内存哈希标成文件哈希。

---

## 3. 剩余 R1-B3：输入观察、登记与计数（关闭）

1. **输入指纹在真实核心调用前取得**：`capturing_verify` 现在**先**保留真实入参引用并计算 `before` 指纹，**再**调用 `real_verify`；公开调用完成之后对**保留的同一对象引用**重算 `after` 指纹。实测 `normalized_before == normalized_after`、`screening_before == screening_after`（不再用两个调用后值冒充前后）。
2. **造样公开入口已登记**：`screen_batch(tamper=True)` 改为经 `record_api` 调用 `host.screen_dev_batch`（本进程内），其完整返回单份保存；本轮 API 记录 **7** 条（R1 为 6 条），新增 `g3_mismatch_screen_tampered`。
3. **receiver/checker 从留痕双向核对**：逐批次读取 `workflow/host_manifest.json` 的 `receive.command/exit_code` 与 `workflow/receive_invocation.json` 的 `command/exit_code` 比较一致；读取批次 `batch_manifest.json` 的 `checker_invocation`（argv／attempted／started／exit_code）并**逐项验证** `report`／`stdout_log`／`stderr_log` 的 `exists` 与 `sha256`。实测：**批次 11；checker started 11、exit_code=0 11；receiver 启动 11**；直接 checker CLI 调用 0（另列，不与真实执行混淆）。
4. **总体计数从现场导出**（`scene_outcomes.json` + 控制台汇总）：批次 11、**MATCHED 报告 8**、**成功凭证 6**（可解析 `0006` 且无 `failure`）、**失败现场 3**、MISMATCH 报告 1；同时把**本轮流程检查的批次子集**单独标注（MATCHED 4／成功凭证 4，范围 G1 与 G2 三小样）。`counts` 中总体字段改名 `*_total` 并给出 `scope`，不再以同名指标混用子集与总体。
5. **正式审计能发现未登记调用**：`evidence_ledger.json` 的文件台账与 `call_registry.json` 权威登记表逐条比对，缺失/未登记进入正式 `failures` 并致非零退出；隔离自测**只删审核副本的一条登记**（`cli:b1_chain_start`／`stdout_path` 与其登记表条目）即失败。
6. **traceback 取自异常对象**：API 异常记录改用 `traceback.format_exception(type(err), err, err.__traceback__)`，并标注 `traceback_source=exception.__traceback__`（不再出现 `NoneType: None`）。

---

## 4. 最终入口实测（`data\workflow_host_tests\task014r2_run_03`）

```powershell
$py='D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B '...\tests\test_crosscheck_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task014r2_run_03'   # 0
```

输出要点：`检查项 11：11 PASS / 0 FAIL`、`CLI 记录 76 条 / API 记录 7 条；missing=0 unregistered=0`、`全部预期成立。`
（11 项 = R2 新增的现场清单/子进程审计 + 既有 B1／B2／B4／G1／G2／G3／G5／G6／G7／记录审计；按卡 §4「若选择运行现有完整入口，只做一次最终新容器」执行，未追加额外整套回归。）

总体计数（现场导出）：批次 11／MATCHED 8／MISMATCH 1／成功凭证 6／失败现场 3；子集：MATCHED 4／成功凭证 4；子进程：receiver 11、checker 由 receiver 启动 11（exit 0 11）、直接 checker CLI 0；模拟决定 22；真实批准 0；`0006` 8 份、`0007` 0 份。

---

## 5. 保护比较（单次扫描复用两组）

单次扫描 118572 文件（排除 `.venv`／`.git`）：

| 基线 | 条目 | changed | missing | unexpected |
| --- | --- | --- | --- | --- |
| R2 基线 `data/reviews/task014_r1_gpt_20261012_221645/source_hashes_after.json` | 116059 | `docs/WORKFLOW_HOST_GUIDE.md`、`scripts/run_demo_workflow.py`、`tests/test_crosscheck_demo_workflow.py` | 0 | 0 |
| 原主基线 `data/reviews/task013_r4_20261012_201824/source_hashes_after.json` | 115029 | `docs/WORKFLOW_HOST_GUIDE.md`、`scripts/run_demo_workflow.py` | 0 | 0 |

宿主在 R2 基线下显示 changed 是因为它与 R1 评审时相同（`8cf41ca8…31f7`），差异来自 R1 那轮已授权的宿主改动，本卡未再改宿主（写后哈希与起点完全一致可证）。评审文档与两张修正卡保留未回写。

---

## 6. 失败尝试与迭代

1. `collect_batch_outcome` 首版直接 `json.loads` 半写的 `0006` → 抛 `JSONDecodeError` 中断运行；改为容错读取并记录 `voucher_0006_parseable`。
2. `_ObservedHandle.write` 首版把 `bytes` 传给真实文本句柄 → `TypeError: write() argument must be str`，被 writer 的 `except OSError` 捕获成 `['TypeError']` 且磁盘 0 字节（`partial_matches=False`）；改为写入解码后的前半段文本再抛 `OSError`，异常链恢复为 `['WorkflowHostError','OSError']`、磁盘半写 38222 字节与预期一致。
3. 首次跑 R2 入口时总体/子集计数尚在同一字段（MATCHED 4／凭证 4）；改为从 `scene_outcomes.json` 导出总体（8／6／3）并把流程检查子集单独命名。
4. 指南 R2 段落插入后未重跑 → 按「源码改动须复核受影响范围」在同版本宿主下再跑一次最终入口（`task014r2_run_03`），旧容器 `task014r2_run_01`（容错修正前）、`task014r2_run_02`（指南段落成形前）保留未回写。

---

## 7. 三条完整产物路径

- `D:\harness work\audit_sa_project\data\workflow_host_tests\task014r2_run_03`（283 文件：`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`api_records.json`／`evidence_ledger.json`／`call_registry.json`／`scene_outcomes.json`／`protected_scan.json`；目录 `cli_logs\` 228、`api_records\` 7、`core_returns\` 4、`probe_records\` 11、`isolation\` 2）
- `D:\harness work\audit_sa_project\data\batches\task014r2_run_03`（282 文件；8 份 `0006`、0 份 `0007`）
- `D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task014r2_run_03`（11 文件）

---

## 8. 未执行与边界

- 本卡未重跑 MAIN 之外的额外整套回归，也未运行 TASK-013 冻结测试与 TASK-002—013 历史入口；未装依赖、未初始化 Git、未清理历史目录。
- 未执行：事实底稿、LLM／网络、人类判断保存、正式契约、真实 Gate、UI／真实 ERP／OCR／RAG、并发锁／断电试验、无边界 fuzz、`0007`、TASK-015。
- 边界：本地哈希只证明字节一致；不声称断电持久性、并发锁、身份认证或同权限防篡改。`0006` 是宿主复算完成凭证，不是新批准、新阶段或项目完成。
