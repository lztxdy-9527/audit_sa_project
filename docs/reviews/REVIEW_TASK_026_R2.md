# TASK-026-R2 复审

日期：2026-10-15。结论：**NOT_ACCEPTED，部分问题关闭**。下一步仅执行 `docs/tasks/TASK-026-R3_DRAFT.md`，不进入 TASK-027。本次是实际源码/证据复核与 GPT 复验，不以执行端勾选清单替代验收。

## 1. 已关闭与保留

R2 四份交付身份均与交接一致：

- `scripts/runtime_gate1.py`：`a373f4b508e15548bd7a17c9f5270d365b1c12d19988fedd9a9fbcef15432c3a`，60761 B。
- `tests/test_runtime_gate1_registry.py`：`e898483f369008780ae43774245d6a6a79df21edee203fd0db38becb19d41ad7`，39871 B。
- `docs/RUNTIME_GATE1_REGISTRY_GUIDE.md`：`5d11e754e957c537a9542d65f738a11604591c63342f8dace8add31ea7dac188`，8406 B。
- `docs/EXEC_REPORT_026_R2.md`：`3d2d73bf93d059ad9ddf1ad37ed83741e23ff905c93cb1858e8c299ea3a2995e`，10907 B。

GPT 实际运行当前正常入口一次，使用全新 `task026r2_gpt_20261015_040626_normal` 根：**42 项检查、0 失败、进程退出0**。20次公开API（build3/read7/prepare10）、8次冻结准备器、两次接收器CLI（0/1）。完整进程输出见本轮评审根 `current.stdout/current.stderr/current_process.json`。

本轮关闭：静态captures保留及末端字节复测、23份既有project材料加本脚本构成24项project/32项总材料、来源固定集合、时间/规则ID类型预检、起始时既有scope拒绝、20次直接API完整返回/异常、返回正文改变可被审核检出。GPT另做6次完整登记的定点API：真实来源核验返回后新增 `checks/unknown.json`，本次build定位 `batch/checks` 拒绝，原八文件字节不变；正常read/prepare与覆盖核对通过。静态材料晚变更、非法时间/rule_id及既有scope反例也由本次实际正常入口执行。

R1已关闭的真实writer半写等仅保留原证据，本次未重跑。宿主、控制器、P1/store、正式契约及生效记录、配置与旧Gate1组件未改。

## 2. B2残余：read缺少scope收尾检查

`scripts/runtime_gate1.py:902` 的read在 `_load_stored_registry` 内通过初始 `scope_path.exists()` 检查，但静态绑定消费及末端文件核对之后直接返回。build/prepare已有末端scope检查，read没有。

GPT使用字节相同的**隔离项目模型**，同一真实read实现、同一登记字节：未注入成功；真实 `_require_current_static_identity` 返回后只在隔离项目创建计划scope，**本次read仍成功**；下一次read因scope已存在而定位 `registry.scope_ref` 拒绝。注入命中1。模型目录位于本轮评审根，未在真实 `data/human_gate_decision_records/` 建删任何scope。证据：`api_probe_records.json` 后三项，模型范围明确，未冒称真实业务目录被修改。

这属于R2卡§3明确要求的“收尾核对计划路径状态”，不是新增业务规则。补read收尾这一处，勿重新设计scope或接入未来保存功能。

同属原卡路径收尾的源码遗漏：read的静态绑定直接 `_capture_file`，而公共 `_recheck_capture` 也只复读字节，没有对该文件路径调用既有逐级reparse检查。末端 `_require_fixed_members(leaf,...)` 只覆盖登记叶，不能代表project静态文件路径。本项是源码核对，**本轮未新建junction，未声称实际链接反例已跑**。可在现有 `_recheck_capture` 内复用 `_reject_reparse_chain` 补这一步，不增加I/O框架或额外路径机制。

## 3. E1残余：完整观察仍缺嵌套载荷与独立绑定

`tests/test_runtime_gate1_registry.py:98` 已记录所有直接API的完整返回/异常，这是实质进步。但没有记录 `kwargs`（build的 `scope_dir` 在其中）；返回对象直接引用，未建立独立快照。冻结准备器仅在 `EntryObserver` 统计8次，**没有8条完整输入/返回或异常载荷**。回执§7“20次公开API与8次嵌套准备器均保存完整返回或异常链”与文件不符。

`expected_payloads`（704行）只绑定返回值指纹，异常只绑定类型/字符串；args/before/field/stage/traceback/cause等完整观察不在独立预期内。审核的checks/summary等依赖候选本身与候选台账，不能把这些候选关系称为完整定稿观察比较。

