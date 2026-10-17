# TASK-024-R4 执行回执（新事件终端集合与八文件目录观察）

任务：`docs/tasks/TASK-024-R4_DRAFT.md`（**B 类：DSH 定点修正，GPT 验收**）；依据 `docs/reviews/REVIEW_TASK_024_R3.md`。日期：2026-10-14。
执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务判断与看板：人类主理人。

**范围**：只修改 `scripts/record_demo_human_gate1.py`（起点 `76e95b0d…82f4`／85015）与 `tests/test_record_demo_human_gate1.py`（起点 `a4ad7932…581fde`／156692）；`docs/HUMAN_GATE1_DECISION_GUIDE.md`（`9c8f4409…c2fb`）**未改**（无同步必要）。新增 `docs/EXEC_REPORT_024_R4.md` 与本轮 `task024r4_*` 根；**未另建 tests/ 文件、未改任何旧容器**。

**写后实读身份**：适配器 `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9`（85064）；测试 `0df0982f865d485625c39cdce1744e41158cc7410ee99d97fcd725d85187e55e`（170089）；本回执自身最终 SHA 仅交接给出。

**旧 harness**：`data/human_gate1_decision_tests/task024r1_fault_00/aux_fault_r1.py` = `7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035`／4248 —— **本轮无恢复授权、未修改、未列为授权恢复**；保全副本与全部旧结果冻结。

**基线**：`data/reviews/task024_r3_gpt_20261014_185350/source_hashes_after.json`，实读 **154103** 项、verdict=**NOT_ACCEPTED**、两个确切自指排除。

---

## 1. B1：本次目标事件也通过终端固定集合检查

实现：`_terminal_confirm` 的 `target_dir` 分支现调用与历史事件**同一个** `_confirm_event_layout`——目标目录恰为 `context/receipt/snapshots`、`snapshots` 恰为冻结六文件、有效 `failure.json`/未知项阻断；已消费路径按原 R3 规则逐级 link/junction/reparse 与正常文件/目录条件复查；**不重复检查同一目标**、保留原字节预期、scope 集合与自锁处理；不加载核心、不解析业务 JSON、不重建材料、不增加第三/第四轮语义消费。

实测（两个独立新 scope；包装真实 `_source_snapshot`，先调用原函数并返回原值，在其返回后各注入**恰 1 次**）：

| 注入 | 本次 save | 定位 field | failure | 撤销 wrapper 后 verify |
| --- | --- | --- | --- | --- |
| 目标 `unknown.json` | **Blocked** | `event_0001` | **恰七键**、边界权限 false | **仍拒绝** |
| 目标 `snapshots/unknown.json` | **Blocked** | `event_0001/snapshots` | 恰七键、边界权限 false | **仍拒绝** |

两例均保留故意新增文件与失败现场，未删除 failure/未知项凑成功；旧事件与来源字节未变（同轮其他检查与来源快照比对通过）。**正常对照**：未注入的新 scope 保存 **returned**，随后只读恢复 **returned**。

## 2. E2：目录观察按角色覆盖既定输入文件的确切字节

实现：`bounded_dir_scene` 除首层文件（长度 + SHA + relative）外新增 `subdir_file_scenes`——子目录内每个文件记录长度、SHA 与相对路径；prepare 的 `batch_dir` 与 `store.verify` 输入目录均按该角色规则记录**真实存在性/类型/长度/文件 SHA 与固定目录集合**，`store.save` 的 `out_dir` 仍为**输出角色**（建立前不存在 → 写后六文件）；**同一角色规则同时用于完整输入描述与三个时点指纹**；读取有界（首层/子目录各 ≤32 项），不 rglob 项目/data/历史根，异常现场记实际原因。

实测（同一真实批次，逐项只改本轮故意目标后恢复）：对 `checks/quality_report.json`、`source/input.xlsx`、`logs/checker.stdout.txt`、`code_snapshot/check_demo_data.py` **各只加一个 LF** → 目录场景**指纹均变化**、差异**恰定位到该 relative**、恢复后指纹**回到原值**（四项全真）。

**辨识度控制（真实 prepare 恰一次）**：在观察器返回后、所属公开 API 收尾前只改 `checks/quality_report.json` 字节，八项判据全部为真——`prepare_called_once`、`injected_once`、第二时点干净、**第三时点检出**、`mutation_paths == ["checks/quality_report.json"]`、**共享正式审核规则拒绝**、恢复后指纹回原值、公开 prepare 正常返回。控制期间暂时清空其他探针登记的 `EXPECTED_PATHS`，证明完成后按**隔离控制**单列并写入 `control_proof`（原件通过 / 坏候选失败分列；**未清除审核失败冒充原件通过**，**未放宽** `expected_mutation`）。`store.verify` 六文件输入与 `store.save` 输出“前不存在→后六文件”正常控制沿用既有检查通过。

