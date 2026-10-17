# TASK-016-R1 执行回执（严格来源指纹格式与守卫调用登记）

任务：按唯一权威细则 `docs/tasks/TASK-016-R1.md` 修两项阻断 B1（来源指纹必须完整匹配、不接受尾随 LF）与 B2（G6 守卫内一次真实调用必须进入统一登记与正式计数）。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：两项阻断均已修复并有定点实测证据；本轮最终定点入口在**全新容器**一次执行，退出 **0**、**2/2 检查 PASS、failures=[]**。停在纯核心 `DEV_INITIAL_JUDGMENT_VALIDATED`——不保存真实判断、不认证身份、不解锁 AI，未接宿主、未建 `0008`、未实施 TASK-017。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 起点 | 写后 |
| --- | --- | --- |
| `scripts\build_demo_initial_judgment.py` | `41026b98f8608b8280fbb62793bac59f766e932a17b0deae407ebc8238dd208c` | `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`（20510 字节） |
| `tests\test_build_demo_initial_judgment.py` | `d4ad4b886c9484bb79c088a2428fbc27f3c6fb93ee46a975877620d856b6e13a` | `c0ef730e59ad78f54d7d60014289ea56ca7e79c764f9afba515c1c77449b62f3`（68622 字节） |
| `docs\INITIAL_JUDGMENT_GUIDE.md` | `d995d20d8493e44d53babd37113c96d83c34bcc54ac250f35c2fce51a828b938` | `2bbaa876ae7a76175f3462d9395b7bbc8e4bec5b1631030ff3fe32142d0286f5`（10714 字节；补严格指纹口径与 `--only r1` 说明） |
| `docs\EXEC_REPORT_016_R1.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

**冻结件实测未改**：宿主 `scripts/run_demo_workflow.py` = `67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a`；TASK-015 最终宿主测试 `tests/test_fact_packet_demo_workflow.py` = `90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e`；三份只读事实包字节哈希与登记一致（C06b `8cecbf3b…8755`、MAIN `711fe8d7…b926`、C03 `9644a10a…4426`）。未回写原 TASK-016 回执、未改卡/评审/证据、未清理历史、未安装依赖或初始化 Git。

---

## 2. B1：来源指纹必须完整匹配（已关闭）

**原因**：`_HEX64 = ^[0-9a-f]{64}$` 与 `re.match` 组合，`$` 锚点允许在末尾换行之前匹配，于是「64 位十六进制 + LF」这种 65 字符字符串被当成合法指纹；四项来源共用该 helper，非法值被原样复制进 `record.source`。

**修复**：改为 `_HEX64.fullmatch(value)`（模式去掉 `^`/`$`），要求**整个字符串恰为 64 位小写十六进制**；不做 `strip`、截断、转小写或忽略后缀等静默修正。该 helper 同时覆盖四项来源、`expected_packet_sha256` 与 `submission.fact_packet_sha256`。同时把 `submission.fact_packet_sha256` 的格式检查放在与 expected 比较之前，使「仅 submission 指纹非法」时 `field` 准确指向 `submission.fact_packet_sha256`（旧的 expected 不匹配场景仍先指向 `expected_packet_sha256`，未改变原语义）。

**定点实测**（每项都是独立内存深拷贝、`expected` 与 `submission.fact_packet_sha256` 均绑定候选对象的**新**规范指纹，排除外层指纹不匹配造成的提前拒绝）：

| 反例 | 候选长度 | 本次 API | field |
| --- | --- | --- | --- |
| `workbook_sha256` + LF | 65 | `InitialJudgmentBlocked` | `fact_packet.bindings.workbook_sha256` |
| `normalized_payload_sha256` + LF | 65 | `InitialJudgmentBlocked` | `fact_packet.bindings.normalized_payload_sha256` |
| `screening_report_sha256` + LF | 65 | `InitialJudgmentBlocked` | `fact_packet.bindings.screening_report_sha256` |
| `crosscheck_report_sha256` + LF | 65 | `InitialJudgmentBlocked` | `fact_packet.bindings.crosscheck_report_sha256` |

共享 helper 的少量边界（各一项，未做无穷组合）：来源加 CRLF、来源尾随空格、来源整体大写、`expected` 尾随 LF、`submission`（与 expected 同时）尾随 LF、仅 `submission` 尾随 LF —— 全部 `InitialJudgmentBlocked`；其中仅 submission 非法的用例 `field=submission.fact_packet_sha256`，仅 expected 非法的用例 `field=expected_packet_sha256`。全部反例均为内存深拷贝，三份输入文件与原始对象未被回写（本轮每次合法/非法调用前后同引用指纹一致）。

**合法路径不变**：C06b 正常、MAIN 12 条、C03 零条各一次成功；完整真实返回单份保存、`record_sha256` ＝ `record` 规范指纹、`source` 的对象指纹与四项来源绑定准确、`finding_ids` 按 packet 原序、原文保留；C03 零条未自动产生“无问题”。

---

## 3. B2：守卫内真实调用进入统一登记（已关闭）

**原因**：G6 在 `guard_probe` 的 action 中直接调用新 API，绕过 `record_api`，因此实际公开调用 48 次而台账只有 47 条，缺的正是守卫内那次成功返回。

**修复**：
- 新增 `core_recording(func, label)`：只记录「进入真实核心」的调用序号，不改变入参与返回，**不在守卫内写任何文件**；守卫的 action 用它在守卫期间完成唯一一次真实调用。
- 新增 `record_observed_api(label, (result, exc))`：登记**已在守卫内观察到**的结果或完整异常（含 `traceback`、`reasons`、`field`、cause/context 链），**不再次调用核心**；其文件落盘发生在**守卫解除之后**，因此不会把测试记录 I/O 误判成核心 I/O。
- 每次 `record_api` 记录调用前后的核心调用日志增量（`core_calls_delta`），使「实际进入真实核心的次数」不依赖被调用对象的身份；收尾处统一核对「实际核心调用次数 == 已登记调用覆盖的核心次数 == 登记条数」，不一致即进入正式 failures。该判定在 `all` 与 `r1` 两种模式下共用。

**定点实测**（`task016r1_final`）：守卫调用 **1 次**、守卫命中 **0**（`open`/`os.open`/`socket`/`popen` 全 0）、守卫内返回与同一输入的成功返回严格规范 JSON 相等；`actual core calls observed = 14`、`api_registered = 14`、`registered_core_calls = 14`、`一致=True`；API 记录文件数 14 与登记数 14 双向一致；G6 相关文件 `api_records/r1_guard_observed_call.return.json` 存在且实读哈希与登记一致；五项 `null` / 两项 `false` 固定，状态仅 `VALIDATED`。

**保留入口的连带确认（超出本卡最低要求，如实登记）**：本轮另在过程容器 `task016r1_allcheck` 运行了一次原完整七组入口（卡 §4 称无需重跑；此处仅为确认共享 helper 改动未破坏保留入口）：7/7 PASS、退出 0，且 **API 记录 48 条 / 实际核心调用 48 次**（返回 10、按预期 Blocked 38、意外 0），即原先「48 实际 vs 47 登记」的缺口在原模式下也已闭合。该容器为过程容器，不作为本卡最终交付。

---

## 4. 最终定点入口与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\build_demo_initial_judgment.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"            # 0
& $py -B -c "src = open(r'...\tests\test_build_demo_initial_judgment.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"        # 0
& $py -B '...\tests\test_build_demo_initial_judgment.py' --out-dir '...\data\initial_judgment_tests\task016r1_final' --only r1                            # 0
```

