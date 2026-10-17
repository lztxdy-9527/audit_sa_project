# TASK-024-R8 执行回执：收敛为一次正式收尾，真实 CLI 消费最终结论

日期：2026-10-14。任务卡：`docs/tasks/TASK-024-R8_DRAFT.md`。
依据：`docs/reviews/REVIEW_TASK_024_R7.md`。
分类：B 类，DSH 定点实施，**交 GPT 验收**（本回执不宣称任何验收通过，也不代表任何批次被批准）。

本轮只修三处同根问题（B1 最外层未消费最终 verdict、B2 终端确认后仍有候选读取、E1 假干跑导致正式根双写）。
未新增业务功能、未改生产协议；R5 越界现场继续固定留证、不追认。

## 1. 起点核对（只读实读）

| 文件 | 要求 SHA-256 | 实读 | 一致 |
| --- | --- | --- | --- |
| `tests/test_record_demo_human_gate1.py`（起点） | `59a47508faa9117128b03c3717ddd93a8006caa40f6d460dc29abc87467058e1`（235369） | 同 | ✅ |
| `scripts/record_demo_human_gate1.py`（冻结） | `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9` | 同 | ✅ |
| `docs/HUMAN_GATE1_DECISION_GUIDE.md`（冻结） | `9c8f4409a1c964a65fe64139424795e635ecdf33a55f1724fec683fe9998c2fb` | 同 | ✅ |
| 旧 harness `task024r1_fault_00/aux_fault_r1.py`（冻结） | `7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035` | 同 | ✅ |
| `docs/reviews/REVIEW_TASK_024_R7.md` | `e16dc122ca86afb4a70aa4b51f28abbdf795f2a5df8daa63c16f65b2c8c62257` | 同 | ✅ |
| `docs/tasks/TASK-024-R8_DRAFT.md` | `9eae5ec3319bd521347fba82210a7341408f898862ce62b61dc98c58ce9f3a30` | 同 | ✅ |
| R7 基线 `data/reviews/task024_r7_gpt_20261014_234640/source_hashes_after.json` | `feff142c9a787601eda695df09eb3cb810517930505a7839afe475ba02fcd7a6`（156540 项，NOT_ACCEPTED） | 同 | ✅ |

## 2. 根因与修复位置

### B1：最外层未消费实际最终 verdict

- 根因：`clean_payloads` 让正式正常根使用**局部 failures 副本**，内部失败写入该副本与根目录；
  而 `run_r5_only` 结尾只检查**全局 `FAILURES`**，忽略了 `normal` verdict 的 `entry_failed`，
  故内部 FAIL 而 CLI 仍返回 0。
- 修复：`run_r5_only` 直接消费实际最终正常根 verdict——
  `normal_clean = verdict.exit_code==0 ∧ summary_status=="PASS" ∧ entry_failed==False ∧ same_buffer ∧ ledger_audit_ok ∧ 磁盘核对全一致 ∧ 终末字节确认全一致`；
  外层返回码 `0 if (normal_clean ∧ controls_ok ∧ outer_clean) else 1`。
  两个内部故障副本的 1/FAIL 只作控制证据（`control_flags`），既不代替外层判定，也不会让正常套件一律失败。

### B2：终端字节确认之后不再读候选文件

- 根因：`late_confirmation` 之后，成功分支还 `read_bytes`+`json.loads` 读 `summary.json`，
  再读其字节决定是否覆写；该接缝可被后置改动绕过。
- 修复：成功路径直接采用**写盘前已定稿的同一 in-memory summary 对象**（`final_payloads["summary.json"]`），
  `ledger_readback.json` 直接取**在内存中已算出的** `ledger_audit`；
  失败路径按既定口径用内存对象写失败元数据。静态核对：`late_confirmation` 之后的
  `read_bytes/read_text` 次数为 **0**（只剩内存写入与 `json.loads(内存字节)`）。
- 另加最外层**一次有界字节再确认**（`outer_byte_confirmation`）：仅当正式正常根自报成功时，
  把当前最终字节作为已绑定读数与写前声明逐项比对，不一致即拒绝返回成功并把根 summary 记为 FAIL。
  这是单一的线性确认，不是多轮审核循环；正常路径比对的即是 entry 自己写入的字节。

