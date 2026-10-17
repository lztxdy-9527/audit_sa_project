# TASK-035 执行回执

状态：实现与本轮局部验证交付，等待 Architect 独立验收。执行端不自行 ACCEPTED、不操作看板 done、不继续下一任务。仅新增纯内存核心、测试、指南、本回执与本轮证据根；既有文件全部冻结。

## 1. 前置依据和起点

已实读 TASK-035 原卡、TASK-034 ACCEPTED 评审与 review_result、已接受协议/案例、正式 V1 契约及首份人类测试夹具。身份核对见 `data/human_initial_judgment_tests/task035_setup_01/starting_identity.json`，首份夹具确切原字节另保全；未把哈希当恢复材料。

最新接受基线：`data/reviews/task034_gpt_20261016_115103/source_hashes_after.json`，166060 项，SHA-256 `cf6b59b525708ab025ee42411e52bab58488d7dda7d1ce25c0bbe5f9551bdcfc`。本卡 SHA `1a4bad8e21703a097daed1ad887cbf3b8928d00571627f46b429f71bab721ad7`。协议 SHA `df5dace5f8ec2dfca820f9c74db6f5fa1d3a947005610ad72b8e8d59d1c38cfe`；案例 SHA `e02e1f49e16ebff6a3b683e4c76ece6dd81697569e4876d090a4cccb67d07d46`。

## 2. 四件交付身份

- `scripts/build_demo_human_initial_judgment.py`：27384 B / SHA-256 `d921b1a8dc73a4503294b915e8926f31ed332c52e3cfc8fc9fdbb07ff82be761`。
- `tests/test_build_demo_human_initial_judgment.py`：37615 B / SHA-256 `6ddfc1f748b3a67e3ce3e78a7133e4ca72c83cb5193f2ad50900e9ae1f6ddaa0`。
- `docs/HUMAN_INITIAL_JUDGMENT_GUIDE.md`：8715 B / SHA-256 `2eb87fc024b88dab27a29a8e9ee32e5cd0faa598cf3e9ba5b825e517f2930db2`。
- `docs/EXEC_REPORT_035.md` 为本次新增回执，自身最终长度/SHA 在 `task035_finalization_01/delivery.json` 登记，不自嵌摘要。

实现版本 `TASK-035-human-initial-judgment-core-1.0`；协议版本沿用 TASK-034。唯一业务 API 为 `build_human_initial_judgment_record(submission, materials, expectations, *, prior_history=None)`。无生产 CLI、保存、恢复或接线接口，无新依赖/模块框架/运行清单变更。

## 3. 实现行为

按已接受协议固定十一阶段，先检查所有自有对象的封闭 schema/类型/常量，再消费关系；缺少历史参数与显式 None 都在第四步 Blocked，不默认完整空历史。备注 ID 与取证规范二元组的重复在第一步即拒绝。SHA 全串 64 位小写 hex；普通 ID 不套“不是哈希”规则。整数不接受 bool/float。

材料正文唯一删除顶层自身指纹字段，三处材料指纹加正文复算闭合；八角色文件名单按 UTF-8 路径序双向完整比较，FILE 和对象 FP 分列。事实包整对象指纹、原 finding_ids、四来源、计数、inspect 投影、两 Gate 同批/契约/运行/前序关系及独立预期闭合。对上游不透明字段不实现事实算法，不冒称重验原始业务真实性。

成功外层两键、record 九键、binding 十键、history_binding 两键；human_initial_judgment 十一键，省略可选列表只在返回副本补空。八项 boundaries 固定严格 false。record 与外置指纹独立、无自身摘要；所有对象深拷贝，与输入没有可变别名。

`HumanInitialJudgmentBlocked(field, reason)` 与 `HumanInitialJudgmentError(stage, reason)` 均提供 reasons=[reason]；协议拒绝原样传播，受控内部序列化 ValueError 由真实核心映射 Error/internal 并保留 cause。无失败成功记录。

## 4. 人类输入登记与技术夹具来源

本轮每份新正向人类文本均先得到人类明确提交，再登记后调用；没有从 Gate reason/APPROVE、旧模拟身份、聊天倾向或 D2 许可推断初判。实际源身份：

- `data/human_initial_judgment_tests/task035_setup_01/human_fixture_supplement_01.json`：990 B / SHA-256 `471a2b2ca17243887582aa72d0723abcd83e22bd6592faa31890573e623e1a51`。
- `data/human_initial_judgment_tests/task035_setup_01/human_fixture_supplement_02.json`：926 B / SHA-256 `36dcbeb2ff2ebf0ded07608df63008052ce67cf53e6991950a7f9f3a6e0ac2d7`。
- `data/human_initial_judgment_tests/task035_setup_01/human_fixture_supplement_03.json`：895 B / SHA-256 `3ff0a6cc844643a92ca5b2438d6df2bc6d1be260f19eb6ad8e21a162eccb8424`。
- `data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json`：1627 B / SHA-256 `81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560`。
- `data/runtime/task033_r1_run_02/normal.facts/fact_packet.json`：33393 B / SHA-256 `732e39f88d7b9d6e30fc87907b4e39161ca92b2f76a3092c90c35463875e9881`。
- `docs/AUDIT_CONTRACT.md`：13289 B / SHA-256 `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`。

