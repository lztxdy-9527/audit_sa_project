# 有效 Gate2 决定后的 SQL 筛查与只读恢复

实现版本：`TASK-031-runtime-gate1-1.0`。本指南对应 TASK-031，仅说明新运行层的一次规则筛查动作。正式技术验收仍由独立架构会话作出。

## 1. 接口与前提

`scripts/runtime_gate1.py` 新增两个公开 API，无 CLI：

```python
run_gate2_approved_screen(
    batch_dir, runtime_dir, *, scope_dir, event_relative,
    database_path, gate2_event_relative
)
inspect_gate2_approved_screen(
    batch_dir, runtime_dir, *, scope_dir, event_relative,
    database_path, gate2_event_relative
)
```

`scope_dir`、`event_relative` 仍引用本运行的 Gate1；`gate2_event_relative` 引用固定 Gate2 事件。数据库为前序已核验的 `runtime.sqlite3`。调用方不能传入 status、预期指纹或批准字符串替代实读。

两个接口实际调用 `verify_runtime_gate2_decision`，要求同批次完整 GATE2 APPROVE、来源 `HUMAN_GATE_DECISION`、身份声明 `HUMAN_DECLARED`、质量 OK 且三项计数为严格整数 0。契约与共享运行绑定须等于当前登记；前序摘要闭合到本次完整有效 Gate1。HOLD/REJECT 是合法记录，但本次筛查动作在核心调用和输出创建前拒绝它们。失败、锁、不完整凭证或材料变化也阻断。

这是当前明确 API 调用的单次动作前提，不颁发其他步骤许可。P1 的 `execution_allowed=false`、`persisted=false` 保持原值。契约生效、D2 建设授权、模拟夹具决定及本接口返回均不批准真实批次。

## 2. 真实核心与读取绑定

冻结核心 `scripts/screen_demo_sqlite.py` 的独立 SHA-256 为 `1b123766b57849c1d64a5a18cb504fbeb03f563bcd96b2de708586f19c9e71fe`，版本 `TASK-006-rule-core-1.1`。它仍在原 14 项代码清单中，四份 SQL 沿用既有规则清单。

运行前固定来源八文件、登记二文件、Gate1 八文件、Gate2 八文件、装载四文件、数据库及静态材料/SQL的实读缓冲。对象、长度、文件 SHA 来自同一缓冲。前序核验返回后再次确认这些初始字节与固定集合，才独占建立输出并执行一次：

```python
screen_sqlite(str(database_path), load_report_object, cutoff_date="2026-09-30")
```

`load_report_object` 从本次已绑定缓冲解析，真实调用前后比较同一引用规范指纹；输入被改写即拒绝。数据库字节也须仍等于起始读数。运行不调用标准化、装载或决定保存；inspect 不重新运行 SQL。原十个公开接口签名与协议不变。

完整真实报告以 canonical JSON + 单 LF 写入，UTF-8、无 BOM。每份文件用真实独占 writer 写入并读回，与本次待写缓冲逐字节相等，不能用重新读取的候选建立预期。文件 SHA 与对象规范指纹分列，canonical 使用 ensure_ascii=False、sort_keys=True、separators=(",", ":")、allow_nan=False。

## 3. 输出形状

输出是登记叶同级 `<登记叶名>.screen/`；必须从未存在，已有空目录或文件也拒绝。成功目录恰三文件，按以下顺序独占写入：

1. `started.json`：八键，`started_version=TASK-031-approved-screen-start-1.0`，批次、来源、登记、Gate1/Gate2 事件、数据库路径及五键 bindings。bindings 保存登记文件 SHA、Gate2 两键结果文件 SHA、Gate2 record 规范指纹、装载报告文件 SHA、共享 run_binding。
2. `screening_report.json`：冻结核心完整 18 键返回。保留 `DEVELOPMENT_TEST_ONLY`、`DEV_RULES_COMPUTED`、`next_step_allowed=false`、全部 limits 与人类提示。
3. `artifacts.json`：十一键，`artifacts_version=TASK-031-approved-screen-artifacts-1.0`；登记/前序/装载/started/报告文件 SHA、报告规范指纹、运行绑定及三键数据库声明。数据库 byte_size 是严格非负整数。

