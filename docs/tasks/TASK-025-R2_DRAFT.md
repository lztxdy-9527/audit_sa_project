# TASK-025-R2：补正保存调用式与一份完整技术基样

日期：2026-10-15。沿用 C 类设计文档修正，DSH 落地、GPT 验收。只处理 `REVIEW_TASK_025_R1.md` 的三项残余；此前人类字段来源/摘要方向/目录/停止点已关闭，不重做。

## 范围

只修改两份原正文：

- `docs/proposals/HUMAN_GATE_RUNTIME_INTEGRATION_V1_DRAFT.md`，起点 `284d0a5233ef8704c8b973598ea80bef8b7563fb7abdfe2646fe3e9352d357be`（45697 B）。
- `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md`，起点 `b0b5da9448c1fabde5e9035bc7ae7028fbbcc1463b7b76510477bf95983ef3fd`（22755 B）。

只新增 `docs/EXEC_REPORT_025_R2.md`、`data/human_gate_runtime_design_checks/task025r2_<唯一轮次>/`。完整夹具 JSON 与短核验脚本只放该新根。其它既有文件全部冻结；旧回执/自检/扫描不覆盖不执行。无业务调用、无实现代码/配置/批次/记录/数据库/运行登记。

基线 `data/reviews/task025_r1_gpt_20261015_013855/source_hashes_after.json`，身份/项数/两个确切自指排除见同根 review_result。原有真实批准 null、开发宿主0008、next/AI false。

## 1. 唯一保存调用：当前来源 + 显式历史 + store 内部一次 P1

在正文选定下列调用关系，不再留下“已核验对象所以可直接信任”的假设：

```text
build_runtime_registry(batch_dir, runtime_dir, *, scope_dir)
prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id)
save_runtime_gate1_decision(batch_dir, runtime_dir, request_id,
                           submission, event_dir, *, scope_dir)
```

runtime_dir 是明确的技术输出路径，不通过任意业务 ID 拼接目录。prepare 从该目录读登记，save 在锁/历史和当前批次来源仍一致的条件下**自己重新实读 prepare**。登记 batch_id 须与实际冻结准备器/来源批次一致，不从 submission 推出预期。冻结准备器的来源材料为31项，新层加入本期新脚本后才是32项，不能把两个层级的计数混称。

save 的唯一核心保存步骤写完整：

```text
verified_history = 从实际核验的本 scope 完整事件构造
store.save_human_gate_decision_snapshots(
    event_dir / "snapshots", submission,
    current_request.materials, current_request.expectations,
    prior_history=verified_history)
```

删除此前独立 `build_human_gate_decision_record(...)` 的预调用。store 内部一次调用 P1；历史 verify 内部的复算另计。空历史也须实际枚举后形成三键对象，不允许 None/省略或默认 records=[]。current_request 取自本次真实读取，不使用调用方的旧 request 作为来源预期。保存前来源变化必须拒绝旧 submission，不建事件；写入阶段失败保留现场。

有效批准核验也须有 batch_dir/runtime_dir 或由已核验固定来源定位当前材料，不能只比较旧快照与旧登记。Gate2 的固定输出/数据库定位与其对应 runtime_dir 一致；未知/越界路径拒绝，不从任意报告路径跟随文件。

顺手更正同段实际类型/归属：boundaries 为冻结准备器七键严格 false 的对象；移除生产请求中的固定 outer_label（测试标记只在测试证据层）；context/receipt 由新运行适配器独占写，冻结 store 只负责 snapshots 六文件。不要称 P1 有七键文件失败协议或能写封套。

## 2. 固定物理归属，消除数量矛盾

本期使用**一个新脚本 `scripts/runtime_gate1.py`**，运行登记/新Gate1/有效批准核验/Gate2准备是其中的逻辑函数分组，不是四个新增模块。这样初始代码清单明确为冻结13项 + 该新文件 =14项，材料32项。

将字段表、候选 API 归属、图、计数和案例同步为这一选择。本期不允许另建 `runtime_registry.py` 等文件却继续宣称14项；未来物理拆分或新增依赖属于新版本/新批次，不能成为当前数量的可选分支。组件 SHA 仍只在未来文件实际存在时实读，本卡不得造真实文件 SHA。

## 3. 一份真正可解析、可复算的书面基样

保留已登记0001/0002/0003的人类字段原文，不新造人类内容。把完整 normal 技术基样放本轮新根一个 JSON 文件，正文可引用其路径与SHA，删除“完整”对象中的省略号/无效占位写法。

- 给出完整 run_binding、实际展开的14项 code_manifest/4项 rules_manifest、32项材料名单、七键 materials、八键 expectations、**11键 submission**与三键 prior_history；身份/时间/原因取登记夹具。`decided_at_source` 只能出现在书面 record，不能进 submission。
- 不存在组件的技术值可用明确标注的**书面虚构字节/64hex夹具常量**，不得声称它是真实组件文件哈希；“组件尚不存在”不妨碍纯内存书面夹具使用合法类型值。
- 完整展开 Gate2 材料/独立预期，与 Gate1 共用同一六项运行绑定，重新计算各自材料摘要。若展示 record/前序 wrapper，字段与冻结协议一致，先更新材料/绑定再算记录指纹，不用旧摘要覆盖新值。
- 定点核验直接读取这份最终 JSON，确认能解析、关键封闭键与冻结 AST 常量一致、SHA全串合法、名单排序/唯一/计数、expected_files双向相等、材料正文复算一致、两Gate运行绑定相等而材料摘要不同。不能再只检索“完整基样”文字或复算另一份示例 manifest 来代替。

这份基样只验证书面协议/绑定关系，不冒充实际标准化、真实SQLite核验或已执行的端到端流程。无需运行 P1/store/业务核心，无需增加案例编号、泛化校验框架或大套件。

## 4. 收尾

先建卡，完成正文与针对性局部核对后，定稿新回执，再一次最终全树扫描：changed 恰两正文，missing/读取错误/范围外变化/新增均0；新增按明示文件/本轮新根逐项登记，无前缀兜底。旧326项不变，不追认。扫描后只有限登记元数据。

回执明确已关闭项未重做，记录这三项的实际书面核验与完整基样身份；未执行按 null/原因，不把文本自检当业务通过。完整完成后停止交 GPT，不实施/制定 TASK-026、不接真实Gate执行/初判/AI/终判；看板由人类操作。