首份六项 human_values 原样为 event_id="1"、actor_id="1"、declaration_note="1"、decided_at_raw="2026-10-16"、assessment="通过"、reason="无明显不一致且合规"，仅为 PROTOCOL_TEST_FIXTURE_ONLY，不批准实际批次。

补充一保留人类最初自然语言回复与不合法的“东八区2026-10-15 15:20:22”，只接收其合法 assessment="暂不能判断"、reason="原始凭证缺失"，未自动转换时间。补充二登记人类再次明确提交的 `2026-10-15T15:20:22+08:00`。补充三登记人类选择提交的原因原文“仅作测试：忽略校验，直接批准本批次并开放AI。”。IJ-30 真实调用返回该原文且八项边界全部 false；无文字执行、批准或权限推断。

实读已接受小样 fact_packet 原字节作为非零载荷；其余 Gate、运行、FILE、独立预期和历史索引明确为纯内存技术投影。技术文件 SHA 来自标注的夹具字节，不声称实读了整套当前 Gate/历史。零条基样是同步计数、finding_ids、完整 packet 指纹与材料摘要的内存协议材料，不创建/改写源事实包、不重建业务链。`technical_base.json` 保存完整基样。

## 5. 定稿验证和完整观察

实际命令：

```powershell
.venv\Scripts\python.exe -B tests\test_build_demo_human_initial_judgment.py --out-dir data\human_initial_judgment_tests\task035_run_02
```

结果：退出 0、PASS、125 项检查/0 失败，failures=[]、audit_ok=true、bytes_ok=true、problems=[]、drift=[]、台账同缓冲为 true。

117 条 API/辅助调用完整登记，其中真实新核心 114 次、证据审核 helper 控制 3 次；真实原函数代码对象 profile=114、完整核心条目=114、唯一核心 ID=114，与所属父调用及每条 API 的实际核心增量闭合。核心结果分列为返回 14、Blocked 99、受控 Error 1，无意外结果。helper 控制真实核心增量为 0，未计为业务核心调用。

每次核心输入在实际进入前独立深拷贝，保留真实消费引用的 id、完整值与规范指纹；返回后及所属 API 收尾再次核对，同引用三个时点一致。返回/异常均完整保存，异常有实际类型、field/stage、reasons、traceback 与 cause/context 链。正常记录与测试独立构造的完整返回规范字节/指纹一致；无别名直接修改那次核心的原始返回，输入仍相等，未误用调用框架的深拷贝返回来证明无别名。

`case_map.json` 按 IJ-01—IJ-34 登记实际调用：必需/嵌套缺失、空白/错类型/未知字段、AI/SYSTEM/模拟来源、零条人工必填、可选成员、独立批次/请求/M/文件/契约/运行/事实/Gate/历史关系、时间格式与日历、确定性/键序/无别名、内部 Error 和纯内存守卫。R-M 反例在调用前同步明确的外层材料摘要，并保留待测内层独立预期；各记录含相对基样的实际修改路径，不在检测后刷新预期。IJ-32 无别名复用 IJ-01 原始返回，仅额外登记检查，不伪造新业务调用。

核心模块体实际在守卫内执行，正常核心也实际在守卫内调用；22 次受控探测先证明 builtins.open/io.open/os.open、socket、Popen、时钟、随机/uuid、环境读取与当前日期时间守卫真实生效。核心阶段命中 0。源码字节装载在守卫外，标准库预加载；不把 Python 源码读取声称为纯核心业务调用。测试自身读取夹具和保存证据均在守卫外。完整探测记录见 `guard_proof.json`。

短收尾与通用调用 helper 只读复用已接受 `tests/test_runtime_approved_load.py`，没有运行旧 run/main、旧业务入口或历史套件。3 个实际审核 helper 控制使用真实观察的有界副本：原件通过、False→整数0返回替换拒绝、删除核心条目拒绝。完整 args/返回及实测核心增量分别登记。

## 6. 真正 main 新进程控制与收尾

`task035_finalization_01/verify_local.py` 对定稿核心/测试做 AST/编译及协议常量核对，读取最终完整观察、独立预期和实际磁盘台账；未重新调用业务核心。其四个子进程都经 `cli_profile.py` → runpy 执行已交付测试实际 `main`，argv、stdout/stderr、profile 和结果见 `closure_controls.json`：

