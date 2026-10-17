# 项目最终验收入口（合成 CAAT 演示，至人类独立初判 + 四相符 L1）

用途：整体完成时回 Codex 最终验收的**唯一入口**。本文件只索引已发布身份与证据，不重复、替代任何 review_result、回执或快照；不从聊天推断授权。全部内容为**合成数据**上的技术记录，不是真实批次批准、不是身份认证、不实施 AI 建议与人类终判。

## 1. 最后接受身份（以文件为准）

| 项 | 路径 | 身份 |
| --- | --- | --- |
| 最后接受 | `data/reviews/task046_dsh_20261017_01/review_result.json` | 见该文件 `review_file_sha256` / `accepted_baseline_sha256` / `accepted_baseline_entries` |
| 最后接受基线 | `data/reviews/task046_dsh_20261017_01/source_hashes_after.json` | 见该文件（本轮发布，快照排除自身与 review_result） |
| 最终评审 | `docs/reviews/REVIEW_TASK_046.md` | 见 review_result |
| 本轮交付（TASK-046，已验收） | `docs/EXEC_REPORT_046.md` | 见该回执与 `data/runtime_initial_judgment_recording_tests/task046_finalization/delivery.json` |
| 扫描后自身元数据 | `data/reviews/task045_dsh_20261017_01/final_readback.json` | 记录基线/评审/回执的实际长度与 SHA |

历史接受基线（均未被替换，保留原件）：TASK-039-R1 168839 项 / `43fa7288b88d3deb806d215352ce1a91b02f841a32eebdd03b3f0f9ec02ccae2`；TASK-040-R1 171449 项 / `26a0adf7a2352cb352f88b090999bd457733ef3e5fe3ff6f3888ae8acd3a981a`；TASK-041 173529 项 / `5a05a245323fdb5aae58b00e331cc2a054ae1c61c6381a7a0b797a4c86051319`；TASK-042 173950 项 / `6f8c27876367e97b225cd4f31c1ada6b25b04f153b5dd096d0af4f61461d4537`；TASK-043 174820 项 / `c65c27cb9969df75…`；TASK-043-R1 175436 项 / `8ceb0df0ef0250ad514e7c4a41723bc7738f43cf2b95f8fd5f2808ca084744be`；TASK-044 175375 项 / `849d22022cab133be3c13c518be40a9a15504b91f7aa53d44d64f854a86bd28f`。

## 2. 交接后的任务链（卡 → 执行回执 → 独立 review → 修正闭合）

| 环节 | 卡 | 执行回执 | 独立 review | 结论 |
| --- | --- | --- | --- | --- |
| 起点接受 | `docs/tasks/TASK-039-R1_DRAFT.md` | `docs/EXEC_REPORT_039_R1.md` | `docs/reviews/REVIEW_TASK_039_R1.md` | ACCEPTED（168839 基线） |
| 运行层初判保存/恢复 | `docs/tasks/TASK-040_DRAFT.md` | `docs/EXEC_REPORT_040.md` | `docs/reviews/REVIEW_TASK_040.md` | NOT_ACCEPTED（观察快照） |
| 定点修正 | `docs/tasks/TASK-040-R1_DRAFT.md` | `docs/EXEC_REPORT_040_R1.md` | `docs/reviews/REVIEW_TASK_040_R1.md` | ACCEPTED（171449 基线） |
| 硬化 | `docs/tasks/TASK-041_DRAFT.md` | `docs/EXEC_REPORT_041.md` | `docs/reviews/REVIEW_TASK_041.md` | ACCEPTED（173529 基线） |
| 演示 + AI 扩展点 | `docs/tasks/TASK-042_DRAFT.md` | `docs/EXEC_REPORT_042.md` | `docs/reviews/REVIEW_TASK_042.md` | ACCEPTED（173950 基线） |
| 输入契约 v1 | `docs/tasks/TASK-043_DRAFT.md` | `docs/EXEC_REPORT_043.md` | `docs/reviews/REVIEW_TASK_043.md` | ACCEPTED（174820 基线） |
| 输入补充 v1.1（P02 凭证） | `docs/tasks/TASK-043-R1_DRAFT.md` | `docs/EXEC_REPORT_043_R1.md` | `docs/reviews/REVIEW_TASK_043_R1.md` | ACCEPTED（175436 基线） |
| 账证相符 L1 | `docs/tasks/TASK-044_DRAFT.md` | `docs/EXEC_REPORT_044.md` | `docs/reviews/REVIEW_TASK_044.md` | ACCEPTED（175375 基线） |
| 账实相符（银行交易级） | `docs/tasks/TASK-045_DRAFT.md` | `docs/EXEC_REPORT_045.md` | `docs/reviews/REVIEW_TASK_045.md` | ACCEPTED（175890 基线） |
| 四相符演示集成 + 版本声明集 | `docs/tasks/TASK-046_DRAFT.md` | `docs/EXEC_REPORT_046.md` | `docs/reviews/REVIEW_TASK_046.md` | ACCEPTED（本节基线） |