GPT在实际main收尾副本中只改 `call_001.args[0]`，保持返回值、ID与计数，按canonical格式保存并同步该候选台账的派生长度/SHA：**实际审核audit_ok=true、进程退出0**。这证明完整输入观察未绑定到本次实际调用。证据：`closure_input_replace_canonical.json`。候选台账与候选自洽不能替代独立完整期望。

最低修正只需完整观察深拷贝和现有轻量记录/审核的补齐，不要求多层profile、函数代码指纹、三通道观察框架。

## 4. E1残余：失败落盘与最后消费顺序

R2的两个fault开关在706—721行，**写盘前改内存**，并用 `injected` 预设 `expected_final_status="FAIL"`。它们不是任务卡要求的“写盘后、末次正式审核前改磁盘”。最后真实审核在777行；失败时只打印和返回1，没有更新磁盘summary/failures。所谓最后字节确认在765行，早于此审核消费。

GPT复用本次真实观察，按当前真实main/末次审核代码路径在新进程执行收尾；接收器和业务组不再调用，复用来源与计数归属明示，不把重放计数算成新业务调用：

- 正常控制：进程0、磁盘PASS、failures空，台账无漂移。
- 写盘后改一项checks：真实审核失败、进程1，但**磁盘仍PASS、failures仍空**。
- 写盘后改完整返回的 `registry_file_sha256`，canonical形态合法：实际审核检出 `payload_content_mismatch:call_001`、进程1，但**磁盘仍PASS、failures仍空**。
- 末次真实审核返回后，仅给其已消费的checks追加LF：**进程0/PASS**，独立实读确认台账漂移恰为checks。

证据：`closure_probe_results.json`、`closure_disk_return_canonical.json`及相应stdout/stderr。这些是收尾控制，不是上游回归。第一版输入/返回探针使用非canonical排版而被形态检查提前拒绝，原结果保留；后续canonical隔离例单独保存，以后者支持内容结论。

修正应让同一末次裁决直接支配返回码及磁盘失败事实；全部语义消费后再做一次有界原始字节确认。失败路径可以写FAIL/非空failures/诊断，但应保留坏checks或API候选，不重建期望/台账把它洗成成功，不把失败状态写入称为正常路径“一次写定”。

## 5. E1路径残余

当前test main仅对相对路径resolve，绝对路径直接 `relative_to(TEST_ROOT)`，含 `..` 的绝对路径会绕过解析后严格后代检查。GPT输入指向**本轮评审根内部**的绝对 `TEST_ROOT/../reviews/<本轮>/outside_test_root`：进程最终因技术根已存在而退出1，但已先在证据允许根外创建空目录。未运行接收器或业务API。证据：`path_probe_result.json`及完整进程输出。

按R2卡既有要求，在任何mkdir前统一解析后判断严格后代，并保留原路径逐级reparse检查。只需这个局部修正，不需要新的路径框架。

## 6. 证据范围与保护

GPT本轮：一次当前正常入口（20次公开API、两次接收器）、另6次定点API（其中3次隔离模型）、7个仅收尾的新进程，以及1个纯路径预检新进程。后两种没有新接收/新业务API。定点API的嵌套准备器次数未单独profile，不把推算计入已观察次数。证据根：`data/reviews/task026_r2_gpt_20261015_040626/`。

GPT未修改任何既有实现/测试/指南/历史证据。新正常入口的隔离测试仅操作本轮新副本；GPT来源集合反例在本轮新批次留下unknown现场，原八文件不变。真实记录根无建删动作；所有旧现场保持原样。

GPT一次最终全树文件扫描实读158000文件：changed恰三份允许修改文件；范围外变化/新增、missing、读取错误均0；旧R5越界326项不变且不追认。新增按确切路径登记，无前缀豁免，上轮两个确切自指元数据单列。GPT未改既有实现、测试或历史证据；扫描后仅有限核对身份并定稿本轮评审元数据，无第二次全树扫描。文件哈希保护与上述目录动作分别记录，不据此追认历史越界。

## 7. 后续

发出 **B类TASK-026-R3**，仅上述scope收尾与测试观察/最终裁决/路径残余。已关闭生产行为不回归、不扩展Gate1保存。TASK-026/R1/R2继续待验收，板卡由人类处理。本结论不重新征求人类D1/D2/D3，不形成任何批次批准。

真实批准null；宿主仍开发态0008；next/AI false；真实初判未保存；未制定TASK-027。