### E1：移除假干跑与正式根双写

- 根因：`run_r5_entry` 的 `dry_run` 参数未在函数体内生效，正常根被写两次（checks 与台账两次字节不同）。
- 修复：**删除 `dry_run` 参数与前置干跑**。正式正常根与两个故障副本各自的六载荷 + 台账
  都只在 `run_r5_entry` 内**写一次**（`compile_payloads` 定稿 → 一次写盘 → 真实末次审核 → 最终字节确认）；
  成功路径此后不再改任何已登记载荷字节（失败路径按既定口径写失败元数据）。
  正常根的检查结论不再预写进载荷（避免自指），改为在 `r8_entry_checks.json` 中与根 summary/failures 如实分列。

## 3. 实际 CLI 末端验收（真实新进程）

driver：`data/human_gate1_decision_tests/task024r8_run_01/r8_cli_probe.py`（三种模式各起独立新进程）
+ `run_r8_cli_probes.py`（聚合）；结果 `cli_probe_results.json`。
每个模式都经当前 `main()` → `--only r5` → `run_r5_only` 的真实分派路径，验收以**进程退出码**为准。

| 模式 | 实际进程退出码 | 根 summary | failures | 说明 |
| --- | --- | --- | --- | --- |
| `normal` 正常对照 | **0** | PASS | 0 | 六载荷+台账各写一次；终端确认后无候选读取 |
| `final_audit_failure` 实际最终正常根末次审核失败 | **1** | **FAIL** | 非空（1） | 真实 helper 原值 `ok=true` → 受控映射一次 `ok=false`+非空问题；`hit_counter=1`；`normal_clean=false` |
| `post_confirmation_lf` 终端确认后字节变化 | **1** | **FAIL** | failures.json 非空（1） | 终端确认之后对正式根 `checks.json` 追加 1 个 LF（4670→4671 B）；最外层有界字节再确认检出 `outer_byte_drift=[checks.json]`，根 summary 记 FAIL、`outer_failure_diagnostic.json` 留存、坏字节保留 |

- 故障一的注入**只发生在正式正常根**（`injected_control.fault is None` 的那一次末次审核调用），
  未注入内部故障副本、未在写盘前宣布 FAIL：`declared_failed_before_write=false`。
- 两例控制均恰命中 1 次（`hit_counter=1`、`applied=true`），`observation_flags_rewritten=false`。
- 三条既有隔离负向（`core-prepare::4/5/9`）仍由同一真实 helper 分别拒绝，范围未扩大。

## 4. 正常正式根最终磁盘核对（独立实读）

| 载荷 | 台账 = 实际 | 一致 |
| --- | --- | --- |
| `calls.json` | 100546 B `1c915ad2…` | ✅ |
| `checks.json` | 4670 B `b67b2111…` | ✅ |
| `core_observations.json` | 154032 B `0003970f…` | ✅ |
| `failures.json` | 3 B `37517e5f…` | ✅ |
| `samples.json` | 8084 B `213adc58…` | ✅ |
| `summary.json` | 2661 B `96fe4f76…` | ✅ |

`same_buffer=true`、`ledger_audit_ok=true`、`expectation_compare_ok=true`、`disk_audit_ok=true`；
`outer_byte_confirmation` 六项全 `ok`；`outer_returns={normal_clean:true, controls_ok:true,
outer_byte_confirmation_clean:true, exit_code:0}`。

## 5. 同源旧观察 / 本轮实际执行 / 未执行项（如实分列）

- **同源旧观察（读取，不计为本轮重新观察）**：GPT R7 评审 `window_lifecycle_controls.json` 等只读引用；
  R6/R7 基线与越界清单只读核对。未执行会写其固定输出路径的 reviewer 脚本。
- **本轮实际执行**：`--only r5` 正式运行一次（9 次 prepare、3 次接收、9 项检查）；
  另在三个独立新根各跑一次实际 CLI 探针（合计新增 27 次 prepare、9 次接收），用于验收外层返回码与控制传播。
- **未执行**：完整 98/93 项套件、历史入口、writer/loader、已关闭业务保存反例、
  真实 Gate2/宿主/真实初判/0009/AI/终判；未制定 TASK-025。
