# TASK-024-R5 执行回执（测试故障豁免限于本次注入）

任务：`docs/tasks/TASK-024-R5_DRAFT.md`（**B 类：DSH 定点实施，GPT 验收**）；依据 `docs/reviews/REVIEW_TASK_024_R4.md`（R4 暂未通过，唯一剩余问题在测试侧）。日期：2026-10-14。
执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务判断与看板：人类主理人。

**范围**：**唯一修改的既有文件**是 `tests/test_record_demo_human_gate1.py`（起点 `0df0982f865d485625c39cdce1744e41158cc7410ee99d97fcd725d85187e55e`／170089）。新增 `docs/EXEC_REPORT_024_R5.md` 与 `data/human_gate1_decision_tests/task024r5_run_01`（98 项过程证据）、`task024r5_run_02`（R5 定点入口）与 `data/batches/task024r5_run_01|run_02`。**未新建决定存储事件、未授权新记录根、未改任何旧样本或旧容器、未另建 tests/ 文件。**

**写后实读身份**：测试 `a5126fdd1d3c7f80a7b9eb0e8649d5737a772294d65ea7b8fed94196c89ee4a0`（188793）；本回执自身最终 SHA 仅交接给出。

**生产适配器（本期完全冻结，未改）**：`scripts/record_demo_human_gate1.py` = `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9`（85064）。
**指南（冻结未改）**：`docs/HUMAN_GATE1_DECISION_GUIDE.md` = `9c8f4409a1c964a65fe64139424795e635ecdf33a55f1724fec683fe9998c2fb`（10300）。
**旧 harness（冻结未改）**：`data/human_gate1_decision_tests/task024r1_fault_00/aux_fault_r1.py` = `7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035`（4248）；本轮**没有历史恢复例外**。

**基线**：`data/reviews/task024_r4_gpt_20261014_201447/source_hashes_after.json` = `f0990b7135c425a22595efccf1184f0929fac859aa5d5bac2b59c7d430c5fc67`、**155639** 项、verdict=**NOT_ACCEPTED**、两个确切自指排除。

---

## 1. 唯一根因与修正

**根因**：`EXPECTED_PATHS` **跨 API 调用累积**；路径分支只比较“路径是否曾被登记”，没有“**这一轮是否处于注入窗口**”的要求。结果旧探针登记过的路径在后续 active=false 的新变化中仍被判为“预期”，被正式审核接受。

**修正（仅测试文件）**：
1. 以 `MUTATION_WINDOW = {"paths", "active"}` 表示**当前一次 API/观察窗口**，取代累积集合；历史登记只写入**只读证据** `EXPECTED_PATH_LOG`（不参与判定）。
2. `finalize_api_time_point()` 在**所属公开 API 收尾**时按窗口判定：`expected_mutation = 有差异 且 (差异路径 ⊆ 本窗口登记 或 内存对象控制且窗口 active)`；**随后清空窗口**（`paths.clear()`、`active=False`）。
3. 收尾路径覆盖正常 / `Blocked` / `Error`（均在公开 API 包装的 `finally` 中执行），因此**异常收尾同样使窗口失效**。
4. 既有 S9 / R3-B1 / R1-B1（含 B1.5 save 接缝）故意探针**只调整其窗口登记与还原方式**（登记本次注入目标、记录原字节用于恢复），**不改变其生产期望结果**。
5. 未登记、错误窗口、窗口内额外目标的变化一律进入**实际正式审核**失败路径；**未**通过“预先清空残留”“发现异常后追加允许路径”“仅凭路径相同/历史探针改过/全局开关/三时点有差异”获得豁免；**未**放宽 `expected_mutation` 使普通异常变化通过。

## 2. 五类最小控制（同一新批次、真实冻结 prepare，调用**真实 `evidence_audit`**）

每条控制都用真实 `evidence_audit` 审核**只含该条核心观察的隔离候选**（并含一条完整 anchor API 记录以保持计数/关系闭合），不复制其条件、不改写其文本：

| 控制 | 内容 | 实测结果 |
| --- | --- | --- |
| **R5.1** 正常调用 | 无注入 → 三时点一致 | 三时点一致 **true**；真实 audit **通过**（`ok=true`） |
| **R5.2** 合法故意窗口 | 本窗口登记并注入 `checks/quality_report.json` LF | 检出差异 true、定位 `["checks/quality_report.json"]` true、`expected_mutation=true`（预期控制分列）、真实 audit 接受该控制条目；**结束后窗口失效** |
| **R5.3** 紧接的下一调用 | **无新登记**但同路径隔离变化 | 调用起点窗口为空 true；`expected_mutation=false`；**真实 audit 拒绝**（定位“第三时点不一致”） |
| **R5.4** 窗口内额外未登记目标 | 窗口登记 `quality_report`，同时改 `logs/checker.stdout.txt` | 检出额外路径 true、**不被豁免**（`expected_mutation=false`）、**真实 audit 拒绝**并定位额外差异 |
| **R5.5** 异常/拒绝收尾 | 调用收尾（含异常/拒绝）后 | 窗口与登记**已清空**、`active=false`，后续普通调用三时点仍一致、不继承登记 |

