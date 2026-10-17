# TASK-024-R7 执行回执：末次终审必须决定顶层返回

日期：2026-10-14。任务卡：`docs/tasks/TASK-024-R7_DRAFT.md`（`567aeccd85d1dbc209211a282230a081babf7174b517bc05a0906641377b3f40`）。
依据：`docs/reviews/REVIEW_TASK_024_R6.md`（`8a32613425d25b7fb9c4a33bee40c0decf1f428e98ccc890929c33bf60ecdb85`）。
分类：B 类，DSH 定点修复，**交 GPT 验收**（本回执不宣称任何验收通过，也不代表任何批次被批准）。

本轮实测范围：唯一修改既有文件 `tests/test_record_demo_human_gate1.py`；新增本轮证据根
`data/human_gate1_decision_tests/task024r7_run_01/` 与同轮接收批次根 `data/batches/task024r7_run_01/`；
新建 `docs/EXEC_REPORT_024_R7.md`。未运行完整 98 项套件、历史入口、writer/loader 或已关闭保存反例；
未改生产适配器、指南、窗口算法、契约/生效登记、配置、宿主/控制器与任何旧现场；未重做 B1/窗口/隔离负向范围/S1。

## 1. 起点核对（只读实读）

| 文件 | 要求 SHA-256 | 实读 SHA-256 | 一致 |
| --- | --- | --- | --- |
| `tests/test_record_demo_human_gate1.py`（起点） | `8258581529e87385f47dcf3ec62c6c51053b224a695ebf37ef75c7a735149086`（686526） | 同 | ✅ |
| `scripts/record_demo_human_gate1.py`（冻结） | `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9` | 同 | ✅ |
| `docs/HUMAN_GATE1_DECISION_GUIDE.md`（冻结） | `9c8f4409a1c964a65fe64139424795e635ecdf33a55f1724fec683fe9998c2fb` | 同 | ✅ |
| 旧 harness `task024r1_fault_00/aux_fault_r1.py`（冻结） | `7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035` | 同 | ✅ |
| `docs/tasks/TASK-024-R7_DRAFT.md` | `567aeccd…7b3f40` | 同 | ✅ |
| `docs/reviews/REVIEW_TASK_024_R6.md` | `8a326134…db85` | 同 | ✅ |
| R6 基线快照 `source_hashes_after.json` | `06ebfc68f8ef5c5424b9b1435e3b484085fdc7b8761b5d57ea95b83252ae84f4`（156315 项，NOT_ACCEPTED） | 同 | ✅ |

R5 越界 37 目录/326 文件在本轮仍逐项实读不变（见 §5），不追认、不改动、不作正向样本或真实批准。

## 2. 早期结果与最后成功的分界

- **早期阶段**（`build_r5_round_summary`）：真实接收 3 个样本、真实 prepare 9 次、B1 窗口控制 9 条。
  它只返回观察载荷，**不产出任何成功结论**（不再有早期 closure/PASS 继承）。
- **唯一成功判定处**（`run_r5_entry`）：真正 `--only r5` 顶层末次收尾。它在**同一份确定字节**上
  一次定稿六个载荷 + 台账，写盘后不再改这些字节，并由真实末次判据决定 FAIL/非空 failures/返回码。
- 最终预期来源：`run_r5_entry` 写盘前在待写缓冲上计算 `expectation_sha256/byte_size` 并写入台账
  （`final_entry_basis`）；写盘后逐项从磁盘复算，不重建期望、不从坏候选重新生成预期。
- 正常根的检查结论由**干跑**（`dry_run=True`）在同一确定缓冲上取得，然后写进载荷再重放同一末次收尾；
  干跑与写盘跑同源同值（见 §3.1），不构成"早期 PASS 继承"。

## 3. 末次失败如何进入真正顶层返回

本轮实跑：`.venv\Scripts\python.exe -B tests\test_record_demo_human_gate1.py --only r5 --out-dir data\human_gate1_decision_tests\task024r7_run_01`
→ **10 项检查、0 失败、退出 0**；顶层末次：正常 `0/PASS`、故障一 `1/FAIL`、故障二 `1/FAIL`。
本模式真实计数：prepare 9、save 0、verify 0、接收 3、核心观察 9、窗口登记 4；
`store_save/store_verify/p1_entry/p1_seam` 实际为 0，未观察的子进程次数按 `null` 分列。

三个判定都由**同一实际顶层末次收尾**（同一函数、同一代码路径）产出；两个故障副本只改变注入。

### 3.1 正常（`R7-A`，真正顶层返回 0 / summary PASS / failures 空）