- 未观察项按 `null`/`0` 分列，不填默认值。

## 6. 交付物与最终哈希

唯一修改的既有文件：

- `tests/test_record_demo_human_gate1.py`：起点 `59a47508…58e1`（235369 B）→ 最终
  **`bb3a3c6fbf75e05322138fdf0efd97bd09199f05d7601dcbd064d0d0b26402d2`**（236218 B）

本轮新增（关键文件实读 SHA-256）：

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `.../task024r8_run_01/summary.json` | 2661 | `96fe4f766b753cf1ce18b1e7fc62d349072ea919545f60caab1ba97d40b125a0` |
| 同目录 `checks.json` | 4670 | `b67b2111bf7cc7666506f4465c1d8c7f5d4b7755ceabf3a4890556bcc1d76bb5` |
| 同目录 `evidence_ledger.json` | 275370 | `69c2f589c0b86f2d8a65ea9528e0c49ca5f9455dcc877a8e100c929cec5248bf` |
| 同目录 `ledger_readback.json` | 6637 | `1f85e98fe2a45bd3ad4a058b1a8e2345c208d8aa47b720f319c80a66971f0683` |
| 同目录 `r8_entry_checks.json` | 21216 | `5f609574b304aa7c5347a48c6033e7dfa0eb979799679839f54e8d6f99e6b4d5` |
| 同目录 `cli_probe_results.json` | 4809 | `92c3506331d6a49c0df6236d720576c2c949f5f438e04a91ed22e0036ca60790` |
| 同目录 `r8_cli_probe.py` / `run_r8_cli_probes.py` | 3734 / 3244 | `7dcf7773…a62` / `2c9c7f18…486` |
| 同目录 `protection_scan_r8.json` | 112366 | `66995a8bc90ddb8e660dc61c39cc0304b49de14efe5dea089b23b70011170ce9` |
| 三个探针新根 `task024r8_probe_{normal,auditfail,lf}/` | — | 逐项登记在扫描 `allowed_added` |

本回执自身最终 SHA-256 见交接消息（避免自指反复改写）。

## 7. 保护与历史留证

- 最终一次全树扫描（含本回执与三个探针新根）：R7 基线 156540 项；changed **1**（仅测试文件，允许）；
  范围外变化 **0**；added 247 全部落在本卡明示根 + 三个探针新根 + 本回执；范围外新增 **0**；
  missing **0**；读取错误 **0**；R5 越界 **326 项逐项不变**（drifted 0/gone 0）；`scope_compliant=true`。
- 自指/口径：基线快照自身与本轮扫描结果文件为自指排除；基线漏登的既有
  `data/reviews/task024_r7_gpt_20261014_234640/review_result.json`
  （`1f72fe1b896af38e8f05e68fea21ecc06539640ca099744edb8cafd992194ff0`，2672 B）按确切路径单列，未改动。
  未把 `data/human_gate_decision_records/` 或 reviews/data 大前缀列入豁免；本轮未新建决定记录根。

## 8. 更正与残余风险

- 更正 R7 回执中"干跑不写盘、不改全局状态""内部 1 即代表整个 CLI 1"的两处声明：
  前者与实现不符（`dry_run` 未生效、正式根被写两次），后者被 B1 反例证伪。**只在本回执更正，不回写旧回执。**
- 残余风险（供评审定点裁决）：
  1. 正常根的检查结论不预写进载荷（避免自指与双写），改在 `r8_entry_checks.json` 与根 summary/failures 分列；
     载荷内只登记两个控制副本的真实结论（`checks_total=9`）。该分列口径请 GPT 裁决。
  2. 最外层"一次有界字节再确认"是线性单次确认（非多轮循环），仅在正式正常根自报成功时执行；
     其是否满足"终端确认后不再引入未复测消费/不自动重写已声明成功载荷"的口径请 GPT 裁决。
  3. `audit_ledger` 的 `expect_failure` 语义沿用 R7 裁决（仅表示既有失败登记是否如实保留），未扩大三条具名负向范围。
- 未接 Gate2、宿主、标准化/SQLite、真实初判、0009、AI/终判或真实数据。真实批准 `null`、开发宿主 `0008`、
  next/AI false；本回执不宣称验收通过或批次获批，看板由人类处理。
