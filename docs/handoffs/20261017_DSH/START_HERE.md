# audit_sa_project → DSH 交接入口

交接日期：2026-10-17（Asia/Shanghai）。人类因Codex周额度转移平台，DSH接续架构验收与执行实施；后续是否回到Codex及何时回归由人类安排。本交接只新增说明和确切身份登记，不实施TASK-040、不改既有任务卡、生产、测试、指南、接受快照或看板。

项目根：`D:\harness work\audit_sa_project`。Windows / PowerShell。Python：`D:\harness work\audit_sa_project\.venv\Scripts\python.exe`；所有Python运行带 `-B`。

## 1. 分角色接任

建议分别使用两个DSH会话，由人类把对应交接说明交给它们。架构端独立验收与制定卡；执行端按卡实现和自测。不要让同一轮“执行自报PASS”代替独立验收。平台转移不要求每张卡必须等待Codex回来；DSH架构端可在同一业务授权内接续有限任务、独立验收及下一卡。新增业务权限仍由人类决定。

- 架构/测试验收端：读本文件和 `ARCHITECT_REVIEWER_HANDOFF.md`。
- 执行落地端：读本文件和 `EXECUTOR_HANDOFF.md`，直接接续已发布TASK-040。
- 两端都先核 `HANDOFF_MANIFEST.json` 中的实际长度/SHA；权威文件优先于聊天摘要或看板。

可直接给架构端的开场指令：

> 你接任 audit_sa_project 的 Architect / Reviewer。先读 D:\harness work\audit_sa_project\docs\handoffs\20261017_DSH\START_HERE.md 和 ARCHITECT_REVIEWER_HANDOFF.md，核交接清单与最后接受基线。TASK-040已设计、尚无本次交接确认的交付；待执行端交付后独立验收，通过才发布新接受基线并制定下一张有限任务卡。不要修改生产、交付测试或既有指南，不把执行PASS当验收，不开放真实批准/AI/终判。

可直接给执行端的开场指令：

> 你接任 audit_sa_project 的执行端。先读 D:\harness work\audit_sa_project\docs\handoffs\20261017_DSH\START_HERE.md 和 EXECUTOR_HANDOFF.md，核身份后按 docs\tasks\TASK-040_DRAFT.md 完成合成运行初判保存/只读恢复。遵守唯一既有可改文件、允许新增路径、冻结组件和证据保护要求。不得自行修改任务卡/冻结核心或扩大业务权限；定稿交付后停待DSH架构独立验收，不自行推进下一卡。

## 2. 当前准确状态

最后独立接受：**TASK-039-R1，ACCEPTED**。它接受运行层初判保存/恢复的**设计1.1与有限静态检查**，未来两个运行API尚未因本次接受而实现。生产适配器仍是已接受TASK-038版本。

必须按顺序阅读：

1. `docs/reviews/REVIEW_TASK_039_R1.md`。
2. `data/reviews/task039r1_gpt_20261017_100901/review_result.json`。
3. 同根 `source_hashes_after.json`。
4. `docs/tasks/TASK-040_DRAFT.md`，SHA `a1fb5e0f7347c0cfdd1b7ff7c003106c1796da216a2f643c623cd180b2b521a1`。
5. `docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_PROTOCOL_V1_DRAFT.md` 与同目录 `RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_CASES_V1_DRAFT.md`。
6. `docs/reviews/REVIEW_TASK_038.md`，再按需读TASK-034/035-R1/036-R1/037冻结契约与核心。

最后接受快照：168839项，26324874 B，SHA **`43fa7288b88d3deb806d215352ce1a91b02f841a32eebdd03b3f0f9ec02ccae2`**。快照自身及同根review_result不在快照内，后续仅这两条元数据有限确切登记。

适配器 `scripts/runtime_gate1.py`：290568 B，SHA **`ca1139abbe18fc9cd2f1c3ad893f42b8b1b5b5bce28d1ed1216c0434309b6b9a`**。目前17个业务API、17项代码清单、38项Gate1材料；TASK-040计划19个API、17项代码、40项材料，后者不能写成已经实现。

TASK-039-R1独立实际结果：正常111/111、main退出0；角色错误控制退出1/FAIL；三种候选内存摘要角色替换均拒绝；业务入口/导入/新业务链0。一次双口径保护通过，历史139损失单列。动态保存、恢复、句柄、并发等在该文档任务仍null，不是PASS。

TASK-039原版NOT_ACCEPTED及其92项静态PASS原证据保持。TASK-033/035/036也应使用各自已接受R1结果，不能挑原版执行PASS代替修正后的接受身份。TASK-038“保留开发链、另建最终链”是历史特定授权；TASK-040自有开发/最终/失败链上限按其卡，不泛化旧例外。