输出要点：`[PASS] R1_STRICT_DIGESTS_AND_GUARD_REGISTRATION`、`[PASS] R1_EVIDENCE_AND_PROTECTION`、`检查项 2：2 PASS / 0 FAIL`、`API 登记 14 条（直接调用 13、守卫观察 1 = 实际核心调用 14 次；返回 4、按预期 Blocked 10、意外错误 0）；一致=True；missing=0 unregistered=0`、`守卫命中 0；保护比较 executed=True`、`测试失败 0`（约 3 分 14 秒）。

---

## 5. 保护比较与冻结件

本轮正确基线 `data/reviews/task016_gpt_20261013_015839/source_hashes_after.json`（实际 **124275** 项、文件 SHA-256 `d8d24e056a2c1543ee2cb1789bf4a0f1ba5386341aa12e43f232916dc7e17f8e`，与同目录 `review_result.json` 登记一致）：单次扫描后 **changed 恰为本轮三个允许文件**（`scripts/build_demo_initial_judgment.py`、`tests/test_build_demo_initial_judgment.py`、`docs/INITIAL_JUDGMENT_GUIDE.md`）、**missing=0**、**读取错误 0**、unexpected=[]；宿主与 TASK-015 测试冻结哈希一致；三份只读 packet 哈希一致。未沿用旧基线，未做第二次全项目扫描。

---

## 6. 辅助记录更正（非阻断，按卡 §5）

1. 旧回执称 G4「28 个提交反例 + 11 个事实包反例」；**按源码/记录实际为 22 + 11 = 33**（本轮新回执按实数给出，未回写旧回执）。
2. 旧登记 47 条＋漏记 G6 的实际 48 次调用：本轮定点模式为 14 条登记 / 14 次实际核心调用，原完整入口复跑为 48 / 48（见 §3 连带确认）。
3. 原隔离自测同时删除 `file_ledger` 一条与 `registry` 一条，**不是**只改一个条件；本轮已改为**严格只删审核副本的一条权威登记（registry）**，`file_ledger`、真实文件与真实台账完全不动，真实 audit helper 立即判失败（`API 调用未登记进权威登记表：api:r1_legal_C06b`），原件审计通过，未因此再建业务链。证据：`isolation/isolation_result.json`。
4. 本轮每次合法/非法调用都重新核对同引用调用前后指纹；负向探针只改内存深拷贝，三份输入文件未回写。

