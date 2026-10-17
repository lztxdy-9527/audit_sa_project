# TASK-015 执行回执（将冻结事实底稿核心接入开发态宿主）

任务：按唯一权威细则 `docs/tasks/TASK-015_DRAFT.md` 把 TASK-008-R1 已验收的确定性事实底稿核心接入宿主：在同版本新批次的合法 `0006` 上显式调用一次 `build_fact_packet`，保存完整 JSON 事实包与对应 Markdown，成功后追加 `0007`，并支持新进程只读恢复。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：八组有界验证全部通过；一次全新容器最终入口退出 **0**、**8/8 检查 PASS、failures=[]**；停在 `phase=DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED` + `RULE_CROSSCHECK_RECORDED` + `FACT_PACKET_RECORDED`（`0007`），无 `0008`、真实批准 `null`、`next_step_allowed=false`；未建立正式契约或真实 Gate、未保存或预填人类判断、未生成 AI 建议、未接 LLM／网络／UI／ERP。

---

## 1. 实现与协议版本

| 项 | 值 |
| --- | --- |
| 宿主实现版本 | `TASK-015-workflow-host-1.0` |
| checkpoint 协议 | `TASK-012-checkpoint-1.0`（未改） |
| manifest 协议 | `TASK-012-host-manifest-1.0`（未改） |
| Gate2／筛查／复算协议 | `TASK-012-*`／`TASK-013-screen-*`／`TASK-014-crosscheck-*`（未随实现版本改名） |
| 事实底稿协议（新增） | `TASK-015-fact-packet-start-1.0`／`-artifacts-1.0`／`-failure-1.0` |
| 冻结核心协议 | `PACKET_VERSION = TASK-008-fact-packet-1.1`（实际核心为准；`FACT_PACKET_GUIDE.md` 第 3 节仍写 1.0 属已登记非阻断旧标注，未改冻结指南） |
| 新增公开 API | `build_dev_fact_packet(batch_dir) -> dict` |
| 新增 CLI | `build-fact-packet --batch-dir <existing-new-batch>`（共八个；七个旧子命令保留） |
| 状态字段 | 新增 `fact_packet_status=FACT_PACKET_RECORDED`、`fact_packet` 摘要、`completed_actions` 项 `FACT_PACKET` |

---

## 2. 修改与新增文件（写后实测 SHA-256）

| 文件 | 起点 | 写后 |
| --- | --- | --- |
| `scripts\run_demo_workflow.py` | `8cf41ca8da12c77f5fc2a9827c936971aeeafd93a963746cc778a9c1d72031f7` | `707cd16ecf9ebeefba2e459f3e468ae3379459adc5cbf426bfb394173eedb75d` |
| `docs\WORKFLOW_HOST_GUIDE.md` | `5ce64aee26986a1ace88ac5ef64a016799077ff10ac0d1d933c87fc455bdbb68` | `ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8` |
| `tests\test_fact_packet_demo_workflow.py` | 新增 | `5f7dacfa07f54587dc835a0e5462470a6638178b5cb642c01af55d491cad9c0d` |
| `docs\EXEC_REPORT_015.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

**关键冻结件实施前与交付后均核对一致**：

| 冻结件 | SHA-256 |
| --- | --- |
| `scripts/build_demo_fact_packet.py` | `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62` |
| `tests/test_build_demo_fact_packet.py` | `46d426e7c262f3b5c773ba6717e5b3e002c34783d11d24a5bd3c43b80effeb36` |
| `docs/FACT_PACKET_GUIDE.md` | `48c051be9bfca3659560c73e4693892ecd1a72629fba7401698eb87f8657ff9d` |
| `scripts/crosscheck_demo_rules.py` | `8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2` |
| `tests/test_crosscheck_demo_workflow.py` | `f34533833d0fa0ac41274f1c847f933ecaf8110de65e35acc43c8bf12393cf43` |
| `tests/test_screen_demo_workflow.py` | `27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca` |

未改：本卡、既有评审/回执、纯核心、其他旧测试/指南、控制器、接收器、标准化/装载/筛查/复算模块、SQL/schema、规格、契约草案、生成器/答案册、原始工作簿或历史容器。未初始化 Git、未装依赖、未清理历史目录。

---

## 3. 真实最终命令与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"        # 0
& $py -B -c "src = open(r'...\tests\test_fact_packet_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"  # 0
& $py -B '...\tests\test_fact_packet_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task015_run_06'                                  # 0
```

