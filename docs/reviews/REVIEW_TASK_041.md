# TASK-041 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-17，DSH 架构/测试验收端对 TASK-041 硬化独立复验。上一轮 `REVIEW_TASK_040_R1` §5 记录的全部残差（S8 双构造、verify 末段、S5 schema 复测、死代码/静默路径、遗留项）已闭合，且交付在架构端自跑下可复现。本接受覆盖**合成运行层初判保存/只读恢复的硬化实现**，不是批次批准、不是身份认证，不开放 AI/终判/真实数据。

## 1. 交付身份（实读同缓冲）

| 交付 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py` | 404971 B | `f5c7c3967abc8257f1eff5c55487f6ff88c68d0879161e715dc43c95e0fad4b7` |
| `tests/test_runtime_initial_judgment_recording.py` | 69930 B | `ac9c95730065e46c0da0139ac1f37cc169d13ffe5815618e03c518c114edc75a` |
| `docs/RUNTIME_INITIAL_JUDGMENT_RECORDING_GUIDE.md` | 7202 B | `8cef774549ffc4d15ce92adc4da90e35c7e57421e1a1f744ca9b34c9f6de7bb7` |
| `docs/EXEC_REPORT_041.md` | 8444 B | `297d15b60161527eb2ae37e9cc0a7edd50f4bdb3f3a1b55bcab480dd9e9eb048` |

起点 R1 四件身份与 `data/reviews/task040_dsh_r1_20261017_01/source_hashes_after.json`（171449 项 / `26a0adf7…`）实读一致；`task040_run_05`、`task040_dev_01`、`task040_r1_run_01/02`、两轮评审根与 `REVIEW_TASK_040*.md` 原样冻结。

## 2. H1—H5 闭合（实读代码 + 实际运行）

- **H1 S8 双构造成立**：L6213-6242（save）与 L6627-6643（verify）中，候选 `_build_success_040` 只取真实 `store.save` 返回 + 真实 H1/Hc history 返回 + writer 缓冲；预期 `_rebuild_success_040` 只用目标叶六文件字节重建 `storage_verification` 十一键（`_rebuild_storage_verification_040` 调冻结 store `_build_return(VERIFIED, manifest, buffers, objects)`）、E1/H1 独立重建历史、`_descriptor_from_capture_040` 重建文件描述、叶内/登记 identity；`success = candidate_result`，两对象互不复制。公共路径可达性实测 `h1_candidate_control`：包装候选构造器（非直调审核）→ `Blocked result.record_relative`，失败前 `store.save=1 / store.verify=1 / core=2`，三封装+failure+锁保留。硬化内部调用 `hardening.rebuild_success` 单列（save/verify 各 1），未并入业务公式。
- **H2 verify 末段成立**：L6647-6649 传 `target_leaf/target_captures`，复确认目标叶六件集合与 failure，全程只读。
- **H3 S5 schema 复测成立**：L5853-5857 在 `_pre_store_confirm_040` 内复测 `sql/demo_schema.sql`、`normalize_demo_data.py`、`store_demo_sqlite.py`；`h3_schema_drift` 实测 `Blocked sql/demo_schema.sql`、`store=0/core=0`、现场保留、事后精确恢复。
- **H4 死代码/静默路径成立**：`_initial_snapshot_objects_040`/`_initial_target_name_040` 已不存在；`_confirm_initial_history_040` 对非目标缺缓冲显式 `Blocked history.entries[i]`（`h4.missing_buffer_field=history.entries[1]`）；坏 envelope failure 缺键/未知键精确到 `failure.reason`/`failure.zzz_unknown`（L6303/L6306）。
- **H5 遗留**：store Blocked 的 `reasons` 原样复制；旧适配器 290568 B 正文不可证明继续如实承担，未伪造基线。

## 3. 架构端独立实际运行（不复用执行端结论）

- **正常链复跑** `data/runtime_initial_judgment_recording_tests/task041_dsh_01`：**87/87 checks、api=25、core=476、exit 0**；8 条具名失败场景 field/stage 全部复现（`store.submission.assessment`、`write.expectations.json`、`write.context`、`write.receipt`、`release.lock`、`context.prepared_request.request_sha256`、`result.record_relative`、`sql/demo_schema.sql`）。
- **四项 CLI**（新进程、新 out-dir）：**0 / 1 / 1 / 1**，失败摘要与执行端一致（`api_records_mismatch:call_004`、`ledger_*`、`drift:checks.json`）。
- **内容独立重算** `recompute_041.py`：**41/41 PASS**（五载荷 FILE+FP、record FP、run_binding/request 角色、封装 FILE 绑定、H0 空/H1=1 叶、旧叶逐字节不变、九/八边界、十二键、`storage_verification` 恰十一键且 save=VERIFIED/context=STORED/verify=VERIFIED、save 图=卡公式且算法/SQL/事实 build 0、`hardening.rebuild_success=1`）。

## 4. 结论与遗留

无阻断项。仍在案、但不属本卡范围：物理 junction（无权限）、真实数据、强认证、AI、终判、并发双进程真实竞态、非合作篡改证明（null + 原因）；RC-03/15/16/18/19/23/28/33/34/35/36/37 未执行（第二注册叶/第二事件链、会永久锁定唯一正常链或超链预算），case_map 三层据实。旧适配器 290568 B 正文无法证明，只以"旧文件未登记变化 0 + 旧 17 签名与既有指南一致"承担。

真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。本接受不改变该状态。

## 5. 接受与下一卡

发布新接受基线 `data/reviews/task041_dsh_20261017_01/source_hashes_after.json` 与 `review_result.json`，接受 TASK-041 硬化实现及证据。按人类 2026-10-17 指示（`docs/decisions/DECISION_20261017_DSH_DEMO_SCOPE_AND_AI_DEFERRAL.md`）：优先做到人类初判为止、使项目可演示；后置 AI 只预留只读扩展点，不实施。下一卡 `docs/tasks/TASK-042_DRAFT.md`：运行层演示就绪（一条命令、可阅读输出）+ AI 只读扩展点文档与只读消费者实证。
