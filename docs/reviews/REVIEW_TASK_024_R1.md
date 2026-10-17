# TASK-024-R1 复审：NOT_ACCEPTED

日期：2026-10-14。依据实际文件、原任务卡及 R1 修复卡。**剩余三组阻断：B1、B3、E2。** 原 TASK-024 和 R1 保持 in_review；不制定 TASK-025。人类操作看板、作出真实业务决定。

## 1. 身份、实际复验与证据边界

实读交付身份与交接一致：

- 适配器 `e03f02ae2dbb63746bb44d6b2e7b9af47824c04397999176b2224f1705c9441f`，74560 字节。
- 测试 `4e162d8c5a0fbff30ab84670e284768c19c1d81c2cfbc983c20fe097faa23291`，115505 字节。
- 新回执 `1fbac54da25e08d174bb1896fd187adbf4392bb8b5c6568c1ec89767769d983d`，16809 字节。
- 指南 `9c8f4409a1c964a65fe64139424795e635ecdf33a55f1724fec683fe9998c2fb` 未改。

证据根：`data/reviews/task024_r1_gpt_20261014_152547/`。13 项有限身份核对/源码副本见 `finite_audit.json`、`reviewed_inputs/`；冻结 prepare/store/P1/契约及生效登记/配置/宿主/控制器一致，GPT 未改实现或测试。

读取了既有 `task024r1_run_08` 的 summary/core_observations/calls/ledger_readback/protection 及源码；其中 74 项、8 项写后审核、junction 和故障轮次是**执行端既有证据，不是本轮 GPT 重跑结果**。发现必要反例后未再运行完整本卡入口、任何历史套件或上游宿主链。

GPT 实际执行：两个全新正常接收批次（真实 receiver CLI 均退出 0，完整原文留证），在全新记录根完成 25 个有名称的定点操作及另外 5 次技术组装 prepare；后 5 次没有逐条单独留完整返回，本评审不把 25 条称整个驱动的完整 API 登记/独立入口计数。另有一次真实 P1 的受控观察器辨识度调用。该范围在 `finite_audit.json` 明确登记。没有改旧业务源或旧证据；故意修改/恢复限本轮隔离输入。

## 2. B1 未关闭：第二遍确认之后仍有必要消费

实现约 756—762、1260—1276、1383—1404 行。R1 增加第二遍 `_final_confirm_decision_request`，但最后一遍仍读取 adapter 文件、加载核心并复算材料正文；此时历史文件/失败/集合的确认已经结束。

先无注入真实 verify 成功，观察 `_adapter_bytes` 实际读取 **3 次**：首次来自 verify，第 2/3 次来自两遍 `_final_confirm_decision_request`。`adapter_read_observation.json` 保存实际调用行号和同缓冲 SHA。随后只包装真实 reader：**第 3 次真实读取返回原字节后**，仅改变一项，不改 SHA：

- 较早事件 context 追加 LF；
- 当前 source quality_report 追加 LF；
- 目标事件新增合法七键 failure；
- scope 新增空事件目录。

**四例本次均返回 VERIFIED**，每例读取 3 次/注入 1 次；撤销 wrapper 保留变更后均 Blocked，恢复本轮原件后均成功。证据：`probe_records.json`、`verification_summary.json`。只读 verify 未写失败诊断。

这不是要求无限追逐任意并发变化：必须把材料正文复算、核心/静态绑定消费、对象校验等必要工作放在终端字节/集合确认之前，再做一轮有界终端确认。不能仅多加第三/第四遍来源确认，随后继续必要消费。最后核验自身字节的单纯哈希操作与重新加载核心、计算语义对象应分开。本评审不要求原子多文件快照或返回之后不再变化。

原 R1 探针命中较早的 2/3 接缝，只能证明那个接缝被下一遍覆盖，不能证明最后必要消费之后的义务已满足。该点应在新回执纠正，旧回执不回写。

## 3. B3 部分关闭，历史 evidence schema 仍漏检

`_validate_request_schema` 已补材料/期望/部分清单严格类型，但对 `request.evidence.source_scope` 与 `source_description` 没有按冻结准备器的真实形状校验。

从实际合法两事件出发，各独立改变较早事件的一个字段：

- `request.evidence.source_scope=7`；
- `request.evidence.source_description=[]`。

仅同步该事件 context/receipt 和后继 prior_events 的必要字节哈希；六份冻结快照、record、材料和期望不变。两例公开 verify **均成功**。外层关系已经同步，拒绝不能被旧 SHA 提前遮蔽；恢复原件成功。见 `historical_evidence_*`。