输出要点：`检查项 8：8 PASS / 0 FAIL`、`CLI 记录 90 条 / API 记录 14 条；missing=0 unregistered=0`、`全部预期成立。`
定点子集：`--only main|samples|premise|persistence|late|readonly|evidence|protection|smoke`（冒烟先行：`--only smoke` 退出 0、G1＋G2 两项 PASS）。

---

## 4. 八组验证结果与证据引用

| 组 | 结果 | 关键实测 |
| --- | --- | --- |
| 1 MAIN 正常接入 | PASS | 真实建链至 `0007`；底稿核心本次**恰调用 1 次**；`core_returns/main_01_build_fact_packet_return.json` 单份完整真实返回与落盘 packet **严格规范 JSON 相等**；`packet_sha256`（核心返回）＝磁盘 packet 规范指纹；Markdown 磁盘字节精确等于返回 markdown 的 UTF-8 字节（无 BOM、无 CRLF）；12 条线索、分布 `3/5/2/2`、R02 超额 `1600000` 分保持；逐卡比对命中键／整数分／related_ids／source_rows 与筛查报告一致；三输入指纹在核心调用前／返回后／公开返回后一致；`0007` revision 严格整数 7、kind `BUILD_FACT_PACKET`、previous＝0006 实读哈希、workflow 与 0006 严格相等。证据 `probe_records/g1_main_fact_packet.json`。 |
| 2 小样与合法阶段 | PASS | C06b（findings 1，付款 1000000／退款 100000／净额 900000／超额 400000 分）、C03（findings 0 且正文含固定未命中限制文案）、C07b（保留 R03 与整笔/分摊区分）各成功一次并核对本轮 JSON 与正文；只读恢复 `0001`—`0007`；`0005` 过早 build 退出 1 且不建现场、`0007` 重复 build 退出 1、HOLD 对照退出 1 且目录字节集合不变。证据 `probe_records/g2_samples_and_stages.json`。 |
| 3 前提与接口拒绝 | PASS | 真实 MISMATCH 造样（真实 `screen_sqlite` 返回后只改一处整数分金额、由宿主保存、真实复算发现不一致）后 `build-fact-packet` 退出 **1**、未创建 `workflow/fact_packet/`、无 `0007`；错误 `packet_sha256` 协议探针（真实 builder 返回后复制并只改该字段，明确标为测试污染）被协议阻断并留下正确诊断、无成功凭证；`FactPacketBlocked`→退出 1／`FactPacketError`→退出 2 各一次**宿主映射注入**（明确标注为注入，不冒称真实核心业务失败），阶段 `fact_packet`、异常链含对应类别。证据 `probe_records/g3_premise_and_protocol.json`。 |
| 4 有限持久化故障 | PASS | 只对目标 `0007`：**真实 writer** 在真实独占写句柄上写前半缓冲后抛 `OSError`（模式 `x`、`newline="\n"`、进入 1 次、命中 1 次、磁盘半写 38999 字节与预期一致）；完整真实 writer 保存后抛 sentinel。两场景当前与新进程 `status` 均退出 **2**、`stage=fact_packet`、异常链含 `OSError`／`RuntimeError`、旧 `0001`—`0006` 与输入不变；待写完整 UTF-8 文本单份保存并**重新读取**验证（file_sha256＝buffer_sha256、reread_matches_buffer=true）。半写文件数与可恢复成功凭证数分列（`half_written_vouchers=1`）。证据 `probe_records/g4_{partial,throw}_persistence.json`。 |
| 5 晚变更与固定引用 | PASS | 先**无注入**实测真实读取位置（第 1 次来自链核验 `_verify_fact_packet_operation`／第 2 次来自 status 摘要读取／第 3 次为收尾再读），再在**最后一次**用于底稿摘要的读取返回原对象后单次改 `fact_packet.md` 字节：本次 API 即 `WorkflowHostBlocked`；撤销 wrapper 保留变更后新进程 CLI 退出 1；恢复原件后退出 0。只改 `0007.operation.markdown_relative` → 退出 1 且消息指向该字段；改 `started.normalized_payload_sha256` → 退出 1 且消息指向该字段；两者还原后均退出 0。证据 `probe_records/g5_late_change_and_paths.json`。 |
| 6 只读／隔离与输入不变 | PASS | **同进程**把五个真实下游函数（`normalize_workbook`／`load_normalized_to_sqlite`／`screen_sqlite`／`verify_rule_facts`／`build_fact_packet`）替换为计数后抛错守卫，随后直接调用公开 `inspect_dev_batch` → 成功、五个命中计数全 0、批次目录哈希集合前后一致；另作新进程 CLI 对照退出 0；数据库字节不变；三输入同一引用三时点指纹一致（构建观察在核心调用前／返回后／公开调用完成后取值）。字典读取源码哈希属静态核对，未执行。证据 `probe_records/g6_readonly_and_inputs.json`。 |
| 7 证据登记与计数 | PASS | CLI 记录 **90** 条＋API 记录 **14** 条（含造样与负向），每条含完整 command／cwd／退出码／期望码／stdout+stderr 路径与哈希／返回对象或完整异常+链单份引用；`call_registry.json` 权威登记表与 `evidence_ledger.json` 文件台账逐条比对，`missing=0`、`unregistered=0`；receiver 与 checker 按 `receive_invocation.json`／批次 `checker_invocation` 双向核对命令、started、退出码与 report/stdout/stderr 的存在＋实读 SHA；计数从现场导出并分列（见 §5）；隔离自测只删审核副本一条调用登记即失败（真实日志与历史容器未改）。证据 `evidence_ledger.json`、`call_registry.json`、`isolation/isolation_result.json`、`scene_outcomes.json`。 |
| 8 保护与停止点 | PASS | 基线 `data/reviews/task014_r2_gpt_20261012_225658/source_hashes_after.json`（**118788 项**，文件 SHA `19639176acb6dae72cdd0c2ede0df86c4f917d05971cba9da45da99080505e1b`）：单次扫描 121722 文件后 changed **恰为宿主与宿主指南**、missing **0**、unexpected **[]**；六个关键冻结件哈希一致；各批次 checkpoint 均在合法名单内、无 `0008`；五个成功批次链 `0001`—`0007` 有效、`workflow` 与 0006 相等、真实批准 `null`、`next_step_allowed=false`。证据 `probe_records/g8_protection_and_stop.json`、`protected_scan.json`。 |