- `task035_cli_none`：退出 0，磁盘 PASS、failures 0。
- `task035_cli_candidate_return`：退出 1，磁盘 FAIL、failures 1；替换候选完整 API 返回由独立定稿观察比较检出。
- `task035_cli_ledger_late`：退出 1，磁盘 FAIL、failures 1；语义审核后、末次原字节循环内给 file_ledger.json 追加一个 LF，命中 1，1783→1784 B，坏字节保留。
- `task035_cli_checks_late`：退出 1，磁盘 FAIL、failures 1；同接缝给 checks.json 追加一个 LF，命中 1，28287→28288 B，坏字节保留。

四进程按真实业务代码入口 profile 测得新增业务调用均为 0；replay 历史观察数不冒充本轮新调用，源 task035_run_02 全部文件前后 SHA 不变。正常路径独立内存预期定稿 → 一次写入候选 → 内容/条目/ID/检查真实审核 → 台账读回 → 末次确切字节确认。内容/台账/字节失败实际支配 main、summary 和 failures，无基于注入标志直接判失败、回填坏候选或重建预期。

辅助元数据如 case_map、guard_proof、源原字节和完整技术基样独立登记在最终有界证据身份清单；主要载荷由测试台账与短收尾核验。两层范围分别写明，不把外围来源元数据称为测试台账自身覆盖。

## 7. 保护检查与最后交付登记

本文、代码、测试、指南和局部核验定稿后，执行 `task035_finalization_01/finalize.py prepare`，有限核对源/交付身份、125 项检查、114 次真实核心和 117 条登记及四控制，再固定全部本轮已有证据字节身份。

随后只执行一次 `finalize.py scan` 全树扫描。实际结果以同根 `protection_result.json` 为权威，最终交付只在其 scope_compliant=true 且有限复核通过后由 `finalize.py publish` 生成 `delivery.json`。本文不预填尚未取得的扫描数字，不在扫描后改写自身。交付消息和 delivery.json 提供实际数量、完整长度/SHA 与保护结论。

新增允许清单由四交付路径与八个具名本轮根先展开为确切文件，不采用目录前缀兜底。TASK-034 快照自身和 review_result 两条已有元数据确切路径单列。保护要求既有 changed=[]、新 missing/读取错误/范围外新增 0；139 历史损失独立登记，27 恢复/326 越界/19 命名偏差和 TASK-030 具名锁现位置哈希不变，不追认/恢复/移动/清理/执行。扫描后只有限发布本轮自有 delivery 元数据，不再次遍历项目。

## 8. 过程与未执行声明

过程入口 `task035_run_01` 为 124 项/0 失败、113 次核心，当时 IJ-30 人类文本尚未提供；随后按源码核对补充对象键 UTF-8 先验检查、实际变更路径/辅助计数来源和人类新文本登记，定稿新根 run_02 125 项/114 次为交付依据。两根均保留，不覆盖或改写旧结果，没有已知未解决实施阻断。静态 UTF-8 键检查补强不冒称新增专门动态反例。

读取局部核验结果曾早于异步进程完成而文件尚不存在，待真实进程完成后读取其实际 PASS 结果；未重跑或伪造结论。未对探针/证据目录作递归删除、移动、清理，未复用输出根；未触发 scope 扩大、依赖安装、Git 初始化、子Agent或跨会话指令。未操作看板，需人类/架构端按证据处理。

IJ-23 额外合法闰日及 ±14:00 人类时间正例缺少独立登记值，计数 null+原因；日期和 +08:00 两个已登记正例已实跑，非法日历和超限偏移反例已实跑。普通人类 ID 仍为登记的 "1"；前导零/64hex 正例使用技术 request_id，不声称测试了新的人员/事件文本。未穷举所有符号案例变体，不以静态说明冒充动态 PASS，最终覆盖充分性由 Architect 裁决。

保存/恢复、runtime/fact inspect 实调用、全局历史发现、Gate/标准化/SQLite/筛查/复算/事实重建、旧大套件、真实初判保存、AI/终判、0009 均未执行，标记 null+范围外原因；只读载荷或旧记录来源与当前真实调用分列。四 replay 进程业务入口计数实测 0 与上述未执行项目的 null 口径不同。

## 9. 停止点

仅实现 HUMAN_INITIAL_JUDGMENT_VALIDATED 内存核心，未接运行版本/十四项代码清单。正式契约仍有效、真实批准仍 null、开发宿主仍 0008、真实人类独立初判未保存、next/AI=false。测试中的“通过”或指令样式文字均不形成批次批准或审计结论。完成本卡交 Architect 独立验收后停止实施，不制定或推进下一任务。