- 最终六个载荷 + 台账一次写出；`same_buffer=true`、`ledger_audit.ok=true`、`content_audit_readback.ok=true`。
- 独立从最终磁盘复算：六项载荷长度/SHA 与台账**逐项一致**，`late_confirmation` 全 `ok`：

| 载荷 | 台账 = 实际 | 一致 |
| --- | --- | --- |
| `calls.json` | 100546 B `d7362a2b…` | ✅ |
| `checks.json` | 5322 B `73665784…` | ✅ |
| `core_observations.json` | 154032 B `d36718dd…` | ✅ |
| `failures.json` | 3 B `37517e5f…` | ✅ |
| `samples.json` | 8084 B `0d78e97e…` | ✅ |
| `summary.json` | 2664 B `ef0aeb4d…` | ✅ |

- 正常成功路径的 summary 末次审核块在**写盘前**按同值定稿，因此写盘后不发生任何已登记载荷字节变化
  （实现上写入前先比对 SHA，一致即不写）。

### 3.2 故障一（`R7-B`，顶层末次台账读回审核受控失败）

- 时点：**写盘后**、最终磁盘字节上真实调用 `audit_ledger` 返回之后，恰 1 次受控映射为非空问题。
- 完整读数：真实 helper 原结果 `ok=true`（`readback_audit_real_helper.ok=true`，`real_helper_ok_before_control=true`），
  映射后 `ok=false`，问题为 `R7 受控映射：顶层末次台账读回审核被测试注入标记为非空问题`。
- `injected_control`：`applied=true`、`hit_counter=1`、`target_hit=1`、`observation_flags_rewritten=false`。
- 顶层结果：**真正入口返回 1**、根 `summary.status=FAIL`、`failures=1`（非空）、
  `declared_failed_before_write=false`（**不是**写盘前先宣布 FAIL 凑证明），坏候选 9 文件原样保留。
- 台账读回：`ledger_audit_ok=false`；`final_audit_diagnostic.json` 留存判据与注入现场。

### 3.3 故障二（`R7-C`，末次必要消费之后的字节变化）

- 时点：真实读取返回原值之后，对当前根已消费的 `checks.json` 只追加一个 LF，**不同步任何哈希**。
- 实测字节：期望 3647 B `700c5cc6…` → 实际 3648 B `bc8a02e8…`；`late_drift_after_final_read` 命中该文件。
- `injected_control`：`applied=true`、`hit_counter=1`、`sha256_before/after` 与长度差如实登记。
- 顶层结果：**真正入口返回 1**、根 `summary.status=FAIL`、`failures=1`（非空）、
  `ledger_audit_ok=true`（该例的失败来自末次字节而非台账读回），坏候选 9 文件保留（含被追加 LF 的那个字节）。

### 3.4 支配关系（回答"不是只登记为 false"）

失败不再是"只写进 `ledger_readback`"。三个位置的判据全部进入顶层：`FAILURES`（失败登记）、
`summary.status/checks_failed`、以及 **`run_r5_only` 的返回码**（`1 if FAILURES else 0`）。
`entry_failed = 写盘前定稿失败 ∨ 末次审核失败 ∨ 同缓冲不一致 ∨ 磁盘一致性失败 ∨ 内容审核失败 ∨ 末次字节漂移`，
其中**任一项为真即顶层 FAIL 且返回 1**；两例故障的实测返回码均为 1，正常为 0。

## 4. 本轮定点清理与实现要点

- 依 `REVIEW_TASK_024_R6.md` §3 的允许，局部清理了收尾相关**同名重复（死）定义**：
  `collect_negative_controls` 30→1、`evaluated_evidence` 30→1、`build_r5_round_summary` 31→1、
  `register_r5_closure_checks` 25→1、`finalize_r5_closure_checks` 25→1，另删除 30 份重复常量并补回
  被覆盖遗漏的模块级声明。清理前后**逐名比较最后生效定义的源码文本完全一致**（AST 定位 + 原文比对），
  未做大重构、未改历史组件、未新增 tests/ 文件。
- 删除 R6 的"常量成功替代"：不再有 `content_audit.ok=true` 之类硬填；`content_audit` 只作信息登记，
  内容一致由真实 `compare_expectation` 支配，台账失败结论由真实 `audit_ledger` 支配。
- 台账不内嵌自身 SHA；末次自身哈希另存读回诊断（`ledger_readback.json` 的 `expectation_sha256`）。
- 保留完整真实载荷/异常、独立入口计数与严格 canonical 类型规则；未手动改观察标记。

## 5. 保护与历史留证