---

## 5. 实际调用与现场计数（从记录导出）

- **CLI**：`start` 13／`record-simulated-decision` 13／`prepare-gate2` 13／`record-simulated-gate2-decision` 13／`screen-rules` 11／`crosscheck-rules` 11／`build-fact-packet` 4／`status` 12。
- **公开 API**：`build_dev_fact_packet` 10、`inspect_dev_batch` 3、`screen_dev_batch` 1。
- **进程内观测核心**：`build_fact_packet` 8 次；`screen_sqlite` 1 次（真实 MISMATCH 造样包装）；`verify_rule_facts` 0 次（复算经 CLI 子进程执行）。**CLI 子进程内部核心次数不可观测 → 记 `null`**，未把推导值冒充实测。
- **现场导出（总体）**：MATCHED 报告 7；成功凭证 `0007` **5**；失败现场 **5**；半写凭证 **1**；receiver 启动 13；checker 由 receiver 启动 13（exit 0 13）；直接 checker CLI 调用 0；模拟决定 26；真实批准 **0**；副本 0；故障注入 8。
- 子集口径：本入口的“已建事实底稿 4”指流程检查批次（MAIN＋三小样）；总体成功凭证 5 含晚变更探针批次，两者在 `counts` 与 `scene_outcomes.json` 中分别命名。

---

## 6. 真实核心返回与输入观察

- 单份完整返回：`core_returns/main_01_build_fact_packet_return.json`（MAIN）与各小样/故障场景的 `core_returns/*_build_fact_packet_return.json`；`return_path` 在 API 记录中引用。
- 输入引用保留：`capturing` 包装在**调用前**保留三个入参引用并计算指纹，核心返回后与公开调用完成后对**同一对象引用**重算；实测 `before == after_core == after_public`（`normalized`／`screening_report`／`crosscheck_report` 三项）。
- 输入完整对象已有文件，以相对路径＋字节哈希引用：`workflow/gate2/normalized.json`、`workflow/screening/screening_report.json`、`workflow/crosscheck/crosscheck_report.json`。

---

## 7. 故障命中与原因链

