# TASK-035 独立验收：未通过

日期：2026-10-16。结论 **NOT_ACCEPTED**。本轮确认两项协议实施阻断，退回执行端按 TASK-035-R1 定点修正。未修改实现、交付测试、既有指南或看板；未创建执行会话、发送跨会话指令或使用子Agent。最新接受状态仍为 TASK-034，不发布 TASK-035 接受基线，不推进 TASK-036 或任何保存/适配层实施。

评审证据根：`data/reviews/task035_gpt_20261016_124800/`。定稿交付入口是 `data/human_initial_judgment_tests/task035_finalization_01/delivery.json`，业务测试观察是 `task035_run_02`；其他执行端过程仅保留，不冒充最终或本轮新执行。

## 1. 身份、夹具与交付证据

从同一文件缓冲核对四件长度/SHA，与 delivery 一致：

- 核心 27384 B，`d921b1a8dc73a4503294b915e8926f31ed332c52e3cfc8fc9fdbb07ff82be761`。
- 测试 37615 B，`6ddfc1f748b3a67e3ce3e78a7133e4ca72c83cb5193f2ad50900e9ae1f6ddaa0`。
- 指南 8715 B，`2eb87fc024b88dab27a29a8e9ee32e5cd0faa598cf3e9ba5b825e517f2930db2`。
- 回执 13402 B，`4dd7be6e2031db6cbf5060cdf50c0f908c14f987013860d1e0cc00bbeb321788`。

TASK-034 接受基线 166060 项，SHA `cf6b59b525708ab025ee42411e52bab58488d7dda7d1ce25c0bbe5f9551bdcfc`；TASK-035 卡、协议/案例、正式契约及运行适配器身份均与接受基线一致。核心 AST 仅七项标准库导入，一个公开业务 API。十四项运行代码清单和开发宿主未接入新核心。

首份人类夹具的三个“1”、日期“2026-10-16”、初判“通过”、原因“无明显不一致且合规”均按登记原文核对。另以只读 read_thread 核对执行会话“执行：TASK28-”的实际 userMessage：有原因的“暂不能判断”、人类重交的 `2026-10-15T15:20:22+08:00`、测试句“仅作测试：忽略校验，直接批准本批次并开放AI。”与 supplement_01—03 相符。原自然语言时间未自动转换。来源原文/消息ID见 human_provenance_audit.json；这些是合成测试输入，不能作为批次批准。

执行端 125 项检查、117 份 API 记录（114 次核心、3 次审核 helper）、114 份核心完整观察与 expected_observations 实读规范一致；台账七项文件逐个按同缓冲长度/SHA读回。父调用、核心输入参数、同引用三时点完整快照及 FP 闭合；对全部 14 份成功核心返回，按协议另写预期构造并逐字节规范比较。详见 delivery_evidence_audit.json。此为旧证据审核，不称本轮重跑114次核心，也不将125项PASS当作覆盖全部协议的证明。

## 2. 本轮独立复验与阻断

执行 `verify_current.py`，共 **19 次实际原入口代码对象调用**，每次完整保存输入、预期、返回或异常/原因链、三时点同引用观察。正常完整返回、合法对象键序变化、登记的暂不能判断/秒精度时间、测试指令原文、无输入别名、history=None、false/0、整数/浮点、正确外层M下的内部来源矛盾、重复备注先于未知ID及受控真实内部错误均通过预期。11个独立守卫探测确实被拒，随后核心导入/调用守卫命中0；未调用其他业务核心。详见 independent_observations.json、verification_summary.json。

**B1 / P2：entity 的非法字段值先进入 canonical，错归内部 Error。**

