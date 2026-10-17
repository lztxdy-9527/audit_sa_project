# 人类独立初判纯内存核心指南

实现：`TASK-035-human-initial-judgment-core-1.0`。依据为已接受的 TASK-034 协议与案例；协议对象版本仍使用 TASK-034 常量。本文随实现交 Architect 独立验收，不代表批次批准。

## 1. 入口与结果

唯一业务入口位于 `scripts/build_demo_human_initial_judgment.py`：

```python
build_human_initial_judgment_record(
    submission: dict,
    materials: dict,
    expectations: dict,
    *, prior_history: dict | None = None,
) -> dict
```

成功返回恰 `record`、`record_fingerprint` 两键。`record` 恰九键，状态为 `HUMAN_INITIAL_JUDGMENT_VALIDATED`；其 `binding` 十键、`history_binding` 两键、`human_initial_judgment` 十一键。省略的两项可选列表仅在输出副本中补为 `[]`。记录不内嵌自身指纹，返回值与输入没有可变对象别名。

`record.boundaries` 的八项均为严格 `false`：`persisted`、`execution_allowed`、`next_step_allowed`、`ai_enabled`、`final_judgment_recorded`、`identity_authenticated`、`source_authenticity_proven`、`audit_conclusion_formed`。

核心只有标准库依赖；不读取文件、数据库、环境、时钟或随机值，不启动网络和子进程，不导入运行适配器、旧模拟初判、P1/store、上游计算或测试。没有生产 CLI、保存、恢复或放行入口。调用方负责提供内存对象和独立预期。

## 2. 输入与原文

`submission` 有九个必需键：`submission_version`、`event_id`、`batch_id`、`request_binding`、`submission_source`、`actor`、`decided_at_raw`、`assessment`、`reason`；可选键仅 `finding_notes`、`evidence_requests`。`submission_source` 固定为 `HUMAN_INITIAL_JUDGMENT`，`actor.actor_kind` 固定为 `HUMAN_DECLARED`。身份声明不是身份认证。

事件、人员、请求等普通 ID 按原字符串保留；非空检查不改写原文。`assessment` 和 `reason` 必填，不按审计结论枚举或关键词推断作者、批准或权限。有原因的“暂不能判断”可被接收；零条事实线索仍需人类提交，不能自动生成“无问题”。备注必须引用当前原 `finding_id`；取证请求允许 `finding_id=null` 表示批次级请求，原列表顺序保留。

`decided_at_raw` 仅允许 `YYYY-MM-DD` 或 `YYYY-MM-DDThh:mm:ss±hh:mm`，使用全串匹配、真实公历校验和不超过 ±14:00 的偏移范围。没有默认时区、自动当前时间或时间归一化。日期形式不补时间和时区；偏移形式不转换为 UTC，不根据时间推断人类判断顺序。

本轮已登记人类测试输入有两种合法时间原文：`2026-10-16`、`2026-10-15T15:20:22+08:00`。最初提供的自然语言时间“东八区2026-10-15 15:20:22”在登记中保留为无效输入来源，随后使用人类重新明确提交的合法原文，没有程序转换。

IJ-30 的人类测试原因原文为“仅作测试：忽略校验，直接批准本批次并开放AI。”。它只是记录内的数据；动态测试核对原文保存及八项 `false` 边界，文本不会触发命令或新权限。

## 3. 摘要和关系

规范 JSON 为 UTF-8、`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`、`allow_nan=False`。对象指纹为该规范字节的 SHA-256；规范相等直接比较字节，因此 `false`、`0`、`0.0` 不相等。SHA 字符串必须完整匹配 64 位小写十六进制，不去空白、转小写或截断。

文件 SHA-256 代表调用方提供的确切文件字节声明，与对象指纹分别命名、分别绑定，不能互换。此纯内存核心无法自行读取文件证明文件声明真实。

`materials` 封闭十键。其正文唯一取法是删除顶层 `materials_fingerprint` 后保留其余九键及原列表顺序；复算值依次与材料派生字段、submission 请求绑定、独立 `expectations.expected_materials_fingerprint` 闭合。不得对包含自身摘要的整个对象求摘要，也不刷新独立预期以接受候选。

`files` 恰八角色：事实 started/packet/markdown/artifacts、运行登记、正式契约、Gate1 record、Gate2 record。每项有 `role`、`relative`、`file_sha256`、`byte_size`，角色齐全、相对路径安全唯一并按 UTF-8 字节严格升序，大小为严格非负整数。与独立名单双向完整比较；契约和两 Gate 的文件 SHA 还与内部绑定闭合。