| 场景 | 命中 | 退出 | 阶段 | 异常链 |
| --- | --- | --- | --- | --- |
| `0007` 半写 I/O | 真实 writer 进入 1／句柄写命中 1，模式 `x`、`newline="\n"` | 2 | `fact_packet` | `WorkflowHostError` → `OSError` |
| `0007` 完整后 sentinel | 真实 writer 完整写入后抛 sentinel | 2 | `fact_packet` | `RuntimeError` |
| 错误 `packet_sha256` | 协议探针（测试污染） | 1 | `fact_packet` | 协议阻断（无成功凭证） |
| `FactPacketBlocked` 映射注入 | 宿主映射（明确标注） | 1 | `fact_packet` | 含 `FactPacketBlocked` |
| `FactPacketError` 映射注入 | 宿主映射（明确标注） | 2 | `fact_packet` | 含 `FactPacketError` |
| 真实 MISMATCH 后 build | 未创建本层目录、无 `0007` | 1 | `fact_packet` | 前提阻断 |

---

## 8. 过程失败尝试与修正（如实记录）

1. **`_verify_crosscheck_operation` 从未回传核验读数** → `0007` 拿不到筛查/复算上游预期（`chain.expected` 不可用）；补回 `screening_*`／`crosscheck_*`／`gate2_*` 读数返回。
2. **误用 `_verify_gate2_tail` 的键名**（传 `gate2_*` 前缀字典致宿主清单期望 `None`）→ 改为显式复测宿主清单与 Gate2 产物。
3. **状态常量名笔误** `RULE_SCREEN_STATUS_RECORDED` → `SCREEN_STATUS_RECORDED`（该错误发生在成功写入 `0007` 之后，如实留下失败现场并由下一新批次重跑）。
4. **`0007` 缺少“最后一次读取之后”的最终复测**（晚变更探针 G5 首轮未拒绝：注入发生在收尾再读之后）→ 宿主在收尾再读之后追加最终磁盘核验（4 份产物字节、packet 规范指纹、artifacts 内嵌副本、started 指纹一致性），G5 复跑通过。
5. **测试侧 `newline` 比较用了两字符 `"\\n"`** 导致 G4 partial 误判失败 → 改为真实换行符 `"\n"`。
6. G4 首版“旧文件不变”口径过宽（含链构建期间的上游产物）→ 收窄为 `0001`—`0006` checkpoint 前后不变。
7. 测试首版 MAIN 建链误传空 fixture → 改为显式使用真实工作簿 `data/generated/demo_20260930_a/input/erp_export.xlsx`。

过程容器保留未回写：`task015_smoke1`…`task015_smoke5`（定向冒烟）、`task015_run_01`／`_02`／`_03`／`_04`／`_05`（G4/G5 修正前）。

---

## 9. 三条完整产物绝对路径

- 测试容器：`D:\harness work\audit_sa_project\data\workflow_host_tests\task015_run_06`（338 文件：`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`api_records.json`／`evidence_ledger.json`／`call_registry.json`／`scene_outcomes.json`／`protected_scan.json`；`cli_logs\` 270、`api_records\` 14、`core_returns\` 9、`probe_records\` 8、`isolation\` 2）
- 批次父目录：`D:\harness work\audit_sa_project\data\batches\task015_run_06`（381 文件；成功批次各含 `workflow/fact_packet/` 四份产物与 `0007`）
- 外置 SQLite 父目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task015_run_06`（13 文件）

---

## 10. 未执行与边界

- 未执行：TASK-002—014 历史整套入口、事实核心 21 组重跑、TASK-013 冻结测试；未建立正式契约或真实 Gate、未保存或预填人类初判/终判、未生成 AI 建议、未接 LLM／网络／UI／ERP、无性能任务、无 `0008`。
- 边界：本地哈希只证明字节一致；不声称断电持久性、并发锁、身份认证或同权限防篡改。事实底稿是**事实展示**：`0007` 只表示事实底稿已持久化，不代表审计完成、审计通过或底稿已批准；输入文字仍只当数据。业务呈现沿用冻结核心（R03 合法空关联/台账外标识保留、主表与分摊分列、无线索不代表“无异常”）。
- 未解决项：无。若后续需要改冻结核心、规则/金额/缺失关联口径或作真实业务决定，按卡 §8 保存现场交回 GPT/人类。