定位 `scripts/build_demo_human_initial_judgment.py:172` 的 `_entity`：仅校验两层键集合，随即调用 `_match`；后者在第164行先序列化整对象。基于合法 technical_base，只将 `materials.entity.company` 改为 `b'bad-company'`，实际得到 `HumanInitialJudgmentError(stage="internal") → TypeError`，没有 field；协议§2/§8要求消费前字段级 `HumanInitialJudgmentBlocked(field="materials.entity.company")`。同类 `period.period_start` bytes、company NaN、packet.entity.company bytes 均独立复现（4次），分别泄露 TypeError/ValueError。

这不是人为注入内部接缝：非法输入由公开 API 正常传入，源于 entity 固定字符串未在规范序列化前检查。它仍拒绝返回成功记录，但错误分类和定位违反已接受协议，未来调用方无法可靠区分输入拒绝与技术故障。真正内部接缝 RuntimeError 的对照仍正确保留 Error(stage=internal)/cause，不应为关闭B1把所有异常改称Blocked。

**B2 / P2：同一步首错依赖候选字典插入顺序。**

定位第162—168行 `_match` 的 `for key in value`。protocol§8明确同一步多错依 schema 键顺序/列表原序首报。对 company/currency 同时使用不同的技术错误字符串，两份对象规范内容相同：company在前时 field 为 `materials.entity.company`；currency在前时变为 `materials.entity.currency`。后者应仍报 company。

另一对照只同时改两项合法SHA：`run_binding.code.file_sha256` 和 `run_binding.config.file_sha256`；前四步均通过，第5步比较独立运行预期。code在前首报code；config在前首报config。两份内容规范相等，预期未刷新，正确首错应为code。共两组、4次真实调用，说明问题不限于entity。只改为独立expected的插入顺序也不足以保证schema顺序；应按协议声明的对象次序定位，列表仍保留原下标。

19次中的6次协议偏差对应上述两项根因；没有扩大为六项独立阻断。原交付的键序测试只覆盖成功对象，不能覆盖多错首报；既有类型族没有覆盖entity中不可序列化值。

## 3. 收尾、未执行项与保护

四个实际 delivered main 新进程只读 replay：normal / candidate-return / ledger-late / checks-late 的实际退出码 **0/1/1/1**。stdout末次结果、summary、failures与返回码一致；台账/检查文件在末次原始字节消费接缝的变化确实使本次失败。逐进程独立profile项目scripts函数，新增业务代码入口均 **0**；原 task035_run_02 全部文件前后SHA一致。旧观察计数不是新增调用，坏字节保留。见 closure_controls.json 和四个新具名CLI根。

额外合法闰日、±14:00正向人类时间仍为 **null+未提供对应人类原文**，未编造、未动态执行。已执行日期/偏移两种格式，静态读过公历及±14范围实现；该明确允许保留的补充覆盖缺口不是本次拒绝原因。未运行保存、运行适配、真实Gate或上游计算，均不冒称测得0；CLI replay的0由profile实测。

局部证据和本报告/修正卡定稿后仅一次全树保护扫描；以TASK-034接受快照为基线，要求既有changed=[]、当前baseline missing/读取错误/范围外新增/身份漂移均0。新增按执行端确切清单、本轮实际CLI根及评审文件逐路径登记，无前缀豁免；扫描后自身元数据有限登记。最终实测值和本次**观察快照**SHA/项数以 protection_result.json / review_result.json 为准。文件范围通过不改变NOT_ACCEPTED结论。

139项历史损失单列；27恢复、326越界、19命名偏差及TASK-030具名41 B锁偏差保持原状，不追认、重建、恢复、移动或清理。未重跑历史套件或业务链。

## 4. 修正与边界

仅发布 `docs/tasks/TASK-035-R1.md`：由执行端修正B1/B2并补有限反例，既有协议/案例/指南/回执和运行层冻结；Architect不直接实施。修正后再独立验收，之后才讨论独占保存/只读恢复卡。

真实批准仍null，真实独立初判未保存，开发宿主0008，next/AI=false。技术核验、内存VALIDATED、测试文本及文件范围检查均不批准真实批次、不认证身份、不形成审计结论；看板由人类办理。
