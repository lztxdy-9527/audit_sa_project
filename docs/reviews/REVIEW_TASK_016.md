# TASK-016 验收记录

日期：2026-10-13；验收端：GPT。

结论：**暂不通过，返回TASK-016-R1定点修正。** 正常纯核心行为及开发态边界已实际复验；但四项来源指纹允许非法尾随LF，且G6一次实际公开调用未登记。TASK-016保持待验收；本轮不制定或实施TASK-017。

## 1. 交付身份

实际文件哈希与交接一致，GPT复验前后不变：

- 核心 `41026b98f8608b8280fbb62793bac59f766e932a17b0deae407ebc8238dd208c`。
- 测试 `d4ad4b886c9484bb79c088a2428fbc27f3c6fb93ee46a975877620d856b6e13a`。
- 指南 `d995d20d8493e44d53babd37113c96d83c34bcc54ac250f35c2fce51a828b938`。
- 回执 `50b0bc15eef10103ebec1706c7f04ba293d0feed123f455f5386ac8a71b970b6`。

宿主仍冻结 `67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a`；TASK-015测试仍冻结 `90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e`。原TASK-016卡及其他选定冻结件未改，见本轮selected_hashes_before/after。

## 2. GPT实际复验范围

GPT在全新 `data/initial_judgment_tests/task016_gpt_20261013_015839` 实际执行当前交付七组入口一次，退出0、7/7 PASS；没有重跑宿主、上游、历史任务或新建业务批次。保护扫描通过该次入口执行，基线124005项、实扫124259文件，changed=[]、missing=[]、读取错误0，冻结件与三份packet哈希一致。该完整扫描读数在本轮 `current_scan.json` 保留，无第二次全项目扫描。

外部代码帧观察器绑定交付测试实际使用的 `test.CORE`，记录真实API进入/返回及同一输入引用前后指纹；守卫期间只在内存中采集，结束后才落盘，没有因观察器写文件制造核心I/O守卫命中。

此外GPT直接调用四个来源指纹LF反例，各保留完整实际返回。**本轮真实公开核心调用总数52 = 定点4 + 原入口实际48**；未以测试自报47替代实际调用数。

独立证据位于 `data/reviews/task016_gpt_20261013_015839/`：`run_review.py`、`targeted_digest_grammar.json`、`targeted/`、`actual_api_code_frames.json`、`actual_call_audit.json`、`review_execution.json`。

## 3. 已通过部分

正常模拟文本及“暂不能判断”、MAIN12/C06b1/C03零条的批次级接收、来源/线索ID序列、完整返回指纹、原文保留、可选键规范化、无别名和确定性均实际通过。核心调用输入前后规范指纹一致，负向仅改内存副本，三份只读文件未改变。

原入口33项G4协议反例、5项绑定反例均按预期Blocked；正常及守卫调用固定五项null、next_step_allowed/ai_suggestion_allowed严格false，状态仅VALIDATED。核心静态依赖为标准库，守卫命中0；未见I/O、身份/时间自动生成、候选判断或AI解锁行为。

这些结果不覆盖新增LF反例，也不代表真实人类判断已保存/认证。宿主仍停0007，真实批准null、next=false。

## 4. B1（P2）：来源指纹尾随LF仍返回VALIDATED

位置：`scripts/build_demo_initial_judgment.py:71`、`:118`—`:119`。`^[0-9a-f]{64}$`与match的组合允许字符串在64位十六进制后带一个末尾LF；`:171`之后四项来源都复用该检查。

GPT分别深拷贝合法C06b事实包，给workbook_sha256、normalized_payload_sha256、screening_report_sha256、crosscheck_report_sha256单独追加LF。每项实际长度65；expected_packet_sha256与submission.fact_packet_sha256均按候选对象重新计算且相互一致，排除了外层指纹不匹配造成的提前拒绝。

**四次公开API全部返回DEV_INITIAL_JUDGMENT_VALIDATED，非法65字符来源原样复制进record.source，record_sha256也正确。** 输入前后不变，但应在对应来源字段拒绝。完整返回在targeted目录，参数/长度/前后指纹在targeted_digest_grammar.json。

原卡明确要求四项来源为合法64位小写十六进制指纹；不能仅因为外层对象指纹一致，就把非法来源字符串声明为已校验。这里要求严格协议形状校验，不要求纯核心抵御调用方重声明所有指纹的同权限篡改。修复共同完整匹配，不做strip/截断/转小写的静默修正。

## 5. B2（P2）：G6一次真实公开调用未进入登记与正式计数

位置：`tests/test_build_demo_initial_judgment.py:631`—`:643`。G6 action直接调用CORE.build_initial_judgment_record，绕过record_api；guard_probe返回的完整成功record没有进入api_records/call_registry。

GPT观察到原七组真实API48次：返回10、抛Blocked38；持久记录47条：返回9、Blocked38。唯一未经过record_api的调用方为action，事件EV-SIM-pure-memory，实际成功且输入未变；完整真实返回已由GPT保存在actual_api_code_frames/actual_call_audit。

因此missing/unregistered=0仅证明已登记47条内部一致，不能证明所有实际调用均已登记。原卡§7要求每次新API直接调用都有完整返回或异常和登记；这次遗漏正发生在纯内存停止点验收，必须补齐那一次实际守卫结果，不能通过再调用一次核心补造记录。

记录落盘应在守卫解除后完成，避免把测试记录I/O误判成核心I/O。修复后实际核心次数与本模式登记数严格一致，保留完整结果/异常链及正式failures。

## 6. 辅助记录（非阻断）

1. 回执G4称28个提交反例+11个事实包反例；实际源码和记录为22+11=33。新回执按实际数更正，不回写旧回执。
2. 原隔离自测同时删除一条file_ledger及其registry，并非只改一处。GPT已调用交付真实audit_ledger，仅删除副本一条registry，其他记录/台账/文件不动，准确报未登记；性质独立补证，见strict_registry_helper.json，不另设阻断或要求重复建链。
3. 已登记引用及冻结保护本轮通过；不能用它们追认漏记G6为已登记。R1只补受影响证据，不重新审核全部历史流程。

## 7. 后续

交执行端 `docs/tasks/TASK-016-R1.md`：仅核心严格指纹匹配、相关定点测试/G6登记、必要指南更新及新回执/新容器。原合法输出协议保持，宿主/控制器/上游/packet冻结；不保存真实判断、不解锁AI、不建0008。

R1验收通过后继续按持续授权制定TASK-017。DSH由人类操作，GPT没有访问看板或关闭卡片。