---

## 7. 过程失败尝试与修正（如实记录）

1. 收尾函数参数化时把 `baseline` 变量名同时用于 Path 与扫描字典，导致 `rel(baseline)` 收到 dict 报 `TypeError` → 字典改名 `baseline_map`，路径变量保持 Path。
2. 首个 `submission` 尾随 LF 探针用了 `source_case=True`（expected 仍为干净指纹），于是该调用被 expected 不匹配挡下、无法证明共享 helper 生效 → 改为 `source_case=False`（expected 与 submission 同带 LF），并**另加**「仅 submission 指纹带 LF、expected 合法」的用例，使 `field` 精确落在 `submission.fact_packet_sha256`。
3. 核心对 `submission.fact_packet_sha256` 原先只检查与 expected 相等性、未单独给出格式诊断 → 补上完整匹配格式检查并置于相等性检查之前（消息明确「不接受尾随 LF」）。
4. 控制台原输出「API 调用 47」实际只是直接调用计数、与登记条数口径不一致 → 改为打印登记条数、直接调用数、守卫观察数与实际核心调用次数及一致性。

过程容器：`task016r1_smoke1`（收尾 dict 遮蔽报错）、`task016r1_smoke2`（`submission` LF 探针口径错误，仅字段断言失败）、`task016r1_run_01`（同上字段断言失败）、`task016r1_run_02`、`task016r1_run_03`（共享一致性判定加入前）、`task016r1_allcheck`（保留入口连带确认）全部保留未回写。

---

## 8. 计数与来源（本轮最终容器）

| 项 | 值 | 来源 |
| --- | --- | --- |
| API 登记条数 | 14（直接调用 13 + 守卫观察 1） | `api_records.json` / `api_records\`（14 个文件） |
| 实际进入真实核心次数 | 14（`core_calls_observed`） | `call_consistency.json` 的核心调用日志 |
| 覆盖核心的登记次数 | 14（`registered_core_calls`） | 每条记录的 `core_calls_delta` 求和 |
| 返回 / 按预期 Blocked / 意外错误 | 4 / 10 / 0 | `counts.json` |
| 守卫调用次数 / 守卫命中 | 1 / 0（`open`、`os.open`、`socket`、`popen` 全 0） | `probe_records/r1_guard_registration.json` |
| 台账缺失 / 未登记 | 0 / 0（已执行） | `evidence_ledger.json`、`counts.json` |
| 隔离自测 | `failed_as_expected`（严格单删一条 registry） | `isolation/isolation_result.json` |
| 保护比较 | 已执行（124275 项基线、changed＝三项、missing 0、读取错误 0） | `probe_records/r1_protection.json` |

未执行的动作写 `null`，不填未测得的 0；本卡不涉及宿主 receiver/checker/持久化计数。

---

## 9. 产物路径

- 最终定点容器：`D:\harness work\audit_sa_project\data\initial_judgment_tests\task016r1_final`（28 文件：`summary.json`／`checks.json`／`counts.json`／`api_records.json`／`cli_logs.json`／`call_registry.json`／`evidence_ledger.json`／`call_consistency.json`；`api_records\` 14、`probe_records\` 5、`isolation\` 1）
- 三份只读输入事实包：`data\batches\task015r2_run_03\r1_normal_control\workflow\fact_packet\fact_packet.json`、`data\batches\task015_run_06\main_01\workflow\fact_packet\fact_packet.json`、`data\batches\task015_run_06\g2_c03\workflow\fact_packet\fact_packet.json`（只读，未回写）
- 保护基线：`data\reviews\task016_gpt_20261013_015839\source_hashes_after.json`

---

## 10. 未执行与边界

- 未执行：宿主接入、持久化/独占保存、`0008`、真实 Gate、AI 建议、LLM/网络/UI/ERP；未重跑 TASK-015 宿主入口、0007 writer 或 TASK-002—015 历史任务；未重做全部协议反例与完整七组作为**本卡最终入口**（仅按 §3 做了一次保留入口的连带确认并如实登记）。
- 契约仍为 `DRAFT_NOT_IN_FORCE`；`human_initial_judgment`/`ai_suggestion`/`final_judgment`/两项批准恒为 `null`；身份（`actor_id`/`occurred_at`/`event_id`）均为调用方声明、未认证；不声称实读 `0007`、数据库或 packet 文件字节；调用方同时重声明全部指纹不属本纯内核能阻止的同权限篡改，不宣称防伪。
- 未解决项：无。业务口径或身份/来源问题交 GPT/人类，不自行改规格。