## 3. 定稿入口、计数与未执行项

定稿入口：既有套件（`R4-*` 具名检查 5 项为等价明确小入口；卡允许），**全新容器** `data/human_gate1_decision_tests/task024r4_run_04`：

```text
93 项检查 / 0 失败 / 退出码 0；写盘后审核 8 项全 OK；失败支配 status=PASS、failures=0
逐层独立聚合（settrace）== 完整条目 == 唯一 ID，cross_check_delta=0：
  冻结 prepare 118、真实 P1 136、store.save 34、store.verify 102
核心观察条目 526；登记 adapter prepare 36 / save 44 / verify 69；冻结接收器 3（退出码 0/0/1）
冻结 store.save 计数 34、store.verify 计数 102（与逐层条目一致）
```

**未执行项**（记 `null`+原因）：宿主/控制器、标准化/装载/DB/筛查、Gate2、真实初判、`0009`、AI/终判、网络/UI/ERP、强身份认证、真实批次批准、跨 scope 历史发现、直接 checker CLI（0 次并记原因）、**新建真实 junction**（环境未建立，路径规则沿用既有控制）；子进程内部未知核心次数为 `null`。未重跑 TASK-021/022/023 历史入口、writer/loader 大组与原完整 88 项（按卡，本卡不要求）。

**旧 R3 扫描计数差异（分列，不回写旧回执）**：R3 交接声明「普通 changed 仅两文件 + 单列授权恢复、允许新增 3043」；**实际本次保存结果**为——R3 基线 151000 项 → 实扫 154041、普通 changed 两文件、授权恢复 `7506a64b…`、允许新增 3043；本轮基线 154103 项 → 实扫 155572、普通 changed 两文件、允许新增 1469。差异来自两轮基线不同（R3 评审基线已含 R3 期新增），非同一轮重复遍历所致。

## 4. 最终保护扫描（扫描后仅有限登记元数据）

扫描脚本 `data/human_gate1_decision_tests/task024r4_run_04/scan_protection_r4.py`，结果 `protection_result.json`：

| 项 | 值 |
| --- | --- |
| 基线 | `task024_r3_gpt_20261014_185350/source_hashes_after.json`（**154103** 项、NOT_ACCEPTED、两确切自指排除、无前缀兜底） |
| 实扫 | **155572** 文件 |
| **普通 changed** | `scripts/record_demo_human_gate1.py`、`tests/test_record_demo_human_gate1.py`（**仅允许的三个文件中的两个**；指南未改）→ **范围外变化 0** |
| 旧 harness | 实际 `7506a64b…1035`，与基线一致、**不在 changed 中、不列为授权恢复**（`ok=true`） |
| missing / 读取错误 | **0 / 0** |
| 范围外新增 | **0**（允许新增 1469 项按确切路径与本轮 `task024r4_*` 根登记） |
| 退出码 | 0 |

扫描后动作：仅按身份有限登记本回执（不改实现/测试、不重复遍历全树）。

## 5. 过程偏差与边界

1. 嵌套字节纳入目录指纹后，先前“故意注入”的探针（S9 晚变更、R3 未知项注入、内存对象第三时点控制）会被三时点/正式审核判为异常变化；已把“预期变更”改为**基于实际差异路径**判定（`mutation_paths ⊆ EXPECTED_PATHS`，或内存对象控制），**未放宽**普通异常变化的通过条件。
2. 本轮未触碰旧 harness、旧回执、旧故障结果与其他冻结文件；`task024r4_*` 为唯一新增根。
3. 边界不变：三 API/无 CLI、32 材料/14 代码、封套/store/锁/限定历史/false 权限、D1/D2/D3 与真实业务范围均未改；真实批准 `null`、宿主开发态 `0008`、`next=false`、AI=false；`APPROVE` 保存不等于执行许可。

## 6. 停止点

完成后停止本卡实施交 GPT 终审；**验收通过前不推进 TASK-025、Gate2、宿主或真实初判**；不生成真实批准、`0009` 或 AI 决定；若需扩大范围或改变规则/权限/协议，先停并升级。业务决定与看板由人类负责。