## 3. 不变的业务和权限边界

这是IT审计CAAT Agent求职作品，当前仅合成采购付款数据。固定澄明商贸有限公司、人民币CNY、2026年9月、截至2026-09-30。整数分；业务ID保持原字符串；主表与分摊分别计算，不能相加称损失。R01—R04是待核查线索，不是舞弊、损失或审计结论。

目标顺序：接收核验 → Gate1 → 标准化/SQLite → Gate2 → SQL筛查 → 独立复算 → 事实底稿 → 人类独立初判保存 → 后置AI建议 → 人类终判。目标包含AI不等于当前已获AI实施许可。

正式契约V1已由人类建立并确认生效。D1采纳契约，D2允许合成Gate决定及独立初判建设，D3批次初判/原因必填、逐条备注可选、有原因的暂不能判断有效。这些不批准任何真实批次，不授权强认证、真实数据、AI或终判实施。

人类是业务决定和真实Gate批准唯一决策者。人类event_id、actor_id、declaration_note、decided_at_raw、assessment、reason不得Agent编造；仅测试可读已登记夹具。程序技术登记时间与人类决定时间分列，日期原文不补时间/时区。夹具中的“通过”只是人类测试字符串，不等于实际业务放行。

冻结开发宿主停0008，保存的是模拟初判；不建0009、不把开发态phase当真实放行。**真实批准null、真实独立初判未保存、next/AI=false。** 运行层合成记录成功、快照保存、计算一致、技术验收均不等于真实批准或身份认证。

## 4. 证据保护及平台转移

不递归删除/移动，不清理锁、探针、失败、半写或旧过程产物。注入只针对本轮自建场景，坏字节具名保全，仅精确恢复本轮单文件原件。读旧脚本可参考定义，不直接执行硬编码旧根的run/main。不为追求数量重跑全部历史矩阵。

139项已知历史损失与新missing分开：

- `data/reviews/task026_r3_gpt_20261015_043939/remaining_loss.json`：166误删中27恢复，仍139缺失；人类确认无已知备份，不能伪造重建或写成零。
- 同根 `restoration_journal.json`：27恢复身份。
- `data/reviews/task024_r5_gpt_20261014_213428/unauthorized_record_roots.json`：326历史越界，不追认。
- `data/reviews/task027_r1_gpt_20261015_165854/protection_result.json` 的declared_out_of_scope_added：19命名偏差。
- `data/runtime/task030_run_01/normal.gate2.lock.preserved_probe/lock.json`：41 B / SHA `c78006d55489a9ad1b10cc98a081c3bc8135858c5b9040b7d7d5079409cf0e47`，原位置冻结。

仅有这四份交接文件不能替代完整工作区及证据。转移应保全源字节、目录关系及旧证据，不自动换行/格式化/迁移凭证；.venv可依平台另行处理，但依赖变更不得混入生产交付。若DSH没有Windows或项目文件访问能力，先明确能力缺口，只做能证实的文档/静态工作，不能声称真实Win32句柄/新进程业务测试已运行。换根路径需登记环境映射，不能批量改旧材料中的路径。

本交接仅做有限身份读回，**没有再做全树扫描，也没有发布替代接受基线**。四份交接是接受基线之后、由本次人类交接请求授权的新确切路径；后续扫描应将HANDOFF_MANIFEST列出的四路径作为独立已知授权增量核SHA，不把整个handoffs目录设为豁免。接受快照/旧review_result仍原件，不能为了消除新增而改它们。

## 5. TASK-040之后与最终回归

先完成TASK-040交付和DSH独立验收。NOT_ACCEPTED则少量可复现阻断与定点修正卡；ACCEPTED才发布新基线并评估下一卡。未来任务号由架构端按实际最新文件确认，不能提前把本交接视为TASK-041及后续所有实施授权。

后续先对照目标链找实际缺口，再设计有限任务，避免无休止扩大测试平台或重构。AI建议必须在人类独立初判保存后；AI、终判、真实数据、强认证等未获许可部分须先做明确方案并取得人类对应授权，不能凭“项目整体完成”自动越界。作品可用合成场景和真实边界说明完成，不需要虚构真实批次批准。

项目整体完成回Codex最终验收时，请交一个明确入口文件，至少列：最后接受review_result/基线SHA及数量；自本次交接后的任务卡→执行回执→独立review→修正闭合链；实际最终交付身份；具名完整演示证据；实际调用图/四CLI及保护结果；各新增人类授权和夹具原文来源；未执行项与已知限制；139历史损失及其他偏差保持结果。不要只交最后一次“全绿”摘要，也不要要求从聊天推断授权。

看板done由人类办理。每卡执行交付与独立验收分别留痕；平台切换和最后一次总验收均不追认此前越界操作。