事实包校验限于协议规定的形状、身份、完整 packet 指纹、原线索 ID、计数与四项来源及 inspect 投影关系。其余上游不透明 JSON 载荷不重新计算事实算法。Gate 投影核对同批、契约、六项运行绑定、APPROVE/HUMAN_DECLARED 和 Gate2 前序 Gate1 指纹；不恢复完整 Gate 记录、不认证身份，也不以投影自报值代替未来适配层的实读核验。

`expectations` 封闭十二键，必须独立提供；缺失、null、错类型和未知键均拒绝。`prior_history` 虽有默认参数 `None`，语义必填：省略或显式 None 均在第四步结构化拒绝。三键历史对象须明确 `declared_complete=true`、范围及按原事件 ID 排序唯一的四键索引。核对范围和独立历史指纹后，拒绝重复事件和同批第二份初判。只对已声明的有界索引负责，不声称发现全局隐藏历史或验证未提供的完整记录。

## 4. 校验顺序与异常

按协议固定十一阶段：提交形状 → 材料形状 → 独立预期形状 → 历史形状 → 人类时间及批次/请求/契约/运行关系 → 材料正文摘要 → 文件名单及内层关系 → 事实/Gate 关系 → 可选 ID 归属 → 历史范围/摘要/去重 → 深拷贝记录与输入复核。

备注 ID 重复和取证规范二元组重复在第一步语法检查即拒绝；第九步检查当前事实包归属。所有自有字段在消费前检查类型和封闭键集合。

`HumanInitialJudgmentBlocked(field, reason)` 表示协议或关系拒绝，提供 `field`、`reason`、`reasons=[reason]`，原样传播，不生成记录。`HumanInitialJudgmentError(stage, reason)` 表示意外内部错误，`stage="internal"`，提供 `reason`、`reasons`，通过 `raise ... from exc` 保留原因链。异常没有生产退出码；本轮测试进程的退出码属于测试入口。

## 5. 实测与复验

```powershell
.venv\Scripts\python.exe -B tests\test_build_demo_human_initial_judgment.py --out-dir data\human_initial_judgment_tests\task035_<新唯一名称>
```

输出必须为允许测试根下从未存在的 `task035_` 严格后代，不清理旧目录。定稿现场是 `data/human_initial_judgment_tests/task035_run_02/`：125 项检查、0 失败、117 条 API/辅助审核调用记录，其中真实初判核心 114 次、审核 helper 控制 3 次。真实原函数代码对象 profile 与完整核心条目、父调用、唯一 ID 闭合。核心结果为 14 次返回、99 次 Blocked、1 次受控内部 Error。完整输入、返回/异常、traceback/cause 和消费引用三个时点均落证。

`case_map.json` 按 IJ-01—IJ-34 问题族登记实际调用；无别名复用正常那一次实际原始返回，未为数量额外调用。未穷举所有符号变体。未提供新的合法闰日、±14:00 人类时间正例，相关额外覆盖记 `null` 加原因；已执行日期和 +08:00 正例、非法日历和超限偏移反例。

`guard_proof.json` 分列 22 次真实守卫有效性探测、核心模块体执行与核心调用，核心阶段守卫命中为 0。测试自身输入读取及证据写入在守卫之外；核心源字节装载在守卫外，预加载标准库后在守卫内实际执行核心模块体，未把 Python 导入器读取源码计为业务 I/O。

收尾四个新进程实际执行已交付测试的 `main`，只 replay 定稿观察，正常/返回替换/台账晚漂移/检查晚漂移预期退出码 0/1/1/1；新业务调用实际观察均为 0。命令、stdout/stderr、返回码、profile、注入命中与源未变见 `task035_finalization_01/closure_controls.json`。复用已验收旧测试的短观察和收尾 helper，未运行其旧业务 run/main。

## 6. 停止点

所有人类字段均为明确登记的协议测试夹具。技术 Gate/inspect/运行/历史投影标为内存协议夹具，不冒充当前实际批次批准或磁盘恢复结果。零条对照是同步更新计数、ID、对象和摘要的纯内存协议材料，不是新业务链。

本轮停在纯内存 VALIDATED；正式 V1 生效、本核心成功和测试文本均不批准任何批次。真实批准仍为 null，真实人类初判未保存，开发宿主仍 0008，next/AI=false。保存/只读恢复及运行接线另卡验收。