- R5 越界 **37 目录/326 文件逐项实读不变**（drifted 0 / gone 0）；本轮未新建任何决定记录根、无新事件、无 SQLite。
- 最终一次全树扫描（含本回执）：基线 R6 快照 156315 项；changed 仅测试文件（允许）；
  R7 新增全部落在本卡明示根 + 本回执；missing/读取错误/范围外变化/范围外新增均为 **0**；
  `scope_compliant=true`。结果见同目录 `protection_scan_r7.json`（哈希见 §6）。
- 自指/口径说明逐项列出（不使用 reviews/data 大前缀豁免）：基线快照自身与本轮扫描结果文件为自指排除；
  基线快照漏登的既有文件按确切路径单列（见扫描报告 `pre_existing_baseline_omissions`）。

## 6. 交付物与最终哈希

唯一修改的既有文件：

- `tests/test_record_demo_human_gate1.py`：起点 `8258581529…9086`（686526 B）→ 最终
  **`59a47508faa9117128b03c3717ddd93a8006caa40f6d460dc29abc87467058e1`**（235369 B）

本轮新增（关键文件实读 SHA-256）：

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `data/human_gate1_decision_tests/task024r7_run_01/summary.json` | 2664 | `ef0aeb4db8c56de45d488fd86ec8dd9009aaed68a45b216dc34bdd97f2045d73` |
| 同目录 `checks.json` | 5322 | `73665784798eb004ac2b9ef85aee8a877af7e465fe789c6b9eb446c90ff7e940` |
| 同目录 `failures.json` | 3 | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| 同目录 `evidence_ledger.json` | 276031 | `73014cd563b832c28501838a6b31eefbdf67a8deae4adeaf55a1475f67b0b36a` |
| 同目录 `ledger_readback.json` | 6638 | `62201a135a2070cecde08c12911f5b775a89ec5d2f71c3d5554d5c73cd92f256` |
| 同目录 `r7_entry_checks.json` | 13945 | `43aae1e6f1d460dc704e39a0315d3aaae55da034b19d39d2e1f9557f47fa5b46` |
| 同目录 `r5_closure_fault_controls.json` | 22468 | `c15abe5b19a8a280eb1d2614a77c1e24d43eaa26497ddca6cab8e39db36f588b` |
| 同目录 `protection_scan_r7.json` | 29679 | `3b5171e431914b057e5c14d30d23e420fa126ec2433b285422d5a08429bedf4a` |
| `entry_fault_1_ledger_readback/`（坏候选，9 文件） | — | 含 `final_audit_diagnostic.json` |
| `entry_fault_2_late_byte_after_final_read/`（坏候选，9 文件） | — | 含被追加 LF 的 `checks.json` 3647→3648 B |

本回执自身最终 SHA-256 见交接消息（避免自指反复改写）。

## 7. 计数范围、读旧证据与本轮实测

- **本轮实测**：`--only r5` 一次真实运行（9 次 prepare、3 次接收、10 项检查）；两例故障在同一轮次内
  由同一实际顶层末次收尾产出（复用同一次真实观察，未重复接收/建链）。
- **读取旧证据（非本轮重跑）**：GPT R6 终审的 `window_lifecycle_controls.json` 等只读引用；
  R5/R6 越界与基线清单只读核对；未执行会写其固定输出路径的 reviewer 脚本。
- **未执行**：完整 98 项套件、历史入口、writer/loader、已关闭保存反例、真实 Gate2/宿主/真实初判/0009/AI/终判。
- **未观察项**按 `null`/`0` 分列，不填默认值。

## 8. 边界与残余风险

- 未接 Gate2、宿主、标准化/SQLite、真实初判、0009、AI/终判或真实数据；未制定或实施 TASK-025。
- 本回执不宣称 GPT 验收通过、不宣称任何批次获批；真实批准 `null`、开发宿主 `0008`、next/AI false。
- 残余风险（供评审定点裁决）：
  1. 正常根采用"同一确定缓冲上先干跑取得结论、再重放同一末次收尾写盘"的组织方式（干跑不写盘、不改全局状态）；
     其是否满足"最终载荷一旦声明不再改其字节"与"不以早期结果代替最后成功"的口径，请 GPT 裁决。
  2. 台账读回审核的 `expect_failure` 语义已调整为"已登记失败即视为如实登记"（`final_audit_failed` 必须为 true），
     `content_audit` 降为信息登记（内容一致由 `expectation_compare` 支配）；该口径请 GPT 裁决。
  3. 故障一为保留真实 helper 原始读数的受控映射（恰 1 次，写盘后边界）；其作为"真实末次审核失败传播"的
     充分性请 GPT 裁决。