控制条目在证明完成后按**隔离控制**单列（写入 `control_proof`），原件通过 / 坏候选失败分列；**未删除失败、未把坏观察改标预期后冒称原件通过**。

## 3. 定点入口（真实 `--only r5`）与证据闭合

```text
.venv\Scripts\python.exe -B tests\test_record_demo_human_gate1.py \
    --only r5 --out-dir data\human_gate1_decision_tests\task024r5_run_02
→ R5 定点模式：5 项检查、0 项失败；退出码 0
```

- 检查集合**仅 `R5.1`–`R5.5` 五项**，**实际跳过原套件各项检查**（非仅命名）。
- 收尾复用与主入口**同一套**逻辑：内存定稿 → 一次写入 → 同缓冲读回 → `compare_expectation` **ok=true** → **真实 `evidence_audit`** `ok=true` → 台账落盘 + 读回（同缓冲 **true**）→ 字节漂移 `[]` → 写盘后审核无失败 → **失败支配**（本次无失败，退出码 0）。
- 本模式真实计数：登记 prepare **6**、save 0、verify 0；`store.save`/`store.verify`/P1 入口调用 **0**（本模式未调用；未观察的子进程内部核心次数按 `null`，此处 0 为真实调用数）、接收器 3、核心观察 **6** 条、窗口登记日志 **3** 条。
- 产物（完整证据路径）：`data/human_gate1_decision_tests/task024r5_run_02/{calls,samples,checks,failures,summary,core_observations}.json`、`evidence_ledger.json`、`ledger_readback.json`、`receiver_C06b_normal*.{stdout,stderr}.txt`、`receiver_C06b_currency_usd*.{stdout,stderr}.txt`。
- `not_executed`（记 `null`+原因）：宿主/控制器、标准化/装载/DB/筛查、Gate2、真实初判、`0009`、AI/终判、网络/UI/ERP、强身份认证、真实批次批准、跨 scope 历史发现、新建 junction；直接 checker CLI 记 **0** + 原因。
- 过程证据（**引用、未重跑**）：`data/human_gate1_decision_tests/task024r5_run_01` = 98 项检查 / 0 失败（含 R5 五类控制进入主入口后的回归）；R4 定点入口 `task024r4_run_04` = 93 项 / 0 失败；旧 R1 两个故障 7/7、R3 四轮 harness、R4 最终扫描等结果均按原样保留，未重跑、未回写。

## 4. 旧交接/扫描数字差异（按来源说明，不回写旧回执）

| 来源 | 声明 | 实际保存结果 |
| --- | --- | --- |
| R3 交接 | 普通 changed 两文件 + 单列授权恢复、允许新增 3043、基线 151000 | 实扫 154041、普通 changed 两文件、授权恢复 `7506a64b…`、允许新增 3043（与声明一致） |
| R4 交接 | 基线 154103、实扫 155572、changed 两文件、允许新增 1471 | 与声明一致（本轮再次确认守护 `changed` 仅两实现文件、旧 harness 未列授权恢复） |
| 本轮 R5 | 基线 `task024_r4_gpt_20261014_201447` = **155639** 项 | 见 §5（**changed 只能是测试文件**） |

差异来源均为**两轮基线不同**（各轮评审基线已含前轮新增），非同一轮重复遍历所致；未做补偿性重跑。

## 5. 最终保护扫描

- 结果（脚本 `data/human_gate1_decision_tests/task024r5_run_02/scan_protection_r5.py`，结果 `protection_result.json`）：基线 `f0990b7135c425a22595efccf1184f0929fac859aa5d5bac2b59c7d430c5fc67`、**155639** 项、verdict=NOT_ACCEPTED、两确切自指排除；实扫 **156059** 文件 →
  - `changed` = `['tests/test_record_demo_human_gate1.py']`（**仅测试文件**，即本卡唯一允许修改的既有文件）；`out_of_scope_changes=[]`；
  - 冻结身份不一致 = `[]`（生产适配器 `d8ace42f…`、指南 `9c8f4409…`、旧 harness `7506a64b…1035` 均未变，且旧 harness 未列为授权恢复）；
  - `missing=0`、`read_errors=0`、**范围外新增 0**；允许新增 **420** 项按确切路径与本轮 `task024r5_run_01|run_02` 根、明确场景后缀逐项登记；`prefix_exemption_used=false`；扫描退出码 0。
- 扫描后动作：仅按身份有限登记本回执（不改实现/测试、不重复遍历全树）。

## 6. 停止点

完成后停止本卡实施交 GPT 终审。**未关闭任何卡片、未推进 TASK-025**；真实批准 `null`、宿主开发态 `0008`、`next=false`、AI=false；不接 Gate2、宿主、真实初判、`0009`、AI 或终判；`APPROVE` 保存不等于执行许可。业务判断与看板由人类负责。