成功返回恰六键：`stage_version`、`status`、`batch_id`、`run_binding_sha256`、`artifacts`、`boundaries`。前两值分别为 `TASK-031-approved-screen-1.0`、`RT_RULE_SCREEN_RECORDED`。boundaries 恰八键，全部严格 false：crosscheck_recorded、fact_packet_recorded、human_initial_judgment_saved、ai_enabled、audit_conclusion_formed、identity_authenticated、source_authenticity_proven、next_step_allowed。

## 4. 报告关系和只读恢复

run/inspect 都核验报告顶层封闭 18 键、版本、期间与截至日、开发标记、DB 前后 SHA、database_unchanged=true、read_only 的 ro 和严格整数 query_only=1。load_source 七键与本次装载报告和十键数据库元数据闭合；其中字符串 `"false"` 不转换成布尔 false。

R01—R04 四规则的 SQL 路径/SHA/版本绑定当前清单，计数为严格非负整数，与 findings 实际规则归属和总长相符，hit_key 唯一。主表净额、已知/缺失关联净额及缺失分项与装载报告精确相等；两成功旗标严格 true。R02 超额等于报告 R02 线索金额之和。计算金额/计数拒绝 bool 和同值 float；Excel 来源 cells 按原始证据保留，不将原始字符串、空值改写成计算金额。

inspect 只读绑定文件和已有报告，不重跑规则算法。它使用同缓冲解析与摘要，检查封闭 started/artifacts 及跨文件关系，再构造返回值。全部语义消费完成后有界复核来源、静态、事件、DB、三输出的初始/本次 writer 字节、固定集合、failure、锁和逐级 reparse；之后直接返回，无候选读取生成成功。

## 5. 失败现场

协议/路径/变化阻断使用 `RuntimeGate1Blocked(field, reason)`；运行/I-O 使用 `RuntimeGate1Error(stage, reason)`。冻结 `RuleScreenBlocked` 按实际加载模块类对象映射为 Blocked；`RuleScreenError` 为 Error，完整 reasons 与 cause 链保留。

仅当本次已建立输出目录时独占写 `failure.json`，恰六键：failure_version/kind/stage/field/reason/cause_chain。版本 `TASK-031-approved-screen-failure-1.0`，kind 为 BLOCKED 或 ERROR。无目录不为诊断造目录；不重试、覆盖、清理半写或声称回滚。诊断写入失败保留主次错误。

inspect 优先核验有效 failure，再消费其他可能半写文件；它不写 failure。旧运行版本不迁移、不补签。需要新运行时新建登记/Gate1/装载/Gate2 事件，保留旧现场。

## 6. 本轮验证入口

```text
.venv\Scripts\python.exe -B tests\test_runtime_approved_screen.py --out-dir data\runtime_approved_screen_tests\task031_<新名>
```

定稿实测根 `data/runtime_approved_screen_tests/task031_run_01/`：21 项检查、0 失败。四个独立新进程只重放已定稿观察，通过同一个实际 main/收尾路径验证 normal、candidate-return、ledger-late、checks-late，退出 0/1/1/1；不重新建链或执行 SQL。原文与结果见 `task031_finalization_01/closure_controls.json`。

正常小样的规则计数为 0/1/0/0，R02 超额 400000 分；这是测试预期，不进入生产规则。完整 SQL 返回/报告字节、同引用三时点、DB不变、HOLD、前提/路径、真实晚变更、真实 artifacts 半写及原因链均留证。

未开放复算、事实底稿、真实独立初判、AI、终判或任何真实数据/网络流程。真实批准仍 null；开发宿主 0008、next/AI=false；线索不能直接认定舞弊、损失或审计调整。