仍属于原 R1 “request 六键及全部嵌套证据的完整封闭 schema”要求，不新增业务口径。修复须核对冻结准备器输出的实际 source_scope/description 等字段，不因有七个顶层键就称完整；历史内部关系应与已有材料/配置/规则声明闭合，仍不读取历史业务源。已通过的严格 float/false/缺键等修正保留，不重新复制一套历史反例。

## 4. E2 未关闭：覆盖/输入不变性不是函数代码稳定性

### 4.1 执行端自己的观察已经显示缺口

从同一 `task024r1_run_08` 读取真实帧汇总与完整观察条目：

- 冻结 prepare：入口 **92**，完整条目 **85**。
- store.save：入口 **27**，完整条目/summary **24**。
- store.verify：入口 **78**，完整条目 **78**。
- 真实 P1：入口 **105**，`real_p1_seam` 条目 **102**。

条目共 289，四层入口合计 302，相差 13。**不是要求不同层次数相等，而是每层自身的实际入口与登记覆盖闭合。** 回执 §1“真实 P1 22 次”还是早期 seam 数，不能覆盖最终 105 次；交接引用 store.save 27 而 summary 是 24，也需更正。

实际 `evidence_audit` 对原件 `ok=true`；再只删一条核心条目（289→288），保留 ID/声明/帧观察等其他载荷，仍 `ok=true`。这是**隔离调用真实 helper**，不是 GPT 重跑一个故障套件。`evidence_probe.json` 保存原件、删项及来源范围。当前审核只检查条目唯一/存在，不强制同层入口完整覆盖。

### 4.2 “289/289 引用不变”测的是函数代码

测试 263—320 行：`code_fingerprint(function)` 比较函数代码；`describe_input` 的 `value` 保留原对象引用。没有真实消费对象调用前/返回后/API 收尾指纹，且前快照会跟输入对象一起变化。

GPT 的受控辨识度反例：读取本轮合法输入，调用真实 P1 一次取得真实返回，再由测试 wrapper 改内存 submission.reason；没有改任何业务文件，**不声称冻结 P1 自己会修改输入**。实际输入 SHA 从 `79fffb57…d5e8` 变为 `3f8b891a…9160`，观察器仍 `reference_unchanged=true`；条目中的 `inputs[0].sha256` 是旧值，而其 `value` 已变成新值。把该完整观察交给实际 audit 仍 `ok=true`。

完整结果、原对象前后 SHA、记录的 SHA/对象矛盾在 `evidence_probe.json`。该证据明确证明当前观察器不能验证任务要求的输入不变性；不能拿函数代码未变来替代消费对象未变。

### 4.3 已修好部分保留

统一登记本层公开 prepare、完整返回 value、终审前冻结期望、首轮磁盘内容比较、类型敏感比较、台账读回与 receiver 完整原文均已有实现或既有正向证据。本轮不重复列为阻断。修复只需补真实入口覆盖、消费对象三时点与快照/指纹一致性，并把它们接到已存在的正式失败路径；不再新造通用审核框架。

## 5. 可保留项及未重跑范围

GPT 新批次独立正向控制：z_first(rev1)→a_second(rev2) 可保存并恢复；EV2/HOLD(B)→EV1/APPROVE(A)→EV3/REJECT(B) 可保存并恢复第三事件。因此 **B2 本轮定点通过**。同批规则仍由冻结 P1 执行。

B4 的已知拒绝映射/loader/主次错误报告、E1 的真实句柄故障方法源码及既有回执记录支持修复；**本轮没有重跑这些故障**，不把它们重新派发为阻断。旧 guides/回执不回写，来源/计数的更正在新回执完成。

独立 tests/r1_points.py 曾越界创建后删除、区间替换误删后还原、pending_agreement=false 的阶段标签等按执行端自报登记。本轮没有追认先前范围偏差，也不因最终文件恢复而隐去过程；目前不另列业务阻断。看板第 7—13 项尚未补勾不影响实际文件验收，GPT 未操作看板。

GPT一次最终保护扫描：基线147001项，实扫149658文件；**changed恰为适配器和测试两项，范围外变化、missing、读取错误、范围外新增均0**。允许新增按执行端确切文件/明确根、本轮评审/两个新批次/新记录根及前轮两个自指元数据逐项登记，没有 reviews/gate1 前缀兜底；旧现场和junction保留。扫描后只有限登记评审及元数据，不重新扫描项目树。NOT_ACCEPTED修复基线的完整SHA/项数/两个确切自指排除见同目录review_result.json。

结论：**NOT_ACCEPTED**。只制定 `docs/tasks/TASK-024-R2_DRAFT.md` 修剩余 B1/B3/E2，B 类 DSH 实施。真实批准仍 null、宿主仍开发态 0008、next=false、AI=false；不接 Gate2/真实初判/0009/执行放行。