NOT_ACCEPTED 与各轮观察快照、失败/半成功现场、开发迭代根全部保留：`data/reviews/task040_dsh_20261017_01/`、`data/reviews/task040_dsh_r1_20261017_01/`、`data/reviews/task041_dsh_20261017_01/`、`data/reviews/task042_dsh_20261017_01/`、`data/reviews/task043_dsh_20261017_01/`、`data/reviews/task043r1_dsh_20261017_01/`、`data/reviews/task044_dsh_20261017_01/`、`data/reviews/task045_dsh_20261017_01/` 及对应 `task04*.0*` 运行/测试根。

## 3. 实际最终交付身份

| 交付 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py`（运行层适配器） | 404971 B | `f5c7c3967abc8257f1eff5c55487f6ff88c68d0879161e715dc43c95e0fad4b7` |
| `scripts/run_runtime_demo.py`（四相符演示） | 34519 B | `8f264a2d9f06b7ea3d82f8f0ef51f343f6c126ba0f6affcf58babe3f162bf40a` |
| `scripts/input_contract_v1.py`（输入契约校验，版本声明集 1.0/1.1） | 36194 B | `622f47b9acb54a3c943bb4fbaa56923718cc88a0b7976a560685b59afad8b351` |
| `scripts/voucher_match_v1.py`（账证 L1） | 38985 B | `8daa8cd858fcf435797f8cb2ee19c4692c17d2285a2f4c696de9a9c3bb4cae84` |
| `scripts/bank_reconcile_v1.py`（账实交易级） | 27824 B | `ef802fde1408cba06861bc821180c02510dfc20cff193a6f60c3f20797de2e88` |
| `tests/test_runtime_initial_judgment_recording.py` | 69930 B | `ac9c95730065e46c0da0139ac1f37cc169d13ffe5815618e03c518c114edc75a` |
| `tests/test_input_contract_v1.py` | 16322 B | `7ea474ab872dbf834c85e6ab448a72238ab78059fe7faddc14c39274b38fc647` |
| `tests/test_voucher_match_v1.py` | 19470 B | `e680bf9cf3604b5c4f2e326202d06d9bc945ed54a5c7567dec00d1f3316e113b` |
| `tests/test_bank_reconcile_v1.py` | 15453 B | `2a442b46029fad8b3b0bd4eaa2223089f33530f2e3f31843106323e429ef4af1` |
| `docs/RUNTIME_INITIAL_JUDGMENT_RECORDING_GUIDE.md` | 7202 B | `8cef774549ffc4d15ce92adc4da90e35c7e57421e1a1f744ca9b34c9f6de7bb7` |
| `docs/RUNTIME_DEMO_AND_AI_EXTENSION_GUIDE.md` | 5182 B | `06ae294a758a316543dd7936ccdac92b03b0d818cf057d5147235675cad14e1b` |
| `docs/INPUT_CONTRACT_V1.md` | 6597 B | `0b3fa7b471c99e6a0f650b2bc8a8481cf261eae70eb5a3c85617b8c51ad32299` |
| `docs/ACCOUNT_VOUCHER_MATCH_GUIDE.md` | 6858 B | `944a9917bb6249bab7e272aec979cf399bd35526c308a76916bf4dfa63b11c44` |
| `docs/BANK_RECONCILIATION_GUIDE.md` | 5878 B | `67ae604d99d3b326b2801e6812f41fa124a7f44b25cc29e293761b14a24568aa` |
| `docs/JOB_DEMO_PLAYBOOK_20261017.md`（求职演示稿） | 14339 B | `1b4c265d28c4e11341f81348ce658bb1b32acc8ca67803ce77fbaabfd93efe8f` |

profile：19 公开 API / 17 代码清单 / 40 项 Gate1 材料；版本 `TASK-040-runtime-registry-1.0`、`TASK-040-code-manifest-1.0`、`TASK-040-runtime-gate1-1.0`。本入口文件自身身份以文件为准（不列自哈希）。

## 4. 演示证据（具名、可复演）

- 四相符单命令：`.venv\Scripts\python.exe -B scripts\run_runtime_demo.py --out-dir data\runtime_initial_judgment_recording_tests\task046_demo_01` → exit 0；`demo_summary.json` 含：
  契约 `INPUT_V1_ACCEPTED`（凭证 8：回单 3/审批 2/其他 3；links 8；流水 3）、账证 **8/8 MATCHED**（P02 证据 V-APR-0002/V-BR-0003；R02 抽样 AP01/P01/P02/R01）、账实 **3/3 MATCHED**（REFERENCE_INDEX；期间合计 OUT 1,000,000 == 已结算付款、IN 100,000 == 退款，差异 0；未达账项 0；人类结论 null）。
- 证据根：`data/runtime_initial_judgment_recording_tests/task046_run_01/`（command.json、demo 与两个负例的 stdout/stderr、只读前后快照、四 CLI 回归日志）；演示运行根 `task046_demo_01/`（demo_readme.md、task043_input_check、task044_match、task045_reconcile）；人读摘要：`task046_demo_01/demo_readme.md`。
- 负例（现场保留）：`--evidence-input` 指向 v1（P02 缺证）→ 账证 2 条 `MISSING_VOUCHER`、演示退出码 1（`task046_demo_v1_neg`）；输入版本改为未知 1.2 的副本 → 契约 `MANIFEST_VERSION` 拒收、演示退出码 1（`task046_demo_badver_neg`）。原输入不改（副本注入）。
- 四 CLI 控制（TASK-046 重跑，各轮均为 0/1/1/1）：正常 0、内容反例 1、台账替换 1、末次读后漂移 1（`task046_regress_*`）。
- 只读扩展点（TASK-042 接受轮证据沿用，inspect 模式未改）：`--inspect-record` → `zero_write=true`、`algorithm_builds=0`、不导入适配器。
- 调用图（TASK-042 实测）：save n=0 → prepare 1 / store.save 1 / 后 history 1（总 2）/ store.verify 1 / core 2，Gate1 6、Gate2 5、inspect 5/2/1/1、render 1、gate store/core 11/11、冻结准备器 6、算法·SQL·装载·复算·事实 build 0；verify m=1（history 1 / prepare 0 / save 0 / store.verify 1 / core 1）、m=2（2/2）。

## 5. 保护与历史损失

各轮接受均执行唯一一次全树扫描并登记逐路径新增：`data/runtime_initial_judgment_recording_tests/task040_finalization/`、`task040_r1_finalization/`、`task041_finalization/`、`task042_finalization/`、`task043_finalization/`、`task043r1_finalization/`、`task044_finalization/`、`task045_finalization/`、`task046_finalization/`（本轮）与架构端各 review 根 `protection_result.json`。相对各基线：既有 changed 仅卡允许的几件（TASK-042/043/044/045 轮为 0，TASK-046 轮恰四件）、missing 0、读取错误 0、未登记新增 0。

已知历史损失与偏差（逐项保留、不追认、不重建）：139 项历史损失（`data/reviews/task026_r3_gpt_20261015_043939/remaining_loss.json`）、27 项恢复（同根 `restoration_journal.json`）、R5 的 326 项越界（`data/reviews/task024_r5_gpt_20261014_213428/unauthorized_record_roots.json`）、19 项命名偏差（`data/reviews/task027_r1_gpt_20261015_165854/protection_result.json`）、TASK-030 保留锁 41 B / `c78006d5…0e47`（原位置冻结）。

## 6. 人类授权与夹具来源（原文/原字节）

- 交接授权与平台转移：`docs/handoffs/20261017_DSH/HANDOFF_MANIFEST.json`（含授权原文与时点）。
- 正式契约生效与 D1/D2/D3：`docs/AUDIT_CONTRACT.md`（`174a021b…`）、`docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md`（`042086cb…`）。
- 演示优先与 AI 延后：`docs/decisions/DECISION_20261017_DSH_DEMO_SCOPE_AND_AI_DEFERRAL.md`（`ee0272fc…`）。
- 四相符范围：`docs/decisions/DECISION_20261017_DSH_FOUR_MATCH_SCOPE.md`（`DSH-SCOPE-20261017-02`）。
- 夹具原文：Gate 决定 `data/decision_protocol_checks/task020r2_run_01/fixture_values.json`（`6d8126ae…`）；初判 event1 `data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json`（`81521ff0…`）、event2 `data/reviews/task036r1_gpt_20261016_193749/human_history_fixture_supplement.json`（`e7bb8813…`）；只读批次 `data/batches/task027r1_run_04/batch_normal`（input.xlsx `8f6f2a98…`）；canonical 输入 `data/evidence_inputs/task043_v1_1/`（manifest `151c35fc…`），v1 `data/evidence_inputs/task043_v1/`（`5a9c3bb3…`）冻结保留。

## 7. 未执行与已知限制

真实数据、真实批次批准、强认证、AI 建议实施、人类终判实施、物理 junction 绕过、非合作篡改证明、并发双进程真实竞态：均未执行（`null` + 原因）。RC-03/15/16/18/19/23/28/33/34/35/36/37 未执行（需第二注册叶/第二事件链、会永久锁定唯一正常链或超链预算），case_map 三层据实。旧适配器 290568 B 正文无本地副本，只能以"旧文件未登记变化 0 + 旧 17 签名与既有指南一致"承担。TASK-042 失败迭代现场登记路径不精确（实际保留于五类业务根），已在 `REVIEW_TASK_042.md` §5 备案。账表/账账未做（需报表层输入与另行授权）；账证/账实只做字段级/交易级 L1，未看影像、未做外部查验、不证明凭证/流水真实；银行余额核对未做。

## 8. 当前真实状态

`real_approval=null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。合成链至人类初判 + 账证/账实 L1 已可演示；后置 AI 仅预留**只读**扩展点，未实施；人类终判未实施。任何后续真实批次、AI、终判、真实数据与强认证均需人类另行授权并新增协议/卡。TASK-046 已 ACCEPTED（见本轮 review_result）。
